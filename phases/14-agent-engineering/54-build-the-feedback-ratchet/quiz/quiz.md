# 测验 · 建立持续反馈机制，明确负责人和退役条件（Build a Feedback Ratchet with Ownership and Retirement）

> **阶段 14 · Agent 工程 · 第 54 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：本节中文讲义为机器翻译，误译较多：ratchet（棘轮）被译成"鼠标 / 告密 / 招手 / 扳机"，promotion 译成"宣传"，artifact 译成"文物"，"An unowned improvement" 译成"一种未加控制的改进"（应为"无人负责的改进"），"Retire Stale Controls" 译成"退役定额控制"（应为"退役过时的控制"），"Do not add another prompt paragraph when a test or permission can make the failure impossible" 一句被译乱。本测验以英文原文为准。ratchet 的含义是"只进不退的棘轮"：每一次被验证的改进都被固定下来，不会悄悄回退。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 反馈是基础设施 | 收集 trace、eval、工单、事故日志不等于学习；缺的是 promotion（晋升）：从观察到"有负责人、有证明的持久变更"的明确路径 |
| 2 | 六步循环 | 观察具体信号 → 关联到 outcome / 约束 / 假设 → 找到拥有原因的最早系统层 → 做有界变更 → 验证复发变少 → 复审控制是否该保留 |
| 3 | 路由到拥有层 | 误报/回归/错误结果 → evaluation；缺上下文/重复工作/过时事实 → context；不安全动作/权限缺口 → policy；超时/重试风暴/依赖不可用 → runtime；新需求/未决权衡 → backlog |
| 4 | 最早有效层 | 能用测试或权限让失败"不可能发生"时，不要再加一段 prompt |
| 5 | ownership 是控制的一部分 | 每个 ratchet action 需要：一个负责人、基于后果与复发的优先级、要改的 artifact、证明变更的验证、复审/到期窗口、退役条件 |
| 6 | 无人负责的改进 | "An unowned improvement is an observation with better formatting." |
| 7 | 退役过时控制 | 触发复审：架构/流程变化；低层不变量取代了高层指令；被保护的失败在窗口内没出现；控制阻碍合法工作多于防止伤害 |
| 8 | 退役也要证据 | 不能因为"感觉旧了"就删除控制 |
| 9 | 两条轨道共用一个棘轮 | 产品证据改变结果框架、假设、切片或测量计划；coding-agent 纠正改变测试、上下文、范围、自动化或 handoff；事故可能两者都改 |
| 10 | 代码的实现 | 关键词路由（有先后顺序）、优先级 = severity × frequency、按优先级降序再按目标层名字排序、退役条件只是"N 天无复发" |

### 核心技能（能动手做到）

- [ ] 把一次事故和一条用户投诉各转成一个 ratchet action，写全负责人、artifact、验证、到期与退役条件
- [ ] 对任意信号说出"最早能阻止复发的层"，并解释为什么不是加 prompt
- [ ] 手算本节示例的优先级与排序结果，解释同分时的次序
- [ ] 找出关键词路由的误判（顺序依赖、子串匹配、缺"stale"），并提出更可靠的路由方式
- [ ] 评估 `severity × frequency` 的排序是否合理，为高严重度低频的安全问题设计优先级规则
- [ ] 写一个基于证据的控制复审函数，输出 keep / revise / retire

---

## 二、基础自测（选择题）

**Q1.** 按讲义，反馈什么时候才算"基础设施"？

- A. 被汇总成周报时
- B. 出现在仪表盘上时
- C. 有一条通往"有负责人、可验证的持久变更"的路径时
- D. 被采集进日志系统时

**Q2.** 用本节代码的 `destination` 路由观察文本 `"retry storm caused duplicate writes"`，结果是：

- A. `"context"`
- B. `"runtime"`
- C. `"policy"`
- D. `"backlog"`

**Q3.** 运行本节 `main`，`outputs/feedback-backlog.json` 中三个 action 的目标层顺序是：

- A. policy → context → evaluation
- B. evaluation → context → policy
- C. context → policy → evaluation
- D. context → evaluation → policy

**Q4.** 上题中前两个 action 的优先级都是 12，为什么 context 排在 evaluation 前面？

