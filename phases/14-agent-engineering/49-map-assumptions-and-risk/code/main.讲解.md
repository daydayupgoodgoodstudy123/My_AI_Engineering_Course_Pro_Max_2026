# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 49 节 梳理假设，优先验证风险最高的一项 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在小节目录下 `python3 code/main.py`；测试 `python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义要求把计划中的构建拆成显式假设，分别给出影响、不确定性、不可逆性三个分数，按风险而不是热情选择下一个实验，并用证据替换已检验的假设。这份约 60 行的代码实现了这条链：

1. **假设的数据化**：`Assumption` 记录陈述、三个 1–5 分的维度、检验方式和证据。
2. **风险评分**：`risk_score = impact × uncertainty + irreversibility`，先校验三个维度都在 1–5。
3. **排序与状态**：`prioritize` 按风险从高到低排序，并标注每条假设是 `open` 还是 `tested`。
4. **选下一个实验**：`next_experiment` 在**还没有证据**的假设中选风险最高的一条——对应讲义流程图中的 "Highest open risk → Cheapest decisive experiment"。

> 一句话：**把"我们觉得这个功能该先做"换成"这条未经证实的假设风险最高，所以先花最少的钱验证它"**。代码的局限同样值得学习：状态只分 open/tested（证据否定了也叫 tested），排序和选实验在平局时规则不一致，公式让不可逆性几乎不起作用。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Assumption` | frozen dataclass | 陈述、impact、uncertainty、irreversibility、test、evidence | 可证伪的假设 |
| `risk_score` | 函数 | 校验 1–5，计算 `I × U + R` | 风险不是一个数 |
| `prioritize` | 函数 | 按（风险降序，陈述升序）排序，附加 `risk_score` 与 `status` | 假设地图 |
| `next_experiment` | 函数 | 开放假设中风险最高的一条，无则 `None` | 最高开放风险 |
| `example` | 函数 | 三条事故工具假设 | 讲义"每次构建都包含赌注" |
| `main` | 函数 | 写 `outputs/assumption-map.json` 并打印 | 留存产物 |
| `tests/test_main.py` | 单元测试 | 5 个测试（见第 9 节） | 可执行验证 |

数据流：`example()` → `prioritize()`（每条调用 `risk_score()`，再 `asdict` 并附加两个字段）→ `json.dumps` → `outputs/assumption-map.json`。注意 `main` 并**不**调用 `next_experiment`，所以输出文件里没有"下一个实验"这一项，需要读者自己从排序中找第一个 `open`。

---

## 3. 逐段精讲

### 3.1 `Assumption`：一条可证伪的赌注

```python
@dataclass(frozen=True)
class Assumption:
    statement: str
    impact: int
    uncertainty: int
    irreversibility: int
    test: str
    evidence: str = ""
```

| 字段 | 讲义含义 |
|------|---------|
| `statement` | 必须为真的条件，应写成可证伪的陈述 |
| `impact` | 假设为假时的损害（1–5） |
| `uncertainty` | 现有证据有多弱（1–5，越大越不确定） |
| `irreversibility` | 承诺之后才发现错误的代价（1–5） |
| `test` | 检验它的实验 |
| `evidence` | 检验得到的证据；空字符串表示尚未检验 |

- ⚠️ 没有讲义"五类假设"（Value / Usability / Feasibility / Viability / Safety）对应的字段，因此无法检查"是否遗漏了 Safety 类假设"（讲义练习 2）。
- ⚠️ `test` 只是一段文字，没有讲义要求的阈值、样本和三种结果的决策；`evidence` 也只是一段文字，没有"支持还是否定"的结论。
- 示例三条恰好覆盖了不同类别：识别服务（Feasibility）、两分钟重要（Value）、自动修复可接受（Safety/Usability）。

### 3.2 `risk_score`：校验 + 公式

```python
def risk_score(item: Assumption) -> int:
    for value in (item.impact, item.uncertainty, item.irreversibility):
        if value not in range(1, 6):
            raise ValueError("risk dimensions must be integers from one to five")
    return item.impact * item.uncertainty + item.irreversibility
