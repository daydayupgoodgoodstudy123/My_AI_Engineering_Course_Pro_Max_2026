# 测验 · 从零实现分布式数据并行与 FSDP（Distributed Data Parallel and FSDP from Scratch）

> **阶段 19 · 综合项目 · 第 48 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 进程组（process group） | `MASTER_ADDR` + `MASTER_PORT` 是 rendezvous（会合点），每个 rank 用相同的 `world_size`、不同的 `rank` 调 `init_process_group` 才能组成一个组 |
| 2 | backend | `gloo` 跑在 CPU 上、随 PyTorch 自带；`nccl` 跑在 GPU 上；两者的 collective API 完全相同，换卡只改 backend、张量设备和启动器（`torchrun`） |
| 3 | 三个核心 collective | `broadcast`：一对多复制；`all_reduce`：所有 rank 求和（或均值/最大值）后人人拿到结果；`all_gather`：每个 rank 贡献一块，人人拿到拼接结果 |
| 4 | DDP 契约 | 构造时 `broadcast` 参数（起点一致），每次 backward 后 `all_reduce` 梯度并除以 `world_size`（每步更新一致），所以参数全程不分叉 |
| 5 | 梯度平均的等价性 | 在 loss 用 mean 归约、各 rank 分片**等大**时，"各 rank 梯度求和 ÷ N" 等于单进程在拼接 batch 上的梯度；代码实测最大差约 1e-8 |
| 6 | collective 必须"对齐调用" | 每个 rank 必须按同样顺序、对同样形状的张量调用同样次数的 collective，否则会挂起；所以无梯度参数也要补零再参与 `all_reduce` |
| 7 | FSDP 的分片 | 把每个参数拉平、补零到 `world_size` 的倍数，每个 rank 只保存 1/N；forward 前 `all_gather` 还原完整张量，用完丢掉 |
| 8 | FSDP 的代价 | 参数显存降到约 1/N，但每次 forward（实际 FSDP 在 backward 还要再来一次）都要付一次 `all_gather` 的通信；生产实现用"预取下一层 + 与当前层计算重叠"把代价藏起来 |
| 9 | 生产 DDP 的额外工程 | 梯度 hook 让 all-reduce 与 backward 重叠、把小梯度分桶（bucket）合并通信、梯度累积时用 `no_sync` 跳过中间步的通信 |
| 10 | 同步检查与日志 | 参数一致性要按元素比较而不是只比总和；各 rank 的 loss 是本地值，看板上展示前应先 all-reduce |

### 核心技能（能动手做到）

- [ ] 用 `torch.multiprocessing` + `gloo` 在一台 CPU 机器上起 N 个 rank，完成 `broadcast` / `all_reduce` / `all_gather`
- [ ] 手写 `MinimalDDP`：构造时广播参数与 buffer，backward 后对梯度 `all_reduce(SUM)` 再除以 `world_size`
- [ ] 写一个对照实验，证明分片梯度平均 = 单进程全 batch 梯度，并说出这个等式成立的前提（等大分片、mean 归约）
- [ ] 给定参数元素数和 `world_size`，手算 FSDP 分片的 `per`、`pad` 和每个 rank 实际持有的元素数
- [ ] 用 `register_post_accumulate_grad_hook` + `async_op=True` 把梯度通信挂到 backward 过程中（讲义练习 3）
- [ ] 写出比"参数总和"更可靠的跨 rank 一致性检查
- [ ] 估算 DDP 每步的梯度通信量（ring all-reduce 的 `2(N−1)/N × 梯度字节数`）

---

## 二、基础自测（选择题）

**Q1.** 本节所说的"DDP 契约"是指哪两个 collective、分别在什么时候调用？

- A. 每步前 `all_gather` 参数、每步后 `broadcast` 梯度
- B. 只在训练结束时 `all_reduce` 一次参数
- C. 每步 forward 前 `barrier`、backward 后 `send/recv`
- D. 构造模型时 `broadcast` 参数（从 rank 0），每次 backward 之后对梯度 `all_reduce` 并除以 `world_size`

