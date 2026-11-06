# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 14 节 信息检索与搜索 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`re`、`collections.Counter`）；讲义中的真 dense 检索与 cross-encoder 需要 `sentence-transformers`，本文件没有用到

---

## 1. 这份代码在考察什么

讲义的检索栈是"BM25 + dense + RRF + cross-encoder 重排"四层。这份代码把**不需要下载模型的两层**完整写出来，另外一层用玩具代替：

1. **BM25 从零实现**：df 统计、带 +1 的 IDF、`k1` 词频饱和、`b` 长度归一化、top-k 排序——这是面试最常被要求手写的检索算法。
2. **RRF 融合**：只用名次、不用分数，把两个量纲不同的排名列表合并。
3. **"形状演示"用的假 dense**：`fake_dense_rank` 用 Jaccard + 子串扩展模拟一个"会给不同排名的第二路检索器"，让 RRF 有东西可融合。它**不是语义检索**。
4. **讲义开头的难题**：查询 "what happens if someone lies to get money" 与目标法条 "Section 420 ... cheating and dishonest inducement" 没有共同词汇——跑完你会亲眼看到纯词面方法为什么找不到它。

> 一句话：**BM25 和 RRF 是可以闭着眼睛手写的基本功；dense 和 rerank 是"换上模型"的部分，接口形状在这里已经搭好了。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tokenize(text)` | 函数 | 小写 + 正则抽 `[a-z0-9]+` | 分词 |
| `BM25.__init__` | 方法 | 分词全部文档，统计平均长度 `avg_dl` 与文档频率 `df` | 索引构建 |
| `BM25.idf(term)` | 方法 | `log(1 + (N - n + 0.5)/(n + 0.5))` | 逆文档频率 |
| `BM25.score(query, doc_idx)` | 方法 | 对单个文档打 BM25 分 | TF 饱和 + 长度归一化 |
| `BM25.rank(query, top_k)` | 方法 | 全量打分、排序、截断 | 稀疏检索 |
| `reciprocal_rank_fusion(rankings, k)` | 函数 | `Σ 1/(k + rank + 1)` 融合多个排名 | RRF |
| `fake_dense_rank(query, corpus, top_k)` | 函数 | Jaccard + 子串"扩展"打分 | 占位的第二路检索器 |
| `main()` | 函数 | 7 句语料、1 个查询，依次打印 BM25 / fake-dense / RRF 结果 | — |

数据流：`main` 构建 `BM25(corpus)` → `bm25.rank` 得到 sparse 列表；`fake_dense_rank` 得到 dense 列表；两者都是 `[(score, doc_idx), ...]` 格式，交给 `reciprocal_rank_fusion` 合并。**统一的 `(score, idx)` 接口**让任何检索器都能插进 RRF。

---

## 3. 逐段精讲

### 3.1 构建索引：`BM25.__init__`

```python
class BM25:
    def __init__(self, corpus, k1=1.5, b=0.75):
        if not corpus:
            raise ValueError("BM25 corpus must not be empty")
        self.corpus = [tokenize(d) for d in corpus]
        self.k1 = k1
        self.b = b
        self.n_docs = len(self.corpus)
        self.avg_dl = sum(len(d) for d in self.corpus) / self.n_docs
        self.df = Counter()
        for doc in self.corpus:
            for term in set(doc):
                self.df[term] += 1
```

- **空语料检查**放在最前面：否则 `avg_dl` 会除以 0。这是"在构造函数里校验输入"的好习惯。
- `self.corpus` 存的是**分词后的列表**，查询时就不必重复分词。
- `avg_dl`（average document length）是长度归一化的基准。本 demo 中 7 篇文档长度为 `[10, 9, 11, 9, 12, 13, 12]`，`avg_dl ≈ 10.86`。
- `df[term]` = 包含该词的**文档数**。`for term in set(doc)` 的 `set` 很关键：一篇文档里出现 2 次 `to` 也只算 1 篇。忘了 `set` 就会把 df 算成"总出现次数"，IDF 全部偏小。
- `Counter()` 访问不存在的键返回 0，所以 `self.df[term] += 1` 无需先判断键是否存在。

### 3.2 IDF：为什么要 `1 +`

```python
    def idf(self, term):
        n = self.df.get(term, 0)
        return math.log(1 + (self.n_docs - n + 0.5) / (n + 0.5))
