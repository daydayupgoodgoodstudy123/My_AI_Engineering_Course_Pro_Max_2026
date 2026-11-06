# 测验 · 从零实现集合通信操作（Collective Ops From Scratch）

> **阶段 19 · 综合项目 · 第 76 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（测试：[tests/test_collectives.py](../tests/test_collectives.py)） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四个集合原语 | allreduce（人人得到总和）、broadcast（一人的值发给所有人）、allgather（人人得到所有分片的拼接）、reduce_scatter（每人只得到总和的一个分块） |
| 2 | 朴素 allreduce 的问题 | 全部发给 root 再广播回去：root 收发 `(N−1)·T`，带宽随 N 线性增长，root 成为瓶颈 |
| 3 | Ring allreduce = reduce-scatter + allgather | 张量切成 N 块，两轮各 N−1 步，每步每个 rank 只向下一个 rank 发一块 `T/N` |
| 4 | 带宽最优 | 每 rank 发送 `2T(N−1)/N` 字节，N 很大时趋近 `2T`，**与集群规模基本无关**；本节 N=4、T=256 B 时实测 384 B |
| 5 | 树形算法 | broadcast 每轮持有者翻倍，`⌈log2 N⌉` 轮；树形 allreduce 深度 log2 N，适合小消息或高延迟链路 |
| 6 | Ring vs Tree 的取舍 | 延迟项（步数 × α）vs 带宽项（字节 / β）；讲义：NCCL 大约在 1 MB 以上选 ring、以下选 tree |
| 7 | 与训练框架的对应 | DDP 用 allreduce 同步梯度；ZeRO 用 reduce_scatter 分片梯度、allgather 恢复参数；FSDP 前向 allgather、反向 reduce_scatter |
| 8 | Queue mesh 模拟 NCCL | 每条边一个 `multiprocessing.Queue`，单生产者单消费者、有序送达；通信模式与 NCCL ring 相同，只是介质不同 |
| 9 | 与参考实现对拍 | 用 `torch.distributed` + gloo 在同样输入上运行；浮点加法顺序不同，结果只能"足够接近"（代码用 `< 1e-5`），不是字节相等 |
| 10 | 生产模式 | 梯度分桶（DDP 默认约 25 MB）、通信与反向计算重叠、按消息大小选拓扑 |

### 核心技能（能动手做到）

- [ ] 手工追踪 N=3 或 N=4 的 ring allreduce，写出每一步每个 rank 发送/接收哪一块、持有什么
- [ ] 推导 ring allreduce、allgather、reduce_scatter 的每 rank 通信量，并用代码的字节计数器验证
- [ ] 用 α-β 模型估算 ring 与 tree 的耗时交叉点
- [ ] 找出并修复 `broadcast` 在 `src ≠ 0` 时死循环的问题
- [ ] 解释本节代码在 Linux 上直接运行崩溃（`FileNotFoundError`）的原因，并给出修复
- [ ] 说清楚 DDP、ZeRO、FSDP 分别在什么时候调用哪个集合原语

---

## 二、基础自测（选择题）

**Q1.** 本节 demo 中 world_size N = 4，每个 rank 的张量是 64 个 float32（T = 256 字节）。ring allreduce 中**每个 rank 发送**的字节数是：

- A. 256
- B. 512
- C. 768
- D. 384

**Q2.** 按本节 `ring_allreduce` 的下标约定（第 s 步 rank r 发送块 `(r−s) mod N`、接收并累加块 `(r−s−1) mod N`），reduce-scatter 阶段结束后，rank r 持有哪一块的**完整总和**？

- A. 块 r
- B. 块 `(r+1) mod N`
- C. 块 `(r−1) mod N`
- D. 全部 N 块

**Q3.** demo 输出中 allreduce 与 gloo 的 `max_abs_diff` 是 `4.768e-07`，而 4 个 rank 之间的 ring 结果彼此**逐位相同**。最合理的解释是：

- A. 浮点加法不满足结合律，ring 与 gloo 的求和顺序不同；而 ring 中每一块的总和只由一个 rank 算一次，再在 allgather 阶段原样复制给其它 rank
- B. 队列传输时发生了精度损失
- C. gloo 使用 float16 计算
- D. ring 实现有 bug，应该改为与 gloo 字节相等才算正确

