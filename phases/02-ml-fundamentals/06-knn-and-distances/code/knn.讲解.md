# 代码讲解 · knn.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 06 节 K-最近邻和距离 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python knn.py`（无命令行参数，约 2–3 秒跑完 10 个演示） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`time`），无需 NumPy / scikit-learn

---

## 1. 这份代码在考察什么

1. **KNN 的完整机制**：没有训练、没有参数，预测时"算距离 → 排序 → 取前 K → 投票/平均"，以及距离加权的变体。
2. **距离度量的差异**：L1、L2、余弦、Minkowski 族在同一份数据上会选出不同的邻居。
3. **特征缩放的必要性**：年龄 vs 年薪的例子，直观展示"大数值特征主导距离"。
4. **维度灾难**：用实验测量"随维度增加，最远/最近距离比趋近 1"，以及噪声维度如何拖垮准确率。
5. **加速结构**：从零实现 KD-tree（中位数切分 + 回溯剪枝），与暴力搜索对比速度并验证结果一致。
6. **工程流程**：手写 5 折交叉验证选 K；惰性学习"训练快、预测慢"的计时验证。

> 一句话：**KNN 是"向量检索"的最小原型**——今天的向量数据库、RAG 检索、推荐召回，做的都是同一件事，只是规模和索引结构不同。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `l2_distance` / `l1_distance` / `cosine_distance` / `minkowski_distance` | 函数 | 四种距离 | 距离度量 |
| `standardize` / `apply_standardize` | 函数 | 计算并应用 z-score 标准化 | 特征缩放、防止数据泄漏 |
| `KNN` | 类 | `fit` / `predict` / `_predict_one` / `_classify` / `_regress` / `predict_with_neighbors` | KNN 分类与回归、加权投票 |
| `KDNode` / `KDTree` | 类 | 构建 KD-tree，`query` 返回 k 个最近邻 | 空间划分、剪枝搜索 |
| `accuracy` / `mse` | 函数 | 分类 / 回归评估指标 | — |
| `generate_classification_data` / `generate_regression_data` / `generate_high_dim_data` | 函数 | 三簇分类数据、`sin(x)` 回归数据、高维（仅前 2 维有信号）数据 | — |
| `train_test_split` | 函数 | 随机切分训练/测试集 | — |
| `demo_*` × 10 | 函数 | 十个演示实验 | 见第 3、6 节 |
| `print_summary` + `__main__` | 入口 | 依次执行所有演示并打印总结 | — |

数据流：`generate_*` → （可选）`standardize` → `train_test_split` → `KNN.fit` 存数据 → `KNN.predict` 对每个 query 调 `_predict_one`（暴力算距离、排序、取前 K）→ `_classify` / `_regress`。`KDTree` 是独立的一套查询结构，只在 `demo_kdtree` 中与暴力搜索对比，没有接入 `KNN` 类。

---

## 3. 逐段精讲

### 3.1 四种距离函数

```python
def l2_distance(a, b):
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))

def l1_distance(a, b):
    return sum(abs(ai - bi) for ai, bi in zip(a, b))

def cosine_distance(a, b):
    dot_val = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = math.sqrt(sum(ai ** 2 for ai in a))
    norm_b = math.sqrt(sum(bi ** 2 for bi in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - dot_val / (norm_a * norm_b)

def minkowski_distance(a, b, p=2):
    if p == float("inf"):
        return max(abs(ai - bi) for ai, bi in zip(a, b))
    return sum(abs(ai - bi) ** p for ai, bi in zip(a, b)) ** (1 / p)
```

| 函数 | 公式 | 特点 |
|------|------|------|
| `l2_distance` | `√Σ(aᵢ−bᵢ)²` | 默认选择；平方会放大大差值，对离群点敏感 |
| `l1_distance` | `Σ|aᵢ−bᵢ|` | 不平方，对离群点更稳 |
| `cosine_distance` | `1 − a·b/(‖a‖‖b‖)` | 只看方向，取值 [0, 2]；文本、embedding 首选 |
| `minkowski_distance` | `(Σ|aᵢ−bᵢ|^p)^(1/p)` | p=1 即 L1，p=2 即 L2，p→∞ 即切比雪夫距离 `max|aᵢ−bᵢ|` |

