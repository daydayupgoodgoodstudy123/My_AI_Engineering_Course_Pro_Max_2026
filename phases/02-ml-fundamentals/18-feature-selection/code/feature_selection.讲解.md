# 代码讲解 · feature_selection.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 18 节 Feature 选择 ｜ 讲义：[../docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python feature_selection.py`（无命令行参数，约 8 秒，其中树重要性占 7 秒多） ｜ **依赖**：仅 `numpy`（不需要 scikit-learn）

---

## 1. 这份代码在考察什么

这份脚本在一个"**答案已知**"的合成数据集上，从零实现并横向对比五种特征选择方法：

1. **Filter 方法**：方差阈值（只看特征自身）、互信息（看特征与目标的统计依赖，能捕捉非线性）。
2. **Wrapper 方法**：RFE——反复"训练 → 排序 → 删最差"，用模型自身的权重当重要性。
3. **Embedded 方法**：L1 正则（近端梯度下降 + 软阈值把权重压成 0）、随机森林式的树重要性（累加不纯度下降）。
4. **方法之间的分歧**：用"一致性表"看四种方法各选了哪些特征，理解冗余特征、单变量打分的局限。
5. **选择是否真的有用**：只在训练集上做选择，在留出的测试集上比较"全部特征 vs 选中特征"的准确率。

> 一句话：**每种方法都只是"统计 + 循环"**——方差是 `np.var`，互信息是数列联表，RFE 是训练-排序-删除的 while 循环，L1 是梯度下降加一步软阈值，树重要性是递归地累加分裂增益。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `make_feature_selection_data` | 函数 | 生成 500×20 的数据：5 个信息特征、5 个相关特征、10 个噪声特征 | 已知真相的实验床 |
| `variance_threshold` | 函数 | 计算每列方差，返回 `方差 > 阈值` 的掩码 | Filter：方差阈值 |
| `discretize` / `mutual_information` | 函数 | 等宽分箱，再用列联表计算 I(X;Y) | Filter：互信息 |
| `simple_logistic_importance` | 函数 | 无正则的逻辑回归（批量梯度下降），返回 w, b | RFE 与评估用的基模型 |
| `rfe` | 函数 | 递归删除 `|w|` 最小的特征，返回选中掩码与排名 | Wrapper：RFE |
| `soft_threshold` / `l1_feature_selection` | 函数 | 近端梯度下降求解 L1 逻辑回归，非零权重即选中 | Embedded：Lasso |
| `gini_impurity` / `best_split` | 函数 | Gini 不纯度；在一个特征上找最优切分阈值 | 决策树分裂 |
| `_build_tree_importance` / `tree_importance` | 函数 | 递归建树并累加 "增益 × 样本数"；多棵 bootstrap 树求和并归一化 | Embedded：MDI 重要性 |
| `evaluate_accuracy` | 函数 | 用选中的列训练逻辑回归，返回测试集准确率 | 选择效果验证 |
| `feature_group` / `print_feature_scores` | 函数 | 根据名字标注 INFO/CORR/NOISE；排序打印 | — |
| `if __name__ == "__main__":` | 演示入口 | 切分、标准化、五种方法、一致性表、准确率对比 | — |

数据流：生成数据 → 前 80% 训练 / 后 20% 测试 → **只用训练集**做五种选择（方差、MI、树用原始尺度；RFE、L1 用标准化后的数据）→ 汇总各方法的选择掩码 → `evaluate_accuracy` 在测试集上验证。

---

## 3. 逐段精讲

### 3.1 一个"答案已知"的数据集

```python
    x1 = rng.randn(n_samples)
    x2 = rng.randn(n_samples)
    x3 = rng.randn(n_samples)
    x4 = x1 + 0.1 * rng.randn(n_samples)
    x5 = x2 + 0.1 * rng.randn(n_samples)

    informative = np.column_stack([x1, x2, x3, x4, x5])

    correlated = np.column_stack([
        x1 * 0.9 + 0.1 * rng.randn(n_samples),
        x2 * 0.8 + 0.2 * rng.randn(n_samples),
        x3 * 0.7 + 0.3 * rng.randn(n_samples),
        x1 * 0.5 + x2 * 0.5 + 0.1 * rng.randn(n_samples),
        x2 * 0.6 + x3 * 0.4 + 0.1 * rng.randn(n_samples),
    ])

    noise = rng.randn(n_samples, 10) * 0.5

    X = np.hstack([informative, correlated, noise])
    y = (2 * x1 - 1.5 * x2 + x3 + 0.5 * rng.randn(n_samples) > 0).astype(int)
```

