# 测验 · 大规模语料下载器（Large Corpus Downloader）

> **阶段 19 · 综合项目 · 第 42 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两个必须从第一天就设计的失败 | 断点续传（partial-download resume）与重复文档去除；二者都有成熟方案，却常因"一行 `requests.get`"起步而被跳过 |
| 2 | HTTP Range 续传 | 客户端发 `Range: bytes=N-`，服务器应回 `206 Partial Content` 与 `Content-Range: bytes N-...`；不支持 Range 的服务器回 200 全量，客户端必须能识别并回退 |
| 3 | 已验证字节（verified bytes） | checkpoint 记录 `verified_bytes` 与这些字节的 `sha256` 前缀；续传前重算磁盘上前缀的哈希，匹配才续传，否则从 0 重下 |
| 4 | 原子写 checkpoint | 先写 `.tmp` 再 `os.replace`，避免 checkpoint 写一半；讲义要求 checkpoint 先于数据落盘并 `fsync`（代码未 fsync） |
| 5 | 流式解压 | `zstandard.ZstdDecompressor().stream_reader` 包住文件对象，按块解压、逐行迭代，不把整个分片读进内存 |
| 6 | MinHash | 对文档的 shingle（重叠 n-gram）集合，用 k 个独立哈希各取最小值得到 k 维签名；任一分量相等的概率 = Jaccard 相似度 s |
| 7 | LSH banding | 把 k = b × r 个分量切成 b 个 band，每 band r 行；至少一个 band 完全相同即碰撞，概率 `1 − (1 − s^r)^b`，阈值约 `(1/b)^(1/r)` |
| 8 | 参数与阈值 | k=128、b=32、r=4 的阈值约 **0.42**（代码 docstring 正确），而不是讲义所说的 0.8；想要 0.8 附近的阈值需要更大的 r（如 b=16、r=8，阈值约 0.71） |
| 9 | Tombstone 而非删除 | 被判重复的文档以 `near_duplicate` + `collided_with`（保留者 `shard:doc`）记入 manifest，保留审计线索，日后可调阈值重判 |
| 10 | Manifest 是契约 | 每分片记录 URL、字节数、文档数、去重后数量、sha256；manifest 自身再算 sha256 写入 `manifest.json.lock`，下游先验哈希再开工 |

### 核心技能（能动手做到）

- [ ] 写出带 `Range` 续传、`206` 校验、200 回退、checkpoint 原子替换的流式下载器，并用本地 HTTP 服务器模拟断线验证续传
- [ ] 给定 shingle 宽度手写任意句子的 shingle 集合并算出真实 Jaccard
- [ ] 用 `1 − (1 − s^r)^b` 计算任意 (b, r) 下的碰撞概率，并为目标阈值选出 (b, r)
- [ ] 解释 MinHash 签名中 `((a·h + b) mod p)` 这一族哈希的作用，以及为什么要用固定种子派生系数
- [ ] 读懂 manifest 与 verdict 记录，从 `collided_with` 追溯每条重复文档的"保留者"
- [ ] 指出本节代码在"已完成分片重跑"、"文档计数"、"manifest 可复现性"上的缺陷并修复

---

## 二、基础自测（选择题）

**Q1.** `.partial.json` checkpoint 里同时记录了 `verified_bytes` 和 `sha256_prefix_hex`。续传前重新计算磁盘上前 `verified_bytes` 字节的 sha256 并与之比较，主要是为了：

- A. 加快续传速度，避免重新下载
- B. 让服务器确认客户端拥有哪些字节
- C. 保证磁盘上的字节确实是当初验证过的那些；若文件被截断、篡改或与 checkpoint 不一致，就丢弃并从 0 重下，而不是在错误的前缀后面追加
- D. 计算最终分片的 sha256，写入 manifest

**Q2.** 两篇文档 Jaccard 相似度 s = 0.5，使用 k = 128、b = 32、r = 4 的 LSH。它们至少在一个 band 上碰撞的概率约为：

- A. 0.873
- B. 0.0625
- C. 0.5
- D. 0.42

**Q3.** 讲义写道："The threshold for typical corpus dedup is s = 0.8, which the LSH research literature reaches with k = 128, b = 32, r = 4"。按阈值近似公式 `(1/b)^(1/r)`，(b=32, r=4) 的实际阈值约为：

- A. 0.80，与讲义一致
- B. 0.125
- C. 0.71
- D. 0.42

