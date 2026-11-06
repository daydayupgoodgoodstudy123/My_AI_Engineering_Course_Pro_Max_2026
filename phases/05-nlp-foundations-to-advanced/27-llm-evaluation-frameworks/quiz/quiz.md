# 测验 · LLM Evaluation — RAGAS、DeepEval、G-Eval（LLM Evaluation — RAGAS, DeepEval, G-Eval）

> **阶段 05 · NLP 基础到进阶 · 第 27 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 传统指标的局限 | Exact Match / token F1 看不出语义等价："June 29th, 2007" 对 "June 29, 2007"，EM = 0，人会给满分 |
| 2 | LLM-as-judge | 用一个 judge LLM 按评分细则（rubric）给 `(query, context, answer)` 打 0–1 分；成本低（讲义：GPT-4o-mini 每条约 0.003 美元，1000 条不到 5 美元） |
| 3 | judge 的"静默失败" | 偏置（偏好长答案、同家族模型、与 prompt 风格一致的答案）；JSON 解析失败 → NaN 被悄悄排除出均值；judge 版本升级导致所有指标漂移 |
| 4 | RAG 四指标（RAGAS） | Faithfulness（答案中的每条 claim 能否被检索上下文蕴含，用 NLI）· Answer relevance（由答案反推问题，与真实问题比相似度）· Context precision（检索到的 chunk 中有多少相关）· Context recall（检索是否覆盖了 gold 答案所需的全部信息） |
| 5 | G-Eval | 自定义评价标准 → 展开成 chain-of-thought 评估步骤 → 输出 0–1 分；显式步骤比"直接打个 0–1 分"更稳定 |
| 6 | DeepEval | "LLM 版的 pytest"：G-Eval、faithfulness、hallucination 等指标 + 阈值断言，在每个 PR 上运行，回归就阻止合并 |
| 7 | 校准（calibration） | 先用 ≥ 50（讲义建议 100）条人工标注样本算 judge 与人工的 Spearman ρ；ρ < 0.7 说明 rubric 要返工 |
| 8 | 常见陷阱 | 自评（同一模型生成 + 评判）虚高 10–20%；pairwise 位置偏置（要随机化并正反各跑一次）；均值掩盖尾部故障（必须看最低 10%）；评测集不做版本管理；judge 调用成本 |
| 9 | 2026 典型组合 | RAGAS 做线上监控（可用 reference-free 模式）、DeepEval 做 CI 闸门、G-Eval 补充自定义维度；三者"有用地不一致" |

### 核心技能（能动手做到）

- [ ] 能用纯标准库实现玩具版 faithfulness / answer relevance / context precision / context recall / G-Eval，并逐个解释本节 3 个 case 的输出数字
- [ ] 能构造一个"词重叠 faithfulness 抓不到的数字幻觉"，并写出对数字更严格的版本
- [ ] 能手写（或用 scipy）计算 judge 分数与人工标注的 Spearman ρ（含并列秩），据此判断 judge 能否上线
- [ ] 能写出 DeepEval + pytest 的 CI 闸门：逐指标阈值、失败信息里带 case id、最低 10% 告警
- [ ] 能设计 pairwise 评测的位置去偏流程（随机顺序 + 交换顺序再跑一次）
- [ ] 能用一个 `llm(prompt) -> str` 回调和一个 embedding 模型，实现 RAGAS 风格的 answer relevance

---

## 二、基础自测（选择题）

**Q1.** 预测答案 "June 29th, 2007."，标准答案 "June 29, 2007."。按 SQuAD 风格归一化（小写、去标点、去冠词、按空格切分）后，Exact Match 和 token F1 分别约为：

- A. EM = 1，F1 = 1.0
- B. EM = 0，F1 ≈ 0.67
- C. EM = 0，F1 = 0
- D. EM = 0，F1 ≈ 0.86