把 20 列的"真实身份"整理成表：

| 列 | 名字 | 实际是什么 | 与 y 的关系 |
|----|------|-----------|------------|
| 0 | `info_0` | x1 | 真信号，系数 2（最强） |
| 1 | `info_1` | x2 | 真信号，系数 -1.5 |
| 2 | `info_2` | x3 | 真信号，系数 1（最弱） |
| 3 | `info_3` | x1 + 小噪声 | x1 的复制品（与 x1 相关系数约 0.995） |
| 4 | `info_4` | x2 + 小噪声 | x2 的复制品 |
| 5–9 | `corr_0`~`corr_4` | x1/x2/x3 的线性组合 + 噪声 | 间接相关，`corr_0` 几乎就是 x1 |
| 10–19 | `noise_0`~`noise_9` | 标准差 0.5 的纯噪声 | 无关 |

- `np.column_stack` 把多个一维数组按**列**拼成二维数组；`np.hstack` 把三块二维数组左右拼接成 500×20。
- `y` 由 `2·x1 − 1.5·x2 + x3 + 噪声 > 0` 决定，再 `.astype(int)` 把布尔转 0/1。本例 y=1 有 254 个、y=0 有 246 个，基本均衡。
- ⚠️ 一个容易忽略的事实：**真正独立的信号源只有 x1、x2、x3 三个**。`info_3`、`info_4`、`corr_0` 等都是复制品，对模型几乎没有增量信息。只能选 5 个时，好的方法应该覆盖三个独立信号，而不是把预算花在复制品上——这是读懂后面结果的关键。

### 3.2 方差阈值

```python
def variance_threshold(X, threshold=0.01):
    variances = np.var(X, axis=0)
    mask = variances > threshold
    return mask, variances
```

- `np.var(X, axis=0)`：沿第 0 轴（样本方向）求方差，得到每个特征一个数。`axis=0` 是"压掉行、保留列"。
- `variances > threshold` 返回布尔掩码，之后可以用 `X[:, mask]` 选列。
- 主程序里是 `variance_threshold(X_train, ...)`，用的是**未标准化**的训练集——标准化后每列方差都是 1，方差阈值就失效了。
- ⚠️ 噪声特征的方差约 0.25（实测 0.22~0.29），远超 0.01，所以一个也删不掉。方差阈值只能清理常数列和近常数列，"必要但不充分"。

### 3.3 互信息：分箱 + 列联表

```python
def discretize(x, n_bins=10):
    min_val, max_val = x.min(), x.max()
    if max_val == min_val:
        return np.zeros_like(x, dtype=int)
    bin_edges = np.linspace(min_val, max_val, n_bins + 1)
    binned = np.digitize(x, bin_edges[1:-1])
    return binned
```

- **等宽分箱**：`np.linspace(min, max, 11)` 产生 11 个等距边界、10 个区间。
- `np.digitize(x, bin_edges[1:-1])` 只用 9 个**内部边界**，返回 0~9 的箱号。如果传完整边界，最大值会被单独分到第 11 个箱（编号 10），最小箱 0 反而永远为空。
- 常数列特判：所有值放进 0 号箱，后面计算出的 MI 恰为 0。

```python
def mutual_information(X, y, n_bins=10):
    n_samples, n_features = X.shape
    mi_scores = np.zeros(n_features)

    y_vals, y_counts = np.unique(y, return_counts=True)
    p_y = y_counts / n_samples

    for f in range(n_features):
        x_binned = discretize(X[:, f], n_bins)
        x_vals, x_counts = np.unique(x_binned, return_counts=True)
        p_x = dict(zip(x_vals, x_counts / n_samples))

        mi = 0.0
        for xv in x_vals:
            for yi, yv in enumerate(y_vals):
                joint_mask = (x_binned == xv) & (y == yv)
                p_xy = np.sum(joint_mask) / n_samples
                if p_xy > 0:
                    mi += p_xy * np.log(p_xy / (p_x[xv] * p_y[yi]))
        mi_scores[f] = mi

    return mi_scores
```

