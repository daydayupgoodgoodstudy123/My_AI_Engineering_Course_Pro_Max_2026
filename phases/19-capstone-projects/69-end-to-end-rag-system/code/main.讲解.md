# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 69 节 端到端 RAG 系统 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（退出码 0 表示全部指标达标；测试：`python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`） ｜ **依赖**：第三方 `torch`；其余为标准库（`math`、`re`、`sys`、`time`、`collections`、`dataclasses`、`typing`）。无需 GPU、网络或 API key。

---

## 1. 这份代码在考察什么

这份代码把第 64–68 节的组件压缩进一个文件，组装成一条可运行的端到端 RAG 流水线，并以"自终止 demo"的形式充当 CI 冒烟测试：

1. **Chunker**（第 64 节）：递归字符切分，产出带 `doc_id:chunk_index` 锚点的 `Chunk`。
2. **HybridIndex**（第 65 节）：BM25 + 哈希稠密向量 + RRF。
3. **Rewriter**（第 67 节）：按启发式规则选择 decompose / hyde / multiquery。
4. **CrossEncoder 重排**（第 66 节）：一个更小的 PyTorch cross-encoder，分数再与词法重叠率混合。
5. **带引用的生成器**：从 top-3 中挑选 chunk，每个取第一句并附 `[doc_id:chunk_index]`，低分时拒答。
6. **评估与门禁**（第 68 节）：文档级 recall@5、precision@1、MRR 以及 faithfulness、answer relevance，与阈值比较后决定进程退出码。

> 一句话：**用一个编排文件把"入库 → 改写 → 检索 → 重排 → 生成 → 评估"串起来，并让评估结果直接决定 CI 成败**。同时要看清：在这个 fixture 上 chunker 是空操作、HyDE 分支不可达、拒答从不触发、precision@1 恰好压线——端到端 demo 的"PASS"远不等于系统可用。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tokenize` / `_STOP` / `_content_tokens` | 函数 / 常量 | 分词、停用词、内容词集合 | 预处理 |
| `_stable_hash` / `mock_embed` / `cosine` | 函数 | 确定性哈希、96 维哈希向量（词 + 字符 bigram） | 稠密检索替身 |
| `Chunk` | dataclass | `doc_id`、`chunk_index`、`text`，`anchor()` 返回 `"d6:0"` | 引用单元 |
| `DEFAULT_SEPARATORS` / `_recursive_split` / `Chunker` | 常量 / 函数 / dataclass | 按 `"\n\n"`、`"\n"`、`". "`、`" "` 递归切分并贪心打包到 `target` 字符 | 递归切分 |
| `BM25Index` / `DenseIndex` / `rrf` / `HybridIndex` | dataclass / 函数 | 词法 + 稠密检索，RRF 融合；`search_with_hypothetical` 供 HyDE | hybrid 检索 |
| `_REWRITE_HYDE` / `Rewriter` | 常量 / dataclass | 策略选择与三种改写 | 查询改写 |
| `_token_to_id` / `tokenize_pair` / `CrossEncoder` | 函数 / `nn.Module` | 第 66 节模型的压缩版（d_model 48） | cross-encoder |
| `TRAIN_TRIPLES` / `train_reranker` | 常量 / 函数 | 17 条三元组，全批量 Adam + MSE 80 轮 | 重排训练 |
| `rerank` | 函数 | cross-encoder 分数 + 0.3 × 内容词重叠率 | 混合重排 |
| `REFUSE_THRESHOLD` / `REFUSE_TEXT` / `generate_answer` | 常量 / 函数 | 选 chunk、取首句、附锚点、低分拒答 | 带引用生成 |
| `Result` / `Pipeline` | dataclass | 组合五个阶段；`ingest`、`train_reranker_on`、`query` | 编排 |
| `CORPUS` / `EvalQuery` / `EVAL_QUERIES` | 常量 / dataclass | 12 篇文档、4 个评估 query | fixture |
| `doc_level_recall` / `doc_level_precision` / `doc_level_mrr` | 函数 | chunk 级结果映射为文档级指标 | 检索指标 |
| `faithfulness_score` / `answer_relevance_score` | 函数 | 去掉锚点后的 claim 支持率；问答词汇重叠 | 答案指标 |
| `THRESHOLDS` / `build_pipeline` / `run_eval` / `run_demo` | 常量 / 函数 | 构建、评估、打印、返回退出码 | CI 门禁 |

数据流：`run_demo` → `build_pipeline()`（`Pipeline()` 构造时创建并固定种子的 `CrossEncoder` → `ingest(CORPUS)` 切块入索引 → `train_reranker_on(TRAIN_TRIPLES)`）→ 打印一条 query 的完整轨迹 → `run_eval`：对 4 个 eval query 调 `p.query()`，累加 5 项指标并取平均 → 与 `THRESHOLDS` 比较 → `sys.exit(0 或 1)`。

`Pipeline.query` 内部：`pick_strategy` → 生成改写 → 检索候选（HyDE / 多路 RRF / 直接检索三选一）→ `rerank` 取 top-5 → `generate_answer` → `Result`。

---

## 3. 逐段精讲

### 3.1 共享的分词、停用词与哈希向量

```python
_STOP = {"the", "a", "an", "is", "are", "of", "to", "in", "on", "at", "for",
         "with", "and", "or", "as", "by", "do", "you", "we", "our", "how",
         "what", "where", "when", "which", "before", "after"}


