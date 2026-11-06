# 测验 · 实体链接和消歧（Entity Linking & Disambiguation）

> **阶段 05 · NLP 基础到进阶 · 第 25 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 实体链接（Entity Linking, EL）的定义 | 把文本中的每个 mention（实体提及）映射到知识库（KB）里**唯一**的条目，如 Wikidata 的 `Q41421`；NER 只给类型，EL 给"到底是哪一个" |
| 2 | 两个子任务 | **候选生成**（谁可能是它？给出 10–30 个候选）+ **消歧**（结合上下文选出正确的那一个） |
| 3 | 别名索引（alias index） | 表面形式 → 候选实体的倒排表；Wikipedia 别名数据约 1800 万条 (alias, entity) 对，是候选生成的主力 |
| 4 | 先验 + 上下文（Milne & Witten, 2008） | `P(entity | mention) × 上下文相似度`；无需训练、速度快，是低延迟场景的 baseline |
| 5 | 基于 embedding 的消歧（BLINK / REL） | 用 `[MENTION]…[/MENTION]` 标记 mention 编码上下文，实体描述离线预编码，查询时点积取最大；2020–2024 的默认做法 |
| 6 | 生成式消歧（GENRE / LLM-EL） | 逐 token 生成实体规范名，用合法实体名构成的 trie 做**约束解码**，保证输出一定是合法 KB 条目；LLM 版本 = 候选列表 + 受约束 JSON |
| 7 | 两个必报指标 | **mention recall**（gold 实体是否出现在候选里，是整条流水线的上限）+ **消歧准确率 / F1**；端到端 ≈ 两者相乘 |
| 8 | NIL 处理 | KB 里没有的实体（新公司、冷门人物）必须预测 NIL，而不是硬猜一个最像的；单独评估 |
| 9 | 常见失败模式 | mention 边界错误、流行度偏置（popularity bias）、跨语言 EL、KB 过期 |
| 10 | 生产模式 | NER → 共指消解 → 对每个 mention 做 EL → 把共指簇折叠成一个规范实体；输出"每个实体一个 KB id"，而不是"每个 mention 一个" |

### 核心技能（能动手做到）

- [ ] 从零实现"别名索引 + Jaccard 上下文重叠 + 先验"的消歧器，在本节 11 个用例上复现"有先验 11/11、无先验 10/11"
- [ ] 能手算某个 mention 的每个候选的 Jaccard 分数，解释为什么 "Jordan scored 45 points…" 在去掉先验后被错链到约旦（Q810）
- [ ] 能给消歧器加上 NIL 阈值，并构造含 NIL 样本的测试集验证它
- [ ] 能分别计算 mention recall@K 与 top-1 准确率，并说明"99% 消歧 × 80% 召回 ≈ 79% 端到端"
- [ ] 能用 sentence-transformers 写出 BLINK 风格的 bi-encoder：mention 标记 → 编码 → 与预计算的实体向量做点积
- [ ] 能写出"候选列表 + 受约束 JSON"的 LLM-EL prompt，并说明为什么输出必须限制在合法 KB id 内

---

## 二、基础自测（选择题）

**Q1.** NER 已经把句子 "Jordan beat the press." 中的 "Jordan" 标为 `PERSON`。实体链接（EL）在此基础上输出的是：

- A. 更细粒度的类型，比如把 `PERSON` 细化成 `ATHLETE`
- B. 知识库中唯一的条目标识，比如 Wikidata 的 `Q41421`
- C. 句子中所有指向同一个人的 mention 组成的共指簇
- D. 这个 mention 的上下文 embedding 向量

**Q2.** 某 EL 系统在测试集上：候选生成的 mention recall 为 80%；在 gold 实体确实出现在候选列表里的前提下，消歧 top-1 准确率为 99%。这条流水线端到端的 top-1 准确率大约是：

- A. 99%
- B. 约 89%
- C. 约 79%
- D. 无法估计，两个指标彼此独立

**Q3.** GENRE 这类生成式实体链接模型如何保证输出的一定是知识库里真实存在的实体？