**Q2.** 问题："第一代 iPhone 是什么时候发布的？"检索上下文只讲了 iPhone 的发布日期。模型回答："Apple is a technology company based in Cupertino."（这句话在现实中是对的）。它的 faithfulness 应该：

- A. 很高，因为这句话是真实的
- B. 很低，因为 faithfulness 衡量的是答案中的 claim 能否被**检索到的上下文**支持，而不是是否符合现实
- C. 无法计算，因为没有 gold 答案
- D. 等于 answer relevance

**Q3.** RAGAS 的 answer relevance 是怎么计算的？

- A. 计算答案与 gold 答案的 BLEU
- B. 让 LLM 根据答案反向生成若干个"这个答案可能在回答的问题"，把它们与真实问题做 embedding 相似度，再取平均
- C. 统计答案中出现了多少个问题里的关键词
- D. 让 judge 直接判断答案是否正确

**Q4.** 检索返回了 5 个 chunk，其中只有 1 个相关，但这 1 个 chunk 已经包含回答问题所需的全部信息。此时 context precision 和 context recall 大约是：

- A. precision = 1.0，recall = 0.2
- B. precision = 0.2，recall = 1.0
- C. precision = 0.2，recall = 0.2
- D. precision = 1.0，recall = 1.0

**Q5.** 一次 1000 条样本的评测里，judge 有 80 条输出了无法解析的 JSON，代码把这些分数记为 NaN，然后用 `nanmean` 求平均。最大的问题是：

- A. 计算变慢
- B. 失败样本被悄悄排除，均值只代表"judge 能解析的那部分"，而这些失败往往集中在难例上，结果会偏高且不可比
- C. NaN 会让均值变成 0
- D. 没有问题，`nanmean` 是标准做法

**Q6.** 用 judge 做 pairwise 比较（"A 和 B 哪个更好？"），发现 judge 总是偏向第一个出现的答案。正确的做法是：

- A. 永远把自家模型的答案放在第一位
- B. 换一个更大的 judge 就能消除偏置，不用改流程
- C. 随机化顺序，并且交换顺序再跑一次；两次结论不一致时记为平局
- D. 改成只评一个答案、不再比较

**Q7.** 你用 100 条人工标注样本校准一个 G-Eval 指标，judge 分数与人工分数的 Spearman ρ = 0.45。下一步最合理的是：

- A. ρ > 0 说明正相关，可以上线
- B. 把 CI 阈值调高，弥补 judge 的不准
- C. 重写评分细则（更明确的 evaluation steps），必要时更换 judge 模型，重新校准直到 ρ ≥ 0.7 再上线
- D. 把 judge 分数和 BLEU 平均一下

---

## 三、动手 / 代码题

**Q8.** 本节 `code/main.py` 中的 faithfulness 实现如下（`tokenize` 会小写化、只保留字母数字串，并去掉 `STOP` 中的停用词，如 the、on、was、in）：

```python
def faithfulness(answer, context):
    context_set = set(tokenize(context))
    claims = split_sentences(answer)
    if not claims:
        return 0.0
    supported = 0
    for claim in claims:
        claim_tokens = tokenize(claim)
        if not claim_tokens:
            continue
        overlap = sum(1 for t in claim_tokens if t in context_set)
        if overlap / len(claim_tokens) >= 0.5:
            supported += 1
    return supported / len(claims)
```

case 1 的输入：

```python
context = "Apple released the first iPhone on June 29, 2007. The moon landing was in 1969."
answer  = "The first iPhone launched on June 29, 2006, shortly after the moon landing."
```

1. `faithfulness(answer, context)` 返回多少？写出计算过程。
2. 脚本末尾打印的解读是 `case 1 = hallucinated date -> g-eval drops, faithfulness partial`。这与实际输出一致吗？说明了词重叠 faithfulness 的什么缺陷？

**Q9.** 本节的 answer relevance 是问题与答案词集合的 Jaccard：