- 逐字对应公式 `I(X;Y) = Σₓ Σᵧ p(x,y)·log(p(x,y) / (p(x)p(y)))`：外层遍历 x 的箱，内层遍历 y 的类别，`joint_mask` 数出同时满足两者的样本，得到联合概率。
- `p_x` 用字典存（键是箱号），`p_y` 用数组存（按 `enumerate` 的下标 `yi` 取）——两种查表方式都演示了。
- `if p_xy > 0`：约定 `0·log 0 = 0`，同时避免 `log(0)` 报警。
- 用 `np.log`（自然对数），单位是 nats；均衡二分类时上界是 `H(Y) = ln 2 ≈ 0.693`。
- ⚠️ **有限样本偏差**：这种"直方图插值"估计对纯噪声也会给出正值，一阶近似约为 `(箱数−1)(类别数−1)/(2N) = 9×1/(2×400) ≈ 0.011`。实测：50 个随机噪声列在本数据上的 MI 平均 0.012，与理论一致。运行结果中 `noise_9` 达到 0.0299，甚至排在真信号 `info_2`（0.0229）之前——单个噪声特征完全可能"碰巧"得分偏高。
- ⚠️ 讲义提到 sklearn 的 `mutual_info_classif` 对连续特征用的是 **k-NN 密度估计**而不是分箱，偏差更小、对箱数不敏感。
- 复杂度：每个特征 O(箱数 × 类别数 × n)，20 个特征只需约 5 毫秒。

### 3.4 RFE：训练 → 排序 → 删最差

```python
def simple_logistic_importance(X, y, lr=0.1, epochs=100):
    n_samples, n_features = X.shape
    w = np.zeros(n_features)
    b = 0.0

    for _ in range(epochs):
        z = X @ w + b
        pred = 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))
        error = pred - y
        w -= lr * (X.T @ error) / n_samples
        b -= lr * np.mean(error)

    return w, b
```

标准的批量梯度下降逻辑回归（无正则）。`np.clip(z, -500, 500)` 防止 `exp` 溢出。名字里的 "importance" 是指：训练完后用 `|w|` 当作特征重要性。

```python
    while len(remaining) > n_features_to_select:
        X_subset = X[:, remaining]
        w, _ = simple_logistic_importance(X_subset, y, lr, epochs)
        importances = np.abs(w)

        least_idx = np.argmin(importances)
        original_idx = remaining[least_idx]
        rankings[original_idx] = rank
        rank -= 1
        remaining.pop(least_idx)
```

- `remaining` 是"还活着的原始列号"列表。`X[:, remaining]` 用列表做花式索引，每轮只取这些列。
- **下标映射**：`least_idx` 是在子集里的位置，必须通过 `remaining[least_idx]` 翻译回原始列号，然后才能 `pop`。顺序反了就会删错特征。
- 为什么每轮都**重训**：重要性是相对的。x1 有三个复制品时，权重被三者分摊；删掉一个，剩下的就会"接盘"变大。逐个删除并重训，才能反映这种相互作用——这也是 RFE 比 Filter "周到"的地方。
- **必须标准化**：`|w|` 的大小依赖特征的量纲。主程序把 `X_scaled_train` 传给 RFE，就是为了让各特征的权重可比。
- ⚠️ 排名编号的瑕疵：`rank` 从 20 开始递减，15 次淘汰分配了 20~6，剩下 5 个统一记为 1，于是**排名 2~5 不存在**（运行输出里 Rank 1 之后直接是 Rank 6）。相对顺序没错，但与 sklearn `RFE.ranking_`（最后淘汰者记 2）的约定不同。修正见测验 Q9。
- ⚠️ 代价：本例 20 → 5 要训练 15 次，每次 200 轮，约 0.09 秒；讲义提到 500 → 10 就要 490 次，可以每轮删一批来加速。

### 3.5 L1：梯度步 + 软阈值

```python
def soft_threshold(w, alpha):
    return np.sign(w) * np.maximum(np.abs(w) - alpha, 0)


def l1_feature_selection(X, y, alpha=0.1, lr=0.01, epochs=500):
    # ...
    for _ in range(epochs):
        z = X @ w + b
        pred = 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))
        error = pred - y

        gradient_w = (X.T @ error) / n_samples
        gradient_b = np.mean(error)

        w -= lr * gradient_w
        w = soft_threshold(w, lr * alpha)
        b -= lr * gradient_b

    selected_mask = np.abs(w) > 1e-6
    return selected_mask, w
```

