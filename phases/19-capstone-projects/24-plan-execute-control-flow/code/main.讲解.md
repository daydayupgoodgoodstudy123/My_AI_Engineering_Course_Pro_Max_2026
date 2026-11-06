# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 24 节 计划—执行控制流程 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试：`python3 -m pytest -q tests` 或 `python3 -m unittest discover -s tests` ｜ **依赖**：仅标准库（`json`、`time`、`dataclasses`、`typing`），需 Python ≥ 3.10（模块级使用了 `str | None`）

---

## 1. 这份代码在考察什么

这份代码实现了一个**串行的 plan-and-execute 执行器**，外加一个不调用模型的确定性 planner，用来覆盖执行器的每一条状态转移路径：

1. **计划是数据**：`Step` 用 dataclass 表示，执行器可以检查、记录、比较计划。
2. **失败交回 planner**：步骤抛异常 → 把 `"异常类名: 消息"` 作为 `last_error` 交给 planner → 拿到新计划、游标归零继续执行。
3. **修订可见**：每次重规划都计算 `PlanDiff` 并发出 `plan.diff` 事件。
4. **两个硬预算**：`max_steps`（步骤执行总数）与 `max_replans`（重规划次数）。
5. **结构化结果**：`SessionResult(status, reason, history, revisions, events)`，供第 20 课的 harness 读取。

> 一句话：**把"失败 → 重规划 → 继续"写成一个可测试的小状态机，并让每次改计划都在事件流里留下痕迹。** 同时要看清它在预算检查时序、对象复用、结果语义上的几处简化。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Step` | dataclass | 一个计划步骤；`signature()` 返回 `(tool_name, 排序后的 args JSON)` | Step 形状 |
| `PlanDiff` | dataclass | 一次修订的 `removed / added / revised` | Plan diff |
| `Event` | dataclass | 事件类型 + payload + 时间戳 | 事件流 |
| `SessionResult` | dataclass | 会话结果，`to_dict()` 可序列化 | 结果形状 |
| `Planner` / `ToolExecutor` | 类型别名 | planner 与执行函数的签名 | Planner 契约 |
| `ToolFailure` | 异常类 | 演示用的工具失败 | 失败 |
| `_diff_plans` | 函数 | 按 id 集合与签名计算 diff | Plan diff |
| `PlanExecuteAgent` | 类 | `run(goal)` 是整个状态机 | 执行器 |
| `_summarize` | 函数 | 把计划压缩成 `{id, tool, outcome}` 列表放进事件 | 事件 payload |
| `make_deterministic_planner` | 工厂函数 | 返回闭包 planner：首次 4 步，失败后按 `recovery` 给出替代计划 | 确定性 planner |
| `_demo` | 函数 | 步骤 2 被强制失败、route_around 成功的演示 | 演示 |

数据流：`_demo` 构造 planner 与 executor → `PlanExecuteAgent.run("ship the report")` → planner 产出计划 → 逐步调用 executor → 失败时 planner 重规划、`_diff_plans` 产出 diff → 返回 `SessionResult` → 打印 JSON 摘要。

---

## 3. 逐段精讲

### 3.1 `Step` 与签名

```python
@dataclass
class Step:
    id: int
    tool_name: str
    args: dict
    expected_outcome: str
    result: Any | None = None
    error: str | None = None

    def signature(self) -> tuple:
        return (self.tool_name, json.dumps(self.args, sort_keys=True))
```

- 前四个字段由 planner 填写，`result / error` 由执行器回填——同一个对象既是"计划"又是"执行记录"（这一点在 3.6 会成为问题）。
- `signature()` 用 `json.dumps(..., sort_keys=True)` 把 dict 规范化成字符串：`{"a":1,"b":2}` 与 `{"b":2,"a":1}` 得到同一签名。dict 本身不可哈希，转成字符串后才能放进元组比较。
- `expected_outcome` **不在签名里**：只改它不会被视为"revised"。讲义："It is not enforced by the executor."
- 代价：args 必须可 JSON 序列化。实测把 `set` 放进 args，在 `_diff_plans` 里抛 `TypeError: Object of type set is not JSON serializable`，而这一行不在 `try` 之内，会直接让 `run()` 崩溃。

### 3.2 结果与事件的 dataclass

```python
@dataclass
class Event:
    type: str
    payload: dict
    ts: float = field(default_factory=time.time)
