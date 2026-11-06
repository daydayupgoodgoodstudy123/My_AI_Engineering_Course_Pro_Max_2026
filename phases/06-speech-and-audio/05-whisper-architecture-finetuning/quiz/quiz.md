# 测验 · Whisper——架构与 Fine-Tuning（Whisper — Architecture & Fine-Tuning）

> **阶段 06 · 语音与音频 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Whisper 是什么 | 30 秒窗口的 Transformer encoder-decoder，在 68 万小时多语种弱监督音频-文本对上训练，99 种语言、多任务 |
| 2 | 输入与帧预算 | 30 秒 log-mel、10 ms 帧移 → 3000 帧；encoder 前的卷积 stride 2 → 1500 个 encoder token；短于 30 秒补零，长于 30 秒必须切块 |
| 3 | 模型规模 | Large-v3：32 层、1280 维、20 头、1.55B 参数；decoder 是带因果自注意力 + cross-attention 的同尺寸 Transformer；BPE 词表 51,865 |
| 4 | Turbo | decoder 从 32 层砍到 4 层（809M），讲义称延迟约降 8×、WER 损失 <1%——因为自回归解码的成本主要在 decoder |
| 5 | 提示格式 | `<\|startoftranscript\|><\|语言\|><\|transcribe 或 translate\|><\|notimestamps\|>`：用特殊 token 切换语言、任务、是否输出时间戳 |
| 6 | 时间戳 token | 每 0.02 秒一个特殊 token，属于 51k 词表的一部分；0.02 秒 × 1500 个 encoder 位置 = 30 秒 |
| 7 | 预处理必须一致 | 必须用 `whisper.audio.log_mel_spectrogram`；换成 librosa 的 mel 会得到"近乎随机"的输出 |
| 8 | 推理防护 | `temperature=0.0`、`condition_on_previous_text=False`（防止幻觉级联）、`no_speech_threshold`、VAD 门控 |
| 9 | 长音频与运行时 | WhisperX = VAD + Whisper + wav2vec 2.0 强制对齐（词级时间戳）+ pyannote 说话人分离；faster-whisper（CTranslate2）约快 4× |
| 10 | 微调流程 | 10–100 小时领域数据；LoRA 加在 attention 的 `q_proj/v_proj` 等上；少于 10 小时冻结 encoder 只调 decoder；永远不要换 tokenizer 和提示格式 |

### 核心技能（能动手做到）

- [ ] 手写 Whisper 的 decoder 提示，能为"法语音频 → 英文文本"、"日语转写 + 时间戳"等任务拼出正确的特殊 token 序列
- [ ] 计算任意时长音频的 mel 帧数、encoder token 数，并解释为什么 30 秒是 3000 / 1500 而不是 2998
- [ ] 实现带重叠的切块调度 `chunk_schedule`，并说明重叠区的转写如何合并
- [ ] 用公式估算 Transformer encoder-decoder 的参数量，能发现并修正"Turbo decoder 漏算 cross-attention"的错误
- [ ] 正确估算 LoRA 可训练参数量（区分 encoder / decoder 层数、包含 cross-attention 的 `q_proj/v_proj`），验证讲义"约 3M / 809M"
- [ ] 为一个领域（医疗、低资源语言、长会议）设计 Whisper 的变体、运行时、微调方案、推理防护和评估计划

---

## 二、基础自测（选择题）

**Q1.** 一段 30 秒的音频送入 Whisper，encoder 最终输出多少个时间步（token）？

- A. 3000
- B. 1500
- C. 750
- D. 480,000

**Q2.** Whisper Large-v3-turbo 相比 Large-v3 推理快很多，主要是因为：

- A. encoder 从 32 层减到 4 层
- B. decoder 从 32 层减到 4 层，而自回归解码每生成一个 token 都要跑一遍 decoder
- C. 输入窗口从 30 秒缩短到 10 秒
- D. 词表从 51,865 缩小到 5,000

**Q3.** 想把一段**法语**录音直接翻译成**英文**文本、不需要时间戳，正确的 decoder 提示是：