- 这是**近端梯度下降**（proximal gradient descent，也叫 ISTA）：L1 项 `alpha·Σ|w|` 在 0 处不可导，不能直接求梯度；做法是先对光滑的交叉熵部分走一步梯度，再对结果施加 L1 的"近端算子"——软阈值。
- `soft_threshold`：`|w|` 先减去 `lr·alpha`，小于 0 的截成 0（`np.maximum(..., 0)`），再乘回原符号（`np.sign`）。每步都把所有权重往 0 拉一点，小权重直接归零——**精确零**就是这样来的。普通梯度下降加 `alpha·sign(w)` 的次梯度会在 0 附近来回震荡，很难得到严格的 0。
- 阈值是 `lr * alpha` 而不是 `alpha`：近端步的强度与步长成正比。
- 只惩罚 `w`，不惩罚截距 `b`——截距只是平移决策边界，与特征选择无关。
- `np.abs(w) > 1e-6`：用容差判断非零（软阈值可能产生 `-0.0`，数值上等于 0）。
- ⚠️ **未收敛的问题**：主程序用 `alpha=0.05, lr=0.01, epochs=1000`，总"步长"只有 10，离收敛很远。结果是 8 个非零特征，x1 的三个复制品（`info_0`、`info_3`、`corr_0`）权重几乎相等（0.55、0.55、0.53）——这其实是"从 0 出发的梯度下降把权重平均分给相关特征"的表现，并没有展示讲义所说的"在相关特征中挑一个、其余置零"。实测把训练加到 `lr=0.5, epochs=20000` 后，非零特征降到 5 个（`info_0, info_1, info_2, info_3, corr_1`），更稀疏了，但依然保留了 x1 的两个复制品。结论：**L1 的稀疏性要在充分收敛时才能体现，而且在高度相关的特征之间如何取舍并不稳定。**

### 3.6 Gini 与最优切分

```python
def gini_impurity(y):
    if len(y) == 0:
        return 0.0
    classes, counts = np.unique(y, return_counts=True)
    probs = counts / len(y)
    return 1.0 - np.sum(probs ** 2)
```

`Gini = 1 − Σ pₖ²`：节点越"纯"越接近 0；二分类各占一半时最大，为 0.5。

```python
def best_split(X, y, feature_idx):
    values = np.unique(X[:, feature_idx])
    if len(values) <= 1:
        return None, -1.0
    best_threshold, best_gain = None, -1.0
    parent_gini = gini_impurity(y)
    n = len(y)
    step = max(1, (len(values) - 1) // min(20, len(values) - 1))
    for i in range(0, len(values) - 1, step):
        threshold = (values[i] + values[i + 1]) / 2.0
        left_mask = X[:, feature_idx] <= threshold
        n_left, n_right = np.sum(left_mask), n - np.sum(left_mask)
        if n_left == 0 or n_right == 0:
            continue
        gain = parent_gini - (n_left / n) * gini_impurity(y[left_mask]) - (n_right / n) * gini_impurity(y[~left_mask])
        if gain > best_gain:
            best_gain, best_threshold = gain, threshold
    return best_threshold, best_gain
```

- 候选阈值取**相邻唯一值的中点**，保证切分落在两个观测值之间。
- `gain = 父节点 Gini − 加权子节点 Gini`，即不纯度下降量。
- **与讲义不同之处**：讲义版本遍历全部 `len(values) − 1` 个候选点；代码多了一个 `step`，最多只试约 20 个候选点。例如 400 个唯一值时 `step = 399 // 20 = 19`，只检查 21 个阈值。这是为了速度做的近似（类似直方图算法的思路），代价是可能错过最优切分点。小节点（唯一值少于 21 个）时 `step = 1`，仍然穷举。
- `~left_mask`：布尔数组取反，得到右子节点。

### 3.7 树重要性：递归累加增益

```python
def _build_tree_importance(X, y, feature_subset, max_depth, depth=0):
    n_features = X.shape[1]
    importances = np.zeros(n_features)

    if depth >= max_depth or len(np.unique(y)) <= 1 or len(y) < 4:
        return importances
    # ... 在 feature_subset 中找增益最大的 (best_feature, best_threshold) ...
    if best_feature is None or best_gain <= 0:
        return importances

    importances[best_feature] += best_gain * len(y)

    left_mask = X[:, best_feature] <= best_threshold
    right_mask = ~left_mask

    importances += _build_tree_importance(X[left_mask], y[left_mask], feature_subset, max_depth, depth + 1)
    importances += _build_tree_importance(X[right_mask], y[right_mask], feature_subset, max_depth, depth + 1)

    return importances
```

- 这个函数**并不保存树结构**，只在"建树的过程中"顺手记录每个特征贡献了多少不纯度下降——因为目的只是算重要性。
- 三个停止条件：达到最大深度、节点已纯（只剩一个类别）、样本少于 4 个。
- `best_gain * len(y)`：增益乘以**当前节点的样本数**，即讲义公式中的 `n_samples × impurity_decrease`。靠近根部的分裂样本多、权重大，这很合理——它影响了更多样本的预测。
- 递归：左右子树各返回一个长度为 `n_features` 的重要性数组，`+=` 累加回来。`X` 在递归中只切行、不切列，所以数组长度始终一致。

