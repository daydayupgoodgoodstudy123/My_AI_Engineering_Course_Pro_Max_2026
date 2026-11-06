# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 15 节 主题建模 — LDA 和 BERTopic ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`random`、`re`）；讲义里的 scikit-learn LDA 和 BERTopic 本文件没有用到

---

## 1. 这份代码在考察什么

讲义用 scikit-learn 和 BERTopic 调库；这份代码则**用不到 100 行纯 Python 从零实现 collapsed Gibbs 采样版 LDA**，让你看清"文档是主题的混合、主题是词的分布"到底是怎么被学出来的：

1. **三个计数表**：`ndt`（文档-主题）、`ntw`（主题-词）、`nt`（主题总词数）——LDA 的全部"参数"都藏在这三张表里。
2. **Gibbs 采样的核心公式**：`p(z=k) ∝ (n_dk + α)·(n_kw + β)/(n_k + Vβ)`，以及"先减、采样、再加"的更新顺序。
3. **从计数到分布**：`doc_topic = (n_dk + α)/(n_d + Kα)`，对应讲义的 `(n_docs, n_topics)` 矩阵，每行和为 1。
4. **输入校验与可复现性**：参数检查、`random.Random(seed)` 固定随机数。
5. **（运行后的真实教训）**：9 篇短文档几乎没有共享词，LDA 只能靠 `the / new / for / cut` 这类词来分组——这就是讲义说的"短文本上 LDA 连贯性崩溃"和"junk topic 吸收停用词"。

> 一句话：**LDA 不懂语义，只懂"哪些词经常一起出现在同一篇文档里"**；跑完这份代码，你会对这句话有切身体会。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SHORT_ALLOWLIST` | 常量 | 允许保留的短词（`ai`、`ml`、`s`、`p` 等） | 分词规则 |
| `tokenize(text)` | 函数 | 小写、正则切词，丢掉长度 ≤ 2 且非数字、不在白名单中的词 | 预处理 |
| `collapsed_gibbs_lda(docs, n_topics, n_iters, alpha, beta, seed)` | 函数 | 参数校验 → 建词表 → 随机初始化 → Gibbs 迭代 → 输出 top 词与 `doc_topic` | LDA 推断 |
| `main()` | 函数 | 9 篇（金融 / AI / 政治各 3 篇）短文档，3 个主题、300 轮，打印主题词和文档混合 | 演示 |

数据流：`docs_raw` →（`tokenize`）→ `docs`（词列表的列表）→ `collapsed_gibbs_lda` 内部再映射成整数 id（`indexed`）→ 迭代更新 `z` 与三张计数表 → 输出 `topics`（每主题 top-8 词）和 `doc_topic`（每篇文档的主题分布）。

---

## 3. 逐段精讲

### 3.1 分词：长度过滤 + 白名单

```python
SHORT_ALLOWLIST = {"ai", "ml", "nn", "s", "p", "pr"}


def tokenize(text):
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 2 or t.isdigit() or t in SHORT_ALLOWLIST]
```

- 用"长度 > 2"粗略过滤掉 `a`、`on`、`as`、`in` 这类短虚词；数字（如 `500`）保留；白名单保留有意义的短词 `ai`、`ml`，以及为 "s p 500" 准备的 `s`、`p`。
- 白名单用 `set` 是为了 O(1) 的 `in` 查询。
- ⚠️ **这不是停用词过滤**：`the`、`for`、`new`、`after`、`with` 都长于 2 个字母，全部被保留。讲义 sklearn 示例用的是 `stop_words="english"` 加 `min_df/max_df`，这里没有，结果见第 6 节。
- ⚠️ `s` 在白名单里，所以所有格 `"Google's"` 也会产生一个 `s`。

### 3.2 参数校验：让错误早点暴露

```python
    if not isinstance(n_topics, int) or n_topics <= 0:
        raise ValueError(f"n_topics must be a positive int, got {n_topics!r}")
    if alpha <= 0 or beta <= 0:
        raise ValueError(f"alpha and beta must be positive, got alpha={alpha}, beta={beta}")
    if not docs:
        raise ValueError("docs must not be empty")
