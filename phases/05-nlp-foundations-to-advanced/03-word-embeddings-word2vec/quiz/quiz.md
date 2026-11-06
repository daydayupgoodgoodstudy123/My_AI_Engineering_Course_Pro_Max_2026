# 测验 · 词 Embeddings——从零实现 Word2Vec（Word Embeddings — Word2Vec from Scratch）

> **阶段 05 · NLP 基础到高级 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 分布式假设 | Firth（1957）："You shall know a word by the company it keeps"——上下文相似的词，含义也相似 |
| 2 | 稠密静态 embedding | 每个词一个低维（常见 100–300 维）稠密向量；`dog` 与 `puppy` 在空间中靠近，TF-IDF 做不到 |
| 3 | Skip-gram vs CBOW | Skip-gram：中心词 → 预测上下文；CBOW：上下文 → 预测中心词。Skip-gram 训练更慢，但对稀有词更好 |
| 4 | 网络结构 | one-hot → `W`（无非线性的隐藏层）→ `W'` → 词表 softmax；训练完丢掉输出层，`W` 的行就是 embedding |
| 5 | 负采样 | 把 V 路 softmax 改成"这对词是否真的共现"的二分类：每个正样本配 k 个随机负样本 |
| 6 | 负采样的梯度 | 中心向量梯度 = `(σ(v·u⁺) − 1)·u⁺ + Σ σ(v·u⁻)·u⁻`；两张表 `W`、`W'` 都会被更新 |
| 7 | 词向量类比 | `king − man + woman ≈ queen`：差向量编码了某种"关系方向"；检索时要排除三个输入词 |
| 8 | 余弦近邻 | 先把所有向量归一化，再用矩阵乘一次算出与目标的余弦相似度并排序 |
| 9 | 两大局限 | 多义词共用一个向量（`bank`）；未登录词（OOV）没有向量——分别由上下文 embedding 和 subword（fastText）解决 |
| 10 | 2026 年的用武之地 | 轻量领域检索、设备端推理（查表即一行读取）、可视化/可解释、偏见方向探测 |

### 核心技能（能动手做到）

- [ ] 能写出 `skipgram_pairs`，并手算给定句子长度与窗口时的正样本对数（如 5 个词、window=2 → 14 对）
- [ ] 能写出负采样的损失函数，并**手推**中心向量、正上下文向量、负样本向量三处梯度，与 `train_pair` 逐行对上
- [ ] 能从零跑通训练循环，并用 `nearest` 验证 `cat` 的近邻里有 `dog`
- [ ] 能实现 `analogy(vocab, W, a, b, c)`，并解释为什么要把 a、b、c 排除在候选之外
- [ ] 能把均匀负采样改成 unigram^0.75 分布，并说明这样做的动机
- [ ] 能用 gensim 的 `Word2Vec(sentences, vector_size=..., window=..., sg=1, negative=...)` 训练并调用 `model.wv.most_similar`
- [ ] 能为一个训练好的模型设计质量检查：类比测试、近邻测试、对称性检查、范数异常检查，并说明为什么不能只看类比准确率

---

## 二、基础自测（选择题）

**Q1.** 关于 Skip-gram 与 CBOW，下列说法正确的是：

- A. Skip-gram 由上下文预测中心词，CBOW 由中心词预测上下文
- B. Skip-gram 由中心词预测上下文，CBOW 由上下文预测中心词
- C. Skip-gram 是深层网络，CBOW 是浅层网络
- D. Skip-gram 训练更快，但对稀有词表现更差

**Q2.** 对句子 `["the", "cat", "sat", "on", "mat"]` 调用 `skipgram_pairs(docs, window=2)`，一共产生多少个 (center, context) 正样本对？

- A. 8
- B. 10
- C. 14
- D. 20

**Q3.** Word2Vec 使用负采样（negative sampling）的主要原因是：

- A. softmax 无法表示概率分布
- B. 对 10 万级词表做完整 softmax，每一步都要和所有词算点积并归一化，代价太高
- C. 负采样能让模型学会处理多义词
- D. 负采样能解决未登录词问题

**Q4.** 训练结束后，通常把哪部分作为词向量使用？

- A. 输出层 `W'`（上下文表）
- B. 输入层到隐藏层的权重 `W`（中心词表），`W'` 常被丢弃或与 `W` 平均
- C. `W @ W'.T` 的乘积矩阵
- D. 训练后另外学习的一个投影矩阵

