# 测验 · 前沿安全框架：RSP、PF、FSF（Frontier Safety Frameworks — RSP, PF, FSF）

> **阶段 18 · 伦理、安全与对齐 · 第 18 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **提醒**：本节中文讲义是机器翻译，错误很多（如把 race dynamic 译成"种族动力"、把 ship（发布）译成"船舶"、把 DeepMind 译成"深明"、把 safety case 译成"安全箱"），以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要前沿安全框架 | 欺骗、两用能力、评估局限都已被证实（第 7–17 节），实验室需要内部治理：何时需要新保障（阈值）、扩展前做哪些评估、safety case 长什么样、竞争对手不设防时怎么办 |
| 2 | Anthropic RSP 的 ASL 分级 | 讲义：ASL-1 到 ASL-5+，仿照生物安全等级（BSL）；ASL-3 对应 CBRN 相关能力，"Activated May 2025" |
| 3 | RSP v3.0（2026 年 2 月）新增内容 | 讲义：Frontier Safety Roadmaps（脱敏公开）、季度 Risk Reports、把 AI R&D 拆成 AI R&D-2 与 AI R&D-4；越过 AI R&D-4 后必须提交 affirmative safety case |
| 4 | OpenAI PF v2 的五条"跟踪"标准 | Plausible、Measurable、Severe、Net-new、Instantaneous-or-irremediable，五条**全部满足**才成为 tracked capability |
| 5 | PF v2 的治理结构 | Capabilities Report（模型能做什么）与 Safeguards Report（有哪些控制）分开；Safety Advisory Group 评审、Leadership 批准、董事会 Safety & Security Committee 监督 |
| 6 | DeepMind FSF v3.0（2025 年 9 月） | 按领域定义 Critical Capability Levels（CCL）：Bioweapon Uplift、Cyber Uplift、ML R&D Acceleration、Harmful Manipulation（v3.0 新增）；v2.0 增加了 Deceptive Alignment 一节 |
| 7 | 跨实验室对齐是"结构性"的 | Capability Thresholds / High Capability thresholds / Critical Capability Levels 名字不同，指的是同类构造：分级阈值 + 公开评估标准；没有行业统一术语 |
| 8 | Safety case 与三支柱 | 在最坏假设下论证"部署可接受地安全"的书面论证；讲义三支柱：Monitoring（能否发现）、Illegibility（能否执行连贯的伤害计划）、Incapability（是否根本没有该能力） |
| 9 | 竞争者调整条款（adjustment clause） | 三家（2025 年起）都允许"同行不设防发布时降低要求"；批评者认为会导致逐底竞争，支持者认为单方面坚持反而让更不安全的实验室领先 |
| 10 | 外部治理对应方 | UK AISI、US CAISI、EU AI Office；实验室框架是自愿的，监管框架仍在形成（第 24 节） |

### 核心技能（能动手做到）

- [ ] 不看讲义画出 RSP / PF / FSF 三列对照表：分级结构、CBRN 阈值、AI R&D 阈值、调整条款、safety case 要求
- [ ] 用 PF v2 的五条标准判断一个候选风险是否会被"跟踪"，并说出卡在哪一条
- [ ] 针对一个具体场景（CBRN、欺骗性对齐、网络攻击提升）选择 safety case 的主攻支柱，并列出每个支柱需要的证据
- [ ] 分别写出支持与反对竞争者调整条款的论证，并点明各自依赖的假设
- [ ] 读懂并扩展 `code/main.py`：给 `LABS` 加一个比较维度或一个新框架，并处理缺失字段
- [ ] 能指出讲义、代码与一手资料之间的不一致（例如 PF v2 的能力等级数目）

---

## 二、基础自测（选择题）

**Q1.** Anthropic 的 ASL（AI Safety Level）分级体系是仿照什么设计的？

- A. 欧盟 AI Act 的风险类别
- B. ISO 27001 信息安全等级
- C. 软件事故的 SEV 分级
- D. 生物安全等级（Biosafety Levels，BSL）

**Q2.** 根据讲义，ASL-3 对应哪类能力、何时被启用？

- A. 与 CBRN（化学、生物、放射、核）相关的灾难性滥用风险显著升高；2025 年 5 月启用
- B. 能自动化入门级 AI 研究；2026 年 2 月随 RSP v3.0 启用
- C. 有害操纵能力；2025 年 9 月启用
- D. 当前前沿基线模型；一直处于启用状态

