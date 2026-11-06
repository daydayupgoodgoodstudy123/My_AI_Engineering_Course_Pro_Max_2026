# 面试官手册：streamhttp（13/09）

候选人计时期间不要看。候选人手里只有 README、`streamhttp/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 两个 Mcp-Method 或 Mcp-Name 的值一样，也要拒绝吗？ | "Yes. Each routing header must arrive exactly once; never select a value from duplicates." |
| 1 | 两个 Content-Length 的值一样，也要拒绝吗？ | "Yes. We never choose between two framing headers, even when they agree." |
| 1 | Content-Length: 0 可以吗？ | "No. A JSON-RPC message is never empty: 1 through the limit." |
| 1 | 能不能一次 read 读完？ | "No. A connection can hand you fewer bytes than you ask for." |
| 1 | 头值两边的空格要不要去掉？ | "The HTTP parser has already trimmed them. Compare exactly what you get." |
| 2 | save 会顺延过期时间吗？ | "No. A draft lives ttl_ms from creation, however often it is saved." |
| 2 | 过期的草稿要删掉吗？ | "Your call. The tests only need it to be gone for every caller." |
| 2 | 副本能在内存里缓存草稿吗？ | "Only if every read still sees the latest save from any replica. Simplest is no cache." |
| 2 | handle 用什么格式？ | "Anything opaque with at least 128 random bits. secrets.token_urlsafe is fine." |
| 2 | 拿着别人的 handle，报什么错？ | "Exactly what a handle we never issued gets." |
| 3 | 要检查 Content-Type 和 Accept 吗（415、406）？ | "Not in this session. The tests always send good ones." |
| 3 | dispatch 返回 -32602 这类错误时，HTTP 状态码给多少？ | "200. Only -32601 maps to 404." |
| 3 | 被拒绝的通知要带 JSON-RPC body 吗？ | "Yes: the error with a null id, like any message we reject before dispatch." |
| 3 | 收到两个 Origin 头怎么办？ | "Refuse it. Never pick one. The tests don't send two." |
| 3 | 允许列表里的 origin 要不要做大小写或端口归一化？ | "No. Exact match against the configured list." |
| 4 | keepalive 注释里写什么？ | "Anything after the colon, or nothing. One comment line, then a blank line." |
| 4 | 没有 progress token 时 Heartbeat 还发吗？ | "Yes. A keepalive isn't progress." |
| 4 | 工具没给 ToolResult 就结束了呢？ | "That's a bug in the tool. The tests don't cover it." |
| 5 | 单独一个 CR 也算换行吗？ | "Not here. LF or CRLF." |
| 5 | 非 200 的响应怎么办？ | "Not this class's job. It only ever sees the body of a 200." |
| 5 | 流开头会有 BOM 吗？ | "No. The tests never send one." |

## 每关：要看什么、提示、追问

### Part 1 修请求读取（目标 10 分钟）

一个测试里叠了 4 个缺陷和 1 组护栏：

1. `Headers.get_all` 按原样比较头名（`key == name`）。测试模拟 HTTP/2 那一跳，所有头名都是小写。错误不在 `Headers` 里报出来，而是在上一层：`read_body` 报 `FramingError: Content-Length is required`，可请求里明明带着 `content-length`。
2. `_expect` 只拒绝没有值，随后取 `values[0]` 比较。第一个路由头与 body 相同，第二个却不同也会放行；两个值相同也不能接受。头名大小写不同仍然是同一个路由字段。要先确认正好一个值，再使用它，不能 first-wins、last-wins 或只拒绝冲突值。解码后原样比较已经正确给定，大小写和尾空格断言保护这个合同。
3. `body_name` 一律取 `params.name`，`resources/read` 应该取 `params.uri`。测试用的正是讲义练习 3：非 ASCII 的 URI 用 Base64 哨兵发过来，解码后和 `params.uri` 比较。
4. `read_body` 用 `body += chunk` 累加 bytes。bytes 没有原地追加，每次都把已读的部分复制一遍，是 O(n²)：12 MiB 的 body 按 4 KiB 一块读要 1 秒多，改成 bytearray 或 list 加 join 只要 2 到 3 毫秒。
5. 护栏：换成快写法时，Content-Length 的严格规则一条都不能丢。缺失、两个冲突的值、和 Transfer-Encoding 同时出现（测试里的 TE 头名是小写）、非 ASCII 数字（`"١٠".isdigit()` 为真，`int()` 也能转）、带符号、0、超过上限，都要在读 body 之前拒绝；body 不够长要报错；只读 Content-Length 个字节，后面的字节留在流里。顺手把值也转小写、给值 strip、只转一边的小写，也都会被抓住。

测试不抓的写法：`body_name` 写成 `params.get("uri", params.get("name"))`，不分方法。测试里的请求都只带其中一个字段，所以能过，但 `resources/read` 漏了 uri 时会拿 name 去比。看到了可以问一句。

看什么：是不是先看 traceback，再把实际的头打印出来；会不会想到报错的地方和出错的地方不是同一处；每改一处就重跑。

提示：
- H1："The request has a Content-Length. What name does read_body ask for, and what name did the client send?"
- H2："Print lowered.get_all('Content-Length')."
- H3：直接指出 `get_all` 里的 `key == name`。

追问：
- "Why refuse Content-Length plus Transfer-Encoding instead of preferring one?"（前置代理和源站可能按不同规则切分请求边界，这是请求走私的典型条件；宁可拒绝也不猜）
- "Why must the bytes after the body stay in the stream?"（HTTP/1.1 长连接上，下一个请求就从那里开始；多读一块会吃掉或拼错下一个请求）
- "Why is it dangerous to compare header values case-insensitively?"（网关按头做路由和授权，源站执行 body。比较一宽松，网关看到的和源站执行的就可能不是同一个方法或工具）
- "The lesson's server has no timeout while it reads headers. What does that expose?"（slowloris：慢慢发请求头占住线程。给 Handler 设 timeout，前面放有超时和连接上限的反向代理）

### Part 2 共享草稿库（目标 12 分钟）

坑：
- 漏 commit：sqlite3 执行 INSERT 时会自动开事务，不提交，另一个副本的连接就看不到。第一处 `replica_b.get` 就报 UnknownHandle。
- 在副本内存里缓存草稿：B 保存以后，A 从自己的缓存读到旧版本。讲义说副本内存可以做缓存，但不能是正确性依赖的唯一副本。
- handle 用计数器或固定种子的 random：两个副本各自从头数，插入时撞主键（`UNIQUE constraint failed`）。太短的 handle 过不了 128 位的检查：测试按字符集估算位数，全是十六进制字符的每个字符算 4 位，其余算 6 位，所以 `token_hex(12)`（24 个字符，96 位）和 `token_urlsafe(8)` 都会挂，`token_hex(16)`、`token_urlsafe(16)` 能过。`uuid.uuid4().hex` 也能过（32 个十六进制字符，实际 122 位随机），可以接受，但 docstring 要求用 secrets，值得问一句。
- 过期时间用整数毫秒和注入的 clock。用墙上时钟，`expires_at_ms` 对不上；列声明成 REAL，读回来是 float；`expires_at_ms - 1` 时还能读，到期那一刻就读不到，`>=` 和 `>` 写反会挂。
- save 不顺延过期时间。测试先把时钟拨快一分钟再保存。
- 版本号要放进 UPDATE 的 WHERE 里做 compare-and-set。旧版本号保存必须报 VersionConflict，而且什么都不改。`VersionConflict.current` 是库里现在的版本（测试里是 2），不是调用方传进来的 expected_version；服务器把它写进“read version N and retry”的提示里。
- 别人（另一个 subject，或者同名但在另一个租户）拿着 handle，得到的错误要和“从没发过的 handle”一模一样，类型和消息都一样。专门写一句“这个草稿是别人的”，或者抛 PermissionError，都等于告诉对方这个 handle 存在。
- 先查归属再查版本。先比版本号的话，入侵者拿旧版本号保存会得到 VersionConflict，同样泄露了存在性。
- 正文原样读回：CRLF、行尾的空格和制表符、U+2028、emoji。

追问：
- "Your save reads the version, then updates. Two replicas do that at the same moment?"（丢失更新。版本号必须写在 `UPDATE ... WHERE version = ?` 里，让 SQLite 原子地判断，再看 rowcount。测试是单线程的，测不出先读后写的竞态，所以要靠追问）
- "Why not turn on sticky sessions instead?"（讲义：重启、发布、重新调度、故障转移都会把下一个请求挪到别的副本上）
- "The client times out and retries a save. What happens?"（第一次如果已经写进去，重试会撞 VersionConflict；要可靠就加幂等键。讲义把并发控制和幂等都列为草稿必需的）
- "Expired drafts pile up. Then what?"（定期 `DELETE ... WHERE expires_at_ms <= now`，给 expires_at_ms 建索引）
- "The replicas run on two machines?"（SQLite 文件不能放在网络盘上让多台机器写；换成真正的共享数据库，接口不变）

### Part 3 HTTP 响应映射（目标 14 分钟）

docstring 里按顺序列了 9 条规则。坑都在细节里：
- 路径不对是没有 JSON-RPC body 的 404；方法不存在是带 `-32601` body 的 404。讲义说双时代客户端靠这个 body 区分“现代服务器”和“端点不存在”，两种 404 不能混。
- 除 POST 以外一律 405，并带 `Allow: POST`。只拦 GET 和 DELETE 的话，PUT 会被当成 POST 往下处理。
- Origin：头存在、又不等于允许列表里的任何一项，才是 403；没有这个头就放行。前缀匹配会放过 `https://client.example.attacker.net`；`if origin and ...` 会把空字符串当成没有；用 `DEFAULT_ORIGINS` 而不是构造时传入的列表，会放过 `http://127.0.0.1`。Origin 要在方法之前查。
- 镜像头不一致是 `-32020`，排在版本检查之前：头写 2027、body 写 2026，或者反过来，都是 `-32020`。先查版本支持，不管查的是 body 的版本还是头的版本，都会挂。
- `-32022` 的 data 精确是 `{"supported": ["2026-07-28"], "requested": "2027-01-01"}`。
- 通知也要过同样的检查（镜像头、版本），通过了才 202，而且 body 必须是空的，`b"null"` 不行。没有 id 的 `prompts/list` 也是 202：通知从来不回 JSON-RPC 响应，方法不认识也一样。
- 只有 `-32601` 变成 404。dispatch 返回的其他错误（测试里是 `arguments` 传成列表的 `-32602`）是 200，写成 `404 if "error" in response` 会挂。
- 读不出 body（Content-Length 冲突）、不是 JSON、不是 UTF-8，都是 400 加 `-32700`，id 为 null。只捕获 `json.JSONDecodeError` 的话，FramingError 和 UnicodeDecodeError 会直接抛出来。
- `Mcp-Session-Id` 和 `Last-Event-ID` 不拒绝，也不回显。
- 测试不抓、可以接受的写法：Origin 先转小写再比（浏览器发来的 Origin 本来就是小写，但和澄清答案“exact match”不一致，可以问一句）；收到两个 Origin 时，参考答案回 403，本课 `code/main.py` 回 400 加 `-32020`，两种都算拒绝；把 `"id": null` 当成通知回 202（讲义只说没有 id 的是通知，JSON-RPC 规定有 id 成员就是请求，可以追问）；`-32020` 的错误回 null id（测试只查了 `-32022` 的 id；本课代码两种都回请求的 id）。
- Base64 哨兵的解码在 Part 1 的代码里，这一关只看它在 HTTP 层的效果：哨兵形式的非 ASCII 工具名能通过（未知工具是工具错误，`isError: true`），坏的 Base64、裸的非 ASCII 值、缺少 Mcp-Name 都是 `-32020`。
- 最后一段是端到端检查：两个 StreamableServer 共用一个 SQLite 文件，副本 1 建草稿，副本 2 凭 handle 继续保存。`dispatch` 必须拿到 `request.principal`，传 None 的话草稿工具会回“需要认证”的工具错误。

