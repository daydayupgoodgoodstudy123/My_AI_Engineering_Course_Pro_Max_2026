# 测验 · 基于 Cross-Encoder 的 Reranker（Cross-Encoder Reranker）

> **阶段 19 · 综合项目 · 第 66 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义机翻质量很差（例如把 cross-encoder 译成"十字架"），有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Bi-encoder（双塔编码器） | query 和文档**各自独立**编码成向量，用 cosine 排序；文档向量可离线预计算，是唯一能在全库规模上检索的方式，但文档向量"看不到"query |
| 2 | Cross-encoder（交叉编码器） | 把 `[CLS] query [SEP] doc [SEP]` 拼成**一条序列**做全注意力，每个文档 token 都能看到每个 query token，输出**一个相关性标量** |
| 3 | 代价不对称 | bi-encoder：每文档离线编码一次 + 每 query 一次；cross-encoder：**每个 (query, doc) 对一次前向**，1,000 万文档就是每个 query 1,000 万次前向 |
| 4 | 两阶段 retrieve-then-rerank | 便宜的检索器取 top-N（讲义：50–200），cross-encoder 把 N 重排为 top-K；质量 = cross-encoder 的质量，**上限是检索器在 N 处的 recall** |
| 5 | N 的选择 | N 是唯一可调参数：太小会封顶 recall，太大白付延迟；讲义称 lift 通常在 20–50 处出现"拐点"；N 至少取 K 的 3 倍 |
| 6 | 输入打包与 segment（type）id | 本节 `tokenize_pair`：`[CLS]=2`、`[SEP]=1`、`[PAD]=0`；query 段（含 CLS 和第一个 SEP）type=0，文档段（含末尾 SEP）type=1，padding 也是 type=0 |
| 7 | 池化方式 | 讲义标准做法是取 CLS 位置接线性头；本节代码用**去掉 padding 的 mean-pooling**；讲义说二者差别很小 |
| 8 | 典型生产规格 | 讲义：约 22M 参数（`ms-marco-MiniLM-L-6-v2` 量级）是常见生产点，float32 约 88MB；更大的如 `bge-reranker-v2-m3`（568M）留给离线或 K 很小的首页重排 |
| 9 | 隐藏的失败模式 | cross-encoder 不对称（query 必须放前面）；N = K 时 top-K 集合不变；训练数据泄漏进评估；不 batch 时延迟乘以 N |
| 10 | 生产模式 | 把 bi-encoder、cross-encoder、N 一起"钉死"；按 (query, doc_id) 缓存重排结果；记录 rank-1 分数，低于阈值就提示"不确定" |

### 核心技能（能动手做到）

- [ ] 说清 bi-encoder 与 cross-encoder 在输入形状、计算量、能否离线预计算上的区别，并能估算两者每个 query 的前向次数
- [ ] 手写 `tokenize_pair`：给定 query、文档和 `max_len`，写出 `ids` 与 `type_ids`，并指出截断时会丢掉什么
- [ ] 用 PyTorch 写出一个单层 cross-encoder（embedding 三件套 → 多头注意力 → FFN → 池化 → 线性头），说清每一步张量形状
- [ ] 把两阶段 pipeline 跑通，并通过扫描 N 解释"recall 封顶"和"延迟随 N 线性增长"
- [ ] 识别"训练集与评估集重叠"导致的虚高结果，并设计严格分离的评估
- [ ] 能为线上 reranker 设计 N、batch、缓存、置信阈值和显存预算

---

## 二、基础自测（选择题）

**Q1.** 关于 bi-encoder 与 cross-encoder 的本质区别，正确的是：

- A. bi-encoder 把 query 和文档分别编码成向量再算相似度；cross-encoder 把二者拼成一条序列，在拼接处做全注意力后输出一个相关性分数
- B. bi-encoder 需要训练，cross-encoder 不需要训练
- C. bi-encoder 用 cosine，cross-encoder 用点积，除此之外结构相同
- D. cross-encoder 只能在 GPU 上运行，所以不能做第一阶段检索

