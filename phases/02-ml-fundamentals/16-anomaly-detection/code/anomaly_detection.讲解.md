# 代码讲解 · anomaly_detection.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 16 节 异常检测 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python anomaly_detection.py`（无命令行参数，依次运行 5 个演示） ｜ **依赖**：仅 `numpy`（代码中没有 import sklearn）

---

## 1. 这份代码在考察什么

1. **三种检测器的本质**：Z-score（均值 + 标准差）、IQR（分位数围栏）、Isolation Forest（随机切分的路径长度），都输出"标签 + 连续分数"两样东西。
2. **"异常少而不同"如何变成算法**：Isolation Tree 用完全随机的切分，异常点因为处在稀疏区域，路径更短。
3. **分数归一化**：`c(n)` 让路径长度可以跨样本量比较，`2^(−E[h]/c)` 把它映射到 (0, 1)。
4. **阈值与评估**：同一组分数，不同阈值得到不同的 precision / recall；Precision@k 不依赖阈值。
5. **方法的适用边界**：单簇数据上三种方法都很好，三簇数据上逐特征的 Z-score / IQR 几乎失效。

> 一句话：**异常检测 = 给每个点打一个"有多不正常"的分数 + 选一个业务上合理的阈值**，这份代码把这两步都摊开给你看。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `zscore_detect(X, threshold)` | 函数 | 每个特征算 \|z\|，取最大值为分数 | Z-score |
| `iqr_detect(X, factor)` | 函数 | 分位数围栏，超出部分以 IQR 为单位作为分数 | IQR / 箱线图 |
| `_c_factor(n)` | 私有函数 | n 个点的二叉搜索树"不成功查找"的平均路径长度 | 归一化常数 c(n) |
| `IsolationTree` | 类 | 递归随机切分；`path_length` 计算单点的路径长度 | 隔离树 |
| `IsolationForest` | 类 | 子采样 + 多棵树；`anomaly_score` 平均路径并归一化 | 隔离森林 |
| `make_anomaly_data` / `make_multimodal_data` | 函数 | 单簇 + 远处异常；三簇 + 均匀散布的异常 | 演示数据 |
| `precision_recall` / `precision_at_k` | 函数 | 阈值化后的指标；按分数排名取前 k 的精度 | 评估 |
| `demo_*`（5 个） | 演示 | 三种方法的阈值扫描、方法对比、多峰数据 | 讲义 Demo Scenarios |

调用关系：`IsolationForest.fit` 为每棵树抽 ψ 个样本并调用 `IsolationTree.fit`；`anomaly_score` 对每个点、每棵树调用 `path_length`，叶子处再调用 `_c_factor`。所有演示都是"在同一份数据上拟合并打分"的**完全无监督**设定。

---

## 3. 逐段精讲

### 3.1 `zscore_detect`：离均值几个标准差

```python
def zscore_detect(X, threshold=3.0):
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    z = np.abs((X - mean) / std)
    scores = z.max(axis=1)
    labels = scores > threshold
    return labels, scores
```

- 按列（`axis=0`）求均值和标准差，广播后得到每个样本每个特征的 |z|。
- `z.max(axis=1)`：一个点只要**任意一个特征**超标就算异常，分数取各特征 |z| 的最大值。这是讲义说的 "Flags a point if any feature exceeds the threshold"。
- `std[std == 0] = 1.0`：常数列标准差为 0，避免除零。
- 同时返回 `labels` 和 `scores`：标签用于阈值化评估，分数用于排名（Precision@k）和后续选阈值。讲义片段只返回标签，实际代码多返回了分数。
- ⚠️ 均值和标准差是在**包含异常的同一份数据上**估计的，异常会拉偏均值、撑大标准差（masking）。在极端情况下，n 个点里任何一个点的 |z| 都不可能超过 `√(n−1)`——n ≤ 10 时 `threshold=3` 永远报不出异常（测验 Q8）。

### 3.2 `iqr_detect`：箱线图的须线

