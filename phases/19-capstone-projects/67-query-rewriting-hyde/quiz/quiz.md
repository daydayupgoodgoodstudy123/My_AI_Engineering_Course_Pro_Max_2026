# 测验 · 查询改写：HyDE、多查询与查询分解（Query Rewriting: HyDE, Multi-Query, and Decomposition）

> **阶段 19 · 综合项目 · 第 67 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义为机翻且质量较差，有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要改写 | 用户输入的 query 往往和语料用词不同（"dropped" vs "aborted"），正确文档可能连 top-N 都进不去，后面的 reranker 永远看不到它 |
| 2 | HyDE | 让 LLM 写一段"假设的答案文档"，用**这段文本的向量**代替 query 向量去做稠密检索；讲义出处：Gao et al. 2023 "Precise Zero-Shot Dense Retrieval without Relevance Labels" |
| 3 | HyDE 为什么有效 | 检索器只关心 token 分布，不关心事实对错；假设文档用的是"语料的口吻"，向量落在真实答案附近 |
| 4 | Multi-query | 生成 N 个改写，分别检索，再用 RRF 合并；覆盖"表述方式"的方差，适合"换个说法就能命中"的 query |
| 5 | Decomposition | 把多主题 / 带连词的复杂问题拆成可独立回答的子问题，分别检索后合并；原子问题必须原样返回 |
| 6 | RRF | `score(d) = Σ 1/(k + rank)`，k = 60，只看名次不看原始分数，不需要分数校准 |
| 7 | 本节检索器 | BM25（标题重复 3 次加权）+ 哈希稠密向量，RRF 融合；HyDE 路径中 BM25 仍跑**原始 query**，只有稠密侧用假设文档 |
| 8 | 失败模式 | HyDE 编造标识符；multi-query 改写趋同；decomposition 过度拆分；LLM 调用次数让延迟成倍增加 |
| 9 | 生产模式 | 按 query 特征选择策略（短→multi-query，多子句→decomposition，术语多→HyDE）；按 query 哈希缓存改写；三种并行再 RRF |
| 10 | Mock LLM | 本节用查表 + 同义词表的确定性 `MockLLM` 离线运行；接口不变，生产时替换为真实模型调用 |

### 核心技能（能动手做到）

- [ ] 写出 HyDE、multi-query、decomposition 三种 prompt，并说清各自适用的 query 类型
- [ ] 实现 `Rewriter` 接口与 `retrieve_with_rewriter`：改写 → 多路检索 → RRF 融合
- [ ] 手算 RRF 分数，并能判断两个文档何时会出现**完全相同**的融合分数
- [ ] 读懂一组"策略对比"实验结果，分辨哪些"胜出"是真实提升、哪些是平局或偶然
- [ ] 为 multi-query 加重复检测（Jaccard），为 decomposition 加"是否需要拆分"的防护
- [ ] 指出测试用例中的逻辑漏洞（例如永远为真的断言）

---

## 二、基础自测（选择题）

**Q1.** HyDE 在检索时实际用来做稠密检索的向量是：

- A. 原始 query 的向量
- B. 原始 query 与语料中所有文档向量的平均
- C. LLM 根据 query 写出的"假设答案文档"的向量
- D. 正确答案文档的向量

**Q2.** LLM 不了解你的私有语料，它写出的假设文档在事实上往往是错的。HyDE 仍然有效的主要原因是：

- A. 检索器只关心 token 分布和向量所在区域，不关心事实正确性；假设文档用的是"文档的口吻和词汇"
- B. HyDE 会把假设文档和真实文档逐字比对，自动纠正事实错误
- C. LLM 在生成时会自动访问你的向量索引
- D. HyDE 只在 BM25 上起作用，与稠密检索无关

**Q3.** 用户问："上传失败、并且重试预算耗尽时，系统会怎么做？"答案分散在"分片上传中止"和"重试配额冷却"两篇文档里。最对症的改写策略是：

- A. HyDE
- B. Multi-query
- C. 不改写，直接把 top-K 调大
- D. Decomposition（查询分解）

**Q4.** 在本节代码中，`retrieve_with_rewriter(q, MultiQueryRewriter(n=3), retriever)` 一共会调用多少次 `HybridRetriever.search`？

- A. 3 次
- B. 4 次
- C. 6 次
- D. 1 次

**Q5.** RRF 取 k = 60。某文档在列表 A 中排第 1、在列表 B 中排第 5，它的 RRF 分数约为：

