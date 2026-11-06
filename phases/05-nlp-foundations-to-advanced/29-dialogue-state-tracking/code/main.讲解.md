# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到进阶 · 第 29 节 对话状态跟踪 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`re`），无需 API key

---

## 1. 这份代码在考察什么

这是讲义 Step 1、Step 2 的完整实现：一个**基于规则的订餐 DST**，跟踪 4 个槽位（cuisine、area、price、people），在 3 段手写对话上计算准确率。它要你掌握：

1. **槽位抽取器**：同义词表 + 正则，把自然语言映射到规范值（"pasta" → italian、"centre" → center、"six guests" → 6）。
2. **状态更新循环**：每一轮复制旧状态、只改被提到的槽位，实现讲义的三条不变式：未提及的槽位不重置、显式否定要清空、纠正要覆盖。
3. **封闭槽 vs 半开放槽**：cuisine、area、price 是封闭集合；people 是数字，需要正则 + 数词转换。
4. **JGA 的"全对才算对"**：最终状态必须和 gold 完全相等。
5. **规则方法的边界**：在规范词表内很好用，一遇到否定、同时出现多个值、子串误匹配就会出错。这正是讲义推荐"LLM + Pydantic 全量重生成"的原因。

> 一句话：**DST = 一个不断被"打补丁"的字典**。规则版把补丁逻辑写死在代码里；LLM 版让模型根据完整历史重新生成整个字典。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CUISINE_SYNONYMS` / `AREA_WORDS` / `PRICE_WORDS` | 模块级字典 / 集合 | 每个槽位的规范值及同义词 | 封闭词表的 schema |
| `CORRECTION_CUES` / `NEGATION_CUES` | 模块级列表 | 纠正提示词、否定提示词 | 纠正与否定处理 |
| `extract_cuisine / extract_area / extract_price / extract_people` | 函数 | 从一句话中抽出某个槽位的规范值，没有就返回 `None` | 槽位抽取器 |
| `SLOT_EXTRACTORS` | 字典：槽名 → 函数 | 把槽位和抽取器注册在一起 | schema 驱动的抽取 |
| `is_correction(utterance)` | 函数 | 判断是否含纠正提示词（**定义了但没有被调用**） | 纠正检测 |
| `is_negation(utterance, slot)` | 函数 | 含否定提示词**且**提到了槽位名 | 显式否定 |
| `update_state(state, utterance)` | 函数 | 根据一句话生成新状态 | 增量式状态更新 |
| `render_dialog(turns)` | 函数 | 把对话渲染成文本（**没有被调用**，对应讲义 LLM 版 prompt 里的 `render(history)`） | 为 LLM DST 预留 |
| `main()` | 函数 | 3 段对话逐轮更新、打印、与 gold 比较 | 评测 |

数据流：`main` 对每段对话从全空状态开始，逐轮调用 `update_state`；`update_state` 遍历 `SLOT_EXTRACTORS`，调用各个 `extract_*`。

---

## 3. 逐段精讲

### 3.1 Schema 与同义词表

```python
CUISINE_SYNONYMS = {
    "italian": ["italian", "pasta", "pizza"],
    "chinese": ["chinese", "chow mein", "dim sum"],
    "indian":  ["indian", "curry", "tandoori"],
    "thai":    ["thai", "pad thai"],
}

AREA_WORDS = {"north", "south", "east", "west", "center", "centre"}
PRICE_WORDS = {
    "cheap":     ["cheap", "inexpensive", "budget"],
    "moderate":  ["moderate", "mid-range", "mid range", "medium"],
    "expensive": ["expensive", "fancy", "high-end", "upscale"],
}
CORRECTION_CUES = ["actually", "no wait", "on second thought", "change that to", "instead"]
NEGATION_CUES = ["never mind", "forget about", "don't worry about"]
```

- 字典的**键是规范值**（canonical value），列表是各种说法。抽取器输出永远是规范值，这样状态里不会出现 "pasta"、"centre" 这类不统一的写法（讲义陷阱 "Case sensitivity — normalize everywhere"）。
- 这些表就是一个隐式的 schema：cuisine ∈ {italian, chinese, indian, thai, any}、price ∈ {cheap, moderate, expensive}。讲义 Step 3 的 Pydantic `Literal` 写的是同一套取值，规则版与 LLM 版共用一份 schema 是好习惯。
- ⚠️ 顺序很重要：`dict` 从 Python 3.7 起保持插入顺序，抽取器"先到先得"，所以 italian 永远比 chinese 先检查，cheap 永远比 expensive 先检查。这会在一句话同时提到两个值时出问题（见 3.5）。
- ⚠️ `AREA_WORDS` 是 **set**，没有确定的遍历顺序（见 3.3）。

### 3.2 `extract_cuisine` 与 `extract_price`：子串匹配

```python
def extract_cuisine(utterance):
    low = utterance.lower()
    for canonical, synonyms in CUISINE_SYNONYMS.items():
        if any(syn in low for syn in synonyms):
            return canonical
    if "any cuisine" in low or "any food" in low:
        return "any"
    return None


