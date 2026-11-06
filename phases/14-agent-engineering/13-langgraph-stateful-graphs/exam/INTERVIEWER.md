# 面试官手册：StateGraph（14/13）

候选人计时期间不要看。候选人手里只有 README、`stategraph/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 测试里的 `Desk`、`Api`、`Clock` 和脚本化的 router 是外部世界的替身，不要改它们。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 在 gate 暂停后恢复，是重跑 gate 还是跑下一个节点？ | "The next node. The gate's step is checkpointed, so resume picks up at step N+1. The gate's own edge decides whether that is send or the gate again." |
| 1 | 暂停标记算不算 state 的一部分？ | "No. It's a signal from the node to the runner. Neither the checkpoint nor the state keeps it." |
| 1 | 人改 state 算不算一步？ | "Yes. A step of its own, node HUMAN, and what it wrote is the edit." |
| 1 | router 返回一个没有对应边的标签怎么办？ | "Raise GraphError. The run must never end quietly in the middle of the graph." |
| 1 | 检查点能不能直接引用 state 对象？ | "No. A checkpoint must not change after its step, whatever a node does with its objects later." |
| 2 | 能用 pickle 吗？ | "No. The file stays JSON text, and anything outside the listed types must fail loudly." |
| 2 | datetime、Decimal 这类值呢？ | "Not supported. dumps raises TypeError, and so does put." |
| 2 | set 要保留顺序吗？ | "Sets have no order. It just has to come back equal, and still a set." |
| 2 | 一张表还是两张表？ | "Your call. The tests only go through put and records." |
| 2 | 两个 worker 写同一步怎么办？ | "The second put raises ValueError. Concurrency beyond that isn't tested." |
| 3 | 节点崩溃后重跑，崩溃那次的调用要不要重放？ | "No. Calls only count once their step is checkpointed. The crashed attempt is forgotten, and the rerun records fresh." |
| 3 | 重放时节点的调用比录制多，怎么办？ | "That's a mismatch. Never fall back to the real API." |
| 3 | replay 需要 World 吗？ | "No. A replay has to work with nothing real attached." |
| 3 | replay 返回什么？ | "The final state, the same one load_state gives." |
| 3 | update 用 == 比较就行吗？ | "Yes, plain equality, once the pause marker is out." |
| 4 | START 也要发事件吗？ | "Yes. Every checkpoint the stream writes, the inputs and human edits included." |
| 4 | interrupt 和 end 带不带 id？ | "No. Only updates events do, and their id is the step." |
| 4 | 节点抛异常时流怎么办？ | "The events before it are already out. The error propagates, nothing more is sent." |
| 4 | 换行用 LF 还是 CRLF？ | "LF." |
| 4 | 要不要把整个 state 发给 UI？ | "No, only what the step wrote. The client applies it." |
| 5 | 子图能看到父图的整个 state 吗？ | "Yes, a copy, checkpointed as the subgraph's START step." |
| 5 | 子图交回给父图的是什么？ | "Everything its steps wrote after START, folded through the subgraph's reducers. Not its final state." |
| 5 | 暂停在子图里时，patch 交给谁？ | "The subgraph that paused. It becomes a HUMAN step in that namespace." |
| 5 | 同一个子图节点能跑两次吗？ | "Yes, in a loop. Each run gets a namespace of its own, with the parent step in it." |
| 5 | 嵌套暂停的 PausedAtNode 报哪一层？ | "The innermost: that node, its step and its namespace." |

## 每关：要看什么、提示、追问

### Part 1 修暂停与恢复（目标 14 分钟）

一个测试里叠了 4 个缺陷（第 3 个分两层）和几个护栏：

1. `_loop` 先写检查点、后 pop `_pause_reason`，照抄了课里 `Runner.run` 的顺序，暂停那一步的检查点里留着暂停标记。错误不在暂停时报出来，而是在恢复时：人已经批准了，`resume` 却在 `human_gate` 上又停了一次（`PausedAtNode: human_gate`）。从检查点读回来的 state 带着旧标记，节点一合并、一检查，就又暂停。课里的 `main()` 恢复前手动 `pop("_pause_reason")`，绕开的正是这个问题。
2. `_position` 返回最后一个检查点对应的节点本身，恢复时把已经完成的节点再跑一遍。审批场景里多出一个 `human_gate` 步；崩溃场景里会再开一张工单。课里说的是 resume picks up from step N+1。
3. `next_node` 把条件边展开成每个标签一条边，每条边各调一次 router，和课里 `_make_router` 的写法一样。脚本化的 LLM router 每次回答不同，调了 3 次以后走到了 sales。修成只调一次以后，下一层是：没有边对应的标签，或者没有出边的节点，返回 None，`_loop` 把 None 当成结束，静默返回。docstring 要求抛 GraphError。
4. 每一步都把整个 state（1500 篇文档的工具状态，加上不断增长的消息列表）作为记录交给 checkpointer，`put` 再 deepcopy 一遍。800 步在本机约 2.0–3.1 秒；记录里只存这一步写的 update，读的时候按 reducer 折叠，约 6–10 毫秒。限值 0.15 秒。
5. 护栏：
   - 只存 update、读的时候不折叠（课里的 Checkpoints too small）：恢复时 state 里只剩最后一步写的东西，send 报 `KeyError: 'ticket'`。
   - 折叠时不走 reducer：消息列表只剩最后一条。
   - 去掉 `put` 里的 deepcopy，或者只做浅拷贝：Notebook 节点每步交回同一个还在变的列表，历史里每一步都变成最后的样子。
   - `load_state` 不拷贝就交出去：调用方改返回值，检查点跟着变。
   - 保留整个 state 的快照、只把拷贝换成浅拷贝或 pickle：浅拷贝过得了计时，过不了“记录里只放这一步写的”；pickle 约 1 秒，过不了计时。
   - 把暂停标记留在检查点、读的时候再删：只在 `_state_at` 里删的话，历史里那一步的 state 带着标记；`history` 里也删的话，state 都对了，可 t1 第 3 步的记录里还留着标记，测试最后直接比这条记录。
   - 恢复时跟着节点的第一条边走（课里 `main()` 写死 `resume_from="send"`）：没批准也发出去了。
   - 先算下一个节点、再应用人的修改；或者修改只合并进内存、不写成 HUMAN 步：恢复起点或历史不对，崩溃以后修改也丢了。
   - 恢复位置取最后一条记录，把 HUMAN 也当成节点：`no edge out of '__human__'`。
   - router 的结果按节点缓存起来：第二个会话沿用第一个会话的路由。

看什么：是不是先读 traceback，注意到 PausedAtNode 是 `resume` 抛的，不是 `run`；有没有打印恢复时的起始 state；看到 deepcopy 慢时，是直接去掉拷贝（会被 Notebook 护栏抓住），还是回去读 `Record` 的 docstring，改成只存这一步写的东西。

提示：
- 暂停层：H1 "The human approved. Which part of the state still says pause?" H2 "Print the state resume starts from." H3 直接指出 `_loop` 里写检查点和 pop 的先后。
- 恢复起点层：H1 "Which steps ran twice?" H2 "What does the lesson say resume does after a failure at step N?"
- router 层：H1 "How many times does the router run for one step?" H2 "What does _loop do when next_node returns None?"
- 计时层：H1 "What does each record hold, compared with what the step changed?" H2 "Read the Record docstring." H3 "If a record only holds the update, how do you get the whole state back?"

追问：
- "The send node charges a card and crashes before it returns. What happens on resume?"（重跑会再扣一次。检查点存的是 state，撤不回外部世界已经发生的事；要靠幂等键、先记录后执行，或者 Part 3 那样的录制）
- "load_state now folds every step. What about a session with a million steps?"（定期写一个完整快照，读的时候从最近的快照开始折叠后面的增量，也就是快照加日志的压缩）
- "Why must put copy at all, if nodes are supposed to be pure?"（节点会交回自己还在改的对象，比如 Notebook。真正的 checkpointer 序列化时值就固定了，内存替身必须和它一致）
- "Why does calling the router once matter when the router is an LLM?"（成本；两次调用可能答案不同，走到谁都没选的分支。更好的做法是课里 classify 那样：LLM 调用放在节点里，结果写进 state，router 只读 state）
- "Resume chooses the next node with the patched state. What does that let a human do?"（课里练习 1：人手动设置 route 以后恢复，图按新的 route 走）

### Part 2 SQLite 检查点（目标 12 分钟）

坑：
- JSON 会悄悄改类型：tuple 变成 list；用 int 或 tuple 做键的 dict 变成字符串键，7 和 "7" 还会撞成一个；set、frozenset、bytes 直接报 TypeError。每种容器都要带上类型标签。
- 标签要和数据分得开。普通 dict 原样写成 JSON 对象、只按“只有一个键、键名像标签”来认标签的话，用户自己写的 `{"tuple": [1]}` 读回来就变成了 tuple。参考实现把 dict 也写成 `{"dict": [[k, v], ...]}`，这样编码里的每个 JSON 对象都是标签。测试还把每个值编码出来的 JSON 当成普通数据，再 dumps、loads 一遍，所以换成 `{"__type__": "tuple", "items": [...]}`、`{"py/tuple": [...]}` 这类测试里没列出的标签形状，也一样过不去。
- set 不能为了编码稳定先排序：里面混着 str、int 和 tuple，`sorted` 直接报 TypeError。
- 读回时元素要先还原再放进 set：set 里的 tuple、dict 的 tuple 键必须是可哈希的 tuple。
- True 和 1、1 和 1.0、-0.0 和 0.0 要分得开（测试的 `exact()` 会查），2**64+1 要原样回来。按 SQLite 原生类型存标量的写法会在这里出错：True 读回来是 1，大整数存不进 INTEGER。把大整数写成字符串“照顾 JS 读者”也会被抓住。
- 存不了的值（datetime）在 dumps 和 put 时都要报 TypeError。课里 `main()` 打印时用的 `default=str` 会把它悄悄变成字符串。pickle 能原样往返，但写出来的不是 JSON，也不会报错。
- 写 None 也是一次写入：retry 把 error 改回 None。值为 None 就不存的话，重开后 error 还是 timeout。
- 没写任何通道的一步（暂停的 gate）也是检查点。只用一张 (session, step, node, channel, value) 表、一个通道一行的话，这一步一行都没有，记录就丢了。参考实现另有一张 steps 表，录下的 calls 也放在那里。
- 一次 put 要么全部写进去，要么什么都不留：先把所有值编码好，再在一个事务里插入。边编码边逐行提交的话，datetime 那一行失败时前面的行已经留下了。
- 同一步写第二次要报 ValueError。只靠 (session, step, channel) 主键时，换了通道的重复写入不会冲突；只靠 steps 表主键时，报出来的是 IntegrityError。
- 录下的 calls 也要存，里面全是 tuple。

追问：
- "Why not pickle?"（读检查点就能执行任意代码；只有 Python 读得了；类改个名，旧检查点就读不出来）
- "Next month a node writes a new type. What happens to old checkpoints?"（编码要带版本；遇到不认识的标签要报错，不能猜）
- "Postgres instead of SQLite?"（同样一个通道一行，值用 JSONB；一步一个事务；按 session 查询要有索引）
- "Two workers resume the same session at once?"（谁先写下这一步谁赢，另一个的 put 被拒。生产上要把检查和插入放在同一个事务里，或者交给唯一约束）

### Part 3 录制与重放（目标 12 分钟）

坑：
- 录制时要存结果的深拷贝：quote 节点直接改 API 返回的 dict（减掉折扣，再往 lines 里追加一行）。存引用的话，录下来的是改过的值；浅拷贝也不够，嵌套的 lines 还是同一个列表。
- 重放时也要交出拷贝。把录下的对象直接交给节点，第一次重放能过，可录制本身已经被节点改掉，第二次重放就对不上。测试连着重放两次。
- 每次调用都要和录制核对 op 和参数。只看 op 的话，退款金额从 45 改成 50 也发现不了；什么都不核对的话，顺序一换就把时间戳当成随机数用了。只核对参数、不核对 op 的写法过得了测试：random 和 now 的参数都是空元组，两个调换顺序时参数核对发现不了，要等比较 update 才露出来。看到这种写法要指出来。
- 超出录制的调用要报 ReplayMismatch，不能退回去调真接口（pay_and_notify）。没用完的录制也要报（quote_without_clock 写出的 update 和原来一模一样，只有 `finish()` 能发现）。
- 只核对调用还不够：节点背着 ctx 读了墙上时钟（pay_wall_clock），或者代码改了但调用没变（quote_double_discount，少写了 paid_at 的 pay_unstamped），只有比较 update 才发现得了。update 要整个比较，只比节点这次写了的那几个通道，pay_unstamped 就漏过去了。
- 比较 update 前要去掉暂停标记，review 那一步的检查点里没有 `_pause_reason`。
- HUMAN 步要照记录应用。跳过的话，pay 收到的 note 是 None，参数和录制对不上。
- 节点拿到的是这一步之前的 state。先把这一步写的东西合并进去再重跑节点的话，review 看到自己已经写过的 asked_at，就不再读时钟，`finish()` 报录制没用完。
- 崩溃那次尝试不留录制：只有写进检查点的调用才算数，重跑的节点重新抽一次随机数。starter 的 `_loop` 每次执行都新建 NodeContext，这一点本来就是对的，测试只是确认它没被改坏。
- 重放不写检查点，也不碰 World 的 RNG、时钟和 API。
- ReplayMismatch 的消息里要有 `step <n>`，测试按它定位是哪一步。

追问：
- "Suppose every call were journaled the moment it returns, before its step is checkpointed. What does that buy, and what does it cost?"（崩溃后重跑不会重复扣款；可如果正是那次调用的结果让节点崩溃，重放会一直崩。代码一改，旧日志就可能重放不了，需要版本化）
- "How would you use replay in CI?"（拿线上录下来的 session 对着新代码重放，quote_double_discount 就是这种回归检查）
- "An LLM call inside a node?"（它就是一次外部 API 调用，经过 ctx 录下来；温度、模型版本都会让重新调用的结果不同）
- "Replay could also check the path the graph takes. How?"（每个节点步之后用 next_node 算出下一个节点，和下一条节点记录比较。这套题没有要求）

### Part 4 节点增量 SSE（目标 10 分钟）

坑：
- data 里只放这一步写了什么，也就是检查点里的 writes，不放整个 state。暂停标记不能出现在 data 里，原因放在 interrupt 事件里。
- 写下的每个检查点都要发，START（输入）和 HUMAN（人的修改）也发，客户端按顺序应用就能拼出完整 state。
- id 是步号，不是这条流自己的序号：恢复以后第一条是 3，不是 0；不发 HUMAN 的话第一条成了 4，也不对。
- interrupt 之后流就结束。用 break 跳出循环会多发一个 end。
- 一步写完检查点以后才能发它的事件，START 和 HUMAN 也一样。先 yield 后提交的话，客户端收到第 1 步就断开时，第 1 步根本没写进去。测试每收到一个带 id 的事件，就去 checkpointer 里查这一步在不在，最后再用 `aclose()` 在第 1 步之后断开一次。
- 一步完成就发，不能攒到最后。测试按日志里节点执行和收到事件的交错顺序来判断。
- 节点可能是协程函数，要 await；也可能是普通函数，不能一律 await。
- 节点抛异常时，前面的事件已经发出，异常照常往外抛，检查点和 run 一样。
- 骨架是只有 raise 的 `async def`，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要看出这里需要 async generator。

追问：
- "The browser reconnects with Last-Event-ID: 2. What do you send?"（从第 3 步开始补发。检查点就是事件日志，id 用步号正是为了这个）
- "The UI reads slower than the graph runs?"（async generator 只在被拉取时往前走，图会等客户端。不想让图等，就在中间放一个有界队列，满了丢弃或断开）
- "Why not send the whole state every time?"（大，而且大部分没变。只发增量时客户端要知道 reducer：messages 是追加，不是覆盖）
- "Exercise 5 in the lesson streams partial state while a node runs. Where does that fit?"（节点自己也做成生成器，事件再多一种 partial；检查点仍然只在节点结束时写）

### Part 5 嵌套子图（目标 12 分钟）

坑：
- 命名空间是父命名空间加上 `|节点:步号`，三层就是 `s1|review:2|legal:2`。只用 session 拼，或者不带步号，暂停位置就对不上。
- 子图里暂停时，父图不能给这个节点写检查点，否则恢复时直接去了父图的下一个节点，子图剩下的步骤没跑。
- 暂停原样往外抛。每一层重新包一个 PausedAtNode，就丢了真正暂停的节点和命名空间。
- 人的修改要交给真正暂停的那一层。先在父图写 HUMAN、再去找子图的话，步号多了一格，找不到原来的子图，只好重开一个从头跑；测试里看到的是 legal 命名空间里没有 HUMAN 记录。
- 恢复时回到子图内部的下一个节点，不能从子图入口重来：draft 会再跑一遍，checkpointer 还会因为这个命名空间的第 0 步已经写过而报 ValueError。
- 子图交给父图的是它各步写了什么：START 之后的节点步和 HUMAN 步，按子图的 reducer 折叠。交出整个最终 state，或者把 START 也算进去，messages 会重复。
- 父图和子图里都有叫 send 的节点，节点要在当前这一层图里找。
- 同一个子图节点在循环里跑多次，每次一个命名空间（步号不同）。不带步号时，第二次会找到第一次的检查点，当成已经跑完。
- 子图恢复时用它自己的检查点折叠出来的 state，不是父图的 state（父图里没有 draft）。
- 这几个图各层的 reducer 都是同一个追加。交给父图的 update 用 `self.graph` 的 reducer 折叠，或者拿子图最终 state 减去父图 state（列表只取多出来的尾巴），在这里结果都一样，测试分不出来。看代码时留意，可以追问各层 reducer 不同时会怎样。

追问：
- "The lesson's skill file wants nested subgraphs beyond about 30 nodes. Why?"（平铺的 30 个节点没法审；子图可以单独测试、单独恢复）
- "Why does the parent get the writes and not the subgraph's final state?"（子图从父图的 state 出发，最终 state 里本来就有父图的内容，用追加 reducer 再合并一遍就重复了）
- "Two subgraphs running in parallel?"（各用各的命名空间；合并顺序要确定，比如按节点名；reducer 要么可交换，要么规定顺序）
- "Supervisor versus hierarchical, as the lesson lists them?"（supervisor 是一个中心路由分派给专家；hierarchical 是 supervisor 管 sub-supervisor，用的就是这种嵌套子图）
- "Part 3's replay calls every node again, but a subgraph node is not a function. How would you replay a session with subgraphs?"（对子图节点那一步，递归重放它自己的命名空间，再把折叠出的 update 和父图这一步的 writes 比较）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出副作用与幂等、快照压缩、序列化格式、断线重连、子图隔离 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
