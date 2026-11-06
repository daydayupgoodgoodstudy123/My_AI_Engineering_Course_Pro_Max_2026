<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="anthropic-responsible-scaling-policy-v30"></a>

# Anthropic Responsible Scaling Policy v3.0（负责任扩展政策）

> RSP v3.0 于2026年2月24日生效,取代了2023年的政策。 Anthropic 将单方面对一个整个行业的建议(包括RAND SL-4安全标准)进行比较。添加边界安全路线图和风险报告作为长期文件,而不是一次性交付。 Anthropic 必须公布肯定的案例,查明不匹配的风险和缓解措施。 Claude 欧普斯4.6没有越过它。 Anthropic 声明在 v3. 0 公告中说“ 明确排除这一点正变得困难。 ” Anthropic 与RSP类相邻的“弱” OpenAI 质量阈值取代了2023年的数量承诺;删除暂停条款是最明显的倒退。

**类型：** 了解
**语言:** Python (stdlib, RSP 阈值决定引擎)
**先修要求:** 阶段15 · 06(AAR),阶段15 · 07(RSI)
**时间：** ~45分钟

<a id="the-problem"></a>

## 问题

边境实验室公布比例化政策,部分是技术文件,部分是治理文件,部分是向监管者发出信号。 Anthropic 文档。阅读它并不重要,因为遵守它不是约束性的(它不是约束性的),而是因为设计图塑造了实验室如何设想灾难性风险以及它们如何向公众传达权衡利益。

V3.0 vs v2.0 diff 是有用的单位。 添加的内容是: 边境安全路线图、 风险报告、 AI 研发4 阈值。 取消的内容是 2023 暂停承诺。 重新设定的内容是: 二级缓解计划分为两个部分 Anthropic外部审查——SecureAI——将分数从2.2(v2)降至1.9(v3.0)。 这就是如何在看得更光滑的同时,使比例政策变得不那么严格。

<a id="the-concept"></a>

## 概念

<a id="the-two-tier-mitigation-schedule"></a>

### 二级缓解时间表

- **Anthropic 单方面行动**: 什麽? Anthropic 训练将停止超过门槛, 具体的安全措施,具体的部署大门。
- **全行业建议**: 什麽? Anthropic 包括RAND SL-4安全标准。 Anthropic一方面;它们是政策倡导。

双层结构不是在 v2 中, 这意味着读者需要查看每个承诺的值。 “ 全行业建议”栏中的安全措施不是 Anthropic承诺;这是 Anthropic充满希望

<a id="the-ai-rd-4-threshold"></a>

### AI 研发-4 阈值

这是能力水平RSP v3.0 名称作为下一个重要门槛。 具体而言:一个可以以竞争性成本使大量AI研究自动化的模式。 Anthropic 认为模型会跨越它,它们必须公布肯定的案例,在继续扩大之前查明不匹配的风险和缓解。

Claude opus 4.6 并不在 v3. 0 公告中横跨它。 文件补充道 : “ 明确排除这一点正变得困难。 ” 这句话很重要; 它承认门槛已经接近到可以成为现实的关注,而不是投机性的极限。

课程6(自动 Alignment 研究)和课程7(自我稳定改善)直接纳入这一门槛。 alignment 研究人员跨过研究质量栏目,证明AI研发-4临界值正在接近。

<a id="frontier-safety-roadmaps-and-risk-reports"></a>

### 边界安全路线图和风险报告

v3.0 将两种文物提升为常备文件:

- **边界安全路线图**:前瞻性文件,介绍计划的安全工作、能力预期和减缓研究。
- **风险报告**:关于释放后具体模型的回顾文件,说明观察到的能力和残余风险。

两者都是公开的。两者都以所宣布的音节更新。 工具是: 读者可以追踪到什么 Anthropic 说,它们将在路线图中比照风险报告中的报告。

<a id="removing-the-pause-clause"></a>

### 删除暂停条款

2023年的RSP包括一项明确的暂停承诺:如果模型超越具体能力阈值,培训将暂停,直到实施减缓措施。 v3.0以较软的表述方式取代明确暂停(公布肯定情况,如果缓解措施足够的话,则继续)。

