# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 19 节 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`random`）。同目录另有 TypeScript 版 `main.ts`（Node 20+，含鉴权、token bucket、重试与 fallback 骨架），本讲解只覆盖 Python 版。

---

## 1. 这份代码在考察什么

代码模拟一个网关把请求依次发给三家提供商（OpenAI → Anthropic → 自托管），每家按固定概率注入错误；失败就切到下一家（fallback）。对四种网关（LiteLLM、Portkey、Kong、Cloudflare）各跑 1000 个请求，统计成功率、平均时延、失败次数与 fallback 次数。

对应讲义的三个概念：

1. **fallback 链**：失败率相乘带来的高可用（Notes 里的 97% → 99.94% → 99.997%）。
2. **网关开销**：不同网关给每个请求加上不同的固定时延（讲义的 Latency budget 一节）。
3. **fallback 的时延代价**：失败的那次调用也会耗时，fallback 请求的时延更高。

> 一句话：**用"按概率失败、失败就换下一家"的循环演示 fallback 的可用性算术和网关开销**。但它没有实现真正的重试，四个网关的差别也只是一个常数，看不出讲义里各网关在规模、guardrails 上的区别。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Provider` | `@dataclass` | 名称、基础时延、错误率、`overhead_ms`（未使用） | 提供商 |
| `PROVIDERS` | 列表常数 | OpenAI 180 ms / 3%，Anthropic 220 ms / 2%，自托管 100 ms / 5% | fallback 顺序 |
| `GATEWAY_OVERHEAD` | 字典常数 | LiteLLM 10、Portkey 30、Kong 5、Cloudflare 2（毫秒） | 讲义时延预算的中间值 |
| `call_provider(p, rng)` | 函数 | 按错误率决定成败；失败返回 30% 的基础时延 | 错误注入 |
| `simulate_fallback(gateway, n, seed)` | 函数 | n 个请求，每个依次尝试三家直到成功，累计统计 | fallback 链 |
| `report(row)` | 函数 | 打印一行结果 | 输出 |
| `main()` | 函数 | 打印表头，对四个网关调用模拟，打印可用性算术 | 入口 |

数据流：`main()` → 对每个网关 `simulate_fallback(gw)`（种子都是 7）→ 每个请求遍历 `PROVIDERS` 调 `call_provider` → 汇总成 `dict` → `report()` 打印。

---

## 3. 逐段精讲

### 3.1 提供商与网关开销

```python
@dataclass
class Provider:
    name: str
    base_latency_ms: float
    error_rate: float
    overhead_ms: float


PROVIDERS = [
    Provider("OpenAI",       180, 0.03, 0),
    Provider("Anthropic",    220, 0.02, 0),
    Provider("Self-hosted",  100, 0.05, 0),
]

GATEWAY_OVERHEAD = {
    "LiteLLM": 10,
    "Portkey": 30,
    "Kong":      5,
    "Cloudflare": 2,
}
```

- `PROVIDERS` 的顺序就是 fallback 顺序，对应讲义练习 1 的 "OpenAI→Anthropic→self-hosted"。
- 自托管最快（100 ms）却最不稳定（5%），被放在最后——这是一个"把最不可靠的放末位"的取舍，也可以讨论按时延或成本重排。
- `GATEWAY_OVERHEAD` 取的是讲义区间的中间值：LiteLLM 5–15 → 10，Portkey 20–40 → 30，Kong 3–8 → 5，Cloudflare 1–3 → 2。
- ⚠️ `overhead_ms` 字段四处都是 0，且从未被读取，是死代码；文件头的 `from dataclasses import dataclass, field` 里的 `field` 也没有用到。

### 3.2 错误注入

```python
def call_provider(p: Provider, rng: random.Random) -> tuple[bool, float]:
    if rng.random() < p.error_rate:
        return False, p.base_latency_ms * 0.3  # half-done before error
    return True, p.base_latency_ms
```

- `rng.random()` 返回 `[0, 1)` 的均匀随机数，小于错误率就判失败——这是最常见的伯努利（Bernoulli）注入方式。
- 失败也要耗时：OpenAI 失败耗 54 ms、Anthropic 66 ms、自托管 30 ms。这反映了现实中"等到 429/5xx 或超时才知道失败"的代价。
- ⚠️ 注释说 "half-done"（一半），实际乘数是 0.3。
- 返回类型 `tuple[bool, float]`，调用方用 `ok, ms = ...` 解包。
- 每次调用独立失败——**没有相关性**：现实中提供商宕机往往持续一段时间，或者 429 成片出现，独立假设会高估 fallback 的效果。

### 3.3 fallback 主循环

```python
    for _ in range(n):
        req_latency = gw_ovh
        done = False
        for attempt, p in enumerate(PROVIDERS):
            ok, ms = call_provider(p, rng)
            req_latency += ms
            if attempt > 0:
                fallback_hits += 1
            if ok:
                success += 1
                done = True
                break
            retries += 1
        total_latency += req_latency
