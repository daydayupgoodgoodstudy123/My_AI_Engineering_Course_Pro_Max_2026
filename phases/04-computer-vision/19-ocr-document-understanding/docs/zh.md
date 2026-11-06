<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="ocr--document-understanding"></a>

# OCR 和文档理解

> OCR 是一个三阶段管道 - 检测文本框、识别字符，然后将其布局。每个现代 OCR 系统都会对这些阶段进行重新排序或合并。

**类型：** 学习 + 使用
**语言：** Python
**先决条件：** 第 4 阶段第 06 课（检测）、第 7 阶段第 02 课 (Self-Attention)
**时间：** ~45分钟

<a id="learning-objectives"></a>

## 学习目标

- Trace 经典 OCR 管道（检测 -> 识别 -> 布局）和现代端到端替代方案（Donut、Qwen-VL-OCR）
- 为序列到序列 OCR 训练实施 CTC（连接主义时间分类）损失
- 使用PaddleOCR或EasyOCR进行生产文档解析，无需培训
- 区分 OCR、布局解析和文档理解 - 并为每个任务选择正确的工具

<a id="the-problem"></a>

## 问题

充满文字的图像无处不在：收据、发票、身份证、扫描书籍、表格、白板、标牌、屏幕截图。从它们中提取结构化数据——不仅仅是字符，而是“这是总量”——是价值最高的应用视觉问题之一。

该领域分为三个技能层：

1. **OCR 正确**：将像素转换为文本。
2. **布局解析**：将OCR输出分组到区域（标题、正文、表格、标题）。
3. **文档理解**：从布局中提取结构化字段（“invoice_total = $42.50”）。

每一层都有经典和现代的方法，“我想要图像中的文本”和“我需要这张收据的总金额”之间的差距比大多数团队意识到的要大。

<a id="the-concept"></a>

## 概念

<a id="the-classical-pipeline"></a>

### 经典管道

```mermaid
flowchart LR
    IMG["Image"] --> DET["Text detection<br/>(DB, EAST, CRAFT)"]
    DET --> BOX["Word/line<br/>bounding boxes"]
    BOX --> CROP["Crop each region"]
    CROP --> REC["Recognition<br/>(CRNN + CTC)"]
    REC --> TXT["Text strings"]
    TXT --> LAY["Layout<br/>ordering"]
    LAY --> OUT["Reading-order text"]

    style DET fill:#dbeafe,stroke:#2563eb
    style REC fill:#fef3c7,stroke:#d97706
    style OUT fill:#dcfce7,stroke:#16a34a
```

- **文本检测** 生成每行或每字的四边形。
- **Recognition** 将每个区域裁剪到固定高度，运行 CNN + BiLSTM + CTC 来生成字符序列。
- **Layout** 重建阅读顺序（拉丁语从上到下、从左到右；阿拉伯语、日语不同）。

<a id="ctc-in-one-paragraph"></a>

### 一段话中的 CTC

OCR 识别从固定长度生成可变长度序列feature地图。 CTC（Graves et al., 2006）可以让你在没有角色级别的情况下训练它alignment。 模型在每个时间步输出（词汇+空白）上的分布； CTC 损失总体上边缘化alignments合并重复并删除空格后减少到目标文本。

```
raw output: "h h h _ _ e e l l _ l l o _ _"
after merge repeats and remove blanks: "hello"
```

CTC 是 CRNN 在 2015 年发挥作用的原因，并且在 2026 年仍然训练大多数生产 OCR 模型。

<a id="modern-end-to-end-models"></a>

### 现代端到端模型

- **Donut**（Kim 等人，2022） — ViT encoder + 文本 decoder；读取图像并直接发出 JSON 。没有文本检测器，没有布局模块。
- **TrOCR** — ViT + transformer decoder 用于行级 OCR。
- **Qwen-VL-OCR / InternVL** — 针对 OCR 任务进行了完整的 vision-language models 微调； 2026 年复杂文档的最佳准确率。
- **PaddleOCR** — 成熟生产包中的经典 DB + CRNN 管道；仍然是开源的主力。

端到端模型需要更多的数据和计算，但跳过多级管道的误差累积。

<a id="layout-parsing"></a>

### 布局解析

对于结构化文档，运行布局检测器（LayoutLMv3、DocLayNet）来标记每个区域：标题、段落、图形、表格、脚注。然后，读取顺序变为“按布局顺序迭代区域，连接”。

