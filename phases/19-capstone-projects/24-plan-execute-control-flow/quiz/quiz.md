# 测验 · 计划—执行控制流程（Plan-Execute Control Flow）

> **阶段 19 · 综合项目 · 第 24 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Plan-and-execute vs chain-of-thought | 先产出一份**结构化计划**（数据），再由 harness 逐步确定性地执行；计划可被检查、记录、比较，而不是让循环去"猜"工具调用在哪里结束 |
| 2 | 失败的三种处理 | Abort（直接失败）、Skip（标记失败继续）、Replan（把错误交回 planner，从游标处重新规划）。讲义："Replan 才把脚本变成 agent" |
| 3 | `Step` 的形状 | `id / tool_name / args / expected_outcome / result / error`；`expected_outcome` 不被执行器校验，只给重规划器和 tracer 读 |
| 4 | Planner 契约 | `planner(goal, history, last_error) -> list[Step]`：首次 `last_error=None`；之后传入最近一次失败信息；planner 不知道重试、超时和执行器 |
| 5 | 执行器状态机 | EXEC → 成功则游标 +1；失败则进入 REPLAN；计划跑完 → DONE；预算耗尽 → FAILED |
| 6 | Plan diff | 每次修订发 `plan.diff`：`removed`（旧有新无的 id）、`added`（新有旧无的 id）、`revised`（同 id 但 `(tool_name, args)` 变了）；让"改计划"成为可见事件 |
| 7 | 两个硬预算 | `max_steps`（默认 12）限制整个会话的步骤执行总数（含失败的步）；`max_replans`（默认 5）限制首个计划之后调用 planner 的次数 |
| 8 | 结果形状 | `SessionResult(status, reason, history, revisions, events)`；reason ∈ `goal_met / step_budget / replan_budget / no_plan` |
| 9 | 事件流 | `plan.commit / step.start / step.end / plan.draft / plan.diff / session.complete`，供 tracer 或 UI 渲染时间线 |
| 10 | 与前后课的关系 | 第 20 课 harness 循环读取 `SessionResult`；第 23 课 dispatcher 执行每一步；第 21 课 registry 校验参数；第 22 课 transport 把流程暴露给模型客户端 |

### 核心技能（能动手做到）

- [ ] 手动追踪任意"计划 + 执行器"组合下的事件序列、`history` 长度与最终 `reason`
- [ ] 计算一次修订的 `PlanDiff`（`removed / added / revised`），并说出"按 id 比较"在什么情况下会误导
- [ ] 说清 `max_steps` 与 `max_replans` 各自拦截哪一类失控，并找出本节代码里两个预算检查的时序漏洞
- [ ] 写一个读取 `history` 的 planner，实现"跳过已成功步骤"（partial-plan caching）或"跳过失败步骤"（Skip 策略）
- [ ] 识别"复用 Step 对象"导致 `error` 字段残留、`history` 别名的问题，并用 `dataclasses.replace` 修复
- [ ] 区分"可重规划失败"与"致命失败"，说出生产中如何对异常分类

---

## 二、基础自测（选择题）

**Q1.** 运行本节 `main.py` 的 demo（`fail_step_id=2`、`recovery="route_around"`），输出的唯一一条 revision 是：

- A. `{"revision": 1, "removed": [], "added": [], "revised": [2]}`
- B. `{"revision": 1, "removed": [1], "added": [], "revised": [2]}`
- C. `{"revision": 1, "removed": [2, 3, 4], "added": [2, 3, 4], "revised": []}`
- D. `{"revision": 1, "removed": [], "added": [2], "revised": []}`

**Q2.** 测试 `test_replan_exhaustion_returns_failed` 中，初始计划是 `[fetch, transform]`，此后 planner 每次都返回 `[transform(v1)]`，执行器对 `transform` 总是抛异常，`max_replans=2`。整个会话里 `transform` 一共被执行了几次？

- A. 2 次
- B. 4 次
- C. 6 次
- D. 3 次

**Q3.** `max_steps=12`，planner 返回一个恰好 12 步的计划，所有步骤都成功。结果是：

- A. `failed / step_budget`，因为第 12 步执行后 `steps_taken == max_steps`
- B. `completed / goal_met`，12 步全部执行
- C. `failed / step_budget`，只执行了 11 步
- D. `completed / goal_met`，但 `history` 只有 11 条

