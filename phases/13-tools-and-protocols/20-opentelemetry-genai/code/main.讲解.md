# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 20 节 OpenTelemetry GenAI：端到端追踪 Tool Calls ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`；开启内容捕获：`OTEL_CAPTURE_CONTENT=1 python3 code/main.py` ｜ **依赖**：纯标准库（`json`、`os`、`random`、`time`、`uuid`、`dataclasses`），不需要安装 OpenTelemetry SDK、不连接任何 Collector

---

## 1. 这份代码在考察什么

这份代码不依赖 OTel SDK，自己实现了一个最小的"span 发射器"，模拟一个 agent 的一次运行：

1. **span 树**：根 `agent.invoke_agent` → 两次 `llm.chat` 与三次 `tool.execute` → 每个工具下一次 `mcp.call`，全部共享一个 trace id，父子关系由 `parent_span_id` 表达。
2. **SpanKind**：跨进程的 LLM 调用与 MCP 调用是 CLIENT，agent 循环与工具执行是 INTERNAL。
3. **GenAI 语义约定属性**：`gen_ai.operation.name`、`gen_ai.provider.name`、`gen_ai.request.model` / `response.model`、`gen_ai.usage.*`、`gen_ai.tool.name`、`gen_ai.tool.call.id`、`gen_ai.agent.*`。
4. **内容捕获默认关闭**：只有设置环境变量时才以 span event 记录 prompt / completion。
5. **W3C `traceparent` 的构造**：为 MCP 调用拼出 `00-<trace>-<span>-01`。

> 一句话：**让你看清"一次 agent 运行"被拆成哪些 span、每个 span 该带哪些标准属性**。它是教学用的形状演示：输出不是真正的 OTLP、`traceparent` 没有真正发送、异常路径不安全——这些都在测验 Q9–Q12 中展开。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CAPTURE_CONTENT` | 模块常量 | 读环境变量 `OTEL_CAPTURE_CONTENT`，决定是否记录内容 | opt-in 内容捕获 |
| `_hex(n_bytes)` | 函数 | 由 uuid4 截取 `2n` 个十六进制字符作 id | trace id / span id |
| `Span` | dataclass | 名称、kind、trace/span/父 id、起止纳秒、属性、事件；`finish`、`add_event`、`to_otlp` | span |
| `SPANS` | 全局列表 | 收集所有 span（按**开始**顺序） | 内存中的 exporter |
| `start_span` | 函数 | 继承父 span 的 trace id，生成新 span id 并登记 | 上下文传递（显式） |
| `fake_llm_call` | 函数 | 睡 50 ms，填响应 id、模型、token 数；可选内容事件 | LLM span |
| `fake_tool_execute` | 函数 | 睡 30 ms，填工具名与 call id | tool span |
| `fake_mcp_call` | 函数 | 建 CLIENT 子 span，拼 `traceparent`，睡 40 ms | MCP 调用与传播 |
| `agent_loop` | 函数 | 编排整棵 span 树 | agent 运行 |
| `main` | 函数 | 打印 banner、运行、逐行输出 span 摘要 | 输出 |

数据流：`main` → `agent_loop`：建根 span → `llm.chat` → 循环三个城市（`tool.execute` → `fake_tool_execute` → `fake_mcp_call` 建 `mcp.call`）→ 第二个 `llm.chat` → 结束根 span → `main` 遍历 `SPANS` 打印摘要。

---

## 3. 逐段精讲

### 3.1 内容捕获开关与 id 生成

```python
CAPTURE_CONTENT = os.environ.get("OTEL_CAPTURE_CONTENT", "0") == "1"

def _hex(n_bytes: int) -> str:
    return uuid.uuid4().hex[: n_bytes * 2]
```

- 开关在**导入模块时**就读取一次；运行中修改环境变量不起作用。只有值恰好为 `"1"` 才开启，`true`、`yes` 都不行（已实测 `OTEL_CAPTURE_CONTENT=true` 仍显示 off）。
- ⚠️ `OTEL_CAPTURE_CONTENT` 是本课自定义的变量名。讲义提到的是 `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` 加"specific content-capture env vars"——真实 instrumentation 库各有自己的变量名，以所用库的文档为准。
- `_hex(16)` = uuid4 的 32 个十六进制字符（trace id 需要 16 字节），`_hex(8)` = 前 16 个字符（span id 需要 8 字节）。
- 小瑕疵：uuid4 的第 13 个十六进制字符固定是版本号 `4`，第 17 个只能是 `8/9/a/b`（已实测）。所以本代码所有 span id 的第 13 位都是 `4`，随机性略低于 64 位。生产用 OTel SDK 的 id 生成器，或 `secrets.token_hex(n)`。
- `_hex(n)` 在 `n > 16` 时会被静默截断到 32 个字符——切片不会报错。

### 3.2 `Span` 数据类

```python
@dataclass
class Span:
    name: str
    kind: str  # INTERNAL / CLIENT / SERVER
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    start_ns: int = 0
    end_ns: int = 0
    attrs: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)

    def finish(self) -> None:
        self.end_ns = time.time_ns()

    def add_event(self, name: str, attrs: dict) -> None:
        self.events.append({"time": time.time_ns(), "name": name, "attrs": attrs})
