# 面试官手册：mcpgateway（13/17）

候选人计时期间不要看。候选人手里只有 README、`mcpgateway/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查 Python 官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 调用方 `_meta` 里的 traceparent 之类要转给后端吗？ | "Not in this exercise. The backend gets the gateway's own envelope and nothing else. Trace propagation is a follow-up." |
| 1 | 被拒绝的请求算不算进限流？ | "Not against this quota. Only calls the policy allows spend a unit. An abuse limit on refused calls would be a separate limiter, and it isn't in scope." |
| 1 | 窗口在正好 window_s 的时候还算吗？ | "No. A call allowed at t stops counting at t + window_s, as the docstring says." |
| 1 | 网关没有某个后端的凭证怎么办？ | "That backend is never called. `_credential` already says so." |
| 2 | mrtr_round 和 request_meta 是新的 MCP 字段吗？ | "No. They are this exercise’s audit fields. Preserve the captured values; do not add wire fields." |
| 2 | error.code 也算授权码吗？ | "No. It is protocol evidence. Redact code only under arguments and inputResponses." |
| 2 | 要查其他事件把调用拼起来吗？ | "No. Project one event. Part 5 reconstructs calls across events." |
| 2 | 头名要规范成小写吗？ | "No. Keep the names as they arrived, sorted." |
| 2 | 自由文本里出现的 Bearer token 也要脱敏吗？ | "Not here. Header values, and the SECRET_KEYS keys under arguments and inputResponses." |
| 2 | 每条都要 fsync 吗？ | "Flush is enough for the tests. Tell me what fsync would add." |
| 2 | 别的副本写的行也算进 seq 吗？ | "Yes. seq is the event's place in the file." |
| 2 | 最后一行写了一半（进程崩了）怎么办？ | "The tests don't cover it. Tell me what you'd do." |
| 3 | 能不能把策略文档缓存一会儿？ | "No. Ask the service for every decision. A revocation has to apply to the very next call." |
| 3 | token 里的角色还有用吗？ | "Not for this engine. Roles come from the policy. The token's roles are whatever was true when it was issued." |
| 3 | 服务挂了，又从来没拿到过策略？ | "Fail closed." |
| 3 | 一次 fetch 成功但结果是拒绝，也刷新 last-known 吗？ | "Yes. Any fetch that returns a policy refreshes it." |
| 3 | 几条规则同时不满足，报哪个？ | "The first one in the docstring's order." |
| 4 | 客户端没给 progressToken，后端还是发了进度？ | "Drop it. A client that asked for no progress gets none." |
| 4 | 结果里面嵌套的 id 要改吗？ | "No. Only the response's own id, and the token on this request's progress." |
| 4 | 日志之类的其他通知呢？ | "Drop them." |
| 4 | 可以攒几个事件一起发吗？ | "No. Each event goes out when it arrives." |
| 4 | 两个后端给出同一个 taskId？ | "The tests don't cover it. Tell me what you'd do." |
| 5 | 一个请求会有两个 result 吗？ | "No. One decision, and at most one result." |
| 5 | 被拒绝的重试还算在树里吗？ | "Yes. A refused retry is still part of the call." |
| 5 | 重试能挂到时间更晚的结果下面吗？ | "No, only under an earlier one. The tests don't send that." |
| 5 | 请求 id 7 和 "7" 是同一个吗？ | "No. JSON-RPC ids are compared as they are." |

## 每关：要看什么、提示、追问

### Part 1 修转发与限流（目标 10 分钟）

一个测试里叠了 4 个缺陷和几道护栏：

1. `_backend_request` 把调用方的 HTTP 头摊在最后（`**request.headers`），调用方的 `Authorization: Bearer tok-alice` 盖掉了网关给 reports 后端的凭证。错误不在这里报：后端拒绝了陌生的 token（-32001），网关的结果检查把它包成 502 `Backend error`，测试看到的是“allowed call 没拿到结果”。课里：Never pass the outer gateway token to a backend。
2. 同一个函数里 `params.setdefault("_meta", ...)`。调用方的 params 本来就带着 `_meta`，所以 setdefault 什么都不做，后端拿到的是调用方原样的 `_meta`，里面声明了 Tasks 扩展。后端自己决定返回 `resultType: task`，而这个网关并不中介 Tasks，`check_response` 拒绝转发，又是一个 502，这次写着 `cannot relay`。根因离报错有两层：先要想到“后端为什么会返回 task”，再看后端收到的 `_meta`。课里：The gateway is the backend's client。
3. `_admit` 在校验之前，按 `Mcp-Name` 路由头就扣了限流。三条畸形请求（方法头不一致、工具名不一致、不支持的版本）各花掉 alice 一次额度，后面合法的调用直接 429。docstring 写的顺序是认证、校验、找路由、问策略，最后才扣限流。课里：Apply cheap validation before consuming expensive work。
4. `RateLimiter.allow` 每次调用都用列表推导重建整个窗口，一个 key 窗口里有 12,000 次调用时是平方级。本机实测（负载 6 到 8）12,001 次调用 0.93 到 1.37 秒，限值 0.05 秒；改成 deque 从队头弹出后 1.5 到 4 毫秒。

护栏：

- 后端收到的请求要逐字段相等：新 id、后端自己的工具名、网关自己的三项 `_meta`。把网关的信封写在调用方 `_meta` 上面、照抄调用方能力、照抄 clientInfo、什么能力都不声明、把网关能中介的能力全声明（bob 什么都没声明，后端却看到 elicitation），都会挂。
- 后端收到的头只能是路由头加网关凭证。把调用方的头放前面再覆盖，还是会带上 `Mcp-Session-Id` 和 `Cookie`；合并以后只改 `Authorization`，调用方的 `Mcp-Name: reports.build` 会盖掉 `build`，后端报 -32020。路由头要按发给后端的 params 生成，拿调用方的 params 去生成，`Mcp-Name` 也是公开名，同样是 -32020。
- 调用方的请求不能改。直接在调用方的 params 上改 `name` 和 `_meta`，后端收到的请求没错，但调用方的 body 变了，网关之后写审计时读到的也是网关自己的 `_meta`，trace 就丢了。测试在第一次调用后比对调用方的 body 和头。
- 凭证按 (issuer, resource) 取。notes 和 reports 同一个 issuer、不同 resource，只按 issuer 取会把 notes 的 token 发给 reports。legacy 后端没有凭证，退回用调用方的 token、或者带个空 token 照样去调，都会被“never called”抓住。
- MRTR 重试要把 `inputResponses` 和 `requestState` 原样带给后端。只拿 name 和 arguments 重建 params，后端会再要一轮输入。
- 限流只在策略允许以后扣，而且要在转发之前扣：bob 三次调用他无权的 `notes.create` 必须每次都是 403；放在校验之后、策略之前扣，第二次就成了 429。等后端回答以后才检查限流，第 4 次调用已经转发出去了。
- 窗口按 (principal, issuer, resource, 工具, 成本类别) 分开。为了提速改成一个全局窗口、按成本类别共用、只按 principal（本课代码就是这样）、不带 issuer，都会挂。另一个 issuer 下同名的 alice 是另一个 principal。
- 窗口语义：换成本课 `TokenBucket` 那样的令牌桶，30 秒后会放进一次调用；换成固定的一分钟格子，跨格子就放行；被拒绝的调用也记进窗口，60 秒后只放进一次；边界写成 `<`，正好 60 秒时还拒绝；限流器自己读 `time.monotonic()`，测试拨的时钟就没用了。
- 换成 deque 但每次还是 `deque(t for t in calls if ...)` 重建，或者用 bisect 找到切点再把剩下的复制一遍，计时照样挂；先判断窗口满没满、再删过期的，窗口满了以后就永远是满的。

看什么：是不是先读 502 里的 `data`，看出是后端拒绝的，而不是网关自己；会不会打印 `reports.received[-1]` 看后端实际收到了什么；第二个 502 出来时，有没有问“后端凭什么返回 task”。

提示：

- H1："The 502 says the backend refused. What did the backend actually receive?"
- H2："Print reports.received[-1].headers, then .body['params']['_meta']."
- H3：直接指出 `**request.headers` 和 `setdefault`。

追问：

- "Why not forward the caller's capabilities as they are?"（网关是后端的客户端。后端看到 Tasks 或 elicitation，就会返回网关没法转给这个客户端的结果；网关支持、客户端没声明的能力也一样。课里：Advertise only the capability intersection the gateway can honor end to end）
- "The backend needs to know which end user is acting. How, without the user's token?"（设计好的 token exchange 或 claims 模型，带上委托关系；不要用共享服务凭证冒充用户，也不要转发外层 token。课里 Credential mediation 一节）
- "Should refused calls count against something?"（业务额度不该被拒绝的调用花掉；另设一个滥用限额，把被拒绝和畸形的请求都算进去，防止有人无限试探工具名）
- "Three gateway replicas behind a load balancer. Where does the window live?"（共享存储，原子的“检查并追加”，比如 Redis 的有序集合加脚本；或者按 key 一致性哈希到同一个副本。会话 id 不能当键：现在没有会话，有也可以随便换）

### Part 2 单条审计证据与脱敏（目标 12 分钟）

坑：

- 一条事件要留下完整协议和策略证据。MRTR round、状态摘要、任务 id、descriptor pin 版本、调用方/后端 request id、trace、principal/issuer、route、decision/reason、latency/result 以及捕获的 request/result metadata 都不能被“只保留少数固定字段”的重建丢掉。
- task_id 是任务关联证据；outer error 的 code 和 data.requiredCapabilities 是协议拒绝证据，不是 arguments.code 那种授权码。只留 error 的 code/message，会丢掉拒绝要求；对整条事件递归脱敏，会误擦协议码。
- `mrtr_round`、`descriptor_pin`、`request_meta`、`result_meta` 是本练习的应用审计字段，不是新 MCP 属性。metadata 的值来自真实 protocolVersion/clientInfo/serverInfo；保存完整结构，不能只留 server 的显示名。
- JSONL sink 和 AuditLog 调用 wrapper 已正确给出：先做 redact 投影，再 append/flush。候选人不再实现文件缓冲；追加、flush、编号和读回的断言与错误修法保护给定 sink。
- 给定 sink 用追加模式，不能换成清空文件的 `"w"`；每条事件写完 flush，`record` 返回后、`close` 前直接读磁盘可见。
- 先脱敏再写。只在返回值里脱敏、磁盘上写原始事件，会被逐个查找的秘密字符串抓住：`tok-alice-7f3a`、Cookie、`PW-5e1`、`RT-88a`、`AK-41c`、`AUTHCODE-17`。
- 不能改调用方的事件。网关下一步还要用这些头和参数。直接在 event 上改、或者浅拷贝以后原地脱敏，都会把调用方的 dict 改掉。
- `headers` 只留头名，用默认的 `sorted`（区分大小写）。把值换成 `[redacted]` 但保留 dict、按到达顺序列出、按小写排序，都和测试要的不一样。
- 秘密键下面的值整个换成 `[redacted]`，不管它是不是字符串：`secret` 下面是一个 dict，只替换字符串值的写法会钻进去，把 `SV-3b0` 写到磁盘上。
- 键名按小写精确比对 SECRET_KEYS，要递归穿过 dict 和 list。区分大小写会漏掉 `Password`；只看顶层会漏掉 `options.refresh_token`；不进 list 会漏掉 `items[0].api_key`；按子串匹配会把 `max_tokens` 也抹掉；假设每个值都是 dict 会在 list 上报 AttributeError。
- 只脱敏 `arguments` 和 `inputResponses`。对整个事件递归，会把网关自己记的 `error.code` 也抹掉；漏掉 inputResponses，OAuth 授权码就落盘了。
- 读的时候只按 `\n` 切行。别的副本用 `ensure_ascii=False` 写了一行，里面有原样的 U+2028；`splitlines()` 会在它那里切开，报 JSONDecodeError。
- `seq` 接着文件里已有的事件往下编，包括别的副本写的。每次打开都从 1 开始，或者只数自己写的，都会挂。
- 原样往返：请求 id 7 和 "7" 是两个值，`0.1 + 0.2` 的延迟要一位不差，读回来按写入顺序，不按 ts 排。把 id 统一成字符串、把延迟四舍五入、按时间排序、从内存里返回而不读文件，都会挂。
- 最后一段是端到端检查：网关（Part 1 要先修好）把事件写进 AuditLog，文件里不能出现调用方 token、后端凭证和参数里的 api_key。
- 可以接受的写法：写入时用 `ensure_ascii=False`（读的时候只按 `\n` 切就没问题）；不整体 deepcopy，只给 headers 和两个脱敏字段建新对象，调用方的 dict 一样不受影响。

追问：

- "Two gateway replicas append to the same file. What can go wrong?"（O_APPEND 只保证每次 write 落在文件末尾；Python 的缓冲可能把一条长事件拆成几次 write，网络文件系统更不保证；两个副本各自编 `seq` 还会撞号。实际做法是每个副本一个文件，或者发到集中的日志管道，按 (副本, seq) 排序）
- "The process dies halfway through a line."（读的时候跳过最后一行不完整的 JSON，打开写之前补一个换行；要更稳就 fsync 加校验和）
- "How do you prove nobody edited the log later?"（哈希链：每行带上一行的摘要，定期把链头锚定到外部；第 30 课的准入账本就是这么做的）
- "Why not log requestState itself?"（它是后端的不透明状态，可能带敏感数据；记一个摘要就够把轮次连起来，Part 5 正是靠这个）

### Part 3 运行时策略（目标 12 分钟）

坑：

- 每个决定都要问一次策略服务，按调用方、按上下文缓存允许决定，或者只取一次策略文档，角色撤销后都会照样放行。课里：Do not cache an allow decision under a connection or removed session identifier。
- 角色从策略的 `roles` 里取，键是 (issuer, principal)。用 token 里的角色，撤销后照样放行（token 不会因为撤销就变）；不给默认值，策略里没有 carol 时报 KeyError；只按名字找，partner-idp 的 alice 会拿到 idp 的 alice 的角色。
- 准入只是输入。已准入、已 pin 的后端，跨租户的调用照样拒绝（`tenant`），撤销角色的调用照样拒绝（`role`）。“已准入又已 pin 就放行”、“已 pin 就不查租户”都会挂。
- 参数里没有租户（`target_tenant` 是 None）不算跨租户。
- 数据分级只决定失败路径。服务在线时，敏感读照常按规则判定；另加一条“敏感数据一律拒绝”的规则会挂。
- 规则有顺序，第一个不满足的就是原因。测试里有准入和角色、角色和 pin、pin 和 tenant、tenant 和 health、health 和隔离同时不满足五种组合，把 pin、health 这些后端层面的检查提到角色前面，会挂。
- 隔离只管写。读照常放行。
- 策略里没列的工具直接拒绝（`role`），不能 KeyError。
- 服务挂了以后：只有读、公开数据、工具在 last-known 策略的 `stale_reads` 里、last-known 不到 ttl，这四条都满足才能用 last-known 策略，而且规则照样全套执行（bob 的角色在 v4 里已经没了，照样拒绝；后端不健康照样拒绝），路径记 `last_known`，版本记 last-known 的版本。写、通过批准工具的写、敏感读、内部读、没批准的公开读，都失败关闭：`policy_unavailable`、`fail_closed`、没有版本。
- ttl 从最后一次成功 fetch 算起，严格小于。正好 30 秒就关闭；从第一次 fetch 算会提前关闭；失败的 fetch 刷新了时间会一直开着；只在允许的决定上刷新也不对，5040 那次成功的 fetch 得到的是拒绝，照样要刷新。
- PolicyUnavailable 要接住。漏接住，异常会冒到网关。
- 最后一段是端到端检查：网关换上 PolicyEngine，alice 的第一轮 MRTR 放行，策略撤销她的角色后，第二轮重试被 403 拒绝，后端只收到过一次请求。课里：It must not assume an earlier round granted unlimited approval。

追问：

- "The policy service is slow, not down. What then?"（设超时，超时按不可用处理；不要无限等，也不要因为慢就放行）
- "Who decides what goes in stale_reads?"（按风险模型由人审批，写进策略文档并带版本；不是网关代码里写死的）
- "How would you roll out a new policy version safely?"（先影子评估：新旧策略都算，只按旧的执行，记录分歧；分歧可以接受再切换。决定里记了版本，回放审计日志就能比较）
- "Why record the path and the version on every decision?"（事后要能回答“当时是哪一版策略、走的哪条失败路径放行的”；课里：Record which policy version and failure path made the decision）

### Part 4 SSE 透传与任务路由（目标 14 分钟）

坑：

- 输出格式由测试的解析代码决定：每个事件是一行 `data: <JSON>` 加一个空行，UTF-8 字节。写成 str、只跟一个换行、JSON 带缩进、前面加 `event:` 或 `id:` 行，都会挂。用 Latin-1 编码会在 em dash 上报 UnicodeEncodeError。课里：do not promise Last-Event-ID replay。
- 网关给后端的进度 token 就是后端请求 id（`gw-3`），所以进度通知要换回客户端自己的 token（`p-7`）。换成客户端的请求 id（7）、原样发出 `gw-3`、转发别的 token 的进度、给通知加上 id，都会挂。进度消息文本里也有 `gw-3`，做字符串替换会改坏它。
- 最终响应把 id 换成客户端的 id，result 的 `_meta` 整个换成网关的 serverInfo（`gateway_result`），其余原样。后端的 `_meta` 里除了 serverInfo 还有 `com.example/shard`，和网关的 serverInfo 合并会把它带给客户端。错误响应也一样换 id。
- 客户端没要进度（`progress_token` 是 None）就一条进度也不发。0 是合法的客户端 id 和进度 token，用 `if hop.progress_token:` 判断会把它当成没要进度。
- 流上别的东西一律丢掉：日志通知、别的 token 的进度、给另一个请求 `gw-2` 的响应，还有后端发来的 `sampling/createMessage` 请求（现代版本不允许服务端在请求流上发请求，见第 09 课）。把带 id 的消息都当成最终响应，会在这条请求上报 KeyError；只看有没有 result 不比对 id，会把 `gw-2` 的响应当成这条请求的。
- 响应发出去流就结束，不再读后端。读完后端剩下的消息、或者响应以后继续转发，都会挂。
- 进度到达就转发。测试数被拉取了几页，攒到响应再一起发的写法在一个永远不结束的后端上拿不到第一个事件。
- 客户端断开（`aclose`）时要关掉后端的流，这就是取消后端请求（课里：Closing the response stream cancels that in-flight modern HTTP request）。漏了 `finally: await messages.aclose()`，后端的 finally 不会及时执行。
- input_required 的 result 原样透传，`inputRequests` 和 `requestState` 一个字节不动。只挑 complete 结果那几个字段重建 result，就把它们丢了。课里：Preserve requestState byte for byte。
- task 要在客户端看到 taskId 之前记下路由：测试在客户端拿到事件、还没断开时就去 resolve。在 yield 之后记、在 finally 里记，都晚了；断开时把这条流记下的任务删掉，也不对（任务比请求活得长）。路由记的是后端名，不是后端请求 id。
- TaskRoutes 只给记下的那个 owner：bob、partner-idp 的 alice 都拿不到 alice 的任务，而且和不存在的任务一模一样（同一个 -32602）。只按名字比对 owner 会放过 partner-idp 的 alice；对别人的任务报 PermissionError，等于告诉对方这个任务存在。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要会看出这里需要 async generator。
- 测试不抓的写法：只在 `except GeneratorExit` 里关后端、正常结束时不关（网关的 `_tap` 自己也会关）；`json.dumps` 默认转义非 ASCII。可以追问为什么 `finally` 更稳。
- 最后一段是端到端检查：网关的 `open_stream` 把进度和 task 发给客户端，之后 `tasks/get` 按 Mcp-Name 里的 taskId 路由到 reports；MRTR 两轮都走流式，后端用 HMAC 验证客户端回传的 requestState。

追问：

- "The client reconnects and asks for the events it missed."（现代版本没有 Last-Event-ID 重放；要么重新调用，要么用 Tasks 拿到可轮询的句柄）
- "A thousand progress events a second."（进度可以合并、可以丢最旧的，最终响应不能丢；第 29 课讲的就是这个）
- "Two backends both mint tsk-1."（路由表按 taskId 冲突时不能覆盖；可以拒绝转发第二个，或者网关自己重新编号并保存映射，这就是课里说的 terminates and reissues）
- "When can a task route be deleted?"（任务进入终态并且过了 ttlMs 以后；客户端断开不算）

### Part 5 审计决策链重建（目标 12 分钟）

坑：

- 一个请求的身份是 (issuer, principal, trace_id, request_id)。请求 id 是客户端起的：alice 的第二个 agent 也用 1；bob 的服务在 alice 的 trace 里被调用，也从 1 开始。不带 trace，第一轮的结果会挂到第二个 agent 的请求下面；不带 principal，会挂到 bob 的请求下面；只按 id 更乱。
- MRTR 重试是新 id，靠 `state_in` 等于某个更早结果的 `state_out` 连起来，挂在产生这个状态的那一轮下面（第三轮在第二轮下面，不在第一轮下面）。按 trace 连会把同一个 trace 里独立的 notes.search 也拉进来；同一个状态被重发了两次（网络重试），两次都挂在同一轮下面，`pop` 掉就只剩一个。
- 任务请求靠 taskId 连到返回这个任务的那次结果（result 是 "task"）。第一次轮询隔了很久，中间夹着别的事件，还换了 trace；按位置或按 trace 都连不上。轮询的结果也带着 taskId，但它不是创建任务的结果，拿它建索引会把第二次轮询挂到第一次下面。
- 状态和任务都按 (issuer, principal) 分开：bob 重放 alice 的状态、bob 轮询 alice 的任务，都是孤儿，不能挂进 alice 的树。partner-idp 的 alice 和 alice 同名，在同一个 trace 里也用了 id 2，还重放了 alice 的状态：身份里不带 issuer，第二轮的结果会挂到她的请求下面；状态表不带 issuer，她会挂进 alice 的树。
- 状态链接不看 trace：第三轮的第二次发送来自一个新的 trace，照样挂在第二轮下面，按 trace 分开的状态表会把它当成孤儿。
- 被拒绝的请求也在树里：第三轮又发了一次、被策略拒绝，它照样挂在第二轮下面。跳过不是 allow 的决定，它和 bob 的两个孤儿都会消失。
- 孤儿：找不到 decision 的 result（叶子），连不上的重试和任务请求（连同它下面的 result）。连不上的请求当成新的调用，或者把它的 result 单独列成孤儿，都会挂。
- 排序按 (ts, seq)。输入是打乱的；alice 的两个 agent 同一毫秒开始，只按 ts 排会把顺序交给输入；只按 seq 排，晚写进日志、时间更早的 notes.search 会排错。
- 最后一段是端到端检查：网关自己的审计事件（MRTR 两轮加一次搜索）拼回两棵树，没有孤儿。
- 可以接受的写法：按 seq 顺序处理、最后再把每一层按 (ts, seq) 排序。测试里每个链接的目标在 seq 和时间上都更早，结果一样。先处理所有 decision、再处理 result 不行：处理重试时状态表还是空的，每个重试都成了孤儿。

追问：

- "The log comes from three replicas with skewed clocks."（ts 不可靠时用因果关系：结果一定在决定之后，重试一定在产生状态的结果之后；可以给每个副本单独的 seq，再按因果合并）
- "Would you store a call id instead of rebuilding?"（可以在 requestState 里带上原始调用 id，但那要网关终止并重发交互；不改 requestState 的话，摘要连接是网关唯一能做的）
- "A million events a day. How do you answer 'what happened to call X'?"（按身份、状态摘要、taskId 建索引，查询时只展开一棵树；冷数据归档）
- "What would make two different calls share a state digest?"（后端重复用同一个 requestState，或者摘要截断后碰撞；状态应当绑定 principal 和一次性 nonce，第 11、12 课讲过）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读断言消息和 502 里的 data、打印后端实际收到的请求、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出凭证中介、限流放在哪、多副本、日志完整性、策略失败路径、背压、任务路由的生命周期 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
