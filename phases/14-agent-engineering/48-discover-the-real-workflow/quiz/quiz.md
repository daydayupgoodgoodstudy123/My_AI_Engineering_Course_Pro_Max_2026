# 测验 · 发现人们实际执行的工作流（Discover the Workflow People Actually Perform）

> **阶段 14 · Agent 工程 · 第 48 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 需求不是"收集"来的 | 讲义："Requirements are not waiting in a meeting to be collected"——它们散落在动作、变通办法、记录和分歧里 |
| 2 | 先重建现状，不问想要什么功能 | 对每一步记录 Actor、Trigger、Action、Input、Output、Friction、Authority、Evidence 八个字段 |
| 3 | 工作流大于屏幕 | 包括等待、复制粘贴、旁路沟通、审批、错误恢复，以及人们已经习以为常、不再注意的步骤 |
| 4 | 证据阶梯 | 直接行为（观察、trace、录屏、系统事件）> 工件（工单、runbook、日志、表单）> 报告的行为（当事人自述）> 推断（团队猜测）；讲义说只有前两级能直接证明当前行为 |
| 5 | 防止置信度静默膨胀 | 四级证据都有用，但后两级必须标注，否则"有人说过"会悄悄变成"需求" |
| 6 | 找四样东西 | Friction（重复劳动、延迟、重录、恢复）、Hidden state（记在脑子、聊天、私人笔记里的事实）、Authority（谁有权做有后果的改动）、Exceptions（常规流程不再常规的情况） |
| 7 | AI 功能常败在 handoff 和异常 | 因为只有 happy path 被认真设计过 |
| 8 | 不要把分歧平均掉 | 不同流程可能代表不同角色、风险等级、新旧流程、专长差异或真正的政策分歧；"平均出来的工作流描述不了任何人" |
| 9 | 代码的审计逻辑 | 顺序必须是从 1 开始的连续整数、每步至少一条证据、置信度在 [0, 1]；`direct_evidence_ratio` = 直接证据条数 / 证据总条数；至少一条直接证据即可 `grounded` |
| 10 | 代码的简化 | `direct` 只是布尔值，表达不了四级阶梯；比例按"证据条数"而非"步骤"计；没有 trigger/input/output/authority 字段；无法表达异常分支 |

### 核心技能（能动手做到）

- [ ] 为一个真实流程写出每一步的八个字段，并标出 handoff、隐藏状态、权限边界和异常
- [ ] 给每条证据贴上"直接 / 工件 / 报告 / 推断"标签，并说明哪些步骤仍缺直接证据
- [ ] 读懂 `audit` 的四项检查，能手算任意输入的 `status`、`issues` 和 `direct_evidence_ratio`
- [ ] 指出"按证据条数算比例"和"一条直接证据即 grounded"会怎样让置信度膨胀，并改成按步骤统计
- [ ] 为工作流加一条异常分支（讲义 Build It：部署记录缺失），且不破坏主路径的顺序校验
- [ ] 遇到两种流程变体时，能先判断差异来源（角色 / 风险 / 新旧 / 专长 / 政策），而不是合并成一个

---

## 二、基础自测（选择题）

**Q1.** 按讲义的证据阶梯，从强到弱的正确顺序是：

- A. 报告的行为 > 直接行为 > 工件 > 推断
- B. 直接行为 > 工件 > 报告的行为 > 推断
- C. 工件 > 直接行为 > 推断 > 报告的行为
- D. 推断 > 报告的行为 > 工件 > 直接行为

**Q2.** "值班工程师记在自己笔记里的'哪个服务归哪个组'对照表"属于讲义"四样东西"中的哪一类？

- A. Friction
- B. Authority
- C. Exceptions
- D. Hidden state

**Q3.** 运行本节代码，示例工作流的 `direct_evidence_ratio` 是：

- A. 0.67
- B. 0.5
- C. 0.88
- D. 1.0

**Q4.** 一个 10 步的工作流：第 1 步有一条直接证据（`direct=True, confidence=0.9`），第 2–10 步各只有一条团队推断（`direct=False, confidence=0.3`），顺序为 1–10。`audit` 的结果是：