**Q4.** 关于 MinHash 签名，下列说法正确的是：

- A. 签名的每个分量是对整篇文档做一次 sha256 的结果
- B. 对一个哈希函数，两篇文档在该分量上取到相同最小值的概率等于它们 shingle 集合的 Jaccard 相似度
- C. 签名长度随文档长度增长
- D. 只要两篇文档有一个 shingle 相同，它们的签名就完全相同

**Q5.** 续传时客户端发送了 `Range: bytes=512-`，但服务器忽略了 Range，返回 `200 OK` 和完整文件。本节 `StreamingDownloader.download` 会：

- A. 把完整文件追加到已有的 512 字节之后
- B. 关闭这个响应，删除分片文件和 checkpoint，把 `resume_from` 置 0，重新发一个不带 Range 的 GET，从头写入
- C. 抛出 `ValueError` 并终止
- D. 跳过前 512 字节后追加剩余部分

**Q6.** `MinHasher(shingle_width=3).shingles("the cat sat on")` 的返回值是：

- A. `["the", "cat", "sat", "on"]`
- B. `["the cat sat on"]`
- C. `["the cat", "cat sat", "sat on"]`
- D. `["the cat sat", "cat sat on"]`

**Q7.** 运行 demo 得到 `kept=8 duplicates=7`。语料共 15 行，其中不同的字符串只有 10 条。下面哪个解释与实际 verdict 记录相符？

- A. 7 条重复中，5 条是跨分片的逐字重复；另外 2 条是 `shard-0000` 内部的"近似重复"（真实 3-gram Jaccard 分别只有 0.364 和 0.5），在 (b=32, r=4) 的低阈值下被判为重复
- B. 7 条重复全部是逐字重复
- C. 去重只在单个分片内部进行，跨分片的重复没有被检测到
- D. 因为 shingle 宽度是 3，所有包含 "the" 的文档都被判为重复

**Q8.** 对同一个 `ManifestWriter` 连续调用两次 `write()`（中间间隔 1 秒以上），返回的 manifest sha256：

- A. 相同，因为 `json.dumps(sort_keys=True)` 保证输出确定
- B. 相同，因为 shards 与 verdicts 没变
- C. 不同，因为 body 中包含 `generated_at = int(time.time())`
- D. 不同，因为 `ManifestWriter` 每次写入都会重新下载分片

---

## 三、动手 / 代码题

**Q9.** 用一个支持 Range 的本地 HTTP 服务器测试：第一次下载在第 2 个 chunk 后断线，第二次成功续传（服务器日志依次收到 `None`、`bytes=512-`，最终 sha256 与源文件一致）。**第三次**对同一个已完整下载的分片再调用 `download()`，却抛出：

```text
urllib.error.HTTPError: HTTP Error 416: Range Not Satisfiable
```

1. 结合下面的代码解释原因。
2. 这个问题在 demo 和测试里为什么没暴露出来？
3. 给出至少两种修复方式。

```python
        if state is not None and state.url == plan.url and self._verify_partial(shard_path, state):
            resume_from = state.verified_bytes
            ...
        request = urllib.request.Request(plan.url)
        if resume_from > 0:
            request.add_header("Range", f"bytes={resume_from}-")
        response = self._opener(request)
```

**Q10.** `download()` 用下面的方式统计文档数，而 `process_shard` 用 `ZstdDocIterator` 逐行迭代并为每行给出 verdict：

```python
            while True:
                chunk = reader.read(self.chunk_bytes)
                if not chunk:
                    break
                decompressed_bytes += len(chunk)
                document_count += chunk.count(b"\n")
```

```python
    def __iter__(self) -> Iterator[str]:
        for line in self._text:
            line = line.rstrip("\n")
            if line:
                yield line
```

分别对解压后内容为 `b"a b c\n\nd e f\n"` 和 `b"a b c\nd e f"` 的两个分片，写出 `document_count` 与 `kept_count + duplicate_count`，指出不一致的原因并给出修复。

**Q11.** 你希望去重阈值落在 s ≈ 0.8 附近（讲义所说的典型值），签名长度固定 k = 128。

1. 对 (b, r) ∈ {(32, 4), (16, 8), (8, 16)}，计算阈值近似 `(1/b)^(1/r)` 以及 s = 0.5、0.8 时的碰撞概率。
2. 选出最合适的一组，并说明它在 demo 语料上会带来什么变化。
3. 为什么不能只看阈值、还要看曲线两端？

