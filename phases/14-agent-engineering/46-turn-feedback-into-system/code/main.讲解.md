# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 46 节 把每一次对 Agent 的纠正转化为系统改进 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在小节目录下 `python3 code/main.py`；测试 `python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`hashlib`、`json`、`re`、`dataclasses`、`pathlib`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义的主张是：**纠正是关于工作系统的证据**，应当晋升为最早能防止复发的那一层控制（测试、scope、自动化、示例、指令、人类决策），并且要去重、要能退役。这份约 110 行的代码把这个流程做成了一个最小的"棘轮"（ratchet）：

1. **分类**：`choose_target` 根据症状和原因里的关键词，决定控制落在哪一层（对应讲义"Promote to the Earliest Effective Layer"表格）。
2. **规范化**：`normalize_cause` 把原因改写成"implicit X / unchecked X description / missing Y for X"这样的标准短语，让措辞不同的同一原因得到同一条规则。
3. **晋升**：`promote` 生成控制：规则文本、验证方式、指纹，并保留原始证据（症状、原因、复发次数、后果）。
4. **去重**：`ratchet` 用指纹去重并排序，写出 `outputs/feedback-ratchet.json`。

> 一句话：**把"别再这样做了"变成一条带验证方式、可去重的结构化控制记录**。同时要看清它的简化：关键词子串路由会误判、去重会丢失复发次数、没有后果门槛、没有 owner 与退役日期——这些正是讲义练习要你补的部分。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Correction` | frozen dataclass | 一次纠正：症状、原因、复发次数、后果 | 纠正是证据 |
| `Control` | frozen dataclass | 晋升后的控制：target、rule、verification、fingerprint + 原始证据 | Ratchet 记录（缺 owner/日期） |
| `choose_target` | 函数 | 关键词 → `test / scope / automation / example / instruction` | 最早有效层 |
| `normalize_cause` | 函数 | 三个正则把原因改写成标准短语 | 区分原因与措辞 |
| `promote` | 函数 | 组装 `Control`，计算 sha256 指纹 | 晋升 + 稳定身份 |
| `ratchet` | 函数 | 跳过 `recurrence < 1`，按指纹去重，按 (target, fingerprint) 排序 | 去重、确定性输出 |
| `example` | 函数 | 3 条示例纠正（越界、回归、环境） | 讲义三类典型纠正 |
| `main` | 函数 | 写 JSON 并打印 | 留存产物 |
| `tests/test_main.py` | 单元测试 | 7 个测试（见第 9 节） | 可执行验证 |

数据流：`example()` → `ratchet()`（逐条 `promote()` → `choose_target()` + `normalize_cause()` + sha256）→ `asdict` → `json.dumps` → `outputs/feedback-ratchet.json`。

---

## 3. 逐段精讲

### 3.1 两个数据类：纠正与控制

```python
@dataclass(frozen=True)
class Correction:
    symptom: str
    cause: str
    recurrence: int
    consequence: str


@dataclass(frozen=True)
class Control:
    target: str
    rule: str
    verification: str
    fingerprint: str
    symptom: str
    cause: str
    recurrence: int
    consequence: str
```

- `frozen=True`：实例创建后不可修改，适合"证据记录"——纠正发生后不应被悄悄改写；同时 frozen dataclass 自动可哈希，可放进 set 或作 dict 键。
- `Control` 把 `Correction` 的 4 个字段原样复制进来（测试 `test_control_retains_correction_evidence` 专门验证），保证每条控制都能追溯到"为什么存在"。
- 对照讲义的 ratchet 记录 8 个字段：症状 ✓、根因 ✓、后果 ✓、复发次数 ✓、所选控制（target + rule）✓、控制的验证 ✓、**owner ✗、复审/退役日期 ✗**。缺的两项正是讲义练习 4。

### 3.2 `choose_target`：关键词路由到"最早有效层"

```python
def choose_target(correction: Correction) -> str:
    text = f"{correction.symptom} {correction.cause}".lower()
    if any(word in text for word in ("incorrect output", "regression", "edge case", "bug")):
        return "test"
    if any(word in text for word in ("scope", "unrelated file", "permission")):
        return "scope"
    if any(word in text for word in ("command", "setup", "environment", "tool")):
        return "automation"
    if any(word in text for word in ("format", "pattern", "example")):
        return "example"
    return "instruction"