```

- 一个 span 的核心字段与 OTel 数据模型一致：名称、kind、trace id、span id、父 span id、起止时间（Unix 纳秒）、属性、事件。
- 根 span 的 `parent_span_id` 是 `None`。
- `time.time_ns()` 返回整数纳秒，避免浮点误差；OTLP 的时间字段也是纳秒。注意它是"墙上时钟"，系统时间被调整时时长可能出错，测量时长更稳妥的是 `time.perf_counter_ns()`（OTel SDK 会处理这个问题）。
- 缺少的字段：**状态**（OK / ERROR）、`error.type`、links、resource（`service.name` 等）。
- `to_otlp()` 把字段改成 OTLP 风格的驼峰名，但**从未被调用**；而且属性仍是扁平字典、kind 是字符串，与真正的 OTLP JSON（属性为 `{"key", "value": {"stringValue": ...}}` 列表、kind 为枚举）不同。

### 3.3 `start_span`：显式传父

```python
SPANS: list[Span] = []

def start_span(name: str, kind: str, parent: Span | None = None,
               attrs: dict | None = None) -> Span:
    trace_id = parent.trace_id if parent else _hex(16)
    span = Span(name=name, kind=kind, trace_id=trace_id, span_id=_hex(8),
                parent_span_id=parent.span_id if parent else None,
                start_ns=time.time_ns(), attrs=attrs or {})
    SPANS.append(span)
    return span
```

- 有父就继承父的 trace id，没有父就开新 trace——这就是"整棵树共享一个 trace id"的来源。
- 每个 span 都有新的 span id，父 id 指向调用者。
- `attrs or {}`：调用方没传属性时给一个新字典（不能用 `attrs: dict = {}` 作默认参数，否则所有调用共享同一个字典）。
- span 在**开始时**就加入 `SPANS`，所以输出顺序是开始顺序：根、llm、tool、mcp、tool、mcp……
- 父子关系靠每次手动传 `parent=`，容易传错；OTel SDK 用"当前上下文"自动确定父 span（测验 Q12 用 `contextvars` 实现了这一点）。

### 3.4 三个 fake 函数

```python
def fake_llm_call(span: Span, prompt: str) -> str:
    time.sleep(0.05)
    resp_id = f"resp_{uuid.uuid4().hex[:8]}"
    span.attrs.update({
        "gen_ai.response.id": resp_id,
        "gen_ai.response.model": "gpt-4o-2024-08-06",
        "gen_ai.usage.input_tokens": len(prompt) // 4,
        "gen_ai.usage.output_tokens": random.randint(20, 80),
    })
    if CAPTURE_CONTENT:
        span.add_event("gen_ai.content.prompt", {"content": prompt[:200]})
        span.add_event("gen_ai.content.completion", {"content": "sample completion"})
    return "sample completion"
```

- 请求类属性（`operation.name`、`provider.name`、`request.model`）在建 span 时填；响应类属性（`response.id`、`response.model`、`usage.*`）在拿到结果后补——这是真实埋点的通常顺序，因为响应信息只有在调用后才知道。
- `request.model` 是 `"gpt-4o"`，`response.model` 是 `"gpt-4o-2024-08-06"`，演示"别名 vs 实际快照"。
- `len(prompt) // 4`：按"约 4 个字符一个 token"粗估。两个 prompt 长 34 和 32，结果都是 8。`output_tokens` 是 20–80 的随机数。真实值应取自提供方响应的 usage 字段。
- 内容事件只截断到 200 个字符——截断不等于脱敏，仍可能含 PII。

```python
def fake_tool_execute(span: Span, tool: str, args: dict) -> dict:
    time.sleep(0.03)
    span.attrs.update({
        "gen_ai.tool.name": tool,
        "gen_ai.tool.call.id": f"call_{uuid.uuid4().hex[:8]}",
    })
    return {"content": [{"type": "text", "text": f"{tool} ran with {args}"}]}
```

