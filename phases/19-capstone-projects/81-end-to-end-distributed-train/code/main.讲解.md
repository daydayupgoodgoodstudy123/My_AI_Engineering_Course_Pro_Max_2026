# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 81 节 端到端分布式训练 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下；测试：在小节根目录运行 `python3 -m pytest -q tests`）｜ **依赖**：`torch`（第三方，CPU 版即可，使用 `torch.distributed` 的 gloo 后端）；标准库 `multiprocessing`、`hashlib`、`json`、`tempfile`、`shutil`、`dataclasses`、`pathlib`。无需 GPU、无需网络（走本机回环网卡）。
>
> **注意**：在 Linux 上直接运行会在回传结果时崩溃（`EOFError` / `ConnectionResetError`），原因与绕过办法见 3.9 节和第 6 节。

---

## 1. 这份代码在考察什么

这是 76–80 节分布式训练轨道的收官：在一台 CPU 机器上起 4 个进程，把前面各节的零件装成一个真实的训练循环。

1. **进程组与 rendezvous**（76 节）：`mp.get_context("spawn")` 起 4 个进程，gloo 后端 + 文件 rendezvous 组成进程组。
2. **DDP 形状的初始化同步**（77 节）：每个参数从 rank 0 `broadcast`。
3. **ZeRO-1 优化器**（78 节）：扁平化梯度 → `reduce_scatter` → 分片 Adam → `all_gather` 写回。
4. **中途分片 checkpoint**（80 节）：第 10 步把每个 rank 的状态收集起来，写 4 个分片 + manifest（带 sha256、原子 rename）。
5. **一个真正的 Transformer**：2 层 pre-norm、因果多头注意力、GELU MLP、独立的 LM head，交叉熵 loss——比 77 节的 MLP 多了 LayerNorm、embedding、softmax 这些"接线点"。
6. **端到端不变量**：loss 有限、各 rank 参数范数一致、每 rank 优化器内存等于 `12P/N`、checkpoint 回读逐字节一致。

> 一句话：**每个零件单独都对，不代表拼起来也对**；这份代码的价值在于让你看清"拼"的每一处接口。顺带它自己也提供了一个反例：在 Linux 上它恰恰坏在"组件之间的结果回传"这一环。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 顶部常量 | 常量 | `SEED=41`、`WORLD_SIZE=4`、`STEPS=20`、`CHECKPOINT_STEP=10`、`BATCH=4`、`SEQ_LEN=16`、`VOCAB=64`、`EMBED_DIM=32`、`NUM_HEADS=4`、`NUM_LAYERS=2`、`LR=5e-3` | 实验配置 |
| `_loopback_iface` | 函数 | macOS 用 `lo0`，其它用 `lo` | gloo 网卡选择 |
| `CausalSelfAttention` | `nn.Module` | 合并的 qkv 投影、拆头、缩放点积 + 因果 mask、合头、输出投影 | 多头因果注意力 |
| `TransformerBlock` | `nn.Module` | pre-norm：`x + attn(ln1(x))`、`x + mlp(ln2(x))` | Transformer block |
| `MiniGPT` | `nn.Module` | token/位置 embedding → 2 个 block → `ln_f` → LM head | 语言模型 |
| `flat_param_numel` / `gather_flat_params` / `scatter_flat_to_params` / `gather_flat_grads` | 函数 | 参数与梯度在"模块"与"扁平向量"之间互转 | ZeRO 的扁平化 |
| `ZeroOptimizer` | 类 | 分片 Adam：`step`、`zero_grad`、`state_dict`、`load_state_dict`、`shard_bytes` | ZeRO-1 |
| `ShardEntry` / `save_sharded` / `load_sharded` | dataclass / 函数 | 80 节的精简版：分片文件 + manifest + sha256 + 原子 rename | 分片 checkpoint |
| `make_corpus` | 函数 | 固定种子生成均匀随机 token | 合成数据 |
| `init_distributed` | 函数 | 设置 `GLOO_SOCKET_IFNAME`，`init_process_group(gloo, file://...)` | rendezvous |
| `_gather_payloads_to_rank0` | 函数 | 两次 `all_gather` 交换变长字节串 | checkpoint 收集 |
| `_train_worker` | 函数 | 每个进程的主体：初始化 → 20 步训练 → 第 10 步 checkpoint → 回传结果 | 训练循环 |
| `run_e2e` | 函数 | 起 4 个进程、收集结果、清理 | 编排 |
| `verify_resume` | 函数 | 重新加载 checkpoint，比较 master 分片与快照 | 恢复合同 |
| `main` | 函数 | 打印参数量、loss 表、范数、内存、验证结果 | 端到端 demo |

数据流：`main` → `run_e2e` 起 4 个 `_train_worker` → 每个 worker：`init_distributed` → `MiniGPT` + `broadcast` → `ZeroOptimizer` → 20 次 {取本 rank 的数据块 → forward → `cross_entropy` → backward → `optim.step()`（reduce_scatter → Adam → all_gather）}，第 10 步后 {序列化 → `_gather_payloads_to_rank0` → rank 0 `save_sharded`} → 结果放入队列 → `os._exit(0)` → 主进程收集 → 打印 → `verify_resume` → 删除工作目录。

