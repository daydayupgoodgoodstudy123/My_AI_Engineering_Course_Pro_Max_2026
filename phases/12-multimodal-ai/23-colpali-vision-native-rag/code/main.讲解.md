# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 23 节 ColPali 与视觉原生文档 RAG ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`），无需网络、GPU 或模型权重

---

## 1. 这份代码在考察什么

这份 130 行的脚本用纯 Python 列表模拟 ColPali 检索的核心：

1. **多向量表示**：每个"页面"是一组 patch 向量（16 个 × 32 维），每个查询是一组 token 向量（4 个 × 32 维），而不是各自一个向量。
2. **MaxSim 打分**：`Σ_i max_j cos(q_i, p_j)`，即讲义里 ColBERT 的 late interaction。
3. **top-k 检索**：对所有页面打分、排序、取前 k。
4. **MaxSim vs 平均相似度**：用一个手工构造的小例子说明"取最大值"不会被无关 patch 稀释。
5. **存储估算**：ColPali 每页 729 × 128 个浮点 vs 文本 RAG 每块一个 768 维向量。

> 一句话：**把"检索单位从一个文档向量变成一组 patch 向量、打分从一次余弦变成 MaxSim"写成几十行可读的代码**。但要注意：本脚本的检索演示在默认种子下 3 个查询的 top-1 全部错误，且对比实验的口径有问题——读懂"为什么错"比读懂代码本身更有价值。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `random.seed(7)` | 模块级语句 | 固定页面 embedding 的随机性 | 可复现 |
| `Page` | dataclass | `doc_id` + `patches`（向量列表） | 页面的多向量表示 |
| `Query` | dataclass | `text` + `tokens`（向量列表） | 查询的多向量表示 |
| `cosine` | 函数 | 纯 Python 余弦相似度 | 相似度 |
| `maxsim` | 函数 | 对每个查询 token 取最大余弦再求和 | ColBERT MaxSim |
| `random_emb` | 函数 | 生成均值为 `bias/10`、方差 1 的高斯向量 | 合成 embedding |
| `build_pages` | 函数 | 5 个话题页面，每页 16 个 patch，偏置 1–5 | 入库 |
| `build_queries` | 函数 | 3 个查询，每个 4 个 token，偏置 1/2/4 | 查询编码 |
| `retrieve` | 函数 | 全量打分 → 降序排序 → 取前 k | 暴力检索 |
| `storage_estimate` | 函数 | 打印每页存储量 | 存储算术 |
| `compare_maxsim_vs_mean` | 函数 | 手工小例子比较 MaxSim 与平均余弦 | late interaction 的选择性 |
| `main` | 函数 | 串起以上演示并打印端到端流程 | 完整 pipeline |

数据流：`build_pages`（模拟"PDF → 页图 → PaliGemma → patch 向量"）→ `build_queries`（模拟"文本 → 查询 token 向量"）→ `retrieve`（对每页 `maxsim`）→ 打印 top-3；随后 `compare_maxsim_vs_mean` → `storage_estimate` → 打印端到端流程说明。

---

## 3. 逐段精讲

### 3.1 两个数据类：多向量表示

```python
@dataclass
class Page:
    doc_id: str
    patches: list[list[float]]


@dataclass
class Query:
    text: str
    tokens: list[list[float]]
```

- `patches` 是"列表的列表"：外层长度 `N_p`（本例 16，ColPali 讲义中 729），内层长度 `D`（本例 32，ColPali 中 128）。这就是讲义说的 "N_p vectors per page"。
- `Query.tokens` 同理：外层 `N_q`（本例 4），内层 `D`。查询与页面必须在**同一个向量空间**里（真实 ColPali 中都由 PaliGemma 的语言模型输出再线性投影到 128 维）。
- `Query.text` 只用于打印，打分完全不看文字——真实系统里文字要先经过编码器才会变成 `tokens`。

### 3.2 `cosine` 与 `maxsim`：late interaction 的核心

```python
def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) + 1e-8
    nb = math.sqrt(sum(y * y for y in b)) + 1e-8
    return dot / (na * nb)


def maxsim(query_tokens: list[list[float]],
           patches: list[list[float]]) -> float:
    """ColBERT MaxSim: sum over query tokens of max over patches."""
    s = 0.0
    for q in query_tokens:
        best = max(cosine(q, p) for p in patches)
        s += best
    return s
```

