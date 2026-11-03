<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="function-calling-deep-dive--openai-anthropic-gemini"></a>

# 深入理解 Function Calling：OpenAI、Anthropic、Gemini

> 三个边境供应商于2024年在同一条工具呼叫圈上聚集,然后就其他所有问题分歧。 OpenAI 使用 `tools` 和 `tool_calls`. Anthropic 使用 `tool_use` 和 `tool_result` blocks. Gemini 使用 `functionDeclarations` 和独特的一模一样的关联。这个教训会分辨三对一, 以便一个供应商的船舶在移植时不会中断。

**类型：** 构建
**语言:** Python (stdlib, 计划翻译)
**先修要求:** 阶段13 · 01(工具界面)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 说明 OpenAI, Anthropic, 和 Gemini 功能调用有效载荷(声明、调用、结果)。
- 对所有三种供应商格式翻译一项工具声明,并预测严格模式的限制将有所不同。
- 使用 `tool_choice` 在每个供应商中,强迫、禁止或自动挑选 tool calls.
- 了解每个提供者的硬限(工具计数、系统深度、参数长度),并在违反限制时显示错误符号。

<a id="the-problem"></a>

## 问题

功能调用请求的形状因提供者而异。 3个具体例子来自2026年的制表堆:

**OpenAI 聊天补全/ 响应 API.** 你过 `tools: [{type: "function", function: {name, description, parameters, strict}}]`模式的反应包含 `choices[0].message.tool_calls: [{id, type: "function", function: {name, arguments}}]` where `arguments` 是一个 JSON 字符串 您必须分析。 严格模式 ()`strict: true`通过限制解码,强制推行计划。

**Anthropic Messages API.** 你过 `tools: [{name, description, input_schema}]`。回复是 `content: [{type: "text"}, {type: "tool_use", id, name, input}]`. `input` 已经解析( 对象, 不是字符串) 。 您以新 `user` 含有 `{type: "tool_result", tool_use_id, content}` block.

**Google Gemini API.** 你过 `tools: [{functionDeclarations: [{name, description, parameters}]}]` (在大赦令下) `functionDeclarations`答复是: `candidates[0].content.parts: [{functionCall: {name, args, id}}]` where `id` 独特于 Gemini 3个,加码为平行呼叫相关。您要回答 `{functionResponse: {name, id, response}}`.

相同的循环。不同的字段名称, 不同的嵌套, 不同的字符串- vs- 对象习惯, 不同的关联机制。 一个写有天气的团队 agent 在 OpenAI 支付两天的港口 Anthropic 和另一个日子 Gemini 只是为了管道

课程中将三种格式统一成一个金字塔工具声明和边缘路径。 LLM gateway.

<a id="the-concept"></a>

## 概念

<a id="the-common-structure"></a>

### 共同结构

每个供应商都需要五样东西:

1. **工具列表 。** 每个工具名、描述和输入图案。
2. **工具选择。** 强制使用特定工具,禁止使用工具,或让模型来决定。
3. **呼叫发射** Structured output 命名工具和参数 。
4. **打电话给ID** 修改对正确调用(平行事项)的回复。
5. **注射结果** 信息或阻断 将结果连接到电话。

<a id="shape-diffs-field-by-field"></a>

### 形状 diffs, 按字段排列

| 方面 | OpenAI | Anthropic | Gemini |
|--------|--------|-----------|--------|
| 声明信封 | `{type: "function", function: {...}}` | `{name, description, input_schema}` | `{functionDeclarations: [{...}]}` |
| 计划字段 | `parameters` | `input_schema` | `parameters` |
| 反应容器 | `tool_calls[]` 显示于助手信息 | `content[]` 类型 `tool_use` | `parts[]` 类型 `functionCall` |
| 参数类型 | stringified JSON | 解析对象 | 解析对象 |
| ID 格式 | `call_...` (OpenAI 生成) | `toolu_...` (Anthropic) | 用户界面( UUID)Gemini 3+) |
| 结果块 | role `tool`, `tool_call_id` | `user` 与 `tool_result`, `tool_use_id` | `functionResponse` 匹配 `id` |
| Force-a-tool | `tool_choice: {type: "function", function: {name}}` | `tool_choice: {type: "tool", name}` | `tool_config: {function_calling_config: {mode: "ANY"}}` |
| 紫外线工具 | `tool_choice: "none"` | `tool_choice: {type: "none"}` | `mode: "NONE"` |
| 严格计划 | `strict: true` | 计划(始终执行) | `responseSchema` 请求级别 |

