<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="clip-and-contrastive-vision-language-pretraining"></a>

# CLIP 与视觉语言对比 Pretraining

> OpenAI已经证明CLIP(2021年)是一个足以在未来五年内发力的单一想法:对齐图像 encoder 和文本 encoder 在同一矢量空间中,仅使用噪音的网络图像插图配对和对比性丢失。 embedding 空间确实 zero-shot 分类、图像文本检索和插入2026年VLM作为其视觉塔。 softmax 与 sigmoid 以较低的成本缩放过 CLIP。 此课从 InfoNCE 到 sigmoid 双向损失, 并构建训练步骤 Python.

**类型：** 构建
**语言:** Python (stdlib, InfoNCE + 组合键) sigmoid 损失执行额)
**先修要求:** 阶段12 · 01 (ViT patches),第7阶段(Transformers)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 相互信息中产生的信息NCE损失,并采用数字稳定的矢量化版本。
- 解释一下 sigmoid 双向损失(SigLIP)至批次32768+,无全采集间接费用 softmax demands.
- Run zero-shot 通过构建文本模板来进行图像网络分类(`a photo of a {class}`并使用 argmax 过 cosine similarity.
- 命名四个杠杆 CLIP/ SigLIP pretraining 给您: batch size, temperature, prompt 模板,数据质量。

<a id="the-problem"></a>

## 问题

监控了CLIP前的视觉。 收集标签数据集( ImageNet: 1.2M 图像, 1000 类), 培训 a CNN标签很贵,标签上贴有标签上的偏差,标签不会在不作微调的情况下转移到新的任务。

图像描述网有10亿多张免费的标签。一张金色的搜索器图片“我的狗在公园里”带有一个监督信号 — — 文字描述了图像。问题:您能否将它变成有用的培训?

CLIP 的回答是: 把图像描述对做匹配任务。 在一组 N 图像和 N 标题中, 学习将每个图像与自己的标题匹配到 N-1 分散器 。 监管是“ 这两个东西属于一起; 这些 N-1 不属于一起 ” 。 没有类标签。 没有人类标记。 只是一种对比性损失 。

由此导致 embedding 空间比 CLIP 训练的要多。 图像网络 zero-shot 因为它的功能是“猫的照片”嵌入猫的图片,而猫从未被明确标注。这是每2026年产卵一次的赌注。

<a id="the-concept"></a>

## 概念

<a id="the-dual-encoder"></a>

### 双面 encoder

CLIP有两个塔楼:

- Image encoder `f`: ViT 或 RESNet, 输出每张图像的 D- dim 矢量 。
- Text encoder `g`: 小 transformer,输出每个标题的 D- dim 矢量。

两个塔的输出都与单位长度一致 `cos(f(x), g(y)) = f(x)^T g(y)` 因为两者都是单位-规范。

一组 N( 图像、 标题) 配对, 构建相似矩阵 `S` 形状 `(N, N)`:

```
S[i, j] = cos(f(x_i), g(y_j)) / tau
```

where `tau` 是一个学识 temperature (CLIP初始化为0.07;在日志空间中学习)

<a id="infonce-loss"></a>

### 信息与电子损失

CLIP 使用对称 cross-entropy 横线和列之间:

```
loss_i2t = CE(S, labels=identity)     # each image's positive is its own caption
loss_t2i = CE(S^T, labels=identity)   # each caption's positive is its own image
loss = (loss_i2t + loss_t2i) / 2
```

这是InfoNCE。 softmax 中文本的图像强制每个图像比批次中的其他标题都匹配。“负数”是全部其他批次项目。大批次=负数=强度信号。CLIP在批次32k中培训过;比例问题。

<a id="temperature"></a>

### Temperature

`tau` 控制着 softmax。低 Tau   锐分布,硬性负式采矿效应。高音  软,所有样本都起作用。 CLIP 学习日志(1/tou), 剪辑以防止崩溃。 SigLIP 2 修补初始的 tau , 并使用学到的偏差代替 。

<a id="why-sigmoid-scales-better-siglip"></a>

### Why sigmoid 更佳比例( SigLIP)

Softmax 需要同步的全相似矩阵。 在分布式训练中, 您必须全部收集 embedding 在每个复制品,然后做 softmax。这是世界通信规模的四角形。

替换 SigLIP softmax 使用元素顺序 sigmoid:每一对 `(i, j)`损失是二进制的“是否匹配对”的分类?正类标签是对角标签,其他的都是负的。损失是:

```
L = -1/N sum over (i, j) [ y_ij log sigmoid(S[i,j]) + (1-y_ij) log sigmoid(-S[i,j]) ]
```

`y_ij = 1` 如果 `i == j`换句话说,每对损失都是独立的,不需要全部采集。 GPU 计算本地块和总和。 SigLIP 2 比例尺可便宜地分批 32k-512kk, 供CLIP 需要按比例增加通信。

<a id="zero-shot-classification"></a>

### Zero-shot classification

鉴于 N 类名称, 每个类都构建文本模板 :

```
"a photo of a {class}"
```

将每个模板都嵌入文本 encoder。您的形象被图像嵌入 encoder。 cosine similarity 预言课,没有目标课的培训

Prompt 模板很重要。 CLIP的原始纸张每类使用80个模板(平板、艺术、照片、绘画等), embeddings。+3 图像网络点。现代使用通常会选择一两个模板。

<a id="linear-probes-and-finetuning"></a>

### 线性探测器和微调

Zero-shot 是一个基线。一个线性探测器(在冰冻的 CLIP 顶部培养一个线性层) features 目标课) zero-shot 完全调整会击败内部线性探测器,但可能会受伤 zero-shot 三个制度,三者取舍。

