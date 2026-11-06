# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 18 节 生产服务技术栈：KV 卸载与缓存感知路由 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`random`），无需 GPU、无需 vLLM

---

## 1. 这份代码在考察什么

代码用 120 行左右的标准库 Python，模拟一个"4 个 vLLM 引擎、6 种共享前缀模板、200 个请求"的小集群，比较三种 KV 处理策略：

| 配置 | 含义 | 对应讲义 |
|------|------|---------|
| `NATIVE_ONLY` | 不卸载，引擎本地最多记住 4 个前缀，未命中就重新 prefill | 基线：HBM 不够时只能重算 |
| `CPU_OFFLOAD` | 引擎本地卸载到 CPU，本地缓存不淘汰，写出有少量开销 | 原生 vLLM CPU offload（engine-local） |
| `LMCACHE` | 4 个引擎共享一个集群级缓存，本地未命中时可以从 LMCache 读回 | LMCache connector（cross-engine） |

它想让你体会讲义的核心论点：**跨引擎共享前缀可以避免重复 prefill**。代码确实显示 LMCACHE 避免的重算次数最多（194 次）。

> 一句话：**用"命中就跳过 prefill、未命中就重算"的计数模型对比三种 KV 策略**——但要看清它的常数让"从 LMCache 读回"比"重新 prefill"慢 7.5 倍，结果 LMCACHE 反而最慢，而且模拟并没有真正建模 HBM 容量和抢占。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PREFILL_TOK_PER_MS = 40.0` | 常数 | prefill 速度：每 token 0.025 ms | 重算成本 |
| `DECODE_TOK_PER_MS = 0.15` | 常数 | decode 速度：每输出 token 6.67 ms | decode 主导总时延 |
| `CPU_OFFLOAD_TIME_MS_PER_BLOCK = 1.5` | 常数 | 写出到 CPU 的每块代价（实际再乘 0.1） | 卸载开销 |
| `LMCACHE_TIME_MS_PER_BLOCK = 3.0` | 常数 | 从 LMCache 读回的每块代价 | 读回成本 |
| `KV_BLOCK_TOKENS = 16` | 常数 | 每个 KV 块 16 个 token | PagedAttention 的块大小 |
| `Request` | `@dataclass` | prompt 长度、输出长度、前缀模板 ID | 请求 |
| `make_workload(n, seed)` | 函数 | 生成 200 个请求：prompt ∈ {2000, 4000, 8000}，输出 150–400，前缀 6 选 1 | 高复用负载 |
| `simulate(config, reqs)` | 函数 | 逐个请求随机分配引擎，按配置决定 prefill 耗时，累加总时间 | 三种 KV 策略 |
| `report(row, baseline)` | 函数 | 打印总时间、prefill 时间、避免次数、加速比 | 结果展示 |
| `main()` | 函数 | 生成负载 → 跑基线 → 跑三个配置并打印 | 入口 |

数据流：`make_workload()` → 为每个配置复制请求列表 → `simulate()` 逐请求累加 `prefill_ms + decode_ms` → `report()` 以 NATIVE_ONLY 总时间为基线算 speedup。

---

## 3. 逐段精讲

### 3.1 常数与请求

```python
PREFILL_TOK_PER_MS = 40.0
DECODE_TOK_PER_MS = 0.15
CPU_OFFLOAD_TIME_MS_PER_BLOCK = 1.5
LMCACHE_TIME_MS_PER_BLOCK = 3.0
KV_BLOCK_TOKENS = 16


@dataclass
class Request:
    prompt_tokens: int
    output_tokens: int
    prefix_id: str  # for reuse across engines
