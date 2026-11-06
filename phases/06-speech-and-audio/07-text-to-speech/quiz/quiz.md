# 测验 · 文本转语音 (TTS) — 从 Tacotron 到 F5 和 Kokoro（Text-to-Speech (TTS) — From Tacotron to F5 and Kokoro）

> **阶段 06 · 语音与音频 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | TTS 三段式 | 文本前端（text → phonemes/tokens）→ 声学模型（→ mel 频谱）→ vocoder（mel → 波形）；2026 年端到端模型把边界模糊了，但排查问题时仍按三段想 |
| 2 | 文本前端 | 先做文本归一化（数字、日期、缩写、邮箱），再做 G2P（grapheme-to-phoneme，字形到音素），必要时预测韵律；音素是"通用桥梁" |
| 3 | Tacotron 2（2017） | 自回归 seq2seq：字符 embedding → BiLSTM encoder → location-sensitive attention → LSTM decoder 逐帧吐 mel；慢，长文本对齐不稳 |
| 4 | FastSpeech 2（2020） | 非自回归：duration predictor 给每个音素预测整数帧数，一次前向生成全部帧，比 Tacotron 快约 10×，代价是部分自然度 |
| 5 | VITS（2021） | encoder + 基于 flow 的时长模型 + HiFi-GAN vocoder 用变分推断端到端联合训练；2022–2024 开源主力，衍生 YourTTS、XTTS v2 |
| 6 | F5-TTS 与 Kokoro（2024） | F5：flow matching 上的 diffusion transformer，335M，5 秒参考音频零样本克隆；Kokoro：82M、CPU 可跑、Apache-2.0 的英文实时 TTS |
| 7 | Vocoder 演进 | WaveNet（只能离线）→ WaveRNN → HiFi-GAN（约 100× 实时）→ BigVGAN（跨说话人/语言泛化）→ SNAC/DAC 等神经编解码器（离散 token） |
| 8 | 评测指标 | MOS/CMOS 人工打分；UTMOS/DNSMOS 无参考神经 MOS 预测；用 Whisper 转写算 CER 衡量可懂度；SECS 衡量克隆音色相似度 |
| 9 | 帧—时间—采样点换算 | 时长 = Σ帧数 × hop；hop 12.5 ms、24 kHz 时每帧 300 个采样点；HiFi-GAN 的上采样倍率乘积必须等于 hop 的采样点数 |
| 10 | 工程坑 | 没有 normalizer、OOV 专有名词、mel 尺度不匹配导致超出 ±1.0、采样率不匹配（Kokoro 24 kHz vs 下游 16 kHz） |

### 核心技能（能动手做到）

- [ ] 能读懂并复现 `main.py` 的三步：最长匹配 G2P → 每音素帧数 → mel 帧时间表，并手算总时长、采样点数和 mel 内存占用
- [ ] 能举出至少 3 个让玩具 G2P 出错的输入（数字、缩写、单词内部的 "the"），并说明真实系统用什么组件解决
- [ ] 能为一个文本归一化器写出最小实现：数字转英文单词、常见缩写展开，并放在 phonemizer 之前
- [ ] 能根据场景（CPU 实时、5 秒克隆、小语种、情感标签）从讲义的 2026 选型表中给出模型并说出理由
- [ ] 能设计一套上线前的 TTS 评测：UTMOS + Whisper CER + SECS（克隆时）+ 覆盖数字/同形异音词/专有名词/长句的测试集
- [ ] 能解释 HiFi-GAN 的上采样倍率（如 `[8, 8, 2, 2]` → 256×）与 hop length 的对应关系，以及 vocoder 的三种训练损失

---

## 二、基础自测（选择题）

**Q1.** FastSpeech 2 比 Tacotron 2 推理快一个数量级，最根本的原因是：

- A. 它把 LSTM 换成了更小的 GRU
- B. 它是非自回归的：先由 duration predictor 预测每个音素占多少帧，再一次性并行生成全部 mel 帧
- C. 它去掉了 vocoder，直接输出波形
- D. 它只支持英文，所以词表更小

