# 代码讲解 · fourier.py

> **所属小节**：阶段 01 · 数学基础 · 第 20 节 傅里叶变换 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在小节根目录执行 `python code/fourier.py`（这样才能把提示词写到 `outputs/prompt-spectral-analyzer.md`；在其他目录运行也能跑完所有演示，只是会提示写文件失败） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy

---

## 1. 这份代码在考察什么

这份文件用不到 600 行纯 Python，把讲义里的傅里叶变换"从定义到应用"走了一遍：

1. **DFT 的定义就是一个双重循环**：每个 `X[k]` 都是信号与一个旋转相量 `e^(−2πikn/N)` 的相关程度，O(N²)。
2. **FFT 是同一个结果的快速算法**：奇偶拆分 + 递归 + twiddle 因子蝶形合并，O(N log N)，并且用演示证明它和 DFT 的结果只差浮点误差。
3. **频域能做什么**：读出主频和幅度、无损重建、卷积定理（FFT 卷积 = 直接卷积）、加窗抑制泄漏、Parseval 能量守恒。
4. **和 AI 的连接**：Transformer 正弦位置编码就是一组几何间隔的频率，点积只依赖位置差。
5. **复数运算的底层**：自己写一个 `Complex` 类，看清复数乘法 `(a+bi)(c+di)` 是怎么展开的。

> 一句话：**先把 DFT/FFT/卷积定理亲手实现一遍，再用 `np.fft` 一行搞定**——面试官问"FFT 为什么快""卷积为什么能在频域做"时，你脑子里有一份可运行的代码。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Complex` | 类 | 复数的加、减、乘、模、相位、共轭、打印 | 复数代数（第 19 节） |
| `euler(theta)` | 函数 | 返回 `cosθ + i·sinθ` | 欧拉公式 |
| `dft` / `idft` | 函数 | 按定义计算正/逆 DFT，O(N²) | DFT 定义、完美重建 |
| `fft` / `ifft` | 函数 | 递归 Cooley-Tukey FFT；用"共轭技巧"复用 FFT 做逆变换 | FFT、蝶形运算 |
| `power_spectrum` / `magnitude_spectrum` / `spectral_analysis` | 函数 | 求功率谱、幅度谱、bin→Hz 换算 | 频谱分析、分辨率 |
| `hann_window` / `hamming_window` / `apply_window` | 函数 | 生成窗函数并逐点相乘 | 频谱泄漏、加窗 |
| `convolve_direct` / `convolve_fft` | 函数 | 直接线性卷积 vs 补零 + FFT 卷积 | 卷积定理、循环 vs 线性卷积 |
| `generate_signal` / `positional_encoding` | 函数 | 生成多正弦叠加信号；生成正弦位置编码 | 信号合成、Transformer PE |
| `demo_*`（9 个） | 演示函数 | 每个对应讲义的一个知识点，打印表格 | — |
| `write_prompt_output` | 函数 | 把"频谱分析专家"提示词写到 `outputs/` | Ship It |
| `print_summary` | 函数 | 打印 8 条总结 | — |

数据流：`generate_signal` 造信号 → `dft`/`fft` 变到频域（内部依赖 `euler` 和 `Complex` 运算）→ `magnitude_spectrum` 等读结果；`convolve_fft` 依赖 `fft` + `ifft`，`ifft` 又复用 `fft`。

---

## 3. 逐段精讲

### 3.1 `Complex`：能和普通数字混算的复数类

```python
class Complex:
    def __init__(self, real=0.0, imag=0.0):
        self.real = float(real)
        self.imag = float(imag)

    def __add__(self, other):
        if isinstance(other, (int, float)):
            return Complex(self.real + other, self.imag)
        return Complex(self.real + other.real, self.imag + other.imag)

    def __radd__(self, other):
        return self.__add__(other)
    # ...
    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return Complex(self.real * other, self.imag * other)
        r = self.real * other.real - self.imag * other.imag
        i = self.real * other.imag + self.imag * other.real
        return Complex(r, i)
