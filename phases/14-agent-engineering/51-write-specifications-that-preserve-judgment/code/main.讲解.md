# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 51 节 编写保留判断空间的规格说明 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下）；测试：`python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义的核心主张是：给 coding agent 的规格应该是一份 **executable contract（可执行契约）**——固定不变量和证据，放开廉价可逆的实现选择。这份约 100 行的代码把这个主张变成一个"规格编译器"：

1. **六个契约表面**：用一个 `Specification` dataclass 表达 Outcome、Invariants、Examples、Non-goals、Decisions、Proof，并检查它们都不为空。
2. **三种决策模式**：每个 `Decision` 必须是 `locked / bounded / delegated` 之一；非 delegated 的决策必须写理由。
3. **路由**：`compile_contract` 把决策分成三张表——agent 可自行决定的、有边界的、需要人工 checkpoint 的——下游的 agent 与审查者共享这份 JSON。

它同时也是一个很好的反面教材：校验只停留在**结构层**，不懂语义。讲义 Build It 要求你把"写生产"的决策改成 delegated 并观察——校验器照样放行。

> 一句话：**把"规格"从一段散文变成可以被程序检查、被 agent 和人共同消费的 JSON 契约，并看清"结构合法"与"风险合理"之间的距离。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Decision` | frozen dataclass | 一个设计问题 + 模式 + 理由 | Decision policy |
| `Specification` | dataclass | 六个契约表面 | Executable contract |
| `VALID_MODES` | 集合常量 | `{"locked", "bounded", "delegated"}` | 三种决策模式 |
| `validate` | 函数 | 返回问题列表（空列表 = 通过） | 结构校验 |
| `compile_contract` | 函数 | 生成 status、原契约与三张路由表 | 决策路由 / 人工 checkpoint |
| `example` | 函数 | 事故诊断场景的示例规格 | 讲义贯穿案例 |
| `main` | 函数 | 写出并打印 `outputs/executable-specification.json` | 交付物 |
| `tests/test_main.py` | 单元测试 | 6 个测试，见第 9 节 | 校验器行为 |

数据流：`example()` → `compile_contract()`（内部调用 `validate()`、`asdict()`）→ `json.dumps` → 写入 `outputs/executable-specification.json` → 读回并打印。

---

## 3. 逐段精讲

### 3.1 文件头与导入

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
```

- 文件头注释给出两篇参考文献：Zave & Jackson（区分环境假设、需求与规格）、Gotel & Finkelstein（需求可追溯性）。前者对应"Outcome vs Decisions"的分离，后者对应"记录理由"。
- `from __future__ import annotations` 让类型注解延迟求值；在 Python 3.9+ 中 `list[str]` 本身已可用，这里主要是习惯写法。

### 3.2 两个数据类：`Decision` 与 `Specification`

```python
@dataclass(frozen=True)
class Decision:
    question: str
    mode: str
    rationale: str


@dataclass
class Specification:
    outcome: str
    invariants: list[str]
    examples: list[str]
    non_goals: list[str]
    decisions: list[Decision]
    proof: list[str]
```

- `Decision` 是 **frozen**（不可变）：创建后不能 `d.mode = "delegated"`，实测会抛 `FrozenInstanceError`。决策一旦写定，要改就得创建新对象——这和"改 locked 决策需要显式动作"的语义一致。
- `Specification` **不是** frozen：测试里会直接 `specification.non_goals = []` 来构造反例。
- 六个字段与讲义表格一一对应：

| 字段 | 讲义表面 | 示例值 |
|------|---------|-------|
| `outcome` | Outcome | 两分钟内从告警识别受影响服务 |
| `invariants` | Invariants | 诊断只读；每个数据源都进审计记录 |
| `examples` | Examples | 带 deployment id 的告警解析到服务 owner |
| `non_goals` | Non-goals | 自动修复；修改告警路由 |
| `decisions` | Decision policy | 三个决策，各占一种模式 |
| `proof` | Proof | 10 次事故 replay；零生产写入 |

