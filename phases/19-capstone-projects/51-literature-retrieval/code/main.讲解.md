# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 51 节 文献检索 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数，打印 JSON） ｜ **依赖**：仅 Python 标准库（`collections.Counter / defaultdict / deque`、`dataclasses`、`math`、`re`、`json`、`time`）；类型注解中的 `str | None` 写法在 3.10+ 原生支持（文件已 `from __future__ import annotations`）。

---

## 1. 这份代码在考察什么

研究循环中，第 50 节生成了假设，本节要回答"这个假设是不是已经有人研究过了"。代码约 400 行，覆盖讲义的五个学习目标：

1. **论文记录** `Paper`：下游第 52、53 节要读的字段（id、标题、摘要、年份、引用关系）。
2. **从零实现 BM25**：倒排结构 + 文档频率 + 长度归一化，只用字典与 `Counter`。
3. **引用图遍历**：以 BM25 命中为种子，双向 BFS 最多 2 跳，找到"用词不同但学术相关"的论文。
4. **按 id 合并去重并综合打分**：`0.5·BM25 归一化 + 0.3·图距离分 + 0.2·新近度`。
5. **两个 mock API 客户端**：模拟 arXiv（无引用）和 Semantic Scholar（有引用），封装在一个检索客户端后面。

> 一句话：**词法检索负责"说同样的话"，引用图负责"站在同一条学术脉络上"，合并打分负责给出可解释的排名**。同时要注意：mock 语料是模板生成的、两个 API 客户端实际上没被调用——这两点决定了 demo 结果"看起来对、但测不出质量"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TOKEN_RE` / `tokenise` | 正则 + 函数 | 小写后提取 `[a-z0-9]+` | 分词（无词干化） |
| `Paper` | dataclass | 论文记录，`references` / `citations` 用 `default_factory=list` | 数据模型 |
| `BM25Index` | 类 | `add` 建索引、`finalise` 算 avgdl、`idf` / `score` / `search` | Okapi BM25 |
| `CitationGraph` | 类 | 前向（references）与后向（citations）邻接表；`expand` 多源 BFS | 引用图 |
| `ArxivMockClient` | 类 | 词有交集即命中；返回不带引用的论文 | mock API |
| `SemanticScholarMockClient` | 类 | 同上但带引用；另有 `fetch(id)` | mock API |
| `RetrievalConfig` | dataclass | top_k、max_hops（截到 ≤ 2）、三项权重 | 配置 |
| `RankedPaper` / `RetrievalResult` | dataclass | 每篇的分项分数；整次查询的统计 | 可解释输出 |
| `RetrievalClient` | 类 | 建索引与图、两遍检索、合并、打分、排序 | 检索客户端 |
| `build_corpus` | 函数 | 5 个主题 × 20 篇的模板语料 + 引用边 | mock 数据 |
| `build_client` / `_demo` | 函数 | 组装客户端；查询并打印前 3 名 | 演示 |

数据流：`_demo` → `build_client` → `build_corpus()` → `RetrievalClient.__init__`（BM25 索引 `title + abstract`，引用图，年份范围）→ `search(query)`：`tokenise` → `BM25Index.search` 取前 k 个种子 → `CitationGraph.expand` 得到 `{id: 跳数}` → 种子与图结果求并集 → 每篇算 `bm25 / max_bm25`、`graph_score`、`recency` → 加权得 `final_score` → 按 `(-final, id)` 排序 → `RetrievalResult`。

---

## 3. 逐段精讲

### 3.1 分词与 `Paper`

```python
TOKEN_RE = re.compile(r"[a-z0-9]+")

def tokenise(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())
```

- 先小写再提取连续的字母数字串，标点和空白都是分隔符：`"Attention, Sparsity!"` → `["attention", "sparsity"]`；数字保留：`"study 12"` → `["study", "12"]`。
- 没有词干化：`sparse` 与 `sparsity` 是两个不同的词（讲义承认 "It is not stemmed"）；没有停用词表：`the`、`and`、`we` 都会进索引（但它们出现在所有摘要里，idf 只有约 0.005，几乎不影响分数）。
- 非英文字符全部被丢掉。
- `Paper` 中 `references`、`citations` 用 `field(default_factory=list)`，避免所有实例共享同一个列表。

### 3.2 `BM25Index`：建索引

```python
    def add(self, doc_id: str, text: str) -> None:
        tokens = tokenise(text)
        self._doc_lens[doc_id] = len(tokens)
        counts = Counter(tokens)
        for term, count in counts.items():
            self._term_freq[term][doc_id] = count
            self._doc_freq[term] += 1
        self._n_docs += 1

    def finalise(self) -> None:
        if self._n_docs == 0:
            self._avgdl = 0.0
            return
        self._avgdl = sum(self._doc_lens.values()) / self._n_docs
