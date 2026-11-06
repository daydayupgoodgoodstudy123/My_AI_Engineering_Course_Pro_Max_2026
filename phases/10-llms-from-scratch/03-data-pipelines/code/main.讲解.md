# 代码讲解 · main.py

> **所属小节**：阶段 10 · 从零构建 LLM · 第 03 节 用于预训练的数据管道 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅 Python 标准库（`re`、`hashlib`、`random`、`time`、`collections`），无需网络

---

## 1. 这份代码在考察什么

这是一条**缩小到 15 篇文档**的完整预训练数据管道，每个阶段都对应工业界真实存在的一个环节：

1. **清洗**：用正则剥 HTML、删 URL、删非文本字符、规整空白。
2. **质量过滤**：三条启发式规则（太短、全大写比例、特殊字符比例）拦截存根页和 SEO 垃圾。
3. **近似去重**：从零实现 shingling → MinHash 签名 → LSH 分桶 → Jaccard 校验。
4. **分词与打包**：训练一个小 BPE，文档间插 EOS，拼接后切成定长 128 的序列，并生成 padding mask。
5. **DataLoader**：打乱、分批，用生成器把 batch "流"给训练循环。
6. **统计**：压缩比、词表利用率、序列利用率——判断管道是否健康的仪表盘。

> 一句话：**模型学到什么，取决于管道放进来什么**。这份代码让你看清每一层"筛子"具体筛掉了什么，也让你看到这些筛子会在哪里悄悄出错。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `clean_text` | 函数 | 正则清洗 HTML/URL/非 ASCII/多余空白 | HTML 剥离 |
| `quality_filter` | 函数 | 长度、大写比例、特殊字符比例三条规则 | 启发式质量过滤 |
| `get_shingles` | 函数 | 文档 → 5 词 shingle 集合 | Shingling |
| `minhash_signature` | 函数 | shingle 集合 → 128 维 MinHash 签名 | MinHash |
| `lsh_buckets` | 函数 | 签名切成 16 个 band，每个 band 哈希成桶 id | LSH |
| `deduplicate` | 函数 | 分桶找候选对 → 精确 Jaccard 校验 → 删除重复 | 近似去重 |
| `SimpleTokenizer` | 类 | 字节级 BPE（无预分词）+ 训练后追加 EOS | 分词 |
| `tokenize_corpus` | 函数 | 每篇文档编码后追加 `eos_id`，拼成一条长序列 | 文档分隔 |
| `pack_sequences` | 函数 | 按 `seq_length` 切块，最后一块 pad 并生成 0/1 mask | 序列打包 |
| `PreTrainingDataLoader` | 类 | `__len__` 给出 batch 数，`__iter__` 打乱并逐批 `yield` | DataLoader |
| `compute_statistics` | 函数 | 汇总各项指标为字典 | 数据集统计 |
| `generate_sample_corpus` | 函数 | 10 篇正常文档 + 2 篇"近似重复" + 短文档 + HTML 文档 + 垃圾文档 | 测试数据 |
| `run_pipeline` | 函数 | 串起 6 个阶段并打印每一步的结果与耗时 | 主流程 |

数据流：`generate_sample_corpus` → `clean_text` → `quality_filter` → `deduplicate` → `SimpleTokenizer.train_bpe` / `tokenize_corpus` → `pack_sequences` → `PreTrainingDataLoader` → `compute_statistics`。

---

## 3. 逐段精讲

### 3.1 清洗：五条正则

```python
def clean_text(text):
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^\x20-\x7E\n]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()
```

| 正则 | 含义 |
|------|------|
| `<[^>]+>` | `<` 开头、若干个非 `>` 字符、`>` 结尾——即 HTML 标签 |
| `http\S+` | 以 http 开头直到下一个空白——粗略的 URL |
| `[^\x20-\x7E\n]` | 不在"可打印 ASCII（空格到 `~`）或换行"范围内的字符 |
| `\n{3,}` | 3 个及以上连续换行 → 压成一个空行 |
| ` {2,}` | 2 个及以上连续空格 → 1 个 |

