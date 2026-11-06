# 面试官手册：Duplex（06/15）

候选人计时期间不要看。候选人手里只有 README、`duplex/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 能不能让 `encode` 直接返回逐帧的码？ | "No. encode mirrors Mimi's (n_q, T) code tensor and other callers rely on that layout. Fix the caller." |
| 1 | 真实模型的上下文有上限，能只保留最近几帧吗？ | "Not here. The context covers the whole session, and a step still has to stay cheap." |
| 2 | 同一帧的同一侧写了两次怎么办？ | "That's a bug upstream. Raise a ValueError. Never overwrite what's logged." |
| 2 | `frames()` 要不要返回只写了一侧的帧？ | "No, only frames with both sides. The model's side of the newest frame is usually still being generated." |
| 2 | 码值要校验范围吗？ | "Yes. A code is an int in 0..1023, and a side has exactly 8 of them." |
| 3 | 时间戳是什么精度？ | "Milliseconds, from the forced aligner. 2.32 means 2320 ms." |
| 3 | 词塞不进这段音频怎么办？ | "Raise a ValueError. Never drop or truncate a word." |
| 3 | 两个词的开始时间一样呢？ | "That's still time order. The second one moves later, like any collision." |
| 3 | 时间顺序按时间戳算还是按帧算？ | "By the timestamps. A word at 0.24 s after one at 0.25 s is out of order, even though both fall in frame 3." |
| 4 | 同一个方向的包会乱序吗？ | "No. Each direction is one ordered connection, so frame numbers only go up. If one repeats or goes backwards, raise a ValueError." |
| 4 | 一侧丢了一帧，`barge_in` 怎么算？ | "A null counts as not voiced, as the docstring says." |
| 4 | 某一侧一直不来包怎么办？ | "Wait for it. Timeouts are out of scope today." |
| 5 | 没有帧可填的位置放什么？ | "UNSET. Never a real code: 0 is a valid code." |
| 5 | 分组可以嵌套几层？ | "Any depth. Frames and delays always share one shape." |
| 5 | `ready_ms` 看整个布局里最大的延迟，还是只看模型的音频？ | "Your call. In every layout here the model's audio has the largest delay, so both give the same number. Say which one you chose." |

## 每关：要看什么、提示、追问

### Part 1 修全双工循环（目标 12 分钟）

一个测试里叠了 4 个缺陷和 2 个护栏：

1. `SAMPLES_PER_FRAME = SAMPLE_RATE / FRAME_RATE` 得到的是 1920.0。Python 3 的 `/` 总是返回 float，`24000 // 12.5` 也是 float。错误不在常量那一行报出来，而是在 `split_frames` 的 `range(count)` 报 `TypeError: 'float' object cannot be interpreted as an integer`。
2. `encode` 按 docstring 返回 codebook-major 的 `codes[k][t]`，和 Mimi 的 `(n_q, T)` 张量一样；`DuplexSession.hear` 却把它当成逐帧的列表来遍历。错误在下一层 `DuplexStepper.step` 报出来：`a user frame carries 8 codes, got 4`，那 4 个数其实是同一个码本在 4 帧上的值。根因在 `hear`，应该经过 `frames_of`。
3. `step` 先预测、最后才把三路历史一起 append，所以第 t 步的上下文只折叠了第 0..t-1 帧，而且把用户第 s 帧和模型第 s 步自己的输出配成一对。结果是模型永远晚一帧才听到用户，平白多 80 ms。课里 Step 3 写的是 `user_mimi[0..t]`、`moshi_mimi[0..t-1]`、`moshi_text[0..t-1]`；`ToyMoshi.advance` 的 docstring 也写明了配对方式。测试用一个记录调用的 Probe 模型把这一点直接测出来。只在上下文最前面多折叠一帧起始 token，计数就对上了，可第 t 步折叠进去的仍是用户第 t - 1 帧。Probe 还记录了每一步最后折叠进去的用户帧和模型音频，这种修法会挂在 `step t folds in user frame t` 上；第 0 步的模型音频要用 `AUDIO_START`，写成码 0 也挂在这里。
4. `_context()` 每一步都从头重放整段会话，是 O(T²)。1500 帧（2 分钟）在本机约 1.6 到 2 秒，修好后约 6 到 10 毫秒，限值是 0.1 秒。每帧只有 80 ms 的预算，会话越长越慢就会跟不上实时。修法是像 KV cache 一样把上下文留在 stepper 里，每步只折叠一帧。
5. 护栏一：断言 `encode` 仍是 codebook-major。把 `encode` 改成逐帧输出来迁就 `hear`，或者把帧率写成 12 让 `//` 得到整数（每帧变成 2000 个样本），都会在第一行断言挂掉。
6. 护栏二：Probe 跑满 100 步后，上下文里必须还有第 0 帧。为了提速只重放最近几帧，计时能过，这里会挂。

