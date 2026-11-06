<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="norms-and-distances"></a>

# 范数与距离

> 您的距离函数定义了“相似”的含义。选择错误，下游的一切都会崩溃。

**类型：** 构建
**语言：** Python
**先决条件：** 第 1 阶段，第 01 课（线性代数直觉）、第 02 课（向量、矩阵和运算）
**时间：** ~90 分钟

<a id="learning-objectives"></a>

## 学习目标

- 从头开始实现 L1、L2、cosine、Mahalanobis、Jaccard 和编辑距离函数
- 为给定的 ML 任务选择适当的距离度量并解释替代方案失败的原因
- 将 L1 和 L2 范数连接到 LASSO 和 Ridge 正则化及其几何约束区域
- 演示同一数据集如何在不同指标下产生不同的最近邻

<a id="the-problem"></a>

## 问题

你有两个向量。也许它们是单词 embeddings。也许它们是用户个人资料。也许它们是像素阵列。您需要知道：它们有多接近？

答案完全取决于您选择的距离函数。两个数据点在一个指标下可以是最近的邻居，而在另一个指标下则可以相距很远。你的 KNN 分类器、你的推荐引擎、你的 vector database、你的聚类算法、你的 loss function ——它们都取决于这个选择。如果出错，你的模型就会针对错误的事情进行优化。

没有通用的最佳距离。 L2 适用于空间数据。 Cosine similarity 主导 NLP。 Jaccard 手柄套装。编辑距离处理字符串。马哈拉诺比斯解释了相关性。瓦瑟斯坦移动概率质量。每个都编码了关于“相似”含义的不同假设。

本课程从头开始构建每个主要距离函数，向您展示每个距离函数何时是正确的工具，并演示相同的数据如何根据您使用的度量产生完全不同的最近邻。

<a id="the-concept"></a>

## 概念

<a id="norms-measuring-vector-magnitude"></a>

### 规范：测量矢量幅度

范数测量向量的“大小”。两个向量之间的每个距离函数都可以写成它们差值的范数： d(a, b) = ||a-b||。所以理解规范就是理解距离。

<a id="l1-norm-manhattan-distance"></a>

### L1 范数（曼哈顿距离）

L1 范数将所有分量的绝对值相加。

```
||x||_1 = |x_1| + |x_2| + ... + |x_n|
```

它被称为曼哈顿距离，因为它测量您在只能沿轴线移动的城市网格上行走的距离。没有对角线。

```
Point A = (1, 1)
Point B = (4, 5)

L1 distance = |4-1| + |5-1| = 3 + 4 = 7

On a grid, you walk 3 blocks east and 4 blocks north.
```

何时使用 L1：
- 高维稀疏数据（文本features，one-hot编码）
- 当您希望对异常值具有鲁棒性时（单个巨大差异并不占主导地位）
- Feature选择问题（L1正则化促进稀疏性）

与 L1 正则化（Lasso）的连接：添加 ||w||_1 到 loss function 会惩罚绝对 weight 值的总和。这会将小 weights 精确地推至零，执行自动 feature 选择。 L1惩罚在weight空间中创建菱形约束区域，并且菱形的角位于一些weights为零的轴上。

连接到 loss functions：平均绝对误差 (MAE) 是预测与目标之间的平均 L1 距离。它对所有错误进行线性惩罚，与 MSE 相比，它对异常值具有鲁棒性。

<a id="l2-norm-euclidean-distance"></a>

### L2 范数（欧几里得距离）

L2范数是直线距离。各分量平方和的平方根。

```
||x||_2 = sqrt(x_1^2 + x_2^2 + ... + x_n^2)
```

这是您在几何课上学到的距离。 n 维毕达哥拉斯。

```
Point A = (1, 1)
Point B = (4, 5)

L2 distance = sqrt((4-1)^2 + (5-1)^2) = sqrt(9 + 16) = sqrt(25) = 5.0

The straight line, cutting diagonally through the grid.
```

何时使用 L2：
- 中低维连续数据
- 当feature秤具有可比性时
- 物理距离（空间数据、传感器读数）
- 像素级图像相似度

