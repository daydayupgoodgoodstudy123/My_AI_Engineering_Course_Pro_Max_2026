# 测验 · 主题建模 — LDA 和 BERTopic（Topic Modeling — LDA and BERTopic）

> **阶段 05 · NLP 从基础到进阶 · 第 15 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 主题建模要解决的问题 | 无监督：没有标签、也不知道有几类，从语料中找出少量连贯主题，并给每篇文档一个主题分布 |
| 2 | LDA 生成故事 | 主题 = 词上的分布；文档 = 主题的混合；生成一个词时先从文档的主题混合中抽主题，再从该主题的词分布中抽词；推断就是把这个过程反过来 |
| 3 | LDA 的两个输出矩阵 | `doc_topic`：`(n_docs, n_topics)`，每行和为 1；`topic_word`：`(n_topics, vocab_size)`，每行和为 1 |
| 4 | 推断方法 | collapsed Gibbs 采样或变分贝叶斯；Gibbs 每次给一个 token 重新采样主题：`p(z=k) ∝ (n_dk + α)·(n_kw + β)/(n_k + Vβ)` |
| 5 | LDA 要原始计数 | 用 `CountVectorizer` 而不是 TF-IDF，因为模型是定义在整数词计数上的；还要去停用词、用 `min_df`/`max_df` 过滤过稀 / 过泛的词 |
| 6 | BERTopic 四步 | sentence transformer 编码（如 384 维 MiniLM）→ UMAP 降到约 5 维 → HDBSCAN 密度聚类（含 -1 离群标签）→ 每个簇算 class-based TF-IDF 取主题词 |
| 7 | 单主题 vs 混合成员 | BERTopic 一篇文档一个主题（可选 HDBSCAN 软概率）；LDA 是混合成员，适合长文档 |
| 8 | 评估 | c_v 一致性（基于滑动窗口内 top 词的 NPMI，再聚合比较余弦）、topic diversity（所有主题 top 词中唯一词的比例）、人工阅读 |
| 9 | 选型主轴：文档长度 | 短文本（推文、评论、标题）选 BERTopic；长文档、需要多主题分布、无 GPU / 边缘部署选 LDA（或 NMF）；BERT 会截断，LDA 计数不受长度限制 |

### 核心技能（能动手做到）

- [ ] 从零实现 collapsed Gibbs LDA：维护 `ndt / ntw / nt` 三个计数表，正确地"先减后采样再加"
- [ ] 从计数表算出 `doc_topic` 与 `topic_word`（带 α、β 平滑），并验证每行和为 1
- [ ] 解释本节 demo 输出为什么没有分出"金融 / AI / 政治"三类，并说出至少两种改进
- [ ] 用 scikit-learn 跑 LDA（`CountVectorizer(stop_words="english", min_df=2, max_df=0.9)` + `LatentDirichletAllocation`）并打印每个主题的 top 词
- [ ] 用 BERTopic 跑一遍，过滤掉 `Topic == -1` 的离群桶，读懂 `get_topic_info()`
- [ ] 计算 topic diversity，并用 `gensim.models.CoherenceModel(coherence="c_v")` 比较不同主题数

---

## 二、基础自测（选择题）

**Q1.** 关于 LDA 的建模假设，正确的是：

- A. 每篇文档只属于一个主题
- B. 每篇文档是多个主题的混合，每个主题是词表上的概率分布
- C. 每个主题是一个文档簇的质心向量
- D. LDA 需要预先标注好的主题标签

**Q2.** BERTopic 流水线的正确顺序是：

- A. TF-IDF → k-means → UMAP → 句向量
- B. 句向量编码 → HDBSCAN → UMAP → c-TF-IDF
- C. 句向量编码 → UMAP 降维 → HDBSCAN 聚类 → class-based TF-IDF 提取主题词
- D. LSTM 端到端训练 → softmax 输出主题

**Q3.** 用 scikit-learn 跑 LDA 时应该用 `CountVectorizer` 而不是 `TfidfVectorizer`，因为：

- A. LDA 不支持浮点数输入，会直接报错
- B. LDA 的概率模型定义在原始词计数上，TF-IDF 加权会扭曲它假设的分布
- C. TF-IDF 太慢
- D. CountVectorizer 自带停用词表而 TfidfVectorizer 没有

**Q4.** BERTopic 输出中主题编号为 `-1` 的文档表示：

