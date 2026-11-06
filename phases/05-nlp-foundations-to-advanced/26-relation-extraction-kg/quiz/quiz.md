# 测验 · 关系抽取与知识图谱构建（Relation Extraction & Knowledge Graph Construction）

> **阶段 05 · NLP 基础到进阶 · 第 26 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三元组（triple） | `(subject, relation, object)` 是知识图谱（KG）的原子单位；KG = 节点 + 边 + 出处（provenance） |
| 2 | 三类抽取方法 | 规则 / 模式（Hearst 模式 + 正则，精确、可解释、脆弱）→ 监督分类器（TACRED / ACE / KBP，2015–2022 主流）→ 生成式 LLM（开箱即用，但会幻觉） |
| 3 | REBEL | seq2seq 关系抽取模型：输入文本，直接输出三元组，关系已经是 Wikidata 属性 id；在远程监督数据上训练，是开源权重的标准 baseline |
| 4 | 远程监督（distant supervision） | 把文本和已有 KG 对齐，自动产生训练标签；便宜但有噪声 |
| 5 | LLM 幻觉三元组 | LLM 会"热情地"抽出原文不支持的三元组；没有出处就分不清真实三元组和"看起来合理的虚构" |
| 6 | AEVS | Anchor（锚定实体和关系短语的精确位置）→ Extract（抽取并关联锚点）→ Verify（逐元素回查原文，拒绝无依据者）→ Supplement（覆盖性补漏） |
| 7 | Provenance（出处） | 每个三元组携带文档 id + 字符 span；最小形式的校验就是 `text[start:end] == 实体文本` |
| 8 | 封闭本体 vs Open IE | 封闭本体（Wikidata 11,000+ 属性、UMLS、FIBO）可预测、可查询；Open IE 召回高、精度低、难查询；生产常用"Open IE 发现 → 规约到封闭本体" |
| 9 | 规范化（canonicalization） | 关系规范化（"was born in / came from / is a native of" → P19）+ 实体规范化（"Apple Inc" 与 "Apple" 是同一节点，靠 EL）；常占 60–80% 的工程量 |
| 10 | 时间限定与集成流水线 | 雇主、配偶、职位等关系有时效，用 P580 / P582（开始 / 结束时间）限定；集成顺序：NER → 共指 → EL → RE → 本体映射 → 入图 |

### 核心技能（能动手做到）

- [ ] 能写出基于正则捕获组的关系抽取器，并为每个三元组记录 `span` 和 `evidence`
- [ ] 能预测正则模式在多词人名、代词、动词变形、连字符名字上会怎样出错，并说出对应的上游修复（NER / 共指 / 词形还原）
- [ ] 能实现 span 校验，并构造一个"能骗过宽松校验"的幻觉三元组，再写出更严格的版本
- [ ] 能把关系映射到 Wikidata 属性，并处理 P112（founded by）、P169（chief executive officer）这类"主宾方向与英文动词相反"的属性
- [ ] 能用邻接表构建图，同时支持按主语和按宾语的查询
- [ ] 能设计"要求输出 span 的 LLM 抽取 prompt + 校验"流程，并统计校验前后的幻觉率

---

## 二、基础自测（选择题）

**Q1.** 对句子 "fruits such as apples and pears"，Hearst 模式 "X such as Y" 应该抽出：

- A. `(fruits, isA, apples)`
- B. `(apples, isA, fruits)`
- C. `(apples, such_as, fruits)`
- D. `(fruits, partOf, apples)`

**Q2.** 关于 Open IE 与封闭本体（closed ontology），下列说法正确的是：

- A. Open IE 精度高、召回低，适合直接写入生产图谱
- B. 封闭本体的关系集合固定、可预测、便于查询，但新关系无法表达，需要扩展本体
- C. 生产中通常只用 Open IE，因为它不需要任何后处理
- D. 封闭本体会让 LLM 更容易编造关系

**Q3.** 用 AEVS 流水线处理 "Larry Page founded Google with Sergey Brin."：Anchor 阶段锚定了 `Larry Page`、`Google`、`Sergey Brin` 三个实体 span，但 Extract 阶段只产出了 `(Larry Page, founded, Google)`。负责发现并补上 "Sergey Brin" 相关三元组的是哪一步？

- A. Anchor
- B. Extract
- C. Verify
- D. Supplement