**Q12.** 讲义"Checkpoint before write"一段要求：先把 `.partial.json` `fsync` 到磁盘，再追加分片字节；课程自带的 `quiz.json` 解释说这样"a crash leaves the verified offset trailing or equal to the file, never ahead"。代码的写入顺序是：

```python
                    self._write_checkpoint(checkpoint_path, new_state)
                    out.write(buf)
                    out.flush()
```

1. 若进程恰好在 `_write_checkpoint` 之后、`out.write` 之前崩溃，checkpoint 与文件的关系是什么？`quiz.json` 的说法对吗？
2. 下次运行时代码会怎么处理？会损坏数据吗？
3. 代码与讲义在持久化上还差了什么？如果要做到"崩溃后既不损坏、也不丢进度"，你会怎么改？

---

## 四、面试高频题

**Q13.**（基础必考）预训练语料为什么要去重？精确哈希去重和 MinHash + LSH 近似去重各能解决什么问题？

**Q14.**（原理深挖）推导 LSH banding 的碰撞概率 `1 − (1 − s^r)^b`，并说明 b、r、shingle 宽度分别如何影响去重的假阳性与假阴性。

**Q15.**（工程实践）设计一个能可靠下载 200 GB 语料的下载器。除了本节已经实现的 Range 续传和前缀哈希，你还会加什么？

**Q16.**（场景设计）语料规模到万亿 token、数十亿文档时，本节的单机内存 LSH 去重怎么扩展？还需要哪些层次的去重？

**Q17.**（追问型）讲义说"manifest 是契约"。一个好的数据 manifest 应该包含什么？本节的 manifest 有哪些地方不满足"可复现、可校验"？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："On startup the downloader reads the checkpoint, recomputes `sha256_prefix` over the on-disk bytes, and only resumes if the recomputed hash matches... Silent corruption is impossible because the verified bytes are checked, not assumed." 代码 `_verify_partial` 先比较文件大小是否等于 `verified_bytes`，再逐块计算 sha256 比较。

- A 错：哈希校验本身要重读全部已下载字节，是额外开销而非加速。
- B 错：服务器完全不知道这个哈希，Range 请求只告诉它起始偏移。
- D 错：最终写入 manifest 的 sha256 来自下载过程中的 `rolling` 哈希；checkpoint 的前缀哈希只用于续传判断（虽然下载完成时二者数值相同）。

### Q2 — 答案：A

`s^r = 0.5^4 = 0.0625`（一个 band 全部 4 行都相同的概率）；32 个 band 都不碰撞的概率 `(1 − 0.0625)^32 ≈ 0.127`；至少一个碰撞 `≈ 0.873`（已计算验证）。

- B 是单个 band 的碰撞概率。
- C 是单个分量相等的概率。
- D 是 (32, 4) 的阈值近似，不是 s = 0.5 时的概率。

### Q3 — 答案：D

`(1/32)^(1/4) ≈ 0.42`。代码中 `LSHIndex` 的 docstring 写的正是"For (b=32, r=4) the threshold is near s = 0.42"，**讲义正文的 0.8 是错的**。实测 (32, 4) 的 S 曲线：s = 0.3 时碰撞概率已有 0.229，s = 0.5 时 0.873，s = 0.8 时约 1.0。

- B（0.125）是 (b=64, r=2) 的阈值；C（0.71）是 (b=16, r=8) 的阈值。

### Q4 — 答案：B

对随机哈希函数 h，集合 A ∪ B 中哈希值最小的元素等可能是其中任意一个；它同时属于 A 和 B 的概率就是 `|A∩B| / |A∪B|`，即 Jaccard。讲义："Two documents with Jaccard similarity s have a probability s of agreeing on any single component of the signature." 这也是 `jaccard_estimate`（相等分量的比例）是无偏估计的原因。

- A 错：每个分量是"对所有 shingle 哈希后取最小值"。
- C 错：签名长度固定为 `num_hashes`（这正是 MinHash 的价值："fixed space"）。
- D 错：只有一个 shingle 相同，大部分分量仍会不同。

### Q5 — 答案：B

代码检查 `status != 206` 或 `Content-Range` 不以 `bytes {resume_from}-` 开头时，关闭响应、`resume_from = 0`、重置 `rolling` 哈希、删除分片与 checkpoint，然后 `self._opener(urllib.request.Request(plan.url))` 重新整体下载，并以 `"wb"` 模式写入。

