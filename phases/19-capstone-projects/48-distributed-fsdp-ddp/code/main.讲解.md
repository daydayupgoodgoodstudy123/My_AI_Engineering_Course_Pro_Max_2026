# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 48 节 从零实现分布式数据并行与 FSDP ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py [--world-size N] [--backend gloo] [--num-steps 6] [--batch-size 8] [--seed 0] [--no-write]` ｜ **依赖**：第三方 `torch`（CPU 版即可，需编译了 gloo）；其余为标准库（`argparse`、`json`、`os`、`socket`、`dataclasses` 等）。不需要 GPU、不需要网络（只用本机回环）。
>
> 提示：不加 `--no-write` 会覆盖 `outputs/ddp-demo.json`；只想看结果时建议加上。

---

## 1. 这份代码在考察什么

这份代码在一台 CPU 机器上用 `torch.multiprocessing` 起 N 个进程，通过 `gloo` backend 组成一个真正的进程组，然后做三件事：

1. **等价性实验**：每个 rank 在自己那一片数据上算梯度，`all_reduce` 求和再除以 N，与"单进程在拼接 batch 上的梯度"逐元素比较——证明数据并行在数学上没有改变训练。
2. **最小 DDP 包装器 `MinimalDDP`**：构造时 `broadcast` 参数，每次 backward 后 `all_reduce` 梯度；跑几步 SGD 后检查各 rank 参数仍然一致。
3. **FSDP 分片草图**：把每个参数拉平、补零、切成 N 片，再 `all_gather` 还原，验证分片—还原是无损的。

对应讲义的核心概念：进程组与 rendezvous、`broadcast` / `all_reduce` / `all_gather` 三个 collective、"DDP 契约"、梯度平均的等价性、FSDP 的 unshard。

> 一句话：**数据并行 = 起点一致（broadcast）+ 每步梯度一致（all-reduce）；FSDP = 参数平时只存 1/N、用时 all-gather**。同时要看清这份 demo 在哪些地方"测得不够狠"——它们正是面试追问点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `RankResult` | dataclass | 每个 rank 回传的结果字段 | 结果汇总 |
| `init_process_group` / `shutdown_process_group` | 函数 | 设置 rendezvous 环境变量、建组 / 销毁 | 进程组 |
| `make_model` | 函数 | `Linear → GELU → Linear` 小 MLP | 被并行的模型 |
| `broadcast_module` | 函数 | 把参数和 buffer 从 `src` 广播给所有 rank | broadcast |
| `all_reduce_grads_` | 函数 | 梯度求和 ÷ world_size，返回 L2 范数 | all-reduce 梯度平均 |
| `shard_for_rank` | 函数 | 把 batch 按第 0 维切给各 rank（余数给前面的 rank） | 数据分片 |
| `MinimalDDP` | `nn.Module` 子类 | 构造时广播，`sync_grads()` 时 all-reduce | DDP 契约 |
| `_grad_norm` | 函数 | 单进程梯度 L2 范数 | 对照值 |
| `fsdp_round_trip_sketch` | 函数 | 拉平 → 补零 → 切片 → all_gather → 去补零 → 比较 | FSDP unshard |
| `manual_all_reduce_matches_single_process` | 函数 | 分片梯度平均 vs 单进程全 batch 梯度 | 等价性证明 |
| `rank_main` | 函数 | 每个子进程的入口：建组 → 三个实验 → 结果放进队列 | worker |
| `free_port` | 函数 | bind 到端口 0 让系统分配一个空闲端口 | rendezvous 端口 |
| `run_distributed_demo` | 函数 | spawn N 个进程、收集结果、计算 spread | 启动器 |
| `write_demo` / `parse_args` / `main` | 函数 | 写 JSON、解析参数、断言三项检查 | CLI |

数据流：`main` → `run_distributed_demo` 选端口、`spawn` N 个 `rank_main` → 每个 rank：`init_process_group` → 等价性实验（得 `grad_norm`、`max_diff`）→ `MinimalDDP` 训练 `num_steps` 步 → `fsdp_round_trip_sketch` → 结果放进 `Queue` → 主进程汇总成字典 → 打印、断言、（可选）写 `outputs/ddp-demo.json`。

---

## 3. 逐段精讲

### 3.1 建组：rendezvous 与网卡

