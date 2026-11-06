# 测验 · 频谱图、Mel 刻度与音频 Features（Spectrograms, Mel Scale & Audio Features）

> **阶段 06 · 语音与音频 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么不直接喂波形 | 10 秒 16 kHz = 160,000 个 float，与标签几乎不相关；同一个音素相隔 100 ms 说两次，原始样本完全不同 |
| 2 | STFT | 分帧（25 ms 窗 / 10 ms 帧移 = 16 kHz 下 400 / 160 样本）→ 加窗 → 逐帧 FFT → 堆成 `(n_frames, n_fft//2+1)` 矩阵 |
| 3 | 帧数公式 | 不补边时 `n_frames = 1 + (L − frame_len) // hop`；10 秒 16 kHz、400/160 → 998 帧 |
| 4 | 窗函数 | Hann（默认）/ Hamming 把帧两端压到 0 附近，减少截断造成的频谱泄漏 |
| 5 | 对数幅度 | 原始幅度跨 5–6 个数量级，取 `log(\|X\| + eps)` 或 `20·log10(\|X\|)` 压缩动态范围；生产中一律用对数 |
| 6 | Mel 刻度 | `m = 2595·log10(1 + f/700)`：1 kHz 以下近似线性、以上近似对数，模拟人耳对音高的感知 |
| 7 | Mel 滤波器组 | 在 mel 轴上等距的三角滤波器，矩阵形状 `(n_mels, n_fft//2+1)`；一次矩阵乘法把 STFT 投影到 mel 频带；低频滤波器窄、高频滤波器宽 |
| 8 | Log-mel 与 MFCC | Log-mel 是 2026 年通用音频前端；MFCC = 对 log-mel 做 DCT-II 取前 13 个系数，去相关、更紧凑，c0 编码总能量 |
| 9 | 分辨率权衡 | 帧越长频率越细、时间越粗：语音 25/10 ms，音乐 50/12.5 ms，瞬态检测 5/2 ms |
| 10 | 常见上线坑 | mel 数不一致、上游采样率不一致、dB vs log、训练/推理归一化不一致、尾部补零泄漏 |

### 核心技能（能动手做到）

- [ ] 只用 `math` 实现分帧、Hann 窗、STFT 幅度谱，并能算出任意长度音频的帧数和频率 bin 数
- [ ] 从零实现 `hz_to_mel` / `mel_to_hz` 和三角 mel 滤波器组，说出 `(n_mels, n_fft//2+1)` 的形状来源
- [ ] 用一次 NumPy 矩阵乘法 `stft_mag @ fb.T` 替代三重循环，并验证结果一致
- [ ] 实现 log-mel 和 DCT-II，得到 MFCC，并验证 c0 等于该帧 log-mel 之和
- [ ] 能定位 `chirp` 函数的瞬时频率 bug，并写出正确的线性 chirp 相位公式
- [ ] 给定下游任务（ASR / TTS / 分类 / 说话人 / KWS），选出特征类型、mel 数、帧长/帧移和归一化方式

---

## 二、基础自测（选择题）

**Q1.** 一段 10 秒、16 kHz 的音频，`frame_len = 400`、`hop = 160`、不补边，按讲义的分帧公式得到多少帧？

- A. 1000
- B. 1001
- C. 998
- D. 997

**Q2.** 用 `n_fft = 400` 做 STFT，构造 80 个 mel 滤波器的 filterbank，矩阵形状是：

- A. `(80, 400)`
- B. `(80, 201)`
- C. `(80, 200)`
- D. `(201, 400)`

**Q3.** 关于 mel 滤波器组，下列说法正确的是：

- A. 滤波器在 Hz 轴上等距，所以每个滤波器覆盖的 FFT bin 数相同
- B. 滤波器在 mel 轴上等距，所以低频滤波器窄、高频滤波器宽
- C. 滤波器在 mel 轴上等距，所以低频滤波器宽、高频滤波器窄
- D. mel 滤波器是矩形的，相邻滤波器之间没有重叠

**Q4.** 生产中的音频特征几乎都要取对数（log-magnitude / log-mel），最主要的原因是：

