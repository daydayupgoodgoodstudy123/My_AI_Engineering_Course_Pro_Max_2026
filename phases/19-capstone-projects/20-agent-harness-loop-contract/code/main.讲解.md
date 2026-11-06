# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 20 节 Agent Harness 的循环契约 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（演示）；`python -m pytest -q` 或 `python -m unittest discover -s tests`（测试，在 `code/` 目录下） ｜ **依赖**：仅标准库（`json`、`time`、`dataclasses`、`enum`、`typing`、`unittest`）

---

## 1. 这份代码在考察什么

这一节是第 20–29 节"自己写一个 coding agent harness"系列的地基。它**不调用模型、不执行工具、不实现传输**，只把循环的"契约"固定下来：

1. **显式状态机**：六个状态 + 一张合法转移表，所有转移经 `_transition` 检查。
2. **Hook 扩展点**：十个生命周期 topic，运维方可以在这些位置挂策略、遥测、guardrail。
3. **Pull point**：循环需要外部输入（工具结果）或预算耗尽时，以**返回值**的形式把控制权交还调用方，调用方 `resume(payload)` 继续。
4. **类型化事件流**：十一种事件按固定时机追加，供 UI、tracer 订阅。
5. **预算信封**：turns、tool calls、wall-clock 三个上限，达到即暂停（yield），不是直接杀掉。

> 一句话：**把"一个 agent 会话"写成一个可审计、可拦截、可暂停恢复的确定性状态机，让模型、工具、策略之后都只是"注册进去"的部件。**

同时也要看清代码与讲义在几处契约上的落差（直接改 `self.state`、`_history` 从不更新、重新规划未实现、非 `before_tool_call` 的 hook 异常会卡死会话）——这些是本节最值得讨论的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `State` | `str` + `Enum` | 六个状态 | 状态机节点 |
| `HOOK_TOPICS` / `EVENT_TYPES` | 元组常量 | 10 个 hook topic、11 个事件类型的白名单 | 契约枚举 |
| `HookAbort` | 异常类 | hook 用来中止当前工具调用 | 策略拦截 |
| `Event` | dataclass | `type + payload + ts` | 事件信封 |
| `Budget` | dataclass | 三个上限 + 计数器 + `exceeded()` | 预算信封 |
| `Step` | dataclass | 计划中的一步：是否需要工具、工具名与参数、结果/错误 | 计划单元 |
| `PullRequest` | dataclass | 循环让出控制权时的返回值 | pull point |
| `SessionResult` | dataclass | 会话到达 `DONE` 时的返回值 | 终止结果 |
| `HookRegistry` | 类 | topic → 订阅者列表；`on` 注册、`fire` 依次调用 | hook 分发表 |
| `_default_planner` | 函数 | 固定返回三步计划（两步需要工具） | 模型的替身 |
| `HarnessLoop` | 类 | `run` / `resume` 对外；`_step` / `_begin_plan` / `_check_budget` / `_pause` / `_complete` / `_transition` / `_emit` 对内 | 循环本体 |
| `_demo` | 函数 | 给所有 topic 挂记录器，跑完默认计划，打印 JSON 报告 | 演示 |

数据流：`run(goal)` → `session.start` → `_step`（`IDLE` → `_begin_plan` → `PLANNING` → `EXECUTING`）→ 逐步执行：无工具步骤直接完成并进入 `REFLECTING`，工具步骤进入 `AWAITING_TOOL` 并**返回** `PullRequest` → 调用方 `resume({"result": ...})` → `REFLECTING` → 推进游标 → …… → `_complete` → `DONE` → 返回 `SessionResult`。

---

## 3. 逐段精讲

### 3.1 状态与契约常量

```python
class State(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    AWAITING_TOOL = "awaiting_tool"
    REFLECTING = "reflecting"
    DONE = "done"


HOOK_TOPICS = ("before_plan", "after_plan", "before_step", "after_step",
               "before_tool_call", "after_tool_call", "on_error", "on_pause",
               "on_budget_exceeded", "on_complete")

EVENT_TYPES = ("session.start", "plan.draft", "plan.commit", "step.start", "step.end",
               "tool.call", "tool.result", "tool.error", "budget.warn",
               "session.pause", "session.complete")
```

