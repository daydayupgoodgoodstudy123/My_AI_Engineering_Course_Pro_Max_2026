<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="any-resolution-vision-patch-n-pack-and-naflex"></a>

# 任意分辨率视觉：Patch-n'-Pack 与 NaFlex

> 真实图像不是224x224方形。 收据是 9: 16, 图表是 16: 9, 医疗扫描可能是 4096x4096, 移动截图是 9: 19.5 。 2024 年前的 VLM 回答 — 将所有内容调整到固定方形 — 丢弃了使OCR、 文件理解和高分辨率场景解析工作成为 OCR、 文件解析和高分辨率场景解析工作的信号 。 NaVit (Google, 2023) 显示您可以包装变量解析度 。 patches 变成单 transformer 一组带块对角遮罩的。 Quen2- VL的 M-RoPE (2024) 完全丢弃绝对位置表。 LLAVA- NEXT 的 AnyRes 将高分辨率图像拖动成基图像+子图像。 SigLIP 2 的 NaFlex 变体(2025) 现在默认为默认值 encoder 用于打开想要单 checkpoint 以服务于每个侧面比例。此课执行 patch- 包到头了

**类型:** Build
**语言:** Python (stdlib, patch 包装器 + 块对角遮罩)
**先修要求:** 阶段12 · 01 (ViT patches阶段12 -05(LLAVA)
**时间:** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- Pack patches 从一组变量分辨率图像中生成一个序列, 并构建块对角 attention mask.
- 在 AnyRes 平铺( LLAVA- NEXT) 、 NaFlex (SigLIP 2) 和 M- 之间选择RoPE 用于一项特定任务。
- Compute token budgets 用于光学和光学记录仪、图表和摄影,不调整大小。
- 列出平方大小的三种故障模式: 压缩文本、 裁剪内容、 浪费 tokens 被贴在垫子上

<a id="the-problem"></a>

## 问题

Transformers 期待一个序列。 一批是相同长度的序列堆叠。 如果您的图像为 224x224, 您可以得到 196 patch tokens 每一次,不需要铺垫,就完成了。 224号火车,224号电路,再也不会考虑解答问题了。

世界不合作,文件是肖像(8.5x11英寸,2:3-ish),图像截图是景观(16:9),收据高、薄(1:3),医疗成像船在2048x2048或更大处,移动设备截图为1 170x2532 (0.46:1)。

2024年之前的三个选项以及每个选项失败的原因:

1. 缩放大小为固定方形(224x224或336x336)。 缩放扭曲文本和面部。 缩放尺度摧毁图表标签和 OCR 内容。 标准操作直到 LLAVA- 1. 5 。
2. 切成固定的侧面比例。你丢弃了大部分图像,而选择作物位置是它自己的视觉问题。
3. 固定最长的一面。 修补扭曲, 但浪费 50 tokens 图像的粘贴。 attention 花这么多钱 tokens.

2024-2025年的答案: transformer eat patches 并找出如何将一个不同组分 整合成一个序列,而不浪费计算。

<a id="the-concept"></a>

## 概念

<a id="navit-and-patch-n-pack"></a>

### 纳维特和 patch-n'-pack

NaViT(Dehghani等人,2023年)是显示这种工程规模的论文。

1. 计算每组图像的本地值 patch 网格 patch 大小(例如14)
2. 平整每张图像 patches 进入它自己的变长序列
3. 将所有图像集中在一起 patches 成一个长序列 批量。
4. 构建块对角 attention 面具,所以图像A patches 仅访问图像 A 。
5. 背负每 -patch 位置信息(2D) RoPE 或分数位置 embeddings).

336x336(576)的三张图像 tokens256) 区域 tokens和448x336(768) tokens变成1600token 带有 1600x1600 块对角面罩的序列。 没有粘贴。 没有浪费计算 。 transformer 处理任意的侧面比。

NaVit 还引入了分数 patch 培训期间的辍学率——50% patches 随机通过批量——既规范又加快培训。

<a id="anyres-llava-next"></a>

### 任何反应( LLAVA- NEXT)