- A. 去掉相位信息
- B. 提高频率分辨率
- C. 原始幅度跨 5–6 个数量级，取对数压缩动态范围，也更接近人耳对响度的感知
- D. 让矩阵变得稀疏，减少计算量

**Q5.** 关于 MFCC，下列说法**错误**的是：

- A. MFCC 是对 log-mel 频谱做 DCT（type II）后保留前若干个系数
- B. DCT 让各维特征去相关、进一步压缩
- C. 第 0 个系数编码整体能量，下游常把它丢掉
- D. 现代 ASR（Whisper、Parakeet）的输入就是 13 维 MFCC

**Q6.** 一个模型训练时对每条音频做 per-utterance 均值方差归一化，上线后推理代码改成了用全局统计量归一化。最可能的现象是：

- A. 推理时立刻报形状不匹配的错误
- B. 不报错，但 WER 明显上升
- C. 完全没有影响，归一化方式不重要
- D. 推理速度变慢一倍

**Q7.** 要检测鼓点、爆破音这类非常短促的瞬态事件，帧长 / 帧移最合适的是：

- A. 50 ms / 12.5 ms
- B. 25 ms / 10 ms
- C. 5 ms / 2 ms
- D. 200 ms / 100 ms

**Q8.** `hz_to_mel(1000)` 的值约等于：

- A. 100
- B. 1000
- C. 2595
- D. 2146

---

## 三、动手 / 代码题

**Q9.** `code/main.py` 的 Step 5 本意是生成一个 "200 Hz → 4000 Hz" 的线性扫频（chirp），并打印每帧能量最大的 mel bin。阅读代码，回答：①实际运行时 `argmax_mel` 是单调上升的吗？②为什么？③给出修正后的 `chirp`。

```python
def chirp(f0, f1, sr, seconds, amp=0.5):
    n = int(sr * seconds)
    out = []
    for i in range(n):
        t = i / sr
        f = f0 + (f1 - f0) * (t / seconds)
        out.append(amp * math.sin(2.0 * math.pi * f * t))
    return out
```

（参数：`sr = 8000`、`seconds = 0.4`、`frame_len = 256`、`hop = 128`、`n_mels = 40`）

**Q10.** 阅读分帧函数：

```python
def frame_signal(signal, frame_len, hop):
    if len(signal) < frame_len:
        return []
    n = 1 + (len(signal) - frame_len) // hop
    return [signal[i * hop : i * hop + frame_len] for i in range(n)]
```

(a) `sine(2000.0, 8000, 0.5)` 用 `frame_len=256, hop=128` 能切出多少帧？
(b) 一段只有 100 个样本的音频会返回什么？这在流式/短音频场景下有什么隐患？
(c) 写一个 `frame_center(signal, frame_len, hop)`：两端各做 `frame_len // 2` 的 reflect 补边后再分帧（类似 `librosa.stft(center=True)`），并说出它对 4000 个样本、hop=128 会产生多少帧。

**Q11.** `apply_filterbank` 用三重循环把 STFT 投影到 mel 频带：

```python
def apply_filterbank(stft_mag, fb):
    n_mels = len(fb)
    result = []
    for spec in stft_mag:
        frame_mels = []
        for m in range(n_mels):
            val = 0.0
            for k, w in enumerate(fb[m]):
                if w:
                    val += spec[k] * w
            frame_mels.append(val)
        result.append(frame_mels)
    return result
```

用 NumPy 一行改写它，说明各矩阵的形状，并说明 `if w:` 这行的作用。另外：这里传进来的是**幅度谱**而不是**功率谱**，和 librosa / Whisper 的默认做法有何不同？

**Q12.** `main.py` 的 Step 6 对一帧 log-mel 做 `dct_ii(..., 13)`。不运行代码，证明 `dct_ii(x, 1)[0] == sum(x)`，并由此解释"c0 编码整体能量"这句话。

---

## 四、面试高频题

**Q13.**（基础必考）从原始波形到 log-mel 再到 MFCC，完整说一遍流程。以 10 秒 16 kHz、25 ms / 10 ms、`n_fft=400`、80 mels 为例，写出每一步的张量形状。

**Q14.**（原理深挖）为什么要用 mel 刻度和对数？MFCC 曾经统治语音识别，为什么深度学习时代主流改回直接用 log-mel？

