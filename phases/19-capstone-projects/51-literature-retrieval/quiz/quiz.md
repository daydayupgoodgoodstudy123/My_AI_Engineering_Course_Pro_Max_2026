# 测验 · 文献检索（Literature Retrieval）

> **阶段 19 · 综合项目 · 第 51 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要检索 | 假设便宜，"是否已经有人证明过"才贵；检索是研究循环中最便宜的一环，应在启动沙箱跑实验前先做 |
| 2 | 两遍检索 | BM25 词法检索抓"用词相同"的论文；引用图遍历补上"用词不同的奠基论文"和"引用锚点的后续论文" |
| 3 | `Paper` 记录 | `id`、`title`、`abstract`、`year`、`authors`、`references`（我引用谁）、`citations`（谁引用我）、`source`；后两者构成有向引用图 |
| 4 | BM25 公式 | `idf = ln((N − df + 0.5)/(df + 0.5) + 1)`；`tf_norm = f(k1+1)/(f + k1(1 − b + b·dl/avgdl))`；分数是查询词上 `idf × tf_norm` 之和；默认 `k1 = 1.5`、`b = 0.75` |
| 5 | k1 与 b 的含义 | k1 控制词频饱和（出现越多收益递减），b 控制文档长度归一化（长文档被惩罚的程度） |
| 6 | 引用图 BFS | 以 BM25 前 k 名为种子，沿 references 与 citations 双向做广度优先搜索，记录最短跳数，最多 2 跳 |
| 7 | 跳数上限 | 1 跳太浅，3 跳在连通图上结果爆炸且容易跑题；代码把 `max_hops` 强制截到 ≤ 2 |
| 8 | 合并打分 | `final = 0.5·bm25/max_bm25 + 0.3·graph_score + 0.2·recency`；graph_score：种子 1.0、1 跳 0.6、2 跳 0.3；recency 在语料年份上线性 0→1 |
| 9 | 去重 | 两遍结果按 paper id 合并（集合并），每篇只出现一次 |
| 10 | 客户端封装 | 两个 mock API（arXiv 无引用字段，Semantic Scholar 有）藏在同一个客户端后面，真实端点接入时上游调用点不变 |

### 核心技能（能动手做到）

- [ ] 不用任何库从零实现 BM25 的建索引与打分，并能手算一篇文档的分数
- [ ] 解释 idf 公式里 `+0.5` 与 `+1` 的作用，以及 df = N 时 idf 为什么接近 0 而不是负数
- [ ] 用 `deque` 写出带跳数上限的多源 BFS，返回每个节点的最短跳数
- [ ] 读懂 `final_score` 的三项组成，并能逐篇手算 demo 的结果
- [ ] 指出 mock 语料与打分设计导致的"平分"和"年代偏置"问题
- [ ] 给分词器加简单词干化，让 "sparse" 能匹配 "sparsity"
- [ ] 把两个 API 客户端的结果按 id 合并，并处理字段缺失

---

## 二、基础自测（选择题）

**Q1.** 讲义认为只做关键词检索不够，需要再加一遍引用图遍历。它要补上的两种情况是：

- A. 奠基论文用了不同的词汇（例如查 "sparse attention" 漏掉 "block selection in transformer routing"）；以及引用某个已知锚点的后续论文
- B. 摘要太短的论文，以及作者名拼写错误的论文
- C. 非英文论文，以及没有摘要的论文
- D. 年代太久远的论文，以及预印本

**Q2.** 语料 N = 100 篇，词 `attention` 出现在 20 篇中。按代码的 `BM25Index.idf`，它的 idf 约为：

- A. 1.386
- B. 2.303
- C. 1.595
- D. 0.005

**Q3.** 在本节语料上分别搜索 `"attention sparsity head pruning"` 与 `"sparse attention"`，对 p001 的 BM25 分数分别是 8.49 与 2.65。后者低得多的原因是：

- A. `"sparse attention"` 只有两个词，BM25 会除以查询长度
- B. `sparse` 是停用词被过滤了
- C. b = 0.75 惩罚了短查询
- D. 分词器不做词干化，`sparse` 与 `sparsity` 是不同的词，只有 `attention` 命中

