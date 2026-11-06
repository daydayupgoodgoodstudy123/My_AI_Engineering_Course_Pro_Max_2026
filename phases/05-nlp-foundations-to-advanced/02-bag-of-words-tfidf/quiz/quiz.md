# 测验 · 词袋、TF-IDF 和文本表示（Bag of Words, TF-IDF, and Text Representation）

> **阶段 05 · NLP 基础到高级 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 文本 → 定长向量 | 分类器需要固定长度的数值输入；BoW 用"词表大小"作为向量维度，第 i 维是第 i 个词的出现次数 |
| 2 | BoW 丢弃词序 | "dog bites man" 与 "man bites dog" 的 BoW 完全相同；换来的是简单、快速、可解释 |
| 3 | TF / DF / IDF | TF：词在文档内的频率；DF：包含该词的文档数；IDF：`log(N/df)`，出现越普遍权重越低 |
| 4 | 平滑 IDF | `ln((N+1)/(df+1)) + 1`：分子分母加 1 防止除零；末尾 +1 让"每篇都出现的词"IDF 为 1 而非 0（scikit-learn 默认） |
| 5 | L2 归一化 | 消除文档长度偏差，所有文档落在单位超球面上，此时余弦相似度 = 点积 |
| 6 | 稀疏 + 可解释 | 词表常有 1 万～10 万维、绝大多数为 0；每一维对应一个词，线性模型的系数可以直接读出"哪些词推动了预测" |
| 7 | scikit-learn 关键参数 | `ngram_range`、`min_df`、`max_df`、`stop_words`、`sublinear_tf`；情感分析不能去掉否定词 |
| 8 | TF-IDF 何时仍然赢 | 垃圾邮件、主题标注、日志异常；数据少；延迟敏感；需要解释——"词是否出现"就是信号的任务 |
| 9 | TF-IDF 的两大失败 | 语义盲（否定、词序、同义词）与推理时的未登录词（OOV） |
| 10 | 混合方案 | 用 TF-IDF 权重对词向量做加权平均池化，兼得语义能力与稀有词强调 |

### 核心技能（能动手做到）

- [ ] 从零实现 `build_vocab`、`bag_of_words`、`document_frequency`、`inverse_document_frequency`、`tfidf`、`l2_normalize`，并验证结果与 `TfidfVectorizer()` 默认输出一致（对齐列顺序后误差 ~1e-16）
- [ ] 给定 N 和 df，手算平滑 IDF 与原始 IDF，并解释两者在"处处出现的词"上的差别
- [ ] 实现一个对任意向量都正确的 `cosine_similarity`，验证"相同文档 = 1.0、词表不相交 = 0.0"
- [ ] 给 `bag_of_words` 加上 n-gram 支持，并验证 `["the","cat","sat"]` 的 bigram 是 `["the cat","cat sat"]`
- [ ] 能针对具体任务写出 `TfidfVectorizer(...)` 的参数配置，并逐个解释每个参数的作用与风险
- [ ] 能实现 TF-IDF 加权的 embedding 池化函数，并说明它为什么比简单平均更好

---

## 二、基础自测（选择题）

**Q1.** 对分好词的文档 `[["cat","sat","on","mat"], ["cat","cat","ran"]]`，用本节的 `build_vocab`（按首次出现顺序编号）+ `bag_of_words`，第 2 篇文档的向量是：

- A. `[1, 0, 0, 0, 1]`
- B. `[2, 0, 0, 0, 1]`
- C. `[0, 0, 0, 2, 1]`
- D. `[2, 1]`

**Q2.** 语料共 N = 3 篇文档，`the` 在 3 篇中都出现。用本节代码的平滑公式 `ln((N+1)/(df+1)) + 1` 和原始公式 `ln(N/df)` 分别计算 `the` 的 IDF，结果是：

- A. 0 和 0
- B. 1 和 0
- C. 1 和 1
- D. `ln(4/3)` 和 0

**Q3.** 计算文档相似度前对 TF-IDF 行向量做 L2 归一化，主要目的是：

- A. 把稀疏矩阵变成稠密矩阵
- B. 去掉所有 0 元素以节省内存
- C. 消除文档长度对相似度的影响，并让余弦相似度退化为点积
- D. 压缩词表大小

