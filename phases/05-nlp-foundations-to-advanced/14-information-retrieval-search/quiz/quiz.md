# 测验 · 信息检索与搜索（Information Retrieval and Search）

> **阶段 05 · NLP 从基础到进阶 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 稀疏检索 BM25 | 基于倒排索引，按 TF（带饱和）、IDF、文档长度归一化打分；对精确词（法条编号、产品码、报错信息、实体名）很准，对同义改写无能为力 |
| 2 | BM25 的两个超参 | `k1`（默认 1.5）控制词频饱和，越大越看重重复；`b`（默认 0.75）控制长度归一化，0 = 忽略长度，1 = 完全归一化 |
| 3 | 稠密检索（bi-encoder） | query 与文档**分别**编码成向量，做最近邻搜索；能抓语义改写，但会漏掉只差一个字符的精确匹配；L2 归一化后点积 = 余弦 |
| 4 | 融合 RRF | `score(d) = Σ 1/(k + rank)`，只用名次、不用原始分数，因此不需要把 BM25 和余弦校准到同一量纲；`k=60` 是原论文默认值 |
| 5 | Cross-encoder 重排 | query 与文档**拼在一起**打分，比 bi-encoder 准但每对都要算一次，只对融合后的 top-30 跑，保留 top-5 |
| 6 | 三路检索 | BM25 + dense + learned-sparse（如 SPLADE）在 2026 基准上优于两路，但需要 learned-sparse 索引基础设施；多数团队"两路 + 重排"是甜点 |
| 7 | 检索评估指标 | Recall@k（RAG 最重要）、MRR（首个相关文档名次倒数的均值）、nDCG@k（考虑相关度分级） |
| 8 | 生产 RAG 经验 | 讲义称约 80% 的 RAG 失败源自数据摄入和切块；parent-doc 模式；`k_rerank=3` 通常最优；HyDE 查询扩展；上下文预算 < 8K；所有组件做版本管理 |

### 核心技能（能动手做到）

- [ ] 从零实现 `BM25`（df 统计、IDF、带 `k1`/`b` 的打分、top-k 排序），并能手算单个词的贡献
- [ ] 解释并验证 `k1=0`、`b=0`、`k1→∞` 时 BM25 分别退化成什么
- [ ] 实现 `reciprocal_rank_fusion`，能手算两个排名列表融合后的分数与顺序
- [ ] 指出本节 demo 里"零分文档也参与 RRF"的问题，并修复
- [ ] 实现 Recall@k 和 MRR，在一组带标注的查询上对比 BM25-only、dense-only、hybrid
- [ ] 能根据语料规模（1k / 100k / 10M+）给出检索栈选型，并说明为什么 reranker 只跑 top-30

---

## 二、基础自测（选择题）

**Q1.** BM25 中把 `b` 从 0.75 改成 0，效果是：

- A. 关闭 IDF，所有词同等权重
- B. 不再考虑文档长度，长文档不会因为"长"而被惩罚
- C. 词频不再饱和，重复次数线性增加分数
- D. 所有文档分数变为 0

**Q2.** 用户经常搜索 `ERR_CONN_RESET_4012`、`SKU-88213` 这类字符串。只用 dense 检索最可能出现什么问题？

- A. 延迟过高，无法上线
- B. 精确标识符在 embedding 空间里被"抹平"，只差一个字符的码可能被当成相近，真正匹配的文档反而排不上来
- C. 无法处理英文
- D. 召回率一定是 100%，但精确率低

**Q3.** RRF 只使用名次（rank）而不使用原始分数，主要原因是：

- A. 排序比加法更快
- B. BM25 分数和余弦相似度量纲完全不同，直接相加需要校准，用名次可以绕开这个问题
- C. RRF 要求输入必须是概率
- D. 原始分数在 RRF 中会导致除零

**Q4.** 关于 bi-encoder 与 cross-encoder，下列说法**正确**的是：

