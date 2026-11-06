# 代码讲解 · clustering.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 07 节 无监督学习 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python clustering.py`（无命令行参数，不到 1 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy / scikit-learn

---

## 1. 这份代码在考察什么

1. **四大聚类算法的内部机制**：K-Means（分配 ↔ 更新）、DBSCAN（从核心点向外"生长"）、GMM（EM 的软分配）、层次聚类（自底向上合并）。
2. **无标签时如何评估**：用 inertia（肘部法）和轮廓系数（silhouette）选择 K、比较算法。
3. **算法的适用边界**：在球形高斯簇上大家都表现不错；在双月牙这种非凸数据上，K-Means 的"最近中心"假设会出问题。
4. **聚类的副产品——异常检测**：DBSCAN 的噪声点天然就是离群点。
5. **数值计算意识**：GMM 中的指数下溢、方差下限、空簇处理等防御式写法。

> 一句话：**四种算法都只用"距离"这一种原料，区别在于怎样定义"一个簇"**——离同一个中心近（K-Means）、密度相连（DBSCAN）、来自同一个高斯分布（GMM）、合并代价小（层次聚类）。读这份代码时也要留意：几处演示的设置让输出与讲义叙述并不一致（见 3.8、第 6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `euclidean_distance` | 函数 | L2 距离 | 所有算法的"相似度"基础 |
| `kmeans` | 函数 | Lloyd 算法，返回 `(assignments, centroids)` | K-Means |
| `compute_inertia` | 函数 | 平方距离之和 | 肘部法 |
| `silhouette_score` | 函数 | 平均轮廓系数，`O(n²)` | 聚类质量的内部指标 |
| `find_best_k` | 函数 | 对多个 K 打印 inertia 与轮廓系数 | 选择 K |
| `dbscan` | 函数 | 含内部函数 `region_query`，返回标签（−1 为噪声） | 基于密度的聚类 |
| `gmm` | 函数 | 含内部函数 `gaussian_pdf`，EM 迭代 | 高斯混合模型、软分配 |
| `agglomerative_clustering` | 函数 | 四种 linkage 的凝聚式层次聚类，返回标签和合并历史 | 层次聚类、Ward 方法 |
| `make_blobs` / `make_moons` | 函数 | 生成球形高斯簇 / 双月牙数据 | 测试数据 |
| `if __name__ == "__main__":` | 入口 | 7 个演示：K-Means、肘部法、DBSCAN、GMM、层次聚类、月牙对比、异常检测 | — |

数据流：`make_blobs` / `make_moons` 生成数据 → 各聚类函数输出"每个点的簇编号" → `silhouette_score` / `compute_inertia` 评估。所有算法的输出格式一致（长度为 n 的标签列表），所以评估函数可以通用。

---

## 3. 逐段精讲

### 3.1 K-Means：分配与更新交替

```python
def kmeans(data, k, max_iterations=100, seed=42):
    random.seed(seed)
    n_features = len(data[0])

    centroids = random.sample(data, k)

    for iteration in range(max_iterations):
        clusters = [[] for _ in range(k)]
        assignments = []

        for point in data:
            distances = [euclidean_distance(point, c) for c in centroids]
            nearest = distances.index(min(distances))
            clusters[nearest].append(point)
            assignments.append(nearest)

        new_centroids = []
        for cluster in clusters:
            if len(cluster) == 0:
                new_centroids.append(random.choice(data))
                continue
            centroid = [
                sum(point[j] for point in cluster) / len(cluster)
                for j in range(n_features)
            ]
            new_centroids.append(centroid)

        if all(
            euclidean_distance(old, new) < 1e-6
            for old, new in zip(centroids, new_centroids)
        ):
            print(f"  Converged at iteration {iteration + 1}")
            break

        centroids = new_centroids

    return assignments, centroids
```

与讲义 Lloyd 算法四步一一对应：

