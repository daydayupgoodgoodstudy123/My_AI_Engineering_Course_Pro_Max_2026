# 面试官手册：Harness（14/17）

候选人计时期间不要看。候选人手里只有 README、`harness/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 告诉候选人：工具调用由测试写好，Part 4 的 subagent 是测试里的 `Probe`，不联网，也不要去改测试里的替身。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 钩子返回的既不是 None 也不是 Deny 呢？ | "Treat it as allow. Only a Deny blocks a call." |
| 1 | 被拒绝的调用要写进会话吗？ | "Yes, as a tool turn like any other result. The model has to see that it was denied." |
| 1 | 未知工具也要过 PostToolUse 吗？ | "Yes. Every result goes through every PostToolUse hook." |
| 1 | context_tokens 是这一次 run 的，还是整个会话的？ | "The whole session, earlier runs included. It's what the model would read next." |
| 2 | session id 里会有 "/" 吗？ | "Any string. Some callers nest subagent ids with slashes." |
| 2 | delete 的时候能重写父会话的镜像文件吗？ | "No. Mirror files are append-only, people tail them. Removing a deleted session's own file is fine." |
| 2 | 只 link 过、还没写 turn 的子会话也要有镜像文件吗？ | "Yes. Every session has its own file, even an empty one." |
| 2 | 要支持几个进程同时写吗？ | "Not today. Tell me what would break." |
| 2 | id 很长、超过文件名长度上限怎么办？ | "The tests don't cover it. Tell me what you would do." |
| 3 | 最后一批不满 k 个怎么办？ | "It runs as a smaller batch. Every task gets done." |
| 3 | subagent 写的那份摘要，两边都要算吗？ | "Yes. It's in the subagent's context when it writes it, and in the orchestrator's when it reads it." |
| 3 | 能不能重新排任务，把小的凑成一批？ | "No. Batches are consecutive, in the order given." |
| 3 | 不用 subagent 的方案要看 window 吗？ | "No. There's no subagent, only the orchestrator and its cap." |
| 4 | 照练习那样 5 个一组跑吗？ | "At most five at a time, but don't wait for the whole group. Start the next task as soon as a slot frees up." |
| 4 | 事件按任务顺序发吗？ | "No. In the order the subagents finish." |
| 4 | 出错的那条要写进 orchestrator 的会话吗？ | "Yes. The error line goes in like a result, so the orchestrator knows." |
| 4 | 客户端中途断开呢？ | "Cancel what is running and start nothing new." |
| 5 | 没有任何轮次的会话算不算空闲？ | "Yes, it's idle." |
| 5 | 最新一轮恰好在 ttl_s 秒前，算不算空闲？ | "No. Idle means more than ttl_s ago." |
| 5 | 同一个子会话挂在两个父会话下？ | "Malformed. Raise ValueError and delete nothing." |
| 5 | 返回的 id 什么顺序？ | "Sorted." |
| 5 | 树会有多深？ | "As deep as agents nest. Thousands of levels happen." |

## 每关：要看什么、提示、追问

### Part 1 修 harness（目标 12 分钟）

一个测试里叠了 4 个缺陷和几个护栏：

1. `_dispatch` 调了 PreToolUse 钩子，却不看返回值。`stay_in_work` 返回的 Deny 被丢掉，`/etc/hosts` 照样被写。docstring 写的是：Deny 时工具不运行，后面的 PreToolUse 钩子不再运行，结果是 `denied: <reason>`。
2. 工具抛异常的分支直接 `return`，跳过了 PostToolUse。课里说 PostToolUse 用来 audit tool calls，审计日志里少了一条 FileNotFoundError。
3. `spawn_subagents` 把子 agent 的整段转录（`store.load(sub_session)`，一个 `list[Turn]`）当成一条 turn 交回父会话。错误不在这里报，而是两层调用之后，在 `count_tokens` 里报 `AttributeError: 'list' object has no attribute 'split'`。课里说 only results return to the orchestrator，应该交回 `run.output`。
4. `_record` 每追加一条 turn 就 `load()` 整个会话重新数一遍 token，是 O(n²)。5000 次工具调用在本机测试里要 1.4 到 2.2 秒，限值 0.12 秒；改成增量计数后是 6.5 到 8.2 毫秒。

护栏：
- 被拒绝的调用也要进 PostToolUse。修第 1 处时在 Deny 分支直接 `return`，会被 “post_tool_use audits denied calls too” 抓住。
- 拿到 Deny 以后不 `break`、只记下来继续跑剩下的钩子，会被 “PreToolUse hooks after a Deny do not run” 抓住。
- 修第 3 处时把转录 `"\n".join` 成字符串，报错没了，但 orchestrator 的上下文从 26 变成 89，会被 “only subagent results return to the orchestrator” 抓住。
- 修第 4 处时从 0 开始累加，会话第二次 run 的 context_tokens 只剩这一次的 8 个，正确值是 34。要在 run 开始时把已有会话数一次，再增量累加。起点用会话已有的轮数也不对，测试里得到的是 14。

测试抓不到的：用 `if decision:` 代替 `isinstance(decision, Deny)` 也能通过，因为测试里的钩子只返回 None 或 Deny。按澄清问题的答案，别的返回值都算放行，可以顺口问一句。

看什么：是不是先读 traceback，顺着 `count_tokens` 往上找到传进来的是什么；是不是先 `print(repr(...))` 看实际数据；每改一处就重跑。

提示：
- H1："What type reaches count_tokens, and who put it there?"
- H2："What does a PreToolUse hook give back, and who reads it?"
- H3：直接指出 `_record` 每次都调用 `_context_tokens`。

追问：
- "The lesson's hook signature has no session id. What breaks without it?"（按会话审计、按会话限流都做不了，审计记录分不清是哪个会话的调用）
- "Hook creep: every team adds a hook. How do you keep dispatch fast?"（按工具名分组注册、给钩子计时、定期清理）

### Part 2 会话镜像（目标 14 分钟）

坑：
- `delete` 要递归级联。课里的代码只删一层，测试里被删的 `lead/sub01` 下面还有两层。
- 镜像文件只能追加，删除也一样。测试在删除前后读父会话 `lead` 的镜像，删除后的内容必须以删除前的内容开头。把 link 那一行从父会话文件里去掉、整份写回，会被 “mirror files are only ever appended to” 抓住。要在父会话的镜像里追加一条 `{"removed": ...}`，回放时处理，这样重开以后被删的子会话也不会回到 subkeys 里。
- link 也算会话存在。`lead/sub02` 只 link 过、一轮都没写：同一个 store 的 `list_sessions` 里要有它，它也要有自己的镜像文件，重开以后还在。link 时只给父会话写一行、不登记子会话，会被 “a session exists once it has a turn or takes part in a link” 抓住。
- 每次 append 返回时，这一行必须已经在文件里，课里的 `--session-mirror` 就是边产生边写。一直开着文件句柄又不 flush，测试中途读到的是空文件。
- 时间戳要原样读回。测试用了 1767225600 + i/3 和 0.1 + 0.2，`round(ts, 6)` 或者按固定位数格式化都会挂。json 写 float 用的是能原样读回的最短表示，本身没问题。
- 顺带覆盖的边界：
  - 镜像是给人看的，docstring 要求非 ASCII 原样写出（`ensure_ascii=False`），文件里就会有原样的 U+2028 和 U+0085。读回时用 `str.splitlines()` 会在它们中间断开，报 `Unterminated string`。按 `"\n"` 切，或者直接逐行迭代文件对象，都没问题。
  - 文件名要可逆、不冲突、不出 root。`replace("/", "_")` 让 `lead/sub01` 和 `lead_sub01` 撞名；`urllib.parse.quote` 保留大小写，`Lead` 和 `lead` 在 macOS 默认的大小写不敏感文件系统上是同一个文件（测试按小写比较文件名，在任何文件系统上都会抓住）；原样拼接的话，`lead/sub01` 指向不存在的子目录，报 FileNotFoundError，`../escape` 会写到 root 外面；标准 base64 会编出 `/`（`naïve / id?` 就会），写的时候报 FileNotFoundError。UTF-8 字节转十六进制是最省事的办法。

测试抓不到、可以接受的：
- urlsafe base64 作文件名能通过。但它区分大小写，两个不同的 id 可能编成只差大小写的文件名，在大小写不敏感的文件系统上撞名，可以追问。
- 保持 `ensure_ascii=False`，再自己把 U+2028、U+0085 转义掉，读的时候用 `splitlines()`，也能通过。追问 U+2029：json 同样不转义它，`splitlines()` 也会在它那里断行。

追问：
- "Two processes append to the same mirror at once?"（各自用追加模式写，本地文件系统上一次小的 write 通常不会交错，但缓冲可能把一行拆成几次 write，网络文件系统也不保证；要么加文件锁，要么只留一个写者；两个进程的内存索引也会不一致）
- "A 300-character session id?"（十六进制会超过 255 字节的文件名上限；改用 hash 作文件名，原 id 写在文件第一行）
- "Session bloat: the mirror directory has a million files."（按日期分目录、过期清理，也就是 Part 5）

### Part 3 分批规划（目标 10 分钟）

主数据就是测验 Q12：orchestrator 自身提示 50，每个模块读 2,000，摘要是 50 加每个任务 50（一个任务 100，五个一批 300），每个 subagent 的固定开销 3,000，brief 50。不用 subagent 是 40,050 / 40,050，每任务一个是 2,050 / 105,050，五个一批是 1,250 / 54,650（orchestrator 上下文 / 总 token），和 Q12 的答案一样。

坑：
- 上下文隔离：subagent 读进来的内容留在它自己的上下文里，orchestrator 只多出交回的摘要。把读入也算进 orchestrator，每任务一个的 orchestrator 上下文是 42,050 而不是 2,050，被 “only the summaries return to the orchestrator” 抓住。
- 不用 subagent 时，20 个模块都由 orchestrator 自己读，上下文是 50 + 20 × 2,000 = 40,050。和 subagent 方案共用一套算法、批次为空时只剩提示 50，会被 “without subagents the orchestrator reads every task itself” 抓住；干脆漏掉这一行，会被 “one plan without subagents, then one per batch size” 抓住。
- 最后一批不满 k 个也要跑。按 `n // k` 切，k = 3 时只剩 6 批、18 个模块；写成 `n // k + 1`，整除时又多出一个空批。两种都被 “the last batch taking what is left” 抓住。
- 一批只交回一份合并摘要：50 + 50 × 批里的任务数。按每个任务各算一份 100，五个一批的 orchestrator 上下文是 2,050 而不是 1,250，被 “a subagent hands back one summary for its whole batch” 抓住。
- 选方案要同时看两个上限：orchestrator 不超过 cap，每个 subagent 不超过它自己的 window。只看 cap 的话，总 token 和 orchestrator 上下文都随 subagent 变少而下降，会选出一个 subagent 读全部 20 个模块（它自己的上下文是 44,100）。window 16,000 时最少要 4 个 subagent：k = 5 和 k = 6 一样多、一样贵，取小批 k = 5，就是练习 1 的 5 个一组。
- 能不能放下不随 k 单调。`UNEVEN` 里 k = 2 把 c、d 放进同一批（940），放不下；k = 3 把它们分开（745 和 640），反而放得下。从小到大试、第一次放不下就停的写法会选 k = 1，被 “a batch size that does not fit says nothing about larger ones” 抓住。
- 总数相同先取 subagent 少的。测试里有一组 brief、固定开销和摘要基数都是 0 的数据，所有 subagent 方案的总数都是 240，k = 1 和 k = 2 都放得下，要选 k = 2。
- 什么都放不下时报 ValueError。cap 只拿来查不用 subagent 的方案，cap = 1,000 时会返回 k = 5。
- 最后一段把计划交给 Part 1 的 harness：按计划的三批（3、3、1 个模块）调用 `spawn_subagents`，orchestrator 的上下文从 8 涨到 20，只多出三份 4 个词的摘要，每个 subagent 的上下文也和计划一一对应。这一段依赖 Part 1 修好的 `spawn_subagents`，没修的话报的是 Part 1 那个 AttributeError。
- 顺带覆盖的边界：总数要算上每个 subagent 的固定开销（漏掉的话每任务一个是 45,050）和它自己写的那份摘要（漏掉是 103,050）；cap 正好等于 40,050 时不用 subagent 的方案放得下，写成 `<` 会改选 k = 5；window 只拿批里的读入去比，会选出 k = 7。

