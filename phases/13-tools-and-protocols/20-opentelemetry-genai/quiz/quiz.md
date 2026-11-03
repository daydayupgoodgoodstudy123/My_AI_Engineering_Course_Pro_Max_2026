# 测验 · OpenTelemetry GenAI：端到端追踪 Tool Calls（OpenTelemetry GenAI — Tracing Tool Calls End-to-End）

> **阶段 13 · 工具与协议 · 第 20 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Trace 与 Span | 一个 trace 是共享同一 trace id 的 span 树；span 是有开始、结束、属性的一段工作，父子关系靠 `parentSpanId` 连接 |
| 2 | Agent 的 span 层级 | `agent.invoke_agent`（根，INTERNAL）→ `llm.chat`（CLIENT）、`tool.execute`（INTERNAL）→ `mcp.call`（CLIENT）、`subagent.invoke`（INTERNAL） |
| 3 | SpanKind | 跨进程边界的调用（LLM 提供方、MCP server）用 CLIENT；agent 自己的循环步骤与工具执行用 INTERNAL；被调服务端用 SERVER |
| 4 | LLM span 必备属性 | `gen_ai.operation.name`、`gen_ai.provider.name`、`gen_ai.request.model`、`gen_ai.response.model`、`gen_ai.usage.input_tokens` / `output_tokens`、`gen_ai.response.id` |
| 5 | Tool / Agent span 属性 | 工具：`gen_ai.tool.name`、`gen_ai.tool.call.id`、可选 `gen_ai.tool.description`；agent：`gen_ai.agent.name` / `id` / `description` |
| 6 | 内容捕获默认关闭 | 默认只记时序与指标，不记 prompt / completion；开启后以 span event（`gen_ai.content.prompt` 等）记录，需评估 PII 风险 |
| 7 | 跨进程传播 | W3C `traceparent` = `00-<32 位十六进制 trace id>-<16 位十六进制父 span id>-<flags>`；Streamable HTTP 走请求头，stdio 无 HTTP 头，讲义建议放进 JSON-RPC 的 `_meta.traceparent` |
| 8 | GenAI 指标 | `gen_ai.client.token.usage`、`gen_ai.client.operation.duration`、`gen_ai.tool.execution.duration`（直方图），用于不需要逐次细节的看板 |
| 9 | OTLP 与后端无关 | Jaeger / Tempo、Langfuse、Phoenix、Datadog、Honeycomb 都接收 OTLP；按语义约定埋点一次，可发往任何后端 |
| 10 | 语义约定的价值 | 统一的 `gen_ai.*` 属性名让不同厂商工具解析同一份 span；自定义属性要带明确前缀 |

### 核心技能（能动手做到）

- [ ] 读本节输出，数出 span 数量，标出每个 span 的 kind 和父节点
- [ ] 为一次 LLM 调用、一次工具调用、一次 agent 调用分别列出应填的 `gen_ai.*` 属性
- [ ] 手写 W3C `traceparent`，并在 MCP 服务端解析它、创建同一 trace 下的 SERVER span
- [ ] 用环境变量开关内容捕获，说清开启后的 PII 风险与缓解措施
- [ ] 为工具执行时长实现一个直方图指标（`gen_ai.tool.execution.duration`）
- [ ] 用上下文管理器 / `contextvars` 改写埋点，保证异常时 span 也能结束并带上错误信息

---

## 二、基础自测（选择题）

**Q1.** 运行本节 `code/main.py`，一共会输出多少个 span？

- A. 6
- B. 9
- C. 7
- D. 5

**Q2.** 下列 span 与 SpanKind 的对应，哪一组与讲义和代码一致？

- A. `llm.chat` → INTERNAL；`mcp.call` → INTERNAL
- B. `agent.invoke_agent` → CLIENT；`tool.execute` → CLIENT
- C. `tool.execute` → SERVER；`mcp.call` → INTERNAL
- D. `llm.chat` → CLIENT；`tool.execute` → INTERNAL；`mcp.call` → CLIENT

**Q3.** 本节 `fake_mcp_call` 构造的 `traceparent` 是 `f"00-{mcp_span.trace_id}-{mcp_span.span_id}-01"`。关于这个字符串，正确的是：

- A. 第二段是 32 个十六进制字符的 trace id，第三段是**发起调用的 CLIENT span** 的 16 位十六进制 id，服务端会把它当作自己 span 的父 id；末尾 `01` 表示已采样
- B. 第三段应该填根 span 的 id，否则 trace 会断开
- C. `00` 表示采样标志，`01` 表示版本号
- D. 第二段每次 MCP 调用都应该重新生成，以免不同调用互相干扰

