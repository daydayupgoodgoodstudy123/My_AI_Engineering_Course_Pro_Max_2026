<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="sequence-to-sequence-models"></a>

# 序列到序列模型

> 两个RNNs冒充翻译。他们遇到的瓶颈是 attention 存在的原因。

**类型：** 构建
**语言：** Python
**先决条件：** 第 5 阶段·08（CNNs + RNNs 用于文本），第 3 阶段·11（PyTorch 简介）
**时间：** ~75 分钟

<a id="the-problem"></a>

## 问题

分类将可变长度序列映射到单个标签。翻译将一个可变长度序列映射到另一个可变长度序列。输入和输出采用不同的 vocabularies，可能是不同的语言，不保证长度奇偶性。

seq2seq 架构（Sutskever，Vinyals，Le，2014）用一个故意简单的方法破解了这个问题。两个RNNs。读取源句子并生成固定大小的上下文向量。另一个读取该向量并通过 token 生成目标句子 token。您在第 08 课中编写的代码相同，但以不同的方式粘合在一起。

这值得研究，原因有二。首先，上下文向量瓶颈是 NLP 中在教学上最有用的失败。它激发了 attention 和 transformers 所擅长的一切。其次，训练方法（教师强制、计划 sampling、inference 的波束搜索）仍然适用于包括 LLMs 在内的每个现代系统。

<a id="the-concept"></a>

## 概念

**Encoder.** 读取源语句的 RNN。它的最终隐藏状态是 ** 上下文向量 ** — 整个输入的固定大小的摘要。据推测，除了来源之外什么都不会丢失。

**Decoder.** 另一个从上下文向量初始化的RNN。在每个步骤中，它都将先前生成的 token 作为输入，并生成目标 vocabulary 上的分布。 Sample 或 argmax 选择下一个 token。将其送回。重复直到生成 `<EOS>` token 或达到最大长度。

**Training：** Cross-entropy 每个 decoder 步骤的损失，在序列上求和。通过两个网络随时间变化的标准反向传播。

**Teacher forcing.** 在训练过程中，decoder 在步骤 `t` 的输入是 *ground-truth* token 位于 `t-1` 位置，而不是 decoder 自己之前的预测。这可以稳定训练；如果没有它，早期的错误就会级联，并且模型永远不会学习。在 inference 中，您必须使用模型自己的预测，因此始终存在 train/inference 分布差距。该差距称为 ** 曝光偏差 **。

**瓶颈。** encoder 了解到的有关源的所有内容都必须被压缩到该一个上下文向量中。长句子会失去细节。罕见的单词会变得模糊。重新排序（黑色聊天与黑猫）必须被记住，而不是计算。

Attention（第 10 课）通过让 decoder 查看 *every* encoder 隐藏状态（而不仅仅是最后一个状态）来修复此问题。这就是整个球场。

```figure
lstm-gates
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-an-encoder"></a>

### 步骤一：encoder

```python
import torch
import torch.nn as nn


class Encoder(nn.Module):
    def __init__(self, src_vocab_size, embed_dim, hidden_dim):
        super().__init__()
        self.embed = nn.Embedding(src_vocab_size, embed_dim, padding_idx=0)
        self.gru = nn.GRU(embed_dim, hidden_dim, batch_first=True)

    def forward(self, src):
        e = self.embed(src)
        outputs, hidden = self.gru(e)
        return outputs, hidden
```

`outputs` 的形状为 `[batch, seq_len, hidden_dim]` — 每个输入位置一个隐藏状态。 `hidden` 的形状为 `[1, batch, hidden_dim]` — 最后一步。第 08 课说“汇集输出进行分类”。这里我们保留最后一个隐藏状态作为上下文向量，并忽略每一步的输出。

<a id="step-2-a-decoder"></a>

### 第2步：decoder

```python
class Decoder(nn.Module):
    def __init__(self, tgt_vocab_size, embed_dim, hidden_dim):
        super().__init__()
        self.embed = nn.Embedding(tgt_vocab_size, embed_dim, padding_idx=0)
        self.gru = nn.GRU(embed_dim, hidden_dim, batch_first=True)
        self.fc = nn.Linear(hidden_dim, tgt_vocab_size)

    def forward(self, token, hidden):
        e = self.embed(token)
        out, hidden = self.gru(e, hidden)
        logits = self.fc(out)
        return logits, hidden