- A. 停用词主题
- B. 文档数最多的主题
- C. HDBSCAN 无法可靠归入任何簇的离群文档
- D. 训练失败的文档

**Q5.** 一家公司要分析 20 万条平均 15 个词的用户评论，追求语义连贯的主题，并有 GPU。优先选：

- A. LDA，因为它是经典方法
- B. BERTopic，短文本上词共现太稀疏，embedding 能捕捉语义相似
- C. 不需要主题模型，直接用 BM25
- D. NMF，因为它一定比 BERTopic 好

**Q6.** 在 collapsed Gibbs 采样公式 `p(z=k) ∝ (n_dk + α)·(n_kw + β)/(n_k + Vβ)` 中，`(n_dk + α)` 这一项表达的是：

- A. 词 w 在主题 k 中有多常见
- B. 当前文档 d 已经有多少词被分给主题 k（文档偏好哪个主题）
- C. 主题 k 的总词数
- D. 词表大小

**Q7.** 把 LDA 的 `α` 从 0.1 调到 5.0，文档的主题分布通常会：

- A. 更稀疏，每篇文档集中在一两个主题上
- B. 更平滑，每篇文档在各主题上的比例更接近均匀
- C. 不受影响
- D. 所有主题的 top 词变得一样

**Q8.** 关于 topic diversity，正确的是：

- A. 它是所有主题 top 词中**唯一词**所占的比例，越高说明主题之间重叠越少
- B. 它是主题数除以文档数
- C. 越低越好
- D. 它衡量的是同一主题内 top 词的共现程度

---

## 三、动手 / 代码题

**Q9.** 本节 `main.py` 的真实输出如下：

```text
=== LDA topics (collapsed Gibbs, 300 iters) ===
  topic 0: the, new, s, p, earnings, reports, openai, released
  topic 1: cut, for, stocks, rose, after, fed, interest, rates
  topic 2: bond, yields, fell, investors, bought, treasuries, 500, hit

=== document mixtures ===
  [0.13, 0.86, 0.01]  stocks rose after the fed cut interest rates
  [0.02, 0.02, 0.97]  bond yields fell as investors bought treasuries
  [0.66, 0.01, 0.33]  the s p 500 hit a new high on earnings reports
  [0.01, 0.98, 0.01]  chip makers reported strong demand for ai accelera
  [0.97, 0.01, 0.01]  openai released a new model with multimodal reason
  [0.01, 0.01, 0.97]  deep learning researchers published a paper on eff
  [0.81, 0.02, 0.17]  the senate passed a bill on healthcare spending
  [0.97, 0.01, 0.01]  the president signed new tariffs on steel imports
  [0.01, 0.97, 0.01]  congress debated a tax cut for small businesses
```

语料的设计意图显然是"金融 3 篇、AI 3 篇、政治 3 篇"，但结果把 chip makers（AI）和 congress tax cut（政治）分进了金融主题 1，把 openai 和 senate、president 分进了主题 0。请解释原因（提示：统计每个词出现在几篇文档里），并给出改进方向。

**Q10.** 下面是 Gibbs 采样的核心循环。(1) 为什么在计算 `probs` 之前要先把当前 token 的计数减 1？忘了减会怎样？(2) 一次完整迭代（遍历所有 token）的时间复杂度是多少？

```python
    for _ in range(n_iters):
        for d in range(D):
            for i, w in enumerate(indexed[d]):
                t = z[d][i]
                ndt[d][t] -= 1
                ntw[t][w] -= 1
                nt[t] -= 1

                probs = []
                for k in range(n_topics):
                    p = (ndt[d][k] + alpha) * (ntw[k][w] + beta) / (nt[k] + V * beta)
                    probs.append(p)
                # ... 按 probs 采样 new_t，再把三个计数加回去
```

**Q11.** `collapsed_gibbs_lda` 只返回了每个主题的 top-8 词和 `doc_topic`，没有返回讲义里的 `topic_word` 矩阵。请在函数末尾补一段代码计算 `topic_word`（`n_topics × V`，每行和为 1，使用 β 平滑），并写一个 `topic_diversity(topics)` 函数。

**Q12.** 本节 `tokenize` 如下。`tokenize("AI and ML in the U.S. by 2026, a GPU")` 返回什么？这个分词器对 LDA 有什么隐患？