**Q4.** 讲义规定 prompt / completion 内容默认**不**写入 span，主要原因是：

- A. OTLP 协议不支持字符串属性
- B. 内容写入后会改变 span 的父子关系
- C. 内容体积大、可能包含 PII，默认关闭；需要时显式开启并审慎评估
- D. 内容只能写进指标，不能写进 span

**Q5.** 要知道提供方**实际服务**的是哪个模型版本（可能与请求的别名不同），应看哪个属性？

- A. `gen_ai.request.model`
- B. `gen_ai.provider.name`
- C. `gen_ai.operation.name`
- D. `gen_ai.response.model`

**Q6.** MCP 客户端通过 **stdio** 调用服务端，要让服务端日志关联到同一个 trace。按讲义，应该怎么做？

- A. stdio 没有 HTTP 头，把 `traceparent` 放进每个 JSON-RPC 请求的 `_meta.traceparent`
- B. 放进 HTTP 请求头 `traceparent`
- C. 不需要传播，服务端会自动继承父进程的 trace
- D. 把 trace id 写进工具参数 `arguments` 里

**Q7.** 本节 `fake_llm_call` 用 `len(prompt) // 4` 估算输入 token。第一次 LLM 调用的 prompt 是 `"user wants weather in three cities"`，`gen_ai.usage.input_tokens` 的值是：

- A. 34
- B. 6
- C. 8
- D. 9

**Q8.** 你只想做一个"各工具 p95 延迟"的看板，不需要逐次调用的细节。讲义建议优先使用：

- A. 打开内容捕获，在 span event 里记录每次调用
- B. GenAI 指标，如 `gen_ai.tool.execution.duration` 直方图
- C. 只看日志
- D. 给每个 span 加一个自定义的 `latency` 属性

---

## 三、动手 / 代码题

**Q9.** 对照讲义"Use It"与代码，找出至少 5 处不一致或"看起来像标准、其实不是"的地方。提示：banner 编号、工具与 MCP 调用次数、输出能否直接粘贴进 OTLP 查看器、内容捕获的环境变量、`traceparent` 是否真的被发送、打印时过滤了哪些属性。

**Q10.** 完成讲义练习 4：把 `traceparent` 从客户端 span 传播到 MCP 请求的 `_meta.traceparent`，并写出服务端的解析逻辑——服务端要创建一个 SERVER span，其 trace id 与客户端相同、父 span id 等于客户端 `mcp.call` span 的 id。`traceparent` 格式不合法时应该怎么办？

**Q11.** 完成讲义练习 3：为每次工具执行记录 `gen_ai.tool.execution.duration` 直方图样本（单位秒）。用 `[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1, 2.5, 5, 7.5, 10]` 作为桶边界，跑一次 `agent_loop()` 后，样本会落在哪个桶？总数和总和大约是多少？

**Q12.** 假设 `fake_tool_execute` 抛出 `TimeoutError`（模拟 MCP server 冷启动挂起）。

1. 用原代码，异常抛出后 `SPANS` 中各 span 的 `end_ns` 是多少？导出后会出现什么问题？
2. 用 `contextmanager` + `contextvars` 写一个 `span(...)` 上下文管理器：自动以当前 span 为父、异常时记录 `error.type` 并把状态置为错误、无论如何都结束 span。

---

## 四、面试高频题

**Q13.**（基础必考）解释 trace、span、SpanKind、attribute、event 的概念。一个 agent 调用 LLM、再通过 MCP 调用工具，你会建哪些 span、各自是什么 kind、带哪些 `gen_ai.*` 属性？

**Q14.**（原理深挖）分布式追踪的上下文是怎样跨进程、跨线程、跨异步任务传播的？MCP 的 stdio 与 Streamable HTTP 在传播上有什么不同？

**Q15.**（工程实践）生产环境中是否应该在 span 里记录 prompt 和 completion？请给出一套内容捕获与数据治理策略。

**Q16.**（场景设计）讲义开头的案例：用户反映"agent 有时 30 秒才响应，有时 3 秒"。你会如何用 OTel GenAI 的 trace 和指标定位到"某个 MCP server 冷启动偶尔挂起"？需要哪些看板和告警？

**Q17.**（追问型）为什么要遵循 GenAI semantic conventions，而不是各团队自定义属性名？语义约定还在演进时，如何避免升级时看板全部失效？