- A. `needs-evidence`，因为直接证据比例低于 0.5
- B. `needs-evidence`，因为有证据置信度低于 0.5
- C. `grounded`，`direct_evidence_ratio = 0.1`
- D. 抛出异常

**Q5.** 两位值班工程师处理同类告警的步骤不同：一位先查部署记录，另一位先看仪表盘。讲义建议：

- A. 先保留两个变体，弄清它们代表的是角色、风险等级、新旧流程、专长差异还是政策分歧
- B. 把两者合并成一个平均流程，便于设计功能
- C. 只采用更资深那位的流程
- D. 按多数人的做法定稿

**Q6.** 三个步骤的 `order` 依次为 `[1, 3, 2]`（每步都有合法证据）。`audit` 会：

- A. 不报问题，因为 {1, 2, 3} 是连续的
- B. 报 `"step 3 has no evidence"`
- C. 自动按 order 排序后再检查，不报问题
- D. 报 `"workflow order must be contiguous from one"`

**Q7.** 示例第 3 步的证据来源是 `"runbook"`，代码把它标成 `direct=False`。对照讲义的证据阶梯，下列说法最准确的是：

- A. runbook 属于"推断"，标 `False` 与讲义完全一致
- B. runbook 属于"工件"，讲义说前两级都能直接证明当前行为，因此按讲义字面应计为直接；代码的布尔字段无法区分工件与推断
- C. runbook 属于"直接行为"，代码标错了级别
- D. runbook 属于"报告的行为"，标 `False` 与讲义一致

**Q8.** 讲义认为 AI 功能最常在哪里失败？

- A. 界面配色与布局
- B. 模型选择
- C. Handoff 与异常情况，因为只有 happy path 被认真设计
- D. 响应延迟

---

## 三、动手 / 代码题

**Q9.**（把布尔 `direct` 升级为四级证据阶梯）当前 `Evidence` 只有 `direct: bool`。请：

1. 把它改成 `kind: str`，取值 `"direct" | "artifact" | "reported" | "inference"`；未知取值要报问题。
2. 按讲义"只有前两级能直接证明当前行为"，统计**每一步**是否有支撑；输出 `ungrounded_steps` 和 `grounded_step_ratio`，并且只有所有步骤都有支撑时才是 `grounded`。
3. 用示例数据（录屏 = direct，incident 184 = artifact，runbook = artifact）验证结果；再把第 3 步的证据换成一次访谈（reported），结果应如何变化？

**Q10.**（找出置信度膨胀）下面两个工作流的实际运行结果都是 `grounded`：

| 工作流 | 实际 `direct_evidence_ratio` |
|------|------|
| W1：10 步，仅第 1 步有一条直接证据，其余 9 步各一条推断 | 0.1 |
| W2：3 步，第 1 步有 5 条直接证据，第 2、3 步各一条推断 | 0.71 |

1. 解释为什么两者都是 `grounded`；W2 的 0.71 为什么具有误导性。
2. 如果改为"有直接证据的步骤数 / 总步骤数"，W1、W2 和示例分别是多少？

**Q11.**（讲义 Build It：异常分支）讲义要求："加一条部署记录缺失时的异常路径，保持主顺序不变，并记录分支从哪里开始。"

1. 如果直接在示例末尾追加 `WorkflowStep(3, "on-call engineer", "deployment record missing", ...)`，`audit` 会报什么？为什么？
2. 设计一种数据结构表达异常分支，并修改 `audit`：主路径仍要求 1..n 连续，异常步骤必须指向一个存在的主路径步骤，且同样需要证据。

**Q12.**（手算输出）写出下列调用的 `status`、`issues`、`direct_evidence_ratio`：

- (a) `audit([])`
- (b) 一个步骤，order=1，两条证据：`confidence=1.5, direct=True` 和 `confidence=-1, direct=False`
- (c) 两个步骤：order=1 有一条直接证据；order=2 的 evidence 为空元组
- (d) 两个步骤：order 分别为 0 和 1，各有一条 `direct=False` 的证据，第 2 步 friction 为 `"re-entry"`（同时写出 `friction_points`）

---

## 四、面试高频题

