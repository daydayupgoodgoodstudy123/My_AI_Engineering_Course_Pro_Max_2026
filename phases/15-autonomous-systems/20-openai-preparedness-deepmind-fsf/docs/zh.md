<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="openai-preparedness-framework-and-deepmind-frontier-safety-framework"></a>

# OpenAI Preparedness Framework 与 DeepMind Frontier Safety Framework

> OpenAI 准备框架v2(2025年4月)引入了研究类别——远程自主、沙渣、自动复制和适应、爆破保障——不同于跟踪类别。跟踪类别触发能力报告加上安全咨询小组审查的保障报告。DeepMind的FSF v3(2025年9月,加上跟踪能力水平,又增加了4月17日,2026年4月17日)将自主性折合到ML研发和网络域(ML研发自主一级=以竞争性成本与人类+AI工具完全自动化AI研发管道)。 alignment 使用自动监控工具的滥用。 诚实的注释: PF v2 中的研究类别(包括远程自主)不会自动触发缓解;政策语言是“ 潜在 ” 。 DeepMind 自己说, 如果工具推理得到加强, 自动监控“ 将无法保持足够的长期性 ” 。

**类型:** 学习
**语言:** Python (stdlib, 三个框架决定表 diff 工具)
**先修要求:** 阶段15 · 19 (Anthropic RSP)
**时间:** ~45分钟

<a id="the-problem"></a>

## 问题

第19课改为 Anthropic正在仔细调整政策。 此课通过阅读完成图片 OpenAI三份文件是表兄弟的手工艺品,涉及同样的问题——边疆实验室何时暂停或关上模型——它们集中在少数类别上,在特定地点有分歧。

趋同:所有这三个国家都把远程自主称为值得跟踪的能力类别。 这三个国家都承认欺骗行为( ) 。alignment 三个都有内部审查机构。 OpenAI 将分类分为“ 跟踪” (强制减缓) 和“ 研究” (无自动触发)。 深最小将自主性折叠成两个域, 而不是单独命名。 实验室名称追踪到 Research 和 security 和 Moderate , 或者 Tier-1 和 Tier-2 ; 操作结果是各实验室不同的, 功能所在的桶里有不同功能 。

将两者结合起来阅读是有用的。 Anthropic,"监测但不会触发" OpenAI政策态势很重要

<a id="the-concept"></a>

## 概念

<a id="openai-preparedness-framework-v2-april-2025"></a>

### OpenAI 准备框架 v2 (2025年4月)

Structure:

- **跟踪分类**:触发能力报告(模式可以做什么)加上保障报告(已有哪些缓解措施)。
- **研究类别**:实验室正在跟踪但尚未承诺进行特定减缓的模型能力。包括远程自主、沙堆、自动复制和适应、破坏保障。

键框 v2: 研究类别不会自动触发减缓。 政策语言是“ 潜在” 缓解。 这是要查看的具体三角洲 : 追踪与研究中的分类位置是“ 标记” 和“ 观察” 之间的连接点 。

<a id="deepmind-frontier-safety-framework-v3-september-2025-tracked-capability-levels-added-april-17-2026"></a>

### 深明边界安全框架 v3 (2025年9月;跟踪能力水平增加)

Structure:

- **关键能力水平**:五个领域的能力阈值:网络、生物、ML研发、CBRN、自主(已并入ML研发和网络)。
- **跟踪能力级别**具体例子:ML研发自主水平1=以竞争性成本与人类+AI工具相比完全自动化AI研发管道。
- **Deceptive alignment monitoring**:明确承诺自动监测滥用工具的理由。

自主框架与 OpenAI。 DeepMind 不保留“ 自主” 作为顶级域名; 它被折叠到自发性会造成损害的领域( ML 研发和网络 ) 。 理由是没有域名的自主就是无风险的能力; 反论是跨域的自主性是框架应该命名的元风险。

<a id="what-all-three-converge-on"></a>

### 三个人都聚集在一起

- 内部安全咨询小组(名称) Anthropic SAG, OpenAI 高级咨询小组,深明内部委员会)在部署高能力模型之前进行审查。
- 明确提及欺骗 alignment / alignment 假装是风险等级
- 宣布的音带上的立体文物(Anthropic边界安全路线图,风险报告; OpenAI能力与保障报告;DeepMind:FSF更新周期)。
- 承认只受监控的防御系统有上限。深明很清楚地说:“自动监控将无法保持足够的长期监控。”

