# 代码讲解 · imbalanced.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 17 节 处理不平衡数据 ｜ 讲义：[../docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python imbalanced.py`（无命令行参数，不到 1 秒跑完） ｜ **依赖**：仅 `numpy`（不需要 scikit-learn / imbalanced-learn）

---

## 1. 这份代码在考察什么

这份脚本把"处理不平衡数据"的几种主流手段全部**从零手写**一遍，放在同一个数据集、同一个模型（逻辑回归）上横向对比：

1. **为什么 accuracy 会骗人**：先跑一个"永远预测多数类"的基线，看它 accuracy 很高、其他指标全为 0。
2. **数据层面的修正**：随机过采样、随机欠采样、SMOTE（k 近邻 + 线性插值）各自怎么改变训练集。
3. **算法层面的修正**：类权重（class weights）如何通过"给损失乘权重"让模型重视少数类，而不改动数据。
4. **决策层面的修正**：阈值调优——训练完的模型不动，只移动 0.5 这条分界线。
5. **正确的评估方式**：手写混淆矩阵、precision、recall、F1、MCC，并强调"阈值在验证集上调、在测试集上评"。

> 一句话：**SMOTE 就是少数类内部的 k-NN 插值，类权重就是给损失乘个系数，阈值调优就是一个 for 循环**——没有魔法，但每一步都有讲究。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `make_imbalanced_data` | 函数 | 生成 950 负 / 50 正的二维高斯数据并打乱 | 不平衡数据集 |
| `euclidean_distance` / `find_k_neighbors` | 函数 | 计算欧氏距离，找某个点的 k 个最近邻 | k-NN |
| `smote` | 函数 | 在少数类样本与其近邻之间插值，生成合成样本 | SMOTE |
| `random_oversample` / `random_undersample` | 函数 | 复制少数类 / 丢弃多数类，使两类数量相等 | 随机重采样 |
| `sigmoid` / `logistic_regression_weighted` | 函数 | 带样本权重的逻辑回归（批量梯度下降） | 加权交叉熵 |
| `compute_class_weights` | 函数 | 按 `n / (n_classes · n_c)` 给每个样本分配权重 | class weights |
| `class_weighted_loss` | 函数 | 计算加权二元交叉熵 | 加权损失 |
| `confusion_matrix_values` / `compute_metrics` | 函数 | 混淆矩阵四格 + accuracy/precision/recall/F1/MCC | 不平衡评估指标 |
| `find_optimal_threshold` | 函数 | 在 0.05~0.95 之间扫阈值，返回使指标最大的阈值 | 阈值调优 |
| `print_confusion_matrix` / `print_metrics` | 函数 | 格式化打印 | — |
| `if __name__ == "__main__":` | 演示入口 | 8 个实验 + 汇总表 | — |

数据流：`make_imbalanced_data` → 按 80/20 切分训练/测试 → 每种策略各自"改造训练集或权重" → 都交给 `logistic_regression_weighted` 训练 → 在**同一个原始测试集**上用 `compute_metrics` 评估 → 汇总对比。

---

## 3. 逐段精讲

### 3.1 造一个不平衡数据集

```python
def make_imbalanced_data(n_majority=950, n_minority=50, seed=42):
    rng = np.random.RandomState(seed)
    X_maj = rng.randn(n_majority, 2) * 1.0 + np.array([0.0, 0.0])
    X_min = rng.randn(n_minority, 2) * 0.8 + np.array([2.5, 2.5])
    X = np.vstack([X_maj, X_min])
    y = np.concatenate([np.zeros(n_majority), np.ones(n_minority)])
    shuffle_idx = rng.permutation(len(y))
    return X[shuffle_idx], y[shuffle_idx]
```

- 多数类：以原点为中心、标准差 1 的二维高斯；少数类：以 `(2.5, 2.5)` 为中心、标准差 0.8（更紧凑）。两个中心相距约 `2.5·√2 ≈ 3.5`，**两类相当可分**——所以后面连"不做任何处理"的逻辑回归 precision 都能到 1.0。
- `rng = np.random.RandomState(seed)`：用**独立的随机数生成器**而不是全局 `np.random.seed`，函数内外的随机状态互不干扰，结果可复现。
- `rng.permutation(len(y))` 生成一个打乱的下标序列，再用花式索引 `X[shuffle_idx]` 同时打乱 X 和 y，保证特征与标签仍然一一对应。
- ⚠️ 标签 `y` 是 `float`（`0.0 / 1.0`），因为 `np.zeros/np.ones` 默认是浮点型。后面用 `y == 1` 比较时没问题，但打印时会看到 `1.0`。

