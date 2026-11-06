# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 05 节 扩展：分布式训练、FSDP、DeepSpeed ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：`numpy`（第三方）；无需 GPU、无需 PyTorch、无需网络。`collections.defaultdict` 被导入但未使用。

---

## 1. 这份代码在考察什么

真正的分布式训练需要多张 GPU 和 NCCL，这份代码改用**单进程 NumPy 模拟 + 解析公式**，把分布式训练的核心机制和"显存 / 通信 / 成本"三本账拆开来看：

1. **数据并行**：把 batch 切成 N 份分别算梯度再平均，结果与单卡相同（`simulate_data_parallelism`）。
2. **张量并行**：把权重矩阵按输出列切开，各卡算一部分再拼接，结果与整块矩阵乘精确相等（`simulate_tensor_parallelism`）。
3. **流水线并行**：用一个事件时间表模拟 GPipe 调度，量化 micro-batch 数量对空泡（bubble）的影响（`simulate_pipeline_parallelism`）。
4. **显存账本**：权重 + 优化器状态 + 梯度 + 激活，以及 FSDP / ZeRO 各阶段把哪一项除以 N（`memory_calculator`）。
5. **混合精度**、**通信量**、**训练成本**三个估算器。

> 一句话：**分布式训练的本质是"同一个数学计算，换一种切分方式放到多张卡上"——切法决定了每卡显存和通信量**。同时要看清这些估算器里的简化与错误，它们正是面试追问的高发区。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `simulate_data_parallelism` | 函数 | 切分 batch → 各分片 `model_fn` → 平均 loss 与梯度 | 数据并行、all-reduce |
| `simulate_tensor_parallelism` | 函数 | 按输出列切权重 → 各片相乘 → 拼接 → 与直接相乘比误差 | column-parallel 张量并行 |
| `simulate_pipeline_parallelism` | 函数 | 构造 `(stage, mb, fwd/bwd) → (start, end)` 时间表，算总时长与空泡 | GPipe 流水线、bubble |
| `memory_calculator` | 函数 | 计算每卡权重 / 优化器 / 梯度 / 激活显存，按分片策略除以 N | 显存预算、FSDP、ZeRO-1/2/3 |
| `mixed_precision_comparison` | 函数 | 比较 FP32、FP16+master、"混合 BF16"三种口径 | 混合精度 |
| `communication_volume_calculator` | 函数 | 估算 DP / FSDP / TP 每步通信量 | ring all-reduce、all-gather、reduce-scatter |
| `training_cost_estimator` | 函数 | `6ND` → GPU 时间 → 天数与美元 | 训练算力与成本 |
| `if __name__ == "__main__":` | 脚本入口 | 依次运行 7 个演示并打印表格 | — |

数据流：固定种子 → 数据并行演示 → 张量并行演示 → 流水线演示 → 显存表 → 混合精度表 → 通信量 → 成本表。各部分彼此独立，没有共享状态（`training_cost_estimator` 内部会调用 `memory_calculator`）。

---

## 3. 逐段精讲

### 3.1 数据并行：切分 → 各自计算 → 平均

```python
def simulate_data_parallelism(data, num_gpus, model_fn):
    batch_size = len(data)
    shard_size = batch_size // num_gpus
    remainder = batch_size % num_gpus

    gpu_losses = []
    gpu_gradients = []

    offset = 0
    for gpu_id in range(num_gpus):
        extra = 1 if gpu_id < remainder else 0
        shard = data[offset:offset + shard_size + extra]
        offset += shard_size + extra

        loss, grad = model_fn(shard)
        gpu_losses.append(loss)
        gpu_gradients.append(grad)

    avg_loss = np.mean(gpu_losses)
    avg_gradient = np.mean(gpu_gradients, axis=0)
    return avg_loss, avg_gradient
```

