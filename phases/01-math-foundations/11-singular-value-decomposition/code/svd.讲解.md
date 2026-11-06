# 代码讲解 · svd.py

> **所属小节**：阶段 01 · 数学基础 · 第 11 节 奇异值分解 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python svd.py`（无命令行参数，依次运行 11 个演示） ｜ **依赖**：`numpy`；`demo_pca_is_svd` 里可选用 `scikit-learn`（没装会被 `try/except ImportError` 静默跳过）

---

## 1. 这份代码在考察什么

这是一份约 20KB、由"2 个核心算法 + 4 个工具函数 + 11 个演示"组成的脚本。它想让你建立的认知是：

1. **SVD 是怎么"算出来"的**：用幂迭代（power iteration）找最大奇异值，再用紧缩（deflation）逐个剥离，从零实现一个能和 `np.linalg.svd` 对上数的 SVD。
2. **SVD 的几何**：把单位圆上的点依次送过 `Vᵀ → Σ → U`，亲眼看到"旋转 → 缩放 → 旋转"。
3. **低秩近似为什么最优**：构造一个奇异值已知的矩阵，验证截断误差恰好等于被丢弃的奇异值（Eckart-Young）。
4. **SVD 的四大应用**：图像压缩、推荐系统潜在因子、LSA 语义空间、去噪。
5. **伪逆与数值稳定性**：超定 / 欠定 / 奇异三种方程组统一用 `VΣ⁺Uᵀ` 求解；`AᵀA` 会把条件数平方。
6. **SVD 是很多东西的"底座"**：PCA、秩、Frobenius / 谱 / 核范数、行列式都能从奇异值读出来。

> 一句话：**先从零把 SVD 算出来，再用 NumPy 的 SVD 去做一圈真实应用**——面试里"SVD 是什么、能干什么、为什么数值上更好"三个层次的问题，这份代码都覆盖了。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `power_iteration(M, num_iters, tol)` | 函数 | 求对称矩阵 M 的最大特征值与特征向量 | 幂迭代、Rayleigh 商 |
| `svd_from_scratch(A, k)` | 函数 | 对 `AᵀA` 做幂迭代 + 紧缩，逐个求出 σ、u、v | SVD 与特征分解的关系、外积形式 |
| `truncated_svd` / `reconstruct` | 工具函数 | 取前 k 项 / 由三因子重构 | 截断 SVD（⚠️ 本文件中定义了但没有被调用） |
| `compression_ratio(m, n, k)` | 工具函数 | 计算 `k(m+n+1)/(mn)` | 截断 SVD 的存储账 |
| `pseudoinverse_via_svd(A, tol)` | 函数 | 带阈值的 `VΣ⁺Uᵀ` | Moore-Penrose 伪逆 |
| `demo_svd_basics` | 演示 | 从零实现 vs NumPy，验证 `A·vᵢ = σᵢ·uᵢ` | 正确性校验 |
| `demo_geometry` | 演示 | 单位圆 8 个点逐步变换 | 旋转-缩放-旋转 |
| `demo_low_rank_approximation` | 演示 | 已知谱的秩 5 矩阵，扫 k=1..7 | Eckart-Young |
| `demo_image_compression` | 演示 | 合成"图像"的谱、能量、RMSE | 压缩比 vs 质量 |
| `demo_recommendation_system` | 演示 | 均值填充 + 秩 3 重构预测缺失评分 | 潜在因子模型 |
| `demo_lsa` | 演示 | 词-文档矩阵 → 3 维概念空间 | LSA |
| `demo_noise_reduction` | 演示 | 4 档噪声下找最优截断秩 | 低秩去噪 |
| `demo_pseudoinverse` | 演示 | 超定 / 欠定 / 奇异 | 最小二乘、最小范数解 |
| `demo_condition_number` | 演示 | 4 个矩阵的 κ；`A` vs `AᵀA` | 条件数、数值稳定 |
| `demo_pca_is_svd` | 演示 | 协方差特征分解 vs SVD（vs sklearn） | PCA = SVD |
| `demo_matrix_properties` | 演示 | 秩、三种范数、行列式 | 奇异值揭示矩阵性质 |

数据流：只有 `demo_svd_basics` 用到从零实现的 `svd_from_scratch`（它调用 `power_iteration`）；其余演示都直接调用 `np.linalg.svd`，`demo_pseudoinverse` 调用 `pseudoinverse_via_svd`，`demo_low_rank_approximation` 调用 `compression_ratio`。`__main__` 按顺序执行 11 个演示，彼此独立。

---

## 3. 逐段精讲

### 3.1 `power_iteration`：反复乘、反复归一化

```python
def power_iteration(M, num_iters=200, tol=1e-10):
    n = M.shape[1]
    v = np.random.randn(n)
    v = v / np.linalg.norm(v)

    for _ in range(num_iters):
        Mv = M @ v
        norm = np.linalg.norm(Mv)
        if norm < tol:
            return 0.0, v
        v_new = Mv / norm
        if np.abs(np.dot(v_new, v)) > 1 - tol:
            v = v_new
            break
        v = v_new

    eigenvalue = v @ M @ v
    return eigenvalue, v