与 L2 正则化 (Ridge) 的连接：添加 ||w||_2^2 对你的 loss function 惩罚大 weights。与 L1 不同，它不会将 weights 推为零。它将所有 weights 按比例缩小到零。 L2 惩罚创建圆形约束区域，因此轴上没有角。 Weights 变小，但很少恰好为零。

连接到 loss functions：均方误差 (MSE) 是 L2 距离平方的平均值。平方对大错误的惩罚比小错误更严重。

```
MAE (L1 loss):  |y - y_hat|         Linear penalty. Robust to outliers.
MSE (L2 loss):  (y - y_hat)^2       Quadratic penalty. Sensitive to outliers.
```

<a id="lp-norms-the-general-family"></a>

### Lp 规范：一般家庭

L1 和 L2 是 Lp 范数的特例：

```
||x||_p = (|x_1|^p + |x_2|^p + ... + |x_n|^p)^(1/p)
```

不同的 p 值会产生不同形状的“单位球”（距原点距离为 1 的所有点的集合）：

```
p=1:    Diamond shape      (corners on axes)
p=2:    Circle/sphere      (the usual round ball)
p=3:    Superellipse       (rounded square)
p=inf:  Square/hypercube   (flat sides along axes)
```

<a id="l-infinity-norm-chebyshev-distance"></a>

### L-无穷范数（切比雪夫距离）

当 p 接近无穷大时，Lp 范数收敛到最大绝对分量。

```
||x||_inf = max(|x_1|, |x_2|, ..., |x_n|)
```

两点之间的距离由它们差异最大的单一维度决定。所有其他维度都将被忽略。

```
Point A = (1, 1)
Point B = (4, 5)

L-inf distance = max(|4-1|, |5-1|) = max(3, 4) = 4
```

何时使用 L-无穷大：
- 当任何单一维度的最坏情况偏差都很重要时
- 游戏板（国际象棋中的国王在 L-无穷大中移动：向任何方向迈出一步都会花费 1）
- 制造公差（每个尺寸必须在规格范围内）

<a id="cosine-similarity-and-cosine-distance"></a>

### Cosine Similarity 和余弦距离

Cosine similarity 测量两个向量之间的角度，忽略它们的大小。

```
cos_sim(a, b) = (a . b) / (||a||_2 * ||b||_2)
```

它的范围从-1（相反方向）到+1（相同方向）。垂直向量有 cosine similarity 0。

余弦距离将其转换为距离：cosine_distance = 1 - cosine_相似度。范围从 0（相同方向）到 2（相反方向）。

```
a = (1, 0)    b = (1, 1)

cos_sim = (1*1 + 0*1) / (1 * sqrt(2)) = 1/sqrt(2) = 0.707
cos_dist = 1 - 0.707 = 0.293
```

为什么余弦主导 NLP 和 embeddings：在文本中，文档长度不应该影响相似性。一篇关于猫的文档的长度是另一篇关于猫的文档的两倍，仍然应该是“相似的”。 Cosine similarity 忽略大小（长度），只关心方向。单词分布相同但长度不同的两个文档指向同一方向，得到 cosine similarity 1.0。

何时使用cosine similarity：
- 文本相似度（TF-IDF向量，单词embeddings，句子embeddings）
- 大小为噪声、方向为信号的任何域
- 推荐系统（用户偏好向量）
- Embedding 搜索（vector databases 几乎总是使用余弦或点积）

<a id="dot-product-similarity-vs-cosine-similarity"></a>

### 点积相似度与 Cosine Similarity

两个向量的点积为：

```
a . b = a_1*b_1 + a_2*b_2 + ... + a_n*b_n
      = ||a|| * ||b|| * cos(angle)
```

Cosine similarity 是按两个量级归一化的点积。当两个向量已经单位归一化（幅度 = 1）时，点积和 cosine similarity 相同。

```
If ||a|| = 1 and ||b|| = 1:
    a . b = cos(angle between a and b)
```

当它们不同时：点积包含幅度信息。幅度较大的向量获得较高的点积得分。这在某些您希望“流行”项目排名更高的检索系统中很重要。幅度充当隐含的质量或重要性信号。

```
a = (3, 0)    b = (1, 0)    c = (0, 1)

dot(a, b) = 3     dot(a, c) = 0
cos(a, b) = 1.0   cos(a, c) = 0.0

Both agree on direction, but dot product also reflects magnitude.
```

