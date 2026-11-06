# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 13 节 行动预算、迭代上限与成本控制 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

这是一个**分层成本控制器（cost governor）模拟器**。它不调用任何模型，而是用一条预设的"消费轨迹"模拟一个 agent：前 29 轮正常工作（每轮 2,500 token），从第 30 轮开始陷入轮询循环（每轮 8,000 token），每轮耗时 30 秒。然后用三种配置跑同一条轨迹：

1. **no caps**：不设任何限制（为了让模拟能结束，实际上用 10,000 轮当上限）；
2. **monthly cap only**：只有一个 $500 的"月度上限"；
3. **layered stack**：每请求上限 + 迭代上限 + 会话美元上限 + 速度限制（velocity limit）+ 月度上限。

它要演示的是讲义的核心论点："**The fix is not one number. It is a stack of limits at different time scales and granularities.**" 不同失效模式（失控循环、慢泄漏、坏版本、正常激增）在不同时间尺度上暴露，所以需要不同层级的限制。

但这份代码最值得学的地方，是它**与讲义的说法不一致**：讲义说"the layered stack catches it within the velocity window"，实际运行中速度限制**从未触发**，拦住循环的是迭代上限 `max_turns=200`；"月度上限"在 10,000 轮里也从未触发。原因是阈值与模拟的消费速率差了两个数量级。读懂这一点，就读懂了"成本护栏的阈值必须按真实消费速率来定"。

> 一句话：**用一条"正常 → 循环"的消费轨迹对比单一上限与分层上限；同时提醒你，阈值没有按实际速率标定的护栏，形同虚设。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `NORMAL_TURN_TOKENS` / `LOOP_TURN_TOKENS` / `LOOP_STARTS_AT` | 常量 | 2,500 / 8,000 token 每轮，第 30 轮开始循环 | 模拟的消费轨迹 |
| `DOLLARS_PER_KTOK` | 常量 | 每千 token $0.003（即每百万 token $3） | 单价 |
| `turn_cost(turn)` | 函数 | 返回第 `turn` 轮消耗的 token | 轨迹生成 |
| `Governor` | dataclass | 6 个阈值 + 5 个开关 + 每轮秒数 | 成本控制器配置 |
| `Run` | dataclass | 轮数、token、美元、历史 `(分钟, 累计美元)`、停止原因 | 运行状态 / 审计 |
| `velocity_exceeded(run, gov, now)` | 函数 | 在滚动窗口内算"美元/分钟"，超过阈值返回 True | 速度限制 |
| `simulate(gov, label)` | 函数 | 最多 10,000 轮：计费 → 记录 → 依次检查各层上限 → 打印 | governor 主循环 |
| `main()` | 函数 | 构造三种配置并模拟，打印结论 | 演示驱动 |

数据流：`turn_cost` → （每请求上限截断）→ 累加 token 与美元 → 时间前进 30 秒 → 写入 `history` → 按顺序检查 `max_turns` → `max_budget_usd` → velocity → monthly → 命中即 `break` 并记录 `stopped_by`。

---

## 3. 逐段精讲

### 3.1 消费轨迹与单价

```python
NORMAL_TURN_TOKENS = 2_500
LOOP_TURN_TOKENS = 8_000
LOOP_STARTS_AT = 30

# $/token (input+output blended) for a Sonnet-class model, mid-2026 rates
DOLLARS_PER_KTOK = 0.003

def turn_cost(turn: int) -> int:
    return LOOP_TURN_TOKENS if turn >= LOOP_STARTS_AT else NORMAL_TURN_TOKENS
```

