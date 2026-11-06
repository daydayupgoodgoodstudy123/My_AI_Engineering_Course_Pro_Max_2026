# 测验 · RAG（检索增强生成）（RAG (Retrieval-Augmented Generation)）

> **阶段 11 · LLM 工程 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | RAG 解决什么 | 模型只知道训练截止前的公开数据；RAG 在提问时检索私有/最新文档、贴进 prompt，让模型基于这些内容作答 |
| 2 | 四步模式 | Query → Retrieve → Augment prompt → Generate；差别都在细节：怎么切块、怎么 embed、怎么检索、怎么拼 prompt |
| 3 | 两个阶段 | 索引（离线，文档变化时重跑：切块 → embed → 存储）与查询（在线，每个请求：embed 查询 → top-k → 拼 prompt → 生成） |
| 4 | RAG vs fine-tuning | RAG 便宜、更新快（重新索引即可）、可溯源、文档不进权重；fine-tuning 适合改变风格、语气、推理模式 |
| 5 | 相似度 | cosine 是默认选择，只看方向、不受文本长度影响；dot 受模长影响；L2 越小越相似 |
| 6 | Chunking | 固定长度 + 重叠、语义（按段落/标题）、递归；太小缺上下文，太大稀释相关性，常用 256–512 token、50 token 重叠 |
| 7 | 向量存储 | 本节是内存中的暴力检索（等价 FAISS flat index，讲义称约 10 万向量内可用）；生产用 HNSW 等 ANN |
| 8 | Prompt 构造 | "只根据以下上下文回答，不足就说不知道" + 编号的来源 + 问题放在最后 |
| 9 | 典型生产参数 | k = 5–10；检索内容 2,500–5,000 token；总 prompt 8K–16K；检索 50–200 ms，生成 500–3000 ms（讲义 Real Numbers） |
| 10 | 评估 | 检索指标（recall@k、precision@k、MRR）+ 生成指标（faithfulness 忠实度、answer relevance 相关性）；本节代码没有任何评估与拒答阈值 |

### 核心技能（能动手做到）

- [ ] 不依赖任何库写出完整的 RAG 流水线：切块、TF-IDF、cosine 检索、prompt 构造、（模拟）生成
- [ ] 手算平滑 IDF：`ln((n+1)/(df+1)) + 1`
- [ ] 读懂并修复抽取式"生成器"的分句、标点、平局问题
- [ ] 为检索加相关性阈值和拒答路径，并说明词法方法的局限
- [ ] 给 prompt 加上来源元数据，让答案可以引用出处
- [ ] 准备一组问答对，计算 recall@k 与 MRR，并用它比较不同 chunk 大小
- [ ] 把多轮追问改写成独立问题（query rewriting）再检索

---

## 二、基础自测（选择题）

**Q1.** 讲义认为下列哪种需求是 fine-tuning **胜过** RAG 的场景？

- A. 知识库每周更新，需要答案引用来源
- B. 回答公司内部的退款政策
- C. 让模型稳定采用某种特定的风格、语气或推理模式
- D. 不希望训练数据被固化进模型权重

**Q2.** STEP 2 的小语料为三句话："The cat sat on the mat"、"The dog sat on the rug"、"Machine learning is a branch of artificial intelligence"。按本节 `compute_idf`，`cat` 的 IDF 是：

- A. 1.693
- B. 1.288
- C. 0.693
- D. 1.000

**Q3.** 关于 RAG 的两个阶段，正确的是：

- A. 索引和查询都在每个用户请求时完整执行一遍
- B. 查询时可以换一个更好的 embedding 模型，不影响已有索引
- C. 索引阶段需要调用 LLM 生成答案
- D. 索引离线进行、文档变化时重做；查询在线进行，必须用与索引**相同**的 embedding 方法（本节即同一词表与 IDF）把问题转成向量

**Q4.** `build_rag_prompt` 中写有"Answer the question based ONLY on the following context. If the context doesn't contain enough information, say ..."。这两句的主要作用是：