**Q13.**（基础必考）做一个面向内部团队的 AI 功能之前，你怎样发现用户**真实**的工作流，而不是只收集他们"想要什么功能"？

**Q14.**（原理深挖）为什么要把证据分为直接行为、工件、报告和推断？"置信度静默膨胀"是什么意思，会造成什么后果？

**Q15.**（工程实践）讲义练习 1 要求"不访谈任何人，只从日志重建一个工作流"。对一个已经在线上运行的 agent 系统，你会用哪些数据源、怎样重建？

**Q16.**（场景设计）你发现客服团队里资深员工和新员工处理退款的流程差异很大，产品经理希望"统一成一个标准流程再做 AI 助手"。你怎么回应？

**Q17.**（追问型）为什么说 AI 功能常在 handoff 和异常处失败？请举一个例子，并说明在发现阶段如何把它们找出来。

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义的阶梯：1. Direct behavior（observation、trace、recording、system event）；2. Artifact（ticket、runbook、log、form、completed output）；3. Reported behavior（当事人描述）；4. Inference（团队推断）。A 把自述放在了观察之上——这正是"人们说的"与"人们做的"常常不一致的地方；C、D 顺序混乱。

### Q2 — 答案：D

讲义定义 Hidden state 为 "facts carried in memory, chat, or personal notes"。私人对照表正是这种事实：它让流程能跑通，但不在任何正式系统里，AI 功能如果只读正式系统就拿不到它。A 是重复劳动和延迟；B 是谁有权做有后果的改动；C 是常规流程失效的情况。

### Q3 — 答案：A

示例有 3 条证据，其中 2 条 `direct=True`（录屏、incident 184），1 条 `False`（runbook）：`round(2/3, 2) = 0.67`（已实际运行验证）。C 是三条证据置信度的平均值 `(0.95+0.9+0.8)/3 ≈ 0.883`，但代码不计算这个值；D 是按讲义"工件也算直接"的理想口径（见 Q7、Q9）。

### Q4 — 答案：C

`status` 的条件是 `not issues and direct > 0`：顺序 1–10 连续、每步有证据、置信度都在 [0, 1]，没有 issue；直接证据数为 1 > 0，于是 `grounded`，比例 `1/10 = 0.1`（已实际运行验证）。A 是一个合理的改进规则但代码没有；B 错，`confidence` 只做范围检查，不参与 status；D 不会发生。这说明 "grounded" 这个标签可能严重高估证据强度（见 Q10）。

### Q5 — 答案：A

讲义 "Do Not Average Away Disagreement"：保留变体，直到你理解它们代表的是不同角色、不同风险等级、新旧流程、专长差异还是真正的政策分歧；"An averaged workflow can describe nobody." B 正是讲义反对的做法；C、D 用权威或多数代替理解，可能抹掉有合理理由的变体（例如高风险服务就该先查部署记录）。

### Q6 — 答案：D

代码比较的是**列表**：`[1, 3, 2] != [1, 2, 3]`，于是报 "workflow order must be contiguous from one"。这条消息的措辞有点误导——集合确实连续，问题在于**顺序**不对；测试 `test_reversed_contiguous_order_is_rejected` 专门验证了"连续但倒序也要拒绝"。A 混淆了集合与序列；B 与证据无关；C 代码不做排序。

### Q7 — 答案：B

讲义把 runbook 明确列为 Artifact（第二级），并说 "Only the first two prove current behavior directly"。按字面，它应计入直接证据，示例比例会变成 1.0。不过也可以为代码辩护：runbook 记录的是**规定**的流程（"production writes require approval"），并不证明人们**实际**这样做——这恰好说明一个布尔值无法承载这种区分，应该用四级标签并让分析者显式选择。A、D 把工件误归为推断或自述；C 把工件当成了观察。

### Q8 — 答案：C

讲义原文："AI features often fail at handoffs and exceptions because the happy path was the only path shaped." 交接点有隐藏状态和权限变化，异常是常规假设失效的地方，这两处最容易被只看"标准流程"的设计遗漏。A、B、D 都可能是问题，但不是讲义的结论。

### Q9 — 参考答案