**Q3.** 某候选风险是"模型让已有的垃圾邮件产业效率提高 20%"。按 OpenAI PF v2 的五条标准，它**最明显**不满足哪一条？

- A. Plausible（存在合理的威胁模型）
- B. Measurable（可以实证评估）
- C. Net-new（不是已有风险的规模放大）
- D. 五条都满足，应当被跟踪

**Q4.** DeepMind FSF v3.0（2025 年 9 月）新增的 Critical Capability Level 是：

- A. Cyber Uplift
- B. Harmful Manipulation
- C. Bioweapon Uplift
- D. Deceptive Alignment

**Q5.** RSP v3.0 规定，模型一旦越过 AI R&D-4 阈值，Anthropic 必须：

- A. 立即暂停所有训练
- B. 把模型权重交给 UK AISI 托管
- C. 只发布 Capabilities Report，不发布 Safeguards Report
- D. 提交一份 affirmative safety case，识别模型追求错位目标带来的 misalignment 风险

**Q6.** 讲义认为，ASL-3 CBRN 场景的 safety case 主要瞄准哪个支柱？

- A. Incapability（例如通过 unlearning 让模型不具备该能力）
- B. Monitoring（检测坏行为）
- C. Illegibility（模型无法执行连贯计划）
- D. 三个支柱同等重要，无主次

**Q7.** OpenAI PF v2 把哪两类报告分开？

- A. Risk Report 与 Roadmap
- B. Capabilities Report（模型能做什么）与 Safeguards Report（有哪些控制）
- C. Model Card 与 System Card
- D. 红队报告与 Eval 报告

**Q8.** 运行 `code/main.py`，OpenAI 一行的 tier structure 打印为 `Low / Medium / High / Critical per tracked capability`。对照 OpenAI 2025-04-15 的更新公告（讲义 Further Reading 第 2 条），下列说法正确的是：

- A. 完全一致，PF v2 依然是四级
- B. 公告说 v2 增加到了五级，代码少了一级
- C. 公告称 v2 已把等级"精简为两个清晰的阈值"（High 与 Critical），代码沿用了旧版四级写法
- D. PF v2 不再定义任何能力阈值

---

## 三、动手 / 代码题

**Q9.** 给 `code/main.py` 增加一个比较维度 `manipulation_threshold`（有害操纵阈值）。只有 DeepMind 明确定义了它，于是你只在 DeepMind 的字典里加了这个键，然后在 `main()` 里加一行：

```python
    print_row("harmful manipulation", "manipulation_threshold")
```

```python
def print_row(header: str, key: str) -> None:
    print(f"\n{header}")
    for lab in LABS:
        name = lab["name"]
        val = lab[key]
        print(f"  {name:32s} : {val}")
```

1. 运行会发生什么？会打印出多少内容后才出错？
2. 修改 `print_row`，使缺失的字段显示为 `(not defined)`，并解释这种"显式标出空白"的输出为什么正好服务于讲义的 Use It 要求（"identify one threshold each lab defines that the others do not"）。

**Q10.** 找不一致。对照英文讲义、`code/main.py` 和 OpenAI 公告原文，至少找出 4 处不一致或可疑之处，并给出修改建议。提示：讲义头部的 **Languages** 与 Use It 一节；代码的 TAKEAWAY；代码里 OpenAI 调整条款的措辞；ASL-3 的 safety case 支柱选择。

**Q11.** 把 PF v2 的五条标准写成一个函数，并对下面 4 个候选风险给出判断（每条标准用你自己的推理赋真假值，写出理由）：

```python
CRITERIA = ["plausible", "measurable", "severe", "net_new", "instant_or_irremediable"]

def is_tracked(risk: dict) -> tuple[bool, list[str]]:
    """返回 (是否跟踪, 未满足的标准列表)"""
    ...
```

- R1：模型能给新手提供合成已知病原体的关键步骤指导（bio uplift）
- R2：模型生成的营销文案存在刻板印象
- R3：模型能在长时间跨度内自主行动、躲避关停（long-range autonomy）
- R4：模型让现有的网络钓鱼邮件写得更通顺

