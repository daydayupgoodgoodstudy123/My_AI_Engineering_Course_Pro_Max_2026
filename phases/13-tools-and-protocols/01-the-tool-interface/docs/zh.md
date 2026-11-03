<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="the-tool-interface--why-agents-need-structured-io"></a>

# 工具接口：为什么 Agents 需要结构化输入输出

> 语言模型生成 tokens，程序执行行动。连接两者的是`工具接口`：一份允许模型请求行动、由宿主执行行动的契约。2026 年的各种技术栈——OpenAI、Anthropic 和 Gemini 上的 function calling，MCP 的 `tools/call`，以及 A2A 的 task parts——都是同一个四步循环的不同编码。本课介绍这个循环，并展示运行它所需的最小机制。

**类型：**学习 **语言：**Python（标准库，无需 LLM）
**先修要求：**第 11 阶段（LLM 文本补全 APIs）
**时间：**约 45 分钟<a id="learning-objectives"></a>

## 学习目标

- 解释为什么只能生成文本的 LLM 无法独自对现实世界采取行动。
- 画出工具调用的四步循环（描述 → 决策 → 执行 → 观察），并指出每一步由谁负责。
- 写出由三部分组成的工具描述：名称、采用 JSON Schema 定义的输入，以及确定性的执行函数。
- 区分纯工具与带有副作用的工具，并说明这种区分为何影响安全性。

<a id="the-problem"></a>

## 问题
LLM 输出的是下一个 token 的概率分布，这就是它全部的输出能力。如果你问聊天模型“班加罗尔现在的天气如何”，它能写出看似合理的句子，却无法自行调用天气 API。这句话可能碰巧正确，也可能已经过时三天。

工具接口的目的就是弥合这个差距。

宿主程序——你的 agent 运行时、Claude Desktop、ChatGPT、Cursor 或自定义脚本——

向模型公布可调用工具的列表。

模型判断需要采取行动时，输出一个包含工具名称和参数的结构化载荷。

宿主解析该载荷，真正运行工具，再把结果反馈给模型。



循环继续，直到模型判断不再需要调用工具。

这份契约的首个版本，是 OpenAI 于 2023 年 6 月推出的“functions” parameter。随后 Anthropic 在 Claude 2.1 中加入了 `tool_use` 块，Gemini 几个月后也加入了 `functionDeclarations`。如今各提供商都暴露相同结构：输入是由 JSON Schema 定义类型的工具列表，输出是包含 JSON 载荷的 tool call。Model Context Protocol（2024 年 11 月）把这份契约通用化，让同一个工具注册表服务于所有模型。A2A（2026 年 4 月，v1.0）把相同的基础机制扩展到 agent 与 agent 之间的 delegation。

四步循环是所有这些形式背后保持不变的结构。第 13 阶段的其他内容都是对它的扩展。

<a id="the-concept"></a>

## 概念

<a id="step-one-describe"></a>

### 第一步：描述

宿主使用三个字段声明每个工具。

- **名称** 稳定、机器可读的标识符。使用 `get_weather`，而不是“天气那个工具”。
- **描述** 一段自然语言说明：“用户询问某个城市的当前天气时使用。不要用于历史数据。”
- **输入 schema** 一个描述工具参数的 JSON Schema 对象（draft 2020-12）。

模型接收工具列表。现代提供商使用各自的专用模板，把这些声明序列化进 system prompt；调用方只需处理结构化形式。

<a id="step-two-decide"></a>

### 第二步：决策

模型根据用户消息和可用工具，选择以下三种行为之一。

1. **直接回答**文本，不进行 tool call
2. **调用一个或多个工具** 输出结构化调用对象。启用 `parallel_tool_calls: true` 时（OpenAI 和 Gemini 默认启用，Anthropic 需要主动开启），模型可以在一轮中输出多个调用。
3. **拒绝** 严格模式的 structured outputs 可以输出一个具有明确类型的 `refusal` 块，而不是调用。

tool call 载荷有三个稳定字段：调用 `id`、工具 `name`，以及 JSON 格式的 `arguments` 对象。id 用于让宿主把后续结果关联到具体调用；并行调用的结果按不同顺序返回时，这一点尤其重要。

<a id="step-three-execute"></a>

### 第三步：执行

宿主接收调用，按已声明的 schema 校验参数，然后运行执行函数。参数无效通常意味着模型虚构了字段或使用了错误类型——这在能力较弱的模型上很常见。

生产宿主通常采用三种方式之一：