<a id="siglip-2-naflex-and-dense-features"></a>

### SIGLIP 2: 密度和密度 features

SigLIP 2 (2025) 补充说:
- NaFlex: 单一模型处理变量方面比率和分辨率。
- 更浓 features 用于分解和深度估计,目标为作为低放射性液体中冻结的脊柱。
- 多语种:在CLIP只使用英语的100+语言培训。
- 1B 参数比例,CLIP在400M时升空

在2026年打开的VLMs中, SigLIP 2 SO400m/14 是默认的视觉塔。 CLIP 仍然是纯图像文本检索的默认值, 即特定 LAION-2B 培训分布与您的查询模式匹配 。

<a id="align-basic-openclip-eva-clip"></a>

### ALIGIN,基础,开放氯(EVA-CLIP)

ALIGIN(谷歌,2021年):与 CLIP 相同的想法, 1. 8B 比例, 90% 的吵闹。 证明数据比例很吵 。 OpenCLIP (LAION) : 在 LAION- 400M / 2B 上公开复制 CLIP, 多比例, 开始打开 checkpoint。 EVA- CLIP: 首创来自蒙面图像模型; VLMs的坚固骨干。 BASIC: Google 的 CLIP+ALIGN 混合体。 全部相同, 不同的数据和调试 。

<a id="the-zero-shot-ceiling"></a>

### 该 zero-shot ceiling

CLIP 类模型上限在76%左右 zero-shot 需要更大的数据( SigLIP 2 获得 80 ) 或改变建筑( 受监督的头, 更多) parameters)基准是饱和;实际值是 embedding 下游VLMs消费的空间。

```figure
multimodal-fusion
```

<a id="use-it"></a>

## 实际应用

`code/main.py` implements:

1. 双倍的玩具 encoder (基于 Hash 的图像) features文本字符 features)这样您就可以看到 InfoNCE 形状,而没有 numpy.
2. 纯净信息损失 Python (通过日志和表达式实现数字稳定性)
3. Sigmoid 以对式损失作为比较。
4. 一个 zero-shot 分类常规: 计算 cosine similarity 对照一套案文 prompts, 预测的难度。