| 讲义步骤 | 代码 |
|---------|------|
| 1. 随机选 K 个点作初始中心 | `random.sample(data, k)`（不放回抽样，保证 K 个中心互不相同） |
| 2. 每个点分配到最近中心 | `distances.index(min(distances))` 找最小距离的下标 |
| 3. 中心更新为簇内均值 | 按维度 `j` 求均值的列表推导 |
| 4. 重复直到不再变化 | 所有中心移动都 < `1e-6` 时 `break` |

- **空簇处理**：某个中心一个点都没分到时，用 `random.choice(data)` 随机挑一个数据点"复活"它，否则后面除以 `len(cluster) = 0` 会报错。sklearn 的做法是把离当前中心最远的点拿来当新中心，更有针对性。
- **收敛判据**：比较的是中心的位移，而不是 inertia。中心不动 ⇔ 下一轮分配也不会变 ⇔ 收敛。
- **固定种子**：每次调用都 `random.seed(seed)`，所以 `find_best_k` 中不同 K 的运行彼此独立且可复现。
- ⚠️ 只做**一次**初始化，没有多次重启（sklearn 有 `n_init`），也没有 K-Means++。测验 Q11 实测：换成 `seed=1` 时会收敛到 inertia ≈ 1016 的坏解。
- ⚠️ 若跑满 `max_iterations` 仍未收敛，返回的 `assignments` 是用上一轮中心算出来的，而 `centroids` 已更新为新中心，两者略有不一致（收敛时没有这个问题）。
- ⚠️ 函数内部直接 `print`，导致 `find_best_k` 每跑一次就多打印一行 "Converged at..."——库函数一般不应直接打印，可以返回迭代次数或用 `logging`。

### 3.2 inertia 与轮廓系数

```python
def compute_inertia(data, assignments, centroids):
    total = 0.0
    for point, cluster_id in zip(data, assignments):
        total += euclidean_distance(point, centroids[cluster_id]) ** 2
    return total
```

inertia 就是 K-Means 要最小化的目标函数：每个点到所属中心的**平方**距离之和。

```python
def silhouette_score(data, assignments):
    # ...
    clusters = {}
    for i, c in enumerate(assignments):
        clusters.setdefault(c, []).append(i)

    if len(clusters) < 2:
        return 0.0

    scores = []
    for i in range(n):
        own_cluster = assignments[i]
        own_members = [j for j in clusters[own_cluster] if j != i]

        if len(own_members) == 0:
            scores.append(0.0)
            continue

        a = sum(euclidean_distance(data[i], data[j]) for j in own_members) / len(own_members)

        b = float("inf")
        for cluster_id, members in clusters.items():
            if cluster_id == own_cluster:
                continue
            avg_dist = sum(euclidean_distance(data[i], data[j]) for j in members) / len(members)
            b = min(b, avg_dist)

        if max(a, b) == 0:
            scores.append(0.0)
        else:
            scores.append((b - a) / max(a, b))

    return sum(scores) / len(scores)
```

- **先建倒排表**：`clusters.setdefault(c, []).append(i)` 把"点 → 簇"转成"簇 → 点下标列表"，后面才能快速取出同簇和异簇成员。
- **a**：到本簇其他点（排除自己）的平均距离——衡量"紧不紧"。
- **b**：到**每个**其他簇的平均距离，取最小值——即"最近的邻簇"有多远。
- **s = (b − a)/max(a, b)**：b ≫ a 时接近 1；在边界上接近 0；离别的簇更近时为负。
- **边界情况**：只有 1 个簇时返回 0（轮廓系数无定义）；单点簇的 s 记为 0（与 sklearn 的约定一致）；`max(a, b) == 0`（所有点重合）时记 0，避免除零。
- 复杂度 `O(n²·d)`：每个点要和所有其他点算距离。sklearn 对大数据提供 `sample_size` 参数做抽样估计。
- 注意：DBSCAN 的噪声点标签是 −1，若直接传给这个函数，噪声点会被当作"第 −1 簇"参与计算。评估 DBSCAN 时一般先剔除噪声点。

### 3.3 `find_best_k`：肘部法 + 轮廓系数

