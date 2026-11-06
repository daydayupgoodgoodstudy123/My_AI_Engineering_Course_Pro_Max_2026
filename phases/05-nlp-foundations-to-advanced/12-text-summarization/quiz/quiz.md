# 测验 · 文本摘要（Text Summarization）

> **阶段 05 · NLP 基础到进阶 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 抽取式 vs 生成式 | 抽取式 = 给句子打分排序、原样返回 top-k（语法一定正确，可能漏掉分散的信息）；生成式 = 条件生成新文本（流畅、压缩率高，可能编造事实） |
| 2 | TextRank | 句子为节点、相似度为边权，在图上跑 PageRank，与其他句子"连接越强"的句子得分越高（Mihalcea & Tarau, 2004） |
| 3 | PageRank 迭代 | `score_j = (1-d) + d·Σ_i (w_ij / Σ_k w_ik)·score_i`，阻尼 d=0.85，迭代到变化小于 ε |
| 4 | 生成式模型 | BART、T5、Pegasus 的 encoder-decoder，通过 cross-attention 逐 token 生成；Pegasus 用 gap-sentence 预训练目标，天然适合摘要 |
| 5 | ROUGE | Recall-Oriented：ROUGE-1/2 看 unigram/bigram 重叠，ROUGE-L 看最长公共子序列；用 `rouge-score` 并开启词干化 |
| 6 | ROUGE 之外 | BERTScore（语义相似）、BARTScore（以生成概率打分）、MoverScore、G-Eval（LLM 打分连贯/一致/流畅/相关）；用 50–100 条人工标注校准 |
| 7 | 四类幻觉 | 实体替换、数字漂移、极性反转、事实捏造 |
| 8 | 事实性检测 | FactCC（蕴涵分类器）、基于 QA 的事实性、实体级 F1；生成式在高风险领域必须有事实性闸门 |
| 9 | 选型 | 新闻用 `bart-large-cnn`，论文用 `pegasus-pubmed`，长文多文档用长上下文 LLM，对话用 samsum 微调模型，合规场景优先抽取式 |

### 核心技能（能动手做到）

- [ ] 从零实现句子切分、对数归一化的词重叠相似度和 TextRank 迭代，并解释每个参数（`damping`、`iterations`、`epsilon`）
- [ ] 能证明（或用代码验证）本节 TextRank 的得分总和恒等于句子数 n，并说明孤立句子会发生什么
- [ ] 从零实现 ROUGE-N 的精确率/召回率/F 值，以及基于 LCS 动态规划的 ROUGE-L
- [ ] 能说明分词（标点、大小写、词干化）对 ROUGE 数值的影响，并给出本节例子中的定量对比
- [ ] 能说出四类幻觉并为每类设计一种自动检测（如实体级 F1、数字比对）
- [ ] 能针对给定场景（文档类型、合规要求、长度、算力）按技能卡给出：方法、模型/库、评估方案、需要重点排查的失败模式

---

## 二、基础自测（选择题）

**Q1.** 关于抽取式与生成式摘要，下列说法**错误**的是：

- A. 抽取式本质上是排序问题，输出原样来自原文，所以语法一定正确
- B. 生成式本质上是生成问题，可能自信地编造原文没有的事实
- C. 抽取式完全不可能误导读者，因此任何场景都无需人工复核
- D. 抽取式的主要风险是漏掉分布在全文各处的信息

**Q2.** 在 TextRank 中，阻尼系数 `damping = 0.85` 的作用最接近：

- A. 只保留相似度大于 0.85 的边
- B. 每个句子得分中有一个固定的基础分 `1 - d`，其余部分来自邻居按边权传递的分数，保证迭代收敛
- C. 每轮迭代后把所有得分乘以 0.85
- D. 选出得分前 85% 的句子

**Q3.** ROUGE-L 衡量的是：

- A. 系统摘要与参考摘要的 unigram 重叠
- B. bigram 重叠
- C. 最长公共子序列（LCS），不要求连续但要求顺序一致
- D. 两段文本 embedding 的余弦相似度

**Q4.** 讲义强调计算 ROUGE 时"Always use stemming"，原因是：

