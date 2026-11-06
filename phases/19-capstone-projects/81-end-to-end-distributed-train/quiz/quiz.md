# 测验 · 端到端分布式训练（End-to-End Distributed Training）

> **阶段 19 · 综合项目 · 第 81 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 组合即验证 | 76–80 节各自有单元测试，但"拼在一起"是独立的性质：会死锁、loss 发散、checkpoint 恢复失败、每 rank 内存不降反升，只有端到端运行才能发现 |
| 2 | 四个不变量 | (a) 20 步 loss 有限（讲义原文写"单调下降"，实测并不单调）；(b) 各 rank 参数范数一致；(c) 每 rank 优化器内存 = ZeRO-1 公式 12P/N 字节；(d) step 10 的 checkpoint 逐字节恢复 |
| 3 | DDP 的残留部分 | 初始化时 `broadcast` 一次参数（以 rank 0 为准）；DDP 的梯度 all-reduce 被 ZeRO-1 的 reduce_scatter 取代 |
| 4 | ZeRO-1 一步 | 扁平化梯度 → 补零到 N 的倍数 → `reduce_scatter`（求和）后除以 N → 在本 rank 的 1/N 分片上做 Adam → `all_gather` 主参数 → 写回模型 |
| 5 | 通信量等价 | ring all-reduce = reduce-scatter + all-gather，所以 ZeRO-1 的通信量与 DDP 相同，却把优化器状态内存降到 1/N |
| 6 | 数学等价 | 每 rank batch 大小相同时，"各 rank 平均梯度的平均"= 全局 batch 的平均梯度；Adam 是逐元素运算，分片不改变结果。实测与单进程 batch=16 的 Adam 最终参数范数一致（54.51317） |
| 7 | Mini GPT | 2 层、32 维、4 头、词表 64、序列 16、每 rank batch 4；LM head 不与 embedding 共享；共 29,824 个参数（讲义说"a few thousand"） |
| 8 | 中途 checkpoint | step 10 时每 rank 序列化 `{model_state, optim_state, rank}`，all_gather 到所有 rank 后由 rank 0 写 4 个分片 + manifest（这正是 80 节反对的 gather-then-write 形状） |
| 9 | 自终止 | 固定 20 步、exit 0、无人工介入；任一环节死锁就不会返回，由测试/CI 超时捕获 |
| 10 | 生产模式 | 按 wall-clock 而非 step 做 checkpoint；NaN 守卫 + loss 尖峰检测后回滚；内存剖面记录各 rank 的最大值与均值 |

### 核心技能（能动手做到）

- [ ] 用 `torch.distributed`（gloo + 文件 rendezvous）在一台 CPU 机器上启动 4 个进程，完成 broadcast、reduce_scatter、all_gather
- [ ] 手写一个 ZeRO-1 优化器：扁平化参数/梯度、补零、分片 Adam、all_gather 写回，并能说清每一步的张量长度
- [ ] 用单进程大 batch 的 `torch.optim.Adam` 作为基线，验证分布式实现在数值上等价
- [ ] 按参数、梯度、主参数、m、v 逐项计算每 rank 内存，并对比 DDP / ZeRO-1 / ZeRO-2 / ZeRO-3
- [ ] 诊断并修复 `multiprocessing` 队列传张量 + `os._exit` 导致的 Linux 崩溃
- [ ] 实现"从 step 10 恢复并继续训练到 step 20，最终 loss 与原始运行一致"（讲义练习 3）

---

## 二、基础自测（选择题）

**Q1.** 本节代码中，DDP 与 ZeRO-1 是如何组合的？

- A. 每步先做 DDP 的梯度 all-reduce，再做 ZeRO-1 的 reduce_scatter，两次通信叠加
- B. DDP 只保留初始化时的参数 broadcast；梯度同步由 ZeRO-1 的 reduce_scatter 完成，更新后用 all_gather 把参数发回各 rank
- C. 只用 DDP，ZeRO-1 仅用于保存 checkpoint
- D. 用 `torch.nn.parallel.DistributedDataParallel` 包装模型，再用 `ZeroRedundancyOptimizer`

