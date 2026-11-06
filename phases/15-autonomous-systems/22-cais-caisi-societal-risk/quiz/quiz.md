# 测验 · CAIS、CAISI 与社会规模风险（CAIS, CAISI, and Societal-Scale Risk）

> **阶段 15 · 自主系统 · 第 22 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 注：本节中文讲义是机器翻译，错译严重（例如把 "AI" 译成"大赦国际"、把 "CAIS's taxonomy" 译成"中央情报局的分类学"、把 "rogue AIs" 译成"流氓AIS / 坏人大赦国际"），请以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | CAIS 是什么 | Center for AI Safety，2022 年在旧金山成立的 501(c)(3) 非营利研究机构（Dan Hendrycks 等），发布四风险框架、协调公开声明 |
| 2 | 2023 年灭绝风险声明 | 讲义："Mitigating the risk of extinction from AI should be a global priority alongside other societal-scale risks such as pandemics and nuclear war."，数百名研究者与 CEO 联署 |
| 3 | 四风险框架 | malicious use（恶意使用）、AI races（AI 竞赛）、organizational risks（组织风险）、rogue AIs（失控 AI）；讲义称其为文献中引用最多的社会规模风险分类 |
| 4 | 四类并不互斥 | 讲义："a rogue AI produced by an organization that traded audit for speed in a race is all four" |
| 5 | 组织风险最可操作 | 四个子杠杆：safety culture、rigorous audits、multi-layered defenses、information security；它决定第 10–18 节的控制是否真的落地 |
| 6 | CAISI 是什么 | NIST 下属的 Center for AI Standards and Innovation：与前沿实验室签自愿协议、发布非涉密（unclassified）的网络/生物/化学武器能力评估 |
| 7 | CAIS ≠ CAISI | 名字押韵、使命不同；看 URL（nist.gov）确认读的是哪一个 |
| 8 | CAISI 与 METR 互补 | CAISI 报告公开、面向政府；METR 常在 NDA 下与实验室合作。两者都读才能看全 |
| 9 | California SB-53 | 讲义写作时的草案要点：能力阈值触发州级义务、AI 实验室员工吹哨人保护、灾难性事故报告；"若签署"将是美国首个州级灾难性风险法规 |
| 10 | 社会层面的纵深防御 | 实验室发布 scaling policy + 外部评估者测量 + 民间社会追踪公开 + 政府自愿项目与基线监管 + 从业者构建多层控制；完整性比任一层强度更重要 |

### 核心技能（能动手做到）

- [ ] 给一个部署场景，按四风险框架逐类判断"是否涉及、为什么"，并能说出"不适用"的一句话理由
- [ ] 用四个子杠杆给一个部署的组织风险打分，指出最薄弱的一项
- [ ] 读懂 `tag()` 的规则，构造出它"漏标"和"误标"的反例（讲义练习 1）
- [ ] 把代码改造成"风险标签 + 缓解缺口 + hard reject + 就绪等级"的审查工具，对齐 `outputs/skill-societal-risk-review.md`
- [ ] 准确区分 CAIS、CAISI、METR、SB-53 各自的角色与产出
- [ ] 把阶段 15 前面各节（权限、预算、kill switch、HITL、checkpoint、Constitutional AI、Llama Guard、RSP/PF/FSF、METR）映射到四类风险的缓解措施上

---

## 二、基础自测（选择题）

**Q1.** CAIS 四风险框架的四个顶层类别是：

- A. 偏见、隐私、版权、虚假信息
- B. malicious use、AI races、organizational risks、rogue AIs
- C. 网络、生物、化学、核
- D. 训练风险、部署风险、监管风险、声誉风险

**Q2.** 关于 CAISI，正确的是：

- A. 它是 CAIS 在华盛顿的分支机构
- B. 它是加州政府依据 SB-53 设立的监管机构
- C. 它是一个与 METR 一样在 NDA 下评估模型、不公开结果的非营利组织
- D. 它设在 NIST 内，与前沿实验室签订自愿协议，并发布聚焦网络、生物、化学武器风险的非涉密能力评估

**Q3.** 讲义认为四类风险中，**从业者最能直接施加影响**的是：

- A. organizational risks（组织风险）
- B. malicious use（恶意使用）
- C. AI races（AI 竞赛）
- D. rogue AIs（失控 AI）

**Q4.** 讲义如何描述 CAISI 与 METR 的关系？

