# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 25 节 案例研究与 2026 年前沿进展 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）

---

## 1. 这份代码在考察什么

本节讲义是阶段 16 的收官阅读课，标注"Languages: —"，正文也没有 Build It 小节，但 `code/` 下附带了一个"案例映射器"（case-study mapper）。它把讲义"Choosing a reference for your next project"一段和 `outputs/skill-case-study-mapper.md` 的思路落成了代码：

1. **设计指纹**：用 `Design` dataclass 描述一个拟建的多 agent 系统（任务类型、agent 数量、是否需要验证、运行时长、角色是否分明、是否面向用户网络）。
2. **映射到参考案例**：`map_to_case` 用 if 规则把设计映射到 Anthropic Research、MetaGPT / ChatDev、OpenClaw / Moltbook 三个案例之一。
3. **输出可照搬的模式**：每个案例附带要复制的设计模式、推荐框架和引用。
4. **框架格局表**：打印 2026 年 4 月主流框架的状态。

> 一句话：**"先找最接近的参考案例，再照着它已经验证过的取舍去改"**——同时也示范了 if 链式规则映射的典型缺陷：字段没用上、优先级隐含、讲义里的第四条规则缺失。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Design` | dataclass | 拟建系统的 7 个属性 | 设计指纹 |
| `CASES` | 嵌套字典 | 三个参考案例：名称、模式列表、推荐框架、引用 | 三个 2026 参考案例 |
| `FRAMEWORK_LANDSCAPE` | 元组列表 | 7 个框架的名称、状态、擅长场景 | 框架格局 |
| `map_to_case` | 函数 | 设计 → 案例键（if 链） | 选参考案例 |
| `print_case` | 函数 | 打印一个案例的模式、框架、引用 | 可照搬的模式 |
| `print_landscape` | 函数 | 打印框架表与"协议不是差异点"的结论 | 框架选择 |
| `main` | 函数 | 4 个示例设计 → 映射 → 打印；再打印框架表与 Takeaways | 入口 |

数据流：`main()` 构造 4 个 `Design` → 逐个 `map_to_case(d)` 得到键 → `print_case(key)` 查 `CASES` 打印 → `print_landscape()` → 打印 Takeaways。

---

## 3. 逐段精讲

### 3.1 `Design`：设计指纹

```python
@dataclass
class Design:
    name: str
    task_type: str          # "research" | "engineering" | "population" | "automation"
    n_agents_expected: int
    verification_required: bool
    runtime_duration_hours: float
    roles_distinct: bool
    user_facing_network: bool
```

- 7 个字段对应 skill 文件第 1 步"Design fingerprint"的六项（加一个名字）。
- `task_type` 用字符串加注释约定取值；更稳妥的写法是 `Literal["research", "engineering", "population", "automation"]` 或 `Enum`，拼错时能被类型检查器发现。现在传一个 `"reserch"` 不会报错，只会悄悄落到默认分支。
- `user_facing_network` 的含义有歧义：是"面向终端用户"，还是"agent 与 agent 组成的、对外开放的网络"？这个歧义在 3.3 中会导致误映射。

### 3.2 `CASES` 与 `FRAMEWORK_LANDSCAPE`：把讲义压成数据

```python
CASES = {
    "anthropic_research": {
        "name": "Anthropic Research (supervisor-worker)",
        "patterns": ["fresh-context subagents", "orchestrator synthesis",
                     "rainbow deployment", "verification role"],
        "framework": "Anthropic Claude Agent SDK or LangGraph",
        "citation": "https://www.anthropic.com/engineering/multi-agent-research-system",
    },
    "metagpt_chatdev": { ... "patterns": ["role prompts encode SOP", "structured artifact handoffs",
                     "communicative dehallucination", "DAG routing at scale"], ... },
    "openclaw_moltbook": { ... "patterns": ["local ReAct loop", "agent-to-agent social graph",
                     "emergent economy", "prompt-injection threat model"], ... },
}
```

- 每个案例的 `patterns` 与讲义各案例的"Design lessons"一一对应：
  - Anthropic：新上下文子 agent、编排者综合、rainbow deploy、验证角色；
  - MetaGPT / ChatDev：SOP 角色 prompt、结构化工件 handoff、communicative dehallucination、DAG 路由（MacNet）；
  - OpenClaw / Moltbook：本地 ReAct 循环、agent 社交图、涌现经济、prompt-injection 威胁模型。
- 用字典而不是 if/else 存放"案例知识"，是**数据与逻辑分离**：新增案例只需加一项。
- ⚠️ 讲义的"Choosing a reference"有**四**条规则，第四条是"Classic enterprise automation → CrewAI or LangGraph"，但 `CASES` 只有三项，第四条在代码里不存在。

```python
FRAMEWORK_LANDSCAPE = [
    ("LangGraph", "production", "structured graph + checkpointing + HITL"),
    ...
    ("Anthropic Claude Agent SDK", "production", "agent + Research extension"),
]
```

- ⚠️ 讲义表格有 8 行，这里 7 行，缺了 **Microsoft AutoGen（Maintenance mode, Feb 2026）**。讲义列出它正是为了提示"AutoGen 已进入维护模式、并入 Microsoft Agent Framework"，删掉这一行会让读者看不到这条迁移信息。

### 3.3 `map_to_case`：if 链的隐含优先级

```python
def map_to_case(d: Design) -> str:
    if d.task_type == "population" or d.user_facing_network:
        return "openclaw_moltbook"
    if d.task_type == "engineering" or d.roles_distinct:
        return "metagpt_chatdev"
    if d.task_type == "research":
        return "anthropic_research"
    if d.verification_required and d.runtime_duration_hours >= 1:
        return "anthropic_research"
    return "anthropic_research"
