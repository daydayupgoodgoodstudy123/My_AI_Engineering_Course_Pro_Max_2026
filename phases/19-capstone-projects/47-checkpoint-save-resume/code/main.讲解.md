# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 47 节 Checkpoint 保存与恢复 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py [--total-steps 24] [--interrupt-at 10] [--num-shards 3] [--seed 11]`（在 `code/` 目录下；`--sharded` 参数被解析但未使用，脚本总是先跑单文件、再跑分片两个 demo）；测试：`python3 -m pytest -q test_main.py` 或 `python3 -m unittest test_main -v` ｜ **依赖**：`torch`、`numpy`（第三方）；其余为标准库（`argparse`、`hashlib`、`json`、`os`、`random`、`tempfile`、`time`、`dataclasses`、`pathlib`、`typing`）
>
> **注意**：脚本结尾**无条件**把摘要写到 `../outputs/resume-demo.json`（覆盖仓库中的同名文件）。本讲解的运行结果是把 `code/` 复制到临时目录后运行得到的，没有改动仓库文件。

---

## 1. 这份代码在考察什么

长时间训练一定会被打断（墙钟上限、节点重启、抢占）。这份代码实现了让训练"被杀死后能原样接着跑"的全部零件：

1. **完整的训练状态**：模型、优化器、调度器、训练计数（step / epoch / batch_in_epoch / loss 历史）、RNG 状态，打包成一个 payload。
2. **原子保存**：同目录唯一临时文件 → `os.replace`，任何时刻崩溃都不会留下半个 checkpoint。
3. **安全加载**：`torch.load(..., weights_only=True)`，配合"RNG 状态存成纯列表"，让加载器无需反序列化任意对象。
4. **分片 checkpoint**：参数按键轮询分到多个分片，`meta.pt` 存其余状态，`index.json` 存哈希；加载时校验每个哈希并拒绝逃出目录的路径。
5. **epoch 中间恢复的验证**：同一配置训练两次——一次不中断、一次在中途保存并在"新进程"（新模型对象）中恢复——比较中断之后的 loss 序列，最大差必须 < 1e-4。

> 一句话：**checkpoint = 一切会影响下一步计算的状态 + 原子写入 + 可校验、可安全读取的格式**；验证方法是"中断后的 loss 曲线与不中断时一模一样"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CHECKPOINT_SCHEMA` / `SHARD_SCHEMA` | 常量 | `"ckpt.v1"`、`"ckpt-shard.v1"` | 格式版本 |
| `TrainState` | dataclass | step、epoch、batch_in_epoch、losses | 训练计数 |
| `seed_everything` | 函数 | 同时设置 Python、NumPy、torch（含 CUDA）种子 | 可复现 |
| `make_model` / `make_optimizer_and_scheduler` | 函数 | 3 层 MLP；AdamW + `CosineAnnealingLR` | 被保存的对象 |
| `synthetic_loader` | 生成器函数 | 用独立 Generator 产出随机 batch（**未被使用**） | — |
| `capture_rng_state` / `restore_rng_state` / `tuple_from_nested` | 函数 | 抓取/恢复四种 RNG 状态，全部转成纯 Python 类型 | RNG 状态 |
| `atomic_save` / `atomic_write_json` | 函数 | 临时文件 + `os.replace` | 原子保存 |
| `file_sha256` | 函数 | 分块计算文件 sha256 | 完整性校验 |
| `save_checkpoint` / `load_checkpoint` | 函数 | 单文件 checkpoint 的保存与恢复 | 完整往返 |
| `shard_keys_by_prefix` | 函数 | 排序后的参数键轮询分到 N 个分片 | 分片布局 |
| `save_sharded_checkpoint` / `load_sharded_checkpoint` | 函数 | 分片 + meta + index 的保存与带校验的恢复 | 分片 checkpoint |
| `step_one` | 函数 | 一次前向、反向、优化器 step、调度器 step | 训练步 |
| `train_until` | 函数 | 按 `(epoch, batch_in_epoch)` 重建数据流并训练到 `stop_step` | epoch 中间恢复 |
| `run_resume_demo` | 函数 | 不中断 vs 中断恢复两条轨迹，返回最大 loss 差 | 正确性验证 |
| `parse_args` / `main` | 函数 | 依次跑单文件与分片 demo，写摘要 JSON | 入口 |

数据流：`main` → `run_resume_demo(sharded=False)`：`seed_everything` → 模型 1 `train_until(stop=interrupt_at)` → `save_checkpoint` → 模型 1 继续训练到 `total_steps`（基线）→ `seed_everything` → 新建模型 2 → `load_checkpoint` → 模型 2 `train_until(stop=total_steps)` → 比较两条 loss 序列 → 同样流程跑 `sharded=True` → `atomic_write_json(summary)`。

---

## 3. 逐段精讲

### 3.1 训练状态、种子与被保存的对象

```python
@dataclass
class TrainState:
    step: int
    epoch: int
    batch_in_epoch: int
    losses: List[float] = field(default_factory=list)

