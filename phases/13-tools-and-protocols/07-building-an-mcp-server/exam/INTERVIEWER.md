# 面试官手册：notesrv（13/07）

候选人计时期间不要看。候选人手里只有 README、`notesrv/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 负数 id 合法吗？ | "Yes. Any integer within ±(2^53 − 1), and any string." |
| 1 | id 是 5.0 怎么办？ | "Treat it like any other float: -32600. The tests don't send it." |
| 2 | 正文文件用什么编码？ | "UTF-8, exactly the body's bytes. Nothing added, nothing removed." |
| 2 | 可以在内存里缓存笔记吗？ | "Yes, as long as a fresh NoteDir on the same directory sees everything." |
| 2 | next_id 里存什么格式？ | "Your call. Only NoteDir reads it." |
| 2 | 编号可以跳吗？ | "Yes. Gaps are fine, reuse is not." |
| 3 | 不传 arguments 怎么办？ | "Treat it as an empty object." |
| 3 | 未知工具算协议错误吗？ | "Not in this server. It's a tool error, so the model sees the message and can pick a real tool." |
| 3 | limit 传 true 呢？ | "A boolean isn't an integer. Reject it. The tests don't cover it." |
| 3 | principal 是谁？ | "Whoever the transport says: the principal argument to handle(). Never clientInfo." |
| 3 | 示例笔记谁能删？ | "Nobody. They have no owner." |
| 4 | 最后一行没有换行怎么办？ | "Handle it once the input ends." |
| 4 | 要支持 JSON-RPC batch 吗？ | "No. An array gets -32600 with a null id." |
| 4 | stderr 写什么格式？ | "Anything readable. One line per bad input line is plenty." |
| 4 | 单独一个 `\r` 算换行吗？ | "No. Only \n ends a message. A \r right before it is JSON whitespace. The tests don't send a lone \r." |
| 5 | 要等 notifications/initialized 才处理 legacy 请求吗？ | "No. A successful initialize is enough here." |
| 5 | initialize 要的版本我们不支持？ | "Answer with 2025-11-25 anyway. The client decides whether it can live with that." |
| 5 | 同一条连接第二次 initialize？ | "Replace the old handshake. The tests don't cover it." |
| 5 | 没握过手的连接也会调 close() 吗？ | "Yes. The transport calls it for every connection that ends, modern ones included." |

## 每关：要看什么、提示、追问

### Part 1 修请求校验和结果字段（目标 10 分钟）

一个测试里叠了 5 个缺陷和 3 个护栏：

1. `note_id_from_uri` 用了 `str.lstrip("notes://")`。lstrip 去掉的是一组字符，不是前缀，`notes://note-4` 会变成 `-4`。错误在两层调用之外报出来：测试看到 resources/read 返回 -32602 Resource not found，而那条笔记刚刚建好。
2. `complete()` 的 `cache_scope` 默认值写成了 "public"，和 docstring 写的 "private" 不一致。resources/read 没传 scope，用户的笔记就成了 public。只在 resources/read 里补一个 `cache_scope="private"` 也能过，但默认值仍然和 docstring 矛盾，下一个忘了传 scope 的 handler 又会公开缓存，算凑测试。
3. `handle_prompts_get` 照抄了 prompts/list 的写法，带上了 ttlMs 和 cacheScope。课里说 prompts/get 的结果是 complete，但它不是要带缓存提示的结果。
4. `valid_request_id` 用 `isinstance(value, (int, str))`：bool 是 int 的子类，True 会被当成合法 id 照样回显；Python 的 int 没有上限，2**53 也会被接受，而 TS 版用 `Number.isSafeInteger` 拒绝它。这个 helper 同时决定校验结果和错误响应里回显的 id，只在 validate_request 里内联修一处的话，错误响应仍然回显 True。
5. `MemoryNotes.create` 每次扫一遍所有 id 求最大值，7000 次创建要 1.5 秒左右。它还有第二个问题：删掉最新的一条以后，下一条会复用它的 id，和 docstring 不一致。
6. 护栏一：改成 `len(notes) + 1` 很快，但删过一条以后，新 id 会撞上一条还在的笔记并把它覆盖；删除时重新计算最大值也会复用 id。测试删掉中间一条和最新一条，再建两条，新 id 不能是发过的任何一个。
7. 护栏二：tools/list 的 cacheScope 必须仍然是 public。“把所有可缓存结果都改成 private” 这种一刀切的修法过不了。
8. 护栏三：合法 id 的错误响应要带回这个 id。只在 validate_request 里内联修 id 校验，再把 `handle` 里的错误 id 一律改成 null，True 那条断言能过，但正常请求的错误也丢了 id，客户端没法把错误对回请求。测试读一条不存在的笔记，要求 -32602 的响应带着原来的 id。

