# 测验 · ZeRO Optimizer 状态分片（ZeRO Optimizer State Sharding）

> **阶段 19 · 综合项目 · 第 78 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（测试：[tests/test_zero.py](../tests/test_zero.py)） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 训练显存的组成 | 混合精度 + Adam：fp16 参数 2P、fp16 梯度 2P、fp32 主参数 4P、fp32 一阶矩 4P、fp32 二阶矩 4P，共 **16P 字节** |
| 2 | 为什么先分片优化器状态 | 12P 的优化器状态是最大的一项，而且只在 `step` 时用到，前向/反向不需要它 |
| 3 | ZeRO-1 | 每个 rank 只保存 1/N 的 fp32 主参数和 Adam 矩，显存 `4P + 12P/N`；N = 8 时 5.5P，下降约 65.6% |
| 4 | ZeRO-1 的一步 | 反向 → **reduce_scatter** 梯度（每个 rank 只拿自己分片的梯度和）→ 本地对分片做 Adam → **allgather** 更新后的参数分片 |
| 5 | 通信量不变 | allreduce = reduce_scatter + allgather；ZeRO-1 只是让后半段传"更新后的参数"而不是"求和后的梯度"，总字节数与 DDP 相同 |
| 6 | ZeRO-2 / ZeRO-3 | ZeRO-2 再分片梯度（`2P + 14P/N`）；ZeRO-3（FSDP FULL_SHARD）连参数也分片（`16P/N`），代价是每层前向/反向都要 allgather，通信约为 DDP 的 1.5 倍 |
| 7 | 扁平化 | 把所有参数拼成一个连续向量，按 rank 切片；长度不能整除时补零 |
| 8 | Adam 是逐元素的 | 每个元素的更新只依赖它自己的梯度和矩，所以在分片上独立做 Adam 与在全量上做完全等价 |
| 9 | 跨分片的全局量 | 梯度裁剪需要全局范数：各 rank 算本分片的平方和，allreduce 求和后开方 |
| 10 | 本节实现的简化 | 全程 fp32（没有 fp16 参数/梯度），主参数分片与模型自身的 fp32 参数**重复**；每步仍会分配全长的梯度/参数临时缓冲区 |

### 核心技能（能动手做到）

- [ ] 写出任意 P、N 下 DDP、ZeRO-1/2/3 的每 rank 显存公式，并代入 7B 模型计算
- [ ] 解释为什么 ZeRO-1 的通信量与 DDP 相同，而 ZeRO-3 更多
- [ ] 用 `reduce_scatter` + 分片 Adam + `all_gather` 实现 ZeRO-1，并与 `torch.optim.Adam` 单进程参考对拍
- [ ] 在 ZeRO-1 下实现全局梯度裁剪
- [ ] 指出本节代码与讲义在精度（fp16/fp32）、显存表、函数名上的不一致
- [ ] 找出 `shard_bounds` 在小张量上返回 `start > end` 的边界问题

---

## 二、基础自测（选择题）

**Q1.** ZeRO 首先选择分片优化器状态，而不是参数，最主要的原因是：

- A. 混合精度 Adam 下优化器状态（fp32 主参数 + 两个矩，共 12P 字节）是显存中最大的一项，而且只在 `step` 时才被访问
- B. 参数无法被切分
- C. 优化器状态比参数更重要
- D. 分片参数不能节省显存

**Q2.** 混合精度 + Adam，按讲义的公式，ZeRO-1 在 N = 8 时每个 rank 的显存是多少？相对 DDP 下降多少？

- A. 2P，下降 87.5%
- B. 4P，下降 75%
- C. 14P，下降 12.5%
- D. 5.5P，下降约 65.6%

**Q3.** 模块 docstring 写道"the full fp16 gradient is reduce_scattered ... the updated fp16 parameter shards are allgathered"。阅读代码，实际在 `reduce_scatter` 和 `all_gather` 中传输的数据类型是：

- A. 梯度 fp16、参数 fp16
- B. 梯度 fp16、参数 fp32
- C. 梯度和参数都是 fp32——模型本身就是 fp32，`gather_flat_grads` 转成 fp32，`all_gather` 的是 fp32 的 `master_shard`
- D. 梯度 bf16、参数 fp32