---

## 3. 逐段精讲

### 3.1 因果自注意力

```python
        self.qkv = nn.Linear(embed_dim, 3 * embed_dim, bias=False)
        self.proj = nn.Linear(embed_dim, embed_dim, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, t, e = x.shape
        qkv = self.qkv(x).reshape(b, t, 3, self.num_heads, self.head_dim)
        q, k, v = qkv.unbind(dim=2)
        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)
        attn = (q @ k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        mask = torch.triu(torch.ones(t, t), diagonal=1).bool()
        attn = attn.masked_fill(mask, float("-inf"))
        attn = attn.softmax(dim=-1)
        out = attn @ v
        out = out.transpose(1, 2).reshape(b, t, e)
        return self.proj(out)
```

形状追踪（每 rank `b=4, t=16, e=32`，4 头、`head_dim=8`）：

| 步骤 | 形状 |
|------|------|
| `self.qkv(x)` | `(4, 16, 96)`：一个合并矩阵同时算 Q、K、V |
| `.reshape(b, t, 3, 4, 8)` | 把 96 拆成"3 份 × 4 头 × 8 维" |
| `unbind(dim=2)` | 得到 q、k、v，各 `(4, 16, 4, 8)` |
| `.transpose(1, 2)` | `(4, 4, 16, 8)`：头维提前 |
| `q @ kᵀ / √8` | `(4, 4, 16, 16)` |
| `masked_fill(mask, -inf)` | mask `(16, 16)` 广播到每个样本、每个头 |
| `attn @ v` | `(4, 4, 16, 8)` |
| `.transpose(1, 2).reshape(b, t, e)` | `(4, 16, 32)` 合头 |

- `torch.triu(..., diagonal=1)` 取主对角线以上为 True，即"未来位置"；`masked_fill` 把它们设为 `-inf`，softmax 后为 0。因为对角线永远不被屏蔽，每一行至少有一个有限值，不会出现整行 `-inf` 导致 NaN。
- `transpose` 之后的张量不连续，这里用的是 `reshape`（必要时自动拷贝），如果写成 `view` 就会报错。
- mask 每次 forward 都重新创建；生产中会注册为 buffer 或直接用 `F.scaled_dot_product_attention(q, k, v, is_causal=True)`。
- `nn.Linear` 的权重形状是 `(out, in)`：`qkv.weight` 为 `(96, 32)`。

### 3.2 Block 与 MiniGPT

```python
class TransformerBlock(nn.Module):
    ...
        self.mlp = nn.Sequential(
            nn.Linear(embed_dim, 4 * embed_dim),
            nn.GELU(),
            nn.Linear(4 * embed_dim, embed_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x
```

```python
    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        b, t = ids.shape
        pos = torch.arange(t, device=ids.device)
        x = self.tok_embed(ids) + self.pos_embed(pos)
        for blk in self.blocks:
            x = blk(x)
        x = self.ln_f(x)
        return self.head(x)
```

- 标准 pre-norm GPT：每个子层前做 LayerNorm，残差主干保持干净，最后一个 `ln_f`。
- `self.head` 是独立的 `nn.Linear(32, 64, bias=False)`，没有与 `tok_embed` 共享权重（讲义："untied for clarity"）；共享的话参数会少 2,048 个。
- `nn.ModuleList` 让两个 block 的参数被 `model.parameters()` 正确收集——如果用普通 Python list，参数不会被注册，既不会被 broadcast 也不会被优化。
- **参数量 29,824**（实际打印）：token 2,048 + 位置 512 + 每 block 12,576 × 2 + `ln_f` 64 + head 2,048。`model.parameters()` 的遍历顺序是固定的（按模块注册顺序），这一点对下面的扁平化至关重要。讲义称"A few thousand parameters"，实际约 3 万。

### 3.3 扁平化工具：模块 ↔ 一维向量

```python
def gather_flat_params(module: nn.Module) -> torch.Tensor:
    return torch.cat([p.detach().to(torch.float32).flatten() for p in module.parameters()])


def scatter_flat_to_params(module: nn.Module, flat: torch.Tensor) -> None:
    offset = 0
    for p in module.parameters():
        n = p.numel()
        p.data.copy_(flat[offset:offset + n].reshape(p.shape).to(p.dtype))
        offset += n


def gather_flat_grads(module: nn.Module) -> torch.Tensor:
    parts = []
    for p in module.parameters():
        if p.grad is None:
            parts.append(torch.zeros_like(p.data, dtype=torch.float32).flatten())
        else:
            parts.append(p.grad.detach().to(torch.float32).flatten())
    return torch.cat(parts)
```

