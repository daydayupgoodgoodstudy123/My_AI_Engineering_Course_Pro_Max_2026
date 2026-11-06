# 测验 · 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval（Hybrid Retrieval with BM25 and Dense Embeddings）

> **阶段 19 · 综合项目 · 第 65 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两种检索互补 | 词法检索（BM25）擅长 query 中含有语料里逐字出现的标识符；语义检索（dense）擅长换了说法的 query。真实 query 分布两类都有，所以要 hybrid |
| 2 | BM25 打分 | 对每个 query 词求和：`IDF × f·(k1+1) / (f + k1·(1 − b + b·dl/avgdl))`，即"IDF × 饱和的词频 × 长度归一化" |
| 3 | 平滑 IDF | `log((N − df + 0.5)/(df + 0.5) + 1)`；log 里的 +1 保证 df 超过一半语料时 IDF 仍为正 |
| 4 | k1 与 b | k1（默认 1.5）控制词频饱和速度；b（默认 0.75）控制文档长度惩罚，b = 0 忽略长度、b = 1 完全归一化 |
| 5 | 字段加权 | 本节实现是"索引时把 title 的 token 重复 3 次"；简单但会同时改变词频与文档长度，不等价于真正的 BM25F |
| 6 | Dense 检索 | 把文本 embedding 成定长向量，余弦相似度排序；算法只是"点积 + 排序"，质量取决于 embedding 模型 |
| 7 | RRF | `score(d) = Σ w_i / (k + rank_i(d))`，rank 从 1 开始，k 默认 60（Cormack、Clarke、Buettcher 2009）；只用排名，不用分数 |
| 8 | 为什么不线性插值分数 | BM25 分数无界且依赖语料，余弦在 [−1, 1]；`α·bm25 + (1−α)·cos` 需要按语料调 α，重建索引就失效；排名在两种模态间可比 |
| 9 | RRF 的 k | k 小：头部名次占主导；k 大：贡献曲线平坦，深层候选也能"投票" |
| 10 | 失败模式 | 停用词主导 BM25、OOV 词 BM25 贡献为 0、两种模态 top-1 相同时融合"看不见"、chunk 级结果需要按文档去重 |

### 核心技能（能动手做到）

- [ ] 从零写出 BM25 的 `add/search`（df、tf、doc_len、avgdl、平滑 IDF），并能手算单个词对某文档的贡献
- [ ] 写出带权重的 RRF，正确处理"rank 从 0 枚举但公式从 1 开始"的偏移
- [ ] 解释并演示线性分数插值的尺度问题，必要时实现 min-max 归一化后的插值作对照
- [ ] 读懂三路输出（bm25 / dense / fused），判断融合是帮了忙还是帮了倒忙
- [ ] 为代码搜索场景设计分词（camelCase、snake_case）、停用词与字段权重
- [ ] 构造"对抗性 query 对"来验证融合是否真的在起作用

---

## 二、基础自测（选择题）

**Q1.** 本节语料 N = 7。某个词出现在 2 篇文档中（df = 2），按代码中的平滑 IDF 公式，IDF 约为：

- A. 0.916
- B. 0.788
- C. 1.163
- D. 1.674

**Q2.** RRF（k = 60，两路权重都为 1）中：文档 X 只出现在 BM25 列表且排第 1；文档 Y 在 BM25 和 dense 两个列表中都排第 2。融合后：

- A. Y 排在 X 前面：Y 得 `2/62 ≈ 0.0323`，X 只得 `1/61 ≈ 0.0164`
- B. X 排在 Y 前面，因为第 1 名的贡献最大
- C. 两者并列
- D. 无法判断，需要知道两者的原始分数

**Q3.** BM25 中参数 k1 的作用是：

- A. 控制文档长度惩罚的强度
- B. 控制 IDF 的平滑程度
- C. 决定返回多少个结果
- D. 控制词频饱和速度：同一个词重复出现时，得分增长多快趋于饱和

**Q4.** 把 BM25 的 b 设为 0 意味着：