**Q2.** 本节 `MiniGPT()` 默认配置的参数量是多少？

- A. 约 3,000（讲义说 "A few thousand parameters"）
- B. 27,776
- C. 119,296
- D. 29,824

**Q3.** 4 个 rank 时，每个 rank 打印的 `shard_bytes`（ZeRO-1 分片：fp32 主参数 + m + v）是多少？

- A. 89,472
- B. 357,888
- C. 29,824
- D. 119,296

**Q4.** 实际运行时 rank 0 的 20 个 loss 从 4.297 开始、以 4.222 结束，中途最高到 4.459。对此最准确的解释是：

- A. loss 应该单调下降到接近 0，说明实现有 bug
- B. 训练发散，后续会出现 NaN
- C. 语料是 `torch.randint` 生成的均匀随机 token，没有可学的规律，loss 只能在 `ln 64 ≈ 4.159` 附近波动；讲义"单调下降"的不变量并不成立，代码和测试也只检查了 loss 有限
- D. 学习率太小，loss 会持续上升

**Q5.** 运行结果中 4 个 rank 的最终参数范数完全相同（drift 0.00e+00）。根本原因是：

- A. 每个 rank 都调用了 `torch.manual_seed(SEED)`，与通信无关
- B. DDP 在每步 backward 中自动 all-reduce 了梯度
- C. 浮点误差恰好抵消
- D. 每一步所有 rank 都把**同一个** all_gather 得到的扁平主参数写回模型；加上初始化时从 rank 0 broadcast，各 rank 的参数始终逐位相同

**Q6.** 在 Linux（PyTorch 2.14.1）上直接运行 `python3 main.py`，主进程在 `out_queue.get()` 处抛出 `EOFError` 或 `ConnectionResetError`。原因是：

- A. worker 往队列里放了一个 torch 张量（`master_at_ckpt`）；Linux 默认的 `file_descriptor` 共享策略要求主进程反序列化时去 worker 进程取文件描述符，而 worker 放完数据就 `os._exit(0)` 退出了
- B. gloo 后端在 Linux 上不可用
- C. 回环网卡名应为 `lo0`
- D. `out_queue.get(timeout=180)` 超时

**Q7.** 关于本节 step 10 的 checkpoint，下列说法正确的是：

- A. 每个 rank 并行地把自己的分片写到自己的文件
- B. 用 `dist.gather` 只把数据收集到 rank 0
- C. 每个 rank 的序列化状态通过 all_gather 发给**所有** rank，然后只由 rank 0 写出全部 4 个文件——这正是 80 节批评的 gather-then-write 形状
- D. 只保存了优化器分片，没有保存模型参数

**Q8.** `verify_resume` 实际验证了什么？

- A. 从 step 10 恢复并继续训练到 step 20，最终 loss 与原始运行一致
- B. 从磁盘重新加载的每个 rank 的 `master_shard`，与 worker 在 step 10 时内存中的快照逐字节相等；没有比较 m、v、模型参数，也没有继续训练
- C. 4 个 rank 在 step 10 时的 loss 一致
- D. 在 world size = 8 上重新加载 checkpoint

---

## 三、动手 / 代码题

**Q9.** worker 的结尾如下：

```python
    out_queue.put((rank, rank0_losses if rank == 0 else [], param_norm, optim.shard_bytes(),
                   master_at_ckpt))
    out_queue.close()
    out_queue.join_thread()
    os._exit(0)
```

1. 结合 Q6 解释崩溃机制。为什么作者在 macOS 上可能没有遇到这个问题？
2. 给出至少两种修复方式，并说明各自的代价。
3. 为什么作者要用 `os._exit(0)` 而不是正常 `return`？

**Q10.** 证明组合的正确性：写一个**单进程**脚本，用同样的种子初始化 `MiniGPT`，用 `torch.optim.Adam(lr=5e-3)` 在"4 个 rank 的数据拼成的 batch=16"上训练 20 步，比较最终参数范数和 rank 0 那一段数据上的 loss。预期结果是什么？为什么在数学上应该相等？在什么情况下会不相等？