- A. 0.03178
- B. 0.01639
- C. 0.20000
- D. 1.20000

**Q6.** 本节 `HybridRetriever.search_vec(qv, qtext, ...)`（HyDE 路径）中，BM25 和稠密检索分别使用什么？

- A. 两者都用假设文档
- B. BM25 用假设文档，稠密用原始 query 向量
- C. 两者都用原始 query
- D. BM25 用原始 query 文本，稠密用假设文档的向量

**Q7.** 讲义提到 multi-query 的失败模式"rewrites all converge"。推荐的对策是：

- A. 把 N 从 3 提高到 30
- B. 去掉原始 query，只保留改写
- C. 在改写 prompt 中显式要求多样性，并用 Jaccard 等方法检测重复改写
- D. 改用更大的 RRF k 值

**Q8.** 对一个本身就是单一主题的"原子问题"，decomposition 改写器应该：

- A. 至少拆成两个子问题，以便并行检索
- B. 原样返回这一个问题，不要编造子问题
- C. 改用 HyDE 生成假设文档
- D. 返回空列表，让系统跳过检索

---

## 三、动手 / 代码题

**Q9.** 运行 `python3 main.py`，第二个 query 的结果显示 HyDE 是唯一 `gold@1 = yes` 的策略：

```text
no-rewrite   | how does the search service merge two retrievers |  no    |   5
hyde         | how does the search service merge two retrievers |  yes   |   1  <- expected winner
```

已知 HyDE 路径下 `retrieve_with_rewriter` 产生两条内部排名（`k_each=8`）：

```text
ranking 1 = search_vec(假设文档向量, qtext=原 query): d6, d3, d4, d1, d2, d8, d5, d7
ranking 2 = search(原 query):                        d2, d8, d4, d3, d6, d7, d1, d5
```

1. 用 RRF（k = 60）算出 d6 和 d2 的最终分数。
2. 为什么最终 d6 排在 d2 前面？这个"胜出"可靠吗？
3. 把 `k_each` 改成 5 后，HyDE 在这个 query 上 gold 排第 2。这说明了什么？

**Q10.** 下面是 `tests/test_rewriters.py` 中的一个测试：

```python
    def test_gold_promotion_for_designated_strategies(self) -> None:
        """For each gold case, the designated strategy at least matches no-rewrite on gold rank."""
        for q, gold, _winner in GOLD:
            baseline = retrieve_with_rewriter(q, _IdentityRewriter(), self.retriever, k_each=8, k_out=8)
            base_ids = [d.doc_id for d, _ in baseline["results"]]
            base_rank = base_ids.index(gold) + 1 if gold in base_ids else 99
            best = base_rank
            for rw in (HyDERewriter(), MultiQueryRewriter(n=3), DecomposeRewriter()):
                out = retrieve_with_rewriter(q, rw, self.retriever, k_each=8, k_out=8)
                ids = [d.doc_id for d, _ in out["results"]]
                rank = ids.index(gold) + 1 if gold in ids else 99
                best = min(best, rank)
            self.assertLessEqual(best, base_rank, f"no rewriter helped on query: {q}")
```

1. 这个测试能失败吗？为什么？
2. docstring 说的是"指定的策略（designated strategy）至少不差于 no-rewrite"，代码实际检查的是什么？
3. 改写这个测试，使它真正验证 `GOLD` 中第三列 `expected_winner` 的表现。

**Q11.** `MockLLM.decompose` 的兜底逻辑是"遇到 and 就拆"：

```python
        if " and " in query.lower():
            parts = re.split(r"\s+and\s+", query, flags=re.IGNORECASE)
            return [p.strip().rstrip("?") for p in parts if p.strip()]
        return [query]
```

1. 对 `"how is lexical and semantic retrieval combined"`，它返回什么？这属于讲义中的哪种失败模式？
2. 写一个 `safe_decompose(query)`：只有当每个子句都"像一个问题"且子句之间足够不同时才拆分，否则原样返回。
3. 你的规则有什么局限？

**Q12.** 第二个 query 不改写时（no-rewrite），d6 只排第 5。但单独看 BM25，d6 是第 1 名（1.919），d2 只排第 4；稠密检索中 d2 第 1，d6 第 7。

