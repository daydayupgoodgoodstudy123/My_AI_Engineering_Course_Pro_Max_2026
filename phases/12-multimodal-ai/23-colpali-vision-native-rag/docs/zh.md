<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="colpali-and-vision-native-document-rag"></a>

# ColPali 与视觉原生文档 RAG

> Traditional RAG 将 PDF 转换成文字, 分割成块, 嵌入块, 存储矢量。 每一步都会丢失信号 : OCR 滴下图表数据, chunking 换行, 文本 embeddings 忽略数字。 ColPali (Faysse等人, 2024年7月) 提出了一个更简单的问题: 为什么要提取文本? 直接通过 PaliGemma 嵌入页面图像, 使用 ColBERT 式的延迟互动来检索, 并保存文档所携带的所有版式、 数字、 字体和格式化信号 。 已公布的基准: 20- 40% 的端到端准确度比文本要好 。RAG 高视文档。 高校 Quen2, 高校 Smol 和 VisRAG 扩展了这个模式。 此课读取了视觉 RAG 论文,并建造一个小 的Pali类索引器。

**类型：** 构建
**语言:** Python (stdlib, 多矢量索引器+ MaxSim 计分器)
**先修要求:** 第11阶段(LLM 工程学 - RAG 基础教育,第12阶段 0.05(LLAVA)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释一下两...encoder 检索(每个文档一个矢量)和后对接检索(每个文档许多矢量)。
- 描述 ColBERT 的 MaxSim 操作, 以及 ColPali 如何从文本中概括它 tokens 图像 patches.
- 建立一个小的ColPali类索引器:第 _______页 patch embeddings 最大Sim 过问号 embeddings 头版
- 比较 ColPali + Quen2.5-VL 生成器与文本RAG + GPT- 4,发票/财务报告使用案例。

<a id="the-problem"></a>

## 问题

Text-RAG 财务报告的Q3收入增长通常在图表中;医疗报告的结果在附加说明的图像中;法律合同的签字块是一个布局事实,而不是文字事实。

文本 -RAG pipeline:

1. PDF / / pdftotext 的文本 。
2. 案文_300-500 token chunks.
3. 块...encoder embedding (一矢量)。
4. 用户查询 ________________________________ embedding → cosine similarity 头部的块。
5. 块 + 查询 + LLM.

五个丢失的步。图表没有被捕获。表格在块间破裂,多列布局平坦,图示说明消失了。

ColPali 的修正: 跳过 OCR, 直接嵌入页面图像。 使用 ColBERT 式的延迟交互功能进行检索, 这样模型可以处理精细刻度 patches 时段。

<a id="the-concept"></a>

## 概念

<a id="colbert-2020"></a>

### 科尔伯特(2020年)

ColBERT (Khattab & Zaharia, arXiv: 2004. 12832) 是文字检索方法。 它不是每个文档中有一个矢量, 而是产生一个矢量 token查询时:

- Query tokens 自己去买 embeddings (N_q 矢量)。
- Document tokens get embeddings (N_d 矢量,通常为缓存)。
- 分数=查询所得总和 tokens 文档最多 tokens 的 cosine similarity: Σ_最大数_j 项( q)_页:1_j).

这是最大Sim 操作。 每个查询 token "挑"它最匹配的文件 token最终得分是总和

Pros: 强烈的回想, 处理任期级语义。 Cons: N_d 每份文件的矢量,储存费用昂贵。

<a id="colpali"></a>

### ColPali

ColPali(Faysse等人,ArXiv:2407.049)将ColBERT模式应用于图像。

- 每页由帕利杰马编码(PaliGemma)。ViT + 语言)改为 patch embeddings数字: N_p 每页矢量。
- 每个用户查询( 文本) 编码为查询 -token embeddings数字: N_q 矢量。
- 分数=_最大数_j 项( q)_i, p , p , i, p i, p i, p i, p i, p i, p i, p i, p i, p i, p i, p i, p_即,MaxSim通过查询文本tokens 和页面图像 -patches.
- 获取头版页面的总分。

在文件接收时间: 将每页都嵌入 PaliGemma, 全部存储 patch embeddings。在查询时间:嵌入查询 tokens,根据全部存储页面计算最大sim embeddings,返回顶级页面。

Pros: 端到端节选文本-RAG 在视觉上丰富的文档中,每张文档的比重为20-40%。 patch- 矢量捕捉到本地布局和内容。

关节: N_p patches × 4 字节浮点 × D- dimm 每页矢量 = 储存量增长快。 被 PQ/ OPQ 缓解 quantization.

<a id="colqwen2-and-colsmol"></a>

### 科尔·昆恩2号和科尔·斯莫尔

Qwen2号上校(Illuin-tech,2024-2025年)将PaliGemma换成Quen2-VL。 encoder更好的检索。

ColSmol 是本地/ 边缘使用的较小比例的变体。 ColSmol 检索器在~ 1B 参数上运行于消费者 GPU.

<a id="visrag"></a>

### VisRAG

