# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到高级 · 第 03 节 词 Embeddings——从零实现 Word2Vec ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 10–15 秒） ｜ **依赖**：`numpy`；标准库 `re`。不需要 gensim

---

## 1. 这份代码在考察什么

这份约 120 行的脚本，用 NumPy 从零实现了 **Skip-gram + 负采样（SGNS）** 版的 Word2Vec，并在一个玩具语料上训练、查看近邻。它要你真正弄懂：

1. **训练数据从哪来**：滑动窗口自动生成 (中心词, 上下文词) 正样本对——这是一种无需人工标注的自监督学习。
2. **模型是什么**：只是两张向量表 `W`、`W'`，打分就是点积，没有任何隐藏层非线性。
3. **负采样怎么把 softmax 变成二分类**：每个正样本配 k 个随机负样本，用 sigmoid + 对数损失训练。
4. **梯度怎么手写**：`train_pair` 里每一行都对应一项手推的偏导，还藏着 NumPy 视图 / 副本的细节。
5. **怎么查看结果**：用余弦相似度找近邻，体会"上下文相似 → 向量相似"，以及它在小语料上的奇怪表现。

> 一句话：**Word2Vec 的全部"魔法"就是：两张表 + 点积 + sigmoid + 随机负样本。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TOKEN_RE` / `tokenize` | 正则 + 函数 | 只抽取字母单词并小写（数字、标点都丢弃） | 预处理 |
| `build_vocab` | 函数 | 按首次出现顺序给词编号 | 词表 |
| `skipgram_pairs` | 函数 | 滑动窗口生成 (center, context) 正样本对 | Skip-gram 训练数据 |
| `sigmoid` | 函数 | 带截断的数值稳定 sigmoid | 二分类概率 |
| `init_embeddings` | 函数 | 用 N(0, 0.1²) 初始化 `W` 和 `W'` | 两张 embedding 表 |
| `train_pair` | 函数 | 对一个正样本 + 若干负样本做一步 SGD | 负采样损失与梯度 |
| `train` | 函数 | 多轮打乱样本对、采负样本、调用 `train_pair`，返回 `vocab, W` | 训练循环 |
| `nearest` | 函数 | 归一化后用余弦相似度排序，返回 top-k 近邻 | 向量检索 |
| `main` | 函数 | 10 句玩具语料 × 20，训练后打印 4 个词的近邻 | 演示入口 |

数据流：`corpus → tokenize → docs → build_vocab / skipgram_pairs → train（反复调用 train_pair 更新 W、W'）→ W → nearest`。

---

## 3. 逐段精讲

### 3.1 预处理与词表

```python
TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def tokenize(text):
    return [t.lower() for t in TOKEN_RE.findall(text)]
```

- 比第 02 节更进一步，连数字分支都去掉了，只保留字母单词。玩具语料里没有数字和标点，这里只是保持简单。
- `build_vocab` 与第 02 节完全相同：`vocab[token] = len(vocab)` 按首次出现顺序编号。本语料最终词表有 **24** 个词。

### 3.2 `skipgram_pairs`：滑动窗口造训练数据

```python
def skipgram_pairs(docs, window=2):
    pairs = []
    for doc in docs:
        for i, center in enumerate(doc):
            for j in range(max(0, i - window), min(len(doc), i + window + 1)):
                if i != j:
                    pairs.append((center, doc[j]))
    return pairs
```

- 对每个位置 `i`，取左右各 `window` 个词作为上下文；`max(0, ...)` 和 `min(len(doc), ...)` 处理句首句尾的越界，`i != j` 排除中心词自己。
- 例：`["the","cat","sat","on","mat"]`、window=2 → 2+3+4+3+2 = **14** 对。
- 窗口**不跨句**：每个 `doc` 单独处理。
- 本语料 200 个句子共生成 **2800** 个样本对，每个 epoch 都要遍历一遍。
- ⚠️ 简化：原版 Word2Vec 还会对窗口大小做随机缩小（近的上下文被采样得更多），并对高频词做下采样；这里都没做。

