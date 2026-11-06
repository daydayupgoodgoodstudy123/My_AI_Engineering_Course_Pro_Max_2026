# 代码讲解 · dim_reduction.py

> **所属小节**：阶段 01 · 数学基础 · 第 10 节 降维 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python dim_reduction.py`（无命令行参数；MNIST 部分首次运行会通过 `fetch_openml` 联网下载约 50 MB 数据） ｜ **依赖**：`numpy`；MNIST / 对比 / t-SNE / 预处理部分需要 `scikit-learn`；UMAP 部分需要可选的 `umap-learn`（缺失时只打印安装提示）

---

## 1. 这份代码在考察什么

这份脚本围绕"如何把高维数据压到低维、同时保住结构"展开，从零实现与库调用相结合：

1. **从零实现 PCA**：中心化 → 协方差 → `eigh` 特征分解 → 排序 → 投影，外加 `inverse_transform` 做重构。只用 NumPy 的十几行代码就能与 sklearn 结果对齐。
2. **选择主成分个数**：在"5 个信息维度 + 噪声"的 20 维合成数据上，观察解释方差与重构误差如何揭示数据的真实维度。
3. **Kernel PCA**：手写 RBF 核、核矩阵中心化，解决线性 PCA 分不开的同心圆问题，并扫描 gamma。
4. **真实数据与工具对比**：在 MNIST 上与 sklearn PCA 对比，跑 t-SNE / UMAP 可视化，并测试"PCA 作为逻辑回归预处理"时 k 与准确率的关系。
5. **工程习惯**：特征向量符号不唯一时如何比较、可选依赖如何优雅降级、训练/测试集如何正确地拟合与变换。

> 一句话：**PCA 是"找对角度看数据"——这份代码让你亲手转动坐标系，再看看非线性方法在 PCA 失效的地方如何补位**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PCA` | 类 | `fit` / `transform` / `fit_transform` / `inverse_transform`，属性 `components`、`mean`、`eigenvalues`、`explained_variance_ratio_` | PCA、解释方差、重构 |
| `kernel_pca(X, n_components, kernel, gamma)` | 函数 | 构造核矩阵 → 中心化 → 特征分解 → 返回训练样本的核主成分坐标 | Kernel PCA、核技巧 |
| `reconstruction_error(X, X_reconstructed)` | 函数 | 逐元素均方误差 | 重构误差 |
| `demo_kernel_pca` | 演示 | 同心圆：线性 PCA vs RBF Kernel PCA，gamma 扫描 | 非线性流形 |
| `demo_reconstruction_error` | 演示 | 300×20、5 个信息维度的合成数据，k 从 1 到 20 | 有效维度、选 k |
| `demo_synthetic` | 演示 | 3 维数据（第 3 维是前两维的线性组合 + 噪声）降到 2 维并重构 | PCA 基本流程 |
| `demo_mnist` | 演示 | MNIST 前 5000 张，2/50 个主成分的解释方差，10/50/200 维重构误差 | 真实高维数据 |
| `demo_sklearn_comparison` | 演示 | 自写 PCA 与 sklearn PCA 对比（符号无关） | 正确性验证 |
| `demo_tsne` / `demo_umap` | 演示 | 先 PCA 到 50 维，再 t-SNE / UMAP 到 2 维 | 非线性可视化 |
| `demo_pca_preprocessing` | 演示 | k ∈ {10, 30, 50, 100, 200, 784} 时逻辑回归准确率 | PCA 作为预处理 |

执行顺序（`__main__`）：`demo_kernel_pca → demo_reconstruction_error → demo_synthetic → demo_mnist`（返回 `X, y, X_pca2d`）→ 后面四个 demo 都复用这份 MNIST 数据。前三个 demo 只依赖 NumPy，后面的都依赖 sklearn 和网络下载。

---

## 3. 逐段精讲

### 3.1 `PCA.fit`：五步走

