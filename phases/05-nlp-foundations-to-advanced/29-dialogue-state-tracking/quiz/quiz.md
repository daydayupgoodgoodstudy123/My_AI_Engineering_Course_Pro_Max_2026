# 测验 · 对话状态跟踪（Dialogue State Tracking）

> **阶段 05 · NLP 基础到进阶 · 第 29 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | DST 是什么 | 在任务型对话中，跨轮次维护一个 slot-value 字典（如 `{cuisine: italian, area: north, price: moderate}`），它是"用户说了什么"和"后端执行什么"之间的枢纽 |
| 2 | Schema | 定义领域（restaurant、hotel、taxi）和各自的槽位；槽位可以为空、取封闭集合中的值（price ∈ {cheap, moderate, expensive}），或取自由文本值（餐厅名） |
| 3 | 两种建模方式 | 分类式：对每个 (slot, 候选值) 判断是否成立，适合封闭词表，2020 年前的标准；生成式：直接生成槽值文本，适合开放词表，是现在的默认做法 |
| 4 | JGA（Joint Goal Accuracy） | **所有槽位都正确**的轮次占比，全对才算对；讲义称 MultiWOZ 2.4 上 2026 年的最好成绩约 80–83% |
| 5 | 架构演进 | 规则（正则 + 关键词）→ TripPy / BERT-DST（基于拷贝）→ LDST（LLaMA + LoRA 指令微调）→ 无本体（ontology-free）DST → prompt + 结构化输出（Pydantic + 约束解码，几行代码可上线） |
| 6 | 经典失败模式 | 跨轮共指（"就第一个吧"）、覆盖 vs 追加（"加上意大利菜"）、隐式确认（"OK cool"）、纠正（"actually 改成 7 点"）、指代系统上一句（"对，就那个"） |
| 7 | 状态更新三条不变式 | 用户没提到的槽位绝不重置；显式否定（"never mind the cuisine"）必须清空；纠正（"actually…"）必须覆盖而不是追加 |
| 8 | 全量重生成 vs 增量更新 | 每轮让 LLM 根据完整历史重新生成整个状态，天然能处理纠正；代价是总 token 量 O(n²)，需要截断或摘要早期轮次 |
| 9 | 工程陷阱 | schema 漂移要版本化；大小写统一归一化；隐式继承（新请求不应清掉之前的人数）；封闭槽与自由文本槽混合 |
| 10 | 合规场景 | 银行、医疗、航空等需要确定性的槽值：规则为主、LLM 兜底，破坏性操作前显式确认 |

### 核心技能（能动手做到）

- [ ] 能用同义词表 + 正则写出槽位抽取器，并实现满足三条不变式的 `update_state`
- [ ] 能逐轮推演规则 DST 的状态变化，指出否定、纠正、字典遍历顺序导致的错误
- [ ] 能同时计算轮次级 JGA 和槽位准确率，并解释为什么两者可以差很多
- [ ] 能用 Pydantic（`Optional[Literal[...]]`、`Optional[int]`）写出状态 schema，并写出"每轮根据完整历史重生成状态"的 LLM DST 函数
- [ ] 能识别"遍历 set 导致结果随运行变化"这类非确定性问题并修复
- [ ] 能为合规场景设计"规则主路 + LLM 兜底 + 确认流程"的 DST 方案

---

## 二、基础自测（选择题）

**Q1.** 一段 4 轮对话、4 个槽位。系统在第 2 轮和第 4 轮各错了 1 个槽位，其余全对。按轮次计算，JGA 和槽位准确率分别是：

- A. JGA = 87.5%，槽位准确率 = 87.5%
- B. JGA = 50%，槽位准确率 = 87.5%
- C. JGA = 75%，槽位准确率 = 50%
- D. JGA = 100%，因为最后只差一个槽位

**Q2.** 下列哪个槽位最**不适合**用"对每个 (slot, 候选值) 做二分类"的方式建模？

- A. price ∈ {cheap, moderate, expensive}
- B. area ∈ {north, south, east, west, center}
- C. 餐厅名称（如 "The Copper Kettle"）
- D. 是否需要停车位（yes / no）

**Q3.** 状态为 `{cuisine: thai, people: 4, time: 19:00}`。用户说："能改成 8 点吗？"正确的新状态是：