```

- `field(default_factory=time.time)`：每创建一个 Event 调用一次 `time.time()`。如果写成 `ts: float = time.time()`，时间戳会在**类定义时**被固定成同一个值。
- `SessionResult.to_dict()` 把 `history` 中的 Step 压成 `{"id","tool","args","result","error"}`，events 带上 `ts`，方便直接 `json.dumps`（前提是 `result` 可序列化）。

### 3.3 类型别名

```python
Planner = Callable[[str, list[Step], str | None], list[Step]]
ToolExecutor = Callable[[str, dict], Any]
```

- 这是**运行时执行**的普通赋值，不受 `from __future__ import annotations` 影响，所以 `str | None` 要求 Python 3.10+、`list[Step]` 要求 3.9+。
- `Planner` 与讲义的签名一致：`planner(goal, history, last_error) -> list[Step]`。

### 3.4 `_diff_plans`：按 id 做集合运算

```python
def _diff_plans(old: list[Step], new: list[Step], revision: int) -> PlanDiff:
    old_ids = {s.id for s in old}
    new_ids = {s.id for s in new}
    removed = sorted(old_ids - new_ids)
    added = sorted(new_ids - old_ids)
    revised: list[int] = []
    old_by_id = {s.id: s for s in old}
    for s in new:
        if s.id in old_ids and old_by_id[s.id].signature() != s.signature():
            revised.append(s.id)
    return PlanDiff(revision=revision, removed=removed, added=added, revised=revised)
```

- `removed = 旧 − 新`、`added = 新 − 旧`、`revised = 交集中签名变化的`，与讲义定义一致。
- 调用处传入的 `old` 是 `plan[cursor:]`——旧计划中**还没成功执行**的部分（含刚失败的那一步）。已成功的步骤不参与比较。
- 假设：**同一个 id 在各次修订中表示同一个逻辑步骤**。实测 planner 把 `[2 b, 3 c]` 重新编号为 `[1 b2, 2 c]` 时，diff 给出 `removed [3]、added [1]、revised [2]`，而真实变化只是"b 换成 b2"（见测验 Q12）。
- 若 planner 返回完全相同的计划，diff 三个列表都为空——"什么都没改"本身是一个有用信号，但执行器没有利用它。

### 3.5 `run()`：主状态机

初始化与首次规划：

```python
        plan = self._planner(goal, history, None)
        self._emit("plan.commit", {"revision": 0, "steps": _summarize(plan)})

        if not plan:
            self._emit("session.complete", {"reason": "no_plan"})
            return SessionResult(status="failed", reason="no_plan", ...)
```

- 首次调用 `last_error=None`。空计划直接 `failed / no_plan`（测试 `test_no_plan_initial`）。
- 注意即使计划为空也先发了 `plan.commit`。

主循环——执行一步：

```python
        while cursor < len(plan):
            if steps_taken >= self.max_steps:
                ...return SessionResult(status="failed", reason="step_budget", ...)

            step = plan[cursor]
            self._emit("step.start", {"step_id": step.id, "tool": step.tool_name})
            try:
                step.result = self._executor(step.tool_name, step.args)
                self._emit("step.end", {"step_id": step.id, "outcome": "ok"})
                history.append(step)
                cursor += 1
                steps_taken += 1
                continue
            except Exception as exc:
                step.error = f"{type(exc).__name__}: {exc}"
                self._emit("step.end", {"step_id": step.id, "outcome": "error", "error": step.error})
                history.append(step)
                steps_taken += 1
                last_error = step.error
