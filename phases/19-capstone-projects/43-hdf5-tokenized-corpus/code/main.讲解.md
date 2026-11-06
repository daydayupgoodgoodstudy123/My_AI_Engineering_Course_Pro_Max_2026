# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 43 节 HDF5 格式的分词语料 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（约 0.25 秒，全部在临时目录中完成，运行后不留文件）；测试：`python -m unittest discover tests -v` 或 `python -m pytest -q tests` ｜ **依赖**：`numpy`、`h5py`（第三方，`pip install h5py`；缺失时脚本以 `SystemExit` 给出安装提示）；`hashlib`、`json`、`random`、`tempfile`、`dataclasses`、`pathlib` 为标准库

> 本目录下的 `tests/__init__.py` 是一个 **0 字节空文件**，只用于把 `tests/` 标记为 Python 包，便于 `unittest discover`/pytest 导入；没有任何逻辑，故并入本讲解，不单独成篇。
>
> 本讲解的运行结果基于 h5py 3.16.0（内置 HDF5 2.0.0）与 NumPy 2.5.3。

---

## 1. 这份代码在考察什么

承接第 42 课的下载与去重，这份代码把文本语料变成训练器能"以线速读取"的形态：

1. **流式分词写入**：字节级 tokenizer 把每篇文档变成 token ID，写入一个可扩展（`maxshape=(None,)`）、分块（`chunks=(chunk_size,)`）的 HDF5 整数数据集；内存缓冲攒满一个 chunk 才 resize 一次。
2. **分片与索引**：每个输入分片输出一个 `.h5`，`shards.json` 记录每片的 token 数、文档数、sha256 与全局起点 `global_start`。
3. **跨分片随机读取**：`MmapTokenStore.get_slice(start, stop)` 把全局区间路由到各分片并拼接。
4. **滑动窗口 dataloader**：随机起点读 `window_size + 1` 个 token，构造右移一位的 `(input, target)`。
5. **完整性校验**：重算磁盘上 token 字节的 sha256，与索引比对。
6. **工程细节**：SWMR 读写模式、边界 token、`uint16` dtype、JSONL 适配器、文档打包函数。

> 一句话：**把"分词"从训练热路径上彻底移走——离线一次性写成带校验的扁平 token 流，训练时只剩"按偏移读整数"**。同时要注意本实现在异常收尾、打包边界、dtype 容量和"mmap"说法上的简化。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DEFAULT_CHUNK_SIZE` 等常量 | 模块常量 | chunk 8192、窗口 64、边界 ID 0、dtype `uint16` | 参数 |
| `ShardWriteResult` / `ShardIndexEntry` | dataclass | 单片写入结果 / 索引行（多一个 `global_start`） | 数据契约 |
| `Tokenizer` | 类 | 字节 + 1 偏移，0 保留为边界，词表 257 | 分词 |
| `HDF5ShardWriter` | 上下文管理器类 | 缓冲 → resize → 写入 → flush；退出时写属性 | 可扩展分块数据集 |
| `ShardedTokenizationPipeline` | 类 | 每片一个 writer，每篇文档后加边界；写 `shards.json` | 分片写 + 索引 |
| `MmapTokenStore` | 上下文管理器类 | SWMR 打开所有分片，`get_slice` 跨分片读取 | 随机读取 |
| `SlidingWindowDataloader` | 类（可迭代） | 随机窗口、构造 `(input, target)`、`take(n)` | 训练样本 |
| `JSONLSource` | 类（可迭代） | 从 JSONL 读取 `text` 字段，统计丢弃行 | 输入适配 |
| `pack_documents` | 生成器函数 | 把文档打包成定长组，组内用边界分隔 | packing（流水线未使用） |
| `tokenize_jsonl_path` | 函数 | JSONL → 单个 HDF5 分片的便捷封装 | 入口 |
| `load_index` / `validate_corpus` | 函数 | 读索引；重算 sha256 校验 | 校验 |
| `build_demo_corpus` / `run_demo` | 函数 | 两片各 3 篇长文档 → 写入 → 校验 → 采样 10 个 batch | 演示 |

数据流：`build_demo_corpus` → `ShardedTokenizationPipeline.write_corpus`（逐片 `write_shard`：`Tokenizer.encode` → `HDF5ShardWriter.add_document/add_boundary` → 退出写属性）→ `shards.json` → `validate_corpus` → `MmapTokenStore(entries)` → `SlidingWindowDataloader.take(10)` → 打印形状与校验和。

---

## 3. 逐段精讲

### 3.1 常量、导入守卫与 dataclass

```python
try:
    import h5py