```python
STRENGTH = {"direct": 4, "artifact": 3, "reported": 2, "inference": 1}

@dataclass(frozen=True)
class Evidence:
    source: str
    observation: str
    kind: str          # "direct" | "artifact" | "reported" | "inference"
    confidence: float

def proves_current_behavior(item: Evidence) -> bool:
    return STRENGTH.get(item.kind, 0) >= STRENGTH["artifact"]

def audit(steps: list[WorkflowStep]) -> dict:
    issues: list[str] = []
    if [s.order for s in steps] != list(range(1, len(steps) + 1)):
        issues.append("workflow order must be contiguous from one")
    for step in steps:
        if not step.evidence:
            issues.append(f"step {step.order} has no evidence")
        for item in step.evidence:
            if item.kind not in STRENGTH:
                issues.append(f"step {step.order} has unknown evidence kind {item.kind!r}")
            if not 0 <= item.confidence <= 1:
                issues.append(f"step {step.order} has confidence outside zero to one")
    ungrounded = [s.order for s in steps
                  if not any(proves_current_behavior(e) for e in s.evidence)]
    return {
        "status": "grounded" if steps and not issues and not ungrounded else "needs-evidence",
        "issues": issues,
        "grounded_step_ratio": round(1 - len(ungrounded) / len(steps), 2) if steps else 0.0,
        "ungrounded_steps": ungrounded,
        "friction_points": [s.friction for s in steps if s.friction],
    }
```

实际运行：

- 示例（direct / artifact / artifact）：`status="grounded"`、`grounded_step_ratio=1.0`、`ungrounded_steps=[]`。
- 第 3 步换成访谈（`kind="reported"`）：`status="needs-evidence"`、`grounded_step_ratio=0.67`、`ungrounded_steps=[3]`，且 `issues` 为空——这一步**不是错误**，只是**仍需证据**，正好对应讲义"把不确定的说法保持可见，而不是把它变成需求"。
- 未知取值 `kind="rumor"` 会产生 `"step 1 has unknown evidence kind 'rumor'"`。
- 空工作流 `[]` 为 `needs-evidence`，比例 `0.0`（顺带修正了原代码返回整数 `0` 的类型不一致）。

### Q10 — 参考答案

1. `status` 只要求"没有 issue 且直接证据总数 > 0"。W1 只有第 1 步有直接证据，W2 也是，于是都是 `grounded`。W2 的 0.71（5/7）是**按证据条数**算的：同一步骤堆了 5 条直接证据，就把比例拉高，可另外两步完全没有直接证据。这个数字会让人以为"大部分流程已被观察证实"，实际只有 1/3 的步骤被证实——这正是讲义说的"confidence silently inflates"。

2. 按步骤统计（已实际运行验证）：W1 = `1/10 = 0.1`；W2 = `1/3 = 0.33`；示例 = `2/3 = 0.67`（按原代码的布尔口径）。W1 的数字没变，是因为它每步恰好只有一条证据；一旦某步有多条证据，两种口径就会分开。此外，status 应改为"所有步骤都有直接/工件证据"才算 grounded（Q9 的做法），或至少在输出中列出未被证实的步骤。

### Q11 — 参考答案

1. 报 `["workflow order must be contiguous from one"]`（已实际运行验证）：order 序列变为 `[1, 2, 3, 3]`，不等于 `[1, 2, 3, 4]`。当前模型只有一条线性路径，异常步骤没有地方放；如果硬把它编成第 4 步，又会错误地表示"异常总在审批之后发生"。

2. 参考设计：给步骤加 `branch_from` 字段，主路径步骤为 `None`，异常步骤指向它从哪一步分出：

```python
@dataclass(frozen=True)
class WorkflowStep:
    order: int
    actor: str
    action: str
    evidence: tuple[Evidence, ...]
    friction: str = ""
    branch_from: int | None = None     # None 表示主路径

def audit_with_branches(steps: list[WorkflowStep]) -> dict:
    main_path = [s for s in steps if s.branch_from is None]
    branches = [s for s in steps if s.branch_from is not None]
    result = audit(main_path)                       # 原有检查只作用于主路径
    main_orders = {s.order for s in main_path}
    for s in branches:
        if s.branch_from not in main_orders:
            result["issues"].append(f"exception step {s.order} branches from unknown step {s.branch_from}")
        if not s.evidence:
            result["issues"].append(f"exception step {s.order} has no evidence")
    if result["issues"]:
        result["status"] = "needs-evidence"
    result["exceptions"] = [asdict(s) for s in branches]
    return result
```