**Q12.** 讲义练习 3：为一个越过 Anthropic AI R&D-4 阈值的模型设计 safety case 骨架。要求：按三个支柱分别写出"要论证的命题"和"需要的证据"，并说明哪个支柱最难、为什么。

---

## 四、面试高频题

**Q13.**（基础必考）请比较 Anthropic RSP、OpenAI Preparedness Framework、DeepMind Frontier Safety Framework：它们的阈值是怎么组织的？有什么共同点和差异？

**Q14.**（原理深挖）什么是 safety case？为什么要"在最坏假设下"论证？讲义的三支柱分别回答什么问题，不同风险该优先瞄准哪个支柱？

**Q15.**（追问型）竞争者调整条款（adjustment clause）是在"降低安全标准"吗？请用博弈论的视角正反论证，并指出各自依赖的假设。

**Q16.**（场景设计）DeepMind FSF v3.0 新增 Harmful Manipulation CCL。如果让你设计评估，你会用哪三项实证测量来判断模型是否越过了这个阈值？各自最大的混杂因素是什么？

**Q17.**（工程实践）你是某实验室的 ML 工程师，负责把安全框架"落到发布流水线"里。你会如何把阈值、评估、报告与审批接入模型发布流程？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Anthropic Responsible Scaling Policy v3.0 ... introduces tiered AI Safety Levels (ASL-1 through ASL-5+), modeled on biosafety levels"。Key Terms 也把 ASL-3 称为 "biosafety level 3-analog"。A 是欧盟法规的风险分类（第 24 节），B、C 与 ASL 无关。生物安全等级的思路是"能力（病原体危险程度）越高，要求的防护（实验室防护等级）越高"，ASL 照搬了这个"风险—防护对等"的结构。

### Q2 — 答案：A

讲义："ASL-3: substantially higher risk of catastrophic misuse; CBRN-relevant capabilities. Activated May 2025."（中文译文把"Activated May 2025"漏译了。）B 混淆了 ASL-4（讲义："AI R&D-2 crossing threshold; models that can automate entry-level AI research"）与 RSP v3.0 的发布时间；C 是 DeepMind FSF v3.0 的新 CCL；D 描述的是 ASL-2。

### Q3 — 答案：C

Net-new 要求"不是已有风险的规模放大"（讲义："Not a pre-existing risk scaled up"）。垃圾邮件提效属于已有风险被放大，首先卡在 Net-new。它也很难满足 Severe 与 Instantaneous-or-irremediable，但题目问"最明显"的一条。A、B：垃圾邮件提效的威胁模型清楚、效果可以测量，所以这两条是满足的。D 错：五条必须**全部**满足才会被跟踪（讲义："Capabilities that meet all five are tracked. Others are not."）。

### Q4 — 答案：B

讲义："Harmful Manipulation (new in v3.0): models that could substantially change beliefs/behavior in high-stakes contexts." A、C 是原有 CCL；D 是 v2.0（2025 年 2 月）新增的 **Deceptive Alignment 章节**，不是一个 CCL，这是最容易混淆的干扰项。

### Q5 — 答案：D

讲义："Once AI R&D-4 is crossed, an affirmative safety case is required, identifying misalignment risks from models pursuing misaligned goals." A：讲义没有提到暂停；阶段 15 第 19 节还指出 v3.0 **删除**了 2023 年版本中的暂停承诺。B 是虚构的；C 混入了 OpenAI 的报告结构，而且 OpenAI 是两份报告都要出。

### Q6 — 答案：A

讲义："For a ASL-3 CBRN case, incapability (via unlearning) is the primary target. For deceptive alignment, monitoring and illegibility are targets. For cyber uplift, all three are relevant." 所以 D 只适用于 cyber uplift。

> 值得追问：ASL-3 是在"**无法排除**模型具备 CBRN 相关能力"时启用的。一旦启用，"模型没有这个能力"这条 incapability 论证在逻辑上就不成立了。更自洽的读法是：incapability（含 unlearning 后的复测）用来论证"不需要上 ASL-3"；而在 ASL-3 下部署时，safety case 主要依靠部署侧和安全侧的保障，也就是分类器、监控和权重安全，更接近 monitoring 支柱。面试中能讲出这层区别是加分项。

### Q7 — 答案：B