- A. 完全按文档长度归一化
- B. 忽略文档长度：长文档不会因为长度被惩罚
- C. 所有词的 IDF 都变成 0
- D. 词频不再影响得分

**Q5.** 讲义认为 RRF 优于 `α·bm25 + (1 − α)·cosine` 线性插值的核心理由是：

- A. RRF 计算更快
- B. BM25 分数无界且依赖语料、余弦有界，两者尺度不可比；线性插值的 α 要按语料调，重建索引就会失效，而排名在两种模态之间天然可比
- C. 线性插值无法处理负分数
- D. RRF 能利用两个检索器的原始分数信息

**Q6.** 本节 `BM25Index` 的字段加权实现是 `out.extend(tokens * weight)`（title 权重 3）。下列说法正确的是：

- A. 它只在打分时给 title 匹配乘以 3，不影响索引
- B. 它与 BM25F 完全等价
- C. 它会把 title 的 IDF 乘以 3
- D. 它在索引时把 title 的 token 重复 3 次：title 词的 tf 变成 3 倍，文档长度 dl 也被拉长，并且仍受 k1 饱和的影响，所以不等价于按字段分别做长度归一化的 BM25F

**Q7.** 对本节语料执行 `BM25Index.search("abort")`，返回的是空列表。原因是：

- A. 分词器不做词干化，正文里是 "Aborts"（token `aborts`），标题 `AbortMultipartOnFail` 被整体切成一个 token `abortmultipartonfail`，没有任何文档包含 token `abort`
- B. "abort" 是停用词，被过滤了
- C. IDF 为负数，得分被截断
- D. BM25 只匹配 title 字段

**Q8.** 运行结果中，paraphrased query "how do we handle cancelled uploads" 的融合结果 d2 与 d3 得分都是 0.0325。下列解释正确的是：

- A. 两者在两个列表中的原始分数相同
- B. RRF 对前两名总是给相同的分数
- C. d2 在 BM25 第 1、dense 第 2，d3 在 BM25 第 2、dense 第 1，`1/61 + 1/62` 完全相等；Python 的 `sorted` 是稳定的，并列时按插入顺序（先遍历 BM25 列表，d2 先插入）排在前面
- D. 这是浮点误差

---

## 三、动手 / 代码题

**Q9.** query "centralized authorization for service accounts" 的 BM25 结果中，第 2 名是 d7（Index sizing，内容是向量索引内存），得分 1.7171。已知：N = 7、`avgdl ≈ 35.571`、d7 的文档长度 `dl = 32`、词 `for` 的 df = 2、在 d7 中出现 f = 2 次，k1 = 1.5、b = 0.75。

1. 手算 `for` 对 d7 的贡献，验证 1.7171。
2. 为什么一个与授权毫无关系的文档能排第 2？在 dense 列表中它也是第 2，这是巧合吗？
3. 加一个停用词表（至少包含 for、the、a、how、do、we）后重新检索，BM25 和融合结果会怎样变化？

**Q10.** 讲义 Build It 声称："The literal identifier query lands at BM25 rank 1, dense rank 4, RRF rank 1. The paraphrased query lands at BM25 rank 6, dense rank 1, RRF rank 1. The ambiguous query lands at BM25 rank 3, dense rank 3, RRF rank 1."

1. 对照实际运行输出，逐条写出目标文档在 BM25、dense、fused 中的真实名次。
2. "how do we handle cancelled uploads" 为什么 BM25 能直接排第 1？这个 query 真的是 paraphrase 吗？
3. 我们试了 query "who may access a resource"（目标应为 d4 check_permission）：BM25 列表 `[d4, d3, d5, d7, d6]`，dense 列表 `[d3, d6, d4, d7, d2]`，融合后第 1 名是什么？这对讲义"the vote wins on every query class"的说法意味着什么？

**Q11.** 实现线性分数插值作为对照：

```python
def linear_fusion(bm25_hits, dense_hits, alpha):
    ...
```

