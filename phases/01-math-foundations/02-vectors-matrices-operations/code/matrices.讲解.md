# 代码讲解 · matrices.py

> **所属小节**：阶段 01 · 数学基础 · 第 02 节 向量、矩阵和运算 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python matrices.py` ｜ **依赖**：仅 Python 标准库（`random`），无需 NumPy

---

## 1. 这份代码在考察什么

上一节（`vectors.py`）重点是"向量的几何"；这一节把重心移到**矩阵运算本身**，目标是让 `output = relu(W @ x + b)` 这一行代码里的每个符号都不再神秘：

1. **矩阵的全套基本运算**：加、减、数乘、逐元素乘、矩阵乘、转置、行列式、逆、单位矩阵，每个都用最朴素的 for 循环 / 列表推导写出来。
2. **形状意识**：`matmul` 显式检查内侧维度，并给出可读的错误信息——和你在 PyTorch 里看到的 `shape mismatch` 是同一件事。
3. **逐元素乘 vs 矩阵乘**：两个方法并排放在一起，用同一对输入跑出完全不同的结果。
4. **广播的最小实现**：`__add__` 支持"矩阵 + 行向量"和"矩阵 + 列向量"，这是 bias 加法的本质。
5. **从运算到网络**：最后用这些积木搭一个 3 → 4 → 2 的两层网络，跑通一次完整前向传播。

> 一句话：**这个 `Matrix` 类就是一个"玩具版 NumPy"**——讲义明确说它会成为阶段 03 迷你神经网络框架的地基。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Vector` | 类 | 向量加减、数乘、点积、模长、归一化 | 向量基本运算（复习第 01 节） |
| `Matrix.__init__` / `__repr__` | 构造与显示 | 复制数据、记录 `rows/cols/shape`；按列对齐、带括号地打印矩阵 | 矩阵的形状 |
| `Matrix.__add__` | 魔术方法 | 同形状相加 + 行/列向量广播 | 加法、广播 |
| `__sub__` / `scalar_multiply` / `element_wise_multiply` | 方法 | 减法、数乘、Hadamard 积 | 逐元素运算 |
| `matmul` / `__matmul__` | 方法 / 魔术方法 | 带形状检查的矩阵乘，支持 `@` 运算符 | 矩阵乘法 |
| `transpose` / `T` | 方法 / 属性 | 行列互换 | 转置 |
| `determinant` | 递归方法 | 余子式展开求行列式 | 行列式 |
| `inverse_2x2` | 方法 | 2×2 求逆公式 | 逆矩阵 |
| `identity` / `zeros` / `random` | 静态方法 | 构造单位阵、零矩阵、随机矩阵 | 单位矩阵、权重初始化 |
| `relu_matrix` | 函数 | 对每个元素做 `max(0, x)` | 激活函数 |
| `demo_*` × 6 | 函数 | 分主题演示 | — |

数据流：`demo_neural_network_layer` 用 `Matrix.random` 生成 `W1/W2`，经 `@`（→ `matmul`）、`+`（→ `__add__`）、`relu_matrix` 完成 `x → z1 → h1 → z2`；其他 demo 各自独立。

---

## 3. 逐段精讲

### 3.1 `Vector`：上一节的精简版

```python
class Vector:
    def __init__(self, data):
        self.data = list(data)
        self.size = len(self.data)
    # ...
    def normalize(self):
        mag = self.magnitude()
        return Vector([x / mag for x in self.data])
```

和第 01 节的 `Vector` 几乎一样（字段名从 `components` 改成了 `data`），只保留了本节用得到的运算。`demo_vectors` 用 `[3, 4]` 这个"3-4-5 三角形"演示：模长是 5，归一化后是 `[0.6, 0.8]`，再求模长得到 1.0。

⚠️ 同样没有处理零向量（`normalize` 会除以 0）和维度不一致（`zip` 静默截断）。

### 3.2 构造函数与 `__repr__`：让矩阵"长得像矩阵"