**Q2.** 某 TTS 系统 hop 为 12.5 ms、输出采样率 24 kHz，声学模型一共输出 160 个 mel 帧。对应的音频时长和采样点数是：

- A. 2.0 s，48000 个采样点
- B. 2.0 s，32000 个采样点
- C. 1.6 s，38400 个采样点
- D. 2.0 s，40960 个采样点

**Q3.** 你想在没有人工打分的情况下，自动衡量 TTS 输出"有没有把字念对"（可懂度）。讲义推荐的代理指标是：

- A. UTMOS
- B. SECS
- C. 把 TTS 输出送进 Whisper 转写，再与输入文本算 CER
- D. CMOS

**Q4.** 下列关于 VITS 的描述，正确的是：

- A. 自回归 LSTM 解码器 + location-sensitive attention，逐帧生成 mel
- B. 用变分推断把 encoder、基于 flow 的时长模型和 HiFi-GAN vocoder 端到端联合训练
- C. 在 flow matching 上训练的 diffusion transformer，5 秒参考即可零样本克隆
- D. 82M 参数、可在 CPU 上实时运行的英文专用模型

**Q5.** Kokoro 输出 24 kHz 音频，而下游管道只接受 16 kHz。正确做法是：

- A. 每 3 个采样点丢掉 1 个
- B. 不动数据，只把文件头里的采样率改成 16000
- C. 用带抗混叠低通滤波的重采样（例如 2/3 倍的多相重采样）
- D. 不用处理，下游模型对采样率不敏感

**Q6.** 输入 "Dr. Smith lives on Smith Dr. since 2026." 被念成了 "D R … two zero two six"。应该在哪个环节修复？

- A. Vocoder：换成 BigVGAN
- B. 声学模型：加大 duration predictor 的容量
- C. 文本前端：在 phonemizer 之前加文本归一化（缩写展开、数字读法）
- D. 后处理：对波形做 `np.clip(wav, -1, 1)`

**Q7.** 你要为一种只有约 10 小时录音的低资源语言做 TTS，按讲义的 2026 选型表，首选是：

- A. 直接用 Kokoro 的英文声音
- B. 在 5–20 小时目标语言数据上训练 VITS
- C. 训练 Tacotron 2
- D. 用 ElevenLabs 的情感标签

---

## 三、动手 / 代码题

**Q8.** 下面是 `main.py` 里的 `phonemize`（G2P 表见源码）。不运行代码，写出 `phonemize("6 pm")` 和 `phonemize("Dr. Smith")` 的返回值，说明各自暴露了什么问题，并写一个最小的 `normalize(text)` 放在它前面，至少处理 0–9 的单个数字和 "Dr." 缩写。

```python
def phonemize(text):
    text = text.lower()
    phones = []
    i = 0
    while i < len(text):
        matched = False
        for length in (3, 2, 1):
            if i + length <= len(text):
                chunk = text[i : i + length]
                if chunk in G2P:
                    phones.extend(G2P[chunk])
                    i += length
                    matched = True
                    break
        if not matched:
            i += 1
    return phones
```

**Q9.** `phonemize("mother")` 的结果是什么？为什么 "er" 没有被识别成 `ER`？这种"字符级贪心最长匹配"的根本缺陷是什么，真实系统怎么做？

**Q10.** 阅读 `duration`：

```python
def duration(phones, jitter=0.1, seed=0):
    random.seed(seed)
    out = []
    for p in phones:
        base = DURATION_FRAMES.get(p, 5)
        noise = int(round(base * random.uniform(-jitter, jitter)))
        out.append(max(1, base + noise))
    return out
```

(1) 当 `jitter=0.1` 时，基础帧数为 3、4、5 的音素（占大多数辅音）会不会被扰动？基础帧数为 12 的 `_PAUSE_` 呢？
(2) `random.seed(seed)` 写在函数里有什么副作用？
(3) 改写这个函数，使用局部随机数生成器，并让小帧数的音素也能真正得到扰动（提示：先在浮点上扰动、累计后再取整）。

---

## 四、面试高频题

