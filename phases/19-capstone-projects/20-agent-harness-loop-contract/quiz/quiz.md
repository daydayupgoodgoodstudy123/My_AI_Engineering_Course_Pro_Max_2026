# 测验 · Agent Harness 的循环契约（Agent Harness Loop Contract）

> **阶段 19 · 综合项目 · 第 20 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | "harness 即 agent" | 讲义："The harness is the agent. The model is a coprocessor." 循环、策略、预算、观测都属于 harness，模型只是被调用的一个部件 |
| 2 | 六个状态 | `IDLE`（唯一入口）、`PLANNING`、`EXECUTING`、`AWAITING_TOOL`、`REFLECTING`、`DONE`（唯一出口、终态） |
| 3 | 集中式转移表 | `_transition` 用一张 `legal` 字典检查每一次状态变化，非法转移抛 `RuntimeError`，不变量集中在一处 |
| 4 | 十个 hook topic | `before/after_plan`、`before/after_step`、`before/after_tool_call`、`on_error`、`on_pause`、`on_budget_exceeded`、`on_complete`；订阅者按注册顺序执行 |
| 5 | 两种 pull point | 需要工具结果时返回 `PullRequest(reason="tool_call")`；预算耗尽时暂停并返回 `budget_exceeded:*`。pull point 是**返回值**而不是异常，调用方用 `resume(payload)` 继续 |
| 6 | 十一种事件 | `session.start/pause/complete`、`plan.draft/commit`、`step.start/end`、`tool.call/result/error`、`budget.warn`；事件流只追加 |
| 7 | hooks ≠ events | hooks 是命令式的（可以修改、可以中止）；events 是观测式的（记录、上报），两者正交 |
| 8 | HookAbort | `before_tool_call` 中抛 `HookAbort` 会跳过该工具调用：记录 `step.error`、发 `tool.error`、触发 `on_error`，然后进入 `REFLECTING` 继续下一步 |
| 9 | 预算信封 | 三个上限：turns、tool calls、wall-clock 秒；达到上限时发 `budget.warn`、触发 `on_budget_exceeded`，转入 `IDLE` 并返回 pull point——"预算不是 kill switch，而是 yield" |
| 10 | 确定性 | 用固定 planner 代替模型，相同输入产生相同的事件类型序列，这是回放调试与测试的前提 |

### 核心技能（能动手做到）

- [ ] 画出六状态图，并对照代码里的 `legal` 表说出每条边在什么时候被走到（以及哪些边从未被走到）
- [ ] 手动推演一次带工具步骤的会话，写出完整的事件序列和 hook 触发顺序
- [ ] 给定 `Budget` 参数，推断 `run()`/`resume()` 在哪一步返回什么 `PullRequest`
- [ ] 写一个 `before_tool_call` 策略 hook（如拦截危险命令），并解释它对事件流和预算的影响
- [ ] 找出代码中绕过 `_transition`、`_history` 从不更新、非 `before_tool_call` 的 `HookAbort` 未被捕获等契约漏洞并修复
- [ ] 用 `unittest` 为状态机写"钉住转移与 hook 顺序"的测试

---

## 二、基础自测（选择题）

**Q1.** 讲义把 harness 循环建模为显式状态机，而不是"带若干标志位的 while 循环"，最主要的好处是：

- A. 所有状态变化都经过一个函数，可以在一处拒绝非法转移，并且行为可确定地重放
- B. 状态机运行速度更快
- C. 状态机可以并行执行多个工具调用
- D. 状态机不需要测试

**Q2.** 关于本节的 pull point，正确的是：

- A. 它是一个异常，调用方必须用 `try/except` 捕获
- B. 它会阻塞线程，直到工具在后台执行完毕
- C. 它是 `run()`/`resume()` 的返回值 `PullRequest`；调用方取回所需输入后调用 `resume(payload)`，循环从停下的地方继续
- D. 它只在会话结束时出现一次

**Q3.** 在 `before_tool_call` 中注册一个总是 `raise HookAbort("deny")` 的 hook，使用默认的三步计划（步骤 2、3 需要工具）运行 `run("g")`，结果是：

