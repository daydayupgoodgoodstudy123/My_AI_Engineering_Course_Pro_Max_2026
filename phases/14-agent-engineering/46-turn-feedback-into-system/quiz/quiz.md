# 测验 · 把每一次对 Agent 的纠正转化为系统改进（Turn Every Agent Correction into a System Improvement）

> **阶段 14 · Agent 工程 · 第 46 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 纠正是证据 | 对 agent 说"别改那个文件"，说明 scope 边界不可执行；把纠正当作对**工作系统**的观察，而不是 prompt 写得不好 |
| 2 | 只活在聊天里的纠正只修一次运行 | 讲义："A correction that lives only in chat fixes one run"；晋升为 test、边界、示例或工具后，才会改进之后的每一次运行 |
| 3 | 最早有效层（earliest effective layer） | 错误结果/回归 → test 或 evaluation；越界/不安全 → scope 或权限策略；重复 setup/命令错误 → 自动化或工具；格式错误 → 规范示例 + validator；模糊约定 → 带场景检查的指令；产品分歧 → 人类决策记录 |
| 4 | 控制的强弱 | 越早越便宜：阻止非法状态的类型 > 事后发现它的 review 评论；聚焦的测试 > 一段"请 agent 记住"的文字 |
| 5 | Ratchet 记录（棘轮记录） | 8 个字段：症状、根因、后果、复发次数、所选控制、控制的验证方式、负责人、复审/退役日期 |
| 6 | 晋升门槛 | 不要把每个一次性偏好都固化；当**复发次数或后果严重性**足以证明值得付出永久复杂度时才晋升 |
| 7 | 区分原因与症状 | "agent 改了 README"是症状，可能的原因有 4 种（任务允许仓库根、文档被默认安全、计划捆绑实现与文档、两个 worker 所有权重叠），每种原因对应不同控制 |
| 8 | 控制也会衰减 | 架构变了、被更强的可执行控制取代、在有意义的窗口内不再复发、摩擦大于风险 → 删除或重写 |
| 9 | 稳定指纹去重 | 代码用 `sha256(target|rule)[:12]` 作为控制的身份，同一教训只保留一条；sha256 跨进程稳定，Python 内置 `hash()` 对字符串则不稳定 |
| 10 | 代码的简化之处 | 关键词子串路由（会误判）、去重时后者覆盖前者（复发次数不累加）、`recurrence ≥ 1` 即晋升（不看后果）、没有 owner/退役日期、没有"人类决策"这一类 |

### 核心技能（能动手做到）

- [ ] 拿到一条纠正，能写出症状、根因、后果，并把它分到讲义表格里的 6 类目标之一
- [ ] 能说出"为什么这条规则应该是一个测试/类型/脚本，而不是一段指令"
- [ ] 读懂 `choose_target` → `normalize_cause` → `promote` → `ratchet` 的数据流，手推任意输入的 target、rule 和指纹是否相同
- [ ] 能找出关键词子串匹配、去重覆盖、指纹包含 target 这三类实现缺陷，并给出修复代码
- [ ] 给 ratchet 加上后果加权、owner 与复审日期（讲义练习 3、4）
- [ ] 能为一条已有的 agent 指令设计"退役检查"：证明存在更强的控制后再删除

---

## 二、基础自测（选择题）

**Q1.** 一个 agent 连续三次把 JSON 输出的字段名写成了驼峰（团队约定是下划线）。按讲义的"最早有效层"表格，这条纠正最应该晋升为：

- A. 规范示例（canonical example）加 validator
- B. 在 AGENTS.md 里再加一段加粗的"字段名必须用下划线"
- C. 一条人类决策记录
- D. scope / 权限策略

**Q2.** 讲义列出了几种"应删除或重写某条控制"的情形。下面哪一项**不在**其中？

- A. 底层架构已经变了
- B. 已有更强的可执行控制取代了它
- C. 在一个有意义的时间窗口内，该失败没有再复发
- D. 这条控制已经存在超过 30 天

