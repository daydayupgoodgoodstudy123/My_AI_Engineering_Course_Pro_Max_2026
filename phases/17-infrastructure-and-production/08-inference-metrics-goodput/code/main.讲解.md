# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 08 节 Inference 指标：TTFT、TPOT、ITL、Goodput、P99 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`statistics`、`dataclasses`）；无需 GPU、无需网络

---

## 1. 这份代码在考察什么

这是一个"玩具 goodput 计算器"：不连接任何真实模型，而是**合成** 2000 个请求的延迟轨迹，然后：

1. **定义指标**：每个请求的 TTFT、E2E，以及两种口径的 TPOT（GenAI-Perf 排除 TTFT、LLMPerf 包含 TTFT）。
2. **用分位数而不是均值**：对 TTFT / TPOT / E2E 报告 P50、P90、P99。
3. **算 goodput**：在三档 SLO（loose / target / tight）下，统计同时满足 TTFT、TPOT、E2E 三个约束的请求占比，并贴上 SHIPPABLE / DEGRADED / FAILING 标签。
4. **展示测量陷阱**：同一批轨迹，两种 TPOT 口径的均值相差约 1 ms。

它对应讲义的"指标定义""均值是错误统计量""goodput 多约束""工具陷阱"四部分。

> 一句话：**用一个可复现的合成负载，把"吞吐好看不等于用户满意"变成可以逐项验证的数字**——同时，这份代码自己也恰好演示了几个"测量口径陷阱"（见第 3.2、3.5 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `RequestTrace` | `@dataclass` | 一个请求的排队、prefill、逐 token decode 延迟和输出长度 | 请求轨迹 |
| `.ttft_ms` / `.e2e_ms` | `@property` | TTFT = 排队 + prefill；E2E = TTFT + 全部 decode | TTFT、E2E |
| `.tpot_llmperf()` / `.tpot_genaiperf()` | 方法 | 两种工具口径的 TPOT | 测量陷阱 |
| `synth_workload` | 函数 | 生成 n 个右偏分布的请求（指数排队、随 prompt 长度变化的 prefill、带尖刺的 decode） | 合成负载 |
| `percentiles` | 函数 | 排序后取最近秩分位数 | P50/P90/P99 |
| `report_latency` | 函数 | 打印三个指标的分位数和两种 TPOT 的均值差 | 分位数报告 |
| `goodput` | 函数 | 三约束同时满足的请求占比 | goodput |
| `main` | 函数 | 生成负载 → 报告 → 三档 SLO 的 goodput → KEY FINDING | — |

数据流：`synth_workload(n=2000)` → `list[RequestTrace]` → `report_latency`（分位数）与 `goodput`（三档 SLO）→ 打印。

---

## 3. 逐段精讲

### 3.1 `RequestTrace`：一个请求的"时间账"

```python
@dataclass
class RequestTrace:
    queue_ms: float
    prefill_ms: float
    decode_ms_per_token: list[float]      # per-token decode latency
    output_tokens: int

    @property
    def ttft_ms(self) -> float:
        return self.queue_ms + self.prefill_ms

    @property
    def e2e_ms(self) -> float:
        return self.ttft_ms + sum(self.decode_ms_per_token)
```

- `ttft_ms = 排队 + prefill`。讲义公式还有 `network_request`，代码省略了网络项（相当于在服务端测量）。
- `e2e_ms = TTFT + 所有 decode 间隔之和`，同样省略了 `network_response`。
- `@property` 让这两个量可以像属性一样访问（`t.ttft_ms`），但每次都即时计算，不会和原始字段不同步。
- 逐 token 存储 `decode_ms_per_token`（列表），而不是只存一个平均值——这样才可能计算"逐 token 的尾延迟"。不过后面的 `report_latency` 并没有利用这一点（见 3.5）。

### 3.2 两种 TPOT 口径（以及一个分母错位）

```python
    def tpot_llmperf(self) -> float:
        """LLMPerf: include TTFT in ITL calculation."""
        return self.e2e_ms / self.output_tokens

    def tpot_genaiperf(self) -> float:
        """GenAI-Perf: ITL starts from token 2."""
        if self.output_tokens <= 1:
            return 0.0
        return sum(self.decode_ms_per_token) / (self.output_tokens - 1)
```

