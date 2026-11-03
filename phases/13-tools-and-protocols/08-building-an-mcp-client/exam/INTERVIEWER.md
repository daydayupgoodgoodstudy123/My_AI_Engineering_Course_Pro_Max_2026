# 面试官手册：multipeer（13/08）

候选人计时期间不要看。候选人手里只有 README、`multipeer/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | call 遇到没人提供的工具名要抛异常吗？ | "No. It returns a tool error and contacts no peer. That part already works." |
| 1 | legacy 结果要补上 ttlMs 这类字段吗？ | "No. Only resultType, as complete. Don't invent cache fields for an older era." |
| 2 | 保存时要保留运维写的注释吗？ | "No. save_peers writes a fresh file." |
| 2 | argv 怎么引用？ | "The way a POSIX shell quotes it. shlex is fine." |
| 2 | 协商出来的 era 要写进这个文件吗？ | "No. The era belongs to one transport lifetime, not to the configuration." |
| 2 | save 也要做校验吗？ | "Your call. Say what you chose. The tests check what load accepts." |
| 3 | -32020、-32021 要修正请求后自动重试吗？ | "Not here. negotiate fails with ProtocolError, and the caller fixes the request." |
| 3 | initialize 里请求哪个修订？ | "The first one in legacy_revisions. Any revision in that list is fine in the answer." |
| 3 | discover 的响应 id 对不上怎么办？ | "Treat the peer as broken and fail. It's no evidence of the legacy era. The tests don't cover it." |
| 4 | peer 死了是立刻重启，还是等下一个调用？ | "Your call. The tests only look at what each process receives." |
| 4 | 重试又失败了呢？ | "The call fails with TransportLost. One retry, no more." |
| 4 | 池里会有 legacy peer 吗？ | "No. Every pool peer is modern." |
| 5 | reject-on-collision 报第一个冲突还是全部？ | "All of them in one error is nicer. The test needs both peer names in the message." |
| 5 | 结果要排序吗？ | "It must not depend on the input order. Sorting by canonical name is one way to get there." |

## 每关：要看什么、提示、追问

### Part 1 修路由和响应关联（目标 10 分钟）

一个测试里叠了 4 个缺陷和 2 个护栏：

1. `protocol.mutual_version` 返回对方列表里第一个双方都支持的版本，不是最高的那个。discover 本身不报错，错误在两层调用之外才露出来：后面一个 `tools/call` 的 `_meta` 里版本不对。notes 是按从旧到新列出版本的，所以拿到了 2026-07-28。
2. `client.call` 把规范名原样发给后端。`notes/search` 到了 notes 那里是个未知工具，返回 isError。修法是发路由表里的 `route.local_name`。从规范名里截掉最后一个 `/` 之前的部分也能让 notes 通过，但 hub 是网关，它的本地名 `notes/search` 本身带 `/`，截完只剩 `search`，会挂在 hub 那条断言上。只在第一个 `/` 处拆开能过测试，因为 Part 5 的命名可逆；可以接受，但要追问下面第三条。
3. `client._result` 对所有 era 都要求 `resultType`。legacy peer 的结果没有这个字段，本课规定按 `"complete"` 处理。
4. `PendingCalls` 用列表存在途请求，`add` 查重和 `resolve` 都要线性扫描，5000 个乱序响应要 1.5 秒左右。
5. 护栏一：现代结果缺 `resultType` 仍然无效（测试里的 sloppy peer）。把检查整个删掉，或对所有 era 都补 `"complete"`，都会挂在这里。用版本号 `== "2025-11-25"` 判断 legacy 也不行：archive 协商的是 2024-11-05。
6. 护栏二：id 的类型和值都相同才算匹配。改成以裸 id 为键的 dict 后，`True == 1` 且哈希相同，id 为 true 的响应会领走请求 1。以 `str(id)` 为键会让 1 和 "1" 撞车。先 pop 再比较类型，会把真正的请求 1 弄丢。

看什么：是否从错误的版本戳一路往上找到 `mutual_version`；是否先打印实际发出的请求；是否一次只改一处，每改一处就重跑。

提示：
- H1："Where does the version in that request's _meta come from?"
- H2："What does mutual_version's docstring promise, and what does its loop return?"
- H3：直接指出 `mutual_version` 的循环。

追问：
- "Each transport call here returns its own answer. Why keep a pending table at all?"（stdio 是一条双向管道，多个调用同时在途时响应顺序任意，见 Part 4）
- "Python says True == 1. Why does JSON-RPC care?"（JSON 的 true 和 1 是不同类型，严格关联要同时比类型和值，1.0 同理）
- "Could call() just strip the prefix off the canonical name?"（只有命名可逆时才行，见 Part 5；存下路由更简单，命名策略变了也不受影响）

### Part 2 固定 peer 配置（目标 12 分钟）

坑：
- configparser 默认开着 BasicInterpolation。读到 `%PORT%` 报 InterpolationSyntaxError，写 `50%` 报 `invalid interpolation syntax`。要用 `interpolation=None` 或 RawConfigParser。只在写的时候把 `%` 转义成 `%%` 不够，运维手写的文件里是单个 `%`。
- argv 要按 shell 规则引用和拆分，用 `shlex.join` 和 `shlex.split`。`" ".join` 和 `str.split()` 会丢掉空格、引号和空字符串参数。
- `bool("off")` 是 True；`== "true"` 认不出 `yes`。用 `getboolean`。
- `probe_timeout_ms` 要读回成 int，`argv` 和 `legacy_revisions` 要读回成 tuple，否则 dataclass 比较不相等。超时必须是正数，`if not timeout` 只拦得住 0，拦不住 -275。
- `[DEFAULT]` 里的值会被每个 section 继承，`allow_legacy = true` 写在那里，就是本课说的通配符。把 `default_section` 改成别的名字来绕开也不行：`[DEFAULT]` 会变成一个叫 DEFAULT 的普通 peer，测试里那段带着 argv，于是能加载，测试会挂。docstring 要求整段拒绝。
- 同名 section 默认抛 DuplicateSectionError，它不是 ValueError；`strict=False` 会把两段合并，把 allow_legacy 绑到另一个命令上。
- `ConfigParser.read()` 遇到不存在的文件会静默跳过，返回空列表。要用 `open` 加 `read_file`。
- 名字或端点里有 `*` 要拒绝。端点里的 `?` 是查询串，不是通配符。

追问：
- "Why bind allow_legacy to the command or endpoint, not to the name a server reports?"（server 自报什么名字都行；运维固定的是自己信任的命令。本课："Do not use a wildcard that lets an arbitrary server opt itself into weaker semantics."）
- "Should the negotiated era be cached in this file?"（不该：era 只在一次传输生命周期内有效，重启或端点变化就要重新协商）
- "The lesson's skill also lists an environment allowlist. What breaks if you store env vars as INI keys?"（configparser 默认把键名转成小写，`PATH` 会变成 `path`；要设 `optionxform = str`，或者把它们放进值里）

### Part 3 era 协商（目标 12 分钟）

坑（按决策表）：
- 探测用 `modern_versions[0]`。DiscoverResult 里选双方都支持的最高版本，可以直接用 Part 1 修好的 `modern_selection`。
- -32022：从 `error.data.supported` 里选最高的共同版本，用新 id 重试一次。没有共同版本，或者重试又失败，就直接失败，不发 initialize，peer 在 allowlist 上也一样。一直重试会被假 peer 在第 5 条消息时判失败。
- -32020、-32021：是现代错误，失败，不降级。
- 超时、断开、空响应、其他错误码（-32601、-32602、-32603）都是含糊信号。peer 不在 allowlist 上就失败，transport 只收到一条 server/discover。只把 -32601 当成可以探测的信号，会挂在 -32602 上。
- 在 allowlist 上：只发一次 initialize，请求第一个配置的修订，用 peer 自己的 `probe_timeout_ms`，不带 `_meta`。按本课的五项检查验证结果，任何一项不过就失败，并且不发 `notifications/initialized`。
- 回来的修订在 `legacy_revisions` 里就接受，2024-11-05 也算；和内置常量 2025-11-25 比较会挂。
- `capabilities` 只要求是对象，`{}` 也算，用真值判断会挂。`serverInfo` 的 name 和 version 都要是非空字符串，只判断真值会放过 name 为 7 的回答。
- `TimeoutError`、`ConnectionError` 不能原样抛出，要变成 ProtocolError。
- `notifications/initialized` 是通知，没有 id。

追问：
- "Why is -32601 no evidence of a legacy server?"（现代 server 遇到不认识的方法也这样回答。本课：它只让 allowlist 上的 peer 有资格做一次探测）
- "How is this like a TLS downgrade attack?"（攻击者或坏掉的 server 诱使双方退回弱协议；对策是：有现代证据就绝不降级，legacy 需要运维意图加正面证据）
- "Where must the probe deadline be enforced?"（在真实的传输适配器里，读响应时用 select 或 asyncio.wait_for；这里的假 peer 只记录它）

### Part 4 stdio 进程池（目标 14 分钟）

坑：
- 输出格式由测试的解析代码决定：每个 peer 的 stdin 上一行一个 JSON-RPC 对象，以换行结尾。少了换行，start() 会卡住；`indent=2` 会被假 peer 当成半行。
- 每个 peer 一个读取任务，按 id 把响应交给等着的调用，可以用 Part 1 的 PendingCalls。files 会先收齐两个调用再倒序回答，"写一条、等一条"的串行写法会死锁。
- 进程退出（stdout 读到 `b""`）时，所有在途调用都要失败，否则会一直等下去。
- 只有 `retry_safe` 里给这个 peer 列出的工具才重试，而且只重试一次。files 的 restore 是安全的，notes 的 restore 不是；把各 peer 的名单合成一个集合会挂。`readOnlyHint` 是服务器自己的说法，不算数。
- 重试前要重启进程，重新 server/discover 和 tools/list。选中的版本跟着旧进程一起作废：新进程支持 2027-01-01，后面的请求都要带 2027-01-01。直接重发旧帧，会带着旧 id 和旧 `_meta`。
- id 要在整个池里递增。每个进程从 1 重新计数，重试的 id 会和丢失的那次相同。
- 一个 peer 迟迟不回答，不能挡住别的 peer（slow 探针）。全局锁会挂在这里。
- 测试里不会有两个调用同时触发同一个 peer 的重启，所以没有每 peer 一把锁也能通过；用下面第一条追问考这一点。start() 一个一个地启动 peer 也能通过。

追问：
- "Two safe calls were in flight when the peer died. How many processes do you start?"（一个；用每个 peer 一把锁，或者共享同一个连接中的 future）
- "When is it safe to retry a tools/call at all?"（只有幂等的操作，或者带应用层幂等键；崩溃可能发生在工具已经执行之后）
- "What about subscriptions/listen after a restart?"（用新的请求重新打开 listen 并重新拉列表；现代流不支持 Last-Event-ID 续传）

### Part 5 命名空间合并（目标 12 分钟）

坑：
- 先按 peer 名排序，排在前面的拿到裸名，后来的变成 `<peer>/<tool>`。按连接顺序（dict 的插入顺序）决定会挂。
- 后端本身是网关时，本地名里已经带 `/`。照课里的代码把它当裸名，`notes/search` 会和 notes 的前缀名撞车：课里的代码直接报错（一个 server 就能让整个合并失败），覆盖的写法则会把调用悄悄路由到另一个 peer。规则是带 `/` 的本地名总是加前缀。这样一来，规范名要么不含 `/`，要么在第一个 `/` 处拆回 (peer, 本地名)，不会重复。
- reject-on-collision 要报错，消息里带两个 peer 名。课里的代码是 `continue`，等于静默丢弃。
- 同一个 peer 把一个名字列了两次，两种策略下都是配置错误。用 set 去重，或者给第二个加前缀，都会挂。
- peer 名不能带 `/`，否则 `a/b` 的 `c` 和 `a` 的 `b/c` 会撞车。
- 测试里还有一段 300 组的随机检查：每个工具恰好一个规范名，规范名能拆回原来的 peer 和本地名。只在 `/` 前面恰好是某个 peer 名时才加前缀，会挂在这一段。
- 返回的 dict 不按规范名排序也能通过，只要 peer 和工具都先排了序，结果就与输入顺序无关。

追问：
- "A new peer named aaa connects tomorrow. What happens to the bare names?"（它会拿走所有和别人重名的裸名，模型的调用悄悄换了 server，这是第 15 课讲的工具遮蔽；可以配显式别名或信任顺序）
- "The model provider rejects '/' in tool names. Now what?"（换成 provider 允许的可逆写法，路由表仍然是唯一的依据）
- "Only peer order decides the bare name. Why sort the tools too?"（输出和模型上下文都稳定；本课：本地注册表的顺序不能取决于启动时序）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看实际发出的请求、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出降级攻击、幂等重试、工具遮蔽、超时由谁执行 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