- A. 词干化能把大写转为小写
- B. 不做词干化时，`running` 和 `run` 被当作不同的词，ROUGE 会低估真实重叠
- C. `rouge-score` 包要求必须开启词干化
- D. 词干化能检测幻觉

**Q5.** 原文："The board rejected the offer from Acme for 25,000 dollars." 摘要："The board accepted Acme's offer of 25 million dollars." 这个摘要包含了哪几类幻觉？

- A. 只有实体替换
- B. 极性反转 + 数字漂移
- C. 事实捏造 + 实体替换
- D. 没有幻觉，只是改写

**Q6.** Pegasus 在摘要任务上"不需要太多微调就表现很好"，讲义归因于：

- A. 它的参数量最大
- B. 它使用 gap-sentence 预训练目标：遮住文档中的整句并让模型生成它们，与摘要任务形式高度相似
- C. 它是抽取式模型
- D. 它只在新闻语料上预训练

**Q7.** 一份 300 页的合同超出了模型的上下文窗口。按讲义技能卡，正确的处理是：

- A. 直接截断，只保留前面能放进窗口的部分
- B. 分块后做 map-reduce 式摘要（先分块摘要，再汇总），而不是简单截断
- C. 改用 BLEU 评估
- D. 随机抽取几页做摘要

---

## 三、动手 / 代码题

**Q8.** 本节 `textrank` 的迭代部分：

```python
    scores = [1.0] * n
    for _ in range(iterations):
        new_scores = [1 - damping] * n
        for i in range(n):
            total_out = sum(sim[i]) or 1e-9
            for j in range(n):
                if sim[i][j] > 0:
                    new_scores[j] += damping * sim[i][j] / total_out * scores[i]
        if max(abs(s - ns) for s, ns in zip(scores, new_scores)) < epsilon:
            scores = new_scores
            break
        scores = new_scores

    ranked = sorted(range(n), key=lambda k: scores[k], reverse=True)[:top_k]
    ranked.sort()
    return [sentences[i] for i in ranked]
```

(a) 本节文章有 7 句，实测收敛后得分为 `[0.862, 1.153, 1.048, 1.167, 1.083, 0.666, 1.021]`，总和恰好是 7.0。请解释为什么总和恒等于 n。
(b) `sum(sim[i]) or 1e-9` 处理的是什么情况？此时该句子的得分是多少？总和还等于 n 吗？
(c) 先 `sorted(...)[:top_k]` 再 `ranked.sort()`，两次排序各自的目的是什么？

**Q9.** 本节的 ROUGE 实现：

```python
def rouge_n(hyp, ref, n=1):
    def ngrams(tokens, k):
        return Counter(tuple(tokens[i:i + k]) for i in range(len(tokens) - k + 1))

    hyp_tokens = hyp.lower().split()
    ref_tokens = ref.lower().split()
    hyp_ngrams = ngrams(hyp_tokens, n)
    ref_ngrams = ngrams(ref_tokens, n)
    if not ref_ngrams:
        return 0.0
    overlap = sum((hyp_ngrams & ref_ngrams).values())
    total = sum(ref_ngrams.values())
    return overlap / total
```

实际输出 `ROUGE-1: 0.381`、`ROUGE-2: 0.150`。参考摘要为：

```text
Researchers introduced a linear-time attention variant, trained up to 1B parameters, matched standard attention on benchmarks, and released code and weights.
```

(a) 这个函数算的是精确率、召回率还是 F 值？0.381 是哪两个数相除？
(b) 参考摘要按 `.split()` 切分后，有哪些 token 因为带着标点而无法与摘要匹配？如果先去掉标点，你预计 ROUGE-1 会升高还是降低？
(c) 如果把**整篇文章**当作"摘要"提交，这个函数的 ROUGE-1 会比 TextRank 的 3 句话更高还是更低？这说明了什么？

**Q10.** 讲义说"ROUGE-L scores longest common subsequence"，但代码只实现了 ROUGE-N。请实现 `rouge_l(hyp, ref)`，用动态规划求 LCS，返回 (precision, recall, F1)；并改写 `rouge_n` 让它同样返回三元组。用本节的 TextRank 输出和参考摘要计算结果。

