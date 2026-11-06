# 测验 · ColPali 与视觉原生文档 RAG（ColPali and Vision-Native Document RAG）

> **阶段 12 · 多模态 AI · 第 23 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 文本 RAG 的五步损耗 | PDF → OCR 文本 → 300–500 token 切块 → 单向量 embedding → 余弦检索 → LLM；图表数据丢失、表格行被切断、多栏版面被压平、图注消失 |
| 2 | ColPali 的核心主张 | 不抽文本，直接把**页面图像**编码成 patch 向量，用 ColBERT 式 late interaction 检索，保留版面、图表、字体信息 |
| 3 | Bi-encoder vs late interaction | bi-encoder 每个文档一个向量，快、省存储但丢细节；late interaction 每个 token/patch 一个向量，召回强但存储大 |
| 4 | MaxSim | `score = Σ_i max_j cos(q_i, p_j)`：每个查询 token 各自挑最匹配的文档 token/patch，再求和 |
| 5 | ColPali 流程 | 入库：PDF → 页图 → PaliGemma → 缓存全部 patch 向量；查询：文本 → 查询 token 向量 → 对所有页做 MaxSim → top-k 页；生成：top-k 页图 + 问题 → VLM |
| 6 | 变体 | ColQwen2 把底座换成 Qwen2-VL，质量更好；ColSmol 约 1B，可在消费级 GPU 上跑；VisRAG 把每页池化成一个向量做 bi-encoder 检索，存储小、召回弱；M3DocRAG 扩展到多文档多页推理 |
| 7 | ViDoRe 基准 | ColPali 配套的视觉文档检索基准，指标 nDCG@5；讲义：ColPali-v1 约 80%，同一批文档上的文本 RAG 约 50–60% |
| 8 | 存储算术 | 每页 `N_p × D × 4 字节`：729 × 128 × 4 = 373,248 字节 ≈ 365 KiB；PQ/OPQ 压缩约 8 倍 ≈ 46 KiB；768 维单向量只需 3 KiB |
| 9 | 文本 RAG 仍占优的场景 | 无版面信号的纯文本（wiki、聊天记录）；存储主导成本的数百万页档案；监管要求同时提供可抽取 OCR 文本 |
| 10 | 质量与成本的取舍 | ColPali 求质量，VisRAG 求规模；大语料常用"便宜召回 + MaxSim 重排"的两阶段方案 |

### 核心技能（能动手做到）

- [ ] 手写 `cosine` 与 `maxsim`，并能用 NumPy 一次矩阵乘法 + `max` + `sum` 实现向量化 MaxSim
- [ ] 按 `页数 × patch 数 × 维度 × 字节数 ÷ 压缩比` 估算任意语料的索引大小，并与文本 RAG 比较倍数
- [ ] 构造一个"信号只在少数 patch 中"的合成数据集，实测 MaxSim 与 bi-encoder（均值池化）的 hit@1 差异
- [ ] 读懂并诊断本节玩具检索的失败原因（话题偏置沿全 1 方向，期望余弦只随页面偏置单调增长）
- [ ] 针对给定语料规模、延迟预算、存储预算，在 ColPali / ColQwen2 / ColSmol / VisRAG / 文本 RAG 之间做选择并给出理由
- [ ] 说出 MaxSim 暴力计算的复杂度，并设计 ANN 召回 + MaxSim 重排的两阶段检索

---

## 二、基础自测（选择题）

**Q1.** ColBERT / ColPali 的 MaxSim 打分公式是（`q_i` 为查询 token 向量，`p_j` 为文档 token 或页面 patch 向量）：

- A. `max_i max_j cos(q_i, p_j)`
- B. `Σ_j max_i cos(q_i, p_j)`
- C. `mean_i mean_j cos(q_i, p_j)`
- D. `Σ_i max_j cos(q_i, p_j)`

**Q2.** 关于 bi-encoder 与 late interaction，说法正确的是：

- A. bi-encoder 每个文档只存一个向量，检索快、省存储，但丢失细粒度信息；late interaction 每个 token/patch 存一个向量，召回更强、存储更大
- B. late interaction 在查询时把查询和文档拼接后过一遍 cross-encoder，所以最准也最慢
- C. bi-encoder 每个 token 一个向量，late interaction 每个文档一个向量
- D. 两者存储相同，区别只在于相似度用余弦还是点积

