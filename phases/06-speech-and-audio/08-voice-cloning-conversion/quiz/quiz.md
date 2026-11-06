# 测验 · 语音克隆和语音转换（Voice Cloning & Voice Conversion）

> **阶段 06 · 语音与音频 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 克隆 vs 转换 | Voice cloning：文本 + 5 秒参考音 → 目标音色读出文本；voice conversion：A 说 X 的音频 + B 的参考音 → B 说 X |
| 2 | 共同的分解思想 | 把波形分解为 (content, speaker, prosody)，取一方的内容、另一方的说话人，再重组 |
| 3 | 零样本克隆 | 在数千说话人上预训练；speaker encoder 把参考音映射为 speaker embedding，TTS decoder 以 embedding + 文本为条件（F5-TTS、YourTTS、XTTS v2、OpenVoice v2） |
| 4 | 少样本微调 | 录 5–30 分钟目标声音，LoRA 微调约 1 小时，质量从"还行"到"难以分辨" |
| 5 | VC 之 recognition-synthesis | 先用类 ASR 模型提取内容表示（如 PPG，音素后验图），再用目标说话人重合成；对语言和口音鲁棒（KNN-VC、Diff-HierVC） |
| 6 | VC 之 disentanglement | 自编码器在瓶颈处分离内容/说话人/韵律，推理时替换说话人 embedding；更快但质量较低（AutoVC） |
| 7 | KNN-VC | 用 WavLM 提取源音频与目标池的逐帧特征，把每个源帧替换为目标池中的最近邻；非参数，约 1 分钟目标语音即可 |
| 8 | 神经编解码器克隆 | VALL-E / VALL-E 2 等把音频当作 SoundStream / EnCodec 的离散 token，在其上训练大模型 |
| 9 | 伦理三件套 | 水印（PerTh、SilentCipher，约 16–32 bit 不可闻 ID）、同意门槛（可验证的同意记录 + 防篡改日志）、检测（AASIST、RawNet2、Wav2Vec2-AASIST） |
| 10 | 评测与坑 | SECS 衡量音色相似度（讲义：>0.70 多数听众难以分辨），WER/CER 衡量可懂度；参考文本不一致、混响、情绪不匹配、跨语言口音泄漏 |

### 核心技能（能动手做到）

- [ ] 能用 `main.py` 的玩具模型说清"内容向量 + 说话人向量 → 合成 → 用余弦探针分别还原说话人和内容"的完整流程
- [ ] 能解释为什么玩具模型里说话人余弦只有约 0.46、内容余弦却有 0.9 以上，并通过调整 `mix` 让二者平衡
- [ ] 能指出玩具 VC（闭集检索内容）与真实 VC（连续内容表示）的差别
- [ ] 能解释非盲水印与盲水印的区别，并写出一个基于扩频（伪随机 ±1 码 + 相关检测）的盲检测水印
- [ ] 能为一个克隆服务设计同意记录、水印载荷、检测与审计链路，并指出用 `assert` 做安全检查的问题
- [ ] 能根据场景（5 秒零样本、改写已有语音、跨语言、深伪检测）从讲义选型表中挑出模型

---

## 二、基础自测（选择题）

**Q1.** 下列哪个任务属于 voice conversion（语音转换）而不是 voice cloning（语音克隆）？

- A. 输入一段文字和某人 5 秒的录音，输出该人朗读这段文字的音频
- B. 输入一段我读的有声书，再给出配音演员 1 分钟的录音，输出配音演员"读"这段内容的音频
- C. 用某人 30 分钟录音 LoRA 微调一个 TTS，再输入文字合成
- D. 用 VALL-E 根据文本和 3 秒提示音生成语音

**Q2.** recognition-synthesis 类 VC 方法用 PPG（音素后验图）作为内容表示，主要好处是：

- A. PPG 中保留了完整的说话人音色，便于还原
- B. PPG 是逐帧的音素后验概率，基本不含说话人信息，因此对语言和口音更鲁棒
- C. PPG 可以直接当作波形播放
- D. PPG 让模型不再需要目标说话人的任何音频

**Q3.** 关于 KNN-VC，下列说法正确的是：

