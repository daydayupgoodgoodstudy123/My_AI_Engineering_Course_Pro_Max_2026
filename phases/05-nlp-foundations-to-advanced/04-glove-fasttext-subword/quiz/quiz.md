# 测验 · GloVe、FastText 和 Subword Embeddings（GloVe, FastText, and Subword Embeddings）

> **阶段 05 · NLP 基础到高级 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | GloVe 的目标 | 先建全局共现矩阵 X，再训练向量使 `vᵢ·ṽⱼ + bᵢ + b̃ⱼ ≈ log Xᵢⱼ`——用"矩阵分解"代替 Word2Vec 的在线预测 |
| 2 | GloVe 的加权函数 | `f(x) = (x/x_max)^α`（x < x_max），否则为 1；常用 x_max = 100、α = 0.75：罕见共现被降权，高频共现的权重被封顶为 1 |
| 3 | GloVe 的实现细节 | 共现计数按距离加权 `1/distance`；最终向量取 `W + W̃`（两张表相加通常比只用一张好） |
| 4 | FastText 的表示 | 词 = 其字符 n-gram（通常 3–6）的向量之和 + 整词本身；用 `<`、`>` 标记词边界 |
| 5 | FastText 解决 OOV | 未见过的词只要有已知的 n-gram 就能组合出向量；`where` 与 `whereupon` 共享 10 个 n-gram |
| 6 | BPE 训练 | 从字符（或字节）出发，反复统计相邻对频次、合并最频繁的一对，得到一个**有序**的合并表 |
| 7 | BPE 编码 | 按学习顺序依次应用合并规则；合并顺序决定切分结果（本节中 `lowest → ['lo', 'west</w>']`） |
| 8 | 字节级 BPE | 基础词表是 256 个字节，任何输入都能被编码，永远没有 OOV（GPT-2 的方案） |
| 9 | 子词 tokenizer 家族 | BPE（GPT 系）、WordPiece（BERT）、SentencePiece（T5、LLaMA）——现代 LLM 的 tokenizer 都是子词级 |
| 10 | 选型与头号坑 | 通用词向量选 GloVe，需要处理拼写错误/新词/形态丰富语言选 FastText；进 Transformer 的文本**只能**用模型自带的 tokenizer |

### 核心技能（能动手做到）

- [ ] 能手写 `char_ngrams(word, 3, 6)`，并准确数出 `where` 的 n-gram 个数（15 个）
- [ ] 能计算两个词 n-gram 集合的 Jaccard 重叠，并解释它和 FastText 跨形态迁移的关系
- [ ] 能从零实现 `learn_bpe` 与 `apply_bpe`，手算第一次合并选中的相邻对
- [ ] 能**不运行代码**，根据合并表预测一个新词的 BPE 切分，并解释"合并顺序"对结果的影响
- [ ] 能写出 GloVe 的加权最小二乘损失与加权函数，算出 `f(1)`、`f(10)`、`f(100)`
- [ ] 能根据任务（通用词向量 / 新词多 / 微调 LLM / 从零训练 LM）选出合适的方案，并说出"tokenizer 与模型必须配套"的原因

---

## 二、基础自测（选择题）

**Q1.** GloVe 训练时拟合的目标是：

- A. 用中心词经 softmax 预测上下文词
- B. `vᵢ·ṽⱼ + bᵢ + b̃ⱼ ≈ log Xᵢⱼ`，其中 Xᵢⱼ 是全局共现计数
- C. 对 PMI 矩阵做截断 SVD
- D. 把字符 n-gram 向量相加后预测上下文

**Q2.** GloVe 加权函数 `f(x) = (x/x_max)^α (x < x_max)，否则 1`，取 x_max = 100、α = 0.75。下列描述**最准确**的是：

