# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 02 节 频谱图、Mel 刻度与音频 Features ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`），无需 NumPy / librosa

---

## 1. 这份代码在考察什么

这份脚本把"波形 → STFT → mel 频谱 → log-mel → MFCC"这条特征阶梯**每一级都用纯 Python 手写一遍**，目的是让你在使用 `librosa` / `torchaudio` 之前知道它们内部在做什么：

1. **分帧与加窗**：帧数公式 `1 + (L − frame_len) // hop`，Hann 窗如何把帧边缘压到 0。
2. **STFT 幅度谱**：每帧 DFT 只保留 `n_fft // 2 + 1` 个 bin，峰值 bin 如何换算回 Hz。
3. **Mel 滤波器组**：mel 公式、三角滤波器的构造、为什么低频窄高频宽。
4. **Log-mel 与 MFCC**：取对数压缩动态范围，DCT-II 去相关并得到倒谱系数。
5. **用扫频信号验证**：chirp 的 argmax mel 应随时间上升——不过本文件的 `chirp` 有一个公式 bug，正好成为理解"瞬时频率"和 aliasing 的好例子（见 3.1）。

> 一句话：**搞懂 `(n_frames, n_fft//2+1) @ (n_fft//2+1, n_mels) → (n_frames, n_mels)` 这一次矩阵乘法背后的每个数字**，你就能排查绝大多数特征不一致的线上 bug。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sine` / `chirp` | 函数 | 合成测试信号（纯音 / 扫频） | 测试信号 |
| `hann(N)` | 函数 | 生成对称 Hann 窗 | 窗函数、频谱泄漏 |
| `dft_mag(x)` | 函数 | `O(N²)` DFT，只算前 `N//2+1` 个 bin 的幅度 | 实信号的非冗余频谱 |
| `frame_signal` | 函数 | 按 `frame_len` / `hop` 切帧 | 分帧 |
| `stft_magnitude` | 函数 | 分帧 → 加窗 → 逐帧 `dft_mag` | STFT |
| `hz_to_mel` / `mel_to_hz` | 函数 | Hz 与 mel 互转 | Mel 刻度 |
| `mel_filterbank` | 函数 | 构造 `(n_mels, n_fft//2+1)` 三角滤波器矩阵 | Mel 滤波器组 |
| `apply_filterbank` | 函数 | STFT × filterbankᵀ | Mel 频谱 |
| `log_transform` | 函数 | `log(max(v, eps))` | Log-mel |
| `dct_ii` | 函数 | DCT type II，取前 `n_coeffs` 个 | MFCC |
| `main()` | 演示入口 | 6 个步骤依次打印 | — |

数据流：`chirp` → `stft_magnitude`（内部 `frame_signal` + `hann` + `dft_mag`）→ `apply_filterbank`（用 `mel_filterbank` 的结果）→ `log_transform` → `dct_ii`。

---

## 3. 逐段精讲

### 3.1 测试信号：`sine` 与有 bug 的 `chirp`

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

- 作者的意图：频率 `f` 从 `f0` 线性升到 `f1`，然后计算 `sin(2π·f·t)`。
- ⚠️ **这里有一个经典错误**：正弦的**瞬时频率**是相位对时间的导数除以 2π，而不是"相位里乘的那个 f"。代码的相位是 `2π·(f0·t + (f1−f0)·t²/T)`，求导得 `f0 + 2·(f1−f0)·t/T`——扫频速度是预期的 **2 倍**。
  - 参数 `f0=200, f1=4000, T=0.4, sr=8000` 下，`t = 0.2 s` 时已经到 4000 Hz（Nyquist），之后继续升到 7800 Hz，超过 Nyquist 被折叠回 `8000 − 7800 = 200 Hz`。
  - 所以 Step 5 打印的 argmax mel 是**先升后降**（11 → 39 → 15），而不是讲义练习 1 说的"与扫频一致"的单调上升。