```

- 规则顺序就是优先级：population / 面向用户网络 > 工程 / 角色分明 > 研究 > 其他。
- ⚠️ **死逻辑**：最后两个分支返回同一个值，第 4 个 `if` 无论真假结果都一样。`verification_required` 和 `runtime_duration_hours` 因此从不影响结果；`n_agents_expected` 则根本没被读取。7 个字段里真正起作用的只有 `task_type`、`roles_distinct`、`user_facing_network` 三个。
- ⚠️ **优先级导致的误映射**（已运行验证）：
  - `research` + `roles_distinct=True` → `metagpt_chatdev`（"有角色"压过了"是研究任务"）；
  - `research` + `user_facing_network=True` → `openclaw_moltbook`（一个面向公众的研究助手被当成了 agent 社交网络）；
  - 枚举 4 种任务类型 × 其余 4 个二值字段共 64 种组合：OpenClaw 40 种、MetaGPT 16 种、Anthropic 8 种，映射器明显偏向排在最前面的规则。
- ⚠️ `automation` 类型永远到不了讲义推荐的 CrewAI / LangGraph：要么因角色分明进 MetaGPT，要么因面向用户进 OpenClaw，要么落入默认的 Anthropic Research。
- skill 文件里"Anthropic Research if … verification mandatory, multi-hour runs"的条件，在代码中没有实际效果。测验 Q10 给出了"打分 + 理由"的改写。

### 3.4 `print_case` 与 `print_landscape`：打印

```python
def print_case(key: str) -> None:
    case = CASES[key]
    print(f"\n  closest case study: {case['name']}")
    print(f"  patterns to copy:")
    for p in case["patterns"]:
        print(f"    - {p}")
```

- `CASES[key]` 用方括号取值，键不存在会抛 `KeyError`——由于 `map_to_case` 只返回三个合法键，这里是安全的。
- `print(f"  patterns to copy:")` 是一个没有任何占位符的 f-string，`f` 前缀多余（无害，linter 会提示 F541）。

```python
    print(f"  {'framework':30s} {'status':22s} {'best for':30s}")
    for name, status, best_for in FRAMEWORK_LANDSCAPE:
        print(f"  {name:30s} {status:22s} {best_for:30s}")
```

- 在 `for` 中直接把三元组解包成三个变量。
- `:30s` 表示**最小宽度** 30、左对齐（字符串默认左对齐），不足补空格、超出不截断。`best for` 列有 4 项超过 30 个字符（39、41、35、37），因为是最后一列，目前只表现为行长不齐和短行末尾的多余空格；若以后在右边加列就会错位。

### 3.5 `main`：四个示例设计

```python
    designs = [
        Design("research-assistant", "research", 6, True, 2.0, False, False),
        Design("codegen-team", "engineering", 5, True, 1.0, True, False),
        Design("agent-marketplace", "population", 1000, False, 24.0, False, True),
        Design("internal-automation", "automation", 3, True, 0.5, True, False),
    ]