**Q4.** 用 `make_deterministic_planner(None, recovery="give_up")`，执行器让 `transform(v1)` 失败。planner 返回 `[log_failure, notify_user]` 两步且都成功。最终 `SessionResult` 是：

- A. `failed / replan_budget`
- B. `failed / no_plan`
- C. `completed / goal_met`
- D. `failed / give_up`

**Q5.** 关于 `Step.expected_outcome`，下列说法正确的是：

- A. 执行器从不校验它；它出现在 `plan.commit / plan.draft` 事件的步骤摘要里，供重规划器和 tracer 阅读
- B. 执行器会把工具返回值与它做字符串比较，不一致则视为失败
- C. 它参与 `Step.signature()`，所以改了它会出现在 `revised` 中
- D. 它是 dispatcher 的缓存键

**Q6.** 第一次计划执行到某步失败后，planner 在重规划时返回了空列表 `[]`。此时：

- A. 执行器继续执行旧计划剩余的步骤
- B. 返回 `failed / replan_budget`
- C. 发出 `plan.diff`（所有旧步骤都在 `removed` 中）后返回 `completed`
- D. 发出 `plan.draft` 后直接返回 `failed / no_plan`，不发 `plan.diff`

**Q7.** 讲义把失败分为"可重规划"和"致命"两类。在本节代码里，哪些情况会被当作**可重规划失败**送回 planner？

- A. 只有 `ToolFailure` 异常
- B. 只有 `step.error` 中包含 `"transform"` 的异常
- C. 执行器抛出的任何 `Exception` 子类（包括代码 bug 引起的 `TypeError`、`KeyError`），只要两个预算都没耗尽
- D. 所有异常都致命，只有返回值为 `None` 才会重规划

**Q8.** 为什么在 `max_steps` 之外还要单独设 `max_replans`？

- A. 因为 `max_steps` 不统计失败的步骤
- B. planner 若反复返回同一个坏计划，单靠 `max_steps` 要等很久才会拦住；`max_replans` 让失败更快、原因更清楚
- C. 因为 `max_replans` 会限制计划的长度
- D. 因为没有 `max_replans` 时执行器会并行运行多个计划

---

## 三、动手 / 代码题

**Q9.** 阅读 `run()` 中失败分支之后的代码：

```python
            except Exception as exc:
                step.error = f"{type(exc).__name__}: {exc}"
                ...
                steps_taken += 1
                last_error = step.error

            if replans_used >= self.max_replans:
                ...return SessionResult(status="failed", reason="replan_budget", ...)

            replans_used += 1
            revision += 1
            new_plan = self._planner(goal, history, last_error)
            ...
            plan = new_plan
            cursor = 0
```

`step_budget` 的检查只在 `while` 循环顶部。现在 `max_steps=12`，初始计划有 12 步，第 12 步失败，重规划返回 1 步。

1. 最终 `reason` 是什么？planner 一共被调用了几次？最后 3 个事件是什么？
2. 讲义说"The executor will refuse the replan and return FAILED"，代码真的"拒绝了重规划"吗？在真实系统里这会造成什么浪费？
3. 给出修复方式。

**Q10.** 某同学写了一个"缓存计划"的 planner：

```python
PLAN = [Step(1, "flaky", {}, "x")]
planner = lambda g, h, e: PLAN       # 每次都返回同一个列表、同一个 Step 对象
```

执行器第一次调用 `flaky` 抛 `ToolFailure("first fail")`，第二次返回 `"ok"`。会话最终 `completed / goal_met`。

1. 此时 `res.history` 中两条记录的 `(result, error)` 分别是什么？为什么？
2. 这暴露了执行器的什么设计缺陷？给出一行修复。

**Q11.** 讲义提到三种失败处理（Abort / Skip / Replan），代码只实现了 Replan。请**不修改执行器**，只写一个 planner，实现"失败步骤直接跳过、已经成功的步骤不重跑"的效果：完整计划是 `[1 fetch, 2 transform, 3 render, 4 submit]`，`transform` 总是失败。写出 planner，并给出最终的 `history` 和 `revisions`。

**Q12.** 某 planner 在重规划时**重新编号**了步骤：

```python
# 旧计划剩余部分（plan[cursor:]）
[Step(2, "b", {}, ""), Step(3, "c", {}, "")]
# 新计划
[Step(1, "b2", {}, ""), Step(2, "c", {}, "")]
```