**Q4.** 做电影评论情感分类时，下列 `TfidfVectorizer` 参数中**风险最大**的是：

- A. `sublinear_tf=True`
- B. `ngram_range=(1, 2)`
- C. `min_df=2`
- D. `stop_words="english"`

**Q5.** 想在**不手写停用词表**的情况下，近似地去掉"几乎每篇文档都出现"的词，应调整：

- A. `min_df=2`
- B. `max_df=0.95`
- C. `sublinear_tf=True`
- D. `ngram_range=(1, 2)`

**Q6.** 对 "The movie was not good at all." 和 "The movie was excellent." 这对句子，下列哪项改动**最能部分缓解** BoW 的"否定盲区"？

- A. 对行向量做 L2 归一化
- B. 把 IDF 换成平滑版本
- C. 设置 `ngram_range=(1, 2)`，让 "not good" 成为一个独立特征
- D. 设置 `max_df=0.5`

**Q7.** 本节代码的 TF 是 `count / 文档长度`，而 scikit-learn 的 `TfidfVectorizer` 默认直接用原始计数作为 TF。两者在**都做 L2 归一化之后**：

- A. 完全相同，因为同一行所有元素都乘了同一个常数 `1/长度`，归一化时被抵消
- B. 不同，本节代码会让短文档的权重偏大
- C. 不同，scikit-learn 的结果会让长文档的权重偏大
- D. 只有在所有文档等长时才相同

**Q8.** 以下哪个场景，讲义认为在 2026 年 TF-IDF + 线性模型**仍然是首选**？

- A. 中英文机器翻译
- B. 开放域多轮对话
- C. 只有几百条标注数据、要求微秒级响应、并且审计要求解释每次预测的工单分类
- D. 需要理解"这个手机不算便宜但物有所值"这种复杂语义的评论分析

---

## 三、动手 / 代码题

**Q9.** 运行本节 `main.py`，d0 的输出为：

```text
vocab: ['the', 'cat', 'sat', 'on', 'mat', 'dog', 'ran', 'across', 'room']
d0: The cat sat on the mat.
    tfidf: ['0.61', '0.39', '0.39', '0.39', '0.39', '0.00', '0.00', '0.00', '0.00']
cosine similarity matrix:
  d0: ['1.00', '0.80', '0.46']
```

(1) 为什么"最没信息量"的 `the` 反而在 d0 里权重最高？请用数字说明。
(2) 如果把 IDF 换成不带平滑的 `ln(N/df)`，d0 中 `the` 的权重会变成多少？d0 与 d1 的相似度会升高还是降低？为什么？

**Q10.** 本节代码中的余弦相似度是这样写的：

```python
def cosine_similarity(a, b):
    return sum(x * y for x, y in zip(a, b))
```

(1) 这个函数在什么前提下才是"余弦相似度"？如果直接传入 `tfidf(bow)`（未归一化）的结果会怎样？
(2) 写一个对任意向量都正确、遇到零向量不会崩溃的版本，并完成讲义练习 1 的验证：相同文档得 1.0，词表不相交的文档得 0.0。

**Q11.** （讲义练习 2）给 `bag_of_words` 加上 n-gram 支持：写一个 `ngrams(doc, n)` 和 `bag_of_ngrams(docs, n)`，要求 `n=2` 时 `["the", "cat", "sat"]` 产生 `["the cat", "cat sat"]`。并回答：加入 bigram 后词表大小大致会怎样变化？对稀疏性有什么影响？

---

## 四、面试高频题

**Q12.**（基础必考）请完整解释 TF-IDF：每一项的含义、为什么用 log、为什么要平滑、为什么还要 L2 归一化。

**Q13.**（原理深挖）TF-IDF 和 BM25 有什么区别？为什么搜索引擎后来普遍用 BM25？

**Q14.**（工程实践）2026 年了，大家都有 embedding 模型，你什么时候还会选 TF-IDF？什么时候必须换 embedding？有没有折中方案？

**Q15.**（场景设计）你要把 3 万条客服工单分到 12 个类别，工单多为 2～3 句英文，审计要求每次预测可解释。请给出完整方案（表示方法、具体参数、模型、上线前要测什么）。