**Q2.** `world_size = 4`，某个参数在四个 rank 上 backward 后的梯度（标量）分别是 1、2、3、6。执行代码中的 `all_reduce_grads_`（先 `ReduceOp.SUM` 再 `div_(world_size)`）之后：

- A. 四个 rank 上的梯度都变成 3.0
- B. rank 0 上是 12.0，其他 rank 保持原值
- C. 四个 rank 上都是 12.0
- D. 四个 rank 各自保持原值，只有返回值是平均数

**Q3.** `all_reduce_grads_` 里有这样两行：

```python
        if p.grad is None:
            p.grad = torch.zeros_like(p.data)
```

去掉它们、并且某个参数恰好只在部分 rank 上有梯度时，最可能发生什么？

- A. 没有影响，`all_reduce` 会自动跳过 `None`
- B. 只是这个参数的梯度少了一部分，训练稍微慢一点
- C. 各 rank 调用 collective 的次数/顺序不再一致：有梯度的 rank 在等一个永远不会来的 `all_reduce`，可能挂起或与下一个张量错配
- D. 会让梯度自动除以 2

**Q4.** 讲义说"分片梯度求和 ÷ N 等于单进程在拼接输入上的梯度"。以 `nn.CrossEntropyLoss()`（默认 mean 归约）为例，这个等式**严格成立**还需要哪个前提？

- A. 必须使用 `nccl` backend
- B. 每个 rank 分到的样本数相同；分片不等大时，"各 rank 均值的平均"不等于"全 batch 均值"
- C. 每个 rank 必须使用不同的随机种子
- D. 模型里不能有 GELU 激活

**Q5.** 在 `world_size = 3` 下，对形状 `(16, 32)` 的权重执行 `fsdp_round_trip_sketch` 的分片逻辑，`per`（每个 rank 的分片长度）和补零个数 `pad` 分别是：

- A. `per = 171`，`pad = 1`
- B. `per = 170`，`pad = 2`
- C. `per = 171`，`pad = 0`
- D. `per = 512`，`pad = 0`

**Q6.** 把本节代码从 CPU 迁移到多 GPU 节点，下面哪一项**不需要**改？

- A. `backend="gloo"` 改成 `backend="nccl"`
- B. 模型与数据张量放到各自 rank 对应的 GPU 上
- C. 启动方式从 `torch.multiprocessing` 换成 `torchrun`（可选但常见）
- D. `dist.broadcast` / `dist.all_reduce` / `dist.all_gather` 的调用方式

**Q7.** 如果把 `MinimalDDP.__init__` 里的 `broadcast_module(self.module, src=0)` 删掉，再运行 `python3 main.py --no-write`，`param_sum_spread` 会怎样？

- A. 变成一个明显大于 1e-3 的数，`assert` 失败
- B. 程序挂起，因为少了一次 collective
- C. 仍然是 0.0——因为每个 rank 在 `make_model` 前都执行了 `torch.manual_seed(seed)`，初始权重本来就相同；这个 demo 无法证明"广播是必要的"
- D. 变成 NaN

**Q8.** 关于 FSDP 的说法，正确的是：

- A. FSDP 只切分数据、不切分参数，所以显存与 DDP 相同
- B. FSDP 让每个 rank 的参数显存降到约 1/N，代价是每次用到某层时都要 `all_gather` 一次；生产实现会把下一层的 gather 与当前层计算重叠
- C. FSDP 不需要任何通信
- D. 本节的 `fsdp_round_trip_sketch` 已经真正把每个 rank 的参数显存降到了 1/N

---

## 三、动手 / 代码题

**Q9.** 阅读 `shard_for_rank`：