**Q5.** 记中心词向量为 `v`、正上下文向量为 `u⁺`、负样本向量为 `u⁻ᵢ`，负采样损失为 `L = −log σ(v·u⁺) − Σᵢ log σ(−v·u⁻ᵢ)`。`∂L/∂v` 等于：

- A. `(σ(v·u⁺) − 1)·u⁺ + Σᵢ σ(v·u⁻ᵢ)·u⁻ᵢ`
- B. `(1 − σ(v·u⁺))·u⁺ − Σᵢ σ(v·u⁻ᵢ)·u⁻ᵢ`
- C. `σ(v·u⁺)·u⁺ + Σᵢ σ(v·u⁻ᵢ)·u⁻ᵢ`
- D. `(σ(v·u⁺) − 1)·v + Σᵢ σ(v·u⁻ᵢ)·v`

**Q6.** 同一个 Word2Vec 向量无法区分 "river bank" 和 "bank account" 中的 `bank`，根本原因是：

- A. 负采样把罕见义项的样本丢掉了
- B. 窗口太小，看不到足够的上下文
- C. 它是静态 embedding：每个词形只有一个向量，与所在上下文无关
- D. 向量维度太低，装不下两个含义

**Q7.** 计算类比 `king − man + woman` 后用余弦近邻找答案时，要把 `king`、`man`、`woman` 三个词排除在候选之外，主要是因为：

- A. 这三个词的向量没有被归一化
- B. 结果向量往往离输入词（尤其是 `king`）本身最近，不排除的话 top-1 常常就是输入词
- C. 这三个词不在词表里
- D. 为了让结果的余弦值更大

**Q8.** 本节 `main.py` 训练后实测：`cos(cat, dog) ≈ 0.99`，而 `cos(cat, cats)` 只有约 0.20。最合理的解释是：

- A. 训练轮数不够，再多训练几轮 `cat` 和 `cats` 一定会靠近
- B. Word2Vec 把每个词形当作互不相关的原子符号，`cat` 和 `cats` 之间没有任何共享参数；它们在本语料中的上下文也不同
- C. 余弦相似度对单复数不敏感
- D. tokenizer 把 `cats` 切成了 `cat` + `s`

---

## 三、动手 / 代码题

**Q9.** 阅读本节的 `train_pair`：

```python
def train_pair(W, W_prime, c_idx, ctx_idx, neg_indices, lr):
    v_c = W[c_idx]
    u_pos = W_prime[ctx_idx]
    u_negs = W_prime[neg_indices]

    pos_err = sigmoid(v_c @ u_pos) - 1.0
    neg_errs = sigmoid(u_negs @ v_c)

    grad_center = pos_err * u_pos + neg_errs @ u_negs
    W_prime[ctx_idx] -= lr * pos_err * v_c
    for i, neg_idx in enumerate(neg_indices):
        W_prime[neg_idx] -= lr * neg_errs[i] * v_c
    W[c_idx] -= lr * grad_center
```

(1) `neg_errs @ u_negs` 计算的是什么？各数组的形状是什么？
(2) 如果有人把 `grad_center = ...` 这一行挪到 `W_prime[ctx_idx] -= ...` **之后**，结果会变吗？`u_pos` 和 `u_negs` 在这个问题上表现一样吗？为什么？
(3) 为什么要在最后一步才更新 `W[c_idx]`？

**Q10.** 补全两个函数：

(1) `analogy(vocab, W, a, b, c, topk=5)`：返回 `b − a + c` 的近邻（复用本节的 `nearest`）。
(2) `unigram_table(docs, vocab, power=0.75)`：返回一个长度为词表大小的概率数组，用于替换 `train` 中的均匀负采样 `rng.integers(0, vocab_size, ...)`。说明 0.75 次方的作用，并给出替换后的采样写法。

**Q11.** 本节 `main.py` 的实际输出中有这样一段：

```text
nearest to chased:
  a            0.977
  mouse        0.823
  cat          0.473
  dog          0.393
```

`chased` 最近的邻居竟然是冠词 `a`（0.977）。请结合语料解释原因，并说明这暴露了"上下文相似 ≠ 语义相似"的哪一面。你会用讲义中提到的哪种技巧缓解高频词的影响？

