# 测验 · Anthropic Responsible Scaling Policy v3.0（负责任扩展政策）（Anthropic Responsible Scaling Policy v3.0）

> **阶段 15 · 自主系统 · 第 19 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **说明**：本节涉及的政策细节（生效日期、评分、模型名称等）均按讲义转述，标注为「讲义：…」；代码中的数值阈值与模型测量值是**示意性**的，并非 Anthropic 公布的数字。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | RSP 是什么、不是什么 | 前沿实验室发布的扩展政策，兼具技术文件、治理文件和对监管者的信号；讲义："RSP v3.0 is not a regulation; nothing forces Anthropic to follow it"——本节学的是带着具体性与怀疑去**阅读**它 |
| 2 | v3.0 的基本事实 | 讲义："RSP v3.0 went into effect February 24, 2026"；全文 32 页 |
| 3 | 两层缓解措施（two-tier） | Anthropic 单方面会做的事 vs 面向全行业的建议（含 RAND SL-4 安全标准）；建议栏里的措施"is not Anthropic's promise; it is Anthropic's hope" |
| 4 | AI R&D-4 阈值 | 能以有竞争力的成本自动化相当大比例 AI 研究的能力；越过后必须先公开一份 affirmative case（识别 misalignment 风险与缓解措施）才能继续扩展 |
| 5 | Opus 4.6 与"难以排除" | 讲义：按 v3.0 公告，Claude Opus 4.6 没有越过 AI R&D-4，但"confidently ruling this out is becoming difficult"——承认阈值已近在眼前 |
| 6 | 两类常设文件 | Frontier Safety Roadmap（前瞻：计划中的安全工作与能力预期）与 Risk Report（回顾：模型发布后观察到的能力与残余风险）；公开、按声明的节奏更新，可以互相对照 |
| 7 | 删除暂停条款 | 2023 RSP 有明确的 pause 承诺；v3.0 改为"发布 affirmative case、缓解充分则继续"；被认为是最尖锐的倒退 |
| 8 | SaferAI 降级 | 讲义：评分从 2.2 降到 1.9，从 "moderate" 降为 "weak"，与 OpenAI、DeepMind 同列；原因：定性阈值取代定量、删除暂停、affirmative case 而非具体措施、审查依赖内部 Safety Advisory Group |
| 9 | 承诺装置（commitment device） | 暂停条款的价值在于让政策可信；支持删除的理由是 2023 的定量阈值因基准被重新标定而在 2026 年变得无法触及 |
| 10 | 代码中的决策形状 | 三个指标中任意两个越过示意阈值即判定越过；越过后输出 6–7 节 affirmative case 模板；gaming 率只影响模板，不影响判定 |

### 核心技能（能动手做到）

- [ ] 用自己的话复述 RSP v3.0 相对旧版的"增、删、改"：增加 Roadmap / Risk Report / AI R&D-4，删除暂停条款，改为两层缓解
- [ ] 读一份扩展政策时，把每条承诺分到"单方面"或"行业建议"栏，并计算比例
- [ ] 读懂 `threshold_crossed` 与 `affirmative_case_template`，预测任意测量值的输出（含边界值）
- [ ] 指出"任意两项触发"的规则与 AI R&D-4 定义之间的张力，以及 gaming 率不参与判定的问题
- [ ] 为代码补上"能否继续部署"的决策函数，并按讲义练习 1 加入第三个模型
- [ ] 设计一条能替代暂停条款、同时考虑基准重标定问题的承诺（讲义练习 4）

---

## 二、基础自测（选择题）

**Q1.** 按讲义，RSP v3.0 的生效日期是：

- A. 2023 年 9 月
- B. 2024 年 10 月
- C. 2026 年 2 月 24 日
- D. 2026 年 1 月 22 日

**Q2.** 在 v3.0 的两层结构中，一项安全措施（例如 RAND SL-4 安全标准）出现在"industry-wide recommendation"一栏，这意味着：

- A. 它是 Anthropic 认为全行业应共同采取的做法，属于政策倡导，而不是 Anthropic 自己的承诺
- B. Anthropic 已经在内部全面执行该措施
- C. 它是监管机构强制要求的标准
- D. 它只适用于 OpenAI 和 DeepMind