### 3.3 `sigmoid` 与初始化

```python
def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))


def init_embeddings(vocab_size, dim, seed):
    rng = np.random.default_rng(seed)
    W = rng.normal(0, 0.1, size=(vocab_size, dim))
    W_prime = rng.normal(0, 0.1, size=(vocab_size, dim))
    return W, W_prime
```

- `np.clip(x, -20, 20)`：当 `x` 是很大的负数时，`np.exp(-x)` 会溢出成 `inf`（并触发警告）。截断到 ±20 后，`sigmoid(20) ≈ 1 − 2e-9`，精度上已经足够。这是**数值稳定性**的标准防御写法。
- 两张表形状都是 `(vocab_size, dim)`。`W` 是中心词表（最后保留），`W'` 是上下文词表（最后丢弃）。
- 初始化为小随机数（标准差 0.1）而不是 0：如果两张表全为 0，`grad_center` 是若干零向量的组合、`W'` 的更新量是"误差 × 零向量"，所有梯度恰好为 0，参数永远不会更新；随机初始化同时也打破了不同词之间的对称性。
- `np.random.default_rng(seed)` 是 NumPy 推荐的新式随机数生成器，传入种子保证结果可复现。

### 3.4 `train_pair`：负采样的一步 SGD（核心）

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

损失函数：`L = −log σ(v·u⁺) − Σᵢ log σ(−v·u⁻ᵢ)`。逐行对照：

| 代码 | 数学含义 |
|------|---------|
| `pos_err = sigmoid(v_c @ u_pos) - 1.0` | `∂L/∂(v·u⁺) = σ(v·u⁺) − 1`，正样本得分越接近 1，误差越接近 0 |
| `neg_errs = sigmoid(u_negs @ v_c)` | `∂L/∂(v·u⁻ᵢ) = σ(v·u⁻ᵢ)`，负样本得分越接近 0，误差越接近 0；形状 `(k,)` |
| `grad_center = pos_err * u_pos + neg_errs @ u_negs` | `∂L/∂v = (σ⁺−1)·u⁺ + Σᵢ σ⁻ᵢ·u⁻ᵢ`；`(k,) @ (k, d) → (d,)` 一次完成加权求和 |
| `W_prime[ctx_idx] -= lr * pos_err * v_c` | `∂L/∂u⁺ = (σ⁺−1)·v`，把正上下文向量拉向中心向量 |
| `W_prime[neg_idx] -= lr * neg_errs[i] * v_c` | `∂L/∂u⁻ᵢ = σ⁻ᵢ·v`，把负样本向量推离中心向量 |
| `W[c_idx] -= lr * grad_center` | 最后更新中心向量 |

**为什么要"先算梯度、最后更新中心向量"**——这里藏着 NumPy 的视图机制：

- `W[c_idx]`、`W_prime[ctx_idx]` 用**单个整数**索引，返回的是原数组那一行的**视图**（不拷贝）。之后原数组被原地修改，`v_c`、`u_pos` 看到的也是新值。
- `W_prime[neg_indices]` 用**列表**索引（花式索引），返回的是**副本**。
- 因此：`grad_center` 必须在更新 `W_prime[ctx_idx]` 之前算好（否则会用到新的 `u_pos`）；`W[c_idx]` 必须最后更新（否则上下文和负样本的更新会用到新的 `v_c`）。现在的顺序保证了三处更新都基于同一组旧参数。

其他细节：

- 讲义版本用 `for` 循环累加负样本梯度，代码版本用 `neg_errs @ u_negs` 向量化，结果相同、更快。讲义版本里还有一行 `W[context_idx] = W[context_idx]`，是没有任何作用的自赋值，代码版本已删掉。
- 如果同一个负样本下标被采到两次，`for` 循环会对它更新两次，这和"把它当两个负样本"在数学上一致。
- ⚠️ 简化：学习率固定（原版会线性衰减）；没有对 `W'` 和 `W` 做任何正则化。

