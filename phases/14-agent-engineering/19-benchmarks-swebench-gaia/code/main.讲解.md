# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 19 节 基准评测：SWE-bench、GAIA、AgentBench ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`typing`），不下载任何数据集、不需要 Docker

---

## 1. 这份代码在考察什么

这份 145 行的代码把两个基准的"评估规则"做成可以运行的玩具：

1. **SWE-bench 风格的 harness**：每个任务有一个"修复前状态"、一个由脚本给出的 patch、一组 FAIL_TO_PASS 检查和一组 PASS_TO_PASS 检查；`run_task` 在 patch 前后各跑一遍检查，判断任务是否 resolved。这对应讲义的核心："The patch must flip FAIL_TO_PASS tests ... without breaking PASS_TO_PASS tests."
2. **GAIA 风格的难度分类器**：用"步骤连接词 + 模态词 + 工具词"的计数估计问题需要几步、几种模态、几种工具，再映射到 Level 1/2/3。对应讲义的"Three difficulty levels; Level 3 requires long tool chains across modalities"。

这里的"代码库"被简化成一个 `dict[str, int]` 状态，"单元测试"被简化成对状态的布尔函数，"agent"被简化成一个固定的 `lambda` patch。

> 一句话：**把"打 patch → 跑两组测试 → 判 resolved"这条评估规则变成十几行可读的代码**；同时它的判定用的是"净变化计数"，存在可以被绕过的漏洞，GAIA 分类器也只是关键词启发式，这些恰好是理解"评估器是否稳健"的好材料。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Task` | dataclass | 任务 ID、描述、修复前状态、patch 函数、FAIL_TO_PASS 列表、PASS_TO_PASS 列表 | SWE-bench 任务实例 |
| `TaskResult` | dataclass | 两组测试的通过数/总数与 `resolved` | 单任务评测结果 |
| `run_task` | 函数 | patch 前后各跑一次检查，计算 resolved | SWE-bench evaluator |
| `gaia_level` | 函数 | 关键词计数 → 分数 → Level 1/2/3 | GAIA 难度分级（启发式） |
| `swe_demo` | 函数 | 3 个合成任务 + 打印每任务结果与 resolution rate | 演示 harness |
| `gaia_demo` | 函数 | 3 个问题的难度分级 | 演示分类器 |
| `main` | 函数 | 依次调用两个演示并打印要点 | 入口 |

数据流：

- SWE：`Task.state_before` → 复制 → 跑 FTP/PTP 检查（pre）→ `task.patch(复制)` → 跑 FTP/PTP 检查（post）→ `TaskResult` → 汇总 resolution rate。
- GAIA：问题字符串 → 小写 → 三类关键词计数 → 求和 → 阈值映射到级别。

---

## 3. 逐段精讲

### 3.1 `Task` 与 `TaskResult`：把基准实例写成数据

```python
@dataclass
class Task:
    tid: str
    description: str
    state_before: dict[str, int]
    patch: Callable[[dict[str, int]], dict[str, int]]
    fail_to_pass: list[tuple[str, Callable[[dict[str, int]], bool]]]
    pass_to_pass: list[tuple[str, Callable[[dict[str, int]], bool]]]
```

与真实 SWE-bench 的对应关系：

| 玩具字段 | 真实 SWE-bench |
|---------|---------------|
| `state_before` | 修复前 commit 的代码库快照 |
| `description` | issue 的自然语言描述 |
| `patch` | agent 产出的 diff（这里是一个"状态 → 新状态"的函数） |
| `fail_to_pass` | 参考修复后由失败变为通过的测试 |
| `pass_to_pass` | 修复前后都应通过的测试 |

- 每个测试是一个 `(名字, 检查函数)` 元组，名字用于报告，函数返回 `bool`。
- 类型注解里写的是 `dict[str, int]`，但任务 `t003` 的状态中有 `"flag": True`（布尔）——Python 中 `bool` 是 `int` 的子类，类型检查器不会报错，但注解并不精确。
- `TaskResult` 只记录通过数与总数；真实 harness 还会记录每个测试的名字与日志、步数、token、耗时（`outputs` 的要求）。

### 3.2 `run_task`：评估器的核心

```python
def run_task(task: Task) -> TaskResult:
    state = dict(task.state_before)
    ftp_pre = sum(1 for _, check in task.fail_to_pass if check(state))
    ptp_pre = sum(1 for _, check in task.pass_to_pass if check(state))

    new_state = task.patch(dict(state))

    ftp_post = sum(1 for _, check in task.fail_to_pass if check(new_state))
    ptp_post = sum(1 for _, check in task.pass_to_pass if check(new_state))

    ftp_fixed = ftp_post - ftp_pre
    ptp_broke = ptp_pre - ptp_post
    resolved = (ftp_post == len(task.fail_to_pass)) and (ptp_broke == 0)
