<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="internvl3-native-multimodal-pretraining"></a>

# InternVL3：原生多模态 Pretraining

> 实习前的每个打开 VLM 都遵循相同的三步配方: 使用文本 LLM 培训数万亿文本 tokens闪烁在幻象上 encoder,然后细调接缝。 alignment 债务——案文 LLM 已经用完 pretraining 预算在纯文本上, 并且不当地理解视觉 tokens。当您添加视野后, LLM 需要重新学习如何将视觉输入与其文字推理联系起来,而不要忘记文字。 pretraining 运行、文本和多式联运与第一步脱节。 Gemini 2.5 MMMU-Pro的教学,第78B段,开课,该课为当地语 pretraining 以及当你做的时候会发生什么变化。

**类型:** 学习
**语言:** Python (Stdlib,训练公司混音器)
**先修要求:** 阶段12 -05, 阶段12 -07(答复)
**时间:** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么热后VLM培训积累 alignment 债务,以三种可衡量症状(灾难性的遗忘、回答漂移、视觉文字不一致)为根据。
- 描述 InternVL3 的本地语言 pretraining 字符串组合和为什么文本的比例: 间断: 标题重要。
- 比较 V2PE( 可变视觉位置编码) 到 Quen2- VL 的 M-RoPE.
- 命名为视觉解析路由器(VIR)和脱钩视野语言(DvD)部署优化。

<a id="the-problem"></a>

## 问题

