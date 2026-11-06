# 测验 · Advanced RAG（Chunking、重排序、混合检索）（Advanced RAG (Chunking, Reranking, Hybrid Search)）

> **阶段 11 · LLM 工程 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 向量相似 ≠ 相关 | Basic RAG 的 top-k 语义检索会召回"话题相近但不含答案"的 chunk；歧义查询、多跳问题、大语料（ANN 近似误差）是三类典型失败 |
| 2 | BM25 | `IDF(t) · tf·(k1+1) / (tf + k1·(1 − b + b·|d|/avgdl))`；k1（默认 1.2）控制词频饱和，b（默认 0.75）控制长度归一化；擅长精确匹配（如错误码 `E-4021`） |
| 3 | Hybrid search | 语义检索与 BM25 并行跑，再合并结果：前者懂"意思"，后者抓"原词"，互补 |
| 4 | Reciprocal Rank Fusion | `RRF(d) = Σ 1/(k + rank)`，k 常取 60；只用**名次**不用原始分数，因此不怕两路分数量纲不同 |
| 5 | Bi-encoder vs cross-encoder | bi-encoder 各自编码、可预计算、可扩展到百万级；cross-encoder 把 (query, doc) 一起输入，更准但慢 100–1000 倍，只能用于对候选集重排 |
| 6 | 两阶段检索 | 先用 hybrid 召回较大的候选集（如 top-50），再用 reranker 精排到 top-5 放进 prompt |
| 7 | Query transformation | 查询改写、HyDE（先生成"假想答案"再拿它去检索）、多查询 / step-back；HyDE 多一次 LLM 调用，讲义估计增加 500–2000ms |
| 8 | Parent-child chunking | 用小 chunk（如 128 token）检索保证精确，再把它所属的大 chunk（如 512 token）放进 prompt 保证上下文 |
| 9 | Metadata filtering | 先按日期、类别、来源等过滤再做向量检索，缩小搜索空间、避免"语义相近但过时"的文档 |
| 10 | RAG 评估三件套 | Recall@k（检索对没对）、faithfulness（回答是否有依据）、answer correctness（端到端是否答对） |

### 核心技能（能动手做到）

- [ ] 不依赖任何库写出 BM25 的 `index / score / search`，并能手算某个词对某个 chunk 的得分贡献
- [ ] 实现 RRF，并能手算"一路第 1、另一路缺席"与"两路都第 10"的融合分数谁高
- [ ] 读懂本节 `hybrid_search → rerank` 两阶段流水线，并指出启发式 reranker 与真正 cross-encoder 的差距
- [ ] 实现 parent-child chunking，说清 `child_to_parent` 映射、为什么要对父块去重、为什么不能跨文档切父块
- [ ] 写出基于词重叠的 faithfulness 检查，并能构造出它**检测不出来**的幻觉例子（数字被改、否定句）
- [ ] 为一个 RAG 系统设计 Recall@k / faithfulness 评估集，并据此决定该加 BM25、reranker 还是 HyDE

---

## 二、基础自测（选择题）

**Q1.** 关于 BM25 公式中的两个超参数，下列说法正确的是：

- A. k1 控制文档长度归一化，b 控制词频饱和
- B. k1 越大，词频对得分的影响越快饱和
- C. b = 0 时长文档会受到更强的惩罚
- D. k1 控制词频饱和（默认 1.2），b 控制长度归一化（默认 0.75）；b = 0 时完全不做长度归一化

**Q2.** 用 RRF（k = 60）融合向量检索与 BM25 两个排名列表。文档 A 在向量检索中排第 1、在 BM25 中**没有出现**；文档 B 在两个列表中都排第 10。哪个融合分数更高？

- A. B 更高（约 0.0286 vs 0.0164）
- B. A 更高，因为第 1 名永远优先
- C. 两者相等
- D. 无法判断，需要知道两路的原始分数

**Q3.** 讲义说"先用 hybrid search 取 top-50，再用 cross-encoder 重排到 top-5"。为什么不直接用 cross-encoder 对全库打分？

- A. cross-encoder 无法处理长文档
- B. cross-encoder 的分数不能排序
- C. cross-encoder 必须把 query 与每个文档拼在一起逐对前向计算，无法预计算，比 bi-encoder 慢 100–1000 倍，对百万级语料不可行
- D. cross-encoder 只支持英文

**Q4.** HyDE（Hypothetical Document Embeddings）检索时实际拿去做 embedding 的是：

