<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="chameleon-and-early-fusion-token-only-multimodal-models"></a>

# Chameleon：仅用 Token 的早期融合 Multimodal Models

> 迄今我们所看到的每个VLM都把图像和文字分开。 tokens 由幻觉而来 encoder,然后在 LLM愿景和文本 vocabularies 变色龙(Meta, 2024年5月)问:如果它们这样做了呢?VAE 将图像转换成离散序列 tokens 来源于共享 vocabulary1. 每一份多式联运文件现在都采用一个顺序——文本 tokens 和 image tokens 间断的,单 autoregressive 副作用:模型可以产生混合的modality 产出——交替文本和 image tokens 单 inference 呼叫。这个课读早期集成论 并构建一个玩具版本结束。

**类型:** Build
**语言:** Python (斯德利布,VQ -)VAE tokenizer + 间断 decoder)
**先修要求:** 阶段12 -05,第8阶段(大赦国际)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么共享 vocabulary +单项损失改变模型所能做的。
- 描述一个VQ-VAE 将图像标记为与 transformer下一个...token objective.
- 查梅伦训练技巧的名字: dropout placement, LayerNorm ordering.
- 比较变色龙和BLIP-2的Q-Former方法,描述每个选择的正确时间。

<a id="the-problem"></a>

## 问题

适应器基VLMs(LLAVA, BLIP-2) Qwen-VL) 将文字和图像视为两个不同的东西。 token 穿过 `embed(text_token)`; 图像通过 `visual_encoder(image) → projector → ... pseudo_tokens`。该模型有两个输入路径,可以合并部分。

三个后果:

1. 该 LLM 只能使用图像, 而不是发布。 输出仅是文本 。
2. Mixed-modality 文档(如文章中转录段落和图像)是尴尬的,您要么在模型或链代之外分析多式联运输入。
3. 分布不匹配。 视觉 tokens 和文本 tokens 生活在隐藏空间的不同区域, 创造微妙的 alignment issues.

变色龙拒绝这个前提:图像只是离散的序列 tokens 来源于共享 vocabulary. 培训关于间断文件的模型,一次损失,一次损失 autoregressive decoder你却把混音器打开modality 免费的一代

<a id="the-concept"></a>

## 概念

<a id="vq-vae-as-image-tokenizer"></a>

### VQ-VAE 图像 tokenizer

该 tokenizer 是一个矢量定量的自动编码器。

- Encoder: CNN + ViT 将图像映射为空间 feature 地图, 标注 32x32 features 256号
- 守则: 学到的 vocabulary 中,K矢量(Chameleon使用8192),也低度256。
- Quantization:针对每个空间 feature,以 L2 距离查找最近的代码簿条目。替换连续 feature 与整数索引。
- Decoder: CNN 需要量化 features 回到像素。

Training: VAE 重建损失+承诺损失+代码簿损失。代码簿索引构成图像的离散字母表。

