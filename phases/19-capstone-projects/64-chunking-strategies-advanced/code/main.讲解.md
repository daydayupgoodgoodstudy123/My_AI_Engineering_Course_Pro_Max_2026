# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 64 节 Chunking 策略比较 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`cd code && python3 main.py`；测试 `python3 -m pytest -q tests`（或 `python3 -m unittest discover tests`） ｜ **依赖**：仅标准库（`math`、`re`、`dataclasses`、`typing`），无需网络与第三方包

---

## 1. 这份代码在考察什么

RAG 的第一步是把文档切成块。这份代码用纯标准库实现五种 chunker，并用同一套 recall@k 评估比较它们：

1. **五种切分策略**：fixed-window（带重叠）、sentence 打包、recursive split、semantic 聚类、structural markdown。
2. **字符偏移**：每个 `Chunk` 都记录原文中的 `[start, end)`，这样才能与金标准答案 span 比较。
3. **离线可复现的"embedding"**：`mock_embed` 用 token 哈希构造归一化向量，不依赖任何模型。
4. **Dense 检索**：`DenseIndex` 用余弦相似度做暴力 top-k。
5. **评估**：三份 fixture 文档（散文、markdown、混合）× 每份 3 个 query，每个 query 带金标准 span，计算 recall@1/3/5。

> 一句话：**用最少的代码把"切法 → 检索 → 是否命中答案"这条链路量化出来**。同时，这个评估本身有明显的偏差（每篇文档单独建索引、块数 ≤ k、整篇当一块必中），读懂这些偏差与读懂五种 chunker 同样重要。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Chunk` | dataclass | `doc_id`、`strategy`、`start`、`end`、`text`；`overlaps()` 判断与金标准是否重叠 | 块 + 偏移 |
| `fixed_window` | 函数 | 按 `size` 切、步长 `size − overlap` | 策略 1 |
| `_SENTENCE_BOUNDARY` / `split_sentences` | 正则 / 函数 | 句子切分，返回 `(start, end, text)` | 句子边界 |
| `sentence_chunks` | 函数 | 把句子装进 `target` 字符预算 | 策略 2 |
| `DEFAULT_SEPARATORS` / `_recursive_split` / `recursive_split` | 常量 / 递归函数 | 按分隔符层级递归切分再打包 | 策略 3 |
| `_token_hashes` / `mock_embed` / `cosine` | 函数 | 哈希词袋向量；点积即余弦 | mock embedding |
| `semantic_chunks` | 函数 | 逐句与质心比较，低于阈值或超长就切 | 策略 4 |
| `_HEADER` / `structural_markdown` | 正则 / 函数 | 在 `#`~`######` 标题处切 | 策略 5 |
| `DenseIndex` | dataclass | `add` 存向量、`search` 暴力 top-k | 稠密检索 |
| `PROSE_DOC` / `MARKDOWN_DOC` / `MIXED_DOC` + `*_QUERIES` | 常量 | 三份 fixture 文档与 (query, 金标准文本) | 评估数据 |
| `_locate` / `build_fixture` | 函数 | 把金标准文本定位成字符区间 | 金标准 span |
| `eval_recall` | 函数 | 每篇文档建索引、对每个 k 统计命中 | recall@k |
| `STRATEGIES` | 字典 | 策略名 → 参数固定好的 lambda | 策略注册表 |
| `main` | 函数 | 打印 recall 表与块数 | 演示 |

数据流：`build_fixture()` → 对每个策略：对每篇文档 `chunker(doc_id, text)` → `DenseIndex.add` → 每个 query `search(q, k)` → `overlaps(gold)` → 汇总 recall@k。

---

## 3. 逐段精讲

### 3.1 `Chunk` 与重叠判断

```python
@dataclass
class Chunk:
    doc_id: str
    strategy: str
    start: int
    end: int
    text: str

    def overlaps(self, gold_start: int, gold_end: int) -> bool:
        return not (self.end <= gold_start or self.start >= gold_end)
```