- ZeRO 的分片是在**扁平参数空间**上切的：把所有参数按固定顺序拼成一个长度 29,824 的向量，再平均切 N 份。分片边界可能落在某个权重矩阵的中间，这没关系，因为 Adam 是逐元素的。
- 三个函数都依赖 `module.parameters()` 的顺序在所有 rank 上一致——同一份代码构造的模型自然满足。
- `p.grad is None` 时补零：某个参数在本步没有参与计算（本模型中不会发生，但这是通用写法），也必须占位，否则后面的偏移会全部错位。
- `.to(torch.float32)` 为混合精度预留：若模型是 fp16/bf16，这里会把梯度提升到 fp32 再参与归约与 Adam；`scatter_flat_to_params` 再转回模型的 dtype。本节模型就是 fp32，这些转换不改变数值。
- `p.data.copy_(...)` 绕过 autograd 原地写入参数。

### 3.4 `ZeroOptimizer.__init__`：切分与补零

```python
        total = flat_param_numel(module)
        self.total = total
        pad = (-total) % world_size
        self.chunk = (total + pad) // world_size
        full = gather_flat_params(module)
        padded = torch.zeros(self.chunk * world_size, dtype=torch.float32)
        padded[:total] = full
        self.master_shard = padded[rank * self.chunk:(rank + 1) * self.chunk].clone()
        self.m_shard = torch.zeros_like(self.master_shard)
        self.v_shard = torch.zeros_like(self.master_shard)
```

- `(-total) % world_size` 是"补到 N 的倍数需要几个零"的惯用写法：29,824 能被 4 整除，pad = 0，chunk = 7,456；如果 total = 29,825，pad 就是 3。
- 每个 rank 只保留自己那一段的 fp32 主参数和 Adam 的 m、v：`3 × 7,456 × 4 B = 89,472 B`，这就是 `shard_bytes()` 的返回值，也就是讲义的 `12P/N`。
- `.clone()` 很关键：切片是原张量的**视图**，不 clone 的话 `master_shard` 会与临时的 `padded` 共享内存。
- ⚠️ 本节模型全是 fp32，模型参数本身就是 fp32 全量副本，`master_shard` 与对应的参数段逐位相同，是冗余的。它的意义在于模拟混合精度：那时模型参数是 fp16，必须另存 fp32 主参数，才有"12 字节/参数"的账。

### 3.5 `ZeroOptimizer.step`：一次 ZeRO-1 更新

```python
    def step(self) -> None:
        flat_grad = gather_flat_grads(self.module)
        pad = (-self.total) % self.world_size
        padded = torch.zeros(self.total + pad, dtype=torch.float32)
        padded[:self.total] = flat_grad
        chunks = [c.contiguous() for c in padded.chunk(self.world_size)]
        local_grad = torch.zeros_like(chunks[0])
        dist.reduce_scatter(local_grad, chunks, op=dist.ReduceOp.SUM)
        local_grad.div_(self.world_size)
```

- 每个 rank 把**完整**的本地梯度切成 N 块；`reduce_scatter` 的语义是："第 i 块在所有 rank 上求和，结果只交给 rank i"。于是每个 rank 拿到自己分片对应的**全局梯度之和**，除以 N 得平均。
- 这一步替代了 DDP 的 all-reduce：all-reduce = reduce-scatter + all-gather，而 ZeRO-1 在两步之间插入了"只更新自己的分片"。
- `.contiguous()`：`chunk` 返回的是视图，集合通信要求连续内存。

```python
        self.step_count += 1
        self.m_shard.mul_(self.beta1).add_(local_grad, alpha=1 - self.beta1)
        self.v_shard.mul_(self.beta2).addcmul_(local_grad, local_grad, value=1 - self.beta2)
        bc1 = 1 - self.beta1 ** self.step_count
        bc2 = 1 - self.beta2 ** self.step_count
        m_hat = self.m_shard / bc1
        v_hat = self.v_shard / bc2
        self.master_shard.addcdiv_(m_hat, v_hat.sqrt().add_(self.eps), value=-self.lr)
```

标准 Adam（与 `torch.optim.Adam` 默认行为一致）：

- `m ← β1·m + (1−β1)·g`；`v ← β2·v + (1−β2)·g²`（`addcmul_` 计算 `v + value·g·g`）；
- 偏差校正 `m̂ = m / (1−β1^t)`、`v̂ = v / (1−β2^t)`；
- `θ ← θ − lr · m̂ / (√v̂ + ε)`（`addcdiv_` 计算 `θ + value·m̂/(√v̂+ε)`）。
- 全部是**逐元素**运算，所以在 1/N 分片上算与在整个向量上算结果相同——这是 ZeRO 能分片优化器状态的数学基础。
- 带下划线的方法（`mul_`、`add_`、`addcmul_`、`addcdiv_`）原地修改，不分配新内存。
- 没有 weight decay、没有梯度裁剪、没有学习率 warmup。

```python
        gathered = [torch.zeros_like(self.master_shard) for _ in range(self.world_size)]
        dist.all_gather(gathered, self.master_shard)
        flat_full = torch.cat(gathered)[:self.total]
        scatter_flat_to_params(self.module, flat_full)
```

- `all_gather` 把每个 rank 更新后的主参数分片收集到所有 rank，拼回完整向量，`[:self.total]` 去掉补零，再写回模型。
- 所有 rank 写回的是**同一个**向量，所以各 rank 参数逐位相同——这就是运行结果中范数漂移为 `0.00e+00` 的原因。
- 我们用单进程 `torch.optim.Adam` 在 batch = 16（4 个 rank 的数据拼接）上训练 20 步作为基线：最终参数范数 `54.51317`，与分布式结果一致；rank 0 那段数据上的 20 个 loss 也逐个相同（6 位小数）。这证明了"DDP + ZeRO-1"在数学上等价于单卡大 batch 训练。

