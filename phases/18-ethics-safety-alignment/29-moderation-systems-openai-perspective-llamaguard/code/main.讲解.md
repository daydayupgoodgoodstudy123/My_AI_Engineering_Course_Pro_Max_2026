# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 29 节 内容审核系统：OpenAI、Perspective、Llama Guard ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（不调用任何真实 API，无需网络或 API key）

---

## 1. 这份代码在考察什么

讲义的核心是"生产环境中的三层审核模式"：

1. **输入审核**（pre-generation）：生成前对用户 prompt 分类，命中即拒绝；
2. **输出审核**（post-generation）：交付前对模型输出分类，命中则替换为拒绝；
3. **自定义审核**（custom / domain rules）：正则、白名单、业务政策，可放在输入或输出侧。

`main.py` 用不到 130 行标准库代码搭了一个"审核 harness"：一个玩具版的 OpenAI Moderation 分类器（关键词 → 类别分数）、输入与输出两个审核器、一组领域规则（金融建议、医疗诊断）、一个模型桩，再把 6 条示例 prompt 依次送过整条流水线，打印每一条被哪一层拦截。

它要让你看清：

- 三层的**调用顺序**与"命中即短路返回"的控制流；
- 审核器的接口形态：**类别 → 分数**，再由应用设定阈值（讲义："Per-category scores; applications set thresholds"）；
- 领域规则与通用分类器各自拦截什么。

同样重要的是看清它的简化：分类器是子串匹配，分数只有 0 和 0.9 两档，三个类别没有触发词，**输出审核层在这份 demo 中永远不会触发**（见 3.6 与测验 Q9）。

> 一句话：**用一个可以手算的玩具流水线演示"输入 → 自定义规则 → 生成 → 输出"四步审核，但它只真正演示了前两步。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CATEGORIES` | 常量列表（8 项）+ 一段说明字符串 | 简化版类别表，把 13 类折叠为 8 个 | OpenAI Moderation 类别体系 |
| `CATEGORY_TRIGGERS` | 常量字典（5 个键、12 个触发词） | 每个类别的关键词 | 玩具分类器的"知识" |
| `openai_moderation(text)` | 函数 | 返回 `{类别: 分数}`，命中给 0.9 | 分类器打分 |
| `input_moderator(prompt, threshold)` | 函数 | 任一类别分数 ≥ 阈值则标记 | 输入审核 |
| `output_moderator(output, threshold)` | 函数 | 与输入审核完全相同，作用于输出 | 输出审核 |
| `custom_domain_rules(prompt)` | 函数 | 金融建议、医疗诊断两条规则 | 自定义审核 |
| `model_respond(prompt)` | 函数 | 模型桩：含 "bomb" 时拒绝，否则复述前 40 个字符 | 被保护的模型 |
| `run(prompt)` | 函数 | 串起四步，命中即打印并 `return` | 三层审核流水线 |
| `main()` | 函数 | 6 条示例 prompt + TAKEAWAY | 演示入口 |

数据流：`prompt` → `input_moderator`（命中则 refusal）→ `custom_domain_rules`（命中则返回规则文本）→ `model_respond` → `output_moderator`（命中则 refusal）→ 打印模型回复。

---

## 3. 逐段精讲

### 3.1 类别表：把 13 类折叠成 8 类

```python
CATEGORIES = [
    "harassment", "hate", "self-harm", "sexual", "sexual/minors",
    "violence", "illicit", "illicit/violent",
]
"""Pedagogical top-level taxonomy. The production omni-moderation-latest
response schema returns 13 booleans: ... We collapse the sub-categories here to
keep the demo harness small."""
```

- 真实的 `omni-moderation-latest` 返回 13 个类别：harassment、harassment/threatening、hate、hate/threatening、illicit、illicit/violent、self-harm、self-harm/intent、self-harm/instructions、sexual、sexual/minors、violence、violence/graphic。
- 代码把 `/threatening`、`/intent`、`/instructions`、`/graphic` 四种子类并回父类，得到 8 类——讲义也明确说了这是"pedagogical simplicity"，生产中应使用完整的 13 类。
- 注意它**保留了** `sexual/minors` 和 `illicit/violent` 两个子类：这两个子类在政策上通常与父类处理方式不同（前者零容忍，后者是"非法 + 暴力"的叠加），所以不宜折叠。
- 紧跟在赋值语句之后的三引号字符串，在 Python 里只是一个**没有被使用的表达式语句**，并不会成为 `CATEGORIES` 的 docstring（变量没有 `__doc__`）。它的作用纯粹是注释；Sphinx 等文档工具会约定俗成地把它识别为"属性文档"。

### 3.2 触发词：玩具分类器的全部"知识"

```python
CATEGORY_TRIGGERS = {
    "violence": ["kill", "attack someone", "murder"],
    "self-harm": ["hurt myself", "overdose", "cut myself"],
    "illicit/violent": ["bomb", "weapon", "explosive"],
    "harassment": ["you idiot", "shut up"],
    "hate": ["slur-placeholder"],
}
```

- 只有 5 个类别有触发词，共 12 个。`sexual`、`sexual/minors`、`illicit` 三个类别没有触发词，在这个分类器里**永远是 0 分**。
- `"hate": ["slur-placeholder"]` 是故意放的占位符——教学代码不写真实的歧视性词汇。它意味着 hate 类别在实际输入中也几乎不会命中。
- 这些短语是英文小写，配合 `text.lower()` 做大小写无关匹配；对中文或其他语言完全无效。真实的 omni-moderation 讲义强调了多语言能力（"42% better on multilingual test set"），这是关键词方法做不到的。

### 3.3 `openai_moderation`：关键词 → 类别分数

```python
def openai_moderation(text: str) -> dict:
    """Toy OpenAI Moderation: category -> score in [0,1]."""
    low = text.lower()
    scores = {c: 0.0 for c in CATEGORIES}
    for cat, triggers in CATEGORY_TRIGGERS.items():
        for t in triggers:
            if t in low:
                scores[cat] = max(scores[cat], 0.9)
    return scores