### 3.5 `train`：训练循环与负样本采样

```python
def train(docs, dim=16, window=2, k_neg=5, epochs=200, lr=0.05, seed=0):
    vocab = build_vocab(docs)
    vocab_size = len(vocab)
    W, W_prime = init_embeddings(vocab_size, dim, seed)
    pairs = skipgram_pairs(docs, window=window)
    rng = np.random.default_rng(seed)

    for epoch in range(epochs):
        rng.shuffle(pairs)
        for center, context in pairs:
            c_idx = vocab[center]
            ctx_idx = vocab[context]
            neg_candidates = rng.integers(0, vocab_size, size=k_neg * 2)
            negs = [int(n) for n in neg_candidates if n != ctx_idx and n != c_idx][:k_neg]
            train_pair(W, W_prime, c_idx, ctx_idx, negs, lr)
    return vocab, W
```

- `rng.shuffle(pairs)` 每个 epoch 原地打乱样本顺序，避免模型按固定顺序"记住"语料，这是 SGD 的标准做法。
- 负样本采样：先采 `2k` 个候选，过滤掉"恰好等于正上下文或中心词"的下标，再截取前 k 个。多采一倍是为了过滤后**大概率**仍凑够 k 个（讲义版本只采 k 个，过滤后可能不足）。即便如此，也不保证一定是 k 个——这无伤大雅。
- `int(n)` 把 NumPy 整数转成 Python `int`，让 `negs` 是干净的 Python 列表。
- ⚠️ 简化：这里是**均匀**采样。原论文按 unigram 频率的 0.75 次方采样（测验 Q10 有实现），能让高频词更常被当作负样本、同时不至于完全淹没低频词。
- ⚠️ 返回值只有 `vocab, W`，`W'` 被丢弃——正是讲义说的"训练完扔掉输出层"。
- 计算量：120 个 epoch × 2800 对 × 每对一次 `train_pair`，约 34 万次 Python 函数调用，所以纯 Python 循环要跑十几秒。gensim 用 C/Cython 实现同样的循环，快几个数量级。

### 3.6 `nearest`：余弦近邻

```python
def nearest(vocab, W, target_vec, topk=5, exclude=None):
    exclude = exclude or set()
    inv_vocab = {i: w for w, i in vocab.items()}
    norms = np.linalg.norm(W, axis=1, keepdims=True) + 1e-9
    W_norm = W / norms
    target = target_vec / (np.linalg.norm(target_vec) + 1e-9)
    sims = W_norm @ target
    order = np.argsort(-sims)
    out = []
    for i in order:
        if int(i) in exclude:
            continue
        out.append((inv_vocab[int(i)], float(sims[i])))
        if len(out) == topk:
            break
    return out
```

- `exclude = exclude or set()`：经典的**可变默认参数**防御写法。如果签名直接写 `exclude=set()`，这个集合会在所有调用之间共享。
- `inv_vocab`：字典推导式把 `{词: 下标}` 反转成 `{下标: 词}`。
- `np.linalg.norm(W, axis=1, keepdims=True)`：对每一行求 L2 范数，`keepdims=True` 让结果保持 `(V, 1)` 的形状，这样 `W / norms` 可以按行**广播**。`+ 1e-9` 防止零向量除零。
- `W_norm @ target`：一次矩阵-向量乘法算出目标与所有词的余弦相似度，形状 `(V,)`。
- `np.argsort(-sims)`：`argsort` 默认升序，取负号变成降序。
- `exclude` 用来排除查询词本身（否则 top-1 永远是自己，相似度 1.0）；在类比任务中还要排除三个输入词。

### 3.7 `main`：玩具语料与输出

```python
    corpus = [
        "the cat sat on the mat",
        "the dog sat on the rug",
        "a cat chased a mouse",
        # ...
        "cats chase mice",
        "dogs chase squirrels",
    ] * 20

    docs = [tokenize(s) for s in corpus]
    vocab, W = train(docs, dim=16, window=2, k_neg=5, epochs=120, lr=0.05, seed=42)
```

