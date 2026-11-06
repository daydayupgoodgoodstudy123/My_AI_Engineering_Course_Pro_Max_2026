# 测验 · 多模态 RAG 与跨模态检索（Multimodal RAG and Cross-Modal Retrieval）

> **阶段 12 · 多模态 AI · 第 24 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 多模态 RAG 比单模态多出的四件事 | 多个检索头（各模态需要兼容的 embedding 空间）、跨模态结果融合、跨模态引用的 grounded generation、覆盖跨模态信号的评估 |
| 2 | 跨模态检索三种模式 | 共享 embedding 空间（CLIP/SigLIP 2 管图文、CLAP 管文音）；各模态编码器 + 翻译模块；用 VLM 隐状态作检索表示（质量最高、最贵） |
| 3 | Score fusion | 每个模态各自检索打分，**先在模态内归一化**，再加权求和；最便宜、常常够用；生产默认加一点向查询主导模态倾斜的偏置 |
| 4 | Attention / MoE fusion | attention 融合：拼接所有检索结果，用小网络学权重，需要训练；MoE 融合：门控网络按查询路由到模态专家，同样需要监督数据 |
| 5 | Grounded generation | 每个结论标注来源：文本 `[1]`、图像 `[img 3]` + 简短说明、音频 `[audio 2 at 0:34]`；用带来源标签的数据训练生成器 |
| 6 | 2025 三篇综述 | Abootorabi 等（arXiv:2502.08826，覆盖最广的分类法）、Mei 等（arXiv:2504.08748，子任务基准与失败模式）、Zhao 等（arXiv:2503.18016，偏视觉，ColPali 系列） |
| 7 | MuRAG（2022） | 第一个多模态 RAG：从多模态知识库检索图像 + 文本再生成；REACT、VisRAG、M3DocRAG 都在其基础上发展 |
| 8 | 查询分解 | "安静 / 素食早午餐 / 自然光" 分别落到音频、文本、图像三路检索，再融合成每家餐厅的综合分 |
| 9 | Agentic multi-hop | 首轮置信度低时由 LLM 改写查询再检索；能处理单轮无法完成的查询，但每一轮都有延迟成本 |
| 10 | 评估仍不成熟 | 常用代理指标：各模态 Recall@k、融合后 top-k 准确率、人工端到端满意度、任务指标（预订、购买）；没有覆盖所有模态的标准基准 |

### 核心技能（能动手做到）

- [ ] 手算本节代码三路检索器对任一餐厅的分数，以及给定权重下的融合分
- [ ] 指出 `text_retrieve` 子串计数、停用词、标点带来的错误匹配，并改写成按词匹配
- [ ] 实现模态内 min-max 归一化与 RRF（Reciprocal Rank Fusion），比较它们与原始加权和的排序差异
- [ ] 识别"只调权重就让置信度上升"的伪 agentic 循环，改写为每轮重跑检索、用 top-1/top-2 差距作置信度、限制轮数并如实标记低置信
- [ ] 为一个新产品（医疗分诊、电商、现场维修）设计各模态的知识库、检索器、融合方式和引用格式
- [ ] 为多模态 RAG 写评估规格：各模态召回、融合准确率、引用正确率、端到端任务指标

---

## 二、基础自测（选择题）

**Q1.** 按讲义，"文本查询检索音频"最合适的现成选择是：

- A. CLIP
- B. ColPali
- C. CLAP
- D. Nougat

**Q2.** 讲义推荐的生产默认融合方式是：

- A. Score fusion：各模态分数先在模态内归一化再加权求和，并略向查询的主导模态倾斜；在 A/B 证明有明显收益后再升级到 MoE
- B. MoE fusion：上线第一天就训练门控网络
- C. Attention fusion：不需要训练，直接拼接即可
- D. 只取得分最高的那个模态的结果，其它模态丢弃

**Q3.** 本节代码中，查询为 `"find me a quiet vegan brunch with natural light"`，`r1`（Sunday Plant Bistro）的三路分数为：文本 `3/7 ≈ 0.4286`、图像 `1.0`、音频 `1 − 38/80 = 0.525`。第一轮权重为 `[0.3, 0.4, 0.3]`，`r1` 的融合分是：