LLAVA- NEXT 的 AnyRes 是实用的替代方案。 给高分辨率图像和固定图像 encoder 图像平铺:

1. 从预定义的一组(1x1)、(1x2)、(2x1)、(1x3)、(2x1)、(2x2)等中选择格子布局——最符合图像的侧面比。
2. 将整张图像粘贴在网格中;每张瓷砖变成336x336的作物。
3. 还要制作缩略图:整幅图像作为全球通俗文字,已调整为336x336 token.
4. 将冰冻的336瓦 全部编码encoder。 tokens +缩略图 tokens.

672x672 图像, 2x2 网格加缩略图: 4 * 576+576=2880视觉 tokens费用昂贵但有效—— LLM 既能了解当地细节,又能了解全球背景。

任何Res是选择的路径 当你 encoder 被冻结,只支持一个分辨率。它爆炸 token 大图像计数( 4x4 网格上的图像为 9216 + 576 + 9800) tokens,它填充了8K LLM context).

<a id="m-rope-qwen2-vl"></a>

### M-RoPE (Qwen2-VL)

Qwen2-VL 引入多式旋转位置 Embedding。 与 NaVit 的分数位置或 AnyRes 的平板和图布奈尔相比, patch 带有三维位置(时空、高度、宽度)。查询/键旋转处理任意的 H、 W 和时间长度。

M-RoPE 未经再培训的本地动态分辨率。 inference 您正在给任何 HXW 图像提供 patch 嵌入器生成 H/14 x W/14 tokens, 每个 token 获得其(t=0,r=row,c=col)位置, RoPE rotates attention Qwen2.5-VL和 Quen3-VL 继续。 InternVL3 的 V2PE 与变量编码相同, 以每 modality.

不像任何Res,M -RoPE 表示 O( H x W / P% 2) tokens 与 NaVit 不同的是,它仍然期望每个前方有一个图像。 patch- 上面没有包

<a id="naflex-siglip-2"></a>

### 纳夫列克(SIGLIP 2)

纳夫列克思是SigLIP 2 checkpoint本地- 反光模式。 单一模型可提供多个序列长度( 256, 729, 1024) tokens) 在 inference。内部使用 NaVit 型号 patch- 训练期间没有包件, 且绝对分数位置为每 patch。销售点: checkpoint选择 token budget 在 inference 基于任务。

用于语义任务(分类、检索),256 tokens1024) 用于对记录和记录进行理解或图表理解 tokens不准再训练

<a id="the-packing-mask"></a>

### 包装面具

块对角掩码是大多数执行失败的地方。 对于一个包装的长度序列 `N_total` 覆盖图像 `i=0..B-1` 与长度 `n_i`面具 `M` 形状 `(N_total, N_total)` 如果两个指数都跌落到相同的图像块中,则为 1,其他为 0。您可以从累积长度列表中构建它 :

```
offsets = [0, n_0, n_0+n_1, ..., N_total]
M[i, j] = 1 iff there exists b where offsets[b] <= i < offsets[b+1] and offsets[b] <= j < offsets[b+1]
```

这是一条线 PyTorch 与 `torch.block_diag` 或一个明显的集合。 FlashAttention变量长度路径( E)`cu_seqlens`)完全跳过面具,使用累积长度按顺序出席 tensor 直接——~10x比典型批量的密面罩快。

<a id="token-budgets"></a>

### Token budgets

按任务选择策略 :

- OCR/文件: 1024-4096 tokens。SigLIP 2 NaFlex, 1024, 或 AnyRes 3x3 +缩略图。
- 图表和界面:729-1024 tokens 以384-448美元原生。 Qwen2.5- VL 动态分辨率, 最大像素上限 。
- 自然照片:256-576 tokens 下游没问题 LLM 够多了,付钱 tokens 内容密度高的地方。
- 录像:64-128 tokens 空间集成后,每个框架,2-8 FPS。

2026年的生产规则: 取出每个任务的最大像素上限, 以本地端比编码到顶部, 打包批量, 跳过垫。 Qwen2.5- VL 曝光 `min_pixels` 和 `max_pixels` 完全的这个把手。