看什么：是不是先打印错误响应、顺着 handler 往下找；会不会在 REPL 里试一下 `"notes://note-4".lstrip("notes://")`；每改一处就重跑。

提示：
- H1："The note exists. What id does resources/read actually look up?"
- H2："Print note_id_from_uri('notes://note-4')."
- H3：直接指出 lstrip 去掉的是一组字符。

追问：
- "Why must a note id never be reused?"（客户端按 URI 缓存 resources/read 的结果，cacheScope 是 private 也照样缓存；notes_create 返回的嵌入资源也带着 URI。id 复用以后，缓存和日志里的旧 URI 会指向另一条笔记）
- "Why ±(2^53 − 1), when Python ints have no limit?"（TS 版把 id 存成 JavaScript number，超过 2^53 就丢精度，没法原样回显；两个实现必须接受同一组 id）
- "What does the TypeScript port do with an id of 5.0?"（JSON.parse 得到 5，`Number.isSafeInteger(5)` 为真，照样接受；Python 的 json 读成 float，被拒绝。这种差异只有一份同时驱动两种实现的一致性语料才能发现）
- "Why is tools/list public but resources/read private?"（工具定义对所有人都一样；笔记是用户数据，共享缓存不能跨授权上下文复用）

### Part 2 笔记目录（目标 12 分钟）

坑：
- 文本模式读回：`read_text()` 默认按 universal newlines 读，会把 `\r\n` 和单独的 `\r` 都变成 `\n`。Python 3.12 的 `Path.read_text` 还没有 newline 参数，要用 `read_bytes().decode("utf-8")` 或 `open(..., newline="")`。macOS 和 Linux 上文本模式写入不改换行，所以这里只有读的一侧会挂；Windows 上写入也会把 `\n` 变成 `\r\n`。
- `strip()` 或 `rstrip("\n")` 会吞掉行尾空格、首尾空行和结尾换行，标题两边的空格也一样。
- `print(body, file=f)` 会多写一个换行，`utf-8-sig` 会在文件开头写 BOM。磁盘上的字节必须正好是正文的 UTF-8 编码。
- 空正文也要有文件。先 `if body:` 再写，读回时就是 FileNotFoundError。
- owner 为 None 的笔记，存成 "" 或 "None" 都不对。课里 `str(arguments.get("tag", ""))` 把 None 存成 "None" 是同一类问题。JSON 的 null 能原样读回。
- 计数器要持久化，而且不能在打开时用“磁盘上最大的编号 + 1”重建：删掉最新的一条再重开，就会把它的编号再发一次。
- “oldest first” 要按编号的数值排。`sorted(glob(...))` 会把 note-10 排在 note-2 前面。
- 不存在的 id 要报 KeyError。直接 `open()` 报的是 FileNotFoundError，`pytest.raises(KeyError)` 不认。
- delete 要把正文和元数据两个文件都删掉。只删正文，重开后 `all()` 会读到半条笔记；只删元数据，笔记看起来没了，正文却还留在磁盘上。测试会检查 note-3 的文件一个都不剩。
- 最后一段是端到端检查：NotesServer 换上 NoteDir 以后，resources/read 读出的正文和写进去的完全一样。Part 1 的 lstrip 没修的话，这里也会挂。

追问：
- "The process dies between bumping the counter and writing the note. What happens? What about the other order?"（先写计数器：丢一个编号，留下空号；先写笔记：重启后同一个编号会再发一次，把那条笔记覆盖掉）
- "It dies after the body file but before the metadata file?"（留下一个孤立的 .body，`all()` 按 .json 枚举，看不到它；要更稳就先写临时文件再 rename，用元数据文件当提交标记）
- "Why not sort by file mtime?"（复制、备份恢复都会改 mtime，同一时刻建的文件还会并列；编号才是可靠的顺序）
- "Two server processes share one notes directory?"（两个进程会抢计数器，可能拿到同一个编号；要么加文件锁，要么只允许一个写者）
- "resources/read gets notes://../other/note-1. What does NoteDir read?"（直接拿 id 拼路径的话，会读到 root 外面的文件；参考实现先按 `note-<n>` 的格式校验 id。测试没有覆盖，路径穿越在第 11、13 课考）

