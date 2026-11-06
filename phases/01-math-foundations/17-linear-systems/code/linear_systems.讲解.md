# 代码讲解 · linear_systems.py

> **所属小节**：阶段 01 · 数学基础 · 第 17 节 线性系统 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python linear_systems.py`（无命令行参数） ｜ **依赖**：`numpy`；`scikit-learn` 可选（仅用于对比，缺失时打印安装提示后继续运行）

---

## 1. 这份代码在考察什么

这份代码把"解 `Ax = b`"这件事拆成了几乎所有主流方法，每个都从零手写，再和 NumPy / sklearn 对答案。学习目标是：

1. **直接法的骨架**：高斯消元 = 消成上三角 + 回代；LU = 把消元过程"存下来"复用；Cholesky = 对称正定时的"半价 LU"。
2. **数值稳定意识**：部分主元、奇异判定阈值、`log det` 在对数域里算——这些都是"公式对但浮点下会翻车"的地方。
3. **最小二乘 = 线性回归**：正规方程 `AᵀAx = Aᵀb` 和 `np.linalg.lstsq`、`sklearn.LinearRegression` 给出同一组权重。
4. **正则化的数值意义**：岭回归加 `λI` 后矩阵必然对称正定，可以用 Cholesky，且条件数大幅下降。
5. **迭代法**：共轭梯度只用矩阵-向量乘，收敛快慢由条件数决定。

> 一句话：**同一个方程，七八种解法，各自的前提、代价和稳定性不同**——面试问"线性回归怎么解"时，你要能把这张地图讲出来。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `gaussian_elimination(A, b)` | 函数 | 增广矩阵 + 部分主元消元 + 回代 | 高斯消元、回代 |
| `lu_decompose(A)` | 函数 | 返回 `P, L, U`，满足 `PA = LU` | LU 分解、置换矩阵 |
| `lu_solve(P, L, U, b)` | 函数 | 前代解 `Ly = Pb`，回代解 `Ux = y` | 复用分解，O(n²) 求解 |
| `cholesky(A)` | 函数 | 求下三角 L，使 `A = LLᵀ` | Cholesky 分解 |
| `cholesky_solve(L, b)` | 函数 | 前代解 `Ly = b`，回代解 `Lᵀx = y` | 三角求解 |
| `least_squares_normal(A, b)` | 函数 | 形成 `AᵀA`、`Aᵀb`，再用高斯消元解 | 正规方程 / OLS |
| `ridge_regression(A, b, lam)` | 函数 | 解 `(AᵀA + λI)x = Aᵀb`，用 Cholesky | 岭回归 |
| `condition_number(A)` | 函数 | 用 SVD 算 `σ_max/σ_min` | 条件数 |
| `conjugate_gradient(A, b, ...)` | 函数 | 迭代求解对称正定系统，返回 `(x, 迭代次数)` | 共轭梯度 |
| `demo_*`（9 个） | 演示函数 | 每个演示一个主题并与 NumPy / sklearn 对比 | — |
| `if __name__ == "__main__":` | 入口 | 依次调用 9 个 demo | — |

调用关系：`least_squares_normal → gaussian_elimination`；`ridge_regression → cholesky + cholesky_solve`；`lu_solve` 依赖 `lu_decompose` 的输出；所有 demo 都以"我们的结果 vs NumPy/sklearn"的形式输出误差。

---

## 3. 逐段精讲

### 3.1 高斯消元：增广矩阵 + 部分主元 + 回代

```python
def gaussian_elimination(A, b):
    n = len(b)
    Ab = np.hstack([A.astype(float), b.reshape(-1, 1).astype(float)])

    for k in range(n):
        max_row = k + np.argmax(np.abs(Ab[k:, k]))
        Ab[[k, max_row]] = Ab[[max_row, k]]

        if abs(Ab[k, k]) < 1e-12:
            raise ValueError(f"Matrix is singular at pivot {k}")

        for i in range(k + 1, n):
            m = Ab[i, k] / Ab[k, k]
            Ab[i, k:] -= m * Ab[k, k:]

    x = np.zeros(n)
    for i in range(n - 1, -1, -1):
        x[i] = (Ab[i, -1] - Ab[i, i + 1 : n] @ x[i + 1 : n]) / Ab[i, i]

    return x
