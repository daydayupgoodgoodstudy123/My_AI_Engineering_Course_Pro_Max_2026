<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="dualpipe-parallelism"></a>

# DualPipe 并行

> DeepSeek- V3在2 048 H800号公路上接受培训 GPUs 与 MoE 跨节点专家全面通信费用 GPU- 通讯时间为每1小时 GPU- 计时时间 GPUs 一半时间闲置。DeepSeek, Dec 2024) 是一条双向管道, 与前向和后向计算重叠。 泡泡下降, 吞吐量攀升, 并保留两个模型-parameter 印本( 给出名字的双份) 曾经很便宜 Expert Parallelism 无论如何,这堂课已经将专家分散到各个级别。 这是学习式的体验, 展示双Pipe实际上所做的一切, 以及为什么海洋 AI Lab 的双PipeV 改进会降低 2x 。 parameter 代价以牺牲一个稍稍收紧的泡沫。

**类型:** 学习
**语言:** Python (stdlib, 时间表模拟器)
**先修要求:** 第10阶段 · 05(分配培训、FSDP、深层采样),第10阶段 · 14(开放型建筑和 MoE)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 命名 DualPipe 前向块的四个组件, 以及为什么每个部件都有自己的重叠窗口 。
- 解释管道泡沫问题的规模, 以及“无泡沫”在实际中和营销中意味着什么。
- Trace a 8个PP级和16个微型蓄水池手表,确认前向和反向流,填充彼此空闲的空位。
- 说明双PipeV(海洋AI实验室,2025年)的权衡结果:下降 2x parameter 以稍大一点的泡沫为代价复制 Expert Parallelism 不活动 。

<a id="the-problem"></a>

## 问题

培训a 671B MoE 2k H800 型号 GPUs 有三个复杂的瓶颈:

1. **记忆压力** 每个 GPU 持有一个模型的片段。 启动记忆在顺序 8K 上横跨 61 层, 在 128 个头上是巨大的。
2. **管道泡沫。** Traditional pipeline parallelism 叶子(1F1B) GPUs 等待舞台输入时闲置或 gradient。在8个阶段,大约12% GPU 时间可以是泡泡 即使1F1B排期。
3. **交叉节点全对齐** MoE 与 expert parallelism 将专家分散到各节点 forward pass 触发全部发送 tokens 和他们的专家, 和另一个组合。 GPUs 这很容易变成 1:1 的计算对comm比率。

每种办法都有不同的解决办法: gradient 用于内存的关卡, Zero Bubble (海洋 AI Lab, 2023) 用于管道泡泡、 专家- 平行的通气内核 。 DualPipe 所做的是让它们一起玩。 时间表在单个前向块中进行计算和通气, 同时从管道两端输入微型插管, 并使用由此得出的时间表将全部都隐藏在计算窗口中 。

所报告的结果:管道泡沫接近消除,95%以上 GPU 利用情况 DeepSeek-V3是14点8Ttoken 训练跑。

<a id="the-concept"></a>

## 概念

<a id="pipeline-parallelism-refresher"></a>

### Pipeline parallelism refresher

在 P 设备上拆分 N 级模型 。 `i` 持有层 `i * N/P .. (i+1) * N/P - 1`。微批次通过0号设备向P-1,然后从P-1向后流到P-1。每个设备只有在前一个设备发送输出时才能开始前台,并且只有在下游设备向上端发送时才能开始后端 gradient.

GPipe (Huang等人,2019年) 一次安排一次微型批量,浪费最多 GPU 1F1B(Narayanan等人,2021年) backward passes 零泡泡(Qi等人,2023年) backward pass 分为两个部分——后向投入(B)和后向投入(B)weights (W)——并安排它们填充泡沫。在零泡泡之后,管道几乎紧凑。

DualPipe是下一步。它在上面增加了两个想法:

<a id="idea-1-chunk-decomposition"></a>

### 设想1:块分解

每个前方块分为四个组成部分:

- **Attention.** Q/K/V预测, attention输出投影
- **全对全调** 发送交叉节点通讯 tokens 给他们的专家。
- **MLP 车站长** 该 MoE 专家计算。
- **全对全组合。** 交叉节点交流 将专家产出带回来

向后增加块 gradient 每一个版本。 DualPipe 计划它们, 以便所有发送都与 attention 计算下一个块, 并且全对全组合会与 MLP 计算以下块平行进行 。

<a id="idea-2-bidirectional-scheduling"></a>

### 设想2:双向时间安排

大部分输油管的排程是从0级向P-1级注入微型蓄水池。双管道的排气槽从两极端注入微型蓄水池。 第0阶段从那里看到前方微型蓄水池; 第1阶段也从那里看到前方微型蓄水池。 这两个流在中间交汇。