```

- `__init__` 带默认参数，所以 `Complex(3)` 就是实数 3（虚部 0）；`float(...)` 统一转成浮点，避免整数除法之类的意外。
- `isinstance(other, (int, float))` 用**元组**一次判断多种类型，让 `Complex + 1.5` 也能工作。
- `__radd__` / `__rmul__` 是**反射运算符**：`2 * z` 时 Python 先试 `int.__mul__(2, z)`，失败后才调用 `z.__rmul__(2)`。有了它们，`sum(...)` 和 `2 * z` 都能用。
- 乘法就是把 `(a+bi)(c+di)` 展开：实部 `ac − bd`，虚部 `ad + bc`。DFT 中 99% 的计算都落在这一行。
- ⚠️ 只实现了 `__sub__` 没有 `__rsub__`，所以 `1 - z` 会报错；也没有除法，`idft` 只好手动写 `Complex(total.real / N, total.imag / N)`。

```python
    def phase(self):
        return math.atan2(self.imag, self.real)

    def __repr__(self):
        if abs(self.imag) < 1e-12:
            return f"{self.real:.6f}"
        sign = "+" if self.imag >= 0 else "-"
        return f"{self.real:.6f} {sign} {abs(self.imag):.6f}i"
```

- `atan2(y, x)` 而不是 `atan(y/x)`：能正确区分四个象限，且 x = 0 时不会除零——这就是讲义里相位谱的公式。
- `__repr__` 把 `1e-12` 以下的虚部视为浮点噪声、只打印实部，所以 `dft([1,2,3,4])` 的 `X[2]` 会显示成 `-2.000000`。

### 3.2 `dft`：定义的逐字翻译

```python
def euler(theta):
    return Complex(math.cos(theta), math.sin(theta))


def dft(x):
    N = len(x)
    result = []
    for k in range(N):
        total = Complex(0, 0)
        for n in range(N):
            angle = -2 * math.pi * k * n / N
            xn = x[n] if isinstance(x[n], Complex) else Complex(x[n])
            total = total + xn * euler(angle)
        result.append(total)
    return result
```

- 对应公式 `X[k] = Σₙ x[n]·e^(−2πikn/N)`。外层循环 k 选"探测频率"，内层循环 n 把信号与该频率的相量逐点相乘再累加——本质是**相关（点积）**：信号里有这个频率，累加就会"同相叠加"变大；没有就会互相抵消接近 0。
- `euler(angle)` 用欧拉公式 `e^(iθ) = cosθ + i·sinθ` 生成单位圆上的点。
- `xn = x[n] if ... else Complex(x[n])` 是**条件表达式**，让 `dft` 同时接受实数列表和 `Complex` 列表（FFT 递归时传进来的可能是后者）。
- 复杂度 O(N²)：N 个输出 × 每个 N 次乘加。

### 3.3 `idft`：符号取反 + 除以 N

```python
def idft(X):
    N = len(X)
    result = []
    for n in range(N):
        total = Complex(0, 0)
        for k in range(N):
            angle = 2 * math.pi * k * n / N
            xk = X[k] if isinstance(X[k], Complex) else Complex(X[k])
            total = total + xk * euler(angle)
        result.append(Complex(total.real / N, total.imag / N))
    return result
