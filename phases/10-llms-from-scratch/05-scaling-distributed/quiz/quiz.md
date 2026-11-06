# 测验 · 扩展：分布式训练、FSDP、DeepSpeed（Scaling: Distributed Training, FSDP, DeepSpeed）

> **阶段 10 · 从零构建 LLM · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 训练显存账本 | 不含激活时 = 权重 + 梯度 + 优化器状态；讲义口径：FP16 权重 2B + FP16 梯度 2B + FP32 Adam m、v 共 8B = **12 字节/参数**，70B → 840 GB |
| 2 | 数据并行（DP/DDP） | 每卡一份完整模型，batch 切 N 份，反向后 all-reduce 平均梯度；**只缩短时间，不降低单卡显存** |
| 3 | Ring all-reduce | 每卡通信量 `2 × 梯度大小 × (N−1)/N`，N 大时趋近梯度大小的 2 倍，与 GPU 数基本无关 |
| 4 | 张量并行（TP） | 把一个矩阵乘法切到多卡；按输出维切（column-parallel）结果拼接，按输入维切（row-parallel）结果求和；FFN 用"先列后行"省掉中间一次通信；每层都要通信，只适合节点内 NVLink |
| 5 | 流水线并行（PP） | 按层切成 N 个 stage；朴素流水线利用率只有 1/N；切 M 个 micro-batch 后空泡占比 `(N−1)/(M+N−1)`（讲义写作 `(N−1)/M`，那是"空泡时间 / 有效计算时间"） |
| 6 | FSDP | 每卡只存 1/N 的参数、梯度、优化器状态；每层前向/反向前 all-gather 参数，反向后 reduce-scatter 梯度 |
| 7 | ZeRO-1/2/3 | 依次切分优化器状态 → + 梯度 → + 参数；ZeRO-3 ≈ FSDP；ZeRO-Offload/Infinity 把状态卸载到 CPU 内存 / NVMe |
| 8 | 混合精度 | 前向/反向用 BF16/FP16，优化器维护 FP32 master 权重；BF16 有 8 位指数（同 FP32）、7 位尾数，基本不需要 loss scaling |
| 9 | 3D 并行 | TP 在节点内、PP 跨节点、DP 在最外层；讲义：Llama 3 405B 为 8 × 16 × 128 = 16,384 张 H100 |
| 10 | 训练成本估算 | 总 FLOPs ≈ `6 × 参数量 × token 数`；MoE 应该用**激活参数**计算，这是 DeepSeek-V3 便宜一个数量级的根本原因 |

### 核心技能（能动手做到）

- [ ] 给定参数量和精度，手算权重 / 梯度 / Adam 状态显存，并判断需要几张 80GB 卡
- [ ] 解释 DP、TP、PP、FSDP 各自切的是什么、通信的是什么、通信发生在什么时候
- [ ] 手算朴素 GPipe 流水线的总时长和空泡占比，并说清讲义 `(N−1)/M` 与代码输出 15.8% 的区别
- [ ] 按 ZeRO 论文 16 字节/参数口径，算出 ZeRO-1/2/3 在 N 张卡上每卡的模型状态显存
- [ ] 指出本节 `mixed_precision_comparison` 漏算 FP32 master 权重、`communication_volume_calculator` 低估 FSDP 通信量等简化
- [ ] 用 `6ND` 估算一次训练的 GPU 小时与费用，并正确处理 MoE 模型

---

## 二、基础自测（选择题）

**Q1.** 按讲义的口径（FP16 权重、FP16 梯度、FP32 的 Adam m 和 v，不含激活），一个 70B 模型训练所需的模型状态显存是：

- A. 840 GB
- B. 560 GB
- C. 280 GB
- D. 1,120 GB

**Q2.** 关于数据并行（DDP），下列说法正确的是：

- A. N 张卡时每张卡只需存 1/N 的模型参数
- B. 每张卡处理同一份数据，但用不同的随机种子
- C. 它在每一层前向之前都要 all-gather 参数
- D. 每张卡都持有完整的模型、梯度和优化器状态，它只缩短训练时间、不降低单卡显存

**Q3.** 用 ring all-reduce 同步大小为 G 的梯度，N 张卡时**每张卡**发送（或接收）的数据量约为：

- A. `G / N`
- B. `2G × (N−1) / N`
- C. `N × G`
- D. `G × (N−1)`