---

## 五、参考答案与解析

### Q1 — 答案：B

实际运行输出 `emitted 9 spans across 1 trace`：1 个根 `agent.invoke_agent` + 2 个 `llm.chat` + 3 个 `tool.execute`（Bengaluru、Tokyo、Zurich 各一次）+ 3 个 `mcp.call`（每个工具 span 下一个）= 9。注意讲义 Use It 写的是"dispatches two tools, and makes one MCP round-trip"，按那个描述会是 1 + 2 + 2 + 1 = 6（选项 A），与代码不符。C、D 是常见的漏数结果（漏掉 MCP 子 span 或第二次 LLM 调用）。

### Q2 — 答案：D

讲义："`SpanKind.CLIENT` for calls crossing a process boundary (LLM provider, MCP server). `SpanKind.INTERNAL` for the agent's own loop steps and tool execution." 代码中 `llm.chat` 与 `mcp.call` 都是 `"CLIENT"`，`agent.invoke_agent` 与 `tool.execute` 是 `"INTERNAL"`。A、B、C 都至少弄错一个。SERVER 是被调用的服务端（如 MCP server 进程内处理请求的 span）使用的 kind，本节代码没有生成。

### Q3 — 答案：A

W3C `traceparent` 的四段依次是：版本（`00`）、trace id（16 字节 = 32 个十六进制字符）、parent id（8 字节 = 16 个十六进制字符）、trace flags（`01` = sampled）。parent id 应该是**直接发起这次远程调用的 span**，也就是 `mcp.call` 这个 CLIENT span，服务端据此把自己的 SERVER span 挂在它下面。B 错：填根 span 会让服务端 span 挂错层级（trace 不会断，但树形结构错了）。C 把版本和标志弄反了。D 错：trace id 必须在整条调用链中保持不变，否则就成了另一个 trace。

### Q4 — 答案：C

讲义："By default, spans carry metrics and timing — not prompts or completions. Large payloads and PII are off by default... Review carefully before enabling in prod." 技能文件也把"content capture on by default"列为硬拒绝项。A 错，属性支持字符串；B 无关；D 错，内容开启后是作为 span event 记录的。

### Q5 — 答案：D

`gen_ai.request.model` 是请求时写的模型名（代码中是 `"gpt-4o"`），`gen_ai.response.model` 是实际服务的模型（代码中是 `"gpt-4o-2024-08-06"`）。请求别名可能被提供方路由到具体快照版本，排查"行为突然变化"时要看后者。B 是提供方（`openai`），C 是操作类型（`chat`）。

### Q6 — 答案：A

讲义："Stdio does not carry HTTP headers natively... include the traceparent in the `_meta` of every request manually." B 只适用于 Streamable HTTP。C 错：子进程不会自动继承 trace 上下文（环境变量方式只能在启动时传一次，无法区分每次调用）。D 会污染工具参数，工具 schema 校验也可能拒绝它。

### Q7 — 答案：C

`len("user wants weather in three cities")` = 34，`34 // 4 = 8`。实际运行输出中两次 LLM 调用的 `gen_ai.usage.input_tokens` 都是 8（第二个 prompt `"synthesize three weather results"` 长 32，同样 `// 4 = 8`）。`output_tokens` 是 `random.randint(20, 80)`，每次运行不同（本次为 39 和 26）。A 是字符数；`//` 是整除，不会是 9。这只是演示用的粗略估计，真实值应来自提供方响应中的 usage 字段。

### Q8 — 答案：B

讲义 "Metrics"："Use these for dashboards that do not need per-call detail." 指标是预聚合的直方图，存储和查询成本远低于逐个 span。A 引入不必要的 PII 风险；C 日志难以聚合出分位数；D 的自定义属性不在语义约定中，后端无法通用解析，而且 span 本身已经有起止时间。

### Q9 — 参考答案