- ⚠️ 标签被替换成**空串**：`<h1>Title</h1><p>Machine` 变成 `TitleMachine`，两个词粘在一起（样例中的 HTML 文档实际就是这样）。应替换为空格。
- ⚠️ `[^\x20-\x7E\n]` 会删掉**所有非 ASCII 字符和制表符**：`café` → `caf`，中文整段消失，代码里的 tab 缩进也没了。这对纯英文教学语料无害，但用在多语言或代码数据上是灾难。讲义中的语言过滤应由语言识别模型（如 fastText）完成，而不是靠删字符。
- ⚠️ 正则剥 HTML 无法处理 `<script>`、`<style>` 里的 JS/CSS 文本；生产中用 `trafilatura`/`readability` 抽取正文。

### 3.2 质量过滤：三条便宜的启发式规则

```python
def quality_filter(text, min_words=50, max_ratio_caps=0.3, max_ratio_special=0.1):
    words = text.split()
    if len(words) < min_words:
        return False
    caps_ratio = sum(1 for w in words if w.isupper()) / len(words)
    if caps_ratio > max_ratio_caps:
        return False
    special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
    if special_chars / max(len(text), 1) > max_ratio_special:
        return False
    return True
```

- **少于 50 词**：拦截存根页（样例中的 `"This is too short to be useful."` 只有 7 个词）。
- **全大写单词占比 > 30%**：拦截 `BUY NOW CLICK HERE ...` 这类 SEO 垃圾（样例中占比 100%）。
- **特殊字符占比 > 10%**：拦截乱码、表格残渣、机器生成噪声。
- `sum(1 for ... if ...)` 是"满足条件的元素计数"的惯用写法。
- 先做最便宜的长度检查，不通过就**提前返回**，后面的统计都不用算。
- ⚠️ 规则是英文导向的：`isupper()` 对中文恒为 `False`，`min_words` 用 `split()` 数词对中文无效。生产中还会加"重复行比例""停用词比例"等规则，以及基于困惑度或分类器的模型打分（讲义中 RefinedWeb 的做法）。

### 3.3 Shingling 与 MinHash 签名

```python
def get_shingles(text, k=5):
    words = text.lower().split()
    if len(words) < k:
        return set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def minhash_signature(shingles, num_hashes=128):
    signature = []
    for i in range(num_hashes):
        min_hash = float("inf")
        for shingle in shingles:
            h = int(hashlib.sha256(f"{i}:{shingle}".encode()).hexdigest(), 16)
            min_hash = min(min_hash, h)
        if min_hash == float("inf"):
            min_hash = 0
        signature.append(min_hash)
    return signature
```

- `get_shingles` 用**集合推导式**生成所有连续 5 词组合。用集合而不是列表：重复的 shingle 只算一次，Jaccard 本来就是集合运算。
- **MinHash 的核心性质**：对一个随机哈希函数，两个集合的"最小哈希值"相等的概率恰好等于它们的 Jaccard 相似度。128 个哈希 → 128 次独立"抽样"，签名中相等位置的比例就是 Jaccard 的估计。签名长度固定为 128，与文档长短无关，这是它能扩展到海量文档的关键。
- 用 `f"{i}:{shingle}"` 给 shingle 加上编号前缀再做 SHA-256，相当于构造了 128 个"不同的"哈希函数。`int(..., 16)` 把十六进制摘要转成（很大的）整数，Python 整数不会溢出。
- `float("inf")` 作为求最小值的初始值；如果集合为空（文档少于 5 个词），循环一次都不执行，就把它置为 0。
- ⚠️ 每个文档要做 `128 × shingle 数` 次 SHA-256，非常慢。生产实现只对每个 shingle 做一次基础哈希，再用 128 组随机线性变换 `(a·x + b) mod p` 生成 128 个哈希值，并用向量化计算。

### 3.4 LSH 分桶与去重

```python
def lsh_buckets(signature, bands=16):
    rows_per_band = len(signature) // bands
    buckets = []
    for b in range(bands):
        start = b * rows_per_band
        band_data = tuple(signature[start:start + rows_per_band])
        bucket_hash = hashlib.md5(str(band_data).encode()).hexdigest()
        buckets.append((b, bucket_hash))
    return buckets
```

