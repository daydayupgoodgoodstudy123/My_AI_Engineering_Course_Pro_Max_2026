<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="glove-fasttext-and-subword-embeddings"></a>

# GloVe、FastText 和 Subword Embeddings

> Word2Vec 每个单词训练一个 embedding。 GloVe 对共现矩阵进行因式分解。 FastText 嵌入了这些片段。 BPE 桥接到 transformers。

**类型：** 构建
**语言：** Python
**先决条件：** 第 5 阶段·03（Word2Vec 从头开始）
**时间：** ~45分钟

<a id="the-problem"></a>

## 问题

Word2Vec 留下了两个悬而未决的问题。

首先，有一项并行研究直接分解共现矩阵（LSA、HAL），而不是进行在线 skip-gram 更新。 Word2Vec 的迭代方法从根本上来说更好，还是两种方法处理计数方式的差异造成的？ **GloVe** 回答说：经过深思熟虑选择的损失的矩阵分解匹配或击败 Word2Vec，并且训练成本更低。

其次，这两种方法都没有它从未见过的单词的故事。 `Zoomer-approved`、`dogecoin`，上周创造的任何专有名词，罕见词根的每种变形形式。 **FastText** 通过 embedding 字符 n 元语法修复了这个问题：单词是其各个部分（包括语素）的总和，因此即使是 vocabulary 之外的单词也会得到一个合理的向量。

第三，transformers到达后，问题再次转移。字级vocabularies上限约为100万个条目；真正的语言比这更开放。 **字节对编码（BPE）**及其亲属通过学习涵盖所有内容的频繁子字单元vocabulary解决了这个问题。每个现代 tokenizer 对于每个现代 LLM 都是一个子字 tokenizer。

本课将介绍这三个部分，然后解释何时该接触哪一个。

<a id="the-concept"></a>

## 概念

**GloVe（全局向量）.** 构建单词-单词共现矩阵 `X`，其中 `X[i][j]` 是单词 `j` 在单词上下文中出现的频率`i`。训练向量使得 `v_i · v_j + b_i + b_j ≈ log(X[i][j])`。 Weight 损失如此频繁的对不占主导地位。完毕。

**FastText.** 单词是其字符 n 元语法加上单词本身的总和。 `where` 变为 `<wh, whe, her, ere, re>, <where>`。词向量是这些分量向量的总和。训练为 Word2Vec。好处：看不见的单词（`whereupon`）由已知的 n 元语法组成。

**BPE（字节对编码）。** 以 vocabulary 的单个字节（或字符）开始。计算语料库中每个相邻对的数量。将最频繁的对合并到新的 token 中。重复 `k` 迭代。结果：`k + 256` tokens 的 vocabulary，其中频繁序列（`ing`、`tion`、`the`）为单个tokens 和生僻单词被分解成熟悉的片段。每句话都象征化为某种东西。

```figure
n5-subword-merge
```

<a id="build-it"></a>

## 动手实现

<a id="glove-factorize-the-co-occurrence-matrix"></a>

### GloVe：分解共生矩阵

```python
import numpy as np
from collections import Counter


def build_cooccurrence(docs, window=5):
    pair_counts = Counter()
    vocab = {}
    for doc in docs:
        for token in doc:
            if token not in vocab:
                vocab[token] = len(vocab)
    for doc in docs:
        indexed = [vocab[t] for t in doc]
        for i, center in enumerate(indexed):
            for j in range(max(0, i - window), min(len(indexed), i + window + 1)):
                if i != j:
                    distance = abs(i - j)
                    pair_counts[(center, indexed[j])] += 1.0 / distance
    return vocab, pair_counts


def glove_train(vocab, pair_counts, dim=16, epochs=100, lr=0.05, x_max=100, alpha=0.75, seed=0):
    n = len(vocab)
    rng = np.random.default_rng(seed)
    W = rng.normal(0, 0.1, size=(n, dim))
    W_tilde = rng.normal(0, 0.1, size=(n, dim))
    b = np.zeros(n)
    b_tilde = np.zeros(n)

    for epoch in range(epochs):
        for (i, j), x_ij in pair_counts.items():
            weight = (x_ij / x_max) ** alpha if x_ij < x_max else 1.0
            diff = W[i] @ W_tilde[j] + b[i] + b_tilde[j] - np.log(x_ij)
            coef = weight * diff

            grad_W_i = coef * W_tilde[j]
            grad_W_tilde_j = coef * W[i]
            W[i] -= lr * grad_W_i
            W_tilde[j] -= lr * grad_W_tilde_j
            b[i] -= lr * coef
            b_tilde[j] -= lr * coef

    return W + W_tilde
```