- A. 因为 context 信号的严重度更高
- B. 因为排序键 `(-priority, destination, change)` 在优先级相同时按目标层名称字母序，`"context" < "evaluation"`
- C. 因为它在 `example()` 中排第一，排序是稳定的
- D. 因为 context 的 `expires_after_days` 更长

**Q5.** 下列哪一项**不是**讲义列出的、应当复审（可能退役）控制的理由？

- A. 架构或工作流发生了变化
- B. 一个更低层的不变量取代了高层的指令
- C. 该控制阻碍合法工作的次数多于它防止伤害的次数
- D. 该控制已经存在很久，感觉过时了

**Q6.** 执行 `promote(Signal("x", "y", 3.0, 1, "owner", 30))`（严重度是浮点数 3.0），结果是：

- A. 正常返回 action，`priority` 为 `3.0`
- B. 抛出 `ValueError`，因为 `3.0` 不是整数
- C. 正常返回 action，`priority` 为整数 `3`
- D. 抛出 `TypeError`

**Q7.** 一个 coding agent 多次在没有授权的情况下尝试写生产数据库。按讲义"最早有效层"原则，最合适的修复是：

- A. 在系统 prompt 中再加一段"请不要写生产数据库"
- B. 在周报中提醒团队注意
- C. 在权限边界上收回生产写权限，并加一个"尝试写入被拒绝"的场景测试
- D. 提高模型的 temperature 以减少重复行为

**Q8.** 执行 `promote(Signal("incident 9", "unsafe deploy", 4, 2, "", -5))`（owner 为空、到期天数为负），结果是：

- A. 抛出 `ValueError`，因为 owner 为空
- B. 正常返回 action：`owner` 为空字符串，`retirement_check` 为 `"Remove or revise after -5 days without recurrence"`
- C. 抛出 `ValueError`，因为到期天数为负
- D. 返回 `None`

---

## 三、动手 / 代码题

**Q9.** 阅读 `destination`：

```python
def destination(signal: Signal) -> str:
    text = signal.observation.lower()
    if any(word in text for word in ("regression", "wrong result", "false positive")):
        return "evaluation"
    if any(word in text for word in ("permission", "unsafe", "production write")):
        return "policy"
    if any(word in text for word in ("missing context", "could not find", "duplicate")):
        return "context"
    if any(word in text for word in ("timeout", "retry", "unavailable")):
        return "runtime"
    return "backlog"
```

1. 写出下列观察的路由结果，并判断是否合理：`"timeout caused wrong result"`、`"retry storm caused duplicate writes"`、`"stale fact about service owner"`、`"nonduplicated"`。
2. 只调整关键词顺序能根治问题吗？给出更可靠的改法。

**Q10.** 优先级 `priority = severity × frequency`。示例中三个信号为：

| 信号 | severity | frequency |
|------|----------|-----------|
| missing context caused duplicate service lookup | 4 | 3 |
| production write was attempted | 5 | 1 |
| false positive on a stale deployment | 3 | 4 |

1. 算出优先级与排序。生产写入尝试排在最后，你认为合理吗？
2. 比较三种替代方案的排序：`severity² × frequency`、按 `(severity, frequency)` 字典序、"severity = 5 一律置顶，其余按乘积"。

**Q11.** 讲义说每个 ratchet action 都需要"one owner"和"a review or expiry window"。找出 `promote` 的输入校验漏洞（至少四个），并写出 `validate_signal`。

**Q12.** 讲义列出四种复审控制的情形，并强调"Retirement also needs evidence"。代码的退役条件只是一句 `"Remove or revise after N days without recurrence"`。请写一个 `review_control(...)`，根据证据返回 `"keep" / "revise" / "retire" / "review-for-retirement"`，并说明每个分支对应讲义的哪条理由。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 feedback ratchet（反馈棘轮）？它和"收集日志、做仪表盘"有什么区别？

**Q14.**（原理深挖）为什么讲义强调"在最早有效层修复原因"，而不是在 prompt 里补一句？请分别举 evaluation、context、policy、runtime 层的例子。

