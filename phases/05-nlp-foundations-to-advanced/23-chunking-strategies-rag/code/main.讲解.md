# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 23 节 面向 RAG 的 Chunking 策略 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`hashlib`、`math`、`re`），不需要 LangChain、sentence-transformers 或 API key

---

## 1. 这份代码在考察什么

这份代码把讲义中的 5 种切分策略都用纯 Python 实现了一遍，在同一份 5 章的小合同上对比 chunk 数量和检索召回：

1. **Fixed**：按字符数硬切，支持 overlap，并校验参数合法性。
2. **Recursive**：按 `\n\n` → `\n` → `. ` → 空格的优先级找边界，贪心地把小片段合并到不超过 `size`。
3. **Semantic**：相邻句子的 embedding 相似度低于阈值、且当前 chunk 足够长时才切。
4. **Sentence**：每 3 句一个 chunk。
5. **Parent-child**：先切大的 parent，再在每个 parent 内部切小的 child，记录映射关系。
6. **检索评测**：用 hashing-trick embedding 对每种切分做 recall@3。

> 一句话：**切分函数决定了"答案能不能作为一个完整单元被检索到"**。读这份代码时，要同时留意它的两个"反面教材"：recursive 实现缺了递归，评测指标已经饱和（第 3.3、3.8 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tokenize` / `hash_embed` / `cosine` | 函数 | 简易词袋哈希向量与点积 | embedding 替身（同第 22 节） |
| `chunk_fixed(text, size, overlap)` | 函数 | 按字符步长切片 | Fixed chunking |
| `chunk_recursive(text, size, seps)` | 函数 | 按分隔符优先级贪心合并 | Recursive chunking |
| `split_sentences(text)` | 函数 | 正则按 `.!?` 后的空白切句 | 句子边界检测 |
| `chunk_semantic(text, threshold, min_chars)` | 函数 | 相邻句相似度骤降处切，带最小长度 | Semantic chunking |
| `chunk_sentence(text, sentences_per_chunk)` | 函数 | 每 N 句一个 chunk | Sentence chunking |
| `chunk_parent_child(text, parent_size, child_size)` | 函数 | 两级切分，返回 child→parent 映射 | Parent-document |
| `retrieve_recall(chunks, query, gold_substrings, top_k)` | 函数 | top-k 中是否有 chunk 包含金标准子串 | recall@k |
| `main()` | 演示入口 | 5 章合同、5 种策略、3 条查询 | — |

数据流：`doc → 各 chunk_* 函数 → chunk 列表 → retrieve_recall（hash_embed + cosine 排序 + 子串匹配）→ 命中数`。

---

## 3. 逐段精讲

### 3.1 embedding 替身

```python
def hash_embed(text, dim=256):
    vec = [0.0] * dim
    for tok in tokenize(text):
        h = hashlib.md5(tok.encode()).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sign = 1.0 if h[4] % 2 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]
```

- 与第 22 节的 `hash_embed` 思路相同：每个词哈希到一个维度、加 ±1、最后 L2 归一化。区别是这里只做**一次** MD5，用前 4 字节决定位置、第 5 个字节的奇偶决定符号，省掉了第二次哈希。
- 它本质上是词袋，没有语义：`terminate` 和 `termination` 是两个毫不相关的维度。
- `cosine` 直接返回点积，依赖输入已归一化；它没有维度检查，因为这里所有向量都由同一个函数产生，维度必然一致。

### 3.2 Fixed：按字符步长切片

```python
def chunk_fixed(text, size, overlap=0):
    if size <= 0:
        raise ValueError("size must be positive")
    step = size - overlap
    if step <= 0:
        raise ValueError("overlap must be less than size")
    return [text[i:i + size] for i in range(0, len(text), step) if text[i:i + size].strip()]
