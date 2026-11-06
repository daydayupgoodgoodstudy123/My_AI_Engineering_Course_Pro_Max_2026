<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="from-clip-to-blip-2--q-former-as-modality-bridge"></a>

# 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former

> CLIP 将图像和文字对齐, 但无法生成标题、 回答问题或进行谈话 。 BLIP-2 (Selexforce, 2023) 用小的可训练桥解决了这个问题: 32个可学习的查询矢量在冷冻处 ViT的 features 通过 cross-attention,然后直接插入一个冷冻的 LLM输入流 188M parameters 连接11B的桥 LLM 改为 ViT-g/14. 2026年每个适配者VLM-MiniGPT-4-指示BLIP,LLVA的表兄弟——都是后代。 tokens 进入一个冻结的文本 decoder.

**类型：** 构建
**语言:** Python (stdlib, cross-attention + 可学习的询问演示)
**先修要求:** 阶段12 02(CLIP),阶段7(Transformers)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么一个冷冻的视觉之间的可训练瓶颈 encoder 和冻结 LLM 胜于成本和稳定性的端到端微调。
- 执行a cross-attention 将一组固定的可学习查询包含到外部图像的块 features.
- 穿过BLIP-2的两步 pretraining: 表示式(ITC+IMT+ITG)然后变形(冷冻的LM损失) decoder).
- 比较Q- Former 和 LLAVA 使用的简单的 MLP 投影器, 当每个选择都获胜时进行争论 。

<a id="the-problem"></a>

## 问题

你冻僵了 ViT 生产256个 patch tokens 图像的平面图。您有一个冷冻 7B LLM 中意的 token embeddings 明显连接的桥梁——1408至4096线层——运作正常,但供餐的只有256座。 patch tokens 进入 LLM附加费用 256 tokens 每张图像。 超过32张图像, 即 8192 张 tokens 被视觉所消耗 modality alone.

BLIP-2问题:你能压缩256 -token 图像表达方式远低于 tokens (第32段),同时保存足够的信息供 LLM 来解释,回答问题,以及图片的道理。你能训练这座桥,不触动冷冻的骨骼, 将训练费用仅放在桥上 parameters?

答案: Q- 前置。 32 个可学习的“ 尖叫” 矢量, 交叉到 ViT的 patch tokens制作32 -token 视觉总结 LLM 消费量 188兆 parameters 总共。在接触前,先用对比性、匹配性和基因化目标进行培训。 LLM.

<a id="the-concept"></a>

## 概念

<a id="learnable-queries"></a>

### 可学习查询

Q -Former的核心把戏: 而不是让 LLM文本 tokens 显示图像 patches,引入一套由32个可学习查询矢量组成的新系统 `Q` 并让 *them* 显示图像 patches查询 parameters 模型的模型——在培训期间学习,每张图像都使用同样的32个查询。

之后 cross-attention,每个查询都持有图像的压缩摘要——“描述主对象”、“描述背景”、“计算对象”等。这些查询并不真正专门处理语义标签;它们知道下游损失的编码是什么。

<a id="architecture"></a>

### 建筑

Q - 以前的是一个小 transformer (12层,~ 100M参数) 有两个路径 :

1. 查询路径:32个查询矢量通过 self-attention 然后, cross-attention 冰冻的 ViT的 patch tokens,然后FFFN。
2. 文本路径: a BERT- 类似文字 encoder 共享 self-attention 和新生力量 weights 使用查询路径。 Cross-attention 用于文本路径。

训练时,两个路径都运行。查询和文本通过共享进行互动 self-attention,这意味着查询可以以需要的任务的文字为条件(ITM、ITG)。 inference 甚低频磁力计的时间 handoff,只有查询通过,产生32个视觉 tokens.

<a id="two-stage-training"></a>

### 两阶段培训

BLIP-2 分两个阶段:

第一阶段:代表性学习(无) LLM3项损失:
- 国贸中心(图像-文字对比):CLIP式的集合查询对比 tokens 和文本 CLS token.
- ITM(图像文本匹配):二进制分类器——图像文本对是匹配的吗?
- IG(图像背景文本生成):因果 LM 头以文本为主, 以查询为条件。 强制查询可编码文本元件内容 。