```python
def init_process_group(rank: int, world_size: int, backend: str, master_port: int) -> None:
    os.environ["MASTER_ADDR"] = "127.0.0.1"
    os.environ["MASTER_PORT"] = str(master_port)
    loopback = "lo0" if sys.platform == "darwin" else "lo"
    os.environ.setdefault("GLOO_SOCKET_IFNAME", loopback)
    os.environ.setdefault("TP_SOCKET_IFNAME", loopback)
    dist.init_process_group(backend=backend, rank=rank, world_size=world_size)
```

- `init_process_group` 默认用 `env://` 方式初始化：从环境变量读 `MASTER_ADDR`、`MASTER_PORT`。rank 0 在这个端口上起一个 TCPStore，其他 rank 去连它，交换各自的地址后建立 collective 通道——这就是讲义说的 rendezvous。
- `GLOO_SOCKET_IFNAME` 强制 gloo 走回环网卡（Linux 是 `lo`，macOS 是 `lo0`），避免在有多块网卡/容器网络的机器上选错接口而卡住。`setdefault` 表示用户已设置时不覆盖。
- 运行时会看到两行 `[c10d] The client socket cannot be initialized to connect to [localhost]... errno: 97` 的警告：客户端先尝试 IPv6 地址失败，随后回退到 IPv4 成功，不影响结果。

### 3.2 两个 collective 的封装

```python
def broadcast_module(module: nn.Module, src: int = 0) -> None:
    for tensor in list(module.parameters()) + list(module.buffers()):
        dist.broadcast(tensor.data, src=src)


def all_reduce_grads_(module: nn.Module, world_size: int) -> float:
    """Sum gradients across ranks, divide by world size, return l2 norm."""
    total_sq = 0.0
    for p in module.parameters():
        if p.grad is None:
            p.grad = torch.zeros_like(p.data)
        dist.all_reduce(p.grad.data, op=dist.ReduceOp.SUM)
        p.grad.data.div_(world_size)
        total_sq += float(p.grad.data.pow(2).sum().item())
    return total_sq ** 0.5
```

- `dist.broadcast(t, src=0)` 是**原地**操作：rank 0 发送，其他 rank 用收到的值覆盖自己的 `t`。连 `buffers()` 一起广播，是为了覆盖 BatchNorm 的 running mean/var 这类非参数状态（本例 MLP 没有 buffer）。
- `dist.all_reduce(..., SUM)` 也是原地操作，结束后**每个 rank** 拿到同一个和；再 `div_(world_size)` 得平均。函数名末尾的下划线沿用 PyTorch 惯例：表示"原地修改"。
- **补零那两行很关键**：collective 要求所有 rank 按同样顺序调用同样次数。某参数在某 rank 上没有梯度时如果跳过，各 rank 的第 k 次 all-reduce 就会对应到不同张量，可能挂起或静默错配（测验 Q3）。
- 返回值是平均后梯度的全局 L2 范数，用于日志（`grad_norm_after_all_reduce`）。每个参数一次 collective，没有分桶，也没有和 backward 重叠——这是与生产 DDP 的主要差距。

### 3.3 数据分片 `shard_for_rank`

```python
    per = total // world_size
    remainder = total - per * world_size
    start = rank * per + min(rank, remainder)
    end = start + per + (1 if rank < remainder else 0)
```

- 前 `remainder` 个 rank 各多拿 1 个样本。例：`total=11, world_size=3` → 大小 4、4、3；`total=10` → 下标 0–3、4–6、7–9。
- 这些分片拼起来正好是原张量，大小最多差 1（两个 helper 测试验证的正是这两点）。
- ⚠️ 分片不等大时，"各 rank 的 mean loss 梯度求平均"**不等于**全 batch 梯度。我们实测 10 个样本 / 3 个 rank：最大差 0.0222；按样本数加权后 1.5e-8。代码的等价性实验总用 `batch_size * world_size` 个样本，所以这个前提没有被暴露（测验 Q4、Q9）。

### 3.4 `MinimalDDP`

```python
class MinimalDDP(nn.Module):
    def __init__(self, module: nn.Module, world_size: int):
        super().__init__()
        self.module = module
        self.world_size = world_size
        if dist.is_initialized() and world_size > 1:
            broadcast_module(self.module, src=0)

    def forward(self, *args, **kwargs):
        return self.module(*args, **kwargs)

    def sync_grads(self) -> float:
        if not dist.is_initialized() or self.world_size == 1:
            return _grad_norm(self.module)
        return all_reduce_grads_(self.module, self.world_size)
```

