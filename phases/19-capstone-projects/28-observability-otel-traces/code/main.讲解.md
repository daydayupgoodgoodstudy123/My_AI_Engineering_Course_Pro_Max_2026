# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 28 节 通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下）或 `cd code && python3 main.py`；测试：`python3 -m pytest code/tests/ -v` ｜ **依赖**：仅标准库（`json`、`math`、`os`、`tempfile`、`time`、`uuid`、`contextlib`、`dataclasses`、`typing`），无需网络、无需 opentelemetry-sdk

---

## 1. 这份代码在考察什么

这份代码用约 500 行标准库 Python 手写了一个"迷你 OpenTelemetry"，让 agent harness 的每一步都留下可解析的结构化记录：

1. **span 的数据形状**：`trace_id` / `span_id` / `parent_span_id` / name / kind / 起止纳秒时间 / attributes / events / status——这就是 OTel 的 span 模型。
2. **GenAI 语义约定**：用 `gen_ai.*` 标准 key 记录模型调用（provider、model、token 用量、response id）与工具调用（tool name、call id）。
3. **context manager 计时与异常记录**：`with builder.span(...)` 自动记开始/结束时间，异常时设 `ERROR`、追加 `exception` event 并重新抛出。
4. **JSONL 导出**：每行一个 span，便于流式写入、grep 和逐行 `json.loads` 回读。
5. **Prometheus 指标**：带 label 的 counter 与 histogram，并按 Prometheus 文本格式（exposition format）输出 `_bucket{le=...}`、`_sum`、`_count`。
6. **trace 与 metric 联动**：工具 span 结束时自动更新 `tools_called_total` 与 `tool_latency_ms`。

> 一句话：**把"一次 agent 调用里发生了什么"变成标准化的 span 树，把"整体表现如何"变成可聚合的 Prometheus 时间序列**。同时要注意它和讲义有几处不一致（ID 生成、exporter 是否会抛异常、缺失的装饰器、临时文件未清理），这些都在下文标出。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GEN_AI_*` / `HARNESS_*` / `STATUS_*` | 模块常量 | 语义约定 attribute key 与状态码 | OTel GenAI semconv |
| `SpanEvent` | dataclass | span 内的离散事件（名字、时间戳、attributes） | OTel span event |
| `GenAISpan` | dataclass | 一个 span 的全部字段；`duration_ms` 属性；`to_dict` 序列化 | OTel span |
| `new_trace_id` / `new_span_id` / `now_unix_nano` | 函数 | 生成 32/16 位十六进制 ID；纳秒时间戳 | W3C Trace Context |
| `JSONLExporter` | dataclass | 追加写文件，一行一个 span，每次 `flush` | 离线版 OTLP exporter |
| `InMemoryExporter` | 类 | 把 span 存在列表里，供测试与 demo 打印 | 测试替身 |
| `_label_key` / `_format_labels` | 函数 | label 字典 → 可哈希的有序元组；→ `{k="v",...}` 字符串（含转义） | Prometheus label |
| `Counter` | dataclass | 每个 label 组合一个累计值 | Prometheus counter |
| `Histogram` | dataclass | 存原始样本，按需计算累积桶、总数、总和 | Prometheus histogram |
| `MetricsRegistry` | dataclass | 按名字管理 counter/histogram（get-or-create） | metric registry |
| `prometheus_exposition` / `_format_le` | 函数 | 渲染文本格式 | exposition format |
| `SpanBuilder` | dataclass | 持有一个 trace_id；`span()` context manager 负责计时、状态、导出、更新 metric | Tracer |
| `run_demo` | 函数 | 合成一次 agent 回合（chat 包两个工具调用）+ 一次被拒绝的工具调用 | 演示 |

数据流：`run_demo` → `SpanBuilder.span()` 创建 `GenAISpan` → 业务代码在 `with` 块内补 attributes/events → 退出时 `finally` → 各 exporter（`JSONLExporter` 写 `traces.jsonl`、`InMemoryExporter` 存列表）→ 若带 `gen_ai.tool.name` 则更新 `MetricsRegistry` → `prometheus_exposition` 打印文本 → 回读 JSONL 校验。

---

## 3. 逐段精讲

### 3.1 语义约定常量

```python
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
...
GEN_AI_TOOL_NAME = "gen_ai.tool.name"
GEN_AI_TOOL_CALL_ID = "gen_ai.tool.call.id"
GEN_AI_TOOL_RESULT_BYTES = "gen_ai.tool.result.bytes"

