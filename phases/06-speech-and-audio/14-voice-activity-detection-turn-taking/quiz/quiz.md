# 测验 · 语音活动检测与对话轮次交接——Silero、Cobra 与 Flush Trick（Voice Activity Detection & Turn-Taking — Silero, Cobra, and the Flush Trick）

> **阶段 06 · 语音与音频 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 每个 chunk 上的三个决策 | 这一帧是不是语音（VAD）？用户是否开始了新一句（onset）？用户是否说完了（end-pointing / turn-end）？ |
| 2 | 三级 VAD 级联 | 能量门（最便宜，-40 dBFS）→ Silero VAD（深度模型）→ 语义 turn detector（看语言上下文判断"是不是说完了"） |
| 3 | dBFS 与能量门 | `dBFS = 20·log10(RMS)`，满刻度 1.0 为 0 dBFS；-40 dBFS 即 RMS = 0.01；任何超过阈值的噪声都会误触发 |
| 4 | Silero VAD | MIT 协议、约 1M 参数、单 CPU 线程处理一个 30 ms chunk 约 1 ms；5% FPR 下 TPR 87.7%，是开源默认选择 |
| 5 | 四个关键参数 | 阈值（默认 >0.5，敏感 >0.3）、最短语音 250 ms、静音 hangover 500–800 ms、pre-roll 300–500 ms |
| 6 | turn-end 状态机 | `idle ↔ speaking` 两个状态：连续语音够长 → START；连续静音超过 hangover → END |
| 7 | Flush trick（Kyutai 2025） | 流式 STT 有 look-ahead 延迟（STT-1B 为 500 ms）；VAD 判定结束时发 flush 强制立即出结果，STT 约 4× 实时，500 ms 缓冲约 125 ms 处理完 |
| 8 | 语义端点检测 | "嗯……让我想想"里有长停顿；只靠静音会打断用户，需要看最近的词和语调来判断 |
| 9 | VAD 选型基准 | TPR @ 5% FPR：WebRTC 50%、Silero 87.7%、pyannote 约 95%、Cobra 98.9%；能量-only 不应上生产 |

### 核心技能（能动手做到）

- [ ] 能实现 `energy_vad`：算 RMS → 转 dBFS → 与阈值比较，并能心算 -40 dBFS / -20 dBFS 对应的 RMS
- [ ] 能实现 `idle/speaking` 两状态的 turn detector，并根据一串 20 ms chunk 的标签手算出 START / END 的时间戳
- [ ] 能找出并修复"idle 状态下 `speech_ms` 跨静音累积"导致零星咳嗽最终触发 START 的 bug
- [ ] 能用 `collections.deque(maxlen=...)` 实现 pre-roll 环形缓冲，并说明 pre-roll 至少要覆盖 `min_speech_ms` 带来的起点延迟
- [ ] 能按讲义用 `silero_vad.get_speech_timestamps` 设置 `threshold`、`min_speech_duration_ms`、`min_silence_duration_ms`、`speech_pad_ms`
- [ ] 能估算 flush trick 节省的延迟（look-ahead ÷ 处理倍速），并说出 STT 必须支持 flush
- [ ] 能为呼叫中心 / 端侧 / 无障碍等场景给出 VAD 型号、阈值、hangover、pre-roll 和是否启用语义 turn detector

---

## 二、基础自测（选择题）

**Q1.** 能量门的阈值设为 -40 dBFS。一个 chunk 的 RMS 恰好为多少时处在阈值上？

- A. 0.4
- B. 0.04
- C. 0.01
- D. 0.0001

**Q2.** 把静音 hangover 从 600 ms 调到 150 ms，最可能出现的问题是：

- A. 用户第一个字被截掉
- B. 用户句中稍一停顿，agent 就抢话、打断用户
- C. 咳嗽声被误识别为语音
- D. agent 回复显得迟钝

**Q3.** pre-roll 缓冲（VAD 触发前保留 300–500 ms 音频）主要解决：

