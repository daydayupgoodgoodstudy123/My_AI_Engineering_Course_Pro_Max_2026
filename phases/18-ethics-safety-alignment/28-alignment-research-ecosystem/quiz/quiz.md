# 测验 · Alignment 研究生态：MATS、Redwood、Apollo、METR（Alignment Research Ecosystem — MATS, Redwood, Apollo, METR）

> **阶段 18 · 伦理、安全与对齐 · 第 28 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **说明**：本节是"Learn"型小节（讲义标注 `Languages: none`、"Use It: No code"），但仓库里仍附带了一个打印生态地图的 `code/main.py`。中文讲义机翻质量较差（如把 Redwood 译成"红木"、把 Claude Opus 4 译成"Claude 4号计划"），**一切以英文讲义为准**。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | "非实验室"对齐研究层 | 讲义："Five organisations define the 2026 non-lab alignment research layer"——MATS、Redwood、Apollo、METR、Eleos，位于前沿实验室之外 |
| 2 | MATS = 人才管道 | ML Alignment & Theory Scholars，2021 年底启动；导师制，学者跟资深研究员做 10–12 周；527+ 研究者、180+ 论文、10K+ 引用、h-index 47 |
| 3 | MATS 的职业去向 | 2025 年前校友约 80% 从事 safety/security；200+ 人在 Anthropic、DeepMind、OpenAI、UK AISI、RAND、Redwood、METR、Apollo |
| 4 | Redwood Research | Buck Shlegeris 创立的应用对齐实验室；提出 AI Control（第 10 节）；与 UK AISI 合作 control safety case；风格是"具体威胁模型 + 最坏情况对手 + 可压力测试的协议" |
| 5 | Apollo Research | 为前沿实验室做部署前 scheming（谋划）评估；著有 In-Context Scheming（第 8 节）与 Towards Safety Cases for AI Scheming；三柱分解：misalignment、goal-directedness、situational awareness |
| 6 | METR | Model Evaluation and Threat Research；基于任务的能力评估、自主任务"时间跨度（time horizon）"研究；"Common Elements of Frontier AI Safety Policies"横向比较各实验室框架 |
| 7 | Eleos AI Research | 模型福利（model welfare）部署前评估；做了 Claude Opus 4 system card 第 5.3 节记录的福利评估（第 19 节） |
| 8 | 外部评估的价值 | 实验室评估自家模型存在结构性利益冲突（conflict of interest）；外部评估者能提出并验证实验室可能少报的失败模式 |
| 9 | 多组织合作即质量控制 | Sleeper Agents、Alignment Faking = Anthropic + Redwood；In-Context Scheming = Apollo；Anti-Scheming = Apollo + OpenAI |
| 10 | 生态的循环 | MATS 培养 → 进入实验室安全团队或外部评估机构 → 与实验室、UK AISI / CAISI 合作 → 发表成果 → 反哺下一期 MATS |

### 核心技能（能动手做到）

- [ ] 说出五个组织各自的"核心产出 + 方法风格"，并能把第 7–19 节的论文对应到组织
- [ ] 给定一篇对齐论文，判断它是单一实验室成果、外部机构成果还是"实验室 + 外部"联合成果，并解释这对可信度的影响
- [ ] 读懂 `main.py` 的"字典列表"数据结构，指出字段语义不一致的问题，并能改写为带类型的 `dataclass`
- [ ] 为生态地图增加 `partners`（合作方）字段，写出查询"某组织与谁合作过"的函数
- [ ] 按 `outputs/skill-ecosystem-map.md` 的五步（来源、方法风格、对应机构、多组织信号、发表渠道）分析一条对齐结论
- [ ] 解释 h-index 等文献计量指标的含义与局限，不把"引用多"等同于"结论对"

---

## 二、基础自测（选择题）

**Q1.** 关于 MATS，下列描述与讲义一致的是：

- A. 2021 年底启动的研究导师项目，累计 527+ 研究者、180+ 论文、h-index 47，2025 年前校友约 80% 从事 safety/security
- B. 由英国政府设立的 AI 安全研究所，负责发放模型出口许可
- C. 一个奖励模型训练服务平台，向前沿实验室出售偏好数据
- D. 由 OpenAI 内部孵化的红队组织，2024 年拆分独立

**Q2.** Redwood Research 最具代表性的研究议程是：

