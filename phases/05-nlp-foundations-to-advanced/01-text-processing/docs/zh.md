<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="text-processing--tokenization-stemming-lemmatization"></a>

# 文本处理 — Tokenization、词干提取、词形还原

> 语言是连续的。模型是离散的。预处理是桥梁。

**类型：** 构建
**语言：** Python
**先决条件：** 第 2 阶段·14（朴素贝叶斯）
**时间：** ~45分钟

<a id="the-problem"></a>

## 问题

模型无法读取“猫在奔跑”。它读取整数。

每个 NLP 系统都以相同的三个问题开始。一个词从哪里开始。这个词的词根是什么。当“跑步”、“跑步”、“跑步”有帮助时，我们如何将其视为同一件事，而无帮助时，我们如何将其视为不同的事情。

如果 tokenization 错误，模型就会从垃圾中学习。如果您的 tokenizer 将 `don't` 视为一个 token 而将 `do n't` 视为两个，则训练分布会分裂。如果您的词干分析器将 `organization` 和 `organ` 折叠为同一个词干，则主题建模就会终止。如果您的词形还原器需要词性上下文，但您没有传递它，则动词将被视为名词。

本课程从头开始构建三个预处理步骤，然后展示 NLTK 和 spaCy 如何执行相同的工作，以便您可以看到权衡。

<a id="the-concept"></a>

## 概念

三个操作。每个人都有一个工作和一个失败模式。

**Tokenization** 将字符串拆分为 tokens。 “Token”故意含糊不清，因为正确的粒度取决于任务。经典 NLP 的词级。 transformers 的子字。没有空格的语言的字符。

**Stemming** 用规则去除后缀。快速、侵略性、愚蠢。 `running -> run`。 `organization -> organ`。第二个是故障模式。

**词形还原** 使用语法知识将单词还原为其字典形式。较慢，准确，需要查找表或形态分析器。 `ran -> run`（需要知道“ran”是“run”的过去时）。 `better -> good`（需要知道比较形式）。

经验法则。当速度很重要并且您可以容忍噪音（搜索索引、粗略分类）时，进行茎干。当意义很重要时进行词形还原（问答、semantic search、用户会读到的任何内容）。

```figure
edit-distance
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-a-regex-word-tokenizer"></a>

### 步骤1：正则表达式单词tokenizer

最简单有用的 tokenizer 在非字母数字字符上进行拆分，同时将标点符号保留为其自己的 tokens。不完美，不是最终的，但它在一行中运行。

```python
import re

def tokenize(text):
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|[0-9]+|[^\sA-Za-z0-9]", text)
```

三种模式按优先顺序排列。带有可选内撇号的单词（`don't`、`it's`）。纯数字。任何单个非空白非字母数字字符作为独立的 token（标点符号）。

```python
>>> tokenize("The cats weren't running at 3pm.")
['The', 'cats', "weren't", 'running', 'at', '3', 'pm', '.']
```

需要注意的故障模式。 `3pm` 拆分为 `['3', 'pm']`，因为我们在字母运行和数字运行之间交替。足以胜任大多数任务。网址、电子邮件、主题标签全部失效。对于生产，请在常规模式之前添加模式。

<a id="step-2-a-porter-stemmer-step-1a-only"></a>

### 步骤 2：Porter 词干分析器（仅限步骤 1a）

完整的波特算法有五个阶段的规则。仅步骤 1a 就涵盖了最常见的英语后缀并教授了该模式。

```python
def stem_step_1a(word):
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("ies"):
        return word[:-2]
    if word.endswith("ss"):
        return word
    if word.endswith("s") and len(word) > 1:
        return word[:-1]
    return word
