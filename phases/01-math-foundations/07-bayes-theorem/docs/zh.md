<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="bayes-theorem"></a>

# 贝叶斯定理

> 概率就是你所期望的。贝叶斯定理是关于你学到的东西。

**类型：** 构建
**语言：** Python
**先决条件：** 第 1 阶段，第 06 课（概率基础）
**时间：** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 应用贝叶斯定理根据先验、可能性和证据计算后验概率
- 使用拉普拉斯平滑和对数空间计算从头开始构建朴素贝叶斯文本分类器
- 比较 MLE 和 MAP 估计并解释 MAP 如何对应于 L2 正则化
- 使用 Beta-二项式共轭先验实施顺序贝叶斯更新进行 A/B 测试

<a id="the-problem"></a>

## 问题

医学测试的准确率是 99%。你测试呈阳性。您实际上患有这种疾病的可能性有多大？

大多数人说99%。真正的答案取决于这种疾病的罕见程度。如果万分之一的人患有此病，则阳性结果仅表明您患病的可能性约为 1%。另外 99% 的阳性结果是健康人的误报。

这不是一个棘手的问题。这就是贝叶斯定理。每个垃圾邮件过滤器、每个医疗诊断、每个量化不确定性的机器学习模型都使用这种精确的推理。你从一个信念开始。你看到证据了。你更新。

如果您在不了解这一点的情况下构建机器学习系统，您将误解模型输出、设置错误的阈值并发布过于自信的预测。

<a id="the-concept"></a>

## 概念

<a id="from-joint-probability-to-bayes"></a>

### 从联合概率到贝叶斯

从第 06 课中您已经知道条件概率是：

```
P(A|B) = P(A and B) / P(B)
```

并且对称地：

```
P(B|A) = P(A and B) / P(A)
```

两个表达式共享相同的分子：P(A 和 B)。将它们设置为相等并重新排列：

```
P(A and B) = P(A|B) * P(B) = P(B|A) * P(A)

Therefore:

P(A|B) = P(B|A) * P(A) / P(B)
```

这就是贝叶斯定理。四个量，一个方程。

<a id="the-four-parts"></a>

### 四个部分

| 部分 | 名称 | 这意味着什么 |
|------|------|---------------|
| P(A\|B) | 后部 | 看到证据 B 后您对 A 的更新信念 |
| P(B\|A) | 可能性 | 如果 A 为真，证据 B 的可能性有多大 |
| P(A) | 事先 | 在看到任何证据之前你对 A 的信念 |
| P(B) | 证据 | 在所有可能性下看到 B 的总概率 |

证据项 P(B) 充当标准化项。您可以使用全概率定律将其展开：

```
P(B) = P(B|A) * P(A) + P(B|not A) * P(not A)
```

<a id="medical-test-example"></a>

### 医学测试示例

疾病影响万分之一的人。该测试的准确度为 99%（发现 99% 的病人，1% 的时间出现假阳性）。

```
P(sick)          = 0.0001     (prior: disease is rare)
P(positive|sick) = 0.99       (likelihood: test catches it)
P(positive|healthy) = 0.01    (false positive rate)

P(positive) = P(positive|sick) * P(sick) + P(positive|healthy) * P(healthy)
            = 0.99 * 0.0001 + 0.01 * 0.9999
            = 0.000099 + 0.009999
            = 0.010098

P(sick|positive) = P(positive|sick) * P(sick) / P(positive)
                 = 0.99 * 0.0001 / 0.010098
                 = 0.0098
                 = 0.98%
```

小于1%。先验占主导地位。当病情罕见时，即使准确的检测也大多会产生误报。这就是医生要求进行确认测试的原因。

<a id="spam-filter-example"></a>

### 垃圾邮件过滤器示例

您收到一封包含“彩票”一词的电子邮件。是垃圾邮件吗？

```
P(spam)                = 0.3      (30% of email is spam)
P("lottery"|spam)      = 0.05     (5% of spam emails contain "lottery")
P("lottery"|not spam)  = 0.001    (0.1% of legitimate emails contain "lottery")

P("lottery") = 0.05 * 0.3 + 0.001 * 0.7
             = 0.015 + 0.0007
             = 0.0157

P(spam|"lottery") = 0.05 * 0.3 / 0.0157
                  = 0.955
                  = 95.5%
```

一个词就能将概率从 30% 提高到 95.5%。真正的垃圾邮件过滤器同时对数百个单词应用贝叶斯。