```python
def iqr_detect(X, factor=1.5):
    q1 = np.percentile(X, 25, axis=0)
    q3 = np.percentile(X, 75, axis=0)
    iqr = q3 - q1
    iqr[iqr == 0] = 1.0
    lower = q1 - factor * iqr
    upper = q3 + factor * iqr
    below = (X - lower) / iqr
    above = (X - upper) / iqr
    scores = np.maximum(-np.minimum(below, 0), np.maximum(above, 0)).max(axis=1)
    labels = ((X < lower) | (X > upper)).any(axis=1)
    return labels, scores
```

- 围栏 `[Q1 − 1.5·IQR, Q3 + 1.5·IQR]` 就是箱线图的须线；分位数不受少数极端值影响，比 Z-score 稳健。
- **分数的构造**稍微绕一点，拆开看：
  - `below = (X − lower)/iqr`：在下界以下时为负数，`-np.minimum(below, 0)` 得到"低于下界多少个 IQR"；在界内时为 0。
  - `above = (X − upper)/iqr`：在上界以上时为正数，`np.maximum(above, 0)` 得到"高于上界多少个 IQR"。
  - 两者逐元素取大，再对特征取最大值。**界内的点分数都是 0**。
- `np.maximum` / `np.minimum` 是**逐元素**比较两个数组（或数组与标量），和对整个数组求最大值的 `.max()` 是两回事。
- 标签用 `|`（逐元素或）和 `.any(axis=1)`：任一特征越界即为异常。注意 `(X < lower) | (X > upper)` 两侧的括号不能省，因为 `|` 的优先级高于 `<`。
- ⚠️ 大量分数并列为 0 会让 Precision@k 失真：在三簇数据上，IQR 给全部 620 个点的分数都是 0，P@k=0.1 只是排序算法对并列元素的处理结果（测验 Q10）。

### 3.3 `_c_factor`：路径长度的"标尺"

```python
def _c_factor(n):
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0
    h = np.log(n - 1) + 0.5772156649
    return 2.0 * h - (2.0 * (n - 1.0) / n)
```

- 公式 `c(n) = 2H(n−1) − 2(n−1)/n`，其中调和数 `H(i) ≈ ln(i) + γ`，`γ ≈ 0.5772` 是欧拉常数。`c(n)` 是 n 个点构成的二叉搜索树中一次"不成功查找"的平均路径长度——可以理解成"一个普通点被隔离所需的期望切分次数"。
- 几个值：`c(2) = 1`，`c(10) ≈ 3.75`，`c(256) ≈ 10.24`，`c(525) ≈ 11.68`。增长是对数级的。
- 小 n 时 `ln(i) + γ` 只是调和数的近似（例如 `H(2) = 1.5`，近似值为 1.27），但 sklearn 内部也用的是同样的近似式，影响可以忽略。
- 函数名前的下划线表示"模块内部使用"：`from anomaly_detection import *` 不会导入它。

### 3.4 `IsolationTree`：完全随机的递归切分

```python
    def fit(self, X, depth=0):
        n, p = X.shape

        if depth >= self.max_depth or n <= 1:
            self.is_leaf = True
            self.size = n
            return self

        self.feature = self.rng.randint(p)
        x_col = X[:, self.feature]
        x_min = x_col.min()
        x_max = x_col.max()

        if x_min == x_max:
            self.is_leaf = True
            self.size = n
            return self

        self.is_leaf = False
        self.threshold = self.rng.uniform(x_min, x_max)

        left_mask = x_col < self.threshold
        right_mask = ~left_mask

        self.left = IsolationTree(self.max_depth, self.rng)
        self.left.fit(X[left_mask], depth + 1)

        self.right = IsolationTree(self.max_depth, self.rng)
        self.right.fit(X[right_mask], depth + 1)

        return self
```

- **三个停止条件**：到达深度上限；只剩 ≤1 个点（已被隔离）；选中的特征在当前节点上是常数，无法切分。
- **随机性**：随机选特征（`randint(p)`），在该特征当前的 [min, max) 内均匀随机选切分点。与决策树不同，这里**没有任何"最优切分"的计算**，也不需要标签——这正是它快的原因。
- 每个节点就是一个 `IsolationTree` 对象，左右子树递归构建，形成一棵**对象树**。`size` 记录叶子中剩余的点数，打分时要用。
- 所有子节点共享同一个 `self.rng`，整棵树的随机序列由创建时传入的生成器决定，因而可复现。
- ⚠️ 选中的特征恰好是常数时直接成为叶子，而不是换一个特征再试；这会让少数节点提前停止，但叶子处补上的 `c(size)` 会对此做出估计补偿。

