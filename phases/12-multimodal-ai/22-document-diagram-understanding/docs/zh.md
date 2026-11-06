<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="document-and-diagram-understanding"></a>

# 文档与图解理解

> 文件不是照片。 PDF、科学纸、发票或手写表格有布局、表格、图表、脚注、信头和语义结构,而普通图像无法捕捉。 VLM 之前的堆叠是一个管道: 宇宙魔方 OCR + 布局LM3 + 桌面Expractics 。 VLM 波用无OCR模型( Donnut 2022, Nougat (2023), DocLLM (2023) 取代了无OCR 模型, 直接释放结构标记。 到2026年, 边框“ 将页面图像添加到” Claude 原文为Opus 4. 7, 原文为2576px, 结构标记输出是免费的。 这个课读取了文件AI 的三年弧。

**类型:** Build
**语言:** Python (stdlib, 能够显示布局的文档解析器骨架)
**先修要求:** 阶段12 □ 05(LLAVA),阶段5(NLP)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释文件AI的三个时代:OCR管道、无OCR、VLM-Native。
- 描述布局LMv3 的三个输入流: 文本、布局( bbox) 、图像 patches,与统一面具。
- 比较 Donnut (无OCR, 图像标记 + ) 、 Nougat (科学论文 + LaTeX) 、 DocLLM (外观认知基因) 、 PaliGemma 2 ( VLM- 本地) 。
- 为新任务选择一个文件模型(发票、科学论文、手写表格、中国收据)。

<a id="the-problem"></a>

## 问题

"了解PDF"是欺骗性的。

- 文字内容(90%的信号)。
- 版式(页眉、脚注、侧边栏、双列格式)
- 表格(行、列、合并单元格)。
- 图表。
- 手写的注释。
- 字体和打字(标题与体形)。

Raw OCR 丢弃文字并丢失 rest。一个关心发票的系统需要知道“总计:1,245美元”来自右下方,而不是脚注。

<a id="the-concept"></a>

## 概念

<a id="era-1--ocr-pipeline-pre-2021"></a>

### 时间1-OCR输油管(2021年前)

经典堆叠 :

1. PDF 图像/ 页
2. 宇宙魔方(或商业OCR)用每个字的捆绑框抽出文字。
3. 布局分析器识别区块(标题、表格、段落)。
4. 表格结构识别符
5. 域规则 + 正则提取字段。

用于清洁打印文本。 手写、 扭曲扫描、 复杂表格、 非英文脚本上断开。 每个失败模式都需要自定义的例外路径 。

<a id="trocr-2021"></a>

### 跨国民事责任(2021年)

转角控制器(Li等人,ArXiv:2109.10282)取代了宇宙魔方的经典 CNN- 具有 transformer encoder-decoder 以合成的 + 真实文本图像为培训对象。 手写和多语言文本可以打赢。 仍然是一个管道( 探测器然后是 TrOCR , 然后是布局) , 但 OCR 步骤有了显著改善 。

<a id="era-2--ocr-free-2022-2023"></a>

### 时代2-无OCR(2022-2023)

第一批无OCR模型说:完全跳过探测,映像像素映射到 structured output directly.

Donut(Kim等人,ArXiv:2111.15664):
- Encoder-decoder transformer, encoder 斯温 -B
- 输出为 JSON 以便他们能理解。 markdown 或任何特定任务计划
- 没有OCR,没有布局,没有探测

Nougat(Blecher等人,ArXiv:2308.13418):
- 专门培训科学论文。
- 输出为 LaTeX / markdown.
- 处理方程式,多列布局,数字。
- 模型每个ArXiv -parser打电话。

这些都是专家,而不是通才。 科学论文上的甜甜圈失败;发票上的努加特失败。

<a id="layoutlmv3-2022"></a>

### 布局LMv3 (2022)

另一条轨道。布局LMv3 (Huang等人, arXiv: 2204.08387) 保持了 OCR, 但增加了布局理解度 :

- 三个输入流: OCR 文本 tokens, 每-token 2D 边框, 图像 patches.
- 这三个方面都以面具为培训目标 modalities (假发,蒙面) patches),以掩码版式。
- 下游:分类、实体提取、表格质量A。

LMv3 版式是基于 OCR 的文档理解高峰。 表格和发票都强烈。 需要 OCR 上游 。 标准文档基准的 VLM 前最佳精确度 。

<a id="docllm-2023"></a>

### 档案室(2023年)

DOCLLM (Wang 等人, ARXiv: 2401.00908) 是布局LM 的基因比方。 生成以布局为条件的自由形式答案 tokens。文件的质量评估更好;仍然取决于OCR输入。

<a id="era-3--vlm-native-2024"></a>

### 时代3 - VLM-native(2024+)

2024 VLMs 变得足够好, 完全取代管道。 将整页图像高分辨率输入 VLM, 询问问题, 获得答案 。

- LLAVA-NEXT 336-瓦号 AnyRes 用于小型文件。
- Quen2.5-VL 动态分辨率处理 2048+ 像素,本地操作。
- Claude Opus 4.7 支持 2576px 文档。
- 2025年4月,帕利杰马2号火车专门为文件+笔迹提供火车。