```python
    for _ in range(n_trees):
        sample_idx = rng.choice(n_samples, size=n_samples, replace=True)
        n_subset = max(1, int(np.sqrt(n_features)))
        feature_subset = rng.choice(n_features, size=n_subset, replace=False)
        # ...
        importances += tree_imp

    total = importances.sum()
    if total > 0:
        importances /= total
```

- **Bootstrap**：`replace=True` 有放回地抽 n 个样本，每棵树看到的数据略有不同。
- **特征子集**：每棵树随机取 `√20 ≈ 4` 个特征。
- 最后除以总和，重要性归一化到和为 1。
- ⚠️ 与真正的随机森林不同：RF 是在**每次分裂**时重新随机抽特征子集，这里是**每棵树**只抽一次、整棵树都只用这 4 个特征（更接近"随机子空间"方法）。这会让重要性受"哪些特征碰巧被抽到同一棵树"影响较大。
- ⚠️ 这是整个脚本最慢的部分：100 棵树 × 最多 63 个节点 × 4 个特征 × 约 21 个候选阈值，每次都调用 `np.unique` 算 Gini，实测约 7.7 秒（其余所有方法加起来不到 0.2 秒）。
- ⚠️ MDI 在训练数据上计算，偏向高基数特征；讲义建议用置换重要性复核。

### 3.8 主流程：标准化、一致性表、准确率验证

```python
    mean = X_train.mean(axis=0)
    std = X_train.std(axis=0)
    std[std == 0] = 1.0
    X_scaled_train = (X_train - mean) / std
    X_scaled_test = (X_test - mean) / std
    X_scaled = np.vstack([X_scaled_train, X_scaled_test])
```

- 均值和标准差**只从训练集计算**，再用于测试集——防止测试集信息泄漏。
- `std[std == 0] = 1.0`：布尔索引赋值，防止常数列除以 0。
- `X_scaled` 把两部分按原顺序拼回去，是为了交给 `evaluate_accuracy`，它内部会再按 80/20 切一次——因为 n 都是 500、切分点都是 400，两次切分恰好一致。⚠️ 这是一种脆弱的隐式耦合：只要有一方改了切分比例，训练/测试就会错位。

```python
    all_masks = {"MI": mi_selected, "RFE": rfe_mask, "L1": l1_mask, "Tree": tree_selected}
    header = f"  {'Feature':<12}" + "".join(f" {n:>6}" for n in all_masks) + f" {'Total':>6}"
```

- 用字典统一管理四种方法的掩码，之后只需遍历 `.values()`。遍历字典本身得到的是键（方法名），用于表头。
- 注意这里的 `n` 是生成器表达式内部的变量，Python 3 中推导式/生成器有自己的作用域，**不会覆盖**外面的 `n = len(y)`。不过同名变量容易让读者困惑，最好换个名字。
- MI 与 Tree 的"选中"是用 `np.argsort(scores)[-5:]` 取分数最高的 5 个；RFE 固定选 5 个；L1 选多少由 alpha 决定（本例 8 个）。

```python
def evaluate_accuracy(X, y, selected_mask, lr=0.1, epochs=200):
    X_selected = X[:, selected_mask]
    # ... 前 80% 训练，后 20% 测试 ...
    w, b = simple_logistic_importance(X_train, y_train, lr, epochs)
    z = X_test @ w + b
    preds = (1.0 / (1.0 + np.exp(-np.clip(z, -500, 500))) >= 0.5).astype(int)
    return np.mean(preds == y_test)
```