要成功,设备 `i` 必须保持两个管道的早期层 `i` 和末端管道层 `P - 1 - i`。这是双层管道的“双层”部分:每个设备都保留它需要使用的模型层的两份副本(每个方向一份)。 DeepSeek-V3的尺码,这是2x parameter 复制成本。 这是负担得起的,因为 Expert Parallelism 已经展开 MoE 专家如此瘦小, 复制了两次非专家层 是小土豆。

关键的是,向一个方向的前行流和向另一个方向的后向流完全重叠,而泡沫则在单一方向上。泡沫消失了。

<a id="a-hand-traced-schedule"></a>

### 手动追踪时间表

考虑 P = 4 级, 8 个微型蓄水池, 向前 4 / 4 个反向。 时间向右移动; 行是设备排。

```
           Time →
rank 0:  F1 F2 F3 F4  F5R F6R F7R F8R  B1 B2 B3 B4  ...
rank 1:     F1 F2 F3  F4/F5R F6R F7R   B1 B2 ...
rank 2:        F1 F2  F3/F5R F4/F6R    B1 ...
rank 3:           F1  F2/F5R F3/F6R    ...
```

读取“ F4/ F5R” 符号 : 1 级正在运行, 向前是微批4 ( 左对右在输油管中) , 向前是微批5 ( 右对左) 。 这就是“ 双向” 的意思 。

第2级的交叉流重叠得更快,在0级和P-1级则最晚重叠。在稳定的中段时间里,每级的X向前与Y向后相重叠。计算繁忙。 forward pass 隐藏在后向计算中。 全部组合都隐藏在前向计算中。 泡泡被挤出 。

<a id="bubble-accounting"></a>

### 泡沫核算

标准 1F1B 管道泡泡(每级时间浪费):

```
bubble_1F1B = (P - 1) * forward_chunk_time
```

零泡泡的精细化使其下降, 但不会降至零。 在稳定的阶段, 如果微批量的计算比输油管深度高出2倍, 则双泡泡会为零 。 在稳定阶段之外( 稳定阶段) 。warmup 以及冷却),有一些泡沫,但是它不会随着微型水桶的数量而增长——这是纸上强调的一个关键属性。

营销术语 : “ 无泡沫” 。 从技术术语来说: 泡沫不会随着微批量的计算而增长。 AI Lab 的后续分析( DualPipeV / Cut- half) 显示只有当 Expert Parallelism 并不是瓶颈;在由欧洲议会驱动的 " 全面到所有 " 的情况下,总是存在着一些时间安排上的妥协。

<a id="dualpipev--the-refinement"></a>

### 双PipeV——改进

AI实验室(2025年)观察到2架 parameter 当 EP 通信重叠不是关键时, 复制是浪费的。 它们的双向射入会折叠成一个“ V 形状” 列表 parameter 复制。 气泡略大于 DualPipe 的, 但内存的节省量很大 。 DeepSeek 采用双PipeV作为EP的开放源码执行模式。

权衡:

| Feature | DualPipe | DualPipeV | 1个F1B | 零泡泡 |
|---------|---------|-----------|------|------------|
| 每个设备的参数副本 | 2 | 1 | 1 | 1 |
| 泡泡与微型浴缸 | constant | 小增长 | grows | grows |
| 计算通讯重叠 | full | partial | minimal | partial |
| 使用时 | EP-heavy MoE | 密度或EP-光线 | 基线 | 任何管道 |

<a id="what-it-means-for-a-148t-token-run"></a>

### 14点8T是什么意思?token run

DeepSeek-V3的训练前消耗了14.8T tokens 2,048 H800时 GPUs 约2.8米 GPU幼稚的1F1B,它们会失去12-15%的气泡——340-420K GPU- 小时,足够训练一个70B的模型。 DualPipe 回收了大部分。没有内部日志,很难直接量化贡献,但文件中的主张超过95% GPU 整个培训的平均利用率。

较小运行量( 1k 以下) GPUs与总成本相比,输油管泡沫较小,而密集的模范培训很少会遇到全面瓶颈。 MoE 在多千人培训 GPU 规模,这是有效的要求。

<a id="where-it-sits-in-the-stack"></a>

### 堆放着它的地方

- 补充 **FSDP** (第10阶段 -05年) parameters 横跨列; 两极Pipe 计划跨列的计算。 它们合并 。
- 与 **ZeRO-3** gradient 重复复制的簿记需要和ZeRO的碎片合作 gradients.
- 需要 **定制全对全部内核** 专为特定组群地形而调 DeepSeek开源核心是参考执行。

