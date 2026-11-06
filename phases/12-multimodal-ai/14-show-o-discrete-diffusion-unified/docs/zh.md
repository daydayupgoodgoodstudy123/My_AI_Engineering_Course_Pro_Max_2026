<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="show-o-and-discrete-diffusion-unified-models"></a>

# Show-o 与离散扩散统一模型

> 传输混合连续和离散的表达方式。 tokens 使用因果下一个 --token prediction, image tokens 使用面具的分散传播方式 transformer 混合体 attention 将 VQA、文字图像、油漆和混合modality 一代人,一个骨干 tokenizer 每 modality,一种损失配方(下一项-)token 以“显示”为例,“显示”设计是“显示”设计,“显示”的分离扩散是一个平行的、几步式图像生成器,与“传输”和“Emu3”形成对比。

**类型:** 学习
**语言:** Python (尖锐,遮蔽,分解,扩散取样器)
**先修要求:** 阶段12 · 13(过渡)
**时间:** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释隐藏的离散扩散:隐藏的日程 tokens 一样,然后问 transformer 来找回他们
- 比较平行图像解码( show- o, MaskGIT) 到 autoregressive 图像解码( Chameleon, Emu3) 速度和质量 。
- 将三个任务名称 显示- o 手柄放在一个 checkpoint: T2I, VQA, 图像油漆 。
- 选择遮蔽表( 直线、 短程) , 并解释其对样本质量的影响 。

<a id="the-problem"></a>

## 问题

传播的两重损失训练工作,但具有更狡猾的动态——持续传播在与离散NTP损失不同的数值尺度上丧失生命。 weights 是一个 hyperparameter 搜索。 建筑是有效的, 但复杂 。

秀-o 的答案: 保留两个 modalities 离散( 如变色龙) , 但通过掩蔽离散的传播而不是相继生成图像 。 训练目标变成一个单一的蒙蔽 - - 图像 。token- 预言,概括下一个...token- 自然的预感

<a id="the-concept"></a>

## 概念

<a id="masked-discrete-diffusion-maskgit"></a>

### 遮蔽离散扩散(MaskGIT)

原张等人(2022年) MaskGIT 技巧优雅。 从全面图像开始( 每个图像都显示在屏幕上) token 是特别的 `<MASK>` 每一步都预测所有遮蔽 tokens 平行地保持最高K级最自信的预测 并重新标注 rest。在~ 8-16 重复之后,所有 tokens 。 有多少 tokens 调整了接线时间,

培训很简单:对隐蔽率进行统一抽样, [0, 1],应用到图像的 VQ tokens训练 transformer 来找回面具 BERT 用于文字, 缩放成图像生成 。

<a id="show-o-one-transformer-hybrid-mask"></a>

### 显示- o: 1 transformer混合面罩

秀o 将 MaskGIT 放在一个因果语言模型中 transformer. 该 attention 掩码为 :

- Text tokens:因果(标准) LLM).
- Image tokens:图像块内完全双向(因此,遮罩) tokens 能够看见其他 image token ) 预测期间)。
- 文字到图像: 文本包含先前的图像, 图像包含先前的文本 。

培训候补人员,在以下人员之间:
1. 文本序列的标准 NTP 。
2. T2I 样本: 带有遮罩的文本  图像 image tokens蒙面的... . 蒙面的...token- 输了
3. VQA 样本: 图像 + 文本, 带有遮蔽文本 tokens (只是净化)