```python
class Matrix:
    def __init__(self, data):
        self.data = [list(row) for row in data]
        self.rows = len(self.data)
        self.cols = len(self.data[0])
        self.shape = (self.rows, self.cols)
```

- `[list(row) for row in data]` **逐行复制**。这一点后面很关键：`demo_neural_network_layer` 里写了 `Matrix([[0.0]] * hidden_size)`，`[[0.0]] * 4` 生成的 4 个内层列表其实是**同一个对象**，如果构造函数不复制，改一行就会改掉所有行。
- `shape` 用元组 `(行, 列)`，和 NumPy/PyTorch 的命名一致。
- ⚠️ 没有检查每行长度是否一致（"锯齿"列表也能构造成功），也不支持空矩阵（`data[0]` 会 `IndexError`）。

```python
    def __repr__(self):
        col_widths = []
        for j in range(self.cols):
            width = max(len(f"{self.data[i][j]:.4f}") for i in range(self.rows))
            col_widths.append(width)
        lines = []
        for i in range(self.rows):
            row_str = "  ".join(
                f"{self.data[i][j]:{col_widths[j]}.4f}" for j in range(self.cols)
            )
            bracket_l = "|" if 0 < i < self.rows - 1 else ("/" if i == 0 else "\\")
            bracket_r = "|" if 0 < i < self.rows - 1 else ("\\" if i == 0 else "/")
            lines.append(f"  {bracket_l} {row_str} {bracket_r}")
        header = f"Matrix {self.rows}x{self.cols}:"
        return header + "\n" + "\n".join(lines)
```

- 第一遍循环先算出**每一列**格式化后最长的宽度，第二遍用 `f"{值:{宽度}.4f}"` 右对齐——这是 f-string 的**嵌套格式说明符**，宽度本身也来自变量。
- 括号用 `/ \`、`| |`、`\ /` 拼出类似手写大括号的效果：首行 `/…\`，中间行 `|…|`，末行 `\…/`。`"\\"` 是转义后的单个反斜杠。
- ⚠️ 只有 1 行时 `i == 0` 命中首行分支，所以打印成 `/ … \`（运行结果里的 `Bias` 就是这样），纯属显示细节。
- 统一 `.4f` 意味着整数也会显示成 `1.0000`，但 `data` 里存的仍是整数（例如 `det(A) = 10` 打印出来是整数）。

### 3.3 `__add__`：同形状相加 + 简化版广播

```python
    def __add__(self, other):
        if isinstance(other, Matrix):
            if other.shape == self.shape:
                return Matrix([...])                               # 普通逐元素相加
            if other.rows == 1 and other.cols == self.cols:
                return Matrix([
                    [self.data[i][j] + other.data[0][j] for j in range(self.cols)]
                    for i in range(self.rows)
                ])                                                 # 行向量：每行都加同一行
            if other.cols == 1 and other.rows == self.rows:
                return Matrix([
                    [self.data[i][j] + other.data[i][0] for j in range(self.cols)]
                    for i in range(self.rows)
                ])                                                 # 列向量：第 i 行加 other[i]
        raise ValueError(f"Cannot add shapes {self.shape} and {other.shape}")