- `State(str, Enum)`：同时继承 `str`，于是 `State.DONE == "done"` 为真，序列化成 JSON 时也方便（演示里用 `.value`）。
- 两个元组就是讲义中"ten hook topics""eleven event types"的白名单；`HookRegistry.on` 与 `_emit` 都会用它校验，拼错名字立即 `ValueError`，而不是静默失效。实测 `len(HOOK_TOPICS) == 10`、`len(EVENT_TYPES) == 11`、`len(State) == 6`，与讲义一致。

### 3.2 数据类：Event、Budget、Step、PullRequest、SessionResult

```python
@dataclass
class Budget:
    max_turns: int = 8
    max_tool_calls: int = 16
    max_wall_seconds: float = 30.0
    turns: int = 0
    tool_calls: int = 0
    started_at: float = field(default_factory=time.time)

    def remaining_seconds(self) -> float:
        return max(0.0, self.max_wall_seconds - (time.time() - self.started_at))

    def exceeded(self) -> str | None:
        if self.turns >= self.max_turns:
            return "turns"
        if self.tool_calls >= self.max_tool_calls:
            return "tool_calls"
        if self.remaining_seconds() <= 0.0:
            return "wall_clock"
        return None
```

- 上限和计数器放在同一个对象里，`exceeded()` 返回**哪一个**上限被触发（或 `None`），调用方据此拼出 `budget_exceeded:turns` 这样的 reason。
- 检查顺序是 turns → tool_calls → wall_clock，同时触发多个时只报第一个。
- 关键语义：`>=` 表示"**达到**上限即触发"。配合"每次 `_step` 开头检查"，会出现"最后一次额度刚用完、只差收尾也要暂停"的情况（见第 6 节和测验 Q6）。
- `field(default_factory=time.time)`：传入函数本身而不是 `time.time()` 的结果，每个实例在创建时取当前时间；`run()` 里还会再重置一次。

```python
@dataclass
class Step:
    id: int
    description: str
    requires_tool: bool
    tool_name: str | None = None
    tool_args: dict = field(default_factory=dict)
    result: Any = None
    error: str | None = None
```

- `Step` 既是计划（`requires_tool`、`tool_name`、`tool_args`）又是执行记录（`result`、`error`），是可变对象，会被 hook payload、`SessionResult.steps` 共享引用。
- `PullRequest(reason, state, payload)` 与 `SessionResult(state, reason, steps, events)` 是 `run()`/`resume()` 的两种返回类型，返回注解写成 `PullRequest | SessionResult`，调用方用 `isinstance` 区分。

### 3.3 HookRegistry

```python
class HookRegistry:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[dict], Any]]] = {t: [] for t in HOOK_TOPICS}

    def on(self, topic: str, fn: Callable[[dict], Any]) -> None:
        if topic not in self._subs:
            raise ValueError(f"unknown hook topic: {topic}")
        self._subs[topic].append(fn)

    def fire(self, topic: str, payload: dict) -> list[Any]:
        results = []
        for fn in self._subs[topic]:
            results.append(fn(payload))
        return results
```

- 每个 topic 一个列表，**按注册顺序**依次调用——对应讲义"Subscribers fire in registration order"。
- 讲义说订阅者可以"mutate the payload, raise to abort the turn, or return a sentinel to skip the next step"。代码实际情况：
  - **修改**：payload 字典每次新建，改字典无效；但字典里的 `Step` 是共享引用，改 `p["step"].tool_args` 会影响随后返回的 `PullRequest`（实测 `args` 变成 `{"safe": True}`）。
  - **中止**：只有 `before_tool_call` 处捕获 `HookAbort`；其他 topic 抛出的任何异常都会穿出 `run()`/`resume()`。
  - **sentinel**：`fire` 收集了返回值，但所有调用点都丢弃它，返回值没有任何效果。
- 一个订阅者抛异常后，同一 topic 后面的订阅者不会执行。

### 3.4 默认 planner

```python
def _default_planner(goal: str, history: list[Step]) -> list[Step]:
    if history:
        return []
    return [
        Step(id=1, description=f"interpret goal: {goal}", requires_tool=False),
        Step(id=2, description="fetch user record", requires_tool=True,
             tool_name="db.get_user", tool_args={"id": 42}),
        Step(id=3, description="summarize and respond", requires_tool=True,
             tool_name="format.summary", tool_args={"style": "short"}),
    ]
```