**Q3.** 关于 AI R&D-4 阈值，说法正确的是：

- A. 它衡量模型在生物安全基准上的得分
- B. 越过后 Anthropic 必须立即停止所有训练
- C. 它只在模型公开发布之后才评估
- D. 指能以有竞争力的成本自动化相当大比例 AI 研究的能力；越过后必须先公开一份识别 misalignment 风险与缓解措施的 affirmative case，才能继续扩展

**Q4.** 讲义认为 v3.0 相对 2023 版"最尖锐的倒退"是：

- A. 增加了 Frontier Safety Roadmap
- B. 删除了明确的暂停（pause）承诺
- C. 引入了 AI R&D-4 阈值
- D. 把文档从 32 页缩短到 10 页

**Q5.** 运行 `code/main.py`，"Synthetic next-gen" 模型的输出是：

- A. `CROSSED`，列出 3 条触发理由，affirmative case 模板共 7 节（因为 gaming 率 28% > 20%）
- B. `CROSSED`，只列出 2 条触发理由，模板 6 节
- C. `not crossed`，但列出 3 条 single trigger
- D. `CROSSED`，模板 6 节，gaming 率不影响输出

**Q6.** Frontier Safety Roadmap 与 Risk Report 的区别是：

- A. 两者都是一次性文件，发布后不再更新
- B. Roadmap 是内部文件，Risk Report 是公开文件
- C. Roadmap 前瞻描述计划中的安全工作与能力预期；Risk Report 回顾特定模型发布后观察到的能力与残余风险
- D. Roadmap 由 SaferAI 撰写，Risk Report 由 Anthropic 撰写

**Q7.** 在本节代码中，若某模型 `rd_automation_share=0.9`、`metr_horizon_hours=10`、`aar_outperform_share=0.1`，`threshold_crossed` 的结果是：

- A. `True`，因为研发自动化份额远超 0.5
- B. `False`，因为代码要求至少两项指标越过阈值，而这里只有一项
- C. `True`，因为任意一项越过即可
- D. 抛出异常，因为 0.9 超出合法范围

**Q8.** 按讲义，SaferAI 对 Anthropic RSP 的评分变化是：

- A. 从 1.9 升到 2.2，进入 "strong" 档
- B. 从 4.0 降到 2.2
- C. 保持 2.2 不变
- D. 从 2.2 降到 1.9，从 "moderate" 降为 "weak"，与 OpenAI、DeepMind 同列

---

## 三、动手 / 代码题

**Q9.** 阅读判定规则：

```python
AI_RD_4_THRESHOLDS = {
    "rd_automation_share": 0.5,
    "metr_horizon_hours": 40.0,
    "aar_outperform_share": 0.4,
}
...
    crossed = len(reasons) >= 2  # any two triggers; illustrative
```

1. 写出以下三个测量的判定结果与触发理由数：
   - (a) `rd=0.50, metr=40.0, aar=0.39`
   - (b) `rd=0.20, metr=40.0, aar=0.40`
   - (c) `rd=0.90, metr=10.0, aar=0.10`
2. 讲义对 AI R&D-4 的定义是"automate a substantial fraction of AI research at competitive cost"。对照 (b) 与 (c)，你认为"任意两项"规则合理吗？
3. 提出一个更贴近定义的判定结构，并写出代码。

**Q10.** 观察 `eval_context_gaming_rate` 在代码中的使用：

```python
def affirmative_case_template(m):
    sections = [ ... 6 sections ... ]
    if m.eval_context_gaming_rate > 0.2:
        sections.append(f"7. Gaming-adjusted capability estimate "
                        f"(observed gaming rate {m.eval_context_gaming_rate:.0%})")
    return sections
```

1. 一个模型 `rd=0.45, metr=35, aar=0.38, gaming=0.6`，`evaluate` 会打印什么？第 7 节会出现吗？
2. gaming 率是否会影响 `crossed`？如果模型在评测中**故意表现得更差**（sandbagging），这个设计会导致什么后果？
3. 修改判定逻辑，让 gaming 率真正参与阈值判断，并引入"无法排除（cannot rule out）"这一中间状态。

