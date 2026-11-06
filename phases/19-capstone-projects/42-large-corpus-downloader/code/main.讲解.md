# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 42 节 大规模语料下载器 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（不到 0.2 秒，全部在临时目录中完成，运行后不留文件）；测试：`python -m unittest discover tests -v` 或 `python -m pytest -q tests` ｜ **依赖**：`zstandard`（第三方，`pip install zstandard`，缺失时脚本以 `SystemExit` 给出安装提示）；其余 `hashlib`、`urllib`、`struct`、`dataclasses`、`pathlib`、`tempfile` 等均为标准库。无需网络（demo 用 `file://` URL）

> 本目录下的 `tests/__init__.py` 是一个 **0 字节空文件**，作用只是把 `tests/` 标记为 Python 包，使 `unittest discover`/pytest 能以包的方式导入测试模块；它没有任何逻辑，故并入本讲解，不单独成篇。

---

## 1. 这份代码在考察什么

这份代码实现了预训练数据流水线的第一站——"把语料可靠地落到磁盘上，并去掉重复文档"。它覆盖了讲义的四个学习目标：

1. **流式下载与解压**：`urllib` 按 64 KiB 块读取，`zstandard` 流式解压，逐行迭代文档，不把整个分片读入内存。
2. **可验证的断点续传**：`.partial.json` checkpoint 记录 `verified_bytes` 和这些字节的 sha256；续传前重算校验，用 HTTP `Range` 请求从断点继续，并校验 `206` 与 `Content-Range`。
3. **MinHash + LSH 近似去重**：对每篇文档的词级 shingle 计算 128 维 MinHash 签名，切成 32 个 band 做桶查找，碰撞即判为近似重复。
4. **Manifest 契约**：每个分片记录字节数、文档数、保留/重复数与 sha256，manifest 本身再算一次 sha256 写入 `.lock` 文件。

> 一句话：**数据工程的可靠性来自"先校验、再信任"——续传前校验已下载的字节，去重时保留可追溯的 tombstone，下游开工前校验 manifest 哈希**。同时，本代码在已完成分片重跑、计数口径、manifest 可复现性和 LSH 阈值上都有值得指出的缺陷。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CHUNK_BYTES` 等常量 | 模块常量 | 64 KiB 块大小、128 个哈希、32 个 band、shingle 宽度 5、`2^64−1`、梅森素数 `2^61−1` | 参数 |
| `ShardPlan` / `ShardResult` / `DocVerdict` / `CheckpointState` | dataclass | 计划、分片结果、单文档判决、续传状态 | 数据契约 |
| `_hash_seed_pair` | 函数 | 由种子派生哈希系数 `(a, b)` | 可复现的哈希族 |
| `MinHasher` | 类 | 切 shingle、计算 MinHash 签名 | MinHash |
| `LSHIndex` | 类 | 按 band 分桶、查询碰撞、估计 Jaccard | LSH |
| `Dedup` | 类 | 签名 → 查询 → 判 `keep` 或 `near_duplicate` → 保留者入索引 | 流式去重 |
| `ZstdDocIterator` | 类 | 包装 zstd 流 + 文本流，逐行产出非空文档 | 流式解压 |
| `StreamingDownloader` | 类 | Range 续传、前缀校验、checkpoint 原子写、二次解压计数 | 断点续传 |
| `ShardPlanner` | 类 | URL 列表 → `shard-0000` 编号的计划 | 分片规划 |
| `ManifestWriter` | 类 | 收集分片结果与 verdict，写 `manifest.json` 与 `.lock` | Manifest 契约 |
| `process_shard` | 函数 | 下载 → 迭代 → 去重 → 回填计数 → 记入 manifest | 编排 |
| `build_demo_corpus` / `run_demo` | 函数 | 生成 3 个带重复的 zst 分片，跑完整流程并打印 | 演示 |

数据流：`build_demo_corpus` 写出 3 个 `.zst` 并返回 `file://` URL → `ShardPlanner.from_urls` → 对每个计划 `process_shard`：`StreamingDownloader.download`（写分片 + checkpoint，解压计数）→ `ZstdDocIterator` 逐行 → `Dedup.evaluate`（`MinHasher.signature` → `LSHIndex.query/insert`）→ `ManifestWriter.add_verdict/add_shard` → `ManifestWriter.write` 输出 manifest 与 lock。

---

## 3. 逐段精讲

### 3.1 导入守卫与常量

```python
try:
    import zstandard as zstd
except ImportError as exc:
    raise SystemExit(
        "zstandard is required for this lesson. Install with: pip install zstandard"
    ) from exc

CHUNK_BYTES = 1 << 16
DEFAULT_NUM_HASHES = 128
DEFAULT_BANDS = 32
DEFAULT_SHINGLE_WIDTH = 5
MAX_UINT64 = (1 << 64) - 1
MERSENNE_PRIME = (1 << 61) - 1
```

- 缺少第三方依赖时用 `SystemExit` 给出明确提示，比一长串 traceback 友好；`from exc` 保留原始异常链。
- `1 << 16 = 65,536` 字节（64 KiB），是每次网络读、文件读、解压读的块大小。
- `MERSENNE_PRIME = 2^61 − 1` 是 universal hashing 中常用的模数（梅森素数，取模可以用位运算加速）。