- A. f 单调递减：共现越多权重越小，从而压制 `(the, and)` 这类高频对
- B. f 单调不减、在 x_max 处封顶为 1：只共现 1 次的对权重约 0.03（噪声大、被降权），而极高频的对权重不会超过 1，不会随次数无限增长
- C. f 对所有词对给出相同权重，只是数值缩放
- D. f 用来选择负样本

**Q3.** 本节 `char_ngrams("where")`（n_min=3, n_max=6）返回的集合共有多少个元素？

- A. 5
- B. 13
- C. 14
- D. 15

**Q4.** FastText 能为训练时没见过的 `whereupon` 生成向量，是因为：

- A. 它在推理时会在线微调一次
- B. 它把词向量定义为字符 n-gram 向量之和，`whereupon` 的许多 n-gram（如 `<wh`、`her`、`<where`）在训练中见过
- C. 它把所有未知词映射到同一个 `<unk>` 向量
- D. 它在词表中存了所有可能的英文单词

**Q5.** 对本节 `main.py` 的语料 `{"low": 5, "lower": 2, "newest": 6, "widest": 3, "lowest": 4, "newer": 2}`，`learn_bpe` 第一次合并选中的相邻对是：

- A. `('l', 'o')`
- B. `('e', 's')`
- C. `('w', 'e')`
- D. `('s', 't')`

**Q6.** GPT-2 使用字节级 BPE，最主要的好处是：

- A. 字节比字符训练更快
- B. 基础词表是 256 个字节，任何 UTF-8 文本都能被编码，从根本上消除了 OOV
- C. 字节级 BPE 不需要学习合并规则
- D. 字节能自动保留大小写信息

**Q7.** 你要微调一个开源 LLaMA 模型，同事建议"用我们领域语料重新训练一个 BPE tokenizer 替换原来的，效果会更好"。正确的回应是：

- A. 同意，领域 tokenizer 一定更好
- B. 同意，只要新词表大小与原来相同即可
- C. 不同意：模型的 embedding 矩阵与原 tokenizer 的 token ID 一一绑定，换 tokenizer 会让每个 ID 指向错误的向量；微调预训练模型时应使用它自带的 tokenizer
- D. 不同意，因为 BPE 不能用于领域语料

**Q8.** 下列"模型 → tokenizer 类型"的对应，哪一组与讲义一致？

- A. BERT → WordPiece；T5、LLaMA → SentencePiece；GPT-2 → 字节级 BPE
- B. BERT → 字节级 BPE；T5 → WordPiece；GPT-2 → SentencePiece
- C. 三者都用词级 tokenizer
- D. BERT → FastText；GPT-2 → GloVe

---

## 三、动手 / 代码题

**Q9.** 本节 `main.py` 在上述语料上学到的 10 条合并规则（按顺序）是：

```text
  'w' + 'e' -> 'we'
  's' + 't' -> 'st'
  'st' + '</w>' -> 'st</w>'
  'l' + 'o' -> 'lo'
  'we' + 'st</w>' -> 'west</w>'
  'n' + 'e' -> 'ne'
  'ne' + 'west</w>' -> 'newest</w>'
  'lo' + 'w' -> 'low'
  'low' + '</w>' -> 'low</w>'
  'we' + 'r' -> 'wer'
```

(1) 不运行代码，写出 `apply_bpe("lowest", merges)` 和 `apply_bpe("lower", merges)` 的结果。
(2) 合并表里明明有 `'lo' + 'w' -> 'low'`，为什么 `lowest` 没有被切成 `['low', ...]`？
(3) 讲义中用另一个语料 `{"low": 5, "lower": 2, "newest": 6, "widest": 3}` 得到的是 `apply_bpe("lowest") → ['low', 'est</w>']`。两个结果的差异说明了什么？

**Q10.** （讲义练习 1）写一个 `jaccard(w1, w2)` 函数，计算两个词 `char_ngrams` 集合的 Jaccard 相似度，并：

(1) 写出 `playing` 与 `played` 的共享 n-gram 集合和 Jaccard 值；
(2) 再算 `cat` 与 `cats`。结合上一节 Word2Vec 中实测 `cos(cat, cats) ≈ 0.20` 的现象，说明 FastText 会带来什么不同。

