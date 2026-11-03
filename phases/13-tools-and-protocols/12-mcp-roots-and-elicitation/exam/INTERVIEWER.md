# 面试官手册：scopegate（13/12）

候选人计时期间不要看。候选人手里只有 README、`scopegate/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 工作区本身算不算在工作区里？ | "Yes. The workspace itself and everything below it." |
| 1 | `%252e%252e` 要解码成 `..` 吗？ | "No. Decode exactly once. %25 is a literal percent sign, so that's a folder named %2e%2e." |
| 1 | 符号链接要不要处理？ | "Not here. This check is lexical. The OS sandbox is the third layer. Do say what you'd add." |
| 1 | 存储满了，能不能淘汰最旧的条目？ | "No. Refuse the new claim. Forgetting a live nonce lets its confirmation run twice." |
| 2 | nonce 能只放内存、笔记放 SQLite 吗？ | "No. Several processes share the file. The claim lives in the database, in the same transaction as the delete." |
| 2 | 两个重试同时到怎么办？ | "Exactly one deletes. The other gets 'requestState was already consumed'." |
| 2 | prune 要在 claim 里自动做吗？ | "Your call. prune() has to exist; the tests call it directly." |
| 2 | 过期时间怎么存？ | "As the float seconds you're given. Don't round them." |
| 2 | 能把 SQLite 的 busy timeout 调小吗？ | "Keep the default. Under contention a writer should wait, not fail." |
| 2 | 先查笔记还是先认领 nonce？ | "Claim first, then re-check the note in the same transaction. A used confirmation is refused whatever note it names." |
| 3 | content 里多出来的字段怎么办？ | "Ignore them. Only note_id and confirm matter. The tests don't cover it." |
| 3 | confirm 是 false，算不算拒绝？ | "No. It's not a confirmation: -32602, and the state stays usable." |
| 3 | enum 按什么顺序？ | "NoteBook order." |
| 3 | decline 以后要不要再问一次？ | "No. A decline is final: a complete result with deleted false, not an error." |
| 3 | 表单展示以后笔记被删了或被挪走了？ | "Refuse with the matching -32602 message. The state stays usable for another candidate." |
| 4 | accept 以后马上重试，还是等？ | "Wait for the next tick. The ticks are when the user says they're back." |
| 4 | 每次 input_required 都要重新问用户吗？ | "Not for the same URL. Ask once per URL." |
| 4 | ticks 用完了还没完成怎么办？ | "Stop. No complete line." |
| 4 | 服务端回了错误响应？ | "Raise McpError with its code, message and data." |
| 4 | 浏览器回调里的用户不是发起操作的人？ | "Return False and leave the flow pending." |
| 4 | 重试带哪一个 requestState？ | "The one from the latest input_required result, exactly as it came." |
| 5 | 同一个工作区上既有 read 又有 delete？ | "They add up to delete. Only deny overrides on the same workspace." |
| 5 | 父目录 deny，子目录 delete？ | "The child is more specific, so it wins below the child." |
| 5 | 不认识的 action？ | "ValueError." |
| 5 | bob 的授权会影响 alice 吗？ | "No. Grants are per principal." |

## 每关：要看什么、提示、追问

### Part 1 修范围和重放代码（目标 10 分钟）

一个测试里叠了 4 个缺陷和一组护栏：

1. `uri_within_workspace` 用 `startswith` 比较路径字符串。错误不在 scope.py 里报出来，而是在两层调用之外 `NoteBook.matching` 的候选列表里：`file:///work/notes-evil/q3-report.md` 也成了候选。
2. `file_uri_parts` 先 `normpath` 再 `unquote`。`%2e%2e` 在规范化之后才变成 `..`；`commonpath` 按分量比较但不解析 `..`，所以 `/work/notes/../private.md` 被当成在工作区里。
3. `supports_form_elicitation` 写的是 `elicitation.get("form", {})`。默认值让只声明了 url 的客户端也被当成支持 form。
4. `ReplayStore.claim_and_consume` 每次 claim 都用字典推导式重建整张表来清理过期 nonce。1 万个未过期的 nonce 是平方级，本机在负载下要 1.4 到 2.4 秒；用按过期时间排序的堆，只要几毫秒。
5. 护栏，重放存储的语义：满了要拒绝新的 claim，不能淘汰最旧的条目（`late` 被淘汰后就能再用一次）；按插入顺序从头清理不对，因为 `late` 先插入却晚过期；完全不清理的话，过期的 nonce 不腾位置；过期的判断是 `expires_at <= now`；操作失败的 claim 不能消费 nonce。
6. 护栏，包含性的过度修复：反复解码直到不变（`%252e%252e` 只能解码一次）；拒绝所有带 `%` 的路径（`q3%20plan.md` 是合法笔记）；拒绝所有 `..`（`drafts/../q4-plan.md` 仍在工作区里）；`startswith(ws + "/")`（工作区本身和根工作区 `file:///` 都会算错）；不再比较主机。
7. 护栏，form 能力的过度修复：去掉“空声明等于 form”的兼容规则；声明了 url 就不算 form；先判断“空”再判断类型，让没声明 elicitation 的客户端也通过。
8. 护栏，容量的边界：`>` 写成 `>=` 的反面（多放进一个）、先查容量再查重放（满的时候重放 `late` 得到的是 capacity 而不是 already consumed），都会挂。