- A. cross-encoder 可以离线预先计算所有文档的向量，所以检索更快
- B. bi-encoder 把 query 和文档拼在一起编码，所以更准
- C. bi-encoder 的文档向量可以离线算好，查询时只需编码 query；cross-encoder 必须对每个 (query, doc) 对跑一次模型
- D. 两者精度相同，只是名字不同

**Q5.** 对 RAG 的检索器来说，讲义认为**最重要**的指标是：

- A. BLEU
- B. 每秒查询数（QPS）
- C. Recall@k
- D. 索引大小

**Q6.** 关于"parent-doc 模式"，下列描述正确的是：

- A. 只对父文档做 embedding，不切块
- B. 检索时用小的子块保证精度；当同一父段落的多个子块被召回时，换成整个父段落送给 reader，保留上下文
- C. 永远返回语料中最长的文档
- D. 把所有子块拼接成一个超长上下文

**Q7.** 你的系统把 reranker 之后保留的块数从 `k=3` 调到 `k=8`，答案质量明显变好。按讲义的经验，这最可能说明：

- A. LLM 太弱，需要换更大的模型
- B. reranker 表现不佳，没能把真正相关的块排进前 3
- C. 一切正常，`k` 越大越好
- D. BM25 的 `k1` 设置错了

**Q8.** 关于 HyDE（Hypothetical Document Embeddings），说法正确的是：

- A. 需要先在领域数据上微调 embedding 模型
- B. 让 LLM 先根据问题生成一个"假想答案"，用它的 embedding 去检索，弥补短问题和长文档之间的措辞差距
- C. 是一种倒排索引压缩算法
- D. 用来替代 cross-encoder 重排

---

## 三、动手 / 代码题

**Q9.** 用本节的 `reciprocal_rank_fusion`（`k=60`）融合下面两个排名，写出输出（保留 4 位小数即可），并说明 A 为什么能排在 C 前面：

```python
r1 = [(9, 'A'), (8, 'B'), (7, 'C')]        # 例如 BM25 的结果：(score, doc_id)
r2 = [(0.9, 'C'), (0.8, 'A'), (0.1, 'D')]  # 例如 dense 的结果
print(reciprocal_rank_fusion([r1, r2]))
```

**Q10.** 运行本节 `main.py`，RRF 融合结果如下（真实输出）：

```text
RRF fused:
  0.0328  Cheating someone to obtain money is a criminal offence in most jurisdictions.
  0.0323  Fraud refers to wrongful or criminal deception intended to result in financial gain.
  0.0317  Section 420 of the Indian Penal Code covers cheating and dishonest inducement.
  0.0312  The first iPod was released by Apple in 2001.
  0.0308  Android launched in 2008 as Google's mobile smartphone operating system.
```

有同学据此说"hybrid 把 Section 420 找回来了，排第 3"。这个结论对吗？请从 `BM25.rank` 和 `fake_dense_rank` 的实现找原因，并给出修复。

**Q11.** 下面是 `BM25.score` 的核心循环。不运行代码，回答：(1) `k1=0` 时每个命中词贡献多少？(2) 某个词的词频 `f → ∞` 时，它的贡献上界是多少？(3) 查询 `"money money"` 的得分是 `"money"` 的几倍？这样合理吗？

```python
        for term in q_tokens:
            f = freq.get(term, 0)
            if f == 0:
                continue
            num = f * (self.k1 + 1)
            den = f + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
            total += self.idf(term) * num / den
```

**Q12.** 讲义练习 2 要求计算 MRR。请实现 `recall_at_k(ranked, relevant, k)` 和 `mrr(ranked, relevant)`，其中 `ranked` 是 `BM25.rank` 返回的 `[(score, doc_idx), ...]`，`relevant` 是相关文档下标的集合；并说明在本节 demo 中，若把 Section 420（下标 4）当作唯一相关文档，BM25 的 MRR 为何"看起来"是 1/3。

---

## 四、面试高频题

**Q13.**（基础必考）写出 BM25 的打分公式，解释 TF 饱和、IDF、长度归一化各自解决什么问题。为什么本节的 IDF 写成 `log(1 + (N - n + 0.5)/(n + 0.5))`，而不是经典的 `log((N - n + 0.5)/(n + 0.5))`？