**Q11.** 内存账（均已用 Python 计算）：

1. 本节模型全是 fp32。按"参数 + 梯度 + ZeRO-1 分片（主参数 + m + v）"计算每 rank 的字节数；再与不用 ZeRO 的普通 fp32 Adam（参数 + 梯度 + m + v）比较。代码中的 `master_shard` 在这里是否必要？
2. 把同样的思路用在 70B 模型、64 张 GPU、混合精度（fp16 参数 2 B + fp16 梯度 2 B + 优化器 12 B）上：ZeRO-1、ZeRO-2、ZeRO-3 每张 GPU 各需多少 GB（只算这三项，不算激活）？80 GB 的卡用哪一级才放得下？

**Q12.** 讲义练习 3：实现"从 step 10 的 checkpoint 恢复并继续训练到 step 20，最终 loss 与原始运行一致"。写出恢复时每个 rank 需要做的事情，并回答：如果**只恢复优化器状态、忘了恢复 `model_state`**，或者**恢复时把 `step_count` 置 0**，分别会发生什么？

---

## 四、面试高频题

**Q13.**（基础必考）DDP、ZeRO-1、ZeRO-2、ZeRO-3（FSDP）分别切分了什么？每一级的通信量与每卡内存如何变化？

**Q14.**（原理深挖）为什么说 "all-reduce = reduce-scatter + all-gather"？请用 ring 算法说明每个 rank 发送的数据量，并解释 ZeRO-1 为什么"内存省了、通信没多"。

**Q15.**（工程实践）把这个 4 进程 CPU demo 搬到 64 张 GPU 的真实集群，你会改哪些东西？（后端、启动方式、checkpoint、容错、监控）

**Q16.**（场景设计）大模型训练中 loss 突然出现尖峰或 NaN，你会怎样设计自动检测与回滚机制？回滚之后如何避免再次掉进同一个坑？

**Q17.**（追问型）每个组件都有单元测试，为什么还需要端到端测试？一个好的分布式训练端到端测试应该断言哪些不变量？本节的四个不变量哪些实现得不够严格？

---

## 五、参考答案与解析

### Q1 — 答案：B

`_train_worker` 构造模型后对每个参数做 `dist.broadcast(p.data, src=0)`，这是 DDP 形状仅存的部分；之后每步 `optim.step()` 内部依次调用 `dist.reduce_scatter`（梯度求和到各自分片）和 `dist.all_gather`（发回更新后的主参数）。quiz.json 的解释："DDP's gradient allreduce is subsumed into ZeRO's reduce_scatter"。A 会做两次梯度同步，浪费带宽；C、D 与代码不符（代码没有使用 PyTorch 自带的 DDP 包装器或 `ZeroRedundancyOptimizer`，全部手写）。

### Q2 — 答案：D

逐项（实际打印 `model params: 29824`）：token embedding `64×32 = 2,048`；位置 embedding `16×32 = 512`；每个 block：两个 LayerNorm `4×32 = 128`、`qkv` `32×96 = 3,072`、`proj` `32×32 = 1,024`、MLP `32×128 + 128 + 128×32 + 32 = 8,352`，合计 12,576，两层 25,152；`ln_f` 64；LM head `32×64 = 2,048`。总计 29,824。A 是讲义的说法，实际是"三万左右"；B = 29,824 − 2,048，是 LM head 与 token embedding 共享权重时的数量（讲义说本节"untied for clarity"）；C 是 fp32 下参数占用的**字节数**。

### Q3 — 答案：A

`29,824 / 4 = 7,456`（刚好整除，无需补零），`7,456 × 3（主参数、m、v）× 4 字节 = 89,472`，与运行输出和 `expected per-rank` 一致，也就是讲义的 `12P/N`。B 是不分片时的 `12P`；C 是参数个数；D 是一份完整 fp32 参数的字节数。

### Q4 — 答案：C