```

- 经典 Robertson–Spärck Jones IDF 是 `log((N - n + 0.5)/(n + 0.5))`，当一个词出现在**超过一半**的文档中时，括号里 < 1，IDF 变**负数**——命中这个词反而扣分。
- 加 1 之后括号恒 > 1，IDF 恒为正，这也是 Lucene / Elasticsearch 采用的写法。
- `+0.5` 是平滑，避免 `n = 0` 或 `n = N` 时出现除零或 log(0)。
- 本 demo 的几个值（N=7）：

| 词 | df | IDF |
|----|----|-----|
| `someone` / `money` | 1 | 1.674 |
| `to` / `cheating` | 2 | 1.163 |
| `the` | 4 | 0.575 |

越稀有的词 IDF 越高。

### 3.3 打分：`BM25.score`

```python
    def score(self, query, doc_idx):
        q_tokens = tokenize(query)
        doc = self.corpus[doc_idx]
        dl = len(doc)
        freq = Counter(doc)
        total = 0.0
        for term in q_tokens:
            f = freq.get(term, 0)
            if f == 0:
                continue
            num = f * (self.k1 + 1)
            den = f + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
            total += self.idf(term) * num / den
        return total
```

逐项对应公式 `IDF(t) · f·(k1+1) / (f + k1·(1 - b + b·dl/avgdl))`：

- **`num/den` 的饱和**：`f=1` 时约等于 1（长度为平均值时恰好为 1）；`f→∞` 时趋近 `k1+1 = 2.5`。词频收益递减，防止关键词堆砌。
- **长度项** `1 - b + b·dl/avg_dl`：文档比平均长 ⇒ 分母变大 ⇒ 分数打折；`b=0` 时长度完全不起作用。
- `if f == 0: continue` 跳过未命中的词，也省掉一次 IDF 计算。
- 手算 Fraud 文档（`to` 出现 2 次，dl=13）：`num = 2×2.5 = 5`，`den = 2 + 1.5×(0.25 + 0.75×13/10.86) ≈ 3.72`，`5/3.72 × 1.163 ≈ 1.563`，与运行输出一致。
- ⚠️ `q_tokens` 没有去重：查询 `"money money"` 的分数是 `"money"` 的 2 倍（实测 3.197 vs 1.598）。
- ⚠️ **每次调用都重新 `Counter(doc)`**：对 N 篇文档打分是 O(N·L)。生产实现会在建索引时预存每篇文档的词频，并用**倒排索引**（词 → 包含它的文档列表）只访问命中的文档——这才是讲义所说"百万文档 sub-10ms"的来源。

### 3.4 排名：`BM25.rank`

```python
    def rank(self, query, top_k=10):
        scored = [(self.score(query, i), i) for i in range(self.n_docs)]
        scored.sort(reverse=True)
        return scored[:top_k]
```

- 返回 `(分数, 文档下标)`，按分数降序。分数相同时比较下标，**下标大的排前面**（元组字典序 + reverse）。
- ⚠️ **零分文档也会被返回**。demo 中只有 2 篇文档得分 > 0，但 `top_k=5` 会补上 3 篇零分文档，它们随后会在 RRF 中拿到分数（见第 6 节）。生产代码应过滤 `score > 0`，或者只从倒排索引命中的文档中取。

### 3.5 RRF：`reciprocal_rank_fusion`

```python
def reciprocal_rank_fusion(rankings, k=60):
    scores = {}
    for ranking in rankings:
        for rank, (_, doc_idx) in enumerate(ranking):
            scores[doc_idx] = scores.get(doc_idx, 0.0) + 1.0 / (k + rank + 1)
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(score, doc_idx) for doc_idx, score in fused]
```

- `for rank, (_, doc_idx) in enumerate(ranking)`：**嵌套解包**——`enumerate` 给出 `(rank, (score, doc_idx))`，用 `_` 丢掉原始分数。这一行就体现了 RRF 的本质：**分数根本不用**。
- `rank` 从 0 开始，所以公式写 `k + rank + 1`，等价于论文的 `1/(k + 名次)`（名次从 1 开始）。
- `scores.get(doc_idx, 0.0) + ...` 实现"没见过就从 0 开始累加"。
- `sorted(..., key=lambda x: x[1], reverse=True)` 按累计分数降序；最后把 `(doc_idx, score)` 翻转成 `(score, doc_idx)`，与输入格式保持一致，因此 RRF 的输出还能再作为另一次 RRF 的输入。
- `k=60` 越大，名次差异越被压平；越小，头部名次越占主导。

### 3.6 占位的第二路：`fake_dense_rank`

```python
def fake_dense_rank(query, corpus, top_k=5):
    q_tokens = set(tokenize(query))
    scored = []
    for i, d in enumerate(corpus):
        d_tokens = set(tokenize(d))
        if not d_tokens or not q_tokens:
            scored.append((0.0, i))
            continue
        jaccard = len(q_tokens & d_tokens) / len(q_tokens | d_tokens)
        expansion = 0.0
        for qt in q_tokens:
            for dt in d_tokens:
                if qt != dt and min(len(qt), len(dt)) >= 4 and (qt in dt or dt in qt):
                    expansion += 0.15
        scored.append((jaccard + expansion, i))
    scored.sort(reverse=True)
    return scored[:top_k]
