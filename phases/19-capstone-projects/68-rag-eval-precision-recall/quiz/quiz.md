# 测验 · RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性（RAG Evaluation: Precision, Recall, MRR, nDCG, Faithfulness, Answer Relevance）

> **阶段 19 · 综合项目 · 第 68 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义为机翻且质量较差，有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 分阶段评估 | RAG 至少有 chunker、retriever、reranker、generator 四个部件，任何一个都可能导致错误答案；没有分阶段指标就是"盲飞" |
| 2 | Precision@k | top-k 中属于 gold 的比例；本节实现分母固定为 k（返回不足 k 个也按 k 算） |
| 3 | Recall@k | gold 中出现在 top-k 的比例；讲义：生产 RAG 最常引用的指标，因为生成器能忽略无关块，却无法凭空编出没看到的块 |
| 4 | MRR | 每个 query 第一个相关文档名次的倒数，再对 query 求平均；高度偏重第 1 名（第 1 名 1.0，第 2 名 0.5，第 10 名 0.1） |
| 5 | nDCG@k | `DCG = Σ (2^rel − 1) / log2(i + 2)`（本节实现），除以理想排序的 IDCG，范围 0–1；支持分级相关性 |
| 6 | Faithfulness | 答案的每个 claim 是否被检索到的上下文支持，取支持比例；又叫 groundedness、attribution |
| 7 | Answer relevance | 答案是否回应了问题；"忠实但跑题"与"切题但无依据"是两种不同的失败 |
| 8 | Qrels | 标注集：query、gold 文档 id、分级相关性、参考答案片段；本节 4 条手工 fixture |
| 9 | 用指标诊断 | 低 recall → chunker/检索；recall 可以但 MRR 低 → reranker；MRR 高但忠实度低 → 生成提示；忠实但不相关 → 改写或提示；全高但用户仍抱怨 → 评估集不具代表性 |
| 10 | 评估本身的失败模式 | LLM-as-judge 偏向自己的输出；qrels 随语料变化而"腐烂"；逐句忠实度漏掉宏观误导；平均 recall 掩盖某类 query 的系统性失败 |

### 核心技能（能动手做到）

- [ ] 给定排名列表和 gold 集合，手算 precision@k、recall@k、hit-rate@k、MRR、nDCG@k
- [ ] 用纯 Python 实现上述检索指标，并处理边界情况（k = 0、gold 为空、检索结果不足 k 个）
- [ ] 实现基于 claim 的 faithfulness 和 answer relevance，并说出 token 重叠评审器（mock judge）漏判的典型情况
- [ ] 写一个 `evaluate_pipeline`，对任意 `(query, k) -> (doc_ids, answer)` 形式的 pipeline 输出指标表
- [ ] 读一张指标表，判断问题出在检索、排序、生成还是 grounding
- [ ] 识别"评估设计缺陷"：指标饱和、qrels 不一致、评审器太宽松、各变体结果完全相同等

---

## 二、基础自测（选择题）

**Q1.** gold 集合有 3 篇文档。检索返回的 top-3 中有 2 篇在 gold 中、1 篇不在。precision@3 是：

- A. 1/3
- B. 1/2
- C. 1.0
- D. 2/3

**Q2.** 4 个 query 中第一个相关文档的名次分别是：第 1、第 2、没有找到、第 4。MRR 是：

- A. 0.4375
- B. 0.5833
- C. 0.3333
- D. 0.75

**Q3.** 本节 `dcg_at_k` 中第 i 个（i 从 0 开始）结果的贡献是：

- A. `rel / (i + 1)`
- B. `rel / log2(i + 1)`
- C. `(2^rel − 1) / log2(i + 2)`
- D. `rel × log2(i + 2)`

**Q4.** 某系统 recall@10 = 0.92，但 MRR = 0.31。按讲义的诊断表，最该优先改进的是：

- A. Chunker 边界
- B. Reranker（正确文档在 top-k 里，但没排到前面）
- C. 生成提示词（force-cite-or-refuse）
- D. 扩充 qrels

