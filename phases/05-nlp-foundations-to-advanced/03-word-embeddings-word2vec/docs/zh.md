<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="word-embeddings--word2vec-from-scratch"></a>

# 词 Embeddings——从零实现 Word2Vec

> 一个词就是它的陪伴。在这个想法上训练一个浅网，几何学就会失败。

**类型：** 构建
**语言：** Python
**先决条件：** 第 5 阶段·02 (BoW + TF-IDF)、第 3 阶段·03 (Backpropagation 从头开始)
**时间：** ~75 分钟

<a id="the-problem"></a>

## 问题

TF-IDF 知道 `dog` 和 `puppy` 是不同的词。它不知道它们的意思几乎相同。在 `dog` 上训练的分类器无法推广到有关 `puppy` 的评论。您可以通过列出同义词来掩盖这一点，但对于罕见术语、领域术语和您没有预料到的每种语言来说，这会失败。

您需要 `dog` 和 `puppy` 在太空中靠近着陆的表示。 `king - man + woman` 降落在 `queen` 附近。在 `dog` 上训练的模型免费将一些信号传输到 `puppy`。

Word2Vec 给了我们这个空间。两层神经网络，万亿 token 训练运行，发表于 2013 年。该架构几乎简单得令人尴尬。结果重塑了 NLP 十年来的面貌。

<a id="the-concept"></a>

## 概念

**分布假设**（Firth，1957）：“你应该通过它所保持的公司来认识一个单词。”如果两个词出现在相似的上下文中，它们可能意味着相似的事情。

Word2Vec 有两种风格，都利用了这个想法。

- **Skip-gram.** 给定一个中心词，预测周围的词。 `cat -> (the, sat, on)`，窗口尺寸为 2。
- **CBOW（连续词袋）。** 给定周围的单词，预测中心。 `(the, sat, on) -> cat`。

Skip-gram 训练速度较慢，但可以更好地处理罕见单词。它成为默认值。

该网络有一个隐藏层，没有非线性。输入是 vocabulary 上的独热向量。输出是 softmax 通过 vocabulary。训练结束后，你就扔掉输出层。隐藏层weights是embeddings。

```
one-hot(center) ── W ──▶ hidden (d-dim) ── W' ──▶ softmax(vocab)
                          ^
                          this is the embedding
```

窍门：softmax 超过 100k 字的成本非常昂贵。 Word2Vec使用**negative sampling**将其变成二元分类任务。预测“这个上下文单词是否出现在这个中心单词附近，是或否”。对每个训练对采样一些负面（非共现）单词，而不是在整个 vocabulary 上计算 softmax。

```figure
word-vector-arithmetic
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-training-pairs-from-a-corpus"></a>

### 第 1 步：从语料库中训练对

```python
def skipgram_pairs(docs, window=2):
    pairs = []
    for doc in docs:
        for i, center in enumerate(doc):
            for j in range(max(0, i - window), min(len(doc), i + window + 1)):
                if i == j:
                    continue
                pairs.append((center, doc[j]))
    return pairs
```

```python
>>> skipgram_pairs([["the", "cat", "sat", "on", "mat"]], window=2)
[('the', 'cat'), ('the', 'sat'),
 ('cat', 'the'), ('cat', 'sat'), ('cat', 'on'),
 ('sat', 'the'), ('sat', 'cat'), ('sat', 'on'), ('sat', 'mat'),
 ...]
```

窗口中的每个（中心，上下文）对都是一个正向训练示例。

<a id="step-2-embedding-tables"></a>

### 步骤2：embedding表

两个矩阵。 `W` 是中心字 embedding 表（您保留的表）。 `W'` 是上下文词表（经常被丢弃，有时与 `W` 进行平均）。

```python
import numpy as np


def init_embeddings(vocab_size, dim, seed=0):
    rng = np.random.default_rng(seed)
    W = rng.normal(0, 0.1, size=(vocab_size, dim))
    W_prime = rng.normal(0, 0.1, size=(vocab_size, dim))
    return W, W_prime
```

小随机初始化。词汇大小 10k 和暗淡 100 是现实的；对于教学来说，50 个词汇 x 16 个暗淡足以看清几何。

<a id="step-3-negative-sampling-objective"></a>

### 步骤3：否定sampling目标

对于每个正对 `(center, context)`，从 vocabulary 中采样 `k` 随机词作为负数。训练模型，使点积 `W[center] · W'[context]` 对于正值而言较高，对于负值而言较低。