- 128 位签名切成 16 个 band，每个 band 8 行。把一个 band 的 8 个数转成元组再取 MD5，作为桶 id。
- 返回 `(band 编号, 桶 id)`：必须带 band 编号，否则第 1 个 band 和第 5 个 band 的值碰巧相同也会被误认为同桶。
- **候选概率**：两篇 Jaccard 为 s 的文档，在某个 band 上 8 行全相等的概率是 `s⁸`，16 个 band 中至少一个全等的概率是 `1 − (1 − s⁸)¹⁶`。阈值约 `(1/16)^(1/8) ≈ 0.71`：s=0.5 时只有约 6%，s=0.8 时约 95%。

```python
    bucket_map = defaultdict(list)
    for doc_idx, sig in enumerate(signatures):
        for band_id, bucket_hash in lsh_buckets(sig, bands):
            bucket_map[(band_id, bucket_hash)].append(doc_idx)

    duplicate_pairs = set()
    for bucket_docs in bucket_map.values():
        if len(bucket_docs) < 2:
            continue
        for i in range(len(bucket_docs)):
            for j in range(i + 1, len(bucket_docs)):
                duplicate_pairs.add((bucket_docs[i], bucket_docs[j]))

    removed = set()
    for i, j in duplicate_pairs:
        if i in removed or j in removed:
            continue
        s1, s2 = shingle_sets[i], shingle_sets[j]
        if not s1 or not s2:
            continue
        jaccard = len(s1 & s2) / len(s1 | s2)
        if jaccard >= threshold:
            removed.add(j)
```

- `defaultdict(list)`：访问不存在的 key 时自动创建空列表，直接 `.append`。
- 同一个桶里的文档两两组成候选对；用 `set` 存，避免同一对在多个 band 里重复出现。由于 `doc_idx` 递增加入，总有 `i < j`。
- **候选 ≠ 重复**：对每个候选对再算一次精确 Jaccard（`&` 交集、`|` 并集），≥ 0.8 才删除**后出现的那篇** `j`，保留先出现的。
- `if i in removed or j in removed: continue`：已经删掉的文档不再参与比较，避免 A≈B、B≈C 时把 B、C 都删掉后 A 也被误判之类的连锁问题。
- 空 shingle 集合（短文档）的签名全为 0，所有 band 都会撞桶，但 `if not s1 or not s2` 会跳过它们，不会误删。
- ⚠️ 遍历 `set` 的顺序不是按 `(i, j)` 排好序的，存在连锁重复时"保留哪一篇"可能与直觉不同；生产中通常用并查集把重复文档聚成簇，每簇保留一篇。

### 3.5 分词器：训练完再追加 EOS

```python
        self.eos_id = self.next_id
        self.vocab[self.eos_id] = b"<EOS>"
        self.next_id += 1
```

- `SimpleTokenizer.train_bpe` 与第 01 节的 BPE 相同（直接在整段文本上合并，**没有预分词**），这里不再重复。合并完成后把下一个可用 ID 分配给 EOS（本次运行为 356），词表大小 = 256 + 100 + 1 = 357。
- `decode` 会跳过 `eos_id`；`pad_id = 0` 与字节 `0x00` 共用 ID 0——由于 `clean_text` 已删除控制字符，真实数据里不会出现字节 0，所以这里不冲突。
- ⚠️ 构造函数的 `vocab_size=256` 参数没有被使用，是一个"摆设"参数。

### 3.6 拼接与定长打包

```python
def tokenize_corpus(documents, tokenizer):
    all_tokens = []
    for doc in documents:
        tokens = tokenizer.encode(doc)
        all_tokens.extend(tokens)
        all_tokens.append(tokenizer.eos_id)
    return all_tokens


def pack_sequences(token_ids, seq_length, pad_id=0):
    sequences = []
    attention_masks = []
    for i in range(0, len(token_ids), seq_length):
        seq = token_ids[i:i + seq_length]
        mask = [1] * len(seq)
        if len(seq) < seq_length:
            pad_count = seq_length - len(seq)
            seq = seq + [pad_id] * pad_count
            mask = mask + [0] * pad_count
        sequences.append(seq)
        attention_masks.append(mask)
    return sequences, attention_masks
```

