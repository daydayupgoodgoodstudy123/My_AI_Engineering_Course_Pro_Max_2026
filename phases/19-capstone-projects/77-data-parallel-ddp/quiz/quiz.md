# 测验 · 从零实现数据并行 DDP（Data Parallel DDP From Scratch）

> **阶段 19 · 综合项目 · 第 77 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（测试：[tests/test_ddp.py](../tests/test_ddp.py)） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 数据并行的本质 | N 个 rank 各持一份完整模型，各算一份数据分片的前向/反向，每步把梯度汇总，让 N 个副本始终相同 |
| 2 | DDP 需要的三个集合操作 | 初始化时从 rank 0 broadcast 参数；反向后 allreduce 梯度；（有 BatchNorm 时）broadcast buffer |
| 3 | 求和再除以 world_size | allreduce-SUM 后 `div_(world_size)` 得到平均梯度；平均梯度的尺度与 rank 数无关 |
| 4 | 与单进程的等价性 | 单进程把 N 个分片依次前向/反向、每个 loss 除以 N 再累加梯度，得到的梯度与 DDP 的平均梯度相同（前提：各分片大小相同） |
| 5 | 初始化 broadcast | 只要从 rank 0 广播参数，各 rank 用什么种子初始化都无所谓；不广播，各副本从第 1 步起就不同 |
| 6 | 分桶（bucket） | 把许多小梯度拼成约 25 MB 的桶，一个桶一次 allreduce，摊薄每次调用的延迟 |
| 7 | 通信/计算重叠 | 反向按层倒序产生梯度，某个桶就绪就立即异步 allreduce，同时继续算前面的层 |
| 8 | `no_sync()` | 梯度累积的前 K−1 个 micro-batch 跳过 allreduce，只在最后一个同步 |
| 9 | `find_unused_parameters` | 前向有条件分支时，部分参数没有梯度；不处理会导致各 rank 的集合调用不匹配而挂起 |
| 10 | 本节实现的简化 | 无 hook、无分桶、无重叠：反向结束后在训练循环里显式调用 `sync_grads()`，逐参数 allreduce（每步 6 次） |

### 核心技能（能动手做到）

- [ ] 用 `torch.distributed`（gloo）+ spawn 启动多个 CPU rank，写出"broadcast 参数 → 前向 → 反向 → allreduce 梯度 → step"的完整循环
- [ ] 写一个单进程参考实现，并证明它与 DDP 每一步等价（loss 与参数都对上）
- [ ] 把逐参数 allreduce 改成"拼成一个扁平桶 → 一次 allreduce → 拆回"
- [ ] 实现 `no_sync()` 上下文管理器，并验证梯度累积与"一个大 batch"等价
- [ ] 估算一个模型每步的梯度通信量与耗时
- [ ] 指出本节讲义与代码在 hook、分桶、种子、输出表格上的不一致

---

## 二、基础自测（选择题）

**Q1.** 本节 `DistributedDataParallel.__init__` 做的唯一一件"分布式"的事情是：

- A. 对每个参数调用 `dist.broadcast(p.data, src=0)`，让所有 rank 从相同的权重出发
- B. 给每个参数注册反向 hook，在梯度就绪时自动 allreduce
- C. 把参数分片，每个 rank 只保存 1/N
- D. 调用 `dist.barrier()` 等待所有 rank 就绪

**Q2.** `sync_grads` 中 allreduce-SUM 之后执行 `p.grad.data.div_(self.world_size)`。讲义给出的主要理由是：

- A. gloo 的 SUM 会溢出，必须除
- B. 除法可以减少下一次通信的字节数
- C. 平均梯度的尺度与 world_size 无关，在 1 个 rank 上调好的学习率换到 4 个 rank 不必重调
- D. 不除的话各 rank 的梯度会不一致

**Q3.** `reference_single_process` 在每一步里对 4 个分片依次执行 `loss = loss_fn(pred, y) / world_size; loss.backward()`，最后才 `optim.step()`。它能与 DDP 逐步等价的原因是：

