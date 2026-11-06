# 测验 · 实时音频处理（Real-Time Audio Processing）

> **阶段 06 · 语音与音频 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（另有 Rust 版 `code/main.rs`，演示 20 ms 帧的增益 + 流式 FIR 处理） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 延迟预算 | 人类对话轮次间隔约 230 ms；>500 ms 显得机械，>1500 ms 显得坏了。讲义预算：采集 20 + VAD 10 + 流式 ASR 150 + LLM 首 token 100 + TTS 首块 100 + 播放 20 ≈ 400 ms |
| 2 | 10× 提速的三板斧 | 处处流式（streaming）、带部分结果的异步流水线（pipelining）、可中断生成（interruptible generation）；2022 年级联方案约 2500 ms，Moshi 约 200 ms，GPT-4o-realtime 约 320 ms |
| 3 | 帧 / 块 | 实时音频按固定大小的块流动，常用 20 ms（16 kHz 下 320 个采样点）；下游每一级都必须跟上这个节拍 |
| 4 | Ring buffer | 固定容量的环形 FIFO，生产者写、消费者读，热路径上不分配内存；容量 ≈ 最大延迟 × 采样率（2 秒 × 16 kHz = 32000），缓冲本身就是延迟下限 |
| 5 | VAD 门控 | 没人说话时不做下游工作；Silero VAD 在 CPU 上每帧不到 1 ms；最简单的是能量阈值（RMS / dBFS） |
| 6 | 流式 ASR | 随音频到达输出部分转写，lookahead 有界；讲义：Parakeet-CTC-0.6B 约 320 ms 延迟、2–5% WER，Whisper-Streaming 约 2 s |
| 7 | 打断（barge-in） | 用户在助手说话时开口，要在 100 ms 内检测、停止 TTS、丢弃剩余 LLM 输出；依赖异步 I/O 与可取消的流式 TTS |
| 8 | 传输与抖动 | WebRTC Opus：20 ms 帧、48 kHz、8–128 kbps 自适应；jitter buffer 重排与平滑网络包，典型 60–80 ms，太小有空洞、太大加延迟 |
| 9 | 常见工程问题 | GIL 与重模型抢占音频线程；管线内重采样增加 5–20 ms；TTS 首次请求预热 100–200 ms；没有 AEC 时机器人的声音回灌麦克风触发 ASR |
| 10 | 评估口径 | 以分阶段 P95（而非平均值）衡量延迟；TTS 块小于 200 ms 会出现 vocoder 伪影，320 ms 是讲义给出的甜点 |

### 核心技能（能动手做到）

- [ ] 能计算任意帧长 / 采样率下每帧的采样点数，以及 ring buffer 容量对应的最大缓冲延迟
- [ ] 能用 RMS → dBFS 实现能量 VAD，并根据信号电平选择阈值（如 `main.py` 中语音约 −16 dBFS、静音约 −54 dBFS、阈值 −40 dBFS）
- [ ] 能给 `main.py` 的 VAD 循环加上"静音挂起时间（hang-over）+ 最短语音时长"的端点检测，避免句中停顿把一句话切碎
- [ ] 能解释 `main.py` 的"整句缓冲后再 STT"为什么不是真正的流式，并估算句子变长时端到端延迟如何增长
- [ ] 能用 `asyncio` 写出可被打断的回复任务（barge-in 时 `cancel()` TTS 任务）
- [ ] 能为一个语音 Agent 填写分阶段延迟预算表，并指出每一级的选型（传输、VAD、ASR、LLM、TTS、AEC）

---

## 二、基础自测（选择题）

**Q1.** 16 kHz 单声道音频，帧长 20 ms，每帧有多少个采样点？一个容量为 32000 个采样点的 ring buffer 最多能缓冲多长时间？

- A. 160 个；1 秒
- B. 320 个；2 秒
- C. 320 个；32 秒
- D. 640 个；2 秒

**Q2.** 讲义把 2022 年约 2500 ms 的级联方案提速到 2026 年约 400 ms，归功于三项技术。下列哪一项**不在**其中？

- A. 处处流式
- B. 带部分结果的异步流水线
- C. 可中断生成
- D. 把所有模型参数量扩大 10 倍

**Q3.** 一位工程师"为了保险"在麦克风后面加了 500 ms 的缓冲。讲义对此的评价是：