**Q4.** demo 中 p005：BM25 为本次最大值，是种子（`graph_distance = 0`），年份 2022（语料年份范围 2018–2025）。按默认权重，它的 `final_score` 是：

- A. 1.0
- B. 0.9143
- C. 0.8571
- D. 0.8

**Q5.** demo（`top_k_lexical=5, max_hops=2`，查询 `"attention sparsity head pruning"`）返回 `hit_count = 24`。这 24 篇的构成是：

- A. BM25 命中的 24 篇
- B. 5 篇种子 + 19 篇 1 跳邻居
- C. attention 主题的 20 篇（种子与 1 跳）+ p086（1 跳，跨主题引用 p001）+ p021、p081、p082（2 跳）
- D. 全部 100 篇中得分大于 0.5 的论文

**Q6.** 关于 `RetrievalClient.search` 与两个 mock API 客户端的关系，与代码相符的是：

- A. 构造函数接收并保存了 `ArxivMockClient` 与 `SemanticScholarMockClient`，但 `search` 从不调用它们；BM25 与引用图直接由传入的 `corpus` 构建，`_merge_paper` 也没有被使用
- B. `search` 先调用 arXiv 拿摘要，再调用 Semantic Scholar 补引用，最后按 id 合并
- C. `search` 只调用 Semantic Scholar
- D. 两个客户端在 `search` 中被并行调用

**Q7.** `RetrievalConfig(max_hops=5).max_hops` 与 `RetrievalConfig(max_hops=-1).max_hops` 分别是多少？后者在 `expand` 中会产生什么效果？

- A. 5 和 −1；−1 会无限扩展
- B. 2 和 0；与 0 跳相同
- C. 5 和 0；与 0 跳相同
- D. 2 和 −1；`__post_init__` 只截断上限，−1 不会被修正，但因为 `d >= max_hops` 恒成立，效果与 0 跳相同（只返回种子）

**Q8.** demo 中 p001 被同主题 18 篇和 1 篇跨主题论文引用，是最核心的锚点论文，却只排第 11 名。主要原因是：

- A. p001 的 BM25 分数最低
- B. p001 是 2018 年的论文，`recency_score = 0`，在 20 篇 BM25 相同的论文里被"新论文加分"压了下去；而打分里没有任何"被引次数"信号
- C. p001 不是种子
- D. p001 的 `graph_distance` 是 2

---

## 三、动手 / 代码题

**Q9.** 手算 BM25。已知：N = 100，avgdl = 37.8；p001 的 `title + abstract` 分词后长度 dl = 38，其中 `attention`、`sparsity` 各出现 3 次，`head`、`pruning` 各出现 1 次；这 4 个词的 df 都是 20。

1. 计算 f = 3 与 f = 1 时的 `tf_norm`，以及 p001 对查询 `"attention sparsity head pruning"` 的 BM25 总分。
2. 运行代码会发现 attention 主题的 20 篇论文 BM25 分数**完全相同**。为什么？在这种情况下，`top_k_lexical=5` 选出的种子是哪 5 篇、由什么决定？
3. 这对"检索质量"测试意味着什么？

**Q10.** 讲义的架构图是"query → arXiv / S2 两个客户端 → load corpus → BM25 + 引用图"，讲义还说 "The retrieval client unions on id"。

1. 用一个"间谍"（spy）子类证明 `RetrievalClient.search` 实际上没有调用两个客户端。
2. 写 `load_corpus_from_clients(query, arxiv, s2)`：分别调用两个客户端的 `search`，按 id 合并，引用字段以 S2 为准，并把 `source` 标为 `"merged"`。
3. 用合并后的子语料构造 `RetrievalClient` 再跑 demo 查询，`hit_count` 会变成多少？为什么会变？

**Q11.** 打分改进：