**Q5.** 本节 `precision_at_k(["a"], {"a"}, 5)` 的返回值是：

- A. 1.0
- B. 0.0
- C. 0.2
- D. 抛出异常

**Q6.** 关于 faithfulness 与 answer relevance，正确的是：

- A. faithfulness 检查答案是否被**检索上下文**支持；answer relevance 检查答案是否回应了**问题**
- B. 两者都检查答案是否与参考答案一致
- C. faithfulness 高则 answer relevance 一定高
- D. answer relevance 检查检索结果中有多少是相关文档

**Q7.** 讲义说生产 RAG 最常引用的检索指标是 recall@k，理由是：

- A. recall@k 比 precision@k 更容易计算
- B. recall@k 不需要标注数据
- C. recall@k 对排序位置最敏感
- D. 生成器可以忽略多余的无关块，但无法从它从未看到的块中"发明"答案

**Q8.** 本节 `MockJudge`（`overlap_threshold=0.4`）判断 claim "The abort threshold is five failed parts." 是否被上下文 d3（"The abort threshold is configured per bucket at three failed parts..."）支持。结果是：

- A. 不支持，因为 "five" 与 "three" 不一致
- B. 支持——content token 重叠 4/5 = 0.8 ≥ 0.4，数字错误完全检测不出来
- C. 不支持，因为 claim 太短
- D. 抛出异常，因为 claim 里有数字

---

## 三、动手 / 代码题

**Q9.** 运行 `python3 main.py`，baseline pipeline 对 4 个 qrel 的检索结果（`k=5`，只返回得分大于 0 的文档）为：

| qid | gold_doc_ids | graded_relevance | baseline 检索结果 |
|-----|-------------|------------------|-------------------|
| q1 | d3, d1 | d3:3, d1:2, d2:1 | d3, d9, d1 |
| q2 | d4 | d4:3, d5:2 | d11, d4 |
| q3 | d6 | d6:3, d8:1 | d6, d12 |
| q4 | d7 | d7:3, d2:1 | d10, d7 |

1. 手算 baseline 的 recall@1、precision@3、MRR。
2. 手算 q1 的 nDCG@3。
3. 再算 hit-rate@1（top-1 中至少有一个 gold 记 1，否则 0）。它和 recall@1 为什么不同？（讲义练习 1）

**Q10.** 讲义说："The hybrid retrieval row beats the chunker baseline on recall; the rerank row beats hybrid on MRR." 实际输出：

```text
metric          | baseline       | hybrid         | hybrid+rerank
recall@3        | 1.000          | 1.000          | 1.000
recall@5        | 1.000          | 1.000          | 1.000
mrr             | 0.750          | 1.000          | 1.000
...（hybrid 与 hybrid+rerank 的 12 项指标完全相同）
```

`hybrid_plus_rerank_pipeline` 的核心代码：

```python
    ids, _ = hybrid_pipeline(query, k * 2)
    by_id = {d.doc_id: d for d in CORPUS}
    q_tokens = set(_baseline_tokens(query))
    for syn_list in _SYN.values():
        for s in syn_list:
            if s in {t for t in _SYN if any(s in v for v in _SYN.values())}:
                continue

    def title_boost(doc_id: str) -> int:
        title_tokens = set(_baseline_tokens(by_id[doc_id].title))
        expanded = set(q_tokens)
        for t in q_tokens:
            expanded.update(_SYN.get(t, []))
        return len(expanded & title_tokens) * 5

    ranked = sorted(ids, key=lambda did: -title_boost(did))
```

1. 讲义的两句话与实际输出是否一致？
2. 为什么 rerank 与 hybrid 的结果一模一样？中间那段双层 `for` 循环做了什么？
3. MRR 已经是 1.0 时，这个 fixture 还能证明"rerank 有用"吗？应该怎样修改 fixture 或指标？

**Q11.** 三个 pipeline 的 faithfulness 都是 1.000。

