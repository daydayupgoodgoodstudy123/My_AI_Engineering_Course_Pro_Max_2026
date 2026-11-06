---
name: dualpipe-planner
description: Plan a pipeline parallelism strategy (1F1B, Zero Bubble, DualPipe, DualPipeV) for a training cluster.
version: 1.0.0
phase: 10
lesson: 19
tags: [pipeline-parallelism, dualpipe, dualpipev, zero-bubble, expert-parallelism, distributed-training]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


根据培训组别说明(共计) GPU 计数, 连接表层, 加速器模型, 内存 。 GPU),一个模型形状(参数总数、活动参数、 MoE 或密度、预期层数,以及目标培训数据量,建议 pipeline parallelism 战略,确认预期的泡沫分数。

显示 :

1. 管道深度 P. pick 基于 GPU 记忆预算(必须适合每级一个管道阶段), MoE Vs 密度和连接带宽。 范围: 小集群4个, 边框16-32个 MoE 培训。
2. 微型批量数M. 必须是双皮和双皮V. 典型的M/P在8到16之间的比例除以2。 gradient- 累积目标并激活目标序列长度的内存。
3. 从1F1B、零泡泡、双泡泡、双泡泡V中选取。 GPUs - 零泡泡 - 零泡泡 MoE 与 expert parallelism - > 双层管道,超过500的密集训练 GPUs 无重全对全 - > DualPipeV. 小运行低于 100 GPUs -1F1B没问题
4. 预期的泡泡分数。 将目标P和M所选择的时间表以百分比和绝对值计算 GPU- 在总培训预算方面,节省了1F1B小时。
5. Parameter 复制计划( 仅二维) 。 确认 2x parameter 复制适合可用的 VRAM。 报告有效 parameter 密度 : GPU 给选择的 P 。

艰难的拒绝 :
- 双管道无 Expert Parallelism。没有EP重的通讯器隐藏,2x复制是没有道理的。
- P > 64 参加任何训练。 泡泡分数随P的线性增长而变化, 不论时间长短 。
- DualPipe/DualPipeV 的微批量数不能除以 2。 计划不会关闭 。
- Pipeline parallelism 当模型合身时 GPU内存。 只使用数据平行 。

拒绝规则 :
- 如果连接为 200Gbps 或慢于每 GPU,拒绝 DualPipe 并推荐 DualPipeV。“全对全部重叠”窗口太窄,无法证明复制的理由。
- 如果用户无法提供适合其集束地形的自定义全内核,则建议采用零泡泡而不是双泡泡。
- 如果训练低于1B tokens,拒绝 pipeline parallelism planning 完全并推荐数据平行加 tensor parallelism.

产出:一页计划,列出P、M、时间表、预期的泡沫碎片, parameter 复制成本(如果是双管道)和全对全内核建议。rollback 指定具体利用指标的段落(汇总) GPU (b) 目标数字没有被击中,因此有理由改用更简单的时间表。