**Q11.** 关于 `learn_bpe` 的两个问题：

(1) 对 `main.py` 的语料调用 `learn_bpe(corpus, k_merges=30)`，实际只返回 18 条合并规则。为什么？18 这个数字可以怎么推出来？
(2) 写一小段代码，统计合并 0、1、2、5、10、18 次后，整个语料（按词频加权）被切成多少个 token，以及"每个 token 平均覆盖多少个字符"。这就是讲义练习 2 的简化版。

---

## 四、面试高频题

**Q12.**（基础必考）Word2Vec、GloVe、FastText 三者的核心区别是什么？各自适合什么场景？

**Q13.**（原理深挖）请完整描述 BPE 的训练和编码过程。词表大小怎么选？为什么说子词 tokenizer"没有 OOV"？

**Q14.**（原理深挖）BPE、WordPiece、SentencePiece 有什么区别？为什么多语言模型更倾向 SentencePiece（带 byte fallback）？

**Q15.**（工程实践）讲义说"tokenizer 与模型不匹配是最常见的静默生产 bug"。请举出它的几种具体表现，以及你会怎样在工程上防住它。

**Q16.**（场景设计）你要为一个处理用户评论的系统选择词表示：评论里有大量拼写错误、网络新词和表情符号，并且下游是一个轻量级分类器（不上 Transformer）。你选什么？为什么？如果后来决定从零训练一个小型语言模型，又该怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：B

GloVe（Global Vectors）先在整个语料上统计共现矩阵 X，再用加权最小二乘拟合 `vᵢ·ṽⱼ + bᵢ + b̃ⱼ ≈ log Xᵢⱼ`。A 是 Word2Vec 的原始 softmax 形式；C 是 LSA 一类经典的矩阵分解方法（GloVe 与它同属"计数派"，但目标函数不同）；D 是 FastText。

### Q2 — 答案：B

代入数值：`f(1) = (1/100)^0.75 ≈ 0.032`，`f(10) = 0.1^0.75 ≈ 0.178`，`f(100) = 1`，`f(10000) = 1`。所以 f 是**单调不减、在 x_max 处封顶**的函数：
- 只共现一两次的词对统计上很不可靠，被大幅降权；
- 高频词对的权重最多为 1，不会像"按出现次数逐条采样"那样随频次线性增长，从而"不会主导损失"。

讲义说它"downweights very frequent pairs"，准确的理解是"**相对于按频次线性加权而言**封顶"，而不是"频次越高权重越低"——A 的"单调递减"是常见误解。C、D 与 f 无关（GloVe 不使用负采样）。

### Q3 — 答案：D

`wrapped = "<where>"`，长度 7：
- n=3：`<wh, whe, her, ere, re>`（5 个）
- n=4：`<whe, wher, here, ere>`（4 个）
- n=5：`<wher, where, here>`（3 个）
- n=6：`<where, where>`（2 个）
- 再加上整词 `<where>`（1 个）

共 15 个，`main.py` 的实际输出也是 `where        15 grams`。注意讲义正文里展示的 `char_ngrams("where")` 结果只列了 13 个，漏掉了 `<where` 和 `where>` 两个 6-gram，以代码运行结果为准。

### Q4 — 答案：B

FastText 的词向量 = 所有字符 n-gram 向量之和（+ 整词向量）。`whereupon` 本身没见过，但它与 `where` 共享 `<wh`、`<whe`、`<wher`、`<where`、`whe`、`wher`、`where`、`her`、`here`、`ere` 共 10 个 n-gram（`main.py` 输出 `shared n-grams between where / whereupon: 10`），这些 n-gram 的向量都是训练过的，于是能组合出一个落在 `where` 附近的向量。C 是很多词级模型的做法，所有 OOV 共用一个向量，信息全丢；只有当一个词的所有 n-gram 都没见过时，FastText 才无能为力。

