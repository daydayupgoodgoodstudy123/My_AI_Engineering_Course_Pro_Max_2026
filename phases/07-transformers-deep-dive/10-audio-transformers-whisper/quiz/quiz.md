# 测验 · 音频 Transformers — Whisper 架构（Audio Transformers — Whisper Architecture）

> **阶段 07 · Transformers 深入 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Whisper 的三个赌注 | ①68 万小时弱标注互联网音频；②一个 decoder 联合训练转写、翻译、VAD、语种识别、时间戳；③标准 encoder-decoder Transformer，不用 vocoder、CTC、HMM |
| 2 | 预处理 | 16 kHz 采样，裁剪/补齐到 30 秒；帧长 25 ms（400 采样点）、帧移 10 ms（160 采样点）→ 约 3000 帧的 log-mel 频谱，这就是 Whisper 看到的"输入图像" |
| 3 | 卷积 stem | 两层 kernel=3 的 Conv1D，把 3000 帧下采样为 1500 个时间步，参数很少 |
| 4 | Encoder / Decoder | encoder 在 1500 个时间步上做 self-attention（正弦位置编码、GELU FFN）；decoder 用 BPE 词表自回归输出文本，通过 cross-attention 读取 encoder 输出 |
| 5 | Task tokens | decoder 前缀 `<\|startoftranscript\|> <\|语种\|> <\|transcribe 或 translate\|>`（可选 `<\|notimestamps\|>`）决定任务——语音版的"指令" |
| 6 | 输出与时间戳 | beam search（宽度 5）+ log-prob 阈值；不加 `<\|notimestamps\|>` 时以 0.02 秒为粒度预测时间戳 |
| 7 | 模型尺寸与 turbo | tiny 39M → large-v3 1550M；large-v3-turbo 保留完整 encoder，把 decoder 从 32 层砍到 4 层（809M），解码约快 8 倍 |
| 8 | Whisper 不做的事 | 不做说话人分离（配 pyannote）；不原生支持流式（30 秒固定窗口，靠 VAD + 重叠拼接）；不跨 30 秒保持上下文 |
| 9 | 生产生态 | faster-whisper（CTranslate2 + int8，约 4 倍速）、WhisperX、Moonshine（边缘设备）；VAD 先去静音能大幅降成本 |

### 核心技能（能动手做到）

- [ ] 用纯 Python 实现分帧 `frame_signal`，能用公式 `⌊(N − frame)/hop⌋ + 1` 预测帧数，并解释为什么 30 秒得到 2998 帧而不是 3000 帧
- [ ] 实现 `pad_or_clip`，把任意长度的帧序列补齐/截断到 3000 帧，并说出它和 Whisper 官方"先补齐音频再算频谱"的区别
- [ ] 用 `whisper_prompt` 为"法语音频 → 英文文本、无时间戳"等任务写出正确的 task token 前缀
- [ ] 能画出 Whisper 的数据流并写出每一步形状：`480000 采样点 → (80, 3000) log-mel → (1500, d_model) → 文本 token`
- [ ] 用 `numpy.fft` 实现 80 维 log-mel 频谱（讲义练习 2），说明 mel 与 log 各自的作用
- [ ] 为长音频设计分块方案（例如 10 秒窗口、2 秒重叠 + VAD），并说明如何合并重叠部分的转写结果

---

## 二、基础自测（选择题）

**Q1.** Whisper 的输入是 30 秒、16 kHz 的音频，帧移 10 ms。经过两层卷积 stem 后，encoder 处理的序列长度是：

- A. 480,000
- B. 3,000
- C. 1,500
- D. 750

**Q2.** 想让 Whisper 把一段**法语**语音翻译成**英文**文本，decoder 前缀应该是：

- A. `<|startoftranscript|> <|en|> <|translate|>`
- B. `<|startoftranscript|> <|fr|> <|translate|>`
- C. `<|startoftranscript|> <|fr|> <|transcribe|>`
- D. `<|startoftranscript|> <|en|> <|transcribe|>`

