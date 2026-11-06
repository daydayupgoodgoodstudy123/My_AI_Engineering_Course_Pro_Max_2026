# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 77 节 从零实现数据并行 DDP ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（在 `code/` 目录下）；测试：`python -m unittest discover tests`（在小节根目录下） ｜ **依赖**：标准库 `multiprocessing` + 第三方 `torch`（CPU 即可，`torch.distributed` gloo 后端）

---

## 1. 这份代码在考察什么

DDP（DistributedDataParallel）听上去复杂，核心其实只有两次集合通信：**构造时 broadcast 参数**，**反向后 allreduce 梯度**。这份代码用最薄的一层包装把这两件事暴露出来，并用一个单进程参考实现证明它是对的：

1. **数据并行的契约**：N 个 rank 各持完整模型、各算一个数据分片，每步梯度取平均，所有副本保持一致。
2. **平均梯度**：allreduce-SUM 后本地除以 world_size。
3. **等价性证明**：单进程按 rank 顺序处理全部分片、loss 除以 N 累加梯度，与 DDP 每步结果相同。
4. **多进程工程**：spawn 启动、文件 rendezvous、结果回传、进程回收。

> 一句话：**DDP = 相同的起点（broadcast）+ 相同的每步增量（allreduce 平均梯度）**。读这份代码要同时注意它省略了什么——没有 hook、没有分桶、没有重叠，而讲义正文把这些写成了"本节实现了的"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SEED / WORLD_SIZE / STEPS / BATCH / *_DIM` | 常量 | 7、4 个 rank、20 步、每 rank 8 条、16→32→32→4 | 实验配置 |
| `_loopback_iface` | 函数 | gloo 使用的回环网卡名 | 网络配置 |
| `MiniMLP` | `nn.Module` | 三层 MLP，1,732 个参数、6 个参数张量 | 被训练的模型 |
| `DistributedDataParallel` | 类 | 构造时 broadcast；`sync_grads()` allreduce + 除以 N | DDP 核心 |
| `make_dataset` | 函数 | 固定种子生成线性回归数据 `y = xW + 噪声` | 合成数据 |
| `_ddp_worker` | 函数 | 每个 rank 的训练循环 | rank 进程 |
| `run_ddp` | 函数 | spawn N 个 rank，收集各 rank 的 loss 历史与参数范数 | 启动器 |
| `reference_single_process` | 函数 | 单进程模拟 N 个 rank 的平均梯度 | 正确性基准 |
| `main` | 函数 | 跑 DDP 和参考，打印逐步 loss 表与最终范数 | demo |

数据流：`main` → `run_ddp`（spawn 4 个 `_ddp_worker`：`init_process_group` → `MiniMLP` → DDP 构造时 broadcast → 20 步 {切自己的分片 → 前向 → `MSELoss` → 反向 → `sync_grads` → `SGD.step`} → 放回 `(rank, losses, norm)`）→ `reference_single_process`（同样的数据、同样的初始权重，单进程模拟）→ 打印对比表。

---

## 3. 逐段精讲

### 3.1 模型与数据

```python
class MiniMLP(nn.Module):
    def __init__(self, in_dim=IN_DIM, hid_dim=HID_DIM, out_dim=OUT_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hid_dim), nn.ReLU(),
            nn.Linear(hid_dim, hid_dim), nn.ReLU(),
            nn.Linear(hid_dim, out_dim),
        )
```

- 参数量：`16×32+32 = 544`、`32×32+32 = 1,056`、`32×4+4 = 132`，共 **1,732**；`parameters()` 返回 6 个张量（3 个 weight + 3 个 bias），所以每步 `sync_grads` 发起 6 次 allreduce。

```python
def make_dataset(seed: int, n_total: int) -> tuple:
    g = torch.Generator().manual_seed(seed)
    x = torch.randn(n_total, IN_DIM, generator=g)
    w = torch.randn(IN_DIM, OUT_DIM, generator=g)
    y = x @ w + 0.1 * torch.randn(n_total, OUT_DIM, generator=g)
    return x, y