```python
def find_best_k(data, max_k=10):
    print("Elbow method:")
    inertias = []
    for k in range(1, max_k + 1):
        assignments, centroids = kmeans(data, k)
        inertia = compute_inertia(data, assignments, centroids)
        inertias.append(inertia)
        print(f"  K={k}: inertia={inertia:.2f}")

    print("\nSilhouette scores:")
    for k in range(2, max_k + 1):
        assignments, centroids = kmeans(data, k)
        score = silhouette_score(data, assignments)
        print(f"  K={k}: silhouette={score:.4f}")

    return inertias
```

- 肘部法从 K=1 开始（K=1 的 inertia 就是数据的总平方和，作为基准）；轮廓系数从 K=2 开始（K=1 无定义）。
- 两个循环各自重新跑一遍 K-Means——由于种子固定，同一个 K 两次结果完全相同，所以这里只是浪费了一倍计算。更好的写法是一次循环同时算两个指标。
- 函数只打印、不自动选 K：肘部的位置需要人看，作者把判断留给读者。

### 3.4 DBSCAN：从核心点向外扩张

```python
def dbscan(data, eps, min_samples):
    n = len(data)
    labels = [-1] * n
    cluster_id = 0

    def region_query(point_idx):
        neighbors = []
        for i in range(n):
            if euclidean_distance(data[point_idx], data[i]) <= eps:
                neighbors.append(i)
        return neighbors

    visited = [False] * n

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True

        neighbors = region_query(i)

        if len(neighbors) < min_samples:
            labels[i] = -1
            continue

        labels[i] = cluster_id
        seed_set = list(neighbors)
        seed_set.remove(i)

        j = 0
        while j < len(seed_set):
            q = seed_set[j]

            if not visited[q]:
                visited[q] = True
                q_neighbors = region_query(q)
                if len(q_neighbors) >= min_samples:
                    for nb in q_neighbors:
                        if nb not in seed_set:
                            seed_set.append(nb)

            if labels[q] == -1:
                labels[q] = cluster_id

            j += 1

        cluster_id += 1

    return labels
```

流程拆解：

1. **`region_query`**：暴力扫描所有点，返回 `eps` 半径内的下标列表——**包括点自身**（距离 0 ≤ eps）。所以 `min_samples` 的计数含自己，与 sklearn 约定一致。它是嵌套函数，能直接读取外层的 `data`、`n`、`eps`（闭包）。
2. **外层循环**：找一个未访问的点。邻居不足 `min_samples` → 暂时标为噪声（−1）；否则它是核心点，开一个新簇。
3. **`seed_set` 扩张（BFS 队列）**：用下标 `j` 从前往后扫描一个**会不断变长**的列表。对每个邻居 q：
   - 若未访问：访问它；如果 q 也是核心点，就把 q 的邻居追加进队列——簇沿着"核心点链"向外生长。
   - 若 `labels[q] == -1`：把它纳入当前簇。这一句同时处理了两种情况：从未分配的点，以及**之前被暂判为噪声、其实是边界点**的点（"改判"）。
4. 一个簇扩张完毕，`cluster_id += 1`，回到外层循环找下一个种子。

- 为什么用 `while j < len(seed_set)` 而不是 `for q in seed_set`：在 `for` 循环中修改正在遍历的列表是危险写法；用显式下标 + `while` 可以安全地边遍历边追加。
- 边界点只在"从未被任何簇认领"时才会被分配（`labels[q] == -1` 的判断），所以一个同时靠近两个簇的边界点，归属于**先扩张到它的那个簇**——DBSCAN 的边界点归属依赖遍历顺序，这是算法本身的特性。
- ⚠️ `if nb not in seed_set` 在列表上查找是 `O(len)`，加上 `region_query` 的 `O(n)`，整体最坏 `O(n²)` 以上。生产实现用 KD-tree / Ball tree 做半径查询，并用集合或布尔数组判重。

### 3.5 GMM：EM 算法（各向同性方差版）

```python
def gmm(data, k, max_iterations=100, seed=42):
    random.seed(seed)
    n = len(data)
    d = len(data[0])

    indices = random.sample(range(n), k)
    means = [list(data[i]) for i in indices]
    variances = [1.0] * k
    weights = [1.0 / k] * k

    def gaussian_pdf(x, mean, variance):
        d = len(x)
        coeff = 1.0 / ((2 * math.pi * variance) ** (d / 2))
        exponent = -sum((xi - mi) ** 2 for xi, mi in zip(x, mean)) / (2 * variance)
        return coeff * math.exp(max(exponent, -500))
```

