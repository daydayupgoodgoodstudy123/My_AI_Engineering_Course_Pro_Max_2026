# 测验 · HDF5 格式的分词语料（HDF5 Tokenized Corpus）

> **阶段 19 · 综合项目 · 第 43 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么不用 JSONL | 训练器要的是"扁平 token 流 + O(1) 随机切片"；JSONL 每次读都要解析、文档边界不可寻址，定位第 N 个样本要扫描文件 |
| 2 | 可扩展的分块数据集 | `create_dataset(shape=(0,), maxshape=(None,), chunks=(chunk_size,), dtype=uint16)`：初始为空、长度不设上限、按固定块存储 |
| 3 | 先缓冲再扩展 | 内存缓冲攒满 `chunk_size` 个 token 才 `resize` 并写入一次；逐 token/逐文档 resize 会碎片化，一次性写完则崩溃丢整片 |
| 4 | 属性记录真值 | 关闭时把 `token_count`、`document_count`、`sha256` 写成数据集属性，读端以此为准 |
| 5 | 分片写 + 索引 | 一个输入分片对应一个 `.h5`；`shards.json` 记录路径、token 数、文档数、sha256、`global_start`（全局偏移） |
| 6 | 跨分片切片 | `get_slice(start, stop)` 按 `global_start` 把全局区间拆成各分片的局部区间，拼成一个 `uint16` 数组 |
| 7 | SWMR | 写端 `libver="latest"` 打开 → 先建好所有数据集 → `swmr_mode = True` → 每次 resize 后 `flush()`；读端以 `swmr=True` 打开 |
| 8 | 滑动窗口采样 | 随机起点读 `window_size + 1` 个 token，`(input, target) = (chunk[:-1], chunk[1:])`；窗口可以跨文档、跨分片 |
| 9 | 边界 token（packing） | ID 0 保留为文档分隔符，字节整体偏移 1（1..256）；本实现由**写端**在每篇文档后追加，模型据此学习"换文档" |
| 10 | 校验 | 对磁盘上的 token 字节重算 sha256 与索引比对，训练开始前发现损坏，而不是跑了 16 小时后才发现 |

### 核心技能（能动手做到）

- [ ] 用 h5py 写出带缓冲、按块 resize、写属性的分片写入器，并解释每次 `_flush_buffer` 后数据集的形状
- [ ] 手算任意语料的 token 数、边界 token 数与 `global_start`
- [ ] 实现跨分片的 `get_slice`，并处理越界、空切片与拼接长度校验
- [ ] 实现可复现的滑动窗口采样器，并验证 target 恰好是 input 右移一位
- [ ] 计算随机起点下"一次读取跨越两个 chunk"的概率，据此选择 chunk 大小
- [ ] 识别本节代码在异常收尾、`pack_documents` 边界、`uint16` 容量、"mmap"命名上的问题并修复

---

## 二、基础自测（选择题）

**Q1.** 讲义认为训练时的分词语料应存成 HDF5 的分块整数数据集而不是 JSONL，最核心的理由是：

- A. HDF5 文件一定比 JSONL 小
- B. 训练器需要的是一个扁平的 token 流，能以 O(1) 代价读取任意 `tokens[a:b]` 切片；JSONL 每次读都要解析、无法按样本编号直接定位
- C. JSONL 不支持 UTF-8
- D. HDF5 会自动完成分词

**Q2.** 执行下面的代码后，`tokens` 数据集的状态是：

```python
writer = HDF5ShardWriter(path, chunk_size=8)
with writer:
    writer.add_document([1, 2, 3, 4, 5])
    writer.add_boundary()
    writer.add_document([6, 7, 8, 9])
```

- A. 形状 `(16,)`，末尾 6 个位置补 0，属性 `token_count = 10`
- B. 形状 `(8,)`，最后 2 个 token 留在缓冲区里丢失了
- C. 形状 `(11,)`，因为最后一篇文档后也自动追加了边界 token
- D. 形状 `(10,)`，共写入两次：缓冲满 8 个时写一次，`__exit__` 时把剩余 2 个写入；属性 `token_count = 10`

**Q3.** demo 输出中两个分片的 sha256 前缀都是 `5c811f78961b`，`shard-0001` 的 `global_start = 6456`。最合理的解释是：

