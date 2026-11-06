# 测验 · 代码库 RAG——跨仓库 Semantic Search（Capstone 02 — RAG over Codebase (Cross-Repo Semantic Search)）

> **阶段 19 · 综合项目 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：本节中文讲义是质量很差的机器翻译（如把 "engineering org" 译成"工程大猩猩"、把 "tree-sitter" 译成"树质保存器"），有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么不能只做余弦检索 | 讲义："Naive cosine search over raw chunks poisons results on generated code, on monorepo duplication, and on the long tail of rarely-imported symbols"；1M token 上下文也不能替代排序检索 |
| 2 | AST-aware chunking | 用 tree-sitter 在函数/类节点边界切块，而不是固定 token 窗口；每块记录 `{repo, path, start_line, end_line, symbol, body}`，行号就是之后的引用锚点 |
| 3 | 每个 chunk 的三种表示 | dense embedding、BM25 稀疏词项、一句话自然语言 summary；summary 让"how is X authorized"能命中只写了 `check_permission` 的代码 |
| 4 | Hybrid 检索 | dense 与 BM25 并行检索、合并 top-k、去重，再交给 cross-encoder reranker；BM25 擅长精确符号名，dense 擅长语义改写 |
| 5 | Reciprocal Rank Fusion（RRF） | `score(d) = Σ 1/(k + rank)`，本节 `k_rrf = 60`、rank 从 1 起；只用名次不用原始分数，天然免去 dense 与 BM25 分数尺度不一致的问题 |
| 6 | BM25 与字段加权 | `idf · f·(k1+1) / (f + k1·(1−b+b·dl/avgdl))`，本节 `k1=1.5, b=0.75`；讲义的 BM25F 权重：symbol 4、summary 2、body 1，代码用"重复 token"近似 |
| 7 | Cross-encoder rerank | 把 (query, candidate) 拼在一起打分，比双塔余弦准但贵，只对 top-50 之类的小候选集做；本节代码用"词重叠"打分的 stub 代替 |
| 8 | 引用强制（citation enforcement） | 每个论断必须带 `(repo/path:start-end)` 锚点，没有锚点的论断重问或丢弃；对应指标 citation faithfulness |
| 9 | 增量重建索引 | git push → webhook → 符号级 diff → 只重新 embed 文本变化的 chunk、只重算受影响的符号边；目标：2M LOC、50 文件的 push 60 秒内可搜 |
| 10 | 评估 | 100 道带金标准 file:line 的跨仓库问题：MRR@10、nDCG@10、citation faithfulness、p50/p99 延迟；每周重跑，MRR@10 掉超过 5% 告警 |

### 核心技能（能动手做到）

- [ ] 从零写出 BM25（含 IDF、长度归一化）并手算一个词的 IDF
- [ ] 实现 RRF，并能手算"dense 第 1、BM25 第 2"这类文档的融合分数
- [ ] 指出本节代码 `fake_embed` 用 `hash()` 导致**跨进程不确定**的问题，并给出确定性哈希的修复
- [ ] 解释 `tokenize` 不拆分 `camelCase` / `snake_case` 时，symbol 字段加权和 reranker 的 symbol 重叠为什么全部失效
- [ ] 写出一个 citation post-filter：解析 `(repo/path:start-end)` 锚点，校验它是否落在检索到的 chunk 行号范围内
- [ ] 手算 MRR@10 与 nDCG@10，并设计一个代码 RAG 的离线评估集
- [ ] 画出 git push 触发增量重建索引的流程，说清"哪些东西需要重算、哪些不需要"

---

## 二、基础自测（选择题）

**Q1.** 讲义要求用 tree-sitter 做 AST-aware chunking，而不是固定 512 token 窗口。最核心的理由是：

- A. 每个 chunk 恰好是一个完整的函数或类，语义完整，且自带精确的 `start_line`/`end_line`，可直接作为引用锚点
- B. AST 切块后 chunk 数量更少，向量库存储成本一定更低
- C. tree-sitter 能把代码翻译成自然语言，省掉 summary 步骤
- D. 固定窗口切块无法被 BM25 索引

