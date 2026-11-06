# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 65 节 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`cd code && python3 main.py`；测试 `python3 -m pytest -q tests`（或 `python3 -m unittest discover tests`） ｜ **依赖**：仅标准库（`math`、`re`、`collections`、`dataclasses`、`typing`）

---

## 1. 这份代码在考察什么

这份代码用纯 Python 搭了一个最小的 hybrid 检索器：

1. **BM25 从零实现**：文档频率 df、词频 tf、文档长度、平均长度 avgdl、平滑 IDF、k1 饱和、b 长度归一化；外加"重复 token"式的字段加权（title × 3）。
2. **Dense 检索**：一个确定性的哈希 embedding（词哈希 + 字符二元组），余弦排序。
3. **Reciprocal Rank Fusion**：按 2009 年论文的 `1/(k + rank)`，k = 60，支持每路权重。
4. **HybridRetriever**：同一个文档同时进两个索引，查询时两路各取 top-k 再融合。
5. **演示**：7 篇文档的小语料、3 个分别针对"字面标识符 / 换说法 / 混合"的 query，打印三路排名。

> 一句话：**把"词法 + 语义 + 按名次投票"三件事写到能逐行看懂的程度**。但要注意：这里的"dense"是哈希词袋，本质仍是词法匹配；演示 query 也没能真正体现融合的价值（见第 6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Doc` | dataclass | `doc_id`、`title`、`body`；`field_text(name)` 按字段名取文本 | 文档 + 字段 |
| `_TOKEN` / `tokenize` | 正则 / 函数 | 小写化后提取 `[a-z0-9]+` | 分词 |
| `BM25Index` | dataclass | `add` 建 tf/df/长度；`search` 按 BM25 打分 | BM25 |
| `mock_embed` / `cosine` | 函数 | 哈希词袋 + 字符二元组，L2 归一化；点积 | mock embedding |
| `DenseIndex` | dataclass | 存 (Doc, 向量)，暴力余弦 top-k | dense 检索 |
| `rrf` | 函数 | 多路排名 → `Σ w/(k + rank)` → 排序 | RRF |
| `HybridRetriever` | dataclass | 组合 BM25 与 dense，`search` 返回三路结果 | hybrid |
| `CORPUS` | 常量 | 7 篇文档（S3 abort、上传、桶预算、权限、策略引擎、检索排序、索引大小） | fixture |
| `print_ranking` / `main` | 函数 | 打印三个 query 的三路排名 | 演示 |

数据流：

```text
CORPUS ─► HybridRetriever.add ─┬─► BM25Index.add（title×3 + body 的 token 计数）
                               └─► DenseIndex.add（mock_embed(title + "\n" + body)）
query ─► HybridRetriever.search ─┬─► BM25Index.search(k_each) ─┐
                                 └─► DenseIndex.search(k_each) ┴─► rrf(k=60, weights) ─► fused[:k_out]
```

---

## 3. 逐段精讲

### 3.1 `Doc` 与分词

```python
@dataclass
class Doc:
    doc_id: str
    title: str
    body: str

    def field_text(self, field_name: str) -> str:
        return {"title": self.title, "body": self.body}.get(field_name, "")

_TOKEN = re.compile(r"[a-z0-9]+")

