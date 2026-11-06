<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="visual-autoregressive-modeling-var-next-scale-prediction"></a>

# 视觉 Autoregressive 建模（VAR）：下一尺度预测

> Diffusion models 及时迭代采样（去噪步骤）。 VAR 按比例迭代采样 - 它预测 1x1 token，然后是 2x2，然后是 4x4，直到最终分辨率，每个比例都以前一个比例为条件。 2024 年的论文表明，VAR 与 GPT 式的图像生成缩放法则相匹配，并在相同的计算预算下击败了 DiT。本课构建核心机制。

**类型：** 构建
**语言：** Python（与PyTorch）
**先决条件：** 第 7 阶段第 03 课（多头 Attention）、第 8 阶段第 06 课（DDPM）
**时间：** ~90 分钟

<a id="the-problem"></a>

## 问题

Autoregressive 一代主导了语言建模，因为它的扩展可预测：更多的计算，更多的 parameters，更低的 perplexity，更好的输出。图像生成在 2024 年之前有两次主要的 AR 尝试：PixelRNN/PixelCNN（逐像素）和 DALL-E 1 / Parti / MuseGAN（VQ-VAE 代码上的 token-by-token）。

两者都面临着代序问题。像素和 tokens 以 2D 网格排列，但 AR 模型必须以 1D 光栅顺序访问它们。早期的角像素不知道图像最终会变成什么。生成质量比 GPT-on-text 更差，并且在匹配计算时从未达到扩散模型质量。

VAR 通过改变正在生成的内容来解决生成顺序问题。 VAR 不是在空间中一张一张地预测 image tokens，而是以不断增加的分辨率来预测整个图像。步骤1：预测一个1x1的token（整体图像“摘要”）。步骤2：预测tokens的2x2网格（更粗的features）。第 3 步：预测 4x4 网格。步骤K：预测最终的(H/8)x(W/8)网格。

每个尺度都涉及所有先前的尺度（因果关系按“尺度顺序”）并在其自己的尺度内平行。顺序问题消失了：尺度 k 的整个图像在一次 transformer 过程中生成。

<a id="the-concept"></a>

## 概念

<a id="vq-vae-multi-scale-tokenizer"></a>

### VQ-VAE 多尺度 Tokenizer

VAR需要**多尺度离散tokenizer**。对于图像 x，它会生成一系列分辨率逐渐提高的 token 网格：

```
x -> encoder -> latent f
f -> tokenize at 1x1: token grid z_1 of shape (1, 1)
f -> tokenize at 2x2: token grid z_2 of shape (2, 2)
...
f -> tokenize at (H/p)x(W/p): token grid z_K of shape (H/p, W/p)
```

每个z_k使用相同的码本（典型大小4096-16384）。每个尺度的 tokenization 都不是独立的——它经过训练，以便对每个尺度的残差求和来重建 f：

```
f ≈ upsample(embed(z_1), target_size) + ... + upsample(embed(z_K), target_size)
```

这是 ** 剩余 VQ** 变体。尺度 k 捕获了尺度 1..k-1 错过的内容。 Decoder 取所有尺度 embeddings 的总和并生成图像。

多尺度 VQ tokenizer 训练一次（如 VQGAN），然后冻结。所有生成工作均由顶部的 autoregressive 模型完成。

<a id="next-scale-prediction"></a>

### 下一代预测

生成模型是 transformer，它从所有先前的尺度中看到 tokens 并预测下一个尺度的 tokens。

输入序列结构：
```
[START, z_1 tokens, z_2 tokens, z_3 tokens, ..., z_K tokens]
```

位置 embeddings 对尺度索引和尺度内的空间位置进行编码。 Attention 在尺度顺序上是因果关系：尺度 k 处的 token，位置 (i, j) 可以处理尺度 1..k 处的所有 tokens 以及尺度 k 处的 tokens 本身，无论使用何种尺度内顺序，它们都先出现（VAR 使用固定位置attention，没有尺度内因果关系——尺度内的所有位置都是并行预测的）。

训练损失：在每个尺度 k，在给定所有先验尺度 tokens 的情况下预测 tokens z_k。 Cross-entropy 离散 VQ 码丢失。与 GPT 的结构相同，只是“序列”现在是按比例结构的。

<a id="generation"></a>

### 一代

在inference：
```
generate z_1 = sample from p(z_1)                    # 1 token
generate z_2 = sample from p(z_2 | z_1)              # 4 tokens in parallel
generate z_3 = sample from p(z_3 | z_1, z_2)         # 16 tokens in parallel
...
decode: f = sum of embed-and-upsample scales 1..K
image = VAE_decoder(f)
```

对于 K = 10 尺度，生成为 10 transformer forward passes。每个通道并行生成其整个尺度 - 尺度内没有每个 token 自回归。对于 256x256 图像，这大约是 10 次通过，而 DiT 是 28-50 次。

<a id="why-next-scale-wins-over-next-token"></a>

### 为什么Next-Scale胜过Next-Token

三个结构性胜利：
1. **从粗到细与自然图像统计数据一致。** 人类视觉感知和图像数据集都表现出与尺度相关的规律性：低频结构稳定且可预测；高频细节取决于低频内容。下一个规模的预测利用了这一点。
2. **规模内并行生成。** 与GPT式token AR不同，VAR一步生成规模内的所有tokens。有效生成长度是对数尺度而不是线性的。
3. **无生成顺序偏差。** Tokens 在尺度 k 处查看尺度 k-1 的所有内容；在后期上下文可用之前，不存在强制早期 tokens 到 commit 的“左侧”或“上方”偏差。