except ImportError as exc:
    raise SystemExit(
        "h5py is required for this lesson. Install with: pip install h5py"
    ) from exc

DEFAULT_CHUNK_SIZE = 8192
DEFAULT_WINDOW_SIZE = 64
BOUNDARY_TOKEN_ID = 0
TOKEN_DTYPE = np.uint16
```

- `uint16` 每个 token 占 2 字节，最大 65,535。本节词表只有 257，绰绰有余；但换成 128K 词表的 BPE 时必须改 `uint32`，否则写入时 NumPy 2.x 会抛 `OverflowError`（实测 `np.asarray([70000], dtype=np.uint16)`）。
- `ShardIndexEntry` 比 `ShardWriteResult` 多了 `global_start`，少了 `chunk_size`（chunk 大小放在索引的顶层）。两者都有 `to_dict()`（`asdict`）用于 JSON 序列化。

### 3.2 Tokenizer：字节偏移 1，空出 0

```python
    BOUNDARY_TOKEN = BOUNDARY_TOKEN_ID
    BYTE_OFFSET = 1

    def encode(self, text: str) -> list[int]:
        if not text:
            return []
        data = text.encode("utf-8")
        return [self.BYTE_OFFSET + b for b in data]

    def decode(self, ids: Iterable[int]) -> str:
        byte_ids = [int(i) - self.BYTE_OFFSET for i in ids if int(i) >= self.BYTE_OFFSET]
        return bytes(byte_ids).decode("utf-8", errors="replace")
```

- 字节值 0..255 映射为 1..256，0 专门留给边界 token，所以字节 `0x00` 不会与边界冲突（测试 `test_boundary_token_is_reserved`）。
- `decode` 丢弃所有 < 1 的 ID（即边界），再按 UTF-8 解码，非法字节显示为 `�`。
- `vocab_size = 257` 是实例属性，与讲义"接口是 `encode(text)` 和 `vocab_size`"一致，真实项目可以替换为 BPE（第 30 课）。
- ⚠️ docstring 写着 "boundary token (separator injected by the dataloader)"，讲义也说"the only token the dataloader injects"；但代码中边界是**写入端**（`ShardedTokenizationPipeline.write_shard` 调用 `add_boundary`）注入的，dataloader 只是随机切窗口，不注入任何 token。

### 3.3 HDF5ShardWriter：本节核心

**(1) 打开：创建可扩展分块数据集并进入 SWMR**

```python
    def __enter__(self) -> "HDF5ShardWriter":
        self._file = h5py.File(self.path, "w", libver="latest")
        self._dataset = self._file.create_dataset(
            self.dataset_name,
            shape=(0,),
            maxshape=(None,),
            chunks=(self.chunk_size,),
            dtype=TOKEN_DTYPE,
        )
        self._file.swmr_mode = True
        return self
```

- `shape=(0,)`：初始为空；`maxshape=(None,)`：第一维无上限，可无限 `resize`；可扩展数据集必须分块存储，`chunks=(chunk_size,)` 指定每块 `chunk_size` 个元素（demo 中 512 个 `uint16` = 1 KiB）。
- 严格按讲义的 SWMR 顺序：`libver="latest"` 打开 → 先建好数据集 → 再 `swmr_mode = True`。
- `__enter__` 返回 `self`，所以可以写 `with writer:` 或 `with HDF5ShardWriter(...) as w:`。

**(2) 追加：逐 token 进缓冲，满一个 chunk 就刷**

```python
    def add_document(self, token_ids: Iterable[int]) -> None:
        self._document_count += 1
        for token in token_ids:
            self._buffer.append(int(token))
            if len(self._buffer) >= self.chunk_size:
                self._flush_buffer(final=False)

    def add_boundary(self) -> None:
        self._buffer.append(BOUNDARY_TOKEN_ID)
        if len(self._buffer) >= self.chunk_size:
            self._flush_buffer(final=False)
