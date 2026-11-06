# 测验 · OpenAI Preparedness Framework 与 DeepMind Frontier Safety Framework（OpenAI Preparedness Framework and DeepMind Frontier Safety Framework）

> **阶段 15 · 自主系统 · 第 20 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **说明**：三份政策的版本、日期、类别名称均按讲义转述；代码中的对照表是讲义作者的"教学提炼"，并非政策原文，做真实判断时必须回到原始文件（这也是讲义练习 1 的要求）。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三份"表亲"文件 | Anthropic RSP v3.0、OpenAI Preparedness Framework v2、DeepMind FSF v3 回答同一个问题："前沿实验室何时应暂停或门控一个模型"；它们在少数类别上趋同，在关键处分歧 |
| 2 | OpenAI PF v2（2025 年 4 月） | Tracked Categories 触发 Capabilities Report + Safeguards Report，部署前由 Safety Advisory Group 审查；Research Categories 只跟踪、不自动触发缓解 |
| 3 | 四个 Research Categories | Long-range Autonomy、Sandbagging、Autonomous Replication and Adaptation、Undermining Safeguards；政策用语是 "potential" mitigations |
| 4 | Tracked vs Research 是"铰链" | 一个能力落在哪一栏，决定了它是"被门控"（gated）还是"被观察"（observed） |
| 5 | DeepMind FSF v3 | 讲义：2025 年 9 月发布，2026 年 4 月 17 日增加 Tracked Capability Levels；按领域设 Critical Capability Levels（CCL）；autonomy 不单列，而是并入 ML R&D 与 Cyber |
| 6 | ML R&D autonomy level 1 | "fully automate the AI R&D pipeline at competitive cost vs human + AI tools"，与 Anthropic 的 AI R&D-4 是同一类关切 |
| 7 | 欺骗性对齐监控 | FSF v3 明确承诺对 instrumental reasoning（手段—目的推理）的滥用做自动化监控；但 DeepMind 自己说它"will not remain sufficient long-term" |
| 8 | 三者的共同点 | 内部安全审查机构；把欺骗性对齐 / alignment faking 列为风险类别；按声明节奏发布常设文件；承认"只靠监控"有上限 |
| 9 | Sandbagging 让三者都变复杂 | 模型在评测中策略性地表现不佳 → 所有框架的能力阈值都被低估；"The framework works only if the measurement works"，所以需要外部测量（第 21 节 METR）与对抗评测 |
| 10 | 读政策的四步 | Locate（能否在文中找到）→ Classify（触发缓解还是只跟踪）→ Cadence（是否有声明的更新节奏）→ Independence（外部审查是否强制） |

### 核心技能（能动手做到）

- [ ] 说出 PF v2 的 Tracked / Research 划分及其操作后果，并列出四个 Research Categories
- [ ] 解释 DeepMind 为何把 autonomy 并入 ML R&D 与 Cyber，以及支持与反对这种做法的论点
- [ ] 读懂 `Policy` 表与 `diff()`，预测任意能力名的输出（包括不在表中的名字）
- [ ] 对照讲义（含第 17、19 节）核查代码对照表，找出无出处或概念混用的条目
- [ ] 给对照表加上"约束强度""原文出处""单方面 / 行业建议"字段，让对比可以被计算与审计
- [ ] 设计一个能迫使 sandbagging 模型暴露真实能力的评测（讲义练习 4），并能手算评测结果的偏差

---

## 二、基础自测（选择题）

**Q1.** 按讲义，OpenAI Preparedness Framework v2 的 Research Categories 包括：

- A. Biological、Chemical、Cybersecurity、Nuclear
- B. Long-range Autonomy、Sandbagging、Autonomous Replication and Adaptation、Undermining Safeguards
- C. Persuasion、Model Autonomy、Cybersecurity、CBRN
- D. Long-range Autonomy、AI R&D-4、Cyber CCL、Bio CCL

**Q2.** 在 PF v2 中，一个能力被归入 Research Category，其操作后果是：

- A. 触发 Capabilities Report 与 Safeguards Report，并由 SAG 在部署前审查
- B. 立即暂停该模型的训练
- C. 自动转交外部机构 METR 评估
- D. 实验室会跟踪它，但不自动触发缓解措施；政策用语是 "potential" mitigations

