<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="sentiment-analysis"></a>

# 情绪分析

> 规范的 NLP 任务。您需要了解的有关经典文本分类的大部分内容都显示在这里。

**类型：** 构建
**语言：** Python
**先决条件：** 第 5 阶段·02 (BoW + TF-IDF)、第 2 阶段·14 (朴素贝叶斯)
**时间：** ~75分钟

<a id="the-problem"></a>

## 问题

“食物不太好。”积极还是消极？

情绪听起来很简单。评论者说他们喜欢或不喜欢某些东西。给句子贴上标签。它之所以成为标准的 NLP 任务，是因为每一个看似简单的案例都隐藏着一个困难的案例。否定翻转了意义。讽刺则颠倒了它。尽管有两个负面编码的词，“一点也不坏”仍然是积极的。表情符号比周围的文字承载更多的信号。域名 vocabulary 很重要（音乐评论中的 `tight` 与时尚评论中的 `tight` ）。

Sentiment 是经典 NLP 的工作实验室。如果您理解为什么每个朴素基线都有特定的故障模式，您就会理解为什么发明每个更丰富的模型。本课程从头开始构建朴素贝叶斯基线，添加逻辑回归，并指出使生产情绪成为合规级问题的陷阱。

<a id="the-concept"></a>

## 概念

古典情感是一个两步的秘诀。

1. **Represent.** 将文本转换为 feature 向量。 BoW、TF-IDF 或 n-gram。
2. **Classify.** 在标记示例上拟合线性模型（朴素贝叶斯、逻辑回归、SVM）。

朴素贝叶斯是最愚蠢的模型。假设每个 feature 都是独立的给定标签。根据计数估计 `P(word | positive)` 和 `P(word | negative)`。在 inference 处，乘以概率。 “天真的”独立假设是可笑的错误，但结果却令人震惊。原因是：对于稀疏文本 features 和适度的数据，分类器关心每个单词更倾向于哪一边，而不是多少。

逻辑回归修正了独立性假设。它为每个 feature 学习一个 weight，包括负 weights。 `not good` 作为二元组 feature 得到负 weight。对于从未标记过的二元模型，朴素贝叶斯无法做到这一点。

```figure
sentiment-logits
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-a-real-mini-dataset"></a>

### 第 1 步：真正的迷你数据集

```python
POSITIVE = [
    "absolutely loved this movie",
    "beautiful cinematography and a great story",
    "one of the best films of the year",
    "brilliant acting from the lead",
    "heartwarming and funny",
]

NEGATIVE = [
    "boring and far too long",
    "not worth your time",
    "the plot made no sense",
    "terrible acting, awful script",
    "i want my two hours back",
]
```

故意的小。实际工作使用数以万计的示例（IMDb、SST-2、Yelp 极性）。数学是相同的。

<a id="step-2-multinomial-naive-bayes-from-scratch"></a>

### 第 2 步：从头开始多项式朴素贝叶斯

```python
import math
from collections import Counter


def train_nb(docs_by_class, vocab, alpha=1.0):
    class_priors = {}
    class_word_probs = {}
    total_docs = sum(len(d) for d in docs_by_class.values())

    for cls, docs in docs_by_class.items():
        class_priors[cls] = len(docs) / total_docs
        counts = Counter()
        for doc in docs:
            for token in doc:
                counts[token] += 1
        total = sum(counts.values()) + alpha * len(vocab)
        class_word_probs[cls] = {
            w: (counts[w] + alpha) / total for w in vocab
        }
    return class_priors, class_word_probs


def predict_nb(doc, class_priors, class_word_probs):
    scores = {}
    for cls in class_priors:
        s = math.log(class_priors[cls])
        for token in doc:
            if token in class_word_probs[cls]:
                s += math.log(class_word_probs[cls][token])
        scores[cls] = s
    return max(scores, key=scores.get)