`make_corpus` 用 `torch.randint(0, VOCAB, ...)` 生成独立均匀的 token，下一个 token 与上下文无关，理论最优 loss 就是 `ln 64 ≈ 4.1589`。开始时 4.297 略高，是因为随机初始化的 logits 不完全均匀；训练只能把输出分布拉向均匀，之后就在 4.1–4.46 之间随批次波动（每步都是新数据）。讲义的不变量 (a) 写"the loss decreases monotonically across the 20 steps within float noise"，实测不成立；quiz.json 已改为"loss runs to step 20 without NaN"，测试 `test_loss_finite_and_no_nan` 也只检查有限性。若想看到 loss 明显下降，需要换成有结构的语料（例如重复的模式或真实文本）。

### Q5 — 答案：D

每一步各 rank 的梯度来自**不同**的数据，若没有同步，参数会立刻分叉——所以 A 不对（相同种子只能保证初始化相同）。代码每步把 `torch.cat(gathered)[:self.total]` 这同一个张量 `scatter_flat_to_params` 回模型，各 rank 的参数因此逐位相同，范数差为 0。B 错：代码没有用 DDP 包装器，也没有梯度 all-reduce。C 不是原因：结果是严格相等而不是"差不多相等"。

### Q6 — 答案：A

`import torch` 会给 `multiprocessing` 的 pickler 注册张量的 reduction：CPU 张量会被移到共享内存，通过文件描述符传递，接收方反序列化时要连接发送方进程里的 `resource_sharer` 线程取回 fd。worker 在 `put` 之后立即 `os._exit(0)`，主进程反序列化时发送方已经不在了，于是得到 `EOFError` / `ConnectionResetError`。我们连续运行 3 次都失败（1 次 `EOFError`、2 次 `ConnectionResetError`），`pytest` 6 个用例全部失败。可以确认 Linux 上默认的共享策略是 `file_descriptor`。B、C 错：gloo 正常完成了 rendezvous 与训练（失败发生在结果回传阶段），代码在非 macOS 上用的就是 `lo`；D 错：失败发生在约 11 秒时，远未到 180 秒。

### Q7 — 答案：C

`_gather_payloads_to_rank0` 名字说"to rank0"，实际用的是两次 `dist.all_gather`：先交换各自的字节长度，再交换补零后的字节张量，所以**每个** rank 都收到了全部 4 份 payload，然后只有 rank 0 调用 `save_sharded` 写 4 个文件。讲义的组合规则表也写着"Called on rank 0 with state collected via allgather"。这是 80 节"gather-then-write"的反模式：写带宽受限于 rank 0，通信量与内存是 N 倍。A 才是 80 节推荐的做法；B 不符（用的是 all_gather 而非 gather）；D 错：每个分片里都有完整的 `model_state`（4 份完全相同的副本）加该 rank 的 `optim_state`。

### Q8 — 答案：B

`verify_resume` 只做一件事：`load_sharded` 后比较 `loaded[r]["optim_state"]["master_shard"]` 与 worker 回传的 `master_at_ckpt`（`torch.equal`）。它证明了"写进去的等于读出来的"，但没有恢复训练。A 是讲义练习 3 要你去实现的内容（见 Q12）；C、D 代码中都没有。讲义 Build It 对它的描述"reloads the step-10 checkpoint in-process and asserts the saved master shards match the in-memory snapshot byte-for-byte"是准确的，但不变量 (d) 中"reloads byte-equal at restart"容易让人误以为做了重启。

### Q9 — 参考答案