```

- **步骤预算在执行之前检查**：`max_steps=12` 意味着最多执行 12 步；恰好 12 步全部成功会正常 `goal_met`（实测）。
- 成功：写 `result`、记入历史、游标 +1，`continue` 回到循环顶部。
- 失败：错误格式化为 `"ToolFailure: transform marker-forced failure"` 这种"类名: 消息"形式，失败步骤**也进入 history、也消耗步骤预算**。
- `except Exception` 不区分异常种类：执行器自身的 bug 也会被当作"可重规划失败"。讲义里的 "failure-fatal" 在代码中只对应预算耗尽和 `no_plan`。

主循环——重规划：

```python
            if replans_used >= self.max_replans:
                ...return SessionResult(status="failed", reason="replan_budget", ...)

            replans_used += 1
            revision += 1
            new_plan = self._planner(goal, history, last_error)
            self._emit("plan.draft", {"revision": revision, "steps": _summarize(new_plan)})
            if not new_plan:
                ...return SessionResult(status="failed", reason="no_plan", ...)
            diff = _diff_plans(plan[cursor:], new_plan, revision)
            revisions.append(diff)
            self._emit("plan.diff", diff.to_dict())
            plan = new_plan
            cursor = 0
            self._emit("plan.commit", {"revision": revision, "steps": _summarize(plan)})
```

- **重规划预算在失败之后检查**：`max_replans=0` 时第一次失败就返回 `replan_budget`；`max_replans=2` 时允许 2 次重规划，第 3 次失败返回（失败步骤被执行 `max_replans + 1` 次）。
- 事件顺序：`plan.draft`（planner 的草稿）→ `plan.diff` → `plan.commit`（执行器采纳）。草稿为空时只有 `plan.draft` 没有 `plan.diff`。
- 新计划从游标 0 开始执行，旧计划剩余部分被整体替换——planner 负责给出"从当前位置往后"的计划，讲义："returns the next plan starting from the cursor"。
- ⚠️ **预算检查时序漏洞**：失败分支没有检查步骤预算。若第 12 步失败，执行器仍会调用 planner（真实场景下是一次 LLM 请求）、发 diff、提交新计划，回到循环顶部才返回 `step_budget`。实测：planner 被调用 2 次，最后事件为 `plan.draft, plan.diff, plan.commit, session.complete`。讲义说 "The executor will refuse the replan"，与代码不符（测验 Q9）。

收尾：

```python
        self._emit("session.complete", {"reason": "goal_met"})
        return SessionResult(status="completed", reason="goal_met", ...)
```

- 只要最后一份计划跑完就是 `goal_met`。⚠️ 这包括 `give_up` 路径：planner 改成 `[log_failure, notify_user]` 并成功执行后，结果同样是 `completed / goal_met`（实测），尽管原目标并未达成（测验 Q4）。

### 3.6 隐藏问题：Step 对象被原地修改

执行器直接修改 planner 返回的 `Step` 对象，成功时不清空 `error`。若 planner 每次返回同一个对象（例如缓存的计划常量），实测 `history` 中两条记录是同一对象，都显示 `('ok', 'ToolFailure: first fail')`。修复：执行前复制一份

```python
step = dataclasses.replace(plan[cursor], result=None, error=None)
```

已验证修改后原有 8 个测试全部通过（测验 Q10）。另外 `history` 列表本身也直接传给了 planner，planner 若修改它会影响执行器状态；讲义说 planner 是 "A pure function"，但执行器没有强制这一点。

### 3.7 `make_deterministic_planner`：闭包工厂

```python
def make_deterministic_planner(fail_step_id: int | None, recovery: str = "route_around") -> Planner:
    def planner(goal, history, last_error):
        if last_error is None:
            initial = [
                Step(1, "fetch", {"key": "input"}, "loaded user input"),
                Step(2, "transform", {"mode": "v1"}, "computed v1 form"),
                Step(3, "render", {}, "rendered output"),
                Step(4, "submit", {}, "submitted to backend"),
            ]
            if fail_step_id is not None:
                for s in initial:
                    if s.id == fail_step_id:
                        s.args = {**s.args, "_force_fail": True}
            return initial
        if recovery == "route_around" and "transform" in last_error:
            return [Step(2, "transform", {"mode": "v2"}, "computed via fallback"), ...]
        if recovery == "give_up":
            return [Step(98, "log_failure", {"why": last_error or ""}, ...),
                    Step(99, "notify_user", {}, ...)]
        return []
    return planner