def _content_tokens(text: str) -> set[str]:
    return {t for t in tokenize(text) if t not in _STOP and len(t) > 1}


def _stable_hash(tok: str) -> int:
    h = 0
    for ch in tok:
        h = (h * 1315423911) ^ ord(ch)
        h &= 0xFFFFFFFF
    return h
```

- 本文件把第 66、67 节中重复出现的哈希逻辑抽成了 `_stable_hash`，`mock_embed` 与 `_token_to_id` 共用。
- 为什么不用 Python 内置 `hash()`？因为字符串的内置哈希在每个进程中带随机盐（`PYTHONHASHSEED`），不同运行结果不同；自写哈希保证跨进程确定。
- `_STOP` 与第 68 节 `_content_tokens` 的停用词表**不同**（本节更短，例如不含 does、can、who、why），answer relevance 的阈值也从 0.4 变成了 0.3。两节的"相关性"不能直接比较。
- `mock_embed` 与第 67 节完全相同（词哈希两个桶 + 字符 bigram）。

### 3.2 Chunk 与递归切分

```python
@dataclass
class Chunk:
    doc_id: str
    chunk_index: int
    text: str

    def anchor(self) -> str:
        return f"{self.doc_id}:{self.chunk_index}"
```

- `Chunk` 是贯穿所有阶段的记录：检索返回它、重排给它打分、生成器引用它的锚点、评估按它的 `doc_id` 去重。
- 锚点 `doc_id:chunk_index` 在 RRF 中也被用作去重键（同一 chunk 在多条排名中出现时合并分数）。

```python
def _recursive_split(text: str, separators: tuple[str, ...], target: int) -> list[str]:
    if len(text) <= target or not separators:
        return [text] if text else []
    sep = separators[0]
    rest = separators[1:]
    if sep not in text:
        return _recursive_split(text, rest, target)
    parts = text.split(sep)
    pieces: list[str] = []
    for p in parts:
        if not p:
            continue
        if len(p) <= target:
            pieces.append(p)
        else:
            pieces.extend(_recursive_split(p, rest, target))
    packed: list[str] = []
    for p in pieces:
        if packed and len(packed[-1]) + len(sep) + len(p) <= target:
            packed[-1] = packed[-1] + sep + p
        else:
            packed.append(p)
    return packed
```

- **递归**：先用最"粗"的分隔符（段落 `\n\n`）切，切出来仍然超长的片段再用更细的分隔符（换行、句号空格、空格）切。这是 LangChain 式 recursive character splitter 的思路：尽量在语义边界处断开。
- **贪心打包**：切碎后再把相邻的小片段用当前分隔符拼回去，直到接近 `target`，避免产生大量碎块。
- **终止条件**：文本不超长，或分隔符用完（此时即使超长也原样返回——单个超长"单词"不会被硬切）。
- ⚠️ `text.split(sep)` 会删除分隔符，只有在打包时被重新拼接的位置才补回分隔符；**chunk 边界处的分隔符丢失**。例如 `target=60` 时 d2 被切成 `['Large files are split into parts', 'Cancelled uploads release the reserved keys after three', 'failed parts.']`，第一个 chunk 丢了句号，关键事实 "three failed parts" 被切成两半。
- ⚠️ `Chunker.target` 默认 400，而 12 篇文档都只有 89–137 个字符，所以**每篇恰好一个 chunk**（demo 打印 `chunks indexed: 12`）。在这个 fixture 上 chunker 什么都没做，chunk 级与文档级完全等价。
- `Chunker.chunk` 用 `enumerate` 给每片编号，并 `strip()` 掉首尾空白、过滤空片。

### 3.3 Hybrid 索引

```python
    def search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        ...
        ranked = sorted(zip(self.chunks, scores), key=lambda x: -x[1])
        return [(c, s) for c, s in ranked[:k] if s > 0]
```

- BM25 部分与第 67 节相同（k1 = 1.5、b = 0.75、Lucene 式 IDF），但没有标题加权（`Chunk` 没有标题字段），并且**过滤掉 0 分结果**——与 query 毫无交集的 chunk 不会在 RRF 中拿到名次分。这是对第 67 节实现的一个改进。
- 稠密检索不过滤，永远返回 `k` 个。

```python
    def search(self, query: str, k_each: int = 8, k_out: int = 12) -> list[Chunk]:
        b = self.bm25.search(query, k_each)
        d = self.dense.search(query, k_each)
        return [c for c, _ in rrf([b, d])[:k_out]]

    def search_with_hypothetical(self, query, hypothetical, k_each=8, k_out=12):
        b = self.bm25.search(query, k_each)
        d = self.dense.search_vec(mock_embed(hypothetical), k_each)
        return [c for c, _ in rrf([b, d])[:k_out]]