- 所有文档首尾相接、中间用 EOS 隔开，形成一条长 token 流；再以 `seq_length` 为步长切块。这就是讲义中的"高效打包"：只有最后一块需要 padding。
- `range(0, n, seq_length)` 的步长参数让 `i` 依次取 0、128、256……；切片 `token_ids[i:i + seq_length]` 越界时自动截断，不会报错。
- `[1] * len(seq)`：列表乘法快速生成全 1 列表。
- ⚠️ 这里的 mask 只区分"真实 token / padding"，**不是**讲义要求的块对角 mask：同一条序列里的后一篇文档仍能注意到前一篇。测验 Q10 给出了按 EOS 构造块对角因果 mask 的实现。
- ⚠️ 文档在 128 的边界处被硬切断，可能切在句子中间；讲义提到一些管道会尽量对齐段落/句子边界。
- ⚠️ 这里没有构造 `labels`（输入右移一位的目标），那一步在训练循环中完成（见第 04 节）。

### 3.7 DataLoader：可迭代对象 + 生成器

```python
class PreTrainingDataLoader:
    # ...
    def __len__(self):
        return (len(self.sequences) + self.batch_size - 1) // self.batch_size

    def __iter__(self):
        indices = list(range(len(self.sequences)))
        if self.shuffle:
            random.shuffle(indices)
        for start in range(0, len(indices), self.batch_size):
            batch_idx = indices[start:start + self.batch_size]
            batch_seqs = [self.sequences[i] for i in batch_idx]
            batch_masks = [self.attention_masks[i] for i in batch_idx]
            yield batch_seqs, batch_masks
```

- `(n + b - 1) // b` 是**向上取整除法**的经典写法：21 条序列、batch 4 → 6 个 batch（最后一个只有 1 条）。
- 实现 `__iter__` 后，对象可以直接放进 `for` 循环；因为函数体里有 `yield`，`__iter__` 是一个**生成器函数**，每次只产出一个 batch，不会一次性构造所有 batch。
- 每次迭代（每个 epoch）都重新打乱**下标**而不是打乱数据本身，开销小且不修改原数据。
- ⚠️ `random.shuffle` 没有设随机种子，每次运行的 batch 顺序都不同，结果不可复现（本次输出的 Batch 1/2 内容就是随机的）。
- ⚠️ 全部序列都在内存中。讲义目标是"流式处理 TB 级数据"，生产中会把 token 预先存成分片二进制文件，按需读取、分片级打乱。

### 3.8 统计指标

```python
    compression_ratio = total_chars / max(total_tokens, 1)
    # ...
    non_pad_tokens = sum(sum(1 for t in seq if t != 0) for seq in sequences)
    total_positions = sum(len(seq) for seq in sequences)
    utilization = non_pad_tokens / max(total_positions, 1)
```

