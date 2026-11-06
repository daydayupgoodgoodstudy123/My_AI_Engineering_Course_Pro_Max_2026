# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 从基础到进阶 · 第 24 节 共指消解 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`re`），不需要 spaCy 或神经网络模型

---

## 1. 这份代码在考察什么

讲义 Step 2 说明了它的定位：一个只用标准库的**规则版代词消解器**，"不具竞争力，但能展示搜索空间，以及端到端模型必须做出的决策"。具体来说：

1. **Mention 抽取**：用三条启发式找出命名实体（大写串）、代词（查表）、名词性 mention（"the/a + 中性名词"）。
2. **特征**：给每个 mention 标上性别（m/f/n/u）和数（sg/pl）。
3. **先行词打分**：一致性分（数、性别）+ 近因分（越近越好）。
4. **选先行词**：对每个代词，在它之前的所有命名/名词性 mention 中取分数最高者。
5. **聚类**：用并查集把"代词 → 先行词"的链接合并成共指簇。

> 一句话：**端到端神经模型做的也是"找 mention → 给候选先行词打分 → 聚类"这三步**，只是打分函数是学出来的。读这份代码时，最有价值的是看它**错在哪里**——输出里有两条错误链接。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PRONOUNS` | 常量字典 | 11 个英文代词及其性别、数 | 代词 mention + 特征 |
| `FEMALE_FIRST` / `MALE_FIRST` | 常量集合 | 常见名字表，用于推断性别 | 性别启发式 |
| `NEUTER_HEADS` / `DETERMINERS` | 常量集合 | 中性名词中心词、限定词 | 名词性 mention |
| `extract_mentions(text)` | 函数 | 分句、分词，按规则抽 mention | mention detection |
| `infer_gender(name)` | 函数 | 按名字的第一个词查表 | 性别特征 |
| `agreement_score(m, c)` | 函数 | 数一致 +1；性别兼容 +1，冲突 −2 | 一致性约束 |
| `recency_score(m, c)` | 函数 | 句子距离 ×2 + 句内距离 ×0.01，取负 | 近因偏好 |
| `resolve(mentions)` | 函数 | 每个代词取最高分先行词 | mention-ranking（无学习） |
| `clusters(mentions, links)` | 函数 | 并查集把链接合并为簇 | 传递闭包聚类 |
| `main()` | 演示入口 | 8 句的新闻式短文 | — |

数据流：`doc → extract_mentions → mentions → resolve（agreement + recency → max）→ links → clusters（union-find）→ 簇`。

---

## 3. 逐段精讲

### 3.1 词表：把语言知识写死在字典里

```python
PRONOUNS = {
    "he":    {"gender": "m", "number": "sg", "type": "prp"},
    "him":   {"gender": "m", "number": "sg", "type": "prp"},
    # ...
    "it":    {"gender": "n", "number": "sg", "type": "prp"},
    "they":  {"gender": "u", "number": "pl", "type": "prp"},
    # ...
}

FEMALE_FIRST = {"mary", "alice", "sarah", ...}
MALE_FIRST = {"john", "james", "david", "tim", "steve", ...}
NEUTER_HEADS = {"company", "firm", "corporation", "product", "device", "phone", "laptop", ...}
```

- 性别取值：`m`（男）、`f`（女）、`n`（中性，物/机构）、`u`（未知）。`they` 标为 `u / pl`。
- `PRONOUNS` 是"代词 → 特征字典"的嵌套字典，查表即得特征。
- ⚠️ `her` 既可以是宾格（"call her"）也可以是物主限定词（"her team"），这里不区分；`they` 也可以是单数（指性别未知或非二元的个人），这里一律视为复数。
- ⚠️ 名字表推断性别正是讲义 Pitfalls 中的"Gender assumptions"：对非二元指称、机构、动物都会出错，讲义建议用学习模型或中立打分。

### 3.2 Mention 抽取：三条启发式

```python
def extract_mentions(text):
    mentions = []
    for sent_idx, sent in enumerate(re.split(r"(?<=[.!?])\s+", text)):
        tokens = re.findall(r"[A-Za-z]+|[^\s]", sent)
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            low = tok.lower()
            if low in PRONOUNS:
                mentions.append({"text": tok, "span": (sent_idx, i),
                                 "type": "pronoun", "features": PRONOUNS[low]})
                i += 1
                continue
            if low in DETERMINERS and i + 1 < len(tokens):
                head = tokens[i + 1].lower()
                if head in NEUTER_HEADS:
                    mentions.append({"text": f"{tok} {tokens[i + 1]}", "span": (sent_idx, i),
                                     "type": "nominal",
                                     "features": {"gender": "n", "number": "sg", "head": head}})
                    i += 2
                    continue
            if tok[0].isupper() and tok.isalpha() and low not in DETERMINERS:
                j = i + 1
                while j < len(tokens) and tokens[j][0].isupper() and tokens[j].isalpha():
                    j += 1
                name = " ".join(tokens[i:j])
                gender = infer_gender(name)
                mentions.append({"text": name, "span": (sent_idx, i),
                                 "type": "ne", "features": {"gender": gender, "number": "sg"}})
                i = j
                continue
            i += 1
    return mentions
