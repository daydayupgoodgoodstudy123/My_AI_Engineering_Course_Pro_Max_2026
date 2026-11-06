<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="frontier-safety-frameworks--rsp-pf-fsf"></a>

# 前沿安全框架：RSP、PF、FSF

> 三个主要实验室框架确定了2026年边界能力的工业治理。 Anthropic 负责任的扩大政策 v3.0 (2026年2月) 引入了分层的AI安全级别(ASL-1至ASL-5+),以生物安全级别为模型,2025年5月启动与化学、生物、辐射和核有关的模型的ASL-3。 OpenAI 准备框架 v2 (2025年4月)界定了跟踪能力的五项标准,并将能力报告与保障报告分开。 DeepMind边界安全框架 v3.0 (2025年9月)引入关键能力水平,包括新的有害操纵CCL。 所有三个框架现在都包含竞争者调整条款,允许在无可比保障的同级实验室船舶上推迟。 alignment 仍然具有结构性,而非术语性:“能力阈值”、“高能力阈值”和“关键能力水平”表示类似的概念。

**类型：** 了解
**语言:** 无
**先修要求:** 阶段18 17 阶段18 07-09(欺骗性故障)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- Describe AnthropicASL 级结构及激活 ASL-3 的部件 。
- 说五 OpenAI 跟踪能力准备框架 v2 标准。
- 描述深明公司的关键能力级别结构和有害操纵CCL。
- 解释一下竞争者调整条款 以及它们为什么对种族动态很重要
- 界定安全案例,说明三支柱结构(监测、不易辨认、能力不强)。

<a id="the-problem"></a>

## 问题

经验教训7-17确定,欺骗是可能的,存在双重用途能力,以及 evaluation 实验室具有边际能力,需要内部治理结构:
- 界定何时需要新的保障措施的门槛。
- 定义 evaluations 缩放前
- 描述安全箱的外观
- 处理种族动力问题(如果竞争者没有保障,你做什么? )

2025-2026年的三个框架是最新技术——不完善、不断演变和足够协调的实验室,治理问题是这些框架是否充分,而不是是否存在。

<a id="the-concept"></a>

## 概念

<a id="anthropic-responsible-scaling-policy-v30-february-2026"></a>

### Anthropic 负责任的扩大政策 v3.0 (2026年2月)

ASL 结构 :
- ASL-1:不是前沿模型(由较弱基线所抵消)。
- ASL-2:现有边界基线;部署时有常规保障。
- ASL-3:灾难性滥用的风险大得多;与化学、生物、辐射或核有关的能力。
- ASL-4:AI研发2号跨越阈值;能够使入门一级AI研究自动化的模型。
- ASL-5+:先进的AI研发模型,大大加快了有效推广的速度。

新建于 v3. 0 :
- 边境安全路线图(以编辑形式公开)。
- 风险报告(每季度,有些是外部审查)。
- AI研发活动分为AI研发2和AI研发4。
- 一旦AI研发-4研究被跨越,就需要肯定的安全案例,查明追求目标不匹配模型的不匹配风险。

<a id="openai-preparedness-framework-v2-april-15-2025"></a>

### OpenAI 准备框架 v2 (2025年4月15日)

跟踪能力的五项标准:
- **Plausible.** Reasonable threat model exists.
- **Measurable.** Empirical evaluation possible.
- **Severe.** 伤害很大
- **Net-new.** 风险不是先有的
- **Instantaneous-or-irremediable.** 伤害发生得很快,或者无法挽回。

与所有五个人相遇的能力都得到跟踪,其他的则不是。

其他PF v2结构:
- 独立能力报告(模式可以做什么)和保障报告(现有控制)。
- 安全咨询小组审查。
- 领导权批准;理事会的安全和安保委员会监督。
- "调整条款": OpenAI 如果另一艘没有类似保障的实验船可能减少要求。

<a id="deepmind-frontier-safety-framework-v30-september-2025"></a>

### 深明边界安全框架 v3.0 (2025年9月)

按域分列的关键能力水平(CCLs):
- 提升生物武器
- 网络提升
- ML 研发加速
- 有害操纵(新版为3.0):在高接触度情况下,可大大改变信仰/行为的模式。

v2.0 (2025年2月) 添加了一个欺骗 Alignment 高安全级别,ML研发CCL

<a id="cross-lab-alignment"></a>

### Cross-lab alignment