- A. 减少 prompt 的 token 数
- B. 把答案约束在检索到的内容上（grounding），并给模型一条明确的拒答路径，降低幻觉
- C. 让检索阶段返回更多文档
- D. 提高 embedding 的质量

**Q5.** 运行 STEP 4，问题"What is the refund policy for enterprise customers?"得到的答案是"Acme Corp Refund Policy"，而正确答案（企业客户 60 天退款窗口）就在检索到的第一个块里。原因是：

- A. 检索出错，第一个块里没有企业客户的句子
- B. TF-IDF 把"enterprise"的权重算成了 0
- C. LLM 产生了幻觉
- D. `simple_generate` 选与问题重叠词最多的句子：标题句命中 `refund`、`policy` 两个词，企业句命中 `enterprise`、`refund` 两个词（`customers?` 因问号不匹配），平局时 `>` 保留先出现的标题句

**Q6.** 对查询"What is the capital of France?"，检索 top-1 分数为 0.3901，**高于**真正的业内问题"What is the refund policy for enterprise customers?"的 top-1 分数 0.3419。这说明：

- A. 该查询只命中了 `is`、`the`、`of` 等虚词，TF-IDF cosine 的绝对值没有"相关程度"的含义；代码又没有相关性阈值，无关问题也照样返回 top-k
- B. 知识库里确实有关于法国首都的内容
- C. cosine 相似度计算有 bug
- D. 分数越高越相关，系统应优先回答这个问题

**Q7.** STEP 5 中 chunk_size 取 20、50、100、200 时，`answer_len` 全都是 23。最合理的解释是：

- A. 四种切块检索到的内容完全相同
- B. 答案长度被代码截断到 23 个字符
- C. 四种配置都返回了同一个标题句"Acme Corp Refund Policy"（正好 23 个字符）；瓶颈在"生成器"而不是检索，而 `top_score` 又因每次重新 fit 词表而不可比
- D. chunk 大小对 RAG 没有影响

**Q8.** 按讲义的生产参数，k = 5、每块 512 token 时，检索内容约占多少 token？是否落在讲义建议的"2,500–5,000 token"范围内？

- A. 512，低于范围
- B. 2,560，在范围内
- C. 5,120，略高于范围
- D. 25,600，远高于范围

---

## 三、动手 / 代码题

**Q9.** 本节的"生成器"：

```python
def simple_generate(prompt, retrieved_chunks):
    query_section = prompt.lower().split("question:")[-1]
    query_words = set(query_section.split())
    stop_words = {"the", "a", "an", "is", "are", ...}
    query_words = query_words - stop_words
    ...
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
```

实测问题：
- "How is customer data encrypted?" 的答案是"Customer data is stored in isolated tenants..."；
- "What happens if uptime falls below the SLA?" 的答案以"...10% credit for each 0"结尾；
- "Does Acme support SAML?" 的答案是"Acme Corp does not sell or share customer data with third parties"。

1. 分别找出这三个现象的原因。`query_words` 里除了问题本身的词，还混进了什么？
2. 改写一个更合理的抽取式生成器，并说明它仍然解决不了哪个问题、为什么。

**Q10.** 拒答与相关性阈值：

```python
    def query(self, question, top_k=None):
        k = top_k or self.top_k
        query_emb = tfidf_embed(question, self.vocab, self.idf)
        results = search(query_emb, self.embeddings, k)
```

1. 实测"What about enterprise?"检索出 3 个分数为 0.0 的块。为什么分数全是 0？为什么仍然返回了 3 个块？
2. 在 `query` 中加入"去停用词后再检索 + 分数阈值 + 拒答"。用阈值 0.25 时，对 6 个业内问题和 3 个无关问题（法国首都、Acme 的 CEO、是否支持 SAML）分别会怎样？
3. 这说明词法检索做拒答的根本局限是什么？生产中怎么做？

**Q11.** 讲义练习 3 与练习 4：

