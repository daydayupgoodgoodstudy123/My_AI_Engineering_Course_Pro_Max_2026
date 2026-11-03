# 参考答案讲解：GenAITrace（13/20）

计时结束后再看。参考实现在同目录的 `genaitrace/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 agent 的 trace

**现象**：解锁后的第一个错误是 `one agent run is one trace`，`assert 9 == 1`。`link` 把一次运行拆成了 9 个 trace，可 `link` 本身没错。

**顺着往上找**：把每个 span 的 trace id 打出来，9 个全不一样。trace id 是在 `Tracer.start_span` 里定的：它算出了父 span 的 context，也用 context 填了 parent_span_id，可 `trace_id=` 那一行永远是 `self.ids.trace_id()`。于是每个子 span 都开了新 trace，`link` 在它自己的 trace 里找不到父 span，只好把它当成根。报错在 `link` 的结果上，出错在 tracer 里。

**依次修四处**：

1. `start_span`：`trace_id=context.trace_id if context is not None else self.ids.trace_id()`。父 span 是本进程的 Span，还是 traceparent 带来的 SpanContext，都一样继承。
2. `fake_mcp_call`：`mcp.call` 改成 CLIENT。讲义：调用跨进程边界（LLM 提供方、MCP server）用 CLIENT，agent 自己的循环和工具执行用 INTERNAL。
3. `content_capture_enabled`：改成 `env.get("OTEL_CAPTURE_CONTENT") == "1"`。原来的 `!= "0"` 在没设环境变量时是 `None != "0"`，也就是默认开启，和讲义的 opt-in 正好相反。`bool(...)` 会让 `"0"` 也开启，同样不对。
4. `link`：先建 `{(trace_id, span_id): span}` 索引，再逐个查父节点。原来的 `_find` 每次从头扫一遍，13,003 个 span 要比较一亿多次，1 到 2 秒；索引是 O(n)，几毫秒。

**护栏**：父 span 不在这批里的 span 照样留下，放进所在 trace 的 roots，parent_span_id 原样保留。子 agent 的根就是这样：它的父 span 在调用它的那个进程里，后端拿 parent_span_id 才能把两边接起来。索引的键要带上 trace id，因为 span id 只在 trace 内唯一，测试里放了一批 span id 相同、trace id 不同的重放数据。

## Part 2 span 日志

一行一个 span，内容就是 `to_otlp` 的结果：

```python
def encode_value(value):
    if isinstance(value, bool):                      # 先判 bool：True 也是 int
        return {"boolValue": value}
    if isinstance(value, int):
        if not INT64_MIN <= value <= INT64_MAX:
            raise ValueError(...)
        return {"intValue": str(value)}              # 64 位整数写成字符串
    if isinstance(value, float):
        return {"doubleValue": value}                # 1.0 仍是 double
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        types = {type(item) for item in value}       # 精确类型：bool 和 int 不算一类
        if len(types) > 1 or not types <= {str, bool, int, float}:
            raise ValueError(...)
        return {"arrayValue": {"values": [encode_value(item) for item in value]}}
    raise ValueError(...)