- **零向量保护**：零向量没有方向，余弦无定义；代码约定返回 `1.0`（相当于"正交/不相关"），避免 `ZeroDivisionError`。
- **p = ∞ 单独处理**：如果直接代入通用公式，`3.0 ** float("inf")` 得到 `inf`，再开 `1/inf = 0` 次方得到 `1.0`——一个毫无意义的结果（实测 `[1,2,3]` 与 `[4,0,6]` 会算出 1.0 而不是 3.0）。所以要用 `max` 显式实现切比雪夫距离。`float("inf")` 是 Python 表示无穷大的标准写法。
- ⚠️ 余弦距离不满足三角不等式，严格说不是"度量"。这对暴力 KNN 没影响，但不能直接用于依赖度量性质的树索引。本文件的 `KDTree` 也只支持 L2。

### 3.2 标准化：`standardize` 与 `apply_standardize`

```python
def standardize(X):
    n = len(X)
    d = len(X[0])
    means = [sum(X[i][j] for i in range(n)) / n for j in range(d)]
    stds = [
        max(
            1e-10,
            (sum((X[i][j] - means[j]) ** 2 for i in range(n)) / n) ** 0.5,
        )
        for j in range(d)
    ]
    X_scaled = [
        [(X[i][j] - means[j]) / stds[j] for j in range(d)] for i in range(n)
    ]
    return X_scaled, means, stds

def apply_standardize(X, means, stds):
    return [[(x[j] - means[j]) / stds[j] for j in range(len(x))] for x in X]
```

- 按**列**计算均值和（总体）标准差，再做 `z = (x − μ)/σ`，把每个特征变成均值 0、标准差 1，让各特征对距离的贡献可比。
- `max(1e-10, σ)`：常数列的 σ = 0，直接除会报错；用一个极小的下限兜底。
- **为什么要返回 `means, stds`**：这样才能用**训练集的统计量**去变换测试集（`apply_standardize`），这是 sklearn `fit` / `transform` 分离的同一思想。
- ⚠️ 代码中的不一致：`demo_distance_metrics`、`demo_weighted_knn`、维度灾难第二部分都是**先对全量数据 `standardize` 再切分**，测试集的统计信息泄漏进了训练；只有 `demo_scaling_importance` 用了正确流程（先切分，再 `standardize(X_train)` + `apply_standardize(X_test, ...)`）。演示数据量小、分布一致，所以影响不大，但实际项目中要按后者做。

### 3.3 `KNN` 类：存数据与暴力预测

```python
class KNN:
    def __init__(self, k=5, distance_fn=l2_distance, weighted=False,
                 task="classification"):
        self.k = k
        self.distance_fn = distance_fn
        self.weighted = weighted
        self.task = task
        # ...

    def fit(self, X, y):
        self.X_train = list(X)
        self.y_train = list(y)

    def predict(self, X):
        return [self._predict_one(x) for x in X]

    def _predict_one(self, x):
        distances = []
        for i in range(len(self.X_train)):
            d = self.distance_fn(x, self.X_train[i])
            distances.append((d, self.y_train[i]))
        distances.sort(key=lambda pair: pair[0])
        neighbors = distances[: self.k]

        if self.task == "classification":
            return self._classify(neighbors)
        return self._regress(neighbors)
```

- **`fit` 只有两行**：这就是"惰性学习"——没有任何优化，只拷贝一份数据（`list(X)` 是浅拷贝，外部列表被替换不影响模型，但内层特征向量仍是同一对象）。
- **距离函数作为参数注入**：`distance_fn=l2_distance` 默认 L2，换度量只需传入另一个函数（策略模式），`demo_distance_metrics` 就是这样对比三种度量的。
- **`_predict_one` 的三步**：算 n 个距离（`O(n·d)`）→ 按距离排序（`O(n log n)`）→ 切片取前 k 个。用 `(距离, 标签)` 元组存储，排序时用 `key=lambda pair: pair[0]` 只按距离排；`list.sort` 是稳定排序，距离相同的点保持原训练集顺序。
- `task` 字符串决定走分类还是回归分支：同一个类同时支持两种任务。
- ⚠️ 简化：只需要前 k 个却对全部 n 个排序；用 `heapq.nsmallest(k, ...)` 可降到 `O(n log k)`（见测验 Q12）。生产中用 NumPy 向量化一次性算出所有距离，或者用 KD-tree / ANN 索引。

