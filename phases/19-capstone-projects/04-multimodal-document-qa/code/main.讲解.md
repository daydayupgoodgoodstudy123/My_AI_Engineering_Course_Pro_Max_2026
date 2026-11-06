# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 04 节 多模态文档问答——以视觉处理 PDF、表格与图表 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`、`re`、`dataclasses`），不需要 PDF、图像库、模型或 GPU
>
> 同目录下的 `code/ts/` 是 TypeScript 版本（页面渲染与查看器 API），不在本讲解范围内。

---

## 1. 这份代码在考察什么

讲义的系统是：PDF 页面渲染成图像 → ColQwen 多向量 embedding（每页约 2048 个 patch）→ DocPruner 剪枝 50% → 多向量索引 → MaxSim 检索 top-k 页 → VLM 读图回答并给出证据区域。`main.py` 的 docstring 说明它只实现 "late-interaction retrieval" 这一核心，并且 "on synthetic patch embeddings"：

1. **Multi-vector 表示**：每页不是一个向量，而是一组 "patch" 向量（这里一个文本 token = 一个 patch）。
2. **MaxSim**：对每个查询 token 取与所有 patch 的最大点积，再求和——ColPali / ColQwen 的打分核心。
3. **DocPruner 式剪枝**：每页只保留一半 patch，并做"剪枝前后 top-3 是否一致"的消融。
4. **Top-k 检索**：按 MaxSim 分数排序返回页面。

没有实现的：页面渲染、真实视觉模型、VLM 合成、证据区域、OCR fallback、ViDoRe 评估。

> 一句话：**把 ColPali 的 MaxSim 打分写成三重循环让你看清楚，但"patch"其实是文本 token 的随机向量——所以这份代码能演示算法形状，却不能说明 vision-first 的效果，剪枝部分甚至给出了误导性的直觉。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `EMB_DIM = 16` | 常量 | 向量维度（ColQwen 实际为 128） | patch embedding 维度 |
| `tokenize` | 函数 | `\w+` 小写分词 | 查询 token 化 / "页面内容" |
| `hash_embed` | 函数 | 以 token 哈希为种子生成 16 维随机单位向量 | 查询塔 / 文档塔的替身 |
| `Page` | dataclass | `doc_id`、`page_num`、内容 token、patch 向量；`embed_patches()` | 一页 = 多向量 |
| `doc_prune` | 函数 | 按 L1 范数保留前 `keep_fraction` 的 patch | DocPruner |
| `dot` / `max_sim_score` | 函数 | 点积；MaxSim | late interaction 打分 |
| `Index` | dataclass | 存页面；`retrieve` 对所有页暴力打分取 top-k | 多向量索引（Vespa/Qdrant） |
| `CORPUS` | 常量 | 6 份文档共 10 页的内容描述（财报、论文、手写、图表） | 模拟语料 |
| `build_index` | 函数 | 分词 → embed → （可选）剪枝 → 入索引 | 摄取管道 |
| `main` | 函数 | 4 个查询的 top-3 + 剪枝消融 | 演示 |

数据流：`CORPUS` 文本 → `tokenize` → `Page.embed_patches()`（每个 token 一个向量）→ `doc_prune`（保留一半）→ `Index.add`；查询 → `tokenize` → 每个 token `hash_embed` → 对每页 `max_sim_score` → 排序取 top-k。

---

## 3. 逐段精讲

### 3.1 `hash_embed`：以哈希为种子的随机向量

```python
EMB_DIM = 16

def hash_embed(tok: str) -> list[float]:
    rnd = random.Random(hash(tok) & 0xFFFFFFFF)
    v = [rnd.gauss(0, 1) for _ in range(EMB_DIM)]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]
```

