# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 67 节 查询改写：HyDE、多查询与查询分解 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（测试：`python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`） ｜ **依赖**：纯标准库（`math`、`re`、`collections`、`dataclasses`、`typing`），无需网络、无需 LLM API key。

---

## 1. 这份代码在考察什么

这份代码在一个 8 篇文档的 fixture 上，实现并对比三种**检索前的查询改写**策略：

1. **HyDE**：让（模拟的）LLM 写一段假设答案，用它的向量做稠密检索。
2. **Multi-query**：生成多个改写，分别检索后用 RRF 合并。
3. **Decomposition**：把多主题问题拆成子问题，分别检索后合并。

为了离线、确定地运行，它还自带了：

- 一个简化版的 **hybrid 检索器**（BM25 + 哈希稠密向量 + RRF，模仿第 65 节）；
- 一个**查表式 `MockLLM`**：fixture 里的 query 直接查表得到假设文档/改写/子问题，没见过的 query 走同义词扩展或按 "and" 拆分的兜底逻辑；
- 一个统一的 **`Rewriter` 接口**和 **`retrieve_with_rewriter`** 编排函数。

> 一句话：**改写器只负责"把一个 query 变成若干个检索请求"，检索器和融合方式保持不变**——这让三种策略可以互换、对比和组合。同时要看清 demo 的结论有多脆弱：一处"胜出"是平局，一处"胜出"与基线打平，一个测试永远不会失败。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tokenize` | 函数 | 小写 + 正则抽取字母数字串 | 分词 |
| `mock_embed` / `cosine` | 函数 | 词哈希 + 字符 bigram 哈希的 96 维向量；L2 归一化后点积 | 稠密检索替身 |
| `Doc` | dataclass | 文档：id、标题、正文 | 语料单元 |
| `BM25Index` | dataclass | BM25 倒排统计与打分，标题重复 3 次加权 | 词法检索 |
| `DenseIndex` | dataclass | 存每篇文档向量，按 cosine 排序；支持直接传入向量 | 稠密检索 |
| `rrf` | 函数 | 倒数排名融合，k = 60 | Reciprocal Rank Fusion |
| `HybridRetriever` | dataclass | BM25 + 稠密各取 `k_each`，RRF 后取 `k_out`；`search_vec` 供 HyDE 使用 | hybrid 检索 |
| `_SYNONYMS` / `HYDE_TABLE` / `MQ_TABLE` / `DECOMP_TABLE` | 常量 | Mock LLM 的同义词表与三张查表 | 离线 LLM |
| `MockLLM` | dataclass | `generate_hypothetical` / `paraphrase` / `decompose` | LLM 接口 |
| `RewriteResult` | dataclass | 策略名、检索用的 query 列表、可选的假设文档 | 改写输出 |
| `Rewriter` 及三个子类 | 类 | HyDE、MultiQuery、Decompose 改写器 | 策略模式 |
| `_IdentityRewriter` | 类 | 不改写的基线 | 对照组 |
| `retrieve_with_rewriter` / `rwriter_name` | 函数 | 改写 → 多路检索 → RRF 融合 | 编排 |
| `CORPUS` / `GOLD` / `build_retriever` | 常量 / 函数 | 8 篇文档、3 个带"预期胜出策略"的 query、建索引 | fixture |
| `main` | 函数 | 3 个 query × 4 种策略，打印 gold 是否第一及其名次 | demo |

数据流：`main` → `build_retriever()` 把 8 篇文档同时加入 BM25 与稠密索引 → 对每个 `(query, gold, expected_winner)`、每个策略：`rewriter.rewrite(query)` 得到 `RewriteResult` → `retrieve_with_rewriter` 对假设文档和每条改写分别检索 → 外层 `rrf` 融合 → 找 gold 的名次并打印。

---

## 3. 逐段精讲

### 3.1 分词与哈希向量

```python
def mock_embed(text: str, dim: int = 96) -> list[float]:
    vec = [0.0] * dim
    for tok in tokenize(text):
        h = 0
        for ch in tok:
            h = (h * 1315423911) ^ ord(ch)
            h &= 0xFFFFFFFF
        vec[h % dim] += 1.0
        vec[(h >> 7) % dim] += 0.5
        for i in range(len(tok) - 1):
            bg = (ord(tok[i]) * 31 + ord(tok[i + 1])) & 0xFFFFFFFF
            vec[bg % dim] += 0.25
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
```

- 每个词哈希到两个桶（权重 1.0、0.5），再把词内每个**字符 bigram** 哈希到一个桶（权重 0.25）。bigram 让 "upload" 和 "uploads" 有部分重叠，算是一点点"形态相似"，但仍然没有语义（"abort" 与 "cancel" 毫不相关）。
- 与第 66 节的 `mock_embed` 相比多了 bigram 部分。文件注释说 "mirrors lesson 65 for compatibility"。
- 归一化后 `cosine` 直接写成点积。
- 只有 96 维，大量词会撞到同一个桶，所以稠密分数整体偏平（例如第二个 query 的稠密分数都在 0.31–0.55 之间）。

### 3.2 BM25 索引

```python
    def add(self, doc: Doc) -> None:
        toks = tokenize(doc.title) * 3 + tokenize(doc.body)
        counts = Counter(toks)
        ...

    def search(self, query: str, k: int) -> list[tuple[Doc, float]]:
        ...
        for term in q_terms:
            df = self.df.get(term, 0)
            if df == 0:
                continue
            idf = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
            for i, counts in enumerate(self.tf):
                f = counts.get(term, 0)
                if f == 0:
                    continue
                dl = self.doc_lens[i]
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                scores[i] += idf * f * (self.k1 + 1) / denom
        return sorted(zip(self.docs, scores), key=lambda x: -x[1])[:k]