**Q16.**（追问型）面试官追问："你的 TF-IDF 模型上线后，用户输入里出现了训练时没见过的新词，会发生什么？`fit` 应该在哪些数据上做？词表会不会越来越大？"

---

## 五、参考答案与解析

### Q1 — 答案：B

`build_vocab` 按首次出现顺序编号：`cat→0, sat→1, on→2, mat→3, ran→4`。第 2 篇文档里 `cat` 出现 2 次、`ran` 出现 1 次，所以向量是 `[2, 0, 0, 0, 1]`（与讲义示例一致）。C 是把列顺序搞错了；D 漏掉了"向量长度必须等于词表大小"这一点——**每篇文档的向量长度相同**，这正是 BoW 能喂给分类器的原因。

### Q2 — 答案：B

- 平滑版：`ln((3+1)/(3+1)) + 1 = ln(1) + 1 = 1`；
- 原始版：`ln(3/3) = 0`。

末尾的 +1 就是为了"每篇都出现的词 IDF 仍为 1 而不是 0"，与 scikit-learn 的默认 `smooth_idf=True` 一致。原始版会把这类词的权重直接清零。两种都能用，讲义的评价是"the smoothed version is friendlier"——但 Q9 会展示它的副作用。

### Q3 — 答案：C

不归一化时，长文档的向量模长更大，在点积类相似度中会"压过"短文档。L2 归一化后所有文档向量模长为 1，`cos(a,b) = a·b / (|a||b|) = a·b`。A 错：归一化不改变稀疏性（0 除以任何数仍是 0）；B、D 与归一化无关。

### Q4 — 答案：D

scikit-learn 的英文停用词表包含 `not` 等否定词。实测：对 "The movie was not good at all." 和 "The movie was excellent." 用 `TfidfVectorizer(stop_words="english")` 拟合，词表只剩 `['excellent', 'good', 'movie']`——`not` 被删了，负面评论只剩一个 `good`，极性彻底反转。讲义原话："sentiment analysis should *not* drop negations"。A、B、C 在情感任务中通常无害甚至有益。

### Q5 — 答案：B

`max_df=0.95` 会丢弃出现在 95% 以上文档中的词，这类词基本就是语料自己的"停用词"，讲义称之为 "Approximates stopword removal without a hardcoded list"。它比固定停用词表更"数据驱动"：在某个特定领域里，"product" 这类词可能处处出现，标准停用词表却不会收录。A 是去掉**过于稀有**的词，方向相反。

### Q6 — 答案：C

BoW 丢弃词序，`not` 和 `good` 各是一个独立特征，模型很难知道 `not` 修饰的是 `good`。加入 bigram 后 `not good` 成为一个单独的维度，线性模型可以直接给它一个负权重。但这只是**部分**缓解：`not very good`、`not at all good` 等距离更远的否定依然抓不到——讲义的结论是 BoW "can learn this on enough data, but never as gracefully as a model that understands syntax"。A、B、D 都不改变"词序被丢弃"这一事实。

### Q7 — 答案：A

同一篇文档内，本节代码的每个 TF 都是原始计数乘以 `1/length`。L2 归一化会把整行除以模长，而 `1/length` 这个公共因子在分子分母中同时出现，被完全抵消。实测：本节代码 `l2_normalize(tfidf(bow))` 与 `TfidfVectorizer().fit_transform(raw)`（按列名对齐后）最大误差约 `1.1e-16`，即浮点舍入级别。这说明在 L2 归一化之后，"TF 要不要除以文档长度"是无关紧要的。

### Q8 — 答案：C

讲义列出的 TF-IDF 优势场景：词出现与否即信号（垃圾邮件、主题、日志）；低数据量（数百条标注，无预训练成本）；延迟敏感（TF-IDF + 线性模型微秒级，Transformer 编码一篇文档 10–100ms）；需要解释（直接看系数）。C 同时命中后三条。A、B 是生成任务；D 依赖复杂语义理解，正是 TF-IDF 的"语义盲"短板。

### Q9 — 参考答案

