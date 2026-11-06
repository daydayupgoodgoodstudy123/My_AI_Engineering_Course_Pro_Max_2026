# 测验 · Embedding 模型 — 2026 年深度剖析（Embedding Models — The 2026 Deep Dive）

> **阶段 05 · NLP 从基础到进阶 · 第 22 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过 `main.py` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 选型五个维度 | dense/sparse/multi-vector、语言覆盖、上下文长度（有效容量常只有标称的 60–70%）、维度预算、开源 vs 托管 |
| 2 | Dense embedding | 每段文本一个定长向量（常见 384–3,072 维），用余弦相似度排序；默认选择 |
| 3 | Sparse embedding（SPLADE） | 模型为词表中每个 token 预测权重，大部分为 0；像 BM25 一样做词匹配，但权重是学出来的；擅长关键词型查询 |
| 4 | Multi-vector（ColBERT） | 每个 token 一个向量，MaxSim 打分：每个查询 token 找最相似的文档 token，再求和；存储与计算更贵，长查询/专业领域更强 |
| 5 | BGE-M3 | 一个模型一次推理同时输出 dense、sparse、multi-vector 三种表示，可加权融合 |
| 6 | Matryoshka | 训练时让向量的前 N 维本身就是可用的小 embedding；截断后必须重新归一化；非 Matryoshka 模型截断会明显退化 |
| 7 | MTEB 只是参考 | 发布时 56 个任务、8 类，v2 扩展到 100+；排行榜是"必要不充分"，必须在自己领域上评测 |
| 8 | 三层检索模式 | dense bi-encoder 快速召回 → sparse + RRF 提升召回 → multi-vector 或 cross-encoder 对 top-50 精排 |
| 9 | 常见坑 | 查询/文档非对称编码、`bge` 查询前缀（漏掉掉 3–5 点召回）、过度截断、超长输入被静默截断、只看分数不看 p99 延迟 |

### 核心技能（能动手做到）

- [ ] 用标准库实现 hashing-trick embedding、余弦排序、Matryoshka 截断 + 重新归一化、词频稀疏打分和 RRF 融合
- [ ] 能手算两段文本的 BoW 余弦与 RRF 分数，并解释排序中的平局是如何被打破的
- [ ] 能写出 ColBERT 的 MaxSim 打分函数，并手算一个小例子
- [ ] 能估算向量库存储：维度 × 字节数 × 向量条数，并计算 Matryoshka 截断 + int8 量化后的节省倍数
- [ ] 能用 `sentence-transformers` 写出"`normalize_embeddings=True` 编码 → 点积排序"的检索基线
- [ ] 能为一个领域 RAG 设计 embedding 评测：MTEB 相关任务 + 自建领域评测集（nDCG@10、recall@k）+ p99 延迟 + 每百万次查询成本

---

## 二、基础自测（选择题）

**Q1.** 关于三种 embedding 形态，下列说法正确的是：

- A. Sparse embedding 的维度通常是 384–1,024
- B. Multi-vector 为每个 token 保留一个向量，用 MaxSim 打分，索引更大但召回更好
- C. Dense embedding 只能做关键词匹配
- D. SPLADE 的词权重是人工设定的 IDF

**Q2.** 一个 1,536 维的 Matryoshka 向量截断到 256 维后，正确的做法是：

- A. 直接用截断后的向量算点积，结果就等于余弦
- B. 截断后重新做 L2 归一化，再用点积/余弦
- C. 截断后乘以 6 恢复原来的模长
- D. 截断只能用于 sparse 向量

**Q3.** 你用 `bge-*-en-v1.5` 做检索，召回率比论文低了几个点。讲义提到最可能被忽视的原因是：

- A. 向量没有用 float64 存储
- B. 查询端没有加 `"Represent this sentence for searching relevant passages: "` 前缀
- C. 文档太短
- D. 没有用 GPU

**Q4.** 关于 MTEB 排行榜，下列说法最恰当的是：

