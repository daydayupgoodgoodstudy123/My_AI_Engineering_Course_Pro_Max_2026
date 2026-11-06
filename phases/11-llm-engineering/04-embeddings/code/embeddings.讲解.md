# 代码讲解 · embeddings.py

> **所属小节**：阶段 11 · LLM 工程 · 第 04 节 Embeddings 与向量表示 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python embeddings.py` ｜ **依赖**：`numpy`（第三方）+ 标准库 `math`、`collections`；无需 API key、无需网络。同目录 `main.ts` 是 TypeScript 移植版，本讲解只覆盖 Python 版。

---

## 1. 这份代码在考察什么

讲义 Build It 一节的口号是"No vector database. No external embedding API. Pure Python with numpy"。这份代码搭了一个**完整的语义检索流水线骨架**：

1. **切块（chunking）**：固定长度 + 重叠、按句两种方式。
2. **向量化（embedding）**：`SimpleEmbedder`，实为 TF-IDF + L2 归一化。
3. **相似度**：cosine、dot product、Euclidean，以及二值化后的 Hamming 距离。
4. **向量索引**：`VectorIndex` 暴力（brute-force）检索 top-k。
5. **检索引擎**：`SemanticSearchEngine` 把"切块 → fit → embed → 入库 → 查询"串起来。
6. **进阶演示**：Matryoshka 截断、二值量化、chunk 大小实验。

对应讲义概念：dense vs sparse、相似度度量、向量数据库与 ANN、chunking、Matryoshka、binary quantization。

> 一句话：**把 RAG 的"检索那一半"拆成可读的 300 行代码——接口与生产系统一致（文本进、向量出、按相似度取 top-k），只是 embedder 是个"假的" embedding**。要读懂这份代码，最重要的是看清 TF-IDF 与神经 embedding 的差别：讲义称它为"a simple dense embedding"，但它其实是**稀疏**的，也因此解决不了讲义开头提出的词汇不匹配问题；STEP 6、STEP 7 的演示在它上面都会失真。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `chunk_text` | 函数 | 按词数切块，相邻块重叠 `overlap` 个词 | 固定长度切块 |
| `chunk_by_sentences` | 函数 | 按 `.` 切句，累加到词数上限 | 按句切块 |
| `SimpleEmbedder` | 类 | `fit` 建词表与平滑 IDF；`embed` 生成 L2 归一化的 TF-IDF 向量 | embedding 接口（实为稀疏表示） |
| `cosine_similarity` / `dot_product` / `euclidean_distance` | 函数 | 三种相似度 | 相似度度量 |
| `binarize` / `hamming_distance` | 函数 | 正值→1，其余→0；数不同位 | 二值量化 |
| `VectorIndex` | 类 | 存向量、文本、元数据；`search` 暴力算分排序 | 向量数据库（无 ANN） |
| `SemanticSearchEngine` | 类 | 切块 → 在所有块上 fit → 逐块 embed 入库；查询时 embed + search | 检索流水线 |
| `compare_metrics` | 函数 | 同一查询下三种度量的 top-k | 度量比较 |
| `truncate_embedding` | 函数 | 取前 N 维并重新归一化 | Matryoshka 截断 |
| `SAMPLE_DOCUMENTS` | 常量 | 5 篇 Acme 公司文档（退款、产品、安全、API、SLA），91–102 词 | 示例语料 |
| `__main__` | 脚本 | STEP 1–8 + SUMMARY | — |

数据流：`SAMPLE_DOCUMENTS` → `chunk_text`（50 词 / 10 重叠，共 15 块）→ `SimpleEmbedder.fit`（词表 270）→ 每块 `embed` → `VectorIndex.add` → 查询文本 `embed` → `VectorIndex.search`（逐个算分、排序、取 top-k）→ 结果字典。

---

## 3. 逐段精讲

### 3.1 固定长度切块：`chunk_text`

```python
def chunk_text(text, chunk_size=200, overlap=50):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks
```

- 以"词"为单位（`split()` 按任意空白切），步长 `chunk_size - overlap`。50/10 时块起点为 0、40、80……
- 切片 `words[start:end]` 越界时自动截断，不会报错，所以最后一块可能很短。
- **重叠的目的**：一个句子恰好跨在两块边界时，至少有一块包含它的完整上下文。
- ⚠️ **`overlap >= chunk_size` 会死循环**：步长 ≤ 0，`start` 不前进（已用超时验证）。
- ⚠️ **冗余尾块**：循环只检查 `start < len(words)`，不检查"上一块是否已覆盖到末尾"。30 词、30/10 会产出第 2 块 `words[20:30]`，完全被第 1 块包含。本节 50/10 配置下每篇文档的第 3 块只有 11–22 词，且大部分是第 2 块的重复（第一篇的第 3 块只有 1 个新词）——这些短块正是 STEP 7 二值检索结果"全军覆没"的原因（见 3.7）。修复见测验 Q12。
- 讲义说的 "token" 在这里是"空格分词的词"；真实系统按 tokenizer 的 token 计数（1 个英文词约 1.3 个 token 量级）。

### 3.2 按句切块：`chunk_by_sentences`

```python
def chunk_by_sentences(text, max_chunk_tokens=200):
    sentences = text.replace("\n", " ").split(".")
    sentences = [s.strip() + "." for s in sentences if s.strip()]
    ...
    for sentence in sentences:
        sentence_length = len(sentence.split())
        if current_length + sentence_length > max_chunk_tokens and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_length = 0
        current_chunk.append(sentence)
        current_length += sentence_length