```

- **校验**：`range(1, 6)` 即 1–5。`in range(...)` 对整数是 O(1) 的数值判断。
  - ⚠️ 它按**数值相等**判断，所以 `3.0`（`3.0 == 3`）和 `True`（`True == 1`）都能通过；`risk_score(Assumption("x", 3.0, 3, 3, "t"))` 返回浮点 `12.0`，与注解 `-> int` 和错误消息"must be integers"不符（已实际运行验证）。严格写法是 `type(value) is int and 1 <= value <= 5`。
  - 字符串 `"3"` 不等于任何整数，会被拒绝。
- **公式**：`I × U + R`，分数范围 2–30。讲义："The example score multiplies impact and uncertainty, then adds irreversibility. The formula is not universal."
  - 乘法让"影响大且不确定"的假设分数陡增——两者缺一都不急。
  - ⚠️ 不可逆性只是加法项，最多贡献 5 分、区分度最多 4 分。示例中不可逆性为 5 的"自动修复可接受"（25）仍排在不可逆性为 2 的"能识别服务"（27）之后；在 1–5 分制下它**无论如何**都超不过 27。这与讲义"High-consequence, irreversible choices need earlier evidence"存在张力（测验 Q10 比较了乘法与门槛法）。

### 3.3 `prioritize`：排序与状态

```python
def prioritize(items: list[Assumption]) -> list[dict]:
    ranked = sorted(items, key=lambda item: (-risk_score(item), item.statement))
    return [{**asdict(item), "risk_score": risk_score(item), "status": "tested" if item.evidence else "open"} for item in ranked]
```

- 排序键是元组 `(-风险分, 陈述)`：用**负号**实现分数降序，同时让陈述按字母**升序**作平局规则——一个 `sorted` 同时完成两个方向的排序。
- `{**asdict(item), "risk_score": ..., "status": ...}`：用字典解包把原字段展开，再追加两个计算字段。
- **状态**：只要 `evidence` 非空就是 `tested`。
  - ⚠️ 讲义流程图里证据有两个出口："Supports → Bounded build"、"Rejects → Reframe or stop"。代码不区分：`evidence="rejected: 2 of 10"` 也是 `tested`，被否定的核心假设会像"已解决"一样沉到列表底部（测验 Q11 给出 `result` 字段与 `next_decision` 的扩展）。
  - ⚠️ 已检验的假设仍按原来的 uncertainty 打分。证据本应降低不确定性，但分数不变，只是状态变了。
- `risk_score` 在排序时算一次、构造结果时又算一次，对小数据无所谓。

### 3.4 `next_experiment`：最高开放风险

```python
def next_experiment(items: list[Assumption]) -> Assumption | None:
    open_items = [item for item in items if not item.evidence]
    return max(open_items, key=risk_score, default=None)
```

- 先过滤出没有证据的假设，再取风险最高的。`default=None` 让空列表时返回 `None` 而不是抛 `ValueError`。
- 返回类型 `Assumption | None` 是 Python 3.10 的联合类型写法；有了 `from __future__ import annotations`，注解不会在运行时求值。
- ⚠️ **平局规则与 `prioritize` 不一致**：`max` 在多个最大值中返回**第一个遇到的**（输入顺序），而 `prioritize` 用陈述字母序。两条 10 分的假设，输入 `[B, A]` 时 `prioritize` 把 A 排第一，`next_experiment` 却返回 B（已实际运行验证）。修复：两者共用一个排序键，`next_experiment` 用 `min(open_items, key=lambda i: (-risk_score(i), i.statement), default=None)`。
- 讲义要求选"Cheapest decisive experiment"，但代码不考虑实验成本：它只选"最该验证的假设"，至于用多便宜的方法验证，留在 `test` 字段的文字里。

### 3.5 示例与 `main`

```python
def example() -> list[Assumption]:
    return [
        Assumption("Engineers can identify the right service from alert context", 5, 5, 2, "Replay ten incidents with a read-only prototype"),
        Assumption("Two-minute diagnosis matters", 4, 2, 1, "Interview five incident commanders", "four of five confirmed"),
        Assumption("Automatic remediation is acceptable", 5, 4, 5, "Do not automate; test approval workflow first"),
    ]