- A. 0.733
- B. 0.651
- C. 0.600
- D. 0.686

**Q4.** 运行结果显示第二轮"置信度"从 0.69 升到 0.73。真正的原因是：

- A. 改写后的查询加入了 "bright windows"，图像检索器因此给 r1 更高的分
- B. 三路检索的分数完全没变（文本检索没有用新查询重跑，图像和音频检索器也不认识新增的词），只是融合权重从 `[0.3, 0.4, 0.3]` 改成 `[0.3, 0.5, 0.2]`，把更多权重给了 r1 恰好拿满分的图像通道
- C. 音频检索器识别了 "low noise"，把 r1 的音频分提高了
- D. 第二轮检索引入了新的餐厅

**Q5.** `r3`（Vine & Leaf，评论 "vegan lunch, dim lighting"）的文本分是 `2/7`，与 r2、r4 相同。它多拿的那 1 分来自：

- A. "brunch"，因为 "lunch" 是它的子串
- B. "natural"，因为评论里有 "dim"
- C. "light"：`text.count("light")` 是**子串计数**，命中了 "lighting"——用户要自然光，昏暗灯光反而加了分
- D. "with"，因为它是停用词

**Q6.** 讲义所述 2025 年三篇综述共同归纳的多模态 RAG 子问题是：

- A. 分词、预训练、对齐、部署
- B. OCR、版面分析、表格识别、规则抽取
- C. 量化、蒸馏、剪枝、缓存
- D. 跨模态检索、检索融合、生成 grounding、多模态评估

**Q7.** 把查询改成 `"vegan brunch with natural light"`（不含 "quiet"/"calm"），音频检索器对所有餐厅都返回 0.5。对融合结果的影响是：

- A. 给每家餐厅都加上相同的 `0.3 × 0.5 = 0.15`（第一轮权重下）：排序不变，但融合分的绝对值——也就是代码用作"置信度"的那个数——被无意义地抬高
- B. 音频通道被自动禁用，权重重新分配给其它通道
- C. 所有餐厅的融合分都变成 0.5
- D. 程序抛出 `KeyError`

**Q8.** 讲义练习 2 问："score fusion 是简单加权和，它有什么 MoE fusion 能避免的失败模式？"最佳回答是：

- A. 加权和的计算量太大
- B. 权重对所有查询固定：一个"看图"的问题和一个"听声音"的问题用同一组权重，无关模态的噪声照样计入；MoE 由门控网络按查询决定信任哪个模态——但它需要监督数据训练（skill 文件把"没有训练数据就提议 MoE"列为硬性拒绝）
- C. 加权和无法处理三种以上模态
- D. MoE 不需要任何训练数据就能自动学会路由

---

## 三、动手 / 代码题

**Q9.** 阅读 `text_retrieve`：

```python
def text_retrieve(query: str) -> dict[str, float]:
    """Crude keyword matching for the query against review text."""
    keywords = [w.lower() for w in query.split() if len(w) > 2]
    scores = {}
    for r in CORPUS:
        text = r.review_text.lower()
        s = sum(text.count(k) for k in keywords)
        scores[r.id] = s / len(keywords) if keywords else 0
    return scores
```

1. 对示例查询，`keywords` 是什么？指出其中会稀释分数的词。
2. 列出这个函数至少三个问题（匹配方式、停用词、标点）。
3. 改写为"按词匹配 + 停用词表"的版本 `text_retrieve2`，写出对示例查询五家餐厅的新分数。

**Q10.** 讲义说 score fusion 要 "Normalize scores within-modality then sum"，但代码的 `fuse` 直接加权求和。

1. 说明三路原始分数的取值范围有何不同，以及这会导致什么。
2. 实现模态内 min-max 归一化后再按 `[0.3, 0.4, 0.3]` 融合，写出五家餐厅的排序与分数。
3. 再实现 RRF（`score = Σ 1/(60 + rank)`），写出排序，并指出 RRF 在这个数据上的问题。

**Q11.** 阅读 `agentic_loop`（节选）：