1. 写 `rerank_with_citations(result, w_cite=0.2)`：给每篇论文加上 `w_cite × log(1 + 被引数)/log(1 + 最大被引数)`，重新排序。demo 的前 4 名变成什么？
2. 另一种做法是把 `w_recency` 设为 0（`w_bm25 = 0.7`）。前 6 名又是什么？这暴露了什么新问题？
3. 结合"检查假设是否已被证明"这个用途，讨论 recency 权重应该怎么设。

**Q12.** 词干化：

1. 写一个最小的后缀剥离词干器 `stem(tok)`（依次尝试去掉 `ities`、`ity`、`ing`、`es`、`s`、`e`，且剩余长度 ≥ 3），给出 `sparse`、`sparsity`、`pruning`、`heads`、`routing`、`adapters` 的结果。
2. 让索引与查询都使用它，`"sparse attention"` 对 p001 的 BM25 从 2.654 变成多少？
3. 这种简单规则有什么副作用？

---

## 四、面试高频题

**Q13.**（基础必考）写出 BM25 的公式，并解释 k1、b、idf 各自的作用。它相比 TF-IDF 改进了什么？

**Q14.**（原理深挖）词法检索（BM25）、稠密检索（embedding）、引用图扩展各自擅长什么、漏掉什么？如何把多路结果融合？

**Q15.**（工程实践）把这两个 mock 客户端换成真实的 arXiv 与 Semantic Scholar API，你需要处理哪些工程问题？

**Q16.**（场景设计）研究 agent 生成了一个假设（第 50 节的输出），要判断"这个假设是否已经被前人证明或证伪"。请设计从假设到结论的完整检索流程。

**Q17.**（追问型）你怎么评估这个检索模块的好坏？如何决定 `top_k_lexical`、`max_hops` 和三项权重？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："It misses two cases. The first is when the foundational paper uses different vocabulary... The second is when the relevant paper is a follow up that cites a known anchor; it is more efficient to find the anchor and walk forward than to brute force the abstract pool." B、C、D 都不是讲义给出的理由。注意 C 中"非英文论文"确实是本节分词器（`[a-z0-9]+`）的盲区，但引用图遍历的动机不是它。

### Q2 — 答案：C

`ln((100 − 20 + 0.5)/(20 + 0.5) + 1) = ln(80.5/20.5 + 1) = ln(4.927) ≈ 1.5947`（代码实测 1.5947）。A 是 `ln(80/20)`（经典 Robertson–Spärck Jones idf 去掉平滑），B 是 `ln(10)`，D 是 df = 100 时的值——`perplexity` 这类出现在所有摘要里的词 idf 只有 0.005。公式中 `+1` 保证 idf 恒为正（这是 Lucene 等实现采用的变体），即使 df > N/2 也不会给文档扣分。

### Q3 — 答案：D

`tokenise` 只是小写 + 按非字母数字切分，没有词干化（讲义："It is not stemmed. A production system would swap in a small stemmer"）。`sparse` 在语料中不存在，只有 `attention` 贡献分数（2.654 = 1.5947 × 1.6645）。A 错，BM25 不除以查询长度；B 错，代码没有停用词表；C 错，b 作用于**文档**长度。讲义自己举的例子正是"查 sparse attention 会漏掉……"，而本节的 mock 语料用的词恰好是 `sparsity`。

### Q4 — 答案：B

`bm25_norm = 8.4904/8.4904 = 1`，`graph_score = 1.0`（种子），`recency = (2022 − 2018)/(2025 − 2018) = 4/7 ≈ 0.5714`。`final = 0.5×1 + 0.3×1 + 0.2×0.5714 = 0.9143`，与运行输出一致。A 假设 recency 为 1；C 是 p003（2020，recency 0.2857）的分数；D 是 p001（2018，recency 0）的分数。

### Q5 — 答案：C