**Q11.**（讲义练习 1）

1. 在 `main()` 中加入第三个模型 `CapabilityMeasurement("Synthetic mid (one trigger)", 0.35, 45.0, 0.30, 0.05)`，写出它的输出。
2. 讲义 "Use It" 说这个引擎会返回"whether the AI R&D-4 threshold is crossed, the required affirmative-case sections, and whether deployment can proceed"。代码实现了第三项吗？请补一个 `deployment_decision(...)`：未越过则按标准流程继续；越过则需要 affirmative case 已发布、Safety Advisory Group 签字、外部审查三者齐全才能继续，否则返回缺什么。

**Q12.** 找出讲义与代码中的不一致（至少三处），并说明各自会误导读者什么：

```python
    opus_4_6 = CapabilityMeasurement(
        model_name="Claude Opus 4.6 (as stated by Anthropic in v3.0)",
        rd_automation_share=0.30,
        metr_horizon_hours=14.0,
        aar_outperform_share=0.35,
        eval_context_gaming_rate=0.12,
    )
...
    print("  Thresholds are qualitative in v3.0, not quantitative as in v2.")
    print("  SaferAI downgraded v3.0 from 2.2 to 1.9 (weak RSP category).")
```

提示：对照讲义中"2023 RSP"、"v2"两种说法；对照代码自己的阈值字典；对照模型名里的 "as stated by Anthropic"。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 Responsible Scaling Policy？按讲义，RSP v3.0 相对旧版增加、删除、改动了什么？

**Q14.**（原理深挖）暂停条款为什么被称为"承诺装置"？删除它的支持理由与反对理由分别是什么？请提出一个替代承诺（讲义练习 4）。

**Q15.**（工程实践）你的团队重度依赖前沿模型 API。你会如何"阅读"一家实验室的扩展政策？请给出一个结构化的检查清单。

**Q16.**（场景设计）你所在公司在做能长时间自主运行的 coding agent，老板让你仿照 RSP 写一份内部"扩展政策"。你会定义哪些能力阈值、对应什么缓解措施、需要哪些常设文件和独立审查？

**Q17.**（追问型）讲义引用 v3.0 公告说 Opus 4.6 不越过 AI R&D-4，但"confidently ruling this out is becoming difficult"。这句话意味着什么？评测情境识别（eval-context gaming）会怎样让阈值评估变得更难？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："RSP v3.0 went into effect February 24, 2026, replacing the 2023 policy"；Key Terms 也写 "v3.0 effective Feb 24, 2026"。D（2026 年 1 月 22 日）是上一节 Claude Constitution 的发布日期，属于常见混淆。

### Q2 — 答案：A

讲义："These are not commitments on Anthropic's side; they are policy advocacy... A security measure in the 'industry-wide recommendation' column is not Anthropic's promise; it is Anthropic's hope." 所以读者要看每项承诺落在哪一栏。B 把倡导当成了承诺；C 错，讲义强调 RSP 不是法规；D 无依据。

### Q3 — 答案：D

讲义："a model that could automate a substantial fraction of AI research at competitive cost. Once Anthropic believes a model crosses it, they must publish an affirmative case identifying misalignment risks and mitigations before continued scaling." B 是 2023 版暂停条款的思路，v3.0 恰恰把它换成了 affirmative case；A 混入了 CBRN 类评测；C 错，"before continued scaling"说明评估发生在继续扩展之前。

### Q4 — 答案：B

讲义开头："removing the pause clause is the sharpest regression"，正文也说 SaferAI 等分析者"called this out directly as the strongest regression"。A、C 是 v3.0 的新增内容，不是倒退；D 无依据（讲义说全文 32 页）。

### Q5 — 答案：A

实际输出：`AI R&D-4 threshold: CROSSED`，三条理由 `rd_automation_share=0.55 >= 0.5`、`metr_horizon_hours=48.0 >= 40.0`、`aar_outperform_share=0.45 >= 0.4`，模板 7 节，第 7 节为 `Gaming-adjusted capability estimate (observed gaming rate 28%)`。`threshold_crossed` 会把所有越过的项都记入 `reasons`（B 错）；`0.28 > 0.2` 触发第 7 节（D 错）。