```

- 每路取 8 个，融合后最多 16 个（去重后 ≤ 12），再截到 `k_out`。返回值去掉了分数，只给 `Chunk` 列表。
- `search_with_hypothetical` 与第 67 节一样：BM25 用原 query，稠密用假设文档向量。
- `Pipeline.top_n = 12` 等于语料大小，实测候选数在 8–11 之间——第一阶段几乎没有过滤作用，recall@5 主要取决于重排。

### 3.4 Rewriter：策略选择

```python
@dataclass
class Rewriter:
    def pick_strategy(self, query: str) -> str:
        if " and " in query.lower():
            return "decompose"
        if any(t in tokenize(query) for t in ("api", "function", "endpoint", "config")):
            return "hyde"
        return "multiquery"

    def rewrite_hyde(self, query: str) -> str | None:
        return _REWRITE_HYDE.get(query.lower().strip().rstrip("?"))

    def rewrite_multiquery(self, query: str) -> list[str]:
        base = query.strip().rstrip("?")
        toks = [t for t in tokenize(base) if t not in _STOP]
        variants: list[str] = [base]
        if toks:
            variants.append(" ".join(toks))
        return list(dict.fromkeys(v for v in variants if v))

    def rewrite_decompose(self, query: str) -> list[str]:
        parts = re.split(r"\s+and\s+", query, flags=re.IGNORECASE)
        out = [p.strip().rstrip("?") for p in parts if p.strip()]
        return out or [query.strip().rstrip("?")]
```

- **策略规则**：连词 → decompose；术语关键词 → hyde；默认 multiquery。讲义写的是"by query length and presence of conjunctions"，代码并没有使用 query 长度。
- **multiquery**：只有两个变体——原句和"去停用词版本"（如 `'stop long running worker'`），不是真正的改写；`dict.fromkeys` 用来**保序去重**（两者相同时只留一个）。
- **decompose**：按 "and" 拆分，没有防过度拆分（第 67 节测验 Q11 的问题依然存在）。
- ⚠️ **HyDE 分支不可达**：`rewrite_hyde` 只在 query 恰好等于表中 4 个 key 时返回非 None，而这 4 个 key 都不含 api/function/endpoint/config，`pick_strategy` 不可能对它们返回 "hyde"。当别的 query 被判为 "hyde" 时，`rewrite_hyde` 返回 None，`Pipeline.query` 会落到"直接检索原 query"的分支，但 `rewriter_strategy` 仍报告 "hyde"。
- ⚠️ `_REWRITE_HYDE` 的"假设文档"几乎就是 gold 文档原文（e1 与 d3、e4 与 d7 逐字相同）。如果这个分支被"修通"，就是把答案直接塞进检索向量，属于评估泄漏。
- 实测 4 个 eval query **全部走 multiquery**。

### 3.5 压缩版 cross-encoder 与训练

```python
class CrossEncoder(nn.Module):
    def __init__(self, d_model: int = 48, n_heads: int = 4, ff_hidden: int = 96,
                 max_len: int = 96) -> None:
        super().__init__()
        torch.manual_seed(SEED)
        ...
```

- 结构与第 66 节完全相同（token/type/position embedding → 多头注意力 → post-norm → GELU FFN → post-norm → 去 PAD 的 mean-pooling → 线性头），只是维度从 64 降到 48、FFN 从 128 降到 96。实测参数量 416,929，其中 token embedding 8192 × 48 = 393,216（约 94%）。
- `forward` 中的形状：`(B, 96)` → `(B, 96, 48)` → 池化 `(B, 48)` → `(B,)`。
- 构造函数里 `torch.manual_seed(SEED)`，所以 `Pipeline()` 每次创建的 reranker 初始权重都相同，`build_pipeline()` 的结果可复现。

```python
TRAIN_TRIPLES: list[tuple[str, str, float]] = [
    ("function for centralized auth check",
     "Authorization is centralized in check_permission ...", 1.0),
    ("function for centralized auth check",
     "A central permission gate inherits roles ... see d4.", 0.1),
    ...
]
```

- 17 条 `(query, 文档文本, 标签)` 元组，覆盖 auth、abort、fusion、worker 四类。注释说明了设计意图：每类配一个**困难负例**（hard negative），专门教模型避开 lexical baseline 会误选的干扰文档。
- 讲义说本节用"a smaller fixture training set"，实际是 17 条，比第 66 节的 14 条还多。
- 讲义说 "The demo's eval queries are deliberately disjoint from the rerank training set"——query 字符串确实不重叠，但**训练用的文档文本就是语料原文**，困难负例恰好是 eval 中的干扰文档（d9、d10、d11、d12）。这是文档层面的泄漏：模型直接学过"d11 对授权类问题打低分"。
- `train_reranker` 与第 66 节 `train_tiny` 相同：全批量 Adam、MSE、80 轮。实测 loss 从 0.4673 降到约 7e-5，几乎完全记住了训练集。

### 3.6 混合重排

```python
def rerank(model, query, candidates, top_k, overlap_weight=0.3):
    if not candidates:
        return []
    model.eval()
    ...
    with torch.no_grad():
        ce_scores = model(torch.tensor(ids, dtype=torch.long),
                          torch.tensor(tids, dtype=torch.long)).tolist()
    q_tokens = _content_tokens(query)
    blended = []
    for c, ce in zip(candidates, ce_scores):
        c_tokens = _content_tokens(c.text)
        overlap = len(q_tokens & c_tokens) / max(1, len(q_tokens))
        blended.append((c, ce + overlap_weight * overlap))
    blended.sort(key=lambda x: -x[1])
    return blended[:top_k]
