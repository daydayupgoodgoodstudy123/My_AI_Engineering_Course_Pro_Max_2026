# 面试官手册：conformance（13/31）

候选人计时期间不要看。候选人手里只有 README、`conformance/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档和本课讲义。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | `tokenCount` 里有 token，要脱敏吗？ | "No. Only keys whose canonical form is on the denylist." |
| 1 | 健康窗口缺了某个字段，用默认值算吗？ | "No. A missing or mistyped observation fails the window." |
| 1 | `Active` 或 `deprecated` 算可用的回滚目标吗？ | "No. Only the Registry's exact value active." |
| 1 | 回滚证据签名是对的，还要检查字段格式吗？ | "Yes. The signature says who vouched for it, not that the pins are digests." |
| 2 | 存的时候能把头名统一成小写吗？ | "No. Store what was captured. Normalize names only when you compare." |
| 2 | 两个用例名映射到同一个文件怎么办？ | "Refuse the second one with a ValueError, and leave the first file alone." |
| 2 | 同一个用例名再存一次呢？ | "That's a re-recording. Replace the fixture." |
| 2 | 哪些值算易变？ | "Only the members in VOLATILE, and only when they're non-empty strings." |
| 2 | 手写的夹具没有 era 呢？ | "Refuse it with a ValueError. Never guess the era." |
| 3 | 结果里有不认识的字段，算违规吗？ | "No. Unknown members are additive. An unknown resultType is not." |
| 3 | 其他 JSON-RPC 错误码对应什么 HTTP 状态？ | "Only the four codes in PROTOCOL_ERROR_STATUS are pinned. Don't check the others." |
| 3 | 一个响应同时违反好几条规则，报哪条？ | "The first one in the docstring's order." |
| 3 | 负例的响应违反的是另一条规则，算通过吗？ | "No. A negative case proves the rule it names." |
| 4 | 同一个视图来了两次？ | "Keep the first copy, ignore the rest." |
| 4 | 一个 exchange 报告之后又来了它的视图？ | "Ignore it. One line per exchange." |
| 4 | 超时用哪个时钟？ | "The capture times in the events. No wall clock." |
| 4 | 几个 exchange 同时超时，按什么顺序输出？ | "The order they first appeared in." |
| 5 | SDK 去掉了工具描述里的 `_meta`，算记账字段吗？ | "Only if allowed names that object. By default only the result root has bookkeeping." |
| 5 | 列表要先对齐（LCS）再比吗？ | "No. Compare by position." |
| 5 | SDK 给 legacy 结果补了一个 resultType，要报吗？ | "Yes, as synthesized. The allowance is for dropping, not adding." |

## 每关：要看什么、提示、追问

### Part 1 修发布闸门（目标 10 分钟）

一个测试里叠了 4 个缺陷，其中一个有两处，外加一个护栏：

1. `redact` 拿原始键名去查 `SECRET_KEYS`，而 `SECRET_KEYS` 里存的是规范化后的形式（`xapikey`、`clientsecret`）。`Authorization`、`X-Api-Key`、`access_token`、`client.secret`、`Set-Cookie` 全部漏掉。报错出现在闸门的报告上（报告里能找到 Bearer token），根因在两层调用之下：`ReleaseGate.evaluate` → `_transcripts` → `redact`。同一个文件里的 `canonical_field_name` 写好了，却没人调用。命中的键整个值都换掉，值是对象或列表也一样；只替换字符串值、遇到对象就往里递归的写法会被 `{"secret": {...}, "Cookie": [...]}` 抓住。
2. `evaluate_health` 缺字段时用了会通过的默认值：`sampleCount` 缺失按 `min_samples` 算，`errorRate`、`p95Ms` 缺失按 0 算。一个没有任何样本的 canary 被判健康，闸门直接 promote。只把默认值改成会失败的值还不够，字符串 `"1200"` 会在比较时抛 TypeError。`sampleCount` 是计数，`1200.0` 也算类型不对，三个字段一律用 `(int, float)` 检查会在这里挂。
3. `rollback_evidence_ready` 有两处：状态只拦 `deleted`，`deprecated`、`Active`、缺失都放行；三个 pin 只检查是非空字符串，`sha256:` 前缀、`pending`、64 个 z 都算摘要。
4. `evaluate` 在给每个用例算摘要的推导式里调用 `self._transcripts(cases)`，每个用例都把整个语料脱敏一遍，O(n²)。320 个用例在本机约 1.5 秒（机器很忙时到 5 秒），修好后约 7 毫秒（很忙时中位数 14 毫秒），限值 0.15 秒。
5. 护栏：摘要必须对脱敏后的证据计算。只换一个凭证的值，用例摘要和整包摘要都不变；改一个非秘密字段，两者都变；每个用例的摘要只覆盖它自己的证据，并且等于 `digest(redact(evidence))`。为了提速改成对原始证据求摘要、按用例名缓存摘要、只对名字和结果求摘要，都会在这里挂掉。

看什么：是不是先看报告里到底留下了什么，再顺着调用链往下找；是不是先 `print(canonical_field_name("X-Api-Key"))` 这类小实验；每改一处就重跑；改 `evaluate_health` 时有没有想到类型。

提示：
- H1："Which function decides that a key is secret, and what exactly does it compare?"
- H2："Print the key as it arrives and what is in SECRET_KEYS."
- H3：直接指出 `key in SECRET_KEYS`。后面几层同样先问再指：`"What does a missing sampleCount become?"`、`"Which Registry statuses can a version have?"`（active、deprecated、deleted）、`"How many times is redact called for 320 cases?"`

追问：
- "Why hash the redacted bundle and not the raw one?"（摘要要证明是哪一份脱敏证据做出的决定，又不能泄露被删掉的值；对原始证据求摘要，换一次凭证摘要就变，短凭证还能被穷举出来）
- "A key named query holds a customer's address. Does the denylist help?"（不能。按方法的参数策略处理，课里专门说了）
- "errorRate arrives as NaN. What does your code do?"（`nan > 0.01` 是 False，用 `>` 判断会放行；写成 `not value <= limit` 或先查 `math.isfinite` 才会拒绝）
- "Where does the signing key live in production?"（KMS 或公钥证明，测试里的 key 是公开的固定值）
- "Why hold instead of rolling back when the target is not verified?"（回滚到一个没有证据的版本等于猜）

### Part 2 transcript 夹具目录（目标 11 分钟）

坑：
- 头名要保留原样。夹具里有一个负例同时带 `Mcp-Method` 和 `mcp-method`，存或读的时候统一成小写，两个头就合成了一个。比较时才归一，存的时候不归一。
- 文件名是有损的 slug，准确的名字存在文件里面。所以 `names()` 要读文件内容，`load` 要核对文件里的名字；只靠文件名，`Golden Résumé Lookup` 会变成 `golden-r-sum-lookup`。
- 两个名字映射到同一个文件要报 ValueError，而且要在写之前报，不能先覆盖再报错。比较名字要精确：用 casefold 比较的话，`GOLDEN-MODERN-LIST` 会悄悄覆盖 `golden-modern-list`。文件名规则先转小写，也是因为 macOS 默认的文件系统不区分大小写，只差大小写的两个文件名本来就是同一个文件。
- 同一个名字再存一次是重新录制，直接替换。
- era 和每条 transcript 存在同一个文件里。读到没有 era 的文件，或者 era 写成了 `2026-07-28` 这种协议版本，都要报 ValueError，不能默认成 modern。
- 精确往返：`capabilities` 存成排好序的列表、读回 frozenset。只写 `list(capabilities)` 时顺序随每次运行的哈希种子变，两个能力的夹具有一半的运行碰巧是有序的，所以测试另存一个带 8 个能力的夹具，乱序几乎每次都会被抓住；没有 body 存成 null、读回 None，不能变成 `{}`；`expect` 的 -32020 读回来还是整数。
- 易变值在写入前归一化，任意深度都要处理，包括请求参数里列表中的 `createdAt`。只替换非空字符串：负例里的空字符串、数字和 null 本身就是证据，替换掉负例就失效了。不能原地修改调用方传进来的 transcript。
- 同样的行为录两次，写出的文件要逐字节相同。
- 不能缓存在内存里：另一个 `TranscriptCorpus` 实例存的东西，这个实例要马上能读到。

追问：
- "Why one JSON file per case instead of SQLite?"（夹具要进版本控制，能在 code review 里看 diff；课里说 fixture schema 存在版本控制里）
- "How would you record a literal null body as opposed to no body?"（解析后的 JSON 分不出来，要存原始字节，比如 base64 或单独的 bodyBytes 字段）
- "The Mcp-Name header mirrors a taskId. What does normalization do to it?"（头和 body 要一起归一，否则夹具里凭空多出一个头与 body 不匹配；这套题只归一 body 里的成员）
- "Two people re-record the same fixture at once?"（先写临时文件再 rename，冲突交给 code review）

### Part 3 响应一致性校验（目标 13 分钟）

坑：
- `futureHint` 这种附加字段要接受，未知的 `resultType` 要拒绝。`resultType` 是一个对象时，`in set` 会抛 TypeError，要先判断类型。
- 先查判别字段，再查方法载荷：`resultType: "surprise"` 加上坏掉的 `tools`，报的是 `unknown-result-type`。
- legacy 时代缺 `resultType` 视为 complete，但方法载荷照样要查，而且要用推断出来的 complete 去查。拿原始结果里的 `resultType` 和 complete 比较，会把合法的 legacy `tools/list` 判成 `method-result-type`。legacy 只豁免缺失，不豁免未知值。推断出来的 complete 不能写回原始结果，否则 harness 自己就成了“替 SDK 合成判别字段”的那一方。
- `tools/list` 和 `completion/complete` 只能 complete；`task` 既要声明 Tasks 能力，又只能用于 `tools/call`。测试用 `server/discover` 单独考第二条，因为 `tools/list` 已经被第一条拦住了。
- 载荷边界：100 个补全值可以，101 个不行；`total` 等于值的个数可以；缺 `tools` 数组或缺 `values` 不能当成空列表；`ttlMs` 必须出现但可以是 null，0 是合法的非负数；描述是空字符串不行。
- 布尔值不是整数：`isinstance(True, int)` 为真，`total: true` 和 `ttlMs: true` 都要拒绝，课里的代码也专门排除了 bool。错误码是 `true` 的情况测试没有单独考，候选人主动排除可以加分。
- 已知协议错误的状态：-32020、-32021、-32022 要 400，-32601 要 404，其他错误码不检查；结果必须是 HTTP 200；`result: null` 是中间件把 handler 的 None 包成了成功响应。没有 body 用 `body is None` 判断：`{}` 是一个 body，只是不是 JSON-RPC 响应，报 `envelope`；用真值判断会报成 `missing-body`。
- 通知只能得到 202 且没有 body：`{"jsonrpc": "2.0", "result": null}`、`{}`、204 都不行。只看状态码、用真值判断 body，都会放过其中一种。
- `check_case`：负例要证明它自己点名的那条规则，违反别的规则不算通过；期望错误码的负例，要求响应是合法的 JSON-RPC 错误并且码对得上，HTTP 500 带 -32020 的 body 不算。
- 最后一段把 Part 1–3 串起来：夹具存进目录、`run_corpus` 跑一遍、结果交给闸门，全部通过才 promote，加一个预期错了的夹具就 rollback。

追问：
- "Why does an unknown resultType fail while futureHint passes?"（判别字段决定生命周期，客户端不知道自己会丢掉什么；附加字段不改变怎么处理这个结果）
- "Where do the capabilities come from in a real run?"（每个现代请求的 `_meta` 里声明，扩展要协商过）
- "How would request-scoped SSE change this validator?"（每个事件都是一个 JSON-RPC 消息，要逐个按选定的时代校验，还要记录事件顺序和流怎么结束；课里的 Practice Lab）
- "A -32022 comes back. Should the client retry on the legacy era?"（不能。认得的现代错误证明对方是现代时代，降级会掩盖问题）

### Part 4 代理三视图 TAP（目标 14 分钟）

坑：
- 输出格式由测试决定：每个 exchange 一行 `ok N - id` 或 `not ok N - id # 原因`，原因按固定顺序用 `; ` 连接，最后是计划行 `1..N`，每行以换行结尾；没有 exchange 时只输出 `1..0`。
- 三个视图到达顺序任意，egress 可能最先到。只在 ingress 到来时才建 exchange 的写法会挂。
- 同一视图重复投递只算一次，而且留第一份：后到的副本 body 不同也不能覆盖，`views[view] = event` 会把一个保留了 body 的 exchange 判成 body 被改。凑齐三个不同的视图才算完整，数事件的写法会提前报告。已经报告的 exchange 再来视图要忽略，不能重新打开，否则后面会多出一行“证据不完整”。
- 判定前先脱敏：egress 那边的采集器发出之前已经脱敏，origin 没有。直接比较原始 body，凡是带凭证的响应都会被判成 body 被改了。
- 判定规则：origin 回 400 或 404 且 body 是 JSON-RPC 错误、客户端拿到 500，是 collapse，只报 collapse，不再同时报状态变化；HTML 的 400 变 500 只是状态变化。
- 超时：截止时间是这个 exchange 第一个事件的 `at` 加 `timeout_ms`；时钟是目前见过的最大 `at`；严格小于才算超时，正好落在截止时间上不算；先应用事件再检查超时，所以 exchange 还开着时到的视图都算数，哪怕它的捕获时间已经过了截止时间；同时超时的按第一次出现的顺序输出；一个刚出现就已经过了截止时间的 exchange 要立刻报告。截止时间按第一个到达的事件算，测试里每个 exchange 的捕获时间都是递增的，分不出“第一个到达”和“最小的 `at`”，用后者的写法测试会放过，可以追问乱序时两者有什么不同。
- 拼齐即输出：测试数被拉取了多少个事件，攒到最后再统一输出会挂。

