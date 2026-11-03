# 面试官手册：MCPCore（13/06）

候选人计时期间不要看。候选人手里只有 README、`mcpcore/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | make_request 要不要复制调用者传进来的 params？ | "Yes. A request is a snapshot, and building it leaves the caller's dict as it was." |
| 1 | 缺 capabilities 的请求，能不能当成空对象？ | "No. An empty object is a valid declaration. A missing one is invalid params, -32602." |
| 1 | 没有 clientInfo 的请求要拒绝吗？ | "No. clientInfo is recommended, not required. A present one must be well-formed." |
| 1 | 服务器起来以后还能注册工具吗？ | "Yes, any time. A new tool is callable and listed right away." |
| 2 | id 为 null 和没有 id 要区分吗？ | "Yes. A null id is an error the server couldn't tie to a request. No id is a notification. Both come back as they were." |
| 2 | id 会超过 64 位吗？ | "JSON puts no limit on numbers, and we've seen clients send huge ids. Keep them exact." |
| 2 | raw 能存成 TEXT 吗？ | "Any column type you like, as long as the bytes come back exactly. Some lines aren't valid UTF-8." |
| 2 | 同一个 seq 记两次怎么办？ | "That's a recorder bug. Your call. The tests don't cover it." |
| 3 | 要支持 batch（JSON 数组）吗？ | "No. One message per body. An array is -32600 with a null id." |
| 3 | 头名的大小写要处理吗？ | "No. The HTTP layer hands you these exact names." |
| 3 | 通知格式不对，要回错误吗？ | "Not outside HTTP: there a notification never gets a response. Over HTTP it goes through the same checks as a request, up to the version. An error goes back with a null id, and one that passes gets nothing back." |
| 3 | 头和 body 的版本一致，但服务器不支持呢？ | "Then it's -32022. Only a disagreement is -32020." |
| 3 | tools/call 的 name 不是字符串，归 check_request 管吗？ | "Over HTTP the Mcp-Name comparison catches it. Otherwise it's the handler's job." |
| 3 | id 是 null 的请求怎么处理？ | "Your call. Say what you chose. The tests don't cover it." |
| 3 | -32020、-32602 这些错误要带 data 吗？ | "Up to you. Only -32022 and -32021 have data the client relies on." |
| 4 | 响应的 id 没有对应的请求？ | "That's an orphan. The docstring has its line." |
| 4 | 一个 id 能用两次吗？ | "Once its request is answered, yes. Ids are unique only while a request is in flight." |
| 4 | 出现过 initialize 以后，后面的消息都算 legacy 吗？ | "No. Every message is judged on its own." |
| 4 | 要区分消息的方向吗？ | "Not in this stream. Requests come from the client, responses from the server." |
| 5 | `{"extensions": {}}` 满足对 tasks 扩展的要求吗？ | "No. An empty object declares that capability, not the ones a requirement nests below it." |
| 5 | true 算声明了吗？ | "No. Only an object declares a capability." |
| 5 | data 里列出全部要求，还是只列缺的？ | "Only what's missing." |

## 每关：要看什么、提示、追问

### Part 1 修无状态请求（目标 12 分钟）

一个测试里叠了 5 个缺陷和 3 个护栏：

1. `make_request` 直接把调用者的 params 当成请求的 params，再往里写 `_meta`。测试用同一份 params 造了两个请求，第二个请求把第一个的版本改回了 `2026-07-28`。错误不在这里报：测试看到的是服务器“接受了一个不支持的版本”，而 `validate_request` 的版本检查没有问题。根因在两层调用之外的客户端构造器。
2. `request_meta` 没拿到 capabilities 时，放进去的是模块级的 `NO_CAPABILITIES`，所有请求共用这一个 dict。一个调用者给自己的请求加上 tasks 扩展，之后的每个请求都“声明”了它。
3. `NotesServer.dispatch` 记住上一个请求的 capabilities，遇到缺 capabilities 的请求就替它补上，顺手还改了调用者的 message。这是课里 The Problem 说的“从先前的请求推断”，也是 legacy 时代按连接协商留下的习惯。
4. `tools/list` 按注册顺序返回，换个注册顺序结果就变（课后练习 3）。
5. `tools/call` 每次都把整个注册表排一遍序，再线性找名字。20000 个乱序注册的工具调用 500 次，要 1.4 秒以上，限值是 0.04 秒。

护栏：
- 缺 capabilities 时当成空对象（在 `validate_request` 里写 `meta.get(CAPABILITIES_KEY, {})`，或者在 dispatch 里 `setdefault`），第 3 处的断言照样挂。空对象是合法声明，缺失是 -32602。
- 去掉 clientInfo 的请求必须仍然有效（课后练习 5）。为了修第 3 处把 `_meta` 的三个键都设成必填，会挂在 "clientInfo is recommended, not required"。
- 修第 5 处要在 `register` 里维护索引。只在 `__init__` 里建一次索引，或者把排好序的名字缓存起来，后注册的工具就调不到、列不出。

另外几种不够的修法：`dict(params)` 只复制一层，`arguments` 还是和调用者共用；最后把整个请求 deepcopy 一遍也不行，调用者的 params 里已经被写进了 `_meta`；只把 `NO_CAPABILITIES` 换成新的 `{}`、却不再复制显式传入的 capabilities，调用者的 dict 会被请求改掉；只去掉排序、保留线性扫描，20000 个工具扫 500 次在本机要 65–190 ms，仍然超过限值。

看什么：第一处报错时，是先怀疑服务器的版本检查，还是先打印 `future`，发现它的版本已经不是 `2027-01-01`；能不能说清楚报错的位置不是根因；每改一处就重跑。

提示：
- H1："Print future right before it is dispatched. Is that the version it was built with?"
- H2："Which objects do future and today share?"
- H3：直接指出 `make_request` 里的 `body_params = params` 和 `request_meta` 里的 `NO_CAPABILITIES`。

追问：
- "stdio has one client per process. Why shouldn't the server remember capabilities anyway?"（同一个 HTTP worker 或网关会轮流处理不同客户端的请求；副本之间不共享内存；课里 The Problem 的例子）
- "A handler needs to know whether this client supports tasks. Where does it get that?"（从当前请求的 `_meta` 显式传下去，不能挂在 `self` 上）
- "tools/list returns deep copies. What breaks if it handed out the registry's own dicts?"（调用者改了列表里的工具，就改了服务器，之后每个请求都看得到；本课代码讲解里 `SERVER_CAPABILITIES.copy()` 的浅拷贝问题）
- "Exercise 4: when may tools/list be cacheScope public?"（每个调用者看到的列表都一样时才行；按用户过滤的列表必须 private；安全默认是 `ttlMs: 0` 加 `private`）

### Part 2 transcript 库（目标 10 分钟）

坑：
- 没有 id 的通知和 id 为 null 的错误响应要读回可区分。SQL 的 NULL 不能同时表示两者。参考做法是把 id 存成 JSON 文本：null 存成文本 `null`，没有 id 才存 SQL NULL。
- id 可能超过 2^63。直接绑定 Python int 会报 `OverflowError`。把 JSON 文本放进 INTEGER 或 NUMERIC 列也不行：SQLite 的类型亲和性会把整数 id 的 JSON 文本 `7` 存成整数 7（读回来是 int，不能直接 `json.loads`），把 `18446744073709551617` 存成 REAL `1.8446744073709552e+19`，精度就丢了。带引号的 `"7"` 仍是文本。列要用 TEXT，或者不声明类型。
- `7` 和 `"7"` 是两个 id。用 `str(id)` 存会把类型丢掉。
- raw 是字节，原样进、原样出。有一行不是合法的 UTF-8：解码成文本会报 UnicodeDecodeError，`errors="replace"` 会改掉字节，`strip()` 会丢掉行尾的 `\r`，把解析结果重新 `json.dumps` 会改掉空格和 `\u00e9` 这种转义。存 BLOB 最省事。
- 读回按 seq 排序。测试先记 seq 4 再记 seq 3，按插入顺序读会错。seq 要存成整数：存成 TEXT 的话，`10` 会排在 `2` 前面。`with_id` 也要按 seq 排：超过 64 位的那对 id，先记的是 seq 11 的响应，后记的是 seq 10 的请求。另设一个自增列、按它排序就会错。
- `with_id(None)` 要找到 null id 的那条。如果 null 存成了 SQL NULL，`WHERE id = ?` 传 None 永远匹配不到，因为 `= NULL` 从来不为真。

追问：
- "Why keep the raw line instead of the parsed message?"（解析不了的那一行正是排查时最需要的证据；Ship It 的 skill 写着保留原始 transcript，修正的例子另外给）
- "Transcripts contain tool arguments and results. What about secrets?"（脱敏后的副本另存，原始证据加访问控制和保留期限，不能悄悄改写原文）
- "One recorder per direction, both writing to this database?"（SQLite 一次只有一个写者，可以开 WAL；seq 必须由同一个能看到两个方向的点来分配）

### Part 3 请求生命周期（目标 14 分钟）

坑：
- 顺序是：类型（-32602）先于头（-32020），头先于版本支持（-32022），版本先于方法（-32601）。
- 头和 body 的版本不一致时，不管哪一边是不支持的版本，都是 -32020。直接调用现成的 `validate_request` 再比较头，这里会报成 -32022；先比较头再调用它，类型错误又会报成 -32020。要把它拆开。
- 三个头都在版本检查之前比较。测试里 Mcp-Method 不一致、Mcp-Name 不一致的两行，头和 body 的版本一致但都不受支持。把 Mcp-Name 当成 tools/call 的参数校验、放到版本检查之后，会报成 -32022。
- 本课 `code/main.py` 的 `validate_request` 先查版本支持、后查 capabilities，照抄会把“不支持的版本加缺 capabilities”报成 -32022（本课测验 Q3、Q9）。clientInfo 同理，坏了的 clientInfo 也要在版本之前报 -32602。
- 没有 id 成员的消息是通知。不经 HTTP（`headers is None`）时什么都不回：params 坏了不回，jsonrpc 写错了也不回。经 HTTP 时要和请求一样过第 3 到第 5 步（头不对是 -32020，版本不支持是 -32022），出错就回 null id 的错误；都通过了也不回，不再查 -32021 和 -32601。这和第 09 课一致：接受的通知回 202、没有 body，头不对的通知回 400 和 -32020。
- -32700 和“不是一个 JSON 对象”的 -32600 用 null id，响应里要有 `"id": null` 这个成员。不支持 batch 数组。
- `headers` 是 `{}` 也说明消息来自 HTTP，只是一个头都没带，应该是 -32020。写成 `if headers:` 会把它当成 stdio。
- Mcp-Name 镜像哪个参数随方法而定：tools/call 是 `name`，resources/read 是 `uri`，`NAME_PARAMS` 已经给了。Mcp-Name 缺失也是 -32020。
- -32022 的 data 正好是 `requested` 和 `supported` 两个键，`supported` 是列表，而且是副本：调用方改了它，不能改到服务器的 `SUPPORTED_VERSIONS`。
- 版本精确匹配，不按日期比大小。`2027-01-01` 不会因为比较新就被接受。
- 第 6 步要用 Part 5 的 `missing_capabilities`。Part 3 的测试里没有带需求的方法；无条件调用它，这一关就会碰到 NotImplementedError。只在方法出现在 `required` 里时才调用。

追问：
- "Why does -32020 win over -32022?"（课里的例子：网关按 `Mcp-Name: notes.read` 授权，源站执行 `params.name: notes.delete`。两半对不上的请求先拒掉，网关和源站才不会各自理解成不同的调用；每类失败也各自留下可区分的证据）
- "Which HTTP status goes with each code?"（第 09 课：头不一致和版本不支持是 400；未知方法是 404，body 里带 -32601，双时代客户端靠它区分现代错误和 legacy 端点不存在）
- "The client gets -32022. What next?"（从 `data.supported` 里挑一个双方都支持的版本，用新的 JSON-RPC id 重试；不能因此退回 legacy 的 initialize）
- "A tool is named café. What goes in Mcp-Name?"（第 09 课：UTF-8 的 Base64 哨兵 `=?base64?...?=`，比较前先解码）
- "A request arrives with id 0. Walk me through your notification check."（只有缺少 id 成员才是通知；`if not message.get("id")` 会把 0 和空串当成通知。这一关的测试没有覆盖，第 07 课和第 14 课的题里有）

### Part 4 无状态追踪器（目标 12 分钟）

坑：
- 响应按 id 配对，不是配给最早的在途请求：测试里 tools/call 和 tools/list 同时在途，回答按相反的顺序到达。
- 配对后要从 pending 删掉，同一个 id 的第二个响应是 orphan。
- 通知不进 pending。-32700 的响应 id 是 null；如果通知被当成 id 为 None 记进 pending，这条响应就会“配上”一条通知。
- 请求答完以后 id 可以再用（测试里 id 1 先用于 discover，后用于 tools/list）。拿“见过的 id”集合判断 orphan，会把重用的 id 也当成 orphan。
- era：-32020、-32021、-32022 是现代证据（Ship It 的规则），-32602、-32700 不是。本课的 `trace_message` 把所有错误都标成 unknown。
- 只有回答 initialize 的结果才是 legacy。本课的 `trace_message` 把所有缺 resultType 的结果都标成 legacy，这里要标 invalid，因为现代的成功结果必须带 resultType。看到 initialize 以后也不能“切换到 legacy 模式”，后面的现代请求仍然是 modern。按结果里有没有 protocolVersion 来判断也不行：测试最后有一条重复发来的 initialize 结果，它回答的请求已经答过了，是 orphan/invalid。
- 有 resultType 就是 modern，值不一定是 `"complete"`：tasks 扩展的 tools/call 回 `resultType: "task"`（第 13 课）。只认 `"complete"` 会把它标成 invalid。
- 只有版本、没有 capabilities 的请求是 invalid（本课测验 Q12 第 4 条），但它也要进 pending，它的错误响应照样配对。
- 现代服务器用 -32601 回答 initialize，era 是 unknown，不是 legacy。错误的 era 只看错误码；第 08 课也说 -32601 不能当作 legacy 的证据。
- 不是对象的消息（测试最后那个列表）不能让追踪器崩掉。
- 每条消息一到就输出，测试会数拉取了几条；每行恰好一个 `\n`。
- 写成普通的 async 函数（只有 return、没有 yield）时，测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出来这里需要 async generator。

追问：
- "Why not switch the tracer into legacy mode once it sees initialize?"（一份 transcript 里可能有多个连接、多个客户端；课里说双时代实现是无状态的现代核心加隔离的 legacy 适配器，选哪一边要显式决定；按历史推断时代，和按历史推断 capabilities 是同一个错误）
- "A response never arrives. What happens to pending?"（只增不减就是内存泄漏；给 pending 设上限、按时间淘汰，流结束时把没回答的请求报出来）
- "Legacy servers also sent requests to the client. How would direction change the pending map?"（按 (发送方, id) 当键；Ship It 的 skill 要求现代流量里出现服务器发起的请求就报错）

### Part 5 嵌套 capability（目标 12 分钟）

坑：
- 键名里有 `.` 和 `/`，`io.modelcontextprotocol/tasks` 是一个键。先拼成点号路径再按 `.` 拆，会拆成 `io` 和 `modelcontextprotocol/tasks`。
- `{}` 表示支持；`true`、`null`、`[]`、字符串、数字都不算，名字列表 `["io.modelcontextprotocol/tasks"]` 也不算。
- 空对象只声明它自己：`{"extensions": {}}` 不满足挂在 extensions 下面的 tasks。
- 只报缺的部分：部分满足的子树只留缺的叶子，全部满足返回 `{}`，已满足的键不能以空对象的形式出现在结果里。
- 结果是副本：调用方改了 error data，不能改到服务器的需求表。
- 在 `check_request` 里的位置：头（-32020）和版本（-32022）之后；capabilities 不是对象时是 -32602，不是 -32021；data 是 `{"requiredCapabilities": ...}`，不能直接放缺失的对象。
- data 里也只放缺的部分：测试里 notes/sync 的要求有三片叶子，请求声明了其中两片，data 里只剩 attachments。直接放整份需求（哪怕是副本），或者只在整份需求都缺时才报 -32021，都会挂。

追问：
- "Lesson 15 says {"elicitation": {}} implicitly supports form elicitation. Where would that rule go?"（在匹配之前把声明规范化，集中在一个地方做；通用的匹配函数里不写特例）
- "Why report only the missing part?"（客户端能准确告诉用户或开发者还要打开什么；整份需求会把已经有的也列进去）
- "A tools/call that may return a task needs the tasks extension in that same request. How would you key requirements per tool instead of per method?"（按 (方法, 工具名) 查需求；工具名校验过以后、handler 运行以前检查）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出多路复用、缓存作用域、证据保全、HTTP 状态码、pending 的内存上限 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