**Q4.** 在 Transformer FFN 中做张量并行：第一层（升维）按输出维切分（column-parallel），第二层（降维）按输入维切分（row-parallel）。第二层各卡的部分结果应如何合并？

- A. 在最后一维拼接（concatenate）
- B. 取平均
- C. 逐元素求和（all-reduce）
- D. 不需要合并，各卡直接把部分结果送入下一层

**Q5.** 运行本节代码，`simulate_pipeline_parallelism(32, 4, 16)` 输出 `bubble=15.8%`。与代码输出一致的公式是（N 为 stage 数、M 为 micro-batch 数）：

- A. `(N−1) / (M+N−1)`
- B. `(N−1) / M`
- C. `1 / N`
- D. `(N−1) / N`

**Q6.** 关于 DeepSpeed ZeRO 的三个阶段，正确的是：

- A. ZeRO-1 切分参数，ZeRO-2 再切分梯度，ZeRO-3 再切分优化器状态
- B. ZeRO-3 与 FSDP 是两种机制完全不同的方法
- C. ZeRO-1 的通信量比 ZeRO-3 更大
- D. ZeRO-2 切分优化器状态和梯度，但每张卡仍保存完整的参数

**Q7.** 为什么业界大多从 FP16 转向 BF16 训练？

- A. BF16 的尾数位更多，精度高于 FP16
- B. BF16 占用 4 字节，数值更稳定
- C. BF16 有 8 位指数，动态范围与 FP32 相同，梯度几乎不会下溢，基本不需要 loss scaling
- D. BF16 只能在 TPU 上使用，所以更便宜

**Q8.** 讲义中 Llama 3 405B 的 3D 并行配置是 TP=8、PP=16、DP=128。为什么 TP 被限制在单个节点（8 卡）以内？

- A. 因为每个节点恰好有 8 层 Transformer
- B. TP 每一层都要做集合通信，需要 NVLink 级带宽（讲义：900 GB/s）；跨节点的 InfiniBand 约 50 GB/s，太慢
- C. 因为 PP 无法跨节点
- D. 因为 TP 的切分数必须等于注意力头数

---

## 三、动手 / 代码题

**Q9.** 阅读本节 `mixed_precision_comparison`：

```python
    fp16_weights = params * 2
    fp16_master = params * 4
    fp16_optimizer = params * 4 * 2
    fp16_gradients = params * 2
    fp16_total = fp16_weights + fp16_master + fp16_optimizer + fp16_gradients

    mixed_weights = params * 2
    mixed_optimizer = params * 4 * 2
    mixed_gradients = params * 2
    mixed_total = mixed_weights + mixed_optimizer + mixed_gradients
    # ...
        "savings_vs_fp32": 1 - mixed_total / fp32_total,
```

讲义表格把 `mixed_total` 标为 "Mixed (BF16 + FP32 master)"，结论是"7B 模型 FP32 112GB、混合精度 84GB，节省 25%"。

1. `mixed_total` 是否真的包含了 FP32 master 权重？算出 7B 模型 `fp16_with_master_gb` 的值（它被计算了但没有打印）。
2. 那么"混合精度节省 25% 模型状态显存"的结论成立吗？混合精度真正的收益来自哪里？
3. ZeRO 论文使用的"每参数 16 字节"是怎么构成的？

**Q10.** 手算流水线：`simulate_pipeline_parallelism(num_layers=32, num_stages=4, num_microbatches=4)`。每个 stage 有 8 层，代码里一个 stage 处理一个 micro-batch 的前向耗时 8、反向耗时也是 8，且所有反向都要等全部前向结束（`deps = [last_fwd_end]`）。

1. 前向阶段在什么时刻结束？`total_time` 是多少？`bubble` 是多少？
2. 讲义写"M=16、N=4 时空泡为 3/16 = 18.75%"，代码输出 15.8%。两者谁错了？
3. 如果把 `num_layers` 改成 30，会发生什么？

**Q11.** 阅读数据并行模拟及 `__main__` 中的 `model_fn`：

```python
    avg_loss = np.mean(gpu_losses)
    avg_gradient = np.mean(gpu_gradients, axis=0)
```

```python
    def model_fn(batch):
        output = batch @ weight          # (B, 16)
        loss = np.mean(output ** 2)
        grad = 2 * batch.T @ (batch @ weight) / len(batch)
        return loss, grad
```