```

- **Jaccard** = 交集大小 / 并集大小，衡量两个词集合的重叠程度；集合的 `&`、`|` 运算符直接给出交集和并集。
- **"扩展"项**：如果查询词和文档词互为子串（如 `cheat` 与 `cheating`），且两者长度都 ≥ 4，就加 0.15。这是对"相关但不完全相同的词"的一种极粗糙模拟，`>= 4` 是为了防止 `a`、`in` 这种短词到处匹配。例如查询 `"cheat money"` 时，Section 420 文档会靠 `cheat ⊂ cheating` 拿到 0.15 分（已实测）。
- 空集保护：`if not d_tokens or not q_tokens` 防止并集为空时除零。
- ⚠️ 本质上**仍然是词面匹配**，打印标题也老老实实写着 "shape demonstration"。它的作用只是提供一个"排序和 BM25 略有差别的第二路列表"，让 RRF 的流程跑得通。真正的 dense 检索要用讲义 Step 2 的 `SentenceTransformer` + `normalize_embeddings=True` + 点积。
- ⚠️ 双重循环是 O(|q|·|d|)，对玩具语料无所谓。

### 3.7 `main`：一个刻意选的难查询

```python
    query = "what happens if someone lies to get money"
```

语料里有三篇和"骗钱"相关：Section 420（法条，用词 cheating / dishonest inducement）、Fraud（定义，用词 deception / financial gain）、Cheating（用词 someone / money）。只有 Cheating 一篇和查询共享词汇（`someone`、`to`、`money`）。这个设计就是要让你看到：**词汇不匹配时，词面方法无论怎么融合都救不回来**，必须引入语义检索。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| BM25 全量打分，无倒排索引 | 代码短、和公式一一对应 | O(N·L)；生产用 Elasticsearch / OpenSearch / Lucene 的倒排索引 |
| IDF 加 1 | 保证 IDF 非负，避免常见词扣分 | 与经典公式数值不同，复现论文结果时要注意 |
| `k1=1.5, b=0.75` 默认 | 讲义称是经典推荐值，很少需要调 | 特殊语料（极短标题、极长文档）可在验证集上微调 |
| 统一 `(score, idx)` 接口 | 任何检索器都能直接喂给 RRF | — |
| RRF 只用名次 | 无需校准 BM25 与余弦的量纲 | 丢掉了分差信息；已知某路占优时可用加权融合 |
| 用 Jaccard 冒充 dense | 零依赖即可演示融合流程 | 不能捕获语义；真实系统用 sentence-transformers + FAISS / 向量库 |
| 不过滤零分文档 | 代码更简单 | 零分文档会进入 RRF 并按下标"排名"，污染结果；应过滤 `score > 0` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `raise` 抛异常 | `raise ValueError("BM25 corpus must not be empty")` | 输入非法时立即报错，信息清楚 |
| 类与默认参数 | `def __init__(self, corpus, k1=1.5, b=0.75)` | 构造时可覆盖超参：`BM25(corpus, k1=1.2)` |
| 生成器表达式 | `sum(len(d) for d in self.corpus)` | 不建中间列表直接求和 |
| `set` 去重与集合运算 | `set(doc)`、`q_tokens & d_tokens`、`q_tokens \| d_tokens` | `&` 交集、`\|` 并集 |
| `collections.Counter` | `self.df = Counter()`；`self.df[term] += 1` | 缺失键默认 0，适合计数 |
| `dict.get` 默认值 | `freq.get(term, 0)`、`scores.get(doc_idx, 0.0)` | 键不存在时返回默认值而不报错 |
| `math.log` | `math.log(1 + ...)` | 自然对数 |
| `continue` | `if f == 0: continue` | 跳过本轮循环 |
| `enumerate` | `for i, d in enumerate(corpus)` | 同时拿到下标和元素 |
| 嵌套解包 | `for rank, (_, doc_idx) in enumerate(ranking)` | 一次拆开两层结构；`_` 表示"不用的变量" |
| `lambda` 与 `sorted(key=...)` | `sorted(scores.items(), key=lambda x: x[1], reverse=True)` | 按字典的值排序 |
| `list.sort` vs `sorted` | `scored.sort(reverse=True)` / `sorted(...)` | 前者原地排序返回 `None`，后者返回新列表 |
| 元组比较 | `(score, idx)` 排序 | 先比分数，相同再比下标 |
| 字符串 `in` | `qt in dt` | 判断子串 |
| 链式比较条件 | `qt != dt and min(len(qt), len(dt)) >= 4 and (...)` | `and` 短路求值，前面不满足就不算后面 |
| f-string | `f"  {score:.3f}  {corpus[idx]}"`、`f"query: {query}\n"` | 保留 3 位小数；`\n` 换行 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13）输出：

```text
query: what happens if someone lies to get money

