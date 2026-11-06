# 代码讲解 · complex_numbers.py

> **所属小节**：阶段 01 · 数学基础 · 第 19 节 人工智能的复数 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python complex_numbers.py`（无命令行参数；运行时会在**脚本所在目录**下创建 `outputs/skill-complex-arithmetic.md`） ｜ **依赖**：仅 Python 标准库（`math`、`os`）

---

## 1. 这份代码在考察什么

Python 自带 `complex` 类型（`3 + 2j`），这份代码却从零写了一个 `Complex` 类，目的是让你亲手体会：

1. **复数运算的本质**：乘法公式 `(ac − bd) + (ad + bc)i` 和除法"乘共轭"技巧是怎么来的。
2. **几何意义**：模长、相位、极坐标；乘以 `e^(iθ)` 就是旋转，并用旋转矩阵逐点核对。
3. **欧拉公式与单位根**：`e^(iθ)` 永远在单位圆上；N 个单位根之和为 0。
4. **DFT 不是黑盒**：只用"加法 + 复数乘法 + 单位根"两层循环就能写出 DFT / IDFT，并完美重构信号。
5. **与 Transformer 的联系**：打印正弦位置编码的频率表，看到"多频率旋转相量"的样子。
6. **Python 运算符重载**：包括 `__radd__`、`__rmul__` 这些"反向运算"魔术方法。

> 一句话：**复数 = 会旋转的二维向量**。把这个类写一遍，傅里叶变换和 RoPE 就不再神秘。讲解聚焦核心约 60% 的代码，纯打印的演示只挑关键处说明。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Complex` | 类 | 复数的加减乘除、取负、模、相位、共轭、打印、相等比较 | 复数代数 |
| `to_polar(z)` / `from_polar(r, theta)` | 函数 | 直角坐标 ↔ 极坐标 | 极坐标形式 |
| `euler(theta)` | 函数 | 返回 `cosθ + i·sinθ` | 欧拉公式 |
| `dft(signal)` / `idft(spectrum)` | 函数 | O(N²) 离散傅里叶变换及其逆 | DFT、单位根 |
| `roots_of_unity(N)` | 函数 | 生成 N 个单位根 | 单位根 |
| `demo_arithmetic` … `demo_positional_encoding`（8 个） | 演示函数 | 运算、极坐标、欧拉公式、旋转、单位根、DFT、相量、位置编码 | — |
| `write_skill_output()` | 函数 | 生成一份"复数速查"Markdown 文件 | 课程产出物 |
| `print_summary()` | 函数 | 打印 8 条要点 | — |
| `if __name__ == "__main__":` | 入口 | 依次运行全部演示并写文件 | — |

依赖关系：`euler` 返回 `Complex`；`from_polar`、`dft`、`idft`、`roots_of_unity` 都建立在 `euler` 和 `Complex` 的 `+`、`*` 之上。整份代码只有"一个类 + 几个纯函数"，演示函数只负责打印。

---

## 3. 逐段精讲

### 3.1 构造函数：统一转成 float

```python
class Complex:
    def __init__(self, real, imag=0.0):
        self.real = float(real)
        self.imag = float(imag)
```

- `imag=0.0` 默认参数让 `Complex(5)` 表示实数 5，后面"把 int/float 转成 Complex"的逻辑都依赖它。
- `float(...)` 统一数值类型，避免整数运算与浮点运算混用带来的意外；同时也起到**类型检查**作用：传入字符串 `"abc"` 或 Python 内置 `complex` 会直接报错（后者是一个坑，见 3.2）。
- 属性名取 `real`、`imag`，与内置 `complex` 保持一致——这让后面出现了一个有趣的"鸭子类型"现象。

### 3.2 运算符重载：正向与反向