<a id="naive-bayes-independence-assumption"></a>

### 朴素贝叶斯：独立性假设

朴素贝叶斯通过假设所有 features 是有条件独立的，将其扩展到多个 features：

```
P(class | feature_1, feature_2, ..., feature_n)
  = P(class) * P(feature_1|class) * P(feature_2|class) * ... * P(feature_n|class)
    / P(feature_1, feature_2, ..., feature_n)
```

“天真的”部分是独立性假设。在文本中，单词的出现不是独立的（“New”和“York”是相关的）。但这个假设在实践中效果出人意料地好，因为分类器只需要对类别进行排名，而不需要产生校准概率。

由于所有类别的分母都相同，因此您可以跳过它并仅比较分子：

```
score(class) = P(class) * product of P(feature_i | class)
```

选择得分最高的班级。

<a id="maximum-likelihood-estimation-mle"></a>

### 最大似然估计 (MLE)

如何获得P(feature|类）来自训练数据？数数。

```
P("free"|spam) = (number of spam emails containing "free") / (total spam emails)
```

这就是 MLE：选择使观察到的数据最有可能的 parameter 值。您正在最大化似然函数，对于离散计数，该似然函数会减少到相对频率。

问题：如果训练期间某个单词从未出现在垃圾邮件中，MLE 给出的概率为零。一个看不见的词就会毁掉整个产品。使用拉普拉斯平滑修复此问题：

```
P(word|class) = (count(word, class) + 1) / (total_words_in_class + vocabulary_size)
```

每次计数加 1 可确保概率永远不会为零。

<a id="maximum-a-posteriori-map"></a>

### 最大后验概率 (MAP)

MLE 问：parameters 最大化 P(data|parameters)?

MAP问：什么parameters最大化P(parameters|数据）？

根据贝叶斯定理：

```
P(parameters|data) proportional to P(data|parameters) * P(parameters)
```

MAP 在 parameters 本身之上添加了一个优先级。如果您认为 parameters 应该很小，则可以将其编码为惩罚大值的先验。这与 ML 中的 L2 正则化相同。岭回归中的“岭”惩罚实际上是 weights 上的高斯先验。

| 预估 | 优化 | ML 等效项 |
|------------|-----------|---------------|
| 最大LE | P(data\|params) | 非正规培训 |
| MAP | P(data\|params) * P(params) | L2 / L1 正则化 |

<a id="bayesian-vs-frequentist-the-practical-difference"></a>

### 贝叶斯主义与频率主义：实际差异

频率论者将 parameters 视为固定未知数。他们问：“如果我多次重复这个实验，会发生什么？”

贝叶斯主义者将 parameters 视为分布。他们问：“根据我的观察，我对 parameters 有何看法？”

对于构建机器学习系统，实际差异：

| 方面 | 频率论者 | 贝叶斯 |
|--------|-------------|----------|
| 输出 | 点估计 | 价值分布 |
| 不确定性 | 置信区间（关于程序） | 可信区间（约parameter） |
| 小数据 | 可能会过度拟合 | 先验作为正则化 |
| 计算 | 通常更快 | 通常需要 sampling (MCMC) |

大多数生产机器学习都是频率论的（SGD，点估计）。当您需要校准不确定性（医疗决策、安全关键系统）或数据稀缺（few-shot 学习、冷启动）时，贝叶斯方法会大放异彩。

<a id="why-bayesian-thinking-matters-for-ml"></a>

### 为什么贝叶斯思维对机器学习很重要

这种联系比类比更深刻：

**Priors 是正则化。** weights 上的高斯先验是 L2 正则化。拉普拉斯先验是 L1。每次添加正则化项时，您都会对您期望的 parameter 值做出贝叶斯声明。

**后验是不确定性的。** 单个预测概率无法告诉您模型对该估计的置信度。贝叶斯方法为您提供一个分布：“我认为 P(spam) 在 0.8 到 0.95 之间。”

**贝叶斯更新在线学习。** 今天的后验变成明天的先验。当您的模型看到新数据时，它会逐步更新其信念，而不是从头开始重新训练。

**模型比较是贝叶斯模型。** 贝叶斯信息准则（BIC）、边际似然和贝叶斯因子均使用贝叶斯推理在模型之间进行选择，而无需 overfitting。

```figure
bayes-update
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-bayes-theorem-function"></a>

### 步骤1：贝叶斯定理函数

```python
def bayes(prior, likelihood, false_positive_rate):
    evidence = likelihood * prior + false_positive_rate * (1 - prior)
    posterior = likelihood * prior / evidence
    return posterior

result = bayes(prior=0.0001, likelihood=0.99, false_positive_rate=0.01)
print(f"P(sick|positive) = {result:.4f}")
```

<a id="step-2-naive-bayes-classifier"></a>

### 步骤 2：朴素贝叶斯分类器

```python
import math
from collections import defaultdict

class NaiveBayes:
    def __init__(self, smoothing=1.0):
        self.smoothing = smoothing
        self.class_counts = defaultdict(int)
        self.word_counts = defaultdict(lambda: defaultdict(int))
        self.class_word_totals = defaultdict(int)
        self.vocab = set()

    def train(self, documents, labels):
        for doc, label in zip(documents, labels):
            self.class_counts[label] += 1
            words = doc.lower().split()
            for word in words:
                self.word_counts[label][word] += 1
                self.class_word_totals[label] += 1
                self.vocab.add(word)

    def predict(self, document):
        words = document.lower().split()
        total_docs = sum(self.class_counts.values())
        vocab_size = len(self.vocab)
        best_class = None
        best_score = float("-inf")
        for cls in self.class_counts:
            score = math.log(self.class_counts[cls] / total_docs)
            for word in words:
                count = self.word_counts[cls].get(word, 0)
                total = self.class_word_totals[cls]
                score += math.log((count + self.smoothing) / (total + self.smoothing * vocab_size))
            if score > best_score:
                best_score = score
                best_class = cls
        return best_class
```

对数概率可防止下溢。将许多小概率相乘产生的数字对于浮点来说太小了。对数概率求和在数值上是稳定的并且在数学上是等效的。

<a id="step-3-train-on-spam-data"></a>

### 第 3 步：训练垃圾邮件数据

```python
train_docs = [
    "win free money now",
    "free lottery ticket winner",
    "claim your prize today free",
    "urgent offer free cash",
    "congratulations you won free",
    "meeting tomorrow at noon",
    "project update attached",
    "can we schedule a call",
    "quarterly report review",
    "lunch on thursday sounds good",
    "team standup notes attached",
    "please review the pull request",
]

train_labels = [
    "spam", "spam", "spam", "spam", "spam",
    "ham", "ham", "ham", "ham", "ham", "ham", "ham",
]

classifier = NaiveBayes()
classifier.train(train_docs, train_labels)

test_messages = [
    "free money waiting for you",
    "meeting rescheduled to friday",
    "you won a free prize",
    "please review the attached report",
]

for msg in test_messages:
    print(f"  '{msg}' -> {classifier.predict(msg)}")
```

<a id="step-4-inspect-the-learned-probabilities"></a>

### 第 4 步：检查学习到的概率

```python
def show_top_words(classifier, cls, n=5):
    vocab_size = len(classifier.vocab)
    total = classifier.class_word_totals[cls]
    probs = {}
    for word in classifier.vocab:
        count = classifier.word_counts[cls].get(word, 0)
        probs[word] = (count + classifier.smoothing) / (total + classifier.smoothing * vocab_size)
    sorted_words = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    for word, prob in sorted_words[:n]:
        print(f"    {word}: {prob:.4f}")

print("\nTop spam words:")
show_top_words(classifier, "spam")
print("\nTop ham words:")
show_top_words(classifier, "ham")
```

<a id="use-it"></a>

## 实际应用

Scikit-learn 提供生产就绪的朴素贝叶斯实现：

```python
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import classification_report

vectorizer = CountVectorizer()
X_train = vectorizer.fit_transform(train_docs)
clf = MultinomialNB()
clf.fit(X_train, train_labels)

X_test = vectorizer.transform(test_messages)
predictions = clf.predict(X_test)
for msg, pred in zip(test_messages, predictions):
    print(f"  '{msg}' -> {pred}")
```

相同的算法。 CountVectorizer 处理 tokenization 和 vocabulary 构建。 MultinomialNB 在内部处理平滑和对数概率。您的从头开始版本在 40 行内完成了同样的事情。

<a id="ship-it"></a>

## 交付成果

此处构建的 NaiveBayes 类演示了完整的管道：tokenization、使用拉普拉斯平滑的概率估计、对数空间预测。 `code/bayes.py` 中的代码端到端运行，不依赖于 Python 的标准库。

<a id="conjugate-priors"></a>

### 共轭先验

当先验和后验属于同一分布族时，先验称为“共轭”。这使得贝叶斯更新在代数上变得干净——您无需数值积分即可获得封闭形式的后验。

| 可能性 | 共轭先验 | 后部 | 示例 |
|-----------|----------------|-----------|---------|
| 伯努利 | Beta(a, b) | Beta(a + successes, b + failures) | 抛硬币偏差估计 |
| 正常（已知方差） | Normal(mu_0, sigma_0) | 正态（加权平均值，方差较小） | 传感器 calibration |
| 泊松 | Gamma(a, b) | Gamma（a + 计数总和，b + n） | 建模到达率 |
| 多项式 | Dirichlet(alpha) | Dirichlet(alpha + counts) | 主题建模、语言模型 |

为什么这很重要：如果没有共轭先验，您需要 Monte Carlo sampling 或变分 inference 来近似后验。使用共轭先验，您只需更新两个数字。

Beta 分布是实践中最常见的共轭先验。 Beta(a, b) 代表您对概率 parameter 的信念。平均值为a/(a+b)。 a+b 越大，分布越集中（置信）。

Beta先验的特殊情况：
- Beta(1, 1) = 均匀。您对 parameter 没有意见。
- Beta(10, 10) = 峰值为 0.5。您坚信 parameter 接近 0.5。
- Beta(1, 10) = 偏向 0。您认为 parameter 很小。

更新规则非常简单：

```
Prior:     Beta(a, b)
Data:      s successes, f failures
Posterior: Beta(a + s, b + f)
```

没有积分。没有 sampling。只是补充。

<a id="sequential-bayesian-updating"></a>

### 顺序贝叶斯更新

贝叶斯 inference 自然是顺序的。今天的后事成为明天的先事。这就是真实系统如何增量学习而无需重新处理所有历史数据的方式。

具体例子：评估一枚硬币是否公平。

**第1天：还没有数据。**
从 Beta(1, 1) 开始——统一的先验。你没有意见。
- 先验均值：0.5
- 先验在 [0、1] 上是平坦的

**第2天：观察7个头，3个尾。**
Posterior = Beta(1 + 7, 1 + 3) = Beta(8, 4)
- 后验平均值：8/12 = 0.667
- 有证据表明硬币偏向正面

**第3天：再观察5个头，再观察5个尾。**
使用昨天的后验作为今天的先验。
Posterior = Beta(8 + 5, 4 + 5) = Beta(13, 9)
- 后验平均值：13/22 = 0.591
- 平衡后的新数据将预估值拉回到 0.5

```mermaid
graph LR
    A["Prior<br/>Beta(1,1)<br/>mean = 0.50"] -->|"7H, 3T"| B["Posterior 1<br/>Beta(8,4)<br/>mean = 0.67"]
    B -->|"becomes prior"| C["Prior 2<br/>Beta(8,4)"]
    C -->|"5H, 5T"| D["Posterior 2<br/>Beta(13,9)<br/>mean = 0.59"]
```

观察的顺序并不重要。 Beta(1,1) 一次更新为所有 12 个正面和 8 个反面，得到 Beta(13, 9)——相同的结果。顺序更新和批量更新在数学上是等效的。但是顺序更新可以让您在每个步骤中做出决策，而无需存储原始数据。

这是生产机器学习系统中在线学习的基础。 Thompson sampling for bandits、增量推荐系统和 streaming 异常检测器都使用此模式。

<a id="connection-to-ab-testing"></a>

### 连接 A/B 测试

A/B 测试是贝叶斯 inference 的变相。

设置：您正在测试两种按钮颜色。变体 A（蓝色）和变体 B（绿色）。您想知道哪一个获得更多点击。

贝叶斯 A/B 测试：

1. **Prior.** 两个变体均以 Beta(1, 1) 开头。无优先偏好。
2. **Data.** 变体 A：1000 次浏览中获得 50 次点击。变体 B：1000 次浏览中有 65 次点击。
3. **Postteriors.**
   - A: Beta(1 + 50, 1 + 950) = Beta(51, 951). Mean = 0.051
   - B: Beta(1 + 65, 1 + 935) = Beta(66, 936). Mean = 0.066
4. **Decision.** 计算 P(B > A) -- B 的真实转化率高于 A 的概率。

分析计算 P(B > A) 很困难。但 Monte Carlo 让它变得微不足道：

```
1. Draw 100,000 samples from Beta(51, 951)  -> samples_A
2. Draw 100,000 samples from Beta(66, 936)  -> samples_B
3. P(B > A) = fraction of samples where B > A
```

如果 P(B > A) > 0.95，您将发布变体 B。如果它在 0.05 和 0.95 之间，您将继续收集数据。如果 P(B > A) < 0.05，则交付变体 A。

相对于频繁 A/B 测试的优点：
- 你得到一个直接的概率陈述：“有 97% 的机会 B 更好”
- 没有 p 值混淆。没有“未能拒绝原假设”的对冲。
- 您可以随时检查结果，而不会增加误报率（没有“偷看问题”）
- 您可以结合先验知识（例如，之前的测试表明转化率通常为 3-8%）

| 方面 | 频率论者A/B | 贝叶斯A/B |
|--------|----------------|--------------|
| 输出 | p 值 | P(B > A) |
| 解读 | “如果 A=B，这个数据有多令人惊讶？” | “B 比 A 更好的可能性有多大？” |
| 提前停止 | 夸大误报 | 在任何时候都是安全的（给定事先精心选择且正确指定的模型） |
| 先验知识 | 未使用 | 编码为 Beta 先验 |
| 决策规则 | p < 0.05 | P(B > A) > threshold |

<a id="exercises"></a>

## 练习

1. **多次检测。** 一名患者在独立检测中两次检测呈阳性（两次准确率均为 99%，疾病患病率为万分之一）。两次测试后 P(sick) 是多少？使用第一个测试的后验作为第二个测试的先验。

2. **平滑影响。** 使用平滑值 0.01、0.1、1.0 和 10.0 运行垃圾邮件分类器。最上面的单词概率如何变化？如果 smoothing=0 和仅出现在 ham 中的单词会发生什么？

3. **Add features.** 扩展 NaiveBayes 类，以将消息长度（短/长）用作 feature 以及字数统计。估计P(短|垃圾邮件）和 P（短|火腿）从训练数据中提取并将其折叠到预测分数中。

4. 手工 **MAP。** 给定观察到的数据（10 次抛硬币中有 7 个正面），使用 Beta(2,2) 先验计算偏差的 MAP 估计。将其与 MLE 估计 (7/10) 进行比较。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| 事先 | “我最初的猜测” | P（假设）在观察证据之前。在机器学习中：正则化项。 |
| 可能性 | “数据的拟合程度如何” | P（证据\|假设）。观察到的数据在特定假设下的可能性有多大。 |
| 后部 | “我更新的信念” | P（假设\|证据）。先验乘以可能性，然后标准化。 |
| 证据 | “归一化常数” | 所有假设的 P（数据）。确保后验总和为 1。 |
| 朴素贝叶斯 | “那个简单的文本分类器” | 假设 features 是独立给定类别的分类器。尽管有错误的假设，但效果很好。 |
| 拉普拉斯平滑 | “加一平滑” | 为每个 feature 添加一个小计数，以防止未见数据出现零概率。 |
| 最大LE | “只需使用频率” | 选择最大化 P(data\|parameters) 的 parameters。没有事先。小数据可能会过度拟合。 |
| MAP | “有先验的 MLE” | 选择最大化 P(data\|parameters) * P(parameters) 的 parameters。相当于正则化 MLE。 |
| 对数概率 | “在日志空间中工作” | 使用 log(P) 代替 P 以避免在乘以许多小数时出现浮点下溢。 |
| 误报 | “错误的警报” | 测试显示为阳性，但真实状态为阴性。导致基本利率谬误。 |

<a id="further-reading"></a>

## 进一步阅读

- [3Blue1Brown：贝叶斯定理](https://www.youtube.com/watch?v=HZGCoVF3YvM) - 医学测试示例的视觉解释
- [Stanford CS229：生成学习算法](https://cs229.stanford.edu/main_notes.pdf) - 朴素贝叶斯及其与判别模型的联系
- [Think Bayes](https://greenteapress.com/wp/think-bayes/) - 免费书籍，带有 Python 代码的贝叶斯统计
- [scikit-learn 朴素贝叶斯](https://scikit-learn.org/stable/modules/naive_bayes.html) - 生产实现以及何时使用每个变体