- 语料刻意构造成**成对平行**的句子：`cat/dog`、`kitten/puppy`、`mat/rug` 出现在几乎相同的上下文中，好让分布式假设"一眼可见"。
- `* 20` 把 10 句话重复 20 次，相当于给更多训练步数；但不增加任何新信息。
- `f"  {w:12s} {s:.3f}"`：`12s` 让单词左对齐、占 12 个字符宽，便于对齐输出。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 NumPy + Python 循环 | 每一步梯度都看得见 | 十几秒才训完 2800 对 × 120 轮；生产用 gensim（C 实现、多线程） |
| 负采样而不是完整 softmax | 每步代价从 O(V·d) 降到 O(k·d) | 只是对 softmax 的近似目标，得不到归一化概率 |
| 均匀负采样 | 实现最简单 | 原论文用 unigram^0.75；均匀采样让稀有词被过度当作负样本 |
| 固定学习率 0.05 | 简洁 | 原版线性衰减学习率，收敛更稳 |
| 不做高频词下采样 | 简洁 | `a`、`the` 主导训练，出现 `chased` 的近邻是 `a` 这样的现象 |
| 只返回 `W` | 与讲义"保留中心词表"一致 | 也可以用 `W + W'` 或平均，有时效果更好 |
| 向量化 `neg_errs @ u_negs` | 比 `for` 循环快、写法更接近公式 | 需要理解形状与视图 / 副本 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表推导式 | `[t.lower() for t in TOKEN_RE.findall(text)]` | 一行生成列表 |
| 带过滤与切片的推导式 | `[int(n) for n in neg_candidates if n != ctx_idx and n != c_idx][:k_neg]` | 先过滤再截取前 k 个 |
| 列表乘法 | `[...] * 20` | 把列表重复 20 次（元素是字符串，共享无副作用） |
| 元组列表与解包 | `pairs.append((center, doc[j]))`；`for center, context in pairs` | 存储与拆解成对数据 |
| `enumerate` | `for i, center in enumerate(doc)` | 同时拿到下标和元素 |
| `range` 起止 + `max/min` 截断 | `range(max(0, i - window), min(len(doc), i + window + 1))` | 处理窗口越界 |
| 字典推导式 | `{i: w for w, i in vocab.items()}` | 反转字典 |
| 可变默认参数防御 | `exclude = exclude or set()` | 默认值写 `None`，函数内再创建新集合 |
| NumPy 随机数生成器 | `np.random.default_rng(seed)`、`rng.normal`、`rng.integers`、`rng.shuffle` | 新式 API，可复现 |
| `@` 矩阵乘法 | `v_c @ u_pos`、`neg_errs @ u_negs`、`W_norm @ target` | 向量点积、矩阵-向量乘 |
| 增强赋值原地修改 | `W[c_idx] -= lr * grad_center` | 直接修改数组内容，函数无需返回 |
| 视图 vs 副本 | `W[c_idx]`（视图）vs `W_prime[neg_indices]`（副本） | 整数索引得到视图，列表索引得到副本 |
| 广播与 `keepdims` | `W / norms`，`norms` 形状 `(V, 1)` | 按行除以各自的范数 |
| `np.argsort` | `np.argsort(-sims)` | 返回排序后的下标；取负实现降序 |
| `np.clip` | `np.clip(x, -20, 20)` | 截断到区间，防止 `exp` 溢出 |
| f-string 宽度格式 | `f"{w:12s} {s:.3f}"` | 固定宽度对齐 + 保留 3 位小数 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13 + NumPy 2.5，耗时约 13.5 秒）的完整输出：

```text
nearest to cat:
  dog          0.988
  mouse        0.750
  mat          0.622
  rug          0.598

nearest to dog:
  cat          0.988
  mouse        0.703
  mat          0.566
  rug          0.537

nearest to sat:
  rug          0.795
  mat          0.762
  on           0.616
  the          0.594

nearest to chased:
  a            0.977
  mouse        0.823
  cat          0.473
  dog          0.393
```