BM25 种子按 `(−score, id)` 排序，20 篇同分，取 id 最小的 p001–p005。p003–p020 都引用 p001、p002，所以 attention 主题其余 15 篇都在 1 跳内。跨主题边：p086（第 5 主题的第 6 篇）引用 p001，是 1 跳；p086 的参考文献 p081、p082 是 2 跳；p006 引用 p021（第 2 主题的锚点），p006 是 1 跳，所以 p021 是 2 跳。合计 `20 + 1 + 3 = 24`。实测 `max_hops=0` 时 5 篇、`max_hops=1` 时 21 篇。A 错，BM25 只命中 20 篇；B、D 都与代码逻辑不符。

### Q6 — 答案：A

`RetrievalClient.__init__` 保存了 `self._arxiv`、`self._s2`，但 `search` 只用 `self._index`（由 `corpus` 建）和 `self._graph`（由 `corpus` 建）。我们用重写了 `search` 的子类实测，调用 `client.search("attention")` 后记录到的客户端调用次数为 0。`_merge_paper` 方法定义了但没有调用者。讲义架构图与 "unions on id" 的描述和代码不一致（见 Q10）。

### Q7 — 答案：D

```python
    def __post_init__(self) -> None:
        if self.max_hops > 2:
            self.max_hops = 2
```

只截上限，静默改成 2（实测 `max_hops=5` → 2），而且不报警告；负数不处理（实测仍为 −1）。`expand` 中 `if d >= max_hops: continue` 对种子（d = 0）就成立，所以只返回种子。更好的做法是在 `__post_init__` 中对非法值 `raise ValueError`，或者至少记录被截断的事实。

### Q8 — 答案：B

20 篇 attention 论文的 BM25 完全相同（`bm25_norm` 都是 1），种子 graph_score 1.0、1 跳 0.6，最后决定排名的就是 recency。p001 是 2018 年，`final = 0.5 + 0.3 + 0` = 0.8，排第 11；2025 年的 p008 即使只是 1 跳邻居也有 0.88。打分中没有被引次数之类的"权威性"信号。对"判断假设是否已被证明"来说，奠基论文往往更重要，这种年代偏置恰好相反（见 Q11）。A 错，BM25 相同；C、D 错，p001 是种子，距离 0。

### Q9 — 参考答案

1. 长度归一化项 `1 − b + b·dl/avgdl = 0.25 + 0.75 × 38/37.8 = 1.00397`。
   - f = 3：`tf_norm = 3 × 2.5 / (3 + 1.5 × 1.00397) = 7.5/4.506 ≈ 1.6645`
   - f = 1：`tf_norm = 2.5 / (1 + 1.5 × 1.00397) = 2.5/2.506 ≈ 0.9976`
   - 总分：`1.5947 × (1.6645 + 1.6645 + 0.9976 + 0.9976) = 1.5947 × 5.3242 ≈ 8.4904`，与运行输出一致。
   - 注意词频饱和：出现 3 次的贡献只是出现 1 次的 1.67 倍，而不是 3 倍——这就是 k1 的作用。
2. `build_corpus` 用模板生成摘要：同一主题的 20 篇只有 `study {i+1}` 中的数字不同，查询词出现次数和文档长度都完全相同，所以分数相同。`BM25Index.search` 按 `(-score, doc_id)` 排序，种子是 id 最小的 **p001–p005**——由 id 的字典序决定，与论文内容无关。
3. 意味着现有测试（如 `test_top_hit_is_on_topic` 只检查标题含 "Attention Sparsity"）无法验证 BM25 是否把"更相关"的论文排在前面，因为语料里根本没有"更相关"与"不太相关"之分。要测排序质量，需要构造有差异的文档（不同长度、不同词频、带有相关性标注），并用 recall@k、nDCG 等指标评估（见 Q17）。

### Q10 — 参考答案

1. 间谍子类（已运行验证，记录到的调用为空列表）：

```python
calls = []
class SpyArxiv(ArxivMockClient):
    def search(self, q):
        calls.append(("arxiv", q)); return super().search(q)
class SpyS2(SemanticScholarMockClient):
    def search(self, q):
        calls.append(("s2", q)); return super().search(q)

corpus = build_corpus()
client = RetrievalClient(SpyArxiv(corpus), SpyS2(corpus), corpus)
client.search("attention")
print(calls)        # []
```