- **切分**：`//` 求每片大小，`%` 求余数，前 `remainder` 张卡各多分 1 个样本。64 个样本分 3 卡 → 22/21/21。
- **"模拟 GPU"就是 for 循环**：每次迭代代表一张卡在自己的分片上跑前向 + 反向。真实 DDP 中这些是并行发生的。
- **`np.mean(gpu_gradients, axis=0)`**：把 N 个 `(32, 16)` 的梯度堆成 `(N, 32, 16)` 再沿第 0 维平均，就是 all-reduce（求和）再除以 N 的效果。
- ⚠️ **"均值的均值"只在分片等大时正确**。分片不等大时（如 3 卡），每片的 loss 已经是片内平均，再简单平均会让小分片的样本权重偏大。实测 3 卡 loss = 30.2035，而单卡是 30.2175。修正：按样本数加权平均（见测验 Q11）。PyTorch 的 `DistributedSampler` 会补齐样本让每卡等量，从根源上回避这个问题。

`__main__` 中配套的 `model_fn`：

```python
    def model_fn(batch):
        output = batch @ weight          # (B, 32) @ (32, 16) -> (B, 16)
        loss = np.mean(output ** 2)
        grad = 2 * batch.T @ (batch @ weight) / len(batch)
        return loss, grad
```

- 这是一个线性模型、目标为 0 的 MSE：`L = mean((XW)²)`。
- ⚠️ `np.mean` 是对 `B × 16` 个元素求平均，正确梯度应为 `2Xᵀ(XW)/(B·16)`；代码只除以 `B`，梯度被放大了 16 倍（打印的 grad_norm 53.05，真实值 3.3157，正好 16 倍）。不影响"多卡 = 单卡"的结论（统一缩放），但是一个典型的手写梯度错误。
- `weight` 来自外层作用域，`model_fn` 是一个**闭包**。

### 3.2 张量并行：按列切、拼接

```python
def simulate_tensor_parallelism(input_data, weight_matrix, num_gpus):
    d_in, d_out = weight_matrix.shape
    assert d_out % num_gpus == 0, f"d_out {d_out} not divisible by num_gpus {num_gpus}"
    shard_size = d_out // num_gpus

    partial_results = []
    for gpu_id in range(num_gpus):
        start = gpu_id * shard_size
        end = start + shard_size
        weight_shard = weight_matrix[:, start:end]
        partial = input_data @ weight_shard
        partial_results.append(partial)

    full_output = np.concatenate(partial_results, axis=-1)
    direct_output = input_data @ weight_matrix
    error = np.abs(full_output - direct_output).max()
    return full_output, error
```

形状追踪（演示：`x` 为 `(4, 8192)`，`W` 为 `(8192, 8192)`，4 卡）：

| 步骤 | 形状 |
|------|------|
| `weight_matrix[:, start:end]` | `(8192, 2048)`：每卡只存 1/4 的列 |
| `input_data @ weight_shard` | `(4, 2048)`：输出的第 k 段列 |
| `np.concatenate(..., axis=-1)` | `(4, 8192)`：拼回完整输出（对应 all-gather） |

- **为什么误差恰好是 0**：输出的每一列只依赖 `x` 和 `W` 的对应列，按列切开后每一列的计算顺序与整块相乘完全一样，所以浮点结果逐位相同，打印 `max_error=0.00e+00`。
- 这是 **column-parallel**。讲义还提到 **row-parallel**（按 `d_in` 切 `W` 的行、同时切 `x` 的列），各卡得到完整形状的部分和，需要**求和**而不是拼接。FFN 第一层 column-parallel、第二层 row-parallel，中间的激活刚好是按列分好的，省掉一次通信。代码没有演示 row-parallel，可作为练习。
- `assert ... , f"..."`：维度必须能被卡数整除，否则直接报错。
- ⚠️ 这里只模拟了"数学正确性"，没有模拟 TP 最关键的成本——每层都要 all-reduce / all-gather 激活。

### 3.3 流水线并行：事件时间表