1. 当前 prompt 只写 `[Source 1]`、`[Source 2]`，而 `RAGPipeline` 其实保存了 `self.sources`。改写 `build_rag_prompt`，让 LLM 能引用文件名。
2. 写一个 `evaluate(rag, qa_pairs, k)`：对每个"问题 → 答案关键片段"判断 top-k 中是否有块包含该片段，输出 recall@k 和 MRR。用 8 个问答对比较 chunk_size = 20/50/100/200，结果说明了什么？要注意什么陷阱？

**Q12.** 讲义练习 5（多轮 RAG）：先问"How much does the Professional plan cost?"，再追问"What about enterprise?"。

1. 直接拿追问去检索会怎样？
2. 一个简单的"把追问拼上上一个问题"的改写会怎样？为什么仍然答错？
3. 正确的改写应当是什么？用它检索后，答案为什么是一个半截句子"The Enterprise plan includes everything in"？这暴露了什么问题？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 RAG？画出（或口述）它的完整流水线，并说明离线和在线各做什么。

**Q14.**（原理深挖）RAG 和 fine-tuning 各适合什么场景？二者能否结合？讲义说 RAG"grounded in retrieved documents"，RAG 就不会幻觉了吗？

**Q15.**（工程实践）你的 RAG 系统上线后用户反馈"经常答非所问"。你如何定位问题出在检索还是生成？给出排查步骤和指标。

**Q16.**（场景设计）为一家公司的 20 万页内部文档（含权限控制、每天有更新）设计 RAG 系统：切块、embedding、存储、检索、prompt、更新、评估分别怎么做？

**Q17.**（追问型）chunk 大小怎么定？为什么讲义说"Chunk size matters more than people think"？只看 top-1 相似度分数选 chunk 大小有什么问题？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："The one case where fine-tuning wins: when you need the model to adopt a specific style, tone, or reasoning pattern that cannot be achieved through prompting alone. For factual knowledge retrieval, RAG wins every time."
- A：频繁更新 + 引用来源正是 RAG 的强项（freshness、auditability）。
- B：事实型知识检索，RAG 更合适——这就是讲义 The Problem 的例子。
- D：讲义表格"Data privacy: Training data baked into weights"是 fine-tuning 的缺点，是选择 RAG 的理由。

### Q2 — 答案：A

`n = 3`，`cat` 只出现在 1 句中：`ln((3+1)/(1+1)) + 1 = ln 2 + 1 ≈ 1.693`，与 STEP 2 输出一致（所有只出现在一句中的词 IDF 都是 1.693）。
- B 是出现在 2 句中的词（`the`、`sat`、`on`）的 IDF：`ln(4/3) + 1 ≈ 1.288`。
- C 是忘了 `+1` 的 `ln 2`。
- D 是出现在所有 3 句中的词才会有的值（`ln(4/4) + 1 = 1`），本语料没有这样的词。

### Q3 — 答案：D

讲义："The indexing phase runs once per document (or when documents update). The querying phase runs on every user request." 本节 `query` 用 `self.vocab` 和 `self.idf`（索引时建立的）来 embed 问题，必须一致，否则向量维度和含义都对不上。skill 文件"Common mistakes"第一条："Using different embedding models for indexing and querying (vectors are incompatible)"。
- A 错：索引是离线批处理。
- B 错：换模型必须全量重建索引。
- C 错：索引阶段只切块、embed、存储，不生成答案。

### Q4 — 答案：B

"ONLY on the following context"把模型限制在检索内容上（grounding）；"say 'I don't have enough information'"给出拒答路径，否则模型倾向于用自己的参数知识"编"一个答案。
- A：这两句反而增加 token。
- C、D：prompt 不影响检索与 embedding。
- 另外注意 prompt 的结构：指令在最前，上下文在中间，问题在最后——这与上一节 lost-in-the-middle 的建议一致。

### Q5 — 答案：D