**Q14.**（原理深挖）比较 bi-encoder、cross-encoder 和 ColBERT 式 late interaction：计算方式、能否离线建索引、精度与延迟。为什么工业界是"bi-encoder 召回 + cross-encoder 重排"的两阶段？

**Q15.**（原理深挖）RRF 和加权分数融合（如 `α·norm(bm25) + (1-α)·cos`）各有什么优缺点？RRF 中的 `k` 调大调小分别有什么影响？

**Q16.**（场景设计）为一个电商客服知识库（50 万文档，大量商品型号和错误码，也有大量口语化提问）设计检索栈，并给出评估方案和延迟预算。

**Q17.**（工程实践）RAG 上线后答案质量差，团队已经换了三次 LLM 都没用。你会怎么排查检索侧？列出你会依次检查和尝试的东西。

---

## 五、参考答案与解析

### Q1 — 答案：B

长度归一化项是 `1 - b + b·dl/avgdl`。`b=0` 时它恒等于 1，文档长度不再影响分数。A 是 IDF 的事；C 对应 `k1→∞`；D 显然错。

### Q2 — 答案：B

讲义："dense 会漏掉只差一个字符的精确关键词匹配"；skill 里也要求"对含实体名、错误码、SKU 的语料，除非有证据，否则拒绝推荐纯 dense"。BM25 在这类精确匹配上恰好最强，这就是 hybrid 的动机。

### Q3 — 答案：B

BM25 分数可能是 0～十几，余弦在 [-1, 1]，分布还随查询变化。直接相加必须做归一化 / 校准，而 RRF 用 `1/(k + rank)` 只看名次，天然对量纲不敏感。

### Q4 — 答案：C

bi-encoder 分别编码 query 和文档，所以文档向量可以离线算好放进 FAISS / 向量库，查询时只编码一次 query；cross-encoder 把 (query, doc) 拼在一起过模型，能做 token 级交互因而更准，但无法预计算，每个候选都要跑一次——所以只对 top-30 用。A、B 把两者说反了。

### Q5 — 答案：C

"reader 无法回答没被检索到的段落"，Recall@k 是 RAG 端到端准确率的上界。

### Q6 — 答案：B

讲义原文：检索小的 child 块保证精度；当同一 parent 的多个 child 出现时，换入 parent 块以保留上下文，"无需重训即可稳定提升答案质量"。

### Q7 — 答案：B

讲义："`k_rerank=3` 通常最优……如果 `k=8` 仍比 `k=3` 好，说明 reranker 表现不佳。"多塞块会增加 token 成本和延迟；正确做法是改进 reranker（换模型、领域微调、调阈值），而不是无限加大 k。

### Q8 — 答案：B

HyDE：先根据 query 生成一个假想答案，embed 它再检索，弥合"短问题 vs 长文档"的措辞差距，讲义称是"无需训练的免费精度提升"。不需要微调（A 错），也不替代重排（D 错）。

### Q9 — 参考答案

```text
[(0.0325, 'A'), (0.0323, 'C'), (0.0161, 'B'), (0.0159, 'D')]
```

（完整精度：`0.03252247…`、`0.03226645…`、`0.01612903…`、`0.01587301…`）

手算（`rank` 从 0 开始，公式里用 `rank + 1`）：

| 文档 | r1 名次 | r2 名次 | RRF 分数 |
|------|--------|--------|---------|
| A | 1 | 2 | 1/61 + 1/62 = 0.03252 |
| C | 3 | 1 | 1/63 + 1/61 = 0.03227 |
| B | 2 | — | 1/62 = 0.01613 |
| D | — | 3 | 1/63 = 0.01587 |

A 在两个列表里都排得靠前（第 1、第 2），C 一次第 1、一次第 3。RRF 奖励"在多个检索器里都稳定靠前"的文档；而且只在一个列表中出现的 B、D，分数大约只有两路都出现的一半——这就是融合的价值。注意 r1 的原始分 9、8、7 和 r2 的 0.9、0.8、0.1 完全没有被使用。