- **初始化**：均值取 K 个随机数据点（`list(data[i])` 复制一份，防止后面原地更新均值时改坏原数据），方差都设为 1，混合权重均等。
- **`gaussian_pdf`**：d 维**各向同性**高斯密度 `N(x | μ, σ²I) = (2πσ²)^(−d/2) · exp(−‖x−μ‖²/(2σ²))`。`variance` 是一个标量。
- ⚠️ 与讲义的差异：讲义说 GMM 更新"均值、协方差"、能建模**椭圆形**簇；这里每个分量只有一个标量方差，只能建模**圆形**簇（大小可以不同）。完整协方差版本需要矩阵求逆和行列式。
- ⚠️ `max(exponent, -500)`：防止 `exp` 下溢为 0，但会把所有"非常远"的点的相对概率抹平（测验 Q12：一个远点在两个分量上的 responsibility 都变成 0.5）。正确做法是在对数空间用 log-sum-exp。

```python
    for iteration in range(max_iterations):
        responsibilities = []
        for i in range(n):
            probs = []
            for j in range(k):
                probs.append(weights[j] * gaussian_pdf(data[i], means[j], variances[j]))
            total = sum(probs)
            if total == 0:
                total = 1e-300
            responsibilities.append([p / total for p in probs])

        old_means = [list(m) for m in means]

        for j in range(k):
            r_sum = sum(responsibilities[i][j] for i in range(n))
            if r_sum < 1e-10:
                continue

            weights[j] = r_sum / n

            for dim in range(d):
                means[j][dim] = sum(
                    responsibilities[i][j] * data[i][dim] for i in range(n)
                ) / r_sum

            variances[j] = sum(
                responsibilities[i][j]
                * sum((data[i][dim] - means[j][dim]) ** 2 for dim in range(d))
                for i in range(n)
            ) / (r_sum * d)
            variances[j] = max(variances[j], 1e-6)

        shift = sum(
            euclidean_distance(old_means[j], means[j]) for j in range(k)
        )
        if shift < 1e-6:
            print(f"  GMM converged at iteration {iteration + 1}")
            break
```

| EM 步骤 | 公式 | 代码 |
|---------|------|------|
| E 步 | `rᵢⱼ = πⱼ·N(xᵢ|μⱼ,σⱼ²) / Σₗ πₗ·N(xᵢ|μₗ,σₗ²)` | `probs` 归一化成 `responsibilities` |
| M 步：权重 | `πⱼ = Σᵢ rᵢⱼ / n` | `weights[j] = r_sum / n` |
| M 步：均值 | `μⱼ = Σᵢ rᵢⱼ xᵢ / Σᵢ rᵢⱼ` | 按维度加权平均 |
| M 步：方差 | `σⱼ² = Σᵢ rᵢⱼ‖xᵢ−μⱼ‖² / (d·Σᵢ rᵢⱼ)` | 除以 `r_sum * d`：d 个维度共享一个方差 |

- `r_sum` 是分量 j 的"有效样本数"（软计数）。小于 `1e-10` 说明这个分量几乎没认领任何点，跳过更新，防止除零。
- **方差下限 `1e-6`**：防止某个分量缩到只包住一个点、方差 → 0、密度 → ∞ 的退化解。
- **方差用的是新均值**：先更新 `means[j]`，再用新均值算方差——这是标准 EM 的顺序。
- 收敛判据是均值位移之和；更严谨的是监控对数似然的增量。
- 最后用 `responsibilities[i].index(max(...))` 把软分配转成硬标签，用来算轮廓系数。函数同时返回完整的 `responsibilities`，保留了"软"的信息。

### 3.6 层次聚类：四种 linkage