```

与讲义表格的对应：

| 讲义：重复的失败 | 讲义：持久落点 | 代码 target |
|------|------|------|
| 错误结果或回归 | 测试或 evaluation | `test` |
| 越界或不安全操作 | scope 或权限策略 | `scope` |
| 重复的 setup / 命令错误 | 自动化或工具 | `automation` |
| 重复的输出格式错误 | 规范示例 + validator | `example` |
| 模糊的本地约定 | 指令 + 场景检查 | `instruction`（兜底） |
| 产品分歧 | 人类决策记录 | **无**（代码没有这一类） |

- 症状和原因拼在一起后转小写，再用 `word in text` 做**子串**匹配。`if` 的先后顺序就是隐含的优先级：test > scope > automation > example > instruction。
- ⚠️ 子串匹配的误判（已实际运行验证）：`"information"` 含 `"format"` → example；`"debug"` 含 `"bug"` → test；`"tooltip"` 含 `"tool"` → automation；`"incorrect output format"` 先命中 test，而讲义明确说格式错误应归到 example。修复见测验 Q10（`\b` 单词边界 + 负向前瞻）。
- ⚠️ 兜底是 `instruction`，意味着"没认出来的都写成指令"——而指令恰恰是讲义认为最弱的控制。生产中更好的做法是让记录者显式填写失败类型，关键词只给建议。

### 3.3 `normalize_cause`：把措辞不同的原因变成同一短语

```python
def normalize_cause(cause: str) -> str:
    text = cause.strip().rstrip(".").lower()
    implicit = re.fullmatch(r"(.+?) (?:was|were) implicit", text)
    if implicit:
        return f"implicit {implicit.group(1)}"
    unchecked = re.fullmatch(r"(.+?) was described but not checked", text)
    if unchecked:
        return f"unchecked {unchecked.group(1)} description"
    missing = re.fullmatch(r"(.+?) had no (.+)", text)
    if missing:
        return f"missing {missing.group(2)} for {missing.group(1)}"
    return text
```

| 输入 | 输出 |
|------|------|
| `environment assumptions were implicit` | `implicit environment assumptions` |
| `scope was described but not checked` | `unchecked scope description` |
| `edge case had no executable example` | `missing executable example for edge case` |
| `Environment assumptions were implicit.` | `implicit environment assumptions`（去句号、转小写后相同） |
| `The environment assumptions were implicit` | `implicit the environment assumptions`（冠词没去掉） |
| `environment assumptions were not explicit` | 原样返回（同义表达未覆盖） |
| `scopes were described but not checked` | 原样返回（只写了 `was`） |
| `docs were implicitly considered safe` | 原样返回（讲义 README 例子中的原因，规则变成不通顺的 `Prevent docs were implicitly considered safe`） |

- `re.fullmatch` 要求**整串**匹配，避免只匹配一部分；`(.+?)` 是非贪婪捕获，`(?:was|were)` 是不捕获的分组。
- 规范化的作用是让"规则文本"成为一个**可比较的标准形式**，指纹就建立在它之上。讲义的 Build It 练习正是让你扩展这里，直到不同措辞合并、而不同原因不合并（参考实现见测验 Q11）。

### 3.4 `promote`：生成控制与稳定指纹

```python
def promote(correction: Correction) -> Control:
    target = choose_target(correction)
    rule = f"Prevent {normalize_cause(correction.cause)}"
    verification = {
        "test": "Run the new regression test",
        "scope": "Run the scope checker",
        "automation": "Run the setup or tool preflight",
        "example": "Compare the output with the canonical example",
        "instruction": "Run the instruction linter and scenario check",
    }[target]
    digest = hashlib.sha256(f"{target}|{rule}".encode()).hexdigest()[:12]
    return Control(target, rule, verification, digest, correction.symptom, ...)