```

- **原理**：把随机向量 v 展开到 M 的特征基上，每乘一次 M，第 i 个分量就乘上 λᵢ。乘很多次之后，最大特征值对应的分量"跑赢"其他分量，v 就转到了最大特征向量方向。每轮归一化是为了防止数值上溢/下溢。
- **收敛判据** `|v_new · v| > 1 − tol`：两个单位向量的点积就是夹角余弦，接近 1 说明方向不再变化。用 `np.abs` 是因为特征向量的正负号无所谓——如果 λ 为负，v 会在正反方向来回翻转，但仍算收敛。
- `norm < tol` 时直接返回 0：说明 M 把 v 压成了零（M 近似为零矩阵，比如紧缩到最后的残差），继续除以 norm 会除以 0。
- **最后一行** `v @ M @ v` 是 **Rayleigh 商** `vᵀMv`（v 已是单位向量），给出与 v 对应的特征值估计。
- ⚠️ 收敛速度取决于 `|λ₂/λ₁|`。这里 M 是 `AᵀA`，特征值是 σ²，所以每轮误差约按 `(σ₂/σ₁)²` 缩小——σ₁ 与 σ₂ 很接近时，300 轮也可能不够。工业级 SVD 不用这种方法，而是用 Golub-Kahan 双对角化 + QR 迭代 / 分治法。
- ⚠️ 初始向量用的是全局 `np.random`，结果是否可复现取决于调用前有没有 `np.random.seed`（`demo_svd_basics` 开头设置了 42）。

### 3.2 `svd_from_scratch`：幂迭代 + 紧缩

```python
def svd_from_scratch(A, k=None):
    m, n = A.shape
    if k is None:
        k = min(m, n)

    sigmas = []
    us = []
    vs = []

    A_residual = A.copy().astype(float)

    for i in range(k):
        AtA = A_residual.T @ A_residual
        eigenvalue, v = power_iteration(AtA, num_iters=300)

        if eigenvalue < 1e-10:
            break

        sigma = np.sqrt(max(eigenvalue, 0))
        u = A_residual @ v / sigma

        u_norm = np.linalg.norm(u)
        if u_norm > 1e-10:
            u = u / u_norm

        sigmas.append(sigma)
        us.append(u)
        vs.append(v)

        A_residual = A_residual - sigma * np.outer(u, v)

    U = np.column_stack(us) if us else np.empty((m, 0))
    S = np.array(sigmas)
    V = np.column_stack(vs) if vs else np.empty((n, 0))

    return U, S, V
```

逐行对应讲义里的公式：

| 代码 | 数学 |
|------|------|
| `AtA = A_residual.T @ A_residual` | V 是 `AᵀA` 的特征向量，`σ²` 是特征值 |
| `sigma = np.sqrt(max(eigenvalue, 0))` | `σ = √λ`；`max(…, 0)` 防止舍入误差让 λ 变成 -1e-17 时 `sqrt` 得到 `nan` |
| `u = A_residual @ v / sigma` | 由 `A·v = σ·u` 反推 `u = A·v/σ` |
| `u = u / u_norm` | 理论上 u 已是单位向量，再归一化一次是为了抵消累积误差 |
| `A_residual - sigma * np.outer(u, v)` | 外积形式 `A = Σσᵢuᵢvᵢᵀ`，减掉已找到的那一层 |

- **为什么紧缩有效**：减去 `σ₁u₁v₁ᵀ` 后，残差的 SVD 正好是原矩阵去掉第一项，最大奇异值变成 σ₂，于是下一轮幂迭代自然找到第二个。
- `.astype(float)` 保证整数矩阵也能做浮点运算；`.copy()` 保证不改动调用者传入的 A。
- `eigenvalue < 1e-10` 比较的是 σ²，相当于 σ < 1e-5 就认为"剩下的都是零"并提前结束——所以对秩亏矩阵，返回的奇异值个数会少于 `min(m, n)`。
- `np.empty((m, 0))`：一个奇异值都没找到时（A 是零矩阵），返回形状正确的空数组，而不是让 `np.column_stack([])` 报错。
- ⚠️ **返回的是 V，不是 Vᵀ**。这与 `np.linalg.svd` 的返回约定不同，重构要写 `U @ np.diag(S) @ V.T`。
- ⚠️ 显式构造了 `AᵀA`——这正是讲义"数值稳定性"一节警告不要做的事（条件数平方）。这里是为了教学上把"SVD ↔ 特征分解"的关系写得直白；讲义练习 1 也让你对比这种做法的精度。

### 3.3 `demo_svd_basics`：和 NumPy 对账

```python
    U_ours, S_ours, V_ours = svd_from_scratch(A)
    U_np, S_np, Vt_np = np.linalg.svd(A, full_matrices=False)
    # ...
    A_ours = U_ours @ np.diag(S_ours) @ V_ours.T
    A_np = U_np @ np.diag(S_np) @ Vt_np
    # ...
    for i in range(min(4, len(S_np))):
        v_i = Vt_np[i]
        u_i = U_np[:, i]
        lhs = A @ v_i
        rhs = S_np[i] * u_i
        match = np.allclose(lhs, rhs, atol=1e-10) or np.allclose(lhs, -rhs, atol=1e-10)
