# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 14 节 Prompt 缓存与语义缓存的经济性 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数，瞬间完成） ｜ **依赖**：仅标准库（`dataclasses`、`random`），不调用任何真实 API

---

## 1. 这份代码在考察什么

讲义把缓存分成两层，并强调"缓存是协议，不是开关"。代码用一个两层缓存模拟器给出账单对比：

1. **L2 前缀缓存的计费结构**：写入付溢价（5 分钟 TTL 1.25 倍、1 小时 TTL 2 倍），读取只付 1/10。
2. **并行陷阱**：并行到达的请求在缓存写好前一起 miss，只写不读。
3. **L1 语义缓存**：命中时完全跳过 LLM，连输出费都省掉。
4. **组合效果**：不缓存 → L2 → 修复并行 → 再叠加不同命中率的 L1，账单逐级下降。

它与讲义的 "L2 — provider prompt/prefix caching"、"L1 — app-level semantic caching"、"The parallelization anti-pattern" 三节一一对应。

> 一句话：**用一个可复现的模拟器展示"写入溢价 + 读取折扣 + 跳过 LLM"如何决定缓存账单**。但这个模拟器对并行波次和 TTL 的建模过于简化，导致它自己算出的并行惩罚只有约 1.17 倍，与讲义的"5–10 倍"相去甚远——读懂原因是本节最有价值的练习。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `BASE_INPUT` 等 5 个价格常量 | 模块常量 | 新鲜输入 / 输出 / 缓存读 / 两档写入价（$/M token） | L2 计费结构 |
| `Request` | `@dataclass` | 一次请求：prompt 长度、前缀哈希、是否属于并行波次、到达时间 | 工作负载 |
| `Config` | `@dataclass` | 是否开 L1 / L2、是否施加并行惩罚、L1 阈值与命中概率、TTL 档位 | 缓存配置 |
| `make_workload()` | 函数 | 生成混合负载：60% 单发、40% 一波 5 个并行 | 并行流量 |
| `simulate()` | 函数 | 逐个请求走 L1 → L2 → 计费 | 两层缓存 |
| `report()` | 函数 | 运行一次模拟并打印一行 | — |
| `main()` | 函数 | 依次跑 5 种配置 | 逐级对比 |

数据流：`make_workload()` → 复制成 `reqs` → 对每个 `Config` 调用 `simulate(reqs, cfg)`（L1 命中则跳过；否则 L2 查集合 → 读 / 写计费；最后加输出费）→ `report` 打印成本与计数。

同目录的 `main.ts` 是 TypeScript 版本（不在本批讲解范围），可对照阅读。

---

## 3. 逐段精讲

### 3.1 价格常量

```python
BASE_INPUT = 3.00       # $/M input tokens (Claude Sonnet-class)
BASE_OUTPUT = 15.00     # $/M output tokens
CACHED_INPUT = 0.30     # 10x cheaper read
CACHE_WRITE_5MIN = 1.25 * BASE_INPUT  # write premium 5-min TTL
CACHE_WRITE_1HR = 2.00 * BASE_INPUT   # write premium 1-hour TTL
```

- 单位都是"美元 / 百万 token"，所以后面统一写成 `tokens / 1e6 * 单价`。
- `CACHE_WRITE_5MIN = 3.75`、`CACHE_WRITE_1HR = 6.00`、`CACHED_INPUT = 0.30`，与讲义（Claude 3.5 Sonnet，2026-04 快照）一致。
- 用表达式 `1.25 * BASE_INPUT` 而不是直接写 3.75，表达的是"写入溢价是基础价的倍数"，改基础价时溢价自动跟着变。

### 3.2 两个数据类

```python
@dataclass
class Request:
    prompt_tokens: int
    prefix_hash: str
    is_parallel_wave: bool
    arrived_at: float


@dataclass
class Config:
    l1_enabled: bool
    l2_enabled: bool
    parallel_penalty: bool  # N parallel arrivals miss cache together
    l1_threshold: float
    l1_hit_prob: float
    ttl: str                # "5min" or "1hr"
```

- `prefix_hash` 代表"可缓存前缀的身份"：哈希相同即前缀逐字节相同。
- 两个字段**声明了却没被使用**：`Request.arrived_at`（因此 TTL 过期无从实现）和 `Config.l1_threshold`（L1 命中只看 `l1_hit_prob`）。它们像是为讲义概念预留的接口，读代码时要意识到它们不影响结果。
- `ttl: str` 用字符串表示枚举，判断时写 `cfg.ttl == "5min"`；更稳妥的写法是 `Literal["5min", "1hr"]` 或 `Enum`。

