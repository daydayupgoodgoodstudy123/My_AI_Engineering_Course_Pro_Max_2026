# 代码讲解 · evaluation.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 09 节 模型评估 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python evaluation.py`（无命令行参数，约 2 秒跑完） ｜ **依赖**：仅 Python 标准库（`random`、`math`），无需 NumPy / sklearn

---

## 1. 这份代码在考察什么

sklearn 里一行 `cross_val_score(model, X, y, cv=StratifiedKFold(5), scoring="f1")` 背后其实只是 for 循环和下标记账。这份代码把评估流程拆到最底层，让你看清：

1. **数据怎么切**：训练/验证/测试三分、K 折、分层 K 折——本质都是"打乱下标，再按位置切片"。
2. **指标怎么算**：所有分类指标都从混淆矩阵的四个计数 TP/TN/FP/FN 推出；AUC 是扫描阈值后的梯形积分；回归指标就是残差的不同聚合方式。
3. **为什么准确率会骗人**：在 4.3% 正样本的数据上，"永远预测负"拿到 95.67% 的准确率，但 recall = 0。
4. **怎么诊断模型**：学习曲线看训练/验证分数随数据量的变化。
5. **怎么比较两个模型**：在相同的折上做配对 t 检验，而不是只比均值。

> 一句话：**评估本身也是代码，也会有 bug**。亲手写一遍，你才能在面试和工作中一眼看出"先标准化后划分""ROC 缺起点""t 检验用错标准差"这类问题——本文件里恰好就藏着这几个，下文会逐一指出。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `train_val_test_split` | 函数 | 打乱后按 60/20/20 切三份 | Hold-out 划分 |
| `kfold_split` / `stratified_kfold_split` | 函数 | 生成 K 组 `(train_idx, val_idx)` 下标 | K 折 / 分层 K 折 |
| `cross_validate` | 函数 | 对每折新建模型、训练、预测、打分，返回 K 个分数 | 交叉验证 |
| `confusion_matrix`、`accuracy`、`precision`、`recall`、`f1_score` | 函数 | 计数 TP/TN/FP/FN 并推导指标 | 分类指标 |
| `roc_curve` / `auc_roc` | 函数 | 扫阈值得 (FPR, TPR) 点列，梯形法求面积 | ROC / AUC |
| `mse`、`rmse`、`mae`、`r_squared` | 函数 | 回归误差的不同聚合方式 | 回归指标 |
| `learning_curve` | 函数 | 固定验证集，逐步增大训练子集 | 学习曲线 |
| `SimpleLogistic` / `SimpleLinearRegression` | 类 | 用 SGD 训练的最小模型，接口为 `fit` / `predict` | 被评估对象 |
| `standardize` | 函数 | z-score 标准化，返回值和均值、标准差 | 特征缩放 |
| `make_*_data` | 函数 | 生成平衡分类、回归、不平衡分类三种合成数据 | 实验数据 |
| `if __name__ == "__main__":` | 演示入口 | 依次演示 7 个实验 | — |

数据流：`make_*_data` → 划分函数产出**下标** → `cross_validate` / `learning_curve` 按下标取样本，调用 `model_fn()` 新建模型 → `fit` → `predict` → 指标函数打分。所有评估函数只依赖"有 `fit(X, y)` 和 `predict(x)` 的对象"，与具体模型解耦。

---

## 3. 逐段精讲

### 3.1 `train_val_test_split`：打乱下标再切片

```python
def train_val_test_split(X, y, train_ratio=0.6, val_ratio=0.2, seed=42):
    random.seed(seed)
    n = len(X)
    indices = list(range(n))
    random.shuffle(indices)

    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_idx = indices[:train_end]
    val_idx = indices[train_end:val_end]
    test_idx = indices[val_end:]
```