**Q4.** demo 输出 `optim_shard_bytes=5196`（`MiniMLP` 共 1,732 个参数，N = 4）。这个数字是怎么来的？

- A. `1,732 × 4 = 6,928` 减去补零部分：一份完整 fp32 参数扣掉 padding 后的大小
- B. 每个 rank 的分片长度 `1,732 / 4 = 433`，主参数、m、v 三个 fp32 张量：`433 × 3 × 4 = 5,196`
- C. `1,732 × 3 = 5,196`，每个元素 1 字节
- D. `12P / N + 4P = 12,124` 中的优化器部分

**Q5.** 关于 ZeRO-1 与 DDP 每步通信量的比较，正确的是：

- A. 相同：ring allreduce 本身就是 reduce_scatter + allgather；ZeRO-1 做的也是这两个操作，只是 allgather 传的是更新后的参数
- B. ZeRO-1 是 DDP 的 1/N，因为每个 rank 只拿一个分片
- C. ZeRO-1 是 DDP 的 2 倍，因为多了一次 allgather
- D. ZeRO-1 不需要任何通信

**Q6.** `ZeroOptimizer.step` 中 `dist.reduce_scatter(local_grad, chunks, op=SUM)` 之后紧跟 `local_grad.div_(self.world_size)`。去掉这一行会怎样？

- A. 各 rank 的参数会不一致
- B. 梯度变成 N 个 rank 梯度的**和**；对 Adam 而言 `m / sqrt(v)` 对梯度的整体缩放几乎不敏感，但 `eps` 的相对作用、梯度裁剪阈值等都会随 N 变化，与单卡/DDP 的语义不再一致
- C. 程序会因为数值溢出崩溃
- D. 没有任何影响，因为 Adam 完全不受梯度缩放影响

**Q7.** 关于 ZeRO-3（FSDP `FULL_SHARD`），下列说法正确的是：

- A. 它的通信量与 ZeRO-1 完全相同
- B. 它只分片参数，不分片优化器状态
- C. 参数也被分片，前向每层要 allgather 参数，反向时还要再 allgather 一次并 reduce_scatter 梯度，总通信约为 DDP 的 1.5 倍
- D. 它不需要 reduce_scatter

**Q8.** `shard_bounds(5, 4, 3)` 的返回值是 `(6, 5, 2)`。这说明：

- A. 函数正确，rank 3 的分片是第 5～6 个元素
- B. 函数会抛出异常
- C. 补零后总长度变为 6
- D. 补零后每个分片长 2，rank 3 的 `start = 6` 已经超过 `total = 5`，出现 `start > end`；任何用 `[start:end]` 取真实元素的代码都会得到空切片——当每片长度很小时，最后一个（或几个）rank 的分片可能完全落在补零区

---

## 三、动手 / 代码题

**Q9.** 本节没有把 ZeRO-1 与任何参考实现对拍，只检查了"各 rank 的参数范数相同"和"loss 下降"。

1. 写一个单进程参考：用 `torch.optim.Adam(lr=0.05)`，每步依次处理 4 个 rank 的分片、loss 除以 4 累加梯度。ZeRO-1 的结果应与它一致到什么程度？
2. 为什么"每个 rank 只对自己的 1/N 分片做 Adam"在数学上与"对全部参数做 Adam"完全等价？什么样的优化器**不能**这样简单地分片？

**Q10.** 讲义练习 4：在 ZeRO-1 下实现梯度裁剪（`max_norm = 1.0`）。每个 rank 只有自己分片的梯度，怎样得到与 `torch.nn.utils.clip_grad_norm_` 相同的全局范数？写出 `step()` 中需要插入的代码。

**Q11.** 对照讲义与代码回答：

1. 列出至少四处不一致（提示：fp16、显存表的标题、7B 模型的优化器状态是 28 GB 还是 56 GB、函数名、demo 输出）。
2. 本节代码**实际**每个 rank 持有多少 fp32 字节（模型参数 + 梯度 + 优化器分片）？与"单卡 fp32 Adam"（参数 + 梯度 + m + v）相比节省了多少？如果去掉"主参数分片"这份冗余拷贝呢？（P = 1,732，N = 4）

