# 测验 · 端到端 RAG 系统（End-to-End RAG System）

> **阶段 19 · 综合项目 · 第 69 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义为机翻且质量较差，有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要端到端 | 讲义："Six components in isolation prove nothing."——chunker、检索、改写、重排各自的离线成绩，不能代表组合后的系统表现 |
| 2 | 稳定的阶段接口 | Chunker：文本 → `Chunk` 列表；检索：query → top-N chunk；改写：query → 改写 + 假设文档；重排：(query, 候选) → top-K（带分数）；生成：(query, top-K) → 带引用的答案 |
| 3 | `Chunk` 与引用锚点 | `Chunk(doc_id, chunk_index, text)`，锚点格式 `doc_id:chunk_index`，答案中每句后接 `[d6:0]` |
| 4 | 策略选择式改写 | 本节 `pick_strategy`：含 " and " → decompose；含 api/function/endpoint/config → hyde；否则 multiquery |
| 5 | 混合重排分数 | `blended = cross_encoder_score + 0.3 × 内容词重叠率`；docstring 说明小 cross-encoder 在训练集外 query 上噪声大，混入词法信号增加鲁棒性 |
| 6 | 带引用的 mock 生成器 | 从 top-3 中按"与 query 的内容词重叠数"选最多 2 个 chunk，各取第一句并附锚点 |
| 7 | 低置信拒答 | top-1 混合分数 < 0.05 时输出 "I do not know."；讲义称这是防幻觉的"安全阀" |
| 8 | 文档级指标 | chunk 级结果按 `doc_id` 去重后计算 recall@5、precision@1、MRR；faithfulness 与 answer relevance 沿用第 68 节思路 |
| 9 | 自终止 demo / CI 门禁 | 跑完评估，与 `THRESHOLDS` 比较，全部通过返回 0，否则返回 1 并列出失败指标——CI smoke test 的形态 |
| 10 | 讲义列出的隐藏风险 | chunker 漂移让 gold 对不上；reranker 训练集泄漏；mock 生成器掩盖幻觉风险；没有流式输出；离线延迟不含真实 LLM 调用 |

### 核心技能（能动手做到）

- [ ] 用 dataclass 组装一个五阶段 `Pipeline`，每个阶段可替换，`query()` 返回答案、引用、top-K 与分阶段延迟
- [ ] 实现递归切分 chunker、BM25 + 稠密 + RRF 的 hybrid 索引，并理解 chunk 级结果如何映射回文档级指标
- [ ] 读懂"混合分数重排"的设计动机，并通过消融实验（ablation）判断每个阶段的真实贡献
- [ ] 实现带引用和拒答的生成器，并设计能真正触发拒答的条件
- [ ] 写一个"阈值门禁"的自终止 demo，并评估阈值是否足够严格
- [ ] 识别端到端评估中的泄漏、死代码和"刚好及格"的指标

---

## 二、基础自测（选择题）

**Q1.** 本节 `Pipeline.query` 中各阶段的执行顺序是：

- A. retrieve → rewrite → rerank → generate
- B. rewrite → retrieve → rerank → generate
- C. rewrite → rerank → retrieve → generate
- D. retrieve → rerank → rewrite → generate

**Q2.** `Chunker` 默认 `target=400` 个字符，而 `CORPUS` 中 12 篇文档的长度在 89–137 个字符之间。`ingest(CORPUS)` 之后索引中有多少个 chunk？

- A. 0
- B. 24
- C. 36
- D. 12

**Q3.** 生成器在每句答案后附加的引用锚点格式是：

- A. `[d6:0]`（`doc_id:chunk_index`）
- B. `(d6)`
- C. `[0:d6]`
- D. `<cite id="d6"/>`

**Q4.** 对 eval query "how do you stop a long-running worker"，`Rewriter.pick_strategy` 选择的策略是：

- A. hyde（因为包含 worker）
- B. decompose（因为包含 long-running 中的连字符）
- C. multiquery
- D. 不改写

**Q5.** 4 个 eval query 中第一个 gold 文档的（去重后）名次分别是 1、3、1、2。demo 打印的 MRR 是：

