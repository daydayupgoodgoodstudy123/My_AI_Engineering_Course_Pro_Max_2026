# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 04 节 多 Agent 的基本单元模型 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`threading`、`dataclasses`、`typing`），无需 LLM、无需网络

---

## 1. 这份代码在考察什么

讲义的核心论断是：所有多 agent 框架都只是在四个原语（primitive）上取不同的默认值——**Agent、Handoff、Shared state、Orchestrator**。这份代码用约 170 行标准库 Python 把这四个原语落成最小实现，然后让**同一组 agent、同一种共享状态**分别跑在三种 orchestrator 下：

1. **Agent 是无状态的**：`Agent` 只是"名字 + system prompt + 策略函数"，每次运行都从共享状态推导出要说什么，自己不保存任何东西。
2. **共享状态是系统里唯一有状态的部分**：`SharedState` 是一个带锁的消息池（message pool），所有 agent 读写同一个列表。
3. **Handoff 是一个结构化字段**：agent 返回的消息里带 `"handoff": "writer"`，表示"下一个该谁"。
4. **Orchestrator 决定谁下一个说话**：静态顺序（LangGraph 式）、由当前 agent 的 handoff 决定（OpenAI Swarm 式）、由 selector 函数决定（AutoGen GroupChat 式）。

> 一句话：**把 agent 和状态固定住，只换"谁决定下一个发言者"，看清 orchestrator 这一根轴到底改变了什么。**

需要提前说明的是：在默认脚本下三种 orchestrator 的输出**完全相同**，讲义承诺的"handoff 驱动的运行在 researcher 提前结束时会访问更少 agent"并没有在默认运行中体现，需要自己构造输入才能看到（见第 6、7 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Message = dict` | 类型别名 | 消息就是普通字典，含 `from`、`content`、`handoff` | 消息格式 |
| `SharedState` | dataclass | 线程安全的消息池：`append` / `snapshot` / `last_by` | Shared state（full pool） |
| `Agent` | dataclass | `name` + `system_prompt` + `policy`；`run` 调策略并补上 `from` | Agent 原语（无状态） |
| `researcher_policy` / `writer_policy` / `reviewer_policy` | 函数 | 脚本化的"假 LLM"：读消息池，返回内容和 handoff 目标 | Agent 的行为 |
| `make_team` | 函数 | 构造三人团队字典 `{name: Agent}` | 团队 |
| `StaticOrchestrator` | 类 | 按固定列表顺序依次运行 | 静态图 orchestrator |
| `HandoffOrchestrator` | 类 | 从起点开始，每步跟随上一条消息的 `handoff` 字段 | Handoff 驱动 orchestrator |
| `LLMSelectorOrchestrator` | 类 | 每步调用 `selector(state, team)` 选下一个发言者 | LLM 选择 orchestrator |
| `round_robin_selector` | 函数 | 模拟的 selector：轮流发言，reviewer 说过话就停 | 发言者选择（speaker selection） |
| `render_pool` | 函数 | 打印消息池 | 可观测性 |
| `main` | 函数 | 三种 orchestrator 各跑一遍并打印 | 演示入口 |

数据流：`main` → `make_team()` + 新的 `SharedState()` → `Orchestrator.run(team, state)` 循环调用 `Agent.run(state)` → 策略函数读 `state.snapshot()` 生成消息 → `state.append(msg)` → orchestrator 决定下一个 → `render_pool` 打印。

---

## 3. 逐段精讲

### 3.1 `SharedState`：唯一有状态的原语

```python
@dataclass
class SharedState:
    messages: list[Message] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, msg: Message) -> None:
        with self._lock:
            self.messages.append(msg)

    def snapshot(self) -> list[Message]:
        with self._lock:
            return list(self.messages)

    def last_by(self, name: str) -> Optional[Message]:
        with self._lock:
            for m in reversed(self.messages):
                if m["from"] == name:
                    return m
            return None