```

与 `dft` 只差两处：`angle` 前面是 `+2π`，最后除以 N。这正是讲义强调的"DFT 是一次换基，逆变换就是换回来"。⚠️ 演示里实际用的是更快的 `ifft`，`idft` 保留下来是为了对照公式。

### 3.4 `fft`：递归 Cooley-Tukey（本文件的核心）

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

逐行理解：

| 代码 | 含义 |
|------|------|
| `if N <= 1` | 递归终止：1 个点的 DFT 就是它自己 |
| `if N % 2 != 0: return dft(x)` | 奇数长度没法对半拆，退回 O(N²) 的定义法 |
| `range(0, N, 2)` / `range(1, N, 2)` | 步长为 2 的 `range`，分别取偶数、奇数下标 |
| `twiddle = euler(-2πk/N)` | twiddle 因子 `Wᵏ = e^(−2πik/N)` |
| `result[k] = E + t`，`result[k+N/2] = E − t` | **蝶形运算**：一次复数乘法 `t` 同时产出两个输出 |

- **为什么正确**：把求和拆成偶数项和奇数项，`X[k] = E[k] + Wᵏ·O[k]`；又因为 `W^(k+N/2) = −Wᵏ`，且 E、O 以 N/2 为周期，所以 `X[k+N/2] = E[k] − Wᵏ·O[k]`。每层 O(N) 工作量，共 log₂N 层。
- **对任意长度都正确**：N = 12 → 6 → 3（奇数，走 `dft`）。合并公式对任意偶数 N 成立，所以结果仍然精确，只是奇数因子部分退化为 O(N²)；N 为质数时完全退化成 DFT。
- `result = [Complex(0)] * N` 让 N 个槽位指向同一个对象，但后面只做"重新赋值"而不做"原地修改"，并且 `k` 与 `k + N//2` 覆盖了全部下标，所以安全。
- ⚠️ 刻意的简化：
  - 每层递归都用列表推导复制一份子数组，额外内存 O(N log N)；工业实现用 bit-reversal 重排后**原地迭代**。
  - 每次都调用 `cos/sin` 算 twiddle，真实库会预先算好查表。
  - `fft([])` 会因为 `x[0]` 抛 `IndexError`（`N <= 1` 分支没有处理 N = 0）。

### 3.5 `ifft`：用"共轭技巧"复用 FFT

```python
def ifft(X):
    N = len(X)
    conj_X = [xk.conjugate() if isinstance(xk, Complex) else Complex(xk) for xk in X]
    result = fft(conj_X)
    return [Complex(r.real / N, -r.imag / N) for r in result]
```

恒等式：`IDFT(X) = conj( DFT( conj(X) ) ) / N`。先共轭输入，正向 FFT 后再共轭（`-r.imag`）并除以 N。好处是**不用再写一份正号指数的 FFT**，逆变换同样是 O(N log N)。这是面试和工程里都常见的技巧。

### 3.6 频谱读数：功率谱、幅度谱、bin→Hz

```python
def power_spectrum(X):
    return [xk.real ** 2 + xk.imag ** 2 for xk in X]


def magnitude_spectrum(X):
    return [xk.magnitude() for xk in X]


def spectral_analysis(signal, sample_rate):
    N = len(signal)
    X = fft(signal)
    magnitudes = magnitude_spectrum(X)
    freqs = [k * sample_rate / N for k in range(N)]
    return freqs[:N // 2 + 1], magnitudes[:N // 2 + 1]
```

- `power_spectrum` 不开方，直接 `re² + im²`，比 `magnitude() ** 2` 少一次 `sqrt`，也更精确。
- `freqs = k·fs/N` 就是讲义里的 `f_k = k·fs/N`。
- `[:N // 2 + 1]` 只返回 0 到 Nyquist 的 bin：实信号的后半段是共轭镜像，没有新信息。函数用 `return a, b` 一次返回**两个列表组成的元组**。
- ⚠️ 返回的是**未归一化**的幅度：振幅为 A、频率恰好落在 bin 上的正弦，峰值是 `A·N/2`（演示里 3 Hz、幅度 1.0、N = 64 → 32）。想读出真实振幅要乘 `2/N`（DC 分量则除以 N）。

### 3.7 窗函数

```python
def hann_window(N):
    return [0.5 * (1 - math.cos(2 * math.pi * n / (N - 1))) for n in range(N)]


def hamming_window(N):
    return [0.54 - 0.46 * math.cos(2 * math.pi * n / (N - 1)) for n in range(N)]


def apply_window(signal, window):
    return [s * w for s, w in zip(signal, window)]
```

- 两个窗都是升余弦：Hann 两端严格降到 0；Hamming 两端停在 0.08，压低了**最近的**旁瓣。
- 分母是 `N − 1`，即**对称窗**（首尾都是端点值）。做频谱分析时也常用分母为 N 的**周期窗**，两者在 N 较大时差别很小。
- ⚠️ `hann_window(1)` 会因 `N − 1 = 0` 抛 `ZeroDivisionError`。

