# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 22 节 Embedding 模型 — 2026 年深度剖析 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`hashlib`、`math`、`re`、`collections.Counter`），不需要 sentence-transformers 或 GPU

---

## 1. 这份代码在考察什么

讲义 Step 5 说明了它的定位：用 hashing trick 造一个"假的 dense embedding"，**不追求效果，只展示检索流水线的形状**：tokenize → 向量 → 归一化 → 点积。在这个形状上，代码依次演示：

1. **Dense 检索**：hashing-trick 向量 + 余弦排序。
2. **Matryoshka 截断**：取前 64 维并重新归一化。
3. **Sparse 检索**：词频向量的点积（BM25/SPLADE 的极简替身）。
4. **RRF 融合**：把 dense 和 sparse 两个排名按名次合并。

> 一句话：**这份代码里每一个"操作"都和生产系统一样，只有"向量从哪来"是假的**——这恰好让你看清：向量质量不行时，后面所有花招都救不回来（运行结果里正确答案一次都没排第一）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tokenize(text)` | 函数 | 小写 + 正则取字母数字串 | 分词 |
| `hash_token(token, dim, seed)` | 函数 | 用 MD5 把 token 映射到 `[0, dim)` 的整数 | hashing trick |
| `hash_embed(text, dim)` | 函数 | 每个 token 在哈希位置上 ±1，最后 L2 归一化 | "dense" 向量（替身） |
| `cosine(a, b)` | 函数 | 已归一化向量的点积 | 余弦相似度 |
| `truncate_matryoshka(vec, new_dim)` | 函数 | 取前 `new_dim` 维并重新归一化 | Matryoshka 截断 |
| `rank(corpus_embs, query_emb)` | 函数 | 计算所有文档分数并降序排序 | 暴力检索 |
| `sparse_embed(text)` / `sparse_score(q, d)` | 函数 | 词频 `Counter` 与其点积 | 稀疏检索 |
| `rrf_fuse(rankings, k=60)` | 函数 | 倒数名次融合 | RRF |
| `main()` | 演示入口 | 6 篇文档、1 个查询，跑四种检索并打印 top-3 | — |

数据流：`文本 → tokenize → hash_embed / sparse_embed → rank / sparse_score → (可选) truncate_matryoshka → rrf_fuse`。

---

## 3. 逐段精讲

### 3.1 hashing trick：把任意 token 映射到固定维度

```python
def hash_token(token, dim, seed=0):
    h = hashlib.md5(f"{seed}:{token}".encode()).digest()
    return int.from_bytes(h[:4], "big") % dim
```

- 对 `"seed:token"` 做 MD5，取前 4 个字节转成整数，再对 `dim` 取模，得到 `[0, dim)` 中的一个位置。
- **为什么用 `hashlib.md5` 而不是内置 `hash()`**：Python 的字符串 `hash()` 每次启动进程都会随机化（`PYTHONHASHSEED`），同一个词在两次运行中会落到不同维度，向量就无法跨进程复用。MD5 是确定性的。这里用 MD5 只是为了"确定且分布均匀"，与密码学安全无关。
- `seed` 参数让同一个函数可以产生多个**独立**的哈希：`seed=0` 决定位置，`seed=1` 决定符号。
- 不需要词表：任何新词都能直接映射，这就是 hashing trick 的卖点。代价是**哈希冲突**——本语料中 `iphone` 和 `system` 恰好都落在第 112 维且符号相同，导致讲 Android 的文档与查询之间出现了一点虚假相似度（0.129）。

### 3.2 `hash_embed`：带符号的哈希词袋

```python
def hash_embed(text, dim=256):
    vec = [0.0] * dim
    for tok in tokenize(text):
        idx = hash_token(tok, dim)
        sign = 1.0 if hash_token(tok, 2, seed=1) == 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]
```

- 每个 token 在自己的哈希位置上加 +1 或 -1。**随机符号**的作用：两个不同词冲突到同一维时，有一半概率互相抵消而不是叠加，使点积在期望上更接近真实的词袋点积（这是 feature hashing 的标准技巧）。
- 最后做 L2 归一化，之后点积就等于余弦。
- 本质：这是一个**随机投影后的词袋（BoW）**，完全没有语义——`iPhone` 和 `smartphone` 毫无关系。讲义说真实的 dense embedding 来自 transformer（BGE、Nomic、Voyage），而这里只保留了"文本 → 定长向量 → 归一化"的外形。
- `if norm == 0: return vec`：空文本（或全是标点）时避免除以 0，返回全 0 向量。
- ⚠️ 不去停用词：`the`、`was` 与 `iphone` 权重相同，这直接导致了第 6 节中的错误排名。

### 3.3 余弦与暴力排序

```python
def cosine(a, b):
    if len(a) != len(b):
        raise ValueError(f"cosine: dim mismatch {len(a)} vs {len(b)}")
    return sum(x * y for x, y in zip(a, b))