- A. 先自由生成，再用 BM25 在实体标题里找最接近的一个
- B. 在所有合法实体名构成的前缀树（trie）上做约束解码，每一步只允许能延续成合法名字的 token
- C. 生成多个答案后用投票选出出现次数最多的
- D. 用正则表达式过滤掉不像实体名的输出

**Q4.** BLINK 风格的 embedding 消歧中，讲义把 mention 包成 `"... [MENTION] Jordan [/MENTION] ..."` 再编码，而实体则编码成 `"<id>: <description>"`。关于这种设计，下列说法**错误**的是：

- A. 标记告诉编码器"这段上下文要表示的是哪个 span"，同一句话里有多个 mention 时尤其重要
- B. 实体向量不依赖任何 mention，可以在建索引时一次性算好
- C. 查询时只需编码一次 mention 上下文，再与候选实体向量做点积取最大
- D. 因为 mention 与实体分开编码，模型能逐 token 地让 mention 与实体描述交互，所以精度一定高于 cross-encoder

**Q5.** 一个在通用网页数据上训练的 EL 系统，处理机器学习论文时经常把 "Michael I. Jordan"（伯克利教授）链接到篮球运动员 Michael Jordan。最直接有效的改进是：

- A. 把先验 `P(entity | mention)` 的权重调得更大
- B. 用领域语料统计领域内的先验，或在领域标注数据上微调消歧器
- C. 删掉候选生成这一步，让模型直接在全库里选
- D. 提高上游 NER 的召回率

**Q6.** 下列哪一项**不是**合理的 NIL（"不在知识库中"）处理策略？

- A. 对 top-1 分数设阈值，低于阈值就输出 NIL
- B. 训练一个二分类器判断"top-1 候选是否真的匹配"
- C. 在候选列表中显式加入一个 NIL 候选，让它和真实实体一起参与打分
- D. 只要候选列表非空，就永远返回先验最高的那个候选

**Q7.** 讲义推荐的生产模式是"NER → 共指消解 → EL → 把簇折叠成一个规范实体"。把共指消解放在 EL **之前**的主要理由是：

- A. 共指消解能直接产生 KB id，EL 只是校验
- B. "他""这家公司"这类 mention 单独无法链接；先聚成簇，整簇共享上下文证据并保证同一实体只得到一个 id
- C. 共指消解能把候选数量从 30 降到 1
- D. EL 模型只接受代词作为输入

---

## 三、动手 / 代码题

**Q8.** 本节 `code/main.py` 的打分核心如下：

```python
def tokenize(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))

# disambiguate() 循环内部：
            overlap = len(ctx_tokens & desc_tokens)
            union = len(ctx_tokens | desc_tokens)
            jac = overlap / union if union else 0.0
        prior = PRIORS.get(cand, 0.0) if use_prior else 1.0
        score = jac + 0.1 * prior
        scored.append((cand, score, jac, prior))
    scored.sort(key=lambda x: -x[1])
    return scored[0][0], scored[0][1]
```

相关数据：

```python
"jordan": ["Q41421", "Q810", "Q254110", "Q3308285"],
"Q41421":  "Michael Jordan American basketball player Chicago Bulls six championships",
"Q810":    "Jordan country Middle East kingdom capital Amman Arabic",
"Q254110": "Michael B Jordan American actor Black Panther Creed film",
"Q3308285": "Michael I Jordan Berkeley professor machine learning statistics",
"Q41421":  0.50, "Q810":    0.20, "Q254110": 0.20, "Q3308285": 0.10,
```

对 `disambiguate("Jordan", "Jordan scored 45 points against the Lakers last night.", use_prior=...)`：

1. `use_prior=False` 和 `use_prior=True` 分别返回什么（实体 id 与保留 3 位小数的分数）？
2. 为什么去掉先验后会错链到约旦（Q810）？Q810 和 Q3308285 分数相同，为什么赢的是 Q810？
3. `use_prior=False` 时代码令 `prior = 1.0` 而不是 `0.0`，这会影响排序吗？会影响什么？

**Q9.** 找 bug：有同学想测试 NIL 场景，在 `main()` 的 `test_cases` 末尾加了一行：