- `random.Random(seed)` 创建一个**独立的**随机数生成器，不影响全局 `random`；同一个种子产生同一串随机数，所以同一个 token 在同一进程内总得到同一个向量。
- `hash(tok) & 0xFFFFFFFF`：按位与取低 32 位，把可能为负的哈希值变成非负整数做种子。
- 16 个标准正态数再 L2 归一化，得到 16 维球面上的均匀随机单位向量。
- 性质：**相同 token 点积 = 1**；不同 token 点积近似 `N(0, 0.25²)`。所以这个"embedding"只认"完全相同的词"，没有任何语义（`margin` 与 `margins` 毫无关系）。
- ⚠️ `hash()` 对字符串每个进程加随机盐，结果**跨运行不确定**。我们用 `PYTHONHASHSEED=0/1/2` 运行，EMEA 查询的 top-1 依次为 `p.88`、`p.88`、`chart-report p.12`。修复：`random.Random(zlib.crc32(tok.encode("utf-8")))`。

### 3.2 `Page`：一页 = 一组向量

```python
@dataclass
class Page:
    doc_id: str
    page_num: int
    content_tokens: list[str]          # stand-in for page contents
    patches: list[list[float]] = field(default_factory=list)

    def embed_patches(self) -> None:
        """Multi-vector: each content token becomes a patch vector."""
        self.patches = [hash_embed(t) for t in self.content_tokens]
```

- 这就是 **multi-vector** 的数据形状：`patches` 的形状为 `(n_patches, 16)`。在真实 ColQwen 中，形状约为 `(2048, 128)`（讲义数字），每个向量对应页面图像上的一个区域。
- 关键差异：真实 patch 是**图像块**，可以表达表格线、柱状图、手写笔迹；这里的 patch 是**文本 token**，本质上仍是 "OCR-then-text" 的世界，只是换了个打分方式。
- 重复 token 会产生重复 patch（本语料各页 token 恰好没有重复）。

### 3.3 `doc_prune`：按 L1 范数剪枝

```python
def doc_prune(patches, keep_fraction: float = 0.5):
    scored = [(sum(abs(x) for x in p), p) for p in patches]
    scored.sort(key=lambda x: -x[0])
    keep_n = max(1, int(len(scored) * keep_fraction))
    return [p for _, p in scored[:keep_n]]
```

- 计算每个 patch 的 L1 范数，降序排序，保留前 `int(n × 0.5)` 个（至少 1 个）。`p.88` 有 13 个 patch，保留 6 个（`int(6.5) = 6`）。
- ⚠️ **三处说法不一致**：讲义说 DocPruner "keep high-variance patches"；函数上方注释写 "keep top-fraction patches by norm variance"；docstring 写 "highest per-patch norm"；代码实际是 L1 范数。
- ⚠️ **这个剪枝等价于随机剪枝**：向量已经 L2 归一化，L1 范数只反映分量分布是否均匀（抽样范围约 2.27–3.79），与 token 是否重要无关。`PYTHONHASHSEED=2` 时 `p.88` 保留的是 `['18','2','16','8','140bp','four']`，把 `segment`、`emea`、`operating`、`margin` 全部丢掉。
- 我们用 30 个种子统计 4 个演示查询的 hit@1（不剪枝 / 剪枝）：22/16、30/17、30/24、30/16。与讲义"50% 压缩、损失 < 0.5%"相反，这里损失很大。原因是真实页面图像里大量 patch 是空白、背景，剪掉无伤大雅；而这里每个 patch 都是一个有内容的词。
- docstring 自己也承认是 "poor proxy for info density"。

### 3.4 `max_sim_score`：late interaction 的核心

```python
def max_sim_score(query_tokens, doc_patches) -> float:
    total = 0.0
    for q in query_tokens:
        best = -1e9
        for p in doc_patches:
            s = dot(q, p)
            if s > best:
                best = s
        total += best
    return total
```