在实践中：
- 当您想要纯粹的方向相似性时，请使用 cosine similarity
- 当幅度携带有意义的信息时使用点积
- 许多vector databases（Pinecone、Weaviate、Qdrant）让您在它们之间进行选择
- 如果你的embeddings是L2标准化的，那么选择并不重要

<a id="mahalanobis-distance"></a>

### 马哈拉诺比斯距离

欧几里得距离平等对待所有维度。但如果您的 features 相关或具有不同的尺度，L2 会给出误导性的结果。

马哈拉诺比斯距离说明了数据的协方差结构。

```
d_M(x, y) = sqrt((x - y)^T * S^(-1) * (x - y))
```

其中 S 是数据的协方差矩阵。

直观地说：马哈拉诺比斯距离首先对数据进行去相关和归一化（白化），然后计算该变换空间中的 L2 距离。如果 S 是单位矩阵（不相关，单位方差 features），则马哈拉诺比斯距离减少为欧几里德距离。

```
Example: height and weight are correlated.
Someone 6'2" and 180 lbs is not unusual.
Someone 5'0" and 180 lbs is unusual.

Euclidean distance might say they are equally far from the mean.
Mahalanobis distance correctly identifies the second as an outlier
because it accounts for the height-weight correlation.
```

何时使用马氏距离：
- 异常值检测（与均值马哈拉诺比斯距离较大的点为异常值）
- features 具有不同尺度和相关性时的分类
- 当您有足够的数据来估计可靠的协方差矩阵时
- 制造质量控制（多变量过程监控）

<a id="jaccard-similarity-for-sets"></a>

### 杰卡德相似度（对于集合）

杰卡德相似性度量两个集合之间的重叠。

```
J(A, B) = |A intersect B| / |A union B|
```

它的范围从 0（无重叠）到 1（相同的集合）。杰卡德距离 = 1 - 杰卡德相似度。

```
A = {cat, dog, fish}
B = {cat, bird, fish, snake}

Intersection = {cat, fish}         size = 2
Union = {cat, dog, fish, bird, snake}  size = 5

Jaccard similarity = 2/5 = 0.4
Jaccard distance = 0.6
```

何时使用杰卡德：
- 比较标签、类别或 features 的集合
- 基于单词存在（而非频率）的文档相似度
- 近似重复检测（Jaccard 的 MinHash 近似）
- 比较二进制 feature 向量（存在/不存在数据）
- 评估分割模型（Intersection over Union = Jaccard）

<a id="edit-distance-levenshtein-distance"></a>

### 编辑距离（编辑距离）

编辑距离计算将一个字符串转换为另一个字符串所需的单字符操作的最少次数。这些操作是：插入、删除或替换。

```
"kitten" -> "sitting"

kitten -> sitten  (substitute k -> s)
sitten -> sittin  (substitute e -> i)
sittin -> sitting (insert g)

Edit distance = 3
```

使用动态规划计算。填充一个矩阵，其中条目 (i, j) 是字符串 A 的前 i 个字符与字符串 B 的前 j 个字符之间的编辑距离。

```
        ""  s  i  t  t  i  n  g
    ""   0  1  2  3  4  5  6  7
    k    1  1  2  3  4  5  6  7
    i    2  2  1  2  3  4  5  6
    t    3  3  2  1  2  3  4  5
    t    4  4  3  2  1  2  3  4
    e    5  5  4  3  2  2  3  4
    n    6  6  5  4  3  3  2  3
```

何时使用编辑距离：
- 拼写检查和更正
- DNA序列alignment（带加权运算）
- 模糊字符串匹配
- 杂乱文本数据去重

<a id="kl-divergence-not-a-distance-but-used-like-one"></a>

### KL 散度（不是距离，但像距离一样使用）

KL 散度衡量一种概率分布与另一种概率分布的差异。在第 09 课中介绍过，但它属于本次讨论，因为人们将它用作“距离”，尽管它不是一个。

```
D_KL(P || Q) = sum(p(x) * log(p(x) / q(x)))
```

关键属性：KL 散度不对称。

```
D_KL(P || Q) != D_KL(Q || P)
```