```python
    confidence = top[0][1] if top else 0
    trace = [f"round 1: top={top[0]}  confidence={confidence:.2f}"]
    if confidence < confidence_floor:
        trace.append("  confidence low; reformulating query")
        query2 = query + " bright windows low noise"
        i2 = image_retrieve(query2)
        a2 = audio_retrieve(query2)
        fused = fuse([t, i2, a2], [0.3, 0.5, 0.2])
```

1. 指出这个"agentic"循环的至少四个问题。
2. 改写为 `agentic_loop_v2`：每一轮三路检索都用新查询重跑；分数先归一化；置信度用 top-1 与 top-2 的差距（margin）；最多 3 轮；用尽轮数时如实返回"低置信"标记。写出两个示例查询的运行轨迹并解释。

---

## 四、面试高频题

**Q12.**（基础必考）多模态 RAG 相比文本 RAG 多了哪些问题？请按"检索—融合—生成—评估"四个环节说明，并给出跨模态检索的三种实现模式。

**Q13.**（原理深挖）比较 score fusion、attention fusion、MoE fusion 和 RRF：各自需要什么、优缺点是什么？为什么"模态内归一化"是 score fusion 的前提？融合权重能否跨领域迁移？

**Q14.**（场景设计）设计一个医疗分诊多模态 RAG：用户上传伤口照片 + 文字描述症状。各模态从什么知识库检索？如何融合、如何引用、有哪些安全要求？（讲义练习 1）

**Q15.**（工程实践）为"旅行规划"多模态 RAG（安静 / 素食早午餐 / 自然光）写一份评估规格：图像召回、音频召回、综合正确性分别用什么指标？数据怎么标注？（讲义练习 4）

**Q16.**（追问型）Agentic multi-hop RAG 每多一轮就多一次往返延迟。什么样的查询难度值得这个代价？置信度应该怎么定义？如何防止查询改写跑偏？（讲义练习 5）

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："CLIP / SigLIP 2 for text+image; CLAP for text+audio; VLM-hidden-states for cross-modal at frontier quality." CLAP 把文本和音频映射到共享空间，余弦相似度可以直接跨模态比较。A 是图文；B 是文档页面检索（第 23 节）；D 是论文 OCR-free 解析（第 22 节）。

### Q2 — 答案：A

讲义："Normalize scores within-modality then sum. Simple, often works." 以及 "Production default: score fusion with a slight bias toward the query's dominant modality. Upgrade to MoE if A/B shows clear wins on your domain." B 违背"先简单后复杂"的建议，且 MoE 需要监督数据；C 错，讲义明确 attention fusion "Needs training"；D 会丢掉其它模态的证据，违背多模态 RAG 的初衷。

### Q3 — 答案：D

`0.3 × 0.4286 + 0.4 × 1.0 + 0.3 × 0.525 = 0.1286 + 0.4 + 0.1575 = 0.6861`，与运行输出 `round 1: top=('r1', 0.6860714285714286)` 一致。A 是第二轮权重 `[0.3, 0.5, 0.2]` 下的值（0.7336）；B、C 是错误计算。

### Q4 — 答案：B

已逐项验证：图像检索器只认 "light/sun/airy/spacious/minimal"，新增的 "bright windows" 不会改变 `tag_hints`（仍只有 `natural_light`）；音频检索器只认 "quiet/calm"，"low noise" 没有作用，返回值与第一轮完全相同；文本检索器根本没有用 `query2` 重跑（代码复用了第一轮的 `t`——若真重跑，"windows" 能命中 r1，但关键词变多反而让 r1 的文本分从 0.4286 降到 0.3636）。所以分数上升 100% 来自权重调整：`0.3 × 0.4286 + 0.5 × 1.0 + 0.2 × 0.525 = 0.7336`。这是"把阈值调到能通过"而不是"找到了更多证据"。A、C 与实测不符；D 错，语料始终是 5 家。

### Q5 — 答案：C

关键词 `light` 在 `"vegan lunch, dim lighting"` 里以子串形式出现一次，`vegan` 一次，共 2 次，`2/7 ≈ 0.2857`。用户要"自然光"，评论说"灯光昏暗"，语义相反却得分——这是子串匹配的典型误报。A 错，"brunch" 不是 "lunch" 的子串（反过来 "lunch" 才是 "brunch" 的子串）；B、D 与事实不符（"with" 确实是关键词，但 r3 的评论中没有 "with"）。