- 区间都是**半开** `[start, end)`。两个区间不重叠当且仅当"一个在另一个左边"：`end <= gold_start` 或 `start >= gold_end`；取反即重叠。
- 只要重叠 1 个字符就算命中——这是"宽松"的判定，也是评估偏爱大块的根源。
- `strategy` 字段记录块由哪个策略产生，对应讲义 "Persist the strategy name in each chunk's metadata"。

### 3.2 策略 1：fixed-window

```python
def fixed_window(doc_id, text, size=400, overlap=80):
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be non-negative and smaller than size")
    out = []
    step = size - overlap
    i = 0
    n = len(text)
    while i < n:
        end = min(i + size, n)
        out.append(Chunk(doc_id, "fixed", i, end, text[i:end]))
        if end == n:
            break
        i += step
    return out
```

- `overlap >= size` 会使步长 ≤ 0、死循环，所以提前报错。
- `if end == n: break`：到达末尾就停，避免生成一个完全被上一块包含的尾块。
- 在 880 字符的 `PROSE_DOC` 上得到 `[0,400)`、`[320,720)`、`[640,880)`。实测三个块的边界分别切在 "...partial state cle|aned up" 和 "...the storage call go|es out" 处——讲义说的 **mid-word cut**。

### 3.3 句子切分与策略 2：sentence 打包

```python
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

def split_sentences(text):
    out = []
    cursor = 0
    for m in _SENTENCE_BOUNDARY.finditer(text):
        end = m.start()
        if end > cursor:
            out.append((cursor, end, text[cursor:end]))
        cursor = m.end()
    if cursor < len(text):
        out.append((cursor, len(text), text[cursor:]))
    return out
```

- 正则：`(?<=[.!?])` 是**后行断言**（前面必须是句末标点），`\s+` 是要"吃掉"的空白，`(?=[A-Z0-9])` 是**先行断言**（后面必须是大写字母或数字）。断言本身不消耗字符，所以句末标点留在前一句里，下一句的首字母留在下一句里。
- `finditer` 逐个找到边界空白，`m.start()` 是上一句的结束，`m.end()` 是下一句的开始。
- ⚠️ markdown 标题以 `#` 开头，不满足 `[A-Z0-9]`，于是标题会被**粘到上一句**里。`MARKDOWN_DOC` 的第一个"句子"从 `# Storage Service Configuration` 一直延续到 "Each client carries a retry budget."。
- ⚠️ 缩写会被错切：`"Dr. Smith arrived."` 被切成 `"Dr."` 和 `"Smith arrived."`（实测）；小写或括号开头的句子不会被切开。

```python
def sentence_chunks(doc_id, text, target=500):
    ...
    for s_start, s_end, s_text in sents:
        if cur_start is None:
            cur_start = s_start
        sep = " " if cur_buf else ""
        added = len(sep) + len(s_text)
        if cur_len + added > target and cur_buf:
            out.append(Chunk(doc_id, "sentence", cur_start, cur_end, " ".join(cur_buf)))
            cur_start = s_start
            cur_buf = [s_text]
            cur_len = len(s_text)
            cur_end = s_end
            continue
        cur_buf.append(s_text)
        cur_len += added
        cur_end = s_end
```

- 贪心装箱：加上这一句会超预算、且当前块非空时，先输出当前块，再用这一句开新块。
- `and cur_buf` 保证单个超长句子也能单独成块（不会死循环，也不会被丢弃），代价是这个块超出 `target`。
- ⚠️ 块文本是 `" ".join(cur_buf)`，原文中的 `\n\n` 被换成空格，`chunk.text != text[start:end]`（prose 上 2 块都不一致）。偏移仍正确，评估不受影响，但高亮/引用时要注意。

### 3.4 策略 3：recursive split

```python
DEFAULT_SEPARATORS = ("\n\n", "\n", ". ", " ")

def _recursive_split(text, base_offset, separators, target):
    if len(text) <= target or not separators:
        if not text:
            return []
        return [(base_offset, base_offset + len(text), text)]
    sep = separators[0]
    rest = separators[1:]
    if sep not in text:
        return _recursive_split(text, base_offset, rest, target)
    pieces = []
    cursor = 0
    parts = text.split(sep)
    for idx, part in enumerate(parts):
        start = cursor
        cursor += len(part)
        if idx < len(parts) - 1:
            cursor += len(sep)
        if not part:
            continue
        if len(part) <= target:
            pieces.append((base_offset + start, base_offset + start + len(part), part))
        else:
            pieces.extend(_recursive_split(part, base_offset + start, rest, target))
```

