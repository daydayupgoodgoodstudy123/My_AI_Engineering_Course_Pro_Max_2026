---
name: skill-svd
description: Apply SVD to real problems including compression, denoising, recommendations, and least-squares solving
phase: 1
lesson: 11
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


您是将奇异值分解应用于实际工程问题的专家。当任务涉及矩阵、数据压缩、噪声、缺失数据或线性系统时，确定 SVD 是否是正确的工具以及如何应用它。

<a id="decision-framework"></a>

## 决策框架

<a id="step-1-identify-the-problem-type"></a>

### 第 1 步：确定问题类型

- **数据压缩/降维**：使用截断SVD。保留前 k 个奇异值。根据能量阈值（95% 是常见目标）或下游任务性能来选择 k。
- **降噪**：计算完整的SVD。寻找奇异值谱中的间隙。在间隙下方截断。该间隙将信号与噪声分开。
- **缺失数据/建议**：填充缺失条目（行平均值或零），计算SVD，以低等级重建。在生产中，使用 ALS 或增量 SVD 来本地处理丢失的数据。
- **最小二乘/伪逆**：计算 SVD。反转非零奇异值。将 V Sigma+ U^T 乘以目标向量。比正规方程更稳定。
- **文本相似度/主题建模**：构建术语-文档矩阵。应用 SVD（这是 LSA/LSI）。将项目文档和术语放入低级空间。使用 cosine similarity 进行比较。
- **数值排名确定**：计算SVD。计算高于阈值（相对于最大值）的奇异值。这比行减少更可靠。
- **矩阵范数计算**：谱范数=最大奇异值。弗罗贝尼乌斯范数 = sqrt（奇异值平方和）。核范数=奇异值之和。
- **条件号**：sigma_max / sigma_min。告诉您系统对扰动的敏感程度。

<a id="step-2-choose-the-right-variant"></a>

### 第 2 步：选择正确的变体

| 情况 | 方法 | 为什么 |
|-----------|--------|-----|
| 密集矩阵，需要完全分解 | `np.linalg.svd(A)` / `svd(A)` 位于 Julia | 标准算法，数值稳定 |
| 仅需要前 k 个组件 | `scipy.sparse.linalg.svds(A, k)` | 当 k 很小时，比完全 SVD 更快 |
| 稀疏矩阵 | `scipy.sparse.linalg.svds` | 有效处理稀疏存储 |
| Streaming数据 | 增量SVD/在线SVD | 更新分解而无需从头开始重新计算 |
| 缺失数据（建议） | ALS、Funk SVD 或 NMF | 标准 SVD 需要完整的矩阵 |
| 非常大的矩阵（数百万行） | 随机 SVD (`sklearn.utils.extmath.randomized_svd`) | O(mn log k) 而不是 O(mn min(m,n)) |
| 基于中心数据的 PCA | 中心数据矩阵的 SVD | 相当于协方差的特征分解，但更稳定 |

<a id="step-3-choose-the-rank-k"></a>

### 步骤3：选择等级k

- **能量阈值**：计算累积能量 = sum(sigma_1^2 ... sigma_k^2) / sum(全部 sigma^2)。当能量超过 0.95（或高保真任务为 0.99）时停止。
- **间隙检测**：绘制奇异值。寻找急剧下降。间隙表示信号和噪声之间的边界。
- **交叉验证**：对于下游任务，扫描 k 并测量保留数据的性能。
- **Elbow 方法**：绘制重建误差与 k 的关系。弯头是添加更多组件不再有帮助的地方。
- **领域知识**：如果知道数据有d个潜在因素，则使用k = d。

<a id="step-4-validate-results"></a>

### 第 4 步：验证结果

- **重建错误**：计算 ||A-A_k|| / ||一个||。如果截断有意义，则应该很小。
- **解释方差**：对于PCA/压缩，报告捕获的总方差（能量）的分数。
- **下游任务性能**：如果SVD是预处理步骤，则测量端到端指标。
- **目视检查**：对于图像，目视比较原始图像和重建图像。如需建议，请根据已知评级检查预测。

<a id="common-mistakes"></a>

## 常见错误

- 通过 A^T A 的特征分解计算 SVD。这会平方条件数并损失数值精度。使用专用 SVD 例程。
- 当只需要前 k 个分量时，使用完整的 SVD。对于大型矩阵，请使用截断或随机 SVD。
- 将 SVD 直接应用于缺少条目的矩阵。标准 SVD 需要完整的矩阵。请改用矩阵补全方法（ALS、Funk SVD）。
- 忽略居中。对于 PCA，数据必须在 SVD 之前居中（减去平均值）。如果没有居中，第一个分量捕获平均值，而不是方差。
- 过度截断。如果保留的奇异值太少，就会丢失信号。如果保留太多，就会留下噪音。使用能量阈值或交叉验证。
- 将 SVD 与特征分解混淆。 SVD 适用于任何矩阵（任何形状、任何等级）。特征分解需要一个带有全套eigenvectors的方阵。对于对称正半定矩阵，它们是相同的。

<a id="code-patterns"></a>

## 代码模式

<a id="quick-compression"></a>

### 快速压缩
```python
U, S, Vt = np.linalg.svd(A, full_matrices=False)
k = np.searchsorted(np.cumsum(S**2) / np.sum(S**2), 0.95) + 1
A_compressed = U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :]
```

<a id="pseudoinverse-for-least-squares"></a>

### 最小二乘的伪逆
```python
U, S, Vt = np.linalg.svd(A, full_matrices=False)
S_inv = np.array([1/s if s > 1e-10 else 0 for s in S])
x = Vt.T @ np.diag(S_inv) @ U.T @ b
```

<a id="denoising"></a>

### 去噪
```python
U, S, Vt = np.linalg.svd(noisy_data, full_matrices=False)
k = find_gap(S)
clean_data = U[:, :k] @ np.diag(S[:k]) @ Vt[:k, :]
```

<a id="large-scale-pca"></a>

### 大规模主成分分析
```python
from sklearn.utils.extmath import randomized_svd
U, S, Vt = randomized_svd(X_centered, n_components=50, random_state=42)
explained_variance = S**2 / (n_samples - 1)
```

<a id="when-not-to-use-svd"></a>

## 何时不使用 SVD

- 该矩阵非常稀疏，您只需要几个组件。直接使用稀疏特征求解器。
- 您需要非负因素（主题建模、谱分解）。使用 NMF 代替。
- 数据具有线性方法无法捕获的强非线性结构。使用自动编码器或流形学习。
- 您需要实时更新 streaming 数据，并且矩阵不断变化。使用增量/在线 SVD 或近似方法。
- 该矩阵适合内存，但太大，甚至随机 SVD 也太慢。考虑绘制草图方法或基于 sampling 的方法。

<a id="computational-cost"></a>

## 计算成本

| 方法 | 时间 | 空间 |
|--------|------|-------|
| m x n 矩阵的全 SVD | O(mn min(m,n)) | O(mn) |
| 截断 SVD（前 k） | O(mnk) | O((m+n)k) |
| 随机 SVD（前 k 个） | O(mn log k) | O((m+n)k) |
| 幂迭代（1 个向量） | O(mn * iters) | O(m+n) |

对于 10000 x 5000 矩阵：
- 完整 SVD：约 2500 亿次操作
- 截断 SVD (k=50)：约 25 亿次运算
- 随机 SVD (k=50)：约 5 亿次操作

选择符合您的规模和精度要求的方法。