```

这是本文件最值得细看的方法：

- **行向量广播**（`1×n`）：`other.data[0][j]` 固定读第 0 行，相当于把这一行"复制"到每一行。讲义的例子 `[[1,2,3],[4,5,6]] + [10,20,30]` 走的就是这个分支。批量数据按"一行一个样本"排布时，bias 就是这样加的。
- **列向量广播**（`m×1`）：`other.data[i][0]` 固定读第 0 列，相当于把这一列复制到每一列。神经网络 demo 里 `(W1 @ x) + b1` 的 `b1` 是 `4×1`，形状和 `W1 @ x` 完全相同，其实走的是第一个分支；但如果 `x` 换成 `3×batch` 的批量输入，就会走这个分支。
- **为什么这样设计**：只实现神经网络真正需要的两种 bias 形状，代码最短、行为最可预测。
- ⚠️ 与 NumPy 的差距：不支持标量（`M + 5`）、不支持 `1×1`、不支持"两边同时拉伸"（`(3,1)+(1,4)`）。另外当 `other` 不是 `Matrix` 时，`raise` 那一行访问 `other.shape` 会先抛出 `AttributeError`，而不是预期的 `ValueError`。

### 3.4 减法、数乘、逐元素乘

```python
    def __sub__(self, other):
        return Matrix([
            [self.data[i][j] - other.data[i][j] for j in range(self.cols)]
            for i in range(self.rows)
        ])

    def scalar_multiply(self, scalar):
        return Matrix([
            [self.data[i][j] * scalar for j in range(self.cols)]
            for i in range(self.rows)
        ])

    def element_wise_multiply(self, other):
        return Matrix([
            [self.data[i][j] * other.data[i][j] for j in range(self.cols)]
            for i in range(self.rows)
        ])
```

- 三个方法都是"对每个位置 (i, j) 做一次标量运算"，**输出形状和 `self` 相同**。
- `scalar_multiply` 对应讲义表格里的"学习率 × 梯度"：`W_new = W - lr * grad` 里的 `lr * grad` 就是数乘。
- `element_wise_multiply` 就是 NumPy 的 `A * B`（Hadamard 积）。
- 注意命名：数乘和逐元素乘用了普通方法名，**没有重载 `*`**，而矩阵乘重载了 `@`。这样 `*` 这个符号在本类中根本不可用，避免了"`*` 到底是哪种乘法"的歧义——是一个很实用的教学设计。
- ⚠️ `__sub__` 和 `element_wise_multiply` **都不检查形状**：`other` 比 `self` 大时会静默只用左上角的子块；`other` 比 `self` 小时抛 `IndexError`。前者是更危险的静默错误（测验 Q9 专门考这一点）。

### 3.5 `matmul` 与 `@`：带形状检查的三重循环

```python
    def matmul(self, other):
        if self.cols != other.rows:
            raise ValueError(
                f"Cannot multiply shapes {self.shape} and {other.shape}: "
                f"inner dimensions {self.cols} != {other.rows}"
            )
        return Matrix([
            [
                sum(self.data[i][k] * other.data[k][j] for k in range(self.cols))
                for j in range(other.cols)
            ]
            for i in range(self.rows)
        ])

    def __matmul__(self, other):
        return self.matmul(other)
```

- **形状规则写进代码**：`(m×n) @ (n×p)` 要求 `self.cols == other.rows`。错误信息同时打出两个形状和内侧维度，这正是 PyTorch 报 `mat1 and mat2 shapes cannot be multiplied` 时你需要的信息。
- 公式 `C[i][j] = Σₖ A[i][k]·B[k][j]`：外层列表推导遍历输出行 `i`，中层遍历输出列 `j`，最内层生成器表达式对 `k` 求和。三层循环，时间复杂度 O(m·n·p)。
- `__matmul__` 只是转发给 `matmul`，这样 `A @ B` 和 `A.matmul(B)` 两种写法都能用。Python 遇到 `A @ B` 时调用 `A.__matmul__(B)`。
- 和第 01 节相比：这里**没有** `isinstance(other, Vector)` 的分派——向量统一用 `n×1` 的列矩阵表示（如 `x = Matrix([[0.5], [0.8], [0.2]])`），规则更统一。
- ⚠️ 纯 Python 三重循环很慢；NumPy 的 `@` 会调用 BLAS 中高度优化的 GEMM 例程，讲义说"同样的数学，快 100 倍"。

### 3.6 转置与 `@property`

```python
    def transpose(self):
        return Matrix([
            [self.data[j][i] for j in range(self.rows)]
            for i in range(self.cols)
        ])

    @property
    def T(self):
        return self.transpose()
