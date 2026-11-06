<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="flamingo-and-gated-cross-attention-for-few-shot-vlms"></a>

# Flamingo：面向 Few-Shot VLM 的门控 Cross-Attention

> 深明的Flamindo (2022年) 比其他人都做了两件事。 它显示一个模型可以任意处理图像、视频和文字的断裂序列。 它显示VLMs可以学习内涵 — — 给个 few-shot prompt 有三个示例( 图象、 标题) 配对, 模型标题则显示没有 gradient 机制:门 cross-attention 层,插入于冻结的 LLM现有的层, 由一个学习的塔纳门开始在零, 所以 LLM初始化时保存文本能力。 此课会向 Flamingo 的 Perceiver 恢复器和 Gated 移动 cross-attention 建筑—— 历史学家 Gemini断开输入和 Idefic2 的视觉 tokens.

**类型:** 学习
**语言:** Python (斯迪利布,门关) cross-attention + 移动器恢复器演示)
**先修要求:** 阶段12 -03(BLIP-2 Q-前期)
**时间:** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释怎么关上门 cross-attention 保存一个被冻结的 LLM塔尼(门)初始化时的文字能力=0。
- 穿过一个 Perceiver 恢复器: N 图像 patches K 修正“ 延时” 查询 cross-attention.
- 描述Flamingo如何处理图像文本的断裂序列, 并使用尊重图像布置的因果遮罩 。
- 复制 a few-shot multimodal prompt 结构( 3个图像插图示例, 然后是查询图像) 。

<a id="the-problem"></a>

## 问题

BLIP-2 种子 32 视觉 tokens 变成一个冰冻的 LLM输入层。 每张图像工作一个 prompt。但是,如果你想要喂 *many* 图像与文字互连, 如“ 这是图像 A, 标题; 这里是图像 B, 标题; 现在是图像 C, 标题 ” 。 LLM的 self-attention 需要处理 image tokens 和文本 tokens 以及哪些位置可以关注到哪些图像会变得棘手的问题。

火烈鸟的回答:不要改变 LLM输入流。插入额外 cross-attention 现有 LLM 文本 tokens 仍然流经 LLM因果关系 self-attention 总是这样,每少一个 LLM 区块, 文本 tokens 交叉到图像 features 门(初始为零)是指在零点时,新层是无操作层——模型的行为与预训练的完全相同。 LLM。随着培训的推进,大门打开,视觉信息开始流动。

第二个问题回答:您如何处理每个图像的变量数( 0、 1或多个) ? prompt一台小型的收音机 cross-attention 模块,无论数字 patches 您拥有并生成了固定的视觉潜伏数 tokens. 该 LLM cross-attention 层看到相同的形状, 不论图像在 prompt.

<a id="the-concept"></a>

## 概念

<a id="the-frozen-llm"></a>

### 冻僵了 LLM

火烈鸟从冰冻的香奇拉开始 LLM全部 70B weights 未触及。 现有案文 self-attention 新生力量正常作业。

<a id="perceiver-resampler"></a>

### 移动器恢复器

每一个图像 prompt, 该 ViT 生产量N patch tokens。Perceiver 恢复器有 K 固定的可学习隐性(Flamingo 使用 K=64)。每个恢复器块是两个子步骤:

1. Cross-attention: K 潜伏值覆盖 N patch tokens (来自潜伏物的Q, K/V来自 patches).
2. Self-attention + 潜伏物中的FFFN。

在 6 个恢复器区块后,输出为 K= 64 视觉 tokens 1024年的低温 patches 该 ViT 制成的A 224x224图像(196) patches和一张480x480的图像(900) patches) 以64个恢复器退出 tokens.

视频的恢复器是暂时使用的: patches 生成64个潜伏值, 时间位置编码让模型区分 t=0 和 t=N。 完整视频变为 T * 64 视觉 tokens.

<a id="gated-cross-attention"></a>

### Gated cross-attention

冰冻的M层之间 LLM (Flamingo使用M=4),插入新的门 cross-attention block:

