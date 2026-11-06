<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="vectors-matrices--operations"></a>

# 向量、矩阵和运算

> 每个神经网络只是带有额外步骤的矩阵乘法。

**类型：** 构建
**语言：** Python、Julia
**先决条件：** 第 1 阶段，第 01 课（线性代数直觉）
**时间：** ~60 分钟

<a id="learning-objectives"></a>

## 学习目标

- 使用逐元素运算、矩阵乘法、转置、行列式和逆运算构建 Matrix 类
- 区分元素乘法和矩阵乘法并解释它们何时适用
- 仅使用从头开始的 Matrix 类实现单个密集神经网络层 (`relu(W @ x + b)`)
- 解释广播规则以及偏差添加在神经网络框架中的工作原理

<a id="the-problem"></a>

## 问题

您想要构建一个神经网络。您阅读代码并看到以下内容：

```
output = activation(weights @ input + bias)
```

那`@`就是矩阵乘法。 `weights` 是一个矩阵。 `input` 是一个向量。如果您不知道这些操作的作用，那么这一行就很神奇。如果你知道的话，它是一个层的整个 forward pass 的三个操作。

您的模型处理的每个图像都是像素值矩阵。每个单词 embedding 都是一个向量。每个神经网络的每一层都是一个矩阵变换。如果不熟练掌握矩阵运算，就无法构建人工智能系统，就像不了解变量就无法编写代码一样。

本课程从头开始构建流畅性。

<a id="the-concept"></a>

## 概念

<a id="vectors-ordered-lists-of-numbers"></a>

### 向量：有序的数字列表

向量是具有方向和大小的数字列表。在AI中，向量代表数据点，features或parameters。

```
v = [3, 4]        -- a 2D vector
w = [1, 0, -2]    -- a 3D vector
```

二维向量 `[3, 4]` 指向平面上的坐标 (3, 4)。它的长度（大小）是 5（3-4-5 三角形）。

<a id="matrices-grids-of-numbers"></a>

### 矩阵：数字网格

矩阵是二维网格。行和列。 m x n 矩阵有 m 行和 n 列。

```
A = | 1  2  3 |     -- 2x3 matrix (2 rows, 3 columns)
    | 4  5  6 |
```

在神经网络中，weight 矩阵将输入向量转换为输出向量。具有 784 个输入和 128 个输出的层使用 128x784 weight 矩阵。

<a id="why-shapes-matter"></a>

### 为什么形状很重要

矩阵乘法有严格的规则：`(m x n) @ (n x p) = (m x p)`。内部尺寸必须匹配。

```
(128 x 784) @ (784 x 1) = (128 x 1)
  weights       input       output

Inner dimensions: 784 = 784  -- valid
```

如果您在 PyTorch 中遇到形状不匹配错误，这就是原因。

<a id="the-operations-map"></a>

### 行动图

| 操作 | 它的作用 | 神经网络的使用 |
|-----------|-------------|-------------------|
| 加法 | 按元素组合 | 向输出添加偏置 |
| 标量乘法 | 缩放每个元素 | Learning rate * gradients |
| 矩阵乘法 | 变换向量 | 层 forward pass |
| 转置 | 翻转行和列 | Backpropagation |
| 行列式 | 单号汇总 | 检查可逆性 |
| 逆 | 撤消转换 | 求解线性系统 |
| 身份 | 无为矩阵 | 初始化、剩余连接 |

<a id="element-wise-vs-matrix-multiplication"></a>

### 逐元素与矩阵乘法

这种区别经常让初学者感到困惑。

逐元素：乘以匹配位置。两个矩阵必须具有相同的形状。

```
| 1  2 |   | 5  6 |   | 5  12 |
| 3  4 | * | 7  8 | = | 21 32 |
```

矩阵乘法：行和列的点积。内部尺寸必须匹配。

```
| 1  2 |   | 5  6 |   | 1*5+2*7  1*6+2*8 |   | 19  22 |
| 3  4 | @ | 7  8 | = | 3*5+4*7  3*6+4*8 | = | 43  50 |
```

不同的操作，不同的结果，不同的规则。