- 公式：`score = Σ_i max_j ⟨q_i, d_j⟩`。外层遍历查询 token，内层在页面所有 patch 中找最大点积，最后求和。
- 复杂度：`O(n_q × n_p × d)`。讲义规模下每页 `20 × 2048 × 128 ≈ 5.2M` 次乘加，10k 页约 524 亿次——所以生产中需要两阶段检索、量化等手段。
- `best = -1e9` 作为初始值；若 `doc_patches` 为空，每个查询 token 会贡献 −1e9（`doc_prune` 的 `max(1, ...)` 保证了至少一个 patch）。
- 等价的 NumPy 写法：`(Q @ P.T).max(axis=1).sum()`，其中 `Q: (n_q, d)`、`P: (n_p, d)`、`Q @ P.T: (n_q, n_p)`。
- **噪声与长度偏置**：不匹配的查询 token 也会贡献"N 个随机点积中的最大值"，N 越大越高（16 维下 N=5 约 0.29、N=13 约 0.41）。EMEA 查询有 9 个 token，只有 3 个精确命中 `p.88`，另外 6 个贡献约 `6 × 0.41 ≈ 2.5` 的噪声，估算总分 ≈ 5.46，与实测 5.2–5.3 吻合。真实模型中停用词向量经过训练，噪声小得多。
- ColBERT/ColPali 原版对查询和文档向量都做归一化后点积（即余弦），这里向量本来就是单位向量，二者等价。

### 3.5 `Index.retrieve`：暴力打分

```python
    def retrieve(self, query: str, k: int = 5) -> list[tuple[Page, float]]:
        q_tokens = [hash_embed(t) for t in tokenize(query)]
        scored = [(pg, max_sim_score(q_tokens, pg.patches)) for pg in self.pages]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]
```

- 查询端同样分词、每个 token 一个向量——对应讲义第 3 步 "embed with the query tower (token-level embeddings)"。
- 对**每一页**都计算 MaxSim 再排序，是最朴素的全量扫描。Vespa / Qdrant 会先用 ANN 召回候选再精排。
- 查询中的 `what`、`was`、`the`、`for` 等停用词没有过滤，都参与打分（贡献噪声）。

### 3.6 `CORPUS` 与 `build_index`

```python
CORPUS = [
    ("10k-2024", 88, "segment EMEA operating margin 18.2 to 16.8 decline 140bp table four"),
    ...
    ("chart-report", 12, "bar chart operating margin by segment with 2023 2024 comparison"),
]

def build_index(prune: bool = True) -> Index:
    idx = Index()
    for doc, page, text in CORPUS:
        p = Page(doc_id=doc, page_num=page, content_tokens=tokenize(text))
        p.embed_patches()
        if prune:
            p.patches = doc_prune(p.patches, keep_fraction=0.5)
        idx.add(p)
    return idx
```

- 10 页的"内容"是对页面的文字描述（例如 `p.88` 对应讲义 Use It 中的 "Table 4, Segment Operating Margin"），每页 6–13 个 token。
- `tokenize` 会把 `18.2` 拆成 `18` 和 `2`，`ColPali` 变成 `colpali`。
- for 循环里的 `for doc, page, text in CORPUS` 是**元组解包**。
- 注意 `chart-report p.12` 同样包含 `operating`、`margin`、`2024`，与 `p.88` 对 EMEA 查询的精确命中数相同（各 3 个），所以即使不剪枝，EMEA 查询的 top-1 也取决于随机噪声（30 个种子中 `p.88` 只赢了 22 次）。

### 3.7 `main`：查询演示与剪枝消融

```python
    full = build_index(prune=False)
    pruned = build_index(prune=True)
    q = "chart comparing segment margins"
    full_top = [(p.doc_id, p.page_num) for p, _ in full.retrieve(q, 3)]
    prn_top = [(p.doc_id, p.page_num) for p, _ in pruned.retrieve(q, 3)]
    print(f"  overlap       : {len(set(full_top) & set(prn_top))}/3")
```