`X[:, selected_mask]` 用布尔掩码选列；`np.mean(preds == y_test)` 是求准确率的惯用写法（True 记 1、False 记 0 再求平均）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 合成数据，答案已知 | 能直接判断每种方法"选对没有" | 真实数据没有标准答案，只能靠留出集验证与业务知识 |
| 方差/MI/树用原始尺度，RFE/L1 用标准化数据 | 方差阈值在标准化后失效；树对单调变换不敏感；线性模型的 `|w|` 需要量纲一致 | 生产中用 Pipeline 把"标准化 + 选择 + 模型"串起来 |
| MI 用等宽分箱估计 | 公式直观，就是数列联表 | 有限样本偏差、对箱数敏感；sklearn 用 k-NN 估计 |
| RFE 每轮只删 1 个 | 最贴近算法定义 | 特征多时太慢；用 `step` 每轮删一批 |
| L1 用近端梯度下降 | 能得到精确的 0，展示 Lasso 稀疏性的来源 | 需充分收敛；生产中用坐标下降（如 `liblinear`、`saga` 求解器） |
| `best_split` 最多试约 20 个阈值 | 加速纯 Python 建树 | 可能错过最优切分；LightGBM 等用直方图算法做类似近似 |
| 每棵树只抽一次特征子集 | 实现简单 | 与随机森林"每次分裂抽样"不同；生产中直接用 `RandomForestClassifier.feature_importances_` 并配合置换重要性 |
| 只在训练集上选择，测试集上评估 | 避免选择泄漏 | 测试集只有 100 个样本，1 个样本 = 1%，差异需谨慎解读；应使用交叉验证 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| f-string 与列表推导 | `[f"info_{i}" for i in range(5)]` | 批量生成特征名 |
| 列表拼接 | `[...] + [...] + [...]` | `+` 连接列表，外层括号允许换行 |
| `in` 判断子串 | `if "noise" in name:` | 字符串包含检查 |
| 字典与 `dict(zip(...))` | `p_x = dict(zip(x_vals, x_counts / n_samples))` | 两个序列配对成"键→值" |
| `enumerate` | `for yi, yv in enumerate(y_vals)` | 同时取下标和值 |
| 嵌套元组解包 | `for i, (idx, s) in enumerate(ranked[:top_k or len(ranked)])` | `ranked` 的元素本身是 `(idx, score)` 元组 |
| `or` 提供默认值 | `top_k or len(ranked)` | `top_k` 为 `None` 时取全部 |
| `sorted` + `lambda` + `reverse` | `sorted(enumerate(scores), key=lambda x: x[1], reverse=True)` | 按分数从高到低排序，保留原下标 |
| `list.pop(i)` | `remaining.pop(least_idx)` | 删除并返回第 i 个元素 |
| 默认参数 + 递归 | `def _build_tree_importance(..., depth=0)`，递归时传 `depth + 1` | 首次调用不用传深度；递归必须有终止条件 |
| 下划线前缀 | `_build_tree_importance` | 约定为"内部辅助函数"，不建议外部直接调用 |
| 多重赋值 | `best_gain, best_threshold = gain, threshold` | 一行同时更新两个变量 |
| 生成器表达式 | `"".join(f" {n:>6}" for n in all_masks)`、`sum(1 for m in all_masks.values() if m[i])` | 按需生成，配合 `join` / `sum` 使用；变量作用域局限在表达式内 |
| 条件表达式 | `row += f" {'YES':>6}" if mask[i] else f" {'---':>6}"` | 一行 if-else |
| 字符串乘法 | `" ------" * (len(all_masks) + 1)` | 画表格分隔线 |
| f-string 格式符 | `{i+1:>2}`、`{names[idx]:<12}`、`{s:>8.4f}`、`{acc:>10.4f}` | 对齐、宽度、小数位 |
| `continue` | `if np.sum(mask) == 0: ... continue` | 没选中任何特征时跳过评估 |
| **NumPy 部分** | | |
| 按列拼接 | `np.column_stack([...])`、`np.hstack([...])`、`np.vstack([...])` | 拼列 / 左右拼 / 上下拼 |
| `axis` 参数 | `np.var(X, axis=0)`、`X_train.mean(axis=0)` | 沿样本方向聚合，每列得到一个数 |
| `np.linspace` / `np.digitize` | `np.linspace(min_val, max_val, n_bins + 1)`、`np.digitize(x, bin_edges[1:-1])` | 等距边界 / 返回所在区间编号 |
| `np.zeros_like(..., dtype=int)` | `np.zeros_like(x, dtype=int)` | 同形状、指定类型的全 0 数组 |
| 布尔索引赋值 | `std[std == 0] = 1.0`、`mi_selected[np.argsort(mi_scores)[-5:]] = True` | 按条件 / 按下标批量赋值 |
| 布尔取反 | `~left_mask` | 布尔数组逐元素取反（不能用 `not`） |
| 列选择 | `X[:, remaining]`、`X[:, selected_mask]` | 用整数列表或布尔掩码选列 |
| `np.argmin` / `np.argsort` | `np.argmin(importances)`、`np.argsort(tree_imp)[-5:]` | 最小值下标 / 升序排序后的下标，`[-5:]` 取最大的 5 个 |
| `np.sign` / `np.maximum` | `np.sign(w) * np.maximum(np.abs(w) - alpha, 0)` | 软阈值：逐元素取符号、与 0 比大小 |
| `rng.choice` | `rng.choice(n_samples, size=n_samples, replace=True)` | 有放回抽样（bootstrap）；`replace=False` 为无放回 |
| 数组原地累加 | `importances += tree_imp`、`importances /= total` | 对 NumPy 数组是原地修改 |

