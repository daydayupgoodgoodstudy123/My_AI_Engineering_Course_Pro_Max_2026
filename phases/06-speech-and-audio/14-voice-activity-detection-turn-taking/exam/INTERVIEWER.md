# 面试官手册：TurnKit（06/14）

候选人计时期间不要看。候选人手里只有 README、`turnkit/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 电平正好等于阈值的帧算不算响？ | "No. Strictly above, like the lesson's energy gate. The tests don't sit on the boundary." |
| 1 | 结尾不满一帧的样本怎么办？ | "Ignore them. Only complete frames get a flag." |
| 2 | 存秒还是存采样点？ | "Samples. Seconds are only for display." |
| 2 | 同一个 recording 来了另一个采样率？ | "Reject it with a ValueError. We don't resample." |
| 2 | 查一个从没存过的 recording？ | "Return an empty list. It's not an error." |
| 3 | 没有打开的轮次时调用 flush？ | "Drop whatever speech is pending and return None." |
| 3 | pre-roll 比和上一轮之间的空隙还长？ | "Stop at the end of the previous turn. Two turns never share audio." |
| 4 | 流结束时不足一帧的样本？ | "Drop them. They never get a decision and don't count as a frame." |
| 4 | 开头要不要先发一个 silence 事件？ | "No. The stream starts in silence; only changes are sent." |
| 4 | 流刚开始，前面凑不够 context_frames 帧？ | "Send what you have. The first frame's context is just that frame." |
| 4 | 模型输出正好等于 speech_prob 算不算语音？ | "Yes. At least speech_prob is speech, like the lesson's `silero_prob >= 0.5`. The tests don't sit on the boundary." |
| 5 | 两个说话人的 spurt 起止完全相同？ | "Whichever comes first in the input holds the floor. The tests don't cover it." |
| 5 | 一个人的 spurt 落在他自己的另一段里？ | "That's an overlap with themselves. Raise a ValueError." |

## 每关：要看什么、提示、追问

### Part 1 修能量门（目标 10 分钟）

一个测试里叠了 4 个缺陷和 2 个护栏：

1. `rms` 返回的是样本的均值（有正有负），不是均方根。错误不在 `rms` 报出来，而是下一层在 `dbfs` 里报 `ValueError: math domain error`：负数取了对数。`dbfs` 只把 0.0（数字静音）当特例，这对真正的 RMS 是对的，所以不要去改它。
2. `energy_gate` 为了省掉开方，比较的是均方（功率），可阈值换算成的是幅度 `10 ** (dB / 20)`。实际门限变成了 -20 dBFS，-30 和 -38 dBFS 的帧被当成静音。功率要和 `limit ** 2`（也就是 `10 ** (dB / 10)`）比，或者开方后和 `limit` 比。
3. hangover 换算成帧数时除的是 `frame_len`（采样点数），不是 `frame_ms`。8 kHz 下 100 // 160 = 0，hangover 完全不起作用。
4. `apply_hangover` 对每一帧都从头扫一遍历史找最近的响帧，是 O(n²)。测试里的 16,000 帧是 1,000 帧说话、再跟 15,000 帧静音，要 1.3 秒左右。从当前帧往回找、碰到响帧就停也不行：静音里的每一帧都要一路往回走到那段话，还是 O(n²)，要 1.1 秒左右。
5. 护栏：改成 O(n) 时最常见的两种写法都会在边上出错。“距上一个响帧多少帧”的计数器从 0 开始，开头的静音会被当成语音；用 `loud[i - frames : i + 1]` 取窗口，开头几帧的下标是负数，切片变成空的，第一帧是响帧也会丢。

看什么：是不是先读 traceback、发现报错的地方没有问题再往上游找；是不是先 `print(repr(...))` 看实际的电平和帧数；每改一处就重跑。

提示：
- H1："What value reached log10, and where did it come from?"
- H2："What is -40 dBFS as an amplitude, and as a power? Which of the two is the gate comparing?"
- H3：直接指出 `rms` 的返回式，或者 `power > limit` 和 `hangover_ms // frame_len` 这两行。

追问：
- "Why does the gate avoid the logarithm?"（这是级联里最便宜的一层，每帧都要跑；阈值只换算一次，按功率比较就够了）
- "The lesson says a fixed threshold fails in noise. How would you calibrate on the device?"（在非语音帧上估计噪声底，按功率平均，不能直接平均 dB 值；阈值取噪声底加一个余量，并且慢慢跟踪）
- "A cheap microphone adds a DC offset. What happens to this gate?"（静音也有能量，会被判成语音；算 RMS 之前先去直流或做高通）
- "This hangover is 100 ms. Part 3 has a 500 ms silence hangover. Why both?"（这里只是补上音节之间的短暂凹陷；Part 3 的是判断一轮话结束要等多久）