```python
def shard_for_rank(x: torch.Tensor, rank: int, world_size: int) -> torch.Tensor:
    total = x.shape[0]
    per = total // world_size
    remainder = total - per * world_size
    start = rank * per + min(rank, remainder)
    end = start + per + (1 if rank < remainder else 0)
    return x[start:end]
```

1. `total = 10, world_size = 3` 时，三个 rank 各拿到哪些下标？
2. 用这种不等大分片做"各 rank 的 mean 梯度求和 ÷ 3"，再和单进程全 batch 梯度比较，会得到很小的差（1e-8 级）还是明显的差？为什么代码里的 `manual_all_reduce_matches_single_process` 没暴露这个问题？
3. 给出一个在不等大分片下仍然精确等价的修正方案。

**Q10.** `run_distributed_demo` 用下面的方式判断"各 rank 参数是否一致"：

```python
    param_sums = {r: results[r]["post_param_sum"] for r in results}
    spread = max(param_sums.values()) - min(param_sums.values())
```

1. 举一个参数明明不一致、但 `spread` 仍为 0 的例子。
2. 写一个 `params_max_diff_vs_rank0(module)`，在每个 rank 上调用，返回所有 rank 中"与 rank 0 逐元素比较的最大绝对差"。

**Q11.** 讲义练习 4：实现 FSDP 的"重新分片（re-shard）"，让每个 rank 真的只持有 1/N 的参数。

1. 指出现有 `fsdp_round_trip_sketch` 为什么**没有**节省显存。
2. 写一个 `ShardedParam` 类：构造时只保留本 rank 的分片；`unshard()` 用 `all_gather` 还原完整张量。用它对 `make_model(32, 16, 4)` 做一次 forward，`world_size = 3` 时每个 rank 持有多少个元素？
3. 真正的 FSDP 在 backward 时还需要哪两个通信步骤？

**Q12.** 模块 docstring 写着"averages gradients in a post-backward hook"，但实际代码是训练循环里手动调用 `ddp_model.sync_grads()`。请按讲义练习 3，用 `Tensor.register_post_accumulate_grad_hook` 和 `async_op=True` 写一个 `HookDDP`，让每个参数的梯度一算完就开始异步 all-reduce，并说明它比手动 `sync_grads()` 快在哪里、还差生产 DDP 的哪一步。

---

## 四、面试高频题

**Q13.**（基础必考）DDP、FSDP（ZeRO-3）各自在每个 rank 上保存什么？分别解决什么问题？什么情况下 DDP 就够了？

**Q14.**（原理深挖）ring all-reduce 是怎么工作的？每个 rank 每步要发送多少数据？以 GPT-2 Small（约 1.24 亿参数、FP32 梯度）在 8 卡上做 DDP 为例估算一下。

**Q15.**（工程实践）PyTorch 的 `DistributedDataParallel` 相比本节 `MinimalDDP` 多做了哪些事？各自解决什么问题？

**Q16.**（场景设计）要在 8 × 80GB 的 GPU 上全参数微调一个 70B 模型（AdamW、混合精度）。DDP 行不行？FSDP 行不行？你会怎么设计？

**Q17.**（追问型）多卡训练在第一步就卡住不动，也不报错。你会怎么排查？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："The DDP contract is `broadcast` at construction and `all_reduce` after backward."  构造时广播保证 step 0 起点一致，backward 后平均梯度保证每一步更新一致，两者合起来参数就永远不会分叉。A 是 FSDP 的 `all_gather` 与错误的方向混在一起；B 只在结束时同步，中间各 rank 早已各练各的；C 中 `barrier` 只是同步点，不传数据。

### Q2 — 答案：A

`all_reduce(SUM)` 的语义是"所有 rank 求和，**每个 rank** 都拿到结果"：1+2+3+6 = 12，四个 rank 都变成 12，再各自 `div_(4)` 得 3.0。B 描述的是 `reduce`（只有目标 rank 拿到结果）；C 漏了除以 `world_size`——技能文件也把"Forgetting to divide after sum"列为失败模式，会让有效学习率放大 N 倍；D 错在 `all_reduce` 是**原地**修改 `p.grad.data`。

