# 测验 · 有意识地选择原型、试点或生产方案（Choose Prototype, Pilot, or Production Deliberately）

> **阶段 14 · Agent 工程 · 第 53 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：本节中文讲义为机器翻译，部分句子失真：Build It 一节漏译了"Explain what additional evidence would justify production"（解释还需要什么证据才能进入生产），练习 5 被译成"设计a rollback 被绑的飞行员的收据"（原文：为有界试点设计一份回滚凭据），"operations"被译成"行动"。本测验以英文原文为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三个阶段是三种学习环境 | 不是"打磨程度"的三个等级；选择能以最小不必要后果回答当前未知的阶段 |
| 2 | 三个主问题 | Prototype：这个机制能否产生证据？Pilot：在有界的真实受众与条件下能否安全运作？Production：能否以承诺的可靠性与风险水平持续拥有它？ |
| 3 | Prototype 的要求 | 可丢弃、隔离、行为窄、学习问题明确、不做虚假的运维承诺；机制证明自己之前不要优化架构 |
| 4 | Pilot 的要求 | 指名的受众、人类负责人、有界的时长与权限、审计与回滚、outcome 与 guardrail 阈值、扩大 / 修订 / 停止三种退出标准 |
| 5 | Production 的要求 | SLO、on-call 与事故归属、安全与隐私评审、成本与容量控制、回滚与恢复、持续监控、退役路径 |
| 6 | 生产的真正起点 | "Production begins when the organization accepts ongoing responsibility"——不是有了 URL 或部署就算生产 |
| 7 | 试点可以用生产数据 | 试点可以使用生产数据，但受众和权限有限 |
| 8 | 阶段漂移（stage drift） | 原型获得了用户、数据或权限，却没有获得 ownership；警告横幅不够，阶段边界要体现在配置、访问控制、遥测与文档中 |
| 9 | 阶段应可观测 | "The stage should be observable from the system itself." |
| 10 | 代码的决策规则 | 不需要真实用户且不需要真实数据 → prototype；否则只要"未就绪 / 后果 ≥ 4 / 不可逆"任一成立 → pilot；其余 → production |

### 核心技能（能动手做到）

- [ ] 按"学习问题"而不是"部署状态"给现有项目分类
- [ ] 手推 `choose_stage` 的真值表，说出 80 种输入组合中各阶段的数量
- [ ] 为试点写出包含 **stop** 在内的退出标准
- [ ] 指出 `required_controls` 与讲义清单的差异（例如生产清单里没有审计）
- [ ] 修改 `choose_stage`，让进入生产需要试点证据，并加强输入校验
- [ ] 写一个阶段漂移检测器，用系统的可观测事实（用户、数据访问、写权限、负责人）检查声明的阶段

---

## 二、基础自测（选择题）

**Q1.** 讲义认为 prototype、pilot、production 的根本区别是：

- A. 代码质量与界面打磨程度
- B. 要回答的学习问题、真实暴露程度、后果大小和 ownership
- C. 使用的模型大小
- D. 部署在哪个云区域

**Q2.** 执行 `choose_stage(BuildDecision("x", False, False, 5, False, False))`，结果是：

- A. `"pilot"`，因为后果为 5
- B. 抛出 `ValueError`
- C. `"production"`
- D. `"prototype"`

**Q3.** 执行 `choose_stage(BuildDecision("x", True, True, 3, False, True))`（需要真实用户与数据、后果 3、**不可逆**、运维已就绪），结果是：

- A. `"pilot"`
- B. `"production"`
- C. `"prototype"`
- D. 抛出 `ValueError`

**Q4.** 讲义中的"stage drift（阶段漂移）"指的是：

- A. 试点到期自然结束
- B. 一个指标的数值随时间漂移
- C. 原型获得了用户、数据或权限，却没有同时获得控制措施和 ownership
- D. 把 Git 分支改名

**Q5.** `choose_stage` 的输入中，两个布尔需求 × 5 档后果 × 可逆性 × 运维就绪，共 2×2×5×2×2 = 80 种组合。其中返回 `"production"` 的有几种？

- A. 3
- B. 9
- C. 20
- D. 51

**Q6.** 比较 `required_controls("pilot")` 与 `required_controls("production")`，下列哪一项出现在试点清单中，却**不在**生产清单中？

- A. audit trail
- B. rollback
- C. cost and capacity controls
- D. continuous monitoring

**Q7.** 一个服务已经部署、有公开 URL，也有几位同事在用。按讲义，它什么时候才算真正意义上的 production？