- 第 1–29 轮正常，第 30 轮起每轮 8,000 token——模拟讲义 $1,200 → $4,800 案例中"新工具让 agent 每次会话都去轮询订单状态"。
- 单价：`0.003` 美元 / 千 token = **$3 / 百万 token**。注释写的是 "$/token"，与变量名 `PER_KTOK` 不一致，以变量名和代码用法（`tok / 1000.0 * DOLLARS_PER_KTOK`）为准。
- 由此可以算出（已用 Python 验证）：
  - 正常轮：2,500 / 1000 × 0.003 = **$0.0075 / 轮**；每轮 30 秒 → **$0.015 / 分钟**；
  - 循环轮：8,000 / 1000 × 0.003 = **$0.024 / 轮** → **$0.048 / 分钟**。
- 记住这两个速率，后面所有"为什么某个上限不触发"的问题都由它们决定。

### 3.2 `Governor` 与 `Run`：配置与状态分离

```python
@dataclass
class Governor:
    max_tokens_per_request: int = 10_000
    max_turns: int = 200
    max_budget_usd: float = 50.0
    velocity_usd_per_min: float = 5.0       # cut off above this rolling rate
    velocity_window_min: float = 10.0
    monthly_cap_usd: float = 500.0

    enable_request_cap: bool = True
    ...
    seconds_per_turn: float = 30.0
```

- 阈值与讲义名词一一对应：`max_tokens`（每请求）、`max_turns`（迭代上限）、`max_budget_usd`（会话美元上限，讲义说这是 Claude Code Agent SDK 的名字）、velocity（$5/分钟 × 10 分钟窗口 = 讲义的 "$50 in 10 minutes"）、monthly cap。
- 每层都有独立开关 `enable_*`，方便做"去掉某一层"的对照实验（讲义练习 1）。
- `Run` 里 `history: list[tuple[float, float]] = field(default_factory=list)`：可变默认值必须用 `default_factory`，否则所有 `Run` 实例会共享同一个列表（见第 5 节）。
- 讲义的 12 层里，代码只实现了 5 层（每请求、迭代、会话美元、速度、月度）；每工具上限、滚动小时/日上限、分级路由、prompt caching、上下文压缩、HITL、熔断后的重新启用路径都没有建模。

### 3.3 `velocity_exceeded`：滚动窗口速率

```python
def velocity_exceeded(run: Run, gov: Governor, now_min: float) -> bool:
    if not run.history:
        return False
    cutoff = now_min - gov.velocity_window_min
    window = [(t, d) for (t, d) in run.history if t >= cutoff]
    if not window:
        return False
    start_min, start_dollars = window[0]
    window_dollars = run.dollars - start_dollars
    elapsed = max(now_min - start_min, EPSILON_MIN)
    rate = window_dollars / elapsed
    return rate > gov.velocity_usd_per_min
```

- `history` 存的是**累计**美元，所以窗口内的花费 = 当前累计 − 窗口起点的累计，不需要逐项求和。
- 用**实际经过的时间** `now_min - start_min` 做分母，而不是名义窗口宽度 10 分钟。注释解释了原因：运行刚开始（不足 10 分钟）时，若除以 10 会把速率低估。
- `max(..., EPSILON_MIN)` 防止第一轮时分母为 0。第一轮窗口只有一个点，`window_dollars = 0`，速率为 0。
- ⚠️ 每次调用都遍历整个 `history`，是 O(n) 的；整个模拟是 O(n²)。生产实现会用双端队列（`collections.deque`）在左侧弹出过期记录，或用分桶计数器。
- ⚠️ 这里的"窗口"是按**模拟时间**滑动的；真实系统要按挂钟时间，并且要跨会话聚合（同一个 API key 下的多个并发会话一起算），否则开 10 个并发会话就能绕过单会话速度限制。

### 3.4 `simulate`：每轮计费，再按顺序检查各层