**(1)** d0 分词后为 `the cat sat on the mat`，共 6 个 token：
- `the`：TF = 2/6 ≈ 0.333，IDF = `ln(4/4) + 1 = 1`，TF-IDF ≈ 0.333；
- `cat / sat / on / mat`：TF = 1/6 ≈ 0.167，IDF = `ln(4/3) + 1 ≈ 1.288`，TF-IDF ≈ 0.215。

`the` 的 IDF 只比其他词低约 22%，但 TF 是它们的 2 倍，于是胜出。L2 归一化后：模长 `√(0.333² + 4×0.215²) ≈ 0.544`，`the ≈ 0.333/0.544 ≈ 0.61`，其他 ≈ `0.215/0.544 ≈ 0.39`，与输出一致。

教训：平滑 IDF 的 "+1" 让高频虚词保留了权重。在小语料上，`the` 甚至成了相似度的主要贡献者——d0 与 d1 的 0.80 中有相当一部分来自共享的 `the`。

**(2)** 原始 IDF 下 `the` 的 IDF = `ln(3/3) = 0`，权重直接变成 **0.00**。实测：d0 的向量变为 `['0.00', '0.50', '0.50', '0.50', '0.50', '0.00', ...]`，相似度矩阵变为：

```
d0-d1: 0.47   d0-d2: 0.10   d1-d2: 0.00
```

d0 与 d1 的相似度从 0.80 **降到** 0.47，因为不再有共享的 `the` 撑场面，只剩 `sat / on / mat` 三个真正的共享内容词。d1 与 d2 除了 `the` 没有任何共同词，相似度降为 0。另一个参考：用 `TfidfVectorizer(stop_words="english")`（同时去掉了 `the / on / across`）时，d0-d1 = 0.60、d0-d2 = 0.27、d1-d2 = 0.00。

### Q10 — 参考答案

**(1)** 只有当 `a`、`b` 都已经 **L2 归一化**（模长为 1）时，点积才等于余弦相似度。本节 `main()` 先调用了 `l2_normalize`，所以没问题；但函数名会误导调用者。如果直接传 `tfidf(bow)` 的结果，得到的只是原始点积：实测（语料即下面 (2) 中的三篇）两篇完全相同的文档 `"the cat sat"` 得分约 0.553，而不是 1.0。

**(2)**

```python
import math

def cosine_similarity_safe(a, b):
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:          # 空文档 / 全 OOV 文档没有方向
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)

raw = ["the cat sat", "the cat sat", "dog ran fast"]
docs = [tokenize(r) for r in raw]
vocab = build_vocab(docs)
t = tfidf(bag_of_words(docs, vocab))      # 不归一化也能正确工作
print(cosine_similarity_safe(t[0], t[1]))  # 1.0000000000000002
print(cosine_similarity_safe(t[0], t[2]))  # 0.0
```

注意相同文档得到的是 `1.0000000000000002` 而不是精确的 1.0——浮点误差。测试里要写 `math.isclose(score, 1.0)` 而不是 `== 1.0`。

### Q11 — 参考答案

```python
def ngrams(doc, n):
    return [" ".join(doc[i:i + n]) for i in range(len(doc) - n + 1)]

def bag_of_ngrams(docs, n=1):
    grams = [ngrams(d, n) for d in docs]
    vocab = build_vocab(grams)          # 直接复用：n-gram 字符串就是新的"词"
    return vocab, bag_of_words(grams, vocab)

print(ngrams(["the", "cat", "sat"], 2))
# ['the cat', 'cat sat']
print(bag_of_ngrams([["the", "cat", "sat"], ["the", "cat", "ran"]], 2))
# ({'the cat': 0, 'cat sat': 1, 'cat ran': 2}, [[1, 1, 0], [1, 0, 1]])
```

要点：
- 长度为 L 的文档有 `L - n + 1` 个 n-gram；文档比 n 短时 `range` 为空，自然返回空列表。
- 把 n-gram 拼成字符串后，`build_vocab` / `bag_of_words` 无需任何修改即可复用——这就是"表示与计数解耦"的好处。若要像 `ngram_range=(1, 2)` 那样同时包含一元和二元，把两个列表拼起来即可。
- 词表规模：不同 bigram 的数量通常远多于不同单词数（理论上限是词表大小的平方，实际受语料限制），因此维度暴涨、矩阵更稀疏，大多数 bigram 只出现一两次——这正是生产中 `ngram_range=(1, 2)` 常与 `min_df` 搭配使用的原因。