**Q3.** 关于 Whisper 的建模方式，下列说法**正确**的是：

- A. 使用 CTC loss，对每一帧独立输出字符
- B. 使用 HMM + 声学模型 + 语言模型的传统流水线
- C. 标准的 encoder-decoder Transformer：encoder 吃 log-mel 频谱，decoder 自回归输出文本 token
- D. 先用 vocoder 把音频变成波形特征，再接一个 encoder-only 模型

**Q4.** Whisper large-v3-turbo 相比 large-v3 做了什么改动，为什么能大幅提速？

- A. 把 encoder 从 32 层砍到 4 层，因为 encoder 计算量最大
- B. 把 decoder 从 32 层砍到 4 层，因为 decoder 要逐 token 自回归运行，而 encoder 每个 30 秒窗口只运行一次
- C. 把 d_model 从 1280 降到 384
- D. 把输入从 30 秒改为 5 秒

**Q5.** 某会议录音有 4 个人轮流发言，你需要"谁在什么时候说了什么"。只用 Whisper 会缺少哪一环？

- A. 语种识别
- B. 时间戳
- C. 说话人分离（diarization），需要额外配合 pyannote 等工具
- D. 标点符号

**Q6.** Whisper 使用 **log**-**mel** 频谱作为输入。"mel"和"log"分别对应什么？

- A. mel：把频率轴映射到更接近人耳音高感知的刻度；log：压缩能量的动态范围，近似人耳对响度的感知
- B. mel：一种降噪滤波器；log：把时间轴压缩为对数刻度
- C. mel：把采样率降到 8 kHz；log：把幅值转换为分贝后取整
- D. 两者都只是为了让数据变成整数，便于量化

**Q7.** 在 ASR 流水线中先加一个 VAD（Voice Activity Detection）门控，主要好处是：

- A. 提升模型的语种识别能力
- B. 去掉静音段，减少需要送入 ASR 的音频量，显著降低成本，也为流式/分块提供切分点
- C. 自动完成说话人分离
- D. 把 30 秒窗口扩展到无限长上下文

**Q8.** 对一段 1 秒的 16 kHz 音频，用 `frame_size=400, hop=160` 且**不做任何边界补齐**的方式分帧，得到的帧数是：

- A. 100
- B. 101
- C. 98
- D. 40

---

## 三、动手 / 代码题

**Q9.** 运行 `code/main.py` 得到：

```text
1s signal → 16000 samples → 98 frames
5s signal → 80000 samples → 498 frames
```

(1) 写出帧数公式，并算出 30 秒（480,000 个采样点）时 `frame_signal` 得到多少帧。(2) 讲义说 30 秒对应 3000 帧，Whisper 官方实现是怎么恰好得到 3000 帧的？(3) 本代码里少掉的这两帧最后是被谁"补"上的？

```python
def frame_signal(x, frame_size=FRAME_SIZE, hop=HOP):
    frames = []
    for start in range(0, len(x) - frame_size + 1, hop):
        frames.append(x[start:start + frame_size])
    return frames
```

**Q10.** 输出中前 5 帧的 log 能量完全相同：

```text
first 5 frame log-energies: +5.298, +5.298, +5.298, +5.298, +5.298
```

(1) 为什么恰好是 `5.298`，且每一帧都一样？（提示：440 Hz、16 kHz、400 个采样点。）(2) 如果把输入换成 880 Hz 的正弦波（振幅不变），每帧能量会变吗？这说明"每帧一个能量值"作为 mel 的替身缺了什么？

**Q11.** 下面的 `pad_or_clip` 有一个隐蔽的问题：

```python
def pad_or_clip(frames, target):
    if len(frames) >= target:
        return frames[:target]
    pad_frame = [0.0] * len(frames[0]) if frames else [0.0] * FRAME_SIZE
    return frames + [pad_frame] * (target - len(frames))
```