- A. Constitutional AI 与 RLAIF
- B. 基于 SynthID 的生成内容水印
- C. 面向 LLM 的差分隐私训练
- D. AI Control：即使模型可能蓄意破坏，也能通过监控协议保障安全

**Q3.** Apollo Research 在分析 scheming（谋划）风险时使用的"三柱分解"是：

- A. 能力、意图、机会
- B. misalignment（目标不一致）、goal-directedness（目标导向）、situational awareness（情境感知）
- C. 数据、模型、部署
- D. 监控、拦截、回滚

**Q4.** 讲义说 MATS 的 h-index 为 47。这个数字的准确含义是：

- A. MATS 共发表了 47 篇论文
- B. MATS 论文的平均引用次数是 47
- C. 至少有 47 篇 MATS 论文，每篇都被引用了至少 47 次
- D. MATS 有 47 篇论文发表在顶会上

**Q5.** 讲义认为"外部评估层"之所以重要，最核心的理由是：

- A. 实验室评估自家模型存在结构性利益冲突，外部评估者能提出并验证实验室可能少报的失败模式
- B. 外部机构的算力比前沿实验室更多
- C. 欧盟 AI 法案强制要求所有论文必须有外部合著者
- D. 外部评估能让论文更快发表、引用更多

**Q6.** 下列"论文—参与机构"的对应，哪一项与讲义一致？

- A. In-Context Scheming：Anthropic + Redwood
- B. Sleeper Agents：Apollo + OpenAI
- C. Anti-Scheming 训练合作：Apollo + OpenAI
- D. Alignment Faking：METR + Eleos

**Q7.** 关于本节 `code/main.py` 中的 `ECOSYSTEM` 数据结构，下列说法正确的是：

- A. 它是一个以组织名为键的嵌套字典，查找某个组织是 O(1)
- B. 每个组织都有 `partners` 字段，`main()` 会据此打印交叉引用
- C. 五个组织的 `scale` 字段都给出了可比较的数量指标
- D. 它是由 5 个字典组成的列表，每个字典有相同的 5 个键；但 `scale` 字段只有 MATS 真的是"规模"，其余 4 个组织填的是机构描述

**Q8.** Eleos AI Research 在生态中的主要作用是：

- A. 起草加州训练数据透明法
- B. 做模型福利的部署前评估，例如 Claude Opus 4 system card 第 5.3 节记录的外部福利评估
- C. 维护 AI Control 基准
- D. 制定 C2PA 内容来源标准

---

## 三、动手 / 代码题

**Q9.** 阅读 `main.py` 的数据定义（节选）：

```python
ECOSYSTEM = [
    {
        "org": "MATS",
        "full_name": "ML Alignment & Theory Scholars",
        "scale": "527+ researchers since 2021, 180+ papers, h-index 47",
        "role": "talent pipeline + mentorship program",
        "canonical_output": "90 scholars x 10-12 week cohorts -> labs and external evaluators",
    },
    {
        "org": "Redwood",
        "full_name": "Redwood Research",
        "scale": "founded by Buck Shlegeris; applied alignment lab",
        ...
```

1. 指出这个数据结构在**字段语义**上的至少两个问题。
2. 文件 docstring 写着 "Prints a compact map ... with canonical outputs and cross-references"，代码里真的有 cross-references 吗？
3. 用 `@dataclass(frozen=True)` 重写一个 `Org` 类型，加入 `kind`（talent / external-eval）、`canonical_outputs`（元组，允许多篇）和 `partners`（合作方集合）字段。

**Q10.** 讲义说"The multi-org structure is the quality control"。请写一个函数 `multi_org_signal(orgs: set[str]) -> str`，把一篇论文的参与机构归为 `lab+external`、`lab-only`、`multi-external`、`single-external` 四类（实验室集合取 `{"Anthropic", "OpenAI", "DeepMind"}`），并对下列论文给出结果：

| 论文 | 参与机构（按讲义） |
|------|-------------------|
| Sleeper Agents | Anthropic、Redwood |
| Alignment Faking | Anthropic、Redwood |
| In-Context Scheming | Apollo |
| Anti-Scheming | Apollo、OpenAI |
| AI Control | Redwood |
| Scheming safety-case sketch | Apollo、METR |

**Q11.** `outputs/skill-ecosystem-map.md` 的第 1 步是"来源识别"。有同学用下面的关键词查找实现它：

```python
def lookup(keyword):
    kw = keyword.lower()
    return [o["org"] for o in ECOSYSTEM if any(kw in str(v).lower() for v in o.values())]
```