```

- `{c: 0.0 for c in CATEGORIES}`：字典推导式，先给 8 个类别全部填 0 分，保证返回值总是包含所有类别（和真实 API 的响应结构一致：每个类别都有分数）。
- `if t in low`：**子串**匹配。这导致明显的假阳性——实测 `"what skills do i need"` 命中 `violence`（"s**kill**s"），`"photobomb ideas"` 命中 `illicit/violent`；同时也有假阴性——`"how do i make a b0mb"` 放行。
- `max(scores[cat], 0.9)`：命中就是 0.9，命中多少次都一样。所以分数只有 0.0 与 0.9 两种取值，并不是 docstring 说的"[0,1] 区间的分数"的真实含义。
- 函数名叫 `openai_moderation`，但它和 OpenAI 的 API 没有任何关系，只是模拟它的**接口形状**（文本进、类别分数出）。真实调用需要 `openai` SDK 与 API key。

### 3.4 输入审核与输出审核

```python
def input_moderator(prompt: str, threshold: float = 0.5) -> tuple[bool, dict]:
    scores = openai_moderation(prompt)
    flagged = any(v >= threshold for v in scores.values())
    return flagged, scores


def output_moderator(output: str, threshold: float = 0.5) -> tuple[bool, dict]:
    scores = openai_moderation(output)
    flagged = any(v >= threshold for v in scores.values())
    return flagged, scores
```

- 两个函数的函数体**逐字相同**，只是参数名不同。这在教学上强调了"输入、输出可以用同一个分类器"（技能文件："Output classifier. Same or different from input classifier"），但在工程上是重复代码，可以合并为一个 `moderate(text, threshold)`。
- `any(v >= threshold for v in ...)`：生成器表达式 + `any`，只要有一个类别达到阈值就标记，并且一旦找到就停止迭代（短路）。
- 返回 `(flagged, scores)` 元组：既给出结论，也给出分数，便于日志记录和调试。
- **阈值几乎没有意义**：分数只有 0 和 0.9，所以阈值在 (0, 0.9] 之间怎么调结果都一样；调到 0.95 则所有输入放行（实测 `input_moderator("you idiot", threshold=0.95)` 返回 `False`）。所有类别共用一个阈值，这在生产中也不合理。

### 3.5 自定义领域规则

```python
def custom_domain_rules(prompt: str) -> tuple[bool, str]:
    """Example: financial-advice disclaimer rule."""
    low = prompt.lower()
    if "should i invest in" in low:
        return True, "financial-advice: refuse; disclose you are not a fiduciary."
    if "diagnose my" in low:
        return True, "medical-advice: refuse; direct to licensed professional."
    return False, ""