```python
    for turn in range(1, 10_001):
        tok = turn_cost(turn)
        if gov.enable_request_cap and tok > gov.max_tokens_per_request:
            tok = gov.max_tokens_per_request
        run.turns = turn
        run.tokens += tok
        run.dollars += (tok / 1000.0) * DOLLARS_PER_KTOK
        now_min += gov.seconds_per_turn / 60.0
        run.history.append((now_min, run.dollars))

        if gov.enable_iter_cap and turn >= gov.max_turns:
            run.stopped_by = "max_turns"
            break
        if gov.enable_session_cap and run.dollars >= gov.max_budget_usd:
            ...
        if gov.enable_velocity and velocity_exceeded(run, gov, now_min):
            ...
        if gov.enable_monthly_cap and run.dollars >= gov.monthly_cap_usd:
            ...
```

- **先花钱、后检查**：每轮的费用先计入，再判断是否越界。所以任何上限都会"超出一轮"——比如会话上限 $50 实际停在 $50.02。真实系统要么在调用**前**做预估检查（用 `max_tokens` 估算最坏花费），要么接受"超出一个请求"的误差。
- **每请求上限是截断而不是拒绝**：超过 `max_tokens_per_request` 的轮被截到上限值。默认上限 10,000 > 循环轮的 8,000，所以在默认配置下**从未生效**。
- **检查顺序**决定 `stopped_by` 的标签：同一轮里多个上限同时越界时，只报告第一个。
- ⚠️ 这里的 "monthly cap" 用的是 `run.dollars`——**单次会话**的累计花费，而不是一个月内所有会话的累计。在单会话模拟中，它本质上就是一个阈值更高的会话上限。真正的月度上限需要跨会话的持久化计数（可以接上第 12 节的持久化存储）。
- 循环上限是 10,000 轮；跑满而没有任何上限触发时，`stopped_by` 设为 "ran out of simulated turns"。

### 3.5 `main`：三种配置

```python
    g = Governor(enable_request_cap=False, enable_iter_cap=False, ...)
    # Cap at something huge so the sim terminates; this line is the "unbounded" case.
    g.max_turns = 10_000
    g.enable_iter_cap = True
    simulate(g, "no caps (iter 10k sim)")
```

- "no caps" 先全部关掉，再**重新打开**迭代上限并设为 10,000，只是为了让输出标签更明确。它与 "monthly cap only" 的花费完全相同（$239.52），区别只在 `stopped_by` 的文字。
- "layered stack" 使用全部默认值。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 预设确定性消费轨迹 | 结果可复现，便于比较配置 | 真实消费有噪声、有突发；阈值要基于历史分布（如 P99）留余量 |
| 每层独立开关 | 便于做"去掉一层"的消融实验 | 生产中开关本身要受保护，agent 不能修改（skill 文件："Kill switches the agent itself can modify" 是 hard reject） |
| 速率 = 窗口花费 / 实际经过时间 | 避免启动阶段低估 | 启动阶段几次昂贵调用可能误触发；可以要求窗口内至少有若干样本再判断 |
| 先计费后检查 | 实现简单 | 每个上限都会超出一轮；生产在调用前用 `max_tokens` 估算最坏花费做预检 |
| "月度上限"用单会话累计 | 单会话模拟里不需要持久化 | 真正的日/周/月上限必须跨会话、跨实例聚合，并持久化计数 |
| 速度阈值 $5/分钟 | 与讲义 "$50 in 10 minutes" 一致 | 与模拟中 $0.048/分钟 的循环速率差约 100 倍，永远不会触发；应按"正常速率 × 安全系数"标定 |
| 每请求上限 10,000 | 大于正常和循环单轮用量 | 在本轨迹中不起作用；它防的是"单次回复失控"，不是"多轮循环" |
| 打印 `stopped_by` | 让每次熔断有记录 | 生产中熔断要告警到人、写审计日志，并有单独的重新启用流程（讲义第 12 层） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 数字下划线分隔 | `2_500`、`10_000`、`range(1, 10_001)` | 仅为可读性，等于 2500、10000 |
| `@dataclass` 带默认值 | `max_turns: int = 200` | 所有字段都有默认值，`Governor()` 即可构造 |
| `field(default_factory=list)` | `history: list[...] = field(default_factory=list)` | 可变默认值（列表、字典）必须用工厂函数，每个实例各自新建 |
| 关键字参数构造 | `Governor(enable_request_cap=False, ...)` | 只覆盖需要改的字段，其余用默认值 |
| 构造后修改属性 | `g.max_turns = 10_000` | dataclass 默认可变 |
| 复杂类型注解 | `list[tuple[float, float]]` | 列表，元素是 `(float, float)` 元组 |
| 条件表达式 | `LOOP_TURN_TOKENS if turn >= LOOP_STARTS_AT else NORMAL_TURN_TOKENS` | 一行 if/else |
| 列表推导式 + 解包 + 过滤 | `[(t, d) for (t, d) in run.history if t >= cutoff]` | 筛出窗口内的记录 |
| 元组解包 | `start_min, start_dollars = window[0]` | 取窗口第一个点 |
| `max` 做下限保护 | `max(now_min - start_min, EPSILON_MIN)` | 防止除以 0 |
| 增强赋值 | `run.tokens += tok`、`now_min += ...` | 原地累加 |
| `for ... break` | 任一上限命中即 `break` | 提前结束循环 |
| `if not run.stopped_by` | 空字符串为假 | 判断"没有任何上限触发" |
| f-string 格式符 | `{label:<24}`、`{run.turns:>5}`、`{run.tokens:>8,}`、`{run.dollars:>7.2f}` | 左/右对齐、宽度、千分位、两位小数 |
| 相邻 f-string 拼接 | `print(f"..." f"...")` | 括号内两段字符串自动合并 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，耗时约 1 秒，输出确定）：