```python
def answer_relevance(question, answer):
    q_tokens = set(tokenize(question))
    a_tokens = set(tokenize(answer))
    if not q_tokens or not a_tokens:
        return 0.0
    return len(q_tokens & a_tokens) / len(q_tokens | a_tokens)
```

问题固定为 `"When was the first iPhone released?"`，分别计算下面三个答案的得分，并评价这个指标的问题：

```python
a1 = "June 29, 2007."
a2 = "The first iPhone was released."
a3 = "The first iPhone was released on June 29, 2007."
```

**Q10.** 修复 Q8 暴露的问题：写一个 `faithfulness_strict(answer, context, ratio=0.5)`，在原有"重叠比例 ≥ ratio"的基础上增加一条规则：**claim 中任何含数字的 token 只要不在上下文中，这个 claim 就判为不受支持**。验证它在本节 3 个 case 上的结果。

**Q11.** 讲义要求先校准再信任 judge。用纯 Python 实现：

1. `spearman(xs, ys)`：Spearman 秩相关，并列值取平均秩；
2. `bottom_quantile(scores, q)`：返回分数最低的 `q` 比例样本的下标（至少 1 个）。

用下面的数据计算 ρ，并判断这个 judge 能否上线；再找出最低 20% 的样本下标：

```python
judge = [0.9, 0.8, 0.85, 0.3, 0.95, 0.6, 0.7, 0.2, 0.9, 1.0]
human = [1,   1,   1,    0,   1,    0,   1,   0,   0,   1]
```

---

## 四、面试高频题

**Q12.**（基础必考）什么是 LLM-as-judge？它为什么能用？又为什么会"静默失败"？怎样才能让团队信任 judge 给出的数字？

**Q13.**（原理深挖）讲清 RAGAS 的四个指标各自怎么算、诊断的是检索还是生成，以及哪些指标需要 gold 答案。

**Q14.**（工程实践）为一个 RAG 产品设计基于 DeepEval 的 CI 评测闸门：数据集、指标与阈值、judge 选型、回归判定、尾部告警、成本控制。

**Q15.**（场景设计）团队准备把 judge 从旧模型升级到新模型。新 judge 上线后所有分数整体降了 0.08。你如何判断这是"系统变差了"还是"尺子变了"？升级流程应该怎么设计？

**Q16.**（追问型）G-Eval 相比直接让模型"给个 0–1 分"好在哪里？如果 judge 自己就是被评测模型的同一家族，会出什么问题？

---

## 五、参考答案与解析

### Q1 — 答案：B

归一化后预测为 `[june, 29th, 2007]`，标准答案为 `[june, 29, 2007]`。EM 要求完全相同，所以为 0；公共 token 是 `june`、`2007` 两个，precision = 2/3，recall = 2/3，F1 = 0.67。讲义写的是 "F1 ~75%"，具体数值取决于分词方式（若把 "29th" 拆成 "29" 和 "th"，F1 ≈ 0.86，即 D）。但结论不变：**EM 为 0、F1 不满分，而人类会给满分**，词面指标看不出语义等价。

### Q2 — 答案：B

faithfulness 的定义是"答案中被检索上下文**蕴含**的 claim 占比"，衡量的是 grounding（有据可依），不是事实正确性。答案里的内容即使在现实中是真的，只要上下文不支持，就算"不忠实"。在 RAG 中这很重要：模型绕开检索内容、凭参数记忆作答，是幻觉风险的来源。本节代码中 case 2 的 faithfulness = 0.00 正是这种情况。C 错在 faithfulness 不需要 gold 答案。

### Q3 — 答案：B

讲义 Step 2：让 LLM 写出 n 个"这个答案可能在回答的问题"，用 embedding 编码后与原问题算余弦相似度并取平均。如果答案跑题，它反推出的问题就和原问题不像，相关性下降。A 需要 gold 答案，而且衡量的是表面重合；C 是本节玩具代码的近似做法（问题见 Q9）；D 衡量的是正确性，不是相关性。