### 3.6 `zero_grad` 与 `state_dict`

```python
    def zero_grad(self) -> None:
        for p in self.module.parameters():
            if p.grad is not None:
                p.grad.detach_()
                p.grad.zero_()
```

- 与 `torch.optim.Optimizer.zero_grad(set_to_none=False)` 的旧行为相同：把梯度原地清零（PyTorch 新版本默认改成设为 `None` 以省内存）。`detach_()` 断开梯度张量自身可能带有的计算图。

`state_dict` / `load_state_dict` 保存/恢复 `master_shard`、`m_shard`、`v_shard` 和 `step_count`。`step_count` 必须恢复，否则偏差校正会被重置（测验 Q12 实测：置 0 后最终 loss 4.371615 ≠ 4.364540）。`load_state_dict` 用 `copy_` 原地写入，要求形状一致——也就是要求相同的 world size。

### 3.7 精简版分片 checkpoint

```python
@dataclass
class ShardEntry:
    rank: int
    path: str
    sha256: str
```

`save_sharded` 与 80 节同样走"写 tmp → fsync → 全部 rename → 最后 rename manifest"。与 80 节相比的差异：

| 方面 | 80 节 | 本节 |
|------|-------|------|
| manifest 字段 | world_size、step、wall_clock、schema_version、每分片 offset/numel | 只有 world_size、step、每分片 rank/path/sha256 |
| fsync 目录 | 有 `_fsync_dir` | 无 |
| 加载校验 | schema、分片数、rank 范围、重复、路径穿越、存在性、sha256 | 只有 world_size 与 sha256 |
| 异常类型 | `CheckpointError` | `RuntimeError` |

本节的 `load_sharded` 若遇到缺失的分片会直接抛 `FileNotFoundError`，manifest 不存在时也是如此——不是"大声的、带语义的"失败。作为 capstone，更好的做法是直接 `import` 80 节的模块，而不是复制一份简化版。

### 3.8 数据与进程组

```python
def make_corpus(seed: int, total_tokens: int) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    return torch.randint(0, VOCAB, (total_tokens,), generator=g)
```

- 用独立的 `torch.Generator`，不影响全局随机状态；种子相同则每个 rank 生成完全相同的语料。
- ⚠️ 均匀随机 token：下一个 token 与上下文无关，理论最优 loss 是 `ln 64 ≈ 4.159`，模型学不到任何东西。讲义的不变量 (a)"loss 单调下降"因此不可能成立（见第 6 节）。

```python
def init_distributed(rank: int, world_size: int, init_file: str, iface: str) -> None:
    os.environ["GLOO_SOCKET_IFNAME"] = iface
    dist.init_process_group(
        backend="gloo", init_method=f"file://{init_file}",
        rank=rank, world_size=world_size,
    )
```

- **文件 rendezvous**：所有进程通过同一个共享文件交换地址信息，不需要 `MASTER_ADDR/MASTER_PORT`，适合单机演示。
- `GLOO_SOCKET_IFNAME` 指定 gloo 使用回环网卡，避免它去选一个不可达的外部网卡。

### 3.9 训练 worker

```python
    init_distributed(rank, world_size, init_file, iface)
    torch.manual_seed(SEED)
    model = MiniGPT()
    for p in model.parameters():
        dist.broadcast(p.data, src=0)
    optim = ZeroOptimizer(model, world_size=world_size, rank=rank, lr=LR)
```

- 所有 rank 用相同种子，初始化本就相同；`broadcast` 是"以 rank 0 为准"的保险——真实 DDP 也会在构造时这样做，因为各 rank 的随机状态不一定一致。
- **顺序很重要**：必须先 broadcast，再构造 `ZeroOptimizer`（它在构造时从模型拷贝主参数分片）。

```python
    for step in range(steps):
        offset = step * world_size * BATCH * (SEQ_LEN + 1) + rank * BATCH * (SEQ_LEN + 1)
        block = corpus[offset:offset + BATCH * (SEQ_LEN + 1)].reshape(BATCH, SEQ_LEN + 1)
        x = block[:, :-1]
        y = block[:, 1:]
        optim.zero_grad()
        logits = model(x)
        loss = F.cross_entropy(logits.reshape(-1, VOCAB), y.reshape(-1))
        loss.backward()
        optim.step()
```

- **数据分片**：每步取 `4 rank × 4 条 × 17 token = 272` 个 token，rank r 取其中第 r 段 68 个，reshape 成 `(4, 17)`。语料总长 `4 × 4 × 17 × 20 = 5,440`，每个 token 只用一次，各 rank 数据不重叠。
- `x = block[:, :-1]`、`y = block[:, 1:]`：输入与目标错开一位，即 next-token prediction。
- `F.cross_entropy` 需要 `(N, C)` 的 logits 和 `(N,)` 的目标，所以把 `(4, 16, 64)` 展平成 `(64, 64)`。
- 只有 rank 0 记录 loss，而且记录的是 rank 0 **本地** batch 的 loss，不是全局平均 loss。