# Harness-specific attributes (under a non-conflicting prefix).
HARNESS_GATE_DECISION = "agent.harness.gate.decision"
```

- 把 key 定义成常量，既避免拼写错误，也方便测试 `from main import GEN_AI_SYSTEM` 后断言。
- 自定义的 harness 字段放在 `agent.harness.` 前缀下，不和标准命名空间冲突——这是 OTel 推荐的做法。
- 注意 1：`gen_ai.tool.result.bytes` **并不是** GenAI 标准 key，却放在了 `gen_ai.` 命名空间里，与代码自己"自定义字段用独立前缀"的原则相矛盾；更稳妥的命名是 `agent.harness.tool.result_bytes`。
- 注意 2：同课程 [阶段 14 · 23](../../../14-agent-engineering/23-otel-genai-conventions/docs/zh.md) 与 [阶段 13 · 20](../../../13-tools-and-protocols/20-opentelemetry-genai/docs/zh.md) 的讲义都用 `gen_ai.provider.name` 表示提供商，并说明 GenAI 约定大多仍处于 experimental；本节用的是 `gen_ai.system`。讲义"OTel never breaks GenAI attribute names"的说法过于绝对。

### 3.2 `SpanEvent` 与 `GenAISpan`

```python
@dataclass
class GenAISpan:
    trace_id: str
    span_id: str
    name: str
    start_unix_nano: int
    end_unix_nano: int = 0
    parent_span_id: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)
    status: str = STATUS_UNSET
    status_message: str = ""
    kind: str = "INTERNAL"

    @property
    def duration_ms(self) -> float:
        if self.end_unix_nano <= 0:
            return 0.0
        return (self.end_unix_nano - self.start_unix_nano) / 1_000_000.0
```

- 字段与 OTel span 一一对应：`kind` 取 `INTERNAL` / `CLIENT` 等（demo 中模型调用是 `CLIENT`，因为它调用远程服务）；`status` 三态 `UNSET` / `OK` / `ERROR`。
- `field(default_factory=dict)`：可变默认值必须用工厂函数，否则所有实例会共享同一个字典。
- 没有默认值的字段必须排在有默认值的字段前面（dataclass 规则），所以 `start_unix_nano` 在前、`end_unix_nano = 0` 在后。
- `duration_ms`：纳秒差 ÷ 10⁶ = 毫秒；未结束（`end <= 0`）时返回 0，测试 `test_duration_zero_when_not_ended` 验证这一点。测试里 `start=10_000, end=15_000_000` 得到 14.99 ms。
- `to_dict` 把 `status` 嵌套成 `{"code": ..., "message": ...}`，与 OTLP JSON 的结构相似；`duration_ms` 是派生字段，四舍五入到 4 位小数，方便人读（OTLP 本身没有这个字段）。
- `dict(self.attributes)` 做浅拷贝，避免序列化后外部修改影响结果。

### 3.3 ID 生成

```python
def new_trace_id() -> str:
    """Random 16-byte hex string. Matches W3C trace context."""
    return uuid.uuid4().hex + uuid.uuid4().hex[:0]  # uuid4 hex is already 32 chars

def new_span_id() -> str:
    """Random 8-byte hex string. Matches W3C trace context span id."""
    return uuid.uuid4().hex[:16]
```

- 长度正确：trace_id 32 个十六进制字符（16 字节），span_id 16 个（8 字节），符合 W3C Trace Context。
- 与讲义不一致：讲义说"generated from `os.urandom`"且"span id and trace id are 16-byte"；代码用的是 `uuid4`，且 span_id 是 8 字节。
- `+ uuid.uuid4().hex[:0]` 拼接空串，是无用代码。
- uuid4 有固定位：`hex[12]` 恒为 `'4'`（版本号），`hex[16]` 只能是 `8/9/a/b`（variant）。实测 2000 个 span_id 的 `[12]` 字符集合为 `{'4'}`，所以 span_id 只有 60 位随机。建议改为 `os.urandom(8).hex()` / `secrets.token_hex(8)`，并排除全 0（W3C 规定全 0 无效）。详见测验 Q9。
- `time.time_ns()` 返回整数纳秒，避免浮点精度丢失；OTLP 的时间字段也是 unix 纳秒。

### 3.4 Exporter：JSONL 与内存

```python
@dataclass
class JSONLExporter:
    path: str
    fh: Any = None
    closed: bool = False

    def _ensure_open(self) -> None:
        if self.fh is None:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            self.fh = open(self.path, "a", encoding="utf-8")

    def export(self, span: GenAISpan) -> None:
        self._ensure_open()
        line = json.dumps(span.to_dict(), separators=(",", ":"))
        self.fh.write(line + "\n")
        self.fh.flush()