1. 代码输出 1/2/4/8 张卡的 loss 和 grad_norm 完全相同（30.2175 / 53.0517）。如果改用 3 张卡（64 个样本分成 22/21/21），结果还会相同吗？为什么？如何修正？
2. `grad` 真的是 `loss` 对 `weight` 的梯度吗？用有限差分说明。

**Q12.** 阅读成本与通信估算的输出：

```text
  Data Parallel (Ring AllReduce)            Per-step volume: 245.0 GB
  FSDP (AllGather + ReduceScatter per layer) Per-step volume: 245.0 GB
       671B   14.8T   2048     850d   $146,287,037
```

1. 讲义说 FSDP"通信成本比普通数据并行更高"，代码却给出相同的 245 GB。哪里漏算了？按每卡计，70B、8 卡的 FSDP 通信量应约为多少？
2. 第四行用来对照 DeepSeek-V3（讲义：约 $5.6M）。为什么代码估出了 850 天、1.46 亿美元？改用激活参数 37B 后结果是多少？

---

## 四、面试高频题

**Q13.**（基础必考）请比较数据并行、张量并行、流水线并行和 FSDP：各自切分什么、通信什么、通信发生在何时、适用场景是什么？

**Q14.**（原理深挖）ZeRO-1/2/3 分别把单卡模型状态显存降低到多少？通信代价分别是多少？ZeRO-3 为什么和 FSDP 等价？

**Q15.**（工程实践）给你 64 张 H100（8 节点 × 8 卡，节点内 NVLink、节点间 InfiniBand），要全参数训练一个 70B 的稠密模型，序列长度 8K。请给出并行方案、显存预算和需要打开的优化开关。

**Q16.**（原理深挖）混合精度训练为什么需要 FP32 master 权重？loss scaling 解决什么问题？为什么 BF16 基本不需要它？

**Q17.**（追问型）讲义说 Llama 3 405B 花了约 1 亿美元，DeepSeek-V3 约 560 万美元。请用 `6ND` 估算解释差距从何而来，并说出这类估算最容易出错的地方。

---

## 五、参考答案与解析

### Q1 — 答案：A

`70B × (2 + 2 + 8) 字节 = 840 GB`：权重 140 GB + 梯度 140 GB + Adam 560 GB。讲义表格与代码 `memory_calculator(70)` 的前三项一致（代码默认还会加 70 GB "激活"，打印出 910 GB）。B 只算了 Adam 状态；C 是权重 + 梯度；D 是全 FP32（16 字节/参数）口径。注意：讲义"问题"小节写"Adam 再存两份副本，那是另外 28GB"（7B），这是按 FP16 存 m、v 的口径，与后面表格中 FP32 的 56GB 自相矛盾，应以表格为准。

### Q2 — 答案：D

讲义："Data parallelism does nothing to reduce per-GPU memory. It only reduces training time." A 描述的是 FSDP/ZeRO-3；B 错，DP 的关键是每卡处理**不同**的数据分片，同一份模型；C 是 FSDP 的行为，DDP 只在反向后做一次梯度 all-reduce。

### Q3 — 答案：B

ring all-reduce = reduce-scatter（N−1 步）+ all-gather（N−1 步），每步传 G/N，共 `2(N−1)/N × G`。代码 `communication_volume_calculator(70, 8, "data_parallel")`：梯度 140 GB × 2 × 7/8 = **245 GB**。它的妙处是每卡通信量几乎不随 N 增长，所以 DP 能扩展到很多卡。A 是一次 scatter 的量；C、D 是朴素"参数服务器 / 两两互发"的量级。

### Q4 — 答案：C

row-parallel：输入 X 按列切成 `[X₁, X₂]`，权重按行切成 `[W₁; W₂]`，`XW = X₁W₁ + X₂W₂`，各卡得到的是**完整形状的部分和**，必须求和（all-reduce）。A 是 column-parallel 的合并方式（代码 `simulate_tensor_parallelism` 演示的就是这种，`max_error=0`）。D 错：只有"column 之后紧接 row"时中间才免通信，row 之后必须 all-reduce。讲义："the first linear (expand) uses column-parallel and the second linear (contract) uses row-parallel. This avoids an all-reduce between the two layers."

### Q5 — 答案：A