- `cosine`：点积除以两个范数之积；`+ 1e-8` 防止零向量除零（`compare_maxsim_vs_mean` 里确实有一个零向量 patch，余弦得 0）。
- `maxsim`：外层循环查询 token，内层用生成器表达式对所有 patch 求余弦并取 `max`，再累加。复杂度 `O(N_q × N_p × D)`，一页就是 `4 × 16 × 32 = 2,048` 次乘加。
- 输出范围：每个 `max` 在 `[-1, 1]`，总分在 `[-N_q, N_q]`。分数随查询 token 数增长，**不同查询之间的分数不可直接比较**，只能在同一查询内排序。
- 真实实现会预先把向量 L2 归一化，余弦就退化为点积，整个 MaxSim 是一次矩阵乘法 `(N_q, D) @ (D, N_p)` 后按行取 max 再求和（测验 Q10 有 NumPy 版本，已验证与本函数一致）。

### 3.3 `random_emb` / `build_pages` / `build_queries`：合成数据（问题所在）

```python
def random_emb(dim: int, bias: int = 0) -> list[float]:
    return [random.gauss(bias / 10.0, 1.0) for _ in range(dim)]


def build_pages(n_pages: int = 5, n_patches: int = 16, dim: int = 32) -> list[Page]:
    pages = []
    topics = ["finance", "science", "legal", "medical", "engineering"]
    for i, topic in enumerate(topics[:n_pages]):
        bias = i + 1
        patches = [random_emb(dim, bias) for _ in range(n_patches)]
        pages.append(Page(doc_id=f"page_{i}_{topic}", patches=patches))
    return pages


def build_queries(dim: int = 32) -> list[Query]:
    random.seed(100)
    queries = []
    for text, bias in [("Q3 revenue growth", 1),
                       ("proof of lemma 3", 2),
                       ("patient diagnosis", 4)]:
        tokens = [random_emb(dim, bias) for _ in range(4)]
        queries.append(Query(text=text, tokens=tokens))
    return queries
```

设计意图：话题 i 的页面偏置为 `i+1`，查询用相同偏置表示"同一话题"，期望检索到对应页面（finance=1、science=2、medical=4）。

⚠️ **这个意图实现不了**：

- 偏置只是"每一维的均值都加 `bias/10`"，所有话题都沿**同一个方向**（全 1 方向）平移，只是平移幅度不同。话题之间没有方向上的区别。
- 期望余弦约为 `m_q·m_p / √((1+m_q²)(1+m_p²))`（`m = bias/10`）。对查询偏置 1，五个页面依次约 `0.0099, 0.0195, 0.0286, 0.0370, 0.0445`——只随页面偏置单调增长，"engineering 页对任何查询都最像"。
- 这些差异（约 0.01）远小于 32 维随机向量余弦的噪声（标准差约 `1/√32 ≈ 0.18`），而 `max` over 16 个 patch 又专门挑噪声最大的那个。
- 结果：默认种子下 3 个查询 top-1 **全部错误**（见第 6 节）；200 个种子重复实验 hit@1 约 22%，几乎等于随机（20%），且 engineering 成为 top-1 的次数最多。
- 修复方法：让每个话题有一个随机"原型方向"，页面中少数 patch = 原型 + 小噪声，查询 token = 原型 + 噪声。修复后 hit@1 为 100%（测验 Q9 有完整代码）。

其它细节：

- `build_queries` 内部调用 `random.seed(100)` 会**重置全局随机状态**，任何在它之后调用 `random` 的代码都会受影响——这是一个隐蔽的副作用。用 `random.Random(seed)` 创建局部生成器更安全。
- 模块顶层的 `random.seed(7)` 在 `import main` 时就执行，同样影响导入方。

### 3.4 `retrieve`：暴力 top-k

```python
def retrieve(query: Query, pages: list[Page], k: int = 3) -> list[tuple[str, float]]:
    scored = [(p.doc_id, maxsim(query.tokens, p.patches)) for p in pages]
    scored.sort(key=lambda x: -x[1])
    return scored[:k]
```

- 对**每一页**都算一次 MaxSim，再按分数降序排序。`key=lambda x: -x[1]` 用取负实现降序，等价于 `sort(key=lambda x: x[1], reverse=True)`。
- 这对应讲义的"compute MaxSim against all stored page embeddings, return top-k pages"。5 页无所谓；100 万页 × 729 patch 时每次查询约 1.9 × 10¹² 次乘加（20 个查询 token 时），必须用"ANN 召回 + MaxSim 重排"的两阶段方案（测验 Q10/Q14）。
- 若要 top-k 而不需要全排序，可用 `heapq.nlargest(k, ...)`，复杂度 `O(N log k)`。

