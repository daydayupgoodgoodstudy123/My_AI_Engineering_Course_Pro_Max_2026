# 面试官手册：mrtrkit（13/11）

候选人计时期间不要看。候选人手里只有 README、`mrtrkit/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 模型选了列表里没有的文件，是整个回复都拒绝，还是丢掉那些名字？ | "Drop the names the listing didn't offer. If nothing is left, it's -32602." |
| 1 | 验证过的 requestState 能缓存吗？ | "Cache the key if you like. A requestState is checked every time it comes back, expiry included." |
| 1 | 每一轮的过期时间要重新算吗？ | "Yes. Each requestState is good for five minutes from when it's sealed." |
| 1 | 能不能把 PBKDF2 的迭代次数调小？ | "No. Every replica derives the key with the same parameters." |
| 1 | clientInfo 能不能当身份？ | "No. It's display metadata. The transport hands you the authenticated principal." |
| 2 | 新令牌用哪个密钥签？ | "keyring.current. The other keys in the ring only verify." |
| 2 | 令牌在 expiresAt 那一秒还有效吗？ | "Yes. It expires the second after." |
| 2 | 状态里有 NaN 怎么办？ | "It has no canonical JSON form. Raise ValueError when sealing." |
| 2 | 带 `=` 填充的令牌要拒绝吗？ | "Your call. Say what you chose. The tests don't cover it." |
| 3 | 一轮有两个输入请求，审批一次还是两次？ | "Once per request. The user sees each one before the model runs." |
| 3 | max_rounds 数的是什么？ | "The input_required results you fulfil. Three means at most three rounds of model calls." |
| 3 | 服务器要的东西主机不支持，回什么？ | "Nothing. Stop the interaction with a HostError." |
| 3 | inputRequests 是空的怎么办？ | "Your call. Say what you chose. The tests don't cover it." |
| 4 | 预算什么时候扣？ | "When the round is approved, before the model runs." |
| 4 | 被拒或超预算的轮次要扣吗？ | "No. Their tokens column is 0." |
| 4 | 行按什么顺序输出？ | "The order the decisions are made." |
| 4 | 用户一直不回审批怎么办？ | "Keep waiting. If the approvals stream ends, deny whatever is still waiting." |
| 4 | 一轮有几个输入键时，input_key 怎么写？ | "All of them, sorted, separated by spaces." |
| 4 | budgets 里没有这个主体怎么办？ | "Your call. Nothing to spend is the safe default. The tests don't cover it." |
| 5 | 两条路径汇到同一个阶段算环吗？ | "No. Only a path that comes back to a phase it already visited." |
| 5 | DONE 算一轮吗？ | "No. A round is a phase that asks the client something." |
| 5 | 同一轮用同样的答案重试两次，第二次要拒绝吗？ | "No. A stateless server can't tell that from a network retry." |

## 每关：要看什么、提示、追问

### Part 1 修 MRTR 两轮（目标 10 分钟）

一个测试里叠了 5 个缺陷和 3 道护栏：

1. `_binding` 对整个 params 求摘要，连 `inputResponses`、`requestState`、`_meta` 一起算进去，第一轮和重试的摘要永远对不上。错误在 `verify` 里报出来：`requestState arguments mismatch`，可是参数根本没变。根因在上游的 `_binding`，docstring 写的是只绑定工具名和参数。
2. `_caller` 优先用 `clientInfo.name` 当身份。课里写明 clientInfo 是展示和诊断用的元数据，不能当已认证的身份。user-7 拿着 user-42 的 requestState、用同一个客户端就能继续。
3. `_offered` 只检查“是不是一个存在的文件”，`../secrets.txt` 和绝对路径都能读到仓库外面。课里的要求是模型输出当文件名用之前必须校验；这里只认第 1 轮列给模型的那些名字，`docs/../server.py` 和 `./LICENSE` 也不行：它们指向仓库里的文件，却不是列表里的名字。只跳过带 `..` 的名字和绝对路径的写法会放过 `./LICENSE`，在这里挂。列表外的名字丢掉就好，不是整个回复作废。
4. 模型把同一个文件选三次也照单全收（测验 Q10(d) 指出的缺陷）。要保持模型给的顺序去重，再截到三个。
5. `seal` 和 `verify` 每次都用 PBKDF2（600,000 次迭代）从口令派生密钥，一次约 45 ms，24 次重试要 1 秒多。docstring 写的是副本启动时派生一次。

三道护栏：

- 已知答案检查：签名必须是 PBKDF2(secret, KDF_SALT, 600000) 派生出的密钥算的 HMAC。为了提速调小迭代次数，或者每个副本随机生成密钥，都会在这里挂；随机密钥还会让另一个副本验不过。反过来，口令不同的服务器必须拒绝，所以也不能把派生好的密钥缓存在类上、不管是哪个口令。
- 改了 arguments 的重试必须被拒。为了让第 1 个缺陷“消失”而删掉绑定检查，或者只绑定工具名，会在这里挂。
- 过期：为了提速缓存验证结果，过期检查就被跳过了。时钟走到 expiresAt 那一秒仍有效，再过一秒必须拒绝。只按 token 缓存还会跳过参数和主体检查，在更早的断言就挂。

看什么：看到 `arguments mismatch` 后，是否把两次参与摘要的内容打印出来对比；是否一次只改一处、改完就重跑；修路径问题时是想到“白名单”还是只想到“过滤 `..`”。

提示：

- H1："Print what goes into the digest on the first call and on the retry. What differs?"
- H2："Which identity does the state get bound to, and where does that value come from?"
- H3：直接指出 `_offered` 用的是 `is_file()`，`_key()` 每次调用都在派生。

追问：

- "Would you bind _meta as well?"（不要：协议版本和能力是每个请求自己声明的，clientInfo 只是展示信息；把它们绑进去，客户端升级一次就会让合法的重试失败。只去掉 inputResponses 和 requestState、保留 _meta 的写法测试拦不住，在这里问）
- "Why not cache verified tokens to make retries fast?"（过期必须每次检查；缓存键还得包含主体和调用。慢在密钥派生，派生一次就够了）
- "HMAC or authenticated encryption for this state?"（HMAC 只保证完整性，客户端能读到 picked；不能让客户端读时用认证加密，这是课里的原话）
- "The same retry arrives twice. What happens, and does it matter?"（无状态服务器两次都接受；轮次有副作用时才有害；一次性 nonce 存储是第 12 课的内容）
- "Several replicas: where does the secret live, and how do you rotate it?"（密钥管理服务；带密钥 id 才能轮换，这就是 Part 2）

### Part 2 版本化签名令牌（目标 12 分钟）

坑：

- 去掉的 `=` 解码前要补回去，不然 `Incorrect padding`。标准 base64 的 `+` 和 `/` 不是 base64url。
- `base64.urlsafe_b64decode` 不检查字母表：把同一串字节写成带 `+`、`/` 的标准 base64，它照样解出同样的字节，MAC 也对得上。测试要求这种令牌被拒（`only base64url text opens`），所以解码前要先查字符，用正则，或者解码后重新编码再和原文比较。
- 长度字段按字节：非 ASCII 文件名在 UTF-8 下字节比字符多。按字符算，`open_state` 会报长度不符。
- 规范 JSON：排序键、无空格、非 ASCII 原样写（`ensure_ascii=False`）、不允许 NaN 和 Infinity（`allow_nan=False`）。只在顶层手工查 NaN 会放过嵌套列表里的 `inf`，测试里有这一条。直接复用 `protocol.canonical` 会得到 `\u` 转义的负载，头部长度就对不上。
- HMAC 要覆盖整个头部。只签负载的话，改过期时间或密钥 id 都发现不了。
- 先看版本和密钥 id，再验签。未知密钥 id 不能漏出 KeyError，短输入不能漏出 struct.error，测试要的都是 StateError。
- 新令牌用 `current` 签，不是 id 最大或最小的那个；ring 里的旧密钥签的令牌照样能打开。
- 尾部多出的字节要拒绝：只按头部长度切片、不看总长度，会放过它。
- 往返要逐类型一致：`2` 和 `2.0`、`-0.0`、`2**70`、次正规数、`e` 加组合重音符都要原样回来。

追问：

- "Why is the key id in the clear?"（验证方要知道用哪把钥匙；它不是秘密，而且在 HMAC 覆盖范围内）
- "How do you retire key 2?"（先停止用它签名，等最长有效期过去，再从 ring 里删掉）
- "Why a version byte?"（格式会变；未知版本直接拒绝，不去猜）
- "Why not a JWT?"（也可以；这里考的是布局和精确往返，JWT 的 header 和 alg 选择是另一类坑）
- "You compared the MACs with ==. Does that matter?"（要用 `hmac.compare_digest`，避免按字节提前返回带来的计时侧信道；测试测不出来，在这里问）

### Part 3 客户端 MRTR 驱动（目标 12 分钟）

坑：

- 每一轮都是新请求：id 从 `ids` 里取下一个，方法和原始 params（name、arguments、_meta）不变，调用方传进来的 params 本身不能被改。
- 只带本轮的答案，不累积上一轮的。
- 回传的是本轮收到的 requestState，逐字节：不能 strip，不能“看起来像 JSON 就解析再序列化”。测试里有一个 `'{"phase":"pick",...}'` 和一个带尾部空格的 state。
- screen 在用户和模型之前：整轮的每个请求都先过检查，再逐个问审批，全部批准后才调模型。边审边调模型，被拒的那一轮已经花了钱。
- 只有 tools/call、prompts/get、resources/read 可以要输入；tools/list 返回 input_required 要拒绝，prompts/get 要放行。
- 能力看的是这次请求自己的 `_meta` 里声明了什么，不是“主机会做什么”。不认识的方法（这里是 elicitation/create）直接拒绝。
- includeContext 只能是 `"none"`；没写就等于 `"none"`，课里的示例请求就没写这个字段。一轮里的每个请求都要看，测试里要上下文的是第二个。
- 轮数上限在审批和模型之前检查；`max_rounds=3` 表示最多 3 轮模型调用，第 4 个 input_required 直接停，用户也不会被问到。数的是 input_required 的轮数，不是输入请求的个数：prompts/get 那一段第 1 轮有两个请求，测试给的是 `max_rounds=2`，两轮都要放行；按请求个数累加会在第 2 轮报 `rounds`。
- modelPreferences 是互相独立的提示，原样交给模型，不归一化，也不因为加起来不等于 1 就拒绝。
- 错误响应要抛 McpError，不能当结果返回。

追问：

- "Why must the round cap live in the host and not only in the server?"（不可信的是服务器；恶意服务器可以无限要输入，花的是用户的模型额度）
- "What do you show the user at approval time?"（发起的方法、输入键、prompt 内容、maxTokens；不是隐藏的上下文）
- "The server asks for includeContext allServers. Why refuse instead of quietly sending none?"（悄悄降级会让服务器以为拿到了上下文；而且这些模式已弃用，课里要求保持 none）
- "costPriority, speedPriority and intelligencePriority are all 0.9. Which model do you pick?"（模型策略归客户端；三个提示互相独立，可以忽略）

### Part 4 并发审批与预算（目标 14 分钟）

坑：

- 交互之间不能互相等。A 排在第一个，它的第 1 轮审批却要等 B 和 C 都处理完才来。一个一个按顺序跑会卡住，测试 3 秒后报 `the run stalled`，并打印已经输出的行。
- 审批可能先于它对应的轮次到达：B 第 2 轮的拒绝比第 1 轮的批准还早。要先存起来，等那一轮出现再用；按交互名而不是按 (交互, 轮次) 去对审批，会把它错用在第 1 轮上。
- 预算按主体共享：A 第 2 轮超预算，是因为同一个用户的 B 第 1 轮已经花掉一半。按交互单独算预算会放过它。
- 字节也要扣：C 第 2 轮单看付得起，加上第 1 轮已经扣掉的就不够了。只检查不扣，或者只扣 token，都会放过它。
- denied、over_budget、refused 的轮次都要写一行，tokens 是 0，它们的交互随之结束：不再发请求，也不调模型。
- 先看用户的决定，再看预算：用户没批准的轮次是 denied，哪怕预算也不够。第二段里 E 第 1 轮正好用完 user-7 的 400 token，审批流结束时 F 第 1 轮要记 denied，不是 over_budget。
- request_id 是“提出这一轮的那个请求”的 id，不是之后重试的 id；所有交互共用 `ids`，id 不会重复。
- 一个 chunk 是一条 CSV 记录，要用 csv 模块写：交互名 `C, "the docs"` 带逗号和引号，手工拼逗号会坏。
- 行一决定就输出。测试里的“用户”要看到前面的行才给下一个审批，攒到最后再输出会卡住。
- 所有交互都结束了就结束，不要等审批流结束（用户之后不再说话）。审批流结束时还在等的轮次记为 denied。
- 日志里不能出现 prompt 文本。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出这里需要 async generator。

追问：

- "Two interactions of the same user race for the last 400 tokens. Who gets them?"（先被批准的那一轮；也可以在发起审批时预留、被拒时释放，代价是更复杂）
- "Should you ask the user to approve a round the budget can't cover?"（先查一遍再问，体验更好；但等待期间预算可能变化，批准时还要再查）
- "What belongs in this log, and what must never be in it?"（方法、输入键、决定、花费；课里明确不记敏感的 prompt 内容）
- "The approval UI disconnects. What happens to rounds that are waiting?"（审批流结束，等待中的轮次拒绝；生产里还要超时）

### Part 5 阶段图（目标 12 分钟）

坑：

- 环检测要分清“在当前路径上”和“已经算过”。pick → summarize 和 pick → narrow → summarize 汇到同一个阶段，是菱形，不是环；只用一个 visited 集合会误报。
- 轮数是最长路径（这里是 4），不是广度优先的层数（3），也不是阶段个数（DIAMOND 有 4 个阶段，一次运行只走 3 个）；DONE 不算一轮。最长路径超过 max_rounds 就拒绝：max_rounds=4 可以，3 不行。
- 要报 ValueError 的情况：起点没定义、下一阶段没定义（`sumarize` 拼错）、阶段没有出口、从起点到不了的阶段、环。不检查未定义的阶段，会在递归里漏出 KeyError。“到不了”要从起点走一遍来算，不能看“有没有阶段指向它”：测试里有一个只指向自己和 summarize 的 legacy，有入边，但从 pick 走不到。
- 阶段没有出口时，求最长路径的 `max()` 碰到空序列本身就会抛 ValueError，所以漏写这项检查也能过测试。看到这种写法可以问候选人是不是有意的。
- advance 只信状态里的 phase，不能从答案的键反推阶段。本轮答案的键必须恰好是这一阶段问的那一个，多一个、少一个都是 -32602；陈旧的 requestState 配上新一轮的答案就是这样被挡住的。
- 记下的是 handle 返回的校验后的值，不是原始文本，之前各轮的值要保留；narrow 这一轮只能在第 1 轮校验过的文件里选。返回新状态，传进来的 state 不能被改。
- 下一轮是 round + 1；走到 DONE 时轮数不再加一。状态里不认识的阶段（包括已经 DONE 的）是 -32602；handle 给出 then 里没有的 outcome，是服务器自己的流程写错了，和 plan 一样抛 ValueError，不能漏出 KeyError。
- 同一轮用同样的答案重试，得到同样的下一个状态。

追问：

- "A client replays round 2's requestState with the same answer. Can a stateless server stop that?"（不能。短过期时间限制了窗口；要么一次性存储，那是第 12 课的内容，要么让每一轮都幂等）
- "You change the flow and redeploy while tokens are in flight. What breaks?"（旧阶段可能不存在了，得到 -32602；把流程版本写进状态，旧阶段保留到令牌过期）
- "Why check the graph when the server starts instead of on each request?"（尽早失败；轮数上限是流程本身的性质，要和主机的上限对得上）
- "How would you allow critique to send the flow back to summarize once?"（在状态里记访问次数，按轮数封顶；plan 就不能再要求无环）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出信任边界、密钥轮换、预算竞争、重放和部署 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