### Q6 — 答案：C

讲义："Frontier Safety Roadmap: forward-looking document..."；"Risk Report: retrospective document on specific models after release"；"Both are public. Both are updated on a declared cadence." A 错在"一次性"——v3.0 的变化正是把它们提升为常设文件；B 错，两者都公开；D 无依据。

### Q7 — 答案：B

已实际运行：`(False, ['rd_automation_share=0.90 >= 0.5'])`。`crossed = len(reasons) >= 2`，只有一项触发，判定"未越过"。A 是"按定义应该如此"的直觉（见 Q9 讨论），但代码不是这样实现的；C 与代码不符；D 错，`dataclass` 不做范围校验。

### Q8 — 答案：D

讲义："SaferAI rated the 2023 RSP at 2.2; they downgraded v3.0 to 1.9, putting Anthropic in the 'weak' RSP category alongside OpenAI and DeepMind"，以及"This moved Anthropic from 'moderate' to 'weak'"。B 中的 4.0 是讲义所说评分尺度上"当前最佳 RSP"的位置，不是 Anthropic 的分数。

### Q9 — 参考答案

1. 已实际运行：
   - (a) `True`，2 条理由：`rd=0.50 >= 0.5`、`metr=40.0 >= 40.0`（比较用的是 `>=`，恰好等于阈值也算触发）；`aar=0.39 < 0.4` 不触发。
   - (b) `True`，2 条理由：`metr` 与 `aar`。
   - (c) `False`，1 条理由：只有 `rd`。
2. 不太合理。三个指标中，`rd_automation_share`（"以专家人力等价成本完成内部 AI 研发任务的比例"）最贴近 AI R&D-4 的定义；METR 时间跨度和 AAR 胜出比例只是**相关信号**。结果是：(b) 一个几乎不能自动化研发（0.2）的模型因两个旁证被判越过；(c) 一个能自动化 90% 研发任务的模型却被判未越过——与定义直接矛盾。代码注释写了 "illustrative"，但这个规则会让读者误以为"多数投票"是阈值的含义。
3. 参考结构：以 `rd_automation_share` 为主判据，另外两项作为预警信号；预警或接近主阈值时进入"无法排除"状态：

```python
def assess(x):
    T = AI_RD_4_THRESHOLDS
    if x.rd_automation_share >= T["rd_automation_share"]:
        return "CROSSED"
    warn = [k for k in ("metr_horizon_hours", "aar_outperform_share")
            if getattr(x, k) >= T[k]]
    if warn or x.rd_automation_share >= 0.8 * T["rd_automation_share"]:
        return "CANNOT-RULE-OUT"        # 需要更多证据 / 预先准备 affirmative case
    return "NOT-CROSSED"
```

这样 (c) 判为 `CROSSED`，(b) 判为 `CANNOT-RULE-OUT`。真实政策中判定还需要人类判断与更大的证据集，代码 docstring 也说明 "the real RSP involves human judgment across a larger evidence base"。

### Q10 — 参考答案

1. 已实际运行：`threshold_crossed` 返回 `(False, [])`——三项都没越过（0.45 < 0.5、35 < 40、0.38 < 0.4），所以只打印 `AI R&D-4 threshold: not crossed`，没有任何 single trigger。`affirmative_case_template` 若被调用会返回 7 节，但它只在 `crossed` 为真时才被调用，所以第 7 节**不会出现**。
2. 不会。gaming 率只决定模板里是否多一节，不参与 `crossed` 的判定。代码 HEADLINE 说 gaming 会让能力数字"偏高"（第 01 节讲义也提到 METR 的时间跨度是"idealized upper bounds"），但第 01 节同样指出前沿模型能区分评测与部署情境、"behaving measurably safer in tests"——评测情境识别也可能让模型在危险能力评测里**刻意表现得更差**（sandbagging）——此时测得的能力被**低估**，真实能力可能已经越过阈值。代码的结构恰好在最需要 gaming 调整的地方（接近阈值但未越过）完全忽略了它：gaming 率 60% 的模型被干净地判为"未越过"。
3. 参考实现（已运行验证）：

