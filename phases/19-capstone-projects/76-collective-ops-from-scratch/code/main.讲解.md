# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 76 节 从零实现集合通信操作 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（在 `code/` 目录下）；测试：`python -m unittest discover tests`（在小节根目录下） ｜ **依赖**：标准库 `multiprocessing` + 第三方 `torch`（CPU 即可，用到 `torch.distributed` 的 gloo 后端）；需要 `fork` 启动方式（Linux/macOS）。⚠️ 在 Linux 上直接运行会崩溃，见 3.8 与第 6 节

---

## 1. 这份代码在考察什么

分布式训练里所有的"同步"最终都落到四个集合通信原语上：allreduce、broadcast、allgather、reduce_scatter。这份代码不依赖 NCCL，用 `multiprocessing.Queue` 搭一个进程间的"网络"，从点对点 `send/recv` 出发亲手实现这四个原语：

1. **Ring allreduce 两阶段**：reduce-scatter（N−1 步累加）+ allgather（N−1 步覆盖），以及块下标的轮转规律。
2. **通信量**：用共享计数器统计发送字节，验证每 rank `2T(N−1)/N`。
3. **树形 broadcast**：每轮持有者翻倍，`⌈log2 N⌉` 轮。
4. **allgather / reduce_scatter**：前者是环上转一圈，后者是 allreduce 的前半段（加一次块旋转以符合 `torch.distributed` 的契约）。
5. **对拍验证**：在同样的输入上用 `torch.distributed` + gloo 跑一遍参考结果，比较最大绝对误差。
6. **多进程工程细节**：fork 与 spawn 两种启动方式、文件 rendezvous、超时与清理。

> 一句话：**把 NCCL 黑盒拆成"谁在第几步把哪一块发给谁"**。同时，这份代码有两个真实缺陷——`broadcast` 在 `src ≠ 0` 时死循环，以及在 Linux 默认配置下张量经队列传递会崩溃——正好说明"对拍测试覆盖不全"和"平台差异"在分布式代码中有多危险。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PRIMITIVES`、`RECV_TIMEOUT_S` | 常量 | 四个原语名（下游契约）；接收超时 30 秒 | — |
| `_loopback_iface` | 函数 | 返回回环网卡名（macOS `lo0`，Linux `lo`） | gloo 网络配置 |
| `Mesh` | dataclass | 每个 rank 的出/入队列表 + 字节计数器；`send/recv` | 点对点通信 |
| `build_queue_grid` / `mesh_from_grid` | 函数 | 建 N×N 队列网格，切出某个 rank 的视图 | 全连接 mesh |
| `ring_allreduce` | 函数 | 两阶段 ring allreduce，支持非整除长度（补零） | allreduce |
| `broadcast` | 函数 | 二项树广播 | broadcast |
| `allgather` | 函数 | N−1 步环形旋转 | allgather |
| `reduce_scatter` | 函数 | 旋转输入块 + ring 的前半段 | reduce_scatter |
| `_gloo_worker` / `gloo_reference` | 函数 | spawn N 个进程，用 gloo 跑同样的操作 | 参考实现 |
| `_mesh_worker` / `run_mesh` | 函数 | fork N 个进程，在 queue mesh 上跑本节实现，返回结果与总字节 | 执行框架 |
| `verify_against_gloo` | 函数 | 对两边结果求最大绝对误差，`< 1e-5` 视为匹配 | 对拍 |
| `main` | 函数 | 四个原语逐一对拍，再测 allreduce 字节数 | demo |

数据流：`main` 生成每个 rank 的随机张量 → `verify_against_gloo` → `run_mesh`（fork 4 个进程，各自 `_mesh_worker` → 原语 → 结果放回 `out_queue`）+ `gloo_reference`（spawn 4 个进程，`_gloo_worker` → `dist.*` → 结果放回队列）→ 比较 → 打印表格 → 单独再跑一次 allreduce 读取字节计数。

---

## 3. 逐段精讲

### 3.1 `Mesh`：点对点通信的最小抽象

```python
@dataclass
class Mesh:
    rank: int
    world_size: int
    out_queues: list
    in_queues: list
    byte_counter: object = None

    def send(self, dst: int, tensor: torch.Tensor) -> None:
        if dst == self.rank:
            raise ValueError("rank cannot send to itself")
        payload = tensor.detach().clone().contiguous()
        nbytes = payload.numel() * payload.element_size()
        if self.byte_counter is not None:
            with self.byte_counter.get_lock():
                self.byte_counter.value += nbytes
        self.out_queues[dst].put(payload)

    def recv(self, src: int) -> torch.Tensor:
        if src == self.rank:
            raise ValueError("rank cannot recv from itself")
        return self.in_queues[src].get(timeout=RECV_TIMEOUT_S)