### Q5 — 答案：C

第一轮统计（按词频加权）：
- `('w','e')`：lower 2 + newest 6 + lowest 4 + newer 2 = **14**
- `('e','s')`、`('s','t')`、`('t','</w>')`：newest 6 + widest 3 + lowest 4 = 13
- `('l','o')`、`('o','w')`：low 5 + lower 2 + lowest 4 = 11

`('w','e')` 以 14 次胜出，与 `main.py` 输出的第一条 `'w' + 'e' -> 'we'` 一致。注意 `newest` 中 `w e` 只出现一次，但要乘上词频 6。

### Q6 — 答案：B

讲义 Key Terms："Vocabulary starts with 256 bytes, so nothing is ever OOV." 任何字符（包括 emoji、生僻字）在 UTF-8 下都是若干字节，最坏情况也能退化到逐字节编码。A、D 不是主要动机；C 错，字节级 BPE 同样要学习合并规则，只是起点从字符换成了字节。

### Q7 — 答案：C

预训练模型的 embedding 矩阵第 i 行就是"token ID = i"的向量，这个对应关系是和原 tokenizer 一起训练出来的。换了 tokenizer，同一个 ID 代表的字符串完全不同，模型看到的输入等于乱码——而且不会报错。讲义的选型表写得很明确："Whatever tokenizer the model shipped with. Never swap."，Ship It 也要求"Refuse to recommend training a custom tokenizer when the user is fine-tuning a pretrained LLM"。B 的"大小相同"毫无意义，关键是 ID 与字符串的映射。

### Q8 — 答案：A

讲义原文："Every modern tokenizer is a BPE variant, WordPiece (BERT), or SentencePiece (T5, LLaMA)"，并且 GPT-2 使用字节级 BPE（`Ġ` 前缀标记词边界是 GPT-2 的约定）。

### Q9 — 参考答案

**(1)** 逐条应用合并规则（`</w>` 是词尾标记）：

`lowest`：`l o w e s t </w>`
→ `w+e`：`l o we s t </w>`
→ `s+t`：`l o we st </w>`
→ `st+</w>`：`l o we st</w>`
→ `l+o`：`lo we st</w>`
→ `we+st</w>`：`lo west</w>`
→ 其余规则都不再匹配

结果：`['lo', 'west</w>']`

`lower`：`l o w e r </w>` → `l o we r </w>` → `lo we r </w>` → `lo wer </w>`

结果：`['lo', 'wer', '</w>']`

两者都与 `main.py` 的实际输出一致。

**(2)** 因为 `apply_bpe` **按学习顺序**应用合并。第 1 条规则 `w+e` 早早就把 `w` 和后面的 `e` 粘成了 `we`；等轮到第 8 条 `lo+w` 时，序列里已经没有单独的 `w` 了，规则自然匹配不上。BPE 编码是一个"贪心、有顺序"的过程，不是"在所有可能切分中选最优"。

**(3)** 讲义的语料里 `newest`（6 次）和 `widest`（3 次）让 `e+s`、`es+t`、`est+</w>` 排在前面，于是 `est</w>` 先形成，`lo+w` 才有机会作用于 `lowest`；本节代码的语料多了 `lowest`、`newer`，`w+e` 的频次（14）超过了 `e+s`（13），合并顺序整体改变，切分结果也随之改变。这说明：**BPE 的切分完全由训练语料的统计决定**，语料稍有变化，同一个词的切分就可能不同。这也是为什么 tokenizer 必须和模型一起版本化、绝不能"换一个看起来差不多的"。（顺带一提：`lower` 明明在训练语料里，也被切成了 3 个 token——只做 10 次合并时，并不保证训练词能合成一个整体。）

### Q10 — 参考答案