- A. 有了 URL 的那一刻
- B. 界面足够精致时
- C. 第一次提交代码时
- D. 组织接受了对其可靠性、风险与运维的持续责任时

**Q8.** 为什么讲义说"A warning banner is not enough"，要在配置、访问控制和遥测中标记阶段边界？

- A. 因为横幅会降低页面性能
- B. 因为文档在法律上无效
- C. 因为横幅无法阻止访问或权限扩张，只有技术控制才能让阶段可执行、可观测
- D. 因为技术控制可以替代 ownership

---

## 三、动手 / 代码题

**Q9.** 讲义 Build It："Change the pilot example to low consequence with operational readiness. Explain what additional evidence would justify production."

1. 把第二个示例改成 `BuildDecision("Will engineers trust the recommendation?", True, True, 2, True, True)`，`choose_stage` 返回什么？这暴露了什么问题？
2. 修改 `choose_stage`，让进入生产必须有通过的试点证据。

**Q10.** 阅读输入校验：

```python
def choose_stage(decision: BuildDecision) -> str:
    if not 1 <= decision.consequence <= 5:
        raise ValueError("consequence must be from one to five")
```

1. `consequence=3.5` 和 `consequence=True` 分别会怎样？为什么？
2. 写出更严格的校验。

**Q11.** 对比讲义清单与 `required_controls` 的实现，列出至少四处不一致，并说明其中哪一处风险最大。

**Q12.** 讲义练习 3："Add a technical control that prevents a prototype from reaching production data." 以及"The stage should be observable from the system itself."

请写一个 `detect_drift(declared_stage, observed)`：`observed` 包含系统的可观测事实（是否有真实用户、是否能读生产数据、是否有写权限、是否有指名负责人、是否有回滚），返回漂移问题列表。给出一个原型漂移的例子并说明输出。

---

## 四、面试高频题

**Q13.**（基础必考）原型、试点、生产三者有什么区别？分别要回答什么问题、需要什么控制？

**Q14.**（原理深挖）为什么说"原型代码最危险的时候不是它写得差，而是它开始有了用户"？如何从技术上防止阶段漂移？

**Q15.**（工程实践）你负责的 AI agent 试点已经跑了 4 周，指标不错，老板问"能不能直接全量上线？"你需要确认哪些东西？

**Q16.**（场景设计）为"AI 自动回复客户退款申请"的 agent 设计一个试点方案：受众、负责人、时长与权限、审计与回滚、阈值、退出标准。

**Q17.**（追问型）`choose_stage` 规定后果 ≥ 4 的工作永远只能停留在试点。这合理吗？高后果系统应如何进入生产？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："These are different learning environments, not levels of polish." 三个阶段分别回答"机制能否产生证据""在有界真实条件下是否安全""能否持续拥有"，差别在于真实暴露、后果和责任。

- A 错：讲义明确说"A prototype can be technically complete and still be disposable"。
- C、D 与阶段选择无关。

### Q2 — 答案：D

`choose_stage` 先校验后果在 1–5 之间（5 合法），然后检查"既不需要真实用户、也不需要真实数据"——成立，直接返回 `"prototype"`。后果和可逆性只在需要真实暴露时才参与判断。这是合理的：不接触真实用户和数据的原型，本身的后果就被隔离了。

- A 错：后果判断在 prototype 分支之后。
- B 错：5 在合法范围内。
- C 错：既然没有真实暴露，就到不了生产分支。

### Q3 — 答案：A

需要真实用户 → 越过 prototype；进入第二个条件 `not operational_readiness or consequence >= 4 or not reversible`，其中 `not reversible` 为真 → `"pilot"`。讲义流程图只写了"Consequence bounded and operations ready?"，代码把"可逆性"也纳入了判断：不可逆的工作即使后果中等、运维就绪，也只能先试点。

### Q4 — 答案：C

讲义："Prototype code becomes dangerous when it acquires users, data, or authority without acquiring ownership." 漂移是暴露增长而控制没有跟上。

- A 是正常的退出。
- B 是指标漂移（metric drift），另一回事。
- D 无关。

### Q5 — 答案：B

实际枚举 80 种组合：prototype 20、pilot 51、production 9。

推导：production 需要同时满足"至少需要用户或数据之一"（3 种）、后果 ∈ {1, 2, 3}（3 种）、可逆（1 种）、运维就绪（1 种）：`3 × 3 × 1 × 1 = 9`。prototype 是"两者都不需要"（1 种）× 其余 5×2×2 = 20。剩下的 `80 − 20 − 9 = 51` 都是 pilot。