2. 合并函数（已运行验证：查询 `"attention sparsity"` 得到 20 篇，p001 的 `source` 为 `merged`，引用字段 19 条）：

```python
def load_corpus_from_clients(query, arxiv, s2):
    merged = {}
    for p in arxiv.search(query):
        merged[p.id] = p
    for p in s2.search(query):
        base = merged.get(p.id)
        if base is None:
            merged[p.id] = p
        else:
            base.references = base.references or list(p.references)   # arXiv 没有引用字段，以 S2 为准
            base.citations = base.citations or list(p.citations)
            base.source = "merged"
    return list(merged.values())
```

3. 用子语料构造客户端后，demo 查询的 `hit_count` 从 24 变成 **20**。原因：子语料只包含与查询词有交集的 20 篇，p086、p021、p081、p082 不在其中；`search` 遍历 `merged_ids` 时 `self._corpus.get(doc_id)` 为 `None` 就 `continue`。这说明"先按查询拉一小批论文、再在这批里做图扩展"会丢掉图上的邻居——真实系统应在图扩展后**按 id 再调用 S2 的 `fetch`** 把邻居的元数据补回来（mock 已提供 `fetch`，但代码没有用）。

### Q11 — 参考答案

1. 参考实现（已运行验证）：

```python
import math
def rerank_with_citations(result, w_cite=0.2):
    mx = max((len(x.paper.citations) for x in result.ranked), default=0)
    for x in result.ranked:
        cite = math.log1p(len(x.paper.citations)) / math.log1p(mx) if mx else 0.0
        x.final_score += w_cite * cite
    result.ranked.sort(key=lambda x: (-x.final_score, x.paper.id))
    return result
```

   前 4 名：p002（1.0251，被引 18）、p001（1.0，被引 19）、p005（0.9143，被引 0）、p004（0.8857，被引 0）。两个锚点升到最前。注意 p001 被引更多却排在 p002 后面：p002 年份 2019 比 p001 多了 0.2×0.1429 的 recency。用 `log1p` 是为了让被引次数收益递减，避免高被引论文压倒一切；分数也不再在 [0, 1] 内，若需要应重新归一化权重。
2. `w_recency=0, w_bm25=0.7`：前 6 名是 p001–p005 均为 1.0，p006 为 0.88。年代偏置消失了，但 5 个种子完全并列，最终靠 id 排序——又回到了 Q9 中"平分靠 id"的问题。这说明在这个语料上，三项信号都无法区分种子之间的差异。
3. 讨论要点：判断"是否已有人做过"时，应同时找**最早的奠基工作**（证明想法不新）与**最新的进展**（证明想法已被超越）。recency 应作为可配置项（讲义："a stale topic might tune recency down while a fast moving topic raises it"），新颖性检查场景可以把 recency 权重降低，加入被引数或 PageRank 之类的权威性信号；或者输出两个列表"奠基"与"最新"，而不是一个混合排名。

### Q12 — 参考答案

1. 参考实现与结果（已运行验证）：

```python
SUFFIXES = ("ities", "ity", "ing", "es", "s", "e")
def stem(tok):
    for suf in SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            return tok[: -len(suf)]
    return tok
```

   `sparse → spars`、`sparsity → spars`、`pruning → prun`、`heads → head`、`routing → rout`、`adapters → adapter`。后缀按"从长到短"排列，避免 `sparsity` 只被剥掉 `y` 之类的问题。

2. 把 `main.tokenise` 换成"分词后逐个 `stem`"的版本（索引与查询都要用同一个函数），`"sparse attention"` 对 p001 的 BM25 从 **2.654 变成 5.309**——`spars` 也以 3 次出现命中，贡献与 `attention` 相同。
3. 副作用：
   - 过度合并：`news → new`、`universe/university` 一类规则会把不相关的词合在一起，降低精确率；
   - 不足合并：不规则变化（`ran/run`）合并不了；
   - 名词缩写、代码标识符（如 `lora`、`bm25`）可能被误剥；
   - 索引与查询必须用同一个词干器，否则一边剥一边不剥，命中率反而下降。
   - 生产中常用 Porter/Snowball 词干器或词形还原（lemmatization），并配合同义词表或稠密检索解决 "sparse attention" vs "block selection" 这类**完全不同用词**的情况——那是词干化解决不了的。