- A. 用户原始问题
- B. 由 LLM 生成的一段"假想答案"
- C. 检索结果中的第一个真实文档
- D. 问题与所有文档的平均向量

**Q5.** 关于 parent-child chunking，说法正确的是：

- A. 父块和子块都放进向量索引，检索时取分数最高的那个
- B. 用父块检索，命中后把它的子块拼进 prompt
- C. 它的主要目的是减少 chunk 数量、节省存储
- D. 用小的子块建索引做检索，命中后把子块所属的父块放进 prompt

**Q6.** 运行本节代码 Step 1，查询 `"What was revenue last quarter?"` 的 BM25 第 1 名是**不含** `$47.2 million` 的 earnings chunk（得分 4.95），真正含答案的 chunk 排第 2（3.55）。最主要的原因是：

- A. 查询没有去停用词，`was` 在第 1 名 chunk 中出现 3 次，贡献了 3.07 分；而 `last`、`quarter?` 在任何 chunk 中都匹配不上
- B. BM25 的 IDF 对 `revenue` 给了负值
- C. 第 2 名的 chunk 比平均长度短，被长度归一化惩罚
- D. RRF 融合把第 1 名和第 2 名的顺序换了

**Q7.** 在 Weaviate 的 `collection.query.hybrid(query=..., alpha=0.0)` 中，`alpha = 0.0` 表示：

- A. 纯向量检索
- B. 向量与关键词等权
- C. 纯关键词（BM25）检索
- D. 关闭检索，直接让 LLM 回答

**Q8.** 本节 Step 7 中，"坏答案"（90 天退款窗口、即时退款、$50 手续费）的 faithfulness 得分是 0.67，只有"$50 手续费"一句被判为无依据。这说明：

- A. 坏答案其实大部分是对的
- B. 基于词重叠的检查只看内容词是否出现在上下文中，`90-day`、`instantly` 这类被改动的事实只占句子少数词，比例仍 ≥ 0.5，于是被误判为有依据
- C. 阈值 0.5 太低，改成 0.6 就能把三句都判出来
- D. 上下文检索错了，取到了别的文档

---

## 三、动手 / 代码题

**Q9.** 本节 Step 3 的真实输出如下（查询 `"What was revenue last quarter?"`）：

```text
  RRF fused top-5:
    #1 [earnings] rrf=0.0328 | to 14,200 from 11,800 in Q3 2024. ...
    #2 [earnings] rrf=0.0323 | Acme Corp Q3 2025 Earnings Report. ...
    #3 [refund] rrf=0.0317 | Acme Corp Refund Policy. ...
    #4 [refund] rrf=0.0312 | within 5-7 business days ...
    #5 [refund] rrf=0.0308 | cancelled mid-term ...
```

而向量 top-3 与 BM25 top-3 中，第 3 名的分数都是 `0.0000`。

```python
    vec_results = vector_search(query_emb, embeddings, top_k=10)
    bm25_results = bm25.search(query, top_k=10)
    fused = reciprocal_rank_fusion([vec_results, bm25_results])
```

1. 手算 #1、#2、#3 的 RRF 分数，说明它们从哪里来。
2. 为什么完全不相关的 refund chunk 能以 0.0317 排第 3，几乎和真正的答案并列？
3. 给出修复方法，并说明修复后融合结果是什么。

**Q10.** `evaluate_faithfulness` 的核心逻辑：

```python
    for sentence in answer_sentences:
        words = set(sentence.lower().split())
        content_words = words - stop_words
        matched = sum(1 for w in content_words if w in context)
        ratio = matched / len(content_words) if content_words else 0
        if ratio >= 0.5:
            grounded += 1
        else:
            ungrounded.append(sentence)
```

1. 写出坏答案第一句 `"Enterprise customers receive a 90-day refund window"` 的内容词及各自是否命中，算出 ratio。
2. `w in context` 是子串匹配还是整词匹配？举一个由此导致误判的例子。
3. 写一个补充检查 `numeric_claims_unsupported(answer, chunks)`：抽出句子里的数字（含 `$`、`%`、`5-7` 这种区间），凡不在上下文中出现的都报出来。在本节的坏答案上它应报出哪些？

**Q11.** 阅读 `chunk_text` 与 Step 6 的 parent-child 代码：

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

```python
    full_text = " ".join(SAMPLE_DOCUMENTS)
    parents, children, child_to_parent = create_parent_child_chunks(
        full_text, parent_size=100, child_size=25
    )
```