```

- **懒打开**：第一次 `export` 才创建目录和文件；`"a"` 追加模式，多次运行不会覆盖。
- `separators=(",", ":")` 去掉默认的空格，得到最紧凑的单行 JSON；`json.dumps` 默认会把非 ASCII 转义成 `\uXXXX`，因此一行里不会出现裸换行，保证"一行一个 span"。
- 每次写完 `flush()`：进程崩溃时已写入的 span 不会丢在缓冲区里，代价是每个 span 一次系统调用。
- `os.path.dirname(self.path) or "."`：若 path 只是文件名，`dirname` 返回空串，`makedirs("")` 会报错，所以兜底为当前目录。
- ⚠️ 讲义说"The exporter never throws; IO errors are surfaced but the harness keeps running"，但 `export` 没有任何 `try/except`，磁盘满、权限不足都会直接抛出（见 3.8）。
- ⚠️ `close()` 后 `self.fh` 仍是已关闭的文件对象，`_ensure_open` 不会重开；再 `export` 会抛 `ValueError: I/O operation on closed file.`（已实测）。
- `InMemoryExporter` 是一个"鸭子类型"的替身：只要有 `export` / `close` 方法即可被 `SpanBuilder` 使用，没有用抽象基类或 `Protocol` 声明接口。

### 3.5 Label 处理与 `Counter`

```python
def _label_key(labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(labels.items()))

def _format_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = []
    for k, v in sorted(labels.items()):
        escaped = str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        parts.append(f'{k}="{escaped}"')
    return "{" + ",".join(parts) + "}"
```

- 字典不可哈希，不能当 dict 的 key；`tuple(sorted(items))` 把 `{"tool": "x"}` 变成 `(("tool", "x"),)`，并且**排序**保证 `{"a":1,"b":2}` 与 `{"b":2,"a":1}` 映射到同一条时间序列。
- 转义顺序很重要：先把 `\` 变成 `\\`，再转义 `"` 和换行；反过来会把新加的反斜杠再转义一次。实测 `'a"b\c\nd'` 输出为 `c{tool="a\"b\\c\nd"} 1.0`，符合 Prometheus 规范要求的三种转义。
- label **名**没有校验（Prometheus 要求 `[a-zA-Z_][a-zA-Z0-9_]*`），生产中应检查。

```python
@dataclass
class Counter:
    name: str
    help: str = ""
    values: dict[tuple[tuple[str, str], ...], float] = field(default_factory=dict)

    def inc(self, labels=None, by: float = 1.0) -> None:
        key = _label_key(labels or {})
        self.values[key] = self.values.get(key, 0.0) + by
```

- 每个 label 组合一个浮点累计值；`get` 对不存在的组合返回 0.0。
- 值是 float，所以 exposition 输出 `1.0`。Prometheus 文本格式接受浮点，测试里 `assertIn('... 1', text)` 能通过是因为 `"1"` 是 `"1.0"` 的子串。
- ⚠️ 没有检查 `by >= 0`。counter 必须单调递增，`inc(by=-1)` 在 Prometheus 侧会被当成"计数器重置"，导致 `rate()` 结果错误。
- 讲义说 counter 是 `{(name, frozen_labels): int}`，代码实际是"按名字一个 `Counter` 对象 + 每对象内 `{label_key: float}`"，结构略有不同但等价。

### 3.6 `Histogram` 与 `MetricsRegistry`

```python
    def bucket_counts(self, labels=None) -> dict[float, int]:
        key = _label_key(labels or {})
        values = self.samples.get(key, [])
        counts: dict[float, int] = {}
        for bound in self.buckets:
            counts[bound] = sum(1 for v in values if v <= bound)
        counts[math.inf] = len(values)
        return counts
```