```

- 一次 batch 前向给全部候选打分，然后加上 `0.3 × (query 内容词在 chunk 中出现的比例)`。
- docstring 坦白了动机："A small cross-encoder (this lesson) is noisy on out-of-training-set queries. A production-shaped fix is to mix in a lexical overlap signal at score time." 生产中确实常见"多信号加权融合"（如重排分数与第一阶段分数、时效性等加权）。
- 我们做的消融（候选集与 pipeline 相同）：

| 排序方式 | precision@1 | MRR | recall@5 |
|---------|-------------|-----|----------|
| 不重排（multiquery 融合顺序） | 0.25 | 0.583 | 1.0 |
| 只用 cross-encoder（`overlap_weight=0`） | 0.25 | 0.487 | 1.0 |
| 默认 `overlap_weight=0.3` | 0.50 | 0.708 | 1.0 |
| `overlap_weight=1.0` | 0.75 | 0.875 | 1.0 |
| `overlap_weight=3.0` | 0.50 | 0.750 | 1.0 |
| 只用重叠率 | 0.25 | 0.625 | 1.0 |

  单独的 cross-encoder 比不重排还差；只有两种信号混合时才超过两者。讲义学习目标 "prove the staged build wins on every metric over the same components in isolation" 在代码中没有实现，这张表也不支持"每个指标都赢"。而用 4 个 eval query 去挑 `overlap_weight`，本身就是在测试集上调参。

### 3.7 带引用的生成器与拒答

```python
REFUSE_THRESHOLD = 0.05
REFUSE_TEXT = "I do not know."


def generate_answer(query, ranked):
    if not ranked:
        return REFUSE_TEXT, []
    top_chunk, top_score = ranked[0]
    if top_score < REFUSE_THRESHOLD:
        return REFUSE_TEXT, []
    q_tokens = _content_tokens(query)
    scored_chunks = []
    for c, s in ranked[:3]:
        overlap = len(q_tokens & _content_tokens(c.text))
        scored_chunks.append((c, overlap, s))
    scored_chunks.sort(key=lambda x: (-x[1], -x[2]))
    selected = [t for t in scored_chunks if t[1] > 0][:2] or [scored_chunks[0]]
    sentences = []
    citations = []
    for c, _, _ in selected:
        first_sentence = re.split(r"(?<=[.!?])\s+", c.text.strip(), maxsplit=1)[0]
        sentences.append(f"{first_sentence} [{c.anchor()}]")
        citations.append(c.anchor())
    return " ".join(sentences), citations
```

- **选 chunk**：在 top-3 中按"与 query 共有的内容词个数"降序、再按重排分数降序排序，取重叠 > 0 的前 2 个。排序键 `(-x[1], -x[2])` 是元组比较：先比第一个元素，相等再比第二个。
- **取首句**：`re.split(..., maxsplit=1)[0]` 只切一刀，取第一句。
- **引用**：每句后附 `[doc_id:chunk_index]`，同时返回 `citations` 列表。
- 这一步会**重新挑选**重排结果：e2 的 top-1 是 d1（错），但 d4 在 top-3 且与 query 有重叠（"centralized" 不等于 "central"，但 "permission" 命中），所以答案仍然引用了 d4。这让 precision@1 只有 0.5 时 answer relevance 仍为 1.0——生成器"掩盖"了重排的错误。
- ⚠️ **拒答几乎不可能触发**：
  1. 阈值作用在"cross-encoder 回归分数 + 重叠"这个未校准的分数上，cross-encoder 对任何 query 都会给某些文档 ~1 的分数；
  2. `or [scored_chunks[0]]` 兜底：top-3 与 query 完全没有重叠时仍然用 top-1 作答。
  实测 "what is the capital of france" 得到了 d1 的第一句加引用。修复见测验 Q9。
- 讲义说 mock 生成器"cannot hallucinate because it only emits text from the retrieved chunks"——它确实不会编造句子，但会**答非所问**（把不相关文档的句子当答案并附上引用），这同样是线上需要防范的失败。

### 3.8 Pipeline 编排

```python
@dataclass
class Pipeline:
    chunker: Chunker = field(default_factory=Chunker)
    index: HybridIndex = field(default_factory=HybridIndex)
    rewriter: Rewriter = field(default_factory=Rewriter)
    reranker: CrossEncoder = field(default_factory=CrossEncoder)
    top_n: int = 12
    top_k: int = 5

    def query(self, question: str) -> Result:
        latencies: dict[str, float] = {}

        t0 = time.perf_counter()
        strategy = self.rewriter.pick_strategy(question)
        hypothetical = self.rewriter.rewrite_hyde(question) if strategy == "hyde" else None
        subqueries: list[str] = []
        if strategy == "multiquery":
            subqueries = self.rewriter.rewrite_multiquery(question)
        elif strategy == "decompose":
            subqueries = self.rewriter.rewrite_decompose(question)
        t1 = time.perf_counter()
        latencies["rewrite"] = (t1 - t0) * 1000

        if hypothetical:
            candidates = self.index.search_with_hypothetical(question, hypothetical, k_out=self.top_n)
        elif len(subqueries) > 1:
            rankings = []
            for q in subqueries:
                hits = self.index.search(q, k_out=self.top_n)
                rankings.append([(c, 1.0) for c in hits])
            fused = rrf(rankings)
            candidates = [c for c, _ in fused[: self.top_n]]
        else:
            candidates = self.index.search(question, k_out=self.top_n)
        ...