```

- **标题加权**：`tokenize(doc.title) * 3` 把标题词重复 3 次，相当于标题字段权重 ×3（简化版的 BM25F）。
- **IDF**：`ln((N − df + 0.5)/(df + 0.5) + 1)`，这是 Lucene 采用的"+1"版本，保证 IDF 永远为正。实测 N = 8 时：`the` 出现在 7 篇，IDF = ln 1.2 ≈ 0.182；`fusion`、`rank` 只在 1 篇，IDF = ln 6 ≈ 1.792。
- **TF 饱和与长度归一**：`f·(k1+1) / (f + k1·(1 − b + b·dl/avgdl))`，k1 = 1.5、b = 0.75。`avgdl` 实测 23.5（含标题重复）。
- 查询词重复会被重复累加（`for term in q_terms` 没有去重）。
- ⚠️ `search` 返回 `[:k]` 时**不过滤 0 分文档**。`k_each=8` 等于语料大小时，所有文档都会出现在 BM25 排名里，包括与 query 毫无交集的文档——它们也会在 RRF 中拿到名次分。第 69 节的同名函数加了 `if s > 0` 过滤。

### 3.3 RRF 与 hybrid 检索

```python
def rrf(rankings: list[list[tuple[Doc, float]]], k: int = 60) -> list[tuple[Doc, float]]:
    score: dict[str, float] = defaultdict(float)
    by_id: dict[str, Doc] = {}
    for ranks in rankings:
        for rank, (doc, _) in enumerate(ranks):
            score[doc.doc_id] += 1.0 / (k + rank + 1)
            by_id[doc.doc_id] = doc
    fused = sorted(score.items(), key=lambda x: -x[1])
    return [(by_id[did], s) for did, s in fused]
```

- `rank` 从 0 开始，所以第 1 名贡献 `1/61 ≈ 0.01639`，第 5 名 `1/65 ≈ 0.01538`，第 8 名 `1/68 ≈ 0.01471`。k = 60 让名次之间的差距很小、很平滑。
- 原始分数 `_` 被丢弃——RRF 只看名次，因此 BM25 分数（几十）与 cosine（0–1）不需要校准就能融合。
- `defaultdict(float)` 让第一次访问某个 key 时自动为 0.0。
- **平局处理**：`sorted` 是稳定排序，分数完全相同时保持**字典插入顺序**（即"哪个文档先在某条排名中出现"）。这一点在测验 Q9 中决定了 HyDE 是否"胜出"。

```python
    def search(self, query, k_each=5, k_out=5):
        b = self.bm25.search(query, k_each)
        d = self.dense.search(query, k_each)
        return rrf([b, d])[:k_out]

    def search_vec(self, qv, qtext, k_each=5, k_out=5):
        b = self.bm25.search(qtext, k_each)
        d = self.dense.search_vec(qv, k_each)
        return rrf([b, d])[:k_out]
