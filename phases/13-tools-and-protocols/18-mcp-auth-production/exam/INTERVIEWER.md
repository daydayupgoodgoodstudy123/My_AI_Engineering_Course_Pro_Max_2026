# 面试官手册：tokengate（13/18）

候选人计时期间不要看。候选人手里只有 README、`tokengate/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 告诉候选人：`tokengate/idp.py` 是假的授权服务器，相当于网络另一端，不要改它。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 资源服务器能不能让授权服务器换钥匙？ | "No. It doesn't hold the issuer's private keys. It can only fetch what the issuer publishes." |
| 1 | 缓存没命中时刷新几次？ | "Once. If the kid is still missing, refuse with unknown kid." |
| 1 | `aud` 可以是列表吗？末尾多一个斜杠算不算？ | "Not here. aud is our canonical resource string, compared exactly." |
| 1 | 两个签发者能用同一个 kid 吗？ | "Yes. A kid is only unique inside one issuer's key set." |
| 2 | 为了排查问题，能不能存 token 的前几位？ | "No. Not in any column, not even part of it. Key by the digest." |
| 2 | 用什么摘要？ | "SHA-256 of the token's UTF-8 bytes, as hex." |
| 2 | 否定的内省结果要不要缓存？ | "Yes, briefly: negative_ttl seconds." |
| 2 | 签发者没给 max_age 怎么办？ | "Then exp and the revocation window decide." |
| 2 | 几个副本共用这个文件吗？谁来 commit？ | "Yes, they share it. The connection is in autocommit mode, so every statement commits." |
| 3 | 依赖挂了返回什么状态码？ | "503, and no WWW-Authenticate. The credential was never judged." |
| 3 | 钥匙超过陈旧窗口时，网关要不要自己去刷新？ | "No. The scheduled job owns refreshes. Past the window we fail closed." |
| 3 | opaque token 送到哪个签发者内省？ | "The deployment's opaque issuer. There is at most one." |
| 3 | exp 是浮点数行不行？内省结果没有 exp 呢？ | "No to both. exp is an integer here, and a missing exp is malformed." |
| 3 | 拒绝的结果也要报 health 吗？ | "Yes. Every outcome reports it." |
| 4 | 定时刷新失败了怎么办？ | "Carry on. The cache stays as it was, and the health column shows it." |
| 4 | 要不要表头？ | "Yes. First, in a chunk of its own." |
| 4 | kid 里有奇怪的字符，要不要清理？ | "No. Log it exactly as sent. CSV quoting keeps it in its column." |
| 4 | opaque token 的 kid 写什么？ | "An empty string." |
| 4 | 两个事件的 t_ms 一样？ | "Handle them in the order they arrive." |
| 5 | 没写 application_type 时默认是什么？ | "Nothing. DCR requires it." |
| 5 | 127.0.0.2 算 loopback 吗？ | "Not for us. Exactly localhost, 127.0.0.1 or [::1]." |
| 5 | 重定向 URI 能带 query 吗？ | "Yes. A fragment can't." |
| 5 | 乱七八糟的输入是抛异常还是返回 False？ | "Return False. Only an unknown application_type raises." |

## 每关：要看什么、提示、追问

### Part 1 修 JWKS 缓存和受众检查（目标 10 分钟）

一个测试里叠了 4 个缺陷和 4 个护栏：

1. `validate` 没检查 `iss` 在不在 `prm.authorization_servers` 里。错误不在 `validate` 报出来，而是一层调用之下，在 `refresh_jwks` 的 `self.idps[issuer]` 报 KeyError。真正的问题是不受信任的签发者根本不该走到抓取这一步；能连上的 lab 签发者在没有白名单时会被接受（讲义 Failure modes 的 "iss not pinned"）。
2. 缺 `aud` 的 token 被当成发给本服务器的：`claims.get("aud", self.prm.resource)`（讲义 "Missing aud claim"）。
3. `refresh_jwks` 把缓存条目写在 `jwks_uri` 下面，`validate` 按 issuer 读，永远不命中，每个请求都抓一次 JWKS。假抓取每次 5 ms，200 次验证要 1.2 秒左右。
4. 缓存没命中时调用 `rotate_key()` 让授权服务器再造一把钥匙，而不是 refresh。新钥匙签的 token 永远找不到，随机 kid 还会让授权服务器的钥匙越来越多（讲义 Rotate-as-fall-back、练习 6）。

护栏：

- 授权服务器轮换后，新钥匙签的 token 一次刷新后必须通过。把 JWKS 永久缓存、或者改成按时间刷新，都会在这里挂掉。
- 随机 kid 每个最多抓一次，钥匙数不变，只刷新这个 token 的签发者；partners 换了钥匙也要能刷新到。“刷新到找到为止”“先 rotate 再 refresh”和照抄讲义代码、永远刷新第一个签发者的写法会在这里挂掉。
- 刷新是替换不是合并：退役的钥匙在下一次定时刷新后失效。两个签发者都有 kid `k1`，缓存必须按签发者分开，`fetched_at` 要更新。
- 白名单在 kid 之前检查：未列入的签发者发来 kid 不是字符串的 token，也要报 `iss not allowed`。把白名单检查加在起始代码的 kid 检查后面会在这里挂掉。

可以接受：按签发者给“未命中刷新”加冷却时间（本课测验 Q12 的做法），测试分不出来。

看什么：是否读了 traceback 之后顺着调用链往上找，而不是在 `refresh_jwks` 里把 KeyError 吞掉；是否对照 `validate` 的 docstring 一条一条核对；计时失败时是否先看 `jwks_cache` 里到底存了什么键。

提示：
- H1："Which issuer was refresh_jwks asked about, and should we have asked at all?"
- H2："Print server.jwks_cache.keys() after two validations."
- H3：直接指出 `validate` 里缺白名单检查的位置，或者指出 `rotate_key` 是授权服务器的动作。

追问：
- "Why is a refresh on a miss safe, but a rotate is not?"（刷新是幂等的抓取；新造的 kid 永远对不上 token，随机 kid 就能让授权服务器无限造钥匙）
- "An attacker sprays random kids. How many JWKS fetches does each one cost now? What would you add?"（每个最多一次，仍然会把流量放大到 IdP；按签发者加冷却或 singleflight，见本课测验 Q12）
- "The lesson's JWKS publishes the HS256 secret. What changes in production?"（RS256 或 EdDSA，JWKS 只放公钥）

### Part 2 内省缓存（目标 12 分钟）

坑：
- 键里放 token 原文，或者为了排查存一个“前 8 位 + ...”的标签。讲义原话是 "Never use the clear token as a log or cache label"。测试会扫描每张表的每一列，还会读整个数据库文件。
- 键里漏了 resource 或 issuer：同一个 token 对另一个资源也命中（讲义 "A result for one resource cannot authorize another resource"）。
- 正向条目只看 exp，或者忘了签发者的 max_age、撤销窗口。三者取最早的那个。
- 否定结果按正向公式缓存，新签发的 token 会被当成 inactive 很久；已经过期的答案不该存。
- 用真值判断会漏两种情况：`if max_age:` 把 max_age 0（签发者要求不复用）当成没给；`if response.get("active"):` 把字符串 `"false"` 当成正向结果。只有 `"active": true` 是正向的。
- 往返要原样。把整个响应当 JSON 文本存最稳。分列存的话，REAL 列会把 1700000600 读回成 1700000600.0，INTEGER 列会把 true 读回成 1；scope 排序以后不是原来的字符串；丢掉 `cnf`、`ext` 这样的扩展字段也不行。测试比较的是 sort_keys 的 JSON 文本，所以类型变了也会挂。
- `put` 不能改调用方的 dict。
- 重开要 `IF NOT EXISTS`；同一个键再存一次要替换：普通 INSERT 会撞主键，没有主键会多出一行。
- `lookup`：活着的条目直接返回，否定的也算；`introspect()` 抛异常就原样抛出，什么都不存；存的时候带上 max_age。命中时不要再存一遍，否则每读一次过期时间就往后推，被撤销的 token 只要一直有人用就一直有效。

可以接受：`get` 顺手删掉过期的行；算出来不该存的答案不去删这个键原来的条目（docstring 没有规定，测试也不检查）。

追问：
- "Why a digest and not the token?"（缓存、备份和日志都会泄漏；摘要是单向的）
- "Is a bare SHA-256 always enough?"（高熵的随机 token 猜不出来；低熵的就要用带密钥的 HMAC）
- "Who decides the revocation window?"（产品和法务给出的最大撤销延迟；高风险工具每次都内省）

### Part 3 验证方式和依赖故障（目标 14 分钟）

坑：
- 时钟读出 NaN 时，任何比较都是 False，`exp <= now` 永远不成立，过期 token 全部放行。讲义的故障表是 "Clock source or claim type is invalid → Reject rather than widening skew until the token passes"。这是运维错误，不是 401。只用 `math.isnan` 会漏掉无穷大（docstring 要求有限的数）；只在 JWT 路径检查会漏掉 opaque token。
- 算法按签发者配置固定，不看 token 头。`alg: none` 要在抓 JWKS 之前就拒绝；头写 HS512、签名其实是 HS256 的 token，不查 alg 的话 `validate` 会放行。写死 `"HS256"` 也不行，测试里有一个只配了 RS256 的签发者。
- claim 类型：exp 是字符串时 `validate` 里会 TypeError；`isinstance(True, int)` 为真，所以 exp 为 true 要单独排除；scope 是列表会在 `.split()` 上 AttributeError；iss 是列表时直接查 dict 会报 unhashable。
- 验证方式由签发者的配置决定。partners 发的 JWT 也要内省，被撤销了就拒绝。按“长得像不像 JWT”选路径，被撤销的 token 会在本地验签通过。
- 内省不可用：不能当 active，也不能当 inactive（那是授权拒绝），是 503 运维错误。缓存里还活着的结果照样可以用。
- 内省结果要逐项检查：active、类型、aud（缺 aud 也要拒绝，不能当通配）、exp、scope。partners 的时钟慢 90 秒，它说 active 的 token 在我们这里已经过期了。scope 要按空格拆开比较：`required_scope in response["scope"]` 是子串匹配，`mcp:tools.invoke.readonly` 会被当成有 `mcp:tools.invoke`。
- 故障表：定时刷新失败、钥匙还在陈旧窗口内，继续服务，health 报 degraded，而且不能每个请求都去问一遍挂掉的授权服务器；未知 kid 且那一次刷新失败，503 `jwks unavailable`；超过陈旧窗口，503 `jwks stale`。陈旧窗口从错过的那次刷新算起，所以界限是 `fetched_at + refresh_interval + stale_window`；只拿 `stale_window` 和钥匙年龄比，会提前 300 秒拒绝。
- health 要按 `validate` 之后的缓存来算：`validate` 里那次刷新成功了，health 就是 ok。拒绝也要报 degraded。

可以接受：边界用 `>=` 还是 `>`（测试不取边界那一刻）。用 `except Exception` 接住 `validate` 里的刷新失败，测试分不出来，但值得追问：它会把代码错误也报成依赖故障，正是讲义说的 "Never improvise availability policy inside an exception handler"。

追问：
- "Why is an introspection timeout not 'inactive'?"（两类结果的后续动作不同：运维错误走健康检查和重试，授权拒绝会让客户端重新授权）
- "How would you size the stale window?"（不能超过撤销新鲜度契约，窗口内退役的钥匙仍然有效）
- "Where does the jwks_uri come from? Would you ever follow a jku header?"（来自已验证的签发者元数据和部署配置；不跟随 token 头里的 URL）

### Part 4 事件回放和 CSV（目标 12 分钟）

坑：
- 输出格式由测试的 `csv.reader` 决定。kid 是攻击者能控制的字段，测试里带了逗号、引号和换行。手工 `",".join` 时这一行会被拆成两行，第二行正好是一条伪造的 allow 记录（日志注入）。用 csv 模块，原样写，不要“清洗”。
- 第一块是表头，之后每块恰好一条记录。多一个空行、去掉行尾、复用一个不清空的缓冲区都会挂。
- 每个请求判定完就输出，探针只允许拉取一个事件。
- 每个事件先把时钟设成 `t_ms / 1000` 再处理。只在请求上设时钟的话，定时刷新会记错 `fetched_at`，之后的 health 就错了；设成毫秒，所有 token 都过期了；用 `//` 丢掉不足一秒的部分，内省缓存的过期时间会提前，1720.3 秒那一行会错。
- 定时刷新失败不能让回放停下，也不写行。刷新事件只刷新它指定的签发者，不要顺手把所有签发者都刷一遍。