```

- **依赖注入**：五个阶段都是 dataclass 字段，可以在构造时替换（讲义："Every stage is swappable"）。`default_factory=CrossEncoder` 意味着 `Pipeline()` 会创建一个新的（未训练的）模型，需要再调用 `train_reranker_on`。
- **三条检索路径**：有假设文档 → HyDE 检索；子查询多于 1 个 → 每个子查询检索后 RRF；否则 → 直接检索原 query。`(c, 1.0)` 只是为了满足 `rrf` 的输入格式，分数本身不被使用。
- **分阶段计时**：`time.perf_counter()` 在每个阶段前后打点，存入 `latencies`（毫秒）。讲义提醒这只测 CPU 工作，真实系统中 LLM 调用才是大头。
- 返回 `Result(answer, citations, top_k, rewriter_strategy, latency_ms)`，讲义中写的是 `Result(answer, top_k, latency_ms_per_stage)`，代码多了引用和策略字段。
- 注意 `top_n` 字段与 `generate_answer` 中的 top-3、`rerank` 的 `top_k=5` 是三个不同的截断点。

### 3.9 文档级指标

```python
def doc_level_recall(retrieved_chunks, gold, k):
    if not gold:
        return 0.0
    top_docs = {c.doc_id for c, _ in retrieved_chunks[:k]}
    return len(top_docs & gold) / len(gold)


def doc_level_precision(retrieved_chunks, gold, k):
    if k <= 0:
        return 0.0
    top_docs = [c.doc_id for c, _ in retrieved_chunks[:k]]
    if not top_docs:
        return 0.0
    return sum(1 for d in top_docs if d in gold) / len(top_docs)


def doc_level_mrr(retrieved_chunks, gold):
    seen: set[str] = set()
    rank = 0
    for c, _ in retrieved_chunks:
        if c.doc_id in seen:
            continue
        seen.add(c.doc_id)
        rank += 1
        if c.doc_id in gold:
            return 1.0 / rank
    return 0.0
```

- **recall**：取 top-k 个 **chunk**，转成文档集合后与 gold 求交。注意它是"top-k chunk"而不是"top-k 文档"，同一文档的多个 chunk 会占用多个位置。
- **precision**：分母是 `len(top_docs)` 而不是 `k`——与第 68 节 `precision_at_k`（分母为 k）口径不同；而且 `top_docs` 没有去重，同一文档的两个 chunk 都命中会被算两次。
- **MRR**：按"不同文档"计名次，同一文档的后续 chunk 被跳过。
- 在本 fixture 上每篇文档只有一个 chunk，这些区别都不会体现出来。

### 3.10 答案指标

```python
def faithfulness_score(answer, top_k):
    if not top_k:
        return 1.0 if answer == REFUSE_TEXT else 0.0
    ctx_tokens = set()
    for c, _ in top_k:
        ctx_tokens |= _content_tokens(c.text)
    body = re.sub(r"\[[^\]]+\]", "", answer)
    claims = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body.strip()) if s.strip()]
    ...
        if len(c_tokens & ctx_tokens) / len(c_tokens) >= 0.4:
            supported += 1
    ...
    return supported / counted
```

- 先用 `re.sub(r"\[[^\]]+\]", "", answer)` 去掉所有 `[...]` 锚点，否则锚点会被当成一个独立的"claim"（注释说明了这一点）。
- 上下文是 top-K 全部 chunk 内容词的并集；claim 内容词重叠率 ≥ 0.4 即视为支持。
- 空 top-K 时：拒答得 1.0（不说就不会错），否则 0.0。但若 top-K 非空而生成器拒答，`REFUSE_TEXT` 的内容词 `{not, know}` 与上下文无交集，faithfulness 会是 0——同样是拒答，两种情况得分不一致。
- 由于答案是 top-K 中 chunk 的原句，faithfulness 在本 fixture 上**结构性为 1.0**，阈值 0.75 形同虚设（讲义 "Mock generator hides hallucination risk" 也承认）。
- `answer_relevance_score` 去锚点后，用问题内容词在答案中出现的比例，阈值 0.3。

### 3.11 自终止 demo

```python
THRESHOLDS = {
    "recall@5":         0.75,
    "precision@1":      0.50,
    "mrr":              0.60,
    "faithfulness":     0.75,
    "answer_relevance": 0.75,
}

def run_demo() -> int:
    ...
    for name, threshold in THRESHOLDS.items():
        observed = metrics[name]
        ok = observed >= threshold
        ...
    if failed:
        print(f"== demo FAILED: {failed} ==")
        return 1
    print("== demo PASSED ==")
    return 0


if __name__ == "__main__":
    sys.exit(run_demo())