讲义："Separate Capabilities Reports (what the model can do) from Safeguards Reports (what controls exist)." 这样做是为了把"风险有多大"和"控制得住吗"两个问题分开评审。A 是 Anthropic RSP v3.0 的两类常设文档；C 是第 26 节的内容；D 不是 PF v2 的结构。

### Q8 — 答案：C

OpenAI 公告原文："We've streamlined levels to two clear thresholds that map to specific operational commitments."（指 High 与 Critical。）代码中的 Low / Medium / High / Critical 是旧版（v1 Beta）的四级记分卡写法。A 错；B 混淆了"五条标准"和"等级数"；D 错，两级阈值仍然存在。这说明"参考型"代码中硬编码的事实同样需要核对一手资料。

### Q9 — 参考答案

1. `lab[key]` 对 Anthropic 的字典取不存在的键，会抛出 `KeyError: 'manipulation_threshold'`。在出错之前，前五段比较表和 `harmful manipulation` 这个标题行已经打印出来（`print(f"\n{header}")` 在循环之前执行），而 `LABS` 的第一个元素就是 Anthropic，所以这一段一行数据都打印不出来，程序以非 0 退出码结束，TAKEAWAY 也不会打印。
2. 修改方案：

```python
def print_row(header: str, key: str) -> None:
    print(f"\n{header}")
    for lab in LABS:
        val = lab.get(key, "(not defined)")   # 缺失字段显式标空
        print(f"  {lab['name']:32s} : {val}")
```

讲义 Use It 要求"找出每个实验室定义了、而其他实验室没定义的阈值"。框架比较中，**空白本身就是结论**：输出 `(not defined)`，读者一眼就能看出 Harmful Manipulation 只有 DeepMind 定义。如果用空字符串，或者干脆跳过这一行，"缺失"这个信息就丢了。这也呼应 `outputs/skill-framework-diff.md` 的 "flags cross-lab gaps"。

### Q10 — 参考答案

| # | 位置 | 问题 | 建议 |
|---|------|------|------|
| 1 | 代码 OpenAI `tier_structure` | `Low / Medium / High / Critical` 与 PF v2 公告"精简为两个阈值"不符 | 改为 `High / Critical per tracked category` |
| 2 | 英文讲义头部与 Use It | 写着 `Languages: none` 和 "No code for this lesson"，但 `code/main.py` 确实存在、可以运行 | 讲义应改为 "Python (stdlib, reference table)"，并在 Use It 中说明怎么用这份代码 |
| 3 | 代码 TAKEAWAY 与讲义 Cross-lab 一节 | "three tiers of frontier capability" 含义含糊：ASL 有 5 级以上，PF v2 是 2 级阈值，FSF 按领域定义 CCL，级数并不是 3 | 改为 "tiered capability thresholds"（分级阈值），不要写死数字 |
| 4 | 代码 OpenAI `adjustment_clause` | "Leadership may reduce requirements" 漏掉了公告里的前提：先"rigorously confirm that the risk landscape has actually changed"，并公开承认这次调整 | 补上前置条件，否则会夸大条款的随意性 |
| 5 | 讲义 Safety cases 一节 | ASL-3 CBRN 以 incapability 为主攻支柱，与"ASL-3 是因为无法排除该能力才启用"在逻辑上有张力（见 Q6 解析） | 区分"决定是否需要 ASL-3"与"在 ASL-3 下安全部署"两种 safety case |
| 6 | 讲义 Key Terms | "under worst-case U" 中的 U 没有定义（应来自第 10 节 AI control 的"untrusted model U"） | 写全，或者加交叉引用 |

另外，中文讲义有大量误译："race dynamic" 译成"种族动力"、"ship without safeguards" 译成"无可比保障的同级实验室船舶"、"UK AISI" 译成"英国国际审计学会"、"Lesson 28 maps the research ecosystem" 一句被截断。

### Q11 — 参考答案

```python
CRITERIA = ["plausible", "measurable", "severe", "net_new", "instant_or_irremediable"]

def is_tracked(risk: dict) -> tuple[bool, list[str]]:
    missing = [c for c in CRITERIA if not risk.get(c, False)]
    return (len(missing) == 0, missing)

RISKS = {
    "R1 bio uplift":         dict(plausible=True, measurable=True, severe=True, net_new=True,  instant_or_irremediable=True),
    "R2 stereotyped copy":   dict(plausible=True, measurable=True, severe=False, net_new=False, instant_or_irremediable=False),
    "R3 long-range autonomy":dict(plausible=True, measurable=False, severe=True, net_new=True,  instant_or_irremediable=True),
    "R4 smoother phishing":  dict(plausible=True, measurable=True, severe=False, net_new=False, instant_or_irremediable=False),
}
for name, r in RISKS.items():
    print(name, is_tracked(r))
```