```python
        if step + 1 == CHECKPOINT_STEP:
            state = {
                "model_state": {k: v.clone() for k, v in model.state_dict().items()},
                "optim_state": optim.state_dict(),
                "rank": rank,
            }
            master_at_ckpt = optim.master_shard.clone()
            dist.barrier()
            payloads = _gather_payloads_to_rank0(_serialize(state), world_size)
            if rank == 0:
                all_states = [_deserialize(p) for p in payloads]
                save_sharded(all_states, ckpt_dir, step=CHECKPOINT_STEP)
            dist.barrier()
```

- 第 10 次更新之后（`step` 从 0 开始，`step + 1 == 10`）保存。
- 每个 rank 的状态里都有**完整**的 `model_state`（参数是复制的，4 份完全相同）加自己的 `optim_state`。
- 两个 `barrier`：第一个确保所有 rank 都到达同一步；第二个确保 rank 0 写完之前，其它 rank 不会继续往下跑。
- ⚠️ **这是 gather-then-write**：`_gather_payloads_to_rank0` 用两次 `all_gather`（先交换长度，再交换补零后的字节），每个 rank 都收到了全部 payload，然后只由 rank 0 写 4 个文件。80 节讲义花了整节论证这种模式在大规模下不可行；讲义的组合规则表也坦白写着"Called on rank 0 with state collected via allgather"。按 80 节的思路，应该是每个 rank 直接 `save` 自己的分片，只把 sha256 这类小元数据 gather 到 rank 0 写 manifest。
- `_gather_payloads_to_rank0` 里的 `bytes(gathered[r][:n].tolist())` 先把张量转成 Python 整数列表再转字节，对大 payload 很慢；`gathered[r][:n].numpy().tobytes()` 更高效。PyTorch 也提供现成的 `dist.all_gather_object` / `dist.gather_object`。

```python
    param_norm = sum(p.detach().pow(2).sum().item() for p in model.parameters()) ** 0.5
    out_queue.put((rank, rank0_losses if rank == 0 else [], param_norm, optim.shard_bytes(),
                   master_at_ckpt))
    out_queue.close()
    out_queue.join_thread()
    os._exit(0)
```

- 参数范数 = 所有参数平方和的平方根，用来廉价地检查"各 rank 参数是否一致"（更严格的做法是比较参数的哈希）。
- ⚠️ **Linux 上的崩溃点**：`master_at_ckpt` 是 torch 张量。`import torch` 会给 `multiprocessing` 注册张量的序列化方式：张量被移到共享内存，通过**文件描述符**传给接收方，接收方反序列化时要连接发送方进程取回 fd。Linux 默认共享策略是 `file_descriptor`；worker 放完数据立即 `os._exit(0)`，主进程反序列化时发送方已退出，于是 `EOFError` 或 `ConnectionResetError`。我们直接运行 3 次全部失败，`pytest` 6 个用例全部失败。macOS 上只支持 `file_system` 策略（按文件名共享，不需要发送方在线），结合代码专门处理了 Darwin 的 `lo0`，可以推断作者是在 macOS 上验证的（推断）。
- 修复：回传 `master_at_ckpt.numpy()` 或字节串；或在 worker 里先 `torch.multiprocessing.set_sharing_strategy("file_system")`；或让 worker 等主进程确认后再退出（测验 Q9）。
- `os._exit(0)` 的用意是让进程立即退出，避开进程组析构可能的卡住（代码没有调用 `destroy_process_group`）；`close()` + `join_thread()` 保证队列数据已写入管道。

### 3.10 编排：`run_e2e`

```python
    ctx = mp.get_context("spawn")
    out_queue = ctx.Queue()
    workdir = tempfile.mkdtemp(prefix="aie_e2e_")
    ...
            for r in range(world_size):
                p = ctx.Process(
                    target=_train_worker,
                    args=(r, world_size, init_file, iface, ckpt_dir, steps, out_queue),
                )
                p.start()
                procs.append(p)
            results = {}
            for _ in range(world_size):
                rank, losses, norm, shard_bytes, master_at_ckpt = out_queue.get(timeout=180)
                results[rank] = {...}
        except Exception:
            cleanup_workdir = True
            raise
    finally:
        for p in procs:
            p.join(timeout=5)
            if p.is_alive():
                p.terminate()
                p.join(timeout=2)
        if cleanup_workdir:
            shutil.rmtree(workdir, ignore_errors=True)
```

- **spawn** 上下文：每个子进程是全新的 Python 解释器，重新 import 本模块（所以 `if __name__ == "__main__"` 保护是必需的），而不是 fork 父进程——fork 与已初始化的线程/通信库混用容易出问题。
- `out_queue.get(timeout=180)`：每次最多等 180 秒，这就是讲义"self-terminating"的保险——任一 worker 死锁，主进程超时抛异常而不是永远挂起。
- 结果按 `rank` 存入字典，因为 4 个 worker 放入队列的先后顺序不确定。
- 嵌套的 `try/except/finally`：异常时设置清理标志并重新抛出；无论成功失败都 `join`，超时仍活着的进程 `terminate`。成功时工作目录保留给 `verify_resume` 使用，由 `main`（或测试的 `tearDown`）负责删除。