这意味着它不符合距离度量的基本要求。它也不满足三角不等式。这是一种分歧，而不是距离。

转发KL (D_KL(P || Q)) 是“均值寻求”：Q 尝试覆盖 P 的所有模式。
反向KL (D_KL(Q || P)) 是“模态搜索”：Q 关注 P 的单个模态。

当你看到 KL 散度时：
- VAEs（ELBO 中的 KL 项将潜在分布推向先验）
- Knowledge distillation（学生尝试匹配老师的分布）
- RLHF（KL惩罚使微调模型保持接近基础模型）
- Policy gradient方法（约束策略更新）

<a id="wasserstein-distance-earth-movers-distance"></a>

### Wasserstein 距离（推土机距离）

Wasserstein 距离衡量将一种概率分布转换为另一种概率分布所需的最小“工作”。可以将其想象为：如果一个分布是一堆泥土，另一个分布是一个洞，那么您需要移动多少泥土以及多远？

```
W(P, Q) = inf over all transport plans gamma of E[d(x, y)]
```

对于一维分布，它简化为累积分布函数的绝对差的积分：

```
W_1(P, Q) = integral |CDF_P(x) - CDF_Q(x)| dx
```

瓦瑟斯坦为何重要：
- 它是一个真实的度量（对称，满足三角不等式）
- 即使分布不重叠（KL 散度趋于无穷大），它也会提供 gradients
- 这一特性使其成为 Wasserstein GANs (WGAN) 的核心，解决了原始 GANs 的训练不稳定问题

```
Distributions with no overlap:

P: [1, 0, 0, 0, 0]    Q: [0, 0, 0, 0, 1]

KL divergence: infinity (log of zero)
Wasserstein: 4 (move all mass 4 bins)

Wasserstein gives a meaningful gradient. KL does not.
```

何时使用 Wasserstein：
- GAN训练（WGAN、WGAN-GP）
- 比较可能不重叠的分布
- 最优运输问题
- 图像检索（比较颜色直方图）

<a id="why-different-tasks-need-different-distances"></a>

### 为什么不同的任务需要不同的距离

| 任务 | 最佳距离 | 为什么 |
|------|--------------|-----|
| 文本相似度 | 余弦 | 幅度是噪音，方向是意义 |
| 图像像素比较 | L2 | 空间关系很重要，features 具有可比尺度 |
| 稀疏高调光 features | L1 | 稳健，不会放大罕见的大差异 |
| 设置重叠（标签、类别） | 杰卡德 | 数据本质上是集值的，而不是向量的 |
| 字符串匹配 | 编辑距离 | 操作映射到人类编辑直觉 |
| 异常值检测 | 马哈拉诺比斯 | feature 相关性和尺度的账户 |
| 比较分布 | KL散度 | 使用 Q 代替 P 来测量丢失的信息 |
| GAN培训 | 瓦瑟斯坦 | 即使分布不重叠，也提供 gradients |
| Embeddings（矢量数据库） | 余弦或点积 | Embeddings 被训练以编码方向含义 |
| 推荐 | 点积 | 程度可以编码受欢迎程度或信心 |
| DNA序列 | 加权编辑距离 | 替代成本因核苷酸对而异 |
| 制造质量控制 | L-无穷大 | 任何维度的最坏情况偏差都很重要 |

<a id="connection-to-loss-functions"></a>

### 连接到 Loss Functions

Loss functions 是应用于预测与目标的距离函数。

```
Loss function       Distance it uses       Behavior
MSE                 L2 squared             Penalizes large errors heavily
MAE                 L1                     Penalizes all errors equally
Huber loss          L1 for large errors,   Best of both: robust to outliers,
                    L2 for small errors    smooth gradient near zero
Cross-entropy       KL divergence          Measures distribution mismatch
Hinge loss          max(0, margin - d)     Only penalizes below margin
Triplet loss        L2 (typically)         Pulls positives close, pushes
                                           negatives away
Contrastive loss    L2                     Similar pairs close, dissimilar
                                           pairs beyond margin
```

<a id="connection-to-regularization"></a>

### 与正则化的联系

正则化将 weights 上的范数惩罚添加到 loss function 上。