### 3.2 四个 dataclass：数据契约

```python
@dataclass
class CheckpointState:
    url: str
    verified_bytes: int
    expected_size: int | None
    sha256_prefix_hex: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "CheckpointState":
        data = json.loads(text)
        return cls(
            url=str(data["url"]),
            verified_bytes=int(data["verified_bytes"]),
            expected_size=(int(data["expected_size"]) if data.get("expected_size") is not None else None),
            sha256_prefix_hex=str(data["sha256_prefix_hex"]),
        )
```

- `CheckpointState` 是讲义中 `.partial.json` 的结构：URL、已验证字节数、期望大小、前缀 sha256。`from_json` 对每个字段显式做类型转换，配合 `_read_checkpoint` 中捕获 `JSONDecodeError/KeyError/ValueError`，损坏的 checkpoint 会被当作"没有 checkpoint"处理，而不是让程序崩溃。
- `ShardResult` 对应 manifest 的一行；`to_manifest_row` 直接 `asdict`。
- `DocVerdict` 的 `verdict` 只有 `"keep"`/`"near_duplicate"` 两种值，`collided_with` 是保留者的 `"shard:doc"`——这就是讲义 "Tombstone, not delete" 的落地。
- `ShardPlan.expected_size` 默认 `None`。⚠️ 整个代码中**没有任何地方给它赋值，也没有检查最终大小是否等于它**——字段存在但未生效。
- `int | None` 是 Python 3.10+ 的联合类型写法；配合 `from __future__ import annotations`，注解不会在运行时求值。

### 3.3 MinHasher：shingle 与签名

```python
def _hash_seed_pair(seed: int) -> tuple[int, int]:
    digest = hashlib.blake2b(seed.to_bytes(8, "little"), digest_size=16).digest()
    a = int.from_bytes(digest[:8], "little") | 1  # ensure a is non-zero
    b = int.from_bytes(digest[8:], "little")
    return a, b
```

- 第 i 个哈希函数的系数由 `blake2b(i)` 派生，**不依赖随机数生成器**，因此不同机器、不同进程得到同一族哈希——签名可以跨运行比较、可以存盘复用。
- `| 1` 把最低位置 1，保证 `a` 是奇数、非零。

```python
    def shingles(self, text: str) -> list[str]:
        tokens = text.split()
        if len(tokens) < self.shingle_width:
            return [" ".join(tokens)] if tokens else []
        shingles: list[str] = []
        for start in range(len(tokens) - self.shingle_width + 1):
            shingles.append(" ".join(tokens[start : start + self.shingle_width]))
        return shingles
```

- **词级** shingle：按空白切词后取宽度为 w 的滑动窗口。`"the cat sat on"`、w = 3 → `["the cat sat", "cat sat on"]`。
- 词数少于 w 时把整段作为一个 shingle；空串返回 `[]`。
- 注意：返回的是**列表**而非集合，重复的 shingle 会被重复哈希，但对"取最小值"没有影响；Jaccard 的定义针对集合。

```python
    def signature(self, text: str) -> list[int]:
        shingles = self.shingles(text)
        if not shingles:
            return [MAX_UINT64] * self.num_hashes
        shingle_hashes = [self._hash_shingle(s) for s in shingles]
        sig: list[int] = []
        for a, b in self._coefficients:
            best = MAX_UINT64
            for h in shingle_hashes:
                candidate = ((a * h + b) % MERSENNE_PRIME) & MAX_UINT64
                if candidate < best:
                    best = candidate
            sig.append(best)
        return sig
```

- 每个 shingle 先用 `blake2b(digest_size=8)` 映射成一个 64 位整数 `h`（只算一次），然后对 128 组 `(a, b)` 分别计算 `(a·h + b) mod p`，取最小值——这就是 128 个"独立"哈希函数的最小值。
- 复杂度 `O(num_hashes × num_shingles)`，纯 Python 双重循环；128 × 几十个 shingle 在 demo 中无压力，但对真实语料太慢，生产中用 NumPy 向量化（`(A[:,None] * H[None,:] + B[:,None]) % p` 再 `min(axis=1)`）或 C 扩展。
- ⚠️ 两个细节：
  - `% MERSENNE_PRIME` 的结果已经 < 2^61，后面的 `& MAX_UINT64` 是**空操作**；`_hash_seed_pair` docstring 中写的 "mod 2^64" 并没有真正起作用。
  - 经典 universal hashing 要求输入 `x < p`，而 `h` 是 64 位、可能大于 `2^61 − 1`。取模后仍然可用，但严格的"两两独立"性质不再完全成立。对教学 demo 影响不大。
- 空文档得到全 `MAX_UINT64` 的哨兵签名：所有空文档的签名完全相同，第一篇之后的空文档都会被判为重复。

### 3.4 LSHIndex：banding