- A. `<|startoftranscript|><|en|><|transcribe|><|notimestamps|>`
- B. `<|startoftranscript|><|fr|><|translate|><|notimestamps|>`
- C. `<|startoftranscript|><|en|><|translate|><|notimestamps|>`
- D. `<|startoftranscript|><|fr|><|transcribe|>`

**Q4.** 讲义建议长音频转写时设置 `condition_on_previous_text=False`，主要原因是：

- A. 这样可以启用词级时间戳
- B. 防止上一个窗口的幻觉文本作为条件"污染"后续窗口，造成级联的重复/幻觉
- C. 让模型自动识别语言
- D. 节省显存

**Q5.** 有人用 `librosa.feature.melspectrogram` 自己算特征喂给 Whisper，结果输出几乎随机。根本原因是：

- A. librosa 的 FFT 算法有 bug
- B. Whisper 依赖它自己的特征管线（mel 参数、取对数和缩放方式），特征分布不一致时模型无法工作
- C. librosa 只支持 22.05 kHz
- D. Whisper 只接受原始波形

**Q6.** 你只有 5 小时目标领域的标注音频，按讲义的流程，下列哪种微调方案最合适？

- A. 全量微调 encoder 和 decoder，并换成领域专用 tokenizer
- B. 冻结 encoder，只在 decoder 上做 LoRA，保持 Whisper 原有的 tokenizer 和提示格式
- C. 冻结 decoder，只微调 encoder
- D. 从零训练一个小 Whisper

**Q7.** Whisper 的时间戳 token 的分辨率是：

- A. 1 秒
- B. 0.1 秒
- C. 0.02 秒
- D. 10 ms

**Q8.** 关于 WhisperX，下列说法**错误**的是：

- A. 用 VAD 对音频进行门控和切分
- B. 用 wav2vec 2.0 做强制对齐得到词级时间戳
- C. 用 `pyannote.audio` 做说话人分离
- D. 用 CTC 解码器替换了 Whisper 的 attention decoder 来做转写

---

## 三、动手 / 代码题

**Q9.** 阅读 `chunk_schedule`：

```python
def chunk_schedule(total_seconds, chunk_s=30.0, stride_s=5.0):
    if total_seconds <= chunk_s:
        return [(0.0, total_seconds)]
    out = []
    start = 0.0
    step = chunk_s - stride_s
    while start < total_seconds:
        end = min(total_seconds, start + chunk_s)
        out.append((round(start, 2), round(end, 2)))
        if end == total_seconds:
            break
        start += step
    return out
```

(a) 预测 `chunk_schedule(30.0)`、`chunk_schedule(55.0)`、`chunk_schedule(65.0)` 的输出。
(b) 10 分钟（600 秒）的音频在默认参数下切成几块？如果 `stride_s=0.0` 呢？
(c) 这里的 `stride_s` 是"重叠"还是"步长"？相邻两块重叠的 5 秒，转写结果会重复出现，你会怎么合并？

**Q10.** 阅读 `encoder_frames`：

```python
def encoder_frames(seconds, sr=16000, hop=160):
    samples = int(seconds * sr)
    return 1 + (samples - 400) // hop
```

(a) `encoder_frames(30.0)` 返回多少？为什么和打印语句里说的"3000 frames"对不上？Whisper 实际是怎么得到正好 3000 帧的？
(b) `encoder_frames(0.01)` 返回什么？为什么？
(c) 函数名叫 `encoder_frames`，但返回的是 mel 帧数还是 encoder token 数？

**Q11.** Step 4 用下面的代码估算 Turbo 的参数量，打印出 `Turbo 629.3 78.7 70.2 778.2`，而讲义说 Turbo 是 809M：

```python
def transformer_params(n_layers, d_model, d_ff, n_heads, vocab):
    per_block = 4 * d_model * d_model + 2 * d_model * d_ff + 4 * d_model
    enc = n_layers * per_block
    dec = n_layers * (per_block + 4 * d_model * d_model + 4 * d_model)  # +cross-attn
    embed = vocab * d_model + 3000 * d_model
    return enc, dec, embed

# main() 中：
        if name == "Turbo":
            enc_big, _, embed_big = transformer_params(32, d, d_ff, heads, vocab)
            dec = enc  # 4 decoder layers match 4-layer mini
            enc = enc_big
            embed = embed_big
```

