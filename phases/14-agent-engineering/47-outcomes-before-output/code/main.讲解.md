# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 47 节 先定义预期成效，再选择交付形式 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在小节目录下 `python3 code/main.py`；测试 `python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义的核心是"先写成效框架（outcome frame），再选产出"。这份约 75 行的代码把框架变成一个**数据结构 + 校验器**：

1. **六部分框架的数据化**：`OutcomeFrame` 的前 6 个字段正好对应讲义表格的 User、Situation、Current behavior、Desired outcome、Constraints、Non-goals；第 7 个字段 `proposed_output` 记录"有人已经想到的那个产物"。
2. **完整性校验**：四个文本字段不能为空，约束和 non-goals 至少各一条——讲义强调约束和 non-goals 不是可选项。
3. **方案泄漏检测**：如果 `desired_outcome` 里直接出现了 `proposed_output`，说明产出"渗进"了成效（讲义 Build It：把成效改成 "use the incident assistant"，校验器应报警）。
4. **把框架变成下一步**：`decision` 输出 status（`ready-to-discover` / `needs-framing`）和一个"证据问题"，对应讲义流程图最后的 "Evidence question"，并为第 48 节（发现真实工作流）提供输入。

> 一句话：**把"别急着做助手，先说清楚谁在什么情况下要得到什么、不能破坏什么、不做什么"变成一个可以被机器检查的 JSON**。它的检查很浅——只做"非空"和"整串子串"判断——看清这些局限是本节代码最有价值的部分。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `OutcomeFrame` | dataclass（可变） | 6 个框架字段 + 可选的 `proposed_output` | 六部分框架 |
| `validate` | 函数 | 返回问题列表：空字段、空列表、方案泄漏 | 完整性 + solution leakage |
| `decision` | 函数 | 组装 status、issues、frame、next_question | 框架 → 证据问题 |
| `example` | 函数 | 值班工程师 / 生产告警 / 事故助手的示例 | 讲义示例句 |
| `main` | 函数 | 写 `outputs/outcome-frame.json` 并打印 | 留存产物 |
| `tests/test_main.py` | 单元测试 | 6 个测试（见第 9 节） | 可执行验证 |

数据流：`example()` → `decision()`（内部调用 `validate()`，再 `asdict(frame)`）→ `json.dumps` → `outputs/outcome-frame.json`。

---

## 3. 逐段精讲

### 3.1 `OutcomeFrame`：把六部分框架写成字段

```python
@dataclass
class OutcomeFrame:
    user: str
    situation: str
    current_behavior: str
    desired_outcome: str
    constraints: list[str]
    non_goals: list[str]
    proposed_output: str = ""
```

| 字段 | 讲义中的问题 | 示例值 |
|------|------------|--------|
| `user` | 谁直接经历这个问题？ | on-call engineer |
| `situation` | 何时何地发生？ | a production alert arrives during an incident |
| `current_behavior` | 今天发生了什么，包括变通办法？ | searches three dashboards before finding the affected service |
| `desired_outcome` | 哪个可观察状态应改善？ | identifies the failing service and safe next action within two minutes |
| `constraints` | 哪些安全、政策、成本、兼容限制是固定的？ | read-only during diagnosis; must preserve the audit trail |
| `non_goals` | 排除哪些诱人的相邻工作？ | automatic remediation; replacing the incident commander |
| `proposed_output` | （讲义没有这一行）已经被提出的产物 | incident assistant |

- 这里**没有** `frozen=True`：测试会直接改字段（`frame.user = ""`）来构造反例。与第 46、48、49、50 节的 frozen dataclass 形成对比。
- `proposed_output` 有默认值 `""`，所以必须放在最后：dataclass 不允许无默认值字段出现在有默认值字段之后。
- 把 `proposed_output` 单独存下来是一个好设计：**不假装没人想到方案，而是把它隔离在成效之外**，然后检查它有没有渗进去。
- 讲义示例句"诊断仍然只读、可审计"在代码里被拆进了 `constraints`，`desired_outcome` 只保留可观察的改善。这正是"约束是成效的一部分，但要单独列出"的结构化写法。