- A. 两个分片里放的是完全相同的 3 篇文档（每篇都是同一个 `long_repeat`，2,151 字节），token 流逐字节相同，哈希自然相同；`6456 = 3 × (2151 + 1)`，其中 `+1` 是每篇文档后的边界 token
- B. sha256 只取了前 12 个字符，碰撞是正常现象
- C. `validate_corpus` 有 bug，把同一个分片读了两遍
- D. 第二个分片的 sha256 是从第一个分片复制过来的

**Q4.** demo 中总 token 数为 12,912，`SlidingWindowDataloader(store, window_size=64, batch_size=4, seed=7)`。下列说法正确的是：

- A. 每个样本读取 64 个 token，`targets` 是 `inputs` 左移一位
- B. `_max_start = 12912 − 64 = 12848`，最后一个样本可能越界
- C. 每个样本读取 65 个 token，`inputs = chunk[:-1]`、`targets = chunk[1:]`；`_max_start = 12912 − 64 − 1 = 12847`，`randint` 两端都包含，最远恰好读到第 12,912 个 token
- D. 每个 batch 都从全局第 0 个 token 开始顺序读取

**Q5.** 关于 HDF5 的 SWMR（Single-Writer-Multiple-Reader）模式，与讲义和代码一致的是：

- A. 只需要读端设置 `swmr=True`，写端不需要任何特殊设置
- B. 写端先设置 `swmr_mode = True`，再创建数据集
- C. 写端用 `libver="latest"` 打开文件，先创建好所有数据集，再设置 `swmr_mode = True`，此后每次 resize 后调用 `dataset.flush()`；读端用 `swmr=True` 打开
- D. SWMR 允许多个进程同时写同一个文件

**Q6.** demo 使用 `chunk_size=512`、`window_size=64`，每个样本从**随机起点**读取 65 个 token。一个样本的读取跨越两个 chunk 的概率约为：

- A. 12.5%
- B. 0%，因为 512 是 64 的整数倍
- C. 50%
- D. 100%

**Q7.** 类名 `MmapTokenStore` 和讲义都在说"memory-mapped read"。对本节实际的读取方式，最准确的描述是：

- A. h5py 把整个文件 `mmap` 进进程地址空间，切片不发生任何拷贝
- B. 读取时先把整个分片读进内存，再切片
- C. 读取等价于 `np.memmap`，因为 HDF5 的 chunk 在磁盘上是连续的
- D. h5py 通过 HDF5 库按 chunk 读取（必要时解压/查 chunk 缓存），再把请求的 hyperslab 拷贝进一个新分配的 NumPy 数组；分块数据集没有单一连续偏移（实测 `dataset.id.get_offset()` 返回 `None`），无法直接 `np.memmap`

**Q8.** 代码把 token 存成 `np.uint16`。如果换成词表大小为 128,256 的 tokenizer（如 Llama 3）而不改 dtype，会发生什么？

- A. 没有影响，`uint16` 能表示到 128,255
- B. 大于 65,535 的 token ID 无法放进 `uint16`；在 NumPy 2.x 中 `np.asarray([70000], dtype=np.uint16)` 会直接抛 `OverflowError`，需要改用 `uint32`
- C. HDF5 会自动把数据集升级为 `uint32`
- D. 大 ID 会被静默截断为 65,535，训练照常进行

---

## 三、动手 / 代码题

**Q9.** 阅读 `HDF5ShardWriter.__exit__`：

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

假设文档来源在第 1 篇文档之后抛出 `RuntimeError("source died")`（例如上游下载流断开）。

1. `x.h5` 文件最后处于什么状态？它看起来"完整"吗？
2. 这对讲义"分片写使崩溃最多丢一个分片"的承诺意味着什么？
3. 给出修复方案。

**Q10.** `pack_documents(tokenizer, documents, max_tokens)` 的文档字符串说"short documents share a group separated by BOUNDARY_TOKEN_ID"。写出下面三次调用的输出（字节 a=97 偏移后为 98），并指出问题：

```python
list(pack_documents(tok, ["abc", "def"], 3))
list(pack_documents(tok, ["ab", "cd"], 3))
list(pack_documents(tok, ["a", "", "b"], 8))
```

**Q11.** 当前的 `validate_corpus` 如下：