```

逐行说明：

- `dict(task.state_before)` 复制一份，`task.patch(dict(state))` 再复制一份交给 patch——保证 patch 即使原地修改，也不会污染任务定义和"修复前"的状态。这相当于真实 harness 中"每次评测从干净的 checkout 开始"。
- `sum(1 for _, check in ... if check(state))` 用生成器统计通过的测试个数；`_` 表示不需要的测试名。
- **判定规则**：所有 FAIL_TO_PASS 在 patch 后通过（绝对条件），且 PASS_TO_PASS 的通过数**没有净减少**（相对条件）。

⚠️ 这条规则有三个漏洞（均已用额外脚本实际验证，详见测验 Q9）：

1. **净变化会互相抵消**：PTP 测试 A 被打坏、另一个原本失败的 PTP 测试 B 被"修好"，`ptp_broke = 0`，判为 resolved。真实 SWE-bench 要求 patch 后**每一个** PASS_TO_PASS 都通过。
2. **不校验任务有效性**：如果 PTP 测试在 patch 前就失败、之后仍失败，`ptp_broke = 0`，判为 resolved；如果 FTP 测试在 patch 前就已通过，一个什么都不做的 patch 也会被判为 resolved。真实数据集在构建时就会验证"FTP 修复前失败、PTP 修复前通过"，这也是 Verified 去掉"不可靠测试"的意义。
3. **patch 抛异常会让整个 harness 崩溃**：没有 `try`，例如 patch 访问不存在的键会直接抛 `KeyError`。

另外 `ftp_fixed` 被计算后**从未使用**，可以删除或写入结果用于报告。

```python
    return TaskResult(
        tid=task.tid,
        ftp_passed=ftp_post, ftp_total=len(task.fail_to_pass),
        ptp_passed=ptp_post, ptp_total=len(task.pass_to_pass),
        resolved=resolved,
    )
```

用关键字参数构造结果，可读性更好，也不怕字段顺序变化。

### 3.3 三个合成任务

```python
        Task(
            tid="t001",
            description="fix off-by-one in counter",
            state_before={"counter": 0, "multiplier": 2},
            patch=lambda s: {**s, "counter": s["counter"] + 1},
            fail_to_pass=[("counter > 0", lambda s: s["counter"] > 0)],
            pass_to_pass=[("multiplier unchanged", lambda s: s["multiplier"] == 2)],
        ),
```

- `{**s, "counter": ...}`：字典解包后覆盖一个键，生成**新字典**，原字典不变——这是"不可变更新"的常用写法。
- 三个任务分别演示了：
  - `t001`：修好 bug、不破坏其他测试 → resolved；
  - `t002`：同上（修 multiplier）→ resolved；
  - `t003`：修好了 counter（`1 → 2` 满足 `> 1`），但顺手把 `flag` 改成 `False`，打破 "flag stays true" → 未 resolved。讲义说的"agent overreaches"正是 coding agent 常见的失败：改了不该改的地方。
- 三个任务的 FTP 在 patch 前确实都失败、PTP 都通过，所以本例中上述漏洞没有被触发。

### 3.4 `gaia_level`：关键词计数的难度估计

```python
def gaia_level(question: str) -> int:
    steps = sum(1 for w in question.lower().split()
                if w in {"then", "after", "finally", "next", "and"}) + 1
    modalities = sum(word in question.lower() for word in
                     ("image", "video", "audio", "pdf", "chart", "graph"))
    tools = sum(word in question.lower() for word in
                ("search", "look up", "find", "visit", "extract"))
    score = steps + modalities + tools
    if score <= 2:
        return 1
    if score <= 5:
        return 2
    return 3
```

- **steps**：按空白切词，统计"连接词"个数再加 1（至少一步）。用集合 `{...}` 做成员判断是 O(1)。
- **modalities / tools**：`word in question.lower()` 是**子串**判断，返回 `True/False`，`sum` 把布尔当 0/1 相加。注意每个关键词最多计 1 次（出现多次也只算一次），而 steps 中的连接词每次出现都计数。
- **阈值**：`≤2` → Level 1，`3–5` → Level 2，`≥6` → Level 3。

演示中三个问题的拆解（已实际运行验证）：

| 问题 | steps | modalities | tools | 总分 | Level |
|------|-------|-----------|-------|------|-------|
| What is the capital of France? | 1 | 0 | 0 | 1 | 1 |
| Search for the Wikipedia article on ReAct and extract the first author. | 2 | 0 | 2 | 4 | 2 |
| Visit the arXiv listing ... then count ... and return the ratio ... | 3 | 1（pdf） | 2（visit、find） | 6 | 3 |

⚠️ 局限（测验 Q10 有完整算例）：

- `split()` 不去标点：`"then,"` 不等于 `"then"`，带逗号的连接词会被漏数；
- 子串匹配误报：`"paragraph"` 含 `"graph"`，`"findings"` 含 `"find"`；
- `"and"` 在列举中（"salt and pepper and oil"）会被误当成步骤；
- 真实 GAIA 的级别是题目作者根据解题所需的步骤与工具**人工标注**的，不是从问题文本推断的。这个函数只是把"深度 + 模态 + 工具 → 难度"的直觉具体化。

### 3.5 演示与打印

```python
    resolved_count = 0
    for task in tasks:
        result = run_task(task)
        ...
        if result.resolved:
            resolved_count += 1
    print(f"\nresolution rate: {resolved_count}/{len(tasks)}")