```

- 每条有向边 `src → dst` 一个队列：rank r 的 `out_queues[d] = grid[r][d]`、`in_queues[s] = grid[s][r]`。一条边只有一个生产者和一个消费者，`Queue` 保证 FIFO，所以"第 k 次 send 对应第 k 次 recv"。
- 网格是 N×N 全连接（对角线为 `None`），ring 算法只用邻居边；docstring 说这是为了以后试验树形拓扑时不必重新接线。
- **字节计数**：`numel() * element_size()` 是逻辑字节数；`multiprocessing.Value("q", 0)`（64 位有符号整数）放在共享内存里，`get_lock()` 保证多个进程 `+=` 不丢更新（`+=` 不是原子操作）。
- **为什么 `clone()`**：`import torch` 后，`multiprocessing` 的 pickler 已被 torch 注册了张量 reducer——张量经队列发送时存储被移到共享内存，只传句柄。不复制的话，发送方之后原地修改同一张量，接收方会看到。⚠️ 这也意味着计数器统计的是"逻辑字节"，实际经过管道的只是一个很小的句柄。
- `recv` 有 30 秒超时，超时抛 `queue.Empty`。讲义练习 2 要"加一个 `recv_timeout_ms`"，代码其实已经有了一个固定的秒级超时，只是不可配置。

### 3.2 `ring_allreduce`：两阶段

```python
    n = tensor.numel()
    pad = (-n) % w
    flat = torch.zeros(n + pad, dtype=tensor.dtype)
    flat[:n] = tensor.flatten()
    chunks = [c.clone() for c in flat.chunk(w)]
    next_rank = (r + 1) % w
    prev_rank = (r - 1) % w
    for step in range(w - 1):
        send_idx = (r - step) % w
        recv_idx = (r - step - 1) % w
        mesh.send(next_rank, chunks[send_idx])
        incoming = mesh.recv(prev_rank)
        chunks[recv_idx] = chunks[recv_idx] + incoming
    for step in range(w - 1):
        send_idx = (r - step + 1) % w
        recv_idx = (r - step) % w
        mesh.send(next_rank, chunks[send_idx])
        incoming = mesh.recv(prev_rank)
        chunks[recv_idx] = incoming
    return torch.cat(chunks)[:n].reshape(tensor.shape)