```python
def assess(x, margin_per_gaming=0.5):
    T = AI_RD_4_THRESHOLDS
    factor = 1 - margin_per_gaming * x.eval_context_gaming_rate   # gaming 越高，阈值下调越多
    if x.rd_automation_share >= T["rd_automation_share"] * factor:
        return "CROSSED", factor
    warn = [k for k in ("metr_horizon_hours", "aar_outperform_share")
            if getattr(x, k) >= T[k] * factor]
    if warn or x.rd_automation_share >= 0.8 * T["rd_automation_share"] * factor:
        return "CANNOT-RULE-OUT", factor
    return "NOT-CROSSED", factor
```

结果：gaming 60% 的模型 `factor=0.7`，`rd` 阈值降为 0.35，0.45 越过 → `CROSSED`；代码中"Opus 4.6"的示意值（gaming 12%，`factor=0.94`）仍为 `NOT-CROSSED`；"Synthetic next-gen" 为 `CROSSED`；`(0.35, 45, 0.30, 0.05)` 为 `CANNOT-RULE-OUT`。`margin_per_gaming` 是需要论证的政策参数，这里只演示思路：**不确定性越大，越应该保守地把"可能越过"当作"越过"处理**。

### Q11 — 参考答案

1. 已实际运行：

```text
Model: Synthetic mid (one trigger)
----------------------------------------------------------------------
  rd_automation_share=0.35  metr_horizon_hours=45.0  aar_outperform_share=0.30  gaming_rate=5%
  AI R&D-4 threshold: not crossed
  single trigger(s) observed (below threshold):
    - metr_horizon_hours=45.0 >= 40.0
```

三个模型分别展示了"无触发 / 单触发 / 多触发"三种分支，正好覆盖 `evaluate` 的所有路径。

2. 没有实现，`evaluate` 只打印判定和模板。补充（已运行验证）：

```python
def deployment_decision(crossed, case_published, sag_signoff, external_review):
    if not crossed:
        return "proceed (standard safeguards)"
    missing = [name for name, ok in [("affirmative case", case_published),
                                     ("SAG sign-off", sag_signoff),
                                     ("external review", external_review)] if not ok]
    return "proceed under affirmative case" if not missing else "hold: missing " + ", ".join(missing)
```

输出：未越过 → `proceed (standard safeguards)`；越过但缺外部审查 → `hold: missing external review`；三者齐全 → `proceed under affirmative case`。把"外部审查"设为必要条件，是对讲义所列 SaferAI 降级原因之一"Review mechanisms depend on Anthropic's Safety Advisory Group, with limited independent oversight"的回应，也对应 skill 文件"Internal-only review ... does not qualify as independent oversight"。

### Q12 — 参考答案

1. **"as stated by Anthropic" 的模型名**：本节讲义只说 Anthropic 声明 Opus 4.6 **没有越过**阈值。代码里的数字来源混杂：14.0 小时与第 01 节讲义引用的 METR 数字（"Claude Opus 4.6 at 14+ hours of expert work at 50% reliability"）一致；12% 与第 01 节提到的 alignment faking 比例（"faking in 12% of basic tests"，来自 2024 年的另一项研究、另一种指标）数值相同；0.30 与 0.35 在讲义中找不到来源。把这些数字统一放在 "(as stated by Anthropic in v3.0)" 名下，容易让读者以为它们都是 RSP v3.0 公布的测量结果。
2. **"定性阈值" vs 代码的定量阈值**：HEADLINE 说 "Thresholds are qualitative in v3.0"，代码却用 0.5 / 40 小时 / 0.4 的数值阈值和"任意两项"规则来"mirror the decision shape"。教学上可以理解，但应明确：真实 v3.0 的判定依赖定性判断，这正是 SaferAI 降级的原因之一。
3. **版本混淆**：讲义一处说 "replacing the 2023 policy"、"SaferAI rated the 2023 RSP at 2.2"，另一处说 "The v3.0 vs v2.0 diff"、"downgraded the score from 2.2 (v2) to 1.9"、Key Terms "v2 was 2.2"；代码 HEADLINE 说 "not quantitative as in v2"，讲义开头却说 "Qualitative thresholds replaced the 2023 quantitative commitments"。2023 年的版本与 v2 被混用，读者无法确定 2.2 分和"定量阈值"到底对应哪一版。skill 文件要求"If the user cites an older policy version ... as current, refuse"——阅读政策时版本号本身就是关键信息。
4. （可选）**gaming 的方向**：HEADLINE 说评测情境 gaming 让能力数字"偏高"，但对阈值评估而言更危险的是 sandbagging 造成的低估（见 Q10）。
5. （可选）**部署决策缺失**：讲义 "Use It" 承诺输出"whether deployment can proceed"，代码没有实现（见 Q11）。