- C（20）是 prototype 的数量，D（51）是 pilot 的数量，A（3）只数了用户/数据的组合。

### Q6 — 答案：A

实测：`set(pilot) − set(production) = {"limited audience", "human owner", "audit trail", "exit criteria"}`。其中"limited audience"和"exit criteria"在生产中不再需要是合理的；"human owner"可以认为被"on-call owner"取代；但 **audit trail 在生产中消失**是一个真实的缺口——生产的权限和影响面比试点更大，审计只应加强。讲义的生产清单本身也没有显式列出审计（只在试点清单列了"audit and rollback"），代码照搬了这个遗漏。

- B 错：rollback 两边都有。
- C、D 错：只在生产清单中。

### Q7 — 答案：D

讲义："Production begins when the organization accepts ongoing responsibility." 生产是一种持续的责任状态（SLO、on-call、监控、退役路径），不是托管状态。题干描述的正是讲义警告的"阶段漂移"：已经有用户，却未必有人对它负责。

### Q8 — 答案：C

讲义："Mark prototype and pilot boundaries in configuration, access control, telemetry, and documentation. A warning banner is not enough." 横幅只能提醒，不能阻止原型连上生产数据库或获得写权限；配置、访问控制和遥测可以执行并观测边界。

- D 错：讲义强调技术控制与 ownership 都要有，前者不能替代后者。

### Q9 — 参考答案

1. 实测返回 `"production"`。问题：`choose_stage` 只看"上下文"（是否需要真实暴露、后果、可逆性、运维就绪），**不看证据**。原来这个示例的未知是"工程师是否信任推荐"——这个问题恰恰只有试点能回答；把后果调低、把运维设为就绪，并不能回答它。讲义学习目标："Delay real authority until evidence and operations justify it."——证据和运维两者缺一不可。

   进入生产还需要的证据：试点中 outcome 与 guardrail 指标按事前阈值达标（第 52 节）；退出标准判定为"expand"；回滚演练成功；on-call、SLO、安全与隐私评审、成本控制都已到位。

2. 参考实现（已运行验证：同一输入在 `pilot_evidence_passed=False` 时返回 `"pilot"`，为 `True` 时返回 `"production"`）：

```python
def choose_stage(decision: BuildDecision, pilot_evidence_passed: bool = False) -> str:
    ...  # 校验同 Q10
    if not decision.real_users_required and not decision.real_data_required:
        return "prototype"
    if (not decision.operational_readiness
            or decision.consequence >= 4
            or not decision.reversible
            or not pilot_evidence_passed):
        return "pilot"
    return "production"
```

注意：改动后原测试 `test_ready_reversible_work_can_be_production` 需要传入 `pilot_evidence_passed=True` 才能通过。更好的做法是把证据作为 `BuildDecision` 的字段（例如 `pilot_result: str | None`），并在输出 JSON 中记录引用的证据报告。

### Q10 — 参考答案

1. 实测两者都**被接受**并返回 `"production"`（在用户/数据需求为真、可逆、就绪的情况下）：
   - `3.5`：`1 <= 3.5 <= 5` 为真；dataclass 的类型注解 `consequence: int` 在运行时不检查。
   - `True`：`bool` 是 `int` 的子类，`True == 1`，所以 `1 <= True <= 5` 为真。
   后果是一个有序等级，3.5 没有定义；传入布尔值通常意味着调用方把字段搞错了。

2. 严格校验（已运行验证 3.5 与 True 都会被拒绝）：

```python
c = decision.consequence
if isinstance(c, bool) or not isinstance(c, int) or not 1 <= c <= 5:
    raise ValueError("consequence must be an integer from one to five")
```

同理可以检查四个布尔字段确实是 `bool`。注意 `isinstance(c, bool)` 必须放在前面，因为 `isinstance(True, int)` 为 `True`。

### Q11 — 参考答案