```

- 这是讲义里的 **full pool** 拓扑：每个 agent 都能看到全部消息。讲义："Full pools are simple and scale badly."
- `field(default_factory=list)`：每个实例拿到自己的新列表。如果写成 `messages: list = []`，dataclass 会直接报错（防止所有实例共享同一个可变默认值）。
- `snapshot()` 返回的是**浅拷贝**：列表是新的，但里面的字典仍是同一批对象。调用方往快照里 append 不影响池子，但修改某条消息字典的内容会直接改到池子里。
- 锁在本 demo 中其实用不上（所有 orchestrator 都是单线程顺序执行），它是为讲义练习 2 的"队列驱动、多 worker 并发轮询"预留的。
- ⚠️ 锁只保护了经由这三个方法的访问；后面 `round_robin_selector` 直接读 `state.messages`，绕过了锁（见 3.5）。

### 3.2 `Agent`：名字 + prompt + 策略

```python
@dataclass
class Agent:
    name: str
    system_prompt: str
    policy: Callable[[SharedState], Message]

    def run(self, state: SharedState) -> Message:
        msg = self.policy(state)
        msg.setdefault("from", self.name)
        return msg
```

- 讲义定义 `Agent = (system_prompt, tools, model, optional_name)`；代码里用 `policy` 函数代替"模型 + 工具"，`system_prompt` 只是摆设（策略函数并不读取它）。讲义 Build It 说 Agent 是"a dataclass of name, system prompt, tools, policy function"，但代码里**没有 `tools` 字段**。
- **无状态**：`Agent` 对象没有任何会随运行改变的属性，所有"记忆"都从 `state` 里读。这正是讲义的 "Two agents with the same system prompt and tools are interchangeable"。
- ⚠️ `setdefault("from", self.name)` 只在策略没写 `from` 时才补上。如果策略返回 `{"from": "reviewer", ...}`，这条消息就会以 reviewer 的身份进入消息池——身份可被冒充（实测见第 6 节）。生产中应由框架**强制覆盖**发送者字段：`msg["from"] = self.name`。

### 3.3 三个脚本化策略：从共享状态推导一切

```python
def researcher_policy(state: SharedState) -> Message:
    n = len([m for m in state.snapshot() if m["from"] == "researcher"])
    notes = f"note {n + 1}: FIPA-ACL ratified 2000; 20 performatives."
    return {"content": notes, "handoff": "writer" if n == 0 else "done"}
```

- researcher 用"池子里我已经说过几次"来决定行为：第一次交给 writer，之后就宣布 `done`。这是"无状态 agent + 有状态共享池"的典型写法——agent 的"进度"存在消息池里。
- 内容中的事实取自上一节讲义（阶段 16 · 02）："FIPA-ACL (ratified 2000) produced the reference standardization: twenty performatives"。

```python
def writer_policy(state: SharedState) -> Message:
    research = [m["content"] for m in state.snapshot() if m["from"] == "researcher"]
    draft = "Draft summarizing: " + " | ".join(research) if research else "Draft with no research yet."
    return {"content": draft, "handoff": "reviewer"}

def reviewer_policy(state: SharedState) -> Message:
    last = state.last_by("writer")
    verdict = "approved" if last and "summarizing" in last["content"] else "needs revision"
    return {"content": f"Review verdict: {verdict}.", "handoff": "done"}
```

- writer 汇总所有 researcher 消息；没有研究就写一份"空草稿"。注意条件表达式的优先级：`"Draft summarizing: " + ... if research else ...` 等价于 `("Draft summarizing: " + ...) if research else (...)`。
- reviewer 只看 writer 最近一条消息，判断依据是字符串里有没有 `"summarizing"`——这是用关键字模拟"LLM 审稿"，非常脆弱，但足以演示流程。

### 3.4 静态与 handoff 驱动的 orchestrator

```python
class StaticOrchestrator:
    def run(self, team, state, max_steps: int = 10) -> None:
        for name in self.order[:max_steps]:
            msg = team[name].run(state)
            state.append(msg)