```

- `search_vec` 是给 HyDE 用的：**BM25 仍用原始 query 文本**，稠密侧用传进来的假设文档向量。注释说明了原因："so the lexical signal does not vanish"。这也规避了讲义说的"假设文档编造的标识符污染 BM25"。

### 3.4 Mock LLM：查表 + 兜底

```python
    def generate_hypothetical(self, query: str) -> str:
        key = query.lower().strip().rstrip("?").strip()
        if key in HYDE_TABLE:
            return HYDE_TABLE[key]
        toks = tokenize(query)
        expanded = []
        for t in toks:
            expanded.append(t)
            expanded.extend(_SYNONYMS.get(t, []))
        return " ".join(expanded)
```

- **规范化 key**：小写、去首尾空格、去掉末尾问号，让 "How does ...?" 也能命中表。
- 查表命中时返回手写的假设文档；兜底时把每个词后面接上它的同义词，例如 `"abort the upload on fail"` → `"abort cancel stop terminate the upload transfer ingest on fail error failure"`——这更像**同义词查询扩展**而不是"假设文档"。
- 注意 `HYDE_TABLE` 中第二个 query 的假设文档几乎照抄了 d6 的正文（"reciprocal rank fusion... operates on ranks, not on scores"），这让 HyDE 在该 query 上稠密相似度达到 0.909。真实 LLM 不了解你的语料，很难写得这么"准"。

```python
    def paraphrase(self, query: str, n: int = 3) -> list[str]:
        ...
        toks = tokenize(query)
        out: list[str] = []
        for shift in range(n):
            swapped = []
            for i, t in enumerate(toks):
                opts = _SYNONYMS.get(t, [])
                if opts and (i + shift) % 2 == 0:
                    swapped.append(opts[shift % len(opts)])
                else:
                    swapped.append(t)
            out.append(" ".join(swapped))
        return out
```

- 兜底改写：第 `shift` 个改写只替换"下标与 shift 同奇偶"的、有同义词的词，并选第 `shift % len(opts)` 个同义词。例如 `"abort the upload on fail"` → `['cancel the transfer on error', 'abort the upload on fail', 'terminate the transfer on error']`。
- ⚠️ 对没有同义词的 query（如 `"where is the vector index stored"`），三个改写**和原句一模一样**——这正是讲义的 "Multi-query rewrites all converge" 失败模式，代码没有做去重。

```python
    def decompose(self, query: str) -> list[str]:
        ...
        if " and " in query.lower():
            parts = re.split(r"\s+and\s+", query, flags=re.IGNORECASE)
            return [p.strip().rstrip("?") for p in parts if p.strip()]
        return [query]
```

- 兜底按 "and" 拆分，没有 "and" 就原样返回（原子问题）。
- ⚠️ `"how is lexical and semantic retrieval combined"` 会被拆成 `['how is lexical', 'semantic retrieval combined']`——讲义的 "Decomposition over-splits"。改进思路见测验 Q11。

### 3.5 改写器接口

```python
@dataclass
class RewriteResult:
    strategy: str
    rewrites: list[str]
    hypothetical: str | None = None


class Rewriter:
    name: str

    def rewrite(self, query: str) -> RewriteResult:
        raise NotImplementedError
```

- `Rewriter` 是一个"抽象基类"的轻量写法：子类必须实现 `rewrite`，否则调用时抛 `NotImplementedError`。（更正式的写法是 `abc.ABC` + `@abstractmethod`。）
- `name: str` 只是类型注解，不会生成属性；子类用 dataclass 字段或类属性给它赋值。

```python
@dataclass
class HyDERewriter(Rewriter):
    llm: MockLLM = field(default_factory=MockLLM)
    name: str = "hyde"

    def rewrite(self, query):
        h = self.llm.generate_hypothetical(query)
        return RewriteResult(strategy=self.name, rewrites=[query], hypothetical=h)


@dataclass
class MultiQueryRewriter(Rewriter):
    llm: MockLLM = field(default_factory=MockLLM)
    n: int = 3
    name: str = "multiquery"

    def rewrite(self, query):
        rewrites = [query] + self.llm.paraphrase(query, n=self.n)
        return RewriteResult(strategy=self.name, rewrites=rewrites)