- A. 需要为每个目标说话人训练一个专用的神经网络
- B. 用 WavLM 提取逐帧特征，把每个源帧替换为目标语音池里最相近的帧，是非参数方法
- C. 在自编码器的瓶颈层替换说话人 embedding
- D. 它在 EnCodec 离散 token 上训练自回归模型

**Q4.** 用 F5-TTS 克隆时输出的音频开头吞字、节奏错乱。检查发现 `ref_text` 少写了参考音频里的一个单词。最可能的原因是：

- A. 参考音频太短，至少需要 30 分钟
- B. 参考文本必须与参考音频完全一致（包括标点），否则对齐被破坏
- C. F5-TTS 不支持英文
- D. 没有加水印导致模型拒绝工作

**Q5.** 以下哪段参考音频最适合做零样本克隆？

- A. 在空旷大厅里用手机远距离录的 5 秒讲话
- B. 带背景音乐的 5 秒播客片段
- C. 近距离麦克风、无混响的 6 秒平静朗读，情绪与目标用途一致
- D. 情绪非常兴奋的 5 秒欢呼，用于合成新闻播报

**Q6.** 与 recognition-synthesis 相比，AutoVC 这类 disentanglement（解耦）方法的特点是：

- A. 通过自编码器瓶颈在潜空间分离内容、说话人和韵律，推理时替换说话人 embedding；更快但质量较低
- B. 必须先运行 ASR 得到文字
- C. 不需要任何训练
- D. 质量总是高于 KNN-VC

**Q7.** 关于 SECS（Speaker Embedding Cosine Similarity），下列说法正确的是：

- A. 它衡量合成语音的可懂度
- B. 它是目标说话人 embedding 与克隆输出 embedding 的余弦相似度；讲义认为 >0.70 时多数听众难以分辨
- C. 越接近 0 说明克隆越成功
- D. 它需要人工打分

---

## 三、动手 / 代码题

**Q8.** `main.py` 中合成和探针的核心代码如下。运行结果显示 Step 1 的说话人探针余弦只有 `0.437`，内容探针却有 `0.936`。请解释原因（提示：分别估算两种向量的模长），并说明把 `mix` 调到多少附近两者大致平衡。

```python
def content_vector(text, dim=64):
    h = hashlib.sha256(text.encode()).digest()
    expanded = (h * ((dim + len(h) - 1) // len(h)))[:dim]
    return [b / 255.0 - 0.5 for b in expanded]

def speaker_vector(seed, dim=64):
    rng = random.Random(seed)
    v = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in v)) or 1e-12
    return [x / norm for x in v]

def fake_tts(content, speaker, mix=0.5):
    return [(1 - mix) * c + mix * s for c, s in zip(content, speaker)]
```

**Q9.** Step 3（语音转换）打印的 `post-conversion speaker: alice (cos=0.462)` 与 Step 2（零样本克隆）的数值完全相同。为什么？这一步相对于真实的 voice conversion 做了什么"作弊"式的简化？

```python
    wav_bob_orig = fake_tts(content_remind, bob, mix=0.5)
    matched_text, _ = extract_content(wav_bob_orig, contents)
    content_est = contents[matched_text]
    wav_converted = fake_tts(content_est, alice, mix=0.5)
```

**Q10.** 代码中的水印与检测如下。(1) 为什么 Step 5 的位准确率一定是 100%？(2) 如果检测端拿不到原始音频（真实场景几乎都是这样），这个方案还能用吗？(3) 写一个"盲检测"的扩频水印：嵌入时用密钥生成伪随机 ±1 码，检测时只用带水印的音频和密钥做相关。

```python
def watermark(wave, payload_bits, strength=0.003):
    n_bits = len(payload_bits)
    out = list(wave)
    for i in range(len(out)):
        bit_idx = i % n_bits
        sign = 1 if payload_bits[bit_idx] else -1
        out[i] += sign * strength
    return out

def detect_watermark(wave_original, wave_wm, n_bits=32):
    diff = [a - b for a, b in zip(wave_wm, wave_original)]
    bits = []
    for b in range(n_bits):
        chunk = diff[b::n_bits]
        avg = sum(chunk) / max(1, len(chunk))
        bits.append(1 if avg > 0 else 0)
    return bits
```