- A. `{cuisine: None, people: None, time: 20:00}`，因为这是一个新请求
- B. `{cuisine: thai, people: 4, time: 20:00}`
- C. `{cuisine: thai, people: 4, time: [19:00, 20:00]}`
- D. 保持不变，因为用户用的是疑问句

**Q4.** 每轮都让 LLM 读完整历史、重新生成整个状态。关于这种做法，下列说法**错误**的是：

- A. 它能自然地处理 "actually…" 这类纠正，不需要显式的回滚逻辑
- B. 一段 n 轮对话的总 token 消耗约为 O(n²)
- C. 可以通过限制历史长度或摘要早期轮次来控制成本
- D. 因为每轮都重新生成，所以完全不需要传入历史对话

**Q5.** 用户之前说了 "Chinese"，现在说 "add Italian"。最合理的处理是：

- A. 永远覆盖：cuisine = italian
- B. 永远追加：cuisine = [chinese, italian]
- C. 由 schema 决定：cuisine 是单值槽就覆盖（必要时向用户确认），业务支持多选就设计成列表槽并追加
- D. 忽略这句话，保持 chinese

**Q6.** 用 Instructor + Pydantic schema 做 LLM DST。下列说法**错误**的是：

- A. 输出一定能解析成合法的 `RestaurantState` 对象（槽名、类型、Literal 取值都受约束）
- B. 不会出现 schema 之外的槽位名
- C. 它保证抽出的槽值一定符合用户的真实意图
- D. `price` 定义为 `Optional[Literal["cheap", "moderate", "expensive"]]` 后，模型无法输出 "affordable" 这种 schema 外的值

**Q7.** 一个银行转账助手需要抽取"金额、收款账户、日期"。按讲义的建议，最合适的方案是：

- A. 纯 LLM 抽取，因为 LLM 的 JGA 更高
- B. 规则抽取为主、LLM 兜底，执行转账前向用户显式确认关键槽位
- C. 只用规则，遇到规则抽不出的情况直接执行默认值
- D. 让 LLM 直接调用转账 API，不维护状态

---

## 三、动手 / 代码题

**Q8.** 本节 `code/main.py` 的关键逻辑如下：

```python
CUISINE_SYNONYMS = {
    "italian": ["italian", "pasta", "pizza"],
    "chinese": ["chinese", "chow mein", "dim sum"],
    "indian":  ["indian", "curry", "tandoori"],
    "thai":    ["thai", "pad thai"],
}
PRICE_WORDS = {
    "cheap":     ["cheap", "inexpensive", "budget"],
    "moderate":  ["moderate", "mid-range", "mid range", "medium"],
    "expensive": ["expensive", "fancy", "high-end", "upscale"],
}
NEGATION_CUES = ["never mind", "forget about", "don't worry about"]

def extract_cuisine(utterance):
    low = utterance.lower()
    for canonical, synonyms in CUISINE_SYNONYMS.items():
        if any(syn in low for syn in synonyms):
            return canonical
    # ...

def is_negation(utterance, slot):
    low = utterance.lower()
    return any(cue in low for cue in NEGATION_CUES) and slot in low

def update_state(state, utterance):
    new_state = dict(state)
    for slot, extractor in SLOT_EXTRACTORS.items():
        value = extractor(utterance)
        if value is not None:
            new_state[slot] = value
            continue
        if is_negation(utterance, slot):
            new_state[slot] = None
    return new_state
```

从全空状态开始，依次输入下面 4 轮，写出每轮之后的 `cuisine` 和 `price`，指出与用户意图不符的地方及原因：

```python
turns = ["I don't want Chinese, give me Indian.",
         "Somewhere cheap in the west.",
         "Actually, not cheap, make it expensive.",
         "Never mind the Indian."]
# 用户的真实意图（最终）：cuisine=None, area=west, price=expensive, people=None
```

再给出修复思路和参考实现（至少修好 cuisine 和 price 两个槽）。

**Q9.** `extract_area` 的实现如下：

```python
AREA_WORDS = {"north", "south", "east", "west", "center", "centre"}

def extract_area(utterance):
    low = utterance.lower()
    for w in AREA_WORDS:
        if re.search(rf"\b{w}\b", low):
            return "center" if w == "centre" else w
    return None
```

