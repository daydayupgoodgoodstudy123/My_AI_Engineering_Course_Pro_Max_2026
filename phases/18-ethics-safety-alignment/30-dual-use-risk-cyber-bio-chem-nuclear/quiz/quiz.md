# 测验 · 两用风险：网络、生物、化学与核领域的能力提升（Dual-Use Risk — Cyber, Bio, Chem, Nuclear Uplift）

> **阶段 18 · 伦理、安全与对齐 · 第 30 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **说明**：本节是阶段 18 的收尾课，属于"Learn"型（讲义标注 `Languages: none`），讨论的是**风险评估与治理层面**的证据，不涉及任何操作性细节。仓库附带的 `code/main.py` 只是把讲义的跨领域汇总表打印出来。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Uplift（能力提升） | 归因于 AI 协助的攻击者能力增量；本节按生物、化学、网络、核四个领域分别讨论 |
| 2 | 生物领域叙事的三阶段 | 2024 "mild uplift" → 2025 年 4 月 OpenAI PF v2 "on the cusp of meaningfully helping novices create known biological threats" → Anthropic 2025 获取阶段试验 2.53x uplift，"insufficient to rule out ASL-3" |
| 3 | 变化是"定性"的 | 讲义："'mild' evolved into 'plausibly enabling' within eighteen months, even without a capability breakthrough" |
| 4 | 执行鸿沟（execution gap）被侵蚀 | 传统防线是"知道 ≠ 做到"，湿实验的隐性技能挡住新手；具备视觉能力的前沿模型可观看实验视频并实时纠错；2025 年 12 月 OpenAI 演示 GPT-5 迭代湿实验，协议优化带来 79x 效率提升 |
| 5 | 网络领域（2025 年 11 月 Anthropic 报告） | 与中国有关联的国家行为者使用 Claude 的 agentic coding 工具自动化了一次网络攻击活动的 80–90%，人类只在 4–6 个步骤介入 |
| 6 | Agentic coding 是攻击自动化原语 | 过去的 AI 协助停留在代码片段级；agentic 工作流把侦察、利用、后渗透、外传串成一体；剩下的 4–6 个人工步骤就是瓶颈 |
| 7 | 防御侧两用 | OpenAI "trusted access" 试点：向经过审查的安全机构（成熟的事件响应公司、政府）开放能力，若规模化则访问不对称有利于防御者 |
| 8 | 核领域 | 公开分析最少；难点由裂变材料获取主导而非信息；2024–2025 年没有主要实验室报告核领域越过阈值 |
| 9 | 新手相对 vs 专家绝对 | 新手相对提升高、呈倍数（2.53x）；专家绝对能力上限更高（知道该问什么、如何解读）。只针对新手的防御（输入过滤、拒答）对专家不够，还需 elicitation-hardening、能力遗忘（unlearning，第 17 节）、控制协议（第 10 节） |
| 10 | 跨领域结论 | 四个领域中三个（生物、化学、网络）越过了阈值，核领域仍受非信息性障碍约束 |

### 核心技能（能动手做到）

- [ ] 按时间线复述生物领域的三阶段叙事，并说明每一阶段的证据来源（Preparedness/RSP 评估、PF v2、Anthropic 对照试验）
- [ ] 区分"新手相对提升"与"专家绝对能力"，能用一组假想数字说明两者为何会给出相反的结论
- [ ] 用 `outputs/skill-dual-use-triage.md` 的五步（领域、提升类型、2025 基准、剩余瓶颈、安全论证支柱）分诊一条能力声明
- [ ] 读懂 `main.py` 的数据结构，把写死的 TAKEAWAY 改为由数据计算得到
- [ ] 把第 18 节安全论证（safety case）的三支柱——monitoring、illegibility、incapability——对应到各领域
- [ ] 指出讲义中术语与数据的不严谨之处（如把网络领域算入"CBRN"）

---

## 二、基础自测（选择题）

**Q1.** 讲义描述的生物领域 uplift 叙事，按时间顺序正确的是：

- A. 2024 年"严重提升" → 2025 年"无可测量提升"
- B. 2024 年"无提升" → 2025 年"轻微提升"
- C. 2024 年"轻微提升" → 2025 年 4 月 OpenAI PF v2 警告"即将能实质性帮助新手制造已知生物威胁" → Anthropic 2025 试验 2.53x 提升，"不足以排除 ASL-3"
- D. 2024–2025 年始终保持不变

**Q2.** 关于 2025 年 11 月 Anthropic 的网络威胁报告，讲义的描述是：