```

- 顺序在构造时就固定（LangGraph 确定性边、CrewAI Sequential）。`self.order[:max_steps]` 用切片限制步数。
- 它**完全忽略**消息里的 `handoff` 字段：即使 researcher 说 `done`，静态图也会继续调用 writer 和 reviewer。这正是"把路由钉死在代码里"的含义：可预测、可审计，但不会因为 agent 的判断而提前结束。

```python
class HandoffOrchestrator:
    def run(self, team, state, max_steps: int = 10) -> None:
        current = self.start
        for _ in range(max_steps):
            if current not in team:
                return
            msg = team[current].run(state)
            state.append(msg)
            nxt = msg.get("handoff", "done")
            if nxt == "done":
                return
            current = nxt
```

- OpenAI Swarm 式：路由权交给当前 agent。`msg.get("handoff", "done")` 让"没写 handoff"等价于结束。
- `max_steps` 是防止 A→B→A 无限循环的唯一保险。实测把 reviewer 改成永远交回 writer，会在第 10 条消息处被截断（第 6 节）。
- 目标名字不存在时静默 `return`，没有任何报错或日志——生产中应把"handoff 到未知 agent"视为错误并上报。

### 3.5 "LLM 选择"的 orchestrator 与轮询 selector

```python
class LLMSelectorOrchestrator:
    def run(self, team, state, max_steps: int = 10) -> None:
        current: Optional[str] = self.start
        for _ in range(max_steps):
            if current is None or current not in team:
                return
            msg = team[current].run(state)
            state.append(msg)
            current = self.selector(state, team)

def round_robin_selector(state, team) -> Optional[str]:
    if not state.messages:
        return None
    last = state.messages[-1]["from"]
    names = list(team.keys())
    idx = (names.index(last) + 1) % len(names)
    if len([m for m in state.messages if m["from"] == "reviewer"]) >= 1:
        return None
    return names[idx]