- **LLMPerf 口径**：总时间（含 TTFT）÷ 输出 token 数。TTFT 越大、输出越短，这个数被"污染"得越严重。
- **GenAI-Perf 口径**：只用首 token 之后的间隔，分母是 `n − 1` 个间隔。对应讲义例子 `700 / 99 = 7.07 ms` vs `1200 / 100 = 12.00 ms`。
- ⚠️ **分母与样本数不一致**：`synth_workload` 为每个请求生成了 `output_tokens` 个 decode 样本（见 3.3），但首 token 到达后只应有 `n − 1` 个间隔。于是 `tpot_genaiperf` 用 n 个样本之和除以 n − 1，系统性偏高 `n/(n−1)` 倍（n = 50 时约 2%）。本次运行所有间隔的真实均值约 7.63 ms，报告的 GenAI-Perf 均值是 7.69 ms，差值就来自这里。`e2e_ms` 也因此多算了一个间隔。修正方法见测验 Q9。
- ⚠️ `output_tokens <= 1` 时返回 `0.0`：单 token 输出没有间隔，TPOT 无定义；返回 0 会让它自动通过 TPOT 约束。本代码 `randint(50, 300)` 不会触发，但在真实数据里（分类、工具调用的短输出）会高估 goodput。

### 3.3 `synth_workload`：构造右偏的延迟分布

```python
def synth_workload(n: int = 1000, seed: int = 7, tail_spike_rate: float = 0.02) -> list[RequestTrace]:
    rng = random.Random(seed)
    traces = []
    for _ in range(n):
        prompt_len = rng.choice([128, 256, 512, 2048, 8192])
        output_tokens = rng.randint(50, 300)
        queue = rng.expovariate(1 / 40.0)           # avg 40 ms queue
        prefill = prompt_len * 0.05                 # ~50 us per input token
        decode_base = 7.0                            # 7 ms mean TPOT
        decodes = []
        for _ in range(output_tokens):
            t = max(1.5, rng.gauss(decode_base, decode_base * 0.15))
            if rng.random() < tail_spike_rate:
                t *= rng.uniform(3, 8)              # tail spike
            decodes.append(t)
        traces.append(RequestTrace(queue, prefill, decodes, output_tokens))
    return traces
```

每个随机成分都对应讲义里的一种延迟来源：

| 成分 | 分布 | 数值 | 对应讲义 |
|------|------|------|---------|
| prompt 长度 | 5 选 1 均匀 | 128 … 8192 | prefill 随 prompt 长度增长 |
| prefill | `prompt_len × 0.05 ms` | 6.4 / 12.8 / 25.6 / 102.4 / 409.6 ms | "Prefill dominates when prompts are long" |
| 排队 | 指数分布，均值 40 ms | 长尾 | "Queue time is scheduler behavior under load" |
| decode 间隔 | 正态 N(7, 1.05²)，下限 1.5 ms | 均值约 7 ms | 讲义 TPOT 参考值 7.33 ms |
| 尾部尖刺 | 2% 概率乘 3–8 倍 | 21–56 ms | "TPOT can spike to 50 ms" |
| 输出长度 | `randint(50, 300)` | — | E2E 与输出长度相关 |

- `random.Random(seed)` 创建**独立的**随机数生成器，固定种子 7，每次运行结果完全相同，且不影响全局 `random` 状态。
- `expovariate(1/40)` 的参数是速率 λ，均值 = 1/λ = 40 ms。
- 尖刺的期望增量：`0.02 × (平均 5.5 − 1) × 7 ≈ 0.63 ms`，所以逐 token 均值约 7.63 ms，而不是 7。
- ⚠️ 尖刺是**独立随机**发生的，而真实系统中尖刺往往是相关的（同一时刻插进来的长 prefill 会让同一 batch 的所有序列一起变慢）。独立尖刺被平均掉得更快，这也是请求级 P99 TPOT 很低的原因之一。
- 讲义练习 1 说"1% tail spike"，而默认值是 0.02（2%），做练习时需要显式传 `tail_spike_rate=0.01`。

### 3.4 `percentiles`：最近秩分位数

```python
def percentiles(values: list[float], ps: list[float]) -> list[float]:
    s = sorted(values)
    return [s[min(len(s) - 1, int(p * len(s)))] for p in ps]
```