```

- 新矩阵有 `self.cols` 行，第 i 行由原矩阵的第 i 列组成：`Aᵀ[i][j] = A[j][i]`。
- `@property` 让 `A.T` 可以像属性一样访问（不加括号），和 NumPy 的 `A.T` 写法一致。
- ⚠️ 这里每次 `.T` 都会**新建一份数据**，O(m·n)；NumPy/PyTorch 的转置只交换 stride，O(1) 返回视图。

### 3.7 `determinant`：余子式展开（递归）

```python
    def determinant(self):
        if self.rows != self.cols:
            raise ValueError("Determinant only defined for square matrices")
        if self.shape == (1, 1):
            return self.data[0][0]
        if self.shape == (2, 2):
            return self.data[0][0] * self.data[1][1] - self.data[0][1] * self.data[1][0]
        det = 0
        for j in range(self.cols):
            minor = Matrix([
                [self.data[i][k] for k in range(self.cols) if k != j]
                for i in range(1, self.rows)
            ])
            det += ((-1) ** j) * self.data[0][j] * minor.determinant()
        return det
```

- 两个**递归终止条件**：1×1 直接返回元素，2×2 用 `ad - bc`。
- n ≥ 3 时沿第 0 行展开：对每一列 j，构造去掉第 0 行（`range(1, self.rows)`）和第 j 列（`if k != j`）的子矩阵 `minor`，递归求它的行列式，再乘以符号 `(-1)^j` 和元素 `a₀ⱼ`。
- 带条件的列表推导 `[... for k in range(self.cols) if k != j]` 一行就完成了"删掉一列"。
- 几何含义：行列式是变换对面积/体积的缩放倍数；为 0 表示空间被压扁，矩阵不可逆。
- ⚠️ 复杂度 O(n!)：每层要递归 n 个 (n-1) 阶子问题。只适合 3×3、4×4 这样的小矩阵；生产中用 LU 分解（O(n³)）。

### 3.8 `inverse_2x2`：公式法求逆

```python
    def inverse_2x2(self):
        if self.shape != (2, 2):
            raise ValueError("This method only works for 2x2 matrices")
        det = self.determinant()
        if abs(det) < 1e-10:
            raise ValueError("Matrix is singular, no inverse exists")
        return Matrix([
            [self.data[1][1] / det, -self.data[0][1] / det],
            [-self.data[1][0] / det, self.data[0][0] / det]
        ])
```

- 公式：`[[a,b],[c,d]]⁻¹ = (1/det)·[[d,-b],[-c,a]]`——主对角互换，副对角取负，整体除以 det。
- 用 `abs(det) < 1e-10` 而不是 `det == 0`：讲义正文里的版本写的是 `det == 0`，代码版改成了容差判断，更健壮——浮点运算得到的"0"往往是 `1e-17` 量级的噪声。
- ⚠️ 固定阈值 `1e-10` 是教学简化：行列式会随矩阵整体缩放剧烈变化，严格判断"接近奇异"应该看条件数。

### 3.9 静态工厂方法：`identity` / `zeros` / `random`

```python
    @staticmethod
    def identity(n):
        return Matrix([
            [1 if i == j else 0 for j in range(n)]
            for i in range(n)
        ])

    @staticmethod
    def zeros(rows, cols):
        return Matrix([[0] * cols for _ in range(rows)])

    @staticmethod
    def random(rows, cols, low=-1.0, high=1.0):
        return Matrix([
            [random.uniform(low, high) for _ in range(cols)]
            for _ in range(rows)
        ])
```

- `@staticmethod`：不需要实例（没有 `self`），用类名直接调用 `Matrix.identity(3)`，作用类似 NumPy 的 `np.eye`、`np.zeros`、`np.random.uniform`。
- `identity` 用条件表达式 `1 if i == j else 0` 生成对角线。
- `zeros` 写成 `[[0] * cols for _ in range(rows)]` 而**不是** `[[0] * cols] * rows`：后者的每一行是同一个列表对象。虽然构造函数会再复制一次，但养成这个习惯能避免在别处踩坑。
- `random` 用 `random.uniform(-1, 1)` 做权重初始化。⚠️ 真实网络会用 Xavier / He 初始化，按输入维度缩放方差（阶段 03 会讲）。
- 方法名 `random` 和模块名 `random` 同名，但方法体内的 `random.uniform` 解析到的是**模块级全局变量** `random`（函数体内的名字查找不会去查类属性），所以不会冲突。不过这种同名写法容易让人困惑，工程中最好避免。

### 3.10 `relu_matrix` 与两层网络前向传播

```python
def relu_matrix(m):
    return Matrix([[max(0, val) for val in row] for row in m.data])