```

`to_otlp` 照模块 docstring 拼字段：时间戳 `str(ns)`，根 span 的 parentSpanId 是 `""`，kind 查 `SPAN_KIND`，属性和事件按原顺序。span 没结束就报 ValueError。`SpanLog` 在构造时用 `"a"` 打开文件（文件不存在就建出来），append 先把整行编码好，再写入并 flush；`spans()` 逐行 `json.loads` 再 `from_otlp`。

为什么时间戳和整数要写成字符串：2026 年的纳秒时间戳约 1.77e18，double 在这个量级上相邻两个值差 256 ns。Python 的 json 自己读写没问题，但日志还会被 JavaScript、jq 这类把数字当 double 的工具读。测试用 `parse_int=float` 模拟这种读者：写成数字，它读到的时间戳就差了几十到上百纳秒，`2**53 + 1` 会变成 `2**53`。

几个类型陷阱：`isinstance(True, int)` 为真，先判 int 会把 True 写成 1；看 `is_integer()` 把 1.0 写成整数，读回来就成了 1；数组只能是一种标量，`[True, 1]`、`[1, True]`、`[1, 2.5]` 都要拒绝，用 isinstance 或者只看第一个元素都会漏。int 的范围是闭区间 `[-2**63, 2**63 - 1]`，两个端点本身合法。

写不了的 span 要在动文件之前报错：先 `to_otlp`，成功了再写。这样文件里永远只有完整的行。

## Part 3 语义约定与指标

`check` 逐个 span：没有 `gen_ai.operation.name` 就跳过；不在 REQUIRED 里就报 `unknown operation` 并跳过；否则先查 kind，再按 REQUIRED 顺序查缺失的属性。缺失的判断是 `key not in attrs or attrs[key] == ""`：0 个 token 是值，空字符串的 call id 不是。

- agent 自己的 span 必须零问题。chat span 的 response.model（`gpt-4o-2024-08-06`）和 request.model（`gpt-4o`）不同，这是讲义说的“实际服务的模型”，不是错误。mcp.call 是 CLIENT 的 execute_tool，也合法。
- `chat.completions` 是 OpenAI API 的名字，不是 GenAI 约定里的 operation 值，正好用来检查“不认识的操作”。

`scrub` 用 `dataclasses.replace` 生成新 span，只滤掉 CONTENT_EVENTS 里的事件，其余按原顺序保留。

直方图的规则是“正好等于边界的值属于以它为上界的桶”：

```python
self.counts[bisect.bisect_left(self.bounds, value)] += 1
```

`bisect_left` 返回第一个 `>= value` 的边界的下标，正好是这个桶；比所有边界都大时返回 `len(bounds)`，就是最后一格。`bisect_right` 会把边界上的值放进下一个桶。

`metrics` 只看 `gen_ai.operation.name`，不看 span 名：

- token usage：chat span 的 input、output 分别记进 `"input"`、`"output"`，值为 0 也记（判断用 `is not None`，不能用真值）。每个计数各自是一个样本：只有 input_tokens 的 chat span（流在输出之前被切断）记一个 input 样本，缺的那个计数不记。
- operation duration：chat span 的时长，按 `gen_ai.request.model` 分组。
- tool execution duration：只记 INTERNAL 的 execute_tool span，按 `gen_ai.tool.name` 分组。一次 MCP 工具调用有两个 execute_tool span，外面的 tool.execute（INTERNAL）和里面的 mcp.call（CLIENT），都记就成了两次调用。按 call id 分组会让每次调用一条序列。

时长用 `(end_ns - start_ns) / 1e9`。整数相除的结果是最接近真值的 double，所以 75 ms 正好等于边界 0.075；`* 1e-9` 先引入了 1e-9 自身的舍入误差，75 ms 会变成 0.07500000000000001，落进下一个桶。

## Part 4 传播与分批导出

`parse_traceparent` 用 `re.fullmatch(r"00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}", value)`，再排除全零的 id，非字符串直接返回 None。三处容易放宽：`re.match` 加 `$` 会接受末尾的换行（`$` 能匹配换行之前）；`[0-9a-fA-F]` 或 `int(x, 16)` 会接受大写（flags 的 `0A` 也一样）；`int(x, 16)` 还接受 `0x`、`+` 和下划线。

`inject` 先深拷贝 message、复制 headers：HTTP 加 `traceparent` 头；stdio 用 `params.setdefault("_meta", {})["traceparent"] = ...`，保留原有的 progressToken。然后在 `fake_mcp_call` 里把请求换成 `inject(request, span)`。这里的 span 是 mcp.call，服务端的 SERVER span 挂在发起调用的 CLIENT span 下面。坏的 traceparent 让 `extract` 返回 None，服务端开新 trace，工具照常返回。

`BatchExporter` 的状态只有三样：队列、最早入队时刻、是否已关闭。

```python
def on_end(self, span):
    if self._closed:
        return
    if not self._queue:
        self._oldest_ns = self.clock()
    self._queue.append(span)
    if len(self._queue) >= self.max_batch:
        self._flush()

