# 代码讲解 · transformations.py

> **所属小节**：阶段 01 · 数学基础 · 第 03 节 矩阵变换 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python transformations.py` ｜ **依赖**：Python 标准库 `math`；最后一个演示可选用 NumPy（未安装时自动跳过）

---

## 1. 这份代码在考察什么

上一节把矩阵当成"一堆运算"；这一节把矩阵当成**改变空间形状的机器**，代码要你亲手验证：

1. **基本变换矩阵**：旋转（2D 与 3D 三个轴）、缩放、剪切、反射分别长什么样，作用到点上会发生什么。
2. **复合与顺序**：`S @ R` 和 `R @ S` 作用在同一点上结果不同；复合矩阵的行列式 = 各行列式之积。
3. **行列式的几何意义**：面积/体积的缩放倍数；负号表示定向翻转；0 表示空间被压扁。
4. **特征值 / 特征向量从零实现**：用 2×2 特征方程求特征值、用闭式公式求特征向量，并用 `A @ v == λ * v` 验证；遇到复数特征值时识别出"纯旋转"。
5. **特征分解**：手动拼出 `V`、`D`、`V⁻¹`，重构出原矩阵；最后用 NumPy 对拍，并用协方差矩阵预演 PCA。

> 一句话：**用最小的 2×2 例子，把"矩阵 = 空间变换"和"特征向量 = 不被转动的方向"变成可以打印、可以验证的事实。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `rotation_2d` / `rotation_3d_x/y/z` | 函数 | 构造 2D 旋转矩阵和 3D 绕轴旋转矩阵 | 旋转、正交矩阵 |
| `scaling_2d` / `shearing_2d` / `reflection_x` / `reflection_y` | 函数 | 构造缩放、剪切、反射矩阵 | 基本线性变换 |
| `mat_vec_mul` / `mat_mul` | 函数 | 矩阵×向量、矩阵×矩阵（列表的列表） | 作用变换、复合变换 |
| `det_2x2` / `det_3x3` | 函数 | 2×2、3×3 行列式的展开公式 | 面积/体积缩放 |
| `eigenvalues_2x2` | 函数 | 解特征方程，必要时返回复数 | 特征值 |
| `eigenvector_2x2` | 函数 | 给定特征值求单位特征向量 | 特征向量 |
| `fmt` | 工具函数 | 把数或列表四舍五入，方便打印 | — |
| `demo_*` × 8 | 演示函数 | 分主题打印结果 | — |

数据流：所有矩阵都是 Python 的"列表的列表"；构造函数返回矩阵 → `mat_vec_mul` 作用到点上 / `mat_mul` 复合 → `det_*`、`eigen*` 分析其性质 → `fmt` 格式化打印。最后 `demo_numpy_comparison` 用 NumPy 做同样的事来对拍。

---

## 3. 逐段精讲

### 3.1 旋转矩阵：2D 与 3D

```python
def rotation_2d(theta):
    c, s = math.cos(theta), math.sin(theta)
    return [[c, -s], [s, c]]


def rotation_3d_z(theta):
    c, s = math.cos(theta), math.sin(theta)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]
# ...
def rotation_3d_y(theta):
    c, s = math.cos(theta), math.sin(theta)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
```

- **为什么长这样**：矩阵的列 = 基向量的去向。把 `[1,0]` 逆时针转 θ 得到 `[cosθ, sinθ]`（第 1 列），把 `[0,1]` 转 θ 得到 `[-sinθ, cosθ]`（第 2 列）。
- `theta` 用**弧度**，所以代码里写 `math.pi / 4` 表示 45°。
- 3D 旋转：绕哪个轴转，那一行一列就是单位阵的样子（该坐标不变），其余 2×2 子块就是 2D 旋转。
- 注意 `rotation_3d_y` 里 `s` 和 `-s` 的位置和另外两个"反过来"：右手系的循环顺序是 x→y→z→x，绕 y 轴旋转时，旋转平面里的"第一轴"是 z、"第二轴"是 x（绕 z 轴时是 x、y；绕 x 轴时是 y、z）。把标准 2D 旋转按 (z, x) 的顺序写进 (x, z) 的位置，正负号看起来就对调了。运行结果中 `(1,0,0)` 绕 y 轴转 90° 得到 `(0,0,-1)` 就是这个约定的体现。
- `c, s = math.cos(theta), math.sin(theta)` 先算一次再复用，避免重复调用三角函数。

### 3.2 缩放、剪切、反射

```python
def scaling_2d(sx, sy):
    return [[sx, 0], [0, sy]]


