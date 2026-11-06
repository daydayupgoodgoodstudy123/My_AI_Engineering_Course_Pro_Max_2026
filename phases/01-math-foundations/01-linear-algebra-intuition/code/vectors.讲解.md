# 代码讲解 · vectors.py

> **所属小节**：阶段 01 · 数学基础 · 第 01 节 线性代数直觉 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python vectors.py` ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy

---

## 1. 这份代码在考察什么

这份代码的目的不是"造一个好用的线性代数库"（NumPy 早就有了），而是逼你**亲手把每个运算拆到最底层的加法和乘法**，从而真正理解：

1. **向量运算的定义**：加减、数乘、点积、模长、归一化到底是怎么一个分量一个分量算出来的。
2. **几何意义**：点积 → 相似度/夹角；投影 → 分解出"沿某方向的分量"；Gram-Schmidt → 把任意基变成正交基。
3. **矩阵 = 变换**：`Matrix @ Vector` 就是神经网络的一层；矩阵乘法的三重循环就是 GPU 每天在做的事。
4. **秩与线性无关**：用行化简（高斯-约当消元）判断"这组向量到底提供了几个独立方向"。
5. **数值计算意识**：浮点数不能用 `== 0` 判断，需要容差 `1e-10`；`acos` 的输入需要夹紧到 [-1, 1]。

> 一句话：**先从零手写一遍，再用 NumPy 一行搞定**——这样你在面试或排查模型 bug 时，能说清 NumPy/PyTorch 底层发生了什么。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应的数学概念 |
|---------|------|------|---------------|
| `Vector` | 类 | 表示 n 维向量，支持 `+ - *`、点积、模长、归一化、余弦相似度、夹角、投影 | 向量空间的基本运算 |
| `is_independent(vectors)` | 函数 | 用行化简求秩，判断一组向量是否线性无关 | 线性无关、秩 |
| `gram_schmidt(vectors)` | 函数 | 把一组向量变成标准正交基 | 正交投影、QR 分解的核心 |
| `Matrix` | 类 | 表示矩阵，支持 `@`（矩阵乘）、转置、求秩 | 线性变换 |
| `if __name__ == "__main__":` | 演示入口 | 依次演示上面所有功能并打印结果 | — |

调用关系很简单：`gram_schmidt` 依赖 `Vector.project_onto`、`-`、`magnitude`、`normalize`；`Matrix.__matmul__` 在右侧是向量时返回 `Vector`。

---

## 3. 逐段精讲

### 3.1 `Vector` 的构造：把输入"复制"成列表

```python
class Vector:
    def __init__(self, components):
        self.components = list(components)
        self.dim = len(self.components)
```

- `list(components)` 有两个作用：①接受任何可迭代对象（列表、元组、生成器都行）；②**复制一份**，避免外部修改原列表时连带改了向量内部数据（防御式编程）。
- `self.dim` 缓存维度，后面 `is_independent` 会用到。

### 3.2 运算符重载：让 `a + b` 直接可用

```python
    def __add__(self, other):
        return Vector([a + b for a, b in zip(self.components, other.components)])

    def __sub__(self, other):
        return Vector([a - b for a, b in zip(self.components, other.components)])

    def __mul__(self, scalar):
        return Vector([x * scalar for x in self.components])
```

- Python 看到 `a + b` 时会调用 `a.__add__(b)`，这叫**运算符重载**。这样写出来的代码和数学公式长得一样，可读性极高——这也是 NumPy、PyTorch 的设计思路。
- `zip` 把两个列表"拉链式"配对：`zip([1,2,3],[4,5,6]) → (1,4),(2,5),(3,6)`，正好实现逐分量运算。
- 每个运算都**返回新的 `Vector`**，不修改自身（不可变风格），避免"算着算着原向量被改了"的隐蔽 bug。
- ⚠️ 设计上的简化：`zip` 遇到长度不同的列表会**静默截断**到较短的那个，不会报错。生产代码应先检查 `self.dim == other.dim`（或在 Python 3.10+ 用 `zip(..., strict=True)`）。
- `__mul__` 只支持 `向量 * 数`，`3 * v` 会报错，因为没有实现 `__rmul__`。

### 3.3 点积、模长、归一化、余弦相似度

```python
    def dot(self, other):
        return sum(a * b for a, b in zip(self.components, other.components))

    def magnitude(self):
        return sum(x**2 for x in self.components) ** 0.5

    def normalize(self):
        mag = self.magnitude()
        return Vector([x / mag for x in self.components])

    def cosine_similarity(self, other):
        return self.dot(other) / (self.magnitude() * other.magnitude())
