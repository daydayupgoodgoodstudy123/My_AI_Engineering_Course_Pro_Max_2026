# 代码讲解 · naive_bayes.py

> **所属小节**：阶段 02 · 机器学习基础 · 第 14 节 朴素贝叶斯 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python naive_bayes.py`（无命令行参数，依次运行 5 个演示） ｜ **依赖**：仅 `numpy`（代码中没有 import sklearn）

---

## 1. 这份代码在考察什么

1. **朴素贝叶斯训练 = 计数**：MultinomialNB 的 `fit` 只是按类别加总词频、加平滑、取对数；GaussianNB 的 `fit` 只是按类别算均值和方差。没有任何迭代优化。
2. **预测 = 一次矩阵乘法**：在对数空间里，`log P(c) + Σ xᵢ·log P(wᵢ|c)` 写成 `X @ log θᵀ + log prior`，和线性模型的前向计算一模一样。
3. **数值稳定**：对数空间避免连乘下溢；`predict_proba` 先减最大值再 `exp`（log-sum-exp 技巧）；方差加一个小量防止除零。
4. **变体与数据类型要匹配**：计数数据用 Multinomial，连续数据用 Gaussian，`demo_comparison` 用"故意用错"的方式展示代价。
5. **评估不只看准确率**：最后手写混淆矩阵与每类 precision / recall / F1。

> 一句话：**朴素贝叶斯是"能用 30 行写完、训练只需扫一遍数据"的分类器**，这份代码让你看清它为什么快、在哪里需要小心数值问题。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MultinomialNB` | 类 | 计数特征的 NB：`fit / predict_log_proba / predict_proba / predict / score` | 多项分布 + Laplace 平滑 + 对数空间 |
| `GaussianNB` | 类 | 连续特征的 NB：每类每特征一个均值和方差 | 高斯似然 |
| `make_text_data` | 函数 | 用泊松分布生成"tech / sports"两类词袋数据 | 词频特征 |
| `make_continuous_data` | 函数 | 生成类 Iris 的 3 类 4 维高斯数据 | 连续特征 |
| `train_test_split` / `accuracy` / `print_separator` | 工具函数 | 随机切分、准确率、打印分隔线 | — |
| `demo_multinomial` | 演示 | 文本分类 + 预测概率 + 不同 α 对比 | 平滑强度 |
| `demo_gaussian` | 演示 | 连续特征分类 + 打印学到的参数 | 每类的均值/方差/先验 |
| `demo_comparison` | 演示 | 两种变体分别用在两种数据上 | 变体选择 |
| `demo_training_size` | 演示 | 训练集从 20 增加到 1600 时的准确率 | 小样本优势 |
| `demo_confusion_matrix` | 演示 | 手写混淆矩阵与每类指标 | 评估 |

数据流：`make_*_data` → `train_test_split` → `模型.fit(X_train, y_train)` → `模型.score / predict_proba(X_test)` → 打印。两个模型类互不依赖，接口仿照 sklearn（属性名带下划线后缀，如 `classes_`、`feature_log_prob_`）。

---

## 3. 逐段精讲

### 3.1 `MultinomialNB.fit`：训练就是数数

```python
    def fit(self, X, y):
        if np.any(X < 0):
            raise ValueError("MultinomialNB requires non-negative feature values")
        self.classes_ = np.unique(y)
        n_classes = len(self.classes_)
        n_features = X.shape[1]

        self.class_log_prior_ = np.zeros(n_classes)
        self.feature_log_prob_ = np.zeros((n_classes, n_features))

        for i, c in enumerate(self.classes_):
            X_c = X[y == c]
            self.class_log_prior_[i] = np.log(X_c.shape[0] / X.shape[0])
            counts = X_c.sum(axis=0) + self.alpha
            total = counts.sum()
            self.feature_log_prob_[i] = np.log(counts / total)

        return self
```