- 把原模型存为 `self.module`（与 PyTorch DDP 一样，保存 checkpoint 时通常要取 `.module.state_dict()`，否则键名会多一个 `module.` 前缀）。
- 单进程或未建组时退化为普通模型，便于同一份训练脚本在单机调试。
- `forward(*args, **kwargs)` 原样透传所有参数。
- ⚠️ 文件开头 docstring 写"averages gradients in a post-backward hook"，实际是训练循环里**手动**调 `sync_grads()`；类 docstring 自己也承认生产 DDP 才用 hook。讲义练习 3 就是把它改成 hook 版（测验 Q12 给了已验证的实现）。

### 3.5 FSDP 往返草图

```python
    for p in module.parameters():
        full = p.data.detach().clone()
        flat = full.flatten()
        total = flat.numel()
        per = (total + world_size - 1) // world_size
        padded_total = per * world_size
        pad = padded_total - total
        if pad > 0:
            padded = torch.cat([flat, torch.zeros(pad, dtype=flat.dtype)])
        else:
            padded = flat
        my_slice = padded[rank * per:(rank + 1) * per].clone()
        gathered = [torch.empty(per, dtype=flat.dtype) for _ in range(world_size)]
        dist.all_gather(gathered, my_slice)
        rebuilt_padded = torch.cat(gathered)
        rebuilt = rebuilt_padded[:total].view_as(full)
        if not torch.allclose(rebuilt, full):
            ok = False
            break
```

- `(total + world_size - 1) // world_size` 是整数向上取整。gloo 的 `all_gather` 要求每个 rank 输出等长，所以必须补零到 `world_size` 的倍数，还原后再切掉。
- 本例模型 4 个参数 `(16,32)`、`(16,)`、`(4,16)`、`(4,)` 共 596 个元素。`world_size=3` 时 `per` 分别为 171、6、22、2，`pad` 分别为 1、2、2、2，每个 rank 持有 201 个元素。
- `gathered` 是预先分配好的 N 个空张量，`all_gather` 把 rank i 的 `my_slice` 填进 `gathered[i]`，所以 `torch.cat` 的顺序就是 rank 顺序。
- `view_as(full)` 把一维张量恢复成原形状（`[:total]` 切片是连续的，可以直接 view）。
- ⚠️ 这是**验证**而不是**节省**：`full` 是完整参数的拷贝，模块里的原参数也一直在，显存没有下降。它也没有把 gather 回来的张量用于 forward，而且是在训练**结束后**才调用。真正的 re-shard（练习 4）见测验 Q11。
- ⚠️ 各 rank 本来就持有完全相同的参数，所以"还原后等于本地原值"在 gather 顺序正确时必然成立；它能抓到的错误是"切片/拼接顺序写错、补零处理错"。

### 3.6 等价性实验

```python
    torch.manual_seed(0)
    full_x = torch.randn(batch_size * world_size, in_dim)
    full_y = torch.randint(low=0, high=out_dim, size=(batch_size * world_size,))
    my_x = shard_for_rank(full_x, rank, world_size)
    my_y = shard_for_rank(full_y, rank, world_size)

    torch.manual_seed(7)
    model = make_model(in_dim, hidden=16, out_dim=out_dim)
    broadcast_module(model, src=0)
    ...
    loss.backward()
    norm_after = all_reduce_grads_(model, world_size)

    if rank == 0:
        torch.manual_seed(7)
        ref_model = make_model(in_dim, hidden=16, out_dim=out_dim)
        ...
        ref_loss = loss_fn(ref_model(full_x), full_y)
        ref_loss.backward()
        ...
            diffs.append(float((p.grad.data - q.grad.data).abs().max().item()))
```