### 3.2 SMOTE：k 近邻 + 线性插值

```python
def euclidean_distance(a, b):
    return np.sqrt(np.sum((a - b) ** 2))


def find_k_neighbors(X, idx, k):
    distances = []
    for i in range(len(X)):
        if i == idx:
            continue
        d = euclidean_distance(X[idx], X[i])
        distances.append((i, d))
    distances.sort(key=lambda x: x[1])
    return [d[0] for d in distances[:k]]
```

- `find_k_neighbors` 是最朴素的 k-NN：算出 `X[idx]` 到所有其他点的距离，存成 `(下标, 距离)` 元组列表，按距离排序，取前 k 个的下标。
- `if i == idx: continue` 排除自己——否则距离为 0 的"自己"永远是第一近邻，插值就变成复制。
- `sort(key=lambda x: x[1])`：按元组第 2 个元素（距离）排序。复杂度 O(n log n)。

```python
def smote(X_minority, k=5, n_synthetic=100, seed=42):
    rng = np.random.RandomState(seed)
    n_samples = len(X_minority)
    k = min(k, n_samples - 1)
    if k < 1:
        raise ValueError("SMOTE requires at least 2 minority samples")
    synthetic = []

    for _ in range(n_synthetic):
        idx = rng.randint(0, n_samples)
        neighbors = find_k_neighbors(X_minority, idx, k)
        neighbor_idx = neighbors[rng.randint(0, len(neighbors))]
        t = rng.random()
        new_point = X_minority[idx] + t * (X_minority[neighbor_idx] - X_minority[idx])
        synthetic.append(new_point)

    return np.array(synthetic)
```

逐行对应讲义的三步算法：

| 代码 | 讲义步骤 |
|------|---------|
| `idx = rng.randint(0, n_samples)` | 选一个少数类样本 x |
| `find_k_neighbors(X_minority, idx, k)` | 在**少数类内部**找 k 个近邻 |
| `neighbors[rng.randint(0, len(neighbors))]` | 随机挑一个近邻 |
| `t = rng.random()` | `t ~ U[0, 1)` |
| `X[idx] + t * (X[nn] - X[idx])` | 在两点连线上取一点 |

- **为什么只在少数类内部找近邻**：保证插值点落在"少数类所在的区域"里。注意函数只接收 `X_minority`，它根本看不到多数类——这既是 SMOTE 简单的原因，也是它的缺陷（可能在边界附近、甚至多数类区域内生成噪声点）。
- `k = min(k, n_samples - 1)`：少数类样本数不足 k+1 时自动缩小 k；只有 1 个样本时 k=0，无法插值，直接 `raise ValueError`——**快速失败**，比返回奇怪结果好。
- ⚠️ 简化 1：原始 SMOTE 论文是"对**每个**少数类样本各生成若干个合成点"，这里是"每次**随机**挑一个基准点"（有放回），所以有的样本可能被选很多次、有的一次也没被选。数量足够多时两者差别不大。
- ⚠️ 简化 2：每生成一个点都重新算一遍 k 近邻，总复杂度约 O(n_synthetic · n log n)。本例 728 × 36 个点没问题；生产中应**先为每个少数类样本预计算一次近邻**（或用 KD-Tree / `sklearn.neighbors.NearestNeighbors`），再循环插值。
- ⚠️ 简化 3：没有做特征缩放。SMOTE 依赖欧氏距离，各特征量纲不同时必须先标准化。

### 3.3 随机过采样与欠采样

```python
def random_oversample(X, y, seed=42):
    rng = np.random.RandomState(seed)
    classes, counts = np.unique(y, return_counts=True)
    max_count = counts.max()

    X_resampled = list(X)
    y_resampled = list(y)

    for cls, count in zip(classes, counts):
        if count < max_count:
            cls_indices = np.where(y == cls)[0]
            n_needed = max_count - count
            chosen = rng.choice(cls_indices, size=n_needed, replace=True)
            X_resampled.extend(X[chosen])
            y_resampled.extend(y[chosen])

    X_out = np.array(X_resampled)
    y_out = np.array(y_resampled)
    shuffle = rng.permutation(len(y_out))
    return X_out[shuffle], y_out[shuffle]
```

