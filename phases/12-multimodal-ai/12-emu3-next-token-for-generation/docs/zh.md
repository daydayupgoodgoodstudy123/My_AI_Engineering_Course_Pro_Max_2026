<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="emu3-next-token-prediction-for-image-and-video-generation"></a>

# Emu3：通过下一 Token 预测生成图像与视频

> BAAI的Emu3(Wang等人,2024年9月)是2024年的结果,本应结束扩散-反向:autoregressive 辩论。 Llama-style decoder-仅 transformer仅培训下一个...token- 统一目标 vocabulary + VQ 键 image tokens + 3D VQ 视频 tokens,在图像生成上比 SDXL 差, LLAVA-1.6 差。没有 CLIP 损失。没有扩散计划。 inference 质量,但核心培训目标是下一个 --token 自然界的预言,这篇论文读了Emu3论文——为什么更好 tokenizer 加上比例表,你只需要—— 与扩散方法形成对比。

**类型:** 学习
**语言:** Python (Stdlib, 3D 视频) tokenizer 数学+ autoregressive 取样器骨架)
**先修要求:** 阶段12 · 11(查梅伦)
**时间:** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么Emu3的单项损失接下来...token 尽管长期以来一直认为图像质量需要传播,但客观的工作仍然有效。
- 描述三维视频 tokenizer:什么是时空VQ代码簿 看起来像,为什么 patches 时间间隔 。
- 比较 Emu3 与稳定扩散 XL (训练计算, inference 成本、质量上限)
- 说明Emu3模式所扮演的三个角色:Emu3-Gen(图像gen)、Emu3-Chat(感知)、Emu3-Stage2(视频gen)。

<a id="the-problem"></a>

## 问题

2024年的传统智慧:图像生成需要传播。 image tokens 丢失了太多信息来重建细节, autoregressive sampling 累积错误 tokens。稳定扩散,DALL-E 3,immagen, Midjourney 都使用某种形式的扩散。变色龙(Lesson 12.11) 部分地以小规模推翻了这一说法,但质量上与SDXL不符。

Emu3正面攻击了争论。 tokenizer + 足够比例 + 下一个token = 在同一模型中生成的反射图像,也具有感知功能。

这场赌注在公布时是有争议的。 两年后,开放源码的统一一代家族(Emu3,Show-o,Janus-Pro,Transcultion)是研究的默认路径;生产前沿模型似乎使用某种变体。

<a id="the-concept"></a>

## 概念

<a id="the-emu3-tokenizer"></a>

### 民族三号 tokenizer

关键成分是视觉 tokenizer。Emu3 训练自定义 IBQ 类 tokenizer (瓶子量子,SBER-MoVQGAN家庭)每减8x8分辨率 token。512x512 图像变为 64x64 = 4096 tokens 代码簿大小 32768。

这比变色龙的1024号还要大 tokens 每512x512克,K=8192,但每更便宜 token 关键指标:重建PSNR30.5 dB,与稳定扩散的连续 latent space 3 时,

视频:3D VQ tokenizer 将时空密码编码 patch 4x4x4 像素) 改为一个整数。 8 FPS 的4s 剪辑有32 个框架; 256x256 带4x空间和4x时间减小, token 计数为 (256/4) * (256/4) * (32/4) = 64 * 64 * 8 = 32,768 tokens.

Tokenizer 质量是天花板。Emu3的贡献是部分"我们训练的非常好 tokenizer."

<a id="single-loss-training"></a>

### 单项损失培训

EMU3使用一个目标:下一个token 共同数据预测 vocabulary 横跨文本 tokens, 2D 数字 image tokens视频 tokens. Weights 乘以 modality- 培训期间兼顾贡献的具体因素,但 loss function 完全一样。

火车搭配:
- 图像类型 : `<text caption> <image> image_tokens </image>`
- 图像感知 : `<image> image_tokens </image> <question> text_tokens`
- 视频gen : `<text caption> <video> video_tokens </video>`
- 视频感知:相似。
- 仅文本:标准 NTP 。

模特儿学着什么时候发球 image tokens 文本 tokens 数据分布中生成的生成 image tokens 之后 `<image>` tag.

<a id="classifier-free-guidance-and-temperature"></a>

### 不含分类的指导和 temperature

Autoregressive 图像生成在 inference。Emu3使用它:产生两次,一次带有完整标题,一次带有空白标题,混合 logits 并附有指导 weight 通常为3.0-7.0。这是CFG的相同技术扩散用途,借给 autoregressive setting.

Temperature 物质:太高, 文物; 太低, 模式崩溃。 Emu3 建议 temperature 视觉是1.0,图像生成是0.8。

<a id="three-roles-one-model"></a>

### 三个角色,一个模式

3艘在功能上不同的Emu3舰艇 APIs 只有一个 weight set:

- Emu3- Gen. 图像生成。 输入文本, 输出 image tokens.
- Emu3- Chat. VQA 和字幕。 输入图像 (tokens),输出文本。
- Emu3-Stage2. 视频生成和视频 VQA. 输入文本或视频、输出文本或视频。