def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())
```

- `field_text` 用一个临时字典按名字取字段，未知字段返回空串——这让 `BM25Index` 可以只通过 `field_weights` 的键来决定索引哪些字段。
- 分词规则很粗：先小写，再取连续的字母数字。效果（测试中也有）：`"AbortMultipart, On Fail!"` → `["abortmultipart", "on", "fail"]`；`"v1.2-rc3"` → `["v1", "2", "rc3"]`。
- ⚠️ 对代码标识符的影响：
  - **snake_case 被拆开**：`check_permission` → `check`、`permission`；
  - **camelCase 不拆**：`AbortMultipartOnFail` → 一个 token `abortmultipartonfail`；
  - **没有词干化**：`aborts` 与 `abort`、`cancelled` 与 `cancel` 是不同的词。实测 `search("abort")` 返回空列表；
  - **没有停用词表**：`for`、`the`、`a` 都会参与打分。

### 3.2 `BM25Index`：建索引

```python
@dataclass
class BM25Index:
    k1: float = 1.5
    b: float = 0.75
    field_weights: dict[str, int] = field(default_factory=lambda: {"title": 3, "body": 1})
    docs: list[Doc] = field(default_factory=list)
    doc_lens: list[int] = field(default_factory=list)
    df: Counter = field(default_factory=Counter)
    tf: list[Counter] = field(default_factory=list)
    avgdl: float = 0.0

    def _doc_tokens(self, doc):
        out = []
        for field_name, weight in self.field_weights.items():
            tokens = tokenize(doc.field_text(field_name))
            out.extend(tokens * weight)
        return out

    def add(self, doc):
        tokens = self._doc_tokens(doc)
        counts = Counter(tokens)
        self.docs.append(doc)
        self.doc_lens.append(len(tokens))
        self.tf.append(counts)
        for term in counts:
            self.df[term] += 1
        self.avgdl = sum(self.doc_lens) / max(1, len(self.doc_lens))
```

| 数据结构 | 含义 | 本节实测 |
|---------|------|---------|
| `tf[i]` | 第 i 篇文档中每个词的出现次数（`Counter`） | 例如 d7 中 `for` 出现 2 次 |
| `df[t]` | 包含词 t 的文档数 | `for`、`service`、`budget`、`retry` 的 df 都是 2；`the` 的 df 是 6 |
| `doc_lens[i]` | 第 i 篇文档（加权后）的 token 数 | `[28, 52, 35, 37, 27, 38, 32]` |
| `avgdl` | 平均文档长度 | 35.571 |

- **字段加权 = token 重复**：`tokens * 3` 把 title 的 token 列表重复 3 次。这会让 title 词的 tf 变成 3 倍，**同时**让文档长度变长。讲义说它 "keeps the math identical"，但它与 BM25F（按字段分别做长度归一化、再合并词频）不等价（讲义练习 4）。
- `field(default_factory=lambda: {...})`：可变默认值（字典）必须用工厂函数，每个实例一份。
- `df` 只按"是否出现"计数：`for term in counts` 遍历的是去重后的词。
- 每次 `add` 都重新计算 `avgdl`，O(N)；批量建索引时可以最后算一次。
- ⚠️ 这是一个"只追加"的索引：没有删除/更新文档的接口。

### 3.3 `BM25Index.search`：打分

```python
    def search(self, query, k=10):
        if not self.docs:
            return []
        q_terms = tokenize(query)
        n = len(self.docs)
        scores = [0.0] * n
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
        ranked = sorted(zip(self.docs, scores), key=lambda x: -x[1])
        return [(d, s) for d, s in ranked[:k] if s > 0]
```

- 外层遍历 query 词、内层遍历所有文档——这是"按词遍历"的写法；真正的倒排索引只访问包含该词的文档（posting list），这里为了简单扫了全部文档。
- **平滑 IDF**：`log((N − df + 0.5)/(df + 0.5) + 1)`，永远为正。N = 7 时：df = 1 → 1.674，df = 2 → 1.163，df = 6（`the`）→ 0.208。
- **词频饱和 + 长度归一化**：`f·(k1+1) / (f + k1·(1 − b + b·dl/avgdl))`。
- query 中重复的词会被重复计分（`for term in q_terms` 没有去重），相当于 query 词频线性加权。
- `self.avgdl or 1`：防止空索引时除以 0（实际上前面已经判断过 `if not self.docs`）。
- 最后只返回**分数 > 0** 的结果，所以 BM25 列表经常比 k 短（演示中字面 query 只返回 1 条）。这一点对 RRF 很重要：BM25 不会为不相关的文档"投票"，而 dense 会。

手算示例（query "centralized authorization for service accounts" 对 d7）：

```text
IDF(for) = log(5.5/2.5 + 1) = 1.1632
K = 1.5 × (1 − 0.75 + 0.75 × 32/35.571) ≈ 1.3871
score = 1.1632 × 2 × 2.5 / (2 + 1.3871) ≈ 1.7171      ← 与运行输出一致
```

d7 只因为停用词 `for` 出现两次就排到了第 2（讲义失败模式 "Stop-token domination"）。

### 3.4 Mock embedding 与 `DenseIndex`

```python
def mock_embed(text, dim=96):
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