- **打乱的是下标而不是数据本身**：X 和 y 用同一组下标取值，天然保持对齐；如果分别 shuffle X 和 y，样本和标签就错位了。
- 测试集取 `indices[val_end:]`，剩下的全给它，所以三份加起来一定等于 n，不会因 `int()` 截断丢样本。n=300 时得到 180 / 60 / 60。
- 为什么先打乱：原始数据往往有顺序（按时间、按类别收集）。不打乱直接切，测试集可能全是某一类或某一时段。
- ⚠️ **不是分层划分**：演示里训练集 91/180 为正、验证集 29/60 为正，比例基本接近只是因为数据本身平衡。不平衡数据上应按类别分别切（见 3.3）。
- ⚠️ **不适用于时间序列**：时间序列要按时间顺序切，随机打乱等于"用未来预测过去"。
- `random.seed(seed)` 修改的是**全局**随机状态，调用一次这个函数会影响之后所有 `random.*` 的结果。生产代码更推荐 `rng = random.Random(seed)` 的局部实例（sklearn 的 `random_state` 也是这个思路）。

### 3.2 `kfold_split`：最后一折兜底

```python
def kfold_split(n, k=5, seed=42):
    random.seed(seed)
    indices = list(range(n))
    random.shuffle(indices)

    fold_size = n // k
    folds = []

    for i in range(k):
        start = i * fold_size
        end = start + fold_size if i < k - 1 else n
        val_idx = indices[start:end]
        train_idx = indices[:start] + indices[end:]
        folds.append((train_idx, val_idx))

    return folds
```

- 第 i 折的验证集是 `indices[start:end]`，训练集是"切掉这一段后剩下的两截拼起来"：`indices[:start] + indices[end:]`。这保证了**每个样本恰好被验证一次**，且训练集与验证集不相交。
- `end = ... if i < k - 1 else n`：前 k−1 折大小都是 `n // k`，**余数全部塞给最后一折**。n=300、k=5 刚好整除，每折 60 个；但 n=23、k=5 时折大小是 `[4, 4, 4, 4, 7]`。sklearn 的 `KFold` 会把余数分摊给前几折（5, 5, 5, 4, 4），各折更均匀。
- 返回的是**下标**而不是数据：省内存，也方便同一组折被多个模型复用（3.11 的配对 t 检验正依赖这一点）。
- 因为每次都 `random.seed(42)`，对同样的 n 多次调用得到**完全相同**的折。

### 3.3 `stratified_kfold_split`：按类别分别切，再合并

```python
def stratified_kfold_split(y, k=5, seed=42):
    random.seed(seed)

    class_indices = {}
    for i, label in enumerate(y):
        class_indices.setdefault(label, []).append(i)

    for label in class_indices:
        random.shuffle(class_indices[label])

    folds = [{"train": [], "val": []} for _ in range(k)]

    for label, indices in class_indices.items():
        fold_size = len(indices) // k
        for i in range(k):
            start = i * fold_size
            end = start + fold_size if i < k - 1 else len(indices)
            val_part = indices[start:end]
            train_part = indices[:start] + indices[end:]
            folds[i]["val"].extend(val_part)
            folds[i]["train"].extend(train_part)

    return [(f["train"], f["val"]) for f in folds]
```

思路：**对每个类别单独做一次 K 折，再把同号的折拼起来**。这样每折里各类的比例都接近全集比例。

- `class_indices.setdefault(label, []).append(i)`：按标签分桶的惯用写法——键不存在时先放一个空列表再 append。
- 演示数据有 148 个负、152 个正：负类每折 29 个（最后一折 32），正类每折 30 个（最后一折 32），所以验证集大小是 `[59, 59, 59, 59, 64]`——"余数给最后一折"在每个类别上各发生一次，最后一折明显更大。
- ⚠️ **少数类样本数 < k 时**：`fold_size = 0`，前 k−1 折一个少数类样本都没有，全部落在最后一折，分层就失效了。sklearn 的 `StratifiedKFold` 在这种情况下会给出警告。
- ⚠️ **训练集按类别排序**：`folds[i]["train"]` 是"先全部负类、再全部正类"拼起来的。本节的 `SimpleLogistic` 用逐样本 SGD 训练，对样本顺序敏感。本次实验把训练下标打乱后再训练，5 折分数变化不大（均值 0.872 vs 0.876），但在学习率较大、类别更不平衡时，这种"成块排序"可能让模型偏向最后见到的类别。稳妥起见应在返回前 shuffle 一下训练下标。

