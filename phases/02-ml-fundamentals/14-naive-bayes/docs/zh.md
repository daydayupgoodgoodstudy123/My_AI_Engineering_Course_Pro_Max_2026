<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="naive-bayes"></a>

# 朴素贝叶斯

> “天真的”假设是错误的，但无论如何它都是有效的。这就是它的美妙之处。

**类型：** 构建
**语言：** Python
**先决条件：** 第 2 阶段，第 01-07 课（分类、贝叶斯定理）
**时间：** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 使用拉普拉斯平滑从头开始实施多项式朴素贝叶斯以进行文本分类
- 解释为什么朴素的独立性假设在数学上是错误的，但在实践中却产生了正确的班级排名
- 比较多项式、伯努利和高斯朴素贝叶斯变体，并为给定的 feature 类型选择正确的变体
- 评估朴素贝叶斯与高维稀疏数据上的逻辑回归，并解释工作中的偏差-方差权衡

<a id="the-problem"></a>

## 问题

您需要对文本进行分类。电子邮件分为垃圾邮件或非垃圾邮件。客户评价分为正面或负面。支持门票分类。您有数千个 features（每个字一个）和有限的训练数据。

大多数分类器都在这里窒息。逻辑回归需要足够的样本来可靠地估计数千个 weights。决策树一次分裂一个单词，并且过度拟合。 10,000 维的 KNN 没有意义，因为每个点与其他点的距离相等。

朴素贝叶斯处理这个问题。它做出了一个数学上错误的假设（即每个 feature 都独立于给定类别的每个其他 feature），并且它在文本分类方面仍然优于“更智能”的模型，尤其是在训练集较小的情况下。它通过数据进行一次训练。它可扩展到数百万个 features。它产生概率估计（尽管由于独立性假设而经常校准不佳）。

理解为什么错误的假设会导致良好的预测，可以教会您一些关于机器学习的基本知识：最好的模型不是最正确的模型，而是对数据具有最佳偏差-方差权衡的模型。

<a id="the-concept"></a>

## 概念

<a id="bayes-theorem-quick-review"></a>

### 贝叶斯定理（快速回顾）

贝叶斯定理翻转条件概率：

```
P(class | features) = P(features | class) * P(class) / P(features)
```

我们想要 `P(class | features)`——给定文档中的单词，该文档属于某个类的概率。我们可以通过以下方式计算：
- `P(features | class)` -- 在此类文档中看到这些单词的可能性
- `P(class)`——该类别的先验概率（垃圾邮件一般有多常见？）
- `P(features)` -- 证据，所有类都相同，所以我们在比较时可以忽略它

`P(class | features)` 最高的班级获胜。

<a id="the-naive-independence-assumption"></a>

### 天真的独立假设

计算 `P(features | class)` 恰好需要估计所有 features 的联合概率。对于 10,000 个单词的 vocabulary，您需要估计超过 2^10,000 种可能组合的分布。不可能的。

天真的假设：每个 feature 在给定类别的情况下都是条件独立的。

```
P(w1, w2, ..., wn | class) = P(w1 | class) * P(w2 | class) * ... * P(wn | class)
```

您不是估计一个不可能的联合分布，而是估计 n 个简单的每 feature 分布。每个人只需要数一数。

这种假设显然是错误的。 “机器”和“学习”这两个词在任何文档中都不是独立的。但分类器不需要正确的概率估计。它需要正确的排名——哪个类别的概率最高。独立性假设引入了系统误差，但这些误差对所有类别的影响相似，因此排名保持正确。

<a id="why-it-still-works"></a>

### 为什么它仍然有效

三个原因：

1. **排名高于calibration.** 分类只需要排名靠前的类别是正确的。即使真实概率为 0.7 时 P(spam) = 0.99999，分类器仍然可以正确挑选垃圾邮件。我们不需要正确的概率。我们需要正确的获胜者。

2. **高偏差，低方差。** 独立性假设是强先验。它严重限制了模型，从而阻止了 overfitting。在训练数据有限的情况下，稍微错误但稳定的模型会击败理论上正确但极不稳定的模型。这就是实际中的偏差-方差权衡。

3. **Feature冗余抵消。**相关features提供冗余证据。分类器会重复计算该证据，但也会重复计算正确的类别。如果“机器”和“学习”总是一起出现，那么两者都为“科技”类别提供了证据。 NB 对它们进行了两次计数，但它对正确的类进行了两次计数。