- `np.unique(y, return_counts=True)` 一次性拿到"有哪些类别、每类几个"，例如 `([0., 1.], [764, 36])`。
- 写法是**通用的多分类版本**：遍历每个类，凡是比最大类少的，就**有放回**（`replace=True`）地抽 `max_count - count` 个下标补齐。有放回是必须的——要补 728 个，而少数类只有 36 个。
- `list(X)` 把二维数组拆成"一行一个一维数组"的列表，`extend(X[chosen])` 往后追加若干行，最后 `np.array(...)` 再拼回二维数组。
- 最后再打乱一次：否则复制出来的样本全堆在末尾。对本例的**全批量**梯度下降来说顺序无所谓，但对 mini-batch SGD 很重要。

```python
def random_undersample(X, y, seed=42):
    # ...
    for cls in classes:
        cls_indices = np.where(y == cls)[0]
        chosen = rng.choice(cls_indices, size=min_count, replace=False)
        X_resampled.extend(X[chosen])
        y_resampled.extend(y[chosen])
    # ...
```

- 欠采样对**每个**类都无放回地抽 `min_count` 个（少数类相当于全部保留、只是换了顺序）。`replace=False` 保证不重复。
- 代价很直观：训练集从 800 条缩到 72 条，丢掉了 90% 以上的数据。

### 3.4 带样本权重的逻辑回归

```python
def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))


def logistic_regression_weighted(X, y, weights, lr=0.01, epochs=200):
    n_samples, n_features = X.shape
    w = np.zeros(n_features)
    b = 0.0

    for _ in range(epochs):
        z = X @ w + b
        pred = sigmoid(z)
        error = pred - y
        weighted_error = error * weights

        gradient_w = (X.T @ weighted_error) / n_samples
        gradient_b = np.mean(weighted_error)

        w -= lr * gradient_w
        b -= lr * gradient_b

    return w, b
```

- `np.clip(z, -500, 500)`：`exp(1000)` 会溢出成 `inf` 并报警告。夹到 ±500 后 `exp(500) ≈ 1.4e217` 仍在 float64 范围内，sigmoid 结果也已经是 0 或 1，不影响数值。
- **加权的核心只有一行**：`weighted_error = error * weights`。加权交叉熵 `L = (1/n) Σ wᵢ·BCE(yᵢ, pᵢ)` 对 w 的梯度是 `(1/n) Σ wᵢ (pᵢ − yᵢ) xᵢ`——每个样本的误差先乘上自己的权重，再走普通逻辑回归的梯度公式。
- 统一接口的巧妙之处：**所有实验都用这同一个函数**。不加权时传 `np.ones(len(y))`，就是普通逻辑回归；类权重实验传 `compute_class_weights(y)`。这样对比实验里唯一的变量就是"数据/权重怎么处理"。
- `X.T @ weighted_error`：`(n_features, n) @ (n,) → (n_features,)`，一次矩阵乘法完成"对所有样本求和"，这就是向量化。
- ⚠️ 简化：固定 `epochs=300`、`lr=0.1` 的全批量梯度下降，没有收敛判断、没有正则化、没有特征标准化。本例数据只有两个量级相近的特征，问题不大。

### 3.5 类权重与加权损失

```python
def compute_class_weights(y):
    classes, counts = np.unique(y, return_counts=True)
    n_samples = len(y)
    n_classes = len(classes)
    weight_map = {}
    for cls, count in zip(classes, counts):
        weight_map[cls] = n_samples / (n_classes * count)
    return np.array([weight_map[yi] for yi in y])
```