```
L1 regularization (Lasso):   loss + lambda * ||w||_1
  -> Sparse weights. Some weights become exactly zero.
  -> Automatic feature selection.
  -> Solution has corners (non-differentiable at zero).

L2 regularization (Ridge):   loss + lambda * ||w||_2^2
  -> Small weights. All weights shrink toward zero.
  -> No feature selection (nothing goes to exactly zero).
  -> Smooth solution everywhere.

Elastic Net:                  loss + lambda_1 * ||w||_1 + lambda_2 * ||w||_2^2
  -> Combines sparsity of L1 with stability of L2.
  -> Groups of correlated features are kept or dropped together.
```

为什么 L1 产生稀疏性而 L2 不产生稀疏性：描绘 2D weight 空间中的约束区域。 L1是菱形，L2是圆形。 loss function 的轮廓（椭圆）最有可能在角处接触菱形，其中 weight 为零。它们在平滑点处接触圆，其中 weights 均非零。

<a id="nearest-neighbor-search"></a>

### 最近邻搜索

每个距离函数都意味着一个最近邻搜索问题：给定一个查询点，找到数据集中最近的点。

在 d 维 n 个点的数据集中，每个查询的精确最近邻搜索为 O(n * d)。对于大型数据集，这太慢了。

Approximate Nearest Neighbor (ANN) 算法以少量的精度换取巨大的速度增益：

```
Algorithm         Approach                      Used by
KD-trees          Axis-aligned space partition   scikit-learn (low-dim)
Ball trees        Nested hyperspheres            scikit-learn (medium-dim)
LSH               Random hash projections        Near-duplicate detection
HNSW              Hierarchical navigable         FAISS, Qdrant, Weaviate
                  small-world graph
IVF               Inverted file index with       FAISS (billion-scale)
                  cluster-based search
Product quant.    Compress vectors, search       FAISS (memory-constrained)
                  in compressed space
```

HNSW（Hierarchical Navigable Small World）是现代vector databases中的主导算法。它构建了一个多层图，其中每个节点都连接到其 approximate nearest neighbors。搜索从顶层（稀疏、长跳）开始，下降到底层（密集、短跳）。

```figure
norm-unit-balls
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-all-norm-and-distance-functions"></a>

### 步骤 1：所有范数和距离函数

完整实现请参见 `code/distances.py`。每个函数都是仅使用基本的 Python 数学从头开始构建的。

<a id="step-2-same-data-different-distances-different-neighbors"></a>

### 步骤 2：相同的数据，不同的距离，不同的邻居

`distances.py` 中的演示创建一个数据集，选择一个查询点，并显示最近邻居如何根据距离度量而变化。 L1 下“最接近”的点可能不是 L2 或余弦下最接近的点。

<a id="step-3-embedding-similarity-search"></a>

### 步骤3：Embedding相似度搜索

该代码包括模拟 embedding 相似性搜索，该搜索使用 cosine similarity 与 L2 距离查找与查询最相似的“文档”，显示排名可能不同。

<a id="use-it"></a>

## 实际应用

最常见的实际用途：在 vector database 中查找相似的项目。

```python
import numpy as np

def cosine_similarity_matrix(X):
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    X_normalized = X / norms
    return X_normalized @ X_normalized.T

embeddings = np.random.randn(1000, 768)

sim_matrix = cosine_similarity_matrix(embeddings)