- A 是最危险的错误实现：会得到"512 字节前缀 + 完整文件"的损坏分片。
- C 错：不会报错，而是安全回退。
- D 错：代码没有实现"跳过前 N 字节"的回退（那是另一种可选方案）。
- 补充：`file://` URL 的响应 `status` 为 `None`（实测），所以对本地文件的"续传"永远走这条回退路径。

### Q6 — 答案：D

`tokens = ["the", "cat", "sat", "on"]`，宽度 3 的滑动窗口从 `start = 0` 到 `len(tokens) − 3 = 1`，得到 `"the cat sat"` 和 `"cat sat on"`。

- A 是宽度 1；C 是宽度 2。
- B 是 token 数**少于**宽度时的行为：例如 `shingles("a b")` 返回 `["a b"]`（整段作为一个 shingle）；空串返回 `[]`，签名退化为全 `MAX_UINT64` 的哨兵值。

### Q7 — 答案：A

实际 verdict 记录（已运行验证）：

- `shard-0000`：doc 1（alignment 第二句）→ `collided_with: shard-0000:0`；doc 3（transformers 的倒装句）→ `shard-0000:2`。这两对并不是同一篇文档：真实 3-gram Jaccard 分别为 **0.364**（8/22）和 **0.5**（6/12），MinHash 估计为 0.383 和 0.531。(32, 4) 下碰撞概率分别约 0.43 和 0.87。
- `shard-0001` doc 0、1 是 `base[3]`、`base[4]` 的逐字重复；`shard-0002` doc 0–2 是 `base[6..8]` 的逐字重复。共 5 条。

注意 `shard-0001:0`（即 `base[3]`）的 `collided_with` 是 `shard-0000:2` 而不是 `shard-0000:3`——因为 `shard-0000:3` 自己已被判重复、没有插入索引，指针总是指向**保留者**。

- B 错：有 2 条不是逐字重复。
- C 错：`Dedup` 使用同一个 `LSHIndex` 跨所有分片。
- D 错：单个常见词不构成 3-gram 重叠。

### Q8 — 答案：C

`write()` 构造的 body 含 `"generated_at": int(time.time())`，所以即使数据完全相同，manifest 文本和 sha256 也会随时间变化（实测两次写入的 sha 不同）。

- A 错：`sort_keys=True` 只保证键的顺序确定，管不了值。
- B 错：时间戳是值的一部分。
- D 错：`write()` 不涉及下载。

这与讲义"Manifest as merge gate... The link between code and data is git"相矛盾：同一份数据每次都产生新的 manifest 哈希，无法用哈希判断"数据有没有变"。修复：把时间戳移出参与哈希的部分（或单独存放），只对内容字段求哈希。

### Q9 — 参考答案

1. **原因**：下载完成后 `.partial.json` 没有被删除或标记为"已完成"，其中 `verified_bytes` 等于文件总长（实测 9060）。再次运行时校验通过，`resume_from = 9060`，于是发送 `Range: bytes=9060-`。按 RFC 7233，起始偏移 ≥ 资源长度时服务器返回 **416 Range Not Satisfiable**；`urllib.request.urlopen` 对 4xx 状态直接抛 `HTTPError`，代码只处理了"返回 200 忽略 Range"的情况，没有处理 416，于是整个流程中断。
2. **为什么没暴露**：demo 每次都用新的 `TemporaryDirectory` 作为缓存，从不重跑；测试全部用 `file://` URL，而 `FileHandler` 不理会 Range、响应 `status` 为 `None`，代码走"回退整体重下"分支。也就是说，demo 和测试**从未真正走过 206 续传路径**，也没有覆盖已完成分片的重跑。
3. **修复方式**（任选其二）：
   - 下载完成后把 checkpoint 改写为 `{"complete": true, "sha256": ...}` 或改名为 `.done.json`；`download()` 开头若发现已完成且 sha256 校验通过，直接跳过网络请求。
   - 在 `ShardPlan.expected_size` 已知时（例如先发 HEAD 取 `Content-Length`），`verified_bytes == expected_size` 就视为完成。
   - 捕获 `urllib.error.HTTPError`，若 `code == 416` 且响应头 `Content-Range: bytes */<total>` 中的 total 等于 `verified_bytes`，视为已完成；否则清理后整体重下。
   - 生产中还要配合 `If-Range: <ETag>`，避免远端文件已更新时把新旧两个版本拼在一起（见 Q15）。