对 `"Not the north, the south please."`，同一份代码多次运行（不同进程），结果会一样吗？为什么？应该怎么改？

**Q10.** 讲义对 JGA 的定义是"所有槽位都正确的**轮次**占比"，而 `main()` 只在每段对话结束时比较一次最终状态（`ok = state == d["gold"]`）。请：

1. 写一个 `run_dialogue(turns)` 返回每轮之后的状态列表；
2. 写一个 `turn_level_metrics(pred_states, gold_states)`，返回轮次级 JGA 和每个槽位的准确率；
3. 用 Q8 的对话和下面的逐轮 gold 计算结果，并解释 JGA 与槽位准确率的差距。

```python
gold = [
    {"cuisine": "indian", "area": None,   "price": None,        "people": None},
    {"cuisine": "indian", "area": "west", "price": "cheap",     "people": None},
    {"cuisine": "indian", "area": "west", "price": "expensive", "people": None},
    {"cuisine": None,     "area": "west", "price": "expensive", "people": None},
]
```

---

## 四、面试高频题

**Q11.**（基础必考）什么是对话状态跟踪？既然有了 LLM 和 function calling，为什么 DST 仍然重要？

**Q12.**（原理深挖）对比分类式 DST、生成式 DST（TripPy 等拷贝机制）、LLM + 结构化输出三类方法。JGA 为什么是"全对才算对"？它有什么优缺点？

**Q13.**（工程实践）你负责一个订餐 / 订酒店的多领域对话系统，用 LLM 做 DST。如何设计 schema、更新策略、纠正和否定处理、成本控制和评估？

**Q14.**（场景设计）为航空公司改签助手设计 DST：用户可能说"改到周四""不要早班机""就刚才说的第二个航班"。请给出方案，重点说明合规与确认流程。

**Q15.**（追问型）"每轮重新生成整个状态"和"增量更新状态"各有什么取舍？对话很长（50+ 轮）时你怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：B

JGA 按轮次计算，某轮只要有一个槽位错，这一轮就算错：4 轮中 2 轮全对，JGA = 50%。槽位准确率按槽位计：共 16 个槽位，错 2 个，14/16 = 87.5%。这正是 JGA "all-or-nothing" 的含义：它比平均槽位准确率严格得多，也更贴近"后端会不会执行错"的业务结果。

### Q2 — 答案：C

分类式 DST 需要事先枚举候选值，只适合封闭词表。餐厅名、时间、地址等是开放词表，无法穷举，需要生成式（或拷贝式）建模，讲义也说名称、时间、地址需要自由文本槽位。A、B、D 都是小而封闭的取值集合。

### Q3 — 答案：B

讲义的第一条不变式："Never reset a slot the user did not touch"；陷阱部分的"隐式继承"也说："之前说了 4 个人，新的时间请求不应清掉人数"。用户只改了时间，cuisine 和 people 必须保留；time 是单值槽，应该覆盖而不是追加（C）。D 错在疑问句在这里是请求，不是询问。

### Q4 — 答案：D

A、B、C 都是讲义内容：全量重生成通过读完整历史自然吸收纠正；但每轮都重读历史，总 token 是 O(n²)；可以限制历史或摘要早期轮次。D 说反了：全量重生成恰恰**依赖**完整历史，讲义在陷阱部分强调 "Always pass the full history"。

### Q5 — 答案：C

讲义把"覆盖 vs 追加"列为经典失败模式：用户说 "add Italian"，到底是替换还是追加，取决于业务语义。单值槽默认覆盖，但"add"暗示用户想要多个选项，这时可以向用户确认；如果业务确实支持多选（比如"中餐或意餐都行"），schema 就应该把 cuisine 设计成列表。A、B 都是一刀切的规则，D 丢失了用户输入。

### Q6 — 答案：C

Instructor + Pydantic 保证的是**形式**：输出能通过 schema 校验（槽名固定、类型正确、取值在 Literal 范围内，校验失败可以重试），所以 A、B、D 都成立。它不能保证**语义**正确：用户说 "not cheap"，模型仍然可能填 `price="cheap"`，这在 schema 上完全合法。这也是讲义要求合规槽位必须有规则二次校验和确认流程的原因。