1. **机制**：见 Q6。关键在于"张量走共享内存 + fd 传递"这条路径要求发送方在接收方反序列化完成之前保持存活，而 `os._exit(0)` 打破了这个前提。`join_thread()` 只保证数据已写入管道，不保证对方已经取走 fd。PyTorch 在 macOS 上的默认共享策略是 `file_system`（通过文件名共享，不需要发送方在线），再结合代码中专门为 Darwin 写的 `lo0` 网卡名，可以推断作者是在 macOS 上开发和验证的（这是推断）。
2. **修复**（任选）：
   - 回传前把张量转成与 torch 无关的对象：`master_at_ckpt.numpy()`、`.tolist()` 或 `_serialize(...)` 的字节串。代价：一次拷贝，对小张量可以忽略。
   - 在 worker 中先调用 `torch.multiprocessing.set_sharing_strategy("file_system")` 再 `put`。我们用这种方式（在包装脚本里替换 `_train_worker`，不改原文件）实测：`main()` 正常输出并以 exit 0 结束，6 个测试全部通过（耗时约 180 秒）。代价：可能在 `/dev/shm` 留下共享内存文件，需要依赖 torch 的清理机制。
   - 让 worker 等主进程确认收到后再退出（例如再传一个 `Event`，主进程 `get` 完后 `set`）。代价：多一个同步原语。
3. `os._exit(0)` 直接结束进程，不执行 `atexit`、不做解释器清理、不等待非守护线程。代码没有调用 `dist.destroy_process_group()`；用 `os._exit` 可以避开 gloo 进程组析构时偶发的卡死或报错，让"自终止"更可靠。代价就是本题的 bug：任何依赖进程还活着的"后续工作"都会被腰斩。更稳妥的写法是：显式 `dist.barrier()` → `dist.destroy_process_group()` → 回传纯 Python 数据 → 正常返回。

### Q10 — 参考答案

```python
import torch, torch.nn.functional as F
import main as M

torch.manual_seed(M.SEED)
model = M.MiniGPT()
opt = torch.optim.Adam(model.parameters(), lr=M.LR, betas=(0.9, 0.999), eps=1e-8)
W, B, S, V = M.WORLD_SIZE, M.BATCH, M.SEQ_LEN, M.VOCAB
corpus = M.make_corpus(M.SEED + 7, W * B * (S + 1) * M.STEPS)
rank0_losses = []
for step in range(M.STEPS):
    off = step * W * B * (S + 1)
    block = corpus[off:off + W * B * (S + 1)].reshape(W * B, S + 1)   # 4 个 rank 的数据按 rank 顺序拼接
    x, y = block[:, :-1], block[:, 1:]
    opt.zero_grad()
    logits = model(x)
    loss = F.cross_entropy(logits.reshape(-1, V), y.reshape(-1))
    with torch.no_grad():                                              # rank 0 那 4 条序列上的 loss
        rank0_losses.append(F.cross_entropy(logits[:B].reshape(-1, V), y[:B].reshape(-1)).item())
    loss.backward()
    opt.step()
norm = sum(p.detach().pow(2).sum().item() for p in model.parameters()) ** 0.5
```

**实际结果**：单进程最终范数 `54.51317`，与分布式输出的 `54.513170` 一致；rank 0 那段数据上的 loss 序列前三个是 `4.297341, 4.295949, 4.237854`，最后两个是 `4.185369, 4.222419`，与分布式运行的输出逐个相同（6 位小数）。

**为什么相等**：
- 每个 rank 的 loss 是自己 64 个位置的平均；4 个 rank 的 batch 大小相同，"各 rank 梯度求和再除以 4"恰好等于"全部 256 个位置的平均 loss 的梯度"；
- Adam 的 m、v 更新与参数更新都是**逐元素**的，把扁平向量切成 4 段分别计算，与整体计算的结果完全相同；
- 偏差校正只依赖 `step_count`，各分片相同。

**何时不相等**：各 rank batch 大小不同（例如最后一个 batch 不满）却仍然简单除以 N；梯度裁剪按"本地范数"而不是"全局范数"做（全局范数需要跨分片再 all-reduce 一次）；带 BatchNorm 之类依赖 batch 统计量的层；以及浮点求和顺序不同带来的末位差异（本例规模小，6 位小数内一致）。

### Q11 — 参考答案

