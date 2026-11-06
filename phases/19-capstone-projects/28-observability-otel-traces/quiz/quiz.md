# 测验 · 通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability（Observability with OTel GenAI Spans and Prometheus Metrics）

> **阶段 19 · 综合项目 · 第 28 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么 agent 需要 observability | 讲义列出三种失败：没有 trace（出事只能翻聊天记录）、trace 字段名自定义导致工具链读不了、只有 trace 没有聚合 metric（回答不了"read_file 最近一小时 p95 延迟"） |
| 2 | trace / span 的结构 | 一次 agent 调用是一个 trace（`trace_id`），其中每个操作是一个 span（`span_id`），用 `parent_span_id` 连成树；span 带 name、kind、起止时间（纳秒）、attributes、events、status |
| 3 | OTel GenAI 语义约定 | 用标准 key 记录模型调用与工具调用：`gen_ai.system`、`gen_ai.request.model`、`gen_ai.usage.input_tokens/output_tokens`、`gen_ai.response.id`、`gen_ai.tool.name`、`gen_ai.tool.call.id` 等；用了标准 key，任何 OTel 兼容后端都能直接解析 |
| 4 | W3C Trace Context 的 ID 长度 | trace_id 16 字节（32 个十六进制字符），span_id 8 字节（16 个十六进制字符） |
| 5 | span 作为 context manager | 进入时记开始时间；正常退出 `status=OK`；抛异常时 `status=ERROR`、写 `status_message`、追加名为 `exception` 的 event 并**重新抛出**；`finally` 里记结束时间并导出 |
| 6 | JSONL exporter | 每行一个自包含 JSON 对象（一个 span），可流式写、可 grep、可 `json.loads` 逐行回读；是 OTLP gRPC 导出器的离线替身 |
| 7 | Prometheus counter | 单调递增、带 label：`tools_called_total{tool="read_file"}`；一个 label 组合就是一条时间序列 |
| 8 | Prometheus histogram | 固定桶边界，`_bucket{le="..."}` 是**累积**计数（`v <= le`），外加 `_sum`、`_count` 和 `le="+Inf"`；分位数由服务端 `histogram_quantile` 线性插值估算 |
| 9 | trace 与 metric 分工 | trace 回答"这一次发生了什么"，metric 回答"整体趋势/分位数是多少"；本节在 span 结束时顺手更新工具调用的 counter 与 histogram |
| 10 | 手写 vs SDK | 手写是为了看清 wire format；生产中换成 opentelemetry-sdk，获得 OTLP 导出、批处理、resource 检测，attribute key 保持不变 |

### 核心技能（能动手做到）

- [ ] 用 `@dataclass` + `@contextmanager` 写出一个记录耗时、状态、异常事件并支持父子关系的 span builder
- [ ] 给定一组延迟样本和桶边界，手算 Prometheus histogram 每个 `le` 桶的累积计数、`_sum`、`_count`
- [ ] 用 `histogram_quantile` 的线性插值规则从累积桶估算 p50/p95/p99，并说明误差来源
- [ ] 读懂 JSONL trace 文件，按 `parent_span_id` 还原 span 树，解释为什么子 span 先于父 span 写出
- [ ] 指出本节代码与讲义的不一致（ID 生成方式、exporter "从不抛异常"、缺失的 `wrap_tool_call`、临时文件未清理）并给出修复
- [ ] 为 agent harness 设计 span 名、attribute、metric 与 label，避免高基数 label

---

## 二、基础自测（选择题）

**Q1.** 按 OTel GenAI 语义约定（也是本节代码的写法），哪一组 attribute key 用来标识"这是一次工具调用、调用的是哪个工具、是哪一次调用"？

- A. `gen_ai.tool.name` + `gen_ai.tool.call.id`
- B. `gen_ai.system` + `gen_ai.request.model`
- C. `agent.harness.gate.decision` + `agent.harness.gate.reason`
- D. `gen_ai.operation.name` + `gen_ai.response.id`

**Q2.** 在 `with builder.span(...) as s:` 块内抛出 `PermissionError("tool 'shell' not in allow-set")`，本节 `SpanBuilder.span` 会怎样处理？