### 3.8 卷积：直接法 vs FFT 法

```python
def convolve_direct(x, h):
    N = len(x)
    M = len(h)
    out_len = N + M - 1
    result = [0.0] * out_len
    for n in range(out_len):
        total = 0.0
        for k in range(M):
            if 0 <= n - k < N:
                total += x[n - k] * h[k]
        result[n] = total
    return result
```

- 公式 `y[n] = Σₖ h[k]·x[n−k]`，输出长度 `N + M − 1`。`0 <= n - k < N` 是 Python 的**链式比较**，相当于"下标在合法范围内"，越界的项视为 0。

```python
def convolve_fft(x, h):
    if len(x) == 0 or len(h) == 0:
        return []
    N = len(x) + len(h) - 1
    padded_N = 1
    while padded_N < N:
        padded_N *= 2

    x_padded = list(x) + [0.0] * (padded_N - len(x))
    h_padded = list(h) + [0.0] * (padded_N - len(h))

    X = fft(x_padded)
    H = fft(h_padded)

    Y = [xk * hk for xk, hk in zip(X, H)]

    y = ifft(Y)
    return [y[n].real for n in range(N)]
```

- **卷积定理三步走**：两个 FFT → 逐点相乘 → IFFT。
- **为什么补零到 ≥ N+M−1**：DFT 把信号看成周期重复，直接相乘得到的是**循环卷积**，尾部会回绕叠加到开头。留够空间后回绕部分只和 0 相乘，结果等于线性卷积。
- `while padded_N < N: padded_N *= 2` 再向上取到 2 的幂，是为了让 radix-2 递归一路对半拆到底；数学上只要求 ≥ N+M−1。
- `list(x)` 先复制成列表，允许传入元组等可迭代对象，也不会改动调用者的数据。
- 最后只取前 N 个点的实部：多出来的是补零的尾巴；虚部理论上为 0，只剩浮点噪声。
- 开头的空输入检查是必要的，否则 `fft([])` 会崩溃。

### 3.9 信号生成与位置编码

```python
def positional_encoding(pos, d_model):
    pe = [0.0] * d_model
    for i in range(d_model // 2):
        freq = 1.0 / (10000 ** (2 * i / d_model))
        angle = pos * freq
        pe[2 * i] = math.sin(angle)
        pe[2 * i + 1] = math.cos(angle)
    return pe
```

- 对应 `PE(pos, 2i) = sin(pos/10000^(2i/d))`、`PE(pos, 2i+1) = cos(...)`。第 i 对维度共用一个频率，频率从 1 几何递减。
- 两个位置的点积 = `Σᵢ [sin(ωp)sin(ωq) + cos(ωp)cos(ωq)] = Σᵢ cos(ωᵢ(p−q))`，只依赖位置差——`demo_positional_encoding` 打印的表格正是在验证这一点。

`generate_signal` 则是把若干 `amp·sin(2π·f·t)` 逐点叠加，`t = n / sample_rate` 把样本下标换成秒。

### 3.10 演示函数：每个都在验证一个定理

| 演示 | 验证什么 | 关键设计 |
|------|---------|---------|
| `demo_pure_sine` | DFT 能找出频率 | `fs = N = 32`，正好 1 秒，5 Hz 落在整数 bin 上，没有泄漏 |
| `demo_multi_frequency` | 线性叠加 → 多个峰，峰高 = `A·N/2` | 用 `fft` 而非 `dft`，顺带展示 FFT 结果可直接用 |
| `demo_fft_vs_dft` | 两种算法结果一致 | 比较实部、虚部的最大绝对差，阈值 1e-10 |
| `demo_reconstruction` | FFT → IFFT 无损 | 随机高斯信号，逐点打印误差 |
| `demo_convolution_theorem` | FFT 卷积 = 直接卷积 | `x` 长 5、`h` 长 3，补零到 8 |
| `demo_windowing` | 泄漏与加窗 | **故意**选 7.5 Hz，落在 bin 7 与 bin 8 之间 |
| `demo_parseval` | 能量守恒 | `Σx² == Σ|X|²/N` |
| `demo_positional_encoding` | PE 点积只依赖距离 | 选了多组距离相同、起点不同的位置对 |
| `demo_frequency_scaling` | O(N²) vs O(N log N) 的增长 | 纯公式计算，不实际计时 |

