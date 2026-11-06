# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 78 节 ZeRO Optimizer 状态分片 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（在 `code/` 目录下）；测试：`python -m unittest discover tests`（在小节根目录下） ｜ **依赖**：标准库 `multiprocessing` + 第三方 `torch`（CPU 即可，`torch.distributed` gloo 后端）

---

## 1. 这份代码在考察什么

数据并行（第 77 节）让每个 rank 都持有完整的参数、梯度和优化器状态。ZeRO stage 1 只改一件事：**优化器状态（fp32 主参数 + Adam 的 m、v）按 rank 切分**。这份代码在一个三层 MLP 上实现了它：

1. **扁平化**：把所有参数/梯度拼成一个连续向量，按 rank 切片（不能整除时补零）。
2. **reduce_scatter 梯度**：每个 rank 只收到自己那 1/N 分片的梯度和，除以 N 得平均梯度。
3. **分片 Adam**：只对自己的分片维护 m、v、主参数并更新——Adam 是逐元素的，所以与全量 Adam 等价。
4. **allgather 参数**：把更新后的各分片拼回完整参数，写回模型，供下一步前向使用。
5. **显存账本**：`shard_bytes()` 统计每 rank 的优化器字节数；`memory_table` 给出 DDP 与 ZeRO-1 的理论显存。

> 一句话：**通信总量和 DDP 一样（reduce_scatter + allgather = allreduce），但最大的显存项被除以 N**。同时要注意：这份代码全程 fp32，讲义和 docstring 里的"fp16 参数/梯度"并不存在，"主参数分片"与模型自身的 fp32 参数是重复的。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SEED=13 / WORLD_SIZE=4 / STEPS=20 / BATCH=8 / *_DIM` | 常量 | 实验配置（与第 77 节同结构的 MLP，种子不同） | — |
| `MiniMLP` | `nn.Module` | 16→32→32→4 的 MLP，1,732 个参数 | 被训练的模型 |
| `flat_param_numel` | 函数 | 参数总数 | 扁平化 |
| `gather_flat_params` / `scatter_flat_to_params` | 函数 | 参数 ↔ 扁平 fp32 向量 | 扁平化 |
| `gather_flat_grads` | 函数 | 梯度 → 扁平 fp32 向量（无梯度的参数补 0） | 扁平化 |
| `shard_bounds` | 函数 | 计算 rank 的分片区间与每片长度 | 分片 |
| `ZeroOptimizer` | 类 | 持有本 rank 的主参数/m/v 分片；`step()` = reduce_scatter → Adam → allgather | ZeRO-1 |
| `make_dataset` | 函数 | 线性回归合成数据 | 数据 |
| `_zero_worker` / `run_zero` | 函数 | 每个 rank 的训练循环 / spawn 启动器 | 多进程训练 |
| `memory_table` | 函数 | 按混合精度公式打印 DDP 与 ZeRO-1 的每 rank 显存 | 显存估算 |
| `main` | 函数 | 训练、打印 loss、各 rank 范数与分片字节、显存表 | demo |

数据流：`main` → `run_zero`（spawn 4 个 `_zero_worker`：初始化进程组 → 建模型 → broadcast 参数 → `ZeroOptimizer` 切出分片 → 20 步 {前向 → 反向 → `step()`：扁平梯度 → reduce_scatter → ÷N → Adam 更新分片 → all_gather → 写回模型} → 回传 loss、范数、分片字节）→ 打印。

---

## 3. 逐段精讲

### 3.1 扁平化工具

```python
def gather_flat_params(module: nn.Module) -> torch.Tensor:
    return torch.cat([p.detach().to(torch.float32).flatten() for p in module.parameters()])


def scatter_flat_to_params(module: nn.Module, flat: torch.Tensor) -> None:
    offset = 0
    for p in module.parameters():
        n = p.numel()
        p.data.copy_(flat[offset:offset + n].reshape(p.shape).to(p.dtype))
        offset += n
```

- 参数顺序由 `module.parameters()` 决定（注册顺序：`net.0.weight, net.0.bias, net.2.weight, ...`）。**所有 rank 必须用相同的顺序**，否则同一偏移量在不同 rank 上对应不同的参数。
- `torch.cat` 产生新的连续存储；`.to(torch.float32)` 为将来混合精度留了接口（目前模型本来就是 fp32，这一步是空操作）。
- 写回时 `p.data.copy_(...)` 原地覆盖，保持参数对象不变（优化器、hook 等持有的引用仍有效）。

```python
def gather_flat_grads(module: nn.Module) -> torch.Tensor:
    parts = []
    for p in module.parameters():
        if p.grad is None:
            parts.append(torch.zeros_like(p.data, dtype=torch.float32).flatten())
        else:
            parts.append(p.grad.detach().to(torch.float32).flatten())
    return torch.cat(parts)