VisRAG(Yu等人,ArXiv:2410.10594)是不同的变体:而不是MaxSim patches,将每页都合为一向量,然后用VLM双-encoder 检索。快速索引 + 较小存储,较弱的回调。

质量-成本-成本-权衡:质量-Pali上校,比例-VisRAG。

<a id="m3docrag"></a>

### M3DocRAG

M3DocRAG(Cho等人, arXiv:2411. 04952)将多式检索扩展至多页多文件推理。在文档之间检索页面,为 VLM 构成多页背景。

<a id="vidore--the-benchmark"></a>

### 维多尔基准

ColPali的相伴基准。 视觉文档检索 Evaluation任务包括财务报告、科学论文、行政文件、医疗记录、手册。

校对:SoupRAG 在同一文档中,得分为~50-60%。

<a id="the-end-to-end-rag-pipeline"></a>

### 端到端 RAG pipeline

给一个理想的 RAG:

1. 插图: PDF 页面图像  PaliGemma 编码  全部存储 patch embeddings.
2. 查询:用户文本 __查询-token embeddings 最大Sim 相对于所有索引页 最大K页
3. 生成: 上方- k 页图像+查询  VLM (Quen2.5- VL 或) Claude回答我的问题

任何地方都没有 OCR。 图、图表、字体、布局都流到答案中 。

<a id="storage-math"></a>

### 存储数学

财务报告50页,729份 patches 每页和128-平方厘米 embeddings:

- 帕利上校: 50岁 * 729 * 128 * 4字节 =~ 18 MB 原始, ~ 4 MB 等PQ 后。
- Text-RAG: 50块 * 768-dim * 4字节 =~150 kB。

ColPali 是一个~ 30x 的存储器, 每一个文档。 在比例上, OPQ/ PQ 将它降为~ 5- 10x, 通常可以容忍 。

<a id="when-text-rag-still-wins"></a>

### 当文字...RAG 仍然赢

- 纯文本文档,无布局信号(wiki文章、聊天日志)。RAG 更简单,更安全
- 储存成本居于首位的数百万页档案。
- 严格的监管要求,要求可提取的OCR文本与检索同时进行。

2026年所有其他文件——财务报告、科学论文、法律合同、医疗记录、UX文件——远景-本地 RAG wins.

```figure
mm-maxsim
```

<a id="use-it"></a>

## 实际应用

`code/main.py`:

- Toy patch encoder:绘制“页面” feature 向量矩阵 patch embeddings.
- 最大Sim 计分器: 计算查询之间的 ColBERT 风格评分 token embedding 设置和页面 patch set.
- 索引 5 个玩具页面,运行 3 个查询, 返回有分数的上K 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-vision-rag-designer.md`。如果有一份文件...RAG 选择 ColPali/ ColQwen2 / VisRAG / textRAG 和大小存储。

<a id="exercises"></a>

## 练习

1. 年度报告200页,729页 patches 计算原始存储和 PQ 压缩 (8x) 存储。

2. 最大Sim是_最大数_j 项( q)_i, p , p , i, p i, p i, p i, p i, p i, p i, p i, p i, p i, p i, p i, p_这笔金额中有什么表明一个简单的相似性没有?

3. 卡尔帕利索引页为 patch 设置。如果我们在单词级别上(如 ColBERT ) 索引, 则会有什么变化? 权衡?

4. 设计一个1M页的终端到终端管道,每份查询都有500米的悬浮预算。

5. 读M3DocRAG(arXiv:2411.04952)。 描述多页 attention 和它与单页 ColPali 检索的不同。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 晚间互动 | "ColBERT-style" | 使用每 -token 或每 - 个patch embeddings + 最大Sim,没有单一的 doc 矢量 |
| MaxSim | "Max-over-patches" | 每个查询 token,选择最相似的文档 token; 跨查询的和 |
| Bi-encoder | "Single-vector" | 每个文档有一个矢量; 速度更快但会丢失颗粒 |
| 多向量 | "Many-vectors-per-doc" | 储存 N_p 每份文件/ 页的矢量; 存储成本增加, 但提醒后会改进 |
| Patch embedding | "Page feature" | 每个图像一个矢量 patch 从 VLM 中 encoder,每个页面的缓存 |
| ViDoRe | "视觉医生长椅" | ColPali 用于视觉文档检索的基准套件 |
| PQ quantization | "Product quantization" | 压缩时保持矢量相似,同时缩小存储~8x |

<a id="further-reading"></a>

## 进一步阅读

- [Faysse等人-Pali上校(arXiv:2407.01449)](https://arxiv.org/abs/2407.01449)
- [卡塔布和扎哈里亚-科尔贝特(arXiv:2004.12832)](https://arxiv.org/abs/2004.12832)
- [Yu等人-VisRAG(arXiv:2410.10594)](https://arxiv.org/abs/2410.10594)
- [Cho等人-M3DocRAG(arXiv:2411.04952)](https://arxiv.org/abs/2411.04952)
- [illuin-tech/colpali GitHub](https://github.com/illuin-tech/colpali)