实测：查询部分 `prompt.lower().split("question:")[-1]` 得到 `" what is the refund policy for enterprise customers?\n\nanswer:"`，去停用词后是 `{refund, policy, enterprise, customers?, answer:}`。标题句 `{acme, corp, refund, policy}` 命中 2 个；企业句（"Enterprise plan customers receive an extended 60-day refund window..."）命中 `enterprise`、`refund` 2 个（`customers` ≠ `customers?`）。`if overlap > best_score` 用严格大于，平局保留先遇到的标题句。
- A 错：第一个块（50 词）包含完整的企业句（已打印验证）。
- B 错：检索阶段 `enterprise` 正常参与了打分。
- C 错：本节没有 LLM，"生成"是确定性的句子抽取。

### Q6 — 答案：A

"What is the capital of France?" 中只有 `is`、`the`、`of` 在词表里（已实测）。查询向量只有这三个维度，与恰好虚词密度高的块（13 号块，SLA 文档）cosine 达到 0.39。cosine 的绝对值只反映"方向重合度"，不代表"语义相关程度"；而 `search` 无条件返回 top-k，于是无关问题也会得到 3 个"高分"块。
- B 错：知识库全是 Acme 公司文档。
- C 错：计算是正确的。
- D 错：这正是需要阈值和拒答机制的原因（Q10）。生成器在这个问题上碰巧正确拒答，是因为去停用词后剩下的 `capital`、`france?` 与任何句子都不重叠。

### Q7 — 答案：C

`len("Acme Corp Refund Policy") == 23`。不管切块大小如何，标题句都在第一个块里，生成器都因 Q5 的平局规则选中它。这说明对 RAG 质量的评估要分别看检索和生成——此处检索 top-1 都来自退款文档，错误发生在生成环节。`top_score` 也不能横比：每次 `index` 都重新建词表、算 IDF。
- A 错：块数（35/15/10/5）和内容都不同。
- B 错：代码没有截断答案。
- D 错：chunk 大小对检索影响很大（Q11 的 recall 实验）。

### Q8 — 答案：B

`5 × 512 = 2,560` token，在 2,500–5,000 范围内（讲义 Real Numbers："k = 5 to 10"、"Chunk size = 256 to 512 tokens"、"Context budget: 2,500-5,000 tokens of retrieved content per query"）。k = 10 时为 5,120，略超上限。
- A 只算了一个块。
- C 是 k = 10 的情况。
- D 多乘了 10。

### Q9 — 参考答案

1. 三个现象的原因（均已实测）：
   - **标点粘连**：`encrypted?` 带问号，与句中的 `encrypted` 不匹配，剩下 `customer`、`data` 两个词让"Customer data is stored in isolated tenants..."（命中 2 个）胜过"All data is encrypted at rest using AES-256..."（只命中 `data` 1 个）。
   - **按 `.` 分句**：`chunk.split(".")` 把 `0.1%` 切成 `0` 和 `1% below...`，句子在"for each 0"处被截断；`TLS 1.3`、`status.acme.com`、`99.9%` 同样会被切开。
   - **只要有 1 个词重叠就作答**："Does Acme support SAML?" 去停用词后是 `{acme, support, saml?}`，`acme` 出现在很多句子里，于是随便选出一句含 `acme` 的句子——这是**看起来像答案的错误回答**，比拒答更危险。
   - `query_words` 里还混进了 `answer:`：`split("question:")[-1]` 把 prompt 末尾的 `"\n\nAnswer:"` 也带了进来。正确做法是直接把原始问题传给生成器，而不是从拼好的 prompt 里反向解析。
2. 改进版（已运行验证）：