### 3.2 `validate`：三类检查

```python
def validate(frame: OutcomeFrame) -> list[str]:
    issues: list[str] = []
    for name in ("user", "situation", "current_behavior", "desired_outcome"):
        if not getattr(frame, name).strip():
            issues.append(f"{name} is empty")
    if not frame.constraints:
        issues.append("constraints are empty")
    if not frame.non_goals:
        issues.append("non-goals are empty")
    if frame.proposed_output and frame.proposed_output.lower() in frame.desired_outcome.lower():
        issues.append("desired outcome names the proposed output")
    return issues
```

- **文本字段**：用 `getattr(frame, name)` 按名字取属性，避免写四遍几乎相同的 `if`；`.strip()` 让纯空白也算空。
- **列表字段**：`if not frame.constraints` 只判断列表是否为空。⚠️ `["  "]`、`[""]` 能通过检查（已实际运行验证）。
- **泄漏检测**：大小写不敏感的**整串子串**判断。
  - ✓ `"Uses the incident assistant"`、`"Use the Incident Assistant"` 会被检出。
  - ⚠️ 换个说法就漏：`"engineers use an AI incident helper"`、`"use the incident-assistant"`（连字符）都返回 `[]`。
  - ⚠️ `proposed_output` 为空时完全不检查，讲义列举的 "Deploy a vector database""weekly AI summary" 等泄漏都检测不到。
  - ⚠️ `proposed_output = " "` 时误报：空格是任何多词句子的子串。
- **返回问题列表而不是布尔值**：调用者能看到**所有**问题，而不是只知道"不合格"。issues 的顺序就是 `if` 的书写顺序。
- ⚠️ 讲义说"约束可以点名技术，但要记录为什么固定"，代码不检查约束是否附带理由；也不检查 non-goals 是否和 proposed_output 矛盾。
- ⚠️ 类型注解不在运行时生效：`user=None` 会在 `.strip()` 处抛 `AttributeError`。

### 3.3 `decision`：status 与证据问题

```python
def decision(frame: OutcomeFrame) -> dict:
    issues = validate(frame)
    return {
        "status": "ready-to-discover" if not issues else "needs-framing",
        "issues": issues,
        "frame": asdict(frame),
        "next_question": f"What evidence would show that the desired outcome was achieved for the {frame.user}?",
    }
```

- status 的命名很讲究：合格的 frame 下一步是 **discover**（第 48 节：去观察真实工作流），而不是 build。即使框架写好了，也还没有资格开始实现。
- `asdict(frame)` 把整个 frame 原样放进输出，让下游读 JSON 就能拿到全部上下文。
- `next_question` 对应讲义流程图的最后一个节点 "Evidence question"：把讨论从"做什么"转向"什么证据能说明成功"。
- ⚠️ 问题模板是固定的，只替换 user；即使 status 是 `needs-framing`（例如 user 为空白），也会生成 `"...achieved for the    ?"`。讲义练习 4（最早能证伪成效的观察）在代码中没有字段承载（改进方案见测验 Q11）。

### 3.4 示例与 `main`

```python
def example() -> OutcomeFrame:
    return OutcomeFrame(
        user="on-call engineer",
        situation="a production alert arrives during an incident",
        current_behavior="searches three dashboards before finding the affected service",
        desired_outcome="identifies the failing service and safe next action within two minutes",
        constraints=["read-only during diagnosis", "must preserve the audit trail"],
        non_goals=["automatic remediation", "replacing the incident commander"],
        proposed_output="incident assistant",
    )
```

