# 面试官手册：AgnoMastra（14/18）

候选人计时期间不要看。候选人手里只有 README、`agnomastra/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 题里没有真实模型。每个模型都是测试里的确定性函数，候选人不需要也不应该联网。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 实例化太慢，能不能把 agent 缓存起来复用？ | "No. Every request gets a fresh agent. Make creating one cheap instead." |
| 1 | 能不能给每个 agent 一份注册表的浅拷贝，免得它改到共享的那份？ | "No. Agents only read the registry, so they all share the app's one. A copy makes every request pay for the whole registry." |
| 1 | 工具参数不对，要不要中止整个 run？ | "No. Record the error in the trace and go on with the next call." |
| 1 | schema 里没列的多余参数怎么办？ | "Not covered today. The lesson's check only looks at the fields the schema lists." |
| 1 | 参数里某个字段是 None，算缺字段吗？ | "No. The field is there and its value is null. Report its type." |
| 1 | 一个调用既缺字段又有类型错，报哪一个？ | "Whichever field comes first in the schema." |
| 2 | run id 里会有斜杠吗？ | "Yes. The scheduler uses ids like nightly/2026-11-02. Store them, and keep every file inside workflows/." |
| 2 | run id 最长有多长？ | "No limit. Backfill runs list every date they cover, so some ids are a few hundred characters long." |
| 2 | 旧的快照要保留吗？ | "No. One snapshot per run, the latest one." |
| 2 | 能不能全放进 SQLite？ | "No. Memory, workflows and observability each go to their own backend, as the docstring says." |
| 2 | 要不要原子写、fsync？ | "Not for this exercise. Tell me what you would do in production." |
| 3 | rate 的单位？ | "Requests per second." |
| 3 | rate 可以是 0 吗？ | "Yes. An idle service still has a max_rate." |
| 3 | 端到端延迟要算排队时间吗？ | "No. latency_ns is the sum of the service times." |
| 3 | 结果用 float 还是精确值？ | "Exact. The fields are Fractions." |
| 4 | 客户端中途断开怎么办？ | "Store nothing for that request, and the session must be usable again right away." |
| 4 | 客户端读到最后一块就断开了，这一轮算不算完成？ | "Yes. It already has the whole reply, so the turn must be stored before the last chunk goes out." |
| 4 | 模型吐出空 token？ | "Skip it. An empty chunk would end the response." |
| 4 | “按开始的顺序”指什么？ | "The order in which handle() is first iterated." |
| 4 | 要不要发 Content-Length？ | "No. Use the HEADERS constant; chunked responses don't carry a length." |
| 5 | 顶层的 optional 怎么处理？ | "The same as anywhere else." |
| 5 | 非 strict 的对象里多余字段算不算错？ | "No. They're ignored." |
| 5 | 同一个子工作流能在一个工作流里用两次吗？ | "Yes. Reusing a flow is fine. Only a flow that contains itself is an error." |
| 5 | 有好几处不兼容时报哪一个？ | "The first one, in the order the docstring gives." |

## 每关：要看什么、提示、追问

### Part 1 修运行时（目标 10 分钟）

一个测试里叠了 4 个缺陷和 3 个护栏：

1. `AgnoApp.__init__` 只建了一个 `Agent`，`handle` 每个请求都复用它。memory 跟着这个对象越积越多，会话 s2 看得到 s1 的内容。课里的 `main()` 也是只建一个 agent、传给每一次 `agno_request_handler`，那里的 agent 没有 memory，看不出问题。课里说的是 "each request starts a fresh agent; session state lives in a DB"。
2. `MastraAgent.run` 发现参数不符合 `input_schema` 以后记下了错误，却没有 `continue`，工具照样被调用。错误不在 `run` 里报出来，而是在测试里的 `search` 工具里报 `AttributeError: 'int' object has no attribute 'lower'`。
3. `check_input` 遍历的是调用方传来的 `args`，不是 schema，所以缺了必填字段的调用照样通过检查。第 2 处修好以后才露出来：`("search", {})` 通过了检查，`run` 调用测试里的 `search` 时报 `TypeError: ... missing 2 required positional arguments: 'query' and 'limit'`，原因却在 `check_input`。docstring 写的是 schema 列出的字段都必填，缺了就返回 “missing field <key>”，工具不运行。课里 TypeScript 版的 `checkSchema` 遍历的就是 schema，每个字段先看在不在，再看类型。修的时候容易错的几处：
   - 在原来的循环前面或者后面补一段缺字段检查，顺序就不是按 schema 一个字段一个字段来的。`{"limit": "ten"}` 应该报缺 query，补在后面会先报 limit 的类型；`{"query": 7}` 应该报 query 的类型，补在前面会先报缺 limit。用 `sorted(set(schema) - set(args))` 找缺字段，`{}` 会报成缺 limit。
   - 值是 None 不算缺字段，要报类型（got null）。用 `args.get(key) is None` 判断缺字段会把它当成缺；`not args.get(key)` 还会把 `limit: 0` 当成缺，工具就不运行了。
   - `True` 是 boolean，不是 number。把类型检查改写成 `isinstance(value, (int, float))` 会放过它。
   - 只给空参数特判一下“缺字段”，第一个 trace 断言能过，第二个过不了。
4. 每次创建 agent 都 `copy.deepcopy` 整个工具注册表。只有一个 agent 的时候这笔开销只付一次；第 1 处修好、每个请求都新建 agent 以后才显出来：1000 个工具、300 个请求本机约 0.83–1.57 秒，限值 0.05 秒；共享注册表以后约 0.2 毫秒。
5. 护栏：
   - 每个请求一个新 agent。继续复用同一个 agent、在 `run` 开头清空 memory，memory 那条断言能过，但测试会发现 3 个请求只用了 1 个 agent 对象；修计时的时候为了提速把 agent 缓存回去，也挂在这里。按会话缓存 agent 也不行，同一会话的第二个请求会把历史读进 memory 两遍。
   - 注册表共享，不拷贝。把深拷贝换成 `dict(tools)` 这样的浅拷贝，300 个请求约 1 毫秒，计时能过，但创建 agent 的开销仍然随注册表线性增长。测试最后检查所有 agent 拿到的是同一个注册表对象。
   - trace 的每一条要保存那一步返回时的输出。起始代码里 `Workflow.run` 已经对每一步的输出做了深拷贝，这组断言防的是改坏：修第 4 处时顺手把这里的 `copy.deepcopy` 也删掉，或者为了快改成浅拷贝（`tags` 列表和 `meta` 字典还是共享的），后面的步骤原地修改 payload，前面的记录就跟着变。课里的 `MastraWorkflow.run` 直接存引用，步骤返回新字符串时看不出问题，步骤改 dict 时就露出来了。

看什么：是不是先读断言的 diff，看出第二个请求的 memory 里混进了第一个请求的内容；修第 1 处时是每个请求新建 agent，还是去清空 memory；遇到工具里的 AttributeError 时，是不是顺着 traceback 回到 `run`，而不是去改测试的工具函数；遇到 TypeError 时，是不是去查 `check_input` 为什么放过了空参数，而不是在 `run` 里用 try/except 把它吞掉；修第 4 处时有没有分清两处 `copy.deepcopy`：注册表那份是多余的开销，trace 那份必须留着。

提示：
- H1："Three requests ran. How many Agent objects served them?"
- H2："The trace says the call was rejected. Why did the tool still run?" 第 3 处卡住时问："This call passes no arguments. Which fields does check_input look at?"
- H3：直接指出 `handle` 复用的 `self.agent`、缺失的 `continue`，以及 `check_input` 遍历的是 `args` 而不是 schema。

追问：
- "Why does Agno want a fresh agent per request at all?"（无状态：任何一个实例都能接任何会话的请求，可以水平扩容；状态在数据库里，agent 之间没有串扰）
- "Your fix shares the registry. What must stay true for that to be safe?"（注册表只读；请求级的工具要放在 agent 自己的一层，比如 ChainMap，不能写进共享的 dict）
- "When does a 2μs instantiation matter?"（课里说的：每秒成千上万个短命 agent，比如 chat fan-in、评测流水线；一个 agent 跑 10 分钟时不重要）
- "Exercise 2 asks what changes with Zod. What would a Zod schema give you that check_input doesn't?"（`execute` 的参数类型从 schema 推出来，写错字段名编译时就报；可选字段、默认值、嵌套对象；一次报出全部问题。错误原样回给模型，模型才能改参数重试）

### Part 2 组合存储（目标 12 分钟）

课里讲 Mastra 的 composite storage：memory、workflows、observability 分别写到不同的后端。这一关照这个思路，三类记录各进一个后端。

坑：
- 快照要原样读回：dict 的键顺序、`True` 和 `1`、`2.0` 和 `2`、`2**64 + 1`、`-0.0` 都要保持。`sort_keys=True` 会改掉键顺序，测试用带类型和顺序的比较抓它。快照文件必须是 JSON，测试会逐个解析；用 pickle 或 `repr` 存也能原样读回，但不符合 docstring 写的“一个 run 一个 JSON 文件”。
- run id 是任意字符串。直接当文件名，`nightly/2026-11-02` 会报 FileNotFoundError，`../escape` 会写到 `workflows/` 外面。把 `/` 换成 `_` 又会让 `nightly/2026-11-02` 和 `nightly_2026-11-02` 撞成一个文件。URL 编码或 base64 能躲开这两处，但测试里有一个 349 个字符的 backfill run id，编码以后有 411 或 468 个字符，超过文件名 255 字节的上限，报 `OSError: File name too long`。参考答案用 run id 的 sha256 作文件名，run id 存在文件里面。
- `runs()` 要按 run id 排序，不能按文件名排序。
- 日志要求是可读的 UTF-8（测试在原始字节里找 `Grüße`），所以要 `ensure_ascii=False`。这样一来，事件里的 U+2028（LINE SEPARATOR）会原样写进文件，读的时候用 `str.splitlines()` 会把这一行从中间切开，报 JSONDecodeError。要按 `"\n"` 切。
- 重开时日志不能被清空，追加要用 `"a"` 模式。
- 空的 run id 要报 ValueError，docstring 写了，测试也查。
- 消息内容里的 `\r\n` 要原样读回。SQLite 的 TEXT 本身没问题，问题出在自己写的文本格式上。sqlite3 默认开着隐式事务，插入以后不 commit，`close()` 时就丢了。

测试抓不到的：查消息时不写 `ORDER BY` 也能过，因为 SQLite 全表扫描恰好按 rowid 返回；SQL 不保证这个顺序。看到就问一句。

追问：
- "Mastra recommends ClickHouse for observability at scale. What changes in record() and events()?"（批量写入、按 trace_id 和时间列查询；不再整文件扫描）
- "Two processes append to the same log?"（需要单一写入者、文件锁，或者换成数据库；不要假设大块写入不会交错）
- "Your run ids are case-sensitive. What happens on a case-insensitive file system?"（`Nightly` 和 `nightly` 会撞成一个文件；用哈希作文件名就没有这个问题）

### Part 3 容量规划（目标 10 分钟）

本课的坑之一是 "Perf-for-perf's-sake"：一个请求只调一次慢模型时，实例化开销不是瓶颈。Exercise 3 让你自己量一量。这一关用 Little 定律把这件事算清楚。

坑：
- 瓶颈是利用率最高的那一段，不是服务时间最长的那一段，也不是 in_flight 最多的那一段。测试里有一个每秒 2000 个请求的 fan-in：实例化 1 毫秒、只有 1 个 worker，利用率是 2；模型 50 毫秒、200 个 worker，利用率是 1/2。瓶颈是实例化，这正是课里说的“每秒成千上万个短命 agent”时 2μs 才重要的情形。只看服务时间或 in_flight，前面几组数据都能蒙对，到这一组才挂。
- 单位：`μs`（希腊字母 U+03BC）和 `µs`（微符号 U+00B5）长得一样，是两个不同的字符，都要认。测试里用转义写成 `μ` 和 `µ`。
- `float("2.05") * 10**9` 是 2049999999.9999998，`int()` 截断成 2049999999。用 Decimal 或者整数运算才精确。用 `round()` 能过 2.05 秒，但会把 `1.5ns` 舍入成 2，而 docstring 要求报错；用 Decimal 但不检查是不是整数纳秒，`int()` 会把 `1.5ns` 截成 1，也不报错。
- 利用率正好等于 1 时撑不住，判断要用 `< 1`。所以 `workers_needed` 是 `floor(in_flight) + 1`，in_flight 是整数时 `ceil` 会少算一个。
- 平局规则写在 docstring 里：先比服务时间，再比顺序。直接 `max()` 会拿到第一个。
- `max_rate` 只取决于各段的 worker 数和服务时间。用 `rate / 最高利用率` 算，rate 为 0 时除以零，测试里有 rate 0 的情形。
- docstring 列的非法输入都要报 ValueError：负的 rate、0 服务时间（否则 `max_rate` 除以零）、带正号的 `+2ms`。
- 结果是 Fraction。`9/80` 写成 float 是 0.1125，与 `Fraction(9, 80)` 不相等。

追问：
- "The model stage sits at 27/32 utilization. Comfortable?"（越接近 1 排队越长；通常要留余量，或者按尾延迟目标来定并发）
- "Switching the 40 ms instantiation to 2μs saves about 2%. When would it be worth it?"（实例化占比大的负载：大量短请求、评测扇出，比如测试里那组 fan-in）
- "Little's law says nothing about the distribution. What would you measure in production?"（每段的 p50/p99、队列长度、拒绝数）

### Part 4 流式后端（目标 14 分钟）

本课推荐的 Agno 生产形态是无状态的 FastAPI 后端，Mastra 也有 Express、Hono 这些 server adapter。在 HTTP/1.1 上，事先不知道总长度的流式回复用 chunked 编码发送，这一关就输出这种原始字节。

坑：
- 输出格式由测试里的解析代码决定：每块是十六进制长度、CRLF、数据、CRLF，最后是 `0\r\n\r\n`。长度只能是十六进制数字：`hex(n)` 写出来是 `0x11`，Python 的 `int(s, 16)` 认，真正的 HTTP 客户端不认，测试的解析代码也不认。
- 长度按 UTF-8 字节数算，不是字符数（`Grüße ` 是 6 个字符、8 个字节，emoji 是 4 个字节）。用十进制写长度，17 字节的 token 会被读成 0x17。
- 空 token 要跳过。发出去就是 `0\r\n\r\n`，回复提前结束。只有一个空格的 token 不是空的，要照发（测试里有一个 `" "`）；用 `strip()` 判断会把回复里的空格吞掉。
- 同一个会话的请求一个接一个跑，不同会话并行。用一把全局锁，s2 会被 s1 卡住；不加锁，或者每个请求新建一把锁，同一会话的第二个请求会并发开始。
- 历史要在拿到锁以后再读，否则排在后面的请求看不到前一轮。
- token 一到就发。先攒完整个回复再发，测试里的模型会一直等着，第一块永远出不去。
- 客户端 `aclose()` 以后锁必须释放。用 `async with` 就没问题；手动 `acquire()`、最后才 `release()`，锁会一直被占着，同一会话的下一个请求超时。
- 中途断开的请求什么都不存。在开始流式输出之前就写入 user 那一轮，会留下半截对话。
- 两轮对话要在发出最后一块之前写进会话。先发 `0\r\n\r\n` 再写，客户端读完最后一块就断开时这一轮就丢了；多进程部署时，客户端的下一个请求还可能落到另一个进程，读到旧的历史。测试读到最后一块就 `aclose()`。
- 函数体还没有 `yield` 时，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`，要看出这里需要 async generator。