运行它并观察损失曲线。 绝对数字是玩具; 形状匹配一个真正的 CLIP 训练员的输出 。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-clip-zero-shot.md`。如果使用一组图像(通过路径)和目标类列表,它会构建文本 prompts 使用 CLIP 模板, 以声明的 checkpoint (e.g., `openai/clip-vit-large-patch14`),返回上/下/前5级的类似分数预测。 prompt list.

<a id="exercises"></a>

## 练习

1. 手动对4对组合的一对实施InfoNCE。构建 4x4 相似矩阵,运行 softmax,选择对角线,计算 cross-entropy。 Python 使用此手动计算。

2. SigLIP 使用偏差 parameter `b` 以及 temperature: `S'[i,j] = S[i,j]/tau + b`。什么角色 `b` 当批量存在大类不平衡时播放( 许多负数多于每行正数) ? 读SigLIP 3节 (arXiv:2303.15343) 。

3. 构建 zero-shot 猫和狗的分类员,试试看 prompt templates: `a photo of a {class}` 和 `a picture of a {class}`。测量 100 个测试图像的准确性。模板的组合是否比单行?

4. 计算通信费用 softmax 信息与NCE 对比 sigmoid 双对512GPU 以批量32k. 哪种比例为O(N),哪些为O(N)2?

5. 读取 OpenCLIP 缩放法文件(arXiv:2212.07143, Cherti等人) 。 从数字中推断数据缩放结论: 在固定模型大小时,图像网络之间的日志线关系是什么 zero-shot 准确度和训练数据大小?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 信息NCE | “对比损失” | Cross-entropy 在一个批次相似矩阵上,每个项目正数是它的对齐项,负数是其它所有 |
| Sigmoid loss | (SigLIP损失) | 双双曲二进制 cross-entropy; 否 softmax,没有全套收集,在分布式培训中采用廉价的尺度 |
| Temperature | “头” | 缩放比例 logits 之前 softmax/sigmoid; 控制分布的清晰度 |
| Zero-shot | "无纤维分类" | 使用文本 prompts 用于构建类 embeddings 并按 cosine similarity;没有目标课程培训 |
| Prompt template | "一张..." | 围绕类名的文本脚架; 影响 zero-shot 精确度乘以 1-5 点 |
| Dual encoder | "Two-tower" | 一张图像 encoder +一个文本 encoder,共享 D- dimm 空间的产出 |
| 硬负 | "分散注意力" | 与模型必须设法分离的积极性相当的负数 |
| 线性探头 | "冻结+一层" | 仅训练一个被冻结的线性分类器 features; 措施 feature 质量 |
| NaFlex | "新式灵活解决方案" | SigLIP 2 能力, 以任何宽比和分辨率摄入图像, 不调整大小 |
| Temperature scaling | "log-parmetricized Tau" (反比法) | CLIP 参数 `log(1/tau)` so gradients 行为; 防止崩溃到接近零的剪辑 |

<a id="further-reading"></a>

## 进一步阅读

- [Radford等人——从自然语言监督中学习可转移的视觉模型(arXiv:2103.00020)](https://arxiv.org/abs/2103.00020) - CPIP的论文
- [扎伊等人- Sigmoid 语言图像培训前损失(arXiv:2303.15343)](https://arxiv.org/abs/2303.15343) - 希格莱普
- [Tschanen等人——SigLIP 2 (arXiv:2502.14786)](https://arxiv.org/abs/2502.14786) - 多语种+纳夫列克。
- [Jia等人-ALIGN(阿尔西夫:2102.05918)](https://arxiv.org/abs/2102.05918) 以网络数据为尺度
- [Cherti等人——为对比性语言形象学习提供可复制的缩放法(arXiv:2212.07143)](https://arxiv.org/abs/2212.07143) - 开放CLIP法律。