def extract_price(utterance):
    low = utterance.lower()
    for canonical, synonyms in PRICE_WORDS.items():
        if any(syn in low for syn in synonyms):
            return canonical
    return None
```

- 先 `lower()` 再匹配，大小写不敏感。
- `any(syn in low for syn in synonyms)`：只要有一个同义词是这句话的**子串**就命中。`any` 遇到第一个 True 就停止（短路）。
- "any cuisine / any food" 放在最后检查，表示"不限菜系"，对应 schema 中的 `"any"` 值，用于第 2 段对话的 "Never mind the cuisine, any food is fine."。
- ⚠️ **子串匹配没有词边界**："We're near Indianapolis." 会抽出 indian；"We have no budget constraints" 会抽出 cheap（都已实际验证）。
- ⚠️ "expensive" 是 "inexpensive" 的子串，但因为 cheap 先检查、"inexpensive" 属于 cheap，所以 "inexpensive" 能正确归为 cheap。这是**顺序碰巧救了一次**，不是设计出来的保证。
- ⚠️ 不理解否定：`"I don't want Chinese"` 抽出的是 chinese。

### 3.3 `extract_area`：词边界正则，但遍历的是 set

```python
def extract_area(utterance):
    low = utterance.lower()
    for w in AREA_WORDS:
        if re.search(rf"\b{w}\b", low):
            return "center" if w == "centre" else w
    return None
```

- `rf"\b{w}\b"` 同时是 raw string 和 f-string：`\b` 是正则的**词边界**，保证 "north" 不会匹配 "northern"（north 后面紧跟字母 e，词边界不成立）。相比 cuisine 和 price 的子串匹配，这里更严谨。
- 英式拼写 "centre" 被归一化为 "center"。
- ⚠️ **非确定性**：`AREA_WORDS` 是 set，字符串的哈希在每次启动 Python 时会随机化（`PYTHONHASHSEED`），set 的遍历顺序随之变化。对 "Not the north, the south please." 这种同时提到两个方位的句子，实测在 `PYTHONHASHSEED=4` 时返回 north，在 0、1、2、3、5 时返回 south。修复方法：改成有序列表，并按"最后一个未被否定的提及"决策（参考测验 Q9）。

### 3.4 `extract_people`：正则 + 数词映射

```python
def extract_people(utterance):
    m = re.search(r"\b(\d+|two|three|four|five|six|seven|eight)\s+(?:people|guests|persons|diners)", utterance.lower())
    if not m:
        return None
    word_to_num = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
    raw = m.group(1)
    return int(raw) if raw.isdigit() else word_to_num.get(raw)
```

- 正则要求"数字或数词 + 空白 + 人数名词"。`(\d+|two|...)` 是捕获组，`(?:people|guests|...)` 是非捕获组。
- `raw.isdigit()` 区分 "4" 和 "four"，前者 `int()`，后者查表。
- 返回 `int`，与讲义 Pydantic schema 中的 `people: Optional[int]` 一致：数量类槽位应该是数字，而不是字符串。
- ⚠️ 覆盖有限："a table for 4"（没有人数名词）、"ten people"、"one person" 都抽不出来（前两个已验证返回 None）。

### 3.5 `update_state`：增量更新与三条不变式

```python
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

逐条对照讲义的三条不变式：

| 不变式 | 代码如何实现 | 局限 |
|-------|------------|------|
| 未提及的槽位不重置 | `dict(state)` 复制旧状态，只有抽到值或被否定的槽位才会被改 | ✅ 实现良好 |
| 显式否定要清空 | `is_negation`：含否定提示词**且**句中出现槽位名（如 "cuisine"） | 用户说的是**值**（"never mind the Indian"）时无法清空；而且抽取器先找到 "indian" 就 `continue`，否定判断根本不会执行 |
| 纠正要覆盖 | 抽到新值就直接覆盖旧值，所以 "Actually make it moderate pricing" 能把 cheap 改成 moderate | 靠的是"新值覆盖"，不是纠正检测：`is_correction` 从未被调用；句中同时出现旧值和新值时（"not cheap, make it expensive"），先到先得会选中旧值 |

- **为什么要 `dict(state)` 复制**：返回新字典而不是原地修改，调用方可以保存每一轮的状态快照（逐轮评估、回滚都需要）。这是浅拷贝，状态的值都是不可变的字符串和整数，浅拷贝足够。
- `continue` 让"抽到值"优先于"否定"：同一句话既抽到新值又含否定提示词时，以新值为准。第 2 段对话的最后一句 "Never mind the cuisine, any food is fine." 正是靠这个顺序得到 `any`。
- 这是**增量式**更新：只看当前这一句和上一个状态。讲义推荐的现代做法是让 LLM 每轮根据**完整历史**重生成整个状态，自然处理纠正，代价是 O(n²) 的 token 成本。