**Q2.** 本节 `rrf()` 使用 `k_rrf = 60`、名次从 1 开始。某个 chunk 在 dense 结果中排第 1、在 BM25 结果中排第 2，它的 RRF 分数约为：

- A. 0.0164
- B. 0.0328
- C. 0.0161
- D. 0.0325

**Q3.** 在代码检索中，BM25 与 dense 检索并行使用，BM25 最主要的补充价值是：

- A. BM25 能理解同义改写，比如把 "authorization" 和 "permission" 对应起来
- B. 对精确的符号名、错误码、配置键等"字面匹配"类查询召回稳定，而 dense embedding 在这类长尾标识符上容易失手
- C. BM25 的分数和余弦相似度在同一尺度上，可以直接相加
- D. BM25 不需要建立索引

**Q4.** 本节 `BM25Index.search` 的 IDF 为 `log((n − df + 0.5)/(df + 0.5) + 1)`。语料共 6 个 chunk，某个词只出现在 1 个 chunk 中，它的 IDF 约为：

- A. 0.693
- B. 1.030
- C. 1.540
- D. 1.792

**Q5.** 关于 cross-encoder reranker，下列说法正确的是：

- A. 它把 query 与每个候选拼在一起送入模型打分，比双塔向量的余弦更准，但每个候选都要做一次前向，所以只用于对已召回的小候选集（如 top-50）重排
- B. 它预先为所有 chunk 计算向量，查询时只需做一次点积，因此可以替代第一阶段召回
- C. 它的作用是把 chunk 压缩后再送给合成模型
- D. 它只能处理自然语言，不能处理代码

**Q6.** 连续运行两次 `python main.py`，第一个问题的 `dense` 行在两次运行中可能不同，而 `sparse` 行始终一致。原因是：

- A. `DenseIndex.search` 内部使用了 `random.shuffle`
- B. BM25 的 `avgdl` 每次运行都会重新计算
- C. `fake_embed` 用的是 Python 内置 `hash()`，字符串哈希在每个进程里加了随机盐（受 `PYTHONHASHSEED` 控制），于是每次运行"词 → 维度"的映射都不同
- D. 余弦相似度在浮点数上本身不确定

**Q7.** 对查询 `"how does rank fusion work"`，`rerank()` 中 `rank_fusion` 这个 chunk 的 `len(q_toks & set(tokenize(c.symbol)))`（symbol 重叠词数）等于：

- A. 2（rank 和 fusion 都命中）
- B. 6（2 个词 × 3 倍权重）
- C. 1
- D. 0

**Q8.** 讲义对增量重建索引的要求是：50 个文件的 push 在 2M LOC 规模下 60 秒内可搜。下列做法中最符合讲义设计的是：

- A. 每次 push 都对全部 2M 行重新 embedding，保证一致性
- B. 计算符号级 diff，只对文本发生变化的 chunk 重新 embed，并只重算 import 发生变化的 chunk 的符号边
- C. 只更新 BM25 索引，dense 向量每月全量重建一次
- D. 删除符号图，只保留向量索引，以减少更新工作量

---

## 三、动手 / 代码题

**Q9.** `main.py` 的模块 docstring 写着 "hash-based fake embeddings so the loop runs deterministically offline"：

```python
def fake_embed(text: str, dim: int = 64) -> list[float]:
    """Hash-based deterministic embedding; stands in for Voyage-code-3."""
    vec = [0.0] * dim
    for tok in re.findall(r"\w+", text.lower()):
        h = hash(tok)
        vec[h % dim] += 1.0
        vec[(h >> 8) % dim] += 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
```

1. 这句"deterministically"成立吗？怎样用一条命令验证？
2. 给出一个修复，使不同进程、不同机器上的结果一致。
3. 修好之后，这个"dense 检索"能体现 semantic search 的效果吗？为什么？

**Q10.** 语料中 6 个 chunk 的 symbol 分别是 `AbortMultipartOnFail`、`bucket_budget`、`abortUpload`、`check_permission`、`evaluate`、`rank_fusion`，而分词函数是：