```python
    def fit(self, X):
        self.mean = np.mean(X, axis=0)
        X_centered = X - self.mean

        cov_matrix = np.cov(X_centered, rowvar=False)

        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

        sorted_idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[sorted_idx]
        eigenvectors = eigenvectors[:, sorted_idx]

        self.components = eigenvectors[:, : self.n_components].T
        self.eigenvalues = eigenvalues[: self.n_components]
        total_var = np.sum(eigenvalues)
        self.explained_variance_ratio_ = self.eigenvalues / total_var

        return self
```

逐行对应讲义的五步：

| 代码 | 步骤 | 说明 |
|------|------|------|
| `np.mean(X, axis=0)`、`X - self.mean` | 1. 中心化 | `axis=0` 沿样本方向求每个特征的均值；减法依靠**广播**，(n,d) 减 (d,) |
| `np.cov(X_centered, rowvar=False)` | 2. 协方差 | `rowvar=False` 表示"每一列是一个变量"，得到 d×d 矩阵；分母是 n-1 |
| `np.linalg.eigh(cov_matrix)` | 3. 特征分解 | `eigh` 专用于**对称/厄米矩阵**：更快、更稳，保证特征值为实数、特征向量正交 |
| `np.argsort(...)[::-1]` | 4. 排序 | `eigh` 返回**升序**特征值，`[::-1]` 翻转成降序 |
| `eigenvectors[:, :k].T` | 5. 取前 k 个 | 特征向量是**列**，转置后每一**行**是一个主成分，形状 (k, d) |

- 为什么用 `eigh` 而不是 `eig`：协方差矩阵对称半正定（讲义 "symmetric and positive semi-definite"）。`eig` 是通用算法，可能返回带极小虚部的复数、特征向量也不保证正交。
- `eigenvectors[:, sorted_idx]` 是**花式索引**：按 `sorted_idx` 的顺序重排列，特征值与特征向量必须用同一个索引同步重排，否则就"张冠李戴"了。
- `total_var` 用的是**全部**特征值之和，所以 `explained_variance_ratio_` 是相对于总方差的比例，而不是相对于前 k 个的比例。
- 属性名 `explained_variance_ratio_` 末尾带下划线，模仿 sklearn 约定："拟合后才有的属性"。
- `return self` 让你可以写 `PCA(2).fit(X).transform(X)` 这样的链式调用。
- ⚠️ 简化：没有对特征做标准化（量纲差异大时第一主成分会被大方差特征主导）；d 很大时构造 d×d 协方差矩阵很贵，生产中用 SVD（sklearn 就是如此）。

### 3.2 `transform` 与 `inverse_transform`

```python
    def transform(self, X):
        X_centered = X - self.mean
        return X_centered @ self.components.T

    def fit_transform(self, X):
        self.fit(X)
        return self.transform(X)

    def inverse_transform(self, X_reduced):
        return X_reduced @ self.components + self.mean
```

- 投影：`Z = (X - μ) Wᵀ`，形状 (n,d)@(d,k) → (n,k)。每一列是样本在一个主成分上的坐标。
- 重构：`X̂ = Z W + μ`，(n,k)@(k,d) → (n,d)。因为 W 的行是**标准正交**的，`Wᵀ` 就是"投影"的伪逆，重构就是"投影回原空间的正交投影"。
- `transform` 用的是 `fit` 时保存的 `self.mean`——对新数据（如测试集）也必须用**训练集的均值**中心化，不能用新数据自己的均值。
- k = d 时 `WᵀW = I`，重构完全无损；k < d 时丢失的就是被丢弃方向上的方差。

### 3.3 `kernel_pca`：核矩阵、中心化与投影