1. earnings 文档共 84 个词，`chunk_size=50, overlap=10` 时会切出哪几个区间？最后一个 chunk 有什么问题？如何修？
2. Step 6 输出显示 3 个命中的子块都映射到 `Parent #0`。如果直接把"每个子块的父块"拼进 prompt 会怎样？应如何处理？
3. 把 6 篇文档先拼成 `full_text` 再切父块，会带来什么问题？（提示：refund 文档只有 91 个词。）

**Q12.** Step 5 的 HyDE 演示中，查询 `"How much money did the company make?"` 的直接检索 top-3 是 `refund / api / uptime`，HyDE 检索 top-3 是 `refund / uptime / api`——**两者都没找到 earnings**。

1. 已知 TF-IDF 词表由语料中出现过的词构成。这个查询里有几个词在词表中？这说明直接检索靠什么在打分？
2. 模板生成的假想答案是 `"To address '...': The process involves several steps. First, you need to initiate the request for much money did company make. Then, the system processes it according to the defined rules and policies."`。为什么它反而把结果推向 refund / api？
3. 讲义对 HyDE 的直觉是"假想答案在 embedding 空间中更接近真实答案"。这个直觉成立需要什么前提？本节的模板实现缺了什么？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 hybrid search？为什么语义检索和 BM25 要一起用？为什么融合时通常用 RRF 而不是把两路分数直接加权相加？

**Q14.**（原理深挖）比较 bi-encoder、cross-encoder 和 late-interaction（ColBERT 类）三种相关性模型的计算方式、精度、成本和适用位置。

**Q15.**（工程实践）你接手一个线上 RAG 系统，用户反馈"经常答非所问"。你会怎样定位问题出在检索还是生成？会搭建哪些指标和评估集？

**Q16.**（场景设计）语料是某公司 200 万个 chunk 的财报、制度和工单。用户问"上个季度收入是多少？"。请设计一条能答对这个问题的检索链路，并说明每一环解决什么问题。

**Q17.**（追问型）HyDE 什么时候有用、什么时候反而有害？如果线上延迟预算很紧，你会怎么取舍？

---

## 五、参考答案与解析

### Q1 — 答案：D

BM25 的词频项 `tf·(k1+1)/(tf + k1·norm)` 随 tf 增大趋于上限 `k1+1`：k1 越大，饱和得越**慢**（B 说反了）。b 控制长度归一化：`norm = 1 − b + b·|d|/avgdl`，b = 0 时 norm 恒为 1，完全不看文档长度（C 说反了，b = 0 时不惩罚长文档）。A 把两个参数的作用对调了。

数值直觉（|d| = avgdl，k1 = 1.2，已实际计算）：tf = 1 → 1.0；tf = 3 → 1.571；tf = 10 → 1.964；tf = 50 → 2.148。这就是讲义所说"出现 50 次并不比出现 1 次相关 50 倍"。

### Q2 — 答案：A

- A：`1/(60+1) = 0.0164`（BM25 中缺席，贡献 0）。
- B：`1/(60+10) + 1/(60+10) = 2/70 = 0.0286`。

RRF 奖励"两路都认可"的文档。讲义："A document that ranks #1 in one list but is absent from the other gets a moderate score."。B 错在把单路第 1 名当作绝对优先；C 显然不等；D 错在 RRF 恰恰**只用名次**，与原始分数无关——这正是它的卖点。

### Q3 — 答案：C

bi-encoder 把文档向量离线算好、存进索引，查询时只需算一次 query 向量再做近邻搜索；cross-encoder 必须对每个 (query, doc) 对重新做一次完整前向，没法预计算。讲义："cross-encoders are 100-1000x slower than bi-encoders ... You cannot pre-compute cross-encoder scores for a million documents."。A、B、D 都不是本质原因（cross-encoder 输出的就是可排序的相关性分数，主流模型也有多语种版本）。

### Q4 — 答案：B

HyDE 先让 LLM 写一段"看起来像答案"的文字（哪怕事实不对），再把这段文字 embedding 后去检索真实文档。直觉是"答案与答案"的语言结构更像，跨过了"问题空间"和"答案空间"之间的鸿沟。A 是普通检索；C、D 不是任何标准做法。

### Q5 — 答案：D

