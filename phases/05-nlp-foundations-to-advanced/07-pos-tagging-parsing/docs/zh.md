<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="pos-tagging-and-syntactic-parsing"></a>

# 词性标注和句法分析

> 语法一度不流行。然后每个 LLM 管道都需要验证结构化提取，然后它就回来了。

**类型：** 构建
**语言：** Python
**先决条件：** 第 5 阶段·01（文本处理）、第 2 阶段·14（朴素贝叶斯）
**时间：** ~45分钟

<a id="the-problem"></a>

## 问题

第 01 课承诺词形还原需要词性标记。在不知道 `running` 是动词的情况下，词形还原器无法将其简化为 `run`。如果不知道 `better` 是形容词，则无法简化为 `good`。

这个承诺隐藏了整个子领域。词性标注指定语法类别。句法解析恢复句子的树结构：哪个单词修饰哪个，哪个动词控制哪个参数。经典 NLP 花了二十年的时间完善这两者。然后深度学习将它们分解为预训练的 transformer 之上的 token 分类任务，研究社区继续前进。

不是应用社区。每个结构化提取管道仍然在底层使用 POS 和依赖树。 LLM 生成的 JSON 根据语法约束进行验证。问答系统使用依赖性解析来分解查询。机器翻译质量评估人员检查解析树的 alignment。

值得了解。本课程介绍标签集、基线以及停止从头开始实施并调用 spaCy 的点。

<a id="the-concept"></a>

## 概念

**词性标记** 用语法类别标记每个 token。 **Penn Treebank (PTB)** 标记集是英文默认标记集。 36 个标签，具有普通读者觉得挑剔的区别：`NN` 单数名词，`NNS` 复数名词，`NNP` 专有名词单数，`VBD` 动词过去时态，`VBZ` 动词第三人称单数目前，等等。 **通用依赖项 (UD)** 标记集更粗糙（17 个标记）并且与语言无关；它成为跨语言工作的默认设置。

```
The/DET cats/NOUN were/AUX running/VERB at/ADP 3pm/NOUN ./PUNCT
```

**句法解析**生成一棵树。两大风格：

- **选区解析。** 名词短语、动词短语、介词短语相互嵌套。输出是一棵非终结类别（NP、VP、PP）树，以单词为叶子。
- **依存解析。** 每个单词都有一个它所依赖的头词，并标有语法关系。输出是一棵树，其中每条边都是一个（头、依赖、关系）三元组。

依存解析在 2010 年代取得了胜利，因为它能够清晰地概括各种语言，尤其是自由词序语言。

```
running is ROOT
cats is nsubj of running
were is aux of running
at is prep of running
3pm is pobj of at
```

```figure
pos-tagger
```

```figure
dependency-arcs
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-most-frequent-tag-baseline"></a>

### 第 1 步：最常见标签基线

最愚蠢但有效的 POS 标记器。对于每个单词，预测它在训练中最常使用的标签。

```python
from collections import Counter, defaultdict


def train_mft(train_examples):
    word_tag_counts = defaultdict(Counter)
    all_tags = Counter()
    for tokens, tags in train_examples:
        for token, tag in zip(tokens, tags):
            word_tag_counts[token.lower()][tag] += 1
            all_tags[tag] += 1
    word_best = {w: c.most_common(1)[0][0] for w, c in word_tag_counts.items()}
    default_tag = all_tags.most_common(1)[0][0]
    return word_best, default_tag


def predict_mft(tokens, word_best, default_tag):
    return [word_best.get(t.lower(), default_tag) for t in tokens]
```

在 Brown 语料库上，该基线的准确率约为 85%。不好，但是任何严肃的模型都不应该跌倒在这个底线以下。

<a id="step-2-bigram-hmm-tagger"></a>

### 步骤 2：二元 HMM 标注器

对序列的联合概率建模：

```
P(tags, words) = prod P(tag_i | tag_{i-1}) * P(word_i | tag_i)
```

两个表：转移概率（给定前一个标签的标签）、发射概率（给定单词的标签）。通过拉普拉斯平滑的计数来估计两者。使用维特比（Viterbi）解码（标签格上的动态编程）。

```python
import math


def train_hmm(train_examples, alpha=0.01):
    transitions = defaultdict(Counter)
    emissions = defaultdict(Counter)
    tags = set()
    vocab = set()

    for tokens, ts in train_examples:
        prev = "<BOS>"
        for token, tag in zip(tokens, ts):
            transitions[prev][tag] += 1
            emissions[tag][token.lower()] += 1
            tags.add(tag)
            vocab.add(token.lower())
            prev = tag
        transitions[prev]["<EOS>"] += 1

    return transitions, emissions, tags, vocab