```python
def agglomerative_clustering(data, n_clusters=3, linkage="ward"):
    n = len(data)
    cluster_map = {i: [i] for i in range(n)}
    active_clusters = list(range(n))
    merge_history = []

    def cluster_distance(c1_indices, c2_indices):
        if linkage == "single":
            return min(
                euclidean_distance(data[i], data[j])
                for i in c1_indices
                for j in c2_indices
            )
        # ... "complete" 用 max，"average" 用平均
        elif linkage == "ward":
            # ... 分别求合并后、簇 1、簇 2 的中心
            return var_merged - var_1 - var_2
```

- **数据结构**：`cluster_map` 是"簇 id → 成员下标列表"的字典；`active_clusters` 是当前还存在的簇 id。初始时每个点自成一簇（id 0～n−1），每合并一次就生成一个新 id（从 n 开始递增），和 scipy 的 linkage 矩阵编号习惯一致。
- **四种 linkage**：
  - `single`：两簇间**最近**点对的距离——能连出细长链条，但容易被噪声"搭桥"。
  - `complete`：两簇间**最远**点对的距离——倾向紧凑、直径小的簇。
  - `average`：所有点对距离的平均——折中。
  - `ward`：合并后 SSE 的增量 `var_merged − var_1 − var_2`（变量名叫 var，实际是平方和）——和 K-Means 的目标一致，倾向大小相近的球形簇。
- 双重生成器 `for i in c1_indices for j in c2_indices` 枚举所有点对，相当于嵌套循环。

```python
    next_id = n
    while len(active_clusters) > n_clusters:
        best_dist = float("inf")
        best_pair = None

        for idx_a in range(len(active_clusters)):
            for idx_b in range(idx_a + 1, len(active_clusters)):
                # ... 计算距离，记录最小的一对
        c_a, c_b = best_pair
        cluster_map[next_id] = cluster_map[c_a] + cluster_map[c_b]
        merge_history.append((c_a, c_b, best_dist, len(cluster_map[next_id])))
        active_clusters.remove(c_a)
        active_clusters.remove(c_b)
        active_clusters.append(next_id)
        next_id += 1
```

- 每轮枚举所有活跃簇对、找距离最小的一对合并，直到剩 `n_clusters` 个簇——相当于在 dendrogram 上"在 K 个簇处切一刀"。
- `merge_history` 记录 `(簇a, 簇b, 合并距离, 新簇大小)`，就是 dendrogram 的完整信息。
- 最后把剩下的活跃簇重新编号为 0～K−1 作为标签。
- ⚠️ 复杂度：每轮 `O(m²)` 个簇对，每对的距离计算又要遍历成员，整体远高于 `O(n³)`，所以演示只用了 30 个点。生产实现（scipy / sklearn）用距离矩阵 + Lance–Williams 递推公式增量更新簇间距离。

### 3.7 两个数据生成器

```python
def make_blobs(centers, n_per_cluster=50, spread=0.5, seed=42):
    # ...
    for label, (cx, cy) in enumerate(centers):
        for _ in range(n_per_cluster):
            x = cx + random.gauss(0, spread)
            y = cy + random.gauss(0, spread)

def make_moons(n_samples=200, noise=0.1, seed=42):
    # ...
    for i in range(n_half):
        angle = math.pi * i / n_half
        x = math.cos(angle) + random.gauss(0, noise)
        y = math.sin(angle) + random.gauss(0, noise)
    # ...
    for i in range(n_half):
        angle = math.pi * i / n_half
        x = 1 - math.cos(angle) + random.gauss(0, noise)
        y = 1 - math.sin(angle) - 0.5 + random.gauss(0, noise)
```

- `make_blobs`：每个中心周围撒各向同性高斯噪声，**按簇顺序**依次生成——前 50 个点都属于第 0 簇。这一点在 3.8 中很关键。
- `make_moons`：第一个月牙是以原点为圆心的上半圆；第二个是平移、翻转后的下半圆（圆心 `(1, 0.5)`），两者交错，构成经典的非凸数据。这和 sklearn `make_moons` 的公式相同。
- `for label, (cx, cy) in enumerate(centers)`：`enumerate` 给出下标作标签，同时把每个中心 `[x, y]` 解包为 `cx, cy`。

