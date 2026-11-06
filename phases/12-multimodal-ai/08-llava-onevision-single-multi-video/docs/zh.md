<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="llava-onevision-single-image-multi-image-video-in-one-model"></a>

# LLaVA-OneVision：统一处理单图、多图与视频

> 在LLAVA-OneVision(Li等人,2024年8月)之前,开放VLM世界有不同的血统:单图像的LLAVA-1.5、像Mantis和VILA这样的多图像模型、视频-LLAVA和视频-LLaMA光视- OneVision认为,单一课程可以培训一种模式来主导所有三种情景,而新出现的任务转移效应(向视频输出的单图像、向单一图像输出的多图像推理)胜过专家的总和。token budget 并且,在各种情况下都保持不变,加上一个明确的课程,从一图到一图(多图),再到视频。 这个课程读取预算、课程和突发行为。

**类型：** 构建
**语言:** Python (stdlib, token budget 求解器+课程规划器)
**先修要求:** 阶段12 -05(LLAVA),阶段12 -6(任何分辨率)
**时间:** ~180分钟

<a id="learning-objectives"></a>

## 学习目标

- 设计视觉token budget 保持一个图像、多图像和视频输入的恒定
- 下令开设培训课程,将技能从单一图像转移到视频,不忘灾难性。
- 解释为什么一个模型能打赢专家 parameter 校对时计数
- 列出LLAVA-OneVision报告的三种新能力:多镜头推理、标记提示、iPhone屏幕截图 agent.

<a id="the-problem"></a>

## 问题

图像、多图像和视频 都强调一个不同的模型