请预测并解释 `lookup("scheming")`、`lookup("evaluat")`、`lookup("Anthropic")` 的返回值。这暴露了"把非结构化字符串当知识库"的什么问题？

**Q12.** 用讲义给出的 MATS 数字做估算：（1）平均每位研究者对应多少篇论文？（2）平均每篇论文多少引用？（3）2024 年夏季一期的"学者/导师比"是多少？（4）h-index 47 意味着这 47 篇"核心论文"的引用总数至少是多少？然后说明这些指标各自**不能**说明什么。

---

## 四、面试高频题

**Q13.**（基础必考）请用两分钟介绍 2026 年前沿实验室之外的对齐研究生态：有哪些主要机构？各自做什么？它们之间如何流动？

**Q14.**（原理深挖）为什么"实验室自己评估自己的模型"不够？外部评估在方法论上带来了哪些实验室内部评估难以提供的东西？外部评估本身又有什么局限？

**Q15.**（场景设计）你在一家前沿实验室负责发布前安全评估。新模型在内部评估中没有发现 scheming 迹象。你会如何设计外部评估合作（找谁、给什么访问权限、如何发布结果），使结论更可信？

**Q16.**（工程实践）讲义练习 4：Redwood 和 Apollo 都研究 control / scheming，但风格不同。选一个失败模式（例如"模型在代码任务中悄悄植入后门"），分别描述两家会如何研究它。

**Q17.**（追问型）讲义练习 3："MATS 约 80% 校友从事安全/安保，这种选择压力是适应性的（训练了整个领域）还是有偏的（过滤掉异见）？"请给出你的论证。

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："527+ researchers since late 2021, 180+ papers, 10K+ citations, h-index 47"，"80% of pre-2025 alumni work on safety/security"。B 描述的更像 UK AISI（但 AISI 也不发放出口许可）；C、D 是编造的干扰项，与 MATS 的导师项目定位无关。另外注意 2024 年夏季那一期"incorporated as 501(c)(3)"，即注册为美国非营利组织。

### Q2 — 答案：D

讲义："Introduced the AI Control agenda (Lesson 10)"，代表论文 Greenblatt, Shlegeris et al., "AI Control"（arXiv:2312.06942，ICML 2024）。AI Control 的思路是：不假设模型已对齐，而是设计监控与审查协议，使得即使模型蓄意破坏也难以造成危害。A 是 Anthropic 的工作（第 5 节）；B 是水印（第 23 节）；C 是差分隐私（第 22 节）。

### Q3 — 答案：B

讲义："three-pillar decomposition (misalignment, goal-directedness, situational awareness)"。直觉：scheming 需要模型"目标与开发者不一致 + 有持续追求目标的倾向 + 意识到自己正被评估/部署"三个条件同时成立。A 是犯罪学里"动机—手段—机会"的类比，不是讲义原文；C、D 是泛泛的工程分层。

### Q4 — 答案：C

h-index 的定义：一组论文中有 h 篇每篇至少被引用 h 次。h = 47 意味着至少 47 篇论文、每篇 ≥ 47 次引用。A 把它当作论文数（实际是 180+ 篇）；B 是平均引用（10K+/180 ≈ 55.6，见 Q12）；D 与 h-index 无关。

### Q5 — 答案：A

讲义原文："labs evaluating their own models have a structural conflict of interest. External evaluators can raise and validate failure modes the lab may underreport." B 不对，外部机构的算力通常远少于前沿实验室，它们往往依赖实验室提供的模型访问；C 是编造的法规要求；D 把手段当成了目的。

### Q6 — 答案：C

讲义："Anti-Scheming was Apollo + OpenAI"。A 错：In-Context Scheming 是 Apollo 的工作；B 错：Sleeper Agents 是 Anthropic + Redwood；D 错：Alignment Faking 是 Anthropic + Redwood（Greenblatt、Denison、Wright 等，arXiv:2412.14093）。

### Q7 — 答案：D

`ECOSYSTEM` 是 `list[dict]`，5 个字典的键都是 `org / full_name / scale / role / canonical_output`（已运行验证）。但 `scale` 字段只有 MATS 写的是规模数字，Redwood 写的是"founded by Buck Shlegeris; applied alignment lab"，Apollo、METR、Eleos 写的都是业务描述。A 错：是列表不是字典，按名字查找需要线性扫描（5 条时无所谓）；B 错：没有 `partners` 字段，交叉引用只出现在结尾的固定文字里；C 错，原因如上。