```python
SHORT_ALLOWLIST = {"ai", "ml", "nn", "s", "p", "pr"}

def tokenize(text):
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 2 or t.isdigit() or t in SHORT_ALLOWLIST]
```

---

## 四、面试高频题

**Q13.**（基础必考）讲一下 LDA 的生成过程，以及 Dirichlet 先验 α、β 分别控制什么。LDA 和 pLSA / NMF 的关系是什么？

**Q14.**（原理深挖）BERTopic 为什么要先用 UMAP 降维再用 HDBSCAN 聚类？为什么主题词用 class-based TF-IDF 而不是直接取簇中心最近的词？

**Q15.**（场景设计）你有 1 万张客服工单（长度从一句话到几页不等），老板想知道"用户都在抱怨什么"，并且每周追踪趋势。你会怎么做？

**Q16.**（工程实践）主题数怎么选？怎么评估一个主题模型的好坏？只看困惑度（perplexity）够不够？

**Q17.**（追问型）2026 年有了 LLM，主题建模还有必要吗？如果要用 LLM，你会怎么把它和传统方法结合？

---

## 五、参考答案与解析

### Q1 — 答案：B

LDA 的核心是**混合成员**（mixed membership）：文档在所有主题上有一个分布，主题在所有词上有一个分布。A 是 BERTopic 的硬分配特点；C 描述的是聚类式方法；D 错在主题建模是无监督的。

### Q2 — 答案：C

讲义的四步：sentence transformer 编码（如 `all-MiniLM-L6-v2`，384 维）→ UMAP 降到约 5 维 → HDBSCAN 聚类 → 对每个簇做 class-based TF-IDF 取主题词。B 把 UMAP 和 HDBSCAN 的顺序弄反了——高维 embedding 直接做密度聚类效果很差。

### Q3 — 答案：B

LDA 的似然建立在"每个词位置是一次离散抽样"之上，输入应是整数计数。TF-IDF 值是重新加权后的实数，会破坏这个假设。A 错：sklearn 实际上能接受浮点矩阵而不报错——这正是危险之处，**不报错不代表用法正确**。

### Q4 — 答案：C

HDBSCAN 是密度聚类，无法归入任何稠密区域的点被标为噪声 `-1`。BERTopic 示例中 `info[info["Topic"] != -1]` 就是把这个离群桶过滤掉。skill 中也提醒：BERTopic 的典型失败模式是 -1 簇"吞掉"大量含义模糊的文档。

### Q5 — 答案：B

15 个词的短文本，词共现极稀疏，LDA 的连贯性会崩（skill：对 10 个 token 以下的短文本拒绝 LDA）。BERTopic 在 embedding 空间里度量语义相似，讲义"短文本选 BERTopic""追求最大语义连贯选 BERTopic"。NMF 在短文本上与 LDA 质量相当、速度快，是无 GPU 时的备选，但并不"一定更好"。

### Q6 — 答案：B

`n_dk` 是文档 d 中当前被分配给主题 k 的词数，`α` 是平滑。这一项体现"文档已经偏向哪个主题，新词也倾向于分过去"。A 是 `(n_kw + β)/(n_k + Vβ)` 那一项的含义；两项相乘就是"文档偏好 × 主题对这个词的偏好"。

### Q7 — 答案：B

`doc_topic` 的计算是 `(n_dk + α)/(Σn_d + Kα)`，α 越大，平滑越强，分布越接近均匀。实测把 α 改成 5.0 后，前三篇文档的混合变成 `[0.30, 0.35, 0.35]` 这类接近均匀的值（原来是 `[0.13, 0.86, 0.01]`）。小 α（如 0.1）鼓励稀疏——每篇文档只用少数几个主题。

### Q8 — 答案：A

讲义："Topic diversity：所有主题 top 词中唯一词所占比例，越高越好（主题之间不重叠）"。D 描述的是一致性（coherence）。

### Q9 — 参考答案

原因：**LDA 只能从词的共现中学习，而这 9 篇文档几乎没有共享词**。统计 `tokenize` 后每个词出现在几篇文档中，58 个词里只有 4 个出现在 1 篇以上：

| 词 | 出现文档数 | 出现在哪些文档 |
|----|-----------|---------------|
| `the` | 4 | stocks…、the s p 500…、senate…、president… |
| `new` | 3 | the s p 500…、openai…、president… |
| `cut` | 2 | stocks…、congress…tax cut… |
| `for` | 2 | chip makers…for ai…、congress…for small… |