```

- `full_matrices=False` 返回"瘦"SVD：对 6×4 的 A，`U_np` 是 6×4、`S_np` 是长度 4 的一维数组、`Vt_np` 是 4×4。S 是一维的，必须 `np.diag(S)` 变成对角矩阵才能参与矩阵乘。
- 取向量的方式要注意：右奇异向量 vᵢ 是 **Vt 的第 i 行** `Vt_np[i]`，左奇异向量 uᵢ 是 **U 的第 i 列** `U_np[:, i]`。
- `or np.allclose(lhs, -rhs)`：奇异向量的正负号不唯一（`uᵢ, vᵢ` 同时取反仍是合法的 SVD）。不过这里 u、v 都出自 NumPy 的同一次分解，符号是配套的，这个 `or` 分支其实用不上；只有当你把"自己算的 v"和"NumPy 算的 u"混用时才必须考虑符号。

### 3.4 `demo_geometry`：单位圆走一遍三步变换

```python
    theta = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    circle = np.column_stack([np.cos(theta), np.sin(theta)])
    # ...
    for i in range(len(theta)):
        p = circle[i]
        step1 = Vt @ p
        step2 = S * step1
        step3 = U @ step2
        direct = A @ p
```

- `endpoint=False` 让 8 个角度均匀分布且不重复 0 和 2π。
- `step2 = S * step1` 用的是**逐元素乘法**而不是 `np.diag(S) @ step1`：对角矩阵乘向量，等价于把每个分量乘上对应的 σ，这是 NumPy 中常见的省事写法。
- `A = [[3,1],[1,3]]` 是对称正定矩阵，所以输出里 U 与 Vᵀ 完全一样，σ = [4, 2] 正是它的特征值——印证"对称半正定时 SVD = 特征分解"。
- 打印的 `check` 列与 `U*Sig*V^T(p)` 列逐行相同，说明三步分解确实复现了 `A @ p`。

### 3.5 `demo_low_rank_approximation`：构造一个"谱已知"的矩阵

```python
    U_true = np.linalg.qr(np.random.randn(m, true_rank))[0]
    V_true = np.linalg.qr(np.random.randn(n, true_rank))[0]
    S_true = np.array([50, 30, 15, 8, 3], dtype=float)
    A = U_true @ np.diag(S_true) @ V_true.T
```

- 这是一个很值得学的**造测试数据技巧**：对随机矩阵做 QR，取 Q 得到列正交的矩阵，再人为指定奇异值，就得到一个"奇异值精确等于 [50, 30, 15, 8, 3]、秩恰好为 5"的矩阵。用它来检验 Eckart-Young 非常干净。
- 循环里 `np.linalg.norm(A - A_k, 'fro')` 的输出可以手算验证：k=3 时误差 = `√(8² + 3²) = √73 ≈ 8.544`，k=4 时 = 3，k≥5 时为 0——与运行结果完全一致。
- `compression_ratio(m, n, k)` 给出存储占比，k=5 时只需原矩阵 11.3% 的数字就能**无损**表示它。

### 3.6 `demo_image_compression`：能量与 RMSE

```python
    x = np.linspace(-3, 3, cols)
    y = np.linspace(-3, 3, rows)
    X, Y = np.meshgrid(x, y)
    image = np.sin(X) * np.cos(Y) + 0.5 * np.sin(2 * X + Y)
    image = (image - image.min()) / (image.max() - image.min()) * 255
    # ...
    total_energy = np.sum(S ** 2)
    # ...
        energy = np.sum(S[:k] ** 2) / total_energy
        rmse = np.sqrt(np.mean((image - compressed) ** 2))