```

- `_term_freq` 是 `defaultdict(dict)`：`term → {doc_id: 词频}`，这就是**倒排索引**（讲义说是 "term → list of (doc_id, term_count)"，代码用字典实现，查询某词在某文档的词频是 O(1)）。
- `_doc_freq` 是 `Counter`：`term → 包含它的文档数 df`。因为遍历的是 `counts`（去重后的词），同一文档里出现多次也只给 df 加 1。
- `finalise` 必须在所有 `add` 之后调用一次，算出平均文档长度 avgdl。之后再 `add` 不会更新 avgdl；同一个 `doc_id` 重复 `add` 会让 df 和 N 重复计数——这些边界情况代码没有防护。
- 本语料：N = 100，avgdl = 37.8，attention 主题每篇长度 38。

### 3.3 `BM25Index`：idf、打分、搜索

```python
    def idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        return math.log((self._n_docs - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, doc_id: str, query_terms: list[str]) -> float:
        ...
        for term in query_terms:
            f = self._term_freq.get(term, {}).get(doc_id, 0)
            if f == 0:
                continue
            tf_norm = (f * (self.k1 + 1.0)) / (
                f + self.k1 * (1.0 - self.b + self.b * dl / self._avgdl)
            )
            total += self.idf(term) * tf_norm
        return total

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        terms = tokenise(query)
        if not terms:
            return []
        ...
        for term in terms:
            candidate_ids.update(self._term_freq.get(term, {}).keys())
        for doc_id in candidate_ids:
            scores[doc_id] = self.score(doc_id, terms)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [(d, s) for d, s in ranked[:top_k] if s > 0.0]
```

- **idf**：`ln((N − df + 0.5)/(df + 0.5) + 1)`。df = 20 时为 1.5947；df = 100 时为 0.005。`+1` 保证 idf 恒为正（经典公式在 df > N/2 时会变负）。
- **tf_norm**：分子 `f·(k1+1)`、分母 `f + k1·(1 − b + b·dl/avgdl)`。f 越大越接近上限 `k1 + 1 = 2.5`（饱和）；文档越长分母越大（长度惩罚）。手算 p001：f = 3 时 1.6645，f = 1 时 0.9976，总分 `1.5947 × (2×1.6645 + 2×0.9976) = 8.4904`（测验 Q9）。
- **候选集**：只对至少包含一个查询词的文档打分——倒排索引的意义所在，不必遍历全部文档。
- 查询中重复的词会被重复计分（`terms` 是列表不是集合），这是标准 BM25 中"查询词频"的简化处理。
- 排序键 `(-score, doc_id)`：分数降序，同分按 id 升序。⚠️ 本语料同主题 20 篇分数完全相同，种子就由 id 决定（p001–p005）。
- 最后过滤掉 0 分；`ranked[:top_k]` 先截断再过滤。

### 3.4 `CitationGraph.expand`：多源 BFS

```python
    def neighbours(self, doc_id: str) -> list[str]:
        out = list(self._forward.get(doc_id, []))
        out.extend(self._backward.get(doc_id, []))
        return out

    def expand(self, seeds: list[str], max_hops: int = 2) -> dict[str, int]:
        distance: dict[str, int] = {sid: 0 for sid in seeds}
        queue: deque[str] = deque(seeds)
        while queue:
            current = queue.popleft()
            d = distance[current]
            if d >= max_hops:
                continue
            for neighbour in self.neighbours(current):
                if neighbour in distance:
                    continue
                distance[neighbour] = d + 1
                queue.append(neighbour)
        return distance
```

- 邻居 = 我引用的（前向）+ 引用我的（后向），即把有向图当无向图走。
- **多源 BFS**：所有种子同时以距离 0 入队，`deque.popleft()` 保证按距离从小到大处理，第一次访问某节点时记录的就是到"最近种子"的最短跳数。`distance` 字典兼作"已访问集合"。
- 达到 `max_hops` 的节点不再展开，所以结果最多 `max_hops` 跳。
- 本语料：p001、p002 是每个主题的锚点（被同主题 18 篇引用），每个主题第 6 篇（i = 5）额外引用下一个主题的锚点。所以从 p001–p005 出发，1 跳就覆盖整个主题，2 跳开始跨主题。实测 `max_hops` 为 0/1/2 时分别得到 5/21/24 篇。

### 3.5 两个 mock 客户端

```python
class ArxivMockClient:
    def search(self, query: str) -> list[Paper]:
        terms = set(tokenise(query))
        ...
            haystack = set(tokenise(paper.title + " " + paper.abstract))
            if terms & haystack:
                hits.append(Paper(..., source="arxiv"))
```

- 命中条件是"查询词集合与论文词集合有交集"（`&` 是集合交），不排序、不打分，模拟一个简单的关键词 API。
- arXiv 版不复制 `references` / `citations`（保持默认空列表），S2 版复制并带 `fetch(paper_id)` 按 id 取单篇。
- 每次都构造新的 `Paper` 并用 `list(...)` 复制列表，避免调用方修改返回值时污染语料。
- ⚠️ **这两个客户端在 `RetrievalClient.search` 中从未被调用**：构造函数保存了 `self._arxiv`、`self._s2`，但索引和图都是直接用传入的 `corpus` 建的；`_merge_paper` 方法也没有调用者。讲义架构图（query → 两个客户端 → load corpus）和 "The retrieval client unions on id" 与代码不符。测验 Q10 给出了用间谍子类验证的方法和真正调用两个客户端并合并的实现。

### 3.6 `RetrievalConfig` 与输出结构

```python
@dataclass
class RetrievalConfig:
    top_k_lexical: int = 10
    max_hops: int = 2
    w_bm25: float = 0.5
    w_graph: float = 0.3
    w_recency: float = 0.2

    def __post_init__(self) -> None:
        if self.max_hops > 2:
            self.max_hops = 2
```

- `__post_init__` 是 dataclass 在自动生成的 `__init__` 结束后调用的钩子，常用于校验和派生字段。这里把超过 2 的跳数**静默**截到 2（讲义："Two hops is a deliberate ceiling"）；负数不处理（−1 的效果等同 0 跳）。
- `RankedPaper` 保存每篇的 `bm25_score`（未归一化的原始值）、`graph_distance`（`None` 表示不在图结果中）、`recency_score`、`final_score`——讲义强调"每条结果都带解释排名的分项"。
- `RetrievalResult` 附带 `hit_count`、`average_score`、`top_score`、`wall_time_ms`，供下游记录与监控。

### 3.7 `RetrievalClient.search`：合并与打分

```python
        lexical_hits = self._index.search(query, self._cfg.top_k_lexical)
        seed_ids = [doc_id for doc_id, _ in lexical_hits]
        graph_distance = self._graph.expand(seed_ids, self._cfg.max_hops)
        merged_ids = set(seed_ids) | set(graph_distance.keys())
        max_bm25 = max((s for _, s in lexical_hits), default=0.0)
        for doc_id in merged_ids:
            paper = self._corpus.get(doc_id)
            if paper is None:
                continue
            bm25 = self._index.score(doc_id, terms)
            distance = graph_distance.get(doc_id)
            graph_score = self._graph_score(distance)
            bm25_norm = bm25 / max_bm25 if max_bm25 > 0 else 0.0
            recency = self._recency(paper.year)
            final = (
                self._cfg.w_bm25 * bm25_norm
                + self._cfg.w_graph * graph_score
                + self._cfg.w_recency * recency
            )
```

- **去重**：用集合并 `|` 合并两遍结果，天然没有重复 id（测试 `test_dedup_no_duplicate_ids`）。由于 `expand` 的结果本来就包含种子，`set(seed_ids)` 其实是冗余的。
- **对图找到的论文也重新算 BM25**：非种子论文也可能有词法分数（例如 attention 主题的 p006–p020，BM25 与种子完全相同，只是因为 id 排序没进 top-5）。
- **归一化**：除以种子中的最大 BM25。讲义说是"merged set 中的最大值"，两者等价，因为 top-1 一定在种子里。
- **`_graph_score`**：距离 0/1/2 → 1.0/0.6/0.3，`None` 或更远 → 0。
- **`_recency`**：`(year − min)/(max − min)`，语料 2018–2025，2022 年为 4/7 ≈ 0.5714；所有年份相同时返回 1.0 防止除零。
- `paper is None` 时跳过：图中引用了语料外的 id（真实数据很常见）就直接丢弃，不会补抓元数据（S2 客户端的 `fetch` 本可以用在这里）。
- 打分后重新构造一个 `source="merged"` 的 `Paper`，与 `_merge_paper` 的逻辑重复。
- 最终按 `(-final_score, paper.id)` 排序；`average_score` 和 `top_score` 用 `final_score` 计算。

### 3.8 `build_corpus`：模板语料与引用边

```python
            abstract = (
                f"This work investigates {label} and reports on {terms}. "
                f"We measure perplexity, accuracy, and wall time on small transformer baselines. "
                f"The study {i + 1} extends prior findings in topic {topic_idx + 1}."
            )
            year = 2018 + (i % 8)
    ...
            if i >= 2:
                anchor_a = f"p{topic_idx * 20 + 1:03d}"
                anchor_b = f"p{topic_idx * 20 + 2:03d}"
                paper.references.extend([anchor_a, anchor_b])
                by_id[anchor_a].citations.append(pid)
                by_id[anchor_b].citations.append(pid)
            if i == 5:
                cross = f"p{((topic_idx + 1) % 5) * 20 + 1:03d}"
                paper.references.append(cross)
                by_id[cross].citations.append(pid)
```

- id 用 `f"p{n:03d}"` 补零到 3 位（p001–p100），字典序与数值序一致。
- 年份 `2018 + (i % 8)` 在 2018–2025 之间循环。
- 引用边双向维护：A 引用 B 时，同时往 A 的 `references` 与 B 的 `citations` 里加，保证图的一致性。
- 每个主题的第 6 篇引用下一个主题的锚点，`% 5` 让最后一个主题绕回第一个（p086 → p001）。
- ⚠️ 同主题摘要只有数字不同，**BM25 完全平分**；`perplexity`、`accuracy` 等词出现在所有摘要中。这让 demo 能跑通，但无法检验排序是否"更相关在前"（测验 Q9）。讲义说"each paper has a hand written title and abstract"，实际是模板生成的。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯标准库 BM25 | 可读、可审计、零依赖 | 无压缩、无持久化；生产用 Lucene/Elasticsearch/Tantivy 等 |
| 无词干化、无停用词 | 简单 | `sparse` 匹配不到 `sparsity`；可加 Porter/Snowball 或词形还原 |
| idf 带 `+1` | 保证非负，常见词不扣分 | 与经典 BM25 略有差异（Lucene 采用同样变体） |
| 引用图双向 BFS、≤ 2 跳 | 同时找奠基与后续工作；防止爆炸 | 不区分边方向与节点权威性；真实图 2 跳也可能极大，需要扇出上限 |
| 线性加权三项分数 | 透明、可配置 | 需归一化、需调参；可改用 RRF 或学习排序 |
| recency 线性加分 | 快速演进领域偏好新论文 | 新颖性检查场景会压低奠基论文（p001 排第 11）；应可配置或加被引数信号 |
| `max_hops` 静默截断 | 防止误配置 | 不报错、不提示；负数不处理 |
| 图中语料外 id 直接丢弃 | 实现简单 | 丢失邻居；应调用 `fetch` 补元数据 |
| 两个 mock 客户端 | 预留真实 API 的接口形状 | 当前未被使用，讲义描述的合并流程没有实现 |
| 模板语料 | 确定、可复现 | 同主题平分，无法测试排序质量 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `collections.Counter` | `Counter(tokens)`、`self._doc_freq[term] += 1` | 计数字典，缺失键默认 0 |
| `collections.defaultdict` | `defaultdict(dict)` | 访问不存在的键时自动创建空字典 |
| `collections.deque` | `deque(seeds)`、`queue.popleft()` | 两端 O(1) 的队列，BFS 标配 |
| 嵌套 `get` 带默认值 | `self._term_freq.get(term, {}).get(doc_id, 0)` | 链式安全取值，任何一层缺失都得默认值 |
| 集合运算 | `terms & haystack`、`set(seed_ids) | set(graph_distance.keys())` | 交集、并集 |
| `set.update` | `candidate_ids.update(...keys())` | 批量加入元素 |
| 字典推导式 | `{sid: 0 for sid in seeds}`、`{p.id: p for p in corpus}` | 一行构造字典 |
| `max(..., default=...)` | `max((s for _, s in lexical_hits), default=0.0)` | 空序列时返回默认值而不是报错 |
| `sorted` + 元组键 | `key=lambda kv: (-kv[1], kv[0])` | 分数降序、id 升序 |
| 切片后过滤 | `[(d, s) for d, s in ranked[:top_k] if s > 0.0]` | 列表推导式中的解包与条件 |
| `@dataclass` + `field(default_factory=list)` | `references: list[str] = field(default_factory=list)` | 可变默认值的正确写法 |
| `__post_init__` | `RetrievalConfig.__post_init__` | dataclass 初始化后的校验钩子 |
| `X | None` 联合类型 | `graph_distance: int | None`、`def fetch(...) -> Paper | None` | 可能为空的值 |
| `or` 取第一个非空 | `config or RetrievalConfig()`、`(lexical or s2).id` | 短路求值 |
| `math.log` | `math.log((N - df + 0.5) / (df + 0.5) + 1.0)` | 自然对数 |
| f-string 补零 | `f"p{topic_idx * 20 + i + 1:03d}"` | 宽度 3、不足补 0 |
| `str.title()` | `label.title()` | 每个单词首字母大写：`"attention sparsity"` → `"Attention Sparsity"` |
| 取模绕回 | `((topic_idx + 1) % 5)` | 环形索引 |
| `time.perf_counter()` | 计算 `wall_time_ms` | 高精度计时 |
| `json.dumps(..., indent=2)` | `_demo` | 美化输出 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`：

```text
{
  "hit_count": 24,
  "top_score": 0.9143,
  "top_three": [
    {"id": "p005", "title": "Attention Sparsity study 5", "year": 2022, "bm25_score": 8.4904,
     "graph_distance": 0, "recency_score": 0.5714, "final_score": 0.9143},
    {"id": "p004", "title": "Attention Sparsity study 4", "year": 2021, "bm25_score": 8.4904,
     "graph_distance": 0, "recency_score": 0.4286, "final_score": 0.8857},
    {"id": "p008", "title": "Attention Sparsity study 8", "year": 2025, "bm25_score": 8.4904,
     "graph_distance": 1, "recency_score": 1.0, "final_score": 0.88}
  ]
}
```

逐项解读：

- **`hit_count = 24`**：BM25 种子 p001–p005（20 篇同分，按 id 取前 5）；1 跳覆盖 attention 主题其余 15 篇和跨主题的 p086；2 跳得到 p021、p081、p082（测验 Q5）。
- **所有 attention 论文 `bm25_score = 8.4904`**：模板语料同主题完全相同（手算见测验 Q9）。
- **p005 排第一**：种子（graph 1.0）里年份最新的。`0.5 + 0.3 + 0.2 × 4/7 = 0.9143`。
- **p008 排第三**：它只是 1 跳邻居（graph 0.6），但 2025 年 recency = 1.0，`0.5 + 0.18 + 0.2 = 0.88`，超过了种子 p003、p002、p001。

我们额外打印的完整排名（节选）：

| 名次 | id | 年份 | 距离 | recency | final |
|------|----|------|------|---------|-------|
| 1 | p005 | 2022 | 0 | 0.5714 | 0.9143 |
| 5 | p003 | 2020 | 0 | 0.2857 | 0.8571 |
| 8 | p002 | 2019 | 0 | 0.1429 | 0.8286 |
| 11 | p001 | 2018 | 0 | 0.0 | 0.8000 |
| 21 | p086 | 2023 | 1 | 0.7143 | 0.3229 |
| 22 | p082 | 2019 | 2 | 0.1429 | 0.1186 |
| 23 | p021 | 2018 | 2 | 0.0 | 0.0900 |

- 被引最多的锚点 p001 只排第 11：同分时 recency 决定一切，而 recency 惩罚老论文（测验 Q8、Q11）。
- 跨主题论文 BM25 为 0，只靠图分与 recency，分数明显低于主题内论文，符合直觉。
- `average_score = 0.6914`（24 篇 final 的平均）。
- 查询 `"sparse attention"` 时 p001 的 BM25 只有 2.654（`sparse` 不匹配 `sparsity`），但由于同主题仍然平分，排名结构与上面相同。

---

## 7. 动手改一改

1. **让语料有区分度**：给每篇摘要随机加入 0–3 次额外的主题词、长度不同的句子，重新观察 BM25 不再平分；再写一个"更相关的排在前面"的测试。
2. **真正调用两个客户端**：按测验 Q10 实现 `load_corpus_from_clients`，并在图扩展后对语料外的邻居调用 `s2.fetch(id)` 补全，使 `hit_count` 回到 24。
3. **被引数信号**：按测验 Q11 加入 `w_cite × log1p(citations)` 项，或实现一个 10 轮迭代的简化 PageRank，观察锚点论文的排名。
4. **词干化**：按测验 Q12 实现后缀剥离词干器，让 `"sparse attention"` 也能命中 `sparsity`（实测 BM25 从 2.654 升到 5.309）。
5. **RRF 融合**：把"BM25 名次"和"图距离名次"用 `Σ 1/(60 + rank)` 融合，与当前线性加权对比。
6. **配置校验**：把 `__post_init__` 改为对 `max_hops < 0` 或 `> 2` 抛 `ValueError`，对权重和不为 1 给出警告，并补充对应测试。

---

## 8. 常见坑

- **忘记调用 `finalise()`**：avgdl 为 0，`score` 直接返回 0，所有查询都没有结果。
- **建索引与查询用不同的分词/词干规则**：命中率骤降。
- **以为同分时排名有意义**：本语料同主题完全平分，排名由 id 与年份决定。
- **把 recency 当作通用信号**：新颖性检查需要奠基论文，线性 recency 会把它们压下去。
- **图扩展不设扇出上限**：真实引用图上 2 跳可能是成千上万篇。
- **以为 `max_hops=5` 会生效**：被静默截到 2；`max_hops=-1` 等同于 0。
- **引用了语料外的论文**：会被直接丢弃，需要 `fetch` 补全。
- **按 id 去重却没有统一 id 体系**：真实数据中 arXiv id（带版本号）、DOI、S2 id 各不相同。
- **以为 `RetrievalClient` 调用了 mock API**：它没有。

---

## 9. 测试在验证什么

`tests/test_retrieval.py` 用 `unittest` 编写，通过 `sys.path.insert` 把 `code/` 加入搜索路径后 `from main import ...`。共 6 个测试类、18 个用例：

| 测试类 | 用例 | 验证的性质 |
|-------|------|-----------|
| `TestTokenise` | `test_lowercases_and_splits` | 小写化并按标点切分 |
| | `test_keeps_digits` | 数字作为独立 token 保留 |
| `TestBM25` | `test_single_doc_query` | 单文档索引能命中且分数 > 0 |
| | `test_returns_zero_for_unknown_term` | 未登录词返回空列表 |
| | `test_ranking_orders_by_score` | 相关的 d1、d2 命中，无关的 d3 不命中 |
| | `test_empty_query_returns_empty` | 空查询返回空列表 |
| `TestCitationGraph` | `test_expand_zero_hops` | 0 跳只返回种子 |
| | `test_expand_one_hop_reaches_neighbours` | 1 跳同时到达引用对象（b）与施引者（c），距离为 1 |
| `TestClients` | `test_arxiv_returns_lexical_overlap` | arXiv 客户端有结果、`source="arxiv"`、无引用 |
| | `test_s2_returns_full_record` | S2 客户端结果中有带引用的论文 |
| `TestRetrieval` | `test_search_returns_ranked_papers` | demo 查询有结果且按 `final_score` 降序 |
| | `test_top_hit_is_on_topic` | 第一名标题含 "Attention Sparsity" |
| | `test_dedup_no_duplicate_ids` | 结果中 id 不重复 |
| | `test_graph_expansion_extends_beyond_lexical` | 2 跳结果数 ≥ 0 跳结果数 |
| | `test_empty_query_returns_no_hits` | 空查询 `hit_count = 0` |
| | `test_metrics_present` | `top_score ≥ average_score ≥ 0`，耗时 ≥ 0 |
| `TestCorpusShape` | `test_corpus_has_hundred_papers` | 语料 100 篇 |
| | `test_corpus_ids_unique` | id 唯一 |

运行方式与实际结果：

```text
$ cd code && python3 -m pytest -q tests
..................                                                       [100%]
18 passed in 0.05s

$ python3 -m unittest discover -s tests
Ran 18 tests in 0.016s
OK
```

几点观察：

- `test_ranking_orders_by_score` 名字说"按分数排序"，实际只检查谁命中、谁没命中，没有检查 d1 与 d2 的先后。
- `test_graph_expansion_extends_beyond_lexical` 用的是 `>=`，即使图扩展什么都没加也能通过；实测该用例中 0 跳 3 篇、2 跳 24 篇，可以改成严格的 `>`。
- `TestClients` 测了两个 mock 客户端本身，但没有任何测试检查 `RetrievalClient` 是否使用了它们（实际没有使用）。
- 值得补充的测试：BM25 手算值（如 p001 的 8.4904）、同分时的确定性排序、`max_hops` 截断与负值、语料外 id 的处理、词干化后的命中。