看什么：是不是先读 traceback、顺着调用链往上找值从哪来；是不是对照 docstring 和课里 Step 3 的下标；每改一处就重跑。

提示：
- H1："Which function first got a value it didn't expect, and where was that value made?"
- H2："What exactly is 24000 / 12.5 in Python? And what shape does encode() return?"
- H3：直接指出 `step` 里 append 的位置和 `_context()` 的重放循环。

追问：
- "Moshi's theoretical floor is 160 ms. Where is the second 80 ms in this loop?"（这里没有声学延迟；声学码晚一帧出，第 t 帧要到第 t+1 步才完整，这就是 Part 5）
- "Each step has 80 ms. How would you know you're inside the budget in production?"（看每步耗时的 P95/P99，不看均值；超时会排队，延迟越积越多）
- "The session outgrows the model's context. What then?"（真实系统要用滑动窗口或环形 KV cache，并且要说清楚丢掉了什么；本题的 toy 模型保留全部）

### Part 2 会话记录（目标 12 分钟）

坑：
- 一帧的两侧分开到达：用户侧来自上行任务，模型侧来自生成循环，测试里模型侧甚至先到。用一张表、两侧各占一列时，第二次写入必须合并。`INSERT OR REPLACE` 会先删掉整行再插入，另一侧变成 NULL，这一帧就不完整了。参考实现用 `ON CONFLICT ... DO UPDATE`；用两张表再 JOIN 也可以。
- sqlite3 默认开着隐式事务，不 commit 的话，关闭后数据就没了；建表要写 `IF NOT EXISTS`，否则重开报 `table frames already exists`。
- 按帧号排序，不能按插入顺序：测试先写第 1 帧再写第 0 帧。不写 `ORDER BY` 也可能过，因为 `WHERE session = ?` 走的是 (session, frame) 主键索引，碰巧按帧号返回。这是查询计划的副作用，不是保证；可以问候选人顺序靠什么保证。
- `frames()` 只返回两侧都齐的帧；`frame()` 遇到只有一侧的帧报 KeyError。重开之后补上另一侧，这一帧才出现。只有模型侧的帧也不算完整：测试在第 1 帧只写了模型侧时就调一次 `frames()`，只查 `model IS NOT NULL` 会挂在 `a frame shows up once both of its sides are logged` 上。
- 半帧也要马上落库。先把一侧放在内存里、凑齐两侧才写库，重开之后那一半就没了，`the second side completes a frame` 那一行拿到的是 KeyError。
- 校验在 Python 里做：每侧恰好 8 个、0..1023 的整数，缺一个码本的帧报 ValueError，1024 也报；用户侧和模型侧写第二次都报 ValueError，测试两侧各查一次。只靠主键会得到 IntegrityError，只靠 upsert 会静默覆盖。
- 原样读回：码 0、码 1023、PAD（也是 0）都要原样回来。JSON 或整数列都能存准；一个码一个字节存，写 1023 时就报 `bytes must be in range(0, 256)`；读回 tuple 和 list 比较不相等。判断一侧写没写要看 NULL，不能看真假值：`if text` 会把 PAD 当成没写，第 0 帧就丢了。