### Q4 — 答案：B

context precision = 相关 chunk 数 / 检索到的 chunk 数 = 1/5 = 0.2（衡量"检索结果里有多少噪声"）；context recall = 所需信息被覆盖的比例 = 1.0（衡量"该找的有没有找全"）。两者分别诊断检索的"准"和"全"。另外，RAGAS 的实际实现还会考虑相关 chunk 的排名位置，相关 chunk 越靠前分数越高。

### Q5 — 答案：B

讲义把它列为 judge 静默失败的第二条："Bad JSON → NaN score → silently excluded from the aggregate"。被排除的样本往往是长答案、格式怪异或 judge 犹豫的难例，剔除后均值偏乐观；而且每次运行失败的样本不同，分母在变，不同版本之间不可比。正确做法：try/except 后显式记录失败模式（记 0 分或单独统计"解析失败率"并设告警），而不是让它从分母里消失。D 正是问题所在。

### Q6 — 答案：C

位置偏置是 judge 的系统性偏差，靠换更大的模型（B）不能保证消除。标准做法：随机化呈现顺序，并对每一对交换顺序再评一次；两次一致才算胜出，不一致就记为平局。A 是在利用偏置作弊；D 回避了问题，而且很多场景（模型对比、A/B 测试）就需要 pairwise。

### Q7 — 答案：C

讲义的标准：ρ < 0.7 说明 rubric 要返工；ρ 只有 0.3 左右时 judge 基本是噪声。0.45 的 judge 排序与人工只有弱相关，调 CI 阈值（B）解决不了"尺子不准"的问题；与 BLEU 平均（D）只会引入另一种噪声。应该把评价标准拆成明确的 evaluation steps（G-Eval 的做法），检查分歧最大的样本找出 rubric 漏洞，必要时换 judge，然后重新校准。

### Q8 — 参考答案

**1. 返回 1.0。** 计算过程：

- 上下文 token 集合（去停用词后）：`{apple, released, first, iphone, june, 29, 2007, moon, landing, 1969}`
- 答案只有一句，即一个 claim，tokens：`[first, iphone, launched, june, 29, 2006, shortly, after, moon, landing]`，共 10 个
- 在上下文中出现的：`first, iphone, june, 29, moon, landing`，共 6 个，比例 0.6 ≥ 0.5 → 判为支持
- `supported / len(claims) = 1 / 1 = 1.0`

**2. 不一致。** 实际输出是 `faithfulness = 1.00`，并不是"partial"。原因：

- 错误的年份 `2006` 只是 10 个 token 中的 1 个，词重叠比例仍有 0.6，过了 0.5 的阈值。**关键事实只占 claim 的一小部分**，词面重叠对它不敏感。
- "shortly after the moon landing" 这种荒谬的时间关系也没被识别，因为 "moon"、"landing" 恰好在上下文中出现过（来自一个与问题无关的 chunk）。
- 这正是讲义强调生产中要用 **NLI 蕴含**判断每个原子 claim 的原因：NLI 会判 "iPhone launched on June 29, 2006" 与上下文矛盾（contradiction），而不是数重叠词。
- 本例中真正抓到错误的是 G-Eval 近似（`g-eval correctness = 0.00`），因为它拿答案和**期望答案**比。这也说明多个指标要一起看：faithfulness 高不代表正确。

### Q9 — 参考答案

问题 tokens：`{when, first, iphone, released}`（the、was 是停用词）。

| 答案 | 答案 tokens | 交集 | 并集 | 得分 |
|------|------------|------|------|------|
| a1 `"June 29, 2007."` | {june, 29, 2007} | ∅ | 7 | **0.00** |
| a2 `"The first iPhone was released."` | {first, iphone, released} | 3 | 4 | **0.75** |
| a3 完整句 | {first, iphone, released, june, 29, 2007} | 3 | 7 | **0.43**（本节 case 0 的输出） |

（以上数值均已实际运行验证。）