两件值得一提的动人作品。加权函数 `f(x) = (x/x_max)^alpha` 会降低非常频繁的对（如 `(the, and)`）的权重，因此它们不会主导损失。最终的embedding是`W`（中心）和`W_tilde`（上下文）表的总和。将两者相加是一种已发表的技巧，往往比仅使用一种技巧效果更好。

<a id="fasttext-subword-aware-embeddings"></a>

### FastText：子字感知 embeddings

```python
def char_ngrams(word, n_min=3, n_max=6):
    wrapped = f"<{word}>"
    grams = {wrapped}
    for n in range(n_min, n_max + 1):
        for i in range(len(wrapped) - n + 1):
            grams.add(wrapped[i:i + n])
    return grams
```

```python
>>> char_ngrams("where")
{'<where>', '<wh', 'whe', 'her', 'ere', 're>', '<whe', 'wher', 'here', 'ere>', '<wher', 'where', 'here>'}
```

每个单词都由其 n 元语法集（通常为 3 到 6 个字符）表示。单词 embedding 是其 n 元语法 embeddings 的总和。对于 skip-gram 训练，请将其插入 Word2Vec 使用单个向量的位置。

```python
def fasttext_vector(word, ngram_table):
    grams = char_ngrams(word)
    vecs = [ngram_table[g] for g in grams if g in ngram_table]
    if not vecs:
        return None
    return np.sum(vecs, axis=0)
```

对于一个看不见的单词，只要它的一些 n 元语法是已知的，您仍然会得到一个向量。 `whereupon` 与 `where` 共享 `<wh`、`her`、`ere` 和 `<where`，因此两者彼此靠近。

<a id="bpe-learned-subword-vocabulary"></a>

### BPE：学习到的子词vocabulary

```python
def learn_bpe(corpus, k_merges):
    vocab = Counter()
    for word, freq in corpus.items():
        tokens = tuple(word) + ("</w>",)
        vocab[tokens] = freq

    merges = []
    for _ in range(k_merges):
        pair_freq = Counter()
        for tokens, freq in vocab.items():
            for a, b in zip(tokens, tokens[1:]):
                pair_freq[(a, b)] += freq
        if not pair_freq:
            break
        best = pair_freq.most_common(1)[0][0]
        merges.append(best)

        new_vocab = Counter()
        for tokens, freq in vocab.items():
            new_tokens = []
            i = 0
            while i < len(tokens):
                if i + 1 < len(tokens) and (tokens[i], tokens[i + 1]) == best:
                    new_tokens.append(tokens[i] + tokens[i + 1])
                    i += 2
                else:
                    new_tokens.append(tokens[i])
                    i += 1
            new_vocab[tuple(new_tokens)] = freq
        vocab = new_vocab
    return merges


def apply_bpe(word, merges):
    tokens = list(word) + ["</w>"]
    for a, b in merges:
        new_tokens = []
        i = 0
        while i < len(tokens):
            if i + 1 < len(tokens) and tokens[i] == a and tokens[i + 1] == b:
                new_tokens.append(a + b)
                i += 2
            else:
                new_tokens.append(tokens[i])
                i += 1
        tokens = new_tokens
    return tokens
```

```python
>>> corpus = Counter({"low": 5, "lower": 2, "newest": 6, "widest": 3})
>>> merges = learn_bpe(corpus, k_merges=10)
>>> apply_bpe("lowest", merges)
['low', 'est</w>']
```

第一次迭代合并最常见的相邻对。经过足够的迭代后，频繁的子串（`low`、`est`、`tion`）变成单个tokens，而罕见的单词则干净地分解。

真正的GPT / BERT / T5 tokenizers 学习30k-100k合并。结果：任何文本都会标记为已知 ID 的有界长度序列，永远不会出现 OOV。

<a id="use-it"></a>

## 实际应用

在实践中，您很少自己训练这些。您加载预训练的 checkpoints。

```python
import fasttext.util
fasttext.util.download_model("en", if_exists="ignore")
ft = fasttext.load_model("cc.en.300.bin")
print(ft.get_word_vector("whereupon").shape)
print(ft.get_word_vector("zoomerapproved").shape)
```