```

| 策略 | `rewrites` | `hypothetical` | 检索次数（`HybridRetriever` 调用） |
|------|-----------|----------------|------------------|
| no-rewrite | `[query]` | `None` | 1 |
| hyde | `[query]` | 假设文档 | 2（`search_vec` + `search`） |
| multiquery（n=3） | `[query] + 3 个改写` | `None` | 4 |
| decompose | 子问题列表（原子问题时为 `[query]`） | `None` | 子问题数 |

- HyDE 的 `rewrites` 保留了原始 query，所以 HyDE 实际上是"假设文档那一路 + 原 query 那一路"的融合，而不是纯 HyDE。
- Multi-query 也保留了原 query，所以是 N + 1 路检索；讲义只说 "N paraphrases"。
- `_IdentityRewriter` 定义在 `main()` **之后**，但因为 `main()` 是在文件末尾的 `if __name__ == "__main__":` 里才被调用，此时类已定义，所以没问题。

### 3.6 编排：`retrieve_with_rewriter`

```python
def retrieve_with_rewriter(query, rewriter, retriever, k_each=5, k_out=5):
    rw = rewriter.rewrite(query)
    rankings: list[list[tuple[Doc, float]]] = []
    if rw.hypothetical is not None:
        hv = mock_embed(rw.hypothetical)
        rankings.append(retriever.search_vec(hv, qtext=query, k_each=k_each, k_out=k_each))
    for r in rw.rewrites:
        rankings.append(retriever.search(r, k_each=k_each, k_out=k_each))
    fused = rrf(rankings)[:k_out]
    return {
        "rewriter": rwriter_name(rw),
        "rewrites": rw.rewrites,
        "hypothetical": rw.hypothetical,
        "results": fused,
    }