- `Planner = Callable[[str, list[Step]], list[Step]]` 是类型别名：任何"(目标, 历史) → 步骤列表"的函数都能注入，测试里就注入了 `linear_planner`、`two_tool_planner`。
- `if history: return []` 的设计意图是"有历史就说明做完了，返回空计划以结束"。但 `HarnessLoop._history` 从未被追加，所以这个分支永远走不到（实测 planner 只被调用 1 次，`history` 长度 0）。

### 3.5 转移表与事件发射

```python
    def _emit(self, etype: str, payload: dict) -> None:
        if etype not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {etype}")
        self._events.append(Event(type=etype, payload=payload, ts=time.time()))

    def _transition(self, target: State) -> None:
        legal: dict[State, set[State]] = {
            State.IDLE: {State.PLANNING},
            State.PLANNING: {State.EXECUTING, State.IDLE, State.DONE},
            State.EXECUTING: {State.AWAITING_TOOL, State.REFLECTING, State.IDLE},
            State.AWAITING_TOOL: {State.REFLECTING, State.IDLE},
            State.REFLECTING: {State.PLANNING, State.EXECUTING, State.DONE, State.IDLE},
            State.DONE: set(),
        }
        if target not in legal[self.state]:
            raise RuntimeError(f"illegal transition {self.state.value} -> {target.value}")
        self.state = target
```

- 对照讲义的 mermaid 图，表里多了"各状态 → `IDLE`"（用于预算暂停），这是图里没画出的边。
- `DONE: set()`：终态没有出边，会话结束后任何转移都会被拒绝。
- 表中存在、但代码**从未走到**的边：`REFLECTING → PLANNING`（重新规划未实现）、`PLANNING → IDLE`、`AWAITING_TOOL → IDLE`（`AWAITING_TOOL` 时不检查预算）。
- 反过来，`resume()` 的预算恢复分支用 `self.state = State.EXECUTING / REFLECTING` **直接赋值**，走的是表中并不存在的 `IDLE → EXECUTING / REFLECTING`。讲义"`_transition` 是唯一改变状态的函数"在这里被打破。
- `legal` 字典每次调用都重新构建，可以提到类级常量；`events` 和 `plan` 属性返回 `list(...)` 浅拷贝，防止外部改动内部列表（但列表里的对象仍共享）。

### 3.6 预算检查与暂停

```python
    def _check_budget(self) -> PullRequest | None:
        which = self.budget.exceeded()
        if which is None:
            return None
        self._emit("budget.warn", {"limit": which})
        self.hooks.fire("on_budget_exceeded", {"limit": which, "budget": self.budget})
        self._reason = f"budget_exceeded:{which}"
        self._prev_state = self.state
        return self._pause(self._reason)

    def _pause(self, reason: str) -> PullRequest:
        self._emit("session.pause", {"reason": reason})
        self.hooks.fire("on_pause", {"reason": reason})
        self._transition(State.IDLE)
        return PullRequest(reason=reason, state=self.state, payload={"reason": reason})
```

- 顺序：`budget.warn` 事件 → `on_budget_exceeded` hook → 记录 `_prev_state`（暂停前在 `EXECUTING` 还是 `REFLECTING`）→ `session.pause` 事件 → `on_pause` hook → 转入 `IDLE` → 返回 `PullRequest`。与讲义"fires `on_budget_exceeded`, emits `budget.warn`, then transitions to `IDLE`"一致（事件与 hook 的先后略有不同）。
- `on_budget_exceeded` 的 payload 里放的是 `Budget` 对象本身，hook 可以修改上限，但改了也不能阻止这次暂停。
- `_pause` 是唯一的暂停入口，但只有预算会调用它。讲义说 hook 也能"explicitly request human review"来触发暂停，代码中没有这个机制。

### 3.7 `run` 与 `resume`

```python
    def run(self, goal: str) -> PullRequest | SessionResult:
        if self.state != State.IDLE:
            raise RuntimeError(f"run() requires IDLE, got {self.state.value}")
        self._goal = goal
        self.budget.started_at = time.time()
        self._emit("session.start", {"goal": goal})
        return self._step()
```