问题：

- **最好的答案得 0 分，最没用的答案得最高分**：a1 简洁且完全正确，却和问题没有共同词；a2 只是复述问题、没给出日期，反而得分最高。
- 根源在于 Jaccard 的分母：答案里每多一个**新信息**（日期），并集就变大，分数就下降。词面重叠衡量的是"复述程度"，不是"是否在回答这个问题"。
- RAGAS 的做法是由答案**反推问题**再比较语义相似度：a1 反推出的问题是"某件事是哪天发生的？"，与原问题语义接近；a2 反推出的问题是"第一代 iPhone 发布了吗？"，与原问题不同。这样才能惩罚跑题、奖励切题。

### Q10 — 参考答案

```python
def faithfulness_strict(answer, context, ratio=0.5):
    context_set = set(tokenize(context))
    claims = split_sentences(answer)
    if not claims:
        return 0.0
    supported = 0
    for claim in claims:
        toks = tokenize(claim)
        if not toks:
            continue
        nums = [t for t in toks if any(ch.isdigit() for ch in t)]
        if any(n not in context_set for n in nums):   # 数字是"硬事实"，必须原样出现在上下文中
            continue
        if sum(t in context_set for t in toks) / len(toks) >= ratio:
            supported += 1
    return supported / len(claims)
```

实际运行结果：

```text
case 0 → 1.0   # 29、2007 都在上下文中
case 1 → 0.0   # 2006 不在上下文中，被拒绝
case 2 → 0.0   # 本来就只有 1/5 重叠
```

说明：

- 数字、日期、金额、专有名词是 RAG 幻觉的高发区，而且一个 token 就能让整句话变假，所以要"一票否决"，而不是参与比例投票。
- `sum(t in context_set for t in toks)` 利用了 `True == 1`，对布尔值直接求和。
- 这仍然是启发式：上下文写 "2,007 units"、答案写 "2007" 也会被误判为支持；"29th" 和 "29" 也匹配不上。生产中应该拆原子 claim + NLI，或者让 judge 按 rubric 逐条核对。

### Q11 — 参考答案

```python
def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1                          # 找出一段并列值
        avg = (i + j) / 2 + 1               # 并列值取平均秩（秩从 1 开始）
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs, ys):
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else 0.0


def bottom_quantile(scores, q=0.1):
    k = max(1, int(len(scores) * q))
    return sorted(range(len(scores)), key=lambda i: scores[i])[:k]


judge = [0.9, 0.8, 0.85, 0.3, 0.95, 0.6, 0.7, 0.2, 0.9, 1.0]
human = [1, 1, 1, 0, 1, 0, 1, 0, 0, 1]
print(round(spearman(judge, human), 3))   # 0.606
print(bottom_quantile(judge, 0.2))        # [7, 3]
```

结果：ρ ≈ **0.606**（已用 `scipy.stats.spearmanr` 交叉验证，结果一致）。

- 0.606 < 0.7，**不能上线**。看具体分歧：下标 8 的样本 judge 给 0.9、人工判 0；下标 6 的样本 judge 只给 0.7、人工判 1。这类"高分错例"正是 rubric 需要补充的地方。
- 为什么用 Spearman 而不是 Pearson：我们关心的是 judge 能否把好坏**排对顺序**，而不是分数与人工标签成线性关系；人工标签常常是 0/1 或 1–5 分档，并列值很多，所以要用平均秩处理。
- 最低 20% 是下标 `[7, 3]`（judge 分 0.2 和 0.3），它们应该被单独列出来人工复查。讲义的要求是：均值之外必须展示 bottom quantile。

### Q12 — 参考回答要点