```
x_after_llm_block = llm_block(x_before)
cross = cross_attn(x_after, resampler_output)
gated = tanh(alpha) * cross + x_after
x_before_next_block = gated
```

- `alpha` 是一个可学习的天平初始化为零。
- `tanh(0) = 0`门被打开 branch 零分的捐赠
- 作为 `alpha` 离开零, cross-attention 贡献增长顺利。
- 剩余连接意味着即使一个完全开放的大门也无法覆盖 LLM文本表达式; 它只是添加图像信息在上面 。

这是Flamingo 中最重要的设计选择:视觉调节是添加、锁定和初始化时零。 第0步的Flamingo是纯文本输入的完美 Chinchilla 70B。

<a id="masked-cross-attention-for-interleaved-inputs"></a>

### Masked cross-attention 用于间断输入

在一个 prompt 喜欢"<image A> 标题A <image B> 标题B <image C> ",每个文本 token 只能看到它之前的图像 cross-attention 掩码执行: 文本 token 处于岗位 `t` 只对图像恢复器 tokens 其图像索引 `i < i_t` where `i_t` 是位置前的最新图像 `t`。“只看到上一个图像”或“看到前面所有图像”都是有效的选择; Flamingo 选择了前一个。

<a id="in-context-few-shot-learning"></a>

### In-context few-shot learning

火烈鸟 prompt 看起来像:

```
<image1> A photo of a cat. <image2> A photo of a dog. <image3> A photo of a
```

该模型看到完成模式和输出“鸟”(或任何图像3显示的)。 gradient 冻结的 LLM的 in-context learning 能力通过大门 cross-attention 这是报纸的一面之词,也是为什么重要。

<a id="training-data"></a>

### 训练数据

火烈鸟在三个数据集方面接受培训:

1. 多模式大网(M3W):43M网页,带有内置图像和文字,正在重建阅读顺序。
2. 图像- 文本对齐( ALIGN + LTIP): 4. 4B 双。
3. 视频-文字对称(VTP):2 700短片。

OBELICS (2023) 是断裂网络的公开复制, 由 Idefics, Idefics2 和最开放的“ 类似Flamingo” 模型训练来进行。

<a id="openflamingo-and-otter"></a>

### OpenFlamingo 和 Otter 软件开发器

OpenFlamingo (2023) 是开放式复制。 结构相同 (Perceiver Reampler + Gated) cross-attention 冻结 LLaMA 或 MPT)。 Checkpoints 3B、4B、9B. 由于底部较小,质量落后于火烈鸟 LLM 数据也少了

Otter(2023年)在OpenFlamingo的基础上,对MIMIC-IT(一套多式指令数据集)进行了指示调控,显示门 cross-attention 工作为 instruction following too.

<a id="the-descendants"></a>

### 子孙

- 理论/理论2 /理论3: 拥抱脸的门 cross-attention 直线, 逐渐简单( Idefics2 将恢复器放下来直接 patch tokens 适应性集合)。
- 火烈鸟向迦梅莱翁过渡:到2024年,许多小组转移到早期集聚(Lesson 12.11);火烈鸟式门 cross-attention 仍在生产中,需要冻结骨干。
- Gemini断裂输入: 概念上继承了 Flamingo 的断裂格式灵活性, 尽管精确的机制是专有的。

<a id="comparison-to-blip-2"></a>

### 与BLIP-2的比较

| | BLIP-2 | Flamingo |
|---|---|---|
| 视觉桥 | 输入时一次 Q- 之前 | Gated cross-attention 在每个M层 |
| Visual tokens | 每张32 | 每张图象64个横贯图层 |
| Frozen LLM | 是的 | 是的 |
| Few-shot in-context | Weak | 坚固 - 纸张的中间件 |
| 间断输入 | 无本地支持 | 是的,设计目标 |
| 训练数据 | 130M双 | 1.3B对+4300M间断页 |
| Parameter count | 188M 培训 | ~10B 培训(跨一格) |
| 计算 | 8个A100天 | 千个 TPUv4 的周数 |

选择 BLIP-2 用于预算的单图像 VQA。 选择 Flaminggo/ Idefics 2 用于间断工作 , few-shot,或多图像推理。

