# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 80 节 分片 Checkpoint 与原子恢复 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下；测试：在小节根目录运行 `python3 -m pytest -q tests` 或 `python3 tests/test_checkpoint.py`） ｜ **依赖**：`torch`（第三方，仅用 CPU 张量与 `torch.save/load`）；其余为标准库 `hashlib`、`json`、`os`、`shutil`、`tempfile`、`dataclasses`、`pathlib`

---

## 1. 这份代码在考察什么

这份代码把讲义的"分片 checkpoint + manifest + 原子写 + 加载校验 + 轮转"做成一个可运行的最小实现，用 4 个模拟 rank 的状态演示：

1. **分片保存**：每个 rank 的状态（参数分片 + Adam 的 m、v 分片 + step）序列化成独立的 `rankN.bin`。
2. **Manifest 作为合同**：`ShardManifest` 记录 `world_size`、`step`、`schema_version`，以及每个分片的 `rank / path / sha256 / offset / numel`。
3. **原子写**：写 `*.tmp` → `flush` → `fsync` → `os.replace`，manifest 最后 rename，再 fsync 目录。
4. **防御性加载**：先校验 manifest（world size、schema、分片数），再逐个分片校验 rank 范围、重复、路径安全、存在性、sha256，最后才反序列化。
5. **轮转**：只保留最近 K 个 `step_*` 目录。
6. **失败模式演示**：错误的 world size、被篡改的分片都被大声拒绝。

> 一句话：**checkpoint 的价值不在"能存"，而在"坏的绝不会被当成好的读回来"**。同时要看清本实现的几处简化（顺序写而非并行写、offset 不校验、轮转按 mtime 且不识别未完成目录、`weights_only=False`），它们正是工程面试会追问的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SCHEMA_VERSION` / `MANIFEST_NAME` | 常量 | schema 版本号 1；清单文件名 `manifest.json` | schema 演进 |
| `ShardEntry` | dataclass | 单个分片的元数据：rank、文件名、sha256、offset、numel | manifest 条目 |
| `ShardManifest` | dataclass | 整个 checkpoint 的元数据，`to_json` / `from_json` 序列化 | manifest |
| `CheckpointError` | 异常类 | 所有校验失败统一抛它 | 大声失败（fail loudly） |
| `_sha256_bytes` | 函数 | 计算字节串的 sha256 十六进制摘要 | 完整性校验 |
| `_fsync_dir` | 函数 | fsync 目录，让 rename 的元数据落盘；不支持时静默跳过 | 崩溃一致性 |
| `_serialize_state` / `_deserialize_state` | 函数 | 用 `torch.save` / `torch.load` 在内存中序列化 | 分片格式 |
| `save_sharded` | 函数 | 逐 rank 写 tmp + fsync，生成 manifest，最后统一 rename | 分片保存 + 原子写 |
| `load_sharded` | 函数 | 校验 manifest 与每个分片后返回 `(manifest, per_rank)` | 防御性恢复 |
| `rotate_checkpoints` | 函数 | 按 mtime 排序，删除最旧的目录，只留 `keep_last` 个 | 轮转 |
| `make_demo_state` | 函数 | 构造一个 rank 的示例状态（1024 维参数 + m + v） | ZeRO 分片形状 |
| `main` | 函数 | 保存 → 恢复 → 两个失败模式 → 轮转演示 | 端到端 demo |

数据流：`make_demo_state × 4` → `save_sharded`（写 `rank*.bin.tmp`、`manifest.json.tmp` → rename）→ `load_sharded`（校验 → 反序列化）→ `torch.equal` 比对 → 故障注入（world_size=8、篡改 `rank0.bin`）→ 写 8 个目录 → `rotate_checkpoints`。

---

## 3. 逐段精讲

### 3.1 Manifest 的数据结构

```python
@dataclass
class ShardEntry:
    rank: int
    path: str
    sha256: str
    param_shard_offset: int
    param_shard_numel: int


@dataclass
class ShardManifest:
    world_size: int
    step: int
    wall_clock_seconds: float
    shards: list
    schema_version: int = SCHEMA_VERSION