- A. `run()` 抛出 `HookAbort`，循环停在 `EXECUTING`
- B. 两个工具步骤都被跳过并记录 `hook_abort:deny`，`run()` 直接返回 `SessionResult(reason="goal_met")`，`budget.tool_calls` 仍为 0
- C. 返回 `PullRequest(reason="tool_call")`，等待调用方决定是否继续
- D. 循环转入 `PLANNING` 重新规划

**Q4.** 讲义强调 hooks 与 events 是两个正交的关注点，原因是：

- A. hooks 只能在 `DONE` 之后触发，events 只能在之前触发
- B. 两者是同一机制的两个名字
- C. events 可以中止当前 turn，hooks 只能记录
- D. hooks 是命令式的，可以修改 payload 或中止；events 是观测式、只追加的记录，供 UI 与 tracer 订阅

**Q5.** 默认演示中，一个需要工具的步骤（从开始到收到工具结果）触发 hook 的顺序是：

- A. `before_step` → `before_tool_call` → `after_tool_call` → `after_step`
- B. `before_tool_call` → `before_step` → `after_step` → `after_tool_call`
- C. `before_step` → `before_tool_call` → `after_step` → `after_tool_call`
- D. `before_step` → `after_step` → `before_tool_call` → `after_tool_call`

**Q6.** 使用"步骤 1 无工具、步骤 2/3 需要工具"的计划，`Budget(max_turns=10, max_tool_calls=2, max_wall_seconds=10)`。依次 `run("g")`、`resume({"result": 1})`、`resume({"result": 2})`，第三次调用返回：

- A. `PullRequest(reason="budget_exceeded:tool_calls")`——虽然已不再需要工具
- B. `SessionResult(reason="goal_met")`
- C. `PullRequest(reason="tool_call")`
- D. 抛出 `RuntimeError`

**Q7.** 讲义说"The budget is not a kill switch. It is a yield." 在本节代码里，预算耗尽后：

- A. 会话立即进入 `DONE`，不能继续
- B. 进程被强制退出
- C. 循环自动把所有上限翻倍后继续执行
- D. 发出 `budget.warn` 与 `session.pause`，状态转为 `IDLE`，返回 `PullRequest`；调用 `resume()` 会重置计数器并从暂停前的位置继续

**Q8.** 3 个无工具步骤的线性计划，`Budget(max_turns=2)`，`run("g")` 的返回值是：

- A. `SessionResult(reason="goal_met")`，三个步骤全部完成
- B. `PullRequest(reason="budget_exceeded:turns")`，此时已执行完 2 个步骤
- C. `PullRequest(reason="budget_exceeded:turns")`，此时 1 个步骤都没执行
- D. `PullRequest(reason="tool_call")`

---

## 三、动手 / 代码题

**Q9.** 讲义："`_transition` is the only function that changes state, so the state machine invariants live in one place." 阅读 `resume()` 的预算恢复分支：

```python
    def resume(self, payload: dict | None = None) -> PullRequest | SessionResult:
        if self.state == State.IDLE and self._reason.startswith("budget_exceeded"):
            self.budget.turns = 0
            self.budget.tool_calls = 0
            self.budget.started_at = time.time()
            self._reason = ""
            prev = self._prev_state
            self._prev_state = None
            if not self._plan:
                return self._begin_plan()
            if prev == State.EXECUTING:
                self.state = State.EXECUTING
            else:
                self.state = State.REFLECTING
            return self._step()
```

1. 这段代码违反了讲义的哪条不变量？`legal` 表里存在 `IDLE → EXECUTING` 这条边吗？
2. 预算暂停后状态是 `IDLE`，而 `run()` 只检查 `self.state != State.IDLE`。此时调用 `run("another")` 会发生什么？
3. 提出一个修复方案，让"全新会话"和"暂停中的会话"在状态机层面可区分。

**Q10.** 下面的 hook 注册在 `before_step` 上：