```

- `np.meshgrid` 把两个一维坐标变成二维网格，`image[i, j]` 就是函数在 `(x_j, y_i)` 处的值，再线性缩放到 0–255 模拟灰度。
- "能量"用的是 `σ²` 的累计占比，因为 `‖A‖_F² = Σσᵢ²`；RMSE 是逐像素均方根误差。
- ⚠️ 这张合成"图像"其实**秩恰好为 3**：`sin x·cos y` 与 `0.5·sin(2x+y) = 0.5(sin2x·cos y + cos2x·sin y)` 可以合并成两个秩 1 项，归一化时的常数平移再贡献一个秩 1 项。所以输出里 σ₅ 及以后全是 0.00，k=5 时 RMSE 已经是 0。真实照片的奇异值是"快速衰减但不归零"的，曲线会平滑得多——想看真实效果，请做讲义练习 2。
- ⚠️ σ₁ = 32655.77 远大于其他值，主要是因为像素没有中心化：本机算得像素均值为 127.5，仅这个"直流分量"的 Frobenius 范数就是 `127.5 × 256 = 32640`，几乎就是 σ₁。

### 3.7 `demo_recommendation_system`：潜在因子 + 均值填充

```python
    user_prefs = np.random.randn(n_users, n_factors)
    movie_attrs = np.random.randn(n_movies, n_factors)

    true_ratings = user_prefs @ movie_attrs.T
    true_ratings = (true_ratings - true_ratings.min()) / (true_ratings.max() - true_ratings.min()) * 4 + 1
    true_ratings = np.round(true_ratings, 1)

    mask = np.random.random((n_users, n_movies)) > 0.4
    observed = true_ratings.copy()
    observed[~mask] = np.nan
    # ...
    filled = observed.copy()
    for i in range(n_users):
        row_mean = np.nanmean(filled[i])
        filled[i, np.isnan(filled[i])] = row_mean
```

- **数据生成**：用户偏好（10×3）乘电影属性（8×3）的转置，得到的评分矩阵天然是秩 3——这就是"潜在因子"假设的模拟。再线性缩放到 1–5 分。
- **掩码**：`np.random.random(...) > 0.4` 约保留 60% 的评分；`observed[~mask] = np.nan` 用布尔索引把未观测位置设为 NaN（`~` 是布尔数组取反）。
- **填充**：`np.nanmean` 计算时忽略 NaN；`filled[i, np.isnan(filled[i])] = row_mean` 只填这一行的缺失位置。
- ⚠️ 均值填充是最朴素的做法：填充值会被当作真实观测参与 SVD，预测被拉向用户均值（输出中预测值大多在 2.1–3.1 之间，MAE 0.453）。生产中用 Funk SVD / ALS 只在观测项上拟合，讲义里也明确说了这一点。
- ⚠️ min-max 缩放里的平移相当于给矩阵加了一个常数矩阵（秩 1），`np.round(…, 1)` 又引入了舍入噪声。本机验证：`user_prefs @ movie_attrs.T` 严格秩 3，缩放后变成秩 4（第 4 个奇异值约 1.09），取整后则满秩。所以 `k = n_factors = 3` 只是"近似"合适；再加上均值填充，剩余奇异值 `[1.09 0.82 …]` 不为 0 就不奇怪了。

### 3.8 `demo_lsa`：从词频矩阵到概念空间

```python
    for j, doc in enumerate(docs):
        doc_lower = doc.lower()
        for i, term in enumerate(terms):
            td_matrix[i, j] = doc_lower.count(term)
    # ...
    doc_coords = np.diag(S[:k]) @ Vt[:k, :]
    # ...
    term_coords = U[:, :k] @ np.diag(S[:k])
    # ...
    doc_vecs = Vt[:k, :].T