```

| 假设 | I | U | R | 分数 | 状态 | 解读 |
|------|---|---|---|------|------|------|
| 能从告警上下文识别正确服务 | 5 | 5 | 2 | 27 | open | 整个产品的前提，且最不确定；只读回放可逆，所以 R 低 |
| 自动修复可接受 | 5 | 4 | 5 | 25 | open | 后果最重、最不可逆；检验方式本身就是"不要自动化，先测审批流"——用降低不可逆性的方式处理 |
| 两分钟诊断很重要 | 4 | 2 | 1 | 9 | tested | 五位事故指挥官中四位确认；证据来自访谈（第 48 节的"报告的行为"级别） |

- 第一条与第 48 节的摩擦点直接相连：告警缺少服务 owner（owner lookup）、要切换三个仪表盘（context switching）。
- 第二条的证据是访谈结论。按第 48 节的证据阶梯，这只是第三级证据，但代码同样把它视为 `tested`——证据强度没有被记录。
- `main` 输出的是 `prioritize` 的结果，写入 `<小节>/outputs/assumption-map.json`。⚠️ 每次运行会覆盖该文件（内容不变）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 三个维度分别打分 | 让排序理由可解释、可争论 | 打分本身主观；应为每个分数附一句理由和证据来源 |
| `I × U + R` | 演示"影响与不确定性相互放大" | 不可逆性权重过低；可用乘法、门槛或"先把不可逆变可逆"的做法 |
| `in range(1, 6)` 校验 | 一行实现 | 放过 `3.0` 与 `True`；应严格检查类型，最好放在 `__post_init__` |
| 状态只有 open / tested | 简单 | 否定的证据无法触发"重新框定或停止"；应记录结论（supports/rejects/ambiguous） |
| 平局：排序用字母序、选实验用输入顺序 | 两个函数各自取最简单写法 | 结果不一致、依赖输入顺序；应共用排序键 |
| 证据是自由文本 | 灵活 | 无法自动判断强弱与结论；可结构化为 {样本、阈值、结果、证据等级} |
| `main` 不输出下一个实验 | 输出文件只存地图 | 第 50 节需要"必须证明的集合"，应额外输出开放假设列表 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class Assumption` | 不可变的数据记录 |
| 默认值字段 | `evidence: str = ""` | 有默认值的字段放最后 |
| `range` 成员判断 | `value not in range(1, 6)` | 按数值相等判断；`3.0 in range(1, 6)` 为 True |
| `raise ValueError(...)` | 校验失败 | 抛出异常中止计算；测试用 `assertRaises` 捕获 |
| 元组迭代 | `for value in (item.impact, item.uncertainty, item.irreversibility)` | 对多个值做同样的检查 |
| `sorted` + 元组键 | `key=lambda item: (-risk_score(item), item.statement)` | 先按第一项、再按第二项比较；负号实现降序 |
| 字典解包合并 | `{**asdict(item), "risk_score": ..., "status": ...}` | 展开已有字典并追加/覆盖键 |
| 条件表达式 | `"tested" if item.evidence else "open"` | 空字符串为假 |
| 带条件的列表推导式 | `[item for item in items if not item.evidence]` | 过滤开放假设 |
| `max(..., key=..., default=...)` | `max(open_items, key=risk_score, default=None)` | 按键取最大；平局返回第一个；空序列返回 default |
| 函数作为参数 | `key=risk_score` | 直接传函数对象，不加括号 |
| 联合类型注解 | `-> Assumption | None` | 可能返回 None；需 3.10+ 或 `from __future__ import annotations` |
| `bool` 是 `int` 子类 | `True in range(1, 6)` 为 True | 需要 `type(v) is int` 才能排除 |
| `pathlib` / `json` / `__main__` | `main()` | 与其它小节相同 |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，在小节目录副本中执行，输出与仓库内 `outputs/assumption-map.json` 逐字节相同）：

```text
[
  {
    "statement": "Engineers can identify the right service from alert context",
    "impact": 5,
    "uncertainty": 5,
    "irreversibility": 2,
    "test": "Replay ten incidents with a read-only prototype",
    "evidence": "",
    "risk_score": 27,
    "status": "open"
  },
  {
    "statement": "Automatic remediation is acceptable",
    "impact": 5,
    "uncertainty": 4,
    "irreversibility": 5,
    "test": "Do not automate; test approval workflow first",
    "evidence": "",
    "risk_score": 25,
    "status": "open"
  },
  {
    "statement": "Two-minute diagnosis matters",
    ...
    "evidence": "four of five confirmed",
    "risk_score": 9,
    "status": "tested"
  }
]
```