**Q3.** 对本节代码执行：

```python
choose_target(Correction("Missing information in incident summary",
                         "summary template was vague", 2, "rework"))
```

返回值是：

- A. `"test"`
- B. `"example"`
- C. `"instruction"`
- D. `"automation"`

**Q4.** 用本节的 `ratchet` 处理下面两条纠正，结果是：

```python
a = Correction("Setup command failed", "environment assumptions were implicit", 3, "lost session")
b = Correction("Install broke on CI", "Environment assumptions were implicit.", 2, "blocked PR")
ratchet([a, b])
```

- A. 两条控制，因为两条纠正的症状不同
- B. 一条控制，`recurrence == 5`，两个症状都被保留
- C. 一条控制，`symptom == "Install broke on CI"`、`recurrence == 2`
- D. 一条控制，`symptom == "Setup command failed"`、`recurrence == 3`

**Q5.** 代码用 `hashlib.sha256(...).hexdigest()[:12]` 生成指纹，而不是 Python 内置的 `hash()`。最主要的原因是：

- A. sha256 比 `hash()` 快
- B. `hash()` 不能接受字符串参数
- C. sha256 截断到 12 位后仍能保证绝对不碰撞
- D. 字符串的 `hash()` 每个进程会随机加盐（`PYTHONHASHSEED`），指纹跨运行不稳定，无法写进文件做长期去重

**Q6.** 你发现 agent 又一次修改了 README。按讲义，最合适的下一步是：

- A. 先找根因（任务允许仓库根目录？文档被默认视为安全？计划把实现和文档捆在一起？两个 worker 所有权重叠？），再把控制放到对应的那一层
- B. 在指令里加一句"不要修改 README"
- C. 换一个更强的模型
- D. 记在聊天里，下次再犯时提醒它

**Q7.** 按本节代码，`ratchet([Correction("typo", "one-off", 1, "none")])` 的结果是：

- A. 空列表，因为 consequence 是 `"none"`
- B. 空列表，因为 recurrence 必须大于 1
- C. 一条 `target="instruction"`、`rule="Prevent one-off"` 的控制
- D. 抛出 `KeyError`

**Q8.** 按讲义"Earlier controls are cheaper"的观点，下面哪个排序是**从强到弱**？

- A. review 评论 > 聚焦测试 > 类型约束
- B. 阻止非法状态的类型 > 聚焦测试 > 一段请 agent 记住的文字
- C. 一段请 agent 记住的文字 > 聚焦测试 > 类型约束
- D. 三者强度相同，只是写法不同

---

## 三、动手 / 代码题

**Q9.**（读代码找 bug）`ratchet` 的去重逻辑如下：

```python
def ratchet(corrections: list[Correction]) -> list[Control]:
    promoted: dict[str, Control] = {}
    for correction in corrections:
        if correction.recurrence < 1:
            continue
        control = promote(correction)
        promoted[control.fingerprint] = control
    return sorted(promoted.values(), key=lambda item: (item.target, item.fingerprint))
```

1. 结合 Q4 的输入，说明同一指纹出现两次时丢失了哪些信息，为什么这和讲义"Capture recurrence count"的意图矛盾。
2. 改写 `ratchet`：同一指纹的控制合并时把 `recurrence` 相加，并保留所有不同的症状。

**Q10.**（关键词路由的误判）`choose_target` 用 `word in text` 做子串匹配，按 test → scope → automation → example 的顺序判断。实际运行结果：

| 症状 + 原因 | 代码返回 | 期望 |
|------|------|------|
| `"Missing information in incident summary"` + `"summary template was vague"` | `example` | `instruction` |
| `"Agent ran the debug script twice"` + `"no preflight"` | `test` | 不应是 `test` |
| `"incorrect output format"` + `"no canonical example"` | `test` | `example`（讲义：格式错误 → 示例 + validator） |
| `"Tooltip text wrong"` + `"copy was vague"` | `automation` | `instruction` |