**Q4.** 关于远程监督（distant supervision），下列说法**错误**的是：

- A. 它把已有 KG 中的事实与文本对齐来自动生成训练标签
- B. 典型做法：一个句子同时出现了 KG 中有关系的两个实体，就把该句标为这个关系
- C. 噪声来源之一是句子虽然同时提到两个实体，却并不表达这个关系（如 "Steve Jobs returned to Apple" 被标成 founded）
- D. 因为标签来自权威 KG，所以远程监督数据没有噪声，可以直接当金标准

**Q5.** 2015 年的新闻写道 "Tim Cook is CEO of Apple"。把它写入图谱时，最合理的建模方式是：

- A. 写入 `(Tim Cook, CEO of, Apple)`，永远为真
- B. 写入该事实，并加上开始时间（P580）等时间限定，必要时补结束时间（P582），同时保留出处
- C. 时效性关系一律不入图
- D. 在节点名里加年份，如 `Tim Cook 2015`

**Q6.** 讲义推荐的集成顺序是 NER → 共指 → EL → RE → 本体映射 → 入图。如果跳过 EL，最直接的后果是：

- A. 抽取速度大幅下降
- B. "Apple Inc" 和 "Apple" 变成两个节点，水果 apple 和苹果公司也可能被合并成同一个节点，图谱无法正确查询
- C. 关系无法映射到 Wikidata 属性
- D. 代词无法消解

**Q7.** 关于 REBEL，下列说法正确的是：

- A. 它是一个给定实体对、从固定标签集中选关系的分类器
- B. 它是 seq2seq 模型，输入文本、直接生成三元组，关系用 Wikidata 属性 id 表示；训练数据来自远程监督，换到法律、医疗等领域时常需要领域微调
- C. 它是一个基于 Hearst 模式的规则系统
- D. 它只做 Open IE，不输出规范化的关系

---

## 三、动手 / 代码题

**Q8.** 本节 `code/main.py` 的部分模式如下：

```python
PATTERNS = [
    (re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) was born in ([A-Z][A-Za-z]+)"), "P19"),
    (re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) founded ([A-Z][A-Za-z]+(?: Inc)?)"), "P112"),
    (re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) (?:became|is|was) CEO of ([A-Z][A-Za-z]+(?: Inc)?)"), "P169"),
    (re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) works? (?:at|for) ([A-Z][A-Za-z]+(?: Inc)?)"), "P108"),
    (re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) (?:studied|graduated) (?:at|from) ([A-Z][A-Za-z]+(?: University)?)"), "P69"),
    # ...
]
```

对下面这段文本调用 `extract(text)`，会得到哪些 `(subject, relation, object)`？逐条说明哪些是错的、错在哪、应该由流水线的哪一环修复。

```python
text = ("Mark Elliot Zuckerberg founded Facebook. "
        "He founded Meta Platforms Inc in 2021. "
        "Jensen Huang worked at LSI Logic. "
        "Fei-Fei Li studied at University of Illinois.")
```

**Q9.** 本节的校验函数如下：

```python
def verify(triples, text):
    verified = []
    for t in triples:
        s, e = t["span"]
        if text[s:e] != t["evidence"]:
            continue
        if t["subject"] not in text or t["object"] not in text:
            continue
        verified.append(t)
    return verified
```

1. 在 `main()` 中，`extracted: 8  verified: 8`。为什么对规则抽取来说这个校验几乎一定全部通过？
2. 假设 LLM 对 `main()` 里的 `doc` 返回了下面这个三元组，它能通过 `verify` 吗？为什么？

```python
{"subject": "Tim Cook", "relation": "P169", "object": "Google",
 "span": (0, 28), "evidence": "Tim Cook became CEO of Apple"}
```

3. 写一个更严格的 `verify_strict`，拒绝上面这个幻觉三元组，同时让 `doc` 中原有的 8 个三元组全部通过。

**Q10.** 在 Wikidata 中，P112 是 "founded by"、P169 是 "chief executive officer"，它们的主语是**组织**、宾语是**人**；而本节代码把 `(Steve Jobs, P112, Apple)`、`(Tim Cook, P169, Apple)` 这样写入图谱，方向与 Wikidata 相反。另外，`build_graph` 只按主语建索引，"谁是 Google 的 CEO？"这种问题查不了。请写：