```python
def jaccard(w1, w2):
    a, b = char_ngrams(w1), char_ngrams(w2)
    return len(a & b) / len(a | b)

print(sorted(char_ngrams("playing") & char_ngrams("played")))
# ['<pl', '<pla', '<play', 'lay', 'pla', 'play']
print(jaccard("playing", "played"))   # 0.16666666666666666  (6 / 36)
print(jaccard("cat", "cats"))         # 0.23076923076923078  (3 / 13)
```

（均已实测。）

**(1)** 共享 6 个 n-gram：`<pl`、`<pla`、`<play`、`pla`、`lay`、`play`——都是词根 `play` 的片段，正是讲义说的"substantial shared pieces"。Jaccard 只有 0.17，是因为长词的不同后缀会产生大量**不**共享的 n-gram（`ing>`、`yed>` 等）；但 FastText 的向量是**求和**，共享的 6 个 n-gram 会把两个词的向量拉向同一方向，词根的信息被稳定地共享。

**(2)** `cat` 与 `cats` 共享 `<ca`、`<cat`、`cat` 三个 n-gram。Word2Vec 中两者是互不相干的下标，相似度完全取决于上下文，本课程上一节的玩具实验里只有约 0.20；FastText 中两者的向量有 3 个求和项完全相同，即使上下文不同，也天然带有一份共享成分。这就是 FastText 在形态丰富的语言、拼写变体和罕见屈折形式上更稳健的原因。

### Q11 — 参考答案

**(1)** `learn_bpe` 中有 `if not pair_freq: break`：当语料中**每个词都已经合并成单个 token** 时，不再有任何相邻对，循环提前退出。

推算：语料有 6 个不同的词，初始 token 数分别是"字母数 + 1"（加上 `</w>`）：4 + 6 + 7 + 7 + 7 + 6 = 37；合并到底后每个词只剩 1 个 token，共 6 个。所以 6 个词**各自**一共要经历 37 − 6 = 31 次"减少一个 token"。但一条合并规则可以同时作用于多个词：例如第 1 条 `w+e` 同时缩短了 lower、newest、lowest、newer 四个词，`st+</w>` 同时作用于 newest、widest、lowest。共享得越多，需要的**不同**规则就越少——这里实测正好 18 条（`len(learn_bpe(corpus, 30)) == 18`，后 8 条依次是 `wer+</w>`、`lo+west</w>`、`w+i`、`wi+d`、`wid+e`、`wide+st</w>`、`lo+wer</w>`、`ne+wer</w>`）。合并到底后，`apply_bpe("lowest")` 得到 `['lowest</w>']`，`apply_bpe("lower")` 得到 `['lower</w>']`——词表退化成了"整词表"，失去了子词的意义。真实场景中词表远大于合并次数，所以不会出现这种情况。

**(2)**

```python
corpus = Counter({"low": 5, "lower": 2, "newest": 6, "widest": 3, "lowest": 4, "newer": 2})
merges = learn_bpe(corpus, 30)
chars = sum(len(w) * f for w, f in corpus.items())          # 113
for k in [0, 1, 2, 5, 10, 18]:
    toks = sum(len(apply_bpe(w, merges[:k])) * f for w, f in corpus.items())
    print(k, toks, round(chars / toks, 2))
```

实测输出：

```text
0 135 0.84
1 121 0.93
2 108 1.05
5 74 1.53
10 46 2.46
18 22 5.14
```

解读：合并 0 次时 token 数 = 113 个字符 + 22 个 `</w>`，所以每 token 不到 1 个字符；前几次合并压缩最快（高频对先合并），之后边际收益递减；18 次后每个词（共 22 次出现）都只剩 1 个 token。在真实大语料上，这条曲线会如讲义所说逐渐趋近每 token 约 2～3 个字符。

### Q12 — 参考回答要点