```python
def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())
```

1. 写出这 6 个 symbol 经过 `tokenize` 后的结果。
2. 这会让 `BM25Index.add` 中的 `tokenize(chunk.symbol) * 4` 和 `rerank` 中的 `symbol_overlap` 起到什么作用？
3. 写一个 `split_identifier(s)`，把 `camelCase`、`PascalCase`、`snake_case` 拆成小写子词，并说明它应该用在哪里。

**Q11.** 阅读 `rerank`：

```python
def rerank(query, candidates, top_k=5):
    q_toks = set(tokenize(query))
    out = []
    for c, prior in candidates:
        symbol_overlap = len(q_toks & set(tokenize(c.symbol))) * 3
        summary_overlap = len(q_toks & set(tokenize(c.summary)))
        out.append((c, prior + 0.3 * symbol_overlap + 0.1 * summary_overlap))
    out.sort(key=lambda x: -x[1])
    return out[:top_k]
```

1. `prior` 是 RRF 分数，它的取值上限是多少？与 `0.1 * summary_overlap` 相比，最终排序主要由谁决定？
2. 对第一个问题 "how is S3 multipart abort wired into retry budget"，`AbortMultipartOnFail`、`abortUpload`、`bucket_budget` 三个 chunk 的 summary 重叠词分别是哪些、各几个？
3. 为什么第三个问题 "how does rank fusion work" 的最终 top-5 里会出现与 rank fusion 毫不相关的 `auth/libs/policy/opa.py` 之类的 chunk？这对"引用"意味着什么？

**Q12.** 评估与引用强制：

1. 三个问题的金标准分别排在第 1、第 2、未进入前 10，MRR@10 是多少？
2. 某问题有 2 个相关 chunk，系统返回的前 5 名相关性为 `[0, 1, 0, 1, 0]`（二值），nDCG@5 是多少？
3. 写一个 `enforce_citations(answer, known)`：把答案按句切开，只保留"至少带一个锚点、且所有锚点都落在已检索 chunk 行号范围内"的句子。

---

## 四、面试高频题

**Q13.**（基础必考）请描述一个代码库 RAG 的查询链路：从用户问题到带 file:line 引用的答案，每一步做什么？为什么融合 dense 与 BM25 时常用 RRF 而不是直接把分数相加？

**Q14.**（原理深挖）写出 BM25 的打分公式，解释 `k1`、`b`、IDF 各自的作用。本节用"把 symbol 的 token 重复 4 次"来实现字段加权，这与真正的 BM25F 有什么区别？

**Q15.**（工程实践）讲义要求 git push 后 60 秒内让 50 个改动文件可搜。请设计增量重建索引：需要存哪些元数据？如何判断哪些 chunk 要重算？删除和重命名文件怎么处理？如何保证 dense、BM25、符号图三者一致？

**Q16.**（场景设计）你负责给公司内部的代码问答系统做离线评估和线上监控。请设计评估集、指标、回归门槛与漂移告警，并说明如何检测"生成代码污染检索"的问题（讲义练习 2）。

**Q17.**（追问型）"Claude 已经有 1M token 上下文了，把整个仓库塞进去不就行了，还要检索干什么？"你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：A

AST-aware chunking 的价值有两层：一是**语义完整**，一个函数不会被拦腰截断，也不会把两个不相关函数拼进同一块；二是**天然的引用锚点**，每块自带 `start_line`/`end_line`，答案可以引用 `repo/path:start-end`，用户点开就能核对。讲义 Key Terms："Cutting code at tree-sitter node boundaries instead of fixed token windows"。

- B 错：chunk 数量取决于函数大小分布，不一定更少；超长函数还要再拆。
- C 错：自然语言 summary 由 LLM（讲义用 Haiku 4.5）生成，tree-sitter 只做语法解析。
- D 错：任何文本都能被 BM25 索引。

### Q2 — 答案：D

`1/(60+1) + 1/(60+2) = 0.016393 + 0.016129 = 0.032522`（已用 Python 计算）。代码中 `rank` 来自 `enumerate`（从 0 开始），所以写成 `1.0 / (k_rrf + rank + 1)`。