追问：
- "Two server processes log the same session. What happens?"（SQLite 写锁，可开 WAL；更稳的是每个会话只有一个写入任务）
- "This log becomes training data. What else would you store?"（codec 和模型版本、采样率、delay 设置、同意记录；版本不一致的会话不能混着训练）
- "A million hours of sessions?"（按会话存成紧凑的整数数组文件，10 位的码要用 16 位存；元数据留在数据库里）

### Part 3 inner monologue 对齐（目标 11 分钟）

坑：
- 帧边界是浮点陷阱：`2.32 / 0.08` 和 `2.32 * 12.5` 都是 28.999999999999996，`int(16.08 * 1000)` 是 16079。时间戳是毫秒精度，先 `round` 到毫秒，再用整数除以 80。
- 向下取整，不是四舍五入：0.62 s 在第 7 帧（560 到 640 ms），`round(0.62 * 12.5)` 会给 8。
- 0 s 开始的词前面没有帧放 EPAD。写成 `stream[first - 1] = EPAD` 而 first 是 0 时，Python 会静默写到最后一帧。按 docstring，这个词要挪到第 1 帧。
- 说得快时词会撞上前一个词：记住第一个空闲帧，`first = max(起始帧, 空闲帧 + 1)`，多出来的 1 是留给 EPAD 的。
- 塞不下要报 ValueError。切片赋值越过结尾时，列表会变长而不是报错，所以必须显式检查。条件是 `end > n_frames`：词的最后一个 token 正好落在最后一帧是合法的，写成 `>=` 会挂在 `a word can end in the last frame` 上。
- 词要按时间顺序，否则报 ValueError。按帧号比较也能过测试，但同一帧里顺序反了的两个词会被放过（见澄清问题）。
- 最后是端到端检查：Part 1 的 `encode` 和 `frames_of`、Part 2 的会话记录、给好的 `transcript()` 串起来，转写要原样回来。

追问：
- "Why does Moshi bother with a text stream at all?"（课里 Why inner-monologue text helps：语义更连贯，转写是白送的，换语言模型头更容易；文本先于音频预测）
- "Hibiki-Zero trains without word-level alignment. What does that remove from this pipeline?"（不再需要这一步的词级时间戳，改用句级数据，再用 GRPO 优化延迟）
- "A long word keeps pushing later words. Is that a problem?"（文本会落后于音频；可以统计推迟了多少帧做数据质量检查）
- "Why not add a small epsilon before flooring?"（输入是毫秒精度时，`int(start * 12.5 + 1e-9)` 也能过，但 epsilon 的大小是拍脑袋定的；先取整到毫秒再做整数除法是精确的，也说得清楚为什么对）

### Part 4 会话监控（目标 13 分钟）

坑：
- 输出格式由测试的解析代码决定：每帧一行 JSON，用换行分隔。缺了换行会报 Extra data。
- 按帧号配对，不能按到达顺序：两边各丢了一帧，zip 会从丢帧处开始全部错位。
- 还没到不等于丢了。同一方向的包按顺序到，所以只有当这一侧已经送来更晚的帧，或者已经结束，才能判定这一帧丢了。空的 burst 也要处理。
- 丢包和静音要分开：模型在听的时候照样每 80 ms 发一个 voiced 为 false 的包，没收到包才是 null。把丢包记成 false，第 5、6 帧就对不上。
- 每一帧凑齐就要输出，不能先把两边都读完。测试会数拉取了多少个 burst。
- 一侧结束后，另一侧剩下的帧照样输出，结束的那一侧填 null，不是 false；两侧都结束、手里也没有剩下的包才停。两侧都丢了的帧也要输出一行，user 和 model 都是 null；“两侧都没有第 t 帧就停”会挂在 `a frame both sides lost still gets its line` 上。
- `barge_in` 要看上一帧用户是否在说话，这个状态要跨 burst 保留。第 8 帧是模型压过用户说话，算重叠，不算插话。丢了的帧按没在说话算：丢包时沿用更早一帧的状态，会挂在 `a lost frame counts as not voiced` 上。
- 帧号必须严格递增，倒退或重复都报 ValueError，而且要跨 burst 检查。用 `<` 放过重复的帧号，或者每个 burst 重新计数，都会挂在第二个 `pytest.raises` 上。
- 写成普通的 async 函数时，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出来这里需要 async generator。