### Q3 — 答案：C

collective 是"所有 rank 一起调用才完成"的操作。`all_reduce_grads_` 对每个参数调一次 `all_reduce`，如果某个 rank 因为 `p.grad is None` 跳过，它调用的第 k 次 all-reduce 就会和别的 rank 的第 k 次对应到不同的参数（形状不同时报错，形状相同时**静默**把错误的梯度加在一起），或者某个 rank 一直等不到配对而挂起。补零张量保证"人人都调、顺序一致"。A 错，`all_reduce` 不接受 `None`；B、D 都没有抓住"对齐调用"这个本质。PyTorch DDP 里对应的开关是 `find_unused_parameters=True`。

### Q4 — 答案：B

mean 归约下，rank r 的梯度是 `(1/n_r) Σ_{i∈r} g_i`。只有当所有 `n_r = n` 时，`(1/N) Σ_r (1/n) Σ g_i = (1/(Nn)) Σ g_i` 才等于全 batch 均值。实测：10 个样本分给 3 个 rank（4/3/3），"均值的平均"与全 batch 梯度的最大差是 **0.0222**，按样本数加权后降到 **1.5e-8**。代码里 `full_x` 的长度是 `batch_size * world_size`，正好整除，所以没有暴露这个前提。A 与正确性无关；C 说的是数据采样，不是等式条件；D 无关，任何可导激活都行。

### Q5 — 答案：A

`total = 16 × 32 = 512`，`per = ceil(512 / 3) = (512 + 2) // 3 = 171`，`padded_total = 171 × 3 = 513`，`pad = 1`。B 是向下取整的结果，三个分片只有 510 个元素，丢了数据；C 忽略了 513 ≠ 512；D 是不分片。代码注释解释了为什么要补零：gloo 的 `all_gather` 要求每个 rank 的输出大小相同。

### Q6 — 答案：D

讲义："On a multi-GPU node, the only changes are `backend="nccl"`, device tensors, and `torchrun` to launch." collective 的调用接口（API surface）保持一致，这正是先在 CPU 上用 gloo 把逻辑写对的意义。A、B、C 都是需要改的地方（C 严格说可选，但 `torchrun` 会自动设置 `RANK`、`WORLD_SIZE`、`MASTER_ADDR` 等环境变量，是常规做法）。

### Q7 — 答案：C

`rank_main` 中：

```python
        torch.manual_seed(seed)
        base = make_model(in_dim, hidden, out_dim)
        ddp_model = MinimalDDP(base, world_size)
```

所有 rank 用同一个 `seed` 初始化，权重本来就一样，广播只是"复制一份相同的值"。我们实测：同种子下两个 rank 的初始参数和都是 −1.2432；若改成 `torch.manual_seed(seed + rank)`，rank 1 的参数和变成 0.0190，这时删掉广播才会让 `spread` 明显大于 0。`manual_all_reduce_matches_single_process` 里也是同样情况（各 rank 都 `manual_seed(7)`）。所以这个 demo 和测试都**没有覆盖**"跳过广播会分叉"这个失败模式。A 只在种子按 rank 区分时才成立；B 错，删掉的是所有 rank 都删的那一次调用，调用依然对齐，不会挂起。

### Q8 — 答案：B

讲义："per-rank memory for parameters drops to 1/N. The cost is the gather, which is paid every forward pass. Production FSDP overlaps the gather with the previous layer's compute." A 描述的是 DDP；C 错，gather 就是通信；D 错，本节的 sketch 只是"拷贝完整参数 → 切片 → gather → 比较"的往返验证，`ddp_model.module` 一直持有完整参数，显存并没有下降（见 Q11）。

### Q9 — 参考答案

