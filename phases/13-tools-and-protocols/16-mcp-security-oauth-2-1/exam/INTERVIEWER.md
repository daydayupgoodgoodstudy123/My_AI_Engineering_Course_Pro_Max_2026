# 面试官手册：oauthflow（13/16）

候选人计时期间不要看。候选人手里只有 README、`oauthflow/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 告诉候选人：授权服务器、MCP 服务器、DNS 和 HTTPS 都是测试文件里的假实现，读它们是正当的。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 服务器声明了 `authorization_response_iss_parameter_supported`，响应里却没有 `iss`，要拒绝吗？ | "Not in this session. A server that advertises it always sends it here. A present iss must match exactly; an absent one is fine." |
| 1 | 元数据里列了好几个授权服务器，用哪个？ | "The first one. The tests only ever list one." |
| 1 | 发现结果能一直缓存吗？ | "For this session, yes: once per resource for the life of the client. Tell me when you'd refresh it." |
| 2 | 要考虑两个进程同时写 vault 吗？ | "No. One process at a time, but a vault opened later must see everything already written." |
| 2 | 用过的刷新 token 可以明文存吗？ | "Your call. The tests only check that reuse is still caught after a reopen." |
| 2 | 服务器刷新时把同一个刷新 token 又发回来了呢？ | "Then nothing rotated. It stays the current one." |
| 2 | 文件权限不对的旧 vault 要拒绝加载吗？ | "Not required here. Say what you'd do in production." |
| 3 | 403 挑战里没有 `scope` 怎么办？ | "Raise the McpError. The tests don't send one." |
| 3 | 401 时要不要先用刷新 token？ | "No refresh tokens in this part. Run a new flow for the scope the token had." |
| 3 | 存过 DCR 客户端的服务器后来支持 CIMD 了，用哪个？ | "CIMD. The priority order applies on every call." |
| 3 | 预注册的客户端也要看 `allow_dcr` 吗？ | "No. allow_dcr only gates DCR." |
| 4 | 同一个重定向来了两次？ | "Only the first one counts. The copy matches no open flow." |
| 4 | 结果要按重定向到达的顺序输出吗？ | "No. Each Outcome as soon as it is known." |
| 4 | `iss` 不对的那次重定向之后，流程还要留着等真的回调吗？ | "No. The first redirect that matches a state closes that flow, whatever happens next." |
| 4 | 调用方不再读 serve 了，还在进行的换 token 请求怎么办？ | "Cancel them. The tests don't cover it." |
| 5 | 除了 443 的端口可以抓吗？ | "Yes. The rules are about addresses, not ports." |
| 5 | DNS 结果能在几跳之间复用吗？ | "No. Every hop resolves its host again." |
| 5 | 响应头里 Content-Length 已经超过上限呢？ | "You may refuse early. The tests only send chunked bodies." |
| 5 | IPv4 映射的 IPv6 地址（`::ffff:127.0.0.1`）？ | "Refuse them. The tests don't send any." |

## 每关：要看什么、提示、追问

### Part 1 修发现和授权码流程（目标 10 分钟）

一个测试里叠了 4 个缺陷和几道护栏：

1. `protected_resource_metadata_url` 用 `urljoin(resource, "/.well-known/oauth-protected-resource")`。第二个参数是绝对路径，会把 `/mcp` 整个换掉。假网络在根路径上没有文档，第一个错误是 `HttpError: 404 for https://notes.example.com/.well-known/oauth-protected-resource`。讲义原话：保留资源路径，否则会拿到同一 origin 上另一个资源的元数据。
2. `s256` 用 `base64.urlsafe_b64encode` 却没去掉 `=` 填充。授权端点照单全收，错误要到第 6 步换 token 时才出现：`TokenError: invalid_grant: PKCE verification failed`。traceback 走的是 `login → net.token → FakeAuthServer.token`，里面没有 `pkce.py`。要顺着“token 端点重算了什么、和谁比”往回找到第 2 步。
3. `check_response` 把 `iss` 和记录的 issuer 都做了 `rstrip("/")` 和 `lower()` 再比，`https://auth.example.com/`、`https://AUTH.example.com` 都能混过去。讲义和 RFC 9207 要求逐字比较。
4. `McpClient.discovery` 每次都重新抓受保护资源元数据和授权服务器元数据。假网络每次抓取 4 毫秒，200 次调用就是 400 次抓取，约 2 秒。按资源缓存以后约 1 毫秒。
5. 护栏：
   - 按 origin 缓存会被抓住：`https://notes.example.com/archive/mcp` 和 `/mcp` 同 origin，但授权服务器不同。用了 `/archive/mcp` 这种两段路径，“只保留最后一段路径”的写法也会拿错文档。
   - 伪造的 `iss` 有四个：尾斜杠、大写主机名、`:443` 默认端口、`%2E` 百分号编码。按 URL 规范化或者先 `unquote` 再比，都过不了。还有一个空字符串：它也算出现了，`if iss and iss != ...` 会把它当成没有 `iss` 放过去。
   - 归档服务器从不发 `iss`：“没有 `iss` 就拒绝”会挂。它也没有声明 `authorization_response_iss_parameter_supported`，但测试会伪造一个 `iss` 发过来：“只在声明了才检查”也会挂。
   - 改成 `plain` 来绕开 PKCE，会被假授权服务器直接拒绝（讲义：Require S256）。