```python
def kernel_pca(X, n_components, kernel="rbf", gamma=1.0):
    n = X.shape[0]

    if kernel == "rbf":
        sq_dists = np.sum(X ** 2, axis=1).reshape(-1, 1) + np.sum(X ** 2, axis=1).reshape(1, -1) - 2 * X @ X.T
        K = np.exp(-gamma * sq_dists)
    elif kernel == "poly":
        K = (X @ X.T + 1) ** gamma
    else:
        K = X @ X.T

    one_n = np.ones((n, n)) / n
    K_centered = K - one_n @ K - K @ one_n + one_n @ K @ one_n
```

- **向量化的两两距离**：`‖xᵢ - xⱼ‖² = ‖xᵢ‖² + ‖xⱼ‖² - 2xᵢ·xⱼ`。`reshape(-1, 1)` 变成列向量 (n,1)，`reshape(1, -1)` 变成行向量 (1,n)，两者相加通过广播得到 (n,n) 矩阵，再减去 `2 X Xᵀ`。没有任何 Python 循环。
- RBF 核 `K = exp(-γ·‖x-y‖²)`：距离越近核值越接近 1，越远越接近 0。
- ⚠️ `poly` 分支里 `gamma` 被当作**多项式次数**使用（`(x·y + 1)^gamma`），与 RBF 分支中"带宽"的含义完全不同，属于参数名复用，使用时要注意。
- **核矩阵中心化**：无法显式算出 φ(x) 再减均值，只能在核矩阵上等价操作：`K_c = K - 1ₙK - K1ₙ + 1ₙK1ₙ`（`1ₙ` 是元素全为 1/n 的矩阵）。它等价于 `(φ(xᵢ) - φ̄)·(φ(xⱼ) - φ̄)`。
- ⚠️ 浮点误差可能让个别 `sq_dists` 出现 `-1e-15` 这类极小负数，`exp` 后略大于 1，影响可以忽略；更严谨的写法会 `np.maximum(sq_dists, 0)`。

```python
    eigenvalues, eigenvectors = np.linalg.eigh(K_centered)

    sorted_idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[sorted_idx]
    eigenvectors = eigenvectors[:, sorted_idx]

    top_vals = eigenvalues[:n_components]
    top_vecs = eigenvectors[:, :n_components]

    for i in range(n_components):
        if top_vals[i] > 1e-10:
            top_vecs[:, i] = top_vecs[:, i] / np.sqrt(top_vals[i])

    return top_vecs * top_vals[:n_components]
```

- 对 n×n 的中心化核矩阵做特征分解（这里的"维度"是**样本数** n，而不是特征数——这就是 Kernel PCA 的 O(n³) 瓶颈）。
- 最后几行"先除以 `√λ` 再乘以 `λ`"，净效果是返回 `v·√λ`。这正是训练样本在核主成分上的投影：主轴的展开系数 `α = v/√λ`，投影 `K_c·α = λv/√λ = √λ·v`。实测与 `sklearn.decomposition.KernelPCA` 的 `fit_transform` 结果符号无关的最大差异约 `6e-15`。
- `top_vecs * top_vals[:n_components]`：(n,k) 乘 (k,)，广播到每一行，相当于每一列乘以对应的特征值。
- `if top_vals[i] > 1e-10` 防止对零或负的特征值开方。
- ⚠️ 讲义第 4 步说"eigenvectors scaled by 1/sqrt(eigenvalue) are the projections"并不准确：`v/√λ` 是用于新样本投影的对偶系数 α，训练样本的投影是 `√λ·v`。
- ⚠️ 函数只返回训练样本的坐标，没有保存 α 和训练数据，所以**不能对新样本做 transform**。

### 3.4 `demo_kernel_pca`：同心圆

```python
    X_circles = np.vstack([inner, outer])
    labels = np.array([0] * n_per_ring + [1] * n_per_ring)

    pca_linear = PCA(n_components=1)
    X_linear = pca_linear.fit_transform(X_circles)

    inner_range_linear = (X_linear[labels == 0].min(), X_linear[labels == 0].max())
    outer_range_linear = (X_linear[labels == 1].min(), X_linear[labels == 1].max())
    # ...
    overlap = inner_range_linear[1] > outer_range_linear[0] and outer_range_linear[1] > inner_range_linear[0]
```

