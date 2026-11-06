# 测验 · 无监督学习（Unsupervised Learning）

> **阶段 02 · 机器学习基础 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/clustering.py](../code/clustering.py) ｜ 代码讲解：[code/clustering.讲解.md](../code/clustering.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 无监督学习 | 没有标签，算法自己发现分组、结构和异常；难点在于没有"标准答案"来评估 |
| 2 | K-Means（Lloyd 算法） | 随机选 K 个中心 → 分配到最近中心 → 中心更新为簇均值 → 迭代至收敛；只保证局部最优，依赖初始化 |
| 3 | Inertia 与肘部法 | inertia = 各点到所属中心的平方距离之和，随 K 单调下降；找"下降突然变缓"的拐点 |
| 4 | 轮廓系数（silhouette） | 每个点 `s = (b − a)/max(a, b)`，a 为簇内平均距离、b 为最近其他簇的平均距离；范围 [−1, 1] |
| 5 | DBSCAN | 参数 `eps`、`min_samples`；核心点 / 边界点 / 噪声点；能发现任意形状、自动确定簇数、天然标出离群点；怕密度不均 |
| 6 | 层次聚类 | 自底向上合并最近的两簇，形成树状图（dendrogram）；single / complete / average / Ward 四种簇间距离 |
| 7 | GMM 与 EM | 软分配：E 步算每个点属于各高斯的概率（responsibility），M 步更新均值、方差、混合权重 |
| 8 | 算法选型 | K-Means：大数据、球形簇、K 已知；DBSCAN：任意形状、K 未知、有噪声；层次：小数据、要树状结构；GMM：重叠、需要概率 |
| 9 | 聚类做异常检测 | K-Means：离所有中心都远；DBSCAN：噪声点；GMM：在所有分量下概率都低 |

### 核心技能（能动手做到）

- [ ] 从零实现 K-Means，并用肘部法 + 轮廓系数在 K=1～6 中选出 K=3
- [ ] 从零实现 O(n²) 的轮廓系数，并能手算一个 4 点小例子
- [ ] 从零实现 DBSCAN，能解释 `seed_set` 扩展过程中"噪声点被改判为边界点"的逻辑
- [ ] 从零实现各向同性方差的 GMM（EM 算法），并说明它与 K-Means 的关系
- [ ] 实现 K-Means++ 初始化，并演示它能避开随机初始化陷入的局部最优
- [ ] 能针对"双月牙"数据调出让 DBSCAN 正确分成 2 簇的 `eps`，并说明为什么轮廓系数不能用来证明 K-Means 在这里"失败"

---

## 二、基础自测（选择题）

**Q1.** 关于 K-Means（Lloyd 算法），下列说法**错误**的是：

- A. 每轮"分配 + 更新"后，inertia 不会上升
- B. 算法一定会在有限步内收敛
- C. 不论初始中心怎么选，都会收敛到全局最优解
- D. 只能找到局部最优，常用多次随机初始化或 K-Means++ 缓解

**Q2.** 某个点到本簇其他点的平均距离 `a = 2`，到最近的其他簇的平均距离 `b = 6`，它的轮廓系数是：

- A. 0.333
- B. 0.667
- C. 3
- D. −0.667

**Q3.** 一份数据跑 K=1～6 的 K-Means，inertia 依次为 `2127, 1031, 190, 158, 132, 115`。用肘部法最合理的 K 是：

- A. 1
- B. 3
- C. 6，因为 inertia 最小
- D. 无法判断

**Q4.** DBSCAN 中 `min_samples = 4`（计数包含点自身）。点 P 的 `eps` 邻域内共有 3 个点（含 P 自己），但 P 在某个核心点 Q 的 `eps` 邻域内。P 是：

- A. 核心点
- B. 边界点
- C. 噪声点
- D. 取决于 K

**Q5.** 关于 GMM 与 K-Means 的关系，下列说法**正确**的是：

- A. GMM 给出硬分配，K-Means 给出软分配
- B. 当 GMM 所有分量共享相同的各向同性方差且方差趋于 0 时，responsibility 退化为 one-hot，EM 退化为 K-Means
- C. GMM 不需要指定分量个数
- D. GMM 的 EM 算法保证找到全局最大似然解

**Q6.** 关于层次聚类的簇间距离（linkage），下列说法**正确**的是：

- A. single linkage 用两簇间最远点的距离，容易产生紧凑的球形簇
- B. complete linkage 用两簇间最近点的距离，容易产生"链式效应"
- C. Ward 方法每次选择合并后簇内平方和（SSE）增量最小的两簇
- D. average linkage 只计算两簇中心之间的距离

**Q7.** 为什么不能直接选"inertia 最小的 K"？

- A. inertia 计算太慢
- B. inertia 随 K 增大单调不增，K = n 时为 0，"最小"永远指向最大的 K
- C. inertia 只适用于 DBSCAN
- D. inertia 可能为负数

**Q8.** 以下哪种情况 DBSCAN **最**容易表现不好？

- A. 簇的形状是月牙形或环形
- B. 数据中混有少量离群点
- C. 不同簇的密度差异很大（一个很稠密，一个很稀疏）
- D. 事先不知道簇的个数

---

## 三、动手 / 代码题

**Q9.** 代码在双月牙数据上运行的实际输出如下：

```text
=== DBSCAN on moons (non-spherical clusters) ===
  Found 1 clusters, 0 noise points

=== K-Means on moons (will fail to separate) ===
  Converged at iteration 5
  Silhouette score: 0.4895
  K-Means splits moons poorly because they are not spherical
```

（1）DBSCAN 用的是 `dbscan(moon_data, eps=0.3, min_samples=5)`，为什么只找到 1 个簇？已知两个月牙之间最近的两个点距离约 0.17。怎么改参数？
（2）打印的轮廓系数 0.4895 能证明 K-Means "失败"吗？已知用真实月牙标签计算的轮廓系数只有 0.3135。

**Q10.** 层次聚类的演示代码如下，数据由 `make_blobs` 按簇依次生成（前 50 个点全部来自中心 `[2, 2]`）：

```python
    data, true_labels = make_blobs(centers, n_per_cluster=50, spread=0.8)
    # ...
    small_data = data[:30]
    hc_labels, merges = agglomerative_clustering(small_data, n_clusters=3)
    hc_sil = silhouette_score(small_data, hc_labels)
```

这个演示有什么问题？输出的轮廓系数 0.4473 说明了什么？请给出一行修正。

**Q11.** 讲义练习 1：实现 K-Means++ 初始化——第一个中心随机选，之后每个新中心以"到最近已有中心的平方距离"为权重抽样。写出 `kmeans_pp_init(data, k)`，并说明它为什么能减少陷入局部最优。

**Q12.** GMM 的 E 步用到下面这个函数：

```python
    def gaussian_pdf(x, mean, variance):
        d = len(x)
        coeff = 1.0 / ((2 * math.pi * variance) ** (d / 2))
        exponent = -sum((xi - mi) ** 2 for xi, mi in zip(x, mean)) / (2 * variance)
        return coeff * math.exp(max(exponent, -500))
```

（1）`variance` 是一个标量，这意味着这个 GMM 能建模什么形状的簇？和讲义中"GMM 能建模椭圆形簇"一致吗？
（2）`max(exponent, -500)` 是为了解决什么问题？它会带来什么副作用？（提示：考虑一个离两个分量都很远的点 `[100, 100]`，两分量均值 `[0,0]`、`[1,1]`，方差都是 0.01。）
（3）用 log-sum-exp 改写 E 步，消除这个副作用。

---

## 四、面试高频题

**Q13.**（基础必考）讲一下 K-Means 的算法流程、目标函数、时间复杂度和主要缺点。K-Means++ 解决了什么问题？

**Q14.**（工程实践）没有标签时，你如何评估聚类结果、如何选择簇数？

**Q15.**（原理深挖）EM 算法的 E 步和 M 步分别在做什么？为什么说 K-Means 是"硬 EM"？EM 一定收敛吗？

**Q16.**（原理深挖）DBSCAN 的 `eps` 和 `min_samples` 怎么调？相比 K-Means 有什么优缺点？HDBSCAN 改进了什么？

**Q17.**（场景设计）电商要做用户分群（运营要 5～8 个可解释的人群），你会怎么做？上线后新用户如何归类？

**Q18.**（结合大模型）一个 LLM 客服应用每天有 10 万条用户 query，产品经理想知道"用户都在问什么"。请设计一个基于聚类的主题发现流程。

---

## 五、参考答案与解析

### Q1 — 答案：C

Lloyd 算法中，"分配到最近中心"和"中心取均值"两步都只会让 inertia 下降或不变（A 对）；划分方式有限，目标单调不增，所以一定在有限步收敛（B 对）。但它只收敛到**局部**最优。本节实测：同一份 3 簇数据，随机种子 `seed=1` 的初始化收敛到 inertia ≈ 1016 的坏解（两个真实簇被合并），而其他种子和 K-Means++ 都得到 190.22。

### Q2 — 答案：B

`s = (6 − 2)/max(2, 6) = 4/6 ≈ 0.667`。b 远大于 a，说明这个点离本簇很近、离别的簇很远，聚类良好。s 接近 0 表示在两簇边界上，s < 0 表示它离别的簇反而更近（可能分错了）。

### Q3 — 答案：B

从 K=2 到 K=3，inertia 从 1031 骤降到 190；之后每加一个簇只减少 20～30。拐点在 K=3。这组数字就是本节代码在 3 个高斯簇上的真实输出，同时 K=3 的轮廓系数也最高（0.7541）。C 是典型错误，见 Q7。

### Q4 — 答案：B

P 邻域内只有 3 个点，不足 `min_samples=4`，所以不是核心点；但它落在核心点 Q 的邻域内，因此是**边界点**，会被并入 Q 所在的簇。既不是核心点、也不在任何核心点邻域内的才是噪声点。注意：本节实现的 `region_query` 会把点自身算进邻居（距离 0 ≤ eps），和 sklearn 的约定一致。

### Q5 — 答案：B

responsibility `rᵢⱼ ∝ πⱼ·exp(−‖xᵢ−μⱼ‖²/(2σ²))`，σ → 0 时最近的那个分量的项压倒其他所有项，`rᵢⱼ` 变成 0/1，M 步的加权均值退化为簇均值——这正是 K-Means。A 说反了；C 错：GMM 同样要指定分量数 K（可用 BIC 选）；D 错：EM 只保证似然不下降，可能停在局部最优。

### Q6 — 答案：C

Ward 方法每次合并使"合并后的 SSE − 两簇各自的 SSE"最小，本节代码的 `var_merged - var_1 - var_2` 正是这个增量。A、B 把 single 和 complete 说反了：single 用**最近**点距离，容易链式；complete 用**最远**点距离，倾向紧凑。D 错：average 是所有点对距离的平均，不是中心距离（那叫 centroid linkage）。

### Q7 — 答案：B

K 越大，每个点离中心越近，inertia 只降不升；K = n 时每个点自成一簇，inertia = 0。所以 inertia 只能用来找"性价比拐点"（肘部法），不能直接取最小。轮廓系数则会在簇数过多时下降（本节 K=6 时降到 0.3368），可以互相补充。

### Q8 — 答案：C

DBSCAN 用一个全局的 `eps` 定义"稠密"。若一个簇很稠密、另一个很稀疏，`eps` 小了稀疏簇全被当成噪声，`eps` 大了稠密区域的相邻簇会被连成一片。A、B、D 恰恰是 DBSCAN 的优势。HDBSCAN、OPTICS 就是为解决密度不均而提出的。

### Q9 — 参考答案

（1）DBSCAN 的簇是"核心点通过 `eps` 链式相连"形成的。双月牙每个月牙 100 个点，沿弧线非常密集，几乎每个点都是核心点；两个月牙最近的点距离约 0.17 < `eps = 0.3`，只要有一对跨月牙的核心点彼此在 `eps` 内，两个月牙就被"桥接"成一个簇。把 `eps` 调到 0.2 可以解决：实测 `eps=0.2` 时得到 2 个簇、2 个噪声点，与真实标签只差 1 个点；`eps=0.15` 时又碎成 10 个簇，`eps=0.1` 时 134 个噪声点——DBSCAN 对 `eps` 非常敏感。工程上用 k-距离图（每个点到第 k 近邻的距离排序后找拐点）来估计 `eps`。

（2）不能。轮廓系数度量的是"簇内紧、簇间远"的**凸形**结构，天然偏爱 K-Means 这种球形切分。真实的月牙划分是非凸的，轮廓系数反而更低（0.3135 < 0.4895）。也就是说，如果只看轮廓系数，你会得出"K-Means 比真实答案还好"的荒谬结论。要证明 K-Means 失败，应该用真实标签计算外部指标（如 ARI、或在最优标签对应下的准确率）——实测 K-Means 与真实月牙标签的一致率只有 75%。这也说明：**内部指标有偏好，选错指标会得出错误结论**。

### Q10 — 参考答案

问题：`data[:30]` 只取了前 30 个点，而 `make_blobs` 按簇顺序生成，前 50 个点全部来自中心 `[2, 2]` 这一个簇。所以层次聚类实际上是在**一个高斯团内部**硬切成 3 份，并没有演示"在 3 个真实簇上做层次聚类"。轮廓系数 0.4473 明显低于 K-Means 在全量数据上的 0.7541，正是因为这 3 个"簇"本来就不该被分开。

修正：均匀抽样，让三个簇都有代表：

```python
    small_data = data[::5]   # 每 5 个取 1 个，150 → 30 个点，每簇 10 个
```

实测修正后轮廓系数为 0.7636，且 3 个簇与真实标签一一对应（每簇 10 个点）。另一种做法是先 `random.shuffle` 再取前 30 个。

### Q11 — 参考答案

```python
def kmeans_pp_init(data, k):
    centroids = [random.choice(data)]                      # 第一个中心：均匀随机
    for _ in range(1, k):
        d2 = [min(euclidean_distance(p, c) ** 2 for c in centroids) for p in data]
        r = random.uniform(0, sum(d2))                     # 轮盘赌：按 D(x)² 抽样
        acc = 0.0
        for p, w in zip(data, d2):
            acc += w
            if acc >= r:
                centroids.append(p)
                break
    return centroids
```

把 `kmeans` 中的 `centroids = random.sample(data, k)` 替换为 `centroids = kmeans_pp_init(data, k)` 即可。

原理：离已有中心越远的点被选为新中心的概率越大（与距离平方成正比），初始中心因此倾向于**分散在不同的簇里**，避免"两个初始中心落在同一簇、另一个簇没有中心"导致的坏局部最优。已有中心本身 `D(x)² = 0`，不会被重复选中。实测：随机初始化在 `seed=1` 时收敛到 inertia ≈ 1016，K-Means++ 在 seed 0～4 上都得到 190.22，且迭代次数不多于随机初始化。K-Means++ 还有理论保证：期望 inertia 不超过最优解的 `O(log K)` 倍。

### Q12 — 参考答案

（1）`variance` 是标量，协方差矩阵为 `σ²·I`——**各向同性**的球形高斯，每个分量只能建模"圆形/球形、但大小可以不同"的簇，不能建模椭圆或有倾斜方向的簇。讲义所说"GMM 能建模椭圆形簇"指的是**完整协方差**的 GMM（sklearn `GaussianMixture` 默认 `covariance_type="full"`）。本节实现是一种简化。

（2）当点离均值很远时，`exponent` 是一个很大的负数，`math.exp` 会下溢为 0；所有分量的概率都为 0 时，`total == 0`，responsibility 无法计算。`max(exponent, -500)` 把指数下限钳在 −500，保证 `exp` 不为 0。副作用：所有"足够远"的距离被抹成同一个值，失去了区分度。以题中的点为例：到 `[0,0]` 和 `[1,1]` 的指数分别约为 −1,000,000 和 −980,100，都被钳成 −500，两个分量的 responsibility 都是 0.5——但真实答案应该几乎全部归给更近的 `[1,1]`。

（3）在对数空间计算，再用 log-sum-exp 归一化：

```python
def log_gaussian_pdf(x, mean, variance):
    d = len(x)
    sq = sum((xi - mi) ** 2 for xi, mi in zip(x, mean))
    return -0.5 * d * math.log(2 * math.pi * variance) - sq / (2 * variance)

def e_step(data, means, variances, weights):
    resp = []
    for x in data:
        lps = [math.log(w) + log_gaussian_pdf(x, m, v)
               for m, v, w in zip(means, variances, weights)]
        mx = max(lps)                                      # 减去最大值防止上/下溢
        log_total = mx + math.log(sum(math.exp(lp - mx) for lp in lps))
        resp.append([math.exp(lp - log_total) for lp in lps])
    return resp
```

实测对上面那个远点，改写后 responsibility 为 `[0.0, 1.0]`，正确地归给了更近的分量。这是 sklearn 等库实现 GMM 的标准做法（讲义中"库版本增加了数值稳定性"的一个具体例子）。注意 `math.log(w)` 要求混合权重大于 0。

### Q13 — 参考回答要点

- **流程**：初始化 K 个中心 → 分配（每点归最近中心）→ 更新（中心 = 簇均值）→ 重复至分配不再变化。
- **目标**：最小化 inertia `Σᵢ‖xᵢ − μ_c(i)‖²`；两步交替相当于坐标下降，每步都不增加目标。
- **复杂度**：每轮 `O(n·K·d)`，总计 `O(n·K·d·T)`，T 为迭代次数，通常很小；适合大数据，还有 Mini-Batch K-Means。
- **缺点**：①要预先指定 K；②只找局部最优、依赖初始化；③假设簇是凸的、大小相近的球形（因为用欧氏距离和均值）；④对离群点敏感（均值会被拉偏）；⑤对特征尺度敏感，需要标准化。
- **K-Means++**：按 `D(x)²` 抽样选初始中心，让初始中心分散，减少坏局部最优、加快收敛，并有 `O(log K)` 近似比保证；sklearn 默认使用。
- **加分点**：提到 K-Medoids（中心必须是真实样本，对离群点更稳）、球面 K-Means（对归一化 embedding 用余弦）。

### Q14 — 参考回答要点

- **内部指标**（不需要标签）：inertia + 肘部法；轮廓系数（越大越好）；Calinski-Harabasz（越大越好）、Davies-Bouldin（越小越好）；GMM 用 BIC/AIC。
- **注意各指标的偏好**：轮廓系数、CH 指数偏爱凸形、分离良好的簇，对 DBSCAN 找到的非凸簇不公平（本节双月牙实验就是反例）。
- **稳定性**：对数据做子采样或换随机种子重复聚类，结果一致的 K 更可信。
- **外部验证**：有少量标签时用 ARI、NMI；最终要回到业务——簇是否可解释、是否可行动，能否支撑下游指标（如分群运营的转化率提升）。
- **可视化**：PCA / t-SNE / UMAP 降到 2D 看结构（但 t-SNE 的簇间距离不可信）。
- **常见误区**：直接选 inertia 最小的 K；只看一个指标就下结论。

### Q15 — 参考回答要点

- **E 步**：固定参数，计算每个点属于每个分量的后验概率 `rᵢⱼ = πⱼ·N(xᵢ|μⱼ,Σⱼ) / Σₗ πₗ·N(xᵢ|μₗ,Σₗ)`。
- **M 步**：固定 r，按加权最大似然更新 `πⱼ = Σᵢrᵢⱼ/n`、`μⱼ = Σᵢrᵢⱼxᵢ/Σᵢrᵢⱼ`、协方差为加权散布矩阵（本节代码为各向同性：`σⱼ² = Σᵢrᵢⱼ‖xᵢ−μⱼ‖² / (d·Σᵢrᵢⱼ)`）。
- **硬 EM**：K-Means 把 E 步的软概率换成"最近中心取 1、其余取 0"，M 步的加权均值就变成普通均值，且所有分量方差相同——就是 K-Means。
- **收敛性**：EM 每轮都不降低对数似然（它在优化似然的一个下界），所以一定收敛，但可能收敛到局部最优或鞍点；GMM 还可能出现某个分量塌缩到单个点、方差 → 0、似然 → ∞ 的退化解，所以要加方差下限（本节代码中 `max(variances[j], 1e-6)`）或正则。
- **加分点**：判断收敛最好看对数似然的变化，而不只是均值的位移（本节代码用的是后者）。

### Q16 — 参考回答要点

- **调参**：`min_samples` 一般取 `≥ 维度 + 1`，常见经验值约为 `2·维度`，数据噪声越大取越大；`eps` 用 k-距离图（k = `min_samples`）的拐点。参数对结果非常敏感（Q9 中 `eps` 从 0.3 到 0.2 到 0.15，簇数从 1 到 2 到 10）。
- **优点**：不用指定簇数；能发现任意形状；天然输出噪声点（可直接用于异常检测）；对离群点鲁棒。
- **缺点**：密度不均时失效；高维下距离失效、`eps` 难调；边界点的归属取决于遍历顺序（不完全确定）；暴力实现 `O(n²)`，需要空间索引加速。
- **HDBSCAN**：在所有 `eps` 尺度上构建层次结构，再按簇的稳定性挑选，能处理密度不均的簇，基本只需设置最小簇大小，并且能给出每个点属于簇的强度。
- **常见误区**：在未标准化的数据上用 DBSCAN；把 `eps` 当成"簇的大小"。

### Q17 — 参考回答要点

- **特征**：RFM（最近一次购买、频次、金额）、品类偏好、活跃时段、渠道等；金额类做对数变换；全部标准化；高度相关的特征先降维或筛选，避免某类信息被重复加权。
- **算法**：要求 5～8 个可解释人群 → K-Means（或 GMM）为主，在 K=4～10 上用肘部法 + 轮廓系数 + 业务可解释性综合选择；用 K-Means++ 并多次初始化取最好。
- **解释**：对每个簇看中心（反标准化回原始单位）和与整体均值的差异，命名为"高价值低频""价格敏感"等；可以训练一棵浅层决策树来近似聚类结果，得到可读的规则。
- **上线**：保存 scaler 和簇中心，新用户用同样的预处理后分配到最近中心（K-Means 天然支持；DBSCAN 不支持直接预测新点）；定期重训，并监控各簇占比漂移。
- **评估**：分群后运营策略的 A/B 测试效果才是最终标准。
- **加分点**：提到稳定性检验（换时间窗口重训，簇是否还能对上），以及异常用户（羊毛党）可以用 DBSCAN / Isolation Forest 先剔除。

### Q18 — 参考回答要点

- **流程**：
  1. 预处理：去重、脱敏、过滤过短/无意义 query。
  2. 向量化：用句向量 embedding 模型编码，L2 归一化（之后欧氏距离与余弦等价）。
  3. 降维（可选）：PCA 或 UMAP 降到几十维，缓解高维距离集中问题，也能加速聚类。
  4. 聚类：数量未知、有大量长尾和噪声 → HDBSCAN/DBSCAN；想要固定数量的主题 → K-Means（大数据可用 Mini-Batch）。
  5. 命名：每个簇抽取离中心最近的若干条 query（或用 c-TF-IDF 提关键词），交给 LLM 生成主题名和描述。
  6. 评估与迭代：抽样人工检查簇的纯度，合并过细的簇、拆分过粗的簇；噪声簇单独看，可能是新出现的问题。
- **工程**：增量数据用"分配到已有簇中心 + 定期全量重聚类"；跟踪各主题占比随时间的变化，用于发现新问题。
- **加分点**：提到 BERTopic 这类现成方案（embedding + UMAP + HDBSCAN + c-TF-IDF）；指出聚类结果高度依赖 embedding 模型的选择。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 14 范数与距离](../../../01-math-foundations/14-norms-and-distances/docs/zh.md)：所有聚类算法都建立在距离之上。
- [阶段 01 · 06 概率与分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：高斯分布、最大似然，是 GMM/EM 的基础。
- [阶段 02 · 06 K-最近邻和距离](../../06-knn-and-distances/docs/zh.md)：邻域、`eps` 半径查询、维度灾难、特征缩放。

### 本节被哪些后续内容用到
- [阶段 01 · 10 降维](../../../01-math-foundations/10-dimensionality-reduction/docs/zh.md)：PCA / t-SNE / UMAP 常与聚类搭配做可视化和预处理。
- [阶段 02 · 08 Feature 工程与选择](../../08-feature-engineering/docs/zh.md)：聚类结果（簇编号、到中心的距离）本身可以作为新特征。
- [阶段 02 · 13 机器学习管道](../../13-ml-pipelines/docs/zh.md)：把缩放与聚类封装进管道，保证新数据走同样的预处理。
- [阶段 02 · 16 异常检测](../../16-anomaly-detection/docs/zh.md)：DBSCAN 噪声点、GMM 低概率点，以及 LOF、Isolation Forest 等方法。
- [阶段 05 · 15 主题模型](../../../05-nlp-foundations-to-advanced/15-topic-modeling/docs/zh.md)：文本上的"无监督发现结构"。
- [阶段 11 · 04 Embeddings](../../../11-llm-engineering/04-embeddings/docs/zh.md)：对 embedding 做聚类是主题发现、去重、数据分析的常用手段。

### 延伸关键词
`K-Means++` · `Mini-Batch K-Means` · `K-Medoids` · `HDBSCAN` · `OPTICS` · `BIC / AIC` · `Calinski-Harabasz` · `Davies-Bouldin` · `ARI / NMI` · `谱聚类` · `log-sum-exp` · `BERTopic`