```figure
mm-patch-n-pack
```

<a id="use-it"></a>

## 实际应用

`code/main.py` implements patch-n'-pack 用于一组具有整数像素坐标的多式图像。 它 :

- 需要一张图像大小( H、 W) 列表 。
- 计算每个图像 patch 序列长度 patch 14号
- 把它们包装成一个总长度的序列 `sum(n_i)`.
- 构建块对角 attention 掩码(清晰度)
- 比较包装成本与平方大小和 AnyRes 平铺。
- 打印a token budget 混合批次(接收、图表、截图、照片)的表格。

运行它。 退出的数字是为什么每2026年打开 VLM 使用 patch-n'-pack.

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-resolution-budget-planner.md`。考虑到混合区域(OCR、图表、照片、视频框架)的工作量,以及总计-token budget,它选择正确的策略(纳夫列克斯,阿内雷斯,M -RoPE,或固定方形)并发布每个请求的配置。在对产品进行 VLM 缩放时使用此技能,它防止了静音 10x token 爆炸会杀死潜伏预算

<a id="exercises"></a>

## 练习

1. 收据为600x1500(1:2.5)。 patch 14号,有多少本地分辨率 tokens有多少次调整为336?

2. 为四张长256、576、729、1024的图像组组装块对角遮罩。 attention 矩阵为 2585 x 2585, 并且精确的 `256^2 + 576^2 + 729^2 + 1024^2` 非零条目。

3. 1792x896 图像 patch 14,比较:(a) 方形大小改为336,然后编码;(b) AnyRes 2x1+缩略图;(c) M-RoPE 使用最少的 tokens哪个保存最详细?

4. 执行分数 patch 下移: 如果给一个包装的序列, 则将50% tokens 随机一致, 并相应更新块对角面罩。 测量面具的宽度变化 。

5. 阅读Quen2-VL纸(arXiv:2409.12191)第3.2节。 `min_pixels` 和 `max_pixels` 控制,为什么两个界限都重要。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Patch-n'-pack | "NAVT型包装" | 相干变量长度 patch 从不同的图像到一个批量维的序列 |
| 块对角掩码 | 写字面罩 | Attention 限制每个图像的遮罩 patches 只能照顾自己,而不是邻居 |
| AnyRes | "LLAVA-NEXT 砖块" | 将高频图像分割成固定大小的瓷砖格,加上一个全局缩略图;用固定的瓷砖编码每个瓷砖 encoder |
| NaFlex | "SigLIP 2 土制软体" | 单线 checkpoint 服务256/729/1024 -token budgets 在 inference 未经再培训 |
| M-RoPE | "Multimodal RoPE" | 处理任意 H、 W、 T 的 3D 旋转位置编码( 时间、 行、 列) |
| cu_seqlens | "FlashAttention packing" | Cumulative-length tensor 该 FlashAttention 使用粗体路径代替密块对角掩码 |
| min_像素/ 最大_pixels | "解析界限" | Quen2.5-VL 请求的每个控制键 token 依靠非常小或非常大的投入 |
| Visual token budget | "有多少个 tokens 每个图像" | 粗略的数 patch tokens 每个图像的释放; 设置 LLM的 prompt 预算和预算 attention 成本 |

<a id="further-reading"></a>

## 进一步阅读

- [德赫加尼等人 - Patch n'包件: NaViT(arXiv:2307.06304)](https://arxiv.org/abs/2307.06304)
- [王等人——Quen2-VL(arXiv:2409.12191)](https://arxiv.org/abs/2409.12191)
- [Laurençon等人——建造房屋时什么重要 vision-language models? (理论2, arXiv: 2405.0246)](https://arxiv.org/abs/2405.02246)
- [Tschanen等人——SigLIP 2 (arXiv:2502.14786)](https://arxiv.org/abs/2502.14786)
- [Qwen 团队-Quen2.5-VL技术报告(arXiv:2502.13923)](https://arxiv.org/abs/2502.13923)