- 两个半径分别约为 1 和 3 的圆环（半径加了 σ=0.1 的噪声），各 200 个点。
- `X_linear[labels == 0]` 是**布尔掩码索引**：只取标签为 0 的行。
- `overlap` 用的是区间重叠判断：两个区间 `[a₁,b₁]`、`[a₂,b₂]` 重叠当且仅当 `b₁ > a₂ 且 b₂ > a₁`。线性 PCA 把圆投到一条直线上，内环落在 `[-1.13, 1.35]`，被外环的 `[-3.10, 3.24]` 完全覆盖。
- Kernel PCA 的"分离度"用两环在第一主成分上的**均值之差**衡量。
- ⚠️ 均值之差只是粗略指标：它不能保证两类可线性分开，而且不同 gamma 下投影坐标的整体尺度（与 `√λ` 有关）不同，跨 gamma 比较这个数并不完全公平。额外验证表明：γ=0.5 时第一主成分上内环约 `[-0.55, -0.12]`、外环约 `[0.26, 0.42]`，确实完全分开；γ=0.1 时线性分类准确率只有约 50%，γ=1.0、5.0 时只能部分分开。

### 3.5 `demo_reconstruction_error`：找出"有效维度"

```python
    base = np.random.randn(n_samples, n_informative)
    mixing = np.random.randn(n_informative, n_features)
    noise = np.random.randn(n_samples, n_features) * 0.1
    X = base @ mixing + noise
    # ...
    for k in [1, 2, 3, 5, 10, 15, 20]:
        pca_k = PCA(n_components=k)
        X_reduced = pca_k.fit_transform(X)
        X_reconstructed = pca_k.inverse_transform(X_reduced)
        mse = reconstruction_error(X, X_reconstructed)
        cumulative = sum(pca_k.explained_variance_ratio_)
        ev = pca_k.explained_variance_ratio_[-1] if k > 0 else 0
```

- 数据生成：5 个潜在因子经过 5×20 的随机混合矩阵变成 20 维，再加标准差 0.1 的噪声。所以协方差矩阵应有 5 个大特征值 + 15 个约 0.01 的"噪声特征值"。
- `ev` 是**第 k 个**主成分自己的解释方差比（不是累计值）。`if k > 0 else 0` 是防御写法，列表里的 k 都大于 0。
- 重构 MSE 与特征值的精确关系：`MSE = (n-1)/n × Σ(被丢弃的特征值) / d`。`n-1` 来自 `np.cov` 的无偏估计，`/d` 来自对 n×d 个元素求平均。这就是讲义"Reconstruction error = sum of eigenvalues NOT included"的完整版本。
- ⚠️ 小冗余：`total_var_pca` 拟合了一个全成分 PCA 并取出 `all_eigenvalues`，但后续没有使用；循环外的 `cumulative = 0.0` 也会被循环内直接覆盖。每个 k 都重新 `fit` 一次也是重复计算，其实一次全成分分解就能得到所有 k 的结果。

### 3.6 `demo_mnist` 与 `demo_sklearn_comparison`

```python
    from sklearn.datasets import fetch_openml

    mnist = fetch_openml("mnist_784", version=1, as_frame=False, parser="auto")
    X = mnist.data[:5000].astype(float)
    y = mnist.target[:5000].astype(int)
```

- `import` 写在函数内部（**惰性导入**）：只有运行到这个 demo 时才需要 sklearn，前三个纯 NumPy 的 demo 不受影响。
- `fetch_openml` 会联网下载并缓存到 `~/scikit_learn_data`；`as_frame=False` 返回 NumPy 数组；`target` 是字符串（如 `'5'`），所以要 `astype(int)`。
- 只取前 5000 张，控制 t-SNE 和特征分解的时间。