- A. 好习惯，缓冲越大越稳定
- B. 缓冲就是延迟下限，应该尽量缩小
- C. 只影响内存，不影响延迟
- D. 只要 VAD 足够快就没关系

**Q4.** 用户在助手说话时插话，系统却继续把整段回答念完。讲义要求的处理是：

- A. 等助手说完再处理用户的话
- B. 在约 100 ms 内检测到插话、停止 TTS 播放、丢弃剩余的 LLM 输出
- C. 把用户音量调低
- D. 提高 VAD 阈值，忽略插话

**Q5.** 语音助手上线后经常"自己和自己对话"：它说的话被麦克风收进去又触发了 ASR。最直接的解决方案是：

- A. 加大 jitter buffer
- B. 回声消除（AEC，例如 WebRTC AEC3）
- C. 换更快的 LLM
- D. 降低采样率

**Q6.** 关于 jitter buffer，正确的是：

- A. 它用来消除扬声器到麦克风的回声
- B. 它重排乱序、迟到的网络包并做平滑；太小会出现可闻的空洞，太大会增加延迟，典型 60–80 ms
- C. 它越大越好
- D. 它只在本地文件处理中需要

**Q7.** 为降低首次回复延迟，下列哪项做法是讲义推荐的？

- A. 第一次真实请求到来时再加载 TTS 模型
- B. 预先加载并用一次假请求预热 TTS（讲义：即使 Kokoro 首次请求也有 100–200 ms 预热开销）
- C. 把 TTS 输出切成 50 ms 的小块，越小越快
- D. 在管线中间对每一帧做高质量重采样

**Q8.** 某团队汇报"平均端到端延迟 450 ms，达标"。按 skill 文件的要求，你最应该追问的是：

- A. 平均值是怎么算的
- B. 各阶段的 P95（以及 P99）延迟是多少
- C. 用了哪种编程语言
- D. 模型参数量多大

---

## 三、动手 / 代码题

**Q9.** `main.py` 的 VAD 基于 dBFS：

```python
CHUNK_MS = 20
VAD_THRESHOLD_DBFS = -40.0

def rms_dbfs(chunk):
    rms = (sum(x * x for x in chunk) / len(chunk)) ** 0.5
    return 20.0 * math.log10(max(rms, 1e-10))

def simulate_chunk(is_speech, rng):
    n = int(0.001 * CHUNK_MS * 16000)
    if is_speech:
        return [0.15 * rng.gauss(0, 1.0) for _ in range(n)]
    return [0.002 * rng.gauss(0, 1.0) for _ in range(n)]
```

(1) 估算语音块和静音块的 dBFS，说明 −40 dBFS 的阈值是否合理。
(2) `max(rms, 1e-10)` 防止了什么？全零输入时函数返回多少？
(3) 真实场景中，背景是 −35 dBFS 的空调噪声，这个 VAD 会怎样？

**Q10.** `main.py` 的端点检测循环如下。它有什么问题？请改写成支持"静音挂起时间（hang-over）"和"最短语音时长"的版本，并用"0.5 s 语音 + 0.1 s 停顿 + 0.5 s 语音 + 0.5 s 静音"的输入对比两种实现的结果。

```python
    buffered = []
    in_speech = False
    for c in chunks:
        active = vad(c)
        if active:
            buffered.extend(c)
            in_speech = True
        elif in_speech and len(buffered) >= 16000 * 0.3:
            break
```

**Q11.** `main.py` 中 `fake_stt` 的延迟是 `80 + 时长(秒) × 50` ms，LLM 固定 150 ms，TTS 首块固定 100 ms，且三者串行、STT 要等整句缓冲完才开始。
(1) 用户说 1.5 s、3 s、6 s 的话时，打印的 end-to-end 分别约是多少？哪一个超过 500 ms 的目标？
(2) 为什么说这个设计不是真正的"流式"？skill 文件对这种做法的态度是什么？
(3) 运行输出里最后一行是 `end-to-end: 405.6 ms   (target: &lt; 500 ms)`，这里有一个什么 bug？

**Q12.** 讲义 Step 1 的 ring buffer：