- A（0.0164）只算了 dense 第 1 名一项；C（0.0161）只算了 BM25 第 2 名一项；B（0.0328 = 2/61）是"两路都排第 1"的上限。

实际运行中你能看到 `abortUpload` 与 `AbortMultipartOnFail` 一个是"dense 1、BM25 2"，另一个是"dense 2、BM25 1"，两者 RRF 分数完全相同（都是 0.03252）；`sorted` 是稳定排序，平局时按插入顺序（先出现在 dense 列表中的在前）。

### Q3 — 答案：B

BM25 是精确词项匹配，查询里出现 `AbortMultipartOnFail`、`ERR_BUDGET_EXHAUSTED`、`abort_threshold` 这类标识符时，只要索引里有同样的 token 就能稳定命中。dense embedding 对罕见标识符往往"认不出来"。skill 文件的 hard reject 也写了："Cosine-only retrieval without BM25 or rerank. Known to fail on exact-symbol-name queries."

- A 说反了：理解同义改写是 dense 的长处。
- C 错：BM25 分数无上界（本节第一个问题最高约 6.41），余弦在 [−1, 1]，尺度不同，这正是要用 RRF 的原因。
- D 错：BM25 需要倒排统计（df、tf、文档长度）。

### Q4 — 答案：C

`ln((6 − 1 + 0.5)/(1 + 0.5) + 1) = ln(4.667) ≈ 1.540`。

- A（0.693 = ln 2）是 df = 3 时的值；B（1.030 = ln 2.8）是 df = 2 时的值；D（1.792 = ln 6）是朴素 `log(N/df)`。
- 公式里的 `+1` 是 Lucene 的做法，保证 IDF 恒为正；原始 Robertson IDF 在 df > N/2 时会变成负数。

### Q5 — 答案：A

cross-encoder 把 `[query; candidate]` 一起编码，注意力可以在两者之间交互，因而比"各自编码再求余弦"的双塔（bi-encoder）更准；代价是不能预计算，每个候选都要一次前向。所以标准做法是两阶段：便宜的召回（dense + BM25）取 top-50，再用 cross-encoder 精排保留 top-10（讲义 Build It 第 6 步）。

- B 描述的是 bi-encoder。
- C 是"上下文压缩"，不是 rerank。
- D 错：讲义用的 Cohere rerank-3、bge-reranker-v2-gemma-2b 都可以处理代码文本。

### Q6 — 答案：C

Python 3.3 起，`str` 的 `hash()` 默认加随机盐（防哈希碰撞 DoS），每个进程不同。`fake_embed` 用 `hash(tok) % dim` 决定词落在哪一维，于是每次运行的"向量空间"都不一样。我们不设种子运行一次、再用 `PYTHONHASHSEED=0/1/2/3` 各运行一次，5 次运行中第一个问题的 dense top-3 出现了 4 种不同排序（例如 seed=2 时 `multipart.ts` 排第一，seed=0 时 `budgets.yaml` 排第二）。BM25 只依赖 `Counter` 计数，与哈希无关，所以 `sparse` 行稳定。

- A、B、D 都不成立：代码里没有随机打乱；`avgdl` 每次算出的值都一样；浮点运算在同一输入下是确定的。

### Q7 — 答案：D

`\w` 包含下划线，`tokenize("rank_fusion")` 得到的是**一个** token `['rank_fusion']`，与查询 token `{'how','does','rank','fusion','work'}` 的交集为空，所以重叠为 0。`rank_fusion` 能排第一，完全靠 summary 里的 `rank`、`fusion`（`0.1 × 2 = 0.2`）和 RRF 先验。

- A 是"如果正确拆分了标识符"才会得到的值；B 是再乘 3 之后的 `symbol_overlap` 变量值（同样是假设拆分正确）；C 无依据。

### Q8 — 答案：B

讲义 Build It 第 8 步："compute the symbol-level diff. Only re-embed chunks whose text changed. Recompute symbol edges for chunks whose imports changed."