```python
def simulate_pipeline_parallelism(num_layers, num_stages, num_microbatches):
    layers_per_stage = num_layers // num_stages
    timeline = {}

    for mb in range(num_microbatches):
        for stage in range(num_stages):
            start_time = max(
                timeline.get((stage, mb - 1, "fwd"), (0, 0))[1] if mb > 0 else 0,
                timeline.get((stage - 1, mb, "fwd"), (0, 0))[1] if stage > 0 else 0,
            )
            end_time = start_time + layers_per_stage
            timeline[(stage, mb, "fwd")] = (start_time, end_time)
```

- `timeline` 的键是元组 `(stage, micro-batch, "fwd"/"bwd")`，值是 `(开始, 结束)`。用"每层 1 个时间单位"计时，一个 stage 处理一个 micro-batch 耗时 `layers_per_stage`。
- **前向的两个依赖**：
  - 同一 stage 必须先做完上一个 micro-batch（`(stage, mb-1)`）——一张卡同一时间只能干一件事；
  - 同一 micro-batch 必须先在上一个 stage 做完（`(stage-1, mb)`）——数据要从上游传过来。
  `start = max(两个依赖的结束时间)`，这就是经典的 GPipe 前向调度。
- `x if cond else y` 是条件表达式：边界（第一个 micro-batch 或第一个 stage）时依赖为 0。

```python
    last_fwd_end = max(v[1] for v in timeline.values())

    for mb in range(num_microbatches - 1, -1, -1):
        for stage in range(num_stages - 1, -1, -1):
            deps = [last_fwd_end]
            if mb < num_microbatches - 1 and (stage, mb + 1, "bwd") in timeline:
                deps.append(timeline[(stage, mb + 1, "bwd")][1])
            if stage < num_stages - 1 and (stage + 1, mb, "bwd") in timeline:
                deps.append(timeline[(stage + 1, mb, "bwd")][1])
            start_time = max(deps)
            end_time = start_time + layers_per_stage
            timeline[(stage, mb, "bwd")] = (start_time, end_time)
```

- 反向逆序遍历（micro-batch 和 stage 都从大到小），依赖关系与前向镜像：梯度从最后一个 stage 往前流。
- `deps = [last_fwd_end]`：**所有反向都要等全部前向结束**，这是 GPipe 的"flush"式调度。1F1B（PipeDream）会让反向更早开始，以减少同时缓存的激活（讲义练习 2）。
- ⚠️ 反向耗时设为与前向相同；真实反向约是前向的 2 倍。

```python
    total_time = max(v[1] for v in timeline.values())
    compute_time = num_microbatches * num_stages * layers_per_stage * 2
    bubble_fraction = 1.0 - compute_time / (total_time * num_stages)
```

- `compute_time`：所有卡真正在干活的"卡·时间"总和（×2 是前向 + 反向）。
- `total_time * num_stages`：所有卡在整个时间窗口内的"卡·时间"总量。
- 空泡占比 = 1 − 有效 / 总量，化简后等于 `(N−1)/(M+N−1)`。N=4、M=16 时为 3/19 = 15.8%。
- ⚠️ 讲义正文用的是 `(N−1)/M = 18.75%`（空泡 / 有效计算的比值），并说"16 个 micro-batch 时约 19%"，与代码输出的 15.8% 口径不同（详见测验 Q10）。
- ⚠️ `num_layers // num_stages` 会静默丢掉余数层：`num_layers=30` 时每 stage 7 层，2 层凭空消失。

### 3.4 显存计算器：四本账 + 分片

```python
    params = params_billions * 1e9
    weight_memory = params * precision_bytes          # 默认 2 字节（FP16/BF16）

    if optimizer == "adam":
        optimizer_memory = params * 4 * 2             # FP32 的 m 和 v
    elif optimizer == "sgd":
        optimizer_memory = params * 4
    else:
        optimizer_memory = 0

    gradient_memory = params * precision_bytes

    if hidden_dim and num_layers:
        activation_per_layer = (
            sequence_length * batch_size_per_gpu * hidden_dim * precision_bytes * 4
        )
        activation_memory = activation_per_layer * num_layers
    else:
        activation_memory = params * precision_bytes * 0.5
```