讲义："Index small chunks (128 tokens) for retrieval. When a small chunk is retrieved, return its parent chunk (512 tokens) for the prompt."。小块语义集中、匹配精确；大块上下文完整、利于生成。A 混淆了两种粒度的用途；B 方向反了；C 错，parent-child 会**增加**存储（要同时存子块索引与父块文本）。

### Q6 — 答案：A

用 `BM25.score` 的公式逐项拆开（N = 18 个 chunk，avgdl ≈ 37.17，已实际计算）：

| chunk | `was` (tf, 贡献) | `revenue` (tf, 贡献) | 合计 |
|-------|-----------------|---------------------|------|
| #13（不含 $47.2M，44 词） | 3 次，3.066 | 1 次，1.886 | 4.953 |
| #12（含 $47.2M，50 词） | 1 次，1.777 | 1 次，1.777 | 3.554 |

`was` 和 `revenue` 都只出现在 2 个 chunk 里，IDF 同为 `ln(16.5/2.5 + 1) = 2.028`，所以停用词 `was` 和关键词 `revenue` 权重相同。`last` 不在任何 chunk 中，`quarter?` 带着问号永远匹配不上（只用 `split()` 不去标点）。另外，#12 中第二次出现的是 `revenue.`（带句号），也没被算进 tf。B 错：这个 IDF 变体 `ln(... + 1)` 恒为正；C 错：#12 比平均长度**长**；D 错：Step 1 是纯 BM25，没有融合。

### Q7 — 答案：C

讲义："0.0 = pure keyword (BM25), 1.0 = pure vector, 0.5 = equal weight. Most production systems use alpha between 0.3 and 0.7."。注意 Weaviate 的 alpha 是**分数加权**融合，与本节代码的 RRF（名次融合）是两种思路。

### Q8 — 答案：B

实际拆解（已运行验证）：

- `"Enterprise customers receive a 90-day refund window"`：内容词 6 个，只有 `90-day` 未命中，ratio = 5/6 ≈ 0.83 → 判为有依据；
- `"Refunds are processed instantly"`：`refunds`、`processed` 命中，`instantly` 未命中，ratio = 2/3 → 有依据；
- `"There is a $50 processing fee"`：`there / $50 / processing / fee` 全未命中，ratio = 0 → 无依据。

于是得分 2/3 = 0.67。实际上三句话**全是错的**：上下文写的是 60 天、5–7 个工作日、没有手续费。词重叠只能发现"凭空出现的新话题"，发现不了"同一话题下改了数字或语义"的幻觉。C 错：第一句 0.83、第二句 0.67，阈值调到 0.6 仍抓不住，调太高又会误杀正确答案；A、D 与事实不符（Step 7 检索到的 3 个 chunk 中 2 个是 refund、1 个是 api，refund 信息完整）。

### Q9 — 参考答案

1. `reciprocal_rank_fusion` 中 `1.0 / (k + rank + 1)`，rank 从 0 开始：
   - #1（chunk 13）在两路都排第 1：`1/61 + 1/61 = 0.0328`；
   - #2（chunk 12）在两路都排第 2：`1/62 + 1/62 = 0.0323`；
   - #3（refund chunk 0）在两路都排第 3：`1/63 + 1/63 = 0.0317`。
2. 对这个查询，只有 2 个 earnings chunk 得分大于 0；其余 16 个 chunk 在两路里都是 `0.0000`。`list.sort` 是稳定排序，分数相同时保持原下标顺序，所以 refund 的 chunk 0、1、2 在两路里都排第 3、4、5。RRF 只看名次，**把"分数为 0 的第 3 名"和"真正相关的第 3 名"一视同仁**，于是无关 chunk 以几乎相同的分数进入融合结果。若下游取 top-5 拼 prompt，就会塞进 3 个毫无关系的 refund chunk。
3. 修复：融合前过滤掉无效结果，例如 BM25 去掉 `score == 0` 的项、向量检索去掉相似度低于阈值的项：

```python
vec_results  = [r for r in vector_search(query_emb, embeddings, top_k=10) if r[1] > 0]
bm25_results = [r for r in bm25.search(query, top_k=10) if r[1] > 0]
fused = reciprocal_rank_fusion([vec_results, bm25_results])
```

修复后（已实际运行）融合结果只剩 `[(13, 0.0328), (12, 0.0323)]` 两个 earnings chunk。生产中向量检索几乎不会出现精确的 0 分，更常见的做法是设相似度下限，或者让 reranker 给出可信的绝对分数再截断。