**Q11.**（基础必考）讲一下现代 TTS 的三段式管线：每段的输入输出、代表模型。既然 2026 年很多模型已经端到端，这个三段式心智模型还有什么用？

**Q12.**（原理深挖）自回归 TTS（Tacotron 2）与非自回归 TTS（FastSpeech 2）的核心区别是什么？Tacotron 的 attention 对齐会出哪些问题？FastSpeech 用 duration predictor 解决了什么、又牺牲了什么？

**Q13.**（工程实践）语音助手要求 TTS 在 CPU 上首包延迟低于 300 ms，并且能正确念出时间、金额和人名。请给出模型选型和完整的工程设计。

**Q14.**（场景设计）一个新的 TTS / 声音克隆模型要上线，你如何设计评测方案？哪些指标是自动的、哪些必须人工？测试集应该覆盖什么？

**Q15.**（追问型）HiFi-GAN 为什么能比 WaveNet 快几个数量级？`upsample_rates=[8, 8, 2, 2]` 的乘积 256 代表什么？如果声学模型 hop 是 300 个采样点，这个 vocoder 还能直接用吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

Tacotron 2 的 decoder 每一步都要依赖上一步输出的 mel 帧（自回归），一句话几百帧就要串行跑几百步。FastSpeech 2 先用 duration predictor 给每个音素预测"占几帧"，把音素序列按帧数展开（length regulator）后一次性并行生成所有帧。A 是无关细节；C 错，FastSpeech 2 仍需要 vocoder；D 与速度无关。

### Q2 — 答案：A

时长 = 160 × 12.5 ms = 2000 ms = 2.0 s；每帧采样点 = 0.0125 s × 24000 = 300，总采样点 = 160 × 300 = 48000（也可以直接 2.0 s × 24000）。B 是按 16 kHz 算的；C 是按 10 ms hop 算的；D 是把 hop 误当作 HiFi-GAN 常见的 256 个采样点——这正是"声学模型与 vocoder 的 hop 必须一致"的陷阱。

### Q3 — 答案：C

讲义的做法是"Run TTS output through Whisper, compute CER against the input text"，作为可懂度的代理。UTMOS 预测的是自然度（主观质量），SECS 衡量的是音色相似度（克隆），CMOS 是人工 A/B 偏好打分，都不直接衡量"字念对没有"。

### Q4 — 答案：B

A 描述的是 Tacotron 2，C 描述的是 F5-TTS，D 描述的是 Kokoro。VITS 的关键词是"变分推断 + flow + 对抗训练的 HiFi-GAN 解码器，单模型端到端"，在 2022–2024 年是开源 TTS 的主力。

### Q5 — 答案：C

24 kHz → 16 kHz 是 2/3 倍降采样。A 是不加低通的抽取：新的 Nyquist 频率是 8 kHz，原信号 8–12 kHz 的成分会折叠回低频，产生混叠（aliasing）。B 不改数据只改元数据，等于把 24000 个点当 16000 个点播放，时长变成 1.5 倍、音调变低。D 错，ASR/VAD 模型通常严格要求固定采样率。讲义原话："resample or get aliasing"。

### Q6 — 答案：C

"Dr." 读成 Doctor 还是 Drive、"2026" 读成 twenty twenty-six 还是 two zero two six，都是**文本前端**的问题，讲义强调"Normalize BEFORE phonemizer"。声学模型和 vocoder 只会忠实地念出它收到的音素，修它们没用；clip 只解决幅度溢出。

### Q7 — 答案：B

讲义选型表："Low-resource language → Train VITS on 5–20 h target-lang data"。Kokoro 在讲义中被描述为英文模型（skill 文件甚至要求"Flag any Kokoro deployment asked to speak languages other than English"）；Tacotron 2 讲义明确说"除非你是历史学家"别用；情感标签解决的是表现力而不是语种覆盖。

### Q8 — 参考答案

```text
phonemize("6 pm")      → ['_', 'P', 'M']
phonemize("Dr. Smith") → ['D', 'R', '_PAUSE_', '_', 'S', 'M', 'IH', 'TH']
```

