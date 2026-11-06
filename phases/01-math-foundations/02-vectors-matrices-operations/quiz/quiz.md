# 测验 · 向量、矩阵和运算（Vectors, Matrices & Operations）

> **阶段 01 · 数学基础 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/matrices.py](../code/matrices.py) ｜ 代码讲解：[code/matrices.讲解.md](../code/matrices.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 形状（shape）是第一调试工具 | m×n 矩阵有 m 行 n 列；动手算之前先预测输出形状，能预测形状就说明理解了运算 |
| 2 | 矩阵乘法的形状规则 | `(m×n) @ (n×p) = (m×p)`，内侧维度必须相等；结果第 (i, j) 个元素 = A 第 i 行与 B 第 j 列的点积 |
| 3 | 逐元素乘 vs 矩阵乘 | 逐元素乘（Hadamard 积）要求同形状、对应位置相乘；矩阵乘是"行·列"点积，**不满足交换律** |
| 4 | 转置 | `Aᵀ[i][j] = A[j][i]`，m×n 变 n×m；`(AB)ᵀ = BᵀAᵀ`；反向传播中梯度要乘 `Wᵀ` |
| 5 | 行列式 | 2×2 时 `det = ad - bc`；几何上是面积/体积的缩放倍数；为 0 表示把空间压扁了一个维度 |
| 6 | 逆矩阵 | 撤销一次变换；仅当 `det ≠ 0` 时存在；2×2 公式是"主对角互换、副对角取负、再除以 det" |
| 7 | 单位矩阵 | 对角线为 1、其余为 0，相当于"乘以 1"；`I @ A = A`，与残差连接的"恒等映射"同一思想 |
| 8 | 广播（broadcasting） | 把较小数组沿缺失/长度为 1 的维度"拉伸"去匹配较大数组；bias 加法就靠它 |
| 9 | 全连接层 = `relu(W @ x + b)` | 一次矩阵乘、一次加偏置、一次逐元素激活，就是一层的完整前向传播 |

### 核心技能（能动手做到）

- [ ] 不用 NumPy，从零实现 `Matrix`：加、减、数乘、逐元素乘、矩阵乘、转置、行列式、2×2 逆、单位矩阵，并用 `np.allclose` 与 NumPy 结果对拍
- [ ] 手算 2×2 的矩阵乘、行列式、逆，并验证 `A @ A⁻¹ = I`
- [ ] 写任何矩阵代码前，先写出每一步的形状（如 `(4×3)@(3×1)+(4×1) → (4×1)`），并能根据 `shape mismatch` 报错定位是哪一维对不上
- [ ] 只用自己的 `Matrix` 类搭一个 3 → 4 → 2 的两层网络并跑通前向传播
- [ ] 用 NumPy 给 `(batch, features)` 和 `(features, batch)` 两种布局正确地加 bias，并能说出 `(n,)` 与 `(n,1)` 相减为什么会得到 `(n,n)`
- [ ] 能解释余子式展开求行列式为什么是 O(n!)，以及为什么工程上用 `solve` 而不是 `inv`

---

## 二、基础自测（选择题）

**Q1.** 全连接层权重 `W` 的形状为 `(128, 784)`（输出 128、输入 784），一个 batch 的输入 `X` 形状为 `(32, 784)`（每行一个样本）。下面哪个表达式能得到形状为 `(32, 128)` 的输出？

- A. `W @ X`
- B. `X @ W`
- C. `X @ W.T`
- D. `W.T @ X`

**Q2.** 设 `A = [[1,2],[3,4]]`，`B = [[5,6],[7,8]]`。下列说法正确的是：

- A. `A @ B` 与 `B @ A` 相等，因为两者都是 2×2
- B. 逐元素乘 `A * B` 与 `B * A` 相等，但 `A @ B ≠ B @ A`
- C. `A * B` 的结果是 `[[19,22],[43,50]]`
- D. 只要两个矩阵都是方阵，矩阵乘法就满足交换律

**Q3.** 矩阵 `[[2,1],[1,3]]` 作用在单位正方形上，得到的平行四边形面积是：

- A. 1
- B. 5
- C. 6
- D. 7

**Q4.** `A = [[4,7],[2,6]]` 的逆矩阵是：

- A. `[[0.6, 0.7], [0.2, 0.4]]`
- B. `[[6, -7], [-2, 4]]`
- C. `[[0.4, -0.7], [-0.2, 0.6]]`
- D. `[[0.6, -0.7], [-0.2, 0.4]]`

**Q5.** 在 NumPy 中，`x` 的形状为 `(2, 3)`。下列哪个加法会**报错**？

- A. `x + np.zeros(3)`
- B. `x + np.zeros((2, 1))`
- C. `x + np.zeros(2)`
- D. `x + np.zeros((1, 3))`

**Q6.** 若 `A` 是 2×3、`B` 是 3×4，则 `(A @ B)ᵀ` 等于：

- A. `Aᵀ @ Bᵀ`
- B. `Bᵀ @ Aᵀ`
- C. `B @ A`
- D. `A @ Bᵀ`

**Q7.** 本节代码中的 `determinant()` 对第一行做余子式展开并递归。对 n×n 矩阵，它的时间复杂度大约是：

- A. O(n²)
- B. O(n³)
- C. O(2ⁿ)
- D. O(n!)

---

## 三、动手 / 代码题

**Q8.** 下面是本节 `Matrix.__add__` 的实现。写出后续三行代码的结果（输出或异常），并指出它与 NumPy 广播规则相比"少支持"了什么。

```python
    def __add__(self, other):
        if isinstance(other, Matrix):
            if other.shape == self.shape:
                return Matrix([
                    [self.data[i][j] + other.data[i][j] for j in range(self.cols)]
                    for i in range(self.rows)
                ])
            if other.rows == 1 and other.cols == self.cols:
                return Matrix([
                    [self.data[i][j] + other.data[0][j] for j in range(self.cols)]
                    for i in range(self.rows)
                ])
            if other.cols == 1 and other.rows == self.rows:
                return Matrix([
                    [self.data[i][j] + other.data[i][0] for j in range(self.cols)]
                    for i in range(self.rows)
                ])
        raise ValueError(f"Cannot add shapes {self.shape} and {other.shape}")
```

```python
M = Matrix([[1, 2, 3], [4, 5, 6]])
print((M + Matrix([[10], [20]])).data)   # (a)
print((M + Matrix([[1, 1, 1]])).data)    # (b)
M + Matrix([[5]])                        # (c)
```

**Q9.** `__sub__` 和 `element_wise_multiply` 都**没有**做形状检查：

```python
    def element_wise_multiply(self, other):
        return Matrix([
            [self.data[i][j] * other.data[i][j] for j in range(self.cols)]
            for i in range(self.rows)
        ])
```

(1) `Matrix([[1,2],[3,4]]).element_wise_multiply(Matrix([[1,2,3],[4,5,6]]))` 会发生什么？反过来调用呢？
(2) 哪一种情况更危险？为什么？
(3) 给它加上与 `matmul` 风格一致的形状检查。

**Q10.** 讲义练习 2：用**伴随矩阵法（adjugate）**为 `Matrix` 实现 3×3 逆矩阵 `inverse_3x3(m)`，要求复用类里已有的 `determinant()`、`T`、`scalar_multiply()`，奇异矩阵抛 `ValueError`，并用 `np.linalg.inv` 验证 `A = [[1,2,3],[0,1,4],[5,6,0]]`。

---

## 四、面试高频题

**Q11.**（基础必考）矩阵乘法和逐元素乘法有什么区别？在 PyTorch/NumPy 中分别对应什么运算符？在 Transformer 里各举一个出现的位置。

**Q12.**（原理深挖）一个输入 784、输出 128 的全连接层，参数量是多少？batch=32 时一次前向传播大约多少 FLOPs？bias 在这里是怎么"加上去"的？

**Q13.**（工程实践）为什么工程上几乎不用 `np.linalg.inv(A) @ b` 解线性方程组？"行列式接近 0" 能用来判断矩阵是否接近奇异吗？

**Q14.**（追问型）讲讲 NumPy/PyTorch 的广播规则。写回归 loss 时 `pred` 形状是 `(N, 1)`、`y` 形状是 `(N,)`，`((pred - y) ** 2).mean()` 会出什么问题？

**Q15.**（工程实践）讲义里用列向量写 `W @ x`，而 PyTorch 的 `nn.Linear` 计算的是 `x @ W.T + b`。为什么框架要这样约定？`.T` 会不会拷贝数据？

---

## 五、参考答案与解析

### Q1 — 答案：C

`X @ W.T`：`(32×784) @ (784×128) = (32×128)`，内侧维度 784 = 784。
- A：`(128×784) @ (32×784)`，内侧 784 ≠ 32，报错。
- B：`(32×784) @ (128×784)`，内侧 784 ≠ 128，报错。
- D：`(784×128) @ (32×784)`，内侧 128 ≠ 32，报错。

这正是 PyTorch `nn.Linear` 的计算方式（见 Q15）。形状问题先写出 `(m×n)@(n×p)` 再看内侧维度，几秒钟就能排除错误选项。

### Q2 — 答案：B

逐元素乘就是对应位置的标量相乘，标量乘法可交换，所以 `A * B == B * A == [[5,12],[21,32]]`。矩阵乘：`A @ B = [[19,22],[43,50]]`，而 `B @ A = [[23,34],[31,46]]`，二者不同。A、D 错在"方阵乘法可交换"——方阵只保证形状上两种顺序都合法，不保证结果相同（几何上：先旋转再缩放 ≠ 先缩放再旋转）。C 把矩阵乘的结果安到了逐元素乘头上。

### Q3 — 答案：B

`det = 2·3 - 1·1 = 5`。行列式的绝对值就是单位正方形变换后的面积。C（6）是只乘了主对角线、忘了减 `bc`；D（7）是错把 `- bc` 写成 `+ bc`。

### Q4 — 答案：D

`det = 4·6 - 7·2 = 10`；2×2 逆 = `(1/det) · [[d, -b], [-c, a]] = (1/10)·[[6,-7],[-2,4]] = [[0.6,-0.7],[-0.2,0.4]]`，与代码运行结果一致。
- A：忘了副对角线取负。
- B：忘了除以 det（那是伴随矩阵，不是逆）。
- C：主对角线没有互换。

### Q5 — 答案：C

NumPy 广播从**最右侧（尾部）维度**开始对齐，每一维要么相等、要么其中一个为 1、要么缺失。`(2,3)` 与 `(2,)` 对齐后是比较 3 和 2，不相等且都不为 1，报 `operands could not be broadcast together`。A 中 `(3,)` 对齐最后一维 3，合法；B 中 `(2,1)` 的 1 被拉伸成 3；D 中 `(1,3)` 的 1 被拉伸成 2。想按行加一个长度为 2 的向量，要写成 `v[:, None]`（形状 `(2,1)`）。

### Q6 — 答案：B

`(AB)ᵀ = BᵀAᵀ`，顺序要反过来。形状验证：`AB` 是 2×4，转置后 4×2；`Bᵀ`(4×3) `@ Aᵀ`(3×2) = 4×2 ✔。A 的 `Aᵀ`(3×2) `@ Bᵀ`(4×3) 内侧维度 2 ≠ 4，根本不能乘。这个性质在反向传播推导 `∂L/∂x = Wᵀ · ∂L/∂y` 时会反复用到。

### Q7 — 答案：D

n×n 的行列式要展开成 n 个 (n-1)×(n-1) 子行列式，递推 `T(n) = n·T(n-1) + O(n²)`，总量级是 O(n!)。10×10 就是数百万次子问题，20×20 已经不可行。生产中用 LU 分解：`det = 主元乘积 × 行交换符号`，O(n³)。`np.linalg.det` 就是基于 LU 实现的。

### Q8 — 参考答案

```text
(a) [[11, 12, 13], [24, 25, 26]]
(b) [[2, 3, 4], [5, 6, 7]]
(c) ValueError: Cannot add shapes (2, 3) and (1, 1)
```

- (a) `other` 是 2×1 列向量，命中第三个分支：每一行 i 都加上 `other.data[i][0]`，第 0 行加 10、第 1 行加 20——这就是"每个输出神经元一个 bias"的列向量广播。
- (b) `other` 是 1×3 行向量，命中第二个分支：每一行都加上同一个 `[1,1,1]`。
- (c) 1×1 矩阵既不满足 `cols == self.cols`（1 ≠ 3），也不满足 `rows == self.rows`（1 ≠ 2），落到最后的 `raise`。

与 NumPy 相比，本实现**只支持三种情况**：同形状、1×n 行向量、m×1 列向量。少支持的有：①标量 / 1×1 广播到任意形状；②两边同时被拉伸（如 `(3,1) + (1,4) → (3,4)`）；③高维的尾部对齐规则。另外，如果 `other` 不是 `Matrix`（如 `M + 5`），`raise` 语句里访问 `other.shape` 会先抛 `AttributeError`，而不是预期的 `ValueError`——这是一个小瑕疵。

### Q9 — 参考答案

(1) 实测：
- `2×2 .element_wise_multiply(2×3)` 返回 `[[1, 4], [12, 20]]`——循环范围由 `self`（2×2）决定，只读取了 `other` 左上角的 2×2，**静默地丢掉了第 3 列**。
- 反过来 `2×3 .element_wise_multiply(2×2)` 在访问 `other.data[0][2]` 时抛 `IndexError: list index out of range`。

(2) 第一种更危险：程序不报错，结果"看起来正常"，bug 会一路传到下游（比如损失算错、梯度被截断）。第二种至少会立刻崩溃。工程上要"尽早失败（fail fast）"，形状检查宁可多做。

(3) 参考实现：

```python
    def element_wise_multiply(self, other):
        if self.shape != other.shape:
            raise ValueError(
                f"Cannot element-wise multiply shapes {self.shape} and {other.shape}"
            )
        return Matrix([
            [self.data[i][j] * other.data[i][j] for j in range(self.cols)]
            for i in range(self.rows)
        ])
```

`__sub__` 同理。更好的做法是写一个 `_check_same_shape(other, op_name)` 辅助方法复用。

### Q10 — 参考答案

思路：`A⁻¹ = adj(A) / det(A)`，其中 `adj(A) = Cᵀ`，余子式矩阵 `C[i][j] = (-1)^(i+j) · det(去掉第 i 行第 j 列的子矩阵)`。

```python
from matrices import Matrix
import numpy as np

def minor(m, row, col):
    return Matrix([
        [m.data[i][j] for j in range(m.cols) if j != col]
        for i in range(m.rows) if i != row
    ])

def inverse_3x3(m):
    if m.shape != (3, 3):
        raise ValueError("inverse_3x3 only works for 3x3 matrices")
    det = m.determinant()
    if abs(det) < 1e-10:
        raise ValueError("Matrix is singular, no inverse exists")
    cofactors = Matrix([
        [((-1) ** (i + j)) * minor(m, i, j).determinant() for j in range(3)]
        for i in range(3)
    ])
    adjugate = cofactors.T
    return adjugate.scalar_multiply(1 / det)

A = Matrix([[1, 2, 3], [0, 1, 4], [5, 6, 0]])
A_inv = inverse_3x3(A)
print(A_inv.data)
print(np.allclose(A_inv.data, np.linalg.inv(np.array(A.data))))
print(np.allclose((A @ A_inv).data, np.eye(3)))
```

实测输出：

```text
[[-24.0, 18.0, 5.0], [20.0, -15.0, -4.0], [-5.0, 4.0, 1.0]]
True
True
```

要点：①这个 A 的 `det = 1`，所以逆矩阵全是整数，便于手算核对；②容易错的地方是**忘记转置**余子式矩阵（`adj = Cᵀ` 而不是 `C`）和符号 `(-1)^(i+j)`；③伴随矩阵法同样是 O(n!) 级别，只适合教学，通用 n×n 应该用高斯-约当消元或 LU。

### Q11 — 参考回答要点

- **定义**：逐元素乘（Hadamard 积，`A ⊙ B`）要求形状相同（或可广播），对应位置相乘，形状不变；矩阵乘 `A @ B` 要求内侧维度相等，结果每个元素是"行·列"点积，`(m×n)@(n×p) → (m×p)`，不满足交换律。
- **运算符**：NumPy/PyTorch 中 `*` 是逐元素乘，`@`（`np.matmul` / `torch.matmul`）是矩阵乘。Python 的 `@` 调用对象的 `__matmul__`，本节 `Matrix` 也实现了它。
- **Transformer 中的例子**：
  - 矩阵乘：`Q = XW_Q`、注意力分数 `QKᵀ`、`softmax(...) @ V`、FFN 的两层线性变换。
  - 逐元素乘：LayerNorm 中的 `γ ⊙ x̂`、dropout 乘掩码、SwiGLU/GLU 中的门控 `σ(xW) ⊙ (xV)`。
- **常见误区**：把 `*` 当矩阵乘用。若两个矩阵恰好同形状（比如都是方阵），代码不会报错但结果完全错误——这是新手最常见的静默 bug。

### Q12 — 参考回答要点

- **参数量**：权重 `128 × 784 = 100,352`，偏置 128，共 **100,480**。
- **FLOPs**：一次矩阵乘 `(m×n)@(n×p)` 约 `2·m·n·p` 次浮点运算（每个乘加算 2 次）。batch=32 时 `2 × 32 × 784 × 128 ≈ 6.4M` FLOPs；加 bias 和 ReLU 是 O(32×128)，可忽略。
- **bias 的加法**：单样本时 `W @ x` 是 `(128×1)`，b 也是 `(128×1)`，直接相加。批量时输出是 `(32×128)`（行为样本）或 `(128×32)`（列为样本），而 b 只有 128 个数——靠**广播**把同一个 b 复制到每个样本上；列为样本的布局里要写成 `b[:, None]`（`(128,1)`）。所有样本共享同一组 bias，这也是 bias 参数量只有 128 而不是 128×32 的原因。
- **加分点**：能说出矩阵乘的计算量和参数量"一大一小"——大模型推理里 `FLOPs ≈ 2 × 参数量 × token 数` 这个经验公式就是从这里来的。

### Q13 — 参考回答要点

- **不用 `inv` 的原因**：
  1. **计算量**：求逆约 O(n³)，再乘向量；而 `np.linalg.solve` 用 LU 分解 + 前代/回代，同样 O(n³) 但常数更小，且不需要形成整个逆矩阵。
  2. **数值精度**：显式求逆会放大舍入误差，`solve` 的结果残差更小。
  3. 多个右端项时，可以对 A 做一次 LU 分解后反复复用。
- **行列式不是好的奇异性指标**：行列式随缩放剧烈变化。例如 `0.1·I`（100×100）的行列式是 `1e-100`，看起来"几乎为 0"，但它完全良态（条件数 = 1）；反过来，一个病态矩阵的行列式可以很大。判断"接近奇异"应该用**条件数**（`np.linalg.cond`，最大/最小奇异值之比）或最小奇异值。
- 本节 `inverse_2x2` 用 `abs(det) < 1e-10` 判断奇异，是一种教学简化，适用于数值量级正常的小矩阵。
- **加分点**：提到 `lstsq`（最小二乘）和伪逆 `pinv` 用于非方阵/秩亏情况。

### Q14 — 参考回答要点

- **规则**：
  1. 从**最右边的维度**开始逐维对齐，维数少的一方在左边补 1；
  2. 每一维要么相等，要么其中一个为 1（被拉伸），否则报错；
  3. 结果每一维取两者中较大的那个。拉伸不会真的复制内存（stride 为 0 的"虚拟复制"）。
- **经典坑**：`pred` 是 `(N,1)`，`y` 是 `(N,)`，补齐后变成 `(N,1)` 与 `(1,N)`，两边都被拉伸，`pred - y` 的形状是 **`(N, N)`**！loss 变成"每个预测和所有标签两两相减"的平均值，代码不报错，但模型学不好、显存还暴涨。
- **防御**：
  - 计算前 `y = y.reshape(-1, 1)` 或 `pred = pred.squeeze(-1)`；
  - 关键位置写 `assert pred.shape == y.shape`；
  - PyTorch 的 `nn.MSELoss` 在形状不一致时会给出 warning，别忽略。
- **加分点**：能说出 `keepdims=True` 的作用——归一化时 `x - x.mean(axis=1, keepdims=True)` 保留 `(N,1)` 形状，才能按行正确广播。

### Q15 — 参考回答要点

- **约定差异**：数学教材习惯列向量 `y = Wx`；而数据在内存里通常按"一行一个样本"存成 `(batch, in_features)`，所以框架写成 `y = x @ Wᵀ + b`，输出 `(batch, out_features)`，bias 的形状 `(out_features,)` 刚好沿尾部维度广播。`nn.Linear` 的 `weight` 形状是 `(out_features, in_features)`，与数学写法 `W` 保持一致，所以计算时要转置。
- **`.T` 会不会拷贝**：在 NumPy 和 PyTorch 中，转置只是交换 shape 和 stride，返回的是**视图（view）**，O(1)、不拷贝数据。代价是视图可能变成非连续（non-contiguous）内存，某些操作（如 PyTorch 的 `.view()`）会要求先 `.contiguous()`。BLAS/cuBLAS 的 GEMM 接口本身支持"转置标志"，所以 `x @ W.T` 不会额外搬运数据。
- 本节的纯 Python `transpose()` 则会真的新建一个列表的列表，O(m·n)——教学实现和工业实现的差别正在于此。
- **常见误区**：认为 `W.T` 每次都要付出一次完整复制的代价，或者把 `nn.Linear(in, out)` 的权重形状记成 `(in, out)`。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 01 线性代数直觉](../../01-linear-algebra-intuition/docs/zh.md)：向量、点积、矩阵即变换、秩。本节把这些直觉落实为可运行的运算。
- Python 基础：类、列表推导式、运算符重载（`__add__`、`__matmul__`）。

