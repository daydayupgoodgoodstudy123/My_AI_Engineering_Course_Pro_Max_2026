# 面试官手册：reliablerpc（13/29）

候选人计时期间不要看。候选人手里只有 README、`reliablerpc/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 已经完成的请求又收到取消，要报错吗？ | "No. Ignore it. Turning that race into an error only makes another race." |
| 1 | 取消之后 worker 还在报进度，要报错吗？ | "No. It hasn't noticed yet. Send nothing and return None." |
| 1 | 同一个请求 complete 两次呢？ | "Return the response you already sent. Send nothing new." |
| 1 | 合并掉的进度算丢失吗？ | "Yes. It counts in dropped_progress and sets needs_refetch, as the docstring says." |
| 1 | 为了快，buffer 能调整消息顺序吗？ | "No. drain returns messages in the order they were pushed." |
| 2 | 结果能缓存在内存里吗？ | "Not as the source of truth. Another replica, or the same one after a restart, never sees your memory." |
| 2 | 同一个键、同样的参数、新的 JSON-RPC id，重放结果里的 rpcId 是哪个？ | "The first call's. A replay returns the stored result unchanged." |
| 2 | 同一个键用在另一个工具上？ | "That's a conflict. A key names one business intent: one tool, one set of arguments." |
| 2 | 参数里 dict 的键顺序不同算不同参数吗？ | "No. Same JSON, any key order, at any depth." |
| 2 | 工具执行时抛异常怎么办？ | "Keep nothing it wrote, store nothing, and let the exception through." |
| 2 | 空字符串或者数字当键呢？ | "The tests don't cover it. Tell me what you'd do." |
| 2 | 要开 WAL 吗？ | "Your call. BEGIN IMMEDIATE is what serializes the key either way." |
| 3 | 服务器说 readOnlyHint 是 true，能重试吗？ | "Annotations are hints from the server. Only the application's contract decides." |
| 3 | 工具没有 contract 呢？ | "Unsafe. Its side effects are unknown." |
| 3 | 参数里有 idempotencyKey，但 contract 没写去重？ | "Then the server deduplicates nothing for that tool. Unsafe." |
| 3 | safe 的重试要不要改 params？ | "No. Send the same params. The transport gives the request a new id." |
| 3 | HTTP 上关流之后，再 POST 一条 notifications/cancelled 保险一点？ | "No. Closing the response stream is the signal. Post nothing." |
| 3 | 已经变成任务的调用，要不要顺便关流？ | "Its tools/call finished when it returned the task. Send tasks/cancel, nothing else." |
| 3 | reason 必须有吗？ | "No. Leave the field out when there is no reason." |
| 3 | 键是数字可以吗？ | "No. The key is a non-empty string, as the docstring says. Anything else is unsafe." |
| 4 | 保活写 `:` 还是 `: keepalive`？ | "Any SSE comment line. A bare ':' is enough." |
| 4 | 重复的进度值要报错吗？ | "No. It isn't progress: don't send it, and it doesn't count as activity." |
| 4 | 截止和保活落在同一毫秒？ | "Cancellation wins. The tests avoid exact ties." |
| 4 | 事件正好在截止那一毫秒到？ | "The deadline wins: nothing due at that moment is written. The tests avoid exact ties." |
| 4 | 超时的时候要发一个错误响应吗？ | "No. The request is cancelled. Nothing more goes on the stream." |
| 4 | 要给事件加 id，方便断线续传吗？ | "No. This transport version doesn't resume streams. A client that lost one refetches." |
| 4 | 没有 progress token，最终响应还发吗？ | "Yes. Only progress needs a token." |
| 5 | 搜多深？ | "Up to max_depth events. A sequence of exactly max_depth events counts." |
| 5 | 两个 World 字段相同，但里面的 coordinator 对象不同？ | "Same state. World compares only its fields." |
| 5 | 有好几个一样短的反例，返回哪个？ | "The first in the order of the events you were given." |
| 5 | explore 要自己检查不变量吗？ | "No. RaceModel.step sets problem on the world it returns." |

## 每关：要看什么、提示、追问

### Part 1 修取消竞态和缓冲（目标 12 分钟）

一个测试里叠了 4 个缺陷和一组护栏：

1. `complete()` 不看请求是否已经取消。错误不在 coordinator 里报出来，而是在 `buffer.py` 的 `_check_open` 里报 `StreamClosed: write to a closed response stream`：HTTP 请求被取消时，它的响应流已经关了，`complete()` 还往里写最终响应。候选人要从 traceback 读出调用链 `complete → _outbox(...).push_final → _check_open`。在 `complete()` 里吞掉 StreamClosed，或者去掉 buffer 的 closed 检查，都会挂在 "a cancelled request gets no response"。
2. `_cancel()` 不看状态：完成之后迟到的取消把 completed 改成 cancelled。stdio 那一段挂在 "a late cancellation changes nothing"。只在 `receive_stdio_cancellation` 里修，HTTP 上完成之后再关流照样会改状态，挂在 "..., on Streamable HTTP too"。
3. `progress()` 不看状态：请求完成以后，进度还会写进通道。挂在 "notifications stop once a request completes or is cancelled"。只查 cancelled、或者只查 completed，都会在另一种情况下漏掉。
4. `BoundedSseBuffer._drop_oldest_progress` 每次都从头扫描。5000 条响应排在前面、两个 token 交替推进度时，每推一次都要跨过这 5000 条：5000 次推送要 0.8 到 1.4 秒，限值 0.05 秒。按序号存消息、另用一个 deque 记下进度的序号，一次推送 O(1)，同样的工作 1.3 到 1.6 毫秒。

护栏（提速或修缺陷时最常见的改坏方式）：
- `deque(maxlen=capacity)`，或者满了就丢最旧的任意消息：响应被丢，挂在 "every response stays queued, in order"。
- 满了就丢新来的进度、丢最新的那条进度、丢同一个 token 的最旧进度：分别挂在 "the oldest progress makes room for the newest" 和 "the oldest progress makes room, whatever its token"。
- 不再合并、按 token 只留最新一条、越过响应去合并：挂在 "progress replaces the newest message only when that is progress for the same token"。
- 先看满不满、再合并：队列满时，同一个 token 的新进度应该替换队尾那条；先挤掉最旧的进度就丢错了一条，挂在 "progress for the newest message's token replaces it, even in a full queue"。
- 为提速另建的索引（序号 deque、下标列表、指针）在 drain 时没有一起清空：下一轮按旧序号删消息，报 KeyError 或者删错一条，挂在 "a drained buffer starts over empty" 这一段。
- 丢了进度不置 `needs_refetch`、合并不计数、容量用 `>` 判断、drain 先吐响应再吐进度，都各有断言。
- 满了全是响应时再来一条响应，要报 ReliabilityError 并且什么都不改；挤掉最旧的响应会挂在 `DID NOT RAISE`。
- 修第 1 处时让 `complete()` 对一切已结束的请求都返回 None：重复完成要返回已发出的响应，挂在 "completing again returns the response already sent"。修第 2 处时让迟到的取消抛异常、或者干脆不处理 stdio 取消，也都会挂。

看什么：是不是先读 traceback、看出报错的 buffer 本身没有错；是不是先打印请求的 state 再动手；三处状态检查是不是想清楚了“取消先到”和“完成先到”两种顺序；改 buffer 时是不是先说出为什么慢，再选数据结构。

提示：
- H1："Who wrote to the closed stream? Read the traceback from the bottom up."
- H2："What state is request 7 in when complete() runs? What should complete() do in that state?"
- H3：直接指出 `complete()` 开头少了 cancelled 分支，`_cancel()` 和 `progress()` 也都没看状态。

追问：
- "Why ignore a late cancellation instead of answering it with an error?"（它是通知，没有响应；讲义说把竞态变成错误只会制造新的竞态。网络延迟意味着两边都证明不了对方先看到哪个事件，所以目标是任何顺序都有确定的结果）
- "The client receives a response after it gave up. What does it do?"（忽略。Part 5 把这一条当作不变量检查）
- "Coalescing sets needs_refetch here. Is that necessary?"（本课代码的保守选择。被合并掉的值已经被同一个 token 的新值取代，严格说没丢信息；丢最旧进度时客户端才可能错过某个 token 的全部更新。两种都说得通，要说出理由）
- "The buffer is full of responses. What would you do instead of raising?"（给响应预留容量、对生产者施加背压、断开太慢的消费者。不能静默丢）
- "Your fix uses a dict and a deque. What happens to the dict after millions of deletes?"（删除留下空位，插入时 dict 会定期重建，摊还仍是 O(1)；drain 时整体清空）

### Part 2 幂等账本（目标 12 分钟）

坑：
- 不开事务：`isolation_level=None` 下每条语句都自动提交。工具写了扣款之后崩溃，扣款留下了，记录没有，重试又扣一次。挂在 "a call that crashed after charging keeps neither the charge nor a record"。在两个事务之间运行工具（查完键先提交，再执行工具）也挂在这里。
- 普通的 `BEGIN`（deferred）：第二个副本先读后写，写的时候拿不到锁，SQLite 直接报 `database is locked`，不等 busy timeout。挂在 "a replica retrying the key while the first call runs waits for it, then replays its result"。
- 先查后写：在事务外查键，或者用 Python 默认的隐式事务（`with conn:`，SELECT 时还没有 BEGIN），第二个副本看到“没有这个键”，等到锁以后再执行一次工具，插记录时撞主键。同一条断言。
- 进程内的锁：`threading.Lock` 只挡得住同一个进程，测试里的第二个副本是另一个进程。讲义原话："A process lock alone does not protect multiple replicas or survive a restart."
- 失败时不 ROLLBACK：冲突或者工具异常之后，连接还停在事务里，下一次 `BEGIN IMMEDIATE` 报 `cannot start a transaction within a transaction`。重放分支忘了 COMMIT 也一样。
- 指纹：不 `sort_keys`、只排第一层的键、不带工具名、把 JSON-RPC id 也算进去，都会挂。
- 重放要原样返回第一次存下的结果，包括第一次的 rpcId 41。用这次的 42 覆盖掉是错的。
- 内存缓存或浅拷贝：调用方改了返回的 dict（测试改的是嵌套的 `charged.cents`），之后的重放就跟着变。挂在 "changing a returned result changes nothing that later replays return"。
- 按工具分开存键：`refund_account` 就能拿同一个键再跑一次，挂在 `DID NOT RAISE IdempotencyConflict`。
- 漏 commit 在本章 02、09 已经出现过两次，这里没有单独设计；如果漏了，重开之后的断言照样会挂。

测试抓不稳、但看到要指出的写法：
- 先 COMMIT 工具的效果，再用一条单独的语句写幂等记录。效果已提交、记录还没写的那一瞬间，另一个副本查不到这个键，会再执行一次；进程在这一瞬间崩溃也一样。测试里的第二个副本正在 busy handler 里睡眠，几乎总是赶不上这个窗口，所以测试抓不稳。这正是讲义说的 "check key, run mutation, store result"。
- 第一次调用直接返回工具给的 dict，不从存储的 JSON 重建。这里的工具只返回 JSON 原生类型，测试分不出来。追问：工具返回元组或整数键时，第一次的结果和重放的结果就不一样了。

看什么：是不是先说出“查键、执行、存结果”三步为什么不安全；会不会主动问工具抛异常时怎么办；看到第二个副本的那段测试时，能不能说清楚它在测什么。

追问：
- "The charge goes to a real payment API, not this table. Is it still exactly once?"（不是。本地事务管不到外部副作用。要么上游接受同一个幂等键，要么用 transactional outbox 把本地提交可靠地传出去，崩溃后按键对账）
- "The replicas run on different machines. Does this still work?"（网络文件系统上的 SQLite 锁不可靠。要换成共享数据库的事务，或者依赖上游的幂等）
- "When can you delete idempotency records?"（保留期至少要覆盖客户端可能重试的时间窗；删掉以后同一个键会再执行一次，这一点要写进和客户端的约定）
- "Why store the result instead of recomputing it on a replay?"（重放必须和第一次完全一致；重新计算会得到新的收据号和新的 rpcId）
- "An empty key, or a number?"（建议当成格式错误拒绝：空键会让所有调用方共用一条记录）

### Part 3 重试分类和取消信号（目标 10 分钟）

坑：
- annotations 只是服务器给的提示。`send_email` 和 `rotate_keys` 都声称 `readOnlyHint` 和 `idempotentHint`，一个有副作用、不去重，一个根本没有 contract，两个都是 unsafe。拿 annotations 补 contract 也不行。
- conditional 要三个条件同时满足：有副作用；contract 写明服务器按哪个参数去重；调用里这个参数是非空字符串。键放错参数（`deploy_service` 用的是 `releaseId`）、空键、数字键、contract 不去重的工具带着 `idempotencyKey`，都是 unsafe。只写 `if key:` 会放过数字键。
- conditional 的重试要原样发：同一个键、同样的参数。换一个新键，等于发起了另一个业务意图。
- stdio 的取消是通知：没有 `id`；`requestId` 就是原请求的 id，41 不能变成 `"41"`；没有 reason 就不写这个字段，不能写成 null。
- Streamable HTTP 上关闭这个调用的响应流就是取消，什么都不 POST。
- 已经返回任务句柄的调用用 `tasks/cancel`，参数是 `taskId`，它是一个普通请求。关流和发 `notifications/cancelled` 都碰不到任务。两种传输上都一样。
- 服务器只能在 stdio 上用 `notifications/cancelled` 结束 `subscriptions/listen`。stdio 上的 `tools/call`、HTTP 上的 `subscriptions/listen` 都要抛 ReliabilityError。

看什么：是不是先把讲义的三行重试矩阵和三行取消表说出来再写；能不能讲清楚为什么 annotations 不可信。

追问：
- "tasks/cancel came back. Is the task cancelled?"（不一定。它只确认了取消意图，任务可能还是 working，也可能先完成了；要一直轮询到终态）
- "A safe call timed out. Why cancel it before sending it again?"（讲义说先弄清楚失败的边界再重试。不取消的话，两个请求同时在跑：读操作无害但浪费，一旦分类错了就是两次副作用）
- "The HTTP connection dropped. Should the server delete the durable task?"（不能。建任务就是因为它的生命周期比一次请求、一条连接长）
- "Where does the contract come from in practice?"（应用和工具提供方之间的约定、代码审查、集成测试，不是 tools/list）

### Part 4 双时钟的 SSE 流（目标 14 分钟）

坑：
- 最大时钟从请求开始算，进度只重置空闲时钟。1999 ms 的进度挡不住 2000 ms 的最大截止，2100 ms 才到的结果不能写。
- 截止要在处理下一个事件之前判断。先把事件写出去再看截止，2100 ms 的结果就漏出去了。
- 保活不是进度：一直没动静的 worker 到 500 ms 照样空闲超时，不能拖到最大截止。worker 的事件用完了也一样，它卡住了，流不能就此结束。
- 保活按“上一次写出任何东西”计时，安静期每隔 keepalive_ms 写一次。按上次进度计时，会在同一个时刻反复写保活，测试的 `timeline` 最多读 40 块，不会卡死。
- 进度值必须递增。重复或者更小的值既不发，也不算活动；卡在 1 的 worker 到 600 ms 空闲超时。
- 没有 progress token：进度一条都不发，也不重置空闲时钟，空闲时钟从请求开始算；但最终响应照发。
- 结果写出后流就结束：不再向 worker 要下一个事件，并关闭 worker。被取消时、客户端提前关流时，也都要关闭 worker。测试一直持有 CallStream 对象，垃圾回收不会替你关；只在完成和超时两处调用 `close()`、客户端关流时不管，会挂在 "closing the response stream stops the worker"。用 try/finally 在一处收尾。
- 事件正好落在截止那一毫秒：docstring 说截止那一刻到的也不写。测试避开了精确平局（本章其他课已经考过瞬间边界），`<` 和 `<=` 在这里分不出来，可以口头确认。
- 要一边读 worker 一边写，不能先把 worker 读完。
- 响应头要有 `Content-Type: text/event-stream`、`Cache-Control: no-cache`、`X-Accel-Buffering: no`。
- 输出格式由测试的 `SseReader` 决定：注释行算保活，data 行在空行处解码，只允许 data 字段。

看什么：动手前能不能把讲义里 0、400、800、1200 ms 那个例子在纸上推一遍；循环里能不能分清三样东西：下一个事件、下一次保活、最近的截止。

追问：
- "Why not count a keepalive as activity?"（保活只说明连接还活着，不说明工作有进展；把它当进度，卡住的工作就永远不会超时）
- "Which clock would you use in production?"（单调时钟，`time.monotonic()`；墙上时钟会跳）
- "The lesson says to rate-limit progress. Where would that go?"（按 token 合并，每隔 N ms 最多发一次，和 Part 1 的合并配合）
- "Progress still arrives in bursts behind nginx. What else do you check?"（代理自己的读超时和缓冲设置、压缩；保活间隔要小于中间设备的空闲超时）
- "The client reconnects. Can it resume with Last-Event-ID?"（不能。这个版本不支持续传，要新开请求，再从权威方法重新拉取状态）

### Part 5 穷举取消竞态（目标 12 分钟）

坑：
- 不去重：每条交错都重新走一遍。测试里的计步模型在第 2001 步报 "explore keeps expanding worlds it has already explored"；去重后整个搜索只要 840 步，不去重要 3.6 万步左右。
- 深度优先：先找到的不一定是最短的序列。
- 事件顺序：只用传入的 events，并按传入的顺序尝试。用 `EVENTS` 常量或者排序后的顺序，会得到另一个反例。
- `max_depth` 的边界：恰好 max_depth 个事件的序列要检查，更长的不行。
- 返回的 trace 是元组，要包含最后那个事件。
- 按 (world, 深度) 去重：仍是多项式，计步模型放得过（980 步），但同一个 world 在不同深度会被重复展开，不符合 docstring 的 "Each distinct world is explored once"。可以接受，追问它为什么多余：广度优先第一次到达某个 world 时就已经是最浅的一层。

看什么：能不能说清楚为什么广度优先找到的就是最短反例；读 RaceModel 时能不能从测试里那几个故意改坏的协调器，推出预期的反例。

追问：
- "Why does breadth-first search give the shortest counterexample, and the first one in event order?"（BFS 按层展开，第一个违规一定在最浅的一层；同一层里父节点按顺序出队，子节点按事件顺序生成，所以也是这一层里按事件顺序最靠前的）
- "Can deduplication hide a counterexample?"（World 的相等包含了不变量要用的全部字段，包括 first_terminal 和 problem；相等的两个 world 之后的行为完全一样）
- "max_progress is 3. What happens at 10?"（去重后状态数大致线性增加，交错数是指数增加；不去重就爆了）
- "How would you add Streamable HTTP to the model?"（cancel 改成关流，服务器那边调 `close_http_stream`；关流以后在途的消息直接丢弃）
- "What does a clean run prove about the real system?"（只证明模型里的协调器在这些事件下守住了不变量。进程崩溃、多个请求交错、真实的网络都不在模型里）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出外部副作用、跨机器、时钟、代理、续传和背压 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