```figure
expert-capacity
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 是一个管道排程模拟器。 它需要 `(P, n_micro_batches, schedule)` 并打印了1F1B、零泡泡、双泡泡和双泡泡V的每个稳定阶段的使用情况。 这是一个教学工具——数字与文件中的质量要求相符,它们不是关于产量加速度的索赔。

模拟器的价值: 用不同的 P 和 微批数来运行, 并观察 1F1B 的泡泡分数是如何增长的, 但不是 DualPipe 。

实际训练的融合考虑:

- 选择一个管道平行深度, 将它完全分割成你的微批量数。
- 保证你的双向双向双向组合网格 DeepSeek内核是参考。
- 预计第一次在时间表上燃烧一周调试时间。 记账方式很混乱 。
- Monitor GPU 双Pipe的好处是收紧了排泄物。

<a id="ship-it"></a>

## 交付成果

这个课程产生 `outputs/skill-dualpipe-planner.md`根据培训组别说明(GPU 计数, 地形学, 连接, 模型形状), 它推荐 pipeline parallelism 战略, 计划使用算法, 以及目标比例的预期泡泡分数 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py` 在 `(P=8, micro_batches=16, schedule=dualpipe)` 和 `(P=8, micro_batches=16, schedule=1f1b)`。计算 GPU 使用差异,表示为已恢复 GPU每百万小时 tokens 培训。

2. 绘制计划表 `(P=4, micro_batches=8, schedule=dualpipe)` 手动标记。 标记每个时段, 用微批量 ID 和方向。 确定第一个空格 。

3. 阅读图5 DeepSeek- V3 技术报告(arXiv:2412.19437). 确定双管道前方块内所有到所有发送的重叠窗口。 请解释计算时间表如何隐藏它 。

4. 计算 2x parameter 70B型高密度、P=8输油管级和671B型双管顶部 MoE 具有 P=16 管道阶段的模型。 显示为什么 MoE 案件管理费用的比例较小(大多数为 parameters 是专家, 被碎片 跨越一个大型的EP小组。

5. 将双向定位比对齐梅拉( 2021年的双向调度程序) 。 DualPipe 补充道, 以纸张第 3. 4 节作为参考, Chimera 没有这两个特定属性 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 管道气泡 | "每个军阶的闲暇时间" | GPU 循环因管道阶段等待输入或 gradient |
| 1个F1B | "输油管故障计划" | 一个前向/ 一个后向间断排程; 基线双位节拍 |
| 零泡泡 | "海神2023实验室" | 向后拆为 B( 输入) gradient)和W(续)weight gradient;几乎完全收紧管道 |
| DualPipe | "DeepSeek-V3计划" | 双向管道 + 计算comm重叠; 气泡不会随着微批量数而增长 |
| DualPipeV | "半个" | V 形状精细, 降低 2x parameter 以稍大一点的泡沫为代价复制 |
| 块 | “管道工程单位” | 前进或 backward pass 一个微型批次通过一个输油管阶段 |
| 全部发送到全部 | 发送 tokens 致专家" | 交叉节点通信线路 tokens 所分配费用 MoE experts |
| 全部对全部组合 | "把专家产出带回来" | 在 MLP 后收集专家输出的交叉节点通讯 |
| Expert Parallelism (欧 元) | "专家横跨 GPUs" | Shards MoE 跨级专家如此不同 GPUs 安排不同的专家 |
| Pipeline Parallelism (PP) 国家 | "横穿云雾 GPUs" | 不同级的碎片模型层; 维度 DualPipe 计划 |
| 泡泡碎片 | 已经过时 GPU 时间" | (泡泡)_时间/总计_时间; 分数 DualPipe 驱动向零 |

<a id="further-reading"></a>

## 进一步阅读

- [DeepSeek- 亚历克斯 DeepSeek-V3 技术报告(arXiv:2412.19437),第3.3.2节和图5](https://arxiv.org/abs/2412.19437) - 主要的双管道参考
- [DeepSeek - 双管道 GitHub repository](https://github.com/deepseek-ai/DualPipe) - 开放源码参考实施,包括双源 PipeV(半个)模式
- [Qi等人——零泡泡 Pipeline Parallelism (arXiv:2401.10241,海洋AI实验室2023)](https://arxiv.org/abs/2401.10241) - 零泡泡的前身
- [AI 海洋实验室——没有双层平台,两层平台会更好。](https://sail.sea.com/blog/articles/63) - DublePipeV分析,该分析为 DeepSeek'EP- 关闭模式
- [纳拉亚南等人——管道/1F1B(ARXiv:1806.03377,2018-2021)](https://arxiv.org/abs/1806.03377) - 1F1B表比对
- [黄等人——GPipe(arXiv:1811.06965,2018年)](https://arxiv.org/abs/1811.06965) - 原创 pipeline parallelism 纸张和泡沫问题