- 多个演示在函数内部 `import random` 并 `random.seed(...)` 固定种子，保证每次输出一样。
- ⚠️ `demo_fft_vs_dft` 和 `demo_frequency_scaling` 里的"multiplications"是按 `N²` 和 `N·log₂N` 估算的数量级，并不是精确的乘法次数（radix-2 FFT 的复数乘法约为 `(N/2)·log₂N`）。

### 3.11 `write_prompt_output`：带异常处理的文件写出

```python
def write_prompt_output():
    output_path = "outputs/prompt-spectral-analyzer.md"
    try:
        with open(output_path, "w") as f:
            f.write("---\n")
            # ...
        print(f"\n  Prompt output written to {output_path}")
    except OSError:
        print("\n  Could not write prompt output (run from the lesson directory)")
```

- 路径是**相对当前工作目录**的，所以必须在小节根目录运行才能写进 `outputs/`。
- `with open(...)` 保证文件一定会被关闭；`except OSError` 捕获"目录不存在""没有权限"等错误，打印提示而不是让整个脚本崩溃。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 自己写 `Complex` 而不用内置 `complex` | 看清复数乘法的展开，衔接第 19 节 | Python 内置 `complex` 更快；生产用 NumPy 复数数组 |
| 同时保留 `dft` 和 `fft` | 一个对照定义，一个展示算法，可以互相验证 | 生产只用 FFT（`np.fft` / cuFFT） |
| 递归 FFT + 奇数退回 DFT | 代码短、和讲义公式一一对应；任意长度都能得出正确结果 | 递归复制数组、重复算 twiddle；工业库用原地迭代、混合基数、Bluestein 算法 |
| `ifft` 用共轭技巧 | 复用 `fft`，少写一份代码 | 无明显代价，库里也常这么做 |
| 卷积补零到 2 的幂 | 配合 radix-2 FFT | 可能多补近一倍；`scipy.signal.fftconvolve` 会选更合适的快速长度 |
| 幅度谱不归一化 | 与 DFT 定义一致，便于和讲义公式对照 | 读振幅要乘 `2/N`；NumPy 也提供 `norm="ortho"` 等归一化选项 |
| 对称窗（分母 `N−1`） | 公式与讲义一致 | 频谱分析常用周期窗；SciPy 用 `sym=False` 生成 |
| 不做空输入、N=1 等边界检查（`convolve_fft` 除外） | 保持代码聚焦概念 | 生产代码需校验长度并抛出清晰异常 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def __init__(self, real=0.0, imag=0.0)` | 不传参数时使用默认值，`Complex(3)` 即 `3 + 0i` |
| `float()` 类型转换 | `self.real = float(real)` | 把 int 等统一转成浮点数 |
| 魔术方法 / 运算符重载 | `__add__`、`__sub__`、`__mul__`、`__repr__` | 让 `+ - *` 和 `print` 作用于自定义对象 |
| 反射运算符 | `__radd__`、`__rmul__` | 左操作数不支持时，Python 会调用右操作数的反射方法，如 `2 * z` |
| `isinstance` + 类型元组 | `isinstance(other, (int, float))` | 一次判断多种类型 |
| 条件表达式 | `x[n] if isinstance(x[n], Complex) else Complex(x[n])` | 一行版 if/else，返回其中一个值 |
| `math` 模块 | `math.cos`、`math.atan2`、`math.sqrt`、`math.log2`、`math.pi` | 三角函数、开方、对数、常数 π |
| 整除与取模 | `N // 2`、`N % 2 != 0` | `//` 向下取整除，`%` 求余数（判断奇偶） |
| 带步长的 `range` | `range(0, N, 2)`、`range(1, N, 2)` | 取偶数 / 奇数下标 |
| 列表推导式 | `[x[i] for i in range(0, N, 2)]` | 一行生成新列表 |
| 列表乘法 | `[0.0] * out_len`、`[Complex(0)] * N` | 重复元素建列表；注意对象元素是**共享引用** |
| 列表拼接 | `list(x) + [0.0] * (padded_N - len(x))` | `+` 连接两个列表，用于补零 |
| 切片 | `freqs[:N // 2 + 1]`、`signal[start:start + window_size]` | 取前若干个元素 / 子区间 |
| `zip` | `zip(X, H)`、`zip(freqs, amps)` | 按位置配对多个序列 |
| 链式比较 | `0 <= n - k < N` | 等价于 `0 <= n-k and n-k < N` |
| 增强赋值 | `total += ...`、`padded_N *= 2` | 原地累加 / 翻倍 |
| 递归 | `fft` 内部调用 `fft(...)` | 函数调用自身，需要终止条件（`N <= 1`） |
| 返回多个值 | `return freqs[:...], magnitudes[:...]` | 实际返回一个元组，可用 `a, b = f()` 解包 |
| 生成器表达式 + `max/sum` | `max(abs(...) for n in range(N))`、`sum(s ** 2 for s in signal)` | 不建中间列表，直接聚合 |
| `max` 多参数 | `max(max_error, diff_real, diff_imag)` | 一次比较多个值 |
| f-string 格式符 | `{k:<8d}`、`{f_hz:>14.1f}`、`{max_error:.2e}`、`{dft_ops:>14,d}`、`{'-' * 12}` | `<`/`>` 左/右对齐，`.1f` 小数位，`.2e` 科学计数法，`,` 千分位，花括号里可以写表达式 |
| 相邻字符串自动拼接 | `print(f"...{amps[0]}..." f"{amps[1]}...")` | 括号内相邻的字符串字面量会被拼成一个 |
| `float('inf')` | `wavelength = ... else float('inf')` | 正无穷 |
| 函数内 `import` | `import random` 写在 `demo_*` 里 | 合法；仅在函数被调用时导入 |
| `random.seed` / `random.gauss` | `random.seed(42)`、`random.gauss(0, 1)` | 固定随机种子、生成正态随机数 |
| `with open(...)` | `with open(output_path, "w") as f:` | 上下文管理器，离开代码块自动关闭文件 |
| `try / except` | `except OSError:` | 捕获文件系统错误，优雅降级 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行演示，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（在临时副本中执行 `python3 fourier.py`，Python 3.13，耗时不到 1 秒）的关键输出：