1. 写出实现（缺失的一方记 0 分）。
2. 我们实测 α = 0.5 时，"AbortMultipartOnFail" 的融合分数 d1 = 1.721、第 2 名 d7 = 0.153。为什么 d1 遥遥领先？dense 的信息还起作用吗？
3. 给出一种让线性插值"可用"的归一化方法，并说出它仍然存在的问题。

**Q12.** 讲义失败模式提到："only if you de-duplicate by document, not by chunk"。当索引的单元是 chunk（第 64 节的输出）而不是整篇文档时：

1. 不去重会出现什么问题？
2. 写一个 `rrf_by_parent(rankings, parent_of, k=60)`：先在每个列表内把 chunk 映射到父文档并只保留该文档的**最好名次**，再做 RRF。
3. 去重时为什么要"每个列表内取最好名次"，而不是把同一文档所有 chunk 的贡献加起来？

---

## 四、面试高频题

**Q13.**（基础必考）请写出 BM25 的公式，并解释 IDF、词频饱和、长度归一化三部分分别解决了什么问题。

**Q14.**（原理深挖）为什么要做 hybrid retrieval？RRF 的公式是什么、k = 60 意味着什么？它与基于分数的融合（线性加权、归一化后加权）相比有什么优劣？

**Q15.**（工程实践）请设计一个生产级的 hybrid 检索服务（千万级 chunk），说明索引、查询、融合、重排、去重与监控各环节怎么做。

**Q16.**（场景设计）为内部代码库做检索：用户会搜 `AbortMultipartOnFail`、`check_permission`、"how do we cancel an upload"。你会如何设计分词、字段与权重？

**Q17.**（追问型）面试官追问："RRF 只看名次，丢掉了分数。如果 dense 检索器对某个 query 完全不靠谱，RRF 会怎样？你怎么办？"

---

## 五、参考答案与解析

### Q1 — 答案：C

`log((7 − 2 + 0.5)/(2 + 0.5) + 1) = log(5.5/2.5 + 1) = log(3.2) ≈ 1.163`（已用代码验证，词 `for`、`service`、`budget`、`retry` 的 df 都是 2，IDF 都是 1.1632）。A 是 `log(2.5)`，忘了 +1 并算错比例；B 是 `log(2.2)`，漏了 +1；D 是 df = 1 时的 IDF（`log(6.5/1.5 + 1) ≈ 1.674`）。

### Q2 — 答案：A

`rrf` 中 `1.0 / (k + rank + 1)`，`rank` 从 0 枚举，所以第 1 名贡献 `1/61 ≈ 0.01639`，第 2 名贡献 `1/62 ≈ 0.01613`。Y 两次第 2：`0.03226`；X 一次第 1：`0.01639`。Y 远高于 X。这正是 RRF 的"投票"性质：两个检索器都认可的文档胜过只被一个检索器强烈认可的文档。B 错；C、D 错——RRF 完全不看原始分数。

### Q3 — 答案：D

词频项 `f·(k1+1)/(f + k1·K)` 随 f 增大趋于上限 `k1 + 1`。k1 越大，饱和越慢，重复次数影响越大；k1 = 0 时词频完全不起作用（只看是否出现）。讲义 Key Terms："Controls how fast a repeated term stops adding more score"。A 是 b 的作用；B、C 与 k1 无关。

### Q4 — 答案：B

`K = 1 − b + b·dl/avgdl`，b = 0 时 K = 1，与文档长度无关。讲义："0 means ignore document length, 1 means full normalization"。A 是 b = 1；C、D 都不是 b 的作用。

### Q5 — 答案：B

讲义 "Why fusion beats score-weighted interpolation" 的论证。本节实测：α = 0.5 时 BM25 分数（可达 6 左右）几乎完全压倒余弦（0.3–0.6），线性插值退化为 BM25（见 Q11）。A 不是核心理由；C 错，线性插值可以处理负数；D 说反了——RRF 恰恰**丢弃**了分数信息。

### Q6 — 答案：D