(1) 用 5 秒信号补齐到 3000 帧后，执行 `padded[-1][0] = 1.0`，`padded[-2][0]` 会变成多少？为什么？(2) 修复这个问题。(3) 如果对补齐的全零帧调用 `frame_energy`，会得到什么值？这对模型输入有什么影响，Whisper 官方的 log-mel 是怎么处理这个问题的？

---

## 四、面试高频题

**Q12.**（基础必考）请完整描述 Whisper 从原始波形到输出文本的流程，写出各阶段张量形状，并解释 task token 的作用。

**Q13.**（原理深挖）对比 Whisper（encoder-decoder + 自回归）与 wav2vec 2.0 + CTC 这类方案：训练数据、对齐方式、多任务能力、推理延迟和典型失效模式各有什么不同？

**Q14.**（工程实践）你要批量转写 1 万小时的客服录音（每段 5–60 分钟，可能多人对话）。请设计端到端方案：模型、量化、分块、VAD、解码参数、后处理和评测。

**Q15.**（场景设计）为一个实时语音助手设计 ASR 部分，要求从用户说完到识别出文字的延迟 < 300 ms。你会怎么选模型和参数？Whisper 的哪些特性对此不利？

**Q16.**（追问型）为什么 Whisper-turbo 选择砍 decoder 而不是 encoder？请从计算量与延迟的角度定量说明。

---

## 五、参考答案与解析

### Q1 — 答案：C

30 秒 / 10 ms = 3000 帧 log-mel；卷积 stem 总共做 2 倍下采样，3000 → 1500，encoder 在 1500 个时间步上做 self-attention。A 是原始采样点数；B 是 stem 之前的帧数；D 是"两层都 stride 2"时会得到的数字。补充：讲义写的是"两层 kernel 3、stride 2 的 Conv1D"，但若两层都 stride 2 会得到 750；OpenAI 参考实现中第一层 stride 为 1、第二层 stride 为 2，总下采样 2 倍，才与"3000 → 1500"一致。

### Q2 — 答案：B

语种 token 表示**输入音频的语言**，任务 token 表示**做什么**：`<|translate|>` 在 Whisper 中的含义是"翻译成英文"。所以是 `<|fr|> <|translate|>`。本节代码的示例 `("French translation to English, no timestamps", whisper_prompt(lang="fr", task="translate", timestamps=False))` 正是这个组合。A 把语种写成了目标语言；C 会输出法语转写。

### Q3 — 答案：C

讲义"三个赌注"之三：标准 encoder-decoder Transformer，"No vocoder, no CTC, no HMM"。Key Terms 也特别强调 CTC 是经典 ASR loss，"Whisper does NOT use it"。

### Q4 — 答案：B

讲义："Large-v3-turbo (2024) cut the decoder from 32 layers to 4. 8× faster decoding with <1 WER point regression." encoder 对每个 30 秒窗口只跑一次（并行处理 1500 个时间步），decoder 则每生成一个 token 都要把所有层跑一遍，层数直接决定串行延迟。

### Q5 — 答案：C

讲义"What Whisper does not do"第一条：No diarization，需要搭配 pyannote。Whisper 本身能做语种识别（A）、时间戳（B），也会输出带标点的文本（D）。

### Q6 — 答案：A

mel 刻度把线性频率映射到更接近人耳音高感知的刻度（低频分辨率高、高频分辨率低）；取 log 是因为人耳对响度的感知近似对数关系，同时把跨越多个数量级的能量压缩到适合神经网络的范围（讲义 Key Terms：log "approximates human perception of loudness"）。

### Q7 — 答案：B

讲义 Key Terms：VAD 是"在 ASR 之前去掉静音的门控，大幅降低成本"；同时 faster-whisper、WhisperX 正是靠 VAD + 重叠来实现分块/流式。VAD 不做说话人分离（C），也不能扩展 Whisper 的 30 秒上下文（D）。

### Q8 — 答案：C

`⌊(16000 − 400) / 160⌋ + 1 = ⌊97.5⌋ + 1 = 98`。这正是代码输出 `1s signal → 16000 samples → 98 frames`。讲义练习 1 说"约 100 帧"——"约"字很关键：官方实现会在两端补齐（见 Q9），所以每秒恰好 100 帧。