找出 Turbo 分支的 bug，给出修正后的 decoder 参数量和总量。

**Q12.** Step 5 的 LoRA 参数估算：

```python
def lora_params(n_layers, d_model, rank=16, modules=("q_proj", "v_proj")):
    per_module = 2 * d_model * rank
    per_block = len(modules) * per_module
    return n_layers * 2 * per_block  # encoder + decoder
```

它对 Turbo 打印 `0.655 M`，而讲义 Step 3 的注释说 `~3M trainable / 809M total`。指出这个函数的两处简化，写出 `lora_params_fixed(n_enc, n_dec, d_model, rank=16)`，算出 Turbo、Large-v3、Medium 的正确值。（提示：在 HF 的 Whisper 实现中，decoder 每层的自注意力和 cross-attention 都有名为 `q_proj`、`v_proj` 的线性层，PEFT 会按名字全部匹配。）

---

## 四、面试高频题

**Q13.**（基础必考）从一段音频文件到一行文字，完整描述 Whisper 的数据流和架构，包括每一步的张量形状。为什么它要固定 30 秒窗口？

**Q14.**（原理深挖）Turbo 为什么选择砍 decoder 而不是 encoder？从推理计算量的角度分析 encoder-decoder 模型的延迟构成，并说说这样做会损失什么。

**Q15.**（工程实践）要在生产环境转写大量 1 小时以上的播客，并输出词级时间戳和说话人。请设计推理管线，并说明如何防止幻觉。

**Q16.**（场景设计）医院希望用 Whisper 转写医生口述病历，现有 20 小时标注数据；另一个团队要支持一种 Whisper 表现很差的低资源语言，只有 4 小时数据。分别给出微调方案和评估方案。

**Q17.**（追问型）为什么微调 Whisper 时"永远不要换 tokenizer、不要换特征管线"？LoRA 为什么常加在 `q_proj` / `v_proj` 上？秩 r 怎么选？

---

## 五、参考答案与解析

### Q1 — 答案：B

30 秒 × 100 帧/秒 = 3000 个 mel 帧；encoder 前端的卷积 stride 为 2，下采样到 1500 个 encoder token（代码 Step 2 的打印语句也这样说明）。A 是 mel 帧数；C 是下采样两次的误解；D 是 16 kHz 下的样本数。

### Q2 — 答案：B

讲义："Turbo uses a 4-layer decoder (from 32)"。encoder 对每段音频只运行**一次**，decoder 则每生成一个 token 就要运行一次（自回归），一段话几十上百个 token，decoder 的累积成本远大于 encoder。砍 decoder 层数直接降低每步解码的开销。A 方向反了；C、D 不是 Turbo 的改动。

### Q3 — 答案：B

语言 token 表示**音频里说的是什么语言**（这里是法语 `<|fr|>`），任务 token `<|translate|>` 表示输出英文译文。A 是英文转写；C 把语言标签错设为英文，与音频不符；D 是法语转写（且会输出时间戳）。注意：讲义中"`<|en|>` — forces translation-vs-transcription behavior"的说法不准确——决定翻译还是转写的是任务 token，语言 token 描述的是源语言。

### Q4 — 答案：B

讲义 Pitfalls："One hallucination pollutes subsequent windows."长音频按窗口顺序转写时，如果把上一个窗口的输出作为下一个窗口的提示，一旦某个窗口出现幻觉或重复，它会被当作"上下文"继续放大。只有在确实需要跨窗口的流畅性时才开启，并配合防护（技能文件："拒绝在没有防护的多块任务中设为 True"）。

### Q5 — 答案：B