```

- resolution rate 只是"resolved 个数 / 任务数"。讲义 "Build It" 说输出会显示 "resolution rate per task + per difficulty"，但代码中两个演示是分开的：SWE 任务没有难度等级，GAIA 问题也没有被"解决"，所以并不存在"按难度的 resolution rate"。
- `q[:70]` 只打印问题前 70 个字符，第三个问题因此被截断成 `"... linked in the PDF, "`。
- 最后三行打印本节要点，其中 "report both your benchmark score AND the Verified/+-audited score" 对应讲义的 "Always report both"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 dict 状态代替代码库 | 不需要 git、Docker、真实仓库 | 无法体现环境搭建、依赖安装这些真实 harness 的主要难点 |
| 测试是对状态的 lambda | 一眼能看出测试在验证什么 | 真实测试是仓库里的 pytest 用例，需在沙箱中执行 |
| patch 是固定 lambda | 不需要模型即可演示评估规则 | 看不到 agent 的步数、token、成本；`outputs` 要求记录这些 |
| 复制状态后再 patch | 隔离每次评测 | 对应真实 harness 的"干净 checkout + 沙箱" |
| PTP 用净变化判定 | 代码短 | 可被"破坏一个、修好一个"绕过；应改为绝对判据 |
| 不校验任务有效性 | 演示任务本身是对的 | 无效任务会把空 patch 判为成功；应在建数据集时校验 |
| 不捕获 patch 异常 | 篇幅 | 一个崩溃的 patch 会中断整轮评测；应记为未解决 |
| GAIA 难度用关键词计数 | 直观演示"深度/模态/工具" | 误判多；真实 GAIA 难度是人工标注 |
| 只输出 resolution rate | 简洁 | 讲义批评单一数字；应输出每任务结果与 P50/P75/P95 分布 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件顶部 | 注解延迟求值 |
| `@dataclass` | `Task`、`TaskResult` | 自动生成构造函数等 |
| 复杂类型注解 | `list[tuple[str, Callable[[dict[str, int]], bool]]]` | "（名字, 检查函数）"元组的列表 |
| `Callable[[参数类型], 返回类型]` | `Callable[[dict[str, int]], dict[str, int]]` | 描述 patch 函数签名 |
| `dict(...)` 复制 | `state = dict(task.state_before)` | 浅拷贝字典，避免修改原对象 |
| 字典解包合并 | `{**s, "counter": s["counter"] + 1}` | 生成新字典并覆盖指定键 |
| `lambda` | `lambda s: s["counter"] > 0` | 匿名函数，作为测试与 patch |
| 生成器 + `sum` 计数 | `sum(1 for _, check in task.fail_to_pass if check(state))` | 统计满足条件的元素个数 |
| 布尔求和 | `sum(word in q for word in (...))` | `True` 计 1、`False` 计 0 |
| 集合成员判断 | `w in {"then", "after", ...}` | 集合查找为常数时间 |
| 子串判断 | `word in question.lower()` | 字符串的 `in` 是子串匹配，不是整词匹配 |
| `str.split()` | `question.lower().split()` | 按空白切分，不处理标点 |
| 提前返回（guard clause） | `if score <= 2: return 1`、`if score <= 5: return 2` | 依次判断阈值并提前返回，避免 `elif` 嵌套 |
| 关键字参数构造 | `TaskResult(tid=..., ftp_passed=..., ...)` | 按名字传参，可读性好 |
| 相邻字符串拼接 | `"Visit the arXiv ... " "then count ..."` | 多行写一个长字符串 |
| f-string 与切片 | `f"  [Level {level}] {q[:70]}"` | 截断长文本 |
| 字符串乘法 | `"-" * 70`、`"\n" + "-" * 70` | 生成分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，瞬间完成，输出确定）：

```text
======================================================================
BENCHMARKS: SWE-bench, GAIA — Phase 14, Lesson 19
======================================================================
----------------------------------------------------------------------
SWE-bench-style harness (FAIL_TO_PASS + PASS_TO_PASS)
----------------------------------------------------------------------
  t001: fix off-by-one in counter
    FAIL_TO_PASS: 1/1
    PASS_TO_PASS: 1/1
    resolved:     True
  t002: fix multiplier regression
    FAIL_TO_PASS: 1/1
    PASS_TO_PASS: 1/1
    resolved:     True
  t003: agent overreaches and breaks a passing test
    FAIL_TO_PASS: 1/1
    PASS_TO_PASS: 1/2
    resolved:     False

