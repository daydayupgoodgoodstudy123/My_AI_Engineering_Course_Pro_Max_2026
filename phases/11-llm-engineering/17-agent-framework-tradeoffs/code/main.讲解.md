# 代码讲解 · main.py

> **所属小节**：阶段 11 · LLM 工程 · 第 17 节 Agent 框架权衡——图、角色与 Actor Orchestration ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（运行自带的 7 个用例）｜ `python main.py --ask`（交互问答） ｜ **依赖**：仅标准库（`argparse`、`json`、`sys`、`dataclasses`、`typing`），不调用任何 LLM、不需要网络

---

## 1. 这份代码在考察什么

本节是"Learn"类型的课，讲义没有 Build It 部分，`main.py` 实现的是讲义练习 3 要求的 `pick_framework.py`：把讲义里的选型权衡写成一棵**决策树**，输入一个问题描述，输出推荐的框架和一句话理由。它考察：

1. **把"问题形状"量化成信号**：类型化状态、角色、对话、并行 fanout、需要恢复、需要人工中断、LLM 调用次数、会话记忆。
2. **讲义的选型规则**：小任务不用框架；恢复/中断/fanout → LangGraph；对话 → AutoGen；角色 → CrewAI；单 agent + 会话记忆 → Agno；兜底 LangGraph。
3. **"用一句话解释为什么"**：讲义 Skill 的要求——"You can explain, in one sentence, why a given framework is right for a given agent problem"，所以每个推荐都带 `reason`。
4. **用测试固化规则**：7 个用例覆盖每条分支的典型场景。

> 一句话：**把选型经验变成可执行、可测试的规则**。但"有序 if 链"天然有两个问题——信号冲突时由判断顺序决定结果、漏检的字段会让结论与理由自相矛盾——这正是读这份代码时最该看出来的东西。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Problem` | 冻结 dataclass | 8 个字段描述任务形状（7 个布尔 + `total_llm_calls`） | 问题形状 |
| `Recommendation` | 冻结 dataclass | `framework` + `reason` | 一句话理由 |
| `recommend` | 函数 | 7 条有序规则，命中即返回 | 决策矩阵 |
| `_check` | 函数 | 对比实际与期望，打印 `[OK ]` / `[FAIL]` | 测试断言 |
| `run_tests` | 函数 | 7 个内置用例，返回退出码 0/1 | 回归测试 |
| `run_interactive` | 函数 | 逐项 `input()` 提问，输出 JSON | 交互模式 |
| `main` | 函数 | `argparse` 解析 `--ask`，二选一运行 | 命令行入口 |

数据流：命令行参数 → `main()` → `run_tests()`（构造 `Problem` → `recommend` → `_check`）或 `run_interactive()`（`input` → `Problem` → `recommend` → `json.dumps`）→ 返回码交给 `sys.exit`。

---

## 3. 逐段精讲

### 3.1 两个冻结 dataclass

```python
@dataclass(frozen=True)
class Problem:
    """Shape descriptor for an agentic task."""

    has_typed_state: bool = False
    has_roles: bool = False
    has_dialogue: bool = False
    has_parallel_fanout: bool = False
    needs_resume: bool = False
    needs_human_interrupt: bool = False
    total_llm_calls: int = 1
    needs_session_memory: bool = False
```

- 每个字段对应讲义 checklist 里的一个问题：
  - `has_typed_state`、`has_roles`、`has_dialogue` ↔ "Draw the shape"（图 / 组织架构 / 聊天）；
  - `needs_resume`、`needs_human_interrupt` ↔ "Check the state budget"；
  - `has_parallel_fanout` ↔ 决策矩阵"Thousands of parallel fanouts with reducers"；
  - `total_llm_calls` ↔ "Budget the framework overhead"；
  - `needs_session_memory` ↔ Agno 的 session store。
- 讲义练习 3 只要求 5 个字段（`has_typed_state, has_roles, has_dialogue, has_parallel_fanout, needs_resume`），代码多加了 `needs_human_interrupt`、`total_llm_calls`、`needs_session_memory`，更贴近讲义的 checklist。
- 讲义 checklist 第 4 条"Check the cost budget"（LLM 路由的 token 成本、每日运行量）**没有**对应字段；skill 文件里"每日运行量超过 10,000 次考虑纯 Python"的逃生口也没有实现（测验 Q12 让你补上）。
- `frozen=True`：实例不可修改（实测 `p.has_roles = True` 抛 `FrozenInstanceError`），并且自动可哈希，可以放进 set 或当 dict 的键。描述"问题"的值对象不应该被中途改动，这是合理的选择。
- 所有字段都有默认值，所以 `Problem()` 合法，测试里只需写出"打开"的信号。

### 3.2 规则 1：小任务不用框架

```python
    if p.total_llm_calls <= 2 and not any(
        (p.has_roles, p.has_dialogue, p.needs_resume, p.has_parallel_fanout, p.needs_human_interrupt)
    ):
        return Recommendation(
            "plain python",
            "Two or fewer LLM calls with no state, roles, dialogue, fanout, "
            "or resume needs; a framework is pure overhead.",
        )