- 公式 `w_c = n_samples / (n_classes · n_c)` 与 sklearn 的 `class_weight="balanced"` 相同。本例训练集 764 负 / 36 正：负例 `800/(2·764) ≈ 0.5236`，正例 `800/(2·36) ≈ 11.11`。
- 一个漂亮的性质：每类的**总权重**都等于 `n_samples / n_classes`（764 × 0.5236 ≈ 36 × 11.11 ≈ 400），两类在损失中"话语权"相等；所有权重之和仍是 n，所以梯度量级和不加权时可比。
- 返回值是**逐样本**的权重数组（长度 = len(y)），而不是"每类一个权重"的字典——这样可以直接和 `error` 逐元素相乘。（对应 sklearn 里 `compute_sample_weight` 的输出，而 `compute_class_weight` 返回的是每类一个值。）
- `weight_map[yi]`：字典的键是 `np.unique` 返回的 `np.float64`，查询用的 `yi` 也是 `np.float64`，二者哈希一致，所以能查到。

```python
def class_weighted_loss(y_true, y_pred_probs, weights):
    eps = 1e-15
    y_pred_probs = np.clip(y_pred_probs, eps, 1 - eps)
    loss = -(y_true * np.log(y_pred_probs) + (1 - y_true) * np.log(1 - y_pred_probs))
    return np.mean(loss * weights)
```

- 讲义公式 `-Σ wᵢ [yᵢ log pᵢ + (1−yᵢ) log(1−pᵢ)]` 的实现（这里取平均而不是求和）。
- `np.clip(..., eps, 1 - eps)`：防止 `log(0) = -inf`。经典的数值稳定写法。
- 这个函数**不参与训练**（训练只用梯度），只在第 8 个实验里用来"量一量"两个模型各自在两种目标下的损失。

### 3.6 评估：混淆矩阵与 MCC

```python
def confusion_matrix_values(y_true, y_pred):
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    return tp, tn, fp, fn


def compute_metrics(y_true, y_pred):
    tp, tn, fp, fn = confusion_matrix_values(y_true, y_pred)
    accuracy = (tp + tn) / (tp + tn + fp + fn)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    denom = np.sqrt(float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)))
    mcc = (tp * tn - fp * fn) / denom if denom > 0 else 0.0
    # ...
```

- `(y_pred == 1) & (y_true == 1)`：两个布尔数组按位与，`np.sum` 数 True 的个数。注意必须用 `&` 而不是 `and`，且两边都要加括号（`&` 优先级比 `==` 高）。
- **零除保护**：每个比值都写成 `a / b if b > 0 else 0.0`。"全预测为负"时 `tp + fp = 0`，precision 是 0/0，按惯例记为 0；MCC 分母为 0 时也记为 0——这正是讲义说的"这些指标正确地判定该模型毫无价值"。
- **`int(...)` 的深意**：`np.sum` 返回 `numpy.int64`，MCC 分母是四个计数相乘，数据量到百万级时会超出 int64 范围，NumPy 只给一个警告然后"绕回"成负数，`sqrt` 得到 `nan`。转成 Python 原生 int（任意精度）就不会溢出。讲义 Step 6 的片段少了这层 `int(...)`，代码文件的版本更健壮。
- MCC 的直觉：它就是"预测标签"和"真实标签"两个 0/1 变量之间的皮尔逊相关系数，+1 完美、0 等同随机、-1 完全相反。

### 3.7 阈值调优：一个 for 循环

```python
def find_optimal_threshold(y_true, y_probs, metric="f1"):
    best_threshold = 0.5
    best_score = -1.0

    for threshold in np.arange(0.05, 0.96, 0.01):
        y_pred = (y_probs >= threshold).astype(int)
        tp = np.sum((y_pred == 1) & (y_true == 1))
        fp = np.sum((y_pred == 1) & (y_true == 0))
        fn = np.sum((y_pred == 0) & (y_true == 1))

        if metric == "f1":
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            score = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        elif metric == "recall":
            score = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        elif metric == "precision":
            score = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        else:
            score = 0.0

        if score > best_score:
            best_score = score
            best_threshold = threshold

    return best_threshold, best_score
```

- `np.arange(0.05, 0.96, 0.01)` 产生 0.05, 0.06, …, 0.95 共 91 个阈值。用 0.96 作上界是因为 `arange` 不含终点。浮点步长会带来 `0.6700000000000002` 这样的值，打印时用 `:.2f` 掩盖了。
- `(y_probs >= threshold).astype(int)`：布尔数组转 0/1 预测。
- 严格 `>` 意味着**多个阈值并列最优时取最小的那个**。
- ⚠️ 未知的 `metric`（例如 `"f2"`）会走 `else: score = 0.0`，函数**静默返回 `(0.05, 0.0)`**，不报错。更安全的写法是直接 `raise ValueError`（见测验 Q9）。
- ⚠️ 单独优化 `"recall"` 总会选到最低阈值 0.05（阈值越低 recall 越高），是个退化解；实际应优化 F1/Fβ 或带约束的目标。

