<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="cnns-and-rnns-for-text"></a>

# 文本的 CNNs 和 RNNs

> 卷积学习 n 元语法。复发记得。两者均被 attention 取代。两者在有限的硬件上仍然很重要。

**类型：** 构建
**语言：** Python
**先决条件：** 第 3·11 阶段（PyTorch 简介）、第 5·03 阶段（字 Embeddings）、第 4·02 阶段（从头开始的卷积）
**时间：** ~75分钟

<a id="the-problem"></a>

## 问题

TF-IDF 和 Word2Vec 生成忽略词序的平面向量。基于它们构建的分类器无法区分 `dog bites man` 和 `man bites dog`。词序有时带有信号。

在 transformers 到来之前，两个架构家族填补了这一空白。

** 文本卷积网络 (TextCNN)。** 对单词序列 embeddings 应用一维卷积。宽度为 3 的过滤器是一个可学习的三元组检测器：它跨越三个单词并输出一个分数。堆叠不同宽度（2、3、4、5）以检测多尺度模式。最大池化为固定大小的表示。平坦、平行、快速。

**循环网络（RNN、LSTM、GRU）。** 一次处理一个tokens，维持一种向前传送信息的隐藏状态。顺序、记忆、灵活的输入长度。从2014年到2017年统治了序列建模，然后attention发生了。

本课程将构建两者，然后命名激发 attention 的失败。

<a id="the-concept"></a>

## 概念

**TextCNN**（金，2014）。 Tokens 被嵌入。宽度 `k` 1D 卷积在 embeddings 的连续 `k` 克上滑动过滤器，生成 feature 映射。该地图上的全局最大池选择最强的激活。连接多个过滤器宽度的最大池化输出。送入分类器头。

为什么它有效。过滤器是一个可学习的 n 元语法。最大池化是位置不变的，因此“不好”会在审查开始或中间触发相同的 feature。三个滤波器宽度，每个滤波器有 100 个滤波器，可为您提供 300 个学习的 n 元检测器。训练是并行的；没有顺序依赖性。

**RNN.** 在每个时间步`t`，隐藏状态`h_t = f(W * x_t + U * h_{t-1} + b)`。跨时间分享`W`、`U`、`b`。 `T` 时刻的隐藏状态是整个前缀的摘要。对于分类，汇集 `h_1 ... h_T`（最大值、平均值或最后一个）。

普通RNNs遭受消失gradients。 **LSTM** 添加了决定忘记什么、存储什么以及输出什么的门，从而通过长序列稳定 gradients。 **GRU** 将 LSTM 简化为两个门；使用更少的 parameters 执行类似的操作。

**双向 RNNs** 向前运行一个 RNN 并向后运行另一个，连接隐藏状态。每个 token 的表示都可以看到左右上下文。对于标记任务至关重要。

```figure
rnn-unroll
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-textcnn-in-pytorch"></a>

### 步骤1：PyTorch中的TextCNN

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class TextCNN(nn.Module):
    def __init__(self, vocab_size, embed_dim, n_classes, filter_widths=(2, 3, 4), n_filters=64, dropout=0.3):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.convs = nn.ModuleList([
            nn.Conv1d(embed_dim, n_filters, kernel_size=k)
            for k in filter_widths
        ])
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(n_filters * len(filter_widths), n_classes)

    def forward(self, token_ids):
        x = self.embed(token_ids).transpose(1, 2)
        pooled = []
        for conv in self.convs:
            c = F.relu(conv(x))
            p = F.max_pool1d(c, c.size(2)).squeeze(2)
            pooled.append(p)
        h = torch.cat(pooled, dim=1)
        return self.fc(self.dropout(h))
```

`transpose(1, 2)` 将 `[batch, seq_len, embed_dim]` 重塑为 `[batch, embed_dim, seq_len]`，因为 `nn.Conv1d` 将中轴视为通道。无论输入长度如何，池输出都是固定大小的。

<a id="step-2-lstm-classifier"></a>

### 步骤2：LSTM分类器

```python
class LSTMClassifier(nn.Module):
    def __init__(self, vocab_size, embed_dim, hidden_dim, n_classes, bidirectional=True, dropout=0.3):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.lstm = nn.LSTM(embed_dim, hidden_dim, batch_first=True, bidirectional=bidirectional)
        factor = 2 if bidirectional else 1
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim * factor, n_classes)

    def forward(self, token_ids):
        x = self.embed(token_ids)
        out, _ = self.lstm(x)
        pooled = out.max(dim=1).values
        return self.fc(self.dropout(pooled))
```

序列上的最大池，而不是最后状态池。对于分类，最大池化通常优于采用最后一个隐藏状态，因为长序列末尾的信息往往会主导最后一个状态。

<a id="step-3-the-vanishing-gradient-demo-intuition"></a>

### 第三步：消失的gradient演示（直觉）

没有门控的普通 RNN 无法学习远程依赖关系。考虑一个玩具任务：预测 token `A` 是否出现在序列中的任何位置。如果 `A` 位于位置 1 并且序列长度为 100 tokens，则来自损失的 gradient 必须通过循环 weight 的 99 次乘法回流。如果weight小于1，则gradient消失。如果超过1，就会爆炸。

```python
def vanishing_gradient_sim(seq_len, recurrent_weight=0.9):
    import math
    return math.pow(recurrent_weight, seq_len)


# At weight=0.9 over 100 steps:
#   0.9 ^ 100 ≈ 2.7e-5
# The gradient from step 100 to step 1 is effectively zero.
```

LSTM 通过 ** 单元状态 ** 来修复此问题，该状态仅通过加性交互在网络中运行（忘记门以乘法方式对其进行缩放，但 gradients 仍然沿着“高速公路”流动）。 GRU 使用更少的 parameters 执行类似的操作。两者都可以通过 100 多个步骤序列为您提供稳定的训练。