**Q12.** 讲义练习 1 说："Extend to ZeRO-2 by sharding gradients: each rank only stores the gradient for its shard, achieved by zeroing out the non-shard portion after backward." 这种做法真的能省显存吗？真正的 ZeRO-2 应该怎么做？

---

## 四、面试高频题

**Q13.**（基础必考）ZeRO-1、ZeRO-2、ZeRO-3 分别分片什么？每 rank 显存各是多少？

**Q14.**（原理深挖）为什么 ZeRO-1/2 的通信量与 DDP 相同，而 ZeRO-3 是 1.5 倍？为什么用 reduce_scatter 而不是"allreduce 后再丢掉不要的部分"？

**Q15.**（工程实践）用 8 张 80 GB GPU 全参数训练一个 7B 模型（混合精度 + Adam），DDP 放得下吗？ZeRO-1/2/3 分别需要多少显存（不计激活）？你会选哪个 stage？

**Q16.**（场景设计）ZeRO 训练中途要保存 checkpoint，恢复时集群从 8 卡变成了 16 卡。你怎么设计 checkpoint 格式和恢复流程？

**Q17.**（追问型）混合精度训练为什么要保留一份 fp32 主参数？如果不用混合精度直接用 ZeRO，会怎样？bf16 训练还需要 fp32 主参数吗？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："The optimiser state is the largest term and the easiest to shard because it is only touched during the step, not during forward or backward." 分片优化器状态不影响前向/反向的任何计算，只在 step 前后各多一次通信（且总量与 DDP 相同），是"性价比最高"的显存优化。

- B：参数可以切分（ZeRO-3 就是这么做的）；
- C：不是"重要性"问题；
- D：分片参数同样能省显存，只是需要更多通信。

### Q2 — 答案：D

`2P（fp16 参数）+ 2P（fp16 梯度）+ 12P/8 = 5.5P`；`(16 − 5.5) / 16 = 65.6%`。代码 `memory_table(7_000_000_000, 8)` 的输出：vanilla 112,000,000,000 字节，ZeRO-1 38,500,000,000 字节，drop 65.6%。

- A（2P）是 ZeRO-3 在 N = 8 时的 `16P/8`；
- B（4P）是 N → ∞ 时 ZeRO-1 的下限（参数 + 梯度）；
- C 无依据。

N = 4（demo）时是 `4P + 3P = 7P`，下降 56.2%；N = 64 时 4.19P，下降 73.8%。

### Q3 — 答案：C

`MiniMLP()` 默认 fp32；`gather_flat_grads` 把梯度 `.to(torch.float32)`；`padded_grad` 是 fp32；`master_shard` 是 fp32，`dist.all_gather(gathered, self.master_shard)` 传的是 fp32。代码里根本没有 fp16。`memory_table` 却按"fp16 参数 + fp16 梯度"计算——显存表描述的是**理想的混合精度方案**，不是这份代码的实际情况。这也意味着 allgather 的字节数是混合精度方案的两倍。

### Q4 — 答案：B

`shard_bounds(1732, 4, r)` 得到每片 433（1,732 恰好能被 4 整除，不补零）。`shard_bytes()` = `(master_shard + m_shard + v_shard 的元素数) × 4 = 433 × 3 × 4 = 5,196`。四个 rank 都是 5,196。

- A：1,732 能被 4 整除，根本没有补零；而且 6,928 是一份完整 fp32 参数的大小，ZeRO-1 的意义恰恰是每个 rank 只存 1/N。注意当长度不能整除时，每片长度向上取整、含补零，`shard_bytes` 会略大于 `12P/N`；
- C 把 fp32 当成 1 字节；
- D 的 12,124 是 `memory_table` 中 ZeRO-1 的**总**显存（含 fp16 参数和梯度的 4P = 6,928），优化器部分是 `12P/N = 5,196`。

### Q5 — 答案：A

讲义："The wire traffic per step is the same as DDP: one reduce_scatter plus one allgather equals one allreduce by bandwidth." 每 rank 发送：reduce_scatter `T(N−1)/N` + allgather `T(N−1)/N` = `2T(N−1)/N`，与 ring allreduce 相同。

- B：每个 rank 拿到 1/N，但发送量不是 1/N；
- C：DDP 的 allreduce 内部就包含了一次 allgather；
- D 显然错误。