**Q3.** 讲义练习 1：一份 200 页的年报，每页 729 个 patch，128 维，4 字节浮点。原始存储和 8 倍 PQ 压缩后的存储约为：

- A. 约 18.7 MB 与 2.3 MB
- B. 约 74.6 KB 与 9.3 KB
- C. 约 74.6 MB 与 9.3 MB
- D. 约 597 MB 与 74.6 MB

**Q4.** 讲义写道：50 页财报 ColPali 原始约 18 MB、文本 RAG（50 个 768 维向量）约 150 kB，"ColPali is ~30x more storage per document"。按这两个数字实际计算，倍数约为：

- A. 约 30 倍，与讲义一致
- B. 约 121 倍，讲义的"约 30 倍"与它自己给出的两个数字不符
- C. 约 8 倍，因为 PQ 压缩比是 8
- D. 约 4.8 倍，因为 729 / 150 ≈ 4.8

**Q5.** 关于 VisRAG，讲义的描述是：

- A. 用 VLM 把每页池化成一个向量，再做 bi-encoder 检索：索引更快、存储更小，但召回更弱
- B. 在 patch 上做 MaxSim，但把底座换成了 Qwen2-VL
- C. 一种多文档多页推理框架，把多页拼成一个上下文给 VLM
- D. ColPali 的评测基准，指标是 nDCG@5

**Q6.** 按讲义，下列哪种语料**仍然更适合文本 RAG**？

- A. 以图表为主的季度财报
- B. 含公式和插图的科学论文
- C. 带签名栏和多栏排版的法律合同
- D. 几乎没有版面信息的 wiki 文章和聊天记录

**Q7.** 运行本节代码，查询 `'Q3 revenue growth'`（偏置 1，本应匹配偏置也为 1 的 `page_0_finance`）的第 1 名却是 `page_2_legal`。最根本的原因是：

- A. MaxSim 公式写错了，应该取 min
- B. 话题被编码为"所有维度同加 `bias/10`"，即沿全 1 方向平移；查询与页面的期望余弦近似 `m_q·m_p / √((1+m_q²)(1+m_p²))`，只随**页面偏置**单调增大，与"话题是否匹配"无关，再叠加 32 维高斯噪声，排名基本随机
- C. `random.seed(7)` 选得不好，换个种子就能全部检索正确
- D. 页面只有 16 个 patch，太少，增加到 729 个就能检索正确

**Q8.** 代码 `compare_maxsim_vs_mean()` 输出 `MaxSim : 1.478`、`Mean : 0.501`，并据此说明"late interaction beats bi-encoder recall"。下列分析最准确的是：

- A. 结论完全成立：1.478 约为 0.501 的 3 倍，说明 MaxSim 召回是 bi-encoder 的 3 倍
- B. MaxSim 永远大于 1，均值永远小于 1，所以这个比较没有意义
- C. 这两个数不在同一尺度：MaxSim 是对 2 个查询 token 求和，按 token 平均后是 0.739；而且"所有 pair 余弦的平均"并不是 bi-encoder——真正的 bi-encoder 是 `cos(mean(q), mean(p))`，在这组数据上为 0.993，反而高于 MaxSim。这个演示并不能证明 MaxSim 的召回优势
- D. 均值低是因为代码里的 `1e-8` 平滑项导致数值误差

---

## 三、动手 / 代码题

**Q9.** 本节玩具检索的数据构造如下：

```python
def random_emb(dim: int, bias: int = 0) -> list[float]:
    return [random.gauss(bias / 10.0, 1.0) for _ in range(dim)]

def build_pages(n_pages: int = 5, n_patches: int = 16, dim: int = 32) -> list[Page]:
    ...
    for i, topic in enumerate(topics[:n_pages]):
        bias = i + 1
        patches = [random_emb(dim, bias) for _ in range(n_patches)]
```

查询 "Q3 revenue growth"、"proof of lemma 3"、"patient diagnosis" 的偏置分别是 1、2、4，对应 finance、science、medical 页。