```python
class RingBuffer:
    def __init__(self, capacity):
        self.buf = collections.deque(maxlen=capacity)
    def write(self, frame):
        self.buf.extend(frame)
    def read(self, n):
        return [self.buf.popleft() for _ in range(min(n, len(self.buf)))]
    def level(self):
        return len(self.buf)
```

执行 `rb = RingBuffer(5); rb.write([1, 2, 3]); rb.write([4, 5, 6, 7]); print(rb.level(), rb.read(10), rb.level())` 会输出什么？这种行为在实时音频里意味着什么？你会怎么让"溢出"变得可观测？

---

## 四、面试高频题

**Q13.**（基础必考）设计一个语音助手的端到端延迟预算（目标 P95 < 500 ms），列出各阶段及预算，并说明哪些阶段可以重叠执行。

**Q14.**（原理深挖）解释流式 ASR、异步流水线、可中断生成分别如何降低"用户说完 → 听到回复"的延迟。为什么 2022 年的级联方案要 2.5 秒？

**Q15.**（工程实践）在 Python 中实现实时音频管线时，GIL、线程优先级、重采样、TTS 预热、回声分别会带来什么问题？各自怎么处理？

**Q16.**（场景设计）为一个电话车险报价语音 Agent 选型（英文、P95 < 500 ms、每周 5 万分钟、日志不能含 PII），给出传输、VAD、STT、LLM、TTS、编排与可观测性方案。

**Q17.**（追问型）用户在助手说话时插话（barge-in）。从检测、取消到状态恢复，完整说说怎么做？如何避免"误打断"（比如用户只是"嗯"了一声，或者是助手自己的回声）？

---

## 五、参考答案与解析

### Q1 — 答案：B

`16000 × 0.020 = 320` 个采样点/帧；`32000 / 16000 = 2` 秒。讲义原文："20 ms (320 samples at 16 kHz)"、"a 2-second 16 kHz ring = 32,000 samples"。A 是按 8 kHz 算的帧长；C 混淆了采样点数与毫秒；D 是 32 kHz 的帧长。

### Q2 — 答案：D

讲义："The 10× improvement came from three techniques: (1) streaming everywhere, (2) asynchronous pipelining with partial results, (3) interruptible generation." 提速来自架构与调度，而不是更大的模型——更大的模型通常反而更慢。

### Q3 — 答案：B

讲义 Pitfalls："Buffering 500 ms to be safe. The buffer *is* your latency floor. Shrink it." 缓冲区里的每一毫秒音频都要先等它填满才会被处理，直接叠加到端到端延迟上。

### Q4 — 答案：B

讲义：barge-in 时必须 (a) 检测插话、(b) 停止 TTS、(c) 丢弃剩余 LLM 输出，"All within 100 ms, or the user perceives deaf assistant"。D 会让系统"听不见"用户。

### Q5 — 答案：B

讲义 Common gotchas："Without AEC, TTS output re-enters the mic and triggers ASR on the bot's own voice. WebRTC AEC3 is the open-source default." jitter buffer 解决网络抖动，与回声无关。

### Q6 — 答案：B

见讲义 jitter buffer 一段与 Key Terms（"60–80 ms typical"）。A 描述的是 AEC；C 错，越大延迟越高；D 错，它处理的正是网络传输。

### Q7 — 答案：B

讲义："TTS priming. Even fast TTS like Kokoro has a 100–200 ms warm-up on first request. Cache model + warm it with a dummy run before the first real turn." C 错，讲义说低于 200 ms 的 TTS 块会让 vocoder 伪影可闻，320 ms 是甜点；D 错，管线内重采样会增加 5–20 ms，应在入口一次性重采样或使用零延迟重采样器。

### Q8 — 答案：B

skill 文件："Refuse evaluation by average latency — require P95"，并要求按阶段统计 P50/P95/P99 直方图。平均值会掩盖长尾：10% 的请求卡 2 秒，用户就会觉得"经常坏掉"。

### Q9 — 参考答案

(1) 语音块：高斯噪声标准差 0.15，RMS ≈ 0.15，`20·log10(0.15) ≈ −16.5 dBFS`；静音块：RMS ≈ 0.002，`20·log10(0.002) ≈ −54 dBFS`。实测分别为 −16.2 和 −54.2 dBFS。阈值 −40 dBFS 落在两者之间，各有十几到二十几 dB 的余量，对这组模拟数据完全可靠。