```

- **分句**：`(?<=[.!?])\s+` 在句末标点后的空白处切开（与第 23 节相同的写法）。
- **分词**：`[A-Za-z]+|[^\s]` 匹配"连续字母"或"任意单个非空白字符"，所以标点会成为独立 token（`.`、`,`），数字会被拆成单个字符。
- **span 的表示**：`(句子编号, 句内 token 下标)`，后面的近因打分用它计算距离。
- 三条规则按顺序尝试，命中即 `continue`，所以**优先级**是：代词 > 名词性 > 命名实体。
  1. **代词**：小写后查 `PRONOUNS`。
  2. **名词性**：限定词（the/a/an）后紧跟 `NEUTER_HEADS` 中的词，组成 "The company"、"a laptop"，性别固定为 `n`。注意 "the new iPhone" 不会被识别——限定词后面是形容词 `new`。
  3. **命名实体**：首字母大写的纯字母 token，向后贪心吞并连续的大写 token（"Tim Cook"、"Mary Chen"）。排除 `The`、`A` 这类句首限定词。
- 用 `while` 而不是 `for`：命中多 token 的 mention 后要一次跳过多个位置（`i += 2`、`i = j`）。
- ⚠️ 大写启发式的问题：
  - 句首的普通词会被误抽（例如 "Yesterday"）；本例中缩写 `AI`、月份 `June` 都被当成了命名实体。
  - 小写开头的专名会被漏掉：`iPhone` 首字母是 `i`，没有被抽出。
  - 所有命名实体都被标为单数 `sg`，代码里不存在复数候选，`they/them/their` 永远找不到数一致的先行词。

### 3.3 性别推断

```python
def infer_gender(name):
    first = name.split()[0].lower()
    if first in FEMALE_FIRST:
        return "f"
    if first in MALE_FIRST:
        return "m"
    return "u"
```

- 只看名字的第一个词：`"Tim Cook" → "tim" → m`，`"Mary Chen" → "mary" → f`。
- 查不到就返回 `u`。`Apple`、`AI`、`June` 都是 `u`——它们其实应该是中性 `n`，但这条规则无法区分"未知性别的人"和"不是人"。这一点直接导致了 `Her -> AI` 的错误（见 3.5）。

### 3.4 打分：一致性 + 近因

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

- **一致性**是"软约束"：数一致 +1，不一致只是不加分；性别冲突扣 2 分，但仍可能被选中。这是规则系统常见的折中——硬约束（直接排除）在特征估错时会错杀正确答案。
- **未知即兼容**：任一方性别为 `u` 就视为兼容，并且与"性别完全匹配"拿一样的 +1。这个设计让未知性别的候选（`AI`、`Apple`）与确定匹配的候选（`Mary Chen`）在一致性上不分高下。
- **近因**：相隔一句扣 2 分，同句内每隔一个 token 扣 0.01 分。句子距离的权重远大于其他所有因素。
- ⚠️ `max(0, m_idx - c_idx)` 在**跨句**时比较的是两个不同句子里的句内下标，没有意义：代词多在句首（下标 0），这一项几乎总是 0，导致"同在前一句"的所有候选近因分完全相同，无法体现"越靠近句尾越近"。
- ⚠️ 讲义 Step 2 还提到"句法角色（主语优先）"和"只看前 K 个 mention"，代码中都没有实现：候选是代词之前的**全部**命名/名词性 mention。

### 3.5 选先行词

```python
def resolve(mentions):
    links = []
    for i, m in enumerate(mentions):
        if m["type"] != "pronoun":
            continue
        candidates = [c for c in mentions[:i] if c["type"] in ("ne", "nominal")]
        if not candidates:
            links.append((m, None))
            continue
        best = max(candidates, key=lambda c: agreement_score(m, c) + recency_score(m, c))
        links.append((m, best))
    return links
