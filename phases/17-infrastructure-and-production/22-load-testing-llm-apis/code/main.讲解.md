# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 22 节 对 LLM APIs 进行负载测试：为什么 k6 与 Locust 会产生误导 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`random`、`statistics`），无需网络、GPU 或真实 LLM 端点

---

## 1. 这份代码在考察什么

这是一个约 90 行的"反模式演示器"，用一个极简的前缀缓存模型说明讲义中的 **prompt-uniformity trap（单一 prompt 陷阱）**：

1. **同一个压测框架、不同的 prompt 分布，会得到完全不同的数字**：UNIFORM（500 个相同前缀）几乎全部命中缓存，TTFT 看起来恒为 80 ms；REALISTIC（随机长度 + 80 个前缀池）出现 79 次未命中，P99 跳到 800 ms。
2. **缓存命中率决定 TTFT 分布**：TTFT 只有"命中 80 ms / 未命中 800 ms"两个取值，P50/P99/均值完全由命中次数决定。
3. **为什么要按 mean + stddev 采样**：`make_realistic_workload` 用 `rng.gauss(500, 180)` 生成输入长度，模仿 LLMPerf 的 `--mean-input-tokens` / `--stddev-input-tokens`。

同时要看清它的简化：并发参数实际上不影响结果、prompt 长度与 TPOT 常量都没有参与计算、缓存无限大。讲义说代码"measures effective TPOT"，实际并没有测 TPOT。

> 一句话：**用两种工作负载在同一个缓存模型上的对比，说明"压测数字由 prompt 分布决定"**——但它只演示机制，不给出真实容量。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PREFIX_CACHE_HIT_TTFT_MS` / `..._MISS_...` | 模块常量 | 命中 80 ms、未命中 800 ms | 前缀缓存对 TTFT 的影响 |
| `TPOT_MS`、`BATCH_EFFICIENCY_SHARED_PREFIX` | 模块常量 | 定义了但**未使用** | （本意是 TPOT 与共享前缀批处理效率） |
| `Request` | dataclass | 一个请求：`prompt_tokens`、`prefix_hash` | 压测请求 |
| `make_uniform_workload` | 函数 | 500 个相同请求（2,000 token、同一前缀） | 单一 prompt 陷阱 |
| `make_realistic_workload` | 函数 | 长度 ~N(500, 180)、前缀从 80 个中随机选 | 真实 prompt 分布 |
| `simulate` | 函数 | 按批遍历请求、查/写缓存、收集 TTFT、算 P50/P99/均值 | 压测结果统计 |
| `main` | 函数 | 三种并发 × 两种工作负载，打印对比表 | 演示入口 |

数据流：`main` → 对每个并发值构造 UNIFORM / REALISTIC 工作负载 → `simulate` 返回统计字典 → f-string 打印表格。

---

## 3. 逐段精讲

### 3.1 常量：一个两档的 TTFT 模型

```python
PREFIX_CACHE_HIT_TTFT_MS = 80
PREFIX_CACHE_MISS_TTFT_MS = 800
TPOT_MS = 15
BATCH_EFFICIENCY_SHARED_PREFIX = 0.8  # batch serves 1/0.8 = 1.25x fewer slots
```

- 命中前缀缓存时跳过大部分 prefill，TTFT 只有 80 ms；未命中则需要完整 prefill，800 ms。10 倍的差距是本演示的全部"物理"。
- ⚠️ `TPOT_MS` 和 `BATCH_EFFICIENCY_SHARED_PREFIX` 在整个文件中**没有被引用**。注释里的"1/0.8 = 1.25x fewer slots"也没有对应实现。讲义说代码会"measures effective TPOT"，实际输出只有 TTFT。

### 3.2 `Request` 与两种工作负载

```python
@dataclass
class Request:
    prompt_tokens: int
    prefix_hash: str


def make_uniform_workload(n: int = 500) -> list[Request]:
    return [Request(2000, "single_prefix") for _ in range(n)]