`_doc_tokens` 把 title 的 token 列表乘以 3 后与 body 拼接。效果：title 词的 tf × 3、文档长度 dl 增加 `2 × len(title_tokens)`，而 tf 仍然经过 k1 饱和，3 倍 tf 远不等于 3 倍分数。讲义说 "That keeps the math identical"，但"multiplier trick"并不等价于 BM25F（练习 4 要你实现真正的按字段长度归一化）。A 说的是"打分时加权"，不是本节做法；B 错；C 错，IDF 只依赖 df（文档频率），与重复次数无关。

### Q7 — 答案：A

`tokenize` 只做小写化和 `[a-z0-9]+` 提取：正文 "Aborts" → `aborts`；标题 "AbortMultipartOnFail" 没有分隔符，整体成为一个 token `abortmultipartonfail`。BM25 是精确词匹配，没有词干化（stemming），所以 `abort` 的 df = 0，`search` 中 `if df == 0: continue`，最终所有分数都是 0，被 `if s > 0` 过滤，返回 `[]`（实测）。B 错，代码没有停用词表；C 错，平滑 IDF 永远为正；D 错，body 也被索引。

### Q8 — 答案：C

实测 BM25 列表 `[d2, d3]`、dense 列表 `[d3, d2, d6, d1, d4]`。d2 = `1/61 + 1/62`，d3 = `1/62 + 1/61`，完全相等（0.032522）。`rrf` 先遍历 BM25 列表，d2 先进入 `score` 字典；`sorted` 是稳定排序，并列时保持字典的插入顺序，所以 d2 排第一。A 错，原始分数完全不同（BM25 4.85 vs 1.69）；B 错；D 错，这是精确相等，不是误差。我们扫描 k = 1、10、60、200，d2 与 d3 始终并列——任何 k 都分不开"一个第 1 一个第 2"的对称情形。

### Q9 — 参考答案

1. `IDF(for) = log(5.5/2.5 + 1) = 1.1632`；`K = 1.5 × (1 − 0.75 + 0.75 × 32/35.571) = 1.5 × 0.9247 ≈ 1.3871`；贡献 `= 1.1632 × 2 × 2.5 / (2 + 1.3871) ≈ 5.816 / 3.3871 ≈ 1.7171`，与输出一致（已用代码逐项验证）。d4 的 6.0753 来自 centralized 1.6443 + authorization 1.6443 + service 1.1425 + accounts 1.6443。
2. d7 只匹配了停用词 `for`（"Plan **for** 1 KB per vector... **for** the graph structure"），而且在 7 篇文档的小语料中 `for` 只出现在 2 篇，IDF 并不低（1.163，与 `service` 相同）。讲义失败模式 "Stop-token domination" 说的就是这个。dense 列表中 d7 也排第 2 不是巧合：mock embedding 是哈希词袋 + 字符二元组，同样被 `for` 这类共享 token 主导——两路"检索"本质上都是词法的，所以融合后 d7 仍以 0.0323 排第 2。
3. 去掉停用词后 query 变成 "centralized authorization service accounts"：BM25 只剩 `[d4 6.075, d2 0.963]`（d2 含 "service"）；融合结果 `[d4, d2, d1, d7, d6]`，d7 从第 2 掉到第 4。注意 dense 的 query 也一起去掉了停用词。生产中 BM25 一般会配停用词表或依赖大语料下停用词自然极低的 IDF；本节语料太小，停用词的 IDF 不够低。

### Q10 — 参考答案

1. 实际名次：

| query（目标文档） | BM25 | dense | fused | 讲义声称 |
|------------------|------|-------|-------|---------|
| AbortMultipartOnFail（d1） | 1 | **1** | 1 | 1 / 4 / 1 |
| how do we handle cancelled uploads（d2） | **1** | **2** | 1（与 d3 并列） | 6 / 1 / 1 |
| centralized authorization for service accounts（d4） | **1** | **1** | 1 | 3 / 3 / 1 |

   三条都与讲义描述不符：融合在这三个 query 上从未"救回"任何一个模态的失误，因为两个模态的 top-1 本来就对（或者 BM25 本来就对）。讲义失败模式自己也说 "Identical content across modalities... makes the fusion look invisible"。