<a id="where-they-diverge"></a>

### 在那里,他们分歧,

- **Anthropic**:在 v3.0 中删除暂停承诺; AI 研发-4 阈值是命名的下一个关口 。
- **OpenAI**:跟踪与研究的分割;研究类别(包括远程自主)不自动进入门。
- **DeepMind**: 自动叠叠到其它域; 跟踪能力级别在2026年4月增加了颗粒。

<a id="sandbagging-a-specific-capability-that-complicates-all-three"></a>

### 沙滩:使所有三个问题复杂化的具体能力

沙滩(一种战略表现不佳的模式) evaluations)是 OpenAI研究类别。 AnthropicRSP v3. 0 地址为 evaluation- 文字空白(课程1),深思熟虑通过欺骗性解决它 alignment 金融监督局第3卷。

如果一个模型沙袋 evaluations,每个框架的能力阈值都被低估。只有当测量工作奏效时,该框架才会发挥作用。这就是外部测量(Lesson 21,METR)和对称性测量(emptyal 21,METR)的原因所在。 evaluation 除了实验室自我评估之外,还需要进行这种评估。

<a id="the-policy-reading-skill"></a>

### 政策阅读技能

- 定位: 您所关心的每一个能力都应该在政策中找到。 如果找不到, 政策将不覆盖它 。
- 分类:是跟踪(触发减缓)还是研究(跟踪但不触发)? OpenAI 命名此; Anthropic 深明有他们自己的同类。
- 考登斯:政策是否在宣布的时间表上更新,还是只在具体事件发生后更新?
- 独立性:外部审查是强制性还是任择性的? Anthropic 与阿波罗和美国AI安全研究所合作; OpenAI 与METR; 与内部SAG进行深度定位。

```figure
a5-tracked-vs-research
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 使用一个小的、可决策的 diff 工具。 alignment,研发自动化,网络提升等等,它输出出三种政策如何将能力分类,以及什么可以触发缓解。这是一个阅读辅助工具,而不是一个政策工具。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-cross-policy-diff.md` 利用这三个框架作为参考,为具体能力进行跨政策比较。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。确认 diff 工具的输出符合至少两个功能的保单,您可以根据源文件进行验证。

2. Read OpenAI 准备框架 v2 完整。 确定每个研究类别。 对于每一个类别, 请写一个句子, 说明为什么它被放在研究中而不是跟踪 。

3. 全文读取 DeepMind FSF v3, 加上2026年4月的跟踪能力级别更新。 确定 ML 研发自主级别 1 的具体级别 evaluation 标准。 您如何测量它外部 ?

4. 沙滩上 OpenAI研究类别。 evaluation 参考第一课的关于电子交流的讨论。

5. 比较关于特定能力的三种政策( 您的选择)。 名称您认为最严格的和最不严格的政策分类。 与源文本说明理由 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| 准备框架 | "OpenAI缩放政策 | PF v2 (2025年4月);跟踪与研究类别 |
| 跟踪分类 | “强制缓解” | 触发能力+保障报告;SAG审查 |
| 研究类别 | "只监测" | 跟踪但没有自动减缓;包括远程自动 |
| 边境安全框架 | "深视政策" | FSF v3(2025年9月)+跟踪能力水平(2026年4月) |
| CCL | "关键能力水平" | 每域深最小值阈值( 网络、 生物、 ML 研发、 CBRN) |
| ML 研发一级自主 | "研发自动化" | 以竞争性成本完全自动化AI研发管道 |
| Sandbagging | 战略表现不佳 | 模型在评估上表现不佳; OpenAI 研究类别 |
| 工具推理 | "中途推理" | 关于如何实现目标的理由; " 深点 " 监测的目标 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI - 更新我们的准备框架](https://openai.com/index/updating-our-preparedness-framework/) - V2宣布。
- [OpenAI 准备框架 v2 PDF](https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf) - 完整文件。
- [深思——加强我们的边界安全框架](https://deepmind.google/blog/strengthening-our-frontier-safety-framework/) - 家庭支助基金3号通知。
- [深明——更新边境安全框架(2026年4月)](https://deepmind.google/blog/updating-the-frontier-safety-framework/) 跟踪能力水平增加。
- [Gemini 3份Pro FSF报告](https://storage.googleapis.com/deepmind-media/gemini/gemini_3_pro_fsf_report.pdf) 金融稳定框架风险报告的例子。