```

- 贪心装箱：一句一句往当前块里放，放不下就"封箱"开新块。`and current_chunk` 保证单句超长时也至少放进一个块（不会产生空块），但这意味着一个超长句子会单独成块且**超过上限**。
- ⚠️ **按 `.` 切句太粗糙**：实测 SLA 文档里 `99.9%` 被切成 `99.` 和 `9% uptime...`，`status.acme.com` 被切成 `status. acme. com`；`0.1%`、`TLS 1.3` 同理。生产中用 NLTK/spaCy 的句子切分器或正则处理小数、缩写、域名。
- ⚠️ **多余空格**：源文本每行前有 4 个空格缩进，`replace("\n", " ")` 后变成连续 5 个空格，运行输出 `5-7 business days     and returned` 就是这个原因；`" ".join(text.split())` 可以规整空白。
- ⚠️ 参数名是 `max_chunk_tokens`，实际计的是词数。
- 本文件的 `SemanticSearchEngine` **并没有使用**它，只在 STEP 1 中演示（讲义练习 5 要求替换后对比）。

### 3.3 `SimpleEmbedder`：TF-IDF + L2 归一化

```python
    def fit(self, documents):
        vocab_set = set()
        for doc in documents:
            vocab_set.update(doc.lower().split())
        self.vocab = sorted(vocab_set)
        self.word_to_idx = {w: i for i, w in enumerate(self.vocab)}
        n = len(documents)
        self.idf = np.zeros(len(self.vocab))
        for i, word in enumerate(self.vocab):
            doc_count = sum(1 for doc in documents if word in doc.lower().split())
            self.idf[i] = math.log((n + 1) / (doc_count + 1)) + 1

    def embed(self, text):
        words = text.lower().split()
        count = Counter(words)
        total = len(words) if words else 1
        vec = np.zeros(len(self.vocab))
        for word, freq in count.items():
            if word in self.word_to_idx:
                tf = freq / total
                vec[self.word_to_idx[word]] = tf * self.idf[self.word_to_idx[word]]
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec
```

- **维度 = 词表大小**：5 句小语料是 29 维，15 个块是 270 维。换语料就换维度——这与神经 embedding"维度固定"截然不同。
- **平滑 IDF**：`ln((n+1)/(df+1)) + 1`。分子分母加 1 防止 df = 0 时除零；末尾 +1 让出现在所有文档中的词仍有权重 1（不会变成 0）。与 scikit-learn `TfidfVectorizer(smooth_idf=True)` 公式一致。
- **TF**：`freq / total`；随后 L2 归一化会把这个公共缩放因子消掉，所以除以 `total` 其实**不影响**结果。
- **L2 归一化**：所有向量长度为 1，于是 cosine = dot，Euclidean 与 cosine 单调对应（3.4）。
- **未登录词（OOV）**：查询里不在词表中的词被直接忽略；若全部 OOV，向量为全 0。
- ⚠️ **稀疏而非稠密**：STEP 2 显示 29 维中每句只有 5–8 个非零维。讲义正文把 dense 定义为"every dimension carries information, unlike sparse representations (bag-of-words, TF-IDF)"，又把 `SimpleEmbedder` 称为"a simple dense embedding"，二者自相矛盾。代码的意义在于**接口相同**（"text in, fixed-size vector out"），而非表示能力相同。
- ⚠️ **分词不去标点**：`split()` 让 `policy.`、`customers?`、`x-ratelimit-limit,` 成为独立的词。查询"What is the refund policy for enterprise customers?"中 `policy`、`customers?` 都匹配不上；"How is customer data encrypted?"中只有 `is`、`customer`、`data` 命中（已实测）——最关键的 `encrypted?` 没有参与打分。
- ⚠️ **维度按字母序排列**：`sorted(vocab_set)` 让第 0 维是 `'$29'`，最后一维是 `'x-ratelimit-reset.'`。这对 TF-IDF 无所谓，但让 STEP 6 的"截断前 N 维"失去意义（3.6）。
- ⚠️ **`fit` 是 O(V·N·L)**：对每个词都重新 `split()` 每篇文档。一次遍历计算 df 的写法见测验 Q10。
- `embed_batch` 只是列表推导式包一层，真实 API 的批量调用能显著减少网络往返。

### 3.4 三种相似度与 Hamming

```python
def cosine_similarity(a, b):
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))