```

加法平滑（alpha=1.0）是拉普拉斯平滑。如果没有它，类中未见过的单词的概率为零，并且日志会爆炸。 `alpha=0.01`在实践中很常见。 `alpha=1.0` 为教学默认值。

<a id="step-3-logistic-regression-from-scratch"></a>

### 第 3 步：从头开始逻辑回归

```python
import numpy as np


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def train_lr(X, y, epochs=500, lr=0.05, l2=0.01):
    n_features = X.shape[1]
    w = np.zeros(n_features)
    b = 0.0
    for _ in range(epochs):
        logits = X @ w + b
        preds = sigmoid(logits)
        err = preds - y
        grad_w = X.T @ err / len(y) + l2 * w
        grad_b = err.mean()
        w -= lr * grad_w
        b -= lr * grad_b
    return w, b


def predict_lr(X, w, b):
    return (sigmoid(X @ w + b) >= 0.5).astype(int)
```

L2 正则化在这里很重要。文本 features 稀疏；如果没有 L2，模型会记住训练示例。从 `0.01` 开始并进行调整。

<a id="step-4-handling-negation-the-failure-mode"></a>

### 第四步：处理否定（失败模式）

考虑“不好”和“不错”。 BoW 分类器看到 `{not, good}` 和 `{not, bad}` 并从训练中出现更多的那个进行学习。二元组分类器看到 `not_good` 和 `not_bad` 并将它们学习为不同的 features。这通常就足够了。

当您没有二元组时，可以使用更粗略的修复：**negation scoping**。在带有 `NOT_` 的否定词后面加上前缀 tokens 直到下一个标点符号。

```python
NEGATION_WORDS = {"not", "no", "never", "nor", "none", "nothing", "neither"}
NEGATION_TERMINATORS = {".", "!", "?", ",", ";"}


def apply_negation(tokens):
    out = []
    negate = False
    for token in tokens:
        if token in NEGATION_TERMINATORS:
            negate = False
            out.append(token)
            continue
        if token in NEGATION_WORDS:
            negate = True
            out.append(token)
            continue
        out.append(f"NOT_{token}" if negate else token)
    return out