```python
    def __init__(self, num_hashes: int, bands: int = DEFAULT_BANDS) -> None:
        if bands <= 0 or num_hashes % bands != 0:
            raise ValueError(f"bands ({bands}) must divide num_hashes ({num_hashes})")
        self.rows = num_hashes // bands
        self._buckets: list[dict[bytes, list[str]]] = [{} for _ in range(bands)]
        self._signatures: dict[str, list[int]] = {}

    @staticmethod
    def _band_key(band: list[int]) -> bytes:
        return hashlib.blake2b(b"".join(struct.pack("<Q", v) for v in band), digest_size=16).digest()
```

- 128 个分量切成 32 个 band，每 band `rows = 4` 个分量。
- `struct.pack("<Q", v)` 把每个 64 位无符号整数打包成 8 字节小端序，拼接后再用 blake2b 压成 16 字节的桶键。每个 band 有自己独立的字典 `self._buckets[i]`，所以不同 band 的相同键不会互相干扰。
- `query` 依次检查每个 band，第一个命中就返回桶里的第一个文档 id（即最早插入的保留者）；`insert` 用 `setdefault(key, []).append(doc_id)` 把文档加进 32 个桶。
- `jaccard_estimate`：相等分量的比例，是 Jaccard 的无偏估计。

docstring 中的阈值说明是**正确的**："For (b=32, r=4) the threshold is near s = 0.42"。⚠️ 但讲义正文说 "k = 128, b = 32, r = 4" 达到的是 `s = 0.8` 的阈值，这与公式不符。实测 S 曲线：

| s | 0.2 | 0.3 | 0.42 | 0.5 | 0.6 | 0.8 |
|---|-----|-----|------|-----|-----|-----|
| P(碰撞)，b=32 r=4 | 0.050 | 0.229 | 0.636 | 0.873 | 0.988 | ≈1.0 |
| P(碰撞)，b=16 r=8 | ≈0 | 0.001 | 0.015 | 0.061 | 0.237 | 0.947 |

若真想要 0.8 附近的阈值，(16, 8) 更合适（阈值约 0.71）。docstring 里提到的 (b=20, r=5) 需要 k = 100，与默认的 128 不整除。

### 3.5 Dedup：先查后插的流式去重

```python
    def evaluate(self, shard_id: str, doc_index: int, text: str) -> DocVerdict:
        sig = self.hasher.signature(text)
        keeper = self.index.query(sig)
        if keeper is not None:
            return DocVerdict(shard_id=shard_id, doc_index=doc_index,
                              verdict="near_duplicate", collided_with=keeper)
        doc_id = f"{shard_id}:{doc_index}"
        self.index.insert(doc_id, sig)
        return DocVerdict(shard_id=shard_id, doc_index=doc_index, verdict="keep")
```

- **只有保留者进入索引**；被判重复的文档不插入。因此 `collided_with` 永远指向一个保留者。这也意味着"A 与 B 相似、B 与 C 相似、但 A 与 C 不相似"时，若 B 被丢弃，C 可能被保留——链式相似不会传递。
- 先到先得：同一组近似重复中，最早出现的那篇被保留，与内容质量无关。
- 只查询不做二次确认：LSH 碰撞就直接判重复，没有再用 `jaccard_estimate` 或精确 Jaccard 复核。在低阈值 (32, 4) 下，这会把真实 Jaccard 只有 0.364 的两句话判为重复（见第 6 节）。

### 3.6 ZstdDocIterator：两层流包装

```python
    def __init__(self, raw_reader: io.RawIOBase | io.BufferedIOBase) -> None:
        self._dctx = zstd.ZstdDecompressor()
        self._stream = self._dctx.stream_reader(raw_reader)
        self._text = io.TextIOWrapper(self._stream, encoding="utf-8", newline="")

    def __iter__(self) -> Iterator[str]:
        for line in self._text:
            line = line.rstrip("\n")
            if line:
                yield line
```

- 字节文件 → `stream_reader`（按需解压的二进制流）→ `TextIOWrapper`（按 UTF-8 解码、按行切分的文本流）。内存中只有当前缓冲块与当前行。
- `newline=""` 表示不做换行符转换，`\r\n` 中的 `\r` 会留在行尾（`rstrip("\n")` 不会去掉它）。
- `__iter__` 是**生成器**：跳过空行，逐行 `yield`。
- ⚠️ 讲义说迭代的是 "JSONL documents"，但代码把每行当作纯文本，没有 `json.loads`；demo 语料也是纯文本行。真实语料（如 `{"text": ..., "url": ...}`）需要先解析再取文本字段。
- ⚠️ 讲义描述的是"网络 → 解压器 → 文档迭代器"的端到端流式管线；实际实现是**先完整下载压缩分片到磁盘**，再从磁盘读取解压。压缩分片会完整落盘（这对续传是必要的），只是"解压后的内容从不完整驻留内存"这一点成立。

### 3.7 StreamingDownloader：续传的核心

**(1) 路径与 checkpoint 的原子写**

```python
    def _write_checkpoint(self, checkpoint_path: Path, state: CheckpointState) -> None:
        tmp = checkpoint_path.with_suffix(".json.tmp")
        tmp.write_text(state.to_json(), encoding="utf-8")
        os.replace(tmp, checkpoint_path)
```

