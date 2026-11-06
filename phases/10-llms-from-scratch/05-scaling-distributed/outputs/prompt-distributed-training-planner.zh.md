---
name: prompt-distributed-training-planner
description: Plan a distributed training run given model size and available hardware
version: 1.0.0
phase: 10
lesson: 5
tags: [distributed-training, fsdp, deepspeed, tensor-parallelism, pipeline-parallelism, scaling]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="distributed-training-planner"></a>

# 分布式训练规划器

当 planning 为大型语言模型运行分布式训练时，使用此框架来确定并行策略、内存预算、通信开销和预期吞吐量。

<a id="input-requirements"></a>

## 输入要求

提供：
- **模型大小**（parameters，单位为十亿）
- **目标训练tokens**（万亿）
- **可用 GPUs**（类型：A100/H100/H200，计数，互连：NVLink/InfiniBand）
- **GPU 内存**（A100/H100 80GB，H200 141GB）
- **Nodes**（每个节点GPUs，节点数量）
- **预算限制**（最大成本（美元），最大挂钟时间）

<a id="step-1-memory-budget"></a>

## 第 1 步：内存预算

计算每个组件的 per-GPU 内存：

| 组件 | 公式 | FP16 | FP32 |
|-----------|---------|------|------|
| Weights | 参数 x 字节_per_param | 参数 x 2 | 参数 x 4 |
| Adam optimizer (m + v) | 参数 x 4 x 2 | 始终为 8 字节/参数 | 8 字节/参数 |
| Gradients | 参数 x 字节_per_param | 参数 x 2 | 参数 x 4 |
| 激活（估计） | seq_len x 批次 x 隐藏 x 层 x 2 | 各不相同 | 各不相同 |

如果总数超过GPU内存，则需要分片。按顺序尝试：
1. ZeRO-1（仅限分片 optimizer）——最便宜的通信
2. ZeRO-2 (+ gradients) -- 中等通信
3. FSDP/ZeRO-3 (+ weights) -- 最高通信速度，但最大程度节省内存
4. 如果激活仍然太大，请添加 activation checkpointing
5. 如果单层不适合 GPU，则添加 tensor parallelism

<a id="step-2-parallelism-strategy"></a>

## 第 2 步：并行策略

<a id="decision-tree"></a>

### 决策树

1. **一层适合一层GPU吗？**
   - 否：您需要 tensor parallelism。设置 TP = 2、4 或 8（在节点内）。
   - 是：跳过 tensor parallelism。

2. ** 完整模型（带分片）是否适合一个节点内的 GPUs？**
   - 否：您需要 pipeline parallelism。设置 PP = 节点数/组数。
   - 是：跳过 pipeline parallelism。

3. ** 数据并行还剩多少GPUs？**
   - DP = total_gpus / (TP x PP)

4. ** 数据并行组内的分片级别是多少？**
   - 从 FSDP (ZeRO-3) 开始。如果通信是瓶颈，则减少到 ZeRO-2 或 ZeRO-1。

<a id="typical-configurations"></a>

### 典型配置

| 型号尺寸 | 总计 GPUs | TP | 聚丙烯 | DP | 分片 |
|-----------|-----------|----|----|-----|----------|
| 7B | 8 | 1 | 1 | 8 | FSDP |
| 13B | 16 | 2 | 1 | 8 | FSDP |
| 70B | 64 | 8 | 1 | 8 | FSDP |
| 70B | 128 | 8 | 2 | 8 | FSDP |
| 405B | 16,384 | 8 | 16 | 128 | FSDP |

<a id="step-3-communication-analysis"></a>

## 第三步：沟通分析

估计每个训练步骤的通信量：

- **数据并行（全归约）**：2 x梯度_尺寸x（N-1）/N每步
- **FSDP（全聚集+减少分散）**：〜3 x重量_尺寸x（N-1）/N每步（高于DP）
- **Tensor 并行（每层全部归约）**：2 x 激活_size x num_ 每步层数（需要 NVLink）
- **管道并行（点对点）**：激活_每级边界的大小（最小）

如果通信时间超过计算时间的 20%，则策略受通信限制。解决方案：
- Gradient accumulation（减全减频）
- 与计算重叠通信（FSDP 默认情况下这样做）
- 增加micro-batch size（更好的计算通信比）
- 切换到通信量较少的分片阶段

<a id="step-4-throughput-and-cost-estimate"></a>

## 第 4 步：吞吐量和成本估算

**FLOPS 每个训练步骤：**
- 转发：~2 x params x tokens_per_batch
- 向后：〜4 x params x tokens_per_batch（2x向前）
- 总计：~6 x 参数 x 代币_per_batch

**培训时间：**
- total_flops = 6 x params x total_tokens
- time_seconds = total_flops / (num_gpus x gpu_tflops x 1e12 x utilization)
- 典型利用率：35-45%（考虑通信、管道气泡、内存开销）

**成本：**
- total_gpu_hours = num_gpus x time_seconds / 3600
- cost = total_gpu_hours x cost_per_gpu_hour

<a id="step-5-validation-checklist"></a>

## 第 5 步：验证清单

启动前：

1. Per-GPU 内存符合硬件限制（有 10% 的空间）
2. 有效batch size匹配目标（per_gpu_batch x DP xgradient_accumulation_steps）
3. 通信计算比低于20%
4. 管道气泡分数低于 15%（足够的微批次）
5. Learning rate 缩放为有效 batch size
6. 检查点频率考虑了故障概率（对于大型运行，每 1-2 小时保存一次）
7. Gradient clipping 已设置（大型模型通常为 1.0）
8. Warmup 步数与总步数成正比（通常为总步数的 0.1-1%）

<a id="red-flags"></a>

## 危险信号

- **TP > 8**：跨节点的 Tensor parallelism（通过 InfiniBand）几乎总是慢于 pipeline parallelism
- **管道阶段 > 32**：即使有许多微批次，气泡开销也会变得很大
- **E有效 batch size > 10M tokens**：收益递减；可能会损害收敛性
- **利用率低于30%**：通信限制——重新评估并行策略
- **No activation checkpointing 以上 13B**：在 backward pass 期间您将耗尽内存
- **否 gradient accumulation 与小每 GPU 批次 **：Gradient 噪音增加；累计有效批次256+样品