- 工具 span 带 `gen_ai.tool.name` 与 `gen_ai.tool.call.id`。真实场景中 call id 应来自 LLM 返回的 tool call id，这样才能把"模型决定调用"与"实际执行"关联起来；这里是随机生成的。
- 返回值是 MCP 风格的 `content` 列表，但 `agent_loop` 没有使用它。
- 工具参数（城市名）没有写进 span——参数也属于可能敏感的内容。

```python
def fake_mcp_call(parent: Span, tool: str) -> dict:
    mcp_span = start_span("mcp.call", "CLIENT", parent=parent, attrs={
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": tool,
        "mcp.server": "notes",
        "mcp.transport": "stdio",
        "net.peer.name": "child_process",
    })
    traceparent = f"00-{mcp_span.trace_id}-{mcp_span.span_id}-01"
    mcp_span.attrs["traceparent"] = traceparent
    time.sleep(0.04)
    mcp_span.finish()
    return {"tool": tool, "result": "ok"}
```

- `traceparent` 的格式正确：版本 `00`、32 位 trace id、16 位 span id（用的是**这个 CLIENT span** 的 id，服务端会把它当父）、标志 `01`（已采样）。
- ⚠️ 但它只被存成了一个 span 属性，**没有任何请求把它带出去**——讲义说 stdio 下要放进 JSON-RPC 的 `_meta.traceparent`，这正是练习 4（测验 Q10 给出实现）。
- 属性 `traceparent` 没有任何前缀，违反了本节技能文件的"Hard rejects: emits arbitrary custom attributes without the `gen_ai.` or explicit vendor prefix"。`mcp.server`、`mcp.transport` 可以视为带 `mcp.` 前缀。
- `mcp.server: "notes"` 与工具 `get_weather` 并不搭配，只是占位值。
- 函数自己 `finish()` 了 `mcp_span`，但 `tool.execute` 由调用方结束——谁开谁关的约定不统一。

### 3.5 `agent_loop`：编排 span 树

```python
    root = start_span("agent.invoke_agent", "INTERNAL", attrs={
        "gen_ai.operation.name": "invoke_agent",
        "gen_ai.agent.name": "research-agent",
        "gen_ai.agent.id": "agent_42",
    })
    llm1 = start_span("llm.chat", "CLIENT", parent=root, attrs={...})
    fake_llm_call(llm1, "user wants weather in three cities")
    llm1.finish()

    for city in ("Bengaluru", "Tokyo", "Zurich"):
        tool_span = start_span("tool.execute", "INTERNAL", parent=root, attrs={
            "gen_ai.operation.name": "execute_tool",
        })
        fake_tool_execute(tool_span, "get_weather", {"city": city})
        fake_mcp_call(tool_span, "get_weather")
        tool_span.finish()
    ...
    root.finish()
```

最终的树（9 个 span）：

```text
agent.invoke_agent (INTERNAL)                 ≈ 310 ms
├── llm.chat (CLIENT)                         ≈ 50 ms
├── tool.execute (INTERNAL)  Bengaluru        ≈ 70 ms
│   └── mcp.call (CLIENT)                     ≈ 40 ms
├── tool.execute (INTERNAL)  Tokyo            ≈ 70 ms
│   └── mcp.call (CLIENT)                     ≈ 40 ms
├── tool.execute (INTERNAL)  Zurich           ≈ 70 ms
│   └── mcp.call (CLIENT)                     ≈ 40 ms
└── llm.chat (CLIENT)                         ≈ 50 ms
```

- 根 span 时长 ≈ 50 + 3 × 70 + 50 = 310 ms，与实测 311.59 ms 一致；三次工具调用是**串行**的，瀑布图上一目了然——这正是"用 trace 找优化点"的典型场景（并行化可以省掉约 140 ms）。
- ⚠️ 与讲义的出入：讲义 Use It 说"dispatches two tools, and makes one MCP round-trip"，代码是 3 + 3；层级图中的 `subagent.invoke` 没有实现。
- ⚠️ 没有任何异常处理：中途抛异常时已开始的 span 永远不会 `finish()`，`end_ns` 停在 0（测验 Q12 实测）。

### 3.6 `main`：摘要输出

```python
    for span in SPANS:
        summary = {
            "name": span.name,
            "kind": span.kind,
            "trace": span.trace_id[:8] + "...",
            "id": span.span_id[:6] + "...",
            "parent": (span.parent_span_id or "ROOT")[:6],
            "duration_ms": round((span.end_ns - span.start_ns) / 1_000_000, 2),
            "attrs": {k: v for k, v in span.attrs.items() if k.startswith("gen_ai")},
            "events": len(span.events),
        }
        print(json.dumps(summary))
```