### Q10 — 参考答案

实测结果：

| 解压内容 | `document_count`（数 `\n`） | `kept + duplicate`（迭代行数） |
|----------|---------------------------|-------------------------------|
| `b"a b c\n\nd e f\n"` | 3 | 2 |
| `b"a b c\nd e f"` | 1 | 2 |

原因：两处对"文档"的定义不同。`document_count` 数的是换行符个数——空行会被算作一篇，最后一行若没有结尾换行则不会被计入；`ZstdDocIterator` 则跳过空行、并且会产出没有结尾换行的最后一行。于是 manifest 中可能出现 `document_count ≠ kept_count + duplicate_count`，下游若用它做一致性校验会误报（或漏报）。

修复：只保留一种计数方式。最简单的做法是去掉 `download()` 里的二次解压计数，在 `process_shard` 中用迭代结果回填：

```python
    result = dataclasses.replace(
        result,
        document_count=kept + duplicates,
        kept_count=kept,
        duplicate_count=duplicates,
    )
```

`decompressed_bytes` 也可以在同一次迭代中累加（`len(line.encode()) + 1`），从而把分片的解压次数从两次降到一次。此外讲义说文档是 JSONL，而代码把每行当作纯文本，没有 `json.loads` 取 `"text"` 字段，生产中还要处理解析失败的行。

### Q11 — 参考答案

1. 计算结果（已运行验证）：

| (b, r) | 阈值 `(1/b)^(1/r)` | P(s=0.5) | P(s=0.8) |
|--------|-------------------|----------|----------|
| (32, 4) | 0.42 | 0.873 | ≈1.000 |
| (16, 8) | 0.71 | 0.061 | 0.947 |
| (8, 16) | 0.88 | 0.0001 | 0.204 |

2. 选 **(16, 8)**：s = 0.8 的文档有约 95% 概率被抓到，s = 0.5 的只有约 6% 被误杀。用它重跑 demo（已验证），结果变为 `shard-0000` 5 条全部保留、总计 kept = 10、duplicates = 5——只删除 5 条逐字重复，Jaccard 0.364 与 0.5 的那两对不再被误判。(8, 16) 的阈值太高，s = 0.8 的近似重复约 80% 会漏掉。
3. 阈值只是 S 曲线最陡的位置。真正的代价在两端：左端（低相似度）的碰撞概率就是**假阳性率**，会删掉不同的文档、损失数据多样性；右端（高相似度）的不碰撞概率就是**假阴性率**，会放过重复文档。还要考虑 shingle 宽度对 Jaccard 本身的影响：同一对 alignment 句子，宽度 3/5/9 时的真实 Jaccard 分别是 0.364、0.300、0.125（实测），宽度越大，同样的改写会显得越"不相似"。实践中常在 LSH 候选之后再计算一次精确 Jaccard（或用签名估计）做二次确认。

### Q12 — 参考答案

1. checkpoint 写成 `verified_bytes = N + len(buf)`，但文件只有 N 字节——**checkpoint 领先于文件**。所以 `quiz.json` 中"never ahead"的说法是错的：先写 checkpoint 恰恰会让 checkpoint 领先；反过来"先写数据"才会让 checkpoint 落后。
2. 下次运行 `_verify_partial` 首先比较 `actual_size != state.verified_bytes`，不相等就返回 False，代码删除分片与 checkpoint、从 0 重下。**不会损坏数据，但会丢失全部进度**。实际上无论哪种写入顺序，这个"大小必须完全相等"的检查都能防止损坏；讲义描述的"重复后缀破坏文件"在本实现中不会发生。
3. 差距与改进：
   - 代码没有 `fsync`：`out.flush()` 只把数据交给操作系统缓存，`_write_checkpoint` 也没有对 `.tmp` 文件和目录 `fsync`，断电时两者的落盘顺序无法保证。
   - 每个 64 KiB chunk 都重写一次 checkpoint，200 GB 就是约 300 万次小文件写，开销不小；可以每 N MB 写一次。
   - 更稳妥的顺序是"**先写数据并 fsync，再原子写 checkpoint 并 fsync**"，于是 checkpoint 只会落后或相等；续传时若文件比 `verified_bytes` 长，先 `truncate(verified_bytes)`，再校验前缀哈希，然后从 `verified_bytes` 继续。这样崩溃后最多重下最后一个 chunk。
   - 前缀哈希可以分段保存（每 64 MB 一个哈希），避免续传时重读整个大文件做校验。