```

- 每个 chunk 长 `size`，相邻 chunk 起点相距 `step = size - overlap`，所以相邻两块共享 `overlap` 个字符。
- **两道参数校验**比讲义 Step 1 的版本更严谨：`step == 0` 时 `range` 会直接报错，`step < 0` 时 `range` 静默返回空序列，整篇文档凭空消失。显式 `raise` 让错误在调用处暴露。
- 列表推导式末尾的 `if text[i:i + size].strip()` 过滤掉纯空白 chunk。
- ⚠️ 两个简化：
  - 按**字符**而不是 token 计数。生产中 chunk 大小通常以 token 计（要和 embedder 的最大输入长度对齐）。
  - 有 overlap 时，尾部可能出现一个完全包含在前一块中的短碎片，例如 `chunk_fixed("abcdefghij", 4, 2)` 的最后一块 `'ij'`。
- 本例 716 字符、`size=300, overlap=50` → 起点 0、250、500 → 3 块，第二块以 `"hapter 3."` 开头：fixed 切分会切断单词。

### 3.3 Recursive：按结构边界贪心合并

```python
def chunk_recursive(text, size, seps=("\n\n", "\n", ". ", " ")):
    if len(text) <= size:
        return [text.strip()] if text.strip() else []
    for sep in seps:
        if sep not in text:
            continue
        parts = text.split(sep)
        chunks = []
        buf = ""
        for p in parts:
            candidate = buf + sep + p if buf else p
            if len(candidate) <= size:
                buf = candidate
            else:
                if buf:
                    chunks.append(buf.strip())
                buf = p
        if buf:
            chunks.append(buf.strip())
        return [c for c in chunks if c]
    return chunk_fixed(text, size)
```

- **基本情况**：整段不超过 `size` 就直接返回，不再切。
- **选分隔符**：按优先级找到第一个在文本中出现的分隔符（段落 > 换行 > 句号空格 > 空格）。
- **贪心合并**：`buf` 是正在累积的 chunk。把下一个片段拼上去（`buf + sep + p`）后若仍不超过 `size` 就继续累积，否则先把 `buf` 输出，再从 `p` 开始新的 `buf`。这样 chunk 尽量大、又尽量不超过上限，而且只在分隔符处断开。
- 本例：5 个章节段落长度分别为 115、130、191、137、135。第 1、2 章合并为 247 字符；再加第 3 章会超过 300，于是第 3 章单独成块（191）；第 4、5 章合并为 274。共 3 块，每块都是完整的章节——这就是 recursive 的价值。
- 兜底：所有分隔符都不出现时，退回 `chunk_fixed` 硬切。
- ⚠️ **与讲义版本的关键差异（bug）**：讲义 Step 1 在循环里有一个分支——遇到 `len(p) > size` 的片段时，先输出 `buf`，再用更细的分隔符**递归**调用 `chunk_recursive(p, ...)`。这里没有这一步，函数名叫 recursive，却从不调用自己：超长片段被原样设为 `buf` 并输出。例如 `"Short intro.\n\n" + "This is sentence number one. " * 20` 以 `size=300` 切分，得到长度为 `[12, 579]` 的两块，第二块远超上限。本例的合同每章都不到 300 字符，所以没有暴露问题。修复见测验 Q9。

### 3.4 切句与 Semantic chunking

```python
def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def chunk_semantic(text, threshold=0.3, min_chars=40):
    sentences = split_sentences(text)
    if not sentences:
        return []
    embs = [hash_embed(s) for s in sentences]
    chunks = [[sentences[0]]]
    for i in range(1, len(sentences)):
        sim = cosine(embs[i], embs[i - 1])
        if sim < threshold and len(" ".join(chunks[-1])) >= min_chars:
            chunks.append([sentences[i]])
        else:
            chunks[-1].append(sentences[i])
    return [" ".join(c) for c in chunks]
```

- `(?<=[.!?])\s+` 是**后行断言**：匹配"前面紧跟 `.`、`!` 或 `?` 的空白"，按这些空白切开，标点留在前一句末尾。注意 `\n\n` 也是空白，所以段落结构在这里被抹平了。
- ⚠️ 简单正则切句会把 `"Chapter 1."`、`"Introduction."` 这样的标题当成独立句子（本例 21 个"句子"中有 10 个是标题）；`"Dr. Smith"`、`"3.14"` 等缩写/小数也会被错切（小数点后没有空白时不会切，`"Dr. Smith"` 会被切）。
- 核心规则：只有同时满足 ①与上一句相似度 < `threshold`（话题变了）②当前 chunk 至少 `min_chars` 个字符，才开新 chunk。第二个条件就是讲义强调的**最小长度护栏**，防止产生 40 token 级的碎片。
- `chunks` 是"列表的列表"，每个子列表是一组句子，最后统一 `" ".join`。
- ⚠️ 与讲义 Step 2 的差异：这里没有 `max_chars` 上限（讲义版本超长组会再交给 `chunk_recursive` 切），也只比较相邻两句，不看段落结构。后果在第 6 节可以看到：标题 `Chapter 3.` 被粘到第 2 章末尾。

### 3.5 Sentence chunking

```python
def chunk_sentence(text, sentences_per_chunk=3):
    sentences = split_sentences(text)
    return [" ".join(sentences[i:i + sentences_per_chunk])
            for i in range(0, len(sentences), sentences_per_chunk)]