- **终止条件**：文本已经装得下，或者分隔符用完（此时即使超长也原样返回）。
- **当前分隔符不存在**：直接换下一个分隔符递归。
- **偏移计算**：`cursor` 逐段累加 `len(part) + len(sep)`，`base_offset` 把子串内的偏移换算成原文偏移——这是递归切分最容易写错的地方。
- 超长的段落用剩下的分隔符 `rest` 继续递归。

```python
    packed = []
    for p_start, p_end, p_text in pieces:
        if packed and (p_end - packed[-1][0]) <= target:
            prev_start, _, prev_text = packed[-1]
            packed[-1] = (prev_start, p_end, prev_text + sep + p_text)
        else:
            packed.append((p_start, p_end, p_text))
    return packed
```

- **打包**：相邻的小块如果合并后跨度仍 ≤ `target`，就合并，避免产生大量碎块。合并判断用的是原文跨度 `p_end − 起点`，包含了中间的分隔符。
- 合并后的文本用 `sep` 重新拼接。我们用 3000 个随机文本做了 `chunk.text == text[start:end]` 检查，全部一致。
- 用 `". "` 切分时，句号被当成分隔符的一部分，所以单独成块的句子会**丢掉结尾的句号**（如 `'aaaa. bbbb'`）。
- 公开函数 `recursive_split` 最后过滤掉纯空白的块。实测 prose 上切出 278、305、293 三块，恰好对应三个段落。

### 3.5 Mock embedding 与余弦

```python
def _token_hashes(text, dim):
    vec = [0.0] * dim
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = 0
        for ch in tok:
            h = (h * 1315423911) ^ ord(ch)
            h &= 0xFFFFFFFF
        vec[h % dim] += 1.0
        vec[(h >> 7) % dim] += 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))
```

- 小写化后取字母数字 token，对每个 token 计算一个 32 位滚动哈希（`& 0xFFFFFFFF` 截断到 32 位），在两个桶上分别加 1.0 和 0.5，最后 L2 归一化。
- 本质是**哈希词袋**（feature hashing）：只反映"共享了哪些词"，不理解同义词，也不去停用词；96 维还会有哈希碰撞。
- 因为向量已经归一化，`cosine` 直接做点积即可。
- `or 1.0`：空文本时范数为 0，避免除以 0。
- ⚠️ 不去停用词的后果：prose 查询 "what is the abort threshold per bucket" 在 fixed 策略下，不含答案的第 0 块得分 0.529，高于含答案的第 1 块 0.491。

### 3.6 策略 4：semantic 聚类

```python
    for s_start, s_end, s_text in sents:
        v = mock_embed(s_text)
        cur_chars = sum(s[1] - s[0] for s in cur_sents)
        if cur_vec is None:
            cur_vec = v
            cur_sents.append((s_start, s_end, s_text))
            cur_n = 1
            continue
        sim = cosine(cur_vec, v)
        if sim < similarity_threshold or cur_chars + (s_end - s_start) > max_chars:
            flush()
            cur_sents = [(s_start, s_end, s_text)]
            cur_vec = v
            cur_n = 1
        else:
            cur_sents.append((s_start, s_end, s_text))
            cur_n += 1
            cur_vec = [(cur_vec[i] * cur_n + v[i]) / (cur_n + 1) for i in range(len(cur_vec))]
            norm = math.sqrt(sum(x * x for x in cur_vec)) or 1.0
            cur_vec = [x / norm for x in cur_vec]
    flush()
```