只有Q -前列车 ViT 被冻结。 LLM involved.

第二阶段:基因学习。 LLM (OPT-2.7B或Flan-T5-XL等) 投影到 LLM的 embedding 透过小线性层暗淡。 将其附加到文本中 prompt。仅培训线性投影和前方的 Q-mer 有关所包涵的LM 损失 prompt +图像+标题序列。

第 2 阶段结束后，Q-Former 加投影层构成完整的视觉适配器。在 inference 时，流程为：图像 → ViT → Q-Former → 线性投影 → 拼接到文本前方 → 冻结的 LLM 生成输出。

<a id="parameter-economics"></a>

### Parameter economics

BLIP-2 与 ViT-g/14(1.1B,冻结)+ OFM-6.7B(6.7B,冻结)+Q-前方(188M,培训)=8B,培训188M。 parameters培训费用反映了这一点:在少数A100和最后几周的天数上。

质量: BLIP-2 匹配或击败 Flamingo-80B 连接 zero-shot VQA,但小50倍,桥管正常

<a id="instructblip-and-the-instruction-aware-q-former"></a>

### 指示BLIP和预知指令Q- 格式

指示BLIP (2023) 将Q- 格式扩展, 并增加输入: 指令文本本身 。 cross-attention 时间,查询现在可以访问两个图像 patches 和指令。查询可以专门列出每个指示(“计数汽车”、“描述情绪”),而不是学习一个固定的概要。

<a id="minigpt-4-and-the-projector-only-approach"></a>

### MiniGPT-4和只投影器方法

MiniGPT-4 保留了Q- 格式, 但只训练输出线性投影, 却冻结了其他所有东西。 低价, 但成本是质量的, 询问是 BLIP-2 的, 不是你的。 快速循环对快速循环有好处, 而不是最好的结构 。

<a id="why-llava-went-simpler"></a>

### 为什么LALAVA变简单了

LLAVA (2023, 课程12.05) 以一个普通的2级 MLP 取代Q-Former, 投射每个 ViT patch token 进入 LLM 空间 - 576 tokens 每个图像的 24x24 格,全部输入 LLM。更糟糕的压缩,但让 LLM 原页 patches。当这个过程引起争议时,到2023年底,它就占据了主导地位,因为视觉教学数据(LLAVA-Instruct-150k)证明MLP可以被训练来保存足够的信号。权衡:LLAVA的上下文填得更快,但自然地会达到多图像和视频的大小。

2026年,田间分裂:Q-Former在 token budget 重要( 长视频, 许多图像); MLP 投影器在原始质量 / i 中占主导地位 token 优先处理

<a id="gated-cross-attention-flamingo-the-ancestor"></a>

### Gated cross-attention火烈鸟,祖先

火烈鸟(Lesson 12.04)早于BLIP-2型,使用相同 cross-attention 想法,但在每个冻结 LLM 平面,而不是作为一座桥。 BLIP-2 显示您只能压缩到输入层,并且仍然有效。 Gemini 和理论结合: 断开输入 tokens 加上可选门 cross-attention 用于内置字符 few-shot.

<a id="the-2026-descendants"></a>

### 2026年后代

- Q- 原版: BLIP-2, 教程BLIP, MiniGPT-4, 以及大多数视频语言模式 token budget reasons.
- 佩西贝尔·雷姆普勒:Flamingo的变体(Lesson 12.04);伊德菲克家族,鹰,奥姆尼马埃。
- 微光谱投影器:LLAVA、LLAVA-NXT、LLAVA-OneVision、Cambrian-1。
- Attention 游泳池:VELA,帕利杰马。

四个都有效,决定的问题在于你是否受限制 token budget 或质量 - / /token.