- 所有 rank 用种子 0 生成**同一份**全量数据，再各取一片——这样不用通信就能保证"拼起来就是全 batch"。
- rank 0 用同一个种子 7 再造一个参考模型，在全 batch 上算梯度，与 all-reduce 后的梯度逐参数比较最大绝对差。只有 rank 0 做比较，其他 rank 返回 `0.0`，主进程取最大值。
- 数学依据：`CrossEntropyLoss` 默认 mean 归约，各片等大时 `(1/N) Σ_r mean_r = mean_all`，求导是线性的，所以梯度也相等；剩下的差只来自浮点求和顺序（本次实测 7.45e-9）。
- `hidden=16` 写死在这里，与 CLI 无关；`torch.manual_seed(seed + rank)`（`rank_main` 第 239 行）在这之前调用，但随即被函数内部的 `manual_seed(0)` / `manual_seed(7)` 覆盖，实际上不起作用。
- ⚠️ 由于每个 rank 都 `manual_seed(7)` 后建模型，`broadcast_module` 在这里是"把相同值再复制一遍"，实验无法证明广播的必要性（测验 Q7）。

### 3.7 每个 rank 的训练循环

```python
        torch.manual_seed(seed)
        base = make_model(in_dim, hidden, out_dim)
        ddp_model = MinimalDDP(base, world_size)
        optimizer = torch.optim.SGD(ddp_model.parameters(), lr=lr)
        ...
        torch.manual_seed(seed * 31 + rank)
        for step in range(num_steps):
            x = torch.randn(batch_size, in_dim)
            y = torch.randint(low=0, high=out_dim, size=(batch_size,))
            optimizer.zero_grad()
            out = ddp_model(x)
            loss = loss_fn(out, y)
            loss.backward()
            ddp_model.sync_grads()
            optimizer.step()
            local_loss = float(loss.detach().item())
```

- 标准五步：`zero_grad → forward → loss → backward → sync_grads → step`。`sync_grads()` 必须夹在 `backward()` 与 `step()` 之间。
- `manual_seed(seed * 31 + rank)` 让每个 rank 生成**不同**的随机数据，模拟"各自读不同的数据分片"；`seed * 31` 只是让它和建模型时的种子错开。
- 因为每步每个 rank 拿到的平均梯度相同、SGD 是确定性的，参数会全程保持逐位一致（实测 `param_sum_spread = 0.0`）。换成带动量的 SGD 或 Adam 也一样，因为优化器状态也只依赖相同的梯度序列。
- `local_loss` 是本 rank 最后一步在**本地**数据上的 loss，没有做 all-reduce；所以输出里 `losses` 各不相同。讲义说"如果平均了梯度却不平均 loss，看板就会说谎"——这份代码本身就没有平均 loss，只是如实列出每个 rank 的值。
- `pre_param_sum` 计算了但没有出现在最终 JSON 里，只在 `RankResult` 中。

### 3.8 主进程：spawn、收集、汇总

```python
    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue()
    port = free_port()
    ...
    while collected < world_size and time.time() < deadline:
        try:
            rank, payload, diff = result_queue.get(timeout=1.0)
        except Exception:
            continue
```

- 用 `spawn` 启动方式：子进程是全新的 Python 解释器，重新 import 本模块再调用 `rank_main`。这要求 `rank_main` 是模块顶层函数（可被 pickle），也是为什么入口必须放在 `if __name__ == "__main__":` 里——否则子进程 import 时会再次启动 demo。
- `free_port()` 绑定端口 0 让操作系统分配空闲端口再关闭。讲义称之为 bind-and-close trick。注意存在极小的竞态：关闭后到 rank 0 真正监听之间，端口可能被别的进程抢走。
- 队列取结果带 1 秒超时轮询，总超时 60 秒。子进程异常时会把 `{"error": ...}` 放进队列，主进程最后会抛出 `rank X failed`。
- ⚠️ 如果一个 rank 出错退出而另一个 rank 卡在 collective 上，主进程会先命中"ranks did not finish in time"，真正的错误信息可能被掩盖。
- 汇总时 `param_sum_spread = max − min`。⚠️ 比较参数**总和**是一个很弱的一致性检查：我们实测把 rank 1 上两个权重元素互换，总和完全相同（spread = 0），但逐元素最大差是 0.1188（测验 Q10 给出更可靠的检查）。

### 3.9 `main` 的三个断言

```python
    assert result["param_sum_spread"] < 1e-3, "parameters diverged across ranks"
    assert result["fsdp_round_trip_all_ranks_ok"], "FSDP sketch round trip failed"
    assert result["manual_all_reduce_max_diff_vs_single_process"] < 1e-4, "manual all-reduce mismatched single-process gradient"
```