- A. 单进程用了更大的学习率
- B. 单进程只用 rank 0 的数据
- C. `loss.backward()` 会自动除以 world_size
- D. `.backward()` 默认把梯度**累加**到 `.grad` 上；4 次"loss / 4"的梯度之和 = 4 个分片梯度的平均 = DDP allreduce-SUM 再除以 4

**Q4.** 讲义"Why pin the seed"一节说：如果参数初始化用 rank 相关的种子，"gradient sync no longer makes the replicas identical"。我们把 `_ddp_worker` 的初始化种子改为 `SEED + rank`，其余不变，结果是：

- A. 4 个 rank 的参数从第 1 步起就不一致
- B. 4 个 rank 的参数始终**逐位相同**，rank 0 的 loss 与单进程参考完全一致——因为构造时的 broadcast 已经覆盖了各 rank 自己的初始化
- C. 程序死锁
- D. 只有 rank 0 正确，其余 rank 的 loss 变成 NaN

**Q5.** demo 输出表中有一列 `rank_drift = |ddp_rank0 − ddp_rank3|`，数值在 0.13～5.38 之间。正确的理解是：

- A. 这是 rank 0 与 rank 3 **在各自不同数据分片上**的 loss 之差，本来就应该不同；它不能说明参数是否漂移
- B. 说明梯度同步有 bug，两个 rank 的参数在漂移
- C. 说明 rank 3 的学习率不同
- D. 说明 gloo 的 allreduce 有数值误差

**Q6.** `MiniMLP` 是 `Linear(16,32) → ReLU → Linear(32,32) → ReLU → Linear(32,4)`。它的参数量和每一步 `sync_grads` 发起的 allreduce 次数分别是：

- A. 1,728 个参数，3 次
- B. 1,732 个参数，3 次
- C. 1,732 个参数，6 次
- D. 1,600 个参数，5 次

**Q7.** 关于 PyTorch DDP 的 `no_sync()`，说法正确的是：

- A. 它关闭 DDP，退化为单卡训练
- B. 它让 allreduce 改为异步执行
- C. 它跳过前向计算以节省时间
- D. 在梯度累积的前 K−1 个 micro-batch 中暂停反向后的 allreduce，梯度在本地累加，只在最后一个 micro-batch 同步一次

**Q8.** 假设某个 rank 的前向因为条件分支没有用到第二个 `Linear`，它的 `p.grad` 为 `None`。在本节的 `sync_grads` 中会发生什么？

- A. 什么也不会发生，`if p.grad is None: continue` 已经处理好了
- B. 该 rank 少调用了 2 次 `all_reduce`，各 rank 的集合调用序列错位：后续 allreduce 会与形状不同的张量配对而报错，或者某些 rank 一直等待而挂起
- C. gloo 会自动用 0 填充缺失的梯度
- D. 只是该层的梯度不被平均，其余层不受影响

---

## 三、动手 / 代码题

**Q9.** 当前 `sync_grads` 对每个参数调用一次 `all_reduce`：

```python
    def sync_grads(self) -> None:
        for p in self.module.parameters():
            if p.grad is None:
                continue
            dist.all_reduce(p.grad.data, op=dist.ReduceOp.SUM)
            p.grad.data.div_(self.world_size)
```

请改写为"单桶"版本：把所有梯度拼成一个扁平张量，只做一次 `all_reduce`，再拆回各参数。说明：改写后结果与原版是否逐位相同？为什么？再说说如何扩展成"按容量切成多个桶"。

**Q10.** 讲义练习 2：为本节的 `DistributedDataParallel` 实现 `no_sync()` 上下文管理器，并写出"每个 rank 每步累积 K = 2 个 micro-batch（每个 4 条样本）"的训练循环。你的实现应与"单进程、每步一个 `4 × 2 × 4 = 32` 条样本的大 batch"等价。写出代码，并说明 loss 要怎么缩放。