测试抓不到、可以接受的：window 的比较写成 `<` 也能通过，测试里没有哪个 subagent 的上下文正好等于 window。可以顺口问一句正好等于时算不算放得下。

追问：
- "Batches run in parallel. What does the batch size do to wall time?"（每个 subagent 串行处理自己那一批，最慢的一批决定墙钟时间；subagent 一样多时，批越均匀越快，这也是并列时取小批的原因）
- "Prompt caching makes the overhead almost free. Does over-spawn still matter?"（总 token 的差距只剩 brief 和摘要，但会话数量、调度和 Part 5 的会话膨胀还在）
- "You only learn a module's size by reading it. How do you plan?"（按文件大小或上次的读入量估计，给 window 留余量；subagent 快满时先交回摘要，剩下的任务拆成新的一批）

### Part 4 并行子 agent（目标 14 分钟）

坑：
- 输出格式由测试的 `parse_sse` 决定：每个事件一行 `event:`、一行 `data:`，以空行结尾。少了空行会被 “every event ends with a blank line” 抓住；`json.dumps(indent=2)` 会让 data 变成多行，被 “one event: line and one data: line” 抓住。
- 同时最多 5 个，但一个完成就补一个。照练习字面写成“5 个一组 `gather`、组内按任务顺序发”，先被 “outcomes arrive in the order subagents finish” 抓住；改成组内边完成边发、整组完了才补下一组，慢的 sub01 会拖住整组，它就不是最后一个完成的。
- 完成一个就发一个，不能等全部完成。测试记下收到第一个事件时已经完成了几个。
- 一个 subagent 抛异常时发 `error` 事件，其他照常。`asyncio.gather` 不带 `return_exceptions` 会把异常抛出来。
- orchestrator 的 token 只算父会话里的结果，是 150。把所有会话加起来是 1370，因为每个子 agent 都在自己的会话里写了 61 个词。
- 消费方提前 `aclose()` 时，正在跑的要取消，并且要等它们真的结束：只 `cancel()` 不 await，aclose 返回时还有 4 个在跑。
- 用 `asyncio.wait(FIRST_COMPLETED)` 或者信号量加 `as_completed` 写，也都能通过。这组数据里每次 `asyncio.wait` 只返回一个完成的任务，集合没有顺序不影响结果。