---

## 四、面试高频题

**Q11.**（基础必考）抽取式摘要和生成式摘要有什么区别？各自的典型方法和主要风险是什么？你会怎么选？

**Q12.**（原理深挖）讲一下 TextRank 的原理：图怎么建、分数怎么算、为什么能收敛？和 PageRank、LexRank 有什么关系？有哪些可以改进的地方？

**Q13.**（原理深挖）ROUGE 有哪些局限？2026 年做摘要评估，你会怎么搭一套评估体系？

**Q14.**（工程实践）你们上线了一个基于 LLM 的新闻摘要功能，用户投诉"摘要里的数字和人名是错的"。请设计一个事实性检测与拦截方案。

**Q15.**（场景设计）合规团队需要每天对几百份长篇监管文件生成摘要，要求可追溯、不能编造。请给出架构方案。

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义 Step 4 特别说明：抽取式的幻觉风险**低得多**，但"they can still mislead if source sentences are decontextualized, outdated, or quoted out of order"——句子脱离上下文（例如代词指代不明）、信息过时、顺序被打乱，都可能误导读者。A、B、D 都是讲义原意。注意讲义术语表写的是"Never hallucinates"，这是相对于"编造新内容"而言，不等于"不会误导"。

### Q2 — 答案：B

本节代码中 `new_scores = [1 - damping] * n` 给每个句子 0.15 的基础分，剩下的 0.85 部分由邻居按归一化边权传递过来。在 PageRank 的随机游走解释中，`1-d` 相当于"随机跳转"的概率，它让迭代对应的线性映射成为压缩映射，从而保证收敛到唯一解。A、C、D 都是望文生义。

### Q3 — 答案：C

ROUGE-1、ROUGE-2 分别是 unigram、bigram 重叠；ROUGE-L 基于最长公共子序列——子序列不要求连续，但要求相对顺序一致，因此能在一定程度上反映语序/句子结构。D 是 BERTScore 一类的思路。

### Q4 — 答案：B

讲义原话："Without it, 'running' and 'run' count as different words and ROUGE undercounts." 词干化把屈折变化归并到同一词干。大小写由其他预处理负责（A）；`rouge-score` 中 `use_stemmer` 是可选参数（C）；ROUGE 本身不能检测幻觉（D）。

### Q5 — 答案：B

`rejected → accepted` 是**极性反转**；`25,000 → 25 million` 是**数字漂移**。实体 Acme 被保留，没有实体替换；也没有凭空加入原文没有的事件。这正是讲义列出的四类幻觉中最危险的两类——读起来完全通顺，含义却相反。

### Q6 — 答案：B

讲义："Pegasus in particular uses a gap-sentence pretraining objective that makes it excellent at summarization without much fine-tuning." 遮住重要句子再让模型生成，本身就是"根据其余内容写出关键句"，与摘要任务形式非常接近。

### Q7 — 答案：B

技能卡原文："Flag input over the model's context window as needing chunked map-reduce summarization (not just truncation)." 截断会直接丢掉后半部分内容，合同中的关键条款往往在后面。

### Q8 — 参考答案

(a) 每一轮中，句子 i 把自己的 `d · scores[i]` 按 `sim[i][j] / total_out` 的比例分给所有邻居 j，而这些比例之和为 1，所以"分出去的总量"恰好是 `d · Σ scores[i]`。再加上每个句子的基础分 `(1-d)`，新的总和为：

```text
Σ new_scores = (1 - d)·n + d·Σ scores
```

初始 `scores = [1.0] * n`，总和为 n，代入得 `(1-d)·n + d·n = n`。因此**每一轮**总和都保持 n，收敛后当然也是 7.0。这意味着平均得分为 1，大于 1 的句子就是"比平均更中心"的句子。

