---
name: skill-cot-patterns
description: Decision framework for choosing the right reasoning technique based on task complexity, accuracy requirements, and cost constraints
version: 1.0.0
phase: 11
lesson: 02
tags: [chain-of-thought, few-shot, self-consistency, tree-of-thought, react, reasoning, prompting]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="reasoning-technique-selection-guide"></a>

# 说明技术选择指南

当你需要一个 LLM 来解释一个问题,在写 prompt。该技术决定了推理结构。 prompt 填满它。

<a id="quick-decision-tree"></a>

## 快速决策树

1. 任务是一个简单的事实调查还是一个步骤分类?
   - 是: 使用 **zero-shot**. CoT 增加成本,但没有准确收益。
   - 号继续。

2. 任务是否需要多步推理(逻辑、逻辑、逻辑) planning)?
   - 是: 使用 **Chain-of-Thought**继续第三步。
   - 否: 使用 **few-shot** 如果格式很重要, zero-shot 如果它没有。

3. 单一推理错误是否可以接受?
   - 是: 使用 **few-shot CoT** (单一样本, temperature 0.0).
   - 否: 使用 **self-consistency** (N=5) 国家 temperature 继续第四步。

4. 问题是搜索/planning 有很多可能的路径有问题?
   - 是: 使用 **Tree-of-Thought**.
   - 否:自我一致性就足够了。

5. 任务是否需要外部信息或计算?
   - 是: 使用 **ReAct** (理由+ tool calls).
   - 否:纯粹的推理技术就足够了。

<a id="technique-matrix"></a>

## 技术矩阵

| 技术 | 准确性提升 | 成本乘数 | 延迟 | 最适合 |
|-----------|--------------|-----------------|---------|----------|
| Zero-shot | 基线 | 1个x | ~1 个 | 简单任务,事实 |
| Few-shot | +5-15% | 1.2x | ~1 个 | 格式匹配、 分类 |
| Zero-shot CoT | +10-20% | 1.3x (单位:千美元) | ~1.5s | 快速推理促进 |
| Few-shot CoT | +15-25% | 1.5x | ~2岁 | 数学、逻辑、多步 |
| 自我维持(N=5) | +2%-5%高于计算机 | 5个 | ~5岁 | 高考推论 |
| 自我维持(N=10) | N=5+1%-2% | 10个 | 〜10秒 | 仅限关键决定 |
| Tree-of-Thought | Task-dependent | 10-40x 目标 | ~30岁+ | 搜身 搜身 搜身 搜身 planning拼图 |
| ReAct | Task-dependent | 3-10x 3-10x | ~5-15岁 | 知识型任务 |
| Prompt Chaining | 单身加5-10% | 2-5x 级 | ~5-10岁 | 复杂的多部分任务 |

<a id="model-specific-guidance"></a>

## 示范性具体指导

<a id="gpt-4o--gpt-41"></a>

### GPT- 4o / - 4o - 4o - 4o GPT-4.1
- 强有力的基线推理。 Zero-shot 电磁脉冲往往足够。
- Few-shot 高科技3个例子在GSM8K上占95%。
- 自我一致性带来边际收益(95%至97%) -- -- 只值得用于关键任务。
- Supports structured outputs 原本是用来解答的

<a id="claude-35-sonnet--claude-37-sonnet"></a>

### Claude 3.5 索内特/ Claude 3.7 索内特
- 精于结构化 prompt 格式(XML (标记)
- Few-shot CoT 与 XML- 有限的例子最有效。
- 扩展思维( E)Claude 3.7)是原生COT -- -- 没有必要 prompt 为了它。
- 自我一致性是有效的,因为 Claude推理的差别很大 temperature 0.7.

<a id="llama-3133-70b"></a>

### Llama 3.1.3.3 70B号
- 大部分好处来自: few-shot COT( 更大的准确度差距与% ) zero-shot).
- 建议用于推理任务的N=5的自理性。
- 需要比商业模型更明确的格式指示。
- 本地的陶艺很贵 inference - 仅考虑批量处理。

<a id="gemini-25-pro"></a>

### Gemini 2.5 专业
- 坚持多步推理出盒子
- 思维模式提供内置 CoT , 不带 prompt engineering.
- Few-shot 示例有助于格式的一致性,而不是准确性。
- 大 context window (1M) 使示例重 few-shot 实际。

<a id="anti-patterns"></a>

## 反模式

**简单任务的 CoT**:问“2+2是什么?让我们一步一步想”废物 tokens。模型获得简单的算术正确而没有推理 traces。如果有3+级,计算机辅助功能会有所帮助。

**自我一致性 temperature 0.0**:所有 N 样本都将相同。您必须使用 temperature 大于0(建议为0.5-0.8),可选择不同的推理途径。

**什么都用ToT**: ToT 需要 O(b^d) LLM 调用 b = 键盘因子和 d = 深度。 树上 b= 3, d= 3 需要最多 39 个调用。 预留使用较便宜技术失败的问题 。

**Few-shot 有坏的例子**:推理错误的例子教模型如何做出这些错误。每个例子都必须被校验。一个错误的例子可以降低精确度超过零的例子。

**解开没有统一格式的答案**: 自 己性需要比较各样样本的答案。 如果回答格式不同( $18, $18, $8) , 投票失败 。 总是执行 : “ 答案是 [number]."

<a id="cost-optimization"></a>

## 费用优化

生产系统每天处理10,000次查询 GPT- 4o 定价(250/1M投入,10/1M产出):

| 技术 | Avg Tokens/查询 | 每日费用 | 准确度 |
|-----------|-----------------|------------|----------|
| Zero-shot | ~200 | ~$5 | 78% |
| Few-shot CoT | ~600 | ~$15 | 95% |
| 自我维持(N=5) | ~3,000 | ~$75 | 97% |
| 托尔特(b=3,d=2) | ~6,000 | ~$150 | Task-dependent |

多数应用的成本最佳战略:从 few-shot COT. 仅在信任度低的查询中添加自定性( 构建它一节中的升级模式)。

<a id="integration-with-prompt-chaining"></a>

## 与 Prompt Chaining

理性技术构成 prompt 链条 :

**链条步骤1** (摘录): zero-shot, temperature 0.0
**链条步骤2** (原因): few-shot 科特,我们... temperature 0.0
**链条步骤3** (核查):与N=3的自我一致性; temperature 0.7

这三步链的成本是~3x 一次COT调用,但捕捉提取错误、推理错误,并提供了从核查步骤中得出的信任分数。

<a id="when-to-move-beyond-prompting"></a>

## 何时移动超越提示

如果你花更多的时间 工程 prompts 与写入应用程序代码相比,考虑:

1. **Fine-tuning**:如果您有500多个标签示例,且任务范围狭窄
2. **DSPy 汇编**:如果您想要自动 prompt optimization
3. **Agent frameworks**:如果任务需要多方向工具使用(第14阶段)
4. **RAG**:如果模型需要获得私人/当前知识(课程06-07)

激励技术是基础。 它们与任何模型、任何提供者一起工作,不需要训练数据。 但是它们有限度。 了解何时毕业与掌握技术本身一样重要。