def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

def make_optimizer_and_scheduler(model, lr, total_steps):
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=total_steps)
    return opt, sched
```

- `field(default_factory=list)`：可变默认值必须用工厂函数，否则所有实例会共享同一个列表。
- `seed_everything` 覆盖四种随机源；但种子只决定**起点**，checkpoint 需要的是**当前状态**（讲义 Key Terms："RNG state… not just the seed"）。
- 模型 `16 → 24 → 24 → 4`，参数量 `16·24+24 + 24·24+24 + 24·4+4 = 1,108`。
- `CosineAnnealingLR(T_max=total_steps)`：无 warmup、`eta_min=0`，lr 从 0.01 余弦衰减到 0。它的 `state_dict()` 已实测包含 `T_max`、`eta_min`、`base_lrs`、`last_epoch`、`_step_count`、`_last_lr` 等——`last_epoch` 就是调度器在曲线上的位置。
- `synthetic_loader` 定义了却没有被调用，`train_until` 内联了相同的数据生成逻辑。

### 3.2 RNG 状态：抓取与恢复

```python
def capture_rng_state() -> Dict[str, Any]:
    name, keys, pos, has_gauss, cached_gaussian = np.random.get_state()
    state = {
        "python": random.getstate(),
        "numpy": (name, keys.tolist(), int(pos), int(has_gauss), float(cached_gaussian)),
        "torch_cpu": torch.get_rng_state().tolist(),
    }
    if torch.cuda.is_available():
        state["torch_cuda"] = [s.tolist() for s in torch.cuda.get_rng_state_all()]
    return state
```

- `np.random.get_state()` 返回 5 元组：算法名 `'MT19937'`、624 个 uint32 的 key 数组、位置、是否缓存了高斯数、缓存值。NumPy 数组不在 weights-only 加载器的允许列表中，所以 `tolist()` 成纯列表，其余转成 `int`/`float`。
- `random.getstate()` 本身就是由整数组成的元组，可以直接保存。
- `torch.get_rng_state()` 是 uint8 张量（本环境 5,056 字节），`tolist()` 后成为 5,056 个整数的列表。张量本身其实是 weights-only 允许的类型，这一步转换不是必需的，但保持了"全部纯 Python"的一致性。
- CUDA 每张卡一份状态，用列表推导式逐个转换。

```python
def restore_rng_state(state):
    py = state.get("python")
    if py is not None:
        random.setstate(tuple_from_nested(py))
    np_state = state.get("numpy")
    if np_state is not None:
        np.random.set_state(tuple_from_nested(np_state))
    cpu = state.get("torch_cpu")
    if cpu is not None:
        torch.set_rng_state(torch.tensor(cpu, dtype=torch.uint8))
    ...

def tuple_from_nested(obj):
    if isinstance(obj, list):
        return tuple(tuple_from_nested(x) for x in obj)
    return obj