第四个实际原因：朴素贝叶斯速度极快。训练是对数据计数频率的单次传递。预测是矩阵乘法。您可以在几秒钟内训练一百万个文档。这种速度意味着与较慢的模型相比，您可以更快地迭代，尝试更多的 feature 集，并运行更多的实验。

<a id="the-math-step-by-step"></a>

### 一步一步的数学

让我们通过一个具体的例子来说明trace。假设我们有两类：垃圾邮件和非垃圾邮件。我们的vocabulary有三个字：“免费”、“钱”、“会”。

训练数据：
- 垃圾邮件提及“免费”80 次、“金钱”60 次、“会议”10 次（总共 150 个单词）
- 非垃圾邮件提及“免费”5 次、“金钱”10 次、“会议”100 次（总共 115 个单词）
- 40% 的电子邮件是垃圾邮件，60% 的电子邮件不是垃圾邮件

使用拉普拉斯平滑（alpha=1）：

```
P(free | spam)    = (80 + 1) / (150 + 3) = 81/153 = 0.529
P(money | spam)   = (60 + 1) / (150 + 3) = 61/153 = 0.399
P(meeting | spam) = (10 + 1) / (150 + 3) = 11/153 = 0.072

P(free | not-spam)    = (5 + 1) / (115 + 3) = 6/118 = 0.051
P(money | not-spam)   = (10 + 1) / (115 + 3) = 11/118 = 0.093
P(meeting | not-spam) = (100 + 1) / (115 + 3) = 101/118 = 0.856
```

新邮件包含：“免费”（2次）、“金钱”（1次）、“会议”（0次）。

```
log P(spam | email) = log(0.4) + 2*log(0.529) + 1*log(0.399) + 0*log(0.072)
                    = -0.916 + 2*(-0.637) + (-0.919) + 0
                    = -3.109

log P(not-spam | email) = log(0.6) + 2*log(0.051) + 1*log(0.093) + 0*log(0.856)
                        = -0.511 + 2*(-2.976) + (-2.375) + 0
                        = -8.838
```

垃圾邮件以很大优势获胜。 “免费”一词出现两次是垃圾邮件的有力证据。请注意，“会议”未出现对两个对数和的贡献均为零 (0 * log(P))——在多项式 NB 中，缺失的单词没有影响。伯努利 NB 明确地模拟了单词缺失。

<a id="three-variants"></a>

### 三种变体

朴素贝叶斯分为三种类型。每个型号 `P(feature | class)` 都不同。

<a id="multinomial-naive-bayes"></a>

#### 多项式朴素贝叶斯

将每个 feature 建模为计数。最适合 features 是词频或 TF-IDF 值的文本数据。

```
P(word_i | class) = (count of word_i in class + alpha) / (total words in class + alpha * vocab_size)
```

`alpha` 是拉普拉斯平滑（如下所述）。该变体是文本分类的主力。

<a id="gaussian-naive-bayes"></a>

#### 高斯朴素贝叶斯

将每个 feature 建模为正态分布。最适合连续 features。

```
P(x_i | class) = (1 / sqrt(2 * pi * var)) * exp(-(x_i - mean)^2 / (2 * var))
```

根据 feature，每个类别都有自己的均值和方差。当 features 真正遵循每个类别中的钟形曲线时，这种方法效果很好。

<a id="bernoulli-naive-bayes"></a>

#### 伯努利朴素贝叶斯

将每个 feature 建模为二进制（存在或不存在）。最适合短文本或二进制 feature 向量。

```
P(word_i | class) = (docs in class containing word_i + alpha) / (total docs in class + 2 * alpha)
```

与多项式不同，伯努利明确惩罚缺少单词的情况。如果“免费”通常出现在垃圾邮件中，但此电子邮件中没有，伯努利会将其视为反对垃圾邮件的证据。

<a id="when-to-use-each-variant"></a>

### 何时使用每个变体

| 变体 | Feature型 | 最适合 | 示例 |
|---------|-------------|----------|---------|
| 多项式 | 计数或频率 | 文本分类、词袋 | 垃圾邮件、主题分类 |
| 高斯 | 连续值 | 具有正常的表格数据 features | 虹膜分类、传感器数据 |
| 伯努利 | 二进制 (0/1) | 短文本，二进制 feature 向量 | 垃圾短信，存在/不存在 features |