- 模型状态 = `2 + 8 + 2 = 12` 字节/参数：7B → 84 GB，70B → 840 GB，与讲义表格一致。
- ⚠️ 漏了混合精度必需的 **FP32 master 权重**（4 字节/参数）。ZeRO 论文的标准口径是 16 字节/参数。
- ⚠️ `optimizer == "sgd"` 给了 4 字节/参数：纯 SGD 没有状态，带 momentum 的 SGD 才有一份 FP32 动量，这里实际对应后者。
- **激活**：
  - 给定 `hidden_dim` 和 `num_layers` 时，每层按 `s × b × h × 2 字节 × 4` 估算——即"每层保存 4 个与隐藏状态同形状的张量"。2048 × 4096 × 2 × 4 = 64 MiB，与讲义"单层约 64MB"一致。真实 Transformer 每层要保存的中间量（Q/K/V、注意力分数、FFN 的 4h 中间层等）远多于 4 份，这是很粗的下界。
  - 否则用 `params × 2 × 0.5` 这个**与 batch、序列长度无关**的经验值：7B → 7 GB、70B → 70 GB、405B → 405 GB。

```python
    if sharding == "fsdp" or sharding == "zero3":
        weight_memory /= num_gpus
        optimizer_memory /= num_gpus
        gradient_memory /= num_gpus
    elif sharding == "zero2":
        optimizer_memory /= num_gpus
        gradient_memory /= num_gpus
    elif sharding == "zero1":
        optimizer_memory /= num_gpus
```

- 这几行就是 ZeRO 三阶段的全部定义：ZeRO-1 只切优化器状态，ZeRO-2 再切梯度，ZeRO-3 / FSDP 连参数也切。
- 激活**不被切分**——这是对的：激活取决于每卡处理的数据，FSDP 不会减少它。但因为默认激活值与参数量挂钩，70B 用 16 卡 FSDP 时 `52.5 + 70 = 122.5 GB`，405B 用 128 卡时激活一项就有 405 GB，表里出现大量 "No"。这与讲义"16 卡即可放下 70B"的说法（不含激活）不同，读表时要注意口径。
- ⚠️ 没有考虑 FSDP 计算时临时 all-gather 出来的整层参数（每卡还要额外容纳"最大一层"的完整权重）。
- 返回一个字典，`fits_on_80gb` 用 `<= 80` 判断。

### 3.5 混合精度对比

```python
    fp16_weights = params * 2
    fp16_master = params * 4
    fp16_optimizer = params * 4 * 2
    fp16_gradients = params * 2
    fp16_total = fp16_weights + fp16_master + fp16_optimizer + fp16_gradients   # 16 字节/参数

    mixed_weights = params * 2
    mixed_optimizer = params * 4 * 2
    mixed_gradients = params * 2
    mixed_total = mixed_weights + mixed_optimizer + mixed_gradients             # 12 字节/参数
```

- `fp32_total = 4 + 8 + 4 = 16` 字节/参数，7B → 112 GB。
- `fp16_total` 包含 master 权重，也是 16 字节/参数，7B → **112 GB**——与 FP32 相同！但它没有被打印。
- `mixed_total` 是 12 字节/参数（84 GB），打印的 "Savings=25%" 来自它。
- ⚠️ 讲义把 84 GB 一行标为 "Mixed (BF16 + FP32 master)"，但计算里并没有 master 权重。标准混合精度训练在**模型状态**上不省显存；它省的是激活（16 位保存）、通信（16 位梯度）和计算时间（tensor core）。详见测验 Q9。

### 3.6 通信量估算

```python
    gradient_size_gb = params * 2 / 1e9

    if strategy == "data_parallel":
        allreduce_volume = 2 * gradient_size_gb * (num_gpus - 1) / num_gpus
    elif strategy == "fsdp":
        allgather_volume = params * 2 / 1e9 * (num_gpus - 1) / num_gpus
        reducescatter_volume = gradient_size_gb * (num_gpus - 1) / num_gpus
    elif strategy == "tensor_parallel":
        ... "per_step_gb": gradient_size_gb * 0.01,
```