测试抓不到、可以接受的：
- 一开始就把 20 个子会话全部 link 上。完整跑完时 subkeys 的顺序一样；提前关流时，没启动过的子会话也留在 subkeys 里，而 docstring 说的是启动前一刻才 link。可以顺着问会话膨胀，这些空会话要等 Part 5 的过期清理来删。
- 先 yield 结果、再补下一个任务。测试的消费方读得快，看不出差别；消费方读得慢时，空出来的位置要等它读完这一条才补上，正好接下面 “The consumer reads slower” 那个追问。

追问：
- "Subagent over-spawn: 100 tiny tasks?"（每个 subagent 都有启动和上下文的开销；把小任务合并成一批交给一个 subagent）
- "Why stream results instead of returning a list?"（orchestrator 可以边收边决策，慢任务不拖住快任务的结果）
- "The consumer reads slower than subagents finish. What grows?"（结果队列；需要有界队列或在消费慢时暂停启动新任务）

### Part 5 subagent 树（目标 10 分钟）

坑：
- 一个会话只有在它自己和下面所有层都空闲时才过期。`lead` 很旧，但孙会话 `lead/tests/unit` 还活着，所以 `lead` 和 `lead/tests` 都要保留。只看自己、或者只看直接子会话，都会把 `lead` 删掉，还会顺着级联删掉活着的孙会话。
- 空闲按最新一轮算，而且要超过 ttl_s。`other` 最早一轮在 100、最新一轮在 900，要留下，按第一轮算会把它删掉；`nightly` 的最新一轮恰好在 now − ttl_s，不算空闲，把空闲写成 `now - newest >= ttl_s` 会删掉它。
- 没有任何轮次的会话算空闲。`lead/docs/draft` 只 link 过，要跟着 `lead/docs` 一起过期。对它求 `max()` 会报 ValueError；把它当成活着的，又会把 `lead/docs` 留下。
- 空闲的子会话挂在活着的父会话下面时要删（`lead/docs`），父会话的 subkeys 里也随之消失。只删整棵都空闲的树，会把它留下。
- 渲染：子节点按 link 的顺序，不按名字排序；subtree 包含自己，`lead/docs/draft` 是 `turns=0 subtree=0`；根不存在时报 ValueError。
- 一个会话挂在两个父会话下、或者 link 成环时报 ValueError，而且什么都不删。先检查再删除。
- 顺带覆盖的边界：树有 1200 层。递归写法会撞上 Python 默认的递归上限，报 RecursionError。用显式栈。

测试抓不到、可以接受的：递归写法加上 `sys.setrecursionlimit` 也能通过。可以追问：它改的是整个进程的设置，树再深一些还是会出错。

追问：
- "What does deep nesting cost the orchestrator?"（每层只交回结果，所以 orchestrator 的上下文不随深度增长，但延迟和总 token 会）
- "Expire by age or by size?"（课里的 Session bloat 两者都提到；大小可以按 subtree 的轮数算，这一关的 subtree 统计就是它）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出并发、取消、文件名、subagent 的开销、会话膨胀 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
