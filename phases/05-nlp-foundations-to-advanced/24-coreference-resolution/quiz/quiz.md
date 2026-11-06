# 测验 · 共指消解（Coreference Resolution）

> **阶段 05 · NLP 从基础到进阶 · 第 24 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过 `main.py` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 任务定义 | 输入一篇文档，输出 mention（文本片段）的聚类：同一簇的 mention 指向同一个真实世界实体 |
| 2 | 四类 mention | 命名实体（Tim Cook）、名词性（the CEO / the company）、代词（he / it）、同位语（Tim Cook, Apple's CEO,） |
| 3 | 为什么重要 | 讲义：不做共指，NER 流水线会漏掉 60–80% 的实体提及；摘要、QA、信息抽取、知识图谱都依赖它 |
| 4 | 架构演进 | 规则（Hobbs 1978）→ mention-pair 分类 + 传递闭包 → mention-ranking（含"无先行词"选项）→ span-based 端到端（Lee et al. 2017，现代默认）→ 生成式 LLM（2024+） |
| 5 | 端到端 span 模型 | 枚举长度有上限的所有候选 span → 打 mention 分 → 为每个 span 预测先行词概率 → 贪心聚类 |
| 6 | 评估指标 | MUC、B³、CEAF、BLANC、LEA；CoNLL F1 = MUC、B³、CEAF-φ4 三者 F1 的平均；讲义称 2026 年 CoNLL-2012 SOTA 约 83 F1 |
| 7 | 难例 | 远距离定指描述、桥接回指（"the wheels" → 前文的车）、中日文零形回指、后指（cataphora，代词在前） |
| 8 | LLM 共指的两种失败 | 过度合并（把指不同人的 him/her 合在一起）、长文档中静默丢 mention；需要 span 偏移校验和滑窗合并 |
| 9 | 集成模式 | 先 NER，再 coref，把共指簇合并进 NER 实体，下游看到"一个簇一个实体" |

### 核心技能（能动手做到）

- [ ] 读懂规则版共指消解器：mention 抽取（大写串、代词表、"the + 中性名词"）、一致性打分、近因打分、取最高分先行词
- [ ] 能手算任一代词对各候选先行词的 `agreement_score + recency_score`，并预测 `max` 在平局时选谁
- [ ] 能解释输出中的错误链接（`Her -> AI`、`It -> The company`），并说明"修一个规则、坏另一个例子"的现象
- [ ] 能用并查集（union-find）把两两链接转成共指簇，理解传递闭包
- [ ] 能构造让大写启发式失效的输入（句首普通词、`iPhone` 这类小写开头的专名）
- [ ] 能说出 MUC / B³ / CEAF 各自对"全部单例"系统的反应，并用 spaCy 实验模型或 LLM + 结构化输出做一个共指 baseline

---

## 二、基础自测（选择题）

**Q1.** "Tim Cook, Apple's CEO, said the company would grow." 中，"Apple's CEO" 属于哪类 mention？

- A. 代词
- B. 同位语（appositive）
- C. 零形回指
- D. 桥接回指

**Q2.** "I bought a car. The wheels were bad." 中，"The wheels" 与 "a car" 的关系是：

- A. 普通共指：两者指同一个实体
- B. 后指（cataphora）
- C. 桥接回指（bridging）：轮子不是车本身，而是前文那辆车的部件
- D. 二者毫无关系

**Q3.** 关于 Lee et al.（2017）开创的 span-based 端到端共指模型，正确的描述是：

- A. 先用句法树找候选，再用手写规则选先行词
- B. 枚举所有长度不超过上限的候选 span，打 mention 分，再为每个 span 预测先行词概率，最后贪心聚类
- C. 对每一对 mention 训练二分类器，再用传递闭包聚类
- D. 用 LLM 直接生成 JSON 格式的共指簇

**Q4.** mention-ranking 方法相比 mention-pair 方法的关键区别是：

- A. 它不需要训练
- B. 它对每个 mention 在所有候选先行词（包括"无先行词"）中**排序取最高**，而不是独立判断每一对是否共指
- C. 它只处理代词
- D. 它只能用于中文

**Q5.** 一个"偷懒"的系统把每个 mention 都输出为单独的簇（全是单例）。下列说法正确的是：