```

- 只为**代词**找先行词；名词性 mention（"The company"、"The device"）不会被链接到命名实体（"Apple"），所以它们之间的共指关系完全不会被发现。
- 候选只取 `mentions[:i]`（之前出现的），所以**后指**（"When she walked in, Mary smiled."）天然处理不了。
- 候选只限 `ne` 和 `nominal`，代词不能以另一个代词为先行词。这避免了错误链式传播，但也失去了"Her → She → Mary Chen"这种自然的链。
- `max(..., key=...)` 在平局时返回**第一个**最大值，也就是文中更早出现的候选——与"越近越好"的原则恰好相反。本例中 `It` 的两个候选同分，平局规则决定了结果（见第 6 节）。
- 没有"无先行词"选项：只要有候选就一定选一个，哪怕得分很低。mention-ranking 方法会把"这是新实体"作为一个可选项。

### 3.6 并查集聚类

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

- **并查集**（union-find / disjoint set）：每个元素指向一个"父节点"，根节点代表所在集合。`union` 把一个集合的根挂到另一个集合的根下，`find` 沿父指针找到根。
- `parent[x] = parent[parent[x]]` 是**路径减半**（一种路径压缩）：查找时顺手把节点指向祖父，树越查越矮。
- 用 `id(m)` 作 key：mention 是字典，字典不可哈希，不能作 dict 的 key；`id()` 返回对象的唯一整数标识。这要求 `links` 里的 mention 和 `mentions` 里的是**同一个对象**（`resolve` 返回的正是原对象，满足条件）。
- `find`、`union` 定义在 `clusters` 内部，是**闭包**：它们直接读写外层函数的 `parent` 字典。
- 为什么用并查集而不是直接"把代词放进先行词的簇"：并查集自动处理**传递闭包**——若 A–B、B–C 都有链接，A、B、C 就会在同一簇，这正是讲义中 mention-pair 方法 "Cluster by transitive closure" 的实现方式。
- `groups.setdefault(root, [])` 在 key 不存在时插入空列表并返回它，然后 `.append`，一行完成"分组"。
- 返回结果包含所有单例簇；`main()` 只打印长度大于 1 的簇，所以簇编号会出现跳号（0、1、4、6）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 大写串当命名实体 | 零依赖、几行代码 | 误抽句首词、缩写、月份，漏抽 iPhone；生产先跑 NER（讲义集成模式：NER → coref） |
| 名字表推断性别 | 简单直观 | 非二元、机构、动物全部出错；"未知"与"非人"混为一谈；生产用学习到的表示 |
| 软一致性约束（冲突 −2） | 特征估错时不至于完全排除正确答案 | 权重需要手调，且彼此牵制 |
| 句子距离 ×2 的近因 | 抓住"先行词通常就在附近" | 跨句时句内位置失效；压倒其他所有信号 |
| 只为代词找先行词 | 聚焦最常见、最容易演示的情况 | 名词性与专名之间（"The company"↔"Apple"）的共指完全缺失 |
| `max` 选最高分、无"新实体"选项 | 实现简单 | 平局按出现顺序；低分也必须选一个；mention-ranking 会加入空先行词 |
| 并查集聚类 | 自动完成传递闭包，近线性复杂度 | 一条错误链接就会合并两个簇 |
| `id(m)` 作 key | 字典不可哈希 | 依赖对象身份，拷贝后会失效；生产用 mention 的字符偏移作 ID |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 嵌套字典字面量 | `PRONOUNS = {"he": {"gender": "m", ...}, ...}` | 外层查词、内层查特征 |
| 集合字面量 | `FEMALE_FIRST = {"mary", "alice", ...}` | O(1) 成员判断 |
| `enumerate` + `re.split` | `for sent_idx, sent in enumerate(re.split(r"(?<=[.!?])\s+", text))` | 同时拿句子编号和句子 |
| 正则"或" | `re.findall(r"[A-Za-z]+|[^\s]", sent)` | 字母串或单个非空白字符 |
| `while` + 手动下标 | `i += 2`、`i = j` | 一次跳过多个 token |
| 字符串方法 | `tok[0].isupper()`、`tok.isalpha()`、`tok.lower()` | 判断首字母大写、是否纯字母、转小写 |
| 元组作 span | `"span": (sent_idx, i)`；`mention["span"][0]` | 不可变的位置坐标 |
| 列表切片 + `join` | `" ".join(tokens[i:j])` | 拼接多 token 名字 |
| 条件组合 | `mf["gender"] == "u" or cf["gender"] == "u" or mf["gender"] == cf["gender"]` | `or` 短路求值 |
| `max` + `key=lambda` | `max(candidates, key=lambda c: agreement_score(m, c) + recency_score(m, c))` | 按自定义分数取最大；平局取第一个 |
| 元组列表 | `links.append((m, best))`；`for m, ant in links` | 成对存储并解包 |
| `None` 作"无结果" | `links.append((m, None))`；`if ant is not None` | 用 `is` 判断 |
| `id()` | `parent = {id(m): id(m) for m in mentions}` | 对象唯一标识；用于不可哈希对象 |
| 嵌套函数 / 闭包 | `clusters` 内部定义 `find`、`union` | 内部函数可以访问外层的 `parent` |
| `dict.setdefault` | `groups.setdefault(root, []).append(m["text"])` | 不存在则插入默认值，再返回该值 |
| 条件表达式 | `antecedent["text"] if antecedent else "<none>"` | 一行 if/else |
| f-string 对齐 | `f"  [{m['type']:<7}] {m['text']:<22} feats={m['features']}"` | 左对齐；f-string 内用单引号取字典键 |

---

## 6. 运行结果解读

实际运行 `python3 main.py` 的输出：

```text
=== toy rule-based coreference ===
document: Tim Cook walked onto the stage. He announced the new iPhone. The company also showed a laptop. It will ship in June. Mary Chen joined Apple last year. She leads the AI team. Her team built the voice assistant. The device impressed the audience.