`3/(16+3) = 3/19 = 15.79%`，与代码输出一致；M=1 时 `3/4 = 75%`、M=32 时 `3/35 = 8.6%` 也都吻合（已实际运行验证）。B 是讲义写的 `3/16 = 18.75%`，它其实是"空泡时间 / 有效计算时间"之比，不是"空闲时间占总时间"的比例（Megatron 论文用的就是这个比值口径）。C 是朴素流水线（不分 micro-batch）的**利用率**；D 是 M=1 时的空泡占比。

### Q6 — 答案：D

ZeRO-1 切优化器状态；ZeRO-2 再切梯度；ZeRO-3 再切参数。A 把顺序完全说反了；B 错，讲义："ZeRO-3 is equivalent to FSDP. The naming is different, the mechanism is the same."；C 错，ZeRO-1 通信量与 DP 相同，ZeRO-3 因为要额外 all-gather 参数，通信量更大。

### Q7 — 答案：C

BF16：1 位符号 + 8 位指数 + 7 位尾数；FP16：1 + 5 + 10。BF16 用精度换范围，梯度不容易下溢成 0，所以"rarely needs loss scaling"。A 说反了（FP16 尾数更多）；B 错，BF16 是 2 字节；D 错，讲义说 A100、H100 同时支持 FP16 和 BF16。

### Q8 — 答案：B

TP 在每一层的前向和反向都需要 all-reduce 激活，通信极其频繁、且在关键路径上。讲义："This works well with NVLink (900 GB/s ...) but poorly across nodes connected by InfiniBand (400 Gb/s, about 50 GB/s)." 所以 TP 留在节点内，PP（只在 stage 边界传激活）跨节点，DP 在最外层。A、D 是无关的巧合；C 错，PP 恰恰是跨节点的那一维。

### Q9 — 参考答案

1. **没有包含**。`mixed_total = 2 + 8 + 2 = 12` 字节/参数，只有 BF16 权重、FP32 的 m 和 v、BF16 梯度。真正包含 master 权重的是 `fp16_total = 2 + 4 + 8 + 2 = 16` 字节/参数，7B 时 `fp16_with_master_gb = 112.0`（已实际运行），**与 FP32 的 112 GB 完全相同**。
2. **不成立**。在"BF16 计算 + FP32 master + FP32 Adam"的标准混合精度下，模型状态显存与纯 FP32 训练一样是 16 字节/参数，节省为 0%。混合精度的真正收益是：
   - **激活显存减半**（激活以 16 位保存，而长序列、大 batch 时激活往往是大头）；
   - **算力翻倍**（tensor core 的 16 位矩阵乘吞吐约为 FP32 的 2 倍以上）；
   - **通信减半**（梯度以 16 位 all-reduce）。
   讲义"节省 25%"成立的前提是"不保留 FP32 master"（例如纯 BF16 训练 + FP32 优化器状态），而这与表头"BF16 + FP32 master"矛盾。
3. ZeRO 论文的混合精度 Adam：FP16 参数 2 + FP16 梯度 2 + FP32 参数副本 4 + FP32 momentum 4 + FP32 variance 4 = **16 字节/参数**（其中 12 字节是"优化器状态"K=12）。按此口径 7B 为 112 GB、70B 为 1,120 GB。本节 `memory_calculator` 用的是 12 字节/参数，同样漏了 master 权重，算出的数字偏乐观约 25%。

### Q10 — 参考答案

1. 前向：stage s 处理 micro-batch m 的结束时间 = `(m + s + 1) × 8`，最后一个（m=3, s=3）在 `7 × 8 = 56` 结束。反向从 56 开始，对称地再需要 `(M+N−1) × 8 = 56`，所以 `total_time = 112`。有效计算 = `M × N × 8 × 2 = 256`，总"卡·时间" = `112 × 4 = 448`，`bubble = 1 − 256/448 = 3/7 ≈ 42.9%`。与代码输出 `4 micro-batches: total_time= 112, bubble=42.9%` 一致。
2. 两者都"没算错"，口径不同：
   - 代码：空闲时间 / 总时间 = `(N−1)/(M+N−1)` = 3/19 = 15.8%；
   - 讲义：空泡时间 / 有效计算时间 = `(N−1)/M` = 3/16 = 18.75%。
   讲义把后者称为 "bubble fraction ... idle time" 并在 Build It 里写"16 个 micro-batch 降到约 19%"，与代码输出不一致。M ≫ N 时两者趋同。面试时说清楚口径即可。