```

```python
    random.seed(42)
    # ...
    x = Matrix([[0.5], [0.8], [0.2]])
    W1 = Matrix.random(hidden_size, input_size)
    b1 = Matrix([[0.0]] * hidden_size)
    W2 = Matrix.random(output_size, hidden_size)
    b2 = Matrix([[0.0]] * output_size)
    # ...
    z1 = (W1 @ x) + b1
    h1 = relu_matrix(z1)
    # ...
    z2 = (W2 @ h1) + b2
```

- `relu_matrix` 是**逐元素**操作：对每个值取 `max(0, val)`，形状不变。
- 形状推导（代码最后也打印了）：
  - 第 1 层：`(4×3) @ (3×1) + (4×1) → (4×1) → ReLU → (4×1)`
  - 第 2 层：`(2×4) @ (4×1) + (2×1) → (2×1)`
- 权重形状是 `(输出维度, 输入维度)`：因为采用列向量约定 `W @ x`，W 的列数必须等于输入维度。
- `random.seed(42)` 在生成权重之前调用，保证每次运行结果一致（可复现）。
- 第 2 层输出没有激活函数——最后一层通常输出 logits，交给 softmax 或损失函数处理。

### 3.11 `demo_weight_matrix_intuition`：每一行是一个"特征检测器"

```python
    W = Matrix([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.5, 0.5, 0.0],
    ])
    x = Matrix([[0.8], [0.6], [0.1]])