| # | 现象 | 说明 |
|---|------|------|
| 1 | banner 打印 `PHASE 13 LESSON 19` | 本节是第 20 节；`outputs/skill-otel-genai-instrumentation.md` 的 front matter 也写 `lesson: 19` |
| 2 | 讲义说"two tools, one MCP round-trip"，代码是 3 次工具 + 3 次 MCP 调用 | 9 个 span 而不是 6 个 |
| 3 | 讲义说"Paste the output into an OTLP-compatible viewer"，但打印的是**摘要**：trace id 截成 8 位、span id 截成 6 位、`attributes` 是扁平字典（OTLP JSON 中属性是 `{"key": ..., "value": {"stringValue": ...}}` 列表）、`kind` 是字符串 | 不能直接导入任何 OTLP 查看器；`Span.to_otlp()` 定义了但从未被调用，而且它同样不是真正的 OTLP 结构 |
| 4 | 讲义提到 `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` 与"specific content-capture env vars"，代码用的是自定义的 `OTEL_CAPTURE_CONTENT=1` | 而且必须恰好等于 `"1"`，设为 `true` 不会开启（已实测） |
| 5 | `traceparent` 只被写成 `mcp.call` span 的**属性**，并没有放进任何请求 | 真正的传播没有发生（讲义练习 4）；该属性名也没有 `gen_ai.` 或厂商前缀，违反了本节技能文件自己的"Hard rejects" |
| 6 | 打印时 `{k: v for k, v in span.attrs.items() if k.startswith("gen_ai")}` 只保留 `gen_ai.*` | `mcp.server`、`mcp.transport`、`net.peer.name`、`traceparent` 都看不到 |
| 7 | 层级图里的 `subagent.invoke` 未实现；讲义列出的 3 个指标也都没有实现 | 演示只覆盖一半 |
| 8 | 关键术语表把 OTLP 写成 "OpenTelemetry Line Protocol" | OTLP 是 OpenTelemetry Protocol 的缩写 |

### Q10 — 参考答案

```python
import re, time

TP = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")

def build_mcp_request(client_span, tool, args, req_id=1):
    return {"jsonrpc": "2.0", "id": req_id, "method": "tools/call",
            "params": {"name": tool, "arguments": args,
                       "_meta": {"traceparent": f"00-{client_span.trace_id}-{client_span.span_id}-01"}}}

def server_handle(request):
    tp = request.get("params", {}).get("_meta", {}).get("traceparent", "")
    mt = TP.match(tp)
    if mt:   # 继续上游 trace：同一 trace id，父 = 客户端 CLIENT span
        span = Span(name="mcp.server tools/call", kind="SERVER", trace_id=mt.group(1),
                    span_id=_hex(8), parent_span_id=mt.group(2), start_ns=time.time_ns())
        SPANS.append(span)
    else:    # 缺失或非法：开启新 trace，不要报错拒绝业务请求
        span = start_span("mcp.server tools/call", "SERVER")
    # ... 执行工具 ...
    span.finish()
    return span
```

已实际运行验证：服务端 span 的 trace id 等于根 span 的 trace id，父 id 等于 `mcp.call` 的 span id，输出 `True True`；传入 `"garbage"` 时开启了新 trace、父 id 为 `None`。

要点：
- 格式不合法时**忽略**而不是拒绝请求——追踪是旁路能力，不能影响业务；W3C 规范也要求全零 trace id / parent id 视为无效。
- 服务端只信任格式，不信任内容：`traceparent` 来自调用方，不能用它做任何授权判断。
- 若走 Streamable HTTP，就放在 HTTP 头里，用 OTel SDK 的 propagator 注入/提取，不要手拼。

### Q11 — 参考答案

```python
BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1, 2.5, 5, 7.5, 10]

class Histogram:
    def __init__(self, name, unit, bounds):
        self.name, self.unit, self.bounds = name, unit, bounds
        self.counts = [0] * (len(bounds) + 1)          # 最后一个是 +Inf 桶
        self.sum, self.count = 0.0, 0

    def record(self, value, attrs=None):
        i = next((i for i, b in enumerate(self.bounds) if value <= b), len(self.bounds))
        self.counts[i] += 1
        self.sum += value
        self.count += 1

tool_duration = Histogram("gen_ai.tool.execution.duration", "s", BUCKETS)
# 在 tool.execute span 结束后：
tool_duration.record((span.end_ns - span.start_ns) / 1e9, {"gen_ai.tool.name": "get_weather"})
```

实际运行：3 个样本，总和约 0.211 秒，全部落在 `(0.05, 0.075]` 桶（边界 0.075）。原因：每个 `tool.execute` 包含 `fake_tool_execute` 的 `sleep(0.03)` 和其内部 `fake_mcp_call` 的 `sleep(0.04)`，约 70 ms。

要点：直方图只存桶计数、总和、总数，不存每个样本，所以能廉价地计算近似分位数；属性（如 `gen_ai.tool.name`）构成维度，不要把高基数的值（call id、用户 id）放进指标属性，否则时间序列数量爆炸。

### Q12 — 参考答案