```python
("Tesla", "Tesla unveiled a new electric car.", None),
```

运行后程序崩溃了。指出崩溃发生在哪一行、报什么错，并给出最小修复。

**Q10.** 扩展：基于本节的数据（`ALIAS_INDEX / KB_DESC / PRIORS / tokenize`），写两个函数：

1. `disambiguate_nil(mention, context, tau=0.05)`：返回 `(entity_id 或 "NIL", score)`。要求：候选为空返回 NIL；**计算 Jaccard 前把 mention 自身这个词从上下文和描述中去掉**；若最佳候选的 Jaccard 低于 `tau` 则返回 NIL。
2. `mention_recall_at_k(cases, k)`：候选按先验从高到低排序后取前 k 个，统计 gold 落在其中的比例。

并解释：为什么要去掉 mention 自身这个词？

---

## 四、面试高频题

**Q11.**（基础必考）什么是实体链接？它和 NER、共指消解分别是什么关系？一个典型的 EL 流水线由哪几步组成？

**Q12.**（原理深挖）对比三种消歧方法：先验 + 上下文（Milne & Witten）、embedding 检索（BLINK / REL）、生成式（GENRE / LLM）。各自的原理、优缺点和适用场景是什么？

**Q13.**（工程实践）你要上线一个 EL 系统，该怎么评估？为什么讲义强调"mention recall 和消歧准确率必须同时报告"？NIL 怎么评估？

**Q14.**（场景设计）公司想把内部文档里提到的员工、产品、项目链接到内部知识库（约 1 万个实体，每天新增若干条），每天处理 5 万篇文档。请设计 EL 方案，说明知识库、候选生成、消歧器、NIL 策略、评估和刷新机制。

**Q15.**（追问型）"直接让 LLM 读句子，输出这个 mention 对应的 Wikidata QID 不就行了？"——你怎么回应？如果一定要用 LLM，应该怎么用？

---

## 五、参考答案与解析

### Q1 — 答案：B

EL 的输出是 KB 中**唯一**的条目，如 `Q41421`（篮球运动员 Michael Jordan）或 `Q810`（约旦国）。A 是细粒度实体分类（fine-grained typing），仍然是"类型"而不是"哪一个"；C 是共指消解的输出；D 是 embedding 方法的中间产物，不是最终结果。

### Q2 — 答案：C

候选生成是整条流水线的"天花板"：gold 不在候选里，消歧器再强也选不出来。端到端 ≈ `0.80 × 0.99 = 0.792`，约 79%。讲义的说法是"99% 消歧 + 80% 候选召回 = 一条 80% 的流水线"，即端到端被召回率封顶。A 是只看消歧准确率的常见误判；D 错在两者是串联关系，而不是独立的。

### Q3 — 答案：B

GENRE 把实体链接变成"生成实体的规范名"，并用所有合法实体名构建前缀树（trie）：解码每一步只允许那些能延续成某个合法名字的 token，因此最终输出一定能对应到一个 KB 条目。这与第 20 节的约束解码是同一机制。A、D 都是"先生成后修补"，无法保证合法；C 是 self-consistency，与合法性无关。

### Q4 — 答案：D

A、B、C 都是 bi-encoder（双塔）设计的正确描述：标记告诉编码器"表示哪一个 span"；实体向量与查询无关，可以离线预计算并建 ANN 索引；查询时只编码一次。D 恰好说反了：分开编码意味着 mention 和实体在编码阶段**没有**逐 token 交互，这是 bi-encoder 快但精度低于 cross-encoder 的原因。BLINK 论文的完整方案是 bi-encoder 召回 + cross-encoder 重排。

### Q5 — 答案：B

问题来源是**流行度偏置**：网页语料里篮球 Jordan 远比 ML 教授常见，先验 `P(e | m)` 和训练数据都偏向它。A 会让偏置更严重；C 让问题更难而不是更容易；D 与边界无关，mention 本身已经找对了。正确做法是用领域语料重新统计先验（在 ML 论文里 "Jordan" 多半是教授），或在领域标注集上微调，这也是讲义 Ship It 部分"标记未经领域微调、受流行度偏置影响的系统"的原因。