### Q10 — 参考答案

1. 内容词：`enterprise ✓`、`customers ✓`、`receive ✓`、`90-day ✗`、`refund ✓`、`window ✓`，ratio = 5/6 ≈ 0.83 ≥ 0.5，判为有依据。
2. `w in context` 中 `context` 是一个**字符串**，所以是**子串匹配**。例如答案里出现 `"rate"`，上下文里只有 `"pro-rated"`，也会被算作命中；`"6"` 会因为上下文有 `"60-day"` 而命中。反过来，答案写 `"refund."`（带句号）而上下文是 `"refund,"`，`"refund."` 作为子串可能匹配失败。整词匹配应先把上下文分词成集合再查。
3. 参考实现（已在本节数据上运行）：

```python
import re

def numeric_claims_unsupported(answer, chunks):
    ctx = " ".join(chunks).lower()
    problems = []
    for s in re.split(r'(?<=[.!?])\s+', answer):
        nums = re.findall(r'\$?\d+(?:[.,]\d+)*(?:-\d+)?%?', s)
        missing = [n for n in nums if n.lower() not in ctx]
        if missing:
            problems.append((s.strip(), missing))
    return problems
```

在坏答案上报出：`("Enterprise customers receive a 90-day refund window.", ['90'])` 与 `("There is a $50 processing fee.", ['$50'])`；在好答案上返回空列表。它仍然抓不住"Refunds are processed instantly"（没有数字）——要检测这种语义改写，生产中通常用 NLI 模型或 LLM-as-judge 逐条核对 claim（见第 10 节）。

### Q11 — 参考答案

1. 区间是 `[0:50]`、`[40:90]`、`[80:84]`。第三个 chunk 只有 4 个词 `"with continued margin expansion."`，而且**完全被第二个 chunk 包含**——它没有任何新信息，却会占用索引、参与检索、挤占 top-k 名额（Step 1 中它就是那个 BM25 分数为 0 的 chunk 14）。修复：生成当前 chunk 后，若 `end >= len(words)` 就 `break`。修复后 earnings 只切 2 块；其他文档的尾块仍然大部分与前一块重叠（如 refund 的 `[80:91]` 只有 1 个新词），更好的做法是把过短的尾块并入前一块。
2. 3 个子块都指向同一个父块，直接拼就会把同一段 100 词的文本重复 3 次，浪费 token、挤掉其他来源。应当按检索顺序**对父块去重**（`dict.fromkeys(parent_ids)` 保序去重），再按需补足 top-k。
3. refund 文档只有 91 个词，第一个父块取前 100 个词，就会把 product 文档开头的 `"Acme Corp Product Overview. Acme Corp offers three product"` 也包进去（已实际检查 `parents[0]` 结尾）。父块跨文档会把无关内容送进 prompt，还会让引用来源不准。正确做法是**逐文档**切父块，并在每个块上保存 `source` 元数据。另外，代码打印的 `"(100 words each)"` 是写死的，最后一个父块实际只有 55 个词。

### Q12 — 参考答案

1. 查询分词为 `how / much / money / did / the / company / make?`，其中**只有 `the`** 在词表里（corpus 中没有 money、company、make 这些词）。所以直接检索的余弦相似度完全来自停用词 `the`：哪个 chunk 里 `the` 的 TF-IDF 权重大，哪个就排前面。refund 排第 1 和"收入"毫无关系。
2. 选中的是 `"how"` 模板，模板本身的词 `process / request / rules / policies / system` 与 refund（"submit refund requests"）和 api（"request and response bodies"）的用词重合，而查询中真正有信息的词在词表里一个都没有。假想答案越"套话"，就越把检索拉向套话多的文档。
3. 前提是：生成的假想答案要包含**语料中真实使用的领域词汇**（如 "revenue"、"earnings"、"$ million"、"Q3"），这需要一个懂领域的 LLM。模板实现只是把查询词原样塞回去，没有引入任何新词，无法跨越词汇鸿沟。可以对比：`"What was Q3 revenue?"` 用同样的模板做 HyDE，top-2 都是 earnings（因为查询本身就含 `q3`、`revenue`）。讲义 "Use It" 部分用 Claude 生成假想答案才是真正的 HyDE。这个演示也说明：代码末尾 SUMMARY 打印的 "HyDE bridges the query-document vocabulary gap" 在本次运行中**并没有被证明**。

### Q13 — 参考回答要点

