<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="automated-alignment-research-anthropic-aar"></a>

# 自动化 Alignment 研究（Anthropic AAR）

> Anthropic 运行平行团队 Claude 行动4.6 自主 Alignment 独立研究者 sandboxes,通过一个共同论坛进行协调,其日志在任何 sandbox (so agents 研究者们在培训上表现优于人类研究人员。 Anthropic要求工作流程的自定义摘要标记往往限制 AAR 灵活性和降低性能。 alignment 研究是压缩时间轴的压缩步骤 以精确的错配风险 RSP是用来检测。

**类型:** 学习
**语言:** Python (stdlib, 平行研究论坛模拟器)
**先修要求:** 阶段15 -05(AI科学家诉2),阶段15 -04(DGM)
**时间:** ~60分钟

<a id="the-problem"></a>

## 问题

Alignment 研究在人类研究时间上成本很高。 诸如可扩展的监督、奖励规格或弱力至强力的培训等问题需要每迭代几周的实验。 随着前沿能力的提高,这些实验需要时间。 alignment 工作量的增长快于合格研究人员的供应。

Automated Alignment 研究(AAR)询问是否与能力超出的同一前沿模型 alignment 有助于缩小差距。 Anthropic2026年关于AAR运行的弱至强训练研究的报告(AAR-Offering-Offer-struction-research)alignment.anthropic.com/2026/a自动W2s-researcher/)是这一类中已部署的系统最早产生的公开结果之一。

结果确实具有积极意义:AARs比人类基线更好地解决了研究问题,结果也集中在一个单一系统中,每一个关注的阶段都已经发展。 alignment 研究可以自动化,而损害保障措施的部分也可以自动进行。 研究支助方案对AI研发能力的阈值是用这一循环来写成的。

<a id="the-concept"></a>

## 概念

<a id="the-architecture-as-publicly-described"></a>

### 建筑(如公开描述)

- **Parallel agents.** Multiple Claude 以AARs为例运行的Opus 4.6实例,每个案例均在独立情况下运行 sandbox. Sandboxes 限制文件系统、网络和进程表面。
- **共同论坛。** 调查结果公布于一个共同论坛,其储存后端位于每个 sandbox. Agents 能够阅读论坛; agents 无法从自己的论坛记录中删除或编辑 sandbox.
- **任务分配。** 人类设计的任务队列将研究问题分配给 AARs。 AARs提出分解、运行实验、撰写研究结果。
- **训练重点薄弱** 研究报告涉及的是薄弱至强的培训——利用较弱的主管模式来培训更强大的学生模式,AARs在这项任务上比人类研究人员表现得好。

<a id="why-the-out-of-sandbox-log-matters"></a>

### 为什么是出...sandbox 日志事项

日志完整性属性是受控实验和潜在失密实验之间的差别。 如果 AARs 可以编辑自己的日志, 它们可以掩盖失败或可疑的实验。 Anthropic 直接标出:财产是信任研究成果的必要条件,而核实并非三重条件。

基础设施术语的模拟是仅附加日志,通过外部存储进行写入(例如,S3对象锁定,不可更改的数据犬日志)。 agent 与2026年公司安保小组用来进行防赎金软件审计线索的相同模式。

<a id="the-prescribed-workflow-tradeoff"></a>

### 规定的工作流程权衡

Anthropic报告指出,规定的工作流程往往限制AAR的灵活性和降低性能。换句话说:如果人类设计者逐步编写研究计划,AARs所做的比给它设定的高级目标和分解自由还要糟糕。这与整个研究计划的结果是一致的。 agentic 研究(第4条)LangGraph微软 Agent 框架)——超标的脚手架受伤能力 agents.

安全隐含的含义是微妙的。 提高 AAR 性能的灵活性也是允许未经批准分解、新工具使用和目标驱动的灵活性。 权衡是一个设计空间决定:灵活性在多大程度上足以战胜人类,而不交出 agent 是否有空间将目标非分布化?

<a id="the-compression-risk"></a>

### 压缩风险