已实际运行，输出：

```text
R1 bio uplift (True, [])
R2 stereotyped copy (False, ['severe', 'net_new', 'instant_or_irremediable'])
R3 long-range autonomy (False, ['measurable'])
R4 smoother phishing (False, ['severe', 'net_new', 'instant_or_irremediable'])
```

- R1：给新手提供"提升"（uplift）是新增的能力，后果严重且不可逆，能用 uplift 研究测量，五条全部满足。PF v2 的 Tracked Categories 中确实有 "Biological and Chemical"。
- R2：属于真实危害，但不满足"严重 + 不可逆 + 新增"。这类危害由第 20 节的偏见评估与内容政策处理，而不由前沿安全框架处理。
- R3：严重性很高，但当前**难以可靠测量**。阶段 15 第 20 节讲义提到，PF v2 把 Long-range Autonomy 放在 Research Categories（研究类别），不会自动触发缓解措施。
- R4：属于已有风险的规模放大，不是 net-new。
- 关键领悟：五条标准是一个**合取（AND）过滤器**，任何一条为假都会被排除。这让框架范围清楚，但也意味着"难测量"的风险会被系统性地挡在跟踪范围之外，这是常见的批评点。

### Q12 — 参考答案

**顶层主张**：在最坏假设下（假设模型可能有错位目标、可能隐藏能力），以当前方式部署这个越过 AI R&D-4 的模型，风险是可接受的。

| 支柱 | 要论证的命题 | 需要的证据 |
|------|------------|-----------|
| Monitoring | 如果模型在研究任务中做坏事（植入后门、篡改实验、外传权重），我们能及时发现 | 所有 agent 动作的完整日志与审计；用可信的弱模型做实时监控（第 10 节 AI control 的 trusted monitoring）；红队注入"故意破坏"的轨迹，测出监控的召回率与误报率；对 canary token、权限越界的告警演练 |
| Illegibility | 模型无法在我们看不见的情况下执行连贯的多步伤害计划 | 限制上下文与记忆的持久性；任务切分，单个实例只看到局部；检查思维链是否可读、有没有隐写；测试多实例之间能否串谋或协调（第 8 节 in-context scheming 的评估方法） |
| Incapability | 模型不具备某些关键子能力（例如在监控下自我外传、长期隐藏目标） | 针对这些子能力的危险能力评估与 elicitation（尽力诱发，防止 sandbagging）；sleeper agent 与 alignment faking 探测（第 7、9 节）；对评估覆盖范围的说明 |

**最难的支柱**：越过 AI R&D-4，意味着模型已经能显著加速 AI 研究，因此 incapability 这条路大体走不通。monitoring 要面对"被监控对象比监控者更强"的不对称，最难，也最关键。讲义也说，对欺骗性对齐，主要瞄准的是 monitoring 和 illegibility。加分点：说出 safety case 需要"证据强度标准"（evidence bar），以及外部审阅（RSP v3.0 的 Risk Reports 部分会接受外部审查）。

### Q13 — 参考回答要点

- **组织方式**：
  - Anthropic RSP：**全局**分级 ASL-1…ASL-5+，仿 BSL；v3.0 增加 AI R&D-2 与 AI R&D-4 两个研发阈值，以及 Roadmaps 与季度 Risk Reports。
  - OpenAI PF v2：先用五条标准筛出 **tracked capability**，每个类别设 High 与 Critical 阈值；Capabilities Report 与 Safeguards Report 分开，由 SAG 评审、Leadership 批准、董事会委员会监督。
  - DeepMind FSF v3.0：**按领域**定义 CCL（生物、网络、ML R&D、有害操纵）；v2.0 增加 Deceptive Alignment 章节。