于是：

- 主题 1 = 通过 `cut`、`for` 连起来的文档：stocks（cut）、congress（cut、for）、chip makers（for）。
- 主题 0 = 通过 `the`、`new` 连起来的文档：openai（new）、senate（the）、president（the、new）；the s p 500 也有 `the`、`new`，所以占 0.66。
- 主题 2 = 剩下与谁都不共享词的 bond 和 deep learning（以及 s p 500 的一部分）。

"金融 / AI / 政治"的语义区分（`stocks` 与 `bond` 都是金融）对 LDA 来说**不可见**，因为它们是不同的词。决定分组的反而是 `the / new / for / cut` 这类虚词——这正是讲义说的"junk topics 吸收停用词和高频词"，也印证了 skill 中"对非常短的文本拒绝 LDA"。

改进方向：

1. **去停用词**、设置 `min_df`/`max_df`（讲义 sklearn 示例的做法）。但要注意，本语料去掉停用词后**几乎不剩任何共享词**，换不同 seed 结果仍然各不相同（已实测），所以仅靠这一步不够。
2. **增大语料**：每个主题需要几十上百篇、反复出现同一批领域词（`stocks / bond / yields / fed` 多次共现），LDA 才有统计信号。
3. **词形归一**：`reported` / `reports` 合并（词干化 / 词形还原，第 01 节）。
4. 短文本场景直接换 **BERTopic**：embedding 能知道 `stocks` 和 `bond` 语义相近。

### Q10 — 参考答案

(1) collapsed Gibbs 要采样的是条件分布 `p(z_i = k | z_{-i}, w)`，即"在**其他所有** token 的分配给定时，当前 token 属于哪个主题"。所以计算前必须把当前 token 自己的贡献从 `ndt / ntw / nt` 中去掉。忘了减，当前 token 会"给自己投票"：它原来所在的主题 t 的计数多了 1，被重新选中的概率偏高，链条变得粘滞、混合变慢，采到的也不再是正确的后验分布。最后还要把三个计数**加回**新主题上，保持"计数表 = 当前所有分配的统计"这一不变量。

(2) 每个 token 要对 K 个主题各算一次概率，再做一次 O(K) 的累加采样，所以一次迭代是 **O(N·K)**，N 是语料总 token 数；总复杂度 O(n_iters·N·K)。本 demo 中 N=65、K=3、n_iters=300，约 6 万次概率计算，所以几十毫秒就跑完。大语料上 K 很大时，会用 SparseLDA、AliasLDA、LightLDA 等稀疏 / 别名表技巧把单 token 采样降到接近 O(1) 均摊。

### Q11 — 参考答案

在 `return` 之前加入：

```python
    topic_word = []
    for k in range(n_topics):
        denom = nt[k] + V * beta
        topic_word.append([(ntw[k][w] + beta) / denom for w in range(V)])
    # 校验：每行和为 1
    assert all(abs(sum(row) - 1.0) < 1e-9 for row in topic_word)
```

为什么分母是 `nt[k] + V·β`：分子对所有 w 求和得 `Σ_w ntw[k][w] + V·β = nt[k] + V·β`，因此每行恰好归一。这与 `doc_topic` 用 `sum(ndt[d]) + n_topics·α` 做分母是同一个道理。

```python
def topic_diversity(topics):
    """topics: 每个主题的 top 词列表，如 collapsed_gibbs_lda 返回的 topics"""
    all_words = [w for words in topics for w in words]
    if not all_words:
        return 0.0
    return len(set(all_words)) / len(all_words)
```

本 demo 的 3 个主题 × 8 个词全部不重复，diversity = 24/24 = 1.0——这也说明 **diversity 高不代表主题好**：本例主题词里混着 `the`、`for`，语义并不连贯，所以还要结合 coherence 和人工阅读。

### Q12 — 参考答案

```python
['ai', 'and', 'ml', 'the', 's', '2026', 'gpu']
```

逐个看：`ai`、`ml`、`s` 在白名单里保留；`and`、`the`、`gpu` 长度 3 > 2 保留；`2026` 是数字保留；`in`、`by`、`a` 长度 ≤ 2 且不在白名单，被丢弃；`U.S.` 被正则拆成 `u`、`s`，`u` 被丢弃、`s` 因白名单保留。