- A 正是 skill 文件的 hard reject："Full-corpus re-embedding on every git push; must be incremental."
- C 让 dense 与 BM25 不一致，期间会出现"BM25 能搜到、dense 搜不到"的错位。
- D 丢掉了跨仓库符号解析能力（讲义练习 5 依赖符号图）。

### Q9 — 参考答案

1. **不成立。** `hash()` 对字符串加了每进程随机盐。验证：
   ```bash
   for s in 0 1 2; do PYTHONHASHSEED=$s python main.py | grep dense | head -1; done
   ```
   我们实际运行得到三种不同的 dense top-3。不设 `PYTHONHASHSEED` 时每次运行也可能不同。
2. **修复**：换成与进程无关的确定性哈希，例如
   ```python
   import zlib
   h = zlib.crc32(tok.encode("utf-8"))
   ```
   或 `int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "little")`。我们用 `zlib.crc32` 替换后，在 `PYTHONHASHSEED=0` 和 `1` 下输出完全一致。同一课的 TypeScript 版本（`code/ts/src/index_store.ts`）就用了 FNV-1a，并注释 "so embeddings are stable across runs"——Python 版漏了这一点。
3. **不能。** 这个"embedding"本质是**带哈希碰撞的词袋**：只有词形完全相同才会贡献相似度，`authorization` 与 `permission`、`authz` 之间没有任何联系；64 维还会让无关词碰撞到同一维，产生噪声相似度（用 `zlib.crc32` 修好后，第三个问题 "how does rank fusion work" 的 dense 第一名竟是与 rank fusion 无关的 `retry.go`，`query.rs` 只排第二）。它只用来让"两路检索 + 融合 + 重排"的流程能离线跑通。真正的语义能力需要换成 Voyage-code-3 / nomic-embed-code 等模型（讲义练习 1）。

### Q10 — 参考答案

1. 实际结果：`['abortmultipartonfail']`、`['bucket_budget']`、`['abortupload']`、`['check_permission']`、`['evaluate']`、`['rank_fusion']`——除 `evaluate` 外全是"整个标识符一个 token"。
2. 后果：
   - BM25 中 symbol ×4 的加权只对"用户原样输入完整标识符"的查询有用；自然语言查询（"abort upload"）一个都命中不了。讲义说字段加权是为了同时支持"find the function named X"和"find the function that does X"，前者在本实现里只对完整拼写生效。
   - `rerank` 的 `symbol_overlap` 在三个示例问题上**全部为 0**（我们逐个打印验证过），`0.3 * symbol_overlap` 这一项形同虚设，rerank 实际只看 summary 重叠。
3. 参考实现（已运行验证）：
   ```python
   import re

   def split_identifier(s: str) -> list[str]:
       s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)   # camelCase -> camel Case
       return re.findall(r"[a-z0-9]+", s.lower())       # 下划线、点号等都当分隔符
   ```
   输出：`['abort','multipart','on','fail']`、`['bucket','budget']`、`['abort','upload']`、`['check','permission']`、`['evaluate']`、`['rank','fusion']`。
   用法：在建索引和查询两侧**同时**使用（否则两边 token 对不上）。生产中常见做法是保留原始标识符 token **并**追加拆分后的子词，这样既能精确匹配全名，也能部分匹配。若 `split_identifier` 用于 rerank 的 symbol 字段，第三个问题中 `rank_fusion` 的 symbol 重叠会变成 2，额外加分 `0.3 × 2 × 3 = 1.8`。

### Q11 — 参考答案

1. RRF 先验的上限是"两路都排第 1"：`2/61 ≈ 0.0328`；只出现在一路时最多 `1/61 ≈ 0.0164`。而**每命中一个 summary 词就加 0.1**，是先验上限的 3 倍；symbol 每命中一个词加 `0.3 × 3 = 0.9`。所以最终排序几乎完全由词重叠决定，RRF 只在重叠相同时用来打破平局。这不是 bug，但要知道这个 stub 与真实 cross-encoder 的行为不同：真实 reranker 输出的是独立打分，通常**直接替换**而不是叠加在 RRF 分数上。
2. 实际打印的交集：
   - `AbortMultipartOnFail`：`budget, multipart, retry, s3`，4 个 → +0.4，总分 0.4325
   - `abortUpload`：`abort, multipart, s3`，3 个 → +0.3，总分 0.3325
   - `bucket_budget`：`budget, retry, s3`，3 个 → +0.3，总分 0.3318
   这也解释了为什么不管 dense 怎么随机，rerank 的前三名总是这三个 S3 相关 chunk（顺序可能因平局与先验而变）。