```python
import re
STOP = {"the", "a", "an", "is", "are", "was", "were", "what", "how", "why", "when", "where",
        "do", "does", "for", "of", "in", "to", "and", "or", "on", "at", "by", "it", "its",
        "this", "that", "who", "much", "which", "acme", "corp"}     # 品牌词在本语料中无区分度

def words(text):                                   # 去标点 + 极简词干
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        for suf in ("ion", "ed", "s"):
            if len(w) > 5 and w.endswith(suf):
                w = w[: -len(suf)]
                break
        out.add(w)
    return out - STOP

def split_sentences(text):                         # 只在"句号+空白+大写字母"处分句
    text = " ".join(text.split())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if len(s.strip()) >= 10]

def generate_v2(question, chunks):
    q = words(question)
    best, best_score = None, 0.0
    for chunk in chunks:
        for s in split_sentences(chunk):
            score = len(q & words(s)) / (len(q) or 1)
            if score > best_score:
                best, best_score = s, score
    return best or "I don't have enough information to answer that."
```

   结果：退款问题 → "Enterprise plan customers receive an extended 60-day refund window..."；加密问题与"What encryption does Acme use?"（`encryption`、`encrypted` 都归一为 `encrypt`）→ "All data is encrypted at rest using AES-256 and in transit using TLS 1.3."；SLA 句子不再在 `0.1%` 处截断；法国首都 → 拒答。
   **仍解决不了的**："Does Acme support SAML?" 现在答成了"The Professional plan adds ... priority support for $99..."——`support` 这个词在两个语境中含义不同。词重叠无法判断"这句话是否真的回答了问题"，这正是生产中要用 LLM 来生成、并用 faithfulness 评估来检查的原因。

### Q10 — 参考答案

1. `enterprise?` 带问号、`what`/`about` 不在词表中，查询向量全为 0；`cosine_similarity` 遇到零范数返回 0.0，所以所有块都是 0。`search` 仍然排序并返回前 3 个（并列 0 分，按原顺序取前三个退款块），`query` 没有任何"分数太低就不返回"的判断。
2. 实现与结果（已运行验证）：

```python
import re
STOP = {"the", "a", "an", "is", "are", "was", "were", "what", "how", "why", "when",
        "where", "do", "does", "for", "of", "in", "to", "and", "or", "on", "at", "by",
        "it", "its", "this", "that", "who", "much", "which"}

def content_query(q):
    return " ".join(w for w in re.findall(r"[a-z0-9$%.-]+", q.lower()) if w not in STOP)

    def query(self, question, top_k=None, min_score=0.25):
        k = top_k or self.top_k
        query_emb = tfidf_embed(content_query(question), self.vocab, self.idf)
        results = [(i, s) for i, s in search(query_emb, self.embeddings, k) if s >= min_score]
        if not results:
            return {"question": question, "retrieved": [],
                    "answer": "I don't have enough information to answer that."}
        ...
```

| 问题 | 去停用词后 top-1 | 阈值 0.25 下的结果 |
|------|----------------|-------------------|
| refund policy for enterprise | refund 0.423 | 作答 |
| API rate limits | api 0.387 | 作答 |
| customer data encrypted | security 0.336 | 作答 |
| uptime falls below SLA | uptime 0.432 | 作答 |
| Professional plan cost | product 0.319 | 作答 |
| What encryption does Acme use? | api 0.190 | **误拒**（`encryption` ≠ `encrypted`，只剩 `acme` 命中） |
| capital of France | 0.000 | 拒答 |
| CEO of Acme | 0.190 | 拒答 |
| support SAML | 0.201 | 拒答 |

   去掉虚词后，无关问题的分数从 0.39 降到 0~0.2，6 个业内问题中 5 个正常作答、3 个无关问题全部拒答；代价是 1 个业内问题因词形不同被误拒。
3. 根本局限：词法相似度只看字面，**分数既受同义/词形影响而偏低，又受常见词影响而偏高**，不存在一个能干净分开"相关/不相关"的阈值。生产做法：神经 embedding（同义词也能匹配）+ 混合检索（BM25 + dense）+ cross-encoder 重排序（重排分数更适合做阈值）+ 在 prompt 中要求 LLM 在上下文不足时拒答，并用"无答案问题"组成的评测集校准阈值（下一节 Advanced RAG）。

### Q11 — 参考答案

1. 带来源的 prompt：