```

```python
>>> [stem_step_1a(w) for w in ["caresses", "ponies", "caress", "cats"]]
['caress', 'poni', 'caress', 'cat']
```

自上而下阅读规则。 `ies -> i`规则就是为什么`ponies -> poni`，而不是`pony`。 Real Porter 有步骤 1b 可以解决这个问题。规则竞争。较早的规则获胜。顺序比任何单一规则更重要。

<a id="step-3-a-lookup-based-lemmatizer"></a>

### 步骤 3：基于查找的词形还原器

正确的词形还原需要形态学。易于处理的教学版本使用小引理表和后备。

```python
LEMMA_TABLE = {
    ("running", "VERB"): "run",
    ("ran", "VERB"): "run",
    ("runs", "VERB"): "run",
    ("better", "ADJ"): "good",
    ("best", "ADJ"): "good",
    ("cats", "NOUN"): "cat",
    ("cat", "NOUN"): "cat",
    ("were", "VERB"): "be",
    ("was", "VERB"): "be",
    ("is", "VERB"): "be",
}

def lemmatize(word, pos):
    key = (word.lower(), pos)
    if key in LEMMA_TABLE:
        return LEMMA_TABLE[key]
    if pos == "VERB" and word.endswith("ing"):
        return word[:-3]
    if pos == "NOUN" and word.endswith("s"):
        return word[:-1]
    return word.lower()
```

```python
>>> lemmatize("running", "VERB")
'run'
>>> lemmatize("cats", "NOUN")
'cat'
>>> lemmatize("better", "ADJ")
'good'
>>> lemmatize("watched", "VERB")
'watched'
```

最后一个案例是教学的关键时刻。 `watched` 不在我们的表中，我们的后备仅处理 `ing`。真正的词形还原涵盖`ed`、不规则动词、形容词比较级、带声音变化的复数(`children -> child`)。这就是生产系统使用 WordNet、spaCy 的形态分析器或完整形态分析器的原因。

<a id="step-4-pipe-them-together"></a>

### 第四步：用管道将它们连接在一起

```python
def preprocess(text, pos_tagger=None):
    tokens = tokenize(text)
    stems = [stem_step_1a(t.lower()) for t in tokens]
    tags = pos_tagger(tokens) if pos_tagger else [(t, "NOUN") for t in tokens]
    lemmas = [lemmatize(word, pos) for word, pos in tags]
    return {"tokens": tokens, "stems": stems, "lemmas": lemmas}
```

缺少的部分是 POS 标记器。第 5·07 阶段（POS 标签）构建一个。现在，将所有内容默认为 `NOUN` 并承认该限制。

<a id="use-it"></a>

## 实际应用

NLTK 和 spaCy 提供量产版本。每行几行。

<a id="nltk"></a>

### NLTK

```python
import nltk
nltk.download("punkt_tab")
nltk.download("wordnet")
nltk.download("averaged_perceptron_tagger_eng")

from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer, WordNetLemmatizer
from nltk import pos_tag

text = "The cats were running."
tokens = word_tokenize(text)
stems = [PorterStemmer().stem(t) for t in tokens]
lemmatizer = WordNetLemmatizer()
tagged = pos_tag(tokens)


def nltk_pos_to_wordnet(tag):
    if tag.startswith("V"):
        return "v"
    if tag.startswith("J"):
        return "a"
    if tag.startswith("R"):
        return "r"
    return "n"


lemmas = [lemmatizer.lemmatize(t, nltk_pos_to_wordnet(tag)) for t, tag in tagged]
```

`word_tokenize` 处理收缩，Unicode 处理正则表达式错过的边缘情况。 `PorterStemmer` 运行所有五个阶段。 `WordNetLemmatizer` 需要将 POS 标签从 NLTK 的 Penn Treebank 方案转换为 WordNet 的缩写集。上面的翻译接线是大多数教程都会跳过的部分。

<a id="spacy"></a>

### spaCy

```python
import spacy

nlp = spacy.load("en_core_web_sm")
doc = nlp("The cats were running.")

for token in doc:
    print(token.text, token.lemma_, token.pos_)