**Q2.** 一个 1,000 万文档的语料库。如果**直接用 cross-encoder 当第一阶段检索器**，每个 query 需要多少次 cross-encoder 前向？

- A. 1 次（只编码 query）
- B. N 次（N 为重排池大小，如 100）
- C. 约 `log2(10^7) ≈ 23` 次（借助 ANN 索引）
- D. 10,000,000 次（每个 (query, doc) 对一次）

**Q3.** 执行本节代码 `tokenize_pair("alpha", "beta gamma", max_len=12)`，返回的 `type_ids` 是：

- A. `[0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0]`
- B. `[0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0]`
- C. `[0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1]`
- D. `[1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0]`

**Q4.** 在 retrieve-then-rerank 两阶段系统中，最终 top-K 的质量受什么约束？

- A. 只取决于 cross-encoder 的参数量，与第一阶段无关
- B. 只取决于第一阶段检索器的 precision@1
- C. 等于 cross-encoder 的排序质量，但**上限是第一阶段在 N 处的 recall**——正确文档没进 top-N，reranker 永远看不到
- D. 只要 N 足够大，质量就会随 N 单调无限提升

**Q5.** 讲义说"N 至少取 K 的 3 倍"。如果设置 N = K，会发生什么？

- A. cross-encoder 会报错，因为输入 batch 太小
- B. 系统退化为只用 cross-encoder 做全库检索
- C. 延迟会比 N = 3K 时更高
- D. top-K 的**集合**与第一阶段完全相同，reranker 只能在内部调换顺序；像 recall@K 这类集合型指标没有任何提升

**Q6.** 本节 `CrossEncoder.forward` 中的 `x = self.ln1(x + attn_out)`，属于哪种归一化位置？

- A. post-norm：先做残差相加，再 LayerNorm（与原始 Transformer、BERT 相同）
- B. pre-norm：先 LayerNorm 再进子层（与 GPT-2 相同）
- C. RMSNorm：只做缩放、不减均值
- D. 没有使用残差连接

**Q7.** 讲义提到一个约 22M 参数的 cross-encoder。用 float32 存储权重，大约需要多少显存/内存（不含激活）？

- A. 22MB
- B. 44MB
- C. 88MB
- D. 176MB

**Q8.** 训练好本节的模型后，用同一对 (query = "how do we abort a multipart upload"，doc = d1 文本) 分别按正常顺序 `tokenize_pair(q, d)` 和颠倒顺序 `tokenize_pair(d, q)` 打分，实测结果最接近：

- A. 两者完全相同，因为注意力是对称的
- B. 正常顺序约 0.978，颠倒顺序约 0.530——cross-encoder 不对称
- C. 颠倒顺序会抛出异常
- D. 两者互为相反数

---

## 三、动手 / 代码题

**Q9.** 运行 `python3 main.py`，第二个 query 的输出如下：

```text
query: centralized authorization check function
  retrieve top-N:
    1. d4  retriever_score=0.5159
    ...
  reranked top-K:
    1. d8  cross_score=1.1841
    2. d4  cross_score=0.9991
    3. d2  cross_score=0.8358
```

d8 是 "Cancelling jobs"（取消任务）文档，和"授权检查"毫无关系，却被 cross-encoder 排到第一，分数甚至超过 1。而 `TRAIN_TRIPLES` 里恰好有 `("centralized authorization check function", d4, 1.0)`。

1. 为什么 d4 的分数几乎正好是 0.9991？为什么 d8 会超过它？（提示：把 query 换成空字符串 `""` 再打分，d8 得 0.993，排第一。）
2. 训练 loss 从 0.5356 降到 0.0003，说明了什么？
3. 讲义在"Failure modes"里专门警告过一种问题，本节 demo 恰好踩中了。是哪一种？
4. 如果要让这个 demo 的结论可信，你会如何修改训练与评估数据？

**Q10.** 用训练好的模型扫描第一阶段的 N（`top_k=3`，三个 demo query 的 gold 分别为 d1、d4、d8）。实测 rerank 后的 top-1：