```

- **补零**：`pad = (-n) % w` 是"补到 w 的倍数需要几个元素"（例如 n = 10、w = 4 → pad = 2）。补零不影响求和，最后 `[:n]` 截掉，再 `reshape` 回原形状。所以任意长度、任意形状都能处理（线程模拟验证 n = 10 正确）。
- **`flat.chunk(w)` 返回视图**，`.clone()` 让每块成为独立张量，后面 `chunks[i] = ...` 替换不会互相影响。
- **reduce-scatter**：第 s 步发送 `(r−s) mod w`，接收 `(r−s−1) mod w`，即"上一个 rank 发给我的那一块"——因为上一个 rank 发送的是 `((r−1)−s) mod w`，下标正好对上。接收块与本地同一块相加。
- **结束时的归属**：经过 w−1 步，rank r 手里完整的是块 `(r+1) mod w`（不是讲义说的块 r）。以 w = 3 为例，输入 `[1,2,3]`、`[10,20,30]`、`[100,200,300]`：

| 阶段 | rank 0 | rank 1 | rank 2 |
|------|--------|--------|--------|
| RS 第 0 步后 | `[1, 2, 303]` | `[11, 20, 30]` | `[100, 220, 300]` |
| RS 第 1 步后 | `[1, 222, 303]` | `[11, 20, 333]` | `[111, 220, 300]` |
| AG 第 0 步后 | `[111, 222, 303]` | `[11, 222, 333]` | `[111, 220, 333]` |
| AG 第 1 步后 | `[111, 222, 333]` | `[111, 222, 333]` | `[111, 222, 333]` |

- **allgather**：第 s 步发送 `(r−s+1) mod w`——第 0 步发出的正是刚完成的 `(r+1)` 块；接收的块直接**覆盖**（`=`，不是 `+=`）。因此每一块的最终值只在一个 rank 上算过一次，其它 rank 拿到的是同一份比特——所有 rank 的结果逐位相同。
- **通信量**：每个 rank 共发送 `2(w−1)` 块、每块 `(n+pad)/w` 个元素。demo 中 `2 × 3 × 16 × 4 B = 384 B`。
- **先 send 后 recv 不会死锁**：`Queue.put` 不阻塞（无界队列，后台 feeder 线程负责写管道），所以所有 rank 同时 send 再 recv 是安全的。如果换成阻塞的同步发送（如原始 socket），就需要奇偶 rank 交错收发。

### 3.3 `broadcast`：二项树

```python
    has_value = {src}
    out = tensor.clone() if r == src else torch.zeros_like(tensor)
    round_idx = 0
    while len(has_value) < w:
        new_holders = set()
        for h in sorted(has_value):
            partner = h + (1 << round_idx)
            if partner < w and partner not in has_value:
                if r == h:
                    mesh.send(partner, out)
                elif r == partner:
                    out = mesh.recv(h)
                new_holders.add(partner)
        has_value |= new_holders
        round_idx += 1
    return out
```

- **SPMD 风格**：每个 rank 都在本地模拟整张"谁持有值"的表，然后只执行和自己有关的 send/recv。所有 rank 看到的模拟过程相同，所以收发配对一致。
- 第 k 轮，每个持有者 h 发给 `h + 2^k`：`{0} → {0,1} → {0,1,2,3} → ...`，`⌈log2 w⌉` 轮。w = 5 时第 2 轮只有 0 → 4（线程模拟验证正确）。
- 非 src 的 rank 忽略自己的输入（用 `zeros_like` 占位），只取接收到的值。
- **通信量**：总共 w−1 次发送，每次 T 字节；但不均匀——src 发送 `⌈log2 w⌉` 次，叶子节点一次都不发。
- ⚠️ **`src ≠ 0` 时死循环**：`partner = h + 2^k` 只会向更大的 rank 扩展。N = 4、`src = 2`：第 0 轮 2 → 3，之后 `2 + 2 = 4`、`3 + 2 = 5` 都越界，`has_value` 永远停在 `{2, 3}`，`while` 永不退出。rank 0、1 甚至没进入 `recv`，所以 30 秒超时也不会触发。线程模拟中 4 个 rank 3 秒后全部仍在运行。修复：用虚拟 rank `vr = (r − src) mod w` 计算 partner，再映射回真实 rank（见测验 Q9）。demo 和测试都只用 `src=0`，gloo 参考也把 `src=0` 写死，所以没被发现。

### 3.4 `allgather` 与 `reduce_scatter`

```python
def allgather(mesh, tensor):
    shards = [torch.zeros_like(tensor) for _ in range(w)]
    shards[r] = tensor.clone()
    for step in range(w - 1):
        send_idx = (r - step) % w
        recv_idx = (r - step - 1) % w
        mesh.send(next_rank, shards[send_idx])
        shards[recv_idx] = mesh.recv(prev_rank)
    return torch.cat(shards)
