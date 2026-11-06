# 面试官手册：RTLoop（06/11）

候选人计时期间不要看。候选人手里只有 README、`rtloop/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 环满了丢最旧的还是最新的？ | "The oldest, as the docstring says. The loop wants fresh audio." |
| 1 | 静音的电平报多少？ | "FLOOR_DBFS, minus 200. Never minus infinity: levels end up in JSON and in averages." |
| 1 | 电平是峰值还是 RMS？ | "RMS. A full-scale sine reads minus 3.01 dBFS." |
| 1 | 采样率不是 16 kHz 时一帧多少个样本？ | "Always 20 ms of audio: 882 samples at 44.1 kHz, 960 at 48 kHz." |
| 2 | mark 来自哪个时钟？ | "One monotonic clock per session, in integer nanoseconds. Some services log time.time_ns(), so expect big numbers." |
| 2 | 一轮可以缺阶段吗？ | "Yes, when the user cuts in. It keeps the stages it reached, in order, starting at speech_end." |
| 2 | 两个 mark 可以相等吗？ | "Yes. A cached reply has its first token the moment the transcript is final." |
| 2 | 正好等于预算算不算慢？ | "No. Slow means over budget." |
| 2 | 轮次编号是全局的还是按 session？ | "Per session, starting at 1, and it carries on after a restart." |
| 3 | 被打断的那一块要不要进 history？ | "Yes. The user heard the start of it. That's what 'started playing' means." |
| 3 | TTS 比实时慢，两块之间有空档怎么办？ | "A chunk starts when it arrives. The reply still holds the floor during the gap." |
| 3 | 用户开口之前的语音帧算不算进连续计数？ | "Your call. The tests don't depend on it." |
| 4 | 第一个队列满了怎么办？ | "Drop the oldest waiting frame and count it. The mic never waits." |
| 4 | sink 报错的那一帧算 delivered 吗？ | "No. That frame is lost and counted as an error, like a stage error." |
| 4 | 麦克风结束时队列里还有帧？ | "Deliver them all before you return." |
| 4 | 可以用 TaskGroup 吗？ | "If you're on 3.11 or later, sure. Say which version you're assuming." |
| 5 | reference 边算不算延迟？ | "No. It carries the previous frame." |
| 5 | 两条链一样慢取哪条？ | "The input listed first, as the docstring says." |
| 5 | 图会有多大？ | "Generated graphs can have dozens of stages with a lot of fan-in." |

## 每关：要看什么、提示、追问

### Part 1 修采集代码（目标 10 分钟）

一个测试里叠了 4 个缺陷和 4 个护栏：

1. `RingBuffer.write` 在回绕处切分时少算了一格（`self.capacity - start - 1`）。存储的最后一格永远写不到，回绕后的样本都错后一格。错误不在 `ring.py` 报出来，而是两层调用之后，在 `meter.rms` 里报 TypeError：那一格还是初始化时的 None。
2. `ms_to_samples` 先除后乘：`sample_rate // 1000 * ms`。16 kHz 和 48 kHz 能被 1000 整除，结果没错；44.1 kHz 下 44100 // 1000 是 44，一帧只有 880 个样本，不是 882，每帧的时间戳少 45 µs，越走越偏。讲义 `code/main.rs` 的 `FRAME_LEN = SAMPLE_RATE / 1000 * FRAME_MS` 就是这么写的，只因为用的是 16 kHz 才没出错。测验的技能清单第一条就是“能计算任意帧长 / 采样率下每帧的采样点数”。改成 `int(sample_rate / 1000) * ms` 不算修好，还是先截断再乘。
3. 环写满时，`write` 用 `read(1)` 一个一个挤掉最旧的样本，但没有计入 `dropped`。测验 Q12 讲的就是这种静默丢弃：样本丢了，没有任何地方能看到。
4. 每挤掉一个样本就调一次 `read(1)`，而 `read` 每次都把整个环复制一遍（`self._buf[start:] + self._buf[:start]`）。处理循环一卡住，回调每写一块都要复制“块长 × 容量”个元素：1 秒的环卡 2 秒，要 1 秒以上。讲义说环形缓冲区的用处就是热路径上不分配内存。
5. 护栏：电平是 20·log10(RMS)，和 `code/main.py`、`code/main.rs` 一样，所以满幅正弦波是 -3.01 dBFS。测试用 16 kHz 下的 1 kHz 正弦，每个 20 ms 帧正好 20 个周期。把电平改成峰值，或者照 AES17 的习惯加 3.01 dB，都会在这里挂。
6. 护栏：静音的麦克风读 `FLOOR_DBFS`（-200 dBFS），电平计里已经有 `code/main.py` 那样的下限。有人改写电平计、让静音返回 -inf，会在这里挂：电平要进 JSON 和平均值。
7. 护栏：把存储初始化成 0.0，TypeError 就没了，但回绕的错还在，帧里会混进一个 0 和错位的样本。测试逐个样本比对每一帧，只修症状过不去。
8. 护栏：卡住以后，帧的时间戳要从丢弃之后的位置算起，第一帧在 300 ms。批量丢弃时只加 `dropped`、不移动读指针，读的一方会被写的一方套圈，读出重复的样本；时间戳只数送出去的样本、不算丢掉的，第一帧会变成 0 ms。