- A. 0.500
- B. 0.708
- C. 0.750
- D. 0.875

**Q6.** `generate_answer` 在什么情况下输出 "I do not know."？

- A. 答案中的 claim 未被上下文支持时
- B. answer relevance 低于 0.3 时
- C. query 中没有内容词时
- D. `ranked` 为空，或 top-1 的混合分数低于 `REFUSE_THRESHOLD = 0.05` 时

**Q7.** 关于 `run_demo` 的"自终止"设计，说法正确的是：

- A. 所有指标 ≥ 阈值时返回 0，否则返回 1；入口处 `sys.exit(run_demo())` 把它变成进程退出码，CI 据此判定成败
- B. 它会无限循环地监听新 query，直到收到退出信号
- C. 它只打印指标，不影响进程退出码
- D. 任意一个指标高于阈值就返回 0

**Q8.** `doc_level_mrr` 遍历 chunk 级排名时维护一个 `seen` 集合，作用是：

- A. 跳过分数为 0 的 chunk
- B. 防止 gold 文档被计算两次相关度
- C. 同一文档的多个 chunk 只在第一次出现时占一个名次，名次按"不同文档"计数
- D. 记录已经被生成器引用过的文档

---

## 三、动手 / 代码题

**Q9.** 用 demo 构建好的 pipeline 问两个与语料毫不相关的问题：

```text
what is the capital of france  -> AbortMultipartOnFail aborts an in-flight S3 multipart upload ... [d1:0]
recipe for chocolate cake      -> Authorization is centralized in check_permission ... [d4:0]
```

相关代码：

```python
REFUSE_THRESHOLD = 0.05

def generate_answer(query, ranked):
    if not ranked:
        return REFUSE_TEXT, []
    top_chunk, top_score = ranked[0]
    if top_score < REFUSE_THRESHOLD:
        return REFUSE_TEXT, []
    q_tokens = _content_tokens(query)
    scored_chunks = []
    for c, s in ranked[:3]:
        overlap = len(q_tokens & _content_tokens(c.text))
        scored_chunks.append((c, overlap, s))
    scored_chunks.sort(key=lambda x: (-x[1], -x[2]))
    selected = [t for t in scored_chunks if t[1] > 0][:2] or [scored_chunks[0]]
    ...
```

1. 为什么拒答没有触发？（两处原因）
2. 修改 `generate_answer`，使"top-3 中没有任何 chunk 与 query 有内容词重叠"时拒答。
3. 修改后 eval 的 5 项指标会变吗？这说明现有评估缺了什么？

**Q10.** 我们对重排阶段做了消融实验（候选集与 pipeline 相同：multiquery 融合后的 hybrid 结果；只改变排序方式）：

| 排序方式 | precision@1 | MRR | recall@5 |
|---------|-------------|-----|----------|
| 不重排（hybrid 融合顺序） | 0.25 | 0.583 | 1.0 |
| 只用 cross-encoder（`overlap_weight=0`） | 0.25 | 0.487 | 1.0 |
| 默认混合（`overlap_weight=0.3`） | 0.50 | 0.708 | 1.0 |
| `overlap_weight=1.0` | 0.75 | 0.875 | 1.0 |
| `overlap_weight=3.0` | 0.50 | 0.750 | 1.0 |
| 只用重叠率（不用 cross-encoder） | 0.25 | 0.625 | 1.0 |

1. 单独的 cross-encoder 比"不重排"更好还是更差？结合 `TRAIN_TRIPLES` 的规模解释原因。
2. 讲义的学习目标说要"prove the staged build wins on every metric over the same components in isolation"。代码做了这样的对比吗？上表能支持这个结论吗？
3. 既然 `overlap_weight=1.0` 最好，是否应该直接把默认值改成 1.0？

**Q11.** 阅读 `Rewriter` 与 `Pipeline.query`：