- **保存原始样本、导出时再分桶**：实现最简单，任何时候都能换桶边界；代价是内存随调用次数线性增长、每次导出要 O(样本数 × 桶数) 扫描。真实客户端库是"observe 时直接给对应桶 +1、累加 sum 和 count"，内存恒定。
- `v <= bound` 实现**累积**计数（Prometheus `le` = less than or equal）；`math.inf` 桶等于样本总数。
- 例：样本 `3, 7, 12, 30, 600` → `{5:1, 10:2, 25:3, 50:4, 100:4, 250:4, 500:4, 1000:5, ..., inf:5}`（已实测）。
- 默认桶 `5 … 10000`（毫秒）。讲义称之为"the OTel default for latency in milliseconds"；它实际与 Prometheus Go 客户端 `DefBuckets`（0.005…10 秒）×1000 一致，而 OTel SDK 的默认显式桶还包含 0、75、750、7500 等边界。
- `MetricsRegistry.counter(name, help)` 是 get-or-create：已存在时直接返回旧对象，**忽略**新传入的 help。所以第一次创建时给的 help 才会生效。

### 3.7 Prometheus 文本格式渲染

```python
    for name in sorted(registry.histograms):
        hist = registry.histograms[name]
        if hist.help:
            lines.append(f"# HELP {hist.name} {hist.help}")
        lines.append(f"# TYPE {hist.name} histogram")
        keys = list(hist.samples.keys()) or [tuple()]
        for key in sorted(keys):
            label_dict = dict(key)
            counts = hist.bucket_counts(label_dict)
            for bound in hist.buckets:
                bucket_labels = {**label_dict, "le": _format_le(bound)}
                lines.append(f"{hist.name}_bucket{_format_labels(bucket_labels)} {counts[bound]}")
            ...
            lines.append(f"{hist.name}_sum{_format_labels(label_dict)} {hist.total_sum(label_dict)}")
            lines.append(f"{hist.name}_count{_format_labels(label_dict)} {hist.total_count(label_dict)}")
    return "\n".join(lines) + "\n"
```

- 每个 metric 先输出 `# HELP`（可选）和 `# TYPE`，再输出各条样本行；整个文本以换行结尾（规范要求）。
- 对没有任何数据的 counter 输出 `name 0`；没有样本的 histogram 用 `[tuple()]` 兜底，输出一组全 0 的无 label 桶（实测 `h_bucket{le="5"} 0 … h_sum 0.0`、`h_count 0`），这样抓取端能看到该 metric 存在。
- `{**label_dict, "le": ...}` 用字典解包合并 label；`_format_labels` 内部排序，所以 `le` 会排在 `tool` 前面：`tool_latency_ms_bucket{le="10",tool="read_file"} 1`。label 顺序不影响 Prometheus 解析。
- `_format_le(5.0)` → `"5"`，`_format_le(0.5)` → `"0.5"`：整数边界去掉 `.0`。
- 每个 label 组合会产生 `桶数 + 3` 行（11 个有限桶 + `+Inf` + `_sum` + `_count` = 14 行）——这正是"label 基数要低"的直观理由。
- 没有输出时间戳，由 Prometheus 抓取时打时间戳，这是 pull 模型的常规做法。

### 3.8 `SpanBuilder.span`：本节的核心

```python
    @contextmanager
    def span(self, name, attributes=None, parent=None, kind="INTERNAL") -> Iterator[GenAISpan]:
        span = GenAISpan(
            trace_id=self.trace_id,
            span_id=new_span_id(),
            parent_span_id=parent.span_id if parent else "",
            name=name, kind=kind,
            start_unix_nano=now_unix_nano(),
            attributes=dict(attributes or {}),
        )
        try:
            yield span
            span.status = STATUS_OK
        except BaseException as exc:  # noqa: BLE001
            span.status = STATUS_ERROR
            span.status_message = f"{type(exc).__name__}: {exc}"
            span.events.append(SpanEvent(name="exception", ...))
            raise
        finally:
            span.end_unix_nano = now_unix_nano()
            for exporter in self.exporters:
                exporter.export(span)
            if self.metrics is not None:
                tool = span.attributes.get(GEN_AI_TOOL_NAME)
                if tool is not None:
                    self.metrics.counter("tools_called_total", help="Total tool calls").inc({"tool": str(tool)})
                    self.metrics.histogram("tool_latency_ms", help="...").observe(span.duration_ms, {"tool": str(tool)})
```

执行顺序：