```

- 每 token 的 prefill 代价 `1/40 = 0.025 ms`；每块（16 token）的 LMCache 读回代价 3.0 ms，即每 token `0.1875 ms`——**读回比重算贵 7.5 倍**。这个比例决定了 LMCACHE 的结局（见 3.4）。
- 真实系统里，从 CPU DRAM 经 PCIe 读回一块 KV 远比重新做一次 prefill 便宜，讲义所有"LMCache 有帮助"的结论都建立在这一前提上；代码的常数与此相反。
- `@dataclass` 自动生成 `__init__`，于是可以 `Request(2000, 300, "tpl_1")` 这样构造。
- `KV_BLOCK_TOKENS = 16` 对应 vLLM PagedAttention 的默认块大小。

### 3.2 生成负载：少量模板 = 高复用

```python
def make_workload(n: int = 200, seed: int = 7) -> list[Request]:
    rng = random.Random(seed)
    prefixes = [f"tpl_{i}" for i in range(6)]  # small set = high reuse
    reqs = []
    for _ in range(n):
        prompt = rng.choice([2000, 4000, 8000])
        reqs.append(Request(prompt, rng.randint(150, 400), rng.choice(prefixes)))
    return reqs
```

- `random.Random(seed)` 创建**独立的**随机数生成器，固定种子 7，每次运行得到相同的 200 个请求（各模板出现次数：tpl_1 44、tpl_4 35、tpl_2 34、tpl_3 32、tpl_0 30、tpl_5 25）。
- ⚠️ prompt 长度与 `prefix_id` **相互独立**：同一个 `tpl_1` 的请求可能是 2000、4000 或 8000 token。后面命中缓存时却把整段 prompt 都当作已缓存，相当于假设"整个 prompt 就是共享前缀"——这会高估复用收益。

### 3.3 `simulate()` 的骨架

```python
def simulate(config: str, reqs: list[Request]) -> dict:
    """Model a small cluster under HBM pressure."""
    engines_state: list[set[str]] = [set() for _ in range(4)]
    shared_cache: set[str] = set()
    hbm_capacity_blocks_per_engine = 900
    total_time_ms = 0.0
    re_prefills_avoided = 0
    prefill_work = 0
    rng = random.Random(11)

    for r in reqs:
        eng = rng.randrange(len(engines_state))
        blocks = (r.prompt_tokens + KV_BLOCK_TOKENS - 1) // KV_BLOCK_TOKENS
        cached_local = r.prefix_id in engines_state[eng]
        cached_lmcache = r.prefix_id in shared_cache
```

- `engines_state`：4 个集合，每个记录该引擎"本地持有哪些前缀"。`shared_cache`：LMCache 里有哪些前缀。
- `rng.randrange(4)`：**随机路由**，不是 cache-aware 路由。讲义强调生产栈的 router 是 cache-aware 的（阶段 17 · 11），这里没有体现。三个配置都用种子 11，所以每个请求在三种配置下落到同一个引擎，比较是公平的。
- `(p + 16 - 1) // 16` 是整数**向上取整**的惯用写法：2000 → 125 块，4000 → 250 块，8000 → 500 块。
- ⚠️ `hbm_capacity_blocks_per_engine = 900` 定义后**从未使用**。整个模拟没有 HBM 容量约束、没有并发、没有抢占——docstring 所说的"under HBM pressure"和"break-even HBM utilization"都没有实现。

### 3.4 三个分支

```python
        if config == "NATIVE_ONLY":
            if cached_local:
                prefill_ms = 0
                re_prefills_avoided += 1
            else:
                prefill_ms = r.prompt_tokens / PREFILL_TOK_PER_MS
                engines_state[eng].add(r.prefix_id)
                if len(engines_state[eng]) > 4:
                    engines_state[eng].pop()
```

- 本地命中就免 prefill；未命中就重算，并把前缀加入本地集合；超过 4 个就"淘汰"一个，用来模拟 HBM 装不下。
- ⚠️ `set.pop()` 弹出的是**任意**元素，不是 LRU；可能弹掉**刚加入**的前缀。更麻烦的是，弹出哪个取决于字符串哈希顺序，而 Python 每个进程的 `str` 哈希是随机化的，因此这一行的结果**每次运行都可能不同**（见第 6 节）。