```

- 用**独立的 `torch.Generator`** 而不是全局种子：数据只取决于传入的 `seed`（`SEED + 1000`），与模型初始化消耗了多少全局随机数无关。每个 rank 都生成同一份完整数据集，再各取各的切片。
- 目标 `y` 的方差约为 `‖w 的列‖² ≈ 16`，所以初始 MSE 在 10 左右（输出中 step 0 的 loss 为 9.97）。

### 3.2 `DistributedDataParallel`：两个集合操作

```python
class DistributedDataParallel:
    def __init__(self, module: nn.Module, world_size: int):
        self.module = module
        self.world_size = world_size
        self._broadcast_params()

    def _broadcast_params(self) -> None:
        for p in self.module.parameters():
            dist.broadcast(p.data, src=0)

    def sync_grads(self) -> None:
        for p in self.module.parameters():
            if p.grad is None:
                continue
            dist.all_reduce(p.grad.data, op=dist.ReduceOp.SUM)
            p.grad.data.div_(self.world_size)
```

- **broadcast 是原地操作**：rank 0 发送，其它 rank 用收到的值覆盖 `p.data`。之后所有 rank 的参数逐位相同，与各自的初始化种子无关（我们把初始化种子改成 `SEED + rank` 实测，参数差仍为 0.0；去掉 broadcast 则 10 步后差到 0.49）。
- **为什么用 `p.data` / `p.grad.data`**：绕过 autograd 记录，对叶子张量做原地修改不会报错，也不会把通信纳入计算图。现代写法是 `with torch.no_grad(): dist.broadcast(p, 0)`。
- **SUM 再除以 N**：gloo 不支持 `ReduceOp.AVG`（NCCL 支持），所以先求和再本地除。得到平均梯度，学习率的含义不随 rank 数变化。
- ⚠️ **不是 `nn.Module`**：只提供 `forward / parameters / sync_grads`，训练循环必须写 `ddp.forward(x)`（`ddp(x)` 会报错），并且必须**手动**在 `backward()` 后调用 `sync_grads()`。PyTorch DDP 是在每个参数上注册反向 hook，自动在梯度就绪时发起通信；讲义开头也是这么描述的，但本节代码没有 hook。
- ⚠️ **逐参数通信**：6 次 allreduce/步，没有分桶，也没有和反向计算重叠。讲义说"For the lesson's tiny model we group everything into one bucket"，与代码不符。
- ⚠️ **`if p.grad is None: continue`**：如果只有部分 rank 的某个参数没有梯度（前向有分支），各 rank 的集合调用次数不同，会错位或挂起——这正是讲义练习 3 中 `find_unused_parameters` 要解决的问题。

### 3.3 `_ddp_worker`：每个 rank 的训练循环

```python
    os.environ["GLOO_SOCKET_IFNAME"] = iface
    dist.init_process_group(backend="gloo", init_method=f"file://{init_file}",
                            rank=rank, world_size=world_size)
    torch.manual_seed(SEED)
    model = MiniMLP()
    ddp = DistributedDataParallel(model, world_size=world_size)
    optim = torch.optim.SGD(ddp.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    x_all, y_all = make_dataset(SEED + 1000, n_total=world_size * batch * steps)
    for step in range(steps):
        offset = step * world_size * batch + rank * batch
        x = x_all[offset:offset + batch]
        y = y_all[offset:offset + batch]
        optim.zero_grad(set_to_none=True)
        pred = ddp.forward(x)
        loss = loss_fn(pred, y)
        loss.backward()
        ddp.sync_grads()
        optim.step()
        losses.append(loss.item())
```

- **数据切分**：数据集共 `4 × 8 × 20 = 640` 条，第 `step` 步占用 `[step×32, step×32+32)`，rank r 取其中第 r 段 8 条。每条样本只被用一次，各 rank 互不重叠——相当于不打乱的 `DistributedSampler`。
- **顺序**：`zero_grad → forward → backward → sync_grads → step`。`set_to_none=True` 把 `.grad` 置为 `None` 而不是清零，省一次内存写入；反向后梯度重新生成。
- **每个 rank 独立 `optim.step()`**：优化器状态从不通信。因为各 rank 的参数和梯度都相同，SGD 更新后仍相同（对 Adam 等有状态优化器同理）。
- 记录的 `loss` 是**本 rank 分片**上、同步前的 loss。
- 结束时计算参数的 L2 范数 `sqrt(Σ p²)`，连同 loss 列表放回队列；随后 `close()` + `join_thread()` 确保数据写入管道，再 `os._exit(0)` 跳过 gloo 进程组的析构流程。队列里传的都是 Python 浮点数，不涉及张量共享（所以不会遇到第 76 节在 Linux 上的共享内存问题）。

### 3.4 `run_ddp`：启动器

```python
    ctx = mp.get_context("spawn")
    out_queue = ctx.Queue()
    init_dir = tempfile.mkdtemp(prefix="aie_ddp_")
    init_file = os.path.join(init_dir, "rendezvous")
    ...
        for r in range(world_size):
            p = ctx.Process(target=_ddp_worker,
                            args=(r, world_size, init_file, iface, steps, batch, lr, out_queue))
            p.start()
        results = {}
        for _ in range(world_size):
            rank, losses, norm = out_queue.get(timeout=120)
            results[rank] = (losses, norm)
        return results
    finally:
        # join(5) → terminate → 删除 rendezvous 文件与目录
```

- **spawn**：每个 rank 是全新的解释器，重新导入 `main` 模块（所以模块顶层只能有定义，真正的执行在 `if __name__ == "__main__"` 之下）。`torch.distributed` 需要干净的进程。
- **文件 rendezvous**：所有 rank 通过同一个临时文件交换地址，不需要指定端口；每次运行用新的临时目录，避免与上一次残留的文件冲突。
- ⚠️ 讲义学习目标说用 `torch.multiprocessing.spawn`，代码用的是标准库 `multiprocessing` 的 spawn 上下文，效果类似但 API 不同（`mp.spawn(fn, nprocs=N)` 会自动把 rank 作为第一个参数传入，并在任一子进程异常时终止其它进程）。
- 结果字典以 rank 为键，返回值类型注解写的是 `tuple`，实际是 `dict`。

### 3.5 `reference_single_process`：正确性的"另一条路"

```python
    torch.manual_seed(SEED)
    model = MiniMLP()
    ...
    for step in range(steps):
        optim.zero_grad(set_to_none=True)
        rank0_loss = None
        for r in range(world_size):
            offset = step * world_size * batch + r * batch
            x = x_all[offset:offset + batch]
            y = y_all[offset:offset + batch]
            pred = model(x)
            loss = loss_fn(pred, y) / world_size
            loss.backward()
            if r == 0:
                rank0_loss = loss.item() * world_size
        optim.step()
        losses.append(rank0_loss)
```

- **为什么等价**：`.backward()` 把梯度**累加**到 `.grad`。4 次 `∇(L_r / 4)` 的和 = `(Σ ∇L_r) / 4` = DDP 的 allreduce-SUM 再除以 4。初始权重相同（同一个 `SEED`，DDP 那边 rank 0 也用 `SEED`，再广播给其它 rank），数据切片相同，所以每步更新相同。
- 记录的是 rank 0 那一片的 loss（`loss.item() * world_size` 把除掉的 4 乘回去），以便与 DDP rank 0 的 loss 对比。除以 4、乘以 4 都是 2 的幂运算，在浮点下是精确的，所以实测 loss **逐位相同**（差值 0.0）。若 world_size = 3，乘除会引入舍入，可能只在最后一位相同。
- 前提：各分片样本数相同。`MSELoss` 默认取分片内均值；分片大小不等时，"均值的均值"不等于全局均值，DDP 的平均梯度会偏向小分片。

### 3.6 `main`：对比表

```python
    print(f"\n{'step':<6}{'ref_loss':<14}{'ddp_rank0':<14}{'ddp_rank3':<14}{'rank_drift':<14}")
    rank0_losses, rank0_norm = ddp_results[0]
    rank3_losses, _ = ddp_results[WORLD_SIZE - 1]
    for s in range(STEPS):
        drift = abs(rank0_losses[s] - rank3_losses[s])
        print(...)
    print(f"\nfinal param norm: ref={ref_norm:.6f}, ddp_rank0={rank0_norm:.6f}")
```

- ⚠️ `rank_drift` 比较的是 rank 0 与 rank 3 **在不同数据分片上**的 loss，它们本来就该不同（0.13～5.38），不能说明参数是否漂移。真正反映一致性的是参数本身：可以每步记录参数校验和并比较（见测验 Q11）。
- ⚠️ 讲义说表格会显示"parameter checksum"，实际只在最后打印一次参数范数；范数相同也不等于参数相同（不同向量可以有相同的范数）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 薄包装类，显式 `sync_grads()` | 通信发生在哪里一目了然 | 容易忘记调用；PyTorch DDP 用反向 hook 自动触发 |
| 逐参数 allreduce | 代码最短 | 每步 6 次调用，大模型会有成千上万次；生产用约 25 MB 的桶 |
| 反向全部结束后才通信 | 简单 | 通信完全暴露在关键路径上；生产在反向过程中重叠通信 |
| SUM + 本地除以 N | gloo 没有 AVG | 多一次本地运算，可忽略；NCCL 可直接用 `ReduceOp.AVG` |
| 构造时 broadcast 参数 | 保证起点逐位相同 | 一次性开销；buffer（如 BN 统计量）也需要同步 |
| 确定性切片而非打乱 | 让参考实现能复现完全相同的数据 | 真实训练用 `DistributedSampler` + `set_epoch` |
| 单进程参考实现 | 独立的正确性基准 | 只比较 loss 与最终范数，比"逐步比较参数"弱 |
| spawn + 文件 rendezvous | 跨平台、无需端口 | 每次启动要重新导入 torch，测试较慢（6 个用例约 23 秒） |
| SGD、20 步、lr = 0.05 | 快速演示 | loss 波动大，谈不上收敛 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `SEED = 7`、`WORLD_SIZE = 4` | 全大写表示常量；在函数默认参数中引用 |
| 默认参数引用常量 | `def __init__(self, in_dim: int = IN_DIM, ...)` | 默认值在函数**定义时**求值一次 |
| 继承 `nn.Module` | `class MiniMLP(nn.Module)` + `super().__init__()` | 必须先调用父类构造函数，子模块才能被注册 |
| `nn.Sequential` | 三个 `Linear` 与两个 `ReLU` | 按顺序串联子模块 |
| 生成器对象 | `def parameters(self): return self.module.parameters()` | `module.parameters()` 返回生成器，只能遍历一次；每次调用都会得到一个新的生成器 |
| `torch.Generator().manual_seed(seed)` | `make_dataset` | 独立随机数流，不影响全局种子 |
| 方法链 | `torch.Generator().manual_seed(seed)`、`p.detach().pow(2).sum().item()` | 每个方法返回对象，可以继续调用 |
| 原地运算 | `p.grad.data.div_(self.world_size)` | 下划线结尾的 torch 方法原地修改张量 |
| 生成器表达式求和 | `sum(p.detach().pow(2).sum().item() for p in ...) ** 0.5` | 不建中间列表；`** 0.5` 开平方 |
| 切片 | `x_all[offset:offset + batch]` | 取第 offset 到 offset+batch−1 行（返回视图） |
| 关键字参数 | `optim.zero_grad(set_to_none=True)` | 明确参数含义 |
| 元组解包 | `rank, losses, norm = out_queue.get(timeout=120)` | 一次接收多个返回值 |
| 字典 | `results[rank] = (losses, norm)` | 以 rank 为键收集无序到达的结果 |
| `try/finally` | `run_ddp` | 保证子进程被回收、临时文件被删除 |
| `os.environ` | `os.environ["GLOO_SOCKET_IFNAME"] = iface` | 设置环境变量，影响 gloo 的网卡选择 |
| f-string 对齐与格式 | `{'step':<6}`、`{ref_losses[s]:<14.6f}`、`{drift:<14.2e}` | 左对齐宽度；6 位小数；科学计数法 |
| `raise SystemExit(main())` | 文件末尾 | 用返回值作为退出码 |

---

## 6. 运行结果解读

实际运行（Linux、Python 3.13、torch 2.14.1 CPU，`cd code && python3 main.py`，约 8 秒，退出码 0）：

```text
world_size=4, steps=20, batch=8, model=MiniMLP
running DDP across ranks...
running single-process reference...

step  ref_loss      ddp_rank0     ddp_rank3     rank_drift
0     9.972533      9.972533      10.594129     6.22e-01
1     10.442020     10.442020     10.310112     1.32e-01
2     14.129453     14.129453     11.502509     2.63e+00
...
17    8.970582      8.970582      7.135619      1.83e+00
18    12.417347     12.417347     7.035938      5.38e+00
19    8.561934      8.561934      12.318209     3.76e+00

final param norm: ref=5.148460, ddp_rank0=5.148460
```

逐项解读：

- **`ref_loss` 与 `ddp_rank0` 每一步完全相同**：我们用更高精度比较，20 步的最大差值为 0.0。由于 rank 0 第 s 步的 loss 取决于前 s 步更新后的参数，这间接证明了 rank 0 的参数在每一步都与参考一致。
- **最终参数范数**：DDP 与参考相差约 3.2e-8（6 位小数下显示相同），来自 gloo 求和与 autograd 累加的顺序不同；4 个 rank 之间的范数差为 0.0。
- **`rank_drift` 不是漂移**：它是 rank 0 与 rank 3 在不同 8 条样本上的 loss 差，本来就该在 0.1～5 之间波动。
- **loss 没有明显下降**：前 5 步均值 11.64，后 5 步均值 10.05。每步只看 32 条新样本、SGD 学习率 0.05、20 步，远不够拟合；而且每步 loss 是在不同数据上算的，噪声很大。这个 demo 证明的是"同步正确"，不是"训练有效"。

---

## 7. 动手改一改

1. **修正对比表**：每步记录参数校验和（`torch.cat([p.flatten() ...]).double().sum()`），把 `rank_drift` 改为"各 rank 校验和的最大差"，同时打印 DDP 与参考的校验和差。
2. **单桶同步**：把 `sync_grads` 改为拼接成一个扁平张量、一次 allreduce、再拆回（测验 Q9）；比较与原版的数值差异（实测约 1e-6）。
3. **`no_sync()`**（讲义练习 2）：实现上下文管理器，用 K = 2 的梯度累积训练，与"单进程大 batch"对比（测验 Q10，实测参数差约 3e-8）。
4. **未使用参数**（讲义练习 3）：让 rank 1 的前向跳过第二个 `Linear`（例如 `if rank == 1 and step % 2: 走捷径`），观察 `sync_grads` 错位后的报错或挂起；再实现一个"缺失梯度补零"的版本修复它。
5. **反向 hook + 重叠**：用 `p.register_post_accumulate_grad_hook` 在每个梯度就绪时调用 `dist.all_reduce(..., async_op=True)`，在 `step` 前 `wait()` 所有句柄，与原版对拍。
6. **进阶**（讲义练习 5）：把模型加深加宽，测量 batch = 1、16、256 时同步耗时占 step 时间的比例，解释为什么 batch 越大，通信占比越小。

---

## 8. 常见坑

- **忘记 broadcast 只靠种子**：不同平台、不同库版本或初始化顺序的差异都可能让参数不同；broadcast 才是保证。
- **忘记调用 `sync_grads()`**：本节没有 hook，漏调一次，各 rank 就会以不同梯度更新，从此不再一致。
- **在 `zero_grad` 之前或 `step` 之后同步**：顺序必须是 backward → sync → step。
- **除了两次或没除**：梯度尺度错 N 倍，等于学习率错 N 倍；参考实现中 loss 也必须除以 N。
- **分片大小不等**：最后一个不完整的 batch 会让"均值的均值"偏离全局均值；用 `drop_last` 或按样本数加权。
- **各 rank 用了相同的数据**：数据并行退化为"同一个 batch 算 N 遍"，浪费算力且没有增大有效 batch。
- **只比较范数**：范数相等不代表参数相等；测试应比较参数向量。
- **`ddp(x)` 报错**：本节的包装类不是 `nn.Module`，没有 `__call__`，要写 `ddp.forward(x)`。

---

## 9. 测试在验证什么

测试文件：`tests/test_ddp.py`（位于小节根目录的 `tests/`），共 6 个用例。它把 `code/` 加入 `sys.path` 后导入 `main`。运行方式（在小节根目录）：

```bash
python3 -m unittest discover tests -v
```

实际运行结果：`Ran 6 tests in 22.583s  OK`（每个涉及 `run_ddp` 的用例都要 spawn 进程，耗时几秒）。

| 用例 | 验证的性质 |
|------|-----------|
| `test_ddp_rank0_loss_matches_single_process` | 4 rank、10 步，DDP rank 0 每步 loss 与单进程参考相同（`places=4`） |
| `test_all_ranks_end_with_same_param_norm` | 10 步后 4 个 rank 的参数范数相同（`places=5`），即副本没有漂移 |
| `test_ddp_param_norm_matches_reference` | DDP 最终参数范数与参考相同（`places=5`） |
| `test_mini_mlp_param_count` | 参数量大于 0，且有 6 个参数张量 |
| `test_world_size_two_still_converges` | world_size = 2 时能跑完 5 步并返回浮点 loss——⚠️ 名字说"converges"，实际没有检查 loss 下降 |
| `test_seed_constant_is_documented` | `SEED == 7`（防止有人改了常量导致文档中的数字对不上） |

测试的局限：用范数而不是参数向量比较一致性；没有测试梯度累积、未使用参数、不等长分片；`places=4/5` 的容差比实际达到的精度（逐位相同 / 3e-8）宽松得多。