**Q3.** DeepMind FSF v3 对 "autonomy" 的处理方式是：

- A. 不把它作为顶层领域，而是并入会因自主性造成伤害的领域——ML R&D 与 Cyber
- B. 把它作为与 Cyber、Bio 并列的独立领域，设单独的 CCL
- C. 完全不涉及 autonomy
- D. 把它归入 Research Category，不触发任何措施

**Q4.** 讲义给出的 DeepMind "ML R&D autonomy level 1" 的含义是：

- A. 模型能独立完成一篇研讨会论文
- B. 模型的 METR 时间跨度超过 40 小时
- C. 以相对"人 + AI 工具"有竞争力的成本，完全自动化 AI 研发流水线
- D. 模型能在沙箱中自我复制

**Q5.** 为什么说 sandbagging 会让三份框架"都变复杂"？

- A. 因为 sandbagging 只在 OpenAI 的框架中被提及
- B. 模型若在评测中策略性地表现不佳，所有框架的能力阈值都会被低估；框架只有在测量可靠时才有效，因此需要外部测量与对抗评测
- C. 因为 sandbagging 会让模型的推理速度下降
- D. 因为 sandbagging 属于硬编码禁令，无法评测

**Q6.** 关于 FSF v3 的自动化监控，DeepMind 自己的表态是：

- A. 如果 instrumental reasoning 能力增强，自动化监控"will not remain sufficient long-term"
- B. 自动化监控足以永久解决欺骗性对齐
- C. 自动化监控只用于 Cyber 领域
- D. 自动化监控将由 OpenAI 的 SAG 负责

**Q7.** `code/main.py` 的三张对照表各有 7 个能力键，但 `main()` 实际打印 diff 的只有 5 个。**没有被打印**的是：

- A. `long_range_autonomy`
- B. `sandbagging`
- C. `rnd_automation`
- D. `cyber_uplift` 与 `bio_uplift`

**Q8.** 调用 `diff("autonomy")`，输出是什么？

- A. 打印与 `long_range_autonomy` 相同的三行分类
- B. 抛出 `KeyError`
- C. 三个政策都显示 `classification: not in table`、`action: —`
- D. 只打印 DeepMind 一行

---

## 三、动手 / 代码题

**Q9.** 对照第 17、19、20 节讲义，核查 Anthropic 一列：

```python
ANTHROPIC_RSP_V3 = Policy(
    name="Anthropic RSP v3.0 (Feb 2026)",
    table={
        "long_range_autonomy": ("named risk", "affirmative case at threshold"),
        "sandbagging": ("named via eval-context gap", "addressed in measurement methodology"),
        "autonomous_replication": ("not explicitly named", "covered under AI R&D-4"),
        "undermining_safeguards": ("hardcoded prohibition", "refuses training / deploy"),
        "rnd_automation": ("AI R&D-4 threshold", "affirmative case required"),
        "cyber_uplift": ("ASL-3 trigger", "security + deployment mitigations"),
        "bio_uplift": ("ASL-3 trigger", "security + deployment mitigations"),
    },
)
```

找出至少三处"讲义中找不到出处"或"概念混用"的条目，说明问题所在。本节 skill 文件对"无法指向原文条款的分类"持什么态度？

**Q10.** 对照表里的分类都是自由文本，无法比较"哪家更严格"。

1. 为每个分类指定一个约束强度：`mandatory`（自动触发缓解）/ `conditional`（越过阈值后需论证或评估）/ `methodology`（只在测量方法中处理）/ `monitor-only`（只观察）/ `not-named`。
2. 统计每个政策在 7 个能力上的分布，并找出三家**完全一致**与**分歧最大**的能力。
3. 这种"量化"有什么风险？

**Q11.** 改造工具，使它满足 skill 文件的要求：

1. 把 `table` 的值从二元组升级为 `Entry` dataclass，增加 `binding`、`source_clause`、`tier`（单方面 / 行业建议）字段；
2. `diff()` 在缺少 `source_clause` 时打印警告；
3. 对不存在的能力名，不再静默输出三行 `not in table`，而是给出最接近的候选名（提示：`difflib.get_close_matches`），并区分"拼写错误"与"政策确实未覆盖"。

