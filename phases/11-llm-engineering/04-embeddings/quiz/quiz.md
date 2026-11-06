# 测验 · Embeddings 与向量表示（Embeddings & Vector Representations）

> **阶段 11 · LLM 工程 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/embeddings.py](../code/embeddings.py) ｜ 代码讲解：[code/embeddings.讲解.md](../code/embeddings.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 词汇不匹配（vocabulary mismatch） | "payment didn't go through"与"charge was declined"意思相同却没有共同词，关键词检索找不到；embedding 让"意思"而不是"拼写"决定相似度 |
| 2 | Dense vs sparse | Dense embedding 每一维都携带信息（768–3072 维）；TF-IDF / 词袋是 sparse，大多数维度为 0 |
| 3 | 从词到句子 | Word2Vec（2013，每词一个向量、不分上下文）→ 平均词向量 → BERT [CLS] → 对比学习（Sentence-BERT，2019）→ 带任务前缀的 instruction-tuned embedding |
| 4 | 三种相似度 | cosine（只看方向）、dot product（归一化后与 cosine 排序相同、更快）、Euclidean（受模长影响）；单位向量满足 `‖a−b‖² = 2 − 2cos` |
| 5 | ANN 与 HNSW | 暴力检索是 O(n)；HNSW 用多层图从稀疏上层贪心下降到稠密底层，以 95–99% 的召回换取毫秒级延迟 |
| 6 | Chunking | 固定长度 + 重叠、按句、递归、语义四种；讲义推荐 256–512 token、50 token 重叠 |
| 7 | Bi-encoder vs cross-encoder | Bi-encoder 独立编码、可预计算，用于召回；cross-encoder 联合编码、准确但慢，用于重排；典型流水线"召回 top-100 → 重排到 top-10" |
| 8 | Matryoshka embeddings | 训练时让前 N 维承载最重要的信息，截断后仍可用；1536 → 256 维存储降为 1/6，讲义称 MTEB 损失约 3–5% |
| 9 | Binary quantization | 每维只保留符号位，1536 维从 6,144 字节降到 192 字节（32×），用 Hamming 距离；常配合"二值粗排 + 全精度重打分" |
| 10 | 本节代码的本质 | `SimpleEmbedder` 是 TF-IDF（稀疏、非负、按字母序排列维度），它**解决不了**词汇不匹配，Matryoshka 与二值量化演示在它上面都会失真 |

### 核心技能（能动手做到）

- [ ] 从零实现 TF-IDF 向量化（含平滑 IDF 与 L2 归一化）和 cosine / dot / Euclidean / Hamming 四种度量
- [ ] 推导并验证"单位向量下 Euclidean 距离与 cosine 单调对应"，解释为什么三种度量在本节给出相同排序
- [ ] 写出带重叠的固定长度切块与按句切块，并找出 `overlap >= chunk_size`、尾块冗余等边界问题
- [ ] 计算任意规模向量库的存储：float32、Matryoshka 截断、二值量化分别需要多少 GB
- [ ] 实现"二值 Hamming 粗排 + cosine 重打分"的两阶段检索，并用 top-k 重叠率评估
- [ ] 用 OpenAI / sentence-transformers 替换 `SimpleEmbedder`，保持 `VectorIndex` 不变
- [ ] 用 precision@k、recall@k 在自己的查询集上比较两个 embedding 模型

---

## 二、基础自测（选择题）

**Q1.** 本节 STEP 3 中，"Payment transaction was declined by the bank"与"My credit card charge did not go through"（意思相同）的 cosine 相似度实际输出为：

- A. 0.6075
- B. 1.0000
- C. 0.0000
- D. −1.0000

**Q2.** 两个 L2 归一化向量的 cosine 相似度为 0.6075，它们的 Euclidean 距离是：

- A. 0.8860
- B. 0.3925
- C. 0.7850
- D. 1.4142

**Q3.** 关于 bi-encoder 与 cross-encoder，讲义描述的生产模式是：

- A. 用 cross-encoder 对全库每个文档打分，再用 bi-encoder 重排
- B. 只用 cross-encoder，因为它最准确
- C. 用 bi-encoder 对 query 和文档拼接后的文本做一次编码
- D. 用 bi-encoder 召回 top-100 候选，再用 cross-encoder 重排到 top-10

**Q4.** 一个 1536 维的 float32 向量做二值量化后，每个向量占多少字节、压缩多少倍？

- A. 1,536 字节，4 倍
- B. 192 字节，32 倍
- C. 48 字节，128 倍
- D. 768 字节，8 倍

**Q5.** 关于 Matryoshka 表示学习，正确的是：

- A. 训练时让前 N 维承载最重要的信息，因此可以只保留前若干维（通常再重新归一化）而不必重新训练
- B. 任何 embedding 都可以随意截断前 N 维，效果与 Matryoshka 相同
- C. 它把向量的每一维压缩成 1 bit
- D. 它通过 PCA 在推理时对向量降维

**Q6.** 本节 STEP 7 中，查询"API rate limits"的二值量化 top-5 是 `[2, 8, 5, 11, 14]`，与全精度 top-5 只重叠 1 个。这 5 个 chunk 的共同点和根本原因是：

- A. 它们都来自 `api-docs.md`，Hamming 距离比 cosine 更准确
- B. 它们是随机的，因为 `binarize` 引入了噪声
- C. 它们都包含"rate"一词
- D. 它们都是每篇文档最短的尾块；TF-IDF 向量非负，`vec > 0` 退化为"词是否出现"，Hamming 距离 = 查询词数 + 块内词数 − 2 × 共有词数，词越少的块距离越小

**Q7.** `chunk_text` 对一段 30 个词的文本、`chunk_size=30, overlap=10` 调用，返回：

- A. 1 个块，包含全部 30 个词
- B. 2 个块，第二块是第 20–29 个词，内容完全被第一块覆盖
- C. 死循环
- D. 3 个块

**Q8.** 讲义的固定长度切块例子：512 token 一块、重叠 50 token，第 2 块覆盖的 token 范围是：

- A. 512–1023
- B. 450–961
- C. 462–973
- D. 461–972

---

## 三、动手 / 代码题

**Q9.** STEP 6 号称"Matryoshka Simulation"：

```python
    full_dim = len(engine.embedder.vocab)
    query_full = engine.embedder.embed("refund policy enterprise")
    doc_full = engine.embedder.embed(SAMPLE_DOCUMENTS[0][:200])

    for frac in [1.0, 0.5, 0.25, 0.1]:
        dims = max(1, int(full_dim * frac))
        q_trunc = truncate_embedding(query_full, dims)
        d_trunc = truncate_embedding(doc_full, dims)
```

输出为 `270 维: 0.5004`、`135 维: 0.1718`、`67 维: 0.0000`、`27 维: 0.0000`。

1. `SimpleEmbedder` 的第 i 维对应什么？"前 N 维"是按什么排序的？
2. 查询"refund policy enterprise"在向量中只有两个非零维，是哪两个？为什么"policy"没有命中？据此解释 0.5004 → 0.1718 → 0。
3. 这个实验能说明 Matryoshka 截断"损失 3–5%"吗？怎样改造才更像真实的 Matryoshka 行为？

**Q10.** 分词与 IDF：

```python
    def fit(self, documents):
        vocab_set = set()
        for doc in documents:
            vocab_set.update(doc.lower().split())
        ...
        for i, word in enumerate(self.vocab):
            doc_count = sum(1 for doc in documents if word in doc.lower().split())
            self.idf[i] = math.log((n + 1) / (doc_count + 1)) + 1
```

1. 实测词表里有 `policy.` 却没有 `policy`，有 `x-ratelimit-limit,`。查询"How is customer data encrypted?"中哪些词能命中词表？这对检索意味着什么？
2. `fit` 的时间复杂度是多少？为什么在大语料上会非常慢？改写成一次遍历。
3. `embed` 中 `tf = freq / total` 这一步对最终向量有影响吗？为什么？

**Q11.** 二值量化（STEP 7）：

```python
def binarize(vec):
    return (vec > 0).astype(np.int8)
...
    storage_full = full_dim * 4
    storage_binary = math.ceil(full_dim / 8)
```

1. 输出"Binary: 34 bytes, 32x reduction"。`binarize` 返回的数组实际占多少字节？如何真正做到 34 字节？
2. 讲义说的"binary quantization for the first-pass search, then rescore the top-1000 with full-precision vectors"在代码中没有实现。写出两阶段检索函数，并说明在本节数据上的效果。
3. 为什么二值量化对 OpenAI / BGE 这类神经 embedding 有效，对本节 TF-IDF 却几乎失效？

**Q12.** STEP 8 的"chunk size 实验"输出 `20 → 0.3535`、`50 → 0.3419`、`100 → 0.4473`、`200 → 0.4654`，看上去"块越大分数越高"。

1. 为什么这几个 `top_score` **不能直接比较**？
2. `chunk_text` 有哪两个边界问题？（提示：`overlap >= chunk_size`；本节 50/10 配置下每篇文档的第 3 块。）请修复。
3. 若要按讲义练习 2 正确地评估 chunk 大小对检索质量的影响，应该怎么设计实验？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 embedding？它和 TF-IDF 有什么本质区别？为什么检索默认用 cosine，什么情况下 dot product 和 cosine 等价？

**Q14.**（原理深挖）现代句向量模型（Sentence-BERT 之后）是怎么训练出来的？为什么有的模型要求给 query 和 document 加不同的前缀？

**Q15.**（原理深挖）HNSW 的原理是什么？它为什么是"近似"的？有哪些参数影响召回率与延迟？

**Q16.**（工程实践）要为 1,000 万个文档块建向量索引，用 1536 维 embedding。估算存储，并给出至少两种降低成本的方案及其精度代价。

**Q17.**（场景设计）团队想把 embedding 模型从 A 换成 MTEB 分数更高的 B，你会怎么评估和迁移？

---

## 五、参考答案与解析

### Q1 — 答案：C

两句没有任何共同词，TF-IDF 向量的非零维完全不重叠，点积为 0（实际输出 `Cosine: 0.0000`、`Euclidean: 1.4142`）。这正是讲义 The Problem 一节的"vocabulary mismatch"——本节代码用 TF-IDF 演示 embedding，恰好**无法**解决讲义开头提出的问题；神经 embedding 才能把它们放到一起。
- A 是"cat sat on the mat"与"dog sat on the rug"的分数，来自共有的 `the`、`sat`、`on`（虚词），也不是真正的"语义相似"。
- B、D 不可能：TF-IDF 向量非负，cosine 落在 [0, 1]，且两句不同。

### Q2 — 答案：A

单位向量满足 `‖a − b‖² = ‖a‖² + ‖b‖² − 2a·b = 2 − 2cos`，所以 `√(2 − 2 × 0.6075) = √0.785 ≈ 0.8860`，与 STEP 3 输出一致。
- B 是 `1 − cos`（cosine 距离）。
- C 是 `2 − 2cos`，忘了开方。
- D 是 `√2`，对应 cos = 0（正交）。
- 推论：对归一化向量，cosine、dot、Euclidean 给出**完全相同的排序**——STEP 5 三种度量 top-3 一致，且 `cos = 1 − d²/2`（例如 `1 − 1.1093²/2 ≈ 0.3847`，对应 cosine 0.3848）。

### Q3 — 答案：D

讲义："bi-encoder retrieves top-100 candidates, cross-encoder reranks them to top-10. This is the retrieve-then-rerank pipeline."
- A 颠倒了：cross-encoder 不能预计算，对全库打分代价是"文档数 × 一次完整前向"。
- B 准确但太慢，无法用于百万级召回。
- C 描述的是 cross-encoder 的输入方式。

### Q4 — 答案：B

`1536 × 4 = 6,144` 字节 → `1536 / 8 = 192` 字节，`6144 / 192 = 32` 倍。讲义：1,000 万文档 float32 约 61 GB，二值化后约 1.9 GB。
- A 是"每维 1 字节"（int8 量化，或本节 `binarize` 未打包时的真实占用）。
- C、D 数字算错。

### Q5 — 答案：A

讲义："the model is trained so that the first N dimensions capture the most important information, like a Russian nesting doll." OpenAI text-embedding-3 通过 `dimensions` 参数支持截断。手动截断后应重新做 L2 归一化（本节 `truncate_embedding` 就这么做了）。
- B 错：普通 embedding 的维度没有重要性顺序，随意截断损失很大——本节 STEP 6 恰是反例（见 Q9）。
- C 是二值量化。
- D 是事后降维，不是 Matryoshka（Matryoshka 是训练目标的改变）。

### Q6 — 答案：D

已实测：50 词/10 重叠时每篇文档切成 3 块，第 3 块只有 11–22 个词；索引 2、5、8、11、14 恰好是五篇文档的尾块。TF-IDF 值全部 ≥ 0，所以 `vec > 0` 只是"该词是否出现"。设查询有 q 个词、块有 k 个词、共有 m 个，则 Hamming = `q + k − 2m`。查询"API rate limits"有 3 个词，尾块 2 号（k = 11, m = 0）距离 14，而真正相关的 9 号块（k = 43, m = 3）距离 40。词少的块"赢"了。
- A 错：只有 11 号来自 api-docs，且 Hamming 在这里更差。
- B 错：`binarize` 是确定性的。
- C 错：除 11 号外都不含查询词（cosine 为 0）。

### Q7 — 答案：B

`start` 依次为 0、20：第一块 `words[0:30]` 已到末尾，但循环条件 `start < 30` 仍成立，于是又产生 `words[20:30]`（已实际运行验证）。这是一个**完全冗余**的块。
- A 是期望的正确行为。
- C 在 `overlap >= chunk_size` 时才会出现（步长 ≤ 0）。
- D 错：`start = 40` 时退出循环。

### Q8 — 答案：C

步长 = `512 − 50 = 462`，第 2 块从 462 开始，到 `462 + 511 = 973` 结束（含）。
- A 是无重叠的情况。
- B 把重叠算成了 62。
- D 差一位（off-by-one）。

### Q9 — 参考答案

1. 第 i 维对应 `self.vocab[i]`，而 `self.vocab = sorted(vocab_set)` 是**按字母序**排列的（数字、`$` 开头的词在前，例如 `'$29'`、`'$500'`、`'0.1%'`…）。"前 N 维"只是"字母序靠前的 N 个词"，与重要性无关。
2. 两个非零维是 `enterprise` 与 `refund`（已实测）。"policy"没命中，因为词表里只有带句号的 `policy.`（`split()` 不去标点）。字母序上第 135 维附近是 `maintains / maintenance`，第 67 维附近是 `collaboration, / compliance`：
   - 截到 135 维：`refund`（r 开头）被截掉，只剩 `enterprise` 的贡献 → 0.1718；
   - 截到 67 维：`enterprise` 也被截掉，查询向量变成全 0 → `cosine_similarity` 遇到零范数返回 0.0。
3. **不能**。这是"按字母表丢词"，不是 Matryoshka。更合理的模拟：
   - 让维度按重要性排序，例如对 chunk 矩阵做 PCA/SVD，按奇异值从大到小保留前 d 个主成分（这是"事后排序"，Matryoshka 则是训练时让模型自己学出这种排序）；
   - 评价指标用"截断后 top-k 与全维 top-k 的重叠率 / recall@k"，而不是单个 query-doc 对的 cosine。
   - 我们在本节 15 个块、5 个查询上试过（已运行）：按 PCA 保留 8 个主成分，top-3 重叠 12/15；按字母序保留 67 维（反而更多维），重叠只有 8/15。
   - 最真实的做法：用支持 Matryoshka 的模型（如 text-embedding-3 的 `dimensions` 参数，或 sentence-transformers 中的 Matryoshka 模型）对比不同维度的 recall@k。

### Q10 — 参考答案

1. `"How is customer data encrypted?".lower().split()` 得到 `how / is / customer / data / encrypted?`：只有 `is`、`customer`、`data` 命中（已实测）；`how` 不在语料中，`encrypted?` 带问号，而语料里是 `encrypted`。也就是说，问题里**最关键的词"encrypted"根本没参与打分**，安全文档排第一靠的是 `customer`、`data`。生产 tokenizer 至少要去标点、做词形归一；神经 embedding 用子词 tokenizer，天然没有这个问题。改用正则分词 `re.findall(r"[a-z0-9]+(?:[-.][a-z0-9]+)*", text.lower())` 后（保留 `99.9`、`status.acme.com`、`1.3` 这类带点的词），5 个查询的 top-1 来源不变，但分数有升有降（例如 refund 查询 0.3419 → 0.4101，uptime 查询 0.4912 → 0.4467），说明分词改变的是"哪些词参与匹配"，不一定单调提升分数。
2. 外层遍历词表 V 个词，内层对 N 篇文档每篇都重新 `lower().split()`（长度 L），复杂度 O(V·N·L)。语料 1 万块、词表 5 万时就是数十亿次操作。一次遍历的写法：

```python
from collections import Counter

    def fit(self, documents):
        tokenized = [doc.lower().split() for doc in documents]
        df = Counter(w for toks in tokenized for w in set(toks))   # 每篇文档内去重
        self.vocab = sorted(df)
        self.word_to_idx = {w: i for i, w in enumerate(self.vocab)}
        n = len(documents)
        self.idf = np.array([math.log((n + 1) / (df[w] + 1)) + 1 for w in self.vocab])
```

复杂度降为 O(N·L + V log V)。IDF 公式是"平滑 IDF"（分子分母各加 1 防止除零，末尾 +1 保证出现在所有文档里的词权重不为 0），与 scikit-learn 的 `smooth_idf=True` 相同。
3. **没有影响**。同一段文本的所有维度都除以同一个 `total`，随后的 L2 归一化会把这个公共缩放因子抵消掉。只有在不做归一化时才需要它。

### Q11 — 参考答案

1. `(vec > 0).astype(np.int8)` 每维占 1 字节，270 维就是 270 字节（`.nbytes == 270`，已实测），相对 float64 的 2,160 字节（NumPy 默认 dtype）或 float32 的 1,080 字节分别只省 8 倍和 4 倍。打印的 34 字节是理论值。真正打包用 `np.packbits(vec > 0)`，结果 34 字节；Hamming 距离用 `np.unpackbits(a ^ b).sum()` 或 popcount 计算。另外 `storage_full = full_dim * 4` 假设 float32，而代码里向量实际是 float64。
2. 两阶段检索：

```python
def search_two_stage(index, query_vec, top_k=5, candidates=10):
    qb = np.packbits(query_vec > 0)
    codes = [np.packbits(v > 0) for v in index.vectors]        # 实际应在建索引时预先计算
    ham = [int(np.unpackbits(qb ^ c).sum()) for c in codes]
    cand = np.argsort(ham, kind="stable")[:candidates]          # 第一阶段：Hamming 粗排
    rescored = sorted(cand, key=lambda i: -cosine_similarity(query_vec, index.vectors[i]))
    return [int(i) for i in rescored[:top_k]]                    # 第二阶段：全精度重打分
```

在本节数据上（已运行），粗排取 10 个候选再重打分，top-5 为 `[9, 10, 11, 2, 8]`，与全精度 top-5 `[9, 10, 11, 0, 1]` 重叠 3/5，比纯 Hamming 的 1/5 好，但仍不理想——因为第一阶段已经把 1 号块挤出了候选集。这说明重打分的效果受限于粗排召回率，候选数需要足够大（讲义用 top-1000）。
3. 神经 embedding 的各维大致以 0 为中心、正负各半，符号位携带了"在这个方向上偏哪边"的信息，二值化后 Hamming 距离与夹角高度相关。TF-IDF 是非负稀疏向量，符号位只剩"词是否出现"，丢掉了全部权重信息，而且 Hamming 距离受块长度强烈影响（见 Q6）。

### Q12 — 参考答案

1. 每个配置都**重新 `fit`**：词表和 IDF 随切块方式改变（块数 35、15、10、5 不同，IDF 中的 n 和 df 都变），向量空间不同，分数尺度不可比。另外块越大，包含查询词的概率越高，cosine 自然偏高，但这不等于"更好"：大块包含更多无关内容，送进 LLM 时浪费上下文。只看 top-1 分数也忽略了"排在第一的是不是正确答案"。
2. - `overlap >= chunk_size` 时步长 `chunk_size − overlap ≤ 0`，`start` 不增长，**死循环**（已用 `chunk_size=3, overlap=3` 加超时验证）。
   - **冗余 / 过短的尾块**：前一块已覆盖到末尾时仍会再产出一个尾块（Q7 的 30 词例子是"完全冗余"）。50/10 配置下五篇文档（91–102 词）的第 3 块（11–22 词）大部分落在第 2 块内（例如第一篇的第 3 块是第 80–90 词，只有最后 1 个词是新的），既浪费索引，又在 Hamming 检索中成了"干扰项"（Q6）。
   - 修复（参数校验 + 到末尾即停 + 新词太少的尾巴并入当前块）：

```python
def chunk_text(text, chunk_size=200, overlap=50, min_tail=None):
    if not 0 <= overlap < chunk_size:
        raise ValueError("require 0 <= overlap < chunk_size")
    min_tail = overlap if min_tail is None else min_tail
    words = text.split()
    chunks, start = [], 0
    while start < len(words):
        end = start + chunk_size
        if 0 < len(words) - end <= min_tail:   # 剩下的新词太少：并入当前块
            end = len(words)
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):                  # 已覆盖到末尾，停止
            break
        start += chunk_size - overlap
    return chunks
```

   已运行验证：30 词 / 30 / 10 只得到 1 块；五篇示例文档在 50/10 下的块长从 `[50, 50, 11]` 等变为 `[50, 51]`、`[50, 52]`、`[50, 51]`、`[50, 55]`、`[50, 50, 22]`（最后一篇 102 词，尾巴有 12 个新词，超过阈值 10，保留为独立块）；`overlap >= chunk_size` 时抛 `ValueError`。代价是个别块会略超 `chunk_size`。

3. 实验设计：固定一个与切块无关的 embedding 模型（神经模型，或在全文语料上 fit 一次的 TF-IDF）；准备一组带标注的"查询 → 正确答案所在文本段"；对每种 chunk 大小计算 recall@k / MRR（正确段落是否被检回、排第几），同时记录总 token 数（成本）。讲义建议的起点是 256–512 token、50 token 重叠。

### Q13 — 参考回答要点

- **定义**：把文本映射为固定长度的稠密浮点向量，使"几何上接近 ≈ 语义上相近"；讲义："You never inspect them directly. You compare them."
- **与 TF-IDF 的区别**：
  - TF-IDF 是稀疏的，维度 = 词表，值只反映词频与稀有度，同义词互相正交（本节 STEP 3 中两句同义句 cosine = 0）；
  - 神经 embedding 是稠密的、维度固定（768–3072），通过训练把同义表达放到一起；
  - TF-IDF 的优点：可解释、对精确词（型号、错误码）敏感——这也是后续混合检索的出发点。
- **为什么用 cosine**：只看方向不看模长，长短文本可比较；讲义说它是"90% 用例的默认选择"。
- **等价条件**：向量已 L2 归一化时，dot = cosine，Euclidean 与 cosine 单调对应（`d² = 2 − 2cos`），三者排序相同。讲义：OpenAI 的 embedding 已归一化，所以 dot 与 cosine 排序一致。
- 加分点：说明 cosine 的绝对值跨模型不可比（quiz.json 中也强调要用 precision@k、recall 评估，而不是盯着 0.85 这样的分数）。

### Q14 — 参考回答要点

- **对比学习**（讲义："push similar pairs together and dissimilar pairs apart"）：用（query, 正例）对训练，batch 内其他样本的正例作为负例（in-batch negatives），以 InfoNCE / multiple negatives ranking 类损失最大化正例相似度、压低负例；再加入**难负例**（字面相近但答案不对的文档）提升区分度。
- **Sentence-BERT**：孪生（Siamese）结构，同一个编码器分别编码两句，再池化成句向量——这就是 bi-encoder，可以预计算文档向量。
- **为什么 [CLS] 不够**：讲义指出 BERT 的 [CLS] 训练目标是 next-sentence prediction，不是相似度。
- **前缀（instruction）**：检索是不对称任务——query 短、像问题，document 长、像陈述。E5、GTE 等用 `search_query:` / `search_document:` 等前缀告诉模型"这是哪一侧"，让同一个模型产生适合各自角色的向量。实践中忘记加前缀会明显降低效果。
- 加分点：Matryoshka 是在对比损失上对多个截断维度同时计算损失；多语言模型用平行语料对齐。

### Q15 — 参考回答要点

- **问题**：暴力检索对每个查询计算 n 次相似度。讲义：100 万 × 1536 维 ≈ 15 亿次乘加。
- **HNSW 结构**：多层"可导航小世界"图。底层包含所有向量、连边稠密；越往上节点越少、边越"长"。查询从顶层入口点开始贪心地走向更近的邻居，到局部最优后下降一层继续，最后在底层精细搜索。复杂度约 O(log n)。
- **为什么是近似**：贪心搜索可能陷入局部最优，错过真正的最近邻；讲义：典型召回率 95–99%。
- **关键参数**（HNSW 论文与常见实现中的命名）：
  - `M`：每个节点的最大连边数，越大召回越高、内存越大；
  - `efConstruction`：建图时的候选列表大小，越大图质量越高、建索引越慢；
  - `efSearch`：查询时的候选列表大小，越大召回越高、延迟越高——这是线上最常调的旋钮。
- **其他**：IVF（先聚类再只搜少数簇）、PQ（乘积量化压缩向量）常与 HNSW 组合；带元数据过滤时要注意过滤后召回下降。
- 加分点：能说出评估方式——用暴力检索的结果当真值，测 ANN 的 recall@k 与 P99 延迟曲线。

### Q16 — 参考回答要点

- **基线**：`10M × 1536 × 4 B = 61.4 GB`（讲义"61 GB"），还不算 HNSW 图的额外开销。
- **方案 1：Matryoshka 截断到 256 维**：`10M × 256 × 4 B ≈ 10.2 GB`（讲义"10 GB vs 61 GB"），讲义称 MTEB 损失约 3–5%。前提是模型支持 Matryoshka。
- **方案 2：二值量化**：`10M × 192 B ≈ 1.9 GB`（32×），讲义称召回损失 5–10%；配合"二值粗排 top-1000 + 全精度重打分"可恢复到全精度的 95% 以上——全精度向量可以放在磁盘或更便宜的存储上，只对候选读取。
- **方案 3：int8 / 标量量化**：每维 1 字节，4× 压缩，精度损失通常更小。
- **方案 4：选更小的模型 / 合理切块**：减少块数（去掉冗余重叠、去重），控制维度。
- 必须在**自己的查询集**上测 recall@k 再决定，讲义："Always benchmark on your own queries before committing."
- 常见误区：只算向量本身，忘了 ANN 索引结构、元数据和副本的存储。

### Q17 — 参考回答要点

- **离线评估**：MTEB 是通用基准，先在自己的领域数据上建评测集（真实查询 + 标注的相关文档），比较 recall@k、MRR、nDCG；同时比较延迟、成本、维度（存储）、上下文长度、多语言能力。讲义："Voyage/Cohere lead specific domains (finance, law, code)... Always benchmark on your own queries."
- **迁移的关键事实**：不同模型的向量空间**不兼容**，A 的查询向量不能去搜 B 的文档向量；换模型必须**全量重新 embed**。
- **迁移步骤**：
  1. 新建一套索引（新集合/新表），记录 `embedding_model` 与版本；
  2. 后台批量重算全部文档；增量数据双写到新旧两套索引；
  3. 影子流量 / A/B 测试对比线上指标（点击、答案正确率）；
  4. 切换读流量，保留旧索引一段时间以便回滚。
- **注意**：前缀约定（如 query/document 前缀）、归一化方式、相似度阈值都要随模型重新标定；cosine 阈值跨模型不可复用。
- 加分点：估算重算成本（token 数 × 单价）与时间；对超大库考虑先迁移热点数据。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 14 范数与距离](../../../01-math-foundations/14-norms-and-distances/docs/zh.md)：L2 范数、cosine、Euclidean 距离的数学基础。
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../../05-nlp-foundations-to-advanced/02-bag-of-words-tfidf/docs/zh.md)：本节 `SimpleEmbedder` 就是 TF-IDF。
- [阶段 05 · 03 词 Embeddings——从零实现 Word2Vec](../../../05-nlp-foundations-to-advanced/03-word-embeddings-word2vec/docs/zh.md)：讲义提到的 king − man + woman ≈ queen。
- [阶段 05 · 14 信息检索与搜索](../../../05-nlp-foundations-to-advanced/14-information-retrieval-search/docs/zh.md)：关键词检索与评估指标。
- [阶段 05 · 22 Embedding 模型 — 2026 年深度剖析](../../../05-nlp-foundations-to-advanced/22-embedding-models-deep-dive/docs/zh.md)：讲义建议选模型前先读，涵盖 dense/sparse/multi-vector 与 Matryoshka。