1. 本节（P = 29,824，N = 4，全 fp32）：

   | 项目 | 每 rank 字节（ZeRO-1） | 每 rank 字节（普通 fp32 Adam） |
   |------|----------------------|------------------------------|
   | 模型参数 | 119,296 | 119,296 |
   | 梯度 | 119,296 | 119,296 |
   | 主参数分片 | 29,824 | —（参数本身就是 fp32） |
   | m | 29,824 | 119,296 |
   | v | 29,824 | 119,296 |
   | 合计 | **328,064** | **477,184** |

   代码打印的"memory profile"只包含后三行（89,472），而讲义 Key Terms 说内存剖面是"params, grads, optimiser state"，打印内容与描述不一致。`master_shard` 在全 fp32 训练中是**冗余的**：它与模型参数对应分片逐位相同（每步就是用它覆盖模型参数）。它的意义在于模拟混合精度场景——那时模型参数是 fp16/bf16，必须另存一份 fp32 主参数，"12 字节"才是 4（主参数）+ 4（m）+ 4（v）。

2. 70B、64 卡、混合精度（Ψ = 70e9）：
   - ZeRO-1：`2Ψ + 2Ψ + 12Ψ/64 = 140 + 140 + 13.125 = 293.1 GB`
   - ZeRO-2：`2Ψ + (2Ψ + 12Ψ)/64 = 140 + 2.1875 + 13.125 = 155.3 GB`
   - ZeRO-3：`16Ψ/64 = 17.5 GB`

   只有 ZeRO-3（FSDP 的 FULL_SHARD）能放进 80 GB 的卡，而且还要给激活留空间（通常还要配合激活重计算）。这也说明本节"ZeRO-1 + DDP"的组合适合"模型参数能放进单卡、只是优化器状态放不下"的规模。

### Q12 — 参考答案

**恢复步骤**（每个 rank）：
1. 用同样的 world size 初始化进程组；
2. `load_sharded(ckpt_dir, expected_world_size)` 取出本 rank 的分片（或只读自己的 `rank{r}.bin`）；
3. 构造模型和 `ZeroOptimizer`，**同时**调用 `model.load_state_dict(state["model_state"])` 和 `optim.load_state_dict(state["optim_state"])`（后者恢复 master/m/v 与 `step_count`）；
4. 从 `step = 10` 开始继续循环，数据偏移 `offset = step * world_size * BATCH * (SEQ_LEN + 1) + rank * ...` 自然接上；
5. 跑到 step 20，与未中断运行的 loss 序列比较。

我们在单进程（gloo，world_size = 1）中用本节的 `MiniGPT` 与 `ZeroOptimizer` 实测：
- **模型 + 优化器都恢复**：step 10–19 的 loss 序列与不中断运行**完全相等**（最终都是 4.364540…）；
- **只恢复优化器、忘了 `model_state`**：恢复后第一步的 forward 用的是随机初始化的参数，loss 为 4.406082（应为 4.360636）；这一步的 optimizer step 会用主参数把模型覆盖回来，但这一步的梯度已经是在错误参数上算的，最终 loss 4.380538 ≠ 4.364540；
- **`step_count` 置 0**：Adam 的偏差校正 `1 − β^t` 被重置，已经积累好的 m、v 被当成"刚开始积累"的估计去放大。更新量与 `√(1−β2^t)/(1−β1^t)` 成正比：正常续训在 t = 11 时约 0.152，重置后 t = 1 时约 0.316，相当于前几步的有效学习率翻倍（t = 5 时仍为 0.172）。最终 loss 4.371615 ≠ 4.364540。

结论：恢复的"合同"不仅是 byte-equal，还要**完整**（参数、全部优化器状态与步数、数据位置；若有 dropout 还要 RNG 状态）。

### Q13 — 参考回答要点