立即失败并把错误返回模型；

使用受约束的解析器修复 JSON；

或把校验错误加入 prompt，让模型重试。

执行函数本身就是普通代码，可以是 Python、TypeScript、Shell 命令或数据库查询。它生成一个结果，通常是字符串，也可以是任意 JSON 值，或结构化内容块（在 MCP 中可以是文本、图像或资源引用）。结果必须能够序列化。

<a id="step-four-observe"></a>

### 第四步：观察

宿主把工具结果追加到对话中（作为一条角色为 `tool`、具有匹配 `id` 的消息），然后再次调用模型。此时模型的上下文中已有工具输出，可以给出最终答案或请求更多调用。循环继续，直到模型不再输出调用，或宿主达到迭代次数的安全上限。

<a id="the-trust-split"></a>

### 信任边界的划分

从安全角度看，工具分为以下两类。

- **纯工具** 只读、确定性、无副作用，例如 `get_weather`、`search_docs`、`get_current_time`。可以安全地提前试调用。
- **会产生实际影响的工具** 会修改状态、花费资金或操作用户数据，例如 `send_email`、`delete_file`、`execute_trade`。必须设置控制关卡。

Meta 在 2026 年提出的 agent 安全“Rule of Two”指出：单轮操作最多只能组合以下三项中的两项——不可信输入、敏感数据、产生实际影响的行动。工具接口是执行这条规则的位置：拒绝调用、要求用户确认，或升级权限范围。完整的安全章节见第 13 阶段第 15 课；agent 级别的权限策略见第 14 阶段第 09 课。

<a id="where-the-loop-lives"></a>

### 循环运行在哪里

| 上下文 | 谁负责描述 | 谁负责决策 | 谁负责执行 |
|---------|---------------|-------------|--------------|
| 单轮 function calling（OpenAI/Anthropic/Gemini） | 应用开发者 | LLM | 应用开发者 |
| MCP | MCP 服务器 | LLM，通过 MCP 客户端调用 | MCP 服务器 |
| A2A | Agent Card 发布者 | 发起调用的 agent | 被调用的 agent |
| Web 浏览器（支持 function calling 的 agent） | 浏览器扩展 / WebMCP | LLM | 浏览器运行时 |

无论在哪种场景，都是相同的四步。列名可以变化，结构保持不变。

<a id="why-not-just-prompt-the-model-to-emit-json"></a>

### 为什么不直接通过 prompt 要求模型输出 JSON？

“要求模型用 JSON 回答”是原生 function calling 出现之前的做法。即使在前沿模型上，它也有约 5%–15% 的失败率，小模型则更高。常见问题包括缺少括号、多余的末尾逗号、虚构字段和类型错误。随后还需要修复 JSON、重试，或使用受约束的 decoder。

原生 function calling 有三个优势。第一，提供商针对精确的调用结构进行端到端训练，使严格模式下的有效 JSON 比例升至 98%–99%。第二，调用载荷占据独立的协议位置，不混在自由文本里，因此 tool call 不会泄露到用户可见的回复中。第三，提供商通过受约束解码保证 schema 合规性（OpenAI 的 strict mode、Anthropic 的 `tool_use`、Gemini 的 `responseSchema`）。输出保证能够通过校验。

第 13 阶段第 02 课并排讲解三家提供商的 APIs；第 04 课深入讲解 structured outputs。

<a id="circuit-breakers"></a>

### Circuit breakers

模型不再输出调用，或宿主达到最大轮数时，循环终止。生产宿主通常设定 5–20 轮的上限。超过这个范围，几乎可以确定模型已陷入无法退出的循环。Claude Code 的默认值是 20，OpenAI Assistants 是 10，Cursor 的 agent 模式是 25。

另一种做法是不设置循环上限，但每隔几个月就会出现一次类似“agent 一夜之间调用 API 花了 400 美元”的事故复盘。交付之前一定要设置上限。

第 14 阶段第 12 课深入讲解错误恢复与自愈；第 17 阶段讲解生产环境中的 rate limits。

<a id="where-phase-13-goes-from-here"></a>

### 第 13 阶段接下来学什么

- 第 02–05 课完善提供商层面的工具调用接口。
- 第 06–14 课把循环通用化为 MCP。
- 第 15–18 课保护循环，防范恶意服务器、对抗性用户，以及未经身份验证的远程认证接口。
- 第 19–22 课把这一模式扩展到 agent 与 agent 之间的协作、observability、路由和封装。
- 第 23 课利用所有基础机制，交付一个完整的生态系统。

