# 测验 · 行动预算、迭代上限与成本控制（Action Budgets, Iteration Caps, and Cost Governors）

> **阶段 15 · 自主系统 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Denial of Wallet | agent 的坏循环不是"一条坏回复"，而是一张账单：持续推理、持续调用工具、持续计费，没有任何东西设计来阻止它 |
| 2 | 成本控制栈（12 层） | 每请求 `max_tokens`、每任务 token 预算、每任务美元预算、每工具调用上限、迭代上限 `max_turns`、分钟/小时/日/月滚动上限、速度限制、分级模型路由、prompt caching、上下文压缩、昂贵动作 HITL、超限熔断 |
| 3 | 为什么要分层 | 失效模式的时间尺度不同：失控循环靠速度限制、慢泄漏靠日上限、坏版本靠周/月上限、正常激增靠小时/日上限 + 清晰日志 |
| 4 | 速度限制（velocity limit） | 短窗口内的花费速率上限，讲义例子 "$50 / 10 分钟"；比月度上限早得多地抓住循环——前提是阈值按真实速率标定 |
| 5 | Harness 预算接口 | 讲义：Claude Code Agent SDK 提供 `max_turns`、`max_budget_usd`（超限会话中止）、`allowed_tools`/`disallowed_tools`、工具调用前的 hook |
| 6 | 预算与权限正交 | 讲义：没有 `max_budget_usd` 的 Auto Mode 会话是"无治理的自主"；权限分类器与成本无关，两层都要 |
| 7 | $1,200 → $4,800 案例 | 新增订单查询工具后 agent 每次会话都去轮询，无循环检测、无每工具上限、无周环比告警；修复是每工具上限 + 日增长告警 |
| 8 | 每个新工具都是潜在循环 | 新工具上线必须带自己的上限和告警 |
| 9 | 熔断的外部性 | 熔断记录在案、需要单独的重新启用路径；上限必须在 agent 无法修改的地方执行 |
| 10 | 代码揭示的标定问题 | 模拟中循环速率只有 $0.048/分钟，$5/分钟的速度限制从未触发，实际拦截的是 `max_turns=200` |

### 核心技能（能动手做到）

- [ ] 跑通 `code/main.py`，手算三种配置的 token 数与美元数，并解释每一行的 `stopped_by`
- [ ] 根据"每轮 token × 单价 × 每分钟轮数"算出正常速率与循环速率，据此为速度限制选出能真正生效的阈值
- [ ] 指出代码中"月度上限"其实是单会话累计，并设计跨会话的账本
- [ ] 解释"先计费后检查"为何会超出上限一轮，并写出调用前预检
- [ ] 为一个 agent 列出全部工具并给每个工具设上限，说明哪个工具需要最紧的上限
- [ ] 为一个过夜无人值守任务估算成本，设定 `max_budget_usd` 并解释安全系数

---

## 二、基础自测（选择题）

**Q1.** 讲义中 "Denial of Wallet" 指的是：

- A. 云服务商因账单逾期而停止服务
- B. agent 陷入循环，持续推理、调用工具、产生费用，而没有任何设计好的机制去阻止它
- C. 攻击者用大量请求压垮 API，导致正常用户无法访问
- D. 模型因为 `max_tokens` 太小而输出被截断

**Q2.** 讲义把四种失效模式映射到不同的控制层。"agent 卡在一个每 5 秒重试一次的循环里"应该主要由哪一层抓住？

- A. 月度上限
- B. prompt caching
- C. 周上限
- D. 速度限制（velocity limit）

**Q3.** 运行 `code/main.py`，"layered stack" 一行的 `stopped_by` 是：

- A. `max_turns`（第 200 轮，$4.32）
- B. `velocity_limit`（循环开始后几分钟内）
- C. `max_budget_usd`（$50）
- D. `monthly_cap`（$500）

**Q4.** 运行 `code/main.py`，"monthly cap only" 一行的结果是：

- A. 第 30 轮触发 `monthly_cap`
- B. 花费达到 $500 时触发 `monthly_cap`
- C. 跑满 10,000 轮、花费 $239.52，`stopped_by=ran out of simulated turns`——月度上限从未触发
- D. 程序因除以 0 报错

**Q5.** 代码中循环轮每轮 8,000 token，单价 `DOLLARS_PER_KTOK = 0.003`，每轮 30 秒。循环阶段的花费速率是：

