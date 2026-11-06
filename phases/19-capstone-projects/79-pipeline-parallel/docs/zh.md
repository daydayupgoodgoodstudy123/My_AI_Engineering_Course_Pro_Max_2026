<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="pipeline-parallel-and-bubble-analysis"></a>

# 流水线并行与流水线气泡分析

> Tensor parallelism 将矩阵分成数级。 Pipeline parallelism 将模型分成一个层次, 每层一个阶段。 微小插管通过管道。 开始和结束的空位是泡沫; 最小化的是整个飞行器 。

**类型:** Build
**语言:** Python
**先修要求:** 第19阶段C轨道课程42-49
**时间:** ~90分钟

<a id="learning-objectives"></a>

## 学习目标

- 将连续模式分为N级,并模拟N级的前方管道。
- 使用 GPipe 排程( 仅往前填充, 然后向后) 来计算管道中的 M 微插管, 并计算泡泡的分数 。
- 对比一下威震天-LM和管道Dream中 的气泡
- 防御阶段任务:每阶段计算等值比等值重要 parameter 每个阶段计数 。

<a id="the-problem"></a>

## 问题

70B号parameter Fp16模型需要140GB parameters 一个人,没有消费者 GPU 拿着它,ZeRO-3碎片 parameters 跨行, 但仍然需要每个级别来将每一步的整层相加, 每层支付对数跳。 管道平行使用不同的路径: 将模型切入到 N 级, 并给每层设置一个阶段 。 向前第 1 级完成 0 级并启动 tensor 以第1级; 第1级运行第2层,手排第2级; 等。 向后向向向向向移动。 内存会直线下降, 因为每个级别只持有一个阶段; 计算是顺序的, 这就是泡沫问题 。

泡泡是管道开始( 等待第一小批微巴进入最后阶段) 和末( 等待最后一批微巴排出水流回流) 的闲置时间。 在M微巴和N级, 每一个阶段的泡泡分数为( N-1) / ( M+N-1) 。 在 M= 8, N=4 占27%。 在 M=64, N=4 占4.5%。 当您每步有许多微型小巴时, 气泡会缩水, 这意味着每个微巴小的气泡占到27% 。 batch sizes,这是驱动微批量设计的限制。

<a id="the-concept"></a>

## 概念

```mermaid
flowchart LR
  R0[rank 0: stage 0 / layer 0] --> R1[rank 1: stage 1 / layer 1]
  R1 --> R2[rank 2: stage 2 / layer 2]
  R2 --> R3[rank 3: stage 3 / loss]
  R3 -.backward.-> R2
  R2 -.backward.-> R1
  R1 -.backward.-> R0
```

<a id="gpipe-schedule"></a>

### GPipe 计划

在开始任何向后, 以所有 M 微插头填充管道; 然后倒流到反向。 每个微插头的动作必须一直保持到向后, 所以随着 M. 向前采取 M+N-1 周期, 记忆会直线增长, 后向需要另一个 M+N-1 周期。 每阶段有用的工作是 2M 周期; 每阶段的泡泡周期是 2N-1 周期 。 当每个向前和向后都占据一个单位的时间时, 泡泡的分数是 ( N-1) /( M+N-1 ) 。 抓取 M 的比 N 还要大得多 隐藏气泡 。

<a id="1f1b-schedule"></a>

### 1F1B 计划

中间线: 当微插盘向前到达最后阶段, 开始向后并让它向后流。 时间表将每个阶段的前面和后面交替一个。 泡泡仍然是N-1, 但激活记忆是受管道深度而不是微插盘数的约束。 生产管道使用 1F1B (Megatron, PipeDream) 。 课程首先应用 GPipe, 因为它比较简单, 并且用 1F1B 来练习 。

<a id="why-equal-compute-per-stage-matters"></a>

### 为什么计算每个阶段都一样重要

如果第0阶段需要50毫秒,第1阶段需要100毫秒,则每个周期都关在第1阶段,其他阶段每周期需要50毫秒等待第1阶段的释放。 parameter 数错了轴: a transformer计算为 attention 加上每层的 MLP, 和 embedding 层层有多个 parameters 阶段性任务应该等于每个阶段的 FLOPs, 不是 weights 每一阶段。