对于表单，请使用 ** 键值提取** 模型（用于视觉效果丰富的文档的 Donut，用于普通扫描的 LayoutLMv3）。他们采用图像+检测到的文本+位置并预测结构化键值对。

<a id="evaluation-metrics"></a>

### Evaluation 指标

- ** 字符错误率 (CER)** — 编辑距离/参考长度。越低越好。生产目标：干净扫描时 < 2%。
- **字错误率 (WER)** — 在字级别相同。
- 结构化字段上的 **F1** — 用于键值任务；测量 `{invoice_total: 42.50}` 是否正确显示。
- ** JSON** 上的编辑距离 — 用于端到端文档解析； Donut 论文引入了标准化树编辑距离。

```figure
cv3-ctc-collapse
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-ctc-loss--greedy-decoder"></a>

### 步骤1：CTC损失+贪婪decoder

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


def ctc_loss(log_probs, targets, input_lengths, target_lengths, blank=0):
    """
    log_probs:      (T, N, C) log-softmax over vocab including blank at index 0
    targets:        (N, S) int targets (no blanks)
    input_lengths:  (N,) per-sample time steps used
    target_lengths: (N,) per-sample target length
    """
    return F.ctc_loss(log_probs, targets, input_lengths, target_lengths,
                      blank=blank, reduction="mean", zero_infinity=True)


def greedy_ctc_decode(log_probs, blank=0):
    """
    log_probs: (T, N, C) log-softmax
    returns: list of index sequences (blanks removed, repeats merged)
    """
    preds = log_probs.argmax(dim=-1).transpose(0, 1).cpu().tolist()
    out = []
    for seq in preds:
        decoded = []
        prev = None
        for idx in seq:
            if idx != prev and idx != blank:
                decoded.append(idx)
            prev = idx
        out.append(decoded)
    return out
```

`F.ctc_loss` 使用高效的 CuDNN 实现（如果可用）。贪婪的 decoder 比波束搜索更简单，并且通常在 1% CER 之内。

<a id="step-2-tiny-crnn-recogniser"></a>

### 第 2 步：微型 CRNN 识别器

用于行 OCR 的最小 CNN + BiLSTM。

```python
class TinyCRNN(nn.Module):
    def __init__(self, vocab_size=40, hidden=128, feat=32):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv2d(1, feat, 3, 1, 1), nn.BatchNorm2d(feat), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(feat, feat * 2, 3, 1, 1), nn.BatchNorm2d(feat * 2), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(feat * 2, feat * 4, 3, 1, 1), nn.BatchNorm2d(feat * 4), nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 1)),
            nn.Conv2d(feat * 4, feat * 4, 3, 1, 1), nn.BatchNorm2d(feat * 4), nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 1)),
        )
        self.rnn = nn.LSTM(feat * 4, hidden, bidirectional=True, batch_first=True)
        self.head = nn.Linear(hidden * 2, vocab_size)

    def forward(self, x):
        # x: (N, 1, H, W)
        f = self.cnn(x)                # (N, C, H', W')
        f = f.mean(dim=2).transpose(1, 2)  # (N, W', C)
        h, _ = self.rnn(f)
        return F.log_softmax(self.head(h).transpose(0, 1), dim=-1)  # (W', N, vocab)
```

固定高度输入（CNN max-pools 高度为 1）。宽度是CTC的时间维度。

<a id="step-3-synthetic-ocr"></a>

### 第 3 步：合成 OCR

生成用于端到端烟雾测试的白底黑字数字字符串。

```python
import numpy as np

def synthetic_line(text, height=32, char_width=16):
    W = char_width * len(text)
    img = np.ones((height, W), dtype=np.float32)
    for i, c in enumerate(text):
        x = i * char_width
        shade = 0.0 if c.isalnum() else 0.5
        img[6:height - 6, x + 2:x + char_width - 2] = shade
    return img


def build_batch(strings, vocab):
    H = 32
    W = 16 * max(len(s) for s in strings)
    imgs = np.ones((len(strings), 1, H, W), dtype=np.float32)
    target_lengths = []
    targets = []
    for i, s in enumerate(strings):
        imgs[i, 0, :, :16 * len(s)] = synthetic_line(s)
        ids = [vocab.index(c) for c in s]
        targets.extend(ids)
        target_lengths.append(len(ids))
    return torch.from_numpy(imgs), torch.tensor(targets), torch.tensor(target_lengths)


vocab = ["_"] + list("0123456789abcdefghijklmnopqrstuvwxyz")
imgs, targets, lengths = build_batch(["hello", "world"], vocab)
print(f"images: {imgs.shape}   targets: {targets.shape}   lengths: {lengths.tolist()}")
```

