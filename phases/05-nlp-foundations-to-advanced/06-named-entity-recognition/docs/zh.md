<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="named-entity-recognition"></a>

# 命名实体识别

> 把名字拉出来。听起来很容易，直到您处理不明确的边界、嵌套实体和领域术语。

**类型：** 构建
**语言：** Python
**先决条件：** 第 5 阶段·02 (BoW + TF-IDF)、第 5 阶段·03 (字 Embeddings)
**时间：** ~75分钟

<a id="the-problem"></a>

## 问题

“苹果公司就其在美国的 iPhone 搜索协议起诉谷歌。”五个实体：苹果（ORG）、谷歌（ORG）、iPhone（产品）、搜索交易（可能）、美国（GPE）。一个好的 NER 系统会以正确的类型提取所有这些内容。一个坏人会错过 iPhone，将苹果这个水果与苹果公司混淆，并将“美国”标记为一个人。

NER 是每个结构化提取管道下的主力。简历解析、合规日志扫描、医疗记录匿名化、搜索查询理解、用于聊天机器人响应的 grounding、法律合同提取。你永远不会完全看清它；你总是依赖它。

本课程将经典路径（基于规则、HMM、CRF）引入现代路径（BiLSTM-CRF，然后是 transformers）。每一步都解决了前一步的特定限制。模式就是教训。

<a id="the-concept"></a>

## 概念

**BIO 标记**（或 BILOU）将实体提取变成序列标记问题。将每个 token 标记为 `B-TYPE`（实体开头）、`I-TYPE`（内部实体）或 `O`（任何实体外部）。

```
Apple    B-ORG
sued     O
Google   B-ORG
over     O
its      O
iPhone   B-PRODUCT
search   O
deal     O
in       O
the      O
US       B-GPE
.        O
```

多条token实体链：`New B-GPE`、`York I-GPE`、`City I-GPE`。理解 BIO 的模型可以提取任意范围。

架构进展：

- **基于规则。** 正则表达式 + 地名词典查找。对已知实体的高精度，对新实体的零覆盖。
- **HMM.** 隐马尔可夫模型。 token 给定标签的发射概率，标签到标签的转移概率。维特比解码。根据标记数据进行训练。
- **CRF.** 条件随机字段。与 HMM 类似，但具有区分性，因此您可以混合任意 features（词形、大小写、相邻词）。到 2026 年，它仍然是低资源部署的经典生产主力。
- **BiLSTM-CRF.** 神经 features 而不是手工制作。 LSTM 双向读取句子，顶部的 CRF 层强制执行一致的标签序列。
- **Transformer-based.** 使用 token 分类头微调 BERT。最佳准确度。大多数计算。

```figure
ner-bio-tagging
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-bio-tagging-helpers"></a>

### 第 1 步：BIO 标记助手

```python
def spans_to_bio(tokens, spans):
    labels = ["O"] * len(tokens)
    for start, end, label in spans:
        labels[start] = f"B-{label}"
        for i in range(start + 1, end):
            labels[i] = f"I-{label}"
    return labels


def bio_to_spans(tokens, labels):
    spans = []
    current = None
    for i, label in enumerate(labels):
        if label.startswith("B-"):
            if current:
                spans.append(current)
            current = (i, i + 1, label[2:])
        elif label.startswith("I-") and current and current[2] == label[2:]:
            current = (current[0], i + 1, current[2])
        else:
            if current:
                spans.append(current)
                current = None
    if current:
        spans.append(current)
    return spans
```

```python
>>> tokens = ["Apple", "sued", "Google", "over", "iPhone", "sales", "."]
>>> labels = ["B-ORG", "O", "B-ORG", "O", "B-PRODUCT", "O", "O"]
>>> bio_to_spans(tokens, labels)
[(0, 1, 'ORG'), (2, 3, 'ORG'), (4, 5, 'PRODUCT')]
```

<a id="step-2-hand-crafted-features"></a>

### 步骤2：手工制作features

对于经典（非神经）NER，features 是游戏。有用的：

```python
def token_features(token, prev_token, next_token):
    return {
        "lower": token.lower(),
        "is_upper": token.isupper(),
        "is_title": token.istitle(),
        "has_digit": any(c.isdigit() for c in token),
        "suffix_3": token[-3:].lower(),
        "shape": word_shape(token),
        "prev_lower": prev_token.lower() if prev_token else "<BOS>",
        "next_lower": next_token.lower() if next_token else "<EOS>",
    }


def word_shape(word):
    out = []
    for c in word:
        if c.isupper():
            out.append("X")
        elif c.islower():
            out.append("x")
        elif c.isdigit():
            out.append("d")
        else:
            out.append(c)
    return "".join(out)
```

`word_shape("iPhone")` 返回 `xXxxxx`。 `word_shape("USA-2024")` 返回 `XXX-dddd`。大小写模式对于专有名词来说是高信号的。

<a id="step-3-a-simple-rule-based--dictionary-baseline"></a>

### 第三步：简单的基于规则+字典的基线

```python
ORG_GAZETTEER = {"Apple", "Google", "Microsoft", "OpenAI", "Meta", "Amazon", "Netflix"}
GPE_GAZETTEER = {"US", "USA", "UK", "India", "Germany", "France"}
PRODUCT_GAZETTEER = {"iPhone", "Android", "Windows", "ChatGPT", "Claude"}