```

- 与 ring allreduce 的第二阶段同构：第 0 步发自己的分片，之后每步转发刚收到的那一片。输出按 rank 顺序拼接，长度 `w × 输入长度`。每个 rank 发送 `w−1` 个分片。

```python
def reduce_scatter(mesh, tensor):
    n = tensor.numel()
    if n % w != 0:
        raise ValueError(...)
    if w == 1:
        return tensor.clone()
    rotated = list(tensor.chunk(w))
    rotated = [rotated[(i - 1) % w].clone() for i in range(w)]
    chunks = rotated
    for step in range(w - 1):
        ...                                   # 与 ring_allreduce 第一阶段完全相同
        chunks[recv_idx] = chunks[recv_idx] + incoming
    return chunks[(r + 1) % w]
```

- `torch.distributed.reduce_scatter` 的契约是"rank r 得到块 r 的总和"。而 ring 第一阶段把块 `(r+1)` 的总和留在 rank r。代码的技巧：先把输入块整体右移一位（`rotated[i] = 原块[(i−1) mod w]`），于是 `rotated[(r+1) mod w] = 原块[r]`，ring 结束后返回这一块即为原块 r 的总和。
- 这里要求 `n` 能被 `w` 整除（不像 allreduce 那样补零），因为输出长度必须是 `n/w`。
- 每个 rank 发送 `w−1` 块，即 `T(N−1)/N`（T 为输入总字节），正好是 allreduce 的一半。

### 3.5 gloo 参考实现

```python
def _gloo_worker(rank, world_size, op, tensor_bytes, shape, dtype_str, init_file, iface, out_queue):
    os.environ["GLOO_SOCKET_IFNAME"] = iface
    dist.init_process_group(backend="gloo", init_method=f"file://{init_file}",
                            rank=rank, world_size=world_size)
    dtype = getattr(torch, dtype_str)
    tensor = torch.frombuffer(bytearray(tensor_bytes), dtype=dtype).reshape(shape).clone()
    if op == "allreduce":
        dist.all_reduce(tensor, op=dist.ReduceOp.SUM)
    ...
    elif op == "reduce_scatter":
        chunks = [c.contiguous() for c in tensor.chunk(world_size)]
        recv = torch.zeros_like(chunks[0])
        dist.reduce_scatter(recv, chunks, op=dist.ReduceOp.SUM)
    out_queue.put((rank, out.clone()))
    out_queue.close()
    out_queue.join_thread()
    os._exit(0)
```

- **spawn 启动**：`torch.distributed` 的进程组需要干净的进程，不能从已初始化 torch 线程池的父进程 fork。
- **文件 rendezvous**：`init_method="file://..."`，N 个进程通过同一个临时文件交换地址；docstring 说是因为 macOS 上 TCP（libuv）初始化并发创建进程组有问题。`GLOO_SOCKET_IFNAME` 指定走回环网卡。
- **传参方式**：张量先序列化成 `bytes` + 形状 + dtype 字符串（`str(torch.float32).split(".")[-1] == "float32"`），子进程用 `torch.frombuffer` 还原。`bytearray(...)` 是因为 `frombuffer` 需要可写缓冲区，否则会警告；`.clone()` 让张量拥有自己的内存。
- `os._exit(0)`：跳过解释器正常退出流程（atexit、进程组析构），避免 gloo 在退出时卡住；在此之前先 `close()` + `join_thread()` 确保队列数据已写进管道。
- `gloo_reference` 的 `finally` 中依次 `join(timeout=5)`、必要时 `terminate()`，并删除 rendezvous 文件和临时目录。
- ⚠️ 讲义写的是 `_gloo_reference(op, world_size, tensor)`，代码实际名字和签名是 `gloo_reference(op, world_size, per_rank_tensors)`；各原语的签名也都是 `(mesh, tensor[, src])`，而不是讲义的 `(mesh, rank, world_size, tensor)`。

### 3.6 `run_mesh` 与 `_mesh_worker`

```python
def run_mesh(op, world_size, per_rank_tensors, src=0):
    ctx = mp.get_context("fork")
    grid = build_queue_grid(ctx, world_size)
    byte_counter = ctx.Value("q", 0)
    out_queue = ctx.Queue()
    ...
        for r in range(world_size):
            p = ctx.Process(target=_mesh_worker, args=(r, world_size, op, grid, byte_counter, ...))
            p.start()
        results = {}
        for _ in range(world_size):
            rank, tensor = out_queue.get(timeout=60)
            results[rank] = tensor
        return [results[r] for r in range(world_size)], byte_counter.value
    finally:
        for p in procs:
            p.join(timeout=30)
            ...