1. 解释为什么 faithfulness 在本节"不可能不满分"（提示：看 pipeline 怎样生成答案、`evaluate_pipeline` 用什么作上下文）。
2. 写一个更严格的评审器 `StrictJudge`：在 `MockJudge` 的基础上，要求 claim 中的数字（阿拉伯数字或 one…ten 这类英文数字词）必须在上下文中出现。用 Q8 的例子验证。
3. 这个改进还会漏掉哪些幻觉？

**Q12.** 对照 `QRELS` 与讲义里的 fixture 示例：

```python
# 讲义示例
{"qid": "q1", "query": "what is the abort threshold for multipart uploads",
 "gold_doc_ids": ["d1", "d3"], "graded_relevance": {"d1": 3, "d3": 2}, ...}

# 代码 QRELS[0]
Qrel(qid="q1", query="what is the threshold before a multipart upload is dropped",
     gold_doc_ids=["d3", "d1"], graded_relevance={"d3": 3, "d1": 2, "d2": 1}, ...)
```

1. 找出代码中 `gold_doc_ids` 与 `graded_relevance` 之间的不一致，它会让哪些指标"口径不同"？
2. q3（"how do production search engines fuse two retrievers"）把 d8（"Index sizing"，向量索引容量规划）标为相关度 1，你怎么看？
3. 写一个 qrels 一致性检查函数，列出所有不一致的条目。

---

## 四、面试高频题

**Q13.**（基础必考）请解释 precision@k、recall@k、MRR、nDCG@k，各自适合什么场景？在 RAG 里你最先看哪个？

**Q14.**（原理深挖）nDCG 中的"增益"和"折扣"分别怎么定义？线性增益和指数增益有什么区别？计算 IDCG 时有哪些常见错误？

**Q15.**（工程实践）如何用 LLM-as-judge 计算 faithfulness 和 answer relevance？有哪些偏差，怎样让评审结果可信？

**Q16.**（场景设计）你的 RAG 系统指标如下：recall@5 = 0.93、MRR = 0.88、faithfulness = 0.62、answer relevance = 0.91。用户反馈"答案经常有编造的细节"。你如何定位与修复？

**Q17.**（追问型）你的离线评估全部指标都很高，但线上用户仍在抱怨。可能的原因有哪些？如何建设和维护评估集？

---

## 五、参考答案与解析

### Q1 — 答案：D

`precision@3 = 命中数 / k = 2 / 3`。讲义的原例："If gold has three documents and the top-3 returns two of them and one wrong one, precision@3 is 2 / 3." A 是错把"错误数"当分子；B 无依据；C 是 recall@5（若 top-5 包含全部 3 篇）的情形。

### Q2 — 答案：A

`(1/1 + 1/2 + 0 + 1/4) / 4 = 1.75 / 4 = 0.4375`。没找到的 query 贡献 0 但仍计入分母。B 是把没找到的 query 排除在分母外（`1.75 / 3`），这是常见错误；C、D 无依据。

### Q3 — 答案：C

代码：`s += ((2 ** rel) - 1) / math.log2(i + 2)`。i 从 0 开始，所以第 1 名折扣是 `log2(2) = 1`，第 2 名 `log2(3) ≈ 1.585`。指数增益 `2^rel − 1` 让高相关度文档的权重拉得更开（rel = 3 时增益 7，rel = 1 时增益 1）。讲义只说 gain "often 1 for relevant, 0 for not"，代码在二值情况下 `2^1 − 1 = 1`，两者一致。B 在 i = 0 时会除以 0。

### Q4 — 答案：B

讲义诊断表："Decent recall@k, low MRR → Right chunk is in top-k but not at position 1 → Reranker (lesson 66)." A 对应 recall 也低的情形；C 对应 MRR 高但忠实度低；D 对应"全高但用户仍抱怨"。

### Q5 — 答案：C

`sum(1 for r in top if r in gold) / k = 1 / 5 = 0.2`。分母固定为 k，即使只返回了 1 个结果——这是标准定义，测试 `test_k_larger_than_retrieved` 正是验证这一点。注意第 69 节的 `doc_level_precision` 却除以 `len(top_docs)`，两节口径不同。

### Q6 — 答案：A