def shearing_2d(kx, ky):
    return [[1, kx], [ky, 1]]


def reflection_x():
    return [[1, 0], [0, -1]]


def reflection_y():
    return [[-1, 0], [0, 1]]
```

| 变换 | 矩阵 | 对点 `(x, y)` 的作用 | 行列式 |
|------|------|---------------------|-------|
| 缩放 | `[[sx,0],[0,sy]]` | `(sx·x, sy·y)` | `sx·sy` |
| x 方向剪切 | `[[1,kx],[0,1]]` | `(x + kx·y, y)` | 1 |
| 关于 x 轴反射 | `[[1,0],[0,-1]]` | `(x, -y)` | -1 |
| 关于 y 轴反射 | `[[-1,0],[0,1]]` | `(-x, y)` | -1 |

- ⚠️ `shearing_2d(kx, ky)` 把两个方向的剪切合并成一个函数。当 `kx`、`ky` **都不为 0** 时，矩阵 `[[1,kx],[ky,1]]` 的行列式是 `1 - kx·ky`，不再等于 1——例如 `shearing_2d(1, 1)` 的行列式为 0，是奇异矩阵。讲义"剪切的行列式是 1"只对单方向剪切成立。本文件所有调用都只传一个非零系数，所以没有触发这个问题。
- 命名提醒：`reflection_x` 是"**关于 x 轴**"反射（翻转 y），不是"翻转 x"。

### 3.3 `mat_vec_mul` 与 `mat_mul`

```python
def mat_vec_mul(matrix, vector):
    return [
        sum(matrix[i][j] * vector[j] for j in range(len(vector)))
        for i in range(len(matrix))
    ]


def mat_mul(a, b):
    rows_a, cols_b = len(a), len(b[0])
    cols_a = len(a[0])
    return [
        [sum(a[i][k] * b[k][j] for k in range(cols_a)) for j in range(cols_b)]
        for i in range(rows_a)
    ]
```

- 和上一节 `Matrix.matmul` 是同一个公式，只是换成了**纯函数 + 原生列表**，没有类、没有形状检查，代码更短，便于专注于"变换"本身。
- `mat_vec_mul` 的输出第 i 个分量 = 矩阵第 i 行与向量的点积。
- **复合的顺序**：`mat_mul(S, R)` 得到 `S @ R`，作用于点时 R 先执行。`demo_composition` 里变量名 `rotate_then_scale = mat_mul(S, R)` 就是在提醒你"从右往左读"。
- ⚠️ 没有维度检查。如果把 3D 点传给 2×2 矩阵，`range(len(vector))` 会访问 `matrix[i][2]`，抛 `IndexError`。

### 3.4 行列式：2×2 与 3×3 的闭式展开

```python
def det_2x2(m):
    return m[0][0] * m[1][1] - m[0][1] * m[1][0]