<a id="scaling-law"></a>

### 缩放定律

田等人。证明 VAR 在 ImageNet 上遵循 FID 的幂律缩放曲线 - 就像 GPT 对 perplexity 所做的那样。将 parameters 加倍或可靠地计算可将误差减半。这是第一个像语言模型一样清晰地展示这种缩放行为的图像生成模型。结果是 VAR 规模的预测变得可以通过计算来预测，而不是根据每个架构的经验猜测。

<a id="relationship-to-diffusion"></a>

### 与扩散的关系

VAR 和扩散共享相同的数据压缩故事：都将生成问题分解为一系列更简单的子问题。

- 扩散：逐渐添加噪音，学会撤消一步。
- VAR：逐渐添加分辨率，学会预测下一个尺度。

它们是解决问题的不同轴心。两者都产生易于处理的条件分布。根据经验，VAR 在 inference 上更快（更少的传递，在一个范围内全部并行）并且在类条件 ImageNet 上匹配或击败 DiT。文本条件VAR（VARclip、HART）是一个活跃的研究方向。

```figure
gx-var-next-scale
```

<a id="build-it"></a>

## 动手实现

在`code/main.py`中您将：
1. 在合成“图像”数据（2D 高斯环）上构建微型 ** 多尺度 VQ tokenizer**。
2. 训练 **VAR 风格的 transformer** 来下一个尺度预测 tokens。
3. 通过调用transformer 4次（4个尺度）并解码进行采样。
4. 验证按比例排序的训练是否使生成在比例内并行。

这是一个玩具实现。重点是看到尺度结构的 attention 掩模和尺度内并行生成的实际工作情况。

<a id="ship-it"></a>

## 交付成果

本课程产生 `outputs/skill-var-tokenizer-designer.md` — 设计多尺度 tokenizer 的技能：尺度数量、尺度比率、码本大小、残差共享、decoder 架构。

<a id="exercises"></a>

## 练习

1. ** 尺度计数消融。** 用 4、6、8、10 个尺度训练 VAR。测量重建质量与 autoregressive 通过次数的关系。更多尺度 = 更精细的残差 = 更好的质量但更多的通过。

2. **Codebook size.** 使用码本大小 512、4096、16384 训练 tokenizers。较大的码本提供更好的重建，但预测更困难。找到膝盖。

3. **平行范围内检查。** 对于经过训练的 VAR，显式测量 attention 模式。在尺度 k 内，模型是​​否关注跨尺度位置而不关注尺度内位置？验证掩码实施。

4. **VAR 与 DiT 缩放。** 对于相同的 ImageNet 类条件任务，以匹配的参数预算（例如 33M、130M、458M）训练 VAR 和 DiT。绘制 FID 与计算图。 VAR 在每个尺寸上都应该领先于 DiT——以小尺寸再现论文的结果。

5. **文本调节。** 扩展 VAR 以将文本 embedding（CLIP 池化）作为通过 adaLN 的额外调节输入。这是 HART 配方。 FID 比文本对齐的 sampling 提高了多少？

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| VAR | “视觉AutoRegressive” | 通过 VQ token 网格金字塔的下一尺度预测生成图像 |
| 下一个规模的预测 | “先粗略预测，再精细预测” | 该模型以增加的分辨率尺度预测 tokens，并以所有先前的尺度为条件 |
| 多尺度VQ tokenizer | “剩余VQ” | VQ-VAE，产生 K 个 token 分辨率不断增加的网格，其中 decoder 对所有尺度求和 |
| 尺度 k | “金字塔层k” | K 个分辨率级别之一，从 k=1 时的 1x1 到 k=K 时的 (H/p)x(W/p) |
| 规模内并行 | “每级一名前锋” | 尺度 k 上的所有 tokens 均在一次 transformer 传递中进行预测，而不是自回归 |
| 跨尺度因果关系 | “按比例订购 attention” | Token 在尺度 k 处可以处理所有尺度 1..k，但不能处理尺度 k+1..K |
| 残余矢量量化 | “添加剂tokenization” | 每个尺度的tokens编码较低尺度留下的残差； decoder 合计所有刻度 embeddings |
| VAR标定法则 | “图像 GPT 缩放” | FID 在计算中遵循可预测的幂律，例如语言模型的 perplexity |
| 哈特 | “混合VAR+文本” | 文本条件 VAR 变体将 MaskGIT 风格的迭代解码与 VAR 的尺度结构相结合 |
| 刻度位置 embedding | “（比例、行、列）三重” | 位置编码携带尺度索引和尺度内的空间坐标 |

<a id="further-reading"></a>

## 进一步阅读

- [Tian 等人，2024 —“Visual Autoregressive 建模：通过下一尺度预测生成可扩展图像”](https://arxiv.org/abs/2404.02905) — VAR 论文，规范参考
- [Peebles 和 Xie，2022 —“可扩展 Diffusion Models 与 Transformers”](https://arxiv.org/abs/2212.09748) — DiT，扩散比较基线
- [Esser 等人，2021 —“驯服 Transformers 用于高分辨率图像合成”](https://arxiv.org/abs/2012.09841) — VQGAN，tokenizer 系列 VAR 的多尺度tokenizer 延伸
- [van den Oord et al., 2017 — 《神经离散表示学习》](https://arxiv.org/abs/1711.00937) — VQ-VAE，离散图像的基础 tokenization
- [Tang 等人，2024 —“HART：使用混合 Autoregressive Transformer 进行高效视觉生成”](https://arxiv.org/abs/2410.10812) — 文本条件 VAR
