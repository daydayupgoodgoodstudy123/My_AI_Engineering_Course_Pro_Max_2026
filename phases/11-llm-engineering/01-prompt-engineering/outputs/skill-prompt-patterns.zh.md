---
name: skill-prompt-patterns
description: Decision framework for choosing the right prompt pattern based on task type, reliability requirements, and target model
version: 1.0.0
phase: 11
lesson: 01
tags: [prompt-engineering, patterns, llm, temperature, cross-model, few-shot, chain-of-thought]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="prompt-pattern-selection-guide"></a>

# Prompt 模式选择指南

当建造一个 LLM- 动力 feature,选择 prompt 在写入 prompt。图案决定结构,内容填充它。

<a id="pattern-decision-matrix"></a>

## 模式决定矩阵

| 任务类型 | 小学模式 | 二级图案 | Temperature | Few-Shot 需要吗? |
|-----------|----------------|-------------------|-------------|-----------------|
| 数据提取 | 模板填充 | Few-Shot | 0.0 | 有(2-3例) |
| 分类 | Few-Shot | Guardrail | 0.0 | 有(3-5个实例) |
| 总结 | 个人+模板 | 观众适应 | 0.3 | 否 |
| 代码生成 | Persona | Chain-of-Thought | 0.0 | 可选 |
| 创意写作 | Persona | Critique | 0.7-1.0 | 否 |
| 多步骤推理 | Chain-of-Thought | Decomposition | 0.3 | 可选 |
| 问答 | 人 数a+ Guardrail | Boundary | 0.3 | 否 |
| Prompt generation | Meta-Prompt | Critique | 0.7 | 有(1-2例) |
| 内容中和度 | Guardrail +边界 | Few-Shot | 0.0 | 有(5+例) |
| 笔译/改编 | 观众适应 | Few-Shot | 0.3 | 有(2-3例) |

<a id="when-to-use-each-pattern"></a>

## 何时使用每个模式

**个人图案**: 用于每个 prompt 唯一的问题是如何具体确定这一作用。 对于通用任务,一个广泛的角色就足够了。对于特定领域的任务,该角色应该指明域、资历和背景。

**Few-Shot Pattern**:当输出格式比内容重要时使用。如果模型需要生成特定 JSON 形状、 CSV 格式或分类标签,示例比指令更有效。缩略图规则:简单格式为2-3个示例,复杂或模糊格式为5+。

**Chain-of-Thought Pattern**: 用于数学、逻辑、多步分析以及模型需要“ 显示其工作” 的任何任务。 将推理任务的精确度提高10- 40% (Wei等人, 2022年)。 不要使用简单的事实查找或提取 - 它会浪费 tokens.

**模板填充模式**:用于结构提取,其中每个输出必须具有相同的形状。 temperature= 0.0 和明确的“ N/ A” 处理缺失的字段。

**直观模式**:当质量比速度重要得多时使用。模型生成、批评和改进。大约翻倍 token 成本高,但能大大提高准确性和完整性; 最能取得产出(报告、建议、公开内容)。

**Guardrail Pattern**: 用于任何用户定位系统。 总是包括: 范围界限、 范围外请求的拒绝行为, 以及明确的“ 我不知道” 处理。 与应用程序侧的输入验证合并 。

**Meta-Prompt Pattern**:用于生成 prompts 对新任务进行编辑。 prompt 从头开始,描述任务,让模型写 prompt。然后测试和循环。在初始时节省时间 prompt 发展。

**分解模式**:用于从分裂和征服中受益的复杂问题。模型将问题分成几个部分,解决每个部分,并合并。对3-7分问题的任务最为有效。

**观众适应模式**:当同一内容需要为不同的受众服务时使用。明确指定受众 -- -- 不依赖根据上下文推断的模式。

**边界模式**:用于生产系统,而生产系统绝不能回答某些类型的问题。 guardrails 因为它定义了一个硬范围, 含有精确的拒绝信息 。 对于遵守敏感域来说至关重要 。

<a id="cross-model-compatibility"></a>

## 跨模式兼容性

模式按它们如何一贯地运作排列 GPT- 4号 Claude 3.5 索内特, Gemini 1.5 专业,和 Llama 3:

| 图案 | 跨模式一致性 | 注释 |
|---------|------------------------|-------|
| Few-Shot | 非常高 | 在所有模式中很好地传播实例 |
| 模板填充 | 非常高 | 明确的结构没有多少差异的余地 |
| Chain-of-Thought | 高 | 所有主要模型都支持“一步一步思考” |
| Persona | 高 | 各地都有工作,但不同的模式对不同角色的具体程度有反应 |
| Guardrail | 中等 | Claude follows guardrails 最严格的; GPT- 4o 有时在长时间的谈话中漂流 |
| Critique | 中等 | 自我批评的质量因模式不同而有很大差异 |
| Meta-Prompt | 中等 | GPT- 4个和 Claude 产生不同的 prompt styles |
| Boundary | Low-Moderate | 拒绝行为各不相同; 每个模型测试 |

<a id="common-mistakes"></a>

## 常见错误

1. **使用 Chain-of-Thought 为一切**: CoT 添加 tokens 和潜伏。只有在需要理性步骤时才使用它。
2. **太多的制约因素**:超过5-7个制约因素,模型开始减少一些。优先处理3个最重要的因素。
3. **矛盾人a+制约因素**“你是一个创造性的作家”+“永远不要使用隐喻”,使模型混淆不清。
4. **否 temperature specification**:离开 temperature 默认时( 通常是1.0) , 当您需要确定输出时 。
5. **Copy-pasting prompts 跨模型**:总是测试。A prompt 调制 GPT- 4o 可能表现不佳 Claude 反之亦然。
6. **Ignoring system message**把所有的东西都放进 user message 而不是使用 system message 坚持规则。
7. **过分依赖消极制约**: "不要做X,Y,Z,A,B,C"比"不做W"有效。积极的框架给模型一个明确的目标。

<a id="reliability-targets"></a>

## 可靠性目标

| 使用场景 | 模式组合 | 预期准确性 | Token 成本 |
|----------|-------------------|-------------------|------------|
| 生产提取 | 模板+ Few-Shot | 95%+ | 低( 500-1K) |
| 面向用户 Q&A | 人 数a+ Guardrail +边界 | 90%+ | 中型(1-2K) |
| 代码生成 | 人 数a+ Chain-of-Thought | 85%+ | 中型(1-3K) |
| 内容生成 | 人际关系 + critique | 90%+ 质量 | 高(2-4K,双传球) |
| 分类 | Few-Shot + Guardrail | 95%+ | 低(300-800) |
| 复杂分析 | 分解+ Chain-of-Thought | 85%+ | 高(3-5K) |