```

**做了什么**

- **增广矩阵** `[A | b]`：`b.reshape(-1, 1)` 把一维 b 变成列向量，`np.hstack` 横向拼接。这样行交换、行相减时 b 自动跟着变，不用单独维护。`astype(float)` 既把整数矩阵转成浮点（否则整数除法 / 原地减法会出错），又**复制了一份**，不会改坏调用方传入的 A。
- **部分主元**：`np.argmax(np.abs(Ab[k:, k]))` 在第 k 列、第 k 行及以下找绝对值最大的元素。注意 `argmax` 返回的是**子数组里的下标**，所以要 `k +` 才是全局行号。
- **行交换** `Ab[[k, max_row]] = Ab[[max_row, k]]`：花式索引（fancy indexing）在右侧会生成一个**副本**，所以能一次完成交换。`k == max_row` 时是无害的空操作。
- **奇异判定**：选完主元后最大的那个都 `< 1e-12`，说明这一列已经没有可用主元，矩阵（数值上）奇异。
- **消元**：`Ab[i, k:] -= m * Ab[k, k:]` 一次处理一整行的切片（从第 k 列开始，前面已经是 0 了，不用再算），是向量化的写法。
- **回代**：从最后一行往上，`x[i] = (cᵢ − Σⱼ>ᵢ Uᵢⱼxⱼ) / Uᵢᵢ`。`Ab[i, i+1:n] @ x[i+1:n]` 就是那个求和；`Ab[i, -1]` 是增广列里的右端项。

**为什么这样设计**

- 部分主元让每个乘子 `|m| ≤ 1`，误差不会被放大——讲义里 `0.001` 主元的例子说明了不选主元的风险。
- 消元只处理"下方"（得到上三角），而不是像 Gauss-Jordan 那样把上方也消掉，因为回代只要 O(n²)，比继续消元便宜。

⚠️ 刻意的简化：
- `1e-12` 是**绝对**阈值，矩阵整体很小（如所有元素 ~1e-13）时会误报奇异；更合理的是相对阈值（与矩阵范数成比例）。
- 主元列下方的元素理论上被消成 0，浮点下可能残留 1e-17 级别的数，但回代从不读取对角线以下，所以无影响。

### 3.2 LU 分解：把消元过程"存下来"

```python
def lu_decompose(A):
    n = A.shape[0]
    L = np.eye(n)
    U = A.astype(float).copy()
    P = np.eye(n)

    for k in range(n):
        max_row = k + np.argmax(np.abs(U[k:, k]))
        if max_row != k:
            U[[k, max_row]] = U[[max_row, k]]
            P[[k, max_row]] = P[[max_row, k]]
            if k > 0:
                L[[k, max_row], :k] = L[[max_row, k], :k]

        for i in range(k + 1, n):
            L[i, k] = U[i, k] / U[k, k]
            U[i, k:] -= L[i, k] * U[k, k:]

    return P, L, U
```

- 和高斯消元几乎一模一样，区别是：①不带 b；②每个乘子 `m` 存进 `L[i, k]`；③每次行交换同时记录在置换矩阵 `P` 里。最终 `PA = LU`。
- `L` 从单位阵开始，所以对角线天然是 1（**单位下三角**），后面前代时不用除法。
- **为什么 L 只交换前 k 列**：前 k 列是之前已经算好的乘子，它们属于"行"，行换了乘子也要跟着换；第 k 列及之后还没填（只有对角线的 1），整行交换会把对角线 1 换走。
- ⚠️ 与讲义例子的差别：讲义手算的 `L = [[1,0,0],[2,1,0],[1,2,1]]` 是**不选主元**的结果；代码选了主元，`U` 第一行变成 `[4, 3, 3]`，乘子都满足 `|Lᵢⱼ| ≤ 1`。两者都正确，解出来都是 `[2, 2, 2]`。
- 小细节：`A.astype(float)` 已经返回副本，后面的 `.copy()` 是多余的（无害）。
- ⚠️ 这里**没有奇异检查**：遇到全零主元列会 `U[k, k] = 0` 导致除零，得到 `inf/nan`。

```python
def lu_solve(P, L, U, b):
    n = len(b)
    Pb = P @ b.astype(float)

    y = np.zeros(n)
    for i in range(n):
        y[i] = Pb[i] - L[i, :i] @ y[:i]

    x = np.zeros(n)
    for i in range(n - 1, -1, -1):
        x[i] = (y[i] - U[i, i + 1 :] @ x[i + 1 :]) / U[i, i]

    return x