### 3.11 `verify_resume` 与 `main`

```python
    loaded = load_sharded(ckpt_dir, expected_world_size=expected_world_size)
    for r in range(expected_world_size):
        saved = loaded[r]["optim_state"]["master_shard"]
        snapshot = expected_master_shards[r]
        if not torch.equal(saved, snapshot):
            return False
    return True
```

- 比较的是"磁盘上的 master 分片"与"worker 当时内存中的快照"。它验证了序列化 → all_gather → 写盘 → sha256 校验 → 反序列化这条链路无损，但**没有**比较 m、v、`model_state`，也没有真正恢复训练（讲义练习 3）。

`main` 打印参数量、loss 表、各 rank 范数及漂移、各 rank 的 `shard_bytes` 与期望值 `(P + pad)/N × 4 × 3`，最后调用 `verify_resume`。注意 `main` 中 `MiniGPT()` 只是为了数参数，用的是主进程当时的随机状态，不影响训练。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| CPU + gloo + 文件 rendezvous | 单机即可运行，无需 GPU/网络配置 | 生产用 NCCL + `torchrun`（TCP/etcd rendezvous） |
| `mp.spawn` 风格起进程 | 每个 rank 是独立解释器，行为接近真实多机 | 启动开销大（实测一次运行约 39 秒，主要花在 4 个进程各自 import torch 与建组上） |
| 手写 ZeRO-1 而非 `ZeroRedundancyOptimizer` | 每一次集合通信都可见 | 无 bucket、无通信/计算重叠、无梯度裁剪 |
| 在扁平空间上切分并补零 | 切分简单、负载均衡 | 分片边界穿过参数矩阵；需要固定的参数顺序 |
| 保留 fp32 `master_shard` | 模拟混合精度的主参数 | 在全 fp32 模型中是冗余的 |
| 均匀随机语料 | 确定性、无需数据文件 | 没有可学信号，loss 不会下降；验证"学会了"需要有结构的数据 |
| all_gather 后由 rank 0 写 checkpoint | 复用 80 节的 `save_sharded` 签名 | 正是 80 节反对的 gather-then-write；N 倍通信与内存 |
| 复制一份精简版 checkpoint 代码 | 单文件自包含 | 丢失了 80 节的大部分校验；应直接复用 80 节模块 |
| 张量通过 `mp.Queue` 回传 + `os._exit(0)` | 快速退出，避免析构卡住 | 在 Linux 默认共享策略下必然崩溃；应回传纯 Python/NumPy 数据并正常销毁进程组 |
| 只比较最终参数范数 | 实现简单 | 讲义说"每一步"；更严格的是每步比较参数哈希，或与单进程基线比较 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `nn.Module` 子类 | `class MiniGPT(nn.Module)`，`super().__init__()` | 自定义网络层；必须先调用父类构造函数才能注册子模块 |
| `nn.ModuleList` / `nn.Sequential` | `nn.ModuleList([TransformerBlock(...) for _ in range(num_layers)])` | 让子模块的参数被正确注册 |
| 类型注解 | `def forward(self, x: torch.Tensor) -> torch.Tensor` | 说明参数与返回值类型，不影响运行 |
| `assert` | `assert embed_dim % num_heads == 0` | 前置条件检查 |
| 元组解包 | `b, t, e = x.shape`、`q, k, v = qkv.unbind(dim=2)` | 一次拿到多个值 |
| 原地方法 `_` 后缀 | `m.mul_(...).add_(...)`、`local_grad.div_(...)` | 修改张量本身并返回它，可链式调用 |
| `p.data.copy_` | `scatter_flat_to_params` | 绕过 autograd 写入参数 |
| 生成器表达式 | `sum(p.numel() for p in module.parameters())` | 不建中间列表的求和 |
| 字典推导式 | `{k: v.clone() for k, v in model.state_dict().items()}` | 逐项拷贝，避免与模型共享内存 |
| 列表推导式 | `[torch.zeros_like(self.master_shard) for _ in range(self.world_size)]` | 构造接收缓冲区列表 |
| 负数取模 | `pad = (-total) % world_size` | Python 的 `%` 结果与除数同号，用来算"补到倍数还差多少" |
| 条件表达式 | `rank0_losses if rank == 0 else []` | 一行 if/else |
| `@dataclass` + `asdict` | `ShardEntry`、`asdict(s)` | 简洁的数据类与转 dict |
| f-string 格式符 | `f"{s:<6}{loss:<14.6f}"`、`f"{norm_drift:.2e}"`、`f"step_{CHECKPOINT_STEP:04d}"` | 左对齐宽度、6 位小数、科学计数、补零 |
| `try / except / finally` 嵌套 | `run_e2e` | 失败时清理并重新抛出；无论如何都回收子进程 |
| `raise` 无参数 | `except Exception: ...; raise` | 原样重新抛出当前异常 |
| `multiprocessing` spawn | `ctx = mp.get_context("spawn")`、`ctx.Process(...)`、`ctx.Queue()` | 跨进程启动与通信 |
| `os.environ` | `os.environ["GLOO_SOCKET_IFNAME"] = iface` | 设置环境变量，影响底层库 |
| `os._exit` vs `sys.exit` | worker 末尾 | `os._exit` 立即终止进程，不做清理 |
| `sys.platform` | `"lo0" if sys.platform == "darwin" else "lo"` | 区分操作系统 |
| `torch.frombuffer` | `torch.frombuffer(bytearray(payload), dtype=torch.uint8)` | 把字节缓冲区视作张量（需可写缓冲，所以包成 `bytearray`） |
| `if __name__ == "__main__"` | 文件末尾 | spawn 子进程会重新 import 本模块，这个保护防止子进程再次执行 `main()` |