### 本节被哪些后续内容用到
- [阶段 11 · 05 Context Engineering](../../05-context-engineering/docs/zh.md)：用相似度检索决定把哪些内容放进上下文。
- [阶段 11 · 06 RAG（检索增强生成）](../../06-rag/docs/zh.md)：本节的切块 + 向量索引就是 RAG 的检索半边。
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../07-advanced-rag/docs/zh.md)：cross-encoder 重排、混合检索。
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../../05-nlp-foundations-to-advanced/23-chunking-strategies-rag/docs/zh.md)：切块策略的深入比较。
- [阶段 14 · 09 混合记忆：向量、图与 KV](../../../14-agent-engineering/09-hybrid-memory-mem0/docs/zh.md)：Agent 记忆中的向量检索。
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../../19-capstone-projects/65-hybrid-retrieval-bm25-dense/docs/zh.md)、[阶段 19 · 68 RAG Evaluation](../../../19-capstone-projects/68-rag-eval-precision-recall/docs/zh.md)：混合检索与检索评估的综合实践。

### 延伸关键词
`dense vs sparse` · `TF-IDF / smooth IDF` · `contrastive learning / InfoNCE` · `in-batch negatives` · `Sentence-BERT` · `bi-encoder / cross-encoder` · `cosine / dot / L2` · `ANN / HNSW / IVF / PQ` · `Matryoshka` · `binary quantization / Hamming` · `rescoring` · `MTEB` · `recall@k / MRR`