- A. 背景噪声误触发
- B. 用户说完后 agent 等待太久
- C. VAD 触发有延迟，导致开头的 "hey" 等首字被截断
- D. STT 的 look-ahead 延迟

**Q4.** Kyutai STT-1B 的 look-ahead 为 500 ms，处理速度约 4× 实时。VAD 判定用户说完后立刻发送 flush，转写大约多久后可以拿到？

- A. 约 500 ms
- B. 约 2 s
- C. 约 125 ms
- D. 约 20 ms

**Q5.** 讲义说 Whisper streaming 不支持 flush trick，原因是：

- A. Whisper 不支持英语以外的语言
- B. Whisper 是块式（block-based）处理，总要等音频块攒满
- C. Whisper 的参数量太大，不能在 CPU 上跑
- D. Whisper 没有 VAD 接口

**Q6.** 用户说"我想改签……（停顿 1 秒）……改到明天"。只用 VAD + 600 ms 静音 hangover 会在停顿处判定结束。讲义推荐的解决办法是：

- A. 把能量门阈值调低到 -60 dBFS
- B. 把 hangover 永久调到 3 秒
- C. 叠加语义 turn detector（如 LiveKit turn-detector），结合最近的词和语调判断是否真正说完
- D. 换成 WebRTC VAD

**Q7.** 把 Silero 的判定阈值从 0.5 降到 0.3，通常会：

- A. 首字截断更少，但误触发更多
- B. 首字截断更多，误触发更少
- C. 两者都减少
- D. 只影响推理速度

**Q8.** 讲义的 VAD 对比表使用"TPR @ 5% FPR"作为指标。下列解释正确的是：

- A. 在 5% 的音频上测得的准确率
- B. 把阈值调到误报率（非语音被判成语音的比例）为 5% 时，真实语音帧被检出的比例
- C. 5% 的帧被跳过时的延迟
- D. 真阳性和假阳性的比值

---

## 三、动手 / 代码题

**Q9.**（预测输出 + 解释）`main.py` 中的"伪 Silero"如下，输入是 16 kHz、20 ms（320 个样本）的 chunk。讲话 chunk 是 `0.2 * gauss(0,1)`，咳嗽 chunk 前 1/5 是 `0.8 * gauss(0,1)`、其余几乎为 0。

```python
def fake_silero_vad(chunk, prev_state, threshold=0.5):
    rms = (sum(x * x for x in chunk) / len(chunk)) ** 0.5
    duration = len(chunk) / 16000.0
    transient = max(chunk) - min(chunk) > 0.6 and duration < 0.03
    if rms > 0.08 and not transient:
        return 0.92
    if rms > 0.05:
        return 0.55
    return 0.02
```

(a) 一个讲话 chunk 和一个咳嗽 chunk 分别会返回多少？`0.92` 这个分支在本脚本里能被走到吗？
(b) 运行结果中"energy-only"和"Silero-style"两组 turn 事件完全相同（都在 440/1480/2040/2800 ms）。那咳嗽到底是被谁挡住的？
(c) 第一个 START 出现在 440 ms，而语音实际从 200 ms 开始，为什么？

**Q10.**（找 bug + 修复）下面是 `main.py` 的 `TurnDetector.update`：

```python
    def update(self, is_speech, chunk_ms=20):
        if is_speech:
            self.speech_ms += chunk_ms
            self.silence_ms = 0
            if self.state == "idle" and self.speech_ms >= self.min_speech_ms:
                self.state = "speaking"
                return "START"
        else:
            if self.state == "speaking":
                self.silence_ms += chunk_ms
                if self.silence_ms >= self.silence_hangover_ms:
                    self.state = "idle"
                    self.speech_ms = 0
                    self.silence_ms = 0
                    return "END"
        return None
```

如果输入是"每隔 1 秒出现一次 20 ms 的咳嗽，其余全是静音"，持续十几秒，会发生什么？请修复，使 `min_speech_ms` 真正表示"**连续**语音时长"。修复后，原脚本里第二段语音的 START 时间会变吗？