<a id="laplace-smoothing"></a>

### 拉普拉斯平滑

当某个单词出现在测试数据中但从未出现在特定类别的训练数据中时，会发生什么情况？

没有平滑：`P(word | class) = 0/N = 0`。无论所有其他证据如何，一零乘以整个乘积就得到 `P(class | features) = 0`。一个看不见的词就会破坏整个预测，无论有多少其他证据支持它。

拉普拉斯平滑为每个 feature 计数添加一个小计数 `alpha`（通常为 1）：

```
P(word_i | class) = (count(word_i, class) + alpha) / (total_words_in_class + alpha * vocab_size)
```

当 alpha=1 时，每个单词至少有一个很小的概率。测试电子邮件中出现的“discombobulate”一词不再消除垃圾邮件的可能性。平滑具有贝叶斯解释：它相当于在单词分布上放置均匀的狄利克雷先验。

较高的 alpha 意味着更强的平滑（更均匀的分布）。较低的 alpha 意味着模型更信任数据。 Alpha 是你调的 hyperparameter。

阿尔法的效果：

| 阿尔法 | 效果 | 何时使用 |
|-------|--------|-------------|
| 0.001 | 几乎没有平滑，相信数据 | 非常大的训练集，预计不会有看不见的 features |
| 0.1 | 光平滑 | 大型训练集 |
| 1.0 | 标准拉普拉斯平滑 | 默认起点 |
| 10.0 | 深度平滑，使分布平坦 | 训练集非常小，预计有很多看不见的 features |

<a id="log-space-computation"></a>

### 对数空间计算

乘以数百个概率（每个概率都小于 1）会导致浮点下溢。即使真实值是一个非常小的正数，浮点乘积也会变为零。

解决方案：在日志空间中工作。不要将概率相乘，而是将它们的对数相加：

```
log P(class | x1, x2, ..., xn) = log P(class) + sum_i log P(xi | class)
```

这会将预测转化为点积：

```
log_scores = X @ log_feature_probs.T + log_class_priors
prediction = argmax(log_scores)
```

矩阵乘法。这就是朴素贝叶斯预测如此快的原因——它与单层线性模型的操作相同。

<a id="naive-bayes-vs-logistic-regression"></a>

### 朴素贝叶斯与逻辑回归

两者都是文本的线性分类器。不同之处在于他们的模型。

| 方面 | 朴素贝叶斯 | 逻辑回归 |
|--------|------------|-------------------|
| 类型 | 生成（型号 P(X\|Y)） | 判别式（型号 P(Y\|X)） |
| 培训 | 计数频率 | 优化 loss function |
| 小数据 | 更好（强大的先验帮助） | 更糟糕（不足以估计weights） |
| 大数据 | 更糟糕（错误的假设会造成伤害） | 更好（灵活的边界） |
| Features | 假定独立 | 处理相关性 |
| 速度 | 单次通过，速度非常快 | 迭代优化 |
| Calibration | 可能性很小 | 更好的概率 |

经验法则：从朴素贝叶斯开始。如果您有足够的数据并且 NB 稳定，请切换到逻辑回归。

<a id="classification-pipeline"></a>

### 分类管道

```mermaid
flowchart LR
    A[Raw Text] --> B[Tokenize]
    B --> C[Build Vocabulary]
    C --> D[Count Word Frequencies]
    D --> E[Apply Smoothing]
    E --> F[Compute Log Probabilities]
    F --> G[Predict: argmax P class given words]

    style A fill:#f9f,stroke:#333
    style G fill:#9f9,stroke:#333
```

在实践中，我们在日志空间中工作以避免浮点下溢。我们不是将许多小概率相乘，而是将它们的对数相加：

```
log P(class | features) = log P(class) + sum_i log P(feature_i | class)
```

```figure
naive-bayes
```

<a id="build-it"></a>

## 动手实现

`code/naive_bayes.py`中的代码从头开始实现了MultinomialNB和GaussianNB。

<a id="multinomialnb"></a>

### 多项式NB

从头开始实施：

1. **fit(X, y)**：对于每个类别，统计每个feature的频率。添加拉普拉斯平滑。计算对数概率。存储类别先验（类别频率的日志）。

2. **predict_log_proba(X)**：对于每个样本，计算日志 P(class) + 日志 P(feature_i) 的总和 | 类）适用于所有类。这是一个矩阵乘法：X @ log_probs.T + log_priors。