可以接受、测试不区分的写法：只在存储满了的时候才用字典推导式清理一次（没满就不扫，计时能过，满了时每次 claim 仍是 O(n)，可以追问满载时的代价）；`not elicitation or "form" in elicitation`（和参考答案只差在 `{"form": null}` 这种畸形声明上）。

看什么：是不是先看多出来的那条候选的 URI，再顺着 `matching` 走进 scope.py；是不是先 `print(file_uri_parts(...))` 看规范化后的路径；动手提速之前，是不是先说清楚满了怎么办、按什么顺序清理。

提示：

- H1："Which note is in the list that shouldn't be? Where does matching decide that?"
- H2："Print file_uri_parts for the hostile URI. What does the path look like by the time you compare it?"
- H3：直接指出 `startswith`，以及 `normpath` 和 `unquote` 的先后顺序。

追问：

- "Why isn't this enough for a real filesystem?"（符号链接、硬链接、检查和使用之间的竞态、大小写不敏感的文件系统；要 realpath 或 O_NOFOLLOW 逐级打开，最后还要靠 OS 沙箱）
- "Why a heap, not insertion order?"（state 的签发时间各不相同，claim 的先后不是过期的先后）
- "What should a client do with -32023?"（这是本课代码自定义的错误码，讲义里没有定义；容量满时拒绝而不是放行，客户端稍后再试）
- "Why not just make max_entries huge?"（有界才能扛住大量 claim；满了就拒绝，重放保护不降级）

### Part 2 SQLite 重放库（目标 12 分钟）

坑：

- 先 SELECT 再 INSERT 是竞态。测试用第三个连接 `BEGIN IMMEDIATE` 占住写锁，两个重试都在查完、写之前排队；锁一放开，一个提交，另一个要么撞上主键报 IntegrityError，要么用了 `INSERT OR IGNORE`，两边都删了。要用条件写（`ON CONFLICT DO NOTHING` 加 rowcount，或捕获 IntegrityError），或者先 `BEGIN IMMEDIATE` 再查。
- `INSERT OR IGNORE` 不看 rowcount，或者 `INSERT OR REPLACE`：重放直接通过。nonce 只记在进程内存里：另一个进程看不到。
- claim 和删除在同一个事务里。删除前的检查失败时，claim 要一起回滚，这条确认还能用来删别的候选。写成两个 `with self._db:` 会提前提交；在 `claim_and_delete` 里调用自带 `with` 的 `claim()` 也会提前提交，因为 Python sqlite3 的连接上下文管理器嵌套时，内层一退出就 commit。
- 事务里要重查：笔记已经不在；笔记已经不在工作区里。重查用 Part 1 的 `uri_within_workspace`，SQL 的 `LIKE ws || '%'` 是字符串前缀，会把 notes-shared 当成在里面。
- 先 claim 再重查。先 SELECT 笔记、再 INSERT nonce 的写法，SELECT 发生在拿到写锁之前（Python sqlite3 默认只在第一条写语句前才 BEGIN），检查和删除之间别的进程可以改这条笔记。测试用“已用过的 nonce 指向已删除的笔记必须报 already consumed”抓这种顺序，报错是 "the nonce is claimed first, then the note is re-checked"。
- 用 `isolation_level=None`（自动提交）打开连接，`with self._db:` 就不再包住事务，claim 会先提交；用 `lastrowid` 代替 rowcount 判断条件写是否插入，同一个连接上一次插入留下的 rowid 会让重放通过。
- `expires_at <= now` 就是过期，decline 用的 `claim()` 也要查。过期的 state 什么都不写。
- 过期时间原样存、原样读回。存成整数秒，n-3 的 1000.5 就变成 1000，在 1000 这一刻被 prune 掉，可它的 state 还有半秒，同一条确认就能再用一次。存成 TEXT，读回来是字符串，比较也变成字符串比较。
- prune 只删 `expires_at <= now` 的行，返回删了几行。
- decline 也要提交，另一个进程马上就要看到。
- 不要把 busy timeout 调成 0：竞争时写者应该等，而不是报 database is locked。