- 用集合交集比较剪枝前后 top-3 的重合度——这是"剪枝是否伤害检索"的最简单代理指标。
- ⚠️ 只用 1 个查询、1 次运行做结论，样本太小；`overlap` 在不同种子下是 3/3、1/3、2/3。正确做法是在标注集上比较 nDCG@5，并多次实验（讲义练习 2）。
- 查询用 `margins`（复数），而语料是 `margin`，精确匹配的替身向量完全无法关联，这也说明它没有语义能力。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用文本 token 冒充图像 patch | 不加载模型就能看到 MaxSim 的计算 | 无法体现 vision-first 对表格/图表/手写的优势；生产用 ColQwen2.5 / ColQwen3-omni |
| 哈希种子随机向量 | 零依赖、同进程内稳定 | 只认精确词；`hash()` 跨进程不确定，应改 `zlib.crc32` |
| 16 维 | 计算快 | 随机点积噪声大（σ≈0.25）；ColQwen 用 128 维 |
| 三重 Python 循环 | 算法一目了然 | 极慢；生产用矩阵乘法 + GPU，或 Vespa 的 MaxSim 排序表达式 |
| 按 L1 范数剪枝 | 演示"剪掉一半"的接口 | 相当于随机删词，严重伤害检索；真实剪枝基于区域信息量，且必须在评估集上验证 |
| 全量暴力检索 | 10 页无所谓 | 万页以上需要 ANN 召回 + 精排、量化、分片 |
| 只看一次 top-3 overlap | 输出简单 | 统计上不可靠；应报告 nDCG@5 与多次实验结果 |
| 无 VLM、无证据区域、无 OCR 通道 | 聚焦检索 | 讲义第 4–8 步才构成完整系统 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| 模块级常量 | `EMB_DIM = 16`、`CORPUS = [...]` | 全大写表示常量（约定，非强制） |
| `random.Random(seed)` | `rnd = random.Random(hash(tok) & 0xFFFFFFFF)` | 独立的随机数生成器实例，不影响全局状态 |
| `rnd.gauss(0, 1)` | 生成向量分量 | 正态分布随机数 |
| 按位与 | `hash(tok) & 0xFFFFFFFF` | 取低 32 位，得到非负整数 |
| 十六进制字面量 | `0xFFFFFFFF` | 等于 4294967295 |
| `or` 兜底 | `math.sqrt(...) or 1.0` | 范数为 0 时用 1.0，防止除零 |
| `@dataclass` + `field(default_factory=list)` | `class Page`、`class Index` | 可变默认值必须用工厂函数 |
| 方法修改自身状态 | `self.patches = [...]` 于 `embed_patches` | 返回 `None`、原地更新对象 |
| 嵌套列表类型注解 | `list[list[float]]` | 二维"矩阵"的纯 Python 表示 |
| 元组列表 + 排序 | `scored = [(score, p) ...]`、`scored.sort(key=lambda x: -x[0])` | 按第一个元素降序 |
| `int()` 截断 | `int(len(scored) * keep_fraction)` | 向零取整，13 × 0.5 → 6 |
| `max(1, ...)` | `keep_n = max(1, ...)` | 保证至少保留 1 个 |
| `zip` + 生成器表达式 | `sum(x * y for x, y in zip(a, b))` | 点积 |
| 元组解包遍历 | `for doc, page, text in CORPUS:` | 每个元素是三元组 |
| 集合交集 | `set(full_top) & set(prn_top)` | 统计重合页面；元组可哈希，能放进集合 |
| f-string 格式符 | `f"score={score:+.3f}"` | `+` 强制显示正负号，`.3f` 三位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 被导入时不执行 `main()` |

---

## 6. 运行结果解读

实际运行一次（Python 3.13，未设置 `PYTHONHASHSEED`；**每次运行分数与排序都可能不同**）：

```text
=== build index with DocPruner (50% patches) ===
pages indexed: 10

Q: what was the 2024 operating margin change for EMEA
  score=+3.541  chart-report p.12
  score=+3.301  10k-2024 p.88
  score=+2.814  10k-2024 p.92

Q: late interaction retrieval vs OCR
  score=+3.074  paper-vidore-v3 p.3
  score=+2.909  paper-vidore-v3 p.7
  score=+1.678  10k-2024 p.92

Q: handwritten experimental figures with error bars
  score=+2.457  handwritten-lab p.6
  score=+1.963  chart-report p.12
  score=+1.706  10k-2024 p.92

Q: bar chart comparing segment margins
  score=+2.400  chart-report p.12
  score=+1.997  10k-2024 p.92
  score=+1.880  paper-vidore-v3 p.7

=== ablation: pruning off vs on ===
  full    top-3 : [('chart-report', 12), ('chart-report', 11), ('10k-2024', 88)]
  pruned  top-3 : [('chart-report', 12), ('chart-report', 11), ('paper-vidore-v3', 7)]
  overlap       : 2/3
```