```

- `n_topics` 必须是正整数：传 `3.0` 也会被拒绝（`isinstance(3.0, int)` 为 `False`），因为后面要 `range(n_topics)`。
- `alpha`、`beta` 必须为正：它们是 Dirichlet 先验，也是公式里防止概率为 0 的平滑项；为 0 时，一个主题里没出现过的词概率恒为 0，采样可能卡死。
- `{n_topics!r}` 用 `repr` 打印，能区分 `3` 和 `'3'`，错误信息更清楚。
- 后面还有一个 `if V == 0` 检查：比如 `[[]]` 这种全是空文档的输入，会报 "empty vocabulary"。

### 3.3 建词表与随机初始化

```python
    rng = random.Random(seed)
    vocab = {}
    for doc in docs:
        for w in doc:
            if w not in vocab:
                vocab[w] = len(vocab)
    V = len(vocab)
    D = len(docs)
    # ...
    indexed = [[vocab[w] for w in doc] for doc in docs]

    z = [[rng.randint(0, n_topics - 1) for _ in doc] for doc in indexed]
```

- `vocab[w] = len(vocab)`：每遇到一个新词，就给它下一个整数 id。这是建词表的经典一行写法。
- `indexed` 把每篇文档从"词列表"变成"id 列表"，后面计数表可以直接用 id 做下标。
- `z[d][i]` 是**第 d 篇文档第 i 个 token 当前被分配的主题**，这是 Gibbs 采样真正在采的隐变量。初始化时完全随机。
- `random.Random(seed)` 创建**独立的随机数生成器**，不影响全局 `random` 模块，也保证相同 seed 结果完全可复现。
- ⚠️ `rng.randint(0, n_topics - 1)` 两端都包含，所以要写 `n_topics - 1`。

### 3.4 三张计数表

```python
    ndt = [[0] * n_topics for _ in range(D)]
    ntw = [[0] * V for _ in range(n_topics)]
    nt = [0] * n_topics

    for d in range(D):
        for i, w in enumerate(indexed[d]):
            t = z[d][i]
            ndt[d][t] += 1
            ntw[t][w] += 1
            nt[t] += 1
```

| 表 | 形状 | 含义 |
|----|------|------|
| `ndt[d][k]` | D × K | 文档 d 中被分给主题 k 的 token 数 |
| `ntw[k][w]` | K × V | 词 w 被分给主题 k 的次数（所有文档合计） |
| `nt[k]` | K | 主题 k 的 token 总数，等于 `sum(ntw[k])` |

- 必须写 `[[0] * n_topics for _ in range(D)]`，**不能**写 `[[0] * n_topics] * D`：后者的 D 行是同一个列表对象，改一行等于改所有行。
- 这三张表就是"collapsed"的含义：θ（文档主题分布）和 φ（主题词分布）被积分掉了，算法只需要维护计数。

### 3.5 Gibbs 采样主循环：先减、采样、再加

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
```

- **先减**：要采样的是"在其他所有 token 分配不变时，当前 token 属于哪个主题"，所以必须先把它自己从计数中拿掉，否则它会给原主题"投自己一票"。
- **公式的两项**：
  - `(ndt[d][k] + alpha)`：文档 d 已经有多少词在主题 k——"文档偏好"；
  - `(ntw[k][w] + beta) / (nt[k] + V * beta)`：主题 k 里词 w 占多大比例——"主题对这个词的偏好"。
  - 两者相乘：一个 token 倾向于去"本文档常用、且该主题也常用这个词"的主题。这就是 LDA 让共现的词聚到同一主题的机制。
- `probs` 没有归一化——下一步采样时乘以 `total` 即可，省掉一次除法。

```python
                total = sum(probs)
                r = rng.random() * total
                acc = 0.0
                new_t = 0
                for k, p in enumerate(probs):
                    acc += p
                    if r <= acc:
                        new_t = k
                        break

                z[d][i] = new_t
                ndt[d][new_t] += 1
                ntw[new_t][w] += 1
                nt[new_t] += 1
```

- **轮盘赌采样**（累积分布采样）：在 `[0, total)` 上随机取一个点 `r`，看它落在哪一段。第 k 段的长度正比于 `probs[k]`，所以被选中的概率正好是 `probs[k]/total`。
- 等价的标准库写法是 `rng.choices(range(n_topics), weights=probs)[0]`；手写是为了让你看清原理。
- **再加**：把三张表更新到新主题上，保持"计数表 = 当前 `z` 的统计"这一不变量。
- 复杂度：每个 token O(K)，一轮 O(N·K)，N 是总 token 数（本 demo 为 65），总计 O(n_iters·N·K)。
- ⚠️ 没有 burn-in（预热丢弃）也没有多次采样取平均，直接用最后一轮的状态作为结果——教学足够，严谨的实现会在预热后多次取样平均。

