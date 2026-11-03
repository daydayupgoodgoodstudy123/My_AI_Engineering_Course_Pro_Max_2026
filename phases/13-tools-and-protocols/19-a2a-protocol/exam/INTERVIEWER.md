# 面试官手册：agentcard（13/19）

候选人计时期间不要看。候选人手里只有 README、`agentcard/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 两个 data part 都带 targetLength 用哪个？ | "The first one. The tests don't cover it." |
| 1 | 回复里还是没有 targetLength，算失败吗？ | "No. Ask again. The task waits in input_required." |
| 1 | 回复一个已经结束的任务，要不要把消息记下来？ | "No. Raise TaskError and leave the task exactly as it was, messages included." |
| 1 | 未知的 task id 怎么办？ | "KeyError, as the docstring says." |
| 1 | writer 要不要按 inputModes 检查 part 类型？ | "Not here. Only the skill id. Say what you'd add." |
| 1 | 能不能等到 finish() 再统一解码？ | "No. received grows as chunks arrive, and a bad group fails as soon as it's complete." |
| 2 | 能不能把整个任务存成一个 JSON？ | "Not the file bytes. They go in a BLOB, as they are. The rest is your call." |
| 2 | 再存一次是追加还是替换？ | "Replace. The task as it is now replaces whatever was stored for that id." |
| 2 | data part 的键顺序要保留吗？ | "Yes. Exactly as saved: key order and number types too." |
| 2 | task_ids 按什么顺序？ | "Sorted by id." |
| 2 | save 中途失败怎么办？ | "Nothing changes. The store keeps what it had." |
| 3 | 卡片上的 kid 不在 keys 里，能不能换一个 key 试？ | "No. Then the card doesn't verify." |
| 3 | 好几个 skill 都满足？ | "The first one in the card's order." |
| 3 | skill 的 inputModes 必须和消息的 part 类型完全一样吗？ | "No. It has to take every type the message has. It may take more." |
| 3 | 来源可信的话，没签名的卡片能用吗？ | "No. An unsigned card is refused." |
| 3 | 比较签名要不要常数时间？ | "Yes, hmac.compare_digest. The tests can't see it; I will." |
| 3 | artifact 能不能当输入模式？ | "No. Inputs are text, file and data. Outputs are text and artifact." |
| 4 | 4 字节长度包不包括它自己？ | "No. It counts the JSON bytes only." |
| 4 | 能把几帧合成一次 yield 吗？ | "No. One frame per yield, each as soon as it's ready." |
| 4 | 空的 piece 要不要发帧？ | "No, and it doesn't take a seq number." |
| 4 | 调用方关掉流的时候，要不要发一个 canceled 帧？ | "You can't, the stream is closed. Close the model's stream and cancel the task." |
| 4 | JSON 里的中文要不要转义？ | "Either way. The length has to match the bytes you send." |
| 4 | 调用方读到 final 帧以后才关闭流，任务要不要改成 canceled？ | "No. It has already completed, and a finished task never changes." |
| 5 | client 的委托算第 0 跳还是第 1 跳？ | "Hop 1." |
| 5 | 被拒绝的任务下面的委托要不要出现？ | "No. It never ran, so it never delegated anything." |
| 5 | 任务自己失败了，它的下游还跑不跑？ | "Yes. It runs its delegates first, then fails." |
| 5 | 调用方能看到更深一层的 artifact 吗？ | "Only if every task on the way forwards it." |
| 5 | plan 里两个任务用了同一个 id？ | "ValueError." |
| 5 | 有环怎么办？ | "Not in this plan. A plan is a tree." |

## 每关：要看什么、提示、追问

### Part 1 修 writer 和下载（目标 10 分钟）

一个测试里叠了 4 个缺陷和一个护栏：

1. `target_length` 只看第一个 data part。第一条消息的 targetLength 在三个 data part 的中间那个，任务停在 input_required，没有 artifact。错误不在 `tasks_send` 里报出来，而是两层调用之外：`read_report` 调 `artifact_chunks`，在那里报 `AttributeError: 'NoneType' object has no attribute 'parts'`。
2. `tasks_send` 不看卡片上有没有这个 skill：`translate_paper` 照样 working、completed。应该从 submitted 直接到 rejected，再加一条点名这个 skill 的 agent 消息。
3. `tasks_reply` 不看终态：回复一个 completed 的任务，它会重新 working、重新 finish，artifact 被换掉，历史多出两步。应该在改动任何东西之前抛 TaskError；rejected 的任务也一样。
4. `ArtifactAssembler.add` 每收到一片，都把累积的整段 base64 重新解码校验。2 万片、共 18 万字符，本机要 1.2 到 1.5 秒，负载重时到 3.6 秒。只解码新凑齐的 4 字符组、把不满一组的余数留到下一片，2 万片只要 4 毫秒左右。限值是 0.12 秒。
5. 护栏：分片的边界不落在 4 字符上（`read_report` 用 7 个字符一片，计时用 9 个）。每片单独 `b64decode` 会报 Incorrect padding；每片补 `=` 再解码会报错或者拿到错的字节；把解码推迟到 `finish()` 虽然快，但 `received` 不再随分片增长，坏的组也不会在凑齐时报错。重写 `add` 时去掉了 `validate=True` 也不行：默认模式会悄悄丢掉不在字母表里的字符，测试里一组 base64url 的 `----` 必须报错。

`tasks_reply` 写成“不是 input_required 就抛 TaskError”比 docstring 更严，测试不区分，可以接受。

用 `bytes +=` 累加的修法要 30 到 45 毫秒，保留整段文本、只解码新部分的修法要 50 到 65 毫秒，都能过，但都还是平方级的拷贝，可以在追问里问。

看什么：是不是先看 `artifact` 为什么是 None，再去查任务停在什么状态；是不是先 `print(sent.history, sent.messages[-1])`；改终态检查时是不是想到了“先检查，再动任何东西”；提速之前有没有先说清楚分片边界和余数。

提示：

- H1："Why is there no artifact on that task? What state is it in?"
- H2："Which data part holds the targetLength in that message? Which one does target_length read?"
- H3：直接指出 `data[0]`，以及 `add` 里每次解码的是 `self._text` 的全部。

追问：

- "Why reject an unknown skill instead of failing it?"（rejected 是“不接这个活”，没开始干；failed 是干了但出错。调用方据此决定换 agent 还是重试，讲义的终态里两者分开）
- "Should the writer also check part types against inputModes?"（应该，不接受的 part 类型也是 rejected；讲解里列为改进项）
- "Your fix still copies the received bytes on every chunk. Does it matter?"（`bytes +=` 每次都复制一遍，总量还是平方级；用 bytearray 或者先收集再 join）
- "Why validate as the chunks arrive, not at the end?"（坏数据早发现，可以早断开；另一个 agent 的输出是不可信数据）

### Part 2 SQLite 任务库（目标 13 分钟）

坑：

- file part 的字节原样存成 BLOB。用 latin-1 解码成文本或者存 base64 文本，读回来都一样，但测试会扫描数据库文件里每张表的每个值，找不到原样的 BLOB 就挂。空文件 `b""` 也是文件，不能存成 NULL。
- part 的顺序：第一条消息是 data、text、file、file、text 混排。按类型分表存再拼回来，或者 `ORDER BY type`，顺序就乱了。
- 消息有 13 条，序号要按整数排。序号放在文本列里，`'10'` 会排在 `'2'` 前面。
- data part 原样往返：键的顺序（`"zone"` 在 `"draft"` 前面），以及每个值的类型：3 是 int，1.0 是 float，True 是 bool，12345678901234567890 超出 64 位。`json.dumps` 加 `json.loads` 都能保住。`sort_keys=True` 会改键序；经过 SQLite 的 JSON 函数或者 REAL、NUMERIC 列，True 变成 1，大整数变成浮点数。Python 里 `1 == 1.0`、`True == 1`，所以测试另外逐个比较类型。
- 历史里 working 和 input_required 会重复出现。按集合存，或者给 (task_id, state) 加唯一约束再 `INSERT OR IGNORE`，都会丢掉重复。
- 再存一次是替换：只插不删，要么撞主键，要么读回来重复。
- `load` 返回的是存进去的样子，不是传进来的那个对象。把 save 时的对象缓存起来直接返回，任务后来的变化就会“自己”出现在库里。
- 一次失败的 save 不能留下半截。先在一个事务里删旧行、再在另一个事务里插新行，或者手动 commit 而出错时不回滚，同一个连接上都能看到半截状态。参考实现先把所有行算好（未知 part 类型在这一步就报 ValueError），再在一个 `with self._db:` 里删和插。
- `task_ids` 按 id 排序。重开要 `IF NOT EXISTS`。

追问：

- "A 200 MB PDF?"（整块 BLOB 要一次读进内存；可以分块存，或者文件放对象存储，库里只存哈希和大小）
- "Two writer processes?"（SQLite 一次只有一个写者；一个任务只让一个 worker 推进，或者给任务加版本号做乐观锁）
- "Why keep the whole history?"（不透明不等于不可审计：任务 id 和状态时间线都应该记下来）
- "How long do we keep messages?"（file part 里可能有敏感内容，要有保留期和删除流程）

### Part 3 卡片、签名与选 skill（目标 13 分钟）

坑：

- 规范 JSON：去掉 signature 字段，每一层都 `sort_keys`，分隔符是 `","` 和 `":"`，`ensure_ascii=False`，再编码成 UTF-8。卡片描述里有 `résumés, 引用`，默认的 `ensure_ascii=True` 会写成 `\u` 转义，签名就和发布方的对不上。测试第一条断言就是拿发布方签好的卡片来比，签名值写死在测试里。
- 签名值是 base64url，不带 `=`。标准 base64 会出现 `+` 和 `/`，hex 也不对。
- `sign_card` 返回新字典，不改传进来的卡片。再签一次要换掉旧签名，规范 JSON 里不能带着旧签名。
- `verify_card`：alg 必须是 HS256（只把 alg 改成 none、MAC 不变的卡片也要验不过）；kid 必须在 keys 里，不能退而用别的 key；缺 kid、缺 signature 都返回 False，不能抛 KeyError；改了任何字段（嵌套的 inputModes、capabilities、新加的字段、删掉的 skill）都验不过。比较用 `hmac.compare_digest`。签名值多带了 `=` 也接受的宽松写法测试不管，可以接受，但要问候选人为什么不按 docstring 的编码严格比较。
- `check_card`：测试里每条规则都有一张坏卡。字符串 `"false"` 和数字 `1` 都不是布尔值（`in (True, False)` 会放过 1）；空字符串不算有值（顶层的 description、skill 的 name）；`https:///a2a` 没有主机，只看 `https://` 前缀不够；缺字段要报 CardError，不能漏出 KeyError；inputModes 不能为空；skill id 不能重复；http 和相对 URL 都不行；outputModes 只能是 text 和 artifact。
- `choose_skill`：inputModes 要覆盖消息里每一种 part 类型（是子集，不是相等，也不是有交集）；outputModes 要包含 wants；按卡片声明的顺序取第一个，不按字母序，也不挑“最贴合”的；都不满足返回 None，不回退到第一个 skill；空消息报 ValueError，因为空集合是任何集合的子集。
- 交付方式看 `capabilities.streaming`，不看 `pushNotifications`。
- 最后一段是端到端：签好的 writer 卡片经过 discover、choose，交给 Part 1 的 `WriterAgent`。

