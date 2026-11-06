<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-04--multimodal-document-qa-vision-first-pdf-tables-charts"></a>

# 综合项目 04：多模态文档问答——以视觉处理 PDF、表格与图表

> 2026年文件-QA边框从OCR-当时的文本移到视觉- 晚间互动。 ColPali, ColQwen2.5 和 ColQwen3- omni 将每个 PDF 页面都当作图像, 嵌入多矢量延迟的交互, 让查询关注 patches 直接在金融10K,科学论文和手写笔记本上,这种模式比OCR第一(OCR)大打折扣。 将管道的终点建在10k页上,并同时发布对OCR-当时文本的反面。

**类型:** Capstone
**语言:** Python (pipeline), TypeScript (查看界面)
**先修要求:** 阶段4(计算机视线),阶段5(NLP),阶段7(transformers阶段11(LLM 工程,第12阶段(多式),第17阶段(基础设施)
**涉及阶段：**P4 · P5 · P7 · P11 · P12 · P17
**时间:** 30小时

<a id="problem"></a>

## 问题

企业在OCR管道中进行PDF:用旋转的表扫描10K, 科学论文密集的方程式, 仅作为图像和手写注释的图表。 将这些作为文字第一, 意味着失去一半的信号。 2026年的答案是原始页面图像上的延迟对接多矢量检索。 科尔帕利( Illuin Tech) 引入了它; 科勒 Qwen2.5- v0. 2 和 科勒 Quen3- omni 推进了准确性。 在 ViDore v3, 视野- 首先是以有意义的边距读取 OCR- the then- text 上方位数, 差距在图表、 表格和笔迹上扩大。

交换是储存和潜伏 embedding ~2048岁 patch 每页矢量, 不是单个的 1024 位矢量。 Raw 存储气球。 DocPruner (2026) 带来50%的运行, 且没有发生可测量的精确损失。 您将输入 10 k 页, 测量 ViDoRe v3 nDCG@ 5 , 并在 2 下提供答案, 并直接与 OCR- 时间文本基准进行比较 。

<a id="concept"></a>

## 概念

较晚的交互表示每个查询 token 得分对每个 patch token,以及每个查询的最大分数 token 。您不需要单个集合矢量就可以得到精细的匹配。多矢量指数(Vespa, Qdrant 多个矢量, 或 ASTRADB) 保存每 - 个矢量 。patch embeddings 并运行 MaxSim 在检索时间。

答者是 vision-language model 将查询加上上方K级检索页面作为图像,并用证据区域( 绑框或页面引用) 写入一个答案。 Quen3- VL- 30B, Gemini 2.5 Pro和InternVL3是2026年的前沿选择,对于方程式和科学标记,OCR的回溯(Nougat, dots.ocr)被作为可选文本频道。

Evaluation 是一个二维矩阵。一个轴:内容类型(文字段落、密集表格、条形/线形图表、手写笔记、方程式)。其他轴:检索方法(视觉- 第一次较晚互动对 OCR- 时文本对混合) 。每个单元格都得到 nDCG@ 5 和回答准确性。报告是可交付的 。

<a id="architecture"></a>

## 建筑

```
PDFs -> page renderer (PyMuPDF, 180 DPI)
           |
           v
  ColQwen2.5-v0.2 embed (multi-vector per page, ~2048 patches)
           |
           +------> DocPruner 50% compression
           |
           v
   multi-vector index (Vespa or Qdrant multi-vector)
           |
query ----+----> retrieve top-k pages (MaxSim)
           |
           v
  VLM answerer: Qwen3-VL-30B | Gemini 2.5 Pro | InternVL3
    inputs: query + top-k page images + optional OCR text
           |
           v
  answer with cited page numbers + evidence regions
           |
           v
  Streamlit / Next.js viewer: highlighted boxes on source page
```

<a id="stack"></a>

## 堆栈

- 页面翻譯: PyMuPDF (fitz) 位于 180 DPI, 肖像化
- 晚间互动模式:Qwen2.5-v0.2上校或Qwen3-omni上校(抱住脸的虚拟小组)
- 索引: 带有多矢量字段的Vespa, 或 Qdrant 多矢量, 或带有 MaxSim 的 AstraDB
- 普鲁宁: DocPruner 2026 政策( 保持高度差异) patches,50%压缩在 < 0.5% 的精确度损失)
- OCR 后退(等式/密集表):点或努加特
- VLM 答: Quen3-VL-30B 自托管或 Gemini 2.5 专业托管;作为后备的实习生
- Evaluation: ViDore v3 基准, M3DocVQA 用于多页推理
- 查看器 UI: 下个.js 15 , 并覆盖证据区域

```figure
ce-late-interaction
```

<a id="build-it"></a>

## 动手实现

1. **Ingest.** 以10千公尺的PDF页面、科学论文和扫描文件进行记录。 `{doc_id, page_num, image_path}`.

2. **Embed.** 运行每页图像的 ColQwen2.5- v0. 2。 输出形状~ 2048 patch embeddings 128. 应用 DocPruner 保持最高信号半分。 写给 Vespa 多矢量字段或 Qdrant 多矢量字段 。

3. **Query.** 每个输入的查询, 嵌入到查询塔( NAME OF TRANSLATORS) (N)token-level embeddings))对索引运行 MaxSim: 对于每个查询 token,将最大点产品移到页面上 patch embeddings,总和。返回顶级页面。