3. **predict(X)**：返回对数概率最高的类。

```python
class MultinomialNB:
    def __init__(self, alpha=1.0):
        self.alpha = alpha

    def fit(self, X, y):
        classes = np.unique(y)
        n_classes = len(classes)
        n_features = X.shape[1]

        self.classes_ = classes
        self.class_log_prior_ = np.zeros(n_classes)
        self.feature_log_prob_ = np.zeros((n_classes, n_features))

        for i, c in enumerate(classes):
            X_c = X[y == c]
            self.class_log_prior_[i] = np.log(X_c.shape[0] / X.shape[0])
            counts = X_c.sum(axis=0) + self.alpha
            self.feature_log_prob_[i] = np.log(counts / counts.sum())

        return self
```

关键见解：拟合后，预测只是矩阵乘法加上偏差。这就是朴素贝叶斯如此快的原因。

<a id="gaussiannb"></a>

### 高斯NB

对于连续的 features，我们估计每个 feature 每个类的均值和方差：

```python
class GaussianNB:
    def __init__(self):
        pass

    def fit(self, X, y):
        classes = np.unique(y)
        self.classes_ = classes
        self.means_ = np.zeros((len(classes), X.shape[1]))
        self.vars_ = np.zeros((len(classes), X.shape[1]))
        self.priors_ = np.zeros(len(classes))

        for i, c in enumerate(classes):
            X_c = X[y == c]
            self.means_[i] = X_c.mean(axis=0)
            self.vars_[i] = X_c.var(axis=0) + 1e-9
            self.priors_[i] = X_c.shape[0] / X.shape[0]

        return self
```

预测使用每个 feature 的高斯 PDF，乘以 features（添加到对数空间中）。

<a id="demo-text-classification"></a>

### 演示：文本分类

该代码生成模拟两个类别（科技文章与体育文章）的合成词袋数据。每个类别都有不同的词频分布。 MultinomialNB 使用字数对它们进行分类。

合成数据的工作原理如下：我们创建 200 个“单词”（feature 列）。单词 0-39 在科技文章中出现频率较高，在体育文章中出现频率较低。单词 80-119 在体育领域出现频率较高，在科技领域出现频率较低。单词 40-79 在两者中都是中等频率。这创建了一个现实的场景，其中一些单词是很强的类别指示符，而其他单词则是噪音。

<a id="demo-continuous-features"></a>

### 演示：连续 Features

该代码生成类似 Iris 的数据（3 个类，4 个 features，高斯簇）。 GaussianNB 使用每类均值和方差进行分类。每个类别都有不同的中心（平均向量）和不同的散布（方差），模仿真实世界的数据，其中类别之间的测量值系统地不同。

该代码还演示了：
- **平滑对比：**用不同的alpha值训练MultinomialNB来展示平滑强度对精度的影响。
- **训练规模实验：** 随着训练数据从20个样本增长到1600个样本，NB精度如何提高。即使样本很少，NB 也能达到不错的精度——这是它的主要优势。
- **混淆矩阵：** 每类精确率、召回率和 F1 分数，以显示 NB 在哪里出错。

<a id="prediction-speed"></a>

### 预测速度

朴素贝叶斯预测是矩阵乘法。对于 n 个具有 d features 和 k 个类别的样本：
- MultinomialNB：一个矩阵乘法 (n x d) @ (d x k) = O(n * d * k)
- GaussianNB：n * k 高斯 PDF evaluations，每个超过 d features = O(n * d * k)

两者在每个维度上都是线性的。将此与 KNN（需要到所有训练点的距离计算）或带有 RBF 内核的 SVM（需要针对所有支持向量的内核 evaluation）进行比较。 NB 在预测时要快几个数量级。

<a id="use-it"></a>

## 实际应用

对于 sklearn，两种变体都是单行代码：

```python
from sklearn.naive_bayes import GaussianNB, MultinomialNB

gnb = GaussianNB()
gnb.fit(X_train, y_train)
print(f"GaussianNB accuracy: {gnb.score(X_test, y_test):.3f}")

mnb = MultinomialNB(alpha=1.0)
mnb.fit(X_train_counts, y_train)
print(f"MultinomialNB accuracy: {mnb.score(X_test_counts, y_test):.3f}")
```