### Q7 — 答案：B

讲义 Use It："Compliance-sensitive → Rule-based primary, LLM fallback with confirmation flow"；skill 文件要求"拒绝对合规敏感槽位使用纯 LLM DST"，以及"在破坏性操作前显式确认"。A 忽视了 LLM 的抽取错误；C 用默认值执行转账非常危险；D 没有可审计的状态。

### Q8 — 参考答案

实际运行结果：

| 轮次 | 用户输入 | cuisine | price | 用户意图 | 问题 |
|------|---------|---------|-------|---------|------|
| 1 | I don't want Chinese, give me Indian. | **chinese** | None | indian | 否定 "don't want" 没有处理；且 `CUISINE_SYNONYMS` 按 italian → chinese → indian 的顺序检查，**先命中 chinese** 就返回 |
| 2 | Somewhere cheap in the west. | chinese | cheap | indian / cheap | 错误继承自第 1 轮（area = west 正确） |
| 3 | Actually, not cheap, make it expensive. | chinese | **cheap** | expensive | 句中同时出现 cheap 和 expensive，`PRICE_WORDS` 先检查 cheap，于是返回 cheap；"not" 没处理；`is_correction` 定义了但 `update_state` 根本没调用 |
| 4 | Never mind the Indian. | **indian** | cheap | None | 抽取器先找到 "indian" 并赋值，然后 `continue`，否定判断根本没机会执行；而且 `is_negation` 只检查槽位名 "cuisine" 是否出现，用户说的是值 "Indian" |

最终状态 `{'cuisine': 'indian', 'area': 'west', 'price': 'cheap', 'people': None}`，与意图有 2 个槽位不符。

**根因**：

1. **先到先得**：抽取器按字典顺序返回第一个命中的值，而不是句中**最后**提到的值。纠正句通常是"不要 A，要 B"，B 在后面。
2. **否定只认槽位名、且排在抽取之后**："never mind the Indian" 这类按值否定的说法无法清空。
3. **子串匹配**：`syn in low` 没有词边界，"Indianapolis" 会被识别为 indian，"no budget constraints" 会被识别为 cheap（均已实际验证）。

**参考实现**（只改 cuisine 和 price；area、people 沿用原抽取器）：

```python
import re

NEG_BEFORE = re.compile(r"\b(?:not|no|don't want)\s+(?:the\s+)?$")


def extract_last(utterance, synonyms_map):
    """返回 (最后一个未被否定的规范值, 被否定的规范值集合)。"""
    low = utterance.lower()
    best, negated = None, set()
    for canonical, syns in synonyms_map.items():
        for syn in syns:
            for m in re.finditer(rf"\b{re.escape(syn)}\b", low):          # 词边界匹配
                if NEG_BEFORE.search(low[max(0, m.start() - 15):m.start()]):
                    negated.add(canonical)          # "not cheap" / "don't want chinese"
                elif best is None or m.start() > best[0]:
                    best = (m.start(), canonical)   # 越靠后的提及越优先
    return (best[1] if best else None), negated


def update_state_v2(state, utterance):
    new_state = dict(state)
    low = utterance.lower()
    has_neg_cue = any(cue in low for cue in NEGATION_CUES)
    for slot, syn_map in (("cuisine", CUISINE_SYNONYMS), ("price", PRICE_WORDS)):
        value, negated = extract_last(utterance, syn_map)
        if slot == "cuisine" and ("any cuisine" in low or "any food" in low):
            value = "any"
        cur = new_state[slot]
        mentions_cur = cur is not None and any(s in low for s in syn_map.get(cur, []))
        if has_neg_cue and (slot in low or mentions_cur) and value in (None, cur):
            new_state[slot] = None                  # "never mind the Indian"
        elif value is not None:
            new_state[slot] = value
        elif cur in negated:
            new_state[slot] = None                  # 只说了 "not cheap"，没给新值
    for slot, fn in (("area", extract_area), ("people", extract_people)):
        v = fn(utterance)
        if v is not None:
            new_state[slot] = v
        elif is_negation(utterance, slot):
            new_state[slot] = None
    return new_state
```

实际运行：4 轮后的状态依次为