```

- `@dataclass` 自动生成 `__init__`，`Request(2000, "single_prefix")` 即可构造。
- UNIFORM：所有请求都是同一个前缀，相当于"k6 循环 500 次同一个 prompt"。

```python
def make_realistic_workload(n: int = 500, seed: int = 7) -> list[Request]:
    rng = random.Random(seed)
    reqs = []
    prefixes = [f"prefix_{i}" for i in range(80)]
    for _ in range(n):
        prompt = max(50, int(rng.gauss(500, 180)))
        reqs.append(Request(prompt, rng.choice(prefixes)))
    return reqs
```

- `random.Random(seed)` 创建**独立的**随机数生成器，不影响全局 `random`，且固定 seed=7 让结果可复现。
- `rng.gauss(500, 180)`：正态分布采样输入长度，`max(50, ...)` 截断下限（实测 500 个样本中有 4 个被截到 50）。实测均值 503.9、总体标准差 170.9、最大 1,008。讲义的 LLMPerf 示例是 stddev 150，这里用 180，属于参数差异。
- 前缀从 80 个里有放回地抽取 500 次，实测**只出现了 79 种**（有一个前缀从未被抽到）。
- ⚠️ 80 个前缀服务 500 个请求，命中率高达 84%。这个"真实"工作负载其实仍然很缓存友好，所以 REALISTIC 的 P50 依然是 80 ms。

### 3.3 `simulate`：缓存模型与分位数

```python
def simulate(reqs: list[Request], concurrency: int) -> dict:
    cache: set[str] = set()
    ttft_samples: list[float] = []
    # serialize in groups of "concurrency"
    for i in range(0, len(reqs), concurrency):
        batch = reqs[i:i + concurrency]
        unique_prefixes = len({r.prefix_hash for r in batch})
        for r in batch:
            hit = r.prefix_hash in cache
            ttft = PREFIX_CACHE_HIT_TTFT_MS if hit else PREFIX_CACHE_MISS_TTFT_MS
            if not hit:
                cache.add(r.prefix_hash)
            ttft_samples.append(ttft)