**Q4.** 用本节的树形 `broadcast`（`src = 0`）在 N = 8 个 rank 上广播，需要多少轮？全体 rank 合计发送多少次？

- A. 7 轮，7 次
- B. 3 轮，3 次
- C. 3 轮，7 次
- D. 8 轮，8 次

**Q5.** N = 4，每个 rank 向 `allgather` 输入 8 个 float32 的分片。下列说法正确的是：

- A. 输出长度为 8，每个 rank 发送 32 字节
- B. 输出长度为 32，每个 rank 发送 128 字节
- C. 输出长度为 8，每个 rank 发送 96 字节
- D. 输出长度为 32，每个 rank 发送 96 字节

**Q6.** `Mesh.send` 在放入队列前执行 `tensor.detach().clone().contiguous()`。其中 `clone()` 最重要的作用是：

- A. 导入 torch 后，`multiprocessing.Queue` 会通过 torch 注册的 reducer 把张量存储搬到共享内存再传句柄；不复制的话，发送方之后对同一张量的原地修改可能被接收方看到（别名问题）
- B. 让张量从 GPU 移到 CPU
- C. 把 float32 转为 float64 以提高精度
- D. 让字节计数器能统计到正确的字节数

**Q7.** 关于集合原语在训练框架中的用法，下列对应关系正确的是：

- A. DDP：每个参数 broadcast 一次梯度
- B. ZeRO：用 allreduce 分片优化器状态
- C. FSDP：前向前用 allgather 拼出完整层参数，反向后用 reduce_scatter 把梯度分片归约
- D. 流水线并行：每个 micro-batch 都需要一次全局 allreduce 传递激活

**Q8.** 讲义说 NCCL 会"按消息大小而不是信仰"选择拓扑。下面哪种说法正确？

- A. 消息越大越应该用 tree，因为 tree 的步数少
- B. 大消息（约 1 MB 以上）用 ring：带宽项 `2T(N−1)/N` 占主导；小消息用 tree：`log2 N` 的跳数让延迟项更小
- C. 两者的通信量相同，只是实现难度不同
- D. ring 只能用于 N 为 2 的幂的集群

---

## 三、动手 / 代码题

**Q9.** 阅读 `broadcast`：

```python
def broadcast(mesh: Mesh, tensor: torch.Tensor, src: int) -> torch.Tensor:
    w = mesh.world_size
    r = mesh.rank
    if w == 1:
        return tensor.clone()
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

1. 在 N = 4、`src = 2` 时逐轮追踪 `has_value`，会发生什么？
2. 为什么 demo 和测试都没有发现这个问题？
3. 用"虚拟 rank"`vr = (r − src) mod N` 重写，使任意 `src` 都正确。

**Q10.** 在 Linux（PyTorch 2.x、Python 3.13）上直接执行 `python3 code/main.py`，输出表头后立刻崩溃：

```text
  File ".../torch/multiprocessing/reductions.py", line 538, in rebuild_storage_fd
    fd = df.detach()
  ...