- A. 吞掉异常，span 状态保持 `UNSET`，不导出该 span
- B. 把 span 名改成 `error` 后导出，异常不再向外传播
- C. 只把 `status` 设为 `ERROR`，不记录任何 event，异常被吞掉
- D. `status=ERROR`、`status_message="PermissionError: tool 'shell' not in allow-set"`、追加名为 `exception` 的 event，导出 span，然后重新抛出异常

**Q3.** 使用本节 `Histogram` 的默认桶（5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000），依次 `observe` 了 `3, 7, 12, 30, 600` 五个值。`le="50"` 和 `le="+Inf"` 两行的计数分别是：

- A. 1 和 5
- B. 4 和 5
- C. 4 和 4
- D. 3 和 5

**Q4.** 运行 demo 时，`emitted 4 span(s)` 下面的打印顺序是 `tool.execution, tool.execution, gen_ai.chat, tool.execution(ERROR)`——父 span `gen_ai.chat` 排在它的两个子 span 后面。原因是：

- A. `InMemoryExporter` 会按 span 名字母序排序
- B. `gen_ai.chat` 是 `CLIENT` 类型，导出优先级较低
- C. span 在 context manager 的 `finally`（退出时）才导出；嵌套的子 span 先退出，所以先导出
- D. demo 故意把父 span 的导出延后，以便计算总耗时

**Q5.** 关于本节代码生成的 ID，下列说法正确的是：

- A. trace_id 与 span_id 都是 16 字节，即 32 个十六进制字符（与讲义描述一致）
- B. trace_id 用 `os.urandom(16)` 生成，span_id 用 `os.urandom(8)` 生成
- C. span_id 是 32 个十六进制字符，trace_id 是 16 个十六进制字符
- D. trace_id 是 32 个十六进制字符（16 字节），span_id 是 16 个十六进制字符（8 字节），两者都由 `uuid.uuid4().hex` 截取而来

**Q6.** 想回答"过去一小时 `read_file` 的 p95 延迟是多少"，最合适的数据来源是：

- A. 对 `tool_latency_ms_bucket{tool="read_file"}` 在时间窗口内求增量，再用 `histogram_quantile(0.95, ...)` 估算
- B. 用 `tools_called_total{tool="read_file"}` 除以时间窗口长度
- C. 读取 span 的 `status_message` 字段
- D. 只看 `tool_latency_ms_sum` 除以 `tool_latency_ms_count`

**Q7.** demo 里 `read_file` 工具块执行了 `time.sleep(0.005)`，但它的延迟（约 5.16 ms）落在 `le="10"` 桶，而 `le="5"` 桶计数为 0。原因是：

- A. 代码的 `bucket_counts` 用的是严格小于 `v < bound`
- B. `duration_ms` 把纳秒错除以了 10^5
- C. `sleep(0.005)` 只保证至少睡 5 ms，再加上进入/退出 span 的开销，实测略大于 5；而 `le` 桶的判定是 `v <= bound`，5.16 > 5
- D. 第一个桶被保留给 counter，不计入 histogram

**Q8.** demo 中被 gate 拒绝的 `shell` 调用也出现在 `tools_called_total{tool="shell"} 1.0` 与 `tool_latency_ms` 中。若要在 Prometheus 里计算"工具错误率"，当前实现的问题是：

- A. counter 不能有 label，只能用 histogram
- B. metric 的 label 只有 `tool`，没有记录 span 的 `status`，成功和失败的调用混在同一条时间序列里，无法区分
- C. Prometheus 无法对 counter 做除法
- D. 错误 span 根本没有被导出到 JSONL

---

## 三、动手 / 代码题

**Q9.** 阅读 ID 生成函数：

```python
def new_trace_id() -> str:
    """Random 16-byte hex string. Matches W3C trace context."""

    return uuid.uuid4().hex + uuid.uuid4().hex[:0]  # uuid4 hex is already 32 chars


def new_span_id() -> str:
    """Random 8-byte hex string. Matches W3C trace context span id."""

    return uuid.uuid4().hex[:16]
```

1. 对 2000 个 `new_span_id()` 统计第 13 个字符（下标 12），会得到什么？为什么？span_id 实际有多少位随机？
2. `+ uuid.uuid4().hex[:0]` 做了什么？
3. 讲义说 ID 由 `os.urandom` 生成、"span id 和 trace id 都是 16 字节"，与代码有哪些出入？
4. 给出一个符合 W3C Trace Context 的修正实现。