```python
_REWRITE_HYDE = {
    "what is the threshold before a multipart upload is dropped":
        "The abort threshold is configured per bucket at three failed parts. Past that threshold the upload is aborted.",
    "where is the central permission gate":
        "Authorization is centralized in check_permission which evaluates a policy against the principal, the resource, and the action.",
    ...
}

    def pick_strategy(self, query):
        if " and " in query.lower():
            return "decompose"
        if any(t in tokenize(query) for t in ("api", "function", "endpoint", "config")):
            return "hyde"
        return "multiquery"

    def rewrite_hyde(self, query):
        return _REWRITE_HYDE.get(query.lower().strip().rstrip("?"))
```

1. 4 个 eval query 分别走哪种策略？`_REWRITE_HYDE` 的内容在 demo 中有没有被用到过？
2. 证明：在当前代码下，`_REWRITE_HYDE` 对**任何** query 都不可能被用到。当一个 query 被判为 "hyde" 时，实际发生了什么？
3. 如果有人"修好"了这个分支，让 eval query 能用上这张表，评估结果还可信吗？为什么？

**Q12.** 用小一点的 `target` 观察 `_recursive_split`：

```python
>>> _recursive_split("Large files are split into parts. Cancelled uploads release the reserved keys after three failed parts.", DEFAULT_SEPARATORS, 60)
['Large files are split into parts', 'Cancelled uploads release the reserved keys after three', 'failed parts.']
```

1. 解释这三个 chunk 是怎么产生的，指出第一个 chunk 丢了什么。
2. 如果 d2 被切成这样，eval 的文档级指标会受影响吗？生成器的答案会受影响吗？
3. 讲义的 "Chunker boundary drift" 说"Lock the chunker strategy in the qrels file. The demo includes a header that names the chunker." demo 真的打印了 chunker 信息吗？你会怎么实现这个"锁定"？

---

## 四、面试高频题

**Q13.**（基础必考）请画出一个生产 RAG 系统从入库到回答的完整链路，说明每个阶段的输入输出，以及你会在哪些位置打点评估。

**Q14.**（原理深挖）为什么"各组件单独评估都很好"不代表"系统整体好"？请举出至少三种组件之间相互作用导致的失败。

**Q15.**（工程实践）你要把这个 pipeline 的评估接入 CI：smoke set、阈值、失败处理分别怎么设计？如何避免"阈值形同虚设"？

**Q16.**（场景设计）设计一个"引用 + 拒答"的生成阶段：prompt 怎么写，拒答信号从哪里来，如何验证拒答机制有效？

**Q17.**（追问型）面试官看了你的 demo："四个 eval query 全部 PASS，所以系统可以上线了？"你如何回应？

---

## 五、参考答案与解析

### Q1 — 答案：B

`query()` 中依次计时 `latencies["rewrite"]`、`["retrieve"]`、`["rerank"]`、`["generate"]`。改写必须在检索之前（讲义："Rewrite --> Retrieve"），重排作用在检索结果上，生成使用重排后的 top-K。其余选项的顺序在数据依赖上都不成立：A 先检索再改写，改写结果无处可用；C、D 在检索之前就无法重排。

### Q2 — 答案：D

`_recursive_split` 第一行：`if len(text) <= target or not separators: return [text] if text else []`。所有文档都短于 400 字符，各自成为 1 个 chunk，共 12 个——demo 打印的 `chunks indexed: 12` 证实了这一点。也就是说，**在这个 fixture 上 chunker 什么也没做**，chunk 与文档一一对应，文档级去重逻辑也从未真正起作用。

### Q3 — 答案：A

`Chunk.anchor()` 返回 `f"{self.doc_id}:{self.chunk_index}"`，生成器写 `f"{first_sentence} [{c.anchor()}]"`。demo 输出：`... reciprocal rank fusion at k = 60. [d6:0]`。讲义："Emits an answer that is a concatenation of one-sentence-from-each-selected-chunk, with each sentence followed by a `[doc_id:chunk_index]` anchor."

### Q4 — 答案：C

该 query 不含 " and "（`long-running` 中是连字符，`tokenize` 会把它拆成 `long`、`running`），也不含 api/function/endpoint/config，于是落到默认的 multiquery。实际上 4 个 eval query 全部走 multiquery。A 错，worker 不在 hyde 关键词表里；B 错，判断依据是空格包围的 " and "。

