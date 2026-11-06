# 代码讲解 · distances.py

> **所属小节**：阶段 01 · 数学基础 · 第 14 节 范数与距离 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 distances.py`（无命令行参数，依次运行 13 个演示） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy

---

## 1. 这份代码在考察什么

这是一份约 700 行的"距离函数百科全书"：所有函数都只用基础的 Python 数学从零实现，然后用 13 个 `demo_*` 函数逐一演示。它想让你搞清楚：

1. **范数 = 距离的底座**：`l1/l2/lp/linf_distance` 本质上都是"差向量的范数"，以及 `L∞ ≤ L2 ≤ L1` 这个恒成立的排序。
2. **方向 vs 大小**：余弦只看方向，点积还掺杂了模长，L2 归一化后两者合一——这是 embedding 检索的基础。
3. **数据结构决定距离**：向量用 Lp/余弦，相关特征用马氏距离，集合用 Jaccard，字符串用编辑距离，概率分布用 KL / Wasserstein。
4. **"最近"取决于度量**：同一份数据、同一个查询，换一个距离，近邻排序就可能改变。
5. **距离与优化的联系**：L1/L2 范数作为正则项时，分别对应"稀疏"和"收缩"。

> 一句话：**你的距离函数定义了"相似"的含义**——这份代码让你亲手把每一种"相似"都算一遍。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `l1_norm` / `l2_norm` / `lp_norm` / `linf_norm` | 函数 | 计算向量的各种范数 | Lp 范数族 |
| `l1/l2/lp/linf_distance` | 函数 | 差向量的范数 | 曼哈顿 / 欧氏 / 切比雪夫距离 |
| `dot_product` / `cosine_similarity` / `cosine_distance` | 函数 | 点积与余弦 | 方向相似度 |
| `mahalanobis_distance` + `invert_matrix` + `compute_covariance` | 函数 | 协方差感知的距离、矩阵求逆、样本协方差 | 白化、马氏距离 |
| `jaccard_similarity` / `jaccard_distance` | 函数 | 集合重叠度 | Jaccard / IoU |
| `edit_distance` | 函数 | 动态规划求 Levenshtein 距离 | 字符串距离 |
| `kl_divergence` / `wasserstein_1d` | 函数 | 分布之间的差异 | 散度 vs 真度量 |
| `normalize_vector` / `find_nearest_neighbor` / `find_k_nearest` | 工具函数 | 归一化、暴力最近邻检索 | KNN、精确检索 |
| `demo_*`（13 个） | 演示函数 | 打印各种对比实验 | — |
| `if __name__ == "__main__":` | 入口 | 依次调用 13 个 demo | — |

数据流很直接：底层"距离原语"互相调用（`cosine_similarity` → `dot_product` + `l2_norm`；`lp_distance` → `lp_norm`；`mahalanobis_distance` → `invert_matrix`），`demo_*` 只调用这些原语并格式化输出，彼此之间没有依赖。

---

## 3. 逐段精讲

> 文件较大，下面聚焦最核心的约 60%：距离原语全部讲，demo 只挑能说明问题的几个。

### 3.1 范数族：一个公式统一 L1、L2、L∞

```python
def l1_norm(x):
    return sum(abs(xi) for xi in x)


def l2_norm(x):
    return math.sqrt(sum(xi ** 2 for xi in x))


def lp_norm(x, p):
    if p == float('inf'):
        return max(abs(xi) for xi in x)
    return sum(abs(xi) ** p for xi in x) ** (1 / p)
```

- `lp_norm` 就是讲义公式 `‖x‖p = (Σ|xᵢ|ᵖ)^(1/p)` 的直译。p→∞ 时极限是"最大分量"，但 `x ** (1/inf)` 没法直接算，所以单独开一个分支返回 `max`——**数学上的极限在代码里要显式处理**。
- `l2_norm` 里写 `xi ** 2` 而没写 `abs(xi) ** 2`：平方本身就非负，省掉一次 `abs`。
- 对应的距离函数都是"先求差，再求范数"：

```python
def lp_distance(a, b, p):
    diff = [ai - bi for ai, bi in zip(a, b)]
    return lp_norm(diff, p)