### Q6 — 答案：D

A（阈值）、B（分类器）、C（显式 NIL 候选）都是讲义 skill 文件中列出的 NIL 策略。D 等于"永远不输出 NIL"：对一个 KB 里不存在的新公司，它会被链接到同名的某个已有实体，错误的边随后写进知识图谱，污染下游。

### Q7 — 答案：B

代词和名词短语（"他"、"这家公司"）本身没有可用于检索的表面形式，单独做 EL 无法链接；先做共指消解，把它们和 "Michael Jordan" 聚成一个簇，整簇只需链接一次。这样既能汇集整簇的上下文证据，又能保证同一实体在一篇文档里只得到一个 KB id（输出是"每个实体一个 id"，而不是"每个 mention 一个"）。A、C、D 都不是共指消解的功能。

### Q8 — 参考答案

**1. 返回值**（与实际运行一致）：

```text
use_prior=False → ('Q810',   0.163)   # 实际值 0.1625
use_prior=True  → ('Q41421', 0.109)
```

**2. 逐个候选手算**：上下文分词后是 `{jordan, scored, 45, points, against, the, lakers, last, night}`，共 9 个词。

| 候选 | 描述词数 | 交集 | 并集 | Jaccard | 无先验得分 `jac+0.1` | 有先验得分 `jac+0.1·prior` |
|------|---------|------|------|---------|-----------------|-------------------|
| Q41421 | 9 | {jordan} = 1 | 17 | 0.0588 | 0.1588 | **0.1088** |
| Q810 | 8 | 1 | 16 | 0.0625 | **0.1625** | 0.0825 |
| Q254110 | 9 | 1 | 17 | 0.0588 | 0.1588 | 0.0788 |
| Q3308285 | 8 | 1 | 16 | 0.0625 | **0.1625** | 0.0725 |

- 上下文里没有任何真正的证据词（"Lakers" 不在 Michael Jordan 的描述里），四个候选的交集都只有 mention 自己 "jordan"。此时 Jaccard 的差异**完全来自分母**：描述越短，并集越小，分数越高。Q810 和 Q3308285 的描述各 8 个词，于是并列第一。这说明 Jaccard 会系统性地偏向"描述短"的实体。
- 并列时为什么是 Q810：`list.sort` 是**稳定排序**，分数相同的元素保持原有顺序；而 `scored` 的顺序就是 `ALIAS_INDEX["jordan"]` 的顺序，Q810 排在 Q3308285 前面。
- 加上先验后，Q41421 多出 `0.1 × 0.5 = 0.05`，足以压过 0.0037 的 Jaccard 差距。这正是"上下文证据弱时由先验兜底"的设计意图。

**3.** 不影响排序：`prior = 1.0` 让每个候选都加上同一个常数 0.1，排名完全由 Jaccard 决定。它影响的是**打印出来的分数**：无先验时显示的 score 比纯 Jaccard 大 0.1（所以是 0.163 而不是 0.0625）。如果想打印纯 Jaccard，应写成 `prior = 0.0`，或者在 `score` 计算中按 `use_prior` 分支处理。

### Q9 — 参考答案

`disambiguate("Tesla", ...)` 中 `ALIAS_INDEX.get("tesla", [])` 返回空列表，函数返回 `(None, 0.0)`，这一步没问题。崩溃发生在 `run_eval` 的打印行：

```python
print(f"  [{tag}] mention={mention:<10} pred={pred:<7} gold={gold:<7} score={score:.3f}")
```

`pred` 和 `gold` 都是 `None`，而 `None` 不支持 `<7` 这样的格式说明符，抛出：

```text
TypeError: unsupported format string passed to NoneType.__format__
```

最小修复：格式化前转成字符串（或统一用 `"NIL"` 表示）：

```python
pred_s = pred if pred is not None else "NIL"
gold_s = gold if gold is not None else "NIL"
print(f"  [{tag}] mention={mention:<10} pred={pred_s:<7} gold={gold_s:<7} score={score:.3f}")
```

