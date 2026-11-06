# 代码讲解 · main.py

> **所属小节**：阶段 11 · LLM 工程 · 第 07 节 Advanced RAG（Chunking、重排序、混合检索） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`collections.Counter`），无需网络、无需 API key、无需 GPU

---

## 1. 这份代码在考察什么

这份代码用纯 Python 从零搭了一条"进阶 RAG"检索链路，并在 6 篇虚构的 Acme 公司文档（退款、产品、安全、API、财报、可用性）上逐步演示：

1. **两种检索器**：TF-IDF 余弦相似度（充当"向量检索"）与 BM25 关键词检索。
2. **Hybrid search**：用 Reciprocal Rank Fusion（RRF）把两路排名合并。
3. **Reranking**：对融合后的候选再打一次分（这里用词重叠启发式代替 cross-encoder）。
4. **Query transformation**：用模板模拟 HyDE（先写"假想答案"，再拿它去检索）。
5. **Parent-child chunking**：小块检索、大块入 prompt。
6. **评估**：词重叠版 faithfulness 检查，以及（定义了但未在 `__main__` 中调用的）Recall@k。

> 一句话：**把讲义里"BM25 + 向量 → RRF → rerank → prompt"的整条流水线拆成十几个可读的小函数**。同时也要看清：它的 TF-IDF、模板 HyDE、启发式 reranker 和词重叠 faithfulness 都是"玩具版"，演示输出里有好几处恰好暴露了这些简化的局限——这些正是面试追问的素材。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `chunk_text` | 函数 | 按词数滑窗切块（带 overlap） | Chunking |
| `build_vocabulary` / `compute_tf` / `compute_idf` / `tfidf_embed` | 函数 | 构造词表、算 TF、平滑 IDF，得到稠密的 TF-IDF 向量 | 用 TF-IDF 代替神经 embedding |
| `cosine_similarity` / `vector_search` | 函数 | 余弦相似度 + 全量暴力排序取 top-k | 向量检索（bi-encoder 思路） |
| `BM25` | 类 | `index` 统计文档频率与长度，`score` 按 BM25 公式打分，`search` 排序 | 关键词检索 |
| `reciprocal_rank_fusion` | 函数 | `Σ 1/(k + rank + 1)` 合并多路排名 | RRF |
| `hybrid_search` | 函数 | 两路各取 15 个 → RRF → 取 top-k | Hybrid search |
| `rerank` | 函数 | 词重叠 + bigram + 位置加成 + 初始分 × 5 | Reranking（启发式） |
| `hyde_generate_hypothesis` / `hyde_search` | 函数 | 按问句类型套模板生成"假想答案"，再检索 | HyDE |
| `create_parent_child_chunks` | 函数 | 切父块，再把每个父块切成子块，记录 `child_to_parent` | Parent-child chunking |
| `evaluate_faithfulness` | 函数 | 每句内容词在上下文中出现比例 ≥ 0.5 即判为有依据 | Faithfulness |
| `evaluate_retrieval_recall` | 函数 | 计算平均 Recall@k（本文件未调用） | Recall@k |
| `build_rag_prompt` | 函数 | 拼出带 `[Source i]` 的 RAG prompt（本文件未调用） | Prompt 构造 |
| `SAMPLE_DOCUMENTS` | 常量 | 6 篇示例文档（91/92/91/95/84/102 个词） | 语料 |
| `if __name__ == "__main__":` | 主程序 | Step 1–8 逐步演示并打印 | — |

数据流：`SAMPLE_DOCUMENTS` → `chunk_text(50, 10)` 得到 18 个 chunk → 同时建 BM25 索引与 TF-IDF 向量 → 单路检索（Step 1–2）→ RRF 融合（Step 3）→ hybrid + rerank（Step 4）→ HyDE（Step 5）→ parent-child（Step 6，另行切块）→ faithfulness（Step 7）→ 四种方法命中对比（Step 8）。

---

## 3. 逐段精讲

### 3.1 切块：`chunk_text`

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