### Q9 — 参考答案

(1) 帧数 = `⌊(N − frame_size) / hop⌋ + 1`（`range` 的上界是 `len(x) - frame_size + 1`，保证最后一帧不越界）。30 秒：`⌊(480000 − 400) / 160⌋ + 1 = 2997 + 1 = 2998` 帧（已用代码验证）。

(2) OpenAI 参考实现先把**音频**补齐/截断到 480,000 个采样点，再用 `torch.stft` 计算频谱；`torch.stft` 默认 `center=True`，会在信号两端各补半个窗口（200 个采样点），于是帧数变成 `1 + 480000 / 160 = 3001`，再丢掉最后一帧，得到恰好 3000 帧。边界补齐还有一个好处：第 k 帧的中心正好对应时间 `k × 10 ms`，时间戳计算更整齐。

(3) 本代码的 `main()` 只演示了 5 秒信号（498 帧），由 `pad_or_clip(frames5, TARGET_FRAMES)` 补上 2502 个全零帧到 3000。如果对 30 秒信号调用，`pad_or_clip` 同样会补上缺的 2 帧。也就是说，本代码是"先分帧、后补帧"，而官方是"先补音频、后分帧"。

### Q10 — 参考答案

(1) 400 个采样点 = 25 ms，440 Hz 在 25 ms 内恰好振荡 `440 × 0.025 = 11` 个**完整周期**。对整数个周期，`Σ sin² = N / 2 = 400 / 2 = 200`，与相位无关。所以无论每帧从哪个相位开始（帧移 160 个采样点 = 4.4 个周期，相位每帧都不同），能量都是 200，`ln(200 + 1e-9) ≈ 5.298`。

(2) 880 Hz 在 25 ms 内是 22 个完整周期，能量**仍然是 200**，log 能量同样是 5.298。也就是说，"每帧一个总能量"**完全区分不了频率**——440 Hz 和 880 Hz 在这个特征下一模一样。真正的 log-mel 会对每帧做 FFT，把能量分配到 80 个（large-v3 为 128 个）mel 频带上，440 Hz 和 880 Hz 会落在不同的频带。这正是讲义说"能量只是 mel 的教学替身"的局限，也是练习 2 要你用 `numpy.fft` 实现完整 log-mel 的原因。

### Q11 — 参考答案

(1) `padded[-2][0]` 也会变成 `1.0`——实际上所有 2502 个补齐帧的第 0 个元素都会变。`[pad_frame] * k` 生成的是**同一个列表对象的 k 个引用**（`padded[-1] is padded[-2]` 为 `True`）。本代码只读不写，所以没出问题，但只要后续有人对帧做原地操作（例如加窗 `frame[i] *= window[i]`），就会出现诡异的 bug。

(2) 修复：

```python
def pad_or_clip(frames, target, frame_size=FRAME_SIZE):
    if len(frames) >= target:
        return frames[:target]
    width = len(frames[0]) if frames else frame_size
    return frames + [[0.0] * width for _ in range(target - len(frames))]
```

用列表推导式为每个补齐帧创建**独立**的列表。

(3) 全零帧的能量是 0，`frame_energy` 返回 `log(0 + 1e-9) ≈ −20.72`，而有声音的帧是 `+5.298`，两者相差约 26 个单位。如果直接把这样的值送进网络，大量补齐帧会形成极端的数值，主导归一化统计。Whisper 官方的 log-mel 先 `clamp(min=1e-10)` 再取 `log10`，然后用 `max(log_spec, log_spec.max() − 8.0)` 把动态范围限制在最大值以下 8 个数量级，最后做 `(log_spec + 4) / 4` 的缩放——这正是为了处理静音/补齐段的极小值。

### Q12 — 参考回答要点