### Q6 — 答案：B

去掉除法后，梯度是平均梯度的 N 倍。Adam 的更新 `m̂ / (sqrt(v̂) + eps)` 中，梯度整体乘以常数 c，`m̂` 乘 c、`sqrt(v̂)` 也乘 c，比值基本不变——只有 `eps` 的相对大小变了。所以对本节的 Adam，影响很小；但一旦加上梯度裁剪（阈值是绝对值）、weight decay 的相对强度、或者换成 SGD，结果就会随 N 改变，失去"与单卡/DDP 等价"的性质。

- A：所有 rank 都去掉了除法，仍然一致；
- C：不会溢出；
- D 过于绝对，`eps` 和裁剪都会受影响。

### Q7 — 答案：C

ZeRO-3 每个 rank 只存 1/N 参数。前向时每层先 allgather 出完整参数、用完释放；反向时需要再 allgather 一次（因为前向后已经释放），算完梯度后 reduce_scatter。共两次 allgather + 一次 reduce_scatter，即 `3 × T(N−1)/N`，是 DDP `2 × T(N−1)/N` 的 1.5 倍（ZeRO 论文的结论）。讲义表格写的是"1x allgather per layer + 1x reduce_scatter per layer"，没有计入反向时的重新 allgather，是一种简化。

- A、D 错误；B 说反了：ZeRO-3 是在 ZeRO-2 的基础上**再**分片参数。

### Q8 — 答案：D

`total = 5, world_size = 4`：`pad = 3`，`padded = 8`，`chunk = 2`；rank 3：`start = 6`，`end = min(8, 5) = 5`。`start > end`，`flat[6:5]` 是空切片。rank 2 是 `(4, 5)`，只有 1 个真实元素。这个函数的测试 `test_shard_bounds_handles_padding` 只检查了 `s3[1] <= 17`，没有发现问题。

在本节中 `ZeroOptimizer` 只把 `shard_start/shard_end` 存起来、实际切片用的是 `rank * chunk` 和补零后的张量，所以没有引发错误；但这个返回值的语义是误导性的。正确写法应是 `start = min(rank * chunk, total)`，或者直接只返回补零后的 `(rank * chunk, (rank + 1) * chunk)`，并说明后面要截断到 `total`。

- A、B、C 都与实际计算不符。

### Q9 — 参考答案

1. 参考实现：

```python
def reference_adam(ws=4, steps=20, batch=8, lr=0.05):
    torch.manual_seed(SEED)
    model = MiniMLP()
    opt = torch.optim.Adam(model.parameters(), lr=lr, betas=(0.9, 0.999), eps=1e-8)
    loss_fn = nn.MSELoss()
    x_all, y_all = make_dataset(SEED + 1000, ws * batch * steps)
    losses = []
    for step in range(steps):
        opt.zero_grad()
        for r in range(ws):
            o = step * ws * batch + r * batch
            loss = loss_fn(model(x_all[o:o + batch]), y_all[o:o + batch]) / ws
            loss.backward()
            if r == 0:
                l0 = loss.item() * ws
        opt.step()
        losses.append(l0)
    return losses
```

我们实测：ZeRO-1 rank 0 的 20 步 loss 与参考的最大差 **1.43e-6**，最终范数 11.21324224 vs 11.21324214。差异来自浮点运算顺序（gloo 求和、`torch.optim.Adam` 内部 `sqrt(v)/sqrt(bc2) + eps` 的写法与本节 `sqrt(v/bc2) + eps` 在舍入上略有不同），数学上等价。

2. **等价性**：Adam 的每一步只用到同一位置的 `g_i, m_i, v_i, θ_i`，更新公式对每个元素独立：`m_i ← β1·m_i + (1−β1)·g_i`，`v_i ← β2·v_i + (1−β2)·g_i²`，`θ_i ← θ_i − lr·m̂_i/(sqrt(v̂_i)+eps)`。把参数向量任意切分，各段独立更新，拼起来与整体更新完全相同。bias correction 只依赖步数，各 rank 的 `step_count` 相同。
   
   **不能简单分片的优化器**：需要跨元素统计量的优化器，例如 LAMB/LARS（需要逐层的参数范数与更新范数之比）、Adafactor（对矩阵做行/列因子分解）、Shampoo 等二阶方法（需要整块矩阵的预条件子）；以及任何依赖全局梯度范数的操作（如梯度裁剪，见 Q10）。这些都需要额外的 allreduce 来求跨分片的统计量，或者按"层/矩阵"而不是按扁平元素切分。