```

`W @ x` 的第 i 个输出就是"W 的第 i 行"和 x 的点积：第 0 行复制特征 0（0.8），第 1 行复制特征 1（0.6），第 2 行取特征 0 和 1 的平均（0.7），完全忽略特征 2。这是理解"权重矩阵每一行学到一个模式"的最小例子。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 列表的列表 | 每个运算都能逐行读懂 | 慢且占内存；NumPy 用连续内存 + BLAS |
| 向量统一用 `n×1` 列矩阵 | 只需一套 `matmul` 规则，形状推导一致 | 框架里通常是 `(batch, features)` 行布局，写成 `x @ Wᵀ` |
| 只重载 `+ - @`，数乘/逐元素乘用具名方法 | 避免 `*` 语义歧义 | 用起来啰嗦；NumPy 约定 `*` 为逐元素 |
| `matmul` 显式检查形状、报错带形状信息 | 形状错误是最常见的 bug，要尽早失败 | 其他方法（`__sub__`、逐元素乘）未检查，应补齐 |
| 简化广播（只支持行/列向量） | 覆盖 bias 加法即可 | NumPy 的通用尾部对齐规则 |
| 余子式展开求行列式 | 定义直观、递归简洁 | O(n!)；生产用 LU，O(n³) |
| 只实现 2×2 逆 | 有闭式公式，便于验证 | 通用求逆/解方程用 LU、`np.linalg.solve` |
| `abs(det) < 1e-10` 判奇异 | 防浮点噪声 | 应使用条件数或奇异值判断 |
| `random.uniform(-1, 1)` 初始化 | 简单 | Xavier / He 初始化 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `class` 与 `__init__` | `class Matrix: def __init__(self, data)` | 定义类与构造函数 |
| 元组 | `self.shape = (self.rows, self.cols)` | 不可变的有序组合，可直接用 `==` 比较 `other.shape == self.shape` |
| 列表推导式（嵌套） | `[[... for j in range(self.cols)] for i in range(self.rows)]` | 外层生成行、内层生成列；构造二维结构的惯用法 |
| 带条件的推导式 | `[self.data[i][k] for k in range(self.cols) if k != j]` | `if` 放在末尾表示过滤 |
| 条件表达式 | `1 if i == j else 0` | 一行的 if-else，返回一个值 |
| 生成器表达式 | `sum(self.data[i][k] * other.data[k][j] for k in ...)` | 不建中间列表直接求和 |
| `_` 占位变量 | `for _ in range(rows)` | 表示"这个循环变量用不上" |
| 列表乘法 | `[0] * cols`、`[[0.0]] * hidden_size` | 重复元素；对可变对象只复制**引用** |
| 魔术方法 | `__repr__`、`__add__`、`__sub__`、`__matmul__` | `print(A)`、`A + B`、`A - B`、`A @ B` 自动调用 |
| `@property` | `def T(self)` | 把方法变成属性，`A.T` 无需括号 |
| `@staticmethod` | `identity`、`zeros`、`random` | 不依赖实例的工厂函数，`Matrix.zeros(2, 3)` |
| 默认参数 | `def random(rows, cols, low=-1.0, high=1.0)` | 调用时可省略 |
| `isinstance` | `isinstance(other, Matrix)` | 运行时类型判断 |
| `raise ValueError(...)` | 形状不匹配、奇异矩阵 | 主动抛出异常并附带说明 |
| f-string 嵌套格式 | `f"{self.data[i][j]:{col_widths[j]}.4f}"` | 宽度来自变量，`.4f` 保留 4 位小数 |
| 多段 f-string 拼接 | `f"Cannot multiply ... " f"inner dimensions ..."` | 相邻字符串字面量会自动连接 |
| 字符串转义 | `"\\"` | 表示一个反斜杠字符 |
| `str.join` | `"  ".join(...)`、`"\n".join(lines)` | 用分隔符拼接字符串序列 |
| 递归 | `minor.determinant()` | 方法调用自身，需有终止条件 |
| `random.seed` / `random.uniform` | `random.seed(42)` | 固定随机种子保证可复现；均匀分布采样 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 demo |

---

## 6. 运行结果解读

在临时副本中实际运行 `python3 matrices.py`，关键输出如下（已省略部分重复格式）：

```text
v . w = 11                         ← 3·1 + 4·2
|v| = 5.0                          ← 3-4-5 三角形
v normalized = Vector([0.6, 0.8])
|v normalized| = 1.0

A + B =
  /  6.0000   8.0000 \
  \ 10.0000  12.0000 /
A * B (element-wise) =
  /  5.0000  12.0000 \             ← 对应位置相乘
  \ 21.0000  32.0000 /
A @ B (matrix multiply) =
  / 19.0000  22.0000 \             ← 1·5+2·7=19，1·6+2·8=22 ...
  \ 43.0000  50.0000 /
A^T =
  / 1.0000  3.0000 \
  \ 2.0000  4.0000 /
```

逐元素乘和矩阵乘用同一对输入，结果完全不同——这就是讲义反复强调的区别。

```text
det(A) = 10                        ← A = [[4,7],[2,6]]，4·6 - 7·2
A^-1 =
  /  0.6000  -0.7000 \
  \ -0.2000   0.4000 /
A @ A^-1 (should be identity) =
  /  1.0000  0.0000 \
  \ -0.0000  1.0000 /              ← 注意 "-0.0000"
```

`-0.0000` 不是 bug，而是浮点误差：实际值是 `-2.22e-16`，`.4f` 四舍五入后保留了负号。对角线实际是 `0.9999999999999998` 和 `1.0000000000000004`。这说明**验证逆矩阵要用容差比较**（`np.allclose`），不能用 `==`。

```text
Output + Bias (broadcast) =
  / 11.0000  22.0000  33.0000 \    ← 1×3 的 bias 被加到每一行
  \ 14.0000  25.0000  36.0000 /

