# 面试官手册：Fanout（13/03）

候选人计时期间不要看。候选人手里只有 README、`fanout/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 每个事件都带 id 吗？ | "No. Only call_start carries the id and the name. Later events carry the index, the way OpenAI streams it." |
| 1 | 回复按调用顺序还是完成顺序？ | "Completion order, each with its tool_call_id. The model matches results by id." |
| 1 | 执行器失败了要不要重试？ | "No. Answer that call with the error. The model decides what to do next." |
| 1 | run_parallel 要不要限制并发数？ | "Not here. Every call starts at once. Limits come in Part 3." |
| 2 | 每次 append 都要 fsync 吗？ | "Flush, yes: the record has to be in the file when append returns. fsync is your call. The tests can't tell." |
| 2 | 文件中间坏了怎么办？ | "Out of scope. We only ever append, so only the last record can be torn." |
| 2 | resume 要不要再写一条 started？ | "No. The call already has one. Log only the answer." |
| 2 | resume 的结果按什么顺序？ | "Any order. Each answer is logged once." |
| 3 | 好几个调用在等空位，谁先？ | "The one that has waited longest. Calls that became ready at the same moment go in declaration order." |
| 3 | 被跳过的调用占不占位置？ | "No. It never runs." |
| 3 | 一个调用依赖它自己？ | "That's a cycle. ValueError." |
| 3 | 环前面的调用反正会失败，还要报错吗？ | "Yes. A cycle makes the turn malformed. Reject it before you simulate anything." |
| 3 | latency 会是 0 吗？ | "No. Latencies are positive integers." |
| 4 | 要等 finish 再输出吗？ | "No. Write each line the moment you know it." |
| 4 | call_cancel 会不会在 call_stop 之后来？ | "No. The model only cancels a call it is still writing." |
| 4 | call_stop 时参数解析失败怎么办？ | "Report that call as an error and keep going. The tests don't cover it." |
| 4 | finish_reason 是 tool_calls，但还有调用没收到 call_stop？ | "Same as length: report it as incomplete and don't run it." |
| 5 | 成员什么时候算完成：字符串的右引号，还是后面的逗号？ | "Either. The tests only look between members, and never at a value that can still grow." |
| 5 | 键重复了怎么办？ | "The last one wins, like json.loads. The tests don't cover it." |
| 5 | 顶层可以是数组吗？ | "No. Tool arguments are always an object. Anything else fails on the first character." |

## 每关：要看什么、提示、追问

### Part 1 修扇出代码（目标 12 分钟）

一个测试里叠了 4 个缺陷和 3 组护栏：

1. `StreamAccumulator.on_event` 用 `event.get("id")` 找缓冲区，可只有 call_start 带 id。之后的分片和 call_stop 拿到的键都是 None，`defaultdict` 一声不响地给它们建了同一个缓冲区，三个调用的片段混在一起。错误不在这里报：到第一个 call_stop，`CallBuffer.to_call` 解析 `{"city"{"city: "Zur{"city": "Bengich"}` 时报 JSONDecodeError。报错的地方离根因隔了一层调用。
2. `replay_and_execute` 用 `asyncio.as_completed` 按完成顺序收结果，再和 `in_flight` 的键（call_stop 的顺序）zip。乱序完成时城市和 tool_call_id 错配：call_A 拿到了 Bengaluru 的结果。这正是讲义说的 id 关联陷阱：`as_completed` 给出的 future 不告诉你它属于哪个调用。
3. 执行器抛错没人接：`answer` 没有 try，replay 里的任务又直接跑执行器。Atlantis 抛出 LookupError，整个 replay 跟着抛出去，Tokyo 的结果也丢了。docstring 写的是失败的调用要回一条错误消息。
4. `run_parallel` 看上去用了 `create_task`，其实每建一个任务就马上 await，等于串行。250 个各 sleep 8 ms 的调用要 2.4 秒左右，测试要求 0.2 秒内（修好后约 12 ms）。
5. 护栏一：每个调用恰好执行一次；只能在自己的 call_stop 之后开始；又要在流还没读完时就开始。三种常见改法各挂一条：每来一个分片就试 `json.loads`，能解析就提前执行（讲义的 parse-early 陷阱）；先收齐整轮再统一 `run_parallel`；修 zip 时留着旧的执行器任务、又建一批 answer 任务，结果执行了两次。
6. 护栏二：回复按完成顺序，失败也算在内。把 `as_completed` 换成 `gather` 能修好错配，但顺序变成了 call_stop 的顺序，会挂在 "reply in completion order"。run_parallel 同理：小批次里 Atlantis 和时钟服务立刻失败，必须排在最前面。只接 LookupError 的写法会被时钟服务的 ConnectionError 打穿。
7. 护栏三：250 个调用要同时在跑。出于“别把下游打爆”的好意给 run_parallel 加 `asyncio.Semaphore(16)`，或者每批 25 个分批跑，0.2 秒的计时照样能过，但测试会数同时在跑的调用有几个，挂在 "every call of the turn is in flight at once"。限流放在 Part 3，澄清问题里也是这么回答的。

看什么：是不是先打印 `buf.chunks` 看实际数据；是否意识到 JSONDecodeError 不是 `to_call` 的错；有没有想清楚“这个结果属于哪个调用”；改并发时是否同时顾到完成顺序。

提示：
- H1："Print the buffer's chunks right before to_call. Whose fragments are those?"
- H2："Which events carry an id? What key does an args_delta land under?"
- H3：直接指出 `event.get("id")`、zip 那一行和 `await asyncio.create_task(...)`。

追问：
- "The lesson says order in the reply doesn't matter for correctness. Why reply in completion order anyway?"（讲义：OpenAI 和 Anthropic 只看 id，Gemini 只要 id 对得上也接受任何顺序；按完成顺序加显式 id，结果丢了或重复了更好查）
- "When would you turn parallel calls off?"（讲义：有顺序依赖，比如先 create_file 再 write_file；一个调用的输出是另一个的输入；下游限流扛不住扇出。OpenAI 设 `parallel_tool_calls: false`，Anthropic 设 `disable_parallel_tool_use: true`）
- "Your executors are blocking HTTP clients, not coroutines. What changes?"（`asyncio.to_thread` 或线程池，就是课里代码的 ThreadPoolExecutor；等 I/O 时会释放 GIL，CPU 密集的不会变快）
- "Gemini 2 matched results by name. What breaks?"（讲义：同一个工具的两个并行调用分不清，这和第 2 个缺陷是同一类问题）

### Part 2 调用日志（目标 12 分钟）

坑：
- 布局照 docstring：4 字节大端长度、1 字节状态、2 字节大端 id 长度、id、负载。长度数的是 UTF-8 字节。负载里有 "°C"、"Föhn"、"Zürich"、"🌧"，用 `len(str)` 会少算字节，第一条字节比对就挂。
- append 返回时记录就要在文件里：测试在 close 之前直接读文件。不 flush 的话数据还在缓冲区里，读到的是空的。
- 负载里有 `\n` 和 `\r\n`。用换行分隔记录不行；按文本模式读，`\r\n` 会变成 `\n`，重开后读回不一致。
- 先校验再写：被拒绝的记录（第二个答案、第二次 started、没 started 就 done、未知状态）不能进文件，重开后要读回一模一样的四条。
- “每个调用只有一个答案”在重开后也要成立，已经回答过的调用要从文件里重建，不能只记在内存里。
- in_flight 按日志顺序：日志里 call_C（Bengaluru）在 call_B（Tokyo）前面。用 started 的集合减去 done 的集合、再按 id 排序，会挂在 "in log order"。不排序、直接遍历集合的话，顺序随 PYTHONHASHSEED 变，这条断言时过时不过。候选人碰到偶发失败时，看他能不能想到这里。
- 尾部半条记录：长度字段不全（只剩 1 或 3 个字节）、只有长度、长度加一部分正文，都要丢掉，前面的记录完好。少于 4 个字节时别去解析长度，正文不够时别去解析头部，否则是 struct.error。反过来，只靠捕获 struct.error 判断残尾也不够：切在 id 中间（cut 9）时头部能解析，字节切片又不报错，会读出一条只有半个 id 的记录。要拿长度字段和剩下的字节数比。光丢掉不截断也不行：之后 append 的记录接在残片后面，再读就错位。测试会接着 append 一条再读回来。
- 测试里的 call id 都是 ASCII，id 长度按字符数算也能过。看到这种写法就问一句：id 里有非 ASCII 字符时，读回来还对吗？
- `resume` 只重跑没有答案的调用，各一次；只写 done，不再写 started（会撞上 started 只能有一次的规则）。参考实现用的是 Part 1 的 `run_parallel`。

追问：
- "Why not fsync on every append?"（每次 fsync 很慢；可以按批提交，或者在把结果交回模型之前 fsync 一次。flush 只保证交给了操作系统，断电还会丢）
- "A record's length survives but the bytes after it are garbage. How would you notice?"（每条记录加 CRC32，校验失败就当作尾部损坏）
- "Re-running an in-flight call: what if it already charged a card?"（有副作用的工具要幂等：拿 call_id 当幂等键，或者重跑前先查一下是不是已经做过）
- "The log grows forever."（按轮次轮转；压缩时只保留还在飞的调用）

### Part 3 扇出调度（目标 10 分钟）

坑：
- 讲义的基准：并行耗时是 max（800 ms），串行是 sum（1800 ms）；limit 为 1 就是串行；空列表返回 `Plan({}, 0, 0)`。
- 依赖要全部 ok 才就绪。只等任意一个的话，summary 会在 400 就开始。
- 等位的调用先来先服务。按声明顺序挑，write_file（100 时才就绪）会插到 tokyo（0 时就在等）前面。这和 `asyncio.Semaphore` 的行为一致：先排队的先拿到。
- 同一毫秒结束的调用要全部处理完，再开始新调用，新就绪的按声明顺序排队。一个一个处理，或者按完成的先后把下游排进队列，after_a 都会排到 after_b 前面。
- 失败的调用自己算运行过，计入 wall_ms 和 serial_ms；下游不管隔几层都跳过，跳过的不占位置、不计时间。chain 里 notify 声明在 upload 前面，而且 zip 失败是最后一个事件，只扫一遍的写法会把 notify 一直留在等待状态（用“模拟完还在等的就是环”来查环的话，它还会被误报成环）。
- slots 按声明顺序排。边模拟边往 dict 里放，顺序就成了开始的顺序，挂在 "slots are listed in declaration order"。
- 未知依赖、环、重复 id、limit < 1 都是 ValueError，都要在模拟之前查。未知依赖留到模拟时会变成 KeyError。环也一样：“模拟完还在等的就是环”这种查法，会漏掉测试里那个挂在失败调用后面的环。create_file 失败后，write_file 和 read_file 都被当成下游跳过，什么也没剩下，于是不报错。在依赖图上查：Kahn 算法（反复拿掉已经没有依赖的调用，拿不完就是有环）或者 DFS 三色标记。

追问：
- "Exercise 1: when does parallel stop mattering?"（max/sum 接近 1 的时候：一个调用远比其他的慢）
- "Where do the dependencies come from in production?"（讲义练习 4 的 ordering_dependency；本课 skill 给注册表加 `ordering_deps`；也可以按资源推断，对同一个文件的写操作串行）
- "One limit for the whole turn, or one per downstream API?"（本课 skill 的 `rate_limit_group`：打同一个下游的工具共用一个上限）
- "The real host drifts from this plan. Why?"（调度开销、延迟抖动、重试；可以把模拟当基线，和实测的起止时间对比）

### Part 4 流式结果（目标 14 分钟）

坑：
- 一行一个 JSON 对象，换行结尾；格式由测试的 `"".join(...)` 加 `splitlines()` 再 `json.loads` 决定。缺换行报 Extra data，`indent=2` 报 JSONDecodeError。
- 第一行要在流还没结束时就输出。测试里的“模型”写到一半会停下来，等 call_A 那一行出来才继续，等 1 秒还没等到就算失败。只在两个事件之间看一眼有没有完成的调用也过不了：那时你正卡在 `async for` 里等下一个事件。要有一个单独读流的任务、结果从队列里出，或者用 `asyncio.wait` 同时等“下一个事件”和正在跑的调用。用 `asyncio.wait_for(anext(...), timeout)` 轮询也不行：超时会取消正在等的 `__anext__`，CancelledError 被抛进模型那一侧的生成器，流就断了，call_B 再也不会来。
- 调用要并发跑。在 call_stop 处直接 `await` 执行器，第一个探针能过，但 Zurich 会挡住后面所有事件，行的顺序就错了。
- call_cancel 要丢掉缓冲并马上输出 cancelled。不丢的话 finish 时它又会被报成 incomplete；攒到 finish 再输出，顺序就错了。
- finish 时还没收到 call_stop 的调用一律 incomplete，不执行，在 finish 时就输出，不等还在跑的调用。call_D 的参数 `{"city": "Bengaluru"}` 已经是合法 JSON，“能解析就执行”的写法会把它跑掉，这就是讲义说的 parse-early 陷阱。
- 执行器抛错只影响自己那一行；生成器要等所有已经开始的调用都回答了才结束。finish 时把还在跑的调用取消掉也不对，call_B 会没有结果。
- content 放执行器返回的原值。照搬 `tool_message` 写成 JSON 文本，测试解析出来是字符串，和对象不相等。
- 写成普通的 async 函数（只有 return、没有 yield）时，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出来这里需要 async generator。

追问：
- "OpenAI's stream has no per-call stop. How would you know a call is complete there?"（讲义：等 finish_reason 为 "tool_calls" 再解析；想更早，就用 Part 5 那样的增量解析器）
- "The client disconnects mid-stream. What still runs?"（生成器的 finally 里要取消读流的任务和正在跑的调用；有副作用的调用要想清楚取消意味着什么）
- "The consumer reads slower than the tools finish. What grows?"（无界队列；换成有界队列，背压就传到读流那一侧）
- "Should incomplete calls go back to the model?"（应该：每个调用都有一条结果，写明是被截断的，让模型决定重发还是放弃）

### Part 5 增量参数解析（目标 12 分钟）

坑：
- 讲义的例子：`{"q": "a}b"` 里的 `}` 在字符串里，什么也没关上。数花括号会说已经完整。
- 转义：`\"` 不结束字符串；`\\"` 里反斜杠本身被转义了，引号会结束字符串。只看“前一个字符是不是反斜杠”的写法在 `"C:\\"` 上出错。转义状态要跨 chunk 保存，反斜杠可能正好是上一块的最后一个字符。
- 每个转义都要算对。完全不管转义、见引号就当字符串结束的写法，在 `"a\"}b"` 上会把对象提前关掉，然后报错。
- 只有顶层的逗号分隔成员；嵌套数组和对象里的逗号、字符串里的逗号和冒号都不算。
- 成员的值要解码：键 `ci\u0074y` 是 "city"，`\ud83c\udf27` 是一个 emoji。最省事的做法是一个成员结束时对它的原文做一次 `json.loads("{" + text + "}")`，结构和转义都交给标准库。逐字符自己解码的写法要处理切开的 `\uXXXX` 和代理对。
- 还能变长的值不能列出来：块在 `"n": 1` 处断开时，n 可能是 12。“每块结束时试着解析当前成员”的写法挂在这里。
- 完整之后只能有空白（JSON 的空白包括 `\n`，测试里有结尾带换行的参数）；顶层只能是对象；括号要配对；`{"a": 1,}` 这样多余的逗号要报错。
- 一个成员里的错误，最迟在它后面的逗号到达时报出。测试里最后那一块只送到逗号后面，没有右括号：逗号处解析失败就先跳过、等右括号到了再整体 `json.loads` 校验的写法，会挂在 DID NOT RAISE。

追问：
- "Why not call json.loads on the whole buffer after every chunk?"（每块都从头解析是 O(n²)，而且只能告诉你完整没完整，说不出哪些成员已经定了）
- "The UI wants to show the city while it is still being typed."（对没关上的字符串做部分解码，标成“输入中”）
- "Could this replace call_stop as the signal to run a call?"（不能。讲义说正确的闸门是 provider 的结束信号；参数完整了也可能被取消，Part 4 的 call_cancel 就是这种情况。增量解析用来做 UI 和提早发现坏参数）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出限流、崩溃恢复、取消、背压、幂等 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