```python
    for entry in index_entries:
        with h5py.File(entry.path, "r", swmr=True) as fh:
            dataset = fh["tokens"]
            recorded_count = int(dataset.attrs.get("token_count", entry.token_count))
            tokens = np.asarray(dataset[:recorded_count], dtype=TOKEN_DTYPE)
            recomputed = hashlib.sha256(tokens.tobytes()).hexdigest()
            if recomputed != entry.sha256:
                failures.append(entry.shard_id)
```

1. 实测：把 `shard-0001` 第 100 个 token 改成 5 后，它能否被发现？
2. 列出它**没有**检查的不一致情形（至少三种）。
3. 写一个更严格、且不会把整个分片一次读进内存的版本。

**Q12.** 讲义说"Set the HDF5 chunk to a multiple of `window_size` and reads are page-cache aligned. Mismatched chunks halve the throughput because every sample touches two chunks." 设每次读取长度 L = window_size + 1 = 65，起点在全局流中均匀随机。

1. 推导一次读取跨越 chunk 边界的概率（设 L ≤ C），并计算 C = 64、128、512、4096 时的值。
2. C = 64（恰好等于 window_size）时会怎样？讲义的规则在这里有什么漏洞？
3. chunk 越大越好吗？说明读放大（read amplification）的代价。

---

## 四、面试高频题

**Q13.**（基础必考）预训练数据加载有哪些常见存储格式（JSONL、Parquet/Arrow、HDF5、扁平 `.bin` + `np.memmap`、WebDataset 等）？分词后的 token 为什么通常存成扁平的整数数组？

**Q14.**（原理深挖）什么是 sequence packing？为什么要插入文档边界 token？跨文档的注意力会带来什么问题，有哪些处理方式？

**Q15.**（工程实践）把本节的 `SlidingWindowDataloader` 扩展成多 worker 的 PyTorch `DataLoader`，你会遇到哪些坑？

**Q16.**（场景设计）为 2T token 的语料设计一条分词落盘流水线（承接第 42 课的下载器），要求可并行、可续跑、可校验。说说你的设计。

**Q17.**（追问型）HDF5 的 chunk、chunk cache、SWMR 分别解决什么问题？线上遇到"file is locked"或读到不一致数据时，你会怎么排查？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："JSONL on disk dies at the first cold-cache page fault: the JSON parser is slow, the document boundaries are not addressable, and seeking to 'sample 4,217,884' requires scanning the file... it wants a flat token stream with O(1) random access."

- A 错：体积不是核心理由（本 demo 6,456 个 uint16 token 的分片文件为 19,903 字节，元数据开销反而不小）。
- C 错：JSONL 当然支持 UTF-8。
- D 错：分词由 `Tokenizer` 完成，HDF5 只负责存储。讲义还提到 Parquet "compresses well" 但训练器"does not want columns"。

### Q2 — 答案：D

逐步看：前 5 个 token 进缓冲；边界 token 0 进缓冲（共 6 个）；第二篇文档写入 6、7 后缓冲达到 8 → `_flush_buffer(final=False)`：resize 到 `(8,)`、写入 `[1,2,3,4,5,0,6,7]`；剩下 `[8, 9]` 留在缓冲。`with` 结束时 `__exit__` 调用 `_flush_buffer(final=True)`：resize 到 `(10,)` 写入最后 2 个；再写属性 `token_count = 10`。测试 `test_writer_persists_token_count_attribute` 断言的正是 10。

- A 错：最后一次 resize 用的是剩余数量而不是整块，数据集形状精确等于 token 数，没有补零（实测 `shape == (token_count,)`）。
- B 错：`__exit__` 会刷出残余缓冲。
- C 错：`HDF5ShardWriter` 不会自动加边界；是 `ShardedTokenizationPipeline.write_shard` 在每篇文档后调用 `add_boundary()`，这里是直接调用 writer。

### Q3 — 答案：A

`build_demo_corpus` 中 `long_repeat = " ".join(base * 4)`（2,151 字节），两个分片都是 `[long_repeat] * 3`。每篇文档编码为 2,151 个 token，加 1 个边界，共 `3 × 2152 = 6456`。两个分片的 token 流完全相同，sha256 必然相同；`shard-0001` 的 `global_start` 等于 `shard-0000` 的 token 数 6,456。

- B 错：sha256 碰撞概率可忽略，打印截断不影响比较。
- C、D 错：实测把 `shard-0001` 的一个 token 改掉后，`validate_corpus` 只报告 `['shard-0001']`，说明两个分片是独立计算的。