```text
{'cuisine': 'indian', 'area': None, 'price': None, 'people': None}
{'cuisine': 'indian', 'area': 'west', 'price': 'cheap', 'people': None}
{'cuisine': 'indian', 'area': 'west', 'price': 'expensive', 'people': None}
{'cuisine': None, 'area': 'west', 'price': 'expensive', 'people': None}
```

与意图完全一致，并且 `main()` 中原有的 3 段对话仍然全部通过（回归测试）。

说明：这个修复依然是启发式的（否定窗口只看前 15 个字符，"I'd rather avoid Chinese" 就识别不了），这也说明了讲义的结论：纠正和否定"不借助 LLM 很难做对"，现代做法是让 LLM 根据完整历史重生成整个状态，规则只作为合规槽位的二次校验。

### Q9 — 参考答案

**不一定一样**。`AREA_WORDS` 是 `set`，而字符串的哈希值在每个 Python 进程启动时会随机化（`PYTHONHASHSEED`），所以 set 的遍历顺序在不同进程之间可能不同。句子里同时出现 "north" 和 "south" 时，先遍历到哪个就返回哪个。实际验证：同一句话在 `PYTHONHASHSEED=0/1/2/3/5` 时返回 `south`，在 `PYTHONHASHSEED=4` 时返回 `north`。

这类 bug 非常隐蔽：单元测试可能偶尔通过、偶尔失败，线上行为也不可复现。而且无论返回哪个都没有理解 "Not the north"。

修改：

```python
AREA_WORDS = ["north", "south", "east", "west", "center", "centre"]   # 改成有序列表


def extract_area(utterance):
    low = utterance.lower()
    best = None
    for w in AREA_WORDS:
        for m in re.finditer(rf"\b{w}\b", low):
            prefix = low[max(0, m.start() - 10):m.start()]
            if re.search(r"\bnot\s+(?:the\s+)?$", prefix):
                continue                          # 跳过被否定的提及
            if best is None or m.start() > best[0]:
                best = (m.start(), w)             # 取最后一个有效提及
    if best is None:
        return None
    return "center" if best[1] == "centre" else best[1]
```

修改后，这句话在不同的 `PYTHONHASHSEED` 下都返回 `south`（已验证），"In the centre of town." 仍然返回 `center`。

要点：①需要确定性的地方不要依赖 set 的遍历顺序（dict 从 Python 3.7 起保证插入顺序，set 不保证）；②多值冲突时要有明确的决策规则（"最后提及优先"、"跳过被否定的提及"）。

### Q10 — 参考答案

```python
def run_dialogue(turns, init=None):
    state = dict(init or {"cuisine": None, "area": None, "price": None, "people": None})
    states = []
    for t in turns:
        state = update_state(state, t)
        states.append(state)                  # update_state 每次返回新字典，可以直接保存
    return states


def turn_level_metrics(pred_states, gold_states):
    jga = sum(p == g for p, g in zip(pred_states, gold_states)) / len(gold_states)
    slots = list(gold_states[0])
    slot_acc = {
        s: sum(p[s] == g[s] for p, g in zip(pred_states, gold_states)) / len(gold_states)
        for s in slots
    }
    return jga, slot_acc


pred = run_dialogue(turns)                    # turns 为 Q8 的 4 轮
jga, slot_acc = turn_level_metrics(pred, gold)
print(jga, slot_acc)
```

实际输出：

```text
0.0 {'cuisine': 0.0, 'area': 1.0, 'price': 0.5, 'people': 1.0}
```

解读：

- **轮次级 JGA = 0**：4 轮里没有一轮所有槽位都对（cuisine 每轮都错）。
- **平均槽位准确率 = (0 + 1 + 0.5 + 1) / 4 = 62.5%**：看起来"还行"，但业务上这 4 轮无论在哪一轮下单都会订错。JGA 对应的正是"后端会不会执行错"。
- **为什么要逐轮评估**：`main()` 只比最终状态，等于"对话级成功率"。中间轮次如果错了，但最后一轮恰好纠正过来，它看不出来；而真实系统可能在中间轮次就调用了 API（查询空位、预下单）。讲义 Step 4 的 `joint_goal_accuracy(predicted_states, gold_states)` 也是按轮次比较的。
- `update_state` 每次都 `dict(state)` 复制一份，所以 `states` 里保存的是各轮独立的快照；如果它原地修改 `state`，列表里会是同一个对象的多个引用，所有轮次都显示最终状态。