```python
        elif config == "CPU_OFFLOAD":
            if cached_local:
                prefill_ms = 0
                re_prefills_avoided += 1
            else:
                prefill_ms = r.prompt_tokens / PREFILL_TOK_PER_MS
                engines_state[eng].add(r.prefix_id)
                prefill_ms += blocks * CPU_OFFLOAD_TIME_MS_PER_BLOCK * 0.1
```

- 未命中时重算，再加上"写出到 CPU"的开销 `blocks × 1.5 × 0.1`（乘 0.1 大概是想表达"异步卸载大部分被隐藏"，但代码没有注释）。
- ⚠️ 这里**没有淘汰**：本地集合可以无限增长，每个引擎最终持有全部 6 个前缀；命中时 `prefill_ms = 0`，**从 CPU 读回的代价完全没算**。所以它领先的原因是"无限容量 + 免费读回"，而不是 CPU 卸载本身的效率。
- 避免次数 176 = 200 − 24，24 正好是"6 个前缀 × 4 个引擎"各首次未命中一次。

```python
        elif config == "LMCACHE":
            if cached_local:
                prefill_ms = 0
                re_prefills_avoided += 1
            elif cached_lmcache:
                prefill_ms = blocks * LMCACHE_TIME_MS_PER_BLOCK
                engines_state[eng].add(r.prefix_id)
                re_prefills_avoided += 1
            else:
                prefill_ms = r.prompt_tokens / PREFILL_TOK_PER_MS
                shared_cache.add(r.prefix_id)
                engines_state[eng].add(r.prefix_id)
```

- 三级查找：本地命中 → 免费；LMCache 命中 → 付读回代价并放进本地；都没命中 → 重算并同时写入 LMCache 与本地。
- 避免次数 194 = 200 − 6：整个集群只需要为每个前缀 prefill 一次——这是讲义"cross-engine sharing"的体现。
- ⚠️ 但读回代价 `blocks × 3.0` 比重算贵 7.5 倍：8000 token 的请求读回 1500 ms，而重算只需 200 ms。于是 LMCACHE 的 `prefill` 时间（14,800 ms）反而是三者中最高的。只有把 `LMCACHE_TIME_MS_PER_BLOCK` 调到 0.4 以下，读回才比重算划算。
- ⚠️ 这一分支的本地集合同样不淘汰，与 NATIVE_ONLY 的"最多 4 个"不对等。

### 3.5 累加与返回

```python
        decode_ms = r.output_tokens / DECODE_TOK_PER_MS
        total_time_ms += prefill_ms + decode_ms
        prefill_work += prefill_ms

    return {
        "config": config,
        "total_ms": total_time_ms,
        "prefill_ms": prefill_work,
        "re_prefills_avoided": re_prefills_avoided,
    }
```

- 所有请求**串行相加**，没有并发和批处理；decode 对三种配置完全相同，总计约 366,033 ms，占总时间 97% 以上，所以三者的 speedup 只差 1–3%。
- 返回 `dict` 而不是 dataclass，方便 `report` 用键名读取。

### 3.6 报告与入口

```python
def report(row: dict, baseline: float) -> None:
    speedup = baseline / row["total_ms"] if row["total_ms"] else 1
    ...

def main() -> None:
    base = make_workload()
    baseline = simulate("NATIVE_ONLY", [Request(r.prompt_tokens, r.output_tokens, r.prefix_id) for r in base])["total_ms"]
    for cfg in ("NATIVE_ONLY", "CPU_OFFLOAD", "LMCACHE"):
        report(simulate(cfg, [Request(r.prompt_tokens, r.output_tokens, r.prefix_id) for r in base]), baseline)
```