**Q11.** 对照讲义与代码，找出**至少四处**不一致（提示：hook、bucket、`torch.multiprocessing.spawn`、种子、输出表格、函数名）。并修改 `main()` 的表格，使"漂移"一列真正反映参数在 rank 间是否一致。

**Q12.** 估算通信量（ring allreduce，每 rank 发送 `2T(N−1)/N`，float32）：

1. 本节 `MiniMLP`，N = 4，每一步每个 rank 发送多少字节？
2. 一个 1B 参数的模型在 8 张卡上做 DDP，每步每卡发送多少 GB？若卡间有效带宽 12.5 GB/s（约 100 Gbit），完全不重叠时通信需要多少秒？

---

## 四、面试高频题

**Q13.**（基础必考）讲一下 DDP 一个训练 step 的完整流程。为什么所有 rank 的模型能一直保持一致？

**Q14.**（原理深挖）DDP 为什么用梯度的**平均**而不是**和**？当 GPU 数从 1 增加到 8、全局 batch 变成 8 倍时，学习率需要调整吗？

**Q15.**（工程实践）PyTorch DDP 中 bucket、overlap、`find_unused_parameters`、`static_graph` 分别解决什么问题？有什么代价？

**Q16.**（场景设计）你有 8 张 GPU，单卡只能放 batch 4，但希望全局 batch 为 256。怎么配置 DDP 与梯度累积？数据加载、BatchNorm、随机种子分别要注意什么？

**Q17.**（追问型）你怎么证明自己写的 DDP 是对的？如果训练到一半发现各 rank 的 loss 曲线"看起来一致"但最终模型效果不如单卡，你会怎么排查？

---

## 五、参考答案与解析

### Q1 — 答案：A

```python
    def __init__(self, module: nn.Module, world_size: int):
        self.module = module
        self.world_size = world_size
        self._broadcast_params()

    def _broadcast_params(self) -> None:
        for p in self.module.parameters():
            dist.broadcast(p.data, src=0)
```

- B 是 PyTorch DDP 的真实做法，讲义开头也这么描述（"install a backward hook on every parameter"），但**本节代码没有任何 hook**，而是在训练循环中显式调用 `sync_grads()`；
- C 是 ZeRO/FSDP（第 78 节）；
- D：代码里没有 barrier（broadcast 本身就是同步点）。

### Q2 — 答案：C

讲义："The mean is invariant to world_size: a learning rate tuned at one rank works at four ranks because the per-step gradient magnitude does not change." 只用 SUM 的话，梯度随 rank 数线性放大，等于学习率被放大 N 倍。

- A：float32 求 4 个梯度之和不会溢出；
- B：除法是本地操作，与通信无关；
- D：allreduce-SUM 后各 rank 的梯度已经相同，除不除都一致——只是尺度不同。

### Q3 — 答案：D

PyTorch 的 `.grad` 是累加的。每个分片的 loss 先除以 4 再反向，4 次累加得到 `Σ ∇L_r / 4`，正好是 4 个分片梯度的平均。DDP 中每个 rank 算 `∇L_r`，allreduce-SUM 得 `Σ ∇L_r`，再除以 4，两者相同。实测 20 步内 rank 0 的 loss 与参考的差值为 **0.0**（逐位相同；除以 4 是 2 的幂，乘回 4 不引入误差），最终参数范数差约 3.2e-8（浮点求和顺序不同）。

隐含前提：各分片样本数相同。`MSELoss` 默认对分片内取平均，若分片大小不同，"平均的平均"不等于全局平均。

- A、B、C 均不符合代码。

### Q4 — 答案：B

我们实测：`SEED + rank` 初始化 + 构造时 broadcast，10 步后 4 个 rank 的参数最大差值为 **0.0**，rank 0 的 loss 与参考差值 0.0。broadcast 用 rank 0 的权重覆盖了所有 rank，各 rank 自己用什么种子初始化根本不重要。

作为对照，**去掉 broadcast**（同样用 `SEED + rank`），10 步后各 rank 参数最大差 0.488，rank 0 的 loss 与参考相差最多 0.263——副本从一开始就不同，之后梯度同步也只是让它们"以相同的增量更新不同的起点"。