---

## 6. 运行结果解读

**直接运行**（Python 3.13 + PyTorch 2.14.1 CPU，Linux）：

```text
world_size=4, steps=20, model=MiniGPT
model params: 29824
starting distributed train...
Traceback (most recent call last):
  ...
  File ".../main.py", line 380, in run_e2e
    rank, losses, norm, shard_bytes, master_at_ckpt = out_queue.get(timeout=180)
  File ".../torch/multiprocessing/reductions.py", line 538, in rebuild_storage_fd
    fd = df.detach()
  ...
EOFError
```

连续 3 次均失败（1 次 `EOFError`，2 次 `ConnectionResetError: [Errno 104] Connection reset by peer`），退出码 1，约 11 秒。训练本身已经完成，失败发生在结果回传。

**绕过后运行**：我们没有修改原文件，而是写了一个包装脚本：在主进程和每个 worker（替换 `main._train_worker` 为一个先调用 `torch.multiprocessing.set_sharing_strategy("file_system")` 再调用原函数的包装）中切换共享策略，然后调用原来的 `main()`。输出（约 39 秒，exit 0）：

```text
world_size=4, steps=20, model=MiniGPT
model params: 29824
starting distributed train...

step  rank0_loss
0     4.297341
1     4.295949
2     4.237854
3     4.261005
4     4.312036
5     4.203934
6     4.459343
7     4.335932
8     4.238627
9     4.364796
10    4.205659
11    4.176303
12    4.137795
13    4.232329
14    4.111523
15    4.218005
16    4.217341
17    4.317704
18    4.185369
19    4.222419

final param norm (must agree across ranks):
  rank 0: 54.513170
  rank 1: 54.513170
  rank 2: 54.513170
  rank 3: 54.513170
  drift across ranks: 0.00e+00

per-rank optimiser memory (ZeRO-1 shard, bytes):
  rank 0: 89472
  rank 1: 89472
  rank 2: 89472
  rank 3: 89472
  expected per-rank (fp32 master + m + v): 89472

checkpoint at step 10: /tmp/aie_e2e_zd_lbtzn/step_0010
RESUME VERIFIED: saved shard at step 10 matches in-memory snapshot byte-for-byte
```

逐项解读：

- **参数量 29,824**：见 3.2 节的分解。
- **loss**：从 4.297 开始，在 4.11–4.46 之间上下波动，最后 4.222。均匀随机语料的理论下界是 `ln 64 ≈ 4.159`；初始略高是因为随机初始化的 logits 并不完全均匀，训练把它往均匀分布拉。每步都是全新的数据，loss 的波动来自批次差异。讲义的不变量 (a)"monotonically decreases"并不成立；代码和测试只检查了 loss 有限。
- **与单进程基线完全一致**：单进程 Adam、batch = 16，rank 0 那 4 条序列上的 loss 序列与上表逐个相同，最终范数 54.51317 也相同——证明组合是正确的。
- **范数漂移 0**：每步各 rank 写回同一个 all_gather 结果，参数逐位相同。注意这只比较了**最终**范数，讲义说的是"every rank holds the same parameter norm at every step"。
- **内存 89,472 字节**：`29,824 / 4 = 7,456`，`× 3 × 4 B`。这只是优化器分片；每个 rank 还持有完整的 fp32 参数（119,296 B）和梯度（119,296 B），合计 328,064 B。讲义 Key Terms 中"Memory profile = params, grads, optimiser state"，打印内容只覆盖了第三项。
- **RESUME VERIFIED**：4 个 rank 的 master 分片从磁盘读回后与快照逐字节相等。打印出的 checkpoint 目录在 `main` 结束时已被删除。按我们对相近结构的序列化测算，每个分片约 216 KB（其中完整 `model_state` 约 119 KB，4 个分片里各存了一份相同的副本）。

**测试**：直接 `python3 -m pytest -q tests` 实测 `6 failed in 71.18s`（全部是同一个回传错误）；通过同样的包装方式运行 `tests/test_e2e.py`，`Ran 6 tests in 179.949s, OK`。

---

## 7. 动手改一改