- 以**词**为单位（不是 token），窗口每次前移 `chunk_size − overlap` 个词。主程序用 `chunk_size=50, overlap=10`，步长 40。
- `text.split()` 不带参数时按任意空白切分，所以文档里的换行和缩进都被吞掉了。
- 6 篇文档各切出 3 块，共 **18 个 chunk**，每篇的块长分别是 `[50, 50, 11]`、`[50, 50, 12]`、`[50, 50, 11]`、`[50, 50, 15]`、`[50, 44, 4]`、`[50, 50, 22]`。
- ⚠️ **尾块冗余**：循环条件只看 `start < len(words)`。earnings 文档 84 个词时，区间是 `[0:50]`、`[40:90]`、`[80:84]`，第三块 `"with continued margin expansion."` 完全被第二块包含，没有任何新信息，却仍占一个索引位（它就是 Step 1 中分数为 0 的 chunk 14）。修复：生成当前块后若 `end >= len(words)` 就 `break`；更进一步可以把过短的尾块并进前一块。
- ⚠️ 切块是按文档分别做的（主程序里逐篇调用），所以这里的 chunk 不会跨文档；Step 6 的 parent-child 则不同，见 3.8。

### 3.2 TF-IDF "向量"：`build_vocabulary` → `tfidf_embed`

```python
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

- 词表是 18 个 chunk 中出现过的全部小写词，共 **317** 个；每个 chunk 和查询都被表示成一个 317 维的稠密列表。
- TF = 词频 / 总词数；IDF 用平滑公式 `ln((n+1)/(df+1)) + 1`（与 scikit-learn 的 `smooth_idf=True` 相同），保证 IDF ≥ 1，**停用词也有不小的权重**：例如 `the` 出现在 10 个 chunk 中，IDF = 1.547；`revenue` 出现在 2 个 chunk 中，IDF = 2.846。
- 词表外的查询词被直接忽略（`compute_tf` 只遍历 `vocab`）。这是 Step 5 HyDE 演示失败的根源：`"How much money did the company make?"` 里只有 `the` 在词表中。
- ⚠️ 只用 `lower().split()` 分词，没去标点：`policy.`、`revenue.`、`quarter?` 都被当成独立的"词"。
- ⚠️ `compute_idf` 对每个词都把所有文档重新 `split()` 一遍，复杂度 O(|V| × N × L)；生产中应先建倒排表。
- 这一段的定位是"用最简单的向量表示演示 bi-encoder 检索的流程"——查询和文档**分别**向量化、可以预先算好、靠向量相似度比较。真实系统会换成神经 embedding（见第 04、06 节）。

### 3.3 余弦相似度与暴力检索

```python
def cosine_similarity(a, b):
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def vector_search(query_embedding, stored_embeddings, top_k=5):
    scores = []
    for i, emb in enumerate(stored_embeddings):
        sim = cosine_similarity(query_embedding, emb)
        scores.append((i, sim))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]
```

- 对每个 chunk 都算一次余弦相似度再全排序，O(N·|V|)。讲义提到的"200 万 chunk + ANN 近似误差"在这里不存在——这是精确搜索。
- 零向量（查询没有任何词在词表中）时返回 0，避免除零。
- `list.sort` 是**稳定排序**：分数相同的项保持原下标顺序。这一点在 Step 3 的 RRF 中会产生副作用（见 3.5）。
- 返回值统一是 `[(doc_id, score), ...]`，BM25 也用同样的格式，RRF 才能把它们一视同仁地处理。

### 3.4 BM25

```python
    def score(self, query, doc_idx):
        query_words = query.lower().split()
        doc_words = self.docs[doc_idx].lower().split()
        doc_len = self.doc_lengths[doc_idx]
        word_counts = Counter(doc_words)
        total = 0.0

        for term in query_words:
            if term not in word_counts:
                continue
            tf = word_counts[term]
            df = self.doc_freqs.get(term, 0)
            idf = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_dl)
            total += idf * numerator / denominator

        return total