| 阶段 | 讲义要求 | 代码 `required_controls` | 差异 |
|------|---------|--------------------------|------|
| Prototype | discardable、isolated、narrow、明确学习问题、无虚假运维保证 | synthetic or recorded inputs、discardable implementation、learning question | 缺 **isolated**、narrow、"无虚假保证"；多了"合成或录制输入"（可视为隔离的一种手段） |
| Pilot | 指名受众、人类负责人、有界时长与权限、审计与回滚、outcome 与 guardrail 阈值、扩大/修订/停止退出标准 | limited audience、rollback、human owner、audit trail、exit criteria | 缺 **outcome 与 guardrail 阈值**、**有界时长与权限**；退出标准没写明要包含 stop |
| Production | SLO、on-call 与事故归属、安全与隐私评审、成本与容量、回滚与恢复、持续监控、退役路径 | SLO、on-call owner、security review、cost and capacity controls、rollback、recovery、continuous monitoring、retirement path | "security and privacy review"变成只有 security；"incident ownership"弱化为 on-call owner；试点中的 audit trail 消失 |

风险最大的是**试点缺少阈值与有界权限**：没有事前阈值，试点无法产生可判定的证据（第 52 节），"扩大还是停止"会变成凭感觉；没有有界权限，试点就是没有名分的生产。其次是生产清单丢掉审计与隐私评审。

改进方向：让控制清单**累积**（生产 ⊇ 试点中仍适用的项），并把每一项变成可检查的条目（例如配置里存在回滚命令、审计日志开关为真），而不是字符串。

### Q12 — 参考答案

参考实现（已运行验证）：

```python
@dataclass(frozen=True)
class Observed:
    has_real_users: bool
    reads_production_data: bool
    has_write_authority: bool
    has_named_owner: bool
    has_rollback: bool

def detect_drift(declared: str, o: Observed) -> list[str]:
    issues = []
    if declared == "prototype":
        if o.has_real_users:
            issues.append("prototype has real users")
        if o.reads_production_data:
            issues.append("prototype reads production data")
        if o.has_write_authority:
            issues.append("prototype has write authority")
    if declared in ("pilot", "production"):
        if not o.has_named_owner:
            issues.append(f"{declared} lacks a named owner")
        if not o.has_rollback:
            issues.append(f"{declared} lacks rollback")
    return issues
```

例子：`detect_drift("prototype", Observed(True, True, False, False, False))` 返回 `['prototype has real users', 'prototype reads production data']`——原型被同事们用起来了，还连上了生产数据，但没有负责人。

要点：
- `observed` 的值必须来自系统本身（IAM 策略、数据库连接配置、访问日志、服务目录中的 owner 字段），而不是由开发者自报，这才是"observable from the system itself"。
- 预防优于检测：讲义练习 3 的技术控制可以是"原型环境的凭据只能访问合成数据库 / 录制数据"，在网络或 IAM 层就拦住；`detect_drift` 作为持续巡检兜底。

### Q13 — 参考回答要点

- **Prototype**：回答"机制能否产生证据"。不需要真实用户/数据；可丢弃、隔离、窄；明确学习问题；不承诺运维。
- **Pilot**：回答"在有界的真实受众与条件下能否安全运作"。指名受众、负责人、有界时长与权限、审计与回滚、outcome/guardrail 阈值、扩大/修订/停止退出标准。可以用生产数据，但受众和权限有限。
- **Production**：回答"能否以承诺的可靠性和风险水平持续拥有"。SLO、on-call 与事故归属、安全与隐私评审、成本与容量控制、回滚与恢复、持续监控、退役路径。
- 核心观点：阶段是学习环境，不是打磨程度；选能以最小不必要后果回答当前未知的那个。
- 加分点：提到讲义引用的 Boehm 螺旋模型——每次迭代的投入与已解决的风险相匹配。

### Q14 — 参考回答要点

- 原型的"简陋"在设计上是被允许的（可丢弃、无运维承诺）；危险来自**暴露与责任不匹配**：一旦有了用户、数据或权限，故障就有了真实后果，但没有 on-call、回滚、审计、负责人。
- 技术手段：
  1. **访问控制**：原型环境的凭据只能访问合成或录制数据；生产数据库对原型网络不可达。
  2. **配置标记**：每个服务在配置/服务目录里声明阶段，部署流水线据此拒绝"原型 → 生产环境"的发布。
  3. **遥测**：按阶段打标签，监控"原型的活跃用户数""试点的受众是否超出名单"。
  4. **到期机制**：试点与原型有到期时间，到期自动关闭或要求续批。
  5. **持续巡检**：类似 Q12 的漂移检测。
- 常见误区：只靠横幅或 README 说明"这是原型"。

### Q15 — 参考回答要点