Whisper 训练时使用的是它自己的 log-mel 管线；librosa 默认的 mel 公式、归一化、幅度/功率、对数底数和后续缩放都不同，模型看到的是完全不同分布的输入。讲义："Using librosa's mels instead of Whisper's produces near-random output. Use `whisper.audio.log_mel_spectrogram`."
补充（以 openai/whisper 源码为准）：该函数对功率 mel 取 `log10`，把动态范围裁剪到"最大值 − 8"以内，再做 `(x + 4) / 4` 的缩放，**并不是**讲义所写的"用训练语料的 mean/std 做 `(log_mel − mean)/std`"；另外 large-v3 起输入改为 128 个 mel bin（此前的模型是 80）。这些细节恰恰说明了"必须用官方预处理"。

### Q6 — 答案：B

讲义流程第 4、5 条："Freeze the encoder if you have <10 hours. Only tune the decoder."、"Use Whisper's own tokenizer and prompt format; never swap tokenizers." 5 小时数据不足以更新 encoder 的声学表示，冻结它可以防止过拟合和灾难性遗忘；LoRA 进一步减少可训练参数。A 换 tokenizer 会让预训练的 embedding 与输出层全部失配；C、D 都不合理。

### Q7 — 答案：C

讲义 Key Terms："Every 0.02 s offset is a special token in the 51k vocab."这与 encoder 的分辨率一致：1500 个 encoder token 覆盖 30 秒，每个 0.02 秒。D 的 10 ms 是 mel 帧移，下采样后变成 20 ms。

### Q8 — 答案：D

WhisperX 仍然用 Whisper（通常是 faster-whisper 后端）转写，额外加上 VAD 切分、wav2vec 2.0 强制对齐（得到词级时间戳）和 pyannote 说话人分离。wav2vec 2.0 在这里是用来"对齐"的，不是用来替代 Whisper 转写的。

### Q9 — 参考答案

(a)

```text
chunk_schedule(30.0) -> [(0.0, 30.0)]
chunk_schedule(55.0) -> [(0.0, 30.0), (25.0, 55.0)]
chunk_schedule(65.0) -> [(0.0, 30.0), (25.0, 55.0), (50.0, 65.0)]
```

30 秒走提前返回分支；55 秒时第二块正好结束在 55，触发 `break`；65 秒时最后一块只有 15 秒（短于窗口，送进 Whisper 时会被补零到 30 秒）。

(b) 步长 `30 − 5 = 25` 秒，起点 0, 25, …, 575，共 **24 块**（Step 3 实测）。`stride_s=0.0` 时步长 30 秒，共 **20 块**，没有重叠。

(c) 在这段代码里 `stride_s` 实际是**相邻块的重叠量**，真正的步长是 `chunk_s − stride_s`。（HF `pipeline` 的 `stride_length_s` 指每块两侧用作上下文的长度，含义类似但不完全相同，使用前要看文档。）合并方法：
- 简单做法：每块只保留"中间部分"——丢掉每块开头和结尾各 `stride/2` 秒内的词（需要时间戳），拼接剩余部分；
- 更稳的做法：对相邻两块重叠区的词序列做最长公共子序列/编辑距离对齐，取置信度更高的一方；
- 生产中直接用 VAD 在静音处切分（WhisperX），从根本上避免切在词中间。

### Q10 — 参考答案

(a) `int(30 × 16000) = 480000`，`1 + (480000 − 400) // 160 = 1 + 2997 = 2998`。这个公式是"不补边"的分帧（第 02 节的公式）。Whisper 实际用 `torch.stft`（默认 `center=True`，两端反射补边），得到 `1 + 480000 // 160 = 3001` 帧，再丢掉最后一帧，正好 3000 帧，经 stride-2 卷积后为 1500。所以打印的 2998 与"3000 frames"差 2 帧，属于公式简化造成的不一致。

(b) 返回 `-1`。`0.01 × 16000 = 160` 个样本，`(160 − 400) // 160 = −240 // 160 = −2`（Python 的整除向负无穷取整），再加 1 得 −1。函数没有处理短于一帧的输入。修复：`max(0, ...)`，或采用 center 补边公式 `1 + samples // hop`。