```

- **fork 启动**：子进程直接继承父进程中已创建的 N×N 个队列和共享计数器，无需 pickle 队列对象（模块 docstring 的说明）。
- 结果按 rank 编号放回字典再排序输出，因为 `out_queue` 中的顺序取决于谁先完成。
- 返回 `byte_counter.value` 是**所有 rank 的总发送字节**，`main` 再除以 `world_size` 得到每 rank 的平均值（ring 是对称的，平均值即每个 rank 的值）。

### 3.7 `verify_against_gloo` 与 `main`

```python
def verify_against_gloo(op, world_size, per_rank_tensors):
    mesh_out, _ = run_mesh(op, world_size, per_rank_tensors)
    gloo_out = gloo_reference(op, world_size, per_rank_tensors)
    max_diff = 0.0
    for m, g in zip(mesh_out, gloo_out):
        diff = (m - g).abs().max().item()
        ...
    return max_diff < 1e-5, max_diff
```

- 判据是最大绝对误差 `< 1e-5`。⚠️ 模块 docstring 说"checked byte-for-byte"，讲义说"byte-equal comparison"、"diverges from gloo by more than float32 epsilon, the test fails"——实际 allreduce 的差值是 `4.768e-07`，既不是字节相等，也大于 float32 的 machine epsilon（约 1.19e-7）。原因是浮点加法顺序不同；用容差比较才是正确做法。
- `main` 中 broadcast 的输入只有 rank 0 有值；reduce_scatter 的输入长度是 `n × world_size = 256`；其余两个原语用同一组 `per_rank`。
- 最后单独跑一次 allreduce 读字节数，与公式 `2 × (N−1) × (n/N) × 4` 比较。⚠️ 这个公式用了整除 `n // world_size`，只在 n 能被 N 整除时等于实测值（否则实测会因补零略大）。

### 3.8 平台问题：为什么在 Linux 上直接运行会崩溃

`import torch` 会注册张量的多进程 reducer。Linux 上默认 sharing strategy 是 `file_descriptor`：队列中传递的是"去发送进程那里领取 fd"的凭据，接收方反序列化时要通过 `multiprocessing.resource_sharer` 的 Unix socket 连回发送进程。`_mesh_worker` 把结果 `put` 进 `out_queue` 后函数返回、子进程退出，父进程再 `get` 时发送方已不在，于是 `FileNotFoundError`；ring 中最后一次发送也可能遇到同样的竞争，下游 rank 在 `recv` 上等满 30 秒得到 `queue.Empty`。`_gloo_worker` 的 `join_thread()` 只保证凭据写入管道，不保证对方已经取走 fd，所以 gloo 路径同样失败（单独调用得到 `EOFError`）。

macOS 上默认 strategy 是 `file_system`，不需要发送方存活，作者大概因此没有遇到。最小修复：在模块顶层加

```python
import torch.multiprocessing
torch.multiprocessing.set_sharing_strategy("file_system")
```