```

- `Ax = b` ⇔ `PAx = Pb` ⇔ `LUx = Pb`。令 `y = Ux`：先**前代**（从上往下）解 `Ly = Pb`，再**回代**（从下往上）解 `Ux = y`。两步各 O(n²)。
- 前代没有除以 `L[i, i]`，因为单位下三角的对角线是 1。
- `i = 0` 时 `L[0, :0] @ y[:0]` 是两个空数组的点积，NumPy 返回 `0.0`，所以不需要特判。
- 工程中 `P` 不会存成 n×n 矩阵（太浪费），而是存一个长度 n 的置换下标数组；`P @ b` 就变成 `b[perm]`。

### 3.3 Cholesky：对称正定矩阵的"平方根"

```python
def cholesky(A):
    n = A.shape[0]
    L = np.zeros_like(A, dtype=float)

    for i in range(n):
        for j in range(i + 1):
            s = A[i, j] - L[i, :j] @ L[j, :j]
            if i == j:
                if s <= 0:
                    raise ValueError("Matrix is not positive definite")
                L[i, j] = np.sqrt(s)
            else:
                L[i, j] = s / L[j, j]

    return L
```

- 直接对照公式：`Lᵢᵢ = √(Aᵢᵢ − Σₖ<ᵢ Lᵢₖ²)`，`Lᵢⱼ = (Aᵢⱼ − Σₖ<ⱼ LᵢₖLⱼₖ) / Lⱼⱼ`（i > j）。`L[i, :j] @ L[j, :j]` 就是那个求和，i == j 时它正好变成 `Σ Lᵢₖ²`，所以两个公式能共用一行 `s = ...`。
- **正定性检查是顺带的**：如果某个 `s ≤ 0`，说明矩阵不是正定的（开不了实数平方根）。这是工程上"判断矩阵是否正定"最便宜的方法——直接试着做 Cholesky。
- 只用到 A 的下三角和对角线，计算量约 n³/3，是 LU 的一半；不需要选主元（对称正定矩阵天然稳定）。
- ⚠️ **不检查对称性**：传入 `[[2, 3], [1, 4]]` 不会报错，但得到的 L 满足 `LLᵀ = [[2,1],[1,4]]`，与 A 不同。生产代码应先 `np.allclose(A, A.T)`。
- `np.zeros_like(A, dtype=float)`：形状跟 A 一样，但强制浮点类型，避免整数输入导致 `np.sqrt` 结果被截断成整数。

```python
def cholesky_solve(L, b):
    n = len(b)
    y = np.zeros(n)
    for i in range(n):
        y[i] = (b[i] - L[i, :i] @ y[:i]) / L[i, i]

    x = np.zeros(n)
    Lt = L.T
    for i in range(n - 1, -1, -1):
        x[i] = (y[i] - Lt[i, i + 1 :] @ x[i + 1 :]) / Lt[i, i]

    return x
```

- `LLᵀx = b`：前代解 `Ly = b`，回代解 `Lᵀx = y`。和 `lu_solve` 唯一的区别是 L 对角线不是 1，所以前代也要除 `L[i, i]`。
- `L.T` 在 NumPy 中只是一个**视图**（不复制数据），开销为零。

### 3.4 最小二乘与岭回归

```python
def least_squares_normal(A, b):
    AtA = A.T @ A
    Atb = A.T @ b
    return gaussian_elimination(AtA, Atb)


def ridge_regression(A, b, lam):
    n = A.shape[1]
    AtA = A.T @ A + lam * np.eye(n)
    Atb = A.T @ b
    L = cholesky(AtA)
    return cholesky_solve(L, Atb)