(c) 返回的是 **mel 帧数**，而不是 encoder token 数（还需再除以 2）。名字有误导性，叫 `mel_frames` 更准确。

### Q11 — 参考答案

Bug：`dec = enc` 把 4 层 **encoder block** 的参数量当作 4 层 **decoder block**，漏掉了 decoder 每层的 cross-attention（`4·d² + 4·d`）。注释"4 decoder layers match 4-layer mini"恰好掩盖了这一点：`transformer_params(4, ...)` 返回的第二个值才是 4 层 decoder 的参数量，却被 `_` 丢弃了。

修正：

```python
        if name == "Turbo":
            enc_big, _, embed_big = transformer_params(32, d, d_ff, heads, vocab)
            # dec 保持 transformer_params(4, ...) 返回的第二个值（含 cross-attn），不要用 enc 覆盖
            enc = enc_big
            embed = embed_big
```

数值（`d = 1280, d_ff = 5120`）：
- encoder block：`4·1280² + 2·1280·5120 + 4·1280 = 19,665,920`
- decoder block：再加 `4·1280² + 4·1280` → `26,224,640`
- 4 层 decoder：`104.9M`（原代码算出 78.7M）
- 总量：`629.3 + 104.9 + 70.2 ≈ 804.4M`，与讲义的 809M 吻合得多（原来是 778.2M）。

剩余约 5M 的差距来自这个公式忽略的部分：encoder 前端两层卷积、各种 bias 等。另外 `3000 * d_model` 的"音频侧位置编码"也不准确：encoder 的位置编码对应 1500 个位置且是固定的正弦编码（不是可训练参数），decoder 的可学习位置编码是 448 个位置。作为数量级估算可以接受，但要知道它是近似。

### Q12 — 参考答案

两处简化：
1. **encoder 和 decoder 层数相同**：`n_layers * 2` 假设两边层数一样。对 Turbo 传入的是 `layers = 4`，于是 encoder 只算了 4 层，而 Turbo 的 encoder 实际有 32 层。
2. **漏掉 cross-attention**：decoder 每层除了自注意力，还有 cross-attention，二者都有 `q_proj`、`v_proj`；按名字匹配的 PEFT 会把它们都加上 LoRA。

```python
def lora_params_fixed(n_enc, n_dec, d_model, rank=16):
    per_module = 2 * d_model * rank             # A: d×r，B: r×d
    enc = n_enc * 2 * per_module                # 自注意力的 q_proj、v_proj
    dec = n_dec * 4 * per_module                # 自注意力 + cross-attention 的 q_proj、v_proj
    return enc + dec
```

结果（已计算验证）：

| 模型 | 原函数 | 修正后 |
|------|-------|-------|
| Turbo（32 enc / 4 dec，d=1280） | 0.655M | **3.277M** |
| Large-v3（32 / 32，d=1280） | 5.243M | **7.864M** |
| Medium（24 / 24，d=1024） | 3.146M | **4.719M** |

修正后 Turbo 约 3.3M，与讲义注释"~3M trainable / 809M total"一致，约占总参数的 0.4%。每个 LoRA 模块的参数是 `d×r + r×d = 2·d·r`，与第 01 阶段线性代数里"LoRA 参数量从 d² 降到 2dr"的结论相同。

### Q13 — 参考回答要点

| 步骤 | 操作 | 形状（单条 30 秒） |
|------|------|------------------|
| 读音频 | 重采样到 16 kHz 单声道 float32，补零/截断到 30 秒 | `(480000,)` |
| 特征 | Whisper 自己的 log-mel（v3 前 80 bin，v3 起 128 bin），10 ms 帧移 | `(n_mels, 3000)` |
| encoder 前端 | 两层 1D 卷积，第二层 stride 2 | `(1500, d)` |
| encoder | N 层 Transformer（Large-v3：32 层、d=1280、20 头）+ 位置编码 | `(1500, 1280)` |
| decoder | 提示 `SOT, 语言, 任务, [notimestamps]` 起步，因果自注意力 + cross-attention 到 encoder 输出，自回归生成 BPE token | 每步输出 51k 维 logits |
| 输出 | 遇到 `<\|endoftext\|>` 停止，去掉特殊 token 得到文本（可含 0.02 秒粒度的时间戳） | — |