- `(span.parent_span_id or "ROOT")[:6]`：父 id 为 `None` 时显示 `ROOT`；`or` 返回第一个真值。
- 纳秒 → 毫秒：除以 `1_000_000`（数字中的下划线只是分隔符）。
- 字典推导式只保留 `gen_ai` 开头的属性，所以 `mcp.*`、`net.peer.name`、`traceparent` 不会出现在输出中。
- 事件只打印个数，不打印内容。
- ⚠️ 讲义说可以把输出"Paste into an OTLP-compatible viewer"，但这里打印的是截断过的摘要，做不到。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不用 OTel SDK，自写 `Span` | 只用标准库，结构透明 | 没有 exporter、采样、批处理、资源属性；生产用 `opentelemetry-sdk` + OTLP exporter |
| 显式传 `parent` | 一眼看清父子关系 | 易传错，并发时更难；SDK 用上下文自动传播 |
| 全局 `SPANS` 列表 | 最简单的"导出" | 无界增长、非线程安全；生产用批处理 span processor |
| 输出摘要而非 OTLP | 终端易读 | 不能导入查看器；生产由 exporter 序列化为 OTLP protobuf/JSON |
| 自定义环境变量开关内容 | 演示 opt-in | 名称非标准、只认 `"1"`；生产遵循所用 instrumentation 的配置 |
| `traceparent` 记为属性 | 展示格式 | 没有真正传播；应注入 `_meta` 或 HTTP 头 |
| token 数按字符粗估 | 无需真实 LLM | 数值不可信；取提供方 usage |
| 无 try/finally | 代码短 | 异常时 span 不结束、无错误标记；用上下文管理器 |
| 不实现指标 | 聚焦 span | 看板需自行聚合；生产同时发 `gen_ai.*` 直方图 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `os.environ.get(k, default)` | `os.environ.get("OTEL_CAPTURE_CONTENT", "0")` | 读环境变量，缺失时给默认值 |
| 模块级常量 | `CAPTURE_CONTENT = ... == "1"` | 导入时求值一次 |
| `@dataclass` + `field(default_factory=...)` | `attrs: dict = field(default_factory=dict)` | 每个实例独立的可变默认值 |
| `X \| None` 注解 | `parent_span_id: str \| None = None` | 可选值（配合 `from __future__ import annotations`） |
| 条件表达式 | `parent.trace_id if parent else _hex(16)` | 一行 if/else |
| `or` 取默认 | `attrs or {}`、`span.parent_span_id or "ROOT"` | 左侧为假值时取右侧 |
| 字符串切片 | `uuid.uuid4().hex[: n_bytes * 2]`、`trace_id[:8]` | 取前 n 个字符 |
| `dict.update` | `span.attrs.update({...})` | 批量写入键值 |
| 整除 `//` | `len(prompt) // 4` | 向下取整的除法 |
| `random.randint(a, b)` | `random.randint(20, 80)` | 闭区间随机整数 |
| `time.time_ns()` / `time.sleep` | 记录时间戳、模拟耗时 | 纳秒整数；暂停秒数（浮点） |
| 数字下划线 | `1_000_000` | 提高可读性 |
| `round(x, 2)` | `duration_ms` | 保留两位小数 |
| 字典推导式 + `startswith` | `{k: v for k, v in span.attrs.items() if k.startswith("gen_ai")}` | 按前缀过滤 |
| f-string 条件表达式 | `{'ON' if CAPTURE_CONTENT else 'off (...)'}` | 花括号内可以写表达式 |
| 元组迭代 | `for city in ("Bengaluru", "Tokyo", "Zurich")` | 不可变序列 |
| `json.dumps` | `print(json.dumps(summary))` | 每个 span 一行 JSON（类似 JSON Lines） |
| `if __name__ == "__main__":` | 文件末尾 | 被导入时不执行 |

---

## 6. 运行结果解读

实际运行 `python3 code/main.py`（id、时长、`output_tokens` 每次不同；为便于阅读，下面截断了部分字段）：