- 排序后取下标 `int(p × n)`，`min(..., n − 1)` 防止 `p = 1.0` 时越界。n = 2000、p = 0.99 时取第 1980 个元素（0 起计）。
- 这是不插值的"最近秩"法；与 `statistics.quantiles(x, n=100)[98]` 的插值结果在本数据上几乎一样（TTFT P99 都约 524.4 ms）。
- 样本少时（如 100 个请求）P99 只由 1 个样本决定，非常不稳定——这就是 skill 文件要求"≥ 30 次运行、每次 ≥ 100 请求"的原因。

### 3.5 `report_latency`：分位数报告（以及第二个口径陷阱）

```python
    ttft = [t.ttft_ms for t in traces]
    tpot_llm = [t.tpot_llmperf() for t in traces]
    tpot_nv = [t.tpot_genaiperf() for t in traces]
    e2e = [t.e2e_ms for t in traces]

    p50_ttft, p90_ttft, p99_ttft = percentiles(ttft, [0.5, 0.9, 0.99])
    p50_tpot, p90_tpot, p99_tpot = percentiles(tpot_nv, [0.5, 0.9, 0.99])
```

- 用列表推导式把每个指标取成一列，再对每列取分位数。TPOT 分位数用的是 GenAI-Perf 口径。
- ⚠️ **这里的 P99 TPOT 是"每请求平均 TPOT"的 P99**：先把一个请求的 50–300 个间隔求平均，再在 2000 个请求之间取 P99。2% 的独立尖刺被平均掉，结果只有 8.99 ms。若把 35 万多个 token 间隔摊平直接取分位数，P99 约 **37.5 ms**——这才是 KEY FINDING 里"P99 TPOT ~25–40 ms"所描述的量，但代码并没有打印它。讲义中"均值 9 ms、P99 65 ms"的例子也是逐 token 口径。
- "Tool trap" 一行打印两种口径的均值及差值（`{...:+5.2f}` 强制显示正负号）。

### 3.6 `goodput`：多约束 AND

```python
def goodput(traces: list[RequestTrace], slo_ttft: float, slo_tpot: float,
            slo_e2e: float) -> float:
    good = 0
    for t in traces:
        if t.ttft_ms <= slo_ttft and t.tpot_genaiperf() <= slo_tpot and t.e2e_ms <= slo_e2e:
            good += 1
    return good / len(traces)
```

- 三个条件用 `and` 连接：任一违约，该请求就不是 good。这正是讲义的"SLO multi-constraint"。
- 注意 SLO 在讲义中是"P99 ≤ 阈值"的形式（对分布的约束），而这里是"每个请求 ≤ 阈值"（对个体的约束），goodput 是满足个体约束的比例。两者相关：goodput ≥ 99% 大致等价于"各指标的 P99 都在阈值内"，但多约束联合时要更严格。
- ⚠️ TPOT 约束作用在请求平均值上，因此几乎从不生效（见第 6 节的逐约束统计）。
- ⚠️ E2E 约束对所有输出长度一刀切。讲义写的是"E2E P99 ≤ 3 s for <300-token outputs"，并建议"Report output-length-conditioned E2E"。

### 3.7 `main`：三档 SLO 与标签

```python
    slos = [
        ("loose   TTFT<800 TPOT<25 E2E<3000", 800, 25, 3000),
        ("target  TTFT<500 TPOT<15 E2E<2000", 500, 15, 2000),
        ("tight   TTFT<300 TPOT<10 E2E<1500", 300, 10, 1500),
    ]
    for label, t1, t2, t3 in slos:
        g = goodput(traces, t1, t2, t3)
        tag = "  SHIPPABLE" if g >= 0.99 else ("  DEGRADED" if g >= 0.95 else "  FAILING")
```