```

- `random.setstate` 要求元组；如果某种序列化方式把元组变成了列表（例如走 JSON），`tuple_from_nested` 会递归地转回去。用 `torch.save` 保存时元组会原样保留（已实测加载后类型是 `tuple`），所以这里起的是防御作用。
- `torch.tensor(cpu, dtype=torch.uint8)` 把整数列表还原成字节张量交给 `set_rng_state`。
- 用 `.get()` 读取，缺失的键直接跳过，兼容在无 GPU 机器上保存、在有 GPU 机器上恢复的情况。
- ⚠️ 在本 demo 中，这些 RNG 状态**实际上不影响结果**：模型没有 Dropout，数据来自独立的 `torch.Generator`。已实测把 `restore_rng_state` 换成空操作，恢复后 loss 最大差仍为 0.0；而给模型加上 `nn.Dropout(0.2)` 后，不恢复 RNG 的最大差为 0.061、恢复则为 0.0（测验 Q9）。

### 3.3 原子保存

```python
def atomic_save(payload, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(delete=False, dir=str(path.parent),
                                      prefix=path.name + ".", suffix=".tmp")
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        torch.save(payload, tmp_path)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
    return path
```

- `NamedTemporaryFile(delete=False, dir=目标目录, prefix="ckpt.pt.", suffix=".tmp")`：在**同一目录**生成唯一文件名（如 `ckpt.pt.k3j9x2.tmp`），保证 rename 不跨文件系统、两个写者不会撞名。先 `close()` 再交给 `torch.save` 按路径重新打开写入。
- `os.replace(src, dst)`：目标已存在时直接覆盖，在 POSIX 同一文件系统内是原子的；与 `os.rename` 不同，它在 Windows 上也会覆盖已存在的目标。
- `finally` 的清理：成功时临时文件已被改名，`exists()` 为 False，什么都不做；`torch.save` 或 `os.replace` 抛异常时删除临时文件。内层再捕获 `FileNotFoundError`，防止"检查后、删除前"文件被别人删掉的竞态。
- ⚠️ 没有 `fsync`：原子性保证"要么旧、要么新"，但不保证断电后新数据已落盘；讲义延伸阅读专门提到了 `fsync`。完整做法是写完后 fsync 文件、rename 后 fsync 目录（测验 Q11 给出了改写）。
- ⚠️ 进程被 `SIGKILL` 时 `finally` 不执行，会留下孤儿 `.tmp` 文件，需要启动时清理。

```python
def atomic_write_json(payload, path):
    ...
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, dir=str(path.parent),
                                      prefix=path.name + ".", suffix=".tmp", encoding="utf-8")
    tmp_path = Path(tmp.name)
    try:
        json.dump(payload, tmp, indent=2)
        tmp.write("\n")
        tmp.close()
        os.replace(tmp_path, path)
    finally:
        ...
```

- JSON 版本直接写入已打开的临时文件对象，写完关闭再替换。注意如果 `json.dump` 抛异常，文件句柄没有显式关闭就去 `unlink`——在 POSIX 上没问题，在 Windows 上删除打开中的文件会失败。

### 3.4 sha256

```python
def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
```

- `iter(callable, sentinel)` 的双参数形式：反复调用 `f.read(65536)`，直到返回空字节串为止。按 64 KiB 分块读取，大文件也不会一次性读进内存。
- `1 << 16` 是 2^16 = 65,536。

### 3.5 单文件 checkpoint

```python
def save_checkpoint(model, optimizer, scheduler, state, out_path, *, schema=CHECKPOINT_SCHEMA, extras=None):
    payload = {
        "schema": schema,
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "state": {"step": state.step, "epoch": state.epoch,
                  "batch_in_epoch": state.batch_in_epoch, "losses": list(state.losses)},
        "rng": capture_rng_state(),
        "wall_saved_at": time.time(),
    }
    if extras:
        payload["extras"] = extras
    atomic_save(payload, out_path)
    return payload
```

- 讲义的"五个桶"一一对应：`model`、`optimizer`、`scheduler`、`state`、`rng`，外加 `schema` 与保存时间。
- `list(state.losses)` 复制一份，避免之后训练继续追加时影响已构造的 payload。
- `wall_saved_at` 让每次保存的字节都不同（哈希也不同），所以 checkpoint 不是"位级可复现"的文件。
- loss 历史随步数线性增长，长训练中会让每个 checkpoint 越来越大。

```python
def load_checkpoint(path, model, optimizer, scheduler) -> TrainState:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if not str(payload.get("schema", "")).startswith("ckpt"):
        raise ValueError(f"unknown schema {payload.get('schema')}")
    model.load_state_dict(payload["model"])
    optimizer.load_state_dict(payload["optimizer"])
    scheduler.load_state_dict(payload["scheduler"])
    restore_rng_state(payload["rng"])
    s = payload["state"]
    return TrainState(step=int(s["step"]), ...)
```

- `map_location="cpu"`：GPU 上保存的张量也先加载到 CPU，避免目标机器没有对应 GPU 时报错；`load_state_dict` 会把值拷贝进已在正确设备上的参数。
- `weights_only=True`：遇到非白名单对象抛 `pickle.UnpicklingError`（测试 `test_load_refuses_pickled_objects` 验证）。
- **加载顺序**：先建好"空白"的模型、优化器、调度器（结构必须与保存时一致），再分别 `load_state_dict`。优化器的 state_dict 按参数**顺序编号**而不是按名字保存，所以模型参数的注册顺序不能变。
- ⚠️ schema 检查只是 `startswith("ckpt")`：`"ckpt-shard.v1"`、`"ckpt.v99"` 都能通过（已实测用 `ckpt-shard.v1` 的 payload 成功加载）。讲义说"the loader dispatches"，代码没有分派逻辑（测验 Q8、Q12）。
- 用 `raise ValueError` 而不是 `assert` 做检查——讲义："because `python -O` strips asserts"。

### 3.6 分片布局

```python
def shard_keys_by_prefix(state_dict, num_shards):
    if num_shards < 1:
        raise ValueError("num_shards must be >= 1")
    keys = sorted(state_dict.keys())
    shards = {i: [] for i in range(num_shards)}
    for i, k in enumerate(keys):
        shards[i % num_shards].append(k)
    return shards