```

- 外层函数的参数 `fail_step_id`、`recovery` 被内层 `planner` **捕获**（闭包），返回的函数符合 `Planner` 签名。
- 每次调用都新建 Step 对象，所以不会触发 3.6 的问题。
- `{**s.args, "_force_fail": True}` 构造新 dict，不修改原字面量。
- `_force_fail` 是给执行器的"测试钩子"：执行器约定见到它就抛异常；新计划中没有这个标记，所以 route_around 能成功。
- 与讲义的小差异：讲义写 "last_error matches Y → two-step plan"，代码的 `give_up` 分支**不看错误内容**，任何错误都走放弃路径；`route_around` 则只看错误串里是否包含 `"transform"`（子串匹配，很脆弱）。

### 3.8 `_demo`

```python
    def executor(tool: str, args: dict) -> Any:
        if args.get("_force_fail"):
            counters["transform_v1_calls"] += 1
            raise ToolFailure(f"{tool} marker-forced failure")
        ...
        if tool == "transform":
            if args.get("mode") == "v1":
                counters["transform_v1_calls"] += 1
                raise ToolFailure("transform v1 backend down")
            return {"ok": True}
```

- demo 中步骤 2 是被 `_force_fail` 标记弄失败的，"v1 backend down" 分支在 demo 中**从未被执行**；计数器名 `transform_v1_calls` 实际统计的是 marker 失败次数（结果为 1）。
- 未知工具会抛 `ToolFailure("unknown tool ...")`，同样会触发重规划。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 计划用 dataclass 列表表示 | 可检查、可 diff、可序列化 | 生产中通常用 JSON Schema 约束 LLM 输出，再经 registry 校验 |
| 确定性 planner，不调模型 | 每条转移路径都可重复测试 | 真实 planner 输出不稳定，需要容错解析与重试 |
| 按 id 计算 diff | 实现简单 | planner 重新编号会产生误导性 diff；可用签名序列对齐或稳定 key |
| `except Exception` 一律可重规划 | 演示简洁 | 应区分瞬时错误（退避重试）、语义错误（重规划）、致命错误（终止） |
| 步骤预算在循环顶部检查 | 逻辑集中 | 失败后仍会白调一次 planner；应在重规划前也检查 |
| 直接修改 planner 返回的 Step | 少一次复制 | 对象复用时 `error` 残留、history 别名；用 `dataclasses.replace` 复制 |
| 计划跑完即 `goal_met` | 执行器不理解目标 | 需要终止性步骤标记或验证门（第 25 课）判断目标是否真正达成 |
| 严格串行 | 讲义："easier to add once the linear executor is pinned" | 独立步骤可并行（讲义提到的 `gather_step`），需要依赖图 |
| 新计划从游标 0 执行 | planner 负责"从当前位置往后"的计划 | 不读 history 的 planner 会重跑已成功的步骤（partial-plan caching 需 planner 配合） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值（变成字符串），注解里可以前向引用；但不影响普通赋值语句 |
| `@dataclass` | `class Step:` | 自动生成 `__init__`、`__repr__`、`__eq__`；带默认值的字段必须放在后面 |
| `field(default_factory=...)` | `ts: float = field(default_factory=time.time)` | 每个实例单独调用工厂函数；可变默认值（list/dict）也必须这样写 |
| `dataclasses.replace` | 修复建议中 | 复制一个 dataclass 实例并替换部分字段 |
| 联合类型 `X \| None` | `result: Any \| None = None` | Python 3.10+ 写法，等价于 `Optional[X]` |
| 内置泛型 | `list[Step]`、`dict` | Python 3.9+ 可直接写 `list[int]` |
| `Callable` 类型别名 | `Planner = Callable[[str, list[Step], str \| None], list[Step]]` | 描述"接收这些参数、返回这个类型"的函数 |
| 仅限关键字参数 | `def __init__(self, planner, executor, *, max_steps=12, ...)` | `*` 之后的参数只能用 `max_steps=...` 形式传入 |
| 自定义异常 | `class ToolFailure(Exception): pass` | 继承 `Exception` 即可 |
| `try / except ... as` | `except Exception as exc:` | 捕获异常对象；`type(exc).__name__` 取类名 |
| 集合推导与集合运算 | `{s.id for s in old}`、`old_ids - new_ids` | 差集运算；`sorted()` 把集合转成有序列表 |
| 字典推导 | `{s.id: s for s in old}` | 建立 id → Step 的索引 |
| 字典解包合并 | `{**s.args, "_force_fail": True}` | 生成新 dict，不修改原 dict |
| 闭包 | `make_deterministic_planner` 返回内部 `planner` | 内部函数记住外层变量 `fail_step_id`、`recovery` |
| 可变对象做计数器 | `counters = {"transform_v1_calls": 0}` | 内部函数修改字典内容无需 `nonlocal` |
| `json.dumps(..., sort_keys=True, indent=2)` | `signature()`、`_demo` | 键排序得到规范化字符串；`indent` 美化输出 |
| `while` + `continue` | 主循环 | `continue` 跳过本轮剩余代码 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 demo，被测试导入时不执行 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，耗时不到 0.1 秒），输出（为便于阅读，把 JSON 数组压成一行）：

```text
{
  "status": "completed",
  "reason": "goal_met",
  "history": [[1,"fetch",false], [2,"transform",true], [2,"transform",false], [3,"render",false], [4,"submit",false]],
  "revisions": [{"revision": 1, "removed": [], "added": [], "revised": [2]}],
  "events": ["plan.commit", "step.start", "step.end", "step.start", "step.end",
             "plan.draft", "plan.diff", "plan.commit",
             "step.start", "step.end", "step.start", "step.end", "step.start", "step.end",
             "session.complete"],
  "transform_v1_calls": 1
}
```

逐项解读：

- **history 有 5 条**：fetch 成功；transform（带 `_force_fail`）失败，`error="ToolFailure: transform marker-forced failure"`；重规划后 transform（`mode=v2`）成功；render、submit 成功。失败的步骤也在 history 中，且同一个 id 2 出现两次（不同对象）。
- **revisions**：旧计划剩余 `[2,3,4]` 与新计划 `[2,3,4]` id 相同，只有步骤 2 的 args 变了 → `revised [2]`。
- **events 共 15 个**：首个 `plan.commit`（revision 0，4 步）；两对 start/end；一组 `plan.draft → plan.diff → plan.commit`（revision 1）；三对 start/end；`session.complete`。`plan.draft` 的 payload 中可以看到 `expected_outcome`，例如 `"computed via fallback"`。
- **transform_v1_calls = 1**：来自 `_force_fail` 分支，而不是 "v1 backend down" 分支。
- 步骤预算：共执行 5 步 < 12；重规划 1 次 < 5。

---

## 7. 动手改一改

1. 把 demo 的 `recovery` 改成 `"give_up"`，观察 diff 变成 `removed [2,3,4]、added [98,99]`，再思考为什么结果仍是 `goal_met`，给 `SessionResult` 增加一个能区分"放弃"的 reason。
2. 修复预算检查时序：在重规划前检查 `steps_taken >= max_steps`，并为"第 12 步失败"写一个测试，断言 planner 只被调用 1 次。
3. 用 `dataclasses.replace` 复制每个待执行的 Step，并写测试：planner 返回同一个 Step 对象时，history 中两条记录的 `error` 不同。
4. 增加 `on_failure: Literal["abort", "skip", "replan"]` 参数，实现讲义里的三种失败策略，各写一个测试。
5. 增加"无进展检测"：若新计划剩余部分与旧计划签名完全一致（diff 全空），直接返回 `failed / no_progress`。
6. 进阶：把 diff 换成基于 `difflib.SequenceMatcher` 的签名序列对齐；再实现讲义 "Going further" 中的 partial-plan caching：planner 读取 history，跳过已成功的步骤并复用其 `result`。

---

## 8. 常见坑

- **把失败步骤排除在步骤预算之外**：失败也是一次执行（消耗了工具调用和时间），本节代码正确地计入了预算。
- **重规划前不检查剩余预算**：会白白调用一次 LLM planner（本节代码就有这个问题）。
- **复用 Step 对象**：执行器原地修改 `result/error`，对象复用时历史记录会互相污染。
- **用 id 判断"是否同一步骤"**：LLM 经常重新编号，diff 会误导；需要稳定 key 或签名对齐。
- **args 里放不可 JSON 序列化的对象**：`signature()` 会在 diff 时抛 `TypeError`，且不在 `try` 内，直接崩溃。
- **把 `completed` 当成"目标达成"**：计划跑完不等于目标达成，`give_up` 计划同样返回 `goal_met`。
- **用错误串子串匹配决定恢复路径**：`"transform" in last_error` 很脆弱，换个错误措辞就失效；应使用结构化的错误码。
- **测试只断言字段存在**：`test_replan_diff_event_emitted` 只检查了 `removed/added` 键存在，没有断言其内容。

---

## 9. 测试在验证什么

运行方式：在 `code/` 目录下执行 `python3 -m pytest -q tests`（或 `python3 -m unittest discover -s tests -v`）。测试文件通过 `sys.path.insert(0, os.path.dirname(HERE))` 把 `code/` 加入导入路径，再 `from main import ...`。实际运行结果：**8 passed**（unittest：`Ran 8 tests ... OK`）。

| 测试 | 验证的性质 |
|------|-----------|
| `TestLinear.test_linear_plan_completes` | 不注入失败时 4 步全部执行，`completed / goal_met`，history id 为 `[1,2,3,4]`，没有修订 |
| `TestLinear.test_no_plan_initial` | planner 首次返回 `[]` → `failed / no_plan` |
| `TestReplan.test_replan_once_on_transform_failure` | 步骤 2（v1）失败一次后重规划，v1 与 v2 各调用 1 次，恰好 1 个修订，最终完成。这里的执行器不理会 `_force_fail`，是 `mode == "v1"` 分支导致失败 |
| `TestReplan.test_replan_diff_event_emitted` | 事件流中恰好有 1 个 `plan.diff`，`revision == 1`，含三个键，且 2 在 `revised` 中 |
| `TestReplan.test_replan_exhaustion_returns_failed` | planner 反复返回同一个坏步骤，`max_replans=2` → `failed / replan_budget`（实测 transform 共执行 3 次，history 长 4，两次 diff 全空） |
| `TestBudgets.test_step_budget_caps_execution` | 20 步计划、`max_steps=5` → `failed / step_budget`，history 恰好 5 条 |
| `TestBudgets.test_max_replans_zero_returns_after_first_failure` | `max_replans=0` 时第一次失败就返回 `replan_budget`，planner 不会被再次调用 |
| `TestEvents.test_event_order` | 首个事件是 `plan.commit`、末个是 `session.complete`，`step.start/step.end` 各 4 个 |

覆盖空白（可作为练习补充）：
- `give_up` 恢复路径（以及它返回 `goal_met` 的语义问题）；
- 重规划返回 `[]` 时的 `no_plan`；
- "失败恰好发生在步骤预算用尽时"的边界；
- diff 中 `removed / added` 的具体内容；
- Step 对象复用、args 不可序列化等异常输入。