```

- 缓冲是 Python 列表；每满 `chunk_size` 个就刷一次，所以除最后一次外，每次写入都恰好是一个完整 chunk、且与 chunk 边界对齐（讲义 "Every write is contiguous and chunk-aligned except the last one"）。
- 讲义说缓冲是"a NumPy array of length `chunk_size`"，代码用的是 Python 列表再 `np.asarray`，效果相同，但逐元素 `append` 在大语料上较慢；生产中会对整篇文档的 token 数组做切片写入。

**(3) 刷新：resize → 写入 → flush → 更新哈希**

```python
    def _flush_buffer(self, final: bool) -> None:
        ...
        size = len(self._buffer) if final else self.chunk_size
        chunk = np.asarray(self._buffer[:size], dtype=TOKEN_DTYPE)
        new_total = self._token_count + size
        self._dataset.resize((new_total,))
        self._dataset[self._token_count : new_total] = chunk
        self._dataset.flush()
        self._hasher.update(chunk.tobytes())
        self._token_count = new_total
        self._buffer = self._buffer[size:]
        if not final and len(self._buffer) >= self.chunk_size:
            self._flush_buffer(final=False)
```

- 每次 resize 的增量：非最终刷新为 `chunk_size`，最终刷新为剩余数量。因此数据集的**形状精确等于 token 数**，末尾没有补零（实测 `shape == (6456,)`，属性 `token_count = 6456`）。讲义"Without this the reader walks off the end into zero-padded tokens"所担心的情形在本实现中不会出现——`token_count` 属性与形状是冗余的，起到的是交叉校验作用。
- `self._dataset.flush()`：SWMR 下让读者看到新数据的必要步骤。
- sha256 是**增量**计算的：每写一块就 `update(chunk.tobytes())`，最终摘要等于整个 token 流的哈希，无需写完后再读一遍。
- `chunk.tobytes()` 使用本机字节序（x86 为小端，`1` → `b'\x01\x00'`）；在大端机器上同样的 token 会得到不同哈希。用显式的 `'<u2'` dtype 可以消除平台差异。
- 末尾的递归在当前用法下不会触发（`add_*` 一到 `chunk_size` 就刷新，缓冲不会超过一个 chunk），是防御性代码。

**(4) 退出：写属性、关闭文件**

```python
    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._dataset is not None and self._file is not None:
                if self._buffer:
                    self._flush_buffer(final=True)
                self._dataset.attrs["token_count"] = self._token_count
                self._dataset.attrs["document_count"] = self._document_count
                self._dataset.attrs["sha256"] = self._hasher.hexdigest()
        finally:
            if self._file is not None:
                self._file.close()
                ...
```

- `try/finally` 保证文件一定被关闭。`__exit__` 返回 `None`（假值），所以 `with` 块中的异常会继续向外传播。
- ⚠️ **不检查 `exc_type`**：即使 `with` 块因异常中断，也会照常刷缓冲、写属性。实测：文档源在第 1 篇后抛 `RuntimeError`，得到的 `x.h5` 形状 `(12,)`、`token_count = 12`、`document_count = 1`、`sha256` 正确——一个"自洽但残缺"的分片，任何校验都发现不了。应当在异常时不写属性并删除文件，或"写临时文件 + 成功后改名"。
- ⚠️ 属性是在 `swmr_mode = True` **之后**才写入的。HDF5 的 SWMR 模型要求进入 SWMR 写模式后不再改变文件结构；本次 HDF5 2.0.0 实测写属性没有报错，但这依赖具体版本行为，更稳妥的做法是在开启 SWMR 前就创建好属性（写入初值），关闭前只更新值。

### 3.4 ShardedTokenizationPipeline：每片一个文件 + 全局索引

```python
    def write_shard(self, shard_id: str, documents: Iterable[str]) -> ShardWriteResult:
        shard_path = self.output_dir / f"{shard_id}.h5"
        writer = HDF5ShardWriter(shard_path, chunk_size=self.chunk_size)
        with writer:
            for text in documents:
                writer.add_document(self.tokenizer.encode(text))
                writer.add_boundary()
        return writer.result(shard_id)
```

- **每篇文档之后**都加一个边界 token，包括最后一篇，所以每个分片都以 0 结尾；分片之间在全局流中天然有分隔。
- `writer.result()` 在 `with` 结束（文件已关闭）后调用，读取的是 writer 对象中保存的计数与哈希。

```python
    def write_corpus(self, shards: dict[str, Iterable[str]]) -> list[ShardIndexEntry]:
        running_offset = 0
        for shard_id, documents in shards.items():
            result = self.write_shard(shard_id, documents)
            entries.append(ShardIndexEntry(..., global_start=running_offset))
            running_offset += result.token_count
        ...
        index_path.write_text(json.dumps(body, sort_keys=True, indent=2), encoding="utf-8")