注意：此时 `ok = pred == gold` 为 `None == None → True`，这个用例会被判为正确，语义上也合理（候选为空 = NIL）。更规范的做法是让 `disambiguate` 直接返回字符串 `"NIL"`，测试集也用 `"NIL"` 作为 gold。

### Q10 — 参考答案

```python
from main import ALIAS_INDEX, KB_DESC, PRIORS, tokenize


def disambiguate_nil(mention, context, tau=0.05, use_prior=True):
    m = mention.lower()
    candidates = ALIAS_INDEX.get(m, [])
    if not candidates:
        return "NIL", 0.0                      # 候选为空：直接 NIL
    ctx = tokenize(context) - {m}              # 去掉 mention 自身这个"白送"的重叠词
    best, best_jac, best_score = None, 0.0, float("-inf")
    for cand in candidates:
        desc = tokenize(KB_DESC.get(cand, "")) - {m}
        union = len(ctx | desc)
        jac = len(ctx & desc) / union if union else 0.0
        prior = PRIORS.get(cand, 0.0) if use_prior else 0.0
        score = jac + 0.1 * prior
        if score > best_score:
            best, best_jac, best_score = cand, jac, score
    if best_jac < tau:                         # 上下文证据不足 → NIL
        return "NIL", best_score
    return best, best_score


def mention_recall_at_k(cases, k):
    hit = 0
    for mention, _, gold in cases:
        cands = sorted(ALIAS_INDEX.get(mention.lower(), []),
                       key=lambda e: -PRIORS.get(e, 0.0))[:k]
        hit += gold in cands
    return hit / len(cases)
```

在下面 5 个用例上实际运行（前 3 个在库内，后 2 个为 NIL）：

```python
cases = [
    ("Jordan", "Jordan borders Syria, Iraq, and Saudi Arabia in the Middle East.", "Q810"),
    ("Paris", "Paris Hilton is a television personality and heiress.", "Q55411"),
    ("Python", "The python is a large nonvenomous snake found in Asia.", "Q83320"),
    ("Jordan", "Jordan Peterson released a new book on psychology.", "NIL"),
    ("Tesla", "Tesla unveiled a new electric car.", "NIL"),
]
```

```text
Jordan  pred=Q810    gold=Q810    score=0.153
Paris   pred=Q55411  gold=Q55411  score=0.410
Python  pred=Q83320  gold=Q83320  score=0.353
Jordan  pred=NIL     gold=NIL     score=0.050
Tesla   pred=NIL     gold=NIL     score=0.000
recall@1 = 0.00
recall@2 = 1.00
recall@3 = 1.00
```

（recall@K 只在前 3 个库内用例上统计：`in_kb = [x for x in cases if x[2] != "NIL"]`。）

**为什么要去掉 mention 自身**：mention 一定出现在上下文里，而它的别名通常也出现在每个候选的描述里（"jordan" 在 4 个描述里都有）。这个词对所有候选"白送"一份重叠，让每个候选都有约 0.06 的基础分，阈值就很难分开"有证据"和"没证据"。去掉之后，Jaccard 只反映**真正的上下文证据**，阈值才有意义。

**两点观察**：

- `recall@1 = 0`：这三个用例的 gold 恰好都不是该别名下最热门的实体。"按先验取 top-1" 本身就是 Milne-Witten 的纯先验 baseline，说明只靠流行度在长尾实体上会全错，而把 K 放大到 2 就能把 gold 全部召回进候选。
- 阈值是一把双刃剑：用同样的 `tau=0.05` 去跑原始用例 "Jordan scored 45 points against the Lakers"，会得到 NIL（误判），因为玩具描述里没有 "Lakers"。真实系统中 `tau` 要在带 NIL 标注的验证集上调，而且描述越丰富（或改用 embedding 相似度），阈值越可靠。

### Q11 — 参考回答要点