```

- `range(0, n, 3)` 产生 0、3、6……，`sentences[i:i+3]` 取每组 3 句，最后一组可能不足 3 句（切片越界不会报错）。
- 简单、便宜，讲义说在一定长度内它能与 semantic 相当。但本例中标题也被算作"句子"，导致 `"The parties agree to the following terms. Chapter 2. Payment."` 这样的 chunk：第 2 章的标题跑到了第 1 章的块里。

### 3.6 Parent-child 映射

```python
def chunk_parent_child(text, parent_size=800, child_size=200):
    parents = chunk_recursive(text, size=parent_size)
    mapping = []
    for p_idx, parent in enumerate(parents):
        children = chunk_recursive(parent, size=child_size)
        for child in children:
            mapping.append({"child": child, "parent_idx": p_idx, "parent": parent})
    return mapping
```

- 两级 recursive：先切 parent，再在每个 parent 内切 child。这样保证每个 child **完整地属于一个 parent**，不会跨界。
- 返回一个字典列表，每项记录 child 文本、所属 parent 的下标和 parent 文本。检索时用 child 的向量，命中后用 `parent_idx` 找到 parent 返回——讲义 Step 3 的 `retrieve_parent` 还会按 `parent_idx` **去重**。
- 每个字典都存一份 parent 文本，方便但冗余；生产中通常只存 `parent_id`，parent 文本放在单独的文档存储里。
- 本例合同只有 716 字符，小于 `parent_size=800`，所以只有 **1 个 parent**（整篇文档），5 个 child 恰好是 5 个章节段落。

### 3.7 recall@k

```python
def retrieve_recall(chunks, query, gold_substrings, top_k=3):
    chunk_embs = [hash_embed(c) for c in chunks]
    q_emb = hash_embed(query)
    scored = sorted([(cosine(e, q_emb), i) for i, e in enumerate(chunk_embs)], reverse=True)
    top_texts = [chunks[i] for _, i in scored[:top_k]]
    return any(any(g.lower() in c.lower() for g in gold_substrings) for c in top_texts)
```

- 编码所有 chunk → 按余弦降序排序 → 取前 `top_k` → 只要有一个 chunk 包含任一金标准子串就算命中。
- 用**子串匹配**判断命中，而不是标注 chunk id：这让不同切分策略可以共用同一份标注（chunk 边界变了，答案文本不变），是评测 chunking 的实用技巧。
- 嵌套 `any`：外层遍历 top-k chunk，内层遍历金标准子串，`.lower()` 做大小写无关匹配。
- ⚠️ 每次调用都重新编码全部 chunk，3 条查询就编码 3 遍；生产中 chunk 向量应只算一次并建索引。
- ⚠️ `sorted(..., reverse=True)` 对 `(score, i)` 排序，同分时下标大的排前面（同第 22 节）。

### 3.8 主函数与评测设计

```python
    queries = [
        ("When can either party terminate?", ["ninety days", "thirty days"]),
        ("What is the late payment fee?", ["five percent"]),
        ("Which state laws apply?", ["California"]),
    ]

    for name, chunks in [("fixed", fixed), ("recursive", rec), ("semantic", sem),
                         ("sentence", sent), ("parent", [m["parent"] for m in pc])]:
        hits = sum(retrieve_recall(chunks, q, gold) for q, gold in queries)