```

Decoder 一次调用一步。输入：一批单个tokens和当前隐藏状态。输出：vocabulary logits 用于下一个 token 和更新的隐藏状态。

<a id="step-3-training-loop-with-teacher-forcing"></a>

### 第 3 步：教师强制的训练循环

```python
def train_batch(encoder, decoder, src, tgt, bos_id, optimizer, teacher_forcing_ratio=0.9):
    optimizer.zero_grad()
    _, hidden = encoder(src)
    batch_size, tgt_len = tgt.shape
    input_token = torch.full((batch_size, 1), bos_id, dtype=torch.long)
    loss = 0.0
    loss_fn = nn.CrossEntropyLoss(ignore_index=0)

    for t in range(tgt_len):
        logits, hidden = decoder(input_token, hidden)
        step_loss = loss_fn(logits.squeeze(1), tgt[:, t])
        loss += step_loss
        use_teacher = torch.rand(1).item() < teacher_forcing_ratio
        if use_teacher:
            input_token = tgt[:, t].unsqueeze(1)
        else:
            input_token = logits.argmax(dim=-1)

    loss.backward()
    optimizer.step()
    return loss.item() / tgt_len
```

两个值得命名的旋钮。 `ignore_index=0` 跳过填充 tokens 的损失。 `teacher_forcing_ratio` 是在每一步使用真实 token 与模型预测的概率。从 1.0（完全教师强制）开始，并在训练期间退火至约 0.5，以缩小曝光偏差差距。

<a id="step-4-inference-loop-greedy"></a>

### 步骤4：inference循环（贪心）

```python
@torch.no_grad()
def greedy_decode(encoder, decoder, src, bos_id, eos_id, max_len=50):
    _, hidden = encoder(src)
    batch_size = src.shape[0]
    input_token = torch.full((batch_size, 1), bos_id, dtype=torch.long)
    output_ids = []
    for _ in range(max_len):
        logits, hidden = decoder(input_token, hidden)
        next_token = logits.argmax(dim=-1)
        output_ids.append(next_token)
        input_token = next_token
        if (next_token == eos_id).all():
            break
    return torch.cat(output_ids, dim=1)
```

贪心解码在每一步都会选择概率最高的 token。它可能会偏离：一旦您将 commit 更改为 token，您就无法取消它。 **Beam search** 使顶部的 `k` 部分序列保持活动状态，并在最后选择得分最高的完整序列。光束宽度 3-5 为标准。

<a id="step-5-the-bottleneck-demonstrated"></a>

### 第 5 步：展示瓶颈

在玩具复制任务上训练模型：源 `[a, b, c, d, e]`，目标 `[a, b, c, d, e]`。增加序列长度。观察准确性。

```
seq_len=5   copy accuracy: 98%
seq_len=10  copy accuracy: 91%
seq_len=20  copy accuracy: 62%
seq_len=40  copy accuracy: 23%
```

单个 GRU 隐藏状态无法无损地记住 40-token 输入。每个 encoder 步骤都有该信息，但 decoder 只能看到最后一个状态。 Attention 直接修复了这个问题。

<a id="use-it"></a>

## 实际应用

PyTorch 具有基于 `nn.Transformer` 和 `nn.LSTM` 的 seq2seq 模板。 Hugging Face 的 `transformers` 库提供了在数十亿个 tokens 上训练的完整 encoder-decoder 模型（BART、T5、mBART、NLLB）。

```python
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

tok = AutoTokenizer.from_pretrained("facebook/bart-base")
model = AutoModelForSeq2SeqLM.from_pretrained("facebook/bart-base")