- 每个分片两个文件：`shard-0000.zst` 与 `shard-0000.partial.json`。
- `with_suffix(".json.tmp")` 把 `shard-0000.partial.json` 变成 `shard-0000.partial.json.tmp`（只替换最后一个后缀 `.json`）。
- `os.replace` 在同一文件系统内是**原子**的：读者要么看到旧 checkpoint，要么看到新 checkpoint，不会看到写了一半的文件。
- ⚠️ 没有 `fsync`：讲义明确要求"The `.partial.json` must be `fsync`-ed before the bytes are appended"，代码只做了原子替换，断电时数据可能仍在页缓存中。

**(2) 校验已下载的前缀**

```python
    def _verify_partial(self, shard_path: Path, state: CheckpointState) -> bool:
        if not shard_path.exists():
            return False
        actual_size = shard_path.stat().st_size
        if actual_size != state.verified_bytes:
            return False
        hasher = hashlib.sha256()
        with shard_path.open("rb") as fh:
            remaining = state.verified_bytes
            while remaining > 0:
                buf = fh.read(min(self.chunk_bytes, remaining))
                ...
        return hasher.hexdigest() == state.sha256_prefix_hex
```

- 两道关：文件大小必须**恰好等于** `verified_bytes`；前缀 sha256 必须匹配。任何一道失败都会导致从 0 重下。
- 大小相等的要求很严格：无论崩溃发生在"写 checkpoint 后、写数据前"（checkpoint 领先）还是反过来（文件领先），都会被判为不一致而整体重下——**不会损坏，但会丢失进度**。

**(3) 发起请求与 Range 校验**

```python
        if state is not None and state.url == plan.url and self._verify_partial(shard_path, state):
            resume_from = state.verified_bytes
            with shard_path.open("rb") as fh:
                ...  # 把已有前缀重新喂给 rolling 哈希
        else:
            ...  # 删除分片和 checkpoint

        request = urllib.request.Request(plan.url)
        if resume_from > 0:
            request.add_header("Range", f"bytes={resume_from}-")
        response = self._opener(request)
        try:
            if resume_from > 0:
                status = int(getattr(response, "status", 0) or 0)
                ...
                if status != 206 or not content_range.startswith(f"bytes {resume_from}-"):
                    ...  # 关闭响应、清理文件、resume_from = 0、整体重新 GET
```

- 续传时要把已有前缀**重新读一遍**喂给 `rolling` 哈希，这样追加完成后 `rolling.hexdigest()` 就是整个文件的 sha256。注意这意味着 `_verify_partial` 与这里各读了一遍前缀，续传一个 100 GB 的部分文件要先读 200 GB。
- URL 改变（`state.url != plan.url`）也会触发重下。
- `getattr(response, "status", 0) or 0`：兼容没有 `status` 属性或其值为 `None` 的响应对象。实测 `file://` 响应的 `status` 为 `None`、没有 `Content-Range`，所以本地文件的"续传"永远走回退整体重下的分支。
- `opener` 可注入：默认 `urllib.request.urlopen`，测试可以传入假 opener。这是一个很好的可测试性设计——本讲解第 6 节的续传实验就是用它模拟断线的。
- URL scheme 白名单 `{"http", "https", "file"}`，防止 `ftp:`、`data:` 等意外协议。
- ⚠️ **已完成分片重跑会失败**：下载完成后 checkpoint 保留且 `verified_bytes` 等于文件总长；再次调用时发出 `Range: bytes=<总长>-`，真实 HTTP 服务器返回 **416**，`urlopen` 直接抛 `HTTPError`，而代码只处理了 200 回退（实测见第 6 节）。
- ⚠️ 没有 `timeout`、没有重试、没有 `ETag`/`If-Range`：远端文件更新后续传会把新旧版本拼在一起，而前缀哈希只校验本地字节，发现不了。

**(4) 写入循环：checkpoint 先于数据**

```python
            mode = "ab" if resume_from > 0 else "wb"
            with shard_path.open(mode) as out:
                while True:
                    buf = response.read(self.chunk_bytes)
                    if not buf:
                        break
                    rolling.update(buf)
                    next_verified = resume_from + len(buf)
                    new_state = CheckpointState(..., verified_bytes=next_verified,
                                                sha256_prefix_hex=rolling.hexdigest())
                    self._write_checkpoint(checkpoint_path, new_state)
                    out.write(buf)
                    out.flush()
                    resume_from = next_verified
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
```

- 续传用追加模式 `"ab"`，否则 `"wb"` 覆盖。
- `rolling.hexdigest()` 不会结束哈希对象，可以在每个 chunk 后取一次当前前缀的摘要，继续 `update`。
- 写入顺序是"先 checkpoint、后数据"，与讲义一致。但这样崩溃后 checkpoint 会**领先**于文件（课程 `quiz.json` 说"never ahead"是不对的），依靠 `_verify_partial` 的大小检查兜底，结果是从 0 重下。
- `try/finally` 保证无论是否异常，响应都会被关闭。

**(5) 二次解压计数**

```python
        with shard_path.open("rb") as fh:
            dctx = zstd.ZstdDecompressor()
            reader = dctx.stream_reader(fh)
            while True:
                chunk = reader.read(self.chunk_bytes)
                if not chunk:
                    break
                decompressed_bytes += len(chunk)
                document_count += chunk.count(b"\n")
```