```python
    def __add__(self, other):
        if isinstance(other, (int, float)):
            other = Complex(other)
        return Complex(self.real + other.real, self.imag + other.imag)

    def __radd__(self, other):
        return self.__add__(Complex(other))

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            other = Complex(other)
        return Complex(self.real - other.real, self.imag - other.imag)

    def __rsub__(self, other):
        return Complex(other - self.real, -self.imag)

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            other = Complex(other)
        r = self.real * other.real - self.imag * other.imag
        i = self.real * other.imag + self.imag * other.real
        return Complex(r, i)

    def __rmul__(self, other):
        return self.__mul__(Complex(other))
```

- `isinstance(other, (int, float))`：第二个参数可以是**类型元组**，满足其一即可。先把标量"升级"成 `Complex`，后面就只需处理"复数 op 复数"一种情况。
- **反向运算**的调用时机：执行 `2 * z` 时，Python 先试 `int.__mul__(2, z)`，int 不认识 `Complex`，返回 `NotImplemented`；Python 于是调用 `z.__rmul__(2)`。所以想让 `2 * z`、`1 + z`、`1 - z` 都能用，必须实现 `__rmul__`、`__radd__`、`__rsub__`。
- 加法和乘法可交换，`__radd__`、`__rmul__` 直接复用正向方法；减法不可交换，`__rsub__` 必须单独写：`other − z = (other − a) − bi`。
- 乘法公式就是讲义里的展开 `ac + adi + bci + bd·i²`，`i² = −1` 让 `bd` 跑到实部并变号。
- ⚠️ 遇到不支持的类型时，正向方法没有返回 `NotImplemented`，而是直接访问 `other.real`，所以报的是 `AttributeError`。规范写法是 `return NotImplemented`，让 Python 有机会尝试对方的反向方法。
- ⚠️ **不对称的坑**：`Complex(1, 2) + (1 + 2j)` 能算对——内置 `complex` 恰好有 `.real`、`.imag` 属性（鸭子类型）；但 `(1 + 2j) + Complex(1, 2)` 会走 `__radd__` → `Complex(1 + 2j)` → `float(1 + 2j)`，抛出 `TypeError`。

### 3.3 除法：乘以分母的共轭

```python
    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            other = Complex(other)
        denom = other.real ** 2 + other.imag ** 2
        if denom == 0:
            raise ZeroDivisionError("division by zero complex number")
        r = (self.real * other.real + self.imag * other.imag) / denom
        i = (self.imag * other.real - self.real * other.imag) / denom
        return Complex(r, i)
```

- 公式来源：`(a + bi)/(c + di) = (a + bi)(c − di)/(c² + d²)`。分子展开后实部 `ac + bd`、虚部 `bc − ad`，正好对应代码两行。分母 `c² + d² = |w|²` 是实数，除法就变成了"分别除以一个实数"。
- `/` 对应的魔术方法是 `__truediv__`（`//` 是 `__floordiv__`）。
- 显式抛出 `ZeroDivisionError` 并带说明，比让 Python 报一个莫名的 float 除零更友好。这里用 `== 0` 判断是合理的：只有真正的零复数才会让分母恰好为 0。
- 几何意义：除以 w 等于"旋转 −arg(w)、缩放 1/|w|"。演示里 `(5+2i)/(1−3i) = −0.1 + 1.7i`，再乘回 `(1−3i)` 精确还原 `5 + 2i`。
- 没有实现 `__rtruediv__`，所以 `1 / Complex(1, 1)` 会报 `TypeError`。

### 3.4 模长、相位、共轭

```python
    def magnitude(self):
        return math.sqrt(self.real ** 2 + self.imag ** 2)

    def phase(self):
        return math.atan2(self.imag, self.real)

    def conjugate(self):
        return Complex(self.real, -self.imag)
```