1. 实际运行中三个查询的 top-1 分别是什么？有几个是对的？
2. 用期望余弦的近似公式解释为什么"偏置越大的页面越容易排第一"。如果把种子换成 200 组重复实验，hit@1 大约是多少？
3. 重写数据构造，让每个话题有一个随机单位"原型方向"；每页 16 个 patch 中只有 3 个是"原型 + 小噪声"，其余是随机单位向量；查询 token 是"原型 + 噪声"。写出关键代码，并说明修复后的 hit@1。

**Q10.** 把 `maxsim` 向量化：

1. 用 NumPy 写 `maxsim_np(Q, P)`，`Q` 形状 `(N_q, D)`，`P` 形状 `(N_p, D)`，结果需与原 `maxsim` 一致；再写一个对 `(N_pages, N_p, D)` 一次算出所有页分数的版本。
2. 估算暴力 MaxSim 的计算量：1,000,000 页、每页 729 个 patch、128 维、查询 20 个 token，每次查询需要多少次乘加？FP16 存储所有 patch 向量需要多少 GB？
3. 讲义练习 4 要求 500 ms 内完成查询。说明为什么不能直接暴力，并给出一个两阶段方案。

**Q11.** 设计一个实验，证明"当相关信息只出现在页面的极少数 patch 中时，MaxSim 明显优于 bi-encoder"：

1. 写出 bi-encoder 打分函数 `bienc(q, p)`（对查询 token 和页面 patch 分别做均值池化再求余弦）。
2. 用 Q9 第 3 问的数据构造，分别在"16 个 patch 中 3 个是信号"和"64 个 patch 中只有 1 个是信号"两种设置下，跑 200 个种子，比较两种方法的 hit@1，并解释结果。

---

## 四、面试高频题

**Q12.**（基础必考）解释 bi-encoder、cross-encoder 与 late interaction（ColBERT）三种检索架构的区别：各自存什么、查询时算什么、质量与成本如何？

**Q13.**（原理深挖）为什么 ColPali 在视觉丰富的文档上比文本 RAG 好 20–40%（讲义数字）？请沿着文本 RAG 的五个步骤逐一指出信息在哪里丢失，以及 ColPali 如何保留。MaxSim 的"求和"相比"平均相似度"捕捉到了什么？（讲义练习 2）

**Q14.**（工程实践）给 100 万页文档做视觉 RAG，单次查询延迟预算 500 ms，存储预算有限。你选 ColQwen2 还是 VisRAG？请给出存储估算、索引结构和检索流程。（讲义练习 4）

**Q15.**（场景设计）公司现有一套基于文本切块的财报问答 RAG，业务方抱怨"图表里的数字答不上来"。请设计向视觉原生 RAG 迁移的方案：如何评估、如何 A/B、何时全量切换、是否保留文本 RAG？

**Q16.**（追问型）MaxSim 有哪些弱点或陷阱？例如不同长度查询的分数可比性、无意义的查询 token、对精确数字/编号的匹配、存储与延迟。分别怎么缓解？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Score = sum over query tokens of max over document tokens of cosine similarity: Σ_i max_j cos(q_i, d_j)。" 外层对**查询** token 求和，内层对**文档** token/patch 取最大。代码对应：

```python
    for q in query_tokens:
        best = max(cosine(q, p) for p in patches)
        s += best
```

A 只保留了最匹配的一对，丢掉了"每个查询词都要有着落"的信息；B 把求和与取最大的对象对调了，变成"每个 patch 找最像的查询 token"，页面 patch 越多分数越高；C 是代码里拿来对比的"均值相似度"，会被无关 patch 稀释。

### Q2 — 答案：A

讲义 Key Terms："Bi-encoder — One vector per document; faster but loses granularity"；"Multi-vector — Store N_p vectors per document / page; storage cost grows but recall improves"。B 描述的是 cross-encoder（查询与文档拼接后联合编码，无法预先缓存文档表示）；late interaction 的文档向量可以离线缓存，查询时只做 MaxSim。C 说反了；D 错，存储差两个数量级（Q4）。

### Q3 — 答案：C

`200 × 729 × 128 × 4 = 74,649,600` 字节 ≈ 74.6 MB；÷ 8 ≈ 9.33 MB（已用 Python 计算）。A 是讲义中 50 页的数字；B 单位错了 1000 倍；D 把 4 字节又乘了 8。