- 正确写法：相位 `2π·(f0·t + ½·k·t²)`，其中 `k = (f1 − f0)/T`。修正后 argmax mel 为 `8, 13, 18, …, 37, 39`，单调上升。
- `sine` 比上一节多了一个 `phase` 参数，本文件里没有用到。

### 3.2 Hann 窗

```python
def hann(N):
    return [0.5 * (1.0 - math.cos(2.0 * math.pi * n / (N - 1))) for n in range(N)]
```

- 公式 `w[n] = 0.5·(1 − cos(2πn/(N−1)))`：`n = 0` 和 `n = N−1` 时为 0，中间接近 1。乘到帧上之后，帧两端被平滑压到 0，消除"硬切"造成的不连续，减少频谱泄漏。
- 分母用 `N − 1` 是**对称窗**（首尾都为 0）。`torch.hann_window` 默认 `periodic=True`，分母用 `N`（只有首点为 0），更适合做 STFT 的重叠相加。两者差别很小，但与预训练模型对齐时要注意。
- Step 2 打印的 `hann(mid) = 1.0000` 其实是 `0.99996…`：`N = 256` 是偶数，对称窗的峰值落在两个样本之间，没有哪个样本正好等于 1。

### 3.3 只算一半的 DFT

```python
def dft_mag(x):
    n = len(x)
    half = n // 2 + 1
    out = []
    for k in range(half):
        # ...（与上一节相同的实部/虚部累加）
        out.append(math.sqrt(re * re + im * im))
    return out
```

- 与上一节的 `dft` 相比，外层只循环到 `n // 2 + 1`：实信号的频谱共轭对称，后半是镜像；这里**包含了 Nyquist bin**，与 `numpy.fft.rfft` 的输出长度一致（上一节的 `peak_freq` 少取了这一个）。
- 直接返回幅度 `|X|`，不返回相位——特征提取只关心能量分布。
- 计算量减半，但仍是 `O(N²)`：256 点每帧约 3.3 万次乘加，几十帧在 0.3 秒内能跑完。

### 3.4 分帧与 STFT

```python
def frame_signal(signal, frame_len, hop):
    if len(signal) < frame_len:
        return []
    n = 1 + (len(signal) - frame_len) // hop
    return [signal[i * hop : i * hop + frame_len] for i in range(n)]


def stft_magnitude(signal, frame_len, hop):
    w = hann(frame_len)
    frames = frame_signal(signal, frame_len, hop)
    return [dft_mag([w[j] * f[j] for j in range(frame_len)]) for f in frames]
```

- 帧数公式：第一帧占用 `frame_len` 个样本，之后每多 `hop` 个样本多一帧，所以 `1 + (L − frame_len) // hop`。讲义例子：10 秒 16 kHz、400/160 → 998 帧。
- `len(signal) < frame_len` 时返回空列表，避免公式算出 0 或负数。⚠️ 但调用方没有检查空结果，短音频会在 `mag[len(mag) // 2]` 处 `IndexError`。
- ⚠️ 没有补边（相当于 `librosa.stft(center=False)`）：第 `i` 帧的**起点**在 `i·hop`，而不是中心；最后不足一帧的样本被丢弃。生产库默认 `center=True`，两端各补 `frame_len // 2`，帧数变成 `1 + L // hop`。
- `n_fft = frame_len`：本文件不做补零。生产中常见 `frame_len = 400`、`n_fft = 512`（补到 2 的幂以便 FFT）。
- 输出形状：`(n_frames, frame_len // 2 + 1)`，Step 3 实测 `30 × 129`。

### 3.5 Mel 刻度

```python
def hz_to_mel(f):
    return 2595.0 * math.log10(1.0 + f / 700.0)


def mel_to_hz(m):
    return 700.0 * (10 ** (m / 2595.0) - 1.0)
```