- 讲义写"asserts this with `max-abs-diff < 1e-3`"，代码 `main` 里实际用的是更严格的 `1e-4`，测试里用的是 `1e-3`。实测值 1e-8 量级，几种阈值都能通过。
- `json.dumps` 会把整数键 `{0: ..., 1: ...}` 转成字符串键 `"0"`、`"1"`，所以输出里 rank 编号带引号，顺序是结果到达队列的顺序。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| CPU + gloo + `torch.multiprocessing` | 任何机器都能跑，API 与 nccl 相同 | 速度慢几个数量级；生产用 nccl + `torchrun` |
| 手动 `sync_grads()` | 逻辑最清楚，看得到"backward 之后才同步" | 通信不能与 backward 重叠；生产用梯度 hook + 分桶 |
| 每个参数一次 all-reduce | 代码短 | 小张量多时启动延迟主导；生产按 ~25MB 分桶 |
| 无梯度参数补零后照样 all-reduce | 保证各 rank 调用对齐，不会挂起 | 多传了零；生产 DDP 用 `find_unused_parameters` 检测 |
| 所有 rank 用同一种子建模型 | 结果可复现 | 掩盖了"不广播就分叉"的失败模式 |
| 用参数总和比较一致性 | 每个 rank 只回传一个数 | 检测能力弱；应逐元素比较或比较哈希 |
| FSDP 只做"切片—gather—比较"往返 | 演示 unshard 的正确性 | 没有省显存，没有 backward 的 reduce-scatter；生产用 PyTorch FSDP |
| 等价性实验用整除的 batch | 等式严格成立 | 不等大分片时需按样本数加权或用 `DistributedSampler` 补齐 |
| 子进程异常放进队列 | 主进程能报出哪个 rank 失败 | 若另一 rank 卡在 collective，会先超时，掩盖真实错误 |
| `free_port()` bind-and-close | 并发运行不冲突 | 有小概率竞态；`torchrun` 用 c10d rendezvous 管理 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 类型注解延迟求值，允许在旧版本 Python 中写 `tuple[float, float]` |
| `@dataclass` | `class RankResult:` | 自动生成 `__init__` 等方法；`result.__dict__` 取出字段字典 |
| 类型注解 | `def shard_for_rank(x: torch.Tensor, rank: int, world_size: int) -> torch.Tensor` | 只是提示，不做运行时检查 |
| `Dict[str, object]`、`Optional` | `-> Dict[str, object]` | `typing` 模块的泛型写法 |
| 关键字专用参数 `*` | `def run_distributed_demo(world_size=2, *, backend="gloo", ...)` | `*` 之后的参数必须用关键字传入 |
| `*args, **kwargs` | `def forward(self, *args, **kwargs): return self.module(*args, **kwargs)` | 收集并原样转发任意位置/关键字参数 |
| 继承 `nn.Module` + `super().__init__()` | `class MinimalDDP(nn.Module)` | 先初始化父类，`self.module = module` 才会被注册为子模块 |
| `os.environ` / `setdefault` | `os.environ.setdefault("GLOO_SOCKET_IFNAME", loopback)` | 环境变量是字符串字典；`setdefault` 只在没有该键时写入 |
| 条件表达式 | `"lo0" if sys.platform == "darwin" else "lo"` | 一行 if-else |
| 生成器表达式 + `sum` | `sum(float(p.data.sum().item()) for p in ddp_model.parameters())` | 不建列表直接求和 |
| 列表推导式 | `[torch.empty(per, dtype=flat.dtype) for _ in range(world_size)]` | 预分配 N 个接收缓冲区 |
| 整数向上取整 | `(total + world_size - 1) // world_size` | `//` 是整除 |
| 原地方法（下划线结尾） | `p.grad.data.div_(world_size)` | PyTorch 惯例：`xxx_` 原地修改 |
| `try / except / finally` | `rank_main` 中 | 无论成功失败都在 `finally` 里销毁进程组 |
| 宽泛的 `except Exception: continue` | 队列轮询 | 捕获 `queue.Empty` 超时继续等；也会吞掉其他异常 |
| 函数内 import | `free_port` 里 `import socket` | 只在用到时导入 |
| `argparse` | `p.add_argument("--no-write", action="store_true")` | `--world-size` 自动变成属性 `args.world_size` |
| `raise SystemExit(main())` | 文件末尾 | 用 `main()` 的返回值作为进程退出码 |
| `if __name__ == "__main__":` | 文件末尾 | 用 `spawn` 启动子进程时尤其重要：子进程 import 本文件不会再次执行 demo |
| `pathlib.Path` | `HERE.parent / "outputs"` | `/` 拼接路径；`write_text` 写文件 |