### 3.6 输出：top 词与文档主题分布

```python
    inv_vocab = {i: w for w, i in vocab.items()}
    topics = []
    for k in range(n_topics):
        top_ids = sorted(range(V), key=lambda i: -ntw[k][i])[:8]
        topics.append([inv_vocab[i] for i in top_ids])
    doc_topic = []
    for d in range(D):
        total = sum(ndt[d]) + n_topics * alpha
        doc_topic.append([(ndt[d][k] + alpha) / total for k in range(n_topics)])

    return topics, doc_topic
```

- `inv_vocab` 用字典推导式把 `词 → id` 反转成 `id → 词`。
- `sorted(range(V), key=lambda i: -ntw[k][i])[:8]`：按计数**降序**排列所有词 id，取前 8 个。取负号是降序的小技巧（也可以 `reverse=True`）。计数相同时 `sorted` 是稳定排序，保持原来的 id 顺序（即词首次出现的顺序）。
- `doc_topic` 的公式就是讲义 `doc_topic` 矩阵的后验均值估计：分子加 α、分母加 K·α，保证每行和为 1，并且没分到词的主题也有一个小的非零概率（这就是输出里 `0.01` 的来源：一篇 8 个 token 的文档，没分到词的主题概率为 `0.1 / (8 + 0.3) ≈ 0.01`）。
- ⚠️ 没有返回讲义里的 `topic_word` 矩阵；补上它只需要 `(ntw[k][w] + beta) / (nt[k] + V * beta)`，见测验 Q11。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| collapsed Gibbs 采样 | 公式简单、逻辑透明，适合从零实现 | 慢、只能单线程；sklearn / gensim 用变分贝叶斯（在线学习），大规模用 SparseLDA / LightLDA |
| 纯 Python 嵌套列表 | 零依赖、能看清每个计数 | 比 NumPy / C 实现慢几个数量级 |
| α=0.1、β=0.01 | 小先验鼓励稀疏：文档只用少数主题、主题只用少数词 | 需要按语料调；可用超参优化自动学 α |
| 长度过滤代替停用词表 | 代码短 | `the / for / new` 留下来形成垃圾主题；生产用停用词表 + `min_df/max_df` |
| 用最后一轮的 `z` 作为结果 | 简单 | 应先 burn-in，再多次采样取平均，降低随机性 |
| 固定 seed 的独立 `Random` | 结果可复现、不污染全局随机状态 | 不同 seed 结果可能差别很大，小语料尤其明显 |
| 严格的参数校验 | 让错误在入口处暴露，信息清晰 | — |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `set` 字面量 | `{"ai", "ml", "nn", "s", "p", "pr"}` | 集合，`in` 查询 O(1) |
| 列表推导式 + 条件 | `[t for t in tokens if len(t) > 2 or t.isdigit() or t in SHORT_ALLOWLIST]` | 一行完成过滤 |
| `str.isdigit()` | `t.isdigit()` | 判断是否全为数字字符 |
| `isinstance` | `isinstance(n_topics, int)` | 运行时类型检查 |
| `raise ValueError` + f-string `!r` | `f"... got {n_topics!r}"` | 抛出带上下文的异常；`!r` 调用 `repr()` |
| `random.Random(seed)` | `rng = random.Random(seed)` | 独立、可复现的随机数生成器 |
| `rng.randint` / `rng.random` | `rng.randint(0, n_topics - 1)`、`rng.random()` | 闭区间整数 / `[0, 1)` 浮点 |
| 字典建索引 | `vocab[w] = len(vocab)` | 新词获得下一个整数 id |
| 嵌套列表推导式 | `[[vocab[w] for w in doc] for doc in docs]` | 对二维结构逐元素映射 |
| 列表乘法的陷阱 | `[[0] * n_topics for _ in range(D)]` | 必须用推导式生成独立的行，避免共享引用 |
| `_` 占位变量 | `for _ in range(n_iters)` | 循环变量用不到时的惯例写法 |
| `enumerate` | `for i, w in enumerate(indexed[d])` | 同时拿到位置和元素 |
| `break` | `if r <= acc: ... break` | 找到落点后立即退出循环 |
| 字典推导式 + `items()` | `{i: w for w, i in vocab.items()}` | 反转字典 |
| `sorted` + `lambda` | `sorted(range(V), key=lambda i: -ntw[k][i])[:8]` | 按自定义键排序；负号实现降序 |
| `zip` | `for doc_raw, mix in zip(docs_raw, doc_topic)` | 并行遍历两个列表 |
| 字符串切片 | `doc_raw[:50]` | 只打印前 50 个字符 |
| `str.join` | `', '.join(words)` | 用分隔符拼接字符串列表 |
| 多返回值 | `return topics, doc_topic` / `topics, doc_topic = ...` | 实际返回一个元组，再解包 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13，约 0.05 秒）输出：

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