- **定义**：语义检索（dense / 向量）和关键词检索（sparse / BM25）并行执行，再把两个排名列表合并。
- **互补性**：向量检索懂同义改写（"cancel subscription" ≈ "terminate plan"），但对错误码、产品型号、人名、数字等"无语义的精确串"不敏感；BM25 正好相反。讲义例子：`E-4021`。
- **为什么用 RRF**：两路分数量纲完全不同（余弦相似度 0–1，BM25 无上界且依赖语料统计），直接加权需要归一化和调参，而且分布随查询漂移。RRF 只用名次：`Σ 1/(k + rank)`，k = 60 让头部名次差距不至于过大，稳健、几乎无需调参（讲义引用 Cormack 等 2009 年论文：RRF 优于更复杂的融合方法）。
- **加分点**：分数加权（如 Weaviate 的 alpha）在有标注数据可调参时也常用；RRF 的坑是会把"分数为 0 但有名次"的结果也算进去（见 Q9），融合前要过滤。
- **常见误区**：以为 hybrid "不花钱"——它确实多了一次 BM25 查询，但相比 LLM 调用可以忽略；真正的成本是维护两套索引并保证它们对**同一批 chunk** 建索引（outputs 里的 skill 文件也强调了这一点）。

### Q14 — 参考回答要点

| | bi-encoder | cross-encoder | late interaction（ColBERT） |
|--|-----------|--------------|---------------------------|
| 计算方式 | query、doc 各自编码成一个向量，余弦/点积 | (query, doc) 拼接后一起过 Transformer，输出一个相关性分数 | 各自编码成**每个 token 一个向量**，打分时对每个 query token 取与 doc token 的最大相似度再求和（MaxSim） |
| 能否预计算 | 能，doc 向量离线存好 | 不能 | doc 的 token 向量能预计算 |
| 精度 | 最低（信息被压成一个向量） | 最高（query 和 doc 的 token 可以互相注意） | 居中，接近 cross-encoder |
| 成本 | 查询时只算一个向量 + ANN | 每对一次完整前向，慢 100–1000 倍 | 存储大（每 token 一个向量），打分 O(tokens) |
| 适用位置 | 第一阶段召回（百万级） | 第二阶段精排（几十到上百个候选） | 召回或精排均可 |

- 讲义列出的 2026 年 reranker：Cohere Rerank 3.5、Voyage rerank-2.5、Jina-Reranker-v2、bge-reranker-v2-m3、`cross-encoder/ms-marco-MiniLM-L-6-v2`（CPU 可跑，适合原型）、ColBERTv2 / Jina-ColBERT-v2。
- 加分点：指出本节代码的 `rerank` 只是词重叠启发式，并没有任何 "cross-attention"（SUMMARY 中的说法不准确）。

### Q15 — 参考回答要点

- **先分层定位**（与 outputs 中的 debugger prompt 的决策树一致）：
  1. 正确 chunk 是否在索引里？（没索引 / 被切断 → 改 chunking、加 overlap）
  2. 是否在 top-50 召回里？（不在 → 词汇不匹配：加 BM25、HyDE、查询改写）
  3. 是否在最终 top-k 里？（在 50 不在 5 → 加 reranker）
  4. 上下文对了但答错 → 生成问题：prompt 约束、降温度、faithfulness 检查。
- **指标**：Recall@k（k = 5、10、50 分别看）、MRR；faithfulness（答案的每个 claim 是否能在检索内容中找到依据）；answer correctness（与标准答案对比）。
- **评估集**：从真实日志抽样 50+ 条问题，人工标注"相关 chunk ID + 标准答案"；覆盖歧义查询、多跳问题、精确串（错误码、数字）、时效性问题；语料更新后定期重跑。
- **加分点**：每加一个技术就对比前后指标，避免"凭感觉堆功能"；faithfulness 不能只靠词重叠（见 Q8、Q10），要用 NLI 或 LLM-as-judge。
- **常见误区**：只看端到端答对率，不拆检索和生成，导致不知道该改哪一层。

### Q16 — 参考回答要点