- 下载后又完整解压一遍，只为统计解压字节数和换行数；`process_shard` 里还会再解压第三遍做去重。
- ⚠️ `document_count` 数的是 `\n`：空行会被计入，结尾无换行的最后一行不会被计入；而 `ZstdDocIterator` 跳过空行、会产出最后一行。实测 `b"a b c\n\nd e f\n"` 得到 3 vs 2，`b"a b c\nd e f"` 得到 1 vs 2，manifest 中 `document_count ≠ kept_count + duplicate_count`。
- 返回的 `ShardResult` 中 `kept_count`/`duplicate_count` 先填 0，由 `process_shard` 回填。

### 3.8 ShardPlanner 与 ManifestWriter

```python
    @staticmethod
    def from_urls(urls: Iterable[str]) -> list[ShardPlan]:
        plans: list[ShardPlan] = []
        for index, url in enumerate(urls):
            shard_id = f"shard-{index:04d}"
            plans.append(ShardPlan(shard_id=shard_id, url=url))
        return plans
```

- 用 URL 在列表中的**位置**生成 `shard-0000`、`shard-0001`……注意：URL 列表顺序一变，同一个 URL 的 shard_id 就变了，而 checkpoint 以 shard_id 命名，`state.url != plan.url` 会触发重下。用 URL 的哈希作为 id 会更稳定。

```python
    def write(self, manifest_path: Path) -> str:
        body = {
            "version": 1,
            "generated_at": int(time.time()),
            "shards": self._rows,
            "verdicts": self._verdicts,
        }
        text = json.dumps(body, sort_keys=True, indent=2)
        manifest_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        manifest_path.write_text(text, encoding="utf-8")
        lock_path = manifest_path.with_suffix(manifest_path.suffix + ".lock")
        lock_path.write_text(json.dumps({"manifest_sha256": manifest_sha}), encoding="utf-8")
        return manifest_sha
```

- 先序列化成确定格式（`sort_keys=True`、`indent=2`），对**这段文本**求 sha256，再写 `manifest.json` 与 `manifest.json.lock`。
- `with_suffix(manifest_path.suffix + ".lock")`：`.json` → `.json.lock`。
- `shards`/`verdicts` 属性返回 `list(...)` 副本，防止外部修改内部状态。
- ⚠️ `generated_at` 参与哈希：数据不变，manifest 哈希也会随时间变化（实测间隔 1 秒两次写入的 sha 不同），与"manifest 作为 git 中的合并门"的理念冲突。
- ⚠️ 没有对应的"读取并校验 lock"的函数（讲义练习 5）；manifest 和 lock 都不是原子写。
- ⚠️ manifest 记录的 sha256 是**原始压缩分片**的哈希。讲义说的"sha256 of the final shard file"在代码中不存在——保留的文档并没有被写成新的去重后分片（流程图里的 "Append to shard" 未实现）。

### 3.9 process_shard 与 demo

```python
    result = downloader.download(plan)
    ...
    with shard_path.open("rb") as fh:
        for doc_index, line in enumerate(ZstdDocIterator(fh)):
            verdict = dedup.evaluate(plan.shard_id, doc_index, line)
            manifest.add_verdict(verdict)
            ...
    result = dataclasses.replace(result, kept_count=kept, duplicate_count=duplicates)
    manifest.add_shard(result)
```

- `dataclasses.replace` 创建一个修改了部分字段的**新**对象，原对象不变。
- 所有分片共享同一个 `Dedup`（同一个 `LSHIndex`），所以去重是**跨分片**的。
- 每篇文档（包括保留的）都会产生一条 verdict，manifest 中 verdict 数等于文档数。