### 3.4 投票与加权：`_classify` 和 `_regress`

```python
    def _classify(self, neighbors):
        if self.weighted:
            votes = {}
            for dist, label in neighbors:
                w = 1.0 / (dist + 1e-10)
                votes[label] = votes.get(label, 0) + w
        else:
            votes = {}
            for _, label in neighbors:
                votes[label] = votes.get(label, 0) + 1
        return max(votes, key=votes.get)

    def _regress(self, neighbors):
        if self.weighted:
            w_sum = 0.0
            val_sum = 0.0
            for dist, val in neighbors:
                w = 1.0 / (dist + 1e-10)
                val_sum += w * val
                w_sum += w
            return val_sum / w_sum if w_sum > 0 else 0.0
        return sum(val for _, val in neighbors) / len(neighbors)
```

- **分类**：用字典计票。`votes.get(label, 0)` 在标签第一次出现时返回默认值 0，是计数的惯用写法（等价于 `collections.Counter`）。`max(votes, key=votes.get)` 返回票数最多的**键**。
- **平票规则（隐式）**：`max` 遇到并列最大值时返回迭代中的第一个；Python 3.7+ 的 dict 按插入顺序迭代，而插入顺序就是邻居按距离由近到远出现的顺序。所以平票时，"最近成员离 query 更近"的类别获胜。这是一个合理但未写明的行为。
- **加权**：`w = 1/(d + 1e-10)`，对应讲义 `weight_i = 1 / (distance_i + epsilon)`。query 恰好与某个训练点重合时 `w ≈ 1e10`，该点几乎独占决定权。
- **回归**：不加权时是 K 个目标值的算术平均；加权时是 `Σwᵢyᵢ / Σwᵢ`。两者都是训练目标值的凸组合，所以预测永远落在训练目标的取值范围内——讲义说的"KNN 回归无法外推"。
- `if w_sum > 0 else 0.0`：防御式写法，正常情况下权重恒为正，这个分支不会触发。

### 3.5 `predict_with_neighbors`：可解释性接口

```python
    def predict_with_neighbors(self, x):
        distances = []
        for i in range(len(self.X_train)):
            d = self.distance_fn(x, self.X_train[i])
            distances.append((d, i, self.y_train[i]))
        distances.sort(key=lambda t: t[0])
        neighbors = distances[: self.k]
        prediction = self._predict_one(x)
        return prediction, neighbors
```

- 除了预测结果，还返回 `(距离, 训练集下标, 标签)` 三元组——这是 KNN 天然的**可解释性**：可以直接告诉用户"因为你和这 5 个样本最像"。RAG 里返回"引用来源"也是同样的思路。
- ⚠️ 距离被算了两遍（自己算一遍，`_predict_one` 再算一遍），演示用无所谓，工程上应复用。

### 3.6 KD-tree 的构建

```python
class KDTree:
    def __init__(self, X):
        self.dim = len(X[0])
        indexed = [(X[i], i) for i in range(len(X))]
        self.root = self._build(indexed, depth=0)

    def _build(self, points, depth):
        if not points:
            return None
        axis = depth % self.dim
        points.sort(key=lambda p: p[0][axis])
        mid = len(points) // 2
        return KDNode(
            point=points[mid][0],
            index=points[mid][1],
            axis=axis,
            left=self._build(points[:mid], depth + 1),
            right=self._build(points[mid + 1 :], depth + 1),
        )
```

- **轮流选轴**：`axis = depth % self.dim`，第 0 层按 x 切、第 1 层按 y 切、第 2 层又按 x 切……（2D 情形）。
- **中位数切分**：按当前轴排序后取中间点作为节点，左边是该轴坐标较小的一半，右边是较大的一半，保证树大致平衡、深度约 `log₂ n`。
- 与讲义 mermaid 图的区别：讲义画的是"叶子里放多个点"的版本；这里**每个节点本身存一个点**，没有单独的叶子桶，实现更简洁。
- 每层都要排序，建树复杂度约 `O(n log² n)`；用线性时间选中位数（quickselect）可降到 `O(n log n)`。
- `(X[i], i)` 把原始下标一起存进树里，查询结果才能和暴力搜索的下标对上。