```

- 对应讲义"no framework is cheaper than no framework"。放在最前面，体现"smallest-first"（注释原话）。
- `any((...))` 接收一个元组，任一为真即为真。
- 两段相邻的字符串字面量会被 Python 自动拼接成一个字符串。
- ⚠️ **漏检**：元组里没有 `has_typed_state` 和 `needs_session_memory`。因此 `Problem(has_typed_state=True, needs_session_memory=True, total_llm_calls=2)` 会得到 `plain python`，理由写着"with no state"，与输入矛盾（已实测；交互模式同样复现）。修复：把 7 个信号都纳入，或至少加入 `needs_session_memory`，并让理由文本与条件一致（测验 Q9）。

### 3.3 规则 2：恢复 / 中断 / fanout → LangGraph

```python
    if p.needs_resume or p.needs_human_interrupt or p.has_parallel_fanout:
        return Recommendation(
            "langgraph",
            "Typed state, checkpointer, interrupts, and Send fanout are only "
            "first-class in LangGraph.",
        )
```

- 对应讲义"If yes, LangGraph is the default"和决策矩阵"LangGraph + `Send` — The only one with a first-class parallel-dispatch API"。
- 这是一条"一票决定"的规则：三个信号任一为真，后面的对话、角色、记忆全部不再看。所以"角色 + 需要恢复"→ LangGraph，"对话 + 人工中断"→ LangGraph（均已实测）。
- 讲义对 CrewAI/AutoGen 的描述是"开箱没有持久化，需要自己接"，而不是"不能"；把所有恢复需求都判给 LangGraph 是一种保守简化。skill 文件对 Agno 也有限定说明：Agno 有 `Parallel` 块，只是没有 `Send` 风格的 fanout-and-reduce API。

### 3.4 规则 3、4：对话 → AutoGen，角色 → CrewAI

```python
    if p.has_dialogue and not p.has_typed_state:
        return Recommendation("autogen", ...)

    if p.has_roles and not p.has_typed_state:
        return Recommendation("crewai", ...)
```

- `not p.has_typed_state` 的含义：一旦需要类型化状态，就不推荐状态能力弱的 AutoGen/CrewAI（讲义：AutoGen 的"state is the chat history"，CrewAI "State flows as strings between tasks"）。
- ⚠️ **顺序即优先级**：对话写在角色前面，所以 `Problem(has_roles=True, has_dialogue=True, total_llm_calls=5)` → `autogen`，CrewAI 规则根本不会被检查（已实测）。讲义没有规定这个优先级。

### 3.5 规则 5、6、7：Agno、类型化状态、兜底

```python
    if p.needs_session_memory and not p.has_roles and not p.has_dialogue:
        return Recommendation("agno", ...)

    if p.has_typed_state:
        return Recommendation("langgraph", ...)

    return Recommendation(
        "langgraph",
        "Default for multi-step agents with any uncertainty about future state "
        "or branching needs.",
    )