**Q15.**（工程实践）你的 agent 系统运行一年后，system prompt 已有 300 条规则，互相矛盾、成本高。你会怎么治理？

**Q16.**（场景设计）用户投诉"agent 把上周已经下线的服务当成故障源"，同时事故复盘发现"依赖的 CMDB 接口超时后 agent 用了缓存的旧数据"。请把它们转成 ratchet actions（层、artifact、验证、负责人、到期与退役条件）。

**Q17.**（追问型）用 `severity × frequency` 排优先级有什么问题？如果让你设计反馈 backlog 的优先级规则，你会怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："The missing mechanism is promotion: a defined path from observation to a durable change with an owner and proof." 以及开篇："Evidence must change the system or it becomes telemetry nobody owns."

- A、B、D 都只是"收集与展示"。讲义："A team can collect traces, evaluations, support tickets, and incident logs without learning from any of them."

### Q2 — 答案：A

实测返回 `"context"`。文本不含 evaluation 与 policy 的关键词；进入第三个判断时，`"duplicate"` 命中，直接返回 context——runtime 的 `"retry"` 根本没有机会被检查。根因明明是重试风暴（runtime 层），却被路由到上下文层。这是**关键词顺序依赖**的典型误判（见 Q9）。

- B 是"合理"的答案，但不是代码的实际输出。
- C、D 错：没有 policy 关键词；有关键词命中就不会落到 backlog。

### Q3 — 答案：D

实测输出顺序：context（12）→ evaluation（12）→ policy（5）。优先级分别为 `4×3=12`、`3×4=12`、`5×1=5`。

- A 是"按严重度"的直觉顺序，但代码按乘积排序。
- B、C 与同分时的排序规则不符（见 Q4）。

### Q4 — 答案：B

`sorted(actions, key=lambda item: (-item.priority, item.destination, item.change))`：先按 `-priority` 升序（即优先级降序），同分时按 `destination` 字符串升序。`"context" < "evaluation"`（c 在 e 前）。

- A 错：严重度 4 vs 3 确实更高，但排序键里没有严重度。
- C 错：键的第二项已经决定了顺序，与输入顺序无关（稳定性只在键完全相同时才起作用）。
- D 错：`expires_after_days` 不在排序键中。

### Q5 — 答案：D

讲义四条复审理由是 A、B、C 加上"被保护的失败在选定窗口内没有出现"；同时明确："Retirement also needs evidence. Do not delete a control because it feels old." D 正是被否定的做法。

### Q6 — 答案：A

`signal.severity not in range(1, 6)`：Python 中 `3.0 in range(1, 6)` 为 `True`（range 的成员测试对等值的浮点数也成立），所以通过校验；`priority = 3.0 * 1 = 3.0`。实测返回 `priority 3.0`。同理 `True` 也能通过（`True == 1`），`frequency = 1.5` 也能通过（只检查 `< 1`）。而 `2.5` 会被拒绝。

- B 错：校验并不检查类型。
- C 错：乘积保留浮点类型。
- D 错：没有类型错误。

### Q7 — 答案：C

讲义："Fix the cause at the earliest effective layer. Do not add another prompt paragraph when a test or permission can make the failure impossible." 收回权限让失败**不可能发生**，场景测试让回归可检测；本节代码也把含 `"production write"` 的信号路由到 policy，artifact 是 `policies/authority-boundaries.json`，验证是"Record a passing authority-boundary scenario"。

- A 是讲义明确反对的做法：prompt 只能"劝"，不能"禁"。
- B 没有改变系统。
- D 与问题无关。

### Q8 — 答案：B

实测：正常返回，`owner == ""`，`retirement_check == "Remove or revise after -5 days without recurrence"`。`promote` 只校验 severity 与 frequency，不校验 owner 与到期天数。这与讲义"Every ratchet action needs one owner"直接冲突——正是"An unowned improvement is an observation with better formatting"。另外 `"unsafe deploy"` 命中 `"unsafe"`，路由到 policy。

### Q9 — 参考答案

1. 实测结果：

