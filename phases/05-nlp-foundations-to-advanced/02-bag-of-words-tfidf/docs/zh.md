<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="bag-of-words-tf-idf-and-text-representation"></a>

# 词袋、TF-IDF 和文本表示

> 先数数，后思考。 2026 年，TF-IDF 在明确定义的任务上仍然击败 embeddings。

**类型：** 构建
**语言：** Python
**先决条件：** 第 5 阶段·01（文本处理）、第 2 阶段·02（从头开始线性回归）
**时间：** ~75分钟

<a id="the-problem"></a>

## 问题

模型需要数字。你有弦。

每个 NLP 流程都必须回答相同的问题。我们如何将 tokens 的可变长度流转换为分类器可以使用的固定大小向量。该领域得出的第一个答案是最愚蠢的答案。数数单词。制作一个向量。

该向量比任何 embedding 模型都承载了更多的 NLP 生产。垃圾邮件过滤器、主题分类器、日志异常检测、搜索排名（BM25 之前）、第一波情感分析、学术 NLP 基准的第一个十年。 2026 从业者仍然首先在狭窄的分类任务上达到目标。它速度快、可解释，并且在单词存在很重要的任务中通常与 400M-parameter embedding 模型没有区别。

本课程从头开始构建词袋，然后构建 TF-IDF。然后显示 scikit-learn 在三行中执行相同的操作。然后命名使您达到 embeddings 的故障模式。

<a id="the-concept"></a>

## 概念

**Bag of Words (BoW)** 丢弃订单。对于每个文档，计算每个 vocabulary 单词出现的次数。矢量长度为 vocabulary 大小。位置 `i` 是字 `i` 的计数。

**TF-IDF** 重新调整弓的重量。每个文档中出现的单词都没有提供任何信息，因此请缩小其范围。在语料库中罕见但在单个文档中频繁出现的单词是信号，因此请扩大其规模。

```
TF-IDF(w, d) = TF(w, d) * IDF(w)
             = count(w in d) / |d| * log(N / df(w))
```

其中 `TF` 是文档中的术语频率，`df` 是文档频率（有多少文档包含该单词），`N` 是文档总数。 `log` 将 weight 保留为普遍存在的单词。

关键属性：两者都产生具有可解释轴的稀疏向量。您可以查看经过训练的分类器的 weights 并了解哪些单词将文档推向每个类别。您无法使用 768 维的 BERT embedding 执行此操作。

```figure
bow-tfidf
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-build-the-vocabulary"></a>

### 步骤1：构建vocabulary

```python
def build_vocab(docs):
    vocab = {}
    for doc in docs:
        for token in doc:
            if token not in vocab:
                vocab[token] = len(vocab)
    return vocab
```

输入：标记化文档列表（任何单词级 tokenizer 都可以；本课中的 `code/main.py` 使用简化的小写变体）。输出：`{word: index}` 字典。稳定的插入顺序意味着单词索引 0 是第一个文档中看到的第一个单词。惯例各不相同； scikit-learn 按字母顺序排序。

<a id="step-2-bag-of-words"></a>

### 第二步：词袋

```python
def bag_of_words(docs, vocab):
    matrix = [[0] * len(vocab) for _ in docs]
    for i, doc in enumerate(docs):
        for token in doc:
            if token in vocab:
                matrix[i][vocab[token]] += 1
    return matrix
```

```python
>>> docs = [["cat", "sat", "on", "mat"], ["cat", "cat", "ran"]]
>>> vocab = build_vocab(docs)
>>> bag_of_words(docs, vocab)
[[1, 1, 1, 1, 0], [2, 0, 0, 0, 1]]
```

行是文档。列是 vocabulary 索引。条目 `[i][j]` 是“单词 `j` 在文档 `i` 中出现了多少次”。文档 1 有 `cat` 两次，因为它确实如此。 Doc 0 有 `ran` 零次，因为它没有。

<a id="step-3-term-frequency-and-document-frequency"></a>

### 第三步：术语频率和文档频率

```python
import math


def term_frequency(doc_bow, doc_length):
    return [c / doc_length if doc_length else 0 for c in doc_bow]


def document_frequency(bow_matrix):
    df = [0] * len(bow_matrix[0])
    for row in bow_matrix:
        for j, count in enumerate(row):
            if count > 0:
                df[j] += 1
    return df


def inverse_document_frequency(df, n_docs):
    return [math.log((n_docs + 1) / (d + 1)) + 1 for d in df]