### Part 2 语音段表（目标 12 分钟）

坑：
- 边界必须按采样点存整数。按毫秒存的话，16 kHz 下 16001 会变成 1000 ms，读回来是 16000；按 REAL 秒存、读回时用 `int()` 截断，1001 这类值会少一个采样点。
- 区间是左闭右开。[a, b) 和 [b, c) 相接，要合并；中间空一个采样点就不合并。按闭区间想，会把空一个采样点的两段也并起来。
- 新的一段可能同时接上两边，三段要并成一段。只合并查到的第一行会挂。表里已有的段互不相接，所以一次查询就能找全。
- 新的一段整个落在已有段里面也是重叠，返回包住它的那段。只查“已有段的端点是否落在新区间里”会漏掉这种情况，表里就有了两行互相重叠的段。
- 只在同一个 recording 里找要合并的段。查询漏了 `recording = ?`，重开后加的 room-2 [0, late) 会把 call-7 的三段全并走。
- 合并要在一个事务里做完：删掉旧行，插入新行，再 commit。不 commit 的话，重开后什么都没有。
- 建表要写 `IF NOT EXISTS`，否则重开报 `table ... already exists`。
- `segments()` 按开始位置排序。按 rowid 排是插入顺序，测试最后插入的那段在时间上最早。
- 每个 recording 只有一个采样率，第一段决定；另一个采样率、空区间、负数起点都要报 ValueError。

追问：
- "The phone leg of a call is 8 kHz and the app leg is 16 kHz. How do you store both?"（各自作为独立的 recording；要对齐时按有理数比例换算，不要在一张表里混采样率）
- "Two workers add segments to the same recording at once?"（合并是读改写，必须放在同一个写事务里，比如 `BEGIN IMMEDIATE`，或者只留一个写入方）
- "You merge on write and lose the original pieces. When is that a problem?"（需要审计每次 VAD 触发时；另存一份只追加的事件日志）

### Part 3 轮次检测（目标 12 分钟）

坑：
- 最短语音必须是一段连续的语音。照抄课里的 `TurnDetector`，idle 状态下遇到静音不清零 `speech_ms`，零星的点击声会累计成一轮。测试里的 `("#" + "." * 9) * 20` 专门抓这个。
- 最短语音按采样点比，不按整帧数取整。16 kHz、20 ms 一帧时，250 ms 是 12.5 帧，12 帧只有 240 ms，要到第 13 帧才够；课里的合成流也是在第 13 个语音 chunk 才 START。用 `min_speech // frame_len` 算要几帧，会早一帧开始。
- START 要等语音持续够 `min_speech_ms` 才能确定，所以判定得晚；但这一轮的音频要从语音起点往前再推 `pre_roll_ms`。只报判定时刻或语音起点都不对。课里的代码存了 `pre_roll_ms` 却从来没用。
- pre-roll 往前推时不能早于 0，也不能伸进上一轮。测试里 pre-roll（15 帧）比 hangover（10 帧）长，就会碰到上一轮的结尾。
- 静音不到 hangover 的停顿不结束这一轮，后面一来语音就重新计时。
- END 的位置是最后一个语音帧的结尾，不是判定时刻；判定时刻（`decided`）晚一个 hangover。
- `flush` 立即结束打开的轮次，结束位置同样是最后一个语音帧的结尾；还没凑够最短语音的那段直接丢掉，之后要重新攒够 `min_speech_ms`。
- flush 时最后一帧还是语音（比如松开按键说话的按钮），结束位置就是当前位置。只记“静音从哪开始”的写法，这时拿到的是一个过时的位置。flush 结束的那一轮也算上一轮，之后的 pre-roll 同样不能伸进去。
- 最后一段是端到端检查：课里那条合成流（语音、静音、一声咳嗽、语音）经过 Part 1 的能量门、这个状态机和 Part 2 的表，要得到两轮，咳嗽不算。服务会把每一轮的音频交给 STT，紧跟一个 flush。

提示：
- H1："Walk the pattern frame by frame. After each frame, what does the detector know?"
- H2："For the start event: which sample does the turn's audio begin at, and at which sample did you know?"
- H3：指出课里 `TurnDetector.update` 在 idle 状态下遇到静音时什么也没做。