所以讲义这段说法与本节的设计不符：**真正保证一致的是 broadcast，而不是种子**。种子对数据打乱才重要——那时反而需要"每个 rank 看到不同的样本"（本节用确定性切片，不涉及打乱）。

### Q5 — 答案：A

`_ddp_worker` 中 rank r 取的是 `offset = step * world_size * batch + rank * batch` 开始的 8 条样本，rank 0 与 rank 3 的数据不同，loss 自然不同。这一列名叫 "drift"，却无法反映参数漂移。真正的一致性证据是表格下方的 `final param norm`，以及测试 `test_all_ranks_end_with_same_param_norm`（4 个 rank 的范数差为 0.0）。

- B、C、D 都把"不同数据上的 loss 差异"误读成了同步问题。

### Q6 — 答案：C

`16×32 + 32 = 544`，`32×32 + 32 = 1,056`，`32×4 + 4 = 132`，合计 **1,732**。共 3 个 `Linear` × (weight + bias) = 6 个参数张量（测试 `test_mini_mlp_param_count` 也断言 `len(list(m.parameters())) == 6`），`sync_grads` 对每个调用一次 `all_reduce`，即每步 6 次。

- A 漏了某些 bias，且把 6 个参数张量当成 3 次；B 参数量对了但次数错；D 无依据。

这正是讲义说的"one allreduce per tensor pays the latency floor"：大模型有成千上万个参数张量，就要调用成千上万次。

### Q7 — 答案：D

讲义："DDP exposes `no_sync()` as a context manager that pauses the post-backward allreduce. Forget the manager and you allreduce K times for nothing."

- A：模型仍是 DDP 包装的，只是暂停同步；
- B：PyTorch DDP 的 allreduce 本来就是异步重叠的，`no_sync` 是"不发"而不是"异步发"；
- C：前向与反向照常进行，梯度在本地累加。

### Q8 — 答案：B

集合通信要求所有 rank **以相同顺序调用相同的集合操作**。缺少梯度的 rank 跳过了 2 次 `all_reduce`（weight 和 bias），于是它的第 3 次调用会与其它 rank 的第 5 次调用配对：形状不同时 gloo 报错，调用次数不同时最后总有 rank 在等永远不会来的对端而挂起。

- A：`continue` 只是让**本地**不崩溃，恰恰制造了不同步；
- C：gloo 不会补零；
- D：错位会影响之后所有层。

PyTorch DDP 的 `find_unused_parameters=True` 就是在归约前遍历计算图，把没参与前向的参数标记为就绪（梯度视为 0），从而保持各 rank 的调用一致。

### Q9 — 参考答案

```python
    def sync_grads(self) -> None:
        grads = [p.grad for p in self.module.parameters() if p.grad is not None]
        if not grads:
            return
        flat = torch.cat([g.reshape(-1) for g in grads])   # 1,732 个元素的扁平桶
        dist.all_reduce(flat, op=dist.ReduceOp.SUM)
        flat.div_(self.world_size)
        offset = 0
        for g in grads:
            n = g.numel()
            g.copy_(flat[offset:offset + n].view_as(g))
            offset += n
```

- 我们用这个版本跑了 20 步：rank 0 的 loss 与单进程参考最大相差约 **9.5e-7**，最终范数 5.14845977 vs 5.14845979——**不是逐位相同，但在 float32 误差范围内一致**。原因是 gloo 对不同长度的张量可能选用不同的内部算法/分块方式，求和顺序变化导致最后一位不同。
- 拼接用 `torch.cat` 会多一次拷贝；PyTorch DDP 的做法是预先分配连续的桶缓冲区，让梯度直接写进去（`gradient_as_bucket_view`）。
- **多桶**：按参数注册的**逆序**（近似反向时梯度产生的顺序）依次装桶，累计字节数超过 `bucket_cap_mb`（默认 25 MB）就开一个新桶；每个桶独立 allreduce。配合反向 hook，某个桶中所有梯度都就绪就立即异步发出，这就是 overlap。
- 仍需保证所有 rank 的桶划分完全相同（同样的参数顺序、同样的 `None` 处理），否则同样会错位。