看什么：是不是先读 traceback 最底下一层，再问“None 是从哪来的”；是不是 `print(repr(...))` 看帧和环里的内容；看到 TypeError 会不会直接去改 `rms`。

提示：
- H1："Where did the None in that frame come from?"
- H2："After the first wrap, which slot of the ring is still None?"
- H3：直接指出 `write` 里的 `self.capacity - start - 1`。

追问：
- "Why drop the oldest audio, not the newest?"（实时系统要新音频；留着旧的，延迟会越积越大。讲义：缓冲区就是延迟的下限）
- "The callback runs on PortAudio's thread. What changes?"（单生产者单消费者；在 C 里两个计数器要用原子操作和内存屏障；回调里不分配内存、不加锁）
- "How big should the ring be?"（容量约等于最大延迟乘采样率；2 秒的环意味着最坏 2 秒的延迟）
- "The mic runs at 44.1 kHz and the ASR wants 16 kHz. Where do you resample?"（在入口一次性重采样；讲义 Common gotchas：管线中间重采样要多 5–20 ms）

### Part 2 延迟记录（目标 12 分钟）

坑：
- 精度陷阱：有的服务记的是 `time.time_ns()`，2026 年约 1.79e18，远超 2^53。double 在这个量级上相邻两个数差 256 ns。列声明成 REAL，或者换算成浮点秒再存，往返断言都会挂。INTEGER 列能原样存 64 位整数。
- 浮点的 mark 要拒绝：`WALL / 1e9` 是常见的单位错误，把秒当成了纳秒。
- 编号按 session 算，从 1 开始，重开以后接着编。用 `lastrowid` 会编成全局号；在内存里计数，重开后从 1 重来，会撞上 `UNIQUE (session, number)`。
- 相等的 mark 合法（缓存的回复，transcript 一到就有第一个 token），倒退的不合法。只有 speech_end 的前缀合法，跳过阶段不合法。
- 正好等于预算不算慢：用 `>` 不用 `>=`。差值要用整数算，SQL 里直接写 `first_audio - speech_end > ?` 就是精确的。按整毫秒比较，多 1 ns 的那一轮就漏了；先把两个绝对 mark 换成浮点秒再相减也会丢掉这 1 ns，1.79e9 秒这个量级上 double 的间隔约 0.24 µs。
- `turn` 只返回这一轮到过的阶段。没到的阶段补成 None，被打断的那一轮就和记录时的 dict 对不上。
- 慢的轮次按记录顺序返回，不按 session 排。没有 first_audio 的轮次（用户插话了）不算慢。
- 不认识的阶段名（`tts_start`）要报错，不能悄悄丢掉。
- 老问题：不 commit，重开就没了；建表要写 `IF NOT EXISTS`。