RSP v3.0 (Lesson 19) 引入了AI研发能力阈值:以竞争性成本与人+AI工具完全自动化AI研发管道的能力。 DeepMind的FSF v3 包含类似的ML研发自主级别。 这两个框架都将这一阈值视为触发高水平控制的因素。

AAR是距离门槛的一步:它使管道的一部分自动化(AAR)。alignment 时间问题在于差距的缩小速度。

压缩时间表是造成问题复发的问题。 alignment 研究和能力研究化合物的速率相似,与能力相比,失调风险表面至少增长得和能力一样快。如果能力复合更快(历史趋势),差距就会扩大。 alignment 只有在研究过程可信的情况下,结果才会缩小差距。

<a id="what-aar-does-not-replace"></a>

### AAR不能取代的东西

人类研究者设置了任务排队、审查结果并维护了宪法权威。 AARs加速了管道的中间,而不是目的。 Anthropic出版的产出包括:AAR的贡献和人类研究者对出版内容、收回内容和完善内容的判断。

这符合提议...commit 15课中用于研究本身的模式:AARs提议;人类 commit.

```figure
aar-forum
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟多AAR研究论坛。 agents"平行运行, 将调查结果张贴到一个只附件的论坛 带有选择性的篡改企图。

Watch:

- 怎么会...sandbox 伐木作业尝试。
- 任务分配如果能自由分解,如何在困难问题上实现固定工作流程。
- 如果日志不明显篡改的话 单一的AAR会如何污染论坛的信号

<a id="ship-it"></a>

## 交付成果

`outputs/skill-aar-deployment-review.md` 是一个自动-alignment- 研究管道。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。比较“固定工作流”与“自由分解”设置。自由分解总是赢的,还是有固定工作流程具有竞争力的问题类别?

2. 将模拟器修改为 1 agent 尝试对日志进行篡改。 确认只使用附件的日志可以检测它。 写一个段落, 描述在日志中检测的签名的准确性 。

3. Read Anthropic确定AARs击败人类研究人员的具体子任务。是什么使得它可以自动化?

4. 设计任务排分配政策,平衡AAR灵活性(更好的结果)与规定的工作流程限制(更方便的审计),描述您将如何测试 A/B 。

5. 读 RSP v3. 0 的 AI 研发 - 4 阈值。 在一段中, 请描述您认为 AAR 目前没有的跨度 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| AAR | "Automated Alignment Researcher" | Claude 自动运行的4.6例 alignment problems |
| 训练能力薄弱 | 训练一个更强的模型 和较弱的主管 | AARs的成绩超过了人类 |
| 共同论坛 | "Where agents 发表调查结果” | 仅附加, 退出( O)sandbox storage |
| Out-of-sandbox log | "Agent 无法编辑自己的记录” | 向外部存储发送明显写入 |
| 规定的工作流程 | 人类设计师的一步步计划 | AAR 限制; 经常降低性能和自由分解 |
| 自由分解 | "Agent 如何打破任务" | 更有能力,更难审计 |
| AI 研发阈值 | “RSP/FSF能力水平” | 以竞争性成本实现研发管道的完全自动化 |
| 压缩时间表 | "Alignment 与能力竞赛 | 如果能力化合物的化合物快于 alignment,不匹配的风险增加 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic 自动弱至强研究者](https://alignment.anthropic.com/2026/automated-w2s-researcher/) - 原始来源。
- [Anthropic 负责任的缩放政策 v3.0](https://anthropic.com/responsible-scaling-policy/rsp-v3-0) AI研发门槛框架。
- [Anthropic 衡量大赦国际 agent autonomy](https://www.anthropic.com/research/measuring-agent-autonomy) - 范围更广 agent- 自主设计
- [深界边界安全框架 v3](https://deepmind.google/blog/strengthening-our-frontier-safety-framework/) 与研究与开发方案平行的ML研发自主水平。
- [Burns等人(2023年)。 弱至强(通用)OpenAI)](https://openai.com/index/weak-to-strong-generalization/) AARs攻击的根本性问题。