```

- `index` 阶段只做两件事：记录每个文档长度（`doc_lengths`，平均 `avg_dl ≈ 37.17`）和每个词的文档频率（`doc_freqs`，用 `set(words)` 保证一篇文档只计一次）。
- `score` 逐项实现讲义公式：
  - IDF 用 Lucene 的变体 `ln((N − df + 0.5)/(df + 0.5) + 1)`，加 1 保证非负（经典 Robertson 版在 df > N/2 时会变成负数）。N = 18、df = 2 时 IDF = `ln(7.6) = 2.028`。
  - 词频项 `tf·(k1+1)/(tf + k1·norm)`：tf 越大越接近上限 `k1 + 1 = 2.2`。在平均长度的文档上，tf = 1、3、10、50 时分别是 1.0、1.571、1.964、2.148——"出现 50 次并不比 1 次相关 50 倍"。
  - 长度归一化 `norm = 1 − b + b·|d|/avgdl`：文档长度是平均值 2 倍时，tf = 1 的贡献从 1.0 降到 0.710；一半长度时升到 1.257。
- 查询里重复出现的词会被重复累加（`for term in query_words` 不去重），这和部分实现一致，但值得注意。
- ⚠️ 每次 `score` 都重新 `split()` 并 `Counter` 整篇文档，`search` 又对每个文档调用一次——O(N·L)。生产中 BM25 依赖倒排索引，只遍历包含查询词的文档。
- ⚠️ 不去停用词、不去标点。Step 1 中这直接导致**排错第一名**：查询 `"What was revenue last quarter?"` 中，`was` 和 `revenue` 的 IDF 一样（都只在 2 个 chunk 中出现），chunk 13 因为有 3 个 `was` 拿到 3.066 分，总分 4.953，超过了真正含 `$47.2 million` 的 chunk 12（3.554）。`quarter?` 带问号，永远匹配不上。

### 3.5 Reciprocal Rank Fusion

```python
def reciprocal_rank_fusion(ranked_lists, k=60):
    scores = {}
    for ranked_list in ranked_lists:
        for rank, (doc_id, _) in enumerate(ranked_list):
            if doc_id not in scores:
                scores[doc_id] = 0.0
            scores[doc_id] += 1.0 / (k + rank + 1)
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return fused
```

- `enumerate` 从 0 开始，所以用 `rank + 1` 转成 1-based 名次，与讲义公式 `1/(k + rank)` 一致。
- `(doc_id, _)`：解包时用 `_` 丢掉原始分数——RRF **只看名次**，这是它不怕两路分数量纲不同的原因。
- 两路都第 1：`2/61 = 0.0328`；两路都第 2：`2/62 = 0.0323`；讲义例子 `1/61 + 1/65 = 0.0318`、`1/63 + 1/62 = 0.0320` 都可以用这个函数复现。
- ⚠️ **零分结果也参与融合**：对 `"What was revenue last quarter?"`，两路中只有 2 个 earnings chunk 得分大于 0，其余 16 个都是 0。由于稳定排序，refund 的 chunk 0、1、2 在两路里同样排第 3、4、5，于是以 `0.0317、0.0312、0.0308` 进入融合结果，和真正的答案（0.0323）几乎并列。修复：融合前过滤 `score > 0`（或低于相似度阈值）的结果，修复后只剩 2 个 earnings chunk（见测验 Q9）。

### 3.6 Hybrid search 与启发式 rerank

```python
def hybrid_search(query, chunks, vector_embeddings, vocab, idf, bm25_index, top_k=5, retrieval_pool=15):
    query_emb = tfidf_embed(query, vocab, idf)
    vec_results = vector_search(query_emb, vector_embeddings, top_k=retrieval_pool)
    bm25_results = bm25_index.search(query, top_k=retrieval_pool)
    fused = reciprocal_rank_fusion([vec_results, bm25_results])
    return fused[:top_k]
```

- 两路各取 `retrieval_pool = 15` 个候选（语料一共只有 18 个 chunk，几乎是全量），融合后截取 `top_k`。
- `chunks` 参数在函数体内没被用到——保留它只是为了与讲义签名对齐。
- 与讲义的差异：讲义版写的是 `search(...)`（文中并没有这个函数，应为 `vector_search`），候选池是 `top_k * 3`，并把 `fusion_k` 传给 RRF；代码改成了固定的 `retrieval_pool=15`，RRF 固定用默认 k = 60。

```python
        term_overlap = len(query_terms & chunk_words)
        # ...
        bigram_matches = sum(1 for bg in query_bigrams if bg in chunk)
        # ...
        for term in query_terms:
            pos = chunk.find(term)
            if pos != -1 and pos < len(chunk) // 3:
                position_boost += 0.5

        rerank_score = (
            term_overlap * 1.0
            + bigram_matches * 2.0
            + position_boost
            + initial_score * 5.0
        )