（放在顶层而非 `main()` 里，是因为 spawn 子进程会重新导入主模块，只有顶层代码会再执行一次。）也可以改为通过队列发送 `bytes`/NumPy 数组，不让 torch 的共享内存机制介入。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| `multiprocessing.Queue` 当网络 | CPU 上可复现 NCCL 的通信模式 | 实际走共享内存句柄，性能与真实网络无关；生产用 NCCL（GPU）/ gloo（CPU） |
| N×N 全连接队列 | 方便以后实验其它拓扑 | 队列数 O(N²)，ring 只用到 2N 条 |
| 先 send 后 recv | 无界队列不阻塞，代码最简单 | 换成阻塞式传输会死锁，需要交错收发 |
| allreduce 补零到 N 的倍数 | 支持任意长度 | 少量额外通信；字节公式需按补零后长度计算 |
| reduce_scatter 先旋转块 | 复用 ring 第一阶段，又满足"rank r 拿块 r"契约 | 多一次本地拷贝 |
| 二项树 broadcast | 轮数 log2 N | 只支持 `src = 0`（bug）；真实实现用虚拟 rank 或流水线分块 |
| 与 gloo 对拍、容差 1e-5 | 有独立的参考答案 | 每个原语要 spawn N 个进程，单次对拍约 25 秒；只测了 N = 4、`src = 0` |
| fork + spawn 两种启动方式 | 队列继承方便 / 进程组需要干净进程 | Windows 不支持 fork；Linux 下张量共享策略问题导致崩溃 |
| 30 秒接收超时 | 卡死时能报错 | 不可配置；broadcast 死循环发生在 recv 之前，超时无效 |
| 字节计数器统计逻辑字节 | 直接验证 `2T(N−1)/N` | 不等于实际传输量；生产用 NCCL 自带的计数或 profiler |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| `@dataclass` | `class Mesh` | 自动生成 `__init__`；`byte_counter: object = None` 是带默认值的字段 |
| 负数取模 | `(r - step - 1) % w`、`pad = (-n) % w` | Python 的 `%` 结果与除数同号，`(-1) % 4 == 3`，天然适合环形下标 |
| 位运算 | `1 << round_idx`、`k <<= 1` | 左移一位等于乘 2，用来算 `2^k` |
| 集合运算 | `has_value |= new_holders`、`partner not in has_value` | 并集赋值、成员判断 |
| 列表推导式嵌套 | `[[None] * world_size for _ in range(world_size)]` | 正确创建二维列表；写成 `[[None]*w]*w` 会让各行共享同一个列表 |
| 列表推导式 + 条件 | `[per_rank[0].clone() if r == 0 else torch.zeros(n) for r in range(world_size)]` | 推导式中使用条件表达式 |
| `with lock:` | `with self.byte_counter.get_lock():` | 进入时加锁，退出时释放 |
| `multiprocessing.get_context` | `mp.get_context("fork")`、`mp.get_context("spawn")` | 显式选择启动方式，不修改全局默认 |
| `ctx.Value("q", 0)` | 字节计数器 | 共享内存中的 C 类型变量，`"q"` 表示 `long long` |
| `ctx.Process(target=..., args=...)` | `_mesh_worker`、`_gloo_worker` | 创建子进程；`args` 是传给 target 的位置参数元组 |
| `try/finally` | `run_mesh`、`gloo_reference` | 无论是否异常，都会回收子进程、删除临时文件 |
| `try/except 具体异常` | `except FileNotFoundError: pass` | 只忽略预期的异常 |
| `getattr(模块, 名字)` | `getattr(torch, dtype_str)` | 由字符串 `"float32"` 取到 `torch.float32` |
| `os.environ[...] =` | `os.environ["GLOO_SOCKET_IFNAME"] = iface` | 设置当前进程的环境变量（影响 gloo） |
| `os._exit(0)` | `_gloo_worker` 末尾 | 立即退出进程，不执行清理钩子 |
| `raise SystemExit(main())` | 文件末尾 | 与 `sys.exit(main())` 等价 |
| 函数内导入 | `_loopback_iface` 里 `import sys as _sys` | 局部导入并起别名 |
| f-string 对齐与科学计数 | `{op:<16}`、`{diff:<14.3e}`、`{per_rank_bytes:.0f}` | 左对齐宽度 16；科学计数法 3 位小数；不带小数 |
| torch：`chunk` / `cat` / `flatten` / `reshape` | `flat.chunk(w)`、`torch.cat(chunks)[:n].reshape(tensor.shape)` | 切块（返回视图）、拼接、展平、改形状 |
| torch：`detach` / `clone` / `contiguous` | `tensor.detach().clone().contiguous()` | 去掉梯度历史、复制存储、保证内存连续 |
| torch：`numel` / `element_size` | `payload.numel() * payload.element_size()` | 元素个数 × 每元素字节数 |
| torch：`frombuffer` | `torch.frombuffer(bytearray(b), dtype=dtype)` | 从字节缓冲区构造张量（共享内存，所以再 `.clone()`） |