- **为什么固定 30 秒**：训练数据按 30 秒切片，encoder 的位置编码长度固定为 1500；固定形状便于批处理和高效训练。代价是：短音频要补零（尾部静音可能引发幻觉），长音频必须切块，不能原生流式——这正是 WhisperX、Whisper-Streaming、faster-whisper 存在的原因。
- **多任务**：同一个模型通过提示中的特殊 token 切换语言识别、转写、翻译、时间戳。
- 加分点：68 万小时弱监督数据带来的鲁棒性，以及它带来的副作用（字幕式幻觉）。

### Q14 — 参考回答要点

- **延迟构成**：总延迟 ≈ encoder 一次前向 + 输出 token 数 × decoder 单步前向。encoder 处理 1500 个位置是并行的、只做一次；decoder 每步虽然只处理一个新 token（有 KV cache），但它是**串行**的，GPU 利用率低，且每步都要对 1500 个 encoder 位置做 cross-attention。一段 30 秒的语音通常有几十到上百个 token，decoder 的串行步数主导了延迟。
- **为什么砍 decoder**：encoder 负责"听"——声学表示的质量直接决定识别率，砍它损失很大；decoder 更多扮演条件语言模型的角色，4 层在 encoder 表示足够好时仍能工作。讲义：Turbo 延迟降约 8×、WER 损失 <1%。
- **损失**：decoder 变浅后，内部语言建模能力下降，对更依赖语言知识的任务（如翻译、长距离上下文、低资源语言）影响可能更大；上线前要在自己的任务上验证，而不是只看 LibriSpeech 的 WER。
- 加分点：与第 04 节对比——CTC 没有自回归 decoder，所以延迟最低；Turbo 是在 encoder-decoder 框架内向"浅 decoder"方向靠拢。

### Q15 — 参考回答要点

管线（讲义 Step 2 + Use It）：
1. **解码与标准化**：转成 16 kHz 单声道 float32（第 01 节）。
2. **VAD 门控与切分**：用 Silero 等 VAD 找出语音段，在静音处切成 ≤30 秒的片段，静音段根本不送入模型。
3. **批量转写**：WhisperX（faster-whisper/CTranslate2 后端）批量推理，`large-v3-turbo`，`temperature=0.0`、`condition_on_previous_text=False`。
4. **词级时间戳**：wav2vec 2.0 强制对齐（Whisper 自带的时间戳是段级的、粒度 0.02 秒，词级对齐用专门的对齐模型更准）。
5. **说话人分离**：pyannote，把说话人标签分配到词上。
6. **后处理**：文本归一化、过滤已知幻觉短语、检测重复 n-gram。

防幻觉：VAD 是第一道防线；`condition_on_previous_text=False` 防止级联；`no_speech_threshold` 识别无语音窗口；已知语言时强制 `language`，避免 LID 漂移；短片段不要补很长的静音。监控：在静音/噪声测试集上统计幻觉率（技能文件第 5 条）。

### Q16 — 参考回答要点

| 项 | 医疗口述（20 小时） | 低资源语言（4 小时） |
|----|-------------------|--------------------|
| 变体 | Medium 或 Turbo（讲义社区结果：Medium 在 20 小时医疗口述上 WER 12% → 4.5%） | Turbo 或 Medium（讲义：Turbo 在 4 小时冰岛语上 18% → 6%） |
| 方法 | LoRA（r=16、`q_proj/v_proj` 起步，可扩到 `k_proj`）或全量微调 decoder；20 小时可以考虑解冻 encoder 的上层 | 冻结 encoder（<10 小时），decoder 上 LoRA |
| 数据 | 切成 ≤30 秒、转写与音频对齐；术语表、药名统一写法 | 尽量多说话人；可用数据增强（加噪、变速） |
| 提示 | 保持原 tokenizer；强制 `language` + `transcribe` | 若语言在 Whisper 的 99 种之内，使用其语言 token |
| 防遗忘 | 混入少量通用数据；监控通用测试集 WER | 同左 |
| 评估 | 领域测试集 WER（归一化后）+ 医学术语准确率 + 静音幻觉率 | 说话人不相交的测试集 WER/CER；与零样本 Whisper 对比 |