1. `_diff_plans` 会给出什么结果？它和"真实发生的变化"有什么出入？
2. 提出一种不依赖 id 稳定性的 diff 方法，并给出它在这个例子上的输出。

---

## 四、面试高频题

**Q13.**（基础必考）Plan-and-execute 和 ReAct / chain-of-thought 式 agent 循环有什么区别？各自适合什么任务？

**Q14.**（原理深挖）一个 agent 执行器应该有哪些"预算"？本节的 `max_steps` 和 `max_replans` 各防什么？还应该加什么？

**Q15.**（工程实践）把这个执行器接到真实 LLM planner 和真实工具上，你认为最先要补的三件事是什么？（提示：错误分类、副作用与幂等、partial-plan caching）

**Q16.**（场景设计）产品经理要求在 UI 上展示"agent 为什么改计划"。你如何设计事件流和 plan diff 的数据结构，并对接到可观测性系统？

**Q17.**（追问型）如果 LLM planner 连续返回同一个坏计划，本节代码会怎样？除了 `max_replans`，你还能怎么更早发现并处理？

---

## 五、参考答案与解析

### Q1 — 答案：A

demo 中 `fail_step_id=2` 给步骤 2 的 args 加了 `_force_fail: True`，执行器遇到这个标记抛 `ToolFailure("transform marker-forced failure")`，错误串为 `"ToolFailure: transform marker-forced failure"`，含 `"transform"`，于是走 route_around，返回 `[2 transform(v2), 3 render, 4 submit]`。

diff 比较的是 `plan[cursor:]`（旧计划**剩余**部分，`cursor=1`，即步骤 2、3、4）与新计划：id 集合都是 `{2,3,4}`，所以 `removed`、`added` 为空；步骤 2 的 args 从 `{"mode":"v1","_force_fail":true}` 变成 `{"mode":"v2"}`，签名变化，进入 `revised`。实际运行输出正是 A。

- B 错：已经执行过的步骤 1 不在 `plan[cursor:]` 里，不会被算作 removed。
- C 错：diff 按 id 而不是按对象身份比较。
- D 错：id 2 在新旧计划中都有，不是 added。

### Q2 — 答案：D

已用脚本实际追踪：fetch 成功（steps=1）→ transform 失败（steps=2，replans 0<2，重规划 #1）→ transform 失败（steps=3，重规划 #2）→ transform 失败（steps=4，`replans_used=2 >= 2`，返回 `replan_budget`）。transform 执行 **3 次 = max_replans + 1**，`history` 长度为 4。两次 revision 的 diff 都是空的（`removed/added/revised` 全为 `[]`），因为 planner 返回了同样的步骤。

A 漏了最后一次；B 是 `history` 的总长度；C 是把每次重规划都算成"重跑整个初始计划"。

### Q3 — 答案：B

`steps_taken >= max_steps` 只在**执行下一步之前**检查。第 12 步成功后 `cursor == len(plan)`，`while` 条件不成立直接退出，返回 `completed / goal_met`，`history` 12 条。实际运行验证。所以 `max_steps=12` 的含义是"最多允许执行 12 步"，而不是"第 12 步就算超"。A、C、D 都把边界算错了。

### Q4 — 答案：C

实际运行：`completed goal_met`，history 为 `[(1,fetch,ok),(2,transform,err),(98,log_failure,ok),(99,notify_user,ok)]`，diff 为 `removed [2,3,4]`、`added [98,99]`。执行器只判断"当前计划是否跑完"，不判断用户的原始目标是否实现，所以"体面放弃"也被报告成 `goal_met`。这是本节代码的一个语义缺陷：调用方若只看 `status` 会误以为报告已经提交。合理做法是让 planner 能在步骤上标记"终止性/降级"，或增加 `reason="gave_up"` 之类的结果。

D 中的 `give_up` 不是代码里存在的 reason；A、B 不符合实际执行路径。

### Q5 — 答案：A

讲义："`expected_outcome` ... It is not enforced by the executor." 代码中它只出现在 `_summarize()` 里，进入 `plan.commit` 和 `plan.draft` 事件的 `"outcome"` 字段。

- B 错：执行器只看是否抛异常。
- C 错：`signature()` 只有 `(tool_name, json.dumps(args, sort_keys=True))`，修改 `expected_outcome` 不会让步骤出现在 `revised`。
- D 错：本节没有缓存。