```

- 没有梯度的参数用 0 填充——这比第 77 节的 `continue` 更稳妥：扁平向量长度在所有 rank 上一致，集合通信不会错位（相当于"未使用参数的梯度视为 0"）。

### 3.2 `shard_bounds`：切分与补零

```python
def shard_bounds(total: int, world_size: int, rank: int) -> tuple:
    pad = (-total) % world_size
    padded = total + pad
    chunk = padded // world_size
    start = rank * chunk
    end = min(start + chunk, total)
    return start, end, chunk
```

- `(-total) % world_size` 是"补到 N 的倍数所需的个数"。`total = 1,732, N = 4` 时不需补零，每片 433；`total = 17, N = 4` 时补 3 个，每片 5。
- ⚠️ 边界问题：`total = 5, N = 4` → `chunk = 2`，rank 3 得到 `(6, 5, 2)`，`start > end`。一般地，当补零量 ≥ 一片长度时，末尾的 rank 可能完全落在补零区。`ZeroOptimizer` 实际切片用的是 `rank * chunk` 和补零后的张量，没有使用 `start/end`，所以本节不会出错；但返回值语义有误导性，测试也没有覆盖。

### 3.3 `ZeroOptimizer.__init__`：只保留自己的分片

```python
        total = flat_param_numel(module)
        self.total = total
        start, end, chunk = shard_bounds(total, world_size, rank)
        ...
        full = gather_flat_params(module)
        padded = torch.zeros(chunk * world_size, dtype=torch.float32)
        padded[:total] = full
        self.master_shard = padded[rank * chunk:(rank + 1) * chunk].clone()
        self.m_shard = torch.zeros_like(self.master_shard)
        self.v_shard = torch.zeros_like(self.master_shard)
```

- 构造前，`_zero_worker` 已经从 rank 0 broadcast 了参数，所以各 rank 的 `full` 相同，切出的分片拼起来就是完整参数。
- `.clone()` 很关键：`padded[...]` 是视图，不 clone 的话 `master_shard` 会让整个 `padded`（全长）一直存活，分片就失去了省显存的意义。
- `m_shard / v_shard` 初始化为 0（Adam 的标准初始化）。
- `shard_bytes()` 返回 `(433 × 3) × 4 = 5,196` 字节：这才是本 rank 的优化器状态。
- ⚠️ 在纯 fp32 训练里，模型自己的参数就是 fp32 的全量副本，`master_shard` 与之**重复**。混合精度时它才有意义（模型持有 fp16/bf16 参数，fp32 主参数只在优化器里）。

### 3.4 `step()`：reduce_scatter → Adam → allgather

```python
    def step(self) -> None:
        flat_grad = gather_flat_grads(self.module)
        pad = (-self.total) % self.world_size
        padded_grad = torch.zeros(self.total + pad, dtype=torch.float32)
        padded_grad[:self.total] = flat_grad
        chunks = list(padded_grad.chunk(self.world_size))
        chunks = [c.contiguous() for c in chunks]
        local_grad = torch.zeros_like(chunks[0])
        dist.reduce_scatter(local_grad, chunks, op=dist.ReduceOp.SUM)
        local_grad.div_(self.world_size)
```

- `dist.reduce_scatter(output, input_list)`：每个 rank 提供 N 个块，rank r 收到"所有 rank 的第 r 块之和"。这正是第 76 节实现的原语。
- `÷ N` 得到平均梯度，与 DDP 和单卡的语义一致。
- 每个 rank 发送 `(N−1)/N × 4P` 字节（fp32）。

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

Adam 的标准公式，全部是原地运算：

| 代码 | 数学 |
|------|------|
| `m.mul_(β1).add_(g, alpha=1−β1)` | `m ← β1·m + (1−β1)·g` |
| `v.mul_(β2).addcmul_(g, g, value=1−β2)` | `v ← β2·v + (1−β2)·g²` |
| `bc1 = 1 − β1^t`，`m_hat = m / bc1` | 偏差修正（前几步 m、v 偏向 0） |
| `θ.addcdiv_(m_hat, sqrt(v_hat) + eps, value=−lr)` | `θ ← θ − lr · m̂ / (sqrt(v̂) + eps)` |

- 每个元素的更新只依赖它自己的 `g, m, v, θ`，所以分片独立更新与全量更新等价。我们与单进程 `torch.optim.Adam` 对拍：20 步 loss 最大差 1.43e-6，最终范数 11.21324224 vs 11.21324214。
- 补零位置的梯度恒为 0，m、v 保持 0，`m_hat / (sqrt(v_hat)+eps) = 0`，主参数中的补零位也保持 0，不会污染真实参数。

```python
        gathered = [torch.zeros_like(self.master_shard) for _ in range(self.world_size)]
        dist.all_gather(gathered, self.master_shard)
        flat_full = torch.cat(gathered)[:self.total]
        scatter_flat_to_params(self.module, flat_full)