```python
loop = HarnessLoop(planner=linear_planner)
def block(p):
    raise HookAbort("deny")
loop.hooks.on("before_step", block)
loop.run("g")
```

1. `run()` 的结果是什么？之后 `loop.state` 是什么？还能 `resume()` 吗？
2. 讲义说订阅者可以"raise to abort the turn, or return a sentinel to skip the next step"。代码对"返回 sentinel"做了什么处理？
3. 给出一个统一处理 hook 异常的改造思路。

**Q11.** 讲义状态图里有 `REFLECTING --> PLANNING: replan`，默认 planner 也写了 `if history: return []`。

1. 实际运行中 planner 被调用了几次？传入的 `history` 长度是多少？为什么？
2. `REFLECTING → PLANNING` 这条边在代码里被走到过吗？
3. 修改代码实现"计划执行完后用历史重新规划，planner 返回空计划才结束"，写出关键改动。

**Q12.** 对 Q3 的场景（两个工具步骤都被 `HookAbort`），写出完整事件类型序列，指出其中"不对称"的地方，并说明它会给下游 tracer 带来什么问题、如何修复。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 agent harness？为什么说"harness 即 agent，模型只是协处理器"？一个最小 harness 至少要包含哪些部分？

**Q14.**（原理深挖）本节把 pull point 设计成"返回值 + `resume(payload)`"，讲义说它"is the same shape as a Python generator"。比较这种设计与"回调函数"和"抛异常"两种方案的优劣。

**Q15.**（工程实践）设计一个 agent 会话的预算系统：应该限制哪些维度？"达到上限"和"超过上限"该怎么界定？暂停后恢复时计数器应该怎么处理？

**Q16.**（场景设计）你要在 harness 上实现三件事：拦截 `rm -rf`、为每一步上报 OpenTelemetry span、在高风险操作前请人工审批。分别挂在哪个 hook topic 上？本节实现会遇到什么坑？

**Q17.**（追问型）讲义说"Given the same event log, the harness re-enters the same state"。要真正做到"不调用模型就能回放一次会话"，事件日志里至少要记录什么？本节代码离这个目标还差什么？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："`_transition` is the only function that changes state, so the state machine invariants live in one place"，并且"Given the same event log, the harness re-enters the same state. That property is what lets you replay sessions"。官方 `quiz.json` 的答案也是"reject illegal transitions in one place and replay sessions from the event log"。

- B：状态机与性能无关。
- C：本节循环一次只处理一个步骤，没有并行工具调用。
- D：恰恰相反，状态机让测试更容易"钉住"每个转移（`tests/test_loop.py` 就在做这件事）。

### Q2 — 答案：C

讲义："A pull point is not an exception. It is a return. The caller inspects the harness state, fetches whatever the harness asked for, and calls `resume(payload)`." 代码中 `_step` 遇到工具步骤时返回：

```python
            return PullRequest(
                reason="tool_call",
                state=self.state,
                payload={"tool": step.tool_name, "args": step.tool_args, "step_id": step.id},
            )
```

A 说反了；B 错，harness 自己不执行工具，也不阻塞；D 错，一次会话中可以出现多次 pull point（默认演示就有两次 `tool_call`）。

### Q3 — 答案：B

实际运行验证：两个工具步骤的 `error` 都是 `"hook_abort:deny"`，`run()` 直接返回 `SessionResult(reason="goal_met")`，`tool_calls == 0`（因为 `self.budget.tool_calls += 1` 在 hook 之后才执行）。事件序列中出现两次 `tool.error`，没有 `tool.call`。

- A 错：`before_tool_call` 是**唯一**用 `try/except HookAbort` 包住的 hook（其他 topic 才会这样，见 Q10）。
- C 错：hook 中止后不会产生 pull point，而是直接转入 `REFLECTING`。
- D 错：代码从不走 `REFLECTING → PLANNING`。

值得注意：被策略拦截的步骤仍然以 `goal_met` 结束，这个 reason 有误导性——调用方需要检查 `steps[i].error` 才知道有步骤失败。

### Q4 — 答案：D