1. `per = 10 // 3 = 3`，`remainder = 1`。rank 0：`start = 0`，`end = 4` → 下标 0–3（4 个）；rank 1：`start = 3 + 1 = 4`，`end = 7` → 4–6；rank 2：`start = 6 + 1 = 7`，`end = 10` → 7–9。余数分给前面的 rank，每个 rank 大小最多差 1——这正是 `test_shard_for_rank_handles_remainder` 检查的性质。
2. 会得到**明显的差**。实测（`torch.manual_seed(7)` 的 `make_model(32,16,4)`，10 个样本）：直接平均的最大绝对差为 **0.0222**。原因见 Q4：rank 0 的每个样本权重是 `1/(3×4)`，rank 1、2 的是 `1/(3×3)`，与全 batch 的 `1/10` 都不同。代码的等价性实验用 `batch_size * world_size` 个样本，分片永远等大，所以测不出来。
3. 修正思路——按样本数加权：
   - 每个 rank 用 `reduction="sum"` 计算 loss（或把 mean 梯度乘以 `n_r`），`all_reduce(SUM)` 后再除以**全局样本数**（全局样本数本身也可以用一次 `all_reduce` 求得）：

   ```python
   n_local = torch.tensor([float(my_x.shape[0])])
   dist.all_reduce(n_local)                       # 全局样本数
   loss = nn.CrossEntropyLoss(reduction="sum")(model(my_x), my_y)
   loss.backward()
   for p in model.parameters():
       dist.all_reduce(p.grad, op=dist.ReduceOp.SUM)
       p.grad.div_(n_local.item())
   ```

   实测加权后最大差降到 **1.5e-8**。
   - 工程上更常见的做法是让数据加载保证等大：PyTorch 的 `DistributedSampler` 默认会补齐（复制少量样本）或用 `drop_last=True` 丢掉尾部，使每个 rank 每步样本数相同。

### Q10 — 参考答案

1. 例子：rank 1 上把第一层权重 `W[0,0]` 和 `W[0,1]` 两个值互换（或任何"加一个 δ、另一个元素减 δ"的扰动）。实测两个 rank 的参数和都是 −1.1369，`spread = 0`，但逐元素最大差是 **0.1188**。总和只是一个标量指纹，不同的参数完全可能撞出相同的和；另外它用 Python float 累加，还会把很小的差异淹没在舍入里。
2. 参考实现（已在 2 个 rank 上运行验证）：

```python
def params_max_diff_vs_rank0(module):
    flat = torch.cat([p.detach().flatten() for p in module.parameters()])
    ref = flat.clone()
    dist.broadcast(ref, src=0)                         # 人人拿到 rank 0 的参数
    diff = torch.tensor([float((flat - ref).abs().max())])
    dist.all_reduce(diff, op=dist.ReduceOp.MAX)        # 取所有 rank 中的最大差
    return diff.item()
```

要点：用 `broadcast` 拿到"标准答案"、本地逐元素比较、再用 `all_reduce(MAX)` 让每个 rank 都知道全局最差情况。模型很大时可以改为比较每个参数的哈希（如对字节做 CRC），只传一个整数。

### Q11 — 参考答案

1. `fsdp_round_trip_sketch` 对每个参数先 `full = p.data.detach().clone()`，再切片、gather、比较——完整参数一直留在 `module` 里，还多 clone 了一份，显存不降反升。它验证的是"切片 + all_gather 能无损还原"这一步的正确性，而不是显存节省。
2. 参考实现（已用 3 个 rank 运行验证：每个 rank 持有 201 个元素，forward 输出与原模型的最大差为 0.0）：