隐患：

- **长度过滤 ≠ 停用词过滤**：`the`、`and`、`for`、`new` 都是 3 个字母以上的高频虚词，会全部保留，在 LDA 里形成"垃圾主题"（Q9 的输出就是证据）。
- 白名单里的 `s`、`p` 是为了保留 "s p 500" 而加的，但它们也会匹配所有格 `'s`（如 "Google's" → `google`、`s`），引入噪声。
- 只认 ASCII，`café` 变 `caf`，中文全部丢失。

### Q13 — 参考回答要点

- **生成过程**（K 个主题、V 个词）：
  1. 对每个主题 k，从 `Dirichlet(β)` 抽一个词分布 `φ_k`；
  2. 对每篇文档 d，从 `Dirichlet(α)` 抽一个主题分布 `θ_d`；
  3. 对文档中每个位置：先从 `θ_d` 抽主题 z，再从 `φ_z` 抽词 w。
- 推断：观察到的只有 w，要反推 `θ`（即 `doc_topic`）和 `φ`（即 `topic_word`）。精确后验不可解，用 collapsed Gibbs（把 θ、φ 积分掉，只采样 z）或变分贝叶斯（sklearn、gensim 采用）。
- **α**：文档-主题先验，小 α ⇒ 每篇文档只用少数主题；**β**：主题-词先验，小 β ⇒ 每个主题集中在少数词上。本节代码默认 α=0.1、β=0.01，都是鼓励稀疏的设置。
- 与其他方法的关系：pLSA 是没有 Dirichlet 先验的版本（无法自然推广到新文档、易过拟合）；NMF 把文档-词矩阵分解为两个非负矩阵 `W·H`，可以看作非概率版的同一思想，讲义称其速度快、在短文本上与 LDA 质量相当。
- 加分点：能写出 Gibbs 更新公式并解释两项的含义。

### Q14 — 参考回答要点

- **为什么先 UMAP**：384 维的句向量对密度聚类来说太高维——高维空间中点与点的距离趋于接近（维度灾难），"密度"难以区分。UMAP 是保持局部结构的流形学习，把向量压到约 5 维，让语义相近的文档在低维空间里形成可分的稠密区域，HDBSCAN 才能有效工作。
- **为什么 HDBSCAN**：不需要预先指定簇数；能找到大小不一的簇；会把不属于任何稠密区域的点标为 -1，而不是硬塞进某个簇。`min_topic_size`（库默认 10，讲义示例设为 15，大语料可调到 50–100）控制最小簇大小。
- **为什么 c-TF-IDF**：聚类给出的是文档分组，要给人看的是"代表词"。c-TF-IDF 把一个簇的所有文档**当成一篇大文档（一个 class）**，在簇与簇之间计算 TF-IDF：在本簇频繁、在其他簇少见的词得分高。BERTopic 论文中的形式为 `W(t,c) = tf(t,c) · log(1 + A / tf(t))`，其中 A 是每个类的平均词数、`tf(t)` 是词 t 在所有类中的总频次。相比"离簇中心最近的词"，它直接基于该簇的真实用词，更可解释，也不需要词向量和句向量在同一空间。
- 加分点：主题词得到后，还可以用 LLM 给每个簇命名（讲义：BERTopic 直接支持 LLM 打标签）。

### Q15 — 参考回答要点

- **数据准备**：去模板话术、签名、工单编号；按长度分流——长工单要么分块后聚合，要么走 LDA（讲义：超过 embedding 模型上下文的文档，"要么分块聚合，要么用 LDA"；skill：没有分块策略时拒绝对长文档用 BERTopic）。
- **方法**：工单以短文本为主、关心语义 ⇒ BERTopic（`all-MiniLM-L6-v2` 起步，`min_topic_size` 按 1 万文档量级调大）；如果需要"一张工单同时涉及物流 + 退款"的多主题比例，补一个 LDA。
- **主题数参考**：skill 的经验公式 `max(5, round(sqrt(n_docs)))`，1 万篇 ≈ 100，并对 4 万篇以下的语料设上限 200。BERTopic 由 HDBSCAN 自动确定簇数，可再合并相近主题。
- **评估**：c_v coherence、topic diversity、随机抽 20 篇人工阅读；重点检查 -1 离群桶有多大、有没有"吞掉"重要投诉。
- **趋势追踪**：固定模型对新一周数据 `transform` 得到主题分布，按周统计各主题占比；定期重训，用 LLM 给主题起名方便汇报。
- 常见误区：直接对原始工单跑 LDA 而不做停用词 / 模板清洗，得到一堆"您好 / 谢谢 / 订单"的垃圾主题。