```

- 词-文档矩阵是"行 = 词、列 = 文档"（15×6），所以 **U 的行对应词、Vᵀ 的列对应文档**。文档坐标取 `Σ_k·V_kᵀ` 的列，词坐标取 `U_k·Σ_k` 的行——两者落在同一个 k 维"概念空间"里。
- 输出很直观：第 1 维只有 fish_doc、ocean_doc 以及 fish/ocean/sea/water/swim/fin 这些"水"相关的词非零；第 2 维是"陆地宠物"；第 3 维把 cat（-1.414）和 dog（+1.414）分到两侧。
- ⚠️ `str.count(term)` 是**子串计数**，所以 "paws" 里的 paw、"meows" 里的 meow、"Dogs" 里的 dog 都会被算进去（这里恰好起到了粗糙的词干化作用），但也可能误匹配，例如 "fin" 会匹配 "find"。真实系统要先分词、做词形还原，并通常用 TF-IDF 加权。
- ⚠️ 打印坐标时乘了 Σ，算余弦相似度时却用的是**没乘 Σ** 的 `Vt[:k, :].T`。两种做法给出的相似度不同：例如 cat_doc 与 dog_doc，代码输出 -0.291；若用打印出来的 Σ 加权坐标计算，约为 0.169。经典 LSA 通常在 `Σ_k V_kᵀ` 空间里比较文档，这一点值得在阅读时留意。

### 3.9 `demo_noise_reduction`：找最优截断秩

```python
    clean = (5 * np.outer(np.sin(t1), np.cos(t2))
             + 3 * np.outer(np.cos(2 * t1), np.sin(t2))
             + 2 * np.outer(np.ones(m), np.sin(3 * t2)))
    # ...
        for k in range(1, min(m, n)):
            denoised = U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :]
            err = np.linalg.norm(denoised - clean, 'fro') / clean_norm
            if err < best_err:
                best_err = err
                best_k = k
```

- 干净信号是 3 个外积之和，所以秩为 3（输出 `Clean signal: rank 3`）。
- 加噪后奇异值谱出现明显**断崖**：前 3 个约 224/134/126，从第 4 个起掉到噪声水平（σ=1.0 时约 18）。4 档噪声下最优 k 都是 3，改善约 74%。
- 为什么改善比例几乎不随噪声强度变化？高斯噪声的能量均匀分布在所有方向上，而秩 3 的子空间只有约 `3(m+n−3)` 个自由度，占 `mn` 的 `531/8000 ≈ 6.6%`，保留下来的噪声误差约为原来的 `√0.066 ≈ 0.26`，即改善约 74%。
- ⚠️ 选最优 k 时用到了**干净信号 `clean`**——这是"上帝视角"（oracle），实际中你拿不到 clean。真实场景要靠谱间隙、能量阈值或交叉验证来选 k。

### 3.10 `pseudoinverse_via_svd` 与 `demo_pseudoinverse`

```python
def pseudoinverse_via_svd(A, tol=1e-10):
    U, S, Vt = np.linalg.svd(A, full_matrices=False)
    S_inv = np.array([1.0 / s if s > tol else 0.0 for s in S])
    return Vt.T @ np.diag(S_inv) @ U.T
```

- 直接对应讲义公式 `A⁺ = VΣ⁺Uᵀ`：`Vt.T` 就是 V，`U.T` 就是 Uᵀ，`Σ⁺` 由"非零奇异值取倒数、其余置 0"得到。用瘦 SVD 时 Σ 已是方的 k×k，不需要再"转置 Σ"。
- `tol` 是关键：数值上"应该为 0"的奇异值往往是 1e-16 这种舍入噪声，直接取倒数会得到 1e16，把噪声放大成垃圾解。⚠️ 这里是绝对阈值；`np.linalg.pinv` 用的是相对阈值（`rcond × σ_max`），对不同量级的矩阵更稳健。
- 演示三种情形：
  - **超定**（3 个方程 2 个未知数）：伪逆解 = `lstsq` 解 = 正规方程解 = `[1.5, 1.666667]`，残差范数 0.408248（无精确解，只能最小化残差）。
  - **欠定**（2 个方程 3 个未知数）：伪逆给出**最小范数解** `[1, 2, 3]`，范数 3.741657。
  - **奇异**（`[[1,2],[2,4]]`，σ = [5, 0]）：普通求逆会失败，伪逆仍给出 `[0.6, 1.2]`，且满足 `Ax = b`。

### 3.11 `demo_condition_number`：条件数与"平方"问题

```python
    for name, A in matrices:
        U, S, Vt = np.linalg.svd(A)
        cond = S[0] / S[-1] if S[-1] > 1e-15 else float('inf')
    # ...
    AtA = A.T @ A
    eig_vals = np.linalg.eigvalsh(AtA)
    # ...
    print(f"  A^T A condition number: {eig_vals[-1] / eig_vals[0]:.1f}")