| 阶段 | 发生了什么 |
|------|-----------|
| 进入 `with` | 创建 span，记开始时间，`yield` 把 span 交给 `as` 变量 |
| `with` 块内 | 调用方可继续修改 `span.attributes` / `span.events`（例如模型返回后才知道 token 数） |
| 正常结束 | `yield` 之后的 `span.status = STATUS_OK` 执行 |
| 抛异常 | 异常在 `yield` 处"冒出"，进入 `except`：设 ERROR、写 message、追加 `exception` event，然后 `raise` 重新抛出 |
| 无论如何 | `finally`：记结束时间 → 依次导出 → 若是工具 span 则更新 counter 与 histogram |

要点：

- `attributes=dict(attributes or {})` 复制一份，调用方后续改自己的字典不会影响 span。
- exception event 的 key `exception.type` / `exception.message` 是 OTel 通用语义约定中的标准名字。
- 捕获 `BaseException` 而不只是 `Exception`：`KeyboardInterrupt`、`SystemExit`、`GeneratorExit` 也会被记为 ERROR 再抛出。对"记录现场"是合理的（用户按 Ctrl+C 中断的那次调用也会留下 ERROR span）。
- 父子关系必须**手动**传 `parent=`。OTel SDK 用 `contextvars` 自动追踪"当前 span"，嵌套 `with` 时无需传参，跨线程/协程也能正确传播。
- 一个 `SpanBuilder` 固定一个 `trace_id`。demo 中"第二个回合"的 `shell` span 与第一个回合共用同一个 trace_id，且 `parent_span_id` 为空——严格说它应该是另一个 trace 的根 span。
- ⚠️ `finally` 里的导出没有异常保护：若 exporter 抛 `OSError`，它会**替换**掉业务异常（原异常只剩 `__context__`），且后面的 metric 更新不会执行。实测：业务抛 `ValueError('original')`、exporter 抛 `OSError('disk full')`，调用方收到 `OSError`，metrics 为空 `{}`。修复见测验 Q10。
- ⚠️ metric 只按 `tool` 打 label，没有 `status`，因此被 gate 拒绝的 `shell` 调用也计入 `tools_called_total`，无法算错误率（测验 Q8）。
- 讲义承诺的 `wrap_tool_call(name)` 装饰器在代码中不存在，参考实现见测验 Q11。

### 3.9 `run_demo`：合成一次 agent 回合

```python
    with builder.span("gen_ai.chat", attributes={GEN_AI_SYSTEM: "anthropic", ...}, kind="CLIENT") as chat_span:
        time.sleep(0.01)
        chat_span.attributes[GEN_AI_USAGE_INPUT_TOKENS] = 412
        chat_span.attributes[GEN_AI_USAGE_OUTPUT_TOKENS] = 96
        ...
        with builder.span("gen_ai.tool.execution", parent=chat_span,
                          attributes={GEN_AI_TOOL_NAME: "read_file", GEN_AI_TOOL_CALL_ID: "call_001"}) as tool1:
            time.sleep(0.005)
            tool1.attributes[GEN_AI_TOOL_RESULT_BYTES] = 1024
            tool1.events.append(SpanEvent(name="agent.harness.gate.decision", ..., attributes={HARNESS_GATE_DECISION: "ALLOW", ...}))
```