讲义："Hooks are imperative (mutate, abort). Events are observational (record, ship). Treat them as orthogonal." A、C 把两者的性质说反或编造了时机；B 错，代码里是两套独立机制：`HookRegistry.fire` 和 `_emit`。

### Q5 — 答案：C

演示输出的 `hooks_fired` 里，步骤 2 对应的片段是：`before_step, before_tool_call, after_step, after_tool_call`。原因：工具步骤在 `_step` 中发出 pull point 之前就执行了 `step.end` 和 `after_step`（outcome 为 `"awaiting_tool"`），工具结果要等调用方 `resume()` 时才回来，那时才触发 `after_tool_call`。

这意味着：挂在 `after_step` 上的 tracer 会在工具真正执行**之前**就结束这一步的 span。A 是很多人直觉上的顺序，但不是本节代码的行为。

### Q6 — 答案：A

推演（已实际运行验证）：

1. `run`：步骤 1 完成 → 步骤 2 `tool_calls=1` → 返回 `tool_call`。
2. `resume(1)`：进入 `REFLECTING` → `_step` 先检查预算（1 < 2）→ 推进到步骤 3，`tool_calls=2` → 返回 `tool_call`。
3. `resume(2)`：进入 `REFLECTING` → `_step` **先检查预算**：`tool_calls >= max_tool_calls`（2 ≥ 2）→ 暂停，返回 `budget_exceeded:tool_calls`。

此时其实只差"推进游标、发现计划结束"这一步，并不需要再调用工具。原因是 `exceeded()` 用的是 `>=`（"达到"即触发），而检查发生在判断"是否完成"之前。再 `resume()` 一次就会得到 `goal_met`。B 是直觉答案；C、D 不符合实际运行。

### Q7 — 答案：D

`_check_budget` → `budget.warn` + `on_budget_exceeded` → `_pause` → `session.pause` + `on_pause` → `_transition(State.IDLE)` → 返回 `PullRequest`。`resume()` 的预算分支把 `turns`、`tool_calls` 清零、重置 `started_at`，再从 `_prev_state` 继续。A 是 kill switch 的行为；B、C 代码中不存在。注意：代码的"恢复"是**整套预算重新给一遍**，调用方无法通过 `resume()` 传入新的上限，也无法选择"关闭会话"。

### Q8 — 答案：B

`turns` 只在 `REFLECTING` 推进游标时 +1，预算检查在每次 `_step` 开头。推演：步骤 1 → `REFLECTING`（检查 0 < 2）→ `turns=1` → 步骤 2（检查 1 < 2）→ `REFLECTING`（检查 1 < 2）→ `turns=2` → `EXECUTING` 时检查 2 ≥ 2 → 暂停。实际运行：`max_turns=1/2/3` 分别在执行完 1、2 个步骤后暂停、以及正常完成（`goal_met`）。

### Q9 — 参考答案

1. `self.state = State.EXECUTING` / `State.REFLECTING` 是**直接赋值**，绕过了 `_transition`；而 `legal[State.IDLE]` 只有 `{State.PLANNING}`，`IDLE → EXECUTING`、`IDLE → REFLECTING` 在转移表里是非法的。讲义"`_transition` 是唯一改变状态的函数"的说法在代码中不成立。
2. 实测：`run("another")` 会被接受——它发出第二个 `session.start`，用新目标重新调用 planner，覆盖旧计划，游标归零；但预算计数器没有被重置（`turns` 仍是上限），于是立刻再次 `budget.warn` + `session.pause`。旧会话的进度被悄悄丢弃。
3. 修复思路（任选其一）：
   - 增加第七个状态 `PAUSED`：`_pause` 转入 `PAUSED`，`legal` 表中加入 `PAUSED → EXECUTING / REFLECTING / PLANNING` 与 `PAUSED → DONE`（调用方选择关闭）；`run()` 只接受 `IDLE`，`resume()` 只接受 `PAUSED` 或 `AWAITING_TOOL`。
   - 保留六状态，但把 `IDLE → EXECUTING`、`IDLE → REFLECTING` 加入 `legal`，`resume()` 中改为 `self._transition(...)`，并让 `run()` 在 `self._reason` 非空时拒绝。
   - 同时补测试：预算暂停后调用 `run()` 应抛 `RuntimeError`。