- A. 所有指标都会给它 0 分
- B. B³ 对它相对宽容，MUC 会严重惩罚它，所以要同时看多个指标
- C. MUC 对它最宽容
- D. CoNLL F1 只看 B³，所以分数很高

**Q6.** "When she walked in, Mary smiled." 中 "she" 指 Mary。这种现象叫：

- A. 回指（anaphora）
- B. 后指（cataphora）
- C. 桥接回指
- D. 零形回指

**Q7.** 用一次 LLM 调用对一份 80 段的长报告做共指，讲义提醒的风险和对策是：

- A. LLM 无法识别代词，应改用正则
- B. 容易过度合并不同人物、静默漏掉 mention；应使用滑动窗口 + 合并，并用 span 偏移校验输出
- C. 长文档会导致 tokenizer 报错
- D. 没有风险，LLM 共指在长文档上最稳定

---

## 三、动手 / 代码题

**Q8.** `main.py` 对演示文档抽取出的部分 mention 及其位置 `(句子编号, 句内 token 下标)` 如下：

```text
Tim Cook (0, 0)  [ne, m]       He (1, 0)        The company (2, 0) [nominal, n]
a laptop (2, 4) [nominal, n]   It (3, 0) [pronoun, n]
```

打分函数为：

```python
def agreement_score(mention, candidate):
    score = 0.0
    mf = mention["features"]
    cf = candidate["features"]
    if mf["number"] == cf["number"]:
        score += 1.0
    if mf["gender"] == "u" or cf["gender"] == "u" or mf["gender"] == cf["gender"]:
        score += 1.0
    else:
        score -= 2.0
    return score


def recency_score(mention, candidate):
    delta = (mention["span"][0] - candidate["span"][0]) * 2 + max(0, mention["span"][1] - candidate["span"][1]) * 0.01
    return -delta
```

1. 手算代词 `It` 对 `Tim Cook`、`The company`、`a laptop` 三个候选的总分。
2. `resolve` 用 `max(candidates, key=...)` 选先行词，最终 `It` 链接到谁？为什么？语义上应该链接到谁？
3. `recency_score` 中 `max(0, m_idx - c_idx) * 0.01` 这一项在**跨句**时有什么问题？请改写，使"同在前一句时，越靠近句尾的候选越近"。改写后 `It` 会链接到谁？

**Q9.** 程序输出 `Her -> AI`（"Her team built the voice assistant." 中的 Her 显然指 Mary Chen）。

1. `AI` 为什么会被抽成一个 mention？它的特征是什么？
2. 已知 `Her` 位于 (6, 0)，`AI` 位于 (5, 3)，`Mary Chen` 位于 (4, 0)。手算两者的得分，解释为什么 `AI` 胜出。
3. 讲义 Step 2 说打分应考虑"句法角色（主语优先）"，但代码没有实现。请给句首候选（近似主语）加 2.5 分，写出修改后的 `resolve`，并说明它对 4 个代词的链接结果有什么影响。如果把它和 Q8 的近因修复一起使用，`It` 会怎样？这说明了什么？

**Q10.** `clusters` 用并查集把链接变成簇：

```python
def clusters(mentions, links):
    parent = {id(m): id(m) for m in mentions}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for m, ant in links:
        if ant is not None:
            union(id(m), id(ant))
    groups = {}
    for m in mentions:
        root = find(id(m))
        groups.setdefault(root, []).append(m["text"])
    return list(groups.values())
```

1. 为什么用 `id(m)` 而不是 `m` 本身作为字典的 key？
2. `parent[x] = parent[parent[x]]` 这一行起什么作用？
3. 如果允许代词以**其他代词**为先行词（候选列表不再过滤 `type`），`Her` 会链接到 `She`，打印的簇会变成什么？这体现了 mention-pair 方法中的哪个步骤？

**Q11.** 不运行代码，预测 `extract_mentions("Yesterday the bank said it lost money. iPhone sales fell. They were worried.")` 会抽出哪些 mention，`resolve` 又会把 `They` 链接到谁。指出这里暴露的至少三个规则缺陷。

---

## 四、面试高频题

**Q12.**（基础必考）什么是共指消解？它和 NER、实体链接（entity linking）有什么区别与联系？为什么说它是"表层 NLP 与下游语义任务之间的胶水"？

**Q13.**（原理深挖）请讲一下共指消解模型的演进：mention-pair、mention-ranking、span-based 端到端各解决了前一代的什么问题？端到端模型的计算瓶颈在哪里、怎么缓解？