```

- 先排序再轮询（`i % num_shards`），保证布局确定。demo 模型的 6 个键排序后为 `0.bias, 0.weight, 2.bias, 2.weight, 4.bias, 4.weight`，3 个分片已实测为：`{0: ['0.bias', '2.weight'], 1: ['0.weight', '4.bias'], 2: ['2.bias', '4.weight']}`。
- 函数名叫 `by_prefix`，文件 docstring 说"splits the model state by parameter group"，实际是**按键轮询**，与前缀和参数组都无关（讲义正文与本函数自己的 docstring 说的是 round robin）。
- 轮询让各分片的**键数**相差不超过 1，但不保证**字节数**均衡（本例分片大小 4,549 / 3,717 / 2,629 字节）。按层或按大小贪心分配更适合真实大模型（讲义练习 1）。

### 3.7 分片保存

```python
    for shard_idx in range(num_shards):
        keys = layout[shard_idx]
        tensors = {k: model_sd[k] for k in keys}
        shard_path = out_dir / f"model.shard-{shard_idx:03d}.pt"
        atomic_save({"schema": SHARD_SCHEMA, "tensors": tensors, "keys": keys}, shard_path)
        shard_files.append({"shard": shard_idx, "path": shard_path.name,
                            "num_params": len(keys), "sha256": file_sha256(shard_path)})
    meta_path = out_dir / "meta.pt"
    meta_payload = {"schema": CHECKPOINT_SCHEMA + "-sharded", "optimizer": ..., "scheduler": ...,
                    "state": {...}, "rng": capture_rng_state(), "wall_saved_at": time.time(),
                    "shards": shard_files, "extras": extras or {}}
    atomic_save(meta_payload, meta_path)
    index_payload = {"schema": CHECKPOINT_SCHEMA + "-index", "num_shards": num_shards,
                     "shards": shard_files, "meta_sha256": file_sha256(meta_path),
                     "saved_at": meta_payload["wall_saved_at"], "step": state.step}
    atomic_write_json(index_payload, out_dir / "index.json")
```

- **写入顺序**：分片 → meta（含分片哈希）→ index（含 meta 哈希）。index 最后写，所以只要 index 存在且哈希都对得上，就说明前面的文件都已完整写好；这是一种"提交点"设计。
- `f"{shard_idx:03d}"` 零填充成 `000`、`001`，文件名排序与编号顺序一致。
- `num_params` 实际是**键（张量）的个数**，不是参数元素个数，命名容易误导。
- ⚠️ 讲义说"the meta is small and reads first"，但 meta 里有完整的 AdamW 状态（两份与模型同样大小的矩估计）和 RNG 列表。已实测：meta.pt 33,477 字节，三个分片合计 10,895 字节——meta 是分片总和的 3 倍。真实大模型中优化器状态也应该分片。
- ⚠️ 覆盖保存时存在中间状态：新分片已替换、index 仍是旧的，此时加载会因哈希不匹配而失败（安全但不可用）。生产做法是每次保存写到新目录（如 `step-000010/`），最后原子地更新 `latest` 指针。

### 3.8 分片加载与校验

```python
    index = json.loads((ckpt_dir / "index.json").read_text())
    expected_sha = index["meta_sha256"]
    meta_path = ckpt_dir / "meta.pt"
    actual_sha = file_sha256(meta_path)
    if actual_sha != expected_sha:
        raise ValueError(...)
    meta = torch.load(meta_path, map_location="cpu", weights_only=True)
    root = ckpt_dir.resolve()
    merged = {}
    for shard in meta["shards"]:
        shard_path = (ckpt_dir / shard["path"]).resolve()
        if not shard_path.is_relative_to(root):
            raise ValueError(f"shard path escapes the checkpoint directory: {shard['path']}")
        actual = file_sha256(shard_path)
        if actual != shard["sha256"]:
            raise ValueError(f"shard sha mismatch: {shard['path']}")
        body = torch.load(shard_path, map_location="cpu", weights_only=True)
        if body["schema"] != SHARD_SCHEMA:
            raise ValueError(...)
        merged.update(body["tensors"])
    model.load_state_dict(merged)