---

## 6. 运行结果解读

实际运行（Python 3 + torch 2.14.1 CPU 版，`python3 main.py --no-write`，约 14 秒，主要是起进程和 import torch 的时间）：

```text
running distributed demo: backend=gloo, world_size=2
[W1012 ...] [c10d] The client socket cannot be initialized to connect to [localhost]:34437 (errno: 97 - Address family not supported by protocol).
{
  "world_size": 2,
  "backend": "gloo",
  "param_sum_per_rank": {
    "1": -1.2760529667139053,
    "0": -1.2760529667139053
  },
  "param_sum_spread": 0.0,
  "losses": [
    1.6027354001998901,
    1.378564715385437
  ],
  "grad_norm_after_all_reduce": 0.5539113843320747,
  "manual_all_reduce_max_diff_vs_single_process": 7.450580596923828e-09,
  "fsdp_round_trip_all_ranks_ok": true
}
```

逐项解读：

- **`errno: 97` 警告**：IPv6 连接尝试失败后回退到 IPv4，无害。
- **`param_sum_per_rank` 完全相同、`spread = 0.0`**：6 步 SGD 后两个 rank 参数一致。仓库自带的 `outputs/ddp-demo.json` 里是 −1.2760528326…，与本次的 −1.2760529667… 在第 7 位有效数字后不同，原因是不同 torch 版本/CPU 上浮点运算顺序不同，属正常。
- **`losses` 两个值不同**：它们是各 rank 在**各自**随机数据上的最后一步 loss，没有聚合。4 分类随机初始化的 loss 约为 `ln 4 ≈ 1.386`，这两个值都在附近，6 步训练几乎没学到东西（数据是纯随机的，本来也学不到）。
- **`grad_norm_after_all_reduce = 0.554`**：来自等价性实验（不是训练循环），是全 batch 平均梯度的 L2 范数。
- **`max_diff = 7.45e-9`**：all-reduce 平均梯度与单进程梯度只差浮点舍入（约 2⁻²⁷），讲义说"around 1e-8"，吻合。仓库 JSON 里是 2.33e-8，同样是舍入级别。
- **`fsdp_round_trip_all_ranks_ok = true`**：每个参数分片 → gather → 去补零后与原值相同。

改变 world size 的实测：

| `--world-size` | `param_sum_spread` | `max_diff` | `losses` |
|---|---|---|---|
| 2 | 0.0 | 7.45e-9 | 1.603, 1.379 |
| 3 | 0.0 | 2.24e-8 | 1.377, 1.600, 1.319 |
| 4 | 0.0 | 7.45e-9 | 1.347, 1.371, 1.594, 1.320 |

讲义练习 1（`--world-size 4`，spread < 1e-3）满足。注意不同 world size 下最终参数和不同（−1.276 / −1.268 / −1.240），因为全局 batch 变大了、每步看到的数据不同。

---

## 7. 动手改一改

1. **（练习 1）** 跑 `--world-size 4 --num-steps 50 --no-write`，确认 spread 仍为 0；再把训练种子改成 `torch.manual_seed(seed + rank)` 并删掉 `MinimalDDP` 中的广播，观察 spread 变大——这样才真正演示了"广播是必要的"。
2. **（练习 2）** 把 `all_reduce(SUM)` + `div_` 换成 `dist.all_reduce(p.grad, op=dist.ReduceOp.AVG)`。本环境 torch 2.14 的 gloo 已支持 `AVG`（我们实测 `[1, 2]` 平均得 1.5）；旧版本 gloo 可能不支持，需要捕获异常回退。用 `time.perf_counter()` 比较两种方式的耗时。
3. **一致性检查**：把 `param_sum_spread` 换成测验 Q10 的逐元素比较，并故意在 rank 1 上交换两个权重元素，确认新检查能发现而旧检查发现不了。
4. **（练习 3）** 用测验 Q12 的 `HookDDP`（`register_post_accumulate_grad_hook` + `async_op=True`）替换 `sync_grads()`；再实现简单分桶：把多个梯度 `torch.cat` 成一个缓冲区，一次 all-reduce 后再拆回去。
5. **（练习 4）** 按测验 Q11 的 `ShardedParam` 写一个真正只持有 1/N 参数的前向；用 `sum(t.numel() * t.element_size() for t in ...)` 打印每个 rank 的参数字节数，确认约为原来的 1/N。
6. **进阶**：把数据改成不等大分片（例如总样本 10、3 个 rank），先观察等价性实验失败，再按样本数加权修正（测验 Q9）。