- Anthropic "能力门槛"
- 深沉"关键能力水平。
- OpenAI "高能力门槛"

结构上一致:有3级边界能力,已公布 evaluation 所有这三项条款都包括竞争者调整条款(2025年以后)。

<a id="safety-cases"></a>

### 安全案件

安全案例是书面论点,即根据最坏假设部署是可以接受的安全。

- **Monitoring.** 发生坏事时我们能侦测到吗?
- **Illegibility.** 该模式是否缺乏执行一致计划以造成损害的能力?
- **Incapability.** 该模型是否缺乏造成有关伤害的能力?

不同的安全案例针对不同的柱子。 对于ASL-3 CBRN 案例,能力(通过学习)是主要目标。 alignment监控和不易识别是目标,对于网络提升来说,这三者都具有相关性。

<a id="the-race-dynamic-problem"></a>

### 种族动力问题

竞争调整条款是有争议的。 Critics 维权者认为,如果三个实验室都降低了竞争对手缺陷时的要求,那么平衡就会转向叛逃。 如果叛逃实验室不那么安全,则替代(单边保障)的结果会更糟。

英国国际审计学会、美国国际审计学会和欧盟国际审计学会办公室(Lesson 24)是外部治理的对口单位。 实验室框架是自愿的;监管框架正在形成。

<a id="where-this-fits-in-phase-18"></a>

### 18阶段适合的地方

17-18号课程是欺骗和红色小组分析的衡量和治理层面。 19-24号课程涉及福利、偏见、隐私、水印和监管结构。 evaluations.

```figure
al-asl-ladder
```

<a id="use-it"></a>

## 实际应用

没有此课的代码。 读取三个主要来源: RSP v3. 0, PF v2, FSF v3. 0。 将每个实验室的层次结构映射到其它位置, 并指定每个实验室的一个阈值, 其它实验室则定义不 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-framework-diff.md`以安全框架或发布说明为参照,比较了框架的阈值定义, evaluations 安全情况结构,针对RSP v3.0、PF v2. FSF v3.0和横幅标杆空白。

<a id="exercises"></a>

## 练习

1. 阅读 RSP v3. 0, PF v2, 和 FSF v3. 0。 汇编每个实验室的 CBRN 阈值、 每个实验室的 AI 研发阈值以及每个实验室需要的部署前 evaluation.

2. 竞争者调整条款在所有三个框架中(2025+)都有。 写一个段落来论证它;写一个段落来反对它。 确定每个职位取决于的假设。

3. 为模型过境设计一个安全箱 AnthropicAI 研发-4 临界值。 请列出三个支柱( 监测、 不可识别、 无法识别) 所需的证据 。

4. DeepMind的FSF v3.0 引入了有害操纵CCL。 提议三项实验性测量, 表明模型已经越过了这个门槛 。

5. 阅读METR的“边界安全政策的共同要素”(2025年),列出三个最强的交叉实验室趋同和两个最大的差异。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| RSP | "Anthropic框架 | 负责任的缩放政策; ASL 级; v3.0 2026年2月 |
| PF | "OpenAI框架 | 准备框架;五项标准;v2 2025年4月 |
| FSF | "深明的架构" | 边境安全框架;CCLs;v3.0 2025年9月 |
| ASL-3 | "生物安全3级分析" | Anthropic 与化学、生物、辐射和核相关能力的级;2025年5月启用 |
| CCL | "关键能力水平" | 深明值的阈值构造; 每域 |
| 安全案件 | "正式辩论" | 书面论点,认为在最坏的情况下部署是可以接受的安全性 |
| 调整条款 | "竞争者叛逃津贴" | 如果竞争对手没有可比保障的船舶减少要求的框架规定 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic - 负责任的扩大政策3.0 (2026年2月)](https://www.anthropic.com/responsible-scaling-policy) ASL级、路线图、AI研发分类
- [OpenAI - 更新准备框架(2025年4月15日)](https://openai.com/index/updating-our-preparedness-framework/) - 五项标准,调整条款
- [深思——加强我们的边境安全框架(2025年9月)](https://deepmind.google/blog/strengthening-our-frontier-safety-framework/) - CCL v3.0,有害操纵
- [METR - 边界安全政策的共同要素(2025年)](https://metr.org/blog/2025-03-26-common-elements-of-frontier-ai-safety-policies/) 跨实验室比较