def rank(corpus_embs, query_emb):
    scored = [(cosine(e, query_emb), i) for i, e in enumerate(corpus_embs)]
    scored.sort(reverse=True)
    return scored
```

- `cosine` 直接返回点积——前提是输入**已经归一化**。这正是讲义 Step 1 强调 `normalize_embeddings=True` 的原因："makes the dot product equal cosine similarity. Always set it."
- 维度检查用 `raise ValueError` 显式报错。这很重要：`zip` 遇到不同长度会静默截断，如果你拿 64 维查询去比 256 维文档，没有这个检查就会得到一个看似正常、实则错误的分数。
- `rank` 是**暴力检索**（brute force），O(N·d)。生产中用 ANN 索引（HNSW、IVF）。
- ⚠️ 平局问题：`scored.sort(reverse=True)` 对 `(score, i)` 元组排序，分数相同时比较下标，`reverse=True` 使**下标大的排前面**。本例中 iPhone（下标 0）与 iPod（下标 3）分数完全相同，iPod 因此排第一。更稳妥的写法是 `scored.sort(key=lambda x: (-x[0], x[1]))`。

### 3.4 Matryoshka 截断

```python
def truncate_matryoshka(vec, new_dim):
    out = vec[:new_dim]
    norm = math.sqrt(sum(v * v for v in out))
    if norm == 0:
        return out
    return [v / norm for v in out]
```

- 与讲义 Step 2 的 NumPy 版本一一对应：切片取前 N 维，再**重新归一化**。不重新归一化，截断后的向量模长小于 1，且不同文档损失的模长不同，点积排序就会失真。
- ⚠️ 关键认识：这里的"截断操作"是对的，但 hashing 向量**不是 Matryoshka 训练出来的**——它的维度位置是随机的，前 64 维并不比后 192 维更重要，截断等于随机丢掉约 3/4 的词。本例中查询里最关键的 `iphone`（第 112 维）被截掉了，只剩 `was、first、released`。讲义原话："Non-Matryoshka models degrade sharply when truncated." 这段代码正好是它的反面演示。

### 3.5 Sparse：词频点积

```python
def sparse_embed(text):
    return Counter(tokenize(text))


def sparse_score(q_sparse, d_sparse):
    total = 0.0
    for tok, q_weight in q_sparse.items():
        total += q_weight * d_sparse.get(tok, 0)
    return total
```

- `Counter` 本身就是一个稀疏向量：只存非零项，key 是词、value 是词频。
- 点积只需遍历**查询**中的词（查询通常很短），到文档里查权重——这正是倒排索引的思路：只看查询词命中的文档。
- `d_sparse.get(tok, 0)`：文档里没有的词贡献 0。对 `Counter` 也可以直接写 `d_sparse[tok]`（缺失键返回 0），用 `.get` 的写法对普通 dict 同样适用。
- ⚠️ 与真实 sparse 检索的差距：BM25 有 IDF 和文档长度归一化；SPLADE 的权重由模型学习，还会做"词扩展"（给文档中没出现的相关词也赋权重）。这里是原始词频，`the` 和 `iphone` 一样重要。

### 3.6 RRF：只看名次的融合

```python
def rrf_fuse(rankings, k=60):
    scores = {}
    for ranking in rankings:
        for rank, (_, idx) in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])
```

- Reciprocal Rank Fusion：每个文档在每个排名列表中贡献 `1 / (k + 名次)`，名次从 1 算起（代码里 `rank` 从 0 开始，所以写成 `k + rank + 1`）。
- **只用名次、丢掉原始分数**：dense 余弦在 0–1 之间，sparse 分数是词频之和（本例为 0–4），量纲不同，直接相加没有意义；名次天然可比。
- `k = 60` 平滑头部差距：第 1 名贡献 1/61，第 2 名 1/62，差距很小，让多个检索器"投票"而不是由某一路的头名独断。
- `for rank, (_, idx) in enumerate(ranking)`：嵌套解包，`_` 丢弃分数，只要文档下标。
- ⚠️ 局部变量 `rank` 遮蔽了同文件中的全局函数 `rank`。在函数内部无害，但如果以后在这个函数里想调用 `rank(...)` 就会出错，是值得避免的命名习惯。
- `main()` 中只把每路的前 5 名送进来融合（`dense_ranked[:5]`），这与生产中"每路取 top-k 再融合"的做法一致。

### 3.7 演示入口

```python
    corpus = [
        "Apple released the first iPhone on June 29, 2007.",
        "Macworld 2007 featured the iPhone announcement by Steve Jobs.",
        "Android launched in 2008 as Google's mobile operating system.",
        "The first iPod was released by Apple in 2001.",
        "Fraud refers to wrongful or criminal deception for financial gain.",
        "Section 420 of the Indian Penal Code covers cheating.",
    ]

    query = "When was the first iPhone released?"