- A. 排名第一的模型在任何领域都是最好的
- B. MTEB 只评测检索任务
- C. 排行榜是必要但不充分的：它是多任务平均分，且不反映 p99 延迟和成本，必须在自己的领域数据上评测
- D. MTEB 只包含英文任务，所以多语言场景不能参考

**Q5.** 用户查询里大量出现产品型号、法条编号（如 "Section 420"），纯 dense 检索经常找不到。讲义推荐：

- A. 换一个维度更高的 dense 模型
- B. 加 sparse 检索（SPLADE 或 BGE-M3 sparse），与 dense 用 RRF 融合
- C. 把 Matryoshka 截断到 64 维
- D. 去掉查询中的数字

**Q6.** 关于 BGE-M3，下列说法**错误**的是：

- A. 一次推理可以同时得到 dense、sparse（lexical weights）和 ColBERT 多向量表示
- B. 三种分数可以加权融合，权重需要在自己的领域上调
- C. 它的 dense 向量维度是 1,024
- D. 为了得到三种表示，必须分别跑三次模型

**Q7.** 讲义 skill 中提到"语料少于 10k 段落时拒绝使用 ColBERTv2"。最合理的理由是：

- A. ColBERT 不支持英文
- B. 多向量索引的存储和打分开销大，小语料上收益不足以抵消成本
- C. ColBERT 只能处理 512 维向量
- D. 小语料无法计算 MaxSim

---

## 三、动手 / 代码题

**Q8.** 运行 `main.py`，查询 `"When was the first iPhone released?"` 的 dense 结果前两名是：

```text
  0.544  The first iPod was released by Apple in 2001.
  0.544  Apple released the first iPhone on June 29, 2007.
```

1. 两个文档的分数都恰好是 0.544。请不借助代码手算这个数（提示：查询和两个文档分别有几个 token、共享几个 token？hash 冲突可以忽略）。
2. 分数相同，为什么 iPod 排在 iPhone **前面**？问题出在 `rank` 的哪一行？如何修复？
3. RRF 融合结果是 `0.0328 / 0.0323 / 0.0317`。请按 `rrf_fuse` 的公式手算这三个数。

```python
def rank(corpus_embs, query_emb):
    scored = [(cosine(e, query_emb), i) for i, e in enumerate(corpus_embs)]
    scored.sort(reverse=True)
    return scored

def rrf_fuse(rankings, k=60):
    scores = {}
    for ranking in rankings:
        for rank, (_, idx) in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])
```

**Q9.** "Matryoshka truncation: 256 -> 64" 这一段输出：

```text
  1.000  The first iPod was released by Apple in 2001.
  0.577  Apple released the first iPhone on June 29, 2007.
  0.000  Section 420 of the Indian Penal Code covers cheating.
```

已知查询各 token 的哈希位置：`when→129, was→28, the→160, first→44, iphone→112, released→61`。

1. 为什么截断后 iPod 文档的相似度变成了 1.000？
2. 这是不是在演示真正的 Matryoshka？讲义对非 Matryoshka 模型截断是怎么说的？

**Q10.** 讲义说 ColBERT 用 MaxSim 打分："对每个查询 token，找最相似的文档 token，再把这些最大值求和"。

1. 写一个 `maxsim(q_vecs, d_vecs)`（每个参数是向量列表，向量已归一化，用点积作相似度）。
2. 手算 `q = [[1, 0], [0, 1]]`、`d = [[0.8, 0.6], [0.6, 0.8], [1, 0]]` 的 MaxSim 分数。
3. 与 dense 方案相比，MaxSim 的存储代价如何随文档长度变化？

**Q11.** Q8 中 iPhone 与 iPod 两个文档的 sparse 分数也都是 4.0（共享 `was/the/first/released` 或 `the/first/iphone/released`）。

1. 给 sparse 检索加一个停用词表 `{"when", "was", "the", "a", "an", "of", "in", "on", "by", "is", "to", "for", "as", "or"}`（只在打分前过滤），重新计算两者的分数。
2. 有同学提议"不用停用词表，直接用语料内的 IDF 加权 `log(N/df)`"。在这 6 篇文档的语料上，这能让 iPhone 文档排第一吗？为什么？