def log_prob(table, given, key, smooth_denom, alpha):
    return math.log((table[given].get(key, 0) + alpha) / smooth_denom)


def viterbi(tokens, transitions, emissions, tags, vocab, alpha=0.01):
    tags_list = list(tags)
    n = len(tokens)
    V = [[0.0] * len(tags_list) for _ in range(n)]
    back = [[0] * len(tags_list) for _ in range(n)]

    for j, tag in enumerate(tags_list):
        em_denom = sum(emissions[tag].values()) + alpha * (len(vocab) + 1)
        tr_denom = sum(transitions["<BOS>"].values()) + alpha * (len(tags_list) + 1)
        tr = log_prob(transitions, "<BOS>", tag, tr_denom, alpha)
        em = log_prob(emissions, tag, tokens[0].lower(), em_denom, alpha)
        V[0][j] = tr + em
        back[0][j] = 0

    for i in range(1, n):
        for j, tag in enumerate(tags_list):
            em_denom = sum(emissions[tag].values()) + alpha * (len(vocab) + 1)
            em = log_prob(emissions, tag, tokens[i].lower(), em_denom, alpha)
            best_prev = 0
            best_score = -1e30
            for k, prev_tag in enumerate(tags_list):
                tr_denom = sum(transitions[prev_tag].values()) + alpha * (len(tags_list) + 1)
                tr = log_prob(transitions, prev_tag, tag, tr_denom, alpha)
                score = V[i - 1][k] + tr + em
                if score > best_score:
                    best_score = score
                    best_prev = k
            V[i][j] = best_score
            back[i][j] = best_prev

    last_best = max(range(len(tags_list)), key=lambda j: V[n - 1][j])
    path = [last_best]
    for i in range(n - 1, 0, -1):
        path.append(back[i][path[-1]])
    return [tags_list[j] for j in reversed(path)]
```

Brown 上的 Bigram HMM 准确率约为 93%。从 85% 到 93% 的跳跃主要是转换概率——模型学习 `DET NOUN` 很常见，而 `NOUN DET` 很罕见。

<a id="step-3-why-modern-taggers-beat-this"></a>

### 第 3 步：为什么现代标记器打败了这个

转变+发射概率是局部的。他们无法捕捉到 `saw` 在“我买了一把锯子”中是一个名词，但在“我看过电影”中是一个动词。具有任意 features（后缀、单词形状、单词前后、单词本身）的 CRF 命中率约为 97%。 BiLSTM-CRF 或 transformer 达到约 98%+。

这项任务的上限是由注释者的分歧决定的。在 Penn Treebank 上，人类注释者的认同率约为 97%。超过 98% 的模型可能是 overfitting 测试集。

<a id="step-4-dependency-parsing-sketch"></a>

### 第四步：依存解析草图

从头开始进行完整的依赖关系解析超出了范围；尤拉夫斯基和马丁的经典教科书处理方法是这样的。两个值得了解的经典家族：

- **Transition-based** 解析器（arc-eager、arc-standard）的作用类似于移位归约解析器：它们读取 tokens，将它们移到堆栈上，并应用创建弧的归约操作。贪心解码速度很快。经典的实现是 MaltParser。现代神经版本：Chen 和 Manning 的基于转换的解析器。
- **基于图的**解析器（Eisner算法，Dozat-Manning biaffine）对每个可能的头相关边缘进行评分并选择最大生成树。更慢但更准确。

对于大多数应用工作，请致电 spaCy：

```python
import spacy

nlp = spacy.load("en_core_web_sm")
doc = nlp("The cats were running at 3pm.")
for token in doc:
    print(f"{token.text:10s} tag={token.tag_:5s} pos={token.pos_:6s} dep={token.dep_:10s} head={token.head.text}")