- 模型 span 在开始时只知道"请求"属性（system、model、max_tokens、temperature），"响应"属性（token 用量、response model/id）在 `with` 块内补上——这正是 span 设计成可变对象的原因。
- 两个工具 span 以 `chat_span` 为父；gate 决策作为 event 挂在工具 span 上。
- 第二段代码故意 `raise PermissionError(...)` 制造一个 ERROR span，外层 `except PermissionError: pass` 吞掉，证明异常确实被重新抛出了。
- 打印时 `sorted(attrs_compact)[:3]` 只显示按字母序的前 3 个 `gen_ai.*` key，所以 chat span 显示的是 `operation.name / request.max_tokens / request.model`，看不到 token 用量——并不是没记录。
- 最后关闭 JSONL 并逐行 `json.loads` 回读，验证文件格式。
- ⚠️ 讲义说 traces.jsonl 写在"lesson's working dir (cleaned up at the end)"，代码实际用 `tempfile.mkdtemp` 写到系统临时目录，并且**从不删除**；每次运行（以及测试 `test_demo_main_exits_zero`、`test_jsonl_roundtrip`）都会在 `/tmp` 留下一个目录。
- span 名 `gen_ai.chat` / `gen_ai.tool.execution` 是本课自定的；OTel GenAI 约定推荐 `{operation} {model}`、`execute_tool {tool_name}` 这类名字（参见阶段 13 · 20 中 `gen_ai.operation.name` 的取值 `"chat"`、`"execute_tool"`）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手写 span 而不引 opentelemetry-sdk | 看清 wire format，离线、零依赖 | 无批处理、无采样、无上下文传播；生产用 SDK + OTLP，attribute key 不变 |
| `@contextmanager` 包装 span | `with` 语法天然覆盖"开始—结束—异常" | 必须手动传 parent；SDK 用 `contextvars` 自动传播 |
| 同步导出 + 每行 `flush` | 简单、崩溃时不丢已写数据 | 每个 span 一次 IO，阻塞业务线程；生产用 `BatchSpanProcessor` 异步批量导出 |
| JSONL 文件 | 可 grep、可流式读、可导入 | 没有轮转、没有压缩；生产发往 Collector |
| exporter 鸭子类型（`export`/`close`） | 方便插入 `InMemoryExporter` 做测试 | 没有接口声明；可用 `typing.Protocol` |
| histogram 保存原始样本 | 实现直观，可随时换桶 | 内存无界增长；客户端库按桶计数，内存恒定 |
| metric 只按 `tool` 打 label | 低基数、示例简洁 | 无法区分成功/失败；生产加 `status` label 或单独错误 counter |
| ID 用 `uuid4` 截取 | 写起来短 | 有固定位（span_id 仅 60 位随机）；应用 `os.urandom` / `secrets` |
| demo 用 `tempfile.mkdtemp` | 不污染仓库 | 从不清理，与讲义"cleaned up"不符；应用 `TemporaryDirectory()` 上下文 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可以在 3.8/3.9 上写 `dict[str, Any]`、`X \| None` |
| `@dataclass` | `class GenAISpan:` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `field(default_factory=...)` | `attributes: dict[str, Any] = field(default_factory=dict)` | 可变默认值必须用工厂，否则实例间共享 |
| `@property` | `def duration_ms(self) -> float` | 像属性一样访问：`span.duration_ms`，无需括号 |
| 类型注解 | `-> Iterator[GenAISpan]`、`MetricsRegistry \| None` | 只做文档/静态检查，运行时不强制 |
| `@contextmanager` + `yield` | `def span(...)` | 生成器函数变成 context manager；`yield` 之前是 `__enter__`，之后是 `__exit__` |
| `try/except/finally` + 裸 `raise` | `except BaseException as exc: ... raise` | 记录后原样重新抛出；`finally` 总会执行 |
| `with ... as` 嵌套 | `with builder.span(...) as chat_span:` 内再 `with` | 退出顺序与进入相反（子先父后） |
| 条件表达式 | `parent.span_id if parent else ""` | 一行 if/else |
| `or` 取默认值 | `labels or {}`、`os.path.dirname(p) or "."` | 左值为假（None、空）时取右值 |
| 生成器表达式 | `sum(1 for v in values if v <= bound)` | 不建列表直接计数 |
| 字典推导式 | `{k: v for k, v in span.attributes.items() if k.startswith("gen_ai.")}` | 过滤字典 |
| 字典解包合并 | `{**label_dict, "le": "+Inf"}` | 复制并追加键 |
| `dict.setdefault` | `self.samples.setdefault(key, []).append(...)` | 不存在则插入默认值并返回 |
| `dict.get(k, default)` | `self.values.get(key, 0.0)` | 取值带默认 |
| 元组作字典键 | `tuple(sorted(labels.items()))` | 字典不可哈希，转成有序元组 |
| `math.inf` | `counts[math.inf] = len(values)` | 正无穷，可作字典键、可比较 |
| f-string 格式符 | `{span.name:32s}`、`{span.duration_ms:7.2f}` | 宽度 32 的字符串；宽度 7、两位小数 |
| `type(exc).__name__` | `f"{type(exc).__name__}: {exc}"` | 取异常类名 |
| 数字下划线 | `1_000_000.0`、`15_000_000` | 仅提高可读性 |
| `json.dumps(..., separators=(",", ":"))` | `JSONLExporter.export` | 紧凑输出 |
| `next(生成器)` | 测试中 `next(s for s in exp.spans if s.name == "child")` | 取第一个满足条件的元素 |
| `sys.exit(run_demo())` + `if __name__ == "__main__"` | 文件末尾 | 以返回值作为进程退出码；被 import 时不运行 demo |

