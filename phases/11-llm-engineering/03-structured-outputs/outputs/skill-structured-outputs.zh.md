---
name: skill-structured-outputs
description: Decision framework for choosing the right structured output strategy based on provider, reliability, and complexity
version: 1.0.0
phase: 11
lesson: 03
tags: [structured-output, json, schema, constrained-decoding, pydantic, function-calling]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="structured-output-strategy"></a>

# Structured Output Strategy

当建造一个 LLM 需要结构化数据的应用程序,应用本决定框架。

<a id="when-to-use-each-approach"></a>

## 何时使用每种方法

**Prompt- 以“返回”为基础 JSON"):** 仅用于原型。 对于内部工具, 偶尔分析失败是允许的。 添加试/ 除重试外 。 生产管道中永远不要使用 。

**JSON 模式 (API 旗帜 :** 您需要保证有效 JSON 但图案是简单或灵活的。 当您验证了应用程序侧面的形状时, 工作有效 。 可用 : OpenAI, Anthropic (通过工具使用),谷歌。

**Schema 模式( 限制解码) :** 生产系统,其中每个输出必须匹配特定的图案。 零分析失败。 零系统违规。 默认情况下, 用于任何生产提取或分类任务 。 可用 : OpenAI structured outputs,大纲,指导。

**Function calling / 工具使用 :** 模型需要选择要调用哪个函数,而不是只填充 parameters。您有多个图案,模型则选择合适的图案。在与现有工具/功能基础设施整合时,也可以使用。

**教官库 :** 您想要在任何提供者之间自动重试的 Pydantic 验证。 Python 项目。 OpenAI, Anthropic谷歌和开放源码模型。

<a id="provider-specific-guidance"></a>

## 专门针对提供者的指导

**OpenAI:** 使用 `response_format` 与 `json_schema` 类型。 设置了封闭解码。 Pydantic 模型直接工作。 最可靠的 structured output 执行。

**Anthropic:** 使用工具用于 structured output。定义一个带有所希望的图案的工具。模型返回 tool call 参数与公式匹配。可靠但需要工具使用 API 模式。

**开放源码模型(vLLM奥拉马:** 使用大纲或指南进行约束解码。 这些库会汇编 JSON 将隐藏无效的限定状态机器配置成图案 tokens 生成中。需要运行 inference 当地。

<a id="schema-design-guidelines"></a>

## 计划设计准则

1. 尽可能保持平面。 超过 2 层的嵌入对象会增加提取错误 。
2. 对绝对字段使用 enums。 不要依赖模型来创建正确的字符串 。
3. 以明确的无效支持而不是选择性的方式设定所需的模糊字段。 强制模式做出决定 。
4. 将描述添加到 Schema 属性中。 模型读作指令 。
5. 避免工会类型(其中/任何类型),除非有必要。它们增加了解码的复杂性。
6. 设定数字的最低/最大值。 捕捉到幻觉的极端值 。
7. 使用数组上的微小项目/最大项目来防止空或无约束输出。

<a id="common-failure-patterns-and-fixes"></a>

## 常见故障模式和补救

- **模式环绕 JSON 在 markdown fences**: 从 prompt- 基点到 JSON 模式或模式模式
- **计划有效,但实际上是错误的**:增加一个 LLM- 提取后作为判决的验证步骤
- **不一致的隐含值**: 切换到限制解码或添加后处理 normalization
- **缺少可选字段**:在应用程序代码中要求或添加默认值
- **非常缓慢的提取**: 受限解码增加了5-15%的延迟度,如果对延迟感敏感,则会降低机率复杂性
- **具有不同项目的大型阵列**:按下输入并提取每整块,然后合并结果

<a id="reliability-ladder"></a>

## 可靠性阶梯

| 方法 | 分析成功 | 方案匹配 | 设置任务 |
|----------|-------------|-------------|-------------|
| Prompt- 基础 | ~90% | ~80% | 1分钟 |
| JSON mode | 100% | ~90% | 5分钟 |
| 计划模式 | 100% | ~99% | 15分钟 |
| 受限解码 | 100% | 100% | 30分钟 |
| 教官 + 重试 | 100% | ~99.5% | 10分钟 |