(2) 防止 `log10(0)` 抛 `ValueError: math domain error`。全零输入时 RMS 为 0，被替换成 `1e-10`，返回 `20 × (−10) = −200 dBFS`，相当于"极安静"。

(3) −35 dBFS 的噪声高于 −40 dBFS 阈值，VAD 会把空调噪声一直判为"有语音"：端点永远检测不到，下游 ASR 持续收到噪声（还可能引发 Whisper 类模型的幻觉）。能量 VAD 只看音量、不看"像不像人声"，所以讲义推荐生产中换成 Silero VAD 这类模型 VAD；即使用能量法，也应做自适应噪声底估计（例如阈值 = 噪声底 + 若干 dB）。

### Q10 — 参考答案

问题：只要出现**一个** 20 ms 的静音块、且已缓冲 ≥ 0.3 s，就立即结束这句话。正常说话中的短停顿（换气、词间停顿）都会把一句话切断；另外没有"静音挂起时间"，也就无法区分"说完了"和"停顿一下"。

改写（已运行验证）：

```python
def endpoint(chunks, hangover_ms=300, min_speech_ms=200, sr=16000):
    buffered, in_speech, silent_ms = [], False, 0
    for c in chunks:
        if vad(c):
            buffered.extend(c)
            in_speech, silent_ms = True, 0
        elif in_speech:
            buffered.extend(c)                 # 保留短停顿，避免把一句话切碎
            silent_ms += CHUNK_MS
            if silent_ms >= hangover_ms and len(buffered) >= sr * min_speech_ms / 1000:
                break
    trailing = silent_ms * sr // 1000          # 去掉末尾用于判定的静音
    return buffered[:len(buffered) - trailing] if trailing else buffered
```

对比结果（"0.5 s 语音 + 0.1 s 停顿 + 0.5 s 语音 + 0.5 s 静音"）：原实现只缓冲到 **0.5 s**，在第一个停顿处就截断了；新实现得到 **1.1 s**（两段语音 + 中间 0.1 s 停顿），完整保留了整句话。

取舍：hang-over 越长越不容易误切，但每次回复都会多等这么久——它直接计入端到端延迟。skill 文件示例用的是"min speech 220 ms、silence hang-over 400 ms"，并叠加 LiveKit 的 turn-detector 模型做语义层面的轮次判断（第 14 节）。

### Q11 — 参考答案

(1) STT 延迟 = 80 + 50 × 时长：1.5 s → 155 ms，3 s → 230 ms，6 s → 380 ms；再加 LLM 150 ms 和 TTS 100 ms，end-to-end 分别约 **405 ms、480 ms、630 ms**，6 秒那句超过 500 ms 目标。（实际打印值会多出零点几毫秒的 `sleep` 误差，例如 405.6 ms。）

(2) 三点：①STT 要等整句缓冲完才开始，延迟随句子长度线性增长；真正的流式 ASR 在用户说话的同时就在转写，说完时只剩很小的尾部延迟。②三个阶段严格串行，没有利用"LLM 首 token 出来就送 TTS"的流水线重叠。③打印的 end-to-end 只从 STT 开始计时，没有包含端点检测等待的静音时间，用户实际感知的延迟更长。skill 文件明确："Refuse deploys that buffer entire utterances before STT. Refuse TTS that does not stream."

(3) 源码第 98 行是 `print(f"  end-to-end: {total:.1f} ms   (target: &lt; 500 ms)")`。`&lt;` 是 HTML 实体，在 Python 字符串里不会被转义，所以终端上打印出字面的 `&lt;` 而不是 `<`（很可能是文档处理流程把 `<` 误转义了）。修复：改回 `(target: < 500 ms)`。

### Q12 — 参考答案

输出：

```text
5 [3, 4, 5, 6, 7] 0
```

`deque(maxlen=5)` 写满后再 `extend` 会**静默丢弃最旧的元素**：写入 7 个样本后只剩最新的 `[3, 4, 5, 6, 7]`，`1, 2` 被覆盖了。`read(10)` 只能读出现有的 5 个，之后缓冲区为空。

实时含义：这是一次**溢出（overrun）**——消费者（ASR）跟不上生产者（麦克风），最早的音频被丢掉，用户的话会"缺头"，而且没有任何报错。对实时系统来说，"丢旧保新"通常是正确策略（宁可丢一点也不能让延迟无限增长），但必须可观测：