```

- **每条控制都必须带验证方式**（讲义 ratchet 记录里的 "verification for the control"）：一条无法验证的控制，无法证明它在起作用，也无法安全退役。
- 字典字面量直接用 `[target]` 索引，相当于一个小型 switch；5 个 key 覆盖 `choose_target` 的全部返回值，所以不会 `KeyError`。
- **指纹** = `sha256("target|rule")` 的前 12 个十六进制字符（48 位）。选 sha256 而非内置 `hash()`：字符串的 `hash()` 每个进程随机加盐，写进文件后下次运行就对不上了。
- ⚠️ 指纹包含 `target`，而 target 由**症状**的关键词决定。同一个原因配上不同症状可能落到不同 target，从而得到两条控制（实际运行：`environment assumptions were implicit` 配 "Setup command failed" 得 `4583ddf9efe6`，配 "Regression in date parser" 得 `890f82010fa0`）。

### 3.5 `ratchet`：门槛、去重、排序

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

- **门槛**：只跳过 `recurrence < 1`。⚠️ 这意味着 `recurrence == 1` 的一次性纠正也会被晋升，且 `consequence` 完全不参与判断——与讲义"Do not promote every one-off preference... Promote a correction when recurrence or consequence justifies permanent complexity"不一致。示例里的回归（1 次、user-visible failure）按讲义值得晋升，但理由应是"后果严重"，代码却是"因为 ≥ 1"。练习 3 要求补上后果加权（见测验 Q12）。
- **去重**：以指纹为 dict 的键。⚠️ 重复指纹时是**后者覆盖前者**：复发次数不累加、先前的症状和后果丢失（见测验 Q4、Q9）。
- **排序**：按 `(target, fingerprint)` 排序，保证每次运行输出顺序一致，JSON 文件可以稳定地做 diff。

### 3.6 示例与 `main`

```python
def example() -> list[Correction]:
    return [
        Correction("Agent edited an unrelated file", "scope was described but not checked", 2, "review churn"),
        Correction("A regression escaped", "edge case had no executable example", 1, "user-visible failure"),
        Correction("Setup command failed", "environment assumptions were implicit", 3, "lost session"),
    ]


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "outputs" / "feedback-ratchet.json"
    output.write_text(json.dumps([asdict(item) for item in ratchet(example())], indent=2) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))