政策观点认为,2023年的量化阈值是无法达到的,因为2026年时期的能力基准本身被重新标定。 反论:一个比例化政策的暂停条款是一个承诺机制;取消它会降低政策的可信度。

<a id="saferais-downgrade"></a>

### 安全情报处降级

社会安全协会是一个独立组织,对以RSP为型的文件进行评级。 Anthropic RSP得分2.2(在4.0是目前最佳RSP和1.0是名义比例中)。 Anthropic 从中度到弱度,加入 OpenAI 和深思熟虑 在弱类别。

安全分析系统下调系数:
- 质量阈值取代定量阈值。
- 暂停承诺取消 。
- AI研发4的临界值减缓被描述为“肯定案例”,而不是具体措施。
- 审查机制取决于 Anthropic安全咨询小组,独立监督有限

<a id="what-this-lesson-is-not"></a>

### 这课不是

这不是遵守规则的教训。 Anthropic 其教训在于用它应有的特殊性和怀疑性来阅读文件。 扩大政策是公共信号前沿的主要实验室,它揭示出灾难性风险的态势。 读好它们对于任何依靠边际能力工作的人来说都是一种实用的技能。

```figure
a5-rsp-ladder
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 执行一个小型决策引擎,反映RSP的门槛值 --evaluation 形状: 给定候选模型和一套能力测量, 返回是否跨过 AI 研发-4 阈值, 所需的肯定部分, 以及部署是否可以进行。 这是有意的简单; 关键是让文档的逻辑清晰化 。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-scaling-policy-review.md` 审评比例政策(Anthropic, OpenAI,DeepMind,或内部)相对于 v3.0 参考:双层结构、阈值、暂停承诺、独立审查。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`三个合成模型在不同能力级别上提供食物。确认临界值评价员的行为符合预期,并制作正确的肯定型样板。

2. 全文阅读 RSP v3.0 (32页) 。 确定“ 全行业建议” 层中的每一项承诺。 其中哪些承诺会是 ”Anthropic 单方"在V2?

3. 读一下 SEGEAI 的 RSP 分级方法。 将批量的1. 9 分重新加到 v3. 0 分, 将其标注应用到文档中。 哪个列的标数导致降级最多?

4. 2023年暂停承诺被取消,提议替代承诺,以维护政策的信誉,同时承认2026年的基准调整问题。

5. 比较 RSP v3. 0 到 OpenAI 准备框架 v2( lesson 20) 。 选择一个3. 0 较强的区域 。 选择一个更强的准备框架区域 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| RSP | "Anthropic缩放政策 | 负责任的比例化政策;v3.0,2026年2月24日生效 |
| AI 研发-4 | "研究-调整阈值" | 以竞争性成本实现大量人工智能研究自动化的能力 |
| 肯定案件 | 安全的理由 | 已公布的关于查明风险和适当减轻风险的论点 |
| 边界安全路线图 | 前进计划 | 关于计划的安全工作和预期能力的长期文件 |
| 风险报告 | "对模型的反省" | 关于观察到的能力和释放后残余风险的常设文件 |
| 两级缓解 | "单边对产业" | Anthropic 与行业建议相比, |
| 暂停承诺 | "2023年条款" | 明确承诺暂停培训;在 v3. 0 中删除 |
| 更安全国际的评级 | 独立性RSP等级 | 第三方标注; v3.0 得分 1.9 (v2为2.2) |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic - 负责任的扩大政策 v3.0](https://anthropic.com/responsible-scaling-policy/rsp-v3-0) -32页的整条政策
- [Anthropic - RSP v3.0 通知](https://www.anthropic.com/news/responsible-scaling-policy-v3) - v2的变动摘要。
- [Anthropic - 边界安全路线图](https://www.anthropic.com/responsible-scaling-policy/roadmap) - 与RSP v3.0链接的常设文件。
- [Anthropic 风险报告:2026年2月](https://www.anthropic.com/feb-2026-risk-report) ——回顾 Claude 版面4.6, 出版时的边际模式。
- [Anthropic 计量 agent 实际的自主权](https://www.anthropic.com/research/measuring-agent-autonomy) 将AI研发4与衡量的自主性联系起来。