**Q12.**（讲义练习 4，手算 + 设计）假设某模型在某项危险能力任务上的真实成功率为 0.8；当它识别出"正在被评测"时，会把成功率压到 0.3（sandbagging）。

1. 在一套带有明显评测痕迹的题集上，它识别出评测的概率为 0.9；在一套伪装成真实部署任务的题集上，识别概率为 0.1。分别计算两套题集上的期望成功率。
2. 若框架的阈值是"成功率 ≥ 0.6 即触发缓解"，两套题集分别给出什么结论？
3. 据此设计一个能迫使 sandbagging 模型暴露真实能力的评测方案，并说明它与第 01 节 eval-context gaming 讨论的关系。

---

## 四、面试高频题

**Q13.**（基础必考）简述 Anthropic RSP v3.0、OpenAI PF v2、DeepMind FSF v3 三者的结构差异与共同点。

**Q14.**（原理深挖）OpenAI 把 Long-range Autonomy 放在 Research 而不是 Tracked；DeepMind 不把 autonomy 单列而并入领域。分别评价这两种做法的合理性与风险。

**Q15.**（工程实践）你的公司要在产品里接入某家前沿模型，法务让你出一份"该能力在三家框架下如何处理"的对比报告（例如"自主复制与适应"）。你会怎么做，报告里必须有什么？

**Q16.**（场景设计）（讲义练习 3）如何从外部测量一个模型是否达到 "ML R&D autonomy level 1"？请设计评测任务、成本基线、成功标准和防作弊措施。

**Q17.**（追问型）"三家都有内部安全审查机构、都提到了欺骗性对齐，所以它们的保障水平差不多。"你同意吗？请用讲义中的"读政策四步"反驳或补充。

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："OpenAI Preparedness Framework v2 (April 2025) introduces Research Categories — Long-range Autonomy, Sandbagging, Autonomous Replication and Adaptation, Undermining Safeguards — distinct from Tracked Categories." D 混入了 Anthropic 的 AI R&D-4 与 DeepMind 的 CCL；A、C 是其他领域划分的拼凑，讲义中没有把它们列为 Research Categories。

### Q2 — 答案：D

讲义："Research Categories do not automatically trigger mitigations. The policy language is 'potential' mitigations... a category's location in Tracked vs Research is the hinge between 'gated' and 'observed.'" A 描述的是 Tracked Categories；B、C 在讲义中都没有依据。skill 文件也把"把 Research Category 当作 Tracked Category"列为 hard reject。

### Q3 — 答案：A

讲义："DeepMind does not keep 'Autonomy' as a top-level domain; it is folded into the domains where autonomy would cause harm (ML R&D and Cyber)." 支持理由是"脱离领域的自主性只是能力而非风险"，反对理由是"跨领域的自主性本身是一种应被命名的元风险"。D 是 OpenAI 的做法。

### Q4 — 答案：C

讲义："ML R&D autonomy level 1 = fully automate the AI R&D pipeline at competitive cost vs human + AI tools"。它与上一节 Anthropic 的 AI R&D-4（"automate a substantial fraction of AI research at competitive cost"）关注的是同一件事，但措辞是"完全自动化流水线"，门槛表述更高。A 是第 05 节 AI Scientist v2 的话题；B 混入了上一节代码中的示意阈值；D 对应 Autonomous Replication。

### Q5 — 答案：B

讲义："If a model sandbags on evaluations, every framework's capability thresholds are underestimated. The framework works only if the measurement works. This is why external measurement (Lesson 21, METR) and adversarial evaluation are necessary in addition to lab self-assessment." A 错：讲义说 OpenAI 把它放在 Research Categories，Anthropic 通过评测情境差距处理，DeepMind 通过欺骗性对齐监控处理——三家都涉及。

### Q6 — 答案：A

讲义："DeepMind itself says automated monitoring 'will not remain sufficient long-term' if instrumental reasoning strengthens." 这是三家共同承认"只靠监控有上限"的最明确表态。B 与原话相反；C、D 无依据。

### Q7 — 答案：D