- 每句与"当前块的质心"比较：相似度低于阈值（话题漂移）**或**加上这句会超过 `max_chars`（硬上限，讲义"Combine semantic with a hard character cap"）就切。
- `flush` 是**闭包**：定义在函数内部，直接读取外层的 `cur_sents` 和 `chunks`。注意 `cur_sents = [...]` 的重新赋值发生在外层函数里，`flush` 每次调用时读到的是最新的值。
- ⚠️ **质心权重差一（bug）**：`cur_n += 1` 放在计算均值之前，导致旧质心权重偏大。两句 `e1=[1,0]`、`e2=[0,1]` 时得到 `[0.894, 0.447]`，正确方向应为 `[0.707, 0.707]`。修正：先算均值再自增，或维护未归一化的向量和（测验 Q10）。
- `cur_chars` 只累加句子本身的长度，不含句间空白，所以实际块跨度可能略超 `max_chars`。
- 在 mock embedding 下相邻句相似度大多低于 0.55，prose 的 12 句被切成 11 块（块长 24–212），markdown 4 块、mixed 5 块，合计 20 块。

### 3.7 策略 5：structural markdown

```python
_HEADER = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

def structural_markdown(doc_id, text):
    matches = list(_HEADER.finditer(text))
    if not matches:
        return [Chunk(doc_id, "structural", 0, len(text), text)]
    out = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            out.append(Chunk(doc_id, "structural", start, end, body))
    return out
```

- `re.MULTILINE` 让 `^`、`$` 匹配每一行的开头和结尾；`#{1,6}` 匹配 1–6 个 `#`；第 1 组是级别、第 2 组是标题文字。
- 每块从一个标题开始，到**下一个标题（任意级别）**之前结束。
- ⚠️ **没有标题时整篇一块**：prose 文档 880 字符成为唯一的块，单文档索引下 recall 必然为 1——表中 structural 的 1.00 有一部分是这样"赢"来的。
- ⚠️ **第一个标题之前的前言被丢弃**（实测 `"Preamble text here."` 不出现在任何块中）。
- ⚠️ **只有标题的块**不会被过滤（例如紧跟子标题的 `## A1`）。讲义 Failure modes 提到要过滤或合并，代码没做。
- ⚠️ 讲义说每块到"同级或更高级标题"为止，代码在任意级别标题处都切，父节不包含子节。
- ⚠️ 代码块里的 `# comment` 也会被当成标题。
- 块文本 `strip()` 过，`end` 却包含尾部空白，所以 `text != text[start:end]`（不影响评估）。

### 3.8 `DenseIndex`、fixture 与评估

```python
@dataclass
class DenseIndex:
    vectors: list[tuple[Chunk, list[float]]] = field(default_factory=list)

    def add(self, chunk):
        self.vectors.append((chunk, mock_embed(chunk.text)))

    def search(self, query, k):
        qv = mock_embed(query)
        scored = [(c, cosine(qv, v)) for c, v in self.vectors]
        scored.sort(key=lambda x: -x[1])
        return [c for c, _ in scored[:k]]
```

- `field(default_factory=list)`：dataclass 的可变默认值必须这样写，否则所有实例会共享同一个列表。
- 暴力检索：对每个块算余弦，降序排序取前 k，复杂度 O(N·d)。生产中用 ANN 索引（HNSW、IVF）。
- `sort` 是稳定排序，分数并列时保持插入顺序（文档靠前的块优先）。

```python
def _locate(doc, span_text):
    start = doc.index(span_text)
    return start, start + len(span_text)
```

- 金标准用"答案原文"定义，再用 `str.index` 找到字符偏移。找不到会抛 `ValueError`，相当于对 fixture 的自检。如果答案文本在文档中出现多次，只取第一次。

```python
def eval_recall(chunker, fixture, ks=(1, 3, 5)):
    totals = {k: 0 for k in ks}
    hits = {k: 0 for k in ks}
    for doc in fixture:
        chunks = chunker(doc["doc_id"], doc["text"])
        idx = DenseIndex()
        for c in chunks:
            idx.add(c)
        for query, (g_start, g_end) in doc["queries"]:
            for k in ks:
                totals[k] += 1
                top = idx.search(query, k)
                if any(c.overlaps(g_start, g_end) for c in top):
                    hits[k] += 1
    return {k: hits[k] / totals[k] if totals[k] else 0.0 for k in ks}
```