def det_3x3(m):
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )
```

- `det_3x3` 就是沿第一行做余子式展开后**手工展开**的结果，符号 `+ - +` 交替。和上一节递归版 `determinant()` 等价，但没有递归调用。
- 外层套一对括号 `( ... )` 是为了让长表达式可以**跨行书写**而不用反斜杠续行。
- 用途：`demo_3d_rotations` 验证三个 3D 旋转矩阵的行列式都是 1（体积不变）。

### 3.5 `eigenvalues_2x2`：解特征方程，含复数分支

```python
def eigenvalues_2x2(matrix):
    a, b = matrix[0]
    c, d = matrix[1]
    trace = a + d
    det = a * d - b * c
    discriminant = trace ** 2 - 4 * det
    if discriminant < 0:
        real = trace / 2
        imag = (-discriminant) ** 0.5 / 2
        return (complex(real, imag), complex(real, -imag))
    sqrt_disc = discriminant ** 0.5
    return ((trace + sqrt_disc) / 2, (trace - sqrt_disc) / 2)
```

- **推导**：`det(A - λI) = (a-λ)(d-λ) - bc = λ² - (a+d)λ + (ad-bc)`，即 `λ² - tr·λ + det = 0`，用求根公式 `λ = (tr ± √(tr² - 4det)) / 2`。
- `a, b = matrix[0]` 是**序列解包**，一行取出第一行的两个元素。
- **判别式 < 0** 时有一对共轭复根。代码手动构造 `complex(real, ±imag)`，而不是直接对负数开方——在 Python 中 `(-4) ** 0.5` 其实会返回复数，但显式构造更清楚。复数特征值意味着变换里有旋转成分，平面上没有实特征方向。
- 返回顺序固定为"先大后小"（`+√` 在前）。
- ⚠️ 数值上的简化：两个特征值非常接近时，`trace² - 4det` 存在**灾难性抵消**（两个相近的大数相减），误差会被放大；理论上等于 0 的判别式也可能因舍入变成很小的负数，导致返回一对虚部极小的"假复数"。生产库不会用这种公式（见第 4 节）。

### 3.6 `eigenvector_2x2`：闭式求特征向量

```python
def eigenvector_2x2(matrix, eigenvalue):
    a, b = matrix[0]
    c, d = matrix[1]
    if abs(b) > 1e-10:
        v = [b, eigenvalue - a]
    elif abs(c) > 1e-10:
        v = [eigenvalue - d, c]
    else:
        if abs(a - eigenvalue) < 1e-10:
            v = [1, 0]
        else:
            v = [0, 1]
    mag = (v[0] ** 2 + v[1] ** 2) ** 0.5
    return [v[0] / mag, v[1] / mag]
```

- **核心思路**：特征向量满足 `(A - λI)v = 0`。`A - λI` 的第一行是 `[a-λ, b]`，与它垂直的向量是 `[b, λ-a]`，自动满足第一行方程；又因为 λ 是特征方程的根，`A - λI` 的两行线性相关，第二行方程也随之满足。
- **三个分支**：
  1. `b ≠ 0`：用第一行构造 `[b, λ-a]`。
  2. `b ≈ 0` 但 `c ≠ 0`：第一行可能退化，改用第二行 `[c, d-λ]` 的垂直向量 `[λ-d, c]`。
  3. `b ≈ c ≈ 0`：矩阵是对角阵，特征向量就是坐标轴；用 `a ≈ λ` 判断是 x 轴还是 y 轴。
- 最后**归一化**为单位向量，与 NumPy 的输出约定一致（方向可能差一个正负号）。
- 用 `1e-10` 而不是 `== 0` 判断，避免浮点噪声。
- ⚠️ **重根时的局限**：函数一次只拿到一个特征值，无法区分"第一次调用"和"第二次调用"。对 `[[2,0],[0,2]]`（任何方向都是特征向量）和 `[[2,1],[0,2]]`（只有一个特征方向），两次调用都返回 `[1.0, 0.0]`，后续求 `V⁻¹` 时会除以 0（测验 Q10 详细分析）。
- ⚠️ 只适用于实特征值。复数特征值时 `v[0]**2 + v[1]**2` 不是复向量的模长，所以 demo 里遇到复数就跳过了。

### 3.7 `demo_eigenvalues_from_scratch`：四个代表性矩阵

```python
    matrices = [
        ("Symmetric", [[2, 1], [1, 2]]),
        ("Upper triangular", [[3, 1], [0, 2]]),
        ("Scaling", [[3, 0], [0, 5]]),
        ("Rotation 90", [[0, -1], [1, 0]]),
    ]
    # ...
        if all(isinstance(v, (int, float)) for v in vals):
            for val in vals:
                vec = eigenvector_2x2(A, val)
                result = mat_vec_mul(A, vec)
                scaled = [val * vec[0], val * vec[1]]
                # ...
        else:
            print("  Complex eigenvalues: pure rotation, no real eigenvectors.")
