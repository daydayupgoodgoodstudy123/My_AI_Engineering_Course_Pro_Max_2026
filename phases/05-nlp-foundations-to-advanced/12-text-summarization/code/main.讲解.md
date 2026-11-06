# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到进阶 · 第 12 节 文本摘要 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅 Python 标准库（`math`、`re`、`collections.Counter`）；讲义中的 `transformers`（BART）与 `rouge-score` 示例不在本文件里

---

## 1. 这份代码在考察什么

本文件实现了讲义 Build It 的 Step 1（TextRank 抽取式摘要），并附带一个极简的 ROUGE-N，在一篇 7 句的"论文新闻"上跑通"摘要 → 评估"的完整闭环：

1. **句子切分**：用正则的后行断言（lookbehind）在句末标点后切分。
2. **句子相似度**：原始 TextRank 的"共有词数 / 对数长度"归一化。
3. **TextRank = 句子图上的加权 PageRank**：阻尼 0.85、迭代直到收敛，得分高的句子就是"与全文联系最紧密"的句子。
4. **按原文顺序输出 top-k**：先按得分选句，再按位置排序，保证摘要可读。
5. **ROUGE-N 召回率**：系统摘要与参考摘要的 n-gram 重叠占参考的比例，并提醒生产中要用 `rouge-score` 的 F 值和词干化。