---

## 四、面试高频题

**Q12.**（基础必考）Dense、sparse、multi-vector 三种 embedding 的表示方式、打分方式、存储代价和适用场景分别是什么？生产中通常怎么组合？

**Q13.**（原理深挖）解释 Matryoshka Representation Learning。为什么截断后要重新归一化？一亿条 1,536 维 float32 向量，截断到 256 维再做 int8 量化，存储分别是多少？

**Q14.**（工程实践）你要为一个法律文档 RAG 选 embedding 模型。请描述完整的选型与评测流程。

**Q15.**（原理深挖）Bi-encoder、cross-encoder、late interaction（ColBERT）三者的区别是什么？为什么检索第一阶段几乎都用 bi-encoder？

**Q16.**（追问型）RRF 的公式是什么？为什么用名次而不是直接把 dense 和 sparse 的分数相加？`k = 60` 起什么作用？它和 BGE-M3 示例里的加权求和 `0.4·dense + 0.2·sparse + 0.4·colbert` 各适合什么场景？

---

## 五、参考答案与解析

### Q1 — 答案：B

Multi-vector（ColBERT）每个 token 一个向量、MaxSim 打分，讲义 Key Terms："bigger index, better recall"。A 错：sparse 向量的维度是词表大小 |vocab|，只是大多数为 0；C 错：dense 捕捉语义相似；D 错：SPLADE 的权重是端到端学出来的（"Learned BM25"）。

### Q2 — 答案：B

截断会改变向量模长，不再是单位向量，点积就不等于余弦了。讲义 Step 2 的 `truncate` 函数在切片后立即除以 L2 范数。C 的"乘 6"毫无依据；D 错，Matryoshka 针对 dense 向量。

### Q3 — 答案：B

讲义 Pitfalls："`bge-*` models need `"Represent this sentence for searching relevant passages: "` prepended to queries. 3-5 point recall gap if you forget." 更一般的原则是：查询前缀/指令、是否非对称编码，都以模型卡为准（不同模型要求不同）。

### Q4 — 答案：C

MTEB 是多任务平均，自己领域的排名可能完全不同；讲义还指出 MTEB 分数不反映 p99 延迟（"A 600M model might beat a 335M model by 2 points but cost 3× more per query"）。A、B 明显错误；D 错，MTEB 包含多语言任务，讲义也给出了多语言榜单的领先者。

### Q5 — 答案：B

型号、编号、专有名词是 dense 模型容易"抹平"的信息，sparse 检索保留精确词匹配。讲义三层模式中 "Recall boost: Sparse (SPLADE, BGE-M3 sparse) + RRF fuse"，Use It 表中 "Keyword-heavy queries: Add SPLADE sparse, RRF-fuse with dense"。

### Q6 — 答案：D

BGE-M3 的卖点就是 "Three indexes, one inference call"：一次 `encode(..., return_dense=True, return_sparse=True, return_colbert_vecs=True)` 同时返回三者。A、B、C 均与讲义一致（`dense_vecs` 形状为 `(n_docs, 1024)`）。

### Q7 — 答案：B

ColBERT 为每个 token 存一个向量，索引大小约为 dense 的"平均 token 数"倍，打分也更贵。语料很小时，dense + reranker 足以达到高精度，多向量带来的召回提升不值得付出这些工程与存储成本。

### Q8 — 参考答案

1. `tokenize` 不去停用词。查询 6 个 token：`when, was, the, first, iphone, released`；两个文档各 9 个 token。
   - iPhone 文档共享 `the, first, iphone, released`（4 个）；
   - iPod 文档共享 `was, the, first, released`（4 个）。
   
   hashing trick 下（无冲突、每个 token 出现一次），每个 token 落在一个维度上取值 ±1，同一个 token 在查询和文档中符号相同，所以点积 = 共享 token 数，模长 = √(token 数)：

   ```
   cos = 4 / (√6 × √9) = 4 / 7.348 ≈ 0.544
   ```

   这说明 hashing-trick 的"dense"向量本质上是**随机投影后的词袋**，没有任何语义。

