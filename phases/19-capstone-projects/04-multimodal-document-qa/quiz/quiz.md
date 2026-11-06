# 测验 · 多模态文档问答——以视觉处理 PDF、表格与图表（Capstone 04 — Multimodal Document QA (Vision-First PDF, Tables, Charts)）

> **阶段 19 · 综合项目 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义为机器翻译，术语与数字如有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Vision-first vs OCR-then-text | OCR 会弄乱旋转表格、公式、图表和手写批注；讲义："Treating these as text-first means losing half the signal"，2026 的做法是直接把页面当图像检索 |
| 2 | Late interaction | 查询的每个 token 与页面的每个 patch 分别打分，不先池化成一个向量；保留细粒度匹配 |
| 3 | MaxSim | `score(q, d) = Σ_i max_j ⟨q_i, d_j⟩`：对每个查询 token 取与所有 patch 的最大点积，再求和 |
| 4 | Multi-vector 存储代价 | 讲义：ColQwen 每页约 2048 个 128 维 patch 向量，而不是一个 1024 维向量；10k 页 FP16 约 5.2 GB，是单向量 FP32 的 128 倍 |
| 5 | DocPruner | 讲义：保留高方差（高信息量）patch，50% 压缩、精度损失 < 0.5%；本节代码用 L1 范数做替身，效果很差 |
| 6 | 多向量索引 | Vespa / Qdrant multi-vector / AstraDB 存逐 patch 向量并在检索时执行 MaxSim |
| 7 | VLM 合成与证据区域 | Qwen3-VL-30B / Gemini 2.5 Pro / InternVL3 读取查询 + top-5 页面图像，按 `(doc_id, page)` 引用并给出区域或 bbox |
| 8 | OCR fallback | 公式密集、表格密集页面再跑 Nougat / dots.ocr，把 OCR 文本作为图像之外的额外通道 |
| 9 | 二维评估矩阵 | 内容类型（正文、表格、图表、手写、公式）× 检索方式（vision-first、OCR-then-text、hybrid），每格报 nDCG@5 与答案准确率；ViDoRe v3、M3DocVQA |
| 10 | 本节代码的边界 | 没有图像、没有 VLM；"patch"其实是文本 token 的随机向量，`hash()` 使结果跨进程不确定 |

### 核心技能（能动手做到）

- [ ] 手算一个小例子的 MaxSim 分数，并用 NumPy 一行写出 `(Q @ P.T).max(axis=1).sum()`
- [ ] 估算 multi-vector 索引的存储量与暴力 MaxSim 的计算量，并说出 Vespa/PLAID 一类系统如何降本
- [ ] 指出本节 `hash_embed` 的跨进程不确定性与 `doc_prune` 的"按 L1 范数剪枝 ≈ 随机剪枝"问题，并用多随机种子实验量化影响
- [ ] 解释为什么 MaxSim 对 patch 多的页面有"噪声加成"，以及停用词查询 token 的影响
- [ ] 设计内容类型 × 检索方式的评估矩阵，以及 vision-first 与 OCR 的 hybrid（RRF 融合）
- [ ] 说清证据区域（evidence region）引用的生成、校验与展示流程

---

## 二、基础自测（选择题）

**Q1.** 讲义认为在 10-K 财报、科研论文、手写笔记上，vision-first 检索优于 OCR-then-text，主要原因是：

- A. 图像向量比文本向量维度更低，检索更快
- B. OCR 会弄乱旋转表格、公式和图表，丢失大量信息；把页面当图像直接检索可以保留版式与视觉信号
- C. vision-first 不需要任何索引
- D. OCR 无法处理英文

**Q2.** 一个查询有 2 个 token，页面有 3 个 patch，点积矩阵为：q1 对三个 patch 为 `[0.2, 0.9, 0.1]`，q2 为 `[0.5, 0.3, 0.7]`。MaxSim 分数是：

- A. 0.9
- B. 2.7
- C. 0.8
- D. 1.6