**Q11.**（补全功能）`TurnDetector.__init__` 接收并保存了 `pre_roll_ms=300`，但代码里从没用过。请写一个包装类 `PreRollTurnDetector`：始终保留最近 `pre_roll_ms` 的 chunk，在 START 时把缓冲里的 chunk 拼到本次话语的开头。并回答：在默认 `min_speech_ms=250` 下，pre-roll 设成 100 ms 够不够？

---

## 四、面试高频题

**Q12.**（基础必考）VAD 和 turn detection（end-pointing）有什么区别？为什么"VAD + 固定静音超时"在生产中不够用？

**Q13.**（原理深挖）解释 Kyutai 的 flush trick：问题出在哪、怎么做、能省多少延迟、对 STT 服务有什么要求？

**Q14.**（场景设计）为机场航班改签的呼叫中心语音 agent 设计 VAD / 轮次交接方案：背景嘈杂、英语 + 西班牙语、要求 500 ms 内判定轮次结束。

**Q15.**（工程实践）你接手一个语音 agent，用户投诉"老被打断"和"反应慢"。你如何系统地调参和评估 VAD / turn-taking？

**Q16.**（追问型）在本节的级联方案里，从用户真正开口到 agent 拿到最终转写，延迟由哪几部分构成？每一部分如何压缩，代价是什么？

---

## 五、参考答案与解析

### Q1 — 答案：C

`dBFS = 20·log10(RMS)`，`20·log10(0.01) = 20 × (−2) = −40`。同理 RMS 0.1 → −20 dBFS，0.001 → −60 dBFS。代码中讲话 chunk 的 RMS 约 0.2（约 −14 dBFS），静音 chunk 约 0.002（约 −54 dBFS），所以能量门能区分二者——但同样也会放过 RMS 约 0.36 的咳嗽。

### Q2 — 答案：B

hangover 是"VAD 回到 0 之后还要等多久才宣布说完"。太短（讲义：Too short → interrupt user）就会把句中的正常停顿当成结束而抢话；D 是 hangover 太长的症状；A 是缺少 pre-roll 的症状；C 与 hangover 无关。

### Q3 — 答案：C

VAD 需要累计一段语音（比如 250 ms）才确认开口，确认时开头那段已经过去了。持续保留一个滚动的 pre-roll，在 START 时把它拼到话语前面，就不会丢掉 "hey" 之类的首字。讲义 Pitfalls："No pre-roll buffer. First 200–300 ms of user audio lost."

### Q4 — 答案：C

500 ms ÷ 4 = 125 ms。不 flush 时要等满 look-ahead（500 ms，STT-2.6B 甚至是 2.5 s）才有结果；flush 强制 STT 立刻处理掉缓冲区里剩下的音频。讲义："125 ms VAD + flush STT = conversational latency."

### Q5 — 答案：B

flush 需要 STT 是真正的流式模型、并且提供"立刻输出"的信号（讲义列举 Kyutai、Deepgram、AssemblyAI）。Whisper streaming 是块式的，总是等音频块攒满才解码，没有可以强制提前出结果的机制。

### Q6 — 答案：C

问题在于"停顿 ≠ 说完"。语义 turn detector 结合语言上下文（最近的词、语调）区分"句中停顿"和"说完了"，正是讲义 Tier 3 的作用。B 会让所有回复都慢 3 秒；A 只影响"是不是语音"，不影响"是不是说完"；D 是更差的 VAD。

### Q7 — 答案：A

阈值越低越敏感：更容易把真实语音的开头判成语音（首字截断少），也更容易把噪声判成语音（误报多）。讲义："Lower threshold = fewer first-word clips, more false positives."

### Q8 — 答案：B