```python
import torch.nn.functional as F

class ShardedParam:
    def __init__(self, full, rank, ws):
        self.shape, self.numel, self.ws = full.shape, full.numel(), ws
        self.per = (self.numel + ws - 1) // ws
        flat = F.pad(full.detach().flatten(), (0, self.per * ws - self.numel))
        self.shard = flat[rank * self.per:(rank + 1) * self.per].clone()   # 只留 1/N
    def unshard(self):
        bufs = [torch.empty(self.per) for _ in range(self.ws)]
        dist.all_gather(bufs, self.shard)
        return torch.cat(bufs)[:self.numel].view(self.shape)

shards = [ShardedParam(p, rank, ws) for p in model.parameters()]
del model                                                   # 丢掉完整模型
W1, b1 = shards[0].unshard(), shards[1].unshard()
h = F.gelu(F.linear(x, W1, b1)); del W1, b1                 # 用完立刻释放（re-shard）
W2, b2 = shards[2].unshard(), shards[3].unshard()
out = F.linear(h, W2, b2); del W2, b2
```

   元素数：四个参数 512、16、64、4（共 596），`world_size = 3` 时 `per` 为 171、6、22、2，每个 rank 持有 **201** 个，约 596/3 ≈ 199 再加上补零。
3. backward 时：(a) 再次 `all_gather` 该层参数（forward 后已经丢掉了，算梯度还要用）；(b) 对该层完整梯度做 `reduce_scatter`，每个 rank 只拿回自己分片对应的、已经求和/平均的梯度，再用本地分片的优化器状态更新本地分片。这就是 ZeRO-3 的完整流程：参数、梯度、优化器状态三者都分片。

### Q12 — 参考答案

参考实现（已在 2 个 rank 上验证：与手动 `sync_grads()` 的梯度最大差为 0.0）：

```python
class HookDDP(nn.Module):
    def __init__(self, module, world_size):
        super().__init__()
        self.module, self.world_size = module, world_size
        broadcast_module(module)
        self._pending = []
        for p in module.parameters():
            p.register_post_accumulate_grad_hook(self._hook)   # 梯度累加完立即触发

    def _hook(self, p):
        work = dist.all_reduce(p.grad, op=dist.ReduceOp.SUM, async_op=True)
        self._pending.append((work, p))

    def forward(self, *args, **kwargs):
        return self.module(*args, **kwargs)

    def finish_sync(self):                     # optimizer.step() 之前调用
        for work, p in self._pending:
            work.wait()
            p.grad.div_(self.world_size)
        self._pending.clear()
```

- **快在哪里**：backward 是从最后一层往前算的。最后一层的梯度一算完就开始通信，同时 autograd 继续算前面层的梯度，通信与计算**重叠**；手动 `sync_grads()` 要等整个 backward 结束后才串行地发起所有 all-reduce。
- **还差什么**：分桶（bucketing）。每个参数单独一次 collective，小张量多时启动开销占主导；生产 DDP 按反向顺序把梯度装进固定大小（默认 25MB）的桶，一桶满了发一次。此外还要处理"未使用参数"、`no_sync` 梯度累积等。
- 注意：用 `async_op=True` 时必须在 `optimizer.step()` 前 `wait()`，否则可能用到还没归约完的梯度。

### Q13 — 参考回答要点

- **DDP**：每个 rank 保存**完整**的参数、梯度和优化器状态，只切分数据；通信是每步一次梯度 all-reduce。解决"吞吐不够"的问题，前提是模型 + 优化器状态 + 激活能放进单卡。
- **FSDP / ZeRO-3**：参数、梯度、优化器状态都按 1/N 分片；forward/backward 时按层 `all_gather` 参数，backward 后对梯度 `reduce_scatter`。解决"单卡放不下"的问题。
- **中间形态**（加分点）：ZeRO-1 只分片优化器状态；ZeRO-2 再分片梯度；ZeRO-3 = FSDP 的完全分片。分片越多显存越省、通信越多。
- **什么时候 DDP 就够**：单卡能放下"参数 + 梯度 + 优化器状态 + 激活"（例如本节 596 个参数的小 MLP，或数亿参数的模型在 80GB 卡上），这时 DDP 通信最少、最简单。
- 常见误区：以为 FSDP 能减少激活显存——激活要靠 gradient checkpointing（见阶段 10 · 34）或减小 micro-batch。