| 观察 | 代码路由 | 合理路由 | 问题 |
|------|---------|---------|------|
| `timeout caused wrong result` | evaluation | runtime | 症状（错误结果）先于根因（超时）被匹配 |
| `retry storm caused duplicate writes` | context | runtime | `"duplicate"` 抢先命中 |
| `stale fact about service owner` | backlog | context | 讲义表格的"stale fact"没进关键词表 |
| `nonduplicated` | context | 视情况 | 子串匹配，`"duplicate"` 出现在单词内部也会命中 |

2. **只调顺序不能根治**。实测把顺序改成 policy → runtime → context → evaluation、加上 `"stale"` 和单词边界正则 `\b...\b` 后：前三条都变对了，`nonduplicated` 不再误判；但原本正确的 `"false positive on a stale deployment"` 变成了 context（`"stale"` 命中先于 `"false positive"`），本节测试 `test_false_positive_routes_to_evaluation` 会失败。关键词顺序只是把误判从一类挪到另一类。

更可靠的改法：
- **把"根因"作为显式字段**：`Signal` 增加 `cause`（或直接 `owning_layer`），由复盘时人工确定；讲义循环第 3 步就是"identify the earliest system layer that owns the cause"——这是判断，不是字符串匹配。第 46 节的代码就同时使用了 symptom 和 cause 两个字段。
- 关键词路由只做**建议**，在置信度低（命中多个层、或一个都没命中）时标记为"需要人工分诊"，而不是静默选第一个。
- 若保留关键词：只匹配 `cause` 字段、使用单词边界、按"安全优先"排列（policy 最先），并为每条规则配回归测试。

### Q10 — 参考答案

1. 优先级：context 12、evaluation 12、policy 5，排序 context → evaluation → policy。生产写入尝试排最后**不合理**：它是越权、可能不可逆的安全事件，一次就足以造成严重后果。乘积让"低严重度高频"的问题压过"高严重度低频"的问题。讲义说优先级要"based on consequence and recurrence"，但后果不应该能被频率线性抵消。

2. 实测三种替代方案：

| 方案 | 分值 | 排序 |
|------|------|------|
| `severity² × frequency` | context 48、evaluation 36、policy 25 | context → evaluation → policy（仍然最后） |
| `(severity, frequency)` 字典序 | — | policy → context → evaluation |
| severity = 5 置顶，其余按乘积 | — | policy → context → evaluation |

平方只是减弱了频率的影响，不能改变结论；字典序或"严重度门槛置顶"才能保证安全事件优先。实践中更常见的是**分级**：先按严重度分档（如 S1 必须立即处理、有 SLA），档内再按频率或乘积排序。

### Q11 — 参考答案

已实测的漏洞：

| 输入 | 结果 | 问题 |
|------|------|------|
| `severity=3.0` | 通过，priority 3.0 | 浮点数被接受 |
| `severity=True` | 通过，priority 1 | `bool` 被当成 1 |
| `frequency=1.5` | 通过，priority 4.5（severity 3） | 只检查 `< 1`，不检查整数 |
| `owner=""` | 通过 | 讲义要求"one owner" |
| `expires_after_days=-5` | 通过 | 退役条件变成"-5 天无复发"，没有意义 |
| `observation=""` | 通过，路由到 backlog | 没有可行动的内容 |

参考实现（已运行验证：对 `severity=3.0, owner=" ", expires=-5` 报出三条问题，示例信号返回 `[]`）：

```python
def validate_signal(s: Signal) -> list[str]:
    issues = []
    if isinstance(s.severity, bool) or not isinstance(s.severity, int) or not 1 <= s.severity <= 5:
        issues.append("severity must be an integer from one to five")
    if isinstance(s.frequency, bool) or not isinstance(s.frequency, int) or s.frequency < 1:
        issues.append("frequency must be a positive integer")
    if not s.owner.strip():
        issues.append("owner is required")
    if isinstance(s.expires_after_days, bool) or not isinstance(s.expires_after_days, int) \
            or s.expires_after_days < 1:
        issues.append("expires_after_days must be positive")
    if not s.observation.strip():
        issues.append("observation is required")
    return issues
```

`promote` 中改为：`issues = validate_signal(signal); if issues: raise ValueError("; ".join(issues))`。

### Q12 — 参考答案

参考实现（已运行验证四个分支）：