**Q15.**（工程实践）训练和线上推理的特征不一致是语音系统最常见的"静默 bug"。请列举典型的不一致来源，并说明你会建立哪些机制来防止。

**Q16.**（场景设计）分别为以下三个任务选择前端特征（类型、mel 数、帧长/帧移），并说明理由：(a) 跑在 MCU 上的唤醒词检测；(b) 环境声分类（类似 AudioSet）；(c) 音乐生成。

**Q17.**（追问型）帧长和帧移怎么选？时频分辨率之间是什么关系？Hann 窗和 Hamming 窗有什么区别？幅度谱和功率谱该用哪个？

---

## 五、参考答案与解析

### Q1 — 答案：C

`1 + (160000 − 400) // 160 = 1 + 997 = 998`。A 是 `160000 / 160`，忽略了最后一帧需要完整的 400 个样本；B 是 `center=True`（两端各补 200 个样本）时 librosa 的帧数 `1 + 160000 // 160`；D 少算了第一帧。讲义原文：10 秒片段 → 998 帧。

### Q2 — 答案：B

实信号的 `n_fft` 点 FFT 只有 `n_fft // 2 + 1 = 201` 个非冗余 bin（0 Hz 到 Nyquist，两端都包含）。filterbank 每行是一个 mel 滤波器在这 201 个 bin 上的权重，所以是 `(80, 201)`；`(n_frames, 201)` 的 STFT 乘以它的转置就得到 `(n_frames, 80)`。C 少了 Nyquist 那个 bin；A 和 D 把冗余的后半部分也算进来了。

### Q3 — 答案：B

滤波器中心在 mel 轴上等距；mel 在高频是对数压缩的，等距的 mel 间隔映射回 Hz 后越来越宽。代码 Step 4 实测：前 6 个滤波器各覆盖 1–2 个 bin，最后 6 个覆盖 10–12 个 bin。这正对应人耳"低频分辨细、高频分辨粗"。D 错：mel 滤波器是三角形，相邻滤波器重叠一半（一个的中心是下一个的左端点）。

### Q4 — 答案：C

讲义："Raw magnitudes span 5-6 orders of magnitude"。不取对数时，少数高能量 bin 主导数值，安静但重要的高频细节几乎为 0，网络很难学。对数还把乘性的增益变化变成加性偏移，便于归一化。A 错：取幅度时相位已经丢掉了；B、D 与对数无关。

### Q5 — 答案：D

Whisper、Parakeet、SeamlessM4T 的输入是 **log-mel**，不是 MFCC；技能文件 `skill-feature-extractor` 甚至要求"把任何为 Whisper/Parakeet 配 MFCC 的方案标为错误"。A、B、C 都是讲义原文的要点。

### Q6 — 答案：B

讲义的 "Normalization drift" 坑：两种归一化输出的形状完全相同，不会报错，但数值分布不同，模型看到的是"分布偏移"的输入，讲义说这是"会让 WER 翻倍的生产 bug"。A 错在形状不变；C、D 显然不对。

### Q7 — 答案：C

讲义："5 ms / 2 ms for transient detection (drum hits, plosives)"。瞬态只持续几毫秒，25 ms 的窗会把它和前后的内容平均掉。A 是音乐的设置（需要更细的频率分辨率分辨音高），B 是语音默认值，D 时间分辨率太差。

### Q8 — 答案：B

`2595 × log10(1 + 1000/700) = 2595 × log10(2.4286) ≈ 2595 × 0.3853 ≈ 1000`。mel 刻度的常数就是这样选的：1000 Hz 对应 1000 mel。D 是 `hz_to_mel(4000)` ≈ 2146.1（代码中 8 kHz 采样时的 `fmax`）。

### Q9 — 参考答案

① **不是**。实际输出（每隔一帧打印）：

```text
t=  0  argmax_mel=11
t=  2  argmax_mel=20
...
t= 12  argmax_mel=39
t= 14  argmax_mel=36
...
t= 22  argmax_mel=15
```

argmax 先升到 39（最高的 mel bin），然后又降回 15——是"先升后降"的形状。