追问：
- "Why does a header mismatch beat an unsupported version?"（网关只看头做路由、限流和授权，源站执行 body。头和 body 不一致，说明两边看到的不是同一个请求，要先报这个。先报 `-32022` 的话，客户端会去换版本重试，真正的问题被盖住）
- "Origin validation passed. Is the caller authenticated?"（不是。Origin 只防 DNS rebinding；本地服务绑 127.0.0.1，网络服务每个请求都要认证和授权，见第 16、18 课）
- "A client forgets the id on tools/call and gets 202. Whose bug is it?"（客户端的。服务端按通知处理是规定行为；想更早暴露，可以对已知的请求方法缺 id 报 400）
- "When would this server answer a tools/call with SSE instead of JSON?"（长时间运行、要发进度的调用，就是 Part 4）

### Part 4 请求级 SSE（目标 10 分钟）

坑：
- 输出格式由测试的解析代码决定：每个事件只有一行，后面一个空行。`indent=2` 会把 JSON 拆成多行；加 `event:` 行同样不行；行尾是 `\n`，CRLF 过不了。
- 不写 `id:`。现代流不能续传，讲义明确说不要为重放加事件 id。
- Heartbeat 写成注释行 `:` 加空行。写成空的 `data:` 事件，客户端会去 `json.loads("")`；注释后面少了空行，下一个 data 行就和注释挤在同一块里；写成进度通知也不对，keepalive 不是进度。
- 没有 progress token 就不发进度，Heartbeat 照发。“没有”指的是 None：测试里 indexer 的 token 是 `0`，写成 `if progress_token:` 会把它当成没有。`total` 和 `message` 没有就不写，不能写成 null。
- 最终响应用 `complete()` 包装，写完就结束，不再向 steps 要下一个。
- 每个事件一产生就写出去。先把 steps 全读完再写，indexer 在结果之后的那一步也会被执行，crawler 会被一直读到第 999 页。
- 关闭流就是取消调用：stream 被 aclose 时，steps 要在 aclose 返回之前关掉。用 try/finally 或 `contextlib.aclosing`；`except Exception` 接不住 GeneratorExit。
- 测试不抓、可以接受的写法：`json.dumps` 用默认的 `ensure_ascii=True`，或者分隔符带空格（仍然只占一行，客户端照样能解析，但 docstring 写的是 compact）；只在 `except GeneratorExit` 里关 steps，正常写完最终响应时不关（asyncio.run 结束时会替它收尾，不过有清理逻辑的工具会晚一步释放，追问时可以提）。
- 写成普通的 async 函数（函数体里没有 yield）时，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`。

追问：
- "Here the tool sends heartbeats. How would you send a keepalive after 15 s of silence instead?"（保留一个挂起的 `__anext__` task，用 `asyncio.wait({task}, timeout=15)`，超时就写注释，再接着等同一个 task。用 `asyncio.wait_for` 的话，超时会取消工具正在执行的那一步。关闭时先 cancel 并等这个 task 结束，再 aclose steps）
- "The client hangs up halfway through a tool that sends emails. What then?"（关流即取消，已经发生的副作用撤不回；客户端只能在安全时用新 id 重试，非幂等的操作要靠应用层的幂等控制）
- "A reverse proxy delivers all the events in one burst at the end. Why?"（代理缓冲。`SSE_HEADERS` 里的 `Cache-Control: no-cache` 和 `X-Accel-Buffering: no` 就是为这个，见第 29 课）
- "Could the server send the client a sampling request on this stream?"（不能。讲义：这条流上不能发独立的 JSON-RPC 请求，sampling、elicitation、roots 走 MRTR 的结果，见第 11 课）

### Part 5 客户端分层解码（目标 14 分钟）

坑：
- 先在字节层按 `\n` 切行，整行到齐再按 UTF-8 解码。逐块解码在 1 字节一块时会把 é 和 emoji 切开，报 UnicodeDecodeError；用 `errors="replace"` 不报错，但内容被换掉了。JSON body 也一样，要攒齐再解析。
- 不能用 `str.splitlines()`：它会在 U+2028 这类字符上断行，而 JSON 字符串里可以有原始的 U+2028。SSE 的行尾在本题只有 LF 和 CRLF。
- CRLF 的 CR 要去掉。不去的话，`\r` 那一行不算空行，事件不会在那里结束，下一个事件的 data 会拼进来。用正则把 CR 当行尾、又不等 LF 到达，也会在 CR 和 LF 被切进两块时多出一个空行，把多行 data 拆成两半。
- 冒号后面只去掉一个空格；`data:` 后面可以不带空格，用 `line[6:]` 会吃掉 JSON 的第一个字符。
- 只有 data 字段是数据，`event:`、`id:`、`retry:` 都忽略。没有 data 的块（比如注释加空行）不产生事件。每个事件结束后要清空 data 缓冲；多行 data 用 `\n` 连起来，不能只留最后一行。
- 最终响应可以是 result，也可以是 error：对 id 41 的 `-32602` 错误同样是最终响应。只认 `result` 的写法会把它当成 ProtocolError。
- 最终响应之后再来消息是 ProtocolError；服务器在这条流上发请求（测试里是 `sampling/createMessage`）是 ProtocolError；id 的类型和值都要相等，`"41"` 不是 41，JSON body 里的 id 也要查。
- 流在最终响应之前结束是 StreamLost，不是普通的 ProtocolError；结尾那个没有空行收尾的事件要丢掉，不能在 finish 时补发。
- 测试不抓、可以接受的写法：多行 data 用 `""` 而不是 `"\n"` 连接，冒号后面的空格全部去掉（`lstrip()`）。对 JSON 数据这两种写法结果相同，因为 JSON 字符串里不能有原始换行，行间的空白也不影响解析；但和 SSE 规则不一致，可以问候选人换成纯文本数据会怎样。另外，用子串判断 Content-Type（`"event-stream" in ct`）、不检查响应里有没有 result 或 error，测试也不抓。
- Content-Type 按媒体类型比较，忽略大小写和 charset 参数。测试传进来的头名是小写的 `content-type`，可以直接用 Part 1 修好的 Headers。
- 最后一段把 Part 4 写出的流交给这个 reader，读出进度和最终结果。

追问：
- "The SSE spec also allows a lone CR as a line end. What changes?"（块尾的 CR 要先扣住，等下一个字节：是 LF 就和它一起算一个 CRLF，不是就把 CR 当行尾；流结束时再处理扣住的 CR）
- "The reader raises StreamLost. What does the caller do next?"（安全时用新的 JSON-RPC id 重发；不能带 Last-Event-ID 续传；subscriptions/listen 断了要重新 listen 并重新拉取）
- "Why is it safe to split on b'\\n' before decoding UTF-8?"（UTF-8 多字节序列里的每个字节都不小于 0x80，0x0A 不会出现在一个字符中间）
- "A hostile server sends one 2 GB line. What breaks?"（缓冲区无限增长。要给单行和单个事件设上限，超过就断开）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、打印实际的头和字节、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出请求走私、并发写、幂等、代理缓冲、断流重试 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