### 3.7 KD-tree 的查询：下探 + 回溯剪枝

```python
    def _search(self, node, point, k, best):
        if node is None:
            return

        dist = l2_distance(point, node.point)

        if len(best) < k:
            best.append((dist, node.index, node.point))
            best.sort(key=lambda x: x[0])
        elif dist < best[-1][0]:
            best[-1] = (dist, node.index, node.point)
            best.sort(key=lambda x: x[0])

        axis = node.axis
        diff = point[axis] - node.point[axis]

        if diff <= 0:
            first, second = node.left, node.right
        else:
            first, second = node.right, node.left

        self._search(first, point, k, best)

        if len(best) < k or abs(diff) < best[-1][0]:
            self._search(second, point, k, best)
```

逐步拆解：

1. **维护候选集 `best`**：一个按距离升序的列表，最多 k 个元素，`best[-1]` 是当前第 k 近（最远的候选）。未满就直接加入；已满且新点更近就替换掉最远的那个。
2. **先走 query 所在的一侧**（`first`）：`diff ≤ 0` 说明 query 在切分面左边，先搜左子树。这一路下去通常很快就能找到不错的候选，从而让后续剪枝更有效。
3. **回溯时决定是否搜另一侧**（`second`）：`|diff|` 是 query 到切分超平面的距离，也就是另一侧任何点到 query 的距离下界。只有当这个下界**小于**当前第 k 近距离时，另一侧才可能有更近的点。
4. `len(best) < k` 这一条件保证候选没凑满时一定继续搜，否则可能返回不足 k 个结果。

- `best` 列表作为参数在递归中**原地修改**（可变对象传引用），所有递归层共享同一个候选集，不需要返回值。
- 为什么高维会失效：维度高时，以 query 为球心、`best[-1][0]` 为半径的球几乎会穿过所有切分面，`abs(diff) < best[-1][0]` 几乎总是成立，剪枝形同虚设。
- ⚠️ 简化：每次插入都对 `best` 排序（k 很小时没问题，k 大时应改用堆）；距离写死为 `l2_distance`。

### 3.8 维度灾难实验

```python
    for d in dims:
        random.seed(42)
        points = [[random.uniform(0, 1) for _ in range(d)] for _ in range(n_points)]

        distances = []
        sample_size = min(500, n_points * (n_points - 1) // 2)
        for _ in range(sample_size):
            i = random.randint(0, n_points - 1)
            j = random.randint(0, n_points - 1)
            if i != j:
                distances.append(l2_distance(points[i], points[j]))
        # ...
            ratio = max_d / min_d if min_d > 0 else float("inf")
```

- **第一部分**：在 `[0,1]^d` 中撒 200 个点，随机抽约 500 对（`i == j` 的被跳过）计算距离，统计最大/最小距离比、均值和标准差。抽样而不是计算全部 19,900 对，是为了控制纯 Python 的耗时。
- 理论上均匀分布时平均距离约 `√(d/6)`（每一维差值平方的期望是 1/6），标准差趋于一个常数，所以"相对波动"按 `1/√d` 缩小。
- **第二部分**：`generate_high_dim_data` 的标签只由前两维决定（`x[0] + x[1] > 1`），其余维度是纯噪声。随着噪声维增多，邻居越来越由噪声决定，准确率下降。
- 注意 `for d in dims` 里的变量名 `d` 与内层 `d_val` 区分开：作者刻意用 `d_val` 避免覆盖外层的维度变量。

### 3.9 手写 K 折交叉验证选 K：`demo_k_selection`

```python
    n_folds = 5
    fold_size = n // n_folds
    # ...
        for fold in range(n_folds):
            val_start = fold * fold_size
            val_end = val_start + fold_size
            val_idx = indices[val_start:val_end]
            train_idx = indices[:val_start] + indices[val_end:]
        # ...
        if mean_acc > best_mean:
            best_mean = mean_acc
            best_k = k
```