```python
    def path_length(self, x, depth=0):
        if self.is_leaf:
            return depth + _c_factor(self.size)

        if x[self.feature] < self.threshold:
            return self.left.path_length(x, depth + 1)
        else:
            return self.right.path_length(x, depth + 1)
```

- 对单个点从根走到叶子，每经过一个内部节点深度加 1。
- **到达叶子时加上 `c(size)`**：如果叶子里还有 size 个点没有被隔离，就用"随机继续切下去平均还需要的步数"来估计剩余路径。叶子里点越多，说明区域越稠密，路径越长、越正常。这是原论文中路径长度 `h(x) = e + c(T.size)` 的做法。

### 3.5 `IsolationForest`：子采样 + 平均 + 归一化

```python
    def fit(self, X):
        self.n_train = X.shape[0]
        rng = np.random.RandomState(self.seed)
        self.trees = []

        sample_size = min(self.max_samples, X.shape[0])
        max_depth = int(np.ceil(np.log2(sample_size)))

        for _ in range(self.n_estimators):
            idx = rng.choice(X.shape[0], size=sample_size, replace=False)
            tree_rng = np.random.RandomState(rng.randint(0, 2**31))
            tree = IsolationTree(max_depth=max_depth, rng=tree_rng)
            tree.fit(X[idx])
            self.trees.append(tree)

        return self
```

- **子采样**：每棵树只用 ψ = min(256, n) 个点（无放回抽样）。树小、建得快，而且原论文指出，子样本中异常更稀疏，能缓解 masking（异常扎堆互相掩护）和 swamping（正常点被误判）。
- **深度上限** `⌈log₂ψ⌉`（ψ=256 时为 8）：大约是平衡二叉树的高度。我们只关心路径**短**的点，超过这个深度的点反正是正常的，不必再切。
- **随机数管理**：一个主生成器负责抽子样本，并为每棵树生成一个独立的种子 `rng.randint(0, 2**31)`。同一个 `seed` → 完全相同的森林。
- `fit` 返回 `self`，可以链式调用 `IsolationForest(...).fit(X).anomaly_score(X)`。

```python
    def anomaly_score(self, X):
        n = X.shape[0]
        avg_path = np.zeros(n)

        for tree in self.trees:
            for i in range(n):
                avg_path[i] += tree.path_length(X[i])

        avg_path /= self.n_estimators
        sample_size = min(self.max_samples, self.n_train)
        c = _c_factor(sample_size)
        scores = 2.0 ** (-avg_path / c) if c > 0 else np.zeros(n)

        return scores
```

- 先对所有树求平均路径长度 `E[h(x)]`，再计算 `s = 2^(−E[h]/c(ψ))`：路径等于 `c(ψ)` 时分数为 0.5；路径越短越接近 1；越长越接近 0。
- 归一化用的是**子样本大小** ψ 对应的 `c(ψ)`，而不是训练集大小，因为每棵树只见过 ψ 个点。
- `if c > 0 else np.zeros(n)`：训练集只有 1 个点时 `c = 0`，防止除零。
- ⚠️ 双重 Python 循环（树 × 样本，每次再递归若干层），复杂度 O(T·n·depth) 次 Python 函数调用。几百个点没问题（整个脚本不到 1 秒），几十万个点就会很慢；生产实现会把树存成数组并批量遍历。
- `predict(X, threshold=0.5)` 只是对分数做阈值化；演示中实际使用的阈值是 0.6。

### 3.6 造数据：单簇与三簇

```python
    center = rng.uniform(-2, 2, n_features)
    cov = np.eye(n_features) * 0.5
    X_normal = rng.multivariate_normal(center, cov, n_normal)

    X_anomaly = rng.uniform(
        X_normal.min(axis=0) - 3,
        X_normal.max(axis=0) + 3,
        (n_anomaly * 3, n_features),
    )
    distances = np.linalg.norm(X_anomaly - center, axis=1)
    far_enough = distances > 3.0
    X_anomaly = X_anomaly[far_enough][:n_anomaly]
```