### Q6 — 答案：D

讲义："Three 2025 surveys ... codified the sub-problems: cross-modal retrieval, retrieval fusion, generation grounding, multimodal evaluation." 也对应 "The Problem" 中的四项要求。B 是第 22 节的 OCR pipeline；A、C 与本节无关。

### Q7 — 答案：A

`audio_retrieve` 在查询不含 "quiet"/"calm" 时对所有餐厅返回常数 0.5。常数项不改变排序，但代码把**融合分的绝对值**当作置信度，这个常数让所有分数都"虚高" 0.15。实测该查询第一轮 top-1 为 0.67、第二轮 0.72，且 r1 与 r4 并列 0.72——因为去掉 "quiet" 后，r1 与 r4 唯一的区分信号（38 dB vs 42 dB）也消失了。正确做法是：没有音频需求时该通道权重应为 0（或由路由/MoE 决定），而不是填一个常数。B 是理想行为但代码没实现；C、D 与运行结果不符。

### Q8 — 答案：B

固定权重的加权和无法根据查询调整对各模态的信任度：一个纯视觉问题里，文本和音频通道的噪声依旧按固定比例计入。MoE 用门控网络按查询类型路由（讲义："a visual question weights images higher"）。但 skill 文件明确："Proposing MoE fusion without training data. MoE needs supervision to route correctly."，并且 "Claiming score-fusion weights transfer across domains. They do not." A 错，加权和是最便宜的；C 错，加权和对模态数没有限制；D 与 skill 文件相反。

### Q9 — 参考答案

1. `keywords = ['find', 'quiet', 'vegan', 'brunch', 'with', 'natural', 'light']`（`len(w) > 2` 过滤掉了 "me"、"a"）。"find"、"with" 是停用词，"natural" 在任何评论里都不出现——它们只会让分母变大，把所有餐厅的分数等比例压低。

2. 问题：
   - **子串计数**：`text.count("light")` 命中 "lighting"（Q5）；同理 "vegan" 会命中 "veganism"，"sun" 会命中 "sunday"。
   - **停用词**：长度 > 2 不等于有意义，"find"、"with" 进入分母。
   - **标点**：`query.split()` 不去标点，查询里若写 "light," 就匹配不到 "light"。
   - **重复计数**：同一个词出现多次会多次加分，长评论天然占优。
   - **没有语义**："lots of windows"（r1）与 "natural light" 显然相关，但关键词匹配看不出来——这正是讲义要用 CLIP/文本 embedding 的原因。
   - 分数 `s / len(keywords)` 只在本查询内可比。

3. 参考实现（已运行验证）：

```python
import re

STOP = {"find", "me", "a", "with", "the", "and"}

def toks(s):
    return re.findall(r"[a-z]+", s.lower())       # 只保留字母串，自动去标点

def text_retrieve2(query):
    kws = [w for w in toks(query) if w not in STOP]
    out = {}
    for r in CORPUS:
        words = set(toks(r.review_text))           # 按"词"匹配，不再按子串
        out[r.id] = sum(k in words for k in kws) / len(kws) if kws else 0.0
    return out
```

   示例查询的关键词变为 `quiet, vegan, brunch, natural, light`，分数：`r1 0.6`（quiet、vegan、brunch）、`r2 0.4`、`r3 0.2`（只有 vegan，"lighting" 不再误配）、`r4 0.4`、`r5 0.0`。r1 与第二名的差距从 `0.43 vs 0.29` 拉大到 `0.6 vs 0.4`。生产中应换成 BM25 或文本 embedding。

### Q10 — 参考答案

1. 原始取值范围：文本 `[0, 0.43]`（7 个关键词里最多命中 3 个），图像只有 `{0, 1}`，音频 `[0.1, 0.525]`。不归一化时，**取值范围最大的通道（图像）实际权重远大于名义权重**：图像的 0/1 跳变贡献 0.4，而文本的最大差距只贡献约 0.13。名义权重 `[0.3, 0.4, 0.3]` 并不代表各模态真实的影响力。

2. min-max 归一化（每个模态内 `(x − min)/(max − min)`）后融合（已运行验证）：