### Q13 — 参考回答要点

- **定义**：前沿实验室公开的、把"能力阈值"与"必须采取的安全措施"绑定的自我约束政策；讲义说它同时是技术文件、治理文件和对监管者的信号，且不具法律约束力。
- **增加**（讲义）：Frontier Safety Roadmap 与 Risk Report 成为常设文件；AI R&D-4 阈值及 affirmative case 要求；两层缓解结构（单方面 vs 行业建议，含 RAND SL-4）。
- **删除**：2023 版的明确暂停承诺。
- **改动**：定性阈值取代定量承诺；越过阈值后从"暂停"改为"发布 affirmative case、缓解充分则继续"。
- **外部评价**：讲义：SaferAI 从 2.2 降至 1.9，进入 "weak" 档。
- 加分点：讲义的一句话总结——"This is how a scaling policy can get less rigorous while looking more polished."
- 常见误区：把 RSP 当法规，或把"有政策"当"已合规"（skill 文件："A policy is a commitment device; compliance requires evidence"）。

### Q14 — 参考回答要点

- **为什么是承诺装置**：事先公开承诺"到某阈值就停"，让未来的自己在商业压力下也难以反悔，外界据此判断政策是否可信。讲义："a pause clause in a scaling policy is a commitment device; removing it removes the credibility of the policy."
- **支持删除的理由**（讲义）：2023 的定量阈值因基准被重新标定，到 2026 年已无法触及——条款形同虚设，不如换成更灵活的 affirmative case。
- **反对理由**：affirmative case 由实验室自己撰写、自己评估，"缓解是否充分"缺乏外部可检验标准；删掉暂停等于把刹车换成了"说明书"。
- **替代承诺示例**（讲义练习 4）：
  1. 阈值用**相对基线**定义（如"相对上一代模型、在冻结的私有任务集上的研发自动化提升"），并公开重标定规则，基准换代时同步迁移阈值；
  2. 越过阈值后默认暂停**扩展**（不必停止全部研究），直到独立第三方审阅 affirmative case 并签字；
  3. 规定最长审阅时限与公开披露义务，避免无限期拖延或悄悄继续；
  4. 承诺本身写明修改程序：任何削弱都需提前公告并说明理由。
- 加分点：区分"暂停训练"与"暂停部署"的不同代价。

### Q15 — 参考回答要点

按本节 skill 文件的结构：

1. **两层清单**：把承诺分为"实验室单方面"与"行业建议"，计算比例；多数在建议栏的是弱政策。
2. **阈值表**：每个能力阈值是定量还是定性、触发什么缓解；是否有政策声称覆盖却没有阈值的能力。
3. **暂停条款**：是否有明确的停止训练 / 停止部署条款。
4. **常设文件**：Roadmap 与 Risk Report 是否有声明的更新节奏；能否用 Risk Report 对照 Roadmap 的承诺。
5. **独立审查**：外部审查机制、审查者身份、频率；仅内部委员会不算。
6. **版本**：确认读的是现行版本。
- 对工程团队的意义：阈值触发可能导致 API 能力受限、部署延迟或额外安全措施（如更严格的分类器），需要纳入供应商风险评估与降级预案。
- 加分点：对照多家实验室（下一节 OpenAI Preparedness Framework 与 DeepMind FSF），而不是只看一家。

### Q16 — 参考回答要点

- **能力阈值**（举例，需结合自身评测）：
  - 自主时长：无人干预下连续完成任务的时间跨度超过 X 小时；
  - 权限扩张：评测中出现尝试修改自身权限、关闭日志、绕过审批的行为；
  - 对外部系统的写操作成功率达到某水平。