可以接受：`csv.QUOTE_ALL`、`lineterminator="\n"`，测试的 `csv.reader` 读出来一样。
- t_ms 写原来的整数；kid 不是字符串时写空串；opaque token 的 kid 也是空串；每个请求的 scope 不一样。
- 不认识的事件类型报 ValueError。`rotate` 是授权服务器的动作，资源服务器没有这一项。

追问：
- "Why log the kid at all?"（证据：哪把钥匙参与了判定。但 token 本身不能进日志）
- "How would you prove every replica refuses within the window?"（讲义：从负载均衡打进去测，不只测一个热进程）
- "The consumer disconnects halfway. What runs?"（`aclose()`，清理放在 finally 里）

### Part 5 DCR 重定向 URI（目标 12 分钟）

坑：
- `urlsplit` 会悄悄删掉制表符和换行，还会去掉开头的空格，所以要先查原字符串里的空白和控制字符，包括 DEL。用 `str.isprintable()` 代替也不行：普通空格是可打印的，路径中间的空格会放过去。
- 用真值判断会漏三种情况：`#` 后面为空时 `parsed.fragment` 是空串；`http://@host` 的 `parsed.username` 是空串而不是 None；`host:` 的 `parsed.port` 是 None。
- 端口用 `str.isdigit()` 或 `\d` 会接受阿拉伯-印度数字；范围要查到 65535。
- loopback 只认三个主机名，不按前缀，也不认 127.0.0.2。
- 方括号里的 IPv6 主机要能解析；方括号没闭合时返回 False，不能把 `urlsplit` 的 ValueError 抛出去。
- 私有 scheme：至少两段，每段字母或数字开头结尾，中间可以有连字符；空段、下划线都不行。
- scheme 和主机名不区分大小写；可以带 query，`@` 出现在 query 里没关系。authority 在 `/`、`?` 或 `#` 处结束：`http://127.0.0.1:7333?flow=desktop` 没有路径，只按 `/` 切的话端口会变成 `7333?flow=desktop`。
- `registration_error`：DCR 必须带 application_type，没有默认值（OpenID Connect 的默认 web 在这里不适用）；先查 application_type；空列表和字符串都不行；每一个 URI 都要合规。

追问：
- "Why does DCR need application_type when CIMD doesn't?"（讲义："Do not copy the DCR requirement for application_type into the preferred CIMD path"）
- "Why accept localhost at all, and what does the authorization server owe the user?"（讲义：同意页要显示重定向的主机名，只有 localhost 的重定向要警告）
- "What else would you check before registering?"（练习 3：按源 IP 限流；练习 4：software_statement）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出撤销窗口、故障分类、日志证据、密钥管理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