**Q10.** 讲义写道："The exporter never throws; IO errors are surfaced but the harness keeps running." 请结合下面的 `finally` 分支回答：

```python
        finally:
            span.end_unix_nano = now_unix_nano()
            for exporter in self.exporters:
                exporter.export(span)
            if self.metrics is not None:
                tool = span.attributes.get(GEN_AI_TOOL_NAME)
                ...
```

1. 若某个 exporter 的 `export` 抛出 `OSError("disk full")`，而 span 内部原本抛的是 `ValueError("original")`，调用方最终捕获到哪个异常？metric 会被更新吗？
2. `JSONLExporter.close()` 之后再导出一个 span，会发生什么？
3. 给出修复方案，使"导出失败不影响业务、不吞掉原异常、metric 照常更新"。

**Q11.** 讲义 "What you will build" 第 6 条承诺了 `wrap_tool_call(name)` 装饰器，"emits a span and updates metrics"，但 `main.py` 里并没有它。请实现：

```python
def wrap_tool_call(builder: SpanBuilder, tool_name: str, parent: GenAISpan | None = None):
    ...
```

要求：被装饰函数每次调用都包在 `gen_ai.tool.execution` span 中，带 `gen_ai.tool.name` 与自增的 `gen_ai.tool.call.id`；若返回值是 `str`/`bytes`，记录 `gen_ai.tool.result.bytes`；异常照常抛出。说明它如何复用 `SpanBuilder` 现有的 metric 逻辑。

**Q12.** 某服务 `tool_latency_ms{tool="read_file"}` 在一个窗口内的累积桶增量如下（其余更大的桶都等于 100）：

```text
le="10"   60
le="25"   90
le="50"   98
le="100"  100
le="+Inf" 100
```

按 Prometheus `histogram_quantile` 的线性插值规则（在目标桶内假设均匀分布，第一个桶下界取 0），手算 p50、p95、p99，并说明这种估算的误差上界由什么决定。

---

## 四、面试高频题

**Q13.**（基础必考）Trace、Metric、Log 三者有什么区别？对一个 coding agent，各自用来回答什么问题？

**Q14.**（原理深挖）Prometheus histogram 为什么用累积桶？`histogram_quantile` 是怎么算的、有什么误差？它和 Summary 类型相比有何取舍？桶边界该怎么选？

**Q15.**（工程实践）如果要把本节手写的 span builder 换成生产级 OpenTelemetry SDK，需要补上哪些能力？哪些东西可以原样保留？

**Q16.**（场景设计）为一个"读文件—改代码—跑测试"的 coding agent 设计 observability：你会定义哪些 span、哪些 attribute、哪些 metric 与告警？如何处理 prompt 内容等敏感数据？

**Q17.**（追问型）为什么不能把 `gen_ai.tool.call.id`、`trace_id` 或用户 ID 放进 Prometheus 的 label？如果确实想从一个慢的 histogram 桶跳到具体 trace，该怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："plus tool-specific keys `gen_ai.tool.name` and `gen_ai.tool.call.id`"。代码的工具 span 正是这两个 key，`SpanBuilder` 也只在 attributes 里有 `gen_ai.tool.name` 时才更新 `tools_called_total` / `tool_latency_ms`。

- B 描述的是"哪个提供商、哪个模型"，属于模型调用 span。
- C 是本节自定义的 harness 级 key（`agent.harness.` 前缀），记录 gate 决策，不是 GenAI 标准 key。
- D 中 `gen_ai.operation.name` 标识操作类型（demo 里是 `chat`），`gen_ai.response.id` 是模型响应 ID，都不标识具体工具调用。

### Q2 — 答案：D

代码：

```python
        except BaseException as exc:  # noqa: BLE001
            span.status = STATUS_ERROR
            span.status_message = f"{type(exc).__name__}: {exc}"
            span.events.append(SpanEvent(name="exception", ...))
            raise
```

`raise` 把原异常重新抛出，所以 demo 外层要 `try ... except PermissionError: pass`。`finally` 仍会执行，span 照常导出并更新 metric。A、C 错在"吞掉异常"——那会让调用方以为成功；B 中 span 名不会被修改。注意它捕获的是 `BaseException`，连 `KeyboardInterrupt` 也会被记为 ERROR 后再抛出，这对"记录现场"是合理的。