1. 用 RRF（k = 60）计算 `HybridRetriever.search` 内部 d2 和 d6 的分数，解释为什么 d2 赢了。
2. 讲义说这类 query 的问题是"query 和文档不共享名词短语，BM25 会漏掉"。在本 fixture 中，真正拖后腿的是哪一路？
3. 提出两种不依赖 LLM 改写、也能修复这个 query 的办法。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 HyDE？它解决什么问题？有哪些风险？

**Q14.**（原理深挖）HyDE、multi-query、decomposition 三者分别覆盖什么类型的"query–语料不匹配"？为什么讲义说它们是互补的？

**Q15.**（工程实践）引入查询改写后，延迟和成本会怎样变化？在生产中如何控制？

**Q16.**（场景设计）你要给一个企业知识库 RAG 加一个"改写策略选择器"。请设计它的规则或模型、离线评估方法和上线保护措施。

**Q17.**（追问型）你做了一个对比实验，表格里显示某策略"胜出"。面试官问："你怎么确定这不是偶然？"你会如何回答？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："HyDE replaces the user's query vector with an LLM-written hypothetical document vector." 代码中 `hv = mock_embed(rw.hypothetical)` 后调用 `retriever.search_vec(hv, ...)`。

- A 是不改写的基线。
- B 不是任何标准做法。
- D 是"作弊"：检索时并不知道正确答案文档。

### Q2 — 答案：A

讲义："The retriever does not care about factual correctness, only about token distribution. The hypothetical passage contains the words 'abort', 'multipart', 'bucket', 'budget'... Embed that passage. The vector lands near the real passage."

- B 错：HyDE 不做任何事实校验。
- C 错：生成假设文档时 LLM 看不到语料（否则就是普通 RAG 了）。
- D 错：HyDE 主要作用于稠密检索；本节代码甚至刻意让 BM25 继续用原始 query。

### Q3 — 答案：D

问题包含两个独立主题（上传失败中止、重试预算耗尽），讲义："Decomposition is the right tool for questions that contain conjunctions, multi-clause comparisons, or two unrelated topics." 本节 `DECOMP_TABLE` 正是把这个问题拆成 "how is an in-flight multipart upload aborted" 和 "what happens when the retry quota reaches zero"。

- A、B 仍然是"一个检索向量 / 同一主题的多种说法"，难以同时覆盖两个主题。
- C 增大 top-K 只是碰运气，且会引入更多噪声。

### Q4 — 答案：B

`MultiQueryRewriter.rewrite` 返回 `[query] + self.llm.paraphrase(query, n=self.n)`，即**原始 query + 3 个改写 = 4 条**，`retrieve_with_rewriter` 对每条调用一次 `retriever.search`。每次 `search` 内部又各跑一次 BM25 和一次稠密检索，所以底层是 8 次检索。讲义描述为"N paraphrases"，代码额外保留了原始 query——这是常见且合理的做法（防止改写全部跑偏），但要清楚实际检索次数是 N + 1。

### Q5 — 答案：A

`1/(60+1) + 1/(60+5) = 0.016393 + 0.015385 = 0.031778`。代码 `score[doc.doc_id] += 1.0 / (k + rank + 1)` 中 `rank` 从 0 开始，所以第 1 名对应 `1/61`。

- B 只算了第一个列表。
- C 是 `1/1 × 1/5` 之类的误算。
- D 是把 k 当成 0：`1/1 + 1/5`。

### Q6 — 答案：D

代码注释："When given a precomputed dense vector (HyDE case), still run BM25 on the original query text so the lexical signal does not vanish." 即 `b = self.bm25.search(qtext, k_each)`，`d = self.dense.search_vec(qv, k_each)`。

这呼应了讲义的失败模式："HyDE hallucinates corpus-specific identifiers wrong... weight BM25 lower in the fusion"——假设文档里编造的标识符如果进了 BM25，会成为高权重的噪声词。本节代码的做法更彻底：BM25 完全不看假设文档。

### Q7 — 答案：C

讲义："Add an explicit diversity instruction to the rewrite prompt and detect duplicates by Jaccard."

- A 错：弱模型生成 30 个也可能全是近义重复，只会增加延迟。
- B 错：去掉原始 query 反而失去兜底。
- D 错：RRF 的 k 只影响名次权重的平滑程度，不能消除重复。

### Q8 — 答案：B

讲义："Wrong tool for atomic questions; the decomposer's job there is to return the single question and not invent fake sub-questions." 代码兜底分支 `return [query]`，测试 `test_decompose_atomic_returns_self` 也验证了这一点。A 正是"over-split"失败模式；C 是换策略而不是 decomposition 的职责；D 会导致无结果。