- `magnitude` 是到原点的距离 `√(a² + b²)`。工程上更稳妥的写法是 `math.hypot(a, b)`，它在 a、b 极大或极小时避免中间结果上溢 / 下溢。
- `phase` 必须用 `atan2(b, a)` 而不是 `atan(b/a)`：后者把 `(−1, −1)` 和 `(1, 1)` 都算成 45°，还会在 `a = 0` 时除零。`atan2` 返回 `(−π, π]`，四个象限都正确——演示里 `(0, −1)` 显示为 −90°，`(−2, 3)` 显示为 123.69°。
- 共轭 = 关于实轴镜像。演示验证了 `z·z̄ = a² + b²`（`3+2i` 时为 13），这就是除法公式里分母的来源。

### 3.5 打印与相等比较

```python
    def __repr__(self):
        if abs(self.imag) < 1e-12:
            return f"{self.real:.6f}"
        sign = "+" if self.imag >= 0 else "-"
        return f"{self.real:.6f} {sign} {abs(self.imag):.6f}i"

    def __eq__(self, other):
        if isinstance(other, (int, float)):
            other = Complex(other)
        return (abs(self.real - other.real) < 1e-10 and
                abs(self.imag - other.imag) < 1e-10)
```

- `__repr__` 决定 `print(z)` 和 f-string `{z}` 的显示。虚部小于 1e-12 时只显示实部，所以 `e^(iπ)` 打印为 `-1.000000` 而不是 `-1.000000 + 0.000000i`。
- 符号单独处理：虚部为负时打印 `a - |b|i`，比 `a + -bi` 好看。
- 只隐藏了很小的虚部，没有处理很小的实部：`cos(3π/2) ≈ −1.84e-16`，于是输出里出现 `-0.000000 - 1.000000i`。这不是错误，只是浮点噪声在 6 位小数下的显示。
- `__eq__` 用 1e-10 容差比较，让 `euler(2π) == 1` 成立。
- ⚠️ 定义了 `__eq__` 而没有定义 `__hash__`，Python 会把 `__hash__` 置为 `None`：`Complex` 实例**不能放进 set、不能做 dict 的键**。而且带容差的相等关系不满足传递性，很难写出与之一致的哈希函数。
- ⚠️ `Complex(1, 2) == None` 会抛 `AttributeError`，规范写法是对不认识的类型 `return NotImplemented`。

### 3.6 极坐标与欧拉公式

```python
def to_polar(z):
    return z.magnitude(), z.phase()


def from_polar(r, theta):
    return Complex(r * math.cos(theta), r * math.sin(theta))


def euler(theta):
    return Complex(math.cos(theta), math.sin(theta))
```

- `to_polar` 返回元组 `(r, θ)`；`from_polar` 是逆运算。演示里 6 个测试点往返转换后完全一致。
- `euler(θ)` 就是 `from_polar(1, θ)`：单位圆上角度为 θ 的点。整份代码的"旋转""单位根""DFT 基函数"都由它生成。
- 演示 `demo_euler_formula` 打印 8 个角度：模长全部是 `1.0000000000`；`e^(iπ) + 1` 的模约 `1.22e-16`——不是 0，因为 `math.pi` 本身就不是精确的 π，`sin(math.pi)` ≈ 1.22e-16。

### 3.7 旋转：复数乘法与旋转矩阵逐点核对

```python
    for theta in test_angles:
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        for p in test_points:
            complex_result = p * euler(theta)
            matrix_x = cos_t * p.real - sin_t * p.imag
            matrix_y = sin_t * p.real + cos_t * p.imag

            err = math.sqrt((complex_result.real - matrix_x) ** 2 +
                            (complex_result.imag - matrix_y) ** 2)
            max_error = max(max_error, err)
```

- 复数乘法的实部 `p.real·cos − p.imag·sin`、虚部 `p.real·sin + p.imag·cos`，与旋转矩阵 `[[cos, −sin], [sin, cos]]` 乘向量的两行**逐项相同**。
- 输出 `Max difference ... 0.00e+00`：不是"很小"而是**精确为 0**，因为两边执行的是完全相同的浮点乘法和减法（乘法交换律在 IEEE 浮点下成立），舍入结果一模一样。
- 前半段把 `3 + 4i` 旋转 45°、90°、180°、270°、360°：模长始终 5.0000，相位从 53.13° 依次增加；转 90° 得到 `-4 + 3i`，正好是"乘以 i"：`(3 + 4i)·i = −4 + 3i`。