```python
def build_rag_prompt(query, retrieved):
    context = "\n\n---\n\n".join(
        f"[{i + 1}] (source: {r['source']}, chunk {r['index']})\n{r['chunk']}"
        for i, r in enumerate(retrieved)
    )
    return (
        "Answer the question based ONLY on the following context.\n"
        "Cite the sources you used as [n] after each claim.\n"
        "If the context doesn't contain enough information, "
        "say \"I don't have enough information to answer that.\"\n\n"
        f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
    )
```

   `query` 中把 `retrieved`（含 `source`、`index`）整体传入，返回结果时也带上来源列表，前端就能显示"答案来自 refund-policy.md"。这正是讲义说的 auditability。
2. 评估函数（已运行验证）：

```python
def evaluate(rag, qa_pairs, k=3):
    hits, rr = 0, 0.0
    for question, answer_span in qa_pairs:
        retrieved = rag.query(question, top_k=k)["retrieved"]
        ranks = [i + 1 for i, r in enumerate(retrieved) if answer_span in r["chunk"]]
        hits += bool(ranks)
        rr += 1 / ranks[0] if ranks else 0.0
    return hits / len(qa_pairs), rr / len(qa_pairs)      # recall@k, MRR
```

   8 个问答对（如"How is customer data encrypted?" → `AES-256`、"How long are backups retained?" → `30-day retention`、"What HTTP status is returned when the rate limit is exceeded?" → `429`）的结果：

| chunk_size / overlap | recall@1 | recall@3 | MRR@3 |
|---------------------|----------|----------|-------|
| 20 / 5 | 0.50 | 0.625 | 0.542 |
| 50 / 10 | 0.75 | 1.00 | 0.854 |
| 100 / 20 | 1.00 | 1.00 | 1.00 |
| 200 / 40 | 1.00 | 1.00 | 1.00 |

   说明：20 词的块太碎，答案与问题关键词常被切到不同块；50 词时答案都在 top-3 内，但"API rate limits"的答案（`100 requests per minute`）排在第 2（top-1 是讲 rate-limit headers 的块）。
   **陷阱**：本语料每篇文档只有 91–102 词，chunk 100/200 时**一篇文档基本就是一个块**，"召回"变得轻而易举，但送进 LLM 的 token 也成倍增加。所以比较 chunk 大小时要同时报告上下文 token 成本，并在真实长度的文档上测；评估的粒度要是"答案片段是否被召回"，而不只是"来源文件是否正确"——"What encryption does Acme use?"的 top-1 来自正确的 security.md，但那个块并不含 `AES-256`，正确的块排在第 3。

### Q12 — 参考答案

1. 直接检索：查询向量全 0（Q10），返回 3 个 0 分的退款块，生成器拒答。用户会觉得"系统听不懂追问"。
2. 拼接改写 "How much does the Professional plan cost? What about enterprise?"：`enterprise?` 带问号仍不匹配，`professional`、`plan`、`cost` 主导检索和抽取，答案仍是 Professional 的 $99（已实测）。拼接只补了上下文，没有替换问题的焦点。
3. 正确的改写是把追问"翻译"成独立问题：**"How much does the Enterprise plan cost?"**（生产中由 LLM 根据最近几轮对话完成，常称 query rewriting / condensing）。用它检索后 top-1 是产品文档 3 号块，但答案是"The Enterprise plan includes everything in"——因为 50 词的切块恰好在这句话中间断开，"Professional plus custom integrations... Enterprise pricing is custom and starts at $500 per month"在 4 号块里，而 4 号块没有进入 top-3（已实测）。这暴露了**固定长度切块会切断句子**的问题：重叠只有 10 词，不足以保证每个完整的事实都落在同一块中。改进：按句子/段落边界切块（讲义的 semantic / recursive chunking）、加大重叠，或检索到块后把相邻块一起取回（扩展上下文窗口）。

### Q13 — 参考回答要点