### Q4 — 答案：B

`50 × 729 × 128 × 4 = 18,662,400` 字节；`50 × 768 × 4 = 153,600` 字节；比值 `≈ 121.5`。讲义"约 30 倍"与它自己的两个数字不符。同样，讲义说"~4 MB after PQ"，而按它在 Key Terms 和 skill 文件中采用的 8 倍压缩应为约 2.33 MB；压缩后与文本 RAG 的比值约 15 倍，也高于讲义所说的"~5–10x"。C 混淆了压缩比与存储倍数；D 是无意义的计算。

### Q5 — 答案：A

讲义："instead of MaxSim on patches, pool each page into a single vector with a VLM then bi-encoder retrieve. Faster indexing + smaller storage, weaker recall." B 描述的是 ColQwen2；C 是 M3DocRAG；D 是 ViDoRe。

### Q6 — 答案：D

讲义 "When text-RAG still wins" 列了三类：无版面信号的纯文本（wiki、聊天记录）、存储主导成本的数百万页档案、需要可抽取 OCR 文本的监管场景。A、B、C 都是讲义说"vision-native RAG wins"的类型（财报、科学论文、法律合同）。skill 文件也规定纯文本语料应拒绝视觉 RAG。

### Q7 — 答案：B

实际运行的全部分数（已打印验证）：

| 查询（偏置） | finance(1) | science(2) | legal(3) | medical(4) | engineering(5) |
|------|------|------|------|------|------|
| Q3 revenue growth (1) | 1.314 | 1.154 | **1.403** | 0.906 | 0.934 |
| proof of lemma 3 (2) | 1.446 | 1.497 | 1.462 | **1.687** | 1.585 |
| patient diagnosis (4) | 1.530 | **1.574** | 1.347 | 1.348 | 1.198 |

三个查询 top-1 全错。设查询均值 `m_q = b_q/10`、页面均值 `m_p = b_p/10`，每维方差 1，则期望余弦约为 `m_q·m_p / √((1+m_q²)(1+m_p²))`：对 `b_q = 1`，五个页面依次约为 `0.0099, 0.0195, 0.0286, 0.0370, 0.0445`——**页面偏置越大越高，与查询是哪个话题无关**。而 32 维随机向量余弦的标准差约 `1/√32 ≈ 0.18`，远大于这些差异，MaxSim 取最大值又会放大噪声。200 个种子重复实验的 hit@1 约 22%，与随机猜（20%）几乎相同，且 `page_4_engineering` 成为 top-1 的次数最多（211/600）。C、D 都无法修复"话题方向相同"这一结构性问题；A 是胡说。

### Q8 — 答案：C

逐对余弦（已计算）：查询 token 1 对四个 patch 为 `[0.774, 0.632, 0.632, 0.0]`，token 2 为 `[0.704, 0.632, 0.632, 0.0]`。MaxSim = 0.774 + 0.704 = 1.478（两个 token 求和），平均到每个 token 是 0.739；"Mean" 是 8 个余弦的平均 0.501，其中零向量 patch 贡献了两个 0。真正的 bi-encoder 是先池化再比较：`cos(mean(q), mean(p)) = 0.993`。所以这个演示既有尺度不一致，又没有和真正的 bi-encoder 比。MaxSim 的优势需要"信号只在少数 patch 里"的场景才能体现（见 Q11）。B 错：余弦在 [-1, 1]，MaxSim 的上界是 `N_q`，不是"永远大于 1"；D 错，`1e-8` 只影响零向量。

### Q9 — 参考答案

1. 实际运行：`'Q3 revenue growth'` → `page_2_legal`（1.403）；`'proof of lemma 3'` → `page_3_medical`（1.687）；`'patient diagnosis'` → `page_1_science`（1.574）。**0/3 正确**；正确页面分别排在第 2、第 3、第 3。

2. 见 Q7 解析：偏置把所有向量沿同一个方向（全 1 方向）平移，期望余弦 ∝ `m_q·m_p`，对任意正偏置的查询都是"页面偏置越大越像"；信号（差值约 0.01–0.03）远小于噪声（约 0.18）。200 个种子 hit@1 约 22%（随机水平 20%）。