1. 逐行解释为什么会得到这些结果。
2. 写一个改进版 `choose_target`，修掉这四个误判，并保证本节 `example()` 里三条纠正的结果不变。

**Q11.**（讲义"Build It"练习）讲义要求："加两条措辞不同但原因相同的纠正，改进 normalization，直到它们合并成一条控制，同时不把无关的失败合并。"实际运行 `normalize_cause` 得到：

```text
'environment assumptions were implicit'      -> implicit environment assumptions
'The environment assumptions were implicit.' -> implicit the environment assumptions
'environment assumptions were not explicit'  -> environment assumptions were not explicit
'the scope was described but not checked'    -> unchecked the scope description
```

1. 哪几条本应合并却没有合并？原因分别是什么？
2. 写一个 `normalize_cause` 的改进版。
3. 即使 rule 完全相同，两条纠正仍可能得到不同指纹。为什么？（提示：看指纹的输入。）

**Q12.**（讲义练习 3、4）当前代码只要 `recurrence ≥ 1` 就晋升，完全不看 `consequence`；输出也没有 owner 与复审日期。请：

1. 写一个 `should_promote(correction)`：复发次数 ≥ 2 时晋升；首次出现但后果严重（如 `"user-visible failure"`、`"data loss"`）时也立即晋升；其余一次性纠正不晋升。
2. 说明 `Control` 应新增哪些字段来支持"退役检查"，并给出默认值策略。

---

## 四、面试高频题

**Q13.**（基础必考）用户在会话里纠正了 coding agent 的一个错误。你会怎样把这次纠正变成系统层面的改进，而不只是"这次改对了"？

**Q14.**（原理深挖）为什么说"把规则写进 prompt / 指令文件"往往是最弱的一种控制？什么情况下它又是合适的？

**Q15.**（工程实践）设计一个"纠正 → 控制"的去重机制。指纹应该基于什么？怎样避免把措辞不同的同一教训记成两条，又不把不同原因的教训合并成一条？

**Q16.**（场景设计）团队的 AGENTS.md 已经膨胀到 800 行，agent 依然反复犯同样的错误，而且有些规则互相矛盾。你会如何治理？

**Q17.**（追问型）Reflexion 也会把失败反思存下来、改进下一次尝试。它和本节的"feedback ratchet"有什么区别？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义表格："Repeated output-format mistake → Canonical example plus validator"。规范示例让 agent 有可模仿的样本，validator 让错误在机器层面被拦下。B 是"再写一段文字"，正是讲义说的较弱控制（"A focused test is stronger than a paragraph asking the agent to remember"）；C 用于产品分歧；D 用于越界或不安全的行为。

### Q2 — 答案：D

讲义的四个条件是：底层架构变了；被更强的可执行控制取代；失败在有意义的窗口内没有复发；控制带来的摩擦大于它防止的风险。"存在超过 30 天"是一个与风险无关的固定期限，不是退役理由——讲义强调的是"meaningful window"内的复发证据，而不是控制本身的年龄。

### Q3 — 答案：B

拼接后的文本为 `"missing information in incident summary summary template was vague"`。test、scope、automation 的关键词都不命中，但 `"format"` 是 `"information"` 的**子串**（in-**format**-ion），于是返回 `"example"`。这是子串匹配的典型误判，期望结果应是 `"instruction"`。A 需要 "regression/bug" 等词；D 需要 "command/setup/environment/tool"；C 是正确的期望值，却不是代码的实际输出。

### Q4 — 答案：C

两条的 `cause` 经 `normalize_cause` 后都变成 `"implicit environment assumptions"`（去掉末尾句号并转小写），target 都是 `automation`（文本含 `environment`），所以指纹相同（`4583ddf9efe6`）。`promoted[fingerprint] = control` 是**直接覆盖**，后出现的 `b` 替换了 `a`：实际输出是一条控制，`symptom="Install broke on CI"`、`recurrence=2`。A 错在指纹只看 target 与 rule，不看症状；B 是"应该"的行为但代码没实现（见 Q9）；D 把覆盖方向说反了。