- DP：ring all-reduce 每卡 `2(N−1)/N × G`。70B、8 卡：`2 × 140 × 7/8 = 245 GB`。正确。
- ⚠️ FSDP：只算了一次 all-gather + 一次 reduce-scatter，结果也是 245 GB。但 FSDP 前向和反向**各 all-gather 一次**参数，应为 `3 × 140 × 7/8 = 367.5 GB`（DP 的 1.5 倍）。讲义正文说 FSDP 通信"比普通 DP 高"，`outputs/` 的提示词写 "~3 x weight_size"，都与代码不一致。
- ⚠️ TP 的 `× 0.01` 是没有依据的魔法数；`ops_per_step` 也从未被打印。

### 3.7 训练成本估算

```python
    flops_total = 6 * params * tokens
    flops_per_gpu_per_sec = spec["tflops_bf16"] * 1e12 * utilization

    if num_gpus is None:
        mem = memory_calculator(params_billions, sharding="fsdp", num_gpus=1)
        num_gpus = max(1, int(np.ceil(mem["per_gpu_total_gb"] / spec["memory_gb"])) * 2)

    verify = memory_calculator(params_billions, sharding="fsdp", num_gpus=num_gpus)
    while verify["per_gpu_total_gb"] > spec["memory_gb"]:
        if verify["activations_gb"] >= spec["memory_gb"]:
            break
        num_gpus *= 2
        verify = memory_calculator(params_billions, sharding="fsdp", num_gpus=num_gpus)
    fits_in_gpu_memory = verify["per_gpu_total_gb"] <= spec["memory_gb"]

    total_gpu_seconds = flops_total / (flops_per_gpu_per_sec * num_gpus)
    total_gpu_hours = total_gpu_seconds / 3600
    wall_clock_hours = total_gpu_hours
    total_cost = wall_clock_hours * num_gpus * spec["cost_per_hour"]
```

- **6ND**：每个 token 前向约 2N FLOPs（每个参数一次乘加），反向约 4N，合计 6N。
- 有效算力 = 峰值 BF16 TFLOPS × 利用率（默认 0.4，即 MFU 40%）。H100 用 990 TFLOPS（稠密 BF16）。
- 未给 `num_gpus` 时用显存估算卡数，再用 `while` 循环翻倍直到放得下；如果激活一项就超过单卡显存，翻倍也无济于事，于是 `break`。
- ⚠️ **变量命名误导**：`total_gpu_seconds` 已经除以了卡数，其实是**墙钟秒数**；`total_gpu_hours` 也是墙钟小时，所以下一行直接赋给 `wall_clock_hours`。返回字典里的 `"total_gpu_hours"` 又乘回 `num_gpus`，这次才是真正的 GPU 小时。数值都对，但读代码时容易绕晕。
- ⚠️ `__main__` 第四行 `(671, 14.8, "h100", 2048)` 对照的是 DeepSeek-V3，但把 MoE 的总参数 671B 代入 `6ND`，应使用激活参数 37B（讲义："activates only 37B out of 671B parameters per token"）。用 37B 重算约 46.9 天、约 $8.07M。
- `fits_in_gpu_memory` 被计算但没有打印；405B、671B 都是 False（默认激活估算过大）。

### 3.8 `__main__`：演示脚本

