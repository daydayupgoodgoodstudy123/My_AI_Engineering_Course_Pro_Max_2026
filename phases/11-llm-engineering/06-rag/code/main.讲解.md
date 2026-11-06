# 代码讲解 · main.py

> **所属小节**：阶段 11 · LLM 工程 · 第 06 节 RAG（检索增强生成） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅标准库 `math`、`collections.Counter`（不需要 NumPy、API key 或网络）。同目录 `main.ts` 是 TypeScript 移植版，本讲解只覆盖 Python 版。

---

## 1. 这份代码在考察什么

讲义的结论是"Every RAG system follows this pattern: Query → Retrieve → Augment prompt → Generate"。这份代码用**纯 Python 列表**把这四步完整走了一遍：

1. **切块**：`chunk_text`，固定词数 + 重叠。
2. **向量化**：`build_vocabulary` + `compute_tf` + `compute_idf` + `tfidf_embed`，即 TF-IDF。
3. **检索**：`cosine_similarity` + `search`，暴力计算 top-k（相当于 FAISS 的 flat index）。
4. **增强**：`build_rag_prompt`，把检索到的块编号后拼进"只根据上下文回答"的模板。
5. **生成（模拟）**：`simple_generate`，从检索块中抽取与问题重叠词最多的一句话。
6. **封装**：`RAGPipeline` 提供 `index`（离线）与 `query`（在线）两个入口。

> 一句话：**RAG 的骨架就是"离线切块建索引 + 在线检索拼 prompt"，模型本身不变**。代码把每一步都写成了几行可读的函数，生产系统只需替换 embedder（神经 embedding）、存储（向量数据库）和生成器（LLM API）。但正因为生成器是"词重叠抽句"，运行结果中有 2 个问题答错、1 个答案被截断——这些错误恰好展示了 RAG 中"检索对了不等于答对了"这一要点。

与第 04 节 `embeddings.py` 的区别：这里不用 NumPy、TF-IDF 不做 L2 归一化（cosine 本身会归一化，所以检索分数与第 04 节完全相同，如 0.3419、0.4373），多了 prompt 构造和生成环节。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `chunk_text` | 函数 | 按词数切块，相邻块重叠 | Fixed-size chunking |
| `build_vocabulary` | 函数 | 小写、按空格分词、去重、排序 | 词表（向量维度） |
| `compute_tf` | 函数 | 每个词表词在文本中的频率 / 总词数 | Term Frequency |
| `compute_idf` | 函数 | 平滑 IDF `ln((n+1)/(df+1)) + 1` | Inverse Document Frequency |
| `tfidf_embed` | 函数 | TF × IDF，得到长度 = 词表大小的列表 | "Embedding" |
| `cosine_similarity` | 函数 | 纯 Python 点积 / 范数 | 相似度 |
| `search` | 函数 | 对所有向量算 cosine，排序取 top-k | 向量检索（brute force） |
| `build_rag_prompt` | 函数 | 指令 + `[Source i]` 编号的上下文 + 问题 | Augment |
| `simple_generate` | 函数 | 从检索块中挑与问题重叠最多的句子 | Generate（模拟） |
| `RAGPipeline` | 类 | `index` 建词表/IDF/向量与来源；`query` 检索 + 拼 prompt + 生成 | 完整流水线 |
| `SAMPLE_DOCUMENTS` | 常量 | 5 篇 Acme 公司文档（与第 04 节相同） | 知识库 |
| `__main__` | 脚本 | STEP 1–6 + SUMMARY | — |

数据流：
- 离线：`SAMPLE_DOCUMENTS` → `chunk_text`（50/10 → 15 块）→ `build_vocabulary`（270 词）→ `compute_idf` → 每块 `tfidf_embed` → 保存 `chunks`、`sources`、`embeddings`。
- 在线：问题 → `tfidf_embed`（同一词表与 IDF）→ `search` top-k → `retrieved`（块、来源、分数、下标）→ `build_rag_prompt` → `simple_generate` → 返回 `{question, answer, prompt, retrieved}`。

---

## 3. 逐段精讲

### 3.1 切块

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