```

- 每个 rank 广播自己更新后的分片，拼回全长并截掉补零，写回模型。所有 rank 得到相同的参数（测试与 demo 中 4 个 rank 的范数差为 0）。
- ⚠️ 这里传的是 fp32 `master_shard`；docstring 说"updated fp16 parameter shards are allgathered"，与代码不符。混合精度实现会先把分片转成 fp16/bf16 再 allgather，通信量减半。
- ⚠️ 峰值显存：每步都新建全长的 `flat_grad`、`padded_grad`、`gathered` 与 `flat_full`。在这个玩具模型上无所谓，生产实现会预分配扁平缓冲区并让参数/梯度直接是它的视图（FSDP 的 `FlatParameter`）。

```python
    def zero_grad(self) -> None:
        for p in self.module.parameters():
            if p.grad is not None:
                p.grad.detach_()
                p.grad.zero_()
```

- 与 `torch.optim.Optimizer.zero_grad(set_to_none=False)` 的行为一致：保留梯度张量、置零。

### 3.5 `_zero_worker` 与 `run_zero`

```python
    torch.manual_seed(SEED)
    model = MiniMLP()
    for p in model.parameters():
        dist.broadcast(p.data, src=0)
    optim = ZeroOptimizer(model, world_size=world_size, rank=rank, lr=lr)
    ...
    for step in range(steps):
        offset = step * world_size * batch + rank * batch
        ...
        optim.zero_grad()
        pred = model(x)
        loss = loss_fn(pred, y)
        loss.backward()
        optim.step()
```

- 与第 77 节的结构相同：broadcast 保证起点一致，每个 rank 取自己的 8 条样本。区别在于：没有 `sync_grads()`，梯度同步被合并进了 `optim.step()`（reduce_scatter）；优化器是 Adam 而不是 SGD。
- 结束时回传 `(rank, losses, norm, shard_bytes)`，都是 Python 标量/列表。
- `run_zero` 的 spawn、文件 rendezvous、清理逻辑与第 77 节相同。

### 3.6 `memory_table`

```python
    fp16 = 2
    fp32 = 4
    vanilla = (fp16 + fp16 + fp32 + fp32 + fp32) * p_params
    zero1 = (fp16 + fp16) * p_params + (fp32 * 3 * p_params) // world_size
    drop = 100 * (vanilla - zero1) / vanilla