### Q5 — 答案：D

自 Python 3.3 起，`str`/`bytes` 的 `hash()` 默认启用随机化，每个解释器进程的结果不同，除非固定 `PYTHONHASHSEED`。指纹要写进 `feedback-ratchet.json`、跨会话比较，就必须是确定性的内容哈希。A 不是动机（这里性能无关紧要）；B 错误，`hash()` 可以接受字符串；C 错误，截断到 12 个十六进制字符（48 位）只是"碰撞概率很低"，不是保证。

### Q6 — 答案：A

讲义"Separate Cause from Symptom"一节：同一症状可能来自 4 种不同原因，每种原因属于不同的控制（scope 合同、文档写权限策略、计划拆分、worker 所有权隔离）。B 只是复述症状的规则，"在下一个略有不同的情况下会失败"（比如下次改的是 CHANGELOG）；C 把系统问题归咎于模型；D 让纠正继续"只活在聊天里"。

### Q7 — 答案：C

`ratchet` 只跳过 `recurrence < 1` 的纠正，`recurrence == 1` 会被晋升；`consequence` 完全不参与判断。`"one-off"` 不匹配任何正则，也不含任何关键词，于是 target 为 `instruction`，rule 为 `"Prevent one-off"`（已实际运行验证）。这与讲义"Do not promote every one-off preference"相矛盾——讲义练习 3 正是要求加上后果加权（见 Q12）。A、B 是"合理的设计"但不是代码的实际行为；D 错，`verification` 字典覆盖了全部 5 个 target。

### Q8 — 答案：B

讲义原文："A type that prevents an invalid state is stronger than a review comment that catches it later. A focused test is stronger than a paragraph asking the agent to remember." 类型/结构让错误状态**无法表达**；测试让错误**无法悄悄通过**；文字只能**期望**被遵守。A、C 方向相反；D 忽略了"可执行性"带来的差别。

### Q9 — 参考答案

1. 以 Q4 为例：`a` 的症状 `"Setup command failed"`、复发次数 3、后果 `"lost session"` 全部丢失，最终记录只剩 `b` 的 `recurrence=2`。讲义要求记录复发次数，是为了判断"这个教训是否值得永久复杂度"；去重后复发次数反而变小（真实是 3+2=5 次），会**系统性低估**最常见的失败。同时，不同症状正是"同一根因会以多种形式出现"的证据，被覆盖后无法再回溯。另外，测试 `test_duplicate_controls_are_collapsed` 只用两条**完全相同**的纠正验证"数量为 1"，没有检查合并后的字段，所以这个问题没被发现。

2. 参考实现（已实际运行：Q4 的输入得到 `symptom="Setup command failed | Install broke on CI"`、`recurrence=5`，指纹仍为 `4583ddf9efe6`）：

```python
from dataclasses import replace

def ratchet(corrections: list[Correction]) -> list[Control]:
    promoted: dict[str, Control] = {}
    for correction in corrections:
        if correction.recurrence < 1:
            continue
        control = promote(correction)
        old = promoted.get(control.fingerprint)
        if old is None:
            promoted[control.fingerprint] = control
            continue
        symptoms = old.symptom.split(" | ")
        promoted[control.fingerprint] = replace(
            old,
            recurrence=old.recurrence + control.recurrence,
            symptom=old.symptom if control.symptom in symptoms
                    else f"{old.symptom} | {control.symptom}",
        )
    return sorted(promoted.values(), key=lambda item: (item.target, item.fingerprint))
```

要点：`Control` 是 `frozen=True` 的 dataclass，不能直接改字段，要用 `dataclasses.replace` 生成新对象。更规范的做法是把 `symptom` 改成 `tuple[str, ...]`，并为 consequence 取"最严重的那一个"。注意：同一条纠正重复输入两次会被计为 3+3=6 次，生产中应给每条纠正一个唯一 ID，防止重复计数。