| N | abort 查询 | authorization 查询 | cancel 查询 | gold 是否在 top-N |
|---|-----------|--------------------|-------------|------------------|
| 1 | d1 | d4 | d3 | cancel 查询的 d8 不在 |
| 2 | d1 | d4 | d3 | cancel 查询的 d8 不在 |
| 3 | d1 | d4 | d8 | 全部在 |
| 5 | d1 | d4 | d8 | 全部在 |
| 8 | d1 | **d8** | d8 | 全部在 |

1. N = 1、2 时 cancel 查询为什么错？这体现了两阶段系统的哪条规律？
2. demo 默认 `top_n=8`，而语料正好 8 篇。此时第一阶段起了什么作用？
3. 为什么 N 从 5 增加到 8 反而让 authorization 查询变错？这和讲义"N 越大 lift 越饱和"的描述有什么不同？
4. 讲义表格里 N = 5/20/50/100 对应的 Recall@1（0.62/0.81/0.86/0.86）是实测数据吗？

**Q11.** 讲义练习 3：把 mean-pooling 换成 CLS 头。补全下面的子类，并说明 CLS 位置为什么"能代表整对"。

```python
class CLSCrossEncoder(CrossEncoder):
    def forward(self, input_ids, type_ids):
        # TODO: 与父类相同地得到 x，但用 CLS 位置的向量接 head
        ...
```

**Q12.** 手算本节默认 `CrossEncoder()`（`d_model=64, n_heads=4, ff_hidden=128, max_len=96, VOCAB_SIZE=8192`）的参数量：

1. 写出各组件参数量并求和（`nn.MultiheadAttention` 的 Q/K/V 合并成一个 `in_proj`，带 bias；输出投影也带 bias）。
2. token embedding 占多少比例？这对"小模型训练 60 步就把 loss 压到 0.0003"意味着什么？

---

## 四、面试高频题

**Q13.**（基础必考）bi-encoder 和 cross-encoder 有什么区别？为什么生产 RAG 普遍是"bi-encoder 召回 + cross-encoder 重排"，而不是只用其中一个？

**Q14.**（原理深挖）为什么 cross-encoder 比 bi-encoder 更准？它的文档表示为什么无法像 bi-encoder 那样离线预计算并缓存？

**Q15.**（工程实践）你负责一个 p95 延迟预算 300ms 的检索服务，要接入 cross-encoder 重排。如何确定 N？还有哪些手段控制延迟和成本？

**Q16.**（场景设计）用户问了一个知识库里根本没有答案的问题，但检索 + 重排仍然返回了 top-K，LLM 据此一本正经地编了答案。如何利用 reranker 设计一个"拒答"机制？要注意什么？

**Q17.**（追问型）本节用 MSE 回归 14 条手工标注训练 cross-encoder。真实的 cross-encoder 是怎么训练的？损失函数、负样本、评估切分各要注意什么？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："The model receives `[query] [SEP] [document]` as a single sequence, runs full attention across the join, and produces one relevance scalar."

- B 错：二者都需要训练（真实 cross-encoder 是在检索数据上微调的 encoder transformer）。
- C 错：区别不在相似度函数，而在**是否联合编码**；cross-encoder 根本不产生独立向量，也就谈不上 cosine。
- D 错：不能做第一阶段的原因是**每对一次前向**的计算量，而不是硬件限制。

### Q2 — 答案：D

cross-encoder 必须对每个 (query, doc) 对跑一次前向，讲义："For a 10-million-document corpus that is 10 million forward passes per query. Unrunnable in a request budget."

- A 是 bi-encoder 在查询时的代价（再加一次 ANN 搜索）。
- B 是两阶段架构中 cross-encoder 的代价，不是"直接当检索器"的代价。
- C 混淆了 ANN 索引：ANN 只能加速**向量**近邻搜索，cross-encoder 没有可索引的文档向量。

### Q3 — 答案：B

`ids = [CLS] + [alpha] + [SEP] + [beta, gamma] + [SEP] = [2, h, 1, h, h, 1]`，再补 6 个 PAD。`type_ids = [0] * (1 + 2) + [1] * (2 + 1)`：query 段长度是"query token 数 + 2"（CLS 和第一个 SEP 都算 query 段），文档段是"文档 token 数 + 1"（末尾 SEP）。padding 填 0。实测：