```

`l1_distance`、`l2_distance`、`linf_distance` 则把"求差"和"求范数"写在一个生成器表达式里，不创建中间列表。

- **排序 `L∞ ≤ L2 ≤ L1` 为什么恒成立**：设最大分量为 m，则 `m² ≤ Σxᵢ²`，所以 L∞ ≤ L2；又 `(Σ|xᵢ|)² = Σxᵢ² + 交叉项（都 ≥ 0）≥ Σxᵢ²`，所以 L2 ≤ L1。`demo_norm_ordering` 用 5 组随机向量验证了这一点。
- ⚠️ 所有函数都依赖 `zip`，**维度不同时会静默截断**：`l2_distance([1,2,3],[1,2])` 返回 `0.0` 而不是报错。

### 3.2 点积与余弦：零向量的"约定"

```python
def cosine_similarity(a, b):
    dot = dot_product(a, b)
    norm_a = l2_norm(a)
    norm_b = l2_norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def cosine_distance(a, b):
    return 1.0 - cosine_similarity(a, b)
```

- 与第 01 节的 `Vector.cosine_similarity` 相比，这里多了一个**零向量保护**：模长为 0 时返回 `0.0` 而不是崩溃。这是工程上常见的约定（sklearn 等库也类似处理），但要清楚它的代价：`cosine_distance([0,0],[0,0]) = 1.0`——一个向量和它自己的距离不是 0。
- 余弦距离的范围是 `[0, 2]`：同向 0，正交 1，反向 2。
- ⚠️ 余弦距离不满足三角不等式，严格说不是"度量"，所以不能直接套用依赖三角不等式剪枝的数据结构（如 ball tree）；常见做法是先 L2 归一化，再用 L2 距离（`‖a−b‖² = 2 − 2cos`）。

```python
def normalize_vector(v):
    norm = l2_norm(v)
    if norm == 0:
        return v[:]
    return [vi / norm for vi in v]
```

`normalize_vector` 同样对零向量"原样返回一份拷贝"（`v[:]`），而不是除以 0。`demo_cosine_vs_dot` 用它证明：归一化之后，余弦和点积完全相同。

### 3.3 马氏距离：协方差 + 求逆 + 二次型

先看样本协方差：

```python
def compute_covariance(data):
    n = len(data)
    d = len(data[0])
    means = [sum(data[i][j] for i in range(n)) / n for j in range(d)]
    centered = [[data[i][j] - means[j] for j in range(d)] for i in range(n)]
    cov = [[0.0] * d for _ in range(d)]
    for i in range(d):
        for j in range(d):
            cov[i][j] = sum(centered[k][i] * centered[k][j] for k in range(n)) / (n - 1)
    return cov
```

- 三步走：求每一列均值 → 中心化 → `cov[i][j] = Σₖ (xₖᵢ − μᵢ)(xₖⱼ − μⱼ) / (n − 1)`。
- 除以 `n − 1` 而不是 `n`，是**贝塞尔校正**（无偏估计，下一节"机器学习统计"会细讲）。
- 复杂度 O(n·d²)，生产中就是 `np.cov(data, rowvar=False)`。

再看求逆——**带部分主元的高斯-约当消元**：

```python
def invert_matrix(matrix):
    n = len(matrix)
    augmented = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]

    for col in range(n):
        max_row = col
        for row in range(col + 1, n):
            if abs(augmented[row][col]) > abs(augmented[max_row][col]):
                max_row = row
        augmented[col], augmented[max_row] = augmented[max_row], augmented[col]

        pivot = augmented[col][col]
        if abs(pivot) < 1e-12:
            raise ValueError("Matrix is singular or near-singular")
        # ... 主元行除以 pivot，再消去其他所有行的这一列
    return [row[n:] for row in augmented]