```text
Agent enters a polling loop at turn 30.
  no caps (iter 10k sim)    turns=10000  tokens=79,840,500  dollars=$ 239.52  stopped_by=max_turns
  monthly cap only          turns=10000  tokens=79,840,500  dollars=$ 239.52  stopped_by=ran out of simulated turns
  layered stack             turns=  200  tokens=1,440,500  dollars=$   4.32  stopped_by=max_turns
```

逐项解读：

- **token 数可以手算**：
  - no caps：29 × 2,500 + 9,971 × 8,000 = 72,500 + 79,768,000 = **79,840,500**，× $0.003/千 = **$239.52**；
  - layered：29 × 2,500 + 171 × 8,000 = 72,500 + 1,368,000 = **1,440,500**，= **$4.32**。
- **模拟时长**：10,000 轮 × 30 秒 = 5,000 分钟 ≈ **83 小时（约 3.5 天）**，循环 3.5 天也只花了 $239.52，**从未达到 $500 的月度上限**。按 $0.024/轮计算，要到约 20,853 轮（约 174 小时、7 天多）才会碰到 $500。所以 "monthly cap only" 的标签是 "ran out of simulated turns"，而不是 "monthly_cap"。
- **layered stack 是被 `max_turns` 拦下的，不是 velocity**。速度限制阈值 $5/分钟，循环速率只有 $0.048/分钟，相差约 104 倍。会话上限 $50 也远未达到。
- **与讲义的不一致**（这是本节最重要的发现）：
  - 讲义 Use It："the layered stack catches it within the velocity window" —— 实际由迭代上限拦截，速度限制从未触发；
  - 讲义练习 1："Confirm the velocity limit fires before the iteration cap" —— 无法确认，事实相反；"disable the velocity limit and measure how much the agent spends before the iteration cap catches it" —— 关掉速度限制后结果**完全相同**（200 轮、$4.32），因为速度限制本来就没起作用；
  - HEADLINE 打印的 "Velocity limit ($5/min rolling) catches a loop within minutes" 与 "Monthly cap fires late: the wallet is already half-gone" 都不是本次运行展示出来的事实。