讲义："Faithfulness asks 'is the answer grounded in the context?'. Answer relevance asks 'is the answer grounded in the question?'." B 混淆了参考答案比对；C 错，"A faithful but off-topic answer scores high on faithfulness and low on relevance"；D 描述的是 precision。

### Q7 — 答案：D

讲义："Generation can drop irrelevant chunks easily; it cannot invent an answer from a chunk it never saw." A、B 都不是理由（recall 同样需要标注）；C 错，recall@k 对 top-k 内部的排序**不敏感**，对排序敏感的是 MRR 和 nDCG。

### Q8 — 答案：B

claim 的 content token（去停用词、长度 > 1）是 `{abort, threshold, five, failed, parts}`，其中 4 个出现在 d3 中，重叠 0.8 ≥ 0.4，判为支持。实测 `faithfulness(["The abort threshold is five failed parts."], [d3], MockJudge()) = 1.0`。token 重叠评审器对"数字、否定、主语替换"类幻觉几乎无能为力，这正是讲义说要换成真实 LLM 评审的原因（改进见 Q11）。

### Q9 — 参考答案

1. 逐 query 计算：

| qid | recall@1 | precision@3 | 第一个 gold 名次 | RR |
|-----|---------|-------------|----------------|----|
| q1 | 1/2（d3 命中，d1 不在 top-1） | 2/3 | 1 | 1.0 |
| q2 | 0 | 1/3 | 2 | 0.5 |
| q3 | 1 | 1/3 | 1 | 1.0 |
| q4 | 0 | 1/3 | 2 | 0.5 |

   recall@1 = `(0.5 + 0 + 1 + 0) / 4 = 0.375`；precision@3 = `(2/3 + 1/3 + 1/3 + 1/3) / 4 = 5/12 ≈ 0.417`；MRR = `(1 + 0.5 + 1 + 0.5) / 4 = 0.75`。与输出一致。注意 q2–q4 只返回 2 个文档，precision@3 仍除以 3。

2. q1 nDCG@3：
   - DCG：d3（rel 3）在第 1 位 → `7 / 1 = 7`；d9 不相关 → 0；d1（rel 2）在第 3 位 → `3 / log2(4) = 1.5`；合计 8.5。
   - IDCG：理想顺序 d3、d1、d2 → `7 + 3 / log2(3) + 1 / log2(4) = 7 + 1.893 + 0.5 = 9.393`。
   - nDCG@3 = `8.5 / 9.393 ≈ 0.905`（实测 0.905）。

3. hit-rate@1 = `(1 + 0 + 1 + 0) / 4 = 0.5`（实测），而 recall@1 = 0.375。区别只出现在 **gold 多于一篇**的 q1：hit-rate 只要命中一篇就记 1，recall 要求按比例覆盖全部 gold（1/2）。当每个 query 只有一个 gold 时，二者相等；对于需要综合多篇文档的问题，recall 更严格、更能反映"证据是否找全"。

### Q10 — 参考答案

1. 第一句部分不成立：hybrid 只在 recall@1 上胜出（0.375 → 0.875），recall@3、recall@5 两者都是 1.0，打平。第二句不成立：rerank 与 hybrid 的 MRR 都是 1.0，12 项指标完全相同。（讲义还把 baseline 称为 "chunker baseline"，但代码中的 baseline 是词袋重叠检索，没有任何 chunker。）
2. 原因：
   - `hybrid_pipeline` 已经给"标题包含查询词（含同义词扩展）"的文档加了 `2 × 命中数` 的奖励；`title_boost` 用的是**同一套**扩展词、同一个标题信号，只是系数变成 5，本质上没有带来新信息；
   - `sorted` 是稳定排序，title_boost 相同的文档保留 hybrid 的原顺序；实测 4 个 query 的 rerank 结果与 hybrid 完全相同；
   - 中间的双层 `for` 循环是**死代码**：循环体只有一个 `continue`，什么也不做，不修改任何变量。另外 `_bow`、`_score_doc` 两个函数也从未被调用。