---

## 6. 运行结果解读

实际运行（Python 3.13，`cd code && python3 main.py`，退出码 0；trace_id 与路径每次不同）：

```text
OBSERVABILITY DEMO
trace_id=8ea32deede2f4065ae5a5e24474bf6ec          ← 32 个十六进制字符，注意第 13 位是 4（uuid4 版本号）
writing traces to /tmp/otel-demo-haefcer3/traces.jsonl

emitted 4 span(s):
  - gen_ai.tool.execution            dur=   5.16ms status=OK keys=['gen_ai.tool.call.id', 'gen_ai.tool.name', 'gen_ai.tool.result.bytes']   ← read_file
  - gen_ai.tool.execution            dur=   3.16ms status=OK keys=[...]      ← run_tests
  - gen_ai.chat                      dur=  21.09ms status=OK keys=['gen_ai.operation.name', 'gen_ai.request.max_tokens', 'gen_ai.request.model']
  - gen_ai.tool.execution            dur=   0.02ms status=ERROR keys=['gen_ai.tool.call.id', 'gen_ai.tool.name']   ← shell，被拒

--- prometheus exposition ---
# HELP tools_called_total Total tool calls
# TYPE tools_called_total counter
tools_called_total{tool="read_file"} 1.0
tools_called_total{tool="run_tests"} 1.0
tools_called_total{tool="shell"} 1.0              ← 被拒绝的调用也计入
# HELP tool_latency_ms Tool call latency in milliseconds
# TYPE tool_latency_ms histogram
tool_latency_ms_bucket{le="5",tool="read_file"} 0  ← 5.16 > 5
tool_latency_ms_bucket{le="10",tool="read_file"} 1
...
tool_latency_ms_bucket{le="+Inf",tool="read_file"} 1
tool_latency_ms_sum{tool="read_file"} 5.161171
tool_latency_ms_count{tool="read_file"} 1
tool_latency_ms_bucket{le="5",tool="run_tests"} 1   ← 3.16 ≤ 5
...
tool_latency_ms_sum{tool="shell"} 0.016895
tool_latency_ms_count{tool="shell"} 1

roundtrip parsed 4 spans from /tmp/otel-demo-haefcer3/traces.jsonl
```

逐项解读：

- **span 顺序**：子 span 先结束先导出，父 span `gen_ai.chat` 第三个出现；最后是独立的 `shell` 错误 span。
- **耗时**：`chat` 约 21 ms = 自身 `sleep(0.01)` 10 ms + 两个工具约 8.3 ms + 开销；工具耗时都略大于 `sleep` 时长。`shell` 没有 sleep，0.02 ms 主要是构造 event 和抛异常的开销。
- **桶边界效应**：`read_file` 的 5.16 ms 落在 `le="10"`，`run_tests` 的 3.16 ms 落在 `le="5"`。如果把 sleep 刚好设在桶边界上，结果就会"看运气"。
- **counter 显示为 `1.0`**：值是 float；Prometheus 解析无影响。
- **只有工具 span 产生 metric**：`gen_ai.chat` 没有 `gen_ai.tool.name`，不计入；模型调用的 token 用量只存在 trace 里，没有对应 metric。
- **回读 4 个 span**：证明每行都是合法 JSON。运行结束后 `/tmp/otel-demo-*` 目录仍然存在（未清理）。

---

## 7. 动手改一改

1. **修 ID**：用 `os.urandom` 重写 `new_trace_id` / `new_span_id`，排除全 0，删除 `hex[:0]` 无用拼接；写一个测试统计 1000 个 span_id 每个位置的字符分布，确认不再有固定位。
2. **加 status label**：让 `tools_called_total` 带 `{tool, status}`，再加 `tool_errors_total{tool}`；修改 demo 后确认 `shell` 只出现在 `status="ERROR"` 序列中。
3. **实现 `wrap_tool_call` 装饰器**（讲义承诺但缺失），参考测验 Q11；给 `read_file` / `run_tests` 两个假工具加装饰器，重写 demo。
4. **让 exporter 真正"never throws"**：在 `finally` 中先更新 metric，再对每个 exporter `try/except`；写一个总是抛 `OSError` 的 exporter 测试，断言业务异常类型不变、metric 已更新。
5. **自动父子关系**：用 `contextvars.ContextVar` 保存当前 span，`span()` 在未传 `parent` 时自动取当前 span 作父，退出时恢复；验证嵌套 `with` 无需手动传参。
6. **进阶**：给 histogram 改成"observe 时按桶计数"（只存 `bucket_counts`、`sum`、`count`），对比 10 万次 observe 的内存；再用 `http.server` 暴露 `/metrics` 端点，让本地 Prometheus 抓取，并用 `histogram_quantile(0.95, rate(tool_latency_ms_bucket[5m]))` 查询。