### Q13 — 参考回答要点

- **为什么去重**：重复数据会让模型过度记忆特定文本（隐私与版权风险上升）、浪费算力（同样的 loss 曲线付两次钱）、扭曲数据分布；讲义还强调去重要放在 tokenization 之前，因为"Running it twice on the same document is twice the cost for the same loss curve"。另外要防止评测集泄漏进训练集。
- **精确哈希去重**：对规范化后的全文求 sha256/MD5，O(1) 查表。只能抓逐字重复。
- **MinHash + LSH**：抓近似重复——讲义举例"同一篇 Wikipedia 文章带三种不同页脚""同一代码文件不同 license 头""同一博客每个链接带跟踪参数"。每篇文档一个固定长度签名，每个签名 b 次桶查找，整体近似线性、单次查询亚线性，无需两两比较（n² 不可行）。
- 实践顺序：URL 去重 → 精确哈希去重 → MinHash 近似去重（→ 子串级去重）。
- 常见误区：以为 MinHash 估计的是余弦相似度；以为 LSH 碰撞就一定是重复（其实是候选，需看阈值与假阳性率）。

### Q14 — 参考回答要点

- **推导**：单个分量相等的概率为 s；一个 band 的 r 个分量（来自独立哈希）全部相等的概率为 `s^r`；b 个 band 都不全等的概率为 `(1 − s^r)^b`；至少一个 band 碰撞的概率为 `1 − (1 − s^r)^b`。
- **阈值**：曲线最陡处约在 `s ≈ (1/b)^(1/r)`。
- **r 增大**：单 band 更难碰撞，曲线右移、更陡 → 假阳性下降、假阴性上升。
- **b 增大**：碰撞机会更多，曲线左移 → 假阴性下降、假阳性上升，索引内存随 b 线性增长。
- **k = b·r 固定时**：在 b 与 r 之间权衡；想要更陡的曲线就需要更大的 k（更多计算与存储）。
- **shingle 宽度**：宽度小（如 3）时常见短语造成大量偶然重叠，Jaccard 普遍偏高；宽度大时一次小改动会破坏很多 shingle，Jaccard 偏低。本节 demo 中同一对句子在宽度 3/5/9 下 Jaccard 为 0.364/0.300/0.125。讲义练习 1 要求比较 3、5、9 并为默认值辩护（代码默认 5，demo 用 3）。
- 加分点：指出讲义"k=128、b=32、r=4 对应阈值 0.8"的错误，正确值约 0.42。

### Q15 — 参考回答要点

- 本节已有：流式写盘、`Range` 续传、`206` + `Content-Range` 校验、200 回退、前缀 sha256、原子 checkpoint、URL 变化即重下。
- **还要加**：
  - **远端版本校验**：记录 `ETag` / `Last-Modified`，续传时带 `If-Range`；否则远端文件更新后会把旧前缀与新后缀拼在一起，而本地前缀哈希完全无法发现（它只校验本地已有的字节）。
  - **完整性**：用源站提供的 sha256/MD5 校验最终文件；核对 `Content-Length` 与 `expected_size`（代码中 `expected_size` 从未被赋值和检查）。
  - **完成标记**：避免已完成分片重跑时触发 416（见 Q9）。
  - **重试策略**：指数退避 + 抖动、超时设置（代码 `urlopen` 未设 `timeout`，网络卡死时会无限等待）、区分可重试（5xx、连接重置）与不可重试（404、403）错误。
  - **持久化**：`fsync` 数据与 checkpoint，写入顺序见 Q12；降低 checkpoint 频率。
  - **并发**：多分片并行下载、限速、连接复用；单分片也可以多段 Range 并发。
  - **可观测性**：进度、吞吐、失败率日志；`--resume-only`（讲义练习 3）防止 CI 意外重拉 200 GB；`--cache-dir` 作为一等参数。
  - **安全**：限制 URL scheme（代码已限制为 http/https/file）、校验路径不越界。

### Q16 — 参考回答要点