```text
  k=5                   5.0    16.0000          ← 纯 5 Hz 正弦，只有 bin 5 有能量，峰值 = 1.0 × 32/2
```

整数周期 → 没有泄漏，其他 bin 的幅度都低于 0.01，被过滤掉了。

```text
         3.0    32.0000                 32.0
         7.0    16.0000                 16.0
        15.0     9.6000                  9.6     ← 峰高 = 振幅 × N/2，三个成分互不干扰（线性性）
```

```text
  Max difference between DFT and FFT: 6.02e-14   ← 两种算法结果一致，只差浮点舍入
  Speedup: 6.4x                                  ← N=32 时 1024 / 160
```

```text
  Max reconstruction error: 4.44e-16             ← FFT → IFFT 无损，误差在机器精度量级
```

```text
  0        1.0000     1.0000     0.00e+00
  ...
  4       12.0000    12.0000     0.00e+00        ← 3+4+5，滑动求和
  6        5.0000     5.0000     0.00e+00
  Max difference: 0.00e+00                       ← 卷积定理：FFT 卷积 = 直接卷积
```

```text
   Freq (Hz)    No window         Hann      Hamming
         0.0       2.5924       0.0221       0.1871
         6.0       7.4190       2.8702       2.0491
         7.0      20.9474      13.4373      14.0377
         8.0      19.8426      13.4390      13.9508
        22.0       0.5180       0.0013       0.0406
```