---

## 8. 常见坑

- **把可变对象当 dataclass 默认值**：写成 `attributes: dict = {}` 会直接报错（dataclass 会拦截），必须 `field(default_factory=dict)`。
- **以为 span 按开始顺序导出**：导出发生在结束时，子先父后；重建树要靠 `parent_span_id`，不能靠行号。
- **在 `finally` 里做可能失败的 IO**：会吞掉业务异常并中断后续逻辑。
- **counter 的值可以减**：counter 必须单调；需要增减的量用 gauge。
- **高基数 label**：把 call_id、trace_id、文件路径放进 label 会让时间序列爆炸；这些信息放在 span attribute 里。
- **桶边界没覆盖业务范围**：所有值都 > 最大有限桶时，`histogram_quantile` 只能返回最后一个边界，分位数失真。
- **自定义 key 混进标准命名空间**：如 `gen_ai.tool.result.bytes`；将来标准新增同名 key 时语义可能冲突。
- **semconv 版本差异**：`gen_ai.system` 与 `gen_ai.provider.name`，接入后端前先核对所用版本。
- **临时文件不清理**：`mkdtemp` 需要配合 `shutil.rmtree`，或改用 `with tempfile.TemporaryDirectory() as d:`。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m pytest -q tests`（或 `python3 -m unittest discover tests`）。实际结果：**14 passed in 0.04s**。

| 测试类 / 方法 | 验证的性质 |
|--------------|-----------|
| `IdTests.test_trace_id_is_32_hex` | trace_id 长 32 且能按 16 进制解析（`int(tid, 16)` 不抛异常） |
| `IdTests.test_span_id_is_16_hex` | span_id 长 16 且为合法十六进制（注意：没有检查随机性，所以 uuid4 固定位问题测不出来） |
| `SpanShapeTests.test_span_dict_contains_required_keys` | `to_dict()` 含 trace_id、span_id、name、kind、起止时间、duration_ms、attributes、events、status；attribute 原样保留；duration > 0 |
| `SpanShapeTests.test_duration_zero_when_not_ended` | 未结束的 span `duration_ms == 0.0` |
| `CounterTests.test_increment_default` | 不同 label 组合独立计数；未出现的组合返回 0 |
| `HistogramTests.test_bucket_counts_are_cumulative` | 桶 `(10, 100, 1000)`、样本 `1, 5, 20, 200, 2000` → 累积计数 2/3/4/5，`total_sum = 2226.0` |
| `PrometheusExpositionTests.test_counter_exposition` | 输出包含 `# HELP`、`# TYPE ... counter` 和带 label 的样本行 |
| `PrometheusExpositionTests.test_histogram_exposition_includes_buckets_sum_count` | 观测 7 和 300 后：`le="10"` 为 1、`+Inf` 为 2、`_sum` 为 307.0、`_count` 为 2，并验证 `le` 排在 `tool` 前 |
| `SpanBuilderTests.test_successful_span_status_ok` | 正常结束：导出 1 个 span，状态 OK，结束时间已写入 |
| `SpanBuilderTests.test_exception_records_status_error` | 异常被重新抛出（`assertRaises`），状态 ERROR，message 含异常类名，有 `exception` event |
| `SpanBuilderTests.test_parent_child_relationship` | 子 span 的 `parent_span_id` 等于父 span 的 `span_id`，且共享 trace_id |
| `SpanBuilderTests.test_tool_span_drives_counter_and_histogram` | 3 次工具 span → counter 为 3、histogram 计数为 3 |
| `JSONLRoundtripTests.test_jsonl_roundtrip` | 写入 JSONL 后逐行 `json.loads`，字段与状态码一致 |
| `DemoTests.test_demo_main_exits_zero` | `run_demo()` 返回 0（会打印完整 demo 输出并在 `/tmp` 留下目录） |

测试没有覆盖的点（可作为练习补充）：exporter 抛异常时的行为、`close()` 后再导出、label 转义、空 registry 的输出、ID 的随机性、临时目录清理。