### Q3 — 答案：B

`bucket_counts` 对每个边界计算 `sum(1 for v in values if v <= bound)`，是**累积**计数。实际运行结果：`{5: 1, 10: 2, 25: 3, 50: 4, 100: 4, 250: 4, 500: 4, 1000: 5, ..., inf: 5}`。`le="50"` 包含 3、7、12、30 共 4 个；`+Inf` 永远等于样本总数 5。A 是 `le="5"` 的计数；C 把 `+Inf` 当成了 `le="500"`；D 是 `le="25"`。

### Q4 — 答案：C

导出发生在 `finally` 中，即 `with` 块**结束**时。`gen_ai.chat` 块里嵌套了两个工具块，它们先结束、先导出；`gen_ai.chat` 块最后结束。第四个 `shell` span 是 demo 第二段代码，最后执行。真实 OTel SDK 也是"span 结束时交给 SpanProcessor"，所以后端拿到的数据同样是子先父后，靠 `parent_span_id` 重建树。A、B、D 在代码中都不存在。

### Q5 — 答案：D

实测 `len(new_trace_id()) == 32`、`len(new_span_id()) == 16`，测试 `test_trace_id_is_32_hex` / `test_span_id_is_16_hex` 也是这样断言的，符合 W3C Trace Context（trace-id 16 字节、parent-id 8 字节）。

- A 是讲义的说法（"The span id and trace id are 16-byte hex strings"），对 span_id 不成立。
- B 也是讲义的说法（"generated from `os.urandom`"），代码实际用的是 `uuid.uuid4()`。
- C 把长度说反了。

### Q6 — 答案：A

分位数需要分布信息，histogram 正是为此设计：服务端对各桶求窗口增量（如 `rate(tool_latency_ms_bucket{tool="read_file"}[1h])`），再 `histogram_quantile(0.95, ...)`。B 得到的是调用速率；C 只有错误信息；D 是**平均值**，无法反映尾延迟。逐个解析 JSONL 中的 `duration_ms` 理论上也能算，但需要扫描全部原始 span，不是"预聚合"的做法。

### Q7 — 答案：C

`time.sleep(0.005)` 保证"至少"5 ms，操作系统调度、span 构造、`uuid` 生成都会再加一点时间，实测 `tool_latency_ms_sum{tool="read_file"} 5.161171`。桶判定是 `v <= bound`（A 说成严格小于，是错的；Prometheus 的 `le` 本义就是"小于等于"）。B 错：`duration_ms` 是 `(end - start) / 1_000_000.0`，纳秒转毫秒正确。D 不存在。这也提醒我们：**刚好落在桶边界附近的值很敏感**，桶边界应避开业务里常见的"整数阈值"，或在阈值两侧都设桶。

### Q8 — 答案：B

`SpanBuilder` 更新 metric 时只用了 `{"tool": str(tool)}` 一个 label，被 DENY 的 `shell` 与成功的调用写进同一条序列。改法：加一个低基数的 `status` label（`OK` / `ERROR`），或单独维护 `tool_errors_total{tool=...}`，错误率 = `rate(errors) / rate(total)`。A 错：counter 可以有 label；C 错：PromQL 支持向量除法；D 错：错误 span 已导出，JSONL 回读解析到了 4 个 span。

### Q9 — 参考答案

1. 实际统计 2000 个 span_id：下标 12 的字符集合为 `{'4'}`。UUID 版本 4 的格式是 `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`，第 13 个十六进制字符固定为版本号 `4`；去掉连字符后它就在 `hex[12]`。所以 `hex[:16]` 里有 1 个固定字符，只有 15 × 4 = **60 位**随机（而不是 64 位）。trace_id 同理：`hex[12]` 固定为 `4`，`hex[16]` 只可能是 `8/9/a/b`（variant 位），实测与此一致，有效随机位是 122 位。实际碰撞概率仍极低，但它不符合"Random 8-byte"的注释，且在需要高位随机的采样策略中（例如按 trace_id 某些位做采样）会产生偏差。
2. `uuid.uuid4().hex[:0]` 是空串，拼上它没有任何效果，只是多生成了一个 UUID。这是一段无用代码，应删除。
3. 出入：讲义说 `os.urandom`，代码用 `uuid`；讲义说两者都是 16 字节，代码（以及 W3C 标准）中 span_id 是 8 字节。代码的长度是对的，讲义的长度描述是错的。
4. 修正：