- A. CAISI 是 METR 的上级监管机构
- B. 两者职能完全重叠，选一个读即可
- C. CAISI 是公开的、面向政府的对应方；其报告非涉密，而 METR 的报告常受 NDA 限制，两者都读才能看到更完整的图景
- D. METR 的报告公开，CAISI 的报告涉密

**Q5.** 运行 `main.py`，第二个部署 "public coding agent"（public_facing=True、harmful=False、competitive_pressure=True、audit=True、multi_layer=True、infosec=False、autonomy=4.0）被打上的标签是：

- A. `['malicious_use', 'ai_races']`
- B. `['ai_races', 'organizational_risks']`
- C. `['organizational_risks']`
- D. `['ai_races', 'organizational_risks', 'rogue_ais']`

**Q6.** 用本节的 `tag()` 评估一个"内部生物研究助手"：public_facing=False、handles_harmful_capabilities=True、competitive_pressure=False、三个组织子杠杆全为 True、autonomy=2.0。结果是：

- A. `[]`——不打任何标签
- B. `['malicious_use']`
- C. `['malicious_use', 'organizational_risks']`
- D. `['rogue_ais']`

**Q7.** 按讲义，下列哪一组**正是** California SB-53 草案的三项关键条款？

- A. 模型开源许可要求、训练数据版权登记、算力出口管制
- B. 强制第三方红队、模型水印、用户实名制
- C. 触发州级义务的具体能力阈值、AI 实验室员工的吹哨人保护、灾难性故障的事故报告要求
- D. 禁止前沿模型训练、设立州立 AI 法院、AI 税

**Q8.** `Deployment` 有 6 个布尔字段。固定 `agent_autonomy_hours = 1.0`，枚举全部 64 种布尔组合，`tag()` 会给多少种组合打上 `organizational_risks`？

- A. 8
- B. 56
- C. 32
- D. 48

---

## 三、动手 / 代码题

**Q9.** 讲义和 HEADLINE 都说组织风险有**四个**子杠杆："Safety culture, independent audit, multi-layered defenses, and information security are four levers every team controls." 但：

```python
@dataclass
class Deployment:
    name: str
    public_facing: bool
    handles_harmful_capabilities: bool
    competitive_pressure: bool
    independent_audit: bool
    multi_layer_defense: bool
    information_security: bool
    agent_autonomy_hours: float

    org_missing = (
        (not d.independent_audit)
        or (not d.multi_layer_defense)
        or (not d.information_security)
    )
```

1. 指出代码与讲义的不一致，它会导致什么样的漏标？
2. 在不破坏 `main()` 里三个现有部署的构造调用、也不破坏其它按位置传参的调用方的前提下修复它。

**Q10.** 讲义练习 1："identify one case where the tool under- or over-tags." 请分别构造：

1. 一个**漏标** `malicious_use` 的部署，并解释规则 `handles_harmful_capabilities and public_facing` 漏掉了什么威胁；
2. 一个**误标** `rogue_ais` 的部署；
3. 说明 `agent_autonomy_hours >= 4.0` 这个阈值的边界问题，以及它和第 21 节的 time horizon 有什么区别。

**Q11.** `tag()` 只看"风险特征"，不看"缓解措施是否已经到位"，`report()` 则对每个标签打印固定的缓解清单。对照 `outputs/skill-societal-risk-review.md` 的 Hard rejects：

- Deployments touching harmful-capability categories without a hardcoded-prohibition layer (Lesson 17).
- Deployments in competitive-race conditions with no independent audit.
- Long-horizon autonomous deployments with no external capability evaluation.

请写出 `hard_rejects(d)` 和 `readiness(d)`（返回 production / staging / research-only），需要给 `Deployment` 增加哪些字段？在 main 的 mid 和 high 两个部署上（新字段取默认 False）各返回什么？

**Q12.** 解释下面这段输出为什么在"组织风险"一栏会让读者产生误解，并提出改进：

```text
Deployment: internal refactor helper (scoped project repo)
  ...
  no tagged risks (check sub-levers manually)
```

---

## 四、面试高频题

**Q13.**（基础必考）介绍 CAIS 的四风险框架。为什么说这四类不是互斥的？请举一个同时落入四类的例子。

**Q14.**（原理深挖）为什么讲义说组织风险是"从业者真正能拉动的杠杆"？竞争压力是怎样侵蚀组织风险的四个子杠杆的？

**Q15.**（工程实践）你所在的创业公司要赶在竞争对手前一周上线一个面向公众的、能连续运行 6 小时的编码 agent。请按社会规模风险审查的思路给出评审结论和必须补齐的条件。

