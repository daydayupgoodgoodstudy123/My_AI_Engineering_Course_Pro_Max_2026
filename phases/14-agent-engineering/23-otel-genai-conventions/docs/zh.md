<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="opentelemetry-genai-semantic-conventions"></a>

# OpenTelemetry GenAI 语义约定

> OpenTeetrict 的 GENAI SIG (2024年4月发射) 定义了 agent 遥测。 批量名称、属性和内容获取规则在供应商之间趋同 agent traces 意思是数据犬,格拉法纳,杰格和哈尼科姆 也有同样的意思

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 13 (LangGraph),第14阶段 24(a)Observability Platforms)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 命名 GENAI 横跨类别: 模型/客户, agent工具
- Distinguish `invoke_agent` 法律倡议与内部系统之间以及每个适用时。
- 列出顶级 GENAI 属性: 提供者名称、 请求模式、 数据源 ID 。
- 解释内容获取合同:选择加入, `OTEL_SEMCONV_STABILITY_OPT_IN`,外部参考建议。

<a id="the-problem"></a>

## 问题

每个供应商都发明了自己的跨线名称。 操作团队最终会建造每个框架的仪表板。 开放遥测的GenAI SIG通过定义整个生态系统目标的标准来解决这个问题。

<a id="the-concept"></a>

## 概念

<a id="span-categories"></a>

### span 类别

1. **模型/客户端横跨。** 原始覆盖 LLM 电话: 由提供商发放 SDKs (Anthropic, OpenAI和框架模型适配器。
2. **Agent spans.** `create_agent` (当 agent 和(或) `invoke_agent` 等它运行的时候
3. **工具横跨。** 每个工具引用一个;连接到 agent 父母与子女关系之间的间隔。

<a id="agent-span-naming"></a>

### Agent 横线命名

- span 名称 : `invoke_agent {gen_ai.agent.name}` 如果命名; 返回到 `invoke_agent`.
- 平方形 :
  - **CLIENT** 远程 agent 服务(OpenAI Assistants API贝德洛克 Agents).
  - **INTERNAL** 用于在轨 agent 框架(LangChain, CrewAI, 本地 ReAct).

<a id="key-attributes"></a>

### 密钥属性

- `gen_ai.provider.name` — `anthropic`, `openai`, `aws.bedrock`, `google.vertex`.
- `gen_ai.request.model` - 型号的ID。
- `gen_ai.response.model` 解决模式(由于路线安排,可能不同于要求)。
- `gen_ai.agent.name` — agent identifier.
- `gen_ai.operation.name` — `chat`, `completion`, `invoke_agent`, `tool_call`.
- `gen_ai.data_source.id` — 用于 RAG:查阅了哪个档案或储存。

现有关于技术的公约 Anthropic阿拉伯湾 InferenceAWS贝德洛克, OpenAI.

<a id="content-capture"></a>

### 内容捕获

默认规则: 仪器不应默认地记录输入/输出。 抓取方式为 :

- `gen_ai.system_instructions`
- `gen_ai.input.messages`
- `gen_ai.output.messages`

建议的生产模式: 外部存储内容( S3, 您的日志存储), 跨段记录引用( 指针编号, 不是文章) 。 这是连接到的27号内容溢出防线 observability.

<a id="stability"></a>

### 稳定性

大多数公约都是2026年3月的实验。 选择进入稳定的预览 :

```
OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental
```

数据狗 v1.37+ GenAI 属性, 原生地进入 LLM Observability schema。 其他后端( Grafana, Honeycomb, Jaeger) 支持原始属性 。

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **获取完整 prompts 以横线计。** PII, 机密, 客户数据 traces 行动可以读,对外储存
- **否 `gen_ai.provider.name`.** 缺少归属时, 多提供者仪表板会中断 。
- **没有任何父系链接的垃圾邮件 。** 孤军作战工具横跨了整个区域,总是传播背景
- **不设定稳定性选择。** 您的属性可以在后端升级时重新命名 。

```figure
ae-genai-span-tree
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行符合 GenAI 常规的 Stdlib 范围发射程序 :

- `Span` 使用 GenAI 属性图案 。
- `Tracer` 与 `start_span`,嵌套环境。
- 脚本 agent 运行该发行 : `create_agent`, `invoke_agent` 内部,每个工具的长度, `chat` 区域 LLM calls.
- 存储内容获取模式 prompts 外部记录了横跨的标识

运行：

```
python3 code/main.py
```

输出: 带所有需要 GenAI 属性的横线树, 以及显示选择输入内容引用的“ 外部存储 ” 。

<a id="use-it"></a>

## 实际应用

- **Datadog LLM Observability** (v1.37+) 地图原生属性。
- **兰福斯/凤凰/奥皮克** (第24条)——生态系统的自动仪器。
- **杰格/哈尼科布/格拉法纳- 坦波** - 生奥特 traces;根据 GENAI 属性建立仪表板。
- **Self-hosted** 使用GenAI处理器管理 OTel 采集器。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-otel-genai.md` OTel GenAI 连接到一个现有 agent 含有内容获取默认值和外部参考存储。

<a id="exercises"></a>

## 练习

1. 乐于学习你的第1课 ReAct 循环 `invoke_agent` + / 每工具的宽度。 发送到 Jaeger 实例 。
2. 添加“ 只引用” 模式的内容捕获 : prompts 键到 SQLite,横跨属性只包含行编号。
3. 读取规格 `gen_ai.data_source.id`把它连接到9点的课里
4. Set `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` 验证你的属性,不会被收藏家重新命名。
5. 构建一个仪表板:“ 工具错误与哪些模型相关” 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 吉纳西格 | "开放遥测 GenAI 组" | OTel工作组确定方案 |
| invoke_agent | "Agent span" | 代表 agent run |
| 课程跨度 | 远程呼叫 | 拨打遥控器 agent service |
| 内部间隔 | "In-process" | 用于进程中的span agent run |
| gen_ai.provider.name | "Provider" | anthropic / openai / aws. bedrock / google. vertex / / 斜体 / 斜体 / 斜体 。 |
| gen_ai.data_source.id | "RAG source" | 哪个实体/存储检索被击中 |
| 内容捕获 | "Prompt logging" | 选择收件; 将信件存储到外部 |
| 稳定选择适用 | "预览模式" | 信封 var 以锁定实验性常规 |

<a id="further-reading"></a>

## 进一步阅读

- [GenAI语义学公约](https://opentelemetry.io/docs/specs/semconv/gen-ai/) - 规格
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) 默认的 GenAI 宽度
- [AutoGen v0.4 (微软研究)](https://www.microsoft.com/en-us/research/articles/autogen-v0-4-reimagining-the-foundation-of-agentic-ai-for-scale-extensibility-and-robustness/) - OTel 环形图
- [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview) - W3C 号卫星 trace 环境传播