- **非负检查**：多项分布描述的是"计数"，负数没有意义；`log θ` 乘以负计数还会把证据方向反过来。提前 `raise ValueError` 比静默给出错误结果好得多。
- `np.unique(y)` 返回**排好序**的类别，后面所有矩阵的第 i 行都对应 `classes_[i]`，预测时再用下标映射回标签。
- `X[y == c]`：布尔掩码选出该类的所有样本。
- **先验**：`log(该类样本数 / 总样本数)`。
- **平滑 + 归一化**：`counts = 该类每个词的总次数 + α`；`total = counts.sum()` 等于"该类总词数 + α·V"（V 是特征数），正好是讲义公式的分母。这里没有显式写 `α·V`，而是先加再求和，两者等价且不容易写错。
- 存的是 **log 概率**，预测时直接用，不必每次重新取对数。
- 我在本地用同样的数据与 `sklearn.naive_bayes.MultinomialNB(alpha=1.0)` 对比，`feature_log_prob_`、`class_log_prior_`、`predict_proba` 全部 `np.allclose` 相等——这个实现与 sklearn 的数学定义完全一致。
- ⚠️ 没有检查 `alpha > 0`。α=0 且某个词在某类中从未出现时，`log 0 = −inf`，矩阵乘法中 `0 × (−inf) = NaN`，整类得分变成 NaN（测验 Q9 有实测）。

### 3.2 预测：矩阵乘法 + log-sum-exp

```python
    def predict_log_proba(self, X):
        return X @ self.feature_log_prob_.T + self.class_log_prior_

    def predict_proba(self, X):
        log_proba = self.predict_log_proba(X)
        log_proba -= log_proba.max(axis=1, keepdims=True)
        proba = np.exp(log_proba)
        proba /= proba.sum(axis=1, keepdims=True)
        return proba

    def predict(self, X):
        log_proba = self.predict_log_proba(X)
        return self.classes_[np.argmax(log_proba, axis=1)]
```

- 形状：`X` 是 (n, d)，`feature_log_prob_.T` 是 (d, k)，乘积 (n, k)，再加形状 (k,) 的先验（广播到每一行）。第 j 列就是 `log P(c_j) + Σᵢ xᵢ·log P(wᵢ|c_j)`。
- ⚠️ 命名上的小偏差：`predict_log_proba` 返回的其实是**未归一化**的联合对数概率 `log P(x, c)`（少了 `−log P(x)`），并不是真正的 `log P(c|x)`。比较大小时没有区别，但它的值不能直接当作对数概率使用。sklearn 中真正的 `predict_log_proba` 会再做一次归一化。
- `predict_proba` 中减去每行最大值是 **log-sum-exp 技巧**：softmax 对整体平移不变，减完后最大项是 `exp(0) = 1`，不会出现 `0/0`。文本里几百个词的对数似然相加，得分到几百上千都很常见，不减最大值的话 `exp(−1200)` 会直接下溢成 0。
- `keepdims=True` 让 `max` / `sum` 的结果保持 (n, 1) 形状，才能按行广播。
- `-=`、`/=` 是**原地操作**，`log_proba` 是 `predict_log_proba` 新算出来的数组，原地修改不会影响模型参数。
- `self.classes_[np.argmax(...)]`：先求每行最大值的下标，再用**花式索引**映射回原始标签（如果标签是字符串也能正确返回）。

### 3.3 `GaussianNB.fit`：每类每特征一个正态分布

```python
class GaussianNB:
    def __init__(self, var_smoothing=1e-9):
        self.var_smoothing = var_smoothing
        # ...

    def fit(self, X, y):
        # ...
        for i, c in enumerate(self.classes_):
            X_c = X[y == c]
            self.means_[i] = X_c.mean(axis=0)
            self.vars_[i] = X_c.var(axis=0) + self.var_smoothing
            self.priors_[i] = X_c.shape[0] / X.shape[0]

        return self
```

- 每个类别得到一行均值、一行方差，参数量是 `2 × k × d + k`，非常少，这是 GaussianNB 在小数据上稳定的原因。
- `X_c.var(axis=0)` 是**有偏方差**（除以 n，NumPy 默认 `ddof=0`），即最大似然估计，与 sklearn 一致。
- `+ var_smoothing`：如果某类某特征所有取值都相同，方差为 0，后面除以方差会得到 inf。加一个小量兜底，对应讲义 Common Gotchas 第 2 条。
- ⚠️ 参数名借用了 sklearn 的 `var_smoothing`，但**含义不同**：这里是加一个绝对值 `1e-9`；sklearn 的 `GaussianNB` 加的是 `var_smoothing × 所有特征中最大的方差`（相对值，实测本数据上 sklearn 的 `epsilon_ ≈ 3.5e-9`）。在本数据上两者预测完全相同，但当特征量级非常大或非常小时，绝对值 `1e-9` 可能起不到作用或者过大。
- 这里存的是**原始先验** `priors_`（不是对数），在 `_log_likelihood` 里再取对数；与 MultinomialNB 存 `class_log_prior_` 的风格不一致，但结果等价。