```python
class RingBuffer:
    def __init__(self, capacity):
        self.buf = collections.deque(maxlen=capacity)
        self.dropped = 0
    def write(self, frame):
        overflow = len(self.buf) + len(frame) - self.buf.maxlen
        if overflow > 0:
            self.dropped += overflow           # 记录被覆盖的样本数，上报监控
        self.buf.extend(frame)
```

再配合监控指标（丢弃样本数、缓冲水位 `level()`）报警。另外，讲义 Key Terms 提到生产中的 ring buffer 是无锁或单生产者单消费者（SPSC）结构；CPython 的 `deque` 的 `append`/`popleft` 是线程安全的，可以用于演示，但音频回调最好放在 C 层（sounddevice / PortAudio）。

### Q13 — 参考回答要点

- **预算表**（讲义）：麦克风 → 缓冲 20 ms；VAD 10 ms；流式 ASR 150 ms；LLM 首 token 100 ms；TTS 首块 100 ms；渲染 → 扬声器 20 ms；合计约 400 ms。若走网络，还要加上下行/上行网络（`main.py` Step 4 给出各 50–100 ms）和 jitter buffer（60–80 ms）。
- **可以重叠的部分**：
  - ASR 与用户说话并行（流式），说完时只剩最后一个 chunk 的处理；
  - LLM 在拿到最终转写后立即流式输出，前若干个 token 一到就送 TTS（skill 文件："Pin the first 20 tokens before TTS kicks in"）；
  - TTS 边合成边播放，第一块出来就开始播放。
- **度量**：按阶段统计 P50/P95/P99，而不是平均值；用户感知延迟应从"用户停止说话"算到"听到第一个音"，包含端点检测的等待时间。
- **加分点**：指出端点检测的 hang-over 是隐藏的大头（400 ms hang-over 就可能吃掉整个预算），需要用语义轮次检测模型缩短它（第 14 节）；或者采用全双工端到端模型（Moshi 约 200 ms，第 15 节）。

### Q14 — 参考回答要点

- **2022 年的级联为什么慢**：录完整句 → 整句送 ASR → 整段文本送 LLM、等完整回复 → 整段送 TTS、合成完再播放。每一级都等上一级"全部完成"，延迟是各阶段完整耗时之和，再加上整句缓冲，约 2.5 秒。
- **流式 ASR**：边听边转写，说完时只需处理最后一个 chunk，ASR 的有效延迟从"与句长成正比"变成"约一个 chunk + lookahead"（讲义：Parakeet 约 320 ms）。
- **异步流水线 + 部分结果**：各级之间用队列连接，上一级的部分输出立即交给下一级（LLM 的前几个 token → TTS 的第一个块），总延迟变为各级"首个输出时间"之和。
- **可中断生成**：不是降低首响延迟，而是降低"用户插话 → 系统停下来听"的延迟，避免用户等系统说完，提升交互的实时感；同时节省被丢弃部分的计算。
- **常见误区**：只优化模型推理速度，忽略缓冲、端点检测、网络、预热这些"非模型"延迟。

### Q15 — 参考回答要点

- **GIL / 线程**：Python 的 GIL 加上重模型推理会让音频线程拿不到 CPU，出现爆音、丢帧。对策：使用 C 回调的音频库（sounddevice / PortAudio），让 Python 不在热路径上；模型推理放到独立进程或原生扩展中；音频线程设置更高优先级（讲义 Pitfalls："Not pinning threads"）。
- **重采样**：管线中间重采样会增加 5–20 ms。对策：在入口一次性重采样到统一采样率，或使用零延迟/低延迟重采样器（讲义提到 polyphase、`soxr_hq`）。
- **TTS 预热**：首次请求有 100–200 ms 额外开销。对策：启动时加载模型并用假请求预热，模型常驻。
- **回声**：没有 AEC，机器人的声音被麦克风收进去触发 ASR，甚至触发误打断。对策：WebRTC AEC3；浏览器/移动端 WebRTC 栈通常自带。
- **健壮性**：讲义 Pitfalls："Single-shot error handling. Audio pipelines must be crash-proof." 每个阶段都要捕获异常并降级，不能让一个异常结束整个会话。