### 3.3 `make_workload()`：混合负载

```python
def make_workload(n: int = 500, seed: int = 7) -> list[Request]:
    rng = random.Random(seed)
    reqs = []
    prefixes = [f"prefix_{i}" for i in range(12)]
    now = 0.0
    for i in range(n):
        # 60% individual arrivals, 40% parallel waves of 5
        if rng.random() < 0.4:
            for _ in range(5):
                reqs.append(Request(rng.choice([2000, 4000, 8000]),
                                    rng.choice(prefixes), True, now))
            now += rng.uniform(0.1, 2.0)
        else:
            reqs.append(Request(rng.choice([2000, 4000, 8000]),
                                rng.choice(prefixes), False, now))
            now += rng.uniform(0.1, 2.0)
    return reqs
```

- 只有 12 种前缀，prompt 长度在 2,000 / 4,000 / 8,000 中随机。
- `n = 500` 是**循环次数**，不是请求数：期望请求数 `500 × (0.6 + 0.4 × 5) = 1,300`，实际生成 1,304 个（1,005 个属于 201 个并行波次）。`main()` 标题里的 "500 requests" 因此不准确。
- 同一波次的 5 个请求共享同一个 `now`（同时到达），但**每个请求各自随机选前缀**。实测 201 个波次中前缀完全相同的是 0 个。讲义的并行陷阱说的是"10 个工具调用共享同一个 4K 系统提示"，这里的建模与之不符。
- 时间每步前进 0.1–2.0 秒，整个负载只跨越约 519 秒；同一前缀两次出现的最大间隔约 57 秒，所以 5 分钟 TTL 在这个负载下永远不会过期。
- 两个分支末尾都有 `now += rng.uniform(0.1, 2.0)`，可以提到 `if/else` 之外，属于重复代码。

### 3.4 `simulate()`：L1 → L2 → 计费

```python
    for r in reqs:
        if cfg.l1_enabled and rng.random() < cfg.l1_hit_prob:
            l1_hits += 1
            continue
```

- **L1**：以固定概率命中，命中后 `continue`——不计输入费、不计输出费，相当于"完全跳过 LLM"。现实中还要付 embedding 与向量检索的成本，这里忽略了。
- 命中与否和请求内容无关，`l1_threshold` 也没参与；这是把"阈值 → 命中率"的关系直接抽象成一个概率参数。

```python
        if cfg.l2_enabled:
            if r.prefix_hash in l2_cache:
                l2_reads += 1
                cost += (r.prompt_tokens / 1e6) * CACHED_INPUT
            else:
                if cfg.parallel_penalty and r.is_parallel_wave:
                    write_cost = CACHE_WRITE_5MIN if cfg.ttl == "5min" else CACHE_WRITE_1HR
                    cost += (r.prompt_tokens / 1e6) * write_cost
                    l2_writes += 1
                else:
                    write_cost = CACHE_WRITE_5MIN if cfg.ttl == "5min" else CACHE_WRITE_1HR
                    cost += (r.prompt_tokens / 1e6) * write_cost
                    l2_cache.add(r.prefix_hash)
                    l2_writes += 1
        else:
            cost += (r.prompt_tokens / 1e6) * BASE_INPUT

        cost += (200 / 1e6) * BASE_OUTPUT
```

- **L2 命中**：整个 prompt 按缓存读价计费。代码把整个 prompt 都当作可缓存前缀，没有"动态后缀按新鲜价"的部分，因此无法表现讲义的动态内容陷阱。
- **L2 未命中**：按写入价计费。两个分支的唯一区别是并行惩罚分支**不把前缀加入缓存**——用"这次写入作废"来模拟"并行请求同时 miss"。问题在于：
  - 它让并行请求**永远**不能建立缓存，而现实中只有"第一个写入完成（约 300 ms）前"到达的请求才 miss；
  - 一旦某个前缀被单发请求写入，后续并行请求照常命中。12 个前缀很快都被写入，惩罚只体现在最初的 65 次额外写入（77 − 12）上。
- 两个分支里 `write_cost` 的计算完全重复，可以提到分支外面；`cost` 和 `l2_writes` 的更新也重复。
- **TTL 只影响写入价**：缓存是一个 `set`，没有过期逻辑。在这个模拟里选 1 小时 TTL 只会更贵，不会带来任何额外命中。
- 每个请求固定 200 个输出 token，$0.003/次，1,304 次共约 $3.91，是缓存后总成本的大头。
- 函数内部重新创建 `random.Random(11)`，保证每种配置的 L1 命中序列相同、结果可复现。