extracted 12 mentions:
  [ne     ] Tim Cook               feats={'gender': 'm', 'number': 'sg'}
  [pronoun] He                     feats={'gender': 'm', 'number': 'sg', 'type': 'prp'}
  [nominal] The company            feats={'gender': 'n', 'number': 'sg', 'head': 'company'}
  [nominal] a laptop               feats={'gender': 'n', 'number': 'sg', 'head': 'laptop'}
  [pronoun] It                     feats={'gender': 'n', 'number': 'sg', 'type': 'prp'}
  [ne     ] June                   feats={'gender': 'u', 'number': 'sg'}
  [ne     ] Mary Chen              feats={'gender': 'f', 'number': 'sg'}
  [ne     ] Apple                  feats={'gender': 'u', 'number': 'sg'}
  [pronoun] She                    feats={'gender': 'f', 'number': 'sg', 'type': 'prp'}
  [ne     ] AI                     feats={'gender': 'u', 'number': 'sg'}
  [pronoun] Her                    feats={'gender': 'f', 'number': 'sg', 'type': 'prp'}
  [nominal] The device             feats={'gender': 'n', 'number': 'sg', 'head': 'device'}

pronoun links:
  He       -> Tim Cook
  It       -> The company
  She      -> Mary Chen
  Her      -> AI

clusters:
  cluster 0: ['Tim Cook', 'He']
  cluster 1: ['The company', 'It']
  cluster 4: ['Mary Chen', 'She']
  cluster 6: ['AI', 'Her']