---

## 6. 运行结果解读

**直接运行（未修改，Linux、Python 3.13、torch 2.14.1 CPU）**：输出表头后立即崩溃，退出码 1：

```text
world_size=4, tensor_len=64, dtype=float32
op               gloo_match   max_abs_diff
Traceback (most recent call last):
  ...
  File ".../torch/multiprocessing/reductions.py", line 538, in rebuild_storage_fd
    fd = df.detach()
  ...
FileNotFoundError: [Errno 2] No such file or directory
```

原因见 3.8。**用一个只增加 `torch.multiprocessing.set_sharing_strategy("file_system")` 的包装脚本运行**（不修改 `main.py`）后，结果如下（总耗时约 1 分 43 秒，绝大部分是 gloo 参考路径 spawn 进程并导入 torch，每个原语约 25 秒；mesh 路径一次只需约 0.6 秒）：

```text
world_size=4, tensor_len=64, dtype=float32
op               gloo_match   max_abs_diff
allreduce        True         4.768e-07
broadcast        True         0.000e+00
allgather        True         0.000e+00
reduce_scatter   True         4.768e-07

allreduce per-rank bytes: measured=384 expected=384 formula=2T(N-1)/N with T=256 bytes
```

逐项解读：

- **allreduce / reduce_scatter 差 4.768e-07**：只有涉及加法的原语有误差，来源是求和顺序不同（浮点加法不满足结合律）；这大约是数值量级 1～4 时 float32 的几个 ULP。
- **broadcast / allgather 差 0**：只搬运数据、不做运算，结果逐位相同。
- **384 字节**：`2 × 256 × 3 / 4 = 384`，验证了 `2T(N−1)/N`。若 N 从 4 增加到 64，每 rank 的发送量只从 `1.5T` 增长到约 `1.97T`——这就是"与集群规模无关"的含义。
- **其它验证（线程模拟，非 demo 输出）**：n = 10（不能被 4 整除）时 allreduce 结果正确；4 个 rank 的 allreduce 结果逐位相同；`broadcast(src=2)` 在 N = 4 时 3 秒后 4 个 rank 全部仍在死循环。

---

## 7. 动手改一改

