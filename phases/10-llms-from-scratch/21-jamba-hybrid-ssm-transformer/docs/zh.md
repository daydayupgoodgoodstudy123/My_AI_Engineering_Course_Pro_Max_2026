<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="jamba--hybrid-ssm-transformer"></a>

# Jamba——混合 SSM-Transformer

> 国家空间模型(SSM)和 transformers 想要的东西不一样。 Transformers 购买质量通过 attention 特殊保障机制购买线性时间 inference AI21的Jamba (2024年3月)和Jamba 1.5 (2024年8月)将其置于同一模式中:1 Transformer 每7 Mamba 层层, MoE 和256k的车 context window 适合单80GB GPUMamba-3 (ICLR 2026) 用复杂价值的国家空间和MIMO预测来收紧SMS一边。 这个课读了两个建筑的结尾,并解释了为什么当纯-SSM和纯-Transformer 长期尝试没有。

**类型:** 学习
**语言:** Python (平流、层混合计算器)
**先修要求:** 阶段10 · 14(开放型建筑),阶段10 · 17(本地稀少) attention)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释一下Jamba街区里的三个原始人 Transformer 层, Mamba 层, MoE 和1: 7: 甚至是中间配方。
- 描述 SSM 重现在高层次上是什么样子, 以及它为什么允许恒定记忆 inference.
- 计算 KV cache Jamba 模型的足迹在256k上方,与什么是纯-Transformer 模特儿会需要的
- 说明三种Mamba-3创新(富集带分解、复杂估值状态更新、MIMO)和问题每个目标。

<a id="the-problem"></a>

## 问题

Attention 以序列长度表示。国家空间模型是线性。这种差异的化合物为256k tokens, 一个 Transformer attention 地图是每头65B项; SSM 的经常性状态是固定大小, 不论序列长度 。

纯性 SSM 模型( Mamba, Mamba-2) 匹配 Transformer perplexity 直觉:SMS将历史压缩到一个固定状态,而当历史漫长时,信息就会泄漏。 Attention 记得一切,但支付二次费用。

显而易见的修补方法:使用两个。 Transformer 精确重命名要紧的层 。 在别处使用 SSM 层 。 标出比例 。 Jamba 是首个生产级模型, 用来以比例( 52B 总计、 12B 激活、 256k 上下文、 单 80GB) 运出该混合配方 GPUJamba 1.5将家庭总数扩大到398B/94B活动。 Mamba-3(ICLR 2026)是目前最佳的纯SSM基线,可以围绕混合体重建。

这堂课读了这三篇论文 并产生了“选择正确比例”的心理模式

<a id="the-concept"></a>

## 概念

<a id="an-ssm-in-one-page"></a>

### 一页中的 SSM

国家空间模型处理序列 `x_1, ..., x_N` 通过固定大小状态 `h`:

```
h_t = A h_{t-1} + B x_t
y_t = C h_t
```

每一步,国家都会通过线性动态演变 `A`输入 `B x_t`输出 `C h_t`. `A, B, C` 可以学习。 注意关键属性: 计算 `y_t` 仅需要 `h_{t-1}` 和 `x_t`,没有更早的 `x`。记忆是恒定的。 Inference 是 O(1) / token.

建模质量的秘诀是 `A`S4 (Gu 2021)使用了结构严密的矩阵,可以在培训期间作为一个长期的演变过程加以有效评估。 `A, B, C` Mamba-2 (2024年)进一步简化了结构。 Mamba-3 (2026年)在特定地方增加了复杂性。

关键属性: decoder LLM, SSM 层是用于替换 attention 平面, 具有固定大小的每层状态, 而不是增长 KV cache.

<a id="the-jamba-block"></a>

### Jamba 街区

Jamba区块间断层根据两个数字:

- `l`: 该 attention- Mamba比率。 Jamba 使用 `l = 8`,意指 1 Transformer 每7 Mamba 层( 7 Mamba + 1) Attention = 每组8层)。
- `e`: 该 MoE 频率。 Jamba 使用 `e = 2`,意思是其他各层都适用 MoE.

块内的层序列 :

```
M  M  M  M  M  M  M  A    (7 Mamba + 1 Attention)
|  M  |  M  |  M  |  M    (where | marks MoE applied)
```

Jamba 区块各有8层。 在4个区块深处(共32层), 你得到28 Mamba 和 4 Attention 16种用途 MoE.

<a id="why-the-17-ratio"></a>

### 1:7的比例为何

AI21 流放: attention- 到曼巴给最好的 perplexity-每-parameter 和内文回顾 在他们的长文的变异?

- 太过份了 attention (1:1):质量上升,但内存和速度下降。
- 太少了,太小了,我... ... attention (1: 15): 记忆力很强,但内文检索失败。
- 甜点:1: 7或1: 8。