- A. $0.024 / 分钟
- B. $0.048 / 分钟
- C. $0.48 / 分钟
- D. $4.8 / 分钟

**Q6.** 关于每请求 `max_tokens`，下列说法正确的是：

- A. 它只限制单次回复的长度，挡不住"很多轮、每轮都正常长度"的循环
- B. 它是会话级的总预算，超出后会话中止
- C. 设置了它就不需要 `max_turns`
- D. 在本节代码默认配置下，它把每个循环轮从 8,000 截断到了 5,000

**Q7.** 关于讲义中的电商 agent 案例，下列说法正确的是：

- A. 原因是模型提供商涨价
- B. 原因是模型被 prompt 注入，修复方式是加内容过滤
- C. 只要设置了月度上限就能及时发现
- D. 月成本从 $1,200 涨到 $4,800（是原来的 4 倍）；原因是新工具让 agent 每次会话都轮询订单状态，修复是每工具上限 + 日增长告警

**Q8.** 讲义说"An `autoMode` session without `max_budget_usd` is ungoverned autonomy"，并指出 Auto Mode 的分类器"is orthogonal to cost"。这意味着：

- A. 有了 Auto Mode 分类器，就可以不设预算
- B. 有了预算，就可以不需要权限分类器
- C. 权限分类器决定"这个动作能不能做"，预算决定"总共能花多少"，两者解决不同问题，必须同时具备
- D. Auto Mode 会自动设置 `max_budget_usd`

---

## 三、动手 / 代码题

**Q9.** 讲义 Use It 说："the layered stack catches it within the velocity window"；练习 1 说："Confirm the velocity limit fires before the iteration cap"。

1. 实际运行中速度限制触发了吗？用数字说明原因。
2. 关掉速度限制后，"在迭代上限拦截之前 agent 花了多少钱"？与开着速度限制时相比有何不同？为什么？
3. 给出一个能让速度限制在循环开始后几分钟内触发、又不会在正常阶段误报的阈值，并说明你怎么选的。

**Q10.** 阅读 `simulate` 中的月度上限检查：

```python
        if gov.enable_monthly_cap and run.dollars >= gov.monthly_cap_usd:
            run.stopped_by = "monthly_cap"
            break
```

1. 这里的 "monthly cap" 真的是"月度"上限吗？
2. 按代码的消费速率，单个会话要循环多久才会碰到 $500？
3. 设计一个真正跨会话的日 / 月上限（关键代码或伪代码），说明它的计数应该存在哪里。

**Q11.** 关掉迭代上限运行 layered stack（`Governor(enable_iter_cap=False)`），结果是第 2,104 轮被 `max_budget_usd` 拦下，花费 **$50.02**。

1. 为什么会超过 $50？
2. 改写 `simulate`，在计费**之前**做预检，使会话花费永远不超过 `max_budget_usd`。

**Q12.** 讲义练习 4：为"夜间无人值守地分诊一个仓库的 50 个 issue"估算成本。假设每个 issue 平均 12 轮、每轮 6,000 token，单价 $3 / 百万 token。

1. 点估计是多少？按讲义建议把 `max_budget_usd` 设为点估计的 2 倍，是多少？为什么是 2 倍而不是 1.1 倍或 10 倍？
2. 除了 `max_budget_usd`，这个任务还应该配哪些上限？

---

## 四、面试高频题

**Q13.**（基础必考）为什么 agent 的成本控制不能只靠一个月度预算？请按时间尺度说明你会设哪些层，各自抓什么问题。

**Q14.**（原理深挖）速度限制（velocity limit）怎么实现？窗口、分母、聚合范围各有什么讲究？阈值怎么定？

**Q15.**（工程实践）讲义电商案例：新增一个工具后月成本从 $1,200 涨到 $4,800。如果你是负责人，事前应该有哪些机制？事后如何排查和修复？

**Q16.**（场景设计）为一个浏览器 agent（第 11 节）设计每工具上限：哪个工具要最紧的上限？哪个工具可以基本不限？熔断后怎么恢复？

**Q17.**（追问型）除了"设上限"，还有哪些手段能在不牺牲质量的情况下降低 agent 成本？它们和上限的关系是什么？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："the agent keeps reasoning, keeps tool-calling, keeps billing, and nothing stops it because nothing was designed to." Key Terms："Agent loop generating spend with no cap to stop it." C 描述的是 DDoS（拒绝服务），名字相似但主体不同——Denial of Wallet 的"攻击者"往往就是 agent 自己的循环；A、D 与本节无关。