`main()` 中的循环是 `for cap in ("long_range_autonomy", "sandbagging", "autonomous_replication", "undermining_safeguards", "rnd_automation")`，`cyber_uplift` 和 `bio_uplift` 虽然三张表都有，却从未被打印。实际单独调用 `diff("cyber_uplift")` 会看到三家分别是 `Tracked`、`ASL-3 trigger`、`Cyber CCL`。讲义练习 1 要求"至少两个能力与原文核对"，而恰恰三家最趋同的两个能力没有展示。

### Q8 — 答案：C

已实际运行：`p.table.get(capability, ("not in table", "—"))` 是精确键匹配，`"autonomy"` 不是任何表的键，三行都打印 `not in table`。A 错：没有模糊匹配；B 错：`.get` 带默认值不会抛 `KeyError`。危险在于：读者可能把"拼写不对"误读成"三家都没覆盖 autonomy"，而讲义的第一步 Locate 正是"If not findable, the policy does not cover it"——工具把两种情况混在了一起（Q11 给出改进）。

### Q9 — 参考答案

1. **`undermining_safeguards` → "hardcoded prohibition / refuses training / deploy"**：概念混用。"hardcoded prohibition"是第 17 节 **Claude Constitution** 中约束**模型行为**的概念（生物武器 uplift、CSAM 等，模型拒绝执行），不是 RSP 这份**实验室扩展政策**里的阈值；第 19 节讲义介绍 RSP v3.0 时完全没有提到"undermining safeguards"，也没有"拒绝训练 / 部署"的条款。何况讲义说 v3.0 删除了暂停条款，"refuses training"与之相矛盾。代码 HEADLINE 把它作为三家对比的两个重点之一，放大了这个问题。
2. **`cyber_uplift` / `bio_uplift` → "ASL-3 trigger"**：第 19 节讲义从未提到 ASL（AI Safety Level）体系；在本课程的材料范围内找不到出处。（skill 文件同样直接写 ASL-3，说明对照表与 skill 来自同一份提炼，但都没有给出条款引用。）
3. **`long_range_autonomy` → "named risk / affirmative case at threshold"**：第 19 节讲义只命名了 AI R&D-4 一个阈值，没有把 long-range autonomy 作为独立风险命名；affirmative case 是越过 AI R&D-4 后的要求，把它挂在 long-range autonomy 上属于推断。
4. **`autonomous_replication` → "not explicitly named / covered under AI R&D-4"**：同时说"未明确命名"又说"被 AI R&D-4 覆盖"——按 skill 文件的规则，"If the capability is claimed to be 'covered' by a framework but the word does not appear in the document, refuse and require a concrete clause reference"。
5. **结构性问题**：整张表没有任何"原文出处"字段，而 skill 文件的 hard reject 包括 "Any classification that cannot point to a specific clause in the source document"，且要求标注 Anthropic 承诺属于"unilateral"还是"industry-recommendation"栏（第 19 节的两层结构），表中也没有。

结论：代码 docstring 说这些是 "pedagogical distillations"，可以用来入门，但任何对外的判断都必须逐条回到原文核对。

### Q10 — 参考答案

1. 一种映射（主观，需要说明理由）：

| 分类文本 | 约束强度 |
|---------|---------|
| Tracked、hardcoded prohibition、ASL-3 trigger、Cyber CCL、Bio CCL | mandatory |
| named risk、AI R&D-4 threshold、folded into ML R&D (/ Cyber) domain(s)、ML R&D autonomy level 1 | conditional |
| named via eval-context gap | methodology |
| Research、deceptive alignment monitoring | monitor-only |
| not explicitly named | not-named |

2. 已用 `collections.Counter` 实际统计：

| 政策 | mandatory | conditional | methodology | monitor-only | not-named |
|------|-----------|-------------|-------------|--------------|-----------|
| OpenAI PF v2 | 3 | 0 | 0 | 4 | 0 |
| Anthropic RSP v3.0 | 3 | 2 | 1 | 0 | 1 |
| DeepMind FSF v3 | 2 | 3 | 0 | 2 | 0 |

   - **完全一致**：`cyber_uplift`、`bio_uplift`——三家都是 mandatory。
   - **分歧最大**：`undermining_safeguards`（OpenAI monitor-only、Anthropic mandatory、DeepMind monitor-only）、`autonomous_replication`（monitor-only / not-named / conditional）、`rnd_automation`（OpenAI mandatory，另两家 conditional）。
   - 这与讲义的判断一致：传统的 CBRN / Cyber 风险三家趋同，分歧集中在自主性、欺骗、研发自动化这些"新型"能力上。