看什么：拿到 404 时是不是先看 URL 本身；拿到 `PKCE verification failed` 时是先读假授权服务器的 `token()`，还是乱改客户端；会不会用测试里的 RFC 7636 附录 B 向量自己验证 `s256`；每改一处就重跑。

提示：
- H1："The token endpoint recomputes something from the verifier. What, and what does it compare it with?"
- H2："Print the challenge you send and challenge_of(verifier) from the test, side by side."
- H3：直接指出 `s256` 返回值末尾的 `=`。

追问：
- "A native client has no secret. What exactly does PKCE stop?"（授权码可能被别的应用截获，比如注册了同一个回环端口或自定义 scheme 的应用；没有 verifier，截到的码换不了 token）
- "Why is plain not good enough?"（plain 的 challenge 就是 verifier 本身，它走的正是可能被截获的前端通道）
- "Why compare iss exactly instead of normalizing?"（各方的规范化规则不一样，攻击者正好利用这种差异做混淆；逐字比较没有歧义）
- "Your discovery cache never expires. When should it?"（按 HTTP 缓存头；遇到 401 且挑战里的 `resource_metadata` 指向别处时重新发现，但要按信任策略重新评估，不能盲目跟随）
- "The metadata now lists a different authorization server. What do you do with the old tokens?"（重新评估信任，旧 issuer 签发的东西一样都不给新 issuer，这就是 Part 2）

### Part 2 按 issuer 隔离的凭据库（目标 10 分钟）

坑：
- 权限：umask 是 022，用 `open()` 或 `write_text` 新建的文件是 0644，模式断言会挂。先写再 `chmod`，会撞上测试替换的 `os.chmod`，它报“the vault file is private from the moment it is created, never chmod-ed later”。要在创建时就给 0600：`os.open(path, flags, 0o600)`，或者 `tempfile.mkstemp`（它本来就以 0600 创建），再 `os.replace`。
- issuer 精确分键：`rstrip("/")` 会把 `https://auth-one.example` 和 `https://auth-one.example/` 合成一个，后写的覆盖先写的；转小写会让 `https://AUTH-ONE.example` 查到记录。
- JSON 的键只能是字符串，`(issuer, resource)` 不能直接当键。按 issuer 再按 resource 嵌套两层最自然。
- token 只按 resource 存，带尾斜杠的 issuer 那条会覆盖掉另一条；查不到时“退而求其次拿同一个 resource 的任意 token”，资源换了 issuer 以后就会把旧 issuer 的 token 交出去。只按 issuer 存，同一 issuer 下的两个资源会互相覆盖。
- 原样读回：scope 字符串保持服务器给的顺序（`notes:write notes:read`），不能排序；`expires_at` 是 int；没有刷新 token 时读回 None。
- 每个方法返回前就写盘。测试从不调用 close，直接再开一个 vault 读。
- 轮换：
  - 用过的刷新 token 要记进文件，重新打开后再出现才认得出是重用。
  - 重用时抛 RefreshReuse，并且只删掉这一个 `(issuer, resource)` 的记录。
  - 既不是当前值也没用过的值抛 ValueError。测试用的是另一个 issuer 的刷新 token，在所有记录里找刷新 token 的写法会把它当成合法的。
  - 服务器没有发新的刷新 token 时，当前这个继续有效，不能标成已用，也不能存成 None。
  - 服务器把同一个刷新 token 原样发回来，也没有轮换：不能标成已用。测试接着拿它再轮换一次，标成已用的写法会在这里抛 RefreshReuse。