### Q14 — 参考回答要点

- **过程**：N 个 rank 排成环，把张量切成 N 块。第一阶段 reduce-scatter：N−1 步，每步把一块发给下一个 rank 并累加，结束时每个 rank 拥有一块的完整和；第二阶段 all-gather：再 N−1 步把这些完整块传遍全环。
- **通信量**：每个 rank 发送 `2 × (N−1)/N × M` 字节（M 为张量大小），与 N 几乎无关——这就是 ring all-reduce 带宽最优、能扩展到很多卡的原因（讲义的 `cg-allreduce-ring` 图即此）。
- **估算**：GPT-2 Small 约 124,439,808 个参数，FP32 梯度 ≈ 497.8 MB；N = 8 时每步每个 rank 发送 `2 × 7/8 × 497.8 ≈ 871 MB`。若卡间带宽是几十 GB/s，单次就是几十毫秒，必须与 backward 重叠或用 BF16 梯度压缩一半。
- 加分点：ring 的延迟项随 N 线性增长，小张量多时延迟主导，这也是要分桶的原因；大规模集群上 NCCL 还会用树形算法来降低延迟。

### Q15 — 参考回答要点

- **梯度 hook + 异步通信**：backward 过程中梯度就绪即通信，与计算重叠（见 Q12）。
- **梯度分桶**：把多个小梯度拼成大缓冲区一次 all-reduce，减少 collective 次数与启动延迟。
- **`no_sync()`**：梯度累积的前 k−1 个 micro-batch 不通信，只在最后一个通信（讲义提到第 46 节用过）。
- **未使用参数检测**（`find_unused_parameters`）：处理条件分支导致的"某些参数这一步没梯度"，保证调用对齐（见 Q3）。
- **buffer 同步**：如 BatchNorm 的 running stats，默认每次 forward 前从 rank 0 广播。
- **设备与进程绑定**：每个进程绑定一张 GPU，配合 `DistributedSampler` 分配数据。
- 加分点：说出 MinimalDDP 的 loss 也没有聚合——要在看板上显示全局 loss，需要额外 `all_reduce(loss)/N`，否则"the dashboard lies"（讲义）。

### Q16 — 参考回答要点

- **算账**：混合精度 + AdamW 的常见估算是每参数约 16 字节（BF16 参数 2 + BF16 梯度 2 + FP32 主权重 4 + Adam 两个动量 8）。70B × 16 B ≈ **1,120 GB**。
- **DDP 不行**：每卡要放完整的 1,120 GB，光 BF16 权重就 140 GB，超过 80 GB。
- **只用 8 卡 FSDP 也很紧**：1,120 / 8 = 140 GB/卡，仍超过 80 GB，还没算激活。
- **可行方案**（任选组合，说清取舍）：
  - 加卡：16 卡 FSDP 时约 70 GB/卡，再配 activation checkpointing 和小 micro-batch，仍然非常紧；更现实是 32 卡以上，或多机 FSDP + 节点内张量并行；
  - CPU offload：把优化器状态/分片卸载到 CPU 内存，换取速度损失；
  - 换训练方式：LoRA/QLoRA 只训练少量参数，优化器状态极小，8 卡完全可行；
  - 8-bit 优化器减少动量显存。
- 加分点：说明 FSDP 在多机时通信跨节点，带宽骤降，通常用 hybrid sharding（节点内分片、节点间复制）。

### Q17 — 参考回答要点