- **压缩比 = 字符 / token**（越高越好）。注意它与第 01 节"token / 字节"（越低越好）方向相反。讲义：英文通常 3–4 字符/token；1.5 说明切得太碎；8+ 说明学到了非常领域化的合并。
- **序列利用率 = 非 padding 位置 / 总位置**，低于 90% 说明打包低效。用 `t != 0` 判断 padding 依赖于"真实 token 不会是 0"。
- `max(x, 1)` 防止空数据时除以零。
- **词表利用率 = 出现过的不同 token / 词表大小**，可以发现大量从未用到的 token。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 正则清洗 | 零依赖、直观 | 粘词、删光非 ASCII；生产用 trafilatura 抽正文、语言识别模型做语言过滤 |
| 三条启发式质量规则 | 便宜、可解释，能挡住最明显的垃圾 | 英文导向；生产中叠加困惑度/分类器打分 |
| 5 词 shingle + 阈值 0.8 | 讲义推荐的典型配置，误删少 | 对改写型重复不敏感（样例中 `near_dup_1` 没被抓到） |
| SHA-256 模拟 128 个哈希 | 易懂，不需要额外库 | 极慢；生产用随机线性哈希族 + 向量化/分布式 |
| LSH 16×8 | 阈值约 0.71，略低于校验阈值 0.8 | 需按目标阈值调参 |
| 拼接 + 定长切块 | 几乎没有 padding（利用率 99%） | 只有 padding mask，没有文档内 mask；文档会被截断 |
| 内存中的 DataLoader | 代码简单 | 不能处理 TB 级数据；没有随机种子，无法复现 |
| 每一步打印数量与耗时 | 让每个"筛子"的效果可见 | 生产中写入日志/监控，并抽样人工复查 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `re.sub` 正则替换 | `re.sub(r"<[^>]+>", "", text)` | 把匹配到的部分替换成指定字符串 |
| 字符类与十六进制转义 | `[^\x20-\x7E\n]` | `^` 取反；`\x20` 是空格，`\x7E` 是 `~` |
| 量词 `{m,}` | `\n{3,}`、` {2,}` | 至少 m 次 |
| `str.isupper` / `isalnum` / `isspace` | `w.isupper()`、`c.isalnum()` | 字符/字符串类别判断 |
| 生成器表达式计数 | `sum(1 for w in words if w.isupper())` | 统计满足条件的元素个数 |
| 集合推导式与集合运算 | `{" ".join(...) for i in ...}`、`s1 & s2`、`s1 \| s2` | 去重集合；交集、并集 |
| `float("inf")` | `min_hash = float("inf")` | 正无穷，作为求最小值的初始值 |
| `hashlib` | `hashlib.sha256(...).hexdigest()`、`hashlib.md5(...)` | 计算哈希摘要（十六进制字符串） |
| `int(s, 16)` | `int(... .hexdigest(), 16)` | 把十六进制字符串转成整数；Python 整数无上限 |
| `tuple` 作为可哈希值 | `tuple(signature[start:start + rows_per_band])` | 列表不可哈希，元组可以 |
| `collections.defaultdict` | `bucket_map = defaultdict(list)` | 缺失键自动创建默认值 |
| 元组作字典键 | `bucket_map[(band_id, bucket_hash)]` | 复合键 |
| `enumerate` | `for doc_idx, sig in enumerate(signatures)` | 同时取下标与元素 |
| 带条件的列表推导式 | `[doc for idx, doc in enumerate(documents) if idx not in removed]` | 过滤 |
| 多返回值 | `return [...], len(removed)` / `deduped_docs, num_removed = deduplicate(...)` | 返回并解包元组 |
| `range` 步长与列表乘法 | `range(0, len(token_ids), seq_length)`、`[pad_id] * pad_count` | 分块遍历；重复生成元素 |
| 向上取整除法 | `(n + b - 1) // b` | `//` 是整除 |
| `__len__` / `__iter__` 魔术方法 | `PreTrainingDataLoader` | 支持 `len(loader)` 和 `for batch in loader` |
| 生成器 `yield` | `yield batch_seqs, batch_masks` | 惰性地逐个产出 batch |
| `random.shuffle` | `random.shuffle(indices)` | 原地打乱列表 |
| `time.time()` 计时 | `start = time.time()` ... `time.time() - start` | 粗略测量耗时 |
| f-string 格式符 | `{len(token_ids):,}`、`{x:.1%}`、`{x:.2f}` | 千分位；百分比；两位小数 |
| 字符串字面量自动拼接 | `generate_sample_corpus` 中相邻的多段 `"..."` | 括号内相邻字符串会自动连接 |

---

## 6. 运行结果解读

实际运行（Python 3.13，用时约 0.3 秒）的关键输出：

```text
Raw documents: 15
After HTML stripping: 15 documents

--- Stage 2: Quality Filtering ---
Removed 2 low-quality documents            ← 短文档（7 词）+ 全大写垃圾（大写占比 100%）
Remaining: 13 documents

--- Stage 3: Deduplication (MinHash + LSH) ---
Removed 1 near-duplicates in 0.08s         ← 只删掉了与 base_docs[1] 完全相同的 near_dup_2
Remaining: 12 documents

--- Stage 4: Tokenization ---
Trained tokenizer with 357 tokens in 0.11s ← 256 字节 + 100 合并 + 1 个 EOS
Tokenized 2,660 tokens in 0.04s (69,792 tokens/sec)

--- Stage 5: Sequence Packing ---
Packed into 21 sequences of length 128     ← ⌈2660 / 128⌉ = 21

--- Stage 6: DataLoader ---
DataLoader: 6 batches of size 4            ← ⌈21 / 4⌉ = 6
  Total non-padding tokens served: 2,660   ← 与总 token 数一致，没有丢数据

--- Dataset Statistics ---
  Documents:          12
  Total characters:   5,229
  Total tokens:       2,660
  Unique tokens:      137
  Vocab utilization:  38.4%                ← 137 / 357
  Compression ratio:  1.97 chars/token     ← 只有 100 次合并，切得很碎
  Avg doc length:     64 words
  Seq utilization:    99.0%                ← 只有最后一条序列有 28 个 padding
```

