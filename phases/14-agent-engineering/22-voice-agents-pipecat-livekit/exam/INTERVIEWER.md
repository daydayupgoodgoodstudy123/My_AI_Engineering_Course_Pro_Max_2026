# 面试官手册：VoiceFrame（14/22）

候选人计时期间不要看。候选人手里只有 README、`voiceframe/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。
- 可以先用一句话介绍背景：这是课里 `code/main.py` 那条玩具管道的加强版，模型和 TTS 都是测试里的假函数，不联网。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 只有空格的 audio_chunk 要不要送给 STT？ | "No. Whitespace is silence. It never reaches STT." |
| 1 | 被打断的那条回复，上下文里记什么？ | "Only the words the user heard. That's what the cancel carries." |
| 1 | cancel 正好在合成某个词的时候到了，这个词还播吗？ | "No. Nothing synthesized after the cancel is played." |
| 1 | 机器人已经说完了用户才开口，这个 cancel 怎么处理？ | "Nothing to cut. The user heard the whole reply, so the context keeps all of it." |
| 2 | 二进制布局可以自己定吗？ | "Yes. Only MAGIC at the start is fixed. The tests only use your reader." |
| 2 | 时间戳要多精确？ | "Integer nanoseconds, exactly as given. Up to 2**63 - 1." |
| 2 | 文件中间的记录坏了怎么办？ | "Raise a ValueError. The tests don't cover it." |
| 3 | 空的转写片段，它的置信度算不算？ | "No. Ignore the segment completely." |
| 3 | 让用户重说的那一轮也占轮次号吗？ | "Yes. Every turn that ends takes the next number." |
| 3 | 用户打断以后说的话算哪一轮？ | "The next one. It's a new user turn." |
| 3 | `admit` 说的“最新一轮”是哪一轮？ | "The last turn number you handed out. Its first frames can arrive before bot_started." |
| 4 | 窗口从第一个事件开始算吗？ | "No. From zero on the call clock." |
| 4 | 样本要带时间戳吗？ | "No timestamps. One exposition per window, in order." |
| 4 | 样本按什么顺序？ | "Pipeline order, the order of stages." |
| 4 | UPSTREAM 的事件还推进窗口吗？ | "Yes. Every event tells the time on the call clock. It just isn't counted." |
| 5 | 1200 到 1500 毫秒之间算哪一档？ | "The lesson doesn't name it. We call it slow." |
| 5 | 分档看最好情况还是最坏情况？ | "Worst case. That's what users feel on a bad day." |

## 每关：要看什么、提示、追问

### Part 1 修打断（目标 12 分钟）

一个测试里叠了 3 个缺陷和 4 个护栏：

1. VAD 用 `if frame.payload:` 判断有没有说话，只有空格的块也算语音。错误不在 VAD 报出来，而是三层之后：STT 把它去掉空格变成空转写，LLM 把空串交给模型，测试里的假模型报 `KeyError: ''`。
2. TTS 先把整条回复的每个词都合成完，才开始往下游发第一个词。400 个词，假合成函数每个词至少睡 2 ms，本机实测首个词要等 1.2 秒左右，测试限 0.08 秒；改成流式后约 3 ms。课里的 barge-in 演示其实什么都没截断，原因也在这里：cancel 到达时整句早就发完了。
3. TTS 的 `spoken` 只在 `__init__` 里建一次，每次新回复都没有清空。cancel 往上游带的是整通电话说过的所有词，症状出现在 LLM 的 context 里：被打断那条助手消息前面多出了上一条回复的内容。
4. 护栏一：cancel 在合成某个词的过程中到达（测试的假合成函数里触发打断），这个词合成完也不能播。改成流式时只在合成前检查一次 `cancelled`，会在这里挂掉。
5. 护栏二：打断以后下一条回复要完整说出来。把 `cancelled = False` 删掉、让取消一直生效，会挂在“barge-in stops the bot mid-utterance”（下一条回复一个词都没播）。
6. 护栏三：context 从头到尾比对，包括长回复那条只剩 `clause0`。在 cancel 时清空 `spoken`、而不是在每条回复开始时清空，会把没被打断的上一条回复带进下一次 cancel，这里会挂。
7. 护栏四：最后一条回复完整说完以后用户才开口，transport 照样发 cancel。这时 cancel 带回的是整条回复，context 不变。在回复结束时清空 `spoken`，cancel 带回空列表，LLM 把整条回复改成空串，挂在 “a reply the user heard in full stays whole”。`spoken.append` 放在 `super().process(...)` 之后也不对：播放回调里触发的打断会少算刚播出的那个词。

看什么：是不是顺着 KeyError 的调用链往上游找到 VAD；是不是先 `print(pipe.llm.context)` 看实际内容再改；改 TTS 时有没有想到 cancel 是在 `super().process(...)` 或 `synthesize(...)` 里同步到达的。

能过但要追问的写法：
- 在 STT 或 LLM 里跳过空转写，不改 VAD，测试也会变绿。问根因在哪：只有空白的块根本不该算用户说话，也不该触发一次 STT。
- 只在合成之后检查 `cancelled`（包括把列表推导改成生成器表达式这种一处改动）也能过：取消后会多合成一个词，但不会播出来。问这次多余的合成在真实 TTS 上要花什么。

提示：
- H1："Which processor first let through something it should have stopped?"
- H2："When does the first tts_audio frame leave TTS, relative to the synthesize calls?"
- H3：直接指出 `spoken` 在哪里创建，问它什么时候被清空。

追问：
- "Suppose each processor ran in its own task, with a queue in front of it. What changes about where you check for the cancel?"（取消要能清掉各处队列里已经排着的帧；只设一个标志不够）
- "Why should the context hold only the heard words?"（下一轮模型会以为用户听过整句；用户打断常常就是因为前半句已经答错了）
- "The lesson's skill lists LLM calls without streaming as a hard reject. Where would streaming change this pipeline?"（LLM 也按片段往下发 text 帧，TTS 按句或按词开始合成，首 token 和首音频延迟都下降）

### Part 2 通话录制（目标 12 分钟）

坑：
- 时间戳是纳秒整数（`1_730_000_000_123_456_789` 和它加 1 两条）。存成 double 会把两条变成同一个值，读回不相等。
- 负载是原始字节，里面有 `\n`、`\r\n`、`\x00` 和所有 256 个字节值，不能按行分隔，也不能当文本解码。
- 一条负载有 70,000 字节，长度字段用 16 位会报 `struct.error`。
- 写完要 flush：测试在 Recorder 还开着的时候就去读文件。
- 重开时不能用 `wb`（会清空），也不能再写一次 MAGIC（读回时第二个 MAGIC 会被当成一条记录）。
- 崩溃留下的半条记录：读的时候丢掉；重开继续写之前要先把它截掉，否则新记录接在半条记录后面，读回就错位了。测试截两次：第一次截在 70,000 字节那条记录的第 1,000 字节（负载中间），第二次只留下下一条记录的 3 个字节（头都不完整）。负载不完整时读出一条短记录，也会挂。
- 用 `r+b` 打开、`seek` 到最后一条完整记录的末尾直接写、不截断，也不对：新记录比半条记录短时，后面会留下残渣。第一次崩溃后接着写的是一条几十字节的短记录，残渣有将近 1,000 字节，读回时会被当成坏记录或多出来的记录。
- `2**63`、`-1` 和未知方向都要报 ValueError，不能漏成 `struct.error`。只查上界（`t_ns >= 2**63`）会放过 `-1`。

追问：
- "Recording a real call at 16 kHz, how big does this get, and what would you index?"（每秒 32 KB 的 PCM；可以另写一个按时间的偏移索引，或者按帧类型分文件）
- "Two processes writing the same recording?"（一个文件一个写者；或者用 O_APPEND 加整条一次写入，并说明它的边界）
- "How would you replay this to find where latency went?"（按方向和类型筛出每个轮次的第一帧，算相邻阶段的时间差）

### Part 3 轮次（目标 13 分钟）

坑：
- 静音从用户最后一次停止说话算，不是从最后一个转写片段算。用户说话期间不算静音（`tick(1200)` 那一步），再停下时从新的停止时刻重新算。
- 700 ms 正好就结束（`>=`）。
- 片段先 strip 再用单个空格连接；空片段整个忽略，包括它 0.1 的置信度。
- 只有拼接后的文本以 `?` 结尾才立刻结束；中间出现 `?` 不算；结尾带空格的 `"nine? "` 要算，所以要在 strip 之后看。
- 置信度看最弱的片段：第 3 轮是 0.9、0.4、0.9，取平均是 0.73，只看第一段或最后一段都是 0.9，都会错放过；第 4 轮是 0.9 和正好等于阈值的 0.6，要放行。把置信度乘起来是 0.54，会把这一轮错判成要重说。
- 低置信度的轮次也占轮次号，发出的是直接给 TTS 的 `text` 帧，LLM 看不到。
- 打断：机器人说话时用户开口才发 cancel，而且一个机器人轮次只发一次；cancel 带的是机器人正在说的那一轮的轮次号。测试里这时最新用户轮次和机器人轮次都是 4，带 `self.turn` 也能过，可以问两者什么时候会不同。
- `admit`：只放行最新一轮的帧，机器人还没开口时也要放行（测试先 `admit` 第 4 轮的第一帧，再 `bot_started(4)`）。拿 `bot_started` 记下的轮次去比，每条回复的第一帧都会被挡掉。被取消的那一轮全丢；用一个从不复位的全局标志会把下一轮也丢掉。在 `bot_started` 时复位的全局标志加上轮次号比较也能过，行为上说得通。

追问：
- "Why the weakest segment and not the mean?"（一个听错的名字或数字就足以让回复出错；平均会把它掩盖掉）
- "The lesson says turn detection is a model. Where would a semantic turn detector plug into this class?"（替换 `?` 规则和固定静音时长：模型给出“说完了”的概率，静音阈值随它变）
- "What happens to the LLM's context when a repeat prompt is spoken?"（context 不记这一轮，或者只记一条“没听清”的系统备注；要和产品一起定）

### Part 4 指标（目标 12 分钟）

坑：
- 窗口从通话时钟的 0 开始，空窗口也要输出全 0；流结束时，最后一个有事件的窗口也要输出。从第一个事件开始数窗口，会挂在 “windows start when the call starts”：那组数据只有 2500 ms 的一个事件，要输出三段。
- 正好落在 1000 ms 的事件属于下一个窗口。
- `voice_frames_total` 是 counter，从通话开始累计，不能每个窗口清零；`voice_window_frames` 是 gauge，只数这个窗口。
- 输出格式由测试里的解析器决定：每个指标族一行 `# TYPE`，后面紧跟这个族自己的样本，一个族的行连成一组（Prometheus 文本格式的要求）。把两行 `# TYPE` 都放在最前面再输出样本，或者按 stage 交替输出两个族，都会挂在 “a family's samples follow its own # TYPE line”。样本行是 `name{stage="..."} value`；整段以换行结尾。
- 只数 DOWNSTREAM 帧。课里的定义是：DOWNSTREAM 是数据流（音频进、语音出），UPSTREAM 是反馈和控制（cancel、metrics、barge-in）。练习 1 问的是延迟在哪一段堆积，看的是数据帧。测试在第二个窗口里放了一次打断：1750 ms 时 cancel 从 transport 往上游走，tts、llm、stt、vad 各看到一个 UPSTREAM 帧（就是测验 Q7 的那条路径），这几个 stage 在这个窗口里的计数都不能变。测试拿同一通电话去掉这次打断后的输出来比，要求一字不差。不看方向、每个事件都数，会挂在 “UPSTREAM frames are control, not data, and are not counted”；只在 gauge 里或者只在 counter 里跳过 UPSTREAM，也挂在这里。拿字符串 `"DOWNSTREAM"` 去比（常量的值是小写的 `"downstream"`），什么都数不到，挂在下一条断言。
- 解析器不看 `# HELP` 行，也不看两个指标族的先后顺序（Prometheus 也不要求族的顺序）。docstring 里写了，没写或顺序反了可以提一句，不算错。
- 样本按 `stages` 给的管道顺序，不排序。
- 窗口一关闭就要 yield：测试数拉取了多少个事件，先把整个流读完会挂。
- 骨架是 `async def` 里只有 raise，函数体里没有 `yield` 时测试报 `'async for' requires an object with __aiter__ method, got coroutine`，要看出来这里需要 async generator。
- 未知的 stage 报 ValueError，UPSTREAM 的事件也一样。在循环开头先把 UPSTREAM 事件 `continue` 掉、再查 stage，最后那条 `FrameEvent(0, "asr", UPSTREAM)` 会 DID NOT RAISE。
- 转义已经给了：`_escape` 先转义反斜杠，再转义引号和换行，标签值的转义只是顺带检查。stage 名里的引号、反斜杠和从配置文件带进来的换行，检查的是每个标签值都经过了它，直接把名字写进去会报 bad label syntax。不用它、自己另写的话，先转义引号再转义反斜杠会把 `\"` 变成 `\\"`，同样报 bad label syntax；用 `json.dumps` 会把 `é` 写成 `\u00e9`，这不是 Prometheus 的转义；漏了换行，一个样本会断成两行，解析器报 not a sample line。