```

- 三条示例正好对应讲义开头的三种纠正："do not edit that file"（scope 不可执行）、"output shape is wrong / regression"（缺测试或示例）、"setup fails again"（环境知识应进自动化）。
- `Path(__file__).resolve().parents[1]`：`main.py` 的绝对路径 → 上一级的上一级目录，即小节目录；所以无论从哪个工作目录运行，都写到 `<小节>/outputs/`。
- ⚠️ 每次运行都会**覆盖** `outputs/feedback-ratchet.json`。因为输入固定、输出确定，覆盖后内容不变（已用 diff 验证）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 关键词子串路由 | 零依赖、易读 | 误判（information/debug/tooltip）；生产中用结构化 `failure_kind` 字段 + 人工确认，或 LLM 分类后人工复核 |
| 三个正则做规范化 | 演示"措辞 → 标准短语"的思路 | 覆盖面很窄（冠词、were、同义表达都会漏）；可以用受控词表或 LLM 改写成标准短语再哈希 |
| sha256 截断 12 位做指纹 | 确定性、跨进程稳定、足够短便于阅读 | 48 位在小规模下碰撞概率可忽略；指纹包含 target 导致同因不同症状被拆分 |
| dict 覆盖去重 | 实现最简单 | 复发次数被低估、证据丢失；应合并计数与症状 |
| `recurrence ≥ 1` 即晋升 | 示例里每条都能看到输出 | 违背"不固化一次性偏好"；应加后果加权门槛 |
| frozen dataclass | 证据不可变、可哈希 | 合并时需用 `dataclasses.replace` 生成新对象 |
| 输出排序 | JSON 稳定，便于 code review | 无 |
| 无 owner、无退役日期、无"人类决策"类 | 控制代码量 | 讲义"Controls Also Decay"一节在代码中没有体现；后续第 54 节专门补上 owner 与退役条件 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟类型注解求值，注解按字符串保存；旧版本 Python 也能写 `list[Correction]` |
| `@dataclass(frozen=True)` | `class Correction` | 自动生成 `__init__`、`__repr__`、`__eq__`；frozen 后字段不可赋值，并自动生成 `__hash__` |
| `dataclasses.asdict` | `asdict(item)` | 把 dataclass 递归转成 dict，便于 `json.dumps` |
| 类型注解 | `def ratchet(corrections: list[Correction]) -> list[Control]`、`promoted: dict[str, Control] = {}` | 仅作文档与静态检查用，运行时不强制 |
| f-string | `f"{correction.symptom} {correction.cause}"`、`f"Prevent {...}"` | 字符串插值 |
| `any()` + 生成器表达式 | `any(word in text for word in (...))` | 只要有一个为真就返回 True，并且短路求值 |
| `in` 做子串判断 | `word in text` | 对字符串是"子串包含"，不是"单词相等"——误判的根源 |
| 字符串方法链 | `cause.strip().rstrip(".").lower()` | 去首尾空白 → 去末尾句点 → 转小写 |
| `re.fullmatch` | `re.fullmatch(r"(.+?) (?:was|were) implicit", text)` | 整串匹配；`r""` 原始字符串避免反斜杠转义；`(.+?)` 非贪婪捕获；`(?:...)` 非捕获分组 |
| `match.group(n)` | `implicit.group(1)` | 取第 n 个捕获组 |
| 匹配结果判空 | `implicit = re.fullmatch(...)` 后 `if implicit:` | 未匹配时返回 `None`，在 `if` 中为假；Python 3.8+ 也可写成 `if (m := re.fullmatch(...)):`（海象运算符） |
| 字典字面量直接索引 | `{...}[target]` | 一种简洁的"switch" |
| `hashlib` | `hashlib.sha256(s.encode()).hexdigest()[:12]` | `encode()` 默认 UTF-8 转 bytes；`hexdigest()` 得 64 位十六进制字符串；切片取前 12 位 |
| `continue` | `if correction.recurrence < 1: continue` | 跳过本轮循环 |
| `sorted` + `lambda` 返回元组 | `key=lambda item: (item.target, item.fingerprint)` | 先按 target、再按 fingerprint 排序 |
| 列表推导式 | `[asdict(item) for item in ratchet(example())]` | 逐个转换 |
| `pathlib.Path` | `Path(__file__).resolve().parents[1] / "outputs" / "..."` | `parents[1]` 是上两级目录；`/` 拼接路径；`write_text/read_text` 读写文件 |
| `json.dumps(..., indent=2)` | `main` 中 | 带缩进的 JSON |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被测试导入时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，在小节目录的副本中执行，输出与仓库内 `outputs/feedback-ratchet.json` 逐字节相同）：

```text
[
  {
    "target": "automation",
    "rule": "Prevent implicit environment assumptions",
    "verification": "Run the setup or tool preflight",
    "fingerprint": "4583ddf9efe6",
    "symptom": "Setup command failed",
    "cause": "environment assumptions were implicit",
    "recurrence": 3,
    "consequence": "lost session"
  },
  {
    "target": "scope",
    "rule": "Prevent unchecked scope description",
    "verification": "Run the scope checker",
    "fingerprint": "84a04b190176",
    ...
    "recurrence": 2,
    "consequence": "review churn"
  },
  {
    "target": "test",
    "rule": "Prevent missing executable example for edge case",
    "verification": "Run the new regression test",
    "fingerprint": "a615a06d2823",
    ...
    "recurrence": 1,
    "consequence": "user-visible failure"
  }
]
```

逐项解读：

- **顺序**：输出按 target 字母序（automation < scope < test），而不是输入顺序，也不是按复发次数或严重性——这是为了输出稳定，不代表优先级。
- **automation**：症状里有 `setup`、`command`，原因里有 `environment`，三个词都指向 automation；规则 `Prevent implicit environment assumptions` 来自 "implicit" 正则。
- **scope**：`"unrelated file"` 和 `"scope"` 都命中；规则来自 "described but not checked" 正则。
- **test**：`"regression"` 命中。注意原因里还有 `"example"`，但 test 规则排在前面，所以没落到 example。规则来自 "had no" 正则。
- **指纹**：可以自己验证，`hashlib.sha256(b"scope|Prevent unchecked scope description").hexdigest()[:12]` 得 `84a04b190176`。
- **recurrence 1 也被晋升**：第三条只发生过一次，被晋升是因为门槛只要求 ≥ 1，而不是因为代码识别出了 "user-visible failure" 的严重性。

---

## 7. 动手改一改

1. **讲义 Build It**：在 `example()` 里加两条措辞不同、原因相同的纠正（如 `"The environment assumptions were implicit."` 和 `"environment assumptions were not explicit"`），改进 `normalize_cause` 直到它们合并为一条控制；再加一条 `"permission assumptions were implicit"`，确认它**没有**被合并。
2. **修关键词路由**：把子串匹配换成 `\b` 单词边界正则，处理 `information/debug/tooltip/incorrect output format` 四个误判（参考测验 Q10），并给每个误判写一个回归测试。
3. **合并去重**：改写 `ratchet`，重复指纹时累加 `recurrence`、合并症状、consequence 取更严重者（参考测验 Q9）。
4. **讲义练习 3**：实现 `should_promote`：复发 ≥ 2 或后果严重才晋升；加测试"`typo / one-off / 1 / none` 不被晋升"。
5. **讲义练习 4**：给 `Control` 加 `owner`、`review_after`、`retire_when` 字段，写一个 `due_for_review(controls, today)` 函数列出到期的控制。
6. 进阶：加第 6 类 target `decision`（产品分歧 → 人类决策记录），验证方式为"决策记录已链接到 issue 且有决策人签名"；思考为什么这一类**不应该**由关键词自动路由。

---

## 8. 常见坑

- **把症状当原因写规则**："不要改 README"在下次改 CHANGELOG 时就失效。先问"系统里缺了什么"。
- **子串匹配当单词匹配**：`"bug" in "debug"` 为 True。分类器的规则顺序也是一种策略，改动时要回归全部用例。
- **用 `hash()` 做持久化指纹**：跨进程不稳定，下次运行会把同一条教训记成新的。
- **去重时丢证据**：dict 覆盖会让最常见的失败看起来最不常见。
- **只晋升、不退役**：控制会随架构变化而过时、互相冲突、挤占上下文；每条控制都需要 owner 和复审日期。
- **删除旧指令前没有证明替代控制有效**：讲义练习 5 要求"只有在证明存在更强控制后才删除"。
- **以为 `frozen=True` 能防住一切修改**：它阻止的是字段重新赋值；如果字段本身是可变对象（如 list），里面的内容仍可被修改。

---

## 9. 测试在验证什么

`code/tests/test_main.py` 用 `importlib.util.spec_from_file_location` 按**文件路径**加载 `main.py`（注册为模块名 `lesson46`），所以无论从哪个目录运行都能找到被测模块，也不会和其它小节同名的 `main` 冲突。

| 测试 | 验证的性质 |
|------|-----------|
| `test_scope_correction_becomes_scope_control` | 示例第 1 条（越界编辑）路由到 `scope` |
| `test_regression_becomes_test` | 示例第 2 条（回归）路由到 `test` |
| `test_environment_failure_becomes_automation` | 示例第 3 条（环境/setup）路由到 `automation` |
| `test_control_retains_correction_evidence` | 控制保留了原纠正的症状、原因、复发次数、后果——可追溯性 |
| `test_rules_use_grammatical_cause_phrases` | 三个正则都产出通顺的规则文本（`Prevent unchecked scope description` 等） |
| `test_duplicate_controls_are_collapsed` | 同一条纠正输入两次只得到一条控制 |
| `test_zero_recurrence_is_not_promoted` | `recurrence == 0` 不晋升 |

运行方式（在小节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：

```text
Ran 7 tests in 0.001s

OK
```

测试**没有覆盖**的地方（也就是第 3 节标注 ⚠️ 的问题）：

- 去重测试用的是两条**完全相同**的纠正，只断言数量为 1，没有检查合并后的 `recurrence`，所以"后者覆盖前者"的问题没被发现；
- 没有任何关键词误判的反例（`information`、`debug`、`tooltip`）；
- 没有测试 `recurrence == 1` 但后果轻微的一次性纠正——按讲义它不该被晋升；
- 没有测试"措辞不同、原因相同"的合并，这正是讲义 Build It 练习的目标。