- 与讲义和第 04 节完全相同：步长 `chunk_size - overlap`，以空格分词的"词"为单位。
- STEP 1：91 词的退款文档按 30/10 切成 5 块（起点 0、20、40、60、80），最后一块只有 11 词。
- ⚠️ `overlap >= chunk_size` 会死循环；尾块可能几乎全是重复内容（第 04 节讲解与测验 Q12 有详细分析和修复）。
- ⚠️ **会切断句子**：50/10 切块下，产品文档的"The Enterprise plan includes everything in Professional plus custom integrations..."被切在 `in` 之后，前半句在 3 号块、后半句在 4 号块。测验 Q12 中改写后的问题"How much does the Enterprise plan cost?"因此只得到半句话。讲义推荐的 semantic / recursive chunking 正是为了避免这种情况。

### 3.2 TF-IDF 四件套

```python
def build_vocabulary(documents):
    vocab = set()
    for doc in documents:
        vocab.update(doc.lower().split())
    return sorted(vocab)

def compute_tf(text, vocab):
    words = text.lower().split()
    count = Counter(words)
    total = len(words)
    if total == 0:
        return [0.0] * len(vocab)
    return [count.get(word, 0) / total for word in vocab]

def compute_idf(documents, vocab):
    n = len(documents)
    idf = []
    for word in vocab:
        doc_count = sum(1 for doc in documents if word in doc.lower().split())
        idf.append(math.log((n + 1) / (doc_count + 1)) + 1)
    return idf

def tfidf_embed(text, vocab, idf):
    tf = compute_tf(text, vocab)
    return [t * i for t, i in zip(tf, idf)]
```

- **词表即维度**：`sorted(vocab)` 固定了第 i 维对应哪个词；STEP 2 三句话共 15 个词，15 维；15 个块共 270 维。
- **TF**：`count.get(word, 0) / total` 对词表中的每个词都算一遍，产生一个**稠密的 Python 列表**，其中绝大多数是 0（STEP 2 中 15 维里只有 5–8 个非零）。代码比讲义多了 `total == 0` 的保护，避免空文本除零。
- **平滑 IDF**：`n = 3` 时，只出现在 1 句中的词 `ln(4/2) + 1 = 1.693`，出现在 2 句中的 `the`、`sat`、`on` 为 `ln(4/3) + 1 = 1.288`。STEP 2 打印的前 8 个词全是 1.693（排序后的并列项），这是平滑 IDF 的典型输出。
- **未登录词**：查询里不在词表的词（包括带标点的 `customers?`、`enterprise?`）对向量没有任何贡献。
- ⚠️ `compute_idf` 对每个词遍历所有文档并重新 `split()`，复杂度 O(V·N·L)；一次遍历用 `Counter` 统计 df 即可（见第 04 节测验 Q10）。
- ⚠️ 不去标点、不去停用词：`policy.` ≠ `policy`，`is/the/of` 却能贡献相似度。测验 Q6：无关问题"What is the capital of France?"只靠这三个虚词就拿到 0.3901 的 top-1 分数，比真正的业内问题还高。

### 3.3 相似度与检索

```python
def cosine_similarity(a, b):
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def search(query_embedding, stored_embeddings, top_k=5):
    scores = []
    for i, emb in enumerate(stored_embeddings):
        sim = cosine_similarity(query_embedding, emb)
        scores.append((i, sim))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]
```

- `zip(a, b)` 逐维配对，生成器表达式求和——纯 Python 写出的点积与范数，便于理解公式 `dot(a,b)/(‖a‖·‖b‖)`。
- **零向量保护**：查询中没有一个词在词表里时（如 "What about enterprise?"），返回 0.0 而不是除零。
- **只返回下标和分数**：块文本、来源由调用方用下标去取，存储与检索解耦。
- `list.sort` 是稳定排序：分数相同时保持原顺序，所以全 0 分时总是返回前几个块（退款文档的前 3 块）。
- ⚠️ **没有相关性阈值**：无论分数多低，总是返回 top-k。全 0 分也会把 3 个块塞进 prompt（测验 Q10）。
- ⚠️ **性能**：每次查询 O(N·V) 次 Python 层面的乘加。讲义说 brute force "scales to maybe 100,000 vectors before getting slow"——那是针对 NumPy/FAISS 的向量化实现；纯 Python 列表会慢得多。生产用 ANN（HNSW）和向量数据库。