```text
========================================================================
PHASE 13 LESSON 19 - OTEL GENAI SPAN EMITTER          ← 笔误，应为 20
  content capture : off (set OTEL_CAPTURE_CONTENT=1)
========================================================================

emitted 9 spans across 1 trace

{"name": "agent.invoke_agent", "kind": "INTERNAL", "trace": "56f5a368...", "id": "922bcb...", "parent": "ROOT",   "duration_ms": 311.59, "attrs": {"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "research-agent", "gen_ai.agent.id": "agent_42"}, "events": 0}
{"name": "llm.chat",  "kind": "CLIENT",   ..., "parent": "922bcb", "duration_ms": 50.27, "attrs": {..., "gen_ai.request.model": "gpt-4o", "gen_ai.response.model": "gpt-4o-2024-08-06", "gen_ai.usage.input_tokens": 8, "gen_ai.usage.output_tokens": 39}, "events": 0}
{"name": "tool.execute", "kind": "INTERNAL", ..., "id": "d0eaeb...", "parent": "922bcb", "duration_ms": 70.29, "attrs": {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "get_weather", "gen_ai.tool.call.id": "call_5c1746e3"}, "events": 0}
{"name": "mcp.call",  "kind": "CLIENT",   ..., "parent": "d0eaeb", "duration_ms": 40.11, "attrs": {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": "get_weather"}, "events": 0}
... (另外两组 tool.execute / mcp.call)
{"name": "llm.chat",  "kind": "CLIENT",   ..., "parent": "922bcb", "duration_ms": 50.19, ..., "gen_ai.usage.input_tokens": 8, "gen_ai.usage.output_tokens": 26}, "events": 0}
```

逐项解读：

- **9 个 span、1 个 trace**：所有行的 `trace` 前缀相同（`56f5a368...`）。
- **父子关系**：两个 `llm.chat` 与三个 `tool.execute` 的 `parent` 都是根的 id 前缀 `922bcb`；每个 `mcp.call` 的 `parent` 是它上面那个 `tool.execute` 的 id（如 `d0eaeb`）。
- **时长**：`llm.chat` ≈ 50 ms、`mcp.call` ≈ 40 ms、`tool.execute` ≈ 70 ms（包含其子 `mcp.call`），根 ≈ 311 ms。父 span 时长包含子 span，这是阅读瀑布图的基本规则。
- **`mcp.call` 的属性**只显示了两个 `gen_ai.*` 键，`traceparent` 等被打印过滤器隐藏。
- **`events: 0`**：默认不捕获内容。用 `OTEL_CAPTURE_CONTENT=1` 运行时 banner 显示 `ON`，两个 `llm.chat` 行变为 `"events": 2`（prompt 与 completion 各一个），其余 span 仍为 0（已实测）。

---

## 7. 动手改一改

1. **（练习 1）** 数出 CLIENT 与 INTERNAL 各几个（答案：CLIENT 5 个、INTERNAL 4 个）；修正 banner 为 `LESSON 20`。
2. **（练习 2）** 开启内容捕获，打印 `llm.chat` 的事件内容；再加一个最小的"脱敏"函数，把邮箱、手机号替换为 `<redacted>` 后才写入事件。
3. **（练习 3）** 实现 `gen_ai.tool.execution.duration` 直方图（测验 Q11），以工具名为维度；顺便实现 `gen_ai.client.operation.duration`。
4. **（练习 4）** 构造 JSON-RPC 请求并把 `traceparent` 放进 `params._meta`，写服务端解析并创建 SERVER span（测验 Q10）。
5. **（健壮性）** 用 `contextvars` + 上下文管理器重写所有埋点（测验 Q12），让 `fake_tool_execute` 随机抛 `TimeoutError`，确认 span 都能结束并带 `error.type`。
6. **（进阶）** `pip install opentelemetry-sdk` 后，用 `TracerProvider` + `ConsoleSpanExporter` 重写 `agent_loop`，把同样的 `gen_ai.*` 属性写进真实 span；对比输出格式与本节自写版本的差异（属性结构、kind 枚举、resource）。

---

## 8. 常见坑

- **父 span id 填错**：`traceparent` 的第三段应是发起调用的 CLIENT span，而不是根 span。
- **每次远程调用换 trace id**：trace id 必须在整条链路上不变。
- **只记录不传播**：把 `traceparent` 写进属性不等于传播，必须放进请求（`_meta` 或 HTTP 头）。
- **异常时 span 不结束**：手动 `finish()` 的代码遇到异常就会泄漏未结束的 span；用 `with` 或 `try/finally`。
- **默认开启内容捕获**：prompt、completion、工具参数都可能含 PII；截断不等于脱敏。
- **高基数属性放进指标**：call id、用户 id 作为指标维度会导致时间序列爆炸；它们只适合放在 span 上。
- **把摘要当 OTLP**：本节输出不能直接导入查看器。
- **自定义属性不带前缀**：如 `traceparent`、`latency`，将来可能与官方约定冲突，后端也无法通用解析。
- **用墙上时钟测时长**：`time.time_ns()` 受系统时间调整影响；测时长用单调时钟。