### Q2 — 答案：D

讲义："Runaway loop (agent stuck in a 5-second retry): caught by velocity limit." 失控循环的特点是**短时间内花费速率异常高**，速度限制在分钟级就能发现。A、C 时间尺度太长，等它们触发时钱已经花掉了（讲义："A single monthly cap catches a runaway agent only after the wallet is gone."）；B 是降本手段，不是止损手段。（但要注意 Q9：速度限制的阈值必须按真实速率标定，否则同样不会触发。）

### Q3 — 答案：A

实际输出：`layered stack  turns=  200  tokens=1,440,500  dollars=$   4.32  stopped_by=max_turns`。29 × 2,500 + 171 × 8,000 = 1,440,500 token，× $0.003/千 = $4.32。B 是讲义声称的结果，但实际没有发生（见 Q9）；C、D 的金额远未达到。

### Q4 — 答案：C

10,000 轮共 79,840,500 token、$239.52，远低于 $500；跑满后 `stopped_by` 被设为 "ran out of simulated turns"。按 $0.024/轮，要约 20,853 轮（约 7.2 天的模拟时间）才会达到 $500。A、B 都假设月度上限触发了；D 错，`EPSILON_MIN` 已经防止了除以 0。这也说明代码 HEADLINE 里 "Monthly cap fires late: the wallet is already half-gone" 并不是这次运行展示出来的事实——它根本没触发。

### Q5 — 答案：B

每轮 8,000 / 1,000 × $0.003 = $0.024；每分钟 2 轮 → $0.048/分钟。A 是每**轮**的花费；C、D 分别多乘了 10、100 倍。对比速度限制阈值 $5/分钟，相差约 104 倍——这就是速度限制永远不触发的原因。

### Q6 — 答案：A

讲义："Prevents any one call from emitting an unbounded completion." 它是**单请求**上限，不是会话预算（B 描述的是 `max_budget_usd`）。C 错，`max_tokens` 挡不住多轮循环，迭代上限仍需要。D 错，默认 `max_tokens_per_request = 10_000` 大于 8,000，在默认配置下从未截断；只有把它改成 5,000 时才会截断（实测 200 轮共 927,500 token、$2.78）。

### Q7 — 答案：D

讲义 The Concept 部分："The tool allowed the agent to poll order status during every session. No loop detection. No per-tool cap. No alert on week-over-week growth. The fix was a per-tool cap plus a daily-growth alert." 注意讲义同一段写的是 "monthly cost tripled"，但 $1,200 → $4,800 是**变为 4 倍**（增加了 3 倍），表述不严谨。A 讲义明确说 "That is not a pricing bug"；B 与注入无关；C 恰好是反面——skill 文件说这是"week-over-week growth problem, not a monthly cap problem"。

### Q8 — 答案：C

权限分类器回答"这个动作是否安全/被允许"，预算回答"一共能消耗多少资源"。一个每一步都合法的轮询循环能通过所有权限检查，却会耗尽预算。skill 文件的拒绝规则："If the user treats the Auto Mode classifier as a replacement for budgets, refuse." A、B 都把两者当成可替代；D 无依据。

### Q9 — 参考答案

1. **没有触发**。正常阶段速率 = 2 轮/分钟 × $0.0075 = **$0.015/分钟**，循环阶段 = 2 × $0.024 = **$0.048/分钟**，而阈值是 **$5/分钟**，差约 104 倍。即使按讲义 "5 秒重试" 把 `seconds_per_turn` 改成 5，循环速率也只有 $0.288/分钟（实测仍跑满 10,000 轮）。拦下循环的是 `max_turns=200`。

2. 关掉速度限制（`Governor(enable_velocity=False)`）后结果**完全相同**：200 轮、1,440,500 token、$4.32、`stopped_by=max_turns`（已实测）。因为速度限制本来就没有参与拦截，去掉它不改变任何东西。所以练习 1 的预期（"速度限制先于迭代上限触发"）在这份代码里不成立。