示例异常步骤：`WorkflowStep(1, "on-call engineer", "asks in team chat which deploy changed the service", (Evidence("incident 191", "deployment record missing; owner found via chat", True, 0.85),), "hidden state in chat", branch_from=2)`。实际运行：主路径仍 `grounded`、比例仍 0.67、`exceptions` 中有 1 条；若 `branch_from=9` 且无证据，则得到两条 issue 并变为 `needs-evidence`。

注意这条异常同时暴露了一个**隐藏状态**（谁改了部署只能在聊天里问到），这正是讲义希望通过异常路径发现的东西。也可以把每个变体/异常建模为独立的 `Workflow`，以便"不合并地建模两个变体"（讲义练习 4）。

### Q12 — 参考答案

（全部已实际运行验证。）

| 调用 | status | issues | ratio |
|------|--------|--------|-------|
| (a) `audit([])` | `needs-evidence` | `[]` | `0`（整数，`total` 为 0 走了 `else 0` 分支） |
| (b) | `needs-evidence` | `["step 1 has confidence outside zero to one"]` **重复两次** | `0.5` |
| (c) | `needs-evidence` | `["step 2 has no evidence"]` | `1.0`（唯一的证据是直接的；空步骤不进分母） |
| (d) | `needs-evidence` | `["workflow order must be contiguous from one"]` | `0.0`；`friction_points=["re-entry"]` |

要点：(a) 中空列表与"从 1 开始连续"并不冲突（`[] == list(range(1, 1))`），失败只是因为没有直接证据；(b) 每条越界证据各报一次，消息内容相同，适合改成带证据序号的消息；(c) 说明比例对"没有证据的步骤"视而不见；(d) 比例为浮点 `0.0`，与 (a) 的整数 `0` 类型不一致。

### Q13 — 参考回答要点

- **先观察现状**：跟岗、录屏、看 trace 与系统事件、翻工单和日志，重建"现在发生了什么"，而不是开需求会问"你想要什么功能"。
- **逐步记录八个字段**：Actor、Trigger、Action、Input、Output、Friction、Authority、Evidence。
- **超出屏幕**：等待、复制粘贴、旁路沟通（聊天、电话）、审批、错误恢复、被习以为常的步骤。
- **重点找四样**：friction、hidden state、authority、exceptions。
- **给每个说法标证据等级**，缺直接证据的保持"待验证"，不要写成需求。
- **保留变体**，弄清差异来源。
- 加分点：把产出写成结构化文件（如 `workflow-evidence.json`），作为下一步假设地图的输入（第 49 节）。
- 常见误区：用一次访谈的自述当作事实；只画 happy path。

### Q14 — 参考回答要点

- **原因**：不同证据对"当前行为"的证明力不同。直接行为是观察到的事实；工件是行为留下的痕迹；自述受记忆、社会期望和"应该怎么做"影响；推断只是团队的猜测。
- **静默膨胀**：一条"据说"的说法在会议纪要里被转述几次后，就变成"用户需要 X"的需求，没人记得它从未被观察过。量化指标也会膨胀（如本节代码按证据条数算比例、一条直接证据即 grounded）。
- **后果**：在错误的假设上设计功能——例如以为工程师都会先看部署记录，结果 AI 助手的输入恰好是很多人根本不用的数据源。
- **做法**：每个说法都带等级标签；度量"有直接/工件证据的步骤比例"；把低等级的说法转成第 49 节的待验证假设。
- 加分点：讲义延伸阅读中 Gotel & Finkelstein 讨论的"需求可追溯性"问题——需求与其来源的关系很难保持，标注证据正是为了保住这条链。

### Q15 — 参考回答要点