- 唯一入口，要求 `IDLE`。问题：预算暂停后的状态**也是** `IDLE`，此时再调 `run("another")` 会被接受，覆盖旧计划（实测出现第二个 `session.start`，随后因计数器未重置立刻再次暂停）。"全新"和"暂停中"在状态上无法区分。

```python
        if self.state == State.AWAITING_TOOL:
            if payload is None:
                raise ValueError("resume from AWAITING_TOOL requires a payload")
            current = self._plan[self._cursor]
            if "error" in payload:
                current.error = str(payload["error"])
                self._emit("tool.error", {"step": current.id, "error": current.error})
                self.hooks.fire("on_error", {"step": current, "error": current.error})
            else:
                current.result = payload.get("result")
                self._emit("tool.result", {"step": current.id, "result": current.result})
            self.hooks.fire("after_tool_call", {"step": current})
            self._transition(State.REFLECTING)
            return self._step()
```

- 工具结果通过 payload 回来：有 `"error"` 键就当错误，否则取 `"result"`。注意判断的是**键是否存在**：`{"result": 1, "error": None}` 也会被当作错误，`error` 变成字符串 `'None'`（实测）。
- 无论成功还是失败，都触发 `after_tool_call` 并进入 `REFLECTING`，然后继续下一步——失败不会重试，也不会重新规划。
- 预算恢复分支（上一节已列出代码）：清零 `turns`、`tool_calls`，重置 `started_at`，按 `_prev_state` 回到 `EXECUTING`（重做被打断的步骤）或 `REFLECTING`（推进游标）。`if not self._plan: return self._begin_plan()` 在当前代码里走不到——预算只在 `_begin_plan` 之后检查，而空计划会直接完成。
- 其他状态调用 `resume()` 抛 `RuntimeError`。

### 3.8 `_begin_plan`：规划阶段

```python
    def _begin_plan(self) -> PullRequest | SessionResult:
        self._transition(State.PLANNING)
        self.hooks.fire("before_plan", {"goal": self._goal, "history": list(self._history)})
        draft = self._planner(self._goal, list(self._history))
        self._emit("plan.draft", {"steps": [s.description for s in draft]})
        self.hooks.fire("after_plan", {"steps": draft})
        self._plan = draft
        self._cursor = 0
        self._emit("plan.commit", {"count": len(draft)})
        if not draft:
            return self._complete("no_plan")
        self._transition(State.EXECUTING)
        return self._step()
```

- 草案（draft）与提交（commit）分开：中间的 `after_plan` hook 拿到的是 `draft` 列表本身，可以就地增删步骤（例如策略 hook 删掉危险步骤），提交的是修改后的列表——这是"draft → commit"两段式的价值。但 `plan.draft` 事件在 hook **之前**发出，记录的是修改前的描述。
- `plan.draft` 只记录 `description`，丢掉了 `requires_tool`/`tool_name`/`tool_args`，仅凭事件日志无法重建计划。
- 空计划 → `PLANNING → DONE`，reason 为 `no_plan`（测试 `test_empty_plan_completes`）。

### 3.9 `_step`：循环的心脏

```python
    def _step(self) -> PullRequest | SessionResult:
        if self.state == State.IDLE:
            return self._begin_plan()
        budget_hit = self._check_budget()
        if budget_hit is not None:
            return budget_hit
        if self.state == State.REFLECTING:
            self._cursor += 1
            self.budget.turns += 1
            if self._cursor >= len(self._plan):
                return self._complete("goal_met")
            self._transition(State.EXECUTING)
            return self._step()
        ...
        step = self._plan[self._cursor]
        self.hooks.fire("before_step", {"step": step})
        self._emit("step.start", {"step_id": step.id, "desc": step.description})
        if step.requires_tool:
            try:
                self.hooks.fire("before_tool_call", {"step": step})
            except HookAbort as exc:
                step.error = f"hook_abort:{exc}"
                self._emit("tool.error", {"step": step.id, "error": step.error})
                self.hooks.fire("on_error", {"step": step, "error": step.error})
                self._transition(State.REFLECTING)
                return self._step()
            self.budget.tool_calls += 1
            self._emit("tool.call", {...})
            self._transition(State.AWAITING_TOOL)
            self._emit("step.end", {"step_id": step.id, "outcome": "awaiting_tool"})
            self.hooks.fire("after_step", {"step": step, "outcome": "awaiting_tool"})
            return PullRequest(reason="tool_call", state=self.state, payload={...})
        step.result = f"ok:{step.description}"
        self._emit("step.end", {"step_id": step.id, "outcome": "ok"})
        self.hooks.fire("after_step", {"step": step, "outcome": "ok"})
        self._transition(State.REFLECTING)
        return self._step()
```

