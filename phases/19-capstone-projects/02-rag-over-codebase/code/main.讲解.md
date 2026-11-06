# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 02 节 代码库 RAG——跨仓库 Semantic Search ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`re`、`collections`、`dataclasses`），无需网络、无需 API key
>
> 同目录下还有一个 TypeScript 版本（`code/ts/`，hono + zod 的 HTTP API，结构与本文件一一对应），不在本讲解范围内，文中只在对比处提到。

---

## 1. 这份代码在考察什么

讲义描述的是一个完整的跨仓库代码检索系统：tree-sitter 切块 → 三种表示（dense / BM25 / summary）→ hybrid 检索 → cross-encoder 重排 → 长上下文模型合成并强制引用 → git push 增量重建索引。`main.py` 只实现了其中**检索的核心骨架**：

1. **chunk 的数据形状**：`{repo, path, start_line, end_line, symbol, body, summary}`，以及由它生成的引用锚点 `repo/path:start-end`。
2. **两套索引并行**：一个"假的" dense 索引（哈希词袋向量 + 余弦）和一个**真的** BM25（从零实现，带字段加权）。
3. **Reciprocal Rank Fusion（RRF）**：只用名次把两路结果合并。
4. **Rerank**：用"查询与 symbol / summary 的词重叠"冒充 cross-encoder。
5. **编排**：`retrieve → fuse → rerank`，返回每一阶段的 top 结果，方便对比。

讲义里的 summary 生成、符号图、LLM 合成、citation 校验、增量索引、评估都**没有**实现。

> 一句话：**这是 hybrid 检索"召回—融合—重排"三段式的最小可运行模型；真正要学的是 BM25 和 RRF，而 dense 与 rerank 都是占位实现，而且各有坑。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Chunk` | dataclass | 一个函数/类级别的代码块；`anchor()` 生成 `repo/path:start-end` | AST-aware chunk、引用锚点 |
| `SAMPLE_CORPUS` | 常量列表 | 4 个仓库共 6 个手写 chunk（S3 重试、鉴权、rank fusion） | 被索引的语料 |
| `fake_embed` / `cosine` | 函数 | 哈希词袋向量（64 维、L2 归一化）与点积 | dense embedding 的替身 |
| `DenseIndex` | dataclass | 存 `(chunk, vector)`，暴力计算余弦并排序 | 向量库（Qdrant/pgvector） |
| `tokenize` | 函数 | `\w+` 小写分词 | BM25 分词 |
| `BM25Index` | dataclass | 字段加权的 BM25（symbol×4、summary×2、body×1） | 稀疏检索（Tantivy） |
| `rrf` | 函数 | `Σ 1/(60 + rank)` 合并两路结果，按锚点去重 | Reciprocal Rank Fusion |
| `rerank` | 函数 | 先验分数 + 0.3×symbol 重叠×3 + 0.1×summary 重叠，取 top-5 | cross-encoder 的替身 |
| `answer` | 函数 | 串起 dense、BM25、RRF、rerank，返回各阶段 top 锚点 | LangGraph 的 retrieve→rerank 节点 |
| `main` | 函数 | 建索引、跑 3 个示例问题并打印 | 演示入口 |

数据流：`SAMPLE_CORPUS` → 同时 `DenseIndex.add` 与 `BM25Index.add` → 对每个问题 `answer()`：`dense.search(k=10)` ∥ `bm25.search(k=10)` → `rrf()` → `rerank(top_k=5)` → 打印四行结果。

---

## 3. 逐段精讲

### 3.1 `Chunk`：一块代码 + 一个锚点

```python
@dataclass
class Chunk:
    repo: str
    path: str
    start_line: int
    end_line: int
    symbol: str
    body: str
    summary: str = ""

    def anchor(self) -> str:
        return f"{self.repo}/{self.path}:{self.start_line}-{self.end_line}"
