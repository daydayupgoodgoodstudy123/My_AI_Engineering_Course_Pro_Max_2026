# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 01 节 托管 LLM 平台：Bedrock、Vertex AI、Azure OpenAI ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`；文件还 import 了 `random`、`statistics` 但未使用）

---

## 1. 这份代码在考察什么

这是一个"托管 LLM 平台比较器"的玩具版，用几组示意参数把讲义的三个核心论点算出来：

1. **同一工作负载在三家平台的日成本与延迟**：Bedrock 按需、Azure OpenAI（可选 PTU）、Vertex Gemini；同时显示 TTFT P50/P99 是否满足 SLA，以及各家 FinOps 归因能力的定性评级。
2. **PTU 的盈亏平衡**：扫描 10%–100% 利用率，看 Azure PTU 何时比按需便宜。
3. **two-provider minimum 的代价**：网关开销 + 备用余量带来的每日、每月额外成本。

需要提前知道：模块 docstring 写明"prices and latencies are 2026 public-domain approximations"，所有数字都是示意参数；另外 `simulate` 的 PTU 选择逻辑只看成本不看 SLA，导致演示中 PTU 从未被选中（见 3.3）。

> 一句话：**平台选型是"模型目录 + 容量模型 + 成本归因"的多维决策，不是比谁的延迟数字小**——而要让代码真正体现这一点，决策函数必须把 SLA 当作约束而不是旁观者。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Platform` | dataclass | 一个平台的按需单价、PTU 价格与容量、三种 TTFT、归因评级 | 平台参数 |
| `PLATFORMS` | 列表 | 三个平台实例 | Bedrock / Azure OpenAI / Vertex |
| `simulate` | 函数 | 给定日 token 量与 SLA，打印每个平台的日成本、P50/P99、SLA 判定、归因、路径 | 平台对比 |
| `break_even_demo` | 函数 | Azure PTU 在 10%–100% 利用率下与按需的成本对比 | PTU 盈亏平衡 |
| `lock_in_cost` | 函数 | 计算网关 3% + 备用余量 10% 的额外成本 | two-provider minimum |
| `main` | 函数 | 两次 `simulate` + 平衡扫描 + 冗余成本 | 入口 |

数据流：`main()` → `simulate(3M/1M, SLA 200, 无 PTU)` → `simulate(30M/15M, SLA 100, 允许 PTU)` → `break_even_demo()` → `lock_in_cost()`，每一步只打印、不返回值。

---

## 3. 逐段精讲

### 3.1 `Platform` 与三组参数

```python
@dataclass
class Platform:
    name: str
    per_mtok_input: float        # $/M input tokens on-demand
    per_mtok_output: float       # $/M output tokens on-demand
    ptu_hourly: float | None     # $/hour for one reservation unit (None = not offered)
    ptu_tokens_per_hour: int     # tokens/hour a single PTU delivers
    ttft_median_ms: float        # median TTFT on shared capacity
    ttft_p99_ms: float           # P99 TTFT on shared capacity
    ttft_median_ptu_ms: float    # median TTFT on dedicated PTU
    attribution: str             # qualitative FinOps surface grade