### 3.4 `cross_validate`：用工厂函数保证"每折一个新模型"

```python
def cross_validate(X, y, model_fn, k=5, metric_fn=None, stratified=False):
    n = len(X)

    if stratified:
        folds = stratified_kfold_split(y, k)
    else:
        folds = kfold_split(n, k)

    scores = []
    for train_idx, val_idx in folds:
        # ... 按下标取出 X_train, y_train, X_val, y_val
        model = model_fn()
        model.fit(X_train, y_train)
        predictions = [model.predict(x) for x in X_val]

        if metric_fn:
            score = metric_fn(y_val, predictions)
        else:
            score = sum(1 for yt, yp in zip(y_val, predictions) if yt == yp) / len(y_val)
        scores.append(score)

    return scores
```

- **为什么传 `model_fn`（一个返回新模型的函数）而不是传模型对象？** 如果传同一个对象，第 2 折会在第 1 折训练好的权重上继续训练，信息就在折之间泄漏了。演示中写成 `model_fn=lambda: SimpleLogistic(lr=0.1, epochs=200)`，每调用一次就得到一个全新的模型。sklearn 的做法是 `clone(estimator)`，目的相同。
- `metric_fn` 可插拔：默认是准确率，演示里显式传了 `accuracy`；换成 `f1_score` 就能做"F1 交叉验证"。
- 返回**每折的分数列表**而不是均值：调用方既能算均值，也能算标准差、做配对检验。
- ⚠️ 这里没有任何预处理步骤。如果要标准化，必须**在循环内部、只用当前折的训练集**拟合 scaler——这正是 sklearn `Pipeline` + `cross_val_score` 的价值。

### 3.5 混淆矩阵与 P / R / F1

```python
def confusion_matrix(y_true, y_pred):
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)
    return tp, tn, fp, fn


def precision(y_true, y_pred):
    tp, tn, fp, fn = confusion_matrix(y_true, y_pred)
    return tp / (tp + fp) if (tp + fp) > 0 else 0.0


def f1_score(y_true, y_pred):
    p = precision(y_true, y_pred)
    r = recall(y_true, y_pred)
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0
```

| 指标 | 公式 | 回答的问题 |
|------|------|-----------|
| Accuracy | (TP+TN)/全部 | 总体判对了多少 |
| Precision | TP/(TP+FP) | 报为正的里面，有多少真是正 |
| Recall | TP/(TP+FN) | 真正的正样本，找回了多少 |
| F1 | 2PR/(P+R) | P 与 R 的调和平均，任一很低则 F1 很低 |

- `sum(1 for ... if ...)` 是"数满足条件的元素个数"的惯用写法，不创建中间列表。
- **分母为 0 的约定**：没有任何样本被判为正时 precision 无定义，这里返回 0.0（sklearn 的 `zero_division` 参数默认也是给 0 并警告）。这让"永远预测负"的基线的 precision、recall、F1 全为 0，正好暴露它的无用。
- ⚠️ 只支持标签为 0/1 的二分类。多分类需要逐类计算再做 macro / micro / weighted 平均。
- ⚠️ `f1_score` 内部调用 `precision` 和 `recall`，各自又调一次 `confusion_matrix`，同一份数据被扫描了两遍。演示规模无所谓，大数据上应先算一次混淆矩阵再派生所有指标。

### 3.6 `roc_curve` 与 `auc_roc`：扫阈值 + 梯形积分

```python
def roc_curve(y_true, y_scores):
    thresholds = sorted(set(y_scores), reverse=True)
    # ...
    total_positives = sum(y_true)
    total_negatives = len(y_true) - total_positives

    for threshold in thresholds:
        y_pred = [1 if s >= threshold else 0 for s in y_scores]
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)

        tpr = tp / total_positives if total_positives > 0 else 0.0
        fpr = fp / total_negatives if total_negatives > 0 else 0.0
        # ... 追加到列表
    return fpr_list, tpr_list, thresholds
```