```python
    diff = np.abs(np.abs(X_ours) - np.abs(X_sklearn))
    print(f"Max absolute difference (sign-invariant): {diff.max():.10f}")
```

- 特征向量 `v` 与 `-v` 都合法，不同实现可能给出相反的符号，导致整列投影坐标取反。**先取绝对值再比较**，就能消除符号歧义。
- 注意 `X_ours` 是从 `demo_mnist` 传进来的 `X_pca2d`，函数里新建的 `pca_ours` 只用来打印解释方差比。

### 3.7 t-SNE、UMAP 与可选依赖

```python
def demo_umap(X, y):
    # ...
    try:
        from umap import UMAP

        pca_pre = PCA(n_components=50)
        X_pca = pca_pre.fit_transform(X)

        reducer = UMAP(n_components=2, n_neighbors=15, min_dist=0.1, random_state=42)
        X_umap = reducer.fit_transform(X_pca)
        # ...
    except ImportError:
        print("Install umap-learn to run this demo: pip install umap-learn")
```

- t-SNE 与 UMAP 都**先用 PCA 降到 50 维**再降到 2 维：既去掉噪声方向，又显著加速（t-SNE 的距离计算与维度成正比）。这是业界的标准做法。
- `try / except ImportError`：可选依赖缺失时打印提示而不是崩溃，脚本其余部分照常运行。
- 参数含义：t-SNE 的 `perplexity=30`（有效邻居数）；UMAP 的 `n_neighbors=15`（局部结构范围）、`min_dist=0.1`（输出中点的最小间距，越小簇越紧）。`random_state=42` 固定随机性以便复现。
- `demo_tsne` 和 `demo_umap` 只打印输出的形状和坐标范围（没有画图），坐标的绝对数值本身没有意义。
- 参数 `y` 被传入但没有使用（原本可用于给散点图上色）。

### 3.8 `demo_pca_preprocessing`：k 与准确率

```python
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    for k in [10, 30, 50, 100, 200, 784]:
        if k < X_train.shape[1]:
            pca_k = SklearnPCA(n_components=k)
            X_tr = pca_k.fit_transform(X_train)
            X_te = pca_k.transform(X_test)
            var_captured = sum(pca_k.explained_variance_ratio_)
        else:
            X_tr = X_train
            X_te = X_test
            var_captured = 1.0
```