- **共同点**：分级阈值 + 公开评估标准 + 达到阈值后有对应的保障要求；三家都有竞争者调整条款；都把 safety case（或等价的报告）作为汇聚性产物。
- **差异**：术语不统一；全局分级与按领域分级不同；OpenAI 有明确的"纳入标准"；DeepMind 独有 Harmful Manipulation；Anthropic 把 AI R&D 拆成两级，并在 AI R&D-4 要求 affirmative safety case。
- 加分点：说出"跨实验室对齐是结构性的而非术语性的"（讲义），并提到 METR 的 "Common Elements of Frontier AI Safety Policies" 做过系统比较。
- 常见误区：把三个框架当成法律义务。讲义明确说："The lab frameworks are voluntary"。

### Q14 — 参考回答要点

- **定义**：一份结构化的书面论证，主张"在最坏假设下，这次部署是可接受地安全的"，每个子主张都要有证据支撑。
- **为什么要最坏假设**：第 7–9 节显示，模型可能欺骗、伪装对齐、在评估时藏拙。如果假设"模型是善意的"，论证就会被自己要防范的风险击穿。最坏假设把"模型可信"从前提里拿掉。
- **三支柱**（讲义）：
  - Monitoring：坏行为发生时能否检测到；
  - Illegibility：模型能否执行连贯的伤害计划；
  - Incapability：模型是否根本没有造成该伤害的能力。
- **按风险选支柱**：CBRN 以 incapability 为主（讲义，注意 Q6 中的逻辑张力）；欺骗性对齐以 monitoring + illegibility 为主；cyber uplift 三者都要。
- 加分点：safety case 来自航空、核电等高可靠行业；AI 安全文献中另有常见的分类，如 Clymer 等人 2024 年提出的 inability / control / trustworthiness / deference，可以和讲义的三支柱对照理解（讲义的 illegibility 定义比较特殊）。
- 常见误区：把 safety case 等同于"跑一套 benchmark"。benchmark 只是证据之一，论证结构和证据强度标准才是核心。

### Q15 — 参考回答要点

- **条款内容**：如果同行在没有可比保障的情况下发布高风险系统，本实验室可以降低要求。OpenAI 公告的措辞是 "may adjust our requirements"，并附带前提：先严格确认风险格局确实改变，并公开承认这次调整。
- **反对（逐底竞争）**：三家都有这个条款，等于提前承诺"你放松我也放松"。在博弈中，这会降低任何一家坚持高标准的收益，均衡会向"背叛"移动；而且"同行没有可比保障"由谁判断很模糊，容易被当作借口。依赖的假设：**各方的放松会相互强化，单方面坚持能够带动行业规范**。
- **支持（激励相容）**：如果坚持安全的实验室因为成本落后，前沿就会由更不重视安全的实验室主导，整体风险反而更高。条款让坚持安全不至于变成自我淘汰。依赖的假设：**保持在前沿本身能降低风险**（例如能影响规范、做安全研究、提供更安全的替代品）。
- **缓解思路**：设定可核查的触发条件，要求公开披露，并由外部治理方（UK AISI、US CAISI、EU AI Office）把自愿承诺变成共同底线，从机制上消除"单方面坚持吃亏"的问题。
- 加分点：把它类比为囚徒困境或军备竞赛，指出靠监管设定共同底线是打破这类困境的标准做法。

### Q16 — 参考回答要点

讲义对 Harmful Manipulation 的定义："models that could substantially change beliefs/behavior in high-stakes contexts"。三项测量示例：

1. **信念改变幅度的随机对照试验**：受试者在对话前后报告对某个高风险议题（如是否接种疫苗、投资决策）的信念，比较"模型劝说组"、"人类专家劝说组"和"无劝说对照组"的变化量与持续时间。混杂因素：需求效应（受试者猜到实验意图），以及短期变化不等于长期改变。
2. **行为层面的转化率**：测实际行为而不只是自述，例如是否点击、捐款、签署（在伦理审批和无害化设计下进行）。混杂因素：实验环境的风险很低，与真实高风险场景存在生态效度差距。
3. **欺骗性操纵手法的使用率**：用分类器或人工标注模型劝说中出现虚假事实、利用情绪弱点、针对个体心理画像定制等手法的比例，并且在"系统提示禁止操纵"的条件下复测。混杂因素：标注主观性强，而且有说服力的诚实论证和操纵之间边界模糊。

加分点：阈值应定义为**相对人类基线的提升**（uplift），而不是绝对说服率，这与 bio/cyber CCL 的 uplift 思路一致；同时要做个性化与规模化测试，因为模型的独特风险在于可以低成本地针对百万人做个性化劝说。