统一损失是 cross-entropy 在 `<MASK>` tokens,它覆盖了两个文本NTP(仅最后一个 token 和图像蒙面反射(随机子集被遮蔽)。

<a id="parallel-sampling"></a>

### Parallel sampling

显示o 生成图像, 而不是~ 1000 。autoregressive 每 token或~20 (扩散)。每一步都预测所有遮蔽 tokens 平行; commit 最自信的K级,重复。

Compare:
- 变色龙/Emu3 (autoregressive over tokens缩略语: N_tokens forward passes,通常每张图像1024 -4096。
- 传输(连续扩散):~20步,每个完整 transformer pass.
- 显示o( 碎裂的散射):~ 16 步, 每个完整的 transformer pass.

类似规模的模型显示速度比变色龙快, 大致匹配转录步数, 每步费用较低( 分解 vocab) logits 与持续损失相比,“SE”类损失。

<a id="tasks-in-one-checkpoint"></a>

### 任务在一个 checkpoint

显示o 支持四个任务 inference,由 prompt format:

- 文本生成:标准 autoregressive 文本输出。
- VQA: 图像进入, 文本删除 。
- T2I: 文本输入, 通过遮蔽的离散扩散图像出来 。
- 油漆: 图像与部分 tokens 蒙面,填满。

油漆能力是免费的,没有遮蔽性防毒训练。token 网格, 给 rest 加一个文本 prompt,预测面具 tokens.

<a id="masking-schedule"></a>

### 遮蔽计划

有多少个的日程安排 tokens 以解码每个步态形状的质量。

```
mask_ratio(t) = cos(pi * t / (2 * T))   # t = 0..T
```

零步,全部 tokens 隐藏( 鼠标 1. 0 ) 。 在T 步时, 没有隐藏 。 科辛在预测信息最丰富的中程比例上集中质量 。 线性时间表也有效, 但稳定得更快 。

<a id="show-o2"></a>

### Show-o2

显示o2 (2025年后续, arXiv 2506.15564) 比例表 显示o: 大 LLM 基础,更好 tokenizer改进了掩码表 建筑图案一样

<a id="where-show-o-sits"></a>

### 秀 - o 座椅的位置

在2026年分类学中:

- Discrete tokens + NTP:变色龙,Emu3.简单但缓慢 inference.
- Discrete tokens + 蒙面扩散:显示、MaskGIT、LlamaGen、Muse。 sampling,仍然丢失 tokenizer.
- 连续的+扩散:传输、MMDiT、DIT. 质量最高、更复杂的培训。
- 连续 + 流量匹配在 VLM: JanusFlow, InternVL- U. 最新数据 。

按任务选择: 想要在一个开关模型中以合理速度显示 T2I + 油漆+ VQA 时显示; 当质量是至高无上且您能够负担双损管道时传输 。

```figure
masked-diffusion-unmask
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟显示( O) sampling:

- 16 VQ 的玩具网格 tokens.
- 模拟 "transformer" 预测 logits 基于 prompt 和被揭发的, tokens.
- 平行遮罩 sampling 超过8步,有余弦计划
- 打印中间状态( 矩阵模式演变) 和最终 tokens.

跑过去,看着面具一步一步地溶解

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-unified-gen-model-picker.md`。考虑到产品既需要理解(VQA, 字幕)也需要以开放的-weights 限制,在Shod-o家庭、Tranculation/MMDIT家庭与Emu3/变色龙家庭之间作出具体权衡。

<a id="exercises"></a>

## 练习

1. 覆盖离散扩散样本的 ~ 16 级。 为什么不是 1 级? 如果在 0 级解开所有内容, 是什么折断 ?

2. 油漆是免费的, 使用遮蔽的散射。 提议产品使用案例( 真实或假设) , Show-o的油漆比专家模型要强 。

3. 余弦排程与线性排程 : trace 卸载的数 tokens T=8的每步,哪个更平衡?

4. 512x512 显示图像为 1024 tokens。在 vocab K=16384,模型发布于 1024 * 数据对数2( 16384) = 14, 336 位元 (~ 1. 75 KiB) 。 稳定传播输出 512*512*24 比特 = 6,291,456 比特 (~ 768 KiB) 的原始像素。 压缩比是多少? 它买到什么质量 ?

5. 读LlamaGen(arXiv:2406.06525)。 LlamaGen的课堂条件如何? autoregressive 和秀欧的蒙面图不同吗?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 遮蔽的离散扩散 | "MaskGIT-style" | 预测蒙面的培训 tokens; 在 inference,反复地暴露最自信的预测 |
| 余弦计划 | "无名表" | 遮罩比重下降 inference 步骤; 集中中等幅度的自信增长 |
| 平行解码 | "所有 tokens 立刻来 | 每一步都预言着蒙面的全过程 tokens 在一个 forward pass, 然后 commits top-K |
| Hybrid attention | “双向” | 文字上因果遮罩 tokens 图像块内双向 |
| 修复 | "填充的一代" | 与某些人图像的条件 tokens 蒙面,预测缺失的;不需培训 |
| 承诺率 | "每步都跳高" | 有多少个 tokens 被宣布为“完成”; inference 质量权衡 |

<a id="further-reading"></a>

## 进一步阅读

- [Xie等人——Show-o(arXiv:2408.12528)](https://arxiv.org/abs/2408.12528)
- [显示o2(arXiv:2506.15564)](https://arxiv.org/abs/2506.15564)
- [Chang等人-MaskGIT(arXiv:2202.04200)](https://arxiv.org/abs/2202.04200)
- [Sun等人-LlamaGen(阿尔西夫:2406.06525)](https://arxiv.org/abs/2406.06525)
- [Chang等人-Muse(arXiv:2301.00704)](https://arxiv.org/abs/2301.00704)