- **DDP**：每卡完整的参数、梯度、优化器状态；每步 all-reduce 梯度。内存 `(2 + 2 + 12)Ψ`，通信约 `2Ψ`（ring all-reduce，以每卡发送量计）。
- **ZeRO-1（P_os）**：切分优化器状态；reduce-scatter 梯度 + all-gather 参数，通信仍约 `2Ψ`；内存 `4Ψ + 12Ψ/N`。
- **ZeRO-2（P_os+g）**：再切分梯度，每个 rank 只保留自己分片的归约后梯度；通信不变；内存 `2Ψ + 14Ψ/N`。
- **ZeRO-3 / FSDP FULL_SHARD（P_os+g+p）**：参数也切分，前向/反向时按层 all-gather 参数、用完即释放；通信约 `3Ψ`（前向一次 all-gather、反向一次 all-gather + 一次 reduce-scatter），即 1.5 倍；内存 `16Ψ/N`。
- 讲义："`FullyShardedDataParallel` with `ShardingStrategy.SHARD_GRAD_OP` is ZeRO-2"。
- 加分点：ZeRO-3 的额外通信可以与计算重叠（预取下一层参数）；节点内用 NVLink、节点间用 InfiniBand 时，可以采用混合分片（HYBRID_SHARD：节点内分片、节点间复制）。

### Q14 — 参考回答要点

- **ring reduce-scatter**：数据分成 N 块，N−1 步，每步每个 rank 把一块发给下一个邻居并与收到的块累加；结束时每个 rank 拥有一块的**完整归约结果**。每 rank 发送 `(N−1)/N · Ψ`。
- **ring all-gather**：再走 N−1 步，把各自的完整块传一圈，每 rank 发送 `(N−1)/N · Ψ`，结束时人人拥有全部结果。
- 二者相加 `2(N−1)/N · Ψ`，正是 ring all-reduce 的通信量——all-reduce 本来就是这两步。
- **ZeRO-1 的洞察**：DDP 在 reduce-scatter 之后又立刻 all-gather 出完整梯度，每个 rank 再对**全部**参数做一模一样的 Adam——计算和优化器状态都重复了 N 份。ZeRO-1 在两步之间插入"只更新自己那一块"，再 all-gather 的是**更新后的参数**而不是梯度。通信次数和量不变，优化器内存和计算都变成 1/N。
- 本节代码正对应这个流程：`dist.reduce_scatter(local_grad, chunks)` → 分片 Adam → `dist.all_gather(gathered, self.master_shard)`。

### Q15 — 参考回答要点

- **后端与启动**：gloo → NCCL（GPU 间通信）；`mp.spawn` + 文件 rendezvous → `torchrun`（或 Slurm）+ TCP/etcd rendezvous，`LOCAL_RANK` 绑定 GPU；去掉 `GLOO_SOCKET_IFNAME=lo`，配置真实的高速网卡（`NCCL_SOCKET_IFNAME`、IB 相关参数）。
- **训练**：用 PyTorch 自带的 DDP/FSDP 或 DeepSpeed 替代手写版本（bucket、通信与计算重叠、混合精度、梯度裁剪）；数据用 `DistributedSampler` 或预先分片的数据集。
- **checkpoint**：改成每个 rank 并行写自己的分片（80 节的思路，或 `torch.distributed.checkpoint`），而不是 all_gather 到 rank 0；按 wall-clock 频率、异步写、两级存储、只计数完整 checkpoint 的轮转。
- **容错**：`torchrun --max-restarts` 弹性重启；节点故障后从最近的完整 checkpoint 恢复，必要时重分片到新的 world size。
- **监控**：每 rank 的 step time、显存峰值（取 max 与 mean，讲义的"Aggregate the memory profile across ranks"）、梯度范数、loss、通信耗时；慢节点（straggler）检测。
- **结束**：显式 `destroy_process_group()`，避免本节 `os._exit` 的隐患。

### Q16 — 参考回答要点