PLATFORMS = [
    Platform("Bedrock on-demand",    3.00, 15.00, 21.0, 1_200_000, 75, 180, 55, "A (Application Inference Profiles)"),
    Platform("Azure OpenAI (PTU)",    2.50, 10.00, 10.0, 2_000_000, 50, 140, 38, "B (scopes + tags + PTU obj)"),
    Platform("Vertex AI Gemini",     1.25,  5.00, None,          0, 60, 160,  0, "B+ (BQ billing export)"),
]
```

把参数排成表更直观：

| 平台 | 输入 $/M | 输出 $/M | PTU $/小时 | PTU token/小时 | 共享 P50 | 共享 P99 | PTU P50 | 归因 |
|---|---|---|---|---|---|---|---|---|
| Bedrock | 3.00 | 15.00 | 21 | 1.2M | 75 | 180 | 55 | A |
| Azure OpenAI | 2.50 | 10.00 | 10 | 2.0M | 50 | 140 | 38 | B |
| Vertex | 1.25 | 5.00 | 无 | 0 | 60 | 160 | — | B+ |

- `float | None` 是 Python 3.10 的联合类型写法；配合 `from __future__ import annotations`，在更早版本里作为注解也不会报错。`None` 表示"不提供 PTU"，后面用 `p.ptu_hourly is not None` 判断。
- `1_200_000` 中的下划线是数字分隔符，只为可读性。
- 与讲义对应：Bedrock 75 ms、Azure 50 ms（讲义的中位数）；Bedrock PT $21/小时（讲义"starts around $21/hour"）；归因评级 A / B / B+ 对应讲义"Bedrock 最干净、Vertex 最灵活、Azure 最不透明"。
- ⚠️ 口径差异：代码把 Azure 的 50 ms 当作**共享**容量中位数、PTU 另设 38 ms；而讲义"Numbers you should remember"写的是"~50 ms (with PTUs)"。讲义 Concept 一节又说 50 ms 是在"shared on-demand"下测的，并且是"Llama 3.1 405B equivalents"——可讲义自己也说 Azure OpenAI Service 目录里没有非 OpenAI 模型。这些数字的测量条件本身不清楚。
- ⚠️ 平台名 `"Azure OpenAI (PTU)"` 暗示走 PTU，但两次 `simulate` 实际都走按需。
- Vertex 的 `ttft_median_ptu_ms=0` 只是占位，因为 `ptu_hourly=None` 永远不会走 PTU 分支。讲义说 Vertex 也有按 Gemini SKU 出售的预留容量，代码没有建模。

### 3.2 `simulate`：按需成本

```python
    for p in PLATFORMS:
        cost_ondemand = (tokens_in_per_day / 1e6) * p.per_mtok_input + \
                        (tokens_out_per_day / 1e6) * p.per_mtok_output