逐项解读：

- **HTML 文档通过了过滤**，但清洗后开头是 `"TitleMachine learning ..."`——标签被替换为空串导致粘词（额外检查清洗结果得到）。它有 54 个词、没有大写垃圾，所以三条规则都没拦住它。
- **"近似去重"实际只抓到了精确重复**：额外计算可知，`near_dup_1` 与 `base_docs[0]` 的 5 词 shingle Jaccard 只有 0.27（MinHash 估计 0.273，非常准），16 个 band 一个都没撞桶。这篇是"改写"而不是"微小改动"，5 词 shingle 对改写非常敏感（详见测验 Q8）。
- **69,792 tokens/sec**：纯 Python 的逐条重放合并编码，速度与讲义"纯 Python 比 Rust tokenizer 慢 10–50 倍"的说法吻合。按这个速度处理 1T token 需要约半年。
- **压缩比 1.97 chars/token**：低于英文正常水平（3–4），因为词表只有 100 次合并。
- **Seq utilization 99.0%**：`2660 / (21×128) = 2660 / 2688`。打包几乎消除了 padding 浪费；如果改成"每篇文档单独 pad 到 128"，12 篇文档中较长的还要截断或拆分，利用率会明显更低。
- Batch 1/2 打印的前 20 个 token 每次运行都不同，因为 `random.shuffle` 没有固定种子。

---

## 7. 动手改一改

1. 修复 `clean_text` 的粘词问题：把标签替换为空格，重新运行，确认 HTML 文档开头变成 `"Title Machine learning ..."`。
2. 完成讲义练习 2：在 `deduplicate` 之前加一层 SHA-256 精确去重（对规范化后的全文求哈希），分别统计"精确去重删掉几篇、MinHash 再删掉几篇"。
3. 把 `get_shingles` 的 `k` 改为 3、2，或改为字符 5-gram，观察 `near_dup_1` 是否被删除；再把 `bands` 改为 32（每 band 4 行），观察候选对数量的变化。
4. 给 `PreTrainingDataLoader` 增加 `seed` 参数，使用 `random.Random(seed)` 的实例来打乱，保证可复现，并且不影响全局随机状态。
5. 在 `pack_sequences` 中额外返回每个位置的 `doc_id`（根据 `eos_id` 切换），再据此生成块对角因果 mask（参考测验 Q10）。
6. 完成讲义练习 1：用字符集启发式做语言识别（例如 ASCII 字母占比），在样例语料中加入几篇中文、法文文档，统计被过滤的数量；注意先修改 `clean_text`，否则中文在清洗阶段就已经被删光了。

---

## 8. 常见坑

- **清洗即丢数据**：`[^\x20-\x7E\n]` 会把非英文文本整段删掉，且不报错；每个清洗步骤都应统计"删掉了多少字符/文档"并抽样检查。
- **标签替换成空串导致粘词**：`HelloWorld` 这种词会污染词表和训练数据。
- **把 LSH 候选当成重复**：桶内只是候选，必须再做精确 Jaccard 校验；本代码做了，自己实现时容易漏。
- **shingle 粒度选错**：词级 5-gram 对改写不敏感，字符级/短 n-gram 又容易误删；阈值要用抽样人工复查来校准。
- **以为 padding mask 就够了**：打包后不同文档仍会互相注意，需要文档级 mask 和位置编码重置。
- **压缩比方向混淆**：本节是"字符/token"（高好），第 01 节是"token/字节"（低好）。
- **不设随机种子**：数据顺序不可复现，排查训练问题时无法重现同一批数据。