- **数据源**：agent 的 trace/span（如 OpenTelemetry GenAI 语义约定的调用记录）、工具调用日志、审批/权限系统事件、工单系统状态变化、聊天中的人工介入记录、版本控制提交记录。
- **重建方法**：以一个 case/incident ID 关联所有事件 → 按时间排序 → 识别 actor（人还是 agent）→ 标出 handoff（actor 变化处）与等待（时间间隔）→ 统计各路径的频率，找出主路径和异常分支。
- **证据等级**：这些都是直接行为或工件，可以直接计入。
- **局限**：日志看不到"在脑子里做的事"和"线下的沟通"——隐藏状态需要补充访谈，但访谈结果要标为 reported。
- 加分点：用过程挖掘（process mining）的思路统计变体频率，而不是只画一条平均路径；在 agent 系统中特别关注人工接管点，它们往往就是异常和 handoff。

### Q16 — 参考回答要点

- **先不统一**：差异本身是信息。弄清它是角色差异、风险差异（资深员工处理的是高额退款？）、新旧流程、专长差异，还是对政策理解不同。
- **取证**：观察两组人的真实处理过程，查工单记录，看哪种做法的返工率、投诉率更低；把每个说法标证据等级。
- **分情况处理**：
  - 若是专长差异：资深员工的步骤里可能藏着关键判断（隐藏状态），AI 助手应该把这部分外化给新员工，而不是抹掉；
  - 若是风险差异：两条流程都合理，助手要根据风险等级走不同分支；
  - 若是政策分歧：这是需要人类决策的产品问题，不能交给 AI 助手"自己选"。
- 加分点：引用讲义 "An averaged workflow can describe nobody."；指出"先标准化再做 AI"可能把最有价值的专家判断一起标准化掉。

### Q17 — 参考回答要点

- **原因**：handoff 处 actor 变化，信息要跨人/跨系统传递，常常依赖隐藏状态（聊天、口头约定）；权限也在这里变化（谁能批准）。异常处常规假设失效（数据缺失、系统宕机），而原型和演示通常只覆盖 happy path。
- **例子**：事故助手能根据告警和部署记录推荐故障服务，但当部署记录缺失时（讲义 Build It 的异常），工程师实际是在团队聊天里问"谁刚发过版"。助手没有这个信息源，于是给出自信但错误的建议；或者在需要事故指挥官批准的写操作前，没有正确交接。
- **发现方法**：重建工作流时显式标记每个 actor 变化点；专门询问并观察"上次流程不顺的时候发生了什么"；从工单和事故复盘中找异常案例；为每个异常记录分支起点和证据。
- 加分点：把异常和 handoff 作为第 49 节的高风险假设，优先验证；在第 50 节选切片时，避免"happy-path minimum"。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 47 先定义预期成效，再选择交付形式](../../47-outcomes-before-output/docs/zh.md)：本节用观察检验上一节 frame 中的 user、situation 与 current behavior。
- [阶段 14 · 37 运行时反馈循环](../../37-runtime-feedback-loops/docs/zh.md)：结构化记录真实输出，是"直接证据"在 agent 系统中的来源。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：从 trace 重建工作流需要的数据格式。

### 本节被哪些后续内容用到
- [阶段 14 · 49 梳理假设，优先验证风险最高的一项](../../49-map-assumptions-and-risk/docs/zh.md)：把本节观察到的摩擦和不确定性转成假设地图（讲义 "What You Keep"）。
- [阶段 14 · 50 选择足以改变决策的最小实现范围](../../50-choose-the-smallest-testable-slice/docs/zh.md)：避免只覆盖 happy path 的"假最小切片"。
- [阶段 14 · 51 编写保留判断空间的规格说明](../../51-write-specifications-that-preserve-judgment/docs/zh.md)：规格中的不变量与证据要求来自真实工作流。
- [阶段 14 · 24 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik](../../24-agent-observability-platforms/docs/zh.md)：上线后持续观察真实工作流的工具。
- [阶段 17 · 23 AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：本节事故诊断示例在生产中的形态。

### 延伸关键词
`contextual inquiry` · `requirements elicitation` · `evidence ladder` · `hidden state` · `handoff` · `exception path` · `workflow variants` · `process mining` · `requirements traceability` · `happy path bias`