逐点说明：

- **递归驱动**：`_step` 在内部状态变化后递归调用自己，直到遇到 pull point 或终态才返回。计划很长时递归深度约为"步数 × 2"，Python 默认递归上限 1000：实测 450 个无工具步骤的计划能完成，600 步时抛 `RecursionError`；生产中应改成 `while` 循环。
- **预算检查位置**：每次 `_step` 开头（`IDLE` 分支除外），包括 `REFLECTING` 准备"完成"之前。所以"刚好用完额度"的会话会先暂停再完成。讲义说 wall-clock "checked on every state transition"，代码实际是"每次进入 `_step`"；`AWAITING_TOOL` 期间完全不检查。
- **turn 的含义**：讲义"Each turn increments turns by one"；代码中 turn = "完成一个步骤并推进游标"，在 `REFLECTING` 计数。
- **无工具步骤**：直接写 `result = "ok:..."`，发 `step.end`，进入 `REFLECTING`。
- **工具步骤**：`before_tool_call` → 计数 → `tool.call` → 转入 `AWAITING_TOOL` → `step.end(awaiting_tool)` → `after_step` → 返回 `PullRequest`。因此 `after_step` 在工具执行**之前**就触发（Q5）。
- **HookAbort 分支**：记录错误、`tool.error`、`on_error`，转 `REFLECTING` 继续。不计入 `tool_calls`，不发 `step.end`，不触发 `after_step`，造成 `step.start` 没有配对的 `step.end`（Q12）。
- `before_step` 等其他 hook 没有 `try`，抛异常时会话停在 `EXECUTING`，之后 `run()`、`resume()` 都不可用（实测）。

### 3.10 `_complete` 与 `_demo`

```python
    def _complete(self, reason: str) -> SessionResult:
        self._emit("session.complete", {"reason": reason})
        self.hooks.fire("on_complete", {"reason": reason})
        self._transition(State.DONE)
        self._reason = reason
        return SessionResult(state=self.state, reason=reason, steps=list(self._plan), events=list(self._events))
```

- 进入 `DONE` 后状态机没有出边，`run()` 再调用会因不是 `IDLE` 而报错（`test_run_twice_raises`）。
- reason 只有 `goal_met` 和 `no_plan` 两种；即使所有工具步骤都失败或被拦截，也报 `goal_met`。

```python
    for topic in HOOK_TOPICS:
        loop.hooks.on(topic, lambda payload, t=topic: fired.append(t))
```