- **定义**：用一个 LLM 按评分细则对输出打分（0–1 或 1–5），替代 EM / BLEU 这类静态指标。输入通常是 `(query, context, answer[, reference])`。
- **为什么能用**：LLM 能理解语义等价、改写和推理，与人工判断的一致性远高于词面指标，而成本只是人工的零头，可以在每次改动后跑上千条回归。
- **静默失败**：
  1. 偏置：长度偏置、自家族偏置、风格偏置、pairwise 位置偏置；
  2. 解析失败：坏 JSON → NaN → 被排除出均值；
  3. 版本漂移：judge 升级后所有指标都变了。
- **建立信任**：
  - **校准**：≥ 50–100 条人工标注，Spearman ρ ≥ 0.7；
  - **固定** judge 模型与版本；
  - judge 与被测模型用**不同家族**；
  - 解析失败显式记录；
  - 报告均值的同时报告最低 10%；
  - 评测集版本化。
- **加分点**：定期抽样做人机一致性复核；对高风险维度（安全、事实）保留人工复审。

### Q13 — 参考回答要点

| 指标 | 怎么算 | 诊断对象 | 是否需要 gold |
|------|-------|---------|-------------|
| Faithfulness | LLM 把答案拆成原子 claim → 逐条用 NLI 判断是否被上下文蕴含 → 被蕴含的比例 | 生成（是否幻觉、是否脱离上下文） | 否 |
| Answer relevance | 由答案反推 n 个问题 → 与原问题的 embedding 余弦取平均 | 生成（是否切题） | 否 |
| Context precision | 检索到的 chunk 中相关的比例（judge 判断相关性，RAGAS 实现中考虑排名） | 检索（准不准、噪声多不多） | 视实现而定 |
| Context recall | gold 答案中的信息有多少被检索内容覆盖 | 检索（全不全） | **是**（需要 gold 答案） |

- **组合诊断**：faithfulness 高但答案错 → 检索到了错误内容（看 context precision / recall）；context recall 高但 faithfulness 低 → 生成器没好好用上下文；answer relevance 低 → 答非所问。
- **注意**：讲义术语表说 RAGAS 是 "4 reference-free metrics"，但 context recall 需要 gold 答案，严格来说只有部分指标能做 reference-free 的线上监控。
- **加分点**：faithfulness ≠ 正确性（见 Q2）；线上流量没有 gold 答案时，只能用 reference-free 的指标做监控，离线回归集才能评 recall 和 correctness。

### Q14 — 参考回答要点

1. **数据集**：分层抽样的回归集（按意图、难度、长尾问题分层），每次改动打版本 tag 并写 change log；混入已知幻觉、跑题等"诱饵"样本，验证闸门能抓住它们。
2. **指标与阈值**：faithfulness（如讲义示例 ≥ 0.85）、contextual relevancy（≥ 0.7）+ 1–2 个 G-Eval 自定义指标（如"是否引用了正确来源"）；阈值来自历史基线，而不是拍脑袋。
3. **judge**：固定模型和版本；选通过校准（ρ ≥ 0.7）的最便宜模型（讲义举例 GPT-4o-mini、Claude Haiku、Mistral-small）；与生成模型不同家族。
4. **回归判定**：与上一个基线对比，既看绝对阈值，也看相对下降（如均值下降超过某个幅度，或某个分层显著变差）；单条断言之外加整体统计，避免一两条噪声样本让 CI 抖动。
5. **尾部告警**：输出最低 10% 样本的清单；最低分位的分数低于阈值时直接失败。
6. **工程**：写成 pytest 文件，每个 PR 运行，失败信息带 case id；解析失败计数超标也算失败；缓存未改动样本的 judge 结果以控制成本；大集合每晚全量跑、PR 上跑子集。
- **常见误区**：只看平均分；judge 升级与系统改动同一个 PR 上线，导致无法归因。

### Q15 — 参考回答要点