(b) 如果某个句子与其他所有句子都没有共同词（`sim[i]` 全为 0），`sum(sim[i])` 为 0，除法会抛 `ZeroDivisionError`；`or 1e-9` 把 0 换成一个极小正数（`0 or x` 返回 x）。实际上由于 `if sim[i][j] > 0` 的判断，这个孤立句子不会向任何人分数，它自己也收不到别人的分数，得分恒为 `1 - d = 0.15`。此时它的 `d · score` 那部分"漏掉"了，总和会**小于** n——这对应 PageRank 中"悬挂节点"（dangling node）的问题。

(c) 第一次按得分降序排序并取前 `top_k` 个下标，用于**选句**；第二次对选中的下标升序排序，用于**按原文顺序输出**，保证摘要读起来连贯（先讲背景再讲结论）。本节输出的 3 句（原文第 2、4、5 句）就是按原文顺序排列的，而它们的得分排名其实是第 4 句第一、第 2 句第二、第 5 句第三。

### Q9 — 参考答案

(a) 分母是参考摘要的 n-gram 总数，所以是**召回率**（ROUGE 的 R 就是 Recall-Oriented）。实测：TextRank 摘要 32 个 token、参考 21 个 token，截断重叠的 unigram 有 8 个（`a, and, attention×2, code, on, released, standard`），`8 / 21 ≈ 0.381`。ROUGE-2：参考有 20 个 bigram，重叠 3 个（`standard attention`、`attention on`、`code and`），`3 / 20 = 0.150`。

(b) 参考中的 `variant,`、`parameters,`、`benchmarks,`、`weights.` 都带着标点，而摘要里对应的是不带标点的 `variant`、`benchmarks`、`weights`（后者后面接的是 `on github.`），`.split()` 后无法匹配；参考里的 `linear-time` 也无法与摘要中的 `linear`、`time.` 对上。先用正则把标点替换为空格再算（`linear-time` 会被拆成 `linear time`），ROUGE-1 召回从 0.381 **升到 0.591**（已运行验证）。这说明分词预处理对 ROUGE 数值影响巨大——这也是讲义要求用 `rouge-score` 统一口径的原因。

(c) 更高。把整篇文章作为摘要时，召回率为 **0.571**（精确率只有 0.169）——比 TextRank 的 0.381 还高。只看召回会奖励"越长越好"，所以必须同时看精确率/F 值，或者像评测惯例那样限制摘要长度。`main.py` 结尾的提示"use the `rouge-score` package with stemming for a proper F-measure"正是在提醒这一点。

### Q10 — 参考答案

```python
from collections import Counter

def rouge_n_prf(hyp, ref, n=1):
    def ngrams(tokens, k):
        return Counter(tuple(tokens[i:i + k]) for i in range(len(tokens) - k + 1))
    h, r = ngrams(hyp.lower().split(), n), ngrams(ref.lower().split(), n)
    overlap = sum((h & r).values())
    p = overlap / sum(h.values()) if h else 0.0
    rc = overlap / sum(r.values()) if r else 0.0
    f = 0.0 if p + rc == 0 else 2 * p * rc / (p + rc)
    return p, rc, f

def lcs_len(a, b):
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[-1][-1]

def rouge_l(hyp, ref):
    h, r = hyp.lower().split(), ref.lower().split()
    lcs = lcs_len(h, r)
    if lcs == 0:
        return 0.0, 0.0, 0.0
    p, rc = lcs / len(h), lcs / len(r)
    return p, rc, 2 * p * rc / (p + rc)
```

本节数据实测（`joined` 为 TextRank 的 3 句拼接）：

| 指标 | Precision | Recall | F1 |
|------|-----------|--------|----|
| ROUGE-1 | 0.250 | 0.381 | 0.302 |
| ROUGE-2 | 0.097 | 0.150 | 0.118 |
| ROUGE-L（LCS = 8） | 0.250 | 0.381 | 0.302 |
| ROUGE-L（先去标点） | 0.344 | 0.500 | 0.407 |

要点：
- `dp[i][j]` 表示 `h[:i]` 与 `r[:j]` 的 LCS 长度，相等时对角线 +1，否则取上方/左方的较大值，复杂度 `O(|h|·|r|)`。
- 本例中 LCS 恰好等于 unigram 重叠数 8，说明摘要里匹配到的词与参考的顺序基本一致；若摘要语序被打乱，ROUGE-L 会低于 ROUGE-1。
- 这里用的是 F1（β=1）；`rouge-score` 默认报告的 `fmeasure` 也是 F1。生产中还要加词干化（`use_stemmer=True`），多句摘要常用按句计算的 ROUGE-Lsum。