- 用**每个不同的分数**当阈值（`sorted(set(...), reverse=True)`），从高到低扫：阈值越低，判为正的越多，TPR 和 FPR 都单调不减，点从左下走向右上，最低阈值时所有样本判正，得到 (1, 1)。
- `sum(y_true)` 在 0/1 标签下就是正样本数，一个小技巧。
- 复杂度：每个阈值都重扫全部样本，O(n²)。高效实现是按分数排序后一次扫描累加计数，O(n log n)。

```python
def auc_roc(y_true, y_scores):
    fpr_list, tpr_list, _ = roc_curve(y_true, y_scores)

    pairs = sorted(zip(fpr_list, tpr_list))
    fpr_sorted = [p[0] for p in pairs]
    tpr_sorted = [p[1] for p in pairs]

    area = 0.0
    for i in range(1, len(fpr_sorted)):
        width = fpr_sorted[i] - fpr_sorted[i - 1]
        height = (tpr_sorted[i] + tpr_sorted[i - 1]) / 2
        area += width * height

    return area
```

- 梯形法：相邻两点之间的面积 = 宽 × 上下底平均。
- ⚠️ **缺少起点 (0, 0)**：曲线从"最高分数作阈值"那一点开始。如果最高分上有正负样本**并列**，第一个点就是 (FPR>0, TPR>0)，从原点到它的那块面积被漏掉。例如 `auc_roc([1, 0, 1, 0], [0.9, 0.9, 0.5, 0.1])` 返回 0.5，而按定义（或 sklearn `roc_auc_score`）应为 0.625。演示中的分数是连续值、几乎不会并列，所以结果 0.9408 不受影响。修复方法是积分前加上 `(0.0, 0.0)`，详见测验 Q10。
- 与讲义对应：AUC = 0.5 是随机排序，1.0 是完美排序，**与阈值无关**——因为它把所有阈值都扫了一遍。

### 3.7 回归指标

```python
def r_squared(y_true, y_pred):
    mean_y = sum(y_true) / len(y_true)
    ss_res = sum((yt - yp) ** 2 for yt, yp in zip(y_true, y_pred))
    ss_tot = sum((yt - mean_y) ** 2 for yt in y_true)
    if ss_tot == 0:
        return 0.0
    return 1.0 - ss_res / ss_tot
```

- `mse` 是残差平方的均值，`rmse = math.sqrt(mse(...))` 回到目标的单位，`mae` 是残差绝对值的均值。
- R² 的分母 `ss_tot` 正是"永远预测 `mean_y`"这个基线的平方误差和，所以 R² 衡量的是"比均值基线好多少"。模型比基线还差时 R² < 0，没有下界。
- `if ss_tot == 0`：目标全是同一个值时方差为 0，R² 无定义，这里约定返回 0.0，避免除零。
- 注意 `mean_y` 用的是**传入的 y_true（即测试集）的均值**，这就是为什么用训练集均值做的基线 R² 是 −0.0013 而不是 0（见第 6 节）。

### 3.8 `learning_curve`：固定验证集，逐步加训练数据

```python
    val_size = int(n * val_ratio)
    val_idx = indices[:val_size]
    pool_idx = indices[val_size:]
    # ...
    if train_sizes is None:
        train_sizes = [int(len(pool_idx) * r) for r in [0.1, 0.2, 0.4, 0.6, 0.8, 1.0]]
    # ...
    for size in train_sizes:
        subset = pool_idx[:size]
        # ... 训练新模型
        train_pred = [model.predict(x) for x in X_train]
        val_pred = [model.predict(x) for x in X_val]
```

- **验证集固定不变**，只改变训练集大小，这样不同点之间的差异只来自"数据量"这一个变量（控制变量法）。
- `pool_idx[:size]` 取前缀，所以小的训练集是大训练集的子集——曲线更平滑，不会因为"换了一批样本"而跳动。
- 每个点都同时算训练分数和验证分数：两条线的**高低**看偏差，两条线的**差距**看方差。
- ⚠️ 每个训练规模只训练一次，没有像 sklearn 的 `learning_curve` 那样在每个规模上再做 CV，所以单点噪声较大（验证集只有 60 个样本，1 个样本 = 1.67%）。

### 3.9 两个最小模型：`SimpleLogistic` 与 `SimpleLinearRegression`