对于使用 sklearn 进行文本分类：

```python
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

text_clf = Pipeline([
    ("vectorizer", CountVectorizer()),
    ("classifier", MultinomialNB(alpha=1.0)),
])

text_clf.fit(train_texts, train_labels)
accuracy = text_clf.score(test_texts, test_labels)
```

`naive_bayes.py` 中的代码将相同数据的从头实现与 sklearn 进行比较，以验证正确性。

<a id="tf-idf-with-naive-bayes"></a>

### 带有朴素贝叶斯的 TF-IDF

原始单词计数使每个单词每次出现都等于 weight。但是像“the”和“is”这样的常用词在每个班级中都频繁出现——它们不携带任何信息。 TF-IDF（词频 - 逆文档频率）降低常见单词的权重，提高罕见的、有区别的单词的权重。

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

text_clf = Pipeline([
    ("tfidf", TfidfVectorizer()),
    ("classifier", MultinomialNB(alpha=0.1)),
])
```

TF-IDF 值是非负的，因此它们与 MultinomialNB 一起使用。 TF-IDF + MultinomialNB 的组合是文本分类的最强基线之一。它经常在训​​练样本少于 10,000 个的数据集上击败更复杂的模型。

<a id="bernoullinb-for-short-text"></a>

### BernoulliNB 短文本

对于短文本（推文、短信、聊天消息），BernoulliNB 的性能优于 MultinomialNB。短文本的字数较少，因此 MultinomialNB 依赖的频率信息存在噪声。 BernoulliNB 只关心存在或不存在，对于短文本来说更可靠。

```python
from sklearn.naive_bayes import BernoulliNB
from sklearn.feature_extraction.text import CountVectorizer

text_clf = Pipeline([
    ("vectorizer", CountVectorizer(binary=True)),
    ("classifier", BernoulliNB(alpha=1.0)),
])
```

CountVectorizer 中的 `binary=True` 标志将所有计数转换为 0/1。没有它，BernoulliNB 仍然可以工作，但会看到它不是设计的目的的计数。

<a id="calibrating-nb-probabilities"></a>

### 校准 NB 概率

NB 概率校准不佳。当 NB 说 P(spam) = 0.95 时，真实概率可能是 0.7。如果您需要可靠的概率估计（例如，设置阈值或与其他模型结合），请使用 sklearn 的 CalibrateClassifierCV：

```python
from sklearn.calibration import CalibratedClassifierCV