- 用关键字参数构造，字段一目了然。
- 每次调用 `example()` 都会新建一个对象（包括新的 list），所以测试修改返回值不会影响其它测试——这是"用工厂函数而不是模块级常量"的好处。
- `main` 与其它小节相同：`Path(__file__).resolve().parents[1] / "outputs" / "outcome-frame.json"`，写入后再读出打印。⚠️ 每次运行会覆盖该文件（输入固定，内容不变）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 六部分框架 = 六个字段 | 让"缺哪一部分"可被机器发现 | 只能检查"有没有"，不能检查"好不好"（成效是否可观察、non-goal 是否具体） |
| 单独存 `proposed_output` | 承认方案已被提出，但把它隔离在成效之外 | 只记录一个方案；真实需求里常有多个候选产出 |
| 整串子串检测泄漏 | 一行实现，演示概念 | 换说法就漏报、空白误报、不识别讲义列举的五类泄漏；可加方案形式词表 + 单词边界 + 人工确认（测验 Q9） |
| 返回 issues 列表 | 一次看到所有问题 | 没有严重级别区分，泄漏和缺字段同等对待 |
| 可变 dataclass | 方便测试构造反例 | frame 可能在流转中被意外修改；生产中可用 frozen + `dataclasses.replace` |
| status 叫 `ready-to-discover` | 强调下一步是观察而不是实现 | 无 |
| 固定模板的证据问题 | 简单 | 不引用具体成效与阈值；应基于 `desired_outcome` 和证伪信号生成 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，允许写 `list[str]` 等新式注解 |
| `@dataclass`（非 frozen） | `class OutcomeFrame` | 自动生成 `__init__`/`__repr__`/`__eq__`；字段可以重新赋值 |
| 字段默认值与顺序 | `proposed_output: str = ""` 放最后 | 有默认值的字段之后不能再有无默认值字段，否则定义类时 `TypeError` |
| `list[str]` 字段 | `constraints: list[str]` | 没有默认值所以安全；若要默认空列表须写 `field(default_factory=list)`，不能写 `= []` |
| 类型注解不做运行时检查 | `user: str` 却能传 `None` | 注解只是提示，需要自己校验 |
| `getattr(obj, name)` | `getattr(frame, name).strip()` | 用字符串名取属性，适合循环处理多个字段 |
| `str.strip()` / `str.lower()` | `.strip()`、`.lower()` | 去首尾空白；转小写做大小写不敏感比较 |
| `in` 子串判断 | `proposed.lower() in desired.lower()` | 字符串的 `in` 是子串包含 |
| 空容器为假 | `if not frame.constraints:` | 空列表、空字符串在布尔上下文中为 False |
| 条件表达式 | `"ready-to-discover" if not issues else "needs-framing"` | 一行的 if/else |
| f-string | `f"{name} is empty"`、`f"...for the {frame.user}?"` | 字符串插值 |
| 关键字参数 | `OutcomeFrame(user=..., situation=..., ...)` | 按名传参，顺序无关、可读性高 |
| `dataclasses.asdict` | `"frame": asdict(frame)` | 递归转 dict（list 字段原样保留） |
| 返回类型注解 | `-> list[str]`、`-> dict`、`-> None` | 说明函数返回什么 |
| `pathlib` + `json` | `output.write_text(json.dumps(..., indent=2) + "\n", encoding="utf-8")` | 写带缩进的 JSON 文件 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，在小节目录副本中执行，输出与仓库内 `outputs/outcome-frame.json` 逐字节相同）：

```text
{
  "status": "ready-to-discover",
  "issues": [],
  "frame": {
    "user": "on-call engineer",
    "situation": "a production alert arrives during an incident",
    "current_behavior": "searches three dashboards before finding the affected service",
    "desired_outcome": "identifies the failing service and safe next action within two minutes",
    "constraints": [
      "read-only during diagnosis",
      "must preserve the audit trail"
    ],
    "non_goals": [
      "automatic remediation",
      "replacing the incident commander"
    ],
    "proposed_output": "incident assistant"
  },
  "next_question": "What evidence would show that the desired outcome was achieved for the on-call engineer?"
}
```

逐项解读：

- **status = ready-to-discover，issues 为空**：四个文本字段都非空，约束和 non-goals 各两条，`desired_outcome` 中没有出现 "incident assistant"。
- **desired_outcome 的质量**（代码检查不了，但值得人工确认）：有主体动作（identifies）、有可观察对象（failing service、safe next action）、有阈值（within two minutes），没有点名任何产物。
- **constraints** 正好对应讲义"Constraints Protect the Outcome"中的"no production writes during diagnosis"和"existing audit events remain authoritative"。
- **non_goals** 正好对应讲义列举的"no automatic remediation"和"no replacement of the incident commander"。
- **proposed_output 仍然被记录**：说明"有人想做事故助手"这件事没被删除，只是被隔离在成效之外；后续第 49、50 节会把它当作候选方案之一来检验。
- **讲义 Build It 验证**：把 `desired_outcome` 改成 `"use the incident assistant."` 后，实际得到 `["desired outcome names the proposed output"]`，status 变为 `needs-framing`。