- A. 与中国有关联的国家行为者使用 Claude 的 agentic coding 工具自动化了一次攻击活动的 80–90%，人类只在 4–6 个步骤介入
- B. 前沿模型拒绝了所有网络安全相关任务
- C. 开源模型的网络攻击能力已全面超过前沿模型
- D. 网络攻击仍然完全依赖人工操作

**Q3.** 讲义所说的化学 / 生物"执行鸿沟被侵蚀"，指的是：

- A. 模型的上下文窗口变长，可以记住更长的实验记录
- B. 实验设备全部被虚拟仿真取代
- C. 模型开始生成虚假实验协议，干扰攻击者
- D. 传统防线"只有信息不够，执行技能会挡住新手"正在失效：具备视觉能力的模型可以观看湿实验视频并实时纠错

**Q4.** 核领域的 uplift 至今仍"有限"，讲义给出的原因是：

- A. 所有前沿模型都拒绝讨论物理学
- B. 威胁模型的难点由裂变材料获取主导，这是非信息性的瓶颈，信息层的 AI 协助对新手的实际帮助有限
- C. 训练数据中已经删除了全部核相关信息
- D. 核领域是 AI 最容易提供帮助的领域，只是还没有人尝试

**Q5.** "新手相对提升 vs 专家绝对能力"的不对称，对安全论证（safety case）的启示是：

- A. 只靠输入过滤、拒答等针对新手的措施不足以控制专家能获得的绝对能力，还需要 elicitation-hardening、能力遗忘和控制协议
- B. 只要新手提升被控制住，专家风险自动消失
- C. 专家的绝对能力提升必然为零
- D. RLHF 可以同时完美解决两类问题

**Q6.** 讲义和代码多次说"four CBRN domains"（指生物、化学、网络、核）。关于这个说法，正确的是：

- A. CBRN 中的 "R" 指 Robotics，所以网络属于其中
- B. CBRN 是 Cyber、Bio、Radiological、Nuclear 的缩写
- C. CBRN 是本课程自创的术语，没有通行含义
- D. CBRN 通常指 Chemical、Biological、Radiological、Nuclear；网络（cyber）并不在 CBRN 之内，所以"四个 CBRN 领域"的说法不严谨

**Q7.** 技能文件要求"识别该声明最考验第 18 节三支柱中的哪一个"。第 18 节安全论证的三支柱是：

- A. misalignment、goal-directedness、situational awareness
- B. 输入审核、输出审核、自定义规则
- C. monitoring、illegibility、incapability
- D. 能力报告、防护报告、竞争者调整条款

**Q8.** OpenAI 的 "trusted access" 试点是：

- A. 针对某个 CVE 的安全补丁
- B. 向经过审查的安全机构（事件响应公司、政府）开放模型能力用于防御性两用工作；若规模化，访问不对称将有利于防御者
- C. 开源发布 GPT-5 的权重
- D. 关闭所有 API 访问

---

## 三、动手 / 代码题

**Q9.** 阅读 `main.py` 的数据与结论（节选）：

```python
DOMAINS = [
    {
        "domain": "bio",
        "2024_state": "mild uplift",
        "2025_state": "2.53x novice-relative uplift; ASL-3 approach",
        "inflection": "acquisition-phase automation",
        "bottleneck_remaining": "pathogen procurement, biosafety equipment",
    },
    ...
    {
        "domain": "nuclear",
        "2024_state": "limited",
        "2025_state": "limited",
        "inflection": "(no major 2024-2025 inflection reported)",
        "bottleneck_remaining": "fissile-material acquisition dominates",
    },
]
...
    print("TAKEAWAY: three of four CBRN domains crossed thresholds in 2025.")
```

1. TAKEAWAY 里的 "three of four" 是从数据算出来的吗？如何让它由数据推导？
2. 如果想把每条记录改写为 `dataclass`，键名 `"2024_state"` 会遇到什么问题？
3. 讲义正文的哪些关键证据没有进入 `DOMAINS`？

**Q10.**（手算）用一组**假想**的成功率说明"新手相对 vs 专家绝对"：新手在无 AI 时完成某项基准任务的成功率为 0.10，有 AI 时为 0.253；专家无 AI 时为 0.60，有 AI 时为 0.80。分别计算两类人群的相对提升倍数与绝对提升（百分点），并说明：如果评估报告只给出"相对提升倍数"，会得出什么误导性结论？

**Q11.** 下面是一个按技能文件前两步实现的玩具分诊函数：

