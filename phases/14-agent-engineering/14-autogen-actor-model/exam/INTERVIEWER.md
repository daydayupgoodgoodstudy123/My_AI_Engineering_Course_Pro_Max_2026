# 面试官手册：ActorRT（14/14）

候选人计时期间不要看。候选人手里只有 README、`actorrt/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 测试文件里的 Collect、Audit、Splitter、Batcher、Fragile、Speaker、Echo、Node 是测试自己的 actor，告诉候选人不要改它们。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | handler 里 send 的消息，能不能像函数调用那样马上交给收件人？ | "No. send() puts it in the inbox and returns. The runtime delivers it later, in the order it was sent." |
| 1 | 收件人处理失败，死信记在哪条消息上？ | "On the message whose handler raised. The actor that sent it never sees the error." |
| 1 | body 是深拷贝还是冻结成只读？ | "A deep copy, taken when send() is called. The recipient may change its own copy." |
| 1 | handler 里 send 拿到的 mid，消息被丢弃以后还算不算？ | "It's used up. send() hands the mid out at once; a dropped message just never arrives." |
| 1 | handler 抛异常时，它已经改过的状态要回滚吗？ | "No. Only its messages are dropped. The runtime can't undo an actor's state." |
| 1 | review 失败时要不要通知 checklist？ | "Not today. The checklist stays undecided. Tell me how you'd add it." |
| 1 | 发布到没人订阅的 topic，要进死信队列吗？ | "No. Nothing is queued and nothing is dead-lettered." |
| 2 | flush 够吗，要不要 fsync？ | "flush is what the tests can see. Tell me what fsync would add." |
| 2 | 日志要压缩吗？ | "Not today. It's append only." |
| 2 | 文件中间有坏记录怎么办？ | "Only a torn record at the very end is expected. Anything else may raise." |
| 2 | 崩溃以后同一条消息被处理两次，可以吗？ | "Yes, that's at-least-once. What must never happen is losing it." |
| 2 | 恢复出来的消息算新的 send 吗？ | "No. They go back on the queue as they were, with their old mids." |
| 3 | 第一个发言者也由选择者选吗？ | "Yes. The selector picks every turn, the first one too." |
| 3 | 选择者第一回合就给了不存在的名字呢？ | "Fall back to the rotation, which starts with the first participant. The tests don't cover it." |
| 3 | 选择者回答 "Reviewer" 或 "the reviewer" 算 reviewer 吗？ | "No. Strip the whitespace; then it has to match a name exactly." |
| 3 | max_messages 包括任务吗？ | "Yes. The task is the first message." |
| 3 | run_until_idle 到了上限、返回 False 时，run() 要接着跑吗？ | "Yes. Its cap is per call. A chat is stalled only when the runtime goes idle." |
| 3 | 参与者失败了要重试吗？ | "No. The chat is stalled, and the failed turn is in the dead-letter queue." |
| 3 | 任务里出现终止词呢？ | "The task is never checked. It's the instruction, and it often names the stop word." |
| 4 | 心跳要回一个心跳吗？ | "No. Skip it." |
| 4 | 帧发给本机不存在的 actor 呢？ | "Deliver it like any other message. The runtime dead-letters it here." |
| 4 | 帧里的 mid 用哪一边的？ | "Each host writes its own mids. An arriving message gets a mid of this host." |
| 4 | 坏帧跳过还是报错？ | "Raise ValueError, after everything before it has been delivered. Nothing after it is delivered." |
| 4 | JSON 要紧凑格式吗？ | "Either. The other side parses JSON. Only the length and the UTF-8 matter." |
| 5 | 停止时兄弟之间什么顺序？ | "The most recently spawned child first, and each subtree before its parent." |
| 5 | handler spawn 以后又抛了异常，孩子还在吗？ | "Yes. A spawn isn't a message, so it isn't dropped. The tests don't cover it." |
| 5 | 停止的 actor 的名字能再用吗？ | "No. Names are unique for the life of the runtime." |
| 5 | 发给已停止 actor 的消息，要在 stop 的时候就挪进死信吗？ | "No. Dead-letter it when its turn comes, like a message for an unknown name." |

## 每关：要看什么、提示、追问

### Part 1 修 runtime（目标 12 分钟）

一个测试里叠了 4 个缺陷和几个护栏：

1. handler 里调用 `send` 时，起始代码不入队，直接调用收件人的 `receive`，就是 v0.2 里 `agent_a.chat(agent_b)` 的写法：收件人在发件人的 handler 里同步跑完。收件人抛的异常顺着调用栈落进发件人的 handler，runtime 在最外层接住，记成发件人那条消息的死信。测试看到死信队列里是 `("__user__", "checklist", "start", ..., "TypeError: snippet 1 is not text")`：reviewer 的错记到了 checklist 的 start 头上，reviewer 自己那条 review 反而不在死信里，start 的 handler 也断在半路，snippet 2 没有送审。异常在 ReviewerAgent 里抛出、在 run_until_idle 里被接住，根因在 send，中间隔着 checklist 的 handler。课里 Why decoupling matters 讲的就是这一条：v0.4 的 send 把消息放进收件箱就返回，由 runtime 稍后投递，发件人不在收件人的调用栈上（测验 Q3、Q13）。
2. handler 先 send 再抛异常时，已经发出的消息照样被投递（测验 Q11 第 2 问的 trace）。docstring 规定 handler 发的消息要等它返回才入队，抛异常就整体丢弃，原消息进死信。第 1 处修好以后才露出来：同步投递时，gamma 在 splitter 抛异常之前就已经送到了。
3. ChecklistAgent 在已到的 verdict 都 ok 时就宣布 True，期望数量写死成 3（测验 Q9）。部分运行、某条 review 抛异常永远回不来、4 条 snippet 时都会给出错误结论。
4. `subscribe` 在一个列表里查重，`publish` 每次扫描全部订阅。8000 个订阅加 20000 次发布本机约 1.3 到 1.6 秒（机器忙时到 3.4 秒），限值 0.1 秒；按 topic 建索引后约 3 到 9 毫秒。
5. 护栏：
   - send 只入队。在 send 里给直接调用包一层 try/except、把收件人的异常就地记到它自己那条消息上，死信是对了，可 reviewer 还在 checklist 的 handler 里同步跑：`run_until_idle(max_messages=1)` 处理完 start 就把两条 review 也审完了，测试报 `a message sent from a handler waits in the inbox for its turn`。要去掉的是 send 里的那次调用，不是再包一层 try/except。捕获以后再抛出去，start 和 review 两条都进死信；捕获以后吞掉，死信队列是空的。
   - 按发送的顺序投递。改成先处理最新的消息，或者把 handler 发出的消息插到队首，reviewer 的 verdict 顺序或 max_messages 那一段已到的 verdict 数就对不上。这只是顺带检查，这一关不考遍历顺序。
   - body 的深拷贝起始代码已经做对了，改 send 时不能把它弄丢。拷贝的时机是 send 被调用的那一刻：测试在 send 之后往自己的列表里追加了一条，Batcher 发出一对以后马上清空缓冲区重用，送达时才拷贝、handler 返回时才拷贝都会挂。每个接收者一份：publish 只拷一次给所有订阅者共用，checklist `pop("id")` 以后 audit 抛 `KeyError: 'id'`，进了死信；浅拷贝挡不住嵌套的 issues 列表。以为排了队就不用拷贝、把拷贝删掉，也是 audit 的 KeyError。课里说 two actors cannot share memory，这一条要由 runtime 保证。
   - 丢弃以一次 handler 调用为单位。reviewer 审完 snippet 0、发出的两条 verdict 还在队列里时 snippet 1 失败；Splitter 那一段，第一批的 alpha、beta 还在队列里时第二批失败。按发送者清队列或者按 mid 清队列，都会把这些成功调用发出的消息一起丢掉。
   - 失败以后 outbox 要复位，否则之后从外面 send 的消息会掉进一个没人提交的列表。
   - 索引要去重并保留第一次订阅的顺序：set 会打乱顺序，list 会重复投递；只给 publish 建了索引、subscribe 还在列表里查重，8000 次订阅本身就要 0.2 到 0.3 秒。
   - handler 发出的消息按发出的顺序提交。倒着提交，reviewer 先审到最后一条 snippet，测试报 verdicts 的顺序不对。
6. 可以接受的写法：用 `json.loads(json.dumps(body))` 代替 `copy.deepcopy` 也能通过，这里的消息体都是 JSON 值，Part 2 和 Part 4 本来就要把它们序列化。可以追问它和 deepcopy 的差别：元组会变成列表，非字符串的键会变成字符串，集合和 bytes 直接报错。

看什么：看到 reviewer 的 TypeError 记在 checklist 的 start 上时，有没有去查 reviewer 是在谁的调用栈里跑的，而不是去改 ReviewerAgent、ChecklistAgent，或者在 send 里补一层 try/except；会不会读 traceback、在 handler 里打印调用栈；有没有先打印 `runtime.dead_letters`；每改一处就重跑。

提示：
- 同步投递那一层：H1 "Which handler was running when the reviewer raised?" H2 "Print the call stack inside ReviewerAgent.receive. Who called it?" H3 直接指出 `send` 在 handler 里直接调用了收件人的 `receive`。
- outbox 那一层：H1 "When should a message sent inside a handler become real?" H2 "What if the runtime collected the sends and decided after the handler returns?"
- checklist 那一层：H1 "How does the checklist know it has every verdict?"
- 计时那一层：H1 "How many subscriptions does one publish look at?"
- 拷贝那条护栏（候选人把拷贝改坏了才用）：H1 "Who else holds the dict that audit received?" H2 "Print id(message.body) in the checklist and in audit."

追问：
- "In v0.2, agent_a.chat(agent_b) handed B's answer straight back. What do you give up by queuing, and how does A get the answer now?"（回答变成另一条消息，要带关联 id 或 reply-to；A 不能在一个函数里等结果，等待的状态要放进自己的私有状态；换来的是故障隔离、max_messages 能封顶、可以并发，测验 Q14）
- "Deep-copying every body is expensive. What do real systems do?"（跨进程本来就要序列化成字节；进程内可以约定消息不可变、只读共享）
- "Your outbox drops the messages. What about the state the handler already changed?"（runtime 回滚不了；handler 先算后改，或者用事件溯源重建状态）
- "The checklist stays undecided forever when a review fails. How would you fix that?"（失败通知或超时消息，测验 Q9 第 3 问）
- "run_until_idle returned False. What should the caller do?"（这是防消息风暴的上限；记录告警，再决定继续跑还是报错，测验 Q11）

### Part 2 收件箱日志（目标 13 分钟）

坑：
- 记录格式在 docstring 里：1 字节类型、8 字节大端 mid、4 字节大端长度、payload。测试用自己的 struct 解析器读文件，小端、mid 只用 4 字节、长度按字符数算都会读歪。M 的 payload 只有四个键，mid 在头里。D 的 payload 是原样的 UTF-8 文本，不是 JSON；`büro` 测的是非 ASCII 的原因文本。
- M 的写入时机：handler 里发的消息要等 handler 返回才写。在 send 里就写的话，失败的 handler 发出的 alpha（mid 5）会进日志，重启以后被当成待处理消息投递。
- A 要在 handler 返回、它发出的消息都写完以后再写。先写 A 再写那些 M，中间崩溃就丢了它发出的消息；调用 handler 之前就写 A，handler 中途崩溃时这条消息就丢了（at-most-once）。测试用一个 BaseException 模拟进程在 handler 里死掉，重启后那条消息必须还在，它发出的 half done 必须不在。
- runtime 只捕获 Exception。改成 BaseException 会把“进程崩溃”也当成普通失败吞掉，测试报 DID NOT RAISE。
- 每条记录写完都要 flush，测试在日志还开着的时候直接读文件。
- 下一个 mid 是日志里最大的 mid 加 1。只看待处理消息，全部处理完以后会从 1 重来；按 M 记录的条数算，被丢弃的 mid 5 会让编号撞车；取最后一条记录的 mid 也不对，第一次重启时文件的最后一条是 A3，前面还有待处理的 m4、m6、m7（测试直接检查 `recover().next_mid`）。
- 末尾被截断的记录要丢掉，而且要在写新记录之前把文件截回最后一条完整记录。测试把最后一条记录从第 1 个字节到倒数第 1 个字节逐一截断。只在读的时候跳过、不截断，新记录会接在残片后面，文件从那里开始读歪；不检查记录是否完整，struct 会在残缺的头上报错；头完整就把 payload 读到文件末尾为止，会读出半截 JSON。
- 打开文件用追加模式时，读之前要先 seek 到开头；用 `w` 打开会清空文件。用 `r+b` 打开再 truncate，写指针还停在旧的末尾，下一条记录写在那里，中间留下一段零字节，测试报 `every record is M, A or D`；`a+b` 的写入总是落在文件当前的末尾。
- 恢复的消息直接放回队列，不能再 send 一遍，否则 mid 会变，日志里还会多出重复的 M。经过会写日志的 `_enqueue`、`_dead_letter` 放回去，mid 不变，日志里照样多出重复的 M 和 D，测试检查打开日志不写任何东西。
- body 要原样恢复：键的顺序、`2**64 + 1`、`0.1 + 0.2`、`-0.0`、`True` 和 `1` 都要分得开。标准库 json 默认就能做到，`sort_keys=True` 会改掉键的顺序。

追问：
- "The journal grows forever. What would you do?"（定期压缩：写一个只含待处理消息和死信的新文件再原子替换；或者按段滚动）
- "flush is not fsync. When does that matter?"（flush 只把数据交给操作系统，断电会丢；fsync 才落盘，代价是延迟，可以攒一批再 fsync）
- "After a crash a message is handled twice. Is that OK?"（at-least-once；handler 要幂等，按 mid 去重）
- "Two runtimes share one journal?"（不行；一个日志一个写者，需要锁文件或者每个 runtime 一个日志）

### Part 3 群聊编排（目标 12 分钟）

坑：
- team 本身是一个 actor，所有交互都走消息：manager 发 speak，参与者回 said。参与者是测试写的脚本化 actor，不能直接调用它们的方法。
- 回退的起点是最后一个发言者在轮转中的下一位。用 `participants[0]`、按回合数取模、另外维护一个回退计数器，都会在第 3 回合选错。
- 选择者的回答先 strip（`" coder\n"`），再精确匹配名字；`TESTER` 大小写不同，`the reviewer` 多了字，都算未知名字。按子串在回答里找名字，会把 `the reviewer` 当成 reviewer，原因记成 `selector`。
- 不允许重复时，选择者选了上一位发言者也回退到轮转的下一位，原因记 `repeat`；`allow_repeated_speaker=True` 时照选。第一回合也由选择者选。
- 终止词按整词、区分大小写：`NOT APPROVED`、`DISAPPROVE`、`approve` 都不算。子串匹配、忽略大小写、按空格切词（`APPROVE!` 带着标点）、要求整条消息就是终止词、用 `re.match` 只看开头、`\b` 只加一边，都会错。
- 终止在每条消息之后检查，不是每一轮之后；任务本身不检查，测试的任务里正好写着 `Reply APPROVE ...`。
- max_messages 把任务算在内，任务本身就可能占满：`max_messages=1` 时没有人发言。只在参与者发言之后检查上限，会多问一个人。同一条消息既到上限又含终止词时，原因是 `stop_word`。
- 参与者失败（脚本用完，`pop` 抛 IndexError）时 runtime 空闲了但聊天没结束，原因是 `stalled`，失败的 speak 在死信队列里。
- 只有 runtime 空闲了才算 stalled。`run_until_idle()` 每次最多处理 runtime 的 max_messages 条（默认 100），返回 False 时聊天还在进行。run() 只调一次，60 条消息的聊天停在第 50 条，结果是 stalled。循环调用到聊天停下或 runtime 空闲为止；一直跑到 runtime 空闲、不看聊天停没停，也能通过。
- 不是正在等的那个人发来的 said 要忽略。测试在聊天开始前塞了一条上一场遗留的回答。
- 选择者每次拿到的是当时对话的副本和参与者列表。把内部列表直接交出去，测试事后看到的会是整场对话；把上一位发言者从候选里去掉，选择者看到的参与者就不对了。
- 发给参与者的对话是 `[source, text]` 列表，交给选择者的是 `(source, text)` 元组，两边不能混。

追问：
- "In production the selector is a model call. What can go wrong, and how do you guard it?"（返回不存在的名字、多余的文字、超时；严格校验、回退、把原因记下来，就是这里的 selections）
- "run() keeps calling run_until_idle while the chat waits. What if another actor floods the runtime?"（每次调用有上限，循环本身没有；给 run() 一个总的消息预算或截止时间，到了就按 stalled 或单独的原因结束）
- "The manager sends the whole conversation every turn. What about 200 turns?"（每轮 O(n)，总共 O(n²)；改成只发增量、参与者自己记历史，或者做摘要）
- "When would you pick a selector over a fixed rotation?"（发言顺序取决于内容的时候；代价是每轮多一次模型调用，结果也不确定）

### Part 4 跨主机帧（目标 13 分钟）

坑：
- 帧格式由测试的解析代码决定：4 字节大端长度，后面是 UTF-8 JSON，长度按字节算，不含这 4 个字节。非 ASCII 文本按 UTF-8 原样写，不能是 `\u` 转义（docstring 规定，测试检查原始字节）。
- 输入按任意大小到达：整块、一个字节一个字节、长度头和 payload 分开、中间夹着空块。缓冲区要跨块保留：每次 feed 替换缓冲区、一块只取一帧、把空块当成流结束，都会在最后报 `the stream ended inside a frame`。
- 长度为 0 的帧是心跳，跳过。当成消息解析会报 `Expecting value`；回一个心跳也不对，测试把每个 item 当成一条回复来读。空字符串和 null 的 body 是正常消息，不能当心跳丢掉。
- 每条消息投递后马上 `run_until_idle()`，并把这期间写出的帧立刻 yield，一帧一个 item。测试记录每个回复出来时读了多少字节、reviewer 已经给出几个 verdict：一块里的帧先全部投递再统一回复、读完整个流再回复、把一次投递的两帧拼成一个 item，都会挂。
- serve 开始时已经在 link 上等着的帧要先发出去，而且是在读第一块之前。
- 进来的消息用本机的 send 入队，拿本机的 mid。直接沿用对端的 mid，会和本机的编号混在一起。
- 坏帧（不是 JSON 对象、缺 topic、topic 是 null、不是 UTF-8）和流在帧中间结束（包括停在 4 字节的长度头中间）都要报 ValueError，而且要在它前面的帧投递完以后；坏帧后面的帧不再投递。KeyError、TypeError 不算；只检查键在不在、不检查是不是字符串，topic 为 null 的帧会被投递；剩下不到 4 个字节就当成正常结束也不对；先把一整块里的帧全部解析出来再投递，坏帧会连累它前面的好帧；捕获 ValueError 悄悄结束，或者跳过坏帧、到流结束才报错，也不对。
- 骨架里的 serve 是只有 raise 的 `async def`，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要看出这里需要 async generator。

追问：
- "What if one side writes faster than the other reads?"（async generator 只在被拉取时前进；真实的 socket 要限制缓冲，靠 TCP 流控形成背压）
- "The connection drops and comes back. What happens to frames in flight?"（会丢或者重发；接收方按（主机, mid）去重，发送方留着没确认的帧）
- "Why a length prefix and not newline-delimited JSON?"（读端先知道要读多少字节，payload 里有什么都不影响切分）
- "Exercise 3 in the lesson uses JSON over HTTP. What changes?"（一次请求一条消息，回复可以走响应；要多处理连接、超时和重试）

### Part 5 spawn 树（目标 10 分钟）

坑：
- 树是 handler 通过消息长出来的：pool 先 spawn ingest 和 index，它们各自收到 grow 以后才 spawn 自己的孩子。所以 spawn 的时间顺序是 pool、ingest、index、parse、fetch、shard-0、shard-1、tokenize，和树的先序遍历不一样。
- 停止是后序：子先于父，同一个父亲的孩子从最后 spawn 的那个开始。按全局 spawn 时间倒序停，tokenize 会排到 fetch 前面；用栈做先序遍历再整体倒过来，顺序变成 tokenize、parse、fetch、ingest；按 spawn 顺序停、按名字倒序停、先停父亲、只停直接孩子都会挂。
- 发给已停止 actor 的消息轮到它时进死信，原因是 `stopped`，不是 `no actor`。把停止的 actor 从 `actors` 里删掉，原因就变成 `no actor`，名字也能被重新使用；在 stop 时就把队列里的消息一次扫进死信，死信的顺序会和投递顺序对不上（中间夹着一条 `no actor 'nobody'`）。
- 已停止的 actor 之前发出、还在队列里的消息照常投递；actor 在 handler 里停止自己以后，这次 handler 发出的消息也照常投递。
- 已经停止的不再停第二次：on_stop 只调用一次，stop 的返回值只列这次新停的。对已停止的名字调用 stop 返回空列表，不报 KeyError，KeyError 只留给从没出现过的名字。
- 名字终身唯一，停止后也不能复用；在已停止或不存在的 actor 下面 spawn 报 ValueError；stop 一个不存在的名字报 KeyError。
- tree 只列活着的 actor，按启动的顺序，不按名字排序。

追问：
- "A child keeps crashing. Should its parent restart it?"（课里的 let it crash：由监督者按策略重启，要有次数上限和退避）
- "What should happen to mail for a stopped actor in production?"（进死信并告警，或者转给接替它的 actor；发送方要能知道）
- "How would you stop a tree that spans two hosts?"（停止本身也要变成消息，经 Part 4 的链路送过去，还要等对方确认停完）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback 和死信队列、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出排队的代价和回复的关联、拷贝成本、at-least-once 与幂等、fsync、选择者校验、背压与重连、监督与重启 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