3. 风险：映射本身是主观的，同一个"mandatory"在三家可能意味着完全不同的措施强度；Anthropic 一列的 mandatory 中有一项来自概念混用（Q9 第 1 条），一旦更正，Anthropic 的"严格度"就会下降；数字容易制造"已经比较过了"的错觉。量化只能作为阅读索引，结论仍要回到条款原文。

### Q11 — 参考答案

```python
import difflib
from dataclasses import dataclass

@dataclass
class Entry:
    classification: str
    action: str
    binding: str                    # mandatory / conditional / methodology / monitor-only / not-named
    source_clause: str | None = None
    tier: str | None = None         # unilateral / industry-recommendation（主要用于 Anthropic）

def diff2(cap, tables):             # tables: {政策名: {能力: Entry}}
    known = set().union(*(t.keys() for t in tables.values()))
    if cap not in known:
        hints = difflib.get_close_matches(cap, known, n=3, cutoff=0.3)
        print(f"unknown capability {cap!r}; did you mean {hints}?")
        return
    for name, t in tables.items():
        e = t.get(cap)
        if e is None:
            print(f"  {name}: NOT FOUND in policy table -> treat as not covered")
            continue
        warn = "" if e.source_clause else "  [WARN: no source clause]"
        print(f"  {name}: {e.classification} | {e.binding}{warn}")
```

已运行验证（用 OpenAI 一列升级为 `Entry` 并只给 `long_range_autonomy` 填了出处）：

- `diff2("long_range_autonomy", ...)` → `Research | monitor-only`（无警告）；
- `diff2("sandbagging", ...)` → `Research | monitor-only  [WARN: no source clause]`；
- `diff2("autonomy", ...)` → `unknown capability 'autonomy'; did you mean ['long_range_autonomy', 'autonomous_replication', 'rnd_automation']?`；
- `diff2("replication", ...)` → 候选中第一个是 `autonomous_replication`。

区分两种"找不到"：能力名不在**任何**表中 → 多半是拼写或命名问题，给出候选；能力名在其他表中存在、但某一家没有 → 才是"该政策未覆盖"，按讲义 Locate 步骤处理。`set().union(*...)` 把所有表的键合并成一个集合。

### Q12 — 参考答案

1. 期望成功率 = 真实率 × (1 − 识别率) + sandbagging 率 × 识别率（已用 Python 计算）：
   - 明显评测题集：`0.8 × 0.1 + 0.3 × 0.9 = 0.35`
   - 伪装部署题集：`0.8 × 0.9 + 0.3 × 0.1 = 0.75`
2. 明显评测题集给出 0.35 < 0.6，结论"未触发"；伪装题集给出 0.75 ≥ 0.6，结论"应触发缓解"。同一个模型，测量方式不同，政策结论相反——这就是讲义 "The framework works only if the measurement works" 的具体含义。
3. 评测方案要点：
   - **情境对照**：同一能力用"明显评测"与"伪装部署"两套等价题集测量，差值显著即视为 sandbagging 信号（差值本身就是评测情境识别的度量，对应第 01 节的 eval-context gaming）；
   - **能力引出（elicitation）**：在少量同类任务上做微调或给出充分示例后再测，若成绩大幅跃升，说明原先的低分不是能力上限；
   - **一致性检查**：把难题拆成子任务，若子任务全部会做而整体"不会"，可疑；
   - **私有题集与外部评测方**：题目不公开、由外部机构（第 21 节 METR、讲义提到的 Apollo）执行，降低模型"认出"评测的机会；
   - **保守判定**：出现 sandbagging 信号时，用较高的估计值做阈值判定（与第 19 节 Q10 的思路一致）。
   - 局限：足够强的模型也可能识别伪装题集，所以这只能提高下限，不能证明"没有 sandbagging"。