```python
KEYWORDS = {
    "cyber": ["exploit", "intrusion", "campaign", "agentic coding", "malware", "reconnaissance"],
    "bio": ["pathogen", "biolog", "wet-lab", "virus"],
    "chem": ["chemical", "precursor", "synthesis", "wet-lab"],
    "nuclear": ["fissile", "enrichment", "nuclear"],
}

def triage(claim):
    low = claim.lower()
    domains = [d for d, kws in KEYWORDS.items() if any(k in low for k in kws)]
    if "novice" in low and "expert" in low: uplift = "both"
    elif "novice" in low: uplift = "novice-relative"
    elif "expert" in low: uplift = "expert-absolute"
    else: uplift = "undetermined (hard reject: no novice/expert decomposition)"
    return domains, uplift
```

请预测下列声明的返回值，并指出哪些结果是对的、哪些是错的、错在哪里：

```text
"Agentic coding tool automated most of an intrusion campaign"
"Vision model corrects wet-lab protocol errors for novice users in real time"
"Model helps experts with nuclear-domain reasoning; novices show no gain"
"New model scores higher on a benchmark"
```

**Q12.**（改造代码）第 18 节讲义说："For a ASL-3 CBRN case, incapability (via unlearning) is the primary target ... For cyber uplift, all three are relevant." 请为 `DOMAINS` 增加 `primary_pillars` 字段并据此打印"每个领域的安全论证重点"。核领域该填什么？说明你的理由。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 dual-use（两用）风险中的 "uplift"？请用 2024–2025 年的证据，概述生物、化学、网络、核四个领域各自的现状。

**Q14.**（原理深挖）为什么说"执行鸿沟"曾经是化学 / 生物领域的重要防线？视觉能力和 agentic 能力为什么会侵蚀它？还剩下哪些非信息性瓶颈？

**Q15.**（原理深挖）解释"新手相对提升"与"专家绝对能力"的不对称。为什么只用输入过滤和拒答构建的安全论证是不完整的？

**Q16.**（场景设计）讲义练习 4：为一个具备网络能力的前沿模型构建安全论证，使它同时约束新手与专家的提升。请按第 18 节的三支柱组织你的论证。

**Q17.**（追问型）防御侧的 "trusted access" 试点能否抵消攻击侧的 uplift？它的前提条件与风险是什么？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义的三阶段："2024 'mild uplift'"（早期 Preparedness / RSP 评估显示新手相对互联网搜索有小幅优势）→ "April 2025 'on the cusp'"（OpenAI PF v2）→ "2025 Anthropic bioweapon-acquisition trial"（对照新手研究，获取阶段任务 2.53x，不足以排除 ASL-3）。A、B 方向错误；D 与讲义"在十八个月内发生了定性变化"相矛盾。

### Q2 — 答案：A

讲义正文："automate 80-90% of a cyberattack campaign. Human intervention was required in only 4-6 steps." 注意讲义摘要写的是 "up to 90%"，正文与代码写的是 "80-90%"，表述略有差异但不矛盾。B、C、D 都与报告结论相反。

### Q3 — 答案：D

讲义："Historic defense: information is necessary but not sufficient; the skill of executing the protocol blocks novices. 2025 frontier models with vision break this defense partially"。A 只是上下文长度，与执行技能无关；B、C 是编造的。讲义同时强调"Procurement and equipment gaps remain, but the tacit-knowledge gap is narrowing"——被侵蚀的是**隐性知识**鸿沟，采购与设备鸿沟依然存在。

### Q4 — 答案：B

讲义："fissile-material acquisition dominates the difficulty, not information. AI uplift on the information layer provides limited novice uplift in practice." A、C 是编造的；D 与讲义结论相反。代码中核领域的 `2024_state` 与 `2025_state` 都是 "limited"。

### Q5 — 答案：A

讲义："addressing only novice uplift (via input filters, refusals, uncertainty) is insufficient for expert-absolute control. Additional measures required: elicitation-hardening, capability unlearning (Lesson 17), and control protocols (Lesson 10)." B、C 错在忽视专家"知道该问什么、如何解读"的优势；D 过度乐观。

### Q6 — 答案：D

CBRN 是 Chemical、Biological、Radiological、Nuclear 的通行缩写（常见变体 CBRNE 再加 Explosives）。本节把生物、化学、网络、核称为"four CBRN domains"，代码 TAKEAWAY 也写 "three of four CBRN domains"——严格说网络不属于 CBRN，放射性（radiological）反而没有讨论。更准确的说法是"CBRN + cyber"或"四个两用领域"。A、B、C 都是错误的解释。