<a id="limits-you-will-actually-hit"></a>

### 限制你真的会打

- **OpenAI.** 128个工具,每个要求。 Schema 深度 5. 参数字符串  8192 字节。 严格模式不需要 `$ref`, 否 `oneOf`/`anyOf`/`allOf` 与重叠的,所有财产 `required`.
- **Anthropic.** 10 没有严格的模式旗帜; 计划是一种合同,模型往往符合。
- **Gemini.** 要求的64个函数。 Schema 类型为 OpenAPI 3. 0 子集(与 JSON 2020-12年Schema 电话平行通话,自此以后一直保持独特状态。 Gemini 3.

<a id="tool_choice-behavior"></a>

### `tool_choice` behavior

三种模式每个人都支持, 名称不同。

- **Auto.** 模型选择工具或文本。默认 。
- **需要/任何。** 模型必须至少调用一个工具 。
- **无.** 模型不能调用工具。

另加每个提供者独有的模式 :

- **OpenAI.** 按名称强制使用特定工具 。
- **Anthropic.** 按名称强制使用特定工具; `disable_parallel_tool_use` 标记将单对数分开。
- **Gemini.** `mode: "VALIDATED"` 将每一个反应通过一个模型验证器 不论模式意图如何

<a id="parallel-calls"></a>

### 平行电话

OpenAI的 `parallel_tool_calls: true` (默认) 在一个助手信件中发出多个呼叫。 您运行全部并使用每条含有一个条目的批次工具功能信件回复 `tool_call_id`. Anthropic 历史上只打一次电话; `disable_parallel_tool_use: false` (截至 Claude 3.5) 使多个功能能够实现。 Gemini 2个允许平行通话,但没有给出稳定的ID; Gemini 3 添加了异常反应,因此具有清晰关联性。

<a id="streaming"></a>

### Streaming

所有三个支持流 tool calls。电线格式不同:

- **OpenAI.** 三角形块 `tool_calls[i].function.arguments` 逐渐到达,直到 `finish_reason: "tool_calls"`.
- **Anthropic.** 块启动/块- delta / 块- 停止事件 。 `input_json_delta` 块含有部分参数 。
- **Gemini.** `streamFunctionCallArguments` (新加入) Gemini (3) 排放块与 `functionCallId` 如此多个平行电话可以互换

阶段13 03 深入平行+ streaming 重新组装。 这个课程的焦点是声明和单调形状。

<a id="errors-and-repair"></a>

### 错误和修理

无效的参数错误也不同。

- **OpenAI (non-strict).** 模型返回 `arguments: "{bad json}"`, 你的 JSON 分析失败, 您会输入错误信息并重命名 。
- **OpenAI (strict).** 解码时进行验证; 无效 JSON 无法做到,但 `refusal` 可能出现。
- **Anthropic.** `input` 可能包含意外字段; 方案是咨询。 验证服务器侧面 。
- **Gemini.** OpenAPI 3. 0 奇数 : `enum` 在对象字段中静默地忽略; 验证自己。

<a id="the-translator-pattern"></a>

### 翻译模式

代码中的卡门工具声明看起来像这个(您选择形状) :

```python
Tool(
    name="get_weather",
    description="Use when ...",
    input_schema={"type": "object", "properties": {...}, "required": [...]},
    strict=True,
)
```

三个小函数将它转换成三个提供者形状。 harness 在 `code/main.py` 这样做,然后转弯走一个假的 tool call 不需要网络,这个课可以教给各个提供方的形状,而不是 HTTP.

制作团队包住翻译 `AbstractToolset` (皮德兰特) `UniversalToolNode` (LangGraph), 或 `BaseTool` (LlamaIndex阶段13 - 17艘船只,一个暴露于 OpenAI-shaped API 三个人中任何一个都得在前面

```figure
function-call-args
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 定义一个卡尼卡 `Tool` 数据类和3个翻译 OpenAI, Anthropic, 和 Gemini declaration JSON。然后,它将每个形状的手工制作提供者的反应分析成同一个金刚石调,表明语义在皮肤下是相同的。运行它,并同时测量三个声明。

需要关注的内容：

- 三个申报区块只在信封和字段名称方面有所不同。
- 三个响应区块在呼叫地点不同(顶层) `tool_calls`, `content[]` block, `parts[]` entry).
- One `canonical_call()` 函数摘录 `{id, name, args}` 三个响应形状的

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-provider-portability-audit.md`。鉴于对一个供应商进行功能调用整合,这种技能产生了可移植性审计:哪个供应商限制其依赖的,哪些字段需要重新命名,以及如果相互连接到另一个供应商时会发生什么中断。

<a id="exercises"></a>

## 练习

1. Run `code/main.py` 核实三个提供商的声明 JSONs 全部连环化 `Tool` 对象。修改卡通工具以添加一个 enum parameter 并且只确认 Gemini 翻译需要处理 OpenAPI 怪异。

2. 添加a `ListToolsResponse` 用于为提取工具列表的每个提供者解析一个模型返回 `list_tools` 或发现电话。 OpenAI 不存在一种原生的; 注意这种不对称性。

3. Implement `tool_choice` 转换: 绘制一个卡尼卡 `ToolChoice(mode="force", tool_name="x")` 的图像。然后绘制 `mode="any"` 和 `mode="none"`检查一下课桌

4. 选择三个提供者中的一个, 读取它的函数调用指南结束。 在它的图案中找到一个字段, 其他两个不支持 。 候选人 : OpenAI `strict`, Anthropic `disable_parallel_tool_use`, Gemini `function_calling_config.allowed_function_names`.

5. 写入测试矢量: a tool call 其论点违反了所宣布的策略。 运行它时, 检查每个供应商的验证器( 课程01中的标准lib 将作为代理) 并记录错误的火灾 。 文档中您使用哪家供应商来生产严格性 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Function calling | "工具的使用" | Provider-level API 结构化工具呼叫排放 |
| 工具声明 | "工具规格" | 名称+说明+ JSON Schema输入有效载荷 |
| `tool_choice` | "力量/禁止" | 自动/ 要求 / 无/ 特定名称模式 |
| 严格模式 | "化学执法" | OpenAI 限制解码以匹配 schema 的旗帜 |
| `tool_use` block | "Anthropic调用形状 | 内含内容块, 带有 ID、 名称、 输入 |
| `functionCall` part | "Gemini调用形状 | 一个 `parts[]` 含有名称、参数和id的条目 |
| Arguments-as-string | "Stringified JSON" | OpenAI 返回参数为 JSON 字符串,不是对象 |
| Parallel tool calls | "一转就出来" | Multiple tool calls 在一个助手消息中 |
| Refusal | 模式衰落 | 严格模式的拒绝区,而不是呼叫区 |
| OpenAPI 3. 0 子集 | "Gemini 诡异的阴谋 | Gemini 使用a JSON- 类似方言的方言,有细微差别 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI — Function calling guide](https://platform.openai.com/docs/guides/function-calling) 包括严格模式和平行呼叫的卡通参考
- [Anthropic 工具使用概览](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview) — `tool_use` 和 `tool_result` 块语义
- [谷歌 - Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling) 平行呼叫、独特的ids和 OpenAPI 子集
- [阴性A - Function calling reference](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/function-calling) — Gemini企业表面
- [OpenAI — Structured outputs](https://platform.openai.com/docs/guides/structured-outputs) 严格模式的详细执行方式