### Q9 — 参考答案

1. 外层 RRF 只看名次：
   - d6：ranking 1 第 1 名、ranking 2 第 5 名 → `1/61 + 1/65 = 0.0317781`
   - d2：ranking 1 第 5 名、ranking 2 第 1 名 → `1/65 + 1/61 = 0.0317781`
   两者**完全相等**（实测打印的两个分数都是 `0.03177805800756621`）。
2. 分数相同时，`sorted(score.items(), key=lambda x: -x[1])` 是**稳定排序**，保留字典的插入顺序；ranking 1 先被处理，d6 先插入字典，所以 d6 排在前面。也就是说，HyDE 的"胜出"是一个**平局 + 插入顺序**决定的结果，不是 HyDE 让 d6 的分数真正领先。若把 HyDE 的排名放到后面处理，结论就会反过来。
3. `k_each` 改为 5 后 HyDE 在此 query 上 gold 排第 2，`k_each=3` 时又回到第 1。结论对超参数非常敏感，3 个 query 的 fixture 只能演示"形状"，不能作为策略优劣的证据。另外，嵌套 RRF（先在 hybrid 内部 RRF，再对多条排名 RRF）会把内部分数差异抹平成名次，这也是平局容易出现的原因。

### Q10 — 参考答案

1. **不可能失败**。`best` 初始化为 `base_rank`，之后只会被 `min` 变小或保持不变，所以 `best <= base_rank` 恒成立——这是一个**永真断言**（tautology）。
2. docstring 要求"指定策略不差于基线"，代码检查的是"三个策略中最好的那个不差于基线"，而且由于初始化方式，连这一点都没有真正检查。
3. 改写示例：

```python
    def test_designated_strategy_not_worse_than_baseline(self) -> None:
        strategies = {
            "hyde": HyDERewriter(),
            "multiquery": MultiQueryRewriter(n=3),
            "decompose": DecomposeRewriter(),
        }

        def gold_rank(rw, q, gold):
            out = retrieve_with_rewriter(q, rw, self.retriever, k_each=8, k_out=8)
            ids = [d.doc_id for d, _ in out["results"]]
            return ids.index(gold) + 1 if gold in ids else 99

        for q, gold, winner in GOLD:
            base = gold_rank(_IdentityRewriter(), q, gold)
            designated = gold_rank(strategies[winner], q, gold)
            self.assertLessEqual(designated, base, f"{winner} worse than baseline on: {q}")
            self.assertEqual(designated, 1, f"{winner} did not put gold first on: {q}")
```

按当前输出（multiquery 1 vs 基线 3；hyde 1 vs 5；decompose 1 vs 1），这个测试会通过；但它至少会在某个策略退化时报错。若还想检验"严格胜出"，第三个 query 会失败（decompose 与 no-rewrite 打平）——这恰好揭示了 fixture 不能证明"decomposition 胜出"。

### Q11 — 参考答案

1. 返回 `['how is lexical', 'semantic retrieval combined']`。"lexical and semantic retrieval" 是一个名词短语里的并列，不是两个问题。这就是讲义的 "Decomposition over-splits"：拆出来的子问题残缺、检索质量下降。
2. 参考实现（已在示例上运行验证）：

```python
_QWORDS = {"how", "what", "why", "when", "where", "which", "who", "does", "do", "is", "are", "can"}

def jaccard(a, b):
    a, b = set(tokenize(a)), set(tokenize(b))
    return len(a & b) / len(a | b) if a | b else 1.0

def safe_decompose(query, min_tokens=3, max_jaccard=0.6):
    parts = [p.strip().rstrip("?") for p in re.split(r"\s+and\s+", query, flags=re.IGNORECASE) if p.strip()]
    if len(parts) < 2:
        return [query]
    for p in parts:                                  # 每个子句都要"像问题"
        toks = tokenize(p)
        if len(toks) < min_tokens or toks[0] not in _QWORDS:
            return [query]
    for i in range(len(parts)):                      # 子句之间要足够不同
        for j in range(i + 1, len(parts)):
            if jaccard(parts[i], parts[j]) > max_jaccard:
                return [query]
    return parts
```

   实测：`"how is lexical and semantic retrieval combined"` → 原样返回；`"how is authorization handled and how do policies get evaluated"` → 拆成两个；`"where is the policy engine cached"` → 原样返回。