1. `to_wikidata(t)`：把 P112、P169 的三元组反转成 Wikidata 方向，返回 `(s, r, o)` 元组；
2. `build_index(triples)`：同时返回出边索引 `out_edges[s] → [(r, o)]` 和入边索引 `in_edges[o] → [(r, s)]`；
3. 用它们回答"谁是 Google 的 CEO"，并写出 `out_edges["Google"]` 的内容。

---

## 四、面试高频题

**Q11.**（基础必考）什么是关系抽取？对比规则、监督分类、生成式 LLM 三种方法在精度、召回、成本、可解释性上的取舍。

**Q12.**（原理深挖）LLM 做关系抽取时会出现哪些幻觉？AEVS 的四步分别解决什么问题？你会怎么量化"幻觉率"？

**Q13.**（工程实践）为什么讲义说规范化（canonicalization）常常占 60–80% 的工程量？关系规范化和实体规范化分别怎么做？

**Q14.**（场景设计）合规部门要从每天上万篇新闻和公告中构建"公司—高管—投资—收购"知识图谱，用于审计和 KG-RAG 问答。请设计端到端方案，包括抽取器选择、本体、出处、合并去重、时间限定、评估和存储。

**Q15.**（追问型）"既然有向量检索 RAG，为什么还要费劲建知识图谱？"——请说明 KG 在哪些问题上有优势、代价是什么，以及什么情况下不值得建。

---

## 五、参考答案与解析

### Q1 — 答案：B

Hearst 模式 "X such as Y" 表达的是"Y 是一种 X"，所以是 `(Y, isA, X)` = `(apples, isA, fruits)`（"and pears" 还能再抽出 `(pears, isA, fruits)`）。A 把上下位关系方向弄反了；C 把表面短语当成关系，没有规范化；D 是部分—整体关系，语义不对。

### Q2 — 答案：B

封闭本体的关系集合固定（如 Wikidata 的 11,000+ 属性），可预测、可查询，也不容易被"发明"出新关系；代价是表达力受限，新关系需要扩展本体。A 说反了：Open IE 是**召回高、精度低**，而且混乱、难以查询。C 错在 Open IE 输出必须规范化后才能入生产图谱，讲义的做法是"Open IE 发现 → 规约到封闭本体"。D 也说反了：封闭本体限制了输出空间，反而让编造更难。

### Q3 — 答案：D

Supplement 是**覆盖性补漏**：检查每个锚定的 span 是否都被某个三元组用到，发现 "Sergey Brin" 被遗漏后再补抽 `(Sergey Brin, founded, Google)`。Anchor 负责标出 span；Extract 负责生成三元组；Verify 负责拒绝原文不支持的三元组（提高精度），不负责补召回。

### Q4 — 答案：D

A、B 是远程监督（Mintz et al. 2009）的定义和典型做法，C 是它最主要的噪声来源："两个实体同时出现"不等于"句子表达了这个关系"。D 错：KG 事实本身可靠，不代表"对齐到的句子"可靠，远程监督数据是出了名的有噪声，需要多实例学习、降噪等方法处理。REBEL 正是在这类数据上训练的，所以换领域时需要谨慎评估。

### Q5 — 答案：B

雇主、职位、配偶等是**有时效的关系**："Tim Cook is CEO of Apple" 现在为真，2005 年为假。讲义的做法是用 Wikidata 的限定符 P580（开始时间）/ P582（结束时间）标注时间范围，同时保留出处，以便审计"这条事实是从哪篇文章、什么时间点得出的"。A 会让事实悄悄过期；C 丢失了大量有价值的信息；D 把时间编码进实体名，破坏了实体规范化。

### Q6 — 答案：B

EL 负责**实体规范化**：把不同写法（"Apple Inc"、"Apple"）映射到同一个 KB id，也把同名不同实体（水果 apple 和苹果公司）分开。跳过 EL，图谱会出现重复节点和错误合并，查询结果残缺或混淆。C 是关系规范化的问题；D 是共指消解的职责。

### Q7 — 答案：B

REBEL（Relation Extraction By End-to-end Language generation）是 seq2seq 模型：文本输入、三元组序列输出，关系直接用 Wikidata 属性表示，训练数据来自远程监督。讲义在陷阱部分指出它在 Wikipedia 上训练，法律、医疗、科研文本常需要领域微调的 RE 模型。A 描述的是"监督关系分类器"（TACRED 范式）。