### Q10 — 参考答案

1. 逐行原因：
   - `"information"` 包含子串 `"format"` → 命中 example。
   - `"debug"` 包含子串 `"bug"` → 命中 test（test 规则排在最前）。
   - `"incorrect output format"` 先命中 test 的 `"incorrect output"`；test 优先级高于 example，于是格式问题被当成回归。
   - `"tooltip"` 包含子串 `"tool"` → 命中 automation。

2. 参考实现：用 `\b` 单词边界，并用负向前瞻把 "incorrect output format" 让给 example 规则：

```python
import re

RULES = [
    ("test", r"\b(regression|edge case|bug|incorrect output)\b(?! format)"),
    ("scope", r"\b(scope|unrelated file|permission)\b"),
    ("automation", r"\b(command|setup|environment|tool)\b"),
    ("example", r"\b(format|pattern|example)\b"),
]

def choose_target(correction: Correction) -> str:
    text = f"{correction.symptom} {correction.cause}".lower()
    for target, pattern in RULES:
        if re.search(pattern, text):
            return target
    return "instruction"
```

实际运行：四个误判分别变为 `instruction`、`instruction`、`example`、`instruction`；`example()` 的三条仍为 `scope`、`test`、`automation`。

注意一个陷阱：如果只是简单地把 example 规则挪到最前面，`"A regression escaped"` 会因为原因里的 `"executable example"` 被误判成 example——**规则顺序本身就是隐含的优先级策略**，改动时要跑全部用例。更稳健的做法是让纠正记录者显式填写 `failure_kind`（结构化字段），关键词只作为默认建议。

### Q11 — 参考答案

1. 第 1、2 条应合并：第 2 条多了冠词 `the`，正则 `(.+?) (?:was|were) implicit` 把 `the environment assumptions` 整体捕获，得到 `implicit the environment assumptions`。第 3 条 "not explicit" 与 "implicit" 语义相同，但不匹配任何模式，原样返回。第 4 条同样被冠词 `the` 拖累。此外，多个连续空格也不会被压缩（`"  Environment   assumptions were implicit"` 会得到 `implicit environment   assumptions`）。

2. 参考实现（已实际运行：上述 4 条分别得到 `implicit environment assumptions` ×3 和 `unchecked scope description`，原有 3 个测试用例结果不变）：

```python
def normalize_cause(cause: str) -> str:
    text = re.sub(r"\s+", " ", cause.strip().rstrip(".").lower())
    text = re.sub(r"^(the|a|an|our) ", "", text)
    implicit = re.fullmatch(r"(.+?) (?:was|were) (?:implicit|not explicit|left implicit)", text)
    if implicit:
        return f"implicit {implicit.group(1)}"
    unchecked = re.fullmatch(r"(.+?) (?:was|were) described but not checked", text)
    if unchecked:
        return f"unchecked {unchecked.group(1)} description"
    missing = re.fullmatch(r"(.+?) had no (.+)", text)
    if missing:
        return f"missing {missing.group(2)} for {missing.group(1)}"
    return text
```

"不把无关失败合并"的检验：`"permission assumptions were implicit"` 仍得到 `implicit permission assumptions`，与 environment 那条不同。

3. 指纹是 `sha256(f"{target}|{rule}")`，而 target 由**症状 + 原因**的关键词决定。同一个原因 `"environment assumptions were implicit"`，如果一次的症状是 `"Setup command failed"`（→ automation），另一次是 `"Regression in date parser"`（→ test），就会得到两个指纹（实际运行：`4583ddf9efe6` 与 `890f82010fa0`）。这说明"控制放在哪一层"和"教训是否相同"被耦合在一起了。可以改为只用规范化后的根因做指纹，再让 target 作为可修改的属性。