3. 局限：`"what happens when an upload fails and the retry budget is exhausted"` 的第二个子句以 "the" 开头，规则不会拆分，但它其实是真正的双主题问题（第二个子句省略了疑问词）。规则方法召回不足，生产中通常让 LLM 判断"是否需要拆分"（讲义练习 3 的"atomic 判断头"），并在扇出前做一次"子问题是否足够不同"的检查。

### Q12 — 参考答案

1. `HybridRetriever.search` 内部对 BM25 与稠密两条排名做 RRF：
   - d2：BM25 第 4、稠密第 1 → `1/64 + 1/61 = 0.015625 + 0.016393 = 0.032018`
   - d6：BM25 第 1、稠密第 7 → `1/61 + 1/67 = 0.016393 + 0.014925 = 0.031319`
   d2 胜出。RRF 对两路一视同仁，稠密检索的"错误第一名"和 BM25 的"正确第一名"权重相同。
2. 拖后腿的是**稠密那一路**。query 中的 "search" 只在 d6 出现（df = 1，idf = ln 6 ≈ 1.79），BM25 已经把 d6 排第 1；而哈希 embedding 没有语义，把 d6 排到第 7。讲义描述的"BM25 misses"在这个 fixture 中并不成立，HyDE 的提升主要来自修正稠密那一路（假设文档使 d6 的稠密相似度达到 0.909，排第 1）。
3. 办法：
   - **加权 RRF**：给 BM25 更高的权重（如 `w_bm25 / (k + rank)`），或根据离线评估调权；
   - **更好的稠密模型**：用真正的语义 embedding 替换哈希向量；
   - 也可以只在 BM25 与稠密分歧很大时才调用改写（省下 LLM 调用）。

### Q13 — 参考回答要点

- **定义**：Hypothetical Document Embeddings。让 LLM 针对 query 写一段假设的答案文档，对这段文本做 embedding，用它代替 query 向量去检索（讲义出处：Gao et al. 2023）。
- **解决的问题**：query 短、口语化，与文档的用词和体裁差距大；假设文档"写在语料的口吻里"，向量更接近真实答案所在区域。适合术语密集、零样本（没有标注数据训练检索器）的场景。
- **风险**：
  - 幻觉出错误的专有名词/函数名，如果参与 BM25 会成为高权重噪声（讲义："Cap the hypothetical's length and weight BM25 lower in the fusion"）；
  - 多一次 LLM 调用的延迟和成本；
  - 对 LLM 完全不了解的领域，假设文档可能把向量带到错误区域；
  - 长度：讲义建议 2–3 句，太长噪声多、太短失去词汇信号。
- 加分点：说明本节代码的处理——BM25 仍用原 query，HyDE 只影响稠密侧；并且原 query 的普通检索结果也参与最终 RRF。

### Q14 — 参考回答要点

| 策略 | 覆盖的不匹配类型 | 讲义的说法 |
|------|----------------|-----------|
| HyDE | query 与语料的**词汇/体裁鸿沟**（问题 vs 文档的写法） | "HyDE bridges the query-corpus token gap" |
| Multi-query | 同一意图的**表述方差**，某个说法恰好命中语料 | "Multi-query covers paraphrase variance" |
| Decomposition | **多主题**问题，单个检索向量无法同时靠近两篇文档 | "Decomposition covers multi-topic queries" |

- 互补：三者针对的失败原因不同，一个 query 可能同时有多种问题；讲义建议"按 query 选择策略"或"三者并行再 RRF"。
- 各自的失效情况：multi-query 在"原始问题本身就问错了"时所有改写同样差；decomposition 对原子问题会过度拆分；HyDE 在 LLM 不懂的领域会编造。
- 加分点：讲义练习还提到 step-back prompting（先问更一般的问题再收窄）作为第四种策略。

### Q15 — 参考回答要点

- **成本结构**（讲义）："HyDE costs one LLM call. Multi-query costs one LLM call to generate N rewrites, then N retrievals. Decomposition costs one LLM call to decompose, then M retrievals. The retrievals run in parallel; the LLM call is the floor."——LLM 调用是延迟的下限。
- **控制手段**：
  - 按 query 哈希缓存改写结果（讲义："Many queries repeat"）；
  - 用小而快的模型做改写，限制输出长度（假设文档 2–3 句）；
  - 多路检索并行执行；
  - 只在需要时改写：例如第一阶段 top-1 分数低、BM25 与稠密分歧大、或 query 被分类为"复杂"时才触发；
  - 设置超时：改写超时就退回原始 query 检索。