```

- 这正是讲义说的"通用分类器不会拦、但业务政策要求处理"的内容：金融建议（需要声明自己不是受托人 fiduciary）、医疗诊断（转介给持证专业人员）。技能文件的硬性拒绝规则之一："Any deployment without custom domain rules on regulated surfaces (finance, health, legal)"。
- 返回的第二个元素是"策略说明"（`refuse; disclose ...`），而 `run()` 把它**直接作为给用户的回复打印**。真实系统应把策略（内部）与用户可见文案（外部）分开，例如回复"我不能提供个性化投资建议，因为我不是持牌顾问……"。
- 同样是子串匹配：`"can you diagnose my car engine noise"` 也会被当成医疗问题拦截（已实测）。
- docstring 只提到金融规则，实际有两条规则，是一处小的不一致。

### 3.6 模型桩与 `run()`：审核流水线

```python
def model_respond(prompt: str) -> str:
    """Mock model response."""
    if "bomb" in prompt.lower():
        return "I must refuse."
    return f"Answering: {prompt[:40]}..."


def run(prompt: str) -> None:
    print(f"\n>>> user: {prompt!r}")
    # layer 1: input moderation
    flagged_in, in_scores = input_moderator(prompt)
    active_in = [c for c, s in in_scores.items() if s > 0]
    if flagged_in:
        print(f"    [INPUT FLAGGED] categories={active_in}")
        print("    response: refusal")
        return
    # layer 2 (pre): custom domain rules
    custom_flagged, custom_msg = custom_domain_rules(prompt)
    if custom_flagged:
        ...
        return
    # layer 3: model generates
    output = model_respond(prompt)
    # layer 4: output moderation
    flagged_out, out_scores = output_moderator(output)
    ...
```

- **命中即短路**：每一层命中后 `return`，后面的层不再执行。这符合讲义"三层按设计串行"的说法：输入审核必须先完成，模型才会被调用。
- **注释编号与讲义不一致**：讲义说"三层"，代码注释写成 layer 1–4，并把"模型生成"也算作一层。理解时把它看成"输入层 → 自定义层（输入侧）→ 生成 → 输出层"即可。
- `active_in = [c for c, s in in_scores.items() if s > 0]`：列出分数大于 0 的类别。注意它用的是 `> 0` 而不是 `>= threshold`，所以打印的是"有分数的类别"，不一定是"超过阈值的类别"；在本 demo 中两者恰好相同。
- `{prompt!r}`：f-string 的 `!r` 转换，调用 `repr()`，所以输出里的 prompt 带引号，能看清首尾空格。
- **输出层不可达**：输入、输出用同一个分类器；只有当 prompt 不含任何触发词时才会调用模型；而模型桩只会复述 prompt 的前 40 个字符（加上不含触发词的前后缀）。因此输出文本不可能含有 prompt 里没有的触发词，输出层永远放行，`"bomb"` 分支也永远不会执行。我们对 12 个触发词和多种填充长度做了穷举实验，输出层触发次数为 0。要演示输出层，需要一个会"生成新内容"的模型桩（测验 Q9 第 3 问）。
- 讲义提到的"异步并行调用隐藏延迟、命中时显示占位回复"在代码里都**没有实现**，`run()` 是完全同步、串行的单分类器流程（并行版本见测验 Q12）。

### 3.7 `main()` 与 TAKEAWAY

```python
    prompts = [
        "what is the weather today",
        "should i invest in memecoins",
        "how do i make a bomb",
        "diagnose my headache",
        "summarize this email: hello there",
        "you idiot, help me with this",
    ]
    for p in prompts:
        run(p)