3. `DenseIndex.search` 没有任何分数阈值，`k=10` 大于语料大小 6，所以**每个 chunk 都会进入 dense 结果**，RRF 后也都有分数；`rerank` 再固定截取 `top_k=5`。于是只有 1 个真正相关的问题也会凑满 5 条"引用"。`answer()` 把 `rerank_top` 直接当作 `citations`，没有相关性阈值、没有合成步骤、也没有讲义第 7 步的 citation 校验。生产中应当：给 rerank 分数设阈值（低于阈值宁可少引）；由合成模型只引用它真正用到的片段；再用 post-filter 校验每个锚点。

### Q12 — 参考答案

1. `MRR@10 = (1/1 + 1/2 + 0)/3 = 0.5`。未进入前 10 的问题倒数排名记 0。
2. `DCG = 1/log2(3) + 1/log2(5) = 0.6309 + 0.4307 = 1.0616`；理想排序 `[1,1,0,0,0]` 的 `IDCG = 1 + 0.6309 = 1.6309`；`nDCG@5 = 1.0616/1.6309 ≈ 0.651`（已用 Python 计算）。
3. 参考实现（已运行验证）：
   ```python
   import re
   ANCHOR = re.compile(r"\(([\w.\-]+/[\w./\-]+):(\d+)-(\d+)\)")

   def enforce_citations(answer: str, known: dict[str, list[tuple[int, int]]]):
       """known: 'repo/path' -> 已检索 chunk 的 (start, end) 列表"""
       kept, dropped = [], []
       for sent in re.split(r"(?<=[.!?])\s+", answer.strip()):
           anchors = ANCHOR.findall(sent)
           ok = bool(anchors) and all(
               any(s <= int(a) and int(b) <= e for s, e in known.get(p, []))
               for p, a, b in anchors)
           (kept if ok else dropped).append(sent)
       return " ".join(kept), dropped
   ```
   在一个四句话的例子上，带合法锚点的两句被保留；"It also pages on-call."（无锚点）和引用了未检索文件 `client/libs/metrics.ts:1-9` 的一句被丢弃。要点：既要检查"有没有锚点"，也要检查"锚点是否真实存在且行号落在检索到的范围内"——skill 文件的拒绝规则："Refuse to answer queries that claim to cite files the index never saw"。被丢弃的句子可以触发一次"请为这些论断补充引用"的重问。

### Q13 — 参考回答要点

- **链路**：
  1. 查询改写（可选）：把自然语言问题补充成包含可能符号名的查询；
  2. 并行召回：dense（向量库 ANN）与 BM25（倒排索引）各取 top-k，按 `(repo, path, symbol)` 去重；
  3. 融合：RRF 合并两路名次；
  4. 精排：cross-encoder 对 top-50 打分，保留 top-10；
  5. 可选扩展：沿符号图把被调用方、import 来源等跨仓库 chunk 拉进来；
  6. 合成：长上下文模型（讲义："Claude Sonnet 4.7 with prompt caching"）基于这些 chunk 回答，要求每个论断带 `repo/path:start-end`；
  7. 引用校验：post-filter 丢弃或重问无锚点论断，返回只含已引用内容的答案。
- **为什么用 RRF**：BM25 分数无上界、随查询长度和语料变化；余弦在 [−1,1] 且不同模型分布差异很大。直接相加需要精心归一化，且一路分数异常就会主导结果。RRF 只用名次，`k=60` 让排名靠后的差距变得平缓，几乎不需要调参，对两路检索器的分数尺度不敏感。
- 加分点：Qdrant 等向量库已内置 hybrid query 与 RRF；也可以对 dense/BM25 做加权 RRF（不同路给不同权重）。
- 常见误区：把 RRF 的输出分数当作"相关性概率"设阈值——它只反映名次，不反映绝对相关性；阈值应设在 reranker 分数上。

