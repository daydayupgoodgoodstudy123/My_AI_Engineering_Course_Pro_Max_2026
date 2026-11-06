# 测验 · 傅里叶变换（The Fourier Transform）

> **阶段 01 · 数学基础 · 第 20 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/fourier.py](../code/fourier.py) ｜ 代码讲解：[code/fourier.讲解.md](../code/fourier.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | DFT 定义 | `X[k] = Σₙ x[n]·e^(−2πi·k·n/N)`：信号与第 k 个"旋转相量"求相关；本质是一次**换基**，N 个采样 ↔ N 个复系数 |
| 2 | 系数的含义 | `X[0]` 是直流分量（= 所有采样之和 = N·均值）；bin k 对应频率 `f_k = k·fs/N`；`|X[k]|` 是幅度，`atan2(imag, real)` 是相位 |
| 3 | 实信号的共轭对称 | 实值输入满足 `X[N−k] = conj(X[k])`，后半段是前半段的镜像，所以只需看前 `N/2 + 1` 个 bin |
| 4 | IDFT 与完美重建 | 指数取正号、再乘 `1/N` 即可无损还原；时域与频域是同一信息的两套坐标 |
| 5 | FFT（Cooley-Tukey） | 按奇偶下标拆分、递归、用 twiddle 因子 `e^(−2πik/N)` 做蝶形合并：`X[k] = E[k] + W·O[k]`，`X[k+N/2] = E[k] − W·O[k]`；`O(N²) → O(N log N)` |
| 6 | 分辨率、Nyquist、混叠 | `Δf = fs/N`，`f_max = fs/2`；高于 Nyquist 的频率会"折叠"成低频（100 Hz 采 90 Hz → 看起来是 10 Hz）；补零不提高真实分辨率，只有观测时长 `T = N/fs` 决定 |
| 7 | 卷积定理 | 时域卷积 = 频域逐点相乘：`x * h = IFFT(FFT(x)·FFT(h))`；DFT 天然算的是**循环卷积**，补零到 `N+M−1` 才得到线性卷积 |
| 8 | 频谱泄漏与加窗 | DFT 假设信号周期重复，非整周期会在边界产生跳变 → 能量泄漏到邻近 bin；Hann/Hamming 窗以"主瓣变宽"换"旁瓣降低" |
| 9 | Parseval 定理 | `Σ|x[n]|² = (1/N)·Σ|X[k]|²`，能量在两个域中守恒 |
| 10 | 与 AI 的连接 | 正弦位置编码 = 几何间隔的多频率特征（点积只依赖相对距离）；CNN 卷积 ↔ 频域乘法；FNet 用 FFT 替代 attention；语音模型吃 STFT/mel spectrogram |

### 核心技能（能动手做到）

- [ ] 从零实现 `dft` / `idft`，并手算 `[1, 2, 3, 4]` 的 DFT（`[10, −2+2i, −2, −2−2i]`）来验证
- [ ] 实现递归 radix-2 FFT，在随机信号上与 O(N²) DFT 对比，最大误差 < 1e-10
- [ ] 给定 `fs` 和 `N`，把 bin 下标换算成 Hz，从幅度谱中找出主频，并解释为什么纯正弦的峰值是 `A·N/2`
- [ ] 用 FFT 实现线性卷积，与双重循环的直接卷积逐点比对；能说清为什么必须补零到 `N+M−1`
- [ ] 对"频率落在两个 bin 之间"的正弦分别加矩形窗、Hann 窗、Hamming 窗，比较泄漏程度
- [ ] 数值验证 Parseval 定理，以及正弦位置编码"点积只依赖 |p₁−p₂|"
- [ ] 用 NumPy/SciPy 写出等价代码：`np.fft.fft`、`np.fft.fftfreq`、`scipy.signal.stft`、`scipy.signal.fftconvolve`

---

## 二、基础自测（选择题）

**Q1.** 以 `fs = 1000 Hz` 采集了 `N = 500` 个采样点。DFT 的频率分辨率和可表示的最高频率分别是：

- A. 0.5 Hz，1000 Hz
- B. 2 Hz，500 Hz
- C. 2 Hz，1000 Hz
- D. 500 Hz，2 Hz

**Q2.** 一个 **实值** 信号长度 N = 8，已知 `X[3] = 2 − 3i`，那么 `X[5]` 等于：

- A. `2 − 3i`
- B. `2 + 3i`
- C. `−2 + 3i`
- D. 0，因为 5 > N/2 的系数没有意义

**Q3.** 一个长度为 8、均值为 3 的实值信号，它的 `X[0]` 是：

- A. 3
- B. 24
- C. 0.375
- D. 取决于信号中其他频率成分的相位

**Q4.** 用 100 Hz 的采样率去采一个 90 Hz 的正弦波，再做 DFT，幅度谱的峰值会出现在：

- A. 90 Hz
- B. 10 Hz
- C. 50 Hz
- D. 不会出现峰值，因为 90 Hz 超出了范围

**Q5.** 你需要区分信号里 10 Hz 和 10.5 Hz 两个成分。目前以 128 Hz 采样 1 秒。下面哪种做法**真正**有效？

- A. 把这 1 秒数据补零到 512 点再做 FFT
- B. 采集更长时间的数据（至少 2 秒）
- C. 采样率提高到 256 Hz，仍然只采 1 秒
- D. 改用 Blackman 窗

**Q6.** 用 FFT 计算长度 N = 5 和 M = 3 两个序列的**线性**卷积，为了不发生循环混叠，至少要补零到多少点？

- A. 5
- B. 7
- C. 8
- D. 15

**Q7.** 关于窗函数，下列说法正确的是：

- A. 加窗能提高频率分辨率，让两个很近的频率更容易分开
- B. 加窗以"主瓣变宽"为代价，换来旁瓣（泄漏）大幅降低
- C. 即使信号在 N 个点内恰好是整数个周期，也必须加窗
- D. 加 Hann 窗后，峰值的幅度会变大

**Q8.** 原始 Transformer 的正弦位置编码中，`PE(p)·PE(q)` 只依赖于 `|p − q|`、与绝对位置无关。最直接的数学原因是：

- A. sin 和 cos 的取值都在 [−1, 1] 之间
- B. `sin(a)·sin(b) + cos(a)·cos(b) = cos(a − b)`
- C. 各维度的频率按几何级数排列
- D. `d_model` 是偶数

---

## 三、动手 / 代码题

**Q9.** 预测下面代码的输出（注意 `Complex.__repr__` 的格式规则），并解释：为什么 `X[1]` 和 `X[3]` 互为共轭？为什么 `X[2]` 打印出来没有虚部？

```python
from fourier import dft
print(dft([1, 2, 3, 4]))
```

相关源码：

```python
    def __repr__(self):
        if abs(self.imag) < 1e-12:
            return f"{self.real:.6f}"
        sign = "+" if self.imag >= 0 else "-"
        return f"{self.real:.6f} {sign} {abs(self.imag):.6f}i"
```

**Q10.** `convolve_fft` 里有这样一段：

```python
    N = len(x) + len(h) - 1
    padded_N = 1
    while padded_N < N:
        padded_N *= 2
```

某同学觉得"补零浪费算力"，把它改成只补到 `max(len(x), len(h))`。对 `x = [1, 2, 3, 4]`、`h = [1, 1, 1]`：

1. 原版 `convolve_fft` 的输出是什么？`padded_N` 是多少？
2. 修改后（h 补成 `[1, 1, 1, 0]`，长度 4）得到什么？为什么错了？
3. `while padded_N < N: padded_N *= 2` 补到 2 的幂，是数学上必须的吗？

**Q11.** 本文件没有实现 STFT（短时傅里叶变换）。请只用 `fourier.py` 中已有的 `hann_window`、`apply_window`、`fft`、`magnitude_spectrum` 写一个函数：

```python
def stft(signal, window_size, hop):
    """返回一个列表，每个元素是一帧的幅度谱（只保留前 window_size//2 + 1 个 bin）"""
```

并用"前 128 点是 5 Hz 正弦、后 128 点是 20 Hz 正弦、`fs = 64`"的信号测试 `window_size=64, hop=32`：一共有几帧？每帧的主频是多少？

**Q12.** 阅读 `fft` 的实现，回答两个问题：

```python
def fft(x):
    N = len(x)
    if N <= 1:
        return [x[0] if isinstance(x[0], Complex) else Complex(x[0])]
    if N % 2 != 0:
        return dft(x)

    even = fft([x[i] for i in range(0, N, 2)])
    odd = fft([x[i] for i in range(1, N, 2)])

    result = [Complex(0)] * N
    for k in range(N // 2):
        angle = -2 * math.pi * k / N
        twiddle = euler(angle)
        t = twiddle * odd[k]
        result[k] = even[k] + t
        result[k + N // 2] = even[k] - t
    return result
```

1. `[Complex(0)] * N` 会让 N 个元素指向**同一个对象**。这里是不是 bug？什么情况下会变成 bug？
2. 讲义说"FFT 要求长度是 2 的幂"，但这份代码对 N = 12 也能给出正确结果。它是怎么做到的？代价是什么？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 DFT？FFT 为什么能把复杂度从 O(N²) 降到 O(N log N)？

**Q14.**（原理深挖）解释卷积定理。既然 FFT 卷积是 O(N log N)，为什么主流 CNN 的 3×3 卷积大多不用 FFT 实现？什么场景下 FFT 卷积更划算？

**Q15.**（结合大模型）Transformer 的正弦位置编码为什么要用一组几何间隔的频率？它如何让模型感知相对位置？和 RoPE 有什么联系？

**Q16.**（工程实践）语音模型（如 Whisper）的输入不是原始波形而是 log-mel spectrogram。请描述从波形到 spectrogram 的流程，以及窗长、hop、窗函数的取舍。

**Q17.**（追问型）"补零可以提高频率分辨率"对吗？采样率和采样时长分别决定什么？混叠在深度学习里会以什么形式出现？

---

## 五、参考答案与解析

### Q1 — 答案：B

`Δf = fs/N = 1000/500 = 2 Hz`；`f_max = fs/2 = 500 Hz`（Nyquist）。A 把 N/fs（观测时长 0.5 s 的倒数关系）弄反了；C 忘了 Nyquist 是采样率的一半；D 把两个量对调。

### Q2 — 答案：B

实值信号满足 `X[N−k] = conj(X[k])`，`X[8−3] = X[5] = conj(2−3i) = 2+3i`。D 错在：k > N/2 的系数对应"负频率"，对实信号来说是冗余的镜像，但并不是 0。

### Q3 — 答案：B

`X[0] = Σ x[n]·e⁰ = Σ x[n] = N·mean = 8 × 3 = 24`。DC 分量正比于均值而不是等于均值，所以 A 错；其他频率成分在 k = 0 处的贡献都是 0（整周期正弦求和为 0），与相位无关，所以 D 错。用本节代码对 `3 + sin(2π·2n/8)` 做 FFT，幅度谱为 `[24, 0, 4, 0, 0, 0, 4, 0]`，正好印证。

### Q4 — 答案：B

90 Hz 高于 Nyquist（50 Hz），会被折叠到 `100 − 90 = 10 Hz`。采样点 `sin(2π·90n/100) = −sin(2π·10n/100)`，与 10 Hz 正弦只差一个相位翻转，幅度谱完全一样。对 100 点做 DFT，峰值确实落在 k = 10。这就是为什么 ADC 前面必须有抗混叠滤波器——采样之后无法再区分。

### Q5 — 答案：B

真实分辨率只取决于观测时长：`Δf = fs/N = 1/T`。要分开相差 0.5 Hz 的两个成分，需要 `T ≥ 1/0.5 = 2 s`。

- A：补零只是在已有频谱上插值，曲线更平滑，但信息量没变。
- C：fs 翻倍、N 也翻倍，`Δf = 256/256 = 1 Hz` 不变，只是 Nyquist 变高了。
- D：Blackman 窗主瓣最宽，反而更难分开相邻峰。

### Q6 — 答案：B

线性卷积的长度是 `N + M − 1 = 7`，补到 ≥ 7 就不会有循环卷积的"回绕"。C（8）是本节代码为了 radix-2 FFT 取的下一个 2 的幂，是实现上的方便而非数学上的最低要求；A 会发生回绕；D 是直接卷积的乘法次数 `N·M`。

### Q7 — 答案：B

窗函数让信号两端平滑衰减到 0，消除边界跳变，从而压低旁瓣；代价是主瓣变宽、频率分辨率略降（所以 A 错）。如果信号在窗内恰好是整数个周期，矩形窗（不加窗）没有泄漏、主瓣最窄，是最佳选择（C 错）。加窗会让峰值变小而不是变大：本节代码中 7.5 Hz 信号的峰值从无窗的约 20.9 降到 Hann 的约 13.4（D 错）。

### Q8 — 答案：B

把同一频率 ω 的一对维度 `(sin(ωp), cos(ωp))` 与 `(sin(ωq), cos(ωq))` 做点积：`sin(ωp)sin(ωq) + cos(ωp)cos(ωq) = cos(ω(p−q))`。所以 `PE(p)·PE(q) = Σᵢ cos(ωᵢ(p−q))`，只依赖距离（且因 cos 是偶函数，只依赖 |p−q|）。A、C、D 都是真实属性，但不是这一结论的原因。本节代码中 (0,1)、(1,2) 的点积都是 7.4852，(0,4)、(3,7) 都是 5.5597。

### Q9 — 参考答案

输出：

```
[10.000000, -2.000000 + 2.000000i, -2.000000, -2.000000 - 2.000000i]
```

- 手算：`X[0] = 1+2+3+4 = 10`；`X[1] = 1 + 2(−i) + 3(−1) + 4(i) = −2 + 2i`；`X[2] = 1 − 2 + 3 − 4 = −2`；`X[3] = conj(X[1]) = −2 − 2i`。
- 共轭对称：输入是实数，`X[N−k] = conj(X[k])`，N = 4 时 `X[3] = conj(X[1])`。
- `X[2]` 是 Nyquist bin（k = N/2），旋转因子 `e^(−iπn) = (−1)ⁿ` 是实数，理论虚部为 0；实际计算会留下 `1e-16` 量级的浮点噪声，`__repr__` 用 `abs(self.imag) < 1e-12` 把它当作 0 隐藏，只打印实部。
- 列表打印时，Python 对每个元素调用 `__repr__`，所以看到的是这种格式而不是 `<Complex object at ...>`。

### Q10 — 参考答案

1. `N = 4 + 3 − 1 = 6`，`padded_N` 从 1 翻倍到 8。输出 `[1.0, 3.0, 6.0, 9.0, 7.0, 4.0]`（与 `convolve_direct` 一致，浮点误差在 1e-15 量级）。
2. 只补到 4 时，FFT 相乘得到的是长度为 4 的**循环卷积**：线性结果中下标 4、5 的值（7、4）会"回绕"加到下标 0、1 上：

```
线性:  [1, 3, 6, 9, 7, 4]
循环:  [1+7, 3+4, 6, 9] = [8, 7, 6, 9]
```

原因是 DFT 默认信号以 N 为周期无限重复，卷积窗口从末尾滑出后会从开头"绕回来"。补零到 ≥ N+M−1，相当于在每个周期之间留出足够的空白，回绕的部分只会和 0 相乘。
3. 不是。数学上只需 `≥ N+M−1`（这里是 6）。补到 2 的幂是为了让本文件的 radix-2 递归每一层都能对半拆分，避免退回 O(N²) 的 `dft`。NumPy/SciPy 的 FFT 支持任意长度，常用"凑成 2、3、5 的乘积"之类的快速长度。

### Q11 — 参考答案

```python
import math
from fourier import hann_window, apply_window, fft, magnitude_spectrum

def stft(signal, window_size, hop):
    win = hann_window(window_size)                 # 窗只需算一次
    frames = []
    for start in range(0, len(signal) - window_size + 1, hop):
        seg = apply_window(signal[start:start + window_size], win)
        X = fft(seg)
        frames.append(magnitude_spectrum(X)[:window_size // 2 + 1])  # 实信号只留前半
    return frames

fs = 64
sig = [math.sin(2 * math.pi * 5 * n / fs) for n in range(128)] + \
      [math.sin(2 * math.pi * 20 * n / fs) for n in range(128)]
frames = stft(sig, 64, 32)
print(len(frames), len(frames[0]))          # 7 33
for i, f in enumerate(frames):
    k = max(range(len(f)), key=lambda j: f[j])
    print(i, k * fs / 64, round(f[k], 3))
```

实际输出：

```
7 33
0 5.0 15.748
1 5.0 15.748
2 5.0 15.748
3 5.0 8.127
4 20.0 15.75
5 20.0 15.75
6 20.0 15.75
```

- 帧数 = `(256 − 64) / 32 + 1 = 7`；每帧 `64/2 + 1 = 33` 个 bin，分辨率 `64/64 = 1 Hz`。
- 第 3 帧（采样 96–159）横跨两段，5 Hz 和 20 Hz 各占一半，所以峰值只有约 8.1——这正是 spectrogram 的价值：**单次 FFT 只告诉你"有哪些频率"，STFT 还告诉你"什么时候出现"**。
- 峰值约 15.75 ≈ `N/4 = 16`：Hann 窗的平均值约 0.5，把纯正弦峰值从 `N/2 = 32` 压到约一半。
- 生产中直接用 `scipy.signal.stft(signal, fs=..., nperseg=...)` 或 `torch.stft`。

### Q12 — 参考答案

1. **不是 bug**。`[Complex(0)] * N` 确实让 N 个槽位共享同一个对象，但循环里做的是 `result[k] = ...`——把槽位**重新绑定**到新对象（`even[k] + t` 返回新的 `Complex`），从不原地修改共享对象。而且 `k` 和 `k + N//2` 恰好覆盖了 0..N−1 的每个下标，最终不会残留共享对象。如果改成原地修改，比如 `result[k].real += ...`，就会同时改动所有槽位，变成经典的"列表乘法共享引用"bug。更稳妥的写法是 `[None] * N` 或列表推导 `[Complex(0) for _ in range(N)]`。
2. 递归中只要遇到奇数长度就退回 O(N²) 的 `dft`。N = 12 → 拆成两个 6 → 再拆成 3 → 3 是奇数，走 `dft`。每一层的 twiddle 合并公式对任意偶数 N 都成立，所以结果正确（实测与 DFT 的最大误差约 1e-14）。代价是：奇数因子越大越慢，N 为质数时直接退化为 O(N²)。这也说明讲义里"FFT 要求 2 的幂"严格来说是指 radix-2 版本；工业库（FFTW、pocketfft）用混合基数、Bluestein 等算法支持任意长度。

### Q13 — 参考回答要点

- **定义**：N 点 DFT 把序列投影到 N 个复正弦基 `e^(2πikn/N)` 上，`X[k]` 是信号与频率 k 的相关程度；这组基两两正交，所以 DFT 是可逆的换基（`x = (1/N)·Σ X[k]·e^(+2πikn/N)`）。
- **为什么快**：Cooley-Tukey 利用旋转因子的周期性和对称性。把 x 拆成偶数项 E、奇数项 O 两个 N/2 点 DFT，然后用 `X[k] = E[k] + Wᵏ·O[k]`、`X[k+N/2] = E[k] − Wᵏ·O[k]` 合并——一次复数乘法同时产出两个输出（蝶形运算）。每层 O(N)，共 log₂N 层，总计 O(N log N)。
- **量级**：N = 1024 时，N² ≈ 1.05M，N·log₂N ≈ 1 万，约 100 倍；N = 10⁶ 时是 10¹² 对 2×10⁷。
- **加分点**：能写出递归版本并指出可以改成原地迭代（bit-reversal 重排）以减少内存分配；知道实数输入可用 rfft 省一半计算；知道 GPU 上有 cuFFT。
- **常见误区**：以为 FFT 是"近似"的 DFT——两者结果在数学上完全相同，差别只在浮点误差。

### Q14 — 参考回答要点

- **卷积定理**：`DFT(x ⊛ h) = DFT(x)·DFT(h)`。时域卷积 O(N·M)，频域：两次 FFT + 一次逐点乘 + 一次 IFFT，O(N log N)。注意 DFT 对应循环卷积，要得到线性卷积需补零到 `N+M−1`。
- **为什么 CNN 很少用**：
  - 3×3 核时 M 很小，直接卷积（或 im2col + GEMM）每个输出只要 9 次乘加；FFT 要把小核补零到和特征图一样大，再做复数运算，常数开销反而更大；
  - 带 stride、dilation、分组卷积时 FFT 不再直接适用；
  - 小核还有 Winograd 等专门的快速算法。cuDNN 会根据形状在 GEMM、Winograd、FFT 等算法中自动选择。
- **FFT 更划算的场景**：大卷积核或全局卷积（核长接近序列长度）、长序列的一维滤波、需要"全局感受野"的长卷积类序列模型；还有 FNet 这类直接用 FFT 做 token mixing（O(N log N)，无可学习参数）的结构。
- **加分点**：提到"频域乘法 ↔ 时域循环卷积"的对偶关系（时域逐点乘 = 频域循环卷积 / N）。

### Q15 — 参考回答要点

- **公式**：`PE(pos, 2i) = sin(pos / 10000^(2i/d))`，`PE(pos, 2i+1) = cos(pos / 10000^(2i/d))`，频率 `ωᵢ = 10000^(−2i/d)` 从 1 几何递减到约 1/10000。
- **为什么用多个几何间隔的频率**：高频维度变化快，能区分相邻位置（精细刻度）；低频维度变化慢，能编码长距离（粗刻度）——类似"秒针 + 分针 + 时针"。组合在一起，每个位置都有独特的"频谱指纹"，且数值有界在 [−1, 1]。本节代码 d_model = 16 时，波长从约 6.3 增长到约 19869。
- **相对位置**：对每个频率，`(sin(ω(p+k)), cos(ω(p+k)))` 等于 `(sin ωp, cos ωp)` 乘以一个只依赖 k 的 2×2 旋转矩阵——平移 k 是一个线性变换，所以模型可以学会"关注相对偏移 k"。并且 `PE(p)·PE(q) = Σ cos(ωᵢ(p−q))` 只依赖距离。
- **与 RoPE 的联系**：RoPE 用同样的频率表 `θᵢ = 10000^(−2i/d)`，但不是把编码**加**到 embedding 上，而是把 q、k 的每对维度按 `pos·θᵢ` **旋转**，使 `q_m·k_n` 只依赖 `m−n`，相对位置信息直接进入 attention 分数。
- **常见误区**：认为正弦编码的点积"随距离单调下降"——实际上它总体衰减但伴随振荡，并非严格单调。例如 d_model = 16 时，距离 3 的点积约 5.54，距离 4 反而约 5.56，距离 6 又回升到约 6.44。

### Q16 — 参考回答要点

- **流程**：
  1. 重采样到固定采样率；
  2. 分帧：选窗长（如 25 ms）和 hop（如 10 ms），相邻帧有重叠；
  3. 每帧乘窗函数（Hann/Hamming），抑制帧边界跳变造成的泄漏；
  4. 每帧做 FFT，取幅度或功率谱，只保留前 `N/2+1` 个 bin；
  5. 用 mel 滤波器组把线性频率映射到更符合人耳感知的 mel 刻度；
  6. 取对数（压缩动态范围）并归一化，得到 `(n_mels, n_frames)` 的二维"图像"。
  Whisper 论文中：16 kHz 采样、25 ms 窗、10 ms 步长、80 维 log-mel（large-v3 改为 128 维）。
- **取舍**：
  - 窗长越长 → 频率分辨率越高（`Δf = fs/N`）但时间分辨率越差，这是时频不确定性的直接体现；
  - hop 越小 → 时间轴越密，但帧数和计算量越大，相邻帧冗余越多；
  - 窗函数：Hann 通用，Hamming 在语音中常用；旁瓣越低，主瓣越宽。
- **加分点**：提到采样率决定 Nyquist（16 kHz → 8 kHz 上限，覆盖语音主要频段）；知道 spectrogram 丢掉了相位，所以 TTS 需要 vocoder 来还原波形。

### Q17 — 参考回答要点

- **补零不提高真实分辨率**：补零只是在已有频谱上做更密的插值，看起来更平滑，但无法分辨原始数据中没有的细节。真实分辨率 `Δf = 1/T`，T 是观测时长 `N/fs`。补零的正当用途：凑成快速 FFT 长度、做线性卷积防回绕、让峰值位置的读数更精细。
- **采样率 vs 时长**：采样率 fs 决定**能看到多高的频率**（`fs/2`）；时长 T 决定**能分辨多近的频率**（`1/T`）。在固定时长下提高采样率并不会提高分辨率。
- **混叠在深度学习中**：CNN 里 stride 2 的卷积或池化本质是下采样，如果下采样前不做低通滤波，高频纹理会折叠成低频伪影，导致输出对输入的微小平移很敏感。缓解办法是先模糊（低通）再下采样，即讲义提到的 anti-aliased pooling。
- **常见误区**：认为"采样率越高越好"——超出任务需要的采样率只会增加计算和存储；也有人误以为混叠能在采样后靠滤波去除，实际上必须在采样之前完成。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 19 人工智能的复数](../../19-complex-numbers/docs/zh.md)：欧拉公式 `e^(iθ) = cosθ + i·sinθ`、复数乘法 = 旋转与缩放，是读懂 DFT 公式的前提。
- [阶段 01 · 01 线性代数直觉](../../01-linear-algebra-intuition/docs/zh.md)：点积 = 相关程度、正交基与换基——DFT 就是投影到一组正交复正弦基上。
- [阶段 01 · 03 矩阵变换](../../03-matrix-transformations/docs/zh.md)：DFT 可以写成一个 N×N 的矩阵乘法，FFT 是这个矩阵的快速分解。