```

- **两层 RRF**：每次 `search` 内部先对 BM25 + 稠密做一次 RRF，`retrieve_with_rewriter` 再对多条排名做一次 RRF。内层的分数差异在外层被压缩成名次，因此外层很容易出现**完全相同的分数**（见 6 节）。
- 内层 `k_out=k_each`，外层 `[:k_out]`。
- `rwriter_name(rw)` 只是返回 `rw.strategy`，是个多余的小函数（名字还少了一个字母 e），可以直接写 `rw.strategy`。
- 对不改写的单条排名，外层 RRF 只是把名次重新映射为 `1/(61+rank)`，顺序不变。

### 3.7 fixture 与 demo

```python
GOLD = [
    ("what do we do when a transfer breaks halfway", "d1", "multiquery"),
    ("how does the search service merge two retrievers", "d6", "hyde"),
    ("what happens when an upload fails and the retry budget is exhausted", "d1", "decompose"),
]
```

- 每个 query 设计成某种策略最擅长的类型（注释说明）：表述模糊 → multi-query；体裁不匹配 → HyDE；多子句 → decomposition。
- `main` 对每个 query 跑 4 种策略，`k_each=8, k_out=8`（**等于语料大小**，所以每条排名都包含全部 8 篇文档），打印 gold 是否第一和 gold 的名次，并在预期胜出策略后标注 `<- expected winner`。
- ⚠️ 第三个 query 是双主题问题（答案在 d1 和 d3），但 `GOLD` 只记录了一个 gold（d1），所以这个评估**无法衡量** decomposition 的真正价值——"把两篇文档都找回来"。
- ⚠️ 讲义说第一个 query 类型（"phrasing-mismatched"）由 HyDE 胜出、multi-query 赢"paraphrase-variance"；代码中第一个 query 的预期胜出者是 multi-query，第二个才是 HyDE。讲义的问题示例 "what does our team do when uploads fail and the budget is gone" 在代码中也不存在。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 查表式 Mock LLM | 离线、确定性、可测试 | 查表内容由作者手写，HyDE 文本几乎照抄目标文档，效果被高估；生产换成真实 LLM 调用并缓存 |
| 统一的 `Rewriter` 接口 + `RewriteResult` | 策略可插拔，检索与融合代码不变 | 接口较简陋，没有置信度、成本等字段（讲义练习 5） |
| HyDE 时 BM25 仍用原 query | 防止编造的标识符污染词法检索 | 失去假设文档中的有用词汇信号；也可以用加权 RRF 折中 |
| 改写结果中保留原 query | 改写跑偏时仍有兜底 | 原 query 那一路会稀释改写的效果 |
| 两层 RRF | 复用 hybrid 检索器，代码简单 | 分数被压成名次，平局频繁；生产中可把所有底层排名放到一层 RRF，或使用加权 RRF |
| RRF k = 60 | 经典默认值，平滑 | 名次差异很小，小语料上难以拉开差距 |
| `k_each = 8`（= 语料大小） | 保证每条排名都完整 | 0 分文档也拿到名次分；真实系统 `k_each` 远小于语料 |
| BM25 标题 ×3 | 简单的字段加权 | 生产用 BM25F 或分字段索引 |
| 哈希 + bigram 稠密向量 | 无依赖 | 无语义；正是它拖累了第二个 query（见测验 Q12） |
| 只记录一个 gold | fixture 简洁 | 无法衡量 decomposition 的多文档覆盖；应使用多 gold 的 recall@k（第 68 节） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许 `str \| None`、`list[str]` 等写法在任何 3.7+ 版本中作为注解使用 |
| `Counter` | `Counter(toks)`、`self.df[term] += 1` | 计数字典，缺失键默认为 0 |
| `defaultdict(float)` | `score: dict[str, float] = defaultdict(float)` | 访问不存在的键时自动创建默认值 0.0 |
| 列表重复 | `tokenize(doc.title) * 3` | 把列表重复 3 次再拼接 |
| `dict.get(key, default)` | `self.df.get(term, 0)`、`_SYNONYMS.get(t, [])` | 键不存在时返回默认值，不抛 `KeyError` |
| `continue` | `if df == 0: continue` | 跳过本次循环剩余部分 |
| `x or default` | `(self.avgdl or 1)`、`math.sqrt(...) or 1.0` | 左侧为 0 时用右侧，防止除零 |
| 字符串方法链 | `query.lower().strip().rstrip("?").strip()` | 依次小写、去空白、去末尾问号、再去空白 |
| `re.split` + flags | `re.split(r"\s+and\s+", query, flags=re.IGNORECASE)` | 按正则切分，忽略大小写 |
| `@dataclass` 继承普通类 | `class HyDERewriter(Rewriter)` 加 `@dataclass` | 子类字段自动生成 `__init__`；父类只提供接口 |
| `field(default_factory=...)` | `llm: MockLLM = field(default_factory=MockLLM)` | 每个实例新建一个默认对象，避免共享可变默认值 |
| `raise NotImplementedError` | `Rewriter.rewrite` | 约定"子类必须实现" |
| 仅注解的类属性 | `class Rewriter: name: str` | 只声明类型，不赋值、不创建属性 |
| 类属性赋值 | `class _IdentityRewriter(Rewriter): name = "no-rewrite"` | 所有实例共享 |
| `X \| None` | `hypothetical: str \| None = None` | 可选类型 |
| 元组解包 + `enumerate` | `for rank, (doc, _) in enumerate(ranks)` | 同时取下标和嵌套元组的元素；`_` 表示不用的值 |
| `sorted` 的稳定性 | `sorted(score.items(), key=lambda x: -x[1])` | 键相同时保持原有顺序；dict 保持插入顺序（3.7+） |
| 列表索引查找 | `ranks.index(gold) + 1 if gold in ranks else -1` | 条件表达式 + `list.index` 找名次 |
| 字典字面量 + 对齐写法 | `strategies: dict[str, Rewriter] = {"no-rewrite": ..., ...}` | 带类型注解的字典 |
| f-string 宽度与对齐 | `f"{name:<12} \| {q[:58]:<60} \|"` | `<12` 左对齐占 12 格；`q[:58]` 先截断再填充 |
| 字符串乘法 | `"-" * 100` | 打印分隔线 |
| `typing.Iterable` | `from typing import Iterable` | 导入了但本文件未使用 |
| `if __name__ == "__main__":` | 文件末尾 | 被测试导入时不运行 demo |

---

## 6. 运行结果解读

实际运行（Python 3.13，纯标准库，瞬间完成）：

```text
strategy     | query                                                        | gold@1? | gold-rank
----------------------------------------------------------------------------------------------------
no-rewrite   | what do we do when a transfer breaks halfway                 |  no    |   3
hyde         | what do we do when a transfer breaks halfway                 |  no    |   2
multiquery   | what do we do when a transfer breaks halfway                 |  yes   |   1  <- expected winner
decompose    | what do we do when a transfer breaks halfway                 |  no    |   3