```

- 按需成本 = 输入百万 token 数 × 输入单价 + 输出百万 token 数 × 输出单价。行尾 `\` 是显式续行。
- 工作负载 1（3M 输入 + 1M 输出）：Bedrock 3 × 3 + 1 × 15 = $24；Azure 3 × 2.5 + 1 × 10 = $17.5；Vertex 3 × 1.25 + 1 × 5 = $8.75——与输出一致。
- 这里比较的是"同一工作负载在不同平台"，但三家跑的是**不同模型**（Claude / GPT / Gemini），单价和延迟不能直接等价成"平台好坏"；讲义的选型规则正是"先看模型目录"。

### 3.3 `simulate`：PTU 路径与 SLA 判定（核心问题所在）

```python
        if use_ptu and p.ptu_hourly is not None:
            total_tokens = tokens_in_per_day + tokens_out_per_day
            daily_capacity_per_ptu = p.ptu_tokens_per_hour * 24
            ptu_count = max(1, (total_tokens + daily_capacity_per_ptu - 1) // daily_capacity_per_ptu)
            cost_ptu = ptu_count * p.ptu_hourly * 24
            cost = min(cost_ondemand, cost_ptu)
            ttft_p50 = p.ttft_median_ptu_ms if cost == cost_ptu else p.ttft_median_ms
            ttft_p99 = ttft_p50 * 1.5 if cost == cost_ptu else p.ttft_p99_ms
            path = "PTU" if cost == cost_ptu else "on-demand"
        ...
        sla_ok = "PASS" if ttft_p99 < sla_ttft_ms else "FAIL"
```

- **PTU 数量**：`(a + b - 1) // b` 是整数向上取整；`max(1, ...)` 保证至少 1 个。PTU 容量按"输入 + 输出"总 token 计算，并假设一天 24 小时流量均匀（没有峰谷）。
- **PTU 成本**：个数 × 每小时价格 × 24，与实际用量无关——这就是讲义"pay for the reservation even when idle"。
- **PTU 延迟**：P50 用 `ttft_median_ptu_ms`，P99 直接假设为 P50 的 1.5 倍（专用容量尾延迟更紧），是示意性假设。
- ⚠️ **决策只看成本**：`cost = min(cost_ondemand, cost_ptu)`，SLA 只在最后用来打 PASS/FAIL，不参与选择。第二个工作负载（30M + 15M，SLA 100 ms）下（已计算）：

  | 平台 | PTU 个数 | PTU $/天 | 按需 $/天 | PTU P99 | 代码选择 | 结果 |
  |---|---|---|---|---|---|---|
  | Bedrock | 2 | 1,008 | 315 | 82.5 ms | 按需 | FAIL |
  | Azure | 1 | 240 | 225 | 57 ms | 按需 | FAIL |
  | Vertex | — | — | 112.5 | — | 按需 | FAIL |

  Azure PTU 只比按需贵 $15/天，却能满足 SLA；代码选了便宜但必然 FAIL 的方案。讲义与 skill 文件的规则是"SLA 比按需能提供的更紧时，必须用 PTU"，代码与之相反，整个演示里 `[PTU]` 路径从未出现。测验 Q9 给出了"先满足 SLA、再比成本"的改法，改后 Azure PTU $240 PASS、Bedrock PTU $1,008 PASS、Vertex 仍 FAIL。
- ⚠️ `cost == cost_ptu` 用浮点相等判断走了哪条路径；当两种成本恰好相等时会判为 PTU。更稳妥的写法是在比较时直接记下路径。

### 3.4 `break_even_demo`：盈亏平衡扫描

```python
    p = PLATFORMS[1]  # Azure
    for util_pct in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100):
        tokens_per_day = int(p.ptu_tokens_per_hour * 24 * (util_pct / 100.0))
        ondemand = (tokens_per_day / 1e6) * p.per_mtok_output
        ptu = 24 * p.ptu_hourly
        winner = "PTU" if ptu < ondemand else "on-demand"
```

- 盈亏平衡利用率公式：**u\* = PTU 每小时价格 / (每小时容量 / 10⁶ × 单价)**。代入 Azure：10 / (2 × 10) = 0.5，正好落在讲义"40–60%"带的中间。
- 50% 时两边都是 $240，判断用严格小于，平局判给按需；60% 才第一次是 PTU。
- ⚠️ **只用输出单价**：`ondemand` 把所有 token 按 $10/M（输出价）计费，而 `simulate` 中 PTU 容量按"输入 + 输出"计算。若按真实混合单价计费（已计算）：
  - Azure 输入:输出 = 3:1 → $4.375/M → u\* ≈ 1.14（**永不划算**）；2:1 → $5/M → u\* = 1.0；
  - Bedrock 只按输出价 u\* ≈ 1.17，3:1 时 ≈ 2.92——在代码参数下 Bedrock PT **在任何利用率下都不比按需便宜**，与讲义"break-even is around half peak utilization"不符。
- ⚠️ 100% 利用率时 Azure 按需 $480、PTU $240，最多省 50%，达不到讲义"up to ~70% savings"。
- 标题写"GPT-4o class"，而讲义练习 1 问的是"70B class model"，代码中并没有 70B 模型的参数。

### 3.5 `lock_in_cost`：冗余的价格

```python
    tokens_per_day = 5_000_000
    primary_cost = (tokens_per_day / 1e6) * 10.00
    gateway_overhead_pct = 3.0
    failover_headroom_pct = 10.0
    uplift = primary_cost * (gateway_overhead_pct + failover_headroom_pct) / 100
```

- 主成本 5M × $10/M = $50/天；网关开销 3%、备用余量 10%，合计 13% = $6.50/天、$195/月。
- 这些百分比都是假设参数。讲义说"Cost uplift is negligible"，按代码自己的假设是 13%——不算可忽略，但与停机损失相比通常很小：若该功能每小时支撑 $2,000 收入，全年冗余成本 $2,340 只相当于约 1.17 小时停机（测验 Q11）。
- 最后一行把停机代价写成定性描述（客户流失、SLA 赔付、战情室时间），没有量化。

### 3.6 未使用的 import

```python
import random
import statistics
```

- 两者在文件中都没有被使用：模块 docstring 提到 "TTFT median / P99"，看起来原本打算随机生成延迟样本再用 `statistics` 求分位数，但最终版本直接把 P50/P99 写成常数。linter（如 ruff 的 F401）会提示这两个未使用的导入。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用常数表示价格与延迟 | 输出稳定、易读 | 价格变化快、延迟与模型/区域/时段强相关；生产应从价目表与自测数据加载，并记录日期 |
| P99 直接写常数，PTU 的 P99 = 1.5 × P50 | 省去延迟分布建模 | 实际需要压测或线上 P99；`random`、`statistics` 被 import 却未用 |
| `min(按需, PTU)` 选路径 | 代码最短 | SLA 不参与决策，SLA 紧时选错；应先过滤满足 SLA 的方案再比成本 |
| PTU 容量按日均摊、24 小时均匀 | 简化 | 真实流量有峰谷，容量按峰值买；应用小时级流量曲线计算 |
| 盈亏平衡按输出单价计费 | 让平衡点落在 50% | 高估按需成本；应按真实输入/输出比例的混合单价 |
| 归因评级用字符串 | 讲义的定性结论 | 无法参与计算；可转为"归因覆盖率"等可度量指标 |
| 冗余成本用固定百分比 | 演示量级 | 应计入跨云适配、eval、数据出口、合规等成本，并与停机损失期望对比 |
| 三家用不同模型却直接比价 | 讲义关注平台 | 平台选型先由模型目录决定，跨模型比价要配合质量评测 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，`float \| None` 在旧版本中也可作注解 |
| 联合类型 | `ptu_hourly: float \| None` | 可以是 float，也可以是 None |
| `@dataclass` | `class Platform:` | 自动生成构造函数；字段按声明顺序作为位置参数 |
| 位置参数构造 | `Platform("Bedrock on-demand", 3.00, 15.00, 21.0, 1_200_000, 75, 180, 55, "A ...")` | 9 个参数必须按顺序，易错；关键字参数更清晰 |
| 数字分隔符 | `1_200_000`、`30_000_000` | 下划线只为可读，值不变 |
| 科学计数法 | `tokens / 1e6` | `1e6` 即 1,000,000（浮点） |
| 行尾反斜杠续行 | `... * p.per_mtok_input + \` | 显式续行；放在括号里换行更推荐 |
| 整数向上取整 | `(a + b - 1) // b` | `//` 是整除；该式对正整数等于 ceil(a/b) |
| `is not None` | `p.ptu_hourly is not None` | 判断 None 要用 `is`，不用 `==` |
| 条件表达式 | `"PTU" if cost == cost_ptu else "on-demand"` | 一行 if/else |
| 内置 `min` / `max` | `min(cost_ondemand, cost_ptu)`、`max(1, ...)` | 取较小/较大值 |
| f-string 格式说明 | `{p.name:25}`、`{cost:8.2f}`、`{ttft_p50:7.0f}`、`{sla_ok:>6}`、`{util_pct:>7}` | 宽度、小数位、右对齐 |
| f-string 中的表达式 | `{tokens_in_per_day/1e6:.1f}`、`{'enabled' if use_ptu else 'off'}` | 花括号里可以写任意表达式 |
| 字符串乘法与 `len` | `"-" * len(header)` | 生成与表头等长的分隔线 |
| 元组字面量循环 | `for util_pct in (10, 20, ..., 100):` | 直接遍历固定档位 |
| 关键字参数调用 | `simulate(tokens_in_per_day=3_000_000, ..., use_ptu=False)` | 调用时写明参数名，可读性好 |
| 未使用的 import | `import random`、`import statistics` | 不影响运行，但应删除 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`；被 import 时可单独复用 `PLATFORMS` 等 |

---

## 6. 运行结果解读

实际运行（Python 3，瞬间完成）：

```text
Workload: 3.0M input, 1.0M output per day
SLA: TTFT P99 < 200 ms   |   PTU path: off

Platform                       $/day    TTFT P50    TTFT P99     SLA  Attribution
---------------------------------------------------------------------------------
Bedrock on-demand          $   24.00       75 ms      180 ms    PASS  A (Application Inference Profiles)  [on-demand]
Azure OpenAI (PTU)         $   17.50       50 ms      140 ms    PASS  B (scopes + tags + PTU obj)  [on-demand]
Vertex AI Gemini           $    8.75       60 ms      160 ms    PASS  B+ (BQ billing export)  [on-demand]

Workload: 30.0M input, 15.0M output per day
SLA: TTFT P99 < 100 ms   |   PTU path: enabled

Platform                       $/day    TTFT P50    TTFT P99     SLA  Attribution
---------------------------------------------------------------------------------
Bedrock on-demand          $  315.00       75 ms      180 ms    FAIL  A (Application Inference Profiles)  [on-demand]
Azure OpenAI (PTU)         $  225.00       50 ms      140 ms    FAIL  B (scopes + tags + PTU obj)  [on-demand]
Vertex AI Gemini           $  112.50       60 ms      160 ms    FAIL  B+ (BQ billing export)  [on-demand]

PTU BREAK-EVEN SWEEP — Azure OpenAI, GPT-4o class
On-demand rate: $10.00/M output  |  PTU: $10/hr, 2.0M tok/hr
  Util %     On-demand $/day     PTU $/day  Winner
     10%  $           48.00  $    240.00  on-demand
     ...
     50%  $          240.00  $    240.00  on-demand
     60%  $          288.00  $    240.00  PTU
     ...
    100%  $          480.00  $    240.00  PTU

TWO-PROVIDER MINIMUM — cost uplift for redundancy
Primary daily spend: $50.00
Gateway overhead (3%): $1.50/day
Idle secondary headroom (10%): $5.00/day
Total uplift: $6.50/day
Monthly uplift: $195.00
```

逐项解读：

- **工作负载 1（SLA 200 ms、不允许 PTU）**：三家都 PASS，成本 Vertex $8.75 < Azure $17.50 < Bedrock $24.00。注意这是三个不同模型的价格，不代表平台本身贵贱；按讲义，若产品必须用 Claude，答案仍是 Bedrock（或直连 Anthropic）。
- **工作负载 2（SLA 100 ms、允许 PTU）**：三家全部走按需、全部 FAIL。原因见 3.3：代码只按成本选路径。按"先满足 SLA"的规则，Azure 应以 $240/天走 PTU 并 PASS（P99 57 ms），Bedrock 应以 $1,008/天走 2 个 PTU 并 PASS（P99 82.5 ms）。
- **盈亏平衡扫描**：平衡点正好 50%（平局判按需），60% 起 PTU 更便宜，100% 时省 50%。讲义练习 1 的答案在代码参数下就是"约 50%，处在 40–60% 带中间"，但这个结论建立在"所有 token 按输出价计费"的假设上；按真实混合单价，Azure 的平衡点会升到 100% 甚至更高（3.4）。
- **冗余成本**：增幅 13%，月 $195。讲义"negligible"的说法应理解为"与停机损失相比很小"。

---

## 7. 动手改一改

1. **讲义练习 1**：把 `break_even_demo` 改成接受 `input_ratio` 参数，用混合单价 `(r_in × 输入份数 + r_out × 输出份数) / 总份数` 计费，分别打印 1:1、2:1、3:1 下 Azure 与 Bedrock 的盈亏平衡利用率。
2. **让 SLA 参与决策**：按测验 Q9 改写 `simulate`，先筛出满足 SLA 的方案，再选最便宜；都不满足时选最便宜并标 FAIL。确认工作负载 2 下 Azure 走 PTU 并 PASS。
3. **混合策略**：允许"k 个 PTU 承载基线 + 溢出部分走按需"，对 k = 0, 1, 2 计算成本与（近似）延迟，找到成本最低且满足 SLA 的 k。
4. **用上 `random` 与 `statistics`**：为每个平台生成 1,000 个对数正态分布的 TTFT 样本（中位数取参数值），用 `statistics.quantiles(samples, n=100)[98]` 求 P99，替代写死的常数，观察 P99 随分布参数的波动。
5. **讲义练习 4 的模拟**：构造一份"按团队打标签"的调用日志（团队、模型、输入/输出 token），写一个函数按团队汇总成本，模拟 Application Inference Profiles 的效果，并人为制造一个 token/请求暴涨 4 倍的团队，看能否一眼定位。
6. **冗余成本 vs 停机损失**：给 `lock_in_cost` 增加"每小时收入"和"年停机小时数期望"参数，输出"冗余的年成本"与"不冗余的年期望损失"，并找出两者相等的停机小时数。

---

## 8. 常见坑

- **把 SLA 当打分而不是约束**：先按成本选、再看 SLA，只会得到"便宜但不合格"的方案。
- **盈亏平衡只用输出单价**：输入 token 通常更多更便宜，混合单价可能让 PTU 永远不划算。
- **忽略峰谷**：按日均流量算 PTU 个数，峰值时容量不足、谷值时浪费。
- **跨模型直接比价**：三家跑的是不同模型，价格和延迟差异混入了模型差异。
- **不追问延迟数字的测量条件**：讲义中"50 ms"同时被描述为共享按需与 PTU 条件下的数字，且对应的是 Azure OpenAI 并不提供的 Llama 405B——这类数字不能直接用于选型。
- **浮点相等判断路径**：`cost == cost_ptu` 在成本恰好相等或有舍入时含义不清，应显式记录选择。
- **未使用的 import**：`random`、`statistics` 留在文件里会误导读者以为代码做了随机延迟模拟。