这是 ROC 曲线上的一个点：固定 FPR = 5%，看 TPR（召回率）。固定 FPR 比较，才能公平对比不同模型（否则任何模型把阈值调低都能把 TPR 拉满）。WebRTC 只有 50%，意味着在同样的误报水平下要漏掉一半语音帧。

### Q9 — 参考答案

(a) **两者都返回 0.55，0.92 分支走不到。** `duration = 320/16000 = 0.02 < 0.03` 对每个 20 ms chunk 都恒成立；讲话 chunk 有 320 个 `0.2σ` 高斯样本，峰峰值实测最小也有约 0.95（> 0.6），所以 `transient` 恒为 True，第一个分支被跳过；RMS 约 0.2 > 0.05，于是返回 0.55。咳嗽 chunk 的 RMS 约 0.36、峰峰值更大，同样返回 0.55。0.55 ≥ 0.5，所以伪 Silero 在**帧级别把咳嗽也判成了语音**。

(b) 咳嗽是被 `TurnDetector` 的 **`min_speech_ms=250`** 挡住的：一次咳嗽只有 1 个 chunk（20 ms），远不到 250 ms，所以两种 VAD 都不会因为它触发 START。打印标题里的"many false positives on cough"和 takeaway"Silero VAD handles the cough"在这次运行中并没有得到体现——两组事件逐条相同。（还有一个细节：咳嗽的 20 ms 被计入了 `speech_ms`，使第二个 START 提前了一个 chunk，见 Q10。）

(c) 语音从第 10 个 chunk（200 ms）开始，`speech_ms` 每个 chunk 加 20，要到第 13 个语音 chunk（下标 22，即 440 ms）才达到 260 ≥ 250。也就是说 START 天生比真实开口晚约 `min_speech_ms`——这正是需要 pre-roll 的原因。同理 END 在 1480 ms：静音从 1000 ms 开始，累计 25 个 chunk = 500 ms 才触发。

### Q10 — 参考答案

**会误触发 START。** 在 `idle` 状态下遇到静音时，代码什么都不做，`speech_ms` 不会清零。于是每次 20 ms 的咳嗽都把 `speech_ms` 加 20，第 13 次咳嗽时累计到 260 ≥ 250，即使从来没有任何一段连续语音超过 20 ms，也会宣布用户开始说话（实测在约 12.2 s 处触发 START，又在 500 ms 后 END）。讲义 Step 3 的版本也有同样的问题。

修复：idle 状态下遇到非语音就把 `speech_ms` 清零：

```python
    def update(self, is_speech, chunk_ms=20):
        if is_speech:
            self.speech_ms += chunk_ms
            self.silence_ms = 0
            if self.state == "idle" and self.speech_ms >= self.min_speech_ms:
                self.state = "speaking"
                return "START"
        else:
            if self.state == "idle":
                self.speech_ms = 0              # 语音必须连续
            else:
                self.silence_ms += chunk_ms
                if self.silence_ms >= self.silence_hangover_ms:
                    self.state = "idle"
                    self.speech_ms = 0
                    self.silence_ms = 0
                    return "END"
        return None
```

修复后原脚本的事件变为 440 / 1480 / **2060** / 2800 ms：第二段语音的 START 晚了一个 chunk（20 ms），因为咳嗽那 20 ms 不再被"借用"。上面的"零星咳嗽"输入则不再产生任何事件。

更稳妥的生产做法是允许极短的间隙（比如真实语音里 1–2 帧的 VAD 抖动），即"连续语音中可容忍 ≤ 40 ms 的空洞"，否则清零会让 START 对 VAD 抖动过于敏感。

### Q11 — 参考答案

```python
from collections import deque


class PreRollTurnDetector:
    def __init__(self, detector, pre_roll_ms=300, chunk_ms=20):
        self.detector = detector
        self.chunk_ms = chunk_ms
        self.buffer = deque(maxlen=pre_roll_ms // chunk_ms)   # 环形缓冲，满了自动丢最旧的
        self.utterance = []

    def update(self, chunk, is_speech):
        event = self.detector.update(is_speech, self.chunk_ms)
        if self.detector.state == "speaking" or event == "END":
            if event == "START":
                self.utterance = list(self.buffer)   # 把开口前的音频补回来
            self.utterance.append(chunk)
        self.buffer.append(chunk)
        return event
```