### 3.4 Prompt 构造：RAG 中的 "Augmented"

```python
def build_rag_prompt(query, retrieved_chunks):
    context = "\n\n---\n\n".join(
        f"[Source {i+1}]\n{chunk}"
        for i, chunk in enumerate(retrieved_chunks)
    )
    return (
        "Answer the question based ONLY on the following context.\n"
        "If the context doesn't contain enough information, "
        "say \"I don't have enough information to answer that.\"\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )
```

- **三段式结构**：指令（最前）→ 上下文（中间）→ 问题（最后）。问题放在末尾，符合上一节 lost-in-the-middle 的建议。
- **grounding + 拒答路径**："ONLY on the following context"限制知识来源，"say I don't have enough information"给模型一个不编造的出口。
- **编号与分隔符**：`[Source i]` + `---` 让模型能区分不同来源，也为"引用 [1]"做准备。
- ⚠️ 只有编号没有来源名。`RAGPipeline` 明明保存了 `self.sources`，却没有传进 prompt，LLM 无法引用"refund-policy.md"。讲义练习 3 与测验 Q11 给出了带来源的版本。
- 括号内相邻字符串字面量会自动拼接，其中两段是 f-string——这是写多行 prompt 的常用手法，比三引号字符串更好控制缩进。

### 3.5 模拟生成：`simple_generate`

```python
def simple_generate(prompt, retrieved_chunks):
    query_section = prompt.lower().split("question:")[-1]
    query_words = set(query_section.split())
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "what", "how",
                  "why", "when", "where", "do", "does", "for", "of", "in", "to",
                  "and", "or", "on", "at", "by", "it", "its", "this", "that"}
    query_words = query_words - stop_words

    best_sentence = ""
    best_score = 0

    for chunk in retrieved_chunks:
        for sentence in chunk.split("."):
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
            words = set(sentence.lower().split())
            overlap = len(query_words & words)
            if overlap > best_score:
                best_score = overlap
                best_sentence = sentence

    return best_sentence if best_sentence else "I don't have enough information."
```

- **思路**：一个"抽取式问答"的极简版——在检索到的块中，找与问题共有内容词最多的句子作为答案；一个都不重叠就拒答。
- 生成器有停用词表（检索阶段没有），所以它能对"capital of France"正确拒答。
- `len(sentence) < 10` 过滤掉"0"、"1%"之类的碎片。
- ⚠️ **从 prompt 反向解析问题**：`split("question:")[-1]` 拿到的是 `" what is ...?\n\nanswer:"`，`answer:` 也混进了查询词集合。更好的接口是直接传原始问题。
- ⚠️ **标点**：`customers?`、`encrypted?` 带问号，与句中的词不匹配。
- ⚠️ **按 `.` 分句**：`0.1%`、`TLS 1.3`、`status.acme.com`、`99.9%` 都会被切开，SLA 问题的答案因此停在"for each 0"。
- ⚠️ **平局取先**：`>` 让重叠数相同的句子中第一个胜出。退款问题中标题句"Acme Corp Refund Policy"与企业退款句都命中 2 个词，标题句先出现，于是答案是标题（测验 Q5）。
- ⚠️ **1 个词重叠就作答**："Does Acme support SAML?" 因为 `acme` 被答成"Acme Corp does not sell or share customer data with third parties"——有依据的样子、没有依据的内容。
- 改进版见测验 Q9；即使改进后，"support SAML"仍会被答成含 `support` 的定价句，说明词法方法无法判断"这句话是否真的回答了问题"，这正是需要真正的 LLM 和 faithfulness 评估的原因。

### 3.6 `RAGPipeline`：离线 `index` 与在线 `query`