1. **修复 Linux 崩溃**：把 `master_at_ckpt` 改成 `optim.master_shard.clone().numpy()` 回传（`verify_resume` 里用 `torch.from_numpy` 转回），或在 worker 开头设置 `file_system` 共享策略；在 worker 末尾加上 `dist.barrier()` 与 `dist.destroy_process_group()`。
2. **换成有结构的数据**：把 `make_corpus` 改成重复的短模式（例如 `torch.arange(VOCAB).repeat(...)` 加少量噪声），观察 loss 是否真的单调下降到远低于 `ln 64`；顺便把不变量 (a) 写成测试。
3. **每步一致性检查**：每步更新后计算参数的 sha256（或范数），`all_gather` 后断言所有 rank 相同，兑现讲义"at every step"的承诺。
4. **单进程基线测试**：把测验 Q10 的单进程 Adam 脚本写成测试，断言分布式最终范数与基线差小于 `1e-5`。
5. **真正的恢复**（讲义练习 3）：从 `step_0010` 读取每个 rank 的分片，恢复 `model_state` 与 `optim_state`，从 step 10 继续到 20，断言 loss 序列与不中断运行相同（测验 Q12 已在单进程上验证可行）。
6. **按 80 节的方式保存**：让每个 rank 直接写自己的 `rank{r}.bin`，只把 `(rank, sha256)` 用 `dist.gather_object` 收到 rank 0 写 manifest；再实现讲义练习 2（梯度累积 4 个 microbatch，证明梯度等于一个大 batch 的梯度）或练习 5（loss 尖峰回滚）。

---

## 8. 常见坑

- **用 `mp.Queue` 回传 torch 张量后立刻退出**：Linux 默认按 fd 共享，发送方必须活到接收方取走数据；回传 NumPy/字节/Python 数值最省心。
- **先构造优化器再 broadcast**：`ZeroOptimizer` 在构造时就拷贝了主参数分片，若之后才 broadcast，各 rank 的主参数分片会来自不同的初始化。
- **忘了补零或补零后忘了截断**：参数总数不能被 N 整除时，`chunk` 切分会不等长导致 `reduce_scatter` 报错；`all_gather` 后不 `[:total]` 截断，`scatter_flat_to_params` 会读到多余的零（不报错，但说明长度对不上）。
- **reduce_scatter 之后忘了除以 N**：相当于学习率放大 N 倍（对 Adam 影响较小，因为 m̂/√v̂ 对梯度尺度不敏感，但 ε 的相对作用会变，SGD 则直接放大 N 倍）。
- **集合通信调用不对称**：只在 rank 0 调用 `all_gather` 而其它 rank 不调用，会永久死锁。本节把 `_gather_payloads_to_rank0` 放在 `if rank == 0` 之外，所有 rank 都参与，这一点是对的。
- **各 rank batch 大小不同还简单除以 N**：平均梯度会有偏差；不等 batch 时应按样本数加权。
- **只恢复优化器状态、不恢复模型参数**（或反之），或忘了恢复 `step_count`：恢复后 loss 曲线出现台阶（测验 Q12 有实测数据）。
- **用随机数据验证"模型在学习"**：loss 不下降并不一定是 bug；先确认数据里有可学的信号。

---

## 9. 测试在验证什么

测试文件位于小节根目录的 `tests/test_e2e.py`，`setUp` 中**每个测试都完整跑一遍** `run_e2e(world_size=4, steps=20)`，`tearDown` 删除工作目录。所以 6 个测试要跑 6 次完整训练（绕过崩溃后实测共约 180 秒）。

| 测试 | 验证的性质 | 说明 |
|------|-----------|------|
| `test_all_ranks_end_with_same_param_norm` | 4 个 rank 最终范数在 4 位小数内相同 | 对应不变量 (b)，但只看最终一步 |
| `test_zero_shard_memory_matches_formula` | 每个 rank 的 `shard_bytes == chunk × 4 × 3` | 对应不变量 (c)；只覆盖优化器分片 |
| `test_checkpoint_round_trips_byte_equal` | `verify_resume` 返回 True | 对应不变量 (d)；只比较 master 分片 |
| `test_loss_log_has_one_per_step` | rank 0 记录了 20 个 loss | 训练循环跑满且没有提前退出 |
| `test_manifest_present_at_checkpoint_step` | checkpoint 可以按 world size 4 加载，每个分片都含 `model_state` 与 `optim_state` | checkpoint 内容的结构 |
| `test_loss_finite_and_no_nan` | 每个 loss 都不是 NaN、不是 +inf | 对应不变量 (a) 的弱化版本；`loss != loss` 是判断 NaN 的经典写法（NaN 不等于自身）；没有检查 −inf |

**实际运行**：

- 直接运行 `python3 -m pytest -q tests`：`6 failed in 71.18s`，每个用例都在 `setUp` 的 `out_queue.get` 处失败（`ConnectionResetError` / `EOFError`），原因见 3.9 节。
- 用包装脚本在主进程与 worker 中切换为 `file_system` 共享策略后运行同一个测试模块：`Ran 6 tests in 179.949s — OK`。

改进建议：用 `setUpClass` 只跑一次训练，让 6 个测试共享结果（可以把耗时缩短到约 1/6）；补充"与单进程基线一致"和"恢复后继续训练结果一致"这两个最有说服力的测试。