```

- Agno 规则排在 typed-state 规则之前，所以"类型化状态 + 会话记忆"（≥3 次调用）→ `agno`。讲义把"带自定义 reducer 的深度显式分支图"列为 Agno 的 worst fit，但"有类型化状态"本身并不等于需要复杂图，这个结果可以接受，只是同样属于"顺序决定"的隐含取舍。
- `not p.has_roles and not p.has_dialogue` 并不多余：有角色/对话且有类型化状态的问题会越过规则 3、4 到达这里，这两个条件把它们挡在 Agno 之外，交给后面的 LangGraph。
- **兜底是 LangGraph**：≥3 次调用、没有任何信号的任务也会被推荐 LangGraph（`Problem(total_llm_calls=50)` → `langgraph`）。这与讲义"Refuse to reach for a framework before you can draw the graph..."的精神有张力——没有任何形状信号时，更合理的建议可能是"先画出形状"或纯 Python。

**整体偏向**：穷举 7 个布尔字段的 128 种组合（`total_llm_calls=10`），结果为 `langgraph 120、autogen 4、crewai 2、agno 2`（已实测）。只要 resume/interrupt/fanout 任一为真就有 112 种直接落到 LangGraph。

### 3.6 测试：`_check` 与 `run_tests`

```python
def _check(label: str, actual: Recommendation, expected_framework: str) -> bool:
    ok = actual.framework == expected_framework
    tag = "OK " if ok else "FAIL"
    print(f"[{tag}] {label:<60}  -> {actual.framework:<14} // {actual.reason}")
    return ok

def run_tests() -> int:
    cases: list[tuple[str, Problem, str]] = [
        ("two-call summarizer, no state", Problem(total_llm_calls=2), "plain python"),
        ...
    ]
    failures = 0
    for label, problem, expected in cases:
        if not _check(label, recommend(problem), expected):
            failures += 1
    print()
    print(f"{len(cases) - failures}/{len(cases)} cases passed.")
    return 0 if failures == 0 else 1
```

- `"OK "` 末尾带一个空格，让它和 `"FAIL"` 等宽，输出对齐。
- `run_tests` 返回 0/1，`main` 把它传给 `sys.exit`，这样 CI 可以根据退出码判断成败（实测退出码 0）。
- 用例是 `(标签, 输入, 期望)` 三元组列表——表驱动测试，加用例只需加一行。
- ⚠️ 7 个用例每个只打开一个"主信号"（外加 `has_typed_state`），恰好沿着每条规则的"顺风方向"，所以全部通过；但没有任何"信号冲突"或"边界"用例，3.2、3.4 中的问题都测不出来。这是"测试全绿 ≠ 规则正确"的典型例子。

### 3.7 交互模式

```python
def run_interactive() -> int:
    def yes(prompt: str) -> bool:
        return input(f"{prompt} [y/N] ").strip().lower().startswith("y")

    p = Problem(
        has_typed_state=yes("Typed state / explicit state schema?"),
        ...
        total_llm_calls=int(input("Approx LLM calls per run? ").strip() or "1"),
        needs_session_memory=yes("Needs durable per-user session memory?"),
    )
    r = recommend(p)
    print()
    print(json.dumps({"framework": r.framework, "reason": r.reason}, indent=2))
    return 0
```

- `yes()` 是嵌套函数：`[y/N]` 表示默认 No，只有以 `y` 开头（不分大小写）才算是。
- 关键字参数里的函数调用按书写顺序求值，所以提问顺序就是字段顺序。
- `.strip() or "1"`：直接回车得到空串，`or` 取默认值 `"1"`。
- ⚠️ 健壮性：输入 `about five` → `ValueError`；标准输入关闭（如管道为空）→ `EOFError`，都会带 traceback 退出（已实测）。测验 Q11 给出了重试与友好退出的写法。
- 输出用 `json.dumps(..., indent=2)`，方便被其他脚本解析。

### 3.8 命令行入口

```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ask", action="store_true", help="interactive mode")
    args = parser.parse_args()
    return run_interactive() if args.ask else run_tests()

if __name__ == "__main__":
    sys.exit(main())