3. 选阈值的思路：阈值必须**高于正常速率并留余量**（防误报），又**低于循环速率**（能抓住）。正常 $0.015、循环 $0.048，取 2 倍正常速率 $0.03/分钟：

   | 阈值 | 触发轮次 | 触发时花费 | 评价 |
   |------|---------|-----------|------|
   | $0.03 | 第 39 轮 | $0.46 | 循环开始后 10 轮（5 分钟）触发，余量充足 |
   | $0.02 | 第 33 轮 | $0.31 | 更快，余量 33% |
   | $0.016 | 第 30 轮 | $0.24 | 最快，但只比正常速率高 7%，真实噪声下会频繁误报 |

   以 $0.03 为例，触发在第 39 轮：此时 10 分钟窗口从第 19 轮开始，窗口内花费 = 10 个正常轮（$0.075）+ 10 个循环轮（$0.24）= $0.315，速率 $0.0315 > $0.03。相比迭代上限的 $4.32，节省约 89%。生产中应基于历史消费分布（如正常速率的 P99）乘以安全系数来定阈值，并区分"告警阈值"和"熔断阈值"。讲义的 "$50 / 10 分钟" 是面向组织级消费规模的例子，不能直接套到单个会话上。

### Q10 — 参考答案

1. **不是**。`run.dollars` 是**单次会话**从 0 开始的累计花费，所以它只是一个阈值为 $500 的会话上限。真正的月度上限要统计同一账户/项目在本月**所有会话**的花费。
2. 每循环轮 $0.024，前 29 轮共 $0.2175；(500 − 0.2175) / 0.024 ≈ 20,824 个循环轮，合计约 20,853 轮 × 30 秒 ≈ **174 小时（约 7.2 天）**。也就是说，单会话循环一周多才会碰到这个"月度上限"。
3. 设计要点：计数必须**持久化且跨会话共享**，并在 agent 进程**之外**（网关、计费服务）执行：

   ```python
   class Ledger:                                   # 存在数据库 / Redis(AOF) / 网关里
       def spent(self, account, period): ...      # period 如 "2026-10" 或 "2026-10-12"
       def add(self, account, period, usd): ...    # 原子累加

   def preflight(account, est_usd, now):
       day, month = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")
       if ledger.spent(account, day) + est_usd > DAILY_CAP:
           raise BudgetExceeded("daily")
       if ledger.spent(account, month) + est_usd > MONTHLY_CAP:
           raise BudgetExceeded("monthly")

   # 每次 LLM / 工具调用前 preflight，调用后 ledger.add(实际花费)
   ```

   放在 harness 或 AI 网关层，所有会话、所有子 agent、所有重试都经过同一个账本；配合第 12 节的持久化存储，进程重启也不会清零。另外要有"日环比 / 周环比增长"告警——讲义案例正是缺了这个。

### Q11 — 参考答案

1. `simulate` 是**先计费、后检查**：第 2,104 轮的 $0.024 先被加进 `run.dollars`，此时累计 $50.02 ≥ $50，才触发 `max_budget_usd`。所有上限都会因此超出最多一轮的花费。单轮便宜时误差可以忽略，但若一轮是一次昂贵调用（长上下文、大模型、大下载），超出可能很可观。

2. 预检改写：

   ```python
   for turn in range(1, 10_001):
       tok = turn_cost(turn)
       if gov.enable_request_cap:
           tok = min(tok, gov.max_tokens_per_request)
       est = (tok / 1000.0) * DOLLARS_PER_KTOK          # 本轮最坏花费
       if gov.enable_session_cap and run.dollars + est > gov.max_budget_usd:
           run.stopped_by = "max_budget_usd (preflight)"
           break                                         # 不执行这一轮
       run.turns = turn
       run.tokens += tok
       run.dollars += est
       ...
   ```

   这样会话花费不会超过上限（停在 $49.99x）。真实系统中"本轮最坏花费"用 `输入 token 数 + max_tokens` 乘以单价估算——这也是 `max_tokens` 与会话预算配合的方式：前者让后者的预检成为可能。

### Q12 — 参考答案

1. 点估计：50 × 12 × 6,000 = 3,600,000 token，× $3 / 百万 = **$10.8**；2 倍为 **$21.6**（已用 Python 计算）。
   - **为什么不是 1.1 倍**：点估计本身有误差——issue 难度分布有长尾，个别 issue 可能需要 3–5 倍的轮数；上下文随对话增长，后期每轮 token 往往比早期多。1.1 倍会让正常运行频繁被误杀，夜间没人重新启用，任务就半途而废。
   - **为什么不是 10 倍**：上限的意义是把"最坏情况的损失"限定在可接受范围内。10 倍意味着一个失控循环可以花掉 $108 才被拦住，而且上限太宽松时也失去了"异常信号"的作用。skill 文件："If the proposed budget exceeds the organization's acceptable loss on a single mistake, refuse and require a lower cap."
   - 2 倍是"容纳正常波动"与"限制最坏损失"之间的折中；更好的做法是用历史运行数据估计花费分布，取 P95–P99 作为上限。