- ⚠️ 简化之处：`mode` 用普通字符串而不是 `Enum`，所以 `"Locked"`、`"maybe"` 这类值要靠 `validate` 在运行时拦截；`Decision` 也没有后果、可逆性等结构化字段，模式是否选对无从检查（测验 Q10）。

### 3.3 `validate`：结构校验

```python
VALID_MODES = {"locked", "bounded", "delegated"}


def validate(specification: Specification) -> list[str]:
    issues: list[str] = []
    for field_name in ("outcome", "invariants", "examples", "non_goals", "decisions", "proof"):
        if not getattr(specification, field_name):
            issues.append(f"{field_name} is empty")
    for decision in specification.decisions:
        if decision.mode not in VALID_MODES:
            issues.append(f"invalid decision mode: {decision.mode}")
        if decision.mode != "delegated" and not decision.rationale.strip():
            issues.append(f"constrained decision lacks rationale: {decision.question}")
    return issues
```

- **返回问题列表而不是抛异常**：一次性收集所有问题，适合给人看的报告，也方便测试用 `assertIn` 检查具体某条。
- `getattr(specification, field_name)` 按字符串名取属性，一个循环覆盖六个字段。
- "非 delegated 必须有理由"对应讲义：Locked 与 Bounded 是对 agent 的约束，约束要有理由，以便"later teams can revise them without archaeology"。Delegated 不要求在规格里写理由（讲义说 agent 在实现时"must explain it"）。
- ⚠️ 已实测的几个漏洞（详见测验 Q9）：
  - `outcome="   "` 返回 `[]`——用的是真值判断，没有 `.strip()`，而 rationale 却用了 `.strip()`，标准不一致；
  - `invariants=[""]` 返回 `[]`——只检查列表非空，不检查条目；
  - `Decision("x", "maybe", "")` 返回两条 issue——非法模式又被当成"constrained 缺理由"，第二条是误报（缺一个 `continue`）。
- ⚠️ 更根本的局限：完全不做语义检查——不看 decision 是否与 invariant 冲突、不看 invariant 是否有 proof、不看 examples 是否覆盖 normal/edge/failure/forbidden。

### 3.4 `compile_contract`：把决策路由给 agent 或人

```python
def compile_contract(specification: Specification) -> dict:
    issues = validate(specification)
    return {
        "status": "executable" if not issues else "incomplete",
        "issues": issues,
        "contract": asdict(specification),
        "agent_may_decide": [item.question for item in specification.decisions if item.mode == "delegated"],
        "bounded_decisions": [
            {"question": item.question, "boundary": item.rationale}
            for item in specification.decisions
            if item.mode == "bounded"
        ],
        "human_checkpoint": [item.question for item in specification.decisions if item.mode == "locked"],
    }
```

- `status`：没有问题就是 `executable`，否则 `incomplete`。
- `asdict(specification)` **递归**地把 dataclass（包括列表里的 `Decision`）转成普通 dict，才能被 `json.dumps` 序列化。它返回的是新对象，修改它不会影响原规格。
- 三张路由表对应讲义 mermaid 图的三条出口：

| 模式 | 输出键 | 讲义中的去向 |
|------|-------|-------------|
| `delegated` | `agent_may_decide` | Agent implements and proves |
| `bounded` | `bounded_decisions` | Agent proposes within limits |
| `locked` | `human_checkpoint` | Human checkpoint |

- ⚠️ `"boundary": item.rationale`：对 bounded 决策，`rationale` 字段被挪用来装"边界"（"Stop after five sources or two minutes"），真正的**理由**（为什么是 5 个、为什么是 2 分钟）没有位置，和讲义"保留 locked 与 bounded 选择背后的理由"相冲突（测验 Q12）。
- ⚠️ 即使 `status == "incomplete"`，三张路由表照样输出；非法模式的决策不出现在任何一张表里，被**静默丢弃**。生产中应 fail closed，或增加 `unrouted` 列表。