```

- **信任链**：index 中的 meta 哈希 → 已校验的 meta 中的分片清单与分片哈希 → 每个分片。分片清单取自 meta（而非 index），因为 meta 已被校验。
- **先校验哈希再 `torch.load`**：不对未经校验的字节做反序列化。
- **路径约束**：`resolve()` 消除 `..` 和符号链接后，用 `Path.is_relative_to`（Python 3.9+）确认仍在 checkpoint 目录内，防止 `../outside.pt` 这类路径穿越。讲义同时说"The shards can land on different physical disks"，与这条约束有些矛盾——要跨盘只能通过挂载点放在同一目录树下。
- `model.load_state_dict(merged)` 默认 `strict=True`：缺少或多出任何键都会报错，所以"分片丢了一个"会被发现。
- index 中的 `num_shards` 与 `shards` 字段没有被用来校验。
- ⚠️ 哈希只能防"意外损坏"。能同时改写 index 与 meta 的攻击者可以重算哈希（测试 `test_shard_path_outside_checkpoint_dir_is_rejected` 正是这样构造的），这时只能靠路径约束与 weights-only 加载兜底；防篡改需要签名。

### 3.9 训练步与 epoch 中间恢复

```python
def step_one(model, optimizer, scheduler, x, y, loss_fn) -> float:
    optimizer.zero_grad()
    loss = loss_fn(model(x), y)
    loss.backward()
    optimizer.step()
    scheduler.step()
    return float(loss.detach().item())
```

- 标准顺序：`optimizer.step()` 之后 `scheduler.step()`，调度器每个训练步推进一次。

```python
def train_until(model, optimizer, scheduler, loss_fn, state, *, stop_step,
                batches_per_epoch, batch_size, in_dim, out_dim) -> TrainState:
    while state.step < stop_step:
        gen = torch.Generator()
        gen.manual_seed(12345 + state.epoch)
        for _ in range(state.batch_in_epoch):
            torch.randn(batch_size, in_dim, generator=gen)
            torch.randint(low=0, high=out_dim, size=(batch_size,), generator=gen)
        while state.batch_in_epoch < batches_per_epoch and state.step < stop_step:
            x = torch.randn(batch_size, in_dim, generator=gen)
            y = torch.randint(low=0, high=out_dim, size=(batch_size,), generator=gen)
            loss = step_one(model, optimizer, scheduler, x, y, loss_fn)
            state.losses.append(loss)
            state.step += 1
            state.batch_in_epoch += 1
        if state.batch_in_epoch >= batches_per_epoch:
            state.epoch += 1
            state.batch_in_epoch = 0
    return state
```

- **数据顺序是 `(epoch, batch_in_epoch)` 的确定函数**：每个 epoch 用 `12345 + epoch` 新建生成器，所以不需要把生成器状态存进 checkpoint。
- **快进**：先空跑 `batch_in_epoch` 次相同的随机调用（形状、顺序必须与真实取数完全一致），丢弃结果，生成器就停在下一个未消费的 batch 上。代价是被跳过的数据要真的生成一遍；对真实数据集，通常改为保存样本偏移或 sampler 状态。
- 内层循环两个退出条件：epoch 用完，或到达 `stop_step`。外层在 epoch 用完时进位。
- ⚠️ **默认参数下 checkpoint 落在 epoch 边界**：`interrupt_at=10`、`batches_per_epoch=5`，已实测保存时状态为 `(step=10, epoch=2, batch_in_epoch=0)`，快进 0 个 batch，"epoch 中间恢复"没有被演示。改用 `--interrupt-at 7` 时保存状态为 `(7, 1, 2)`，实测最大差仍为 0.0，快进逻辑是正确的（测验 Q10）。
- 函数原地修改传入的 `state` 并返回它（`run_resume_demo` 依赖这一点读取 `state_1.losses`）。

### 3.10 `run_resume_demo` 与 `main`

```python
    seed_everything(seed)
    m1 = make_model(in_dim, hidden, out_dim)
    o1, s1 = make_optimizer_and_scheduler(m1, lr=0.01, total_steps=total_steps)
    state_1 = TrainState(step=0, epoch=0, batch_in_epoch=0)
    train_until(m1, o1, s1, loss_fn, state_1, stop_step=interrupt_at, ...)
    save_checkpoint(m1, o1, s1, state_1, ckpt_dir / "ckpt.pt")      # 或分片版本
    train_until(m1, o1, s1, loss_fn, state_1, stop_step=total_steps, ...)
    full_losses = list(state_1.losses)

    seed_everything(seed)
    m2 = make_model(in_dim, hidden, out_dim)
    o2, s2 = make_optimizer_and_scheduler(m2, lr=0.01, total_steps=total_steps)
    loaded = load_checkpoint(ckpt_dir / "ckpt.pt", m2, o2, s2)
    train_until(m2, o2, s2, loss_fn, loaded, stop_step=total_steps, ...)
    ...
    max_diff = max(abs(a - b) for a, b in zip(suffix_full, suffix_resumed, strict=True))