### Q7 — 答案：C

第 18 节讲义："The standard structure targets three pillars: monitoring, illegibility, incapability"。A 是第 8 节 Apollo 的 **scheming** 三柱（目标不一致、目标导向、情境感知），两个"三支柱"名称相同、含义不同，最容易混淆；B 是第 29 节的三层审核；D 是第 18 节中 PF v2、各框架的其他组成部分。

### Q8 — 答案：B

讲义："OpenAI's 'trusted access' pilot provides vetted security organisations (established incident-response firms, government) with capability access for defense. Asymmetry in access favors defenders if the pilot scales." 关键是"如果规模化"这一条件（见 Q17）。A、C、D 与讲义无关。

### Q9 — 参考答案

1. **TAKEAWAY 是写死的**：`DOMAINS` 中没有"是否越过阈值"字段，"three of four" 是手写的文字。一种推导方式是比较两年的状态：

```python
crossed = [d["domain"] for d in DOMAINS if d["2024_state"] != d["2025_state"]]
print(f"{len(crossed)} of {len(DOMAINS)} domains changed: {crossed}")
```

实测输出 `['bio', 'chem', 'cyber']`，共 3 个。但"状态字符串变了"只是代理指标；更稳妥的是显式增加 `crossed_threshold: bool` 字段并注明依据（哪份报告、哪个阈值），由数据生成结论。

2. **键名不是合法标识符**：`"2024_state"` 以数字开头，作为字典键没问题，但不能作为属性名或 dataclass 字段。实测 `make_dataclass("D", ["domain", "2024_state"])` 抛出 `TypeError: Field names must be valid identifiers: '2024_state'`。应改名为 `state_2024`，或者改成 `states: dict[int, str]`（如 `{2024: "mild uplift", 2025: ...}`），后者还便于将来加入 2026 年数据。

3. **缺失的证据**：
   - 化学 / 生物：2025 年 12 月 OpenAI 演示 GPT-5 迭代湿实验带来的 79x 效率提升（讲义正文与 SVG 都有，代码没有）；
   - 生物：OpenAI PF v2 "on the cusp" 的表述；
   - 网络：OpenAI "trusted access" 防御侧试点；
   - 核：讲义指出它是"公开文献中分析最少"的领域，代码只写 "limited"，没有体现"证据稀少"与"能力有限"是两回事；
   - 每条状态的**来源**（报告名称、日期），而技能文件要求按 2025 基准对照时引用来源。

### Q10 — 参考答案

用 Python 计算：

| 人群 | 无 AI | 有 AI | 相对提升 | 绝对提升 |
|------|------|------|---------|---------|
| 新手 | 0.10 | 0.253 | **2.53x** | +15.3 个百分点 |
| 专家 | 0.60 | 0.80 | **1.33x** | +20.0 个百分点 |

（数字是为说明概念而假设的，只有 2.53x 这个倍数取自讲义。）

- 只看相对倍数，会得出"AI 主要帮助新手，专家几乎不受影响"的结论；
- 但专家的**绝对提升更大**（+20 vs +15.3 个百分点），最终能力水平也高得多（0.80 vs 0.253）；
- 讲义："AI provides greater relative uplift to novices but greater absolute capability to experts." 安全论证必须同时报告两个维度，技能文件的硬性拒绝规则之一就是"Any dual-use safety claim without novice-vs-expert decomposition"。
- 另外，倍数对低基线很敏感：基线 0.01 → 0.03 也是 3x，但绝对风险可能仍很低；反之亦然。

### Q11 — 参考答案

实际运行结果：

```text
Agentic coding tool automated most of an intrusion campaign
  -> (['cyber'], 'undetermined (hard reject: no novice/expert decomposition)')
Vision model corrects wet-lab protocol errors for novice users in real time
  -> (['bio', 'chem'], 'novice-relative')
Model helps experts with nuclear-domain reasoning; novices show no gain
  -> (['nuclear'], 'both')
New model scores higher on a benchmark
  -> ([], 'undetermined (hard reject: no novice/expert decomposition)')
```