### 3.4 `GaussianNB._log_likelihood`：高斯对数密度相加

```python
    def _log_likelihood(self, X):
        n_classes = len(self.classes_)
        n_samples = X.shape[0]
        log_proba = np.zeros((n_samples, n_classes))

        for i in range(n_classes):
            diff = X - self.means_[i]
            log_prob_features = (
                -0.5 * np.log(2 * np.pi * self.vars_[i])
                - 0.5 * (diff ** 2) / self.vars_[i]
            )
            log_proba[:, i] = log_prob_features.sum(axis=1) + np.log(self.priors_[i])

        return log_proba
```

- 讲义中的密度公式 `1/√(2π·var) · exp(−(x−μ)²/(2·var))` 取对数后变成 `−½·log(2π·var) − (x−μ)²/(2·var)`，这两项正好对应代码里的两行。**取对数之后不再需要调用 `exp`**，既快又不会下溢。
- `X - self.means_[i]`：(n, d) 减 (d,)，广播得到每个样本每个特征的偏差；`log_prob_features` 是 (n, d)，`sum(axis=1)` 把 d 个特征的对数似然加起来——这一步"相加"就是朴素独立假设（在原始空间里是"相乘"）。
- 外层只循环 k 个类别，内部全部向量化，复杂度 O(n·d·k)，与讲义 "Prediction Speed" 一致。
- 方差小的特征，`(x−μ)²/var` 项会被放大，一个特征偏离均值就会严重拉低该类得分——这也是 GaussianNB 概率经常非常极端的原因之一（见第 6 部分中的 `P(0)=1.0000`）。

### 3.5 造数据：泊松词袋与类 Iris 高斯簇

```python
def make_text_data(n_samples=1000, n_features=200, seed=42):
    rng = np.random.RandomState(seed)

    tech_words_weight = np.zeros(n_features)
    tech_words_weight[:40] = rng.uniform(3, 10, 40)
    tech_words_weight[40:80] = rng.uniform(0.5, 2, 40)
    tech_words_weight[80:] = rng.uniform(0.1, 1, 120)

    sports_words_weight = np.zeros(n_features)
    sports_words_weight[:40] = rng.uniform(0.1, 1, 40)
    sports_words_weight[40:80] = rng.uniform(0.5, 2, 40)
    sports_words_weight[80:120] = rng.uniform(3, 10, 40)
    sports_words_weight[120:] = rng.uniform(0.1, 1, 80)
    # ...
    X_tech = rng.poisson(tech_words_weight, (n_tech, n_features)).astype(float)
```

| 词的编号 | tech 中的平均次数 | sports 中的平均次数 | 角色 |
|---------|-----------------|-------------------|------|
| 0–39 | 3–10 | 0.1–1 | tech 指示词 |
| 40–79 | 0.5–2 | 0.5–2 | 中性词（噪声） |
| 80–119 | 0.1–1 | 3–10 | sports 指示词 |
| 120–199 | 0.1–1 | 0.1–1 | 低频噪声词 |

- `rng.poisson(lam_array, size)`：`lam` 是长度 200 的数组，会被广播到 `(n, 200)`，每一列用自己的均值抽样。泊松分布正是"单位时间内某事件发生次数"的经典模型，用来模拟词频很自然，而且各个词是**独立**抽样的——数据完全满足朴素假设。
- 最后用同一个 `shuffle_idx` 打乱 X 和 y，保证两者对齐。
- ⚠️ 这份数据**太容易了**：每篇"文档"平均约 362 个词（实测），40 个强指示词的均值相差 3–100 倍，任何样本量下都能 100% 分类正确。所以后面的 α 对比、训练集大小实验全部是 1.0000，**展示不出讲义描述的趋势**（第 7 部分给出改进方法）。