2. `scored.sort(reverse=True)` 对 `(score, i)` 元组排序：分数相同时比较第二个元素 `i`，`reverse=True` 让**下标大的排前面**。iPod 是下标 3，iPhone 是下标 0，所以 iPod 赢了平局。这不是"相关性"的结果，而是排序实现的副作用。修复：显式指定排序键，分数降序、下标升序（或者引入真正的平局决胜规则）：

   ```python
   scored.sort(key=lambda x: (-x[0], x[1]))
   ```

   修复后 dense 排序变为 iPhone（0）、iPod（3）、Macworld（1）。sparse 排序有同样的问题（`sparse_scores.sort(reverse=True)`）。

3. dense 和 sparse 的前三名顺序相同（iPod、iPhone、Macworld，名次 0、1、2），RRF 分数 = 两个榜单的 `1/(k + rank + 1)` 之和：

   ```
   iPod:     1/61 + 1/61 = 0.03279 → 0.0328
   iPhone:   1/62 + 1/62 = 0.03226 → 0.0323
   Macworld: 1/63 + 1/63 = 0.03175 → 0.0317
   ```

   RRF 只看名次，两路排序本身就把 iPod 排第一，融合也救不回来——**融合不能修复上游的系统性错误**。

### Q9 — 参考答案

1. `truncate_matryoshka` 只保留前 64 维。查询中只有哈希位置 < 64 的 token 能留下：`was(28)`、`first(44)`、`released(61)`，最关键的 `iphone(112)` 被截掉了。iPod 文档在前 64 维里恰好也只有 `first、was、released` 这三个 token，与截断后的查询**完全相同**，重新归一化后余弦为 1.000。iPhone 文档前 64 维里有 `released、first、june、29`，共享 2 个：`2/(√3 × √4) ≈ 0.577`。第三名分数为 0.000，说明剩下的文档与截断后的查询毫无交集，前三名里混进了无关文档。

2. 不是。hashing trick 的维度位置是随机的，前 64 维与后 192 维同等重要，截断等于随机丢掉约 3/4 的词。真正的 Matryoshka 是**训练出来的**：训练目标让前 N 维承载最主要的信息，所以截断后只损失约 1%（讲义：1,536→256 约 1% 精度换 6 倍存储）。讲义原话："Non-Matryoshka models (original Sentence-BERT) degrade sharply when truncated." 这段输出恰好是这句话的反面演示：截断"操作"相同，但向量不是为截断训练的，排名就崩了。

### Q10 — 参考答案

```python
def maxsim(q_vecs, d_vecs):
    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))
    return sum(max(dot(q, d) for d in d_vecs) for q in q_vecs)
```

手算：
- 查询 token 1 `[1, 0]` 与三个文档 token 的点积：0.8、0.6、1.0 → 最大 1.0
- 查询 token 2 `[0, 1]`：0.6、0.8、0.0 → 最大 0.8
- MaxSim = 1.0 + 0.8 = **1.8**

存储：dense 每篇文档 1 个向量，与文档长度无关；MaxSim 需要每个 token 一个向量，存储随文档 token 数**线性增长**（一个 200 token 的段落就是 200 个向量）。打分也从一次点积变成 |q| × |d| 次点积。这就是讲义说 "More expensive to store and score" 的原因，也是 ColBERTv2 要做残差压缩的动机。

### Q11 — 参考答案

1. 过滤后查询只剩 `first, iphone, released`：
   - iPhone 文档：`first、iphone、released` 全中 → **3.0**
   - iPod 文档：`first、released` → **2.0**
   
   iPhone 文档排第一。（同样的停用词过滤用在 dense 哈希向量上，iPhone ≈ 0.655，iPod ≈ 0.516，也会翻转。）