```

- 先打印一条 query 的完整轨迹（策略、top-3、答案、引用、各阶段延迟），再跑评估、逐项打印 PASS/FAIL。
- 返回值通过 `sys.exit` 变成**进程退出码**：CI 系统只看退出码就能判断成败。这就是讲义说的 "This is the shape a CI smoke test takes."
- `print(f"  latency_ms: { {k: round(v, 2) for k, v in result.latency_ms.items()} }")`：f-string 里的 `{ {...} }` 两侧加了空格，避免 `{{` 被解析成转义的字面量大括号，内部是一个字典推导式。
- ⚠️ 讲义说 "The thresholds are deliberately tight on the fixture"。实际上 precision@1 = 0.500 **恰好等于**阈值 0.50（再错一个 query 就会失败），而 faithfulness 恒为 1.0、recall@5 恒为 1.0（候选几乎是全库），这两项阈值不起作用。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 单文件编排、五个阶段作为 dataclass 字段 | 接口清晰、可替换，符合讲义"one orchestrator" | 文件很长；生产中每个阶段放独立模块，编排层只依赖接口 |
| 自写确定性哈希 | 跨进程可复现 | 无语义；生产用真实 tokenizer 与 embedding 模型 |
| 递归字符切分 | 尽量在自然边界断开 | 丢失边界分隔符；`target=400` 在本语料上等于不切块，chunk 相关逻辑没被检验 |
| BM25 过滤 0 分结果 | 避免无关 chunk 在 RRF 中拿名次分 | 与第 67 节实现不一致 |
| 启发式策略选择 | 简单可解释 | HyDE 分支不可达；multiquery 只是"去停用词"；生产可用分类器或 LLM 选择 |
| 小 cross-encoder + 词法混合 | 弥补小模型在训练集外的噪声 | 混合权重在 eval 上调出来，存在过拟合；生产应换成预训练 reranker 并在验证集上调权 |
| 困难负例来自语料原文 | 让 reranker 学会避开干扰文档 | 与 eval 文档重叠，结论偏乐观 |
| 抽取式生成 + 首句 + 锚点 | 无需 LLM，引用格式清晰 | faithfulness 恒为 1；首句可能不是答案所在句；生产用 LLM + 引用约束 prompt |
| 阈值拒答（0.05） | 演示"安全阀"的位置 | 分数未校准且有兜底分支，拒答从不触发 |
| 文档级指标 | chunk 粒度变化不影响指标 | precision 分母与第 68 节不同，且未去重 |
| `sys.exit(run_demo())` | 直接充当 CI 门禁 | 阈值没有余量或已饱和；应基于历史基线设"不回退"阈值 |
| `Pipeline()` 内部固定种子 | 可复现 | 改变全局 RNG 状态 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 中的方法 | `Chunk.anchor()`、`Chunker.chunk()` | dataclass 也可以定义普通方法 |
| 元组类型的默认值 | `separators: tuple[str, ...] = DEFAULT_SEPARATORS` | 元组不可变，可以直接作 dataclass 默认值（列表不行） |
| `field(default_factory=...)` 嵌套组件 | `index: HybridIndex = field(default_factory=HybridIndex)` | 每个 `Pipeline` 实例创建自己的索引与模型 |
| 递归函数 | `_recursive_split` 调用自身 | 每次使用更细的分隔符，`not separators` 为终止条件 |
| 元组切片 | `separators[0]`、`separators[1:]` | 取第一个与其余部分 |
| `list.extend` vs `append` | `pieces.extend(_recursive_split(...))` | `extend` 逐个加入元素，`append` 把整个列表作为一个元素加入 |
| `packed[-1]` | `packed[-1] = packed[-1] + sep + p` | 修改列表最后一个元素 |
| 带条件过滤的列表推导式 | `[(c, s) for c, s in ranked[:k] if s > 0]` | 先切片再过滤 |
| `dict.fromkeys` 保序去重 | `list(dict.fromkeys(v for v in variants if v))` | 字典键唯一且保持插入顺序 |
| `any()` + 生成器 | `any(t in tokenize(query) for t in ("api", ...))` | 只要有一个为真就返回 True，且会短路 |
| `str \| None` 返回值 | `def rewrite_hyde(self, query) -> str \| None` | 可能返回 None，调用方需判断 |
| `x or y` 兜底列表 | `out or [query.strip().rstrip("?")]`、`[...][:2] or [scored_chunks[0]]` | 左边为空列表时使用右边 |
| 元组作为排序键 | `scored_chunks.sort(key=lambda x: (-x[1], -x[2]))` | 先按第一个键，再按第二个键 |
| `re.split(..., maxsplit=1)` | 取答案首句 | 最多切一次，提高效率 |
| `re.sub` 删除模式 | `re.sub(r"\[[^\]]+\]", "", answer)` | `[^\]]+` 匹配不含 `]` 的字符序列，删除所有方括号锚点 |
| 集合原地并集 | `ctx_tokens \|= _content_tokens(c.text)` | 等价于 `ctx_tokens = ctx_tokens \| ...` |
| `max(1, len(...))` 防除零 | `overlap = len(...) / max(1, len(q_tokens))` | 分母至少为 1 |
| `torch.manual_seed` | `CrossEncoder.__init__` | 固定 PyTorch 随机数 |
| `torch.tensor(..., dtype=torch.long)` | `rerank`、`train_reranker` | 把 Python 列表转成整数张量 |
| `with torch.no_grad():` | `rerank` | 推理时不记录梯度 |
| 字典推导式与 f-string 嵌套 | `f"{ {k: round(v, 2) for k, v in result.latency_ms.items()} }"` | 内层大括号两侧留空格，避免被当作 `{{` 转义 |
| f-string 格式符 | `{name:<18}`、`{observed:.3f}`、`{threshold:.2f}` | 左对齐定宽、小数位 |
| `sys.exit(code)` | `sys.exit(run_demo())` | 以给定退出码结束进程；0 表示成功 |
| 类型注解的空容器 | `rankings: list[list[tuple[Chunk, float]]] = []` | 为空列表声明元素类型，方便阅读与静态检查 |
| `typing.Callable` | `from typing import Callable` | 导入了但本文件未使用 |

---

## 6. 运行结果解读

实际运行（Python 3.13，torch 2.14 CPU，退出码 0；总耗时数秒到二十秒不等，主要花在 `import torch` 和 80 轮训练上，取决于机器负载）：

```text
== ingest + train ==
  chunks indexed: 12                     ← 12 篇文档各一个 chunk，chunker 未切分

== one query trace ==
  query: how do production search engines fuse two retrievers
  rewriter strategy: multiquery          ← 4 个 eval query 全部走 multiquery
  top-k: [('d6:0', 0.789), ('d3:0', 0.784), ('d4:0', 0.667)]
  answer: Production search combines lexical and semantic retrieval through reciprocal rank fusion at k = 60. [d6:0]
  citations: ['d6:0']
  latency_ms: {'rewrite': 0.04, 'retrieve': 0.27, 'rerank': 2.3, 'generate': 0.14}

== eval ==
  PASS  recall@5           1.000  (threshold 0.75)
  PASS  precision@1        0.500  (threshold 0.50)   ← 恰好压线
  PASS  mrr                0.708  (threshold 0.60)
  PASS  faithfulness       1.000  (threshold 0.75)   ← 抽取式答案，结构性满分
  PASS  answer_relevance   1.000  (threshold 0.75)

== demo PASSED ==
```

我们额外打印了每个 eval query 的结果：

| qid | gold | top-5（文档, 混合分数） | 答案引用 | P@1 | RR |
|-----|------|----------------------|---------|-----|----|
| e1 | d3, d1 | d3 0.923, d1 0.616, d5, d7, d8 | d3:0、d1:0 | 1 | 1 |
| e2 | d4 | **d1 0.938**, d3 0.878, d4 0.728, d5, d6 | d4:0 | 0 | 1/3 |
| e3 | d6 | d6 0.789, d3 0.784, d4 0.667, d8, d12 | d6:0 | 1 | 1 |
| e4 | d7 | **d3 0.842**, d7 0.709, d4, d5, d1 | d7:0 | 0 | 1/2 |

逐项解读：

- **e3 的轨迹**：d6 只以 0.789 对 0.784 险胜 d3（一篇讲上传中止阈值的文档）。实测纯 cross-encoder 在这个 query 上把 d3 排第一，是词法重叠（d6 含 production、search）把 d6 拉了上来。
- **e2、e4 的 top-1 都是错的**：d1（上传中止）被排在"权限门禁"问题的第一，d3 被排在"停止 worker"问题的第一——cross-encoder 对 d1、d3 有很强的"文档先验"（它们在训练集中都是正例，标签 1.0 和 0.95/1.0）。MRR = `(1 + 1/3 + 1 + 1/2)/4 = 0.708`。
- **答案却都是对的**：生成器在 top-3 里按内容词重叠重新挑选，e2 选中 d4、e4 选中 d7。于是 precision@1 只有 0.5，answer relevance 却是 1.0——这正是"阶段间相互掩盖"的例子。
- **recall@5 = 1.0**：候选集几乎是全库（8–11 个），top-5 必然包含 gold。
- **延迟**：rerank 约 2.3ms，占总时间的大头；改写和生成都是纯 Python 字符串操作，微秒到亚毫秒级。讲义提醒真实 LLM 调用才是延迟主体。
- **我们额外验证的问题**：
  - 问 "what is the capital of france"，系统回答了 d1 的第一句并附 `[d1:0]`，拒答没有触发；
  - 任何被判为 "hyde" 的 query（如 "which config controls the abort threshold"）都会退化为直接检索；
  - 单独的 cross-encoder 排序（MRR 0.487）比不重排（0.583）还差（见 3.6 表格）。

---

## 7. 动手改一改

1. **修复拒答**：按测验 Q9 去掉 `or [scored_chunks[0]]` 兜底，在 top-3 无内容词重叠时拒答；再往 `EVAL_QUERIES` 中加入 2 条 out-of-domain query（gold 为空集），并新增"拒答正确率"指标与阈值。
2. **讲义练习 4（chunker 策略）**：给 demo 加 `--target` 参数（可用 `sys.argv` 或 `argparse`），分别用 400、80、40 运行，观察 `chunks indexed`、5 项指标和答案的变化；同时修正 `_recursive_split` 在 chunk 边界丢失分隔符的问题。
3. **消融实验**：写一个 `run_ablation()`，分别运行"不改写""不重排""只用 cross-encoder""只用重叠"四种配置，打印同一张指标表，检验讲义"staged build wins on every metric"的说法。
4. **讲义练习 1（策略选择器）**：把 `pick_strategy` 改成第 67 节建议的规则（长度、连词、术语密度），并让 "hyde" 策略在没有查表结果时调用一个兜底的假设文档生成器（例如同义词扩展），而不是静默退化为直接检索；`Result.rewriter_strategy` 要如实报告实际使用的路径。
5. **讲义练习 2（真实 LLM 生成器）**：增加环境变量开关，开启时用讲义中的引用 prompt 调用真实模型，关闭时用 mock；比较两者的 faithfulness（此时需要第 68 节测验 Q11 那样更严格的评审）和延迟。
6. **讲义练习 5（流式）**：把 `generate_answer` 改成生成器函数 `yield` 每一句，评估时先拼接完整字符串再算 faithfulness，确认指标不是在流式前缀上计算的。

---

## 8. 常见坑

- **chunk 比文档还大**：`target` 远大于文档长度时 chunker 等于没有，chunk 级逻辑（锚点、去重）都得不到检验。
- **策略名与实际路径不符**：被判为 "hyde" 却没有假设文档时静默退化，日志里的 `rewriter_strategy` 会误导排查。
- **查表式 mock 泄漏答案**：`_REWRITE_HYDE` 的内容就是 gold 原文。
- **用未校准的分数做拒答阈值**：MSE 回归的 cross-encoder 分数没有上下界，阈值 0.05 没有意义。
- **兜底逻辑吞掉拒答**：`or [scored_chunks[0]]` 让"无相关证据"也会作答。
- **生成器掩盖重排错误**：只看 answer relevance 会以为一切正常，必须同时看 precision@1 / MRR。
- **在 eval 集上调混合权重**：`overlap_weight` 在 4 个 query 上挑选，结论不可推广。
- **阈值压线或饱和**：precision@1 = 0.50 恰好等于阈值；faithfulness、recall@5 恒为 1.0。
- **跨节指标口径不一致**：本节 precision 分母为实际个数、relevance 阈值 0.3、停用词表更短，与第 68 节不同。
- **测试中重复构建 pipeline**：`test_eval_meets_thresholds` 与 `test_run_demo_exits_zero` 各自训练一次 reranker，`run_demo` 还会向测试输出打印大量内容。

---

## 9. 测试在验证什么

测试文件：`tests/test_pipeline.py`（`unittest` 风格）。在 `code/` 目录下运行 `python3 -m pytest -q tests` 或 `python3 -m unittest discover tests`。

| 测试类 / 方法 | 验证的性质 |
|--------------|-----------|
| `TestChunker.test_one_chunk_for_short_text` | 短文本只产生 1 个 chunk，`doc_id`、`chunk_index` 正确 |
| `TestChunker.test_anchor_format` | 锚点格式为 `"d1:0"` |
| `TestHybridIndex.test_search_returns_chunks` | 只索引前 3 篇时，"abort upload" 能检索到结果 |
| `TestRewriter.test_strategy_decompose_on_and` | 含 " and " 的 query 选 decompose |
| `TestRewriter.test_strategy_hyde_on_jargon` | 含 "function" 的 query 选 hyde |
| `TestRewriter.test_strategy_default_multiquery` | 其它 query 选 multiquery |
| `TestGenerator.test_refuses_when_top_score_below_threshold` | top-1 分数 0.001 < 0.05 时拒答，无引用 |
| `TestGenerator.test_refuses_on_empty` | 空候选时拒答 |
| `TestGenerator.test_emits_citation_anchor` | 正常作答时答案包含 `[d1:0]`，引用列表为 `["d1:0"]` |
| `TestMetrics.test_recall` / `test_precision` | 文档级 recall@3 = 1.0、precision@1 = 1.0 |
| `TestMetrics.test_mrr_first_unique_doc` | gold 在第 2 个不同文档时 MRR = 0.5 |
| `TestMetrics.test_mrr_no_hit` | 没有命中时 MRR = 0 |
| `TestMetrics.test_faithfulness_refuse_with_empty_topk_is_one` | 空 top-K 时拒答的 faithfulness 为 1.0 |
| `TestMetrics.test_answer_relevance` | 词汇高度重叠的答案判为相关 |
| `TestPipelineQuery.test_returns_result_with_top_k` | `query()` 返回 `Result`，top-K 非空，策略在三者之内 |
| `TestPipelineQuery.test_latencies_reported_per_stage` | 四个阶段都有非负延迟 |
| `TestPipelineQuery.test_answer_carries_citations` | 答案要么有引用、要么是拒答 |
| `TestDemoEval.test_eval_meets_thresholds` | 5 项指标都达到 `THRESHOLDS` |
| `TestDemoEval.test_run_demo_exits_zero` | `run_demo()` 返回 0 |

实际运行结果：

```text
....................                                                     [100%]
20 passed in 5.53s
```

几点评价：

- `TestPipelineQuery` 用 `setUpClass` 只构建一次 pipeline，比每个测试都训练一次 reranker 高效；但 `TestDemoEval` 的两个测试又各自构建了一次。
- `test_refuses_when_top_score_below_threshold` 直接构造了 0.001 的分数，只验证了"阈值比较"这行代码；**真实 pipeline 中这个分支永远不会被走到**（见 3.7），没有任何测试用 out-of-domain query 检验拒答。
- `test_strategy_hyde_on_jargon` 只验证了策略名，没有验证 HyDE 路径真的使用了假设文档——实际上它会退化为直接检索。
- `test_answer_carries_citations` 的断言 `r.citations or r.answer == REFUSE_TEXT` 对任何正常运行都成立，检验力很弱。
- `test_eval_meets_thresholds` 在 precision@1 = 0.500、阈值 0.50 的情况下通过，没有任何余量；任何影响一个 query 排序的改动（例如换 PyTorch 版本导致的数值差异）都可能让它失败。
- 没有测试覆盖 chunker 真正切分多段的情形（文档都短于 `target`），也没有测试覆盖 decompose 路径在 pipeline 中的实际运行。