2. 其他上限：每个 issue 的轮数上限（如 30 轮，防止卡在单个 issue 上）；会话 `max_turns`（如 50 × 30）；每工具上限（如每个 issue 最多读 20 个文件、最多 5 次搜索，写评论/改标签等写操作最多若干次）；速度限制（按正常速率的 2 倍左右）；写操作（关闭 issue、打标签）的 `allowed_tools` 限定；熔断后发送通知、早上人工确认再继续。

### Q13 — 参考回答要点

- **为什么不能只靠月度预算**：它太慢——讲义："A single monthly cap catches a runaway agent only after the wallet is gone." 单请求上限又太细，抓不住会话级问题。
- **按时间尺度分层**（讲义四种失效模式）：
  - 秒/分钟级：每请求 `max_tokens`、速度限制（如 $X / 10 分钟）→ 抓**失控循环**；
  - 会话级：`max_turns`、`max_budget_usd`、每工具上限 → 限制**单次运行**的最坏损失；
  - 小时/日级：滚动上限 + 日增长告警 → 抓**慢泄漏**（每个任务多做约 2 倍工作）和**正常激增**（真实需求，靠清晰日志区分）；
  - 周/月级：周/月上限 + 周环比告警 → 抓**坏版本**（新版本 token 用量 5 倍）。
- 再加上：熔断记录在案、需要单独的重新启用路径；上限在 agent 无法修改的地方执行。
- 加分点：区分"告警阈值"（通知人）和"熔断阈值"（直接停）。

### Q14 — 参考回答要点

- **实现**：保存 `(时间, 累计花费)` 序列，每次调用后取窗口起点 `now − W`，窗口花费 = 当前累计 − 窗口起点累计，速率 = 窗口花费 / 实际经过时间，超过阈值即熔断。本节 `velocity_exceeded` 就是这个实现。
- **窗口**：太短（如 1 分钟）对单次昂贵调用过敏；太长（如 1 小时）抓循环太慢。讲义例子是 10 分钟。可以多窗口并用。
- **分母**：用实际经过时间而不是名义窗口宽度，否则启动阶段会低估速率（代码注释说明了这一点）；但启动阶段样本少时又容易被一两次昂贵调用误触发，可以要求最少样本数。
- **聚合范围**：只在单会话内计算，会被并发会话、子 agent、重试绕过；生产应在账户/项目/API key 级别聚合，放在网关或计费服务里。
- **数据结构**：用双端队列丢弃过期记录，O(1) 摊销；本节代码每次遍历全历史是 O(n)。
- **阈值**：以正常运行的速率分布为基线（如 P99），乘以安全系数（2 倍左右）；不能拍脑袋——本节代码的 $5/分钟比循环速率高约 104 倍，永远不会触发。
- 加分点：说明速度限制熔断后要通知人、保留现场，并且重新启用需要人工确认。

### Q15 — 参考回答要点

- **事前机制**：
  - 新工具上线 = 新的潜在循环：必须带每会话调用上限和独立的消费告警（讲义："every new tool needs its own cap and its own alert"；skill 文件：上线不足 30 天的工具没有每工具上限是 hard reject）；
  - 灰度发布新工具，对比实验组与对照组每会话的 token 和工具调用次数；
  - 日环比 / 周环比增长告警（讲义的修复之一就是 daily-growth alert）；
  - 会话级 `max_budget_usd`、`max_turns` 和速度限制兜底。
- **事后排查**：按工具、按会话类型拆分成本（FinOps 的成本归因），找到增长集中在哪个工具；看 trace 中该工具的调用模式（是否每轮都调、是否重复相同参数）；确认是 bug（循环）还是正常需求增长。
- **修复**：每工具上限（如每会话最多查询 3 次订单状态）、对相同参数的调用做缓存或去重、在 prompt/工具描述中说明何时需要调用、加循环检测（连续 N 次相同工具 + 相同参数即中止）。
- 常见误区：只调高月度预算；只看总账单不做按工具归因。