### Q12 — 参考回答要点

- **定义**：`TF-IDF(w, d) = TF(w, d) × IDF(w)`。TF 衡量"词在这篇文档里有多重要"；IDF = `log(N / df(w))` 衡量"这个词在整个语料中有多稀有"。
- **为什么用 log**：`N/df` 的取值跨度很大（从 1 到 N），不取对数时稀有词的权重会大到压倒一切；log 把它压缩到温和的范围，让 IDF 成为"调节因子"而非"决定因子"。
- **为什么平滑**：`(N+1)/(df+1)` 防止 df = 0（例如对新文档做 transform 时）导致除零；末尾 `+1` 让处处出现的词权重为 1 而非 0（scikit-learn 默认 `smooth_idf=True`）。
- **为什么 L2 归一化**：消除文档长度偏差；归一化后余弦相似度 = 点积，计算和检索都更方便。`TfidfVectorizer` 默认 `norm="l2"`。
- **加分点**：指出 L2 归一化后"TF 是否除以文档长度"不影响结果（Q7）；提到 `sublinear_tf=True` 用 `1 + log(tf)` 抑制同一个词在单篇文档中的大量重复。
- **常见误区**：以为 IDF 可以在全量数据（含测试集）上计算——这会造成信息泄露，`fit` 只能在训练集上做。

### Q13 — 参考回答要点

- **相同点**：都是"词频 × 逆文档频率"思路的稀疏词匹配打分，都可以解释、都很快。
- **BM25 的两个关键改进**：
  1. **词频饱和**：TF-IDF 中词频线性增长（或 `sublinear_tf` 的对数增长）；BM25 用参数 `k1` 控制的饱和函数，一个词出现 10 次和 20 次的得分差距很小，更符合"相关性不随重复无限增长"的直觉。
  2. **文档长度归一化**：BM25 用参数 `b` 把文档长度与语料平均长度比较，长文档天然包含更多词，需要被适度惩罚；L2 归一化则是对整个向量做几何归一。
- **用途差异**：TF-IDF + 余弦更常用于"文档向量化后做分类 / 聚类 / 相似度"；BM25 是"查询-文档"打分函数，专为检索排序设计，至今仍是混合检索中稀疏一路的标准基线。
- **加分点**：能写出 BM25 中饱和项的形式 `tf·(k1+1) / (tf + k1·(1 - b + b·|d|/avgdl))`，并说明 `k1` 常取 1.2～2.0、`b` 常取 0.75 左右。详见 [阶段 05 · 14 信息检索与搜索](../../14-information-retrieval-search/docs/zh.md)。

### Q14 — 参考回答要点

- **选 TF-IDF**（讲义列出的场景）：
  - 任务的信号就是"某些词是否出现"：垃圾邮件、主题标注、日志异常；
  - 标注数据只有几百条，没有预训练成本；
  - 延迟要求在微秒级（Transformer 编码一篇文档要 10–100ms）；
  - 需要解释：直接读线性模型系数，Top 正权重词就是原因。
- **必须换 embedding**：
  - 语义盲导致的错误成为主要错误来源（否定、同义改写、"物有所值"这类需要理解的表达）；
  - 推理时大量 OOV 词（新品牌名、网络用语）——subword embedding 能处理，TF-IDF 不能；
  - 跨语言、短文本语义匹配等任务。
- **折中方案**：TF-IDF 加权 embedding 池化——每个 token 的词向量按其 TF-IDF 分数加权平均，得到文档向量再训练分类器。讲义认为在标注量低于约 5 万条的情感 / 主题 / 意图分类中，它优于单独使用任何一方。
- **加分点**：强调先跑 TF-IDF 基线，用错误分析**证明**存在语义失败后再升级——讲义 Ship It 中明确要求"under 500 labeled examples"时没有证据就不推荐 embedding。

### Q15 — 参考回答要点

- **表示**：TF-IDF。3 万条不算小，而"审计需要解释"直接排除了稠密 embedding。
- **配置**（与讲义 Ship It 示例一致）：