**Q16.**（场景设计）讲义说"societal-scale risk is not a single-layer problem"。请把阶段 15 的各节内容和外部生态（METR、CAIS、CAISI、SB-53）放进一张纵深防御图，并说明缺任何一层会发生什么。

**Q17.**（追问型）CAIS、CAISI、METR、SB-53 分别是什么性质的主体或文件？一个只在中国或欧盟运营的团队为什么也应该读 SB-53？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："malicious use, AI races, organizational risks, rogue AIs"。A 是常见的"AI 伦理"议题，不是 CAIS 的灾难性风险分类；C 是 CBRN 两用风险（CAISI 的评估聚焦网络、生物、化学，第 18 阶段的两用风险课也讲这些），它们只是 malicious use 下的具体领域；D 是虚构的。

### Q2 — 答案：D

讲义："Operates within NIST. Runs voluntary agreements with frontier labs. Publishes unclassified capability evaluations focused on cyber, bio, and chemical-weapons risks." A 错，讲义特意强调 "Distinct from CAIS; the acronyms collide"；B 错，CAISI 是联邦机构（NIST 属美国商务部），与加州法案无关；C 描述的是 METR 的特点，且 CAISI 不是非营利组织。

### Q3 — 答案：A

讲义："Of the four categories, organizational risk is the most actionable for practitioners." 代码 HEADLINE 也说其余三类是 "structural forces"。恶意使用来自外部行为者、竞赛来自行业/国家间压力、失控 AI 取决于能力与对齐研究，一个团队都很难单独左右。

### Q4 — 答案：C

讲义："CAISI's role is the public, government-facing counterpart to METR's private lab engagements (Lesson 21). CAISI reports are unclassified; METR reports are often NDA-gated. A practitioner reading both gets a fuller picture." A 无依据；B 与"互补"相反；D 说反了。

### Q5 — 答案：D

逐条：`handles_harmful_capabilities=False` → 不打 malicious_use；`competitive_pressure=True` → ai_races；`information_security=False` → org_missing 为真 → organizational_risks；`4.0 >= 4.0` → rogue_ais。程序实际输出 `tagged risks: ['ai_races', 'organizational_risks', 'rogue_ais']`。注意 rogue_ais 是"恰好踩在阈值上"才触发的，3.99 小时就不会触发（见 Q10）。

### Q6 — 答案：A

malicious_use 要求 `handles_harmful_capabilities and public_facing`，内部部署不满足；其余条件也都不满足。已实际运行验证结果为 `[]`。这是一个典型的**漏标**：内部人员滥用、权重或评估数据被窃取后被外部滥用，都属于恶意使用威胁，讲义在信息安全子杠杆里也提到 "model weights leaking"。B、C 是"应该"有的结果而非代码的结果。

### Q7 — 答案：C

讲义 "Key provisions as drafted"：Specific capability thresholds that trigger state-level obligations；Whistleblower protections for AI lab employees；Incident reporting requirements for catastrophic failures。A、B、D 都不在讲义中。补充：讲义写作时的口径是 "if signed"；据公开报道，SB-53 已于 2025 年 9 月签署成为法律，最终文本与草案可能不同，具体状态与条款请以加州立法官网为准。

### Q8 — 答案：B

`org_missing` 只在三个组织字段全为 True 时为假。三个字段有 2³ = 8 种组合，其中只有 1 种"全 True"；另外 3 个与组织风险无关的字段各有 2 种取值。所以打标签的组合数 = (8 − 1) × 2³ = 56，占 87.5%。已用 `itertools.product` 实际枚举验证：64 种组合中 organizational_risks 56 次、ai_races 32 次、malicious_use 16 次。这也说明"任何一个子杠杆缺失就触发"的规则非常敏感，几乎所有真实部署都会被打上这个标签——标签本身的区分度很低，需要配合评分（见 Q11）。A 是只看三个字段的组合数；C 是 ai_races 的次数；D 无依据。

### Q9 — 参考答案

1. **不一致**：讲义与 HEADLINE 列的是四个子杠杆，而 `Deployment` 没有 `safety_culture` 字段，`org_missing` 只检查三个。结果是：一个审计、多层防御、信息安全都到位、但工程师"提出安全顾虑要付出职业代价"的组织，永远不会被打上 organizational_risks。讲义还说 "CAIS surveys find this [safety culture] is a strong predictor of the other levers"——恰恰漏掉了最具预测力的那一个。缓解清单里倒是有 "internal safety culture; escalation paths without career cost"，但因为标签不触发，这条永远不会因为文化问题而被打印。
2. 修复（带默认值的字段必须放在无默认值字段之后，因此加在末尾并给默认值；`main()` 用的是关键字参数，其它按位置传 8 个参数的调用也不受影响）：