### 本节被哪些后续内容用到
- [阶段 01 · 03 矩阵变换](../../03-matrix-transformations/docs/zh.md)：用本节的矩阵乘法做旋转、缩放、剪切，并引入特征值。
- [阶段 01 · 12 Tensor 操作](../../12-tensor-operations/docs/zh.md)：把二维矩阵与广播推广到任意维张量。
- [阶段 01 · 17 线性系统](../../17-linear-systems/docs/zh.md)：逆矩阵之外的 LU / QR / 最小二乘求解方法。
- [阶段 03 · 02 多层网络](../../../03-deep-learning-core/02-multi-layer-networks/docs/zh.md)：把本节的"矩阵乘 + 偏置 + 激活"一层层堆叠成多层网络。
- [阶段 03 · 03 反向传播](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：为这些网络计算梯度，让权重矩阵可以被训练。
- [阶段 03 · 10 迷你框架](../../../03-deep-learning-core/10-mini-framework/docs/zh.md)：讲义提到本节的 `Matrix` 类是这个迷你神经网络框架的基础。
- [阶段 07 · 02 从零实现 Self-Attention](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：`QKᵀ`、`softmax(·) @ V` 全是本节的矩阵乘与形状推导。

### 延伸关键词
`Hadamard 积` · `BLAS / GEMM` · `LU 分解` · `条件数` · `stride 与 contiguous` · `einsum` · `keepdims` · `残差连接（ResNet）`