```python
def minmax(d):
    lo, hi = min(d.values()), max(d.values())
    return {k: (v - lo) / (hi - lo) if hi > lo else 0.0 for k, v in d.items()}

fused = fuse([minmax(t), minmax(i), minmax(a)], [0.3, 0.4, 0.3])
```

   结果：`r1 1.000 > r4 0.865 > r3 0.350 > r2 0.235 > r5 0.000`。归一化后音频的差异被放大（r1 的 38 dB 成为 1.0），r3 因为相对安静（55 dB）排在 r2（68 dB）前面。注意 min-max 对常数通道要特殊处理（`hi == lo` 时返回 0），否则除零——这恰好也解决了 Q7 的"常数 0.5 虚高"问题。

3. RRF（k = 60）：

```python
def rrf(lists, k=60):
    out = {}
    for d in lists:
        ranked = sorted(d.items(), key=lambda x: -x[1])
        for rank, (rid, _) in enumerate(ranked, 1):
            out[rid] = out.get(rid, 0) + 1 / (k + rank)
    return out
```

   结果：`r1 0.04918 > r4 0.04788 > r2 0.04763 > r3 0.04737 > r5 0.04615`。问题：RRF 只看名次不看分差，而这里有大量**并列**（图像通道 r2、r3、r5 都是 0；文本通道 r2、r3、r4 都是 2/7），`sorted` 的稳定性让并列项按语料顺序分配名次，r2 因此排在 r3 前面——这个顺序是由列表顺序决定的，并非由证据决定。RRF 的优点是不需要归一化、对异常分数鲁棒，适合候选很多、分数尺度难以对齐的场景；在少量候选、大量并列时应先处理并列（并列项取平均名次）。

### Q11 — 参考答案

1. 问题：
   - **只调权重不找证据**：第二轮唯一真正生效的改动是权重 `[0.3, 0.5, 0.2]`（Q4），置信度上升是"自我说服"。
   - **文本检索没有重跑**：复用了第一轮的 `t`。
   - **改写词检索器不认识**："bright windows low noise" 对图像和音频检索器都无效；真实系统中改写应由 LLM 根据检索器的能力生成，并验证改写后检索结果确实变化。
   - **置信度定义不当**：用融合分的绝对值，未归一化，受权重和常数通道影响（Q7）；更合理的是 top-1 与 top-2 的差距、或经过校准的分数。
   - **只有一轮重试、没有最终兜底**：第二轮仍低于阈值时也照样输出答案，没有"低置信"标记或澄清提问。
   - **鲁棒性**：`top` 为空时 `top[0]` 直接 `IndexError`（`if top else 0` 只保护了 confidence）；`confidence_floor` 默认 0.8，`main` 却传 0.7。

2. 参考实现（已运行验证）：

```python
def run_round(query, weights):
    scores = [minmax(f(query)) for f in (text_retrieve, image_retrieve, audio_retrieve)]
    return top_k(fuse(scores, weights), k=3)

def agentic_loop_v2(query, margin_floor=0.2, weights=(0.3, 0.4, 0.3),
                    expansions=("calm", "sun")):
    trace, top = [], []
    for rnd, q in enumerate([query] + [f"{query} {e}" for e in expansions], 1):
        top = run_round(q, list(weights))           # 每一轮三路检索都重跑
        if not top:
            return "\n".join(trace + ["no results"]), [], False
        margin = top[0][1] - top[1][1] if len(top) > 1 else top[0][1]
        trace.append(f"round {rnd}: '{q}' top={top[0][0]} margin={margin:.2f}")
        if margin >= margin_floor:
            return "\n".join(trace), top, True
    return "\n".join(trace), top, False             # 用尽轮数：如实标记低置信
```

   实际输出：