② **瞬时频率算错了**。正弦的瞬时频率是相位对时间的导数除以 2π。代码的相位是 `2π·f(t)·t = 2π·(f0·t + (f1−f0)·t²/T)`，求导得瞬时频率 `f0 + 2(f1−f0)·t/T`——斜率是预期的 **2 倍**。所以 `t = T/2 = 0.2 s` 时就已经到 4000 Hz（= 8 kHz 采样的 Nyquist），之后继续升到 7800 Hz，超过 Nyquist 被**折叠**回来（`8000 − 7800 = 200 Hz`），表现为"下降"。逐帧 STFT 峰值实测：500 → 3875 Hz（第 11 帧附近）→ 再降回 500 Hz。这也顺带复习了上一节的 aliasing。

③ 修正：线性 chirp 的相位应为 `2π·(f0·t + ½·k·t²)`，`k = (f1 − f0)/T`：

```python
def chirp(f0, f1, sr, seconds, amp=0.5):
    n = int(sr * seconds)
    k = (f1 - f0) / seconds
    out = []
    for i in range(n):
        t = i / sr
        out.append(amp * math.sin(2.0 * math.pi * (f0 * t + 0.5 * k * t * t)))
    return out
```

修正后同样的参数，argmax mel 实测为 `8, 13, 18, 21, 24, 27, 29, 32, 34, 35, 37, 39`，单调上升，与"扫频"一致。注意 mel bin 的上升速度前快后慢——因为 mel 轴在高频被压缩。

### Q10 — 参考答案

(a) `int(8000 × 0.5) = 4000` 个样本，`1 + (4000 − 256) // 128 = 1 + 29 = 30` 帧（与 Step 1 输出一致）。

(b) 返回空列表 `[]`。后续 `stft_magnitude` 也会返回空，`mag[len(mag) // 2]` 会 `IndexError`。在流式识别、短唤醒词片段、VAD 切出的极短语音中都可能出现，需要补边或在上游丢弃过短片段并给出明确报错。

(c)

```python
import numpy as np

def frame_center(signal, frame_len, hop):
    pad = frame_len // 2
    x = np.pad(np.asarray(signal), pad, mode="reflect")
    return frame_signal(list(x), frame_len, hop)
```

对 4000 个样本、hop=128，补边后长度 4256，帧数 `1 + (4256 − 256) // 128 = 32 = 1 + 4000 // 128`。好处：第 `i` 帧的**中心**正好对齐时间 `i·hop`，首尾的样本也能落在帧中央被完整分析。用 reflect 而不是补零，正对应讲义的 "Leakage from padding" 坑：补零会让首尾帧出现平坦、不真实的频谱。

### Q11 — 参考答案

```python
import numpy as np
mel_spec = np.asarray(stft_mag) @ np.asarray(fb).T
```

- 形状：`stft_mag` 为 `(n_frames, n_fft//2+1)`，`fb` 为 `(n_mels, n_fft//2+1)`，`fb.T` 为 `(n_fft//2+1, n_mels)`，结果 `(n_frames, n_mels)`。对 Step 5 的数据实测形状 `(24, 40)`，与循环版本的最大差异约 `1.4e-14`（浮点求和顺序不同）。
- `if w:` 跳过权重为 0 的 bin。每个三角滤波器只覆盖少数几个 bin，大部分权重是 0，这一行是纯 Python 下"利用稀疏性"的手工优化；在 NumPy/GPU 上稠密矩阵乘法反而更快。
- 幅度 vs 功率：代码把 `|X|` 直接投影到 mel；`librosa.feature.melspectrogram` 默认 `power=2.0`（功率谱 `|X|²`），Whisper 的 `log_mel_spectrogram` 也是对 `|X|²` 做 mel。二者取对数后只差常数倍（`log|X|² = 2·log|X|`），但**加 eps 后再取对数**、以及后续的裁剪归一化会不同。所以一定要和目标模型的训练配置保持一致。

### Q12 — 参考答案

DCT-II：`X[k] = Σₙ x[n]·cos(π·k·(2n+1)/(2N))`。当 `k = 0` 时，`cos(0) = 1`，所以 `X[0] = Σₙ x[n]`，即该帧所有 log-mel 值之和（实测都等于 `-390.284…`）。