```

| 方法 | 公式 | AI 中的用途 |
|------|------|------------|
| `dot` | `a·b = Σ aᵢbᵢ` | attention 分数、向量检索打分 |
| `magnitude` | `|a| = √(Σ aᵢ²)` | L2 范数、梯度裁剪 |
| `normalize` | `â = a / |a|` | embedding 归一化后，点积 = 余弦 |
| `cosine_similarity` | `a·b / (|a||b|)` | RAG、推荐系统的相似度 |

- `sum(... for ...)` 是**生成器表达式**，不会创建中间列表，比 `sum([...])` 更省内存。
- `** 0.5` 等价于开平方，省去 `import math`。
- `normalize` 先把 `mag` 存进局部变量，避免在列表推导里对每个分量重复计算模长（O(n) → O(n²) 的低级性能坑）。
- ⚠️ 零向量的 `normalize` / `cosine_similarity` 会触发 `ZeroDivisionError`——这里刻意没处理，保持代码简洁；面试时要能主动指出。

### 3.4 夹角：为什么要夹紧到 [-1, 1]

```python
    def angle_between(self, other):
        import math
        cos_theta = self.cosine_similarity(other)
        cos_theta = max(-1.0, min(1.0, cos_theta))
        return math.degrees(math.acos(cos_theta))
```

- 浮点误差可能让 `cos_theta` 变成 `1.0000000000000002`，而 `math.acos` 的定义域是 [-1, 1]，超出就抛 `ValueError: math domain error`。`max(-1, min(1, x))` 是经典的 **clamp（夹紧）** 写法。
- `math.acos` 返回弧度，`math.degrees` 转成角度，方便人读。
- `import math` 写在函数内部是为了让这个方法"自给自足"，演示用没问题；工程中通常放到文件顶部。

### 3.5 投影

```python
    def project_onto(self, other):
        scalar = self.dot(other) / other.dot(other)
        return Vector([scalar * x for x in other.components])
```

- 公式 `proj_b(a) = (a·b / b·b) · b`。用 `b·b` 而不是 `|b|²` 是因为两者相等，但前者**不需要开方再平方**，更快也更精确。
- 投影结果一定与 `other` 同方向；`self - 投影` 的残差一定与 `other` 正交——演示部分打印的 `residual dot b = 0.000000` 正是在验证这一点。

### 3.6 `is_independent`：用高斯-约当消元求秩

```python
def is_independent(vectors):
    n = len(vectors)
    if n == 0:
        return True
    dim = vectors[0].dim
    rows = [v.components[:] for v in vectors]   # 每个向量当一行，并复制
    rank = 0
    for col in range(dim):                       # 逐列找主元
        pivot = None
        for row in range(rank, len(rows)):
            if abs(rows[row][col]) > 1e-10:      # 浮点容差判断"非零"
                pivot = row
                break
        if pivot is None:
            continue                             # 这一列没有主元，跳过
        rows[rank], rows[pivot] = rows[pivot], rows[rank]   # 交换到当前行
        scale = rows[rank][col]
        rows[rank] = [x / scale for x in rows[rank]]        # 主元归一为 1
        for row in range(len(rows)):                        # 消去其他行该列
            if row != rank and abs(rows[row][col]) > 1e-10:
                factor = rows[row][col]
                rows[row] = [rows[row][j] - factor * rows[rank][j] for j in range(dim)]
        rank += 1
    return rank == n
```

核心思想：**能找到几个主元（pivot），秩就是几**。如果秩等于向量个数，说明没有任何一个向量是"多余的"，即线性无关。

- `v.components[:]` 用切片做**浅拷贝**，保证消元过程不会破坏原始向量。
- `rows[a], rows[b] = rows[b], rows[a]` 是 Python 的**元组解包交换**，不需要临时变量。
- 为什么用 `1e-10` 而不是 `!= 0`：经过多次除法、减法后，理论上为 0 的值往往是 `1e-17` 这样的"浮点噪声"。
- 设计取舍：这里选择"找到第一个非零元素"作主元。数值更稳定的做法是**部分主元法**（选该列绝对值最大的元素），可以减小舍入误差。更进一步，`np.linalg.matrix_rank` 干脆不用消元，而是用 SVD 数"大于阈值的奇异值个数"，对病态矩阵更可靠。

### 3.7 `gram_schmidt`：正交化

```python
def gram_schmidt(vectors):
    orthonormal = []
    for v in vectors:
        w = v
        for u in orthonormal:
            proj = w.project_onto(u)
            w = w - proj                 # 去掉在已有方向上的分量
        if w.magnitude() < 1e-10:
            continue                     # 线性相关的向量，剩下的是 0，丢弃
        orthonormal.append(w.normalize())
    return orthonormal