```

- `global_start` 是前面所有分片 token 数的前缀和；`total_tokens` 是总和。
- 分片按 `dict` 的插入顺序**串行**写入。讲义说"The pipeline writes shards in parallel"，代码并没有并行；不过每片独立、可以很容易地改成进程池，最后按固定顺序算 `global_start`。
- ⚠️ 索引中的 `path` 是 `str(self.output_dir / ...)`，demo 中是绝对临时路径（如 `/tmp/tmpi1k2xx_s/shard-0000.h5`），索引搬到别的目录或机器就失效；写相对路径更好。`shards.json` 也不是原子写。

### 3.5 MmapTokenStore：跨分片的 `get_slice`

```python
        try:
            for entry in shard_entries:
                self._files.append(h5py.File(entry.path, "r", swmr=True))
            self._datasets = [f["tokens"] for f in self._files]
        except Exception:
            for opened in self._files:
                ...close...
            raise
```

- 构造时打开全部分片；中途失败会关闭已打开的文件再重新抛出异常，避免句柄泄漏。
- 实现了 `__enter__`/`__exit__`，可以 `with MmapTokenStore(entries) as store:`。

```python
    def get_slice(self, start: int, stop: int) -> np.ndarray:
        ...
        out = np.empty((stop - start,), dtype=TOKEN_DTYPE)
        cursor = 0
        for entry, dataset in zip(self._entries, self._datasets):
            shard_start = entry.global_start
            shard_stop = shard_start + entry.token_count
            if stop <= shard_start:
                break
            if start >= shard_stop:
                continue
            local_start = max(0, start - shard_start)
            local_stop = min(entry.token_count, stop - shard_start)
            length = local_stop - local_start
            ...
            out[cursor : cursor + length] = dataset[local_start:local_stop]
            cursor += length
        if cursor != stop - start:
            raise RuntimeError(...)
        return out
```

以 demo 为例（两片各 6,456 个 token），请求全局 `[6400, 6465)`：

| 分片 | `shard_start..shard_stop` | `local_start..local_stop` | 长度 | 写入 `out` 的位置 |
|------|--------------------------|--------------------------|------|----------------|
| shard-0000 | 0..6456 | 6400..6456 | 56 | `out[0:56]` |
| shard-0001 | 6456..12912 | 0..9 | 9 | `out[56:65]` |

- 先做参数检查：负数、`stop < start`、越界都抛 `ValueError`；空切片直接返回空数组。
- 最后的 `cursor != stop - start` 检查能发现索引与文件不一致（例如分片缺失导致区间有洞）。
- 线性扫描所有分片，分片多时可以用 `bisect` 在 `global_start` 列表上二分定位。
- ⚠️ 名字叫 "Mmap"，但并不是内存映射：`dataset[a:b]` 由 HDF5 库按 chunk 读取并拷贝进新数组，再拷贝进 `out`。分块数据集没有单一连续偏移（实测 `dataset.id.get_offset()` 为 `None`），无法 `np.memmap`。讲义正文自己也写了"HDF5 copies the requested hyperslab ... into a freshly allocated NumPy array"。
- ⚠️ 使用的是**索引**中的 `token_count`，没有与文件属性或形状核对。

### 3.6 SlidingWindowDataloader：随机窗口与右移目标

```python
        self._random = random.Random(seed)
        self._max_start = store.total_tokens - window_size - 1

    def _sample_window(self) -> tuple[np.ndarray, np.ndarray]:
        start = self._random.randint(0, self._max_start)
        chunk = self.store.get_slice(start, start + self.window_size + 1)
        return chunk[:-1], chunk[1:]

    def __iter__(self) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        while True:
            inputs = np.empty((self.batch_size, self.window_size), dtype=TOKEN_DTYPE)
            targets = np.empty((self.batch_size, self.window_size), dtype=TOKEN_DTYPE)
            for row in range(self.batch_size):
                inputs[row], targets[row] = self._sample_window()
            yield inputs, targets
```

- 每个样本读 `window_size + 1 = 65` 个 token；`inputs` 是前 64 个，`targets` 是后 64 个——`targets[i]` 就是 `inputs[i]` 的下一个 token，正是 next-token prediction 的监督信号。
- `_max_start = 12912 − 65 = 12847`；`randint` 两端都包含，所以最后一个合法样本恰好读到流的末尾。
- 用独立的 `random.Random(seed)` 实例而不是全局 `random`，两个 loader 用相同 seed 会产生相同序列（测试 `test_dataloader_deterministic_with_seed`、讲义练习 2）。
- `__iter__` 是**无限生成器**（`while True`），由 `take(n)` 取有限个 batch。
- 这是"有放回的随机采样"：没有 epoch 概念，不保证覆盖每个 token，也没有可保存/恢复的采样器状态。
- 输出是 `uint16` 数组，送入 PyTorch embedding 前需要转成 `int64`（`torch.from_numpy(x.astype(np.int64))`）。
- 窗口可以跨文档（中间有边界 0）也可以跨分片——这正是讲义说的 packing 规则。实测 1,000 个窗口中有 34 个包含边界 token。

### 3.7 JSONLSource 与 pack_documents

```python
    def __iter__(self) -> Iterator[str]:
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    self.dropped_lines += 1
                    continue
                if not isinstance(record, dict):
                    ...
                value = record.get(self.text_field)
                if not isinstance(value, str) or not value:
                    ...
                yield value