- `make_anomaly_data`：正常点来自方差 0.5（标准差约 0.71）的二维高斯；异常点在正常点范围外扩 3 的方框内均匀抽样，只保留距中心超过 3（约 4.2 个标准差）的点。先多抽 3 倍再过滤，不够时再补。
- `make_multimodal_data`：三个形状、方向不同的高斯簇（协方差中的 ±0.1 让簇略微倾斜），加上在 `[−6, 8]²` 内均匀撒的 20 个异常。
- ⚠️ 三簇数据中的"异常"是均匀撒的，没有过滤距离：实测有几个异常点离某个簇中心只有 1.3–1.8（约 2 个簇内标准差），它们与正常点几乎无法区分。所以任何方法在这份数据上都不可能拿满分，这也更接近真实情况。

### 3.7 评估函数

```python
def precision_at_k(y_true, scores, k):
    top_k_idx = np.argsort(scores)[-k:]
    return np.mean(y_true[top_k_idx] == 1)
```

- `np.argsort` 升序排列，`[-k:]` 取分数最高的 k 个下标，再看其中真异常的比例。演示中令 k = 真实异常数，此时 P@k 也等于 R-precision。
- ⚠️ 两个边界问题：`k=0` 时 `[-0:]` 等于 `[0:]`，会取到整个数组；分数大量并列时结果取决于排序顺序（测验 Q10 给出了修正版）。
- `precision_recall` 用布尔运算 `(y_true == 1) & (y_pred == 1)` 统计 TP/FP/FN，并对分母为 0 的情况返回 0.0。

### 3.8 演示：阈值扫描与多峰数据

```python
    for name, pred, scores in [
        ("Z-score (t=3.0)", z_pred, z_scores),
        ("IQR (f=1.5)", iqr_pred, iqr_scores),
        ("IsoForest (t=0.6)", iso_pred, iso_scores),
    ]:
        prec, rec, f1 = precision_recall(y_true, pred)
        pak = precision_at_k(y_true, scores, n_anomalies)
```

- `demo_zscore` / `demo_iqr` / `demo_isolation_forest` 分别扫描阈值（2.0–4.0、1.0–3.0、0.50–0.70），打印 precision / recall / F1 / 标记数，直观展示"阈值越严，precision 越高、recall 越低"。
- `demo_comparison` 和 `demo_multimodal` 用一个三元组列表循环比较三种方法，同时报告阈值化指标和不依赖阈值的 P@k。
- ⚠️ 阈值是在**同一份带标签的数据**上扫描并挑选的，挑出来的"最佳阈值"天然偏乐观；真实场景中应当在验证集上选阈值，再在独立数据上报告结果。