```python
class SimpleLogistic:
    # ...
    def sigmoid(self, z):
        z = max(-500, min(500, z))
        return 1.0 / (1.0 + math.exp(-z))

    def fit(self, X, y):
        n_features = len(X[0])
        self.weights = [0.0] * n_features
        self.bias = 0.0

        for _ in range(self.epochs):
            for xi, yi in zip(X, y):
                z = sum(w * x for w, x in zip(self.weights, xi)) + self.bias
                pred = self.sigmoid(z)
                error = yi - pred
                for j in range(n_features):
                    self.weights[j] += self.lr * error * xi[j]
                self.bias += self.lr * error
```

- 逐样本 SGD：`error = y − σ(z)` 正是交叉熵损失对 z 的负梯度，所以 `w += lr · error · x` 就是梯度下降的一步。
- `max(-500, min(500, z))` 是夹紧：`math.exp(-z)` 在 z ≈ −710 以下会抛 `OverflowError`，夹到 ±500 既安全又不影响结果（σ 已经饱和为 0 或 1）。
- `fit` 开头把权重**重置为 0**：即使误用同一个对象多次 fit，也不会继承上一次的权重。这是 `cross_validate` 正确性的第二道保险。
- 提供 `predict_proba`（返回概率，用于 AUC）和 `predict`（以 0.5 为阈值返回 0/1，用于混淆矩阵）两个接口——**AUC 必须用连续分数**，用 0/1 预测算出来的 ROC 只有一个拐点。

`SimpleLinearRegression.fit` 中的更新是 `self.weights[j] += self.lr * error * xi[j] / n`：逐样本更新但每步除以 n，一个 epoch 的累计效果约等于"学习率为 lr 的一次全批量梯度下降"。⚠️ 这种写法让学习率与数据量解耦，但也让收敛变慢——所以演示里配合了 `epochs=500`，并且**必须先标准化特征**，否则不同尺度的特征会让固定学习率要么发散要么几乎不动。

### 3.10 演示主程序中的三个"值得挑刺"的地方

**(1) 不平衡数据：准确率为什么会骗人**

```python
    always_negative = [0] * len(y_imb)
    print(f"    Accuracy:  {accuracy(y_imb, always_negative):.4f}")
```

一个什么都没学的基线拿到 95.67% 准确率。这是全节最重要的一课：**先算基线，再谈模型**。

**(2) 回归部分：先标准化后划分（数据泄漏）**

```python
    col0_s, m0, s0 = standardize(col0)
    col1_s, m1, s1 = standardize(col1)
    X_reg_scaled = [[col0_s[i], col1_s[i]] for i in range(len(X_reg))]

    X_tr_r, y_tr_r, X_v_r, y_v_r, X_te_r, y_te_r = train_val_test_split(X_reg_scaled, y_reg)
```

⚠️ `standardize` 用的是**全部 200 个样本**的均值和标准差，之后才划分——正是讲义"常见错误"里点名的 *fitting a scaler on the full dataset before splitting*。返回的 `m0, s0, m1, s1` 也没被使用。本例同分布、只泄漏特征统计量，数值影响很小（改正后 R² ≈ 0.957，见测验 Q11），但写法本身是错误示范。

**(3) 配对 t 检验：用了总体标准差**

```python
    diffs = [a - b for a, b in zip(model_a_scores, model_b_scores)]
    mean_diff = sum(diffs) / len(diffs)
    std_diff = math.sqrt(sum((d - mean_diff) ** 2 for d in diffs) / len(diffs))
    t_stat = mean_diff / (std_diff / math.sqrt(len(diffs))) if std_diff > 0 else 0.0
```