### 3.8 主流程：8 个实验

**切分**：

```python
    split = int(0.8 * len(y))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
```

数据已在生成时打乱，所以直接切前 80% 当训练集。⚠️ 这不是**分层**切分：运行结果中训练集正例 36 个（4.5%），测试集 14 个（7%），比例并不一致。生产中应使用 `train_test_split(..., stratify=y)`。

**实验 2–6** 都是同一个模式："改造训练数据或权重 → 训练 → 在原始测试集上以 0.5 为阈值评估"。其中 SMOTE 实验需要补的数量是 `n_majority_train - n_minority_train = 764 - 36 = 728`，合成点只加到训练集，**测试集保持原样**——这是防泄漏的关键。

**实验 7：阈值调优**

```python
    val_split = int(0.75 * len(y_train))
    X_tr, X_val = X_train[:val_split], X_train[val_split:]
    y_tr, y_val = y_train[:val_split], y_train[val_split:]
    val_weights = compute_class_weights(y_tr)
    w_val, b_val = logistic_regression_weighted(X_tr, y_tr, val_weights, lr=0.1, epochs=300)
    probs_val = sigmoid(X_val @ w_val + b_val)
    best_thresh, best_f1 = find_optimal_threshold(y_val, probs_val, metric="f1")
    print(f"  Optimal threshold: {best_thresh:.2f} (F1 on val: {best_f1:.4f})")
    preds_thresh = (probs_cw >= best_thresh).astype(int)
```

- 从训练集里再切出后 25%（200 条）当**验证集**，在前 75% 上重新训练一个类加权模型 `w_val`，用它在验证集上的概率选阈值——测试集全程没碰，这是正确的姿势。（讲义 Step 7 的片段直接用了未定义的 `X_val`、`y_val`，代码文件补全了这一步。）
- ⚠️ 一个微妙之处：阈值是在 `w_val` 上选的，却应用到了 `probs_cw`——它来自**在全部训练集上**训练的另一个模型 `w_cw`。这是"选好超参后在全量数据上重训"的常见近似，本例两个模型系数几乎一样（约 `[1.07, 1.09]` 对 `[1.08, 1.10]`），所以可行；但若两个模型的概率刻度差异较大，迁移过来的阈值就不再最优。更严谨的做法是用交叉验证的 out-of-fold 预测选阈值。
- ⚠️ 验证集只有 10 个正例，验证 F1 直接是 1.0，阈值估计的方差很大。