- **质量保护**：保留原始 query 那一路（本节 multi-query 和 HyDE 都这样做）；用离线评估（第 68 节）量化每种策略对 recall 的贡献。

### Q16 — 参考回答要点

- **选择器**：
  - 规则版（讲义 "Use It"）：短的原子 query → multi-query；含连词/多子句 → decomposition；术语密度高 → HyDE。第 69 节的 `Rewriter.pick_strategy` 就是规则版（含 " and " → decompose，含 api/function/endpoint/config → hyde，否则 multiquery）。
  - 模型版：用一个小分类器或 LLM 输出策略标签，训练数据来自离线实验中"哪种策略对该 query 的 recall 最好"。
- **离线评估**：
  - 构建带 query 类别标签的 qrels（字面型、改写型、多主题型），分类别报告 recall@k、MRR（第 68 节）；
  - 每种策略单独跑一遍 + 选择器跑一遍 + "三者并行 RRF"跑一遍，比较收益与 LLM 调用成本；
  - 注意平局与小样本问题（见 Q9），需要足够多的 query 与置信区间。
- **上线保护**：改写失败/超时回退到原 query；监控 LLM 调用率、缓存命中率、改写后 top-1 分数分布；A/B 实验观察线上指标；记录每个 query 的策略与改写文本，便于追查。

### Q17 — 参考回答要点

- 先看**样本量**：本节每种策略只有 1 个"专属" query，任何结论都只是示例。应该在几十到几百个 query 上统计，并报告置信区间或做配对显著性检验（如对每个 query 的 MRR 做配对 bootstrap / 符号检验）。
- 检查**平局与排序稳定性**：RRF 只看名次，容易出现完全相同的分数，此时由插入顺序决定先后（Q9 就是例子）。应该显式定义平局处理（如按 doc_id 或第一阶段分数打破平局），并报告平局比例。
- 做**超参数敏感性**：改变 `k_each`、RRF 的 k、top-K，看结论是否稳定（本节 `k_each` 从 8 改 5，HyDE 的胜出就消失了）。
- 检查**基线**：确认对比的基线本身合理（本节第三个 query 不改写就已经 gold@1，"decomposition 胜出"其实是平局）；检查测试/断言是否真的能失败（Q10）。
- 检查**指标是否对准目标**：decomposition 的价值是"覆盖两篇文档"，只看单个 gold 的排名无法衡量它，应该用多 gold 的 recall@k。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 04 Embeddings 与向量表示](../../../11-llm-engineering/04-embeddings/docs/zh.md)：HyDE 的核心是"换一个文本去 embed"。
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)、[阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：查询改写在 RAG 流水线中的位置。
- [阶段 05 · 14 信息检索与搜索](../../../05-nlp-foundations-to-advanced/14-information-retrieval-search/docs/zh.md)：BM25、IDF 与查询扩展的经典做法。
- [阶段 11 · 01 Prompt Engineering：技术与模式](../../../11-llm-engineering/01-prompt-engineering/docs/zh.md)：三种改写 prompt 的写法。
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../65-hybrid-retrieval-bm25-dense/docs/zh.md)：本节复用的 hybrid 检索与 RRF。
- [阶段 19 · 64 Chunking 策略比较](../../64-chunking-strategies-advanced/docs/zh.md)：被检索的单元从哪里来。

### 本节被哪些后续内容用到
- [阶段 19 · 66 基于 Cross-Encoder 的 Reranker](../../66-reranker-cross-encoder/docs/zh.md)：改写后的候选在生产中再交给 reranker（讲义练习 1 的 RAG-Fusion）。
- [阶段 19 · 68 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性](../../68-rag-eval-precision-recall/docs/zh.md)：量化改写对 recall 的提升。
- [阶段 19 · 69 端到端 RAG 系统](../../69-end-to-end-rag-system/docs/zh.md)：带策略选择器的改写阶段被接入完整流水线。
- [阶段 17 · 14 Prompt 缓存与语义缓存的经济性](../../../17-infrastructure-and-production/14-prompt-semantic-caching/docs/zh.md)：缓存改写结果以降低 LLM 调用成本。

### 延伸关键词
`HyDE` · `multi-query expansion` · `RAG-Fusion` · `query decomposition` · `step-back prompting` · `reciprocal rank fusion` · `weighted RRF` · `query expansion` · `synonym expansion` · `over-splitting` · `Jaccard dedup` · `tie-breaking` · `strategy selector`