### Q8 — 参考答案

实际运行结果（只列出 subject / relation / object；`extract` 按 `PATTERNS` 的顺序遍历，所以 P112 的结果排在前面）：

```text
Elliot Zuckerberg  P112  Facebook
He                 P112  Meta
Fei Li             P69   University
```

逐条分析：

| 句子 | 结果 | 问题 | 修复环节 |
|------|------|------|---------|
| Mark Elliot Zuckerberg founded Facebook | `(Elliot Zuckerberg, P112, Facebook)` | 主语模式最多匹配**两个**大写词。从 "Mark" 开始匹配 "Mark Elliot" 后紧跟的是 " Zuckerberg" 而不是 " founded"，失败；引擎右移到 "Elliot"，匹配成功，**边界错误** | 用 NER 的人名 span 代替正则猜边界 |
| He founded Meta Platforms Inc in 2021 | `(He, P112, Meta)` | ① 代词 "He" 首字母大写，被当成实体，入图后会出现一个叫 "He" 的节点；② 宾语模式只允许"一个词 + 可选 Inc"，"Meta Platforms Inc" 被截成 "Meta" | ① 先做共指消解（He → Zuckerberg）；② 用 NER span，再用 EL 规范化到 Meta 的 KB id |
| Jensen Huang worked at LSI Logic | 无输出 | `works?` 只匹配 work / works，不匹配 worked（**动词变形**），召回丢失 | 词形还原后再匹配，或改用监督 / LLM 抽取 |
| Fei-Fei Li studied at University of Illinois | `(Fei Li, P69, University)` | ① `[A-Za-z]` 不含连字符，"Fei-Fei" 被切断；② "University of Illinois" 只匹配到 "University" | NER span + EL |

结论：规则抽取"精度高"的前提是边界正确。真实文本中，人名长度、代词、时态、标点都会让正则失效，这正是讲义坚持 NER → 共指 → EL 放在 RE 之前的原因。

### Q9 — 参考答案

**1.** 规则抽取时，`span = (m.start(), m.end())`，`evidence = m.group(0)`，两者来自**同一次正则匹配、同一份文本**，所以 `text[s:e] == evidence` 恒成立；`subject` 和 `object` 是匹配到的子串，必然出现在 `text` 中。因此 `verify` 对规则输出是"走过场"。它真正的用途是作为校验 **LLM 输出**的模板，因为 LLM 返回的 span 和文本都可能是编造的。

**2.** **能通过**。`doc[0:28]` 正好是 `"Tim Cook became CEO of Apple"`，与 evidence 一致；"Tim Cook" 在全文中出现；"Google" 也在全文中出现（在别的句子里）。问题在于第二个检查用的是**整篇文本**而不是 evidence：只要实体在文档的任何位置出现过就算通过，无法发现"把 Apple 换成 Google"这种张冠李戴的幻觉。

**3.** 参考实现：要求主语和宾语都出现在 evidence span 内。

```python
def verify_strict(triples, text):
    out = []
    for t in triples:
        s, e = t["span"]
        ev = t["evidence"]
        if text[s:e] != ev:                      # 证据必须原样出现在原文对应位置
            continue
        if t["subject"] not in ev or t["object"] not in ev:   # 实体必须在证据里
            continue
        out.append(t)
    return out
```

实际验证：`verify_strict([fake], doc)` 返回 `[]`，`len(verify_strict(extract(doc), doc))` 为 8。

更进一步（AEVS 的 Anchor 思路）：让主语、宾语**各自**携带 `[start, end]`，校验 `text[s_start:s_end] == subject` 且两个 span 都落在 evidence span 内。这样还能避免子串误匹配（比如 "Meta" 是 "Metadata" 的子串）。

### Q10 — 参考答案

```python
from collections import defaultdict

INVERSE = {"P112", "P169"}      # Wikidata 中主语是组织、宾语是人的属性


def to_wikidata(t):
    if t["relation"] in INVERSE:
        return (t["object"], t["relation"], t["subject"])
    return (t["subject"], t["relation"], t["object"])


def build_index(triples):
    out_edges = defaultdict(list)
    in_edges = defaultdict(list)
    for t in triples:
        s, r, o = to_wikidata(t)
        out_edges[s].append((r, o))
        in_edges[o].append((r, s))
    return out_edges, in_edges


out_e, in_e = build_index(verify(extract(doc), doc))
print(out_e["Google"])
print([o for r, o in out_e["Google"] if r == "P169"])
```