```python
import os

def new_trace_id() -> str:
    while True:
        tid = os.urandom(16).hex()          # 32 个十六进制字符
        if tid != "0" * 32:                 # W3C：全 0 是无效 ID
            return tid

def new_span_id() -> str:
    while True:
        sid = os.urandom(8).hex()           # 16 个十六进制字符
        if sid != "0" * 16:
            return sid
```

也可以用 `secrets.token_hex(16)` / `secrets.token_hex(8)`。

### Q10 — 参考答案

1. 实测：调用方捕获到的是 `OSError: disk full`，原来的 `ValueError('original')` 只作为 `__context__` 挂在新异常上；`metrics` 仍是空的 `{}`。原因：`finally` 中抛出的异常会**替换**正在传播的异常，并且 `for` 循环中断，后面的 metric 更新代码根本不会执行。业务异常被可观测性组件"顶替"，是最糟糕的结果之一。
2. `close()` 之后 `self.fh` 仍指向已关闭的文件对象（不是 `None`），`_ensure_open` 不会重新打开，`write` 抛 `ValueError: I/O operation on closed file.`（已实测）。`closed` 标志只用来防止重复关闭，没有在 `export` 中检查。
3. 修复思路：

```python
        finally:
            span.end_unix_nano = now_unix_nano()
            if self.metrics is not None:          # 先更新 metric，不依赖导出是否成功
                ...
            for exporter in self.exporters:
                try:
                    exporter.export(span)
                except Exception as exp_err:      # 只吞导出异常，不碰业务异常
                    print(f"[otel] export failed: {exp_err!r}", file=sys.stderr)
                    self.export_errors += 1      # 可再暴露为 metric：otel_export_errors_total
```

`JSONLExporter.export` 也应在 `self.closed` 为真时直接返回或抛出明确错误。生产 SDK 的做法是 `BatchSpanProcessor`：span 结束时只放入内存队列，后台线程批量导出，导出失败只记日志，不影响业务线程。

### Q11 — 参考答案

```python
import functools
import itertools

def wrap_tool_call(builder: SpanBuilder, tool_name: str, parent: GenAISpan | None = None):
    counter = itertools.count(1)

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            attrs = {
                GEN_AI_TOOL_NAME: tool_name,
                GEN_AI_TOOL_CALL_ID: f"call_{next(counter):03d}",
                GEN_AI_OPERATION_NAME: "execute_tool",
            }
            with builder.span("gen_ai.tool.execution", attributes=attrs, parent=parent) as span:
                result = fn(*args, **kwargs)
                if isinstance(result, str):
                    span.attributes[GEN_AI_TOOL_RESULT_BYTES] = len(result.encode("utf-8"))
                elif isinstance(result, bytes):
                    span.attributes[GEN_AI_TOOL_RESULT_BYTES] = len(result)
                return result
        return wrapper
    return decorator
```

要点：

- 复用 metric：`SpanBuilder.span` 在 `finally` 中只要发现 `gen_ai.tool.name` 就会 `inc` counter 并 `observe` 延迟，所以装饰器无需再碰 `MetricsRegistry`。
- 异常：`fn` 抛异常时 `with` 块会标记 ERROR、追加 `exception` event 并重新抛出，装饰器不需要额外 `try`。
- `functools.wraps` 保留原函数名与 docstring，便于工具注册表（第 21 课）读取。
- `parent` 固定在装饰时传入并不理想：真实场景中父 span 是"当前正在进行的模型调用"，应改用 `contextvars` 保存"当前 span"，在 `span()` 中自动取父 span（这也是 OTel SDK 的做法）。

### Q12 — 参考答案

规则：`rank = q × total`（total = `+Inf` 桶 = 100）；找第一个累积计数 ≥ rank 的桶 `(lower, upper]`；估计值 = `lower + (upper − lower) × (rank − count_below) / (count_in_bucket)`。（已用 Python 按此规则计算验证。）