```

- 字段与讲义 Build It 第 1 步的 chunk 记录一致，多了一个 `summary`（第 2 步由 Haiku 4.5 生成，这里是手写的）。
- `anchor()` 生成的 `uploader/services/retry.go:122-148` 就是答案里要求出现的引用格式，也是本文件中**去重和合并的主键**。
- 语料里的 `body` 不是真实代码，而是"代码的摘要式描述"（如 `"if ctx.Err() != nil { return abort() }; decrement bucket budget; retry with backoff"`）。真实系统中 body 来自 tree-sitter 抽出的函数源码。
- ⚠️ 用含行号的锚点当主键有隐患：文件上方插入一行，所有 chunk 的锚点都变了。讲义第 6 步说按 `(repo, path, symbol)` 去重，代码按锚点去重，两者不一致（见测验 Q15）。

### 3.2 `fake_embed`：一个"不确定"的确定性向量

```python
def fake_embed(text: str, dim: int = 64) -> list[float]:
    vec = [0.0] * dim
    for tok in re.findall(r"\w+", text.lower()):
        h = hash(tok)
        vec[h % dim] += 1.0
        vec[(h >> 8) % dim] += 0.5
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
```

- 思路是 feature hashing：每个词哈希到两个维度（权重 1.0 和 0.5），最后 L2 归一化，于是 `cosine` 只需点积。
- `or 1.0`：空文本时范数为 0，用 1.0 兜底避免除零。
- ⚠️ **最重要的问题**：Python 的 `hash(str)` 每个进程加随机盐（`PYTHONHASHSEED`），所以**每次运行的向量都不同**，docstring 说的 "deterministically offline" 并不成立。我们不设种子运行一次、再用 `PYTHONHASHSEED=0,1,2,3` 各运行一次，5 次运行中第一个问题的 dense top-3 出现了 4 种不同排序。修复：`zlib.crc32(tok.encode())` 或 `hashlib`；TS 版（`code/ts/src/index_store.ts`）用的就是 FNV-1a，注释写明 "so embeddings are stable across runs"。
- ⚠️ 即使修好，它也只是**带碰撞的词袋**：`authorization` 与 `permission` 毫无关系，64 维还会让无关词撞到同一维。它不具备任何"语义"，只是让管道能跑。

### 3.3 `DenseIndex`：暴力余弦

```python
    def add(self, chunk: Chunk) -> None:
        text = f"{chunk.symbol}\n{chunk.summary}\n{chunk.body}"
        self.vectors.append((chunk, fake_embed(text)))

    def search(self, query: str, k: int = 10) -> list[tuple[Chunk, float]]:
        qv = fake_embed(query)
        scored = [(c, cosine(qv, v)) for c, v in self.vectors]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]
```

- 把 symbol、summary、body 拼成一段文本做**一个**向量。讲义第 3 步其实是两个向量队列：代码一个、summary 一个（"summary adds a third retrievable modality"）。这里合并成一个，是简化。
- `sort(key=lambda x: -x[1])`：按分数降序；Python 的排序是稳定的，平局保持插入顺序。
- ⚠️ 没有分数阈值，`k=10` 又大于语料大小 6，所以**每个 chunk 都会被返回**，哪怕余弦只有 0.06。这些"凑数"的结果会一路流进 RRF 和 rerank，最后成为"引用"。
- 生产中用 HNSW 等 ANN 索引（Qdrant），而不是对所有向量逐个算余弦。

### 3.4 `BM25Index`：真正从零实现的 BM25

```python
    def add(self, chunk: Chunk) -> None:
        # field-weighted: symbol x4, summary x2, body x1
        tokens = (tokenize(chunk.symbol) * 4 +
                  tokenize(chunk.summary) * 2 +
                  tokenize(chunk.body))
        counts = Counter(tokens)
        self.docs.append(chunk)
        self.doc_lens.append(len(tokens))
        self.tf.append(counts)
        for term in counts:
            self.df[term] += 1
        self.avgdl = sum(self.doc_lens) / len(self.doc_lens)