`build_demo_corpus` 准备了 10 句话，按 `base[:5]`、`base[3:9]`、`base[6:]` 切成 3 个分片：第 3–4 句、第 6–8 句跨分片逐字重复；第 0/1 句、第 2/3 句是人为构造的"近似重复"。`run_demo` 用 `shingle_width=3`（不是默认的 5）、`bands=32`。两个 `TemporaryDirectory` 在 `with` 结束时自动删除，所以运行后磁盘上不留任何文件。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 64 KiB 块流式读写 | 内存占用恒定 | 每块都重写 checkpoint，大文件写放大严重；生产中每 N MB 写一次 |
| checkpoint 记录前缀 sha256 | 续传前能验证本地字节 | 续传需重读整个前缀（本实现读两遍）；可分段保存哈希 |
| `os.replace` 原子写 checkpoint | 不会读到半个 JSON | 未 `fsync`，断电不保证落盘顺序 |
| 大小必须严格相等才续传 | 简单且不会损坏 | 任何不一致都从 0 重下；更好的做法是"先写数据并 fsync，再写 checkpoint"，续传时截断到 `verified_bytes` |
| 校验 `206` + `Content-Range`，否则整体重下 | 防止"把完整文件追加到前缀后" | 没处理 416、没有 `If-Range`/`ETag`、没有超时与重试 |
| 注入式 `opener` | 便于测试与替换 HTTP 客户端 | 现有测试未利用它覆盖 206 路径 |
| blake2b 派生哈希系数 | 跨机器、跨运行可复现 | 纯 Python 双循环计算签名较慢；生产用 NumPy/datasketch/Rust |
| (k=128, b=32, r=4) | 召回高，几乎不漏近似重复 | 阈值仅约 0.42，会误杀 Jaccard 0.3–0.5 的不同文档；目标 0.8 应选 (16, 8) 等 |
| 只有保留者入索引、先到先得 | 实现简单、内存最小 | 保留者与质量无关；无二次确认；单机内存索引无法扩展到 200 GB（讲义建议按 band 分区存盘） |
| 下载后解压计数 + 迭代时再解压 | 两个阶段职责分离 | 解压三次（含去重）；计数口径与迭代不一致 |
| verdict 内联在 manifest 中 | 一个文件看全貌 | 文档上亿时 manifest 巨大；应按分片拆分 |
| `generated_at` 写进 manifest 并参与哈希 | 记录生成时间 | 相同数据哈希不同，无法作为内容寻址的契约 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `try/except ImportError` + `raise ... from exc` | 导入 `zstandard` | 依赖缺失时给出友好提示，并保留异常链 |
| 位运算 | `1 << 16`、`(1 << 64) - 1`、`a \| 1`、`x & MAX_UINT64` | 左移得到 2 的幂；`\| 1` 置最低位；`&` 掩码截断 |
| 新式类型注解 | `int \| None`、`list[int]`、`dict[str, list[int]]`、`tuple[int, int]` | Python 3.9/3.10+ 的内置泛型与联合类型写法 |
| `@dataclass` 与 `asdict` | `CheckpointState`、`asdict(self)` | 自动生成构造函数；转成字典便于 JSON 序列化 |
| `dataclasses.replace` | `dataclasses.replace(result, kept_count=kept, ...)` | 返回修改了指定字段的新实例 |
| `@classmethod` | `CheckpointState.from_json(cls, text)` | 以类为第一个参数的"替代构造函数" |
| `@staticmethod` | `MinHasher._hash_shingle`、`ShardPlanner.from_urls` | 不需要 `self` 的方法 |
| `@property` | `ManifestWriter.shards` | 像属性一样访问的方法，这里返回副本 |
| `int.to_bytes` / `int.from_bytes` | `seed.to_bytes(8, "little")`、`int.from_bytes(digest[:8], "little")` | 整数与字节串互转，指定长度与字节序 |
| `hashlib` | `hashlib.blake2b(..., digest_size=16)`、`hashlib.sha256()` 的 `update`/`hexdigest` | 可增量更新的哈希对象 |
| `struct.pack` | `struct.pack("<Q", v)` | 按格式打包二进制：`<` 小端、`Q` 无符号 64 位 |
| 生成器表达式 | `b"".join(struct.pack("<Q", v) for v in band)`、`sum(1 for a, b in zip(...) if a == b)` | 边生成边消费 |
| 生成器函数 | `ZstdDocIterator.__iter__` 中的 `yield line` | 让对象可以被 `for` 迭代，惰性产出 |
| `dict.setdefault` | `self._buckets[i].setdefault(key, []).append(doc_id)` | 键不存在时先插入默认值再返回 |
| 列表推导式 | `[{} for _ in range(bands)]` | 每个 band 一个独立字典（不能写成 `[{}] * bands`，那样是同一个字典） |
| 切片 | `signature[i * self.rows : (i + 1) * self.rows]`、`tokens[start : start + w]` | 取第 i 个 band、第 start 个窗口 |
| `enumerate` | `for index, url in enumerate(urls)` | 同时得到下标和元素 |
| f-string 格式符 | `f"shard-{index:04d}"`、`{result.sha256[:12]}`、`{parsed.scheme!r}` | 补零到 4 位；切片；`!r` 用 `repr()` 显示 |
| `pathlib.Path` | `self.cache_dir / f"{shard_id}.zst"`、`with_suffix`、`stat().st_size`、`as_uri()`、`unlink()` | 面向对象的路径操作；`/` 拼接路径 |
| `os.replace` | `os.replace(tmp, checkpoint_path)` | 原子替换文件 |
| `with` 多个上下文 | `with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:` | 一行管理两个资源，退出时自动清理 |
| `try/finally` | 关闭 `response` | 无论是否异常都执行清理 |
| `getattr` + `callable` | `getattr(response, "status", 0)`、`if callable(close)` | 鸭子类型：兼容不同的响应对象 |
| `x or 默认值` | `opener or urllib.request.urlopen`、`... or 0` | 左侧为假值时取右侧 |
| `urllib` | `urllib.parse.urlparse`、`urllib.request.Request`、`add_header` | 解析 URL、构造带请求头的请求 |
| `io.TextIOWrapper` | `io.TextIOWrapper(self._stream, encoding="utf-8", newline="")` | 把二进制流包装成按行读取的文本流 |
| `json.dumps(sort_keys=True, indent=2)` | manifest 序列化 | 键排序保证顺序确定 |
| `if __name__ == "__main__": sys.exit(run_demo())` | 文件末尾 | 直接运行时执行 demo，返回值作为退出码 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.1 秒）：