---

## 四、面试高频题

**Q11.**（基础必考）解释 voice cloning 和 voice conversion 的区别。二者背后共同的"分解—重组"思想是什么？零样本克隆的典型架构是什么？

**Q12.**（原理深挖）比较 voice conversion 的两大流派：recognition-synthesis（PPG / KNN-VC）与 disentanglement（AutoVC）。各自如何保证"内容不变、音色改变"？优缺点是什么？

**Q13.**（工程实践）你要上线一个"上传 5 秒录音即可克隆声音"的 API。请设计同意、水印、检测、风控与审计方案。讲义 Step 5 的示例代码用 `assert` 做同意校验、用 `hash_speaker(ref_audio)` 比对说话人，这两点在生产中有什么问题？

**Q14.**（场景设计）为一位 ALS（渐冻症）患者做"声音银行"：在他还能说话时录音，失声后用 TTS 替他说话。你选零样本、少样本微调还是 VC？参考音频怎么录？如何评估效果？

**Q15.**（追问型）把一个英语母语者的声音克隆后让模型说法语，听起来仍有浓重英语口音，为什么？怎么缓解？另外，如果克隆模型和评测 SECS 用的是同一类 speaker encoder，SECS 的数字可信吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

B 的输入是**一段已有语音**（我读的内容）+ 目标说话人参考，输出保留内容、替换音色——这是 voice conversion。A、D 是"文本 + 参考音频"的零样本克隆，C 是少样本微调后的克隆，它们的输入都是文本（TTS 侧）。

### Q2 — 答案：B

PPG 是 ASR 类模型逐帧输出的音素后验，描述"这一帧在发什么音"，与"谁在发音"基本无关，所以讲义说它"robust to language and accent"，Key Terms 称其为 language-agnostic content representation。A 恰好相反；C 错，PPG 是概率特征不是波形；D 错，重合成仍需目标说话人 embedding。

### Q3 — 答案：B

讲义：KNN-VC 运行 WavLM 为源音频和目标池提取逐帧 embedding，再把每个源帧替换为池中的最近邻，"Non-parametric, works with a minute of target speech"。A 错，它不需要为目标说话人训练；C 是 AutoVC 的做法；D 是 VALL-E 一类神经编解码器 TTS。

### Q4 — 答案：B

讲义在 Build It 和 Pitfalls 中两次强调：F5-TTS 一类模型要求参考文本与参考音频**完全一致（包括标点）**，不一致会破坏对齐。讲义说 5 秒参考就够，A 错；C、D 都是编造的原因。

### Q5 — 答案：C

讲义 Pitfalls："Reverberant reference. Echo kills the clone. Record dry, close-mic."（A 错）以及"Emotional mismatch"（D 错：兴奋的参考会让所有输出都兴奋）。B 的背景音乐会污染 speaker embedding（skill 文件明确要求拒绝 music-bed 参考，并要求 SNR ≥ 20 dB）。

### Q6 — 答案：A

讲义原文："Train an autoencoder that separates content, speaker, and prosody in latent space at the bottleneck. Swap speaker embedding at inference. Lower quality but faster." B 描述的是 recognition-synthesis 的思路（且 PPG 并不需要转成文字）；C 错，自编码器需要训练；D 与讲义"Lower quality"矛盾。

### Q7 — 答案：B

SECS 是用说话人编码器分别提取参考音频和克隆输出的 embedding，再算余弦。它衡量音色相似度而非可懂度（可懂度用 WER/CER，A 错），越接近 1 越像（C 错），是自动指标（D 错）。

### Q8 — 参考答案

- `content_vector` 的每个分量是 `b/255 − 0.5`，近似服从 [−0.5, 0.5] 上的均匀分布，方差约 1/12，64 维的模长约 `√(64/12) ≈ 2.3`（实测两个内容向量的模长为 2.56 和 2.19）。
- `speaker_vector` 被显式归一化，模长为 1。
- `mix=0.5` 时两者权重相同，但内容向量的模长是说话人向量的 2 倍以上，混合结果的方向主要由内容决定，所以与内容的余弦高（0.936），与说话人的余弦低（0.437）。探针仍然能选对 alice，只是因为三个随机说话人向量彼此近似正交（实测 `cos(alice, bob) ≈ −0.04`）。
- 实测不同 `mix` 下 Step 2 克隆结果的两种余弦：