**实验 8：加权损失对比**——用 `class_weighted_loss` 分别以"均匀权重"和"类权重"两种标准，衡量"普通模型"和"类加权模型"。目的是说明：**类权重改变的是优化目标本身**，每个模型都在自己的目标上更优（见第 6 节的输出解读）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 所有策略共用一个 `logistic_regression_weighted` | 控制变量，只比较"数据/权重处理"的差异 | 生产中用 `sklearn.linear_model.LogisticRegression(class_weight=...)` 或 GBDT |
| SMOTE 只接收少数类 `X_minority` | 实现最简，完全对应讲义三步算法 | 看不到多数类，边界噪声；用 Borderline-SMOTE / SMOTE-Tomek 改进 |
| 每次插值都重新暴力找近邻 | 代码直观 | 复杂度高；应预计算近邻或用 KD-Tree |
| 类权重返回逐样本数组 | 可直接与 `error` 逐元素相乘 | sklearn 中用 `class_weight` 或 `sample_weight` 参数 |
| 所有指标手写并做零除保护 | 看清每个指标的定义与边界情况 | 用 `sklearn.metrics`（`classification_report`、`matthews_corrcoef`、`average_precision_score`） |
| 阈值在训练集切出的验证集上调 | 测试集只用于最终评估，避免乐观偏差 | 用 CV 的 out-of-fold 预测选阈值，更稳定 |
| 非分层的 80/20 切分 | 代码最短 | 不平衡数据必须 `stratify=y` 或 `StratifiedKFold` |
| 固定 lr/epochs、无正则、无标准化 | 聚焦于不平衡处理本身 | 需要收敛判断、正则化、特征缩放 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def smote(X_minority, k=5, n_synthetic=100, seed=42)` | 调用时可省略；用关键字参数覆盖，如 `smote(X, k=5, n_synthetic=728, seed=42)` |
| 多返回值 / 元组解包 | `return tp, tn, fp, fn`；`tp, tn, fp, fn = confusion_matrix_values(...)` | 实际返回一个元组，接收方按位置拆开 |
| `_` 占位变量 | `for _ in range(n_synthetic):` | 循环变量用不到时的惯用写法 |
| `continue` | `if i == idx: continue` | 跳过本轮循环 |
| `lambda` 与 `sort(key=...)` | `distances.sort(key=lambda x: x[1])` | 匿名函数，按元组第 2 个元素排序；`list.sort` 原地排序 |
| 列表推导式 | `[d[0] for d in distances[:k]]`、`[weight_map[yi] for yi in y]` | 一行生成新列表 |
| 切片 | `distances[:k]`、`X[:split]`、`X[split:]` | 取前 k 个 / 划分数组 |
| `zip` | `for cls, count in zip(classes, counts)` | 把两个序列按位置配对 |
| 字典 | `weight_map = {}`；`weight_map[cls] = ...` | 类别 → 权重的映射 |
| `list.extend` | `X_resampled.extend(X[chosen])` | 把一个可迭代对象的元素逐个追加（`append` 则是整体追加为一个元素） |
| 条件表达式 | `tp / (tp + fp) if (tp + fp) > 0 else 0.0` | 一行 if-else，常用于零除保护 |
| `if / elif / else` | `if metric == "f1": ... elif metric == "recall": ...` | 多分支选择 |
| `raise` 抛异常 | `raise ValueError("SMOTE requires at least 2 minority samples")` | 参数非法时快速失败 |
| 增强赋值 | `w -= lr * gradient_w` | 等价于 `w = w - lr * gradient_w`；对 NumPy 数组是原地修改 |
| `int()` / `float()` 类型转换 | `int(np.sum(...))`、`float((tp + fp) * ...)` | NumPy 标量转 Python 原生类型，避免溢出 |
| f-string 格式符 | `{tp:>5}`、`{name:<18}`、`{m['f1']:>6.3f}`、`{best_thresh:.2f}`、`{n_pos/len(y)*100:.1f}` | `>`/`<` 右/左对齐，数字是宽度，`.3f` 保留 3 位小数 |
| 字符串乘法 | `"=" * 60`、`'-'*18` | 重复字符串，用来画分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行演示 |
| **NumPy 部分** | | |
| 独立随机数生成器 | `rng = np.random.RandomState(seed)`；`rng.randn`、`rng.randint`、`rng.random`、`rng.choice`、`rng.permutation` | 可复现，且不污染全局随机状态 |
| 数组拼接 | `np.vstack([X_maj, X_min])`、`np.concatenate([...])` | 竖直堆叠二维数组 / 拼接一维数组 |
| 花式索引 | `X[shuffle_idx]`、`X[chosen]` | 用下标数组一次取多行 |
| 布尔掩码 | `X_train[minority_mask]`，其中 `minority_mask = y_train == 1` | 用布尔数组筛选行 |
| 逐元素逻辑运算 | `(y_pred == 1) & (y_true == 1)` | 数组上必须用 `&`、`|`，并给比较式加括号 |
| `np.where(cond)[0]` | `np.where(y == cls)[0]` | 返回满足条件的下标 |
| `np.unique(..., return_counts=True)` | `classes, counts = np.unique(y, return_counts=True)` | 去重并计数 |
| 矩阵乘法与转置 | `X @ w + b`、`X.T @ weighted_error` | `@` 是矩阵乘法，`.T` 转置；`+ b` 触发广播 |
| `np.clip` | `np.clip(z, -500, 500)`、`np.clip(y_pred_probs, eps, 1 - eps)` | 把数值夹在区间内，防溢出/防 log(0) |
| `astype` | `(probs_base >= 0.5).astype(int)` | 布尔数组转 0/1 整数 |
| `np.arange` 浮点步长 | `np.arange(0.05, 0.96, 0.01)` | 不含终点；浮点累积误差会产生 `0.6700000000000002` |
| `np.zeros_like` | `np.zeros_like(y_test)` | 生成形状、类型与 `y_test` 相同的全 0 数组（"全预测为负"） |

---

## 6. 运行结果解读

实际运行（numpy 2.5，Python 3.13，耗时约 0.4 秒）的关键输出如下：

```text
Dataset: 1000 samples, 50 positive (5.0%), 950 negative (95.0%)
Train: 800 samples, Test: 200 samples
Train positives: 36, Test positives: 14
```

非分层切分导致训练集正例率 4.5%、测试集 7%。测试集只有 14 个正例——**每多抓/漏一个，recall 就变化约 7 个百分点**，下面各方法之间的小差距都不具备统计显著性。

```text
1. ALWAYS PREDICT MAJORITY (BASELINE)
    Actual +           0           14
    Actual -           0          186
    Accuracy:  0.9300   Precision: 0.0000   Recall: 0.0000   F1: 0.0000   MCC: 0.0000