没有任务特定的人 只是不一样 prompt 模板。 相同 checkpoint.

<a id="benchmarks"></a>

### Benchmarks

Emu3报(2024年9月):

- 图像生成:在MJHQ-30K FID(5.4对5.6)上比SDXL强,GenEval整体(0.54对0.55——统计领带)和深 Eval的合成相加。
- 图像感知:在VQAv2上击败LLAVA-1.6(75.1对72.4),在MMMU上大致吻合。
- 视频制作:在具有竞争力的FVD和Sora-时代公开基准模型中,4秒的剪辑质量。

数字并不总是赢的——Emu3在这里用一个点来交换一个点——但声称“接下来——”token 预测是你们所需要的" 能够防御 modalities.

<a id="compute-cost"></a>

### 计算费用

3 000亿多式Emu3接受了培训 tokens 7B - 7B - 7B - 7B - 7B - 7Bparameter 模型. GPU- 大约相当于 Llama-2-7B pretraining (2k-4k GPU- 在A100级硅上年。 Diffusion models 类似预算的三列列,但需要单独的文本 encoders 和更复杂的管道。

在 inference, Emu3 慢于每张图像的SDXL: 4096 image tokens 30吨/秒为每512x512图像~2分钟,而SDXL为2-5秒。 Speculative decoding 和 KV- Cache 优化缩小差距, 但不能缩小差距 。 Autoregressive 图像 gen 计算重; 这是常态交换 。

<a id="why-it-matters"></a>

### 为何重要

3号的深刻贡献是概念性的 如果下一个...token 预测比例,以匹配图像生成的传播, 统一模型路径( 丢失一个, 一个主干线, 任何 modality未来模式不需要单独的案文 encoders,单独的传播调度器,单独的 VAEs。 transformer,一个 tokenizer 每 modality,比例尺。

表演,Janus-Pro, InternVL-U 都以这个理论为基础或挑战。 DeepSeek2025年,美国实验室比美国实验室更积极地出版这方面的出版物。

```figure
l5-emu3-next-token
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 制造两个玩具:

- 2D 相对于 3D VQ tokenizer 计数计算器: 给定( 分辨率, 分辨率) patch, 剪辑_长度, FPS),计算 token 图像和视频的计算。
- 一个 autoregressive image-token 具有无分类指导的取样器 temperature.

执行CFG与Emu3的配方相匹配——既有条件又无条件 logits 并附有指导 weight.

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-token-gen-cost-analyzer.md`。根据一代产品规格(图像或视频、目标分辨率、质量等级、延迟预算),计算 token counts, inference 成本,选择Emu3家庭与扩散。

<a id="exercises"></a>

## 练习

1. EMU3生产 4096 tokens 每512x512 图像, 减少 8x8。 计算等值为 1024x1024 和 2048x2048。 发生什么 ? inference latency?

2. 视频上请看Emu3第3.3节 tokenizer。描述三维VQ patch 形状,为什么是 4x4x4 而不是 8x8x1 。

3. 无分类指导 weight 5.0对3.0:什么视觉效果? Trace 数学 `code/main.py`.

4. 计算300B时Emu3-7B培训FLOPs tokens 和稳定扩散相比 哪个更昂贵?

5. Emu3在FID上比SDXL强,但在VQAv2诉专门VLMs中却比不上SDXL。 解释为什么统一损失方法在不同基准上显示不同优势与专家。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| Next-token prediction | "NTP" | Standard autoregressive 损失:预测 token[i+1] given token[0..i]; 为每个 modality 当符号化时 |
| IBQ tokenizer | 倒数量器 | 一类VQ -VAE 与变色龙相比, |
| 3D VQ 3D VQ 3D VQ 3D VQ 3D VQ 3D VQ 3D VQ 3D VQ 3D VQ Q 3D VQ Q 3D VQ Q 3D VQ Q Q 3D VQ Q Q 3D VQ Q | 时空空间量测器 | 编目簿,按(时间、行、科)索引; token 覆盖 4x4x4 像素立方体 |
| 无分类器指导 | “CFG” | 有条件和无条件混合 logits 与 weight 伽马; 在 inference |
| Unified vocabulary | "Shared tokens" | 文本+图像+视频都来自相同的整数空间;模型预测 modality 下一个 |
| MJHQ-30K | "图像基因基准" | 中途旅行质量基准30公里 prompts; Emu3 报告, 这里的 FID |

<a id="further-reading"></a>

## 进一步阅读

- [王等人-Emu3:下一个Token 预测是你们所需要的(arXiv:2409.188669)](https://arxiv.org/abs/2409.18869)
- [Sun等人-Emu: 创造 Pretraining 多式联运(arXiv:2307.0522)](https://arxiv.org/abs/2307.05222)
- [Liu等人-LWM(arXiv:2402.08268)](https://arxiv.org/abs/2402.08268)
- [Yu等人-MAGVIT-V2(arXiv:23 105737)](https://arxiv.org/abs/2310.05737)
- [Tian等人-VAR(arXiv:2404.02905)](https://arxiv.org/abs/2404.02905)