no-rewrite   | how does the search service merge two retrievers             |  no    |   5
hyde         | how does the search service merge two retrievers             |  yes   |   1  <- expected winner
multiquery   | how does the search service merge two retrievers             |  no    |   2
decompose    | how does the search service merge two retrievers             |  no    |   5

no-rewrite   | what happens when an upload fails and the retry budget is    |  yes   |   1
hyde         | what happens when an upload fails and the retry budget is    |  no    |   2
multiquery   | what happens when an upload fails and the retry budget is    |  yes   |   1
decompose    | what happens when an upload fails and the retry budget is    |  yes   |   1  <- expected winner
```

逐项解读：

- **第一个 query**：multi-query 把 d1 从第 3 提到第 1，因为 `MQ_TABLE` 的三个改写都带有 "multipart"、"upload"、"failure" 等语料词汇。decompose 对原子问题原样返回，结果与 no-rewrite 相同——这正是讲义要求的正确行为。
- **第二个 query**：HyDE 显示 `yes`，但我们打印了完整分数：d6 与 d2 的最终分数**完全相同**（都是 `0.03177805800756621`）。原因是两条内部排名互为镜像：假设文档那一路 d6 第 1、d2 第 5；原 query 那一路 d2 第 1、d6 第 5，`1/61 + 1/65` 两者相等。d6 能排第一只是因为它先被插入字典、`sorted` 稳定排序保留了插入顺序。把 `k_each` 改成 5，HyDE 在这个 query 上就变成第 2 名。
- **第二个 query 的基线为什么差**：单看 BM25，d6 是第 1 名（1.919 分，"search" 只在 d6 出现）；稠密那一路却把 d6 排到第 7。内部 RRF 后 d2（BM25 第 4、稠密第 1，0.03202）超过 d6（0.03132）。所以拖后腿的是哈希稠密向量，而不是讲义叙述的"BM25 漏掉"。
- **第三个 query**：no-rewrite 本来就是 `yes`，decomposition 只是打平；HyDE 反而变差（第 2）。讲义说"Decomposition wins on the multi-topic query"，在这个 fixture 上不成立；讲义另一句 "The fallback (no rewriter) loses on at least one of the three" 成立（输了两个）。
- **分数为什么都挤在 0.015–0.065 之间**：RRF k = 60，每多一条排名分数上限加 1/61；multi-query 有 4 条排名，所以它的分数在 0.06 左右，HyDE 两条约 0.03，单条约 0.016。不同策略之间的分数**不能直接比较**，只能比较同一策略内部的名次。

`k_each` 敏感性（我们额外跑的实验，gold 名次，三个 query 依次）：

| k_each | no-rewrite | hyde | multiquery | decompose |
|--------|-----------|------|-----------|-----------|
| 3 | 3, 2, 1 | 2, 1, 2 | 1, 1, 1 | 3, 2, 1 |
| 5 | 3, 5, 1 | 2, 2, 2 | 1, 2, 1 | 3, 5, 1 |
| 8（demo） | 3, 5, 1 | 2, 1, 2 | 1, 2, 1 | 3, 5, 1 |

结论随 `k_each` 改变，在 3 个 query 的 fixture 上，"哪个策略胜出"只能当作演示，不能当作证据。

---

## 7. 动手改一改

1. **打破平局**：给 `rrf` 增加确定性的平局规则（例如分数相同时按"在各排名中的最好名次"再按 `doc_id` 排序），重新跑 demo，看第二个 query 中 HyDE 是否还是 `yes`。
2. **加权 RRF**：给 `HybridRetriever.search` 增加 `w_bm25`、`w_dense` 参数（`score += w / (k + rank + 1)`），设置 `w_bm25 = 2` 后看第二个 query 的 no-rewrite 结果是否已经把 d6 排第一。
3. **多 gold 评估**：把 `GOLD` 改成 `(query, {gold_ids}, winner)`，第三个 query 的 gold 设为 `{"d1", "d3"}`，计算各策略的 recall@2，看 decomposition 能否体现优势。
4. **multi-query 去重**（讲义失败模式）：在 `MultiQueryRewriter.rewrite` 中用 Jaccard 相似度去掉与已有改写过于相似（≥ 0.8）的条目，用 `"where is the vector index stored"` 验证三个重复改写被去掉。
5. **讲义练习 2（step-back）**：新增 `StepBackRewriter`：用一张小表把具体问题映射到更一般的问题（如 "how is an S3 multipart upload aborted" → "how does the storage service handle failures"），把一般问题与原问题一起检索后 RRF。
6. **讲义练习 1（RAG-Fusion）**：把 multi-query 的融合结果再交给第 66 节的 cross-encoder 重排，比较 top-3。

---

## 8. 常见坑

- **把平局当胜出**：RRF 只看名次，镜像排名会产生完全相同的分数，结果取决于插入顺序。写对比实验时要显式处理平局。
- **跨策略比较融合分数**：排名条数不同，RRF 分数的量级就不同（单条约 0.016，四条约 0.06），只能比较名次。
- **HyDE 让假设文档进入 BM25**：编造的函数名、版本号会成为高 IDF 的噪声词。本节代码让 BM25 只看原 query，是一种稳妥做法。
- **Mock 写得太"准"**：查表里的假设文档几乎照抄目标文档，换成真实 LLM 后提升会小很多。
- **multi-query 的改写全部相同**：兜底逻辑在没有同义词时返回三份原句，白白多跑三次检索。
- **按 "and" 机械拆分**：名词短语里的并列（"lexical and semantic retrieval"）会被错拆。
- **单 gold 评估多主题问题**：decomposition 的价值无法体现。
- **写出永远为真的测试**：见下一节 `test_gold_promotion_for_designated_strategies`。
- **`k_each` 等于语料大小**：0 分文档也拿名次分，小 fixture 上的结论在真实规模下不一定成立。

---

## 9. 测试在验证什么

测试文件：`tests/test_rewriters.py`（`unittest` 风格）。在 `code/` 目录下运行 `python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`。

| 测试类 / 方法 | 验证的性质 |
|--------------|-----------|
| `TestMockLLM.test_hyde_table_hit` | 表中 query 的假设文档包含 "rank fusion" |
| `TestMockLLM.test_hyde_fallback_returns_string` | 未知 query 走兜底，返回非空字符串 |
| `TestMockLLM.test_paraphrase_returns_n` | 表中 query 返回 3 个改写，且不含原句 |
| `TestMockLLM.test_decompose_atomic_returns_self` | 原子问题原样返回单元素列表 |
| `TestMockLLM.test_decompose_splits_on_and` | 带 "and" 的问题拆成 2 个 |
| `TestHyDERewriter.test_returns_hypothetical` | HyDE 返回 `RewriteResult`，`hypothetical` 非空，策略名为 "hyde" |
| `TestMultiQueryRewriter.test_includes_original_query_plus_paraphrases` | 改写列表至少 3 条，第一条是原 query |
| `TestDecomposeRewriter.test_multi_clause_decomposes` | 多子句问题拆成 2 个，每个少于 80 字符 |
| `TestRetrieveLoop.test_no_rewrite_baseline_runs` | 基线能返回非空结果 |
| `TestRetrieveLoop.test_hyde_changes_top_rank` | HyDE 的排名与基线不同 |
| `TestRetrieveLoop.test_gold_promotion_for_designated_strategies` | 声称：每个 gold query 至少有一个改写器不差于基线 |
| `TestRRF.test_rrf_empty` | 空输入返回空列表 |
| `TestRRF.test_rrf_single_list_preserves_order` | 单条排名融合后顺序不变 |

实际运行结果：

```text
.............                                                            [100%]
13 passed in 0.02s
```

几点评价：

- **`test_gold_promotion_for_designated_strategies` 是永真测试**：`best` 初始化为 `base_rank`，之后只会用 `min` 变小，`assertLessEqual(best, base_rank)` 不可能失败。即使把三个改写器全部换成"返回随机文档"，它也会通过。正确写法见测验 Q10。
- `test_decompose_splits_on_and` 用的 query 恰好在 `DECOMP_TABLE` 中，测到的是查表结果，**没有测到**"按 and 拆分"的兜底逻辑；兜底逻辑的过度拆分问题完全没有被测试覆盖。
- `test_paraphrase_returns_n` 也只测了查表分支；兜底分支会返回三份与原句相同的改写，若对兜底分支做同样断言会失败。
- `test_hyde_changes_top_rank` 只要求"排名有变化"，不要求变好。
- 测试中没有任何对平局处理的检查，而 demo 中 HyDE 的胜出恰恰取决于平局时的插入顺序。