### 3.5 `example`：讲义贯穿的事故诊断场景

```python
def example() -> Specification:
    return Specification(
        outcome="Identify the affected service from an incident alert in under two minutes",
        invariants=["diagnosis is read-only", "every source is included in the audit record"],
        examples=["an alert with a deployment id resolves to its service owner"],
        non_goals=["automatic remediation", "changing alert routing"],
        decisions=[
            Decision("Which read-only data source should be queried first?", "delegated", ""),
            Decision("May the system write to production?", "locked", "Production authority stays with the incident commander"),
            Decision("How many sources may be queried?", "bounded", "Stop after five sources or two minutes"),
        ],
        proof=["ten recorded incident replays", "zero production writes"],
    )
```

- 三个决策恰好各占一种模式，演示了讲义的分级：先查哪个**只读**源（廉价可逆）→ delegated；能否写生产（权限、不可逆）→ locked；查多少个源（已知安全范围）→ bounded。
- 注意 delegated 决策的问题里已经写了"read-only"——这是"有意保留未知"的范例：讲义说"the implementation may choose any read-only source that returns within the time budget"不是含糊，而是**带边界的委派**。
- ⚠️ 与讲义的差距：
  - examples 只有一条 normal 例子，没有讲义要求的 edge / failure / forbidden；
  - proof 与 invariants 没有对应关系：`"every source is included in the audit record"` 没有任何证明，`"ten recorded incident replays"` 证明的其实是 outcome（测验 Q11）。

### 3.6 `main`：写出交付物

```python
def main() -> None:
    output = Path(__file__).resolve().parents[1] / "outputs" / "executable-specification.json"
    output.write_text(json.dumps(compile_contract(example()), indent=2) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))
```

- `Path(__file__).resolve().parents[1]`：`code/main.py` 的上一级就是小节目录，所以无论从哪个工作目录运行，输出都落在 `<小节>/outputs/`。
- `indent=2` 让 JSON 便于人审阅和 diff；末尾补 `"\n"` 是文本文件惯例。
- 写完再读回打印，保证屏幕上看到的就是磁盘上的内容。
- ⚠️ `outputs/` 目录必须已存在，否则 `write_text` 抛 `FileNotFoundError`（仓库中已有该目录）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| dataclass 表达规格 | 字段即契约表面，清晰、可序列化 | 生产中常用 JSON Schema / Pydantic 做带类型与取值约束的校验 |
| `mode` 用字符串 | 简单、JSON 友好 | 易拼错；可用 `Enum` 或 `Literal["locked", "bounded", "delegated"]` |
| `validate` 返回问题列表 | 一次报告全部问题 | 需配合"非空即失败"的调用约定；非法模式应 `continue` 避免误报 |
| 只做结构校验 | 代码短，聚焦概念 | 写生产改成 delegated 也能通过；应加入后果/可逆性字段与一致性 lint |
| bounded 的边界借用 `rationale` | 少一个字段 | 理由丢失；应拆成 `boundary` + `rationale` |
| 输出完整 `contract` + 路由表 | agent 与审查者共享同一份 JSON | incomplete 时仍输出路由表，应 fail closed |
| proof 是自由文本列表 | 便于书写 | 无法检查"每条 invariant 都有证明、层级匹配"；可改为 `invariant → [proof]` 映射并带 `layer` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，避免前向引用问题 |
| `@dataclass` | `class Specification` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `@dataclass(frozen=True)` | `class Decision` | 实例不可变，赋值会抛 `FrozenInstanceError`；且可哈希 |
| 内置泛型注解 | `list[str]`、`list[Decision]`、`-> dict` | Python 3.9+ 可直接用小写 `list[...]` |
| 集合与成员测试 | `VALID_MODES = {...}`、`mode not in VALID_MODES` | 集合查找平均 O(1) |
| `getattr` | `getattr(specification, field_name)` | 用字符串名动态取属性 |
| 真值判断 | `if not getattr(...)` | 空字符串、空列表、`None` 都为假；但 `"   "` 为真 |
| `str.strip()` | `decision.rationale.strip()` | 去掉首尾空白，用来判断"实际是否为空" |
| f-string | `f"{field_name} is empty"` | 字符串插值 |
| 条件表达式 | `"executable" if not issues else "incomplete"` | 三元表达式 |
| 列表推导式 + 过滤 | `[item.question for item in ... if item.mode == "delegated"]` | 一行完成过滤与映射 |
| 推导式生成 dict 列表 | `[{"question": ..., "boundary": ...} for item in ... if ...]` | 推导式里可以构造任意对象 |
| `dataclasses.asdict` | `asdict(specification)` | 递归转换为 dict，便于 JSON 序列化 |
| `json.dumps(..., indent=2)` | `main` | 序列化为带缩进的 JSON 字符串 |
| `pathlib.Path` | `Path(__file__).resolve().parents[1] / "outputs"` | 面向对象的路径操作，`/` 拼接路径；`parents[0]` 是 `code/`，`parents[1]` 是小节目录 |
| `write_text` / `read_text` | `output.write_text(..., encoding="utf-8")` | 一次性读写文本文件，显式指定编码 |
| 返回类型 `-> None` | `def main() -> None` | 表示函数无返回值 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被测试导入时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时副本中运行，生成的 JSON 与仓库中 `outputs/executable-specification.json` 逐字节一致）：