- "6" 不在 G2P 表里，走 `if not matched: i += 1` 被**静默丢弃**；"pm" 被逐字母念成 P、M。主句里 "at 6 pm" 因此缺了数字。
- "Dr." 被逐字母拼读，句点还被当成**句末停顿** `_PAUSE_`（12 帧 = 150 ms），句子会在 "Dr" 后面断开。

最小归一化器（已验证可运行）：

```python
import re

ONES = ["zero", "one", "two", "three", "four",
        "five", "six", "seven", "eight", "nine"]
ABBR = {"dr.": "doctor", "mr.": "mister", "pm": "p m", "am": "a m"}

def normalize(text):
    words = []
    for w in text.lower().split():
        if w in ABBR:
            words.append(ABBR[w])
        else:
            words.append(w)
    text = " ".join(words)
    # 单个数字转单词；多位数需要更完整的 number-to-words 规则
    return re.sub(r"\d", lambda m: " " + ONES[int(m.group())] + " ", text).strip()

print(normalize("Dr. Smith at 6 pm"))   # doctor smith at  six  p m
```

要点：①归一化必须在 G2P **之前**；②"Dr." 的歧义（Doctor/Drive）需要上下文（后面跟人名还是在门牌号后），生产中用规则 + 上下文的 normalizer（如 WFST 类工具）；③年份、金额、时间要按语义选读法，不能简单逐位读。

### Q9 — 参考答案

`phonemize("mother")` → `['M', 'AO', 'DH', 'AH', 'R']`。

扫描过程：`m`→M；`o`→AO；到位置 2 时先试 3 个字符 `"the"`，命中 `["DH","AH"]`，指针跳到 `r`，于是 `"er"` 被拆散，只剩 `r`→R。

根本缺陷：**字符级、无上下文、贪心**。它不知道单词边界（"the" 作为单词与作为 "mother" 的一部分被同等对待），也不处理英语里大量不规则拼读（"ea" 在 please/bread/great 中读音不同）。真实系统：先按单词查发音词典（如 CMU 词典，ARPABet 39 个音素），查不到的 OOV 词再交给训练好的 G2P 模型（讲义提到 espeak-ng、g2p-en），同形异音词（read/read、live/live）还需要结合词性或上下文消歧。

### Q10 — 参考答案

(1) `noise = round(base × U(-0.1, 0.1))`。base ≤ 5 时 `|base × 0.1| ≤ 0.5`，`round` 之后恒为 0（Python 对 ±0.5 采用银行家舍入，也得 0），所以**完全没有抖动**；base = 6 时只有约 1/6 的概率变成 ±1；base = 12 的 `_PAUSE_` 落在 `|x| > 0.5` 的概率约 0.7/1.2 ≈ 58%，会变成 11 或 13。实测这句话加不加抖动总帧数都是 210。

(2) `random.seed` 重置的是**全局**随机状态：调用一次 `duration` 会影响程序其他地方所有 `random.*` 的结果，并且每次调用都从同一个种子开始，多次调用得到完全相同的"随机"抖动。

(3) 参考实现：

```python
import random

def duration(phones, jitter=0.1, seed=0):
    rng = random.Random(seed)          # 局部生成器，无全局副作用
    out, acc_float, acc_int = [], 0.0, 0
    for p in phones:
        base = DURATION_FRAMES.get(p, 5)
        acc_float += base * (1 + rng.uniform(-jitter, jitter))
        d = max(1, round(acc_float) - acc_int)   # 累计后取整，误差不丢失
        out.append(d)
        acc_int += d
    return out
```

用"累计浮点时长再取整"的方式，每个音素的小数部分会被带到下一个音素，整体时长的抖动不会被量化吃掉——这和 FastSpeech 类模型把连续时长转成整数帧时常用的做法同一个思路。

### Q11 — 参考回答要点