- **先怀疑"尺子"**：讲义的规则是"任何 judge 升级都必须并行跑基线"。用新旧 judge 在**同一批固定输出**（同一个系统版本、同一份评测集）上各打一次分。如果系统没变而分数降了 0.08，那就是尺子变了。
- **重新校准**：用同一批人工标注集分别算两个 judge 的 Spearman ρ。新 judge 的 ρ 更高，说明它更准，之前的分数可能是虚高的；ρ 更低就不应该升级。
- **重建基线**：确认升级后，用新 judge 对历史关键版本重新打分，建立新的基线序列；在报告里标明 judge 版本，不同 judge 的分数不直接比较。
- **流程**：judge 版本写入评测配置并纳入版本管理；升级单独走 PR，不和系统改动混在一起；过渡期双 judge 并行运行一段时间。
- **加分点**：分维度看漂移（是不是只在长答案上降分，即长度偏置变化）；检查解析失败率是否变化。

### Q16 — 参考回答要点

- **G-Eval 的改进**：
  - 把模糊的 "score 0–1" 拆成**显式评估步骤**（读期望输出 → 读实际输出 → 列出 claim → 逐条标注支持与否 → 计算比例），等于给 judge 一份可执行的 rubric，减少随意性，分数更稳定；
  - 框架可以根据评价标准自动展开成 CoT 步骤，便于定义 RAGAS 不覆盖的领域维度；
  - 步骤和理由（`metric.reason`）可审计，便于与人工分歧时排查。
  - 加分点：G-Eval 原论文还用评分 token 的概率对分数做加权求和，得到更细粒度、更连续的分数。
- **自评问题**：同一模型（或同家族）生成并评判，会偏好自己的措辞和推理风格，讲义称分数会虚高 10–20%，而且错误是相关的：模型自己没意识到的错误，作为 judge 也看不出来。对策：judge 换不同家族的模型；用人工校准集验证；关键结论用多个 judge 交叉验证。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 13 问答系统](../../13-question-answering/docs/zh.md)：EM / F1 的定义和局限。
- [阶段 05 · 14 信息检索与搜索](../../14-information-retrieval-search/docs/zh.md)：precision / recall 在检索中的含义，是 context precision / recall 的来源。
- [阶段 05 · 21 自然语言 Inference — 文本蕴涵](../../21-nli-textual-entailment/docs/zh.md)：faithfulness 的后端就是 NLI 蕴含判断。
- [阶段 05 · 22 Embedding 模型深度剖析](../../22-embedding-models-deep-dive/docs/zh.md)：answer relevance 依赖 embedding 余弦相似度。
- [阶段 01 · 15 机器学习中的统计学](../../../01-math-foundations/15-statistics-for-ml/docs/zh.md)：相关系数、秩统计。
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：评估集划分、指标选择的通用原则。

### 本节被哪些后续内容用到
- [阶段 05 · 28 长上下文 Evaluation](../../28-long-context-evaluation/docs/zh.md)：同样是"评测方法论"，关注上下文长度维度。
- [阶段 11 · 10 评估](../../../11-llm-engineering/10-evaluation/docs/zh.md)：在 LLM 工程体系中落地评测。
- [阶段 14 · 30 评测驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：把 CI 评测闸门的思想用到 agent 上。
- [阶段 17 · 21 LLM 功能的 A/B 测试](../../../17-infrastructure-and-production/21-ab-testing-llm-features/docs/zh.md)：线上对比实验与离线评测互补。
- [阶段 19 · 68 RAG 评测：精确率与召回率](../../../19-capstone-projects/68-rag-eval-precision-recall/docs/zh.md)：动手实现 RAG 检索评测。
- [阶段 19 · 75 端到端评测运行器](../../../19-capstone-projects/75-end-to-end-eval-runner/docs/zh.md)：把评测流水线工程化。

### 延伸关键词
`LLM-as-judge` · `MT-Bench / Chatbot Arena` · `pairwise vs pointwise` · `Spearman ρ / Kendall τ / Cohen's κ` · `reference-free evaluation` · `claim decomposition` · `SelfCheckGPT` · `Promptfoo` · `LangSmith / Phoenix` · `MLflow GenAI scorer`