### 3.5 `compare_maxsim_vs_mean`：选择性演示（口径有问题）

```python
    q_tokens = [[1.0, 0.1, 0.0], [0.0, 1.0, 0.1]]
    strong_patch = [0.9, 0.9, 0.0]
    other_patches = [[0.1, 0.1, 0.1], [0.2, 0.2, 0.2], [0.0, 0.0, 0.0]]
    patches = [strong_patch] + other_patches
    max_score = maxsim(q_tokens, patches)
    mean_score = sum(cosine(q, p) for q in q_tokens for p in patches) / (
        len(q_tokens) * len(patches))
```

逐对余弦（已计算）：

| | strong `[0.9,0.9,0]` | `[0.1,0.1,0.1]` | `[0.2,0.2,0.2]` | `[0,0,0]` |
|---|---|---|---|---|
| q1 `[1,0.1,0]` | **0.774** | 0.632 | 0.632 | 0.0 |
| q2 `[0,1,0.1]` | **0.704** | 0.632 | 0.632 | 0.0 |

- MaxSim = 0.774 + 0.704 = **1.478**；Mean = 8 个值的平均 = **0.501**。
- `[0.1,0.1,0.1]` 与 `[0.2,0.2,0.2]` 方向相同，余弦完全一样（0.632）——余弦只看方向不看长度，所以这两个"弱 patch"其实并不弱；真正拉低均值的是零向量。
- ⚠️ 口径问题：
  1. MaxSim 是 2 个 token 的**求和**，Mean 是**平均**，尺度不同。按 token 平均后 MaxSim 是 0.739，差距没有看上去那么大。
  2. "所有 pair 余弦的平均"不是 bi-encoder。bi-encoder 是先池化再比较：`cos(mean(q), mean(p)) = 0.993`，在这组数据上反而**高于** MaxSim。
  3. 所以打印的结论 "MaxSim's selectivity is why late interaction beats bi-encoder recall" 并没有被这个例子证明。要证明它，需要"信号只在极少数 patch 中"的数据：测验 Q11 中 64 个 patch 只有 1 个是信号时，MaxSim hit@1 为 99.7%，bi-encoder 只有 34%。
- `random.seed(42)` 在这个函数里没有任何作用（函数没有用随机数），但它仍然改变了全局随机状态。

### 3.6 `storage_estimate`：存储算术

```python
    print(f"  {'text-RAG 768d bi-enc':<24}{'3.0 KB':<14}  one vector per chunk")
    print(f"  {'ColPali raw (729 x 128)':<24}{'365 KB':<14}  one vec per patch")
    print(f"  {'ColPali PQ 8x':<24}{'46 KB':<14}  OPQ compression")
    print(f"  {'VisRAG bi-enc':<24}{'3.0 KB':<14}  single vec per page")
```

验算（字节，KB 实为 KiB = 1024 字节）：

| 方案 | 公式 | 字节 | 打印 |
|------|------|------|------|
| 文本 RAG | `768 × 4` | 3,072 | 3.0 KB |
| ColPali 原始 | `729 × 128 × 4` | 373,248 | 365 KB（364.5 KiB） |
| ColPali PQ 8× | `373,248 / 8` | 46,656 | 46 KB（45.6 KiB） |
| VisRAG | 单向量 | 3,072（按 768 维假设） | 3.0 KB |

- 每页比值约 `373,248 / 3,072 ≈ 121.5`。讲义正文写 "ColPali is ~30x more storage per document"，与它自己给的 18 MB / 150 kB 不符（应约 121 倍）；"~4 MB after PQ" 也与 8 倍压缩（约 2.33 MB）不一致。代码的每页数字反而是对的。
- "文本 RAG 每页 3 KB" 隐含"每页一个块"的假设；实际一页常切成 1–3 个 300–500 token 的块。
- 729 = 27 × 27，是 384 像素输入、14 像素 patch 的网格数；真实模型每页的 patch 数取决于其输入分辨率，估算时应以所用模型为准。
- 全部是写死的字符串，没有用公式计算。"动手改一改"第 2 题把它改成函数。

### 3.7 `main`：串起演示

```python
    pages = build_pages(n_pages=5, n_patches=16, dim=32)
    queries = build_queries(dim=32)
    ...
    for q in queries:
        hits = retrieve(q, pages, k=3)
        print(f"  query: '{q.text}'")
        for page_id, score in hits:
            print(f"    {page_id:<22}  score={score:+.3f}")
```