- 这是 **HTK 风格**的 mel 公式。常数使得 `hz_to_mel(1000) ≈ 1000`；`f ≪ 700` 时近似线性（`log10(1+x) ≈ x/ln10`），`f ≫ 700` 时近似对数。
- 两个函数互为反函数，用来"在 mel 轴上等距取点，再映射回 Hz"。
- 参考值：`hz_to_mel(4000) ≈ 2146.1`、`hz_to_mel(8000) ≈ 2840.0`。可见 4–8 kHz 这一整段只占 mel 轴的约 700，而 0–1 kHz 就占了 1000——低频被"放大"、高频被"压缩"。
- librosa 默认的是 **Slaney 风格**（1 kHz 以下严格线性、以上对数），与这里的公式略有不同；要与预训练模型对齐时需要确认。

### 3.6 三角 mel 滤波器组

```python
def mel_filterbank(n_mels, n_fft, sr, fmin=0.0, fmax=None):
    if fmax is None:
        fmax = sr / 2
    m_lo = hz_to_mel(fmin)
    m_hi = hz_to_mel(fmax)
    mels = [m_lo + (m_hi - m_lo) * i / (n_mels + 1) for i in range(n_mels + 2)]
    hzs = [mel_to_hz(m) for m in mels]
    half = n_fft // 2 + 1
    bins = [min(half - 1, int(round(h * n_fft / sr))) for h in hzs]
    fb = [[0.0] * half for _ in range(n_mels)]
    for m in range(n_mels):
        left, center, right = bins[m], bins[m + 1], bins[m + 2]
        for k in range(left, center):
            denom = max(1, center - left)
            fb[m][k] = (k - left) / denom
        for k in range(center, right):
            denom = max(1, right - center)
            fb[m][k] = (right - k) / denom
    return fb
```

逐行理解：

1. **在 mel 轴上等距取 `n_mels + 2` 个点**：`n_mels` 个滤波器各需要"左端、中心、右端"三个点，相邻滤波器共享端点，所以总共 `n_mels + 2` 个。
2. **映射回 Hz，再映射成 FFT bin 下标**：`bin = round(h · n_fft / sr)`（上一节的 `k·sr/N` 公式反过来用）；`min(half − 1, ...)` 防止越界。
3. **三角形**：从 `left` 到 `center` 线性上升（0 → 1），从 `center` 到 `right` 线性下降（1 → 0）。第 `m` 个滤波器的中心正好是第 `m+1` 个的左端，相邻滤波器重叠一半。
4. `max(1, ...)` 防止分母为 0：低频处多个 mel 点可能落到同一个 bin 上。

本例实际的 bin 端点（`n_mels=40, n_fft=256, sr=8000`）是 `[0, 1, 2, 3, 5, 6, 7, 9, …, 108, 115, 121, 128]`：低频处间隔 1–2 个 bin，高频处 6–7 个 bin。这就是 Step 4 打印"前 6 个宽度 1–2、后 6 个宽度 10–12"的原因。

设计取舍：

- 讲义版本用 `int(h * n_fft / sr)`（向下取整），代码用 `int(round(...))` 并加了上界裁剪，更稳健。
- ⚠️ 滤波器**没有做面积归一化**：高频滤波器更宽，累加的 bin 更多，数值天然更大。librosa 默认 `norm="slaney"`，会把每个三角形除以其带宽，使各频带的能量可比。
- ⚠️ 三角形端点被量化到整数 bin 上，低频滤波器形状很粗糙（只有 1–2 个非零权重）。librosa 等实现在**连续频率**上计算三角权重，不会出现这种量化。
- 当 `n_mels` 过大而 `n_fft` 过小时，某些滤波器的 `left == center == right`，整行全为 0（"空滤波器"）。本例 40 mels / 129 bins 没有出现，但如果把 `n_mels` 调到 128 就要小心。

### 3.7 应用滤波器组：本质是一次矩阵乘法

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