3. 不能。MRR 在 hybrid 上已经饱和（1.0），任何 rerank 都无法再提升——指标"天花板效应"。修改方向：
   - 增加更多、更难的 query，让第一阶段有排错的空间（例如同主题的干扰文档排在 gold 前面）；
   - 让 rerank 使用与第一阶段**不同**的信号（如第 66 节的 cross-encoder）；
   - 用分级 nDCG、多 gold recall@1 等更细的指标；
   - 在测试中把"rerank 严格优于 hybrid"写成断言（当前测试只要求 `>=`）。

### Q11 — 参考答案

1. 三个 pipeline 的答案都是**把检索到的文档正文原样拼接**（baseline 用 top-1 正文，hybrid 用 top-2 正文），而 `evaluate_pipeline` 的上下文正是全部检索结果的文本。每个 claim 都是上下文的原句，token 重叠 100%，faithfulness 必然为 1.0。这是一个**结构性饱和**的指标：在抽取式生成器上它无法区分好坏。讲义第 69 节也承认："The mock cannot hallucinate because it only emits text from the retrieved chunks."
2. 参考实现（已运行验证）：

```python
_NUM = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"}

def critical_tokens(text):
    toks = _TOK.findall(text.lower())
    return {t for t in toks if t.isdigit() or t in _NUM}

class StrictJudge(MockJudge):
    def supported(self, claim, context):
        if not super().supported(claim, context):
            return False
        context_toks = set(_TOK.findall(context.lower()))
        return critical_tokens(claim) <= context_toks       # 子集判断
```

   验证：对 d3 上下文，"The abort threshold is five failed parts." 从 `MockJudge` 的 1.0 变为 `StrictJudge` 的 0.0；"...configured per bucket at three failed parts." 仍为 1.0。用 `StrictJudge` 重跑 baseline 与 hybrid，faithfulness 依然是 1.0——因为答案本来就是原文，说明修改没有误伤。
3. 仍会漏掉：否定（"is **not** aborted"，`not` 不在停用词中但只是 1 个 token，重叠率仍可能过阈值）、主语/实体替换（把 check_permission 说成 policy engine 的功能）、拼接两个都"被支持"的片段得出错误推论（讲义的 "macro-claims"）、单位和数量级（"KB" 写成 "MB"）。根本解决需要 NLI 模型或 LLM 评审，并用人工标注样本校准。

### Q12 — 参考答案

1. 不一致：q1 的 d2、q2 的 d5、q3 的 d8、q4 的 d2 在 `graded_relevance` 中相关度 > 0，却**不在** `gold_doc_ids` 里。结果是 precision/recall/MRR（用二值 gold）把它们当作不相关，而 nDCG（用分级相关性）把它们当作部分相关——同一个检索结果在不同指标里"口径不同"。例如 hybrid 的 q2 只检索到 d4、d11，MRR = 1.0，但 nDCG@5 只有 0.787，因为 IDCG 里包含了未被检索到的 d5（相关度 2）。另外代码中 q1 的 query、分级与讲义示例也不同（讲义 d1:3、d3:2，代码 d3:3、d1:2）。
2. 不合理。d8 讲的是"向量索引每个向量占 1KB 内存"，与"如何融合两个检索器"无关，看起来像标注错误或随手填写。这类"qrels 噪声"会让 nDCG 对一个本应正确的排序扣分，或对检索到无关文档给分。讲义的 "Qrels rot" 一节提醒要定期复审 qrels。
3. 参考实现：

```python
def check_qrels(qrels, corpus_ids):
    problems = []
    for q in qrels:
        gold = set(q.gold_doc_ids)
        graded_pos = {d for d, r in q.graded_relevance.items() if r > 0}
        for d in sorted(graded_pos - gold):
            problems.append(f"{q.qid}: {d} graded>0 but not in gold_doc_ids")
        for d in sorted(gold - graded_pos):
            problems.append(f"{q.qid}: {d} in gold but no graded relevance")
        for d in sorted((gold | set(q.graded_relevance)) - corpus_ids):
            problems.append(f"{q.qid}: {d} not in corpus")
    return problems
```

   对本节 `QRELS` 会报告 4 条 "graded>0 but not in gold_doc_ids"（q1:d2、q2:d5、q3:d8、q4:d2）。可以把它放进 CI，在每次修改 qrels 时自动运行。