### 3.6 `main`：逐轮更新与"JGA"

```python
    for i, d in enumerate(dialogues):
        state = {"cuisine": None, "area": None, "price": None, "people": None}
        print(f"\ndialogue {i}:")
        for turn in d["turns"]:
            state = update_state(state, turn)
            print(f"  user: {turn}")
            print(f"  state: {state}")
        ok = state == d["gold"]
        jga_correct += int(ok)
        print(f"  gold:  {d['gold']}")
        print(f"  match: {'  OK' if ok else 'MISS'}")
```

- 3 段对话分别覆盖：纠正（cheap → moderate）、显式否定 + "any"（Chinese → any）、平铺直叙的多轮填槽。
- 初始状态显式列出所有槽位并设为 `None`，这样 `state == d["gold"]` 的字典比较才能逐键对齐（`==` 比较两个字典时，键集合和每个值都要相同）。
- ⚠️ **指标口径**：讲义定义的 JGA 是"所有槽位都正确的**轮次**占比"，这里每段对话只在最后比较一次，算的其实是"对话级最终状态准确率"。中间轮次即使错了、后来又被纠正回来，也看不出来。要算真正的轮次级 JGA，需要给每一轮都标注 gold 状态（参考测验 Q10）。
- ⚠️ 测试集只有 3 段对话、全部在规范词表内，100% 不代表系统可用。讲义 Easy 练习要求至少 10 段手写对话。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 同义词表 + 子串匹配 | 实现简单，覆盖规范说法 | 无词边界、无否定理解；生产中用词边界正则、否定窗口，或交给 LLM |
| 规范值作为字典键 | 输出天然归一化 | 新同义词要手工维护；schema 应版本化 |
| 抽取器注册表 `SLOT_EXTRACTORS` | 增加槽位只需加一个函数和一行注册 | 槽位之间无法互相参考（比如 "not cheap, expensive" 需要跨值决策） |
| 增量更新 + `dict(state)` 复制 | 未提及槽位天然保留，每轮都有快照 | 纠正、否定要靠规则补丁；讲义推荐 LLM 全量重生成 |
| 抽到值优先于否定 | "Never mind the cuisine, any food" 能得到 any | "Never mind the Indian" 反而把 cuisine 设为 indian |
| `AREA_WORDS` 用 set | 写起来简洁 | 遍历顺序不确定，多值句子的结果随进程变化；应改成有序列表 |
| 只比最终状态 | 代码最短 | 不是讲义定义的轮次级 JGA；生产中逐轮评估并报告槽位级 P / R |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 字典 / 集合 / 列表字面量 | `CUISINE_SYNONYMS = {...}`、`AREA_WORDS = {...}`、`CORRECTION_CUES = [...]` | 注意 `{"a", "b"}` 是集合，`{"a": 1}` 是字典 |
| `dict.items()` | `for canonical, synonyms in CUISINE_SYNONYMS.items()` | 同时遍历键和值；dict 保持插入顺序（3.7+） |
| set 遍历顺序 | `for w in AREA_WORDS` | set 不保证顺序，字符串哈希随进程随机化 |
| `any()` + 生成器表达式 | `any(syn in low for syn in synonyms)` | 有一个为真就返回 True，并且短路 |
| `in` 子串判断 | `"any food" in low` | 判断子串，不考虑词边界 |
| raw f-string | `rf"\b{w}\b"` | 同时具备原始字符串（`\b` 不转义）和 f-string（插入变量）的特性 |
| `re.search` + 分组 | `m = re.search(r"\b(\d+|two|...)\s+(?:people|...)", ...)`；`m.group(1)` | 找第一个匹配；捕获组取值 |
| `str.isdigit()` | `raw.isdigit()` | 判断字符串是否全是数字字符 |
| 条件表达式 | `int(raw) if raw.isdigit() else word_to_num.get(raw)`；`"center" if w == "centre" else w` | 一行完成分支 |
| 函数作为字典的值 | `SLOT_EXTRACTORS = {"cuisine": extract_cuisine, ...}`；`value = extractor(utterance)` | 函数是一等对象，可以存进字典再调用（注册表模式） |
| `dict(state)` 浅拷贝 | `new_state = dict(state)` | 复制一个新字典，修改它不影响原字典 |
| `continue` | 抽到值后跳过否定判断 | 进入下一轮循环 |
| 字典相等比较 | `state == d["gold"]` | 键和值完全一致才为 True |
| `str.join` + 生成器 | `"\n".join(f"  user: {u}" for u in turns)` | 拼接多行文本 |
| f-string 嵌套引号与条件表达式 | `f"  match: {'  OK' if ok else 'MISS'}"`、`f"{d['gold']}"` | 外双内单，避免引号冲突 |
| f-string 格式说明符 | `{100 * jga_correct / len(dialogues):.1f}` | 保留 1 位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py`，输出如下（节选每段对话的关键行）：

```text
=== rule-based DST ===