### Q11 — 参考回答要点

- **定义**：任务型对话中，跨轮次维护用户目标的结构化表示（slot-value 字典），每一轮用户都可能新增、修改或删除槽位；系统要综合整个对话输出当前状态，作为调用后端的参数。
- **为什么仍然重要**（讲义三点）：
  1. 合规敏感领域（银行、医疗、航空）要求确定性的槽值，而不是自由生成；
  2. 工具调用型 agent 在调用 API 之前同样要先把参数解析清楚，function calling 的参数本质上就是槽位；
  3. 多轮纠正（"actually no, make it Thursday"）比看上去难。
- **现代形态**：经典 DST 概念 + LLM 抽取器 + 结构化输出护栏。
- **加分点**：DST 的错误会直接变成错误的后端操作（订错餐厅、扣错卡），所以 DST 的评测指标（JGA）要严格，执行前还要有确认流程。

### Q12 — 参考回答要点

| 方法 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| 分类式（2020 年前主流） | 对每个 (slot, 候选值) 做是 / 否判断 | 输出必然合法、易于校准 | 只适合封闭词表；候选多时计算量大 |
| 生成 / 拷贝式（TripPy、BERT-DST） | BERT 编码对话，从用户话语、系统话语或已有槽值中**拷贝**槽值 | 支持开放词表（名称、时间） | 需要标注数据，跨领域迁移难 |
| LLM 指令微调（LDST：LLaMA + LoRA） | 用领域-槽位提示做指令微调 | 讲义称在 MultiWOZ 2.4 上达到 ChatGPT 水平 | 需要训练与部署开源模型 |
| LLM + 结构化输出（Pydantic + Instructor） | 提示 LLM 输出符合 schema 的状态 | 零标注、几行代码，输出格式有保证 | 语义错误仍可能发生；成本、延迟较高 |

- **JGA**：每一轮所有槽位都正确才算对。
  - 优点：严格，与"后端执行是否正确"一致；
  - 缺点：对槽位数多的领域非常苛刻，一处小错就整轮作废；看不出错误集中在哪个槽位。
  - 所以 skill 文件要求同时报告**槽位级的 precision / recall**，以及最难槽位的混淆情况。
- **加分点**：JGA 是累积性的，前面轮次的错误如果没被纠正，会一路带到后面所有轮次。

### Q13 — 参考回答要点

1. **Schema**：每个领域一个 Pydantic 模型（讲义 Use It："Schema-guided LLM with per-domain Pydantic models"）；封闭槽用 `Literal`，名称、时间用自由文本 + 后处理归一化；整体 schema 打版本号。
2. **更新策略**：每轮根据完整历史重生成整个状态（自然处理纠正）；历史过长时保留最近 k 轮 + 早期轮次摘要 + 当前状态。
3. **纠正与否定**：prompt 中明确规则（未提及的槽位保持不变、显式否定要清空、纠正要覆盖）；用少量 few-shot 示例覆盖 "actually…"、"never mind…" 等句式。
4. **归一化与校验**：大小写、同义词（centre → center）、数字与时间格式统一；Pydantic 校验失败时重试。
5. **成本**：对话越长，重生成越贵（O(n²)）；用便宜模型做 DST，只在置信度低时升级到大模型；也可以让规则先抽、LLM 补漏（讲义 Hard 练习的路由方案）。
6. **评估**：留出对话集上算轮次级 JGA、槽位级 P / R、最难槽位的混淆矩阵；按"纠正轮""否定轮""共指轮"分桶报告。
7. **确认流程**：下单前复述关键槽位，等待用户确认。
- **常见误区**：只评估最终状态；schema 改动不打版本，导致新旧评测结果不可比。

### Q14 — 参考回答要点

- **Schema**：`origin`、`destination`（封闭集合：机场代码）、`date`（自由文本 → 归一化为具体日期）、`time_preference`（如"不要早班"→ `exclude: morning`）、`selected_flight`（引用系统给出的候选列表）、`passenger`。
- **难点处理**：
  - "改到周四"：相对日期结合当前日期解析成绝对日期，属于纠正，覆盖 date；
  - "不要早班机"：否定约束，作为过滤条件存储，而不是一个槽值；
  - "就刚才说的第二个航班"：指代系统上一句给出的列表，DST 需要能访问系统输出的候选及其顺序（讲义的"coreference to previous system utterance"）。