```text
round 1: 'find me a quiet vegan brunch with natural light' top=r1 margin=0.14
round 2: 'find me a quiet vegan brunch with natural light calm' top=r1 margin=0.14
round 3: 'find me a quiet vegan brunch with natural light sun' top=r1 margin=0.04
confident: False [('r1', 1.0), ('r4', 0.965), ('r3', 0.35)]

round 1: 'vegan brunch with natural light' top=r1 margin=0.00
round 2: 'vegan brunch with natural light calm' top=r1 margin=0.04
round 3: 'vegan brunch with natural light sun' top=r4 margin=0.10
confident: False [('r4', 0.7), ('r1', 0.6), ('r2', 0.2)]
```

   解释：r1 与 r4 都是"素食早午餐 + 自然光"，唯一差别是 38 dB vs 42 dB，**它们本来就难分高下**，诚实的循环不会"制造"置信度，而是返回低置信标记——此时产品应同时展示两家并说明差异，或反问用户"安静有多重要"。第二个查询的第 3 轮还暴露了**查询漂移**：追加的 "sun" 在文本通道命中 r4 的 "lots of sun"，top-1 从 r1 变成 r4，而用户从没说过要"阳光"。改写必须以原始意图为约束，并在 trace 中可审计。

### Q12 — 参考回答要点

- **检索**：每个模态需要在兼容空间里的 embedding。三种模式：共享空间（CLIP/SigLIP 2 图文、CLAP 文音）、各模态编码器 + 翻译模块、VLM 隐状态作表示（最灵活、最贵）。skill 文件：没有共享空间的跨模态 bi-encoder 打分"毫无意义"。
- **融合**：不同模态的结果要合成一个排序：score fusion（归一化 + 加权）、attention fusion、MoE fusion。
- **生成**：VLM 生成器同时看到文本段落、图片、音频片段（或其转写/描述），每个结论要标注来源：`[1]`、`[img 3]`、`[audio 2 at 0:34]`。
- **评估**：各模态 Recall@k、融合 top-k 准确率、人工端到端评分、业务指标；没有覆盖所有模态的标准基准。
- 加分点：说出 2025 年三篇综述及 MuRAG（2022）这一起点；指出查询分解（一个查询拆成多个模态子查询）是多模态 RAG 的关键一步。

### Q13 — 参考回答要点

| 方法 | 需要什么 | 优点 | 缺点 |
|------|---------|------|------|
| Score fusion | 各模态分数 + 归一化 + 权重 | 最简单、可解释、无需训练 | 权重固定、对所有查询一视同仁；尺度不齐时名义权重失真 |
| RRF | 只需各模态的排名 | 不需要归一化、对异常分数鲁棒 | 丢掉分差信息；并列多时排序由列表顺序决定（Q10） |
| Attention fusion | 带标注的训练数据 | 能学习条目之间的交互 | 需要训练、难解释 |
| MoE fusion | 带标注的训练数据 | 按查询路由，视觉问题信图像、声音问题信音频 | 需要监督；门控错了会整体失败 |

- **为什么要模态内归一化**：不同检索器分数的尺度和分布不同（余弦、BM25、0/1 标签、分贝换算），直接相加时取值范围最大的通道主导结果（Q10 中图像 0/1 跳变压过了文本和音频）。
- **权重能否迁移**：不能（skill 文件硬性拒绝）。不同领域的模态信息量不同：餐厅推荐中图像很重要，医疗分诊中文本症状可能更重要；必须在目标领域上用标注数据调权重或训练门控。
- 加分点：可以把"查询主导模态"的判断交给一个轻量分类器或 LLM，作为 score fusion 和 MoE 之间的折中。

### Q14 — 参考回答要点

- **查询模态**：伤口照片 + 文本症状（部位、时间、疼痛、过敏史等）。
- **知识库与检索器**：
  - 图像 → 带标注的临床图像库（伤口类型、严重程度），用医学领域微调的图文 embedding 或 VLM 表示检索相似病例；
  - 文本 → 临床指南、分诊规程、药品说明，用文本 embedding + BM25 混合检索；
  - 跨模态 → 用照片检索指南中的相关段落（图 → 文），需要共享空间。
- **融合**：分诊场景下"漏掉危险信号"的代价远高于误报，可以对"红旗症状"（大出血、感染征象）做规则优先，再用 score fusion 排序；权重在本领域标注数据上调。
- **引用**：每条建议标注指南条目 `[1]` 和相似病例图片 `[img 3]`，让医生/护士能核对。
- **安全要求**：明确不是诊断；低置信或高危时直接建议就医/急诊；人工复核；隐私（照片去标识化、合规存储）；记录检索证据与生成内容以便审计；对不同肤色、拍摄条件做公平性评估。
- 常见误区：直接用通用 CLIP 检索医学图像；只给结论不给来源。