### Q10 — 参考答案

```python
import contextlib

class DistributedDataParallel:
    def __init__(self, module, world_size):
        self.module = module
        self.world_size = world_size
        self._sync = True
        self._broadcast_params()

    @contextlib.contextmanager
    def no_sync(self):
        old = self._sync
        self._sync = False
        try:
            yield
        finally:
            self._sync = old

    def sync_grads(self):
        if not self._sync:
            return                       # 累积阶段：不通信
        for p in self.module.parameters():
            if p.grad is None:
                continue
            dist.all_reduce(p.grad.data, op=dist.ReduceOp.SUM)
            p.grad.data.div_(self.world_size)

# 训练循环（K = 2，每个 micro-batch 4 条）
for step in range(steps):
    optim.zero_grad(set_to_none=True)
    base = step * world_size * K * MB + rank * K * MB
    for k in range(K):
        ctx = ddp.no_sync() if k < K - 1 else contextlib.nullcontext()
        with ctx:
            o = base + k * MB
            loss = loss_fn(model(x_all[o:o + MB]), y_all[o:o + MB]) / K   # 关键：除以 K
            loss.backward()
            ddp.sync_grads()
    optim.step()
```

- **loss 缩放**：每个 micro-batch 的 loss 除以 K，K 次累加得到本 rank 的平均梯度；allreduce 后再除以 N，得到 `N × K` 个 micro-batch 的平均——与 32 条样本的大 batch 的 `MSELoss`（均值）梯度相同。
- 我们实测（4 rank、K = 2、10 步）：与"单进程每步一个 32 条样本的大 batch"相比，参数最大差 **2.98e-8**；每个 rank 共调用 10 次真正的同步（每步 1 次），而不是 20 次。
- 用 `try/finally` 保证即使中途异常，`_sync` 也会恢复。

### Q11 — 参考答案

不一致之处：

1. **hook**：讲义说"install a backward hook on every parameter that issues an allreduce"，代码没有 hook，`sync_grads()` 在 `loss.backward()` 之后由训练循环显式调用。
2. **bucket**：讲义说"For the lesson's tiny model we group everything into one bucket"，也说"We can do all three [bucketing, overlap, NCCL] on CPU with gloo"，但代码是逐参数 allreduce，没有分桶、没有重叠。
3. **spawn 方式**：学习目标说用 `torch.multiprocessing.spawn`，代码用的是 `multiprocessing.get_context("spawn").Process`。
4. **种子**：讲义说 rank 相关的参数种子会破坏一致性；代码有 broadcast，种子不影响一致性（见 Q4）。讲义说 shuffle 用 `seed + rank`，代码根本没有 shuffle，而是按 rank 确定性切片。
5. **输出**：讲义说输出"comparing single-process loss and parameter checksum"，代码只在最后打印一次参数范数；每步表格中的 `rank_drift` 比较的是不同数据上的 loss（见 Q5）。
6. **函数名与测试**：讲义写 `_reference_single_process_loop` 和"byte-equal parameter equivalence after each step"，代码是 `reference_single_process`，测试比较的是 loss（`places=4`）和最终范数（`places=5`），不是逐步的参数逐位相等。
7. **"converge in seconds"**：20 步 SGD 后 loss 仍在 6～14 之间大幅波动（前 5 步均值 11.64，后 5 步均值 10.05），谈不上收敛；`test_world_size_two_still_converges` 也只检查了返回值类型。

修改表格：让 worker 每步记录参数的校验和，例如

```python
        checksum = torch.cat([p.detach().flatten() for p in ddp.parameters()]).double().sum().item()
        checksums.append(checksum)
```

把 `checksums` 一起放回 `out_queue`，主进程打印 `max_r |checksum_r − checksum_0|`，这一列在正确实现下应为 0；同时参考实现也记录同样的校验和，打印 `|ddp − ref|`（应在 1e-6 量级）。