顺带一提：这份 demo 语料本身就是"重复文档"，恰好是第 42 课去重环节应当删掉的内容——演示用数据可以，真实流水线中不该出现。

### Q4 — 答案：C

`_sample_window` 读 `get_slice(start, start + window_size + 1)` 共 65 个 token，`chunk[:-1]` 为输入、`chunk[1:]` 为目标（目标是输入**右移**一位：`targets[i] = inputs[i+1]`，实测 `inputs[0][1:] == targets[0][:-1]`）。`random.Random.randint(a, b)` 包含两端，`start` 最大 12,847，`start + 65 = 12,912 = total_tokens`，恰好不越界。

- A 错：读 65 个，而且 target 是"下一个 token"，即右移。
- B 错：代码减了 `window_size + 1`，不会越界。
- D 错：每行都是独立随机起点。

### Q5 — 答案：C

讲义 Production Patterns："Single-Writer-Multiple-Reader mode requires the writer to open with `libver="latest"`, create every dataset up front, then set `file.swmr_mode = True`. After that the writer must call `dataset.flush()` after each resize..." 代码 `__enter__` 与 `_flush_buffer` 完全按此实现，`MmapTokenStore` 与 `validate_corpus` 以 `swmr=True` 打开。

- A 是课程自带 `quiz.json` 的说法（"the writer needs no special mode"），与讲义和代码都矛盾。
- B 顺序反了：进入 SWMR 写模式后不能再改变文件结构。
- D 错：SWMR 是**单**写者。

### Q6 — 答案：A

设 chunk 大小为 C、读取长度为 L（L ≤ C）。起点在一个 chunk 内的偏移均匀分布于 `0..C−1`，只有偏移 > `C − L` 时才会越过边界，共 `L − 1` 个位置，所以概率 = `(L − 1) / C = 64 / 512 = 12.5%`。用 10 万次随机模拟实测为 12.3%。

- B 错：起点是随机的，不对齐 chunk 边界，"整数倍"并不能保证不跨越。
- C 是 C = 128 时的值；D 是 C ≤ 64 时的情况（见 Q12）。

### Q7 — 答案：D

h5py 读取分块数据集的路径是：HDF5 库定位涉及的 chunk → 从磁盘（或 HDF5 自己的 chunk 缓存、操作系统页缓存）读出 → 必要时解压 → 把请求范围拷贝进新分配的 NumPy 数组。`get_slice` 里 `out[cursor : cursor + length] = dataset[local_start:local_stop]` 还会再拷贝一次进 `out`。讲义正文其实也写了"HDF5 copies the requested hyperslab from the page cache into a freshly allocated NumPy array"，所以"mmap"只是一个比喻；真正零拷贝的 `np.memmap` 需要连续存储的扁平二进制文件。

- A 错：没有 mmap，也不是零拷贝。
- B 错：只读请求范围涉及的 chunk。
- C 错：分块数据集没有单一的连续偏移，chunk 位置由 B-tree 等索引记录。

### Q8 — 答案：B

`uint16` 最大值 65,535。实测 NumPy 2.5：`np.asarray([70000], dtype=np.uint16)` 抛 `OverflowError: Python integer 70000 out of bounds for uint16`——写入第一个大 ID 时流水线就会中断。更隐蔽的风险是：若数据先经过某些整数数组运算再 `astype(np.uint16)`，溢出会**静默回绕**。所以 dtype 必须由词表大小推导（`vocab_size ≤ 65536` 用 `uint16`，否则 `uint32`），并在写入前断言 `max_id < 2**16`。

- A 错：65,535 < 128,255。
- C 错：HDF5 数据集的 dtype 创建后固定。
- D 描述的是"静默截断"，不是这里（NumPy 2.x、Python int 输入）的行为。

### Q9 — 参考答案