- 先看**证据**：试点的 outcome 与 guardrail 是否按事前阈值达标？counter-metric 有没有恶化？样本量够不够（第 52 节）？退出标准判定是"expand"还是"revise"？
- 再看**运维与责任**（生产清单）：SLO 定了吗？谁 on-call、事故谁负责？安全与隐私评审做了吗？成本与容量（全量后调用量放大多少倍、预算上限）？回滚与恢复演练过吗？持续监控与告警有吗？退役路径呢？
- 再看**后果与可逆性**：全量后的影响面、是否有不可逆操作；若有，需要更强的控制或渐进放量。
- 推荐做法：不是一步全量，而是逐步扩大受众（金丝雀 / 渐进式发布），每一步都有阈值和回滚。
- 加分点：指出"指标不错"需要具体化为事前阈值，否则就是事后合理化。

### Q16 — 参考回答要点

- **受众**：一个区域、某一类低金额（如 ≤ 50 元）退款申请，约 5% 的流量；名单在配置中可查。
- **负责人**：客服运营负责人（业务）+ 一名工程 owner，写在服务目录中。
- **时长与权限**：4 周；agent 只能起草回复与建议"批准/拒绝"，**不能直接执行退款**（Locked 决策），由人工一键确认；超过金额上限一律转人工。
- **审计与回滚**：每条建议、采纳与否、最终结果写入审计日志；配置开关可在一分钟内回到纯人工流程，回滚演练一次并留存凭据。
- **阈值**：outcome——人工采纳率 ≥ 80%、平均处理时长下降 ≥ 30%；guardrail——违反退款政策的建议被采纳次数 = 0、泄露个人信息 = 0；counter——7 天内二次投诉率不高于基线。
- **退出标准**：expand（全部达标且样本足够）；revise（outcome 未达标但 guardrail 守住）；stop（任何 guardrail 被突破，或连续两周采纳率 < 50%）。
- 加分点：说明为什么"直接执行退款"留到生产之后再评估，以及进入生产需补齐的 SLO、on-call、隐私评审等。

### Q17 — 参考回答要点

- 代码规则的合理之处：高后果工作在没有更多控制时不应获得"生产级"的持续授权，默认保守。
- 不合理之处：
  1. 规则是静态的，**没有任何证据输入**能改变结论，高后果系统（支付、医疗辅助）永远停留在"试点"，这在现实中会导致"永久试点"——事实上的生产，却只有试点的控制，反而更危险。
  2. 后果等级是固定输入，但控制措施（人工确认、额度上限、只读化）本身可以**降低**有效后果，代码无法表达。
- 高后果系统进入生产的方式：
  - 用控制降低有效后果（人工在环、额度与范围限制、两人复核），再重新评估等级；
  - 更强的试点证据（更大样本、更长窗口、红队测试）；
  - 渐进放量与自动回滚；
  - 更完整的生产控制：审计、隐私与合规评审、事故演练、明确的退役条件；
  - 由有权限的人显式签署（Locked 决策 + 人工 checkpoint）。
- 加分点：指出"生产"在讲义中意味着组织接受持续责任——高后果系统要做的是让组织**有能力**承担这份责任，而不是永远回避它。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 50 选择足以改变决策的最小实现范围](../../50-choose-the-smallest-testable-slice/docs/zh.md)：切片决定了阶段要回答的未知。
- [阶段 14 · 51 编写保留判断空间的规格说明](../../51-write-specifications-that-preserve-judgment/docs/zh.md)：locked 的权限决策决定 agent 在试点中能做什么。
- [阶段 14 · 52 在结果产生前设计成功指标](../../52-design-success-metrics/docs/zh.md)：试点的 outcome / guardrail 阈值与退出判定。
- [阶段 14 · 49 梳理假设，优先验证风险最高的一项](../../49-map-assumptions-and-risk/docs/zh.md)：最高风险的假设决定先进入哪个阶段。

### 本节被哪些后续内容用到
- [阶段 14 · 54 建立持续反馈机制，明确负责人和退役条件](../../54-build-the-feedback-ratchet/docs/zh.md)：生产之后的信号如何回流为受控变更。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)：从试点到生产的渐进放量手段。
- [阶段 17 · 23 AI 的 SRE](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：SLO、on-call 与事故响应。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：生产所需的审计与安全控制。
- [阶段 15 · 16 Checkpoints 与 Rollback](../../../15-autonomous-systems/16-checkpoints-rollback/docs/zh.md)：回滚与恢复的实现。

### 延伸关键词
`prototype / pilot / production` · `stage drift` · `exit criteria` · `bounded pilot` · `SLO` · `on-call` · `rollback receipt` · `retirement path` · `spiral model` · `continuous experimentation` · `canary release` · `access control` · `ownership`