- **查询改写 + 时间解析**："上个季度"必须先结合当前日期解析成具体季度（如 "Q3 2025"），并补上同义词（revenue / earnings / 营收）。
- **Metadata filtering**：限定 `doc_type = 财报`、`period = Q3 2025`，把 200 万缩小到几十个 chunk；不加过滤，"收入策略""收入预测"等语义相近的 chunk 会挤占 top-k，还可能召回往年财报。
- **Hybrid search**：BM25 抓 "Q3"、"2025"、"revenue" 这类精确串，向量检索抓 "earnings ≈ revenue" 的语义改写；用 RRF 融合，候选取 top-50。
- **Reranker**：cross-encoder 对 50 个候选精排，留 top-5。
- **Parent-child**：命中的小块（含数字的那一句）返回其所在的整段，保证模型看到"这是 Q3 2025 的总收入、同比增长 23%"等上下文，不会把分部收入当成总收入。
- **生成与校验**：prompt 要求只依据上下文作答并引用来源；对数字做一致性检查（Q10 的思路）。
- 加分点：多跳问题（"哪个团队满意度提升最大"）需要**查询分解**，分别检索每个团队的数据再汇总，单次检索无法解决。

### Q17 — 参考回答要点

- **有用的场景**：查询很短、很口语、与文档用词差异大（问题空间 vs 答案空间），而 LLM 对领域足够熟悉，能写出"用词像真文档"的假想答案。
- **有害的场景**：
  - LLM 不懂领域或语料是私有知识，假想答案会编造错误的实体和数字，把检索引向错误方向（本节模板版本就是极端例子，见 Q12）；
  - 查询本来就很精确（错误码、型号），改写反而稀释了关键词；
  - 对时效性强的问题，LLM 的先验可能过时。
- **延迟**：讲义估计 HyDE 多一次 LLM 调用，增加 500–2000ms。预算紧时：只对"首轮检索置信度低"（如 reranker 最高分低于阈值）的查询触发 HyDE；用小模型生成假想答案；把原查询和假想答案的检索结果用 RRF 融合，而不是只用其一；对高频查询缓存改写结果。
- 加分点：多查询（multi-query）、step-back prompting 是同一类技术，代价相似；讲义提到的 HyDE 论文是 Gao 等 2022 "Precise Zero-Shot Dense Retrieval without Relevance Labels"。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 06 RAG（检索增强生成）](../../06-rag/docs/zh.md)：本节在其 chunk → embed → top-k → prompt 的基础流水线上做增强。
- [阶段 11 · 04 Embeddings 与向量表示](../../04-embeddings/docs/zh.md)：向量检索与 bi-encoder 的基础。
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../../05-nlp-foundations-to-advanced/02-bag-of-words-tfidf/docs/zh.md)：本节代码用 TF-IDF 充当"向量检索"。
- [阶段 05 · 14 信息检索与搜索](../../../05-nlp-foundations-to-advanced/14-information-retrieval-search/docs/zh.md)：BM25、倒排索引等经典 IR 知识。
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../../05-nlp-foundations-to-advanced/23-chunking-strategies-rag/docs/zh.md)：讲义注明六种 chunking 算法在那一节详细展开。

### 本节被哪些后续内容用到
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../10-evaluation/docs/zh.md)：faithfulness、LLM-as-judge 等更完整的评估方法。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)：RAG 评估框架。
- [阶段 12 · 24 多模态 RAG 与跨模态检索](../../../12-multimodal-ai/24-multimodal-rag-cross-modal/docs/zh.md)：把检索扩展到图像等模态。
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../../19-capstone-projects/65-hybrid-retrieval-bm25-dense/docs/zh.md)、[阶段 19 · 66 基于 Cross-Encoder 的 Reranker](../../../19-capstone-projects/66-reranker-cross-encoder/docs/zh.md)、[阶段 19 · 67 查询改写：HyDE、多查询与查询分解](../../../19-capstone-projects/67-query-rewriting-hyde/docs/zh.md)：综合项目中逐一实现本节技术。
- [阶段 19 · 68 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性](../../../19-capstone-projects/68-rag-eval-precision-recall/docs/zh.md)、[阶段 19 · 69 端到端 RAG 系统](../../../19-capstone-projects/69-end-to-end-rag-system/docs/zh.md)：完整的 RAG 评估与系统。

### 延伸关键词
`BM25 / BM25F` · `SPLADE` · `Reciprocal Rank Fusion` · `cross-encoder` · `ColBERT / late interaction` · `HyDE` · `multi-query / step-back` · `query decomposition` · `parent-document retriever` · `contextual retrieval` · `metadata pre-filtering` · `Recall@k / MRR / nDCG` · `faithfulness / NLI` · `GraphRAG` · `Self-RAG`