```text
[shard] shard-0000 docs=5 kept=3 duplicates=2 sha256=5f6951ba9f5f
[shard] shard-0001 docs=6 kept=4 duplicates=2 sha256=71d866bb8403
[shard] shard-0002 docs=4 kept=1 duplicates=3 sha256=7a08fba093be
[manifest] sha256=63723a45c192 kept=8 duplicates=7
```

逐项解读（verdict 明细通过调试脚本取出）：

| 分片 | 文档 | verdict | collided_with | 说明 |
|------|------|---------|---------------|------|
| shard-0000 | 0 | keep | — | alignment 句 A |
| shard-0000 | 1 | near_duplicate | shard-0000:0 | alignment 句 B，与 A 的真实 3-gram Jaccard 仅 **0.364**（8/22），MinHash 估计 0.383 |
| shard-0000 | 2 | keep | — | transformers 句 |
| shard-0000 | 3 | near_duplicate | shard-0000:2 | 倒装句，真实 Jaccard **0.5**（6/12），估计 0.531 |
| shard-0000 | 4 | keep | — | |
| shard-0001 | 0 | near_duplicate | shard-0000:2 | `base[3]` 的逐字重复；但它的原件 shard-0000:3 未入索引，所以指向保留者 :2 |
| shard-0001 | 1 | near_duplicate | shard-0000:4 | 逐字重复 |
| shard-0001 | 2–5 | keep | — | |
| shard-0002 | 0–2 | near_duplicate | shard-0001:3/4/5 | 逐字重复 |
| shard-0002 | 3 | keep | — | |

- **15 篇文档、10 个不同字符串**：5 条是跨分片逐字重复，2 条是分片内"近似重复"，共 7 条。
- 那 2 条近似重复的真实 Jaccard 都远低于讲义宣称的 0.8 阈值：(32, 4) 下 s = 0.364 的碰撞概率约 0.43、s = 0.5 约 0.87。把 `bands` 改为 16（r = 8）重跑，结果变为 kept = 10、duplicates = 5，只去掉逐字重复。
- **sha256** 是每个原始压缩分片的哈希（`raw_bytes` 分别为 215、286、201 字节；解压后 454、512、336 字节）。
- **manifest sha256** 包含 `generated_at` 时间戳，每次运行都不同。
- 运行结束后两个临时目录被删除，cache 目录里原本有 3 个 `.zst` 和 3 个 `.partial.json`（下载完成后 checkpoint 没有清理）。

**补充实验：用真正支持 Range 的本地 HTTP 服务器验证续传**（demo 与测试都只用 `file://`，从未走到 206 分支）。用一个约 9 KB 的 zst 分片、`chunk_bytes=256`，并通过注入的 opener 让第一次下载在读完 2 个 chunk 后抛 `ConnectionResetError`：

```text
dropped: simulated drop on-disk 512 {"expected_size": null, "sha256_prefix_hex": "6c48...", "verified_bytes": 512, ...}
resumed result 9060 300 24307 LOG [None, 'bytes=512-']      ← 第二次运行发出 Range: bytes=512-，收到 206
sha ok True                                                 ← 最终 sha256 与源文件一致
rerun HTTPError 416 [None, 'bytes=512-', 'bytes=9060-']     ← 第三次对已完成分片重跑：416 异常
```

- 续传路径本身工作正常：校验 512 字节前缀 → Range → 206 → 追加 → 整体哈希正确。
- 已完成分片重跑会发出 `bytes=9060-`，服务器按 RFC 7233 返回 416，`urlopen` 抛 `HTTPError`，流程中断。这是本节代码最实际的 bug（修复见测验 Q9）。

---

## 7. 动手改一改

1. **讲义练习 1**：给 `run_demo` 加 `--shingle-width` 参数（`argparse`），分别用 3、5、9 运行，记录 kept/duplicates；再把 `bands` 在 32、16、8 之间切换，填一张 3 × 3 的表，为默认值辩护。
2. **修复计数口径**：删除 `download()` 中的二次解压，在 `process_shard` 中用迭代结果回填 `document_count` 与 `decompressed_bytes`，并加一条断言 `document_count == kept + duplicates`。
3. **修复 416**：下载完成后写一个 `.done.json`（含最终 sha256 与大小），`download()` 开头发现它且校验通过时直接返回；同时捕获 `HTTPError` 的 416 分支。用第 6 节的本地 Range 服务器验证三次连续运行都成功。
4. **讲义练习 2**：读取分片前 4 个字节嗅探魔数——zstd 为 `28 B5 2F FD`，gzip 为 `1F 8B`——自动选择 `zstandard` 或 `gzip.open`。
5. **讲义练习 5 + 可复现 manifest**：把 `generated_at` 移出哈希范围（例如单独写进 lock 文件），实现 `verify_manifest(path)`：重算 sha256 与 `manifest.json.lock` 比对，不一致就 `raise SystemExit`（fail closed）。
6. **进阶：持久化顺序与 ETag**：改为"写数据 → `os.fsync(out.fileno())` → 原子写 checkpoint → fsync 目录"，续传时若文件比 `verified_bytes` 长就 `truncate`；在 checkpoint 中记录响应的 `ETag`，续传请求带 `If-Range`，服务器返回 200 时自动整体重下。

---

## 8. 常见坑