### Q12 — 参考答案

1. 参考实现：

```python
SEVERE = {"user-visible failure", "data loss", "security incident", "production outage"}

def should_promote(correction: Correction, min_recurrence: int = 2) -> bool:
    if correction.recurrence < 1:
        return False
    return correction.recurrence >= min_recurrence or correction.consequence in SEVERE
```

实际运行：示例中的 "unrelated file"（2 次）、"regression escaped"（1 次但 user-visible failure）、"setup command"（3 次）全部晋升；`("typo", "one-off", 1, "none")` 不晋升；`("Deleted prod table", ..., 1, "data loss")` 首次就晋升。在 `ratchet` 里把 `if correction.recurrence < 1` 换成 `if not should_promote(correction)` 即可。更进一步可以把 consequence 映射成 1–5 的严重度分，用 `recurrence × severity ≥ 阈值` 作门槛。

2. 新增字段与默认值：
   - `owner: str`：负责维护这条控制的人或团队，必填，不设默认值（没有 owner 的控制最终会变成没人敢删的"遗留规则"）；
   - `review_after: str`（ISO 日期）：例如 `date.today() + timedelta(days=90)`，严重后果可缩短为 30 天；
   - `retire_when: str`：退役条件，如 "架构迁移到 X 后" 或 "被 scope checker 覆盖后"；
   - 可选 `last_triggered: str`：最近一次真正拦截到问题的时间，用于判断"在有意义窗口内是否复发"。
   - 讲义 ratchet 记录本来就包含 "owner" 和 "date to review or retire it"，当前代码的 `Control` 漏掉了这两个字段。

### Q13 — 参考回答要点

- **记录**：症状、根因、后果、复发次数（讲义 ratchet 记录的 8 个字段）。
- **找根因**：区分症状与原因，问"系统里缺了什么，才让 agent 能犯这个错"。
- **判断是否晋升**：一次性偏好不晋升；复发或后果严重才晋升。
- **选最早有效层**：回归 → 测试/eval；越界 → scope/权限；重复 setup → 脚本/工具；格式 → 示例 + validator；模糊约定 → 指令 + 场景检查；产品分歧 → 人类决策记录。
- **验证控制本身**：新测试要先在旧代码上失败（证明它真能拦住）；scope checker 要能复现那次越界。
- **owner + 复审日期**，到期检查是否仍有价值。
- 加分点：说明这样做的效果是"下一次运行起点更高"（讲义 mermaid 的终点 "Next run starts stronger"），且不需要改模型权重。
- 常见误区：只在 CLAUDE.md/AGENTS.md 里加一句话就结束。

### Q14 — 参考回答要点

- **为什么弱**：指令是"期望"，依赖模型在长上下文中注意到并遵守；它没有失败信号，违反了也不会报错；随着指令文件变长，每条规则被注意到的概率下降，规则之间还可能冲突。
- **更强的替代**：类型/schema 让非法状态无法表达；测试让错误无法悄悄通过；scope checker/权限让越界操作无法执行；脚本让重复的 setup 步骤不依赖记忆。
- **什么时候指令合适**：本地约定确实模糊、难以机器检查时（讲义："Ambiguous local convention → Instruction with a scenario check"），且最好配一个场景检查验证 agent 确实理解。
- 加分点：引用讲义"The goal is not the longest instruction file. It is the smallest system that preserves hard-won judgment."
- 常见误区：把"加粗、全大写、重复三遍"当成加强控制。

### Q15 — 参考回答要点

- **指纹输入**：规范化后的**根因**（必要时加上控制类型），而不是原始症状文本；症状作为证据列表挂在控制下面。
- **规范化**：大小写、标点、空白、冠词、同义表达（"implicit" / "not explicit"）；也可以让 LLM 先把原因改写成受控词表里的标准短语，再做哈希。
- **哈希函数**：确定性的内容哈希（sha256 等），不能用进程随机化的 `hash()`。
- **防止过度合并**：保留一组"不应合并"的反例做回归测试；规范化规则只处理语法差异，不抹去关键名词（environment 与 permission 必须仍然不同）。
- **合并语义**：复发次数累加、症状取并集、后果取最严重值、保留每条原始纠正的 ID 以便回溯。
- 加分点：指出本节代码把 target 放进指纹，导致"同一根因、不同症状"被拆成多条（Q11 第 3 问）。