```

- `S[0] / S[-1]`：NumPy 的奇异值按**降序**排列，所以第一个最大、最后一个最小。
- `np.linalg.eigvalsh` 专用于对称（Hermitian）矩阵，返回的特征值按**升序**排列，所以这里反过来用 `eig_vals[-1] / eig_vals[0]`。降序 vs 升序是 NumPy 中很容易搞反的细节。
- 输出：A 的条件数 40002.0，`AᵀA` 的条件数 1600159885.7 ≈ 40002²，直观说明"通过 AᵀA 计算会把条件数平方"。

### 3.12 `demo_pca_is_svd`：两条路径，同一个答案

```python
    X_centered = X - X.mean(axis=0)

    cov_matrix = (X_centered.T @ X_centered) / (n_samples - 1)
    eig_vals, eig_vecs = np.linalg.eigh(cov_matrix)
    idx = np.argsort(eig_vals)[::-1]
    eig_vals = eig_vals[idx]
    eig_vecs = eig_vecs[:, idx]

    U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
    svd_variance = S ** 2 / (n_samples - 1)
    # ...
    direction_match = all(
        np.allclose(np.abs(eig_vecs[:, i]), np.abs(Vt[i]), atol=1e-8)
        for i in range(n_features)
    )
```

- `X.mean(axis=0)` 得到每个特征的均值（形状 `(5,)`），`X - …` 利用**广播**对每一行减去均值。
- `np.linalg.eigh` 返回升序特征值，用 `np.argsort(…)[::-1]` 得到降序下标，再同时重排特征值和特征向量的**列**。
- 方向比较用 `np.abs`：输出里 PC1 是 `[-0.7559 -0.5357 …]`，V1 是 `[0.7559 0.5357 …]`，只差一个符号，二者都是合法的主成分。
- 可选的 sklearn 对比放在 `try/except ImportError` 里，没装 sklearn 也能跑。⚠️ 讲义说"sklearn 用 SVD 而不是特征分解实现 PCA"；但 scikit-learn 自 1.5 版起在 `svd_solver='auto'` 下，遇到"特征数 < 1000 且样本数 > 10 倍特征数"的数据（本例 200×5 正是如此）会选 `covariance_eigh`，也就是协方差特征分解。结果当然一致，只是"sklearn 一定用 SVD"的说法需要加限定。

### 3.13 `demo_matrix_properties`：从奇异值读出矩阵的"体检报告"

```python
    print(f"\nRank (non-zero singular values): {np.sum(S > 1e-10)}")
    # ...
    print(f"\nFrobenius norm: {np.linalg.norm(A, 'fro'):.6f}")
    print(f"  sqrt(sum(sigma_i^2)): {np.sqrt(np.sum(S ** 2)):.6f}")
    # ...
    print(f"\nNuclear norm (sum of singular values): {np.sum(S):.6f}")