### 3.8 主程序中的演示（以及三处需要注意的设置）

```python
    print("\n=== Hierarchical Clustering on 3 blobs (Ward linkage) ===")
    small_data = data[:30]
    hc_labels, merges = agglomerative_clustering(small_data, n_clusters=3)

    print("\n=== DBSCAN on moons (non-spherical clusters) ===")
    moon_data, moon_labels = make_moons(n_samples=200, noise=0.1)
    moon_db = dbscan(moon_data, eps=0.3, min_samples=5)

    print("\n=== K-Means on moons (will fail to separate) ===")
    moon_km, moon_centroids = kmeans(moon_data, k=2)
    moon_sil = silhouette_score(moon_data, moon_km)
```

1. ⚠️ **层次聚类的子集只来自一个簇**：`data[:30]` 全部来自中心 `[2, 2]`，所以标题 "on 3 blobs" 名不副实——实际是在一个高斯团里硬切 3 份。改成 `data[::5]` 后，三个簇各 10 个点，层次聚类完美恢复真实分组（轮廓系数 0.7636）。
2. ⚠️ **DBSCAN 在月牙上只找到 1 个簇**：两个月牙最近点距离约 0.17 < `eps=0.3`，被"桥接"成一个簇，与讲义"DBSCAN 能分开月牙"的叙述相反。实测 `eps=0.2` 时正确分成 2 簇（2 个噪声点）。
3. ⚠️ **用轮廓系数证明 K-Means"失败"不成立**：轮廓系数偏爱凸形簇，K-Means 切分的 0.4895 反而高于真实月牙标签的 0.3135。要看是否分对，应使用真实标签（`moon_labels` 已经生成了但没有用上）计算外部指标，实测 K-Means 与真实标签的一致率是 75%。

```python
    anomaly_data = list(data)
    anomaly_data.append([20.0, 20.0])
    anomaly_data.append([-5.0, -5.0])
    anomaly_data.append([15.0, 0.0])
    anomaly_labels = dbscan(anomaly_data, eps=1.5, min_samples=5)
```

- `list(data)` 先复制一份，再追加 3 个人工离群点，避免修改原始 `data`（浅拷贝：外层列表是新的，内部点仍是同一对象，但这里只追加不修改，所以安全）。
- 3 个点远离所有簇，`eps=1.5` 内连自己在内只有 1 个点，被标为噪声——正好演示"DBSCAN 噪声点 = 异常点"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 所有算法输出统一的"标签列表" | 评估函数可以通用，算法可横向对比 | sklearn 统一为 `labels_` 属性和 `fit_predict` 接口 |
| K-Means 随机初始化、只跑一次 | 最简单 | 会陷入局部最优；用 K-Means++ + `n_init` 多次重启 |
| 空簇用随机点"复活" | 避免除零 | sklearn 选离中心最远的点 |
| DBSCAN 暴力半径查询 + 列表判重 | 代码直观 | `O(n²)`；用空间索引和集合/布尔数组 |
| GMM 各向同性方差 | 无需矩阵运算，标准库可实现 | 只能拟合圆形簇；生产中用完整协方差（`covariance_type="full"`） |
| `exp` 指数钳在 −500 | 防止下溢 | 抹平远点概率；用对数空间 + log-sum-exp |
| 方差下限 `1e-6` | 防止分量塌缩、似然发散 | sklearn 用 `reg_covar` 在协方差对角线上加小正则 |
| 层次聚类每轮重算所有簇对距离 | 公式直观 | 复杂度极高；用距离矩阵 + Lance–Williams 递推 |
| 收敛判据看中心/均值位移 | 简单 | GMM 更应监控对数似然的变化 |
| 函数内部 `print` 收敛信息 | 便于观察迭代次数 | 输出混杂；返回迭代数或使用 `logging` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `random.sample` / `random.choice` / `random.gauss` | `random.sample(data, k)`、`random.choice(data)` | 不放回抽 k 个；随机抽 1 个；正态分布随机数 |
| 列表推导创建独立子列表 | `[[] for _ in range(k)]` | 每个簇一个独立的空列表；不能写成 `[[]] * k` |
| `list.index(min(...))` | `distances.index(min(distances))` | 找最小值所在的下标（argmin） |
| `all()` + 生成器 | `all(euclidean_distance(old, new) < 1e-6 for old, new in zip(...))` | 全部满足才为 True，遇到 False 立即短路 |
| `dict.setdefault` | `clusters.setdefault(c, []).append(i)` | 键不存在时先放入默认值再返回，一行完成分组 |
| `dict.items()` | `for cluster_id, members in clusters.items()` | 同时遍历键和值 |
| 字典推导 | `cluster_map = {i: [i] for i in range(n)}` | 一行构造字典 |
| 嵌套函数（闭包） | `region_query`、`gaussian_pdf`、`cluster_distance` | 内部函数可读取外层变量（如 `data`、`eps`、`linkage`） |
| `while` + 手动下标 | `while j < len(seed_set): ... j += 1` | 遍历一个在循环中会变长的列表 |
| `in` 成员判断 | `if nb not in seed_set` | 列表上是 `O(n)` 线性查找；集合上是 `O(1)` |
| 双重生成器表达式 | `min(... for i in c1_indices for j in c2_indices)` | 等价于两层嵌套循环 |
| `enumerate` + 解包 | `for label, (cx, cy) in enumerate(centers)` | 同时拿下标和解包后的元素 |
| 列表浅拷贝 | `list(data[i])`、`list(data)`、`[list(m) for m in means]` | 复制外层列表，避免原地修改影响原数据 |
| 集合运算 | `len(set(db_labels) - {-1})` | 去重后减去噪声标签，得到簇的个数 |
| `list.count` / `list.remove` | `db_labels.count(-1)`、`seed_set.remove(i)` | 统计出现次数；删除第一个匹配值 |
| 浮点无穷 | `b = float("inf")` | 求最小值时的初始值 |
| 嵌套推导 + `round` | `[[round(c, 2) for c in cent] for cent in centroids]` | 打印时保留 2 位小数 |