### Q12 — 参考答案

1. `1,732 × 4 = 6,928` 字节；`2 × 6,928 × 3/4 = 10,392` 字节/rank/步（逻辑量；本节逐参数 6 次调用，还要付 6 次延迟）。
2. 梯度 `1e9 × 4 B = 4 GB`；`2 × 4 × 7/8 = 7 GB`/卡/步；`7 / 12.5 ≈ 0.56 s`。如果一步计算只要 0.5 s，不重叠的话通信时间比计算还长——这就是 overlap、分桶、梯度累积（降低同步频率）、低精度通信（bf16 梯度只需一半字节）存在的原因。

### Q13 — 参考回答要点

- **启动**：每个进程一个 rank，`init_process_group`（NCCL/gloo），模型放到各自设备上。
- **构造 DDP**：从 rank 0 broadcast 参数和 buffer，所有副本相同；按参数逆序划分梯度桶，注册反向 hook。
- **每步**：各 rank 用 `DistributedSampler` 取不同的数据分片 → 前向 → 反向；hook 在桶就绪时异步 allreduce（与剩余反向重叠）→ 反向结束时等待所有通信完成，梯度除以 N → 各 rank 独立执行相同的 `optimizer.step()`。
- **为什么一致**：起点相同（broadcast），每步的梯度相同（allreduce），优化器是确定性的 → 各副本的参数逐步保持一致。本节测试实测 4 个 rank 的参数范数差为 0。
- 加分点：DDP 不同步优化器状态，也不需要——相同的梯度序列会产生相同的状态；BatchNorm 的 running stats 默认每步从 rank 0 broadcast。

### Q14 — 参考回答要点

- **平均 vs 和**：用和，梯度会随 N 线性放大，等于学习率被乘以 N；用平均，每步梯度的期望与单卡一致，学习率的含义不随集群规模变化。讲义："Allreduce-SUM without the division forces you to retune the learning rate every time you change cluster size."
- **但全局 batch 确实变大了**：平均梯度的期望不变，方差约变为 1/N（噪声更小），每个 epoch 的步数变为 1/N。如果要在相同 epoch 数内达到相同效果，常用**线性缩放规则**（学习率 × N）配合 warmup；也有用平方根缩放的。超大 batch 时需要 LARS/LAMB 等方法。
- 结论：讲义说"tuned at one rank works at four ranks"指的是梯度尺度不变，不等于"最优学习率不变"——这个区别是面试追问点。
- 常见误区：混淆"每卡 batch"和"全局 batch"。

### Q15 — 参考回答要点

- **bucket**：合并小梯度，减少调用次数与延迟开销（讲义：约 25 MB）。代价是额外缓冲区内存；桶太大会推迟第一次通信，降低重叠。
- **overlap**：反向 hook 在桶就绪时立即异步 allreduce，与剩余反向计算重叠，隐藏通信时间。代价是实现复杂、要求桶的就绪顺序与反向顺序接近。
- **find_unused_parameters**：前向有条件分支（early exit、MoE 路由）时，未参与的参数没有梯度，桶永远等不齐而挂起；开启后每步遍历计算图找出这些参数。代价是每步一次图遍历（讲义："leave it off unless your forward branches"）。
- **static_graph**：前向结构每步不变时，DDP 可以在第一次迭代后缓存桶调度、未使用参数集合等信息，省掉每步的重复分析。
- 加分点：`gradient_as_bucket_view=True` 让 `.grad` 直接是桶的视图，省一次拷贝；`no_sync()` 用于梯度累积。

### Q16 — 参考回答要点