```

- `least_squares_normal`：把 m×n 的超定问题变成 n×n 的方阵问题 `AᵀAx = Aᵀb`。这就是线性回归闭式解，只是**没有显式求逆**，而是直接解方程——这是正确的工程习惯。
- `ridge_regression`：加 `λI` 之后矩阵对称正定，于是放心用 Cholesky。
- ⚠️ 正规方程会把条件数平方（`κ(AᵀA) = κ(A)²`），特征近共线时精度损失严重；生产中优先 QR / SVD（`np.linalg.lstsq`）。
- ⚠️ `least_squares_normal` 对对称的 `AᵀA` 仍用通用高斯消元，没有利用对称性；满秩时其实也可以直接用 Cholesky（`demo_linear_regression_full` 里就演示了这种做法）。
- ⚠️ `ridge_regression` 把**截距列（全 1 列）也一起惩罚了**。通常的岭回归不惩罚截距（sklearn 默认 `fit_intercept=True` 会先中心化数据）。代码在和 sklearn 对比时特意用了 `fit_intercept=False`，两边定义一致，所以误差在 1e-16 量级。

### 3.5 条件数

```python
def condition_number(A):
    _, S, _ = np.linalg.svd(A)
    if S[-1] < 1e-15:
        return float("inf")
    return S[0] / S[-1]
```

- `np.linalg.svd` 返回 `U, S, Vt`，其中 `S` 是**降序排列**的奇异值，所以 `S[0]` 最大、`S[-1]` 最小。`_` 是"我不需要这个值"的惯用占位名。
- 最小奇异值近似为 0 时返回 `float("inf")`，表示矩阵（数值上）奇异。
- ⚠️ `1e-15` 是绝对阈值，而条件数是**尺度无关**的：`condition_number(1e-20 * np.eye(2))` 会返回 `inf`，但真实值是 1。改进：相对阈值 `S[-1] <= S[0] * eps * max(m, n)`，或直接用 `np.linalg.cond`。
- 小优化：只需要奇异值时可以 `np.linalg.svd(A, compute_uv=False)`，省掉计算 U、V（对 100×5 的矩阵，完整 SVD 会算一个 100×100 的 U）。

### 3.6 共轭梯度

```python
def conjugate_gradient(A, b, tol=1e-10, max_iter=None):
    n = len(b)
    if max_iter is None:
        max_iter = n

    x = np.zeros(n)
    r = b.astype(float) - A @ x
    p = r.copy()
    rs_old = r @ r

    for k in range(max_iter):
        Ap = A @ p
        alpha = rs_old / (p @ Ap)
        x = x + alpha * p
        r = r - alpha * Ap
        rs_new = r @ r
        if np.sqrt(rs_new) < tol:
            return x, k + 1
        beta = rs_new / rs_old
        p = r + beta * p
        rs_old = rs_new

    return x, max_iter
```

- 与讲义伪代码一一对应：`alpha` 是沿搜索方向 p 的最优步长；`r` 用递推 `r − α·Ap` 更新（省一次矩阵-向量乘）；`beta` 让新方向与旧方向 A-共轭。
- `rs_old = r @ r` 缓存残差平方范数，避免重复计算；每轮只做**一次**矩阵-向量乘 `A @ p`——这就是 CG 适合大型稀疏矩阵的原因：A 可以是稀疏格式甚至只是一个"能算 `A @ p` 的函数"。
- `max_iter=None` 再在函数体里设成 n：默认值依赖另一个参数时的标准写法。
- ⚠️ 默认上限 `n` 只在精确算术下够用。本节演示中 50 维、`κ ≈ 899` 的系统 50 步没收敛（残差 4.4e-2），实测需要 69 步。并且到达上限时只返回 `(x, max_iter)`，**调用方无法区分"收敛了"和"没收敛"**。
- ⚠️ `b` 为零向量时 `alpha = 0/0`，结果全是 `nan`；应先检查初始残差。

### 3.7 演示函数里值得注意的几处

```python
    reconstructed = P.T @ L @ U
    print(f"PA = LU reconstruction error: {np.max(np.abs(A - reconstructed)):.2e}")