---

## 6. 运行结果解读

实际运行：在临时副本目录执行 `python3 clustering.py`，约 0.3 秒完成，结果固定可复现。

**① K-Means 与肘部法**

```text
=== K-Means on 3 blobs ===
  Converged at iteration 4
  Centroids: [[5.0, 8.05], [2.12, 1.98], [8.11, 3.16]]
  Silhouette score: 0.7541

  K=1: inertia=2127.55
  K=2: inertia=1031.04
  K=3: inertia=190.22
  K=4: inertia=158.49
  K=6: inertia=115.03

  K=2: silhouette=0.5479
  K=3: silhouette=0.7541
  K=4: silhouette=0.6137
  K=6: silhouette=0.3368
```

- 学到的三个中心与真实中心 `[2,2]`、`[8,3]`、`[5,8]` 非常接近（中心的顺序取决于初始化，没有意义）。
- inertia 在 K=3 处出现明显拐点（1031 → 190，之后每次只降 20～30）；轮廓系数也在 K=3 时最高。两种方法结论一致。
- 输出中夹杂的 "Converged at iteration ..." 来自 `kmeans` 内部的 `print`。

**② DBSCAN 与 GMM（球形簇）**

```text
=== DBSCAN on 3 blobs ===
  Found 3 clusters, 0 noise points

=== GMM on 3 blobs ===
  GMM converged at iteration 9
  Means: [[5.0, 8.05], [2.12, 1.98], [8.11, 3.16]]
  Weights: [0.333, 0.333, 0.333]
  Silhouette score: 0.7541
```

- 三个簇分得很开，DBSCAN 不需要指定 K 就找到了 3 个簇。
- GMM 的均值与 K-Means 的中心（保留两位小数）完全一致、轮廓系数也相同；混合权重都是 1/3，正好反映每簇 50 个点。在分得很开的球形簇上，GMM 的软分配几乎都是 0/1，与 K-Means 结果一致——印证了"K-Means 是 GMM 的硬分配特例"。

**③ 层次聚类**