1. **修复 broadcast**：用虚拟 rank 重写（参考测验 Q9），给 `_gloo_worker` 增加 `src` 参数，并补一个 `src = 2` 的对拍测试。
2. **修复 Linux 崩溃**：在模块顶层设置 `file_system` 策略；或者把 `Mesh.send/recv` 改成传 `payload.numpy().tobytes()` + 形状/dtype，看看字节计数的含义有没有变化。
3. **可配置超时**（讲义练习 2）：给 `Mesh` 增加 `recv_timeout_s` 字段，超时时抛出带 `rank`、`src`、当前步数的自定义异常。
4. **树形 allreduce**（讲义练习 1）：先沿二项树 reduce 到 rank 0，再用 `broadcast` 发回；用字节计数器比较它与 ring 的通信量，再按消息大小在两者间切换。
5. **测量交叉点**（讲义练习 5）：在 4 个 rank 上测 1 KB、1 MB、16 MB 的 ring 与 tree 耗时，与 α-β 模型（测验 Q12）的预测对比；注意 queue mesh 的耗时主要是 Python 和共享内存开销，结论未必与真实网络一致。
6. **进阶**（讲义练习 3）：把队列换成 TCP socket（每条边一个连接），保持四个原语和测试不变，体会"同样的通信模式、不同的介质"。

---

## 8. 常见坑

- **下标约定混淆**：本节 ring 结束时 rank r 持有的是块 `(r+1) mod N`，不是块 r；直接拿 `chunks[r]` 当 reduce_scatter 结果会错位。
- **只测一个 src / 一个 N**：broadcast 的死循环就藏在没测的 `src ≠ 0` 里；N 应覆盖 2、奇数、非 2 的幂。
- **要求与参考实现字节相等**：只要涉及加法就做不到，应使用 `allclose` 并给出合理容差。
- **`[[None] * w] * w`**：创建二维列表时的经典错误，所有行指向同一个列表。
- **发送后原地修改张量**：经 torch 共享内存传递时会产生别名问题，所以 `send` 里必须 `clone()`。
- **子进程发完就退出**：Linux 默认 `file_descriptor` 策略下，接收方还没领取 fd 发送方就退出，会 `FileNotFoundError`。
- **fork 与 CUDA / 已初始化的 torch 线程**：fork 出的子进程不能使用父进程中已初始化的 CUDA 上下文；本节只在 CPU 上 fork，gloo 路径则用 spawn。
- **用整除公式验证字节数**：`n // world_size` 在不能整除时与实测值不符（补零会多发几个元素）。

---

## 9. 测试在验证什么

测试文件：`tests/test_collectives.py`（位于小节根目录的 `tests/`，不在 `code/` 下），共 7 个 `unittest` 用例。它通过 `sys.path.insert(0, str(HERE.parent / "code"))` 导入 `main`。运行方式（在小节根目录）：

```bash
python3 -m unittest discover tests
```

| 用例 | 验证的性质 |
|------|-----------|
| `test_allreduce_matches_gloo` | N = 4、长度 32，queue mesh 与 gloo 的 allreduce 结果 `allclose(atol=1e-5)` |
| `test_broadcast_matches_gloo` | N = 4、`src=0`，所有 rank 与 gloo 一致，并且等于 src 的原始张量 |
| `test_allgather_matches_gloo` | 输出长度为 `n × ws`，与 gloo 一致 |
| `test_reduce_scatter_matches_gloo` | 每个 rank 输出长度为 `per_chunk`，与 gloo 一致（验证了块旋转技巧） |
| `test_allreduce_byte_count_matches_formula` | 每 rank 字节数恰好等于 `2 × (ws−1) × (n/ws) × 4` |
| `test_allreduce_world_size_two` | 最小非平凡规模 N = 2，`[1,…]` + `[2,…]` = `[3,…]`（不经 gloo） |
| `test_primitive_names` | `PRIMITIVES` 恰好是四个原语名——下游第 77～81 节依赖的契约 |

**实际运行结果**：

- 未修改直接运行（Linux）：`6 failed, 1 passed in 62.01s`，只有不涉及多进程的 `test_primitive_names` 通过，其余报 `FileNotFoundError` 或 `_queue.Empty`。
- 用设置了 `file_system` 策略的包装脚本运行同一测试目录：`Ran 7 tests in 94.558s  OK`。

测试没有覆盖：`src ≠ 0` 的 broadcast（会死循环）、不能被 N 整除的 allreduce 长度、N ≠ 2/4 的规模、接收超时路径、非 float32 的 dtype。