测试抓不到的：
- 先发 HEADERS 再排队拿锁也能过。这样排队的请求会先收到 200 的头，严格说排的是第二次迭代的顺序；参考答案进了锁才发 HEADERS，同一会话严格按第一次迭代的顺序执行。可以追问两种做法的差别。
- 不用 `aclosing` 包住模型的流也能过：客户端断开时，模型的生成器要等垃圾回收才被关掉。可以问一句模型那边的连接什么时候释放。

追问：
- "Why chunked instead of Content-Length?"（开始发送时还不知道总长度）
- "The lock dict grows with every session. Fix it?"（没有等待者时删掉；或者用弱引用字典）
- "You run four server processes behind a load balancer. Does the per-session lock still work?"（不行，锁只在一个进程里有效；要按会话做粘性路由，或者用数据库行锁、每个会话一个队列）

### Part 5 工作流 schema 检查（目标 14 分钟）

Mastra 的工具用 Zod 声明类型，工作流的每一步都有输入和输出。这一关判断“上一步的输出能不能交给下一步的输入”，是结构子类型判断，和第 13 章的 strict 编译器、判别式 oneOf 不是一回事。

坑：
- 方向：`integer` 可以给 `number`，反过来不行。
- optional 的输出不能交给必填的输入；必填的输出可以交给 optional 的输入。目标里是 optional 的字段，源里可以没有。
- 源是 union 时，每个成员都要兼容，而且要先拆源的 union。先拆目标的 union，`string | integer` 交给 `integer | string` 会被判成不兼容。
- 数组要递归比较元素类型，路径加 `[]`。
- 非 strict 的对象允许多余字段，strict 的对象不允许，报的是源对象里第一个多余字段。
- 嵌套工作流的边界：它的输入是第一个叶子步骤的输入，输出是最后一个叶子步骤的输出，要一直往里找，不能只拆一层。测试里有一个两步的嵌套工作流，拿第一步的输出当整个工作流的输出会报错位置。
- 链接按数据经过的顺序检查：先查进入某一步的链接，再查这一步里面的链接。先查完外层再查内层，或者先查里面再查进入它的那一条，报出来的都会是错的那一处。
- 名字要带上所有外层工作流的名字。
- 结构问题（空工作流、自己包含自己）要在检查链接之前发现。空工作流可能在任何一层，只查顶层的话，嵌套的空工作流会在取第一个步骤时报 IndexError。
- “自己包含自己”指当前这条嵌套路径上又出现了自己。用一个全局的 visited 集合，会把同一个子工作流用两次误判成环。

测试抓不到的：strict 对象先查多余字段、再查目标的字段，也能过；按 docstring 的顺序是先查目标的字段。

追问：
- "Why must the union on the source side be split first?"（源是 union 时要求“每个成员都行”，目标是 union 时只要求“有一个成员行”；顺序反了，两个都要拆的时候就会判错）
- "A step takes a callback as input. Which way does assignability go for its parameters?"（参数是逆变的，方向反过来）
- "Where would you run this check: at build time or at run time?"（定义工作流时就检查，同时在运行时校验真实数据，因为 schema 和实际数据可能不一致）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出无状态扩容、并发写、精确计算、多进程锁 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
