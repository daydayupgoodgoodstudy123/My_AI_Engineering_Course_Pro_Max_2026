# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到进阶 · 第 26 节 关系抽取与知识图谱构建 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`re`、`collections.defaultdict`）

---

## 1. 这份代码在考察什么

这是一个**带出处（provenance）的规则式关系抽取器**，用不到 100 行代码走完"文本 → 三元组 → 校验 → 图 → 查询"的全过程：

1. **规则抽取**：用 6 条正则模式把 "X was born in Y"、"X founded Y" 等句式变成 `(subject, relation, object)`。
2. **关系规范化**：模式直接输出 Wikidata 属性 id（P19、P112、P169 等），而不是自由短语，演示"封闭本体"的做法。
3. **出处**：每个三元组都带字符 `span` 和原文 `evidence`，这是讲义 AEVS 中 Verify 步骤的前提。
4. **校验**：`verify` 是"回查原文、拒绝无依据三元组"的最小实现，为将来接入 LLM 抽取预留接口。
5. **建图与查询**：用邻接表把三元组组织成图，按关系过滤做一次简单查询，这就是讲义说的"KG-RAG 的原子操作"。

> 一句话：**规则抽取 = 高精度、低召回、完全可解释**。先把"带出处的三元组"这个数据结构做对，后面换成 REBEL 或 LLM 时，校验和建图部分可以原样复用。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PATTERNS` | 模块级列表 `[(编译后的正则, 关系 id)]` | 6 条句式模板，每条对应一个 Wikidata 属性 | 规则 / 模式抽取、封闭本体 |
| `RELATION_LABELS` | 模块级字典 | 关系 id → 人类可读的标签 | 本体中的属性名 |
| `extract(text)` | 函数 | 逐模式 `finditer`，产出带 span / evidence 的三元组字典 | Extract（+ 粗粒度 Anchor） |
| `verify(triples, text)` | 函数 | 回查 span 与实体是否真实存在于原文 | AEVS 的 Verify |
| `build_graph(triples)` | 函数 | 主语 → `[(关系, 宾语, 证据)]` 的邻接表 | 知识图谱存储 |
| `print_graph(graph)` | 函数 | 按主语字母序打印每条边及其证据 | 可审计的输出 |
| `main()` | 函数 | 8 句话的文档 → 抽取 → 校验 → 建图 → 查询 | 端到端演示 |

数据流：`doc → extract → verify → build_graph → print_graph / 查询`。

---

## 3. 逐段精讲

### 3.1 `PATTERNS`：正则 = 手写的关系模板

```python
PATTERNS = [
    (re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) was born in ([A-Z][A-Za-z]+)"), "P19"),
    (re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) founded ([A-Z][A-Za-z]+(?: Inc)?)"), "P112"),
    (re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) (?:became|is|was) CEO of ([A-Z][A-Za-z]+(?: Inc)?)"), "P169"),
    (re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) works? (?:at|for) ([A-Z][A-Za-z]+(?: Inc)?)"), "P108"),
    (re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) (?:studied|graduated) (?:at|from) ([A-Z][A-Za-z]+(?: University)?)"), "P69"),
    (re.compile(r"([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) (?:acquired|bought) ([A-Z][A-Za-z]+(?: Inc)?)"), "P1830"),
]
```

拆开一条来看：

| 片段 | 含义 |
|------|------|
| `([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?)` | **捕获组 1 = 主语**：一个大写开头的词，可选再跟一个大写开头的词（最多两个词，覆盖 "Tim Cook" 这类两词人名） |
| `(?:became|is|was)` | 非捕获组，多个触发词任选其一，不占用组号 |
| `works?` | `s?` 表示 s 可有可无，匹配 work / works |
| `([A-Z][A-Za-z]+(?: Inc)?)` | **捕获组 2 = 宾语**：一个大写词，可选后缀 " Inc"（或 " University"） |

设计要点：

- **关系 id 直接写在模式旁边**：抽取的同时完成了关系规范化，输出就是封闭本体里的属性，省掉了讲义 Step 4 的 `RELATION_MAP` 映射。
- **`re.compile` 预编译**：模块加载时编译一次，`extract` 每次调用时直接复用。
- **"大写开头"是一个廉价的 NER 替身**：用首字母大写来猜实体边界。这正是规则抽取"脆弱"的根源：
  - ⚠️ 三词人名 "Mark Elliot Zuckerberg" 只会匹配到 "Elliot Zuckerberg"（正则从左往右尝试，"Mark Elliot" 后面不是触发词，于是右移一位重试）；
  - ⚠️ 句首代词 "He founded …" 的 "He" 也是大写，会被当成主语；
  - ⚠️ "worked at"、"Fei-Fei Li"、"University of Illinois" 都匹配不到或被截断。
- 这些问题在生产中由上游的 NER（给出准确 span）、共指（He → 谁）、EL（规范化）解决。

### 3.2 `RELATION_LABELS`：给 id 配一个人能读的名字

```python
RELATION_LABELS = {
    "P19":   "place of birth",
    "P112":  "founded",
    "P169":  "CEO of",
    "P108":  "employer",
    "P69":   "educated at",
    "P1830": "acquired",
}
```

- 图里存 id，打印时查表转成标签：存储用规范 id，展示用自然语言，两者解耦。
- ⚠️ **方向问题**：在 Wikidata 中，P112 是 "founded by"、P169 是 "chief executive officer"，主语都是**组织**、宾语是**人**（如 Apple → P169 → Tim Cook）。本代码按英文句子的语序存成 `(Tim Cook, P169, Apple)`，方向与 Wikidata 相反，所以标签写成了 "founded"、"CEO of"。讲义 Step 4 的注释也提醒了 P112 需要交换主宾。玩具代码里只要内部一致就没问题，但如果要把三元组合并进 Wikidata 或用 SPARQL 查询，必须先反转方向。P1830 在 Wikidata 中的标签是 "owner of"，这里标成 "acquired" 也是近似表达。

### 3.3 `extract`：抽取并记录出处

```python
def extract(text):
    triples = []
    for pattern, rel in PATTERNS:
        for m in pattern.finditer(text):
            subj = m.group(1)
            obj = m.group(2)
            span = (m.start(), m.end())
            triples.append({"subject": subj, "relation": rel, "object": obj, "span": span, "evidence": m.group(0)})
    return triples
```

- 外层遍历模式，内层用 `finditer` 找出该模式在全文中的**所有**非重叠匹配。所以结果按"模式顺序 + 文中位置"排列，而不是按句子顺序。
- `m.group(1)` / `m.group(2)` 取两个捕获组，`m.group(0)` 是整个匹配，作为证据句段。
- `span = (m.start(), m.end())` 是**整段证据**在原文中的字符区间，可以用 `text[start:end]` 原样取回。
- 用字典而不是元组存三元组，字段自描述，以后加 `doc_id`、`confidence`、`qualifiers` 也不用改调用方。
- ⚠️ 简化之处：
  - span 只有整段证据的位置，没有主语、宾语**各自**的 span；讲义 LLM prompt 要求的是每个实体都带 `[start, end]`；
  - 没有 `doc_id`，多文档时无法溯源到具体文档；
  - "in 2011"、"in 1976" 这些时间信息没有抽出来，无法生成 P580 等时间限定；
  - "Larry Page founded Google with Sergey Brin" 里的 Sergey Brin 被漏掉。AEVS 的 Supplement 步骤就是要补这种遗漏。

### 3.4 `verify`：回查原文

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

- 两道检查：① span 指向的原文必须与 evidence 一字不差（讲义 Step 3 的 "Reject anything where `text[start:end] != triple_entity`"）；② 主语、宾语必须出现在原文中。
- **对规则抽取来说它一定全部通过**：span 和 evidence 来自同一次正则匹配，所以输出 `extracted: 8  verified: 8`。它存在的意义是：将来把 `extract` 换成 LLM，LLM 返回的 span 和实体可能是编造的，这个函数就成了真正的闸门。
- ⚠️ **第二道检查太宽松**：它查的是"实体是否出现在**全文**某处"，而不是"是否出现在 evidence 里"。LLM 如果把 "Tim Cook became CEO of Apple" 的宾语错写成 "Google"，span 和 evidence 都对，"Google" 又恰好在别的句子里出现过，就能蒙混过关。改进：检查 `t["object"] in t["evidence"]`，或者让每个实体都带自己的 span 并逐一校验。另外，`in` 是子串匹配，"Meta" 也会命中 "Metadata"。

### 3.5 `build_graph` 与 `print_graph`：邻接表就是最小的图数据库

```python
def build_graph(triples):
    graph = defaultdict(list)
    for t in triples:
        graph[t["subject"]].append((t["relation"], t["object"], t["evidence"]))
    return graph


def print_graph(graph):
    for subj in sorted(graph):
        for rel, obj, ev in graph[subj]:
            label = RELATION_LABELS.get(rel, rel)
            print(f"  ({subj}) --[{label}]--> ({obj})")
            print(f"      evidence: \"{ev}\"")
```

- `defaultdict(list)`：访问不存在的键时自动创建空列表，省掉 `if key not in graph: graph[key] = []`。讲义 Step 5 用的 `graph.setdefault(s, []).append(...)` 是等价写法。
- 每条边存成 `(关系, 宾语, 证据)` 三元组，**出处跟着边走**，查询结果可以直接展示来源句子。这是审计友好的设计。
- 只按主语建索引，所以能回答"Tim Cook 的 X 是什么"，回答不了"谁是 Google 的 CEO"（需要入边索引，见测验 Q10）。
- `sorted(graph)` 对字典排序得到的是键的有序列表，所以输出按主语字母序排列（Dario、Elon、Larry…），与文档中的顺序无关。
- `RELATION_LABELS.get(rel, rel)`：查不到标签时退回显示 id 本身，是一个防御式写法。
- ⚠️ 没有去重：同一事实在多句里出现会生成多条边；生产中按 `(实体 id, 关系 id, 实体 id, 时间限定)` 去重，并把多个出处合并到同一条边上。

### 3.6 `main`：端到端演示与一次查询

```python
    triples = extract(doc)
    verified = verify(triples, doc)

    print(f"extracted: {len(triples)}  verified: {len(verified)}")
    print()
    graph = build_graph(verified)
    print_graph(graph)

    print()
    print("=== query: Tim Cook's employer ===")
    for rel, obj, ev in graph.get("Tim Cook", []):
        if rel == "P169":
            print(f"  Tim Cook is CEO of {obj}")
            print(f"  source: \"{ev}\"")
```

- 文档由 8 个简单句组成，每句恰好命中一条模式，所以 8 条全部抽出。真实新闻句式远比这复杂，召回会低得多。
- 查询用 `graph.get("Tim Cook", [])` 而不是 `graph["Tim Cook"]`：对 `defaultdict` 用方括号访问不存在的键会**偷偷插入**一个空列表，`.get` 不会改动图。
- 查询结果附带 `source`，这就是"带出处的回答"，KG-RAG 把这种子图交给 LLM 时，引用可以直接追溯到原句。
- ⚠️ 标题写的是 "Tim Cook's employer"，过滤的却是 P169（CEO），不是 P108（employer）。语义上"是 Apple 的 CEO"蕴含"受雇于 Apple"，但图里并没有 P108 这条边。真实 KG 中这类蕴含要靠本体推理规则（P169 ⇒ P108），或者在抽取时同时写入两条边。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 正则模式抽取 | 精度高、零依赖、每条结果都能追溯到某条规则 | 召回低、边界脆弱；生产中与 REBEL / 监督模型 / LLM + AEVS 混合 |
| 模式直接输出 Wikidata 属性 id | 抽取即规范化，图谱可查询 | 主宾方向按英文语序，与 Wikidata 的 P112 / P169 相反；入库前需要反转 |
| "大写开头"猜实体边界 | 省掉 NER 依赖 | 三词人名、代词、连字符名、多词机构名都会出错；生产中用 NER span + 共指 + EL |
| 每个三元组带 span + evidence | 出处是审计和幻觉检测的基础 | 只有整段证据的 span，缺少实体级 span 和 doc id |
| `verify` 回查原文 | 为 LLM 抽取预留闸门 | 实体检查基于全文子串，可以被张冠李戴的幻觉绕过 |
| `defaultdict(list)` 邻接表 | 最简单的图存储，查询直观 | 只有出边索引、不去重、无时间限定；生产中用 Neo4j / RDF triple store |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组列表作为配置表 | `PATTERNS = [(re.compile(...), "P19"), ...]` | 把"规则 + 标签"打包，循环时用解包取出 |
| `re.compile` | `re.compile(r"... was born in ...")` | 预编译正则，得到可重复使用的 Pattern 对象 |
| 原始字符串 `r"..."` | 所有正则 | 反斜杠不被 Python 转义，正则里更安全 |
| 正则捕获组 / 非捕获组 | `([A-Z][A-Za-z]+)`、`(?:became|is|was)`、`(?: Inc)?` | `(...)` 会被 `group(n)` 取出；`(?:...)` 只分组不捕获；`?` 表示可选 |
| `pattern.finditer` | `for m in pattern.finditer(text)` | 逐个返回 Match 对象（迭代器），适合找多个匹配 |
| Match 对象方法 | `m.group(0)`、`m.group(1)`、`m.start()`、`m.end()` | 整段匹配、第 n 个捕获组、起止下标 |
| 字典字面量 | `{"subject": subj, "relation": rel, ...}` | 用键名表达字段含义 |
| 元组解包 | `s, e = t["span"]`；`for rel, obj, ev in graph[subj]` | 一次取出多个值 |
| 切片 | `text[s:e]` | 取出 [s, e) 区间的子串 |
| `in` 子串判断 | `t["subject"] not in text` | 判断子串是否出现，注意是**子串**而不是整词 |
| `continue` | 校验失败时跳过 | 直接进入下一轮循环 |
| `collections.defaultdict` | `graph = defaultdict(list)` | 缺键时自动用 `list()` 创建默认值 |
| `dict.get(key, default)` | `RELATION_LABELS.get(rel, rel)`、`graph.get("Tim Cook", [])` | 安全取值；对 defaultdict 用 `.get` 不会插入新键 |
| `sorted(dict)` | `for subj in sorted(graph)` | 对字典的键排序，返回新列表 |
| f-string 与转义引号 | `f"      evidence: \"{ev}\""` | 在双引号字符串里用 `\"` 输出引号 |
| 多行字符串拼接 | `doc = ("Tim Cook ... 2011. " "Steve Jobs ...")` | 括号内相邻的字符串字面量会自动拼接 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py`，输出如下：

```text
=== rule-based relation extraction (with provenance) ===
document: Tim Cook became CEO of Apple in 2011. Steve Jobs founded Apple in 1976. ...

extracted: 8  verified: 8

  (Dario Amodei) --[educated at]--> (Princeton University)
      evidence: "Dario Amodei studied at Princeton University"
  (Elon Musk) --[acquired]--> (Twitter)
      evidence: "Elon Musk acquired Twitter"
  (Larry Page) --[founded]--> (Google)
      evidence: "Larry Page founded Google"
  (Satya Nadella) --[place of birth]--> (Hyderabad)
      evidence: "Satya Nadella was born in Hyderabad"
  (Steve Jobs) --[founded]--> (Apple)
      evidence: "Steve Jobs founded Apple"
  (Sundar Pichai) --[CEO of]--> (Google)
      evidence: "Sundar Pichai is CEO of Google"
  (Tim Cook) --[CEO of]--> (Apple)
      evidence: "Tim Cook became CEO of Apple"
  (Yann LeCun) --[employer]--> (Meta)
      evidence: "Yann LeCun works at Meta"

=== query: Tim Cook's employer ===
  Tim Cook is CEO of Apple
  source: "Tim Cook became CEO of Apple"

note: rule-based RE = high precision, low recall.
production stacks mix patterns + REBEL + LLM with AEVS verification.
```

逐行解读：

- **`extracted: 8  verified: 8`**：8 个句子各命中一条模式。校验全部通过，原因见 3.4：规则抽取的 span 天然正确。
- **按主语字母序输出**：`sorted(graph)` 的结果，不是原文顺序。
- **"Princeton University" 被完整抽出**：P69 模式的宾语允许可选后缀 " University"；其他模式没有这个后缀，宾语只能是一个词。
- **evidence 不含时间**：如 "Tim Cook became CEO of Apple" 后面的 "in 2011" 不在匹配范围内，时间信息丢失。
- **Larry Page 那条**：只有 `(Larry Page, founded, Google)`，"with Sergey Brin" 被漏掉，这就是"低召回"的直观例子。
- **查询部分**：按 P169 过滤得到 Apple，并带出原句作为出处。标题写 "employer"，实际查的是 CEO 关系，见 3.6 的说明。

---

## 7. 动手改一改

1. **加 doc_id 和时间**：给 `extract` 增加 `doc_id` 参数写进三元组；在模式末尾加可选的 `(?: in (\d{4}))?`，把年份存成 `qualifiers={"P580": "2011"}`。
2. **Hearst 模式**：加一条 `(\w+) such as (\w+)` → `isA`（如 "fruits such as apples"），注意输出方向是 `(Y, isA, X)`，即主语取第 2 组、宾语取第 1 组。
3. **实体级 span**：用 `m.start(1)`、`m.end(1)`、`m.start(2)`、`m.end(2)` 记录主语、宾语各自的位置，并改写 `verify` 逐一校验。
4. **对齐 Wikidata 方向 + 入边索引**：P112、P169 反转主宾，并维护 `in_edges`，回答"谁是 Google 的 CEO"。
5. **评估**：手写 5 句真实新闻句子（含代词、三词人名、过去时），人工标注 gold 三元组，计算 precision 和 recall，验证"规则 = 高精度、低召回"。
6. **接入 LLM**（需要 API key）：按讲义 Step 3 的 prompt 让 LLM 输出带 span 的 JSON，用你改进后的 `verify` 过滤，统计校验前后的幻觉率。

---

## 8. 常见坑

- **正则从左往右"重试"导致边界错位**：三词人名会被截成后两个词，看起来"抽到了"，实际上是错误实体，比漏抽更隐蔽。
- **代词当实体**：句首大写的 "He / She / It" 会成为图里的节点。RE 之前必须做共指消解。
- **`in` 是子串匹配**：`"Meta" in "Metadata"` 为 True；校验实体时应该比对 span，或用词边界正则 `\bMeta\b`。
- **关系方向**：自定义的 "CEO of" 和 Wikidata 的 P169 方向相反，混用会导致查询为空或语义颠倒。
- **对 defaultdict 用方括号查询**：`graph["不存在的人"]` 会悄悄插入空列表，污染图；查询用 `.get`。
- **时效性关系没有时间限定**："is CEO of" 今天为真，十年后可能为假；不加 P580 / P582，图谱会悄悄过期。