```

- 与讲义的 schema 一一对应。讲义指出三个"承重"字段：`world_size`（换规模时大声失败）、`sha256`（抓部分写）、`offset/numel`（在扁平参数张量中定位）。
- `schema_version` 有默认值，所以必须放在没有默认值的字段之后（dataclass 的规则）。它让将来修改格式时，旧加载器能识别"这不是我认识的格式"而不是瞎读。
- `shards: list` 只写了 `list`，没有写成 `list[ShardEntry]`；不影响运行，但类型信息更弱。

```python
    def to_json(self) -> str:
        return json.dumps({
            "world_size": self.world_size,
            ...
            "shards": [asdict(s) for s in self.shards],
        }, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "ShardManifest":
        data = json.loads(text)
        return cls(
            world_size=int(data["world_size"]),
            ...
            shards=[ShardEntry(**s) for s in data["shards"]],
        )
```

- `asdict` 把嵌套 dataclass 递归转成 dict；`sort_keys=True` 让同样内容的 manifest 每次输出完全一致，便于 diff 和人工审阅。
- `from_json` 用 `int(...)`、`float(...)` 显式转换，`ShardEntry(**s)` 用字典解包构造条目：如果 JSON 里多了或少了字段，会直接 `TypeError`，这也是一种 schema 校验。
- `@classmethod` 是"另一种构造函数"的惯用写法：`ShardManifest.from_json(text)`。

### 3.2 工具函数：哈希、目录 fsync、序列化

```python
def _fsync_dir(path: Path) -> None:
    """Fsync a directory so rename metadata reaches disk; no-op where unsupported."""
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
```

- rename 改的是**目录项**；只 fsync 文件不能保证 rename 本身在掉电后保留，需要对目录也 fsync。Linux 上可以 `open(dir, O_RDONLY)` 后 `fsync`；Windows 不支持打开目录，因此用 `try/except` 静默降级。
- `finally` 保证文件描述符一定被关闭。

```python
def _serialize_state(state: dict) -> bytes:
    """Serialize a state dict deterministically using torch.save with pickle 4."""
    import io
    buf = io.BytesIO()
    torch.save(state, buf, pickle_protocol=4)
    return buf.getvalue()


def _deserialize_state(data: bytes) -> dict:
    import io
    buf = io.BytesIO(data)
    return torch.load(buf, weights_only=False)
```

- 先在内存里序列化成 `bytes`，这样**写盘的字节和计算 sha256 的字节是同一份**，哈希天然一致。我们实测同一 state 连续序列化两次字节完全相同，但代码并不依赖这一点。
- ⚠️ `pickle_protocol=4` 与 `weights_only=False` 是绑在一起的：实测在 PyTorch 2.14.1 上，protocol 4 的文件用 `weights_only=True` 加载会报 `UnpicklingError ... Unsupported operand 149`（protocol 4 的 FRAME 指令），而默认协议保存的同一 state 可以用 `weights_only=True` 加载。`weights_only=False` 意味着完整的 pickle，**加载不可信 checkpoint 可执行任意代码**；sha256 和分片放在同一目录，不能证明来源可信。生产中更安全的选择是 `weights_only=True`（去掉 `pickle_protocol=4`）或 safetensors 这类不含代码的格式。
- `import io` 写在函数内部，是局部导入；放到文件顶部更常规。

### 3.3 `save_sharded`：逐 rank 写 tmp

```python
    for rank, state in enumerate(per_rank_state):
        payload = _serialize_state(state)
        sha = _sha256_bytes(payload)
        final_name = f"rank{rank}.bin"
        tmp_name = f"rank{rank}.bin.tmp"
        tmp_path = dest / tmp_name
        with open(tmp_path, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        tmp_paths.append((tmp_path, dest / final_name))
        param_shard = state.get("param_shard")
        numel = param_shard.numel() if isinstance(param_shard, torch.Tensor) else 0
        shards.append(ShardEntry(
            rank=rank,
            path=final_name,
            sha256=sha,
            param_shard_offset=offset,
            param_shard_numel=numel,
        ))
        offset += numel
```

- `f.flush()` 把 Python 的用户态缓冲交给操作系统；`os.fsync(fd)` 要求操作系统把页缓存刷到磁盘。两步缺一不可。
- `offset` 是前面所有分片 `numel` 的**累加和**：4 个 rank 各 1024 元素，offset 依次为 0、1024、2048、3072。
- 如果某个 rank 的状态里没有 `param_shard`，numel 记为 0，不报错——这是一个宽松的选择。
- ⚠️ **这里是单进程顺序写 4 个分片**，并不是讲义强调的"每个 rank 并行写自己的文件"。在真实分布式中，`save_sharded` 应由每个 rank 各自调用来写自己的分片，再由 rank 0 收集各分片的 sha256/numel（一次小的 gather）写 manifest，最后 barrier。81 节则走了另一条路：把所有状态 all_gather 到 rank 0 再写（见 81 节讲解）。

### 3.4 `save_sharded`：写 manifest 并提交

```python
    manifest_tmp = dest / (MANIFEST_NAME + ".tmp")
    manifest_final = dest / MANIFEST_NAME
    with open(manifest_tmp, "w") as f:
        f.write(manifest.to_json())
        f.flush()
        os.fsync(f.fileno())
    for tmp, final in tmp_paths:
        os.replace(tmp, final)
    os.replace(manifest_tmp, manifest_final)
    _fsync_dir(dest)
    return manifest
```

- 顺序是：所有分片 tmp 落盘 → manifest tmp 落盘 → 分片 rename → **manifest 最后 rename** → fsync 目录。
- `os.replace` 在目标已存在时会原子替换（`os.rename` 在 Windows 上目标存在会失败，所以用 `replace` 更可移植）。必须在同一文件系统内，否则抛 `OSError`（EXDEV）。
- 对于**新目录**：manifest 出现就意味着所有分片都已 rename——manifest 是唯一的提交点；崩溃时这个目录没有 manifest，`load_sharded` 会报 `manifest missing`，上一个目录的 checkpoint 不受影响。
- ⚠️ 模块 docstring 说"a single rename moves everything"，实际是 **N+1 次独立 rename**。如果向**已存在 checkpoint 的同一目录**重写，并在中途崩溃，就会留下新旧混合的分片。我们用 monkeypatch 让第 3 次 `os.replace` 抛错实测：目录剩下 `manifest.json, manifest.json.tmp, rank0.bin, rank1.bin, rank2.bin, rank2.bin.tmp, rank3.bin, rank3.bin.tmp`，`load_sharded` 报 `sha256 mismatch on rank 0`。sha256 拦住了静默损坏，但旧 checkpoint 也已经不可用。修复：每次保存都写新目录，或先写到 `step_XXXX.tmp/` 再整体 rename 目录，或原子更新 `latest` 指针（测验 Q9）。

### 3.5 `load_sharded`：先验合同，再碰状态

```python
    manifest = ShardManifest.from_json(manifest_path.read_text())
    if manifest.world_size != expected_world_size:
        raise CheckpointError(...)
    if manifest.schema_version != SCHEMA_VERSION:
        raise CheckpointError(...)
    if len(manifest.shards) != manifest.world_size:
        raise CheckpointError(...)
```

- 三道"全局"检查都在读任何分片之前完成。world size 不符时，实际报错 `world_size mismatch: manifest=4, expected=8`。
- 分片数检查防的是"manifest 自身不完整"（例如被截断后手工修补过的 JSON）。

```python
    for shard in manifest.shards:
        if not (0 <= shard.rank < manifest.world_size):
            raise CheckpointError(...)
        if shard.rank in seen_ranks:
            raise CheckpointError(f"duplicate shard for rank {shard.rank}")
        seen_ranks.add(shard.rank)
        if os.path.isabs(shard.path) or os.sep in shard.path or "/" in shard.path or shard.path in ("", ".", ".."):
            raise CheckpointError(f"unsafe shard path: {shard.path!r}")
        shard_path = (src / shard.path).resolve()
        try:
            shard_path.relative_to(src_resolved)
        except ValueError as exc:
            raise CheckpointError(f"shard path escapes checkpoint dir: {shard.path!r}") from exc
        if not shard_path.exists():
            raise CheckpointError(f"shard file missing: {shard_path}")
        payload = shard_path.read_bytes()
        actual = _sha256_bytes(payload)
        if actual != shard.sha256:
            raise CheckpointError(...)
        per_rank[shard.rank] = _deserialize_state(payload)
```

- **rank 范围与重复检查**：保证 `per_rank` 的每个位置恰好被填一次。
- **路径安全**：拒绝绝对路径、含分隔符的路径、`.`/`..`；再用 `resolve()` + `relative_to()` 双保险，防止 manifest 被构造成 `../../etc/...` 让加载器读到目录外的文件（路径穿越）。`raise ... from exc` 保留原始异常链。
- **存在性**：对应讲义的"shard count mismatch"失败模式。实测删掉 `rank3.bin` 后报 `shard file missing: .../rank3.bin`。
- **sha256**：对应"partial write"。实测把 `rank1.bin` 截掉一半，报 `sha256 mismatch on rank 1: recorded=0dd605637003..., actual=391ffbde21ce...`。
- 循环后的 `if len(seen_ranks) != manifest.world_size` 在前面"分片数 == world_size + 无重复 + 范围合法"都成立时其实不可能触发，属于防御性冗余。
- ⚠️ `param_shard_offset / numel` 从未被校验或使用。实测把 rank 1 的 offset 改成 999999、rank 2 的 numel 改成 7，加载照样成功。讲义说它们用于"在正确位置重建扁平参数张量"，但这只在跨 world size 重分片（讲义练习 4、测验 Q11）时才会用到。

### 3.6 `rotate_checkpoints`：保留最近 K 个

```python
    children = sorted(
        [c for c in parent.iterdir() if c.is_dir() and c.name.startswith("step_")],
        key=lambda c: (c.stat().st_mtime, c.name),
    )
    if keep_last == 0:
        to_delete = children
    elif len(children) > keep_last:
        to_delete = children[:-keep_last]
    else:
        to_delete = []
```

- 以 `(mtime, name)` 为排序键：先按目录修改时间，mtime 相同（粗粒度时间戳的文件系统）时再按名字。
- `keep_last == 0` 单独处理，因为 `children[:-0]` 等于 `children[:0]`，是空列表——这是 Python 切片的一个经典陷阱。
- ⚠️ 三个问题：
  1. **按 mtime 而不是 step**：demo 中 `step_0100` 最先创建，所以第一个被删（见第 6 节）。
  2. **不识别未完成的目录**：实测 3 个完整 checkpoint + 1 个崩溃留下的空 `step_0003`，`keep_last=1` 会删掉全部完整 checkpoint、只留空目录。
  3. `rmtree(..., ignore_errors=True)` 删除失败也会记入 `deleted`。
- 修复思路：只统计含 manifest 的目录、按 manifest 里的 step 排序、在新 checkpoint 成功提交之后再删（测验 Q10 有已验证的实现）。讲义说"the next save deletes the oldest first"，先删再存能释放磁盘，但新保存失败时就只剩 K−1 个。

### 3.7 `make_demo_state` 与 `main`

```python
def make_demo_state(rank: int, world_size: int) -> dict:
    torch.manual_seed(31 + rank)
    return {
        "rank": rank,
        "world_size": world_size,
        "param_shard": torch.randn(1024) + rank,
        "m_shard": torch.zeros(1024),
        "v_shard": torch.ones(1024) * 1e-6,
        "step": 100,
    }
```

- 模拟 ZeRO-1 的一个 rank：1024 个参数 + 同样大小的 Adam 一阶矩 m、二阶矩 v。每个 rank 用不同种子并加上 `rank` 偏移，保证分片内容各不相同（sha256 也就各不相同）。
- 讲义学习目标提到"fp16 parameters"，这里全是 fp32。

`main()` 依次执行：保存 `step_0100` → 加载并用 `torch.equal` 比对 → `expected_world_size=8` 故障 → 在 `rank0.bin` 末尾追加 `b"corruption"` 再加载 → 恢复原文件 → 写 `step_0000`～`step_0007` → `rotate_checkpoints(keep_last=5)` → 删除整个临时目录。

- ⚠️ round-trip 只比较了 `param_shard`；讲义目标是"verifying byte-equal state for both fp16 parameters and the ZeRO optimiser state"，m、v 没有比较。我们额外检查了全部键（含 m、v、标量），确实全部相等。
- `tempfile.mkdtemp(prefix="aie_ckpt_")` 在系统临时目录建一个唯一目录，最后 `shutil.rmtree` 清理。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 每 rank 一个文件 | 无写入竞争，可利用并行文件系统条带化 | 文件数多、与并行布局绑定；本 demo 实际是单进程顺序写，生产由各 rank 并行写 |
| 先在内存序列化再写盘 | 哈希与写盘内容是同一份字节 | 需要额外一份内存；大分片可边写边增量计算哈希 |
| tmp + fsync + replace + fsync 目录 | 崩溃时不出现"正式名下的半截文件" | 多次 fsync 有延迟；生产常配合异步写 |
| manifest 最后 rename | 给新目录一个单一提交点 | 对同一目录重写时不是原子的；生产用新目录 + `latest` 指针 |
| sha256 | 抓截断、位翻转、新旧混合 | 要完整读文件、算得慢；高频场景用 CRC（讲义练习 3）；不防恶意篡改 |
| 先校验全局字段再读分片 | 尽早失败，不浪费 IO，不碰坏状态 | — |
| 路径白名单 + `relative_to` | 防路径穿越 | 不支持子目录布局（生产格式可能需要） |
| `torch.save` + protocol 4 + `weights_only=False` | 能存任意 Python 对象 | 存在反序列化执行代码的风险；生产可用 `weights_only=True` 或 safetensors |
| offset/numel 只记录 | 为重分片预留信息 | 当前不校验，形同虚设；应在加载或重分片时验证铺满 `[0, total)` |
| 按 mtime 轮转 | 实现简单 | 可能删错、会把未完成目录算进名额；应按 manifest 中的 step 且只计完整 checkpoint |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可在类里写 `-> "ShardManifest"` 等前向引用 |
| `@dataclass` 与默认字段 | `schema_version: int = SCHEMA_VERSION` | 自动生成 `__init__`；有默认值的字段必须排在后面 |
| `dataclasses.asdict` | `asdict(s) for s in self.shards` | 把 dataclass 递归转成 dict，便于 JSON 序列化 |
| `@classmethod` | `def from_json(cls, text)` | 第一个参数是类本身，常用来写"替代构造函数" |
| 字典解包 `**` | `ShardEntry(**s)` | 把 dict 的键值作为关键字参数传入 |
| 自定义异常 | `class CheckpointError(Exception)` | 让调用方可以只捕获这一类错误 |
| `raise ... from exc` | `raise CheckpointError(...) from exc` | 保留"由哪个异常引起"的异常链 |
| `try / except / finally` | `_fsync_dir` | `finally` 无论是否异常都会执行，用来释放资源 |
| `with open(...) as f` | `with open(tmp_path, "wb") as f:` | 上下文管理器，离开代码块自动关闭文件 |
| `pathlib.Path` 与 `/` | `dest / tmp_name`、`.resolve()`、`.relative_to()` | 面向对象的路径操作，`/` 拼接路径 |
| `enumerate` | `for rank, state in enumerate(per_rank_state)` | 同时拿到下标和元素 |
| 条件表达式 | `numel = x.numel() if isinstance(x, torch.Tensor) else 0` | 一行内的 if/else |
| f-string 与 `!r` | `f"unsafe shard path: {shard.path!r}"`、`{entry.sha256[:12]}` | `!r` 用 `repr()` 显示（带引号）；可在花括号内切片 |
| f-string 格式符 | `f"step_{s:04d}"` | 宽度 4、不足补 0，得到 `step_0007` |
| 链式比较 | `0 <= shard.rank < manifest.world_size` | 等价于两个比较用 `and` 连接 |
| 集合 | `seen_ranks = set()`、`set(range(n)) - seen_ranks` | 去重、差集 |
| 切片陷阱 | `children[:-keep_last]` 与 `keep_last == 0` 的特判 | `x[:-0]` 是空列表 |
| `lambda` 作为排序键 | `key=lambda c: (c.stat().st_mtime, c.name)` | 元组比较：先比第一项，相同再比第二项 |
| `io.BytesIO` | `_serialize_state` | 内存中的"文件"，可传给 `torch.save/load` |
| `raise SystemExit(main())` | 文件末尾 | 用 `main()` 的返回值作为进程退出码 |

---

## 6. 运行结果解读

实际运行（Python 3.13 + PyTorch 2.14.1 CPU，`cd code && python3 main.py`，不到 1 秒）：

```text
workdir: /tmp/aie_ckpt_f69x_2gx
saving sharded checkpoint...
manifest: world_size=4, step=100, shards=4
  rank 0: rank0.bin sha256=194bfd3c6653... numel=1024
  rank 1: rank1.bin sha256=0dd605637003... numel=1024
  rank 2: rank2.bin sha256=106f0b7741a2... numel=1024
  rank 3: rank3.bin sha256=ae92515ac857... numel=1024

resuming...
byte-equal round-trip verified for every rank

testing failure mode: wrong world size...
  rejected as expected: world_size mismatch: manifest=4, expected=8

testing failure mode: tampered shard...
  rejected as expected: sha256 mismatch on rank 0: recorded=194bfd3c6653..., actual=712d93275d12...

testing rotation: write 8 checkpoints, keep 5...
  rotated 4 oldest: ['step_0100', 'step_0000', 'step_0001', 'step_0002']
```

逐项解读：

- **4 个分片**：每个 `rank*.bin` 实测 14,241 字节，其中张量数据 `3 × 1024 × 4 = 12,288` 字节，其余约 1.9 KB 是 `torch.save` 的 zip 容器和 pickle 结构开销；manifest 为 929 字节。由于种子固定，sha256 前缀每次运行都相同。
- **offset**：manifest 中依次为 0、1024、2048、3072。
- **round-trip**：`torch.equal` 逐元素比较 `param_shard`，形状、dtype、数值全部相同才为 True。
- **world size 错误**：在读任何分片之前就被拒绝。
- **篡改分片**：在文件尾追加 10 个字节，哈希完全改变（`712d93275d12...`），加载被拒绝。演示结束后用备份把文件写回。
- **轮转**：标题说"write 8, keep 5"，但删了 4 个——因为目录里还有最早写的 `step_0100`，共 9 个。按 mtime 排序时 `step_0100` 最旧，于是被第一个删除，尽管它的训练步数最大。剩下的是 `step_0003`～`step_0007`。在真实训练中目录按时间顺序产生，mtime 与 step 通常一致；但一旦有人复制/恢复目录，或在同一目录重写，这种排序就会出错。
- 运行结束后整个 workdir 被删除，不留文件。

---

## 7. 动手改一改

1. **补全 round-trip 校验**：把 `main` 中的比较扩展到状态字典的所有键（张量用 `torch.equal`，标量用 `==`），对应讲义"同时验证参数和 ZeRO 优化器状态"的目标。
2. **校验 offset/numel**：在 `load_sharded` 中加入"按 offset 排序后无缝铺满 `[0, total)`、numel 与实际 `param_shard.numel()` 一致"的检查，并写一个篡改 offset 的测试用例。
3. **修复轮转**（讲义练习 2）：只统计含 `manifest.json` 的目录、按 manifest 里的 `step` 排序、在新 checkpoint 提交成功后再删旧的。用"3 个完整 + 1 个空目录"的场景验证。
4. **目录级提交**：改成先写到 `step_XXXX.tmp/`，全部 fsync 后 `os.replace` 整个目录，再 fsync 父目录；并增加一个原子更新的 `latest` 文件。用 monkeypatch `os.replace` 在中途抛异常，验证上一个 checkpoint 依旧可加载。
5. **跨 world size 重分片**（讲义练习 4）：实现 `reshard(src_dir, 4, 8)`，参考测验 Q11 的已验证实现。
6. **异步保存 + 两级存储**（讲义练习 1、5）：用 `threading.Thread` 在后台调用 `save_sharded`，下一次保存前 `join` 上一次；保存完成后再复制到第二个目录（模拟 S3），写一个记录远端路径的 upload manifest。

---

## 8. 常见坑

- **以为 `flush()` 就落盘了**：`flush` 只清空 Python 缓冲，必须 `os.fsync` 才要求操作系统写盘；rename 之后还要 fsync 目录。
- **tmp 文件放在别的文件系统**（例如 `/tmp` 与数据盘不同）：`os.replace` 会直接报 `Invalid cross-device link`，原子性也无从谈起。
- **把 N 次 rename 当成一次原子操作**：多文件 checkpoint 需要一个单一提交点（最后写的 manifest、目录 rename 或 `latest` 指针）。
- **把 sha256 当成安全机制**：它只做完整性校验；与 manifest 同处一地，挡不住有意篡改。配合 `weights_only=False` 加载不可信文件尤其危险。
- **world size 不符就"凑合加载"**：静默把 4 份分片当 8 份用，损坏会在几百步之后以 NaN 的形式出现；必须大声失败并走显式的重分片流程。
- **轮转按 mtime 且不识别未完成目录**：可能删掉唯一可用的 checkpoint。
- **只验证参数、不验证优化器状态与 RNG**：恢复后 loss 曲线出现跳变，往往是 m/v、step count、学习率调度器或数据加载器位置没恢复。
- **`keep_last=0` 用切片 `[:-0]`**：得到空列表，什么也不删，本节代码专门特判了这个情况。

---

## 9. 测试在验证什么

测试文件位于小节根目录的 `tests/test_checkpoint.py`，用 `sys.path.insert` 把 `code/` 加入导入路径。运行：`python3 -m pytest -q tests`（实测 `7 passed in 1.47s`）或 `python3 tests/test_checkpoint.py`（`Ran 7 tests ... OK`）。每个测试在 `setUp` 中建临时目录、`tearDown` 中删除。

| 测试 | 验证的性质 | 说明 |
|------|-----------|------|
| `test_round_trip_is_byte_equal` | 保存后加载，每个 rank 的 `param_shard` 完全相等 | 只比较参数分片，不比较 m/v |
| `test_wrong_world_size_rejected` | 以 8 加载 4-rank checkpoint 抛 `CheckpointError`，消息含 `world_size mismatch` | 失败模式 1 |
| `test_sha256_catches_tamper` | 在 `rank2.bin` 末尾追加 1 字节后加载，消息含 `sha256 mismatch` | 失败模式 3（部分写/篡改） |
| `test_atomic_write_leaves_no_tmp_files` | 正常保存后目录中没有 `.tmp` 文件 | 只验证"成功路径会清理 tmp"，并不模拟崩溃，不能证明原子性 |
| `test_manifest_json_roundtrip` | `from_json(to_json(m))` 保留 world_size、step、wall_clock、分片数 | 序列化往返；没有比较每个分片的字段 |
| `test_rotation_keeps_last_k` | 写 7 个目录、keep 3，删 4 个，剩 `step_0004`～`step_0006` | 目录按顺序创建，mtime 与 step 一致，所以测不出 mtime 排序的问题 |
| `test_missing_manifest_raises` | 对没有 manifest 的目录加载抛 `CheckpointError` | 对应"崩溃在 manifest rename 之前"的情形 |

测试没有覆盖的：失败模式 2（分片文件缺失）、路径穿越、重复 rank、schema_version 不符、offset/numel 篡改、崩溃中途的原子性、未完成目录参与轮转。前几项可以照着现有测试的写法补上；原子性可以用 `unittest.mock.patch("main.os.replace", side_effect=...)` 在第 k 次调用时抛异常来模拟。