测试抓不到的：先查 stage、再把 UPSTREAM 事件 `continue` 掉，不让它推进窗口，这组数据分不出来，因为打断在第二个窗口中间，后面还有数据帧；只有通话以一次打断结尾时才不一样。按 docstring，UPSTREAM 帧不计数，但它的时间照样推进窗口，打断所在的那个窗口要输出。看到这种写法可以问一句。

追问：
- "Why is the stage a label and not part of the metric name?"（同一个指标族才能按 stage 聚合、做 rate；名字里带 stage 会变成五个互不相关的指标）
- "What would make this label set explode?"（把轮次号、会话 id 放进标签；基数随通话数增长）
- "Say Prometheus scrapes every 15 s. Is a 1 s window gauge the right shape?"（更常见的做法是只暴露 counter，让服务端用 rate() 算每秒帧数；窗口 gauge 适合本地调试）
- "Barge-ins don't show up here at all. Where would you count them?"（另开一个只数控制帧的指标族，按帧类型分，比如 `voice_control_frames_total{kind="cancel"}`，再加一个从用户开口到 TTS 停下的直方图。混进数据帧的计数里，打断越多的通话，每一段看起来越忙）

### Part 5 延迟预算（目标 11 分钟）

坑：
- 课里的典型延迟表是默认值：五段下限相加 400 ms，上限相加 990 ms。
- 竞速（`first`）：最好情况取各分支最好值的最小，最坏情况取各分支最坏值的最小。直接选“下限最小的那个分支”会得到 (400, 990)，应该是 (400, 940)。
- 等全部（`all`）：两端都取最大；当成串行相加会得到 (550, 1190)。
- 子管道可以嵌套，也可以在两个地方各用一次；用一个全局的“见过”集合找环，会把第二次使用当成环。环要按当前路径判断，没有环检查会 RecursionError。接住 RecursionError 再改报 ValueError 也能过，问他这样写的代价：要等递归到 Python 的深度上限才发现，很深但没有环的管道也会被当成环。
- 实测区间要检查 0 ≤ best ≤ worst（测试里有 `[300, 200]` 和 `[-20, 200]`），带 `ms` 的阶段名也要在表里（`{"stage": "asr", "ms": [80, 120]}`）；一个 dict 只能有一种形式。空的并行块交给 `min()`、`max()` 本来就会报 ValueError，测试分不出有没有专门检查。
- 分档看最坏情况：600 算 premium，1200 算 common，1500 算 slow，1501 才是 broken。

追问：
- "Racing two STT providers takes 50 ms off the worst case here. What does it cost?"（两份 STT 费用；两路结果不一致时听谁的）
- "Where does a MultimodalAgent change this budget?"（STT、LLM、TTS 三段合成一段直接音频，换掉文本级控制）
- "Ranges add up worst-case to worst-case. Is that realistic?"（各段最坏值同时出现的概率很低；生产上更常用每段的 p95 分布做卷积或直接测端到端 p95）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出并发、崩溃恢复、指标基数、延迟分布 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