### Q10 — 参考答案

结论**不对**。Section 420 在 BM25 和 fake-dense 中的分数都是 **0.000**——它和查询没有任何共同词。它排第 3 只是**并列零分时的排序副作用**：

- `BM25.rank` 和 `fake_dense_rank` 都返回 `(score, idx)` 元组并 `sort(reverse=True)`。分数相同时比较第二项 `idx`，**下标大的排前面**。零分文档里 Section 420 的下标是 4，最大，所以总在零分组的第一个。
- 两个排名函数都会把零分文档塞进 top-5，于是 RRF 给这些"完全不相关"的文档也加了 `1/(60+3)` 等分数。

修复：零分文档不进入排名。

```python
sparse = [(s, i) for s, i in bm25.rank(query, top_k=5) if s > 0]
dense = [(s, i) for s, i in fake_dense_rank(query, corpus, top_k=5) if s > 0]
fused = reciprocal_rank_fusion([sparse, dense])[:5]
# 实际运行：[(0.0328, 6), (0.0323, 5)] —— 只剩真正有词面重叠的两篇
```

更深一层：这个查询（"someone lies to get money"）和 Section 420（"cheating and dishonest inducement"）**没有共同词汇**，这正是讲义开头的例子。本节的 `fake_dense_rank` 只是 Jaccard + 子串扩展，本质仍是词面匹配，所以它也找不到；需要真正的语义 embedding（或 HyDE 生成"cheating / fraud"之类的措辞）才能把它召回。

### Q11 — 参考答案

(1) `k1=0`：`num = f·1`，`den = f + 0 = f`，比值为 1，每个命中词只贡献 `idf(term)`。BM25 退化为"**命中词的 IDF 之和**"（二值出现）。本节 demo 中 Cheating 文档的分数会从 4.307 变成 `1.674 + 1.163 + 1.674 = 4.511`（someone、to、money 的 IDF 之和，已实际运行验证）。

(2) `f → ∞` 时 `num/den → k1 + 1`，贡献上界是 `idf · (k1 + 1)`（默认 `2.5·idf`）。这就是"饱和"：一个词出现 2 次比 1 次有用，但出现 100 次并不比 10 次有用多少，防止关键词堆砌刷分。

(3) **2 倍**。`q_tokens = tokenize(query)` 是列表、没有去重，循环会把 `money` 算两次（实测 3.197 vs 1.598）。是否合理见仁见智：经典 BM25 有一个查询词频因子（常记作 `k3`），重复的查询词确实应该加权，但应当也是饱和的而非线性翻倍；而第 13 节的玩具打分用了 `set` 去重。工程上要**明确选择**一种并写在注释里，否则用户把关键词重复输入几次就能显著改变排序。

### Q12 — 参考答案

```python
def recall_at_k(ranked, relevant, k):
    return 1.0 if any(idx in relevant for _, idx in ranked[:k]) else 0.0


def mrr(ranked, relevant):
    for r, (_, idx) in enumerate(ranked, start=1):
        if idx in relevant:
            return 1.0 / r
    return 0.0


# 对一组查询求平均即为 Recall@k / MRR：
# sum(mrr(bm25.rank(q, 10), rel) for q, rel in labeled) / len(labeled)
```

本节 demo：`bm25.rank(query, 7)` 中 Section 420 排第 3，所以 `mrr = 1/3`（实际运行得到 0.333）。但它的分数是 0，排第 3 只是并列零分时按下标倒序的结果（见 Q10）。这说明**评估代码也要处理并列和零分**：常见做法是零分文档视为"未召回"，或在并列时取并列区间的平均名次 / 最差名次，否则指标会被排序实现的偶然性"刷高"。

### Q13 — 参考回答要点