```text
=== Hierarchical Clustering on 3 blobs (Ward linkage) ===
  Silhouette score: 0.4473
  Last 3 merges: [(50, 53, 1.52), (16, 51, 2.25), (52, 54, 3.7)]
```

- 合并记录里的 id ≥ 30 都是合并产生的新簇（30 个点，id 0～29 是原始单点）。最后几次合并的 Ward 代价 1.52 → 2.25 → 3.7 逐渐增大。
- 轮廓系数只有 0.4473，原因见 3.8：这 30 个点全部来自同一个高斯簇，被硬切成了 3 份。

**④ 双月牙**

```text
=== DBSCAN on moons (non-spherical clusters) ===
  Found 1 clusters, 0 noise points

=== K-Means on moons (will fail to separate) ===
  Converged at iteration 5
  Silhouette score: 0.4895
```

- DBSCAN 把两个月牙连成了 1 个簇：`eps=0.3` 大于两个月牙之间的最小间隙（约 0.17）。把 `eps` 改为 0.2 才能分开（2 簇 + 2 个噪声点）。
- K-Means 的轮廓系数 0.4895 并不能说明它"失败"——真实月牙标签的轮廓系数只有 0.3135。要看对错应对照 `moon_labels`：K-Means 与真实标签一致率为 75%，确实没分好，但证据需要用外部指标给出。

**⑤ 异常检测**

```text
=== Anomaly detection with DBSCAN ===
  Detected 3 anomalies
    Point [20.0, 20.0]
    Point [-5.0, -5.0]
    Point [15.0, 0.0]
```

原始 150 个点都被归入簇中（0 个噪声），人工加入的 3 个远点全部被识别为噪声——DBSCAN 不需要额外训练就具备异常检测能力。

---

## 7. 动手改一改

1. **修正层次聚类演示**：把 `data[:30]` 改成 `data[::5]`，再分别试 `linkage="single"` / `"complete"` / `"average"`，对比轮廓系数与合并历史。
2. **让 DBSCAN 分开月牙**：对 `eps ∈ {0.1, 0.15, 0.2, 0.25, 0.3}` 打印簇数与噪声数，再实现 k-距离图（每个点到第 5 近邻的距离，排序后打印）来找合适的 `eps`。
3. **加入外部指标**：写一个函数，在"标签最优对应"下计算聚类与真实标签的一致率（K=2 时只需比较 `acc` 与 `1 − acc`），用它评估月牙上的 K-Means 和 DBSCAN。
4. **K-Means++ 与多次重启**：实现 `kmeans_pp_init`，再加 `n_init` 参数跑多次取 inertia 最小的结果；用 `seed=1` 验证能避开 inertia ≈ 1016 的坏解。
5. **GMM 数值稳定化**：把 E 步改为对数空间 + log-sum-exp，并在每轮计算对数似然 `Σᵢ log Σⱼ πⱼN(xᵢ|μⱼ,σⱼ²)`，用它的增量作为收敛判据。
6. **（进阶）对角协方差 GMM**：把 `variances[j]` 从标量改为长度为 d 的列表，每个维度一个方差，让 GMM 能拟合沿坐标轴拉长的椭圆簇；用 `make_blobs` 改造出 x、y 方向尺度不同的数据来验证。

---

## 8. 常见坑

- **`[[]] * k` 创建子列表**：k 个"簇"共享同一个列表对象，往一个簇里加点所有簇都会变；必须用 `[[] for _ in range(k)]`。
- **忘记特征缩放**：所有算法都基于欧氏距离，量纲大的特征会主导聚类结果。
- **用轮廓系数评价非凸聚类**：它偏爱球形簇，会低估 DBSCAN 在月牙、环形数据上的正确结果。
- **DBSCAN 的噪声标签 −1 直接参与评估**：计算轮廓系数前要先剔除噪声点，否则噪声会被当作一个"簇"。
- **GMM 中的 `exp` 上溢/下溢**：高维或远点时概率乘积极小，不在对数空间计算就会出现除零或概率被抹平。
- **只看前 N 个样本做子集**：数据往往按类别或时间排序，`data[:30]` 这类切片可能只取到一个类别——抽样前先打乱。