### Q15 — 参考回答要点

- **标注数据**：构造查询集（含多种约束组合：只有素食、素食 + 安静、素食 + 安静 + 自然光……），对每个查询标注每家餐厅在各维度上是否满足（来自评论、照片人工判断、实测分贝），以及"整体合格"的餐厅集合。
- **分模态指标**：
  - 图像召回：对含"自然光/通透"等视觉约束的查询，计算图像检索器的 Recall@k、nDCG@k；
  - 音频召回：对含"安静"约束的查询，计算音频检索器的 Recall@k，或用"推荐餐厅的平均分贝"作连续指标；
  - 文本召回：菜单/评论约束的 Recall@k。
- **综合正确性**：融合后 top-k 中"满足全部约束"的比例（约束满足率）、Precision@k；引用正确率（每条结论的引用是否真的支持它）。
- **端到端**：人工满意度评分、线上点击/预订转化率。
- **切片分析**：按约束组合、查询长度、是否触发多轮分别统计，定位哪个模态拖后腿。
- 加分点：把 Q7 中"常数通道"、Q5 中"lighting 误配"这类问题设计成回归测试用例。

### Q16 — 参考回答要点

- **何时值得多轮**：
  - 首轮证据明显不足：top-1 与 top-2 难分（margin 小）、或关键约束在所有候选中都没有证据；
  - 需要链式信息：先检索图片发现菜单，再检索菜单文本（讲义的例子）；
  - 查询本身有歧义，需要细化（"小于 40 dB"）。
  - 简单、单约束、首轮 margin 已大的查询不应多跑。skill 文件：延迟预算 < 200 ms 且需要 multi-hop 时应拒绝，改为单轮 + 更好的检索器。
- **置信度定义**：归一化后的 top-1/top-2 差距；或检索分数经过校准（在标注集上把分数映射为"正确概率"）；或由生成器判断"现有证据能否回答每个子约束"。不要用融合分的绝对值（Q7、Q4）。
- **防止改写跑偏**：改写只能细化或同义扩展原始约束，不能引入新约束（Q11 中 "sun" 导致 top-1 变化）；保留原查询的检索结果做对照；限制轮数；每轮记录改写原因和结果，便于审计；用尽轮数时返回低置信标记或反问用户。
- **成本权衡**：在评估集上画"轮数—准确率—延迟"曲线，按查询难度分桶，找到准确率提升开始不值得延迟增加的拐点。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 23 ColPali 与视觉原生文档 RAG](../../23-colpali-vision-native-rag/docs/zh.md)：本节的先修；文档页面的视觉检索是多模态 RAG 的一路。
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)：单模态 RAG 的基本流程。
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：混合检索、RRF、重排序在文本场景下的做法。
- [阶段 12 · 02 CLIP 与视觉语言对比 Pretraining](../../02-clip-contrastive-pretraining/docs/zh.md)：共享 embedding 空间是跨模态检索的基础。
- [阶段 12 · 19 音频语言模型：从 Whisper 到 Audio Flamingo 3 的演进](../../19-audio-language-whisper-to-af3/docs/zh.md)：音频模态的表示与理解。

### 本节被哪些后续内容用到
- [阶段 12 · 25 多模态 Agents 与计算机操作](../../25-multimodal-agents-computer-use/docs/zh.md)：agentic 循环从"再检索"扩展到"再行动"。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：agentic multi-hop RAG 用到的循环模式。
- [阶段 19 · 04 多模态文档问答](../../../19-capstone-projects/04-multimodal-document-qa/docs/zh.md)：综合项目中的多模态检索与带引用回答。
- [阶段 19 · 68 RAG Evaluation](../../../19-capstone-projects/68-rag-eval-precision-recall/docs/zh.md)：Recall@k、nDCG、忠实度等评估指标的实现。

### 延伸关键词
`cross-modal retrieval` · `CLIP / SigLIP 2` · `CLAP` · `score fusion` · `min-max normalization` · `RRF` · `MoE fusion` · `grounded generation` · `citations` · `MuRAG` · `agentic RAG` · `query decomposition` · `query drift` · `Recall@k`