> ⚠️ 讲义与代码的差异：讲义说代码会"与 sklearn 对比"，并描述了第 3 个场景"50 维、异常只在 5 个特征上不同"，但实际代码中**既没有 sklearn 对比，也没有高维场景**，LOF 也只在讲义中出现。第 7 部分把这些列为练习。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 检测器同时返回标签和分数 | 分数可以排名、换阈值、做集成 | 无 |
| 多特征时取 max | 任一特征异常即报警，简单可解释 | 无法发现组合异常；可改用马氏距离或多元方法 |
| 在同一份数据上拟合并打分 | 模拟完全无监督的设定 | 异常污染统计量；有干净数据时应只在正常数据上拟合（半监督） |
| IsolationTree 用对象 + 递归 | 结构直观，与算法描述一一对应 | 递归和 Python 循环慢；sklearn 基于数组化的树实现 |
| 每棵树独立种子 | 可复现，且树之间相互独立 | 无 |
| 子采样 256 + 深度上限 | 速度快，并缓解 masking / swamping | ψ 太小时会丢失细节；ψ 可作为超参数调节 |
| 叶子处补 `c(size)` | 深度截断后仍能区分稠密与稀疏的叶子 | 无 |
| 阈值写死在演示里 | 便于展示 | 应按误报/漏报成本或审核容量（top-k）来定 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 多返回值（元组） | `return labels, scores`；`y_pred, _ = zscore_detect(...)` | 返回多个值，用 `_` 忽略不需要的那个 |
| 下划线开头的"私有"函数 | `_c_factor` | 约定为模块内部使用，`import *` 不会导入 |
| 可选参数默认 `None` | `rng=None`，`self.rng = rng if rng is not None else np.random.RandomState()` | 不要把可变对象（如生成器）直接写成默认值；用 `is not None` 判断 |
| 递归 | `self.left.fit(X[left_mask], depth + 1)`、`self.right.path_length(x, depth + 1)` | 函数调用自身，每层把深度加 1 |
| 对象树 | `self.left = IsolationTree(...)` | 每个节点是一个对象，引用左右子节点 |
| 返回 `self` | `return self` | 支持链式调用 |
| `np.percentile` | `np.percentile(X, 25, axis=0)` | 按列求分位数（默认线性插值） |
| 逐元素最值 | `np.maximum(a, b)`、`np.minimum(below, 0)` | 两个数组逐元素比较，不同于 `.max()` |
| 布尔数组运算 | `(X < lower) \| (X > upper)`、`(y_true == 1) & (y_pred == 1)` | 用 `\|` `&` `~`，不能用 `or` `and` `not`；两侧要加括号 |
| `.any(axis=1)` | `((X < lower) \| (X > upper)).any(axis=1)` | 每行只要有一个 True |
| 布尔数组求和 | `y_pred.sum()`、`(y_true == 1).sum()` | True 计为 1，直接得到计数 |
| `np.argsort` + 负切片 | `np.argsort(scores)[-k:]` | 升序排序后取最后 k 个；注意 `k=0` 的陷阱 |
| 无放回抽样 | `rng.choice(X.shape[0], size=sample_size, replace=False)` | 从 0..n−1 中抽不重复的下标 |
| 向上取整 + 对数 | `int(np.ceil(np.log2(sample_size)))` | 树的深度上限 |
| `np.linalg.norm(axis=1)` | `np.linalg.norm(X_anomaly - center, axis=1)` | 每行的欧氏长度 |
| 条件表达式 | `2.0 ** (-avg_path / c) if c > 0 else np.zeros(n)` | 一行 if/else，防除零 |
| 遍历元组列表并解包 | `for name, pred, scores in [(...), (...), (...)]` | 一次拿到三个值 |
| f-string 对齐 | `f"{name:<20}"`、`f"{prec:>10.4f}"` | `<` 左对齐、`>` 右对齐，宽度与小数位 |

---

## 6. 运行结果解读

实际运行（约 0.9 秒）：

```text
Z-SCORE ANOMALY DETECTION            (525 samples, 25 anomalies)
 Threshold  Precision     Recall         F1    Flagged
       2.0     0.8929     1.0000     0.9434         28
       3.0     1.0000     1.0000     1.0000         25     ← 恰好全对
       4.0     1.0000     0.5200     0.6842         13

IQR ANOMALY DETECTION
    Factor  Precision     Recall         F1    Flagged
       1.0     0.4167     1.0000     0.5882         60
       1.5     0.8065     1.0000     0.8929         31     ← 默认 1.5 多报了 6 个
       2.5     1.0000     1.0000     1.0000         25

ISOLATION FOREST (FROM SCRATCH)
  Normal points: mean=0.4056, std=0.0419
  Anomaly points: mean=0.7141, std=0.0382                 ← 两组分数几乎不重叠
      0.50     0.5556     1.0000     0.7143         45
      0.60     0.9615     1.0000     0.9804         26
      0.70     1.0000     0.7200     0.8372         18
Precision@25: 1.0000

METHOD COMPARISON
  Z-score / IQR / Isolation Forest  Precision@25 都是 1.0000

MULTIMODAL DATA (WHERE SIMPLE METHODS STRUGGLE)   (620 samples, 20 anomalies, 3 clusters)
Method                Precision     Recall         F1        P@k
Z-score (t=3.0)          1.0000     0.1000     0.1818     0.5000
IQR (f=1.5)              0.0000     0.0000     0.0000     0.1000
IsoForest (t=0.6)        0.7778     0.7000     0.7368     0.7500
```

解读要点：