追问：
- "Why integer nanoseconds and not float seconds?"（2^53 ns 约 104 天；`time.time_ns()` 远超这个数，`monotonic_ns()` 取决于开机多久；和预算比较的差值必须精确）
- "Are speech_end and first_audio on the same clock?"（VAD 结束来自麦克风时钟，首个音频来自播放时钟；不同设备的时钟要先换算到同一个时钟域）
- "How would you report P95 per stage?"（存原始 mark，按阶段算差值再求分位数；skill 文件明确不看平均值）

### Part 3 打断（目标 12 分钟）

坑：
- 播放时间线：一块从“到达”和“上一块结束”中较晚的那个时刻开始。按到达时刻开始，块会互相重叠。
- 打断要在第三个连续语音帧那一刻停，哪怕正播到一块的中间：用户 760 ms 开口，800 ms 停，40 ms 以内。等这一块播完是 940 ms，超过讲义要求的 100 ms。讲义推荐的 TTS 块是 320 ms，所以“播完当前块再停”一定超时。
- 连续计数遇到非语音帧要清零。残留回声是隔一帧一个语音帧，不清零的话数到第三个就误打断。
- 打断后要清掉排队的块，还要忽略被取消的回复后来到的事件：1550 ms 那块迟到的，和 1560 ms 它的 `reply_done`。只看状态不够：迟到的事件到的时候，下一轮回复已经在 thinking 了，要比回复编号。`reply_done` 不比编号，第 2 个回复一个音都没出就被当成结束，话轮提前交回去了。
- 回复还占着话轮时又来了一个 `user_turn`（测试里是用户在 app 里打字），和打断一样处理：正在播的块截到这一刻，history 记下听到的部分，再开始新回复。
- thinking 时用户接着说话也算打断。讲义 Step 4 的 `tts_task` 包着 LLM 和 TTS，`on_user_speech` 只要任务没结束就取消。只在 speaking 时打断，这条回复会在用户说话的时候播出来。
- 最后一块播完才把话轮交回来，收到 `reply_done` 的那一刻还不行。
- history 只记用户听到的，也就是已经开始播的块。记下生成的全部文本，下一轮 LLM 会以为用户听到了没播出来的话（测验 Q17）。一个音都没发出的回复不留空记录。
- 最后一段是端到端检查：Part 1 的采集给出每帧电平，测试用 `code/main.py` 的 -40 dBFS 阈值做 VAD。用户 500 ms 开口，播放在 540 ms 停。

追问：
- "How do you keep the assistant's own voice from triggering a barge-in?"（先过 AEC；要求连续多帧；“嗯”这类附和不算；语义层面的轮次判断见第 14 课）
- "The LLM is still generating when the user cuts in. What else do you cancel?"（LLM 请求本身，释放算力；迟到的 token 不能进 history）
- "What goes into the context for the next turn?"（只放听到的部分，并标明被打断）

### Part 4 异步流水线（目标 14 分钟）

坑：
- 麦克风不能等：第一个队列满了，就丢掉排在最前面的那帧并计数（`get_nowait` 再 `put_nowait`）。用 `await put` 麦克风就要等，测试里 dropped 是 0；丢最新的那帧，最后一帧 199 就到不了。
- 后面的队列都要有界，满了让前一级等。用无界队列，tag 会比 STT 领先 160 帧；测试要求最多 maxsize + 2（队列里 4 个，tag 手里 1 个，STT 正在处理 1 个）。
- 某一帧出错只丢这一帧，计入 errors。让异常抛出去，整个会话就断了，讲义 Pitfalls 的最后一条就是这个。sink 也一样：播放设备在第 5 帧报错，这一帧计入 errors，不算 delivered，测试要的是 `Stats(delivered=6, errors=2)`。但只能捕获 Exception：捕获 BaseException 会把取消也吞掉，挂断以后流水线还在跑。
- 第一个队列满了时把整个队列清空，测试也能过（这个场景里总共只多丢 1 帧，测试分不出来），但和 docstring 不符：只丢最旧的那一帧。看到这种写法就问为什么。
- 麦克风结束后要把路上的帧送完再返回：结束标记一级一级往下传。麦克风任务一结束就取消其他任务，路上的帧就丢了。
- 取消是这一关最深的坑。`asyncio.gather` 在第一个子任务以取消结束时就返回，这时还在清理（关 TTS 连接）的 stage 没结束，run_pipeline 已经先返回了。在 finally 里再 cancel 一遍，又会把那个 stage 的清理半路打断。参考实现用 `asyncio.wait`：每个任务只 cancel 一次，然后等全部结束。Python 3.11 以上用 `asyncio.TaskGroup` 也对。
- 取消要传出去。捕获 CancelledError 后正常返回 stats，调用方会以为通话是正常结束的。