追问：
- "reported grows forever. What would you do?"（时钟走过截止时间再加一段宽限期后清掉；之后再来的事件记成孤儿事件）
- "The collectors' clocks disagree by two seconds. What breaks?"（截止时间会算错；可以用接收时间，或者用允许一定迟到的 watermark）
- "Comparing in redacted form: what can you no longer prove?"（秘密值本身被改了看不出来，这是脱敏的代价）
- "What happens if the consumer of the TAP stream is slow?"（async generator 只在被拉取时才往前读，不会无限缓冲）

### Part 5 SDK 差分（目标 12 分钟）

坑：
- 记账字段只能在 `allowed` 指定的对象里、而且只能被删掉：结果根上的 `resultType`、`_meta`、`ttlMs`、`cacheScope` 被 SDK 去掉不报；SDK 补出来一个 `resultType`（合成），或者把 `input_required` 改成 `complete`（修改），都要报。工具描述里的 `_meta` 不在根上，被删掉就要报，除非 `allowed` 用 `/tools/0` 这样的指针点了名。
- 路径是 RFC 6901 JSON Pointer：名字里的 `/` 写成 `~1`，`~` 写成 `~0`，而且要先替换 `~` 再替换 `/`，顺序反了 `~1` 会变成 `~01`。
- 列表按位置比较，不做对齐；SDK 少了尾部的元素报 dropped，多出来的报 synthesized。
- `12` 和 `"12"` 不相等，`true` 和 `1` 也不相等：Python 的 `==` 认为 `True == 1`，直接用 `!=` 比较会漏掉 SDK 把布尔值变成整数；列表变成对象整体算一次 changed，不往下递归。
- 值为 null 的成员和不存在的成员不同。
- 报告顺序：深度优先，对象成员按名字排序（两边的名字合在一起排），列表按下标。如果最后把路径当字符串排序，`/values/10` 会排到 `/values/2` 前面。
- lifted：名字相同、值相等、新位置在原对象的祖先里，才算一次提升，报在原位置。值不同就是一删一增；横向移动不算提升，更浅的位置也不一定是祖先：`/stats/page/total` 到 `/s/total` 不是提升，用不带 `/` 的前缀比较或者只比层数都会把它当成提升；一个合成的成员只能和一个被删的成员配对；能从列表元素里提升到根。新位置有时排在前面（`/city` 在 `/structuredContent/city` 之前），一遍扫描边找边输出的写法会先把它报成 synthesized，再报一次 lifted，所以要先配对，再按顺序输出。
- 最后一段接回闸门：丢了 `futureHint` 的 SDK 视图让闸门 rollback，保留它就能 promote。

追问：
- "Your component is a transparent proxy, not an application. What changes?"（应用可以有意忽略附加字段，透明中间层应该原样转发，这是要写进发布策略的选择）
- "Two SDKs normalize the same transcript differently. Which one is right?"（事先在发布策略里写明可接受的行为，不要事后挑方便的）
- "Why not align lists with LCS?"（按位置比较反映 SDK 实际做了什么；对齐会把重排藏起来，代价还是 O(n·m)）
- "1 and 1.0: same value or not?"（canonical JSON 认为不同；JSON 本身不区分整数和浮点数，看策略）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出脱敏边界、时钟、发布策略、失败处理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
