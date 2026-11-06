# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 01 节 音频基础知识 — 波形、Sampling、傅里叶变换 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`os`、`struct`、`tempfile`、`wave`），无需 NumPy

---

## 1. 这份代码在考察什么

这份脚本不读任何真实录音，而是**从第一性原理合成信号、手写 DFT**，把讲义里的几个概念变成能打印出来的数字：

1. **波形就是一串 float**：正弦波 `amp·sin(2π·f·i/sr)` 的每个样本是怎么算出来的，样本数为什么是 `int(sr * seconds)`。
2. **16-bit PCM 是怎么存的**：float → int16 → 二进制字节 → WAV 文件，再读回来，量化误差有多大。
3. **DFT 与频率 bin**：`N` 个样本得到 `N` 个复数，第 `k` 个 bin 对应 `k·sr/N` Hz，峰值 bin 就是主频。
4. **Aliasing**：7 kHz 的音在 10 kHz 采样下"变成" 3 kHz；24 kHz 的信号不经低通直接抽到 8 kHz，7 kHz 又"变成" 1 kHz。
5. **数值的诚实性**：输出里的 437.5 Hz、3007.8 Hz 都不是"错"，而是 bin 网格的量化效果。

> 一句话：**用不到 130 行标准库代码，亲手验证"采样率 → Nyquist → aliasing → DFT bin"这条链条**，为下一节的 STFT 和 Mel 打底。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sine(freq_hz, sr, seconds, amp)` | 函数 | 合成纯正弦波 | 波形、采样率、`t = n/sr` |
| `mix(*signals)` | 函数 | 多个信号逐样本求平均 | 叠加原理（傅里叶的"任何信号都是正弦之和"） |
| `write_wav` / `read_wav` | 函数 | 用 `wave` + `struct` 读写 16-bit 单声道 WAV | Bit depth、PCM、量化 |
| `dft(x)` | 函数 | `O(N²)` 手写离散傅里叶变换 | DFT |
| `magnitudes(spectrum)` | 函数 | 复数 → 模长 | 幅度谱 |
| `peak_freq(samples, sr)` | 函数 | 找前半幅度谱的最大 bin，换算成 Hz | bin `k → k·sr/N` |
| `downsample_naive(samples, factor)` | 函数 | 每 `factor` 个样本取 1 个，不滤波 | 错误的降采样 → aliasing |
| `main()` | 演示入口 | 依次跑 6 个步骤并打印 | — |

数据流：`sine`/`mix` 产生样本列表 → （可选）`write_wav`/`read_wav` 往返 → `peak_freq` 内部调用 `dft` → `magnitudes` → 取峰值。

---

## 3. 逐段精讲

### 3.1 合成正弦波与混音

```python
def sine(freq_hz, sr, seconds, amp=0.5):
    n = int(sr * seconds)
    return [amp * math.sin(2.0 * math.pi * freq_hz * i / sr) for i in range(n)]


def mix(*signals):
    length = min(len(s) for s in signals)
    return [sum(s[i] for s in signals) / len(signals) for i in range(length)]
```

- 第 `i` 个样本对应的时间是 `t = i / sr`，代入 `sin(2π·f·t)` 就是连续正弦在该时刻的取值——这就是"采样"的全部含义。
- `amp=0.5` 留了余量：值域 `[-0.5, 0.5]`，写成 int16 时不会碰到 ±1 的边界。
- `mix` 求**平均**而不是求和：三个振幅 0.5 的正弦直接相加最大可达 1.5，超出 `[-1, 1]` 会 clipping；除以信号个数保证不越界。
- `min(len(s) ...)` 以最短的信号为准，防止下标越界。
- ⚠️ `int(sr * seconds)` 依赖浮点乘法：`8000 * 0.064` 恰好是 `512.0`，但 `44100 * 0.35` 得到的是 `15434.999999999998`，`int()` 向零截断后少了一个样本（应为 15435）。生产代码常用 `round()`。

### 3.2 写 WAV：float → int16 → 字节

```python
def write_wav(path, samples, sr):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = b"".join(struct.pack("<h", max(-32768, min(32767, int(s * 32767)))) for s in samples)
        w.writeframes(frames)
```

- `setnchannels(1)` 单声道，`setsampwidth(2)` 每个样本 2 字节（16 bit），`setframerate(sr)` 写入采样率——这三个字段就是 WAV 头里最关键的信息，也是讲义说"先对齐采样率"时要检查的东西。
- `int(s * 32767)`：把 `[-1, 1]` 的 float 放大到 int16 范围；`max(-32768, min(32767, ...))` 是 **clamp**，防止超过 int16 表示范围（真实信号超出就是 clipping）。
- `struct.pack("<h", ...)`：`<` 表示小端序（WAV 规定），`h` 表示有符号 short（2 字节）。
- 输出的 1068 字节 = 44 字节 WAV 头 + 512 样本 × 2 字节。
- ⚠️ `int()` 是向零截断而不是四舍五入，量化误差最大约 1 个 LSB 而不是半个；见 3.3。

### 3.3 读 WAV：字节 → int16 → float

```python
def read_wav(path):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    ints = struct.unpack("<" + "h" * n, raw)
    return [x / 32768.0 for x in ints], sr