2. 不能。在这 6 篇文档上，`was` 只出现在 iPod 文档中（df = 1，IDF = log 6 ≈ 1.79），而 `iphone` 出现在两篇里（df = 2，IDF = log 3 ≈ 1.10）。IDF 加权后 iPod ≈ 4.39，iPhone ≈ 3.70，iPod 反而领先更多。原因是语料太小，IDF 估计极不稳定：功能词 `was` 只因为碰巧只出现一次，就被当成了"稀有关键词"。这说明：
   - IDF 需要足够大的语料才可靠；
   - 这正是 SPLADE 这类**学习型**稀疏权重的价值——模型从大规模训练中学会 `was` 不重要、`iphone` 重要，而不是靠小语料的统计。

### Q12 — 参考回答要点

| | Dense | Sparse（SPLADE） | Multi-vector（ColBERT） |
|---|---|---|---|
| 表示 | 每段一个定长向量（384–3,072 维） | |vocab| 维，大部分为 0 | 每个 token 一个向量 |
| 打分 | 余弦 / 点积 | 词权重点积（学习型 BM25） | MaxSim |
| 存储 | 小、固定 | 小（倒排索引） | 大，随 token 数线性增长 |
| 擅长 | 语义改写、跨语言 | 关键词、编号、专有名词 | 长查询、专业领域、精排 |

- **组合**（讲义三层模式）：dense bi-encoder 快速召回 → sparse + RRF 提升召回 → ColBERT 或 cross-encoder 对 top-50 精排。讲义："Most production stacks use all three."
- **加分点**：提到 BGE-M3 一个模型同时给出三种表示；能说出 sparse 向量可以直接放进倒排索引。

### Q13 — 参考回答要点

- **原理**：训练时对多个前缀长度（如 64、128、256、…、全维）同时计算损失，迫使模型把最重要的信息放在前面的维度上，所以前 N 维本身就是一个可用的 embedding，像俄罗斯套娃一样层层嵌套。
- **为什么要重新归一化**：截断后模长小于 1，点积不再等于余弦；不同文档截掉的"能量"不同，不归一化会让排序失真。
- **存储估算**：
  - 原始：`1,536 × 4 B = 6,144 B/条`，一亿条约 **614 GB**；
  - 截断到 256 维：`256 × 4 B = 1,024 B/条`，约 **102 GB**（节省 6 倍，与讲义 "6× storage savings" 一致）；
  - 再做 int8：`256 × 1 B`，约 **25.6 GB**（相对原始约 24 倍）。
- **取舍**：讲义经验是 1,536→256 通常安全、→64 不安全；skill 要求截断到 64 维以下必须在领域数据上验证。
- **常见误区**：以为任何模型都能截断。非 Matryoshka 模型截断会明显退化（见 Q9）。

### Q14 — 参考回答要点

1. **明确约束**：语料规模、语言（中英混合？）、平均文档长度、部署方式（云 API / 私有化，法律数据往往要求私有化）、延迟与存储预算。
2. **初筛**：用 MTEB 中相关的检索任务和多语言榜筛出 3–5 个候选（讲义建议从 BGE-M3 或 text-3-large 起步）。
3. **自建领域评测集**：几百条真实查询 + 人工标注相关段落，指标用 nDCG@10、recall@k、MRR。
4. **注意模型卡细节**：查询前缀/指令、非对称编码、最大输入长度（长文档必须先 chunk，见第 23 节）。
5. **检索模式**：法律文本中法条编号、案号多，dense + sparse 混合 + RRF 很可能明显优于纯 dense；top-50 用 cross-encoder 精排。
6. **成本维度**：p99 延迟、每百万次查询成本、向量存储（Matryoshka + int8）。
7. **决策规则**：讲义建议领域模型比通用模型高出 3 个点以上才值得替换；选帕累托最优而不是单看分数。

### Q15 — 参考回答要点