### 3.8 DFT 与 IDFT：两层循环 + 单位根

```python
def dft(signal):
    N = len(signal)
    result = []
    for k in range(N):
        total = Complex(0, 0)
        for n in range(N):
            angle = -2 * math.pi * k * n / N
            xn = signal[n] if isinstance(signal[n], Complex) else Complex(signal[n])
            total = total + xn * euler(angle)
        result.append(total)
    return result


def idft(spectrum):
    N = len(spectrum)
    result = []
    for n in range(N):
        total = Complex(0, 0)
        for k in range(N):
            angle = 2 * math.pi * k * n / N
            total = total + spectrum[k] * euler(angle)
        result.append(Complex(total.real / N, total.imag / N))
    return result
```

- 直接实现公式 `X[k] = Σₙ x[n]·e^(−2πikn/N)`：外层循环频率 k，内层循环时间 n。`e^(−2πikn/N)` 是第 k 个频率的"探针"，与信号相乘再求和，就是在测"信号与这个旋转相量有多相似"（复数内积）。
- `xn = ... if isinstance(...) else Complex(...)`：既能接收实数列表，也能接收 `Complex` 列表（例如对 IDFT 的输出再做 DFT）。
- IDFT 与 DFT 只有两处不同：指数**符号为正**、结果**除以 N**。正反变换能完美抵消，依赖的正是单位根的正交性 `Σₙ e^(2πi(k−k')n/N) = N·[k = k']`。
- 复杂度 O(N²)，每一项都重新调用 `cos`、`sin`。⚠️ 可以先预计算 N 个单位根（`e^(−2πi·m/N)`，下标取 `(k·n) mod N`）复用；真正的加速要靠 FFT 的 O(N log N)（见测验 Q11）。
- ⚠️ 指数里的 `k * n` 随 N 增长，角度变大时 `cos/sin` 的浮点误差会略有增加；用 `(k * n) % N` 先取模再算角度更精确。

### 3.9 单位根

```python
def roots_of_unity(N):
    return [euler(2 * math.pi * k / N) for k in range(N)]
```

- 一行列表推导式生成 N 个均匀分布在单位圆上的点。演示打印 N = 4（1, i, −1, −i）和 N = 8（再加四个对角方向）。
- 总和的模分别是 `2.88e-16`、`5.98e-16`：理论上为 0，剩下的是浮点误差。打印成 `Sum of all roots: -0.000000`，负号同样来自极小的负数噪声。

### 3.10 DFT 演示：峰值高度与相位

```python
    for n in range(N):
        t = n / N
        val = amp1 * math.sin(2 * math.pi * freq1 * t) + amp2 * math.sin(2 * math.pi * freq2 * t)
        signal.append(val)
```

- `t = n / N`，在 [0, 1) 内均匀采 32 个点（不含 t = 1），所以 3 Hz 和 7 Hz 的正弦都恰好是整数个周期，频谱干净、没有泄漏。
- 结果 `k=3` 幅值 16、`k=7` 幅值 8，正好是 `amp·N/2`；相位都是 −90°，因为 `sin` 的正频率系数是 `A/(2i)`，纯负虚数。
- 只打印 `k ≤ N//2`：实信号的 DFT 共轭对称，后半部分是镜像（`X[29] = +16i`）。
- `idft(spectrum)` 后与原信号比较实部，最大误差 `7.44e-15`，即"完美重构"。

### 3.11 正弦位置编码的频率表

```python
    for i in range(d_model // 2):
        freq = 1.0 / (10000 ** (2 * i / d_model))
        freqs.append(freq)
    # ...
    for pos in range(max_pos):
        line = f"  {pos:>3d}"
        for i in range(d_model // 2):
            angle = pos * freqs[i]
            line += f"  {math.sin(angle):>7.4f}  {math.cos(angle):>7.4f}"
        print(line)
```