- `np.random.seed(42)`：固定随机数，保证结果可复现。
- 打印用 f-string 格式符对齐成表格，例如 `{params:>6}B`、`{result['per_gpu_total_gb']:>8.1f}GB`、`{bubble:.1%}`、`${result['estimated_cost']:,.0f}`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 for 循环模拟多卡 | 无需 GPU 就能验证"切分后数学结果不变" | 看不到并发与通信时延；生产用 `torch.distributed` + NCCL |
| 张量并行只演示 column-parallel | 拼接最直观，误差恰为 0 | 没有 row-parallel 和激活通信；Megatron-LM 中两者成对使用 |
| GPipe 式流水线、反向耗时 = 前向 | 依赖关系简单，公式漂亮 | 真实反向约 2 倍；生产多用 1F1B / interleaved 调度降低激活峰值 |
| 显存按 12 字节/参数 | 与讲义表格一致、易于心算 | 漏了 FP32 master 权重，标准口径 16 字节/参数 |
| 激活默认 `params × 1` 字节 | 没有模型结构时给个数 | 与 batch、序列长度无关，大模型时严重偏大；应按层结构与序列长度估算，并考虑 activation checkpointing |
| FSDP 通信按 1 次 all-gather | 简化 | 少算一次反向 all-gather，低估约 1/3 |
| 成本按 `6ND` + 固定利用率 | 业界常用的一阶估算 | MoE 必须用激活参数；MFU 需实测；不含实验与失败重跑成本 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 整除与取余 | `batch_size // num_gpus`、`batch_size % num_gpus` | `//` 向下取整除法，`%` 取余数 |
| 条件表达式 | `extra = 1 if gpu_id < remainder else 0` | 一行内的 if-else，返回一个值 |
| 切片 | `data[offset:offset + shard_size + extra]`、`weight_matrix[:, start:end]` | 前者取行区间；后者 `:` 表示所有行、`start:end` 表示列区间 |
| 元组解包 | `d_in, d_out = weight_matrix.shape`、`loss, grad = model_fn(shard)` | 一次接收多个返回值 |
| 函数作为参数 | `simulate_data_parallelism(data, n_gpus, model_fn)` | Python 中函数是一等对象，可以传来传去 |
| 闭包 | `model_fn` 内部使用外层的 `weight` | 内层函数可以读取定义时外层作用域的变量 |
| `assert` + f-string | `assert d_out % num_gpus == 0, f"d_out {d_out} ..."` | 条件不满足时抛出 `AssertionError` 并给出信息 |
| 元组作字典键 | `timeline[(stage, mb, "fwd")] = (start_time, end_time)` | 元组不可变、可哈希，适合做复合键 |
| `dict.get(key, default)` | `timeline.get((stage, mb - 1, "fwd"), (0, 0))[1]` | 键不存在时返回默认值，避免 `KeyError` |
| 生成器表达式 | `max(v[1] for v in timeline.values())` | 不建列表、逐个产出值交给 `max` |
| 倒序 `range` | `range(num_microbatches - 1, -1, -1)` | 从 M−1 递减到 0 |
| `in` 判断键 | `(stage, mb + 1, "bwd") in timeline` | 字典成员检测是 O(1) |
| 带默认值的关键字参数 | `memory_calculator(params_billions, precision_bytes=2, optimizer="adam", ...)` | 调用时可只传需要改的参数，如 `sharding="fsdp"` |
| 原地运算符 | `weight_memory /= num_gpus`、`num_gpus *= 2` | 等价于 `x = x / n`、`x = x * 2` |
| 链式比较与布尔值 | `"fits_on_80gb": per_gpu_total / 1e9 <= 80` | 比较表达式本身就是 `True/False`，可直接存入字典 |
| 嵌套字典 | `gpu_specs = {"a100": {"tflops_bf16": 312, ...}, ...}` | 用字典做简单的配置表 |
| `while` + `break` | `while verify[...] > spec[...]: if ...: break` | 条件循环；`break` 提前退出 |
| 科学计数法字面量 | `1e9`、`1e12` | 浮点数 10⁹、10¹² |
| NumPy 规约 | `np.mean(gpu_gradients, axis=0)`、`np.abs(...).max()` | 把 list of arrays 当作多一维的数组沿 axis 规约 |
| `np.concatenate` | `np.concatenate(partial_results, axis=-1)` | 沿最后一维拼接多个数组 |
| `np.ceil` / `int()` | `int(np.ceil(x / 80)) * 2` | 向上取整后转为整数 |
| f-string 格式符 | `{loss:.4f}`、`{error:.2e}`、`{bubble:.1%}`、`{n_mb:2d}`、`{shard:>8}`、`{cost:,.0f}` | 小数位、科学计数、百分比、宽度、右对齐、千分位 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行演示；被 `import` 时不执行，便于复用函数 |