### Q6 — 答案：D

代码顺序：先 `self._emit("plan.draft", ...)`（steps 为空列表），再 `if not new_plan:` 发 `session.complete {"reason": "no_plan"}` 并返回 `failed / no_plan`。用 `recovery="other"` 实际运行，事件序列为 `plan.commit, step.start, step.end, step.start, step.end, plan.draft, session.complete`，没有 `plan.diff`。讲义的确定性 planner 规则也写明 "otherwise → return [] (signals nothing to replan)"。注意这次空的重规划也消耗了一次 `replans_used`。

### Q7 — 答案：C

代码是 `except Exception as exc:`，不区分异常类型。执行器自身代码里的 bug（如参数缺失引起的 `KeyError`）也会被当成"工具失败"交给 planner，可能让 LLM 白白重规划好几轮。讲义状态机里描述了 "failure-fatal"，但在代码中致命失败只有"预算耗尽"和"no_plan"两种。`ToolFailure` 只是演示用的异常类（A 太窄）；B 是确定性 planner 选择 route_around 的条件，不是执行器的判断；D 与代码不符。

### Q8 — 答案：B

讲义："A planner that returns the same broken plan five times in a row would otherwise loop until the step budget catches it. Capping replans makes the failure faster and the reason clearer." 两个预算度量的单位不同：步骤预算限制总执行量（防止计划不断变长），重规划预算限制 planner 调用次数（防止原地打转）。

- A 错：失败的步骤同样 `steps_taken += 1`。
- C 错：计划长度没有限制。
- D 错：执行器严格串行。

### Q9 — 参考答案

1. 实际运行：`reason = step_budget`，planner 被调用 **2 次**（初始 + 1 次重规划），最后事件是 `... step.end, plan.draft, plan.diff, plan.commit, session.complete`。第 12 步失败后 `steps_taken = 12`，但失败分支不检查步骤预算，照常重规划、发 diff、提交新计划；回到循环顶部才发现 `12 >= 12`，返回 `step_budget`，新计划一步都没执行。
2. 没有"拒绝"。对真实系统而言，这次 planner 调用就是一次 LLM 请求（token、延迟、费用），产生的计划注定不会执行；事件流里还多出一个"已提交但没执行"的修订，tracer 上会显得很奇怪。
3. 在失败分支里、重规划**之前**先检查步骤预算（已验证修改后 planner 只调用 1 次，原有 8 个测试仍全部通过）：

```python
            if steps_taken >= self.max_steps:
                self._emit("session.complete", {"reason": "step_budget"})
                return SessionResult(status="failed", reason="step_budget",
                                     history=history, revisions=revisions,
                                     events=list(self._events))
            if replans_used >= self.max_replans:
                ...
```

更进一步，可以把"剩余步骤预算"作为参数传给 planner，让它生成不超过预算的计划。

### Q10 — 参考答案

1. 实际运行结果：两条记录是**同一个对象**，都显示 `('ok', 'ToolFailure: first fail')`。原因：执行器直接修改 `plan[cursor]` 这个 Step 对象，失败时写入 `step.error`，`history.append(step)`；重规划返回的仍是同一个对象，成功时只写 `step.result`，**从不清空 `error`**，然后再次 `append` 同一个对象。于是历史里"失败的那次"也显示 `result='ok'`，"成功的那次"也带着错误信息。
2. 缺陷：执行器把 planner 返回的对象当作可变的执行记录，既不复制、也不重置字段；`history` 与计划共享对象（别名）。讲义说 planner 是"纯函数"，但执行器并没有保护这个假设。修复（已验证）：

```python
            step = dataclasses.replace(plan[cursor], result=None, error=None)
```

每次执行都复制一个新 Step，`history` 中每条记录独立；修改后输出为 `[(None, 'ToolFailure: first'), ('ok', None)]`，planner 的 `PLAN` 列表也不再被污染。

### Q11 — 参考答案

```python
FULL = lambda: [Step(1, "fetch", {}, ""), Step(2, "transform", {"mode": "v1"}, ""),
                Step(3, "render", {}, ""), Step(4, "submit", {}, "")]

def planner_skip(goal, history, last_error):
    if last_error is None:
        return FULL()
    tried = {s.id for s in history}                 # 成功的和失败的都不再执行
    return [s for s in FULL() if s.id not in tried]
```