---

## 6. 运行结果解读

实际运行（numpy 2.5，Python 3.13，耗时约 8 秒）的关键输出：

```text
Dataset: 500 samples, 20 features
Target: binary classification (y=1: 254, y=0: 246)

1. VARIANCE THRESHOLD
  Threshold: 0.01, surviving: 20 / 20
     1. info_2         1.0161 [INFO]
     ...
    10. corr_3         0.4469 [CORR]
```

20 个特征全部存活。方差排名前 10 全是信息/相关特征，只是因为它们的尺度更大（噪声特征标准差设为 0.5）——**方差大小与"有没有用"无关**，这里的排序纯属数据构造的巧合。

```text
2. MUTUAL INFORMATION   (top 10)
     1. info_0         0.2602 [INFO]
     2. info_3         0.2555 [INFO]
     3. corr_0         0.2455 [CORR]
     4. info_1         0.1003 [INFO]
     5. info_4         0.0988 [INFO]
     6. corr_1         0.0972 [CORR]
     7. corr_4         0.0502 [CORR]
     8. noise_9        0.0299 [NOISE]
     9. corr_2         0.0239 [CORR]
    10. noise_5        0.0233 [NOISE]
```

- 前三名是 x1 的三个复制品，得分几乎一样（0.26 左右）；接下来三个是 x2 的复制品（约 0.10）。
- **真信号 `info_2`（x3）不在前 10**（实测排第 11，0.0229），被两个噪声特征超过。原因：x3 的系数最小，且它对 y 的影响被更强的 x1、x2 掩盖，单独看与 y 的相关系数只有约 0.18。**Filter 方法逐个打分，看不到"控制住 x1、x2 后 x3 还有多大作用"。**
- `noise_9` 得 0.0299，体现了分箱估计的有限样本偏差和方差。

```text
3. RECURSIVE FEATURE ELIMINATION (RFE)
  Selected: ['info_0', 'info_1', 'info_2', 'info_3', 'corr_0']
    Rank  1: info_0 ... corr_0
    Rank  6: info_4       [INFO]
    Rank  7: corr_1       [CORR]
    Rank  8: corr_2       [CORR]
    Rank  9: noise_9      [NOISE]
    ...
    Rank 20: noise_0      [NOISE]
```

- RFE 选中了 x3（`info_2`）：因为模型是多变量的，x1、x2 的作用已被各自的特征解释掉，x3 的**条件贡献**就显露出来了。这就是 Wrapper 比 Filter 强的地方。
- 但它仍然留下了 x1 的三个复制品（x1 系数最大，即使权重被三者分摊，每份也比别人大），反而淘汰了 x2 的复制品 `info_4`。
- 排名从 1 直接跳到 6，即 3.4 节说的编号瑕疵。噪声特征基本排在最后，符合预期；`corr_3`、`corr_4` 这类"混合型"相关特征也被较早淘汰，因为它们的信息已经被纯净的 x1/x2/x3 覆盖。

```text
4. L1 (LASSO) FEATURE SELECTION
  Nonzero weights: 8
  Selected: ['info_0', 'info_1', 'info_2', 'info_3', 'info_4', 'corr_0', 'corr_1', 'corr_2']
     1. info_0         0.5542     2. info_3         0.5532     3. corr_0         0.5340
     4. info_1         0.3146     5. info_4         0.3012     6. corr_1         0.2717
     7. info_2         0.2578     8. corr_2         0.0984     9. corr_3         0.0000
```

（权重列表为压缩排版。）所有 10 个噪声特征和 `corr_3`、`corr_4` 都被精确压到 0——稀疏性生效了；但三个 x1 复制品的权重几乎相等，说明在当前迭代次数下，还没有出现"相关特征里只留一个"的效果（见 3.5 节的收敛讨论）。

```text
5. TREE-BASED IMPORTANCE   (top 10)
     1. corr_0         0.1616     2. info_3         0.1379     3. info_0         0.0937
     4. info_4         0.0833     5. info_1         0.0571     6. corr_3         0.0479
     ...
    10. noise_9        0.0344
```