### Q8 — 答案：B

讲义："Conducted the Claude Opus 4 welfare assessment documented in section 5.3 of the system card"。A 与第 27 节数据治理相关；C 是 Redwood 的方向；D 是第 23 节水印/内容来源。

### Q9 — 参考答案

1. **字段语义问题**：
   - `scale` 字段名不副实：只有 MATS 是规模，其余是描述（见 Q7）。数据结构的同一字段应表达同一种含义，否则下游无法按字段比较或排序。
   - `canonical_output` 是单个字符串，但讲义里 Apollo 有两项代表作（In-Context Scheming、Towards Safety Cases for AI Scheming），Redwood 也有两项（AI Control、Alignment Faking），代码各只保留了一项。
   - MATS 的 `canonical_output` 写的是"90 scholars x 10-12 week cohorts"，这其实是 2024 年夏季一期的规模，不是"代表性产出"；"since 2021" 也省略了讲义中的 "late"。
   - 机构类型（人才管道 vs 外部评估者）没有结构化字段，只藏在 `role` 文本里。
2. **没有真正的 cross-references**：数据里没有任何"组织 A 与组织 B / 实验室合作"的字段，`main()` 只是逐条打印，最后用写死的 `print` 文字提到 "Apollo + OpenAI, Redwood + Anthropic"。docstring 与实现不符。
3. 参考实现（已运行验证）：

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Org:
    org: str
    full_name: str
    kind: str                         # "talent" | "external-eval"
    description: str
    role: str
    canonical_outputs: tuple[str, ...]
    partners: frozenset[str] = field(default_factory=frozenset)

ORGS = [
    Org("Redwood", "Redwood Research", "external-eval", "applied alignment lab",
        "AI Control agenda",
        ("AI Control (ICML 2024)", "Alignment Faking (with Anthropic)"),
        frozenset({"Anthropic", "UK AISI", "DeepMind"})),
    Org("Apollo", "Apollo Research", "external-eval", "pre-deployment scheming evals",
        "three-pillar decomposition",
        ("In-Context Scheming", "Towards Safety Cases for AI Scheming"),
        frozenset({"OpenAI", "METR"})),
    Org("METR", "Model Evaluation and Threat Research", "external-eval",
        "task-horizon evals", "framework synthesis",
        ("Common Elements of Frontier AI Safety Policies",), frozenset({"Apollo"})),
]

def partners_of(name: str) -> list[str]:
    direct = {o.org for o in ORGS if name in o.partners}          # 谁把 name 列为合作方
    own = next((o.partners for o in ORGS if o.org == name), frozenset())
    return sorted(direct | own)

print(partners_of("Apollo"))     # ['METR', 'OpenAI']
print(partners_of("Anthropic"))  # ['Redwood']
```

要点：`frozen=True` 让记录不可变、可哈希；可变默认值必须用 `field(default_factory=...)`；合作关系是对称的，所以查询时要同时看"我列了谁"和"谁列了我"（也可以加一个检查对称性的校验函数）。

### Q10 — 参考答案

```python
LABS = {"Anthropic", "OpenAI", "DeepMind"}

def multi_org_signal(orgs: set[str]) -> str:
    has_lab = bool(orgs & LABS)
    has_ext = bool(orgs - LABS)
    if has_lab and has_ext:
        return "lab+external"
    if has_lab:
        return "lab-only"
    return "multi-external" if len(orgs) > 1 else "single-external"
