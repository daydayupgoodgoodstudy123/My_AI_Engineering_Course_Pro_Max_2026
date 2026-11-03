<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="opentelemetry-genai--tracing-tool-calls-end-to-end"></a>

# OpenTelemetry GenAI：端到端追踪 Tool Calls

> 一个 agent 呼叫五台工具 三台 MCP 服务器,和两个子agents。你需要一个 trace 横跨所有它。 GenAI 的开放遥测语义学( v1.37 和以上中的稳定属性) 是 2026 年的标准, 由 Datadog 、 Langfuse、 Arize Phoenix、 OpenLLetry 和 AgentOps 支持。 此课命名了所需的属性, 沿过跨线等级( 由 Datadog 、 Langfuse 、 Arize Phoenix、 OpenLetry 和 AgentOps 组成 ) 。agent → LLM 工具),并装运一个标准级横贯发射器,您可以插入任何 OTel 出口者。

**类型:** Build
**语言:** Python (stdlib, OTel 横跨发射)
**先修要求:** 阶段13 -07 (MCP 服务器,第13阶段 ・ 08 (MCP client)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 指定需要的 OTel GenAI 属性 LLM 横线和工具执行宽度。
- 构建 trace 覆盖 agent loop, LLM call, tool call, 和 MCP 客户端调度 。
- 决定要捕捉的内容( 选择适用) 与编辑( 默认) 。
- Emit 覆盖本地收藏家( Jaeger, Langfuse), 但没有重写工具代码 。

<a id="the-problem"></a>

## 问题

2026年2月的调试:用户报告“我 agent 有时需要30秒回应, 其它乘以3秒。" traces。日志显示 LLM 调用, 但不是工具发送, 不是 MCP 服务器圆程, 不是子-agent你猜,最终你会发现: MCP 服务器偶尔会挂在冷启动上 。

没有端到端的追踪,你找不到这个。 OTel GenAI 修复它 。

2025-2026年在开放遥测语义- 公约组下达成的公约, 定义了稳定属性名称, 以便数据犬、 兰弗斯、 凤凰城、 OpenLLetry 和 AgentOps 都分析相同的范围。 仪器一次; 将文件送至任何后端 。

<a id="the-concept"></a>

## 概念

<a id="span-hierarchy"></a>

### span 等级

```
agent.invoke_agent  (top, INTERNAL span)
 ├── llm.chat       (CLIENT span)
 ├── tool.execute   (INTERNAL)
 │    └── mcp.call  (CLIENT span)
 ├── llm.chat       (CLIENT span)
 └── subagent.invoke (INTERNAL)
```

整个东西都藏在一个下面 trace id. Span IDs连接了父母与子女的关系。

<a id="required-attributes"></a>

### 所需属性

2025-2026年的地震:

- `gen_ai.operation.name` — `"chat"`, `"text_completion"`, `"embeddings"`, `"execute_tool"`, `"invoke_agent"`.
- `gen_ai.provider.name` — `"openai"`, `"anthropic"`, `"google"`, `"azure_openai"`.
- `gen_ai.request.model` 要求的型号字符串(例如: `"gpt-4o-2024-08-06"`).
- `gen_ai.response.model` - 模型实际上已经使用。
- `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens`.
- `gen_ai.response.id` 供应商的反应id,说明相关情况。

工具的横跨 :

- `gen_ai.tool.name` - 工具识别器。
- `gen_ai.tool.call.id` - 具体电话号
- `gen_ai.tool.description` - 工具说明(可选)。

用于 agent spans:

- `gen_ai.agent.name` / `gen_ai.agent.id` / `gen_ai.agent.description`.

<a id="span-kinds"></a>

### span 类型

- `SpanKind.CLIENT` 跨越进程边界的电话(LLM provider, MCP server).
- `SpanKind.INTERNAL` 用于 agent自己的循环步骤和工具执行。

<a id="opt-in-content-capture"></a>

### 选择内容捕获

默认情况下,宽幅带有衡量标准和时间——而不是 prompts 或完成。 大有效载荷和 PII 默认关闭。 设置 `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` 和特定的内容获取 env evors 以包含内容。 在允许输入前仔细审查 。

<a id="events-on-spans"></a>

### 跨度活动

Token- 活动级别可加为跨度:

- `gen_ai.content.prompt` 输入信息。
- `gen_ai.content.completion` 输出信息。
- `gen_ai.content.tool_call` — tool call 记录。

事件时间顺序在详细重播的间隔内 。

<a id="exporters"></a>

### Exporters

OTel 横切为 :

- **贾格/泰波** OSS,在预备。
- **Langfuse.** LLM-observability- 特定; 可视化 token usage.
- **亚里兹・凤凰城** Evals + 跟踪组合。
- **Datadog.** 商业; 原生剖析 `gen_ai.*` attributes.
- **Honeycomb.** 以列为导向; 方便查询。

全部说OTLP,电线格式,你的代码不关你的事

<a id="propagation-across-mcp"></a>

### 跨过传播 MCP

当 MCP 客户端呼叫服务器, 将 W3C 追踪头输入请求中。 可移动 HTTP 支持标准信头。 Stdio 不携带 HTTP 本地页眉; 2026年的路线图讨论添加 `_meta.traceparent` 字段中 JSON-RPC calls.

直到那艘船: 包括追踪者 `_meta` 手动输入每个请求。 trace id.

<a id="metrics"></a>

### Metrics

与宽度相加,GenAI Semconv定义了衡量标准:

- `gen_ai.client.token.usage` 直方图
- `gen_ai.client.operation.duration` 直方图
- `gen_ai.tool.execution.duration` 直方图

用于不需要每次通话细节的仪表板。

<a id="agentops-layer"></a>

### 代理Ops 层

职业介绍(原2024年)专门从事GenAI observability将流行框架包起来(LangGraph皮德兰特·艾伯特 CrewAI) 自动排放 OTel 。如果您的堆叠使用支持的框架,则有用;否则使用手动仪器。

```figure
t3-span-waterfall
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 释放OTel形的横幅以至 stdout(在 OTLP-)JSON- 类似格式) agent 需要时间 LLM,发送两个工具,并制作一个 MCP 圆形。 没有真正的导体, 课程的焦点是横幅形状和属性集。 将输出粘贴到符合 OTLP 的查看器中, 或者只是读取它 。

需要关注的内容：

- Trace ID 在所有范围内共享 。
- 父母与子女的联系通过下列方式编码: `parentSpanId`.
- 必需 `gen_ai.*` 属性被包含。
- 默认内容捕获关闭; 一种情景通过 env var 打开它 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-otel-genai-instrumentation.md`。如果有的话 agent 代码库, 技能产生一个仪器计划: 添加宽度、 显示宽度、 输出方目标 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。计算间隔,并标明哪个是CLINT对 Internet 。

2. 打开内容捕获( env var) 并确认 `gen_ai.content.prompt` 和 `gen_ai.content.completion` 事件出现。请注意对 PII 的影响。

3. 添加工具执行度量 `gen_ai.tool.execution.duration` 并把它作为直方图样本 以每个呼叫。

4. 向父母宣传追蹤父母 agent 横幅 MCP request's `_meta.traceparent` 字段。 MCP 服务器会看到相同 trace id.

5. 读取 OTel GenAI emconv 的特性。 确定该课程代码未发出的一个属性 。 添加它 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| OTel | "OpenTelemetry" | 开放标准 traces、度量、日志 |
| 吉纳·塞姆科夫 | "金AI语义学惯例" | 稳定属性名称 LLM / 工具 / agent spans |
| `gen_ai.*` | “ 属性命名空间” | 全部 GENAI 属性共享此前缀 |
| Span | "时间操作" | 带有开始、结束和属性的工作单位 |
| Trace | 十字河系的祖先 | 共享的横线树 a trace id |
| SpanKind | "客户/服务器/内部" | 横跨方向的提示 |
| OTLP | “开放遥测线协议” | 出口商的电线格式 |
| 选择内容 | "Prompt / 完成抓取” | 默认关闭; 设置 var 启用 |
| traceparent | "W3C头" | Propagates trace 跨服务领域背景 |
| Exporter | "后端特定托运人" | 向 Jaeger / Datadog 等发送的组件 。 |

<a id="further-reading"></a>

## 进一步阅读

- [开放遥测- GenAI emconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/) 通用会计原则的有效期、衡量标准及活动
- [开放遥测 - GenAI 宽度](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/) — LLM 工具执行宽度属性列表
- [开放遥测——GenAI agent spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/) — agent-level `invoke_agent` span
- [开放遥测/语义-公约——通用数字数字系统](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/gen-ai-spans.md) — GitHub- 被接纳的真相来源
- [数据犬 LLM OTel语义学公约](https://www.datadoghq.com/blog/llm-otel-semantic-convention/) 生产一体化的步进