| 分位 | rank | 落入的桶 | 计算 | 结果 |
|------|------|---------|------|------|
| p50 | 50 | `(0, 10]`，桶内 60 个 | `0 + 10 × 50/60` | ≈ 8.33 ms |
| p95 | 95 | `(25, 50]`，之前 90 个、桶内 8 个 | `25 + 25 × (95−90)/8` | 40.625 ms |
| p99 | 99 | `(50, 100]`，之前 98 个、桶内 2 个 | `50 + 50 × (99−98)/2` | 75 ms |

误差：估算假设样本在桶内均匀分布，真实值可能是桶内任意位置，所以误差上界就是**目标桶的宽度**（p99 落在 `(50, 100]`，最坏误差约 50 ms）。想要更准，就要在关心的分位附近（例如 SLO 阈值附近）加密桶边界；若 rank 落在 `+Inf` 桶，`histogram_quantile` 只能返回最后一个有限边界，说明桶设置得太小。

### Q13 — 参考回答要点

- **Trace**：单次请求的因果树（span 及父子关系、每步耗时、attribute、异常 event）。回答"这一次 agent 调用为什么慢/为什么失败、调了哪些工具、用了多少 token、gate 拒绝了什么"。
- **Metric**：预聚合的数值时间序列（counter、gauge、histogram）。回答"read_file 的 p95 延迟""每分钟工具调用量""错误率是否突增"，适合仪表盘和告警，存储成本与请求量无关（只与时间序列数有关）。
- **Log**：离散的文本/结构化事件，信息最全但难以聚合。本节的 `SpanEvent`（如 gate 决策）相当于挂在 span 上的结构化日志。
- 三者通过 `trace_id` 关联：日志里打印 trace_id，metric 用 exemplar 指向 trace。
- 加分点：讲义的三种失败模式恰好对应"没有 trace""trace 不标准""没有 metric"。

### Q14 — 参考回答要点

- **累积桶**：每个 `le` 桶本身就是一个单调递增 counter，便于用 `rate()/increase()` 处理进程重启、跨实例 `sum by (le)` 聚合；需要单桶计数时相减即可。
- **`histogram_quantile`**：先求总数，确定目标 rank，找到 rank 所在桶后线性插值（见 Q12）。误差上限是桶宽；桶太稀会很不准，落到 `+Inf` 只能给出最后一个有限边界。
- **对比 Summary**：Summary 在客户端算好分位数，精确但**不能跨实例聚合**（多个 p95 无法合成全局 p95），且分位数要预先固定；Histogram 可聚合、可事后选任意分位，代价是精度受桶影响、每个 label 组合都要 N+3 条序列。
- **桶边界**：覆盖预期范围，在 SLO 阈值附近加密，避开常见的"刚好等于边界"的值（Q7 的 5 ms 例子）；数量适中（10–20 个）。本节桶 5…10000 ms 与 Prometheus Go 客户端默认桶 `DefBuckets`（0.005…10 s）换算成毫秒后一致；讲义称其为"OTel default"，而 OTel SDK 的默认显式桶还包含 0、75、750、7500 等边界，二者并不相同。
- 加分点：Prometheus 较新的 native histogram 用指数桶自动适配，减少手工选桶。

### Q15 — 参考回答要点

- **可以保留**：attribute key（`gen_ai.*`）、span 名与父子结构、"异常 → ERROR + exception event"的语义、metric 名与 label 设计。
- **需要补的能力**：
  - `TracerProvider` + `Resource`（`service.name`、版本、主机等）；
  - `BatchSpanProcessor` + OTLP exporter（gRPC/HTTP）发往 Collector，异步批量、失败不影响业务（对应 Q10 的问题）；
  - **上下文传播**：用 `contextvars` 自动维护当前 span，跨线程/协程/进程时用 W3C `traceparent` 头传递（本节必须手动传 `parent`）；
  - **采样**：如 `ParentBased(TraceIdRatioBased(0.1))`，错误 trace 尽量保留（tail sampling 在 Collector 做）；
  - metric 改用 OTel Metrics API，由 Prometheus exporter 暴露或经 Collector 转发；
  - 资源上限：attribute 长度、事件数量限制。
- **注意版本**：同课程 [阶段 14 · 23](../../../14-agent-engineering/23-otel-genai-conventions/docs/zh.md) 讲义指出 GenAI 约定大多仍是 experimental，并使用 `gen_ai.provider.name` 表示提供商、用 `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental` 锁定版本；本节仍用 `gen_ai.system`。所以本讲义"OTel never breaks GenAI attribute names"过于绝对，接入时要按所用 semconv 版本核对 key。