```

- **字段加权**用"列表乘法重复 token"实现：`['a','b'] * 4` 得到 8 个元素。讲义第 4 步的权重是 symbol 4、body 1、summary 2，代码一致。
- `counts`（词频 tf）、`df`（文档频率）、`doc_lens`（文档长度）、`avgdl`（平均长度）是 BM25 需要的全部统计量。`df` 按 `counts` 的键累加，所以重复 token 不影响 df，这是对的。
- 实际文档长度为 `[44, 34, 30, 37, 31, 33]`，`avgdl ≈ 34.83`。
- ⚠️ 重复 token 同时拉长了 `dl`，与真正的 BM25F（每个字段先单独做长度归一化再加权）不同，见测验 Q14。
- ⚠️ `tokenize` 用 `\w+`，下划线属于 `\w`，且不拆驼峰：`check_permission` → `['check_permission']`，`AbortMultipartOnFail` → `['abortmultipartonfail']`。6 个 symbol 中只有 `evaluate` 能被普通英文单词命中，symbol ×4 的加权对自然语言查询几乎无效（测验 Q10）。

```python
    def search(self, query: str, k: int = 10) -> list[tuple[Chunk, float]]:
        q_terms = tokenize(query)
        n = len(self.docs)
        scores: list[float] = [0.0] * n
        for term in q_terms:
            if term not in self.df:
                continue
            idf = math.log((n - self.df[term] + 0.5) / (self.df[term] + 0.5) + 1.0)
            for i, counts in enumerate(self.tf):
                if term not in counts:
                    continue
                f = counts[term]
                dl = self.doc_lens[i]
                denom = f + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[i] += idf * f * (self.k1 + 1) / denom
        ranked = sorted(zip(self.docs, scores), key=lambda x: -x[1])
        return [(c, s) for c, s in ranked[:k] if s > 0]
```

- 标准 BM25 公式：`IDF · f·(k1+1) / (f + k1·(1 − b + b·dl/avgdl))`，`k1 = 1.5`、`b = 0.75`。
- IDF 用 Lucene 的 `+1` 版本，恒为正。N = 6 时：df = 1 → 1.540，df = 2 → 1.030，df = 3 → 0.693。
- `if term not in self.df: continue`：查询词在语料中不存在（如 `how`、`is`）就跳过，相当于天然去停用词。
- 最后 `if s > 0` 过滤掉零分文档——所以 BM25 的结果往往少于 k（第三个问题只返回 1 条），而 dense 永远返回全部。
- 外层遍历查询词、内层遍历所有文档，复杂度 `O(|q| · N)`；真实系统用倒排表只访问含该词的文档。
- 查询词重复会被重复计分（如 "abort abort"），标准 BM25 有时会对查询词频做单独处理，这里没有。

### 3.5 `rrf`：只看名次的融合

```python
def rrf(dense, sparse, k_rrf: int = 60):
    score: dict[str, float] = defaultdict(float)
    by_anchor: dict[str, Chunk] = {}
    for rank, (c, _) in enumerate(dense):
        score[c.anchor()] += 1.0 / (k_rrf + rank + 1)
        by_anchor[c.anchor()] = c
    for rank, (c, _) in enumerate(sparse):
        score[c.anchor()] += 1.0 / (k_rrf + rank + 1)
        by_anchor[c.anchor()] = c
    fused = sorted(score.items(), key=lambda x: -x[1])
    return [(by_anchor[a], s) for a, s in fused]
```

- `for rank, (c, _) in enumerate(dense)`：原始分数被 `_` 丢掉，**只用名次**。这正是 RRF 的精髓——dense 余弦（0～1）和 BM25（本例最高 6.41）尺度完全不同，直接相加没有意义。
- `rank + 1`：`enumerate` 从 0 开始，RRF 的名次从 1 开始。`k = 60` 来自 RRF 原论文的经验值，它让第 1 名（1/61）和第 10 名（1/70）的差距较小，避免某一路的第 1 名一家独大。
- 同时出现在两路中的文档分数相加，所以"两路都靠前"的文档胜出：两路都第 1 = 2/61 ≈ 0.0328；一路第 1 + 一路第 2 ≈ 0.0325；只在一路第 1 ≈ 0.0164。
- `defaultdict(float)`：第一次访问某个键时自动初始化为 0.0，可以直接 `+=`。
- `by_anchor` 记录锚点到 chunk 的映射，最后把分数还原成 `(Chunk, score)`。

### 3.6 `rerank`：词重叠冒充 cross-encoder

```python
def rerank(query, candidates, top_k=5):
    q_toks = set(tokenize(query))
    out = []
    for c, prior in candidates:
        symbol_overlap = len(q_toks & set(tokenize(c.symbol))) * 3
        summary_overlap = len(q_toks & set(tokenize(c.summary)))
        out.append((c, prior + 0.3 * symbol_overlap + 0.1 * summary_overlap))
    out.sort(key=lambda x: -x[1])
    return out[:top_k]