### Q14 — 参考回答要点

- 公式：`score(q, d) = Σ_t IDF(t) · f(t,d)·(k1+1) / (f(t,d) + k1·(1 − b + b·|d|/avgdl))`。
- `k1`（本节 1.5）：词频饱和速度。`f` 增大时分数趋于上限 `IDF·(k1+1)`，避免一个词重复 100 次就"刷分"。`k1 = 0` 时退化为只看是否出现。
- `b`（本节 0.75）：长度归一化强度。`b = 1` 完全按文档长度惩罚，`b = 0` 不惩罚。
- IDF：越罕见的词权重越高；本节的 `+1` 版本保证恒正。
- **重复 token 与 BM25F 的区别**：
  - 重复 4 次会**同时**增大 `f` 和文档长度 `|d|`：symbol 越长，整篇文档越"长"，反而压低了 body 里其它词的分数；
  - 由于 `k1` 饱和，`f` 从 1 变成 4 带来的增益远小于 4 倍（`k1=1.5`、长度相同时，`f=4` 的 TF 项是 `f=1` 的约 1.82 倍：`(4·2.5/5.5)/(1·2.5/2.5)`）；
  - BM25F 的做法是先对每个字段分别做长度归一化、再按字段权重加权求和得到"伪词频"，**最后**再做一次饱和，字段权重的作用更可控；
  - Tantivy、Elasticsearch 都支持多字段检索，生产中不必手写。
- 加分点：代码中 df 是按"重复后"的 token 统计的，但重复不影响 df（每个文档只加 1），这一点是对的。

### Q15 — 参考回答要点

- **元数据**：每个 chunk 存 `chunk_id = hash(repo, path, symbol, kind)`、`content_hash`（body 的哈希）、行号范围、所属 commit、embedding 模型版本；每个文件存其包含的 chunk 列表；符号图边存来源 chunk。
- **判断哪些要重算**：
  1. webhook 拿到 `before..after` 的 diff，得到改动文件列表；
  2. 只对改动文件跑 tree-sitter，得到新的 chunk 集合；
  3. 与旧集合按 `chunk_id` 对比：`content_hash` 没变 → 只更新行号（行号漂移不需要重新 embed）；变了 → 重新 summary + embed + 更新 BM25；新增 → 插入；消失 → 删除；
  4. import/调用发生变化的 chunk 重算符号边；被它引用的一方无需重算。
- **删除与重命名**：删除文件 → 删除其全部 chunk 与边；重命名（git 的 rename 检测）→ 只改 `path` 元数据，不重新 embed。
- **一致性**：同一次 push 的更新按"版本号/commit"原子切换，例如先写入新版本 chunk，全部写完后再切换查询使用的版本过滤条件；失败可重放（webhook 幂等，以 commit SHA 去重）。
- **性能**：summary 与 embedding 批量调用（讲义：Voyage 批大小 128），summary 的 system preamble 开 prompt caching。
- 常见误区：用行号作为 chunk 主键——上方插入一行就会让整个文件所有 chunk "看起来都变了"，导致不必要的重算。本节代码 `rrf` 正是按 `anchor()`（含行号）去重的，讲义第 6 步则是按 `(repo, path, symbol)` 去重。

### Q16 — 参考回答要点