- 公式：`score(q, d) = Σ_{t∈q} IDF(t) · f(t,d)·(k1+1) / ( f(t,d) + k1·(1 - b + b·|d|/avgdl) )`
- 三个部件：
  - **TF 饱和**（`k1`）：词频收益递减，上界 `(k1+1)·IDF`，防止关键词堆砌；
  - **IDF**：罕见词更有区分度（`the` 几乎无用，`iphone` 很有用）；
  - **长度归一化**（`b`、`avgdl`）：长文档天然更容易命中，要按相对平均长度打折。
- IDF 写法：经典 Robertson–Spärck Jones 形式 `log((N-n+0.5)/(n+0.5))` 在 `n > N/2` 时为**负数**，出现在超过一半文档中的词会让分数**下降**，这很反直觉；加 1 后（Lucene / Elasticsearch 采用的变体）IDF 恒为正。本节代码采用的就是加 1 的版本。
- 加分点：BM25 的打分只依赖 query 中出现的词，所以可以用**倒排索引**只遍历包含这些词的文档（讲义：百万文档 sub-10ms）；本节代码对每个文档都重新 `Counter(doc)`、全量打分，是 O(N·L) 的教学实现。

### Q14 — 参考回答要点

| | bi-encoder | cross-encoder | late interaction（ColBERT） |
|--|-----------|---------------|---------------------------|
| 计算 | query、doc 各自编码成一个向量，点积 / 余弦 | (query, doc) 拼接后过整个模型，输出一个相关度分数 | query、doc 各自编码成**每个 token 一个向量**，按 token 做 MaxSim 再求和 |
| 离线索引 | 可以（文档向量预计算） | 不行 | 可以（存 token 级向量，存储更大） |
| 精度 | 中 | 高（token 级全交互） | 介于两者之间，接近 cross-encoder |
| 延迟 | 低（ANN 检索） | 高（每对一次前向） | 中 |

- 两阶段的原因：召回阶段要在百万级文档里找候选，只能用可预建索引的 bi-encoder / BM25；精排阶段只有几十个候选，可以负担 cross-encoder 的高成本。讲义：rerank 只跑 top-30、保留 top-5，skill 中提示 rerank 在 top-30 上增加约 30–100ms。
- 加分点：讲义"最佳质量前沿"一栏就是"三路检索 + ColBERT late-interaction 重排"。

### Q15 — 参考回答要点

- **RRF**：只用名次，无需校准；对异常分数鲁棒；实现简单，是默认选择。缺点是丢失了"分差"信息——第 1 名远超第 2 名和两者几乎相同，RRF 一视同仁。
- **加权分数融合**：能利用分数大小，当已知某一路信号在领域里占主导时效果更好（讲义："当你知道某个信号在你的领域占主导时可以用加权融合"）；缺点是需要对两路分数做归一化（min-max、z-score），且 `α` 需要调参，分数分布随查询漂移时不稳定。
- **RRF 的 k**：`1/(k + rank)`。`k` 越大，名次之间的差距越被"压平"（第 1 名和第 10 名分数接近）；`k` 越小，头部名次主导结果。`k=60` 是原论文默认值，讲义说"很少需要调"。
- 加分点：能举例说明 RRF 会奖励"多路都靠前"的文档，而只在一路中排第 1 的文档可能输给两路都排第 2 的文档。

### Q16 — 参考回答要点

- **规模**：50 万文档落在讲义"100k–10M"档：FAISS / pgvector 做 dense，Elasticsearch / OpenSearch 做 BM25，**并行**执行。
- **检索栈**：hybrid（BM25 + dense + RRF）+ cross-encoder 重排。BM25 负责型号、错误码的精确匹配（这类语料讲义明确反对纯 dense）；dense 负责"手机充不进电怎么办"这种口语化表达。查询里检测到型号 / 错误码模式时，可以提高 BM25 的权重或做精确过滤。
- **编码器**：英文可用 `all-MiniLM-L6-v2` 起步，追求质量用 `bge-large-en-v1.5` / `e5-large-v2`；多语言用 `paraphrase-multilingual-MiniLM-L12-v2`（均为讲义提到的模型）。有标注数据时用 MultipleNegativesRankingLoss 做领域微调。
- **延迟预算**（依讲义量级）：BM25 < 10ms，dense 50–200ms（两者并行），rerank top-30 约 30–100ms，总体控制在几百毫秒内。
- **评估**：先建带标注的查询集（真实日志抽样，覆盖"型号类"与"口语类"），以 Recall@10 为主指标、MRR 为辅；先测 BM25-only / dense-only 基线，再测 hybrid、再测 + rerank，每一步都要相对基线有可度量的提升。
- 常见误区：只看端到端答案质量而不单独测检索召回。