query_idx = 0
similarities = sim_matrix[query_idx]
top_k = np.argsort(similarities)[::-1][1:6]
print(f"Top 5 most similar to item 0: {top_k}")
print(f"Similarities: {similarities[top_k]}")
```

当您调用 `model.encode(text)` 然后搜索 vector database 时，这就是幕后发生的情况。 embedding 模型将文本映射到向量。 vector database 计算查询向量和每个存储向量之间的 cosine similarity（或点积），使用 ANN 算法来避免检查所有向量。

<a id="exercises"></a>

## 练习

1. 计算 (1, 2, 3) 和 (4, 0, 6) 之间的 L1、L2 和 L 无穷远距离。验证 L-inf <= L2 <= L1 对于任何点对始终成立。证明为什么这个顺序是有保证的。

2. 创建两个向量，其中 cosine similarity 较高 (> 0.9)，但 L2 距离较大 (> 10)。从几何角度解释正在发生的事情。然后创建两个向量，其中 cosine similarity 较低 (< 0.3)，但 L2 距离较小 (< 0.5)。

3. 实现一个函数，该函数接受数据集和查询点，并返回 L1、L2、余弦和马哈拉诺比斯距离下的最近邻。找到一个数据集，其中所有四个点对于最近的点都不一致。

4. 使用 CDF 方法手动计算 [0.5, 0.5, 0, 0] 和 [0, 0, 0.5, 0.5] 之间的 Wasserstein 距离。然后在 [0.25, 0.25, 0.25, 0.25] 和 [0, 0, 0.5, 0.5] 之间进行计算。哪个更大，为什么？

5. 实现 MinHash 以获得近似的 Jaccard 相似度。生成 100 个随机集，计算所有对的精确 Jaccard，并使用 50、100 和 200 个哈希函数与 MinHash 近似值进行比较。绘制近似误差。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| 规范 | “向量的大小” | 将向量映射到非负标量的函数，满足三角不等式、绝对同质性以及仅零向量为零 |
| L1范数 | 《曼哈顿的距离》 | 绝对分量值的总和。在优化中产生稀疏性。对异常值具有鲁棒性 |
| L2范数 | “欧几里得距离” | 分量平方和的平方根。欧氏空间中的直线距离 |
| Lp范数 | “普遍规范” | 绝对分量的 p 次方之和的 p 次方根。 L1和L2是特殊情况 |
| L-无穷范数 | “最大范数”或“切比雪夫距离” | 最大绝对分量值。当 p 接近无穷大时 Lp 的极限 |
| Cosine similarity | “向量之间的角度” | 按两个量值归一化的点积。范围从 -1 到 +1。忽略向量长度 |
| 余弦距离 | “1减去cosine similarity” | 将 cosine similarity 转换为距离。范围从 0 到 2 |
| 点积 | “非标准化余弦” | 各分量乘积的总和。等于 cosine similarity 乘以两个量级 |
| 马哈拉诺比斯距离 | “相关性感知距离” | 使用数据协方差矩阵白化（去相关和归一化）的空间中的 L2 距离 |
| 杰卡德相似度 | “设置重叠” | 交集的大小除以并集的大小。对于集合，而不是向量 |
| 编辑距离 | “编辑距离” | 将一个字符串转换为另一个字符串的最少插入、删除和替换操作 |
| KL散度 | “分布之间的距离” | 不是真实距离（不对称）。测量使用 Q 编码 P 产生的额外比特 |
| 瓦瑟斯坦距离 | “推土机距离” | 将质量从一个分布输送到另一个分布的最小工作量。一个真实的指标 |
| Approximate nearest neighbor | “ANN搜索” | 比精确搜索更快地找到近似最近点的算法（HNSW、LSH、IVF） |
| HNSW | 《向量DB算法》 | 分层可导航小世界图。用于快速搜索的多层图 approximate nearest neighbor |
| L1 正则化 | “套索” | 将 weights 的 L1 范数添加到损失中。将 weights 驱动至零（稀疏性） |
| L2正则化 | “山脊”或“weight decay” | 将 weights 的 L2 范数平方添加到损失中。将 weights 缩小到零而不稀疏 |
| 弹性网 | "L1 + L2" | 结合了 L1 和 L2 正则化。处理相关的 feature 组比单独处理任何一个组都要好 |

<a id="further-reading"></a>

## 进一步阅读

- [FAISS：用于高效相似性搜索的库](https://github.com/facebookresearch/faiss) - 用于十亿级 ANN 搜索的 Meta 库
- [Wasserstein GAN (Arjovsky et al., 2017)](https://arxiv.org/abs/1701.07875) - 介绍 Earth Mover 与 GANs 距离的论文
- [局部敏感哈希（Indyk & Motwani，1998）](https://dl.acm.org/doi/10.1145/276698.276876) - 基础 ANN 算法
- [E 词表示的高效估计 (Mikolov et al., 2013)](https://arxiv.org/abs/1301.3781) - Word2Vec，其中 cosine similarity 成为默认值embeddings
- [sklearn.neighbors 文档](https://scikit-learn.org/stable/modules/neighbors.html) - scikit-learn 中距离度量和邻居算法的实用指南