逐项解读：

- **分数的量级**：每个精确命中的查询 token 贡献 1.0，其余 token 贡献 0.3–0.4 左右的噪声。EMEA 查询剪枝后 `p.12` 得 3.54、`p.88` 得 3.30——两页对该查询都有 3 个可命中词（`operating`、`margin` 外加 `2024` 或 `emea`），剪枝后各自剩下几个、噪声多大，决定了谁排第一。这一次 `p.88` 输给了 `p.12`，而讲义 Use It 中正确答案是 `p.88`。
- **"handwritten experimental figures with error bars"**：`handwritten-lab p.6` 的内容是 "graph with annotated error bars figure 3 caption"，命中 `with`、`error`、`bars`；注意它并没有命中 `handwritten`（那个词在 `p.5`），也就是说"手写"这个视觉属性完全靠文本词碰运气。
- **剪枝消融**：本次 overlap 为 2/3。换种子重跑分别得到 3/3、1/3、2/3（`PYTHONHASHSEED=0/1/2`）。30 个种子的统计见 3.3：剪枝使 hit@1 明显下降。
- **与讲义的差距**：讲义 Use It 展示 "top-5 pages in 320ms (ColQwen2.5, MaxSim, Vespa)"、VLM 合成与带表格编号的引用，本代码只到"打印 top-3 页面和分数"为止。

---

## 7. 动手改一改

1. **修复确定性**：把种子换成 `zlib.crc32(tok.encode("utf-8"))`，确认多次运行输出一致。
2. **NumPy 化**：用 `(Q @ P.T).max(axis=1).sum()` 重写 `max_sim_score`，再写一个 padding + mask 的批量版本一次给所有页打分（测验 Q12），与原函数逐页对比误差 < 1e-9。
3. **量化剪枝影响**：给每个演示查询标注正确页，写一个脚本在 30 个 `PYTHONHASHSEED` 下统计 hit@1 / nDCG@3，比较 `keep_fraction` 为 1.0、0.75、0.5、0.25 的结果，画出"压缩率—精度"曲线（讲义练习 2 的缩小版）。
4. **模拟真实页面**：给每页加入若干"空白 patch"（例如与任何词都无关的固定噪声向量），再实现一个"剪掉空白 patch"的剪枝，观察它为什么能在不伤精度的情况下压缩——这才是 DocPruner 想利用的现象。
5. **Hybrid 检索**：为每页的文本内容建一个 BM25 索引（可复用第 02 节的实现）当作 "OCR-then-text" 通道，与 MaxSim 结果做 RRF 融合（讲义练习 3），比较三种方式在 4 个查询上的排名。
6. **进阶：接真实模型**：安装 `colpali-engine`，用 PyMuPDF 渲染几页真实 PDF，替换 `hash_embed` 与 `embed_patches`，观察 patch 数量、向量维度和存储量。

---

## 8. 常见坑

- **用 `hash()` 做随机种子**：字符串哈希每进程不同，"确定性的假 embedding"会变成每次运行都不同的结果。
- **把文本 token 当 patch 就以为实现了 vision-first**：真正的优势来自图像——表格结构、图表、手写；文本替身只能验证 MaxSim 的计算。
- **凭一次消融下结论**：随机性很大的系统必须多次实验、报告分布或置信区间。
- **剪枝不看内容**：在每个单元都有信息的表示上做查询无关剪枝，等于随机删内容；我们试过按 IDF 保留稀有词，EMEA 查询的 hit@1 反而从 22/30 降到 4/30。
- **忽略 MaxSim 的噪声项**：查询越长、页面 patch 越多，无关 token 的"最大值噪声"越大，可能盖过真实命中。
- **MaxSim 写成"所有点积求和"或"取全局最大"**：正确做法是逐查询 token 取最大再求和。
- **空页面**：`doc_patches` 为空时 `best` 保持 −1e9，会把总分拖到极小；剪枝时要保证至少保留一个 patch。
- **剪枝后丢失位置信息**：生产中 patch 还要关联页面坐标以绘制证据区域，剪枝时必须一并保留。