def euclidean_distance(a, b):
    return float(np.linalg.norm(a - b))

def hamming_distance(a, b):
    return int(np.sum(a != b))

def binarize(vec):
    return (vec > 0).astype(np.int8)
```

- **零向量保护**：查询全是 OOV 词时范数为 0，直接返回 0.0 而不是除零得到 NaN。
- **`float(...)`**：把 NumPy 标量转成 Python float，打印与 JSON 序列化更友好。
- **单位向量下的恒等式**：`‖a−b‖² = 2 − 2·cos(a, b)`。STEP 3 中 cos = 0.6075 → `√(2 − 1.215) = 0.8860`；cos = 0 → `√2 = 1.4142`。所以对本节所有向量，三种度量排序完全一致（STEP 5 验证了这一点）。讲义"When to use which"表格中三者的差别只在**未归一化**向量上才显现。
- **Hamming**：`a != b` 得到布尔数组，`np.sum` 数 True 的个数。
- ⚠️ **`binarize` 没有打包**：`int8` 每维 1 字节，270 维占 270 字节，不是打印出来的 34 字节。真正的 1 bit/维用 `np.packbits`。

### 3.5 `VectorIndex`：暴力检索

```python
    def search(self, query_vector, top_k=5, metric="cosine"):
        scores = []
        for i, vec in enumerate(self.vectors):
            if metric == "cosine":
                score = cosine_similarity(query_vector, vec)
            elif metric == "dot":
                score = dot_product(query_vector, vec)
            elif metric == "euclidean":
                score = -euclidean_distance(query_vector, vec)
            elif metric == "hamming":
                score = -hamming_distance(binarize(query_vector), binarize(vec))
            else:
                raise ValueError(f"Unknown metric: {metric}")
            scores.append((i, score))
        scores.sort(key=lambda x: x[1], reverse=True)