- 与第 64 节的 `mock_embed` 相比多了**字符二元组**特征：每个 token 的相邻字符对哈希到一个桶上加 0.25。这样 `cancelled` 和 `cancel` 会共享一部分特征（`ca`、`an`、`nc`、`ce`、`el`），有一点"模糊匹配"的效果。代码注释说是为了"spread synonyms differently from BM25"，但它只能捕捉**拼写相似**，不能捕捉**同义词**（"terminate" 与 "abort" 毫无共同特征）。
- 讲义说它与第 64 节是"the same deterministic embedding... so chunks are comparable"，实际上多了二元组项，两者向量并不相同。
- 96 维、多种特征叠加，哈希碰撞不可避免。

```python
@dataclass
class DenseIndex:
    vectors: list[tuple[Doc, list[float]]] = field(default_factory=list)

    def add(self, doc):
        text = f"{doc.title}\n{doc.body}"
        self.vectors.append((doc, mock_embed(text)))

    def search(self, query, k=10):
        qv = mock_embed(query)
        scored = [(d, cosine(qv, v)) for d, v in self.vectors]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]
```

- dense 侧把 title 和 body 拼起来 embedding，**没有**字段加权。
- 暴力计算所有余弦再排序，O(N·d)。
- ⚠️ 不设相似度阈值，**总是返回 k 个结果**。在 7 篇文档、`k_each = 5` 的设定下，dense 列表几乎包含整个语料，RRF 会给不相关的文档也加上 `1/(60+rank)` 的票。

### 3.5 `rrf`：按名次投票

```python
def rrf(rankings, k=60, weights=None):
    if weights is None:
        weights = [1.0] * len(rankings)
    if len(weights) != len(rankings):
        raise ValueError("weights length must match rankings length")
    score = defaultdict(float)
    by_id = {}
    for w, ranks in zip(weights, rankings):
        for rank, (doc, _) in enumerate(ranks):
            score[doc.doc_id] += w * (1.0 / (k + rank + 1))
            by_id[doc.doc_id] = doc
    fused = sorted(score.items(), key=lambda x: -x[1])
    return [(by_id[did], s) for did, s in fused]
```

- `enumerate` 从 0 开始，公式里的名次从 1 开始，所以写成 `k + rank + 1`。第 1 名贡献 `1/61 ≈ 0.01639`，第 2 名 `1/62 ≈ 0.01613`，第 10 名 `1/70`。
- `(doc, _)`：原始分数被丢弃——RRF 只用名次。
- `defaultdict(float)`：第一次访问某个 doc_id 时自动初始化为 0.0。
- 权重乘在每一路的贡献上，保持名次衰减的形状不变（讲义："preserves the rank-decay shape and stays scale-free"）。
- 只要文档出现在任一列表中就会得分；两路都出现的文档通常胜出：两次第 2（0.0323）远高于一次第 1（0.0164）。
- **并列**：`sorted` 是稳定排序，`score` 字典保持插入顺序，所以分数相同时先插入的（来自第一个列表、名次靠前的）排前面。paraphrased query 中 d2 与 d3 就是精确并列（各自一次第 1、一次第 2）。
- 按 `doc_id` 合并：如果索引单元是 chunk，同一文档的不同 chunk 会被当成不同的条目（讲义失败模式提到要按文档去重）。

### 3.6 `HybridRetriever`

```python
@dataclass
class HybridRetriever:
    bm25: BM25Index = field(default_factory=BM25Index)
    dense: DenseIndex = field(default_factory=DenseIndex)
    rrf_k: int = 60
    bm25_weight: float = 1.0
    dense_weight: float = 1.0

    def search(self, query, k_each=10, k_out=5):
        bm25_hits = self.bm25.search(query, k=k_each)
        dense_hits = self.dense.search(query, k=k_each)
        fused = rrf([bm25_hits, dense_hits], k=self.rrf_k,
                    weights=[self.bm25_weight, self.dense_weight])
        return {"bm25": bm25_hits, "dense": dense_hits, "fused": fused[:k_out]}
```