```

- `"<" + "h" * n` 动态拼出格式串，一次解出 `n` 个 int16。注意这里假设了单声道、16 bit；立体声时 `readframes(n)` 会返回 `2n` 个样本，格式串就不对了。
- 除以 32768 把 int16 映射回 `[-1, 1)`，与 `soundfile` 等库的约定一致。
- 返回 `(waveform, sr)` 二元组，刻意模仿 `soundfile.read` / `torchaudio.load` 的接口风格。
- ⚠️ 写入乘 32767、读回除 32768，**系数不对称**，再加上 `int()` 截断，导致 Step 2 的往返误差是 `0.00004`。改成写入 `round()`、读写用同一系数后误差约 `1.5e-5`（半个 LSB）。这个误差对 ASR 毫无影响，但它说明"16-bit 量化并非无损"。

### 3.4 手写 DFT 与幅度

```python
def dft(x):
    n = len(x)
    out = []
    for k in range(n):
        re = 0.0
        im = 0.0
        for j in range(n):
            angle = -2.0 * math.pi * k * j / n
            re += x[j] * math.cos(angle)
            im += x[j] * math.sin(angle)
        out.append((re, im))
    return out


def magnitudes(spectrum):
    return [math.sqrt(re * re + im * im) for re, im in spectrum]
```

- 公式：`X[k] = Σⱼ x[j] · e^(−2πi·k·j/N)`，用欧拉公式拆成实部 `Σ x·cos` 和虚部 `Σ x·sin`，避免使用复数类型，读者能看到每一步乘加。
- 外层 `k` 遍历 `N` 个频率，内层 `j` 遍历 `N` 个样本 → **`O(N²)`**。512 点约 26 万次乘加，还能接受；4000 点就要约 2 秒，真实音频（每秒 16000 点）完全不可用。生产中用 `numpy.fft.rfft` / `torch.fft.rfft`（`O(N log N)`）。
- 复数 `(re, im)` 的模长是该频率的振幅，`atan2(im, re)` 是相位；本节只用幅度。

### 3.5 峰值检测：bin → Hz

```python
def peak_freq(samples, sr):
    mags = magnitudes(dft(samples))
    half = len(mags) // 2
    mags = mags[:half]
    k = max(range(len(mags)), key=lambda i: mags[i])
    return k * sr / len(samples), k