```

- 全部使用**位置参数**构造，7 个参数的含义要对照字段顺序才能看懂；用关键字参数（`Design(name=..., task_type=..., ...)`）可读性更好，也不怕字段顺序变化。
- `print(f"\ndesign: {d.name!r}")` 中的 `!r` 会调用 `repr()`，所以名字带引号输出：`design: 'research-assistant'`。
- ⚠️ `agent-marketplace` 的 `verification_required=False`，映射器照样给出推荐、没有任何警告。而讲义共同模式第 3 条是"Verification as first-class role"，skill 文件第一条 hard reject 就是"ignore verification when the task has correctness requirements"。测验 Q12 给出了一个 `lint_design` 检查器。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 dataclass 表示设计指纹 | 字段清晰、自动生成构造函数 | `task_type` 用裸字符串，拼错不报错；应用 `Literal` / `Enum` 并校验 |
| 案例知识放在字典 `CASES` | 数据与逻辑分离，易扩展 | 缺讲义的第四类（企业自动化）；应补齐 |
| if 链做映射 | 最简单、可读 | 隐含优先级、字段被忽略、死分支；应改为打分 + 理由，或决策表 |
| 只返回一个案例 | 输出简洁 | 真实设计常是混合体（研究 + 角色分工），应返回排序后的前 2 个及理由 |
| 不做设计检查 | 聚焦映射本身 | skill 文件的 hard reject（无验证、无 prompt-injection 威胁模型、不用 MCP/A2A）没有体现 |
| 框架表写死在代码中 | 演示方便 | 框架状态变化很快（讲义一年内就有多次改名、合并），应外置为数据文件并注明日期与来源；且缺 AutoGen 一行 |
| 固定宽度打印 | 终端表格对齐 | 超长内容不截断；最后一列应不定宽或动态计算宽度 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，旧版本 Python 也能用新式类型写法 |
| `@dataclass` | `class Design:` | 根据字段自动生成 `__init__`、`__repr__`、`__eq__` |
| 类型注解 | `n_agents_expected: int`、`def map_to_case(d: Design) -> str:` | 说明类型，运行时不强制 |
| 字段行尾注释约定取值 | `task_type: str  # "research" \| ...` | 只是文档；可改用 `typing.Literal` 让工具检查 |
| 嵌套字典 | `CASES["anthropic_research"]["patterns"]` | 字典里套字典和列表，存放结构化知识 |
| 列表跨行书写 | `"patterns": ["...", "...",\n "..."]` | 括号内可自由换行，无需反斜杠 |
| 元组列表 + 解包 | `for name, status, best_for in FRAMEWORK_LANDSCAPE:` | 每个元组直接拆成三个变量 |
| 布尔短路 `or` / `and` | `d.task_type == "population" or d.user_facing_network` | 左边为真时不再计算右边 |
| 提前 `return` | `map_to_case` 中各分支 | 命中即返回，后面的规则不再执行——这就是隐含优先级 |
| f-string 宽度 | `{name:30s}`、`{'framework':30s}` | 最小宽度，左对齐，超出不截断 |
| f-string 转换标志 | `{d.name!r}` | `!r` 用 `repr()`，字符串会带引号 |
| f-string 内嵌字典取值 | `{case['name']}` | 外层双引号、内层单引号 |
| 无占位符的 f-string | `print(f"  patterns to copy:")` | 多余的 `f`，不影响结果 |
| 字符串乘法与拼接 | `"\n" + "=" * 78` | 生成换行加分隔线 |
| 位置参数构造对象 | `Design("codegen-team", "engineering", 5, True, 1.0, True, False)` | 依赖字段顺序；关键字参数更清晰 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，可被 import 复用 `map_to_case` |

---

## 6. 运行结果解读

实际运行（Python 3，瞬间完成；节选）：

```text
==============================================================================
CASE-STUDY MAPPER — proposed designs → closest 2026 reference
==============================================================================

design: 'research-assistant'
  type=research  n_agents=6  verification=True  hours=2.0

  closest case study: Anthropic Research (supervisor-worker)
  patterns to copy:
    - fresh-context subagents
    - orchestrator synthesis
    - rainbow deployment
    - verification role
  recommended framework: Anthropic Claude Agent SDK or LangGraph
  citation: https://www.anthropic.com/engineering/multi-agent-research-system

design: 'codegen-team'
  type=engineering  n_agents=5  verification=True  hours=1.0

  closest case study: MetaGPT / ChatDev (SOP role-decomposition)
  ...

design: 'agent-marketplace'
  type=population  n_agents=1000  verification=False  hours=24.0

  closest case study: OpenClaw / Moltbook (population-scale substrate)
  ...
  recommended framework: custom substrate + MCP + A2A

design: 'internal-automation'
  type=automation  n_agents=3  verification=True  hours=0.5

  closest case study: MetaGPT / ChatDev (SOP role-decomposition)
  ...
  recommended framework: CrewAI or MetaGPT reference impl

==============================================================================
FRAMEWORK LANDSCAPE — April 2026
==============================================================================
  framework                      status                 best for
  LangGraph                      production             structured graph + checkpointing + HITL
  CrewAI                         production             role-based crews; Sequential/Hierarchical
  AG2                            community maintenance  GroupChat + speaker selection
  Microsoft Agent Framework      RC (Feb 2026)          orchestration patterns + enterprise
  OpenAI Agents SDK              production             Swarm successor; tool-return handoffs
  Google ADK                     production (Apr 2025)  A2A-native; Google Cloud
  Anthropic Claude Agent SDK     production             agent + Research extension
  ...
```