- `lambda payload, t=topic:` 用**默认参数**在定义时"冻结"当前的 `topic`。如果写成 `lambda payload: fired.append(topic)`，十个 lambda 都会在调用时读取循环变量的最终值 `"on_complete"`——这是 Python 闭包的经典坑（延迟绑定）。
- 演示用 `assert` 检查两次 `tool_call` 和最终 `goal_met`，再把事件类型、hook 序列打印成 JSON。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 显式六状态 + 集中转移表 | 非法转移一处拒绝；可测试、可回放 | `resume` 绕过了它；应补 `PAUSED` 状态或补全转移表 |
| pull point 用返回值而非异常/回调 | 调用方自选传输（TUI、MCP、队列），可跨进程恢复 | 调用方要写驱动循环；harness 要显式保存游标等状态 |
| hooks 与 events 分离 | 命令式扩展与观测式记录互不干扰 | 事件缺少 `step.end` 等配对时 tracer 出错；应把配对规则写进测试 |
| 只在 `before_tool_call` 捕获 `HookAbort` | 最常见的策略拦截点 | 其他 hook 抛异常会卡死会话；应统一包装所有 `fire` |
| 预算"达到即暂停"，恢复时全部清零 | 实现简单，保证不越界 | 收尾也要额外 resume；恢复等于无限续杯；应在消耗前检查，并显式追加额度 |
| `_step` 递归 | 代码短，状态推进直观 | 长计划会触发递归上限；生产用 `while` 循环 |
| 固定 planner | 确定性、无需模型即可测试契约 | 重新规划未实现，`_history` 从不更新 |
| 事件带 `time.time()` 时间戳 | 方便观测 | 回放时需要可注入的时钟；`plan.draft` 信息不足以重建计划 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，`PullRequest | SessionResult` 等写法不会在定义时报错 |
| 继承 `str` 的枚举 | `class State(str, Enum)` | 枚举成员同时是字符串，可直接与 `"done"` 比较；`.value` 取原始值 |
| 自定义异常 | `class HookAbort(Exception)` | 用异常类型表达特定控制流（策略中止） |
| `@dataclass` + 默认值 | `class Budget: max_turns: int = 8` | 自动生成构造函数；有默认值的字段必须排在无默认值字段之后 |
| `field(default_factory=...)` | `field(default_factory=time.time)`、`field(default_factory=dict)` | 每个实例单独调用工厂，避免共享可变默认值或"定义时的时间" |
| 类型别名 | `Planner = Callable[[str, list[Step]], list[Step]]` | 给复杂的函数签名起名字 |
| `Callable` / `Any` | `Callable[[dict], Any]` | 来自 `typing`，描述"接收 dict、返回任意值的函数" |
| `X | None` 与联合返回 | `-> str | None`、`-> PullRequest | SessionResult` | 返回值可能是多种类型，调用方用 `isinstance` 区分 |
| 字典推导式 | `{t: [] for t in HOOK_TOPICS}` | 为每个 topic 建空列表 |
| `@property` | `def events(self) -> list[Event]: return list(self._events)` | 像属性一样访问，返回副本保护内部状态 |
| 下划线前缀 | `self._events`、`_transition` | 约定为"内部使用"，Python 不强制（测试里就直接调用了 `loop._transition`） |
| `or` 提供默认值 | `budget or Budget()`、`planner or _default_planner` | 参数为 `None` 时用默认对象（注意空对象也会被视为假） |
| `try / except ... as exc` | `except HookAbort as exc:` | 捕获特定异常并拿到异常对象，`f"hook_abort:{exc}"` 取其消息 |
| 递归 | `_step` 内 `return self._step()` | 状态推进后继续处理；有递归深度上限 |
| lambda 默认参数绑定 | `lambda payload, t=topic: fired.append(t)` | 在定义时固定循环变量的值，避免闭包延迟绑定 |
| `assert` + `isinstance` | `assert isinstance(out, PullRequest) and out.reason == "tool_call"` | 演示中的自检；`python -O` 运行时会被跳过 |
| `json.dumps(..., indent=2)` | `print(json.dumps(report, indent=2))` | 格式化输出 JSON |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `_demo()`，被测试 import 时不执行 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13）：

```text
{
  "events": [
    "session.start",
    "plan.draft",
    "plan.commit",
    "step.start",       ← 步骤 1（无工具）
    "step.end",
    "step.start",       ← 步骤 2（db.get_user）
    "tool.call",
    "step.end",         ← outcome = awaiting_tool，在工具结果之前
    "tool.result",      ← 第一次 resume
    "step.start",       ← 步骤 3（format.summary）
    "tool.call",
    "step.end",
    "tool.result",      ← 第二次 resume
    "session.complete"
  ],
  "hooks_fired": [
    "before_plan", "after_plan",
    "before_step", "after_step",
    "before_step", "before_tool_call", "after_step", "after_tool_call",
    "before_step", "before_tool_call", "after_step", "after_tool_call",
    "on_complete"
  ],
  "final_state": "done",
  "final_reason": "goal_met"
}
```

（`hooks_fired` 为节省篇幅合并了行，原输出每项一行。）

解读：