### Q16 — 参考回答要点

参考 skill 文件的示例方案：

- **传输**：LiveKit Agents + Twilio SIP（电话渠道，有呼叫中心规模的验证）。
- **VAD + 轮次**：Silero VAD（阈值 0.45、最短语音 220 ms、静音挂起 400 ms），叠加 LiveKit turn-detector。
- **STT**：Deepgram Nova-3（约 150 ms P95）；若需要本地部署审计，备选 Parakeet-TDT。
- **LLM**：GPT-4o 流式输出，前 20 个 token 就送 TTS；对提示词注入做后置过滤。
- **TTS**：Cartesia Sonic 2（约 150 ms 首音），使用预设音色、不做克隆。
- **编排**：LiveKit Agents；可观测性用分阶段 P50/P95/P99 直方图、误打断率、掉线率、抽样 WER。
- **PII**：日志落盘前用正则 + NER 去除 CVV、SSN、出生日期等，保留 30 天。
- **成本**：每周 5 万分钟约每月 20 万分钟以上，skill 文件要求超过每月 10 万分钟时，必须先和自建方案做成本对比，才能选 Vapi / Retell 这类托管平台。

### Q17 — 参考回答要点

- **检测**：在助手播放期间仍然运行 VAD（必须在 AEC 之后，否则会被自己的回声触发）；检测到用户语音持续超过一个最短时长才判定为打断。
- **取消**：立即停止音频播放（清空播放缓冲）；取消 TTS 任务（讲义 Step 4：`self.tts_task.cancel()`）；取消/丢弃 LLM 剩余输出。讲义要求整个过程在 100 ms 内完成。
- **状态恢复**：把助手"实际已经说出口"的部分写入对话历史（而不是 LLM 生成的全部文本），否则 LLM 会以为用户听到了没播出的内容；然后把用户的新话语送入流式 ASR。
- **避免误打断**：
  - AEC 去掉自身回声；
  - 设置最短语音时长和能量/概率阈值；
  - 对"嗯""对"这类附和（backchannel）不打断，或者用语义轮次检测模型判断用户是否真的想接话（第 14 节）；
  - 监控误打断率（skill 文件列为必备指标）。
- **加分点**：全双工模型（Moshi）把"听"和"说"放在同一个模型中同时进行，天然支持打断与附和（第 15 节）。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 01 音频基础知识](../../01-audio-fundamentals/docs/zh.md)：采样率、采样点、dBFS 与振幅的关系。
- [阶段 06 · 04 语音识别 (ASR)](../../04-speech-recognition-asr/docs/zh.md)：CTC / RNN-T 为什么天然适合流式。
- [阶段 06 · 07 文本转语音 (TTS)](../../07-text-to-speech/docs/zh.md)：Kokoro 等 TTS 的首块延迟与采样率。

### 本节被哪些后续内容用到
- [阶段 06 · 12 构建语音助手管道](../../12-voice-assistant-pipeline/docs/zh.md)：把本节的延迟预算落到完整的 STT → LLM → TTS 管线。
- [阶段 06 · 14 语音活动检测与对话轮次](../../14-voice-activity-detection-turn-taking/docs/zh.md)：Silero、语义轮次检测、端点检测的系统讲解。
- [阶段 06 · 15 Streaming 语音到语音（Moshi、Hibiki）](../../15-streaming-speech-to-speech-moshi-hibiki/docs/zh.md)：全双工、约 200 ms 的端到端架构。
- [阶段 14 · 22 语音 Agent（Pipecat / LiveKit）](../../../14-agent-engineering/22-voice-agents-pipecat-livekit/docs/zh.md)：生产级语音 Agent 编排框架。
- [阶段 17 · 08 推理指标与 Goodput](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：TTFT、P95/P99 等延迟指标的定义与度量。
- [阶段 19 · 03 实时语音助手（毕业项目）](../../../19-capstone-projects/03-realtime-voice-assistant/docs/zh.md)：端到端实战。

### 延伸关键词
`ring buffer / SPSC` · `dBFS` · `endpointing / hang-over` · `Silero VAD` · `streaming ASR lookahead` · `TTFA (time to first audio)` · `barge-in` · `AEC3` · `jitter buffer` · `Opus` · `P95 latency` · `full duplex`
