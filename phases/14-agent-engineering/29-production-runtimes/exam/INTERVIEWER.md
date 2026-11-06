# 面试官手册：RunShape（14/29）

候选人计时期间不要看。候选人手里只有 README、`runshape/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | agent 自己抛异常算失败吗？ | "Not here. Failures come from fail_policy; this agent never raises." |
| 1 | DeadLettered 带哪一次的错误？ | "The last attempt's, the one that sent the job to the dead-letter queue." |
| 1 | 进了 DLQ 的作业还会再跑吗？ | "No. A dead job stays dead, and result() keeps raising DeadLettered for it." |
| 1 | stop() 时队列里还有作业怎么办？ | "They stay queued. stop() is not a drain." |
| 1 | 订阅者返回什么？ | "The follow-up events it emits, or None. publish returns them in order." |
| 2 | 会有两个进程同时打开同一个库吗？ | "No. One process at a time. That is what makes recovery at open safe." |
| 2 | 时钟会倒退吗？ | "No. Treat clock() as monotonic." |
| 2 | 已经 done 或 dead 的作业还能 complete 吗？ | "No. Only a running job can complete or fail. Anything else is a ValueError." |
| 3 | 支持 MON、JAN 这种名字吗？ | "No, numbers only." |
| 3 | `5/15` 是什么意思？ | "Reject it. A step needs * or a range." |
| 3 | 日字段写 `*/10` 算受限吗？Vixie cron 把以 `*` 开头的字段都当成 `*`。 | "Here it is restricted. Only a bare * is unrestricted." |
| 3 | 按哪个时区算？ | "UTC. after can come in any zone; convert it first." |
| 3 | 停机一个月，错过的要不要全补？ | "No. 'latest' runs one fire, 'skip' runs only a fire that is on time. Count the rest as skipped." |
| 4 | 会同时有两个客户端吗？ | "No, one client at a time." |
| 4 | final 事件算在 ahead 里吗？ | "Yes, it is an event like the others. The tests don't cover it." |
| 4 | 客户端带来一个我们没发过的 id？ | "Raise ValueError. The tests don't cover it." |
| 5 | 两个订阅者能同名吗？ | "A name is one subscriber. It may listen to several event types." |
| 5 | 同一个 id 的事件来了两次，payload 不一样？ | "An id is the event. The first one to arrive wins." |
| 5 | 超过 max_depth、又没人订阅的事件记在哪？ | "In truncated. Past max_depth we don't look any further. The tests don't cover it." |

## 每关：要看什么、提示、追问

### Part 1 修队列（目标 12 分钟）

`fail_policy(job)` 返回这次尝试失败时的错误，不失败时返回 None。一个测试里叠了 4 个缺陷和 4 个护栏：

1. `_attempt` 一次尝试会问两次 `fail_policy`，这是课里代码原样的 bug：判断重试问一次，没进重试分支时判断进 DLQ 又问一次。错误不在 `_attempt` 报出来，而是在下一层的 `ScriptedFaults.__call__`：A 只写了一个结果，却被问了第二次，报 `LookupError: no scripted outcome left for 'A' (attempt 1)`。
2. 重试条件 `job.attempts < self.max_retries` 拿“已经做过的尝试次数”去和“重试次数”比，作业只跑 2 次就进 DLQ。docstring 写的是一共 `max_attempts` 次。
3. 死信分支只把作业停进了 `dlq`，`job.error` 也记下了最后一次的错误，却没有像成功分支那样把结局交给等结果的人：成功分支写 `_answers` 再 `_wake_waiters`，死信分支既不写 `_dead`，也不叫醒等待者。对提交它的调用方来说，这个作业悄悄消失了，就是讲义 Where production runtimes fail 里的 No DLQ。docstring 要求 `result()` 立刻抛 `DeadLettered(job_id, error)`，error 是最后一次尝试的错误，已经在等的调用方和之后才来问的都一样。测试里每个作业在 worker 开始之前就有一个调用方在等，每个最多等 1 秒，等不到就在测试的 `outcome` 里报 `TimeoutError: nothing came back for j003 within 1 s`，不会卡住。报错的是测试的辅助函数，根因在另一个任务里跑的 `_attempt`。这一处排在缺陷 1、2 后面：`run_jobs` 按日志判断作业是否都结束了，调用方的结果放到日志断言之后才看，所以重试次数没修时先报日志（B 和 C 第 2 次就死了，它们的调用方同样等不到）；修好以后 C 第 3 次失败进 DLQ，才轮到这一处。
4. 空闲 worker 每 50 毫秒轮询一次队列。40 个依次提交、每个都等结果的作业要 2 秒左右，限值 0.2 秒。docstring 写的是由 `enqueue()` 唤醒空闲 worker。前两段测试的作业都在 worker 启动前排好，只有这一段让 worker 空着等新作业；每次等结果最多 1 秒，`enqueue()` 根本不唤醒 worker 的写法在这里报 TimeoutError，不会卡住。
5. 护栏：改成通知以后，(a) 一次进来 12 个作业、3 个 worker 时，每个作业都要跑完，并且只跑一次；(b) `stop()` 之后 `serve()` 很快正常返回（用 `cancel()` 停 worker 的话，`serve()` 抛 CancelledError）；(c) 几个 worker 一起被唤醒时，不能对空队列 `popleft()`。常见的错法是每处理一个作业就 `clear()` 一次事件，一次来多个作业时剩下的就没人处理；或者 `stop()` 忘了唤醒正在等待的 worker。(d) `publish` 的订阅者隔离起始代码已经做对了：逐个订阅者 try/except，失败记进 `dead_letters`，格式是 `"RuntimeError: boom"`，后面的订阅者照常收到。断言都保留，改 `events.py` 时（比如 Part 5 想复用 publish 的投递代码）不能把它弄丢。

缺陷 3 和缺陷 4 都表现为调用方在等，根因不同：缺陷 4 的作业照常做完、结果照常交出，只是 worker 晚一个轮询间隔才开工；缺陷 3 是死信分支漏了交接，等多久都等不到。修缺陷 3 的常见错法：只写 `_dead` 不叫醒，已经在等的调用方照样超时；只叫醒不写 `_dead`，被叫醒的调用方在 `result()` 里报 `KeyError: 'j003'`；直接对等待者 `set_exception`、不记下来，测试在运行结束后又问了一次 j003，这个后来的调用方超时；对等待者 `cancel()`，调用方拿到的是 CancelledError；进 DLQ 时再调一次 `fail_policy` 去取错误，脚本用完报 LookupError；只在重试时记错误，DeadLettered 带的是倒数第二次的 `429 rate limited`。

看什么：是不是先读 traceback，发现报错的 `chaos.py` 本身没错，再回到调用它的地方；是不是把 `rt.log` 和 `faults.asked` 打印出来对照；TimeoutError 出来时，是不是先看日志里 j003 已经是 dead，再去查 `result()` 在等谁叫醒、哪些分支调用了 `_wake_waiters`，而不是把等待加长或者改成轮询；每改一处就重跑。

提示：
- H1："Who calls the fault injector, and how many times per attempt?"
- H2："Count the attempts job B gets. What does max_retries count?"
- H3：直接指出 `_attempt` 里的两处 `self.fail_policy(job)`。
- 卡在 TimeoutError 上时：先问 "The log says j003 is dead. Who tells the caller that is waiting for it?"，再指出成功分支和死信分支最后几行的区别。

追问：
- "Simulate 10% failure on 1,000 jobs. What DLQ size do you expect now, and what did the old code give?"（只判定一次时约 1000 × 0.1³ = 1 个；原来的代码约 100 个，大多数第一次尝试就进了 DLQ。课里代码讲解的实测是 100、87、89）
- "A job is dead-lettered at 3 a.m. Who finds out, and what happens to it next?"（调用方立刻拿到 DeadLettered；运维盯 DLQ 大小，这是讲义列的队列指标之一，超过阈值就告警；查明原因后把 DLQ 里的作业重新入队，所以 DLQ 要留着 payload 和错误。课里代码的 DLQ 只存 Job，代码讲解专门指出它不记失败原因）
- "Why not just poll every millisecond?"（空闲 worker 一直在消耗 CPU，worker 越多越浪费，延迟也还有下限；应该让取任务的一方阻塞等待通知。把 `IDLE_POLL_S` 改成 0.001 或 0 都能过计时，0 就是 `sleep(0)` 忙等，一个空闲 worker 占满一个核。测试看不出这两种写法，看到了就问这一题，代码质量按凑测试记）
- 有人把 `result()` 改成每隔一段时间去翻 `dlq`，绕开缺陷 3：间隔 50 毫秒会在计时那一段挂掉（每次往返都多等一个间隔），1 毫秒的能过。测试看不出后一种，看到了就问 "Why does the dead-letter branch not hand the outcome over, the way the success branch does?"，代码质量按凑测试记
- "popleft() happens before the work. What if the worker dies halfway?"（at-most-once，作业直接丢了；生产里先租用、做完再确认，是 at-least-once。Part 2 的作业表就是这样）

### Part 2 持久作业表（目标 12 分钟）

坑：
- claim 时就把尝试次数加一并提交。等到 fail() 才计数的话，作业跑到一半进程崩了，这次尝试就没算；一个每次都把 worker 弄崩的作业（讲义开头说的 background worker runs out of memory）永远进不了 DLQ。claim 只改不提交也一样：前面有 fail、complete 的提交顺带把它提交了，看不出来；第二次崩溃前没有别的提交，这次领取随着连接关闭回滚掉，作业同样进不了 DLQ。
- 打开库时处理上次留下的 running 作业，按 docstring 当成一次 `fail(..., "interrupted")`：记下错误、退避，最后一次直接进 DLQ。只把 status 改回 pending，会丢掉这条错误和退避时间。
- 退避是 `backoff_ms * 2 ** (attempts - 1)`：第一次重试等 1 秒，第二次 2 秒，第三次 4 秒。写成 `2 ** attempts` 会多等一倍。线性的 `backoff_ms * attempts` 前两次也是 1 秒和 2 秒，要到最后一段 max_attempts=4 的作业第三次失败才露出来：等了 3 秒，不是 4 秒。
- 到期判断是 `run_at_ms <= now`。新作业恰好在 now 到期，用 `<` 的话第一次 claim 就拿不到。
- 先按 run_at_ms，同时到期再按加入顺序。只按加入顺序排，先加入、后到期的重试作业会排到前面。
- dead_letters 按进 DLQ 的先后排，不是按加入的先后。两个作业在同一毫秒死掉时，按时间戳也排不出来，要一个递增的序号。
- complete() 和 fail() 都只接受 running 的作业：测试对一个 done 的作业分别调 complete 和 fail，再对一个 dead 的作业调 complete，都要报 ValueError。只拦 done 的写法过不了。
- 读回来要完全一致：errors 是元组，每条原样保留（里面有换行，用换行拼起来再拆开就坏了）；result 是空字符串时不能变成 None。换成别的分隔符（比如 `|`）能过这组数据，报错里一出现这个字符就坏了；run_at_ms 放进 REAL 列，读回来是 float，值相等所以测试看不出，但和 `int` 的注解不符。这两种都算代码质量问题，可以追问。

追问：
- "Two workers on two machines share this store. What breaks?"（打开时的恢复会把别人正在跑的作业当成中断；要有租约和超时，这一关不做）
- "The side effect happened, then the worker died before complete(). What now?"（at-least-once 会再做一遍，副作用要能重复执行，比如带幂等键）
- "Which numbers would you put on a dashboard?"（讲义列的队列指标：队列深度、单个作业耗时分布、DLQ 大小）

### Part 3 cron（目标 12 分钟）

坑：
- 步长从范围起点数：`9-17/4` 是 9、13、17；日字段从 1 开始，`*/10` 是 1、11、21、31。写成 `v % step == 0` 会得到 12、16 和 10、20、30。
- 周字段 0 和 7 都是周日。Python 的 `weekday()` 周一是 0，要换成 `(weekday() + 1) % 7`。直接用 `isoweekday()` 的话周日是 7，而解析时 7 已经并进了 0，周日永远匹配不上：`30 9 * * 1,7` 的下一次应该是周日 11 月 8 日。
- 日和周两个字段都受限（都不是 `*`）时任一匹配即可，这是经典 cron 的规则，POSIX 和 Vixie cron 都这样。`0 0 13 * 5` 在 11 月 6 日（周五）就触发，不用等到 13 号的星期五。只要有一个字段是 `*`，就要两个都匹配：`0 0 31 * *` 从 9 月 1 日往后找是 10 月 31 日。不分情况一律用“或”，周字段的 `*` 会让每一天都匹配，报的是“with day of week *, only the day of the month decides”。
- “受限”只看字段是不是单独一个 `*`。这里和 Vixie cron 不一样：Vixie cron 把以 `*` 开头的字段（比如 `*/10`）也当成没受限。`Cron` 的注释和断言消息都写明了这里的规则，熟悉 Vixie 的候选人可能会问。
- 只限定了日、而所在的月没有这一天时（2 月 30 日），永远不会触发，要报 ValueError；`0 0 30 2 1` 因为任一匹配，2 月的每个周一都会触发。完全不做这个检查、靠跳月一路找到 9999 年的写法，最后 `date(10000, 1, 1)` 报 ValueError，碰巧也能过（约 0.06 秒，计时区分不出它和合理的 400 年搜索窗口）；按天加 `timedelta` 一路找的话报 OverflowError，过不了。看到前一种，追问它凭什么知道 2 月 30 日永远不会来。
- 2 月 29 日：2100 年不是闰年，从 2096 年 3 月往后找要找到 2104 年。搜索窗口只开 4 年，就会误判成永远不触发。
- 一分钟一分钟往后找，两次找 2 月 29 日要 1.1 到 2 秒；一小时一小时找也要 38 到 66 毫秒。限值 0.01 秒。按天找、月份不对就跳到下个月，只要零点几毫秒；按天找但不跳月也只要 1 毫秒左右，能过。
- 调度按 UTC 走。`after` 可以带任何时区，要先换算；不带时区的 datetime 报 ValueError。返回值也要是 UTC：按 `after` 的时区返回的话，和期望值比较是相等的，但 `utcoffset()` 不是 0。
- 补跑看的是 `(last_fire, now]`：last_fire 已经处理过，正好落在 now 上的那次算到期。"latest" 只跑最近的一次；"skip" 只跑落在当前这一分钟里的那次：03:00:20 时 03:00 那次准时，03:01:00 时它已经晚了，用 `now - fire <= 60 秒` 判断会把后一种也算成准时。其余的都计入 skipped。

追问：
- "Two scheduler replicas tick in the same minute. How do you avoid running the nightly eval twice?"（课里 skill 的要求：用锁文件或分布式锁防止重叠运行；也可以把触发写进 Part 2 的作业表，按“计划名 + 触发时间”去重）
- "The nightly run failed at 03:05. What happens at the next tick?"（讲义说 cron 要和 durable execution 结合，失败的夜间任务在下一次 tick 接着跑；把触发变成作业，就有了重试和退避）
- "Why run schedules on UTC?"（本地时间有夏令时，某些分钟一年里会出现两次，某些根本不存在）

### Part 4 SSE 流（目标 14 分钟）

坑：
- 要有单独的生产者任务，最多领先客户端 `ahead` 个事件。完全不领先（客户端读一个才做一个），或者不设上限（一口气跑完），都过不了。用 `asyncio.Queue(maxsize=ahead)` 并且先取下一步再 `put`，会多做一步：agent 已经把第 3 步做完，才发现没地方放。
- 事件一交给客户端就算读过了，不用等客户端来要下一个。
- 交出事件时不能还拿着锁。在 `async with condition:` 里面 `yield`，客户端拿着这条事件的整段时间锁都没放，生产者拿不到锁，读走一条以后 agent 也不往前走，客户端读完第一条后的探针就报错。测试里断线重连那一段用 `aclosing` 关闭它打开的每个流，所以这种写法会报错，不会卡在 `asyncio.run` 收尾的地方。
- 断线不结束这次运行，agent 停在缓冲满的地方等客户端回来。断线时取消生产者任务的话，重连后只能读到日志里已有的几条，然后卡住。
- 重连从 Last-Event-ID 的下一条开始。客户端可能没收到断线前的最后一条（测试里第 2 条没送到，重连时带的是 1），所以发出去的事件要留着，不能只放在队列里：从队列取走的事件没法再发一次。只用队列的写法重连后拿到的是第 3 条，先在“never more than `ahead` events wait for the client”这个探针上报错：客户端手里只有第 1、3 条，agent 已经做到第 5 步。
- final 只发一次。已经收到 final 的客户端再连上来，流应该直接结束，而不是继续等新事件。
- 回合预算只算 agent 自己干活的时间，也就是 `__anext__` 里走过的时钟；等客户端的时间不算。用 `clock() - 开始时间` 的话，慢客户端会让一次没干多少活的运行“超预算”；在等空位之前就记下这一步的开始时间，也会把等客户端的时间算进去。预算正好用完就停：是 `>=`，不是 `>`。
- 格式由测试的解析代码决定：每个字符串是一条完整的 SSE 消息，`id:`、`event:`、`data:` 各一行，最后一个空行；data 是一行 JSON。

追问：
- "The client goes away while the agent is in the middle of a model call. What does that cost?"（只能在步骤之间暂停；已经发出的模型调用照样计费）
- "How long do you keep a paused run around?"（要有上限，超时就结束，或者转成后台作业，结果通过 webhook 交回去；这需要 durable 状态）
- "What would you measure on this stream?"（讲义列的流式指标：首 token 延迟、每个 chunk 的耗时、尾延迟）

### Part 5 事件级联（目标 10 分钟）

坑：
- 广度优先，深度从 0 开始。用递归写成深度优先，顺序不对；从 1 开始数，会少投一层。
- 同一个事件 id 在一次级联里只处理一次。`pr7:notify` 从两条路径过来（菱形）；`pr7:stats` 一次在第 2 层、一次在第 3 层。不去重的话，第 3 层那次会被当成超深事件，记进 truncated。
- 超过 max_depth 的事件不投递，但要记进 truncated；没有订阅者的事件记进 unhandled。课里代码对没人订阅的事件直接返回空列表，不报错也不记录（代码讲解 3.5 节）。
- 重放：每个订阅者对同一个事件 id 只处理一次，这份记录跨多次 cascade 保留。加了新订阅者再发布一次，只有它收到。按事件 id 记的话，新订阅者永远收不到；不记的话，所有订阅者重跑一遍。账本的键是事件 id，不是事件类型：ping/pong 回环里每个事件都是新 id，按类型记的话第二个 ping 就被跳过了。
- 抛异常的投递不算处理过，重放时要再试。先记“已处理”再调用订阅者，失败的那次就再也不会重试。失败的投递只进 dead_letters，不进 deliveries，也不进 unhandled：这个事件有订阅者，unhandled 只记没人订阅的事件。
- 返回 None 或空列表的订阅者也是成功投递，要记进 deliveries 和账本。把订阅者自己返回的 None 原样传回来、同时又用 None 表示失败，或者用 `if not out` 判断失败，都会把它当成失败；测试里的 reporter 就是这样一个订阅者。
- 一个订阅者的输出触发另一个、再触发回来，而且每次都是新 id 时，只能靠 max_depth 停下来。

追问：
- "The lesson's skill asks for an explicit subscriber registry and a replay path. Where are they here?"（`subscribers` 是注册表；按订阅者记的已处理集合加上重新发布，就是重放的路径。生产里事件要先落盘才能重放）
- "The handled set lives in memory. What happens on restart?"（重启后会重复投递；要把这份记录持久化，或者让订阅者可以重复执行）
- "The workflow is compliance-bound. Is this event bus enough?"（skill 的拒绝规则：合规场景下，没有审计记录的事件驱动不能用；deliveries 和 dead_letters 都要落盘）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出投递语义、死信的去向、退避、补跑、背压、重放和可观测性 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