def rule_based_ner(tokens):
    labels = []
    for token in tokens:
        if token in ORG_GAZETTEER:
            labels.append("B-ORG")
        elif token in GPE_GAZETTEER:
            labels.append("B-GPE")
        elif token in PRODUCT_GAZETTEER:
            labels.append("B-PRODUCT")
        else:
            labels.append("O")
    return labels
```

生产地名词典有数百万条从 Wikipedia 和 DBpedia 中删除的条目。覆盖范围很好。消歧（`Apple` 公司 vs 水果）很糟糕。这就是统计模型获胜的原因。

<a id="step-4-the-crf-step-sketch-not-full-impl"></a>

### 第 4 步：CRF 步骤（草图，未完整实现）

如果没有概率论基础，50 行从头开始的完整 CRF 就没有启发性。使用 `sklearn-crfsuite` 代替：

```python
import sklearn_crfsuite

def to_features(tokens):
    out = []
    for i, tok in enumerate(tokens):
        prev = tokens[i - 1] if i > 0 else ""
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        out.append({
            "word.lower()": tok.lower(),
            "word.isupper()": tok.isupper(),
            "word.istitle()": tok.istitle(),
            "word.isdigit()": tok.isdigit(),
            "word.suffix3": tok[-3:].lower(),
            "word.shape": word_shape(tok),
            "prev.word.lower()": prev.lower(),
            "next.word.lower()": nxt.lower(),
            "BOS": i == 0,
            "EOS": i == len(tokens) - 1,
        })
    return out


crf = sklearn_crfsuite.CRF(algorithm="lbfgs", c1=0.1, c2=0.1, max_iterations=100, all_possible_transitions=True)
X_train = [to_features(s) for s in sentences_tokenized]
crf.fit(X_train, bio_labels_train)
```

`c1`和`c2`是L1和L2正则化。 `all_possible_transitions=True` 让模型学习非法序列（例如 `O` 之后的 `I-ORG`）不太可能，这就是 CRF 在不编写约束的情况下强制 BIO 一致性的方式。

<a id="step-5-what-a-bilstm-crf-adds"></a>

### 第 5 步：BiLSTM-CRF 添加了什么

Features变得博学。 输入：token embeddings（GloVe 或 fastText）。 LSTM 从左到右和从右到左读取。 连接的隐藏状态经过 CRF 输出层。 CRF 仍然强制标签序列一致性； LSTM 取代了手工制作features与有学问的人。

```python
import torch
import torch.nn as nn


class BiLSTM_CRF_Head(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, n_labels):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, bidirectional=True, batch_first=True)
        self.fc = nn.Linear(hidden_dim * 2, n_labels)

    def forward(self, token_ids):
        e = self.embed(token_ids)
        h, _ = self.lstm(e)
        emissions = self.fc(h)
        return emissions
```

对于CRF层，使用`torchcrf.CRF`（pip安装pytorch-crf）。相对于手工制作的 CRF 的收益是可测量的，但比您预期的要小，除非您有数以万计的标记句子。

<a id="use-it"></a>

## 实际应用

spaCy 开箱即用交付生产级 NER。

```python
import spacy

nlp = spacy.load("en_core_web_sm")
doc = nlp("Apple sued Google over its iPhone search deal in the US.")
for ent in doc.ents:
    print(f"{ent.text:20s} {ent.label_}")
```

```
Apple                ORG
Google               ORG
iPhone               ORG
US                   GPE
```

请注意，`iPhone` 标记为 `ORG`，而不是 `PRODUCT` — spaCy 的小模型的产品实体覆盖率较弱。大模型（`en_core_web_lg`）表现更好。 transformer 模型 (`en_core_web_trf`) 的表现更好。

基于 BERT 的 NER 的拥抱脸：

```python
from transformers import pipeline

ner = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")
print(ner("Apple sued Google over its iPhone in the US."))
```

```
[{'entity_group': 'ORG', 'word': 'Apple', ...},
 {'entity_group': 'ORG', 'word': 'Google', ...},
 {'entity_group': 'MISC', 'word': 'iPhone', ...},
 {'entity_group': 'LOC', 'word': 'US', ...}]