- `speedup = 基线总时间 / 本配置总时间`：> 1 表示更快。它是**串行时延之比**，不是讲义所说的"throughput gain"。
- `main` 为每次 `simulate` 用列表推导式复制一份请求；`simulate` 并不修改请求，这份复制是多余但无害的。
- ⚠️ NATIVE_ONLY 被模拟了两次（一次求基线、一次报告）。在同一个进程内哈希顺序相同，两次结果一致，所以第一行的 speedup 总是 1.00x；但不同进程之间结果会变。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用"前缀 ID 集合"代表 KV 缓存 | 计数简单 | 没有块级容量、没有部分前缀命中；生产中按块哈希管理，命中的是共享前缀那一段 |
| 随机路由 | 代码短 | 讲义的生产栈用 cache-aware 路由；随机路由会低估本地命中率 |
| 串行累加时延 | 易于理解 | 没有并发就没有 HBM 压力和抢占，讲义要演示的"preemption-heavy"场景并不存在 |
| NATIVE_ONLY 用 `set.pop()` 淘汰 | 一行代码模拟"装不下" | 非 LRU、可能弹掉新元素、结果随哈希种子变化；应使用 `OrderedDict` 实现 LRU |
| CPU_OFFLOAD 不淘汰、读回免费 | 表达"CPU 内存够大" | 比较不公平；应计入 PCIe 读回时间与 CPU 内存上限 |
| LMCache 读回 3.0 ms/块 | 想表达"跨网络比本地慢" | 比重算慢 7.5 倍，与讲义前提相反；真实值应由带宽实测决定，应远低于 0.4 ms/块才有意义 |
| `hbm_capacity_blocks_per_engine` 未使用 | 可能是未完成的功能 | 无法给出讲义练习 1 要求的"break-even HBM 利用率" |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class Request:` 三个带类型注解的字段 | 自动生成 `__init__`、`__repr__`、`__eq__` |
| 带泛型的类型注解 | `list[Request]`、`list[set[str]]`、`-> dict` | Python 3.9+ 可以直接用内置类型做泛型 |
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，在旧版本里也能写 `list[Request]` |
| 独立随机数生成器 | `random.Random(seed)`、`rng.choice`、`rng.randint`、`rng.randrange` | 不影响全局 `random` 状态，固定种子可复现 |
| f-string 生成字符串 | `f"tpl_{i}"` | 在字符串里插入变量 |
| 列表推导式 | `[set() for _ in range(4)]`、`[Request(...) for r in base]` | 注意 `[set()] * 4` 会得到 4 个**同一个**集合，必须用推导式 |
| 集合操作 | `x in s`、`s.add(x)`、`s.pop()`、`len(s)` | `in` 查找平均 O(1)；`pop()` 弹出任意元素，顺序由哈希决定 |
| 整数向上取整 | `(a + b - 1) // b` | `//` 是整除；这是不借助 `math.ceil` 的常用写法 |
| 条件表达式 | `baseline / row["total_ms"] if row["total_ms"] else 1` | 防止除以 0 |
| `if / elif / else` 分派 | `if config == "NATIVE_ONLY": ... elif ...` | 按字符串选择策略；更工程化的写法是策略类或字典分派 |
| 字典字面量返回多值 | `return {"config": config, ...}` | 调用方用 `row["total_ms"]` 取值 |
| f-string 格式符 | `{row['config']:14}`、`{row['total_ms']:8.0f}`、`{speedup:4.2f}` | 宽度、小数位；字符串默认左对齐，数字默认右对齐 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，耗时不到 0.1 秒）：

```text
================================================================================
vLLM PRODUCTION STACK + LMCACHE — preemption-heavy, 4 engines, shared prefixes
================================================================================
NATIVE_ONLY     total=  374133 ms  prefill=   8100 ms  avoided_re_prefill= 127  speedup=1.00x
CPU_OFFLOAD     total=  369402 ms  prefill=   3369 ms  avoided_re_prefill= 176  speedup=1.01x
LMCACHE         total=  380833 ms  prefill=  14800 ms  avoided_re_prefill= 194  speedup=0.98x

Read: when prefixes repeat across engines, LMCache avoids redundant prefills
even when each engine individually evicted the cache.
```

逐项解读：