- loose 档就是讲义给出的 70B 消费级聊天 SLO（800 / 25 / 3000）；SHIPPABLE ≥ 99% 对应讲义"goodput target ≥ 99%"，DEGRADED ≥ 95% 对应 skill 文件里的 canary 门槛。
- 嵌套条件表达式实现三段标签。
- KEY FINDING 是硬编码文字，与实际输出对照见第 6 节。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 合成负载而不是真实压测 | 无需 GPU，可复现，能控制每个延迟来源 | 尖刺独立、排队与负载无关；生产中用 LLMPerf / GenAI-Perf 对真实引擎做并发扫描 |
| 逐 token 存 decode 间隔 | 保留计算逐 token 尾延迟的可能 | 内存随 token 数增长；生产中通常存直方图（如 Prometheus histogram）|
| TPOT 取每请求平均 | 与常见工具的"per-request TPOT"一致 | 尖刺被平均掉，P99 TPOT 显得很健康；应同时报告 token 级 ITL 分位数 |
| 同时实现两种口径 | 演示工具陷阱 | GenAI-Perf 口径的分母与样本数不一致，产生小偏差 |
| 最近秩分位数 | 简单直观 | 样本少时不稳定；生产中用足够样本或插值/HDR 直方图 |
| E2E 统一上限 | 实现简单 | 长输出天然违约，goodput 低主要来自输出长度而非系统问题；应按输出长度分桶 |
| 不建模网络 | 聚焦服务端 | 用户感知的 TTFT 还包括 TLS 握手与跨区域 RTT（见第 11 节） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 延迟求值注解，允许 `list[float]` 等写法 |
| `@dataclass` | `class RequestTrace` | 自动生成 `__init__`，`RequestTrace(queue, prefill, decodes, output_tokens)` 按字段顺序构造 |
| `@property` | `def ttft_ms(self)` | 把方法变成只读属性，调用时不加括号：`t.ttft_ms` |
| 普通方法 vs 属性 | `t.tpot_genaiperf()` vs `t.e2e_ms` | 前者要加括号调用；风格上"可能有参数或较重的计算"用方法 |
| 类型注解 | `decode_ms_per_token: list[float]`、`-> list[RequestTrace]` | 文档作用，运行时不检查 |
| 独立随机数生成器 | `rng = random.Random(seed)` | 固定种子可复现，且不污染全局 `random` |
| 常用分布 | `rng.choice`、`rng.randint(50, 300)`、`rng.expovariate`、`rng.gauss`、`rng.uniform`、`rng.random()` | 离散选择、闭区间整数、指数、正态、均匀、[0,1) 均匀 |
| 列表推导式 | `[t.ttft_ms for t in traces]`、`[s[...] for p in ps]` | 一行生成列表 |
| 多重赋值解包 | `p50_ttft, p90_ttft, p99_ttft = percentiles(...)` | 返回列表按位置拆成三个变量 |
| `statistics.mean` | `statistics.mean(ttft)` | 标准库求均值 |
| 内置 `sorted` / `sum` / `min` | `sorted(values)`、`sum(self.decode_ms_per_token)` | 返回新列表 / 求和 / 取小 |
| 链式比较与 `and` | `t.ttft_ms <= slo_ttft and ...` | 短路求值：前一个为假就不再计算后面的 |
| 嵌套条件表达式 | `"SHIPPABLE" if g >= 0.99 else ("DEGRADED" if g >= 0.95 else "FAILING")` | 三段式分类 |
| f-string 格式符 | `{p50_ttft:7.1f}`、`{g:6.2%}`、`{delta:+5.2f}` | 宽度与小数位；`%` 乘 100 加百分号；`+` 总显示符号 |
| 元组列表遍历 | `for label, t1, t2, t3 in slos:` | 循环中直接解包 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不执行 `main()`，便于在测试或练习中复用函数 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，固定种子，结果确定）：

```text
Synthetic workload (2000 requests)
----------------------------------------------------------------------------
  TTFT (ms)     P50=   84.6  P90=  439.4  P99=  524.4  mean=  151.3
  TPOT (ms)     P50=   7.65  P90=   8.21  P99=   8.99  mean=   7.69
  E2E  (ms)     P50= 1526.4  P90= 2261.4  P99= 2664.5
  Tool trap     GenAI-Perf mean TPOT=  7.69  LLMPerf mean TPOT=  8.71  delta=+1.02 ms

Goodput under three SLO profiles
----------------------------------------------------------------------------
  loose   TTFT<800 TPOT<25 E2E<3000  goodput=100.00%  SHIPPABLE
  target  TTFT<500 TPOT<15 E2E<2000  goodput=75.95%  FAILING
  tight   TTFT<300 TPOT<10 E2E<1500  goodput=42.15%  FAILING
```

逐项解读：