3. 修复思路：话题 = 方向，而不是幅度。参考实现（已运行验证）：

```python
def unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]

def build_world(seed, dim=32, n_patches=16, n_signal=3, noise=0.5):
    rng = random.Random(seed)                       # 局部 RNG，不污染全局 random
    topics = ["finance", "science", "legal", "medical", "engineering"]
    proto = {t: unit([rng.gauss(0, 1) for _ in range(dim)]) for t in topics}
    pages = []
    for i, t in enumerate(topics):
        patches = []
        for j in range(n_patches):
            if j < n_signal:                        # 少数 patch 携带话题信号
                patches.append([p + rng.gauss(0, noise / math.sqrt(dim)) for p in proto[t]])
            else:                                   # 其余是无关内容
                patches.append(unit([rng.gauss(0, 1) for _ in range(dim)]))
        rng.shuffle(patches)
        pages.append(Page(f"page_{i}_{t}", patches))
    queries = []
    for text, t in [("Q3 revenue growth", "finance"),
                    ("proof of lemma 3", "science"),
                    ("patient diagnosis", "medical")]:
        toks = [[p + rng.gauss(0, 1.0 / math.sqrt(dim)) for p in proto[t]] for _ in range(4)]
        queries.append((Query(text, toks), t))
    return pages, queries
```

   200 个种子下 MaxSim 的 hit@1 为 **100%**。种子 7 的一次运行：`'Q3 revenue growth'` → finance 2.928，第二名 medical 只有 1.436，差距非常明显。随机高维单位向量近似正交，正是"不同话题 = 不同方向"的合理模型。

### Q10 — 参考答案

1. 参考实现（已验证与原函数结果一致，差异在 1e-7 量级）：

```python
import numpy as np

def maxsim_np(Q, P):
    Qn = Q / np.linalg.norm(Q, axis=1, keepdims=True)    # (N_q, D)
    Pn = P / np.linalg.norm(P, axis=1, keepdims=True)    # (N_p, D)
    return (Qn @ Pn.T).max(axis=1).sum()                 # (N_q, N_p) → (N_q,) → 标量

def maxsim_all_pages(Q, P_all):                          # P_all: (N_pages, N_p, D)，已归一化
    sim = np.einsum("qd,npd->nqp", Q, P_all)             # (N_pages, N_q, N_p)
    return sim.max(axis=2).sum(axis=1)                   # (N_pages,)
```

   生产中会在入库时就把向量 L2 归一化，查询时直接点积，省去每次求范数。

2. 乘加次数：`20 × 729 × 128 × 1,000,000 ≈ 1.87 × 10¹²` 次/查询。FP16 存储：`10⁶ × 729 × 128 × 2 ≈ 186.6 GB`（FP32 为 373 GB，8 倍 PQ 后约 46.7 GB）。本机用 NumPy 对 1,000 页做一次 `einsum` 约 0.33 秒，线性外推到 100 万页约需 5 分钟量级（仅作量级参考，与硬件有关）。

3. 暴力 MaxSim 无论算力还是"把所有向量读一遍"的带宽都远超 500 ms。两阶段方案：
   - **召回**：用便宜的索引筛出几百到几千个候选页——例如 VisRAG 式单向量 + HNSW；或者把所有 patch 向量放进 ANN 索引，每个查询 token 检索 top-k 个 patch，取其所属页面的并集（ColBERTv2/PLAID 一类的思路）；
   - **重排**：只对候选页做精确 MaxSim（几百页 × 729 patch 在 GPU 上是毫秒级）；
   - 存储用 PQ/OPQ 压缩（skill 文件要求 >1 万页必须压缩，目标 8–16 倍），候选页的原始向量可放内存或 SSD；
   - 生成阶段另算：讲义/skill 给出生成器 200–500 ms，因此"检索 + 生成"整体 500 ms 很紧，检索要控制在 100 ms 左右。

### Q11 — 参考答案

1. bi-encoder 打分：

```python
def bienc(q, p):
    mq = [sum(x) / len(q.tokens) for x in zip(*q.tokens)]    # 查询均值池化
    mp = [sum(x) / len(p.patches) for x in zip(*p.patches)]  # 页面均值池化
    return cosine(mq, mp)
```