```

四个信号：

| 信号 | 计算 | 权重 | 备注 |
|------|------|------|------|
| `term_overlap` | 去停用词后的查询词集合 ∩ chunk 词集合（整词） | 1.0 | 带标点的词（`policy.`）匹配不上 |
| `bigram_matches` | 相邻查询词组成的 bigram 是否作为**子串**出现 | 2.0 | `"refund policy"` 能匹配 `"refund policy."` |
| `position_boost` | 查询词首次出现位置在前 1/3 | 每词 0.5 | `find` 也是子串匹配 |
| `initial_score` | 上一阶段的 RRF 分数 | 5.0 | RRF 分数约 0.03，× 5 只有约 0.16 |

以 Step 4 的查询 `"enterprise refund policy"` 为例（已逐项核对）：

- chunk 0：overlap 2（enterprise、refund）+ bigram 2.0（"refund policy"）+ 位置 1.0（refund 在第 10 个字符、policy 在第 17 个；enterprise 在第 112 个字符，刚好超过 327 // 3 = 109）+ 0.0328 × 5 = **5.164**；
- chunk 1：overlap 1 + 位置 0.5 + 0.0323 × 5 = **1.661**。

要点：

- ⚠️ `initial_score * 5.0` 原本想保留第一阶段的信号，但 RRF 分数只有 0.03 量级，乘 5 后只有约 0.16，几乎被词重叠淹没。这说明**融合不同量纲的分数需要归一化**——恰好是讲义推荐 RRF 的理由。
- ⚠️ Step 8 中 `"How is customer data encrypted?"` 的 rerank 第 1 名从 chunk 6（含 "encrypted at rest using AES-256"）变成了 chunk 7（数据驻留区域），因为 `encrypted?` 带问号匹配不上，而 `customer`、`data` 在 chunk 7 里位置更靠前。由于 Step 8 按**文档来源**判 HIT，这次退化被掩盖了。
- ⚠️ SUMMARY 中打印 "Reranking scores candidates more carefully with cross-attention"，但这里没有任何模型和 attention；真实做法见讲义 "Use It" 部分的 `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")` 或 Cohere rerank。

### 3.7 模板版 HyDE

```python
def hyde_generate_hypothesis(query):
    templates = {
        "what": "The answer to '{query}' is as follows: Based on our documentation, {topic} involves specific policies and procedures that define the process and requirements.",
        "how": "To address '{query}': The process involves several steps. First, you need to initiate the request for {topic}. Then, the system processes it according to the defined rules and policies.",
        "default": "Regarding '{query}': Our records indicate specific details and policies related to {topic} that provide a comprehensive answer to this question."
    }
    # ... 按 what / how / 其他 选模板
    topic_words = [w.strip("?.,!") for w in query.lower().split() if w.strip("?.,!") not in filler]
    topic = " ".join(topic_words) if topic_words else "this topic"
    return template.format(query=query, topic=topic)
```

- 用问句开头选模板，把去掉虚词的查询词作为 `{topic}` 填进去；`str.format` 用命名占位符。
- 与讲义版的差异：代码中 `how` 和 `default` 模板也插入了 `{topic}`，并用 `strip("?.,!")` 去掉标点、扩充了 `filler`；`hyde_search` 去掉了讲义签名中没用到的 `chunks` 参数。
- ⚠️ **它没有引入任何新词汇**。真正的 HyDE 依赖 LLM 写出"像真实文档一样的答案"（会自然用到 revenue、earnings、$ million 之类的词）；模板只会把查询词原样放回，再加上 `process / request / policies / rules` 等套话。Step 5 的结果因此是：
  - 直接检索 top-3：refund 0.3069、api 0.2203、uptime 0.2129（完全由停用词 `the` 决定）；
  - HyDE top-3：refund 0.3052、uptime 0.2189、api 0.1936（套话把结果推向 refund / api）。
  - 两者都没找到 earnings。讲义注释说 "HyDE bridges the vocabulary gap"，本次运行并没有证明这一点（见测验 Q12）。