```text
([2, 1875, 1, 7837, 7561, 1, 0, 0, 0, 0, 0, 0], [0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0])
```

- A 把第一个 SEP 算进了文档段。
- C 把 padding 当成文档段（BERT 惯例里 padding 的 segment id 无关紧要，因为会被 mask，但本代码填 0）。
- D 把 CLS 标成了 1。

### Q4 — 答案：C

讲义："The total quality is the cross-encoder's quality, capped by the bi-encoder's recall at N." 以及 "The cross-encoder cannot raise recall above the bi-encoder's recall at N, so a low N caps quality, not just latency."

- A、B 忽略了第一阶段对候选集的限制。
- D 错：讲义明确说 lift 在 20–50 附近饱和（"Past the knee you are paying for nothing"），本节实测甚至出现 N 变大反而变差的情况（见 Q10）。

### Q5 — 答案：D

N = K 时，送进 reranker 的就是最终要返回的 K 个文档，集合不变。讲义："If you set N = K, the cross-encoder cannot reorder; it can only reweight. The lift looks zero." 严格地说它仍能在 K 个内部调换顺序（MRR、nDCG 可能变），但 recall@K、precision@K 这类只看集合的指标完全不变。

- A 错：batch 大小不影响能否运行。
- B 错：恰好相反，cross-encoder 只看到 K 个候选。
- C 错：N 越小前向次数越少，延迟更低。

### Q6 — 答案：A

`ln1(x + attn_out)` 是"先加残差、后归一化"的 post-norm，与原始 Transformer、BERT 一致（真实 cross-encoder 大多是 BERT 系 encoder 微调而来）。B 的 pre-norm 写法是 `x + attn(ln(x))`；C 的 RMSNorm 在 PyTorch 中是 `nn.RMSNorm`，这里用的是 `nn.LayerNorm`；D 错，`x + attn_out`、`x + self.ff(x)` 都是残差。

### Q7 — 答案：C

`22,000,000 × 4 字节 = 88,000,000 字节 ≈ 88MB`。讲义："A 22M-parameter cross-encoder is 88MB at float32. Plan the model server's memory before promising sub-100ms p95." B（44MB）是 FP16/BF16 的大小；A 是把参数个数当字节数；D 是把 float32 当成 8 字节。

### Q8 — 答案：B

实测（固定种子、训练 60 轮后）：正常顺序 0.978，颠倒顺序 0.530。原因：位置 embedding 和 type embedding 把"谁在前、谁是 segment 0"编码进了输入，模型也只在"query 在前"的数据上训练过。讲义："`rerank(q, d)` and `rerank(d, q)` are different scores. Always feed the query first."

- A 错：自注意力本身对 token 置换是等变的，但加了位置/segment embedding 后整体就不对称了。
- C 错：只是两段文本，照样能打分。
- D 无任何依据。

### Q9 — 参考答案

1. **d4 ≈ 0.9991**：这一对就在训练集里，标签是 1.0，模型把它**背下来了**。**d8 = 1.18**：d8 在训练集里是 "how do we cancel a job" 的正例（标签 1.0），模型学到的主要是"d8 这段文本 → 高分"这种**文档先验**，而不是"query 与文档是否匹配"。证据：query 为空串时，d8 仍以 0.993 排第一。MSE 回归头没有 sigmoid 约束，所以对没见过的组合可以输出 >1 的值。
2. 14 条样本、564,097 个参数、全批量 Adam 60 步，loss 0.0003 只说明**训练集被拟合（记忆）**了，不说明泛化。实测改写 query（如 "stop an upload that failed"）时，排第一的是 d6（rank fusion 文档），完全错误。
3. 讲义的 "Training data leaks into the eval"："If the hand-labeled training pairs include the eval queries, the rerank looks magical." demo 的 3 个 query **全部**是 `TRAIN_TRIPLES` 里的原句。即便如此，3 个里仍有 1 个排错——泄漏都救不回来，说明模型几乎只学到了文档先验。
4. 改法：
   - 训练与评估 query 严格分离（不同的 query、最好不同的表述方式），评估集里加入改写/同义表达；
   - 每个 query 配**多个困难负例**（同主题但不回答问题的文档），让模型必须看 query 才能区分；
   - 报告排序指标（MRR、nDCG@K）而不是 loss；
   - 真实场景应从预训练 encoder（如 MiniLM/BERT 系 checkpoint）微调，而不是随机初始化的单层模型。