后续每一课都是这个四步循环的扩展。把它作为始终不变的结构牢记在心。

```figure
tp-tool-loop
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 无需 LLM 即可运行四步循环。一个模拟的“决策函数”通过匹配 user message 中的模式来模拟模型；执行函数、schema 校验器和观察步骤中的 harness 都是真实实现。运行程序，可以看到完整的请求与响应流程，以及可打印的中间状态；之后的课程再把模拟决策函数替换为任意真实提供商。

需要关注的内容：

- 工具注册表为每个工具保存三个字段：名称、描述、schema，以及执行函数引用。
- 校验器仅用标准库实现 JSON Schema 的最小子集，支持 types、required、enum、min/max。第 13 阶段第 04 课提供更完整的实现。
- 循环把迭代次数限制为五次。生产环境的 agents 正需要这种 circuit breaker。

<a id="ship-it"></a>

## 交付成果

本课生成 `outputs/skill-tool-interface-reviewer.md`。给定一份工具定义草稿（名称、描述、schema、执行函数概要），这个 skill 会检查它是否适合该循环：名称是否稳定且便于机器使用，描述是否完整说明使用方式，schema 是否正确使用 JSON Schema 2020-12，以及是否明确区分纯工具与会产生实际影响的工具。

<a id="exercises"></a>

## 练习

1. 向 `code/main.py` 添加第四个工具，命名为 `get_stock_price(ticker)`。描述写为：“用户按股票代码查询当前股价时使用。不要用于历史价格或市场综述。”运行 harness，确认模拟决策函数会把含股票代码的查询路由到新工具。

2. 故意让 schema 校验失败。传入一个 `arguments` 对象缺少必填字段的调用，确认宿主会在执行前拒绝它。再传入包含额外未知字段的调用。决定宿主应该拒绝还是忽略，并从安全角度说明理由。

3. 把 harness 中的每个工具分类为纯工具或会产生实际影响的工具。在需要的注册项中添加 `consequential: true` 标记，并修改循环，使它在选择后一类工具时打印“此处会向用户请求确认”。这就是每个生产宿主所需确认关卡的基本结构。

4. 在纸上画出四步循环，并针对你最常用的客户端（Claude Desktop、Cursor、ChatGPT 或自定义技术栈）填写上面的提供商对照表。与第 13 阶段第 06 课中 MCP 专用的变体对照。

5. 完整阅读 OpenAI 的 function calling 指南。找出请求中存在、但本课所述四步循环中没有的一项字段。解释它增加了什么能力，以及为何它只是提供便利，而非必需。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 工具 | “模型可以调用的东西” | 由名称、采用 JSON Schema 定义类型的输入、执行函数组成的三元组 |
| Function calling | “原生工具使用” | 提供商层面的 API 支持，让模型输出结构化 tool calls，而不是普通文本 |
| Tool call | “模型请求采取行动” | 模型输出的 JSON 载荷，包含 `id`、`name`、`arguments` |
| 工具结果 | “工具返回的内容” | 执行函数的输出，封装在角色为 `tool`、具有匹配 id 的消息中 |
| 并行 tool calls | “一次发出多个调用” | 同一轮模型输出中的多个调用对象，相互独立，可通过 id 识别和排序 |
| 严格模式 | “保证有效的 JSON” | 通过受约束解码，强制模型输出通过已声明 schema 的校验 |
| 纯工具 | “只读工具” | 无副作用，可以安全地重复运行 |
| 会产生实际影响的工具 | “行动工具” | 修改外部状态，需要控制关卡、审计或用户确认 |
| 四步循环 | “工具调用周期” | 描述 → 决策 → 执行 → 观察 |
| 宿主 | “Agent 运行时” | 保存工具注册表、调用模型并运行执行函数的程序 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI——Function calling 指南](https://platform.openai.com/docs/guides/function-calling)——OpenAI 风格的工具声明与调用结构的权威参考
- [Anthropic——工具使用概览](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)——Claude 的 `tool_use` / `tool_result` 块格式
- [Google——Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling)——Gemini 中的 `functionDeclarations` 与并行调用语义
- [Model Context Protocol——2026-07-28 版规范](https://modelcontextprotocol.io/specification/2026-07-28)——当前工具接口的无状态、跨提供商通用形式
- [JSON Schema——2020-12 版本说明](https://json-schema.org/draft/2020-12/release-notes)——现代工具 API 使用的 schema 方言