### Q16 — 参考回答要点

- **盘点**：为每条规则补齐 ratchet 记录——它防的是哪个失败？最近一次真正拦截是什么时候？owner 是谁？
- **晋升**：能变成可执行控制的规则（格式、scope、命令、回归）逐条改造成 validator、scope 检查、脚本、测试；**证明新控制能拦住问题后**再从文件中删除原文（讲义练习 5）。
- **退役**：架构已变、长期未复发、已被更强控制覆盖、摩擦大于风险的规则删除或重写。
- **去冲突**：矛盾的规则通常意味着一个未决的产品/团队决策，应升级为人类决策记录，而不是让 agent 自己选。
- **度量**：跟踪指令文件长度、每类失败的复发率，以及"新增控制数 vs 退役控制数"，防止只增不减。
- 常见误区：一次性大删，没有证据证明替代控制有效。

### Q17 — 参考回答要点

- **Reflexion**（讲义延伸阅读 Shinn et al.）：agent 在一次任务内或相邻几次尝试中，把失败反思写进情景记忆，下一次尝试以此为条件；反馈以**自然语言**形式存在，作用于**同一个 agent 的后续决策**，不改模型权重。
- **Feedback ratchet**：把纠正晋升为**工作系统**中的持久、可执行控制（测试、权限、脚本、示例），作用于**所有后续运行、所有 agent 甚至人类**，并且带验证、owner 与退役机制。
- **关键差异**：存储位置（记忆 vs 仓库里的工件）；执行强度（会被参考 vs 会被强制执行）；生命周期（随会话/记忆窗口 vs 有 owner 的版本化资产）；治理（无 vs 去重、复审、退役）。
- 加分点：两者可以组合——Reflexion 式反思产生候选教训，经过复发/后果门槛筛选后再晋升为 ratchet 控制。
- 常见误区：认为"让 agent 记住"就等于系统改进。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 37 运行时反馈循环](../../37-runtime-feedback-loops/docs/zh.md)：结构化记录命令输出，是发现"纠正"的数据来源。
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../33-instructions-as-executable-constraints/docs/zh.md)：把文字规则改造成可检查约束，正是本节"晋升"的目标形态之一。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：越界类纠正的落点。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：晋升后的测试与检查在这里被强制执行。
- [阶段 14 · 03 Reflexion：语言反馈驱动的 Reinforcement Learning](../../03-reflexion-verbal-rl/docs/zh.md)、[阶段 14 · 05 Self-Refine 与 CRITIC](../../05-self-refine-and-critic/docs/zh.md)：讲义延伸阅读，对比"任务内反馈"与"系统级棘轮"。

### 本节被哪些后续内容用到
- [阶段 14 · 54 建立持续反馈机制，明确负责人和退役条件](../../54-build-the-feedback-ratchet/docs/zh.md)：在本节基础上为每条控制补齐 owner 与退役条件。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：回归类纠正最终沉淀为 eval 用例。
- [阶段 14 · 52 在结果产生前设计成功指标](../../52-design-success-metrics/docs/zh.md)：讲义延伸阅读中的 GQM 方法在那里展开。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：把纠正转为测试与评估集的通用方法。

### 延伸关键词
`feedback ratchet` · `earliest effective layer` · `root cause vs symptom` · `canonical example + validator` · `regression test` · `scope policy` · `content-addressed fingerprint` · `PYTHONHASHSEED` · `control retirement` · `AGENTS.md / CLAUDE.md 治理` · `GQM` · `Reflexion`