**Q14.**（原理深挖）共指评估为什么需要 MUC、B³、CEAF 等多个指标？CoNLL F1 是怎么算的？你在内部评估中会怎么做？

**Q15.**（工程实践）你打算用 LLM 做共指消解来增强一个合同信息抽取系统。会遇到哪些问题？如何设计 prompt、输出格式和校验流程？

**Q16.**（场景设计）设计一个从新闻中构建公司知识图谱的流水线，要求"Apple""the company""Cupertino's technology giant""it"最终归到同一个节点。请说明各模块的顺序、共指在其中的作用，以及如何评估。

---

## 五、参考答案与解析

### Q1 — 答案：B

同位语是紧跟在名词后、用逗号隔开、对同一实体做补充说明的名词短语。"Apple's CEO" 与 "Tim Cook" 指同一个人。讲义的四类 mention 中正好以此为例。

### Q2 — 答案：C

桥接回指的特点是：后一个 mention 与前文实体**相关**但不**相同**（部分-整体、属性等），需要常识推断"轮子是那辆车的轮子"。普通共指要求指向同一实体，所以 A 错。

### Q3 — 答案：B

Lee et al.（2017）不依赖句法分析器，直接枚举长度有上限的 span，联合学习 mention 打分和先行词打分，最后贪心聚类。A 是规则方法（Hobbs），C 是 mention-pair，D 是 2024+ 的生成式方法。

### Q4 — 答案：B

mention-pair 对每一对独立判断，可能出现"A 与 B 共指、B 与 C 共指，但 A 与 C 不共指"的矛盾，只能靠传递闭包硬合并；mention-ranking 让候选先行词彼此竞争，还显式包含"无先行词"选项，用来表示这是一个新实体的首次出现。

### Q5 — 答案：B

MUC 基于"链接"计算：全是单例意味着一个链接都没有，召回为 0。B³ 基于每个 mention 计算精确率和召回率，单例的精确率是满分，因此相对宽容。讲义 Pitfalls："B³ is lenient. MUC punishes this. Always check all three metrics." D 错：CoNLL F1 是三者的平均。

### Q6 — 答案：B

代词出现在所指实体之前，是后指（cataphora）；反过来"John arrived. He smiled." 是回指（anaphora）。讲义把后指列为已知难例——只向前找先行词的系统（包括本节的 `main.py`）天然处理不了。

### Q7 — 答案：B

讲义 Step 3 指出 LLM 的两种失败：过度合并、长文档静默丢 mention，要求"Always verify with span-offset checks"；Pitfalls 中要求 50+ 段时用滑动窗口 + 合并；skill 规定超过 2,000 token 的文档拒绝"仅用 LLM 且不做滑窗合并"的方案。

### Q8 — 参考答案

1. `It` 的特征为 `n / sg`，位于 (3, 0)：

| 候选 | 数一致 | 性别 | agreement | recency | 总分 |
|---|---|---|---|---|---|
| Tim Cook (0,0), m | +1 | n≠m → −2 | −1 | −(3×2 + 0) = −6 | **−7** |
| The company (2,0), n | +1 | +1 | 2 | −(1×2 + 0) = −2 | **0** |
| a laptop (2,4), n | +1 | +1 | 2 | −(1×2 + max(0, 0−4)×0.01) = −2 | **0** |

2. `The company` 和 `a laptop` 平分 0。`max` 遇到相同的最大值时返回**第一个**，`The company` 在列表中更靠前，所以 `It -> The company`。这是平局规则决定的，不是模型"判断"出来的。语义上，"It will ship in June" 中会"发货"的是产品，应该指 `a laptop`。程序的提示语 "neuter pronoun 'it' prefers neuter-head nominals like 'the company'" 容易让人误以为这个链接是对的。

3. 问题：`m_idx - c_idx` 比较的是**不同句子**里的句内下标，没有意义。代词通常在句首（下标 0），跨句时这一项几乎总是 0，于是前一句中所有候选的近因分相同，"越近越好"失效。改写：

```python
def recency_score(mention, candidate):
    ds = mention["span"][0] - candidate["span"][0]
    if ds == 0:                                         # 同一句：按 token 距离
        return -(mention["span"][1] - candidate["span"][1]) * 0.01
    return -ds * 2 + candidate["span"][1] * 0.01        # 跨句：越靠句尾越近
```