`make_continuous_data` 用 `rng.multivariate_normal(均值, np.diag(方差), n)` 生成三类 4 维数据，均值取自真实 Iris 数据集三个品种的大致数值。⚠️ 协方差矩阵是**对角阵**，即给定类别后 4 个特征严格独立——GaussianNB 的假设在这里完全成立，所以它表现极好；真实 Iris 中花瓣长度与花瓣宽度是强相关的。

### 3.6 `demo_comparison`：故意用错变体

```python
    X_train_pos = X_train - X_train.min(axis=0) + 0.01
    X_test_pos = X_test - X_train.min(axis=0) + 0.01

    mnb2 = MultinomialNB(alpha=1.0)
    mnb2.fit(X_train_pos, y_train)
    mnb_acc2 = mnb2.score(X_test_pos, y_test)
```

- MultinomialNB 不接受负数，所以把连续特征平移成正数。注意测试集用的是**训练集的最小值**，而不是自己的最小值——这正是上一节"只在训练数据上 fit 变换"的原则。
- 平移后 MultinomialNB 只有 0.678，GaussianNB 是 0.989。原因：MultinomialNB 只关心各特征"计数"的**相对比例** θ，而类 Iris 数据的类别差异主要体现在绝对数值和各自的离散程度上，平移又进一步抹平了比例差异。
- Task 1 中两者都是 1.0000，打印 `Winner: MultinomialNB` 只是因为比较用的是 `>=`，平局时偏向前者。
- 另外，在计数数据上用 GaussianNB 也能 100% 正确——再次说明这份文本数据太简单，区分不出变体差异。

### 3.7 `demo_training_size`：固定测试集，逐步加大训练集

```python
    X_full, y_full = make_text_data(n_samples=2000, n_features=200, seed=42)
    X_test_full = X_full[1600:]
    y_test_full = y_full[1600:]

    for n_train in [20, 50, 100, 200, 500, 1000, 1600]:
        X_train = X_full[:n_train]
        y_train = y_full[:n_train]
```

- 测试集固定为最后 400 条，训练集取前 n 条。数据已经打乱过，所以按位置切也是随机的；训练与测试下标不重叠，没有泄漏。
- 设计意图是展示"NB 在 20 条样本时就能达到不错的准确率"。在这份数据上所有规模都是 1.0000。用更难的数据（第 7 部分练习 1），能看到真实的曲线。

### 3.8 `demo_confusion_matrix`：手写混淆矩阵与每类指标

```python
    cm = np.zeros((n_classes, n_classes), dtype=int)
    for true, pred in zip(y_test, y_pred):
        cm[int(true), int(pred)] += 1
    # ...
    for i, name in enumerate(class_names):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
```