（压缩排版。）树重要性的前 5 名同样全是 x1、x2 的复制品，`info_2` 排第 11；排第一的竟是 `corr_0` 而不是"原版" `info_0`——在相关特征之间，重要性的分配带有很大随机性（取决于哪棵树抽到了哪些特征、哪个切分点碰巧略优）。

```text
METHOD AGREEMENT
  Feature          MI    RFE     L1   Tree  Total
  info_0          YES    YES    YES    YES      4
  info_1          YES    YES    YES    YES      4
  info_2          ---    YES    YES    ---      2
  info_3          YES    YES    YES    YES      4
  info_4          YES    ---    YES    YES      3
  corr_0          YES    YES    YES    YES      4
  ...
  noise_0 ~ noise_9  全部 ---                     0
```

四种方法在"噪声特征一个都不要"上完全一致，这是最可靠的结论；分歧集中在**冗余特征**（选哪个复制品）和**被掩盖的弱信号**（`info_2`）上。

```text
ACCURACY COMPARISON
  Method                 Features   Accuracy
  All 20 features              20     0.9400
  Info only (5)                 5     0.9600
  MI top-5                      5     0.9000
  RFE top-5                     5     0.9600
  L1 selected                   8     0.9800
  Tree top-5                    5     0.9000
```

- 去掉噪声后（Info only、RFE、L1）准确率高于用全部 20 个特征——讲义"更多特征不等于更好"的直接证据。
- **MI top-5 和 Tree top-5 只有 0.90，比全部特征还差**：它们漏掉了 x3，把 5 个名额全花在 x1、x2 的复制品上。选的特征数一样多，覆盖的独立信息却少了一个维度。这是本节最值得记住的结果：**按单项得分取 top-K，会被冗余特征占满名额。**
- L1 的 8 个特征覆盖了 x1、x2、x3 三个信号，准确率最高。
- ⚠️ 测试集只有 100 个样本，0.94 和 0.96 只差 2 个样本，不能据此断言谁优谁劣；严谨的比较应使用交叉验证并报告方差。

---

## 7. 动手改一改

1. **给 MI 加去冗余**（讲义练习 3）：先计算特征相关矩阵，对 |ρ| > 0.9 的特征对只保留 MI 更高的那个，再取 top-5。看 MI 方法能否选回 `info_2`、准确率能否回到 0.96。
2. **修正 RFE 排名**：把排名改成与 sklearn 一致的连续编号（见测验 Q9），并加一个 `step` 参数支持每轮删除多个特征。
3. **观察 L1 的收敛**：用 `alpha=0.05` 分别跑 `(lr, epochs) = (0.01, 1000)`、`(0.1, 5000)`、`(0.5, 20000)`，打印非零特征数和权重。再把 alpha 从 0.01 扫到 0.5，画出"非零特征数 vs alpha"曲线（正则化路径）。
4. **前向选择**（讲义练习 1）：从空集开始，每步加入能让验证准确率提升最多的特征，提升小于 0.005 时停止。与 RFE 的结果和耗时对比。
5. **置换重要性**（讲义练习 5）：实现后在测试集上计算，再删除 x1 的复制品重算，观察 `info_0` 的重要性如何从约 0.09 变到约 0.34（见测验 Q10）。
6. **改成真正的随机森林抽样**：把 `feature_subset` 的抽样从"每棵树一次"挪到 `_build_tree_importance` 的"每个节点一次"（需要把 `rng` 传进去），比较重要性排名的稳定性。

---

## 8. 常见坑

- **在全量数据上做选择再评估**：特征选择也要"只看训练集"，否则噪声特征会因为碰巧与全量 y 相关而被选中，评估分数虚高。本代码所有选择都只用 `X_train`。
- **标准化之后做方差阈值**：标准化后所有方差都是 1，阈值形同虚设；反过来，**用 `|w|` 做 RFE 或 L1 之前必须标准化**，否则量纲大的特征权重小、被误删。
- **把单项得分最高的 K 个当最优子集**：冗余特征会成批入选，挤掉独立信号（本例 MI/Tree top-5 准确率 0.90）。
- **相信未收敛的 L1 结果**：迭代不够时，"非零特征"只是被提前停止的梯度下降留下来的，并不代表 Lasso 的真实解。
- **只看一次运行的重要性**：树重要性、L1 在相关特征之间的取舍都不稳定，换个随机种子或子样本就可能变。用多次子采样统计入选频率（Stability Selection）更可靠。
- **RFE 中下标映射写错**：`least_idx` 是子集中的位置，必须经 `remaining[least_idx]` 转成原始列号；先 `pop` 再取值会删错特征。