改写后 `a laptop` 得分 −1.96，高于 `The company` 的 −2，`It -> a laptop`，正确。但测验 Q9 会看到，这个修复会让另一个代词出错。

### Q9 — 参考答案

1. `extract_mentions` 把"首字母大写的纯字母串"都当作命名实体。`AI` 首字母大写，于是被抽成 `ne`；`infer_gender("AI")` 查不到名字表，性别为 `u`（未知），数为 `sg`。

2. `Her` 的特征为 `f / sg`：
   - `AI` (5,3)：数一致 +1；性别 `u`，规则视为兼容 +1 → agreement 2；recency −(1×2) = −2 → 总分 **0**
   - `Mary Chen` (4,0)：agreement 2；recency −(2×2) = −4 → 总分 **−2**
   
   `AI` 胜出有两个原因：①未知性别被当成和"性别匹配"一样好，得到同样的 +1；②每隔一句扣 2 分的近因惩罚压倒了一切，离得近的 `AI` 占了便宜。

3. 修改 `resolve`，给句首候选加分：

```python
def resolve(mentions, subject_bonus=2.5):
    links = []
    for i, m in enumerate(mentions):
        if m["type"] != "pronoun":
            continue
        candidates = [c for c in mentions[:i] if c["type"] in ("ne", "nominal")]
        if not candidates:
            links.append((m, None))
            continue

        def score(c):
            s = agreement_score(m, c) + recency_score(m, c)
            if c["span"][1] == 0:          # 句首 ≈ 主语
                s += subject_bonus
            return s

        best = max(candidates, key=score)
        links.append((m, best))
    return links
```

实测链接变为：`He -> Tim Cook`、`It -> The company`、`She -> Mary Chen`、`Her -> Mary Chen`，`Her` 被修好了，簇变成 `['Mary Chen', 'She', 'Her']`。

但如果同时使用 Q8 的近因修复，`It` 又回到 `The company`（`The company` 在句首，拿到主语加分）；而**只用** Q8 的近因修复时，`It` 对了，`She` 却会错链到 `Apple`（`Apple` 在 `Mary Chen` 之后、性别未知）。

这说明：手写规则的权重彼此牵制，修好一个例子往往弄坏另一个；"产品才会发货"这类**选择限制**（selectional preference）需要世界知识，规则很难表达。这正是 mention-ranking / 端到端模型用**学习**来的打分函数取代手调权重的原因。

### Q10 — 参考答案

1. mention 是字典，字典是可变对象、不可哈希，不能当 dict 的 key。`id(m)` 返回对象在内存中的唯一标识（整数），可以作 key。注意这依赖于"同一个字典对象"在 `mentions` 和 `links` 中被共享——`resolve` 返回的正是 `mentions` 里的原对象，所以 `id` 一致；如果中途对 mention 做了拷贝，链接就会失效。

2. **路径压缩（路径减半）**：在向上找根的过程中，把每个节点直接指向它的祖父节点，让树变矮，后续 `find` 更快。并查集配合路径压缩，单次操作的均摊代价接近常数。

3. 链接变成 `He -> Tim Cook`、`It -> The company`、`She -> Mary Chen`、`Her -> She`（`She` 与 `AI` 同分 0，`She` 在列表中更靠前，赢得平局）。并查集把 `Her—She` 与 `She—Mary Chen` 两条链接合并，簇为：

```text
['Tim Cook', 'He']
['The company', 'It']
['Mary Chen', 'She', 'Her']
```

`Her` 并没有直接链接到 `Mary Chen`，却通过 `She` 进入了同一簇，这就是 mention-pair 方法中的**传递闭包**聚类。它的风险也在这里：任何一条错误链接都会把两个原本独立的簇整体合并。

### Q11 — 参考答案

抽出的 mention：

| mention | 类型 | 说明 |
|---|---|---|
| `Yesterday` | ne | 句首大写的普通词被误当命名实体 |
| `the bank` | nominal | `bank` 在 `NEUTER_HEADS` 中 |
| `it` | pronoun | |
| `They` | pronoun | |

`iPhone` 没有被抽出（首字母小写），`sales` 也不是任何类型的 mention。