2. d2 的正文中逐字出现了 "**Cancelled uploads** do not block subsequent attempts"，`cancelled` 和 `uploads` 都是精确匹配，IDF 还很高（只在 d2 出现），所以 BM25 得 4.85 排第 1。这个 query 并没有"换掉语料中的字面 token"，不是真正的 paraphrase。而且 mock embedding 本质也是词法的（哈希 + 字符二元组），无法测试真正的语义检索。
3. 融合后第 1 名是 **d3**（Per-bucket budgets），d4 排第 2：d3 = `1/62 + 1/61`（BM25 第 2、dense 第 1），d4 = `1/61 + 1/63`（BM25 第 1、dense 第 3），d3 略高。BM25 单独使用时是对的，融合反而把错误的文档推到了第 1。这说明"vote wins on every query class"并不成立：当一个检索器对、另一个检索器错得很自信时，RRF 可能会被错误的一方拖累。验证融合是否有效必须靠带标注的评估集（第 68 节），而不是三条演示 query。

### Q11 — 参考答案

1. 实现：

```python
def linear_fusion(bm25_hits, dense_hits, alpha):
    b = {d.doc_id: s for d, s in bm25_hits}
    v = {d.doc_id: s for d, s in dense_hits}
    by_id = {d.doc_id: d for d, _ in bm25_hits + dense_hits}
    fused = {i: alpha * b.get(i, 0.0) + (1 - alpha) * v.get(i, 0.0) for i in by_id}
    return sorted(((by_id[i], s) for i, s in fused.items()), key=lambda x: -x[1])
```

2. 实测 α = 0.5：d1 = `0.5 × 2.947 + 0.5 × 0.496 ≈ 1.721`，其余文档没有 BM25 分数，只剩 `0.5 × 余弦 ≈ 0.15`。BM25 分数的量级（0–6）比余弦（0.27–0.57）大一个数量级，只要 BM25 有命中，它几乎完全决定排序；dense 的作用只剩下在"BM25 未命中的文档"之间排序。要让两者平衡，α 必须调到很小（例如 0.1），而这个值换个语料、换个 query 长度就不对了（BM25 分数随 query 词数累加）。
3. 常见做法：每个 query 内对两路分数分别做 **min-max 归一化**（或 z-score）到 [0, 1] 后再加权（相对分数融合）。仍存在的问题：①只有一个命中时 min = max，需要特殊处理；②归一化后分数的含义随 query 变化，一个完全不相关的列表的第 1 名也会被归一化成 1.0；③α 仍需要在评估集上调。是否优于 RRF 取决于语料与评估，讲义的建议是"stay rank-based unless you have very strong evidence to interpolate scores"。

### Q12 — 参考答案

1. 一篇长文档可能被切成多个 chunk，它们会同时出现在列表中，各自独立得到 RRF 分数：
   - top-k 被同一文档的多个 chunk 占满，多样性下降；
   - 同一文档在两个列表中的"投票"分散在不同 chunk 上（BM25 命中 chunk A，dense 命中 chunk B），RRF 认不出它们是同一个文档，两者都得不到"两路共识"的加成。
2. 参考实现：

```python
from collections import defaultdict

def rrf_by_parent(rankings, parent_of, k=60, weights=None):
    weights = weights or [1.0] * len(rankings)
    score = defaultdict(float)
    for w, ranks in zip(weights, rankings):
        best = {}                                   # 父文档 -> 本列表中的最好名次（从 1 开始）
        for rank, (chunk, _) in enumerate(ranks, start=1):
            pid = parent_of(chunk)
            best.setdefault(pid, rank)              # 第一次遇到就是最好名次
        for pid, rank in best.items():
            score[pid] += w / (k + rank)
    return sorted(score.items(), key=lambda x: -x[1])
```

3. 如果把同一文档所有 chunk 的贡献相加，被切得越碎的文档得分越高（chunk 数越多票越多），这与相关性无关，会系统性偏向长文档。每个列表内只取最好名次，保证"每个检索器对每篇文档只投一票"，与 RRF 原本的语义一致。返回给 LLM 时，再从该文档中挑出得分最高的 chunk（或把相邻 chunk 拼在一起）。