追问：
- "Why does chmod after the write leave a hole?"（别的用户可以在那一瞬间打开文件并保留句柄，之后改权限也收不回这个句柄）
- "Two processes refresh at the same moment?"（两边都拿 r1，先到的轮换成 r2，后到的再交 r1，授权服务器会当成重用，把整条链吊销。办法是刷新前加文件锁再重新读 vault，或者只让一个进程负责刷新）
- "Why remember used refresh tokens on the client at all?"（另一个进程拿着旧副本时能当场认出来；也避免把明知作废的 token 发出去）
- "Would you keep them in clear?"（不，存 SHA-256 指纹就够了；参考答案就是这么做的）
- "The lesson says encrypted records. Encrypted with what key?"（系统钥匙串或 DPAPI；不要把密钥放在 vault 旁边）
- "What happens if the process dies in the middle of a write?"（原地覆盖会留下半个 JSON；先写临时文件、fsync、再 `os.replace`）

### Part 3 增量授权与注册顺序（目标 14 分钟）

坑：
- 解析 `WWW-Authenticate`：
  - quoted-string 里有逗号和 `\"`，也有不带引号的 `error=insufficient_scope`。
  - 一个头里有两个挑战，Basic 在前，Basic 的 realm 不能混进来。
  - scheme 不区分大小写（`bearer`），参数值保留大小写。
  - Bearer 后面还跟着别的挑战时（`Bearer error="invalid_token", Basic realm="notes"`），Bearer 的参数到下一个 scheme 为止。先找到 `Bearer` 这个词、再对后面整段跑正则的写法，会把 Basic 的 realm 收进来。
  - 按逗号切、用 `(\w+)="([^"]*)"` 正则，都会挂。
- `step_up_scope`：并集，去重，排序。`"".split(" ")` 得到 `[""]`，会多出一个空 scope。直接拼 set 的顺序是随机的，测试用 11 个 scope 来抓。
- 现有 scope 要用服务器实际批下来的。假授权服务器在请求 `notes:read` 时会多给 `notes:write`；拿“自己请求过什么”去合并，就丢了 write。这一点在 Part 1 的 `store` 里已经做对了，这一关只要用 `TokenRecord.scope`。
- 挑战里的 scope 不在 `scopes_supported` 里（`notes:admin`）也要照样请求，讲义说挑战是权威的。
- 每次调用最多升级一次：`notes:purge` 服务器永远不批，升级后重试还是 403，要抛 McpError，不能再来一轮。
- 没有挑战的 403（`notes.locked`，策略拒绝）不是升级。
- 401 和 403 走不同分支：401 说明 token 已经不被接受，先删掉再重新授权，用的还是原来的 scope；403 升级时用户拒绝了，原来的 token 要留着，它对已批准的操作还有效。
- 注册顺序，见 `Registrar` 的 docstring：
  - 精确 issuer 的预注册最先；带尾斜杠的 issuer 用不上它。
  - 声明支持 CIMD 时用 CIMD，哪怕以前在这个 issuer 上注册过 DCR。
  - DCR 只在 `allow_dcr` 为真且有 `registration_endpoint` 时用。每个 issuer 只注册一次，带着 `registration_access_token` 存进 vault，重启后还能复用，也从不交给别的 issuer。
  - 都不行就抛 NeedClientInfo。
- CIMD 被授权服务器拒绝（`invalid_client`）时，`login` 要把错误抛出来。即使服务器也开着 DCR，也不能偷偷改走 DCR。

看什么：解析器是先想清楚语法再写，还是边试边打补丁；会不会去看假资源服务器到底返回什么头；会不会把注册顺序先写成注释或表格再动手。