链接：`it -> the bank`（正确）。`They`（`u / pl`）对两个候选：`Yesterday`（sg，数不一致 +0，性别 `u` +1，近因 −4，总分 −3）与 `the bank`（sg，+0，+1，−4，总分 −3）同分，`max` 取第一个，于是 **`They -> Yesterday`**——荒谬的结果。

暴露的缺陷：
1. **大写启发式**：句首普通词（Yesterday）被误抽，小写开头的专名（iPhone、eBay）被漏抽；
2. **没有复数候选**：抽取规则只产生单数 mention，`They` 永远找不到数一致的先行词；
3. **没有"无先行词"选项**：只要有候选就必须选一个，哪怕得分很低（mention-ranking 方法会把"新实体"作为一个候选）；
4. **平局靠列表顺序**：结果依赖 mention 出现顺序，而不是语言学依据。

### Q12 — 参考回答要点

- **共指消解**：把文档中所有指向同一实体的 mention（专名、名词短语、代词、同位语）聚成簇。
- **与 NER 的区别**：NER 识别"哪些片段是实体、是什么类型"，但不知道 "Apple""the company""it" 是同一个东西；共指负责把它们连起来。讲义：不做共指，NER 会漏掉 60–80% 的提及。
- **与实体链接的区别**：实体链接把 mention 映射到知识库中的条目（如 Wikidata ID）；共指只在文档内部聚类，不需要知识库。二者常配合：先共指成簇，再对整个簇做实体链接，信息更充分。
- **"胶水"**：摘要需要把"the CEO"换成具体人名，QA 需要解析"she"，信息抽取/知识图谱需要避免"PER1 founded Apple"和"Jobs founded Apple"成为两条记录，跨文档共指则把多篇报道里的同一事件合并。
- 加分点：讲义的集成模式——NER → coref → 把共指簇合并进 NER 实体。

### Q13 — 参考回答要点

- **Mention-pair**：对每对 mention 做二分类，再用传递闭包聚类。问题：各对决策独立，可能互相矛盾；正负样本极不平衡；聚类阶段错误会放大。
- **Mention-ranking**：对每个 mention，在所有候选先行词（含"无先行词"）中排序取最高。候选之间相互竞争，"新实体"被显式建模。仍依赖外部的 mention 检测。
- **Span-based 端到端（Lee et al. 2017）**：把 mention 检测与先行词选择**联合学习**——枚举长度有上限的所有 span，打 mention 分，剪枝后对保留的 span 计算先行词分数，贪心聚类。避免了流水线误差传播；后续工作用 SpanBERT 等更强的预训练编码器进一步提升（讲义延伸阅读）。
- **计算瓶颈**：候选 span 数约为 `文档长度 × 最大 span 长度`，候选对数是它的平方。缓解：限制 span 最大长度、按 mention 分剪枝只保留一定比例、限制每个 span 只考虑最近的若干候选先行词、长文档分段处理。
- **生成式（2024+）**：直接让 LLM 输出簇；简单场景效果好，长文档、罕见指称难以保证（见 Q15）。

### Q14 — 参考回答要点

- **为什么多指标**：共指是聚类评估，没有单一"正确率"。不同指标关注点不同：
  - **MUC**：基于链接，衡量需要增删多少条链接；不奖励单例，全单例系统召回为 0；
  - **B³**：基于 mention，对每个 mention 计算其所在簇的精确率/召回率再平均；对单例宽容；
  - **CEAF**：先在预测簇与金标准簇之间做最优对齐再算相似度；CoNLL 用 entity 版本 CEAF-φ4；
  - BLANC、LEA 是后来提出的补充指标。
- **CoNLL F1** = (MUC F1 + B³ F1 + CEAF-φ4 F1) / 3，由 CoNLL-2012 官方脚本计算。
- **内部评估**（讲义 Step 4 + skill）：先报告 mention 检测的 span 级精确率/召回率，再报告链接 F1 / CoNLL F1；再对约 20 篇文档做人工簇审查；长文档（> 2,000 token）单独分桶，讲义提到这类文档上性能会下降约 15 F1。
- 常见误区：只报 B³；不报 mention 检测的召回，导致"簇看起来很准，但大量 mention 根本没被找到"。

### Q15 — 参考回答要点