用法：`pr = PreRollTurnDetector(TurnDetector(), pre_roll_ms=300)`，每个 chunk 调 `pr.update(chunk, energy_vad(chunk))`。在原脚本的数据上，第一个 START 在下标 22 触发时，缓冲里是下标 7–21 的 15 个 chunk，包含了真正的开口点（下标 10）。

**100 ms 不够。** START 比真实开口晚约 `min_speech_ms`（这里是 240–260 ms），100 ms 的 pre-roll 只能补回最后 5 个 chunk，开头约 140 ms 仍会丢失。经验法则：**pre-roll ≥ min_speech_ms + 余量**，所以讲义给的 300–500 ms 与 250 ms 的最短语音时长是配套的。

### Q12 — 参考回答要点

- 区别：VAD 是**逐帧二分类**（这一帧是不是语音）；turn detection 是**会话级决策**（这一轮是不是结束了），= VAD + 静音 hangover + 语义端点模型。
- 固定超时不够：①人在句中会停顿（思考、念航班号），超时短会打断，超时长又显得迟钝，一个常数无法两全；②噪声环境下 VAD 抖动，超时计数被频繁打断或误延长；③不同用户语速、场景差异大。
- 解决：Silero 级别的 VAD 打底；500–800 ms hangover；叠加语义 turn detector（LiveKit turn-detector 或自训小分类器）——判定"语义上已完整"时可以早结束，"明显没说完"时延长等待。
- 加分点：说出三个参数（min speech、hangover、pre-roll）分别影响什么；提到 START 本身有 `min_speech_ms` 的延迟，要靠 pre-roll 补偿。

### Q13 — 参考回答要点

- 问题：流式 STT 为了准确，会向后看一段音频（look-ahead）再输出。Kyutai STT-1B 为 500 ms，STT-2.6B 为 2.5 s。用户说完后，正常情况下必须再等这么久才拿到最后几个词。
- 做法：VAD（turn detector）一判定 END，就向 STT 发 flush 信号，强制它把缓冲里的剩余音频立即处理完并输出。
- 节省：STT 处理速度约 4× 实时，500 ms 的缓冲约 125 ms 处理完；讲义 skill 示例中的估计是 turn-end 延迟从约 400 ms 降到约 150 ms。
- 要求：STT 必须是真流式并暴露 flush 接口（Kyutai、Deepgram、AssemblyAI）；Whisper streaming 是块式的，不支持。
- 常见误区：以为 flush 能"凭空"减少计算——它只是不再等待未来音频，前提是 VAD 的 END 判定足够可靠，否则 flush 早了会截断最后的词。

### Q14 — 参考回答要点

（与本节 skill 示例一致的方案）

- VAD：Cobra（商用，抗噪、TPR 更高）；成本受限时回退 Silero。
- 参数：阈值约 0.4（机场底噪高，需要权衡）；最短语音 300 ms（过滤广播、行李车等短促噪声）；hangover 600 ms（用户念航班号时会停顿）；pre-roll 400 ms。
- 语义 turn detector：启用——"我要改签……改到明天"这种句中停顿很常见。
- Flush trick：在支持 flush 的 STT 上启用，预期 turn-end 延迟由约 400 ms 降到约 150 ms。
- 防护：低于最短时长的语音丢弃；始终保留 pre-roll；VAD / STT 服务不可用时 fail-open（把所有音频当语音处理，宁可多转写也不丢用户的话）；记录每次 VAD 触发事件用于后续调参。
- 加分点：双语场景要确认 VAD 和 turn detector 对西班牙语同样有效（Silero 训练覆盖 6000+ 语言；语义 turn detector 需要看所支持的语言）；按真实通话录音做离线回放评估。