```

- **只看前一半**：实信号的 DFT 共轭对称，后半是镜像；前半对应 `0 ~ sr/2`，正好是 Nyquist 以内。
- `max(range(...), key=...)` 是"argmax"的纯 Python 写法：比较的是 `mags[i]`，返回的是下标 `i`。
- `k * sr / len(samples)` 就是讲义里的 `bin k → k·sr/N` Hz。
- 设计取舍：
  - ⚠️ 没有跳过 bin 0（直流分量）。纯正弦没问题，但真实录音的 DC offset 可能让 bin 0 成为"最大峰"。
  - ⚠️ `[:N//2]` 少取了 Nyquist 那个 bin（`rfft` 会返回 `N/2 + 1` 个），在本演示里无影响。
  - ⚠️ 结果被量化在 bin 网格上，精度不超过 `sr/N`；更精确的做法是加窗后对峰值附近三个 bin 做抛物线插值。

### 3.6 Naive 降采样

```python
def downsample_naive(samples, factor):
    return samples[::factor]
```

- 切片 `[::3]` 每 3 个取 1 个，采样率从 24 kHz 变成 8 kHz，Nyquist 从 12 kHz 变成 4 kHz。
- 原信号里的 7 kHz 在新采样率下超过 Nyquist，被折叠到 `8 − 7 = 1 kHz`。这个函数**故意是错的**，用来演示"为什么必须先低通"。正确做法是先用截止频率 ≤ 4 kHz 的低通滤波器，再抽取；或直接用 `torchaudio.transforms.Resample` / `librosa.resample`。

### 3.7 `main()`：六个步骤

```python
    print("=== Step 5: aliasing — 7 kHz tone sampled at 10 kHz ===")
    alias_sr = 10000
    tone = sine(7000.0, alias_sr, 0.0512)
    alias_freq, _ = peak_freq(tone, alias_sr)
    folded = alias_sr - 7000.0
```

- 时长都选得很讲究：`8000 × 0.064 = 512`、`10000 × 0.0512 = 512`、`24000 × 0.032 = 768 → 抽取后 256`，样本数都不大，让 `O(N²)` 的 DFT 在 0.2 秒内跑完。
- `folded = alias_sr - 7000.0` 是"`sr − f`"这个特例公式，只在 `sr/2 < f < sr` 时成立；通用公式是"先对 sr 取模，再关于 sr/2 镜像"。
- `alias_freq, _ = ...` 用 `_` 丢弃不需要的返回值（bin 下标）。
- ⚠️ `tempfile.mkdtemp` 创建的临时目录在脚本结束后**不会被删除**，多跑几次会在 `/tmp` 留下 `audio_fundamentals_*` 目录。演示无妨，正式代码应用 `tempfile.TemporaryDirectory()` 上下文管理器。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用标准库 `wave` + `struct` | 零依赖，看清 WAV 字节层面的结构 | 只支持 PCM WAV；生产用 `soundfile` 或 `torchaudio.load` |
| 手写 `O(N²)` DFT | 每一步乘加都看得见，便于对照公式 | 极慢；生产用 `numpy.fft.rfft` / `torch.fft.rfft` |
| 实部/虚部分开算，不用 `complex` | 对应欧拉公式，降低理解门槛 | 代码略长；Python 内置 `complex` 和 `cmath` 可简化 |
| 样本数取 512 / 256 | 让 `O(N²)` DFT 能秒级跑完 | 频率分辨率只有 15–31 Hz，440 Hz 被报告成 437.5 Hz |
| `mix` 取平均 | 防止叠加后 clipping | 每个分量振幅被压低；生产中用峰值/RMS 归一化 |
| 故意写错的 `downsample_naive` | 让 aliasing 肉眼可见 | 生产中必须用带抗混叠滤波器的重采样器 |
| `int()` 截断、32767/32768 不对称 | 写法简短 | 往返误差约 1 LSB；更严谨的写法是 `round()` + 统一系数 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def sine(freq_hz, sr, seconds, amp=0.5)` | 调用时不传 `amp` 就用 0.5 |
| 列表推导式 | `[amp * math.sin(...) for i in range(n)]` | 一行生成列表 |
| 生成器表达式 | `min(len(s) for s in signals)`、`b"".join(struct.pack(...) for s in samples)` | 不建中间列表，按需产生元素 |
| `*args` 可变参数 | `def mix(*signals)` | 接收任意个位置参数，打包成元组 |
| 元组解包 | `for re, im in spectrum`；`loaded, loaded_sr = read_wav(path)`；`alias_freq, _ = ...` | 一次拿到多个值；`_` 表示"不用的变量" |
| 切片步长 | `samples[::factor]`、`mags[:half]`、`a[:5]` | `[start:stop:step]`，`[::3]` 每 3 个取 1 个 |
| `max(..., key=...)` + `lambda` | `max(range(len(mags)), key=lambda i: mags[i])` | 按 key 比较、返回原元素，相当于 argmax |
| `sorted(..., key=...)` | `sorted(range(len(mags)), key=lambda i: -mags[i])[:3]` | 取负号实现降序，取前 3 个即 top-3 |
| `with` 上下文管理器 | `with wave.open(path, "wb") as w:` | 离开代码块时自动关闭文件，即使中途抛异常 |
| bytes 与 `struct` | `struct.pack("<h", ...)`、`struct.unpack("<" + "h" * n, raw)` | 在 Python 数值与 C 结构的二进制表示之间转换；`<` 小端，`h` int16 |
| `b"".join(...)` | 拼接所有样本的字节 | 比在循环里 `+=` 拼 bytes 高效 |
| f-string 格式符 | `f"{freq:.1f}"`、`f"{diff:.5f}"`、`f"{sr / len(a):.2f}"` | `:.1f` 保留 1 位小数；花括号里可以写表达式 |
| `os.path` / `tempfile` | `os.path.join(tmpdir, "a440.wav")`、`tempfile.mkdtemp(prefix=...)` | 拼路径、建临时目录 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.2 秒）：

```text
=== Step 1: synthesize a 440 Hz sine, 8 kHz, 64 ms ===
  samples: 512
  first 5: [0.0, 0.1694, 0.3187, 0.4304, 0.4911]

=== Step 2: round-trip through a WAV file ===
  wrote /tmp/audio_fundamentals_gq3nyjuc/a440.wav (1068 bytes, sr=8000)
  round-trip max abs error (16-bit quantization): 0.00004

=== Step 3: DFT peak detection on 440 Hz ===
  peak bin k=28, freq=437.5 Hz (expected ~440.0 Hz, bin resolution 15.62 Hz)

=== Step 4: mixed signal (220 + 440 + 880) ===
  top 3 peaks: [218.8, 437.5, 875.0] Hz

=== Step 5: aliasing — 7 kHz tone sampled at 10 kHz ===
  true frequency: 7000.0 Hz (above Nyquist = 5000.0 Hz)
  DFT reports:    3007.8 Hz
  expected alias: 3000.0 Hz  (= sr - f_true)

=== Step 6: proper downsample vs naive decimation ===
  24 kHz 7 kHz tone, decimated to 8 kHz without low-pass:
    peak after decimation: 1000.0 Hz (should be 1000 Hz from folding)
    lesson: always low-pass filter before decimating
```

逐行解读：

- **Step 1**：`8000 × 0.064 = 512` 个样本。第 2 个样本 `0.5·sin(2π·440/8000) = 0.5·sin(0.3456) ≈ 0.1694`。440 Hz 一个周期约 18 个样本，所以前 5 个样本还在第一个波峰的上升段（峰值 0.5）。
- **Step 2**：临时目录名每次随机。1068 字节 = 44 字节头 + 1024 字节数据。误差 `0.00004` 来自 `int()` 截断（≤ 1/32767 ≈ 3.05e-5）加上 32767/32768 系数不对称（≈ 0.5/32768 ≈ 1.5e-5）。
- **Step 3**：分辨率 `8000/512 = 15.625 Hz`（打印成 15.62），440/15.625 = 28.16 → 第 28 个 bin → 437.5 Hz。这是 bin 量化，不是 bug。
- **Step 4**：220、440、880 分别落在 bin 14.08、28.16、56.32 附近，最近的 bin 是 14、28、56 → 218.75（打印 218.8）、437.5、875.0。三个峰都找到了，验证了"信号 = 正弦之和"。
- **Step 5**：Nyquist 5 kHz，7 kHz 被折叠到 3 kHz；分辨率约 19.53 Hz，最近 bin 是 154 → 3007.8 Hz。**真实的 7 kHz 在频谱里完全消失了**——这就是 aliasing 不可逆的原因。
- **Step 6**：抽取后 256 个样本、8 kHz、分辨率 31.25 Hz，1000 Hz 正好是第 32 个 bin，所以精确地报告 1000.0 Hz。如果你是在给 ASR 做 48k→16k 的降采样，这类"凭空出现的低频"就会污染语音频段。

---

## 7. 动手改一改

1. 把 Step 3 的时长改成 `0.1` 秒，确认峰值变成精确的 `440.0 Hz`（bin 44），并解释为什么。
2. 实现 `alias_freq(f, sr)`（先 `f % sr`，再关于 `sr/2` 镜像），对 9 kHz、12 kHz、7 kHz 在 10 kHz 下的情况与 `peak_freq` 对比。
3. 修改 `write_wav` 用 `round()`、`read_wav` 用 `/ 32767.0`，观察 Step 2 的误差从 `4.4e-5` 降到约 `1.5e-5`。
4. 在 `peak_freq` 里跳过 bin 0，然后给 440 Hz 正弦加上 `+0.3` 的直流偏移，对比修改前后的结果。
5. 写一个简单的低通滤波器（例如长度 31 的加窗 sinc FIR，截止 3.5 kHz），在 `downsample_naive` 之前先滤波，看 Step 6 的 1 kHz 假峰是否大幅减弱。
6. （进阶，对应讲义练习 3）用 `dft` 实现 STFT：帧长 400、帧移 160、Hann 窗 `0.5 − 0.5·cos(2πn/(N−1))`，输出一个"帧 × 频率"的矩阵。

---

## 8. 常见坑

- **只看文件扩展名不看采样率**：同样是 `.wav`，可能是 8/16/44.1/48 kHz。读文件时一定要拿到 `sr` 并和模型期望比较。
- **把降采样当成切片**：`x[::3]` 不是 48k→16k 的正确做法，没有低通就会 aliasing，且训练、推理都不报错。
- **忘了 int16 → float 的缩放**：直接把 `struct.unpack` 出来的整数喂模型，数值是几千几万，模型输出全是垃圾。
- **立体声当单声道读**：`read_wav` 假设单声道；立体声 WAV 的样本是 L/R 交错的，需要先按声道拆分再取平均。
- **对 bin 量化"大惊小怪"**：437.5 ≠ 440 不是算法错，是分辨率 `sr/N` 的限制；想要更细就增加 `N`（更长的窗口）或做插值。
- **临时文件不清理**：`tempfile.mkdtemp` 需要手动 `shutil.rmtree`，或改用 `with tempfile.TemporaryDirectory() as d:`。
