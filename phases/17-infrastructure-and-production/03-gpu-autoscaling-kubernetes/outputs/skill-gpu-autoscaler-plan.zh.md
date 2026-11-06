---
name: gpu-autoscaler-plan
description: Design a three-layer GPU autoscaling plan (Karpenter + KAI Scheduler + application signals) for a Kubernetes-based LLM serving cluster. Diagnose DCGM_FI_DEV_GPU_UTIL traps and partial-allocation failures.
version: 1.0.0
phase: 17
lesson: 03
tags: [kubernetes, gpu, autoscaling, karpenter, kai-scheduler, hpa, dynamo-planner, llm-d]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


组群表(节点, GPU 类型、 NVLink 域、工作量形状(TP/PP配置、平均同值货币、断裂系数)和 SLO (TTFT P99, goodput),产生一个三层 autoscaling plan.

显示 :

1. 图层 1 - Karpenter 节点pool. 指定 `instance-type`, `capacity-type` (按需/点/预留) `consolidationPolicy` (必须) `WhenEmpty` 与 `consolidateAfter: 1h` 用于 GPU 不包括非GPU 工作量, 以及 KAI 调度器选择的标签 。
2. 图层2 - KAI 调度政策。 是否要求黑帮排队( TP/ PP > 1) 。 定义地形限制( NVLink 域、 架子、 区) 。 指定生产排队等级和先发制人规则与培训租户的顺序 。
3. 图层 3 - 应用程序自动标尺。 选择信号: 队列深度 prefill- 工作量很大 KV cache 用于有解码、复合和 goodput 混合。 禁忌 `DCGM_FI_DEV_GPU_UTIL` 解释原因
4. 分拆。如果使用第17阶段,则分拆17个阶段。 prefill/解码,指定单独的 HPA - 队列深度信号 prefill 游泳池, KV使用信号 解码池。
5. 热源缩放。 基于 P99 TTFT 限制和观察的冷启动时间(节点提供+模型负荷), SLO 关键路径的最低可变复制件。
6. 监测。 仪表板的计量:每复制队列深度、每复制KV的利用率、节点备抵等候时间、帮派排队延后计数、卡彭特合并事件。

艰难的拒绝 :
- 建议HPA `DCGM_FI_DEV_GPU_UTIL`。拒绝将队列深度和 KV 的命名作为正确的信号。
- Leaving `consolidationPolicy: WhenEmptyOrUnderutilized` a 用于 GPU 拒绝并引用工作流动风险
- 忽视TP/PP工作量的帮派安排。 拒绝部分分配是反烧伤方案。

拒绝规则 :
- 如果组只有一个 GPU 用户首先需要管理好的服务器(第17 · 02阶段),
- 如果操作员要求“ 标定在 GPU 内存,"拒绝 - vLLM 预分配额 `--gpu-memory-utilization`;内存保持近90%,即使有一次请求。
- 如果团伙安排因TP-8工作量复杂而被拒绝,则拒绝核证计划——将8个分散的人群单人安置在 GPUs 原子失败

产出:与卡彭特人共同制定的一页计划 YAML 片段、 KAI 调度器配置片段、 HPA/ 客户自动标尺信号选择、 暖源数和五个仪表板度量。 最后使用一个杀死开关: 如果 P99 TTFT 破解, 则返回到已知的自动标尺状态 。
