<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="ab-testing-llm-features--growthbook-statsig-and-the-vibes-problem"></a>

# 对 LLM Features 进行 A/B 测试：GrowthBook、Statsig 与凭感觉判断的问题

> 传统的A/B测试不是为非确定性而建立的 LLMs。关键区别是: 评估回答“ 模型能做得到吗?” A/B测试回答“ 用户是否关心?” 两者都是必需的; 发送感应检查已经结束。 2026年要测试什么: prompt engineering 选择模型(措辞)GPT-4对4 GPT-3.5相对于开放源码软件;准确度相对于成本相对于延迟度),生成 parameters (temperature真实案例:聊天机奖赏模型提供了+70%的谈话长度和+30%的保留; 下门AI主题线实验在奖励功能完善后提供了+1% CTR; Khan Academy Khanmigo在悬浮-vs-math-curity轴上进行了循环。 平台分割 : **Statsig** (由 OpenAI 2025年9月为1.1B)——连续测试,CUPED,全对齐。 **GrowthBook** 开源、仓库-本地、贝耶斯+常客+序列引擎、CUPED、SRM检查、Benjami-Hochberg+Bonferroni校正。SQL 以及是否 "通过 OpenAI" 与贵组织有关。

**类型:** 学习
**语言:** Python (stdlib, 玩具连续测试模拟器)
**先修要求:** 阶段17 · 13 (Observability阶段17 20(逐步部署)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 区分 A/B 测试(“ 用户护理”) 的 Evals (“ 模型能胜任工作 ” )。
- 列出三个可测试轴( A)prompt, 模型, parameters并选择每个指标。
- 解释 CUPED、 连续测试, 和 Benjani-Hochberg 多重比较校正 。
- 以仓库为基础选择 Statsig 或 EscapeBook --SQL 姿态和公司收购立场。

<a id="the-problem"></a>

## 问题

你手调 system prompt。 它感觉更好。 你发送它。 转换变化由噪音。 你责怪标准。 或者你发送了一个新的模型,但转换没有移动—— 模型是否退化了, 变化太小, 无法检测? 你不知道, 因为你没有A/B, 运输时没有A/B。

Evals 回答模型是否可在标签集上执行任务。 他们不回答用户是否喜欢输出。 只有受控的在线实验才能回答, 并且只有在实验有足够的能量、 控制非确定性以及纠正多重比较的情况下回答 。

<a id="the-concept"></a>

## 概念

<a id="evals-vs-ab-tests"></a>

### Evals 与 A/B 测试

**Evals** 下线、标签、评断(鲁布或 LLM回答:"这个固定分布的输出是否正确/有用/安全?

**A/B 测试** 在线用户, 现场用户, 随机。 回答 : “ 新变量移动用户级的衡量标准重要吗 ? ”

两者都需要。 Evals在接触前会发生捕获回归;A/B在接触后确认产品影响。

<a id="what-to-test"></a>

### 试什么

1. **Prompt engineering** ——措辞,系统——prompt 计量:任务成功、用户保留、费用/要求。
2. **模式选择** — GPT-4对4 GPT-3.5 -图尔博对立 Llama计量:准确度(任务)+费用/要求+长期性P99。
3. **Generation parameters** — temperature,顶 -p,顶_符号。 计量: 特定任务( 产出多样性与确定性) 。

<a id="cuped--variance-reduction"></a>

### 中央应急反应系统——减少差异

使用实验前数据进行控制实验。 在比较后期之前, 递减前期差异。 典型的差异减少: 30- 70%。 有效的样本大小会免费上升 。

执行:执行《统计手册》和《增长手册》。

<a id="sequential-testing"></a>

### 序列测试

经典 A/ B 假设固定的样本大小。 序列测试(“ peek- and- dedecide ” ) 控制反复外观下的假正率。 总是有效的连续程序( MSPRT, Howard的自信序列) 允许您在明显胜出者中提前停止 。

<a id="multiple-comparison-corrections"></a>

### 多比较更正

以95%的置信率进行20次A/B测试,偶然得出一个假正数。 Bonferroni 校正会收紧一次的α; Benjamini-Hochberg 控制错误发现率。 增长手册执行两种方法 。

<a id="srm--sample-ratio-mismatch"></a>

### SRM - 抽样比率不匹配

分配散列将用户随机排列为变体。 如果50/50分割后产生47/53, 就会有东西被打破—— SRM检查标记, 两个平台都执行 。

<a id="statsig-vs-growthbook"></a>

### 统计与增长书

**Statsig**:
- 由 OpenAI 10月1日至1月1日(2025年9月),东道主SaaS。
- 连续测试,CUPED, 被搁置的人口。
- All-in-one: feature 标记+实验+ observability.
- 最佳条件:团队已经想要一个捆绑的产品,不关心 OpenAI ownership.

**GrowthBook**:
- 开放源码(MIT);仓库-本地(直接读自Snowflake/BigQuery/Redfrew)。
- 多重引擎:贝叶斯、常客、序列
- 中央应急队,SRM,Bonferroni,BH校正。
- 自我主机或管理好的云
- 最合适,仓库SQL 商店,数据组控制公制层, 想要开放源码软件。

<a id="non-determinism-complicates-power"></a>

### 非决定性使权力复杂化

Same prompt 传统功率计算假设了 IID 观测。 LLM 非确定性,有效样本大小低于名义值。将所需的样本大小乘以~1.3-1.5x作为安全比值。

<a id="real-case-outcomes"></a>

### 实际案件结果

- Chatbot reward model 变量:+70% 对话长度,+30% 保留时间。
- 下一门主题行:在奖励功能精细后,+1% CTR。
- 汗学院汉米戈: 迭代性潜伏性 超自然精确交易

<a id="the-anti-pattern-shipping-on-vibes"></a>

### 反模式:随气流运输

每个高级工程师都可以命名 feature 大部分是被退缩的产品测量仪 团队数月没注意到。A/B是强迫功能。

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 由 OpenAI:1.1B,2025年9月。
- 增长手册:开放源码的麻省理工学院;贝叶斯语+常客语+序列。
- 中央化数据差异减少:30-70%。
- LLM +30-50%样本大小缓冲。

```figure
mx-sequential-test
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟带有固定和连续边界的顺序 A/B 测试。显示顺序如何让您提前停止 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-ab-plan.md`。给定 feature 变化,工作量,基线, 选择平台,门,样本大小。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。对于预计5%的升降,加上3%的基线转换,多少样本大小为80%的功率?
2. 选择Statsig或CreatBook 来为受保健管制的孕期客户服务。
3. 设计一个测试的A/B GPT-4对4 GPT-3.5 成本单价单 guardrail 公制,二级?
4. 您的金丝雀经过, 但 A/ B 显示 - 1. 2% 的转换 。 您是否发运? 写入升级标准 。
5. 将 CUPED 应用到预期, 与职位差异的60% 。 计算有效模量的增压 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Eval | "脱机测试" | Labeled-set evaluation 模型能力 |
| A/B 测试 | "experiment" | 用户的实时随机比较 |
| CUPED | "减少差异" | 减少差异的期前回归 |
| 序列测试 | "皮克-OK测试" | 允许提前停止的总是有效的程序 |
| 多重比较 | 家庭错误 | 进行多次测试, 虚报阳性 |
| Bonferroni | "严格校正" | 将α除以试验次数 |
| Benjamini-Hochberg | "BHFDR" (BH FDR) (BH FDR) (BH FDR) (BH FDR) (BH FDR) (BH FDR) (BH FDR) (BH FDR) (BH FDR) (BH FDR) (BH FDR) (BH FDR) (BH FDR) (BY) (BH FDR) (BH FDR) (BH FD(BY) (BY) (BY) (BY) (BY) (BY) (BY) (BY) (BDD(B) (B) (BY) (B) (B) (BDDD(B) (BD) (BD) (B) (BD) (BD(B) (B) (BD) (BDD) (BD) (B) (B) (B) (FD(FD) (B) (B) (美元) (美元) | 错误发现率控制, 保守程度较低 |
| SRM | "差劲的分裂" | 抽样比率不匹配; 任务错误 |
| Statsig | "OpenAI owned" | 2025年获得的商用全对一 |
| GrowthBook | "OSS一号" | MIT 仓库-本地平台 |
| mSPRT | “序列概率比测试” | 经典顺序程序 |

<a id="further-reading"></a>

## 进一步阅读

- [增长书——如何A/B测试AI](https://blog.growthbook.io/how-to-a-b-test-ai-a-practical-guide/)
- [统计—— 超越 Prompts数据驱动器 LLM Optimization](https://www.statsig.com/blog/llm-optimization-online-experimentation)
- [Statsig 与增长手册比较](https://www.statsig.com/perspectives/ab-testing-feature-flags-comparison-tools)
- [Deng等人—— 中央应急警察](https://www.exp-platform.com/Documents/2013-02-CUPED-ImprovingSensitivityOfControlledExperiments.pdf)
- [霍华德-信心序列](https://arxiv.org/abs/1810.08240)