```

一个正例都没抓到，accuracy 仍有 93%——讲义开篇"accuracy 是谎言"的现场演示。（为节省篇幅，指标合并到一行展示，实际输出是每行一个。）

```text
2. NO TREATMENT (PLAIN LOGISTIC REGRESSION)
    Actual +           9            5
    Actual -           0          186
    Precision: 1.0000   Recall: 0.6429   F1: 0.7826   MCC: 0.7912
```

普通逻辑回归非常"保守"：0 误报，但漏了 5 个正例（recall 64%）。大量负例把截距 b 压得很低（本例约 -3.18），正例的概率普遍偏小，0.5 这条线对它来说太高了。

```text
3. RANDOM OVERSAMPLING     After oversampling: 1528 samples (was 800)   Positive: 764, Negative: 764
    Actual + 14 / 0     Actual - 8 / 178     → Precision 0.6364  Recall 1.0000  F1 0.7778
4. RANDOM UNDERSAMPLING    After undersampling: 72 samples (was 800)    Positive: 36, Negative: 36
    Actual + 14 / 0     Actual - 7 / 179     → Precision 0.6667  Recall 1.0000  F1 0.8000
5. SMOTE                   Generated 728 synthetic minority samples     After SMOTE: 1528 samples
    Actual + 14 / 0     Actual - 7 / 179     → Precision 0.6667  Recall 1.0000  F1 0.8000
6. CLASS WEIGHTS           Weight for negative class: 0.5236   Weight for positive class: 11.1111
    Actual + 14 / 0     Actual - 8 / 178     → Precision 0.6364  Recall 1.0000  F1 0.7778
```

（以上为压缩排版，原输出每项单独成行。）

- 四种"再平衡"方法都把 recall 拉到了 100%，代价是出现 7~8 个误报——典型的 precision-recall 权衡：天平从"保守"一下子摆到了"激进"。
- **过采样与类权重的混淆矩阵完全一致**，这正是"类权重在期望上等价于过采样"的实证。从梯度看：过采样后每个负例在均值梯度里的系数是 `1/1528`，类权重下是 `0.5236/800 ≈ 1/1528`；每个正例在过采样中平均被复制约 21.2 次，系数 `21.2/1528 ≈ 1/72`，类权重下是 `11.11/800 = 1/72`——两者的期望梯度相同。
- 欠采样只用了 72 条数据，效果却不差，是因为这份数据两类分得很开，少量样本就足以确定边界；在重叠更严重的真实数据上，欠采样的方差会明显更大。

```text
7. THRESHOLD TUNING (on class-weighted model)
  Optimal threshold: 0.67 (F1 on val: 1.0000)
    Actual +          13            1
    Actual -           1          185
    Precision: 0.9286   Recall: 0.9286   F1: 0.9286   MCC: 0.9232
```

- 对类加权模型，最优阈值是 **0.67，比 0.5 还高**。原因：类权重把正例概率整体抬高、"矫枉过正"（阈值 0.5 时 8 个误报），把阈值往回调就能在几乎不损失 recall 的情况下去掉大部分误报。这说明"不平衡时阈值要调低"只适用于**普通训练**的模型；最优阈值取决于模型的概率刻度，必须在验证集上搜。
- 这是所有方法中最好的结果：只错了 2 个样本。**阈值调优不需要重新训练，几乎是"免费"的提升。**

```text
8. WEIGHTED CROSS-ENTROPY LOSS COMPARISON
  Base model, uniform loss:   0.0896
  Base model, weighted loss:  0.3462
  CW model, uniform loss:     0.1904
  CW model, weighted loss:    0.1342