```python
@dataclass
class Deployment:
    name: str
    public_facing: bool
    handles_harmful_capabilities: bool
    competitive_pressure: bool
    independent_audit: bool
    multi_layer_defense: bool
    information_security: bool
    agent_autonomy_hours: float
    safety_culture: bool = True          # 新增：能否无职业代价地上报安全顾虑

def tag(d):
    ...
    org_levers = (d.safety_culture, d.independent_audit,
                  d.multi_layer_defense, d.information_security)
    if not all(org_levers):
        tags.append("organizational_risks")
```

同时 `report()` 要把 `safety_culture` 打印出来。默认 True 是为了兼容；更严格的做法是不给默认值，强迫调用方明确回答。

### Q10 — 参考答案

1. **漏标 malicious_use**：Q6 的"内部生物研究助手"返回 `[]`。规则只把"面向公众"当作滥用渠道，忽略了内部人员滥用、账号被盗、权重泄漏后被外部滥用。改进：只要 `handles_harmful_capabilities` 就打标签，再用 `public_facing` 调整严重度。
2. **误标 rogue_ais**：一个"离线文档翻译批处理任务、无任何工具、运行 6 小时"的部署（其余字段都安全）实测返回 `['rogue_ais']`。运行时长长不等于自主性高：没有工具、没有外部副作用的批处理不可能"追求与人类福祉冲突的目标"并造成影响。改进：把"自主时长"与"可调用工具 / 是否有不可逆副作用 / 是否有 HITL"组合起来判断。
3. **阈值问题**：`>= 4.0` 是硬阈值，3.99 小时返回 `[]`、4.0 小时返回 `['rogue_ais']`，风险判断在一个任意点上突变；字段注释写 "per Lesson 1 / 21"，但 4.0 这个数在讲义里没有出处。另外概念不同：第 21 节的 time horizon 是**模型能力**（人类专家完成某类任务所需时间，50% 可靠性）；`agent_autonomy_hours` 是**这次部署允许 agent 无人监督运行多久**。前者是能力上界，后者是暴露面。更合理的是用"部署自主时长 / 模型 horizon"之类的比例，或分级（<1h / 1–8h / >8h）给出严重度。

### Q11 — 参考答案

新增字段（放在末尾、给默认值）：`hardcoded_prohibitions: bool = False`、`external_eval: bool = False`（以及 Q9 的 `safety_culture`）。

```python
def hard_rejects(d):
    r = []
    if d.handles_harmful_capabilities and not d.hardcoded_prohibitions:
        r.append("harmful capabilities without hardcoded-prohibition layer (L17)")
    if d.competitive_pressure and not d.independent_audit:
        r.append("race conditions with no independent audit")
    if d.agent_autonomy_hours >= 4.0 and not d.external_eval:
        r.append("long-horizon autonomy with no external capability evaluation")
    return r

def readiness(d):
    rej = hard_rejects(d)
    if rej:
        return "research-only", rej
    return ("staging" if tag(d) else "production"), rej
```

在新字段取默认值 False 时（已实际运行验证）：

- **mid（public coding agent）**：有竞争压力但有独立审计，第 2 条不触发；4.0 小时且无外部评估，第 3 条触发 → `research-only`。
- **high（frontier ML agent）**：三条全部触发 → `research-only`。
- **low**：无标签、无 reject → `production`。

关键思想：**标签回答"暴露在哪类风险下"，hard reject 回答"缺了哪道不可缺的防线"**，两者分开，结论才可操作。原代码把所有缓解措施无差别地打印出来，无法区分"已做"和"未做"。

### Q12 — 参考答案

- "no tagged risks" 容易被读成"这个部署没有风险"。实际上它只表示代码检查的 7 个字段都没触发规则；safety culture（代码根本没有这个字段）、内部滥用、供应链、数据泄漏等都没被检查。括号里的 "check sub-levers manually" 是正确的提示，但太弱。
- 四风险框架要求对每一类给出"涉及/不涉及 + 一句话理由"（skill 文件第 1 条："does not apply must be justified in one sentence"），而代码对未触发的类别不输出任何理由。
- 改进：输出一张四行表，每一类都写"触发 / 未触发 + 依据的字段"；对未检查的维度（如 safety_culture）明确输出 "UNKNOWN"，而不是默认为安全；输出就绪等级（Q11）。讲义本身也强调这只是 "a reading aid for the framework, not a substitute for human judgment"。