- **定义**：Retrieval-Augmented Generation，检索相关文档片段并放入 prompt，让 LLM 基于这些内容生成答案；讲义："Leave the model untouched."
- **离线索引**：加载文档 → 清洗 → 切块（256–512 token，50 重叠）→ embed 每块 → 连同原文和元数据（来源、位置、权限）写入向量库。
- **在线查询**：（可选）改写问题 → 用同一模型 embed 问题 → 向量检索 top-k（5–10）→（可选）重排序 → 拼 prompt（指令 + 编号来源 + 问题）→ LLM 生成 → 返回答案和引用。
- **数字感**：检索 50–200 ms，生成 500–3000 ms；检索内容 2,500–5,000 token。
- 加分点：提到原始 RAG 论文（Lewis et al., 2020）与 DPR（Karpukhin et al., 2020，讲义称其证明了稠密检索在开放域问答上优于 BM25）；指出本节用 TF-IDF 只是为了把"文本 → 向量"讲具体。

### Q14 — 参考回答要点

- **RAG 适合**：私有/最新知识、需要引用来源、知识频繁变化、需要按用户权限过滤内容。讲义表格：成本、时效、可审计、隐私。
- **fine-tuning 适合**：固定的风格、格式、领域语言习惯、特定推理模式；或把冗长的 prompt 指令"内化"以节省 token。
- **结合**：先微调让模型更会"读检索内容并引用"（或适应领域术语），再用 RAG 提供事实；也可以微调 embedding 模型或重排模型提升检索。
- **RAG 仍会幻觉**：讲义表格写"Grounded in retrieved documents"偏乐观。常见情况：检索不到正确内容时模型用参数知识补全；检索到相互矛盾的内容；模型误读上下文或过度推断。本节 Q9 中"Does Acme support SAML?"被答成一句无关的话，就是"有依据的样子、没依据的内容"。缓解：拒答指令、相关性阈值、引用每个论断、faithfulness 评估（检查答案中的每个陈述能否在上下文中找到）。
- 常见误区：认为"有 RAG 就不需要评估生成质量"。

### Q15 — 参考回答要点

- **先拆开看**：对一批失败样例，分别记录检索到的块和最终答案。
  - 正确答案所在的块**没有被检回** → 检索问题；
  - 检回了但答案仍错 → 生成/prompt 问题（本节 Q5 就是这一类）。
- **检索侧指标与排查**：
  - 构建带标注的评测集，测 recall@k、MRR、nDCG；
  - 检查切块是否把答案切断（Q12）、分词/标点问题（本节的 `customers?`）、embedding 模型是否适合领域（专有名词、代码、多语言）、索引与查询是否用同一模型；
  - 尝试混合检索、重排序、query rewriting、调整 k 与 chunk 大小。
- **生成侧指标与排查**：
  - faithfulness（答案是否被上下文支持）、answer relevance（是否回答了问题）；可用 LLM-as-judge 或 RAGAS 类框架；
  - 检查 prompt：是否有拒答指令、是否要求引用、上下文是否过长导致 lost-in-the-middle、temperature 是否过高（skill 文件建议事实问答用 0）。
- **线上**：记录每次请求的检索结果与分数、用户反馈；定期把失败样例加入评测集做回归。
- 加分点：给出"无答案问题"的拒答率指标，避免系统对什么都硬答。

### Q16 — 参考回答要点

- **文档处理**：按文档结构（标题、段落、表格）做递归切块，256–512 token、约 50 token 重叠；每块保存来源、标题路径、更新时间、**权限标签**。
- **Embedding**：在自有问题集上比较几个候选模型（讲义："see Phase 5 · 22"），注意多语言与领域术语；记录模型版本。
- **存储与检索**：选支持元数据过滤和 ANN 的向量库（pgvector、Qdrant、Weaviate、托管服务等）；检索时**先按用户权限过滤**再算相似度，避免越权；混合检索（BM25 + dense）+ 重排序；k 取 5–10。
- **Prompt**：指令 + 编号来源（含标题与链接）+ 问题；要求逐句引用、不足则拒答；控制总长度在讲义的 8K–16K 量级。
- **增量更新**：文档变更事件触发对应块的删除与重建（用文档 ID + 内容哈希判断变化）；删除的文档要同步从索引中移除；换 embedding 模型需要全量重建。
- **评估与监控**：离线评测集（recall@k、faithfulness、拒答率）；线上记录检索命中、延迟（检索 50–200 ms、生成 500–3000 ms 量级）、用户反馈与成本。
- 常见误区：只在入库时做权限检查、检索时不过滤；文档更新后忘了重新索引（skill 文件 Common mistakes）。