实际运行：`completed goal_met`，history 为 `[(1,ok),(2,err),(3,ok),(4,ok)]`，revisions 为 `[{"revision":1,"removed":[2],"added":[],"revised":[]}]`。

要点：
- planner 通过 `history` 获知哪些步骤已经执行，这正是讲义 "Going further" 里说的 partial-plan caching："The executor already keeps history; the planner just needs to read it."
- 每次调用都新建 Step 对象（`FULL()` 是函数），避免 Q10 的对象复用问题。
- Skip 仍然会消耗一次 `replans_used`；若要严格区分 Skip 与 Replan，应在执行器里加 `on_failure="abort"|"skip"|"replan"` 策略参数。
- 同样注意 Q4 的语义问题：跳过了失败步骤后结果仍是 `goal_met`。

### Q12 — 参考答案

1. 实际输出 `{'removed': [3], 'added': [1], 'revised': [2]}`。真实变化是"`b` 换成了 `b2`，`c` 保持不变"，但按 id 比较会说：步骤 3（`c`）被删除、步骤 1 被新增、步骤 2 被修改——三条信息都在误导。`_diff_plans` 隐含假设"同一个 id 在各次修订中指同一个逻辑步骤"，而 LLM planner 很容易重新编号。
2. 方法：按步骤**签名序列**做序列对齐（最长公共子序列），例如 `difflib.SequenceMatcher(a=[s.signature() for s in old], b=[...new])`，然后遍历 `get_opcodes()`。在本例上实际输出 `[('replace', ['b'], ['b2']), ('equal', ['c'], ['c'])]`，准确反映变化。也可以要求 planner 输出稳定的步骤 key（如 UUID 或语义名），并在 registry 层校验"重规划不得复用 id 表示不同步骤"。

### Q13 — 参考回答要点

- **ReAct / CoT 循环**：每一轮模型"想一步、调一次工具、看结果"，计划隐含在 token 流中，没有显式的全局计划；灵活，适合探索性、信息不完整的任务，但难以审计、容易绕圈。
- **Plan-and-execute**：先生成完整的结构化计划（讲义："The plan is data the harness can introspect"），再由执行器确定性地逐步执行；失败时把错误交回 planner 重规划。
- **优点**：计划可检查、可审批、可 diff；执行阶段不需要每步都调用大模型（省 token，可参考阶段 14 的 ReWOO）；预算与进度易于度量。
- **缺点**：对中途发现的新信息反应慢，依赖重规划；计划质量取决于 planner 一次性的推理。
- **适用**：步骤相对确定的流程型任务（数据管道、报告生成、部署）；探索型任务更适合 ReAct 或混合式。
- 加分点：说出本节执行器是一个显式状态机（EXEC / NEXT / REPLAN / DONE / FAILED），状态与事件一一对应，便于测试每条转移路径。

### Q14 — 参考回答要点

- `max_steps`：防"计划失控增长"——总执行次数（含失败步、含重规划后的步）封顶。
- `max_replans`：防"原地打转"——planner 反复给出相同的坏计划。
- 本节实现细节：两个检查的时机不同（步骤预算在执行前检查、重规划预算在失败后检查），存在 Q9 的"预算已尽仍调用 planner"问题。
- 还应加：**token / 费用预算**（每次 LLM 调用累计）、**墙钟时间预算**（deadline）、**单步超时**、**单工具重试次数**、**有副作用操作的次数限制**（如最多发一次邮件）；下一课（第 25 课）的观察预算则限制塞回模型上下文的观察大小。
- 预算耗尽时要返回**可区分的 reason**，让上层能决定是报警、升级给人还是放宽预算重跑。
- 常见误区：只设一个全局循环上限，失败时无法区分"计划太长"还是"planner 卡住"。

### Q15 — 参考回答要点

1. **错误分类**：区分可重试的瞬时错误（超时、429，用退避重试而不是重规划）、可重规划的语义错误（参数错误、资源不存在）、致命错误（权限拒绝、执行器 bug、安全策略拦截，直接终止）。本节 `except Exception` 一网打尽（Q7）。
2. **副作用与幂等**：重规划后可能重跑 `submit` 这类有副作用的步骤；需要幂等键、"已提交"标记，或在 planner 输入中显式标出已产生的副作用。
3. **Partial-plan caching**：planner 读 `history` 跳过已成功步骤并复用其 `result`（Q11）；执行器应保证 `history` 记录独立、不可变（Q10）。
4. 其他：用 registry（第 21 课）在执行前校验每步 args；给 planner 的 `last_error` 做截断与脱敏；把 `revised` 等事件接入 tracing；结果语义上区分 `goal_met` 与 `gave_up`（Q4）。