### Q13 — 参考回答要点

- 公式：`score(q, d) = Σ_{t∈q} IDF(t) · f(t,d)·(k1+1) / (f(t,d) + k1·(1 − b + b·|d|/avgdl))`。
- **IDF**：`log((N − df + 0.5)/(df + 0.5) + 1)`，稀有词权重高、常见词权重低；+1 保证非负。
- **词频饱和**：f 越大得分越高但趋于上限 `k1 + 1`，避免"关键词堆砌"的文档无限得分；k1 常取 1.2–2.0（讲义默认 1.5）。
- **长度归一化**：长文档天然包含更多词、更容易命中，用 `dl/avgdl` 惩罚；b 控制强度（默认 0.75）。
- 加分点：BM25 是概率检索模型（Robertson / Sparck Jones）的近似；BM25F 对多字段分别做长度归一化后再合并；Lucene/Elasticsearch 默认相似度就是 BM25。

### Q14 — 参考回答要点

- **为什么 hybrid**：BM25 对精确标识符、罕见词、OOV 名字（错误码、函数名、产品型号）极强；dense 对同义改写、自然语言描述强。两者失败的 query 分布相反，合并能提高召回的下限。
- **RRF**：`Σ w_i/(k + rank_i)`，rank 从 1 开始。k = 60 时第 1 名贡献 1/61、第 10 名 1/70，衰减很慢，深层候选也能投票；k 越小越偏向头部。
- **优点**：不需要分数校准、对异常分数鲁棒、实现简单、可融合任意多路；在多个评测中表现稳定（讲义引用 2009 年原论文）。
- **缺点**：丢弃分数信息——无法区分"第 1 名置信度很高"和"第 1 名勉强"；一路检索器很差时它的错误名次也会参与投票（见 Q10 的 "who may access a resource"）；并列难以打破（见 Q8）。
- **基于分数的融合**：min-max/z-score 归一化后线性加权（相对分数融合），在分数校准良好、有调参数据时可能更优；也可以学习融合权重（learning to rank）。
- 结论：默认 RRF + 后接 cross-encoder reranker（第 66 节）；用评估集决定 k 与权重（讲义："Tune by re-running lesson 68's eval harness... not by intuition"）。

### Q15 — 参考回答要点

- **索引**：
  - 词法：倒排索引（如 Elasticsearch/OpenSearch/Lucene），配置分词器、停用词、词干化、代码标识符拆分；
  - 向量：ANN 索引（HNSW 等），讲义 "in production you would use HNSW"；记录 embedding 模型版本；
  - 两侧共用 chunk ID 和父文档 ID、权限标签等元数据。
- **查询**：两路**并行**检索（讲义 "Run both queries in parallel"），各取 top-50~100；应用权限/租户过滤（前置过滤）。
- **融合**：RRF（k、权重在评估集上调），按父文档去重（Q12）。
- **重排**：取融合后 top-20~50 给 cross-encoder 重排（第 66 节），再取 top-5~10 给 LLM。
- **可观测**：记录每个结果来自哪个模态（讲义 "Persist the modality of each retrieved hit"）、两路各自的名次与分数、延迟分解；线上监控"两路 top-k 重叠率"、空结果率。
- **评估与迭代**：离线评估集（recall@k、MRR、nDCG），A/B 测试；换 embedding 模型时双写索引、灰度切换。
- **性能**：缓存热门 query 的 embedding；BM25 的瓶颈在词典与倒排表，向量侧注意内存（如讲义 d7 中 "1 KB per vector at 256 dimensions in float32"）。

### Q16 — 参考回答要点