```

- `action="store_true"`：出现 `--ask` 时为 `True`，否则 `False`，不需要参数值。
- `sys.exit(main())`：把返回值作为进程退出码，是命令行工具的惯用写法。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 有序 if 链 | 简单、每条规则对应讲义一句话、易读 | 冲突信号由顺序决定且无文档；可改成打分制（每个框架对每个信号加权）并输出前两名 |
| 小任务规则放第一 | 体现"no framework is cheaper than no framework" | 漏检字段导致理由矛盾；条件和理由应同源生成 |
| 恢复/中断/fanout 一票决定 LangGraph | 讲义认为这些能力只有 LangGraph 是一等公民 | 128 种组合中 120 种推荐 LangGraph，偏向明显 |
| 兜底 LangGraph | 不确定时选状态能力最强的 | 与"先画出形状再选框架"冲突；可兜底为"信息不足，请先描述形状" |
| 冻结 dataclass | 值对象不可变、可哈希 | 无 |
| 每个推荐带一句理由 | 落实讲义 Skill | 理由是固定字符串，不会根据输入解释"为什么没选别的" |
| 表驱动测试 + 退出码 | 便于 CI | 只覆盖单信号用例；应补充冲突与边界用例、或穷举断言不变量 |
| 不含成本/流量维度 | 保持简单 | 讲义 checklist 第 4 条和 skill 的 10,000 次/天逃生口未实现 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可写 `list[tuple[str, Problem, str]]` |
| `@dataclass(frozen=True)` | `class Problem`、`class Recommendation` | 自动生成 `__init__`/`__repr__`/`__eq__`/`__hash__`；实例不可修改 |
| 字段默认值 | `has_roles: bool = False` | 构造时可省略 |
| 关键字参数构造 | `Problem(has_roles=True, total_llm_calls=4)` | 只写需要的字段，可读性高 |
| `any(iterable)` | `any((p.has_roles, p.has_dialogue, ...))` | 任一为真即返回 `True` |
| 布尔运算组合 | `p.has_dialogue and not p.has_typed_state` | `and`/`or`/`not`，自带短路 |
| 相邻字符串自动拼接 | `"Two or fewer ... " "or resume needs; ..."` | 括号内多行字面量合并成一个字符串 |
| 早返回 | 每条规则命中即 `return` | 避免深层嵌套 if/else |
| 私有约定 | `_check` | 下划线前缀表示"内部使用" |
| 条件表达式 | `"OK " if ok else "FAIL"`、`0 if failures == 0 else 1` | 一行 if/else |
| f-string 对齐 | `{label:<60}`、`{actual.framework:<14}` | 左对齐并填充到指定宽度 |
| 类型注解的复合类型 | `cases: list[tuple[str, Problem, str]]` | 列表里每个元素是三元组 |
| 元组解包循环 | `for label, problem, expected in cases:` | 一次取出三个值 |
| 嵌套函数 | `run_interactive` 里的 `def yes(...)` | 只在局部使用的辅助函数 |
| `input()` 与字符串方法链 | `input(...).strip().lower().startswith("y")` | 读一行、去空白、转小写、判断前缀 |
| `or` 提供默认值 | `input(...).strip() or "1"` | 空串为假，取右边 |
| `int()` 转换 | `int("5")` | 非法字符串抛 `ValueError` |
| `json.dumps(..., indent=2)` | 交互模式输出 | 把 dict 序列化成带缩进的 JSON 字符串 |
| `argparse` | `parser.add_argument("--ask", action="store_true")` | 声明式解析命令行参数 |
| `sys.exit(code)` | `sys.exit(main())` | 以指定退出码结束进程 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行，被 import 时（如测验中的穷举脚本）不执行 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（瞬时完成，退出码 0）：

```text
[OK ] two-call summarizer, no state                                 -> plain python   // Two or fewer LLM calls with no state, roles, dialogue, fanout, or resume needs; a framework is pure overhead.
[OK ] long-running workflow with human approval                     -> langgraph      // Typed state, checkpointer, interrupts, and Send fanout are only first-class in LangGraph.
[OK ] research with parallel fanout to three retrievers             -> langgraph      // Typed state, checkpointer, interrupts, and Send fanout are only first-class in LangGraph.
[OK ] proposer-critic coding loop                                   -> autogen        // Proposer-critic or teacher-student dialogue is AutoGen's native shape; GroupChat selects speakers without hand-wiring.
[OK ] marketing pipeline with researcher/writer/editor roles        -> crewai         // Specialist roles with a short sequential or hierarchical plan are cheapest to express in CrewAI.
[OK ] chat assistant with persistent user memory                    -> agno           // Single agent with tools and persistent session memory; Agno's storage drivers are built in.
[OK ] workflow that must resume after crash                         -> langgraph      // Typed state, checkpointer, interrupts, and Send fanout are only first-class in LangGraph.