### Q16 — 参考回答要点

- **最紧的上限**：有副作用且不可逆或花钱的工具——提交表单/下单/支付、发帖/发消息、写持久记忆。例如每会话最多 1 次提交、0 次未经 HITL 的支付；写记忆每会话最多 1–2 条且需审计。理由：这些动作的成本不只是 token，还有现实世界的后果（结合第 11 节注入风险，它们也是攻击者最想触发的动作）。
- **较紧的上限**：页面抓取/导航（每会话如 50 次）、截图（图像 token 昂贵）、大文件下载（按字节计）。
- **基本可以不限（但仍要计入总预算）**：纯本地、无副作用、几乎无成本的操作，如在已加载页面中查找文本、滚动。注意"不限次数"不等于"不计费"，它们仍然消耗 LLM 轮次，受 `max_turns` 和会话预算约束。
- **熔断后的恢复**：熔断即中止会话、保存现场（trace、已完成步骤，可借助第 12 节的持久化）、通知负责人；重新启用需要人工确认原因（bug 还是正常需求），必要时调整上限；agent 自己无权修改上限或重新启用（skill 文件：kill switch 必须在 agent 外部）。

### Q17 — 参考回答要点

- 讲义列出的降本手段：
  - **分级模型路由**：默认小模型，只有分类器判断需要时才升级到大模型；
  - **prompt caching**：系统提示和稳定上下文放在提供方缓存中，重复发送的成本大幅降低（讲义说 "near zero"；实际上缓存命中通常是按折扣价计费而非完全免费，首次写入缓存还可能有额外费用，需按提供方定价核算）；
  - **上下文压缩 / 窗口化**：摘要、裁剪，保持活跃上下文低于阈值，直接降低每轮 token；
  - **昂贵动作前的 HITL**：在大模型升级、大下载、长工具调用前请人确认。
- 还可以补充：工具结果缓存与去重、批处理 API（非实时任务）、减少不必要的工具描述。
- **与上限的关系**：降本手段降低**正常情况**下的花费（把曲线压低），上限限制**异常情况**下的最大损失（给曲线封顶）。两者互补：只降本不设上限，循环依旧会烧钱；只设上限不降本，正常任务会频繁撞上限。另外，降本后正常速率下降，速度限制阈值也要随之重新标定。
- 常见误区：上了缓存就以为不需要预算；分级路由的分类器本身也有成本和误判，需要评估。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 10 自主 Agents 的权限模式](../../10-claude-code-permission-modes/docs/zh.md)：预算与权限模式正交，Auto Mode 必须配预算。
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../12-durable-execution/docs/zh.md)：持久化让长任务成为可能，也让"无上限地跑下去"成为风险。
- [阶段 11 · 11 缓存、请求速率限制与成本优化](../../../11-llm-engineering/11-caching-cost/docs/zh.md)：缓存与限流的基础。
- [阶段 15 · 11 浏览器 Agents 与长程网页任务](../../11-browser-agents/docs/zh.md)：练习 2 的每工具上限设计对象。

### 本节被哪些后续内容用到
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../14-kill-switches-canaries/docs/zh.md)：预算超限是熔断器的一种触发条件。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../15-propose-then-commit/docs/zh.md)：昂贵动作前的 HITL。
- [阶段 17 · 14 Prompt 缓存与语义缓存的经济性](../../../17-infrastructure-and-production/14-prompt-semantic-caching/docs/zh.md)：prompt caching 的成本核算。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../../17-infrastructure-and-production/16-model-routing/docs/zh.md)：分级模型路由。
- [阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../../17-infrastructure-and-production/19-ai-gateways/docs/zh.md)：在网关层跨会话执行预算与限流。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../../17-infrastructure-and-production/27-finops-llms/docs/zh.md)：按工具/租户做成本归因。
- [阶段 19 · 25 综合项目第 25 课：Verification Gates 与观察预算](../../../19-capstone-projects/25-verification-gates-observation-budget/docs/zh.md)：在综合项目中实现预算控制。

### 延伸关键词
`Denial of Wallet` · `max_tokens` · `max_turns` · `max_budget_usd` · `velocity limit` · `rolling window` · `per-tool cap` · `tiered model routing` · `prompt caching` · `context compaction` · `kill switch` · `FinOps` · `cost attribution` · `week-over-week alert` · `OWASP Agentic Top 10` · `EU AI Act Article 14`