### Q16 — 参考回答要点

- **span 设计**：根 span `invoke_agent`（一次任务）→ 每轮模型调用 `chat`（CLIENT）→ 每个工具调用 `execute_tool`（INTERNAL）→ 工具内部的 sandbox 执行、gate 判定可作为子 span 或 event。
- **attribute**：模型 span 记 provider、request/response model、max_tokens、temperature、input/output tokens、response id、finish reason；工具 span 记 tool name、call id、结果字节数、退出码；gate 决策记 `agent.harness.gate.decision/reason`（自定义 key 用独立前缀）。
- **metric**：`tools_called_total{tool,status}`、`tool_latency_ms{tool}`（histogram）、token 用量 histogram/counter、每任务成本、gate 拒绝数 `gate_denials_total{reason_class}`、任务成功率。
- **告警**：工具错误率突增、p95 延迟超 SLO、单任务 token 超预算、gate 拒绝率异常（可能是 prompt 注入或 agent 跑偏）。
- **敏感数据**：默认不记录 prompt/completion 原文（[阶段 14 · 23](../../../14-agent-engineering/23-otel-genai-conventions/docs/zh.md) 讲义："instrumentations SHOULD NOT capture inputs/outputs by default"），需要时存到外部存储，span 上只记引用 ID；对文件路径、命令行参数做脱敏。
- 常见误区：把每个用户、每个文件路径都做成 metric label。

### Q17 — 参考回答要点

- Prometheus 中**每个不同的 label 组合都是一条独立时间序列**。`call_id`、`trace_id`、用户 ID 几乎每次都不同，会让序列数随请求量无限增长（高基数，cardinality explosion），内存与存储暴涨、查询变慢甚至拖垮 Prometheus。本节 histogram 每个 tool 已经产生 14 行（11 个桶 + `+Inf` + `_sum` + `_count`），再乘以高基数 label 就失控了。
- 规则：label 只放**有限且小**的枚举（工具名、状态、模型名）；高基数信息放在 trace attribute 里。
- 从 metric 跳到 trace：使用 **exemplar**——在 histogram 观测值上附带一个样例 `trace_id`（OpenMetrics 格式支持），Grafana 可以从慢桶直接点到对应 trace。
- 加分点：本节代码的 label 值来自 `span.attributes`，若工具名可被模型自由生成（例如模型乱写工具名），也会成为基数风险，应先经工具注册表校验。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 25 Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：本节 span event 记录的 gate ALLOW/DENY 决策来自这里。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：被追踪的工具执行在 sandbox 中运行。
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../27-eval-harness-fixture-tasks/docs/zh.md)：eval 结果与 trace 结合才能定位失败原因。
- [阶段 13 · 20 OpenTelemetry GenAI：端到端追踪 Tool Calls](../../../13-tools-and-protocols/20-opentelemetry-genai/docs/zh.md)：span 层级、必需 attribute、GenAI metric 定义。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../../14-agent-engineering/23-otel-genai-conventions/docs/zh.md)：span 命名、`gen_ai.provider.name`、内容捕获规则与稳定性说明。

### 本节被哪些后续内容用到
- [阶段 19 · 29 基于 Harness 的端到端 Coding Agent](../../29-end-to-end-coding-task-demo/docs/zh.md)：把本节的 span 与 Prometheus 输出接到完整的 coding agent 流程中。
- [阶段 19 · 11 LLM Observability 与评估仪表盘](../../11-llm-observability-dashboard/docs/zh.md)：在 trace/metric 之上构建仪表盘。
- [阶段 14 · 24 Agent 可观测性：Langfuse、Phoenix、Opik](../../../14-agent-engineering/24-agent-observability-platforms/docs/zh.md)：这些平台消费的正是 OTel GenAI span。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：生产环境的后端与采集链路选型。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：用 histogram 度量推理延迟分位数。

### 延伸关键词
`OpenTelemetry` · `OTLP` · `W3C traceparent` · `gen_ai.provider.name` · `BatchSpanProcessor` · `contextvars` · `tail sampling` · `Prometheus exposition format` · `histogram_quantile` · `native histogram` · `exemplar` · `label cardinality` · `RED method`