```

这四个矩阵的选择很讲究：

| 矩阵 | 特征值 | 学到什么 |
|------|-------|---------|
| 对称 `[[2,1],[1,2]]` | 3、1 | 对称矩阵特征值为实数，特征向量 `[1,1]`、`[1,-1]` 相互**正交** |
| 上三角 `[[3,1],[0,2]]` | 3、2 | 三角矩阵的特征值就是**对角线元素**；特征向量不正交 |
| 缩放 `[[3,0],[0,5]]` | 5、3 | 对角矩阵的特征向量就是坐标轴（走 `else` 分支） |
| 旋转 90° | `±i` | 没有实特征向量 |

- `all(... for v in vals)` 配合 `isinstance(v, (int, float))`：只要有一个是 `complex` 就走 else 分支。`isinstance` 的第二个参数可以是**类型元组**。
- 每个实特征值都打印 `A @ v` 和 `λ * v` 两行，让你肉眼确认二者相等——"用定义验证结果"是最好的单元测试。

### 3.8 `demo_eigendecomposition`：从零重构 `A = V D V⁻¹`

```python
    A = [[3, 1], [0, 2]]
    vals = eigenvalues_2x2(A)

    v0 = eigenvector_2x2(A, vals[0])
    v1 = eigenvector_2x2(A, vals[1])

    V = [[v0[0], v1[0]], [v0[1], v1[1]]]
    D = [[vals[0], 0], [0, vals[1]]]

    det_v = det_2x2(V)
    V_inv = [
        [V[1][1] / det_v, -V[0][1] / det_v],
        [-V[1][0] / det_v, V[0][0] / det_v],
    ]

    reconstructed = mat_mul(mat_mul(V, D), V_inv)
```

- **特征向量按列放进 V**：`V = [[v0[0], v1[0]], [v0[1], v1[1]]]`，第 0 列是 `v0`，第 1 列是 `v1`。这和 `np.linalg.eig` 返回的 `eigenvectors[:, i]` 约定一致——常见错误是按行放。
- `D` 是对角线为特征值的对角阵。
- `V_inv` 直接套用上一节的 2×2 求逆公式（主对角互换、副对角取负、除以行列式）。
- 读法：`V D V⁻¹ x` = 先用 `V⁻¹` 把 x 换到特征向量坐标系 → 用 `D` 沿各轴缩放 → 用 `V` 换回原坐标系。
- 为什么选上三角矩阵而不是对称矩阵：对称矩阵的 `V` 是正交阵，`V⁻¹ = Vᵀ`，体现不出"一般情况要真的求逆"。
- ⚠️ 没有检查 `det_v` 是否为 0，对不可对角化矩阵会直接 `ZeroDivisionError`。

### 3.9 `demo_determinant_meaning`：用 if/elif 给行列式"贴标签"

```python
    for name, m in cases:
        d = det_2x2(m)
        if d == 0:
            meaning = "space collapses, irreversible"
        elif d < 0:
            meaning = "orientation flipped"
        elif abs(d - 1.0) < 1e-10:
            meaning = "area preserved"
        else:
            meaning = f"area scaled by {abs(d):.1f}x"
        print(f"det({name}) = {fmt(d):>8}  ({meaning})")