7/7 cases passed.
```

逐项解读：

- 第 1 行走规则 1；第 2、3、7 行走规则 2（分别由 interrupt、fanout、resume 触发，理由文本相同）；第 4 行规则 3；第 5 行规则 4；第 6 行规则 5。7 条规则中只有规则 6（仅类型化状态）和规则 7（兜底）没有被测试覆盖。
- 规则 2 的三个用例理由完全一样，说明理由是"按分支"而不是"按输入"生成的：用户无法从输出看出到底是哪个信号触发了 LangGraph。

交互模式实测：

```text
$ printf 'y\nn\nn\nn\nn\nn\n2\ny\n' | python3 main.py --ask
...
{
  "framework": "plain python",
  "reason": "Two or fewer LLM calls with no state, roles, dialogue, fanout, or resume needs; a framework is pure overhead."
}
```

回答了"有类型化状态""需要会话记忆"，得到的理由却是"no state"——第 3.2 节的漏检在交互模式下同样出现。输入 `about five` 作为调用次数时抛 `ValueError`；空输入流时抛 `EOFError`。

穷举实验（固定调用次数、7 个布尔字段 128 种组合，结果为各框架被推荐的次数）：

| `total_llm_calls` | plain python | langgraph | autogen | crewai | agno |
|------------------|-------------|-----------|---------|--------|------|
| 1 或 2 | 4 | 118 | 4 | 2 | 0 |
| 3 或 10 | 0 | 120 | 4 | 2 | 2 |

1–2 次调用时 `agno` 为 0，因为本该推荐 Agno 的组合全被规则 1 截走；修复漏检后变为 `plain python 1、agno 2、langgraph 119`。

---

## 7. 动手改一改

1. **修复规则 1**：把 7 个信号都纳入"是否需要框架"的判断，并新增测试 `Problem(has_typed_state=True, needs_session_memory=True, total_llm_calls=1)` 期望 `agno`；重跑穷举确认分布变化。
2. **补冲突用例**：为"角色 + 对话""类型化状态 + 会话记忆""角色 + 需要恢复""没有任何信号但 50 次调用"各写一个用例，先写下你认为正确的答案，再看代码是否同意；不同意的地方是改代码还是改预期，写出理由。
3. **按输入生成理由**：让规则 2 的理由说明是哪个信号触发的（如 `"needs_resume → checkpointer required"`），并在理由末尾列出"为什么没选 CrewAI/AutoGen"。
4. **加入成本维度**：实现测验 Q12 的 `daily_runs` 和 `llm_routing_decisions`，验证"每天 5,000 次、每次 10 次路由决策"的路由成本约 $157.5/天。
5. **打分制重写**：给每个框架定义 `{信号: 权重}`，得分最高者胜出，输出前两名与分差；用穷举统计对比新旧两版的推荐分布，讨论哪种更符合讲义的决策矩阵。
6. **进阶（讲义练习 1、2）**：用同一个任务（"研究 Anthropic 总部，写 200 字简报并注明来源"）分别在 LangGraph 和纯 Python 中实现，记录代码行数、每次运行 token 数、能否崩溃恢复、能否在写作前插入人工审批，把实测结果反过来校准决策树。

---

## 8. 常见坑

- **以为测试全绿就代表规则正确**：自带用例只覆盖单信号的顺风情形，组合问题全部漏网。
- **条件与理由文本不同步**：改了条件忘了改理由（或反之），用户会看到自相矛盾的解释。
- **有序规则的隐含优先级**：谁写在前面谁赢，调整顺序会悄悄改变大量结果；应在文档或测试中显式写出优先级。
- **把"需要恢复"等同于"必须 LangGraph"**：讲义说其他框架是"开箱没有、需要自己接"，不是"不能"；在已有 Agno/CrewAI 代码库里，接一个存储层可能比迁移框架更便宜。
- **忽视成本维度**：LLM 选择路由每一轮都花 token，高频场景下比框架本身的开销更大。
- **`int(input())` 不做校验**：交互工具遇到非数字或 EOF 直接崩溃。
- **讲义引用错位**：英文讲义"Further Reading"提到的"Phase 11 · 19 (Reflexion)"和"Phase 11 · 22 (Production observability)"在本课程中并不存在（阶段 11 只到第 17 节）；对应内容在 [阶段 14 · 03 Reflexion](../../../14-agent-engineering/03-reflexion-verbal-rl/docs/zh.md) 与 [阶段 14 · 24 Agent 可观测性](../../../14-agent-engineering/24-agent-observability-platforms/docs/zh.md)。中文机翻版术语混乱（如"国家计划"实为"state schema"、"船员"实为"crew"），以英文版为准。