```

- `np.sum(S > 1e-10)`：布尔数组求和 = True 的个数 = 数值秩。`[[1,2,3],[4,5,6],[7,8,9]]` 的第三个奇异值约为 0，秩 2。
- 三种范数：Frobenius `√Σσ²` = 16.881943（与逐元素计算一致）、谱范数 `σ₁` = 16.848103（与 `np.linalg.norm(A, 2)` 一致）、核范数 `Σσ` = 17.916473。
- 方阵 `|det| = Πσᵢ`：B 的 det = 8，奇异值 4×2 = 8。
- ⚠️ 函数开头的 `np.random.seed(42)` 在这里没有用到任何随机数，是多余的。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 `AᵀA` 幂迭代 + 紧缩实现 SVD | 一次讲清"SVD ↔ 特征分解"和外积形式 | 条件数平方、误差逐层累积、σ 接近时收敛慢；生产用 LAPACK（Golub-Kahan 双对角化） |
| 其余演示都用 `np.linalg.svd` | 让演示聚焦在"应用"而不是"算法" | 大矩阵只需前 k 项时，用 `scipy.sparse.linalg.svds` 或随机化 SVD |
| `full_matrices=False` | 只需要前 `min(m,n)` 个奇异向量，省内存 | 需要完整正交基（如零空间）时才用 `full_matrices=True` |
| 伪逆用绝对阈值 `1e-10` | 简单直观 | 生产用相对阈值 `rcond·σ_max`，或直接 `np.linalg.pinv` / `lstsq` |
| 用 QR 构造"谱已知"的矩阵 | 结果可手算验证 | — 这是写数值算法测试的通用技巧 |
| 推荐系统用均值填充 | 能直接套用标准 SVD | 预测偏向均值；生产用 ALS / Funk SVD，只在观测项上拟合并加正则 |
| LSA 用子串计数 | 代码短，无需分词库 | 会误匹配；生产先分词 / 词形还原，用 TF-IDF |
| 去噪时用干净信号选 k | 展示"最优 k 存在且等于真实秩" | 实际用谱间隙、能量阈值或交叉验证 |
| 所有演示都 `np.random.seed(42)` | 输出可复现，便于对照讲义 | — |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def power_iteration(M, num_iters=200, tol=1e-10)`、`def svd_from_scratch(A, k=None)` | 调用时可省略；`None` 作为"未指定"的哨兵值，在函数内再决定默认行为 |
| 多返回值 / 元组解包 | `return eigenvalue, v`；`U, S, Vt = np.linalg.svd(...)`；`m, n = A.shape` | 返回一个元组，接收时按位置拆开 |
| 条件表达式 | `np.column_stack(us) if us else np.empty((m, 0))` | `A if 条件 else B`，一行完成二选一；空列表 `[]` 视为假 |
| 带条件的列表推导 | `[1.0 / s if s > tol else 0.0 for s in S]` | 推导式里嵌条件表达式，逐元素决定取值 |
| `_` 作循环变量 | `for _ in range(num_iters):` | 表示"只关心循环次数，不用这个变量" |
| `break` | 收敛后 `break` 跳出 for 循环 | 提前结束循环 |
| `float('inf')` | `best_err = float('inf')` | 正无穷，作为"求最小值"的初始值 |
| 遍历元组列表 | `for name, A in matrices:` | 列表里每个元素是 `(名字, 矩阵)`，循环时直接解包 |
| `enumerate` | `for j, doc in enumerate(docs):` | 同时得到下标和元素 |
| 生成器 + `all()` | `all(np.allclose(...) for i in range(n_features))` | 所有元素为真才返回 True，遇到 False 立即短路 |
| `str.lower()` / `str.count()` | `doc.lower()`、`doc_lower.count(term)` | 转小写；统计子串出现次数（注意是子串，不是单词） |
| f-string 格式符 | `{S_np[i]:.4f}`、`{ratio:7.1%}`、`{storage:10,d}`、`{dl:>10s}`、`{err_ours:.10f}` | `.4f` 4 位小数；`%` 乘 100 并加百分号；`,d` 千分位整数；`>10s` 右对齐占 10 格 |
| `try / except ImportError` | 导入 `sklearn.decomposition.PCA` | 可选依赖：装了就对比，没装就 `pass` 跳过 |
| 函数内 `import` | `from sklearn.decomposition import PCA` 写在 try 里 | 延迟导入，避免脚本因可选依赖缺失而整体报错 |
| `@` 矩阵乘 | `U @ np.diag(S) @ Vt`、`v @ M @ v` | 对一维数组 `v @ M @ v` 就是二次型 `vᵀMv` |
| NumPy 切片 | `U[:, :k]`（前 k 列）、`Vt[:k, :]`（前 k 行）、`Vt[i]`（第 i 行） | 逗号分隔各维度，`:` 表示整维 |
| 布尔索引 / 取反 | `observed[~mask] = np.nan`、`filled[i, np.isnan(filled[i])] = row_mean` | 用布尔数组选中元素并赋值；`~` 对布尔数组取反 |
| 广播 | `X - X.mean(axis=0)`、`S * step1` | 形状兼容的数组自动扩展后逐元素运算 |
| `[::-1]` 反转 | `np.argsort(eig_vals)[::-1]` | 步长 -1 的切片，把升序下标变成降序 |
| 常用 NumPy 函数 | `np.outer`、`np.column_stack`、`np.diag`、`np.meshgrid`、`np.linspace(..., endpoint=False)`、`np.nanmean`、`np.cumsum`、`np.allclose`、`np.linalg.qr/eigh/eigvalsh/lstsq/solve/matrix_rank/det` | 外积、按列拼接、对角矩阵、网格、等距采样、忽略 NaN 的均值、累加、近似相等、各类线代例程 |
| `if __name__ == "__main__":` | 文件末尾依次调用 11 个 demo | 直接运行才执行演示，被 import 时只提供函数 |

---

## 6. 运行结果解读

已在临时副本中实际运行（`python3 svd.py`，NumPy 2.5.3，约 1 秒内完成）。关键输出与解读：