```

- 每处理一个新向量，就把它在**所有已得到的正交方向**上的投影减掉，剩下的部分自然与它们都正交，再归一化。
- 注意这里用的是 `w.project_onto(u)`（基于**已更新的 w**），这其实是**修正 Gram-Schmidt（Modified Gram-Schmidt）**的写法，比教科书上的"经典版"（总是用原始 `v` 去投影）数值上更稳定。这是一个很好的面试加分点。
- 输出向量的个数 = 输入向量组的秩，所以它也顺带能用来"求秩"。

### 3.8 `Matrix`：矩阵乘法与转置

```python
class Matrix:
    def __init__(self, rows):
        self.rows = [list(row) for row in rows]
        self.shape = (len(self.rows), len(self.rows[0]))

    def __matmul__(self, other):
        if isinstance(other, Vector):
            return Vector([
                sum(self.rows[i][j] * other.components[j] for j in range(self.shape[1]))
                for i in range(self.shape[0])
            ])
        rows = []
        for i in range(self.shape[0]):
            row = []
            for j in range(other.shape[1]):
                row.append(sum(
                    self.rows[i][k] * other.rows[k][j]
                    for k in range(self.shape[1])
                ))
            rows.append(row)
        return Matrix(rows)
```

- `@` 是 Python 3.5 引入的**矩阵乘法运算符**，对应魔术方法 `__matmul__`。NumPy 和 PyTorch 都用它。
- `isinstance(other, Vector)` 让同一个 `@` 同时支持"矩阵×向量"和"矩阵×矩阵"——这是一种简单的**多态分派**。
- 矩阵×矩阵就是教科书的三重循环：`C[i][j] = Σₖ A[i][k]·B[k][j]`，时间复杂度 O(m·n·p)。真实框架会用分块、SIMD、GPU 并行来加速，但数学完全一样。
- `self.shape` 用元组 `(行数, 列数)`，命名与 NumPy 保持一致，降低迁移成本。
- 简化之处：没有检查 `self.shape[1] == other.shape[0]`，维度不匹配时会抛 `IndexError` 而不是友好的错误信息。

```python
    def transpose(self):
        return Matrix([
            [self.rows[j][i] for j in range(self.shape[0])]
            for i in range(self.shape[1])
        ])