### 3.5 `report()` 与 `main()`

```python
    base = make_workload()
    reqs = [Request(r.prompt_tokens, r.prefix_hash, r.is_parallel_wave, r.arrived_at) for r in base]
```

- 用列表推导式把每个 `Request` 复制一份。由于 `simulate` 从不修改请求对象，这次复制其实没有必要（直接用 `base` 结果相同）；如果要复制，也可以用 `dataclasses.replace(r)` 或 `copy.copy(r)`。
- 5 次 `report` 调用依次是：不缓存；L2 + 并行惩罚；L2 + 修复并行；L2 1 小时 + L1 30%；L2 1 小时 + L1 70%。注意后两行**同时改了 TTL 和 L1**，省下的钱全部来自 L1，TTL 的改变反而让写入多花了钱。
- "NO CACHING" 的配置里 `parallel_penalty=True` 不起作用，因为 L2 没开。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| L1 命中用固定概率 | 免去 embedding 与相似度计算 | 无法研究阈值与错误命中；应基于真实 embedding 和标注集画"命中率—错误率"曲线 |
| 整个 prompt 视为前缀 | 计费简单 | 表现不了"静态前缀 + 动态后缀"；应拆成 `prefix_tokens` 与 `suffix_tokens` 分别计费 |
| 并行请求 miss 时不入缓存 | 一行代码表达"并行 miss" | 惩罚永久化又被单发请求抵消；应按"首个写入完成时间"建模，只有窗口内的请求 miss |
| 波次内各请求随机选前缀 | 复用单发请求的生成逻辑 | 与讲义"共享系统提示"的场景不符，惩罚被严重稀释；应让一个波次共享前缀 |
| 缓存用 `set`、无过期 | 代码短 | TTL 只影响价格，无法做讲义练习 3 的 TTL 盈亏平衡；应记录写入时间并按 TTL 过期 |
| 固定 200 输出 token | 简化 | 输出占比决定缓存节省的上限；应按分布抽样 |
| 固定种子 7 与 11 | 可复现、配置间可比 | 只代表一次抽样，严肃评估应多种子取均值 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 常量由表达式定义 | `CACHE_WRITE_5MIN = 1.25 * BASE_INPUT` | 模块加载时计算一次，表达倍数关系 |
| `@dataclass` | `class Request`、`class Config` | 自动生成构造函数；可按位置或关键字传参 |
| 关键字参数构造 | `Config(l1_enabled=False, l2_enabled=True, ...)` | 字段多时用关键字更不易出错 |
| 带类型的空集合 | `l2_cache: set[str] = set()` | 变量注解 + 空集合；`{}` 是空字典不是空集合 |
| 成员判断 | `if r.prefix_hash in l2_cache:` | 集合的 `in` 平均 O(1) |
| 列表推导式 | `[f"prefix_{i}" for i in range(12)]` | 一行生成列表 |
| `rng.choice` / `rng.uniform` | `rng.choice([2000, 4000, 8000])`、`rng.uniform(0.1, 2.0)` | 从序列随机选一个；在区间内均匀取浮点数 |
| 条件表达式 | `CACHE_WRITE_5MIN if cfg.ttl == "5min" else CACHE_WRITE_1HR` | 一行 if/else 选值 |
| `continue` | L1 命中后 `continue` | 跳过本次循环剩余部分 |
| 返回类型注解 | `-> list[Request]`、`-> dict` | 内置泛型写法（Python 3.9+；配合 `from __future__ import annotations` 更早也可） |
| f-string 宽度 | `{label:45}`、`{res['cost']:7.2f}`、`{res['l1_hits']:4}` | 左对齐宽度 45；宽度 7 两位小数；宽度 4 |
| 转义换行 | `print("\nRead: ...")` | `\n` 先输出一个空行 |

---

## 6. 运行结果解读

实际运行（Python 3.13）：

```text
PROMPT + SEMANTIC CACHING — 500 requests, Claude Sonnet-class pricing
NO CACHING                                     cost=$  21.63  L1=   0  L2_reads=   0  L2_writes=   0
L2 5-min, parallel penalty active              cost=$   6.84  L1=   0  L2_reads=1227  L2_writes=  77
L2 5-min, parallel fixed (serialize first)     cost=$   5.85  L1=   0  L2_reads=1292  L2_writes=  12
L2 1-hour + L1 semantic 30%                    cost=$   4.25  L1= 391  L2_reads= 901  L2_writes=  12
L2 1-hour + L1 semantic 70% (structured FAQ)   cost=$   2.02  L1= 909  L2_reads= 383  L2_writes=  12
```