```python
def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def train_pair(W, W_prime, center_idx, context_idx, negative_indices, lr):
    v_c = W[center_idx]
    u_pos = W_prime[context_idx]
    u_negs = W_prime[negative_indices]

    pos_score = sigmoid(v_c @ u_pos)
    neg_scores = sigmoid(u_negs @ v_c)

    grad_center = (pos_score - 1) * u_pos
    for i, u in enumerate(u_negs):
        grad_center += neg_scores[i] * u

    W[context_idx] = W[context_idx]
    W_prime[context_idx] -= lr * (pos_score - 1) * v_c
    for i, neg_idx in enumerate(negative_indices):
        W_prime[neg_idx] -= lr * neg_scores[i] * v_c
    W[center_idx] -= lr * grad_center
```

神奇公式：正对上的逻辑损失（希望 sigmoid 接近 1）加上负对上的逻辑损失（希望 sigmoid 接近 0）。 Gradients 流向两个表。完整推导在原论文中；如果你想让它粘住，就用铅笔和纸把它走一遍。

<a id="step-4-train-on-a-toy-corpus"></a>

### 第 4 步：在玩具语料库上进行训练

```python
def train(docs, dim=16, window=2, k_neg=5, epochs=100, lr=0.05, seed=0):
    vocab = build_vocab(docs)
    vocab_size = len(vocab)
    rng = np.random.default_rng(seed)
    W, W_prime = init_embeddings(vocab_size, dim, seed=seed)
    pairs = skipgram_pairs(docs, window=window)

    for epoch in range(epochs):
        rng.shuffle(pairs)
        for center, context in pairs:
            c_idx = vocab[center]
            ctx_idx = vocab[context]
            negs = rng.integers(0, vocab_size, size=k_neg)
            negs = [n for n in negs if n != ctx_idx and n != c_idx]
            train_pair(W, W_prime, c_idx, ctx_idx, negs, lr)
    return vocab, W
```

在大型语料库上经过足够多的时期后，共享上下文的单词具有相似的中心 embeddings。在玩具语料库上，您可以隐约看到效果。在数十亿的 tokens 上，你会看到它的戏剧性。

<a id="step-5-the-analogy-trick"></a>

### 第五步：类比技巧

```python
def nearest(vocab, W, target_vec, topk=5, exclude=None):
    exclude = exclude or set()
    inv_vocab = {i: w for w, i in vocab.items()}
    norms = np.linalg.norm(W, axis=1, keepdims=True) + 1e-9
    W_norm = W / norms
    target = target_vec / (np.linalg.norm(target_vec) + 1e-9)
    sims = W_norm @ target
    order = np.argsort(-sims)
    out = []
    for i in order:
        if i in exclude:
            continue
        out.append((inv_vocab[i], float(sims[i])))
        if len(out) == topk:
            break
    return out


def analogy(vocab, W, a, b, c, topk=5):
    v = W[vocab[b]] - W[vocab[a]] + W[vocab[c]]
    return nearest(vocab, W, v, topk=topk, exclude={vocab[a], vocab[b], vocab[c]})
```

在预训练的 300d Google News 向量上：

```python
>>> analogy(vocab, W, "man", "king", "woman")
[('queen', 0.71), ('monarch', 0.62), ('princess', 0.59), ...]
```

`king - man + woman = queen`。并不是因为模特知道什么是版税。因为向量 `(king - man)` 捕获了类似“royal”的东西，将其添加到 `woman` 会落在皇家女性区域附近。

<a id="use-it"></a>

## 实际应用

从头开始编写Word2Vec就是教学。生产 NLP 使用 `gensim`。

```python
from gensim.models import Word2Vec

sentences = [
    ["the", "cat", "sat", "on", "the", "mat"],
    ["the", "dog", "ran", "across", "the", "room"],
]

model = Word2Vec(
    sentences,
    vector_size=100,
    window=5,
    min_count=1,
    sg=1,
    negative=5,
    workers=4,
    epochs=30,
)

print(model.wv["cat"])
print(model.wv.most_similar("cat", topn=3))
```

对于实际工作，您几乎从不自己训练 Word2Vec。您下载预先训练的向量。

- **GloVe** — 斯坦福大学的共现矩阵分解方法。 50天、100天、200天、300天checkpoints。良好的总体覆盖范围。第 04 课专门介绍了 GloVe。
- **fastText** — Facebook 的 Word2Vec 嵌入字符 n 元语法的扩展。通过组合子词来处理 vocabulary 之外的单词。第 04 课。
- **在 Google 新闻上预训练 Word2Vec** — 300d，3M 字 vocabulary，2013 年发布。仍然每天下载。

<a id="when-word2vec-still-wins-in-2026"></a>

