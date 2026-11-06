<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="vision-transformers-and-the-patch-token-primitive"></a>

# Vision Transformers 与 Patch-Token 基本单元

> 任何多式联运之前,图像必须成为 tokens 一个 transformer 2020年,我们开始吃 ViT 纸张用 16x16 像素回答此 patches,线性投影,以及位置 embedding五年后,每2026年就有一个边界模式(第1页)。Claude 当地人,2576px的Opus 4.7 Gemini 3.1 Pro, Quen3.5-Omni)仍然从这一角度开始—— encoder 更改自 ViT 到 DINOv2 到 SigLIP 2, 注册 tokens 加上了,职位计划变成2DRoPE,但原始的持有。 patch-token 管道结束,并建造成Stdlib Python 也因为 rest 12阶段有具体的精神模型 tokens."

**类型:** 学习
**语言:** Python (stdlib, patch tokenizer +几何计算器)
**先修要求:** 第7阶段(Transformers阶段4(计算机远景)
**时间:** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- 将 HxWx3 图像转换成 patch tokens 具有正确的位置编码。
- 计算序列长度, parameter 数, 和 FLOPs 的 ViT 给定(patch 大小、分辨率、隐藏暗度、深度)
- 三个升级的 ViT 从2020年研究到2026年生产:自我监督 pretraining (DINO/MAE)登记 tokens,和本地分辨率包装。
- 选择 CLS 集合, 平均集合和注册 tokens 来完成下游任务

<a id="the-problem"></a>

## 问题

Transformers 以矢量序列操作。 文本已经是一个序列( 字节或 tokens图像是三色频道的 2D 像素格,不是序列。如果平整每像素,224x224 RGB 图像将变成150,528 tokens, 和 self-attention 长度为非启动器(以序列长度为方形)。

2020年之前的做法 CNN feature 前面的提取器: ResNet 生成一个 7x7 feature 2048-dim矢量图,喂养这49个 tokens 改为 transformer。这个工作但继承了 CNN偏差(翻译等同性、当地可接受领域) transformer喜欢称号

Dosovitskiy等人(2020年)提出了一个直截了当的问题:如果我们跳过这一条,会怎样? CNN将图像分割成固定大小 patches 线性工程 patch 在矢量中添加位置 embedding,然后将序列输入到香草 transformer。当时,这是异端的——视觉没有变幻。有了足够的数据(JFT-300M,然后是LAION),它就把ResNet打在图像网络上,并不断改进。

到2026年时 ViT 原始的就是无可置疑的基础,每个开放的...weights VLM的视觉塔是一些后代(DINOV2, SigLIP 2, CLIP, EVA, InternVIT)。 问题是,“我们是否应该使用” patches"但"什么 patch 大小,什么分辨率表,什么 pretraining 目标,什么位置编码。"

<a id="the-concept"></a>

## 概念

<a id="patches-as-tokens"></a>

### Patches 作为 tokens

给图像 `x` 形状 `(H, W, 3)` 和一个 patch size `P`,你刻出图像成一个网格 `(H/P) x (W/P)` non-overlapping patches. 每个 patch 是一个 `P x P x 3` 象素立方体。 将每个立方体平整为 `3 P^2` 矢量。应用共享线性投影 `W_E` 形状 `(3 P^2, D)` 绘制每个 patch 进入模型的隐藏维度 `D`.

用于 ViT-B/16 罐头配置:
- 第224号决议, patch 16 + 格 14x14 + 196 patch tokens.
- 每个 patch 是 `16 x 16 x 3 = 768` 像素值, 预测为 `D = 768`.
- 添加可学习的 `[CLS]` token 序列长度197

该 patch 投影与内核大小的 2D 相仿 `P`,前进 `P`, 和 `D` 输出渠道。这就是生产代码是如何实际执行的。 `nn.Conv2d(3, D, kernel_size=P, stride=P)`。“线性投影”框架是概念性的;内核框架是有效的。

<a id="positional-embeddings"></a>

### Positional embeddings

Patches 没有任何固有的秩序—— transformer 把他们当做袋子,早一点 ViTs 添加可学习的 1D 位置 embedding 工作模式与培训解决方案挂钩: inference 如果您更改了网格, 您必须插入位置表 。

现代视网膜骨干使用 2D -RoPE (昆特 -VL的M -) (克恩 -VL's M -)RoPE, SigLIP 2 默认) 或因数化 2D 位置。RoPE 根据 patch的“ 列” 索引,因此模型从旋转角度推断相对 2D 位置。没有位置表格。该模型处理任意的网格大小 inference.

<a id="cls-token-pooled-output-and-register-tokens"></a>

### CLS token、集合产出和登记 tokens

图像层面的表示方式是什么?

1. `[CLS]` token。 patch 序列。毕竟 transformer 区块, CLS token隐藏状态是图像的显示。 继承自 BERT。 ViT,CLIP。 ,CLIP。 ,CLIP。
2. 平均游泳池。 patch tokens输出隐藏状态。 由 SigLIP, DINOV2 使用, 多数现代VLMs 。
3. Register tokensDarcet等人(2023年)观察到 ViTs 训练没有明确的水槽 token 开发高温“艺术行为” patches 劫机案 self-attention添加4-16个可学习登记册 tokens 吸收这种负荷,提高密度的防波质量(部分、深度)。

下游任务的选择很重要。 CLS 分类后可以处理。 对于给人进食的 VLMs 来说, patch tokens 变成一个 LLM完全没有集合起来 patch 变成 LLM 输入 token。在被丢弃之前,登记簿将被丢弃 handoff (他们手脚架,不是内容)

<a id="pretraining-supervised-contrastive-masked-self-distilled"></a>

### Pretraining: 监督、对比、蒙面、自我蒸馏

2020年 目标 ViT 被JFT-300M系统监督分类的预科培训。

- CLIP(2021年):400M双对的对比图像文本。
- MAE (2021年,He等人):遮罩 patches重建像素,自我监督,对纯图像起作用。
- DINO (2021年) / DINOV2(2023年): 与学生教师自行蒸馏,没有标签,没有字幕。 ViT-g/14是最强的纯视觉骨干 默认为"强烈" features" 使用场景.
- SigLIP/SigLIP 2 (2023年,2025年): CLIP 与 a sigmoid 2026年开放VLMs的主要视觉塔(NFLex)Qwen3) 与“LLAVA-One Vision”有关的服务。

你选 pretraining 确定主干线对什么有用: CLIP/ SigLIP 用于文字的语义匹配, DINOV2 用于密视 features,MAE作为下游微调的起点。

<a id="scaling-laws"></a>

### 扩大法律范围

ViT 比例(Zhai等人,2022年)确定 ViT质量符合模型大小、数据大小和计算等可预见法律。
- 更大模型+更多数据 质量更高。
- Patch 大小是序列长度相对于忠诚的杠杆。 Patch 14(典型的DINOV2/SigLIP SO400m) 给更多 tokens 每个图像的 patch 16岁; 更适合操作控制器和密集任务, 更适合速度。
- 分辨率是另一个大杠杆。 从224到384到512几乎总是有帮助,在FLOPs中以二次成本计算。

ViT-g/14(1B项, patch 第14号决议,第224号决议 256 tokens和SigLIP SO400m/14(400米平方厘米, patch 14)是两匹马 encoders 2026年开放VLMs

<a id="parameter-count-for-a-vit"></a>

### Parameter 计数 ViT

全部计算寿命 `code/main.py`. 用于 ViT-B/16, 224: 时间:

```
patch_embed = 3 * 16 * 16 * 768 + 768  =  591k
cls + pos    = 768 + 197 * 768          =  152k
block        = 4 * 768^2 (QKVO) + 2 * 4 * 768^2 (MLP) + 2 * 2*768 (LN)
             = 12 * 768^2 + 3k          =  7.1M
12 blocks    = 85M
final LN    = 1.5k
total       ≈ 86M
```

球场每 ViT 这边走,再装上 checkpoint。主干大小设置了下游VLM的 VRAM 层。

<a id="2026-production-config"></a>

### 2026年生产配置

该 encoder 2026年开放的多数VLMs号船舶是SigLIP 2 SO400m/14, 以本地分辨率( NaFlex) 。 它有:
- 400M parameters.
- Patch 编号14, 默认第384号决议 ______________ 729 patch tokens 每一个图像。
- 图像任务的平均集合;全部729 patches 流进 LLM 用于VQA。
- 4个登记册 tokens,之前丢弃 LLM handoff.
- 2D-RoPE 以图像级别缩放显示本地端比 。

配置中的每一个决定 traces 回到报纸上,你可以读。

```figure
image-patch-tokens
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 是一个 patch tokenizer 和几何计算器。 patch P、隐藏D、深度L)和报告:

- 补丁后网格形状和序列长度 。
- Token 合成8x8 像素玩具图像的序列(通过平坦+工程路径)。
- Parameter 计数 细分为 patch 嵌入,位置嵌入, transformer 块,和头。
- 每日津贴 forward pass 目标分辨率。
- 对比表横贯 ViT-B/16 @ 224, 收到吗? ViT-L/14 @ 336, DINOV2 ViT-g/14@ 224, SigLIP SO400m/14@ 384。

运行它。 parameter 与已发布的数字相匹配。 patch 大小和分辨率以感受 token- 计费

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-patch-geometry-reader.md`。如果有的话 ViT 配置( F)patch 大小、分辨率、隐藏暗度、深度),它产生 token-count, parameter使用此技能选择 VLM 的视线主干线, 它防止 tokens 爆炸了,我的 LLM 环境填充"惊喜。

<a id="exercises"></a>

## 练习

1. 计算 patch-token 本地输入 1280x720 时 Quen2.5-VL 序列长度 patch 大小 14 。 这与 CLS 的表示法相比如何 ?

2. 1080p框架(1920x1080) patch 14 生产数量 tokens30FPS 5分钟视频, 有多少总视觉 tokens哪些成本能拯救你 集合,框架 sampling, 或 token merging?

3. 实施平均集合 patch tokens 纯 Python验证平均资源库的 196 以上 tokens 的 DINOV2 输出匹配模型 `forward` 返回时,您会要求集合 embedding.

4. 读取第3节 "Vision Transformers 需要注册”(arXiv:2309.16588),在两句中说明注册的文物吸收了哪些东西,以及它为什么对下游密集预测很重要。

5. Modify `code/main.py` 支持 patch-n'pack:给定不同分辨率的图像列表, 生成一个单包序列和块对角 attention 面具,在到达12.06课前验证

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Patch | "16x16 像素方形" | 输入图像的固定大小不重叠区域; 变成一个 token |
| Patch embedding | "轻射" | 共享的学习矩阵(或带有步数=P的Conv2d)平坦 patch D- dimm 矢量的像素 |
| CLS token | "Class token" | 预选可学习矢量, 其最终隐藏状态代表整个图像; 2026年可选 |
| Register token | "Sink token" | 可额外学习 tokens 吸收高温的 attention artifacts ViTs 开发期间 pretraining |
| Position embedding | "重要信息" | 位置矢量或旋转,使序列顺序意识;2D-RoPE 是现代默认 |
| Grid | "Patch grid" | 氢(H/P) x(W/P) 2D 数组 patches 和对某一决议的 patch size |
| NaFlex | "新式灵活解决方案" | SIGLIP 2 号 feature:单一模式服务于多面比率和分辨率,不进行再培训 |
| 骨干网 | “视觉编码器（Vision tower）” | 预设图像 encoder whose patch-token 输入输出 LLM 在一个 VLM 中 |
| Pooling | "图像级摘要" | 转弯战略 patch tokens 转换成一个矢量: CLS, 平均值, attention 或基于登记册的 |
| Patch 14对16 | 火炉对粗网格 | Patch 14种产品 tokens 每张图像, 更忠实的OCR, 慢; patch 16 是经典的默认值 |

<a id="further-reading"></a>

## 进一步阅读

- [Dosovitskiy等人——一张图象值16x16字(arXiv:2010.11929)](https://arxiv.org/abs/2010.11929) 原创 ViT.
- [他等人——蒙面自动编码者是可扩展的视觉学习者(arXiv:2111.0637)](https://arxiv.org/abs/2111.06377) - MAE, 自我监督 pretraining.
- [Oquab等人-DINOv2(arXiv:2304.07193)](https://arxiv.org/abs/2304.07193) 自我蒸馏,没有标签
- [Darcet等人 - Vision Transformers 需要登记(arXiv:2309.16588)](https://arxiv.org/abs/2309.16588) - 登记 tokens 和人工制品分析。
- [Tschanen等人——SigLIP 2 (arXiv:2502.14786)](https://arxiv.org/abs/2502.14786) - 2026年的默认视线塔
- [扎伊等人——规模 Vision Transformers (arXiv:2106.04560)](https://arxiv.org/abs/2106.04560) 经验性法律。