- **补充实验**（已实际运行）：

  | 修改 | 结果 |
  |------|------|
  | 关掉迭代上限（其余默认） | 第 2,104 轮被 `max_budget_usd` 拦下，$50.02，约 17.5 小时 |
  | 关掉迭代上限和速度限制 | 同上，说明速度限制依然没起作用 |
  | `velocity_usd_per_min=0.03` | 第 39 轮触发 `velocity_limit`，$0.46（循环开始后 10 轮） |
  | `velocity_usd_per_min=0.02` | 第 33 轮触发，$0.31 |
  | `velocity_usd_per_min=0.016` | 第 30 轮即触发，$0.24——但阈值只比正常速率 $0.015 高 7%，现实中会频繁误报 |
  | `seconds_per_turn=5`（讲义"5 秒重试"）且只保留速度限制 | 循环速率 $0.288/分钟，仍低于 $5，跑满 10,000 轮 |
  | `max_tokens_per_request=5000` | 循环轮被截到 5,000，200 轮共 927,500 token、$2.78 |

  结论：要让速度限制真正"在几分钟内抓住循环"，阈值应设在正常速率与循环速率之间并留余量（例如 $0.03/分钟，约为正常速率的 2 倍）。讲义的 "$50 / 10 分钟" 是面向一个**组织级**消费规模的例子，直接套在单会话上就失效了。

---

## 7. 动手改一改

1. **（讲义练习 1，修正版）让速度限制真正起作用**：把 `velocity_usd_per_min` 改为 0.03，确认它在第 39 轮先于迭代上限触发；再关掉它，测量迭代上限拦截前的花费（$4.32），算出速度限制省下的比例。
2. **按正常速率自动标定阈值**：写一个函数，用前 20 轮的平均每分钟花费 × 系数 k（如 2.0）作为速度阈值；试 k = 1.2、2、5，观察触发时机与"误报"风险。
3. **加入每工具上限**（讲义第 4 层与练习 2）：让循环轮标记为 `tool="order_status"`，给它设"每会话最多 20 次"，看它在第几轮触发。这正是讲义 $1,200 → $4,800 案例的修复方式。
4. **真正的日 / 月上限**：引入一个跨会话的 `Ledger`（可以是 JSON 文件），连续模拟 30 个会话，每个会话的花费累加到月度账本；当月度累计越界时，新会话启动即被拒绝。
5. **预检代替事后检查**：在计费**之前**用 `min(turn_cost(turn), max_tokens_per_request)` 预估本轮最坏花费，若会使会话花费超过 `max_budget_usd` 就不执行这一轮，比较停止时的花费是否不再超出上限。
6. **（进阶）告警与熔断分离**：在 50% / 80% 预算处只告警（打印 `ALERT`），100% 才熔断；熔断后写入一条"需人工重新启用"的记录，模拟讲义第 12 层 "requires a separate re-enable path"。

---

## 8. 常见坑

- **阈值不按真实速率标定**：本代码就是反例——$5/分钟的速度限制面对 $0.048/分钟的循环毫无作用。阈值要从实际消费分布推出来，而不是抄一个"看起来合理"的数字。
- **只设月度上限**：讲义："A single monthly cap catches a runaway agent only after the wallet is gone." skill 文件把它列为 hard reject。
- **把 `max_tokens` 当成预算**：它只限制单次回复长度，挡不住多轮循环（本例中它从未生效）。
- **只在单会话内计数**：并发会话、重试、子 agent 都会绕过单会话上限；日/月上限和速度限制要在网关或账户层聚合（可参考 AI 网关、FinOps 相关章节）。
- **先花钱后检查导致超额**：每个上限都可能被超出一轮；对昂贵调用要做调用前预检或 HITL。
- **熔断后可以被 agent 自己恢复**：上限和开关必须在 agent 无法修改的外部（harness、网关、账单系统），重新启用要走人工流程。
- **把权限分类器当成本控制**：讲义强调 Auto Mode 分类器与成本"正交"，两者都需要。
- **新工具上线不加上限和告警**：讲义案例的教训——"every new tool surface is a new potential loop; every new tool needs its own cap and its own alert."