```

- 基线轨迹与"保存"在**同一次运行**中完成：先训练到 `interrupt_at`、保存、再继续训练到底，于是保存操作本身不能扰动训练（`capture_rng_state` 只读不写）。
- "新进程"用新建的 `m2/o2/s2` 模拟。它们用同一个种子初始化，但随即被 checkpoint 覆盖，所以初始化对结果没有影响。
- `zip(..., strict=True)`（Python 3.10+）：两条序列长度不同时直接报错，而不是悄悄截断。
- `resumed_losses` 前 `interrupt_at` 个元素来自 checkpoint 中的 loss 历史，后面才是新训练的结果。
- `main` 中的 `assert ... < 1e-4` 与讲义"Integrity checks raise `ValueError` instead of using `assert`"的原则不一致（这里是 demo 的自检，不是加载器的完整性检查，影响不大，但 `python -O` 下会失效）。
- `--sharded` 参数被解析后从未使用；`main` 总是两种模式都跑。
- 摘要写到 `OUT_DIR / "resume-demo.json"`，没有 `--no-write` 开关。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 五类状态全部进 payload | 恢复后的每一步与不中断时一致 | loss 历史随步数增长；生产中把指标写到独立的日志系统 |
| 同目录临时文件 + `os.replace` | 崩溃不留半个文件 | 无 fsync，不防断电；被杀死时留孤儿 `.tmp` |
| `weights_only=True` + 纯列表 RNG | 防止恶意 pickle 执行代码 | 只能存白名单类型；需 torch ≥ 2.6（讲义） |
| 数据顺序由 `(epoch, batch_in_epoch)` 决定、快进跳过 | 不必保存生成器内部状态 | 快进要真的生成被跳过的数据；真实数据集用偏移量 |
| 分片：键轮询 | 确定、键数均衡、索引易读 | 字节数不均衡；按层或按大小分更实用 |
| meta 存优化器 + RNG | 实现简单 | meta 比全部分片还大（33 KB vs 11 KB）；优化器状态也应分片 |
| 写入顺序 分片 → meta → index | index 是提交点 | 覆盖保存时存在"新分片 + 旧 index"的不可用窗口；用新目录 + `latest` 指针 |
| 哈希链 + 路径约束 | 发现损坏与路径穿越 | 不防有意篡改；需要签名 |
| schema 前缀检查 | 简单 | 误收其他格式；应精确匹配并逐级迁移 |
| 校验用 `ValueError` | `python -O` 不会移除 | demo 末尾仍用了 `assert` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + `field(default_factory=list)` | `TrainState.losses` | 可变默认值必须用工厂函数 |
| 元组解包 | `name, keys, pos, has_gauss, cached_gaussian = np.random.get_state()` | 一次拆出 5 个返回值 |
| 递归函数 | `tuple_from_nested` | 把任意嵌套的列表转成元组 |
| 生成器表达式传给构造器 | `tuple(tuple_from_nested(x) for x in obj)` | 不建中间列表 |
| `isinstance` | `if isinstance(obj, list)` | 类型判断 |
| `dict.get` | `state.get("python")` | 键不存在时返回 None，不抛异常 |
| `try / finally` 与嵌套 `try / except` | `atomic_save` | 无论成功与否都执行清理；忽略特定异常 |
| `tempfile.NamedTemporaryFile(delete=False, dir=..., prefix=..., suffix=...)` | `atomic_save` | 在指定目录生成唯一文件名，关闭后不自动删除 |
| `tempfile.TemporaryDirectory()` 上下文 | `main`、测试 | 退出 `with` 时自动删除整个目录 |
| `os.replace` | `os.replace(tmp_path, path)` | 原子替换（同文件系统） |
| 双参数 `iter(callable, sentinel)` | `iter(lambda: f.read(1 << 16), b"")` | 反复调用直到返回哨兵值 |
| 位移运算 | `1 << 16` | 等于 65,536 |
| `hashlib.sha256().update/hexdigest` | `file_sha256` | 增量计算哈希 |
| f-string 零填充 | `f"model.shard-{shard_idx:03d}.pt"` | 宽度 3、不足补 0 |
| 字典推导式 | `{k: model_sd[k] for k in keys}`、`{i: [] for i in range(num_shards)}` | 一行构造字典 |
| `Path.resolve()` / `Path.is_relative_to()` | `load_sharded_checkpoint` | 规范化绝对路径；判断是否在某目录之下（3.9+） |
| 仅限关键字参数 `*` | `def save_checkpoint(..., *, schema=..., extras=None)` | `*` 之后必须按名字传 |
| `Optional[...]`、`Dict[str, Any]` | 函数签名 | 类型提示 |
| `zip(..., strict=True)` | `run_resume_demo` | 长度不一致时报错（3.10+） |
| 字典推导式过滤 | `{k: v for k, v in single.items() if k not in (...)}` | 打印时去掉长列表 |
| `raise SystemExit(main())` | 文件末尾 | 以返回值作退出码 |

---

## 6. 运行结果解读

实际运行（把 `code/` 复制到临时目录后执行 `python3 main.py`，torch 2.14 CPU，约 3.8 秒）：

```text
running resume demo (single file checkpoint)
{
  "interrupt_at": 10,
  "total_steps": 24,
  "max_loss_diff_after_resume": 0.0,
  "sharded": false
}
running resume demo (sharded checkpoint)
{
  "interrupt_at": 10,
  "total_steps": 24,
  "max_loss_diff_after_resume": 0.0,
  "sharded": true
}
wrote .../outputs/resume-demo.json
```

写出的摘要与仓库中的 `outputs/resume-demo.json` 内容完全一致（两种模式 `max_loss_diff_after_resume` 都是 0.0，`interrupt_at=10`、`total_steps=24`、`num_shards=3`）。

逐项解读：

- **最大差 0.0（位级一致）**：CPU 上的计算是确定的，恢复后模型、优化器、调度器、数据位置都与不中断时相同，后续每一步的浮点运算完全一样。讲义说"the difference is zero or floating-point noise"，这里是严格的 0。
- **checkpoint 位于 epoch 边界**：默认 `interrupt_at=10` 是 `batches_per_epoch=5` 的倍数，保存时 `batch_in_epoch=0`。`--interrupt-at 7` 时保存状态为 `(7, 1, 2)`，最大差同样是 0.0。
- **loss 在 `ln 4 ≈ 1.386` 附近**：实测前三步 `1.4032, 1.4053, 1.3475`，标签随机、无规律可学（与第 46 节相同）。这不影响本节结论：我们只关心两条轨迹是否一致。

**补充消融实验**（`interrupt_at=7`，单文件模式，恢复时有意漏掉一类状态）：

| 恢复时漏掉 | 中断后 loss 最大差 | 说明 |
|----------|------------------|------|
| 无（完整恢复） | 0.0 | 基线 |
| RNG 状态 | 0.0 | 本 demo 没有任何东西消费全局 RNG |
| 优化器状态 | 0.0634 | AdamW 矩估计重新开始 |
| 调度器状态 | 0.0551 | 学习率跳回 0.01 |
| RNG 状态（模型加 `Dropout(0.2)`） | 0.0611 | 有了 Dropout，RNG 才变得必要 |

**分片文件大小**（3 个分片，AdamW 走过 1 步后保存）：`model.shard-000.pt` 4,549 B、`001` 3,717 B、`002` 2,629 B、`meta.pt` 33,477 B、`index.json` 720 B；同状态的单文件 `ckpt.pt` 为 39,145 B。

测试运行结果见第 9 节（9 个测试全部通过）。

---

## 7. 动手改一改

1. **让 RNG 恢复变得必要**：给 `make_model` 加 `nn.Dropout(0.2)`，确认完整恢复时差为 0、把 `restore_rng_state` 换成空操作时差明显大于 0；把这个负面检查写成测试。
2. **真正测试 epoch 中间恢复**：把默认 `--interrupt-at` 改为 7，并在 `run_resume_demo` 返回值中加入 `loaded.batch_in_epoch`，在测试里断言它大于 0。
3. **讲义练习 2**：实现"保留最近 K 个 + `latest.json` 指针"的滚动保存（参考测验 Q12），注意先写新文件、再更新指针、最后删除旧文件。
4. **讲义练习 4**：写 `scan_checkpoints(dir)`，对目录下所有 checkpoint 做加载/哈希校验，返回 `{文件名: "ok" | 错误原因}`，并清理孤儿 `.tmp`。
5. **讲义练习 5**：实现 `migrate_v1_to_v2` 与按版本精确分派的 `load_checkpoint`，为旧版本 payload 写回归测试。
6. **持久化与按大小分片（进阶）**：给 `atomic_save` 加文件与目录 `fsync`；把 `shard_keys_by_prefix` 改成"按张量字节数贪心分配到当前最小的分片"，并把优化器状态也按同样的键分片。

---

## 8. 常见坑

- **只存 `model.state_dict()`**：优化器与调度器状态丢失，恢复后 loss 偏离（本节实测 0.06 量级）。
- **只存种子不存 RNG 状态**：恢复后从种子起点重新开始，Dropout 掩码、数据打乱与中断前不同。
- **临时文件放在 `/tmp`**：跨文件系统时 `os.replace` 报错或不再原子。
- **认为 rename 原子就等于断电安全**：还需要 fsync 文件与目录。
- **`torch.load` 不加 `weights_only=True`**：加载来路不明的文件等于执行它的代码。
- **在 checkpoint 中存 NumPy 数组或自定义对象**：weights-only 加载会拒绝，需要先转成列表或张量。
- **恢复时模型结构或参数注册顺序变了**：优化器 state_dict 按参数序号对应，会错位或报错。
- **只在 epoch 边界测试恢复**：快进逻辑的 bug 不会暴露（本节默认参数和名为"mid_epoch"的测试都落在边界上）。
- **schema 只做前缀匹配**：其他格式或未来版本会被错误地当作 v1 加载。
- **直接运行脚本覆盖了仓库产物**：`main` 无条件写 `outputs/resume-demo.json`。

---

## 9. 测试在验证什么

`test_main.py` 用 `sys.path.insert(0, str(HERE))` 后 `import main as ckpt`；辅助函数 `_build_components` 构造 `8 → 12 → 4` 的模型和配套优化器、调度器；`_ArbitraryObject` 是一个空类，用来制造"不在白名单里的对象"。所有测试都在临时目录中进行，不会写仓库文件。

运行方式（均已实际运行）：

```bash
cd code && python3 -m pytest -q test_main.py      # 9 passed
cd code && python3 -m unittest test_main -v       # Ran 9 tests ... OK
```

| 测试类 | 测试 | 验证的性质 |
|-------|------|----------|
| `AtomicSaveTests` | `test_atomic_save_creates_no_partial_file` | 保存后目标存在，同目录没有遗留 `.tmp` 文件（只覆盖成功路径） |
| | `test_atomic_write_json_round_trip` | JSON 原子写入后可读回，`n == 7` |
| `CheckpointResumeTests` | `test_single_file_round_trip_matches_state` | 种子 0 的模型保存后，种子 99 的新模型（先断言参数全不同）加载后参数全部相同，step/epoch/batch_in_epoch/losses 一致 |
| | `test_mid_epoch_resume_continues_deterministically` | `total=14, interrupt=5, seed=3` 时中断后 loss 最大差 < 1e-5 |
| | `test_load_refuses_pickled_objects` | 含自定义类实例的 payload 在加载时抛 `pickle.UnpicklingError`——weights-only 生效 |
| `ShardedCheckpointTests` | `test_sharded_round_trip` | 分片模式 `total=12, interrupt=4` 时差 < 1e-5，index 中分片数为 3 |
| | `test_sha_mismatch_is_detected` | 在分片末尾追加一个 `\x00` 字节后加载抛 `ValueError` |
| | `test_shard_path_outside_checkpoint_dir_is_rejected` | 把 meta 中分片路径改成 `../outside.pt` 并**重算** meta 哈希写回 index，加载仍抛 `ValueError`——路径约束独立于哈希起作用 |
| `ShardLayoutTests` | `test_shard_layout_is_round_robin_and_complete` | 所有键恰好出现一次，各分片键数相差不超过 1 |

值得注意的测试缺口：

- `test_mid_epoch_resume_continues_deterministically` **名不副实**：`interrupt_at=5`、每 epoch 5 个 batch，保存时 `batch_in_epoch = 0`（已实测），测的是 epoch 边界。真正覆盖 epoch 中间恢复的只有分片测试（`interrupt_at=4`）。
- 没有任何测试能区分"恢复了 RNG"与"没恢复 RNG"——demo 不消费全局 RNG，删掉 `restore_rng_state` 所有测试照样通过。
- 没有测试"漏存优化器/调度器会导致偏离"的负面情形。
- 原子性只测了成功路径；没有模拟 `torch.save` 中途抛异常时旧文件保持不变、临时文件被清理。
- 没有测试 schema 检查拒绝未知版本（当前实现会接受 `ckpt-shard.v1` 等）。