```

- 旋转 45° 的行列式是 `cos²θ + sin²θ`，浮点下可能不精确等于 1，所以用 `abs(d - 1.0) < 1e-10` 容差比较。
- ⚠️ 但第一个分支 `d == 0` 用了**精确比较**——这里只对整数矩阵 `[[1,2],[2,4]]` 生效，换成浮点奇异矩阵（如 `[[0.1,0.2],[0.2,0.4]]`）可能就判断失败。前后两种写法不一致，是个小瑕疵。
- ⚠️ 分支顺序意味着 `d = -2` 只会显示"orientation flipped"，丢失了"面积翻倍"的信息。
- `{fmt(d):>8}` 中的 `>8` 表示**右对齐、宽度 8**，让多行输出对齐。

### 3.10 `demo_numpy_comparison`：可选依赖与对拍

```python
    try:
        import numpy as np
    except ImportError:
        print("\nNumPy not installed. Skipping.")
        return
    # ...
    cov = np.array([[2.0, 1.0], [1.0, 3.0]])
    vals, vecs = np.linalg.eig(cov)
    # ...
    print("PCA picks the eigenvectors with the largest eigenvalues.")
```

- `try/except ImportError` 是处理**可选依赖**的标准写法：有 NumPy 就对拍，没有就优雅跳过，脚本仍能跑完。
- `eigenvectors[:, i]`：取第 i **列**——NumPy 的特征向量按列存放。
- 最后用协方差矩阵演示 PCA：特征值就是各主成分方向上的方差。
- ⚠️ `np.linalg.eig` **不保证特征值的顺序**（运行结果里是 `[1.38, 3.62]`，小的在前）。要按"最大特征值"选主成分，必须自己 `np.argsort(vals)[::-1]`。对协方差这类对称矩阵，更推荐 `np.linalg.eigh`：返回实数特征值、按升序排列、特征向量正交。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 列表的列表 + 纯函数，不用类 | 聚焦"变换"本身，代码最短 | 无形状检查；生产用 NumPy 数组 |
| 每种变换一个构造函数 | 名字即含义，便于组合 | 图形学中常用齐次坐标 3×3/4×4 矩阵统一表示（含平移） |
| `shearing_2d(kx, ky)` 合并两个方向 | 少写一个函数 | 两个系数都非零时不是纯剪切，`det = 1 - kx·ky` |
| 2×2 特征值用求根公式 | 直接对应特征方程，易懂 | 数值不稳定，且无法推广到大矩阵；LAPACK 用 Hessenberg 化 + QR 迭代 |
| 特征向量用闭式公式 `[b, λ-a]` | 无需解线性方程组 | 重根时无法给出两个独立向量 |
| 用 `A@v` 与 `λ*v` 并排打印验证 | 用定义检验结果，最可靠 | 生产中用 `np.allclose` 做自动化断言 |
| NumPy 作为可选依赖 | 脚本在纯标准库环境也能运行 | — |
| 演示 PCA 时直接用 `eig` | 与前文一致 | 对称矩阵应使用 `eigh`，并显式排序 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 多重赋值 | `c, s = math.cos(theta), math.sin(theta)` | 右边先打包成元组，再解包给左边 |
| 序列解包 | `a, b = matrix[0]` | 把长度为 2 的列表拆成两个变量 |
| `math` 模块 | `math.pi`、`math.cos`、`math.sin` | 三角函数用弧度制 |
| 列表推导式 / 生成器表达式 | `[sum(... for j in ...) for i in ...]` | 构造向量与矩阵 |
| 用括号续行 | `det_3x3` 中 `return ( ... )` | 括号内可以自由换行，比 `\` 更安全 |
| 幂运算开方 | `discriminant ** 0.5` | 等价于 `math.sqrt`；对负数会得到复数 |
| `complex` 类型 | `complex(real, imag)`，打印为 `1j`、`-1j` | Python 内置复数，`j` 表示虚数单位 |
| 返回元组 | `return ((trace + sqrt_disc) / 2, ...)` | 一次返回多个值 |
| `isinstance` + 类型元组 | `isinstance(v, (int, float))` | 判断是否属于其中任一类型 |
| `all()` + 生成器 | `all(isinstance(v, ...) for v in vals)` | 全部为真才返回 True，遇假即停 |
| `zip` | `for label, pt in zip(labels, square)` | 两个列表按位置配对遍历 |
| 元组列表 + 解包遍历 | `for name, matrix in transforms:` | 用 `(名字, 矩阵)` 元组组织测试用例 |
| 默认参数 | `def fmt(v, decimals=4)` | 不传时用 4 位小数 |
| `round` | `round(x, decimals)` | 四舍五入到指定小数位 |
| f-string 对齐 | `f"{fmt(d):>8}"` | `>8` 右对齐宽度 8 |
| `try/except ImportError` | `demo_numpy_comparison` 开头 | 可选依赖缺失时优雅降级 |
| 函数内 `import` | `import numpy as np` 写在函数里 | 只有调用到该函数才导入 |
| NumPy 切片 | `eigenvectors[:, i]` | 取第 i 列 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时依次执行 8 个 demo |

---

## 6. 运行结果解读

在临时副本中实际运行 `python3 transformations.py`（NumPy 2.5.3），关键输出如下：

```text
Rotate (1,0) by 45 deg: [0.7071, 0.7071]       ← (cos45°, sin45°)
Shear (1,1) kx=1: [2.0, 1.0]                   ← x 加上 1·y
Reflect (2,1) across y-axis: [-2.0, 1.0]
```

```text
Rotate 45 deg:
  top-right: [1, 1] -> [0.0, 1.4142]           ← 对角线长度 √2 保持不变
  det = 1.0