- **评估集**：100 道跨仓库问题（讲义要求），每题标注金标准 `file:line` 区间；覆盖"按名字找""按功能找""跨仓库调用链""配置 + 代码联合"等类型；从真实工单、代码评审问题中采样，避免全是作者自己编的问题。
- **指标**：检索层 MRR@10、nDCG@10、Recall@k；答案层 citation faithfulness（可核验论断占比）、答案正确率（人工或 LLM-as-judge 抽检）；系统层 p50/p95/p99 延迟、push-to-searchable 时长。
- **回归门槛**：任何改动（换 embedding 模型、调 chunk 策略、换 reranker）都必须在评估集上跑分，MRR@10 下降超过阈值则不准上线。
- **漂移告警**：每周重跑，MRR@10 掉超过 5% 告警（讲义练习 4）——代码库在变、模型 API 在变，指标会悄悄漂移。
- **生成代码污染**（讲义练习 2）：注入 20% LLM 生成的样板代码再评估，观察 MRR 下降；在 payload 加 `generated` 标记（来源于路径规则、文件头注释、git 作者等），检索时降权或过滤；同时做近重复检测（MinHash）合并重复 chunk。
- 加分点：把评估集与线上日志对齐，定期从"用户点了引用又立刻追问"的会话中挖掘新题。

### Q17 — 参考回答要点

- **规模**：讲义的目标是 10 个仓库 2M 行代码，按每行约 10 token 估算约 2000 万 token，远超 1M 上下文。
- **成本与延迟**：即使能塞下，每次查询都处理百万 token，费用和首 token 延迟都不可接受；prompt caching 能打折，但代码一改缓存就失效。
- **质量**：上下文越长，模型越容易被无关代码干扰，"lost in the middle"问题依然存在；检索把最相关的 10 个 chunk 放在前面，信噪比高得多。
- **可引用性**：检索天然产生 `file:line` 锚点，便于强制引用与核验。
- **新鲜度**：索引可以增量更新，而"塞整个仓库"每次都要重新读。
- 讲义原话："Claude's 1M-token context helps; it does not eliminate the need for ranked retrieval."
- 加分点：二者是互补关系——检索负责"选对"，长上下文负责"装得下更多相关片段 + 跨文件推理"，讲义的合成模型恰好就是长上下文模型。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 14 信息检索与搜索](../../../05-nlp-foundations-to-advanced/14-information-retrieval-search/docs/zh.md)：TF-IDF、BM25、倒排索引与 MRR 等检索指标的基础。
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../../05-nlp-foundations-to-advanced/23-chunking-strategies-rag/docs/zh.md)：固定窗口、递归、语义切块，对照理解 AST-aware chunking。
- [阶段 11 · 04 Embeddings 与向量表示](../../../11-llm-engineering/04-embeddings/docs/zh.md)：dense 检索与余弦相似度。
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)：检索 + 生成的基本链路。
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：hybrid、rerank、RRF 的系统讲解。
- [阶段 11 · 15 Prompt 缓存与上下文缓存](../../../11-llm-engineering/15-prompt-caching/docs/zh.md)：summary 批处理与合成步骤都依赖 prompt caching 降本。

### 本节被哪些后续内容用到
- [阶段 19 · 08 面向受监管行业的生产级 RAG 聊天机器人](../../08-production-rag-chatbot/docs/zh.md)：把 hybrid 检索 + 引用强制用到合规场景。
- [阶段 19 · 16 从 GitHub Issue 到 PR 的自主 Agent](../../16-github-issue-to-pr-agent/docs/zh.md)：coding agent 需要代码库检索层定位相关文件。
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../65-hybrid-retrieval-bm25-dense/docs/zh.md)、[阶段 19 · 66 基于 Cross-Encoder 的 Reranker](../../66-reranker-cross-encoder/docs/zh.md)：本节两个核心组件的逐步实现。
- [阶段 19 · 68 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性](../../68-rag-eval-precision-recall/docs/zh.md)：本节评估指标的完整实现。
- [阶段 14 · 24 Agent 可观测性：Langfuse、Phoenix、Opik](../../../14-agent-engineering/24-agent-observability-platforms/docs/zh.md)：讲义要求每个检索、合成步骤上报 Langfuse span。

### 延伸关键词
`tree-sitter` · `AST-aware chunking` · `BM25 / BM25F` · `Reciprocal Rank Fusion` · `bi-encoder vs cross-encoder` · `Qdrant hybrid query` · `pgvector` · `symbol graph` · `repo-map` · `citation faithfulness` · `MRR@10 / nDCG@10` · `incremental indexing` · `content hash` · `PYTHONHASHSEED`