```

- 思路：把 `[A | I]` 通过行变换变成 `[I | A⁻¹]`，最后取右半边 `row[n:]`。
- **部分主元法**：每一列选绝对值最大的元素作主元。第 01 节的 `is_independent` 只是"找第一个非零元素"，这里升级为数值上更稳定的做法——主元越大，除法放大的舍入误差越小。
- 主元小于 `1e-12` 时抛出 `ValueError`：对应"特征完全共线 → 协方差奇异 → 马氏距离无定义"。

最后是距离本身：

```python
def mahalanobis_distance(x, y, cov_matrix):
    n = len(x)
    diff = [xi - yi for xi, yi in zip(x, y)]

    inv_cov = invert_matrix(cov_matrix)

    temp = [0.0] * n
    for i in range(n):
        for j in range(n):
            temp[i] += diff[j] * inv_cov[j][i]

    result = sum(temp[i] * diff[i] for i in range(n))
    return math.sqrt(max(0, result))
```

- `temp` 是行向量 `diffᵀ · S⁻¹`，再和 `diff` 点积得到二次型 `diffᵀ S⁻¹ diff`。
- `max(0, result)`：理论上二次型非负，但浮点误差可能给出 `-1e-17`，`math.sqrt` 会抛 `ValueError`，这里夹到 0 防御。
- ⚠️ **每次调用都重新求逆**，O(d³)。单次演示无所谓，但如果拿它去 `find_k_nearest` 扫描 n 个点，就是 O(n·d³) 的浪费。正确做法是预先求一次逆（或 Cholesky 分解后把数据白化），见测验 Q11。

### 3.4 Jaccard：集合运算一行搞定

```python
def jaccard_similarity(set_a, set_b):
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union
```

- Python 的 `set` 原生支持 `&`（交集）和 `|`（并集），代码几乎就是公式本身。
- 两个空集的并集为空，`0/0` 无定义，这里约定"两个空集完全相同"返回 1.0——同样是一个需要写进文档的**边界约定**。
- 这正是图像分割里的 IoU（Intersection over Union）；大规模近似计算用 MinHash（讲义练习 5）。

### 3.5 编辑距离：经典二维 DP

```python
def edit_distance(s1, s2):
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],
                    dp[i][j - 1],
                    dp[i - 1][j - 1]
                )

    return dp[m][n]
```

- **状态**：`dp[i][j]` = `s1` 前 i 个字符变成 `s2` 前 j 个字符的最少操作数。
- **边界**：`dp[i][0] = i`（删光 i 个字符）、`dp[0][j] = j`（插入 j 个字符）。
- **转移**：字符相同直接继承左上角；不同则取三种操作的最小值 + 1：`dp[i-1][j]`（删除）、`dp[i][j-1]`（插入）、`dp[i-1][j-1]`（替换）。
- 下标 `s1[i - 1]` 的"错一位"是因为 dp 表多了一行一列空串，第 i 行对应第 i 个字符（下标 i−1）。
- 复杂度 O(mn) 时间、O(mn) 空间；因为每行只依赖上一行，空间可以压到 O(min(m,n))（测验 Q12）。
- 用 `[[0] * (n + 1) for _ in range(m + 1)]` 而不是 `[[0] * (n + 1)] * (m + 1)`：后者的每一行是**同一个列表对象**，改一行全变（见"常见坑"）。

### 3.6 KL 散度与一维 Wasserstein

```python
def kl_divergence(p, q):
    total = 0.0
    for pi, qi in zip(p, q):
        if pi > 0:
            if qi <= 0:
                return float('inf')
            total += pi * math.log(pi / qi)
    return total
```

- 两个边界都处理对了：`pᵢ = 0` 的项按约定 `0·log0 = 0` 跳过；`pᵢ > 0` 而 `qᵢ = 0` 时 KL 为无穷大，直接返回 `inf`。
- 用 `math.log`（自然对数），单位是 **nats**；换成 `math.log2` 就是 bits。

```python
def wasserstein_1d(p, q):
    assert len(p) == len(q), "Distributions must have the same number of bins"
    n = len(p)
    cdf_p = [0.0] * n
    cdf_q = [0.0] * n

    cdf_p[0] = p[0]
    cdf_q[0] = q[0]
    for i in range(1, n):
        cdf_p[i] = cdf_p[i - 1] + p[i]
        cdf_q[i] = cdf_q[i - 1] + q[i]

    return sum(abs(cdf_p[i] - cdf_q[i]) for i in range(n))