### Q13 — 参考回答要点

- **公式**：`score(d, q) = Σ_{t∈q} idf(t) · f(t,d)(k1+1) / (f(t,d) + k1(1 − b + b·|d|/avgdl))`；本节 `idf = ln((N − df + 0.5)/(df + 0.5) + 1)`。
- **k1**（常用 1.2–2.0，本节 1.5）：词频饱和速度。k1 = 0 时只看是否出现；k1 越大越接近线性 TF。
- **b**（0–1，本节 0.75）：长度归一化强度。b = 0 不考虑长度；b = 1 完全按相对长度缩放。长文档自然包含更多词，需要惩罚。
- **idf**：稀有词更有区分度；`+0.5` 是平滑，`+1` 保证非负。
- **相比 TF-IDF**：TF 有饱和（不会因为一个词重复 100 次就无限加分）；有基于平均长度的归一化；idf 有概率模型推导（BIM）。
- 加分点：BM25 仍是很强的基线，常与稠密检索做 hybrid；用倒排索引只需遍历包含查询词的文档（本节 `candidate_ids` 就是这样做的）。

### Q14 — 参考回答要点

- **BM25**：精确匹配术语、型号、缩写、罕见专有名词效果好，可解释、无需训练；漏掉同义词、改写、跨语言。
- **稠密检索**：语义相似，能处理改写与跨语言；对精确名词、数字、新术语较弱，需要 embedding 模型与向量索引，难解释。
- **引用图扩展**：找到用词完全不同但学术上紧密相关的工作（奠基论文、后续论文）；容易扩展到高被引的"综述/通用"论文而跑题，跳数多时爆炸（本节 2 跳就从 5 篇扩到 24 篇）。
- **融合方法**：
  - 加权线性组合（本节做法），需要先归一化各路分数；
  - Reciprocal Rank Fusion（RRF）：`Σ 1/(k + rank_i)`，只用名次、不需要分数可比，鲁棒；
  - 最后用 cross-encoder reranker 对候选精排。
- 加分点：说明本节 graph_score 只看距离、不区分"被谁引用"——可以按边的类型（引用 vs 被引）和节点权威性（被引数、PageRank）加权。

### Q15 — 参考回答要点

- **速率限制与重试**：两家 API 都有限流，需要指数退避、并发上限、请求缓存（同一查询/同一 id 不重复请求）。
- **ID 规范化与去重**：arXiv id 有版本号（`v1`/`v2`），同一论文还有 DOI、S2 paper id、会议版与预印本版本；需要映射表把它们归一到一个"规范 id"，否则按 id 去重会失效。
- **字段冲突**：标题大小写、作者名格式、年份（预印本年 vs 发表年）不一致；讲义说"cross client field disagreement handling is deferred"，生产中要定优先级规则。
- **字段缺失**：arXiv 不返回引用，需要 S2 补；部分论文没有摘要。
- **图扩展的成本**：每扩展一跳都要为邻居调用 `fetch`，要限制扇出（每个节点最多取前 N 个被引），并批量请求。
- **可复现**：真实 API 的结果随时间变化，评测与回放时要缓存快照，记录检索时间。
- 加分点：把客户端接口保持为 `search(query) -> list[Paper]` 与 `fetch(id) -> Paper | None`，mock 与真实实现可以互换，测试仍用 mock。

### Q16 — 参考回答要点