- **只在训练集上 fit**，测试集只 `transform`——避免数据泄漏，这是 PCA 预处理最重要的工程规范。
- `k = 784` 时等于原始维度，直接用原始像素作为对照组。
- 讲义结论："Performance plateaus well before 784 dimensions. That plateau is your operating point." 准确率进入平台期的 k 就是性价比最高的选择。
- ⚠️ 原始像素值在 0–255，未做缩放，`LogisticRegression` 在高维原始特征上可能需要更多迭代甚至给出收敛警告；生产中通常先做 `StandardScaler` 或除以 255。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 协方差 + `eigh` 实现 PCA | 与讲义五步一一对应，最易理解 | d 大时构造 d×d 矩阵昂贵且损失精度；生产用 SVD / 随机化 SVD（sklearn 的做法） |
| 只中心化、不标准化 | 保持算法最小化 | 特征量纲不同时应先标准化 |
| 模仿 sklearn 接口（`fit/transform`、`explained_variance_ratio_`、`return self`） | 自写版与库版可以无缝替换、对照 | — |
| 比较时取绝对值 | 特征向量符号不唯一 | 也可以统一符号约定（如令每个主成分绝对值最大的分量为正，sklearn 有类似处理） |
| Kernel PCA 写成函数、只返回训练集投影 | 聚焦核技巧本身 | 无法处理新样本；生产用 `sklearn.decomposition.KernelPCA`，大数据用 Nyström / 随机傅里叶特征 |
| 用均值差衡量核 PCA 分离度 | 一个数字就能比较 | 不等于线性可分，跨 gamma 尺度不一致 |
| 函数内惰性导入 sklearn / umap | 前几个 demo 只需 NumPy；可选依赖缺失时优雅降级 | 导入错误推迟到运行时才暴露 |
| t-SNE/UMAP 前先 PCA 到 50 维 | 去噪 + 加速 | 多一个超参数（50） |
| 固定随机种子 42 | 结果可复现 | `np.random.seed` 修改的是全局状态；新代码推荐 `np.random.default_rng(42)` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类与 `return self` | `def fit(self, X): ... return self` | 返回实例本身，支持链式调用 `PCA(2).fit(X).transform(X)` |
| 属性名末尾下划线 | `self.explained_variance_ratio_` | sklearn 约定：拟合后才产生的属性 |
| `None` 占位属性 | `self.components = None` | 构造时先占位，`fit` 时再赋值 |
| 函数内惰性导入 | `from sklearn.datasets import fetch_openml` 写在 `demo_mnist` 内 | 只在需要时导入，减少硬依赖 |
| `import ... as` 别名 | `from sklearn.decomposition import PCA as SklearnPCA` | 避免与自定义的 `PCA` 类重名 |
| `try / except ImportError` | `demo_umap` | 可选依赖缺失时优雅降级 |
| 多返回值与解包 | `return X, y, X_pca2d`；`X, y, X_pca2d = demo_mnist()`；`X_train, X_test, y_train, y_test = train_test_split(...)` | 函数返回元组，调用方一次拆开 |
| 列表拼接 | `[0] * n_per_ring + [1] * n_per_ring` | 先重复再连接，构造标签 |
| 条件表达式 | `... [-1] if k > 0 else 0` | 一行 if-else |
| `and` 组合条件 | `overlap = a > b and c > d` | 两个条件都为真才为真 |
| f-string 格式符 | `{k:>3d}`、`{var:.4f}`、`{sum(...):.2%}`、`{g:<4}` | 右对齐宽度 3 的整数；4 位小数；百分比；左对齐宽度 4 |
| f-string 填充字符 | `{'':->4s}` | 用 `-` 把空字符串右对齐填充到宽度 4，即输出 `----`，用来画表格分隔线 |
| NumPy `axis` 参数 | `np.mean(X, axis=0)`、`np.sum(X ** 2, axis=1)` | `axis=0` 沿行方向（对每列）计算；`axis=1` 对每行计算 |
| 广播 | `X - self.mean`；`(n,1) + (1,n)`；`top_vecs * top_vals` | 形状不同的数组按规则自动扩展后逐元素运算 |
| `reshape(-1, 1)` | `np.sum(X ** 2, axis=1).reshape(-1, 1)` | `-1` 表示"自动推断这一维长度" |
| `@` 矩阵乘法 | `X_centered @ self.components.T` | 等价于 `np.matmul` |
| 切片与反转 | `[::-1]`、`[:, : self.n_components]`、`.T` | 反转数组；取前 k 列；转置 |
| 花式索引 | `eigenvectors[:, sorted_idx]` | 用整数数组按指定顺序取列（返回副本） |
| 布尔掩码索引 | `X_linear[labels == 0]`、`X_kpca[labels == 0, 0]` | 用条件筛选行；可与列索引组合 |
| `np.column_stack` / `np.vstack` | `np.column_stack([x1, x2, x3])`、`np.vstack([inner, outer])` | 按列拼成矩阵；按行堆叠 |
| `np.random` 旧接口 | `np.random.seed(42)`、`uniform`、`normal`、`randn` | 设全局种子；均匀分布；正态分布；标准正态矩阵 |
| `.astype(...)` | `mnist.data[:5000].astype(float)` | 转换数组元素类型 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行全部 demo |

---

## 6. 运行结果解读