逐项解读（补充数据由同一负载另行计算得到）：

- **请求总数**：1,304（标题写的 500 是循环次数），prompt 总量约 5.9M token。
- **NO CACHING $21.63** = 输入 `5.906M × $3 = $17.72` + 输出 `1,304 × 200 × $15/M = $3.91`。
- **L2 + 并行惩罚 $6.84**：77 次写入（12 个前缀 + 65 次并行波次的无效写入）、1,227 次读取。即便有惩罚也比不缓存便宜 68%，因为只有 12 个前缀、复用率极高。
- **修复并行 $5.85**：只写 12 次。与上一行相比，总成本相差约 1.17 倍，只看输入侧是 `2.93 / 1.94 ≈ 1.51` 倍。远小于讲义的 5–10 倍，原因见 3.3、3.4：波次内前缀不共享、缓存会被单发请求填好。若按讲义场景（10 个请求共享 4K 前缀）单独计算，输入侧确实是约 5.8 倍（见测验 Q10）。
- **L2 1 小时 + L1 30%：$4.25**；**L1 70%：$2.02**。L1 命中数 391 / 909 与 30% / 70% 吻合。下降全部来自 L1——每次 L1 命中省掉了整次输入和输出。单独把 TTL 改成 1 小时而不开 L1，成本是 $5.96，比 5 分钟的 $5.85 还高。
- **结论句** "caching is a protocol" 的方向正确，但这份模拟器中最大的收益来自"前缀少、复用高"与 L1 的高命中率假设；在动态内容多、前缀分散的真实负载下，结果会差很多。

---

## 7. 动手改一改

1. **讲义练习 1**：在 `main()` 里对比 `parallel_penalty=True/False` 的两行（已有），再把 `make_workload` 改成"波次内共享同一个前缀"（在 `for _ in range(5)` 之前先选好 `p = rng.choice(prefixes)`），重新比较惩罚倍数。
2. **实现写入延迟窗口**：给缓存记录 `ready_at = arrived_at + 0.3`，只有 `r.arrived_at >= ready_at` 的请求才能读取；删除"并行请求不入缓存"的特殊分支，看结果是否更接近讲义的 5–10 倍。
3. **实现 TTL 过期**：把 `l2_cache` 改成 `dict[str, float]`（前缀 → 过期时间），命中时按讲义的 TTL 规则续期；把请求间隔拉长到分钟级，完成讲义练习 3 的 TTL 盈亏平衡实验。
4. **拆分前缀与后缀**：给 `Request` 增加 `suffix_tokens`，前缀按缓存规则计费、后缀始终按新鲜价，然后模拟"时间戳在前缀里"（每个请求一个独立前缀）与"时间戳移到后缀"两种模板（讲义练习 2）。
5. **让 L1 依赖阈值**：为每个请求生成一个"与最近缓存条目的相似度"，`sim >= l1_threshold` 时命中，并以一定概率标记"错误命中"，统计 0.95 与 0.85 两个阈值下的命中率与错误率（讲义练习 4）。
6. **进阶**：把 L1 的 embedding 查询成本（如每次 $0.00002）与向量库月费加入成本，找出 L1 命中率多低时不值得部署。

---

## 8. 常见坑

- **前缀里有动态内容**：时间、请求 ID、随机示例顺序都会让前缀每次不同，开缓存后只付写入溢价，比不开还贵。
- **并行扇出不预热**：同一前缀的并行请求在首个写入完成前全部 miss；先串行一个或提前预热。
- **把"95% 准确率"当命中率**：它是匹配正确率；真实命中率从 10% 到 70% 不等。
- **把 TTL 当成命中率开关**：TTL 只决定缓存能活多久；请求间隔都很短时，1 小时 TTL 只是多付写入费。
- **语义缓存键不含租户 / 版本**：可能把 A 用户的答案返回给 B，或在模型 / 提示词升级后返回旧答案。
- **读代码时被未使用的字段误导**：`arrived_at` 与 `l1_threshold` 在本模拟里不影响任何结果。
- **只看总账单比较配置**：最后两行同时改了 TTL 和 L1，要做单变量对比才能知道每个改动的真实影响。