- **配置**：每卡 micro-batch 4，8 卡一次是 32，累积步数 K = 256 / 32 = 8。前 7 个 micro-batch 放在 `ddp.no_sync()` 中，第 8 个正常反向触发同步；loss 除以 K（或用 mean 损失再除以 K）；每 8 个 micro-batch 才 `optimizer.step()` 和 `zero_grad()`。
- **数据加载**：`DistributedSampler` 保证各 rank 拿到互不重叠的分片，每个 epoch 调用 `sampler.set_epoch(epoch)` 让打乱顺序变化；样本数不能整除时注意 padding/drop_last 带来的重复样本。
- **BatchNorm**：每卡 batch 只有 4，BN 统计量噪声很大；可用 `SyncBatchNorm` 跨卡计算统计量（额外通信），或改用 LayerNorm/GroupNorm。
- **随机种子**：参数初始化靠 broadcast 保证一致；数据增强、dropout 应各 rank 不同（`seed + rank`）；数据采样由 sampler 的 `seed + epoch` 控制。
- **学习率**：全局 batch 256 相对单卡调参时的 batch 变大，按线性缩放规则调整并加 warmup。

### Q17 — 参考回答要点

- **证明正确**：
  - 与单进程参考对拍：单进程按 rank 顺序处理所有分片、loss 除以 N 累加梯度，比较每一步的 loss 和**参数**（本节测试只比较了 loss 和最终范数，范数相同不代表参数相同，更严格应比较参数向量）；
  - 检查各 rank 参数逐位相同（或差值为 0）；
  - 覆盖不同 N、梯度累积、未使用参数等情况。
- **"loss 一致但效果差"的排查**：
  - 数据：各 rank 是否拿到了**相同**的数据（忘了用 `DistributedSampler` 或种子全一样）——这时等效 batch 没变大，却浪费了 N−1 张卡；或者忘了 `set_epoch`，每个 epoch 顺序相同；
  - 梯度尺度：是否除以了 N（或除了两次）；学习率是否按全局 batch 调整；
  - 梯度累积：是否忘了 `no_sync`（只影响速度）或忘了 loss 除以 K（影响尺度）；
  - BatchNorm：小 per-GPU batch 的统计量问题；
  - 评估：是否只在 rank 0 上评估了部分数据，或评估时没有 `model.eval()`。
- 加分点：在 rank 间定期比较参数校验和（本节 Q11 的做法），发现漂移立即报警。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 76 从零实现集合通信操作](../../76-collective-ops-from-scratch/docs/zh.md)：broadcast 与 allreduce 的实现原理和通信量。
- [阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../48-distributed-fsdp-ddp/docs/zh.md)：Track C 中 DDP/FSDP 的首次介绍。
- [阶段 19 · 46 Gradient Accumulation](../../46-gradient-accumulation/docs/zh.md)：梯度累积与 loss 缩放，`no_sync` 的基础。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：数据并行在 LLM 训练中的位置。
- [阶段 03 · 06 Optimizers](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：SGD 更新与学习率的作用。

### 本节被哪些后续内容用到
- [阶段 19 · 78 ZeRO Optimizer 状态分片](../../78-zero-parameter-sharding/docs/zh.md)：把 allreduce 拆成 reduce_scatter + allgather，分片优化器状态。
- [阶段 19 · 79 流水线并行与流水线气泡分析](../../79-pipeline-parallel/docs/zh.md)：另一种并行维度，可与数据并行组合。
- [阶段 19 · 80 分片 Checkpoint 与原子恢复](../../80-checkpoint-sharded-resume/docs/zh.md)：多 rank 训练状态的保存与恢复。
- [阶段 19 · 81 端到端分布式训练](../../81-end-to-end-distributed-train/docs/zh.md)：把 DDP 与 ZeRO 组合成完整训练。
- [阶段 19 · 44 带线性 Warmup 的余弦学习率](../../44-cosine-lr-warmup/docs/zh.md)：大 batch 训练时的学习率 warmup。

### 延伸关键词
`DistributedDataParallel` · `DistributedSampler / set_epoch` · `bucket_cap_mb` · `gradient_as_bucket_view` · `no_sync` · `find_unused_parameters` · `static_graph` · `SyncBatchNorm` · `linear scaling rule` · `torchrun` · `Accelerate` · `ReduceOp.AVG`