```

- 语料设计得很有意思：iPhone 文档（正确答案）、Macworld 文档（相关但不是答案）、iPod 文档（**词汇高度重叠的干扰项**）、Android（同领域），以及两篇法律文档（无关；"Section 420" 也呼应讲义里 sparse 擅长匹配编号的说法）。
- iPod 文档专门用来考验检索器能否区分"词相似"与"意思相似"。真实的语义 embedding 会理解查询问的是 iPhone；而本代码的所有方法都是词级的，最终都被它骗了。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| hashing trick 代替 transformer | 零依赖、确定性、演示流水线形状 | 没有语义；生产用 BGE-M3、text-3-large 等 |
| MD5 而非内置 `hash()` | 跨进程确定，结果可复现 | 速度较慢；生产 feature hashing 常用 MurmurHash |
| 随机 ±1 符号 | 冲突时期望上互相抵消 | 仍有冲突噪声（本例 `iphone`/`system`） |
| 先归一化、`cosine` 只算点积 | 与 `normalize_embeddings=True` 的生产实践一致 | 输入未归一化时结果错误 |
| 截断后重新归一化 | 保证点积仍等于余弦 | 对非 Matryoshka 向量无济于事 |
| 词频 sparse | 演示稀疏点积与倒排的思路 | 无 IDF、无长度归一化；生产用 BM25 / SPLADE |
| RRF（k=60） | 免调参、量纲无关 | 丢失分数幅度信息；同源分数可用加权和 |
| 元组 `sort(reverse=True)` | 写法简短 | 平局时偏向大下标；应显式指定排序键 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| f-string 拼接 + `.encode()` | `f"{seed}:{token}".encode()` | 字符串转 UTF-8 字节，哈希函数要求输入是 bytes |
| `hashlib` | `hashlib.md5(...).digest()` | `.digest()` 返回 16 字节的原始摘要 |
| 字节切片与 `int.from_bytes` | `int.from_bytes(h[:4], "big")` | 取前 4 字节按大端序转成整数 |
| 取模 `%` | `... % dim` | 把大整数压到 `[0, dim)` |
| 列表乘法初始化 | `[0.0] * dim` | 创建长度为 `dim` 的零向量（元素是不可变的 float，所以安全） |
| 条件表达式 | `1.0 if ... == 1 else -1.0` | 一行 if/else |
| `math.sqrt` + 生成器 | `math.sqrt(sum(v * v for v in vec))` | L2 范数 |
| 列表切片 | `vec[:new_dim]` | 取前 N 个元素（返回新列表） |
| `raise ValueError` | `raise ValueError(f"cosine: dim mismatch ...")` | 主动报错，避免 `zip` 静默截断 |
| 元组列表排序 | `scored.sort(reverse=True)` | 按元组逐元素比较；原地排序 |
| `sorted` + `key=lambda` | `sorted(scores.items(), key=lambda x: -x[1])` | 按值降序；返回新列表 |
| `Counter` | `Counter(tokenize(text))` | 词频统计，天然的稀疏向量 |
| `dict.get(key, default)` | `d_sparse.get(tok, 0)`、`scores.get(idx, 0.0)` | 缺失键返回默认值 |
| 嵌套解包 | `for rank, (_, idx) in enumerate(ranking)` | 一次解开 `(名次, (分数, 下标))` |
| `_` 占位 | `(_, idx)` | 表示该值不使用 |
| f-string 精度 | `f"{score:.3f}"`、`f"{score:.4f}"` | 保留 3 / 4 位小数 |

---

## 6. 运行结果解读

实际运行 `python3 main.py` 的输出：

```text
=== dense (hash-trick) retrieval ===
  0.544  The first iPod was released by Apple in 2001.
  0.544  Apple released the first iPhone on June 29, 2007.
  0.272  Macworld 2007 featured the iPhone announcement by Steve Jobs.