### Part 3 tools/call 的两层错误和删除授权（目标 12 分钟）

坑：
- arguments 不是对象（列表、字符串、null），是 tools/call 自己的参数错了，要 -32602。省略 arguments 按空对象处理（TS 版要求必须有，这里不要求）。
- 违反 inputSchema 的参数是工具错误：返回 `isError: true`，消息里写出是哪个参数，模型才能改。抛 -32602 过不了。
- minimum 和 maximum 都是闭区间：limit 为 1 和 50 要能用，0 和 51 要拒绝。
- 类型要查。不查的话，`{"query": 7}` 会在执行器里 `query.lower()` 抛 AttributeError，变成 -32603。
- schema 里没列出的参数要忽略，不能报错。
- 未知工具：本课的代码和测试都把它当工具错误，这里照这个约定。课里的代码讲解指出它和讲义的分类规则有出入，候选人能提出来是加分项。
- 授权在执行器里做，主体是传输层传进来的 principal。clientInfo 是自报的：测试里 bob 带着 `clientInfo.name = "alice"` 来删 alice 的笔记，必须拒绝。
- 没有 owner 的示例笔记谁都不能删。只写 `note.owner != principal` 的话，两边都是 None 时条件不成立，匿名调用者就能删掉它们。只给匿名调用者打补丁（principal 为 None 就拒绝，否则只在笔记有 owner 时比较）也不对，登录的 alice 又能删了；测试让 alice 删 note-2，同样要拒绝。
- 先查权限再删。先删后查也会返回 isError，但笔记已经没了。
- 删除不存在的笔记要转成 ToolError，KeyError 漏出去就是 -32603。
- 执行器里的意外异常（测试里是一个带内部路径的 OSError）要变成 -32603，响应里不能出现这个路径，细节要进 server.log。最常见的错法是 `except Exception` 一把转成 isError，把路径直接交给模型；其次是自己抛 -32603 却把异常文本放进 data，或者吞掉异常不记日志。

追问：
- "destructiveHint is true. What does the host do with it, and what does the server still have to do?"（host 用它弹确认框、调整展示；即使 host 不弹，server 也要在执行器里拦住）
- "Now that notes_delete exists, can tools/list stay public?"（所有人看到的工具列表一样就可以；如果按权限过滤列表，就必须改成 private）
- "Should limit: true be accepted?"（不应该。JSON 的 true 是 boolean，而 Python 里 `isinstance(True, int)` 为真，要写 `type(value) is int`。测试没有覆盖）
- "Where does the principal come from on stdio? Over HTTP?"（stdio 是启动进程的本地用户或注入的凭证；HTTP 是校验过的 access token，见第 16、18 课）
- "The client gets -32603 with no detail. How does support find the cause?"（在 data 里放一个随机的 incident id，同一个 id 写进日志）

### Part 4 stdio 服务循环（目标 13 分钟）

坑：
- 在字节层面按 `\n` 切行，整行到齐后再按 UTF-8 解码。逐块解码会在多字节字符被切开时报 UnicodeDecodeError，测试有 1 字节一块的切法。
- 用 `str.splitlines()` 切行也会挂：它还会在 U+2028 这类字符上断开，而测试里有一个 id 带着原始的 U+2028。stdio 的分隔符只有 `\n`。
- 一块里可能有好几行，要循环处理完，不能只找第一个换行。
- 空块不是输入结束。`async for` 结束才是；见到 `b""` 就 break，后面的消息全丢。
- 最后一行没有换行，输入结束时也要处理。本课的 Python 版逐行迭代 stdin，TS 版用 readline，都会处理这一行。
- 只有空白的行跳过，判断前要先 strip。测试里有一行是空格加制表符，还有一行以 `\r\n` 结尾。
- 不是合法 UTF-8 的行也是 -32700。只捕获 `json.JSONDecodeError` 的话，UnicodeDecodeError 会让循环崩掉；用 `errors="replace"` 解码，坏行又会被当成正常请求处理。
- JSON 数组、数字这类非对象是 -32600，不能交给 server.handle。
- 每个响应写成一行紧凑 JSON，立刻 flush。测试的客户端每发一行，就检查上一行的响应有没有 flush；先读完全部输入，或者最后才 flush，都会挂。测试的 StdioServer 还记下每个请求到达时已经 flush 了几行响应：一块里的几行先全部处理、再统一写出，或者每块只 flush 一次，也会挂。`indent=2` 会把一个响应写成好几行。
- 诊断写 stderr。写到 stdout 会破坏客户端的解析，一点都不写又过不了 stderr 的断言。
- 调用 server.handle 时要带上传输层的 principal。