Scale (2, 0.5):
  right: [1, 0] -> [2, 0.0]                    ← 整数与浮点混合，见下方说明
  det = 1.0                                    ← 2 × 0.5 = 1，面积恰好不变
Shear kx=0.5:
  top-right: [1, 1] -> [1.5, 1]                ← 正方形变成平行四边形
  det = 1.0
Reflect y-axis:
  det = -1                                     ← 定向翻转
```

- `[2, 0.0]` 这种 int/float 混合是因为 `scaling_2d(2, 0.5)` 中 `2` 和 `0` 是整数、`0.5` 是浮点数；整数×整数的和仍是整数。数学上无影响。
- `Scale (2, 0.5)` 的行列式恰好为 1：x 拉长 2 倍、y 压缩一半，面积不变。

```text
Rotate 90 then scale (2, 0.5): [0.0, 0.5]
Scale (2, 0.5) then rotate 90: [0.0, 2.0]      ← 顺序不同，结果不同
det(S @ R) = 1.0
det(S) * det(R) = 1.0
```

⚠️ 这里 `det(S)` 和 `det(R)` 都是 1，所以"复合行列式 = 行列式之积"的验证是 `1 = 1 × 1`，说服力较弱。可以把 S 换成 `scaling_2d(2, 3)` 再跑一次（见第 7 节练习 2）。

```text
Rotate 90 around z: [0.0, 1.0, 0.0]            ← x 轴转到 y 轴
Rotate 90 around x: [1.0, 0.0, 0.0]            ← 点就在转轴上，不动
Rotate 90 around y: [0.0, 0.0, -1.0]           ← x 轴转到 -z
```

```text
Symmetric: [[2, 1], [1, 2]]
  lambda=3.0, v=[0.7071, 0.7071]
    A @ v = [2.1213, 2.1213]
    l * v = [2.1213, 2.1213]                   ← 两行相等，验证成功
Upper triangular: [[3, 1], [0, 2]]
  Eigenvalues: 3.0, 2.0                        ← 就是对角线元素
  lambda=2.0, v=[0.7071, -0.7071]