### Q10 — 参考答案

1. 实测：`HookAbort` 从 `run()` **直接抛出**；`loop.state` 停在 `EXECUTING`；再调用 `resume({})` 得到 `RuntimeError: resume() unsupported from state executing`。会话彻底卡死——这正是讲义"Going further"担心的情况（"a hook that raises ... two-thirds of the way through a forty-turn session"）。
2. `HookRegistry.fire` 会收集返回值列表，但所有调用点都**忽略**它；返回 `"SKIP"` 之类的 sentinel 没有任何效果（实测三个步骤照常执行）。"mutate the payload" 也只部分成立：payload 是每次新建的字典，改字典本身无效；但 payload 中的 `Step` 对象是共享引用，改 `p["step"].tool_args` 会生效（实测 `PullRequest.payload["args"]` 变成了 `{"safe": True}`）。
3. 改造思路：
   - 写一个 `_fire_guarded(topic, payload)`：捕获 `HookAbort` → 发 `tool.error` 或新增 `step.error` 类事件、触发 `on_error`、根据 topic 决定"跳过本步"还是"暂停会话"；捕获其他 `Exception` → 视为 hook 自身故障，记录并按配置选择"隔离该 hook 继续"或"暂停等待人工"。
   - 明确返回值约定，例如 `SKIP = object()`：`before_step` 返回 `SKIP` 时把该步标记为跳过并转入 `REFLECTING`。
   - `on_error` 内部再抛异常时不能递归调用自己。

### Q11 — 参考答案

1. 实测 planner 只被调用 **1 次**，`history` 长度为 0。`self._history` 在 `__init__` 里初始化为空列表后**从未被追加**；`_begin_plan` 也只在会话开始（以及预算恢复且计划为空时）调用。
2. 没有。`_step` 在 `REFLECTING` 时只有两条出路：游标越界 → `_complete("goal_met")`（`REFLECTING → DONE`），否则 → `EXECUTING`。`REFLECTING → PLANNING` 只存在于 `legal` 表里。
3. 关键改动：

```python
        if self.state == State.REFLECTING:
            done = self._plan[self._cursor]
            self._history.append(done)          # 1. 记录已完成的步骤
            self._cursor += 1
            self.budget.turns += 1
            if self._cursor >= len(self._plan):
                return self._begin_plan()       # 2. 计划走完 -> 回到 PLANNING 重新规划
            self._transition(State.EXECUTING)
            return self._step()
```

   同时修改 `_begin_plan` 的空计划分支，区分"一开始就无计划"和"做完了"：

```python
        if not draft:
            return self._complete("goal_met" if self._history else "no_plan")
```

   `_begin_plan` 里 `self._transition(State.PLANNING)` 从 `REFLECTING` 出发是合法的。已在副本上实测：只做第一处改动时，演示的 `assert final.reason == "goal_met"` 和 `test_idle_to_done_linear` 会因 reason 变成 `no_plan` 而失败；两处都改后 18 个测试全部通过，事件流在结尾多出一组 `plan.draft, plan.commit`，hook 序列多出一组 `before_plan, after_plan`。

### Q12 — 参考答案

实测事件序列：

```text
session.start, plan.draft, plan.commit,
step.start, step.end,            # 步骤 1（无工具）
step.start, tool.error,          # 步骤 2 被拦截
step.start, tool.error,          # 步骤 3 被拦截
session.complete
```

- **不对称**：步骤 2、3 只有 `step.start` 没有 `step.end`，`after_step` 也没有触发；同时没有 `tool.call` 却有 `tool.error`。
- **影响**：按 `step.start` 开 span、`step.end` 关 span 的 tracer 会留下两个永不关闭的 span；按 `tool.call` / `tool.result|error` 配对统计工具成功率的仪表盘会出现"孤儿错误"。
- **修复**：在 `HookAbort` 分支补发 `step.end`（outcome 为 `"aborted"`）并触发 `after_step`；或者约定 `tool.error` 的 payload 带上 `"phase": "pre_call"`，让消费方能区分"策略拒绝"和"工具执行失败"。再加一条测试：每个 `step.start` 都必须有对应的 `step.end`。