- 先打乱下标一次，再按连续区间切成 5 折：第 `fold` 折作验证集，其余拼接（列表 `+`）作训练集。每个 K 都在完全相同的 5 种划分上评估，比较才公平。
- 同时报告均值和标准差：标准差反映结果在不同划分间的波动，两个 K 的均值差小于标准差时，不应把差异当真。
- `mean_acc > best_mean` 用严格大于：多个 K 并列最优时保留**最先出现（最小）**的 K。本次运行 K=7 与 K=15 都是 0.9667，选了 7。实践中并列时选更大的 K 往往更稳（方差更小），这是可以改进的地方。
- `n // n_folds` 向下取整：样本数不能整除时，末尾多出的几个样本永远不进验证集（本例 300/5 刚好整除）。

### 3.10 其余演示：缩放、计时与 KD-tree 对比

```python
    for _ in range(200):
        age = random.gauss(40, 15)
        salary = random.gauss(50000, 20000)
        label = 1 if age > 45 and salary < 40000 else 0
```

- `demo_scaling_importance`：标签同时依赖年龄与年薪，但未缩放时年薪的数值比年龄大三个数量级，距离几乎只由年薪决定，年龄信息被丢掉。打印的 "Sample distances" 是第一个测试点到**前 5 个训练点**（不是最近的 5 个）的距离，用来对比两种尺度下的数值量级。
- `demo_kdtree`：对每个规模 n，用同样的 100 个随机 query 分别计时暴力搜索与 KD-tree，再在 100 个点上验证两者找到的下标集合一致（`set(...) == set(...)`）。注意计时**不含建树时间**。
- `demo_lazy_vs_eager`：标题虽然写了 eager，但只测了 KNN 自己——`fit` 是微秒级，`predict` 随 n 线性增长。急切学习器的对比只停留在打印文字中。
- 计时用的是 `time.time()`；做性能测量更推荐 `time.perf_counter()`（单调、分辨率更高）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 距离函数作为参数注入 | 换度量不改主逻辑，便于对比实验 | sklearn 用 `metric="euclidean"` 字符串 + 内部向量化实现 |
| 暴力搜索 + 全排序 | 最直观，和讲义五步流程一一对应 | 用 `heapq.nsmallest`、NumPy 向量化、KD-tree / Ball tree / ANN |
| 字典计票 + `max(..., key=...)` | 代码短，支持任意标签类型 | 平票规则是隐式的；生产中应显式定义（如按加权距离再比） |
| `1e-10` 作为 epsilon | 防止距离为 0 时除零 | 也可以直接"若存在距离 0 的点，返回其标签" |
| KD-tree 每节点存一个点 | 实现简单 | 生产实现（如 sklearn）用叶子桶（`leaf_size`）减少递归开销 |
| 维度灾难实验只抽样 500 对 | 纯 Python 计算全部点对太慢 | max/min 比值依赖样本量，抽样越多比值越大 |
| 手写 5 折 CV | 看清 CV 的每一步 | `sklearn.model_selection.cross_val_score` + `Pipeline` |
| 演示中先缩放后切分 | 少写几行代码 | 会造成数据泄漏；应先切分、只在训练集 fit 缩放器 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 生成器表达式 + 内置函数 | `sum(abs(ai - bi) for ai, bi in zip(a, b))`、`max(...)` | 边生成边聚合，不建中间列表 |
| 浮点无穷大 | `float("inf")`、`p == float("inf")` | 表示正无穷，可参与比较 |
| 嵌套列表推导 | `[[(X[i][j] - means[j]) / stds[j] for j in range(d)] for i in range(n)]` | 外层遍历行、内层遍历列 |
| 默认参数为函数 | `distance_fn=l2_distance` | 函数是一等对象，可以作为默认值和参数 |
| 字典计数 | `votes[label] = votes.get(label, 0) + 1` | `get(key, 默认值)` 避免 `KeyError` |
| `max` 的 `key` 参数 | `max(votes, key=votes.get)` | 按值找最大的键；`votes.get` 本身就是一个函数 |
| `sort` + `lambda` | `distances.sort(key=lambda pair: pair[0])` | 按元组第一个元素原地排序；稳定排序 |
| 元组比较 | `dists.sort()`（元素为 `(距离, 下标)`） | 不给 key 时元组逐元素比较：先比距离，相同再比下标 |
| 切片 | `distances[: self.k]`、`points[mid + 1 :]`、`indices[:val_start] + indices[val_end:]` | 取前 k 个、取后半段、拼接两段列表 |
| 条件表达式 | `val_sum / w_sum if w_sum > 0 else 0.0` | 三元表达式 |
| 递归 | `_build` 调用自身构建左右子树；`_search` 递归下探 | 必须有终止条件 `if not points` / `if node is None` |
| 可变对象原地修改 | `best` 列表在递归中被 `append` / 赋值 | 所有递归层共享同一个列表对象 |
| 关键字参数调用 | `KDNode(point=..., index=..., axis=..., left=..., right=...)` | 参数多时提高可读性 |
| 集合比较 | `set(idx for _, idx in brute_top5) == set(...)` | 忽略顺序比较两组下标 |
| 函数内 `import` | `demo_kdtree` 循环体里的 `import time` | 合法（重复 import 只是查缓存），但通常放文件顶部 |
| f-string 格式 | `f"{diff:>+8.4f}"`、`f"{brute_time:>14.4f}s"`、`f"{p_str:>8s}"` | `+` 强制显示正负号；`>14` 右对齐宽度 14 |
| `round` | `round(d, 4)` | 四舍五入到 4 位小数 |