- ⚠️ **每篇文档单独建索引**：相当于事先知道答案在哪篇文档里。每篇文档的块数多在 1–4，k = 3、5 时 top-k 往往就是全部块，recall 恒为 1。
- 换成"所有文档一个索引"后结果大变（第 6 节）。
- 每个 k 都重新 `search` 一次，可以优化为只搜 `max(ks)` 再截取前缀。

```python
STRATEGIES: dict[str, ChunkFn] = {
    "fixed":      lambda d, t: fixed_window(d, t, size=400, overlap=80),
    ...
}
```

- 用 lambda 把各策略的参数"固定"下来，统一成 `(doc_id, text) -> list[Chunk]` 的签名 `ChunkFn`，评估函数就能一视同仁地调用。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 每个块保存 `[start, end)` 偏移 | 可以与金标准 span 精确比较、可回溯引用 | sentence/structural 的 `text` 与偏移切片不完全一致 |
| 哈希词袋 mock embedding | 离线、确定、零依赖 | 不懂语义、不去停用词；semantic chunker 的行为与真实模型完全不同 |
| 按字符计长度 | 简单 | embedding 模型按 token 限长；讲义练习 1 用 tiktoken |
| 句子切分用一个正则 | 零依赖 | 缩写、标题、引号处出错；生产用 Punkt/spaCy |
| recursive 先切后打包 | 尊重结构又避免碎块 | 句号随分隔符丢失；不理解语义 |
| semantic 加 `max_chars` 硬上限 | 防止均匀主题时欠切成巨块 | 质心更新有差一 bug；依赖 embedding 质量 |
| structural 在任意级别标题处切 | 实现简单、块小 | 与讲义描述不符；丢前言、纯标题块、代码块误判 |
| 重叠即命中的 recall@k | 简单直观 | 偏爱大块；应同时报告块长与返回 token 数 |
| 每篇文档单独建索引 | 隔离文档间干扰 | 不符合真实 RAG；块数 ≤ k 时指标失效 |
| 9 个 query 的 fixture | 秒级运行 | 每个 query 占 0.11，无法得出稳健结论 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 方法 | `class Chunk: ... def overlaps(...)` | 数据类也可以定义普通方法 |
| `field(default_factory=list)` | `DenseIndex.vectors` | 可变默认值必须用工厂函数 |
| `typing.Callable` 类型别名 | `ChunkFn = Callable[[str, str], list[Chunk]]` | 描述"接收两个 str、返回 Chunk 列表"的函数类型 |
| 字典注解 | `STRATEGIES: dict[str, ChunkFn] = {...}` | 变量注解 |
| `lambda` | `lambda d, t: fixed_window(d, t, size=400, overlap=80)` | 匿名函数，用来固定参数 |
| `re.compile` 与断言 | `(?<=[.!?])\s+(?=[A-Z0-9])` | 后行断言 / 先行断言不消耗字符 |
| `re.MULTILINE` | `_HEADER` | 让 `^`/`$` 按行匹配 |
| `finditer` 与 match 对象 | `m.start()`、`m.end()`、`m.group(1)` | 遍历所有匹配并取位置/分组 |
| `re.findall` | `re.findall(r"[a-z0-9]+", text.lower())` | 返回全部匹配的字符串列表 |
| 递归函数 | `_recursive_split` 调用自身 | 每次用更弱的分隔符处理超长片段 |
| 元组切片 | `separators[0]`、`separators[1:]` | 取第一个与其余 |
| 元组解包 | `for s_start, s_end, s_text in sents`、`for query, (g_start, g_end) in doc["queries"]` | 支持嵌套解包 |
| 闭包 | `semantic_chunks` 里的 `def flush()` | 内部函数读取外层变量 |
| `X \| None` 注解 | `cur_vec: list[float] \| None = None` | 可选类型 |
| 位运算 | `h = (h * 1315423911) ^ ord(ch)`、`h &= 0xFFFFFFFF`、`h >> 7` | 异或、按位与截断 32 位、右移 |
| `or` 提供默认值 | `math.sqrt(...) or 1.0` | 左边为 0（假值）时取右边 |
| `str.index` | `doc.index(span_text)` | 找不到时抛 `ValueError`（`find` 返回 −1） |
| 字典推导式 | `{k: 0 for k in ks}`、`{k: hits[k] / totals[k] if totals[k] else 0.0 for k in ks}` | 带条件表达式的推导式 |
| `any` + 生成器 | `any(c.overlaps(g_start, g_end) for c in top)` | 有一个为真就返回 True，并短路 |
| `sort(key=lambda x: -x[1])` | `DenseIndex.search` | 按分数降序（也可写 `reverse=True`） |
| f-string 对齐 | `f"{name:<12}"`、`f"  {recall[k]:.2f}  "` | 左对齐宽 12；2 位小数 |
| 括号内隐式拼接字符串 | `PROSE_DOC = ("The retry budget ..." "It exists ...")` | 相邻字符串字面量自动拼接 |