```

置换矩阵正交，`P⁻¹ = Pᵀ`，所以 `A = PᵀLU`。打印的标签写的是 `PA = LU`，实际检查的是等价形式。

```python
    log_det = 2 * np.sum(np.log(np.diag(L)))
    log_det_np = np.log(np.linalg.det(A))
```

`det(A) = det(L)·det(Lᵀ) = (Π Lᵢᵢ)²`，取对数得 `2·Σ log Lᵢᵢ`。3×3 时两者相同；维数一大，`det` 会上溢 / 下溢（例如 `0.1·I₁₀₀₀` 的 det 直接变成 0.0），对数域累加才是高斯过程等场景的标准做法。

```python
    X_collinear = X.copy()
    X_collinear[:, 4] = X_collinear[:, 0] + 1e-8 * np.random.randn(100)
```

第 5 列几乎等于第 1 列（只差 1e-8 的噪声），人为制造多重共线性，用来演示条件数爆炸以及 `λI` 的修复效果。`X.copy()` 很关键，否则会改坏前面用的 X。

```python
    try:
        from sklearn.linear_model import Ridge
        # ...
    except ImportError:
        print("\nInstall scikit-learn for sklearn comparison: pip install scikit-learn")
```

可选依赖的标准写法：装了就对比，没装也不影响主流程。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 NumPy 数组但手写算法 | 向量化切片让代码短，又能看清每一步 | 双重 Python 循环仍慢；生产用 LAPACK（`np.linalg.solve`、`scipy.linalg.lu_factor/cho_factor`） |
| 增广矩阵 `[A \| b]` | 行操作时 b 自动同步 | 多个 b 时要重复消元 → 用 LU |
| 部分主元 | 乘子 `\|m\| ≤ 1`，抑制误差放大 | 极端情况仍可能不稳，可用完全主元（代价更高） |
| `P` 存成完整矩阵 | 便于打印和 `P.T @ L @ U` 验证 | 浪费 O(n²) 内存；LAPACK 存置换下标数组 |
| 正规方程 + 高斯消元做 OLS | 最直观地体现"OLS = 解线性系统" | 条件数平方；生产用 QR / SVD（`lstsq`） |
| 岭回归用 Cholesky | `AᵀA + λI` 必然对称正定，Cholesky 最快 | 截距也被惩罚；生产中通常先中心化、不惩罚截距 |
| 绝对阈值 `1e-12` / `1e-15` | 简单直观 | 与矩阵尺度有关；应使用相对阈值 |
| CG 默认 `max_iter = n` | 呼应"精确算术 n 步收敛"的理论 | 浮点下不够；应设更大上限并返回收敛标志 |
| 每个方法都和 NumPy/sklearn 对比 | 自动验证正确性（误差 ~1e-16） | — |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块别名导入 | `import numpy as np` | 约定俗成的缩写 |
| `range` 倒序 | `range(n - 1, -1, -1)` | 从 n−1 数到 0（终点 −1 不含），用于回代 |
| 抛出异常 | `raise ValueError(f"Matrix is singular at pivot {k}")` | 遇到非法输入时主动报错，比返回垃圾结果好 |
| `try / except ImportError` | 导入 sklearn 的地方 | 可选依赖：导入失败就走降级分支 |
| 默认参数 `None` | `max_iter=None` 然后 `if max_iter is None: max_iter = n` | 默认值依赖其他参数时的惯用写法 |
| 多返回值与解包 | `return P, L, U`；`P, L, U = lu_decompose(A)`；`x_cg, iters = ...` | 返回的是元组，接收时按位置解包 |
| `_` 占位变量 | `_, S, _ = np.linalg.svd(A)` | 不关心的返回值用 `_` 接 |
| `float("inf")` | `return float("inf")` | 正无穷，表示"奇异 / 无穷大条件数" |
| f-string 格式符 | `:.2e`（科学计数）、`:.4f`、`:>5.1f`（右对齐宽 5）、`:>10s`（字符串右对齐宽 10） | 对齐输出表格 |
| 元组列表遍历 | `for name, x in [("LU", x_lu), ("Cholesky", x_chol), ...]` | 一次遍历多个"名字-结果"对 |
| `@` 运算符 | `A.T @ A`、`L[i, :i] @ y[:i]` | 矩阵乘 / 向量点积；空数组点积得 `0.0` |
| NumPy 切片（视图） | `Ab[k:, k]`、`Ab[i, k:]`、`U[i, i + 1 :]` | 基本切片返回视图，`-=` 会原地修改原数组 |
| 花式索引交换行 | `Ab[[k, max_row]] = Ab[[max_row, k]]` | 右侧生成副本，可安全交换两行 |
| 原地运算 | `Ab[i, k:] -= m * Ab[k, k:]` | 直接改写数组切片，不分配新数组 |
| `astype` / `copy` | `A.astype(float)`、`X.copy()` | 类型转换（默认返回副本）/ 显式复制 |
| `reshape(-1, 1)` | `b.reshape(-1, 1)` | `-1` 表示"自动推断"，把一维向量变成 n×1 列向量 |
| 数组构造 | `np.hstack`、`np.column_stack`、`np.eye`、`np.zeros_like(A, dtype=float)` | 拼接、单位阵、同形状全零数组 |
| 常用 NumPy 函数 | `np.argmax`、`np.abs`、`np.diag`、`np.round`、`np.max`、`np.linalg.norm/svd/solve/lstsq/cholesky/det` | 本文件用来对照验证 |
| 随机种子 | `np.random.seed(42)` | 固定随机数，保证每次运行结果一致 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 demo，被 import 时不执行 |

---

## 6. 运行结果解读

已在临时副本中实际运行（Python 3.13、NumPy 2.5、scikit-learn 1.9，约 2 秒）。关键输出：

```text
Solution (ours):  [2. 2. 2.]
Solution (numpy): [2. 2. 2.]
Max difference: 4.44e-16                ← 机器精度级别的差异
```

讲义的手算例子，三种方式一致。

```text
P =
[[0. 1. 0.]
 [0. 0. 1.]
 [1. 0. 0.]]