BM25 (sparse):
  4.307  Cheating someone to obtain money is a criminal offence in most jurisdictions.
  1.563  Fraud refers to wrongful or criminal deception intended to result in financial gain.
  0.000  Section 420 of the Indian Penal Code covers cheating and dishonest inducement.
  0.000  The first iPod was released by Apple in 2001.
  0.000  Android launched in 2008 as Google's mobile smartphone operating system.

fake-dense (shape demonstration):
  0.176  Cheating someone to obtain money is a criminal offence in most jurisdictions.
  0.053  Fraud refers to wrongful or criminal deception intended to result in financial gain.
  0.000  Section 420 of the Indian Penal Code covers cheating and dishonest inducement.
  0.000  The first iPod was released by Apple in 2001.
  0.000  Android launched in 2008 as Google's mobile smartphone operating system.

RRF fused:
  0.0328  Cheating someone to obtain money is a criminal offence in most jurisdictions.
  0.0323  Fraud refers to wrongful or criminal deception intended to result in financial gain.
  0.0317  Section 420 of the Indian Penal Code covers cheating and dishonest inducement.
  0.0312  The first iPod was released by Apple in 2001.
  0.0308  Android launched in 2008 as Google's mobile smartphone operating system.
```

- **BM25 第 1 名 4.307**：Cheating 文档命中 `someone`（IDF 1.674）、`to`（1.163）、`money`（1.674），dl=12 略长于平均，每项乘一个略小于 1 的系数。
- **BM25 第 2 名 1.563**：Fraud 文档只靠虚词 `to`（出现 2 次）得分——**这是"命中了但不相关"**，因为没有停用词过滤。
- **其余 0.000**：没有共同词。它们的先后（下标 4、3、2）纯粹由"分数相同比下标、下标大的在前"决定。
- **fake-dense**：Cheating 交集 3 / 并集 17 = 0.176；Fraud 交集 1 / 并集 19 = 0.053；没有任何子串扩展被触发。排序与 BM25 完全相同。
- **RRF**：两路排名一样，所以第 r 名得分都是 `2/(60+r)`：`2/61 = 0.0328`、`2/62 = 0.0323`、`2/63 = 0.0317`……
- ⚠️ **看起来 Section 420 排到了第 3，但它在两路中都是 0 分**——是并列零分的排序副作用叠加 RRF 对零分文档也加分造成的"假召回"。过滤掉零分文档后，RRF 只剩 Cheating 和 Fraud 两篇（已实测）。真正把 Section 420 找回来，需要讲义 Step 2 的语义 embedding 或 HyDE 这类查询扩展。

---

## 7. 动手改一改

1. **过滤零分**：在 `rank` 和 `fake_dense_rank` 里只保留 `score > 0` 的结果，重新观察 RRF 输出。
2. **调超参**：分别用 `BM25(corpus, k1=0)`、`BM25(corpus, b=0)`、`BM25(corpus, k1=100)` 跑同一个查询，解释 Cheating 文档分数的变化（`k1=0` 时为 4.511，即三个命中词 IDF 之和）。
3. **停用词**：给 `tokenize` 加一个停用词表（`what / if / to / the ...`），看 Fraud 文档还会不会因为 `to` 被召回。
4. **倒排索引**：在 `__init__` 中构建 `postings: dict[str, list[int]]` 和每篇文档的 `Counter`，`rank` 只对命中文档打分；用 1 万篇随机文档对比耗时。
5. **评估**：为 5 个查询标注相关文档，实现 `recall_at_k` 与 `mrr`，比较 BM25-only、fake-dense-only、RRF。
6. **换上真 dense**（需要本地已有 `sentence-transformers` 和模型缓存）：用讲义 Step 2 的 `dense_search` 替换 `fake_dense_rank`，看 Section 420 能否进入 top-3。

---

## 8. 常见坑

- **df 统计忘记 `set(doc)`**：把词的总出现次数当成文档频率，IDF 被系统性低估。
- **经典 IDF 出现负数**：高频词让分数下降，排序反直觉；用 `log(1 + ...)` 的变体。
- **把 BM25 分数和余弦直接相加**：量纲不同，结果被分数大的一方主导；用 RRF 或先归一化。
- **零分文档进入排名**：并列时按下标排序，在 RRF 和 MRR 中制造"假召回"。
- **把 `fake_dense_rank` 当成语义检索**：它只是 Jaccard，词汇不重叠就无能为力。
- **`list.sort()` 的返回值是 `None`**：写成 `scored = scored.sort()` 会把列表弄丢。