```text
{
  "status": "executable",              ← validate 返回 []，规格结构完整
  "issues": [],
  "contract": {
    "outcome": "Identify the affected service from an incident alert in under two minutes",
    "invariants": [ "diagnosis is read-only", "every source is included in the audit record" ],
    "examples": [ "an alert with a deployment id resolves to its service owner" ],
    "non_goals": [ "automatic remediation", "changing alert routing" ],
    "decisions": [
      { "question": "Which read-only data source should be queried first?", "mode": "delegated", "rationale": "" },
      { "question": "May the system write to production?", "mode": "locked",
        "rationale": "Production authority stays with the incident commander" },
      { "question": "How many sources may be queried?", "mode": "bounded",
        "rationale": "Stop after five sources or two minutes" }
    ],
    "proof": [ "ten recorded incident replays", "zero production writes" ]
  },
  "agent_may_decide": [ "Which read-only data source should be queried first?" ],
  "bounded_decisions": [
    { "question": "How many sources may be queried?", "boundary": "Stop after five sources or two minutes" }
  ],
  "human_checkpoint": [ "May the system write to production?" ]
}
```

（为节省篇幅，上面把短列表合并成一行；真实输出每个元素各占一行。）

逐项解读：

- **`status: executable`**：六个表面都非空，三个决策模式合法，locked/bounded 都有 rationale。
- **`contract.decisions[0].rationale` 为空字符串**：delegated 决策允许不写理由，所以不报错。
- **三张路由表**各有一项，与 `example()` 中三种模式一一对应。下游可以这样消费：`agent_may_decide` 直接放进 agent 的任务说明；`bounded_decisions` 变成 harness 的预算参数；`human_checkpoint` 变成需要人审批的门禁。
- **讲义 Build It 实验**（实测）：把写生产决策改成 `Decision("May the system write to production?", "delegated", "")`，输出变为 `status: executable`、`agent_may_decide` 含两项、`human_checkpoint: []`——结构上完全合法，但把生产权限交给了 agent，并且与 invariant "diagnosis is read-only" 冲突。这就是"schema 接受，产品风险不接受"。

---

## 7. 动手改一改