- **定义**：把文本中的 mention 映射到 KB 中唯一条目（Wikidata / Wikipedia / DBpedia / 领域 KB），解决"同名不同实体"（Jordan 可能是篮球运动员、演员、ML 教授或国家）和"同实体不同名"（JFK / John F. Kennedy）。
- **与 NER 的关系**：NER 找出 span 并给类型，是 EL 的上游；NER 的边界错误（"Bank of America" 被切成 "Bank"）会让候选检索走错别名，直接拉低 EL 召回。
- **与共指的关系**：共指把指向同一实体的 mention 聚成簇；EL 给簇一个规范 id。生产中按 NER → 共指 → EL → 簇折叠的顺序执行。
- **两步流水线**：候选生成（别名索引 / 稠密检索，返回 10–30 个候选）→ 消歧（先验 + 上下文、embedding 或生成式）→ NIL 判定。
- **加分点**：指出端到端模型（ELQ、BLINK、ExtEnD、GENRE）可以一次完成检测、候选和消歧，但生产仍以流水线为主，因为每个组件可以单独替换、单独评估。

### Q12 — 参考回答要点

| 方法 | 原理 | 优点 | 缺点 | 适用 |
|------|------|------|------|------|
| 先验 + 上下文（Milne & Witten 2008） | `P(e | m)`（来自 Wikipedia 锚文本统计）× 上下文相似度 | 无需训练、极快、可解释 | 对长尾实体、领域实体弱；有流行度偏置 | 极低延迟、baseline |
| embedding（BLINK / REL） | bi-encoder 分别编码 "mention + 上下文" 与 "实体描述"，点积取最大；BLINK 原论文再用 cross-encoder 重排 | 实体可离线预编码；能做 zero-shot（新实体只要有描述）；可扩展到百万级实体 | 依赖实体描述质量；bi-encoder 精度不如 cross-encoder | 通用英文 + Wikipedia 的默认方案 |
| 生成式（GENRE、LLM） | 生成实体规范名，用 trie / 候选白名单约束输出 | 能利用模型的世界知识；输出合法性由约束保证；mGENRE 支持跨语言 | 解码慢、成本高；不加约束就会编造实体 | 研究 SOTA、跨语言、低流量的 LLM 方案 |

- **常见误区**：认为 LLM 时代可以跳过候选生成。实际上候选列表既是 LLM 的"选择题选项"，也是约束输出的白名单。
- **加分点**：讲清 bi-encoder 与 cross-encoder 的取舍（召回用双塔、重排用交叉），这和 RAG 中"向量召回 + reranker"完全同构。

### Q13 — 参考回答要点

- **两个核心指标**：
  - **Mention recall@K**：gold 实体出现在前 K 个候选中的比例，只评估候选生成，是整条流水线的上限。
  - **消歧准确率 / F1（P@1）**：在 gold 在候选中的前提下，top-1 是否正确。
- **为什么必须同时报告**：二者是串联关系，端到端 ≈ 召回 × 消歧准确率。只报消歧准确率会掩盖候选生成的问题，比如"99% 准确率"实际只是一条约 79% 的流水线；反过来，改进消歧器之前也要先确认瓶颈不在召回。
- **NIL 单独评估**：在含"KB 外实体"的测试集上算 NIL-detection 的 precision / recall / F1；in-KB 准确率和 NIL 检测率要分开报告，因为提高 NIL 阈值会用 in-KB 召回换 NIL 精度。
- **基准**：AIDA-CoNLL（1,393 篇 Reuters 文章，约 3.4 万个 mention，链接到 Wikipedia）。领域任务要自建同样格式的保留集。
- **加分点**：按实体流行度分桶报告（头部 vs 长尾），以暴露流行度偏置；区分 mention 级与文档级（簇级）指标。

### Q14 — 参考回答要点

1. **知识库**：内部 KB（员工、产品、项目），每个实体包含规范名、别名列表、简短描述、类型；记录版本日期，**每天增量同步**（解决 KB 过期问题）。
2. **候选生成**：别名索引（规范名、缩写、工号、产品代号、常见拼写变体、大小写归一化）+ 实体描述的 embedding 稠密检索做补充；离线统计 recall@K，目标 recall@30 尽量接近 100%。
3. **消歧**：
   - 首选 bi-encoder：实体描述离线编码（1 万个实体量很小），mention 用 `[MENTION]` 标记编码后点积；成本低，每天 5 万篇文档完全可承受；
   - 难例（top-1 与 top-2 分差小）可以交给 LLM：把候选列表放进 prompt，输出限定为候选 id 的枚举或 JSON schema（受约束解码，比如 Outlines 的 `choice`），不允许自由生成。