> 一句话：**不用任何模型，30 行代码就能做出一个"不会编造内容"的摘要器**，并亲手看到 ROUGE 这个指标有多依赖分词细节。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sentence_split(text)` | 函数 | 按 `.!?` 后的空白切句，去掉空串 | 句子切分 |
| `similarity(s1, s2)` | 函数 | 共有词数 / (log(\|S₁\|+1) + log(\|S₂\|+1)) | TextRank 边权 |
| `textrank(text, top_k, damping, iterations, epsilon)` | 函数 | 建相似度矩阵 → PageRank 迭代 → 选 top-k 并按原序输出 | 抽取式摘要 |
| `rouge_n(hyp, ref, n)` | 函数 | n-gram 重叠 / 参考 n-gram 总数 | ROUGE-N 召回率 |
| `main()` | 函数 | 对示例文章做 3 句摘要，并与参考摘要算 ROUGE-1/2 | 演示入口 |

数据流：`article → sentence_split → similarity（两两）→ PageRank 迭代 → top-3 句子`；拼接后与 `reference` 一起送入 `rouge_n(n=1)` 与 `rouge_n(n=2)`。

---

## 3. 逐段精讲

### 3.1 句子切分：正则后行断言

```python
def sentence_split(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
```

- `(?<=[.!?])` 是**后行断言**：要求"前面紧挨着一个 `.`、`!` 或 `?`"，但这个标点本身**不被消耗**，所以切分后句号仍留在句子末尾。
- `\s+`：真正被切掉的是标点后面的一个或多个空白。
- 列表推导里的 `if s.strip()` 过滤空字符串（比如文本以多余空格结尾时），讲义版没有这一步，代码版更稳健。
- ⚠️ 简化：遇到缩写（`Dr. Smith`、`U.S. market`）、小数（`3.5 million`）后面跟空格的情况会错误切分；生产中用 spaCy、NLTK punkt 等句子切分器。

### 3.2 句子相似度：原始 TextRank 公式

```python
def similarity(s1, s2):
    w1 = Counter(s1.lower().split())
    w2 = Counter(s2.lower().split())
    intersection = sum((w1 & w2).values())
    denom = math.log(len(w1) + 1) + math.log(len(w2) + 1)
    if denom == 0:
        return 0.0
    return intersection / denom
```

- Mihalcea & Tarau 的原始公式是 `|共有词| / (log|S₁| + log|S₂|)`。用 log 而不是直接除以长度，是为了**不过分惩罚长句**——长句共有词多是正常的，但不应线性放大。
- `w1 & w2`：`Counter` 交集取每个词两边计数的最小值，`sum(...values())` 得到（考虑重复的）共有词数。
- `len(w1)` 是**不同词**的个数（Counter 的键数）；`+1` 让单词句的 `log(1) = 0` 不至于让分母为 0。
- `denom == 0` 实际上只有两个句子都为空时才会发生，是防御性检查。
- ⚠️ 两个影响结果的简化：
  1. **没有去停用词**：`the`、`a`、`at`、`on` 也算共有词。本例中第 7 句"The paper has been accepted at NeurIPS."与第 1、2 句的相似度高达 0.45、0.43，很大程度来自 `the`、`paper`、`at` 这类词。
  2. **没有去标点**：`.split()` 后 `transformers.` 与 `transformers` 是不同的词。
- 讲义提到：TF-IDF 向量的余弦相似度也可以（这就是 LexRank 的思路）。

### 3.3 建图：n×n 相似度矩阵

```python
def textrank(text, top_k=3, damping=0.85, iterations=50, epsilon=1e-4):
    sentences = sentence_split(text)
    n = len(sentences)
    if n <= top_k:
        return sentences

    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                sim[i][j] = similarity(sentences[i], sentences[j])
```

- `if n <= top_k: return sentences`：句子不比要求的多，直接全返回——提前返回的边界处理。
- `sim` 是**对称**矩阵（`similarity` 对两个参数对称），对角线为 0（不自己连自己）。
- 复杂度：`O(n²)` 次相似度计算。本例 7 句无所谓；上千句的长文档要先分块或只保留每个句子 top-k 个邻居（稀疏图）。
- 本例实测的相似度矩阵（保留两位小数）中，第 6 句"Several research labs…"与第 1 句的相似度为 0——两句没有任何共同词。

### 3.4 PageRank 迭代

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
```

- 公式：`score_j ← (1-d) + d · Σ_i (sim_ij / Σ_k sim_ik) · score_i`。
  - 直觉：句子 i 把自己的"重要性"按边权比例**分给**邻居；被很多重要句子"投票"的句子更重要。
  - `(1-d) = 0.15` 是每个句子的基础分，对应 PageRank 随机游走中的"随机跳转"，保证收敛到唯一解。
- **得分总和恒为 n**：每个句子分出去的比例之和为 1，所以 `Σ new = (1-d)·n + d·Σ old`，从全 1 开始每轮都保持 n。本例收敛后得分为 `[0.862, 1.153, 1.048, 1.167, 1.083, 0.666, 1.021]`，总和 7.0——大于 1 就是"比平均更中心"。
- `sum(sim[i]) or 1e-9`：如果句子 i 与所有句子都不相似，`sum` 为 0，`or` 把它换成极小正数防止除零。此时由于 `if sim[i][j] > 0`，该句既不分出也收不到分数，得分固定为 0.15，总和会略小于 n（PageRank 的"悬挂节点"问题）。
- **收敛判断**：`max(abs(s - ns) ...)` 是新旧得分的最大变化（无穷范数），小于 `epsilon=1e-4` 就提前退出；否则最多迭代 50 轮。本例实测 8 轮收敛。
- 讲义："The damping factor 0.85 and iteration count are the PageRank defaults."
- ⚠️ 实现细节：`new_scores` 是新列表，整轮计算都用旧的 `scores`——这是 **Jacobi 式**同步更新；如果原地更新就成了 Gauss-Seidel 式，收敛路径会不同。

### 3.5 选句：两次排序

```python
    ranked = sorted(range(n), key=lambda k: scores[k], reverse=True)[:top_k]
    ranked.sort()
    return [sentences[i] for i in ranked]
```

- 第一次：对下标按得分**降序**排序，切片取前 `top_k` 个——决定"选哪几句"。
- 第二次：`ranked.sort()` 对选中的下标**升序**排序——决定"按原文顺序输出"，保证摘要叙事连贯。
- `sorted(...)` 返回新列表，`list.sort()` 原地排序；`key=lambda k: scores[k]` 让排序依据是得分而不是下标本身。
- 本例中得分前三是第 4 句（1.167）、第 2 句（1.153）、第 5 句（1.083），输出顺序却是 2 → 4 → 5。
- 注意 lambda 参数名 `k` 与外层的 `top_k` 无关，只是一个局部变量名。

### 3.6 ROUGE-N：召回率版本

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

- 分母是**参考**的 n-gram 总数 → 这是 ROUGE-N **召回率**，也是 ROUGE 名字里 "Recall-Oriented" 的由来。与第 11 节 BLEU（分母是候选，精确率）正好相对。
- `Counter(... for ...)` 直接用生成器表达式构造计数器；n-gram 用元组作键。
- `hyp_ngrams & ref_ngrams`：截断重叠，与 BLEU 的 clipping 相同。
- ⚠️ 与 `rouge-score` 的差异：
  1. 只返回召回率，没有精确率和 F 值——只看召回会奖励长摘要（测验 Q9：把整篇文章当摘要，召回 0.571 反而高于 TextRank 的 0.381）；
  2. 没有去标点：参考里的 `variant,`、`weights.` 与摘要中的 `variant`、`weights` 匹配不上；
  3. 没有词干化：讲义 "Always use stemming"；
  4. 没有 ROUGE-L（测验 Q10 给出了 LCS 实现）。
- `main()` 最后一行打印的正是这条提醒："For production, use the `rouge-score` package with stemming for a proper F-measure."

### 3.7 `main()`：文章与参考摘要

```python
    summary = textrank(article, top_k=3)
    joined = " ".join(summary)
    # ...
    for n in [1, 2]:
        score = rouge_n(joined, reference, n=n)
        print(f"  ROUGE-{n}: {score:.3f}")
```

- 文章由 7 句用括号内相邻字符串字面量拼接而成（Python 会自动连接相邻的字符串）。
- 参考摘要是一句人工写的概括，用了 `linear-time`、`1B` 这类与原文措辞不同的表达——这本身就会压低 ROUGE。
- `" ".join(summary)` 把 3 句拼成一段再评估。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 抽取式 TextRank 而非生成模型 | 无需 GPU/模型下载，输出原样来自原文，不会编造 | 可能漏掉分散信息、句子脱离上下文；生产可用 `sumy` 或混合方案 |
| 原始 TextRank 相似度（log 归一化词重叠） | 忠实于论文、实现简单 | 不去停用词/标点时噪声大；可换 TF-IDF 余弦（LexRank）或句向量 |
| 稠密 n×n 相似度矩阵 | 7 句的玩具数据足够 | `O(n²)`；长文档用稀疏图或先分块 |
| 同步更新 + ε 提前停止 | 标准 PageRank 做法，结果确定 | 无明显代价 |
| 选句后按原文顺序输出 | 摘要更连贯 | 无 |
| 正则切句 | 零依赖 | 缩写、小数会切错；生产用专门的句子切分器 |
| ROUGE 只算召回、无词干化 | 代码最短，突出"召回导向" | 数值与 `rouge-score` 不可比；生产报告 P/R/F 并开启 `use_stemmer=True` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `re.split` + 后行断言 | `re.split(r"(?<=[.!?])\s+", text.strip())` | 按正则切分；`(?<=...)` 只检查前文、不消耗字符，所以标点保留在句尾 |
| 原始字符串 `r"..."` | `r"(?<=[.!?])\s+"` | 反斜杠不转义，写正则的标准做法 |
| 带过滤的列表推导 | `[s.strip() for s in ... if s.strip()]` | 先过滤空串再处理 |
| `collections.Counter` 与 `&` | `w1 & w2` | 计数交集，取两边最小计数 |
| `math.log` | `math.log(len(w1) + 1)` | 自然对数，参数必须 > 0 |
| 提前返回 | `if n <= top_k: return sentences` | 处理边界情况 |
| 二维列表 | `[[0.0] * n for _ in range(n)]` | 每行独立；不要写成 `[[0.0] * n] * n` |
| `or` 的短路返回值 | `sum(sim[i]) or 1e-9` | 左边为假（0）时返回右边，常用于提供默认值 |
| 生成器表达式 + `max` | `max(abs(s - ns) for s, ns in zip(scores, new_scores))` | 求最大变化量 |
| `for ... break` | 收敛后 `break` | 提前结束循环 |
| `sorted` + `key` + `reverse` + 切片 | `sorted(range(n), key=lambda k: scores[k], reverse=True)[:top_k]` | 按得分降序取前 k 个下标 |
| `list.sort()` | `ranked.sort()` | 原地升序排序，返回 `None` |
| 嵌套函数 | `rouge_n` 内的 `ngrams` | 只在外层函数内使用的辅助函数 |
| `Counter` + 生成器 | `Counter(tuple(tokens[i:i + k]) for i in ...)` | 直接对生成器计数 |
| 相邻字符串字面量拼接 | `article = ("Researchers ... " "The paper ...")` | 括号内的多个字符串自动连接成一个 |
| `str.join` | `" ".join(summary)` | 用空格把句子列表拼成一段 |
| f-string 格式 | `{score:.3f}`、`f"  - {s}"` | 保留 3 位小数；嵌入变量 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，仅标准库）的完整输出：

```text
=== TextRank summary ===
  - The paper introduces a new attention variant that runs in linear time.
  - Benchmarks show the new attention matches standard attention on most tasks.
  - The authors released training code and weights on GitHub.

=== ROUGE against reference ===
  ROUGE-1: 0.381
  ROUGE-2: 0.150

For production, use the `rouge-score` package with stemming for a proper F-measure.
```

逐行解读：

- **选出的 3 句**是原文第 2、4、5 句：新注意力变体、基准结果、开源代码——正好对应参考摘要中的"linear-time attention variant""matched standard attention on benchmarks""released code and weights"。TextRank 选中了它们，是因为这几句与其他句子共享 `attention`、`new`、`the`、`authors` 等词最多。
- **漏掉的**是第 3 句"trained models up to 1 billion parameters"（得分 1.048，第 4 名，仅略低于第 5 句的 1.083），而参考摘要恰好提到了"trained up to 1B parameters"。这展示了抽取式的主要风险：重要信息不一定"中心"。
- 实测 PageRank 8 轮收敛，各句得分 `[0.862, 1.153, 1.048, 1.167, 1.083, 0.666, 1.021]`，总和 7.0；与其他句子都不太相似的第 6 句（实验被复现）得分最低。
- **ROUGE-1 = 0.381**：参考摘要 21 个 token 中有 8 个能在摘要中找到（`a、and、attention×2、code、on、released、standard`），8/21 ≈ 0.381。
- **ROUGE-2 = 0.150**：参考的 20 个 bigram 中命中 3 个（`standard attention`、`attention on`、`code and`），3/20 = 0.15。
- 这两个数偏低，很大一部分原因是分词：`variant,`、`benchmarks,`、`weights.` 带着标点匹配不上，`linear-time` 是一个 token。把标点替换为空格后，ROUGE-1 召回升到 0.591（测验 Q9）。作为对照，取前三句的 Lead-3 基线 ROUGE-1 为 0.333、ROUGE-2 为 0.050，本例中 TextRank 略好。

---

## 7. 动手改一改

1. **去停用词和标点**：在 `similarity` 中先用 `re.sub(r"[^\w\s]", " ", s)` 去标点，再过滤一个小停用词表（`the, a, at, on, of, to, and…`），看选句是否变化（实测：第 4 句会被第 3 句"trained models up to 1 billion parameters"替换）。
2. **ROUGE 三件套**：给 `rouge_n` 增加精确率和 F1，再实现基于 LCS 的 `rouge_l`（参考测验 Q10），报告 P/R/F。
3. **Lead-3 基线**：实现"取前 3 句"的基线，与 TextRank 比较 ROUGE；在新闻语料上 Lead-3 往往是很难超越的基线。
4. **LexRank 风格相似度**：把 `similarity` 换成 TF-IDF 向量的余弦相似度（复用第 02 节的代码），比较选句结果。
5. **去冗余（MMR）**：选句时惩罚与已选句子过于相似的候选，避免摘要中出现意思重复的两句。
6. **进阶**：实现讲义练习 2 的"实体级事实性"——用简单规则（首字母大写词、数字）近似实体，计算摘要实体对原文的精确率与召回率。

---

## 8. 常见坑

- **只看召回**：ROUGE 召回会奖励长摘要，必须同时看精确率/F 值或限制长度。
- **分词不统一**：标点、大小写、词干化的差异会让 ROUGE 相差十几个百分点；不同系统对比时要用同一个评测包和同样的参数。
- **停用词主导相似度**：不去停用词时，`the`、`at` 之类的词会在句子图上制造虚假的强连接。
- **句子切分出错**：缩写、小数、引号会让正则切句失败，进而影响整个图。
- **以为抽取式"绝对安全"**：句子脱离上下文（代词、时间状语）、信息过时、顺序打乱仍可能误导读者（讲义 Step 4）。
- **`[[0.0] * n] * n` 浅拷贝**：二维矩阵必须用列表推导创建，否则所有行共享同一个列表。