src = tok("Translate this to French: Hello, how are you?", return_tensors="pt")
out = model.generate(**src, max_new_tokens=50, num_beams=4)
print(tok.decode(out[0], skip_special_tokens=True))
```

现代的encoder-decoders掉落RNNs为了transformers。 高级形状（encoder,decoder， 产生-token-经过-token）与 2014 年 seq2seq 论文相同。 每个块内部的机制是不同的。

<a id="when-to-still-reach-for-rnn-based-seq2seq"></a>

### 何时仍需要基于 RNN 的 seq2seq

对于新项目来说几乎从来没有。具体例外情况：

- Streaming 翻译，您一次使用输入一个 token 并使用有限的内存。
- transformer 内存成本过高的设备上文本生成。
- 教育学。了解 encoder-decoder 瓶颈是了解 transformers 获胜原因的最快途径。

<a id="exposure-bias-and-its-mitigations"></a>

### 曝光偏差及其缓解措施

- **Scheduled sampling.** 在训练期间退火教师强迫比，以便模型学会从自身错误中恢复。
- **最小风险训练。** 在句子级BLEU分数上训练而不是token级cross-entropy。更接近你真正想要的。
- **Reinforcement learning fine-tuning.** 用度量奖励序列生成器。用于现代LLM RLHF。

所有这三个仍然适用于基于 transformer 的一代。

<a id="ship-it"></a>

## 交付成果

另存为 `outputs/prompt-seq2seq-design.md`：

```markdown
---
name: seq2seq-design
description: Design a sequence-to-sequence pipeline for a given task.
phase: 5
lesson: 09
---

Given a task (translation, summarization, paraphrase, question rewrite), output:

1. Architecture. Pretrained transformer encoder-decoder (BART, T5, mBART, NLLB) is the default. RNN-based seq2seq only for specific constraints.
2. Starting checkpoint. Name it (`facebook/bart-base`, `google/flan-t5-base`, `facebook/nllb-200-distilled-600M`). Match the checkpoint to task and language coverage.
3. Decoding strategy. Greedy for deterministic output, beam search (width 4-5) for quality, sampling with temperature for diversity. One sentence justification.
4. One failure mode to verify before shipping. Exposure bias manifests as generation drift on longer outputs; sample 20 outputs at the 90th-percentile length and eyeball.

Refuse to recommend training a seq2seq from scratch for under a million parallel examples. Flag any pipeline that uses greedy decoding for user-facing content as fragile (greedy repeats and loops).
```

<a id="exercises"></a>

## 练习

1. **Easy.** 实现玩具复制任务。在目标等于源的输入输出对上训练 GRU seq2seq。测量长度 5、10、20 的精度。重现瓶颈。
2. **Medium.** 添加波束宽度的波束搜索解码 3. 在小型平行语料库上针对贪婪测量 BLEU。记录波束搜索获胜的地方（通常是最后一个 tokens）以及没有区别的地方。
3. **Hard.** 在 10k 对释义数据集上微调 `facebook/bart-base`。将微调模型的 beam-4 输出与保留输入上的基本模型进行比较。报告 BLEU 并选择 10 个定性示例。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|-----------------------|
| Encoder | 输入RNN | 读取源码。生成每步隐藏状态和最终上下文向量。 |
| Decoder | 输出 RNN | 从上下文向量初始化。一次生成一个目标 tokens。 |
| 上下文向量 | 总结 | 最终encoder隐藏状态。固定尺寸。瓶颈attention解决。 |
| 老师强迫 | 使用真tokens | 在训练时输入之前的真实值 token。稳定学习。 |
| 曝光偏差 | 训练/测试差距 | 在真正的 tokens 上训练的模型从未练习过从自己的错误中恢复。 |
| 集束搜索 | 更好的解码 | 在每一步中保持 top-k 部分序列处于活动状态，而不是贪婪地提交。 |

<a id="further-reading"></a>

## 进一步阅读

- [Sutskever，Vinyals，Le (2014)。使用神经网络进行序列到序列学习](https://arxiv.org/abs/1409.3215) — 原始的 seq2seq 论文。四页。
- [Cho 等人。 （2014）。使用 RNN Encoder-Decoder 进行统计机器翻译学习短语表示](https://arxiv.org/abs/1406.1078) — 介绍了 GRU 和encoder-decoder 框架。
- [Bahdanau，Cho，Bengio (2014)。通过联合学习对齐和翻译进行神经机器翻译](https://arxiv.org/abs/1409.0473) — attention 论文。学完本课后立即阅读。
- [PyTorch NLP 从头开始教程](https://pytorch.org/tutorials/intermediate/seq2seq_translation_tutorial.html) — 可构建的 seq2seq + attention 代码。