- **合规与确认**：
  - 规则为主（日期、航班号、金额用正则 + 校验器），LLM 负责理解复杂表达；
  - 关键槽位（航班号、日期、改签费用）在执行前**逐项复述并要求明确确认**，"OK cool" 这类隐式确认不能直接执行；
  - 低置信度时主动澄清；
  - 记录每次状态变更的来源（哪一轮、哪个抽取器），便于审计和回滚（skill 文件：拒绝无法在用户纠正时回滚槽位的 DST）。
- **加分点**：用户纠正后，要撤销已经基于旧槽值发起的预订查询；对语音渠道，先经过 ASR 和归一化再做 DST。

### Q15 — 参考回答要点

| 维度 | 全量重生成 | 增量更新 |
|------|-----------|---------|
| 纠正处理 | 天然处理，模型根据完整历史推出最终状态 | 需要显式的纠正、回滚逻辑 |
| 成本 | 每轮读完整历史，总量 O(n²) | 每轮只处理最新一句 + 当前状态，总量约 O(n) |
| 稳定性 | 每轮都可能"重新想一遍"，偶尔丢掉早期槽位 | 未提及的槽位天然保持 |
| 可审计性 | 状态变化来源不明显 | 每次变更都可追溯到具体轮次 |

- **长对话（50+ 轮）**：
  - 输入 = 当前结构化状态 + 最近 k 轮原文 + 早期轮次摘要，让 LLM 输出更新后的完整状态（介于两者之间）；
  - 状态本身就是对历史最好的压缩，所以要在 prompt 里明确"未提及的槽位保持当前值"；
  - 定期用全量历史做一次校验性重生成，或者在关键操作前做；
  - 对比两种策略的 JGA 与成本，再选择。
- **加分点**：增量方案中仍然可以让 LLM 判断"这一句是否是纠正 / 否定"，再执行确定性的更新操作，兼顾可审计性和理解能力。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 17 聊天机器人——从规则系统到神经网络，再到 LLM Agents](../../17-chatbots-rule-to-neural/docs/zh.md)：任务型对话系统的整体架构，DST 是其中的核心模块。
- [阶段 05 · 20 Structured Outputs & 约束解码](../../20-structured-outputs-constrained-decoding/docs/zh.md)：LLM DST 依赖 Pydantic schema 和约束解码保证输出合法。
- [阶段 05 · 24 共指消解](../../24-coreference-resolution/docs/zh.md)："就第一个吧""那个"这类跨轮指代。
- [阶段 05 · 06 命名实体识别](../../06-named-entity-recognition/docs/zh.md)：槽位填充与序列标注、实体抽取同源。

### 本节被哪些后续内容用到
- [阶段 11 · 09 Function Calling](../../../11-llm-engineering/09-function-calling/docs/zh.md)：工具调用的参数就是槽位，调用前要先完成"槽位解析"。
- [阶段 13 · 02 Function Calling 深入](../../../13-tools-and-protocols/02-function-calling-deep-dive/docs/zh.md)：参数 schema 设计与校验。
- [阶段 11 · 16 LangGraph 状态机](../../../11-llm-engineering/16-langgraph-state-machines/docs/zh.md)：把对话状态显式建模为状态机。
- [阶段 14 · 13 LangGraph 有状态图](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：agent 中的状态管理与持久化。
- [阶段 06 · 12 语音助手流水线](../../../06-speech-and-audio/12-voice-assistant-pipeline/docs/zh.md)：语音场景下的 ASR → 归一化 → DST。
- [阶段 05 · 27 LLM Evaluation](../../27-llm-evaluation-frameworks/docs/zh.md)：把 JGA 等指标接入 CI 回归评测。

### 延伸关键词
`MultiWOZ 2.1 / 2.4` · `Schema-Guided Dialogue (SGD)` · `TripPy` · `TRADE` · `LDST` · `slot filling` · `dialogue policy` · `NLU → DST → Policy → NLG` · `Instructor / Pydantic` · `confirmation strategy`