Rotation 90: [[0, -1], [1, 0]]
  Eigenvalues: 1j, -1j
  Complex eigenvalues: pure rotation, no real eigenvectors.
```

```text
V (eigenvectors as columns):
  [1.0, 0.7071]
  [0.0, -0.7071]
Reconstructed A = V @ D @ V^-1:
  [3.0, 1.0]
  [0.0, 2.0]                                   ← 完美重构
```

```text
det(Rotation 45 deg) =      1.0  (area preserved)
det(Scale (2, 3)) =        6  (area scaled by 6.0x)
det(Singular [[1,2],[2,4]]) =        0  (space collapses, irreversible)
```

NumPy 部分：

```text
Eigenvalues (numpy): [3.+0.j 1.+0.j]
Eigenvectors (numpy, columns):
[[ 0.70710678+0.j -0.70710678+0.j]
 [ 0.70710678+0.j  0.70710678+0.j]]
...
Variance along each (eigenvalues): [1.38196601+0.j 3.61803399+0.j]
```

- 特征值与从零实现一致（3 和 1）。第二个特征向量是 `[-0.7071, 0.7071]`，和我们的 `[0.7071, -0.7071]` 差一个负号——**特征向量的符号是任意的**，两者都对。
- 本次运行环境下 `eig` 输出带 `+0.j` 的复数类型；在较旧版本的 NumPy 中，特征值全为实数时会返回实数数组，你本机可能看不到 `+0.j`。对称矩阵用 `eigh` 就不会有这个问题。
- 协方差矩阵的特征值 `[1.38, 3.62]` 是**乱序**的，最大的在后面——印证了 3.10 节"必须自己排序"的提醒。

---

## 7. 动手改一改

1. **单位正方形保距验证**（讲义练习 1）：对旋转后的 4 个顶点，计算相邻顶点和对角顶点的距离，确认与原正方形一致；再对剪切后的顶点做同样的计算，看哪些距离变了。
2. **让行列式乘积验证更有说服力**：在 `demo_composition` 中把 S 改成 `scaling_2d(2, 3)`，确认 `det(S @ R) = 6 = 6 × 1`。
3. **手算 + 对拍**（讲义练习 2）：手解 `[[4,2],[1,3]]` 的特征值（答案 5 和 2），再用 `eigenvalues_2x2` 和 `np.linalg.eig` 各验证一次。
4. **复合三变换**（讲义练习 3）：旋转 30° → 缩放 `(1.5, 0.8)` → 剪切 `kx=0.3`，作用于圆上 8 个点，验证 `det` 等于乘积 1.2（参考测验 Q11）。
5. **修复重根问题**：在 `demo_eigendecomposition` 里加上 `abs(det_v) < 1e-10` 的检查，对数量矩阵（如 `2I`）直接令 `V = I`，对亏损矩阵抛出清晰的 `ValueError`。
6. **PCA 排序**：把 `demo_numpy_comparison` 中协方差部分改用 `np.linalg.eigh`，并用 `np.argsort(vals)[::-1]` 按方差从大到小输出主成分和解释方差比例。

---

## 8. 常见坑

- **混淆行和列**：变换矩阵的**列**是基向量的去向；`np.linalg.eig` 的特征向量也是按**列**存放。按行读就全错了。
- **复合顺序写反**："先 R 后 S"要写成 `S @ R`，从右往左读。
- **角度与弧度**：`math.cos(45)` 是 45 弧度，不是 45°；要写 `math.radians(45)` 或 `math.pi / 4`。
- **以为特征向量是唯一的**：任何非零倍数（包括取负号）都是同一个特征向量；比较结果时要考虑符号。
- **默认 `eig` 已排序**：它不排序。对称矩阵用 `eigh`（升序），再按需要反转。
- **用 `==` 判断浮点行列式为 0 或 1**：旋转矩阵的行列式可能是 `1.0000000000000002`；奇异判断应使用容差，甚至应看条件数而不是行列式。