追问：
- "Hangover 500 ms, 800 ms, or a semantic end-of-turn model?"（短了会打断用户，长了显得迟钝；语义模型判断说完了可以提前 flush，判断没说完可以多等）
- "How much pre-roll do you need?"（START 本来就晚了约 `min_speech_ms`，pre-roll 至少要覆盖它再加余量，所以课里是 250 ms 配 300–500 ms）
- "Where does the flush trick save time?"（STT 不用等 look-ahead：500 ms 的缓冲按 4 倍实时处理，约 125 ms 出结果）
- "The user starts talking while the agent is still speaking. What changes?"（要先做回声消除；是附和还是打断，就是 Part 5 的结构）

### Part 4 级联流式（目标 14 分钟）

坑：
- 格式由测试里的 `parse_sse` 决定：每个事件一行 `event:`、一行 `data:`，后面一个空行。少了空行报 "every event ends with a blank line"，多一个空行报 "one event line and one data line per event"。
- 模型只给能量门放过的帧调用，每帧一次。先对每帧都调模型、再和门的结果取与，判定一样，但调用次数和模型看到的 context 都不对。
- 模型的 context 是当前帧加上它前面的 `context_frames - 1` 帧，不管前面那几帧有没有过门。只缓存过门的帧会挂。
- context 和帧都要跨块拼接；块的大小随意，可能是空块。按块重新开始会在一个采样点一块时挂。
- 判定一变就要发事件，不能先读完整条流，也不能晚一块。测试会数被拉取了多少块，第一个事件出来时应该正好拉了 5 块。写成 `while len(pending) > frame_len` 要多等一个采样点；先处理缓冲里已有的帧、再把新块加进去，会晚一块。这两种都会多拉一块。
- 结尾不足一帧的样本丢掉，不计入帧数；流结束后发一条 stats。
- 写成普通函数时，测试报的是 `'async for' requires an object with __aiter__`，要会看出来这里需要 async generator。

追问：
- "Silero is stateful, an RNN. What happens to its state when the gate skips frames?"（隐状态停在旧的上下文上；长时间跳过后要重置，或者先喂几帧 context 预热；这也是题目要求把前面的帧一起交给模型的原因）
- "How much does the gate save on a real call?"（一通电话里一半以上是静音；Silero 每 30 ms 约 1 ms CPU，门几乎不要钱）
- "What if the gate threshold is too high?"（门拒掉的帧模型永远看不到，第一层的漏检后面救不回来，所以门要放得宽）
- "The client disconnects mid-stream. What runs, what leaks?"（`aclose()` 会在 `yield` 处抛 GeneratorExit；需要释放的资源放进 finally）

### Part 5 重叠语音结构（目标 12 分钟）

坑：
- 一段 spurt 落在别人的 spurt 里，就挂到包住它的最里层那段下面，可以嵌好几层：A 说话时 C 插话，C 说话时 B 说 "yeah"，B 挂在 C 下面。
- 只看开始时间会把“开始在里面、结束在外面”的那段也挂进去。这种是接过了话轮，是一个新的 turn。
- 只是首尾相接不算嵌套；同一个人前后两段首尾相接也合法，不能当成自己和自己重叠。
- 两段同时开始时，长的那段在前、是外层。只按开始时间排序（稳定排序保留输入顺序）会把短的那段放成外层。
- backchannel_ms 是毫秒，区间是采样点，要用采样率换算；正好 1000 ms 的不算 backchannel（“shorter than”）。
- 输入顺序是乱的；同一个人自己的 spurt 重叠要报 ValueError，中间隔着别人的 spurt 也要查出来。排序后只和前一段比会漏掉，要按说话人记住各自说到了哪里。空的 spurt 也报 ValueError。

追问：
- "Is every short overlap a backchannel?"（不是。"no, wait" 很短，却是在打断；要靠词和语调，也就是课里的语义层）
- "How would you measure how fast the agent answers?"（相邻两个 turn 之间：后一轮的开始减前一轮的结束，负数就是重叠；人和人之间通常在 200 ms 左右）
- "The user's spurt sits inside the agent's turn. What should the agent do?"（backchannel 就继续说；超过阈值的 overlap 当作 barge-in，停掉 TTS）
- "Could you find the parent by walking down the last child at each level, instead of scanning every open spurt?"（可以，结果一样。装不进最后一个孩子的 spurt，也装不进更早的兄弟：更早的兄弟要是包得住它，也就包得住那个最后的孩子，那个孩子本该嵌在它里面）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出噪声、延迟、并发、状态和失败处理 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