逐段解读：

- **cat ↔ dog = 0.988**：两者出现在几乎相同的句子模板里（`the _ sat on the …`、`a _ chased a …`），上下文分布相近，于是向量几乎重合。这正是分布式假设的直接体现，也满足讲义练习 1"`dog` 在 `cat` 的前 3 近邻里"的要求。
- **cat 的第二近邻是 mouse（0.750）**：`mouse` 也出现在 `a cat chased a mouse` 这种句式中，与 `cat` 共享上下文 `a`、`chased`。
- **sat 的近邻是 rug、mat、on、the**：这些都是在 `sat` 周围出现的词，而不是"意思相近"的 `slept`。补充实测：`cos(sat, slept)` 只有约 0.45。在这个极小的语料上，模型学到的更多是"谁和谁一起出现"。
- **chased 的近邻是冠词 a（0.977）**：语料中 `a` 只出现在 `a cat chased a mouse`、`a dog chased a cat` 两句里，它的上下文（cat、dog、mouse、chased）和 `chased` 的上下文（a、cat、dog、mouse）几乎一样。这说明"上下文相似 ≠ 语义相似"，也是没做高频词下采样的后果（详见测验 Q11）。

补充实测（同样设置）：`cos(kitten, puppy) ≈ 0.994`，而 `cos(cat, cats) ≈ 0.20`——Word2Vec 把 `cat` 与 `cats` 当成毫不相干的两个符号，引出下一节 fastText 的字符 n-gram。

---

## 7. 动手改一改

1. **（易）加入类比函数**：按讲义实现 `analogy(vocab, W, a, b, c)`，在本语料上试试 `analogy(vocab, W, "cat", "kitten", "dog")` 是否能得到 `puppy`。
2. **（易）看看 `W'`**：让 `train` 同时返回 `W_prime`，比较用 `W`、`W'`、`(W + W')/2` 做近邻查询的差异。
3. **（中）unigram^0.75 负采样**：用 `rng.choice(vocab_size, size=..., p=probs)` 替换均匀采样，观察 `chased` 的近邻是否变化。
4. **（中）高频词下采样**（讲义练习 2）：以概率 `1 − √(t/f(w))` 丢弃高频词所在的样本对，比较 `a`、`the` 的影响。
5. **（中）记录损失**：在 `train_pair` 中返回当前损失 `−log σ(v·u⁺) − Σ log σ(−v·u⁻)`，每个 epoch 打印平均值，画出收敛曲线。
6. **（难）用 gensim 对照**：如果环境中有 gensim，用 `Word2Vec(docs, vector_size=16, window=2, sg=1, negative=5, epochs=120, min_count=1)` 训练同一语料，对比近邻结果和训练速度。

---

## 8. 常见坑

- **视图被提前修改**：`W[c_idx]`、`W_prime[ctx_idx]` 是视图。调整更新顺序（比如先更新 `W_prime[ctx_idx]` 再算 `grad_center`）会悄悄得到错误梯度，而且不会报错。
- **把梯度符号写反**：`pos_err` 是 `σ − 1`（负数），减去 `lr * pos_err * v_c` 等于**加上**一点 `v_c`，正样本被拉近；写成 `1 − σ` 就会把正样本推远。
- **`sigmoid` 不截断**：`np.exp` 溢出产生 `inf` 和警告，极端情况下出现 `nan` 并污染整张表。
- **近邻不排除查询词**：top-1 永远是自己（相似度 1.0）；类比时不排除三个输入词，top-1 常是 `b` 本身。
- **把玩具语料的结果当真**：语料只有 10 种句子，模型学到的是句式而不是语义；真实效果需要数百万以上的 token。
- **可变默认参数**：如果把 `exclude=None` 改成 `exclude=set()` 并在函数里往里加元素，下次调用会带着上次的残留。