```

- 用集合交集 `&` 统计查询与 symbol、summary 的共有词。symbol 命中一个词加 `0.3 × 3 = 0.9`，summary 命中一个词加 `0.1`。
- **尺度问题**：RRF 先验最大只有 0.0328，而一个 summary 词就加 0.1，所以排序几乎完全由词重叠决定，RRF 只负责打破平局。第一个问题的实际分数：`AbortMultipartOnFail` 0.4325（4 个重叠词）、`abortUpload` 0.3325、`bucket_budget` 0.3318（各 3 个）。
- 由于 3.4 的分词问题，三个示例问题的 symbol 重叠**全部为 0**，`0.3 * symbol_overlap` 这一项从未生效。
- 真正的 cross-encoder（讲义：Cohere rerank-3 或 bge-reranker-v2-gemma-2b）把 `(query, chunk)` 一起送入 Transformer 输出相关性分数，通常直接**替代**先验分数排序，而不是叠加。
- ⚠️ 固定 `top_k=5`，没有分数阈值：只有一个相关 chunk 的问题也会凑满 5 条。

### 3.7 `answer` 与 `main`：编排

```python
def answer(query, dense, bm25):
    dense_hits = dense.search(query, k=10)
    sparse_hits = bm25.search(query, k=10)
    fused = rrf(dense_hits, sparse_hits)
    top = rerank(query, fused, top_k=5)
    citations = [c.anchor() for c, _ in top]
    return {
        "query": query,
        "dense_top": [c.anchor() for c, _ in dense_hits[:3]],
        ...
        "rerank_top": citations,
    }