```

两个值得一提的平滑技巧。 `(n+1)/(d+1)` 避免了 `log(x/0)`。尾部 `+1` 确保每个文档中的单词仍然具有 IDF 1（而不是 0），与 scikit-learn 的默认值匹配。其他实现使用原始 `log(N/df)`。两者都有效；平滑的版本更友好。

<a id="step-4-tf-idf"></a>

### 步骤4：TF-IDF

```python
def tfidf(bow_matrix):
    n_docs = len(bow_matrix)
    df = document_frequency(bow_matrix)
    idf = inverse_document_frequency(df, n_docs)
    out = []
    for row in bow_matrix:
        length = sum(row)
        tf = term_frequency(row, length)
        out.append([tf_j * idf_j for tf_j, idf_j in zip(tf, idf)])
    return out
```

```python
>>> docs = [
...     ["the", "cat", "sat"],
...     ["the", "dog", "sat"],
...     ["the", "cat", "ran"],
... ]
>>> vocab = build_vocab(docs)
>>> bow = bag_of_words(docs, vocab)
>>> tfidf(bow)
```

三个文档，五个词汇（`the`、`cat`、`sat`、`dog`、`ran`）。 `the` 在这三个中均出现，因此其 IDF 较低。 `dog`出现在其中之一，因此其IDF较高。向量是稀疏的（大多数条目都很小）并且有区别的单词会出现。

<a id="step-5-l2-normalize-rows"></a>

### 步骤 5：L2 标准化行

```python
def l2_normalize(matrix):
    out = []
    for row in matrix:
        norm = math.sqrt(sum(x * x for x in row))
        out.append([x / norm if norm else 0 for x in row])
    return out
```

如果没有 normalization，较长的文档会获得较大的向量并主导相似性分数。 L2 normalization 将每个文档放在单位超球面上。行之间的 Cosine similarity 现在只是点积。

<a id="use-it"></a>

## 实际应用

scikit-learn 发布量产版本。

```python
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

docs = ["the cat sat on the mat", "the dog sat on the mat", "the cat ran"]

bow_vectorizer = CountVectorizer()
bow = bow_vectorizer.fit_transform(docs)
print(bow_vectorizer.get_feature_names_out())
print(bow.toarray())

tfidf_vectorizer = TfidfVectorizer()
tfidf = tfidf_vectorizer.fit_transform(docs)
print(tfidf.toarray().round(3))
```

`CountVectorizer` 在一次调用中执行 tokenization、vocabulary 和 BoW。 `TfidfVectorizer` 增加了 IDF 加权和 L2 normalization。两者都返回稀疏矩阵。对于 100k 文档，密集版本无法放入内存；保持稀疏，直到分类器需要密集。

改变一切的旋钮：

| 精氨酸 | 效果 |
|-----|--------|
| `ngram_range=(1, 2)` | 包括二元组。通常会提高分类效果。 |
| `min_df=2` | 在少于 2 个文档中删除单词。对噪声数据进行修剪 vocabulary。 |
| `max_df=0.95` | 删除超过 95% 的文档中的单词。无需硬编码列表即可近似删除停用词。 |
| `stop_words="english"` | scikit-learn 的内置停用词列表。任务相关——情绪分析应该 *not* 放弃否定。 |
| `sublinear_tf=True` | 使用 `1 + log(tf)` 而不是原始 `tf`。当某个术语在一篇文档中重复多次时会有所帮助。 |

<a id="when-tf-idf-still-wins-as-of-2026"></a>

### 当 TF-IDF 仍然获胜时（截至 2026 年）

- 垃圾邮件检测、主题标记、日志异常标记。文字的存在才是最重要的；语义上的细微差别则不然。
- 低数据制度（数百个标记示例）。 TF-IDF加逻辑回归没有pretraining成本。
- 任何地方延迟都很重要。 TF-IDF 加上线性模型可在微秒内得出答案。 Embedding 一个文件通过一个transformer需要10-100ms。
- 必须解释其预测的系统。检查分类器的系数。最积极的话语就是原因。

<a id="when-tf-idf-fails"></a>

### 当 TF-IDF 失败时

语义失明的失败。考虑这两个文档：

- “这部电影一点也不好看。”
- “这部电影很棒。”

一是差评。一是积极的。他们的TF-IDF重叠正是`{the, movie, was}`。词袋分类器必须记住 `good` 附近的单词 `not` 会翻转标签。它可以通过足够的数据来学习这一点，但永远不会像理解语法的模型那样优雅。

另一个失败：inference 处出现 vocabulary 字。如果 token 从未出现在训练中，则在 IMDb 评论上训练的 BoW 模型不知道如何处理 `Zoomer-approved`。子字 embeddings（第 04 课）处理此问题。 TF-IDF 不能。

<a id="hybrid-tf-idf-weighted-embeddings"></a>

### 混合：TF-IDF 加权 embeddings

2026 年中型 data classification 的实用默认值：使用 TF-IDF weights 作为 attention 代替字 embeddings。

```python
def tfidf_weighted_embedding(doc, tfidf_scores, embedding_table, dim):
    vec = [0.0] * dim
    total_weight = 0.0
    for token in doc:
        if token not in embedding_table or token not in tfidf_scores:
            continue
        weight = tfidf_scores[token]
        emb = embedding_table[token]
        for i in range(dim):
            vec[i] += weight * emb[i]
        total_weight += weight
    if total_weight == 0:
        return vec
    return [v / total_weight for v in vec]