### Q10 — 参考答案

1. cancel 查询的 gold d8 在 bi-encoder 中排第 3（分数 0.2586，排在 d3、d4 之后），N ≤ 2 时 d8 根本没有进入候选池，reranker 再强也选不到它。这就是讲义的"quality capped by the bi-encoder's recall at N"。
2. N = 8 等于全库，第一阶段**没有过滤任何文档**，rerank 的结果与 bi-encoder 完全无关——demo 实际上是在"用 cross-encoder 对全库打分"，只是全库只有 8 篇才跑得动。讲义说"picking the answer that the bi-encoder ranked second or third"，但本 demo 中 bi-encoder 的作用只是排序展示。
3. N 增大引入了更多候选；本节 reranker 对 d8 有很强的文档先验（Q9），d8 一旦进池就会"抢"第一。真实曲线里 N 过大一般是 lift 饱和、白付延迟；本节 reranker 质量差，**第一阶段反而起到了"过滤噪声"的作用**。这提醒我们：N 的选择要用评估曲线来定，而且要配合 reranker 的实际质量；reranker 不够强时，大 N 甚至有害。
4. 不是。讲义原文："The numbers above are illustrative of the shape, not measurements from this fixture." 只有"曲线形状"是讲义的观点。

### Q11 — 参考答案

```python
class CLSCrossEncoder(CrossEncoder):
    def forward(self, input_ids, type_ids):
        batch, seq = input_ids.shape
        pos = torch.arange(seq, device=input_ids.device).unsqueeze(0).expand(batch, seq)
        x = self.token_emb(input_ids) + self.type_emb(type_ids) + self.pos_emb(pos)
        mask = (input_ids == PAD_ID)
        attn_out, _ = self.attn(x, x, x, key_padding_mask=mask)
        x = self.ln1(x + attn_out)
        x = self.ln2(x + self.ff(x))
        return self.head(x[:, 0]).squeeze(-1)      # (B, 64) -> (B,)
```

- `tokenize_pair` 保证位置 0 永远是 `CLS_ID`，所以 `x[:, 0]` 就是 CLS 的输出向量。CLS 本身没有语义，但它通过注意力"读"了整条序列（query + 文档），经过训练会成为整对的汇总表示——这是 BERT 做句对分类的标准做法。
- 实测（同种子、60 轮）：CLS 版 loss `0.2090 → 0.00259`，mean-pooling 版 `0.5356 → 0.00029`。都能拟合训练集；本节只有**一层**注意力，CLS 只经过一次信息汇聚，mean-pooling 直接平均了所有位置，在浅模型上收敛更快一些。在多层预训练模型上二者差别通常很小（讲义："the difference is small"）。
- 注意：用 CLS 头时 padding 掩码依然必要——它保证 CLS 不去注意 PAD 位置。

### Q12 — 参考答案

| 组件 | 计算 | 参数量 |
|------|------|-------|
| `token_emb` | 8192 × 64 | 524,288 |
| `type_emb` | 2 × 64 | 128 |
| `pos_emb` | 96 × 64 | 6,144 |
| `attn.in_proj`（Q/K/V 合并） | 3 × 64 × 64 + 3 × 64 | 12,480 |
| `attn.out_proj` | 64 × 64 + 64 | 4,160 |
| `ln1`、`ln2` | 2 × (64 + 64) | 256 |
| `ff` 两层 | 64 × 128 + 128 + 128 × 64 + 64 | 16,576 |
| `head` | 64 + 1 | 65 |
| **合计** | | **564,097** |