3. `layers_per_stage = 30 // 4 = 7`，代码**静默丢掉 2 层**：`total_time = 98`、bubble 仍是 42.9%，看不出任何异常（已实际运行）。真实系统要么允许各 stage 层数不等（让最慢的 stage 决定节拍），要么在 embedding / LM head 所在的首尾 stage 少放几层来平衡。应加 `assert num_layers % num_stages == 0` 或显式处理余数。此外这个模拟还有两个简化：反向耗时设为与前向相同（实际约 2 倍），以及只模拟了 GPipe 式"全部前向后再全部反向"，讲义练习 2 要求实现 1F1B。

### Q11 — 参考答案

1. **不会相同**。3 张卡时实际输出 loss = 30.2035（vs 30.2175），grad_norm = 53.0314（vs 53.0517）。原因：`np.mean(gpu_losses)` 是"均值的均值"，只有每个分片大小相同时才等于全 batch 均值；22/21/21 时第一个分片的权重被低估。修正：按样本数加权，

   ```python
   sizes = [len(shard) for shard in shards]
   avg_loss = sum(l * s for l, s in zip(gpu_losses, sizes)) / sum(sizes)
   avg_gradient = sum(g * s for g, s in zip(gpu_gradients, sizes)) / sum(sizes)
   ```

   修正后 3 卡结果与单卡精确一致（已验证：30.2175）。生产中 PyTorch `DistributedSampler` 通过补齐/丢弃样本让每卡样本数相同，从而让"all-reduce 求和再除以 N"等价于全局平均。
2. **不是**。`loss = mean(output²)` 对 B×16 个元素求平均，正确梯度是 `2 Xᵀ(XW) / (B × 16)`；代码只除以 B，**放大了 16 倍**（d_out = 16）。有限差分验证：对 `weight[0,0]` 加 1e-6，数值梯度为 −0.0791，解析式 `2Xᵀ(XW)/(B·16)` 为 −0.0791，代码的 `grad` 为 −1.266（=16 倍）。真实梯度范数是 3.3157，而不是打印的 53.0517。这个 bug 不影响"各卡平均后与单卡一致"这一演示结论（只是统一缩放），但提醒我们：手写梯度一定要做 gradient check。

### Q12 — 参考答案

1. 代码把 FSDP 算成"一次 all-gather + 一次 reduce-scatter"，各 `(N−1)/N × 140 GB`，合计 245 GB。但 FSDP 在**前向和反向各需 all-gather 一次**参数（前向后会丢掉非本地分片以省显存），再加一次梯度 reduce-scatter，共 `3 × 140 × 7/8 = 367.5 GB`，约为 DP 的 **1.5 倍**。这与 ZeRO 论文 "ZeRO-3 通信量 1.5 倍于基线 DP" 的结论一致，本节 `outputs/` 里的提示词也写了 "~3 x weight_size x (N-1)/N"。另外 TP 一行的 `gradient_size_gb * 0.01` 是一个没有依据的魔法数，TP 通信量应按"每层 2 次（前向）+ 2 次（反向）激活 all-reduce × 层数"来估。
2. `training_cost_estimator(671, 14.8, "h100", 2048)` 用的是 `6 × 671e9 × 14.8e12 ≈ 5.96e25` FLOPs，把 MoE 的**总参数**当成了每 token 的计算量。MoE 每个 token 只激活 37B（讲义："activates only 37B out of 671B parameters per token"）。改为 37B（已实际运行）：总 FLOPs 3.29e24，2,048 张卡、40% 利用率下约 **46.9 天、230 万 GPU 小时、约 $8.07M**（按 H100 $3.5/小时）。如果按 $2/小时，约 $4.6M，与讲义的 $5.6M 在同一量级。DeepSeek-V3 实际用的是 H800，代码里并没有这一型号。

### Q13 — 参考回答要点

| 策略 | 切什么 | 通信什么 / 何时 | 适用 |
|------|--------|----------------|------|
| DP | 数据（batch） | 反向后 all-reduce 梯度，可与反向计算重叠 | 模型能放进单卡时首选，最简单 |
| TP | 每层的权重矩阵 | 每层前向 / 反向都 all-reduce 激活，在关键路径上 | 单层太大；只在节点内（NVLink） |
| PP | 层（stage） | stage 边界点对点传激活和激活梯度 | 跨节点；需要足够多的 micro-batch 压空泡 |
| FSDP / ZeRO-3 | 参数 + 梯度 + 优化器状态 | 每层 all-gather 参数（前向、反向各一次）+ reduce-scatter 梯度 | 模型状态放不下单卡，但单层放得下 |