---

## 四、面试高频题

**Q12.**（基础必考）请讲清楚 Word2Vec（Skip-gram + 负采样）：输入输出是什么、目标函数是什么、为什么训练出来的向量能表达语义？

**Q13.**（原理深挖）负采样为什么能替代完整 softmax？负样本是怎么采的？还有哪些训练技巧（高频词下采样等）？复杂度从多少降到多少？

**Q14.**（原理深挖）静态词向量（Word2Vec / GloVe）和上下文词向量（ELMo / BERT）的本质区别是什么？为什么说从 Word2Vec 到 BERT 是"从静态到上下文"的跃迁？

**Q15.**（工程实践）2026 年还有必要自己训练 Word2Vec 吗？如果你训练了一个领域词向量，你会如何评估它的质量？

**Q16.**（场景设计）电商平台想得到商品的向量表示，用于"看了又看"推荐。你会如何借用 Word2Vec 的思路？新上架商品怎么办？

---

## 五、参考答案与解析

### Q1 — 答案：B

Skip-gram：给定中心词预测周围词，如 `cat → (the, sat, on)`；CBOW：给定周围词预测中心词。讲义的结论是 Skip-gram "slower to train but handles rare words better"，所以 D 说反了。两者都只有一个无非线性的隐藏层，C 错。

### Q2 — 答案：C

逐个中心词数窗口内（左右各 2 个、不含自己）的词数：

| 中心词 | 下标 | 上下文 | 对数 |
|--------|------|--------|------|
| the | 0 | cat, sat | 2 |
| cat | 1 | the, sat, on | 3 |
| sat | 2 | the, cat, on, mat | 4 |
| on | 3 | cat, sat, mat | 3 |
| mat | 4 | sat, on | 2 |

合计 14 对（已用本节代码实测）。句首句尾的词窗口被截断，所以不是 `5 × 4 = 20`。

### Q3 — 答案：B

完整 softmax 的分母要对整个词表求和，每个训练样本的代价是 O(V·d)；V = 10 万时完全不可行。负采样把它改成 1 个正样本 + k 个负样本的二分类，代价降到 O(k·d)。C、D 是 Word2Vec 本身的局限，负采样解决不了。

### Q4 — 答案：B

讲义："After training, you throw away the output layer. The hidden layer weights are the embeddings." 输入是 one-hot，`one-hot × W` 恰好取出 `W` 的一行，所以 `W` 的每一行就是对应词的向量。`W'` "often discarded, sometimes averaged with W"。本节 `train` 函数也只返回 `vocab, W`。

### Q5 — 答案：A

逐项求导：
- 正样本项：`∂[−log σ(x)]/∂x = σ(x) − 1`，链式乘上 `∂(v·u⁺)/∂v = u⁺`，得 `(σ(v·u⁺) − 1)·u⁺`；
- 负样本项：`∂[−log σ(−x)]/∂x = σ(x)`，乘上 `u⁻ᵢ`，得 `σ(v·u⁻ᵢ)·u⁻ᵢ`。

这与代码完全对应：`pos_err = sigmoid(v_c @ u_pos) - 1.0`、`neg_errs = sigmoid(u_negs @ v_c)`、`grad_center = pos_err * u_pos + neg_errs @ u_negs`。B 是负梯度方向且符号不对；D 把"对 v 求导"和"对 u 求导"混淆了——`v` 出现在**上下文向量**的梯度里（`W_prime[ctx_idx] -= lr * pos_err * v_c`）。

### Q6 — 答案：C

Word2Vec 是查表：`bank` 永远对应 `W` 中同一行，无论上下文是河流还是金融。训练时两种义项的上下文信号会混合进同一个向量，下游分类器无法从向量本身区分义项。ELMo、BERT 等上下文 embedding 会根据每一次出现的上下文生成不同的向量，这就是"从静态到上下文"的跃迁。

### Q7 — 答案：B

`king − man + woman` 在数值上通常仍然离 `king` 很近（`man` 与 `woman` 的差向量相对较小），不排除的话 top-1 很可能就是 `king` 自己（或 `woman`）。讲义的 `analogy` 函数通过 `exclude={vocab[a], vocab[b], vocab[c]}` 把三个输入词剔除。A 错：`nearest` 内部已经做了归一化；C、D 与问题无关。