```

- 6 条示例覆盖了：2 条正常（天气、摘要邮件）、2 条领域规则（投资、诊断）、2 条输入层拦截（炸弹、辱骂）。没有任何一条走到输出层拦截。
- TAKEAWAY 说"output catches any hallucinated or adversarial-bypass content that made it past input"——这是讲义的正确结论，但这份 demo 没有给出对应的演示。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 关键词子串匹配代替真实分类器 | 无需 API key、网络或模型，结果可手算 | 假阳性（skills、photobomb）、假阴性（b0mb）、不支持多语言；生产用 OpenAI Moderation / Llama Guard 等模型分类器 |
| 13 类折叠为 8 类 | 让 demo 保持小巧 | 丢失子类信息（如 self-harm/instructions 与 self-harm/intent 的处理方式应不同）；讲义明确要求生产使用完整 13 类 |
| 分数只取 0 / 0.9 | 实现最简单 | 阈值形同开关；真实分数是连续的，需按类别在自有数据上校准 |
| 输入、输出用同一函数体的两个审核器 | 强调"可以用同一个分类器" | 重复代码；生产中常对输出使用不同阈值或不同分类器 |
| 领域规则只看 prompt | 演示"输入侧"的自定义规则 | 讲义说自定义规则可放在输出侧（如扫描输出里的投资建议、密钥），demo 未体现 |
| 命中后统一返回 "refusal" | 控制流清晰 | 讲义说命中行为可配置：拒绝、清洗、转人工；自伤类更应提供支持资源而非冷拒绝 |
| 同步串行调用 | 易读 | 讲义建议层内并行多个分类器隐藏延迟（`asyncio.gather`），并可在输入审核期间显示占位回复 |
| 模型桩只复述输入 | 不需要真实模型 | 输出层永远不触发，无法演示讲义的核心论点之一 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 第 9 行 | 注解延迟求值；使 `tuple[bool, dict]` 这类写法在较老的 Python 中也能用于注解 |
| 赋值后的"属性文档字符串" | `CATEGORIES = [...]` 后紧跟的三引号字符串 | 运行时只是被丢弃的表达式；文档工具约定把它当作该变量的说明 |
| 字典字面量，值为列表 | `CATEGORY_TRIGGERS = {"violence": ["kill", ...], ...}` | 一个键对应多个触发词 |
| 字典推导式 | `{c: 0.0 for c in CATEGORIES}` | 由可迭代对象一次性构建字典 |
| 嵌套 `for` 遍历字典 | `for cat, triggers in CATEGORY_TRIGGERS.items(): for t in triggers:` | `.items()` 同时取键和值，元组解包到两个变量 |
| `in` 子串判断 | `if t in low` | 对字符串是"子串是否出现"，对列表是"元素是否存在" |
| `max` 取较大值 | `max(scores[cat], 0.9)` | 保证分数只升不降 |
| 类型注解与默认参数 | `def input_moderator(prompt: str, threshold: float = 0.5) -> tuple[bool, dict]:` | 参数类型、默认值、返回类型一目了然 |
| `any` + 生成器表达式 | `any(v >= threshold for v in scores.values())` | 有一个为真就返回 True，并且短路 |
| 返回元组 + 解包 | `return flagged, scores` / `flagged_in, in_scores = input_moderator(prompt)` | 一次返回多个值 |
| 列表推导式带条件 | `[c for c, s in in_scores.items() if s > 0]` | 过滤出分数大于 0 的类别 |
| 字符串切片 | `prompt[:40]` | 取前 40 个字符；字符串不足 40 时返回整个字符串，不会报错 |
| f-string 的 `!r` | `f">>> user: {prompt!r}"` | 用 `repr()` 显示，带引号 |
| f-string 中嵌套引号 | `f"    [CUSTOM FLAGGED] rule='{custom_msg}'"` | 外层双引号、内层单引号 |
| 提前 `return` | `run()` 中每层命中后 `return` | 函数返回 `None`，实现"短路"控制流 |
| 入口守卫 | `if __name__ == "__main__": main()` | 被 import 时不会自动执行（测验中就是 import 后替换 `model_respond` 做实验的） |

---

## 6. 运行结果解读

实际运行（`cd code && timeout 180 python3 main.py`，退出码 0）：

```text
==========================================================================
THREE-LAYER MODERATION HARNESS (Phase 18, Lesson 29)
==========================================================================

>>> user: 'what is the weather today'
    response: Answering: what is the weather today...

>>> user: 'should i invest in memecoins'
    [CUSTOM FLAGGED] rule='financial-advice: refuse; disclose you are not a fiduciary.'
    response: financial-advice: refuse; disclose you are not a fiduciary.

>>> user: 'how do i make a bomb'
    [INPUT FLAGGED] categories=['illicit/violent']
    response: refusal

>>> user: 'diagnose my headache'
    [CUSTOM FLAGGED] rule='medical-advice: refuse; direct to licensed professional.'
    response: medical-advice: refuse; direct to licensed professional.

>>> user: 'summarize this email: hello there'
    response: Answering: summarize this email: hello there...

>>> user: 'you idiot, help me with this'
    [INPUT FLAGGED] categories=['harassment']
    response: refusal