- **分词**：对标识符做多粒度切分——保留原始整体 token（`abortmultipartonfail`、`check_permission`）用于精确匹配，同时按 camelCase / snake_case / 数字边界拆成子词（`abort`、`multipart`、`on`、`fail`）用于部分匹配；可加词干化（`aborts → abort`，`cancelled → cancel`）。本节分词器把 `check_permission` 拆开、却把 camelCase 当成一个整体，导致 "abort" 搜不到 d1（见 Q7）。
- **字段**：函数/类名、签名、docstring/注释、函数体、文件路径分为不同字段，符号名字段权重最高；最好用 BM25F 而不是重复 token。
- **dense 侧**：用代码专用 embedding 模型，对"函数签名 + docstring + 摘要"做 embedding，让自然语言 query（"how do we cancel an upload"）能找到 `AbortMultipartOnFail`。
- **融合**：识别 query 类型——像标识符的 query（含下划线/驼峰、无空格）提高 BM25 权重；自然语言 query 提高 dense 权重。
- **评估**：分别统计"标识符 query"和"自然语言 query"两类的 recall，确保融合对两类都不退化。

### Q17 — 参考回答要点

- **会发生什么**：RRF 对每个列表一视同仁，dense 返回的 k 个结果无论多差都会得到 `1/(k+rank)` 的票。本节 `DenseIndex.search` 总是返回 k 个结果（不设阈值），而 BM25 只返回分数 > 0 的结果。当 BM25 正确、dense 错误且错误结果在 BM25 中也排得较前时，融合会把错误结果推上来（Q10 的例子：d3 超过 d4）。
- **缓解**：
  1. 给 dense 设置相似度阈值，低于阈值的结果不参与投票；
  2. 按 query 类型动态调整权重（标识符型 query 降低 dense 权重）；
  3. 融合后接 cross-encoder 重排，用更强的模型纠正；
  4. 在评估集上调 RRF 的 k 与权重；
  5. 在有足够标注数据时，用学习到的融合（把名次、分数、模态等作为特征）。
- **加分点**：指出这正是"只用名次"的代价——RRF 的鲁棒性来自忽略分数，它的盲点也来自忽略分数。监控两路结果的一致性，一致性很低的 query 往往值得人工检查。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 64 Chunking 策略比较](../../64-chunking-strategies-advanced/docs/zh.md)：本节索引的单元来自上一节的 chunker，mock embedding 也与之同源。
- [阶段 11 · 04 Embeddings 与向量表示](../../../11-llm-engineering/04-embeddings/docs/zh.md)：dense 检索的基础。
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)：检索在 RAG 中的位置。
- [阶段 05 · 14 信息检索与搜索](../../../05-nlp-foundations-to-advanced/14-information-retrieval-search/docs/zh.md)：TF-IDF、倒排索引与 BM25 的经典 IR 背景。
- [阶段 05 · 22 Embedding 模型 — 2026 年深度剖析](../../../05-nlp-foundations-to-advanced/22-embedding-models-deep-dive/docs/zh.md)：真实 embedding 模型的选择。

### 本节被哪些后续内容用到
- [阶段 19 · 66 基于 Cross-Encoder 的 Reranker](../../66-reranker-cross-encoder/docs/zh.md)：对融合后的 top-k 重排。
- [阶段 19 · 67 查询改写：HyDE、多查询与查询分解](../../67-query-rewriting-hyde/docs/zh.md)：多查询的结果同样可以用 RRF 融合。
- [阶段 19 · 68 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性](../../68-rag-eval-precision-recall/docs/zh.md)：用评估集调 RRF 的 k 与权重。
- [阶段 19 · 69 端到端 RAG 系统](../../69-end-to-end-rag-system/docs/zh.md)：本节的 hybrid retriever 是其第一阶段。
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：混合检索在完整 RAG 中的工程实践。
- [阶段 14 · 09 混合记忆：向量、图与 KV](../../../14-agent-engineering/09-hybrid-memory-mem0/docs/zh.md)：Agent 记忆检索中的多路召回与融合。

### 延伸关键词
`BM25` · `BM25F` · `Okapi` · `IDF smoothing` · `k1 / b tuning` · `reciprocal rank fusion` · `relative score fusion` · `min-max normalization` · `stopwords / stemming` · `identifier tokenization (camelCase / snake_case)` · `HNSW` · `multi-vector retrieval` · `learning to rank`