---

## 6. 运行结果解读

实际运行（Python 3 + NumPy 2.5，`np.random.seed(42)`，耗时约 2.5 秒）：

```text
DATA PARALLELISM SIMULATION
  1 GPUs: loss=30.2175, grad_norm=53.0517
  2 GPUs: loss=30.2175, grad_norm=53.0517
  4 GPUs: loss=30.2175, grad_norm=53.0517
  8 GPUs: loss=30.2175, grad_norm=53.0517      ← 64 能被 1/2/4/8 整除，平均后与单卡相同

TENSOR PARALLELISM SIMULATION
  1 GPUs: output_shape=(4, 8192), max_error=0.00e+00
  ...
  8 GPUs: output_shape=(4, 8192), max_error=0.00e+00   ← 按列切分是精确的

PIPELINE PARALLELISM SIMULATION
   1 micro-batches: total_time=  64, bubble=75.0%      ← 3/4
   4 micro-batches: total_time= 112, bubble=42.9%      ← 3/7
   8 micro-batches: total_time= 176, bubble=27.3%      ← 3/11
  16 micro-batches: total_time= 304, bubble=15.8%      ← 3/19（讲义写 18.75%）
  32 micro-batches: total_time= 560, bubble=8.6%       ← 3/35

MEMORY CALCULATOR
     Model Sharding  GPUs    Per-GPU  Fits 80GB
       7B     none     1     91.0GB         No     ← 84 状态 + 7 "激活"
       7B     fsdp     8     17.5GB        Yes     ← 84/8 + 7
      70B     none     1    910.0GB         No
      70B     fsdp     8    175.0GB         No     ← 讲义的 105 GB + 70 GB 激活
      70B     fsdp    16    122.5GB         No     ← 讲义说 16 卡可行（不含激活）
     405B     fsdp    64    480.9GB         No     ← 激活一项就 405 GB
     405B     fsdp   128    443.0GB         No

MIXED PRECISION COMPARISON
  7B: FP32=112GB, Mixed BF16=84GB, Savings=25%     ← 未计 FP32 master；计入后为 112GB、节省 0%
  13B: FP32=208GB, Mixed BF16=156GB, Savings=25%
  70B: FP32=1120GB, Mixed BF16=840GB, Savings=25%
  405B: FP32=6480GB, Mixed BF16=4860GB, Savings=25%

COMMUNICATION VOLUME
  Data Parallel (Ring AllReduce)               Per-step volume: 245.0 GB
  FSDP (AllGather + ReduceScatter per layer)   Per-step volume: 245.0 GB   ← 应约 367.5 GB
  Tensor Parallel (AllReduce per layer)        Per-step volume: 1.4 GB     ← 魔法数 0.01

TRAINING COST ESTIMATES
     Model   Tokens   GPUs     Days           Cost
       8B   15.0T    512      41d     $1,767,677
      70B   15.0T   2048      90d    $15,467,172
     405B   15.0T  16384      65d    $89,488,636   ← 与讲义"约 1 亿美元"同量级
     671B   14.8T   2048     850d   $146,287,037   ← 用了总参数；按 37B 激活参数约 47 天、$8.07M
```

逐项解读：