- 7.5 Hz 落在两个 bin 中间，**无窗**时能量一路泄漏到 0 Hz 和 22 Hz（仍有 0.5 以上）。
- **Hann** 窗把远处的泄漏压到 0.001–0.02 量级，代价是峰值从约 20.9 降到约 13.4（窗的平均值约 0.5），主瓣也略宽（bin 6、9 仍有约 2.87）。
- **Hamming** 最近的旁瓣（bin 5、10）比 Hann 更低，但远处的旁瓣衰减慢（0 Hz 处 0.187 对比 Hann 的 0.022）——这就是讲义表格里"旁瓣水平"之外的另一面：Hamming 压低的是**最高**旁瓣，Hann 的旁瓣**衰减更快**。

```text
  Time-domain energy:  sum |x[n]|^2 = 22.147603
  Freq-domain energy:  (1/N) sum |X[k]|^2 = 22.147603   ← Parseval
```

```text
    dim ( 0, 1): freq = 1.00000000  wavelength = 6.3
    dim (14,15): freq = 0.00031623  wavelength = 19869.2   ← 频率几何递减，波长从 2π 增长到约 2万
       0      0      0       8.0000      ← 自身点积 = d_model/2 = 8（每对 sin²+cos²=1）
       0      1      1       7.4852
       1      2      1       7.4852      ← 距离相同，点积完全相同
       3      7      4       5.5597
```

```text
      1024      1,048,576           10,240      102.4x   ← N 越大，FFT 优势越夸张
```

```text
  Could not write prompt output (run from the lesson directory)
```

这一行是因为我们在只含 `code/` 的临时副本里运行，没有 `outputs/` 目录，`open` 抛出 `OSError` 被捕获。在小节根目录运行 `python code/fourier.py` 就会写入（并覆盖）`outputs/prompt-spectral-analyzer.md`。

---

## 7. 动手改一改

1. **补齐 `Complex`**：加上 `__neg__`、`__rsub__`、`__truediv__`（支持除以实数），然后把 `idft` / `ifft` 里的 `Complex(total.real / N, total.imag / N)` 改成 `total / N`。
2. **讲义练习 4**：用 `generate_signal([10, 12], [1, 1], 128, 128)` 生成两个相近频率，分别用无窗、Hann、Hamming 求幅度谱，打印 8–14 Hz 的 bin，观察哪个窗下两峰最容易分开。
3. **计时对比**：用 `time.perf_counter()` 对 N = 256、512、1024、2048 的随机信号分别计时 `dft` 和 `fft`，把实际加速比和 `demo_frequency_scaling` 的理论值放在一起比较。
4. **边界修复**：让 `fft([])` 返回 `[]`，让 `hann_window(1)` 返回 `[1.0]`，并为它们写断言测试。
5. **迭代版 FFT**：先按 bit-reversal 顺序重排输入，再自底向上做 log₂N 轮蝶形运算，不用递归、不复制子数组；与递归版比对结果。
6. **和 NumPy 对拍**：`np.allclose([complex(c.real, c.imag) for c in fft(sig)], np.fft.fft(sig))`；再用 `np.fft.rfft` 验证"实信号只需前 N/2+1 个 bin"。

---

## 8. 常见坑

- **忘记补零 → 循环卷积**：只补到 `max(len(x), len(h))` 时，尾部会回绕叠加到开头，结果悄悄出错且不报错。
- **把 bin 下标当成 Hz**：必须换算 `f = k·fs/N`；只有本文件演示里 `fs = N`（正好 1 秒）时两者才相等。
- **把幅度谱峰值当振幅**：未归一化的 DFT 峰值是 `A·N/2`，DC 分量是 `N·均值`。
- **看后半段的 bin**：实信号 k > N/2 的系数是镜像（负频率），不要把它们当作额外的高频成分。
- **以为补零能提高分辨率**：补零只做插值；要分辨更近的频率只能采更长的数据。
- **在错误的目录运行**：写文件用的是相对路径，`cd code && python fourier.py` 会写不进 `outputs/`。