### Q13 — 参考回答要点

- **定义**：harness 是包在模型外面的运行时——维护循环与状态、调用工具、施加策略与预算、记录观测，并决定何时把控制权交还给人或调用方。
- **"harness 即 agent"**：模型只负责"给定上下文，产出下一步意图"；同一个模型放在不同 harness 里，安全性、可靠性、成本差异巨大。讲义："Once you write the contract down, swapping models, tools, or policies stops being a refactor. It becomes a registration call."
- **最小组成**（对应本节）：显式状态机与转移检查；hook 扩展点；pull point（工具调用、暂停）；类型化事件流；预算信封。后续各节再加入工具注册表（第 21 节）、传输层（第 22 节）、分派器（第 23 节）、规划器（第 24 节）。
- 加分点：讲义提到 Claude Code、Cursor、OpenCode 到 2025 年中都收敛到类似的 hook 形状；能举出"`before_tool_call` 拦截危险命令"这类真实用法。

### Q14 — 参考回答要点

- **返回值 + resume（本节）**：控制权回到调用方，调用方可以自由选择传输（讲义："In a TUI it is keypress. Over MCP it is `tools/call`. Over a queue it is a job poll"），可以序列化状态、跨进程恢复；缺点是调用方要写"循环驱动"代码，harness 要自己保存游标等上下文。
- **回调**：harness 内部直接调用 `tool_executor(...)`，写起来简单；但 harness 必须同步等待、难以做人工审批或跨进程排队，回调里的异常会穿透循环。
- **抛异常**：语义上把"正常的等待"当作错误；`try/except` 会在调用栈中丢失局部状态，难以恢复；讲义明确否定："A pull point is not an exception."
- **与生成器的类比**：生成器 `yield` 交出一个值、`send()` 传回结果，正是 `PullRequest` / `resume(payload)` 的形状；本节用对象字段（`_cursor`、`_plan`、`state`）显式保存了生成器帧里本来隐式保存的状态，好处是可以持久化。
- 常见误区：认为 harness 应该自己执行工具——这会把沙箱、权限、重试都耦合进循环。

### Q15 — 参考回答要点

- **维度**：turns（步数）、tool calls（工具调用次数）、wall-clock（墙钟时间）——本节三项；生产中还应有 token / 费用上限、每种工具的单独配额、连续失败次数上限。
- **"达到"还是"超过"**：本节用 `>=`，并在每次 `_step` 开头检查，结果是"用完最后一次额度后、即使只差收尾也会暂停"（Q6）。更合理的是在**消耗之前**检查："要再调用一次工具时，如果 `tool_calls + 1 > max` 才暂停"；纯收尾步骤不消耗预算。
- **检查时机**：讲义说 wall-clock "checked on every state transition"，代码只在 `_step` 开头检查；`AWAITING_TOOL` 期间（工具可能跑很久）完全不检查，需要由调用方或超时机制兜底。
- **恢复语义**：本节恢复时全部清零，相当于无限续杯；更好的设计是 `resume(extend={"tool_calls": 5})` 显式追加额度，并保留累计总量用于审计和计费；上限为 0 时（如 `max_wall_seconds=0`）清零也无济于事，会无限暂停（实测）。
- **不泄漏部分状态**：暂停时状态要停在一个可恢复的边界上（步骤之间），不能在工具调用一半时暂停。
- 加分点：把预算事件接入告警；区分"软上限（warn）"和"硬上限（pause）"。

### Q16 — 参考回答要点