热后VLM培训是默认的。 LLAVA, BLIP-2, Qwen-VL, 思想家 -所有都已经准备好 LLM (Llama维库纳 Qwen, Mistral和添加愿景。

1. Frozen LLM + 冷冻的视觉 encoder + 可训练的投影机,在标题对齐方面接受培训 embeddings.
2. Unfreeze LLM教学数据培训(LLAVA-Instruct, ShareGPT4V)。
3. 任选任务特定微调。

三种症状 alignment 债务出现 :

- 灾难性的忘记。 后热 VLM 忘记了只使用文本的技能。 GSM8K 分数下降了 5- 10 分。 Hellaswag 分数下降了 。 agents regress.
- 回答漂移。 相同的视觉问题的小词会得到不同的答案。 视觉 encoder 连接到 LLM 与比 LLM属于自己的 tokens.
- 视觉文字不一致。 VLM 可以正确描述图像, 然后回答一个与它自己的描述相矛盾的问题。 VLM tokens 不参加 LLM内部一致性检查与文本相同。

这些症状都有详细记载。 MM1.5 第4节对症下药。LALVA-One Vision的浸泡暗示着这些症状。 pretraining 答案就是这个

<a id="the-concept"></a>

## 概念

<a id="native-multimodal-pretraining"></a>

### 本地多式联运 pretraining

实习性VL3火车从零开始,在一级由本地多式联运组成的体形上。

- 40%只使用文本的数据( FineWeb、 校对- Pile-2 等)
- 35%的图像文本断裂数据(OBELICS, MMC4型)
- 20%配对图像缩略图数据
- 5%的视频文本数据

Vision tokens,文本 tokens,以及跨模式的相互作用 都参与到相同的损失中 gradient 步数。 无 alignment pretraining,没有投影器冷冻阶段, 没有灾难性的忘记从中恢复。

训练是基础模型的单一阶段。 教学调整如下, 但基础模型已经理解视觉 tokens 身为一流公民

<a id="v2pe-variable-visual-position-encoding"></a>

### V2PE( 可变视觉位置编码)

Quen2-VL使用M -RoPE 内置 V2PE: 位置编码依位置变化而异 modality 类型(文字、图像、视频)具有可学习的缩放。

- Text tokens 获得 1D 位置( 文本索引) 。
- Image patches 获得 2D 位置( 行, 科) 。
- 视频框获得 3D 位置( 时间、 行、 COL) 。

三个股一样 RoPE 频率基,但每个波段的隐藏底片分配是一个学习 parameter 而不是固定的分割。 在使用时间和空间频率分辨率时,可以自由进行交换。 pretraining.

V2PE的减价索赔: 1-2点的视频基准超过M-RoPE 而不是革命,而是更干净的

<a id="visual-resolution-router-vir"></a>

### 视觉解析路由器( VIR)

优化配置。 并非所有图像都需要完整分辨率编码。 照片上有一个对象, 其详细度低的废物 tokens 当编码为 1280px 本地。 VIR 是小分类器, 预言在编码前回答问题所需的最小分辨率 。

路线分三个层次:低频(256) tokens中度(576),高度(2048+)。60%的生产流量查询,低度或中度即可。净效果:2-3x质量相等的输送量。

<a id="decoupled-vision-language-deployment-dvd"></a>

### 愿景-语言部署(DvD)

当你在做一个大的VLM, 视觉 encoder 每个图像运行一次, 但 LLM 每个输出自动递减 token。两个组成部分有不同的瓶颈(视线= GPU conv + 的内存带宽 attention; LLM = KV cacheDvD 将它们分割成分开 GPUs 与 streaming 之间.

8B+400M encoder 模型,DvD大约是每个无记号传输量的两倍, 而不是在同一地点。

<a id="single-stage-vs-multi-stage-quality"></a>

### 单阶段与多阶段质量

实习生3的主要基准索赔:78B参数,匹配 Gemini 2.5 Pro的MMU-Pro. 38B,匹配 GPT8B时,领头板开着 单阶段预演+导图配方

该 alignment- 债务假设可以衡量:InternVL3-8B的文字基准点(MMLU, GSM8K)损失比每单位视觉基准收益的Qwen2.5-VL-7B少。 该模型更具有泛泛性,因为培训是一分而不是两分。

<a id="internvl35-and-internvl-u"></a>

### 实习生L3.5和实习生U

INTERVL3.5 ( 2025年8月) 测量配方。 相同的本地预谋方法、 更多的数据、 更多的参数。 MMMU的改进是渐进的。

InternVL-U(2026)增加了统一的生成——通过 MMDiT 头部在同一骨干上添加图像输出。 “ U”代表“理解的一代” , 追逐着外传式的统一模型( Lesson 12. 13 )。 同样的本地预演骨支持理解和下一代头部。

<a id="trade-offs-of-native-pretraining"></a>

### 本地交易 pretraining

Native pretraining 并非免费 :

- 计算。从零开始培训一个新的 VLM 成本与培训文本相同 LLM ——百万个 GPU-小时。 现有热后适应再利用 LLM weights,节省了大部分费用。
- 数据 比例尺的图像文本间断公司非常罕见。 OBELICS 是141M 文档; MMC4 是 571M 。 15T 时仅使用文本 tokens多式联运 pretraining 数据匮乏是一个难以克服的制约因素。
- Base-LLM 重新使用。 本地 pretraining 放弃选项, 跳入新 LLM 稍后,后热能让你交换 Llama- 3.1 改为 Llama- 4次再培训,只有适应器

实习者3 下注: alignment 债务比再利用损失更糟糕。 基准支持了索赔。 成本对生产成本的计算使得未来的实验室无法廉价复制。 热后VLMs会保持存在, 因为大多数项目仍然价格较低。

```figure
l5-native-pretrain
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 是一个训练公司搅拌器和Vir路由器模拟器。

- 使用目标体组合(% text,% interleaved,%caption,%victive) 计算每步的预期值 modality.
- 模拟一组查询的Vir路径(分布:50%低详细,30%中,20%高详细)和报告平均 token count.
- DvD 产出估计数 encoder 与 LLM FLOPs.
- 打印后热对本地 pretraining 参数、计算、数据和预期 alignment- 债务症状

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-native-vs-posthoc-auditor.md`. 鉴于拟议的甚低频成像培训计划,它审计是本地还是后热点、旗帜 alignment债务风险,建议组合。在对新的开放VLM项目进行裁剪时使用它,并且需要选择培训策略。

<a id="exercises"></a>

## 练习

1. 估计InternVL3-8B(本地预设)和LLAVA-OneVision-7B(热后)之间的三角形。 GPU- 差不多几小时?

2. InternVL3 报告了40%的文本 / 35% 的内置 / 20% 的字幕 / 5% 的视频。 如果您的目标任务为视频重, 请提出新的比例, 并争论为什么基础模型仍然需要大量文本和字幕数据 。

3. 读取 MM1.5 第4节关于遗忘的内容。 请列出后热训练显示最大回归的确切基准。 回归成本是多少 ?

4. VIR将60%的流量引向低分辨率编码。 它会错开什么类型的查询( 当需要高射线时会发送到低射线) ? 提议三种路由器故障模式 。

5. DVD 分割视野 LLM 分开 GPUs。 DvD 伤害了交通量而不是帮助?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 本地多式联运 pretraining | "从零开始" | 文字+图像+视频 tokens 参加第1步的损失,以后再不上 |
| Alignment debt | 后处刑 | 文字技巧和答案的一致性的可衡量回归 从螺旋形影像到冷冻 LLM |
| V2PE | "可变视觉的编译" | Per-modality 可学习位置编码分配; InternVL3 的 M-RoPE successor |
| ViR | “分辨率路由器” | 编码前选择每个查询所需的最小分辨率的小分类器, 保存 inference tokens |
| DvD | "无休止的部署" | Vision encoder 在一个 GPU, LLM 与溪流相伴 handoff; 大VLMs 的双倍输送量 |
| InternVL-U | "统一理解+一代" | 2026年后续行动,将图像生成头部添加到本地的预演骨干上 |
| 间断体 | "欧贝利克斯/MMC4" | 附有自然读数的文字和图像的文件;当地材料 pretraining |

<a id="further-reading"></a>

## 进一步阅读

- [陈等人——实习1号(arXiv:2312.14238)](https://arxiv.org/abs/2312.14238)
- [Zhu等人——实习生(arXiv:2504.10479)](https://arxiv.org/abs/2504.10479)
- [实习性VL3.5(arXiv:2508.18265)](https://arxiv.org/abs/2508.18265)
- [实习-U(arXiv:2603.0987)](https://arxiv.org/abs/2603.09877)
- [张等人-MM1.5(arXiv:2409.20566)](https://arxiv.org/abs/2409.20566)