```

- 三条查询分别落在第 3、2、5 章，都是事实型查询。
- `sum(...)` 直接对布尔值求和（True 计 1）。
- ⚠️ **指标饱和**：fixed 和 recursive 都只有 3 个 chunk，`top_k=3` 等于返回全部 chunk，召回必然是 3/3；`parent` 一行传入的是 5 份相同的 parent（整篇文档），同样必然 3/3。所以这张表对这三种策略**没有任何区分度**。只有 semantic（11 块）和 sentence（7 块）的结果有一点信息量。把 `top_k` 改为 1 可以看到差异：sentence 降到 2/3，其余仍为 3/3。
- ⚠️ 程序最后一句 "production embedders ... give 20-40 pp higher recall on the same chunks" 与本次输出（全部 100%）相矛盾，应理解为泛泛的经验说法，而不是这个实验能支持的结论。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 按字符计长度 | 无需 tokenizer，零依赖 | 生产按 token 计，并与 embedder 最大长度对齐 |
| fixed 显式校验 `size`/`overlap` | 防止 `range` 报错或静默返回空 | — |
| recursive 贪心合并 | chunk 尽量大且只在边界断开 | 缺少对超长片段的递归（bug）；LangChain 的实现会递归并可保留分隔符 |
| 正则切句 | 简单 | 标题、缩写会被错切；生产用 spaCy/NLTK 等句子切分器或按文档结构解析 |
| semantic 只有 `min_chars` | 演示最小长度护栏 | 缺 `max_chars`；只看相邻句，不尊重段落边界 |
| parent 文本冗余存储在映射里 | 演示方便 | 生产只存 `parent_id`，并在检索后去重 |
| 子串匹配判断命中 | 不同切分可共用一份标注 | 金标准子串要足够特异，否则会误判命中 |
| 3 条查询、1 篇文档、top-3 | 演示简短 | 指标饱和；生产用 50+ 条分层查询、多文档、recall@5/MRR |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 三引号多行字符串 | `doc = """Chapter 1. ..."""` | 保留换行，`\n\n` 即段落分隔 |
| `raise ValueError` | `raise ValueError("overlap must be less than size")` | 参数不合法时立即报错 |
| `range(start, stop, step)` | `range(0, len(text), step)` | step 为 0 报错，为负则在 start < stop 时为空序列 |
| 字符串切片 | `text[i:i + size]` | 越界不报错，自动截到末尾 |
| 列表推导式 + 过滤 | `[... for i in range(...) if text[i:i + size].strip()]` | 生成并过滤 |
| `str.strip()` 的真值 | `if text.strip()` | 空字符串为假值，用来判断"是否全是空白" |
| `in` 判断子串 | `if sep not in text`、`g.lower() in c.lower()` | 字符串包含检测 |
| `str.split(sep)` / `" ".join(...)` | `text.split(sep)`、`" ".join(c)` | 切分与拼接；`split` 会丢弃分隔符本身 |
| 条件表达式 | `buf + sep + p if buf else p` | `buf` 为空时不加分隔符 |
| 循环内 `return` + 循环后兜底 | 循环中命中分隔符即 `return`；循环结束后 `return chunk_fixed(text, size)` | 只有所有分隔符都不出现时才会执行到最后一行 |
| 正则后行断言 | `re.split(r"(?<=[.!?])\s+", ...)` | `(?<=...)` 只检查前面的字符，不消耗它们，所以标点保留在句末 |
| 列表的列表 | `chunks = [[sentences[0]]]`、`chunks[-1].append(...)` | `[-1]` 取最后一个子列表 |
| 字典字面量 | `{"child": child, "parent_idx": p_idx, "parent": parent}` | 一条映射记录 |
| 集合推导式 | `{m["parent_idx"] for m in pc}` | 去重统计 parent 数 |
| 嵌套 `any` + 生成器 | `any(any(g.lower() in c.lower() for g in gold_substrings) for c in top_texts)` | 两层"存在"判断，短路求值 |
| `sum` 布尔值 | `sum(retrieve_recall(...) for q, gold in queries)` | True 计 1，False 计 0 |
| f-string 对齐 | `f"  {name:<12}: {hits} / {len(queries)}"` | `<12` 左对齐占 12 格 |

---

## 6. 运行结果解读

实际运行 `python3 main.py` 的输出：

```text
=== strategy comparison ===

fixed (300 chars, 50 overlap):    3 chunks
recursive (300 chars):            3 chunks
semantic (hash-trick):            11 chunks
sentence (3 per chunk):           7 chunks
parent-child (800 / 200):         5 children, 1 parents