- 设计亮点：两次 `cross_validate` 都走 `kfold_split(300, 5, seed=42)`，折完全相同，所以可以逐折相减做**配对**检验，消除"某折本身更难"的影响。
- ⚠️ 配对 t 统计量应使用样本标准差（除以 `n − 1`），这里除以 `n`，会把 t 放大约 √(5/4) ≈ 1.118 倍，在临界值附近可能把"不显著"误判成"显著"。打印的临界值 2.78（df=4、双侧 0.05，精确值 2.776）本身是对的。
- ⚠️ `std_diff == 0` 时一律返回 0.0：若各折差值都相同且非零，其实是"差异非常一致"，返回 0 会误导。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 划分函数只返回下标 | 省内存；同一组折可被多个模型复用（配对检验） | sklearn 的 `KFold.split` 同样返回下标生成器 |
| 每个划分函数内 `random.seed(seed)` | 结果可复现，两次 CV 折相同 | 修改全局随机状态；生产中用 `random.Random(seed)` 或 `np.random.default_rng` |
| 余数全给最后一折 | 实现最简单 | 折大小不均；sklearn 把余数分摊到前几折 |
| `model_fn` 工厂函数 | 每折全新模型，杜绝折间泄漏 | sklearn 用 `clone(estimator)` |
| 指标函数统一签名 `metric_fn(y_true, y_pred)` | 可插拔，CV / 学习曲线都能复用 | sklearn 用 `scoring` 字符串或 `make_scorer` |
| 分母为 0 时返回 0.0 | 避免崩溃，让无用基线得分为 0 | sklearn 提供 `zero_division` 参数并发出警告 |
| ROC 用每个唯一分数做阈值，O(n²) | 直观，和定义一一对应 | 排序后一次扫描 O(n log n)，并补上 (0,0) 起点 |
| 纯 Python + 逐样本 SGD 模型 | 无依赖、每一步都可见 | 慢；生产用 sklearn / NumPy 向量化实现 |
| 演示中先标准化再划分 | 写起来省事 | **是泄漏**；应在训练集上 fit、再 transform 其他集合，或用 `Pipeline` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def kfold_split(n, k=5, seed=42)` | 调用时可省略；常用于超参数和随机种子 |
| 多返回值 / 元组解包 | `return tp, tn, fp, fn`；`tp, tn, fp, fn = confusion_matrix(...)` | 函数返回元组，接收端一次拆成多个变量 |
| `_` 占位变量 | `for _ in range(self.epochs)`；`fpr_list, tpr_list, _ = roc_curve(...)` | 约定俗成表示"这个值我不用" |
| 列表推导式 | `[X[i] for i in train_idx]` | 按下标批量取元素 |
| 生成器表达式 + `sum` | `sum(1 for yt, yp in zip(...) if yt == 1 and yp == 1)` | 计数满足条件的元素，不建中间列表 |
| `zip` | `zip(y_true, y_pred)` | 把真实值与预测值逐位配对 |
| `enumerate` | `for i, label in enumerate(y)` | 同时拿到下标和值 |
| 切片与拼接 | `indices[:start] + indices[end:]` | 去掉中间一段，剩下两截拼成训练集 |
| 列表重复 | `[0.0] * n_features`；`[0] * len(y_imb)` | 生成定长初始列表（元素为不可变对象时安全） |
| 条件表达式 | `end = start + fold_size if i < k - 1 else n` | 一行 if/else 赋值 |
| 字典 `setdefault` | `class_indices.setdefault(label, []).append(i)` | 键不存在时先插入默认值，再返回它 |
| 字典列表 | `[{"train": [], "val": []} for _ in range(k)]` | 每折一个独立字典（用推导式而非 `* k`，避免共享同一对象） |
| `sorted(set(...), reverse=True)` | `sorted(set(y_scores), reverse=True)` | 去重后降序排列 |
| `lambda` | `model_fn=lambda: SimpleLogistic(lr=0.1, epochs=200)` | 匿名函数；这里当作"模型工厂" |
| 真值判断 | `if metric_fn:` | `None` 为假，传了函数为真 |
| 夹紧（clamp） | `max(-500, min(500, z))` | 把数值限制在区间内，防止 `math.exp` 溢出 |
| `class` / `__init__` / 实例属性 | `self.weights = None` | 用 `None` 表示"尚未训练" |
| `random` 模块 | `random.seed`、`random.shuffle`、`random.gauss`、`random.uniform`、`random.random` | 设种子、原地打乱、正态/均匀采样 |
| f-string 格式符 | `f"{auc:.4f}"`、`f"{s:>6} {tr:>8.4f}"`、`f"{positives/len(y_imb)*100:.1f}%"` | `.4f` 保留 4 位小数；`>6` 右对齐占 6 格，用来打印对齐的表格 |
| `round` | `[round(s, 4) for s in cv_scores]` | 打印列表时控制小数位数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行演示，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（在临时副本中执行 `python3 evaluation.py`，约 2 秒）的关键输出：

```text
=== Train/Validation/Test Split ===
  Train: 180, Val: 60, Test: 60
  Train class distribution: 91/180 positive
  Val class distribution: 29/60 positive