U =
[[ 4.          3.          3.        ]
 [ 0.          1.5        -0.5       ]
 [ 0.          0.         -0.66666667]]
PA = LU reconstruction error: 0.00e+00
Solving 3 different right-hand sides with the same LU:
  b = [1. 0. 0.] -> x = [ 1.5 -0.5 -1.5]
  b = [0. 1. 0.] -> x = [-0.5  0.   1. ]
  b = [0. 0. 1.] -> x = [ 0.   0.5 -0.5]
```

P 不是单位阵，说明发生了两次行交换（部分主元）。用同一组 LU 解三个单位向量 `e₁, e₂, e₃`，得到的三个 x 恰好是 **A⁻¹ 的三列**——这就是"需要逆矩阵时也应该用 LU 求"的原理。

```text
L =
[[2.     0.     0.    ]
 [1.     2.     0.    ]
 [0.5    1.25   2.0463]]
  x (ours):  [1. 1. 1.]
  2 * sum(log(diag(L))) = 4.204693
  log(det(A))           = 4.204693
```

Cholesky 与 `np.linalg.cholesky` 完全一致；`b = [7, 10, 10]` 恰好是 A 每行之和，所以解是全 1。两种 log det 一致（det(A) = 67，ln 67 ≈ 4.2047）。

```text
True weights:          [ 0.   2.  -1.   0.5]
OLS weights (ours):    [ 0.0113  1.9922 -1.005   0.4892]
Max difference: 6.66e-16
```

噪声标准差 0.1，100 个样本，估计值与真值接近；正规方程与 `lstsq` 一致（该数据条件良好）。

```text
lambda=  0.0  w=[ 0.011  1.992 -1.005  0.489]  ||w||=2.284  ||Xw-y||=0.870
lambda= 10.0  w=[ 0.049  1.732 -0.926  0.439]  ||w||=2.013  ||Xw-y||=2.489
  lambda= 10.0  max diff from sklearn: 1.11e-16
```

λ 越大，权重范数越小（收缩）、训练残差越大（偏差增大）。和 sklearn `Ridge(fit_intercept=False)` 一致到 1e-16。

```text
Ill-conditioned:  kappa = 4.00e+10
  kappa(X)     = 1.38
  kappa(X^T X) = 1.90                 ← ≈ 1.38²，验证"条件数平方"