### Q11 — 参考回答要点

- **抽取式**：给每个句子打分、返回 top-k 原句。方法：TextRank、LexRank（`sumy`）、LSA，或有监督的句子分类器；也有最朴素的 Lead-3（取前三句）基线。优点：不编造内容、可追溯、便宜；风险：漏掉分散的信息、句子脱离上下文后可能误导、压缩率有限、冗余。
- **生成式**：encoder-decoder（BART、T5、Pegasus）或 LLM，条件生成新文本。优点：流畅、压缩率高、可以整合多处信息；风险：幻觉（实体替换、数字漂移、极性反转、事实捏造）。
- **怎么选**（讲义 + 技能卡）：
  - 医疗、法律、金融、受监管内容：默认抽取式；生成式必须有事实性闸门；
  - 新闻 3–5 句摘要：`facebook/bart-large-cnn`；论文：`google/pegasus-pubmed`；对话：samsum 微调模型；
  - 多文档、长文：长上下文 LLM，代价是成本和可复现性。
- **加分点**：混合方案——先抽取关键句（控制事实来源），再让生成模型改写压缩，并在输出中附上来源句引用。

### Q12 — 参考回答要点

- **建图**：每个句子一个节点；边权为句子相似度。原始 TextRank 用"共有词数 / (log|Sᵢ| + log|Sⱼ|)"（本节代码用 `log(len + 1)` 避免单词句分母为 0）；也可以用 TF-IDF 余弦（LexRank 的做法）或句向量余弦。
- **打分**：加权 PageRank，`WS(j) = (1-d) + d·Σ_i (w_ij / Σ_k w_ik)·WS(i)`，d=0.85；迭代到最大变化小于 ε（代码 1e-4，本例 8 轮收敛）。
- **为什么收敛**：`(1-d)` 项使迭代成为压缩映射（d < 1），且归一化后的转移矩阵是随机矩阵，存在唯一的平稳分布——这就是马尔可夫链"随机游走 + 随机跳转"的平稳分布。
- **复杂度**：相似度矩阵 `O(n²·L)`，每轮迭代 `O(n²)`；长文档要先分段或用稀疏图（只保留 top-k 邻居）。
- **可改进**：去停用词和标点（本节代码中 `the`、`at` 等也计入了重叠，`paper.` 与 `paper` 却匹配不上）；用句向量相似度；加入位置先验（新闻的前几句通常更重要）；用 MMR 去冗余，避免选出意思重复的句子。
- **加分点**：指出本节实现的得分总和恒为 n（Q8），孤立节点相当于 PageRank 的悬挂节点。

### Q13 — 参考回答要点

- **ROUGE 的局限**：
  1. 只看表面 n-gram/LCS 重叠，同义改写被低估；
  2. 召回导向，对长度敏感（Q9(c)：整篇文章召回更高），需要看 F 值并控制长度；
  3. 完全不衡量事实性——一个极性反转的摘要可能 ROUGE 很高；
  4. 对预处理极其敏感（Q9(b)：仅去标点就从 0.381 变成 0.591）。
- **评估体系**（讲义的生产建议）：
  - ROUGE-L（含 ROUGE-1/2，`rouge-score` + 词干化）用于历史对比和回归；
  - BERTScore 衡量语义重叠；
  - G-Eval（LLM 按连贯、一致、流畅、相关打分）用于连贯性与事实性；讲义称设计良好的 rubric 下与人工一致率约 80%；
  - 生成式摘要额外加事实性检查（FactCC / QA-based / 实体级 F1）；
  - 所有指标用 50–100 条人工标注摘要校准。
- **常见误区**：只报告 ROUGE；把 LLM 打分当作无需校准的真理。

### Q14 — 参考回答要点