对于transformer时代的BPE样式子字tokenization：

```python
from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained("gpt2")
print(tok.tokenize("unbelievably tokenized"))
```

```
['un', 'bel', 'iev', 'ably', 'Ġtoken', 'ized']
```

`Ġ` 前缀标记字边界（GPT-2 约定）。每个现代 tokenizer 都是 BPE 变体、WordPiece (BERT) 或 SentencePiece (T5, LLaMA)。

<a id="when-to-pick-which"></a>

### 什么时候选择哪个

| 情况 | 挑选 |
|-----------|------|
| 预训练通用词向量，无需 OOV 容错 | 手套 300d |
| 预训练的通用词向量，必须处理拼写错误/新词/形态丰富的语言 | 快速文本 |
| 任何进入 transformer 的内容（训练或 inference） | 无论该型号附带 tokenizer。切勿交换。 |
| 从头开始训练自己的语言模型 | 首先在您的语料库上训练 BPE 或 SentencePiece tokenizer |
| 使用线性模型进行文本分类 | 还是TF-IDF。第 02 课。 |

<a id="ship-it"></a>

## 交付成果

另存为 `outputs/skill-embeddings-picker.md`：

```markdown
---
name: tokenizer-picker
description: Pick a tokenization approach for a new language model or text pipeline.
version: 1.0.0
phase: 5
lesson: 04
tags: [nlp, tokenization, embeddings]
---

Given a task and dataset description, you output:

1. Tokenization strategy (word-level, BPE, WordPiece, SentencePiece, byte-level). One-sentence reason.
2. Vocabulary size target (e.g., 32k for an English-only LM, 64k-100k for multilingual).
3. Library call with the exact training command. Name the library. Quote the arguments.
4. One reproducibility pitfall. Tokenizer-model mismatch is the single most common silent production bug; call out which pair must be used together.

Refuse to recommend training a custom tokenizer when the user is fine-tuning a pretrained LLM. Refuse to recommend word-level tokenization for any model targeting production inference. Flag non-English / multi-script corpora as needing SentencePiece with byte fallback.
```

<a id="exercises"></a>

## 练习

1. **Easy.** 运行`char_ngrams("playing")`和`char_ngrams("played")`。计算两个 n 元组的 Jaccard 重叠。您应该看到大量共享片段（`pla`、`lay`、`play`），这就是 FastText 在形态变体之间迁移良好的原因。
2. **Medium.** 扩展 `learn_bpe` 以跟踪 vocabulary 的增长。将 tokens-per-corpus-character 绘制为合并次数的函数。您首先应该看到快速压缩，每个 token 渐近约 2-3 个字符。
3. **Hard.** 在莎士比亚全集上训练 1k 合并 BPE。比较常用词 tokenization 与罕见专有名词。测量前后每个单词的平均值 tokens。写下令你惊讶的事情。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| 共现矩阵 | 词词频率表 | `X[i][j]` = 单词 `j` 在单词 `i` 周围的窗口中出现的频率。 |
| 子词 | 一段话 | 字符 n-gram (FastText) 或学习的 token (BPE/WordPiece/SentencePiece)。 |
| BPE | 字节对编码 | 迭代合并最频繁的相邻对，直到 vocabulary 达到目标大小。 |
| 外用病毒 | 出vocabulary | 模特从未见过的词。 Word2Vec/GloVe 失败。 FastText 和 BPE 处理它。 |
| 字节级 BPE | 原始字节上的 BPE | GPT-2的方案。 Vocabulary 以 256 字节开头，因此不会出现 OOV。 |

<a id="further-reading"></a>

## 进一步阅读

- [Pennington、Socher、Manning (2014)。 GloVe: Global Vectors for Word Representation](https://nlp.stanford.edu/pubs/glove.pdf) — GloVe 论文，七页，仍然是损失的最佳推导。
- [Bojanowski 等人。 （2017）。使用子词信息丰富词向量](https://arxiv.org/abs/1607.04606) — FastText。
- [Sennrich、Haddow、Birch (2016)。具有子词单元的稀有词的神经机器翻译](https://arxiv.org/abs/1508.07909) - 将 BPE 引入现代 NLP 的论文。
- [Hugging Face tokenizer 摘要](https://huggingface.co/docs/transformers/tokenizer_summary) — BPE、WordPiece 和 SentencePiece 实际上有何不同练习。