```

`aggregation_strategy="simple"` 将连续的 B-X、I-X tokens 合并到一个跨度中。如果没有它，您将获得 token 级别的标签，并且必须自行合并。

<a id="llm-based-ner-the-2026-option"></a>

### 基于LLM的NER（2026选项）

Zero-shot 和 few-shot LLM NER 现在在许多领域都具有与微调模型的竞争力，并且在标记数据稀缺时表现得更好。

- **Zero-shot 提示。** 为 LLM 提供实体类型列表和示例架构。请求 JSON 输出。开箱即用；在新领域的准确性是中等的。
- **ZeroTuneBio式提示。** 将任务分解为候选提取→意义解释→判断→重新检查。多级 prompt（非一次性）大大提高了生物医学 NER 的准确性。同样的模式也适用于法律、金融和科学领域。
- **动态提示RAG。**从每个带注释的小型种子集中检索最相似的标记示例inference称呼; 建立few-shot prompt在飞行中。 在 2026 年基准中，这一提升GPT-4 生物医学 NER F1 比静态提示提高 11-12%。
- **每实体类型分解。** 对于长文档，一次提取所有实体类型的单个调用会随着长度的增长而失去召回率。每种实体类型运行一次提取过程。 inference 成本更高，精度大幅提高。这是临床记录和法律合同的标准模式。

截至 2026 年的生产建议：在收集训练数据之前，从 LLM zero-shot 基线开始。通常 F1 已经足够好，您无需进行微调。

<a id="where-classical-ner-still-wins"></a>

### 经典 NER 仍然获胜的地方

即使 LLMs 可用，经典 NER 在以下情况下仍会获胜：

- 延迟预算低于 50 毫秒。
- 您有数千个带标签的示例，并且需要 98%+ F1。
- 该领域有一个稳定的本体，预训练的 CRF 或 BiLSTM 可以很好地传输。
- 监管限制需要本地的非生成模型。

<a id="where-it-falls-apart"></a>

### 它崩溃的地方

- **域转移。** CoNLL 训练的法律合同 NER 的表现比地名词典差。对您的域进行微调。
- **嵌套实体。**“美国银行大厦”同时是一个组织和设施。标准 BIO 无法表示重叠的跨度。您需要嵌套 NER（多通道或基于跨度的模型）。
- **长实体。**“美国联邦存款保险公司”。 Token级别的型号有时会出现这种情况。使用`aggregation_strategy`或后处理。
- **稀疏类型。** 医疗 NER 标签，如 DRUG_BRAND、ADVERSE_EVENT、剂量。通用模型不知道。 Scispacy 和 BioBERT 是这方面的起点。

<a id="ship-it"></a>

## 交付成果

另存为 `outputs/skill-ner-picker.md`：

```markdown
---
name: ner-picker
description: Pick the right NER approach for a given extraction task.
version: 1.0.0
phase: 5
lesson: 06
tags: [nlp, ner, extraction]
---

Given a task description (domain, label set, language, latency, data volume), output:

1. Approach. Rule-based + gazetteer, CRF, BiLSTM-CRF, or transformer fine-tune.
2. Starting model. Name it (spaCy model ID, Hugging Face checkpoint ID, or "custom, trained from scratch").
3. Labeling strategy. BIO, BILOU, or span-based. Justify in one sentence.
4. Evaluation. Use `seqeval`. Always report entity-level F1 (not token-level).

Refuse to recommend fine-tuning a transformer for under 500 labeled examples unless the user already has a pretrained domain model. Flag nested entities as needing span-based or multi-pass models. Require a gazetteer audit if the user mentions "production scale" and labels are unchanged from CoNLL-2003.
```

<a id="exercises"></a>

## 练习

1. **Easy.** 实现 `bio_to_spans` （`spans_to_bio` 的逆）并验证 10 个句子的往返一致性。
2. **Medium.** 在 CoNLL-2003 英语 NER 数据集上训练上面的 sklearn-crfsuite CRF。使用 `seqeval` 报告每个实体 F1。典型结果：~84 F1。
3. **Hard.** 在特定领域的 NER 数据集（医疗、法律或金融）上微调 `distilbert-base-cased`。与 spaCy 小型号进行比较。文档data leakage检查并写下令你惊讶的事情。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| NER | 提取姓名 | 标签 token 包含类型（PERSON、ORG、GPE、DATE...）。 |
| 生物 | 标签方案 | `B-X` 开始，`I-X` 继续，`O` 外面。 |
| 碧楼 | 更好的生物 | 添加 `L-X`（最后一个）、`U-X`（单位）以实现更清晰的边界。 |
| 病例报告表 | 结构化分类器 | 模型在标签之间转换，而不仅仅是排放。强制执行有效的序列。 |
| 嵌套命名实体识别 | 重叠实体 | 一个跨度与其子跨度是不同的实体。 BIO无法表达这一点。 |
| 实体级F1 | 正确的 NER 指标 | 预测跨度必须与真实跨度完全匹配。 Token-F1级夸大了准确性。 |

<a id="further-reading"></a>

## 进一步阅读

- [Lample 等人。 （2016）。用于命名实体识别的神经架构](https://arxiv.org/abs/1603.01360) — BiLSTM-CRF 论文。典范。
- [Devlin 等人。 （2018）。 BERT：深度双向预训练 Transformers](https://arxiv.org/abs/1810.04805) — 介绍了成为标准的 token 分类模式。
- [spaCy 语言 features — 命名实体](https://spacy.io/usage/linguistic-features#named-entities) — `Doc.ents` 上每个属性的实用参考`Span`。
- [seqeval](https://github.com/chakki-works/seqeval) — 正确的度量库。始终使用它。