- 对比：同样的模板用在 `"What was Q3 revenue?"` 上，HyDE top-2 是两个 earnings chunk——因为查询本身就含 `q3`、`revenue`，并不是 HyDE 的功劳。

### 3.8 Parent-child chunking

```python
def create_parent_child_chunks(text, parent_size=200, child_size=50):
    words = text.split()
    parents, children, child_to_parent = [], [], {}
    parent_idx = 0
    start = 0
    while start < len(words):
        parent_end = min(start + parent_size, len(words))
        parents.append(" ".join(words[start:parent_end]))

        child_start = start
        while child_start < parent_end:
            child_end = min(child_start + child_size, parent_end)
            child_idx = len(children)
            children.append(" ".join(words[child_start:child_end]))
            child_to_parent[child_idx] = parent_idx
            child_start += child_size

        parent_idx += 1
        start += parent_size
    return parents, children, child_to_parent
```

（为节省篇幅，上面合并了几行初始化，逻辑与源码一致。）

- 父块之间**没有 overlap**；子块只在父块内部切，`min(..., parent_end)` 保证子块不越过父块边界。
- `child_to_parent` 是"子块下标 → 父块下标"的字典，检索命中子块后据此找父块。
- 主程序中 `parent_size=100, child_size=25`：555 个词 → 6 个父块（最后一个只有 55 个词）、23 个子块，平均 3.8 个子块 / 父块。
- 子块单独建了一套词表和 IDF（`child_vocab`、`child_idf`），与主索引互不影响。
- ⚠️ **跨文档切块**：`full_text = " ".join(SAMPLE_DOCUMENTS)` 把 6 篇文档拼在一起再切，refund 文档只有 91 个词，所以 `parents[0]` 结尾混进了 `"Acme Corp Product Overview. Acme Corp offers three product"`。正确做法是逐文档切，并给每块保存来源元数据。
- ⚠️ **父块未去重**：Step 6 中 3 个命中子块都映射到 `Parent #0`，如果直接拼进 prompt 会重复 3 次。
- ⚠️ 查询 `"enterprise refund 60 days"` 中的 `60` 不在词表里（文档写的是 `60-day`），所以真正含 "60-day refund window" 的 Child #1 只排第 2，排第 1 的是含 `30 days` 的 Child #0。
- ⚠️ 打印语句中的 `"(100 words each)"`、`"(25 words each)"` 是写死的，并不总是成立。

### 3.9 Faithfulness 与 Recall@k

```python
def evaluate_faithfulness(answer, retrieved_chunks):
    answer_sentences = [s.strip() for s in answer.split(".") if len(s.strip()) > 10]
    # ...
    context = " ".join(retrieved_chunks).lower()
    for sentence in answer_sentences:
        words = set(sentence.lower().split())
        content_words = words - stop_words
        # ...
        matched = sum(1 for w in content_words if w in context)
        ratio = matched / len(content_words) if content_words else 0
        if ratio >= 0.5:
            grounded += 1
        else:
            ungrounded.append(sentence)
```

- 按句号切句，丢掉 10 个字符以内的碎片；每句去停用词后，看内容词在上下文中出现的比例，≥ 0.5 即算"有依据"。
- ⚠️ `w in context` 中 `context` 是字符串，所以是**子串匹配**：`rate` 会命中 `pro-rated`；按 `.` 切句也会把 `$47.2`、`5.5` 这类小数切断。
- ⚠️ **抓不住"改数字、改语义"的幻觉**：坏答案第一句 `90-day` 只占 6 个内容词中的 1 个，ratio = 0.83；第二句 `instantly` 占 3 个中的 1 个，ratio = 0.67；只有 `$50 processing fee` 一句全未命中。于是得分 0.67，而实际上三句全错。补救思路：对数字、实体单独核对（测验 Q10 给出了实现），或用 NLI / LLM-as-judge 逐条核验 claim（第 10 节）。
- Step 7 的上下文来自 `hybrid_search("enterprise refund", top_k=3)`，实际是 2 个 refund chunk + 1 个 api chunk；打印的 `"3 chunks about refund policy"` 也是写死的。
- `evaluate_retrieval_recall(queries_with_relevant, retrieval_fn, k)`：对每个问题，`hits / len(relevant_set)` 即 Recall@k，最后取平均；`retrieval_fn` 是"传入函数"的设计，可以把 `vector_search`、BM25、hybrid 包一层统一评测（讲义练习 5）。本文件的 `__main__` 没有调用它。
- `build_rag_prompt` 同样未被调用：它把检索结果编号成 `[Source 1]`、`[Source 2]`，用 `---` 分隔，并要求"只依据上下文回答，不够就说不知道"。