```

- 公式与讲义表格一致：DDP `16P`，ZeRO-1 `4P + 12P/N`。
- ⚠️ 标题是"per-rank optimiser memory"，但数值是**总**显存（含 fp16 参数与梯度）；而且它描述的是混合精度方案，与本节 fp32 实现的实际占用不同（实际为 `4P + 4P + 12P/N = 11P` 字节，见测验 Q11）。
- `//` 整除：P 不能被 N 整除时会向下取整，与 `shard_bytes()`（向上取整含补零）略有差异。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 扁平化后按偏移切分 | 切分只是一个切片，各 rank 一致 | 一个参数可能跨两个 rank；需要逐层统计量的优化器（LAMB、Shampoo）不能直接用 |
| 补零到 N 的倍数 | `reduce_scatter` 要求等长块 | 末尾 rank 可能只有补零（`shard_bounds` 返回 `start > end`） |
| 每步临时拼接全长梯度/参数 | 代码简单 | 峰值显存仍是全长；生产用预分配的 FlatParameter |
| 全程 fp32 | 不引入混合精度的复杂性 | 主参数分片与模型参数重复；allgather 字节数翻倍；与讲义描述不符 |
| reduce_scatter 后 ÷N | 与 DDP 平均梯度语义一致 | 本地一次除法，可忽略 |
| 自己实现 Adam | 让分片状态可见 | 需与 `torch.optim.Adam` 对拍（本节没有做，我们补测差 1.4e-6） |
| 用"范数相同"验证一致性 | 简单 | 范数相同 ≠ 参数相同；没有与单进程参考对拍 |
| `memory_table` 用公式 | 展示 7B 级别的收益 | 不反映本节代码的真实占用 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表推导式 + `torch.cat` | `torch.cat([p.detach().to(torch.float32).flatten() for p in module.parameters()])` | 把多个张量展平后拼接 |
| 生成器表达式 | `sum(p.numel() for p in module.parameters())` | 不建中间列表直接求和 |
| 负数取模求补齐量 | `pad = (-total) % world_size` | `(-17) % 4 == 3` |
| 整除与 `min` | `chunk = padded // world_size`、`end = min(start + chunk, total)` | 地板除；取较小值 |
| 返回多个值 | `return start, end, chunk` / `start, end, chunk = shard_bounds(...)` | 实际返回一个元组，再解包 |
| 关键字参数默认值 | `lr: float = 0.05, beta1: float = 0.9, ...` | 带类型注解的默认参数 |
| 幂运算 | `self.beta1 ** self.step_count` | `β1^t` |
| torch 原地运算链 | `self.m_shard.mul_(self.beta1).add_(local_grad, alpha=1 - self.beta1)` | 原地方法返回自身，可以链式调用 |
| `addcmul_` / `addcdiv_` | `v.addcmul_(g, g, value=c)`、`θ.addcdiv_(m, d, value=-lr)` | `v += c·g·g`；`θ += −lr·m/d` |
| 切片 + `clone()` | `padded[rank * chunk:(rank + 1) * chunk].clone()` | 取出独立副本，释放对大张量的引用 |
| `zeros_like` 指定 dtype | `torch.zeros_like(p.data, dtype=torch.float32)` | 同形状、指定类型的全零张量 |
| `list(tensor.chunk(n))` | `chunks = list(padded_grad.chunk(self.world_size))` | 把元组转成列表便于后续处理 |
| 数字分隔符 | `memory_table(p_params=1_000_000, ...)`（测试中） | `_` 只是为了可读性 |
| f-string 对齐 | `f"  {name:<20} {b:>12} bytes"`、`{drop:.1f}%` | 左对齐 20、右对齐 12、1 位小数 |
| 字符串拼接 | `"\n".join(out)` | 用换行把多行合并为一个字符串 |

---

## 6. 运行结果解读

实际运行（Linux、Python 3.13、torch 2.14.1 CPU，约 5 秒，退出码 0）：

```text
world_size=4, steps=20, batch=8, model=MiniMLP
running ZeRO-1 across ranks...

step  rank0_loss    rank3_loss
0     10.118991     19.804293
1     18.429354     8.961042
2     32.978512     17.944227
...
10    4.380282      3.433152
...
18    3.214248      4.309986
19    2.480408      3.225639

final param norm (must agree across ranks):
  rank 0: norm=11.213242, optim_shard_bytes=5196
  rank 1: norm=11.213242, optim_shard_bytes=5196
  rank 2: norm=11.213242, optim_shard_bytes=5196
  rank 3: norm=11.213242, optim_shard_bytes=5196

per-rank optimiser memory:
  vanilla DDP                 27712 bytes
  ZeRO-1 (N=4)                12124 bytes
  drop: 56.2%
```

逐项解读：

- **loss 下降明显**：rank 0 从约 10 降到 2.5（第 77 节同结构模型用 SGD 20 步几乎不降）。Adam 在 lr = 0.05 下对这个小问题很有效；前几步 loss 冲高（step 2 达到 33）是 Adam 初期步长较大造成的。两列 loss 是不同分片上的值，本来就不同。
- **4 个 rank 范数相同**：allgather 后所有 rank 的参数一致。我们另外与单进程 `torch.optim.Adam` 对拍，loss 最大差 1.43e-6。
- **`optim_shard_bytes = 5196`**：`433 × 3 × 4`，每个 rank 只存 1/4 的主参数、m、v；全量是 `1,732 × 3 × 4 = 20,784`。
- **显存表**：`vanilla = 16 × 1,732 = 27,712`；`ZeRO-1 = 4 × 1,732 + 12 × 1,732 / 4 = 6,928 + 5,196 = 12,124`；下降 `(16 − 7)/16 = 56.25%`。这是按混合精度公式算的理论值；本节代码实际每 rank 持有 fp32 参数 + fp32 梯度 + 分片 = `6,928 + 6,928 + 5,196 = 19,052` 字节。
- 同一函数代入 7B、N = 8：vanilla 112 GB，ZeRO-1 38.5 GB，下降 65.6%；N = 64 时下降 73.8%（与讲义一致）。