- d_model = 8 时频率依次为 1、0.1、0.01、0.001。第 0 对每个位置转约 57°，相邻位置差别大；第 3 对 10 个位置才转了 0.009 弧度，cos 几乎一直是 1.0000——高维对编码"远距离"的粗粒度位置。
- 每一对 `(sin, cos)` 就是相量 `e^(i·pos·ω)` 的坐标，所以它的模恒为 1。
- ⚠️ 打印说明写的是 "Each (sin, cos) pair is the real and imaginary part"，严格说 **cos 是实部、sin 是虚部**（讲义里的同一句话也是这个顺序）。
- 这里只演示了正弦 PE 的频率，代码中没有实现 RoPE；用 `Complex` 实现 RoPE 见测验 Q12。

### 3.12 写出速查文件：路径问题

```python
def write_skill_output():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "outputs", "skill-complex-arithmetic.md")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        with open(output_path, "w") as f:
            f.write("---\n")
            # ... 逐行写入 Markdown ...
        print(f"\n  Skill output written to {output_path}")
    except OSError:
        print("\n  Could not write skill output (run from the lesson directory)")
```

- `os.path.abspath(__file__)` 取脚本的绝对路径，`dirname` 取所在目录——这样无论从哪个工作目录运行，路径都以脚本位置为基准。
- `os.makedirs(..., exist_ok=True)`：目录已存在时不报错。
- `with open(...) as f:` 是上下文管理器，块结束时自动关闭文件，即使中途出错也会关闭。
- ⚠️ **路径与讲义不一致**：脚本在 `code/` 目录里，所以文件被写到 `code/outputs/skill-complex-arithmetic.md`；而讲义说生成的是课程目录下的 `outputs/skill-complex-arithmetic.md`（仓库里已有的那份）。两份内容完全相同，但运行后会在 `code/` 下多出一个 `outputs/` 目录。应改为 `os.path.join(script_dir, "..", "outputs", ...)`。
- ⚠️ 失败提示 "run from the lesson directory" 有误导性：路径基于 `__file__`，与当前工作目录无关。另外 `os.makedirs` 在 `try` 之外，目录不可写时会直接抛异常而不是打印这条提示。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 自己写 `Complex` 而不用内置 `complex` | 看清乘除公式与几何意义 | 慢且功能少；生产直接用 `complex`、`cmath`、NumPy 复数数组 |
| 标量自动升级成 `Complex` | 让 `2 * z`、`1 + z` 自然可用 | 不认识的类型报 `AttributeError` 而不是返回 `NotImplemented`；不兼容内置 `complex` |
| `__eq__` 带容差 | 浮点下 `euler(2π) == 1` 应为真 | 失去可哈希性，相等关系不传递 |
| `__repr__` 隐藏极小虚部 | 输出更干净 | 极小实部仍显示为 `-0.000000` |
| O(N²) 的 DFT | 与公式一一对应，最好理解 | N 大时太慢；生产用 `np.fft.fft` / `rfft`（FFT，O(N log N)） |
| 每次调用 `euler` 重算 cos/sin | 代码最短 | 可预计算单位根表；角度先对 N 取模 |
| 采样 `t = n/N`（不含端点） | 正弦恰好整数个周期，频谱无泄漏 | 真实信号做不到，需要加窗 |
| 以 `__file__` 为基准写输出文件 | 不依赖当前工作目录 | 少了一层 `..`，写到了 `code/outputs/` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类与默认参数 | `def __init__(self, real, imag=0.0)` | `Complex(5)` 时 imag 取默认值 |
| 类型转换 | `float(real)` | 统一成浮点；不接受内置 `complex` |
| 算术魔术方法 | `__add__`、`__sub__`、`__mul__`、`__truediv__`、`__neg__` | 对应 `+ - * / -z` |
| 反向魔术方法 | `__radd__`、`__rsub__`、`__rmul__` | 左操作数不支持时，Python 调用右操作数的反向方法（如 `2 * z`） |
| `__repr__` / `__eq__` | 自定义打印和 `==` | 定义 `__eq__` 后 `__hash__` 自动变为 `None` |
| `isinstance` + 类型元组 | `isinstance(other, (int, float))` | 满足其中任一类型即为真 |
| 抛出异常 | `raise ZeroDivisionError("division by zero complex number")` | 用内置异常类型并附说明 |
| 条件表达式 | `sign = "+" if self.imag >= 0 else "-"` | 一行 if-else |
| 多返回值 | `return z.magnitude(), z.phase()`；`r, theta = to_polar(z)` | 元组打包与解包 |
| 列表推导式 | `[euler(2 * math.pi * k / N) for k in range(N)]` | 一行生成单位根列表 |
| 生成器表达式 | `max(abs(reconstructed[n].real - signal[n]) for n in range(N))` | 直接求最大误差，不建中间列表 |
| `zip` / `enumerate` | `for label, theta in zip(labels, angles)`；`for k, root in enumerate(roots)` | 并行遍历 / 带下标遍历 |
| 整除 | `N // 2`、`d_model // 2` | 结果为整数，可用于 `range` |
| f-string 格式符 | `{r:>8.4f}`、`{'Rectangular':<25s}`、`{k:<6d}`、`{result.magnitude():.2e}` | 对齐、小数位、科学计数 |
| 自定义对象配格式符 | `{str(z):<25s}` | `Complex` 没有 `__format__`，直接写 `{z:<25s}` 会报 `TypeError`，先 `str()` 再格式化 |
| 隐式字符串拼接 | `f"... " f"..."` 分两行写 | 相邻字符串字面量自动拼接 |
| `math` 模块 | `math.atan2`、`math.degrees`、`math.radians`、`math.sqrt`、`math.pi` | 角度弧度互转、四象限反正切 |
| `os.path` 与 `__file__` | `os.path.dirname(os.path.abspath(__file__))` | 取脚本所在目录，路径与工作目录无关 |
| `os.makedirs(..., exist_ok=True)` | 创建 `outputs` 目录 | 已存在时不报错 |
| `with open(...) as f` | 写 Markdown 文件 | 上下文管理器，自动关闭文件 |
| `try / except OSError` | 写文件失败时打印提示 | 捕获文件系统相关错误 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行演示 |