### Q16 — 参考回答要点

- **主题数**：没有唯一正确答案。做法是扫描多个值（讲义练习：5、10、20、50），画出 coherence 随主题数变化的曲线，选在拐点附近、且人工阅读可接受的值。skill 给出了起点 `max(5, round(sqrt(n_docs)))`，并提示：小于 5 很可能不对，4 万篇以下超过 200 很可能过度切分。
- **自动指标**：
  - c_v coherence：top 词在滑动窗口中的 NPMI 聚合后做余弦比较，越高越好（`gensim.models.CoherenceModel(coherence="c_v")`）；
  - topic diversity：主题间 top 词不重叠的程度。
- **人工评估**：读每个主题的 top 词，能不能叫出名字；抽样文档看分配是否合理。讲义："人的判断仍是最后一道防线。"
- **困惑度够不够**：不够。困惑度衡量的是对留出文档的预测似然，与人对主题可解释性的判断并不一致，主题数越多困惑度往往越低，却可能把主题切得支离破碎。所以实践中以 coherence + diversity + 人工阅读为主。
- 加分点：同时看两个指标——coherence 高但 diversity 低，说明很多主题在重复同一批词。

### Q17 — 参考回答要点

- **仍然有必要**：对 10 万级文档逐篇喂 LLM 成本高、不稳定、难复现；主题建模是便宜、可复现的"第一遍结构化"。LDA 在需要文档级多主题分布、可解释的词级概率、边缘 / 无 GPU 部署时仍是首选（讲义选型表）。
- **结合方式**（讲义"LLM-based labeling"）：先用任意聚类（BERTopic / LDA）分组，再让 LLM 根据每个簇的 top 词和代表文档**起名、写摘要**；也可以让 LLM 合并语义重复的主题、审查 -1 离群桶。
- **embedding 侧**：BERTopic 本身就用了预训练编码器，可以换成更强的 embedding 模型（第 22 节）。
- **风险**：LLM 命名可能过度概括或"编"出簇里没有的主题，需要人工抽检；簇本身的质量仍由聚类决定。
- 加分点：提到 FASTopic、Top2Vec 等更新的选择，以及对超大语料的速度考量。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../02-bag-of-words-tfidf/docs/zh.md)：LDA 的输入是词袋计数，c-TF-IDF 是 TF-IDF 的变体。
- [阶段 05 · 03 从零实现 Word2Vec](../../03-word-embeddings-word2vec/docs/zh.md)：理解"语义相近的词在向量空间里相近"，这是 BERTopic 的基础。
- [阶段 01 · 06 概率与分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)、[阶段 01 · 16 采样方法](../../../01-math-foundations/16-sampling-methods/docs/zh.md)：Dirichlet 分布与 Gibbs 采样。
- [阶段 01 · 10 降维](../../../01-math-foundations/10-dimensionality-reduction/docs/zh.md)：UMAP 等降维方法的背景。

### 本节被哪些后续内容用到
- [阶段 02 · 07 无监督学习](../../../02-ml-fundamentals/07-unsupervised-learning/docs/zh.md)：聚类方法的通用视角，与 BERTopic 的 HDBSCAN 一脉相承。
- [阶段 05 · 22 Embedding 模型深度剖析](../../22-embedding-models-deep-dive/docs/zh.md)：BERTopic 的效果上限取决于 embedding 模型。
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../23-chunking-strategies-rag/docs/zh.md)：长文档"分块再聚合"的处理思路。
- [阶段 11 · 04 Embeddings](../../../11-llm-engineering/04-embeddings/docs/zh.md)：在 LLM 应用中使用 embedding 做聚类与分析。

### 延伸关键词
`Dirichlet 分布` · `pLSA` · `NMF` · `变分推断` · `c-TF-IDF` · `UMAP` · `HDBSCAN` · `NPMI / c_v coherence` · `Top2Vec` · `FASTopic` · `动态主题模型`