追问：

- "Two machines instead of two processes?"（SQLite 只适合一台机器；换成数据库的唯一约束加事务，或 Redis 的 SET NX 带 TTL；关键是认领和变更在同一个原子边界里）
- "What if the deletion happens in another service?"（outbox 模式；或者先认领，再用幂等键调用外部服务）
- "Why keep a claim after the deletion?"（state 过期之前都要能拒绝重放；过期之后签名校验自己会拒绝，所以可以清掉）
- "A process-wide lock would also pass this test. Why is it still wrong?"（测试用线程模拟两个进程；真的两个进程各有各的锁）

### Part 3 破坏性删除表单（目标 15 分钟）

坑：

- 候选：标题包含 title（不分大小写）、在工作区里、grants 允许 principal 删，按 NoteBook 顺序。用 `NoteBook.matching` 再按 grants 过滤。Part 3 用的是扁平的 `WorkspaceList`，按笔记过滤的效果要到 Part 5 才看得出来。
- 表单是扁平的：note_id 是带 enum 的 string，confirm 是 boolean，两个都 required。
- 没有候选时，返回 `isError: true` 的 complete 结果，不是协议错误；工作区外的同名笔记不暴露。
- 服务端自己校验回复：缺 content、content 是 null、缺 confirm、confirm 是 "true"、1 或 false、note_id 不在签名的候选集合里、note_id 不是字符串、action 拼错或缺失，都是 -32602，而且都不消费 nonce。`confirm == True` 会放过 1，`if confirm:` 会放过 "true"；把 confirm false 当成 decline 也不对。
- 候选集合从验过签的 state 里取。重试时重新搜索，会让表单展示后才加进来的 note-15 也能被选；不验签直接解码 state，客户端就能往候选集合里加 note-99。
- 删除前在 replay claim 里面重查，按顺序：笔记还在；还在工作区里（note-7 被挪到 `%2e%2e/outbox`，要靠 Part 1 修好的解码）；principal 还能删。每一项失败都是对应的 -32602，nonce 不消费。顺序反过来，note-7 会报 not authorized 而不是 outside workspace；Part 5 里只重新授权工作区、不授权这条笔记，也会挂。
- cancel：complete，不是错误，deleted false，不消费，同一个 state 之后还能 accept。
- decline：消费 nonce，返回 complete、非错误的拒绝，不能再弹一次表单。
- 每次提示一个新的 nonce。拿参数摘要当 nonce 的话，同样参数的第二次提示一开始就是“已消费”。
- 先删除再 claim：claim 失败时笔记已经没了。

追问：

- "The user picked note-14, but a malicious client changed it to note-3. Can the server tell?"（不能；签名的候选集合只保证选中的是用户看过的；风险更高的操作要加二次认证或带外确认）
- "Why does decline consume the nonce but cancel doesn't?"（decline 是用户明确的决定，是终局；cancel 是没做决定，允许稍后再答）
- "What would you log?"（principal、目标、nonce、结果；不记表单里的内容）
- "Why not collect a password with this form?"（会经过 MCP 客户端，可能进日志和模型上下文；要用 URL 模式）

### Part 4 URL 模式带外流程（目标 12 分钟）

坑：