---

## 6. 运行结果解读

已在临时副本中实际运行（Python 3.13，耗时约 0.03 秒）。在临时目录运行时，速查文件写到了副本的 `outputs/` 下（对应原仓库的 `code/outputs/`），内容与仓库中 `outputs/skill-complex-arithmetic.md` 逐字相同。关键输出：

```text
  z1 * z2  = -5.000000 + 14.000000i          ← 讲义的手算例子
  z1 / z2  = 0.647059 - 0.588235i            ← (3+2i)/(1+4i) = (11 − 10i)/17
  phase(z1)= 0.588003 rad (33.69 deg)
  z1 * conj(z1) = 13.000000                  ← 结果是纯实数 a² + b²
  Division check: (5+2i) / (1-3i) = -0.100000 + 1.700000i
  Reconstruct:    result * (1-3i)  = 5.000000 + 2.000000i
```

```text
  0.000000 - 1.000000i        1.0000        -90.00  0.000000 - 1.000000i
  -2.000000 + 3.000000i       3.6056        123.69  -2.000000 + 3.000000i
```

atan2 正确给出第四象限（−90°）和第二象限（123.69°）的角度，往返转换无损。

```text
  3pi/2       -0.000000    -1.000000     -0.000000 - 1.000000i   1.0000000000
  Euler's identity: e^(i*pi) + 1 = 0.000000
  |e^(i*pi) + 1| = 1.22e-16 (should be ~0)
```