2. 实测（200 个种子 × 3 个查询）：

| 设置 | MaxSim hit@1 | bi-encoder hit@1 |
|------|------|------|
| 16 个 patch 中 3 个是信号 | 100% | 98.5% |
| 64 个 patch 中只有 1 个是信号 | 99.7% | 34% |

   解释：均值池化后，页面向量 = 信号 patch 与无关 patch 的平均。信号占比 3/16 时，池化向量里仍有足够的话题方向分量；占比降到 1/64，话题分量被 63 个随机向量稀释，与噪声相当，bi-encoder 接近随机（5 个页面，随机水平 20%）。MaxSim 让每个查询 token 直接"找到"那个信号 patch，不受无关 patch 数量影响。这正对应真实场景：财报一页里只有一个小图表含"Q3 营收"，其余是正文和页眉页脚——这就是"MaxSim 的求和捕捉了什么"（讲义练习 2）的答案。

### Q12 — 参考回答要点

- **Bi-encoder**：查询和文档分别编码成**一个**向量，文档向量离线缓存；查询时一次向量检索（ANN），最快、存储最小；把整篇文档压成一个向量会丢掉细粒度匹配。
- **Cross-encoder**：查询与文档拼接后一起过 Transformer，输出相关性分数；质量最高，但文档表示无法预先缓存，每个候选都要跑一次完整前向，只能用于少量候选的重排。
- **Late interaction（ColBERT）**：查询和文档分别编码，但保留**每个 token 的向量**；文档向量可离线缓存，查询时做 MaxSim：`Σ_i max_j cos(q_i, d_j)`。质量接近 cross-encoder，速度介于两者之间，代价是存储（每文档 N_d 个向量）。
- **ColPali**：把 late interaction 从文本 token 推广到页面图像 patch。
- 加分点：典型生产架构是"bi-encoder/BM25 召回 → late interaction 或 cross-encoder 重排"；存储用 PQ 压缩。

### Q13 — 参考回答要点

- **五步损耗**（讲义）：
  1. PDF → 文本：图表里的数字、图注、签名栏这类版面事实丢失；
  2. 切块：表格行、跨栏段落被切断；
  3. 单向量 embedding：一个块的所有信息被压成一个向量；
  4. 余弦检索：只能比较整体相似度；
  5. 送入 LLM：LLM 看不到原图。
- **ColPali 如何保留**：不做 OCR、不切块，直接编码页面图像；每个 patch 向量携带局部的内容和版面；检索后把**页面图像**送给 VLM，图表、字体、布局都进入回答。
- **求和 vs 平均**：平均相似度会被大量无关 patch 稀释（Q11）；MaxSim 让每个查询 token 独立找到最佳证据，再把"每个查询概念是否都有对应证据"累加——一个查询包含"Q3""营收""增长"三个概念，页面需要分别覆盖它们才能拿高分，这接近"软的词项匹配"。
- 数据点：讲义称 ViDoRe 上 ColPali-v1 约 80% nDCG@5，文本 RAG 约 50–60%。
- 常见误区：以为 ColPali 内部做了 OCR；以为 MaxSim 的分数在不同查询之间可直接比较（见 Q16）。

### Q14 — 参考回答要点

- **存储估算**（每页 729 patch、128 维）：ColQwen2 原始 FP32 约 373 GB、FP16 约 187 GB、8 倍 PQ 约 47 GB；VisRAG 单向量（按 768 维 FP32 估）约 3 GB。
- **延迟分析**：暴力 MaxSim 每次查询约 1.9 × 10¹² 次乘加，不可行（Q10）。skill 文件："If retrieval SLA <100ms, prefer VisRAG (bi-encoder) over ColPali MaxSim."
- **推荐方案（两阶段）**：
  - 第一阶段 VisRAG 式单向量 + HNSW 召回 top-200～1000 页（毫秒级）；
  - 第二阶段对候选页用 ColQwen2 的 PQ 压缩 patch 向量做 MaxSim 重排；
  - 生成器取 top-3～5 页图像；
  - 预算分配：查询编码约 10 ms + 召回 + 重排 < 100 ms，剩余留给生成。