```

用"均匀"标准衡量，普通模型更好（0.0896 < 0.1904）；用"类加权"标准衡量，类加权模型更好（0.1342 < 0.3462）。**每个模型都在自己优化的目标上胜出**——类权重不是"让模型变好"，而是"换了一个目标让模型去优化"，这个目标更符合"少数类同样重要"的业务需求。

```text
  Approach              Acc   Prec    Rec     F1    MCC
  Always majority     0.930  0.000  0.000  0.000  0.000
  No treatment        0.975  1.000  0.643  0.783  0.791
  Oversampling        0.960  0.636  1.000  0.778  0.780
  Undersampling       0.965  0.667  1.000  0.800  0.801
  SMOTE               0.965  0.667  1.000  0.800  0.801
  Class weights       0.960  0.636  1.000  0.778  0.780
  CW + threshold      0.990  0.929  0.929  0.929  0.923
```

汇总表里一个值得玩味的现象：**"No treatment" 的 accuracy（0.975）比四种再平衡方法都高**，但 recall 只有 0.643。如果只看 accuracy，你会选错模型。另外，各方法 F1 都在 0.78~0.80 之间，差距远小于"加不加阈值调优"带来的差距——在这类数据上，**决策阈值往往比重采样方式更重要**。

---

## 7. 动手改一改

1. **改成分层切分**：把 80/20 切分改为对正负例分别取 80%，观察训练/测试集的正例率是否一致、各方法结果是否变化。
2. **给"无处理"模型也调阈值**：对 `probs_base` 在验证集上调阈值，与 "CW + threshold" 对比（提示：本例中阈值降到 0.3 时测试集 F1 就能到 0.88）。思考：既然调阈值这么有效，类权重还有必要吗？
3. **加上 AUPRC**：实现 `average_precision(y_true, scores)`（见测验 Q10），分别对无处理模型和类加权模型计算。你会发现两者几乎相同——为什么类权重几乎不改变 AUPRC？
4. **加速 SMOTE**：先用 `np.linalg.norm(X_minority[:, None] - X_minority[None], axis=-1)` 一次性算出距离矩阵，再用 `np.argsort` 为每个点预存 k 近邻，循环里只做插值。比较两种实现在 2000 个少数类样本上的耗时。
5. **Borderline-SMOTE（讲义练习 1）**：给 `smote` 增加 `X_majority` 参数，只对"k 近邻（在全体数据中找）里一半以上是多数类、但不全是多数类"的少数类点做插值。把少数类中心从 `(2.5, 2.5)` 挪到 `(1.0, 1.0)` 制造重叠，对比两种 SMOTE。
6. **代价敏感决策（讲义练习 2）**：写 `predict_min_cost(probs, c_fp, c_fn)`，按 `p > c_fp / (c_fp + c_fn)` 判正。分别用 1:10、1:100、1:1000 的代价比，观察 precision/recall 怎么变。注意：类加权模型的概率需要先校准。

---

## 8. 常见坑

- **在切分前做重采样**：先对全量数据 SMOTE / 过采样再切分，合成点和复制点会"跨越"训练/测试边界，测试分数虚高。本代码始终只改造 `X_train`。
- **在测试集上调阈值**：阈值也是超参数，只能在验证集（或 CV）上选。代码中专门从训练集切出了验证集。
- **对重采样后的数据算评估指标**：评估必须在**原始分布**的测试集上进行，否则 precision 会被严重高估。
- **把重采样/加权模型的输出当真实概率**：它们被系统性抬高了，需要先验校正或 Platt/isotonic 校准后才能用于期望代价计算。
- **NumPy 整数溢出**：大数据集上计算 MCC 分母时，int64 相乘可能溢出成负数；用 Python int 或 float 计算（本代码用了 `int(...)`）。
- **`find_optimal_threshold` 的 metric 拼错**：传入不支持的名字不会报错，而是静默返回 `(0.05, 0.0)`；调用后要检查返回的 score。