---

## 7. 动手改一改

1. **讲义 Build It**：把 `desired_outcome` 改成 "use the incident assistant"，确认报警；再改成 "use an AI incident helper"，观察漏报，并思考为什么。
2. **修空白 bug**：让 `validate` 对 `proposed_output=" "`、`constraints=["  "]`、`user=None` 都给出合理结果（参考测验 Q10），为每个情况写一个测试。
3. **方案形式词表**：实现 `find_leakage`，用单词边界检测 assistant、dashboard、summary、vector database 等（参考测验 Q9）；用讲义的 4 个例句做测试数据。
4. **讲义练习 2**：把约束改成 `Constraint(text, reason)` 结构，若约束点名了技术（如 "PostgreSQL"）但 `reason` 为空，则报 "technology constraint lacks a reason"。
5. **讲义练习 4**：加 `disproof_signal` 字段，并让 `next_question` 引用它（参考测验 Q11，注意同步更新 `example()`）。
6. **讲义练习 5**：加 `candidate_outputs: list[str]` 字段，要求至少 3 个，且每个都不能出现在 `desired_outcome` 中；用它记录"软件 / runbook / 界面改动"三种满足同一成效的产出。

---

## 8. 常见坑

- **成效里藏着产物**：把 "AI""助手""仪表盘""向量库"写进成效句，团队就绑定了第一个想到的方案。
- **约束写成愿望**："尽量安全"不是约束；"诊断期间不写生产"才是。
- **non-goal 写成空话**："保证质量"无法拒绝任何工作；"本切片不做自动修复"可以。
- **用 `not list` 判断内容是否有效**：`[""]` 不是空列表。
- **以为类型注解会校验输入**：dataclass 不检查类型，`None` 照样能传进去。
- **在可变 dataclass 上用 `= []` 做默认值**：会直接报错（dataclass 禁止可变默认值）；要用 `field(default_factory=list)`。
- **框架合格就开工**：status 是 `ready-to-discover`，下一步是去观察真实工作流（第 48 节），不是写代码。

---

## 9. 测试在验证什么

`code/tests/test_main.py` 通过 `importlib.util.spec_from_file_location` 按文件路径加载 `main.py`（模块名 `lesson47`），因此可以从任何工作目录运行。

| 测试 | 验证的性质 |
|------|-----------|
| `test_example_is_ready` | 示例 frame 合格，status 为 `ready-to-discover`——示例本身就是"好的 frame"的规范 |
| `test_next_question_is_grammatical` | 证据问题的完整文本，确保模板插入 user 后语法正确 |
| `test_missing_user_is_rejected` | user 为空时出现 `"user is empty"` |
| `test_constraints_are_required` | 约束为空列表时报错——约束不是可选项 |
| `test_non_goals_are_required` | non-goals 为空列表时报错——边界不是可选项 |
| `test_solution_leakage_is_detected` | `desired_outcome = "Uses the incident assistant"` 时检出泄漏（大小写不敏感） |

运行方式（在小节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：

```text
Ran 6 tests in 0.000s

OK
```

测试**没有覆盖**的地方：

- 泄漏的**漏报**（换说法、连字符、`proposed_output` 为空时的 "vector database"）；
- 空白元素列表 `["  "]` 与空白 `proposed_output` 的误判；
- situation、current_behavior、desired_outcome 为空的情况（循环逻辑相同，但没有单独断言）；
- 非字符串输入（`None`）。

另外注意：如果你按讲义练习给 frame 增加必填字段（如 `disproof_signal`），`test_example_is_ready` 会首先失败——它把"示例是合格的"当作契约，这时应同步更新 `example()` 而不是删掉测试。