- **Bi-encoder**：查询和文档**分别**编码成向量，相似度是向量点积。文档向量可以离线预计算并放进 ANN 索引，查询时只需编码一次查询 → 百万到十亿级语料毫秒级检索。代价：查询与文档在编码时没有交互，精度有上限。
- **Cross-encoder**：把查询和文档拼在一起（`[CLS] q [SEP] d [SEP]`）送入 transformer，全程 attention 交互，精度最高；但每个 (q, d) 对都要跑一次完整前向，无法预计算，只能用于对少量候选（如 top-50）重排。
- **Late interaction（ColBERT）**：两边分别编码到 token 级向量（可预计算），打分时用 MaxSim 做轻量交互，精度和成本介于两者之间。
- **为什么第一阶段用 bi-encoder**：只有它能把文档表示完全离线化并配合 ANN 索引，满足大规模、低延迟召回。
- 加分点：能把它与第 21 节 NLI 的 cross-encoder 结构联系起来；说出三层漏斗的设计动机是"用便宜的模型缩小候选集，用贵的模型提高精度"。

### Q16 — 参考回答要点

- **公式**：`RRF(d) = Σ_rankers 1 / (k + rank_r(d))`，其中 rank 从 1 开始（`main.py` 中 `rank` 从 0 开始，所以写成 `k + rank + 1`）。
- **为什么用名次**：dense 余弦（约 0–1）和 sparse/BM25 分数（可能是几十）的量纲、分布完全不同，直接相加需要精心归一化，且分布会随查询变化；名次是无量纲的，天然可比，不需要调参。
- **`k = 60` 的作用**：平滑头部名次的差距。k 越大，第 1 名和第 10 名的贡献越接近，融合越"民主"；k 越小，越偏向各路的头名。60 是经验默认值。
- **加权求和（如 BGE-M3 示例）**：当各路分数来自同一个模型、量纲可控时，加权和能利用分数的**幅度**信息（"差多少"），通常更精细，但权重需要在领域数据上调（讲义："Tune the weights on your domain"）。
- **选择**：异构检索器、没有调参数据 → RRF；同源分数、有标注数据可调权重 → 加权求和。
- 常见误区：以为融合能修复上游错误（见 Q8：两路都把 iPod 排第一，RRF 结果也一样）。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 03 词 Embeddings——Word2Vec](../../03-word-embeddings-word2vec/docs/zh.md)：从词向量到段落向量的演进起点。
- [阶段 05 · 14 信息检索与搜索](../../14-information-retrieval-search/docs/zh.md)：BM25、倒排索引、召回与排序指标。
- [阶段 05 · 02 词袋与 TF-IDF](../../02-bag-of-words-tfidf/docs/zh.md)：sparse 表示与 IDF 的来源。
- [阶段 01 · 14 范数与距离](../../../01-math-foundations/14-norms-and-distances/docs/zh.md)：余弦、点积、L2 归一化。

### 本节被哪些后续内容用到
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../23-chunking-strategies-rag/docs/zh.md)：模型的最大输入长度决定了 chunk 大小上限。
- [阶段 11 · 04 Embeddings](../../../11-llm-engineering/04-embeddings/docs/zh.md) 与 [阶段 11 · 06 RAG](../../../11-llm-engineering/06-rag/docs/zh.md)：在 LLM 应用中落地 embedding 检索。
- [阶段 11 · 07 高级 RAG](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：混合检索、重排序等进阶模式。
- [阶段 19 · 65 BM25 + Dense 混合检索](../../../19-capstone-projects/65-hybrid-retrieval-bm25-dense/docs/zh.md) 与 [阶段 19 · 66 Cross-Encoder 重排序](../../../19-capstone-projects/66-reranker-cross-encoder/docs/zh.md)：本节三层模式的项目实现。
- [阶段 12 · 23 ColPali 视觉原生 RAG](../../../12-multimodal-ai/23-colpali-vision-native-rag/docs/zh.md)：late interaction 思想在图像文档上的应用。
- [阶段 17 · 14 Prompt 语义缓存](../../../17-infrastructure-and-production/14-prompt-semantic-caching/docs/zh.md)：用 embedding 相似度做缓存命中判断。

### 延伸关键词
`bi-encoder` · `cross-encoder` · `late interaction / MaxSim` · `SPLADE` · `BGE-M3` · `Matryoshka` · `int8 / binary quantization` · `RRF` · `MTEB / BEIR` · `nDCG@10` · `asymmetric encoding` · `ANN (HNSW / IVF)`