```python
TfidfVectorizer(ngram_range=(1, 2), min_df=3, max_df=0.95,
                sublinear_tf=True, stop_words=None)
```

  - `ngram_range=(1, 2)`：捕获 "not working"、"refund request" 这类短语；
  - `min_df=3`：去掉只出现一两次的噪声词，控制词表；
  - `max_df=0.95`：数据驱动地去掉处处出现的词；
  - `sublinear_tf=True`：抑制同一工单里某个词的大量重复；
  - `stop_words=None`：保留停用词，因为 "not working" vs "working" 的区别就在停用词上。
- **模型**：逻辑回归（或线性 SVM）；每次预测输出 Top-k 贡献词（特征值 × 系数）写入审计日志。
- **上线前要测**：
  1. `min_df=3` 是否误删了某些小类别的关键词——按类别过滤 `get_feature_names_out()` 人工检查；
  2. 类别不平衡——讲义提醒"这需要的不只是换一个 vectorizer"，要看每类的 precision/recall，必要时用 `class_weight`、重采样；
  3. 训练/推理使用同一个已 `fit` 的 vectorizer 对象（序列化后与模型一起发布）。

### Q16 — 参考回答要点

- **新词会被静默丢弃**：本节代码 `bag_of_words` 中 `if token in vocab` 会跳过未登录词；scikit-learn 的 `transform` 同样忽略词表外的词。极端情况下整篇文档全是新词，得到全零向量，模型只能输出"截距"对应的默认类别。讲义举例：在 IMDb 上训练的模型不认识 `Zoomer-approved`。
- **`fit` 只在训练集上做**：词表和 IDF 都是从数据里"学"出来的统计量，在含测试集的全量数据上 `fit` 属于数据泄露；线上只能 `transform`。
- **词表不会自动增长**：`fit` 后词表固定。要吸收新词，需要定期在新数据上重新 `fit` + 重新训练模型，并把新旧版本的 vectorizer 与模型**绑定发布**。
- **工程手段**：
  - 监控线上 OOV 率与全零向量比例，作为"该重训了"的信号；
  - `HashingVectorizer` 用哈希把任意词映射到固定维度，不存词表、天然支持新词，代价是哈希冲突且无法从维度反查词（损失可解释性）；
  - OOV 严重的场景改用 subword / 字符 n-gram 或 subword embedding（下一节 FastText）。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 01 文本处理](../../01-text-processing/docs/zh.md)：tokenization、小写化、stemming 决定了词表长什么样。
- [阶段 02 · 02 线性回归](../../../02-ml-fundamentals/02-linear-regression/docs/zh.md)：本节官方前置课；TF-IDF 特征最常接的就是线性模型。
- [阶段 01 · 14 范数与距离](../../../01-math-foundations/14-norms-and-distances/docs/zh.md)：L2 范数与余弦相似度。

### 本节被哪些后续内容用到
- [阶段 05 · 03 词 Embeddings——从零实现 Word2Vec](../../03-word-embeddings-word2vec/docs/zh.md)：从稀疏计数向量走向稠密语义向量。
- [阶段 05 · 04 GloVe、FastText 和 Subword Embeddings](../../04-glove-fasttext-subword/docs/zh.md)：解决本节的 OOV 问题；GloVe 本身也基于共现计数。
- [阶段 05 · 05 情绪分析](../../05-sentiment-analysis/docs/zh.md)：TF-IDF + 逻辑回归是情感分类的经典基线，也会遇到否定处理问题。
- [阶段 05 · 14 信息检索与搜索](../../14-information-retrieval-search/docs/zh.md)：BM25 与混合检索。
- [阶段 05 · 15 主题建模](../../15-topic-modeling/docs/zh.md)：LDA 的输入正是词袋计数矩阵。
- [阶段 02 · 14 朴素贝叶斯](../../../02-ml-fundamentals/14-naive-bayes/docs/zh.md)：基于词计数的另一种经典文本分类器。
- [阶段 11 · 07 高级 RAG](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：稀疏 + 稠密混合检索在 RAG 中的应用。

### 延伸关键词
`BM25` · `HashingVectorizer` · `sublinear_tf` · `character n-gram` · `稀疏矩阵 CSR` · `卡方特征选择` · `SPLADE（学习型稀疏表示）` · `hybrid retrieval`