- 三重循环做的就是 `mel[t][m] = Σₖ stft[t][k] · fb[m][k]`，即 `stft_mag @ fbᵀ`。讲义："Multiplying the STFT magnitude by the filterbank matrix gives the mel spectrogram in one matmul." NumPy 一行 `np.asarray(stft_mag) @ np.asarray(fb).T` 结果完全相同（实测最大差 1.4e-14）。
- `if w:` 跳过 0 权重——利用滤波器的稀疏性，纯 Python 下能省掉大部分乘法。
- ⚠️ 输入是**幅度谱** `|X|`。librosa（`power=2.0`）和 Whisper 都对**功率谱** `|X|²` 做 mel。取对数后只差 2 倍，但与预训练模型对接时必须一致。

### 3.8 取对数与 DCT

```python
def log_transform(mel_spec, eps=1e-10):
    return [[math.log(max(v, eps)) for v in frame] for frame in mel_spec]


def dct_ii(x, n_coeffs):
    N = len(x)
    return [
        sum(x[n] * math.cos(math.pi * k * (2 * n + 1) / (2 * N)) for n in range(N))
        for k in range(n_coeffs)
    ]
```

- `max(v, eps)` 而不是 `v + eps`：两者都能防止 `log(0)`，`max` 的写法对正常数值完全不做改动，只在接近 0 时"兜底"。`log(1e-10) ≈ −23`，是 log-mel 的下限。
- 用的是自然对数 `math.log`。讲义提醒的坑："dB vs log"——`10·log10`（dB）与 `ln` 差一个常数倍，再加上 dB 常配合 `ref=max` 归一化，数值完全不同。
- DCT-II 公式 `X[k] = Σ x[n]·cos(π·k·(2n+1)/(2N))`。`k = 0` 时 cos 恒为 1，`X[0] = Σ x[n]`，即整帧 log-mel 之和——所以说"c0 编码整体能量"（实测 `dct_ii(x, 1)[0]` 与 `sum(x)` 都是 `-390.284…`）。
- ⚠️ 没有做正交归一化（`scipy.fft.dct(norm="ortho")` / librosa 默认会乘缩放因子），所以数值比 librosa 的 MFCC 大。形状和"去相关"的思想是一样的。
- 只保留前 13 个：低阶 DCT 系数描述频谱包络（声道形状 → 音素），高阶系数描述细节（如基频谐波），对识别"说了什么"帮助小。

### 3.9 `main()` 的参数选择

```python
    sr = 8000
    frame_len = 256
    hop = 128
    n_mels = 40
    n_fft = frame_len
```