### Q16 — 参考回答要点

- **事件**：沿用 `plan.commit / plan.draft / plan.diff / step.start / step.end / session.complete`，每个事件带 `session_id`、`revision`、`step_id`、时间戳。
- **diff 结构**：`removed / added / revised` 之外，`revised` 最好带上前后签名（old args → new args）以及触发修订的 `last_error`；UI 对 removed 画删除线、added 高亮（讲义："revision is a visible event, not a silent rewrite"）。
- **稳定标识**：要求 planner 使用稳定步骤 key，或用签名序列对齐（Q12），否则 diff 会误导。
- **对接可观测性**：一次会话一个 trace，每个步骤一个 span，修订作为 span event 或独立 span，属性中记录 `expected_outcome`；参见第 28 课 OTel GenAI spans。
- **隐私**：args 和错误信息里可能有敏感数据，进入事件前要脱敏。
- 加分点：把 `expected_outcome` 和实际 `result` 并排展示，方便人工判断"这一步是否真的做成了"。

### Q17 — 参考回答要点

- **本节代码的行为**：每次失败都会重规划，直到 `replans_used >= max_replans` 返回 `replan_budget`；在 Q2 的例子中每次 diff 都是**全空**的——这本身就是"planner 没有吸取教训"的信号，但代码没有利用它。
- **更早发现**：
  - 若新计划剩余部分与旧计划签名完全相同（空 diff），立即判定"无进展"并终止或升级；
  - 维护"失败签名集合"，planner 再次提出已失败过的 `(tool, args)` 时拒绝该计划；
  - 把完整的失败历史（不只是 `last_error`）放进 planner 的上下文，并明确提示"以下方案已失败"。
- **处理**：换更强的模型重规划、提高 temperature 获得不同方案、或交给人工（human-in-the-loop）。
- 常见误区：只依赖 `max_steps` 兜底——成本高、失败原因也不清晰。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：agent 循环的基本形态，本节执行器是它的结构化版本。
- [阶段 14 · 02 ReWOO 与 Plan-and-Execute：解耦 Planning](../../../14-agent-engineering/02-rewoo-plan-and-execute/docs/zh.md)：plan-and-execute 范式的来源与动机。
- [阶段 13 · 01 工具接口：为什么 Agents 需要结构化输入输出](../../../13-tools-and-protocols/01-the-tool-interface/docs/zh.md)：`tool_name + args` 的结构化调用形态。
- [阶段 13 · 02 深入理解 Function Calling](../../../13-tools-and-protocols/02-function-calling-deep-dive/docs/zh.md)：真实模型如何产出工具调用。
- [阶段 19 · 20 Agent Harness 的循环契约](../../20-agent-harness-loop-contract/docs/zh.md)：读取本节 `SessionResult` 的 harness 循环。
- [阶段 19 · 23 函数调用分派器](../../23-function-call-dispatcher/docs/zh.md)：执行每一步的 dispatcher。

### 本节被哪些后续内容用到
- [阶段 19 · 25 Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：在每步之前/之后加入校验门与观察大小预算。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：让计划中的 shell 步骤在受限环境中执行。
- [阶段 19 · 28 OTel GenAI Spans 与 Prometheus Metrics](../../28-observability-otel-traces/docs/zh.md)：把本节事件流变成 trace。
- [阶段 19 · 29 基于 Harness 的端到端 Coding Agent](../../29-end-to-end-coding-task-demo/docs/zh.md)：把 registry、dispatcher、planner、gates、sandbox 组装起来。
- [阶段 14 · 11 结合 HTN 与演化搜索的 Planning](../../../14-agent-engineering/11-planning-htn-and-evolutionary/docs/zh.md)：更复杂的分层规划。
- [阶段 14 · 13 有状态图 Orchestration](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：把状态机执行器扩展为持久化的图执行。

### 延伸关键词
`plan-and-execute` · `ReWOO` · `ReAct` · `replanning` · `state machine` · `plan diff` · `step budget` · `replan budget` · `partial-plan caching` · `idempotency key` · `human-in-the-loop` · `difflib.SequenceMatcher`