```text
Our singular values:   [3.4925 2.3241 1.9279 1.0079]
NumPy singular values: [3.4925 2.3241 1.9279 1.0079]     ← 从零实现与 LAPACK 对齐
Reconstruction error (ours):  0.0000000000               ← U·diag(S)·Vᵀ 完整还原 A
  i=0: sigma=3.4925, match=True ...                       ← A·vᵢ = σᵢ·uᵢ 逐个成立

Sigma (scaling): [4. 2.]                                  ← 对称正定矩阵：σ = 特征值，U = V
  ( 1.00, 0.00)  (-0.71,-0.71)  ( -2.83, -1.41)  (  3.00,  1.00)  check=(  3.00,  1.00)
                                                          ← 旋转 → 缩放 → 旋转，结果与 A@p 相同

Top 10 singular values: [50. 30. 15.  8.  3.  0.  0.  0.  0.  0.]
  3      8.5440    0.140501     6.8%                      ← √(8²+3²)=8.544，Eckart-Young
  5      0.0000    0.000000    11.3%                      ← 秩 5 矩阵，k=5 无损

  sigma_5   = 0.00                                        ← 合成图像秩为 3（见 3.6 的 ⚠️）
    2       1,026     1.6%   97.0928%   23.9339
    5       2,565     3.9%  100.0000%    0.0000
  200     102,600   156.6%  100.0000%    0.0000           ← k 过大，存储反而超过原图

Mean absolute error on missing ratings: 0.453             ← 均值填充 + 秩 3，预测偏向均值
Energy captured by rank-3: 99.6%

Singular values: [4.384 3.923 2.449 2.253 1.592 0.883]    ← LSA：第 1 维"水"，第 2 维"陆地宠物"
  fish_doc ... ocean_doc 1.000                            ← 两篇"水"文档在概念空间里完全同向

  Noise level sigma=1.0:
    Top 10 singular values: [223.19 134.62 124.98  18.4 ...]   ← 第 3、4 个之间的断崖
    Best truncation rank: k=3                             ← 等于真实秩
    Improvement: 74.6%

SVD minimum-norm solution:  [1. 2. 3.]                    ← 欠定：最小范数解
Pseudoinverse solution: [0.6 1.2]                         ← 奇异矩阵也能"求逆"

  A condition number:    40002.0
  A^T A condition number: 1600159885.7                    ← ≈ 40002²，条件数被平方

  Variances match: True
  Directions match (up to sign): True                     ← PCA = SVD
  sklearn PCA variance ratio: [0.4705 0.2213 0.1575 0.0982 0.0526]

Singular values: [16.848103  1.06837   0.      ]          ← [[1..9]] 秩 2
Product of singular values: 8.0000                        ← |det(B)| = Πσ
```

---

## 7. 动手改一改

1. **接口统一**：把 `svd_from_scratch` 的返回值改成 `U, S, Vt`（与 NumPy 一致），并修改 `demo_svd_basics` 中的重构代码；再顺手用上 `truncated_svd` 和 `reconstruct` 这两个没被调用的工具函数。
2. **观察收敛速度**：在 `power_iteration` 里记录实际迭代次数，分别用奇异值为 `[10, 1]` 和 `[10, 9.9]` 的矩阵测试（可用 3.5 节的 QR 技巧构造），验证收敛快慢与 `(σ₂/σ₁)²` 的关系。
3. **相对阈值**：把 `pseudoinverse_via_svd` 的阈值改成 `tol * S[0]`，并对 `A3 * 1e-12`（整体缩小的奇异矩阵）比较新旧两种阈值的结果。
4. **不用"上帝视角"选 k**：在 `demo_noise_reduction` 中改用"相邻奇异值比值最大的位置"作为截断点（谱间隙法），看它在 4 档噪声下是否都选出 k=3。
5. **LSA 改进**：先用正则 `re.findall(r"[a-z]+", doc.lower())` 分词再计数，并把相似度改为在 `Σ_k V_kᵀ` 空间计算，比较 cat_doc 与 dog_doc 的相似度变化。
6. **最小 ALS**：在 `demo_recommendation_system` 里实现一个只在 `mask` 为 True 的位置计算损失的交替最小二乘（加 L2 正则），与均值填充 + SVD 的 MAE 对比。

---

## 8. 常见坑

- **V 还是 Vᵀ**：`np.linalg.svd` 返回的是 `Vt`（行是右奇异向量），本文件的 `svd_from_scratch` 返回的是 `V`（列是右奇异向量）。混用会得到形状对得上、数值全错的结果。
- **S 是一维数组**：`U @ S @ Vt` 会报错或得到错误结果，要写 `U @ np.diag(S) @ Vt`，或用广播 `(U * S) @ Vt`。
- **奇异向量符号不唯一**：不同库、不同版本的 `uᵢ, vᵢ` 可能整体取反，比较时要用 `np.abs` 或 `±` 两种都试。
- **升序 vs 降序**：`np.linalg.svd` 的奇异值降序，`np.linalg.eigh / eigvalsh` 的特征值升序，取最大最小时别搞反。
- **伪逆不设阈值**：1e-16 量级的"伪零"奇异值取倒数后会把解炸掉；能用 `np.linalg.lstsq` / `pinv` 就别手写。
- **忘记中心化**：做 PCA 时不减均值，第一奇异向量会指向均值方向（就像 3.6 节图像的 σ₁ 被直流分量主导）。