- **阈值扫描体现了 precision / recall 的权衡**：每个方法都是阈值越松、标记越多、recall 越高、precision 越低。Z-score 在 3.0、IQR 在 2.5、Isolation Forest 在 0.6 附近达到最佳 F1——但这些"最佳"是在同一份带标签数据上挑出来的，偏乐观。
- **单簇数据太友好**：异常点被刻意放在 4 个标准差以外，三种方法的 P@25 都是满分，区分不出优劣。
- **Isolation Forest 的分数分布**：正常点约 0.41（小于 0.5，"很正常"），异常点约 0.71（接近 1，"很异常"），两者的标准差都只有 0.04 左右，这就是为什么在 0.55–0.65 之间的阈值都能得到很好的效果。
- **三簇数据揭示了逐特征方法的局限**：
  - 三个簇使每个特征的整体分布变宽（多峰），夹在簇之间的异常在每个特征上都处于"正常范围"内。Z-score 只抓到 2 个（recall 0.10），而且其 AUROC 约 0.80、AUPRC 约 0.55（另行计算）；
  - IQR 的围栏被三个簇撑得很宽，**没有任何点越界**，所有分数都是 0，P@k=0.1 只是并列排序的偶然结果（AUROC 恰好 0.5）；
  - Isolation Forest 在二维联合空间中切分，簇之间的稀疏区域很快被隔离，recall 达到 0.70，AUROC 约 0.99。剩下漏掉的主要是离某个簇很近、本来就几乎无法区分的"异常"。
- **与 sklearn 的一致性**（运行脚本之外另行验证）：在同样的两份数据上，用 `sklearn.ensemble.IsolationForest(n_estimators=100, max_samples=256, random_state=42)` 的 `-score_samples` 与本实现的分数做比较，相关系数分别为 0.992 和 0.984，AUPRC 在三簇数据上同为约 0.837。两者的随机切分序列不同，分数不会逐点相等，但排序能力一致。

---

## 7. 动手改一改

1. **稳健 Z-score**：用中位数和 MAD 替换均值和标准差（`0.6745·|x − median| / MAD`，阈值 3.5），在测验 Q11 的污染数据上对比召回率（普通 Z-score 0.09 vs 稳健版 1.00）。
2. **半监督设定**：把 `zscore_detect` 拆成 `fit(X_normal)` 和 `score(X)` 两步，只在正常样本的训练部分上估计统计量，再对测试集打分，观察 masking 是否消失。
3. **补上讲义中的高维场景**：生成 50 维数据，异常只在其中 5 个特征上偏移，比较三种方法的 P@k，并观察 Isolation Forest 的效果是否随无关特征增多而下降。
4. **从零实现 LOF**：计算 k 近邻、可达距离、局部可达密度（lrd）和 LOF 值，在三簇数据上与 Isolation Forest 比较；分别尝试 k=10 和 k=50。
5. **向量化打分**：把每棵树的节点存成数组（特征、阈值、左右子节点下标、叶子大小），对一批样本同时向下遍历，去掉 `anomaly_score` 中的双重 Python 循环，对比 1 万个样本时的耗时。
6. **修复 `precision_at_k`**：检查 `k > 0`，并在并列跨越第 k 名边界时给出警告，在三簇数据上重新报告 IQR 的结果。

---

## 8. 常见坑

- **统计量被异常污染**：在含异常的数据上估计均值/标准差，异常会掩护自己和其他异常（masking）；小样本时 Z-score 的最大可能值只有 `√(n−1)`。
- **逐特征方法看不到组合异常**：多峰数据、相关特征上，Z-score / IQR 会大面积漏检。
- **混淆 `np.maximum` 与 `np.max`**：前者逐元素比较两个数组，后者对一个数组求最大值。
- **布尔运算忘加括号或用了 `and`/`or`**：`X < a | X > b` 会先计算 `a | X`；NumPy 数组之间要用 `&` `|` `~`。
- **`argsort(...)[-k:]` 在 k=0 时取到整个数组**；分数大量并列时 P@k 毫无意义。
- **在评估数据上挑阈值再报告指标**：等同于在测试集上调参，结果偏乐观。
- **Isolation Forest 的归一化用错 n**：应使用子样本大小 ψ 对应的 `c(ψ)`，而不是训练集大小。