FileNotFoundError: [Errno 2] No such file or directory
```

直接跑测试则是 `6 failed, 1 passed`（报错为 `FileNotFoundError` 或 `_queue.Empty`）。

1. 解释崩溃原因（提示：`import torch` 对 `multiprocessing.Queue` 做了什么？Linux 上默认的 sharing strategy 是什么？`_mesh_worker` 放入结果后做了什么？）。
2. 为什么作者在 macOS 上可能没遇到？
3. 给出至少两种修复方法。

**Q11.** N = 3，三个 rank 的输入分别是 `[1, 2, 3]`、`[10, 20, 30]`、`[100, 200, 300]`（每块 1 个元素）。按本节 `ring_allreduce` 的下标规则，写出 reduce-scatter 两步和 allgather 两步之后每个 rank 的 `chunks`。

**Q12.** 用 α-β 模型比较 ring 与 tree allreduce：每一跳延迟 α = 5 µs，带宽 β = 10 GB/s，N = 8。按讲义表格，ring 为 `2(N−1)` 步、每 rank 发送 `2T(N−1)/N` 字节；tree 为 `2·log2 N` 步、发送 `T·log2 N` 字节。

1. 写出两者的耗时公式，求交叉点 T*。
2. 分别计算 T = 1 KB、1 MB、16 MB 时两者的耗时，哪种更快？

---

## 四、面试高频题

**Q13.**（基础必考）讲一下 ring allreduce 的过程。为什么说它是"带宽最优"的？它的缺点是什么？

**Q14.**（原理深挖）为什么说 allreduce = reduce_scatter + allgather？ZeRO / FSDP 为什么把这两半拆开用？与 DDP 相比，它们的通信量是多少？

**Q15.**（工程实践）PyTorch DDP 为什么要把梯度分桶（bucket）？怎么做到通信与计算重叠？bucket 大小怎么调？

**Q16.**（场景设计）2 台机器、每台 8 张 GPU，机内 NVLink，机间 100 Gbit 以太网。你会如何安排梯度 allreduce？如果某一台机器的网卡明显更慢会怎样？

**Q17.**（追问型）你写了一个自己的 allreduce，怎么证明它是对的？为什么本节和 gloo 对拍用的是 `max_abs_diff < 1e-5` 而不是字节相等？分布式测试里还要注意哪些坑？

---

## 五、参考答案与解析

### Q1 — 答案：D

`2T(N−1)/N = 2 × 256 × 3 / 4 = 384` 字节。代码中也是这么算的：`expected_per_rank_bytes = 2 * (world_size - 1) * (n // world_size) * 4 = 2 × 3 × 16 × 4 = 384`，实测输出 `measured=384 expected=384`。

- A（256）是 T 本身；
- B（512）是 `2T(N−1)/N` 在 N → ∞ 时的上限 `2T`；
- C（768）是 `2T(N−1)/N × 2`，或者把发送与接收都算上的量。

### Q2 — 答案：B

以 N = 2 为例：第 0 步 rank 0 发送块 0、接收块 `(0−0−1) mod 2 = 1`，并累加——所以 rank 0 最终持有块 1 的总和，即 `(r+1) mod N`。N = 3 的完整追踪见 Q11：reduce-scatter 后 rank 0 持有块 1（222）、rank 1 持有块 2（333）、rank 2 持有块 0（111）。

讲义写的是"After N−1 steps, rank r owns the full sum for chunk r"，与代码的下标约定**不一致**。代码作者在 `reduce_scatter` 的 docstring 里承认了这一点（"parks the full sum at index (r + 1) % W"），并通过把输入块整体旋转一位来满足 `torch.distributed` 的"rank r 拿块 r"契约。allgather 阶段第 0 步发送的 `(r − 0 + 1) mod N` 也正是这一块。

### Q3 — 答案：A

浮点加法不满足结合律：`(a+b)+c` 与 `a+(b+c)` 的舍入误差可能不同。ring 的块 k 按"沿环依次累加"的顺序求和，gloo 内部用的是另一种算法和顺序，最后一位可能不同，差值在 float32 的 ULP 量级（本次 4.77e-7）。

而在 ring 内部，每一块的最终和只由一个 rank 计算一次，allgather 阶段是**覆盖赋值**（`chunks[recv_idx] = incoming`），所以所有 rank 拿到的是同一份比特——这对 DDP 很重要：各副本的参数必须完全一致，否则会慢慢漂移。我们用线程模拟验证过：4 个 rank 的输出 `torch.equal` 全部为 True。

- B：队列传的是原始张量，不会损失精度；
- C：gloo 用的是输入张量的 dtype（float32）；
- D：要求与另一种求和顺序字节相等是不现实的。讲义说"diverges from gloo by more than float32 epsilon, the test fails"，但 float32 的 machine epsilon 约 1.19e-7，实测差值 4.77e-7 已经超过它；代码实际用的阈值是 `1e-5`。

### Q4 — 答案：C

每轮持有者集合翻倍：`{0}` → `{0,1}` → `{0,1,2,3}` → `{0..7}`，共 `log2 8 = 3` 轮。除 src 外每个 rank 恰好接收一次，所以总发送次数是 `N − 1 = 7`。

- A 是"src 逐个直发"的轮数（7 轮，每轮 1 次）；
- B 混淆了轮数与发送次数（只有 src 自己发了 3 次）；
- D 无依据。

注意：总流量仍是 `(N−1)·T`，树形结构减少的是**串行轮数**（延迟），不是字节数。

### Q5 — 答案：D

每个 rank 拿到全部 4 个分片拼接：`4 × 8 = 32` 个元素。环上转 `N − 1 = 3` 步，每步发送一个 8 元素分片（32 字节），共 96 字节。用讲义表格的写法：输出总大小 T = 128 字节，每 rank 发送 `T(N−1)/N = 96` 字节。

- A、C 错在输出长度：allgather 的输出是输入的 N 倍；
- B 把自己的分片也算进了发送量。

### Q6 — 答案：A

`import torch` 时，`torch.multiprocessing` 会向 `multiprocessing` 的 `ForkingPickler` 注册张量的 reducer：通过队列发送张量时，不是把字节塞进管道，而是把存储移到**共享内存**（`share_memory_()`，原地操作），只传一个句柄。如果直接把 `chunks[send_idx]` 放进队列，接收方拿到的和发送方本地的是同一块共享内存，之后发送方若对这块做原地修改，接收方就会看到变化。`clone()` 切断别名；`detach()` 去掉 autograd 历史；`contiguous()` 保证存储连续。

- B：本节全在 CPU；
- C：`clone()` 不改变 dtype；
- D：`numel() * element_size()` 对原张量同样能算对。

### Q7 — 答案：C

讲义："FSDP. Forward begins with allgather to unshard the layer, computes, then reduces with reduce_scatter and discards the unshard."

- A：DDP 对**分桶后的梯度做 allreduce**，不是逐参数 broadcast（broadcast 用于初始化时同步参数）；
- B：ZeRO 用 **reduce_scatter** 分片梯度、用 allgather 恢复参数；
- D：流水线并行在相邻 stage 之间点对点传激活（讲义说"Pipeline parallel needs broadcast for activations across stage groups"），不需要全局 allreduce。

### Q8 — 答案：B

总耗时 ≈ 步数 × α + 字节数 / β。ring 的步数 `2(N−1)` 随 N 线性增长，但字节数 `2T(N−1)/N` 几乎不变；tree 的步数只有 `2·log2 N`，但字节数更多。所以小消息时延迟项主导，tree 赢；大消息时带宽项主导，ring 赢。讲义："NCCL ships a topology detector that picks ring for messages above ~1 MB and tree below."

- A 说反了；C 错，两者的通信量不同；D 错，ring 对任意 N 都适用，二叉树才更偏好 2 的幂。

### Q9 — 参考答案

1. 追踪 N = 4、`src = 2`：
   - 第 0 轮：`has_value = {2}`，`partner = 2 + 1 = 3` → rank 2 发给 rank 3，`has_value = {2, 3}`；
   - 第 1 轮：`2 + 2 = 4 ≥ 4`，`3 + 2 = 5 ≥ 4`，没有新持有者；
   - 第 2 轮及以后：`partner` 更大，永远 `≥ w`。
   
   `has_value` 停在 `{2, 3}`，`while len(has_value) < w` 永不结束——**所有 rank 都在死循环里空转**（rank 0、1 连 `recv` 都没调用，所以 30 秒的 `RECV_TIMEOUT_S` 也救不了它）。我们用线程模拟验证：3 秒后 4 个线程全部仍在运行。根本原因是 `partner = h + 2^k` 只会"向上"扩展，只有 `src = 0` 时才能覆盖全部 rank。
2. `main()` 和 `test_broadcast_matches_gloo` 都只用 `src=0`；`gloo_reference` 里的 `dist.broadcast(tensor, src=0)` 也把 src 写死了，根本无法对拍其它 src。
3. 参考实现（已在 N = 2、3、4、5、8 的所有 src 上用线程模拟验证）：

```python
def broadcast(mesh, tensor, src):
    w, r = mesh.world_size, mesh.rank
    if w == 1:
        return tensor.clone()
    vr = (r - src) % w                       # 以 src 为 0 号的虚拟 rank
    out = tensor.clone() if r == src else torch.zeros_like(tensor)
    k = 1
    while k < w:
        if vr < k and vr + k < w:            # 本轮已持有 → 发给 vr + k
            mesh.send((vr + k + src) % w, out)
        elif k <= vr < 2 * k:                # 本轮接收者 ← 来自 vr - k
            out = mesh.recv((vr - k + src) % w)
        k <<= 1
    return out
```

顺带去掉了"每个 rank 都要模拟整张 `has_value` 表"的开销：每个 rank 只需根据自己的虚拟 rank 判断本轮是发、是收还是空闲。同时应让 `_gloo_worker` 接收 `src` 参数，补上 `src ≠ 0` 的对拍测试。

### Q10 — 参考答案

1. **原因**：`import torch` 会让 `torch.multiprocessing` 给 `multiprocessing` 的 pickler 注册张量 reducer。通过 `Queue` 发送 CPU 张量时，存储被移入共享内存，Linux 上默认的 sharing strategy 是 **`file_descriptor`**：队列里传的是一个"去发送方那里取文件描述符"的凭据，接收方 unpickle 时要通过 `resource_sharer` 的 Unix socket **连回发送进程**拿 fd。`_mesh_worker` 在 `out_queue.put((rank, result))` 之后就返回，fork 出的子进程随即退出，它的 resource sharer 也随之消失；父进程稍后 `get()` 时连接不到，于是 `FileNotFoundError`。ring 中某个 rank 最后一次发送的块如果在它退出之后才被下一个 rank 取走，也会出同样的问题，下游 rank 就会在 `recv` 上等满 30 秒抛 `_queue.Empty`。`_gloo_worker` 里的 `close()` + `join_thread()` 只保证把"凭据"写进管道，并不等待对方取走 fd，所以 gloo 参考路径同样会失败（单独调用 `gloo_reference` 得到 `EOFError`）。
2. macOS 上 PyTorch 的默认 strategy 是 `file_system`（共享内存以文件名标识，不需要发送进程存活）；代码里的 `lo0` 判断和 "TCP init through libuv has known issues on macOS" 注释也说明作者主要在 macOS 上开发。
3. 修复方法：
   - 在模块顶层（`import torch` 之后、任何子进程创建之前）调用 `torch.multiprocessing.set_sharing_strategy("file_system")`。spawn 出的 gloo 子进程会重新导入主模块，所以必须放在顶层而不是 `main()` 里。我们用一个只加这一行的包装脚本运行，demo 与 7 个测试全部通过。
   - 队列里不传 `torch.Tensor`，而是传 `tensor.numpy().tobytes()` 或 NumPy 数组，接收方再 `torch.frombuffer` 还原——这样走的是普通 pickle，真正"按字节"通过管道，也更符合"wire pattern"的本意。
   - 让子进程在发送完结果后等待父进程确认（例如再等一个 `Event` 或 barrier）才退出。

### Q11 — 参考答案

记 `chunks[r] = [块0, 块1, 块2]`。

| 阶段 | rank 0 | rank 1 | rank 2 | 本步发送（发送方 → 块号） |
|------|--------|--------|--------|------------------------|
| 初始 | `[1, 2, 3]` | `[10, 20, 30]` | `[100, 200, 300]` | — |
| RS 第 0 步 | `[1, 2, 303]` | `[11, 20, 30]` | `[100, 220, 300]` | r0→块0，r1→块1，r2→块2 |
| RS 第 1 步 | `[1, 222, 303]` | `[11, 20, 333]` | `[111, 220, 300]` | r0→块2，r1→块0，r2→块1 |
| AG 第 0 步 | `[111, 222, 303]` | `[11, 222, 333]` | `[111, 220, 333]` | r0→块1，r1→块2，r2→块0 |
| AG 第 1 步 | `[111, 222, 333]` | `[111, 222, 333]` | `[111, 222, 333]` | r0→块0，r1→块1，r2→块2 |

（已用脚本按代码的下标公式逐步验证。）reduce-scatter 结束时 rank 0、1、2 分别持有块 1、2、0 的总和，即 `(r+1) mod 3`（对应 Q2）。每个 rank 共发送 4 次、每次 1 个元素，即 `2(N−1)` 块、`2T(N−1)/N` 字节。

### Q12 — 参考答案

1. 公式：
   - `t_ring = 2(N−1)·α + 2(N−1)/N · T/β = 14α + 1.75·T/β`
   - `t_tree = 2·log2 N·α + log2 N · T/β = 6α + 3·T/β`
   
   令两者相等：`8α = 1.25·T/β` → `T* = 6.4·α·β = 6.4 × 5e-6 × 1e10 = 320,000 字节 ≈ 320 KB`。
2. 计算（单位 µs，已用 Python 计算）：

| T | ring | tree | 更快 |
|---|------|------|------|
| 1 KB | 70.2 | 30.3 | tree |
| 1 MB | 245 | 330 | ring |
| 16 MB | 2,870 | 4,830 | ring |

交叉点在几百 KB 量级，与讲义"约 1 MB"的经验值同一数量级；具体位置取决于 α、β 和 N。这正是讲义练习 1、5 要求实测的内容。注意讲义表格中 tree 的 `T·log2 N` 是简化模型；真实 NCCL 的 tree 使用流水线化的双二叉树，带宽项会好得多。

### Q13 — 参考回答要点

- **过程**：把张量切成 N 块；第一阶段 reduce-scatter，N−1 步，每步每个 rank 把一块发给下一个 rank、从上一个 rank 收一块并累加，结束时每个 rank 持有一块的完整总和；第二阶段 allgather，再走 N−1 步，把完成的块沿环传一圈并覆盖，结束时所有 rank 拿到完整结果。
- **带宽最优**：每个 rank 发送 `2T(N−1)/N`，可以证明任何 allreduce 算法每个 rank 至少要发送和接收约 `2T(N−1)/N`（每个元素既要把自己的贡献送出去，又要拿回最终结果）；而且所有链路同时满载，没有 root 瓶颈。
- **缺点**：步数 `2(N−1)` 随 N 线性增长，延迟项大；小消息、超大集群时不划算；环上最慢的一条链路决定整体速度（讲义："the slowest GPU dictates step time"）；对拓扑敏感（跨机链路应尽量少出现在环上）。
- 加分点：说出 NCCL 的 tree / ring 自动选择，或分层（hierarchical）allreduce。

### Q14 — 参考回答要点

- **分解**：reduce_scatter 之后每个 rank 有总和的 1/N；再 allgather 一次，人人得到完整总和。本节代码中 `reduce_scatter` 就是 `ring_allreduce` 的前半段（加了一次块旋转）。两段各 `T(N−1)/N`，合计 `2T(N−1)/N`。
- **ZeRO**：每个 rank 只负责 1/N 参数的优化器状态。梯度做 reduce_scatter 后，每个 rank 正好拿到自己负责那 1/N 的梯度总和，更新自己的分片参数，再 allgather 回完整参数。通信量与 DDP 的 allreduce 相同（`2T(N−1)/N`），但优化器状态内存降到 1/N（详见第 78 节）。
- **FSDP（ZeRO-3）**：参数本身也分片；每层前向前 allgather 参数、用完即丢，反向时再 allgather 一次，梯度 reduce_scatter。通信量约为 DDP 的 1.5 倍（两次 allgather + 一次 reduce_scatter），换来参数、梯度、优化器状态全部分片。
- 常见误区：以为 ZeRO 必然增加通信——ZeRO-1/2 的通信量与 DDP 相同。

### Q15 — 参考回答要点

- **为什么分桶**：模型有成千上万个梯度张量，逐个 allreduce 每次都要付一次延迟 α；把小张量合并到约 25 MB 的桶里，一个桶一次 allreduce（讲义："DDP buckets gradients into ~25 MB chunks"）。
- **重叠**：反向传播按层倒序产生梯度；一个桶的梯度全部就绪，就通过 hook 立即异步发起它的 allreduce，同时继续计算前面层的梯度。讲义："The overlap halves visible communication time when the network has slack."
- **桶大小**：太小 → 延迟开销大、调用次数多；太大 → 第一个桶要等很久才能发出，重叠变少，最后一个桶的通信暴露在关键路径上。DDP 默认 25 MB（`bucket_cap_mb`），可按网络带宽和模型结构调整，并用 profiler 观察通信是否被计算掩盖。
- 加分点：DDP 的桶顺序按参数注册的逆序近似反向顺序；`find_unused_parameters`、梯度累积时用 `no_sync()` 跳过中间步的同步。

### Q16 — 参考回答要点

- **分层 allreduce**：机内 8 卡先通过 NVLink 做 reduce-scatter（每卡得到 1/8）；机间对应的卡（两台机器的第 i 张卡）只交换各自的 1/8 做 allreduce；机内再 allgather。机间流量从完整 T 降到 T/8 级别，慢链路只承载必须跨机的部分。
- **拓扑感知**：NCCL 会自动探测 NVLink/PCIe/网卡拓扑并构造环或树；平环（16 卡一个大环）会让慢的机间链路出现在环上多次。
- **慢网卡**：ring 是同步的，每一步都要等最慢的那条链路，整个集群的 step time 被拉到最慢链路的水平；表现为所有 GPU 利用率下降。处理：排查硬件、调整通信与计算重叠、增大梯度累积步数以降低通信频率，或者用压缩/低精度梯度通信。
- 加分点：说出机间带宽（100 Gbit ≈ 12.5 GB/s）远低于 NVLink（数百 GB/s）这一量级差。

### Q17 — 参考回答要点

- **证明正确**：对拍参考实现（本节用 `torch.distributed` gloo，同输入、同 world size）；覆盖不同 N（含 2、奇数、非 2 的幂）、不能整除的长度（测试填充逻辑）、不同 dtype、不同 src；检查所有 rank 结果一致；检查通信量公式（本节的字节计数测试）。
- **为什么不字节相等**：浮点加法不满足结合律，不同算法求和顺序不同（本节实测 4.77e-7）；正确的判据是 `allclose`，容差与 dtype、规模相关。若要求字节相等，必须规定相同的归约顺序（确定性算法）。
- **常见坑**：
  - **死锁**：所有 rank 都先 `recv` 再 `send` 会互相等待；本节用"先 send 后 recv"+ 无界队列避免。
  - **挂起**：一个 rank 崩溃，其他 rank 永远等待——需要接收超时（本节已有 `RECV_TIMEOUT_S = 30`）和失败传播。
  - **测试覆盖不全**：本节只测 `src=0`，漏掉了 Q9 的死循环。
  - **平台差异**：Linux 与 macOS 的张量共享策略不同（Q10）；fork 与 spawn 的语义不同。
  - **资源泄漏**：子进程、队列、临时 rendezvous 文件要在 `finally` 中清理。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 05 扩展：分布式训练、FSDP、DeepSpeed](../../../10-llms-from-scratch/05-scaling-distributed/docs/zh.md)：数据并行、ZeRO、FSDP 的整体背景。