1. **预处理**：重采样到 16 kHz，补齐/截断到 30 秒 = 480,000 个采样点；STFT（窗长 400、帧移 160）→ mel 滤波器组 → log → 形状 `(80, 3000)`（large-v3 为 `(128, 3000)`）。
2. **卷积 stem**：两层 kernel 3 的 Conv1D + GELU，总下采样 2 倍 → `(1500, d_model)`，large 系列 `d_model = 1280`。
3. **Encoder**：加正弦位置编码，堆叠 Transformer 层（large 为 32 层）→ `(1500, 1280)`，每个 30 秒窗口只算一次。
4. **Decoder**：前缀 `<|startoftranscript|> <|lang|> <|task|> [<|notimestamps|>]`，自回归生成 BPE token，每层 masked self-attention + cross-attention（K/V 来自 encoder 的 1500 个时间步）+ FFN。
5. **解码**：beam search（宽度 5）+ log-prob 阈值；开启时间戳时以 0.02 秒为粒度输出时间戳 token。

- **Task token 的作用**：同一个模型、同一套权重，通过前缀切换转写/翻译、指定语种、开关时间戳——讲义称之为"语音版的指令微调"，与 T5 的任务前缀一脉相承。
- **常见误区**：讲义"Step 3/4"中写的是"24 层（large）"，但尺寸表中 large 是 32 层（24 层的是 medium），回答时以尺寸表为准。

### Q13 — 参考回答要点

| 维度 | Whisper | wav2vec 2.0 + CTC |
|------|---------|-------------------|
| 训练数据 | 68 万小时弱标注（互联网音频 + 现成字幕），有监督 | 大量无标注音频自监督预训练 + 少量干净标注数据微调 |
| 对齐 | 不需要显式对齐，decoder 通过 cross-attention 自己学 | CTC 通过 blank 符号在所有对齐路径上求和，不需要逐帧标注，但假设各帧输出条件独立 |
| 多任务 | 一个模型通过 task token 做转写、翻译、语种识别、时间戳 | 通常一个任务一个头，翻译需要另外的模型 |
| 推理 | 自回归，延迟随输出长度增长；beam search 更慢 | 非自回归，一次前向输出所有帧，延迟低、易流式 |
| 典型失效 | 在静音/噪声上可能"编造"文本（幻觉）、重复循环，需要 no-speech 阈值、log-prob 阈值、VAD | 缺少语言模型时拼写/语法错误多，常需外接 LM |

- **讲义观点**：wav2vec 2.0/HuBERT 质量高，但数据流程昂贵、领域迁移脆弱，多语种需要按语系分别建模；Whisper 用"规模 + 弱监督"换来了跨口音、跨噪声、跨语种的鲁棒性。
- **加分点**：指出 encoder-decoder 的 decoder 本身就是一个条件语言模型，这是它比纯 CTC 更流畅的原因，也是它会"幻觉"的原因。

### Q14 — 参考回答要点

- **模型与量化**：faster-whisper + large-v3-turbo 作为默认生产配置（配套 skill 拒绝在生产中直接用 OpenAI 参考实现）；GPU 用 float16，CPU 用 int8_float16；如果语种多、质量优先，可换 large-v3。
- **分块与 VAD**：VAD 先切掉静音（客服录音中等待、静音很多，省钱最明显）；按语音段切成 ≤ 30 秒的块，或采用 10 秒窗口、2 秒重叠；记录每块的全局时间偏移，合并时对重叠区间按时间戳去重（或保留置信度高的一侧）。
- **解码参数**：beam 5、温度回退（temperature fallback）、log-prob 阈值、no-speech 阈值，防止在静音上产生幻觉文本。
- **后处理**：WhisperX 强制对齐得到词级时间戳；pyannote 做说话人分离（多人对话必须做，skill 要求标出任何"单说话人假设"）；必要时做标点恢复和敏感信息脱敏。
- **评测**：人工标注一个分层抽样的测试集，按 WER 评估，并按口音、噪声、通话质量分组报告。
- **加分点**：估算吞吐与成本（批处理时用大 batch 提高 GPU 利用率）；监控幻觉率（静音段输出非空文本的比例）。

### Q15 — 参考回答要点