### Q10 — 参考答案

在 reduce_scatter 并除以 N 之后、Adam 更新之前插入：

```python
        local_grad.div_(self.world_size)
        # —— 全局梯度裁剪 ——
        sq = local_grad.pow(2).sum()                 # 本分片的平方和（补零部分贡献 0）
        dist.all_reduce(sq, op=dist.ReduceOp.SUM)    # 所有分片求和 = 全量梯度的平方和
        total_norm = sq.sqrt().item()
        max_norm = 1.0
        if total_norm > max_norm:
            local_grad.mul_(max_norm / (total_norm + 1e-6))
        # —— 之后照常做 Adam ——
```

要点：

- 各分片互不重叠且覆盖全部元素，所以 `Σ_r ‖g_r‖² = ‖g‖²`；只需 allreduce 一个标量，通信可忽略。
- 必须在**平均之后**的梯度上计算（与 DDP/单卡语义一致）。
- 每个 rank 得到相同的 `total_norm`，缩放系数相同。
- 我们实测（4 rank、10 步、`max_norm = 1.0`）：每步全局范数与单进程 `clip_grad_norm_` 的返回值完全一致（前 4 步均为 1.4124、1.4283、2.5679、3.0314），10 步后参数最大差 1.3e-7。

### Q11 — 参考答案

1. 不一致之处：
   - **精度**：docstring 和讲义都说 reduce_scatter fp16 梯度、allgather fp16 参数分片，代码全程 fp32（见 Q3）。讲义自己也说"Running ZeRO without mixed precision pays the memory tax on the fp32 master without the corresponding fp16 forward win"——这正是本节代码的情况。
   - **显存表**：`memory_table` 的标题是 "per-rank optimiser memory"，但数值包含 fp16 参数与梯度（总显存）；而且按混合精度计算，与代码实际的 fp32 布局不符。
   - **7B 的数字**：讲义开头说 7B 模型 Adam 两个矩"56 GB"（`2 × 4 × 7e9`，正确）；"The Problem"一节却说"28 GB of optimiser state"；按讲义自己的表格（主参数 + 两个矩 = 12P），优化器状态应是 84 GB。
   - **函数名**：讲义写 `flatten_params / unflatten_into`，代码是 `gather_flat_params / scatter_flat_to_params`（另有 `gather_flat_grads`）。
   - **demo 输出**：讲义说"prints the per-step memory budget alongside a vanilla DDP baseline"，代码只在最后打印一次显存表，没有 DDP 基线的 loss 对比；docstring 说"Compare per-step loss with vanilla DDP (lesson 77)"，但两节的 SEED（13 vs 7）和优化器（Adam vs SGD）都不同，无法直接比较。
   - **ZeRO-3 通信**：表格漏了反向的重新 allgather（见 Q7）。
2. 实际 fp32 字节（P = 1,732，N = 4，`4P = 6,928`）：
   - 本节代码：模型 fp32 参数 `4P = 6,928` + fp32 梯度 `4P = 6,928` + 优化器分片（主参数 + m + v，各 433 个 fp32）`5,196`，合计 **19,052 字节**（即 `8P + 12P/4 = 11P` 字节）。
   - 单卡 fp32 Adam：参数 + 梯度 + m + v = `4 × 6,928 = 27,712` 字节（16P）。节省约 31%。
   - 去掉冗余的主参数分片（纯 fp32 训练时，模型参数本身就是"主参数"，只需分片 m、v）：`6,928 + 6,928 + 2 × 433 × 4 = 6,928 + 6,928 + 3,464 = 17,320` 字节（`8P + 8P/4 = 10P`），节省 37.5%。
   
   结论：没有混合精度时，"fp32 主参数"这份拷贝纯属多余；ZeRO-1 的收益来自分片 m、v。（另外，每步 `step()` 还会临时分配全长的 `flat_grad`、`padded_grad` 和 `gathered`，峰值显存更高——生产实现会复用预分配的扁平缓冲区。）