```

- **嵌套列表推导**：外层遍历新矩阵的行（原矩阵的列 `i`），内层遍历新矩阵的列（原矩阵的行 `j`），实现 `Aᵀ[i][j] = A[j][i]`。
- `Matrix.rank()` 与 `is_independent` 是同一套消元逻辑，只是返回秩本身。（重复代码是为了让每段都能单独阅读，工程上应抽成一个公共函数。）

### 3.9 演示入口：`if __name__ == "__main__":`

只有**直接运行**这个文件时才执行演示代码；被别的文件 `import` 时不会执行。这样同一个文件既是"库"又是"示例"。最后一段用随机权重的 2×3 矩阵乘以 3 维输入，直观展示"一层神经网络 = 一次矩阵乘法"。`random.seed(42)` 固定随机种子，保证每次运行结果一致、可复现。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python、不用 NumPy | 每个运算都看得见，便于理解 | 慢 100 倍以上；生产中用 NumPy/PyTorch |
| 运算符重载（`+ - * @`） | 代码像数学公式，与 NumPy 用法一致 | 需要了解魔术方法 |
| 每次运算返回新对象 | 无副作用，不易出 bug | 频繁创建对象，有内存开销 |
| 容差 `1e-10` | 浮点数不能精确比较 0 | 容差应随数据量级调整（相对容差） |
| 不做维度/零向量检查 | 保持代码短小、聚焦核心概念 | 生产代码必须校验并抛出清晰异常 |
| 修正 Gram-Schmidt | 数值更稳定 | 生产中直接用 Householder QR（`np.linalg.qr`） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `class` 与 `__init__` | `class Vector: def __init__(self, components)` | 定义类与构造函数；`self` 指向实例本身 |
| 魔术方法 / 运算符重载 | `__add__`、`__sub__`、`__mul__`、`__matmul__`、`__repr__` | 让 `+ - * @` 和 `print()` 作用于自定义对象 |
| `__repr__` | `return f"Vector({self.components})"` | 决定对象打印出来的样子，方便调试 |
| 列表推导式 | `[x * scalar for x in self.components]` | 一行生成新列表，比 `for + append` 简洁 |
| 生成器表达式 | `sum(a * b for a, b in zip(...))` | 不建中间列表，按需产生元素 |
| `zip` | `zip(self.components, other.components)` | 把多个序列按位置配对 |
| 元组解包 | `for a, b in zip(...)`；`rows[a], rows[b] = rows[b], rows[a]` | 一次给多个变量赋值，交换无需临时变量 |
| 切片拷贝 | `v.components[:]`、`row[:]` | 复制列表（浅拷贝） |
| 幂运算 | `x**2`、`** 0.5` | 平方与开方 |
| `isinstance` | `isinstance(other, Vector)` | 运行时判断类型 |
| `None` 哨兵值 | `pivot = None ... if pivot is None` | 用 `None` 标记"没找到"；判断用 `is None` 而不是 `== None` |
| `break` / `continue` | 找到主元就 `break`；没主元就 `continue` | 提前结束循环 / 跳过本轮 |
| f-string 格式化 | `f"{a.magnitude():.4f}"`、`f"{{e1, e2}}"` | `:.4f` 保留 4 位小数；`{{ }}` 输出字面量花括号 |
| `enumerate` | `for i, vec in enumerate(basis)` | 同时拿到下标和元素 |
| `if __name__ == "__main__":` | 文件末尾 | 区分"直接运行"和"被导入" |
| 函数内 `import` | `angle_between` 里的 `import math` | 合法，但通常放在文件顶部 |

---

## 6. 运行结果解读

```text
a · b = 32                          ← 1·4 + 2·5 + 3·6
|a| = 3.7417                        ← √14
cosine_similarity(a, b) = 0.9746    ← 方向非常接近
Rotate Vector([3, 1]) by 90° → Vector([-1, 3])   ← 旋转矩阵 [[0,-1],[1,0]]
proj_b(a) = Vector([3.0, 0.0])      ← 只保留 x 分量
residual dot b = 0.000000           ← 残差与 b 正交 ✔
{e1, e2, 2*e1+e2} independent: False
u1 dot u2 = 0.000000 ... |u3| = 1.000000   ← Gram-Schmidt 输出两两正交、模长为 1 ✔
[[1,2],[2,4]] rank: 1               ← 第二行是第一行的 2 倍
Output (2D): Vector([-0.0197..., 0.1087...])   ← 3 维输入 → 2 维输出，一层网络
```

---

## 7. 动手改一改

1. 给 `Vector` 加上 `__rmul__ = __mul__`，让 `3 * v` 也能工作；再加 `__eq__`，用容差比较两个向量是否相等。
2. 在 `__add__` 里加维度检查：维度不同时 `raise ValueError(...)`。
3. 让 `normalize` 遇到零向量时抛出带说明的异常，而不是 `ZeroDivisionError`。
4. 把 `is_independent` 和 `Matrix.rank` 的公共逻辑抽成 `_row_reduce(rows)`，消除重复代码。
5. 把主元选择改成"部分主元法"（选绝对值最大的），对比一个病态矩阵（如 `[[1e-12, 1], [1, 1]]`）上的结果。
6. 用 `time.perf_counter()` 对比你的 `Matrix @ Matrix` 与 `np.array @ np.array` 在 200×200 矩阵上的速度差距。

---

## 8. 常见坑

- **用 `==` 比较浮点数**：`0.1 + 0.2 == 0.3` 是 `False`。用容差：`abs(x - y) < 1e-9`，或 `math.isclose`。
- **`zip` 静默截断**：维度不同的向量相加不会报错，结果却是错的。
- **零向量归一化**：除以 0。
- **列表的浅拷贝 vs 引用**：`rows = vectors_list` 只复制引用，修改 `rows` 会改坏原数据；本代码用 `[:]` 和 `list()` 规避了这一点。
- **`acos` 定义域**：忘记 clamp，在 `cos=1` 附近随机报错，非常难复现。