追问：
- "Why must stdout carry nothing but JSON-RPC?"（客户端把每一行都当消息解析，一行调试输出就会让它报错或断开）
- "Why flush every response?"（stdout 接管道时是块缓冲，不 flush 的话客户端会一直等）
- "A client sends a 2 GB line with no newline. What happens?"（pending 无限增长；要限制单行长度，超长就回 -32700 或断开）
- "One tools/call takes ten seconds. What happens to the lines behind it?"（这个循环是串行的，后面的请求都得等；把 handle 放进线程池可以并发，但响应顺序和背压要重新设计）
- "Is the process lifetime a session?"（不是。课里说进程寿命是传输的寿命，不是现代 MCP 会话）
- "Why not bytes.splitlines()?"（测试能过，但它把单独的 `\r` 也当成行尾，而 JSON 允许 `\r` 作为空白，一条消息会被切成两半。课里的 Python 版逐行读 stdin，在 macOS 和 Linux 上只认 `\n`；TS 版用 readline，会在单独的 `\r` 上断行，两个实现在这里并不一致）

### Part 5 双时代连接（目标 13 分钟）

坑：
- 判断顺序：先看有没有现代 `_meta`，再看是不是 initialize，最后才看这条连接有没有握手。先判断 method 是不是 initialize，带现代 `_meta` 的 initialize 就会走进 legacy 握手；它应该交给现代核心，得到 -32601，因为现代 MCP 没有 initialize。
- 先看连接状态，做过握手的连接上的现代请求就会走进 legacy 适配器。
- 现代请求的判定是“带了任意一个现代 key”。只带版本、或者只带 capabilities 的请求都是坏掉的现代请求，交给现代核心报 -32602，既不能当成 legacy，也不能拿握手时声明的 capabilities 补上（课里：Never fill missing fields from a previous call）。只认版本 key 的写法，会把只带 capabilities 的请求送进 legacy 适配器。
- 只看有没有 `_meta` 也不对。2025-11-25 的请求可以在 `_meta` 里带 progressToken，它仍然是 legacy 请求，测试在握过手的连接上发了一个这样的 tools/list。
- legacy 结果要去掉 resultType、ttlMs、cacheScope 和 `_meta` 里的 serverInfo，initialize 的结果也一样。只去掉 resultType 不够。
- server/discover 是现代方法，在 legacy 门口要 -32601。
- 握手状态按连接存。用一个全局标志的话，B 连接也会被当成握过手。
- initialize 回答的版本永远是 2025-11-25：不能照抄客户端要的版本，也不要因为版本不同就报错（后者是澄清问题）。
- 参数不完整的 initialize 要报 -32602，而且不能留下状态。先记状态再校验，后面的 legacy 请求就会被放行。
- close() 只忘掉这一条连接。用 `clear()` 会把 D 的握手一起清掉。
- close() 也会用在没握过手的连接上：传输层对每条结束的连接都会调用它，现代连接从来不握手。`del self._handshakes[connection]` 会在 B 上报 KeyError。
- initialize 的三项参数都要校验。测试只拿掉了 capabilities，只查 capabilities 的写法能过，但和 docstring 不一致，看代码时指出来。

追问：
- "Why not one state machine that handles both eras?"（第 06 课：双时代实现不是一个宽松的状态机，而是无状态的现代核心加一个隔离的 legacy 适配器，在两边的解析器运行之前先做一次显式选择）
- "Should legacy requests wait for notifications/initialized?"（这套题里成功的 initialize 就够了；更严格的实现可以在通知到达之前只接受 ping）
- "How do you know when the legacy door can go?"（统计每条连接走的是哪条路径，legacy 流量降到零或者到了弃用期限再删）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读错误响应和 captured stderr、在 REPL 里试、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出 id 复用与缓存、崩溃时的写入顺序、授权主体的来源、背压、legacy 下线 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