- **分层去重**：URL 规范化去重 → 全文精确哈希 → MinHash 近似去重 → 段落/子串级去重（如后缀数组找长重复片段）→ 与评测集的去污染（n-gram 重叠检查）。
- **扩展 LSH**：
  - 讲义提出按第一个 band 的哈希对 LSH 索引分区、分区存盘，新签名只查它会落入的分区；代价是每篇文档多一次磁盘读。
  - 分布式方案：把 (band_id, band_hash) 作为 key，用 MapReduce/Spark 做 shuffle，同 key 的文档归为候选对；再用并查集（union-find）求连通分量，每个分量保留一篇。
  - 签名计算可并行；签名本身可压缩（如只存 32 位）。
- **保留策略**：不只是"先到先得"（本节代码就是先到者成为保留者），可以按质量分、来源可信度、时间新旧选保留者。
- **Tombstone**：记录被丢文档与保留者的映射，便于审计和调整阈值后重判（讲义 "Tombstone, not delete"）。
- **代价权衡**：去重过度会损失多样性与长尾知识；常对不同来源（代码、网页、书籍）使用不同阈值。

### Q17 — 参考回答要点

- **应包含**：每个分片的来源 URL 与版本（ETag）、压缩/解压字节数、文档数、去重后保留数、内容 sha256；去重参数（shingle 宽度、k、b、r、种子）；代码版本（git commit）；verdict/tombstone 记录；manifest 自身的哈希，写入锁文件并提交到 git。
- **下游契约**：tokenization 读 manifest 而不是目录列表；分片缺失或哈希不符就拒绝启动（fail closed，讲义练习 5）。
- **本节不足**：
  - `generated_at` 参与哈希，相同数据得到不同 manifest sha（见 Q8），无法做"数据未变"的判断；
  - 记录的 sha256 是**下载的原始压缩分片**的哈希；讲义说的"final shard file"在代码里并不存在——保留下来的文档没有被写成新的去重后分片，下游只能拿原始分片 + verdict 列表自行过滤；
  - 没有记录去重参数，换参数后无法知道旧 verdict 是怎么来的；
  - `document_count` 与迭代行数可能不一致（见 Q10）；
  - 没有实现启动时校验 `manifest.json.lock`（只写不读）；
  - verdicts 内联在 manifest 中，文档上亿时 manifest 会变成数十 GB，应拆成按分片存放的 verdict 文件，manifest 只记录其哈希。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 03 用于预训练的数据管道](../../../10-llms-from-scratch/03-data-pipelines/docs/zh.md)：预训练数据的整体流程（采集、过滤、去重、分词、打包）。
- [阶段 00 · 09 数据管理](../../../00-setup-and-tooling/09-data-management/docs/zh.md)：数据集版本化与存储组织。
- [阶段 19 · 30 从零实现 BPE Tokenizer](../../30-bpe-tokenizer-from-scratch/docs/zh.md)、[阶段 19 · 31 使用滑动窗口构建分词后的数据集](../../31-tokenized-dataset-sliding-window/docs/zh.md)：讲义列出的先修（30–37 课）中与数据最相关的两课。
- [阶段 05 · 14 信息检索与搜索](../../../05-nlp-foundations-to-advanced/14-information-retrieval-search/docs/zh.md)：Jaccard、n-gram、近似检索的背景。

### 本节被哪些后续内容用到
- [阶段 19 · 43 HDF5 格式的分词语料](../../43-hdf5-tokenized-corpus/docs/zh.md)：消费本节 manifest，把去重后的文档分词并写成 HDF5。
- [阶段 19 · 44 带线性 Warmup 的余弦学习率](../../44-cosine-lr-warmup/docs/zh.md)、[阶段 19 · 45 Gradient Clipping 与 Mixed Precision](../../45-gradient-clipping-amp/docs/zh.md)：在该语料上训练。
- [阶段 19 · 47 Checkpoint 保存与恢复](../../47-checkpoint-save-resume/docs/zh.md)、[阶段 19 · 80 分片 Checkpoint 与原子恢复](../../80-checkpoint-sharded-resume/docs/zh.md)：同样的"原子写 + 校验 + 续跑"思想用于训练状态。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../../18-ethics-safety-alignment/26-model-system-dataset-cards/docs/zh.md)：manifest 中的来源与去重记录是数据集卡的事实基础。

### 延伸关键词
`HTTP Range / 206 / 416` · `ETag / If-Range` · `fsync / write-ahead log` · `os.replace 原子替换` · `Zstandard frame` · `shingling` · `MinHash` · `LSH banding S-curve` · `union-find 连通分量` · `suffix array 去重` · `decontamination` · `content-addressed manifest`