- **把讲义的 "b=32, r=4 → 阈值 0.8" 当真**：实际阈值约 0.42，会误杀大量不同文档。先算 S 曲线再选参数。
- **以为 LSH 碰撞 = 重复**：碰撞只是候选，生产中应做二次确认（精确 Jaccard 或签名估计）。
- **Range 请求不校验响应**：服务器忽略 Range 返回 200 时，直接追加会得到"前缀 + 完整文件"的损坏分片。本代码正确地校验了 `206` 与 `Content-Range`。
- **不处理 416**：已完成分片重跑时出错（本代码的 bug）。
- **只 flush 不 fsync**：`flush()` 只把数据交给操作系统，断电仍可能丢失。
- **前缀哈希 ≠ 远端一致性**：前缀哈希只证明本地字节没变，证明不了远端文件没变；需要 `ETag` + `If-Range`。
- **计数口径不一致**：数 `\n` 与逐行迭代在空行、末行无换行时结果不同。
- **`[{}] * n` 陷阱**：会得到 n 个指向同一字典的引用；代码正确地用了 `[{} for _ in range(bands)]`。
- **manifest 带时间戳参与哈希**：相同数据不同哈希，失去内容寻址的意义。
- **shard_id 依赖 URL 顺序**：列表顺序变化会让 checkpoint 对不上，触发重下。

---

## 9. 测试在验证什么

测试文件 `tests/test_downloader.py`（`unittest` 风格；`tests/__init__.py` 为空文件，使 `tests` 成为包）。运行方式与实际结果：

```bash
cd code
python -m unittest discover tests -v      # Ran 15 tests in 0.040s, OK
python -m pytest -q tests                 # 15 passed in 0.05s
```

测试开头 `sys.path.insert(0, str(HERE.parent))` 把 `code/` 加入导入路径；辅助函数 `_zst_url` 把若干行文本压缩写成 `.zst` 并返回 `file://` URL。

| 测试 | 验证的性质 |
|------|-----------|
| `MinHasherTests.test_signature_length_matches_num_hashes` | 签名长度 = `num_hashes`（64） |
| `MinHasherTests.test_identical_text_produces_identical_signature` | 签名是确定性的 |
| `MinHasherTests.test_near_duplicate_has_high_jaccard_estimate` | 只差一个 "the" 的两句话，估计 Jaccard > 0.5（实测真实值 6/9 = 0.667，估计 0.668） |
| `MinHasherTests.test_empty_text_yields_sentinel_signature` | 空文本得到长度正确的哨兵签名（只断言 `> 0`，较弱；实际全是 `2^64−1`） |
| `MinHasherTests.test_rejects_bad_arguments` | `num_hashes=0`、`shingle_width=0` 抛 `ValueError` |
| `LSHIndexTests.test_band_count_must_divide_num_hashes` | 10 个哈希不能分成 3 个 band |
| `LSHIndexTests.test_lsh_catches_high_similarity_pair` | 真实 Jaccard 0.8（12/15）的一对能被查到 |
| `LSHIndexTests.test_lsh_does_not_collide_unrelated_documents` | 不相关文档不碰撞 |
| `DedupTests.test_dedup_keeps_first_and_drops_second` | 先到者 `keep`，逐字重复判 `near_duplicate` 且 `collided_with == "s0:0"` |
| `CheckpointTests.test_checkpoint_round_trips_through_json` | `to_json` / `from_json` 往返相等（dataclass 自动生成的 `__eq__`） |
| `ShardPlannerTests.test_planner_assigns_zero_padded_ids` | id 为 `shard-0000` 格式 |
| `DownloaderTests.test_download_writes_shard_and_checkpoint` | 下载后分片与 checkpoint 都存在、文档数为 3 |
| `DownloaderTests.test_resume_after_corruption_restarts` | 篡改 checkpoint 的哈希后，再次下载仍得到正确的 3 篇文档 |
| `ManifestTests.test_manifest_writer_emits_a_lock_and_records_hash` | 写出 `manifest.json.lock`，其中记录的哈希等于 `write()` 返回值 |
| `IntegrationTests.test_end_to_end_dedup_via_demo_corpus` | 在 demo 语料上总文档数 > 保留数（确实去掉了重复） |

测试的盲区（值得补充）：

- **从未覆盖 206 续传路径**：所有下载测试都用 `file://`，其响应 `status` 为 `None`，续传一律走"整体重下"分支。`test_resume_after_corruption_restarts` 即使把哈希改成正确的，也一样会整体重下——它无法区分"校验失败后重下"与"续传成功"。可以用注入的 `opener` 构造一个返回 `status=206` 与 `Content-Range` 的假响应，或像第 6 节那样起一个本地 Range 服务器。
- **没有测试已完成分片重跑**（会触发 416）、服务器忽略 Range（200 回退）、URL 变化重下等分支。
- **没有测试计数一致性**：`document_count == kept_count + duplicate_count` 在空行/末行无换行时不成立。
- **没有测试 LSH 的假阳性率**：只测了"不相关"与"0.8 相似"两个极端，没有测 Jaccard 0.3–0.5 的中间区域，所以低阈值的问题被测试放过了。
- **没有测试 manifest 的可复现性**：同一数据两次写出的哈希不同。