### Q12 — 参考答案

- **不能省显存**：把非本分片的梯度"置零"，张量仍然存在、大小不变，只是数值为 0。显存节省来自**释放**，而不是清零。
- **真正的 ZeRO-2**：
  - 在反向过程中按桶（bucket）处理梯度：一个桶的梯度就绪后立即 reduce_scatter 到负责该段的 rank，然后**释放**这个桶的全量梯度，只保留本 rank 的分片（`2P/N` 字节）；
  - 每个 rank 只持有一块 `P/N` 的梯度分片缓冲区；梯度累积时也只在分片上累加；
  - 优化器 step 和参数 allgather 与 ZeRO-1 相同。
- 通信量与 ZeRO-1 相同，但实现上需要与反向 hook 配合（梯度"生产"出来就要立刻归约并释放），这正是讲义说的"Stage 2 needs gradient-shard accumulation logic"。
- 对应 PyTorch FSDP 的 `ShardingStrategy.SHARD_GRAD_OP`（讲义："`SHARD_GRAD_OP` is ZeRO-2; `FULL_SHARD` is ZeRO-3"）。

### Q13 — 参考回答要点

| Stage | 分片内容 | 每 rank 显存（混合精度 Adam） |
|-------|---------|-----------------------------|
| DDP | 无 | `16P` |
| ZeRO-1 | 优化器状态（fp32 主参数、m、v） | `4P + 12P/N` |
| ZeRO-2 | 优化器状态 + 梯度 | `2P + 14P/N` |
| ZeRO-3 | 优化器状态 + 梯度 + 参数 | `16P/N` |

- 显存之外还有激活、临时缓冲区、通信桶等；激活通常靠 activation checkpointing 解决。
- 加分点：说出 ZeRO-Offload/Infinity 把优化器状态或参数卸载到 CPU/NVMe；FSDP 是 PyTorch 原生的 ZeRO-3。

### Q14 — 参考回答要点

- **ZeRO-1/2 = DDP**：DDP 的 ring allreduce 本身分两段：reduce_scatter（`T(N−1)/N`）+ allgather（`T(N−1)/N`）。ZeRO-1/2 把这两段拆开：reduce_scatter 梯度后，每个 rank 用自己的梯度分片更新自己的参数分片，再 allgather 参数——第二段传的是"更新后的参数"而不是"求和后的梯度"，字节数相同。
- **ZeRO-3 = 1.5×**：参数也分片，前向需要 allgather 参数（第 1 次），用完释放；反向需要再 allgather（第 2 次），梯度 reduce_scatter（第 3 次）。
- **为什么不 allreduce 再丢弃**：allreduce 让每个 rank 拿到完整的梯度和，其中 `(N−1)/N` 对它没用——它浪费的是**显存**（要容纳完整的归约结果）和**第二段通信的机会**：如果先 allreduce，之后还得再 allgather 一次参数，总通信变为 DDP 的 1.5 倍（讲义练习 5 让你测量这个差距）。
- 常见误区：以为"分片 = 通信变少"。

### Q15 — 参考回答要点

P = 7e9，N = 8，按 16P 字节模型（不计激活）：

| 方案 | 公式 | 每卡显存 |
|------|------|---------|
| DDP | 16P | 112 GB（放不下 80 GB） |
| ZeRO-1 | 4P + 12P/8 = 5.5P | 38.5 GB |
| ZeRO-2 | 2P + 14P/8 = 3.75P | 26.25 GB |
| ZeRO-3 | 16P/8 = 2P | 14 GB |

- 选择：ZeRO-1 已经能放下，但剩余约 40 GB 还要容纳激活（长序列、较大 micro-batch 时激活可能有几十 GB）；ZeRO-2 通信量不变、多省 12 GB，通常是更稳妥的默认；只有在激活很大或想用更大 batch/更长序列时才上 ZeRO-3（多 50% 通信）。
- 讲义观点："Production stacks default to stage 1 unless the parameter shard memory is also a problem; then stage 2 or 3 trades comm for memory."
- 加分点：配合 activation checkpointing、bf16、梯度累积；用实测的显存峰值而不是公式做最终决定。

### Q16 — 参考回答要点