| mix | 与 alice 的余弦 | 与内容的余弦 |
|-----|----------------|-------------|
| 0.5 | 0.462 | 0.914 |
| 0.7 | 0.749 | 0.708 |
| 0.8 | 0.884 | 0.522 |

`mix ≈ 0.7` 附近两者大致平衡。更好的修复是先把内容向量也归一化为单位长度，再用 `mix=0.5`。启示：真实系统中说话人 embedding 与内容表示的尺度不同，条件注入时常需要归一化或学习的投影层。

### Q9 — 参考答案

- `extract_content` 只是在一个**已知文本的字典**里找余弦最高的那一项，返回的 `content_est` 就是 `contents["please remember to water plants"]` 本身，与 Step 2 用的 `content_remind` 是同一个列表。于是 `wav_converted = fake_tts(content_remind, alice, 0.5)` 与 Step 2 的 `wav_cloned` 逐元素相同（已验证 `==` 为 `True`），余弦自然一模一样。
- "作弊"之处：这是**闭集检索**——系统事先知道所有可能说的话。真实 VC 面对任意语音，内容表示必须是从音频中**连续提取**的（PPG、WavLM 逐帧特征），并且会混入残留的说话人信息、丢失部分韵律；转换质量就取决于这一步分得有多干净。
- 另外这里的"转换"实际上退化成了"识别出文字 → 再用 alice 做 TTS"，丢掉了源语音的韵律（语速、停顿、语调）。真实的 recognition-synthesis VC 是逐帧重合成，会保留源语音的时间结构。

### Q10 — 参考答案

(1) 检测时直接计算 `wave_wm − wave_original`，差值恰好就是嵌入的 `±0.003`，没有任何噪声或处理，按位取均值的符号必然正确。这只证明了"编码/解码的约定成立"，docstring 也是这么说的。

(2) 不能。这是**非盲（non-blind）**检测：需要原始未加水印的音频。实测把原始音频换成全零（等于不知道原始音频），位准确率降到 46.9%，与瞎猜相当；即使有原始音频，再叠加 σ=0.01 的高斯噪声，准确率也降到 71.9%——因为 64 个采样点分给 32 位，每位只有 2 个点，信噪比太低。真实系统（SilentCipher、AudioSeal 等）都是盲检测，并且要扛住 MP3 重编码。

(3) 扩频水印参考实现（已在 1 秒 16 kHz 的合成音频上验证：加 σ=0.01 噪声后 32 位全部正确；换成错误密钥约 59%，接近随机）：

```python
import random

def ss_embed(wave, bits, key=1234, strength=0.01):
    rng = random.Random(key)
    n = len(bits)
    out = list(wave)
    for i in range(len(out)):
        chip = 1 if rng.random() < 0.5 else -1   # 伪随机 ±1 扩频码
        sign = 1 if bits[i % n] else -1
        out[i] += strength * sign * chip
    return out

def ss_detect(wave_wm, n_bits=32, key=1234):
    rng = random.Random(key)
    corr = [0.0] * n_bits
    for i, x in enumerate(wave_wm):
        chip = 1 if rng.random() < 0.5 else -1
        corr[i % n_bits] += x * chip               # 与同一扩频码做相关
    return [1 if c > 0 else 0 for c in corr]
```

原理：宿主音频与伪随机码不相关，相关运算后宿主信号近似抵消为零均值噪声，而水印分量按 `strength × 每位采样点数` 线性累积。音频越长、每位分到的采样点越多，检测越可靠；没有密钥就无法检测，也难以伪造。真实系统还会在感知域（频域掩蔽）嵌入，保证不可闻并抗压缩。

### Q11 — 参考回答要点