W @ x =
  / 0.8000 \                       ← 第 0 行复制特征 0
  | 0.6000 |                       ← 第 1 行复制特征 1
  \ 0.7000 /                       ← 第 2 行 = 0.5·0.8 + 0.5·0.6
```

```text
Hidden layer pre-activation z1: (4, 1)
  / -0.7105 \
  |  0.1722 |
  | -0.2999 |
  \ -0.9182 /
Hidden layer post-ReLU h1: (4, 1)
  / 0.0000 \
  | 0.1722 |                       ← 只有 1 个神经元被激活
  | 0.0000 |
  \ 0.0000 /
Output z2: (2, 1)
  / -0.1037 \
  \  0.0308 /
```

- 用 `seed(42)` 生成的随机权重下，4 个隐藏神经元里有 3 个的预激活为负，被 ReLU 置 0。于是 `z2` 只取决于 `W2` 的第 1 列乘以 0.1722：`-0.6023 × 0.1722 ≈ -0.1037`，`0.1785 × 0.1722 ≈ 0.0308`。
- 这个小例子顺便展示了 **ReLU 的"稀疏激活"**：被置 0 的神经元对这个输入没有贡献，反向传播时梯度也为 0。如果某个神经元对所有输入都为负，就成了"死神经元（dead ReLU）"。

---

## 7. 动手改一改

1. **补齐形状检查**：给 `__sub__` 和 `element_wise_multiply` 加上 `if self.shape != other.shape: raise ValueError(...)`；再把 `__add__` 最后的 `raise` 改成在 `other` 不是 `Matrix` 时也能给出清晰报错。
2. **支持标量广播**：让 `M + 5` 和 `M + Matrix([[5]])` 都能工作（提示：先判断 `isinstance(other, (int, float))`）。
3. **验证逆矩阵**：讲义练习 1——对三个不同的 2×2 矩阵验证 `A @ A.inverse_2x2()` 近似等于单位阵（写一个 `allclose(A, B, tol=1e-9)` 方法）；再试 `[[1,2],[2,4]]`，观察抛出的异常。
4. **3×3 逆矩阵**：讲义练习 2——用伴随矩阵法实现 `inverse_3x3`，用 `np.linalg.inv` 对拍（参考测验 Q10）。
5. **批量前向传播**：把 `x` 改成 `3×5` 的矩阵（5 个样本作为 5 列），观察 `(W1 @ x) + b1` 自动走进 `__add__` 的"列向量广播"分支，输出变成 `4×5`。
6. **计时对比**：用 `time.perf_counter()` 比较 `Matrix.random(100,100) @ Matrix.random(100,100)` 与 NumPy 的 `@`；再比较 `determinant()` 在 8×8 和 9×9 上的耗时，体会 O(n!) 的增长。

---

## 8. 常见坑

- **把 `*` 当矩阵乘**：在 NumPy/PyTorch 中，同形状方阵用 `*` 不会报错但结果是逐元素乘。本类干脆不重载 `*` 来规避这个歧义。
- **形状没对齐的静默错误**：`element_wise_multiply` 和 `__sub__` 在 `other` 更大时会悄悄只用一部分数据——比报错更可怕。
- **`[[0] * n] * m` 的共享引用**：外层列表里的 m 行是同一个对象，改一行全变。本代码靠构造函数里的 `list(row)` 逐行复制兜底，但别依赖这种"恰好没事"。
- **用 `==` 验证逆矩阵**：`A @ A⁻¹` 的结果里会有 `0.9999999999999998` 和 `-2.2e-16`，必须用容差比较。
- **对大矩阵用余子式展开**：O(n!)，n=12 就要跑很久；而且行列式本身会上溢/下溢，大矩阵通常算 `log|det|`（`np.linalg.slogdet`）。
- **混淆权重形状约定**：本节 `W` 是 `(out, in)` 并左乘列向量；如果数据是 `(batch, in)` 的行布局，要写 `x @ W.T`，不要把 `W` 存成 `(in, out)` 又去左乘。
