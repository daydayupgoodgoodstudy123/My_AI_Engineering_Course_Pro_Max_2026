<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="transfusion-autoregressive-text--diffusion-image-in-one-transformer"></a>

# Transfusion：在同一个 Transformer 中结合 Autoregressive 文本与扩散图像

> 变色龙和Emu3用离散的赌注 tokens。它们的工作,但 quantization 瓶颈是可见的——图像质量高原在连续空间以下 diffusion models转换(Meta, Zhou等人,2024年8月)则相反地下注:保持图像连续,降低 VQ-VAE 完全,训练一 transformer 中文本不译。 tokens 下一个...token- 预感,图像 patches 获得流程匹配/ 扩散损失。 两个目标都优化相同 weights。 稳定扩散3 (MMDIT) 的建筑结构是一个近亲。 这个课程读了“传输”论文, 建立了一个玩具双损失训练员, 并且 traces 该 attention 蒙面罩,让一个 transformer 做两个工作。

**类型:** Build
**语言:** Python (史迪利,双损失教练 上MNIST级玩具)
**先修要求:** 阶段12 · 11(夏梅伦),第8阶段(AI)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 电线a transformer 中包含两个损失(文本上的 NTP) tokens,在图像上传播 MSE patches在一个骨干。
- 解释为什么双向 attention 横过图像 patches 加上因果 attention 文本上移 tokens 是一个正确的面具选择。
- 将传输方式(连续图像、扩散损失)与变色龙式(分辨图像、NTP)在计算、质量和代码复杂性方面进行比较。
- 命名 MMDiT 的贡献 : modality-specific weights 在每个街区,联合 attention 留水溪边

<a id="the-problem"></a>

## 问题

离散与连续 image tokens 辩论时间比 LLMs连续表述(原始像素, VAE 隐形)保存细节。 tokens (VQ指数) transformer原生的 vocabulary 但却失去了细节 quantization step.

变色龙/ Emu3 变异: 一次损失, 一个建筑, 但图像忠诚上限由 tokenizer 质量.

Diffusion models 连续: 特殊图像质量, 但一个与 LLM复杂的噪音计时器工程, 和没有干净的整合 与文本生成。

传输询问: 我们能否同时使用? 保持图像连续, 仍然训练一个模型, 使用两个损失缝合成一个 gradient step.

<a id="the-concept"></a>

## 概念

<a id="the-two-loss-architecture"></a>

### 双损失结构

单 decoder-仅 transformer 处理包含以下内容的序列:

- Text tokens (分解, 从 BPE vocab).
- Image patches (连续, 16x16 像素块通过线性投射到隐藏的暗暗处) embedding ——与a相同 ViT encoder输入)
- `<image>` 和 `</image>` 标记连续 patches live.

Forward pass 输了一次,每只选两个头 token:

- 文本为 tokens:标准 cross-entropy 写在Vocab上logits head.
- 图像 patches:连续传播损失 patches 预测每颗子弹的噪音 patch.

该 gradient 流动 transformer 两种损失都改善了共有的 weights simultaneously.

<a id="attention-mask-causal-text--bidirectional-image"></a>

### Attention 掩码:因果文字+双向图像

Text tokens 必须是因果—— 你不能让文本 token 注意未来的文字,或教师强迫中断。 patches但他们应该在同一图像块内双向地关注对方。

面具:

```
M[i, j] = 1 if:
  (i is text and j is text and j <= i)   # causal for text
  OR (i is image and j is image and same_image_block(i, j))   # bidirectional within image
  OR (i is text and j is image and j < i_image_end)   # text attends to previous images
  OR (i is image and j is text and j < i_image_start)   # image attends to preceding text
```

培训时作为块形三角面具执行 inference.

<a id="diffusion-loss-inside-the-transformer"></a>

### 内部的传播损失 transformer

扩散损失是标准: 在图像中添加噪音 patch,请模型预测噪音(或清洁) patch转换版本使用流量匹配, 预测从吵到干净的速度场 。

培训期间:
1. 每一张图像 patch x0,抽取一个随机的时间步骤 t。
2. 样本噪音 ,计算 xt = (1-t) * x0 + t 键 * (流量匹配的线性内插)。
3. 该 transformer 预测 v_e. 损 失 = MSE(v)_-x0  -x0
4. 与文本NTP损失同时从相同的顺序后向反向。

在 inference, 代数是:
- Text tokens:标准 autoregressive sampling.
- Image patches: 扩散 sampling 循环(10-30步典型)以前一文本为条件 tokens.

<a id="mmdit-stable-diffusion-3s-variant"></a>

### MMDiT: 稳定扩散 3 的变体

稳定扩散3(Esser等人,2024年3月)发运MMDiT(Multimodal扩散) Transformer建筑是兄弟姐妹