---

## 7. 动手改一改

1. **与参考对拍**：加一个 `reference_adam()`（单进程、`torch.optim.Adam`、loss 除以 N 累加），在 `main` 中打印每步差值（测验 Q9）。
2. **全局梯度裁剪**（讲义练习 4）：在 `step()` 中对分片平方和做 allreduce 求全局范数（测验 Q10，实测与 `clip_grad_norm_` 一致）。
3. **修正 `shard_bounds`**：让 `start = min(rank * chunk, total)`，并补测 `total = 5, N = 4` 的情况。
4. **混合精度版本**：模型用 `bfloat16` 参数，`gather_flat_grads` 后转 fp32 做 reduce_scatter（或用 bf16 通信再转 fp32），allgather 前把主参数分片转 bf16；统计每 rank 的真实字节数，与 `memory_table` 对比（讲义练习 2）。
5. **naive ZeRO**（讲义练习 5）：把 reduce_scatter 换成 allreduce 再切片，用第 76 节的字节计数思路比较两种做法的通信量（allreduce + allgather = 1.5 倍）。
6. **进阶：ZeRO-2**（讲义练习 1）：反向时用 hook 按桶 reduce_scatter 并**释放**全量梯度，只保留分片；注意"置零"并不省显存（测验 Q12）。

---

## 8. 常见坑

- **各 rank 参数顺序不同**：扁平化依赖 `parameters()` 的顺序，模型构建方式必须完全一致。
- **忘记 `÷N`**：梯度尺度随 N 变化；对 Adam 影响小，但对裁剪、SGD、weight decay 影响大。
- **把分片当视图保存**：`padded[...]` 不 `clone()`，全长张量无法释放。
- **以为"置零"能省显存**：省显存靠释放张量，而不是把数值改成 0。
- **把 `memory_table` 当实测值**：它是混合精度公式，本节代码是 fp32。
- **用逐元素分片实现逐层优化器**：LAMB/LARS 需要每层的范数，按扁平偏移切分会把一层切到多个 rank 上，需要额外通信。
- **梯度裁剪只用本地范数**：每个 rank 只看到 1/N 的梯度，必须 allreduce 平方和得到全局范数。
- **checkpoint 只存 rank 0**：优化器状态分散在所有 rank 上，必须每个 rank 都保存自己的分片（第 80 节）。

---

## 9. 测试在验证什么

测试文件：`tests/test_zero.py`（位于小节根目录的 `tests/`），共 7 个用例。运行方式（在小节根目录）：

```bash
python3 -m unittest discover tests -v
```

实际运行结果：`Ran 7 tests in 9.228s  OK`。

| 用例 | 验证的性质 |
|------|-----------|
| `test_shard_bounds_evenly_divides` | `shard_bounds(16, 4, 0) == (0, 4, 4)`、`(16, 4, 3) == (12, 16, 4)` |
| `test_shard_bounds_handles_padding` | `total = 17` 时每片长 5，rank 3 的 `end ≤ 17`——没有检查 `start ≤ end` |
| `test_flatten_roundtrip_preserves_params` | `gather_flat_params` → `scatter_flat_to_params` 往返后参数不变（注释"`flat += 0` ensure independent storage"并不准确：`torch.cat` 本来就是新存储，`+= 0` 是原地空操作） |
| `test_all_ranks_end_with_same_param_norm` | 4 rank、5 步后范数相同（`places=4`） |
| `test_loss_converges_under_zero` | 20 步后 rank 0 的最后一个 loss 小于第一个（单点比较，受分片噪声影响） |
| `test_shard_bytes_smaller_than_full_optim_state` | 分片字节数 < 全量 `P × 4 × 3` |
| `test_memory_table_reports_zero_drop` | 显存表包含 "vanilla DDP"、"ZeRO-1"、"drop:" 字样 |

测试的局限：没有与 `torch.optim.Adam` 对拍、没有比较参数向量（只比较范数）、没有测试不能整除的参数总数下的端到端训练、没有验证显存表的数值。