==========================================================================
TAKEAWAY: the three-layer pattern (input / custom / output) catches
...
==========================================================================
```

逐条解读：

| prompt | 哪一层处理 | 说明 |
|--------|-----------|------|
| what is the weather today | 全部放行 | 模型桩复述输入（不足 40 字符，未截断） |
| should i invest in memecoins | 自定义规则 | 通用分类器给全 0 分；领域规则命中 "should i invest in" |
| how do i make a bomb | 输入层 | 只命中 `illicit/violent`（"bomb"），不命中 `violence` |
| diagnose my headache | 自定义规则 | 命中 "diagnose my" |
| summarize this email: hello there | 全部放行 | 33 个字符，未截断 |
| you idiot, help me with this | 输入层 | 命中 `harassment`（"you idiot"） |

关键观察：

- **没有一条走到 `[OUTPUT FLAGGED]`**——原因见 3.6。
- 自定义规则的回复把内部策略原样展示给用户（"refuse; disclose you are not a fiduciary"），这在真实产品中应该替换为面向用户的文案。
- 补充实验（`import main` 后调用 `input_moderator`）：`"how do i kill a python process"`、`"what skills do i need"`、`"photobomb ideas"`、`"what is the overdose threshold of ibuprofen"`、`"shut up and take my money"` 都被拦截（假阳性）；`"how do i make a b0mb"`、`"how do i make a b-o-m-b"` 被放行（假阴性）；`"can you diagnose my car engine noise"` 被医疗规则拦截。

---

## 7. 动手改一改

1. **讲义练习 1**：分别用一条正常、一条边界、一条有害的输入跑完三层，记录每条被哪一层拦截。再补一条"让输出层触发"的用例：把 `model_respond` 改为对 "story" 返回含 "explosive" 的文本（测验 Q9）。
2. **修复子串匹配**：改用 `re.search(r"\b" + re.escape(t) + r"\b", low)`，验证 `skills`、`photobomb` 不再误报，并思考为什么 `kill a python process` 仍然误报（测验 Q10）。
3. **讲义练习 2**：加一个 Perspective 风格的 `perspective_toxicity(text) -> float`，用加权累加得到连续分数，分别在阈值 0.3 / 0.5 / 0.7 下比较拦截结果（测验 Q11）。
4. **按类别设阈值、按类别设处理方式**：把 `threshold` 改成 `dict[str, float]`；命中 `self-harm` 时返回支持性回复和求助资源，命中 `harassment` 时清洗后继续，命中 `illicit/violent` 时拒绝，边界分数转人工队列。
5. **层内并行**：用 `asyncio.gather` 同时调用三个（模拟的）分类器，聚合策略为"任一命中即拦截"，测量与串行版本的耗时差（测验 Q12）。
6. **讲义练习 4**：为代码助手设计自定义规则：输出侧扫描硬编码密钥与危险 shell 命令，输入侧检测大段粘贴内容中的注入指令；为每条规则写一条应命中与一条不应命中的测试用例。

---

## 8. 常见坑

- **以为输出层被测试过**：demo 的 6 条示例没有一条触发输出层，而且在当前模型桩下它不可能触发。为每一层单独设计测试用例。
- **子串匹配误报**：`kill` 会匹配 `skills`，`bomb` 会匹配 `photobomb`；技术语境（kill process、exploit、payload）在代码类产品中非常常见。
- **一个阈值管所有类别**：不同类别的风险与误报代价不同，阈值应分别校准；分数离散时阈值甚至不起作用。
- **把内部策略文本直接展示给用户**：`custom_msg` 是给系统看的政策说明，不是用户文案。
- **把模拟函数当真实 API**：`openai_moderation` 只是同名的玩具实现；真实 API 需要网络与 key，返回结构也更丰富（每类的 flag、score，以及该类别适用的输入类型）。
- **忽视多模态覆盖的缺口**：真实 omni-moderation 的图片输入只覆盖 violence、self-harm、sexual，不覆盖 sexual/minors（讲义原文），图片产品需要额外检测。
- **讲义与自带 quiz.json 的日期不一致**：讲义写 Azure Content Moderator "retired February 2027"，`quiz.json` 写 "retired March 15, 2027"。迁移计划应以官方公告为准，并预留余量。
- **中文讲义机翻错误**：摘要把 "14 MLCommons hazards" 译成了"14个刚果解放运动危险"（MLC 被误当作刚果解放运动的缩写），把 Llama Guard 译成"Llama 卫兵 / 警卫"，把 Azure Content Moderator "deprecated February 2024" 译成了"2024年2月退役"（实际 2024 年 2 月是弃用、2027 年 2 月才退役）。以英文讲义为准。
- **Llama Guard 类别数的表述**：讲义摘要写 "14 MLCommons hazards, Code Interpreter Abuse"，容易误读为"14 + 1 = 15 类"；正文与 Key Terms 统一写作"14 类"，SVG 图注也写 "Llama Guard 3 (14 categories) ... + code-interpreter-abuse"。以 14 类为准。