1. **（入门）** 讲义 Build It：把写生产决策改成 delegated，运行 `main`，对照输出解释为什么校验器放行。再把它改成 `"Locked"`（大写 L），观察 `status` 与 `issues`。
2. **（入门）** 修 `validate`：对字符串用 `.strip()`、对列表检查每个条目、非法模式后 `continue`（参考测验 Q9），并补三个对应的单元测试。
3. **（进阶）** 给 `Decision` 加 `consequence` 与 `reversible` 字段，写 `mode_lint`：高后果或不可逆必须 locked，廉价可逆却 locked 时给出"过度约束"提示（测验 Q10）。
4. **（进阶）** 讲义练习 4：给 `Specification` 增加 `invariant_proofs: dict[str, list[str]]`，让 `validate` 报告没有证明的 invariant；示例中应报出 "every source is included in the audit record"（测验 Q11）。
5. **（进阶）** 给 `Decision` 增加 `boundary` 字段，让 bounded 决策同时有边界和理由；更新 `compile_contract` 与测试 `test_compile_keeps_bounded_decisions_in_the_routing_contract`。
6. **（挑战）** 讲义练习 1：选一张你手头真实的 backlog ticket，写成 `Specification`，要求 examples 覆盖 normal / edge / failure / forbidden 四类，并让 `compile_contract` 在 `status != "executable"` 时清空路由表（fail closed）。

---

## 8. 常见坑

- **把"校验通过"当成"规格正确"**：`validate` 只看结构，写生产改成 delegated 也是 `executable`。
- **真值判断不等于"有内容"**：`"   "`、`[""]` 都是真值。判断文本是否为空要 `.strip()`，判断列表要逐项检查。
- **两个独立 `if` 导致误报**：非法模式应提前 `continue`，否则会多出一条"constrained 缺理由"。
- **修改 frozen dataclass**：`decision.mode = ...` 会抛 `FrozenInstanceError`；要用 `dataclasses.replace(decision, mode=...)` 生成新对象。
- **用例子证明不变量**：一个 replay 通过不能证明"永远只读"，需要审计日志或权限层面的保证。
- **忽略 `status` 只读路由表**：incomplete 的规格同样会输出 `agent_may_decide`。
- **在错误的目录运行测试**：讲义命令 `python3 -m unittest discover code/tests -v` 应在**小节目录**下执行；测试文件用 `Path(__file__).parents[1] / "main.py"` 定位被测模块，所以不依赖当前目录，但 `discover` 的起始路径依赖当前目录。

---

## 9. 测试在验证什么

`code/tests/test_main.py` 用 `importlib.util.spec_from_file_location` 按**文件路径**加载 `main.py`（模块名注册为 `lesson51`），这样测试目录不需要 `__init__.py`，也不依赖 `sys.path`。

| 测试 | 验证的性质 |
|------|-----------|
| `test_example_is_executable` | 示例规格编译后 `status == "executable"`（正例基线） |
| `test_every_contract_surface_is_required` | 清空 `non_goals` 后出现 `"non_goals is empty"`——每个表面都是必填 |
| `test_invalid_decision_mode_is_rejected` | 模式 `"maybe"` 会产生 `invalid decision mode` 问题 |
| `test_locked_decision_requires_rationale` | locked 决策 rationale 为空时报 `lacks rationale` |
| `test_compile_separates_agent_and_human_decisions` | 示例中 `agent_may_decide` 与 `human_checkpoint` 各 1 项——agent 与人的决策被分开 |
| `test_compile_keeps_bounded_decisions_in_the_routing_contract` | bounded 决策以 `{"question", "boundary"}` 形式保留在输出中 |

运行方式（在小节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：`Ran 6 tests in 0.001s — OK`，6 个测试全部通过。

测试没有覆盖的地方（可作为练习补充）：空白字符串 / 空白条目、非法模式 + 空理由的重复报告、bounded 决策缺理由、`incomplete` 时路由表的行为，以及任何语义层面的检查。