```

- 与 handoff 驱动的区别：agent 返回的 `handoff` 字段在这里被**忽略**，由外部 selector 读整个池子决定下一个（AutoGen GroupChat 的 speaker selection）。生产中 selector 本身就是一次 LLM 调用。
- `round_robin_selector` 名为 "LLM selector"，实际只是轮询：按字典插入顺序（Python 3.7+ 保证）`researcher → writer → reviewer → researcher ...`，只要 reviewer 发过言就返回 `None` 结束。
- ⚠️ 直接访问 `state.messages`，绕过了 `SharedState` 的锁；若将来改成多线程，就可能读到不一致的数据。应改用 `state.snapshot()`。
- ⚠️ `names.index(last)` 在最后发言者不在团队里时抛 `ValueError`（例如池子里有一条 `from: "user"` 的消息，实测 `ValueError 'user' is not in list`）。
- 先算 `idx` 再判断是否该结束，顺序上有一点浪费，但不影响结果。

### 3.6 `main`：控制变量的实验设计

```python
team = make_team()
state_a = SharedState()
StaticOrchestrator(["researcher", "writer", "reviewer"]).run(team, state_a)
render_pool("Static (LangGraph-style)", state_a)
```

- 每次都新建 `SharedState`，保证三次运行互不影响；`make_team()` 也重建了一次，其实 agent 无状态，复用同一个 team 结果完全一样——重建只是让"控制变量"的意图更显眼。
- `render_pool` 用 `f"{m['from']:10s}"` 左对齐到 10 个字符，并在有 `handoff` 时追加 `-> 目标`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 脚本化 policy 代替 LLM | 让注意力集中在协调结构上，结果可复现 | 体现不出 LLM 路由的不确定性；生产用真实模型 + tool calling |
| 消息用普通 `dict` | 简单、随写随用 | 没有 schema 校验，`from` 可冒充、字段名拼错不会报错；生产用 dataclass/Pydantic 或框架的消息类型 |
| full pool 共享状态 | 最容易理解与调试 | 上下文随消息数线性增长；生产常用 projected state（按角色投影）或 LangGraph reducer |
| `threading.Lock` | 为并发 orchestrator 预留 | 单线程 demo 中没有作用；分布式场景需要外部存储与版本控制 |
| handoff 作为消息字段 | 让三种 orchestrator 共享同一套 agent | 真正的 Swarm handoff 是"tool 返回一个 Agent 对象"，带参数与上下文传递 |
| `max_steps=10` 作为唯一保险 | 防止无限循环 | 到上限时静默结束，没有告警；生产应记录并区分"正常结束"与"被截断" |
| 未知 handoff 目标静默返回 | 代码简短 | 掩盖错误；应抛异常或走兜底 agent |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟类型注解求值，可在 3.7+ 写 `list[Message]`、引用尚未定义的类 |
| 类型别名 | `Message = dict` | 给类型起个名字，增强可读性，运行时没有任何检查 |
| `@dataclass` | `class SharedState`、`class Agent` | 自动生成 `__init__`、`__repr__` 等；字段按声明顺序成为构造参数 |
| `field(default_factory=...)` | `field(default_factory=list)`、`field(default_factory=threading.Lock)` | 为每个实例单独创建可变默认值 |
| `Callable[[A], R]` | `policy: Callable[[SharedState], Message]` | 注解"接收 SharedState、返回 Message 的函数" |
| `Optional[X]` | `-> Optional[Message]`、`current: Optional[str]` | 可能是 `X` 也可能是 `None` |
| `with` 语句 + 锁 | `with self._lock:` | 进入时加锁、离开（包括 return / 异常）时自动释放 |
| `reversed()` | `for m in reversed(self.messages)` | 从后往前遍历，找"最近一条" |
| `dict.setdefault` | `msg.setdefault("from", self.name)` | 键不存在才写入；存在则保持原值（本文件的冒充漏洞来源） |
| `dict.get` 带默认值 | `msg.get("handoff", "done")` | 键不存在时返回默认值，不抛 `KeyError` |
| 列表推导式 + `len` | `len([m for m in ... if m["from"] == "researcher"])` | 计数；更省内存的写法是 `sum(1 for m in ... if ...)` |
| 条件表达式 | `"writer" if n == 0 else "done"` | 一行内的 if/else |
| `str.join` | `" \| ".join(research)` | 用分隔符拼接字符串列表 |
| 切片 | `self.order[:max_steps]` | 取前 `max_steps` 个，越界不报错 |
| `list.index` + 取模 | `(names.index(last) + 1) % len(names)` | 找到位置后循环到下一个；找不到抛 `ValueError` |
| `enumerate` | `for i, m in enumerate(state.snapshot())` | 同时拿到下标和元素 |
| f-string 格式符 | `f"{m['from']:10s}"`、`"-" * 42` | 宽度 10 左对齐的字符串；字符串乘法重复 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时不到 0.1 秒）：

```text
Four multi-agent primitives demo
------------------------------------------

=== Static (LangGraph-style) ===
  [0] researcher | note 1: FIPA-ACL ratified 2000; 20 performatives. -> writer
  [1] writer     | Draft summarizing: note 1: FIPA-ACL ratified 2000; 20 performatives. -> reviewer
  [2] reviewer   | Review verdict: approved. -> done

=== Handoff-driven (OpenAI Swarm-style) ===
  （与上面完全相同的三行）

=== LLM-selected (AutoGen-style) ===
  （与上面完全相同的三行）