追问：
- "Why not ask for every scope up front?"（最小权限；一次要一大堆权限，用户会习惯性点同意。讲义：只要眼下需要的 scope）
- "The challenge asks for a scope you've never seen. Follow it blindly?"（挑战对当前操作是权威的，但要把新权限讲给用户、拿到同意再走流程；危险的 scope 更不能静默升级）
- "The challenge's resource_metadata points somewhere else?"（讲义：不要跟着未经验证的错误响应去发现 issuer。只有和已经为这个资源发现的元数据 URL 一致才用）
- "Why is silently falling back to DCR dangerous?"（会把一次安全校验失败变成一条更弱的注册路径；能让 CIMD 抓取失败的人，就能逼客户端去用 DCR）
- "What does application_type change for DCR?"（回环重定向要声明 native；不写的话 OpenID Connect 实现可能默认 web，合法的回环重定向会被拒。`dcr_metadata` 已经写好）
- "After the step-up you retry. What changes in the request?"（新的 token，新的 JSON-RPC id；这在第 08、11 课考过）

### Part 4 回环重定向与表单编码（目标 14 分钟）

坑：
- 授权 URL：用 `urlencode`（空格变 `+`）。归档服务器的授权端点本身带着 `?tenant=notes`，要接在后面，不能丢，也不能再加一个 `?`。
- 输出格式由测试的解析代码决定：每个换 token 请求都用 `parse_qs(body.decode("ascii"), strict_parsing=True)` 读，Content-Type 必须是 `application/x-www-form-urlencoded`，字段恰好是 grant_type、code、redirect_uri、client_id、code_verifier、resource 这六个。授权码里故意放了 `+`、`/`、`=`、`&`、`%`、`~` 和空格：手拼 `k=v` 会挂，忘了 `.encode()` 发 str 也会挂。
- 回调参数必须用 `parse_qs` 解码。`iss` 到达时是 `https%3A%2F%2F...`，手工按 `&` 和 `=` 切开、不解码，会把正确的 issuer 判成不匹配。
- 不能在 serve 里直接 await 换 token：测试把 notes 的 token 端点卡住，直到归档那条结果出来才放行。顺序 await 会在第一个断言处超时。可行的写法是 `asyncio.wait(..., return_when=FIRST_COMPLETED)`，同时等“下一个重定向”和所有换 token 任务；或者开一个读任务配一个队列。
- 状态一匹配就关闭流程（`pop`），而且要在任何 await 之前。notes 的换 token 还卡着时，同一个重定向又来一次，要立刻得到 unknown_state，不能发第二个 POST。
- 被拒绝的重定向也会关闭流程。`iss` 不对的那个流程，测试随后把它的真回调发过来；过期的那个，测试把同一个回调再发一次。两次都要得到 unknown_state。只在发 token 请求之前才 `pop` 的写法，会让那个真回调去换 token，卡在被挡住的 notes 端点上，1 秒后报“the first redirect that matches a flow closes it”。
- token 端点答复错误时，结果是 denied，带服务器的 error 和 error_description。测试拿一个归档服务器从没发过的 code 去换，期望 `Outcome("denied", ARCHIVE, "invalid_grant", "unknown or already used code")`。把错误答复直接交给 `client.store` 会抛 TokenError，serve 整个中断。
- 先验 `iss` 再看 `error`。伪造的重定向带的是 `iss=https://login.archive.example`，这是客户端也在用的真实 issuer，典型的混淆攻击。它的 error_description 里还有一个钓鱼链接。结果只能是 issuer_mismatch，里面不能出现这段文字。只拿 `iss` 和“已知 issuer 集合”比，也会挂。
- 过期用注入的 clock：一个流程在 t=0 打开，回调在 t=700 到达，ttl 是 600。用 `time.monotonic()` 记开始时间，就永远不会过期。
- 来源结束以后，serve 要等还在进行的换 token 请求做完再结束。测试是先结束来源、再放行 notes 的 token 端点的。
- serve 写成普通协程（里面没有 yield）时，报的是 `'coroutine' object has no attribute '__anext__'`。要能看出这里需要异步生成器。

看什么：动手前有没有想清楚“谁在等谁”；有没有先跑通一条流程再加并发；能不能说清楚为什么 pop 要放在 await 之前。

追问：
- "Why must iss be checked before error and error_description?"（否则攻击者的文字会以我们授权服务器的名义显示给用户，钓鱼正是靠这个）
- "state versus PKCE: what does each stop?"（state 防 CSRF 和登录注入，回调要能对上我们发起的流程；PKCE 防授权码被截获后拿去换 token）
- "The consumer stops reading mid-way. What leaks?"（还在进行的换 token 任务；在 finally 里 cancel，参考答案就这么做）
- "The token POST times out. Retry it?"（授权码只能用一次，而且很快过期；重试可能重复兑换，也可能已经兑换过。安全的做法是开一个新流程）
- "Several redirects for different flows arrive at once and one token endpoint is slow. How many concurrent exchanges would you allow?"（按 issuer 限流，加总上限；超时以后取消）