- **三段**：
  - 文本前端：原始字符串 → 归一化文本 → 音素/子词 token（可附带韵律特征）。工具：espeak-ng、g2p-en。
  - 声学模型：音素 → mel 频谱 `[T, 80]`。代表：Tacotron 2、FastSpeech 2、VITS、F5-TTS、Kokoro。
  - Vocoder：mel → 波形 `[T × hop]`。代表：WaveNet、WaveRNN、HiFi-GAN、BigVGAN、神经编解码器（SNAC、DAC）。
- **为什么仍有用**：出了问题可以分段定位——念错字/数字读错是前端问题；节奏怪、停顿错、跳词是声学模型/时长问题；嗡嗡声、金属音、爆音是 vocoder 或 mel 尺度不匹配。即使 VITS、F5 这类端到端模型，mel 仍是内部表示。
- **加分点**：提到 2024 年后神经编解码器让 TTS 变成"预测离散音频 token"的语言模型问题（与第 13 节神经音频编解码器呼应）。
- **常见误区**：认为端到端模型就不需要文本归一化——讲义明确说任何生产 TTS 都必须有 normalizer。

### Q12 — 参考回答要点

- **自回归（Tacotron 2）**：decoder 每步以上一帧 mel 为输入，用 location-sensitive attention 决定当前该念哪个字符。问题：①串行生成，延迟随长度线性增长；②attention 对齐不稳——长句容易跳词、重复、提前停止或"念不完"（讲义说的 wobbly on long text）。
- **非自回归（FastSpeech 2）**：duration predictor 显式预测每个音素的整数帧数，length regulator 按帧数复制音素表示，之后整段并行生成。好处：一次前向、快约 10×；对齐由时长硬性决定，不会跳词重复；可以直接改时长控制语速。
- **代价**：时长是确定性的、单调对齐，韵律多样性和自然度略差（讲义：Loses some naturalness）；训练时需要外部的对齐来源提供时长标签。
- **后续发展**：VITS 用 flow 化的随机时长模型把多样性补回来；F5-TTS 用 flow matching 生成，自然度和克隆能力更强。
- **加分点**：把"整数帧数"和代码中 `DURATION_FRAMES` / `mel_schedule` 联系起来——FastSpeech 的输出就是这样一张"每个音素从几毫秒到几毫秒"的时间表。

### Q13 — 参考回答要点

- **选型**：讲义推荐实时英文 CPU 场景用 Kokoro（82M，单文件，离线运行）；有 GPU 可考虑 XTTS v2。
- **文本前端**：时间、金额、日期、缩写的规则归一化放在 phonemizer 之前；人名等 OOV 走 G2P 模型兜底，并维护一个可人工修订的发音词典（客户名、产品名）。
- **降低首包延迟**：按句子/子句切分，先合成第一句就开始播放（流式），后面的句子在播放时继续合成；模型常驻内存并做预热，避免冷启动。
- **音频后处理**：`np.clip(wav, -1, 1)` 防止 mel 尺度不匹配造成的溢出；Kokoro 输出 24 kHz，若下游是 16 kHz 必须带抗混叠地重采样。
- **监控**：把 TTS 输出抽样送 Whisper 算 CER，用 UTMOS 做回归检测。
- **常见误区**：只盯模型推理时间，忽略文本归一化错误这类"念错了"的事故——用户对念错数字的容忍度远低于对音质的容忍度。

### Q14 — 参考回答要点

- **自动指标**：
  - 自然度：UTMOS / DNSMOS（无参考神经 MOS 预测，适合排行榜和回归测试）。
  - 可懂度：Whisper 转写 → CER（与输入文本对比）。
  - 克隆相似度：SECS（参考音频与输出的说话人 embedding 余弦相似度，与第 06 节说话人识别同源）。
- **人工指标**：MOS（1–5 分，金标准但慢）；CMOS（A/B 对比，每次标注的置信区间更紧），用于模型之间的直接比较。
- **测试集**：参考 skill 文件的"20 条测试句"——覆盖数字/日期/金额、同形异音词、专有名词、长句（检测对齐崩溃）、标点丰富的句子；克隆场景加不同噪声底和口音的参考音频。
- **基线**：讲义给出 LibriTTS test-clean 上 Ground truth UTMOS 4.08、CER 1.2%，可作为上限参照。
- **加分点**：自动指标只是代理——UTMOS 高不代表念对了，CER 低不代表好听，必须组合使用；克隆功能需要同意机制与水印（skill 文件要求）。