### Q13 — 参考回答要点

- **precision@k**：top-k 中相关的比例。适合"无关块代价高"的场景（浪费上下文 token、污染答案）。
- **recall@k**：相关文档被找回的比例。RAG 最常看（讲义理由见 Q7）；k 应与实际喂给生成器的块数一致。
- **MRR**：第一个相关结果名次的倒数平均。适合"只需要一个正确答案"的场景，对第 1 名极度敏感，忽略其他相关文档。
- **nDCG@k**：考虑全部相关文档、分级相关度和位置折扣，适合"一个 query 有多篇不同程度相关文档"的场景。
- **在 RAG 里先看什么**：先看 recall@k（证据有没有找到），再看 MRR/nDCG（排得是否靠前，影响截断与提示长度），然后看 faithfulness 与 answer relevance（生成是否用好了证据）。
- 加分点：说明 hit-rate@k 与 recall@k 的区别（多 gold 时不同）；讲义引用 Anthropic Contextual Retrieval 用 "1 minus recall@20" 作为检索失败率。

### Q14 — 参考回答要点

- **增益**：二值时相关为 1；分级时常见两种——线性 `rel`、指数 `2^rel − 1`（本节代码）。指数增益让"高度相关"远比"部分相关"重要（3 级为 7，1 级为 1），线性增益则更平均。不同论文/工具默认不同，报告时要写明。
- **折扣**：`1 / log2(位置 + 1)`（位置从 1 开始），越靠后贡献越小，但下降得比 MRR 的 `1/rank` 平缓。
- **归一化**：除以理想排序的 DCG（IDCG），使不同 query 之间可比，范围 0–1。
- **IDCG 常见错误**：
  - 只用"检索到的文档"排序算 IDCG（会高估 nDCG，漏检的相关文档没有被惩罚）——本节代码正确地用 qrels 中全部分级文档；
  - 没有截断到 k；
  - 没有相关文档时 IDCG = 0，要定义返回值（本节返回 0.0）；
  - 二值 gold 与分级 qrels 不一致（Q12）。
- 加分点：讲义引用 Järvelin & Kekäläinen 的 cumulated gain 论文作为 nDCG 出处。

### Q15 — 参考回答要点

- **Faithfulness 流程**：把答案拆成原子 claim（本节用句子切分作近似）→ 对每个 claim 和检索上下文问评审模型"是否被支持（yes/no 或分级）"→ 取支持比例。讲义："The standard implementation uses an LLM-as-judge prompt that takes (claim, context) and returns yes or no."
- **Answer relevance**：把 (question, answer) 交给评审模型判断是否回应了问题；也有做法是让模型根据答案反推问题再比较相似度。
- **偏差与对策**：
  - 自评偏差：评审模型与生成模型同家族会偏向自己（讲义："Use a different model family for the judge than the generator, or hand-grade a sample"）；
  - 位置/长度偏差：长答案更容易被判为相关；
  - 非确定性：固定温度为 0、固定 prompt 版本；
  - 校准：抽取一批样本人工标注，计算评审与人工的一致率（讲义练习 3 要求比较 mock 与真实评审的分歧）。
- **宏观问题**：逐句忠实度可能全部通过，但整体结构误导；讲义建议在自动指标之上加样本级的人工定性审查。
- 加分点：提到 Ragas 等现成框架（讲义 Further Reading），但强调要理解其定义和阈值。

### Q16 — 参考回答要点

- **判断**：recall@5 和 MRR 都高，说明正确证据被找到且排得靠前；faithfulness 0.62 明显偏低，answer relevance 高——典型的"切题但编造"，问题在**生成阶段**（讲义诊断表："High MRR, low faithfulness → Generator invents content despite right context → Generation prompt; force-cite-or-refuse"）。
- **定位**：
  - 按 query 查看 faithfulness 低的样本，看是哪些 claim 不被支持（数字、实体、推断）；
  - 检查是否上下文过长导致模型忽略证据、是否提示词允许"补充常识"；
  - 用不同家族的评审模型或人工抽样复核，排除评审偏差。