- **格式**：每个 rank 保存自己的优化器分片（主参数、m、v、step 计数），外加一个 manifest：world_size、扁平化的参数顺序与形状、每个 rank 的 `[start, end)`、补零长度、dtype、训练步数、数据加载器状态与随机数状态（第 80 节）。
- **原子性**：先写临时文件，全部 rank 写完后由 rank 0 写 manifest 并原子重命名，避免半成品 checkpoint。
- **相同 world size 恢复**：每个 rank 按 manifest 读回自己的分片。
- **不同 world size（8 → 16）**：用 manifest 把 8 个分片按偏移拼回完整的扁平向量（逻辑上，不必一次性放进一张卡），再按新的 N = 16 重新切分；或者离线把 checkpoint 转换成"全量格式"再重新分片（DeepSpeed 提供 `zero_to_fp32` 类工具，PyTorch 有 Distributed Checkpoint 的 reshard 能力）。
- **注意**：学习率调度、梯度累积步数要随全局 batch 变化而调整；数据加载器的进度需要按新的 rank 划分重新计算。

### Q17 — 参考回答要点

- **为什么要 fp32 主参数**：fp16 只有约 3～4 位有效十进制数字，`θ − lr·Δ` 中更新量往往比参数小几个数量级，直接在 fp16 上更新会被舍入成 0（更新丢失）；另外 fp16 动态范围小，梯度可能下溢，需要 loss scaling。所以前向/反向用 fp16，step 在 fp32 主参数上做，再拷回 fp16。
- **不用混合精度直接 ZeRO**：模型参数本身就是 fp32，"主参数"与之重复（本节代码就是这样，见 Q11）；显存公式变成 `4P(参数) + 4P(梯度) + 8P/N(m, v)`，若还保留主参数分片则再加 `4P/N`。讲义："Production runs always pair ZeRO with autocast or bf16 weights."
- **bf16**：bf16 动态范围与 fp32 相同，不需要 loss scaling；但有效位数更少（约 2～3 位十进制），纯 bf16 更新同样会丢失小更新，主流做法仍保留 fp32 主参数（或使用随机舍入、Kahan 求和等补偿技术）。
- 加分点：优化器矩用 8-bit 量化（8-bit Adam）可以进一步把 12P 压到约 6P。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 76 从零实现集合通信操作](../../76-collective-ops-from-scratch/docs/zh.md)：reduce_scatter、allgather 的实现与通信量。
- [阶段 19 · 77 从零实现数据并行 DDP](../../77-data-parallel-ddp/docs/zh.md)：ZeRO 是在 DDP 基础上的显存优化。
- [阶段 19 · 45 Gradient Clipping 与 Mixed Precision](../../45-gradient-clipping-amp/docs/zh.md)：混合精度与 fp32 主参数、梯度裁剪。
- [阶段 03 · 06 Optimizers](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：Adam 的一阶/二阶矩与 bias correction。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：ZeRO 在大模型训练中的位置。

### 本节被哪些后续内容用到
- [阶段 19 · 79 流水线并行与流水线气泡分析](../../79-pipeline-parallel/docs/zh.md)：另一条正交的切分维度（按层切）。
- [阶段 19 · 80 分片 Checkpoint 与原子恢复](../../80-checkpoint-sharded-resume/docs/zh.md)：ZeRO 分片状态的保存与恢复。
- [阶段 19 · 81 端到端分布式训练](../../81-end-to-end-distributed-train/docs/zh.md)：DDP + ZeRO 组合。
- [阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../48-distributed-fsdp-ddp/docs/zh.md)：FSDP（ZeRO-3）的实现视角。
- [阶段 10 · 34 Gradient Checkpointing 与激活重计算](../../../10-llms-from-scratch/34-gradient-checkpointing/docs/zh.md)：ZeRO 之后的下一个显存大头——激活。

### 延伸关键词
`ZeRO-1/2/3` · `FSDP SHARD_GRAD_OP / FULL_SHARD` · `fp32 master weights` · `loss scaling` · `ZeRO-Offload / ZeRO-Infinity` · `8-bit Adam` · `flat parameter` · `reduce_scatter_tensor` · `Distributed Checkpoint (DCP)` · `zero_to_fp32`