### 3.10 主程序 Step 8：四种方法对比

```python
        vec_top = vector_search(query_emb, embeddings, top_k=1)[0]
        vec_hit = "HIT" if chunk_sources[vec_top[0]] == expected_source else "miss"
        # BM25 / hybrid / rerank 同理
```

- 对 5 个问题分别取四种方法的第 1 名，按**来源文档**判 HIT/miss。
- 实际结果是 **20 格全部 HIT**，这个对比没有区分度：讲义练习 1 预期"hybrid 至少赢 3/5"，在这份语料上无法观察到。
- ⚠️ 按文档而不是按 chunk 判定会掩盖错误：`"What was Q3 revenue?"` 四种方法的第 1 名都是**不含答案数字**的 chunk 13，`"How is customer data encrypted?"` 的 rerank 第 1 名是不含加密信息的 chunk 7，但都显示为 HIT。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| TF-IDF 充当"向量检索" | 零依赖，能看清 bi-encoder 的流程 | 不懂同义词，停用词权重不低；生产用神经 embedding + ANN 索引 |
| 纯 Python 暴力 BM25 | 公式逐项可见 | 每次查询 O(N·L)；生产用倒排索引（Elasticsearch、OpenSearch、Tantivy 或向量库内置 BM25） |
| 只用 `lower().split()` 分词 | 简单 | 标点粘在词上（`quarter?`、`policy.`）、停用词主导打分；应做标点清洗、停用词、词干化 |
| RRF 固定 k = 60、不过滤零分 | 与讲义一致、无需调参 | 零分结果也拿到名次分；融合前应按分数阈值过滤 |
| 启发式 reranker | 不需要模型 | 不是 cross-encoder，初始分权重几乎无效；生产用 cross-encoder 或托管 rerank API |
| 模板 HyDE | 不需要 LLM | 不引入新词汇，起不到 HyDE 的作用；生产用 LLM 生成假想答案，并与原查询结果融合 |
| 父块在拼接全文上切 | 代码短 | 父块跨文档、未去重；应逐文档切并保存元数据 |
| 词重叠 faithfulness | 可解释、零成本 | 抓不住数字和语义篡改；用 NLI 或 LLM-as-judge 逐 claim 核对 |
| 按来源文档判 HIT | 便于展示 | 掩盖 chunk 级别的错误；应按 chunk ID 计算 Recall@k / MRR |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `collections.Counter` | `Counter(doc_words)`、`word_counts[term]` | 统计每个元素出现次数，像字典一样取值 |
| `dict.get(key, default)` | `self.doc_freqs.get(word, 0) + 1` | 键不存在时返回默认值，常用于计数 |
| 集合运算 | `query_words - stop_words`、`query_terms & chunk_words` | 差集、交集；`set()` 去重 |
| 列表推导式 | `[t * i for t, i in zip(tf, idf)]` | 一行生成新列表 |
| 生成器表达式 | `sum(1 for doc in documents if word in doc.lower().split())` | 不建中间列表，直接求和计数 |
| `zip` | `zip(a, b)`、`zip(tf, idf)` | 并行遍历两个序列 |
| `enumerate` + 嵌套解包 | `for rank, (idx, score) in enumerate(vec_results[:3])` | 同时拿到序号和元组里的两个字段 |
| `_` 占位变量 | `for rank, (doc_id, _) in enumerate(ranked_list)` | 表示"这个值不用" |
| `lambda` 作为排序键 | `scores.sort(key=lambda x: x[1], reverse=True)` | 按元组第 2 项降序；`sort` 是稳定排序 |
| `sorted(dict.items())` | `sorted(scores.items(), key=lambda x: x[1], reverse=True)` | 把字典变成 `(键, 值)` 列表后排序 |
| 条件表达式 | `"HIT" if ... else "miss"`、`... if self.n_docs else 1` | 一行写 if/else，也用于防止除零 |
| 类与实例属性 | `class BM25: def __init__(self, k1=1.2, b=0.75)` | 用 `self.xxx` 保存索引状态 |
| 字符串方法 | `lower()`、`split()`、`strip("?.,!")`、`find(term)`、`replace("\n", " ")`、`" ".join(...)` | `find` 找不到返回 -1；`strip` 去掉两端指定字符 |
| `str.format` 命名占位 | `template.format(query=query, topic=topic)` | 用 `{query}`、`{topic}` 填值 |
| f-string 格式符 | `{score:.4f}`、`{query:<45s}`、`{vec_hit:>8s}`、`{len(children)/len(parents):.1f}` | 小数位数、左/右对齐与宽度；花括号内可写表达式 |
| 整除 | `len(chunk) // 3` | 结果向下取整 |
| 字符串乘法 | `"=" * 65` | 重复字符串画分隔线 |
| 三引号字符串 | `SAMPLE_DOCUMENTS = ["""Acme Corp ..."""]` | 多行文本，保留换行和缩进 |
| 括号内隐式拼接 | `build_rag_prompt` 中多行字符串字面量相邻书写 | 相邻字符串字面量会自动拼接 |
| 函数作为参数 | `evaluate_retrieval_recall(..., retrieval_fn, k=5)` | 把检索函数当参数传入，便于统一评测 |
| 返回多个值 | `return parents, children, child_to_parent`、`return results, hypothesis` | 实际返回一个元组，调用方解包 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行演示，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 0.05 秒，结果确定、无随机性），节选：