- **14 个事件、13 次 hook**。11 种事件类型里出现了 8 种；`tool.error`、`budget.warn`、`session.pause` 只在错误和预算场景出现。10 个 hook topic 出现了 7 个；`on_error`、`on_pause`、`on_budget_exceeded` 同理只在异常场景出现。`before_plan` 只出现一次（不会重新规划）。
- **两次 pull point**：`run()` 在步骤 2 返回、第一次 `resume()` 在步骤 3 返回，第二次 `resume()` 才拿到 `SessionResult`——三次调用，演示中的三个 `assert` 都通过。
- **工具步骤的事件顺序**是 `step.start → tool.call → step.end → tool.result`：这一步在 harness 看来"结束"于发出工具请求的那一刻。

额外场景实测（临时脚本，不修改源码）：

| 场景 | 结果 |
|------|------|
| 3 个无工具步骤，`max_turns = 1 / 2 / 3` | 分别执行 1、2 步后返回 `budget_exceeded:turns`；`max_turns=3` 时 `goal_met` |
| 两个工具步骤，`max_tool_calls = 2` | 第二个工具结果回来后返回 `budget_exceeded:tool_calls`，再 `resume()` 才 `goal_met` |
| `max_wall_seconds = 0` | 事件为 `session.start, plan.draft, plan.commit, budget.warn, session.pause`；`resume()` 后再次暂停，永远无法前进 |
| `before_tool_call` 抛 `HookAbort` | `goal_met`；`tool_calls = 0`；两个 `tool.error`，被拦截步骤没有 `step.end` |
| `before_step` 抛 `HookAbort` | 异常穿出 `run()`，状态停在 `EXECUTING`，`resume()` 报 "unsupported from state executing" |
| 预算暂停后再 `run("another")` | 被接受，出现第二个 `session.start`，旧计划被覆盖 |
| hook 返回 `"SKIP"` | 无效果，三个步骤照常执行 |

---

## 7. 动手改一改

1. **补齐配对事件**：在 `HookAbort` 分支补发 `step.end(outcome="aborted")` 并触发 `after_step`，再写一个测试断言"每个 `step.start` 都有对应的 `step.end`"。
2. **统一 hook 异常处理**：实现 `_fire_guarded(topic, payload)`，任何 topic 抛 `HookAbort` 时都能把会话带到合法状态（跳过当前步或暂停），并补一个"`before_step` 抛异常"的测试。
3. **引入 `PAUSED` 状态**：让预算暂停转入 `PAUSED` 而不是 `IDLE`，把恢复路径写进 `legal` 表并通过 `_transition` 执行；`run()` 在 `PAUSED` 时拒绝。
4. **实现重新规划**：在 `REFLECTING` 把完成的步骤追加到 `_history`，计划走完后回到 `PLANNING`；空计划时根据是否有历史返回 `goal_met` / `no_plan`（测验 Q11 给出了实测通过全部 18 个测试的改法）。
5. **更合理的预算**：改为"消耗前检查"（下一次工具调用会超额才暂停），并让 `resume(payload)` 支持 `{"extend": {"tool_calls": 5}}` 追加额度而不是清零。
6. **可回放**：让 `plan.draft` 记录完整的 `Step` 字段，注入可替换的时钟函数，写一个 `replay(events) -> HarnessLoop` 从事件日志重建状态，并验证与原会话的 `state`、`_cursor` 一致。

---

## 8. 常见坑

- **以为 `after_step` 在工具完成后触发**：本节中工具步骤的 `after_step` 发生在发出工具请求时；工具耗时要看 `after_tool_call` 或 `tool.result`。
- **lambda 闭包延迟绑定**：循环注册 hook 时忘了 `t=topic` 默认参数，所有 hook 记录的都是最后一个 topic。
- **把 pull point 当异常处理**：`run()` 正常返回 `PullRequest` 时会话并没有结束，必须检查返回类型并 `resume`。
- **`resume` 的 payload 键**：只要有 `"error"` 键（哪怕值是 `None`）就按错误处理。
- **预算上限设为 0**：恢复时只清零计数器、不改上限，`max_wall_seconds=0` 会无限暂停。
- **在暂停状态调用 `run()`**：因为状态是 `IDLE` 会被接受，旧进度被覆盖。
- **长计划的递归深度**：`_step` 递归推进，实测 600 个连续无工具步骤会撞到 `RecursionError`。
- **以为测试覆盖了契约的全部**：18 个测试都通过，但没有覆盖"非 `before_tool_call` hook 抛异常""暂停后 `run()`""事件配对"等情形。