- `field(default_factory=BM25Index)`：用类本身作为工厂，每个 retriever 有自己的索引实例。
- `k_each`：每路取多少候选进入融合；`k_out`：融合后返回多少。两路串行执行，生产中应并行（讲义 "Run both queries in parallel"）。
- 返回字典同时带上三路结果，便于调试与后续 reranker 知道每个结果来自哪个模态。

### 3.7 语料与演示

- 7 篇文档围绕"存储服务"：d1 `AbortMultipartOnFail`（中止分片上传）、d2 上传大文件（含 "Cancelled uploads"）、d3 桶级重试预算、d4 `check_permission`、d5 策略引擎、d6 检索排序（RRF 本身）、d7 向量索引大小（"1 KB per vector at 256 dimensions in float32"，`256 × 4 = 1024` 字节，正确）。
- 三个 query 的 `note` 说明了作者的预期：字面标识符、换说法、混合。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python BM25、扫全部文档 | 公式透明 | 没有倒排表；生产用 Lucene/Elasticsearch/Tantivy |
| 平滑 IDF（+1） | 小语料中高 df 词 IDF 不为负 | 小语料中停用词 IDF 仍不够低，需要停用词表 |
| 字段加权 = 重复 token | 不改打分公式 | 改变了 tf 和文档长度，不等价于 BM25F |
| 分词只做小写 + 字母数字 | 简单 | 无词干化、camelCase 不拆、snake_case 拆开；代码检索需要专门的标识符分词 |
| 哈希 embedding + 字符二元组 | 离线、确定 | 只有词法/拼写相似性，无法测试真正的语义检索 |
| dense 总返回 k 个结果 | 实现简单 | 不相关文档也参与投票；可设阈值 |
| RRF k = 60、等权 | 论文默认值，无需调参 | 无法利用分数置信度；并列难分；应在评估集上调 |
| 按 doc_id 融合 | 演示中索引单元就是文档 | chunk 级检索需按父文档去重 |
| 三路结果一起返回 | 便于调试、给 reranker 提供模态信息 | 无 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `collections.Counter` | `Counter(tokens)`、`df: Counter = field(default_factory=Counter)` | 计数字典；`counts.get(term, 0)` 取次数 |
| `collections.defaultdict` | `score: dict[str, float] = defaultdict(float)` | 访问不存在的键时自动创建默认值 0.0 |
| `field(default_factory=...)` | `field(default_factory=lambda: {"title": 3, "body": 1})`、`field(default_factory=BM25Index)` | 可变默认值 / 嵌套对象的默认值 |
| 列表乘法 | `tokens * weight` | 列表重复 weight 次 |
| `list.extend` vs `append` | `out.extend(tokens * weight)` | `extend` 逐个追加元素，`append` 追加整个对象 |
| 字典字面量 + `.get` | `{"title": self.title, "body": self.body}.get(field_name, "")` | 临时字典做分发 |
| `zip` + `sorted` + `lambda` | `sorted(zip(self.docs, scores), key=lambda x: -x[1])` | 把文档与分数配对后按分数降序 |
| 列表推导式带过滤 | `[(d, s) for d, s in ranked[:k] if s > 0]` | 先截取再过滤 |
| `enumerate` + 元组解包 | `for rank, (doc, _) in enumerate(ranks)` | `_` 表示不用的分数 |
| `typing.Iterable` | `hits: Iterable[tuple[Doc, float]]` | 任何可迭代对象；函数内用 `list(hits)[:top]` 转成列表再切片 |
| `X \| None` 默认参数 | `weights: list[float] \| None = None` | 默认 None，函数内再生成默认列表（避免可变默认参数） |
| `raise ValueError` | 权重与列表数不一致 | 参数校验 |
| f-string | `f"{doc.title}\n{doc.body}"`、`{score:.4f}`、`{i + 1}.` | 插值、4 位小数、表达式 |
| 位运算 | `& 0xFFFFFFFF`、`h >> 7`、`^` | 截断 32 位、右移、异或 |
| 返回字典 | `return {"bm25": ..., "dense": ..., "fused": ...}` | 用字典返回多路结果 |
| `if __name__ == "__main__":` | 文件末尾 | 被测试导入时不运行演示 |