With near-collinear feature:
  kappa(X)     = 2.03e+08
  kappa(X^T X) = 6.86e+15             ← 理论值 ≈ 4e16，已逼近 float64 极限，算出来的数本身已不精确
  kappa(X^T X + lambda I) = 16964.75  ← λ = 0.01 把条件数降了 11 个数量级
```

```text
CG iterations: 50 (max possible: 50)
Max diff from direct solve: 7.01e-03
Residual norm: 4.40e-02
Condition number: 898.69
Better-conditioned system:
  kappa = 1.37
  CG iterations: 10
```

这是最值得注意的一段：第一个系统**并没有收敛**——迭代次数恰好等于上限 50，残差还有 4.4e-2。原因是浮点误差让搜索方向失去共轭性，实际需要 69 步（把 `max_iter` 调到 100 即可验证）。第二个系统条件数 1.37，只用 10 步就收敛，直观展示了"收敛速度取决于条件数"。

```text
Gaussian vs         LU: 5.55e-17
Gaussian vs   Cholesky: 3.89e-16
Gaussian vs         CG: 7.49e-16
...
Normal equations:     [ 6.8785  3.0128 -1.9979]
sklearn:              [ 6.8785  3.0128 -1.9979]
MSE:  0.2405
R^2:  0.9972
```

5 种方法在同一个对称正定系统上一致到 1e-16；完整回归流程中真值是 `[7, 3, -2]`，噪声标准差 0.5，所以 MSE ≈ 0.25 ≈ 0.5²，符合预期。

---

## 7. 动手改一改

1. 给 `lu_decompose` 加奇异检查（主元绝对值小于阈值时 `raise ValueError`），并用 `[[1,2],[2,4]]` 测试。
2. 把 `condition_number` 的阈值改成相对阈值 `S[0] * np.finfo(float).eps * max(A.shape)`，并用 `compute_uv=False` 加速；验证 `1e-20 * np.eye(2)` 返回 1。
3. 给 `conjugate_gradient` 增加收敛标志、相对残差判据 `‖r‖ < tol·‖b‖`，并把默认 `max_iter` 改为 `10 * n`；重跑 `demo_conjugate_gradient`，看看实际需要多少步。
4. 实现 `qr_least_squares(A, b)`（`np.linalg.qr` + 回代），在 `demo_condition_number` 的近共线数据上与 `least_squares_normal` 比较残差和权重的稳定性。
5. 修改 `ridge_regression`，增加参数 `penalize_intercept=False`：不惩罚第 0 列（把 `λI` 的 `[0, 0]` 元素设为 0），再与 `sklearn.linear_model.Ridge(alpha=lam)`（默认 `fit_intercept=True`）对比。
6. 用 `time.perf_counter()` 在 n = 50、200、500 的对称正定矩阵上对比你的 `cholesky` 和 `lu_decompose`，验证 Cholesky 约快 2 倍；再与 `np.linalg.cholesky` 对比，感受 Python 循环与 LAPACK 的差距。

---

## 8. 常见坑

- **用元组解包交换 NumPy 行**：`Ab[k], Ab[j] = Ab[j], Ab[k]` 看起来对，实际上右侧是视图，结果两行变成一样的。必须用花式索引 `Ab[[k, j]] = Ab[[j, k]]`（或显式 `.copy()`）。
- **整数数组参与除法与原地运算**：`np.array([[2, 1], ...])` 是整型，`Ab[i, k:] -= m * ...` 会因类型转换报错或截断；代码统一 `astype(float)` 规避。
- **显式求逆**：`np.linalg.inv(A) @ b` 比 `np.linalg.solve(A, b)` 更慢、更不准；需要多次求解就保存 LU / Cholesky 因子。
- **Cholesky 不检查对称**：非对称矩阵传进去不报错，结果却是错的；而浮点下"理论正定"的矩阵也可能分解失败，常见修复是加 jitter `A + εI`。
- **`np.log(np.linalg.det(A))`**：维度一高就上溢 / 下溢，用 Cholesky 对角线或 `np.linalg.slogdet`。
- **把 CG "迭代次数 = 上限"误读为收敛**：一定要看残差，或让函数显式返回收敛标志。
