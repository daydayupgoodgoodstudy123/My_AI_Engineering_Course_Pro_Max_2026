# 面试官手册：ResearchOps（13/23）

候选人计时期间不要看。候选人手里只有 README、`researchops/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | server/discover 也要声明 Tasks 扩展吗？ | "It may. Only tools/call and the tasks/* methods have to." |
| 1 | 等待可以比 pollIntervalMs 长一点吗，比如加抖动？ | "Not here. Wait the server's current pollIntervalMs, no more and no less. The test checks every wait." |
| 1 | 被拒绝的调用要进审计吗？ | "Yes. Every tools/call decision, allow or deny." |
| 1 | 被拒绝的调用返回什么？ | "The gateway's error dict, as the docstring says. It never reaches the server." |
| 2 | 作者列表怎么存？ | "Your call, as long as every list comes back exactly, including an empty one. Say what you chose." |
| 2 | 标题能顺手去掉首尾空格吗？ | "No. Store every field exactly as given." |
| 2 | 文件存在但是空的？ | "Treat it like a new catalog: write the header first. The tests don't cover it." |
| 2 | 同一个 id、内容也完全一样，还算重复吗？ | "Yes. One row per arXiv id. Raise a ValueError." |
| 2 | 要考虑多个进程同时写吗？ | "No. One writer." |
| 3 | server/discover 算一次 tool call 吗？ | "No. Only tools/call requests count." |
| 3 | 委托失败要重试吗？ | "No. A failed delegation just leaves that paper missing." |
| 3 | 重试之后还是 isError？ | "The job ends failed. Don't go on to generate_report." |
| 3 | 放弃轮询时要发 tasks/cancel 吗？ | "You may. The server accepts it. The tests don't check it." |
| 3 | 刚好过了 ttlMs 算过期吗？ | "Yes. Once ttlMs have passed, stop." |
| 3 | ttlMs 是 null 呢？ | "No limit from the server; only your wait budget applies. The tests don't cover it." |
| 3 | 能不能先算预算够不够，不够就连委托都不做？ | "Your call. Say what you chose. The tests check what gets sent to the server." |
| 4 | 可以一行一行 yield，不按节吗？ | "Yes. The test reads the text, and when each heading went out." |
| 4 | 来了一条不在论文列表里的摘要？ | "That's a bug upstream. Raise a ValueError. The tests don't cover it." |
| 4 | 同一篇论文来了两条摘要？ | "Keep the first one. The tests don't cover it." |
| 4 | 空字符串的摘要算 missing 吗？ | "No, it arrived. Only None, or nothing at all, is missing." |
| 4 | # 前面是制表符呢？ | "Only spaces count, as the docstring says." |
| 5 | evidence 里有表里没要求的项，比如 unit tests？ | "Ignore it. It counts toward nothing." |
| 5 | telemetry 也带了 evidence 列表？ | "Ignore the list. Telemetry is judged only from what the collector received." |
| 5 | run 里没出现的边界？ | "Not exercised. Treat it like a simulated one." |
| 5 | 一个声明什么都不依赖？ | "Then it lacks nothing. The tests don't cover it." |

## 每关：要看什么、提示、追问

### Part 1 修一次研究流程（目标 10 分钟）

一个测试里叠了 4 个缺陷和几个护栏：

1. `Agent.request` 只给 `tasks/*` 方法声明 Tasks 扩展（`tasks = method.startswith("tasks/")`），`generate_report` 的 `tools/call` 因此被服务器回 `-32021`。错误不在 `request` 报出来：`call_tool` 把响应交给 `_settle`，是 `_settle` 里的 `unwrap` 抛出 `ProtocolError: -32021 Missing required client capability`。`_settle` 正是轮询 `tasks/get` 的地方，候选人很容易去查 `tasks/get` 的 `_meta`，那里其实声明了扩展。这个错误是 `tools/call` 的响应，`_settle` 还一次都没轮询。本课原话：客户端必须在可能收到任务句柄的同一个请求里声明扩展。
2. `call_tool` 把 `parent`（调用方的根 span）传给 `_settle`，20 个 `tasks/get` span 全挂在 `agent.invoke_agent` 下面。docstring 和本课的 Target trace（`tools/call: generate_report --> tasks/get polling`）都要求挂在 `tools/call generate_report` 下面。所有 span 共享同一个 trace id，只查 trace id 发现不了。
3. 网关用 `granted = required & grant.scopes` 判断，有任一 scope 就放行。只有 `research:read` 的 bob 也能调要 `research:read` 和 `research:write` 两个 scope 的 `generate_report`。测试直接调网关，还用只有写权限的 carol 堵住“只查 write”的改法。
4. `_settle` 里直接 `time.sleep(pollIntervalMs / 1000)`，不走注入的 `self.sleep`。20 次轮询（40、80、40 ms）要 1.2 秒左右，限值 0.1 秒。在 async 函数里调 `time.sleep` 还会卡住整个事件循环。

护栏：
- 把等待整个删掉、一直用句柄上的间隔、把毫秒直接传给 sleep、先轮询后等待、等待只增不减，都挂在 "wait the server's current pollIntervalMs before each tasks/get"。服务器给的间隔是 40 → 80 → 40 ms，减回去的那一段专门抓“只增不减”。
- 改成 `asyncio.sleep` 或 `asyncio.to_thread(time.sleep, ...)` 仍然花真实时间，挂在计时断言上。`self.sleep(...)` 忘了 await，协程根本没跑，等待记录是空的。
- 只给 `generate_report` 声明扩展（按工具名特判）：挂在 "every one declares the Tasks extension"。哪个调用变成任务由服务器决定，客户端事先不知道。
- 把服务器的 `require_tasks` 删掉让错误消失：测试直接问服务器，没声明扩展的 `generate_report` 必须还是 `-32021`，`data.requiredCapabilities` 照课里的形状。
- 照本课 `code/main.py` 只轮询一次：任务还在 working，抛 `TaskFailed`。
- 被拒绝的调用不能转发给服务器，也必须进审计。

看什么：是不是先读 traceback 和错误里的 `requiredCapabilities`；是不是想清楚了 `-32021` 回答的是哪个请求；修 trace 时是不是对照 docstring 和 Target trace，而不是凑测试；能不能讲清楚 `time.sleep` 在 async 代码里的问题。

提示：
- H1："Which request did that -32021 answer?"
- H2："Print the _meta of every request the server got. Which ones declare the extension?"
- H3：直接指出 `Agent.request` 里 `tasks` 的计算式。

追问：
- "Why declare the extension on every request, instead of once at discovery?"（无状态：没有会话，每个请求都可能落到另一个实例，服务器只看这个请求自己的 `_meta`）
- "All spans share one trace id. Why isn't that enough?"（本课原话：共享 trace id 证明不了父子关系、导出和后端接收；要在接收端断言 parentage，这正是 Part 5）
- "The task id is tsk_0001. What's wrong with that in production?"（可以猜；任务 id 不是授权凭据，`tasks/get` 也要过网关并校验归属）
- "Bob's refused call leaves no span. Should it?"（应该有一个错误状态的 span，和审计记录用同一个 trace id 关联；只看 trace 会以为他从没调过）

### Part 2 论文目录（目标 10 分钟）

坑：
- 读文件时没写 `newline=""`：通用换行模式把标题里的 `\r\n` 和单独的 `\r` 都变成 `\n`。写的时候漏掉，在 macOS 和 Linux 上看不出来，在 Windows 上每行会多一个 `\r`。
- 作者列表要可逆：`", "` 拼接拆不开 "Lu, Aaron"，`"; "` 拆不开 "Smith; J."，任何分隔符都要单独处理空列表（`"".split("|")` 是 `[""]`）。JSON 数组最省事。读回来要是 tuple，list 和 tuple 不相等。
- arXiv id 是文本：`2401.01230` 转成 float 再转回来是 `2401.0123`，`0912.0410` 是 `912.041`。对每个格子都试一下 `json.loads`，或者按内容猜类型，都会出这个错。
- 年份读回要是 int。用 `QUOTE_NONNUMERIC` 读回来是 2024.0，dataclass 比较时 `2024.0 == 2024` 成立，只有测试里的类型断言能抓住。
- 追加时只在新文件里写表头。每次 add 都写，读回时多出来的表头会被当成一篇论文解析；读的时候跳过重复表头也不行，测试会直接用 csv.reader 数行。
- 重复 id 要查文件里已有的，不能只查这个对象自己加过的；也不能按整篇论文比较，标题不同、id 相同也是重复。
- 标题原样保存，不能 strip。读的时候加 `skipinitialspace=True` 也是在 strip：测试里 `"  Padded on purpose  "` 没有逗号，csv 写出时不加引号，前导空格会被吃掉。
- 为了防 Excel 把 id 写成 `="2401.01230"` 也不行：测试用 csv.reader 读文件，id 和年份两格必须是原文。

追问：
- "Someone opens this file in Excel and saves it. What breaks?"（id 变成数字，尾零和前导零丢失；编码和分隔符随区域设置变化。fixture 要当只读制品，或者换成 JSON Lines）
- "Titles come from arXiv. What else in this file is untrusted?"（CSV 注入：以 `=`、`+`、`-`、`@` 开头的格子在表格软件里会被当成公式。这是本课 Rule of Two 里“不可信输入”的一种）
- "add re-reads the whole file to check for duplicates. Fine at 100k papers?"（每次 O(n)；在内存里维护 id 索引，或者换成带唯一约束的存储）
- "The handoff table says Search needs source provenance. What would you put in source?"（抓取时间、API 和版本、查询本身，能回答“这条记录从哪来”）

### Part 3 有上限的研究任务（目标 16 分钟）

坑：
- 重试也是一次 tools/call。预算 2 时，搜索失败一次再重试就用完了，`generate_report` 不能发出去；预算 1 时连重试都不能发。测试数的是服务器真正收到的 tools/call。
- 只重试一次：再失败就 `failed`，不能一直重试到预算用完。
- 委托要同时在飞（`asyncio.gather`），测试记录写手的最大并发。逐个 await 只有 1。
- 委托失败不能让整个任务失败：`gather` 不带 `return_exceptions`，或者用 TaskGroup，一个失败就整体抛出。带了 `return_exceptions=True` 却没把异常当成失败，异常对象会被当成摘要发给服务器。
- 超出 `budget.delegations` 的论文不委托，但要算 missing。missing 和 summaries 都按搜索顺序，不按完成顺序；`as_completed` 是按完成顺序的。
- 轮询时，每次等待之前先查 ttl，再查等待预算。ttl 从拿到句柄时算：写手花了 0.5 秒假时间，从任务开始算会提前过期。时钟是秒，ttlMs 是毫秒。
- 过期有两个场景，间隔都是 250 ms。ttlMs 600、等待预算 2000 ms 时轮询 3 次后过期，按下一次等待结束的时间查 ttl 会少一次。ttlMs 500、等待预算 600 ms 时，等了两次以后 ttl 刚好到，下一次等待也会超出预算，必须报 `expired`、polls 是 2。把 `>=` 写成 `>`（刚好到 ttl 不算过期），或者先查等待预算，都会变成 `over_budget`。
- 等待预算的意思是“不开始一次会超出预算的等待”：649 ms 只等一次，650 ms 等两次，700 ms 也是两次。改成“等完再查”或者把 `>` 写成 `>=`，都会差一次。
- 每次等的是服务器当前的 pollIntervalMs，不是句柄上的那个。
- 完成的任务快照自带 `result`，没有 `tasks/result`，服务器会回 `-32601`。

看什么：是不是先把预算、ttl、等待预算三种停止条件分清楚再写；有没有为 `gather` 的异常行为想一下；状态值是不是严格照 docstring。

提示：
- H1："Count the tools/call requests the server got in the second scenario. Which one shouldn't be there?"
- H2："What does asyncio.gather do when one awaitable raises?"
- H3：直接指出轮询循环里两个检查的顺序和比较符号。

追问：
- "The job gave up on its budget. Is the report task still running?"（是。超时不等于服务端取消；可以发 tasks/cancel，但取消是协作式的，回执不代表已经停下）
- "Why measure ttl from the handle instead of comparing createdAt with your own clock?"（客户端和服务器的时钟不一样；本地单调时钟只能量自己这边。ttlMs 也可能变，要用最新的那个）
- "A delegation hangs forever. What happens to this job?"（gather 一直等；每个委托要有超时，超时算 missing。本课 Delegation 一行要求 timeout 测试）
- "Which of these calls are safe to retry?"（search 只读，重试安全；generate_report 每次都建一个新任务，重试会建出两个，需要幂等键）

### Part 4 报告流（目标 12 分钟）

坑：
- 输出格式由测试的解析代码决定：按 CommonMark 的 ATX 标题规则切节（行首最多 3 个空格，然后 1 到 6 个 #，再接空格或行尾）。
- 摘要里以 # 开头的行要转义，包括前面有空格的 `  # indented`；只转义行首正好是 # 的，会漏掉这一行。把所有 # 都转义也不对，`C# and F#` 要原样保留。
- 标题里的换行（arXiv 的标题常带换行）要折成一个空格，否则标题跨行，后半截成了正文。只替换 `\n` 会留下一串空格。
- 检索结果一开始就完整，要在读第一条摘要之前发出去。
- 按论文顺序：前面的节没完成，后面的先缓存；前面的一完成，缓存里接得上的要一起放出来，不能一次只放一节。
- 失败的（text 为 None）和一直没来的都输出占位节，结论里两种都算 missing，按论文顺序列。测试里 2604 和 2606 先后失败，2605 一直没来；边收边记、最后再补没来的，会写成 `2604.01055, 2606.00007, 2605.00042`。
- 可以接受的写法：只转义 CommonMark 真会当成标题的行（`#hashtag` 不动），测试不区分；用 `re.sub(r"\s+", " ", title)` 折叠标题空白，测试里的标题没有首尾空白，也不区分。
- 测试记下每个标题发出去时已经拉了几条摘要，期望 `[0, 3, 3, 3, 4, 4, 4]`。先把所有摘要读完、晚一拍再放、一次只放一节，都会让这串数字变样。
- 写成普通的 async 函数（没有 yield）时，测试报 `'async for' requires an object with __aiter__`，要看出来这里需要 async generator。

追问：
- "The first paper is slow, so everything waits behind it. What would you show in a real UI?"（后面的节先显示占位，到了再替换；或者按完成顺序显示、带锚点。取舍是阅读顺序和首屏延迟）
- "The client disconnects halfway. What has the reader seen, and what keeps running?"（发出去的节都是完整的；aclose 时要取消还在跑的委托）
- "Why escape the # instead of deleting it?"（不改写手的文本，转义只影响渲染）

### Part 5 证据声明图（目标 12 分钟）

坑：
- telemetry 的两项证据只看 collector 收到的 span。共享一个 trace id 不够（本课原话），要同一个 trace id、只有一个根、每个非根 span 的父 span 也被收到。主运行里 d 的父 span x 没收到。
- 测试里还有两种坏树：同一个 trace 里多出一个根（传播时只带了 trace id，没带父 span），以及一个 span 换了 trace id。
- 模拟的边界没有任何证据，哪怕它报了 evidence；run 里没出现的边界也一样。本课原话：本地跑绿只验证模拟本身。telemetry 也一样：模拟的 collector 哪怕列了一棵完整的 span 树，两项证据也都缺。先判断 received、再看 mode，会漏掉这一条。
- 声明依赖声明，缺的证据要沿依赖传上来；同一个边界从两条路径到达只列一次；按 BOUNDARIES 的顺序排，不按依赖顺序，也不按字母。
- "every hop is traced" 被两条路径引用。用一个全局 visited 集合查环，会把它误判成环，要按当前路径查。
- 未知名字、run 里的未知边界、环，都要报 ValueError；不查环会 RecursionError。
- 声明按给定的顺序返回。

追问：
- "Exercise 1 asks you to separate what the output proves from what still needs integration evidence. Which of these claims can a local run ever prove?"（只能证明模拟本身的行为；表里每一行都要跨过真实边界的证据）
- "Two spans name each other as parent. Does the rule catch it?"（不会，两个父 span 都收到了；要从每个 span 往上走到根，或者检查无环）
- "A million spans at the collector?"（按 trace 分组，建 span_id 索引，一次遍历，O(n)）
- "Why ignore the evidence list for telemetry?"（证据要来自接收端的观察和独立测试的制品，不能是被测系统自己报的）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读断言消息和 traceback、打印实际数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出无状态请求、任务归属、取消与超时、幂等重试、证据从哪来 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