---

## 6. 运行结果解读

实际运行（标准库，瞬时完成）：

```text
query: AbortMultipartOnFail
  bm25 :
    1. d1 (AbortMultipartOnFail)  score=2.9468      ← 只有 d1 含这个 token，BM25 只返回 1 条
  dense:
    1. d1 (AbortMultipartOnFail)  score=0.4957
    2. d7 (Index sizing)  score=0.3055
    ...
  fused:
    1. d1  score=0.0328                               ← 1/61 + 1/61
    2. d7  score=0.0161                               ← 只有 dense 的 1/62

query: how do we handle cancelled uploads
  bm25 :
    1. d2 (Uploading large files)  score=4.8541      ← 正文逐字含 "Cancelled uploads"
    2. d3 (Per-bucket budgets)  score=1.6862
  dense:
    1. d3 (Per-bucket budgets)  score=0.4047
    2. d2 (Uploading large files)  score=0.4016
    ...
  fused:
    1. d2  score=0.0325                               ← 与 d3 精确并列，靠插入顺序排前
    2. d3  score=0.0325

query: centralized authorization for service accounts
  bm25 :
    1. d4 (check_permission)  score=6.0753
    2. d7 (Index sizing)  score=1.7171               ← 只匹配了停用词 "for"
    3. d5 (Policy engine)  score=1.3046
    4. d2 (Uploading large files)  score=0.9630
  dense:
    1. d4 (check_permission)  score=0.5743
    2. d7 (Index sizing)  score=0.4897
    ...
  fused:
    1. d4  score=0.0328
    2. d7  score=0.0323
```

与讲义 Build It 的对照：

| query | 讲义声称（BM25 / dense / RRF） | 实际 |
|-------|------------------------------|------|
| 字面标识符（d1） | 1 / 4 / 1 | 1 / 1 / 1 |
| 换说法（d2） | 6 / 1 / 1 | 1 / 2 / 1（与 d3 并列） |
| 混合（d4） | 3 / 3 / 1 | 1 / 1 / 1 |

三个 query 上，融合都没有纠正任何一路的错误——要么两路都对，要么 BM25 已经对了。"paraphrased" query 其实与 d2 有逐字重合。

我们补充的实验：

| 实验 | 结果 | 说明 |
|------|------|------|
| `search("abort")` | BM25 返回 `[]` | 无词干化、camelCase 未拆分 |
| query "who may access a resource"（目标 d4） | BM25 `[d4, d3, ...]`，dense `[d3, d6, d4, ...]`，fused 第 1 名 **d3** | 融合反而把错误文档推到第 1 |
| 去掉停用词后再查授权 query | BM25 `[d4, d2]`，fused `[d4, d2, d1, d7, d6]` | d7 从第 2 掉到第 4 |
| 线性插值 α = 0.5（字面 query） | d1 1.721，第 2 名 d7 仅 0.153 | BM25 量级压倒余弦 |
| RRF k ∈ {1, 10, 60, 200}（换说法 query） | d2 与 d3 始终并列 | 对称的名次组合任何 k 都分不开 |

---

## 7. 动手改一改

1. **停用词与词干化**：给 `tokenize` 加停用词表和一个简单的后缀剥离（`-s`、`-ed`、`-ing`），重新跑三个 query 和 "abort"，观察 d7 是否还会排第 2、"abort" 是否能找到 d1。
2. **标识符分词**：把 camelCase 拆成子词，同时保留整体 token（`abortmultipartonfail` + `abort`、`multipart`、`on`、`fail`），比较字面 query 与 "abort multipart" 的结果。
3. **讲义练习 3（扫 RRF k）**：扫 k ∈ {10, 30, 60, 100, 200}，并加入"who may access a resource"等对抗性 query，记录目标文档的融合名次。
4. **线性插值对照**：实现原始分数插值与 min-max 归一化插值（测验 Q11），在同样的 query 上和 RRF 比较。
5. **dense 阈值**：让 `DenseIndex.search` 只返回余弦 ≥ 某阈值的结果，观察融合列表中"凑数"的文档是否减少。
6. **讲义练习 4（BM25F）**：对 title 与 body 分别计算长度归一化的词频，按字段权重合并后再做饱和，与"重复 token"的做法比较 `authorization`、`check_permission` 等 query。