=== recall@3 on 3 queries ===
  fixed       : 3 / 3
  recursive   : 3 / 3
  semantic    : 3 / 3
  sentence    : 3 / 3
  parent      : 3 / 3

note: hash-trick embedder is noisy.
production embedders (BGE, text-3) give 20-40 pp higher recall on the same chunks.
```

逐行解读（括号内是额外打印各 chunk 后观察到的内容）：

- **fixed：3 块**（长度 300、300、216）。第二块从第 250 个字符开始，以 `"hapter 3. Termination."` 开头；第一块在 `"Either party may terminate "` 处被截断。终止条款被拆在两块里。
- **recursive：3 块**（247、191、274），分别是"第 1+2 章""第 3 章""第 4+5 章"，全部在段落边界断开。这是讲义推荐它作默认值的直观理由。
- **semantic：11 块**。合同被正则切成 21 个"句子"（含 10 个标题），哈希向量下大多数相邻句的余弦为 0，所以只要当前块满 40 字符就切，结果接近"每一两句一块"。其中出现 `'Late payments incur a five percent fee. Chapter 3.'`：上一块只有 39 个字符，没达到 `min_chars`，标题 `Chapter 3.` 只好被追加进来；接下来 `Termination.` 又开了新块。标题和内容被拆散（修复见测验 Q11）。
- **sentence：7 块**。同样有标题错位，如 `'The parties agree to the following terms. Chapter 2. Payment.'`。
- **parent-child：5 个 child、1 个 parent**。文档短于 800 字符，parent 就是整篇文档；5 个 child 正好是 5 个章节。
- **recall@3 全部 3/3**：如第 3.8 节所述，fixed、recursive、parent 三行在结构上必然满分；semantic 和 sentence 虽然 chunk 更多，但查询词（`terminate`、`late`、`payment`、`laws`、`california` 等）与对应章节有明显词面重叠，top-3 也都命中了。这张表**不能**说明"五种策略一样好"，只能说明评测太简单。
- **最后两行**：第一句提醒哈希 embedding 很粗糙；第二句"生产模型召回高 20–40 个百分点"在全部 100% 的结果下无从体现。

---

## 7. 动手改一改

1. 修复 `chunk_recursive`：遇到 `len(p) > size` 时用更细的分隔符递归切分，并用 `"Short intro.\n\n" + "This is sentence number one. " * 20` 验证所有块都不超过 300（参考测验 Q9）。
2. 让评测有区分度：把 `top_k` 改为 1，再把合同复制成 5 份不同公司名的合同（每份单独切分后合并），观察各策略的 recall 变化。
3. 在 `chunk_parent_child` 的评测中改为"用 child 检索、按 `parent_idx` 去重后返回 parent"，实现讲义 Step 3 的 `retrieve_parent` 逻辑。
4. 实现"结构优先"的 semantic：先按 `\n\n` 切段落，再在段落内调用 `chunk_semantic`，确认 `Chapter 3.` 回到第 3 章的块中（参考测验 Q11）。
5. 给 `chunk_semantic` 加上 `max_chars` 上限，超长组交给 `chunk_recursive` 再切，与讲义 Step 2 对齐。
6. 进阶：把长度单位从字符换成 token（例如用第 19 节训练的 BPE，或简单地按空格数词），对比同样 `size` 下 chunk 数的变化。

---

## 8. 常见坑

- **函数名叫 recursive 却不递归**：超长段落原样输出，chunk 可能远超 embedder 的最大输入长度，被静默截断。
- **评测指标饱和**：chunk 数不超过 top-k 时 recall 必然 100%；parent 不去重时也会"自动命中"。
- **简单正则切句**：标题、缩写被当成句子，导致标题与正文分离。
- **overlap 的尾部碎片**：fixed 切分加 overlap 时，最后可能产生一个被前一块完全包含的短 chunk。
- **只按字符计长度**：中英文、代码的字符/token 比差异很大，上线前要按 token 校准。
- **跨文档切分**：本例只有一篇文档没有暴露，但如果把多篇文档拼起来再切，就会产生跨文档 chunk（讲义 Pitfalls 明确禁止）。