`-0.000000` 与 `1.22e-16` 都是浮点噪声：`math.pi` 不是精确的 π。

```text
   90 deg     -4.000000 + 3.000000i              5.0000       143.13
  180 deg     -3.000000 - 4.000000i              5.0000      -126.87
  360 deg     3.000000 + 4.000000i               5.0000        53.13
  and rotation matrix: 0.00e+00
```

模长恒为 5；180° 的相位显示为 −126.87°（即 233.13° 落在 atan2 的值域里）。复数乘法与旋转矩阵的差是精确的 0。

```text
  k=3         16.0000       -90.00
  k=7          8.0000       -90.00
  IDFT reconstruction error: 7.44e-15
  Perfect reconstruction: True
```

峰值位置、高度（`amp·N/2`）、相位（sin 型 → −90°）全部符合理论；IDFT 重构误差在 1e-14 量级。

```text
   0.062     0.382683     0.923880   1.000000
   0.500    -1.000000     0.000000   1.000000
```

相量 `e^(i·6πt)`：t 每增加 1/16，角度增加 `6π/16 = 67.5°`，16 个采样点里转了 3 整圈；模长始终为 1。

```text
    dim pair 0: freq = 1.000000
    dim pair 3: freq = 0.001000
    9   0.4121  -0.9111   0.7833   0.6216   0.0899   0.9960   0.0090   1.0000
```

第 0 对到 pos = 9 时已转过 9 弧度（约 1.4 圈），数值剧烈变化；第 3 对只转了 0.009 弧度，几乎不动——多尺度的位置"指纹"。

---

## 7. 动手改一改

1. 给 `Complex` 加 `__pow__(self, n)`（用极坐标：`r**n`、`n·θ`）和 `__abs__`（让 `abs(z)` 可用）；完成讲义练习 2：`euler(math.pi / 6) ** 12` 应回到 1。
2. 修改所有运算符：遇到不支持的类型时 `return NotImplemented`；让 `__init__` 能接收内置 `complex`（检查 `hasattr(real, "imag")`），使 `(1 + 2j) + Complex(1, 2)` 也能工作。
3. 修正 `write_skill_output` 的路径，让它写到课程目录的 `outputs/`，并把 `os.makedirs` 移进 `try` 块。
4. 实现基 2 递归 FFT（参考测验 Q11），用 `time.perf_counter()` 对比 N = 256、1024 时 `dft` 与 `fft` 的耗时，再与 `np.fft.fft` 对比结果。
5. 用 `Complex` 实现 RoPE（参考测验 Q12），验证 (5, 2) 与 (103, 100) 两组位置的点积相同。
6. 在 `demo_dft` 的信号里加一项 `0.8·cos(2π·5t)`，预测 k = 5 的幅值和相位（应为 12.8 和 0°），再运行验证；然后把采样改成 `t = n / (N - 1)`，观察频谱泄漏。

---

## 8. 常见坑

- **用 `atan(b/a)` 求相位**：丢失象限信息、a = 0 时除零；一律用 `atan2(b, a)`。
- **读错 DFT 幅值**：`|X[k]|` 是 `A·N/2` 而不是 A；实信号的能量平分在 k 和 N − k 两个 bin 上，换算振幅要乘 `2/N`。
- **自定义数值类型的反向运算**：漏写 `__rmul__` / `__radd__` 时 `2 * z` 会报错；`__rsub__` 不能直接复用 `__sub__`（减法不可交换）。
- **定义 `__eq__` 却忘了 `__hash__`**：对象不能放进 set / dict。
- **对自定义对象直接用格式符**：`f"{z:<25s}"` 报错，要么先 `str(z)`，要么实现 `__format__`。
- **把 `-0.000000`、`1.22e-16` 当成 bug**：它们是浮点运算的正常噪声；比较时用容差。
- **以为输出文件写进了课程的 `outputs/`**：实际写在 `code/outputs/`（见 3.12）。