```

- 对应讲义 LangGraph 的 `retrieve` 与 `rerank` 两个节点；`synth` 节点（LLM 合成 + 引用）和第 7 步的 citation 校验都没有实现，`citations` 只是 rerank 结果的锚点列表。
- 讲义参数是"rerank top-50 保留 top-10"，代码是"两路各 10 条、rerank 保留 5 条"，适配 6 个 chunk 的小语料。
- 两路检索在讲义里是并行的（"fires dense + BM25 in parallel"），这里是顺序调用。
- `main()` 把每个 chunk 同时加入两个索引，然后跑三个问题：S3 multipart abort、authorization、rank fusion。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手写 6 个 chunk，不跑 tree-sitter | 让检索逻辑可离线运行 | 生产用 tree-sitter 多语言语法切块，body 是真实源码 |
| 哈希词袋代替 embedding 模型 | 无网络、无依赖 | 没有语义能力；`hash()` 还导致跨进程不确定，应改用 `zlib.crc32` 或换真实模型 |
| 代码 + summary 合成一个向量 | 简单 | 讲义要求 summary 单独 embed 作为第三种检索模态 |
| 从零实现 BM25 | 这是"真的"算法，值得逐行理解 | 生产用 Tantivy/Elasticsearch 的倒排索引与 BM25F |
| 用重复 token 实现字段加权 | 一行代码就能表达 4/2/1 权重 | 同时拉长文档长度；分词不拆标识符使 symbol 权重失效 |
| RRF 融合（k=60） | 免调参、对分数尺度不敏感 | 也可用加权 RRF；Qdrant 已内置 |
| 词重叠 rerank | 无模型可用时的占位 | 分数尺度压过先验；生产用 cross-encoder，并对分数设阈值 |
| 按锚点去重 | 锚点唯一标识一个 chunk | 行号变化即主键变化；讲义建议 `(repo, path, symbol)` |
| 无合成、无引用校验、无增量索引 | 聚焦检索 | 讲义第 6–9 步才是完整系统 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值，可在旧版本 Python 中使用 `list[float]` 等写法 |
| `@dataclass` | `class Chunk:`、`class BM25Index:` | 自动生成 `__init__`、`__repr__`；字段按声明顺序成为构造参数 |
| 字段默认值 | `summary: str = ""`、`k1: float = 1.5` | 有默认值的字段必须放在无默认值字段之后 |
| `field(default_factory=...)` | `docs: list[Chunk] = field(default_factory=list)` | 可变默认值（列表、Counter）必须用工厂函数，否则所有实例共享同一个对象 |
| 类型注解 | `def search(self, query: str, k: int = 10) -> list[tuple[Chunk, float]]` | 只做文档和静态检查，运行时不强制 |
| f-string | `f"{self.repo}/{self.path}:{self.start_line}-{self.end_line}"` | 字符串内嵌表达式 |
| 正则 `re.findall` | `re.findall(r"\w+", text.lower())` | 返回所有匹配；`\w` 等价于 `[A-Za-z0-9_]`（以及 Unicode 字母），包含下划线 |
| 内置 `hash()` | `h = hash(tok)` | 对 `str` 每进程加随机盐，**不能**用于需要跨进程稳定的场景 |
| 位运算 | `(h >> 8) % dim` | 右移 8 位取另一段比特，得到第二个桶 |
| `or` 兜底 | `math.sqrt(...) or 1.0` | 左边为 0（假值）时取右边 |
| 列表推导式 | `[v / norm for v in vec]` | 逐元素构造新列表 |
| 列表乘法 | `tokenize(chunk.symbol) * 4` | 把列表重复 4 次拼接 |
| `zip` | `zip(a, b)`、`zip(self.docs, scores)` | 并行遍历两个序列 |
| `Counter` | `Counter(tokens)`、`self.df[term] += 1` | 计数字典，缺失键默认为 0 |
| `defaultdict(float)` | `score[c.anchor()] += ...` | 缺失键自动初始化为 0.0 |
| `enumerate` + 元组解包 | `for rank, (c, _) in enumerate(dense)` | 同时拿到下标和元素；`_` 表示不用的值 |
| `sort` / `sorted` 与 `key` | `scored.sort(key=lambda x: -x[1])` | 原地排序 / 返回新列表；`-x[1]` 实现降序；排序是稳定的 |
| 集合运算 | `q_toks & set(tokenize(c.symbol))` | 交集 |
| 切片 | `ranked[:k]`、`out[:top_k]` | 取前 k 个 |
| 带条件的推导式 | `[(c, s) for c, s in ranked[:k] if s > 0]` | 过滤零分 |
| 字典字面量返回 | `return {"query": query, ...}` | 用 `dict[str, object]` 注解 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，未设置 `PYTHONHASHSEED`；**注意：dense 那一行每次运行都可能不同**）：

```text
Q: how is S3 multipart abort wired into retry budget
  dense  : ['uploader/services/retry.go:122-148', 'client/libs/s3client/multipart.ts:44-61', 'uploader/config/budgets.yaml:34-51']
  sparse : ['uploader/services/retry.go:122-148', 'client/libs/s3client/multipart.ts:44-61', 'uploader/config/budgets.yaml:34-51']
  fused  : [retry.go, multipart.ts, budgets.yaml, opa.py, check.py]
  rerank : [retry.go, multipart.ts, budgets.yaml, opa.py, check.py]

Q: where is authorization centralized
  dense  : ['auth/libs/policy/opa.py:88-110', 'auth/services/authz/check.py:12-38', 'uploader/services/retry.go:122-148']
  sparse : ['auth/libs/policy/opa.py:88-110', 'auth/services/authz/check.py:12-38']
  fused  : [opa.py, check.py, retry.go, query.rs, multipart.ts]
  rerank : [opa.py, check.py, retry.go, query.rs, multipart.ts]

Q: how does rank fusion work
  dense  : ['catalog/services/search/query.rs:200-240', 'auth/libs/policy/opa.py:88-110', 'uploader/services/retry.go:122-148']
  sparse : ['catalog/services/search/query.rs:200-240']
  fused  : [query.rs, opa.py, retry.go, check.py, budgets.yaml]
  rerank : [query.rs, opa.py, retry.go, check.py, budgets.yaml]