| 维度 | Word2Vec | GloVe | FastText |
|------|----------|-------|----------|
| 训练信号 | 局部窗口，在线预测上下文（SGNS） | 全局共现矩阵，加权最小二乘拟合 `log X` | 同 Word2Vec，但词向量 = 字符 n-gram 之和 |
| 基本单位 | 整词 | 整词 | 整词 + 字符 n-gram（3–6） |
| OOV | 无法处理 | 无法处理 | 可由 n-gram 组合 |
| 形态变化 | 各词形互不相关 | 各词形互不相关 | 共享词根 n-gram |
| 训练代价 | 需多轮遍历语料 | 一次统计共现，之后只遍历非零项（讲义："costs less to train"） | 比 Word2Vec 更大（n-gram 表大） |

- **场景**：通用英文词向量、不需要容忍 OOV → GloVe；拼写错误、新词、形态丰富的语言 → FastText；需要快速在自己的领域语料上训练 → Word2Vec / FastText。
- **共同局限**：都是**静态**词向量，无法处理多义词——这要靠上下文模型（BERT 等）。
- **加分点**：指出 GloVe 的动机是回答"计数派（LSA）与预测派（Word2Vec）谁更好"，结论是只要损失设计得当，矩阵分解也能达到或超过 Word2Vec。

### Q13 — 参考回答要点

- **训练**：
  1. 把每个词拆成字符（或字节）序列，加上词尾标记（如 `</w>`）；
  2. 统计所有相邻符号对的频次（按词频加权）；
  3. 合并频次最高的一对，生成新符号，记录到合并表；
  4. 重复直到达到目标合并次数 / 词表大小。
- **编码**：把新词拆成字符，按合并表的**学习顺序**依次应用规则（生产实现通常是"反复合并当前序列中优先级最高的相邻对"）。
- **词表大小**：讲义 Ship It 给出的参考是英文单语 LM 约 32k、多语言 64k～100k；真实 GPT / BERT / T5 学习 3 万～10 万次合并。词表越大，序列越短、推理越快，但 embedding 矩阵越大、稀有 token 训练不充分；越小则相反。
- **没有 OOV 的原因**：基础词表包含所有单字符（字节级 BPE 则是全部 256 个字节），任何字符串最坏也能退化成字符/字节序列，所以永远能编码成已知 ID 的有限序列。
- **加分点**：BPE 本质上是一种数据压缩算法，被 Sennrich 等人（2016）引入神经机器翻译；合并顺序依赖语料统计，所以 tokenizer 必须和模型一起版本化。

### Q14 — 参考回答要点

- **BPE**：按**频次**选择要合并的相邻对；GPT-2 起使用字节级版本。
- **WordPiece**（BERT）：同样是自底向上合并，但选择标准不是频次，而是"合并后能让训练语料似然提升最多"的对；词内后续片段用 `##` 前缀标记（如 `play ##ing`）。
- **SentencePiece**（T5、LLaMA）：是一个**工具/框架**，支持 BPE 和 Unigram 两种算法；关键特点是把输入当作原始字符流，**空格也作为普通符号**（用 `▁` 表示）参与建模，因此不依赖预分词，对中文、日文等无空格语言天然友好，解码可以无损还原原文。
- **byte fallback**：遇到词表外的字符时退回到字节表示，避免产生 `<unk>`。
- **为什么多语言偏好 SentencePiece + byte fallback**：不同语言的分词规则差异巨大，"不预分词"的设计避免了为每种语言写规则；byte fallback 保证生僻字、emoji 不会丢失。讲义 Ship It："Flag non-English / multi-script corpora as needing SentencePiece with byte fallback."
- 详见 [阶段 05 · 19 子词 Tokenization](../../19-subword-tokenization/docs/zh.md)。

### Q15 — 参考回答要点

- **典型表现**：
  1. 微调或推理时加载了**另一个**模型的 tokenizer（同系列不同版本、或"看起来一样"的 BPE），token ID 错位，模型输出质量骤降但不报错；
  2. 新增特殊 token 后忘了扩展 embedding 矩阵（Hugging Face 中需 `model.resize_token_embeddings(len(tokenizer))`），新 ID 越界或指向未训练的向量；
  3. 训练和推理用了不同的规范化选项（大小写、Unicode 规范化、是否加 BOS/EOS），得到不同的 token 序列；
  4. tokenizer 库升级导致切分细节变化（与第 01 节的"可复现性漂移"同理）。