- 训练细节：`Seq2SeqTrainer` 训练，评估时开启生成（`predict_with_generate`）来算 WER；每 1000 步存检查点（讲义）。
- 加分点：说明为什么冻结 encoder——数据少时 encoder 的声学表示最容易被破坏，decoder 侧学"领域词汇和写法"性价比最高。

### Q17 — 参考回答要点

- **不能换 tokenizer**：decoder 的输入 embedding 和输出层是按原词表训练的，换词表等于让模型从零学习"输出什么"；特殊 token（语言、任务、时间戳）的下标也会全部错位，多任务提示失效。技能文件："Flag any fine-tune that swaps Whisper's tokenizer or mel pipeline."
- **不能换特征管线**：encoder 的第一层卷积只认识训练时的特征分布（mel 数、对数与缩放方式），换管线等于换了一种"语言"，讲义说会得到近乎随机的输出。
- **为什么 q/v**：LoRA 原论文的经验是在 attention 的 query 和 value 投影上加低秩更新性价比最高；讲义 Step 3 也是 `target_modules=["q_proj", "v_proj"]`，讲义流程第 3 条还提到 `k_proj`。数据多、域差异大时可扩展到 `k_proj`、`out_proj` 和 MLP。
- **r 怎么选**：讲义用 r=16、`lora_alpha=32`。数据少、领域差异小 → r 小（8–16）；差异大、数据多 → r 可加大到 32–64；用验证集 WER 做消融。参数量 = 每个模块 `2·d·r`，Turbo 上 r=16 约 3.3M。
- **常见误区**：只看训练 loss 不看 WER；不做文本归一化；忘记检查微调后在静音上的幻觉率。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 04 语音识别 (ASR)](../../04-speech-recognition-asr/docs/zh.md)：attention encoder-decoder 范式、WER、VAD 与静音幻觉。
- [阶段 06 · 02 频谱图、Mel 刻度与音频 Features](../../02-spectrograms-mel-features/docs/zh.md)：log-mel 管线，以及为什么特征必须与训练一致。
- [阶段 07 · 05 完整的 Transformer](../../../07-transformers-deep-dive/05-full-transformer/docs/zh.md)：encoder-decoder、cross-attention、因果掩码。
- [阶段 07 · 08 T5 / BART 编码器-解码器](../../../07-transformers-deep-dive/08-t5-bart-encoder-decoder/docs/zh.md)：同类架构在文本上的应用。

### 本节被哪些后续内容用到
- [阶段 07 · 10 音频 Transformer 与 Whisper](../../../07-transformers-deep-dive/10-audio-transformers-whisper/docs/zh.md)：从 Transformer 内部机制再看 Whisper。
- [阶段 07 · 12 KV Cache 与 Flash Attention](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：理解 decoder 自回归延迟的关键优化。
- [阶段 11 · 08 LoRA 微调](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：LoRA 的原理与工程细节。
- [阶段 06 · 10 音频语言模型](../../10-audio-language-models/docs/zh.md)：Whisper encoder 常被用作音频 LLM 的"耳朵"。
- [阶段 06 · 12 构建语音助手管道](../../12-voice-assistant-pipeline/docs/zh.md)：把 Whisper 放进端到端语音助手。
- [阶段 12 · 19 从 Whisper 到 AF3 的音频-语言模型](../../../12-multimodal-ai/19-audio-language-whisper-to-af3/docs/zh.md)：Whisper 在多模态模型中的角色。

### 延伸关键词
`faster-whisper / CTranslate2` · `WhisperX` · `Whisper-Streaming` · `distil-whisper` · `温度回退 (temperature fallback)` · `compression ratio threshold` · `DTW 词级时间戳` · `灾难性遗忘` · `PEFT target_modules` · `Moonshine`