```

您可以从 embeddings 获得语义容量，并从 TF-IDF 获得稀有词强调。分类器在合并向量上进行训练。对于低于大约 50k 个标记示例的情感、主题和意图分类，这优于其本身。

<a id="ship-it"></a>

## 交付成果

另存为`outputs/prompt-vectorization-picker.md`：

```markdown
---
name: vectorization-picker
description: Given a text-classification task, recommend BoW, TF-IDF, embeddings, or a hybrid.
phase: 5
lesson: 02
---

You recommend a text-vectorization strategy. Given a task description, output:

1. Representation (BoW, TF-IDF, transformer embeddings, or a hybrid). Explain why in one sentence.
2. Specific vectorizer configuration. Name the library. Quote the arguments (`ngram_range`, `min_df`, `max_df`, `sublinear_tf`, `stop_words`).
3. One failure mode to test before shipping.

Refuse to recommend embeddings when the user has under 500 labeled examples unless they show evidence of semantic failure in a TF-IDF baseline. Refuse to remove stopwords for sentiment analysis (negations carry signal). Flag class imbalance as needing more than a vectorizer change.

Example input: "Classifying 30k customer support tickets into 12 categories. Most tickets are 2-3 sentences. English only. Need explainability for audit logs."

Example output:

- Representation: TF-IDF. 30k examples is not small; explainability requirement rules out dense embeddings.
- Config: `TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_df=0.95, sublinear_tf=True, stop_words=None)`. Keep stopwords because category keywords sometimes are stopwords ("not working" vs "working").
- Failure to test: verify `min_df=3` does not drop rare category keywords. Run `get_feature_names_out` filtered by class and eyeball.
```

<a id="exercises"></a>

## 练习

1. **Easy.** 在 L2 归一化 TF-IDF 输出上实现 `cosine_similarity(doc_vec_a, doc_vec_b)`。验证相同文档的得分为 1.0，不相交的 vocabulary 文档的得分为 0.0。
2. **Medium.** 将 `n-gram` 支持添加到 `bag_of_words`。 Parameter `n` 产生的计数超过 `n` 克。测试 `["the", "cat", "sat"]` 上的 `n=2` 为 `["the cat", "cat sat"]` 生成二元计数。
3. **Hard.** 使用 GloVe 100d 向量构建上面的 TF-IDF 加权 embedding 混合体（下载一次，缓存）。在 20 个新闻组数据集上将分类准确度与普通 TF-IDF 和普通平均池 embeddings 进行比较。报告哪一方获胜。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| 鲍威 | 词频向量 | 一份文档中 vocabulary 单词的计数。丢弃订单。 |
| TF | 术语频率 | 文档中单词的计数，可以选择按文档长度进行标准化。 |
| DF | 文档频率 | 至少包含一次该单词的文档计数。 |
| 以色列国防军 | 逆文档频率 | `log(N / df)` 已平滑。降低随处出现的单词的权重。 |
| 稀疏向量 | 大部分都是零 | Vocabulary 通常为 10k-100k 字；大多数都没有出现在任何给定的文件中。 |
| Cosine similarity | 矢量角 | L2 归一化向量的点积。 1 是相同的，0 是正交的。 |

<a id="further-reading"></a>

## 进一步阅读

- [scikit-learn — feature 从文本中提取](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction) — 规范的 API 参考，以及每个旋钮上的注释。
- [Salton, G. 和 Buckley, C. (1988)。自动文本检索中的术语权重方法](https://www.sciencedirect.com/science/article/pii/0306457388900210)——这篇论文使 TF-IDF 成为十年来的默认标准。
- [“为什么 TF-IDF 仍然击败 Embeddings” — Ashfaque Thonikkadavan（中）](https://medium.com/@cmtwskb/why-tf-idf-still-beats-embeddings-ad85c123e1b2) — 2026 年旧方法何时获胜以及原因。