追问：

- "The lesson says publishers sign with a JWT. Why is HMAC not enough for a public card?"（HMAC 是对称密钥，能验证的人也能伪造；公开的卡片要用非对称签名，消费方只拿公钥）
- "How do you rotate the key?"（kid 就是为这个：一段时间内新旧两个 key 都放在 keys 里）
- "The card says it takes files. Do you trust that?"（卡片是自述；还要契约测试、注册表准入，对方的 artifact 当作不可信数据处理）
- "Why canonical JSON instead of signing the bytes you fetched?"（中间层可能重新排版；规范化让同一张卡片只有一种字节表示。代价是各语言的序列化细节要完全一致）

### Part 4 长度前缀帧（目标 13 分钟）

坑：

- 帧格式：4 字节大端无符号长度，后面恰好是这么多字节的 UTF-8 JSON，长度不包括它自己的 4 字节。用小端或本机字节序、长度多加 4，测试自己的解析都会挂。
- 长度按编码后的字节数算。默认的 `json.dumps` 会把中文写成 `\u` 转义，字节数和字符数一样；改用 `ensure_ascii=False` 还按字符数算长度就会挂。这个陷阱本章 03 和 11 已经练过，这里不单独设题。
- 每一帧单独 yield，一准备好就 yield：working 在向模型要第一片之前发出，模型每写一片就发一片。先收集再一起 yield、拼成一个 bytes 再 yield、先把模型读完，都会被探针抓住。
- seq 从 0 开始数，空片不发帧，也不占号。
- 模型抛 ModelError：最后一帧是 final 的 failed，带上 message；任务 failed，没有 artifact；后面不能再发 completed；异常不能漏给调用方。
- 调用方提前关闭：GeneratorExit 在 yield 那里抛出来。要在 `except GeneratorExit`（或者 finally）里把任务改成 canceled，并且 `await` 模型流的 `aclose()`。不显式关闭的话，模型那边的 finally 要等对象被回收以后由事件循环另外安排，测试检查的那一刻还没有跑。发 working 的那个 yield 也要在 try 里面，否则刚收到 working 就关闭，任务会停在 working。反过来，发 completed 的那个 yield 不能在处理 GeneratorExit 的 try 里：调用方读到 final 帧就关闭流时，已经 completed 的任务不能被改成 canceled。final 帧发出时，任务必须已经 completed、artifact 已经挂上，不能先发帧再改状态。
- artifact 的名字用参数 `artifact`，测试最后一段传的是 `summary`，写死 `report` 会挂。
- `FrameReader`：缓冲字节，只交出完整的帧；长度超过 MAX_FRAME 立刻报错，不等正文；恰好 MAX_FRAME 是可以的；一次 feed 里可能有好几帧，也可能只有半个长度；final 之后的任何字节都报错，包括和 final 在同一块里的；seq 按 artifact 的名字分别计数（测试里 report 和 citations 交错出现）；close 时停在帧中间或者还没有 final 都报错。