VLM-native和OCR-pipline之间的距离迅速缩小。 到2026年,VLM-ntimity赢得了:

- 场景文字(手写+印刷,混合脚本)。
- 包含合并单元格的复杂表格。
- 文本中嵌入的数学方程式 。
- 带有文本说明的数字。

OCR输油管仍然赢:

- 纯扫描工作量,在每页潜伏情况重要的情况下,大规模进行。
- 管道可靠性(确定性故障与VLM) hallucinations).
- 需要可审计的OCR输出的受监管环境。

<a id="the-claude-47--gpt-5-frontier"></a>

### 该 Claude 4.7 / GPT- 5个边界

以2576-像素本地输入,边框VLMs以近人精度记录理解。

- DocVQA: Claude 4.7~95.1,帕利杰马 2~88.4, Nougat~77.3,编织版图LMv3~83。
- ChartQA: Claude 4.7 ~92.2, GPT-4V~78号
- VisualMRC: Claude 4.7 ~94.

封闭式的缺口主要是分辨率和基数LLM 比例。 7B 的开放模型落后了几个点, 但赶上了 。

<a id="math-equations-and-latex-output"></a>

### 数学方程式和 LaTeX 输出

科学论文需要精确的 LaTeX 输出方程式。 诺加特 已经接受了这方面的培训。 受LaTeX 目标( Quen2.5- VL- Math, Nougat 衍生物) 培训的VLMs 生产可用的 LaTeX 。 没有明确的 LaTeX 培训, VLMs 生成可读但不准确的抄录。

2026年的科学纸管道:PDF上的Nougat链, 和棘手的页面上的VLM。

<a id="handwriting"></a>

### Handwriting

仍然是最难完成的子任务。 混合打印的+手写( 医生笔记、 填充表) 仍然可以让 OCR 管道以成本击败 VLMs 。 手写 VLMs 正在改进 ( )Claude 见第4.7段,《帕利杰马2》。

<a id="2026-recipe"></a>

### 2026 食谱

关于一个新的文件-AI项目:

- 标度纯打印的发票:布局LMv3+规则,具有成本效益。
- 混合文档(科学+手写+表):VLM-native(PaliGemma 2或Quen2.5-VL)。
- 完全的ArXiv摄入:数学为Nougat, 数字为VLM。
- 管制:OCR管道+VLM验证器,用于交叉检查。

```figure
mm-doc-layout
```

<a id="use-it"></a>

## 实际应用

`code/main.py`:

- 玩具布局 tokenizer:给定的对(文本, bbox),生成布局LMv3 型输入。
- 甜甜圈式任务图案生成器: JSON 表格模板。
- 比较 token budgets 横跨OCR-管道、Donut、Nougat和VLM-Native的每页。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-document-ai-stack-picker.md`。如果有一个文件-AI项目(域、规模、质量、监管),则在OCR管道、无OCR专家与VLM本地之间进行挑选。

<a id="exercises"></a>

## 练习

1. 您的项目是每天1000万张发票。 哪个堆叠会将每页成本降到最低, 不会失去准确性 ?

2. 为什么布局LMv3在形式 QA 上的表现优于纯 CLIP-VLMs,但在现场文本中表现不佳? bbox 流会放弃什么?

3. Nougat 生成 LaTeX。 提议一个测试案例, 显示 VLM- 本地输出在 LaTeX 忠诚上胜过 Nugat , 以及 Nougat 赢过此案例 。

4. 读读 PaliGemma 2 纸( Google, 2024). 提高文件准确性的关键培训数据是什么呢?

5. 设计一个监管安全混合体:OCR管道为主,VLM为二次交叉检查。您如何解决分歧?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| OCR 输油管 | "Tesseract-style" | 阶段式堆叠: 检测 - > OCR - > 版式 - > 规则; 确定性、 脆弱 |
| OCR-free | "Donut-style" | Image-to-output transformer 跳过明确的 OCR; 单一模式 |
| Layout-aware | "LayoutLM" | 输入包括每 -token bbox 坐标; 横贯统一掩码 modalities |
| VLM-native | 越共VLM(超高频VLM) | 直接向页面图像进纸 Claude/GPT/Qwen 高分辨率甚低频流;无管道 |
| DocVQA | "医生基准" | 文档 VQA 标准; 最高引用分数 |
| 标记输出 | "LaTeX/MD" (LaTeX/MD) , 调制 | Structured output 格式而非自由格式文本; 启用下游自动化 |

<a id="further-reading"></a>

## 进一步阅读

- [Li等人-TrOCR(阿尔西夫:2109.10282)](https://arxiv.org/abs/2109.10282)
- [Blecher等人——Nougat(arXiv:2308.13418)](https://arxiv.org/abs/2308.13418)
- [黄等——布局LMv3(arXiv:2204.08387)](https://arxiv.org/abs/2204.08387)
- [金等人——多努特(arXiv:2111.15664)](https://arxiv.org/abs/2111.15664)
- [王等人-DOCLLM(ARXiv:2401.00908)](https://arxiv.org/abs/2401.00908)