```

- 每个请求起点是网关开销 `gw_ovh`，然后依次尝试提供商，时延不断累加。
- `enumerate` 给出下标 `attempt`：`attempt > 0` 表示正在尝试第二家或第三家，计为一次 fallback。
- 成功就 `break` 跳出内层循环；失败就 `retries += 1` 并继续下一家。
- ⚠️ **没有对同一提供商的重试**：讲义第 3 项功能 "Retries — exponential backoff, bounded attempts" 没有实现。`retries` 实际上是"失败调用次数"，除非最后一家也失败，否则它与 `fallback_hits` 完全相等。
- ⚠️ `done` 被赋值但从未使用（可以删掉，或用 Python 的 `for ... else` 表达"全部失败"）。
- 如果三家都失败，循环自然结束，`success` 不增加，`req_latency` 仍然计入平均值。

### 3.4 统计与种子

```python
def simulate_fallback(gateway: str, n: int = 1000, seed: int = 7) -> dict:
    rng = random.Random(seed)
    ...
    return {
        "gateway": gateway,
        "success_rate": success / n,
        "mean_latency": total_latency / n,
        "retries": retries,
        "fallback_hits": fallback_hits,
    }
```

- 每次调用都新建 `random.Random(7)`。`main()` 对四个网关都用默认种子，于是四次模拟的随机序列**完全相同**：同样的请求在同样的位置失败。网关之间唯一的差别就是 `gw_ovh` 这个常数。
- 这是一种"共同随机数"（common random numbers）的对照设计，好处是差异只来自被比较的因素；坏处是这里被比较的因素只有一个常数，结果没有信息量。
- 只返回平均时延，没有 P99；讲义的 SLA 都以 TTFT P99 表述。

### 3.5 输出

```python
def main() -> None:
    ...
    header = f"{'Gateway':12}  {'Success':>7}         {'mean latency':>12}  retries  fallbacks"
    ...
    print("\nNotes: a single-provider target at 3% error rate → 97% success.")
    print("Two-provider fallback → 99.94% success (complement of 0.03 × 0.02).")
    print("Three-provider fallback → 99.997% success. Latency rises on fallback.")
```

- Notes 的三条可用性算术都正确：`1 − 0.03 = 97%`，`1 − 0.03 × 0.02 = 99.94%`，`1 − 0.03 × 0.02 × 0.05 = 99.997%`。它们是写死的文字，不是由模拟结果计算出来的。
- ⚠️ 表头与数据行的格式不一致：数据行自带 `success=`、`mean_latency=` 标签，表头列名对不齐（见第 6 节输出）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 伯努利错误注入、相互独立 | 可用性算术最清晰 | 忽略相关故障（区域性宕机、429 风暴）；生产要用断路器和健康检查，并做故障注入演练 |
| 失败即 fallback，无重试 | 代码短 | 与讲义"重试 + 退避"不符；生产按错误类型决定重试还是 fallback，且有总时延预算 |
| 网关差异 = 一个固定开销常数 | 对应讲义的时延预算 | 无法体现 RPS 上限、内存、级联失败、guardrails、限流等真正的选型因素 |
| 四个网关共用种子 7 | 公平对照 | 结果只差常数，success / retries / fallbacks 完全一样 |
| 只输出均值 | 简单 | 看不到 fallback 带来的尾部时延；应输出 P50/P95/P99 |
| n = 1000 | 运行快 | 不足以观察 99.997% 这类可用性（期望失败 0.03 次）；要 10^5 量级以上 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class Provider:` | 自动生成构造函数；`Provider("OpenAI", 180, 0.03, 0)` 按字段顺序传参 |
| 未使用的导入 | `from dataclasses import dataclass, field` | `field` 没用到，linter（如 ruff/flake8）会报 F401 |
| 列表 / 字典字面量常数 | `PROVIDERS = [...]`、`GATEWAY_OVERHEAD = {...}` | 模块级配置；字典按键取值 `GATEWAY_OVERHEAD[gateway]` |
| 返回元组的类型注解 | `-> tuple[bool, float]` | Python 3.9+ 写法；调用方 `ok, ms = call_provider(...)` 解包 |
| 独立随机数生成器 | `rng = random.Random(seed)`、`rng.random()` | 固定种子可复现，且互不干扰 |
| `enumerate` | `for attempt, p in enumerate(PROVIDERS):` | 同时拿到下标和元素 |
| `break` | 成功后跳出内层循环 | 只跳出最近一层循环 |
| `for ... else`（可改进点） | 本文件未使用 | `for` 循环没有被 `break` 时执行 `else`，可以用来表达"所有提供商都失败"，替代无用的 `done` 变量 |
| `_` 作为占位变量 | `for _ in range(n):` | 不需要循环变量时的惯例 |
| f-string 格式符 | `{row['success_rate']*100:5.1f}`、`{row['retries']:4}`、`{'Gateway':12}` | 表达式可以直接写在花括号里；`5.1f` 宽 5、1 位小数 |
| 默认参数 | `def simulate_fallback(gateway, n=1000, seed=7)` | 不传就用默认值——也正是四个网关种子相同的原因 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，不到 0.1 秒，结果可复现）：