```python
def review_control(days_without_recurrence: int, window_days: int, superseded: bool,
                   blocked_legit: int, prevented_harm: int, architecture_changed: bool) -> str:
    if superseded:                        # 更低层的不变量已取代该控制
        return "retire"
    if blocked_legit > prevented_harm:    # 阻碍合法工作多于防止伤害
        return "revise"
    if architecture_changed:              # 架构或工作流变化，控制可能失效或错位
        return "revise"
    if days_without_recurrence >= window_days:   # 窗口内未复发：进入退役评审，而不是直接删除
        return "review-for-retirement"
    return "keep"
```

实测：`(100, 90, False, 0, 0, False)` → `review-for-retirement`；`(10, 90, False, 5, 1, False)` → `revise`；`(10, 90, True, 0, 0, False)` → `retire`；`(10, 90, False, 0, 3, False)` → `keep`。

要点：
- "N 天无复发"只进入**评审**而不直接退役——没有复发可能正是因为控制在起作用。退役前可以先降级为"只告警不阻断"观察一段时间，这本身就是退役的证据。
- 每个分支都需要数据来源：`blocked_legit` / `prevented_harm` 来自控制的触发日志与人工复核；`superseded` 来自变更记录（例如权限层已禁止该操作，prompt 中对应的规则就可以退役）。
- 结论要写回 backlog，并有负责人签署——退役本身也是一个 ratchet action。

### Q13 — 参考回答要点

- **定义**：把每一个信号（事故、eval 失败、用户行为、纠正）晋升为"有负责人、有 artifact、有验证、有到期与退役条件"的持久系统变更，并在下一次运行中验证。像棘轮一样只进不退：被验证的改进被固定下来。
- **与日志/仪表盘的区别**：日志和仪表盘是"观察"；棘轮是"观察 → 归因到最早有效层 → 有界变更 → 验证 → 复审"的闭环。讲义："An unowned improvement is an observation with better formatting."
- **关键要素**：负责人、基于后果和复发的优先级、要改的 artifact、验证证据、复审窗口、退役条件。
- 加分点：说明它连接产品轨道与 coding-agent 轨道（产品证据改结果框架与测量计划；agent 纠正改测试、上下文、范围、自动化、handoff）；"塑造构建"不是编码前就结束的阶段。

### Q14 — 参考回答要点

- **为什么不是 prompt**：prompt 是概率性的劝告，模型可能忽略；规则越积越多会互相矛盾、增加成本。测试、权限、运行时控制是确定性的，能让失败"不可能发生"或"一定被发现"。
- **各层例子**：
  - evaluation：误报 → 把这次失败加入回归评测集，以后每次改动都会跑到；
  - context：agent 找不到 runbook、重复查同一服务 → 修检索路由或把信息放进上下文源；
  - policy：尝试写生产 → 收回写权限、加授权边界场景测试；
  - runtime：依赖超时引发重试风暴 → 设置超时预算、指数退避与熔断。
- **"最早"的含义**：离根因最近、最能阻止复发的层。例如"缓存旧数据导致错误结论"，根因在 runtime/context（数据新鲜度），而不是在 evaluation 层多加一条检测。
- 加分点：提到第 46 节"纠正晋升为测试 / 边界 / 例子 / 工具"与本节同一思路。

### Q15 — 参考回答要点

- **盘点**：为每条规则补齐元数据——来源信号、负责人、目的（防什么失败）、添加时间、最近一次触发时间。找不到来源和负责人的规则先标记待审。
- **下沉**：能被更低层保证的规则移到测试、权限、运行时控制或工具中，然后从 prompt 中删除（讲义："a lower-level invariant replaces a higher-level instruction"）。
- **证据驱动退役**：统计每条规则对应失败在窗口内是否复发；对"阻碍合法工作多于防止伤害"的规则做修订；退役前可在评测集上做 A/B（带与不带该规则）验证。
- **防止再膨胀**：新增规则必须走 ratchet 流程（负责人、验证、到期窗口、退役条件）；定期复审。
- 常见误区：一次性大删（没有证据）或只增不删。
- 加分点：给出度量——prompt token 数、规则冲突数、评测通过率随时间的变化。