```figure
cross-attention-fusion
```

<a id="use-it"></a>

## 实际应用

`code/main.py` demonstrates:

1. 一台36号假的收发机 patch tokens 具有8种可学习的潜伏物(纯 Python cross-attention).
2. 门锁 cross-attention 步进 `alpha = 0` 输出等于输入( N)LLM ),没有变化) `alpha = 2.0` 视觉贡献混杂在一起
3. 制造二维的外叶壁建材 attention 用于“(图像1)(文本1)(图像2)(文本2)”序列的遮罩。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-gated-bridge-diagnostic.md`。鉴于 VLM 的开放式配置( resampler Y/N, 交叉连接频率, 门式),它可以识别 Flammingo 线条元素,并解释冻结策略。对于调试微调降低文本性能的原因很有用(答案:大门太宽了) 。

<a id="exercises"></a>

## 练习

1. 计算 Flamingo- 9B 的视觉 parameter 计数: 9B LLM +1.4B 门 cross-attention 层+64M 恢复器。 总共参数中有多少部分是经过培训的?

2. 执行封锁的剩余 `y = tanh(alpha) * cross + x` 在 PyTorch。实验性地显示 `alpha=0`, `y==x` 完全在内侧

3. 读取 OpenFlamingo 第3.2节(arXiv:2308.01390),说明每集如何处理多幅图像 prompt 显示图像的大小。 描述粘贴策略 。

4. 为什么火烈鸟 cross-attention 隐藏让文本 token 处理 *仅是最近* 读取 Flamingo 纸第 2. 4 节,并解释权衡。

5. In-context few-shot: 构建 a prompt , 并有四个例子显示“ 主对象图像 ” 的颜色, 用于新的 Flamingo 变体。 描述预期的精确性模式, 您将示例数从 0 到 8 个不等 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 移动器恢复器 | "Fixed-latent cross-attention" | 生产 K 型固态模块 tokens 从变量输入数中 patches |
| Gated cross-attention | 龙舌兰桥 | 残余层 `y = tanh(alpha)*cross + x`,可学习的阿尔法,因数 0 |
| 中断输入 | "混合序列" | Prompt 格式,图像和文字在阅读顺序中自由混合 |
| Frozen LLM | "否 LLM gradients" | 案文 LLM的 weights 不更新; 只有恢复器 + 交叉连接层列车 |
| Few-shot | "内置示例" | 给一些(图像,回答)配对在 prompt; 模型不作微调而概括 |
| OBELICS | 断绝的网络资料 | 开放141M网页的数据集,按阅读顺序显示图像和文字 |
| 龙猫 | "70B 冻在基地" | 火烈鸟的冷冻文本 LLM,从深明的香琪拉纸 |
| 出入口时间 | "阿尔法如何移动" | 以 cross-attention 训练时大门打开 |
| 横向- atn 频率 | "每层M" | 门锁多频繁 cross-attention 插入块; 火焰使用 M=4 |
| OpenFlamingo | “开放复制” | 摩西卡利/LAION打开 checkpoint 3-9B; 与 Flamingo 相同的建筑 |

<a id="further-reading"></a>

## 进一步阅读

- [Alayrac等人-Flamingo(arXiv:2204.14198)](https://arxiv.org/abs/2204.14198) - 原始文件。
- [Awadalla等人-开放Flamingo(阿尔西夫:2308.01390)](https://arxiv.org/abs/2308.01390) 开放复制。
- [Laurençon等人——奥贝利克斯(arXiv:2306.16527)](https://arxiv.org/abs/2306.16527) - 断裂的网络资料
- [Jaegle等人—— Perceiver IO(阿尔西夫:2107.14795)](https://arxiv.org/abs/2107.14795) 佩西维尔将军的建筑
- [Li等人-Otter(arXiv:2305.03726)](https://arxiv.org/abs/2305.03726) 火烈鸟后代
- [Laurençon等人——理论2 (arXiv:2405.0246)](https://arxiv.org/abs/2405.02246) 现代简化火烈鸟方法。