=== Classification Metrics ===
  Confusion matrix: TP=24, TN=25, FP=3, FN=8
  Accuracy:  0.8167
  Precision: 0.8889
  Recall:    0.7500
  F1 Score:  0.8136
  AUC-ROC:   0.9408
```

- 测试集共 32 个正样本（24+8）、28 个负样本（25+3）。模型偏保守：误报只有 3 个，但漏了 8 个正样本，所以 precision 0.89 高于 recall 0.75。
- AUC 0.94 明显高于准确率 0.82：说明模型**排序能力**很好，只是 0.5 这个阈值偏高。把阈值调低能换来更高的 recall——这就是"AUC 与阈值无关"的直观体现。

```text
=== K-Fold Cross-Validation (K=5) ===
  Fold scores: [0.85, 0.9167, 0.9, 0.8833, 0.8167]
  Mean: 0.8733 (+/- 0.0359)

=== Stratified K-Fold Cross-Validation (K=5) ===
  Fold scores: [0.8305, 0.9322, 0.9322, 0.7797, 0.9062]
  Mean: 0.8762 (+/- 0.0610)
```

- 单次 hold-out 准确率 0.8167，而 5 折均值 0.8733——**单次划分的估计很不稳定**，换一个划分就可能差 5 个百分点，这正是 CV 存在的意义。
- 分层版的标准差反而更大（0.061 vs 0.036）。不要误以为分层"变差了"：这份数据正负几乎 1:1，分层的好处体现不出来，而每折只有约 60 个样本，标准差本身就有很大的随机性。分层的价值在 Q8 那种 2% 正样本的数据上才明显。`+/-` 后是总体标准差（除以 n）。

```text
=== Imbalanced Data: Why Accuracy Lies ===
  Class distribution: 13 positive, 287 negative (4.3% positive)
  Always-negative baseline:
    Accuracy:  0.9567
    Precision: 0.0000
    Recall:    0.0000
    F1 Score:  0.0000

  Trained model on imbalanced data:
    Accuracy:  0.9833
    Precision: 0.7500
    Recall:    1.0000
    F1 Score:  0.8571
```

- 基线"永远预测负"准确率 95.67%，但 P/R/F1 全是 0。
- 训练后的模型准确率 98.33%，看上去只比基线高 2.7 个百分点，但 F1 从 0 提升到 0.857——**准确率掩盖了真正的提升**。
- 注意测试集 60 个样本里只有 3 个正样本（recall = 1.0、precision = 0.75 对应 TP=3、FP=1）。这么小的正样本数，指标波动极大，生产中需要更多数据或给出置信区间。

```text
=== Regression Metrics ===
  MSE:       4.9442
  RMSE:      2.2235
  MAE:       1.8974
  R-squared: 0.9560

  Mean baseline:
    MSE:       112.6230
    R-squared: -0.0013
```

- 数据生成时噪声为 `random.gauss(0, 2)`，即不可约误差的方差为 4、标准差为 2。模型 RMSE 2.22 已经接近噪声下限，说明线性模型几乎把可学的部分学完了。
- MAE < RMSE 是必然的（RMSE ≥ MAE 恒成立），两者差距越大说明误差分布越"长尾"。
- 基线 R² 为 −0.0013：基线用的是**训练集**均值，而 `r_squared` 内部用**测试集**均值作参照，二者略有差异，所以略低于 0。

```text
=== Learning Curve ===
    Size    Train      Val
      24   1.0000   0.8500
      48   0.9167   0.8167
      96   0.9062   0.8167
     144   0.9028   0.8167
     192   0.8906   0.8500
     240   0.8792   0.8500