1. 实测：`RuntimeError` 从 `with` 块中传出时，`__exit__` **不检查 `exc_type`**，照常刷出残余缓冲并写入属性。结果文件中 `tokens` 形状为 `(12,)`，属性 `token_count = 12`、`document_count = 1`、`sha256` 为这 12 个 token 的正确哈希——**看起来完全是一个合法、完整的分片**。`write_corpus` 因为异常不会写 `shards.json`，但磁盘上已经有一个"自洽"的残缺 `.h5`。若有人重新生成索引或手工拼接，它会被当作完整数据接纳，且 `validate_corpus` 也会通过（哈希就是按残缺内容算的）。
2. 讲义承诺"a crash loses at most one shard"成立的前提是：残缺分片能被**识别**出来。当前实现把"异常中断"与"正常完成"写成了同样的元数据，等于把损失从"丢一片"变成了"静默混入一片残缺数据"。（若进程被 `SIGKILL`，`__exit__` 根本不会执行，文件没有属性，这反而是可识别的。）
3. 修复：
   - `__exit__` 中：`if exc_type is not None:` 只关闭文件，不写属性，并删除（或改名为 `.failed`）该文件；
   - 写入临时路径 `shard-0000.h5.tmp`，成功关闭后 `os.replace` 成正式名——下游只认正式名；
   - 写一个显式的 `attrs["complete"] = True`，读端与校验端拒绝没有该属性的分片；
   - 索引只在所有分片成功后原子写入（先写 `shards.json.tmp` 再 `os.replace`）。

### Q10 — 参考答案

实测输出：

```python
list(pack_documents(tok, ["abc", "def"], 3))   # [[98, 99, 100], [101, 102, 103]]
list(pack_documents(tok, ["ab", "cd"], 3))     # [[98, 99, 0], [100, 101]]
list(pack_documents(tok, ["a", "", "b"], 8))   # [[98, 0, 0, 99]]
```

问题：

1. **边界丢失**：第一例中 `"abc"` 恰好填满一组，`buffer` 被清空；处理 `"def"` 时 `if buffer:` 为假，不再插入边界。如果下游把这些组首尾相接成连续 token 流（就像本节的扁平 HDF5 数据集），`"abc"` 和 `"def"` 之间就没有分隔符。第二例边界正常出现（`0` 在第一组末尾）。
2. **空文档产生连续边界**：第三例空串编码为 `[]`，但仍插入了一个边界，得到 `0, 0`。
3. 文档字符串说"Yields lists of exactly max_tokens"，但最后一组可以更短（docstring 后半句也承认了）。另外这个函数**没有被流水线使用**——`ShardedTokenizationPipeline` 走的是 `writer.add_document` + `writer.add_boundary`，测试单独测了它。

修复：用一个"是否已有文档"的标志而不是 `buffer` 是否为空来决定插边界，并跳过空文档：

```python
def pack_documents(tokenizer, documents, max_tokens):
    if max_tokens <= 1:
        raise ValueError("max_tokens must be greater than 1")
    buffer: list[int] = []
    seen_any = False
    for text in documents:
        token_ids = tokenizer.encode(text)
        if not token_ids:
            continue                      # 空文档不产生边界
        if seen_any:
            buffer.append(BOUNDARY_TOKEN_ID)
        buffer.extend(token_ids)
        seen_any = True
        while len(buffer) >= max_tokens:
            yield buffer[:max_tokens]
            buffer = buffer[max_tokens:]
    if buffer:
        yield buffer
```

修复后（已运行验证）第一例输出 `[[98, 99, 100], [0, 101, 102], [103]]`：边界被保留在第二组开头；第三例输出 `[[98, 0, 99]]`，不再有连续边界。

### Q11 — 参考答案

1. 能。实测改动后 `validate_corpus(entries)` 返回 `['shard-0001']`，未改动的 `shard-0000` 通过。
2. 没有检查的情形：
   - 数据集实际形状 `dataset.shape[0]` 与属性 `token_count`、索引 `entry.token_count` 三者是否一致——它用属性截断读取，若属性被改小，只哈希前一部分，后面多出的数据被忽略；若属性缺失则退回索引值；
   - 属性中的 `sha256` 与索引中的 `sha256` 是否一致；
   - 属性 `document_count` 与索引是否一致；
   - `global_start` 是否连续（`entries[i+1].global_start == entries[i].global_start + entries[i].token_count`）、`total_tokens` 是否等于总和；
   - dtype 是否为预期的 `uint16`、数据集名是否存在；
   - 是否存在异常中断留下的"残缺但自洽"的分片（见 Q9），需要 `complete` 标记。
   - 另外它把整个分片一次性读进内存，单个分片数 GB 时会占满内存。
3. 参考实现（按块流式哈希，已在本地语料上运行验证与原函数结果一致）：