---

## 9. 测试在验证什么

`tests/test_loop.py` 共 18 个 `unittest` 测试，分 5 组。它通过 `sys.path.insert(0, os.path.dirname(HERE))` 把 `code/` 加入导入路径，所以可以在 `code/` 下用 `python -m pytest -q`、`python -m unittest discover -s tests`，或直接 `python tests/test_loop.py` 运行。测试里自定义了两个 planner：`linear_planner`（3 个无工具步骤）和 `two_tool_planner`（1 个无工具 + 2 个工具步骤），两者都有 `if history: return []`。

| 测试 | 验证的性质 |
|------|-----------|
| **TestStateTransitions** | |
| `test_idle_to_done_linear` | 无工具计划一次 `run()` 就到 `DONE`，reason 为 `goal_met` |
| `test_run_twice_raises` | 会话结束后再 `run()` 抛 `RuntimeError`（`DONE` 不是 `IDLE`） |
| `test_tool_pull_point_then_resume` | 工具步骤返回 `tool_call` pull point，状态为 `AWAITING_TOOL`；两次 `resume` 后完成 |
| `test_resume_requires_payload` | 从 `AWAITING_TOOL` 恢复时 payload 为 `None` 抛 `ValueError` |
| `test_illegal_transition_rejected` | 直接调用 `_transition(State.DONE)`（`IDLE → DONE`）被拒绝 |
| `test_empty_plan_completes` | planner 返回空列表时 reason 为 `no_plan` |
| **TestHooks** | |
| `test_all_topics_register` | 十个 topic 都能注册（无断言，不抛异常即通过） |
| `test_unknown_topic_rejected` | 未知 topic 抛 `ValueError` |
| `test_hook_firing_order_linear` | 第一、二个是 `before_plan`、`after_plan`，最后是 `on_complete`；`before_step`/`after_step` 各 3 次；无工具计划不触发 `before_tool_call` |
| `test_before_tool_call_fires_per_tool_step` | `before_tool_call` 与 `after_tool_call` 都恰好对步骤 2、3 各触发一次 |
| `test_hook_abort_skips_tool_call` | `before_tool_call` 抛 `HookAbort` 时 `run()` 直接返回 `SessionResult`，`on_error` 收到 2 条以 `hook_abort` 开头的错误 |
| **TestEvents** | |
| `test_event_stream_shape` | 事件流以 `session.start` 开始、以 `session.complete` 结束，中间包含 plan 与 step 事件 |
| `test_tool_events_emitted` | 两个工具步骤各有一次 `tool.call` 和 `tool.result`，没有 `tool.error` |
| `test_tool_error_recorded` | `resume({"error": "boom"})` 产生 `tool.error` |
| **TestBudget** | |
| `test_turn_limit_paused` | `max_turns=1` 时 `run()` 返回以 `budget_exceeded` 开头的 pull point |
| `test_tool_call_limit_paused` | `max_tool_calls=1` 时，第一个工具结果回来后返回预算暂停 |
| `test_wall_clock_check` | `max_wall_seconds=0` 时 reason 恰为 `budget_exceeded:wall_clock` |
| **TestDeterminism** | |
| `test_same_inputs_same_event_types` | 两次独立运行同一计划，事件类型序列完全相同 |

实际运行结果（`python3 -m pytest -q`）：

```text
..................                                                       [100%]
18 passed in 0.02s
```

`python3 -m unittest discover -s tests -v` 同样 `Ran 18 tests ... OK`。

测试的盲区（也是讲义"Run them. Break them. Add cases."的邀请）：

- 没有测试预算暂停后的 `resume()` 能否正确完成会话，也没有测试暂停后调用 `run()` 的行为；
- 没有测试 `before_tool_call` 以外的 hook 抛异常；
- 没有检查 `step.start`/`step.end` 配对、`tool.call`/`tool.result|error` 配对；
- `test_tool_error_recorded` 只检查事件存在，没有检查会话之后能否继续并完成；
- 确定性测试只比较事件**类型**，不是"从日志回放"。