（已用 `sum(p.numel() for p in model.parameters())` 验证。）

token embedding 占 `524,288 / 564,097 ≈ 92.9%`。"模型能力"几乎全在 embedding 查表上，而训练数据里只出现了几十个不同的词：模型很容易用"某些词的 embedding → 高分"来拟合 14 个标签，也就是 Q9 中的文档先验/记忆现象。真正决定 query–文档交互能力的注意力和 FFN 只有约 3.3 万参数，且只有一层。

### Q13 — 参考回答要点

- **bi-encoder**：query、文档分别编码；文档向量离线算好放进向量索引（ANN），查询时只编码一次 query → 毫秒级在百万/千万级语料上检索。缺点：文档要被压缩成一个与 query 无关的向量，同主题但不回答问题的文档难以区分（讲义："Two documents that have the same overall topic can have nearly identical embeddings"）。
- **cross-encoder**：`[CLS] q [SEP] d [SEP]` 联合编码，每个 token 互相注意，精度高；但每对一次前向，无法预计算，全库不可行。
- **为什么组合**：bi-encoder 负责高 recall 的粗排（N 取 50–200），cross-encoder 只在 N 个候选上精排（K 个），把昂贵的计算集中在"最需要精度的地方"；总延迟可控，质量接近 cross-encoder（上限是 recall@N）。
- 加分点：还可以在召回侧做 BM25 + 稠密的 hybrid（第 65 节）提高 recall@N；提到 late-interaction（如 ColBERT 一类按 token 向量交互的模型）是二者之间的折中。

### Q14 — 参考回答要点

- **更准的原因**：注意力在 query 与文档之间直接建模 token 级交互（"Every token of the document can attend to every token of the query"），能识别否定、限定条件、"同主题但没回答"等细节；bi-encoder 只能比较两个固定向量，交互只发生在最后一次点积。
- **无法缓存**：文档的每一层隐藏状态都依赖 query（注意力里 K/V 来自同一条拼接序列），换一个 query 就要重算，所以不存在与 query 无关的"文档表示"。能缓存的只有最终分数，键为 (query, doc_id)（讲义的生产建议）。
- **代价**：计算量 ∝ N × (Lq + Ld)² 级别的注意力（序列越长越贵），讲义："The cost is throughput."
- 常见误区：以为 cross-encoder"更大所以更准"——关键是联合编码，而不是参数量。

### Q15 — 参考回答要点

- **用评估曲线定 N**：在独立的评估集上扫 N（如 10/20/50/100/200），画 recall@N（第一阶段）和 rerank 后的 MRR/nDCG@K，找拐点；同时测每个 N 的 p95 延迟，选"拐点附近且满足预算"的 N（讲义："Pick N from the eval curve plus the latency budget"）。
- **控制延迟**：N 个候选**一次 batch 前向**（讲义："Skip batching and the latency multiplies by N"）；截断文档长度（max_len）；用小模型（~22M 级）、FP16/INT8 推理、GPU 或 ONNX 等推理优化；预热（本节实测第一次 rerank 4.81ms，后续约 2.5ms）。
- **控制成本**：按 (query, doc_id) 缓存分数；对 rank-1 已经非常确定的 query 可以跳过重排；离线大模型重排只用于 K 很小的首页。
- **可维护性**：把 bi-encoder、cross-encoder、N 一起版本化（讲义："Changing any one invalidates the eval"）。
- 显存：22M float32 = 88MB，还要加上 batch 激活；多副本部署时要算总内存。

### Q16 — 参考回答要点

- **思路**：讲义建议记录 rank-1 cross-encoder 分数，"A query whose top-1 score is below a corpus-specific threshold is an out-of-domain hit; surface it to the LLM as 'I am not confident'."
- **实现**：在独立验证集上收集 in-domain 与 out-of-domain query 的 top-1 分数分布，按目标误拒率/误答率选阈值；低于阈值时让生成器拒答或要求澄清，或在 prompt 中明确告诉 LLM"检索结果可信度低"。
- **注意事项**：
  - 分数要**可比**：MSE 回归分数（本节）没有校准，可能 >1 或 <0；生产常用 sigmoid/BCE 训练的 logit，再做温度缩放等校准；
  - 阈值与语料、模型版本绑定，换模型或语料要重标；
  - 本节模型的 d8 文档先验说明：一个记忆型 reranker 会对任意 query 给某些文档高分，拒答阈值会失效——必须用 out-of-domain 样本验证；
  - 可以与生成后的忠实度检查（第 68 节）组合，形成两道防线。