### Q15 — 参考回答要点

- 先量化问题：定义并统计①误打断率（用户其实没说完却 END）、②首字截断率、③误触发率（噪声触发 START）、④端到端 turn 延迟（用户停止说话 → agent 开始回复）。
- 离线评估：在带人工标注的真实录音上算 VAD 帧级 precision / recall 或 TPR@FPR；讲义 Medium 练习就是在 5 分钟录音上调阈值、报告 precision / recall。
- 调参方向：老被打断 → 增大 hangover 或加语义 turn detector；反应慢 → 减小 hangover、启用 flush trick；首字丢失 → 加 / 加大 pre-roll、降低阈值；噪声误触发 → 提高阈值、增大 min speech、换更强的 VAD。
- 线上验证：A/B 测试不同 hangover（讲义："A/B test with target users"），看任务完成率、用户打断次数、满意度。
- 常见误区：只用安静环境的录音调参（讲义 Pitfall："Fixed threshold. Works in quiet, fails in noisy."）。

### Q16 — 参考回答要点

- 开口侧：VAD 确认开口要等 `min_speech_ms`（约 250 ms）——但这不影响最终转写的完整性，只要 pre-roll 能补回开头；流式 STT 可以边听边转。
- 结束侧（真正影响体验）：
  1. 静音 hangover（500–800 ms）：压缩手段是语义 turn detector——语义完整时可提前结束；代价是需要额外模型和标注数据。
  2. STT look-ahead（500 ms ~ 2.5 s）：用 flush trick 压到约 look-ahead / 4；代价是 STT 必须支持 flush，且 END 误判时会截断尾词。
  3. VAD 本身计算：Silero 每个 chunk 约 1 ms，可忽略。
- 取舍：hangover 越短越快但越容易打断；阈值越低首字越完整但越容易误触发——都需要按场景 A/B。
- 加分点：能把这些数字串成一条时间线（如"用户停止 → 500 ms hangover → flush → 125 ms → 转写就绪"），并指出语义 turn detector 才是同时缩短延迟又减少打断的关键。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 01 音频基础知识](../../01-audio-fundamentals/docs/zh.md)：采样率、RMS、分贝。
- [阶段 06 · 11 实时音频处理](../../11-real-time-audio-processing/docs/zh.md)：讲义列出的前置课，chunk、缓冲、流式处理。
- [阶段 06 · 12 构建语音助手管道](../../12-voice-assistant-pipeline/docs/zh.md)：讲义列出的前置课，VAD 在整条管道中的位置。
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：TPR、FPR、ROC、precision / recall。

### 本节被哪些后续内容用到
- [阶段 06 · 15 Streaming 语音到语音](../../15-streaming-speech-to-speech-moshi-hibiki/docs/zh.md)：全双工模型把"轮次交接"内化到模型里，是本节级联方案的替代路线。
- [阶段 06 · 04 语音识别 (ASR)](../../04-speech-recognition-asr/docs/zh.md)：flush trick 依赖的流式 STT。
- [阶段 14 · 22 语音 Agent（Pipecat / LiveKit）](../../../14-agent-engineering/22-voice-agents-pipecat-livekit/docs/zh.md)：生产语音 agent 框架里的 VAD 与 turn detector 配置。
- [阶段 19 · 03 实时语音助手（毕业项目）](../../../19-capstone-projects/03-realtime-voice-assistant/docs/zh.md)：把本节的 VAD + turn-taking 放进完整系统。
- [阶段 06 · 06 说话人识别与验证](../../06-speaker-recognition-verification/docs/zh.md)：pyannote 分段与 diarization。

### 延伸关键词
`Silero VAD ONNX` · `Picovoice Cobra` · `WebRTC VAD` · `pyannote segmentation` · `LiveKit turn-detector` · `semantic endpointing` · `barge-in / 插话` · `hysteresis（迟滞）` · `ROC / EER` · `Kyutai Unmute`