```text
STEP 1: BM25 Keyword Search
  Query: What was revenue last quarter?
    #1 [earnings] score=4.9526 | to 14,200 from 11,800 in Q3 2024. ...      ← 不含 $47.2M，靠 3 个 "was" 胜出
    #2 [earnings] score=3.5542 | Acme Corp Q3 2025 Earnings Report. ...     ← 真正的答案
    #3 [refund] score=0.0000 | ...                                         ← 0 分也被返回

STEP 2: Vector Search vs BM25        ← 5 个查询全部 AGREE

STEP 3: Reciprocal Rank Fusion (Hybrid Search)
    #1 [earnings] rrf=0.0328         ← 2/61
    #2 [earnings] rrf=0.0323         ← 2/62
    #3 [refund] rrf=0.0317           ← 2/63，两路都是"0 分第 3 名"

STEP 4: Reranking   Query: enterprise refund policy
  Before: refund 0.0328, refund 0.0323, api 0.0317, security 0.0310, product 0.0310
  After:  refund 5.1639, refund 1.6613, api 1.6587, security 1.6550, product 1.6550   ← 顺序未变

STEP 5: HyDE
  Direct search top-3: refund 0.3069, api 0.2203, uptime 0.2129
  HyDE search top-3:   refund 0.3052, uptime 0.2189, api 0.1936      ← 都没找到 earnings

STEP 6: Parent-Child Chunking
  Total words: 555 / Parent chunks: 6 / Child chunks: 23 / Ratio: 3.8
  Matched children: #0 (0.4003), #1 (0.2277), #2 (0.2216) → 全部 Parent #0

STEP 7: Faithfulness Evaluation
  Good answer: Faithfulness: 1.00
  Bad answer:  Faithfulness: 0.67, Ungrounded: "There is a $50 processing fee"

STEP 8: 四种方法 × 5 个查询 → 全部 HIT
```

逐项解读：