1. 已实测：异常抛出后 `SPANS` 为 `[('agent.invoke_agent', 0), ('llm.chat', <正常时间戳>), ('tool.execute', 0)]`——根 span 和工具 span 的 `end_ns` 停留在默认值 0，而 `mcp.call` 根本没有创建。导出后时长为负的天文数字（`0 - start_ns`），而且没有任何错误标记；**恰恰是最需要排查的那次失败调用最难看清**。另外 `SPANS` 是全局列表，父子关系靠手动传 `parent=`，容易传错。

2. 参考实现（已运行验证：两个 span 都正常结束、都带 `error.type=TimeoutError`、子 span 的父是根）：

```python
import contextvars
from contextlib import contextmanager

_current = contextvars.ContextVar("current_span", default=None)

@contextmanager
def span(name, kind="INTERNAL", **attrs):
    s = start_span(name, kind, parent=_current.get(), attrs=dict(attrs))
    token = _current.set(s)                 # 进入时成为"当前 span"
    try:
        yield s
    except Exception as e:
        s.attrs["error.type"] = type(e).__name__
        s.status = "ERROR"                  # 真实 SDK 中是 span.set_status(StatusCode.ERROR)
        raise                               # 记录后继续抛出，不吞异常
    finally:
        s.finish()                          # 无论成功失败都结束
        _current.reset(token)               # 恢复上一层的当前 span

with span("agent.invoke_agent", **{"gen_ai.operation.name": "invoke_agent"}):
    with span("tool.execute", **{"gen_ai.operation.name": "execute_tool"}):
        ...
```

`contextvars` 在线程和 `asyncio` 任务之间各自隔离，适合并发的 agent；OTel 官方 SDK 的 `tracer.start_as_current_span()` 就是这个模式。

### Q13 — 参考回答要点

- **trace**：一次端到端请求，所有 span 共享一个 trace id。
- **span**：一段带开始/结束时间的工作，有 span id 和父 span id，构成树。
- **SpanKind**：CLIENT（发起跨进程调用）、SERVER（处理入站请求）、INTERNAL（进程内步骤），另有 PRODUCER/CONSUMER 用于消息队列。
- **attribute**：键值对，描述这段工作（模型、token、工具名）；**event**：span 内带时间戳的事件（如内容捕获的 prompt/completion）。
- **本例的 span**：
  - `agent.invoke_agent`（INTERNAL）：`gen_ai.operation.name=invoke_agent`、`gen_ai.agent.name/id`；
  - `llm.chat`（CLIENT）：`operation.name=chat`、`provider.name`、`request.model`、`response.model`、`response.id`、`usage.input_tokens/output_tokens`；
  - `tool.execute`（INTERNAL）：`operation.name=execute_tool`、`tool.name`、`tool.call.id`；
  - `mcp.call`（CLIENT）：同样的工具信息，加传输/服务端标识，并注入 `traceparent`。
- 加分点：`gen_ai.tool.call.id` 与 LLM 返回的 tool call id 对应，可以把"模型决定调用"与"实际执行"关联起来。

### Q14 — 参考回答要点

- **进程内**：当前 span 保存在上下文中（Python 用 `contextvars`），新 span 自动以它为父；线程池、`asyncio` 任务需要正确复制上下文。
- **跨进程**：用 propagator 把上下文序列化成 W3C `traceparent`（以及可选的 `tracestate`、`baggage`）注入请求，服务端提取后以它为父创建 SERVER span。
- **MCP Streamable HTTP**：标准 HTTP 头即可，OTel 的 HTTP instrumentation 能自动注入。
- **MCP stdio**：没有 HTTP 头，讲义建议在 JSON-RPC 的 `_meta.traceparent` 中携带；讲义提到 2026 路线图在讨论把它标准化，在此之前需要手工注入，服务端手工提取。
- **A2A / 子 agent**：同样要把上下文放进请求，否则子 agent 的 trace 会断开成孤立的树。
- 常见误区：只在进程启动时用环境变量传一次 trace id——这只能关联到"那次启动"，无法区分每次调用。

### Q15 — 参考回答要点