---

## 6. 运行结果解读

实际运行：在临时副本目录执行 `python3 knn.py`，约 2.3 秒完成。时间相关的数字每次运行会略有不同，其余结果固定（随机种子已设置）。

**① K 的影响（三簇数据）**

```text
       K   Train Acc    Test Acc
       1      1.0000      0.9750
       7      0.9688      1.0000
      50      0.9688      1.0000
```

K=1 训练准确率 100%（每个点的最近邻是它自己），测试略低；K 增大后训练准确率下降、测试准确率上升——典型的"降低方差"。数据簇分得很开，所以 K=50 也没有明显欠拟合。

**② 不同度量选出的邻居**

```text
  L2 (Euclidean)                0.9750
  L1 (Manhattan)                1.0000
  Cosine                        0.9750

  Cosine: prediction = 2
    neighbor idx=49, label=2, dist=0.0000
    neighbor idx=26, label=2, dist=0.0000
    neighbor idx=157, label=2, dist=0.0000
```

L1、L2 选出的前 4 个邻居相同，第 5 个不同；余弦选出的邻居集合明显不同（49、157 不在 L2 的前 5 中），而且距离几乎都是 0——在标准化后的 2D 数据里，余弦只看"从原点出发的方向"，同一条射线上远近不同的点都被视为完全相同。这说明**度量决定了"谁是邻居"**。

**③ 加权 vs 不加权（分类）**

```text
       K    Unweighted      Weighted      Diff
       7        1.0000        0.9750   -0.0250
      25        1.0000        1.0000   +0.0000
```

在这份很容易的数据上，加权并没有带来提升（−0.025 只是 40 个测试点中的 1 个）。打印的结论"加权对大 K 更不敏感"在这里看不出来，要看下面的回归实验。

**④ KNN 回归**

```text
       K    Unweighted MSE    Weighted MSE
       1          0.034407        0.034407
       5          0.022037        0.026345
      20          0.035663        0.024588
      50          0.073271        0.026869
```

- K=1 时两者相同（只有一个邻居，权重无关紧要）；不加权在 K=5 附近最好，K=50 时 MSE 翻了 3 倍多——160 个训练点里取 50 个邻居，已经把 `sin` 的波峰波谷抹平了。
- 加权版本的 MSE 在 K=3～50 之间稳定在 0.024～0.029：远处邻居权重小，K 变大也不会被"拉平"。这才是"加权降低对 K 的敏感度"的有力证据。

**⑤ Minkowski 族**

```text
         p      Distance
         1        8.0000
       1.5        5.5912
         2        4.6904
        10        3.2181
       inf        3.0000
```

p 越大距离越小，且向最大分量差 3 收敛，验证了 `L∞ ≤ L2 ≤ L1`。

**⑥ 维度灾难**

```text
    Dimensions    Max/Min dist   Mean dist    Std dist
             2         44.3229      0.5284      0.2495
            20          2.3868      1.7862      0.2366
           100          1.3748      4.0824      0.2400

    Dimensions     K=5 Acc    K=15 Acc
             2      0.9750      0.9750
            20      0.7375      0.7875
            50      0.7500      0.7375
```