- **拦截 `rm -rf`**：`before_tool_call`（讲义原例），检查 `p["step"].tool_name` 与 `tool_args`，命中则 `raise HookAbort("policy_denied")`。坑：被拦截的步骤缺少 `step.end`（Q12）；会话最终仍报 `goal_met`。
- **OpenTelemetry span**：讲义建议放在 `after_step`。坑：工具步骤的 `after_step` 在工具执行**之前**就触发（Q5），span 时长不包含工具耗时；应在 `before_step` 开 span、在 `after_tool_call`（工具步骤）或 `after_step`（非工具步骤）关 span，或者直接订阅事件流而不用 hook。
- **人工审批**：讲义说"a hook that resumes on a paused session lives in `on_pause`"，并且暂停可以由"a hook explicitly requests human review"触发。坑：本节代码**没有**让 hook 请求暂停的机制，只有预算能触发 `_pause`；需要新增例如 `raise PauseRequested(reason)` 的约定，在 `before_tool_call` 中捕获并调用 `_pause`。
- **通用坑**：除 `before_tool_call` 外，任何 hook 抛异常都会让会话卡死（Q10）；多个订阅者时前一个抛异常，后面的不会执行；hook 拿到的 `Step` 是共享引用，"观测型" hook 也可能无意中改坏状态。

### Q17 — 参考回答要点

- **需要记录**：每个非确定性输入——planner/模型的完整输出（不只是步骤描述）、每次工具结果或错误的完整 payload、调用方每次 `resume` 传入的内容、预算配置与触发、hook 的决策（哪个 hook 中止了什么）、时间戳（用于 wall-clock 判断）。回放时用这些记录替换真实调用。
- **本节差距**：
  - `plan.draft` 只记录了步骤描述，没有 `requires_tool`、`tool_name`、`tool_args`，无法据此重建 `Step`；
  - 没有任何"从事件日志恢复状态"的函数，讲义"subscribers can replay from any offset"也没有订阅 API，`events` 只是列表副本；
  - wall-clock 依赖 `time.time()`，回放时无法复现预算判断，需要注入可替换的时钟；
  - `test_same_inputs_same_event_types` 只比较两次新运行的事件类型（实测去掉 `ts` 后 payload 也一致），证明的是"确定性执行"，而不是"可回放"。
- 加分点：回放与 durable execution（持久执行，如 LangGraph checkpoint）的关系——把状态快照与事件日志结合，可以从任意检查点恢复。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：讲义列出的先修，循环的基本形状。
- [阶段 13 · 01 工具接口：为什么 Agents 需要结构化输入输出](../../../13-tools-and-protocols/01-the-tool-interface/docs/zh.md)：工具步骤的输入输出契约。
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../../13-tools-and-protocols/06-mcp-fundamentals/docs/zh.md)：讲义提到 pull point 在 MCP 上对应 `tools/call`。
- [阶段 11 · 16 Agent State Machines——图、节点与 Checkpoints](../../../11-llm-engineering/16-langgraph-state-machines/docs/zh.md)：用图和状态机组织 agent。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：暂停、恢复与回放。

### 本节被哪些后续内容用到
- [阶段 19 · 21 带 Schema 校验的工具注册表](../../21-tool-registry-schema-validation/docs/zh.md)：为循环接上真实工具。
- [阶段 19 · 22 通过换行分隔的 stdio 传输 JSON-RPC 2.0](../../22-jsonrpc-stdio-transport/docs/zh.md)：pull point 的一种传输。
- [阶段 19 · 23 函数调用分派器](../../23-function-call-dispatcher/docs/zh.md)：把 `tool_call` pull point 变成真正的执行。
- [阶段 19 · 24 计划—执行控制流程](../../24-plan-execute-control-flow/docs/zh.md)：替换本节的固定 planner。
- [阶段 19 · 28 通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability](../../28-observability-otel-traces/docs/zh.md)：消费本节的事件流。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：预算信封的深入设计。

### 延伸关键词
`agent harness` · `finite state machine` · `transition table` · `lifecycle hooks` · `pull point / yield` · `generator send()` · `event sourcing` · `deterministic replay` · `budget envelope` · `durable execution` · `HookAbort` · `OpenTelemetry span`