直觉: Transformer 层处理精确的回溯和状态跟踪。 Mamba 层处理廉价的处理量 。

<a id="positional-encoding"></a>

### 位置编码

Mamba层本身就具有定位意识(通过重现)。 Attention 原始 Mamba 混合体中的层没有使用 RoPE - 提供SSM层位置信息。 RoPE 至 attention 用于长文本概括的层,基于经验性长文本的拼接后改进 evaluation.

<a id="the-memory-budget"></a>

### 记忆预算

Jamba-1形状(32层:28 Mamba+4) Attention,隐藏 4096, 32 attention 头( H) :

- KV cache (attention 仅层数 : `2 * 4 * 32 * 128 * 256k * 2 = 8.4 GB` 在256k BF16。 只有4个 attention 分层贡献。
- SSM 状态 : `28 * hidden * state_size` 每 token 前缀, 但这是每层的固定大小, 不是以序列长度缩放 。 典型 Mamba 状态为 16 feature,隐藏4096: `28 * 4096 * 16 * 2 = 3.7 MB` 总计。

与纯度相比 Transformer 在32层,同样的隐藏,满满的MAHA 在32个头: `2 * 32 * 32 * 128 * 256k * 2 = 128 GB` 256k BF16。 KV cache。即使对照2024年大多数模型使用的GQA(8)基准(`2 * 32 * 8 * 128 * 256k * 2 = 32 GB`Jamba的1比7混血体在16GB还小2倍。

这就是AI21的意思,“256k 在单80GB上的背景 GPU." 该 KV cache 纯净的麦加, Transformer 不适用;即使GQA基线也没有任何空间 weights 和激活; Jamba 做的。

<a id="mamba-3-the-pure-ssm-baseline-in-2026"></a>

### Mamba-3:2026年纯SSM基线

Mamba-3(ICLR 2026,arxiv:2603.15569)在纯性SSM方面引入了三项创新:

1. **指甲性脱解。** 将 Mamba-2 中的 Euler-metrodization 替换为更直观的复发。 在核心复发中,像革命一样的行动适用于国家投入,而不是作为外向变换。 `x_t`.

2. **复杂估值的状态更新。** 先前的曼巴斯将州矩阵从综合(S4)降为实际对角(Mamba),降为缩放身份(Mamba-2)。 Mamba-3 重新添加复杂的值,相当于一个依赖数据的旋转键 embedding 这恢复了州级追踪能力 与以前实际估价的简化成本相比

3. **多投入多产出预测。** 而不是每个...feature 利用矩阵价值预测,改进模型能力 inference- 时间硬件的使用,而不增加解码。

1.5B时 parametersMamba-3提高了下游平均精度,比Gated DeltaNet增加了0.6个百分点;MIMO变式增加了1.2,共增加1.8点。 在同一州中,Mamba-3与Mamba-2匹配,占州的一半。

Mamba-3还没有大规模地以混合生产方式运输——但它显然是下一个Jamba级模式的SSM方面的候选人。

<a id="when-to-reach-for-a-hybrid"></a>

### 何时能找到混血儿

混合体在下列情况下获胜:

- 上下文足够长 纯净 Transformer KV cache 变成痛苦 (64k+)。
- 任务混合了短程结构(对特殊保障机制有利)和远程召回(需求) Transformer).
- 你想在单人...GPU 内存预算 Transformer KV cache 独自一人是不合适的。

混合体在下列情况下丧失:

- 上下文很短(16k以下)。 Transformer 没事了
- 任务需要无处不在 attention (深度推理、多文档交叉参照)。 attention 混血体的层层很痛
- 你正在向万亿 -parameter 边境模型,纯净...Transformer + 司法协助+ MoE (DeepSeek-V3风格) 正在赢得能力竞赛。

<a id="the-competitive-landscape"></a>

### 竞争环境

| 模型 | Family | 规模 | A. 独一索赔 |
|-------|--------|------|-------------|
| Mamba-2 | 纯 SSM | 3B | 线性时间, 恒定内存 |
| Jamba | hybrid | 52B/12B | 256公里80GB |
| Jamba 1.5 大号 | hybrid | 398B/94B | 企业级长文本 |
| Mamba-3 | 纯 SSM | 1.5B(纸张) | 恢复状态跟踪 |
| DeepSeek- V3 电磁波 | pure Transformer + MoE | 671B/37B | 边境能力 |

2026年的风景:纯净Transformer MoE Mamba-3的州轨胜算可能会降低混合比率(更多SSM,更少) attention在下一代。

```figure
swiglu-ffn
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 是一个混合结构的内存计算器。Transformer 和隐藏大小/层数配置,它计算:

- KV cache 在目标背景下。
- SSM 国家记忆。
- 一系列模型形状在 N 上下文的总内存。

计算器支持 :

- Pure-Transformer 基线(KV cache 与 N 一起生长。
- 强巴式1: 7混血儿
- 纯 SSM (无) KV cache (见A/AC.96/10,第6段)。

数字直接来自Jamba-1和Jamba-1.5文件,用于发表形状,并推断出假设变体。

实际部署的整合考虑:

- 大部分生产 inference 服务器vLLM, SGLang支持 Jamba 和 Mamba 。 请检查具体版本 。
- 在 256 k 上下文中, Jamba 的内存优势出现在同时请求的传输中。 在相同的 VRAM 中, Jamba 序列比 Transformer 顺序。
- Mamba-3作为一个独立模型,尚未进行生产——研究预览1.5B。

<a id="ship-it"></a>

## 交付成果

这个课程产生 `outputs/skill-hybrid-picker.md`。根据工作量说明(全文、任务组合、记忆预算),它建议使用纯度 Transformer一种Jamba式的混合体, 和纯粹的SSM, 明确解释记忆和质量权衡。

<a id="exercises"></a>

## 练习

1. Run `code/main.py` 要计算 KV cache 32层纯度为 256K 上下文 Transformer (隐藏于4096年, 32 个头) 和相同形状的 Jamba-1 混合体。 校验 AI21 纸质索赔的 ~ 8x 内存减少 。

2. 修改计算器,以模拟1: 3混合( 4 Mamba: 1) Attention和1:15混合体(14 Mamba:1) Attention绘图 KV cache 相对于比率。 KV cache 等于 SSM 状态记忆 ?

3. 阅读Jamba文件第3节(arXiv:2403.19887)。解释为什么AI21使用Mamba-1而不是Mamba-2,尽管Mamba-2的速度更快。提示:混合烧蚀部分对此做了记录。

4. 计算 parameter 间接费用 MoE- Jamba 1.5大(共计398B,正在运行)。 DeepSeek-V3(37B/671B),并解释为什么Jamba的建筑推高了活动比率。

5. 读取 Mamba-3 纸张第3节(arXiv:2603.15569),在三句中解释为什么一个复杂估值的状态更新等同于一个依赖数据的旋转旋转键 embedding将答案与第7阶段挂钩 RoPE 推断。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 国家空间模型(SSM) | "重现固定状态" | 具有学习重现的层 `h_t = A h_{t-1} + B x_t`; 常数内存 token |
| 选择性的 SSM | "曼巴的诡计" | 依赖数据A、B、C parameters 在线性时间给模型带像格子的选择性 |
| Attention- 与曼巴比率 | "有多少个" attention 层" | 在Jamba, `l = 8` 图1 attention 每7 Mamba 层一层 |
| Jamba 区块 | "八层组" | One attention + 7 Mamba+ + 组合键 MoE 候补职位 |
| SSM 状态 | 隐藏缓冲 | 替换 KV cache Mamba 层 |
| 256k 上下文 | "Jamba的旗舰号" | 序列长度 Jamba-1 符合单 80GB GPU; 纯 Transformer 无法达到此大小 |
| Mamba-3 | "2026年纯SSM" | 目前最佳的纯 SSM 结构,具有复杂的状态+MIMO;基线混合体围绕重建 |
| MIMO | "多投入多产出" | Mamba-3 创新,采用矩阵估值预测,而不是每至feature |
| 指数- 诱捕分离 | "曼巴 -3的复发" | 更清晰的复现 包含 Mamba-2 的 Euler- 方法分离 |
| 混合结构 | 混合 attention 和SSM", | 任何中断的模型 Transformer 和 SSM 层; Jamba 是生产原型 |

<a id="further-reading"></a>

## 进一步阅读

- [Lieber等人——Jamba:混合体 Transformer- 曼巴语言模型(ARXiv:2403,1986年)](https://arxiv.org/abs/2403.19887) 原始的Jamba纸、比例、256k上下文索赔
- [AI21 - Jamba 1.5:混合体 Transformer- 天平上的曼巴(arXiv:2408.125.70)](https://arxiv.org/abs/2408.12570) 扩大的家庭,398B/94B和12B/52B公开发布
- [古、道-曼巴:用选择性国家空间进行线性时间序列模型(arXiv:2312.00752)](https://arxiv.org/abs/2312.00752) - 选择性的SSM文件Jamba以
- [Dao, Gu- Mamba-2 (arXiv:2405.21060)](https://arxiv.org/abs/2405.21060) - 简化结构化国家空间继承程序
- [Lahoti等人-Mamba-3(arXiv:2603.15569,ICLR 2026)](https://arxiv.org/abs/2603.15569) - 复杂价值国家,MIMO,2026年纯SSM边界
- [古等人——以结构化国家空间有效模拟长序列(arXiv:2111.00396)](https://arxiv.org/abs/2111.00396) S4文件 SSM基因学的起点 LLMs