```

- 讲义公式 `W₁ = ∫|CDF_P − CDF_Q| dx` 的离散版：先求前缀和（累计分布），再把差的绝对值加起来。
- ⚠️ 隐含假设：**相邻箱间距为 1**、两个分布都已归一化。若箱宽为 Δ，结果要乘以 Δ。
- 这里用 `assert` 检查箱数相同（和其他函数依赖 `zip` 静默截断不同）。注意 `python -O` 运行时 `assert` 会被移除，生产代码应改用 `raise ValueError`。

### 3.7 暴力最近邻：`**kwargs` 透传参数

```python
def find_k_nearest(query, dataset, distance_fn, k=5, **kwargs):
    distances = []
    for i, point in enumerate(dataset):
        d = distance_fn(query, point, **kwargs)
        distances.append((i, d))
    distances.sort(key=lambda x: x[1])
    return distances[:k]
```

- 距离函数作为参数传入（**函数是一等公民**），同一个检索函数可以搭配任何度量。
- `**kwargs` 把额外参数原样转发给距离函数，例如 `find_k_nearest(q, data, mahalanobis_distance, k=3, cov_matrix=cov)`。
- 复杂度 O(n·d + n log n)（算距离 + 全排序）。只取 top-k 时可用 `heapq.nsmallest(k, ...)` 降到 O(n log k)；规模再大就需要讲义里的 ANN（HNSW / IVF / PQ）。
- ⚠️ `find_nearest_neighbor` 和 `find_k_nearest` 在本文件的 demo 中**都没有被调用**，demo 里都是手写循环——它们是留给你练习用的工具函数。

### 3.8 关键演示：马氏距离

```python
    random.seed(42)
    n = 200
    data = []
    for _ in range(n):
        x = random.gauss(0, 3)
        y = 0.8 * x + random.gauss(0, 1)
        data.append([x, y])
    # ...
    point_along = [mean[0] + 3, mean[1] + 0.8 * 3]
    point_perp = [mean[0] + 1, mean[1] - 3]
```

- 构造 `y = 0.8x + 噪声` 的相关数据，然后放两个点：一个沿回归线方向偏离 `(3, 2.4)`，一个朝 `(1, −3)` 方向偏离。
- 结果（见第 6 节）：L2 认为前者更远（3.84 vs 3.16），马氏距离却给出相反结论（0.98 vs 3.86）——沿相关轴的偏离是"正常波动"，逆着相关方向的偏离才是异常。
- ⚠️ 打印文字写的是 `r ~ 0.8`，但 0.8 是**斜率**不是相关系数。理论相关系数 `r = 0.8·3 / √(0.64·9 + 1) ≈ 0.92`，用代码算出的协方差也得到 r ≈ 0.92。
- ⚠️ 变量名 `point_perp`（"垂直"）也不严格：`(1, −3)` 与 `(1, 0.8)` 的夹角约 110°，并非 90°。不影响结论，但读代码时要知道。

### 3.9 关键演示：同一数据、不同度量

`demo_different_neighbors` 生成 8 个 5 维点：P0–P2 来自标准正态，P3–P5 第 0 维被放大 5 倍，P6–P7 是均值为 3 的紧密簇。查询为 `[1.0, 0.5, -0.5, 1.0, 0.2]`。

- ⚠️ 在 `random.seed(123)` 下，四种度量的**第 1 近邻都是 P0**，所以代码里 `if not all_same:` 那段 "The metrics DISAGREE" 根本不会打印——演示标题承诺的"不同近邻"没有在 top-1 上兑现。
- 但**排序已经不同**：按余弦，第 2、3 近的是 P6（0.3778）、P7（0.4041）；按 L1/L2/L∞，P6、P7 却是**最远**的两个（L1 ≈ 12.9）。原因是 P6、P7 各分量都约为 3，方向与查询（分量大多为正）相近，但位置很远——余弦只看方向。这才是这个 demo 真正值得看的地方。

### 3.10 关键演示：正则化

```python
    w_l1 = weights[:]
    for step in range(50):
        for i in range(n_features):
            grad = lr * (1 if w_l1[i] > 0 else (-1 if w_l1[i] < 0 else 0))
            w_l1[i] -= grad
            if abs(w_l1[i]) < lr:
                w_l1[i] = 0.0

    w_l2 = weights[:]
    for step in range(50):
        for i in range(n_features):
            grad = lr * 2 * w_l2[i]
            w_l2[i] -= grad