- 输出格式由测试决定：每个动作一行 JSON，以 `\n` 结尾。缺换行报 "every line ends with a newline"，多一个空行报 Expecting value。
- 先问再开：consent 被调用时什么都还没打开；decline 和 cancel 都不打开；同一个 URL 只问一次、只开一次；交给 consent 的是完整 URL，不能去掉 query。
- accept 只代表“同意打开”。每来一个 tick 重试一次；外部流程完成前服务端一直回 input_required；收到 complete 就输出 complete 并停下，不再拉 tick。不等 tick 就重试，会一直重试下去（测试的 send 在第 13 个请求时抛 RuntimeError）。
- decline 和 cancel：立刻重试一次，action 原样带上（cancel 不能改成 decline），输出 refused，停下，一个 tick 都不拉。
- ticks 用完了就停。不处理的话，StopAsyncIteration 从 async generator 里冒出来，Python 会把它变成 RuntimeError。
- 每一行在动作发生时就输出。测试记下输出每一行时拉了几个 tick，必须是 [0, 0, 1, 2, 3, 3]；把所有行收齐了再 yield 会挂。
- 重试保留原来的 params（包括 `_meta`），id 依次加一，inputResponses 里只有 action，没有 content。requestState 用最近一次 input_required 里的，不是第一次的：测试里每个 tick 时钟前进 30 秒，服务端每次签出的 state 都不一样，回显旧的会报 "a retry echoes the requestState of the latest input_required result"。
- 可以接受：用“问过没有”的布尔标记代替“问过的 URL 集合”。本题的服务端同一个流程一直给同一个 URL，两种写法测试不区分；可以追问 URL 变了该怎么办（应该重新问）。`browser_callback` 里按大小写不敏感比较用户名也不会被测试抓住，但 principal 是认证系统给的标识，应该原样比较，可以追问。
- 服务端的错误响应要变成 McpError 抛出。
- `browser_callback`：只有发起流程的 principal 本人、而且流程还在 pending 时才完成，完成时把这个 principal 记为已连接；未知的流程返回 False，不能抛 KeyError；已完成或已 decline 的流程不能再完成。

追问：

- "Why must the server bind the browser user to the principal?"（不绑定的话，mallory 在自己的浏览器里完成 alice 的流程，alice 的 MCP 身份就连到了 mallory 的第三方账号）
- "Why not prefetch the URL to check it?"（预取会带着用户的 cookie 发出请求，可能触发副作用，也泄露了意图；讲义明确要求不预取）
- "How would the client learn the flow is done without polling?"（本课的设计是客户端重试、服务端查自己的状态；也可以等用户点“我完成了”再重试）
- "What if the URL isn't https?"（讲义说 URL 模式发的是安全的 web URL；客户端可以不展示，直接按 decline 或 cancel 处理，要说清楚选哪个、为什么）

### Part 5 嵌套工作区授权（目标 11 分钟）

坑：

- 按路径分量建树，主机是第一层。按字符串前缀匹配会把 notes-evil 当成 notes 下面的目录。
- 起决定作用的是：这个 principal 有授权的、最具体的那个工作区。只看最浅的一层（/work 的 read 管住一切），或者“路径上任何一个 deny 都赢”（archive/keep 的 delete 被 archive 的 deny 盖住），都不对。
- 只看“最深的、有任何授权的节点”而不管是谁的：q4 上只有 bob 的授权，alice 应该继续用 /work/notes 的 delete。授权也不能不分 principal 混在一起。
- 同一个工作区上：deny 胜过 read 和 delete；read 加 delete 是 delete。“后写的覆盖先写的”会让结果依赖顺序，测试按正序和倒序各建一棵树。
- delete 包含 read，read 不包含 delete；deny 连读也禁止。
- 没有任何授权就拒绝；不是 file URI、带 query 的目标也拒绝（返回 False，不能抛 ValueError）；不同主机是不同的树。
- 根工作区 `file:///` 上的授权也算：dave 在根上有 read。用 dirname 往上走、走到 `/` 就停的写法会漏掉根上的授权。
- 可以接受：不建树，用 (principal, host, path) 做键的字典，从目标路径用 dirname 一路往上找到第一条授权（包括 `/`）。结果和树一样，可以追问授权很多时两种结构的代价。
- 授权 URI 和目标 URI 用同一个 `file_uri_parts` 规范化：`%70rivate`、`./shared`、末尾斜杠、`%61rchive`、`archive%2F2019.md`、`%2e%2e`。自己写规范化又把解码放到最后，`%2e%2e/plan.md` 会挂。
- 非法的 permission、非法的授权 URI、不认识的 action，都报 ValueError，不能悄悄跳过。
- 最后接回服务端：表单只列 alice 能删的笔记；`file:///work` 上只有 read，不能删；表单展示后加了一条 deny，删除前的重查要拒绝（"selected note is not authorized"）。这一段挂了，根因在 Part 3 的 `offer` 和 `resume`。

追问：

- "In AWS IAM an explicit deny anywhere wins. Why not here?"（两种模型都常见；这里按“最具体的规则生效”，好处是能在 deny 的目录里开例外，代价是审计时要看整条路径）
- "How would you explain a decision to the user?"（返回起决定作用的工作区和权限，审计日志里也记一份）
- "Grants change while a form is open?"（删除前重新授权；这就是三层规则要在每次变更前重查的原因）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出符号链接与沙箱、多进程与多机器、重放窗口、审计 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
