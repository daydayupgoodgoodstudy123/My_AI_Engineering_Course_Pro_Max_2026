---
name: checkpointing-planner
description: Choose an activation recomputation policy per layer (none / selective / full / offload) given a training config and HBM budget.
version: 1.0.0
phase: 10
lesson: 34
tags: [gradient-checkpointing, activation-recomputation, selective-checkpoint, fsdp-offload, training-memory]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


根据训练配置( 字符串数 L, 隐藏大小 d, 序列长度 S, 缩微批次 B, dtype bytes per value,) , attention kernel, tensor- 平行度TP,管道-平行度PP, 专家-平行度EP,如果 MoE)和每个级别 HBM 预算之后 weights 和 optimizer 状态, 输出 :

1. 逐层政策。 对于堆叠中的每个层家族( 以 $1 )embedding, attention新生力量, MoE 专家、规范、输出头)不选,选择、完整或卸载。 attention 当S超过4时_096; 剩余流和规范的默认值为零; 只有当测量到的该层激活的PCIe传输时间低于其测量的重新计算时间时, 才会在 FFFN 上卸载默认值 。
2. k. 如果完全设置了检查,则将 k 选为整数( sqrt(L)) 以支付统一的层成本,激活内存时以小k 来支配预算。
3. FlashAttention 确认是否 attention 内核已经重新计算 softmax如果回答为 " 是 " ,则有选择性 attention 检查站很少买到;降级为零。FlashAttention-2/3, x 瓶式记忆效率,香草)
4. TP / PP 计划。 对于 TP, 请列出需要重新计算或重新分解的激活, 并添加了每步通信字节。 对于 PP, 请确认哪个管道阶段在返回前会经过端到端的检查, 从而可以让微信箱自由激活内存 。
5. 预算数学。 政策前后的预测激活记忆( 按每级MB计算 ) 。 预测 FLOP 管理费占 fwd+bwd 的百分比 。 拒绝任何与 HBM 预算不符的计划, 且总机为10% 。

选择时拒绝全部检查每个层 attention 单关闭预算; 配置显示 FLOP 管理费比选择的多倍, 以节省相同的内存, 而准确的比例是特定工作量。 当该层测量到目标 PCIe 链接上的激活传输时间超过其测量的重新计算时间时拒绝卸载; 重新计算胜算 。checkpoint 各地的 FP8 训练, 当选择的框架不显示 异常历史; 重新计算将会移动大小, 并且悄悄地腐蚀 gradients.

示例输入:“L=64, d=8192, S=8192, B=1, bf16 ” FlashAttention-3,TP=8,PP=4,每级32GB weights, MoE 与8名专家 和EP=8。"

输出示例：
- 逐层政策 : attention 选择,FFFN没有, MoE 专家满员, embedding 无,输出头卸载。
- 段大小: 完全应用于 MoE 只在k=8; FLOP 上占12%的专家路径, 在其他地方为0。
- FlashAttention 交互作用: FA-3 已重新计算 softmax;在层包装上选择,而不是在内核中选择。
- TP/PP计划:TP收集 attention 重新计算时输入, 每步0.3GB额外的通信; 每一个 PP 级 checkpoint 完全向前;PP第3阶段保留了它为最后落后的启动。
- 预算计算:启动38GB没有政策,11GB有政策。FLOP总间接费用7.5% fwd+bwd。