### 本节被哪些后续内容用到
- [阶段 04 · 02 从零实现卷积](../../../04-computer-vision/02-convolutions-from-scratch/docs/zh.md)：卷积的直接实现，可与本节的卷积定理对照。
- [阶段 06 · 01 音频基础知识](../../../06-speech-and-audio/01-audio-fundamentals/docs/zh.md)：采样、Nyquist、傅里叶变换在音频中的应用。
- [阶段 06 · 02 频谱图、Mel 刻度与音频 Features](../../../06-speech-and-audio/02-spectrograms-mel-features/docs/zh.md)：STFT、mel 滤波器组、MFCC 的完整流程。
- [阶段 07 · 04 位置编码](../../../07-transformers-deep-dive/04-positional-encoding/docs/zh.md)：正弦编码、RoPE、ALiBi，频率分解思想的直接应用。
- [阶段 07 · 10 音频 Transformers — Whisper 架构](../../../07-transformers-deep-dive/10-audio-transformers-whisper/docs/zh.md)：以 log-mel spectrogram 为输入的 encoder-decoder。
- [阶段 02 · 15 时间序列基础知识](../../../02-ml-fundamentals/15-time-series/docs/zh.md)：周期性、季节性分析可以借助频谱找主周期。

### 延伸关键词
`rFFT` · `STFT / spectrogram` · `mel 滤波器组 / MFCC` · `Welch 功率谱估计` · `Blackman 窗` · `bit-reversal 迭代 FFT` · `Bluestein 算法` · `Winograd 卷积` · `FNet` · `RoPE` · `anti-aliased pooling（BlurPool）` · `奈奎斯特-香农采样定理`