- **Whisper 的不利特性**：固定 30 秒窗口，不原生支持流式；自回归 decoder，输出越长延迟越高；beam search 进一步增加延迟。
- **方案**：VAD 检测说话结束（端点检测）后立即识别该段；模型选 large-v3-turbo（4 层 decoder，解码快约 8 倍）或边缘场景用 Moonshine；beam 宽度设为 1（skill：流式时 beam 为 1）；faster-whisper + 量化；音频短时（几秒）只处理实际长度。讲义提到 faster-whisper + VAD 可以达到约 150 ms 的延迟目标。
- **若要求 < 200 ms 的边说边出字**：讲义建议使用专门的流式 ASR，而不是 Whisper。
- **加分点**：区分"首字延迟"和"整句完成延迟"；讨论 VAD 端点阈值的取舍（太短会切断用户的停顿，太长会增加延迟）。

### Q16 — 参考回答要点

- **运行次数不同**：encoder 每个 30 秒窗口只运行**一次**，1500 个时间步并行计算，GPU 利用率高；decoder 每输出一个 token 就要把所有层**串行**跑一次，一段 30 秒语音通常要输出几十到上百个 token。
- **定量直觉**：设输出 T 个 token，decoder 层数为 L_d，则解码阶段的串行层数约为 `T × L_d`。L_d 从 32 降到 4，串行层数降为 1/8，这与讲义"8× faster decoding"一致；而 encoder 的成本只是一次性的固定开销。
- **质量代价小**：识别所需的声学信息主要由 encoder 提取，decoder 更像一个"以声学表示为条件的轻量语言模型"；讲义给出的回退是 WER 下降不到 1 个点。
- **加分点**：这与第 16 节 speculative decoding、以及"把参数放在并行部分、让串行部分尽量轻"的推理优化思路一致；参数量从 1550M 降到 809M，显存也随之下降（约 10 GB → 约 6 GB）。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 08 T5、BART——Encoder-Decoder 模型](../../08-t5-bart-encoder-decoder/docs/zh.md)：cross-attention、encoder 只跑一次、任务前缀。
- [阶段 07 · 09 Vision Transformers (ViT)](../../09-vision-transformers/docs/zh.md)：把非文本模态"切成 token 序列"，Whisper 被讲义称为"吃 mel 频谱的 ViT"。
- [阶段 06 · 01 音频基础](../../../06-speech-and-audio/01-audio-fundamentals/docs/zh.md)：采样率、波形。
- [阶段 06 · 02 频谱图与 Mel 特征](../../../06-speech-and-audio/02-spectrograms-mel-features/docs/zh.md)：STFT、mel 滤波器组、log-mel 的完整实现。
- [阶段 01 · 20 傅里叶变换](../../../01-math-foundations/20-fourier-transform/docs/zh.md)：FFT 是 log-mel 的数学基础。

### 本节被哪些后续内容用到
- [阶段 06 · 04 语音识别 ASR](../../../06-speech-and-audio/04-speech-recognition-asr/docs/zh.md)：CTC 与其他 ASR 方案的对比。
- [阶段 06 · 05 Whisper 架构与微调](../../../06-speech-and-audio/05-whisper-architecture-finetuning/docs/zh.md)：在自己的数据上微调 Whisper。
- [阶段 06 · 14 语音活动检测与轮次切换](../../../06-speech-and-audio/14-voice-activity-detection-turn-taking/docs/zh.md)：VAD 与端点检测。
- [阶段 06 · 12 语音助手流水线](../../../06-speech-and-audio/12-voice-assistant-pipeline/docs/zh.md)：ASR + LLM + TTS 的实时系统。
- [阶段 12 · 19 音频-语言模型：从 Whisper 到 AF3](../../../12-multimodal-ai/19-audio-language-whisper-to-af3/docs/zh.md)：Whisper encoder 作为多模态模型的音频前端。

### 延伸关键词
`STFT` · `mel filterbank` · `CTC` · `WER` · `temperature fallback` · `no_speech_threshold` · `WhisperX forced alignment` · `distil-whisper` · `pyannote diarization`