- 注意调用顺序：`build_pages` 用的是模块顶层 `seed(7)` 之后的随机流；`build_queries` 再自己 `seed(100)`。两个种子决定了第 6 节的全部数字。
- `{score:+.3f}` 强制显示正负号，保留 3 位小数。
- 最后四行打印讲义的端到端流程：入库（PaliGemma 编码并缓存 patch 向量）→ 查询（MaxSim → top-k 页）→ 生成（top-k 页图像 + 问题 → Qwen2.5-VL）。代码中并没有任何生成步骤。
- 模块 docstring 说会打印 "ranked pages + interpretation"，实际上没有任何解释性输出。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 列表 + `math` | 零依赖，每一步都可见 | 慢；生产用 NumPy/PyTorch 张量，一次矩阵乘法完成 MaxSim |
| 合成随机 embedding | 无需模型权重 | 偏置沿同一方向，检索结果约等于随机；应用"话题 = 方向"的合成数据或真实编码器 |
| 余弦 + `1e-8` | 处理零向量 | 生产中入库时归一化，查询时用点积 |
| 全量暴力 MaxSim | 最直接地体现公式 | `O(N_pages × N_q × N_p × D)`；生产用 ANN 召回 + MaxSim 重排、PLAID 类索引 |
| 全排序取 top-k | 简单 | 大规模用 `heapq.nlargest` 或 ANN 自带 top-k |
| 用"平均余弦"对比 | 直观展示稀释效应 | 尺度不一致，且不是 bi-encoder；应与"池化后余弦"比，并在稀疏信号数据上比 |
| 全局 `random.seed` | 写起来方便 | 副作用影响导入方；用 `random.Random(seed)` 局部生成器 |
| 存储表写死字符串 | 一目了然 | 不能复用；应写成按页数、patch 数、维度、精度、压缩比计算的函数 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可在旧版本写 `list[list[float]]` |
| `@dataclass` | `class Page`、`class Query` | 自动生成构造函数等；`Page(doc_id=..., patches=...)` 用关键字参数构造 |
| 嵌套类型注解 | `list[list[float]]`、`list[tuple[str, float]]` | 描述"向量的列表""(id, 分数) 的列表" |
| `zip` | `zip(a, b)` | 两个序列逐元素配对，计算点积 |
| 生成器表达式 | `sum(x * y for x, y in zip(a, b))`、`max(cosine(q, p) for p in patches)` | 不建中间列表，直接喂给 `sum`/`max` |
| 双重生成器 | `sum(cosine(q, p) for q in q_tokens for p in patches)` | 等价于两层 for 循环，先遍历 q 再遍历 p |
| `math.sqrt` | `math.sqrt(sum(x * x for x in a))` | 求范数 |
| `random.gauss(mu, sigma)` | `random.gauss(bias / 10.0, 1.0)` | 正态分布采样 |
| `random.seed` | `random.seed(7)`、`random.seed(100)` | 设置**全局**随机状态；局部生成器写法 `rng = random.Random(7)` |
| `enumerate` + 切片 | `for i, topic in enumerate(topics[:n_pages])` | 同时拿到下标和元素；切片取前 n 个 |
| `_` 占位变量 | `for _ in range(dim)` | 循环变量不使用 |
| `list.sort(key=...)` | `scored.sort(key=lambda x: -x[1])` | 原地排序；`lambda` 匿名函数取第 2 个元素的相反数实现降序 |
| 列表拼接 | `[strong_patch] + other_patches` | 生成新列表 |
| f-string 格式 | `{score:+.3f}`、`{page_id:<22}`、`{max_score:.3f}` | 带符号 3 位小数、左对齐 22 宽 |
| f-string 内嵌字符串字面量 | `f"  {'system':<24}{'bytes/page':<14}  note"` | 对字面量也能用格式说明符来对齐表头 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`；但模块顶层的 `random.seed(7)` 在 import 时也会执行 |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，瞬时完成）：

```text
INDEX + RETRIEVE
------------------------------------------------------------
  query: 'Q3 revenue growth'                 ← 应命中 page_0_finance
    page_2_legal            score=+1.403     ← 错
    page_0_finance          score=+1.314
    page_1_science          score=+1.154

  query: 'proof of lemma 3'                  ← 应命中 page_1_science
    page_3_medical          score=+1.687     ← 错
    page_4_engineering      score=+1.585
    page_1_science          score=+1.497

  query: 'patient diagnosis'                 ← 应命中 page_3_medical
    page_1_science          score=+1.574     ← 错
    page_0_finance          score=+1.530
    page_3_medical          score=+1.348