4. **Synthesize.** 与查询和上页5页图像一起拨打 Quen3-VL-30B 。 Prompt: " 仅使用所提供的页数的Answer._编号,页数,并列出区域(图,表格,段落)。”

5. **证据区。** 后处理所引用区域的解答。 如果 VLM 发出捆绑框( Quen3- VL does) , 则将它们作为查看器的覆盖符 。

6. **OCR后退 继续** 对于被确定为方程式密集(图像差异的超常)的页面,运行 Nougat 或点数 ocr , 并将OCR 文本作为图像旁的额外通道传递 。

7. **Eval.** 运行 ViDore v3( 检索 nDCG@ 5) 和 M3DocVQA (多页 QA 精度) 。 并使用相同的合成器在同一体上运行 OCR- 时文本管道 。 生成一个内容类型 × 接近矩阵 。

8. **UI.** Streamlit 原型先; 下15个生产查看器,每页有证据区域重叠。

<a id="use-it"></a>

## 实际应用

```
$ doc-qa ask "what was the 2024 operating margin change for segment EMEA?"
[retrieve]   top-5 pages in 320ms (ColQwen2.5, MaxSim, Vespa)
[synth]      qwen3-vl-30b, 1.4s, cited (form-10k-2024, p. 88) + (..., p. 92)
answer:
  EMEA operating margin moved from 18.2% to 16.8%, a 140bp decline.
  cited: 10-K-2024.pdf p.88 (Table 4, Segment Operating Margin)
         10-K-2024.pdf p.92 (MD&A, Operating Performance)
[viewer]     open with highlighted bounding boxes overlaid on p.88 Table 4
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-doc-qa.md` 说明可交付品:设想-第一种多式联运文件质量评估系统,适应具体内容,并根据ViDoRe v3的OCR-当时文本基线进行评估。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | ViDoRe v3 / M3DocVQA 精度 | 基准数相对于OCR-文字基线和已公布的首版 |
| 20 | Evidence-region grounding | 引用区域中实际包含回答范围的部分 |
| 20 | 储存和潜伏工程 | DocPruner压缩率,指数p95,回答p95 |
| 20 | 多页推理 | 手贴100个问题多页集的准确性 |
| 15 | 源头检查 UX | 查看器清晰度、 重叠忠诚度、 并排比较工具 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 在同一块体上测量 Col Qwen2.5- v0. 2 和 Col Quen3- omni 。 哪个页面正确, 哪一个页面错误? 在索引中添加“ 内容类” 标记, 以便按类型进行路径 。

2. Prune embeddings 积极( 75%, 90%) 。 找到压缩悬崖: ViDoRe nDCG@ 5 跌落到 OCR 基线以下的点 。

3. 建立一个混合体:运行OCR-then-text 和ColQwen平行, 与RRF引信, 重新排序与交叉 -encoder混合体能单独击败吗?

4. 交换小VLM(Qwen2.5-VL-7B)的 Quen3-VL-30B。 测量精度- 美元曲线 。

5. 添加手写笔记支持。 发送笔迹, 嵌入到 ColQwen 中, 测量检索 。 比较笔迹 OCR 管道 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 晚间互动 | "ColPali式的检索" | Query tokens 与页面比对 patches 独立; 最大Sim 集成 |
| 多向量 | "每-patch embedding" | 每份文件都有多个矢量, 没有一个集合矢量 |
| MaxSim | "晚间交流评分" | 每个查询 token,对文档矢量采用最大相似度;总和 |
| DocPruner | "Patch compression" | 2026年的修剪,保持50% patches 准确度损失可忽略不计 |
| 维多尔 v3 | "文件检索基准" | 2026年测量视觉文件检索的标准 |
| 证据区域 | 锁着的盒子 | 源页上的 bbox , 将回答范围本地化 |
| OCR 后退 | "平等频道" | 与公式或表重页的视图同时使用的文本管道 |

<a id="further-reading"></a>

## 进一步阅读

- [卡尔帕利(伊林技术)存储库](https://github.com/illuin-tech/colpali) 参考延迟互动文档检索
- [帕利牌纸(arXiv:2407.01449)](https://arxiv.org/abs/2407.01449) 基本方法文件
- [抱抱脸的ColQuen家族](https://huggingface.co/vidore) 生产准备 checkpoints
- [M3DocRAG(阿多贝)](https://arxiv.org/abs/2411.04952) - 多页多式联运 RAG baseline
- [Vesta 多矢量教学](https://docs.vespa.ai/en/colpali.html) - 参考服务堆栈
- [Qdrant 多矢量支持](https://qdrant.tech/documentation/concepts/vectors/#multivectors) - 替代索引
- [AStraDB 多矢量](https://docs.datastax.com/en/astra-db-serverless/databases/vector-search.html) 备选管理指数
- [诺加特](https://github.com/facebookresearch/nougat) - 具有等式能力的OCR后退