- 若只能选一个：延迟极严、存储极紧选 VisRAG；质量优先、可接受更多存储与重排计算选 ColQwen2 + PQ + 候选生成。
- 加分点：用 ViDoRe 风格的 nDCG@5 在自有数据上评估两阶段的召回损失；监控 p95/p99 延迟而不是平均值。

### Q15 — 参考回答要点

- **先建评测集**：从真实工单中收集"图表/表格类"和"纯文本类"问题，标注答案所在页，指标用 nDCG@5、recall@k 和端到端答案正确率。
- **离线对比**：文本 RAG vs ColPali/ColQwen2，分问题类型统计；预期图表类大幅提升、纯文本类持平。
- **在线 A/B**：按用户或会话分流，指标包括答案正确率（人工抽检）、"无法回答"比例、延迟、单次查询成本。
- **切换策略**：可先做**混合检索**——文本 RAG 和视觉 RAG 各取 top-k，融合排序（如 RRF）；或按问题路由（含"图""表""趋势"等走视觉）。当视觉 RAG 在所有类别上不劣于文本 RAG 且成本可接受时再全量。
- **是否保留文本 RAG**：监管场景需要可抽取 OCR 文本（讲义"When text-RAG still wins"），纯文本文档也更便宜，通常保留作为并行通道。
- skill 文件要求的"Migration path from text-RAG. How to A/B, when to fully cutover"即此。

### Q16 — 参考回答要点

- **分数尺度随查询长度变化**：MaxSim 是求和，查询 token 越多分数越高，上界是 `N_q`。同一查询内的排序没有问题，但跨查询设置固定阈值（如"分数 < X 则拒答"）会出错；可除以 `N_q` 归一化，或用排序名次/校准后的分数。
- **无意义查询 token**：停用词、标点也各自贡献一个 max 项。ColBERT 原始做法是对查询做 `[MASK]` 填充（query augmentation）并让模型学习如何利用；工程上也可对 token 加权或过滤。
- **精确匹配弱**：发票号、型号、具体数字在 patch 向量中是"语义化"的，可能匹配到长得像的数字；可与 OCR 文本的 BM25 混合检索。
- **存储与延迟**：每页数百个向量，必须 PQ/OPQ 压缩 + 候选生成 + 重排（Q10、Q14）；patch 数可通过合并/剪枝相似 patch 减少。
- **玩具 demo 的教训**：本节代码中检索结果基本随机，说明合成数据若没有正确的"话题方向"结构，再好的打分函数也体现不出来——评估检索器必须用有标注的真实数据。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)：本节的先修；文本 RAG 的五个步骤正是 ColPali 要替换的对象。
- [阶段 11 · 04 Embeddings 与向量表示](../../../11-llm-engineering/04-embeddings/docs/zh.md)：余弦相似度、bi-encoder 单向量表示。
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：召回 + 重排的两阶段架构、混合检索。
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：VLM 如何把图像变成 patch token。
- [阶段 12 · 22 文档与图解理解](../../22-document-diagram-understanding/docs/zh.md)：OCR pipeline、OCR-free 与 VLM-native 三个时代，ColPali 是"检索侧的 OCR-free"。

### 本节被哪些后续内容用到
- [阶段 12 · 24 多模态 RAG 与跨模态检索](../../24-multimodal-rag-cross-modal/docs/zh.md)：把 ColPali 作为文档路的检索器，与图像、视频、音频检索融合。
- [阶段 19 · 04 多模态文档问答](../../../19-capstone-projects/04-multimodal-document-qa/docs/zh.md)：综合项目中以视觉方式检索并回答 PDF、表格与图表问题。
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../../19-capstone-projects/65-hybrid-retrieval-bm25-dense/docs/zh.md)：与视觉检索混合以弥补精确匹配短板。
- [阶段 19 · 68 RAG Evaluation](../../../19-capstone-projects/68-rag-eval-precision-recall/docs/zh.md)：nDCG、MRR 等检索指标的实现。

### 延伸关键词
`ColBERT` · `late interaction` · `MaxSim` · `multi-vector retrieval` · `ColQwen2` · `ColSmol` · `VisRAG` · `M3DocRAG` · `ViDoRe` · `nDCG@5` · `PQ / OPQ` · `HNSW` · `PLAID` · `query augmentation`