---

## 8. 常见坑

- **没有 `if __name__ == "__main__":`**：`spawn` 模式下子进程 import 本文件会再次启动 demo，无限递归地起进程或报错。
- **忘记除以 `world_size`**：梯度放大 N 倍，相当于学习率放大 N 倍。
- **跳过无梯度参数的 all-reduce**：各 rank collective 调用不对齐，挂起或静默错配。
- **只在部分 rank 上调用 collective**（例如 `if rank == 0: dist.all_reduce(...)`）：其余 rank 永远不来，挂起。代码里 rank 0 的参考模型计算只做本地运算、不调用 collective，所以是安全的。
- **用参数总和判断同步**：互换、正负抵消的差异都检测不到。
- **以为同种子就不需要广播**：真实训练里不同机器、不同库版本、不同初始化路径都可能导致初值不同，广播是低成本的保险。
- **把 `losses` 当全局 loss 展示**：那是各 rank 本地值，需要先 all-reduce 再除以 N。
- **不等大分片直接平均 mean 梯度**：与单进程训练不等价。
- **运行 `main.py` 不加 `--no-write`**：会覆盖仓库中的 `outputs/ddp-demo.json`。
- **CPU 与 CUDA 张量混用同一个 collective**：技能文件提示会导致 backend 不匹配、运行挂起。

---

## 9. 测试在验证什么

`test_main.py` 用 `unittest` 编写，`import main as ddp` 后测试 4 组共 7 个用例：

| 测试 | 验证的性质 |
|------|-----------|
| `HelperTests.test_shard_for_rank_partitions_evenly` | `arange(20)` 分给 4 个 rank 后拼回去与原张量完全相同，且各片大小相差不超过 1 |
| `HelperTests.test_shard_for_rank_handles_remainder` | `arange(11)` 分给 3 个 rank，总数为 11，大小差不超过 1（余数处理正确） |
| `GradNormTests.test_grad_norm_zero_when_no_grads` | 没有 backward 时 `_grad_norm` 跳过 `None` 梯度，返回 0.0 |
| `GradNormTests.test_grad_norm_matches_manual_calc` | `_grad_norm` 与手写的 `sqrt(Σ g²)` 一致（6 位小数） |
| `DistributedDemoTests.test_two_rank_param_sums_match` | 2 个 rank 真正起进程组：spread < 1e-3、FSDP 往返成功、等价性差 < 1e-3 |
| `DistributedDemoTests.test_three_rank_param_sums_match` | 3 个 rank：spread < 1e-3、FSDP 往返成功（3 不整除参数元素数，测试了补零逻辑） |
| `OutputTests.test_write_demo_round_trip` | `write_demo` 写到临时目录，读回后带 `"schema": "ddp-demo.v1"` 且字段保留 |

- `DistributedDemoTests.setUp` 在 `torch.distributed` 或 gloo 不可用时 `skipTest`，所以在精简版 torch 上不会报错而是跳过。
- 输出测试用 `tempfile.TemporaryDirectory()`，不会覆盖仓库中的 `outputs/ddp-demo.json`。

运行方式与实际结果：

```text
$ cd code && python3 -m pytest -q
.......                                                                  [100%]
7 passed in 14.40s
```

（也可以用 `python3 -m unittest test_main -v` 或直接 `python3 test_main.py`。）

测试没有覆盖的地方（可以自己补）：

- "不广播会分叉"——因为所有 rank 同种子初始化，删掉广播测试也照样通过；
- 不等大分片下的梯度等价性；
- `param_sum` 相等但参数不等的情况；
- 某个 rank 出错时主进程能否报出正确的错误。