<a id="microbatch-versus-batch"></a>

### 微批量对批量

输油管运行M型B型微型插管。 batch size 是 M*B. 任务 gradient 管道步骤的结尾处是 gradient 合计M*B例。泡泡碎片取决于 M; 优化器看到 M*B. 调试M系指将泡沫(以高M值降低)与每微积分内存(以高M值高的活性内存对GPipe值)进行交易。

```figure
cd-pipeline-bubble
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- `PipelineStage`: 一个小 `nn.Module` 并保持一个阶段 parameters 和曝光的, `forward(activation)`.
- `Pipeline(stages, num_microbatches)`:在模拟阶段使用模拟的墙上时钟对GPipe时间表进行编织。
- `bubble_fraction(num_stages, num_microbatches)`:闭式(N-1)/(M+N-1)。
- 4级演示 打印每件微小批 trace 和测量的泡沫分数。

运行：

```bash
python3 code/main.py
```

输出: 一种按微小批量排列的甘特图, 以及相对于封闭式预测的泡沫百分比 。

<a id="production-patterns-in-the-wild"></a>

## 野生生物的生产模式

三种模式使管道的强度硬化,足以平行地进行运输。

**Activation checkpointing 配有管道的对** 利用M微巴棒在GPipe上飞行,激活内存是M乘以1微巴。 Activation checkpointing 以内存交换后向值, 组合可以让管道被拖长。

**阶段余额是衡量的,而不是假设的。** 生产团队通过剖析测量,测量目标硬件上的实际每层计算(FLOPs和墙上时数),然后通过测量进行分割。 `--num-layers-per-stage` 标记接受列表, 允许在每层费用不同时进行不均层计数 。

**发送记录表必须避免僵局。** 一条管道在接收电线上的僵局之前就可发送到每个阶段。 标准修补是间断: 平级先发送, 调序后发送, 奇级调序后发送。 课程排程排行表排列明确, 以便显示模式 。

<a id="use-it"></a>

## 实际应用

生产模式:

- **Megatron-LM.** 比例线平行管道的参考。 使用 1F1B 并支持 tensor +管道+数据平行组合。
- **深丝管道。** 与ZeRO结合;ZeRO-1+管道是最大开放型号的共同组合。
- **PyTorch Pipe.** 该 PyTorch- 天然管道包装, 建在 `torch.distributed.pipeline.sync.Pipe`.

<a id="ship-it"></a>

## 交付成果

80个课程,每个阶段 parameter 碎片在碎片中 checkpoint81课是终端至终端演示的DDP+ZeRO+管道(精神上;演示将模拟管道运行时间)。

<a id="exercises"></a>

## 练习

1. 执行 1F1B 并验证气泡分数符合 GPipe, 但激活内存被绑定 。
2. 以测量的墙时点来描述更深模型和再平衡阶段的每个阶段的实际时间。
3. Add gradient accumulation 穿过管道的微型卫生间检查 gradient 等于 gradient 的全包。
4. 输油管对齐 activation checkpointing 并测量内存下降与计算成本。
5. 将管道与DDP合并(每个管道级都通过数据平行组复制),并通过2D时间表解释理由。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 管道 | 深度上的模型平行 | 一级,启动 流向阶段 |
| Bubble | "小便闲暇时间" | 开始时的步骤+结束,有些阶段没有工作 |
| Microbatch | "批量的残渣" | 一个前向/后向单位;随着M的增长,泡沫会缩小 |
| GPipe | "然后排水" | 向后移动前所有 M; 高激活内存 |
| 1个F1B | 休假计划 | 每个阶段向后一个; 捆绑的激活内存 |

<a id="further-reading"></a>

## 进一步阅读

- [黄等人,GPipe:对巨型神经网络的有效培训](https://arxiv.org/abs/1811.06965)
- [纳拉亚南等人,管道:通用 Pipeline Parallelism 培训](https://arxiv.org/abs/1806.03377)
- [威震天- LM 管道平行文档](https://github.com/NVIDIA/Megatron-LM)
- 第19阶段 76课 - 发送/检索原始程序
- 第19阶段 78课 - ZeRO正对齐,而且往往合并