实际输出：

```text
[('P112', 'Larry Page'), ('P169', 'Sundar Pichai')]
['Sundar Pichai']
```

要点：

- 关系方向是本体的一部分。讲义 Step 4 的注释已经提醒 "founded → P112 (founded by)" 需要交换主宾，P169 同理。方向错了，用 SPARQL 查 `?company wdt:P169 ?ceo` 会一无所获。
- 只按主语建索引的图，只能回答"X 的 Y 是什么"，回答不了"谁是 Y 的 X"。图数据库（Neo4j、RDF triple store）默认支持双向遍历，就是因为维护了类似的入边索引。
- 更好的做法是在规范化阶段一次性把方向转好，图里只存一种方向；查询层再提供"反向属性"的便捷视图。

### Q11 — 参考回答要点

- **定义**：从非结构化文本中抽取 `(subject, relation, object)` 三元组；在全语料上聚合得到知识图谱，可用于 RAG、分析、合规审计。
- **三种方法对比**：

| 方法 | 精度 | 召回 | 成本 | 可解释性 | 典型场景 |
|------|------|------|------|---------|---------|
| 规则 / Hearst 模式 | 高（边界正确时） | 低 | 人工写规则，运行极便宜 | 最好，可逐条调试 | 领域流水线、高吞吐新闻抽取的一部分 |
| 监督分类（TACRED / ACE / KBP） | 中高 | 中 | 需要标注数据 | 中 | 固定关系集合、2015–2022 主流 |
| seq2seq / LLM（REBEL、prompt） | 不加约束时偏低（幻觉） | 高 | 推理成本高 | 差，需要靠出处补齐 | 冷启动、长尾关系、配合 AEVS 审计 |

- **加分点**：生产中常用混合方案（讲义的"pattern + supervised hybrid"），并把每一环当作质量闸门；无论用哪种抽取器，都要先有 NER、共指、EL 打底。

### Q12 — 参考回答要点

- **幻觉类型**：原文没提的关系（基于世界知识"补全"，如从 "Tim Cook became CEO of Apple" 推出 `(Tim Cook, born in, Alabama)`）；张冠李戴（实体或关系错配到别的句子）；过度推理（"stated" 与 "implied" 不分）；编造 span。
- **AEVS 四步**：
  - **Anchor**：先标出所有实体 span 和关系短语 span 的精确位置，给后续步骤提供"只能从这里选"的锚点；
  - **Extract**：生成的三元组必须引用锚点；
  - **Verify**：把三元组的每个元素回查原文，不匹配就拒绝，用来提高精度；
  - **Supplement**：检查是否有锚点没被任何三元组覆盖，补抽，用来挽回召回。
  - 代价是更多的计算，换来的是可审计性。
- **量化幻觉率**：抽一批 LLM 抽取结果（讲义建议在 200 条人工标注三元组上算 P/R），人工判断"原文是否支持"，幻觉率 = 不被支持的三元组数 / 总数；对比 verify 前后的幻觉率和召回率（讲义 Hard 练习）。
- **常见误区**：只在 prompt 里写 "Only include triples fully supported by the text" 就以为解决了幻觉。prompt 约束只是软约束，必须有程序化的 span 校验。

### Q13 — 参考回答要点

- **为什么占大头**：抽取模型可以直接拿现成的，但"同一个意思的 N 种说法"和"同一个实体的 N 种写法"必须合并成唯一 id，否则图谱无法查询。这一步高度依赖领域本体，长尾多、需要人工审核，还要随数据持续维护（关系规范化漂移）。
- **关系规范化**：
  - 映射表（讲义 `RELATION_MAP`：surface phrase → Wikidata 属性），注意主宾方向（P112、P169 需要反转）；
  - 对未映射的短语做 embedding 聚类，把聚类结果交给人工打标签，扩充映射表；
  - 用 LLM 在**封闭候选集合**内做选择题（受约束输出），映射不上的返回 None，进入人工审核队列，不能直接入图。
- **实体规范化**：依赖第 25 节的 EL：别名索引 + 消歧 → 规范 KB id；KB 外的实体走 NIL → 新实体创建流程。
- **加分点**：给每条映射记录版本，本体变更时可以回放；用"未映射关系占比"作为监控指标。