### Q17 — 参考回答要点

- **初始化**：从预训练 encoder（BERT/MiniLM 系）开始微调，而不是随机初始化；讲义："A real cross-encoder is a finetuned encoder transformer."
- **损失**：
  - pointwise：二分类 BCE（相关/不相关）最常见，输出 logit 可解释为相关概率；本节用 MSE 回归分级标签，简单但输出无界；
  - pairwise：如 margin ranking loss，要求正例分数高于负例；
  - listwise：对一个 query 的候选列表做 softmax 交叉熵，直接优化排序。
- **负样本**：随机负例太容易，必须加入**困难负例**（第一阶段检索出来但不相关的文档），否则模型学不会细粒度区分；同时避免把未标注但实际相关的文档当负例（false negative）。
- **评估切分**：训练/验证/测试 query 严格不重叠，最好按主题或时间切分，防止讲义说的"rerank looks magical"。指标用 MRR、nDCG@K、recall@K 而不是训练 loss。
- 本节反例：14 条样本、评估 query 等于训练 query、每个 query 只有 1–2 个负例 → 记住文档身份，换个说法就失效（Q9）。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)：retrieve-then-generate 的基本框架，reranker 是其中的精排环节。
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：重排序在 RAG 中的位置与常见方案。
- [阶段 11 · 04 Embeddings 与向量表示](../../../11-llm-engineering/04-embeddings/docs/zh.md)：bi-encoder 的向量检索基础。
- [阶段 07 · 06 BERT——掩码语言建模](../../../07-transformers-deep-dive/06-bert-masked-language-modeling/docs/zh.md)：`[CLS]/[SEP]`、segment embedding、post-norm encoder 的来源。
- [阶段 07 · 03 多头 Attention](../../../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md)：理解 `nn.MultiheadAttention` 与 padding mask。
- [阶段 19 · 65 结合 BM25 与稠密 Embeddings 的 Hybrid Retrieval](../../65-hybrid-retrieval-bm25-dense/docs/zh.md)：为本节提供第一阶段候选。

### 本节被哪些后续内容用到
- [阶段 19 · 67 查询改写：HyDE、多查询与查询分解](../../67-query-rewriting-hyde/docs/zh.md)：改写后的检索结果在生产中再交给 reranker。
- [阶段 19 · 68 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性](../../68-rag-eval-precision-recall/docs/zh.md)：用 MRR/nDCG 量化 rerank 带来的提升。
- [阶段 19 · 69 端到端 RAG 系统](../../69-end-to-end-rag-system/docs/zh.md)：本节 cross-encoder 的压缩版被接在 hybrid 检索之后。
- [阶段 19 · 02 代码库 RAG——跨仓库 Semantic Search](../../02-rag-over-codebase/docs/zh.md)、[阶段 19 · 08 面向受监管行业的生产级 RAG 聊天机器人](../../08-production-rag-chatbot/docs/zh.md)：真实项目中的检索 + 重排。
- [阶段 17 · 14 Prompt 缓存与语义缓存的经济性](../../../17-infrastructure-and-production/14-prompt-semantic-caching/docs/zh.md)：按 (query, doc_id) 缓存重排结果的成本收益。

### 延伸关键词
`bi-encoder` · `cross-encoder` · `retrieve-then-rerank` · `rerank budget N` · `recall@N` · `[CLS]/[SEP]` · `segment / token type ids` · `mean-pooling vs CLS pooling` · `hard negatives` · `pointwise / pairwise / listwise loss` · `score calibration` · `ms-marco MiniLM` · `bge-reranker` · `late interaction`