### 当2026年Word2Vec仍然获胜时

- 轻量级特定领域检索。在笔记本电脑上一小时内进行医学摘要训练，获得通用模型无法捕获的专用向量。
- 类比式feature工程。 `gender_vector = mean(man - woman pairs)`。从其他单词中减去它即可得到性别中立的轴。仍用于公平性研究。
- 可解释性。 100d 足够小，可以通过 PCA 或 t-SNE 进行绘图并实际看到簇的形成。
- 任何地方，inference 都必须在没有 GPU 的设备上运行。 Word2Vec 查找是单行获取。

<a id="where-word2vec-fails"></a>

### Word2Vec 失败的地方

多义墙。 `bank` 有一个向量。 `river bank` 和 `financial bank` 共享。 `table`（电子表格与家具）分享它。下游的分类器无法区分向量和意义。

上下文 embeddings（ELMo、BERT、此后的每个 transformer）通过根据周围上下文为单词的每次出现生成不同的向量来解决这个问题。这就是从 Word2Vec 到 BERT 的跳转：从静态到上下文。第 7 阶段涵盖了 transformer 的一半。

vocabulary 之外的问题是另一个故障。如果 Word2Vec 不在训练数据中，则 `Zoomer-approved` 从未见过。没有后备。 fastText 通过子词组合修复了这个问题（第 04 课）。

<a id="ship-it"></a>

## 交付成果

另存为 `outputs/skill-embedding-probe.md`：

```markdown
---
name: embedding-probe
description: Inspect a word2vec model. Run analogies, find neighbors, diagnose quality.
version: 1.0.0
phase: 5
lesson: 03
tags: [nlp, embeddings, debugging]
---

You probe trained word embeddings to verify they are working. Given a `gensim.models.KeyedVectors` object and a vocabulary, you run:

1. Three canonical analogy tests. `king : man :: queen : woman`. `paris : france :: tokyo : japan`. `walking : walked :: swimming : ?`. Report the top-1 result and its cosine.
2. Five nearest-neighbor tests on domain-specific words the user supplies. Print top-5 neighbors with cosines.
3. One symmetry check. `similarity(a, b) == similarity(b, a)` to within float precision.
4. One degenerate check. If any embedding has a norm below 0.01 or above 100, the model has a training bug. Flag it.

Refuse to declare a model good on analogy accuracy alone. Analogy benchmarks are gameable and do not transfer to downstream tasks. Recommend intrinsic + downstream evaluation together.
```

<a id="exercises"></a>

## 练习

1. **Easy.** 在一个小语料库（关于猫和狗的 20 个句子）上运行训练循环。 200 个 epoch 后，验证 `nearest(vocab, W, W[vocab["cat"]])` 在其前 3 个中返回 `dog`。如果不是，则增加 epoch 或 vocabulary。
2. **Medium.** 添加频繁词的子采样。频率高于 `10^-5` 的单词将从训练对中删除，概率与其频率成正比。衡量对稀有词相似度的影响。
3. **Hard.** 在 20 个新闻组语料库上训练模型。计算两个偏置轴：`he - she` 和 `doctor - nurse`。将职业词投影到两个轴上。报告哪些职业存在最大的偏见差距。这就是研究人员使用的探测公平性的类型。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| 字embedding | 词作为向量 | 从上下文中学习的密集、低暗度（通常为 100-300）表示。 |
| Skip-gram | Word2Vec 技巧 | 从中心词预测上下文词。比 CBOW 慢，对于稀有词更好。 |
| 负sampling | 训练捷径 | 将完整词汇上的 softmax 替换为针对 `k` 随机单词的二进制分类。 |
| 静态 embedding | 每个单词一个向量 | 无论上下文如何，相同的向量。一词多义失败。 |
| 上下文 embedding | 上下文相关向量 | 基于周围单词的每次出现的不同向量。 transformers 生产什么。 |
| 外用病毒 | 出vocabulary | 训练中没有看到这个词。 Word2Vec 无法为这些生成向量。 |

<a id="further-reading"></a>

## 进一步阅读

- [Mikolov 等人。 （2013）。单词和短语的分布式表示及其组合性](https://arxiv.org/abs/1310.4546) — 负sampling 论文。简短易读。
- [Rong，X.（2014）。 word2vec Parameter 学习解释](https://arxiv.org/abs/1411.2738) — 如果原始论文的数学感觉很密集，那么这是 gradients 最清晰的推导。
- [gensim Word2Vec 教程](https://radimrehurek.com/gensim/models/word2vec.html) — 实际有效的生产培训设置。