```python
def validate_corpus_strict(entries, block=1 << 20):
    failures = []
    expected_start = 0
    for e in entries:
        problems = []
        if e.global_start != expected_start:
            problems.append("global_start")
        with h5py.File(e.path, "r", swmr=True) as fh:
            ds = fh["tokens"]
            n = ds.shape[0]
            if ds.dtype != TOKEN_DTYPE:
                problems.append("dtype")
            if int(ds.attrs.get("token_count", -1)) != n or n != e.token_count:
                problems.append("token_count")
            if ds.attrs.get("sha256") != e.sha256:
                problems.append("attr_sha256")
            h = hashlib.sha256()
            for s in range(0, n, block):                       # 分块读，内存恒定
                h.update(np.asarray(ds[s : min(n, s + block)], dtype=TOKEN_DTYPE).tobytes())
            if h.hexdigest() != e.sha256:
                problems.append("content_sha256")
        expected_start += e.token_count
        if problems:
            failures.append(f"{e.shard_id}: {','.join(problems)}")
    return failures
```

   sha256 是可以增量 `update` 的，分块哈希与一次性哈希结果相同。各分片相互独立，还可以用进程池并行校验（讲义"Sharded sha256 with parallel verification"）。

### Q12 — 参考答案

1. 推导见 Q6：`P(跨越) = (L − 1) / C`（L ≤ C）。L = 65 时：

| C | 跨越概率 | 每样本平均触及 chunk 数 |
|---|---------|----------------------|
| 64 | 必然跨越（L > C） | 恰好 2（65 个 token 必然覆盖两个 64 长的 chunk） |
| 128 | 64/128 = 50% | 1.5 |
| 512 | 64/512 = 12.5% | 1.125 |
| 4096 | 64/4096 ≈ 1.6% | ≈1.016 |

2. C = 64 恰好等于 `window_size`，满足讲义"chunk 是 window_size 的整数倍"，但每次读的是 `window_size + 1 = 65` 个 token，比一个 chunk 还长，**每个样本必然触及至少两个 chunk**——这正是讲义想避免的"every sample touches two chunks"。漏洞在于：(a) 读取长度是 `window + 1` 而不是 `window`；(b) 起点是随机的，不对齐 chunk 边界，"整数倍"本身不保证对齐。要真正对齐，要么让起点只取 chunk 边界上的位置（牺牲样本多样性），要么让 C ≫ L 把跨越概率压低。课程 `quiz.json` 中"each sample lands inside one or two chunks"的说法更接近实际。
3. 不是。HDF5 以 chunk 为最小 I/O（和压缩）单位：读 65 个 token（130 字节）也要读入整个 chunk。C = 4096 时一次要读 8 KB，读放大约 63 倍；若开了 gzip 压缩，还要解压整块。chunk cache 命中时代价可以摊薄，但随机采样下命中率很低。权衡：C 取 L 的几十倍、单个 chunk 在几十 KB 到 1 MB 量级是常见折中；讲义练习 4 要求实测 C = window、window/2、2×window 时的吞吐。

### Q13 — 参考回答要点

- **JSONL**：人类可读、易追加，但每次读要解析 JSON、需要重新分词，不能随机访问；适合作为原始语料和交换格式。
- **Parquet / Arrow**：列式、压缩率高，适合带元数据的文档级数据和过滤分析；训练器要的却是"一条 token 流"，按行组读取，不是 O(1) 切片。
- **HDF5**（本节）：分块、可扩展、带属性元数据、可按切片读，单文件内可放多个数据集；代价是依赖 HDF5 库、多进程/网络文件系统下有锁的坑。
- **扁平 `.bin` + `np.memmap`**：最简单的方案，把所有 token 写成连续的 `uint16`/`uint32` 二进制文件，读时 `np.memmap` 真正零拷贝映射；缺点是没有内建元数据与校验，需要另配索引文件。
- **WebDataset / 分片 tar、MDS 等流式格式**：面向对象存储和顺序流式读取，适合多节点大规模训练，随机访问能力较弱，靠 shuffle buffer 打乱。
- **为什么扁平整数数组**：分词只做一次（离线），训练时只剩"按偏移读整数"；固定宽度整数可以 O(1) 定位；packing 后没有 padding 浪费。
- 加分点：dtype 由词表大小决定（见 Q8）；扁平流配合 `global_start` 索引可以实现跨文件的统一寻址。

