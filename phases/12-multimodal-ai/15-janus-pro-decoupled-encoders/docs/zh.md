<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="janus-pro-decoupled-encoders-for-unified-multimodal-models"></a>

# Janus-Pro：用于统一 Multimodal Models 的解耦 Encoders

> Unified multimodal models 无法避免的紧张,理解需要语义 features - SigLIP或DINOv2 输出矢量,具有丰富的概念级信息。 tokens 以正像素的形式组成。 encoder. 亚努斯(Janus)DeepSeek和Janus-Pro (2024年10月)DeepSeek2025年1月)认为, encoders共享 transformer 任务之间,但通过 SigLIP 理解路径,通过 VQ 生成 tokenizer。在 7B , Janus-Pro 在 GenEval 上击败了DALL-E 3, 而在 MMMU 上击败了 LLAVA。 这个课解释了为什么有两个 encoders 工作失败。

**类型:** Build
**语言:** Python (斯德利布,双人...encoder 路径+共享体信号)
**先修要求:** 阶段12 · 13(过渡),阶段12 · 14(展示-o)
**时间:** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么只有一条 encoder 损害理解或影响产生质量。
- 描述 Janus-Pro 的路线: SigLIP features 用于理解的输入面, VQ tokens 生成输入和输出。
- Trace 使Janus-Pro成功成功 而在Janus没有成功的地方
- 比较脱钩(Janus-Pro)、连锁(Transmission)和混合分解(show-o)建筑。

<a id="the-problem"></a>

## 问题

统一模型共享a transformer 之前的尝试( Chameleon, show-o, Transmission) 都使用一个视觉 tokenizer 双向 tokenizer 是一个妥协:

- 最优化的重建(一代):VQ-VAE 捕捉精细像素细节,但生成 tokens 语义一致性薄弱
- 精通语义( 理解) : SigLIP embeddings 接近“ cat” 的“ cat” 图像组 tokens 但却不允许进行良好的重建。

展示和传输支付这个费用, 并有一个方向上有明显的质税。 Janus-Pro问道: 为什么需要 tokenizer 当任务有不同的需求?

<a id="the-concept"></a>

## 概念

<a id="decoupled-visual-encoding"></a>

### 脱钩的视觉编码

Janus-Pro的建筑把两者分开 encoders:

- 了解路径。 输入图像  SigLIP- SO400m  2层 MLP transformer body.
- 生成路径。 输入图像( 如果对现有图像进行设置) ++ VQ tokenizer → token 身份证 transformer body.
- 产出生成。 Image tokens 预测的 transformer ++ VQ 甚高频 decoder 象素一样的

该 transformer 身体的上下游都是有任务区分的

输入被 prompt 格式: a `<understand>` 通过 SigLIP 标记路径; `<generate>` 路线通过VQ。 或者路径是隐含于任务。

<a id="why-this-works"></a>

### 为何这样

了解损失获得 SigLIP features,哪种 CLIP 风格 pretraining 已经调整了语义相似性。 该模型的感知基准比 Show-o/ Transmission 有所改善, 因为输入 features 这样做对任务来说更好。

代际损失获得 VQ tokens,该值 tokenizer 已经为重建而调整。 图像质量在 Show- o 上有所改进, 因为 VQ 代码会以干净的像素形式重新组合 。

共享 transformer 中显示两个输入分布( SigLIP 和 VQ) , 并学习与两者合作。 索赔: 足够数据+足够 parameters,身体吸收开关。

<a id="data-scaling--janus-vs-janus-pro"></a>

### 数据缩放——Janus与Janus-Pro

Janus(原为ArXiv 2410.13848)采用分离但规模小(1.3B 参数,有限数据)。