### Q16 — 参考回答要点

| 信号 | 最早有效层 | artifact | 验证 | 负责人 | 到期 / 退役 |
|------|-----------|----------|------|--------|------------|
| 把已下线服务当故障源（用户投诉） | context：服务目录中缺少"下线"状态，属于 stale fact | 检索路由：查询服务时过滤 `status = decommissioned`；context 源中补充下线记录 | replay 该事故，确认已下线服务不再出现在候选中；加入回归 eval | 平台团队 | 90 天复审；若服务目录本身在 API 层过滤了下线服务（低层不变量取代），则退役该检索规则 |
| CMDB 超时后使用缓存旧数据（复盘） | runtime：超时后的降级策略不当 | 运行时配置：超时预算、重试上限；缓存数据必须带时间戳，超过阈值标记为"可能过时"并降低置信度 | 故障注入场景：模拟 CMDB 超时，确认输出带"数据可能过时"标记且不给确定结论 | 可靠性团队 | 60 天复审；若 CMDB 迁移到高可用接口（架构变化），重新评估 |

- 两个信号可能是同一根因的两个症状：先做关联分析，避免两个团队各改一处却没修根因。
- 加分点：说明为什么不在 prompt 里写"不要使用过时数据"——agent 无法判断数据是否过时，除非运行时把新鲜度信息提供给它。

### Q17 — 参考回答要点

- **问题**：
  1. 严重度与频率可以线性互换：5×1 = 5 < 3×4 = 12，一次越权写入排在多次误报之后（本节示例正是如此）。
  2. 严重度和频率都是粗略的序数，相乘没有明确含义。
  3. 没有考虑修复成本、可逆性、暴露人群、是否有临时缓解措施。
  4. 同分时按层名字母序，与业务无关。
- **改进设计**：
  - 先按严重度**分档**（S1 安全/合规事件立即处理并有 SLA，不参与排序竞争）；
  - 档内按"预期损失 / 修复成本"或"频率 × 影响人数"排序；
  - 引入时间衰减与升级规则：长时间未处理的项自动升档；
  - 同分时按"最早有效层的修复成本"或"是否已有临时缓解"排序；
  - 规则本身也要事前写好并评审（与第 52 节"先定规则再看结果"一致）。
- 加分点：给出本节示例在"严重度置顶"规则下的结果：policy → context → evaluation。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 46 把每一次对 Agent 的纠正转化为系统改进](../../46-turn-feedback-into-system/docs/zh.md)：coding-agent 纠正的晋升机制，本节把它推广到产品信号。
- [阶段 14 · 53 有意识地选择原型、试点或生产方案](../../53-prototype-pilot-or-production/docs/zh.md)：生产阶段的持续监控与退役路径是棘轮的信号来源。
- [阶段 14 · 52 在结果产生前设计成功指标](../../52-design-success-metrics/docs/zh.md)：信号要关联到 outcome、guardrail 与 counter-metric。
- [阶段 14 · 37 运行时反馈循环](../../37-runtime-feedback-loops/docs/zh.md)：运行时层的反馈与控制。
- [阶段 14 · 26 失效模式：Agents 为什么会失败](../../26-failure-modes-agentic/docs/zh.md)：把失败归类到正确的层。

### 本节被哪些后续内容用到
- [阶段 14 · 47 先定义预期成效，再选择交付形式](../../47-outcomes-before-output/docs/zh.md)：讲义说 feedback backlog 是"the input to the next outcome frame"，循环回到结果框架。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：evaluation 层的 artifact（回归评测集）如何持续维护。
- [阶段 17 · 23 AI 的 SRE](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：事故复盘与运行时控制。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：信号的采集来源。
- [阶段 19 · 11 LLM Observability 与评估仪表盘](../../../19-capstone-projects/11-llm-observability-dashboard/docs/zh.md)：在综合项目中把信号、评测与反馈串起来。

### 延伸关键词
`feedback ratchet` · `promotion` · `owning layer` · `earliest effective layer` · `durable artifact` · `regression eval` · `authority boundary` · `retry storm` · `control retirement` · `postmortem` · `severity tiers` · `continuous experimentation`