```

```
The        tag=DT    pos=DET    dep=det        head=cats
cats       tag=NNS   pos=NOUN   dep=nsubj      head=running
were       tag=VBD   pos=AUX    dep=aux        head=running
running    tag=VBG   pos=VERB   dep=ROOT       head=running
at         tag=IN    pos=ADP    dep=prep       head=running
3pm        tag=NN    pos=NOUN   dep=pobj       head=at
.          tag=.     pos=PUNCT  dep=punct      head=running
```

从下到上阅读 `dep` 栏，句子的语法结构就出来了。

<a id="use-it"></a>

## 实际应用

每个生产 NLP 库都将 POS 和依赖解析器作为标准管道的一部分提供。

- **spaCy**（`en_core_web_sm` / `md` / `lg` / `trf`）。快速、准确，与 tokenization + NER + 词形还原集成。 `token.tag_`（宾夕法尼亚州）、`token.pos_`（UD）、`token.dep_`（依赖关系）。
- **斯坦福自然语言处理（节）**。斯坦福大学 CoreNLP 的继任者。支持 60 多种语言的最先进技术。
- **trankit**。基于Transformer，UD精度好。
- **NLTK**。 `pos_tag`。可用，慢，旧。适合教学。

<a id="where-this-still-matters-in-2026"></a>

### 到 2026 年，这一点仍然很重要

- **Lemmatization.** 第 01 课需要 POS 才能正确进行词形还原。总是。
- ** 从 LLM 输出中结构化提取。** 验证生成的句子是否遵守语法约束（例如，主谓一致、所需修饰语）。
- **基于Aspect的情感。** 依赖解析告诉您哪个形容词修饰哪个名词。
- **查询理解。**“由韦斯·安德森执导的比尔·默里主演的电影”通过解析分解为结构化约束。
- **跨语言传输。** UD标签和依赖关系与语言无关，支持zero-shot对新语言的结构化分析。
- **低计算管道。** 如果您无法发送 transformer，POS + 依赖解析 + 地名词典可以让您出人意料地走得更远。

<a id="ship-it"></a>

## 交付成果

另存为 `outputs/skill-grammar-pipeline.md`：

```markdown
---
name: grammar-pipeline
description: Design a classical POS + dependency pipeline for a downstream NLP task.
version: 1.0.0
phase: 5
lesson: 07
tags: [nlp, pos, parsing]
---

Given a downstream task (information extraction, rewrite validation, query decomposition, lemmatization), you output:

1. Tagset to use. Penn Treebank for English-only legacy pipelines, Universal Dependencies for multilingual or cross-lingual.
2. Library. spaCy for most production, stanza for academic-grade multilingual, trankit for highest UD accuracy. Name the specific model ID.
3. Integration pattern. Show the 3-5 lines that call the library and consume the needed attributes (`.pos_`, `.dep_`, `.head`).
4. Failure mode to test. Noun-verb ambiguity (`saw`, `book`, `can`) and PP-attachment ambiguity are the classical traps. Sample 20 outputs and eyeball.

Refuse to recommend rolling your own parser. Building parsers from scratch is a research project, not an application task. Flag any pipeline that consumes POS tags without handling lowercase/uppercase variants as fragile.
```

<a id="exercises"></a>

## 练习

1. **Easy.** 在小型标记语料库（例如 NLTK 的 Brown 子集）上使用最常见的标记基线，测量保留句子的准确性。验证 ~85% 结果。
2. **Medium.** 训练上面的二元模型 HMM 并报告每个标签的精确率/召回率。 HMM 最容易混淆哪些标签？
3. **Hard.** 使用 spaCy 的依存解析从 1000 个句子样本中提取主谓宾三元组。评估 50 个手动标记的三元组。记录提取失败的地方（通常是被动语态、并列语态和省略主语）。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| POS 标签 | 词的类型 | 语法范畴。 PTB有36个； UD有17个。 |
| 宾夕法尼亚树库 | 标准标签集 | 英语专用。细粒度的动词时态和名词数。 |
| 通用依赖关系 | 多语言标签集 | 比PTB更粗；语言中立；跨语言工作的默认设置。 |
| 依赖解析 | 句子树 | 每个单词都有一个头，每个边都有一个语法关系。 |
| 维特比 | 动态规划 | 查找给定发射和跃迁的最高概率标签序列。 |

<a id="further-reading"></a>

## 进一步阅读

- [Jurafsky 和 Martin — 语音和语言处理，第 8 章和第 18 章](https://web.stanford.edu/~jurafsky/slp3/) — POS 和解析的规范教科书处理。
- [通用依赖项项目](https://universaldependencies.org/) - 每个多语言解析器使用的跨语言标记集和树库集合。
- [spaCy 语言 features 指南](https://spacy.io/usage/linguistic-features) — `Token` 上公开的每个属性的实用参考。
- [Chen 和曼宁 (2014)。 A Fast and Accurate Dependency Parser using Neural Networks](https://nlp.stanford.edu/pubs/emnlp2014-depparser.pdf)——这篇论文将神经解析器带入了主流。