- **先确认是否卡在 rendezvous**：各 rank 的 `MASTER_ADDR`/`MASTER_PORT`/`WORLD_SIZE` 是否一致；端口是否被占用或防火墙拦截；是否真的起了 `world_size` 个进程。本节用 bind-and-close 找空闲端口，在并发运行时仍有极小概率被抢占。
- **再确认 collective 是否对齐**：是否有 rank 走了不同的分支（如只在 rank 0 上做 eval 却在里面调用了 collective）、参数数量或顺序不一致、某些参数没有梯度（Q3）。
- **网络接口**：多网卡机器上 gloo/nccl 可能选错网卡。本节代码用 `GLOO_SOCKET_IFNAME=lo` 强制走回环；NCCL 对应 `NCCL_SOCKET_IFNAME`。
- **工具**：`TORCH_DISTRIBUTED_DEBUG=DETAIL` 检查 collective 不一致；`NCCL_DEBUG=INFO` 看拓扑与传输；给 `init_process_group` 设置较短的 `timeout`，让挂起变成可读的报错；用 `py-spy dump` 看每个进程卡在哪一行。
- **混用设备**：技能文件提到"Mixing CPU and CUDA tensors on the same collective: backend mismatch, run hangs"。
- 常见误区：只看 rank 0 的日志。挂起往往是另一个 rank 先出错退出了，要收集所有 rank 的日志。本节 `run_distributed_demo` 在超时时只抛出 "ranks did not finish in time"，可能掩盖真正出错的 rank 的异常信息。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 45 Gradient Clipping 与 Mixed Precision](../../45-gradient-clipping-amp/docs/zh.md)：分布式训练中梯度裁剪要在 all-reduce 之后做，混合精度决定梯度通信的字节数。
- [阶段 19 · 46 Gradient Accumulation](../../46-gradient-accumulation/docs/zh.md)：讲义提到的 `no_sync` 就是为它服务的。
- [阶段 19 · 47 Checkpoint 保存与恢复](../../47-checkpoint-save-resume/docs/zh.md)：多 rank 训练只由 rank 0 写 checkpoint，并用原子替换。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：数据并行、ZeRO 各阶段与 DeepSpeed 的概念层介绍。

### 本节被哪些后续内容用到
- [阶段 19 · 76 从零实现集合通信操作](../../76-collective-ops-from-scratch/docs/zh.md)：自己实现 ring all-reduce 等 collective。
- [阶段 19 · 77 从零实现数据并行 DDP](../../77-data-parallel-ddp/docs/zh.md)：更完整的 DDP（分桶、重叠）。
- [阶段 19 · 78 ZeRO Optimizer 状态分片](../../78-zero-parameter-sharding/docs/zh.md)：在本节 FSDP 草图基础上分片优化器状态。
- [阶段 19 · 79 流水线并行与流水线气泡分析](../../79-pipeline-parallel/docs/zh.md)：另一种并行维度。
- [阶段 19 · 80 分片 Checkpoint 与原子恢复](../../80-checkpoint-sharded-resume/docs/zh.md)：FSDP 下 checkpoint 也要分片保存。
- [阶段 19 · 81 端到端分布式训练](../../81-end-to-end-distributed-train/docs/zh.md)：把这些组件拼起来。
- [阶段 10 · 19 DualPipe 并行](../../../10-llms-from-scratch/19-dualpipe-parallelism/docs/zh.md)：计算与通信重叠的极致形态。
- [阶段 10 · 34 Gradient Checkpointing 与激活重计算](../../../10-llms-from-scratch/34-gradient-checkpointing/docs/zh.md)：FSDP 省参数显存，checkpointing 省激活显存。

### 延伸关键词
`torch.distributed` · `gloo / nccl` · `torchrun` · `init_process_group` · `broadcast / all_reduce / all_gather / reduce_scatter` · `ring all-reduce` · `DistributedDataParallel` · `gradient bucketing` · `no_sync` · `find_unused_parameters` · `DistributedSampler` · `FSDP / ZeRO-1/2/3` · `CPU offload` · `TORCH_DISTRIBUTED_DEBUG`