### Q17 — 参考回答要点

按讲义的"来之不易的经验"依次排查：

1. **先测检索召回**：对失败问题标注正确段落，看是否在 top-k 里。讲义：大部分 RAG 提升来自更好的检索，而不是模型微调；约 80% 的失败源于摄入和切块。
2. **检查摄入与切块**：表格、代码、嵌套标题有没有被固定长度切碎；改用句子感知切块，技术文档考虑语义 / LLM 切块；尝试 parent-doc 模式。
3. **对比 sparse 与 dense 的排名**：一个找到、另一个没找到 ⇒ 词汇不匹配（补上缺的那一路，即做 hybrid）或语义歧义（换更好的 embedding / 加 reranker）。
4. **查询侧**：短问题对长文档措辞差距大时上 HyDE / 查询扩展。
5. **重排与上下文预算**：`k_rerank` 从 3 起步；若 k 越大越好，说明 reranker 不行；上下文持续顶到 8K 说明阈值太松。
6. **版本化与 CI**：prompt、切块规则、embedding 模型、reranker 全部版本化；CI 上用 faithfulness、context precision、未回答率做闸门。
- 加分点：强调"reader 修不好 retriever 漏掉的东西"，换 LLM 前必须先有检索召回基线。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../02-bag-of-words-tfidf/docs/zh.md)：BM25 是 TF-IDF 的"饱和 + 长度归一化"升级版。
- [阶段 05 · 04 GloVe、FastText 和 Subword Embeddings](../../04-glove-fasttext-subword/docs/zh.md)：稠密表示的基础。
- [阶段 01 · 14 范数与距离](../../../01-math-foundations/14-norms-and-distances/docs/zh.md)：余弦、点积与 L2 归一化的关系。

### 本节被哪些后续内容用到
- [阶段 05 · 13 问答系统](../../13-question-answering/docs/zh.md)：RAG 的 reader 半边，本节是它的 retriever 半边。
- [阶段 05 · 22 Embedding 模型深度剖析](../../22-embedding-models-deep-dive/docs/zh.md)：dense 编码器的选型与训练。
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../23-chunking-strategies-rag/docs/zh.md)："80% 的失败来自切块"的系统展开。
- [阶段 11 · 07 高级 RAG](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：HyDE、重排、查询改写等工程技巧。
- [阶段 12 · 23 ColPali 视觉原生 RAG](../../../12-multimodal-ai/23-colpali-vision-native-rag/docs/zh.md)：late interaction 在多模态检索中的应用。
- [阶段 19 · 65 混合检索 BM25 + Dense](../../../19-capstone-projects/65-hybrid-retrieval-bm25-dense/docs/zh.md)、[阶段 19 · 66 Cross-Encoder 重排](../../../19-capstone-projects/66-reranker-cross-encoder/docs/zh.md)、[阶段 19 · 67 查询改写与 HyDE](../../../19-capstone-projects/67-query-rewriting-hyde/docs/zh.md)、[阶段 19 · 68 RAG 评估](../../../19-capstone-projects/68-rag-eval-precision-recall/docs/zh.md)：综合项目逐个落地本节组件。

### 延伸关键词
`倒排索引` · `Okapi BM25 / BM25F` · `SPLADE` · `ColBERT / MaxSim` · `FAISS (HNSW / IVF-PQ)` · `MultipleNegativesRankingLoss` · `HyDE` · `parent-document retriever` · `nDCG` · `RRF`