4. **NIL 策略**：top-1 分数阈值，或显式 NIL 候选；阈值在带 NIL 标注的验证集上调；NIL mention 进入"新实体候选池"，由人工确认后入库，形成刷新闭环。
5. **共指与折叠**：先 NER + 共指，每个簇只链接一次，文档级输出每个实体一个 id。
6. **评估**：标注约 100–几百个句子的保留集，报告 recall@K、P@1、NIL F1；重点关注同名员工（流行度偏置：老员工、高管的提及频率远高于新人），必要时在领域数据上微调。
- **加分点**：考虑权限与隐私（员工数据），以及上线后用人工纠错数据持续扩充别名表和训练集。

### Q15 — 参考回答要点

- **问题**：
  - **编造 id**：QID 是不透明的数字串，LLM 无法可靠记住，很容易生成一个格式合法但指向错误实体、甚至不存在的 id；
  - **知识过期**：模型训练截止后的新实体它不知道，又不会主动说 NIL；
  - **不可控**：输出没有约束，下游 KG 写入前无法保证合法；
  - **成本与延迟**：每个 mention 一次 LLM 调用，大规模处理代价高。
- **正确用法**（讲义的 2026 推荐模式）：先用别名索引或检索生成候选列表 → 把候选（id + 名称 + 描述）放进 prompt → 用受约束输出（JSON schema 中的枚举、Outlines `choice`，或 GENRE 式 trie）只允许从候选里选，或选 NIL → 输出的 id 回 KB 校验。
- **加分点**：让 LLM 输出"规范标题"再映射到 id，比直接输出 QID 更稳；LLM 只用于难例或低流量场景，高流量走 bi-encoder；讲义 skill 文件明确要求"拒绝任何没有把输出约束到合法 KB id 的 LLM-EL 流水线"。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 06 命名实体识别](../../06-named-entity-recognition/docs/zh.md)：EL 的上游，负责找出 mention 并确定边界。
- [阶段 05 · 24 共指消解](../../24-coreference-resolution/docs/zh.md)：先把 mention 聚成簇，再对簇做 EL。
- [阶段 05 · 02 词袋、TF-IDF 和文本表示](../../02-bag-of-words-tfidf/docs/zh.md)：本节代码的 Jaccard 上下文重叠就是最朴素的词袋相似度。
- [阶段 01 · 14 范数与距离](../../../01-math-foundations/14-norms-and-distances/docs/zh.md)：Jaccard、余弦、点积等相似度的定义。

### 本节被哪些后续内容用到
- [阶段 05 · 26 关系抽取与知识图谱构建](../../26-relation-extraction-kg/docs/zh.md)：EL 给出的规范 id 就是知识图谱的节点，否则 "Paris" 会变成多个歧义节点。
- [阶段 05 · 20 Structured Outputs & 约束解码](../../20-structured-outputs-constrained-decoding/docs/zh.md)：GENRE 的 trie 约束解码、LLM-EL 的候选枚举都依赖这一机制。
- [阶段 05 · 22 Embedding 模型深度剖析](../../22-embedding-models-deep-dive/docs/zh.md)：BLINK 风格的 bi-encoder 消歧。
- [阶段 05 · 14 信息检索与搜索](../../14-information-retrieval-search/docs/zh.md)：候选生成本质上是一个检索问题（倒排索引 + 稠密检索）。
- [阶段 11 · 03 结构化输出](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：工程上如何让 LLM 只输出合法的 JSON 和枚举值。
- [阶段 11 · 07 高级 RAG](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：实体级检索、图谱增强检索都依赖实体链接。

### 延伸关键词
`Wikidata QID` · `锚文本 / commonness 先验` · `bi-encoder vs cross-encoder` · `zero-shot entity linking` · `ELQ` · `mGENRE` · `NIL clustering` · `实体类型约束` · `GraphRAG`