- 选 8 kHz、256 点帧（32 ms）、50% 重叠、40 mels，而不是讲义推荐的 16 kHz、400/160、80 mels，是为了让 `O(N²)` 的纯 Python DFT 能在 1 秒内跑完。
- 频率分辨率 `8000 / 256 = 31.25 Hz`，2000 Hz 正好是第 64 个 bin，所以 Step 3 精确报告 2000.0 Hz。
- Step 5 每隔 `len(lm) // 10 = 2` 帧打印一次；Step 6 取中间帧（第 12 帧）算 MFCC，这一帧恰好在 chirp 的瞬时频率越过 Nyquist 的位置附近。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 `math` 手写全部步骤 | 每一步都可读、可对照讲义 | 极慢；生产用 `torch.stft` / `librosa.stft` + `MelSpectrogram` |
| 低采样率、短帧、40 mels | 让 `O(N²)` DFT 秒级跑完 | 不是真实的 ASR 配置（真实为 16 kHz、400/160、80 mels） |
| `center=False` 式分帧 | 帧数公式最直观 | 首尾样本只出现在帧边缘；生产默认 reflect 补边 |
| 对称 Hann 窗（分母 `N−1`） | 教科书公式 | PyTorch 默认周期窗（分母 `N`），需对齐 |
| HTK mel 公式 + 整数 bin 三角形 | 公式简单 | librosa 默认 Slaney mel + 连续频率三角 + 面积归一化 |
| 对幅度谱做 mel | 少一次平方 | Whisper / librosa 默认用功率谱 |
| `ln` + `max(v, eps)` | 简单稳健 | Whisper 用 `log10` + 动态范围裁剪 + 缩放；需完全复刻 |
| 未归一化的 DCT-II | 公式直观 | 生产用 `norm="ortho"`，数值尺度不同 |
| 线性 chirp 相位写成 `f(t)·t` | （疏忽） | 实际扫频速度翻倍、后半段 aliasing；应为 `f0·t + ½·k·t²` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数与 `None` 哨兵 | `def mel_filterbank(..., fmin=0.0, fmax=None)`；`if fmax is None: fmax = sr / 2` | 默认值依赖其他参数时，用 `None` 占位再在函数体内计算 |
| 整除 `//` | `n // 2 + 1`、`(len(signal) - frame_len) // hop` | 向下取整的除法，帧数、bin 数都靠它 |
| 列表推导式 | `[signal[i * hop : i * hop + frame_len] for i in range(n)]` | 一行生成所有帧 |
| 嵌套列表推导式 | `[[math.log(max(v, eps)) for v in frame] for frame in mel_spec]` | 外层遍历帧、内层遍历 mel bin |
| `[[0.0] * half for _ in range(n_mels)]` | 初始化 filterbank | 用推导式建二维列表；⚠️ 不能写 `[[0.0] * half] * n_mels`，那样所有行是同一个列表对象 |
| 切片 | `signal[i * hop : i * hop + frame_len]`、`mel_widths[-6:]` | 负索引从末尾数 |
| 多重赋值 | `left, center, right = bins[m], bins[m + 1], bins[m + 2]` | 一次给三个变量赋值 |
| `enumerate` | `for k, w in enumerate(fb[m])` | 同时拿到下标和权重 |
| 真值判断 | `if w:` | 数值 0.0 为假，非零为真 |
| 生成器表达式 + `sum` | `sum(1 for x in f if x > 0)` | 计数满足条件的元素 |
| `max(..., key=lambda ...)` | `max(range(n_mels), key=lambda m: lm[i][m])` | argmax |
| `round` / `int` | `int(round(h * n_fft / sr))` | 先四舍五入再转整数 |
| f-string 宽度格式 | `f"t={i:3d}  argmax_mel={am:2d}"` | `:3d` 右对齐占 3 位，打印成整齐的表格 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.3 秒）：

```text
=== Step 1: frame a 0.5 s, 2 kHz tone ===
  samples: 4000, frames: 30, frame_len: 256, hop: 128

=== Step 2: Hann window attenuates frame edges ===
  hann(0) = 0.0000   hann(mid) = 1.0000   hann(last) = 0.0000

=== Step 3: STFT of the tone; argmax bin is at 2000 Hz ===
  frames: 30, bins/frame: 129
  peak bin: 64, freq: 2000.0 Hz (expected 2000 Hz)

=== Step 4: mel filterbank, 40 mels, 0-4000 Hz ===
  filterbank shape: 40 x 129
  bin widths (first 6): [1, 1, 2, 2, 1, 2]   (last 6): [10, 11, 10, 11, 12, 12]
  note: low-mel filters are narrow (dense), high-mel filters are wide (sparse).

=== Step 5: chirp 200 Hz -> 4000 Hz; argmax mel per frame ===
  frame -> argmax mel bin:
    t=  0  argmax_mel=11
    t=  2  argmax_mel=20
    t=  4  argmax_mel=26
    t=  6  argmax_mel=30
    t=  8  argmax_mel=35
    t= 10  argmax_mel=38
    t= 12  argmax_mel=39
    t= 14  argmax_mel=36
    t= 16  argmax_mel=33
    t= 18  argmax_mel=28
    t= 20  argmax_mel=23
    t= 22  argmax_mel=15

=== Step 6: MFCC-13 of a single mel frame ===
  MFCC (13 coeffs, mid frame): [-390.284, -96.642, 50.871, -27.78, 22.812, -21.864, 15.223, -12.136, 10.814, -8.813, 5.646, -5.7, 3.93]
  note: coef 0 encodes overall energy; typically dropped downstream.
```