追问：
- "The downlink stalls for two seconds. What does your monitor do, and what should it do?"（现在会一直等；线上要给每一侧一个截止时间，超时就当丢帧输出 null，用完整性换延迟）
- "How would you measure end-of-user-speech to start-of-reply latency from these lines?"（课里 Exercise 2：找用户最后一个有声帧和模型之后第一个有声帧，两者帧号差乘 80 ms）
- "Frame 8: the model starts talking over the user. Bug or feature?"（可能是附和，也可能是抢话；要看持续多久、用户有没有停下来）

### Part 5 声学延迟（目标 12 分钟）

坑：
- 步数是帧数加最大延迟；只做帧数那么多步，最后一帧的声学码就丢了，undelay 也还原不了。
- 没有帧可填的位置放 UNSET。填 0 不行，0 是合法的码。
- 每个码本有自己的延迟：语义码本 0 帧，声学码本 1 帧。不能整路用一个延迟。
- 分组要递归：delays 和帧是同一个嵌套形状，dict 下面可以再有 dict，text 是单个 token 的流。只处理一层，遇到分组会报 TypeError。
- 别用 `[template] * n` 建步骤：所有步骤会共享同一个 dict，最后全都一样。
- delay 先校验形状：缺一个码本、多一个码本、多一路流都报 ValueError，测试三种各查一次。只沿着 delays 走、把 IndexError 换成 ValueError，会放过多出来的码本和流。
- undelay 要校验：该有 token 的位置是 UNSET、该是 UNSET 的位置有 token、步数不够，都报 ValueError，测试三种各查一次。最省事的办法是还原后再 delay 一次，和输入比较；这一次 delay 会校验还原出来的帧，所以该有码的位置是 UNSET 也会被查出来。还原后只按延迟重排、不校验帧，`holed` 那一处就漏过去了。
- `ready_ms`：第 t 帧的最后一个码本在第 t + 最大延迟 步生成，第 s 步要等用户第 s 帧完整到达，也就是 (s + 1) × 80 ms。第 0 帧是 160 ms，正好是课里的 80 ms 帧长加 80 ms 声学延迟；忘了加 1 会得到 80。参考实现取整个布局里的最大延迟；只看模型那一路也能过，测试里的布局都是模型音频延迟最大（见澄清问题）。

追问：
- "Why not predict all eight codebooks of a frame at the same step?"（码本之间有依赖，RVQ 后一级是前一级的残差；Depth Transformer 在帧内逐个预测，声学码再晚一帧，代价是 80 ms 延迟）
- "Stream undelay: emit each frame as soon as it's complete."（缓存最大延迟那么多步，第 t + 最大延迟 步到达时输出第 t 帧）
- "What would a 2-frame acoustic delay cost?"（`ready_ms(0)` 变成 240 ms，延迟下限多 80 ms）
- "Say the user's acoustic codebooks were delayed by 3 frames and the model's by 1. When can the model's frame 0 play?"（只看模型自己的码本：第 1 步生成完，第 1 步要等用户第 1 帧到齐，还是 160 ms。用户的声学码晚几帧不影响模型出声，前提是用户的语义码本不延迟。取整个布局最大延迟的写法会给出 320 ms，在 Moshi 这种两路延迟相同的布局里两者才一样）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出每帧预算、并发写入、版本、超时和丢包处理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