- **修复**：
  - 提示词强制"每个 claim 引用 chunk 锚点，否则拒答"（第 69 节的引用格式）；
  - 降低温度、限制答案长度；
  - 生成后做 claim 级校验，不被支持的句子删除或标注；
  - 在 rank-1 分数过低时拒答（第 66、69 节）。
- **验证**：修复后重跑同一评估，faithfulness 提升且 recall/MRR/relevance 不下降才算成功；把这条回归加入 CI。

### Q17 — 参考回答要点

- **可能原因**：
  - 评估集不具代表性（讲义："Eval set is unrepresentative → Expand qrels with real user queries"）；
  - 平均值掩盖了某类 query 的系统性失败（讲义："Slice the qrels by query class (literal, paraphrased, multi-topic) and report per-slice"）；
  - qrels 过期：语料更新、函数改名后 gold 已经不对（"Qrels rot"）；
  - 指标饱和或评审器太宽松（本节 faithfulness 恒为 1.0）；
  - 评估与线上配置不一致（chunker、N、提示词版本不同）。
- **建设与维护**：
  - 从真实用户日志抽样构建 qrels，按类别切片；
  - 分层：讲义建议 20 条 smoke set 每次 CI 跑、200 条回归集每晚跑、2000 条深度集每周跑；
  - 每次修改检索器或生成器都跑评估，recall@k 回归视同测试失败；
  - 持久化每个 query 的指标轨迹，用户投诉时能对上 qrels 条目；
  - 定期（如每季度）复审 qrels，并用自动一致性检查（Q12）防止标注错误。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)：被评估的 RAG 流水线。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：评估框架与 LLM-as-judge 基础。
- [阶段 05 · 14 信息检索与搜索](../../../05-nlp-foundations-to-advanced/14-information-retrieval-search/docs/zh.md)：precision、recall、MRR、nDCG 的 IR 渊源。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)：faithfulness、answer relevance 的现成实现。
- [阶段 05 · 21 自然语言 Inference — 文本蕴涵](../../../05-nlp-foundations-to-advanced/21-nli-textual-entailment/docs/zh.md)：用 NLI 判断 claim 是否被上下文支持。
- [阶段 19 · 64 Chunking 策略比较](../../64-chunking-strategies-advanced/docs/zh.md)、[阶段 19 · 65 Hybrid Retrieval](../../65-hybrid-retrieval-bm25-dense/docs/zh.md)、[阶段 19 · 66 基于 Cross-Encoder 的 Reranker](../../66-reranker-cross-encoder/docs/zh.md)、[阶段 19 · 67 查询改写](../../67-query-rewriting-hyde/docs/zh.md)：被本节指标衡量的各个部件。

### 本节被哪些后续内容用到
- [阶段 19 · 69 端到端 RAG 系统](../../69-end-to-end-rag-system/docs/zh.md)：在完整流水线上运行本节指标并设置 CI 阈值。
- [阶段 19 · 71 经典评估指标](../../71-classical-metrics/docs/zh.md)、[阶段 19 · 75 端到端评估执行器](../../75-end-to-end-eval-runner/docs/zh.md)：更通用的评估指标与评估执行框架。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：把评估作为开发闭环的一部分。
- [阶段 19 · 11 LLM Observability 与评估仪表盘](../../11-llm-observability-dashboard/docs/zh.md)：把每个 query 的指标轨迹持久化与可视化。

### 延伸关键词
`precision@k` · `recall@k` · `hit-rate@k` · `MRR` · `nDCG / IDCG` · `graded relevance` · `qrels` · `faithfulness / groundedness` · `answer relevance` · `LLM-as-judge` · `claim extraction` · `NLI` · `Ragas` · `metric saturation` · `per-slice evaluation` · `eval tiers (smoke / regression / deep)`