> **运行说明**：完整运行 `python dim_reduction.py` 需要 `fetch_openml` 联网下载 MNIST，本环境按约束不联网下载，因此**只实际运行了前三个纯 NumPy 的 demo**（在临时副本中导入模块后依次调用 `demo_kernel_pca`、`demo_reconstruction_error`、`demo_synthetic`，约 0.3 秒）。MNIST 相关 demo 未实际运行（原因：需联网下载数据）；UMAP 未安装。为了帮助理解后半部分的行为，另外用 sklearn 自带的 8×8 手写数字 `load_digits`（1797×64，离线可用）**替代 MNIST** 调用了后面几个 demo，结果单独列出，**不是原脚本的输出**。

### 6.1 Kernel PCA（实际运行）

```text
  Linear PCA (1 component):
    Inner ring range: [-1.13, 1.35]
    Outer ring range: [-3.10, 3.24]
    Overlapping: True (linear PCA cannot separate circles)

  Kernel PCA (RBF, gamma=0.5, 2 components):
    Inner ring PC1 mean: -0.3585
    Outer ring PC1 mean: 0.3585
    Separation on PC1: 0.7170
    gamma=0.1   separation=0.0046      ← 核太"宽"，近似线性结构，分不开
    gamma=0.5   separation=0.7170      ← 最佳，PC1 上两环完全分开
    gamma=1.0   separation=0.2631
    gamma=5.0   separation=0.0619      ← 核太"窄"，每个点只看见近邻
```

- 两环均值关于 0 对称（±0.3585），因为核矩阵已中心化，投影坐标整体均值为 0，两环点数相同。
- gamma 的合理范围与数据尺度相关：两环相距约 2，`γ=0.5` 时距离为 2 的点对核值约 `e^{-2} ≈ 0.14`，既能区分远近又不至于"全是 0"。

### 6.2 重构误差 vs 主成分个数（实际运行）

```text
     k     Recon MSE   Explained Var   Cumulative
     1        3.1151        0.428028       0.4280
     2        1.8977        0.223531       0.6516
     3        1.0073        0.163484       0.8150
     5        0.0075        0.056768       0.9986    ← 5 个信号方向全部保留
    10        0.0044        0.000100       0.9992    ← 第 10 个主成分只解释 0.01% 的方差
    15        0.0019        0.000085       0.9996
    20        0.0000        0.000061       1.0000    ← 全部保留，无损重构
```

- 从 k=3 到 k=5，MSE 下降两个数量级；之后每加一个主成分只多解释约 0.01% 的方差——"肘部"清晰地出现在 5。
- 全成分特征值约为 `[46.8, 24.4, 17.9, 13.9, 6.2, 0.014, 0.013, …, 0.0066]`，后 15 个都接近噪声方差 0.01。
- 用公式验证：k=5 时 `MSE = 299/300 × Σ(后 15 个特征值) / 20 ≈ 0.0075`，与输出完全一致（对每个 k 都精确吻合）。
- 注意表中没有 k=4，这只是演示列表的选择。

### 6.3 3 维合成数据（实际运行）

```text
Original shape: (500, 3)
Reduced shape:  (500, 2)
Explained variance ratios: [0.59004014 0.40926775]
Total variance captured: 0.9993
Reconstruction MSE: 0.002424
```

- `x3 = 0.5·x1 + 0.3·x2 + 小噪声`，数据几乎落在一个平面上（一个倾斜的圆环），所以 2 个主成分就捕获 99.93% 的方差；第 3 个特征值只占约 0.07%，对应 x3 中噪声的那一点点方差。
- 两个主成分的比例接近 59:41 而不是 50:50，是因为 x3 主要沿 x1 方向叠加（系数 0.5 > 0.3），让这个方向的方差更大。

### 6.4 用 `load_digits` 替代 MNIST 的参考结果（非原脚本输出）