### Q15 — 参考回答要点

- **为什么快**：WaveNet 是逐采样点自回归（每秒 24000 步串行），讲义标注为 offline only；HiFi-GAN 是全卷积、非自回归的生成器，一次前向把整段 mel 上采样为波形，可在 GPU 上并行，讲义给出约 100× 实时。
- **结构**：几个转置卷积上采样块，`[8, 8, 2, 2]` 的乘积 256 表示每个 mel 帧被展开成 256 个采样点，必须等于声学模型提取 mel 时的 hop length（采样点数）。
- **训练损失**：对抗损失（判别器看短窗口）+ mel 频谱重建损失 + 判别器中间层的 feature-matching 损失。讲义认为它已经"商品化"，直接用预训练权重。
- **hop 不一致怎么办**：hop = 300 时 256× 的 vocoder 不能直接用——输出时长会错（只有 256/300 ≈ 85%），音调和语速都会变。要么用匹配 hop 的 vocoder（上采样倍率乘积为 300，如 `[5, 5, 4, 3]`），要么重新按 256 的 hop 提取 mel 训练声学模型。
- **常见误区**：只对齐采样率而忘了对齐 hop、n_mels、mel 的归一化方式——讲义 Pitfalls 中"mel scaling mismatch"导致输出越界就是这类问题。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 02 频谱图、Mel 刻度与音频 Features](../../02-spectrograms-mel-features/docs/zh.md)：mel 频谱、hop length、帧率的定义，是本节"mel 帧时间表"的基础。
- [阶段 05 · 09 序列到序列](../../../05-nlp-foundations-to-advanced/09-sequence-to-sequence/docs/zh.md)：Tacotron 2 本质是带 attention 的 seq2seq。
- [阶段 07 · 05 完整 Transformer](../../../07-transformers-deep-dive/05-full-transformer/docs/zh.md)：F5-TTS 的 diffusion transformer 主干。
- [阶段 06 · 04 语音识别 (ASR)](../../04-speech-recognition-asr/docs/zh.md)：ASR 与 TTS 互为逆问题，CER 评测也来自 ASR。

### 本节被哪些后续内容用到
- [阶段 06 · 06 说话人识别与验证](../../06-speaker-recognition-verification/docs/zh.md)：SECS 依赖的说话人 embedding。
- [阶段 06 · 08 语音克隆和语音转换](../../08-voice-cloning-conversion/docs/zh.md)：在本节的 TTS 上加入参考音频条件，做零样本克隆。
- [阶段 06 · 12 构建语音助手管道](../../12-voice-assistant-pipeline/docs/zh.md)：TTS 是语音助手的最后一段，首包延迟直接影响体验。
- [阶段 06 · 13 神经音频编解码器](../../13-neural-audio-codecs/docs/zh.md)：SNAC、DAC 等把 vocoder 变成离散 token 解码器。
- [阶段 06 · 17 音频 Evaluation](../../17-audio-evaluation-metrics/docs/zh.md)：MOS、UTMOS、WER/CER 的系统讲解。
- [阶段 08 · 03 GAN](../../../08-generative-ai/03-gans-generator-discriminator/docs/zh.md)：HiFi-GAN 的对抗训练原理。
- [阶段 08 · 13 Flow Matching](../../../08-generative-ai/13-flow-matching-rectified-flows/docs/zh.md)：F5-TTS 的生成框架。
- [阶段 14 · 22 语音 Agent（Pipecat / LiveKit）](../../../14-agent-engineering/22-voice-agents-pipecat-livekit/docs/zh.md)：生产级语音 Agent 中 TTS 的流式接入。

### 延伸关键词
`length regulator` · `monotonic alignment search (MAS)` · `StyleTTS 2` · `XTTS v2` · `BigVGAN` · `espeak-ng / g2p-en` · `WFST 文本归一化` · `UTMOS` · `SECS` · `流式 TTS 首包延迟`