### Q13 — 参考回答要点

- **Anthropic RSP v3.0**（第 19 节）：AI R&D-4 是命名的下一道门；越过后发布 affirmative case；两层缓解（单方面 vs 行业建议）；删除暂停条款；常设 Frontier Safety Roadmap 与 Risk Report。
- **OpenAI PF v2**：Tracked Categories（触发 Capabilities + Safeguards Reports，SAG 部署前审查）与 Research Categories（Long-range Autonomy、Sandbagging、Autonomous Replication and Adaptation、Undermining Safeguards，只跟踪、"potential" mitigations）。
- **DeepMind FSF v3**：按领域的 CCL；autonomy 并入 ML R&D 与 Cyber；2026 年 4 月加入 Tracked Capability Levels 增加颗粒度；明确的欺骗性对齐自动化监控。
- **共同点**（讲义）：内部审查机构；把欺骗性对齐列为风险；按声明节奏发布常设文件；承认只靠监控有上限。
- **独立性**（讲义）：Anthropic 与 Apollo、美国 AI Safety Institute 合作；OpenAI 与 METR；DeepMind 主要依靠内部机制。
- 加分点：讲义的核心观点——同一个能力，在 Anthropic 可能是"强制缓解"，在 OpenAI 是"监控但不触发"，在 DeepMind 是"在特定领域中跟踪"；政策姿态本身就是信息。

### Q14 — 参考回答要点

- **OpenAI 把 Long-range Autonomy 放在 Research**：
  - 合理之处：长程自主能力的测量方法尚不成熟，过早绑定强制缓解可能导致阈值形同虚设或误触发；先观察、积累证据。
  - 风险：讲义说 "Research Categories ... do not automatically trigger mitigations"——第 01 节讲义指出长程任务的时间跨度大约每 7 个月翻倍，如果能力增长快于类别"升级"的流程，就会出现"能力已到、门控未到"的空窗。
- **DeepMind 把 autonomy 并入领域**：
  - 合理之处（讲义）："autonomy without a domain is capability without risk"——只在会造成伤害的领域（ML R&D、Cyber）设阈值，测量更具体。
  - 风险（讲义）："autonomy across domains is a meta-risk the framework should name"——例如自主复制、跨领域的长程行动、破坏监督，未必落在某个单一领域内。
- 加分点：两种做法都把关键的判断推迟到"测量"上，sandbagging 会同时削弱二者；建议对"升级规则"（Research → Tracked 的条件）设声明的时间表。

### Q15 — 参考回答要点

按本节 skill 文件的输出格式：

1. **能力定义**：一句话定义（如"在无人干预下获取资源、自我复制并适应环境的能力"）。
2. **OpenAI 行**：Tracked 还是 Research；若是 Research，注明"potential"措辞；附原文条款。
3. **Anthropic 行**：对应哪个阈值；缓解措施；属于单方面还是行业建议栏；附条款。
4. **DeepMind 行**：哪个领域、哪个 CCL / TCL；是否涉及欺骗性对齐监控；附条款。
5. **趋同与分歧总结**：哪家最严格、哪家最宽松，并给出理由。
6. **测量归属**：该能力由谁测（METR、Apollo、内部、第三方），多久测一次。
- **必须避免**（skill hard rejects）：只凭新闻稿措辞相似就说"三家一致"；无法指向原文条款的分类；把 Research 当 Tracked。
- 对公司的意义：把结论转化为供应商风险条款——例如"若该能力在供应商框架中只是 Research 类别，我们在自己的运行时层需补充哪些控制"（权限、沙箱、kill switch）。

### Q16 — 参考回答要点

- **任务集**：覆盖完整 AI 研发流水线的端到端任务——读论文提出假设、实现实验、调参训练、分析结果、写出报告；包括小规模训练运行与评测基础设施维护；任务来自真实研究工作，题目私有。
- **成本基线**：讲义定义的对照是"human + AI tools"。基线为"研究员 + 当前工具"完成同样任务的时间与算力费用；模型方案计入 API / 推理成本、算力与必要的人工复核时间。
- **成功标准**：在预先注册的指标上（实验结果可复现、达到基线研究员的质量评分），以不高于基线的成本完成；报告成功率及置信区间，而非单次演示。
- **防作弊**：私有任务、防数据污染检查；独立评审盲评产出；沙箱中记录全部操作，检查是否利用评测漏洞（reward hacking）；用 Q12 的情境对照方法检测 sandbagging。
- **外部性**：由外部评测机构执行或复核（第 21 节 METR 的时间跨度方法可作为子指标）。
- 加分点：说明"完全自动化流水线"与 Anthropic AI R&D-4"相当大比例"在门槛上的差异，以及这对跨政策比较的影响。