<a id="broadcasting"></a>

### 广播

当您将偏置向量添加到输出矩阵时，形状不匹配。广播会拉伸较小的数组以适应。

```
| 1  2  3 |   +   [10, 20, 30]
| 4  5  6 |

Broadcasting stretches the vector across rows:

| 1  2  3 |   | 10  20  30 |   | 11  22  33 |
| 4  5  6 | + | 10  20  30 | = | 14  25  36 |
```

每个现代框架都会自动执行此操作。当形状看起来错误但代码运行时，理解它可以防止混乱。

```figure
vector-projection
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-vector-class"></a>

### 第1步：向量类

```python
class Vector:
    def __init__(self, data):
        self.data = list(data)
        self.size = len(self.data)

    def __repr__(self):
        return f"Vector({self.data})"

    def __add__(self, other):
        return Vector([a + b for a, b in zip(self.data, other.data)])

    def __sub__(self, other):
        return Vector([a - b for a, b in zip(self.data, other.data)])

    def __mul__(self, scalar):
        return Vector([x * scalar for x in self.data])

    def dot(self, other):
        return sum(a * b for a, b in zip(self.data, other.data))

    def magnitude(self):
        return sum(x ** 2 for x in self.data) ** 0.5
```

<a id="step-2-matrix-class-with-core-operations"></a>

### 第2步：具有核心操作的矩阵类

```python
class Matrix:
    def __init__(self, data):
        self.data = [list(row) for row in data]
        self.rows = len(self.data)
        self.cols = len(self.data[0])
        self.shape = (self.rows, self.cols)

    def __repr__(self):
        rows_str = "\n  ".join(str(row) for row in self.data)
        return f"Matrix({self.shape}):\n  {rows_str}"

    def __add__(self, other):
        return Matrix([
            [self.data[i][j] + other.data[i][j] for j in range(self.cols)]
            for i in range(self.rows)
        ])

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

    def matmul(self, other):
        return Matrix([
            [
                sum(self.data[i][k] * other.data[k][j] for k in range(self.cols))
                for j in range(other.cols)
            ]
            for i in range(self.rows)
        ])

    def transpose(self):
        return Matrix([
            [self.data[j][i] for j in range(self.rows)]
            for i in range(self.cols)
        ])

    def determinant(self):
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

    def inverse_2x2(self):
        det = self.determinant()
        if det == 0:
            raise ValueError("Matrix is singular, no inverse exists")
        return Matrix([
            [self.data[1][1] / det, -self.data[0][1] / det],
            [-self.data[1][0] / det, self.data[0][0] / det]
        ])

    @staticmethod
    def identity(n):
        return Matrix([
            [1 if i == j else 0 for j in range(n)]
            for i in range(n)
        ])
```

<a id="step-3-see-it-work"></a>

### 第 3 步：看看它是否有效

```python
A = Matrix([[1, 2], [3, 4]])
B = Matrix([[5, 6], [7, 8]])

print("A + B =", (A + B).data)
print("A @ B =", A.matmul(B).data)
print("A^T =", A.transpose().data)
print("det(A) =", A.determinant())
print("A^-1 =", A.inverse_2x2().data)

I = Matrix.identity(2)
print("A @ A^-1 =", A.matmul(A.inverse_2x2()).data)
```

<a id="step-4-connect-to-neural-networks"></a>

### 第 4 步：连接到神经网络

```python
import random

inputs = Matrix([[0.5], [0.8], [0.2]])
weights = Matrix([
    [random.uniform(-1, 1) for _ in range(3)]
    for _ in range(2)
])
bias = Matrix([[0.1], [0.1]])

def relu_matrix(m):
    return Matrix([[max(0, val) for val in row] for row in m.data])

pre_activation = weights.matmul(inputs) + bias
output = relu_matrix(pre_activation)

print(f"Input shape: {inputs.shape}")
print(f"Weight shape: {weights.shape}")
print(f"Output shape: {output.shape}")
print(f"Output: {output.data}")
```

这是单个致密层：`output = relu(W @ x + b)`。每个神经网络中的每个密集层都执行此操作。

<a id="use-it"></a>

## 实际应用

NumPy 以更少的行数和更快的数量级完成上述所有操作。

```python
import numpy as np