单图像想要高分辨率 tokens (任何反射,~2880视觉 tokens以捕捉OCR和细细细节。 每样样本的预算: 1张图像, 2880 tokens.

多图像想要一些中等分辨率的图像(~ 576) tokens 每个样本的预算:4-8张图像,576张图像,2300-4600张图像。 tokens.

视频想要很多低分辨率框架(~ 196) tokens 用于捕捉时间动态。 tokens.

如果您训练不同的模型, 您选择一个预算。 如果您训练了一个模型, 您需要预算来在不引起爆炸的情况下 将各种情景进行明智的衡量 。

预览前的默认答案是“ 训练一个方案, 忽略其他方案 ” 。 视频- LLAVA 将视频改装为具有额外培训阶段的图像模型 。 LLAVA- NEXT 添加了多图像支持, 并加了平铺。 没有处理完所有三个方案 。

<a id="the-concept"></a>

## 概念

<a id="the-onevision-token-budget"></a>

### 幻觉 token budget

光视镜 选择了统一的视觉token budget 约3,000-4000美元 tokens 每一样本,按设想情况分配不同:

- 单个图像: 任何Res- 9 (3x3 瓷砖+缩略图), 每张瓷砖为 384 和 729 patches双线式双层热聚体 2x2 182 每瓦。 * 182 + 182 = 1820 tokens。或任何Res-4,每张729瓦=2916+729。
- 多图像:每张分辨率中等的图像(384,无瓦),729 tokens 6张图片4374 tokens.
- 视频:32个框架,384分方位,3x3双线池 tokens 总计:32 * 81 = 2592 tokens.

拨款总额大致保持不变 tokens. 该 LLM 从来没有看到过一个批量的 吹它的背景。 encoder 产生不同的几何 假设情景,但 LLM 消耗的预算相同。

<a id="the-three-stage-curriculum"></a>

### 三阶段课程

激光雷达-一视列列车分三个阶段:

1. Single-image SFT 所有数据都是单图像加文本。 高分辨率 AnyRes 输入培训。 这可以教给感知、 OCR 和精细理解。 使用 LLAVA- NEXT 数据加上 单图像特定数据 。
2. OneVision SFT 组合单图像+多图像+视频(统一取样框)。 token budget。这可以教模型处理不同批量形状。 weight 重置——从SI阶段开始。
3. 任务传输( TT 阶段) 继续使用目标任务组合, 通常根据产品对多图像或视频进行更重的组合。 可选用精细调试配置 。

关键: 课程顺序很重要。 培训视频第一或多图像第一比单图像第一产生更差的图像性能, 即使有相同的数据。 纸张会明确将这一点扩大 。

<a id="why-curriculum-works"></a>

### 课程为何有效

单一图像培训建立了观念基础。 Patch tokens 带有精细的视觉 features; 该 LLM 学习将其与文字整合。 多图像和视频带来了结构性挑战(即哪些是,先发生什么),而如果没有强大的观念基础,这些挑战很难学习。

如果将所有情景从零开始结合起来加以培训,模型的下限感知(每批有限的单一图像数据)和超值结构(多图像/视频数据的数量)。结果:一个遵循交叉图像推理模式但视觉浅。

课程顺序赋予你从职业介绍所阶段到编组/时间推理的感知力,而没有失去。

<a id="emergent-cross-scenario-skills"></a>

### 新出现的跨设想技能

光学和视觉卫星报告有三种新能力:

1. 多镜头推理。 单独培训多图像+视频; 在 inference,询问多镜头驾驶场景。模型正确地整合了各种观点,尽管在训练中从未看到过这种精确格式。
2. 标记的设置提示。 用户在图像中用数字标记来标记对象; 模型解释“ 3 表示相对于 7 表示什么” 。 既用标记也不用注释来训练; 从空间组合中学习 grounding + 多图像参考。
3. iPhone-screenshot agent。用户提供 iPhone 屏幕的截图,并要求计划下一次点击。在 UI 截图、用户工作流程视频和双对前/后多图像上培训。 agent 使用场景.

这些不是经过培训的任务;它们产生于课程的组成结构。

<a id="visual-token-pooling"></a>

### Visual-token pooling

该 token budget 光线对二维线进行双线内插 patch 网格:24x24=576 patches = 144(2x因数)或 8x8 = 64 (3x因数)。 patch- 网格空间,不是 token 空间,以保存位置。

每种假设情景的集合系数的选择本身就是一种 hyperparameter减少集合=更多 tokens = 代表比例较高。 tokens = 更多符合框架/图像。

<a id="llava-onevision-15"></a>

### LLaVA-OneVision-1.5

2025年后续计划(LLAVA-OneVision-1.5,arXiv 2509.23661)在训练数据、模型方面“完全开放”。 weights和代码。匹配某些基准上的专利空白,并使配方民主化。相同的课程、更多的数据、更好的基础 LLM。没有改变建筑。

<a id="contrast-with-qwen25-vl"></a>

### 与 Quen2.5-VL 的对比

Quen2.5-VL( Lesson 12.09) 做出不同的选择。 它使用 M-RoPE 使用1分钟的视频,而不是固定的共享。 tokens 光环-One Vision 确定了预算和共享规模。 两者都工作; 它们为了可预测性而交易配置。

```figure
l5-onevision-budget
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 是一个视觉式VLM的课程和预算规划者。 token budget 每一样本和目标情景组合(例如40%的单一图像、30%的多图像、30%的视频),它:

- 分配分辨率、集合系数和每个假设情景的框架。
- 检查每个方案是否都适合共同预算。
- 预期提出的报告 token count, LLM 以及哪些假设情况没有得到充分重视。
- 打印一个逐阶段培训时间表。

用来计划一个视觉微调 或者检查VLM的部署费用

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-onevision-budget-planner.md`。根据目标任务分布和每个样本的预算,它释放了 AnyRes 系数、每个框架的集合、视频框架数和课程阶段 weights。在训练或微调统一的VLM时使用此选项。

<a id="exercises"></a>

## 练习

1. 您的产品支持80%的单图像,10%的多图像(2-4张),10%的视频(8-16张)。 token budget。您会把额外预算放在哪里?

2. 阅读LALAVA-One Vision第4.3节(显眼能力),提出课程可能解开的第四门新技能,但论文没有报告。

3. 交换课程顺序——先培训多图像,然后是单图像,然后是视频。

4. 本文报告每样本仅8个框架的录像基准。 inference是什么先突破 - token budget 还是时间推理?

5. 24x24双线联营 patches 12x12 是每平方下方的 4x 减小。 在 stdlib 中执行集合 Python 并验证每2x2块的平均值与双线输出相符。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 展望情景 | 单图像,多图像,或视频 | 三个输入中有一个形状了统一的 VLM 控件; 预算在横跨时保持不变 |
| Token budget | "有多少个 tokens 每一样本" | 视觉总 tokens 该 LLM 每一培训/ inference 样本,一般为3000-4000 |
| Curriculum | "训练令" | 选择用于紧急传输的阶段排序( 单图像 + 多图像 + 视频) |
| 双线共享 | "Token shrink" | 将双线内插法应用于 patch 网格(2D) token 保存位置时计数 |
| 新兴技能 | "没有训练,仍然有效" | 出现的能力 inference 由于课程构成原因,没有匹配的训练数据 |
| AnyRes-k | "K牌摆设" | k 固定分辨率的亚梯子加一个缩略图,典型 k {{4, 9} |
| 任务转移 | "假设的概括化" | 通过共享主干获得的关于单一图像的技能(反之亦然)适用于视频 |

<a id="further-reading"></a>

## 进一步阅读

- [Li等人——LLAVA-One Vision(arXiv:2408.0326)](https://arxiv.org/abs/2408.03326)
- [LLAVA-OneVision-1.5:完全开放框架(arXiv:2509.23661)](https://arxiv.org/abs/2509.23661)
- [Lin等人——视频LLAVA(arXiv:2311.10122)](https://arxiv.org/abs/2311.10122)
- [Lin等人-VILA(arXiv:2312.07533)](https://arxiv.org/abs/2312.07533)
- [王等人——Quen2-VL(arXiv:2409.12191)](https://arxiv.org/abs/2409.12191)