```

- `cache` 是一个 `set`，代表"服务端已经缓存的前缀"。容量无限、永不淘汰。
- `range(0, len(reqs), concurrency)` 以 `concurrency` 为步长切批，`reqs[i:i + concurrency]` 取出一批。
- ⚠️ **并发参数形同虚设**：批内仍是逐个查缓存并**立即** `cache.add`，同一批里后面的请求能看到前面请求刚写入的缓存，等价于完全串行。无论并发是 10 还是 200，每个前缀都恰好 miss 一次，结果完全相同。真实系统里"同时在途"的相同前缀请求未必能共享缓存（除非服务端做了合并或前缀共享）。测验 Q10 给出了"整批结束后才写缓存"的改法。
- ⚠️ `unique_prefixes` 计算后从未使用（本意可能是配合 `BATCH_EFFICIENCY_SHARED_PREFIX` 建模批内共享）。

```python
    ttft_samples.sort()
    p50 = ttft_samples[len(ttft_samples) // 2]
    p99 = ttft_samples[int(len(ttft_samples) * 0.99) - 1]
    return {
        "n": len(reqs),
        "p50": p50,
        "p99": p99,
        "mean": statistics.mean(ttft_samples),
        "cache_hits": sum(1 for t in ttft_samples if t == PREFIX_CACHE_HIT_TTFT_MS),
    }
```

- 分位数用"排序后取下标"的近似法。n = 500 时 P50 取下标 250，P99 取下标 `int(495.0) − 1 = 494`，即第 495 个样本，等同于 nearest-rank 法 `ceil(0.99 × 500) = 495`。
- 当 `n × 0.99` 不是整数时，这个写法会偏低一位：例如 n = 10 时 `int(9.9) − 1 = 8`（第 9 个样本），而 nearest-rank 应取 `ceil(9.9) = 10`（第 10 个，即最大值）。更稳妥的写法是 `math.ceil(q * n) - 1`，或直接用 `statistics.quantiles` 并注明插值方法。
- `cache_hits` 通过"TTFT 等于命中值"反推命中次数，依赖于两档 TTFT 取值不同；若以后 TTFT 模型变复杂，应在循环里直接计数。

### 3.4 `main`：三种并发 × 两种工作负载

```python
    for concurrency in (10, 50, 200):
        print(f"\nConcurrency = {concurrency}")
        header = f"{'Workload':22}  {'n':>5}  {'TTFT_P50':>9}  {'TTFT_P99':>9}  {'mean':>7}  cache_hits"
        ...
        uniform = make_uniform_workload(500)
        u = simulate(uniform, concurrency)
        print(f"{'UNIFORM':22}  {u['n']:5}  {u['p50']:8.0f}ms  {u['p99']:8.0f}ms  {u['mean']:6.0f}ms  {u['cache_hits']:4}")
```

- 每轮都重新构造工作负载，`make_realistic_workload` 的 seed 固定，所以每轮的 REALISTIC 请求序列完全相同。
- `{'Workload':22}` 字符串默认左对齐占 22 列；`{'n':>5}` 右对齐占 5 列；`{u['p50']:8.0f}` 宽 8、0 位小数。`print("-" * len(header))` 让分隔线与表头等长。
- 最后两行 `print` 是全课的结论："uniform prompts make your endpoint look fast"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| TTFT 只有命中/未命中两档 | 让"缓存命中率决定数字"一眼可见 | 真实 TTFT = 排队 + 与未缓存 token 数成正比的 prefill + 网络；用真实 benchmark 标定 |
| 缓存用无限大的 `set` | 代码最短 | 真实前缀缓存受显存/CPU 内存限制，会 LRU 淘汰；高前缀多样性下命中率更低 |
| 批内串行更新缓存 | 简单 | 并发参数不起作用；真实压测应是并发在途、开环到达（open-loop） |
| 80 个前缀的"真实"分布 | 演示有差异即可 | 命中率仍高达 84%；应从生产日志统计真实前缀多样性 |
| 用 gauss 采样长度但不用它 | 展示 LLMPerf 的 mean/stddev 思路 | 长度对结果无影响；应让 TTFT 依赖未缓存 token 数 |
| 固定 seed | 输出可复现，便于教学 | 真实压测应多次运行观察方差（skill 要求 3-run stability） |
| 不发任何网络请求 | 无需端点即可运行 | 真正压测用 LLMPerf / k6 / GenAI-Perf 打真实 streaming 端点 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟类型注解求值；让 `list[Request]` 等写法在旧版本 Python 中也能用 |
| `@dataclass` | `class Request: prompt_tokens: int` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| 类型注解 | `def simulate(reqs: list[Request], concurrency: int) -> dict:` | 只是提示，运行时不检查 |
| 带注解的变量 | `cache: set[str] = set()` | 声明变量类型；空集合必须用 `set()`，`{}` 是空字典 |
| 默认参数 | `n: int = 500, seed: int = 7` | 调用时可省略 |
| 独立随机数生成器 | `rng = random.Random(seed)` | 与全局 `random` 隔离，结果可复现 |
| `rng.gauss` / `rng.choice` | `rng.gauss(500, 180)`、`rng.choice(prefixes)` | 正态采样 / 从列表随机取一个 |
| 列表推导式 | `[Request(2000, "single_prefix") for _ in range(n)]` | `_` 表示不使用的循环变量 |
| 集合推导式 | `{r.prefix_hash for r in batch}` | 去重后的前缀集合 |
| 生成器表达式 + `sum` | `sum(1 for t in ttft_samples if t == ...)` | 不建中间列表地计数 |
| 步长 `range` 与切片 | `range(0, len(reqs), concurrency)`、`reqs[i:i + concurrency]` | 分批遍历；切片越界不会报错 |
| 条件表达式 | `A if hit else B` | 三元表达式 |
| `statistics.mean` | `statistics.mean(ttft_samples)` | 标准库求均值 |
| f-string 格式符 | `{'n':>5}`、`{u['p50']:8.0f}`、`{'Workload':22}` | 右对齐、宽度、小数位；字符串默认左对齐 |
| 字符串乘法 | `"=" * 95`、`"-" * len(header)` | 重复字符串画分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3，耗时不到 1 秒），三种并发输出完全相同，这里只截取一组：

```text
Concurrency = 10
Workload                    n   TTFT_P50   TTFT_P99     mean  cache_hits
------------------------------------------------------------------------
UNIFORM                   500        80ms        80ms      81ms   499
REALISTIC                 500        80ms       800ms     194ms   421

Concurrency = 50   ……与上面完全相同
Concurrency = 200  ……与上面完全相同

Read: uniform prompts make your endpoint look fast. Realistic prompts tell the truth.
LLMPerf: --mean-input-tokens + --stddev-input-tokens. Always.
```

逐项解读：

- **UNIFORM 499 次命中**：只有第一个请求 miss。均值 `(499×80 + 800)/500 = 81.44 ≈ 81 ms`。唯一的 800 ms 排在下标 499，P99 下标 494 仍是 80 ms——**一次冷启动被 P99 完全"藏"起来了**。
- **REALISTIC 421 次命中**：实际出现 79 种前缀 → 79 次 miss。均值 `(421×80 + 79×800)/500 = 193.76 ≈ 194 ms`；P50（下标 250）为 80，P99（下标 494）为 800。
- **为什么三种并发一样**：见 3.3 节，批内串行写缓存。改成"整批结束才写缓存"后（测验 Q10），UNIFORM 的 hits 分别变为 490 / 450 / 300，REALISTIC 变为 417 / 392 / 285。
- **"真实"分布仍然偏乐观**：把前缀池扩到 500（实际出现 313 种）后，hits 降到 187，P50 也变成 800 ms，均值 530.72 ms。真实数字取决于生产流量的前缀多样性。
- **讲义练习 1 的答案**：差距主要在尾部和均值（P99 80 → 800 ms，均值 81 → 194 ms）；P50 两者都是 80 ms，**只看 P50 会完全错过这个问题**。

---

## 7. 动手改一改

1. **（讲义练习 1）** 把 `make_realistic_workload` 的前缀池从 80 改为 300、500、5000，记录 cache_hits 与 P50 何时从 80 跳到 800（提示：hits 跌破 251 时）。
2. 删掉未使用的 `unique_prefixes`，或者真正用上它：让同一批中共享前缀的请求按 `BATCH_EFFICIENCY_SHARED_PREFIX` 折算成本。
3. 实现测验 Q10 的 `simulate_concurrent`：同批请求看不到彼此写入的缓存，观察并发对 hits 的影响。
4. 让 TTFT 依赖 `prompt_tokens`：`ttft = base + uncached_tokens × per_token_ms`，并用 `TPOT_MS` 和一个输出长度分布计算 E2E，输出 E2E 的 P50/P99。
5. 给缓存加容量上限（用 `collections.OrderedDict` 实现 LRU），观察缓存容量 20 时 REALISTIC 的命中率变化。
6. 进阶：把批同步模型改成开环到达（泊松到达 + 有限并发槽位的排队模型），复现"负载升高 → 排队 → TTFT 尾部爆炸"的拐点，这就是 Ramp 测试要找的容量拐点。

---

## 8. 常见坑

- **只看 P50**：本例两种工作负载 P50 都是 80 ms，差距全在 P99 和均值。
- **P99 藏住少量极端值**：500 个样本中 1 个 800 ms 不会出现在 P99 上；要看 max 或 P99.9，或者单独统计冷启动次数。
- **以为加了长度随机化就"真实"了**：前缀多样性才是缓存命中率的决定因素，本例 80 个前缀依然 84% 命中。
- **以为并发参数在起作用**：先确认模型里并发真的影响了计算，否则"并发 10 与 200 一样"会被误读为"系统完全没有瓶颈"。
- **定义了常量就以为建模了**：`TPOT_MS`、`prompt_tokens` 都没有进入计算，读代码时要追踪每个变量是否被使用。
- **分位数下标写法**：`int(n * q) - 1` 在 `n × q` 不是整数时会比 nearest-rank 低一位（小样本时尤其明显）；生产统计用成熟库（如 HdrHistogram、`numpy.percentile`）并注明插值方法。