log-mel 之和 = `Σ log(mel_m) = log(Π mel_m)`，反映这一帧所有频带能量的整体大小（几何平均意义上的响度）。说话人离麦克风远近、增益大小都会主要改变它，而它对"说的是什么"贡献很小，所以下游常把 c0 丢掉，或单独用对数能量代替。

### Q13 — 参考回答要点

以 10 秒、16 kHz 为例：

| 步骤 | 操作 | 形状 |
|------|------|------|
| 波形 | float32，`[-1, 1]` | `(160000,)` |
| 分帧 | 400 样本帧、160 帧移（不补边） | `(998, 400)` |
| 加窗 | 逐帧乘 Hann 窗 | `(998, 400)` |
| FFT 取幅度/功率 | `rfft`，`n_fft = 400` | `(998, 201)` |
| Mel 投影 | `× fbᵀ`，fb 为 `(80, 201)` | `(998, 80)` |
| 取对数 | `log(mel + eps)` | `(998, 80)` |
| （可选）DCT-II | 保留前 13 维 | `(998, 13)` |

- 加分点：说明 `center=True` 时为 1001 帧；说明不同框架习惯 `(n_mels, n_frames)` 还是 `(n_frames, n_mels)`；提到 Whisper 等模型还有自己的裁剪 + 归一化步骤（讲义："Whisper uses a more involved clip + normalize routine"）。
- 常见误区：把 `n_fft` 个 bin 都算进去（应为 `n_fft//2+1`）。

### Q14 — 参考回答要点

- **mel 刻度**：人耳对音高的感知近似对数——低频处几十 Hz 的差别听得出来，高频处几百 Hz 的差别都不明显。mel 刻度在 1 kHz 以下近似线性、以上近似对数，把频率轴"按感知等距"重排，用 80 个频带就能保留语音最关键的信息，同时降维（201 → 80）。
- **对数**：压缩 5–6 个数量级的动态范围；把信道/增益的乘性变化变成加性，便于归一化；更接近人耳对响度的感知。
- **MFCC 曾统治的原因**：GMM-HMM 时代常用对角协方差高斯，需要各维特征**去相关**，DCT 正好做到；13 维也足够紧凑。
- **为什么改回 log-mel**：①CNN/Transformer 能自己学到相关结构，不需要人工去相关；②DCT 把相邻频带的局部结构打散了，卷积在 log-mel 上能利用"频率局部性"；③丢掉高阶系数等于丢信息，端到端模型更愿意自己决定用什么。讲义：大约 2015 年之后 log-mel 上的 CNN/Transformer 追上并取代 MFCC。
- **仍用 MFCC 的场景**：极小设备上的关键词检测（讲义表格：40 MFCC），部分说话人识别系统。

### Q15 — 参考回答要点

典型不一致（讲义 "Pitfalls that still ship in 2026"）：

1. **mel 数**：训练 80、推理 128；
2. **上游采样率**：22.05 kHz 与 16 kHz 算出的 mel 不一样，必须在特征提取**之前**统一采样率；
3. **dB vs 自然对数**：`power_to_db`（以 ref 归一化的 dB）与 `log(mel + eps)` 数值完全不同；Whisper 有自己的裁剪 + 归一化；
4. **归一化漂移**：per-utterance 与全局统计量混用；
5. **补边**：尾部补零导致尾帧平坦；
6. 其他：窗函数、`n_fft`、`center`、幅度/功率谱、`fmin/fmax` 的差异。

防止机制：
- **同一份特征代码**：训练和服务共用一个特征提取模块（或把特征提取导出进模型图里），而不是各写一份；
- **特征配置随模型版本一起保存**（sr、n_fft、hop、n_mels、fmin/fmax、log 类型、归一化统计量）；
- **形状与统计断言**：在两端打印/记录特征形状、min/max、mean/std，对一段固定参考音频做断言（技能文件第 5 条）；
- **黄金样本回归测试**：上线前对比训练管线与服务管线在同一音频上的特征差异。
- 加分点：说出"静默"的本质——形状一样、不报错，只有指标默默变差。

### Q16 — 参考回答要点