### Q14 — 参考回答要点

- **Packing**：把多篇文档首尾相接成一条长流，再切成固定长度的训练序列，避免对短文档 padding 造成算力浪费。本节的扁平 HDF5 + 随机滑动窗口就是 packing。
- **边界 token**：在文档之间插入分隔符（本节 ID 0，类似 GPT 系列的 `<|endoftext|>`），让模型知道"上一篇结束、新的一篇开始"，生成时也能学会在合适位置输出结束符。讲义："a window may straddle two documents, with an explicit `boundary_token_id` between them so the model learns to use the separator."
- **跨文档注意力的问题**：标准因果注意力下，窗口内后一篇文档的 token 可以注意到前一篇的内容，引入无关上下文噪声。
- **处理方式**：
  - 接受它（GPT-2/3 风格的常见做法），依靠边界 token 让模型学会"忽略前文"；
  - document masking：构造块对角的注意力 mask，或用变长注意力（如 FlashAttention 的 varlen 接口），让每个 token 只看到同一文档；
  - 位置编码在边界处重置；
  - 对边界 token 的 loss 做 mask（讲义："The training loss masks the boundary token if the model is supposed to ignore it"）。
- 本节实测：demo 中每 1,000 个窗口约有 34 个包含边界 token；边界 token 占全部 token 的比例只有 6/12,912 ≈ 0.05%（因为文档很长）。

### Q15 — 参考回答要点

- **fork 安全**：不要在主进程里打开 h5py 文件句柄再 fork 给 worker；HDF5 句柄不是 fork 安全的。应当在 `worker_init_fn` 或 `__getitem__` 首次调用时在 worker 内部打开（本节 `MmapTokenStore` 在构造时就打开了所有文件，直接传给多 worker 会出问题）。
- **随机种子**：本节用 `random.Random(seed)`，若每个 worker 都用同一个 seed，所有 worker 会产生**完全相同**的样本序列；要按 `seed + worker_id + rank` 派生。
- **数据划分**：多 GPU（DDP）时还要按 rank 划分分片或样本，避免不同卡训练同一批数据。
- **覆盖与 epoch**：随机有放回采样不保证一个 epoch 内覆盖全部 token；可以改为"预先生成打乱的起点排列"，并能记录采样器状态以便从 checkpoint 精确续跑（承接第 47 课）。
- **拷贝与 pinned memory**：讲义提到 batch 拷贝进 pinned memory 再送 GPU；`uint16` 需要在送入 embedding 前转成 `int64`/`int32`。
- **文件锁与网络文件系统**：多读者在 NFS/Lustre 上可能遇到 HDF5 文件锁问题，必要时设置 `HDF5_USE_FILE_LOCKING=FALSE`（前提是确认没有写者）。
- **IterableDataset 与 Dataset 的选择**：本节是无限迭代器，适合 `IterableDataset`，但要自己处理分片和 worker 划分。

### Q16 — 参考回答要点

- **输入契约**：读取第 42 课的 manifest，只处理校验通过（sha256 匹配）的分片，跳过 `near_duplicate` 文档；与本节 `JSONLSource` 对接时要统一格式（第 42 课代码产出的是纯文本行，而本节 `JSONLSource` 期望 `{"text": ...}` 的 JSONL）。
- **并行**：一个输入分片对应一个输出 `.h5`（讲义"1:1 mapping makes resume and partial-failure recovery trivial"），用进程池或集群任务并行；分词器固定版本并记录其哈希。
- **幂等与续跑**：输出先写临时文件，成功后原子改名；重跑时跳过"已存在且校验通过"的分片；失败分片记录日志重试（见 Q9）。
- **索引**：所有分片完成后按固定顺序（例如 shard_id 排序）计算 `global_start`，原子写入 `shards.json`；路径写相对路径（本节写的是绝对路径，换机器就失效）；索引本身算哈希并提交版本控制。
- **数据类型与布局**：按词表选 `uint16`/`uint32`；chunk 大小按训练窗口与读放大权衡（见 Q12）；一般不压缩或只用快速压缩（讲义练习 1 比较 gzip 开销）。
- **校验**：CI 中并行运行严格校验（见 Q11），训练启动前 fail fast。
- **统计与审计**：每分片 token 数、文档数、边界数、超长文档截断数（讲义练习 5），以及哈希与 tokenizer 版本，一起写入索引。