### Q17 — 参考回答要点

- **两端的失败**（讲义）：太小（64–128 token）缺乏上下文，"It increased 15% last quarter"不知道"it"指什么；太大（2048+）一块包含多个主题，相关性被稀释，还挤占上下文。
- **起点**：256–512 token、50 token 重叠，再按自己的文档与问题调。
- **影响因素**：文档结构（FAQ 适合小块，长篇技术文档适合按章节）、问题类型（事实查询 vs 需要综合的问题）、embedding 模型的最佳输入长度、上下文预算（k × chunk 大小）。
- **只看 top-1 分数的问题**：不同切块下词表、IDF（或文本长度分布）不同，分数不可比；分数高不代表块里真有答案；而且只看检索不看最终答案质量。本节 STEP 5 的 top_score 随块变大而升高，但 answer 全是同一个错误的标题句。
- **正确做法**：固定 embedding 模型，用带"答案片段"标注的问答集，对每种切块测 recall@k / MRR 和上下文 token 成本，再抽样看端到端答案（Q11 的实验）。
- 加分点：提到按句/段落边界切块、父子块（小块检索、返回大块上下文）等改进，详见下一节 Advanced RAG。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 04 Embeddings 与向量表示](../../04-embeddings/docs/zh.md)：TF-IDF、cosine、切块与向量索引，本节代码与之几乎相同。
- [阶段 11 · 05 Context Engineering](../../05-context-engineering/docs/zh.md)：检索内容是上下文的一部分，预算与 lost-in-the-middle 同样适用。
- [阶段 05 · 22 Embedding 模型 — 2026 年深度剖析](../../../05-nlp-foundations-to-advanced/22-embedding-models-deep-dive/docs/zh.md)：讲义建议据此选择 embedder。
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../../05-nlp-foundations-to-advanced/23-chunking-strategies-rag/docs/zh.md)：讲义推荐的六种切块算法。
- [阶段 05 · 14 信息检索与搜索](../../../05-nlp-foundations-to-advanced/14-information-retrieval-search/docs/zh.md)、[阶段 05 · 13 问答系统](../../../05-nlp-foundations-to-advanced/13-question-answering/docs/zh.md)：检索与抽取式问答的经典方法。

### 本节被哪些后续内容用到
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../07-advanced-rag/docs/zh.md)：混合检索、重排序、查询改写。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../08-fine-tuning-lora/docs/zh.md)：RAG 与微调的另一侧。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../10-evaluation/docs/zh.md)、[阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)：faithfulness、answer relevance 等 RAG 评估。
- [阶段 12 · 24 多模态 RAG 与跨模态检索](../../../12-multimodal-ai/24-multimodal-rag-cross-modal/docs/zh.md)：把 RAG 扩展到图像与文档版面。
- [阶段 19 · 08 面向受监管行业的生产级 RAG 聊天机器人](../../../19-capstone-projects/08-production-rag-chatbot/docs/zh.md)、[阶段 19 · 69 端到端 RAG 系统](../../../19-capstone-projects/69-end-to-end-rag-system/docs/zh.md)：综合项目中的完整实现。

### 延伸关键词
`retrieve-then-generate` · `indexing / querying` · `TF-IDF / smooth IDF` · `cosine similarity` · `top-k` · `chunk overlap` · `semantic / recursive chunking` · `grounding` · `citation` · `abstention / relevance threshold` · `query rewriting` · `recall@k / MRR` · `faithfulness` · `hybrid search` · `reranking` · `DPR`