```

```python
>>> apply_negation(["not", "good", "at", "all", ".", "but", "funny"])
['not', 'NOT_good', 'NOT_at', 'NOT_all', '.', 'but', 'funny']
```

现在`good`和`NOT_good`是不同的features。分类器可以 weight 它们相反。三行预处理，可测量的准确性在情绪基准上跳跃。

<a id="step-5-evaluation-metrics-that-matter"></a>

### 第 5 步：evaluation 重要指标

如果类别不平衡，仅准确性就会产生误导。真实情感语料库通常有 70-80% 正面或 70-80% 负面；恒定多数分类器的准确度为 80%，毫无价值。报告以下每一项：

- **每类精度和召回率。** 每类一对。对它们进行宏观平均以获得尊重班级平衡的单一数字。
- **Macro-F1（不平衡数据的主要指标）。** 每类 F1 分数的平均值，等权重。当类别不平衡时，使用此选项而不是准确性。
- **Weighted-F1（替代）。** 与宏相同，但按类别频率加权。当失衡本身具有商业意义时，与宏观 F1 一起报告。
- **混淆矩阵。** 原始计数。在信任任何标量指标之前始终进行检查；它揭示了模型混淆了哪对类。
- **每类错误样本。** 每类拉取 5 个错误预测。阅读它们。没有什么可以取代阅读实际错误。

对于严重不平衡的数据（> 95-5 比率），报告 **AUROC** 和 **AUPRC** 而不是精度。 AUPRC 对少数群体更敏感，这也是你通常关心的（垃圾邮件、欺诈、罕见情绪）。

** 要避免的常见错误。** 在不平衡数据上报告微观 F1 而不是宏观 F1 给出的数字看起来很高，因为它由多数类主导。 Macro-F1迫使你看到少数派的表现。

```python
def evaluate(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": precision, "recall": recall, "f1": f1}
```

<a id="use-it"></a>

## 实际应用

scikit-learn 正确地用六行完成了它。

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

pipe = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, stop_words=None)),
    ("clf", LogisticRegression(C=1.0, max_iter=1000)),
])
pipe.fit(X_train, y_train)
print(pipe.score(X_test, y_test))
```

需要注意三件事。 `stop_words=None` 保持否定。 `ngram_range=(1, 2)` 添加二元组，因此 `not_good` 变为 feature。 `sublinear_tf=True` 抑制重复的单词。这三个标志是 SST-2 上 75% 准确度基线和 85% 准确度基线之间的差异。

<a id="when-to-reach-for-a-transformer"></a>

### 何时获取 transformer

- 讽刺检测。经典模型在这里失败了。时期。
- 长篇评论，情绪在文档中发生变化。
- 基于方面的情感。 “相机很棒，但电池很糟糕。”您需要将情绪归因于各个方面。仅限 Transformers 或 structured output 型号。
- 非英语、资源匮乏的语言。多语言BERT免费为您提供zero-shot基线。

如果您需要上述任何内容，请跳至第 7 阶段（transformers 深入研究）。否则，朴素贝叶斯或 TF-IDF 上的逻辑回归加上二元模型加上否定处理就是您 2026 年的生产基线。

<a id="the-reproducibility-trap-again"></a>

### 再现性陷阱（再次）

重新训练情绪模型是例行公事。重新评估它们则不然。论文中报告的准确度数字使用特定的分割、特定的预处理、特定的 tokenizers。如果您在不使用相同管道的情况下将新模型与基线进行比较，您将得到误导性的增量。始终重新生成管道上的基线，而不是论文的编号。

<a id="ship-it"></a>

## 交付成果

另存为`outputs/prompt-sentiment-baseline.md`：

```markdown
---
name: sentiment-baseline
description: Design a sentiment analysis baseline for a new dataset.
phase: 5
lesson: 05
---

Given a dataset description (domain, language, size, label granularity, latency budget), you output:

1. Feature extraction recipe. Specify tokenizer, n-gram range, stopword policy (usually keep), negation handling (scoped prefix or bigrams).
2. Classifier. Naive Bayes for baseline, logistic regression for production, transformer only if the domain needs sarcasm / aspects / cross-lingual.
3. Evaluation plan. Report precision, recall, F1, confusion matrix, and per-class error samples (not just scalars).
4. One failure mode to monitor post-deployment. Domain drift and sarcasm are the top two.

Refuse to recommend dropping stopwords for sentiment tasks. Refuse to report accuracy as the sole metric when classes are imbalanced (e.g., 90% positive). Flag subword-rich languages as needing FastText or transformer embeddings over word-level TF-IDF.
```

<a id="exercises"></a>

## 练习

1. **Easy.** 添加 `apply_negation` 作为 scikit-learn 管道中的预处理步骤，并在小型情感数据集上测量 F1 增量。
2. **Medium.** 实现类加权逻辑回归（将 `class_weight="balanced"` 传递给 scikit-learn，或自己导出 gradient）。衡量对综合 90-10 类不平衡的影响。
3. **Hard.** 通过根据情感模型的残差训练第二个分类器来构建讽刺检测器。记录您的实验设置。当你的准确性低于概率时警告读者（2 级讽刺的概率水平约为 50%，大多数第一次尝试都会达到该水平）。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| 极性 | 正或负 | 二进制标签；有时扩展到中性或细粒度（5 星级）。 |
| 基于方面的情感 | 每方面极性 | 将情感归因于文本中提到的特定实体或属性。 |
| 否定范围 | 附近倒车 tokens | “not”后面加上 tokens 前缀，后面加上 `NOT_`，直到标点符号为止。 |
| 拉普拉斯平滑 | 计数加 1 | 防止朴素贝叶斯中的零概率 features。 |
| L2正则化 | 收缩weights | 将 `lambda * sum(w^2)` 添加到损失中。对于稀疏文本 features 至关重要。 |

<a id="further-reading"></a>

## 进一步阅读

- [Pang 和 Lee (2008)。意见挖掘和情绪分析](https://www.cs.cornell.edu/home/llee/opinion-mining-sentiment-analysis-survey.html) — 基础调查。虽然很长，但前四部分涵盖了所有经典内容。
- [Wang 和曼宁 (2012)。基线和二元组：简单、良好的情绪和主题分类](https://aclanthology.org/P12-2018/)——这篇展示二元组+朴素贝叶斯的论文在短文本上很难被击败。
- [scikit-learn 文本 feature 提取文档](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction) — `CountVectorizer`、`TfidfVectorizer` 和每个旋钮的参考你会调的。