- **默认关闭**：讲义与技能文件都要求默认不捕获内容；技能文件："If the user asks to capture content for debugging prod, refuse without a typed consent policy and PII redaction pipeline."
- **分级开启**：开发/预发环境可开；生产只对特定租户、特定比例的请求、限定时间窗口开启。
- **脱敏管道**：在导出前（SDK processor 或 Collector 中）做 PII 识别与掩码；本节代码 `prompt[:200]` 只是截断，不是脱敏。
- **存储隔离**：内容事件与普通 trace 分开存储，设置更短的保留期和更严格的访问控制。
- **用户同意与合规**：有明确的数据处理依据，支持按用户删除。
- **替代方案**：多数排障只需要时序、token 数、模型版本、错误类型；需要内容时优先记录 hash 或长度。
- 加分点：注意工具参数和工具结果同样可能含敏感数据（如本例的城市、实际业务中的邮件正文）。

### Q16 — 参考回答要点

- **先有完整 trace**：agent → LLM → tool → MCP 全链路 span，且 MCP 调用带 `traceparent`，服务端 span 能接上。
- **从慢请求入手**：按根 span 时长筛出 30 秒的 trace，看瀑布图（waterfall）：哪个子 span 占了绝大部分时间——这里会是某个 `mcp.call`。
- **比较快慢两类 trace**：慢 trace 中该 MCP server 的 SERVER span 是否缺失或开始得很晚（说明时间耗在连接/进程启动上，而不是工具逻辑）；按 `mcp.server` 维度聚合。
- **指标看板**：`gen_ai.tool.execution.duration` 与 `gen_ai.client.operation.duration` 的 p50/p95/p99，按工具名、服务端分组；冷启动表现为长尾（p99 远大于 p50），且常与"距上次调用的间隔"相关。
- **告警**：技能文件建议以 p95 `gen_ai.client.operation.duration` 作为首要告警指标；再对单个工具的 p99 设阈值。
- **修复验证**：预热、常驻进程、超时与重试，修复后对比直方图。
- 加分点：采样策略要保证慢请求被保留（尾部采样 / 基于延迟的采样），否则恰好丢掉要找的那条 trace。

### Q17 — 参考回答要点

- **语义约定的价值**：讲义："define stable attribute names so Datadog, Langfuse, Phoenix, OpenLLMetry, and AgentOps all parse the same spans. Instrument once; ship to any backend." 自定义属性名只能在自家看板使用，换后端就要改代码或写映射。
- **可组合**：框架自动埋点（技能文件建议优先用框架的 OTel hook）与手工埋点产生的 span 能拼在同一个 trace 中。
- **演进中的约定**：讲义提到用 `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` 选择采用最新的实验性约定；工程上要固定 SDK / instrumentation 版本、在 Collector 中做属性重命名（transform processor）以兼容新旧名称、看板查询同时兼容两种名称一段过渡期。
- **自定义属性**：确需自定义时加明确的厂商/组织前缀（技能文件的硬拒绝项之一），避免将来与官方名称冲突。
- 常见误区：以为 OTLP 本身规定了 `gen_ai.*` 的含义——OTLP 只是传输格式，属性语义来自 semantic conventions。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 07 构建 MCP 服务端：无状态 Python 与 TypeScript](../../07-building-an-mcp-server/docs/zh.md)：理解被追踪的服务端在哪里接收请求。
- [阶段 13 · 08 构建 MCP 客户端：发现、路由与新旧协议兼容回退](../../08-building-an-mcp-client/docs/zh.md)：客户端 dispatch 是 `mcp.call` span 的来源。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：两种传输决定了 `traceparent` 的携带方式。
- [阶段 13 · 19 A2A：Agent 与 Agent 之间的通信协议](../../19-a2a-protocol/docs/zh.md)：子 agent 调用也需要传播上下文。

### 本节被哪些后续内容用到
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../../14-agent-engineering/23-otel-genai-conventions/docs/zh.md)：从 agent 工程角度深入语义约定。
- [阶段 14 · 24 Agent 可观测性：Langfuse、Phoenix、Opik](../../../14-agent-engineering/24-agent-observability-platforms/docs/zh.md)：把本节的 span 发往具体平台。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：生产可观测性架构。
- [阶段 19 · 28 通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability](../../../19-capstone-projects/28-observability-otel-traces/docs/zh.md)：综合项目中的完整实现。
- [阶段 19 · 11 LLM Observability 与评估仪表盘](../../../19-capstone-projects/11-llm-observability-dashboard/docs/zh.md)：看板与评估结合。

### 延伸关键词
`OpenTelemetry` · `GenAI semantic conventions` · `gen_ai.*` · `SpanKind` · `W3C Trace Context` · `traceparent / tracestate / baggage` · `OTLP` · `OTel Collector` · `span events` · `histogram buckets` · `tail-based sampling` · `contextvars` · `PII redaction`