### Part 5 重定向链与 SSRF 规则（目标 12 分钟）

坑：
- `public_address`：只用 `not is_private` 会放过 100.64.0.0/10；只用 `is_global` 会放过组播（`224.0.0.251` 的 `is_global` 是 True）。
- 每一跳都要检查：第二跳才指向 `https://127.0.0.1/admin.json`，或者指向一个解析到 169.254.169.254 的名字。
- DNS 应答里每个地址都要合格：`dual.example.com` 一公一私。解析不到任何地址也要 FetchBlocked：`all([])` 是 True，接着取 `addresses[0]` 会抛 IndexError。
- 每一跳都重新解析，不能按主机名缓存：`rebind.example.com` 第二次解析就变成 10.0.0.7。连接时用刚检查过的地址，不能再解析一次：`flip.example.com` 第二次解析是 127.0.0.1，测试会数解析次数，并检查连接到的是哪个地址。
- 只认 https，重定向目标也一样：`down.example.com` 用 301 跳到 http。
- 最多 3 次重定向：第 4 次重定向时拒绝，总共只发 4 个请求。重定向回已经访问过的 URL 是环，立刻拒绝，`loop.example.com` 只发 2 个请求。
- 相对的 Location 要用 `urljoin`，而且相对发出它的那一跳：测试的链是 `jump.example.com` 跳到 `cdn.example.net/c.json`，再跳 `/v2/c.json`。拿第一个 URL 去 join 会落到 `jump.example.com/v2/c.json`。
- 所有跳共用一个时间预算：每跳拿到剩下的时间，测试期望 `[5.0, 3.0, 1.0]`。`TimeoutError` 要转成 FetchBlocked。
- 媒体类型：取分号前的部分、去空格、转小写，再和 `application/json` 精确比较。`startswith` 会放过 `application/jsonp`。
- 正文一块一块读，超过 `max_bytes` 的那一块就停，最多拉 65 块。先 `b"".join` 再检查会把 98 块全拉完。正好 `max_bytes` 字节的正文不算超长，用 `>=` 会挂。
- 只接受 JSON 对象，数组不行。不是合法 JSON 的正文也要转成 FetchBlocked，不能让 JSONDecodeError 漏出去。
- IP 字面量主机也拿去 DNS 解析：假 DNS 对字面量返回空列表，结果照样被拒，测试分不出来。真实的解析器会把字面量原样返回，结果也一样，这种写法可以接受；提一句 docstring 说的是不走 DNS。
- `resolve_cimd`：
  - 没有路径的 client_id（`""` 或 `/`）直接判无效，不发请求。
  - 文档里的 client_id 必须和 URL 逐字相等，差一个尾斜杠也不行。
  - 经过重定向抓到的文档，也要和原来那个 URL 比，不能和最终 URL 比。
  - 缺 client_id 要抛 CimdInvalid，不能抛 KeyError。
  - redirect_uris 必须是非空的字符串列表。只写 `if not uris` 会放过一个字符串。

看什么：是不是先把“一跳要检查什么”列清楚再写循环；会不会读假 DNS 和假 HTTPS 的实现，弄清测试在数什么。

追问：
- "Why connect to the address you checked instead of letting the HTTP library resolve the name?"（检查和连接之间 DNS 可以变：DNS rebinding，也就是 TOCTOU）
- "How would you do this with a real HTTP client?"（自定义传输或连接池，按检查过的 IP 建连接，SNI 和 Host 仍用原主机名；或者走一个强制执行这套规则的出口代理）
- "Is this fetcher the only line of defense?"（不是。出口防火墙、把抓取放到隔离的网络里，都要有；这里只是纵深防御的一层）
- "Can you cache CIMD documents?"（讲义：只能按校验过的 HTTP 缓存控制来缓存）
- "client_name comes from the document. Where does that matter?"（同意页面上显示时当作不可信文本，要转义，不能拿来冒充别的应用）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、读假服务器、看实际数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出混淆攻击、凭据隔离、并发刷新、出口控制 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