```

- L1 部分：`sign(w)` 是 `|w|` 的（次）梯度，每步固定减 `lr`；`|w| < lr` 时直接置 0，防止在 0 附近来回震荡——这是一种简化版"软阈值"。
- L2 部分：`‖w‖²` 的梯度是 `2w`，每步 `w ← 0.8w`，是几何级数衰减，永远不会精确到 0。
- ⚠️ **只有正则项、没有数据项**，于是 L1 在 50 步里最多能减 5.0，把全部 10 个权重（包括 −2.995）都清零；L2 把权重缩到原来的 `0.8⁵⁰ ≈ 1.4×10⁻⁵`，打印出来也全是 `±0.0`。输出与结尾"L1 只把'小'权重清零"的说法并不一致。真正的对比需要加入数据拟合项，见测验 Q10。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python、列表表示向量 | 每个公式都能逐项看清 | 慢几个数量级；生产用 `np.linalg.norm`、`scipy.spatial.distance`、`sklearn.metrics.pairwise` |
| 距离 = 差向量的范数 | 体现"范数决定距离"的统一视角 | 无 |
| 零向量余弦返回 0、空集 Jaccard 返回 1 | 避免除零崩溃 | 破坏 `d(x,x)=0`；生产中应显式过滤零向量或记录告警 |
| 部分主元高斯-约当求逆 | 比"找第一个非零元"更稳定 | 生产中不显式求逆，用 Cholesky / `np.linalg.solve`；协方差病态时加 `εI` |
| 马氏距离内部每次求逆 | 函数自包含、接口简单 | O(d³)/次；应预先求逆或白化数据 |
| 编辑距离完整二维表 | 直观，便于打印/回溯路径 | O(mn) 空间；只要距离值时用两行滚动数组 |
| Wasserstein 只做一维、等间距 | 一维有 CDF 闭式解 | 高维需求解最优传输（线性规划、Sinkhorn）或 WGAN 式对偶估计 |
| `find_k_nearest` 全量排序 | 简单 | O(n log n)；用堆取 top-k，大规模用 ANN 索引 |
| 演示数据用固定随机种子 | 结果可复现 | 某些种子下演示效果不明显（见 3.9） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 生成器表达式 | `sum(abs(xi) for xi in x)` | 不建中间列表，直接喂给 `sum/max` |
| 列表推导式 | `[ai - bi for ai, bi in zip(a, b)]` | 一行生成新列表 |
| 嵌套列表推导 | `[[0] * (n + 1) for _ in range(m + 1)]` | 生成二维表；`_` 表示"用不到的循环变量" |
| `zip` | `zip(a, b)` | 按位置配对；长度不同时截断到较短者 |
| `enumerate` | `for i, point in enumerate(dataset)` | 同时拿下标和元素 |
| 切片拷贝 | `row[:]`、`weights[:]`、`row[n:]` | `[:]` 复制列表；`[n:]` 取第 n 个之后的部分 |
| 无穷大 | `float('inf')` | 用作"初始最小距离"或 KL 的无穷结果 |
| 集合运算 | `set_a & set_b`、`set_a \| set_b` | 交集、并集；`not set_a` 判断空集 |
| 条件表达式 | `1 if w_l1[i] > 0 else (-1 if w_l1[i] < 0 else 0)` | 一行写 if/else，可以嵌套（这里实现 sign 函数） |
| 链式比较 | `dinf <= d2 <= d1`、`l1_best == l2_best == cos_best == linf_best` | 等价于用 `and` 连接的多个比较 |
| `lambda` 与 `key=` | `distances.sort(key=lambda x: x[1])`、`sorted(..., key=lambda x: -x[1])` | 按元组第 2 个元素排序；取负号实现降序 |
| `min/max` 的 `key` | `min(dists, key=lambda x: x[1])`、`max(votes, key=votes.get)` | 返回"使 key 最小/最大"的元素；后者求票数最多的类别 |
| `dict.get` 计数 | `votes[label] = votes.get(label, 0) + 1` | 键不存在时用默认值 0 |
| `dict.items()` | `for metric_name, dists in results.items()` | 同时遍历键和值 |
| 元组解包 | `for d, label, point in neighbors`、`m, n = len(s1), len(s2)` | 一次给多个变量赋值 |
| 函数作参数 | `find_k_nearest(query, dataset, distance_fn, ...)` | 函数是一等公民，可以像变量一样传递 |
| `**kwargs` | `distance_fn(query, point, **kwargs)` | 收集并转发任意关键字参数 |
| `assert` | `assert len(p) == len(q), "..."` | 条件不满足时抛 `AssertionError`；`-O` 模式下会被跳过 |
| `raise` | `raise ValueError("Matrix is singular or near-singular")` | 主动抛出异常 |
| f-string 格式符 | `f"{name:<20s}"`、`f"{x:>8.3f}"`、`f"P{i:<6d}"`、`f"{'-' * 20}"` | `<` 左对齐、`>` 右对齐，数字是宽度，`.3f` 保留 3 位小数；`{}` 里可以放任意表达式 |
| `random` 模块 | `random.seed(42)`、`random.gauss(0, 3)`、`random.randint(2, 10)` | 固定种子、正态采样、闭区间随机整数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 demo，被 import 时不执行 |

---

## 6. 运行结果解读

已在临时目录实际运行（Python 3.13，约 1 秒）。关键输出：

```text
  Vector                     L1       L2       L3    L-inf
  (3, 4)                  7.000    5.000    4.498    4.000   ← 经典 3-4-5；p 越大越接近最大分量 4
  (5, 0, 0)               5.000    5.000    5.000    5.000   ← 只有一个非零分量时所有 Lp 相等
  (1, 2, 3, 4, 5)        15.000    7.416    6.082    5.000   ← 分量越"均匀"，各范数差距越大