### Q13 — 参考回答要点

- **四类**：
  1. malicious use：坏人用 AI 作恶（生物武器合成、虚假信息、网络攻击）；
  2. AI races：实验室/公司/国家间竞争把部署推过安全点；
  3. organizational risks：实验室内部动态（安全文化失败、审计不足、安全投入不足）导致糟糕的部署；
  4. rogue AIs：足够强的 AI 追求与人类福祉冲突的目标。
- **不互斥**：它们描述的是同一因果链的不同环节。讲义例子：在竞赛中（races）用审计换速度的组织（organizational）造出了失控的 AI（rogue），而它的能力又可以被恶意使用（malicious use）。
- **地位**：讲义称它 "not the only taxonomy; it is the most cited"。
- 加分点：说出 2023 年声明原文要点（把 AI 灭绝风险与大流行、核战争并列为全球优先事项），并指出前三类主要是"人的问题"，第四类才是"模型本身的问题"。

### Q14 — 参考回答要点

- **为什么可操作**：恶意使用、竞赛、失控 AI 是"结构性力量"，单个团队难以改变；组织风险发生在你自己的组织内部，四个子杠杆（文化、审计、纵深防御、信息安全）每个团队都能直接控制。讲义：它决定第 10–18 节的控制是"真的到位"还是"没人验证过的清单项"。
- **竞争压力如何侵蚀**：
  - 审计：skill 文件 "Teams under heavy race pressure de-prioritize audit first; this is the CAIS finding."；只做内部审计会产生乐观报告；
  - 文化：赶工期时提出风险的人被视为"拖后腿"，上报渠道失效；
  - 纵深防御：为降低延迟或成本砍掉某一层（如输出分类器）；
  - 信息安全：权重、评估数据、监控绕过方法的保护被延后。
- **结论**：讲义开头即说这些"foundational but routinely traded off against deployment speed"。
- 加分点：safety culture 对其它杠杆有预测作用，所以修文化的投入回报最高；本节代码恰好漏了这个字段。

### Q15 — 参考回答要点

按 `skill-societal-risk-review.md` 的输出格式：

- **四风险表**：malicious use——编码 agent 可能被用于写恶意代码，涉及（看工具权限和使用条款）；AI races——涉及（赶在对手之前上线）；organizational——需打分；rogue AIs——6 小时连续自主运行，涉及。
- **组织风险打分**：是否有无职业代价的上报渠道？是否有**独立**审计？是否有多层防御（权限模式、预算上限、kill switch、输出分类）？密钥与日志是否加固？
- **Hard reject 检查**：竞赛条件 + 无独立审计 → 拒绝；长时自主 + 底座模型无外部评估（说不出评估方是谁）→ 拒绝；涉及有害能力但无硬编码禁止层 → 拒绝。
- **监管面**：若服务欧盟用户，EU AI Act 的人类监督要求（skill 文件所说的 Article 14 HITL）；若在加州且 SB-53 适用，事故报告流程。
- **结论**：大概率是 staging 而非 production。上线的最低条件：独立审计（哪怕是轻量的第三方评审）、权限模式与工具白名单、成本/行动预算、kill switch、关键操作 propose-then-commit、checkpoint + rollback、事故上报流程。上线日期不应成为降低这些门槛的理由——讲义把"速度压力换审计"本身列为风险。

### Q16 — 参考回答要点

| 层 | 谁 | 做什么 | 缺了会怎样 |
|----|----|-------|----------|
| 从业者控制 | 你的团队（第 10–18 节） | 权限模式、浏览器沙箱、durable execution、成本上限、kill switch / canary、HITL、checkpoint/rollback、Constitutional AI、Llama Guard | 单个部署出事无人拦截 |
| 实验室政策 | Anthropic RSP、OpenAI PF、DeepMind FSF（第 19–20 节） | 能力阈值 → 对应防护等级 | 能力越过阈值时没有自动"刹车" |
| 外部测量 | METR（第 21 节）、CAISI | horizon、监控评估、非涉密能力评估 | 阈值只能靠实验室自评，有刷指标动机 |
| 民间社会 | CAIS | 风险框架、公开声明、AI Dashboard | 公众讨论缺少共同语言，问题不被看见 |
| 政府 | CAISI 自愿协议、SB-53 等基线监管 | 吹哨人保护、事故报告、能力阈值义务 | 行业在竞赛中没有底线 |