### Q5 — 答案：B

`(1/1 + 1/3 + 1/1 + 1/2) / 4 = 2.8333 / 4 = 0.708`。e2 的 top-K 是 d1、d3、d4…（gold d4 在第 3），e4 是 d3、d7…（gold d7 在第 2）。C（0.750）是 e2 排第 2 时的值；D（0.875）是消融中 `overlap_weight=1.0` 的结果（见 Q10）。

### Q6 — 答案：D

代码只有两个拒答出口：`if not ranked` 和 `if top_score < REFUSE_THRESHOLD`。A、B 是评估指标，生成器不会调用它们；C 不成立——query 没有内容词时 `overlap` 全为 0，代码会走 `or [scored_chunks[0]]` 兜底，仍然输出 top-1 chunk 的第一句（这正是 Q9 的问题所在）。

### Q7 — 答案：A

`run_demo` 末尾：有失败指标就打印 `== demo FAILED: [...] ==` 并 `return 1`，否则 `return 0`；入口 `sys.exit(run_demo())` 把返回值变成进程退出码。讲义："exits with status zero if all the lesson 68 metrics meet the thresholds... If any metric is below threshold, the demo exits with a non-zero status and a message naming the failing metric." B、C 不成立；D 把"全部满足"说成了"任意一个满足"。

### Q8 — 答案：C

```python
    for c, _ in retrieved_chunks:
        if c.doc_id in seen:
            continue
        seen.add(c.doc_id)
        rank += 1
        if c.doc_id in gold:
            return 1.0 / rank
```

名次只在遇到**新文档**时加 1，同一文档的后续 chunk 被跳过，这样 chunk 粒度变化不会改变文档级 MRR。测试 `test_mrr_first_unique_doc` 验证了这一点。（本 fixture 每篇只有 1 个 chunk，所以这段逻辑实际上没有被触发过。）

### Q9 — 参考答案

1. 两处原因：
   - **阈值作用在未校准的分数上**：混合分数 = cross-encoder 回归分数 + 0.3 × 重叠率。cross-encoder 用 MSE 在 17 条三元组上训练，对任何输入都会给某些文档打出接近 1 的分数（"capital of france" 的 top-1 是 d1，分数 1.032）。0.05 的阈值几乎不可能被触及。
   - **生成器的兜底**：`[t for t in scored_chunks if t[1] > 0][:2] or [scored_chunks[0]]`——即使 top-3 与 query 没有任何内容词重叠，也会退回 top-1 chunk 作答。
2. 参考修改（已运行验证）：

```python
def generate_answer(query, ranked, min_overlap=1):
    if not ranked or ranked[0][1] < REFUSE_THRESHOLD:
        return REFUSE_TEXT, []
    q_tokens = _content_tokens(query)
    scored = [(c, len(q_tokens & _content_tokens(c.text)), s) for c, s in ranked[:3]]
    scored.sort(key=lambda x: (-x[1], -x[2]))
    selected = [t for t in scored if t[1] >= min_overlap][:2]
    if not selected:                                  # 去掉 "or [scored[0]]" 兜底
        return REFUSE_TEXT, []
    sentences, citations = [], []
    for c, _, _ in selected:
        first = re.split(r"(?<=[.!?])\s+", c.text.strip(), maxsplit=1)[0]
        sentences.append(f"{first} [{c.anchor()}]")
        citations.append(c.anchor())
    return " ".join(sentences), citations
```

   验证：两个无关问题以及 "how do you bake a cake before the party" 都输出 "I do not know."；4 个 eval query 的答案不变。
3. 不会变（实测修改前后都是 recall@5 1.0、precision@1 0.5、MRR 0.708、faithfulness 1.0、answer relevance 1.0）。原因是 eval 集里**没有任何"应该拒答"的 query**，拒答路径完全没有被评估覆盖。应该加入 out-of-domain query，并增加"拒答准确率 / 误答率"指标（第 68 节 answer relevance 在这里也能捕捉到：拒答前的错误答案与问题毫无重叠，relevance 为 0）。