- 行是真实类别，列是预测类别。对第 i 类：对角线是 TP；第 i **列**减去 TP 是 FP（别的类被预测成 i）；第 i **行**减去 TP 是 FN（i 类被预测成别的）。
- 每个除法都用条件表达式防止分母为 0。
- `cm[int(true), int(pred)]` 假设标签就是 0..k−1 的整数；`class_names` 硬编码为 `["tech", "sports"]`，只适用于这份数据。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 训练时就存对数概率 | 预测只需矩阵乘法，不用重复取 log | 无 |
| 用 `counts.sum()` 作分母，而不是显式写 `total + α·V` | 写法更不容易出错，结果相同 | 无 |
| `fit` 中检查非负 | 早失败，避免静默错误 | 没有检查 `alpha > 0`，生产代码应补上 |
| `predict_proba` 先减最大值 | 防止 `exp` 下溢导致 0/0 | 也可以直接用 `scipy.special.logsumexp` |
| GaussianNB 方差加绝对小量 1e-9 | 防止零方差除零，代码简单 | sklearn 用相对于最大方差的比例，对特征量级更稳健 |
| GaussianNB 外层循环类别 | k 通常很小，代码直观 | 也可以用三维广播一次算完，但内存占用 O(n·k·d) |
| 合成数据满足独立假设 | 让演示聚焦在算法本身 | 数据过于简单，α、训练集大小、变体对比都看不出差异 |
| 不依赖 sklearn | 纯 NumPy，便于理解 | 讲义说代码会和 sklearn 对比，实际代码里没有这一部分 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类属性初始化为 `None` | `self.classes_ = None` | 表示"尚未训练"；尾部下划线是 sklearn 约定，表示"fit 之后才有的属性" |
| `raise` 抛异常 | `raise ValueError("MultinomialNB requires ...")` | 输入不合法时主动报错 |
| `enumerate` | `for i, c in enumerate(self.classes_)` | 同时拿到下标 i 和类别值 c |
| 列表乘法 | `[0] * n_tech + [1] * n_sports` | 生成 n 个相同元素的列表并拼接 |
| `@` 矩阵乘法 | `X @ self.feature_log_prob_.T` | 等价于 `np.matmul`；`.T` 是转置 |
| 布尔掩码索引 | `X[y == c]` | 选出满足条件的行 |
| 广播 | `X - self.means_[i]`、`+ self.class_log_prior_` | 形状 (n,d) 与 (d,) 自动对齐 |
| `axis` 与 `keepdims` | `log_proba.max(axis=1, keepdims=True)` | 按行聚合并保留维度，便于后续广播 |
| 原地运算符 | `log_proba -= ...`、`proba /= ...` | 直接修改数组，省一次内存分配 |
| 花式索引 | `self.classes_[np.argmax(log_proba, axis=1)]` | 用下标数组一次取出多个元素 |
| `np.any` | `np.any(X < 0)` | 只要有一个元素为 True 就返回 True |
| 随机分布抽样 | `rng.poisson(lam_array, (n, d))`、`rng.multivariate_normal(mean, cov, n)` | 数组形式的参数会被广播 |
| 条件表达式 | `tp / (tp + fp) if (tp + fp) > 0 else 0` | 一行 if/else，常用来防除零 |
| `zip` | `for true, pred in zip(y_test, y_pred)` | 并行遍历两个序列 |
| `str.join` + 生成器 | `", ".join(f"P({c})={proba[i, j]:.4f}" for j, c in enumerate(...))` | 把多段字符串用分隔符拼起来 |
| f-string 格式符 | `f"{alpha:5.2f}"`、`f"{n_train:>12}"`、`f"{'=' * 60}"` | 宽度 5 保留 2 位；右对齐占 12 宽；花括号里可以写表达式 |
| f-string 内的条件表达式 | `{'tech' if proba[i, 0] > proba[i, 1] else 'sports'}` | 花括号里可放任意表达式 |
| 数组 `.round` | `gnb.means_[i].round(3)` | 保留 3 位小数用于打印 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行演示 |

---

## 6. 运行结果解读

实际运行（约 0.2 秒）：

```text
MULTINOMIAL NAIVE BAYES -- TEXT CLASSIFICATION
Training samples: 900 / Test samples: 300 / Features (words): 200
  Train accuracy: 1.0000
  Test accuracy:  1.0000
  Sample 0: P(tech)=1.0000, P(sports)=0.0000 -> tech      ← 概率极端：NB 的典型特征
  alpha= 0.01 ... alpha=10.00 -> test accuracy: 1.0000    ← 数据太简单，α 不起作用

GAUSSIAN NAIVE BAYES -- CONTINUOUS FEATURES
  Train accuracy: 0.9881
  Test accuracy:  0.9823
  Class 0:
    Means: [4.966 3.411 1.391 0.198]                       ← 接近生成时的 [5.0, 3.4, 1.4, 0.2]
    Vars:  [0.0978 0.116  0.0343 0.0107]                   ← 接近 [0.12, 0.14, 0.03, 0.01]
    Prior: 0.347
  Sample 3: P(0)=0.0000, P(1)=0.0289, P(2)=0.9711 -> class 2   ← 类 1 与类 2 有重叠，才出现不那么极端的概率

COMPARISON: MULTINOMIAL vs GAUSSIAN
Task 1: Text data         MultinomialNB: 1.0000  GaussianNB: 1.0000  Winner: MultinomialNB  ← 平局，>= 偏向前者
Task 2: Continuous        MultinomialNB: 0.6778 (shifted to positive)  GaussianNB: 0.9889   ← 变体选错代价很大

NAIVE BAYES vs TRAINING SET SIZE
          20     1.0000   ...   1600     1.0000            ← 仅 20 个样本也是 100%

CONFUSION MATRIX AND PER-CLASS METRICS
   True tech          83           0
 True sports           0          77
      tech: precision=1.0000, recall=1.0000, f1=1.0000
```