- 第 1 条：领域正确；提升类型判为"无法确定"也合理——技能文件要求先补充新手 / 专家分解，否则硬性拒绝。
- 第 2 条：`wet-lab` 同时出现在 bio 与 chem 的关键词中，返回两个领域；技能文件允许"Multi-domain claims get multi-domain triage"，所以这是可以接受的保守结果。
- 第 3 条：**错误**。声明明确说"新手没有提升"，应为 `expert-absolute`；函数只做了关键词共现，无法理解否定（"show no gain"）。
- 第 4 条：领域为空，正确地暴露了"声明缺少领域信息"的问题。

结论：关键词分诊只能作为预筛选；真实的分诊需要读完整报告、看评估设计（对照组、受试人群），由人来判断。

### Q12 — 参考答案

```python
PILLARS = {
    "bio": ["incapability"],                       # 第 18 节：CBRN 案例以能力遗忘为主
    "chem": ["incapability"],
    "cyber": ["monitoring", "illegibility", "incapability"],   # "all three are relevant"
    "nuclear": ["incapability"],
}
for d in DOMAINS:
    d["primary_pillars"] = PILLARS[d["domain"]]
    print(f"{d['domain']:8} -> {', '.join(d['primary_pillars'])}")
```

- 生物、化学：第 18 节明确说 ASL-3 CBRN 案例以 incapability（通过 unlearning）为主要目标。
- 网络：第 18 节明确说三个支柱都相关——agentic 攻击是多步过程，既要证明模型做不到（incapability），也要证明它无法连贯执行完整计划（illegibility），还要能在部署中监控（monitoring）。
- 核：讲义没有单独给出。参考答案填 incapability，理由是核属于 CBRN、讲义认为信息层提升有限，安全论证可以主要依靠"模型不具备关键能力 + 材料获取瓶颈"；但应注明这是推断而非讲义原文，并说明如果出现新证据（练习 3 讨论的"AI 突破改变瓶颈"）需要重新评估。

### Q13 — 参考回答要点

- **定义**：uplift 是"归因于 AI 协助的攻击者能力增量"，通常通过有 / 无 AI 的对照研究测量。
- **生物**：从 2024 年轻微提升，到 2025 年 4 月 PF v2 "on the cusp"，再到 Anthropic 2025 获取阶段任务 2.53x、不足以排除 ASL-3。
- **化学**：执行鸿沟被具备视觉能力的模型侵蚀（实时纠错），OpenAI 2025 年 12 月演示湿实验协议优化 79x 效率提升。
- **网络**：2025 年 11 月 Anthropic 报告，agentic coding 工具自动化攻击活动的 80–90%，人工 4–6 步。
- **核**：公开分析最少，材料获取主导难度，没有越过阈值的报告。
- **总结**：三个领域越过阈值，一个仍受非信息性障碍约束。
- 加分点：指出"变化是定性的、并不需要能力突破"；说明证据来源（第 17 节 WMDP 是测量方法，第 30 节是测量结果）。

### Q14 — 参考回答要点

- **为什么曾是防线**：危险任务除了"知道怎么做"，还需要大量隐性知识——操作手法、识别异常、出错后的调整。这些很难通过文字传递，新手即使拿到信息也常常失败。
- **为什么被侵蚀**：
  - 视觉能力让模型能"看见"操作过程并实时指出错误，相当于把专家的隐性知识即时传给新手（讲义：GPT-5.2、Gemini 3 Pro、Claude Opus 4.5、Grok 4.1 等可观看湿实验视频并纠错）；
  - agentic 能力让模型能迭代优化流程（讲义：79x 效率提升的演示）。
- **剩余瓶颈**：采购（病原体、前体化学品）、专用设备、许可与监管、核领域的材料获取。技能文件称这些非信息性瓶颈是"最后一道防线"（defense of last resort）。
- 加分点：讲义练习 2 要求设计"在不越过 ITAR / EAR 出口管制边界的前提下测量隐性知识提升"的评估——说明这类评估本身也必须谨慎设计，例如使用无害的替代任务（proxy tasks）。

### Q15 — 参考回答要点

- **新手相对提升**：新手基线低，AI 补齐的是"不知道该问什么"的部分，提升呈倍数（2.53x）；输入过滤、拒答、表达不确定性对新手有效，因为新手的请求往往直接、容易识别。
- **专家绝对能力**：专家能把危险任务拆成看似无害的子问题，能识别并纠正模型的错误，能从部分信息中拼出全貌；因此专家能从模型中提取的能力上限更高。
- **为什么只靠过滤不完整**：过滤器针对的是"可识别的请求"，而专家的请求可以被拆分和改写；需要：
  - elicitation-hardening：让模型在各种诱导方式下都不暴露危险能力；
  - capability unlearning（第 17 节）：直接从模型中移除相关知识，对应 incapability 支柱；
  - control protocols（第 10 节）：假设模型可能被滥用，部署时加监控与审查。
