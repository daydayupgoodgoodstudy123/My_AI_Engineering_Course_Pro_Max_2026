# 面试官手册：CloneGate（06/08）

候选人计时期间不要看。候选人手里只有 README、`clonegate/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 检测时能用原始音频吗？ | "No. Verification happens later, somewhere else, with only the clip and the key." |
| 1 | 分块喂入时，码片从哪里开始？ | "From the start of the clip or stream, once. Chunk boundaries don't matter." |
| 2 | 时间统一存成 UTC 行吗？ | "Compare in UTC if you like, but give back exactly what was signed, offset included." |
| 2 | 撤销两次怎么办？ | "The first revocation stands. It's permanent." |
| 2 | 到期那一刻还算有效吗？ | "No. Valid up to the expiry, not at it." |
| 3 | 能用 alice 在别的同意下录的音吗？ | "No. Only what was recorded under the consent that authorizes this conversion." |
| 3 | k 比匹配集还大怎么办？ | "ValueError. Don't shrink k silently." |
| 4 | 流结束时剩下不到 0.1 秒的尾巴怎么算？ | "Score once more at the end. The tail counts." |
| 4 | 确认之后还要继续读流吗？ | "No. One verdict, then stop reading." |
| 5 | 空的 all 和空的 any 怎么算？ | "An empty all allows. An empty any denies." |
| 5 | 遇到不认识的规则类型？ | "ValueError, wherever it sits. Fail closed." |

## 每关：要看什么、提示、追问

### Part 1 修水印代码（目标 10 分钟）

一个测试里叠了 4 个缺陷和 3 个护栏：

1. `Watermarker.chips()` 用的是 `__init__` 里建好的那个 `random.Random`，每次调用都接着上一次的位置往下取，没有回到密钥的起点。stamper 盖第二段 clip 时用的是第 32000 个以后的码片。错误不在 stamper 那里报出来，而是在另一个 verifier 读第二段时 bits 对不上。
2. `Evidence.scores()` 返回原始相关和，没有除以这一位样本能量的平方根。音量调到 0.1 倍，分数也跟着变成 0.1 倍。
3. `bit_accuracy` 只拿“有证据的位”当分母，没证据的位被悄悄排除，全是 None 时还会除零。
4. `Evidence.add` 每来一块，就把收到的全部音频从头再相关一遍。2 秒的音频分成 480 块喂进去要 0.75 秒左右，增量累加只要 3 毫秒。
5. 护栏：verifier 是另一个实例，从没见过原始音频。照课里的写法改成非盲检测（embed 时存下原始音频，detect 时相减），在 verifier 上直接报 AttributeError。
6. 护栏：分块喂入必须和一次喂入结果一致。复位是“每段 clip 或每条流复位一次”。如果改成每次 `add` 都从密钥起点重新取码片，分块的结果就错了。
7. 护栏：两条流同时检测。只在 `chips()` 开头加一句 `self._rng.seed(self.key)`，按顺序调用时看不出问题；两个码片迭代器同时存在时，它们共用一个 RNG、互相抢码片，测试最后一条断言会挂。每次调用要新建自己的 `random.Random(self.key)`。

看什么：是不是先想清楚“第二段 clip 的码片是谁生成的”，而不是只盯着 detect；是不是先 `print` 两次 `chips()` 的前几个值；每改一处就重跑。

提示：

- H1："Which object generated the chips that the second clip was stamped with?"
- H2："Call chips() twice on one Watermarker and compare the first few values."
- H3：直接指出 `chips()` 用的是 `self._rng`。

追问：

- "Why can the detector work without the original audio?"（宿主音频和码片不相关。对 m 个样本求和，水印按 m 增长，宿主只按 √m 增长）
- "What false-alarm rate does a threshold of 4 on all 16 bits give?"（无水印时每一位 |z| ≥ 4 的概率约 6e-5，16 位同时过线几乎不可能；真正的风险是归一化错了，或者宿主恰好和码片相关）
- "The lesson's Step 4 puts consent_id:abc123;ts:1745353200 in the payload. Does that fit?"（31 字节是 248 位，容量只有 16 到 32 位；载荷只放短 id，其余信息到登记表里查）
- "Would this survive an MP3 re-encode?"（不保证。真实系统在感知域嵌入，还要加同步和纠错）
- "What does Evidence hold after an hour-long call?"（原代码保存全部音频，内存 O(n)；改好后只有 2 × n_bits 个浮点数）

### Part 2 同意登记表（目标 12 分钟）

坑：

- id 必须是从 1 开始依次分配的小整数，因为要放进 16 位的水印载荷。用 UUID 会挂。
- 时间要原样读回，包括 +05:30 这样的偏移。转成 UTC 再存的话，datetime 之间比较仍然相等（比较的是时刻），但 isoformat 变了，签字日期也从 22 日变成了 21 日。
- Python 3.12 直接把 datetime 交给 sqlite3，用的是已经弃用的默认适配器，读回来是字符串。
- 不 commit 的话，关闭连接就丢数据，重开后报 KeyError。建表要写 `IF NOT EXISTS`。
- `active` 如果在 SQL 里用 ISO 字符串比较到期时间，不同偏移之间会比错：东京时间 5 月 1 日 0 点到期的同意，到了 UTC 4 月 30 日 15:00 还被当成有效。
- 有效区间是 [granted_at, expires_at)，下限也要查。只写 `at < expires_at` 的话，签字前一分钟（UTC 4 月 29 日 23:59，东京时间 30 日 8:59）的查询也会把 aiko 的同意算进来。
- 撤销是永久的：第二次撤销既不能覆盖第一次的时间，也不能报错。撤销当场生效，`at >= revoked_at` 就不再有效。
- naive datetime 一律报 ValueError。

追问：

- "How would you make this log tamper-evident?"（只追加的表，每条记录带上一条的哈希形成链，定期对链头签名；撤销作为新事件追加，不改旧行）
- "Why not delete a revoked consent?"（撤销前生成的音频是合法的，审计时要查得到；删除请求和审计保留有冲突，所以只存必要的个人信息）
- "Two API servers with skewed clocks?"（时间同步；同时记下服务端收到的时间；比较一律按时刻）

### Part 3 kNN-VC（目标 12 分钟）

坑：

- 用余弦距离，不是欧氏距离。目标说话人的帧整体响了 4 倍，欧氏距离会挑错帧。
- 取 k 个最近帧的均值，不是只取最近的一帧。
- 平票按匹配集里的先后顺序。`sorted((distance, frame))` 在平票时会去比较帧本身；按相似度升序排好再整个倒过来，平票会落到最后一帧。
- k 要在 1 到匹配集大小之间，k = 0 也报 ValueError。只查 `k > len(matching)` 的话，k = 0 会悄悄返回空帧。
- 匹配集只能是这条同意下登记的帧：不能混进 bob 自己的帧，也不能混进 alice 在另一条同意下登记的帧。那条同意覆盖广告和配音，这一刻也有效，但这次转换凭的是第一条同意。直接拿 Part 2 的 `active()` 把她所有有效同意下的帧都收进来，会在这里挂。
- 同意要在 `at` 这一刻覆盖这个用途，否则报 PermissionError：用途不对、到期那一刻、撤销之后都不行。查的是这一条同意，不是“alice 有没有覆盖这个用途的有效同意”：她的另一条同意覆盖广告，这次转换照样不能拿去做广告。
- 最后一段是端到端检查：转换结果盖上同意 id 的水印，再从音频追溯回这条同意记录。这一段用到了 Part 1 和 Part 2。

追问：

- "Why average k = 4 frames instead of taking the nearest one?"（输出更平滑，毛刺更少；kNN-VC 论文就用 k = 4）
- "How much target audio is enough?"（课里说大约一分钟。关键是音素覆盖，太少时有些音素找不到像样的邻居）
- "A million frames in the matching set?"（预先归一化，矩阵乘法，近似最近邻索引，按同意分片）
- "Where else does the consent gate belong?"（登记录音、生成、API、下载各处都要查；每个输出都要盖水印）

### Part 4 实时流监测（目标 14 分钟）

坑：

- 输出格式由测试的解析代码决定：Server-Sent Events，每个事件一行 `event:`、一行 `data:`（JSON），后面跟一个空行。
- 整条流只输出一个事件。确认后马上 yield，然后 return，不再读流。测试数两次被拉取了多少块：一次是拿到事件就 `aclose()`，一次是把生成器跑完。确认后用 break 跳出、再把剩下的流空读完的写法，第二次会数到 120 块。
- 打分时刻按样本数计：每 0.1 秒（1600 个样本）打一次分，和分块方式无关。一块跨过边界时要在边界处切开。只在每块结束时打分的话，`at` 会随分块变化；在边界之外每块结束时再多打一次分也不行，逐个样本喂入时会在 0.97 秒提前过线。用浮点数一次次累加 0.1 秒再换成样本下标，会在第 17599 个样本而不是第 17600 个打分。
- 证据要跨块累加。每块新建一个 Evidence，或者每块重新从密钥起点取码片，结果都会错。
- 流结束时要再打一次分：截到 1.05 秒的流，正是在结尾这一次过线。
- 没有水印的流以 `unmarked` 结束，`seconds` 是读到的样本数除以采样率。空流也一样。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要能看出这里需要 async generator。

追问：

- "Why sum the correlation across chunks instead of voting on bits chunk by chunk?"（累加的相关是最优统计量；逐块硬判决丢掉了信息，结果还取决于块的大小）
- "Why derive the verdict time from the sample count instead of checks × check_s?"（这里 11 × 0.1 恰好等于 1.1，测试分不出来；换成第 12 次就是 1.2000000000000002。样本数除以采样率只舍入一次）
- "Packets get lost in the call. What happens?"（缺一段会让码片错位；真实系统要有同步标记，或者按帧重新同步）
- "We watch 10,000 calls a day. What about false alarms?"（多重检验；按整个系统的误报预算定阈值，记录分数，抽样复核）
- "The caller hangs up mid-check?"（`aclose()` 让生成器停下；这里没有要清理的东西，真实系统要在 finally 里释放解码器）

### Part 5 同意策略（目标 12 分钟）

坑：

- `denied_by` 是 JSON Pointer（RFC 6901），根是空字符串 `""`，不是 `"/"`。
- all 由第一条拒绝的子规则负责；any 的子规则全不通过时，由 any 自己负责；not 的子规则通过时，由 not 自己负责，不是它的子规则。
- 时间按时刻比较：UTC 4 月 21 日 19:00 已经是印度时间 22 日 0:30，过了期限。按 ISO 字符串比较会放行。
- 空 all 允许，空 any 拒绝。`until` 不含它自己那一刻，`from` 包含它自己那一刻：UTC 4 月 30 日 18:30 正是印度时间 5 月 1 日 0:00，从这一刻起放行。`from` 按 ISO 字符串比较的话，这里会拒绝。
- 先校验整棵策略再求值：一个这次永远走不到的分支里有拼错的规则，也要报 ValueError。不带偏移的时间、一个规则对象有两个键、`not` 后面跟列表、`purpose` 后面跟字符串，都要报 ValueError。最后一种不校验的话，`in` 会变成子串匹配。请求的时间不带偏移也是 ValueError，不能等到比较时才抛 TypeError。

追问：

- "How would you explain a denial to the user?"（把指针对应的规则翻译成一句话；策略原文和同意记录一起保存）
- "The policy changes after the consent is signed?"（同意记录里存策略的版本或哈希，按签字时的版本求值）
- "Why validate branches the request never reaches?"（fail closed：很少走到的分支里的笔误，要么在线上悄悄放行，要么在关键时刻崩掉）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出合规、审计、规模、失败处理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