```text
================================================================================
AI GATEWAY FALLBACK — 3-provider chain under error injection
================================================================================
Gateway       Success         mean latency  retries  fallbacks
--------------------------------------------------------------
LiteLLM       success=100.0%  mean_latency=   193ms  retries=  34  fallbacks=  34
Portkey       success=100.0%  mean_latency=   213ms  retries=  34  fallbacks=  34
Kong          success=100.0%  mean_latency=   188ms  retries=  34  fallbacks=  34
Cloudflare    success=100.0%  mean_latency=   185ms  retries=  34  fallbacks=  34

Notes: a single-provider target at 3% error rate → 97% success.
Two-provider fallback → 99.94% success (complement of 0.03 × 0.02).
Three-provider fallback → 99.997% success. Latency rises on fallback.
```

逐项解读：

- **请求路径分布**（我们用同一种子逐个统计）：967 个请求第一家成功；32 个第一家失败、第二家成功；1 个前两家都失败、第三家成功。
- **retries = fallbacks = 34**：`32 × 1 + 1 × 2 = 34`。两列相等正说明代码没有真正的"重试"。
- **success = 100.0%**：三级链理论成功率 99.997%，1000 次的期望失败数只有 0.03，看不到失败很正常。我们把 `n` 改成 100,000 重跑 Kong：success = 99.998%，retries = 3082，fallbacks = 3080（两者差 2，正是两个三家全失败的请求），mean_latency ≈ 187.8 ms。
- **mean_latency**：去掉开销后都是约 183 ms，与理论期望 182.79 ms 吻合（见测验 Q9）。四行的差值就是 `GATEWAY_OVERHEAD`：Portkey 比 Cloudflare 慢 28 ms。
- 平均值掩盖了尾部：一次"OpenAI 失败 → Anthropic 成功"的请求耗时 `54 + 220 = 274 ms`（再加网关开销），比均值高约 50%；对 P99 SLA 来说，这才是要关注的数字。

---

## 7. 动手改一改

1. **讲义练习 1**：把三家错误率都改成 0.05，`n` 改成 100,000，验证成功率接近 `1 − 0.05³ = 99.9875%`、fallback 比例接近 5%。
2. **输出 P99**：把每个请求的时延存进列表，排序后取第 99 百分位，比较各网关的 P99 与均值。
3. **加入真正的重试**：实现 `call_with_retry`（指数退避 + 抖动，参考测验 Q10），对比"重试后 fallback"与"直接 fallback"的成功率和 P99。
4. **相关故障**：让 OpenAI 在第 300–400 个请求之间 100% 失败（模拟宕机），观察 fallback 能否兜住、时延如何变化；再加一个断路器——连续失败 3 次后 30 个请求内跳过该提供商。
5. **网关容量**：给每个网关加 `max_rps`（如 LiteLLM 2000），按到达率超过上限时以一定概率级联失败，模拟讲义所说的 LiteLLM 崩溃点。
6. **按租户限流**：在请求前加 token bucket / sliding window（参考测验 Q12），统计被限流拒绝的比例。

---

## 8. 常见坑

- **把"失败次数"叫作"重试次数"**：读指标时要看清统计口径，否则会以为系统已经有重试逻辑。
- **用小样本验证高可用**：几个 9 的可用性需要非常大的样本才能观测到失败。
- **假设故障独立**：fallback 的可用性乘法只在独立时成立；共同依赖（网关本身、DNS、同一云区域）会让它失效。
- **只看平均时延**：fallback 主要伤害尾部时延，SLA 要看 P99。
- **注释与代码不一致**：`# half-done` 对应 `0.3`，改代码时要同步更新注释。
- **用浮点秒做窗口边界判断**：限流器里 `1.2 - 1.0 != 0.2`，建议用整数毫秒或纳秒时间戳。
- **把厂商基准当定论**：讲义中 Kong 的 228% / 859% 来自 Kong 自己的测试，选型前要在自己的流量上复测。