def tick(self):
    if self._queue and self.clock() - self._oldest_ns >= self.max_delay_ns:
        self._flush()
```

- 满批在 on_end 里当场发，测试比较的是发送时刻和这批最后一个 span 的结束时刻。
- 等待时间从队列由空变非空的那一刻算起，用的是导出器自己的时钟，发送后清零；从上一次发送算起会在 c 只等了 2 s − 1 ns 时就发。也不能拿 span 的 end_ns 当入队时刻：a 结束时带的是 3 秒前的 end_ns，那样它一入队就算超时。
- 队列为空时 tick 不发、也不去读 `_oldest_ns`。
- shutdown 发完剩下的再关闭；之后的 on_end 直接返回。一直在跑的 span 在 shutdown 之后才结束，也就不会被导出：没有结束的 span 从来不进队列。
- `_flush` 每次最多取 max_batch 个，包成 resourceSpans → scopeSpans → spans，`json.dumps(...).encode("utf-8")` 交给 send。

## Part 5 时间花在哪

```python
pieces = sorted((max(c.start_ns, s.start_ns), min(c.end_ns, s.end_ns)) for c in trace.children_of(s))
```

先裁剪再排序，然后按开始时间合并重叠的区间，跳过裁剪后长度不为正的区间，累加合并后的长度，用 span 的时长减掉它。

- 并行的三个工具让根 span 的子区间互相重叠，并集是 [0, 28.4 s] 加 [28.45 s, 30 s]，所以根的 self time 是 50 ms，正好是工具结果回来以后、第二次 chat 开始之前那段空档。
- Tokyo 那次的 SERVER span 比 mcp.call 晚结束 40 ms（服务端时钟偏了），裁剪后 mcp.call 的 self time 是 25.07 s。
- 不等待的缓存写入完全在 chat 结束之后，裁剪后长度为负，跳过。

`critical_path` 先算每个 span 的子树权重：自身时长加上最重的那个子树。从根开始，每一步走进权重最大的子 span，平票取 span id 小的，直到叶子：

```python
path.append(min(children, key=lambda c: (-weight(c), c.span_id)))
```

慢的那次运行，链是 invoke_agent → Tokyo 的 tool.execute → mcp.call → SERVER span。mcp.call 自身 25 秒，服务端 span 只有 2 秒：时间花在服务端接手之前，这就是讲义里那次排查找到的 MCP server 冷启动。快的那次说明不能按时长挑：子 agent 的时长是 1.2 s，可它的两个工具并行，走进去的链只有 1.15 s，比 1.18 s 的那次 chat 轻。第三条说明要求和而不是取最大值：tool.execute 自身 0.6 s、里面的 mcp.call 0.6 s，合起来 1.2 s，比 1 s 的 chat 重。最后一条是平票。

这个“最重链”是简化的定义。按时间倒推的关键路径会把顺序执行的几个子 span 都算进去，回答的是“缩短哪个能让整体变快”。最重链只能指出慢在哪一支。

## 这套题证明了什么，没证明什么

通过了说明你能顺着一个 trace 的错误形状找到 tracer 里的根因，分得清 CLIENT 和 INTERNAL，知道内容捕获为什么默认关闭；能把 span 精确地写进别的语言也读得准的 JSON；能按 GenAI 约定检查属性、按显式桶聚合讲义里的三个指标；能在 MCP 的两种传输上传播 traceparent，并按大小和时间分批导出 OTLP/JSON；能用区间并集算 self time，找出慢请求花时间的那一支。它不涉及真正的 OpenTelemetry SDK、OTLP 的 protobuf 编码和网络发送、Collector、采样、上下文在线程和 asyncio 任务之间的自动传递（测验 Q12 的 `contextvars`），也不涉及 Langfuse、Phoenix 这类后端。