<a id="step-4-why-this-still-was-not-enough"></a>

### 第 4 步：为什么这还不够

即使使用 LSTM，仍然存在三个问题。

1. **顺序瓶颈。** 在长度为 1000 的序列上训练 RNN 需要 1000 个串行向前/向后步骤。无法跨时间并行。
2. **encoder-decoder 设置中的固定大小上下文向量。** decoder 仅看到 encoder 的最终隐藏状态，压缩在整个输入。长输入会丢失细节。第 09 课直接介绍了这一点。
3. **远程依赖精度上限。** LSTM 的性能优于普通 RNNs，但仍难以在 200 多个步骤中传播特定信息。

Attention 解决了这三个问题。 Transformers 完全放弃了复发。第10课是关键。

<a id="use-it"></a>

## 实际应用

PyTorch 的 `nn.LSTM`、`nn.GRU` 和 `nn.Conv1d` 已做好生产准备。培训代码是标准的。

Hugging Face 附带了您插入的预训练 embeddings 作为输入层：

```python
from transformers import AutoModel

encoder = AutoModel.from_pretrained("bert-base-uncased")
for param in encoder.parameters():
    param.requires_grad = False


class BertCNN(nn.Module):
    def __init__(self, n_classes, filter_widths=(2, 3, 4), n_filters=64):
        super().__init__()
        self.encoder = encoder
        self.convs = nn.ModuleList([nn.Conv1d(768, n_filters, kernel_size=k) for k in filter_widths])
        self.fc = nn.Linear(n_filters * len(filter_widths), n_classes)

    def forward(self, input_ids, attention_mask):
        with torch.no_grad():
            out = self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state
        x = out.transpose(1, 2)
        pooled = [F.max_pool1d(F.relu(conv(x)), kernel_size=conv(x).size(2)).squeeze(2) for conv in self.convs]
        return self.fc(torch.cat(pooled, dim=1))
```

符合约束条件时使用清单。

- **Edge / 设备上 inference.** 带 GloVe 的 TextCNN embeddings 比 transformer 小 10-100 倍。如果您的部署目标是电话，那么这就是堆栈。
- **Streaming / 在线分类。** RNN 一次处理一个 token； transformers 需要完整序列。对于实时输入文本，LSTM 仍然获胜。
- ** 基线的微小模型。** 新任务的快速迭代。在 CPU 上 5 分钟训练 TextCNN。
- **有限数据的序列标记。** BiLSTM-CRF（第06课）仍然是用于1k-10k标记句子的生产级NER架构。

其他一切都归transformer。

<a id="ship-it"></a>

## 交付成果

另存为`outputs/prompt-text-encoder-picker.md`：

```markdown
---
name: text-encoder-picker
description: Pick a text encoder architecture for a given constraint set.
phase: 5
lesson: 08
---

Given constraints (task, data volume, latency budget, deploy target, compute budget), output:

1. Encoder architecture: TextCNN, BiLSTM, BiLSTM-CRF, transformer fine-tune, or "use a pretrained transformer as a frozen encoder + small head".
2. Embedding input: random init, GloVe / fastText frozen, or contextualized transformer embeddings.
3. Training recipe in 5 lines: optimizer, learning rate, batch size, epochs, regularization.
4. One monitoring signal. For RNN/CNN models: attention mechanism absence means they miss long-range deps; check per-length accuracy. For transformers: fine-tuning collapse if LR too high; check train loss.

Refuse to recommend fine-tuning a transformer when data is under ~500 labeled examples without showing that a TextCNN / BiLSTM baseline has plateaued. Flag edge deployment as needing architecture-before-everything.
```

<a id="exercises"></a>

## 练习

1. **Easy.** 在 3 类玩具数据集（您发明数据）上训练 TextCNN。验证滤波器宽度 (2, 3, 4) 的平均 F1 性能优于单一宽度 (3)。
2. **Medium.** 为 LSTM 分类器实现 max-pool、mean-pool 和 Last-state pooling。在小数据集上进行比较；记录哪个池化获胜并假设原因。
3. **Hard.** 构建一个 BiLSTM-CRF NER 标注器（结合第 06 课和这一课）。在 CoNLL-2003 上进行训练。与第 06 课中的单独 CRF 基线和 BERT 微调进行比较。报告训练时间、内存和 F1。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| 文本CNN | CNN 文本 | 具有全局最大池的字 embeddings 上的一维卷积堆栈。金（2014）。 |
| RNN | 经常性网络 | 每个时间步更新的隐藏状态：`h_t = f(W x_t + U h_{t-1})`。 |
| 长短期记忆网络 | 门控 RNN | 添加输入/忘记/输出门+单元状态。通过长序列稳定地训练。 |
| 格鲁乌 | 更简单的 LSTM | 两个门而不是三个。 相似的精度，更少parameters。 |
| 双向 | 两个方向 | 向前 + 向后 RNN 串联。每个 token 都能看到其上下文的两面。 |
| 消失 gradient | 训练信号消失 | 在普通 RNNs 中重复乘以 <1 weights 使得早期步骤 gradients 实际上为零。 |

<a id="further-reading"></a>

## 进一步阅读

- [Kim，Y.（2014）。用于句子分类的卷积神经网络](https://arxiv.org/abs/1408.5882) — TextCNN 论文。八页。可读。
- [Hochreiter, S. 和 Schmidhuber, J. (1997)。长短期记忆](https://www.bioinf.jku.at/publications/older/2604.pdf) — LSTM 论文。没想到清醒了。
- [Olah, C. (2015)。了解 LSTM 网络](https://colah.github.io/posts/2015-08-Understanding-LSTMs/) — 这些图表使每个人都可以使用 LSTM。