| 任务 | 特征 | 理由 |
|------|------|------|
| (a) MCU 唤醒词 | 约 40 维 MFCC（讲义表格："40 MFCCs for tiny devices"），帧长 25–30 ms、帧移 10–20 ms | 维度小、去相关，适合极小模型和有限内存；帧移可略大以减少计算 |
| (b) 环境声分类 | 128 log-mel，10 ms 帧移（讲义：AST、PANNs、BEATs） | 环境声频带分布广，更多 mel 频带保留细节；配合 CNN/Transformer |
| (c) 音乐生成 | 离散的 EnCodec token（讲义：MusicGen、Stable Audio 2 不用 mel） | 生成任务需要能还原成波形的表示，codec token 可直接解码；若做音乐分析而非生成，则用更长的帧（约 50 ms / 12.5 ms）提高频率分辨率 |

- 总原则（讲义）："if you are not working on music, start with 80 log-mels"，偏离它需要理由。
- 加分点：一定要对齐目标预训练模型的发布配置（技能文件："拒绝与目标模型训练配置不一致的特征管线"）。

### Q17 — 参考回答要点

- **时频权衡**：频率分辨率 `Δf = sr / n_fft`，时间跨度 `frame_len / sr`。窗口越长 `Δf` 越小（频率越细），但一帧内覆盖的时间越长，快速变化被抹平。二者不能同时任意小。
- **为什么语音选 25 ms / 10 ms**：25 ms 内声道形状近似不变（短时平稳），16 kHz 下 400 样本，频率分辨率 40 Hz 够分辨共振峰；10 ms 帧移让相邻帧重叠 60%，时间轴平滑，每秒 100 帧也便于对齐字符/音素。
- **Hann vs Hamming**：Hann 两端精确为 0（代码 Step 2：`hann(0) = hann(last) = 0`），旁瓣衰减快；Hamming 两端约 0.08，第一旁瓣更低但远处旁瓣衰减慢。讲义称其为"slightly different tradeoff"；Hann 是默认。
- **幅度 vs 功率**：功率谱 `|X|²` 是 librosa、Whisper 的默认；取对数后与幅度谱只差 2 倍系数，但数值范围、eps 的作用、dB 换算（`20·log10` vs `10·log10`）不同——关键是和训练时一致。
- 加分点：说出补零（`n_fft > frame_len`）只是插值，不能提高真实频率分辨率。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 01 音频基础知识](../../01-audio-fundamentals/docs/zh.md)：采样率、Nyquist、DFT bin、分帧加窗——本节直接接着它的 STFT 往下走。
- [阶段 01 · 20 傅里叶变换](../../../01-math-foundations/20-fourier-transform/docs/zh.md)：DFT/FFT 与 DCT 的数学背景。
- [阶段 01 · 10 降维](../../../01-math-foundations/10-dimensionality-reduction/docs/zh.md)：DCT 去相关、只保留前 13 维，与 PCA 降维的思路相通。

### 本节被哪些后续内容用到
- [阶段 06 · 03 音频分类](../../03-audio-classification/docs/zh.md)：MFCC 上的 k-NN、log-mel 上的 CNN/AST。
- [阶段 06 · 04 语音识别 (ASR)](../../04-speech-recognition-asr/docs/zh.md)：80 维 log-mel、10 ms 帧移是声学模型的输入。
- [阶段 06 · 05 Whisper——架构与 Fine-Tuning](../../05-whisper-architecture-finetuning/docs/zh.md)：Whisper 的 log-mel 前端与归一化细节。
- [阶段 06 · 06 说话人识别与验证](../../06-speaker-recognition-verification/docs/zh.md)：ECAPA-TDNN 的 80 维 log-mel 输入、MFCC 的传统用法。
- [阶段 06 · 07 文本转语音 (TTS)](../../07-text-to-speech/docs/zh.md)：TTS 声学模型预测的就是 mel 谱，帧移更短。
- [阶段 06 · 13 神经音频编解码器](../../13-neural-audio-codecs/docs/zh.md)：音乐生成用 codec token 代替 mel。

### 延伸关键词
`librosa.feature.melspectrogram` · `torchaudio.transforms.MelSpectrogram` · `power_to_db` · `Slaney vs HTK mel` · `delta / delta-delta` · `CMVN（倒谱均值方差归一化）` · `SpecAugment` · `PCEN`