### Q10 — 参考答案

1. **更差**：只用 cross-encoder 时 MRR 从 0.583 降到 0.487。训练集只有 17 条三元组、4 个 query 类，而模型有 416,929 个参数（实测，主要在 8192 × 48 的 token embedding），训练 80 轮后 loss 降到约 7e-5——这是记忆而不是泛化。eval query 的措辞都不在训练集里，cross-encoder 在这些 query 上的打分近乎噪声（例如 e2 "where is the central permission gate" 的纯 cross-encoder top-1 是 d1，一篇分片上传文档）。docstring 自己也承认："A small cross-encoder (this lesson) is noisy on out-of-training-set queries."
2. **没有**。代码只跑了组装后的 pipeline，没有任何"组件单独运行"的对照组。上表也不支持"wins on every metric"：recall@5 各种做法都是 1.0（N = 12 等于全库，第一阶段没有过滤任何东西）；precision@1 与 MRR 的提升来自"cross-encoder + 词法重叠"的**混合**，而两个成分单独使用都不如混合，甚至 cross-encoder 单独使用不如不重排。讲义的说法在本代码中没有被证明。
3. **不应该**。4 个 eval query 既用来选 `overlap_weight` 又用来报告指标，就是在测试集上调参，结论会过拟合；`overlap_weight=3.0` 又变差，说明曲线并不平滑。正确做法：准备独立的验证集调参，在另一个测试集上报告；同时更根本的是换一个真正能泛化的 reranker（预训练 checkpoint 微调）。

### Q11 — 参考答案

1. 4 个 eval query 都不含 " and "，也不含 api/function/endpoint/config，全部走 **multiquery**。`_REWRITE_HYDE` 从未被用到。
2. 证明：`rewrite_hyde` 只有在 query（小写、去末尾问号后）**恰好等于**表中的 4 个 key 之一时才返回非 None；而 `pick_strategy` 只有在 query 含有 api/function/endpoint/config 时才返回 "hyde"。表中 4 个 key 都不含这些词，两个条件不可能同时满足，所以这张表是**不可达的死代码**。当某个 query 被判为 "hyde"（如 "which config controls the abort threshold"）时：`hypothetical = None`，`subqueries` 为空列表，`if hypothetical:` 和 `elif len(subqueries) > 1:` 都不成立，最终走 `else` 分支用原 query 直接检索——"hyde" 策略实际上等同于**不改写**，但 `rewriter_strategy` 仍报告为 "hyde"，具有误导性。
3. 不可信。表中的"假设文档"几乎是 gold 文档的**原文**（例如 e1 的假设文档与 d3 正文逐字相同，e4 与 d7 相同），等于把答案直接塞进了检索向量，属于评估泄漏。真实 HyDE 由 LLM 生成，LLM 并不知道你的语料。若要演示 HyDE，应当让假设文档用"领域常识但非语料原文"的措辞，并在与 eval 不同的 query 上设计。

### Q12 — 参考答案

1. 过程：文本 104 字符 > 60，按第一个出现在文本中的分隔符切（`"\n\n"`、`"\n"` 都不在，用 `". "`）：得到 `"Large files are split into parts"`（32 字符）和 `"Cancelled uploads ... three failed parts."`（68 字符）。后者仍 > 60，递归用 `" "` 切成单词，再在内层按 60 字符贪心打包成 `"Cancelled uploads release the reserved keys after three"` 和 `"failed parts."`。外层打包时，第一段与第二段用 `". "` 相连会超过 60，所以各自独立。第一个 chunk **丢掉了句号**——`str.split(sep)` 会删除分隔符，只有在打包时被重新拼接的位置才会补回分隔符，chunk 边界处的分隔符就丢失了。另外 "three failed parts" 这个关键事实被切成了两半。
2. 文档级 recall/precision/MRR 按 `doc_id` 去重，chunk 拆分不会改变 gold 是否被找到的判断（只要任意一个 chunk 进入 top-K），但会影响排名（关键事实被拆开，单个 chunk 的匹配分数下降）。生成器只取每个 chunk 的**第一句**，若选中 `d2:1`，答案会是一句被截断的话 "Cancelled uploads release the reserved keys after three [d2:1]"，信息残缺且有误导性。
3. 没有。`run_demo` 只打印 `chunks indexed: 12`，没有打印 chunker 的策略或参数。实现"锁定"：在 qrels 文件中记录 chunker 配置（策略名、`target`、`separators`）及其哈希，并让 gold 标注到 chunk 锚点；评估开始时比较当前 `Chunker` 配置与 qrels 中的记录，不一致就直接失败并提示"需要重新标注"。