```

- **距离取负**：Euclidean 和 Hamming 越小越相似，取负号后统一成"分数越大越好"，就可以共用 `reverse=True` 排序。这也是为什么 STEP 5 中 EUCLIDEAN 的分数是 `-1.1093` 这样的负数。
- **三个平行列表**：`vectors`、`texts`、`metadata` 用同一个下标对齐，`index` 字段返回下标便于对比（STEP 7 就用它算重叠率）。
- `meta or {}`：没传元数据时存空字典，后续 `.get("source", "unknown")` 不会出错。
- **复杂度**：每次查询 O(n·d) 再加 O(n log n) 排序，在 Python 循环里逐个调用函数，很慢。向量化写法是把向量堆成矩阵 `M`，一次 `M @ q` 算出全部点积，再用 `np.argpartition` 取 top-k。生产中用 HNSW 等 ANN 索引（讲义 Vector Databases 一节）。
- **Hamming 每次重新二值化**库中所有向量；真实系统在入库时就存好二值码。

### 3.6 `SemanticSearchEngine` 与 STEP 6 的"Matryoshka 模拟"

```python
    def index_documents(self, documents, source_names=None):
        all_chunks = []
        all_sources = []
        for i, doc in enumerate(documents):
            chunks = chunk_text(doc, self.chunk_size, self.overlap)
            all_chunks.extend(chunks)
            name = source_names[i] if source_names else f"doc_{i}"
            all_sources.extend([name] * len(chunks))
        self.embedder.fit(all_chunks)
        for chunk, source in zip(all_chunks, all_sources):
            ...
```

- **先切块，再在全部块上 fit**：IDF 的"文档"是块而不是原文。每次调用都会重新 fit，词表随语料变化。
- **元数据 `source`**：`[name] * len(chunks)` 让每块都带上来源文件名，检索结果可以溯源——RAG 中引用出处就靠它。
- ⚠️ **不支持增量添加**：新文档进来必须重新 fit 全部，旧向量的维度也会变化。神经 embedding 没有这个问题（模型固定，向量空间固定）。
- `search_with_scores` 把文本截到 200 字符、分数四舍五入到 4 位，用于展示。

```python
def truncate_embedding(vec, dimensions):
    truncated = vec[:dimensions]
    norm = np.linalg.norm(truncated)
    if norm > 0:
        truncated = truncated / norm
    return truncated
```

- 截断后重新 L2 归一化，这一步本身是对的：手动截断 Matryoshka 向量后应重新归一化。
- ⚠️ **但在 TF-IDF 上做没有意义**：Matryoshka 的前提是"训练时让前 N 维承载最重要的信息"，而这里的维度是**按字母序排列的词**。STEP 6 中查询"refund policy enterprise"只有 `enterprise`、`refund` 两个非零维（`policy` 因标点未命中）：截到 135 维时 `refund` 被截掉（字母序靠后），cos 从 0.5004 降到 0.1718；截到 67 维时 `enterprise` 也被截掉，查询向量全 0，cos = 0。这是"按字母表丢词"，与讲义说的"3–5% accuracy loss"毫无可比性。更合理的模拟见测验 Q9（按 PCA 主成分排序）。
- 另外 `SAMPLE_DOCUMENTS[0][:200]` 按**字符**截取，正好在 "pro-rate" 中间切断。

### 3.7 STEP 7：二值量化为什么"失败"

```python
    query_vec = engine.embedder.embed("API rate limits")
    results_full = engine.index.search(query_vec, top_k=5, metric="cosine")
    results_binary = engine.index.search(query_vec, top_k=5, metric="hamming")
    ...
    storage_full = full_dim * 4
    storage_binary = math.ceil(full_dim / 8)