```python
    def index(self, documents, source_names=None):
        all_chunks = []
        all_sources = []
        for i, doc in enumerate(documents):
            doc_chunks = chunk_text(doc, self.chunk_size, self.overlap)
            all_chunks.extend(doc_chunks)
            name = source_names[i] if source_names else f"doc_{i}"
            all_sources.extend([name] * len(doc_chunks))

        self.chunks = all_chunks
        self.sources = all_sources
        self.vocab = build_vocabulary(all_chunks)
        self.idf = compute_idf(all_chunks, self.vocab)
        self.embeddings = [tfidf_embed(chunk, self.vocab, self.idf) for chunk in all_chunks]
        return len(all_chunks)

    def query(self, question, top_k=None):
        k = top_k or self.top_k
        query_emb = tfidf_embed(question, self.vocab, self.idf)
        results = search(query_emb, self.embeddings, k)
        retrieved = []
        for idx, score in results:
            retrieved.append({"chunk": self.chunks[idx], "source": self.sources[idx],
                              "score": score, "index": idx})
        chunk_texts = [r["chunk"] for r in retrieved]
        prompt = build_rag_prompt(question, chunk_texts)
        answer = simple_generate(prompt, chunk_texts)
        return {"question": question, "answer": answer, "prompt": prompt, "retrieved": retrieved}
```

- **三个平行列表**：`chunks`、`sources`、`embeddings` 用同一下标对齐；`[name] * len(doc_chunks)` 给每块打上来源。
- **索引与查询共用 `self.vocab`、`self.idf`**：这对应生产中"索引和查询必须用同一个 embedding 模型"。
- `k = top_k or self.top_k`：调用时没传就用构造时的默认值。注意 `top_k=0` 也会被当成"没传"。
- 返回字典同时包含答案、完整 prompt 和检索明细，便于调试——生产中也应记录这些，用于排查"检索错还是生成错"。
- ⚠️ `index` 每次调用都**整体重建**，不支持增量添加或删除文档；词表变化后旧向量就不能复用。神经 embedding + 向量数据库可以逐条 upsert/delete。
- ⚠️ 没有元数据过滤（例如按权限、按文档类型），也没有重排序和查询改写（下一节 Advanced RAG）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| TF-IDF 充当 embedding | 讲义："makes the concept concrete" | 无同义词能力；生产用 text-embedding-3-small、BGE 等 |
| 纯 Python 列表、无 NumPy | 零依赖，公式一目了然 | 慢、占内存；用 NumPy/稀疏矩阵/向量数据库 |
| 暴力 cosine 检索 | 等价于 FAISS flat index，结果精确 | O(N) 不可扩展；用 HNSW 等 ANN |
| 无相关性阈值，总返回 top-k | 简单 | 无关问题也塞满上下文；加阈值 + 重排 + 拒答 |
| prompt 三段式 + 拒答指令 | 体现 grounding | 没有来源名，无法引用；加入元数据 |
| 抽取式"生成" | 不需要 API key | 平局、标点、分句问题导致答错；用 LLM（temperature 0） |
| 从 prompt 反解析问题 | 让 `simple_generate` 接口与真实 `generate(prompt)` 一致 | 混入 `answer:` 等噪声；生产中 LLM 直接读 prompt，无此问题 |
| `index` 全量重建 | 词表必须在全部块上统计 | 无法增量更新；神经 embedding 可逐条写入 |
| STEP 5 比较 top_score | 想展示 chunk 大小的影响 | 不同词表下分数不可比；用 recall@k 评测 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `while` 循环 + 手动步进 | `while start < len(words): ... start += chunk_size - overlap` | 步长由变量决定的循环 |
| `set.update` / `sorted` | `vocab.update(doc.lower().split())`、`return sorted(vocab)` | 批量加入集合；排序得到固定顺序的列表 |
| `collections.Counter` + `.get` | `count.get(word, 0)` | 词频统计；不存在的键返回默认值 0 |
| 列表乘法 | `[0.0] * len(vocab)`、`[name] * len(doc_chunks)` | 生成定长的重复列表 |
| 列表推导式 + `zip` | `[t * i for t, i in zip(tf, idf)]` | 两个列表逐元素相乘 |
| 生成器表达式求和 | `sum(x * y for x, y in zip(a, b))`、`sum(1 for doc in documents if ...)` | 点积、计数，无中间列表 |
| `math.log` / `math.sqrt` | `math.log((n + 1) / (doc_count + 1)) + 1` | 自然对数；平方根 |
| `enumerate` | `for i, emb in enumerate(stored_embeddings)` | 同时获得下标和元素 |
| `lambda` 排序键 | `scores.sort(key=lambda x: x[1], reverse=True)` | 按元组第二项降序（稳定排序） |
| 切片取前 k | `scores[:top_k]` | 超出长度也安全 |
| 生成器表达式传给 `join` | `"\n\n---\n\n".join(f"[Source {i+1}]\n{chunk}" for i, chunk in enumerate(...))` | 拼接多段文本 |
| 相邻字符串字面量拼接 | `("Answer the question ...\n" "If the context ..." f"Context:\n{context}\n\n")` | 括号内自动拼接，可混用 f-string |
| 字符串中的转义引号 | `"say \"I don't have enough information to answer that.\"\n\n"` | 双引号字符串里写双引号 |
| `str.split(sep)[-1]` | `prompt.lower().split("question:")[-1]` | 取最后一个分隔符之后的部分 |
| 集合差与交 | `query_words - stop_words`、`query_words & words` | 去停用词；求共同词 |
| 条件表达式 | `best_sentence if best_sentence else "I don't have enough information."` | 空串为假 |
| `or` 取默认值 | `k = top_k or self.top_k` | `None`（或 0）时用默认 |
| 类的实例属性 | `self.chunks = []`、`self.sources = []` | 在 `__init__` 中声明状态，`index` 填充 |
| 字典列表 | `retrieved.append({"chunk": ..., "source": ..., "score": ..., "index": idx})` | 结构化保存每条检索结果 |
| f-string 格式符 | `{word:20s}`、`{score:.3f}`、`{chunk_size:>3d}`、`{sim_12:.4f}` | 字符串宽度、小数位、右对齐整数 |
| `str.replace` | `r["chunk"][:80].replace("\n", " ")` | 预览时去掉换行 |
| `if __name__ == "__main__":` | 文件末尾的 STEP 1–6 | 直接运行时执行演示 |