追问：

- "Why a length prefix instead of newline-delimited JSON?"（正文里可以有任何字节；读端知道还要等多少；代价是必须防住超大的长度）
- "What does MAX_FRAME protect?"（一个恶意的 4 字节长度就能让读端准备接收 4 GB）
- "The caller reconnects halfway. How does it catch up?"（seq 告诉调用方收到了哪里；服务端要能从某个 seq 重放，或者调用方改成轮询把缺的补上）
- "Backpressure?"（async generator 是拉模式：调用方不读，writer 就不会向模型要下一片）

### Part 5 多跳委托视图（目标 11 分钟）

坑：

- 只看得到直接下游：视图只有 task、agent、state、artifacts 四个键；artifact 只留 name、mimeType、parts（source 是内部字段）；steps 永远不出现。
- artifact 只沿着 forward 往上走，而且每一跳都要 forward。t-pdf-1 的 figures 经过 t-research（forward）到了 coordinator，coordinator 也 forward 了 t-research，所以 client 看得到；t-pdf-2 的 figures 到了 writer，但 writer 没有被 forward，client 看不到。转发的是下游“返回的东西”，包括它自己转发上来的，而不是下游 plan 里的 artifacts 列表。多个转发按委托顺序排在任务自己的 artifact 后面。
- 失败不会自动往上传：可选的 t-web 失败了，t-research 照样 completed；必需的 ocr 被拒，t-pdf-2 失败，可 t-pdf-2 对 writer 是可选的，writer 照样 completed。required 默认是 true。
- 跳数：client 的委托是第 1 跳；超过 max_hops 的任务是 rejected，它的下游从来没发出去，结果里不出现。
- 自己失败的任务也先跑完下游（把 coordinator 改成 fails 以后，它的视图还在）。
- 同一个 agent 的两个任务互不相干：两个 pdf-reader 一个 completed、一个 failed。结果按 task id 记，不能按 agent 记，也不能按 agent 缓存结果。
- 结果里只有跑过、而且委托了东西的任务；没有下游的任务不放空列表。
- 不改输入的 plan：用 `setdefault` 补默认值会把默认值写进去。
- 重复的 id 要在运行之前查整棵树。测试里有一对重复的 id 都在超过 max_hops 的子树里，这两个任务从来不运行，只在兄弟之间查或者只查跑过的任务都会漏掉。

追问：

- "How would the client even know a task was delegated further?"（按不透明原则它不该知道；它只看到状态和返回的 artifact）
- "How do you trace this end to end without breaking opacity?"（每一跳只上报自己这一跳；跨组织的部分不传内部细节）
- "Where would you enforce max_hops in a real system?"（剩余跳数随任务往下传，每一跳自己检查，不能只靠根节点）
- "What about a cycle, A to B and back to A?"（本题不考；实际系统靠跳数上限，或者在委托链里带上已经经过的 agent）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出非对称签名与密钥轮换、大文件与保留期、帧大小上限与断线续传、跳数上限与追踪 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