---

## 6. 运行结果解读

实际运行（标准库，瞬时完成）：

```text
strategy     | recall@1 | recall@3 | recall@5
--------------------------------------------
fixed        |   0.89   |   1.00   |   1.00
sentence     |   0.78   |   1.00   |   1.00
recursive    |   1.00   |   1.00   |   1.00
semantic     |   0.67   |   1.00   |   1.00
structural   |   1.00   |   1.00   |   1.00

chunk counts per strategy (across all fixture docs):
  fixed        8 chunks
  sentence     6 chunks
  recursive    7 chunks
  semantic     20 chunks
  structural   9 chunks
```

逐文档拆开看（我们补充统计）：

| 策略 | prose 块数 / 块长 | markdown 块数 | mixed 块数 | 未命中的 query（recall@1） |
|------|------------------|--------------|-----------|--------------------------|
| fixed | 3 / 400, 400, 240 | 2 | 3 | prose 的 "abort threshold" |
| sentence | 2 / 407, 470 | 2 | 2 | prose 的 "abort threshold"、markdown 的 "where is the abort threshold configured" |
| recursive | 3 / 278, 305, 293 | 2 | 2 | 无 |
| semantic | 11 / 24–212 | 4 | 5 | prose 1 个、markdown 2 个 |
| structural | 1 / 880 | 4 | 4 | 无 |

解读：

- **recall@3/5 全是 1.00** 不是因为检索好：每篇文档单独建索引，除 semantic 外每篇只有 1–4 块，k ≥ 块数时必然命中。
- **structural 的 1.00** 中，prose 那 3 个 query 是"整篇一块"白送的。
- **semantic 最差（0.67）**：mock embedding 是词袋，句子被切得很碎，短块的向量不稳定。这与讲义 Build It 中"Semantic clustering wins on the prose fixture"的描述相反；讲义"Sentence loses on the structured fixture"也只部分成立（sentence 在 markdown 上错了 1 个）。
- **全局索引**：把三份文档的块放进同一个索引后，recall@1 变为 fixed 0.56、sentence 0.44、recursive 0.33、semantic 0.44、structural 0.33；recall@3 为 0.78、0.89、1.00、0.67、1.00。排名完全改变，说明讲义表格的结论对评估设定非常敏感。
- 每个 query 占 1/9 ≈ 0.11，表中任意两行差一个 query，都不足以下结论。

---

## 7. 动手改一改

1. **全局索引评估**：写 `eval_recall_global`（测验 Q11），同时报告每个策略的平均块长与"top-k 返回的总字符数"，看哪个策略在相同字符预算下最好。
2. **修 semantic**：修正质心更新的差一 bug，改成维护未归一化的向量和；扫描 `similarity_threshold ∈ {0.2, 0.3, 0.4, 0.55}`，画出块数与 recall@1 的关系。
3. **修 structural**：保留前言、合并纯标题块、给每块加标题路径前缀、跳过 ``` 代码块中的 `#` 行（测验 Q9）；无标题时回退到 `recursive_split`。
4. **讲义练习 1（token 窗口）**：用 `tiktoken`（或简单的空白分词）按 token 数切分，与按字符的 fixed-window 比较块数与 recall。
5. **讲义练习 2（注入代码块）**：在 prose 文档里插入 30% 的 Python/YAML 代码块，观察 fixed-window 的 mid-symbol cut 和 sentence 切分在代码上的表现。
6. **讲义练习 4（块摘要）**：给每块拼接一句"标题/首句"作为摘要再 embedding，比较 recall 的变化；再试着把 `mock_embed` 改为去停用词的版本，观察 prose "abort threshold" 那个 query 是否被修复。