### Q8 — 答案：B

Word2Vec 的词表是"词形 → 下标"的字典，`cat` 和 `cats` 是两个毫无关系的下标，没有任何共享参数；它们是否靠近**完全取决于上下文是否相似**。本语料中 `cat` 出现在 "the cat sat"、"a cat chased" 里，`cats` 出现在 "cats and dogs"、"cats chase mice" 里，上下文几乎不重叠，所以相似度低。这正是 fastText 引入字符 n-gram 的动机（下一节）。A 错：更多轮数不会凭空创造共享的上下文；D 错：本节 tokenizer 不会拆分单词。

### Q9 — 参考答案

**(1)** 设 `d = 16`、k 为负样本数：`v_c` 形状 `(d,)`，`u_negs` 形状 `(k, d)`，`neg_errs = sigmoid(u_negs @ v_c)` 形状 `(k,)`。`neg_errs @ u_negs` 是 `(k,) @ (k, d) → (d,)`，等价于 `Σᵢ neg_errs[i] * u_negs[i]`——对所有负样本梯度的**加权求和**，用一次矩阵乘代替了讲义版本里的 `for` 循环。

**(2)** **对 `u_pos` 会变，对 `u_negs` 不会变**，原因是 NumPy 的视图（view）与副本（copy）：
- `u_pos = W_prime[ctx_idx]` 是用**单个整数**做基本索引，返回的是 `W_prime` 那一行的**视图**。`W_prime[ctx_idx] -= ...` 原地修改后，`u_pos` 看到的也是新值。如果此时才计算 `grad_center`，用的就是"已经更新过的"上下文向量，梯度不再是同一个点上的梯度。
- `u_negs = W_prime[neg_indices]` 是用**列表**做花式索引（fancy indexing），返回的是**副本**，后续更新 `W_prime` 不影响它。

所以原代码"先算完所有梯度、再统一更新"的顺序是必要的。这也是 NumPy 中最容易踩的隐蔽 bug 之一。

**(3)** 同理，`v_c = W[c_idx]` 也是视图。上下文向量和负样本向量的更新都要用到**旧的** `v_c`（`W_prime[...] -= lr * ... * v_c`）；如果先更新 `W[c_idx]`，后面的更新就会用到新的 `v_c`。把中心词更新放在最后，保证三处更新都基于同一组旧参数——这才是对同一个损失函数做的一步标准梯度下降。

### Q10 — 参考答案

```python
from collections import Counter
import numpy as np

def analogy(vocab, W, a, b, c, topk=5):
    v = W[vocab[b]] - W[vocab[a]] + W[vocab[c]]
    return nearest(vocab, W, v, topk=topk, exclude={vocab[a], vocab[b], vocab[c]})

def unigram_table(docs, vocab, power=0.75):
    counts = Counter(t for doc in docs for t in doc)
    freq = np.array([counts[w] for w in sorted(vocab, key=vocab.get)], dtype=float)
    probs = freq ** power
    return probs / probs.sum()

# 在 train() 中：
#   probs = unigram_table(docs, vocab)
#   neg_candidates = rng.choice(vocab_size, size=k_neg * 2, p=probs)
```

调用约定：`analogy(vocab, W, "man", "king", "woman")` 计算的是 `king − man + woman`。

0.75 次方的作用：如果完全按词频采样，`the`、`a` 这类高频词会占据绝大多数负样本；完全均匀采样则让稀有词被过度采样。0.75 次方介于两者之间，**压低高频词、抬高低频词的采样概率**。在本节语料上实测：`the` 的原始频率是 16%，0.75 次方后降到约 11.8%；`kitten`、`squirrels` 从 2% 升到约 2.5%。这个做法来自 Mikolov 等人 2013 年的负采样论文；本节代码为了简洁使用的是均匀采样。

`sorted(vocab, key=vocab.get)` 保证数组第 i 个位置对应下标为 i 的词，与 `W` 的行对齐。

### Q11 — 参考答案

语料中 `chased` 只出现在两种句子里：`a cat chased a mouse`、`a dog chased a cat`。window = 2 时：
- `chased` 的上下文是 `{a, cat, mouse, dog}`；
- `a` 只出现在这两句里，它的上下文是 `{cat, dog, chased, mouse}`。

