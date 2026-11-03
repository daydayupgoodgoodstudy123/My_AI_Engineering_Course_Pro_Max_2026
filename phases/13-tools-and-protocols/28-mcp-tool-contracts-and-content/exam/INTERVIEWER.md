# 面试官手册：contractkit（13/28）

候选人计时期间不要看。候选人手里只有 README、`contractkit/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 游标能不能解码，看看还剩几页？ | "No. Cursors are opaque. Send back exactly what the server gave you." |
| 1 | 空字符串算不算下一页？ | "Yes. Only a missing or null nextCursor ends the listing." |
| 1 | isError 为 true 的结果还要按 outputSchema 校验吗？ | "Yes. Once a tool publishes an outputSchema, every complete result must carry conforming structuredContent, errors included." |
| 1 | call 里能不能顺手再校验一次被调用工具的 descriptor？ | "You can, as long as calls stay fast. The catalog itself is validated once, at discovery." |
| 1 | 没调过 discover_tools 就 call，要不要自动发现？ | "No. A tool that was never discovered is not admitted." |
| 2 | 能不能把 base64 文本原样存进去？ | "No. The archive keeps the decoded bytes; the layout says so." |
| 2 | meta 的 JSON 用什么分隔符、要不要 ensure_ascii？ | "Any UTF-8 JSON object. Lengths count its bytes." |
| 2 | resource_link 要不要顺手把内容取回来一起存？ | "No. A link is stored as given. Whoever follows it later goes through its own authorization." |
| 2 | base64 末尾的填充位不为零（比如 QR==），算合法吗？ | "It decodes, but we couldn't give it back unchanged. Refuse it." |
| 2 | 内容块里要是有别的字段？ | "Keep every field the block has. The tests use the lesson's fields." |
| 3 | 工具没声明的 Mcp-Param-* 头要不要拒绝？ | "No. Leave them alone. Only recognized names are checked." |
| 3 | 明文就能表示的值被包成了 base64，服务器要拒绝吗？ | "No. Decode it and compare. The tests don't cover it." |
| 3 | 好几个头都不对，报哪一个？ | "The first problem in bindings order. Each test request has one problem." |
| 3 | 头名比较要不要做 Unicode 大小写折叠？ | "Header names are ASCII tokens. lower() is fine here." |
| 3 | body 里的整数超出安全范围，服务器报什么？ | "mismatched. That value has no header form, so no header can match it." |
| 4 | 同一个值隔一会儿又打了一遍，要再发请求吗？ | "Yes, after the pause, with a new id." |
| 4 | 新请求还没回来时，界面上显示什么？ | "Keep showing the last answer you accepted until the newest request's answer arrives." |
| 4 | 服务器回了限流错误怎么办？ | "Treat it like any other error answer. The tests use -32602." |
| 4 | 服务器给的 total 比 values 还少？ | "Show what it reports. The tests don't cover it." |
| 5 | 要不要解析 $ref？ | "No. Judge every annotation where it is written." |
| 5 | default、examples、const 这类数据里出现 x-mcp-header 呢？ | "Anything that isn't a direct inputSchema property is refused; it's fail-closed. The tests don't use data keywords." |
| 5 | access_token 算敏感名吗？ | "Not under this policy: names are matched exactly, ignoring case. Tell me what you would change." |
| 5 | 直接成员的 type 写在 $ref 指向的定义里？ | "Refuse it as a type finding. The annotated node itself must say string, integer or boolean. The tests don't cover it." |
| 5 | 两个头名只差大小写，哪个算重复？ | "The later one in inputSchema.properties order." |
| 5 | 头名不合法或类型不对的属性，它的头名算不算已被占用？ | "No. A header name is taken only by an annotation that passed the name and type checks. The tests don't cover it." |

## 每关：要看什么、提示、追问

### Part 1 修发现与调用（目标 10 分钟）

一个测试里叠了 4 个缺陷和一组护栏：

1. `discover_tools` 用 `if not cursor` 判断结束。服务器第一页之后返回的 nextCursor 是空字符串，客户端就此停下，第二、三页从来没读过。错误不在 `discover_tools` 报出来，而是在 `call` 里：`ContractViolation: tool is not admitted: tag_catalog`。看起来像 descriptor 坏了，其实是客户端没见过它，`client.rejections` 里也没有它。
2. `validate_tool_result` 要求 `structuredContent` 是 dict，数组结果被拒，报 `structuredContent must be a JSON object`，和 docstring 写的“任意 JSON 值”矛盾。改的时候有两个坑：用 `is None` 判断缺失，null 结果会被拒；用 `.get()` 不判断在不在，`["string", "null"]` 的 schema 会把“根本没有 structuredContent”当成 null 放过。要判断的是键在不在。
3. 同一个函数里 `isError` 为 true 就直接返回，跳过了 schema。课里说发布了 outputSchema，错误结果也要给出符合 schema 的 structuredContent；`isError` 只是分类执行结果，不免除输出契约。测试分别检查“错误结果漏了 structuredContent”和“错误结果的 structuredContent 不符合 schema”。
4. `call` 每次都调 `admitted()`，把整个目录重新校验一遍。2000 个工具、167 次调用要 1.1 到 1.6 秒，限值 0.1 秒。docstring 写的是 descriptor 在发现时校验一次。

护栏，防的是“为了提速把校验删了”和“缓存了却不更新”：

- 被拒的 descriptor 仍然不能调用，而且一个请求都不能发出去。`call` 直接在原始目录里按名字找工具，会把 broken_route 发出去。
- 参数照样在发送前按 inputSchema 校验：缺字段、空字符串（minLength）、类型不对、多余字段都要拒，服务器一个 tools/call 都收不到。
- 结果照样在返回前校验：结构化内容按 schema 查，content 不能为空，每个内容块都要过 `validate_content_block`（测试里有一张 data 不是 base64 的 image），带 structuredContent 的结果还要有一个给旧客户端的 text 块。
- 重新发现以后，旧目录里的工具不能再调用，rejections 也只描述最新这一次。“第一次 admitted 的结果永远留着”或者在 `call` 里另存一份缓存，会让下架的工具继续可调用。
- nextCursor 为 null 也是结束；重复的游标在再次发送之前就要拒绝；不是字符串的游标要拒绝；最多 max_pages 页。

只在 `call` 里校验被调用的那一个 descriptor，或者按名字线性查找但不重新校验整个目录，都能过计时（一次调用的成本是微秒级，限值卡的是重新校验整个目录的那种写法）。可以追问规模更大时怎么办。

看什么：拿到 “tool is not admitted” 时，是去改 descriptor，还是先看服务器到底收到了哪几次 tools/list；会不会读 docstring；修计时的时候有没有把参数和结果校验一起删掉。

提示：
- H1："Is tag_catalog's descriptor broken, or did the client never see it?"
- H2："Print the cursors the client sent. What did the server answer after the first page?"
- H3：直接指出 `discover_tools` 里的 `if not cursor`。

追问：
- "Why does the lesson say cursors are opaque? What could a server put in one?"（签名、目录版本、私有状态；客户端解码、递增、比较都可能在服务器换实现时出错）
- "How does route_report report a failure inside its own schema?"（schema 里留出表达失败的字段，比如 `accepted: false`，再加上说明文字和 `isError: true`）
- "The server validates arguments too. Why validate on the client?"（Invoke 这一关属于宿主；在发出去之前就失败；参数还可能被镜像进头部）
- "Two thousand tools now, two hundred thousand later. What else changes in admission?"（按需发现、按服务器分批、descriptor 摘要缓存；参考第 15 课和第 30 课的漂移检测）

### Part 2 内容块容器（目标 12 分钟）

坑：
- `base64.encodebytes` 每 76 个字符插一个换行，末尾还总有一个换行。读回来的 data 不再是标准 base64，`validate_content_block` 会拒绝。只 `strip()` 掉末尾那个也不够，514 字节的图片中间还有换行。
- `urlsafe_b64encode` 用的是 `-` 和 `_`，图片里有 `+` 和 `/` 的地方会变。去掉 `=` 填充也不行。
- 长度按字节算。golden 检查用的是 `"λ"`：一个字符、两个字节。按 `len(str)` 写长度，或者 meta 用 `ensure_ascii=False` 却按字符数写长度（`"raw λ"` 那个链接），都会读错位。
- 长度是 4 字节大端。小端或 2 字节都过不了 golden 检查；70,000 字节的 blob 本来也装不进 2 字节。
- image、audio 和 blob 存的是解码后的字节。测试自己按布局把每条记录读出来比对，把 base64 文本原样存进 body 会挂。
- 规范 base64：`QR==` 和 `AAB=` 能解码，但重新编码得到的是 `QQ==` 和 `AAA=`，存成字节以后就还原不了原文。打包时必须拒绝，data 和 blob 都要查。只查 image 不查 audio、只查 data 不查 blob，都会挂。
- 不能改调用方的块。复制了外层 dict，却直接在嵌套的 `resource` 上 pop，调用方的 text 和 blob 就没了。
- 嵌入资源靠键在不在来区分 text 和 blob。测试里有一个 text 为空字符串的嵌入资源，用真值判断会走进 blob 分支。
- resource_link 原样保存：有 mimeType 就有，没有就没有，不能补成 null，也不能只留 uri 和 name。
- 读的时候要严格：魔数不对、截断、最后一条记录后面多一个字节、未知 tag、text 不是 UTF-8、meta 不是对象、重建的块过不了 `validate_content_block`（比如没有 mimeType 的 image），都要抛 ContractViolation，不能漏出 IndexError、struct.error、UnicodeDecodeError 或 TypeError，也不能悄悄返回少一截的数据。
- meta 要先按 UTF-8 解码再解析。`json.loads` 直接吃 bytes 会按 BOM 自动识别 UTF-16、UTF-32，测试里那条带 BOM 的 UTF-16 meta 就会被当成 `{}` 收下。只捕获 `JSONDecodeError` 也不够，UTF-8 解码失败抛的是 `UnicodeDecodeError`。

追问：
- "Why keep decoded bytes instead of the base64 text?"（小三分之一；base64 只是传输编码。代价是必须能按规范形式重新编码，所以要拒绝非规范输入）
- "A disk flips one bit inside an image. Does your reader notice?"（长度检查只能发现截断；要发现损坏得加校验和，每条记录或整个文件一个）
- "Should the archive follow resource_link and store what it points to?"（不应该。课里说链接只是这次调用返回的引用，跟随时要重新授权；要原子地带走的小证据，用嵌入资源）
- "Where would you enforce size limits?"（课里说 image、audio 要校验媒体类型和大小，嵌入资源现在就要执行负载限制；在打包前按解码后的字节数限制）

### Part 3 参数头（目标 14 分钟）

坑（客户端）：
- 明文的条件是“非空，而且每个字符都在 `!` 到 `~` 之间”。`str.isprintable()` 会放过空格和非 ASCII 字母，`isascii() and isprintable()` 还会放过空字符串。空字符串编码成 `=?base64??=`；DEL（0x7F）不算可见字符。
- 以 `=?base64?` 开头的原值要再编码一次，否则服务器会把它当成编码去解，还原不出原文。
- 不能 strip，也不能做 Unicode 规范化。`"A"` 加组合上圈和预组合的 `"Å"` 是两个不同的值。
- 布尔值是小写的 `true`/`false`，`str(True)` 是 `"True"`。`isinstance(True, int)` 为真，所以 bool 不能当整数放过。整数的安全范围是 ±9007199254740991，两端包含在内；超出就拒绝。float 和数字字符串都不是整数。

坑（服务器）：
- 头名不区分大小写地识别。只差大小写的两个头算重复，完全相同的两个头也算重复。把头放进以小写名为键的 dict，后一个会覆盖前一个。按名字前缀匹配会把 `Mcp-Param-Region-Backup` 也当成 Region。
- `=?base64?=` 的前缀和后缀共用了中间的问号。只看 startswith 和 endswith 的解码器会把它解成空串，而空串的规范编码是 `=?base64??=`。要先检查长度，后缀也必须在。用正则 `=\?base64\?(.*)\?=$` 也不行：`$` 能匹配末尾换行之前的位置，结尾多一个 `\n` 的值会被当成合法哨兵。
- 非规范 base64（`=?base64?QR==?=`）、错误的填充、解出来不是 UTF-8 的字节（`/w==` 是 0xFF），都是 malformed。用 Latin-1 解码会把 0xFF 变成 `ÿ`，正好等于 body。
- 只解码一次。双重编码的哨兵值解一次就是原文。
- 比较要精确：大小写、首尾空格、规范化形式都不能放宽。整数按文本比，`07` 不等于 7；布尔按文本比，`False` 不等于 false。body 里超出安全范围的整数没有头部形式，是 mismatched，不能让 ContractViolation 漏出去。body 值的类型和声明不符（声明 string 的 region 传了 7）同样没有头部形式；按 body 值自己的类型去渲染，`7` 就对上了。
- 通过时的 checked 事件按 bindings 顺序列出规范头名。测试里收到的头是倒序的，按收到的顺序列会挂。
- 拒绝时 HTTP 400、`-32020`，dispatch 一次都不调用。审计只记规范头名和原因，不记值，编码后的值也不记（编码不是加密）。

追问：
- "Why does the lesson encode a value that merely looks like the sentinel?"（否则服务器会把字面文本当成传输语法解码）
- "Why reject unsafe integers instead of sending them?"（JavaScript 写的中间件会按双精度浮点数舍入，网关和源站看到的就不是同一个数）
- "The gateway routes on the header and the origin executes the body. What happens if nobody checks parity?"（网关把请求路由到一个区域或租户，源站却按 body 里的另一个值执行，路由和隔离都被绕开了）
- "A header named Mcp-Param-Key arrives, but its K is the Kelvin sign. What does lower() do with it?"（开尔文符号的 lower() 是 ASCII 的 k，这个头会被当成 Key 识别，而网关按 ASCII 比较时认不出它。HTTP 头名是 ASCII token，不是 token 的名字应该直接拒绝）

### Part 4 补全防抖（目标 12 分钟）

坑：
- 防抖，不是节流：每次按键都重新计时。只从第一次按键算起（节流）会在 379 毫秒时发出 "sta"，测试要求这时什么都没发。首次按键就立刻发也不对。
- 边界是“正好 idle_ms 就发”。用 `>` 会在 380 毫秒时不发。
- 一次停顿只发一个请求，发完要清掉待发的值。每次停顿都要发，哪怕值和最新请求的一样：测试最后打了 pro 又删回 pr，拿最新请求的值去重会少发一个。
- id 从连接的计数器里取，这个测试从 41 开始。自己另起一个计数器会和同一连接上的其他请求撞号。同一个值隔一段时间再打一遍，也要用新 id。所有请求共用一个 id，旧答案就和新答案分不开了。
- 每个请求都要带完整的 `_meta`（make_request）。帧是 JSON 文本，不是 dict；测试用 `json.loads` 解析每一帧。
- 只认最新请求的答案。旧请求的答案不管是先到还是后到都丢掉，没发过的 id 也丢掉。“比当前显示的更新就接受”会在新请求的答案到达之前，先把旧请求的答案显示出来。用一张待答表 pop 答案，重复到达的旧答案会报 KeyError。
- 最多显示 100 个值，按服务器给的顺序。服务器说 hasMore，或者客户端截掉了一部分，hasMore 都是 true（课里示例服务器的 hasMore 写死为 false）。截掉指的是超过 100 个；正好 100 个、服务器说 false，就是 false，写成 `>=` 会错。total 只用服务器给的，没给就是 None，不能用 values 的个数代替。
- 最新请求的错误答案把建议清空，旧请求的错误答案照样丢掉。

追问：
- "Why does the lesson list debouncing under authorization?"（补全会泄露普通列表方法保护的名字；请求越少，限流和审计越容易做；防抖是客户端这一半，服务器还要限流）
- "Throttle or debounce here?"（输入框要的是停下来以后的那个值，所以是防抖；节流适合持续的进度类请求）
- "The newest request is still in flight and the user keeps typing. Can the box do better?"（可以先按新前缀在本地过滤已显示的值，但不能凭空造值；第 29 课讲取消和流量控制）
- "The analyst sees production in the list. Whose bug is it?"（服务器的。授权要和被引用的 prompt 或资源用同一套边界，客户端没法替服务器判断）

### Part 5 注解位置审计（目标 12 分钟）

坑：
- 遍历整棵树，不是只认识几个关键字。只走 properties、items、oneOf、$defs 的写法会漏掉 prefixItems、additionalProperties、not、旧的 definitions，以及 inputSchema 根本身上的注解。
- 不要跟着 $ref 走。tree 定义引用了它自己，跟着走会无限递归；同一个定义被 home 和 work 各引用一次，跟着走会报两次，还会把解析后的节点当成直接成员放过；没有被引用的定义（spare、legacy）也要报。课里说解析引用不会让被引用的节点变成顶层属性。
- 直接成员就是 `/inputSchema/properties/<名字>` 这一层。“父键是 properties”或者“在 inputSchema.properties 下面就算”都会放过嵌套对象里的注解。
- outputSchema 里的注解一律是 output，直接属性也不例外。
- type 必须恰好是 string、integer、boolean 之一。number 拒绝；没写 type 拒绝；`["string", "null"]` 拒绝，而且拿列表去 frozenset 里查会报 TypeError，要先判断是不是字符串。
- 头名用 `HEADER_TOKEN.fullmatch`。`match` 会放过 `Region\r\nX-Injected: 1` 的前缀，`$` 会放过结尾的换行。头名是 7 这种非字符串时不能让 re 报 TypeError。
- 重复不区分大小写，报的是 properties 顺序里后出现的那个。
- 敏感名要同时看属性名和头名，都不区分大小写，按整个名字比较。子串匹配会把 tokenizer 也拒掉。
- 每个注解只给一条 finding，按 docstring 的顺序取第一条。测试里 password 用了和 region 重复的头名，报 duplicate 不报 sensitive；secret 的类型是 number，报 type；token 的头名带空格，报 name。先查敏感名、或者先查类型再查头名，都会挂。
- 路径是 JSON Pointer：先把 `~` 写成 `~0`，再把 `/` 写成 `~1`，顺序反了 `geo/zone` 会变成 `geo~01zone`。数组下标是数字段，不是 `[1]`。
- 结果按路径排序。

追问：
- "Why is the placement rule syntactic and fail-closed?"（不同客户端、网关对 oneOf、$ref 的理解不一样；只看写在哪里，所有人得到同一个结论）
- "How would you tell the author which properties pull in the hidden annotation?"（反向解析 $ref，建引用图，做环检测，报告每个定义被哪些属性引用）
- "Exact matching misses access_token and Api-Key. What would you do?"（规范化以后做子串匹配会误伤 author_name；更稳的是白名单，只允许登记过的路由字段镜像）
- "Where does this audit run, and what does Part 1's client do with a finding?"（在发现之后的准入阶段；有 finding 的 descriptor 记入 rejections，其余工具照常准入）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看服务器实际收到了什么、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出游标、规范编码、解析差异、授权边界、规模 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