逐段解读：

- **Step 1**：`1 + (4000 − 256) // 128 = 30` 帧。
- **Step 2**：对称 Hann 窗首尾为 0；中点显示 1.0000，实际是 0.99996（偶数长度没有正中的样本）。
- **Step 3**：每帧 `256 // 2 + 1 = 129` 个 bin；2000 Hz / 31.25 Hz = 第 64 个 bin，精确命中。
- **Step 4**：40 个滤波器 × 129 个 bin。宽度是"非零权重个数"：低频 1–2 个、高频 10–12 个，直观体现了 mel 轴在高频的压缩。
- **Step 5**：⚠️ argmax 从 11 升到 39 后又降到 15——**这不是 mel 的特性，而是 `chirp` 的 bug**（3.1）。真实瞬时频率在 `t = 0.2 s`（约第 12 帧）达到 Nyquist 4000 Hz，之后超过 Nyquist 被折叠回低频。修正 chirp 后 argmax 单调上升。如果你按讲义练习 1 "确认与扫频一致"，会发现它并不一致——这正是检验你是否真懂的地方。
- **Step 6**：c0 = −390.28，等于这一帧 40 个 log-mel 值之和（平均约 −9.76）。后面的系数正负交替、幅度逐渐减小，体现了频谱包络的平滑性——这正是只保留前 13 个就够用的原因。

---

## 7. 动手改一改

1. **修 bug**：把 `chirp` 的相位改为 `2π·(f0·t + 0.5·k·t²)`，确认 Step 5 的 argmax mel 单调上升。
2. 把 `apply_filterbank` 换成 `np.asarray(stft_mag) @ np.asarray(fb).T`，用 `np.allclose` 验证与原结果一致，并用 `time.perf_counter()` 比较速度。
3. 给 `mel_filterbank` 加上 Slaney 式面积归一化：每个滤波器乘以 `2 / (hz[m+2] − hz[m])`，观察高频 mel 数值的变化。
4. 实现 `power_to_db(S, ref=max)`：`10·log10(max(S, 1e-10) / ref)`，再把 STFT 改成功率谱 `|X|²`，对比与 `log_transform` 的数值范围。
5. 按讲义练习 2，把 `n_mels` 取 `{40, 80, 128}`、`frame_len` 取 `{128, 256, 512}`（等比例缩小以保持速度），观察哪组组合下修正后的 chirp 轨迹最"细"；检查 `n_mels=128` 时是否出现全零的空滤波器。
6. 实现 delta 特征：`Δc[t] = (c[t+1] − c[t−1]) / 2`，把 MFCC-13 扩成 MFCC-13 + Δ + ΔΔ 共 39 维。

---

## 8. 常见坑

- **瞬时频率 ≠ 相位里的 f**：`sin(2π·f(t)·t)` 在 `f` 随时间变化时，实际频率是 `d(f(t)·t)/dt`。本文件的 chirp 就栽在这里。
- **bin 数写成 `n_fft`**：实信号只有 `n_fft // 2 + 1` 个非冗余 bin；filterbank 列数必须与之匹配。
- **mel 公式 / 归一化不一致**：HTK vs Slaney、有无面积归一化、幅度 vs 功率、`ln` vs `log10` vs dB，任何一项与预训练模型不同都会造成静默的效果下降。
- **短音频返回空帧**：`frame_signal` 遇到长度不足一帧的输入返回 `[]`，后续索引会崩溃。
- **尾部补零**：讲义提醒补零会让尾帧频谱平坦，应 reflect / replicate 补边。
- **二维列表初始化**：`[[0.0] * n] * m` 会让 m 行共享同一个列表，改一处全改；本文件用推导式规避了这个坑。