```

```text
  Pair           Cosine        Dot
  A vs B         1.0000    28.0000    ← B = 2A，方向相同
  A vs C         0.4226     5.0000
  B vs C         0.4226    10.0000    ← 余弦相同，点积翻倍：点积掺入了模长
```

```text
  Covariance: [[9.39, 7.21], [7.21, 6.49]]   ← 接近理论值 [[9, 7.2], [7.2, 6.76]]
  Point along correlation axis:  L2 3.8419   Mahalanobis 0.9840
  Point perpendicular to axis:   L2 3.1623   Mahalanobis 3.8648   ← L2 与马氏距离的结论相反
```

```text
  'kitten' -> 'sitting':  distance = 3
  'sunday' -> 'saturday':  distance = 3
  'python' -> 'pytorch':  distance = 4
  KL(P || Q) = 0.3681 nats
  KL(Q || P) = 0.5108 nats              ← 不对称
  Shifted right by 1    Wasserstein: 1.0000    KL: inf
  Shifted right by 2    Wasserstein: 2.0000    KL: inf
  Opposite ends         Wasserstein: 3.0000    KL: inf   ← W 随"搬运距离"线性增长，KL 全是 inf
```

```text
  Point          L1       L2   Cosine    L-inf
  P0         1.823    1.020   0.0946    0.737   ← 四种度量的第 1 近邻都是 P0
  P5         2.925    1.439   0.5021    0.929
  P6        12.918    5.957   0.3778    3.610   ← 余弦排第 2，L 系列却排最后
  P7        12.551    5.806   0.4041    3.777