- **数据并行**：四行完全相同，验证了"切分 + 平均 = 全 batch"。但演示刻意选了能整除的卡数；换成 3 卡会得到 30.2035（见 3.1 节）。grad_norm 53.05 是真实梯度的 16 倍（`model_fn` 的缩放错误）。
- **张量并行**：误差严格为 0，因为按列切分不改变任何一个输出元素的计算顺序。如果改成按行切分再求和，会出现约 1e-13 量级的浮点误差（求和顺序变了；我们在同样形状上实测 4 卡 row-parallel 的最大误差为 2.6e-13）。
- **流水线**：`total_time = 2 × 8 × (M + 3)`，空泡 `3/(M+3)`。M 从 1 增加到 32，空泡从 75% 降到 8.6%，代价是要同时缓存更多 micro-batch 的激活。
- **显存表**：只有 7B + 8 卡 FSDP 能放下。这里大量 "No" 主要源于默认激活估算（与参数量挂钩、不随卡数缩小）。讲义"70B 需要 16 卡"的结论是**不含激活**的口径：840/16 = 52.5 GB。
- **混合精度**：恒为 25%，因为 `12/16` 与模型大小无关。真正的混合精度（带 master 权重）在模型状态上不省显存。
- **通信量**：DP 的 245 GB 正确；FSDP 少算了一次 all-gather。
- **成本**：405B 的 3.65e25 FLOPs 与 40% 利用率，得到约 65 天、约 $89.5M。671B 一行把 MoE 当稠密模型算，是本文件最显眼的错误。

---

## 7. 动手改一改

1. **修正数据并行的加权平均**：把 `np.mean` 换成按分片样本数加权，再用 `n_gpus in [3, 5, 7]` 验证与单卡完全一致；顺手把 `model_fn` 的梯度除以 `len(batch) * output.shape[1]`，用有限差分检查。
2. **加入 FP32 master 权重**：给 `memory_calculator` 加参数 `master_weights=True`（+4 字节/参数），并让 `mixed_precision_comparison` 打印 `fp16_with_master_gb`。观察"节省 25%"如何变成 0%。
3. **讲义练习 1：激活检查点**：给 `memory_calculator` 加 `checkpoint_every_k` 参数，只保存每 K 层的输入，其余在反向时重算；输出显存节省与"约多 33% 计算量"的权衡表。
4. **讲义练习 2：1F1B 调度**：改写 `simulate_pipeline_parallelism` 的反向依赖，让每个 stage 在完成 warmup 前向后交替执行一次前向、一次反向；同时统计每个 stage **同时在飞的 micro-batch 数**（激活峰值），与 GPipe 对比 4 stage、8 micro-batch 的情形。
5. **修正通信与成本估算**：FSDP 通信改为 3 次 `(N−1)/N × 参数字节`；给 `training_cost_estimator` 增加 `active_params_billions` 参数，用 37B 重算 DeepSeek-V3，并增加 `"h800"` 型号。
6. **讲义练习 5：ZeRO-Offload**：增加 `offload="cpu"` 选项，把优化器状态从每卡显存中移到每节点 512 GB 的 CPU 内存，求 70B 模型的最少卡数，并在成本估算中给优化器步骤加 30%–50% 的时间惩罚。

---

## 8. 常见坑

- **只算权重不算优化器状态**：Adam 的 m、v（FP32）是权重（BF16）的 4 倍，是显存大头。
- **以为混合精度能把显存减半**：有 FP32 master 权重时，模型状态显存与 FP32 训练相同；省的是激活、通信和时间。
- **以为数据并行能放下更大的模型**：DP 每卡都是完整副本，显存问题要靠 FSDP/ZeRO、TP、PP 解决。
- **FSDP 只切模型状态，不切激活**：长序列时激活往往才是瓶颈，需要 activation checkpointing、序列并行或更小的 micro-batch。
- **TP 跨节点**：每层都要通信，跨 InfiniBand 会把计算拖慢数倍；TP 一般 ≤ 8 且留在节点内。
- **空泡公式口径混用**：`(N−1)/M` 是空泡与计算的比值，`(N−1)/(M+N−1)` 才是空闲时间占比。
- **分片不等大时简单平均**：均值的均值 ≠ 全局均值。
- **MoE 成本按总参数算**：`6ND` 里的 N 应是每个 token 实际参与计算的参数量。
- **GB 与 GiB 混用**：讲义"64MB × 32 层 × batch 8 = 16GB"按 2 的幂计算，`memory_calculator` 用 1e9 作 GB，会得到 17.18 GB。
