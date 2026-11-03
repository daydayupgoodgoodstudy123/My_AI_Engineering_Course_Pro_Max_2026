# 面试官手册：DurableTask（13/13）

候选人计时期间不要看。候选人手里只有 README、`durabletask/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 正在运行的任务收到 cancel，要马上停吗？ | "No. Record the request; the worker stops at its next step. Only a task waiting for input is cancelled on the spot." |
| 1 | 已经结束的任务收到 cancel 呢？ | "Acknowledge it and change nothing, not even lastUpdatedAt." |
| 1 | 刚好满 ttlMs 的任务算过期吗？ | "Yes. At createdAt plus ttlMs it's overdue." |
| 1 | ttlMs 是 null 呢？ | "No limit. It never expires." |
| 1 | 过期的任务用什么错误？ | "EXPIRED_ERROR in task.py." |
| 2 | 能在内存里缓存任务吗？ | "Only if another instance's write shows up on your very next get. In practice, read the file." |
| 2 | 要 fsync 吗？ | "The tests don't cover power loss. Tell me where it would go." |
| 2 | get 一个不存在的 id 返回什么？ | "None. A malformed id is a ValueError." |
| 2 | 文件里的时间戳用什么格式？ | "Wire timestamps, as format_time writes them. Every instance reads the same files." |
| 2 | 文件里能多加一个字段吗，比如版本号？ | "No. The other instances read these files with Task(**record)." |
| 2 | 临时文件叫什么、放哪里？ | "Any name that isn't <taskId>.json, in the same directory." |
| 3 | decline 算回答吗？ | "Yes, it answers the key. What a decline means is up to the tool." |
| 3 | 同一个 key 回答了两次？ | "The first answer stands. Later ones are ignored." |
| 3 | 工具又要一个已经问过的 key？ | "That's a bug in the tool. Fail the task with -32603." |
| 3 | 对没在等输入的任务发 tasks/update？ | "Acknowledge it and ignore it. Nothing is outstanding." |
| 3 | 回答的格式不对，比如没有 action？ | "Then it's not an answer. The key stays outstanding." |
| 3 | 工具抛的不是 McpError，比如 KeyError？ | "The tests don't cover it. Your call. Say what you chose." |
| 4 | 确认之后要先把每个任务的当前快照推一遍吗？ | "No. Only changes. A client that needs a baseline polls once after it subscribes." |
| 4 | 请求里同一个 id 出现两次？ | "List it once, where it first appears." |
| 4 | 流什么时候结束？ | "When every watched task has finished. Send the listen result and stop." |
| 4 | 要发 keepalive 吗？ | "You may, as SSE comments. The tests skip them." |
| 4 | 要加 event: 字段吗？ | "Not needed. One data line per message is enough." |
| 5 | 租约多长？ | "lease_ms. Thirty seconds here, on the injected clock." |
| 5 | 同一个 worker 再 acquire 一次？ | "It renews its own lease." |
| 5 | 过期的租约谁都能接管吗？ | "Yes. Its holder is presumed dead." |
| 5 | sweep 要不要顺便删租约文件？ | "Nice to have. The tests don't check it." |
| 5 | 删掉的任务应该回 task expired 吗？ | "No. Deleted means gone: task not found, like an id that never existed." |
| 5 | 等输入的过期任务，sweep 也要处理吗？ | "Yes. It hasn't finished, so it fails first, like a working one." |

## 每关：要看什么、提示、追问

### Part 1 修轮询和取消（目标 10 分钟）

一个测试里叠了 5 个缺陷和几个护栏：

1. `_fail_if_overdue` 直接拿 `self._now() < task.expires_at()` 比较，没管 `expires_at()` 对 ttlMs 为 null 的任务返回 None。错误不在被轮询的任务上报出来：测试轮询 report，`tasks_get` 先调 `_fail_overdue()` 扫一遍所有任务，扫到 ttlMs 为 null 的 archive，才在 `_fail_if_overdue` 里报 `TypeError: '<' not supported between instances of 'datetime.datetime' and 'NoneType'`。候选人要先弄明白：为什么轮询 report 会去碰 archive。
2. `tasks_get` 用 `"complete" if task.status in TERMINAL_STATUSES else "task"` 当外层 resultType。这正是课里说的 parser bug 的服务器版本：外层 resultType 说的是 tasks/get 这次调用完成了，任务自己的状态在 status。
3. `tasks_cancel` 的 else 分支把所有不是 working 的任务都改成 cancelled，包括已经 completed 的。错误在下一次 tasks/get 才看得出来：status 变成 cancelled，result 不见了。
4. `Task.expires_at` 用 `last_updated_at` 加 ttl，docstring 和课里都说从 createdAt 算。测试里的 slow 在第 10 分钟进入 input_required，应该在第 15 分钟过期，按 lastUpdatedAt 算要到第 25 分钟。
5. `tasks_get` 每次都先 `_fail_overdue()` 把整个 store 扫一遍：3000 个任务时 20 次轮询要 0.6 到 0.9 秒，限值 0.04 秒。

护栏：
- 修第 5 处时把过期检查整个删掉，第 4 处的断言会挂："a task expires ttlMs after it was created"。要只检查被轮询的那个任务。
- `tasks_cancel` 开头也有一个 `_fail_overdue()`。计时只测 tasks/get，所以留着它不会挂；但把它删掉、又不换成对这个任务的检查，等输入的过期任务就会被取消而不是失败，挂在 "tasks/cancel fails an overdue task first, as tasks/get does"。
- 按时钟节流的扫描（同一秒只扫一次）也不行：计时循环里每次轮询时钟前进 1 秒，模拟客户端按 pollIntervalMs 轮询，节流的扫描照样每次都跑。
- 修第 3 处时照课里的代码写成“不是终态就直接 cancelled”，会挂在 "cancellation is cooperative"：working 的任务只记下请求，worker 在下一步才停。改成什么都不做也不行，等输入的任务没有 worker 在跑，要马上 cancelled。
- 已结束的任务收到 cancel 时不改状态、却还是调了 `_save`，lastUpdatedAt 会变，挂在 "a finished task never changes, not even its lastUpdatedAt"。重复 cancel 一个已经记下请求的任务也不能再保存。
- 刚好满 ttlMs（第 15 分钟整）就算过期。把比较写成 `<=`，边界上那次断言会挂；ttlMs 当成秒（`timedelta(seconds=...)`）也会挂。修第 1 处时把 null 当成已经过期，archive 会被判成 failed。
- 过期是一次修改，要保存：只在返回的快照里改成 failed 而不保存，lastUpdatedAt 还是第 10 分钟的。

看什么：第一处报错时，是先读 traceback，看出调用链是 tasks_get → _fail_overdue → _fail_if_overdue，还是直接在比较那一行打补丁；能不能说清楚出错的任务不是被轮询的任务；每改一处就重跑。

提示：
- H1："Which task is that comparison looking at? Print task.task_id and task.ttl_ms right there."
- H2："Why does polling one task touch every task in the store?"
- H3：直接指出 `_fail_if_overdue` 里的比较，和 `tasks_get` 开头的 `_fail_overdue()`。

追问：
- "Why is the outer resultType complete while the task is still working?"（外层说的是 tasks/get 这次 RPC 完成了，任务状态在 status；完成后 result 里还有原 tools/call 自己的 resultType。两层分开，客户端才不会把还在跑的任务当成新句柄，或者当成已经完成的结果）
- "tasks/cancel came back empty. What should the client do next?"（继续 tasks/get 或订阅；任务可能先完成、不理会取消、或者稍后才变 cancelled，不能从确认推断终态）
- "Who fails an expired task that nobody polls?"（后台清理，也就是 Part 5 的 sweep；tasks/get 上的检查只保证轮询的人看不到过期了还在跑的任务）
- "ttlMs is 15 minutes. May the server delete the result one minute after the task completes?"（可以，只要已经过了 createdAt 加 ttlMs；ttlMs 从创建时刻算，不是“完成后保留多久”的承诺）

### Part 2 共享目录的任务库（目标 12 分钟）

坑：
- 照课里的 `TaskStore` 在构造时把目录读进字典、之后只读内存：测试先开 replica，再由另一个实例 tools/call，replica 就看不到这个任务（"a handle resolves on every instance as soon as tools/call returns it"）。只在 miss 时读文件再缓存也不行：一个实例读过的任务，被另一个实例改了以后，它读到的还是旧的。
- 为了“总能看到别人的写”在每次 get 里重读整个目录：2000 个文件读 20 次要 1.6 到 2.5 秒，限值 0.04 秒。get 只读 `<taskId>.json` 这一个文件。
- 时间戳：`isoformat()` 写出来是 `+00:00`，`json.dumps(default=str)` 写出来是 `2026-08-21 10:30:00+00:00`，都和别的实例写的 Z 格式对不上，挂在 golden 记录写回的那一步。读回时用不带时区的 `strptime`，得到的 naive datetime 和 aware 的 T0 比较不相等。`wire.format_time` 和 `wire.parse_time` 已经给了。
- 用 `default=format_time` 把所有 datetime 都转成文本，看起来省事，但混进 structuredContent 的 datetime 会被悄悄改成字符串，读回来已经不是原来的值。docstring 要求这样的任务 save 时报 TypeError。
- 原子写：直接 `open(path, "w")` 或 `path.write_text(...)` 写 `<taskId>.json`，是在原文件上截断重写。测试让另一个实例先打开旧文件，再保存新版本：rename 换的是目录项，已经打开的读者读到的还是完整的旧记录；原地重写时它读到的是新内容，写到一半崩溃时就是半个文件。这个断言只在 POSIX 上运行，Windows 不允许 rename 覆盖一个打开着的文件。
- 写失败要留下旧记录：json.dump 直接写目标文件时，序列化到一半报错，目标文件已经被截断；清理时删错了文件（删了 `<taskId>.json` 而不是临时文件）也一样。
- 目录里不是 `<taskId>.json` 的都不是任务：崩溃留下的 `.tmp`、编辑器的 `.swp`，还有 Part 5 的 `.lease`。用 `iterdir()` 全读，或者 `glob("tsk_*")`，都会把它们当成任务。保存成功后也不能留下临时文件或 `.bak`。
- 任务 id 来自客户端，会变成文件名。`"../elsewhere/tsk_aaaaaaaaaaaa"` 会读到目录外面另一个租户的文件。每个方法都先 `check_task_id`。
- `create` 不能覆盖已有的任务；`issued_keys` 的顺序原样保留；`ttl_ms` 为 null 要写成 null。写的时候省掉 null、读的时候补默认值，就把“没有期限”变成了 15 分钟。
- 可以接受的写法：照课里用固定的 `<taskId>.tmp` 当临时文件名（两个实例同时写同一个任务时会互相踩，可以追问）；在 Python 3.11 以上用 `datetime.fromisoformat` 读回 Z 时间戳。把临时文件建在系统临时目录再 rename 过来，测试抓不到，但违背了 docstring 的“same directory”，用下面第三个追问问清楚。

追问：
- "Is rename enough to survive a power cut?"（不够：临时文件 fsync 之后再 rename，rename 之后还要 fsync 目录。课里也说，多副本要用共享的持久存储）
- "Two instances save the same task at the same moment. What happens?"（后写的覆盖先写的，前一个更新丢了。要版本号加比较后交换，或者用 Part 5 的租约保证同一时间只有一个写者）
- "Why must the temporary file sit in the same directory?"（rename 只在同一个文件系统里是原子的，跨设备的 os.replace 会直接失败）
- "A replica on the next release adds a field. Then what?"（读的时候容忍未知字段、写回时原样保留，或者给记录加格式版本；现在的 `Task(**record)` 遇到未知字段会直接报错）

### Part 3 worker 和按 key 的输入（目标 14 分钟）

坑：
- 只有 working 的任务有活干。等输入的任务、已经结束的任务，step 都返回 False，工具不跑。
- cancel 请求在 step 里兑现：cancel_requested 的任务直接 cancelled，工具不再运行。Part 1 只是把请求记了下来。
- tasks/update 只接受任务正在等的 key：未知的 key（theme）、已经回答过的 key（第二次的 format: pdf）、被新请求取代的 key（approve_outline 之后换成了 approve_outline_2）都忽略，第一个回答算数。按 `issued_keys` 判断，旧 key 会被重新回答，工具看到的 format 就成了 pdf。
- 部分回答：两个 key 只答了一个，任务还是 input_required，inputRequests 只剩没答的那个。
- 回答必须是 elicitation 的结果。`{"action": "accept", "approved": true}` 把字段放在了 content 外面，accept 没有 content 对象，不算回答；只看 action、或者只看是不是对象，都会把它当成回答。decline 和 cancel 也是回答，含义由工具决定。照课里的代码把 decline 当成取消整个任务，会挂在 "once every key is answered the task is working again"。
- key 在任务一生中唯一：purge 工具问过 confirm、又问过 reason，第三次再要 confirm，任务要 failed，错误码 -32603。只记最近一轮的 key（`issued_keys = list(...)`）会放过这种情况。
- 工具返回 `isError: true` 仍然是 completed；工具抛 McpError 才是 failed。error 原样保存：没有 data 就不能有 data 键，也不能写成 `"data": null`。statusMessage 也要换成结局带来的文字：完成时是 Done 的 message，失败时是错误的 message，留着原来的 statusMessage 或写死 "Completed." 都会挂。
- worker 遇到不存在的 id 返回 False，不能拿 None 去读 status。
- 完成时 result 要带自己的 `resultType: "complete"` 和服务器的 serverInfo，和直接 tools/call 返回的一样。
- 每次修改都要盖 lastUpdatedAt：worker 和 tasks/update 都要走 `_save`。什么都没回答上的 update 不能保存，否则 lastUpdatedAt 白白变了。
- 每个任务方法都要校验所有者：别人对你的任务 get、update、cancel，得到的错误和不存在的 id 完全一样，任务也不能有任何变化。tasks/update 是新写的，最容易漏 `_owned_task`。
- tasks/update 也要先做过期检查。漏掉时，过期任务的回答照样被收下、任务回到 working，worker 接着把它做完了；测试最后的 "tasks/update fails an overdue task first" 就是这种情况。
- 可以接受的写法：按 `answers` 而不是 `issued_keys` 判断 key 是否重复。worker 只在没有未决 key 时运行，所以发过的 key 这时都已经回答过，两种写法在这里等价。可以追问：要是以后允许工具在还有未决 key 时追加请求，两种写法还一样吗？

追问：
- "Input needed before the task exists versus during it: how do the continuations differ?"（创建前用核心 MRTR：原请求返回 input_required，客户端带着 inputResponses 和 requestState 重试原 tools/call；创建后任务进入 input_required，tasks/get 看到 inputRequests，用 tasks/update 回答，不重试原调用）
- "Why may a key never be reused?"（客户端会对同一个未决 key 去重 UI，网络重试会重复提交；key 复用时，服务器分不清这是对旧问题的迟到回答还是对新问题的回答，可能把对旧大纲的批准当成对新大纲的批准）
- "The user declined. cancelled, a completed refusal, or something else?"（课里说都可以，但要写进文档；这里交给工具决定）
- "A tool raises KeyError instead of McpError. What should the worker do?"（测试没覆盖：可以让任务 failed 并记 -32603，也可以让 worker 崩掉、等租约过期后重试；要说清楚选了哪个，以及重试是不是幂等）

### Part 4 subscriptions/listen 的 SSE 流（目标 12 分钟）

坑：
- 先发 `notifications/subscriptions/acknowledged`，再等 tick。只列调用者自己的任务 id，按请求里的顺序，每个一次；别人的、不存在的、格式不对的（42）一律静默丢掉，不报错，也不能让人看出哪个 id 属于别人。
- 每条消息的 `_meta` 都带 `io.modelcontextprotocol/subscriptionId`，值等于 listen 请求的 id，类型也不变，7 不能变成 "7"。最后那条 listen 的结果里，subscriptionId 和 serverInfo 并列。
- 推送的快照要和那一刻的 tasks/get 一样，只去掉 resultType。直接 `store.get(...).to_wire()` 会绕过 tasks/get 的过期检查：export 已经到期，tasks/get 说 failed，流里却一直是 working，流也结束不了。只在流里显示过期、不保存也不行：过一秒再 tasks/get，lastUpdatedAt 就对不上了。最省事的写法是直接调 `service.tasks_get`，带上 listen 请求的 `_meta`。
- 只推变化：快照和上次发出去的（或者确认时的）一样，就不发。只比较 status 不够，statusMessage 变了也是变化，探针测的就是这个。只比较 lastUpdatedAt 也不够：时间戳只到秒，探针的修改和任务的创建在同一秒，lastUpdatedAt 没变。确认之后也不要先把每个任务推一遍。
- 已经结束的自己的任务也要出现在确认里：它属于调用者，只是没有变化可推。测试最后那次 listen 里的 export 已经 failed，确认要列出它，然后流马上以 listen 的结果结束。
- 任务推出终态快照后就不再看它。测试在 report 结束后把它删掉了，再读会得到 task not found。所有任务都结束时，发 listen 的结果，不再拉 tick（测试数了拉了几次）。
- 变化一出现就推：第一条通知必须在第一个 tick 之后马上出来。先攒着、等流结束再一起发，会挂在探针上。
- 格式由测试的解析代码决定：每次 yield 一个事件，一行 `data: ` 加 JSON，再一个空行。`json.dumps(indent=2)` 会把 JSON 拆成多行，只有第一行带 `data:`。注释行（keepalive）可以发，测试会跳过。
- 没声明 Tasks 扩展的 listen 请求，要在发出任何东西之前报 -32021。
- 写成普通的 async 函数（只有 return、没有 yield）时，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出这里需要 async generator。
- 测试没覆盖：一个还没结束的被监视任务中途被删掉（比如别的实例清理了它）。参考答案把它从监视列表里拿掉，流继续；让流抛错结束也说得过去，问候选人选了哪种、为什么。按 SSE 规范 `\r\n` 也能当换行，但测试的解析器只认 `\n`，docstring 写的也是空行，这一条按测试来。

追问：
- "The stream drops. How does the client catch up?"（用新的请求 id 重新 listen，再对关心的任务 tasks/get 一次；不靠事件重放，也没有 Last-Event-ID）
- "Why a POST response stream, not a GET stream?"（2026-07-28 没有协议会话，也没有独立的 GET 事件流；订阅就是一个普通请求，它的响应流就是订阅的生命周期）
- "Ten thousand subscribers each polling the store on every tick?"（换成存储的变更通知或消息队列，按任务 id 合并订阅；推送前仍然要按所有者过滤）
- "A task changes three times between two ticks. What does the client see?"（只看到最新的完整快照。快照是全量的，合并没有问题；中间状态要是重要，得另外记日志）

### Part 5 租约和过期清理（目标 12 分钟）

坑：
- 租约的时间用注入的时钟。用 `time.time()` 或 `datetime.now()` 的话，测试拨快了时钟让租约过期，墙上的时钟却没动，b 永远接管不了。
- 刚好满 lease_ms 就算过期：第 30 秒整，b 接管。
- 别人的租约没过期时 acquire 返回 False，不能覆盖。过期的租约可以接管，持有者被认为已经死了；只会说“文件在就失败”的 acquire 接管不了。
- release 只删自己的租约。worker-c 醒过来调 release 时，租约已经是 b 的了；不看持有者就删，a 就能在 b 干活的时候抢进来。
- 提交前确认租约还在：a 卡住超过了租约，b 接管并完成了任务，a 回来时不能再提交，结果必须是 b 的 "run 3"。只比较任务有没有变也不够：租约到期但还没人接管时，a 一样不能提交，因为它不知道别人是不是正要开始。
- step 结束时归还租约，包括什么都没做就返回的情况。测试最后让 a 对已经完成的 paused 再 step 一次，然后检查目录里没有 `.lease` 文件；只在提交成功后才 release 的写法会留下 a 的租约。
- 同一个持有者再 acquire 是续约：到期时间从这一刻重新算。只返回 True 不改到期时间，测试最后那段 held 会挂。
- sweep：ttl 从 createdAt 算，刚好满 ttlMs 就到期；ttlMs 为 null 的任务永远不过期，自己算 deadline 时忘了 None 会报 TypeError；没结束的过期任务（working 和 input_required 都算）先 failed，下一次 sweep 才删，只处理 working 会漏掉 waiting；已经结束的过期任务直接删；只返回这一次删掉的 id。finished 在创建 10 秒后才完成，按 lastUpdatedAt 算会晚 10 秒才到期。sweep 让任务 failed 也是一次修改，要盖 lastUpdatedAt，直接 `store.save` 不走 `_save` 会挂。
- 清理之后的区分（练习 5）：删掉的任务和从来没有过的 id，回一样的 task not found；别人的任务也是 task not found；格式不对的 id 是 invalid taskId，而且根本不会变成路径，`../elsewhere/...` 在 Part 2 的 store 里就被拦下了。别人的请求不能碰你的任务：先查所有者、再查过期，否则 alice 的一次 tasks/get 就把你的任务改成了 failed。

追问：
- "Two workers find the same expired lease at once. Can both take it over?"（会：先删再独占创建时，第二个 worker 可能删掉第一个刚建好的租约。要 rename 到唯一的名字再核对内容，或者用带 compare-and-swap 的存储。测试不覆盖这种竞争，第 29 课专门讲）
- "A lease keeps two workers from running at once. Does it stop the tool's side effect from happening twice?"（不能。持有者卡住时工具可能已经做完了副作用，接管的人会再做一次。副作用本身要幂等，或者带上 fencing token 交给下游校验）
- "Why fail an expired task first and delete it later, instead of deleting it at once?"（课里说服务器可以先让过期任务 failed、之后再删；先 failed，正在轮询的客户端能看到明确的结局，而不是突然变成 not found）
- "Should the owner learn that a deleted task expired?"（这里选择删除后一律 task not found。真要告诉所有者，得用只对所有者可见的墓碑，墓碑本身也要过期）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出 fsync 与原子替换、并发写、租约竞争与 fencing、订阅的扩展、过期与保留 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