```text
Our explained variance:     [0.14890594 0.13618771]
Sklearn explained variance: [0.14890594 0.13618771]
Max absolute difference (sign-invariant): 0.0000000000   ← 自写 PCA 与 sklearn 完全一致

t-SNE output shape: (1797, 2)                            ← 标题仍打印 "MNIST (5000 samples)"，是硬编码字符串
Install umap-learn to run this demo: pip install umap-learn

k= 10  accuracy=0.9333  variance=0.7376
k= 30  accuracy=0.9722  variance=0.9593
k= 50  accuracy=0.9722  variance=0.9995
k=100  accuracy=0.9750  variance=1.0000                  ← 64 维数据下 k≥64 时走"原始特征"分支
```

- 在 64 维的 digits 上，30 个主成分（约 96% 方差）的准确率已经接近使用全部特征——这正是讲义说的"平台期"。MNIST 上的具体数值会不同，但趋势一致。
- 对于原脚本在 MNIST 上的输出，可以预期：2 个主成分只能解释很小一部分方差（2D 散点图上各数字大量重叠），50 个主成分能解释大部分方差；重构 MSE 随 k 从 10 → 50 → 200 明显下降；逻辑回归准确率在 k 约 50–100 处进入平台期。

---

## 7. 动手改一改

1. **（入门）** 在 `demo_reconstruction_error` 中打印全成分 PCA 的 `all_eigenvalues`，确认"5 个大 + 15 个约 0.01"，并用 `(n-1)/n × Σ丢弃特征值 / d` 逐行核对 MSE 列。
2. **（入门）** 给 `PCA` 类加一个参数 `standardize=False`：为 True 时在 `fit` 中保存每个特征的标准差并在 `transform / inverse_transform` 中相应缩放；用"收入 + 年龄"这类量纲差异大的数据对比结果。
3. **（进阶）** 用 SVD 重写 `fit`：`U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)`，主成分是 `Vt[:k]`，特征值是 `S**2 / (n-1)`；验证与 `eigh` 版本的结果（符号无关）一致。
4. **（进阶）** 把 `kernel_pca` 改成类 `KernelPCA`，保存训练数据、`α = v/√λ` 和核矩阵的行/列均值，实现对新样本的 `transform`（新样本的核向量也要按训练集统计量中心化）。
5. **（进阶）** 讲义练习 3：用 `sklearn.datasets.make_classification(n_features=50, n_informative=5, n_redundant=0)` 生成数据，画出（或打印）累计解释方差，看看曲线能否识别出"有效维度为 5"，并思考为什么结果可能不如本文件的合成数据那样干净。
6. **（挑战）** 实现基于重构误差的异常检测：在 `demo_reconstruction_error` 的数据上拟合 `PCA(5)`，以训练集逐样本重构误差的 99 分位数为阈值，混入若干随机样本，统计检出率与误报率。

---

## 8. 常见坑

- **用 `np.linalg.eig` 代替 `eigh`**：对称矩阵也可能得到带极小虚部的复数结果、非正交的特征向量；对称矩阵一律用 `eigh`。
- **忘记 `eigh` 返回升序**：不做 `[::-1]` 的话，"前 k 个"其实是方差最小的 k 个方向。
- **特征值与特征向量没有同步重排**：必须用同一个 `sorted_idx` 同时索引两者，而且特征向量是**列**（`[:, sorted_idx]`），不是行。
- **测试集用自己的均值中心化或重新 fit**：会导致训练/测试坐标系不一致或数据泄漏；只能用训练集拟合的 `mean` 和 `components`。
- **直接比较两个实现的投影坐标**：特征向量符号不唯一，要么取绝对值比较，要么统一符号。
- **把 t-SNE / UMAP 的坐标当特征或解读簇间距离**：它们只适合可视化。
- **Kernel PCA 的 gamma 随手取 1.0**：效果强烈依赖数据尺度，本例中 γ=1.0 明显不如 γ=0.5。