- **定义**：cloning 是 TTS 侧（文本 + 参考音 → 目标音色的语音）；conversion 是语音侧（源语音 + 目标参考 → 内容不变、音色替换）。
- **共同思想**：把语音分解为 content（说了什么）、speaker（谁说的）、prosody（怎么说的），从一个来源取内容、另一个来源取说话人，再重组。
- **零样本克隆架构**：在数千说话人上预训练；speaker encoder 把 5 秒参考映射为 speaker embedding；TTS decoder 以文本 + embedding 为条件生成 mel 或 codec token，再经 vocoder 输出。代表：F5-TTS、YourTTS、XTTS v2、OpenVoice v2。
- **质量阶梯**：零样本（5 秒）→ 少样本 LoRA 微调（5–30 分钟录音，约 1 小时训练，讲义说质量从"okay"到"indistinguishable"）。
- **加分点**：提到神经编解码器路线（VALL-E 系列），以及 2026 年合规要求（EU AI Act 2026 年 8 月起执行）让水印与同意成为架构的一部分而不是附加项（讲义标题："The ethics bit, not a bolt-on"）。

### Q12 — 参考回答要点

- **Recognition-synthesis**：用 ASR 类模型提取逐帧内容表示（PPG 或 WavLM 特征），这些表示本身就不太含说话人信息；再用目标说话人重合成。KNN-VC 更进一步：直接在目标说话人的 WavLM 特征池里为每个源帧找最近邻，用"目标说话人自己发过的相似音"替换，因此音色天然来自目标。优点：对语言、口音鲁棒，KNN-VC 无需训练、约 1 分钟目标语音即可。缺点：依赖内容提取器质量；目标池太小时覆盖不到所有音素。
- **Disentanglement（AutoVC）**：训练自编码器，靠瓶颈尺寸限制信息量，迫使内容、说话人、韵律分到不同的潜变量；推理时替换说话人 embedding。优点：单次前向，快。缺点：解耦不彻底时会有音色泄漏或内容损失，讲义评价"Lower quality"。
- **常见误区**：认为瓶颈"自动"解耦——瓶颈太大会泄漏说话人信息，太小会丢内容，需要仔细调。
- **加分点**：指出两派可以结合（自监督特征 + 解码器），以及神经编解码器路线把 VC 也变成 token 生成问题。

### Q13 — 参考回答要点

- **同意**：每次克隆都必须绑定一条可验证的同意记录（谁、何时、授权什么用途、范围、撤销方式），签名后存入防篡改日志（append-only + 哈希链等）；skill 文件给出的模板是 name + date + purpose + scope + revocation procedure。
- **说话人一致性校验**：上传的参考音必须与同意人是同一人。讲义示例用 `hash_speaker(ref_audio)` 比对 `speaker_id`——如果是对音频字节做哈希，同一人换一段录音哈希就不同，无法做"是不是同一个人"的判断。应使用说话人验证（第 06 节）：提取 embedding，与同意时录制的声纹比对余弦并设阈值，同时配合活体检测（随机朗读一句话）防止拿别人的录音冒充。
- **`assert` 的问题**：Python 以 `-O` 运行时会移除所有 `assert`，安全检查会被静默跳过；失败时抛的 `AssertionError` 也不利于给调用方返回明确的错误码。应使用显式的 `if not ...: raise PermissionError(...)`。
- **水印**：每个输出都嵌入不可闻水印，载荷是**短 ID**（同意记录 ID / 生成 ID），通过 ID 到日志里查完整信息。讲义 Step 4 的载荷 `b"consent_id:abc123;ts:1745353200"` 有 31 字节 = 248 bit，远超同一段说的约 32 bit 容量，必须改为短 ID。发布前在 CI 中检测水印是否存在（skill 文件要求）。
- **检测与风控**：部署 AASIST 类深伪检测；拒绝名人、政客、未成年人（skill 文件）；按用户限流、审计每次生成、保留紧急关停开关。
- **加分点**：主动提到合规时间点（讲义：EU AI Act 2026 年 8 月起执行）并说明水印需要抗 MP3 重编码、流媒体传输等处理。

### Q14 — 参考回答要点