```

- 三类坏行都计入 `dropped_lines`：不是合法 JSON、不是对象、`text` 字段缺失/不是字符串/为空。空行跳过但不计数。调用方可以据此审计丢弃率。
- ⚠️ docstring 说"The downloader (Phase 19 · 42) emits JSONL where each line is a JSON object with a `text` field"，但第 42 课的代码处理的是纯文本行，也没有输出去重后的 JSONL——两课之间的接口并没有真正对上。

```python
    buffer: list[int] = []
    for text in documents:
        token_ids = tokenizer.encode(text)
        if buffer:
            buffer.append(BOUNDARY_TOKEN_ID)
        buffer.extend(token_ids)
        while len(buffer) >= max_tokens:
            yield buffer[:max_tokens]
            buffer = buffer[max_tokens:]
    if buffer:
        yield buffer
```

- 把文档流打包成长度为 `max_tokens` 的组：长文档跨组切分，短文档共享一组，组内用边界分隔。
- ⚠️ 用"`buffer` 是否非空"来决定是否插边界：若上一篇文档恰好把缓冲用完（长度正好是 `max_tokens` 的倍数），下一篇前面就不会有边界。实测 `pack_documents(tok, ["abc", "def"], 3)` → `[[98, 99, 100], [101, 102, 103]]`，两篇文档之间没有 0；空文档还会产生连续两个边界（`["a", "", "b"]` → `[[98, 0, 0, 99]]`）。
- 这个函数**没有被流水线或 demo 使用**，只有测试调用它。

### 3.8 load_index 与 validate_corpus

```python
def validate_corpus(index_entries: list[ShardIndexEntry]) -> list[str]:
    failures: list[str] = []
    for entry in index_entries:
        with h5py.File(entry.path, "r", swmr=True) as fh:
            dataset = fh["tokens"]
            recorded_count = int(dataset.attrs.get("token_count", entry.token_count))
            tokens = np.asarray(dataset[:recorded_count], dtype=TOKEN_DTYPE)
            recomputed = hashlib.sha256(tokens.tobytes()).hexdigest()
            if recomputed != entry.sha256:
                failures.append(entry.shard_id)
    return failures
```

- `load_index` 把 `shards.json` 还原为 `ShardIndexEntry` 列表，对 `document_count` 用 `row.get(..., 0)` 兼容旧版本索引。
- `validate_corpus` 实现了讲义练习 3 的核心：对磁盘上的 token 重算 sha256 与索引比对。实测把 `shard-0001` 第 100 个 token 改成 5 后返回 `['shard-0001']`。
- ⚠️ 局限：一次性把整个分片读进内存；没有核对形状/属性/索引三方的 `token_count`、属性中的 sha256、`global_start` 连续性；无法识别 3.3 中"异常中断但自洽"的残缺分片。分块流式哈希的严格版本见测验 Q11。

### 3.9 demo

```python
    long_repeat = " ".join(base * 4)
    shards = {
        "shard-0000": [long_repeat, long_repeat, long_repeat],
        "shard-0001": [long_repeat, long_repeat, long_repeat],
    }