---

## 8. 常见坑

- **只看 recall 不看块长**：整篇文档一块的 recall 永远是 1，但对 LLM 没用。
- **每篇文档单独评估**：与真实 RAG 不符，k 稍大时指标失效。
- **偏移写错**：递归切分时忘了加 `base_offset`、`split` 后忘了加分隔符长度，评估会悄悄出错。建议断言 `text[start:end]` 与块内容一致（或一致到空白）。
- **`overlap >= size`**：步长 ≤ 0 会死循环，必须校验。
- **句子正则遇到缩写和标题**：`Dr.` 被切开、`## Title` 粘到上一句。
- **语义切分依赖 embedding 模型**：换模型后块边界也会变，索引必须一起重建（讲义 stale embeddings）。
- **标题块丢上下文**：子节块里没有父标题，检索 "abort threshold configured" 时缺少 "Storage Service" 的语境；加标题路径前缀能缓解。
- **dataclass 可变默认值**：`vectors: list = []` 会报错，必须用 `field(default_factory=list)`。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m pytest -q tests`（`tests/test_chunkers.py` 会把上级目录加入 `sys.path` 再 `from main import ...`，所以也可以 `python3 -m unittest discover tests`）。

| 测试 | 验证的性质 |
|------|-----------|
| `TestFixedWindow.test_emits_at_least_one_chunk` | 218 字符的样例文本、size 80 时至少 2 块（方法名说"至少 1 块"，断言是 ≥ 2） |
| `TestFixedWindow.test_overlap_visible` | 相邻块的重叠 `a.end − b.start ≥ 20` |
| `TestFixedWindow.test_rejects_bad_args` | `size=0`、`overlap == size` 抛 `ValueError` |
| `TestSentenceChunks.test_does_not_split_mid_word` | 块不以空格开头。断言 `c.text.split()[0][:1] != ""` 恒为真，实际起作用的只有 `startswith(" ")` 这一条，不能真正证明"不切断单词" |
| `TestSentenceChunks.test_full_coverage` | Alpha、Zeta、Theta 都出现在某个块里 |
| `TestRecursiveSplit.test_respects_target_when_possible` | target 80 时每块 ≤ 200 字符（阈值很宽松） |
| `TestRecursiveSplit.test_handles_short_input` | 短文本只出 1 块 |
| `TestSemantic.test_low_threshold_packs_into_few_chunks` | 阈值 0 时 ≤ 2 块 |
| `TestSemantic.test_high_threshold_splits_more` | 阈值 0.99 的块数 ≥ 阈值 0.1 的块数 |
| `TestStructuralMarkdown.test_one_chunk_per_header` | 4 个标题 → 4 块，第一块以 `# Top` 开头，含 "B sub" 的块存在 |
| `TestStructuralMarkdown.test_returns_whole_doc_when_no_headers` | 无标题 → 1 块 |
| `TestMockEmbed.test_deterministic` / `test_normalized` | 同输入同输出；L2 范数为 1 |
| `TestDenseIndex.test_returns_topk` | 返回 2 个结果，第一个含 "banana" |
| `TestEvalRecall.test_recall_is_a_fraction` | 所有策略的 recall ∈ [0, 1] |
| `TestEvalRecall.test_recall_monotonic_in_k` | recall@1 ≤ recall@3 ≤ recall@5 |

实际运行结果：

```text
................                                                         [100%]
16 passed in 0.06s
```

测试没有覆盖：块偏移与原文是否一致、structural 丢前言/纯标题块、semantic 质心计算、讲义 Build It 中"哪个策略在哪类文档上赢"的结论。