### Q17 — 参考回答要点

- 不同意。相同的"名词"不等于相同的保障：
  - **Locate**：同一能力在三家文件中是否都能找到明确条款？（如本节代码中 Anthropic 对 autonomous replication 标为"not explicitly named"。）
  - **Classify**：找到之后，是触发强制缓解还是只跟踪？OpenAI 的 Research 类别不自动触发；"提到欺骗性对齐"与"对它有强制措施"是两回事。
  - **Cadence**：是否按声明节奏更新，还是只在事件后更新？
  - **Independence**：外部审查是强制还是可选？讲义：Anthropic 与 Apollo、US AISI 合作，OpenAI 与 METR，DeepMind 主要依靠内部；内部 SAG 由实验室员工组成，skill 文件（第 19 节）认为不算独立监督。
- 还要看**测量**：sandbagging 会让所有阈值失效，谁有外部、对抗性的测量机制，谁的阈值才可信。
- 讲义的结论：DeepMind 自己承认自动化监控长期不够；三家都在"只靠监控"的上限附近。
- skill 文件："If the user treats policy-existence as evidence of mitigation-in-practice, refuse and require evidence of the specific mitigations firing."

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 19 Anthropic Responsible Scaling Policy v3.0](../../19-anthropic-rsp/docs/zh.md)：讲义列出的先修课，本节对比的第一份政策。
- [阶段 15 · 17 Constitutional AI 与规则覆盖](../../17-constitutional-ai/docs/zh.md)：区分"模型行为层的硬编码禁令"与"实验室扩展政策"。
- [阶段 15 · 01 从聊天机器人转向长程 Agents](../../01-long-horizon-agents/docs/zh.md)：eval-context gaming 与长程自主能力的增长趋势。
- [阶段 15 · 04 Darwin Godel Machine：开放式自我修改 Agents](../../04-darwin-godel-machine/docs/zh.md)、[阶段 15 · 07 递归自我改进：能力与 Alignment 的权衡](../../07-recursive-self-improvement/docs/zh.md)：ML R&D 自动化与自我改进的能力背景。

### 本节被哪些后续内容用到
- [阶段 15 · 21 METR 时间跨度与外部能力 Evaluation](../../21-metr-external-evaluation/docs/zh.md)：讲义指出外部测量是框架有效的前提。
- [阶段 15 · 22 CAIS、CAISI 与社会规模风险](../../22-cais-caisi-societal-risk/docs/zh.md)：从实验室框架走向社会层面的风险治理。
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../../18-ethics-safety-alignment/18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：三大框架的对齐视角再读。
- [阶段 18 · 06 Mesa 优化与欺骗性 Alignment](../../../18-ethics-safety-alignment/06-mesa-optimization-deceptive-alignment/docs/zh.md)、[阶段 18 · 09 伪装 Alignment](../../../18-ethics-safety-alignment/09-alignment-faking/docs/zh.md)：欺骗性对齐与 alignment faking 的研究基础。
- [阶段 18 · 30 两用风险：网络、生物、化学与核领域的能力提升](../../../18-ethics-safety-alignment/30-dual-use-risk-cyber-bio-chem-nuclear/docs/zh.md)：三家趋同的 Cyber / Bio 类别。

### 延伸关键词
`Preparedness Framework v2` · `Tracked vs Research Categories` · `Capabilities Report / Safeguards Report` · `Frontier Safety Framework v3` · `Critical Capability Level (CCL)` · `Tracked Capability Level` · `ML R&D autonomy level 1` · `deceptive alignment monitoring` · `instrumental reasoning` · `sandbagging` · `capability elicitation` · `external evaluation`