```

- 5 句话重复 4 遍拼成一篇 2,151 字节的长文档，每个分片 3 篇。两个分片内容完全相同——用于演示足够，但它恰恰是第 42 课去重应当消除的重复数据。
- `run_demo` 用 `chunk_size=512`、`window_size=64`、`batch_size=4`、`seed=7`，采 10 个 batch，每个 batch 打印形状与 `blake2b(inputs, 4 字节)` 校验和（`{checksum:08x}` 输出 8 位十六进制）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| HDF5 分块 + 可扩展数据集 | 流式追加、按切片随机读、自带属性元数据 | 依赖 HDF5 库；fork/网络文件系统下有锁问题；也可用扁平 `.bin` + `np.memmap` |
| 缓冲满 `chunk_size` 才 resize | 写入连续、chunk 对齐，避免碎片 | Python 列表逐元素 append 较慢；生产中按数组切片批量写 |
| 最后一次按剩余数量 resize | 形状精确，无尾部补零 | 最后一个 chunk 未满；`token_count` 属性成为冗余校验 |
| 增量 sha256 | 无需写完再读一遍 | 依赖本机字节序；可用 `'<u2'` 固定 |
| 写入端在每篇文档后加边界 | 下游 dataloader 无需关心文档边界 | 与 docstring/讲义"dataloader 注入"的说法不一致 |
| `uint16` | 体积减半 | 词表 > 65,536 时溢出；应由 `vocab_size` 推导 dtype |
| 一片一个 `.h5` + `shards.json` | 故障隔离、可并行、易续跑 | 代码实际串行写；索引存绝对路径、非原子写 |
| `__exit__` 无条件写属性 | 正常路径简单 | 异常中断会产出"自洽的残缺分片"；应检查 `exc_type`、写临时文件再改名 |
| SWMR 读写 | 读者可在写者追加时安全读取 | 开启 SWMR 后再写属性依赖版本行为；更稳妥是预先建好属性 |
| 构造时打开全部分片 | 实现简单 | 多 worker 时句柄不能跨 fork 共享；分片多时句柄数多 |
| 随机有放回采样 | 简单、可复现 | 无 epoch 覆盖保证、无可恢复状态；多 worker 同 seed 会重复样本 |
| `validate_corpus` 一次性读入 | 代码短 | 大分片内存不足；检查项不全 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `try/except ImportError` + `raise SystemExit(...) from exc` | 导入 `h5py` | 缺依赖时友好退出并保留异常链 |
| `@dataclass` + `asdict` | `ShardIndexEntry.to_dict` | 自动构造函数；转字典便于 `json.dumps` |
| 类属性 | `BOUNDARY_TOKEN = BOUNDARY_TOKEN_ID`、`BYTE_OFFSET = 1` | 类级常量，实例共享 |
| 上下文管理器协议 | `__enter__` 返回 `self`；`__exit__(self, exc_type, exc, tb)` | 支持 `with` 语句；`__exit__` 返回假值时异常继续传播 |
| `try/finally` | `__exit__` 中保证 `close()` | 无论是否出错都执行清理 |
| 前向引用注解 | `-> "HDF5ShardWriter"` | 在类定义内部引用自身类型 |
| 新式类型注解 | `h5py.File \| None`、`dict[str, Iterable[str]]`、`tuple[np.ndarray, np.ndarray]` | Python 3.9+/3.10+ 写法 |
| `@property` | `token_count`、`total_tokens` | 只读属性 |
| 列表推导式带条件 | `[int(i) - self.BYTE_OFFSET for i in ids if int(i) >= self.BYTE_OFFSET]` | 过滤并转换 |
| 生成器函数 | `pack_documents` 中的 `yield buffer[:max_tokens]`；`JSONLSource.__iter__` | 惰性产出，节省内存 |
| 无限生成器 + `next` | `while True: ... yield`；`take` 中 `[next(iterator) for _ in range(n)]` | 由调用方决定取多少 |
| `zip` 并行遍历 | `for entry, dataset in zip(self._entries, self._datasets)` | 同时遍历两个列表 |
| 切片与切片赋值 | `self._buffer[size:]`、`out[cursor : cursor + length] = ...`、`chunk[:-1]`、`chunk[1:]` | 取子序列；把数据写入数组的一段 |
| 多目标赋值 | `inputs[row], targets[row] = self._sample_window()` | 元组解包后分别写入两行 |
| `isinstance` | `isinstance(record, dict)`、`isinstance(value, str)` | 运行时类型检查 |
| `dict.get` 带默认值 | `dataset.attrs.get("token_count", entry.token_count)`、`row.get("document_count", 0)` | 键缺失时使用默认值 |
| `random.Random(seed)` | `self._random = random.Random(seed)` | 独立的随机数生成器实例，不影响全局状态 |
| NumPy | `np.empty((B, W), dtype=np.uint16)`、`np.asarray(list, dtype=...)`、`.tobytes()` | 预分配数组；按 dtype 转换；导出原始字节 |
| h5py | `h5py.File(path, "w", libver="latest")`、`create_dataset(..., maxshape=(None,), chunks=(n,))`、`ds.resize`、`ds.attrs[...]`、`ds.flush()`、`swmr=True` | HDF5 的 Python 接口 |
| f-string | `f"{shard_id}.h5"`、`{entry.sha256[:12]}`、`{tuple(inputs.shape)}`、`{checksum:08x}` | `08x` 为补零 8 位十六进制 |
| `int(hex_str, 16)` | `int(hashlib.blake2b(...).hexdigest(), 16)` | 十六进制字符串转整数 |
| `if __name__ == "__main__": sys.exit(run_demo())` | 文件末尾 | 直接运行时执行，返回值作为退出码 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.24 秒，h5py 3.16.0 / HDF5 2.0.0）：

```text
[shard] shard-0000 tokens=6456 sha256=5c811f78961b global_start=0
[shard] shard-0001 tokens=6456 sha256=5c811f78961b global_start=6456
[validate] all 2 shards match recorded sha256
[batch] step=0 shape=(4, 64) checksum=e2747ebe
[batch] step=1 shape=(4, 64) checksum=14bc5794
[batch] step=2 shape=(4, 64) checksum=fe65c4c3
[batch] step=3 shape=(4, 64) checksum=f8860819
[batch] step=4 shape=(4, 64) checksum=1cedb21e
[batch] step=5 shape=(4, 64) checksum=ea89fe2e
[batch] step=6 shape=(4, 64) checksum=593bcd57
[batch] step=7 shape=(4, 64) checksum=4a2960f5
[batch] step=8 shape=(4, 64) checksum=7540dc30
[batch] step=9 shape=(4, 64) checksum=afb2d9da
```

逐项解读：

- **tokens = 6456**：每篇文档 2,151 字节 → 2,151 个 token，加 1 个边界，`3 × 2152 = 6456`。每个分片恰好 3 个边界 token，且最后一个 token 是 0。
- **两个 sha256 相同**：两个分片的文档完全一样，token 流逐字节相同。
- **global_start = 6456**：第二片的全局起点等于第一片的 token 数；总 token 数 12,912。
- **数据集细节**（调试脚本读取）：形状 `(6456,)`、`chunks=(512,)`、dtype `uint16`，属性 `{token_count: 6456, document_count: 3, sha256: '5c81...'}`；分片文件 19,903 字节（token 数据 12,912 字节，其余是 HDF5 元数据与 chunk 索引）。
- **validate 通过**：两片重算的哈希与索引一致。
- **batch 形状 (4, 64)**：每行一个随机窗口。第 0 个 batch 第 0 行解码为 `'ate and the random seed so that a restart resumes exactly where '`——窗口从单词中间开始，这在 packing 训练中是正常的。
- **checksum 可复现**：`seed=7` 固定，两次运行输出完全一致；不同 batch 的校验和不同说明采到的窗口不同。
- 每个样本读 65 个 token，在 chunk = 512 时约 12.5% 的读取会跨越两个 chunk（10 万次模拟实测 12.3%）。

---

## 7. 动手改一改

1. **讲义练习 1**：给 `HDF5ShardWriter` 增加 `compression` 参数（`"gzip"`、`"lzf"` 或 `None`），传给 `create_dataset`，比较写入/读取耗时与文件大小（本 demo 语料重复度高，压缩率会很夸张，注意结论的适用范围）。
2. **修复异常收尾**：`__exit__` 中若 `exc_type is not None`，关闭文件后删除它；或者改为写 `shard.h5.tmp`、成功后 `os.replace`。写一个测试：文档源中途抛异常后，输出目录里不应存在 `.h5` 文件。
3. **修复 `pack_documents`**：用 `seen_any` 标志决定是否插边界并跳过空文档，验证 `["abc", "def"]`、`max_tokens=3` 时输出 `[[98, 99, 100], [0, 101, 102], [103]]`（参考测验 Q10）。
4. **讲义练习 4**：把 `chunk_size` 设为 32、64、128、512、4096，用 `time.perf_counter` 测 `loader.take(2000)` 的耗时，与理论跨越概率 `(L−1)/C` 对照（参考测验 Q12）。
5. **dtype 自适应**：根据 `tokenizer.vocab_size` 选择 `uint16` 或 `uint32`，并把 dtype 写进 `shards.json`；`MmapTokenStore` 与 `validate_corpus` 从索引读取 dtype。
6. **进阶：多 worker 数据加载**：写一个 `torch.utils.data.IterableDataset` 包装，在 `worker_init_fn` 中按 `worker_id` 打开文件并派生不同的 seed；用 `num_workers=4` 验证 4 个 worker 产出的样本互不相同。

---

## 8. 常见坑

- **一个文档 resize 一次**：会产生大量小写入与元数据碎片；要缓冲到 chunk 大小再写。
- **读取时不按 `token_count` 截断**：若某种实现把最后一块补满（本实现没有），读者会读到补零的 token，模型学会预测 0。
- **以为 chunk 是 window 的整数倍就"对齐"**：读取长度是 `window + 1`、起点随机，chunk = window 时每次读取必然跨两块。
- **`uint16` 装不下大词表**：128K 词表必须用 `uint32`。
- **异常中断仍写完成标记**：本实现的 `__exit__` 就是如此，残缺分片会被当作完整数据。
- **SWMR 顺序错误**：先开 SWMR 再建数据集，或写端不用 `libver="latest"`，会导致"file is locked"或无法打开。
- **在主进程打开 HDF5 句柄再 fork 给 worker**：HDF5 句柄不是 fork 安全的。
- **多 worker 使用同一 seed**：所有 worker 产出相同样本。
- **索引存绝对路径**：换目录、换机器就找不到文件。
- **target 方向搞反**：`targets = chunk[1:]` 是"下一个 token"；写成 `chunk[:-1]` 会让模型学"复制当前 token"。

---

## 9. 测试在验证什么

测试文件 `tests/test_hdf5_corpus.py`（`unittest` 风格；`tests/__init__.py` 为空文件）。运行方式与实际结果：

```bash
cd code
python -m unittest discover tests -v      # Ran 17 tests in 0.115s, OK
python -m pytest -q tests                 # 17 passed in 0.31s
```

| 测试 | 验证的性质 |
|------|-----------|
| `TokenizerTests.test_encode_round_trip_preserves_ascii` | `decode(encode("hello")) == "hello"` |
| `TokenizerTests.test_empty_encode_returns_empty_list` | 空串编码为 `[]` |
| `TokenizerTests.test_boundary_token_is_reserved` | 普通文本的编码中不出现 0 |
| `ShardWriterTests.test_writer_rejects_zero_chunk` | `chunk_size=0` 抛 `ValueError` |
| `ShardWriterTests.test_writer_persists_token_count_attribute` | 5 + 1 + 4 个 token，chunk 8，属性 `token_count == 10`（残余缓冲被刷出） |
| `ShardWriterTests.test_writer_chunk_alignment_produces_chunked_dataset` | 16 个 token、chunk 4：形状 `(16,)`、`chunks == (4,)` |
| `ShardWriterTests.test_sha256_matches_recomputed_value` | 增量哈希 = 读回后重算的哈希 |
| `PipelineTests.test_pipeline_writes_index_with_global_starts` | 第一片 `global_start = 0`，第二片等于第一片 token 数；`total_tokens` 为总和 |
| `PipelineTests.test_load_index_round_trip` | `shards.json` 读回后 sha256 不变 |
| `PipelineTests.test_validate_corpus_passes_for_intact_shards` | 完好分片校验通过 |
| `MmapStoreTests.test_get_slice_spans_two_shards` | 全量切片的前后两半与分别切片结果一致（跨分片拼接正确） |
| `MmapStoreTests.test_get_slice_rejects_oob_request` | 越界请求抛 `ValueError` |
| `DataloaderTests.test_dataloader_emits_shifted_targets` | batch 形状为 `(2, 16)` |
| `DataloaderTests.test_dataloader_deterministic_with_seed` | 同 seed 的两个 loader 产生相同 batch（讲义练习 2） |
| `JSONLSourceTests.test_jsonl_source_drops_malformed_lines` | 非 JSON 行与缺字段行被丢弃，`dropped_lines == 2` |
| `PackDocumentsTests.test_pack_documents_yields_fixed_length_groups` | 除最后一组外每组长度为 8 |
| `PackDocumentsTests.test_pack_documents_injects_boundary_between_documents` | 打包结果中出现边界 token |

测试的盲区：

- **名不副实的测试**：`test_dataloader_emits_shifted_targets` 只检查了形状，**没有检查 target 是否真的右移一位**。应补一句 `np.array_equal(inputs[:, 1:], targets[:, :-1])`（实测成立）。
- **没有测试校验失败的情形**：`validate_corpus` 只在完好分片上测过；应修改一个 token 后断言返回该分片 id（实测可以发现）。
- **没有测试异常收尾**：文档源抛异常时会留下"自洽的残缺分片"，测试没有覆盖。
- **`pack_documents` 的测试太宽松**：只断言"出现了边界"，没有覆盖"上一篇恰好填满一组"时边界丢失的情形。
- **没有测试 dtype 溢出、跨分片窗口的内容正确性、`get_slice` 空切片与负数参数**。