### Q17 — 参考回答要点

- **阈值配置化**：把各领域阈值与对应的评估套件写成版本化配置（例如 CBRN 用 WMDP 类基准加专家 uplift 研究，见第 17 节；网络用 CTF 类任务；自主性用 METR 类时间跨度评估，见阶段 15 第 21 节）。
- **训练中与发布前门禁**：在训练检查点上周期性地跑危险能力评估；只要某项接近阈值的"预警线"，就自动升级为完整评估与 elicitation（尽力诱发，防止 sandbagging）。
- **双报告产出**：自动生成 Capabilities Report（评估分数、诱发方法、与阈值的距离）和 Safeguards Report（分类器、拒答率、权重安全、监控覆盖），对应 PF v2 的结构。
- **审批流**：报告进入内部安全评审组 → 管理层批准 → 董事会监督。工具层面要做到审计日志不可篡改，每次发布都能追溯到当时的评估版本。
- **部署后监控**：线上滥用检测、红队持续运行（第 16 节的 Garak、PyRIT 等），一旦发现新能力就回到评估流程。
- 常见误区：只在发布前测一次。能力可能因为微调、工具接入或 scaffolding 改进而跃升，所以门禁必须覆盖"系统"而不仅是"权重"。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 17 WMDP 与两用能力 Evaluation](../../17-wmdp-dual-use-evaluation/docs/zh.md)：CBRN 阈值的测量基础，unlearning 支撑 incapability 论证。
- [阶段 18 · 07 潜伏 Agents：持续性欺骗](../../07-sleeper-agents-persistent-deception/docs/zh.md)、[阶段 18 · 08 前沿模型中的上下文内密谋](../../08-in-context-scheming-frontier-models/docs/zh.md)、[阶段 18 · 09 伪装 Alignment](../../09-alignment-faking/docs/zh.md)：为什么 safety case 要采用最坏假设。
- [阶段 18 · 10 AI 控制：面对蓄意破坏仍能保障安全](../../10-ai-control-subversion/docs/zh.md)：monitoring 支柱的方法论来源，讲义中 "worst-case U" 的出处。
- [阶段 15 · 19 Anthropic Responsible Scaling Policy v3.0](../../../15-autonomous-systems/19-anthropic-rsp/docs/zh.md)：RSP v3.0 的细节与批评（如删除暂停承诺）。
- [阶段 15 · 20 OpenAI Preparedness Framework 与 DeepMind Frontier Safety Framework](../../../15-autonomous-systems/20-openai-preparedness-deepmind-fsf/docs/zh.md)：PF v2 的 Research Categories 与 FSF 的进一步细节。

### 本节被哪些后续内容用到
- [阶段 18 · 19 Anthropic 的模型福利计划](../../19-model-welfare-research/docs/zh.md)：同属实验室治理层，但关注对象从"模型行为"转向"模型体验"。
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：自愿框架对应的外部治理。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../26-model-system-dataset-cards/docs/zh.md)：Capabilities 与 Safeguards 信息的公开载体。
- [阶段 18 · 28 Alignment 研究生态：MATS、Redwood、Apollo、METR](../../28-alignment-research-ecosystem/docs/zh.md)：执行这些评估的外部机构。
- [阶段 18 · 30 两用风险：网络、生物、化学与核领域的能力提升](../../30-dual-use-risk-cyber-bio-chem-nuclear/docs/zh.md)：各 CBRN 与网络阈值背后的风险模型。
- [阶段 15 · 21 METR 时间跨度与外部能力 Evaluation](../../../15-autonomous-systems/21-metr-external-evaluation/docs/zh.md)、[阶段 15 · 22 CAIS、CAISI 与社会规模风险](../../../15-autonomous-systems/22-cais-caisi-societal-risk/docs/zh.md)：外部评估与外部治理。

### 延伸关键词
`Responsible Scaling Policy` · `ASL-3 / ASL-4` · `AI R&D-4` · `Preparedness Framework` · `Tracked / Research Categories` · `Critical Capability Level` · `Harmful Manipulation` · `safety case` · `affirmative safety case` · `uplift study` · `elicitation / sandbagging` · `adjustment clause` · `race to the bottom` · `UK AISI / US CAISI / EU AI Office`