**Q3.** 按讲义数字，10k 页、每页约 2048 个 patch、每个 patch 128 维、FP16 存储，原始 multi-vector 索引大约多大？

- A. 约 5.2 GB
- B. 约 41 MB
- C. 约 2.6 GB
- D. 约 10.5 GB

**Q4.** 与"每页一个池化向量"的单向量检索相比，late interaction 的核心优势是：

- A. 存储更小
- B. 查询时无需计算
- C. 查询的每个 token 都能找到与之最匹配的局部 patch，保留细粒度匹配，避免池化把"表格里的一个数字"淹没在整页信息中
- D. 它不需要训练

**Q5.** 本节代码的 `doc_prune` 用什么给 patch 打分并保留前 50%？

- A. 每个 patch 与所有 patch 的方差
- B. 查询对 patch 的注意力分数
- C. patch 向量的 L1 范数 `sum(abs(x))`
- D. patch 与页面质心的余弦相似度

**Q6.** 讲义保留 OCR fallback（Nougat、dots.ocr）作为额外文本通道，主要用于：

- A. 公式密集、表格密集的页面，让 VLM 同时拿到图像和精确文本
- B. 替代 VLM 生成答案
- C. 减少 multi-vector 的存储量
- D. 训练 ColQwen 模型

**Q7.** 连续运行 `python main.py` 两次，同一个查询的 top-3 页面和分数可能不同，原因是：

- A. `random.gauss` 没有设置种子
- B. `Index.retrieve` 用了多线程
- C. 浮点数求和顺序不确定
- D. `hash_embed` 用 `random.Random(hash(tok) & 0xFFFFFFFF)` 生成向量，而 `hash()` 对字符串每个进程加随机盐，于是每次运行 token 的向量都不同

**Q8.** 讲义评分标准中的 "evidence-region grounding" 衡量的是：

- A. VLM 生成答案的速度
- B. 被引用的证据区域（bbox）中真正包含答案片段的比例
- C. 每页的 patch 数
- D. OCR 文本的字符错误率

---

## 三、动手 / 代码题

**Q9.** DocPruner 替身的实际效果：

```python
def doc_prune(patches, keep_fraction=0.5):
    """Keep patches with highest per-patch norm (poor proxy for info density
    but matches the DocPruner intuition: drop low-signal patches)."""
    scored = [(sum(abs(x) for x in p), p) for p in patches]
    scored.sort(key=lambda x: -x[0])
    keep_n = max(1, int(len(scored) * keep_fraction))
    return [p for _, p in scored[:keep_n]]
```

1. `hash_embed` 已经把每个向量 L2 归一化到长度 1。那么 L1 范数的大小与 token 的"信息量"有关系吗？
2. `10k-2024 p.88` 的内容是 `segment EMEA operating margin 18.2 to 16.8 decline 140bp table four`（13 个 token）。在 `PYTHONHASHSEED=2` 下剪枝后保留了哪些 token？这对查询 "what was the 2024 operating margin change for EMEA" 意味着什么？
3. 用 30 个不同的 `PYTHONHASHSEED` 统计 4 个演示查询的 hit@1（不剪枝 vs 剪枝），结果说明了什么？与讲义"50% 压缩、精度损失 < 0.5%"相比如何？
4. 有人提议"按 IDF 保留最稀有的一半 token"来改进剪枝，你预计效果如何？

**Q10.** MaxSim 的噪声与长度偏置：