- 7B 参数(vs 1.3B)。
- 第1阶段的90M图像-文本对(alignment72M的上升。
- 72M级第2阶段(统一),比26M级增加。
- 为第3阶段添加了200公里图像元指令样本。

其结果:Janus-Pro-7B在MMMU上与LALVA比赛(60.3对~58),在GenEval上比DALL-E 3(0.80对0.67)胜过一个在统一频谱两侧都具有竞争力的开放型号。

<a id="janusflow--the-rectified-flow-variant"></a>

### JanusFlow——纠正的流程变体

JanusFlow (arXiv 2411.07975) 将 VQ 生成路径转换为修正流程生成路径( 持续 ) 。 分割成为 SigLIP 用于理解 + 校正流程 + 代之代之代。 质量上限进一步提升 。 架构仍然分离 - 结构encoders-shared-body.

<a id="the-shared-bodys-job"></a>

### 共同体的工作

该 transformer 物体处理一个统一的序列,但有两个输入分布。

- 理解:消费SigLIP features + 文本 tokens 自动反向发送文本 。
- 生成: 消耗文本 tokens +(可选图像 VQ) tokens” 发送图像 VQ tokens autoregressively.

身体没有 modality-specific weights 文本样式 transformer 里面会发现 Qwen 或 Llama,加上两个输入适配器。

有意思的是,这表示Janus-Pro的尸体 可以从一个预科医生那里开始 LLM。 Janus-Pro 初始化 DeepSeek-MoE-7B. 选择很重要: LLM 帮助推理能力 纯粹的从零到零 统一模型 难以达到。

<a id="compared-to-internvl-u"></a>

### 与 InternVL-U 相比

实习性VL-U(Lesson 12.10)是2026年的后续行动。

- 本地多式联运 pretraining (InternVL3主干) 。
- Decoupled-encoder 路径( SigLIP 英寸, VQ + 扩散头) 。
- 统一理解+生成+编辑。

实习实验室将Janus-Pro的建筑选择纳入一个更大的框架。encoder 概念是当前对比例化统一模型的默认值。

<a id="limitations"></a>

### Limitations

Decoupled encoders 添加建筑复杂性。 tokenizers 来训练,两条输入路径来维持,两套故障模式。 对于不需要生成的产品,Janus-Pro是设计过度的,选择一种LALVA-家庭理解模式。

对于不需要理解的产品,Janus-Pro资格过高——选择稳定扩散3/流动模式。

对于需要两者的产品来说,Janus-Pro现在是开放的参考结构。

```figure
l5-janus-decouple
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟 Janus-Pro 路由 :

- 两个假的 encoders:SigLIP类(产生256-二方语义矢量)和VQ类(产生整数代码)。
- 一个 prompt 选择 encoder 基于任务标记 。
- 共同参与(待办)进程 token 序列,不管 encoder 生产了它们。
- 第1阶段的开关(alignment至第3阶段(指示曲)加权样本时间表。

打印三个示例的路径:图像 QA、 T2I、图像编辑。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-decoupled-encoder-picker.md`。如果产品需要统一的代际关系+以前沿质量理解,它会选择Janus-Pro、JanusFlow或InternVL-U, 提出具体的数据尺度建议。

<a id="exercises"></a>

## 练习

1. Janus-Pro-7B 在 GenEval 上比 DALL- E 3 强。 请解释为什么7B 开放模型可以匹配 一代的前沿专利模型, 但不能基于理解 。

2. 执行路由器函数:给定 prompt 文本,分类为 `understand` 或 `generate`。您如何处理模糊 prompts 喜欢"描述然后草图"?

3. 以校正的流量替换 JanusFlow 路径。 transformer 体外输出,损失中的变化是什么?

4. 提议第四项任务 Janus-Pro建筑可以再处理一次 encoder示例:图像分割(DINO-system),深度(MIDAS-stype)。

5. 读一下关于数据缩放的Janus-Pro第4.2节。哪个数据阶段对T2I质量收益和Janus贡献最大?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 解码编码 | "两张视觉 encoders" | Separate tokenizer 或 encoder 理解的语义,重建代际关系 |
| 共享体 | "One transformer" | Single transformer 进程之一 encoder输出; 无 modality-specific weights |
| 用于理解的 SigLIP | "Semantic features" | CLIP-家庭视觉塔,提供丰富的概念 features 重建不善 |
| 生成 VQ | "重建代码" | Vector-quantized tokens 完全解码回到像素 |
| JanusFlow | "精密流变体" | 使用连续流匹配生成元件而不是 VQ 的 Janus-Pro |
| 运行标记 | "任务标记" | Prompt 标记( 标记)`<understand>` / `<generate>`选择输入 encoder |

<a id="further-reading"></a>

## 进一步阅读

- [吴等人——Janus(arXiv:2410.13848)](https://arxiv.org/abs/2410.13848)
- [陈等人-Janus-Pro(ARXiv:2501.17811)](https://arxiv.org/abs/2501.17811)
- [Ma等人-Janus Flow(ARXiv:24110.7975)](https://arxiv.org/abs/2411.07975)
- [实习-U(arXiv:2603.0987)](https://arxiv.org/abs/2603.09877)
- [Dong等人-DreamLLM(阿尔西夫:2309.11499)](https://arxiv.org/abs/2309.11499)