```

```
The      the     DET
cats     cat     NOUN
were     be      AUX
running  run     VERB
.        .       PUNCT
```

spaCy 将整个管道隐藏在 `nlp(text)` 后面。 Tokenization、词性标记和词形还原全部运行。规模上比 NLTK 更快。开箱即用更准确。代价是您无法轻松更换各个组件。

<a id="when-to-pick-which"></a>

### 什么时候选择哪个

| 情况 | 挑选 |
|-----------|------|
| 教学、研究、交换组件 | NLTK |
| 制作、多语言、速度很重要 | spaCy |
| Transformer 管道（无论如何，您都将使用模型的 tokenizer 进行标记） | 使用 `tokenizers` / `transformers` 并跳过经典预处理 |

<a id="the-two-failure-modes-nobody-warns-you-about"></a>

### 没有人警告您的两种故障模式

大多数教程只教授算法然后就停止了。有两件事会影响真正的预处理流程，而它们几乎从未被覆盖。

**再现性漂移。** NLTK 和 spaCy 更改 tokenization 和版本之间的词形还原器行为。在spaCy 2.x中产生`['do', "n't"]`的东西可能在3.x中产生`["don't"]`。您的模型是在一种分布上进行训练的。 Inference 现在在另一台上运行。准确性悄然下降，但没有人知道原因。 `requirements.txt` 中的引脚库版本。编写一个预处理 regression test，冻结 20 个例句的预期 tokenization。每次升级时运行它。

**Training / inference 不匹配。** 通过积极的预处理（小写、停用词删除、词干）进行训练，部署在原始用户输入上，观察性能下降情况。这是最常见的生产 NLP 失败。如果在训练期间进行预处理，则必须在 inference 期间运行相同的函数。将预处理作为模型包内的函数发送，而不是作为服务团队重写的笔记本单元。

<a id="ship-it"></a>

## 交付成果

可重复使用的 prompt 可以帮助工程师选择预处理策略，而无需阅读三本教科书。

另存为`outputs/prompt-preprocessing-advisor.md`：

```markdown
---
name: preprocessing-advisor
description: Recommends a tokenization, stemming, and lemmatization setup for an NLP task.
phase: 5
lesson: 01
---

You advise on classical NLP preprocessing. Given a task description, you output:

1. Tokenization choice (regex, NLTK word_tokenize, spaCy, or transformer tokenizer). Explain why.
2. Whether to stem, lemmatize, both, or neither. Explain why.
3. Specific library calls. Name the functions. Quote the POS-tag translation if NLTK is involved.
4. One failure mode the user should test for.

Refuse to recommend stemming for user-visible text. Refuse to recommend lemmatization without POS tags. Flag non-English input as needing a different pipeline.
```

<a id="exercises"></a>

## 练习

1. **Easy.** 扩展 `tokenize` 以将 URL 保留为单个 tokens。测试：`tokenize("Visit https://example.com today.")` 应生成一个 URL token。
2. **Medium.** 实施波特步骤 1b。如果单词包含元音且以 `ed` 或 `ing` 结尾，请将其删除。处理双辅音规则（`hopping -> hop`，而不是 `hopp`）。
3. **Hard.** 构建一个词形还原器，它使用 WordNet 作为查找表，但当 WordNet 没有条目时回退到 Porter 词干分析器。对照普通 WordNet 和普通 Porter 测量标记语料库的准确性。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| Token | 一句话 | 无论模型消耗多少单位。可以是字、子字、字符或字节。 |
| 茎 | 词根 | 基于规则的后缀剥离的结果。并不总是一个真实的词。 |
| 引理 | 词典形式 | 您要查找的表格。需要语法上下文才能正确计算。 |
| POS 标签 | 词类 | 名词、动词、形容词等类别。需要准确地进行词形还原。 |
| 形态学 | 字形规则 | 单词如何根据时态、数字、大小写改变形式。词形还原取决于它。 |

<a id="further-reading"></a>

## 进一步阅读

- [Porter，M.F.（1980）。后缀剥离的算法](https://tartarus.org/martin/PorterStemmer/def.txt)——原始论文，五页，仍然是最清晰的解释。
- [spaCy 101 — 语言 features](https://spacy.io/usage/linguistic-features) — 真实管道的接线方式。
- [NLTK 书，第 3 章](https://www.nltk.org/book/ch03.html) — tokenization 您尚未想到的边缘情况。