两者的上下文分布几乎一样（都围绕 cat/dog/mouse），Skip-gram 的目标只要求"上下文相似的词，中心向量相似"，于是 `a` 与 `chased` 的向量几乎重合。这说明：
- 分布式假设捕获的是**用法的相似**，在小语料上会把"总是一起出现在同一种句式里"的词（哪怕一个是冠词、一个是动词）拉到一起——这更接近"句法/搭配相似"而不是"语义相似"；
- 语料只有 10 种句子重复 20 遍，几乎没有多样性，模型基本是在"背句式"。

缓解：讲义练习 2 提到的**高频词下采样（subsampling）**——以一定概率丢弃高频词所在的训练对，减少 `a`、`the` 这类词的主导作用（论文中的丢弃概率是 `1 − √(t/f(w))`，t 约为 1e-5）。当然，最根本的办法是更大、更多样的语料。

### Q12 — 参考回答要点

- **输入输出**：输入是中心词（one-hot，实际实现中就是一个下标），输出是"窗口内某个词是否是它的上下文"。训练对由滑动窗口从语料中自动生成，是一种自监督学习。
- **结构**：两张表 `W`（中心词）和 `W'`（上下文词），隐藏层没有非线性；打分就是点积 `W[c]·W'[o]`。
- **目标函数（负采样）**：`L = −log σ(v_c·u_o) − Σᵢ log σ(−v_c·u_nᵢ)`，正样本推向 1、k 个负样本推向 0。
- **为什么有语义**：如果两个词的上下文分布相似，为了让它们都和同一批上下文向量有高点积，梯度会把它们的中心向量推向相似的方向——这就是分布式假设的几何化。线性结构（`king − man + woman ≈ queen`）是这种训练方式的副产品。
- **加分点**：Levy & Goldberg（2014）证明 SGNS 隐式地分解了一个"减去 log k 的 PMI 矩阵"，把 Word2Vec 和基于计数的方法（如下一节的 GloVe）联系了起来。
- **常见误区**：说 Word2Vec 是"深度学习模型"——它只有一个线性隐藏层，本质是浅层的对数双线性模型。

### Q13 — 参考回答要点

- **为什么可以替代 softmax**：我们只关心训练出好的向量，不需要真正归一化的概率分布。把"从 V 个词中选出正确的上下文"换成"区分真实上下文与 k 个噪声词"，梯度方向在本质上相似，计算量却从 O(V·d) 降到 O((k+1)·d)。
- **负样本怎么采**：原论文使用 unigram 分布的 3/4 次方，平衡高频词与低频词；k 常取 5–20（小数据取大、大数据取小）。本节代码为简洁用均匀采样，并过滤掉与正样本或中心词相同的下标。
- **其他技巧**：
  - **高频词下采样**：以概率 `1 − √(t/f(w))` 丢弃高频词，既加速训练，又提升稀有词向量质量；
  - **层次 softmax（hierarchical softmax）**：原论文中的另一种替代方案，用霍夫曼树把 softmax 变成 O(log V) 次二分类；
  - 学习率线性衰减、动态窗口等。
- **加分点**：负采样的思想后来在对比学习（如 CLIP、sentence embedding 训练中的 in-batch negatives）里被广泛复用。

### Q14 — 参考回答要点

- **静态**：一个词形一个向量，训练完就固定，与上下文无关。优点是快（查表）、小、可解释；缺点是多义词（`bank`、`table`）的多个义项被压成一个平均向量，OOV 没有向量。
- **上下文**：每次出现都根据整句话动态计算一个向量（ELMo 用双向 LSTM，BERT 用 Transformer 编码器），`river bank` 和 `bank account` 中的 `bank` 得到不同向量，自然解决多义问题。
- **跃迁的意义**：从"词典式表示"变成"句子级计算"——表示不再是一张表，而是一个函数 `f(词, 上下文)`。代价是推理需要跑完整模型，延迟从一次查表变成一次前向传播。
- **联系**：上下文模型的第一层（token embedding 表）本质上仍是一张静态表；Transformer 的 subword tokenizer 也一并解决了 OOV。

### Q15 — 参考回答要点