- **Step 1**：BM25 第 1 名不含答案，原因是停用词 `was`（贡献 3.066 分）和不处理标点；第 3–5 名都是 0 分的 refund chunk（稳定排序按下标排列）。讲义问题描述中"答案 chunk 用的是 earnings 而不是 revenue"的情形在这份语料中并不成立——示例文档里写的就是 "Total revenue for Q3 2025"。
- **Step 2**：5 个查询两路第 1 名的**来源**都一致，说明这份小语料上两种检索没有本质分歧，也就难以演示 hybrid 的优势。
- **Step 3**：RRF 分数可以完全手算；零分 chunk 混进融合结果是本次运行最值得注意的现象。
- **Step 4**：rerank 后分数拉开了（5.16 vs 1.66），但前 5 名的顺序没有变化；chunk 0 能拿高分主要靠 bigram "refund policy"（2.0 分）。
- **Step 5**：查询里只有 `the` 在词表中，模板假想答案也没带来任何财务词汇，所以 HyDE 没有改善（见 3.7）。
- **Step 6**：命中的 3 个子块属于同一个父块；真正含 "60-day" 的 Child #1 排第 2。
- **Step 7**：好答案 1.00、坏答案 0.67。坏答案的 3 个 claim 全错，但只被抓到 1 个。
- **Step 8**：20 格全 HIT，对比失去区分度；按文档判定掩盖了 chunk 级别的退化。
- 结论：代码完整演示了进阶 RAG 的**流程**，但在这份 18-chunk 的语料上，"进阶"技术的收益几乎观察不到，部分环节甚至略有退化。这本身就是讲义 outputs 中强调的教训：**每加一项技术都要用 Recall@k 和 faithfulness 量化前后差异**。

---

## 7. 动手改一改

1. **清洗分词**：写一个 `tokenize(text)`，小写化、去掉标点（`re.findall(r"[a-z0-9$%.-]+", ...)` 或 `str.translate`）、去停用词，替换 BM25 与 TF-IDF 中所有的 `lower().split()`。重跑 Step 1，确认含 `$47.2 million` 的 chunk 12 升到第 1。
2. **修 RRF 与 chunk_text**：融合前过滤零分结果；`chunk_text` 在 `end >= len(words)` 时 `break`。对比 Step 3 与 Step 1 的输出变化（参考测验 Q9、Q11）。
3. **讲义练习 2：metadata filter**：给每个 chunk 加 `category` 字段（security / billing / api / product），检索前先按类别过滤，用 `"What encryption is used?"` 验证只搜 security。
4. **修 parent-child**：逐文档切父块，`child_size=30, parent_size=100`（讲义练习 4），检索后对父块去重再拼 prompt，并把 `build_rag_prompt` 用起来。
5. **讲义练习 5：Recall@k 评测**：为 10 个问题标注答案所在的 **chunk ID**，用 `evaluate_retrieval_recall` 比较 vector / BM25 / hybrid / hybrid + rerank 在 k = 3、5、10 时的 Recall，找出 rerank 真正起作用的地方。
6. **进阶：换成真实模型**：用 `sentence-transformers` 的 embedding 模型替换 TF-IDF、用 `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")` 替换 `rerank`、用 LLM 生成 HyDE 假想答案（讲义 "Use It" 部分），在同一评测集上对比。

---

## 8. 常见坑

- **以为 RRF 输出的都是相关结果**：RRF 只看名次，0 分的"第 3 名"也会拿到 1/63 的分数；融合前要过滤。
- **标点和停用词没处理**：`quarter?` 永远匹配不上、`was` 能主导 BM25 排名——分词质量直接决定关键词检索的上限。
- **把不同量纲的分数直接相加**：rerank 中 `initial_score * 5.0` 只贡献约 0.16 分，第一阶段信号几乎丢失。
- **把模板当 HyDE**：HyDE 的价值来自 LLM 写出的领域词汇；不引入新词的"假想答案"只会带来套话噪声。
- **parent-child 跨文档、不去重**：父块混入别的文档内容，同一父块被重复拼进 prompt。
- **只用词重叠做 faithfulness**：改数字、改否定、改时间的幻觉大多能"通过"检查。
- **按文档而非 chunk 计算命中**：文档级 HIT 会把"找对了文档、拿错了段落"算成成功；评估应以 chunk ID 为单位。
- **语料太小看不出差异**：18 个 chunk、每路取 15 个候选，几乎等于全量检索；评估进阶技术需要足够大且有难例的语料。