变色龙:一幅图像变成32*32 = 1024 tokens 取自 vocabulary 与文本相交 tokens (来自 LLM的 BPE vocabulary,例如2000年。 vocabulary:40192。 transformer 看见一个序列,一个损失。

<a id="the-shared-vocabulary"></a>

### 共享 vocabulary

Chameleon's vocabulary 合并文本 tokens, image tokens, 和 modality 分隔器,每个 token 只有一个 ID。 embedding 将每个 ID 映射为 D- dimm 隐藏矢量。输出投影映射映射会隐藏在 vocab logits. Softmax 选择下一个 token随便啦 modality.

分隔符物质 : `<image>` 和 `</image>` 标记括号图像 -token 序列。在生成时,如果模型发出 `<image>`,下游软件知道下一个1024 tokens 是要发送到 decoder 用于像素生成。

<a id="mixed-modality-generation"></a>

### Mixed-modality generation

Inference 下一个...token 共享 vocabulary. 示例 prompt写着"拉猫描述它"

```
<image> 4821 1029 2891 ... (1024 image tokens) </image>
The cat is orange, sitting on a windowsill...
```

模型自动选择顺序,它可以生成图像,然后生成文字,然后生成图像,或者插入。 decoder同样的损失

比较生成仅文本的适配器 VLMs。 变色龙重新打开模型输出问题 modalities.

<a id="training-stability--qk-norm-dropout-layernorm-ordering"></a>

### 培训稳定——QK-Norm dropout, LayerNorm ordering

早期融合训练的规模不稳定 变色龙的论文记录了三种技巧:

- QK- Norm. 应用 LayerNorm 键,然后输入 attention,在点值产品之前。防止在深度进行登录量爆炸。被多个2024年后大型模型使用。
- Dropout placement. Dropout 之后,每次剩余加起来, 而不是仅仅在 attention 和劳动和社会福利部。 gradients 来自 image tokens 能够主宰一切
- LayerNorm 下单。 剩余部分的LN前 branch 稳定最终的层 gradient flow.

没有这些技巧,34B分数变色龙训练 以多重方式出现分歧 checkpoints训练方法与建筑一样重要。

<a id="the-tokenizers-reconstruction-ceiling"></a>

### 该 tokenizer重建上限

VQ-VAE 丢失。 在 8192 代码簿条目和 1024 tokens 每张512x512图像,重建PSNR上限约2628 dB。 这足以识别图像的原型,但明显比连续空间扩散差(稳定扩散3达到32+ dB)。

该 tokenizer 是个瓶颈,好多了 tokenizers (MAGVIT-V2, IBQ, SBER-MoVQGAN) 升起天花板。 Emu3(Lesson 12.12) 通过更好的方式实现了SDXL质量的生成。 tokenizer alone.

<a id="chameleon-vs-blip-2--llava"></a>

### 变色龙对BLIP-2/LALVA

变色龙( 变色龙)early fusion, 共享 vocab :
- 一次损失,一次 decoder.
- 混合产生modality 输出.
- Tokenizer 质量上限。
- 贵到家了VAE decoder 每张生成图像 inference path.

BLIP-2/LALVA(意大利)late fusion,分开的塔:
- 幻觉,只发短信
- 重新使用预训练 LLM.
- 否 tokenizer 理解的瓶颈
- 便宜:单 forward pass.

任务选择。 如果您需要图像生成, 色拉龙家族。 如果您只需要理解, 适配器VLM 比较简单, 并且可以重新使用预选的计算 。

<a id="fuyu-and-anygpt"></a>

### 福玉和阿根特

富玉(Adept, 2023)是一个相关的做法:跳过单独的愿景 encoder 完全, 输入原始图像 patches 通过 LLM输入预测 tokens, 否 tokenizer比变色龙简单多了 连共同的蒸汽机产出都损失了

亚马逊热量热电离子(Zhan等人,2024年) modalities:文字、图像、演讲、音乐。相同的 VQ-VAE 每人玩个把戏, 分享 transformer任何一代人,12.16课里都有更多

```figure
vq-codebook
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 建立玩具端到端的早期聚变模式:

- 一个小VQ...VAE- 映射 8x8 的风格量度器 patches 至编码簿索引(K=16)。
- 共享 vocabulary 和(文字编号:0.31)+(图像编号: 32.47)+(分隔符: 48、49)。
- 玩具 autoregressive decoder 合成字幕+图像培训token sequences.
- Sampling 循环,循环文本+ image tokens 给定一个 prompt.

代码故意保留 transformer 微小( 比格) , 这样您就可以 trace 信号流结束

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-tokenizer-vs-adapter-picker.md`。根据产品规格(只理解和理解+生成、所需的图像质量、成本预算),它选择了变色龙家庭(Cameleon-Family)(Checken)early fusion和LALVA-家庭(late fusion并用定量的拇指规则来说明理由。

<a id="exercises"></a>

## 练习

1. 变色龙使用K=8192代码簿条目和1024 tokens 每张512x512图像。 估计压缩比对24位 RGB 图像。 它丢失了吗? 多亏损 ?

2. 同一VQ-VAE 密度产生多少 image tokens变色龙型的模型能产生一个4K图像 inference 是什么先打破的——背景, tokenizer 质量,或 KV cache?

3. 纯度执行 QK- Norm Python。如果有一个64度的查询和密钥,请在点产品前后显示 LayerNorm。为什么量级控制在深度上很重要?

4. 读读关于训练稳定性的变色龙第2.3节。 请描述在34B号没有QK- Norm的纸所观察到的精确故障模式。 “ 北爆” 的符号是什么 ?

5. 延长玩具 decoder 来释放混合的...modality 给定只文本的答复 prompt。测量模型在图像第一与文本第一之间选择频率,然后选择给定的培训数据分布 60%文本第一/40%图像第一。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Early fusion | "Unified tokens" | 图像转换为离散 tokens 共享 transformer的 vocabulary 从第一步 |
| VQ-VAE | "Image tokenizer" | CNN + ViT + 将图像映射为整数索引的编码簿 transformer 能够预测 |
| Shared vocabulary | "一个字典" | 单 token 覆盖文本+图像的 ID 空间 modality separators |
| QK-Norm | "Attention stabilizer" | LayerNorm 用于点产品前的查询和密钥, 防止标准爆炸 |
| Mixed-modality generation | “文本+图像输出” | Inference 自动产生断裂的文本, image tokens 在一个关卡中 |
| 代码簿大小 | "K项" | VQ- 的离散矢量数量VAE 能够量化到; 交易压缩以达到忠诚 |
| Tokenizer ceiling | "重建限度" | 通过解码VQ而实现的最佳 PSNR tokens; 限制模型图像质量 |

<a id="further-reading"></a>

## 进一步阅读

- [变色龙小组-变色龙:混合模式早期风光基金会模型(arXiv:2405.098818)](https://arxiv.org/abs/2405.09818)
- [Aghajanyan等人——CM3(阿尔西夫:2201.07520)](https://arxiv.org/abs/2201.07520)
- [Yu等人-CM3Leon(阿尔西夫:2309.02591)](https://arxiv.org/abs/2309.02591)
- [Zhan等人—— 任何GPT(arXiv:2402.12226)](https://arxiv.org/abs/2402.12226)
- [Adept-Fuyu-8B博客(aidt.ai)](https://www.adept.ai/blog/fuyu-8b)