dialogue 0:
  user: I want a cheap restaurant in the north.
  state: {'cuisine': None, 'area': 'north', 'price': 'cheap', 'people': None}
  user: Italian food please.
  state: {'cuisine': 'italian', 'area': 'north', 'price': 'cheap', 'people': None}
  user: Actually make it moderate pricing.
  state: {'cuisine': 'italian', 'area': 'north', 'price': 'moderate', 'people': None}
  user: For four people.
  state: {'cuisine': 'italian', 'area': 'north', 'price': 'moderate', 'people': 4}
  gold:  {'cuisine': 'italian', 'area': 'north', 'price': 'moderate', 'people': 4}
  match:   OK

dialogue 1:
  ...
  user: Never mind the cuisine, any food is fine.
  state: {'cuisine': 'any', 'area': 'center', 'price': 'expensive', 'people': 6}
  match:   OK

dialogue 2:
  ...
  state: {'cuisine': 'thai', 'area': 'south', 'price': 'moderate', 'people': 2}
  match:   OK

=== Joint Goal Accuracy: 3/3 (100.0%) ===
```

逐段解读：

- **dialogue 0**：一句话可以同时填多个槽（第 1 轮填了 area 和 price）；第 2 轮只改 cuisine，其他槽保持（不变式 1）；第 3 轮的 "Actually…" 把 cheap 覆盖成 moderate（不变式 3，靠"新值覆盖"实现）；"four" 通过数词表转成整数 4。
- **dialogue 1**：第 1 轮 "Find me an expensive Chinese place." 一次填了 cuisine 和 price；"In the center of town." 填 area；"Six guests." 填 people=6；最后一句同时含否定提示词和 "any food"，抽取器先返回 any 并 `continue`，结果正确。
- **dialogue 2**：最简单的逐个填槽。注意 "Thai food in the south." 里的 "thai" 同时是 "pad thai" 的子串，但 thai 本身就在同义词表里，所以没有歧义。
- **3/3 (100.0%)**：这是"最终状态准确率"，而且测试用例都在规范词表内。换成测验 Q8 那样含否定和多值的对话，最终状态就错了 2 个槽位，逐轮 JGA 为 0。

---

## 7. 动手改一改

1. **修掉非确定性**：把 `AREA_WORDS` 改成列表，用 `PYTHONHASHSEED=4 python main.py` 和 `PYTHONHASHSEED=0 python main.py` 测试 "Not the north, the south please."，确认两次结果一致。
2. **加词边界**：把 `syn in low` 改成 `re.search(rf"\b{re.escape(syn)}\b", low)`，验证 "Indianapolis" 不再被识别为 indian。
3. **"最后提及优先" + 否定窗口**：对每个同义词用 `re.finditer` 找出所有位置，跳过前面紧跟 "not / don't want" 的提及，取位置最靠后的值（参考测验 Q8 的 `extract_last`）。
4. **按值否定**：让 "never mind the Indian" 也能清空 cuisine：否定提示词出现且句中提到了**当前槽值**的同义词时，清空该槽。
5. **逐轮 JGA**：给每段对话的每一轮标注 gold 状态，实现轮次级 JGA 和槽位级准确率。
6. **LLM 版对照**（需要 API key 并安装 instructor、pydantic）：按讲义 Step 3 写 `RestaurantState`，用 `render_dialog` 渲染历史、每轮重生成整个状态，在同一批对话上比较 JGA 和每轮成本。

---

## 8. 常见坑

- **先到先得**：一句话里出现多个候选值时，按字典顺序返回第一个，而用户真正想要的通常是最后提到的那个（"不要 A，要 B"）。
- **子串误匹配**：没有词边界的 `in` 判断会把 "Indianapolis" 当成 indian、把 "no budget constraints" 当成 cheap。
- **否定只认槽位名**：用户更常说 "never mind the Indian"，而不是 "never mind the cuisine"。
- **依赖 set 的顺序**：结果会随 Python 进程变化，测试时好时坏，线上不可复现。
- **只评最终状态**：中间轮次的错误会被掩盖；讲义的 JGA 是按轮次计算的。
- **定义了却没用的逻辑**：`is_correction` 和 `render_dialog` 都没被调用。读代码时不要以为"有纠正检测"，纠正之所以能工作，完全是因为"抽到新值就覆盖"。