```

```text
  Rank   Cosine                              L2                                  Dot Product
  1      machine learning algorith (0.984)   machine learning algorith (2.3)     machine learning algorith (152.3)
  2      deep neural networks      (0.532)   deep neural networks      (11.9)    deep neural networks      (79.3)
  3      reinforcement learning ag (0.414)   reinforcement learning ag (12.2)    natural language processi (54.1)
  4      natural language processi (0.388)   natural language processi (13.2)    reinforcement learning ag (48.9)
  5      database query optimizati (0.091)   computer vision models    (15.1)    database query optimizati (11.3)
  6      computer vision models    (0.058)   database query optimizati (15.3)    computer vision models    (6.6)
```

（文档名被 `[:25]` 截断到 25 个字符，所以是 `algorith`、`processi`。）

前两名（加噪的查询原文、同样加了额外信号的 "deep neural networks"）三种方法一致，第 3–6 名开始分歧：点积受模长影响把 NLP 排到第 3；余弦把 "computer vision" 排在 "database" 之后，L2 则相反——合成 embedding 中 64 维随机噪声相对 10 维 +2 的"主题信号"并不小，排序对度量很敏感。

KNN 演示中四种度量都预测为 `C`（三个最近邻都是 C 类），与标题"distance metric changes the prediction"不符；正则化演示的问题见 3.10。

---

## 7. 动手改一改

1. 在 `l1_distance` 等函数开头加维度检查（或改用 `zip(a, b, strict=True)`），验证 `l2_distance([1,2,3],[1,2])` 会报错。
2. 改 `demo_different_neighbors` 的种子或数据（如把 P6/P7 放到查询方向的远处、放大某一维），找到一组让四种度量的第 1 近邻**互不相同**的数据（讲义练习 3）。
3. 把 `demo_knn_classification` 的查询点改成 `[3.1, 1.7]`：L1/L2/L∞ 仍预测 `C`，余弦却预测 `B`（已验证）。解释原因（提示：余弦只看方向，`[3.1, 1.7]` 的方向更接近 B 类点所在的射线）。再找一个让余弦预测 `A` 的查询。注意这个网格数据集中很多点到查询的距离相等，排序靠 `sort` 的稳定性决定先后，挑查询时要避开平局。
4. 写 `make_mahalanobis(cov)`，只求一次逆，配合 `find_k_nearest` 使用；再加上 `S + εI` 的正则化参数，测试共线数据 `[[1,2],[2,4],[3,6]]`。
5. 实现 MinHash：对 100 个随机集合分别用 50、100、200 个哈希函数估计 Jaccard，统计与精确值的平均绝对误差（讲义练习 5）。
6. 用 NumPy 重写 `cosine_similarity_matrix`（讲义 Use It 部分），对 1000×768 随机矩阵与纯 Python 版比较耗时。

---

## 8. 常见坑

- **`zip` 静默截断**：维度不一致的向量算距离不报错，结果却是错的。
- **零向量约定**：本代码的余弦对零向量返回 0，导致零向量与自身的余弦距离为 1；不同库的约定不同（有的返回 NaN），混用时排查困难。
- **二维表的错误初始化**：`[[0] * (n+1)] * (m+1)` 让所有行共享同一个列表，`dp[1][0] = 1` 会把每一行的第 0 列都改掉；必须用列表推导。
- **把 KL 当距离用**：方向写反（`KL(P‖Q)` vs `KL(Q‖P)`）结果完全不同；支撑集不重叠时直接是 `inf`。
- **Wasserstein 的单位**：`wasserstein_1d` 假设箱宽为 1，换成真实刻度（如 0.1 一档）要乘箱宽，否则数值差 10 倍。
- **协方差奇异**：特征完全共线或样本数少于特征数时 `invert_matrix` 会抛 `ValueError`；不要用 `try/except` 吞掉，应正则化或降维。