真实的 OCR 数据集添加字体、噪声、旋转、模糊和颜色。上面的管道是相同的。

<a id="step-4-training-sketch"></a>

### 第四步：训练草图

```python
model = TinyCRNN(vocab_size=len(vocab))
opt = torch.optim.Adam(model.parameters(), lr=1e-3)

for step in range(200):
    strings = ["abc" + str(step % 10)] * 4 + ["xyz" + str((step + 1) % 10)] * 4
    imgs, targets, target_lens = build_batch(strings, vocab)
    log_probs = model(imgs)  # (W', 8, vocab)
    input_lens = torch.full((8,), log_probs.size(0), dtype=torch.long)
    loss = ctc_loss(log_probs, targets, input_lens, target_lens, blank=0)
    opt.zero_grad(); loss.backward(); opt.step()
```

在这个微不足道的合成数据上，经过 200 个步骤，损失应该从 ~3 下降到 ~0.2。

<a id="use-it"></a>

## 实际应用

三种生产路径：

- **PaddleOCR** — 成熟、快速、多语言。一行用法：`paddleocr.PaddleOCR(lang="en").ocr(image_path)`。
- **EasyOCR** — Python-本机、多语言、PyTorch 骨干。
- **Tesseract** — 经典；当模型遇到困难时，对于旧的扫描文档仍然有用。

对于端到端文档解析，请使用 Donut 或 VLM：

```python
from transformers import DonutProcessor, VisionEncoderDecoderModel

processor = DonutProcessor.from_pretrained("naver-clova-ix/donut-base-finetuned-cord-v2")
model = VisionEncoderDecoderModel.from_pretrained("naver-clova-ix/donut-base-finetuned-cord-v2")
```

对于具有可重复结构的收据、发票和表格，请微调 Donut。对于任意文档或具有推理功能的 OCR，当前默认使用 Qwen-VL-OCR 等 VLM。

<a id="ship-it"></a>

## 交付成果

本课产生：

- `outputs/prompt-ocr-stack-picker.md` — 一个 prompt，根据给定的文档类型、语言和结构选择 Tesseract / PaddleOCR / Donut / VLM-OCR。
- `outputs/skill-ctc-decoder.md` — 一种从头开始编写贪婪和束搜索 CTC decoders 的技能，包括长度归一化。

<a id="exercises"></a>

## 练习

1. **(Easy)** 在 5 位随机数字字符串上训练 TinyCRNN 500 个步骤。报告保留集的 CER。
2. **(中)** 用波束搜索替换贪婪解码(beam_width=5)。报告 CER 增量。集束搜索在哪些输入上获胜？
3. **（硬）** 在一组 20 个收据上使用 PaddleOCR，提取行项目，并针对 {item_name, Price} 对的手动标记的基本事实计算 F1。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| 光学字符识别 | “来自像素的文本” | 将图像区域转换为字符序列 |
| CTC | “Alignment无损失” | 训练没有每个时间步标签的序列模型的损失；边缘化超过 alignments |
| 循环神经网络 | 《经典OCR模型》 | 卷积feature提取器+BiLSTM+CTC；生产中仍使用 2015 年基准 |
| 甜甜圈 | “端到端OCR” | ViT encoder + 文字 decoder;直接从图像发出 JSON |
| 布局解析 | “查找区域” | 检测并标记文档中的标题/表格/图形/段落区域 |
| 阅读顺序 | “文本序列” | 将识别的区域排序成句子；对于拉丁语来说很简单，对于混合布局来说很重要 |
| CER/WER | “错误率” | 字符或单词粒度的编辑距离/参考长度 |
| VLM-OCR | “LLM 读取” | vision-language model 经过 OCR 任务的培训或提示；当前复杂文档的 SOTA |

<a id="further-reading"></a>

## 进一步阅读

- [CRNN (Shi et al., 2015)](https://arxiv.org/abs/1507.05717) — 原始 CNN+RNN+CTC 架构
- [CTC (Graves et al., 2006)](https://www.cs.toronto.edu/~graves/icml_2006.pdf) — 原始 CTC 论文；算法思想密密麻麻
- [Donut (Kim et al., 2022)](https://arxiv.org/abs/2111.15664) — 无 OCR 文档理解 transformer
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — 开源生产 OCR 堆栈