### Q13 — 参考回答要点

- **入库**：文档解析 → 清洗 → chunking（策略、大小、重叠）→ 为每个 chunk 生成 BM25 统计与向量 → 写入 hybrid 索引；记录 chunk 锚点（doc_id、chunk_index、版本）。
- **查询**：改写（HyDE / multi-query / decomposition，按策略选择）→ hybrid 检索 top-N（BM25 + 稠密 + RRF）→ cross-encoder 重排 top-K → 生成（带引用、低置信拒答）→ 返回答案与引用。
- **评估打点**（第 68 节）：
  - 检索后：recall@N（第一阶段是否找到证据）；
  - 重排后：MRR、nDCG@K、precision@1；
  - 生成后：faithfulness（claim 是否被 top-K 支持）、answer relevance、拒答准确率；
  - 每阶段的延迟（本节 `latency_ms`），并注意离线延迟不含真实 LLM 调用（讲义 "Latency is offline"）。
- 加分点：讲义建议用一个编排文件声明全部阶段接口，避免把胶水代码散落在仓库各处。

### Q14 — 参考回答要点

- 讲义给出的三个例子：
  - chunker 单独看 recall@5 很好，但检索器无法对它产出的 chunk 排序，系统 recall 下降；
  - reranker 在合成候选池上 MRR 提升明显，但真实 bi-encoder 在 rerank 预算 N 处的 recall 太低，reranker 没有正确候选可选；
  - 改写器在一个 query 上把 gold 提上来，下一个 query 上 mock LLM 给出退化的假设文档，反而把结果带偏。
- 本节代码中的实例：
  - cross-encoder 单独使用比不重排更差（Q10），必须与词法信号混合才有提升；
  - 生成器从 top-3 中按重叠重新挑 chunk，使得 precision@1 只有 0.5 但答案相关性仍为 1.0——阶段之间会互相"掩盖"问题；
  - 拒答阈值依赖重排分数的尺度，重排模型一换，阈值就失效（Q9）。
- 结论：必须在同一套 qrels、同一套指标上跑完整 pipeline，并做消融实验，才能把提升归因到具体阶段。

### Q15 — 参考回答要点

- **分层**：讲义建议 20 条 smoke set 在每个 PR 上运行（30 秒内），完整回归集每晚运行；第 68 节建议再加每周的深度集。
- **阈值**：
  - 基于当前主分支的指标设置"不得回退"的阈值（如 recall@5 不低于当前值 − 0.02），而不是随手的固定值；
  - 本节 precision@1 = 0.500 恰好等于阈值 0.50，任何微小扰动都会导致失败或侥幸通过——要么修复系统，要么承认阈值没有余量；faithfulness 结构性为 1.0，阈值 0.75 不起任何作用；
  - 讲义说"The thresholds are deliberately tight"，但从上述情况看并不"tight"，只是"刚好过"。
- **失败处理**：失败时打印具体指标与失败的 query 列表；持久化每次 CI 的指标轨迹，方便归因到某个阶段的修改（讲义 "Persist the metric trace per CI run"）。
- **防止形同虚设**：加入困难样本与应拒答样本；定期检查指标是否饱和；对确定性要求高的部分固定随机种子（本节 `CrossEncoder` 构造时固定种子）。

### Q16 — 参考回答要点