- 平均距离按 `√(d/6)` 增长（d=100 时 `√(100/6) ≈ 4.08`，与实测 4.0824 几乎一致），而标准差始终在 0.24 左右，所以 max/min 比值从 44 降到 1.37。
- 讲义给出 "d=100 时 max/min ≈ 1.01" 的示意数字，实测为 1.37——比值确实趋近 1，但收敛速度比讲义描述的慢得多（相对波动按 `1/√d` 衰减），而且该比值还依赖抽样的点对数量。
- 准确率从 2 维的 0.975 掉到 20 维以上的约 0.75：信号只有 2 维，其余全是噪声。

**⑦ 特征缩放**

```text
  Without scaling: accuracy = 0.8750
  With scaling:    accuracy = 0.9500
  Without scaling: [250.5, 8994.0, 14689.1, 15805.4, 39606.8]
  With scaling:    [0.7995, 1.433, 2.1884, 2.4314, 3.9879]
```

未缩放时距离以"元"为量级，基本等于年薪之差；缩放后两个特征共同贡献，准确率提升 7.5 个百分点。

**⑧ KD-tree 与 ⑨ 惰性学习计时**

```text
    N points     Brute force         KD-tree     Speedup
         100          0.0063s          0.0022s         2.9x
        5000          0.3855s          0.0035s       111.6x
    Results match: True

       N     KNN train     KNN predict
     100      0.000002s        0.001683s
    5000      0.000026s        0.378670s
```

- 暴力搜索时间随 n 线性增长；KD-tree 查询时间几乎不变（对数增长），n=5000 时快约 100 倍，且结果与暴力搜索完全一致。
- KNN 的"训练"是微秒级，预测时间随 n 线性增长——惰性学习"把成本挪到预测时"的直接体现。

**⑩ 交叉验证选 K**

```text
       K    Mean Acc     Std Acc
       1      0.9500      0.0211
       7      0.9667      0.0183
      15      0.9667      0.0183
  Best K = 7 with mean accuracy = 0.9667
```

K=3～31 的均值差异都在 1 个标准差以内，说明在这份数据上 K 的选择并不敏感；K=1 明显略差。

---

## 7. 动手改一改

1. 把 `_predict_one` 改用 `heapq.nsmallest`，在 n=5000 上和原版计时对比。
2. 修复数据泄漏：改写 `demo_distance_metrics`，先切分，再用 `standardize(X_train)` + `apply_standardize(X_test, ...)`，观察结果是否变化。
3. 给 `_classify` 加一个显式的平票规则（例如平票时比较各类邻居的平均距离），并写测试验证 `[(0.5,"B"),(1.0,"A"),(1.2,"A"),(2.0,"B")]` 的结果。
4. 给 `KDTree` 加一个计数器统计访问节点数，在 2、5、10、20 维上对比"访问节点数 / n"，找到 KD-tree 退化的维度。
5. 在维度灾难实验中把抽样对数从 500 提高到全部点对，观察 max/min 比值如何变化，理解该指标对样本量的依赖。
6. 让 `demo_k_selection` 在并列时选择更大的 K，并额外输出"一标准差规则"（选均值在最优值一个标准差以内的最大 K）。

---

## 8. 常见坑

- **忘记缩放或在全量数据上缩放**：前者让大数值特征主导距离，后者造成数据泄漏。
- **余弦距离遇到零向量**：除以 0；本实现返回 1.0，自己实现时要记得处理。
- **以为 KD-tree 在高维也快**：几十维以上剪枝失效，可能比暴力搜索还慢（还多了建树和递归开销）。
- **回溯条件写错**：去掉 `len(best) < k` 会导致结果不足 k 个；去掉 `abs` 结果正确但大幅变慢，而且"结果一致"的测试发现不了。
- **平票依赖隐式顺序**：`max(dict, key=dict.get)` 的平票结果取决于插入顺序，换一种实现（比如 `Counter.most_common`）结果可能不同。
- **把演示结论当定理**：`demo_weighted_knn` 的分类结果并不支持"加权更好"；要以具体数字为准，并注意 40 个测试样本中 1 个样本就是 2.5 个百分点。