```figure
modality-projection
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 创建标准标准 Q- 格式 cross-attention:

1. 模拟 256 张图像 patch tokens (第128次)。
2. 证明32个可学习查询(第128次)。
3. 运行缩放点产品 cross-attention (问答问题,K/V发自 patches).
4. 项目至 LLM- 透过直线层,使二分位数(512)
5. 输出 32 LLM- 准备视觉 tokens.

纯净的数学 Python (在矢量上旋转的圈子) Toy , 但要纠正形状。The attention-weight 矩阵被打印,以便您看到 patches 每一个查询都从中提取。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-modality-bridge-picker.md`。给定目标 VLM 配置(视图) encoder token count, LLM ),它建议“前方”对MLP对 Perceiver Reampler, 其理由简短, parameter-每座桥的计数

<a id="exercises"></a>

## 练习

1. 执行 cross-attention 块英寸 PyTorch。 attention-weight 矩阵为 32 x 256, 每行数为 1 softmax.

2. 在BLIP-2阶段1,Q-Fmer同时发生三项损失:ITC、IMT、ITG。每个都以伪代码写前期签名。其中一项需要文本 encoder 要激活的路径 ?

3. Compare parameter 计数:Q- Former(12 层, 768 隐藏) 相对于 2 层 MLP 投影器 (1408  4096, 两层)。 LLM 188MQ-Former成本是否还得回培训效率?

4. 阅读BLIP-2号纸(arXiv:2301.12597)中关于Q- Former 初始化方式的第3.2节。 BERT- 基础(不是随机的)加速了趋同。

5. 10分钟视频,在1个FPS取样到60个框架时,计算每个框架 token 费用(克元______________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________ tokens/范围)与(MLP投影器 + 576) tokens符合128k的尺寸token LLM context window?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Q-Former | "Querying transformer" | 小 transformer 具有32个可学习的查询矢量,该矢量交叉到冻结 ViT features |
| 可学习查询 | "Soft prompt 以视觉为目的 | 一套固定的 parameters 中作为 cross-attention;每个模式学习,在所有投入中共享 |
| Cross-attention | "从这里,从那里,K/V" | Attention 查询、密钥和值来自不同来源;查询如何拉动 ViT patches |
| ITC | "图像文字对比性" | CLIP 式损失适用于 Q- Former 集合查询与文本 CLS |
| ITM | "图像文本匹配" | 硬阴性双对的二进制分类器; 强制查询以区别细微错配 |
| ITG | "图像基础文本生成" | 生成文本时以查询为条件的因结果 LM 损失; 强制查询编码文本可编码内容 |
| Two-stage pretraining | "代表然后发扬光大" | 第一阶段单是Q-前列火车(ITC/ITM/ITG);第二阶段是冻结的 LLM 仅培训投影 + Q- 格式 |
| 冻僵的骨干 | "不要细微地" | 愿景 encoder 和 LLM weights 已经固定; 只有桥上的火车 |
| 投影头 | "渴望着 LLM dim" | 最后线性层映射Q- 格式输出到 LLM的 embedding dimension |
| 移动器恢复器 | 佛拉明戈的版本 | 类似的可学习的询问 cross-attention,被火烈鸟用于每一层,而不是作为一座桥梁 |

<a id="further-reading"></a>

## 进一步阅读

- [Li等人-BLIP-2(arXiv:2301.12597)](https://arxiv.org/abs/2301.12597) - 核心文件。
- [Li等人-BLIP(arXiv:2201.12086)](https://arxiv.org/abs/2201.12086) 贸易中心/信息技术管理/信息技术小组三重奏的前身。
- [Li等人-ALBEF(阿尔西夫:2107.07651)](https://arxiv.org/abs/2107.07651) ——"在引信前调整"——第一阶段训练的概念祖先。
- [Dai等人——BLIP教程(arXiv:2305.06500)](https://arxiv.org/abs/2305.06500) 教官 - 认识Q - 前。
- [Zhu等人-MiniGPT-4(arXiv:2304.10592)](https://arxiv.org/abs/2304.10592) ——只采用投影器的方法。
- [Jaegle等人—— Perceiver IO(阿尔西夫:2107.14795)](https://arxiv.org/abs/2107.14795) 学习式询问的一般结构 cross-attention.