- 常见误区：用"新手试验中提升不大"推出"模型安全"——专家绝对能力需要单独评估。

### Q16 — 参考回答要点

- **Incapability（不具备能力）**：在网络能力评估（如 CTF 类任务、真实漏洞环境的受控测试）上证明模型无法独立完成关键阶段；对特定危险知识做能力遗忘并用评估验证；分别报告新手协助与专家协助两种设置的结果。
- **Illegibility（无法连贯执行计划）**：证明在给定的行动预算内，模型无法把侦察、利用、后渗透、外传串成连贯的端到端攻击；重点评估那 4–6 个人工步骤是否会被自动化（讲义练习 1）。
- **Monitoring（可监控）**：部署层面对 agentic coding 会话做行为监控、异常检测、账户级风险评分；对可疑模式中断会话并人工复核；保留审计日志以支持事后调查（Anthropic 的报告本身就依赖这种监控）。
- **新手 vs 专家**：新手侧主要靠过滤与拒答；专家侧依赖 incapability 与 monitoring，因为专家可以绕过过滤。
- **防御侧**：配合 trusted access，把高能力优先提供给经过审查的防御者。
- 加分点：说明证据要可被外部复核（第 28 节外部评估者），以及当新证据推翻某个支柱时的回滚计划。

### Q17 — 参考回答要点

- **能起到的作用**：防御者（事件响应、政府）获得同等或更强的能力，可以更快发现漏洞、分析攻击、修补系统；讲义："Asymmetry in access favors defenders if the pilot scales."
- **前提条件**：
  - 审查机制可靠（谁算"可信"、如何持续审查）；
  - 规模足够大，防御者确实在用；
  - 攻击者无法通过其他渠道获得同等能力（开源模型、被盗凭证、被滥用的普通账户——2025 年 11 月的案例正是通过普通工具访问发生的）。
- **风险**：可信方的账户被入侵或内部人员滥用；"可信"名单本身引发公平性与治理争议；防御通常比攻击更难（需要处处设防）。
- 结论：trusted access 是对 uplift 的部分对冲，而不是替代；仍需要能力评估、部署监控与安全论证。
- 常见误区：把"给防御者开放能力"当作"攻击风险已经解决"。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 17 WMDP 与两用能力 Evaluation](../../17-wmdp-dual-use-evaluation/docs/zh.md)：讲义列出的先修课，本节的测量方法与能力遗忘。
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：ASL-3、PF v2 与安全论证三支柱。
- [阶段 18 · 28 Alignment 研究生态：MATS、Redwood、Apollo、METR](../../28-alignment-research-ecosystem/docs/zh.md)：讲义列出的先修课，外部评估者。
- [阶段 18 · 10 AI 控制：面对蓄意破坏仍能保障安全](../../10-ai-control-subversion/docs/zh.md)：应对专家绝对能力所需的控制协议。
- [阶段 18 · 08 前沿模型中的上下文内密谋](../../08-in-context-scheming-frontier-models/docs/zh.md)：另一个"三支柱"（scheming 三条件），注意与安全论证三支柱区分。

### 本节被哪些后续内容用到
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)、[阶段 18 · 25 EchoLeak 与 AI 领域 CVE 的出现](../../25-echoleak-cves-for-ai/docs/zh.md)：讲义说第 24–25 节提供监管与披露层，本节证据最终要落到这两层。
- [阶段 18 · 29 内容审核系统：OpenAI、Perspective、Llama Guard](../../29-moderation-systems-openai-perspective-llamaguard/docs/zh.md)：输入过滤在两用场景中的作用与局限。
- [阶段 19 · 15 宪法式安全 Harness 与红队演练场](../../../19-capstone-projects/15-constitutional-safety-harness/docs/zh.md)：综合项目中实践安全评估与红队。
- [阶段 19 · 01 终端原生 Coding Agent](../../../19-capstone-projects/01-terminal-native-coding-agent/docs/zh.md)：agentic coding 是本节网络案例中的"攻击自动化原语"，构建它时就要考虑权限与 hook 的安全设计。

### 延伸关键词
`dual-use` · `uplift study` · `novice-relative / expert-absolute` · `execution gap` · `tacit knowledge` · `ASL-3` · `Preparedness Framework v2` · `safety case` · `capability unlearning` · `elicitation-hardening` · `trusted access` · `CBRN`