MMDiT 的关键区别 :

- Modality-specific weights 每个区块 transformer 区块有独立的Q、K、V和 MLP weights 文本的缩写 tokens Vs 图像 patches. Attention 是联合(交叉-)modality;其他的都是: modality-specific.
- 校正流程培训。 特定流程匹配变量, 包括已知的 sampling 数学比DDPM简单
- 比例。 MMDiT是SD3(2B和8B参数变体)的主干。

两者都围绕同一个核心想法: transformer 在文本上运行 NTP, 并在连续图像显示中进行扩散 。

<a id="why-this-beats-chameleon-style"></a>

### 为什么这比变色龙风格还棒

连续扩散与离散的NTP在图像生成方面的质量差距是可以测量的。

- 在7B参数上,在FID上比同样的变色龙型模型高出3-5点。
- 否 tokenizer 所需培训——图像 encoder 简单( 隐藏的激光投影, 和 ViT输入层)
- Inference 能够平行图像 patch 与众不同,除去 autoregressive image tokens.

下方:传输是一个双重损失模型,使培训动力变小。 weights 需要调整。 NTP 与扩散之间的调度不匹配可能导致一个头占优势 。

<a id="what-sits-downstream"></a>

### 下游的什么东西

Janus-Pro(12.15)通过将愿景脱钩来完善翻转的理念 encoder 以SigLIP代替1,以VQ取代2,同时分享 transformer 显示( lesson 12. 14) 将扩散转换为离散的传播( 虚构的预测)。 branches 传送后迅速。

2026年生产VLMs, 释放图像 Gemini 3 专业, GPT-5, Claude Opus 4.7的图像生成路径——几乎肯定使用这个家族的一些后代,细节是专有的。

```figure
cfg-guidance-scale
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 制造一个玩具传输 在一个小的MNIST类似的问题:

- 文字标题是描述数字( 0- 9)的短整数序列。
- 图像是四轮驱动字节格。
- 一块一块weight 线性投影 transformer 静坐; 文本NTP损失, 音响 MSE损失 patches.
- 训练圈取代了两个损失 attention 面具是明确的。
- 生成一个文本标题和一个 4x4 图像 forward pass.

该 transformer 是个玩具,两层楼的管道 attention 遮罩制造, inference 循环是真正的文物。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-two-loss-trainer-designer.md`。鉴于新的多式联运培训任务(文字+图像、文字+音频、文字+视频),它设计了两笔损失的时间表(损失) weights,面罩形状,共享 modality- 特定区块)和标志执行风险。

<a id="exercises"></a>

## 练习

1. 传输式模型列车 70%的文本 tokens 和30%的图像 patches。图像扩散损失为~10x文本 NTP 损失的星等。 weights 平衡他们?

2. 执行块形三角掩码序列 : `[T, T, <image>, P, P, P, P, </image>, T]`。每个条目编号0或1。

3. MMDiT 已经 modality- 特定QKV weights. 怎样? parameter 计算管理费是否添加 ? transformer7B参数,值得吗?

4. 生成: 给定文本 prompt,模型运行NTP50 tokens,然后点击 `<image>`,然后在256号上运行扩散 patches 20多步,多少步 forward passes total?

5. 3节 描述经调整的流量和为什么它会以较少的量相融合 inference 步骤大于 DDPM。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 两次损失培训 | “NTP + 扩散” | 单 transformer 优化两个 cross-entropy 文本为 tokens 连续图像上的 MSE patches 相同 gradient step |
| 流量匹配 | 精密的流体 | 预测从噪音到清洁数据的速度场的传播变异;比 DDPM 简单的数学 |
| MMDiT | "摩托式迪特" | 稳定扩散 3 的建筑:联合 attention, modality- 具体多边劳工方案和规范 |
| 块形边框遮罩 | “ Causal 文本+双向图像” | Attention 图像区域中因果化的掩码 |
| 连续图像显示 | "没有VQ" | Image patches 实际值矢量,而非整数代码簿索引 |
| 速度预测 | "v-parameterization" | 网络输出是噪音和数据之间的速度场,而不是噪音本身 |

<a id="further-reading"></a>

## 进一步阅读

- [Zhou等人——输解(arXiv:2408.11039)](https://arxiv.org/abs/2408.11039)
- [Esser等人——稳定扩散3/MMDiT(arXiv:2403.03206)](https://arxiv.org/abs/2403.03206)
- [皮尔斯和谢-迪特(arXiv:2212.09748)](https://arxiv.org/abs/2212.09748)
- [赵等人——Mono Former(arXiv:2409.16280)](https://arxiv.org/abs/2409.16280)
- [Xie等人——Show-o(arXiv:2408.12528)](https://arxiv.org/abs/2408.12528)