- **检测**：每步 backward 后检查 loss 与全局梯度范数是否有限（需要在各 rank 之间 all-reduce 一个"是否有 NaN"的标志，保证所有 rank 一致决策）；用滑动窗口检测尖峰（讲义："if loss jumps by more than 2x in one step, roll back"）。
- **处置分级**：单步异常 → 跳过该步更新（混合精度的 loss scaler 本身就会这样做）；持续异常或尖峰 → 回滚到上一个完整 checkpoint。
- **避免重蹈覆辙**：回滚后跳过导致尖峰的那批数据（记录数据位置）、临时降低学习率或加强梯度裁剪、检查是否某个 rank 的硬件出错（例如比较各 rank 的梯度范数，找出异常的 GPU）。
- **前提**：checkpoint 足够频繁、恢复路径经常演练；回滚决策要所有 rank 一致，否则会死锁。
- 讲义练习 5 要求用"一步学习率乘数"人为制造尖峰来演练回滚。本节讲义说"the guard is unused but the hook stays"，但代码中实际上并没有这个 hook。

### Q17 — 参考回答要点

- **为什么需要**：单元测试验证的是组件**各自**的契约；组合会引入新的失败面——集合通信的调用顺序不一致导致死锁、rendezvous 配置、barrier 位置、checkpoint 的 gather 合同、进程退出与结果回传（本节在 Linux 上的崩溃就是典型的"组件都对、拼起来不对"）。
- **应断言的不变量**：
  1. 与单进程基线的数值等价（最有力：见 Q10）；
  2. 每步各 rank 参数一致（或参数哈希一致）；
  3. loss 有限，并在有结构的数据上确实下降；
  4. 每 rank 内存符合公式（包括参数、梯度、优化器，而不仅是优化器）；
  5. checkpoint 恢复后**继续训练**的 loss 与不中断运行一致；
  6. 有界时间内以 exit 0 结束（超时即失败）。
- **本节不够严格之处**：(a) 讲义说单调下降，实际只测了有限性，且随机语料不可能单调下降；(b) 讲义说"每一步"，实际只比较了最终范数；(c) 只统计了优化器分片，没统计参数和梯度；(d) 只比较了 master_shard，没有真正恢复训练。另外缺少与单进程基线的对比——它能一次性覆盖梯度平均、分片切分、补零截断等多处潜在错误。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 76 从零实现集合通信操作](../../76-collective-ops-from-scratch/docs/zh.md)：broadcast、reduce_scatter、all_gather 的语义与 ring 实现。
- [阶段 19 · 77 从零实现数据并行 DDP](../../77-data-parallel-ddp/docs/zh.md)：初始化 broadcast 与梯度同步。
- [阶段 19 · 78 ZeRO Optimizer 状态分片](../../78-zero-parameter-sharding/docs/zh.md)：本节 `ZeroOptimizer` 的出处。
- [阶段 19 · 80 分片 Checkpoint 与原子恢复](../../80-checkpoint-sharded-resume/docs/zh.md)：manifest、sha256 与原子写。
- [阶段 19 · 35 GPT 模型组装](../../35-gpt-model-assembly/docs/zh.md)：MiniGPT 的结构。
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：ZeRO 各阶段的内存与通信分析。

### 本节被哪些后续内容用到
- [阶段 19 · 79 流水线并行与流水线气泡分析](../../79-pipeline-parallel/docs/zh.md)：与数据并行组合成多维并行的另一维。
- [阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../48-distributed-fsdp-ddp/docs/zh.md)：把 ZeRO-3 / FSDP 的思路落到实现。
- [阶段 17 · 03 Kubernetes 上的 GPU Autoscaling](../../../17-infrastructure-and-production/03-gpu-autoscaling-kubernetes/docs/zh.md)：讲义说"Phase 17 是把这套组合搬到真实集群的地方"，成组调度（gang scheduling）正是分布式训练的前提。
- [阶段 17 · 24 LLM 生产环境中的混沌工程](../../../17-infrastructure-and-production/24-chaos-engineering-llm/docs/zh.md)：故意注入故障，检验 checkpoint/回滚链路。

### 延伸关键词
`torchrun` · `NCCL` · `ring all-reduce` · `reduce-scatter / all-gather` · `ZeroRedundancyOptimizer` · `FSDP SHARD_GRAD_OP / FULL_SHARD / HYBRID_SHARD` · `DeepSpeed ZeRO stage 1/2/3` · `torch.multiprocessing sharing strategy` · `elastic training` · `loss spike rollback` · `gradient accumulation`