---

## 6. 运行结果解读

实际运行（Python 3.13，纯标准库，约 0.08 秒）。

**STEP 1 切块**：91 词 → 5 块（30、30、30、30、11 词）。

**STEP 2 TF-IDF**：

```text
  Vocabulary size: 15
    a                    IDF=1.693        ← ln(4/2)+1，只在 1 句中出现
    ...（前 8 个都是 1.693）
  Non-zero entries in 'cat sat on mat': 5
  Non-zero entries in 'machine learning': 8
```

**STEP 3 相似度**：

```text
  'cat on mat' vs 'dog on rug':     0.6344  (similar structure)
  'cat on mat' vs 'machine learning': 0.0000  (unrelated)
```

0.6344 全部来自共有的 `the`、`sat`、`on`。第 04 节同一对句子是 0.6075：语料不同（5 句 vs 3 句），IDF 不同，分数就不同——又一次说明 TF-IDF 分数只在同一语料内有意义。

**STEP 4 完整流水线**（15 块、词表 270）：

| 问题 | 检索 top-1（来源 / 分数） | 生成的答案 | 是否正确 |
|------|------------------------|-----------|---------|
| refund policy for enterprise customers | refund-policy / 0.3419 | "Acme Corp Refund Policy" | 错：选中了标题句（平局取先） |
| API rate limits | api-docs / 0.4373 | "Rate limit headers are included in every response..." | 部分对：答了响应头，没答 100/1000/10000 次每分钟 |
| customer data encrypted | security / 0.3778 | "Customer data is stored in isolated tenants..." | 错：`encrypted?` 未匹配，应为 AES-256 那句 |
| uptime falls below the SLA | uptime-sla / 0.4912 | "...10% credit for each 0" | 被截断：`0.1%` 被当成句号 |
| Professional plan cost | product-overview / 0.2738 | "...for $99 per month per user" | 对 |