### Q17 — 参考回答要点

- **chunk**：数据集在磁盘上的存储与 I/O 单位；可扩展（`maxshape=None`）数据集**必须**分块；压缩也是按 chunk 进行。chunk 太小 → 元数据与索引开销大、碎片多；太大 → 读放大（见 Q12）。
- **chunk cache**：HDF5 在每个打开的数据集上维护一个原始 chunk 缓存（h5py 可通过 `rdcc_nbytes` 等参数设置大小），避免重复读同一 chunk；随机访问下要让缓存至少容纳一次读取会触及的 chunk。
- **SWMR**：允许一个写者在追加数据的同时，多个读者安全地读到一致的数据。要求写端 `libver="latest"`、先建好结构再开启 `swmr_mode`、每次扩展后 `flush()`；读端 `swmr=True`，必要时调用 `refresh()` 看到新长度。进入 SWMR 写模式后不应再改变文件结构（例如新建数据集）。本节在开启 SWMR 后才写入属性，在 h5py 3.16 / HDF5 2.0.0 下实测没有报错，但这依赖于具体版本的行为，更稳妥的做法是在开启 SWMR 前就创建好属性。
- **排查"file is locked"**：
  - 是否有其他进程以写模式打开了同一文件（包括上一次崩溃后残留的进程）；
  - 读端是否以 `swmr=True` 打开、写端是否用了 `libver="latest"`（讲义："Skipping `libver="latest"` or enabling SWMR after structural changes is a common source of 'file is locked' failures"）；
  - 是否在 NFS 等不支持 POSIX 锁的文件系统上，必要时设置 `HDF5_USE_FILE_LOCKING=FALSE`；
  - 是否在 fork 之前打开了句柄。
- **排查读到不一致数据**：写端是否在 resize 后 `flush()`；读端是否 `refresh()`；读端是否按属性/索引中的 `token_count` 截断，而不是盲目使用数据集形状；用 sha256 校验确认。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 42 大规模语料下载器](../../42-large-corpus-downloader/docs/zh.md)：本节的输入来源；去重后的文档与 manifest 是分词的起点。
- [阶段 19 · 31 使用滑动窗口构建分词后的数据集](../../31-tokenized-dataset-sliding-window/docs/zh.md)：滑动窗口与 `(input, target)` 右移一位的构造。
- [阶段 19 · 30 从零实现 BPE Tokenizer](../../30-bpe-tokenizer-from-scratch/docs/zh.md)：真实流水线中替换本节字节级 tokenizer 的组件，也决定了 token dtype。
- [阶段 10 · 03 用于预训练的数据管道](../../../10-llms-from-scratch/03-data-pipelines/docs/zh.md)：预训练数据从采集到打包的整体视角。
- [阶段 00 · 09 数据管理](../../../00-setup-and-tooling/09-data-management/docs/zh.md)：数据存储格式与版本管理基础。

### 本节被哪些后续内容用到
- [阶段 19 · 44 带线性 Warmup 的余弦学习率](../../44-cosine-lr-warmup/docs/zh.md)、[阶段 19 · 45 Gradient Clipping 与 Mixed Precision](../../45-gradient-clipping-amp/docs/zh.md)：消费本节的 dataloader 进行训练。
- [阶段 19 · 46 Gradient Accumulation](../../46-gradient-accumulation/docs/zh.md)：以本节的固定长度 batch 为单位累积梯度。
- [阶段 19 · 47 Checkpoint 保存与恢复](../../47-checkpoint-save-resume/docs/zh.md)：需要同时保存采样器状态，才能精确续跑。
- [阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../48-distributed-fsdp-ddp/docs/zh.md)、[阶段 19 · 77 从零实现数据并行 DDP](../../77-data-parallel-ddp/docs/zh.md)：多 rank 下的数据划分。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：next-token prediction 训练目标消费的正是 `(input, target)` 对。

### 延伸关键词
`h5py` · `chunked dataset` · `maxshape=None` · `SWMR` · `chunk cache (rdcc)` · `HDF5_USE_FILE_LOCKING` · `np.memmap` · `sequence packing` · `document masking / varlen attention` · `<|endoftext|>` · `read amplification` · `worker_init_fn` · `WebDataset / MDS`