MAXSIM vs MEAN SIMILARITY
------------------------------------------------------------
  MaxSim : 1.478   (captures best matches per query token)
  Mean   : 0.501   (washed out by irrelevant patches)
  MaxSim's selectivity is why late interaction beats bi-encoder recall

STORAGE — COLPALI vs TEXT-RAG
------------------------------------------------------------
  system                  bytes/page      note
  text-RAG 768d bi-enc    3.0 KB          one vector per chunk
  ColPali raw (729 x 128) 365 KB          one vec per patch
  ColPali PQ 8x           46 KB           OPQ compression
  VisRAG bi-enc           3.0 KB          single vec per page
```

逐项解读：

- **检索结果**：三个查询的 top-1 都不是目标页，目标页分别排第 2、3、3。分数都集中在 0.9–1.7 之间（4 个 token，每个 token 的最大余弦约 0.2–0.45），这是"16 个随机 patch 里挑噪声最大的"得到的典型水平，而不是语义匹配。原因见 3.3 节；200 个种子重复实验 hit@1 约 22%。
- **完整分数表**（已打印）：例如 'Q3 revenue growth' 对 5 页依次为 1.314、1.154、1.403、0.906、0.934——没有任何规律可循，印证了"排名约等于随机"。
- **MaxSim vs Mean**：1.478 是两个 token 的最大余弦之和（0.774 + 0.704），0.501 是 8 个余弦的平均。口径问题见 3.5 节：按 token 平均后 0.739；真正的 bi-encoder 池化余弦为 0.993。
- **存储表**：每页数字与公式一致（KiB）；ColPali 原始约为文本单向量的 121.5 倍，PQ 8 倍后约 15 倍。讲义正文的"约 30 倍""约 4 MB after PQ"与此不符。
- 修复数据构造后（测验 Q9），同样的 `maxsim`/`retrieve` 能 100% 检索正确，例如 'Q3 revenue growth' → finance 2.928，第二名仅 1.436——**打分函数没问题，问题出在合成数据**。

---

## 7. 动手改一改

1. **修复合成数据**：按测验 Q9 的思路实现 `build_world(seed)`（话题 = 随机单位方向，少数信号 patch + 多数随机 patch），用局部 `random.Random(seed)` 替换全局种子，确认 3 个查询 top-1 全部正确。
2. **存储函数**：写 `storage_bytes(n_pages, n_patches=729, dim=128, bytes_per=4, pq=1)`，复现讲义练习 1（200 页：约 74.6 MB 原始、9.3 MB PQ 8×），并输出与文本 RAG 的倍数，顺便核对讲义"约 30 倍"的说法。
3. **公平对比**：把 `compare_maxsim_vs_mean` 改成三列：MaxSim / N_q、所有 pair 平均余弦、bi-encoder 池化余弦；再在"64 个 patch 只有 1 个信号"的设置下跑 200 个种子统计 hit@1（参考结果：MaxSim 99.7%，bi-encoder 34%）。
4. **向量化**：用 NumPy 写 `maxsim_np` 和一次处理所有页面的 `einsum` 版本，验证与原函数一致，再测 1,000 页 × 729 patch × 128 维的耗时。
5. **两阶段检索**：先用 bi-encoder（池化向量）召回 top-20，再对候选做 MaxSim 重排；比较"全量 MaxSim"与"两阶段"的 hit@1 和计算量。
6. **进阶（需安装依赖与下载权重，非本课必需）**：用 `colpali-engine` 加载 ColPali/ColQwen2，对几页真实 PDF 截图建索引，检查 patch 向量的形状和每页存储量，并在 ViDoRe 的一个子集上计算 nDCG@5。

---

## 8. 常见坑

- **合成数据没有"方向"**：给所有向量加同一个偏置只改变幅度，余弦几乎看不见；话题差异必须体现为不同方向。
- **用全局 `random.seed` 制造隐式耦合**：函数内部重置种子会改变调用方之后的随机序列；用局部 `random.Random`。
- **跨查询比较 MaxSim 分数**：分数随查询 token 数增长，阈值拒答前要归一化或校准。
- **对比实验口径不一**：求和 vs 平均、"平均余弦" vs "池化后余弦"不是一回事，结论会被尺度差异放大或反转。
- **MaxSim 方向写反**：`Σ_j max_i`（对 patch 求和）会让 patch 多的页面天然高分。
- **低估存储**：每页数百个向量，ColPali 原始存储约是单向量的百倍以上；大于 1 万页的语料必须做 PQ/OPQ（skill 文件硬性要求）。
- **生产中仍做暴力 MaxSim**：百万页级必须先 ANN 召回再重排，否则延迟以分钟计。
