# 面试官手册：GenAITrace（13/20）

候选人计时期间不要看。候选人手里只有 README、`genaitrace/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 父 span 是从 traceparent 解出来的 SpanContext 时，也继承它的 trace id 吗？ | "Yes. Local or remote, a child joins its parent's trace." |
| 1 | `link` 遇到父 span 不在列表里的 span 怎么办？ | "It becomes a root of its trace and keeps its parent_span_id. Never drop it." |
| 1 | `OTEL_CAPTURE_CONTENT=true` 算开启吗？ | "No. Exactly 1 turns it on. Anything else, including unset, is off." |
| 1 | 计时那段可以缓存 `link` 的结果吗？ | "No. Each call links the spans it is given." |
| 2 | 能不能改 `from_otlp`，让它接受我写出来的格式？ | "No. Other tools read this file. Write what the module docstring says." |
| 2 | 属性值是 NaN 怎么办？ | "Your call. Say what you chose. The tests don't cover it." |
| 2 | 属性值可以是 tuple 吗？ | "Lists only. The tests never pass a tuple." |
| 2 | 每次 append 要 fsync 吗？ | "No. Flushing is enough here." |
| 2 | 进程写到一半崩了，最后一行不完整呢？ | "Not in this session. The tests only reopen logs that were closed." |
| 3 | response.model 和 request.model 不一样，要报吗？ | "No. The provider may serve a dated snapshot of the model you asked for." |
| 3 | 空字符串算有这个属性吗？ | "No, it's missing. But 0 is a value." |
| 3 | 不认识的 operation，比如 embeddings，要报吗？ | "Yes, as an unknown operation. We only have rules for the three operations this agent emits." |
| 3 | mcp.call 的时长要算进 gen_ai.tool.execution.duration 吗？ | "No. One sample per tool call, from the INTERNAL execute_tool span." |
| 3 | 没通过检查的 span 还算指标吗？ | "Yes. Each span adds whatever samples it can." |
| 4 | traceparent 是大写的十六进制呢？ | "Not usable. Start a new trace." |
| 4 | traceparent 不合法时要让请求失败吗？ | "Never. Tracing must not break the call. Start a new trace." |
| 4 | 两种载体都有 traceparent，当前载体坏了能用另一个吗？ | "No. Read only the active transport's carrier. An unusable active context starts a new trace." |
| 4 | `_meta` 里已有的字段要保留吗？ | "Yes, all of them." |
| 4 | HTTP 下 body 的 `_meta` 也要写一份吗？ | "No. The header carries it over HTTP." |
| 4 | 可以起一个后台线程定时导出吗？ | "Not here. Send from inside on_end, tick or shutdown, so the tests can see when." |
| 4 | shutdown 之后又有 span 结束呢？ | "Drop it quietly. Don't raise." |
| 5 | 子 span 比父 span 还长（时钟偏差）怎么算？ | "Clip it to the parent, as the docstring says." |
| 5 | 关键路径是不是“最长的那条链”？ | "It's the chain whose self times add up to the most. Read the docstring." |
| 5 | 两个子 span 一样重呢？ | "The smaller span id." |

## 每关：要看什么、提示、追问

### Part 1 修 agent 的 trace（目标 10 分钟）

一个测试里叠了 4 个缺陷和 1 组护栏：

1. `Tracer.start_span` 有父 span 时仍然生成新的 trace id。错误不在 tracer 里报出来，而是在 `link` 的结果上：一次运行被拆成 9 个 trace（`assert 9 == 1`），每个 span 都成了自己那个 trace 的根。
2. `fake_mcp_call` 把 `mcp.call` 写成 INTERNAL。docstring 和讲义都说跨进程的调用（LLM 提供方、MCP server）是 CLIENT。
3. `content_capture_enabled` 写成 `!= "0"`。环境变量没设时取到的是 None，不等于 `"0"`，于是默认就把 prompt、completion 和工具参数写进了 span 事件。报错出现在测试检查事件的地方，根因在 `Tracer.__init__` 调用的这个函数里。
4. `link` 为每个 span 线性扫描全部 span 找父节点，是 O(n²)：6,500 次工具调用（13,003 个 span）要 1 到 2 秒，按 (trace id, span id) 建索引后是 5 到 13 毫秒。限值是 0.12 秒。
5. 护栏：改成索引以后，父 span 不在这批里的 span（测试里是一个子 agent 的根，它的父 span 在调用它的那个进程里）必须留下，作为所在 trace 的根，并且保留 parent_span_id。`by_id[...]` 会 KeyError，`continue` 会把它丢掉，把 parent_span_id 清成 None 会让后端接不上调用方。只按 span id 建索引也不行：span id 只要求在一个 trace 里唯一，测试里有一个 trace 的父 span id 恰好等于另一个 trace 的根，还有一批 span id 完全相同、trace id 不同的重放数据。trace 按各自第一个 span 出现的顺序返回，先按 trace id 排序再分组（`sorted` 加 `groupby`）会挂在 `traces come in the order their first span appears`。另外几条：同一个 tracer 跑两次要得到两个 trace（“每个 tracer 一个 trace id”的改法会挂）；`OTEL_CAPTURE_CONTENT` 为 `0` 或 `true` 都不开，为 `1` 必须开；`tool.execute` 仍是 INTERNAL。

看什么：是不是先看 trace id 的实际值，而不是盯着断言改；会不会想到 `link` 本身没错，是喂给它的数据错了；每改一处就重跑。

提示：
- H1："How many traces did one run produce? Print each span's trace id."
- H2："Where does a child span get its trace id from?"
- H3：直接指出 `start_span` 里 `trace_id=` 那一行。

追问：
- "Why is mcp.call CLIENT but tool.execute INTERNAL?"（跨进程边界、去调用别人的是 CLIENT；进程内的步骤是 INTERNAL；服务端处理请求的那个 span 是 SERVER）
- "Why is content capture off by default?"（payload 大、可能含 PII。讲义：Review carefully before enabling in prod。截断不等于脱敏）
- "Span ids are 64 random bits. Why key the index by trace id too?"（这里的约定只要求 span id 在一个 trace 里唯一；合并多个来源、重放数据时只按 span id 查会撞，用 (trace id, span id) 定位才可靠）
- "A parent span arrives in a later batch. What should a trace backend do?"（先把子 span 当根放着，父到了再接上；所以 parent_span_id 一定要保留）

### Part 2 span 日志（目标 12 分钟）

候选人要写 `encode_value`、`to_otlp` 和 `SpanLog`。读取端 `from_otlp` 是给定的，而且很严格。

坑：
- 纳秒时间戳（约 1.77e18）远超 2^53。Python 的 json 读写整数是精确的，但这个文件还要给 JavaScript、jq 这类把数字当 double 的工具读，所以 docstring 规定 64 位整数（时间戳、intValue）一律写成十进制字符串。测试用 `json.loads(line, parse_int=float)` 模拟这种读者，时间戳、事件时间和 `2**53 + 1` 都要原样读出来。
- 写成数字的话，给定的 `from_otlp` 先报 `a timestamp is a decimal string of nanoseconds` 或 `bad AnyValue`。改读取端去迁就写法，会在“double 读者”那几条断言上挂。
- `isinstance(True, int)` 为真：要先判 bool 再判 int，否则 True 写成 intValue `"1"`，读回来是 1。
- 1.0 要写成 doubleValue。看 `value.is_integer()` 就写 intValue，1.0 会读回成 1。
- int 必须在有符号 64 位范围内，`2**63 - 1` 和 `-2**63` 本身合法，测试里两个边界都有；`2**63` 和 `-2**63 - 1` 要拒绝。
- 数组里的值必须是同一种标量：`[True, 1]`、`[1, True]`、`[1, 2.5]`、嵌套列表都拒绝。用 isinstance 判断同类会放过 bool 和 int 混在一起的数组；只拿第一个元素的类型去比，会放过 `[1, True]`。空数组合法。
- None、dict 要报 ValueError，不能转成字符串写进去。
- 事件按记录的顺序写，名字可以重复（一次回复里两个 `gen_ai.content.tool_call`）。按名字建 dict 会丢一个。
- 根 span 的 parentSpanId 写空字符串，不是 null。
- 日志用追加模式打开，`"w"` 会在重开时清掉前面的 span。新建的日志 `spans()` 返回空列表，不能报 FileNotFoundError。
- 测试只在 close 之后重新打开日志来读，append 里不 flush 也能通过。可以追问：同一个 SpanLog 刚 append 完就调 `spans()`，读得到刚写的那行吗？docstring 要求读得到，答案是每次 append 后 flush。
- 没结束的 span、写不了的属性都要在动文件之前报 ValueError，文件保持原样。

追问：
- "The process dies in the middle of a write. What does your reader do?"（本题不考；做法是只认以换行结尾的完整行，见 13/01 的会话日志）
- "Why not pickle the spans?"（别的语言、别的工具要读，而且 pickle 读进来就是执行代码）
- "NaN in an attribute?"（JSON 本身没有 NaN；要么拒绝，要么约定一种字符串写法，读写两端一致）
- "The log grows without bound."（按大小或时间轮转，导出成功后删除）

### Part 3 语义约定与指标（目标 12 分钟）

坑：
- 0 是值，空字符串是缺失：`if not attrs.get(key)` 会把 `output_tokens = 0` 当成缺失；只查 `key in attrs` 会放过 `gen_ai.tool.call.id: ""`。
- response.model 和 request.model 不同不是问题。讲义的例子就是请求 `gpt-4o`、服务的是 `gpt-4o-2024-08-06`，agent 自己的 span 正是这样，`check(run)` 必须为空。
- execute_tool 的 span 可以是 INTERNAL（agent 自己执行），也可以是 CLIENT（MCP 往返）。只允许 INTERNAL 的话，agent 自己的三个 mcp.call 全被报出来。
- 没有 `gen_ai.operation.name` 的 span 不检查。有但不认识的（测试里用的是 OpenAI API 的名字 `chat.completions`）报 `unknown operation`，然后这个 span 不再查别的；忘了 `continue` 会在 `ALLOWED_KINDS[op]` 上 KeyError。
- 一个 span 的问题先报 kind，再按 REQUIRED 的顺序报缺失的属性。按名字排序会挂。
- scrub 只删 CONTENT_EVENTS 里的三种事件，其余事件按原顺序留下；不能改传进来的 span（测试比较了调用前后）；capture 开着时什么都不删。
- 直方图：正好等于边界的值属于以这个边界为上界的桶，用 `bisect_left` 或 `<=`；`bisect_right` 和 `<` 会把它放进下一个桶。大于最后一个边界的值进最后一格。
- token 按 input 和 output 分开；0 个 token 也是一个样本，`if value:` 会漏掉；每个计数单独成为一个样本：测试里有一个流被中途切断的 chat span，只有 input_tokens、没有 output_tokens，它照样贡献一个 input 样本和一个时长样本。“两个计数都在才记”会少一个 input 样本，用 `attrs[...]` 取值会 KeyError。
- chat span 按 `gen_ai.operation.name` 认，不按 span 名：测试里有一个叫 `llm.stream` 的 chat，还有一个叫 `llm.chat` 但 operation 是 `chat.completions` 的 span。工具 span 也一样，`tool.search` 也是工具调用。
- 一次工具调用一个样本：只算 INTERNAL 的 execute_tool span，里面那个 CLIENT 的 mcp.call 是同一次调用的一部分，算进去样本数会翻倍。按 `gen_ai.tool.name` 分组，不按 call id。
- operation.duration 按请求的模型分组，不按服务的模型。
- 时长是 `(end_ns - start_ns) / 1e9`。写成 `* 1e-9` 的话，75 ms 会算成 0.07500000000000001，越过 0.075 这个边界，落进下一个桶。

追问：
- "Why not put the call id on the metric?"（每个 call id 一条时间序列，序列数会爆炸；call id 留在 span 上就够了）
- "How do you get p95 out of these buckets?"（找累计计数刚过 95% 的那个桶，在桶内插值；精度取决于桶边界）
- "Where does scrub run in production?"（导出之前的 processor 里，或者 Collector 里。源头默认不采集，导出前再删一遍，两道保险）
- "What would you alert on?"（讲义的技能文件建议首先看 p95 的 gen_ai.client.operation.duration）

### Part 4 传播与分批导出（目标 14 分钟）

坑：
- 每次注入都使用本次传入 span 的 context，替换当前载体里已有的旧值。不能用 setdefault 留住旧 traceparent，也不能让同一个 base request 的两次注入共享可变状态，后一次覆盖前一次。
- 提取只读当前 transport 的载体：HTTP 读 header，stdio 读 params._meta。另一载体即使有合法 context 也不能优先读取或作为 fallback；当前载体缺失或不合法就返回 None。
- 原请求、其他字段和非当前载体不变。HTTP 下 body 中原有的 traceparent 保留；stdio 下无关 headers 保留。保留 _meta 的 progressToken，没有 params 的 stdio 请求要补上 params。只复制顶层 dict 会改到调用方的嵌套对象。
- agent 用本次 mcp.call span 注入；receiver 的 SERVER span 继续这个 trace，并以本次 call 的 span id 为 parent。同一模板发出的两次调用不能沿用第一次的 parent。
- 第 max_batch 个 span 结束的那次 on_end 里就要发出去，测试比较的是发送时刻和这批最后一个 span 的结束时刻。只在 tick 里发、条件写成 `>`、每个 span 单独发，都会挂。
- tick 用 `>=`；等待时间从 span 入队时（on_end 被调用时，按导出器的时钟）算起，不是从上一次发送算起，不是从最新入队的 span 算起，也不是从 span 自己的 end_ns 算起：测试里的 a 结束时带了 3 秒前的 end_ns，用 end_ns 计时会让它一入队就超时。队列为空时 tick 什么都不发，也不能因为没有“最早的 span”而报错。
- shutdown 把剩下的发出去；之后结束的 span（包括一直在跑、shutdown 之后才结束的那个）静静丢掉，不能抛异常，也不能留到下一次 tick 发出去。
- 请求是 UTF-8 bytes，结构是 resourceSpans → scopeSpans → spans，service.name 写成 OTLP 属性（`{"key": ..., "value": {"stringValue": ...}}`），批内按结束顺序。一个 span 一个 resourceSpans 不对。
- 端到端那段把 Part 2 的 `to_otlp` 也用上了：导出的每个 span 解码回来，要和 tracer 里的 span 完全一样。

给定 helper 护栏：`parse_traceparent` 已完整正确实现；格式测试和错修保护这个给定实现。它只接受本题声明的 version、长度、小写十六进制、非零 id 和完整字符串，坏值返回 None，不让追踪故障影响工具调用。候选人无需重写这个 parser；用 re.match 加 ^...$、int(x, 16)、扩大字符集或抛异常的退化仍会被测试抓住。

追问：
- "The collector is down. What happens to the queue?"（队列要有上限，满了按策略丢并计数；重试带退避；绝不能阻塞 agent）
- "In production the flush runs on a timer thread. What changes?"（队列要加锁；shutdown 要等正在进行的发送结束；测试改用显式的 tick 就是为了不依赖真实时间）
- "Who decides sampling?"（traceparent 的 flags 带着上游的采样决定；要按慢请求采样就得等整个 trace 到齐，即尾部采样）
- "The lesson calls `_meta.traceparent` an interim field. What if the spec settles on another name?"（extract 在过渡期同时认新旧两种，inject 按对端支持的写）

### Part 5 时间花在哪（目标 12 分钟）

坑：
- self time 是时长减去子 span 区间并集的长度。并行的子 span 直接把时长相加，慢的那次运行的根 span 会变成 −1100 ms。
- 求并集前要按开始时间排序。`link` 给的 children 是传进来的顺序，测试按结束顺序传（collector 就是这样交过来的），不排序直接合并，根 span 会算成 150 ms 而不是 50 ms。只取“第一个开始到最后一个结束”也不对：子 span 之间有 50 ms 的空档。
- 子 span 先裁剪到父 span 的区间：服务端时钟偏了几毫秒，一个 SERVER span 在它的 mcp.call 结束之后才结束，另一个在它的 mcp.call 开始之前就开始。两头都要裁。完全落在父 span 之外的子 span（一个不等待的缓存写入）贡献 0，不能贡献负数。
- 最重的链是自身时长加起来最大的那条，不是每一步挑自身时长最大的子 span（会走进最后那个 1.55 秒的 chat），不是挑时长最长的子 span（会走进有两个并行工具的子 agent），也不是取子树里最大的那一个而不求和。
- 平票取 span id 小的。只按权重比较的 `min()`/`max()` 会选先出现的那个。
- 记忆化要按 span id，不能按名字：三个 tool.execute 同名。
- 客户端 span 没到的那个 SERVER span 已经被 `link` 当成根，它自己就是一条链。

追问：
- "Is this heaviest chain the critical path?"（不完全是。按时间倒推的关键路径从根的结束时刻往回找最后结束的子 span，再从它的开始时刻接着往前找，顺序执行的几个子 span 都在路径上。本题的定义能指出慢在哪一支，但不回答“缩短哪个能让整体变快”）
- "Back to the 30-second complaint: what does this trace tell you?"（mcp.call 自身 25 秒，服务端 span 只有 2 秒：时间花在服务端接手之前，也就是冷启动）
- "Clock skew across processes?"（裁剪只是让数字不出错；根本办法是同步时钟，或者在边界两侧各记一次时间，算出偏差）
- "What would you put on a dashboard for this?"（按 mcp.server 分组的 gen_ai.tool.execution.duration 的 p50 和 p99，冷启动表现为长尾）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、打印实际的 trace id 和 span、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出内容捕获和 PII、指标基数、导出背压、采样、时钟偏差 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