---

## 8. 常见坑

- **RRF 名次差一**：`enumerate` 从 0 开始，公式名次从 1 开始，忘了 `+1` 会让第 1 名贡献变成 `1/60`。
- **直接相加原始分数**：BM25（0–6+）与余弦（−1–1）尺度不同，线性相加几乎等于只用 BM25。
- **dense 不设阈值**：总是返回 k 个，不相关文档也会进融合列表。
- **小语料的停用词**：平滑 IDF 下停用词仍有可观权重，会把只含 "for/the" 的文档排上来。
- **代码标识符分词**：camelCase、snake_case、点号路径要专门处理，否则字面匹配这一 BM25 的最大优势会丢失。
- **chunk 级结果不去重**：同一文档的多个 chunk 挤占 top-k，且两路投票无法合并。
- **只用几条演示 query 判断融合效果**：本节三条 query 都看不出融合的作用，还有融合帮倒忙的反例；必须用标注评估集（第 68 节）。
- **dataclass 默认值**：`field_weights: dict = {...}` 会报错，必须用 `default_factory`。

---

## 9. 测试在验证什么

运行：`cd code && python3 -m pytest -q tests`。`tests/test_hybrid.py` 会把上级目录加入 `sys.path` 后导入 `main`。

| 测试 | 验证的性质 |
|------|-----------|
| `TestTokenizer.test_lowercase_and_strip_punct` | `"AbortMultipart, On Fail!"` → `["abortmultipart", "on", "fail"]` |
| `TestTokenizer.test_alnum_only` | `"v1.2-rc3"` → `["v1", "2", "rc3"]` |
| `TestBM25.test_literal_match_ranks_first` | 字面标识符 query 的 BM25 第 1 名是 d1 |
| `TestBM25.test_unknown_term_returns_empty` | 语料中不存在的词返回 `[]`（OOV 时 BM25 贡献为 0） |
| `TestBM25.test_field_weight_boost` | title 权重 5 时 "authorization" 的最高分 ≥ 权重 1 时。注意它比较的是两个不同索引的绝对分数 |
| `TestDense.test_deterministic` | 同一 query 两次检索结果相同 |
| `TestDense.test_unit_norm_embedding` | embedding 的 L2 范数为 1 |
| `TestDense.test_paraphrased_query_finds_upload_doc` | 换说法 query 的 dense top-3 含 d2（实际是第 2） |
| `TestRRF.test_basic_fusion` | 两个列表中 a、b 互换第 1、2 名，c 都是第 3：融合后 a/b 在前、c 最后 |
| `TestRRF.test_weights_change_ranking` | BM25 权重 5 时，只在 BM25 列表中的 a 排第 1 |
| `TestRRF.test_weights_length_mismatch_raises` | 权重数与列表数不一致抛 `ValueError` |
| `TestRRF.test_smaller_k_concentrates_score_on_top` | k = 1 时第 1、2 名的分数比值大于 k = 1000 时 |
| `TestHybridRetriever.test_search_returns_three_lists` | 返回 bm25、dense、fused 三个键，fused 不超过 k_out |
| `TestHybridRetriever.test_fused_contains_union_of_top1s` | 两路的 top-1 都出现在融合结果中 |
| `TestHybridRetriever.test_literal_query_wins_in_fused` | 字面 query 融合后第 1 名是 d1 |

实际运行结果：

```text
...............                                                          [100%]
15 passed in 0.02s
```

测试没有覆盖：BM25 分数与手算值一致、讲义 Build It 中声称的各 query 名次、融合"在每类 query 上都赢"的说法（Q10 中有反例）、停用词与词干化行为。