=== Matryoshka truncation: 256 -> 64 ===
  1.000  The first iPod was released by Apple in 2001.
  0.577  Apple released the first iPhone on June 29, 2007.
  0.000  Section 420 of the Indian Penal Code covers cheating.

=== sparse (lexical) retrieval ===
  4.000  The first iPod was released by Apple in 2001.
  4.000  Apple released the first iPhone on June 29, 2007.
  2.000  Macworld 2007 featured the iPhone announcement by Steve Jobs.

=== RRF fusion (dense + sparse) ===
  0.0328  The first iPod was released by Apple in 2001.
  0.0323  Apple released the first iPhone on June 29, 2007.
  0.0317  Macworld 2007 featured the iPhone announcement by Steve Jobs.

note: the hash-trick embedder is for demonstration.
real dense embeddings come from transformers (BGE, Nomic, Voyage).
Matryoshka truncation, cosine ranking, and RRF fusion all stay identical.
```

逐段解读：

- **Dense：0.544 平局，iPod 排第一**。查询 6 个 token，两篇文档各 9 个 token，各自共享 4 个（iPod：`was/the/first/released`；iPhone：`the/first/iphone/released`），余弦都是 `4/(√6·√9) ≈ 0.544`。平局由 `sort(reverse=True)` 按下标打破，下标 3 的 iPod 排在下标 0 的 iPhone 前面。**正确答案没有排第一，原因是停用词和排序实现，而不是相关性。**
- **Matryoshka 256→64：iPod 1.000**。截断后查询只剩 `was/first/released`（哈希位置 28、44、61），`iphone`（112）被截掉；iPod 文档前 64 维里恰好也只有这三个词，余弦为 1。第三名是无关的法律文档（0.000），说明截断后剩下的信息已不足以区分文档。这演示的是"非 Matryoshka 向量截断会崩"。
- **Sparse：4.000 平局**。原因同 dense：原始词频、不去停用词，`the`、`was` 与 `iphone` 等价。平局同样被大下标打破。
- **RRF**：两路的前三名顺序一致（iPod、iPhone、Macworld），分数分别是 `2/61 ≈ 0.0328`、`2/62 ≈ 0.0323`、`2/63 ≈ 0.0317`。两路犯了同样的错，融合也救不回来。
- **最后三行**：提醒你在真实系统中只需把 `hash_embed` 换成 transformer 编码器，其他操作不变。读完结果你应该同意：**操作不变，但向量质量决定一切**。

---

## 7. 动手改一改

1. 修复平局：把 `rank` 和 sparse 排序改成 `sort(key=lambda x: (-x[0], x[1]))`，观察 iPhone 是否排到第一。
2. 在 `tokenize` 之后加停用词过滤（`when, was, the, ...`），重新运行；dense 应变为 iPhone ≈ 0.655、iPod ≈ 0.516（参考测验 Q11）。
3. 给 `sparse_score` 加 IDF 权重 `log(N/df)`，观察在 6 篇文档的小语料上为什么反而让 iPod 领先更多。
4. 把 `dim` 从 256 改成 32，统计语料中有多少对 token 发生哈希冲突，观察检索结果如何变差。
5. 实现 ColBERT 风格的 `maxsim(q_vecs, d_vecs)`：每个 token 用 `hash_embed(token)` 作为 token 向量，比较它与 dense 的排序差异（参考测验 Q10）。
6. 进阶：如果环境中有 `sentence-transformers`，用讲义 Step 1 的 `BAAI/bge-small-en-v1.5` 替换 `hash_embed`（记得给查询加 BGE 前缀），对比四段输出。

---

## 8. 常见坑

- **忘记归一化**：`cosine` 直接返回点积，输入不是单位向量时结果就不是余弦。
- **截断后不重新归一化**：模长不一致导致排序失真；而对非 Matryoshka 向量，即使归一化也会严重退化。
- **用 Python 内置 `hash()` 做 hashing trick**：每次进程启动结果不同，离线建的索引与在线查询对不上。
- **元组排序的隐式平局规则**：`sort(reverse=True)` 让大下标赢平局，检索结果依赖文档在列表里的位置。
- **把融合当万能药**：RRF 只能综合多路的"不同意见"，各路犯同样的错时融合无效。
- **维度不匹配被静默吞掉**：如果没有 `cosine` 里的长度检查，64 维与 256 维向量 `zip` 后会得到一个看似合理的错误分数。
