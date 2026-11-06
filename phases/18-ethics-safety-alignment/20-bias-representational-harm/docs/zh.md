<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="bias-and-representational-harm-in-llms"></a>

# LLMs 中的偏见与表征性伤害

> 加列戈斯、罗西、巴罗、坦吉姆、金、德农科特、优、张、艾哈迈德(2024年口头语言:2309.00770)。 evaluation 计量为 embedding2024-2025年经验:An等人(PNAS Nexus,2025年3月)测量交叉性别x种族偏见 GPT-3.5 涡轮 GPT-4o, Gemini 1.5 Flash灯, Claude 3.5 索纳特, Llama 3-70B 自动回执 evaluation 共度(COLM 2025,arXiv:2508.07111)引入基于不确定性的公平性 evaluation 2025年 Yu & Ananiadou 识别了多功能性免疫缺陷综合征的性别神经元; Ahsan & Wallace 2025年使用 SAE 来揭示临床种族偏见; Zhou 等人 2024年( UniBias) 操作 attention 10年的文献过分强调二进制性别偏见。

**类型:** Build
**语言:** Python (斯迪利布,玩具) embedding- 以偏差探测为基础的)
**先修要求:** 第05阶段(字词) embeddings阶段 18 -01 (instruction following)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 界定代表与分配的伤害,并在一个或一个以上 LLM deployment.
- 三个名字 evaluation- Gallegos等人(2024年)的计量类别,并描述每个类别的一个计量。
- 描述交叉性,以及为什么基于不确定性的公正度衡量方法解决单一轴偏差问题 evaluation.
- 描述两种机械解释偏见的方法(性别神经元,SAE) features, attention- 头部操纵)

<a id="the-problem"></a>

## 问题

以往的经验教训包括故意伤害(第2条)。jailbreaks偏见是无意的损害——从训练数据传播、从 prompt 衡量和减少这种影响是对抗性强势的一个明显的方法挑战。

<a id="the-concept"></a>

## 概念

<a id="representational-vs-allocational"></a>

### 代表与分配

- **代表伤害。** 定型观念、抹杀、贬低形象。 LLM 护士们被描述为 完全女性 正在造成表情上的伤害
- **分配伤害** 不平等的物质结果。 LLM 黑申请人的简历被系统降低 造成了分配上的伤害

这两种观点不同。 一种模式可以“代表的公正性” (产生不同的描述),而“分配上的偏向性” (提出不平等的建议 ) 。 Evaluations 需要衡量两者。

<a id="three-evaluation-metric-categories-gallegos-et-al-2024"></a>

### Three evaluation- 计量类别(Gallegos等人,2024年)

- **Embedding-based.** 之前的WEAT型测试RLHF embeddings限制:衡量代表性,而不是行为。
- **Probability-based.** 与陈规定型的否定和破坏陈规定型的完成相比,在逻辑上似乎很像。 Decoder- 侧边测量,有行为偏差
- **Generated-text-based.** 生成文本的下游任务测量。 恢复比对、 建议写作、 对话框。 多数生态上有效; 最难复制 。

<a id="intersectionality"></a>

### Intersectionality

Bias evaluation An等人,2025年发现 GPT-4o 黑人妇女恢复得分的比黑人男子和白人妇女分别得分多。 evaluation 无法捕捉到这个 。

双点识别(COLM 2025)引入了基于不确定性的交叉公平性。 它衡量模型对结果的不确定性是否在交叉身份图示之间有所不同 — — 不仅仅是点预测。 这抓住了模型在群体之间同样错误但对某些群体更不确定的案例,这产生了不同的下游分配行为。

<a id="mechanistic-approaches"></a>

### 机械学方法

2024-2025年的可解释性工作为机械干预带来了偏见:

- **性别神经元(Yu和Ananiadou,2025年)。** 特定微粒子神经元与性别特定行为相关,这些神经元的消化降低了能力成本有限的性别比例。
- **通过SAEs的临床种族偏见(Ahsan和Wallace 2025年)。** 粗略自动编码器 features 将内部代表性分解为可解释的层面;与种族相关 features 能够识别和抑制。
- **Unibias案(周等人,2024年)。** Attention- 头部操纵 zero-shot 贬低。 特定头会增强身份类的敏感性; 零或重排这些头会减少偏向, 没有 fine-tuning.

<a id="the-meta-critique"></a>

### 元正统

10年文献审查(arXiv:2508.11067,2025)发现该领域过分注重二元性别偏见。 attention707. 元论认为,忽视会损害边缘化群体:对二元性别有严重偏差的模型可能在无人检查的层面产生严重偏差。

<a id="where-this-fits-in-phase-18"></a>

### 18阶段适合的地方

20-21课正式涉及偏见和公平问题,22课涉及隐私问题,23课涉及水印问题,这是补充先前欺骗/安全层的用户伤害层。

```figure
an-bias-two-harms
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 制造一个玩具 embedding- 基于偏差的探测:测量身份术语和属性术语之间的WEAT型距离,以简单共发 embedding。您可以输入偏差并观察度量火灾;进行简单的贬损操作并观察部分恢复情况。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-bias-eval.md`。如果有的话 model card 或公平索赔,审计 evaluation 三个指标类别(embedding、概率、生成文本、交叉性覆盖以及任何贬低性干预的机制。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。报告WEAT型偏差在贬低步骤前后的得分。解释为什么衡量标准没有下降到零。

2. 扩展探测器, 进行交叉测试:( 性别、 种族) x ( 职业、 家庭) 。 报告交叉轴偏差分数 。

3. 阅读 An 等人,2025年(PNAS Nexus)。 evaluation 就会错过

4. 尤 & Ananiadou 2025 识别性别神经元。 涂抹一个伪造的实验, 将“ 这些神经元导致性别偏向” 与“ 这些神经元与性别偏向相关 ” 区分开来。

5. 元精度认为,这个字段过于狭隘地关注二进制性别。选择一个研究不足的轴,描述一个代表伤害测量程序。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 代表伤害 | "陈规定型/删除" | 偏见描绘一个团体 |
| 分配损害 | "不平等的决定" | 集团的不利物质结果 |
| WEAT | "该 embedding test" | Word Embedding 协会测试;基于共同发生的偏差探测 |
| Intersectionality | “合并身份效应” | 多重身份轴交叉处出现的偏见 |
| 性别神经元 | "MLP偏向神经元" | 与性别特定行为相关的具体神经元 |
| SAE feature | "可解释的维度" | Sparse-autoencoder-identified feature; 可用于机械偏差分析 |
| UniBias | "attention- 头部贬低" | Zero-shot 以重磅方式贬低 attention heads |

<a id="further-reading"></a>

## 进一步阅读

- [Gallegos等人—— 公平与公正 LLMs调查(arXiv:2309.00770,计算语言学2024)](https://arxiv.org/abs/2309.00770) 谷歌调查
- [An等人——跨部门续会evaluation 性别偏差(PNAS Nexus,2025年3月)](https://academic.oup.com/pnasnexus/article/4/3/pgaf089/8111343) - 5个模型的交叉研究
- [共鸣——基于不确定性的交叉公平(arXiv:2508.07111,COLM 2025)](https://arxiv.org/abs/2508.07111) 新的基准
- [联合- attention- 头部操纵(周等人,2024年,ACL)](https://arxiv.org/abs/2405.20612) — zero-shot debiasing