追问：
- "Why drop the oldest frame instead of blocking the mic?"（回调不能等，等了就会丢硬件缓冲；旧音频的价值低）
- "Where would you never drop?"（TTS 音频播到一半不能丢，用背压；能丢的是过时的中间转写）
- "One stage is CPU-bound. What happens to the loop?"（事件循环被阻塞，所有阶段一起卡住；放进线程池或子进程，讲义 Common gotchas 的第一条）
- "Why a private object as the end marker, not None?"（stage 可以合法地返回 None。拿 None 当结束标记，一个返回 None 的 stage 会让后面的阶段提前退出，前面的阶段堵在满队列上，整个调用挂住）
- "The USB headset is unplugged and the mic iterator raises. What does your run_pipeline do?"（参考实现用 FIRST_EXCEPTION，异常传出去，其余任务各取消一次。只写 `gather(..., return_exceptions=True)` 会把异常吞掉，后面的阶段永远等不到结束标记；测试没有覆盖这种情况）

### Part 5 处理图（目标 12 分钟）

坑：
- reference 边（AEC 的远端参考信号来自 speaker）带的是上一帧，不参与排序，也不算延迟。当成 inputs，就会在 aec → … → speaker → aec 上报环。
- 判环只用一个 visited 集合，菱形（vad 同时进 stt 和 turn）也会被当成环。要分“在当前路径上”和“已经完成”两种状态。
- 报错要指出环上的阶段。测试里的环是没有 AEC、STT 直接听扬声器：`stt -> speaker -> tts -> llm -> turn -> stt`（经过 `llm -> stt` 的那个更短的环也算对）。用 Kahn 算法剩下的节点报错，或者把整条 DFS 路径报出来（DFS 是从 captions 走进环的），都会把环下游的 captions 也报进去。
- 同一条回声路径，作为 reference 进 AEC 是合法的，带的是上一帧；作为 inputs 进 STT，就是同一帧里的环。
- 关键路径取各输入里最慢的那条链，再加上自己的 ms。把输入全部相加得 645，只看第一个输入得 265，从 speaker 往回每一步挑 ms 最大的输入（贪心）得 410，正确是 415。llm 同时读 turn 和 stt：stt 自己的 150 ms 最大，但经过 turn 的那条链多 5 ms。
- 平票时取列在前面的输入，结果才确定。
- 输入或 reference 里有未知的名字要报 ValueError，不是 KeyError。
- 立体声链 20 级，每级读上一级的左右两路：不带记忆的递归要走 2^20 条路径，约 1 秒；按拓扑序做一遍动态规划只要几十微秒。

追问：
- "What does the loop through the reference edge cost?"（一帧的延迟；AEC 要知道远端信号和回声之间差多少，WebRTC 里有专门的延迟估计）
- "The critical path says 415 ms. Is that what the user feels?"（不是。流式让各阶段重叠，用户感到的是首个音频的延迟；关键路径给的是各阶段预算加起来的上限）
- "The graph changes at runtime?"（换阶段之前先校验整张图；只重算受影响的下游）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出时钟、线程、背压、取消、故障隔离 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