- **防御**：
  - tokenizer 文件与模型权重**放在同一个制品**里、一起加载（同一路径 / 同一版本号）；
  - 启动时做一致性断言：词表大小 = embedding 行数，特殊 token ID 符合预期；
  - 对固定的一组样例句子做"编码 → 解码"回归测试，并冻结期望的 token ID；
  - 锁定 tokenizer 库版本。

### Q16 — 参考回答要点

- **轻量分类器场景 → FastText**：
  - 拼写错误（`gooood`、`amazng`）和网络新词与正常词共享大量字符 n-gram，能得到合理向量，GloVe 遇到它们只能当 OOV；
  - 推理就是查表 + 求和，无需 GPU；
  - 讲义的选型表："must handle misspellings / neologisms / morphologically rich languages → FastText"。
  - 也可以先跑一个 TF-IDF（可配合字符 n-gram 特征）基线作对比——讲义提醒线性模型做生产文本分类"Still TF-IDF"。
  - 表情符号若对任务重要，需要在 tokenization 阶段单独保留为 token。
- **从零训练小型 LM → 先在自己的语料上训练子词 tokenizer**（讲义："Train a BPE or SentencePiece tokenizer on your corpus first"）：
  - 有 emoji、多种文字时选字节级 BPE 或带 byte fallback 的 SentencePiece，保证无 OOV；
  - 词表规模参考单语约 32k；
  - tokenizer 训练完成后冻结，与模型一起版本化。
- **常见误区**：在这个场景下选词级 tokenizer——Ship It 明确要求"Refuse to recommend word-level tokenization for any model targeting production inference"。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 03 词 Embeddings——从零实现 Word2Vec](../../03-word-embeddings-word2vec/docs/zh.md)：本节官方前置课；Skip-gram、负采样、OOV 与形态问题的来源。
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../02-bag-of-words-tfidf/docs/zh.md)：计数表示；GloVe 的共现矩阵是它的"词 × 词"版本。
- [阶段 01 · 11 奇异值分解](../../../01-math-foundations/11-singular-value-decomposition/docs/zh.md)：矩阵分解视角，帮助理解 GloVe 与 LSA。

### 本节被哪些后续内容用到
- [阶段 05 · 19 子词 Tokenization——BPE、WordPiece、Unigram、SentencePiece](../../19-subword-tokenization/docs/zh.md)：本节 BPE 的完整展开。
- [阶段 05 · 18 多语言自然语言处理](../../18-multilingual-nlp/docs/zh.md)：多语言词表与 SentencePiece。
- [阶段 05 · 05 情绪分析](../../05-sentiment-analysis/docs/zh.md)、[阶段 05 · 08 文本的 CNNs 和 RNNs](../../08-cnns-rnns-for-text/docs/zh.md)：预训练 GloVe / FastText 向量作为模型输入。
- [阶段 10 · 01 Tokenizers](../../../10-llms-from-scratch/01-tokenizers/docs/zh.md)、[阶段 10 · 02 构建 Tokenizer](../../../10-llms-from-scratch/02-building-a-tokenizer/docs/zh.md)：为 LLM 从零构建字节级 BPE。
- [阶段 19 · 30 从零实现 BPE Tokenizer](../../../19-capstone-projects/30-bpe-tokenizer-from-scratch/docs/zh.md)：综合项目中的 BPE 实战。

### 延伸关键词
`LSA / HAL` · `PMI` · `GloVe 加权最小二乘` · `hashing trick（FastText 的 n-gram 桶）` · `byte-level BPE` · `WordPiece ##` · `SentencePiece ▁` · `Unigram LM` · `byte fallback` · `tokenizer-model mismatch`