五个问题的检索 top-1 全部来自正确的文档，但生成环节只有 1 个完全正确。这是本节最重要的观察：**RAG 质量 = 检索质量 × 生成质量，两者要分开评估**。另外注意 SLA 问题的第 3 个检索块来自 product-overview，分数只有 0.0769——没有阈值，低分块也进入了 prompt。

**STEP 5 chunk 大小**：

```text
  chunk_size= 20:  35 chunks, top_score=0.3535, answer_len=23
  chunk_size= 50:  15 chunks, top_score=0.3419, answer_len=23
  chunk_size=100:  10 chunks, top_score=0.4473, answer_len=23
  chunk_size=200:   5 chunks, top_score=0.4654, answer_len=23
```

`answer_len=23` 就是 `len("Acme Corp Refund Policy")`：四种配置都答成了标题句。`top_score` 因每次重建词表/IDF 而不可比。更合理的比较方法是 recall@k（测验 Q11：50 词时 recall@3 = 1.0，20 词时只有 0.625）。

**STEP 6 Prompt 检查**：问题"What encryption does Acme use?"、k = 2，prompt 共 938 字符、15 行；开头是指令与 `Context:`、`[Source 1]`，结尾是 `Question: ...`、空行、`Answer:`。值得注意的是，这个问题检回的两个块（security 7 号块 0.1823、api-docs 9 号块 0.097）都**不包含** "encrypted at rest using AES-256" 那句——`encryption` 与 `encrypted` 词形不同。用 k = 3 时正确的块才排在第 3。

---

## 7. 动手改一改

1. **讲义练习 1**：把 `compute_tf` 换成二值词袋（出现为 1，否则为 0），比较 STEP 4 五个问题的检索 top-3。预期 TF-IDF 更好，因为它给 `refund`、`encrypted` 这类稀有词更高权重。
2. **修生成器**：按测验 Q9 实现 `generate_v2`（正则分词、极简词干、按"句号 + 空白 + 大写"分句、按覆盖率打分），让 `query` 直接把原始问题传给生成器；确认退款、加密两题答对、SLA 句不再截断。
3. **加阈值与拒答**：按测验 Q10 在检索前去停用词并设 `min_score=0.25`，统计 6 个业内问题与 3 个无关问题的作答/拒答情况；再试 0.15 和 0.35，观察误拒与误答的此消彼长。
4. **讲义练习 3 + 4**：把来源名写进 prompt；实现 `evaluate(rag, qa_pairs, k)`，在 chunk_size = 20/50/100/200 下计算 recall@k 和 MRR，并同时报告每次检索送入的总词数。
5. **讲义练习 5**：实现 `ConversationalRAG`，保存最近 3 轮问答；对 4 个词以内的追问做改写（先用规则，再写一个调用 LLM 的版本），测试"How much does the Professional plan cost?" → "What about enterprise?"。
6. **换真实组件**：用讲义 Use It 中的 OpenAI `embed` / `generate`（或本地 sentence-transformers + 任意 LLM）替换 TF-IDF 和 `simple_generate`，`RAGPipeline` 的其余代码不变；对比 STEP 4 的五个答案。

---

## 8. 常见坑

- **以为检索到正确文档就等于答对**：本节 5 题检索全对，生成只对 1 题。检索与生成必须分别评估。
- **没有相关性阈值**：无关问题照样返回 top-k，分数还可能比正常问题高（虚词导致）。
- **标点不处理**：`customers?`、`enterprise?` 使关键词失配，追问"What about enterprise?"的检索分数全为 0。
- **按 `.` 分句**：小数、版本号、域名都会被切开。
- **固定长度切块切断句子**：答案的前后半句落在不同块里，只检回其中一块就只能给出半句话。
- **把追问直接拿去检索**：多轮对话中要先把追问改写成独立问题。
- **prompt 里没有来源名**：模型无法引用，用户也无法核实。
- **用 top-1 分数比较不同切块 / 不同语料**：TF-IDF 分数依赖词表和 IDF，跨配置不可比。
- **索引与查询用不同的 embedding**：本节体现为必须复用 `self.vocab`、`self.idf`；换模型必须重建索引。
- **文档更新后忘了重建索引**：`index` 是全量重建，新文档不会自动进入检索范围。