- **TTFT**：P50 84.6 ms，P90 跳到 439.4 ms——因为 1/5 的请求 prompt 为 8192 token，prefill 就要 409.6 ms。均值 151.3 ms 夹在中间，既不代表"典型用户"，也不代表"最差用户"，正好说明为什么不能只报均值。
- **TPOT**：P50 7.65、P99 8.99，分布很窄——这是请求级平均的结果。实际计算逐 token 间隔的分位数：P50 7.03、P90 8.47、**P99 37.5**、P99.9 59.0 ms。
- **E2E**：P50 1.5 s、P99 2.7 s，主要由输出长度（50–300 token × ~7.6 ms）决定。
- **Tool trap**：LLMPerf 口径比 GenAI-Perf 多 1.02 ms，因为它把平均 151 ms 的 TTFT 摊到了平均约 175 个 token 上。
- **goodput 逐约束拆解**（实际统计，2000 个请求中各约束的违约数）：

| SLO | TTFT 违约 | TPOT 违约 | E2E 违约 | goodput |
|-----|----------|----------|---------|---------|
| loose | 0 | 0 | 0 | 100.00% |
| target | 46 | **0** | **455** | 75.95% |
| tight | 407 | 3 | 1024 | 42.15% |

  goodput 下降几乎完全来自 E2E 和 TTFT，TPOT 约束基本没起作用。

与 KEY FINDING 对照：

- "Mean TPOT ~7 ms looks great. P99 TPOT ~25–40 ms tells the real story."——代码打印的 P99 TPOT 是 8.99 ms，"25–40 ms" 只有在逐 token 口径下才成立（37.5 ms）。
- "Tighten the SLO and goodput collapses from 99% -> 80%+"——实际是 100% → 75.95% → 42.15%；而且"崩塌"的原因是 E2E 一刀切，而不是尾延迟。
- "GenAI-Perf vs LLMPerf disagree by ~1 ms on mean TPOT"——与输出一致（+1.02 ms）。

---

## 7. 动手改一改

1. **（入门）** 在 `report_latency` 里增加一行"token 级 ITL"分位数：`itl = [x for t in traces for x in t.decode_ms_per_token]`，对比它与请求级 TPOT 的 P99。
2. **（入门）** 讲义练习 1：用 `synth_workload(n=2000, tail_spike_rate=0.01)`，打印 TPOT 上限 30 / 15 / 10 / 8 ms 时的 goodput，并在 `goodput` 里加计数器输出"哪个约束违约最多"。
3. **（进阶）** 修复分母错位：让 `synth_workload` 生成 `output_tokens - 1` 个间隔，重新运行看 GenAI-Perf 均值是否变为约 7.63 ms。
4. **（进阶）** 按输出长度分桶的 E2E SLO：例如 `<150 token: 1.5 s`、`150–300 token: 3 s`，或用 `E2E ≤ TTFT_budget + n × TPOT_budget`，看 target 档 goodput 变成多少。
5. **（进阶）** 模拟"相关尖刺"：每个请求以一定概率被一个长 prefill 邻居影响，**连续** 20 个 token 都乘以 5 倍；比较请求级 P99 TPOT 与独立尖刺时的差异，体会 chunked prefill 要解决的问题。
6. **（挑战）** 实现 skill 文件的 CI 闸门：模拟 25% / 50% / 100% / 150% 并发（例如让排队均值和尖刺率随并发增长），在每个并发点算 goodput，按"目标并发 ≥ 99% 通过、150% 比 100% 降 > 5 个百分点告警"输出结论（参考测验 Q12）。

---

## 8. 常见坑

- **只报均值**：TTFT 均值 151 ms 掩盖了 P90 的 439 ms；讲义要求永远报 P50 / P90 / P99。
- **把"请求级平均 TPOT 的 P99"当成用户感受到的卡顿**：本代码中前者 9 ms、后者 37.5 ms，差 4 倍。SLO 文档里要写清楚是哪一个。
- **不声明工具口径**：GenAI-Perf 与 LLMPerf 对同一请求的 TPOT 可以差很多，短输出时尤其严重（见测验 Q11）。
- **TPOT 分母写错**：n 个 token 只有 n − 1 个间隔；样本数与分母不一致会产生系统偏差。
- **E2E 一刀切**：长输出必然超时，导致 goodput 低得"冤枉"，掩盖了真正的系统问题；应按输出长度分桶。
- **单 token 输出的 TPOT 当成 0**：让这类请求自动通过 TPOT 约束，高估 goodput。
- **样本太少就报 P99**：100 个样本的 P99 只取决于 1 个值；至少要几千个样本。
- **只在目标并发下测**：skill 文件要求做 25%–150% 的并发扫描，否则看不到 goodput 在超载时的悬崖。