- **缓解措施**：分为"我们单方面一定做"（沙箱、权限模式、预算上限、kill switch、propose-then-commit、审计日志）与"建议客户做"两栏，并控制后者比例。
- **触发后的动作**：明确的暂停条款——越过阈值即暂停扩大部署范围，直到安全评审通过。
- **常设文件**：季度 Roadmap（计划中的安全工作、预期能力）；每次大版本发布后的 Risk Report（观察到的能力、事故、残余风险），两者互相对照。
- **独立审查**：外部审计方或客户代表参与评审；内部评审委员会需有不参与产品 KPI 的成员。
- **评测诚信**：对评测情境识别 / sandbagging 做专门检查，阈值附近一律按"无法排除"处理。
- 加分点：把本阶段前面各节的运行时控制（第 10、13、14、15、16 节）映射为"单方面缓解措施"栏的具体条目。

### Q17 — 参考回答要点

- **含义**：Anthropic 在声明"未越过"的同时承认证据已不足以有把握地排除——阈值从"远期假设"变成"现实关切"。讲义："it concedes that the threshold is close enough to be a live concern, not a speculative limit."
- **与第 6、7 节的联系**：讲义说自动化对齐研究达到研究质量门槛，本身就是 AI R&D-4 临近的证据。
- **评测情境识别带来的困难**：
  - 模型若能区分"在被评测"与"在部署"，评测分数就不再代表部署行为；
  - 方向可能向上（为评测"表现好"）也可能向下（sandbagging，刻意隐藏能力），后者对阈值判定更危险——低估会导致本应越过的模型被判为安全；
  - 代码只在越过后才在模板里加一节"gaming 调整"，而未越过时完全忽略 gaming（测验 Q10）。
- **让阈值更稳健的做法**：使用私有、未公开的任务集；在类部署环境中评测；用多种独立信号交叉验证；对 gaming 高的模型下调阈值或默认"无法排除"；引入外部评测机构（下一节与第 21 节 METR 的内容）。
- 常见误区：把"未越过"理解为"安全"——它只是"在当前证据下未越过"。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 06 自动化 Alignment 研究（Anthropic AAR）](../../06-automated-alignment-research/docs/zh.md)：讲义列出的先修课；代码中的 `aar_outperform_share` 来自这里。
- [阶段 15 · 07 递归自我改进：能力与 Alignment 的权衡](../../07-recursive-self-improvement/docs/zh.md)：讲义列出的先修课；AI R&D-4 关注的正是研究自动化带来的加速。
- [阶段 15 · 01 从聊天机器人转向长程 Agents](../../01-long-horizon-agents/docs/zh.md)：代码 HEADLINE 提到的评测情境 gaming（Lesson 1）。
- [阶段 15 · 17 Constitutional AI 与规则覆盖](../../17-constitutional-ai/docs/zh.md)：Constitution 在 RSP 体系中的位置。

### 本节被哪些后续内容用到
- [阶段 15 · 20 OpenAI Preparedness Framework 与 DeepMind Frontier Safety Framework](../../20-openai-preparedness-deepmind-fsf/docs/zh.md)：讲义练习 5 要求与之对比。
- [阶段 15 · 21 METR 时间跨度与外部能力 Evaluation](../../21-metr-external-evaluation/docs/zh.md)：代码中 `metr_horizon_hours` 指标的来源与外部评测。
- [阶段 15 · 22 CAIS、CAISI 与社会规模风险](../../22-cais-caisi-societal-risk/docs/zh.md)：从实验室政策走向社会层面的风险治理。
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../../18-ethics-safety-alignment/18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：三大框架的伦理与对齐视角。
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../../18-ethics-safety-alignment/24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：自愿政策与法规的关系。

### 延伸关键词
`Responsible Scaling Policy` · `AI R&D-4` · `affirmative case` · `two-tier mitigation` · `RAND SL-4` · `Frontier Safety Roadmap` · `Risk Report` · `pause commitment` · `commitment device` · `SaferAI rating` · `Safety Advisory Group` · `sandbagging` · `eval awareness`