```python
def max_sim_score(query_tokens, doc_patches):
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

1. 在这个替身里，查询 token 与页面中**相同**的 token 点积是多少？与**不同**的 token 点积大致服从什么分布？
2. 查询 "what was the 2024 operating margin change for EMEA" 有 9 个 token。不剪枝时 `p.88` 有 13 个 patch，其中哪些 token 精确命中？估算它的 MaxSim 分数，并与实测值（约 5.2–5.3）对照。（已知：16 维随机单位向量与 N 个随机单位向量点积的最大值，期望约为 N=5 时 0.29、N=10 时 0.38、N=13 时 0.41。）
3. 由此说明：为什么 patch 越多的页面在 MaxSim 中有"噪声加成"？真实 ColPali 系统里这个问题如何缓解？

**Q11.** 存储与计算估算（全部写出算式）：

1. 10k 页 × 2048 patch × 128 维：FP16 存储多少？50% 剪枝后多少？与"每页一个 1024 维 FP32 向量"相比是多少倍？
2. 查询 20 个 token，对 10k 页做暴力 MaxSim，需要多少次乘加（MAC）？
3. 讲义要求答案 p95 < 2s。请说出至少三种让 multi-vector 检索在大规模下可行的工程手段。

**Q12.** 把 `max_sim_score` 改写成 NumPy 版本，并扩展为一次给所有页面打分：

1. 写出单页版本，说明每一步的形状。
2. 不同页面的 patch 数不同，如何批量计算？（提示：padding + mask）
3. 如何验证新版本与原版本结果一致？

---

## 四、面试高频题

**Q13.**（基础必考）解释 ColPali 式的 late-interaction 检索：它和 OCR-then-text 的 RAG、和单向量图像检索（如 CLIP）分别有什么区别？

**Q14.**（原理深挖）写出 MaxSim 的公式。为什么它被称为 "late" interaction？它与 cross-encoder（early interaction）和 bi-encoder（no interaction）在效果与成本上如何权衡？

**Q15.**（工程实践）你要把 vision-first 文档问答部署到 1000 万页规模。multi-vector 带来的存储与延迟问题怎么解决？剪枝（如 DocPruner）上线前你会怎样验证？

**Q16.**（场景设计）一家银行希望对历年财报 PDF 做问答，要求答案可追溯到页码和表格位置，并且部分扫描件含手写批注。请设计端到端方案和评估方案。

**Q17.**（追问型）"既然 VLM 已经能直接看图，为什么不把整份 200 页的 PDF 全部作为图像塞给 Gemini 2.5 Pro，而要先做检索？"

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义 Problem 一节："scanned 10-Ks with rotated tables, scientific papers dense with equations, charts that only make sense as images, handwritten annotations. Treating these as text-first means losing half the signal." 并指出在 ViDoRe v3 上 vision-first 明显领先，"the gap widens on charts, tables, and handwriting"。

- A 错：multi-vector 的存储反而大得多（见 Q3）。
- C 错：同样需要多向量索引（Vespa/Qdrant）。
- D 错：OCR 当然能处理英文，问题在版式与非文字信息。

### Q2 — 答案：D

`max(0.2, 0.9, 0.1) + max(0.5, 0.3, 0.7) = 0.9 + 0.7 = 1.6`。

- A（0.9）是整个矩阵的最大值；B（2.7）是所有点积之和；C（0.8）是两个最大值的平均。ColBERT/ColPali 的 MaxSim 是"逐查询 token 取最大，再**求和**"。

### Q3 — 答案：A

`10,000 × 2,048 × 128 × 2 字节 = 5,242,880,000 字节 ≈ 5.24 GB`（已用 Python 计算）。

- B（约 41 MB）是"每页一个 1024 维 FP32 向量"的大小：`10,000 × 1,024 × 4`；
- C（约 2.6 GB）是 50% 剪枝后的大小；
- D（约 10.5 GB）是 FP32 存储时的大小。
- 5.24 GB / 40.96 MB = 128 倍，这就是讲义说的 "Raw storage balloons"，也是 DocPruner 存在的原因。

### Q4 — 答案：C

单向量把整页压成一个点，页面上一个小表格里的某个数字很容易在池化中被稀释；late interaction 让每个查询 token 去所有 patch 中找"最像的那一块"，所以局部、细粒度的证据也能贡献分数。讲义："You get fine-grained matching without needing a single pooled vector."

- A 错，存储更大；B 错，查询时要计算 MaxSim；D 错，ColPali/ColQwen 都是专门训练的。

### Q5 — 答案：C

代码 `scored = [(sum(abs(x) for x in p), p) for p in patches]`，按 L1 范数降序保留前一半。注意 docstring 说 "highest per-patch norm"，函数上方注释说 "by norm variance"，讲义说 "keep high-variance patches"，三处说法都不一致；而 A、B、D 都没有实现。

### Q6 — 答案：A

讲义："For equations and scientific notation, an OCR fallback (Nougat, dots.ocr) is spliced in as an optional text channel." Build It 第 6 步用"图像方差"启发式识别公式密集页，再把 OCR 文本与图像一起送给 VLM。

- B 错：VLM 仍然负责回答；C 错：OCR 通道会增加而不是减少存储；D 错：与训练无关。

### Q7 — 答案：D

`random.Random(seed)` 本身是确定的，问题出在种子 `hash(tok)`：Python 对 `str` 的哈希每个进程加随机盐。我们用 `PYTHONHASHSEED=0/1/2` 分别运行，EMEA 查询的 top-1 分别是 `10k-2024 p.88`、`10k-2024 p.88`、`chart-report p.12`，且 seed=2 时 `p.88` 连前 3 都没进；剪枝消融的 overlap 分别为 3/3、1/3、2/3。

- A 错：`hash_embed` 每次都用自己的 `random.Random(...)` 实例，与全局随机状态无关；B、C 都不存在。
- 修复：`random.Random(zlib.crc32(tok.encode("utf-8")))`。

### Q8 — 答案：B

讲义评分表："Fraction of cited regions that actually contain the answer span." 它衡量的是"引用是否真的指向答案所在位置"，与 RAG 中的 citation faithfulness 是同一思想在视觉文档上的版本。

### Q9 — 参考答案

1. **没有关系。** 每个向量是 16 维高斯随机向量再 L2 归一化，L1 范数只反映"各分量是否均匀"（均匀时 L1 大，集中在少数维度时 L1 小），我们抽样 1 万个单位向量，L1 范数范围约 2.27–3.79。它与 token 是 "emea" 还是 "to" 完全无关，因此这个剪枝本质上是**按 token 哈希的随机剪枝**。
2. 实际运行 `PYTHONHASHSEED=2`：13 个 patch 保留 6 个，对应 token 为 `['18', '2', '16', '8', '140bp', 'four']`——`segment`、`emea`、`operating`、`margin` 全被丢掉了。查询中能精确命中 `p.88` 的三个词（`operating`、`margin`、`emea`）一个都不剩，于是剪枝后 `p.88` 跌出 top-3。同一个种子下 `chart-report p.12` 恰好保留了 `operating`、`margin`、`2024`，排到第一。
3. 我们的实测（30 个种子，hit@1，"不剪枝 / 剪枝"）：EMEA 查询 22/16，late interaction 查询 30/17，手写查询 30/24，柱状图查询 30/16。剪枝后命中次数下降 20%–47%，与讲义"损失 < 0.5%"相去甚远。原因：真实 DocPruner 删掉的是背景、空白等低信息 patch，而这里每个"patch"都是一个有意义的词，随机删一半就是删一半内容。main() 里只看一次消融的 overlap（本次运行 2/3），样本太小，看不出这个问题——这本身也是一个教训：**剪枝的效果必须在评估集上用多次实验量化**（讲义练习 2 "找到压缩悬崖"）。
4. 我们试过：按语料 IDF 保留每页最稀有的一半 token，30 个种子下 EMEA 查询 hit@1 反而从 22 降到 **4**。因为 `operating`、`margin` 同时出现在 `p.88` 和 `chart-report p.12`，IDF 较低被丢弃，而 `18`、`140bp` 这类稀有但查询不会用到的 token 被保留。结论：查询无关（query-agnostic）的剪枝必须基于"这块区域是否承载内容"（如图像中的空白、重复背景），而不是"这个词稀不稀有"；任何剪枝策略都要在目标查询分布上评估。

### Q10 — 参考答案

1. 相同 token 的向量完全相同且是单位向量，点积 = **1.0**。不同 token 的向量是独立的随机单位向量，16 维时点积均值约 0、标准差约 `1/√16 = 0.25`。
2. `p.88` 的 token：`segment emea operating margin 18 2 to 16 8 decline 140bp table four`。查询 9 个 token 中精确命中 `operating`、`margin`、`emea` 三个，各贡献 1.0；其余 6 个（what、was、the、2024、change、for）在 13 个随机 patch 上取最大值，每个期望约 0.41。估算：`3 × 1.0 + 6 × 0.41 ≈ 5.46`，实测 seed=1、2 下分别为 5.23、5.34，量级吻合。
3. **噪声加成**：不匹配的查询 token 也会贡献"N 个随机点积中的最大值"，N 越大期望越高（N=5 约 0.29，N=13 约 0.41）。查询里的停用词越多、页面 patch 越多，这部分噪声就越大，可能压过 1～2 个真实命中的差距。本节 EMEA 查询的 6 个"噪声 token"贡献了约 2.5 分，相当于 2.5 个精确命中。
   缓解（真实系统）：
   - 训练好的模型会把停用词、填充 token 的向量学到"不与内容 patch 相似"的位置，噪声远小于随机向量；
   - 查询侧过滤标点和停用词，或使用模型产生的查询扩展 token（ColBERT 的 `[MASK]` 扩展）；
   - 文档侧剪掉空白/背景 patch，本身就降低了这种噪声；
   - 评估时比较的是同一查询下不同页面的相对顺序，噪声只要比信号小就不影响排序。

### Q11 — 参考答案

1. FP16：`10,000 × 2,048 × 128 × 2 B = 5.24 GB`；50% 剪枝后约 `2.62 GB`；单向量 1024 维 FP32：`10,000 × 1,024 × 4 B = 40.96 MB`；倍数 `5.24 GB / 40.96 MB = 128`。
2. `20 × 2,048 × 128 × 10,000 ≈ 5.24 × 10^10`，即约 524 亿次乘加（每个查询）。CPU 上逐页 Python 循环完全不可行；即便 GPU 能扛住，扩展到千万页时也需要两阶段检索。
3. 工程手段（任选三条以上）：
   - **两阶段检索**：先用 ANN 对单个 patch 向量（或页面池化向量）召回候选页，再只对候选做精确 MaxSim；
   - **压缩**：patch 剪枝（DocPruner）、向量量化/二值化（每维 1 bit，用汉明距离近似）、PQ；
   - **专用引擎**：Vespa 的 multi-vector 字段与 MaxSim 排序表达式（讲义推荐）、Qdrant multi-vector；
   - **降维**：ColPali 本就把 patch 投影到 128 维；
   - **缓存与预计算**：热门文档常驻内存，冷数据放磁盘；
   - 讲义 Use It 示例检索耗时 320ms、合成 1.4s，可见答案 p95 的大头在 VLM 合成，也要优化（更小的 VLM、减少传入页数）。

### Q12 — 参考答案

1. 单页版本：
   ```python
   import numpy as np

   def max_sim_np(Q, P):
       Q = np.asarray(Q)          # (n_q, d)   查询 token 向量
       P = np.asarray(P)          # (n_p, d)   页面 patch 向量
       S = Q @ P.T                # (n_q, n_p) 两两点积
       return float(S.max(axis=1).sum())   # 每行取最大 -> (n_q,) -> 求和
   ```
2. 批量版本：把所有页面的 patch 填充到同样长度 `L`，用 mask 标记有效位置，填充位置的分数设为 `-inf`，使其不会被 `max` 选中：
   ```python
   def max_sim_batch(Q, pages):                         # pages: list[(n_p_i, d)]
       L = max(len(p) for p in pages); d = Q.shape[1]
       D = np.zeros((len(pages), L, d)); mask = np.zeros((len(pages), L), bool)
       for i, p in enumerate(pages):
           D[i, :len(p)] = p; mask[i, :len(p)] = True
       S = np.einsum("qd,bld->bql", Q, D)               # (B, n_q, L)
       S = np.where(mask[:, None, :], S, -np.inf)
       return S.max(axis=2).sum(axis=1)                 # (B,)
   ```
3. 验证：在同一进程内对 10 个页面分别用原函数与新函数计算，断言差值 < 1e-9。我们实际运行了单页版本和批量版本（剪枝后的 10 页，`np.allclose` 为真），两者都与 `max_sim_score` 一致。注意要在**同一个进程**里比较（或先修好 `hash()` 的问题），否则两次运行的向量本身就不同。

### Q13 — 参考回答要点

- **ColPali 式**：页面渲染为图像 → 视觉语言模型（ColPali 基于 PaliGemma，ColQwen 基于 Qwen-VL）输出每个 patch 的向量（多向量）→ 查询编码为 token 级向量 → MaxSim 打分 → top-k 页面交给 VLM 回答。
- **vs OCR-then-text**：后者先 OCR 成文本、切块、单向量或 BM25 检索；OCR 错误、版式丢失、图表无法表达是主要损失；优势是存储小、成熟、可做精确关键词匹配，公式/密集表格可能更准（讲义因此保留 OCR fallback 和 hybrid 练习）。
- **vs CLIP 单向量**：CLIP 一张图一个向量，擅长"这张图大概是什么"，不擅长"页面上某个小数字/某行表格"；且 CLIP 并非为文档检索训练。
- 加分点：说出 ViDoRe 基准、讲义里的 nDCG@5 + 内容类型矩阵评估思路；指出 vision-first 的代价是存储与延迟。

### Q14 — 参考回答要点

- 公式：`s(q, d) = Σ_{i=1}^{n_q} max_{j=1}^{n_d} E_q(i) · E_d(j)`。
- **为什么叫 late**：查询和文档各自独立编码（文档可离线预计算），交互只发生在最后的打分阶段，而且只是点积 + 取最大，计算很轻。
- **三种范式**：
  - bi-encoder（无交互）：各自池化成一个向量，最快、存储最小，细粒度匹配最弱；
  - late interaction：保留 token/patch 级向量，效果接近 cross-encoder，文档仍可预计算；代价是存储 ×（patch 数）与 MaxSim 计算；
  - cross-encoder（early interaction）：查询与文档拼接一起过 Transformer，最准，但每个候选都要一次前向，只能用于重排。
- 常见组合：bi-encoder / ANN 召回 → late interaction 精排 → cross-encoder 或 VLM 最终判断。

### Q15 — 参考回答要点

- **存储**：1000 万页 × 2048 × 128 × FP16 ≈ 5.2 TB（按 Q11 线性放大）；必须做剪枝 + 量化（二值化可再压缩 16 倍），冷热分层存储。
- **延迟**：两阶段检索（ANN 召回 → MaxSim 精排）；分片并行；GPU 上批量 MaxSim；按租户/文档集合预过滤（metadata filter）缩小候选。
- **剪枝验证**：
  - 在 ViDoRe v3 和自有标注集上，分别测 0%/50%/75%/90% 剪枝的 nDCG@5，画出"压缩率—精度"曲线，找到悬崖点（讲义练习 2）；
  - 按内容类型分别看（表格、图表、手写可能对剪枝更敏感）；
  - 多次实验、报告置信区间，不能只看一两个查询（本节代码只看一次 overlap 就是反例）；
  - 记录剪枝参数，skill 文件的 hard reject："Storage numbers reported without documenting DocPruner settings."
- 加分点：证据区域需要 patch 的位置信息，剪枝时要保留被保留 patch 的坐标，否则无法渲染 bbox（另一条 hard reject）。

### Q16 — 参考回答要点

- **摄取**：PyMuPDF 以 180 DPI 渲染每页（讲义）；记录 `{doc_id, page_num, image_path}`、年份、报告类型等元数据；对扫描件做方向校正。
- **索引**：ColQwen 多向量 + 剪枝，存 Vespa/Qdrant；对表格/公式密集页额外跑 OCR，建 BM25 文本索引；两路结果 RRF 融合（讲义练习 3 的 hybrid）。
- **问答**：VLM 读查询 + top-5 页面图像（+ OCR 文本），提示要求"只用提供的页面回答，按 (doc_id, page) 引用并指明区域（表格/图/段落）"；Qwen3-VL 可输出 bbox，在查看器中叠加高亮。
- **可追溯**：后处理校验每个引用的页码确实在检索结果中，bbox 落在页面范围内；无引用的论断丢弃或重问。
- **合规**：skill 文件要求敏感文档有脱敏策略（"ColQwen embeddings leak content"）、审计日志。
- **评估**：
  - 检索：nDCG@5，按内容类型（正文/表格/图表/手写）分格，对比 OCR-then-text 基线（必须在同一语料上跑两套管道）；
  - 答案：100 道人工标注的多页问题准确率（讲义要求）、数值类答案精确匹配；
  - 证据：evidence-region grounding（引用区域包含答案的比例）；
  - 系统：检索 p95、答案 p95 < 2s。

### Q17 — 参考回答要点

- **成本与延迟**：200 页图像按每页上千视觉 token 计，单次请求就是几十万 token，费用和延迟都远超"检索 5 页再回答"；讲义的目标是 2s 内回答。
- **规模**：讲义的语料是 1 万页，实际企业是百万页级，根本塞不下。
- **准确率**：页面越多，模型越容易被无关页面干扰、遗漏关键表格；检索把最相关的几页放到前面，信噪比更高。
- **可追溯**：检索天然给出候选页码，便于引用与证据区域高亮；整本塞入时模型给出的页码更难核验。
- **何时可以整本塞**：单个短文档、需要全局总结（"这份报告的主要风险有哪些"）时，长上下文 VLM 可以直接读；检索与长上下文是互补关系。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 19 OCR 和文档理解](../../../04-computer-vision/19-ocr-document-understanding/docs/zh.md)：OCR-then-text 基线的原理与局限。
- [阶段 12 · 01 Vision Transformers 与 Patch-Token 基本单元](../../../12-multimodal-ai/01-vision-transformer-patch-tokens/docs/zh.md)：页面图像如何被切成 patch token。
- [阶段 12 · 22 文档与图解理解](../../../12-multimodal-ai/22-document-diagram-understanding/docs/zh.md)：VLM 读表格、图表、版式的能力。
- [阶段 12 · 23 ColPali 与视觉原生文档 RAG](../../../12-multimodal-ai/23-colpali-vision-native-rag/docs/zh.md)：本节核心方法的专门讲解。
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：hybrid、RRF、rerank 的通用做法。

### 本节被哪些后续内容用到
- [阶段 12 · 24 多模态 RAG 与跨模态检索](../../../12-multimodal-ai/24-multimodal-rag-cross-modal/docs/zh.md)：把视觉文档检索推广到图文混合场景。
- [阶段 19 · 08 面向受监管行业的生产级 RAG 聊天机器人](../../08-production-rag-chatbot/docs/zh.md)：可追溯引用与合规要求。
- [阶段 19 · 12 视频理解流程——场景、问答与搜索](../../12-video-understanding-pipeline/docs/zh.md)：同样的"视觉 embedding + 检索 + VLM 合成"思路用于视频帧。
- [阶段 19 · 63 多模态 Evaluation](../../63-multimodal-eval/docs/zh.md)、[阶段 19 · 68 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性](../../68-rag-eval-precision-recall/docs/zh.md)：nDCG@5 与内容类型矩阵的评估实现。

### 延伸关键词
`ColPali` · `ColQwen` · `ColBERT` · `late interaction` · `MaxSim` · `multi-vector index` · `Vespa` · `Qdrant multivector` · `DocPruner` · `binary quantization` · `PLAID` · `ViDoRe` · `M3DocVQA` · `evidence region / bbox grounding` · `Nougat` · `PyMuPDF`