Takeaway: agents and state are identical across runs;
only the orchestrator choice changes who speaks when.
```

逐项解读：

- **三次输出完全一样**：因为脚本恰好让三种路由方式得出同一个顺序——researcher 第一次发言（`n == 0`）交给 writer，writer 交给 reviewer，reviewer 说 `done`；静态顺序也是这三个；轮询 selector 在 reviewer 发言后结束。Takeaway 说"只有 orchestrator 改变了谁何时发言"，但默认运行里谁何时发言**并没有改变**。
- **讲义的承诺需要构造输入才能看到**：讲义说"The handoff-driven run reaches fewer agents if the researcher decides it is done early"。我们预先往池子里放一条 researcher 的旧笔记（让 `n == 1`），再分别运行（实测）：

```text
static   [('researcher','writer'), ('researcher','done'), ('writer','reviewer'), ('reviewer','done')]
handoff  [('researcher','writer'), ('researcher','done')]
selector [('researcher','writer'), ('researcher','done'), ('writer','reviewer'), ('reviewer','done')]
```

  只有 handoff 驱动的运行在 researcher 说 `done` 后立即停止，writer 和 reviewer 根本没机会发言——这就是"信任 LLM 路由"的代价与收益：省了调用，但如果 researcher 判断错了，后续环节就被跳过了。静态图和 selector 都无视 `handoff` 字段。

- **其它实测**：
  - 冒充：策略返回 `{"from": "reviewer", ...}` 的 writer，其消息在池中显示为 reviewer。
  - 循环：reviewer 改为总是交回 writer，`HandoffOrchestrator` 在 `max_steps=10` 处截断，池中 10 条消息，没有任何告警。
  - 从 writer 开始的 selector 运行：`writer: Draft with no research yet.` → `reviewer: needs revision` 后结束——轮询 selector 在 reviewer 发言后就停，即使结论是"需要修改"。

---

## 7. 动手改一改

1. **让差异显形**（讲义练习 1）：把 `researcher_policy` 改成"第一次就 `done`"或在 `main` 里预置一条 researcher 消息，重新运行，对比三种 orchestrator 访问的 agent 数量。
2. **修补身份冒充**：把 `msg.setdefault("from", self.name)` 改为强制覆盖，并给消息加上递增的 `seq` 字段；再写一个断言检查池中每条消息的 `from` 都在团队里。
3. **队列驱动的 orchestrator**（讲义练习 2）：给 `SharedState` 加一个 `tasks` 队列，agent 在线程里循环轮询"属于自己的任务"。构造一个 writer 等 researcher、researcher 又等 reviewer 的环，观察死锁，并实现"所有 worker 都空闲且队列非空 → 判定死锁"的检测。
4. **让 selector 更像 LLM**：写一个 `keyword_selector`，读最后一条消息内容——包含 "needs revision" 就选 writer，包含 "approved" 就结束——并加上"最多 2 轮修改"的预算。
5. **projected state**：给 `SharedState` 加一个 `view(role)` 方法，writer 只能看到 researcher 的消息、reviewer 只能看到 writer 的消息，体会讲义"Projected pools scale but require upfront schema design"。
6. **把 handoff 做成真正的 Swarm 形式**：让策略返回 `(content, next_agent_object)`，handoff 携带 `reason` 和 `payload`（讲义 `Handoff = (from_agent, to_agent, reason, payload)`），并在池中记录一条 handoff 事件，便于追踪。

---

## 8. 常见坑

- **以为三种 orchestrator 的结果"应该"不同**：本 demo 默认输出完全一样，差异只在 agent 提前结束或循环时出现。设计对比实验时要构造能区分它们的输入。
- **`setdefault` 不是覆盖**：用它补"发送者"字段等于允许策略自报身份。
- **绕过锁读共享状态**：`state.messages` 直接访问在单线程下没问题，并发后会出现读到一半的数据；统一走 `snapshot()`。
- **浅拷贝快照**：`snapshot()` 返回新列表，但消息字典是共享的，改字典会改到池子。
- **`max_steps` 截断是静默的**：程序正常退出，看不出是"完成"还是"被截断"。
- **handoff 目标拼错**：`HandoffOrchestrator` 遇到未知名字直接返回，不报错，很难排查。
- **selector 遇到团队外的发言者会崩溃**：如果池里混入用户消息或系统消息，`names.index` 抛 `ValueError`。
- **把 `system_prompt` 当成有作用的字段**：本文件里它从未被读取，只是为了对齐讲义的 Agent 定义。