```

- 全精度 top-5 `[9, 10, 11, 0, 1]`，二值 top-5 `[2, 8, 5, 11, 14]`，重叠 1/5。
- **原因**：TF-IDF 向量全部 ≥ 0，`vec > 0` 只表示"这个词是否出现"。设查询有 q 个词、块有 k 个词、共有 m 个，则 Hamming = `q + k − 2m`。查询 3 个词；尾块 2 号只有 11 个不同词、与查询无交集，距离 14；真正相关的 9 号块有 43 个不同词、命中 3 个，距离 40（已实测）。于是**词数最少的块**排在最前：2、5、8、11、14 正是五篇文档的尾块。
- 神经 embedding 各维大致以 0 为中心，符号位携带方向信息，二值化后 Hamming 与夹角高度相关，讲义说召回损失约 5–10%。
- 讲义提到的"二值粗排 + 全精度重打分（rescore top-1000）"在代码里没有实现；本节数据上用 10 个候选重打分能把重叠提升到 3/5（测验 Q11）。
- ⚠️ 存储对比假设 float32（`* 4`），但向量实际是 NumPy 默认的 float64；`binarize` 返回的 int8 数组也没打包。打印的"32x"是理论值。

### 3.8 STEP 8：chunk 大小实验

```python
    for chunk_size in [20, 50, 100, 200]:
        eng = SemanticSearchEngine(chunk_size=chunk_size, overlap=max(5, chunk_size // 5))
        n = eng.index_documents(SAMPLE_DOCUMENTS)
        results = eng.search(test_query, top_k=3)
        top_score = results[0]["score"] if results else 0
```

- 每种配置新建引擎、重新 fit，重叠取 `chunk_size // 5`（至少 5）。
- 输出 top_score 为 0.3535、0.3419、0.4473、0.4654，top-1 都是退款文档开头。
- ⚠️ **分数不可横向比较**：每个配置的词表和 IDF 都不同（块数 35/15/10/5），而且块越大越容易包含查询词。要评估 chunk 大小，应固定 embedder，用带标注的查询集测 recall@k / MRR（测验 Q12）。
- SUMMARY 中列出的生产替代品"Voyage-3 (1024d, $0.06/1M tokens)"与讲义表格中的 voyage-4（$0.12）不一致，属于讲义与代码之间的信息不同步；以讲义为准且应以供应商官网的实时价格为准。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 TF-IDF 充当 embedding | 无需模型与 API，接口与真实 embedding 一致 | 稀疏、无语义泛化，同义句 cosine = 0；生产用 OpenAI / BGE / sentence-transformers |
| `split()` 分词 | 代码最短 | 标点粘连导致大量漏匹配；用正则或子词 tokenizer |
| 全部向量 L2 归一化 | cosine = dot，演示等价性 | 隐藏了度量之间在未归一化时的差别 |
| Python 循环暴力检索 | 逻辑直观 | O(n) 且慢；向量化矩阵乘或 HNSW 等 ANN |
| 三个平行列表存索引 | 简单 | 删除/更新困难；生产用向量数据库 |
| 切块后再 fit IDF | IDF 以块为单位，与检索粒度一致 | 新增文档需全量重建；神经 embedding 无此问题 |
| 距离取负统一排序 | 一个排序逻辑覆盖四种度量 | 分数含义不直观（负数） |
| 在 TF-IDF 上演示 Matryoshka / 二值化 | 无需真实模型 | 结果严重失真；应在神经 embedding 上做 |
| `binarize` 用 int8 不打包 | 易读 | 实际只省 8 倍（对 float64）；用 `np.packbits` |
| 每种 chunk 配置单独 fit | 实现简单 | 分数不可比；应固定 embedder + 标注评测 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `str.split()` 无参数 | `text.split()` | 按任意连续空白切分并丢弃空串 |
| `str.join` | `" ".join(words[start:end])` | 用空格把列表拼成字符串 |
| 切片越界安全 | `words[start:end]` 中 `end > len(words)` | 自动截到末尾，不报错 |
| 列表推导式 + 条件 | `[s.strip() + "." for s in sentences if s.strip()]` | 过滤空句并补回句号 |
| `set.update` | `vocab_set.update(doc.lower().split())` | 批量加入集合，自动去重 |
| `sorted` | `self.vocab = sorted(vocab_set)` | 返回排好序的新列表（这里按字母序） |
| 字典推导式 + `enumerate` | `{w: i for i, w in enumerate(self.vocab)}` | 建"词 → 下标"映射 |
| 生成器表达式求和 | `sum(1 for doc in documents if word in ...)` | 不建中间列表地计数 |
| `collections.Counter` | `Counter(words)`、`count.items()` | 统计词频的字典子类 |
| 条件表达式 | `total = len(words) if words else 1` | 防止除以 0 |
| `np.zeros` / `np.linalg.norm` | `np.zeros(len(self.vocab))`、`np.linalg.norm(vec)` | 全零向量（默认 float64）；L2 范数 |
| 向量除标量 | `vec / norm` | NumPy 广播，逐元素相除 |
| 布尔数组 | `(vec > 0).astype(np.int8)`、`np.sum(a != b)` | 比较得布尔数组；求和即计数 |
| `np.count_nonzero` | `np.count_nonzero(emb)` | 统计非零元素个数（STEP 2 用来展示稀疏性） |
| `or` 提供默认值 | `meta or {}` | `meta` 为 `None` 时用空字典 |
| `lambda` 作排序键 | `scores.sort(key=lambda x: x[1], reverse=True)` | 按元组第二项降序原地排序 |
| `raise ValueError` | `raise ValueError(f"Unknown metric: {metric}")` | 对非法参数快速失败 |
| 列表乘法 | `[name] * len(chunks)` | 生成重复元素的列表 |
| `zip` | `for chunk, source in zip(all_chunks, all_sources)` | 并行遍历两个列表 |
| `dict.get` | `r["metadata"].get("source", "unknown")` | 缺键时返回默认值 |
| 集合交集 | `set(full_ids) & set(binary_ids)` | 求两个 top-k 的重叠 |
| `math.ceil` / `math.log` | `math.ceil(full_dim / 8)`、`math.log(...)` | 向上取整；自然对数 |
| f-string 格式符 | `{cos:.4f}`、`{dims:>4d}`、`{frac*100:>5.1f}`、`{storage_full:,}`、`{h['score']:>8.4f}` | 小数位、右对齐宽度、千分位 |
| f-string 中的转义引号 | `print(f"    [{i}] \"{mini_docs[i][:40]}\" ...")` | 在双引号字符串里输出双引号 |
| 三引号多行字符串 | `SAMPLE_DOCUMENTS = ["""Acme Corp ..."""]` | 保留换行与缩进（也带来了多余空格） |
| `if __name__ == "__main__":` | 文件末尾的 STEP 1–8 | 直接运行时执行演示，被 import 时只提供函数和类 |

---

## 6. 运行结果解读

实际运行（Python 3.13 + NumPy 2.5，约 1 秒）。

**STEP 1 切块**：第一篇文档 91 词；30/10 固定切块得 5 块（起点 0、20、40、60、80）；按句切块（上限 30 词）也是 5 块。第 [2] 个句块中 `business days     and returned` 的多余空格来自源文本缩进。

**STEP 2 向量化（稀疏性）**：

```text
  Vocabulary size: 29
  Embedding dimensions: 29
    [0] "The cat sat on the mat" -> 5 non-zero dims     ← 6 个词，"the" 重复，5 个不同词
    [2] "Machine learning is a branch of artifici" -> 8 non-zero dims
```

29 维中只有 5–8 维非零——这是典型的稀疏表示。

**STEP 3 相似度**：

```text
  cat/mat vs dog/rug (similar):          Cosine 0.6075  Dot 0.6075  Euclidean 0.8860
  cat/mat vs ML (unrelated):             Cosine 0.0000  Dot 0.0000  Euclidean 1.4142
  payment declined vs charge didn't go through (same meaning):
                                         Cosine 0.0000  Dot 0.0000  Euclidean 1.4142   ← 关键
  ML vs payment declined (unrelated):    Cosine 0.0000  ...
```

- Cosine 与 Dot 完全相同：向量已归一化。Euclidean = `√(2 − 2cos)`。
- cat/dog 的 0.6075 全部来自共有的 `the`、`sat`、`on`，不是因为模型知道"猫和狗相近"。
- **同义句得 0**：代码注释写着"(same meaning)"，结果却和"无关"一模一样。这正是讲义开头说的 vocabulary mismatch——TF-IDF 解决不了，神经 embedding 才能解决。这是本节最值得记住的一行输出。

**STEP 4 检索**：15 块、词表 270。五个查询的 top-1 都来自正确的文档（refund-policy、api-docs、security、uptime-sla、product-overview），分数 0.27–0.49。这些查询与文档有大量字面重合，所以 TF-IDF 表现尚可。注意第 4 个查询的第 3 名来自 product-overview（0.0769），分数很低，说明除了第一名之外几乎没有可靠信号。

**STEP 5 度量对比**：三种度量 top-3 完全相同，EUCLIDEAN 分数为负（`-1.1093` 对应 cos `1 − 1.1093²/2 ≈ 0.3847`）。

**STEP 6 截断**：

```text
  dims= 270 (100.0%): cosine=0.5004
  dims= 135 ( 50.0%): cosine=0.1718     ← "refund" 被字母序截断丢掉
  dims=  67 ( 25.0%): cosine=0.0000     ← "enterprise" 也被丢掉，查询向量全 0
  dims=  27 ( 10.0%): cosine=0.0000
```

**STEP 7 二值量化**：

```text
  Full-precision top-5 indices: [9, 10, 11, 0, 1]
  Binary quant top-5 indices:   [2, 8, 5, 11, 14]    ← 全是各文档最短的尾块
  Overlap: 1/5 (20%)
    Float32: 1,080 bytes
    Binary:  34 bytes
    Ratio:   32x reduction                           ← 理论值；实际 int8 未打包为 270 字节
```

1080 / 34 ≈ 31.8，四舍五入显示 32。

**STEP 8 chunk 大小**：块数 35/15/10/5，top_score 0.3535/0.3419/0.4473/0.4654。分数随块变大而升高，但因每个配置的 IDF 不同、且大块天然更容易包含查询词，这个趋势**不能**解读为"大块更好"。

---

## 7. 动手改一改

1. **讲义练习 1（度量比较）**：先去掉 `embed` 中的 L2 归一化再跑 STEP 5，观察 dot 与 cosine 的排序何时出现分歧（提示：长块的未归一化向量模长更大，dot 会偏向长块）。
2. **修分词**：把 `split()` 换成 `re.findall(r"[a-z0-9]+(?:[-.][a-z0-9]+)*", text.lower())`，同时改写 `fit` 为一次遍历（测验 Q10），对比 5 个查询的命中词与分数。
3. **讲义练习 5**：让 `SemanticSearchEngine` 支持 `chunker="sentence"`，先修好按句切分对 `99.9%`、`status.acme.com` 的误切，再比较检索结果。
4. **讲义练习 4（二值量化）**：用 `np.packbits` 存二值码、XOR + popcount 算 Hamming，实现"粗排 top-N + cosine 重打分"，画出 N 从 5 到 15 时 top-5 重叠率的变化（测验 Q11）。
5. **讲义练习 3（Matryoshka）**：对 chunk 矩阵做 SVD，按主成分截断到 2/4/8/14 维，测 5 个查询的 top-3 重叠率，并与按字母序截断对比（测验 Q9）。
6. **换真实 embedding**：用 `sentence-transformers` 的 `BAAI/bge-small-en-v1.5`（讲义 Use It 中的例子）替换 `SimpleEmbedder`，保持 `VectorIndex` 不变，重跑 STEP 3：同义句"payment declined / charge did not go through"的 cosine 应明显高于无关句对。再把 `VectorIndex.search` 改成矩阵乘 + `np.argpartition` 的向量化版本。

---

## 8. 常见坑

- **把 TF-IDF 当作语义 embedding**：它只匹配字面，同义词正交；本节"同义句 cosine = 0"就是证据。
- **分词不处理标点和大小写**：`policy.` ≠ `policy`，查询中的关键词悄悄失配。
- **`overlap >= chunk_size`**：死循环。
- **冗余尾块**：重叠切块可能产生几乎全是重复内容的短块，既浪费存储又干扰检索。
- **跨配置比较相似度分数**：不同词表 / 不同模型 / 不同切块下的 cosine 不可比；用 recall@k 等排序指标。
- **在非零中心化的向量上做符号二值化**：TF-IDF 这类非负向量二值化后只剩"出现与否"，Hamming 距离被长度主导。
- **对无序维度做截断**：只有 Matryoshka 训练过的模型（或按方差排序的 PCA 分量）才能"截前 N 维"。
- **以为 `astype(np.int8)` 就是 1 bit**：每维仍占 1 字节；用 `np.packbits`。
- **忘了归一化就用 dot product**：未归一化时 dot 偏向模长大的向量（长文档）。
- **新增文档后不重新 fit**：本节 `SimpleEmbedder` 的词表和 IDF 是固定在 fit 时的，新词会被当作 OOV 忽略。