逐项解读：

- **排在第一的开放假设**就是 `next_experiment(example())` 的返回值：用只读原型回放十个事故。它可逆、便宜，且直接检验整个产品的前提。
- **第二名是自动修复**：分数 25，只比第一名低 2 分，主要是因为 uncertainty 为 4 而不是 5；不可逆性 5 并没有让它前置。它的检验方式说明作者用"不自动化，先测审批工作流"把不可逆的问题转化成了可逆的问题。
- **已检验的假设沉到最后**：分数低（9），而且已有证据；但如果证据是"五位中只有一位认为两分钟重要"，代码同样会显示 `tested`，团队可能错过"成效本身不重要"这个应该让项目停下来的信号。
- **讲义 Build It（改变最高风险假设的证据，观察下一个实验的变化）**：给第一条补上 `evidence="9 of 10 replays correct"` 后，`next_experiment` 变为 "Automatic remediation is acceptable"，对应实验 "Do not automate; test approval workflow first"（已实际运行验证）；三条都有证据时返回 `None`。

---

## 7. 动手改一改

1. **讲义 Build It**：按上面的方法修改第一条假设的证据，打印 `next_experiment` 的变化；再把它改成否定的证据，思考代码为什么"看不出"区别。
2. **修平局 bug**：抽出 `rank_key`，让 `prioritize` 和 `next_experiment` 共用；为"两条同分、输入顺序不同"写一个测试（参考测验 Q9）。
3. **记录结论**：加 `result` 字段与 `next_decision` 函数，被否定的核心假设触发 "reframe or stop"（参考测验 Q11）。
4. **讲义练习 2**：加 `kind` 字段（value / usability / feasibility / viability / safety），写一个检查：若没有任何 safety 类假设则报警。
5. **讲义练习 3**：把 `test` 改成结构化的 `Experiment(sample, observable, threshold, on_pass, on_fail, on_ambiguous)`，并校验阈值在实验前已填写。
6. **公式实验**：实现三种评分（`I×U+R`、`I×U×R`、不可逆性门槛），对同一组假设输出三种排序，写一句话说明你的团队会选哪种、为什么（参考测验 Q10）。

---

## 8. 常见坑

- **把实现任务当假设**："接入告警 API"是任务，不是假设；假设是"告警里有足够的信息识别服务"。
- **不可证伪的陈述**："用户会喜欢"无法检验，任何结果都能被解释成支持。
- **看到结果后再定阈值**：这是确认仪式，不是实验。
- **把 tested 当成 supported**：证据可能否定假设，必须记录结论。
- **以为公式是客观真理**：讲义明确说公式不通用，打分要附理由。
- **`in range` 当类型检查用**：`3.0` 和 `True` 都会溜过去。
- **平局依赖输入顺序**：用 `max` 选第一名时，同分情况下结果随列表顺序变化，导致不可复现。

---

## 9. 测试在验证什么

`code/tests/test_main.py` 用 `importlib.util.spec_from_file_location` 按文件路径加载 `main.py`（模块名 `lesson49`）。

| 测试 | 验证的性质 |
|------|-----------|
| `test_risk_score_weights_impact_and_uncertainty` | `(5, 4, 3)` 的分数为 23，锁定公式 `I × U + R` |
| `test_invalid_dimension_is_rejected` | impact 为 0 时抛 `ValueError` |
| `test_highest_open_risk_is_next` | 示例的下一个实验是"能从告警上下文识别服务"那条 |
| `test_tested_assumption_is_not_selected` | 被选中的假设 evidence 为空——已检验的不会被选 |
| `test_prioritize_marks_evidence_status` | 有证据的"两分钟诊断"被标为 `tested` |

运行方式（在小节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：

```text
Ran 5 tests in 0.000s

OK
```

测试**没有覆盖**的地方：

- 维度为 `3.0`、`True` 时应被拒绝（当前会通过）；
- 同分时 `prioritize` 与 `next_experiment` 的一致性；
- 所有假设都已检验时 `next_experiment` 返回 `None`；
- 被否定的证据应与被支持的证据区别对待——当前代码根本无法表达这一点。