逐项解读：

- **research-assistant → Anthropic Research**：命中第三条规则 `task_type == "research"`；`verification=True, hours=2.0` 看似"佐证"了这一选择，但实际上这两个值没有参与判断。
- **codegen-team → MetaGPT / ChatDev**：命中第二条规则（engineering 且角色分明）。推荐框架"CrewAI or MetaGPT reference impl"与讲义"CrewAI: strong for role decomposition"一致。
- **agent-marketplace → OpenClaw / Moltbook**：命中第一条规则。注意 `verification=False` 没有触发任何警告。
- **internal-automation → MetaGPT / ChatDev**：因为 `roles_distinct=True` 命中第二条规则。按讲义，经典企业自动化应参考 CrewAI 或 LangGraph——巧的是 MetaGPT 案例推荐的框架里也有 CrewAI，所以结论"碰巧"接近，但理由（"SOP 角色分解"）与讲义（"production leader, stable runtime"）不同。
- **框架表**：7 行，缺讲义中的 Microsoft AutoGen；`best for` 列 4 行超过 30 个字符，行长不一（真实输出中短行末尾还有多余空格，上面的摘录已去掉）。
- **Takeaways** 三句与讲义 Ship It 一致："Start from a case study"、"Adopt MCP + A2A"、需要验证、成本核算与 rainbow deploy。

---

## 7. 动手改一改

1. **补齐第四类案例**：在 `CASES` 中加入 `"enterprise_automation"`（推荐框架 "CrewAI or LangGraph"，模式如"确定性流程图、checkpoint、人工审批节点"），并让 `automation` 任务能映射到它。
2. **修掉死逻辑**：删掉或改写第 4 个 `if`，让 `verification_required`、`runtime_duration_hours`、`n_agents_expected` 真正参与判断；再枚举 64 种组合，观察三类（或四类）案例的分布变化。
3. **打分 + 理由**：把 `map_to_case` 改写成测验 Q10 的 `score_cases`，返回前两名和各自的命中理由；思考平局时如何处理。
4. **设计检查器**：实现测验 Q12 的 `lint_design`，把"无验证""无 prompt-injection 威胁模型""不用 MCP/A2A""生产前无 MAST 审计"变成告警，并在 `main` 中对每个设计打印。
5. **讲义练习 5**：为你手头的一个多 agent 项目构造一个 `Design`，运行映射器，再对照对应案例的 `patterns` 写下"本季度要采纳的一条设计决策"。
6. **外置框架表**：把 `FRAMEWORK_LANDSCAPE` 移到 JSON 文件中，加上 `as_of` 日期与来源字段，补回 AutoGen 一行；打印时按列最大长度动态定宽。

---

## 8. 常见坑

- **if 链的顺序就是优先级**：越靠前的规则"抢走"越多输入；改规则顺序会悄悄改变大量结果，应写测试覆盖关键组合。
- **字段定义了却没用**：`n_agents_expected` 等字段让人以为参与了判断，实际不影响结果，属于误导性接口。
- **重复分支掩盖死逻辑**：两个分支返回同一个值时，前一个条件的真假无关紧要，很难在阅读时发现。
- **裸字符串枚举**：`task_type` 拼错会静默落入默认分支，应校验取值。
- **字段语义有歧义**：`user_facing_network` 既可理解为"面向用户"也可理解为"agent 网络"，导致研究助手被映射到社交网络案例。
- **把框架状态写死**：讲义所述的框架格局在一年内多次变化（改名、合并、进入维护），代码里的表要带日期并定期更新。
- **只给推荐不给警告**：一个不做验证的系统也能拿到"可照搬的模式"，映射器应同时输出风险项。