- **问题**：
  1. 过度合并：把指不同当事人的代词合到一起（合同里"甲方""乙方""其"尤其容易混）；
  2. 静默丢 mention：长合同中后半部分的指代没有输出；
  3. 输出的 mention 文本在原文中找不到或重复出现，无法定位；
  4. 跨窗口时同一实体在不同窗口中被命名成不同的簇。
- **设计**：
  - prompt 中明确要求为每个 mention 输出**字符偏移**（或段落号 + 原文片段），并用结构化输出约束 JSON 格式（参见第 20 节）；
  - 文档超过约 2,000 token 时按滑动窗口切分（窗口之间有重叠），每个窗口独立做共指，再用重叠区域中的共享 mention 合并跨窗口的簇；
  - 先跑 NER 给出候选实体列表，让 LLM 在给定实体集合上做归属，降低自由生成的随意性。
- **校验**：偏移处的原文必须与 mention 文本完全一致；每个 NER 实体都必须出现在某个簇里（覆盖率检查）；性别/数明显冲突的合并要标记；关键条款中的指代（如付款方、违约方）走人工复核（讲义 Use It："manual review for critical slots"）。
- **评估**：在标注集上报告 mention 级精确率/召回率和 CoNLL F1，与 spaCy 实验模型等神经 baseline 对比。

### Q16 — 参考回答要点

1. **预处理**：分句、分词、解析结构。
2. **NER**：识别 ORG/PER/LOC 等实体（第 06 节）。
3. **单文档共指**：把 "Apple""the company""Cupertino's technology giant""it" 聚成一簇；选簇中信息量最大的命名 mention（如 "Apple"）作为簇的代表名。讲义推荐英文单文档用 `en_coreference_web_trf`（spaCy-experimental）等神经模型。
4. **簇合并进 NER**：下游每个簇只看到一个实体（讲义的 2026 集成模式）。
5. **实体链接**：以簇为单位链接到知识库 ID，簇中所有 mention 的上下文共同参与消歧（第 25 节）。
6. **关系抽取**：在代词已被消解的文本上抽取关系，"it acquired X" 能正确落到 Apple 上（第 26 节）。
7. **跨文档合并**：按知识库 ID 合并节点；没有链接上的实体用跨文档共指模型或名称 + 上下文相似度合并。
- **评估**：共指用 CoNLL F1 + mention 级 P/R；端到端看实体覆盖率（相对只用 NER 提升多少——对应讲义练习 3）、重复节点率、抽样人工审查图谱中的边。
- 加分点：提到 "Cupertino's technology giant" 这类描述性 mention 需要世界知识，是规则方法做不到、神经/LLM 方法的优势所在。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 06 命名实体识别](../../06-named-entity-recognition/docs/zh.md)：共指的 mention 很大一部分来自 NER。
- [阶段 05 · 07 词性标注和句法分析](../../07-pos-tagging-parsing/docs/zh.md)：规则方法（Hobbs）依赖句法树，主语/宾语等句法角色是重要特征。

### 本节被哪些后续内容用到
- [阶段 05 · 25 实体链接和消歧](../../25-entity-linking/docs/zh.md)：以共指簇为单位链接到知识库。
- [阶段 05 · 26 关系抽取与知识图谱构建](../../26-relation-extraction-kg/docs/zh.md)：消解代词后，关系才能挂到正确的实体上。
- [阶段 05 · 21 自然语言推理](../../21-nli-textual-entailment/docs/zh.md)：拆分原子论断做 faithfulness 检查时，需要先消解代词。
- [阶段 05 · 23 面向 RAG 的 Chunking 策略](../../23-chunking-strategies-rag/docs/zh.md)：chunk 中的代词失去先行词，是 contextual retrieval / late chunking 要解决的问题。
- [阶段 05 · 29 对话状态跟踪](../../29-dialogue-state-tracking/docs/zh.md)：多轮对话中的"它""那个"指代需要消解。
- [阶段 05 · 12 文本摘要](../../12-text-summarization/docs/zh.md) 与 [阶段 05 · 13 问答系统](../../13-question-answering/docs/zh.md)：讲义列举的两个直接受益任务。

### 延伸关键词
`mention detection` · `antecedent` · `anaphora / cataphora` · `bridging anaphora` · `zero anaphora` · `mention-pair / mention-ranking` · `span-based end-to-end` · `SpanBERT` · `OntoNotes / CoNLL-2012` · `MUC / B³ / CEAF-φ4 / LEA` · `cross-document coreference` · `selectional preference`