解读要点：

- **学到的参数验证了实现**：GaussianNB 学到的均值、方差都非常接近 `make_continuous_data` 里的真实参数，先验约为 1/3。样本量 337 时，方差估计的误差比均值大，这是正常的统计波动。
- **概率极端**：MultinomialNB 对前 5 个样本给出的都是 1.0000 / 0.0000。每篇文档 300 多个词，每个词都贡献一点对数似然差，累加后差值上百，softmax 之后自然是 0 或 1。这正是讲义说的"概率校准差、但排序正确"。
- **类别重叠才有不确定性**：类 Iris 数据中类 0 与其他两类分得很开，类 1、类 2 有重叠，所以只有在 1、2 之间才出现 0.03 / 0.97 这样的概率。
- **大部分演示"满分"**：说明这份合成数据的区分度太高，并不代表 NB 在真实文本上能达到 100%。要观察平滑和样本量的作用，需要更难的数据。
- **与 sklearn 的一致性**（运行脚本之外另行验证）：在 `make_text_data(1200, 200, 42)` 上，本实现的 `MultinomialNB` 与 `sklearn.naive_bayes.MultinomialNB(alpha=1.0)` 的参数和概率完全一致；本实现的 `GaussianNB` 与 sklearn 预测完全一致，方差差异约 `2.5e-9`，来自 `var_smoothing` 含义的不同。

---

## 7. 动手改一改

1. **让数据变难，看到真实趋势**：对词频做二项稀疏化，把每篇文档压缩到平均约 7 个词：
   ```python
   rng = np.random.RandomState(0)
   X_full, y_full = make_text_data(2000, 200, 42)
   X_short = rng.binomial(X_full.astype(int), 0.02).astype(float)
   ```
   用 `X_short` 重跑训练集大小实验。我实测的结果是：20 条样本 0.9625 → 100 条 0.9875 → 1600 条 0.99，可以看到"少量样本就有不错表现，之后缓慢提升"的曲线。再观察不同 α 的差异。
2. **补上参数检查**：在 `MultinomialNB.__init__` 或 `fit` 中检查 `alpha > 0`，否则抛 `ValueError`；再写一个 α=0 的反例验证（会产生 NaN）。
3. **实现 BernoulliNB**：按讲义公式 `(含该词的文档数 + α) / (该类文档数 + 2α)`，注意要计入缺席词的 `log(1−p)`（测验 Q11 有参考实现）。在上面的短文本数据上对比 Multinomial 与 Bernoulli。
4. **加入 sklearn 对比**：讲义说代码会与 sklearn 比较，请自己补上：`np.allclose(mine.feature_log_prob_, sk.feature_log_prob_)`。
5. **支持增量训练**：给 `MultinomialNB` 加 `partial_fit(X, y)`，保存原始的类别计数和词计数，每来一批数据就累加，再重新计算对数概率。思考：为什么判别式的逻辑回归做不到这么简单的增量更新？
6. **自定义先验**：增加 `class_prior` 参数，允许手动指定类别先验，构造一个 99:1 的不平衡数据集，观察先验对预测结果的影响。

---

## 8. 常见坑

- **α=0**：零概率词 → `log 0 = −inf` → 矩阵乘法里 `0 × (−inf) = NaN`，整类得分作废；而 `np.argmax` 会把 NaN 当成最大值返回。
- **把负数特征喂给 MultinomialNB**：标准化后的特征、某些嵌入向量都有负值；本实现会报错，自己写的版本如果没有检查则会给出静默的错误结果。
- **把 `predict_log_proba` 的值当成真正的对数后验**：这里返回的是未归一化的联合对数概率，只能用于比较大小。
- **不减最大值直接 `exp`**：长文本的对数得分很容易到 −1000 以下，`exp` 后全为 0，得到 `0/0 = NaN`。
- **忘记 `keepdims=True`**：形状 (n,) 与 (n, k) 广播时按最后一维对齐，可能报错，也可能静默算错。
- **把 NB 的概率当成可靠的置信度**：概率往往被推到 0 或 1，需要阈值或与其他模型融合时，先用 `CalibratedClassifierCV` 校准。