note: rules handle easy pronouns; production models are span-based neural.
note: neuter pronoun 'it' / 'its' prefers neuter-head nominals like 'the company'.
```

逐段解读：

- **12 个 mention**：
  - 漏掉了 `iPhone`（小写开头）、`the stage`、`the AI team`、`the voice assistant`、`the audience`（中心词不在 `NEUTER_HEADS` 里）。
  - 误抽了 `June`（月份）和 `AI`（缩写），二者都被标为性别未知的命名实体。
- **`He -> Tim Cook`**：正确。`Tim` 在男性名字表中，性别匹配，且只隔一句。
- **`It -> The company`**：`The company` (2,0) 和 `a laptop` (2,4) 的总分都是 `2 + (−2) = 0`，平局；`max` 返回先出现的 `The company`。语义上 "It will ship in June" 中发货的是产品，应指 `a laptop`。最后一行提示语把这个结果描述成规则的"偏好"，但它实际上是平局规则的副产品。
- **`She -> Mary Chen`**：正确。`Mary Chen` 与 `Apple` 同在前一句，分数都是 0，`Mary Chen` 更早出现，赢得平局——这次平局规则碰巧帮了忙。
- **`Her -> AI`**：错误。`AI` 性别未知，被视为兼容，一致性分与 `Mary Chen` 相同（都是 2）；但 `AI` 只隔一句（近因 −2），`Mary Chen` 隔两句（近因 −4），`AI` 以 0 比 −2 胜出。
- **簇**：只有含 2 个以上 mention 的簇被打印，编号跳号是因为单例簇（`a laptop`、`June`、`Apple`、`The device` 等）也占了编号。`The company` 和 `Apple` 本该同簇、`The device` 本该和 `a laptop` 或 `the voice assistant` 关联，但规则系统不处理名词性与专名之间的共指。

4 个代词链接中 2 个正确、1 个靠平局碰巧正确、1 个错误。试着修复（测验 Q8、Q9）会发现：改近因规则能修好 `It`，却让 `She` 错链到 `Apple`；加主语偏好能修好 `Her`，却修不好 `It`。这就是讲义说规则方法"展示搜索空间"、而生产要用 span-based 神经模型的原因。

---

## 7. 动手改一改

1. 修复跨句近因：同在前文时让越靠近句尾的候选得分越高，验证 `It -> a laptop`，同时观察 `She` 的链接如何变化（参考测验 Q8）。
2. 实现讲义提到的"主语优先"：给句首候选加 2.5 分，验证 `Her -> Mary Chen`（参考测验 Q9）。
3. 给 `resolve` 加入"无先行词"选项：最高分低于某个阈值（如 −1）时链接到 `None`，用 `"Yesterday the bank said it lost money. iPhone sales fell. They were worried."` 测试 `They` 是否不再链接到 `Yesterday`。
4. 允许代词以代词为先行词，观察并查集如何把 `Mary Chen`、`She`、`Her` 合成一个簇（参考测验 Q10）。
5. 区分"未知性别"和"非人"：给 `infer_gender` 加一个机构/产品词表（Apple、Google、AI 等返回 `n`），重新运行看 `Her` 是否被修好。
6. 进阶：手写 5 段带金标准的短文（讲义练习 1），计算代词链接准确率；如果环境中有 spaCy 实验共指模型，对比两者的错误类型。

---

## 8. 常见坑

- **把平局规则当成模型判断**：`max` 遇到相同分数时取第一个，结果依赖 mention 出现顺序。
- **"未知"不等于"兼容"**：把未知性别当成匹配，会让缩写、机构名、月份抢走人称代词。
- **跨句位置比较**：用句内下标比较不同句子里的 mention，距离计算没有意义。
- **大写启发式**：句首普通词被误抽，小写开头的专名被漏抽；生产中应先跑 NER。
- **只做代词**：名词性 mention（"the company"）与专名（"Apple"）之间的共指同样重要，讲义的 NER 覆盖率问题主要来自这里。
- **一条错误链接合并两个簇**：并查集的传递闭包会放大错误，生产中要对合并结果做一致性检查（如簇内性别冲突）。