### Q14 — 参考回答要点

1. **抽取器**：高频、句式固定的关系（任命、收购公告）用规则 + 监督模型，保证精度和吞吐；长尾关系用 LLM + AEVS（锚定 → 抽取 → span 校验 → 补漏）。
2. **本体**：封闭本体，可以基于 Wikidata 属性子集（P169 CEO、P108 雇主、P127 / P1830 所有权等）加上领域扩展（如 FIBO 金融本体）；Open IE 只用于发现新关系类型，经人工审核后再加入本体。
3. **前置步骤**：NER → 共指（"该公司""他"）→ EL（公司、人到规范 id，KB 外实体走 NIL 流程）。
4. **出处**：每个三元组带 doc id + 字符 span + 抽取器版本 + 抽取时间，这是合规审计的硬性要求（讲义：non-negotiable）。
5. **合并与去重**：以 `(规范实体 id, 关系 id, 规范实体 id, 时间限定)` 为键去重；同一事实的多个来源合并为多条 provenance；冲突事实（不同来源给出不同 CEO）保留并按时间、来源可信度裁决。
6. **时间限定**：任职、持股等关系必须带 P580 / P582；新闻发布时间作为 point-in-time 的兜底。
7. **评估**：200 条人工标注三元组上的 P / R；LLM 抽取样本的幻觉率；每周抽检；监控未映射关系比例。
8. **存储与查询**：属性图（Neo4j）或 RDF triple store（Blazegraph、Virtuoso），支持多跳查询；KG-RAG 时把检索到的子图连同出处一起交给 LLM。
- **加分点**：讲义 skill 文件中的三条红线——LLM 抽取必须做 span 校验；Open IE 输出未经规范化不得进入生产图谱；时效性关系必须有时间限定。

### Q15 — 参考回答要点

- **KG 的优势**：
  - **多跳与结构化查询**：如"所有被 X 收购的公司的现任 CEO"，向量检索很难一次召回所有分散在不同文档里的事实；
  - **聚合与计数**：如"2022 年完成收购的公司有多少家"；
  - **可审计**：每条边都有出处，可以回溯到原句；
  - **一致性**：实体、关系都是规范 id，去重后不会出现"同一事实的 5 个相似 chunk"。
- **代价**：构建流水线长（NER / 共指 / EL / RE / 规范化），规范化工作量大，需要持续维护本体和刷新；抽取错误会被固化进图里。
- **不值得建的情况**：问题以开放式语义问答为主、很少多跳；数据量小、变化快；没有人力维护本体。这些情况下向量 RAG 足够，或者只对关键实体子集建轻量图。
- **加分点**：两者可以结合，比如用图做实体级召回和多跳扩展，再用向量检索补充原文段落（讲义提到的 "vector-augmented graph stores"）。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 06 命名实体识别](../../06-named-entity-recognition/docs/zh.md)：提供实体 span，正则猜边界很容易出错。
- [阶段 05 · 24 共指消解](../../24-coreference-resolution/docs/zh.md)："He founded Apple" 中的 He 需要先消解。
- [阶段 05 · 25 实体链接和消歧](../../25-entity-linking/docs/zh.md)：实体规范化，让 "Apple Inc" 与 "Apple" 落到同一个节点。
- [阶段 01 · 21 图论](../../../01-math-foundations/21-graph-theory/docs/zh.md)：邻接表、有向图、多跳遍历。

### 本节被哪些后续内容用到
- [阶段 05 · 20 Structured Outputs & 约束解码](../../20-structured-outputs-constrained-decoding/docs/zh.md)：让 LLM 按 JSON schema 输出带 span 的三元组，关系字段限定为本体内的枚举值。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../27-llm-evaluation-frameworks/docs/zh.md)：幻觉率、faithfulness 等指标的系统化评估。
- [阶段 11 · 03 结构化输出](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：工程上落地受约束的抽取输出。
- [阶段 11 · 07 高级 RAG](../../../11-llm-engineering/07-advanced-rag/docs/zh.md)：在检索之外引入结构化知识的进阶 RAG 方案。

### 延伸关键词
`TACRED` · `DocRED（文档级 RE）` · `Joint entity-relation extraction` · `SPARQL` · `RDF / 属性图` · `Wikidata qualifiers` · `知识图谱补全（KGC）` · `GraphRAG` · `多实例学习（MIL）`