- 加分点：DP 每卡显存不变；FSDP 每卡模型状态降为 1/N，但激活不被切分（激活取决于每卡 batch 和序列长度），需要配合 activation checkpointing；PP 的代价是空泡和要缓存多个 micro-batch 的激活。
- 常见误区：认为"TP 跨节点也能用"或"DP 能降低显存"。

### Q14 — 参考回答要点

- 设参数量 Ψ、卡数 N、混合精度 Adam 每参数 16 字节（2 参数 + 2 梯度 + 12 优化器）：
  - DDP：`16Ψ`；
  - ZeRO-1：`4Ψ + 12Ψ/N`；
  - ZeRO-2：`2Ψ + 14Ψ/N`；
  - ZeRO-3：`16Ψ/N`。
- 7B、64 卡实算：112 GB → 29.3 GB（约 3.8 倍）→ 15.5 GB（约 7.2 倍）→ 1.75 GB（64 倍）。这正是讲义表格 "~4x / ~8x / ~Nx" 的来源（N 足够大时 → 4 倍、8 倍）。若按本节代码的 12 字节口径，倍数只有约 2.9 / 5.6 / 64。
- 通信：ZeRO-1、ZeRO-2 与 DP 相同（reduce-scatter 梯度 + all-gather 更新后的参数 = 2Ψ）；ZeRO-3 约 3Ψ，即 1.5 倍。
- 等价性：ZeRO-3 和 FSDP 都是"参数分片常驻、计算前 all-gather、用完释放、梯度 reduce-scatter"，只是实现方不同（DeepSpeed vs PyTorch 原生）。讲义："ZeRO-3 is equivalent to FSDP."
- 加分点：ZeRO-Offload 把优化器状态和更新计算放到 CPU，ZeRO-Infinity 再扩展到 NVMe；用 PCIe 带宽换显存。PyTorch FSDP 的 `SHARD_GRAD_OP` 对应 ZeRO-2、`FULL_SHARD` 对应 ZeRO-3、`HYBRID_SHARD` 在节点内分片、节点间复制。

### Q15 — 参考回答要点

- **模型状态**：70B × 16 字节 = 1,120 GB。64 卡 FSDP 全分片后每卡约 17.5 GB；即使按讲义 12 字节口径（840 GB）也只是 13.1 GB/卡。
- **激活是关键**：8K 序列、hidden 8192、80 层的激活远大于模型状态。必须：
  - activation checkpointing（重算，约多 1/3 计算量，讲义练习 1）；
  - micro-batch 设为 1，用梯度累积凑出目标有效 batch（tokens/step）；
  - 必要时 TP=8（节点内）进一步切分每层激活和权重，或用序列并行。
- **方案示例**：
  - 方案 A：FSDP（或 HYBRID_SHARD：节点内分片、节点间复制）+ 激活检查点，纯 DP 维度 64；
  - 方案 B：TP=8（节点内 NVLink）× DP=8（跨节点）+ ZeRO-1/2，与讲义 `outputs/` 中 "70B / 64 卡 / TP 8 / PP 1 / DP 8" 的典型配置一致。
- **其他开关**：BF16 混合精度、FlashAttention、梯度裁剪（如 1.0）、通信与计算重叠、定期 checkpoint（大规模训练故障率高）。
- **验证**：先在 1 个节点上用小层数跑通，测 MFU（模型 FLOPs 利用率）和显存峰值，再扩展。
- 常见误区：只算模型状态忽略激活；把 TP 设到 16 跨节点。

### Q16 — 参考回答要点

- **为什么要 FP32 master 权重**：Adam 的单步更新量 `lr × m̂/√v̂` 往往比权重本身小 3–4 个数量级。BF16 只有 7 位尾数（相对精度约 2⁻⁸ ≈ 0.4%），FP16 有 10 位（约 0.1%），小更新加到大权重上会被**舍入掉**（swamping），训练停滞。在 FP32 副本上累加更新，再转成 16 位用于下一次前向。
- **loss scaling**：FP16 只有 5 位指数，最小正规数约 6e-5，很多梯度会下溢成 0。把 loss 乘以一个大常数 S（反向的梯度随之放大 S 倍），优化器更新前再除以 S；动态 loss scaling 在出现 inf/NaN 时减小 S 并跳过该步。
- **BF16**：8 位指数，动态范围与 FP32 相同，下溢基本不发生，因此"rarely needs loss scaling"（讲义）。代价是尾数更少、精度更差，所以 master 权重依然需要。
- 加分点：混合精度不省模型状态显存（见 Q9），省的是激活、带宽和计算时间；更激进的 FP8 训练需要逐张量 / 逐块缩放因子。