A = np.array([[1, 2], [3, 4]])
B = np.array([[5, 6], [7, 8]])

print("A + B =\n", A + B)
print("A * B (element-wise) =\n", A * B)
print("A @ B (matrix multiply) =\n", A @ B)
print("A^T =\n", A.T)
print("det(A) =", np.linalg.det(A))
print("A^-1 =\n", np.linalg.inv(A))
print("I =\n", np.eye(2))

inputs = np.random.randn(3, 1)
weights = np.random.randn(2, 3)
bias = np.array([[0.1], [0.1]])
output = np.maximum(0, weights @ inputs + bias)

print(f"\nNeural network layer: {weights.shape} @ {inputs.shape} = {output.shape}")
print(f"Output:\n{output}")
```

Python中的`@`算子调用`__matmul__`。 NumPy 使用用 C 和 Fortran 编写的优化 BLAS 例程来实现它。同样的数学，速度快 100 倍。

在NumPy中广播：

```python
matrix = np.array([[1, 2, 3], [4, 5, 6]])
bias = np.array([10, 20, 30])
print(matrix + bias)
```

NumPy 自动在两行之间广播一维偏差。这就是偏差添加在每个神经网络框架中的工作原理。

<a id="ship-it"></a>

## 交付成果

本课程生成一个 prompt，用于通过几何直觉教授矩阵运算。参见 `outputs/prompt-matrix-operations.md`。

这里构建的 Matrix 类是我们在第 3 阶段第 10 课中构建的迷你神经网络框架的基础。

<a id="exercises"></a>

## 练习

1. **验证逆矩阵。** 乘以`A @ A.inverse_2x2()`并确认获得单位矩阵。尝试使用三个不同的 2x2 矩阵。当行列式为零时会发生什么？

2. **Implement 3x3 inverse.** 扩展 Matrix 类以使用 adjugate 方法计算 3x3 矩阵的逆。对照 NumPy 的 `np.linalg.inv` 进行测试。

3. **构建一个两层网络。** 仅使用 Matrix 类（无 NumPy），创建一个两层神经网络：输入 (3) -> 隐藏 (4) -> 输出 (2)。初始化随机 weights，运行 forward pass，并验证所有形状是否正确。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| 矢量 | “一支箭” | 有序的数字列表。在人工智能中：高维空间中的一个点。 |
| 矩阵 | “一张数字表” | 线性变换。它将向量从一个空间映射到另一个空间。 |
| 矩阵乘法 | “只需将数字相乘即可” | 第一个矩阵的每一行和第二个矩阵的每一列之间的点积。顺序很重要。 |
| 转置 | “翻转它” | 交换行和列。将 m x n 矩阵转换为 n x m。 backpropagation 中至关重要。 |
| 行列式 | “矩阵中的一些数字” | 测量矩阵缩放面积 (2D) 或体积 (3D) 的程度。零意味着转变破坏了一个维度。 |
| 逆 | “撤消矩阵” | 反转变换的矩阵。仅当行列式不为零时才存在。 |
| 单位矩阵 | 《无聊的矩阵》 | 相当于乘以 1 的矩阵。用于残差连接 (ResNets)。 |
| 广播 | 《神奇的形状固定》 | 通过沿着缺失的维度重复，拉伸较小的数组以匹配较大的数组。 |
| 逐元素 | 《正则乘法》 | 乘以匹配位置。两个数组必须具有相同的形状（或可广播）。 |

<a id="further-reading"></a>

## 进一步阅读

- [3Blue1Brown：线性代数的本质](https://www.3blue1brown.com/topics/linear-algebra) - 这里介绍的每个操作的视觉直觉
- [NumPy 广播文档](https://numpy.org/doc/stable/user/basics.broadcasting.html) - 确切规则 NumPy 如下
- [Stanford CS229 线性代数复习](http://cs229.stanford.edu/section/cs229-linalg.pdf) - ML 特定线性代数的简明参考