resolution rate: 2/3

----------------------------------------------------------------------
GAIA-style difficulty classifier
----------------------------------------------------------------------
  [Level 1] What is the capital of France?
  [Level 2] Search for the Wikipedia article on ReAct and extract the first author
  [Level 3] Visit the arXiv listing for ReAct, find the GitHub linked in the PDF, 

SWE-bench: patch-based, unit-test-gated. Verified removes ambiguity.
GAIA: depth + modalities + tools -> difficulty level.
report both your benchmark score AND the Verified/+-audited score.
```

逐项解读：

- **t001 / t002**：FTP 由 0/1 变为 1/1，PTP 保持 1/1 → resolved。
- **t003**：FTP 1/1 说明 bug 修好了，但 PTP 从 2/2 掉到 1/2，`ptp_broke = 1` → 未 resolved。这正是 PASS_TO_PASS 这道"不回归闸门"存在的理由：只看 FTP 会把它算作成功。`outputs` 甚至拒绝"只给 FAIL_TO_PASS 分数"的请求。
- **resolution rate 2/3**：这是唯一的汇总数字。讲义批评的 single-number fixation 在这里同样存在——它没告诉你 t003 是"修好了但有回归"，也没有成本和步数。
- **GAIA 三个级别**：拆解见 3.4 的表格。第二个问题末尾的句号被 `[:70]` 截掉了；第三个问题被截断在 "PDF, " 处。
- **没有演示到的情况**：PTP 净变化抵消、无效任务、patch 崩溃——我们用额外脚本验证了它们分别得到 `resolved=True`、`resolved=True`、`KeyError` 崩溃。

---

## 7. 动手改一改

1. **（入门）** 新增任务 `t004`：patch 修好 bug 但同时把 `multiplier` 改成 3，预测并验证输出；再新增一个 patch 什么都不做的任务，确认 FTP 为 0/1。
2. **（修 bug）** 把 `run_task` 改成绝对判据（每个 FTP 与 PTP 都必须通过），加上任务有效性校验和 patch 异常捕获（测验 Q9）。
3. **（讲义练习 2）** 给 `Task` 增加一个"agent 步骤"列表（多个小 patch 依次应用），统计每个任务的步数，输出 P50/P75/P95（测验 Q12 给出了 nearest-rank 算法）。
4. **（讲义练习 3）** 给 `Task` 加一个 `issue_text` 字段和一个 unified diff 形式的 patch 文本，实现 `leakage_ratio`，重叠 ≥ 30% 时在报告中标记（测验 Q11）。
5. **（改进分类器）** 用 `re.findall(r"\b\w+\b", q.lower())` 做词级匹配，修复标点与子串问题；再用测验 Q10 的三个反例检验。
6. **（进阶，讲义练习 1）** 选一个你自己的小仓库，用 `git worktree` 检出修复前的 commit，写 3 个针对已知 bug 的 FAIL_TO_PASS 测试，用 `subprocess.run(["python", "-m", "pytest", ...])` 在临时目录中执行，替换本代码中的 lambda 测试。注意在沙箱/容器中运行不可信 patch。

---

## 8. 常见坑

- **只看 FAIL_TO_PASS**：修好 bug 但打破其他功能的 patch 会被误判为成功；PASS_TO_PASS 不可省略。
- **用净变化代替绝对条件**：一个测试变坏、另一个变好会互相抵消。
- **不验证任务本身**：FTP 修复前就通过、PTP 修复前就失败的任务会让空 patch "成功"。
- **共享可变状态**：如果不复制 `state_before` 就交给 patch，原地修改会污染后续评测；本代码用 `dict(...)` 规避了这一点（注意只是浅拷贝，嵌套结构需要 `copy.deepcopy`）。
- **`split()` 与 `in` 的语义差异**：前者整词但不去标点，后者是子串匹配；混用会导致误判。
- **把关键词分类器当成 GAIA 难度**：真实难度来自人工标注，玩具分类器的输出不能用于报告。
- **只报告一个通过率**：至少同时给出每任务结果、步数与成本分布，以及 Verified / 审计后的分数。