```

（fused / rerank 行为节省篇幅只保留了文件名，实际输出是完整锚点。）

逐项解读（BM25 分数来自同一次额外的打印）：

- **sparse 行稳定**：第一个问题 BM25 分数为 `AbortMultipartOnFail 6.41`、`abortUpload 4.61`、`bucket_budget 3.96`，只返回 3 条（其余为 0 分被过滤）；第二个问题只有 `evaluate 1.52`、`check_permission 1.44` 两条——靠的是 summary 里的 `authorization`；第三个问题只有 `rank_fusion 4.48` 一条。
- **dense 行不稳定**：用 `PYTHONHASHSEED=0..3` 重跑，第一个问题的 dense top-3 分别变成 `[retry.go, budgets.yaml, opa.py]`、`[retry.go, budgets.yaml, multipart.ts]`、`[multipart.ts, retry.go, budgets.yaml]`、`[retry.go, budgets.yaml, multipart.ts]`，原因见 3.2。
- **rerank 前三名基本稳定**：第一个问题始终是三个 S3 相关 chunk，因为 summary 重叠（4/3/3 个词，+0.4/+0.3/+0.3）远大于 RRF 先验（≤ 0.033）。第二个问题始终是两个 auth chunk（各命中 `authorization`），但这两者之间的先后会随 dense 的随机名次变化。
- **后两名是"凑数"**：每个问题都返回 5 个锚点。第三个问题真正相关的只有 `query.rs`，其余 4 个（`opa.py`、`retry.go`、`check.py`、`budgets.yaml`）的 rerank 分数只有约 0.016，纯粹因为 dense 没有阈值、rerank 固定取 5 条。如果把它们当作"引用"交给用户，就违背了讲义的 citation faithfulness。
- **与讲义 "Use It" 的对比**：讲义展示的 `[retrieve] 12 chunks dense + 7 chunks bm25, 16 unique after dedup`、cache 命中率、合成答案等，是完整系统的示意输出，本代码不会打印这些。

---

## 7. 动手改一改

1. **修复不确定性**：把 `hash(tok)` 换成 `zlib.crc32(tok.encode("utf-8"))`，用 `PYTHONHASHSEED=0` 和 `1` 各跑一次，确认输出完全一致。
2. **修复标识符分词**：实现 `split_identifier`（测验 Q10），在 `BM25Index.add` 和 `rerank` 中对 symbol 使用它（查询侧也要用同样的分词），观察 BM25 第三个问题的 `rank_fusion` 分数和 rerank 中 symbol 项的变化。
3. **加阈值**：给 `DenseIndex.search` 加 `min_score`，给 `rerank` 加 `min_score`，让第三个问题只返回真正相关的 1～2 条。思考阈值应该设在哪一层（提示：RRF 分数只反映名次）。
4. **实现评估**：为三个问题标注金标准锚点，写 `mrr_at_k` 与 `ndcg_at_k`，比较"只用 dense""只用 BM25""RRF""RRF + rerank"四种配置（讲义 Build It 第 9 步的缩小版）。
5. **summary 作为独立模态**：给 `DenseIndex` 增加第二组只对 `summary` 计算的向量，三路结果一起做 RRF；把 `check_permission` 的 summary 改写成包含 "authz" 的版本，体会讲义说的 "summary adds a third retrievable modality"。
6. **进阶：增量索引**：给每个 chunk 计算 `content_hash`，写一个 `apply_diff(old_chunks, new_chunks)`，只对新增或内容变化的 chunk 调用 `add`，删除消失的 chunk（需要为 BM25 实现删除并维护 `df`、`avgdl`）。

---

## 8. 常见坑

- **用 `hash()` 做"确定性"哈希**：字符串哈希每进程不同，缓存、分片、离线向量都会因此错乱；需要稳定哈希请用 `zlib.crc32`、`hashlib`。
- **索引侧与查询侧分词不一致**：只在建索引时拆驼峰、查询时不拆（或反过来），命中率会莫名其妙地下降。
- **`\w` 含下划线**：`snake_case` 不会被 `\w+` 拆开；代码检索几乎总需要专门的标识符分词。
- **把不同检索器的原始分数直接相加**：BM25 与余弦尺度不同，应先融合名次（RRF）或做归一化。
- **把 RRF 分数当相关性**：RRF 只反映名次，不能用来判断"是否相关"；阈值应设在 reranker 分数上。
- **固定 top-k 当引用**：没有阈值时，小语料或冷门问题会把无关 chunk 当成引用返回。
- **用含行号的锚点做主键**：代码一移动，所有 chunk 都"变了"，增量索引退化为全量。
- **重复 token 做字段加权时忽略文档长度变化**：字段权重越大，文档越"长"，body 中其它词的得分被压低。