- **decode 主导**：200 个请求的 decode 合计约 366,033 ms；即使所有 prefill 都不命中，prefill 总量也只有 22,850 ms。所以三者总时间只差 1–3%。
- **NATIVE_ONLY**：避免 127 次、prefill 8,100 ms。**这一行不可复现**：用 `PYTHONHASHSEED=0/1/2/3` 运行，prefill 依次为 9,650 / 9,650 / 9,100 / 10,100 ms，避免次数 114 / 111 / 118 / 115，speedup 也随之在 1.01–1.02x、0.98–0.99x 之间变化。我们把淘汰改成 LRU（见测验 Q11）后，结果稳定为 total 374,683 ms、prefill 8,650 ms、避免 123 次。
- **CPU_OFFLOAD**：避免 176 次（= 200 − 6 前缀 × 4 引擎）、prefill 3,369 ms，略快于基线。它赢在"本地缓存不淘汰、读回不计成本"。
- **LMCACHE**：避免 194 次（= 200 − 6），最多；但 prefill 一栏高达 14,800 ms，总时间比基线**慢** 2%。原因是每次 LMCache 命中都要付 `块数 × 3.0 ms` 的读回代价，比重算贵 7.5 倍。
- **"Read:" 结论只说对了一半**：LMCache 的确"avoids redundant prefills"，但在这些常数下避免重算是**亏本**的。把 `LMCACHE_TIME_MS_PER_BLOCK` 改为 0.2 后，LMCACHE 总时间降到 367,533 ms，成为三者中最快——这才是讲义想说明的情形。
- 讲义练习 1 问"HBM 利用率到多少时 LMCache 开始划算"，这份代码没有 HBM 利用率的概念，无法回答。

---

## 7. 动手改一改

1. **修正读回成本**：把 `LMCACHE_TIME_MS_PER_BLOCK` 从 3.0 逐步调到 0.1，画出 LMCACHE 总时间曲线，找到与 NATIVE_ONLY、CPU_OFFLOAD 的交点（理论打平点是 0.4 ms/块）。
2. **LRU 淘汰**：用 `OrderedDict` 给三个配置都实现容量为 4 的本地 LRU（参考测验 Q11），让比较公平且可复现；再把容量改成 2、6，观察避免次数的变化。
3. **给 CPU_OFFLOAD 加读回成本**：命中时按 `blocks × CPU_READ_MS_PER_BLOCK` 计费，并为 CPU 内存设上限。
4. **使用 `hbm_capacity_blocks_per_engine`**：以块为单位跟踪每个引擎的 KV 占用，超过 900 块就按 LRU 淘汰；然后扫描"负载强度"，输出不同 HBM 利用率下三种配置的表现，回答讲义练习 1。
5. **cache-aware 路由**：把 `rng.randrange(4)` 换成"优先选择本地已有该前缀的引擎，否则随机"，观察 NATIVE_ONLY 与 LMCACHE 的差距如何缩小（这说明路由与缓存是同一层问题）。
6. **部分前缀**：给每个模板一个固定的共享前缀长度（如 1500 token），命中时只免掉这部分 prefill，剩余部分照常计算。

---

## 8. 常见坑

- **只看"命中次数"不看"命中代价"**：LMCACHE 避免次数最多却最慢，命中后的读回时间必须和重算时间比较。
- **用 `set.pop()` 当淘汰策略**：既不是 LRU，也不可复现；需要可复现的模拟时，避免依赖集合或字典的哈希顺序，或固定 `PYTHONHASHSEED`。
- **`[set()] * 4`**：会创建 4 个指向同一对象的引用，修改一个就全改了；本代码正确地使用了列表推导式。
- **比较条件不对等**：三个配置的本地容量不同（4 / 无限 / 无限），任何结论都会被这一差异主导。
- **把串行时延比当作吞吐提升**：没有并发的模拟无法体现 HBM 压力、抢占与 goodput。
- **相信 docstring**：docstring 说会报告 break-even HBM 利用率，代码并没有实现；读代码时以实际逻辑为准。