- **从假设生成查询**：用假设的 `text`、`variables`、`metric` 生成多条查询（关键词版、改写版、方法名版），必要时让 LLM 补充同义词与已知方法名。
- **多路召回**：BM25 + 稠密检索 + 引用图扩展（种子取高置信命中）；对 `baseline_ref` 指向的论文直接 `fetch` 并扩展其被引。
- **精排**：cross-encoder 或 LLM 判断"这篇论文是否研究了同一个自变量对同一个指标的影响"。
- **结论判定**：对前 N 篇逐篇抽取"结论句"，与假设比较：已证明 / 已证伪 / 部分相关 / 无关；输出带引用（paper id + 原文句子）的证据。
- **决策**：已证明/证伪 → 跳过实验或改为复现；部分相关 → 调整假设或把相关工作作为 baseline；无关 → 进入第 52 节跑实验。
- **向下游传递**：讲义说第 52 节读取 `paper.id`、`title` 与摘要前三句作为实验上下文，第 53 节读取 `year` 与 `references` 做 baseline 归因。
- 常见误区：只看 top-1；只用新论文（Q8 的年代偏置）；把"检索不到"当作"没人做过"——应报告检索覆盖范围与置信度。

### Q17 — 参考回答要点

- **建标注集**：选一批查询（例如历史假设），人工或用已知综述标注相关论文。
- **指标**：Recall@k（对"是否已被证明"最关键，漏召回代价大）、MRR、nDCG@k；分别评估 BM25 单路、加图扩展、加重排后的增益。
- **调参**：
  - `top_k_lexical`：种子越多召回越高，但图扩展的规模随之膨胀；画"召回率 vs 结果数"曲线选拐点。
  - `max_hops`：本节实测 0/1/2 跳分别得到 5/21/24 篇；在真实图上 2 跳可能是成千上万篇，要配合扇出上限。
  - 三项权重：在标注集上网格搜索或学习排序，按领域（快速演进 vs 成熟领域）分别设置 recency。
- **线上监控**：讲义说 `RetrievalResult` 带 hit_count、average_score、top_score、wall_time，runner 记录它们，用于观察质量随时间的变化。
- **测试数据要有区分度**：本节 mock 语料同主题完全同分（Q9），只能测管线，不能测排序质量。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 14 信息检索与搜索](../../../05-nlp-foundations-to-advanced/14-information-retrieval-search/docs/zh.md)：TF-IDF、BM25 与倒排索引的基础。
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)：检索结果如何作为上下文交给 LLM。
- [阶段 11 · 07 Advanced RAG](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：混合检索与重排序。
- [阶段 19 · 50 研究假设生成器](../../50-hypothesis-generator/docs/zh.md)：本节检索的输入（队首假设）。
- [阶段 19 · 20 Agent Harness 的循环契约](../../20-agent-harness-loop-contract/docs/zh.md)：讲义先修的 Track A 循环原语。

### 本节被哪些后续内容用到
- [阶段 19 · 52 实验执行器](../../52-experiment-runner/docs/zh.md)：读取检索结果中的论文 id、标题、摘要前三句作为实验上下文。
- [阶段 19 · 53 结果评估器](../../53-result-evaluator/docs/zh.md)：用 `year` 与 `references` 把 baseline 归因到具体论文。
- [阶段 19 · 54 论文写作器](../../54-paper-writer/docs/zh.md)：相关工作与引用。
- [阶段 19 · 57 端到端研究演示](../../57-end-to-end-research-demo/docs/zh.md)：完整研究循环。
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../65-hybrid-retrieval-bm25-dense/docs/zh.md)：把本节 BM25 与稠密检索融合。
- [阶段 19 · 66 基于 Cross-Encoder 的 Reranker](../../66-reranker-cross-encoder/docs/zh.md)：对合并后的候选精排。
- [阶段 19 · 68 RAG Evaluation](../../68-rag-eval-precision-recall/docs/zh.md)：用精确率、召回率、MRR、nDCG 评估检索。

### 延伸关键词
`Okapi BM25` · `k1 / b` · `inverted index` · `idf smoothing` · `stemming / lemmatization` · `Porter stemmer` · `citation graph` · `BFS / k-hop expansion` · `PageRank` · `hybrid retrieval` · `Reciprocal Rank Fusion` · `cross-encoder rerank` · `Recall@k / nDCG` · `Semantic Scholar API` · `arXiv API` · `entity resolution`