- **检测层**（讲义的三种方法 + 工程化）：
  1. **实体级检查**：用 NER 抽取原文与摘要中的实体，计算摘要实体对原文的精确率——只出现在摘要里的实体可疑（实体替换、事实捏造）；
  2. **数字比对**：抽取摘要中的数字、日期、金额，规范化单位后必须能在原文找到（数字漂移，如 25,000 → 25 million）；
  3. **蕴涵检查**：用 NLI / FactCC 类分类器判断每个摘要句是否被原文蕴涵（极性反转）；
  4. **QA-based**：从摘要生成问题，分别用原文和摘要回答，答案不一致则标记。
- **拦截策略**：任一检查失败 → 重新生成（降低温度、加入"只用原文信息"的约束）→ 仍失败则回退到抽取式摘要或转人工审核。
- **监控**：按检查类型统计失败率；抽样人工复核校准阈值；技能卡指出新闻摘要中最常见的是实体替换。
- **加分点**：生成时就降低风险——让模型在摘要中引用原文句子编号，便于逐句核验；避免温度采样。

### Q15 — 参考回答要点

- **原则**：监管文件属于合规场景，技能卡要求生成式必须有事实性闸门；讲义："extractive is the safer default"。
- **架构**：
  1. 解析与分块：按章节/条款切分（超出上下文窗口时做 map-reduce，而不是截断）；
  2. 抽取层：每块用 TextRank / LexRank 或监督模型选出关键句，保留文档 ID、页码、句子位置；
  3. 可选的生成层：只基于抽取出的句子做改写压缩，并要求逐句给出来源引用；
  4. 事实性闸门：实体/数字比对 + NLI 蕴涵检查，不通过则退回纯抽取结果；
  5. 输出：摘要 + 每句的原文出处链接，供合规人员一键核对。
- **评估**：ROUGE + BERTScore 做回归；每周抽样人工评估；记录事实性检查拦截率。
- **常见误区**：直接把整份文件塞进 LLM 要摘要、没有出处、没有事实性检查。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../02-bag-of-words-tfidf/docs/zh.md)：词重叠、TF-IDF 余弦是句子相似度的基础。
- [阶段 05 · 11 机器翻译](../../11-machine-translation/docs/zh.md)：BLEU（精确率导向）与 ROUGE（召回导向）是一对近亲；encoder-decoder 生成。
- [阶段 01 · 21 图论](../../../01-math-foundations/21-graph-theory/docs/zh.md)：图、邻接矩阵、PageRank 的图视角。
- [阶段 01 · 22 随机过程](../../../01-math-foundations/22-stochastic-processes/docs/zh.md)：马尔可夫链与平稳分布，PageRank 收敛的数学基础。

### 本节被哪些后续内容用到
- [阶段 05 · 13 问答系统](../../13-question-answering/docs/zh.md)：QA-based 事实性检测依赖问答模型。
- [阶段 05 · 21 自然语言推理——文本蕴涵](../../21-nli-textual-entailment/docs/zh.md)：FactCC 等事实性检查本质是蕴涵判断。
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../23-chunking-strategies-rag/docs/zh.md)：长文档分块与 map-reduce 摘要。
- [阶段 05 · 24 共指消解](../../24-coreference-resolution/docs/zh.md)：抽取句中的代词脱离上下文会误导，共指消解可缓解。
- [阶段 05 · 27 LLM Evaluation](../../27-llm-evaluation-frameworks/docs/zh.md)：G-Eval 与 LLM-as-judge 的系统方法。
- [阶段 05 · 28 长上下文 Evaluation](../../28-long-context-evaluation/docs/zh.md)：长上下文 LLM 摘要的能力评估。
- [阶段 07 · 08 T5、BART 与 encoder-decoder](../../../07-transformers-deep-dive/08-t5-bart-encoder-decoder/docs/zh.md)：BART/T5/Pegasus 的架构。

### 延伸关键词
`LexRank` · `Lead-3 基线` · `MMR 去冗余` · `ROUGE-Lsum` · `BERTScore` · `BARTScore` · `G-Eval` · `FactCC` · `QAGS / QA-based faithfulness` · `map-reduce 摘要` · `pointer-generator` · `CNN/DailyMail / XSum / SAMSum`