### Q17 — 参考回答要点

- **公式**：训练 FLOPs ≈ `6ND`（前向 2ND + 反向 4ND）。所需时间 = FLOPs / (卡数 × 峰值 × MFU)。
- **Llama 3 405B**：`6 × 405e9 × 15e12 ≈ 3.65e25` FLOPs；代码在 16,384 张 H100、40% 利用率下估出约 65 天、约 2,557 万 GPU 小时、约 $89.5M，与讲义"约 1 亿美元"同量级。
- **DeepSeek-V3**：MoE，每 token 只激活 37B，`6 × 37e9 × 14.8e12 ≈ 3.29e24`，计算量约为 405B 稠密模型的 1/11；代码用 37B 估出约 $8.1M（H100 $3.5/h）。差距的主要来源是**激活参数量**，其次是 FP8 训练、通信优化等工程效率（讲义："being clever about architecture ... and training efficiency"）。
- **最容易出错的地方**：
  - MoE 用总参数而非激活参数（本节代码第四行就是这个错误，估出 850 天）；
  - 利用率（MFU）拍脑袋：真实值常在 30%–50%，差一倍成本就差一倍；
  - `6ND` 忽略了注意力的 `O(S²)` 计算，长序列时偏低；
  - 公开的"训练成本"通常只含最终一次训练的 GPU 租金，不含前期实验、失败重跑、数据和人力。
- 加分点：能现场把 FLOPs 换算成 GPU 小时与金额。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：本节要扩展的就是那里的单卡训练循环与参数量估算。
- [阶段 03 · 06 Optimizers](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：Adam 为什么要为每个参数保存 m 和 v 两份状态。
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：浮点格式、上溢 / 下溢，理解混合精度与 loss scaling。
- [阶段 07 · 11 专家混合 (MoE)](../../../07-transformers-deep-dive/11-mixture-of-experts/docs/zh.md)：理解 DeepSeek-V3"总参数 671B、激活 37B"。
- [阶段 07 · 13 Scaling Laws](../../../07-transformers-deep-dive/13-scaling-laws/docs/zh.md)：参数量、数据量与算力预算之间的关系。

### 本节被哪些后续内容用到
- [阶段 10 · 06 指令微调（SFT）](../../06-instruction-tuning-sft/docs/zh.md)：全参数 SFT 同样要面对本节的显存账本。
- [阶段 10 · 19 DualPipe 并行](../../19-dualpipe-parallelism/docs/zh.md)：更先进的流水线调度，进一步压缩空泡并重叠通信。
- [阶段 10 · 20 DeepSeek-V3 架构详解](../../20-deepseek-v3-walkthrough/docs/zh.md)：MoE 与训练效率如何把成本压到数百万美元级。
- [阶段 10 · 34 Gradient Checkpointing 与激活重计算](../../34-gradient-checkpointing/docs/zh.md)：本节练习 1 的完整展开。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：显存不够时的另一条路——只训练少量参数。
- [阶段 19 · 45 Gradient Clipping 与 Mixed Precision](../../../19-capstone-projects/45-gradient-clipping-amp/docs/zh.md)、[阶段 19 · 46 Gradient Accumulation](../../../19-capstone-projects/46-gradient-accumulation/docs/zh.md)、[阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../../19-capstone-projects/48-distributed-fsdp-ddp/docs/zh.md)：综合项目中亲手实现本节的机制。

### 延伸关键词
`DDP` · `NCCL` · `ring all-reduce` · `reduce-scatter / all-gather` · `Megatron-LM` · `column/row parallel` · `sequence parallelism` · `GPipe` · `1F1B` · `interleaved pipeline` · `ZeRO-Offload / ZeRO-Infinity` · `FSDP HYBRID_SHARD` · `activation checkpointing` · `loss scaling` · `BF16 / FP8` · `MFU` · `6ND`