- **路线选择**：患者本人就是声音所有者，同意天然成立；skill 文件的示例给出的是零样本方案（OpenVoice V2，MIT 许可，约 6 秒参考），并用多段参考的中心向量提高稳定性。如果患者状态允许录制 5–30 分钟，少样本 LoRA 微调能把质量从"还行"提升到"难以分辨"，更适合长期日常使用。
- **参考音频**：安静、无混响、近距离麦克风；平静、日常的语气（避免情绪不匹配）；保存原始录音和逐字转写（F5-TTS 类模型要求文本完全一致）；尽早录制，因为病程中声音会变化。
- **评估**：SECS（与患者原声的相似度，>0.70 为讲义给出的经验阈值）；Whisper CER（可懂度）；患者及家属的主观 MOS / A/B 偏好。
- **安全**：仍然要加水印、绑定设备/账号、不对外暴露 API（skill 示例的做法）。
- **常见误区**：只录一段 5 秒就结束——多段、多句式的参考能显著提升稳定性。

### Q15 — 参考回答要点

- **口音泄漏原因**：零样本模型从参考音中提取的 embedding 不只包含音色，还混入了口音、发音习惯等信息；而单语种训练的模型没有学过"同一音色说另一种语言"的样本，无法把口音和音色分开。讲义 Pitfalls："Language leakage ... use cross-lingual models (XTTS, VALL-E X)"。
- **缓解**：使用跨语言模型（XTTS v2、VALL-E X）；如果有目标语言的少量录音则做微调；对用户明确说明口音迁移的局限（skill 文件要求跨语言克隆必须标注 accent-transfer gap）。
- **SECS 可信度**：SECS 本质上是"某个 speaker encoder 认为两者有多像"。如果克隆模型在训练或推理中用到了同类 encoder 的 embedding 作为条件，输出可能恰好在这个 encoder 的特征空间里被拉近，SECS 偏乐观。稳妥做法：用与生成端不同的、独立训练的说话人验证模型评测，并辅以人工 A/B 听测和深伪检测器的结果。
- **加分点**：指出讲义表格中的 SECS 数字来自特定评测设置，不同 encoder 之间的数值不能直接比较。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 06 说话人识别与验证](../../06-speaker-recognition-verification/docs/zh.md)：speaker embedding（如 ECAPA-TDNN）与余弦打分，是零样本克隆和 SECS 的基础。
- [阶段 06 · 07 文本转语音 (TTS)](../../07-text-to-speech/docs/zh.md)：克隆就是在 TTS 上加一个说话人条件；F5-TTS 在两节都出现。
- [阶段 01 · 14 范数与距离](../../../01-math-foundations/14-norms-and-distances/docs/zh.md)：余弦相似度与向量模长对结果的影响（Q8）。

### 本节被哪些后续内容用到
- [阶段 06 · 13 神经音频编解码器](../../13-neural-audio-codecs/docs/zh.md)：VALL-E 一类克隆所依赖的离散音频 token。
- [阶段 06 · 16 语音反欺骗和音频水印](../../16-anti-spoofing-audio-watermarking/docs/zh.md)：AASIST 检测器与 AudioSeal 等水印的系统讲解。
- [阶段 06 · 17 音频 Evaluation](../../17-audio-evaluation-metrics/docs/zh.md)：SECS、WER、MOS 等指标的完整体系。
- [阶段 11 · 08 LoRA 微调](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：少样本克隆中的 LoRA 微调方法。
- [阶段 18 · 23 水印：SynthID、Stable Signature、C2PA](../../../18-ethics-safety-alignment/23-watermarking-synthid-stable-signature-c2pa/docs/zh.md)：跨模态的 AI 内容水印与溯源标准。
- [阶段 18 · 24 监管框架](../../../18-ethics-safety-alignment/24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：EU AI Act 等对合成内容的透明度要求。

### 延伸关键词
`speaker encoder` · `PPG (phonetic posteriorgram)` · `WavLM` · `kNN-VC` · `AutoVC 瓶颈` · `VALL-E X` · `OpenVoice tone color converter` · `spread-spectrum 水印` · `AudioSeal` · `AASIST` · `liveness detection`