- **Prompt**（讲义模板）："You are answering a question using only the snippets below. Cite every claim with the anchor in parentheses. If the snippets do not answer the question, say 'I do not know'."，并把 snippets 以 `[doc_id:chunk_index]` 编号列出。
- **拒答信号**：
  - 检索/重排侧：rank-1 重排分数低于按语料校准的阈值（讲义："The refuse-on-low-confidence path is the whole reason the cross-encoder rank-1 score is logged"）；分数需校准（sigmoid/温度缩放），不能用本节这种无界回归分数；
  - 证据侧：top-K 与 query 没有实质重叠（Q9 的修复）；
  - 生成侧：模型自己声明无法回答；生成后 claim 级校验发现不被支持的句子。
- **验证**：评估集中加入一定比例的 out-of-domain / 无答案 query，统计"应拒答而拒答"（召回）与"不应拒答却拒答"（误拒），画出随阈值变化的曲线选阈值；上线后监控拒答率的变化。
- 常见误区：只在 in-domain query 上评估，看不到拒答路径是否生效（本节就是如此）。

### Q17 — 参考回答要点

- **样本量太小**：4 个 query，单个 query 的变化就让 precision@1 改变 0.25。
- **指标刚好及格或饱和**：precision@1 恰好 0.50；faithfulness 因为抽取式生成恒为 1.0；recall@5 因为 N = 全库恒为 1.0。
- **泄漏风险**：reranker 的训练文档就是语料原文，困难负例正是 eval 的干扰文档（d9、d10、d11、d12），讲义虽说 eval query 与训练 query 不重叠，但文档层面高度重叠；`_REWRITE_HYDE` 若被启用会直接泄漏答案。
- **覆盖不足**：没有 out-of-domain query（拒答路径未测，实测会对"法国首都"作答），没有多 chunk 文档（chunker 和去重逻辑未被触发），没有 decomposition/HyDE 路径的 query。
- **离线 ≠ 线上**：mock 生成器不会幻觉，延迟不含真实 LLM 调用（讲义 "Mock generator hides hallucination risk"、"Latency is offline"）。
- **回应**：PASS 只说明"在这 4 个 query 上没有回归"，上线前需要更大的、分类别的评估集、消融实验、拒答测试、真实模型的忠实度评审，以及线上灰度与监控。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)：RAG 的基本流程。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：评估与 CI 门禁的基础。
- [阶段 19 · 64 Chunking 策略比较](../../64-chunking-strategies-advanced/docs/zh.md)：本节默认的递归切分 chunker。
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../65-hybrid-retrieval-bm25-dense/docs/zh.md)：`HybridIndex` 的来源。
- [阶段 19 · 66 基于 Cross-Encoder 的 Reranker](../../66-reranker-cross-encoder/docs/zh.md)：压缩版 cross-encoder 的来源。
- [阶段 19 · 67 查询改写：HyDE、多查询与查询分解](../../67-query-rewriting-hyde/docs/zh.md)：策略选择式改写的来源。
- [阶段 19 · 68 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性](../../68-rag-eval-precision-recall/docs/zh.md)：本节指标与阈值的来源。

### 本节被哪些后续内容用到
- [阶段 19 · 02 代码库 RAG——跨仓库 Semantic Search](../../02-rag-over-codebase/docs/zh.md)、[阶段 19 · 08 面向受监管行业的生产级 RAG 聊天机器人](../../08-production-rag-chatbot/docs/zh.md)：把同样的流水线用到真实项目中。
- [阶段 19 · 75 端到端评估执行器](../../75-end-to-end-eval-runner/docs/zh.md)：更通用的"跑评估、按阈值决定成败"的执行框架。
- [阶段 11 · 13 构建生产环境中的 LLM 应用](../../../11-llm-engineering/13-production-app/docs/zh.md)：服务化、流式输出与上线实践（本节讲义列为范围之外）。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：分阶段延迟与指标轨迹的线上监控。

### 延伸关键词
`end-to-end RAG` · `stage interface` · `recursive character splitting` · `hybrid retrieval` · `RRF` · `strategy selector` · `score blending` · `citation anchor` · `refuse-on-low-confidence` · `score calibration` · `ablation study` · `CI eval gate` · `smoke set` · `data leakage` · `out-of-domain detection`