```

实际运行结果：

```text
Sleeper Agents               ['Anthropic', 'Redwood'] -> lab+external
Alignment Faking             ['Anthropic', 'Redwood'] -> lab+external
In-Context Scheming          ['Apollo'] -> single-external
Anti-Scheming                ['Apollo', 'OpenAI'] -> lab+external
AI Control                   ['Redwood'] -> single-external
Scheming safety-case sketch  ['Apollo', 'METR'] -> multi-external
```

解读：`lab+external` 的论文同时具备"实验室内部访问权"和"外部视角"，最符合讲义所说的质量控制；`single-external` 不代表不可信——AI Control 就经过了 ICML 同行评审，这时"发表渠道"（skill 第 5 步）是另一种外部审视。注意把 `has_ext` 写成 `orgs - LABS` 比维护一个外部机构白名单更稳健，新机构（如 UK AISI、学术实验室）会自动被视为外部方。

### Q11 — 参考答案

实际运行结果：

```text
scheming  -> ['Apollo']
evaluat   -> ['MATS', 'Apollo', 'METR', 'Eleos']
Anthropic -> []
```

- `"scheming"` 恰好只出现在 Apollo 的字段里，命中正确。
- `"evaluat"` 命中 4 个：MATS 的 `canonical_output` 里有 "external evaluators"，Apollo、Eleos 有 "evaluations"，METR 有 "evals"。"评估"是整个生态的共同词汇，子串匹配无法区分"做评估"和"把人送去评估机构"。
- `"Anthropic"` 返回空列表：虽然 Redwood 与 Anthropic 合作了 Alignment Faking、Sleeper Agents，但这些信息不在数据里（`canonical_output` 只写了 AI Control）。

暴露的问题：自由文本既有**假阳性**（关键词过宽）也有**假阴性**（信息缺失）。真正实现 skill 的"来源识别"应基于论文的作者单位元数据（结构化字段），而不是在描述文本里做子串匹配；技能文件中的硬性拒绝规则 "Any alignment claim without an identified producing organisation" 也要求来源是明确的，而不是猜出来的。

### Q12 — 参考答案

用 Python 计算：`180/527 ≈ 0.34`、`10000/180 ≈ 55.6`、`90/40 = 2.25`、`47 × 47 = 2209`。

1. 约 0.34 篇论文/人：多数学者在 10–12 周项目中不一定产出论文，或多人合作一篇。不能说明论文质量。
2. 约 55.6 次引用/篇（用下限数字粗估）：引用分布通常高度偏斜，少数高引论文会拉高平均值，中位数可能低得多。
3. 学者/导师比约 2.25:1：说明导师制是"小组式"指导，但不能说明指导质量。
4. h-core 引用总数至少 2,209：这是下限，10K+ 总引用远高于此，说明有不少论文超过 47 次。

共同的局限：引用量衡量的是"被讨论的程度"，不是"结论是否正确"；对齐领域里一篇被广泛引用的结论同样需要外部复现（skill 的硬性拒绝规则之一："Any single-org safety claim without an external replication or check"）。

### Q13 — 参考回答要点

- **MATS**：人才管道。2021 年底起的导师项目，学者跟资深研究员做 10–12 周；527+ 研究者、180+ 论文；约 80% 校友进入安全领域，200+ 人在各大实验室与评估机构。
- **Redwood**：应用对齐实验室，AI Control 议程，强调具体威胁模型和最坏情况对手；与 UK AISI 合作 control safety case，与 Anthropic 合作 Alignment Faking。
- **Apollo**：部署前 scheming 评估，In-Context Scheming，三柱分解；与 OpenAI 做 anti-scheming 训练合作。
- **METR**：任务型能力评估与自主任务时间跨度研究，"Common Elements"横向比较实验室安全框架。
- **Eleos**：模型福利评估，Claude Opus 4 福利评估。
- **流动**：MATS → 实验室安全团队 / 外部评估机构 → 与实验室和 UK AISI、CAISI 合作 → 论文反哺 MATS。
- 加分点：能把机构对应到具体论文与本阶段的小节编号；指出这是"非实验室层"，和第 18 节的实验室框架（RSP / PF / FSF）、第 24 节的监管机构共同构成三层结构。

### Q14 — 参考回答要点

- **利益冲突**：实验室有发布压力和商业动机，可能在评估设计、阈值选择、结果披露上"自然地"偏向乐观；这不需要恶意，结构本身就有偏差。
- **外部评估带来的东西**：
  - 独立的威胁模型和评估设计（不受内部假设束缚）；
  - 发现新失败模式（讲义："where novel failure modes are first discovered"）；
  - 对实验室结论的复核与公开背书，提高可信度；
  - 跨实验室比较（METR 的 framework synthesis），这是单一实验室做不到的。
- **局限**：
  - 依赖实验室提供的模型访问（权限、时间窗口、是否能看到内部工具或微调接口）；
  - 资金和人员规模小，人才部分来自同一管道，可能存在共同盲区；
  - 与实验室合作发表也可能产生新的依赖关系。
- 常见误区：认为"有外部合著者 = 结论一定对"。多组织合作提高的是可信度，而不是正确性的保证。

### Q15 — 参考回答要点

- **找谁**：scheming 方向找 Apollo（专长）；控制协议找 Redwood；自主能力 / 任务时间跨度找 METR；监管侧同步 UK AISI / CAISI；涉及福利问题可找 Eleos。
- **访问权限**：足够的部署前时间窗口；接近最终版本的 checkpoint；允许 agentic 场景（工具、文件系统、长任务）——讲义："agentic-setting evaluations where deception can emerge"；必要时提供无安全微调的版本或思维链。
- **评估设计**：让外部方独立设计部分评估集，避免只跑实验室的既有测试；预先约定判定标准。
- **发布**：在 system card 中写明外部评估方、访问范围和限制；允许外部方独立发表方法与结论（哪怕与实验室不一致）；结论要包含"我们没测到什么"。
- 加分点：说明"内部没发现 scheming"本身可能受评估意识（evaluation awareness）影响，这正是需要外部、多样化评估的原因。

### Q16 — 参考回答要点

- **Redwood 风格（control）**：不假设模型诚实，直接把模型当成"可能是对手"。设计协议：用一个可信但较弱的模型监控强模型的代码输出，对可疑片段交由人工审核或替换；用红队把强模型扮演成"会植后门的攻击者"，测量协议在最坏情况下的安全率与有用性。产出是"在该协议下，后门进入生产的概率上界"。
- **Apollo 风格（scheming evals）**：构造 agentic 场景，让模型在追求给定目标时"有动机、有机会"植入后门，观察它是否会这样做、是否隐瞒、被追问时是否撒谎；按三柱分解分别测量目标不一致、目标导向、情境感知。产出是"模型在何种条件下表现出 scheming 行为的证据"。
- 对比：Redwood 回答"即使它想作恶，我们能否兜住"；Apollo 回答"它会不会想作恶、在什么条件下"。两者互补，后者为前者提供威胁模型的经验依据。

### Q17 — 参考回答要点

- **适应性的论据**：领域早期人才极度稀缺，高比例留任意味着培训投入转化为长期产出；200+ 人进入实验室和评估机构，形成跨组织网络，便于合作与复核。
- **偏差的论据**：选拔、导师和研究题目都来自同一社群，可能强化共同假设（例如某些威胁模型被默认为重要）；外部批评或其他学科视角可能被筛掉；评估者与被评估实验室的人才来源高度重合，独立性被削弱。
- **折中观点**：两者都成立；关键是用机制对冲，例如引入学术界、其他国家（SVG 图注："China, India, Africa alignment ecosystems are less documented publicly"）和不同学科的研究者，鼓励发表反驳结果。
- 常见误区：只用 80% 这个数字下结论。80% 本身无法区分"因为领域需要"还是"因为筛选同质化"。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 07 潜伏 Agents：持续性欺骗](../../07-sleeper-agents-persistent-deception/docs/zh.md)：Anthropic + Redwood 的 Sleeper Agents 论文。
- [阶段 18 · 08 前沿模型中的上下文内密谋](../../08-in-context-scheming-frontier-models/docs/zh.md)：Apollo 的 In-Context Scheming 与三柱分解。
- [阶段 18 · 09 伪装 Alignment](../../09-alignment-faking/docs/zh.md)：Anthropic + Redwood 的 Alignment Faking。
- [阶段 18 · 10 AI 控制：面对蓄意破坏仍能保障安全](../../10-ai-control-subversion/docs/zh.md)：Redwood 的 AI Control 议程。
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：METR "Common Elements" 所比较的实验室框架。
- [阶段 18 · 19 Anthropic 的模型福利计划](../../19-model-welfare-research/docs/zh.md)：Eleos 的外部福利评估。

### 本节被哪些后续内容用到
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：UK AISI / CAISI 是外部评估者的监管侧对应方（代码结尾提示 "Lesson 24"）。
- [阶段 18 · 30 两用风险：网络、生物、化学与核领域的能力提升](../../30-dual-use-risk-cyber-bio-chem-nuclear/docs/zh.md)：两用能力评估同样依赖外部评估者与 AISI。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../26-model-system-dataset-cards/docs/zh.md)：外部评估结果最终写进 system card（如 Opus 4 第 5.3 节）。
- [阶段 19 · 15 宪法式安全 Harness 与红队演练场](../../../19-capstone-projects/15-constitutional-safety-harness/docs/zh.md)：综合项目中自己搭建评估与红队流程。

### 延伸关键词
`AI Control` · `safety case` · `scheming evaluation` · `task time horizon` · `external evaluation` · `conflict of interest` · `UK AISI / CAISI` · `model welfare` · `h-index` · `talent pipeline` · `multi-org replication`