- [阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../48-distributed-fsdp-ddp/docs/zh.md)：Track C 中第一次接触 DDP/FSDP。
- [阶段 19 · 46 Gradient Accumulation](../../46-gradient-accumulation/docs/zh.md)：理解"梯度求和"在单卡与多卡上的等价性。
- [阶段 03 · 11 PyTorch 简介](../../../03-deep-learning-core/11-intro-to-pytorch/docs/zh.md)：张量、`clone`、`contiguous` 等基础 API。

### 本节被哪些后续内容用到
- [阶段 19 · 77 从零实现数据并行 DDP](../../77-data-parallel-ddp/docs/zh.md)：用 allreduce 同步梯度。
- [阶段 19 · 78 ZeRO Optimizer 状态分片](../../78-zero-parameter-sharding/docs/zh.md)：用 reduce_scatter + allgather 实现 ZeRO。
- [阶段 19 · 79 流水线并行与流水线气泡分析](../../79-pipeline-parallel/docs/zh.md)：stage 之间的点对点通信。
- [阶段 19 · 80 分片 Checkpoint 与原子恢复](../../80-checkpoint-sharded-resume/docs/zh.md)：分片状态的保存与恢复。
- [阶段 19 · 81 端到端分布式训练](../../81-end-to-end-distributed-train/docs/zh.md)：把四个原语组合成完整训练。
- [阶段 10 · 19 DualPipe 并行](../../../10-llms-from-scratch/19-dualpipe-parallelism/docs/zh.md)：通信与计算重叠的高级形式。

### 延伸关键词
`NCCL` · `gloo` · `ring allreduce` · `double binary tree` · `hierarchical allreduce` · `α-β 模型` · `bucket_cap_mb` · `torch.multiprocessing sharing strategy` · `reduce_scatter_tensor / all_gather_into_tensor` · `Horovod` · `NVLink / InfiniBand`