```

- 只有 24 个样本时训练准确率 100%、验证 85%：小数据上模型"背住"了训练集。
- 随着样本增加，训练分数下降、两条线收敛到 0.85–0.88 附近，差距只剩约 0.03。数据标签含 `gauss(0, 0.5)` 噪声，线性模型的上限大致就在这里——此时**再加数据帮助有限**，要提升需更好的特征或接受噪声上限。
- 验证集只有 60 个样本，0.8167 和 0.8500 只差 2 个样本，不要过度解读中间的小起伏。

```text
=== Statistical Model Comparison ===
  Model A (100 epochs) mean: 0.8733
  Model B (500 epochs) mean: 0.8733
  Mean difference: 0.0000
  Paired t-statistic: 0.0000
  (|t| > 2.78 for significance at p<0.05 with df=4)
```

- 两个模型 5 折分数**逐折完全相同**：100 个 epoch 时决策边界已经收敛，再训练 400 个 epoch 只是微调权重，没有改变任何一个验证样本的预测类别。差值全为 0，于是走了 `std_diff > 0` 的 else 分支，t = 0。
- 结论：两者无差异，应选更便宜的模型 A。实测把模型 B 换成 `lr=0.00001, epochs=1` 这种极度欠训练的配置，准确率也几乎不变——零初始化的逻辑回归只要一次 SGD 遍历，权重**方向**就已基本正确，而准确率只取决于方向。若想看到检验真正起作用，可以让模型 B 只使用第一个特征（写一个子类，在 `fit` / `predict_proba` 中只取 `x[0]`），实测差值约 0.15，用样本标准差算出的 t ≈ 5.3，远大于 2.78。

---

## 7. 动手改一改

1. **修 AUC**：在 `auc_roc` 里补上 `(0.0, 0.0)` 起点，用 `auc_roc([1, 0, 1, 0], [0.9, 0.9, 0.5, 0.1])` 验证结果从 0.5 变成 0.625；再写一个按"正负样本对"定义计算的 `auc_rank` 做对拍。
2. **修泄漏**：把回归演示改成"先划分 → 在训练集上算均值/标准差 → transform 验证集和测试集"，对比前后的 MSE 与 R²。
3. **修 t 检验**：把 `std_diff` 的分母改成 `len(diffs) - 1`，并把 `std_diff == 0` 时的返回值改得更合理；再把模型 B 换成只用第一个特征的版本，看看 t 值。
4. **加 PR 曲线**：仿照 `roc_curve` 写 `pr_curve`，计算 Average Precision；在 `make_imbalanced_data` 上对比 ROC-AUC 和 PR-AUC，体会讲义练习 1 所说"哪个更能反映少数类表现"。
5. **改进分层**：让 `stratified_kfold_split` 把余数分摊到各折，并在返回前打乱每折的训练下标；当某类样本数 < k 时打印警告。
6. **嵌套交叉验证**（讲义练习 2）：外层 5 折评估，内层 3 折从 `lr ∈ {0.01, 0.1, 0.5}` 中选最优，对比"直接用 5 折 CV 选超参再报告该分数"得到的数字是否偏高。

---

## 8. 常见坑

- **先预处理后划分**：标准化、缺失值填充、特征选择都必须只在训练集（或 CV 的每个训练折）上 fit。本文件的回归演示就犯了这个错。
- **用 0/1 预测算 AUC**：AUC 需要连续分数（`predict_proba`）。用硬标签算出来的 ROC 只有一个拐点，AUC 退化成 (TPR + TNR) / 2（即 balanced accuracy），丢失了排序信息。
- **ROC 漏掉 (0,0) 起点**：分数有并列（例如树模型、取整后的概率）时 AUC 会算错。
- **复用同一个模型对象做 CV**：如果模型的 `fit` 不重置参数，第 k 折会继承前一折的权重。用工厂函数或 `clone`。
- **样本标准差用错分母**：做 t 检验、置信区间时要用 `n − 1`；本文件打印 CV 的 `+/-` 用的是 `n`，仅作描述可以，做推断不行。
- **`int()` 截断浮点数**：`int(100 * 0.29)` 得 28 而不是 29。本文件让测试集取"剩下的全部"规避了丢样本，但各集合的大小可能和你预期的差 1。