calibrated_nb = CalibratedClassifierCV(MultinomialNB(), cv=5, method="sigmoid")
calibrated_nb.fit(X_train, y_train)
proba = calibrated_nb.predict_proba(X_test)
```

这使用交叉验证在 NB 的原始分数之上拟合逻辑回归。得到的概率更接近真实的类别频率。

<a id="common-gotchas"></a>

### 常见问题

1. **负 feature 值。** MultinomialNB 需要非负 features。如果您有负值（例如具有某些设置的 TF-IDF 或标准化 features），请改用 GaussianNB，或将 features 更改为正值。

2. **零方差 features.** GaussianNB 除以方差。如果 feature 的类方差为零（所有值相同），则概率计算会中断。该代码向所有方差添加了一个小的平滑项 (1e-9) 以防止出现这种情况。

3. **类别不平衡。** 如果 99% 的电子邮件不是垃圾邮件，则先前的 P(非垃圾邮件) = 0.99 非常强大，以至于压倒了可能性证据。您可以手动设置类先验或在sklearn中使用class_prior parameter。

4. **Feature 缩放。** MultinomialNB 不需要缩放（它适用于计数）。 GaussianNB 也不需要缩放（它估计每个 feature 统计数据）。与对 feature 尺度敏感的逻辑回归和 SVM 相比，这是一个优势。

<a id="ship-it"></a>

## 交付成果

本课产生：
- `outputs/skill-naive-bayes-chooser.md`——选择正确的 NB 变体的决策技巧
- `code/naive_bayes.py` -- 从头开始的 MultinomialNB 和 GaussianNB，与 sklearn 比较

<a id="when-naive-bayes-fails"></a>

### 当朴素贝叶斯失败时

当独立性假设导致不正确的排名（不仅仅是不正确的概率）时，NB 失败。出现这种情况时：

1. **Strong feature 交互。** 如果该类依赖于两个 features 的组合，但不是单独的（类似 XOR 的模式），NB 将完全错过它。每个 feature 本身并不能提供任何证据，并且 NB 无法将它们非线性组合。

2. **features 与相反证据高度相关。** 如果 feature A 说“垃圾邮件”而 feature B 说“非垃圾邮件”，但 A 和 B 完全相关（它们在现实中总是一致），NB在没有证据的情况下会看到相互矛盾的证据。

3. **非常大的训练集。** 有了足够的数据，像逻辑回归这样的判别模型可以学习真实的决策边界，并且表现优于NB。有助于处理小数据的独立性假设现在阻碍了模型的发展。

实际上，这些故障模式对于文本分类来说很少见。文本 features 数量众多，个别较弱，独立性假设的错误往往会被抵消。对于 features 相关性很少的表格数据，首先考虑逻辑回归或基于树的模型。

<a id="exercises"></a>

## 练习

1. **平滑实验。** 在 alpha 值为 0.01、0.1、1.0、10.0 和 100.0 的文本数据上训练 MultinomialNB。绘制准确度与 alpha 的关系图。性能峰值在哪里？为什么过高的阿尔法会造成伤害？

2. **Feature 独立性测试。** 采取真实的文本数据集。选择两个明显相关的词（“机器”和“学习”）。计算 P(word1 | class) * P(word2 | 类）并与 P(word1 AND word2 | 类）。独立性假设有多错误？会影响分类准确率吗？

3. **Bernoulli 实现。** 使用 BernoulliNB 类扩展代码。将词袋转换为二进制（存在/不存在），并将文本数据的准确性与 MultinomialNB 进行比较。伯努利什么时候获胜？

4. **NB 与逻辑回归。** 在文本数据上训练两者。从 100 个训练样本开始，增加到 10,000 个。绘制两者的准确性与训练集大小的关系。逻辑回归在什么时候超越朴素贝叶斯？

5. **垃圾邮件过滤器。** 构建完整的垃圾邮件分类器：标记原始电子邮件文本，构建 vocabulary，创建词袋 features，训练 MultinomialNB，评估精度和召回率（不仅仅是准确性 - 为什么？）。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| 朴素贝叶斯 | 《简单概率分类器》 | 应用贝叶斯定理的分类器，假设 features 在给定类别的情况下是条件独立的 |
| 有条件独立 | “Features 互不影响” | P(A, B \| C) = P(A \| C) * P(B \| C) -- 一旦你了解了 C，了解 B 就不会告诉你关于 A 的任何新信息 |
| 拉普拉斯平滑 | “加一平滑” | 向每个 feature 添加一个小计数，以防止零概率主导预测 |
| 事先 | “在看到数据之前你相信什么” | P(class) -- 观察任何 features 之前每个类别的概率 |
| 可能性 | “数据的拟合程度如何” | P(features \| class) -- 如果该类已知，则观察到这些 features 的概率 |
| 后部 | 《看到数据后你相信什么》 | P(class \| features) -- 观察features后该类的更新概率 |
| 生成模型 | “对数据的生成方式进行建模” | 学习 P(X \| Y) 和 P(Y) 的模型，然后使用贝叶斯定理得到 P(Y \| X) |
| 判别模型 | “对决策边界进行建模” | 直接学习 P(Y \| X) 的模型，无需对 X 的生成方式进行建模 |
| 对数概率 | “避免下溢” | 使用 log P 而不是 P 来防止许多小数的乘积在浮点中变为零 |

<a id="further-reading"></a>

## 进一步阅读

- [scikit-learn 朴素贝叶斯文档](https://scikit-learn.org/stable/modules/naive_bayes.html) -- 所有三个带有数学细节的变体
- [McCallum 和 Nigam，朴素贝叶斯文本分类事件模型的比较 (1998)](https://www.cs.cmu.edu/~knigam/papers/multinomial-aaaiws98.pdf) -- 多项式与伯努利文本的经典比较
- [Rennie 等人，解决朴素贝叶斯文本分类器的不良假设 (2003)](https://people.csail.mit.edu/jrennie/papers/icml03-nb.pdf) -- 对文本 NB 的改进
- [Ng 和 Jordan，论判别式与生成式分类器 (2001)](https://ai.stanford.edu/~ang/papers/nips01-discriminativegenerative.pdf) — 证明 NB 在数据较少的情况下比 LR 收敛得更快