语料的本意是金融（前 3 篇）、AI（中 3 篇）、政治（后 3 篇），但结果**没有**按这个分：

- **topic 0 的头两个词是 `the`、`new`**：分到它的是 openai（含 new）、senate（含 the）、president（含 the、new），外加 the s p 500 的大部分（含 the、new）。
- **topic 1 的头两个词是 `cut`、`for`**：分到它的是 stocks（含 cut）、chip makers（含 for）、congress（含 cut、for）。
- **topic 2** 收留了与其他文档没有任何共享词的 bond 和 deep learning。

原因很简单：分词后 58 个不同的词里，**只有 `the`(4 篇)、`new`(3 篇)、`cut`(2 篇)、`for`(2 篇) 出现在不止一篇文档里**。LDA 的唯一信号就是共现，所以分组完全由这 4 个词决定。`stocks` 和 `bond` 在人看来都是金融，但对 LDA 来说只是两个毫不相干的符号。

- 每行和为 1（如 `0.13 + 0.86 + 0.01 = 1.00`）；`0.01` 是 α 平滑带来的下限。
- the s p 500 是 `[0.66, 0.01, 0.33]` 的真正混合：它 9 个 token 中约 6 个（`the / new / s / p / earnings / reports`）在主题 0，约 3 个（`500 / hit / high`）在主题 2：`(6+0.1)/(9+0.3) ≈ 0.66`。

这个"失败"其实是本节最有价值的输出：它直接演示了讲义和 skill 里的两条告诫——**LDA 在很短的文本上连贯性崩溃**，以及**LDA 会出现吸收停用词和高频词的 junk topic**。另外，去掉停用词后再跑（已实测），因为语料里几乎不剩共享词，不同 seed 给出的分组各不相同——说明问题的根本在于语料太小太稀疏，而不只是停用词。

---

## 7. 动手改一改

1. **加停用词表**：在 `tokenize` 里过滤 `the / for / new / after / with`，换 3 个不同的 `seed` 跑，观察结果是否稳定。
2. **扩充语料**：每个主题写 10 篇以上、反复使用同一批领域词（`stocks / bonds / fed / rates`、`model / training / gpu`、`senate / bill / vote`），再看三个主题能否分开。
3. **补 `topic_word`**：返回 `(ntw[k][w] + beta) / (nt[k] + V * beta)` 矩阵，验证每行和为 1；再写 `topic_diversity(topics)`。
4. **调先验**：把 `alpha` 改成 5.0，观察文档混合变得接近均匀（如 `[0.30, 0.35, 0.35]`）；把 `beta` 调大，观察主题词变得更"平均"。
5. **burn-in + 平均**：前 200 轮丢弃，后 100 轮每 10 轮记录一次 `ndt`，取平均后再算 `doc_topic`，比较稳定性。
6. **对照 sklearn**（如本地已安装 scikit-learn）：用讲义 Step 1 的 `fit_lda` 在同样的 9 篇文档上跑（注意 `min_df=2` 会把大部分词过滤掉——想想为什么，以及该怎么调）。

---

## 8. 常见坑

- **用 `[[0] * K] * D` 初始化二维表**：所有行共享同一个列表，计数全乱。
- **采样前忘了减去当前 token 的计数**：链条偏向原主题，结果不再是正确的后验采样。
- **把长度过滤当作停用词过滤**：`the / for / new` 会把主题污染成"垃圾主题"。
- **在极短、极小的语料上期待 LDA 分出语义主题**：没有共现就没有信号，这种场景用 BERTopic 或直接让 LLM 归类。
- **把 TF-IDF 矩阵喂给 LDA**：sklearn 不会报错，但违背了模型的计数假设。
- **只看一个 seed 的结果下结论**：小语料上不同 seed 差异巨大，至少多跑几次比较。