- **仍然值得训练的场景**（讲义列举）：
  - 轻量领域检索：用医学摘要在笔记本上训练一小时，得到通用模型捕捉不到的专业词向量；
  - 设备端、无 GPU：查一次表就是一行读取；
  - 可解释性与可视化：100 维可以用 PCA / t-SNE 直接看聚类；
  - 偏见研究：用 `he − she` 等方向探测并去除偏见。
- **质量评估**（讲义 Ship It 的思路）：
  1. 类比测试：`king : man :: queen : woman`、`paris : france :: tokyo : japan`、`walking : walked :: swimming : ?`；
  2. 领域近邻测试：挑 5 个领域关键词看 top-5 近邻是否合理；
  3. 对称性检查：`similarity(a, b) == similarity(b, a)`；
  4. 退化检查：若有向量范数 < 0.01 或 > 100，说明训练有 bug；
  5. **下游评估**：最终要在真实任务（分类、检索）上对比。
- **常见误区**：只看类比准确率就宣布模型好——讲义明确指出类比基准"gameable and do not transfer to downstream tasks"，必须内在评估 + 下游评估结合。

### Q16 — 参考回答要点

- **类比**：把每个用户的一次浏览会话（按时间排序的商品 ID 序列）当作一个"句子"，商品 ID 当作"词"，直接套用 Skip-gram + 负采样。在同一会话中邻近出现的商品被视为"上下文"，训练后向量相近的商品就是"经常被一起看"的商品。（业界有 item2vec 等类似做法。）
- **工程细节**：
  - 窗口大小反映"多近才算相关"，可按会话长度调参；
  - 热门商品相当于高频词，需要下采样，负样本分布同样要用平滑后的频率，避免向量被爆款主导；
  - 检索用归一化向量 + ANN 索引做近邻查询。
- **新商品（冷启动）= OOV 问题**：Word2Vec 对没出现过的 ID 没有向量。可以借鉴下一节 fastText"用子单元组合向量"的思路：用商品的类目、品牌、标题词等属性向量组合出一个初始向量；或者用内容侧模型（标题文本 embedding）先顶上，积累足够交互后再纳入训练。
- **加分点**：指出这里同样存在"静态表示"问题——同一个商品在不同用户意图下的相关商品不同，更进一步可以用序列模型（Transformer）做会话级的上下文表示。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../02-bag-of-words-tfidf/docs/zh.md)：本节官方前置课；理解稀疏计数表示的局限，才能明白稠密向量解决了什么。
- [阶段 03 · 03 反向传播](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：本节官方前置课；`train_pair` 就是手写的反向传播 + SGD。
- [阶段 01 · 01 线性代数直觉](../../../01-math-foundations/01-linear-algebra-intuition/docs/zh.md)：点积、余弦相似度、向量加减。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：sigmoid + 二元交叉熵。

### 本节被哪些后续内容用到
- [阶段 05 · 04 GloVe、FastText 和 Subword Embeddings](../../04-glove-fasttext-subword/docs/zh.md)：GloVe 从计数矩阵出发得到类似的向量；fastText 用字符 n-gram 解决本节的 OOV 与形态问题。
- [阶段 05 · 05 情绪分析](../../05-sentiment-analysis/docs/zh.md)、[阶段 05 · 08 文本的 CNNs 和 RNNs](../../08-cnns-rnns-for-text/docs/zh.md)：预训练词向量作为神经网络的输入层。
- [阶段 05 · 22 Embedding 模型深度剖析](../../22-embedding-models-deep-dive/docs/zh.md)：从词向量走向句向量 / 文档向量。
- [阶段 07 · 06 BERT 与掩码语言建模](../../../07-transformers-deep-dive/06-bert-masked-language-modeling/docs/zh.md)：上下文 embedding，解决多义词问题。
- [阶段 11 · 04 Embeddings](../../../11-llm-engineering/04-embeddings/docs/zh.md)：LLM 工程中的向量表示与检索。
- [阶段 18 · 20 偏见与表征伤害](../../../18-ethics-safety-alignment/20-bias-representational-harm/docs/zh.md)：词向量中的性别等偏见方向（讲义练习 3）。

### 延伸关键词
`SGNS` · `hierarchical softmax` · `subsampling` · `PMI / 隐式矩阵分解` · `t-SNE / PCA 可视化` · `word analogy benchmark` · `debiasing (hard / soft)` · `item2vec` · `contextual embeddings (ELMo / BERT)`