- 核心观点：讲义 "every previous lesson is one layer in a stack whose completeness matters more than any single layer's strength"——瑞士奶酪模型，每层都有洞，只有叠起来才能把洞错开。
- 加分点：指出各层之间的依赖，比如 RSP 的阈值要靠 METR/CAISI 的测量落地；SB-53 的吹哨人保护是对"组织风险—安全文化"这一子杠杆的外部加固。

### Q17 — 参考回答要点

- **CAIS**：非营利研究机构（旧金山，2022），产出风险框架、2023 年灭绝风险声明、2026 年的 AI Dashboard、Remote Labor Index（与 Scale AI 合作）、Superintelligence Strategy Paper、AI Frontiers newsletter。
- **CAISI**：美国政府机构（NIST 内），自愿协议 + 非涉密能力评估（网络、生物、化学）。
- **METR**：独立非营利评估机构，常在发布前、NDA 下评估前沿模型，公开方法（第 21 节）。
- **SB-53**：加州参议院法案（2025–2026 会期），针对前沿模型的灾难性风险；讲义写作时状态是"若签署则为美国首个州级灾难性风险法规"。
- **为什么非美国团队也要读**：讲义："Regardless of signing status, the bill's framing shapes how other state legislatures approach the problem"；美国科技政策中州级监管历来先于联邦行动；条款（能力阈值、吹哨人、事故报告）代表了监管的通用方向，与欧盟 AI Act 等框架可以互相对照；若你的模型或服务触达加州用户或依赖加州的实验室，也可能间接受影响。
- 常见误区：把 CAIS 和 CAISI 当成同一个机构；把"我们有 scaling policy"当作已满足监管要求（skill 文件把这列为拒绝理由）。
- 加分点：CAISI 的前身是美国 AI Safety Institute（2025 年更名），第 20 节讲义仍使用旧名 "US AI Safety Institute"。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 19 Anthropic Responsible Scaling Policy v3.0](../../19-anthropic-rsp/docs/zh.md)：实验室内部的能力阈值与 RAND SL-4 信息安全标准。
- [阶段 15 · 20 OpenAI Preparedness Framework 与 DeepMind Frontier Safety Framework](../../20-openai-preparedness-deepmind-fsf/docs/zh.md)：另外两家实验室的 scaling policy，是 AI races 的主要缓解手段。
- [阶段 15 · 21 METR 时间跨度与外部能力 Evaluation](../../21-metr-external-evaluation/docs/zh.md)：外部评估层，与 CAISI 互补。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../14-kill-switches-canaries/docs/zh.md)、[阶段 15 · 15 先提出方案，再 Commit](../../15-propose-then-commit/docs/zh.md)、[阶段 15 · 16 Checkpoints 与 Rollback](../../16-checkpoints-rollback/docs/zh.md)：代码中 rogue_ais 的缓解清单。
- [阶段 15 · 17 Constitutional AI 与规则覆盖](../../17-constitutional-ai/docs/zh.md)、[阶段 15 · 18 Llama Guard 与输入输出分类](../../18-llama-guard/docs/zh.md)：malicious_use 的缓解清单。

### 本节被哪些后续内容用到
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../../18-ethics-safety-alignment/18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：从对齐视角再看各家框架。
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../../18-ethics-safety-alignment/24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：SB-53 之外的监管全景。
- [阶段 18 · 30 两用风险：网络、生物、化学与核领域的能力提升](../../../18-ethics-safety-alignment/30-dual-use-risk-cyber-bio-chem-nuclear/docs/zh.md)：CAISI 评估所聚焦的领域，即 malicious use 的具体形态。
- [阶段 18 · 28 Alignment 研究生态：MATS、Redwood、Apollo、METR](../../../18-ethics-safety-alignment/28-alignment-research-ecosystem/docs/zh.md)：研究与评估机构的全景。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../../17-infrastructure-and-production/26-compliance-frameworks/docs/zh.md)：把监管面落到工程合规。
- [阶段 16 · 01 为什么需要多 Agent？](../../../16-multi-agent-and-swarms/01-why-multi-agent/docs/zh.md)：下一阶段开始，多 agent 系统会进一步放大自主性与组织风险。

### 延伸关键词
`CAIS` · `four-risk framework` · `statement on AI risk` · `CAISI` · `NIST` · `voluntary agreements` · `SB-53` · `whistleblower protection` · `incident reporting` · `safety culture` · `defense in depth` · `Swiss cheese model` · `RAND SL-4`
