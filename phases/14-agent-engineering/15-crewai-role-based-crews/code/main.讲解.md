# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 15 节 基于角色的 Agent 团队：角色、任务与流程 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：标准库（`hashlib`、`dataclasses`、`typing`）+ 第三方 `numpy`（仅用于记忆模块的向量运算）；不需要 CrewAI、API key 或网络。注意讲义写的是"Python (stdlib)"，实际需要 numpy

---

## 1. 这份代码在考察什么

用不到 350 行代码复刻 CrewAI 的主要概念，并让同一个 researcher → writer → editor 团队以三种形态运行：

1. **CrewAI 的原语**：`Agent`（role / goal / backstory / tools）、`Task`（description / expected_output / agent / context）、两种 Crew（Sequential、Hierarchical，对应两种 Process）。
2. **`@tool` 装饰器**：给普通函数打上"工具"标记，agent 按名字找工具调用。
3. **Crew vs Flow**：Crew 的形状由（模拟的）LLM 决定；`Flow` 用 `@start` / `@listen(topic)` 把步骤串成确定的事件链。
4. **记忆**：short-term、long-term（"向量"检索）、entity 三个存储，以及"第二次 kickoff 时 long-term 仍在"。

> 一句话：**Crew 让 LLM 决定形状，Flow 让代码决定形状**（程序最后打印的原话）。同时要看清代码的大量简化：agent 都是固定的字符串函数，`expected_output` 从未被使用，manager 是规则而非 LLM，记忆的"embedding"是没有语义的哈希随机向量，agent 也从不读取记忆。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tool(name)` | 装饰器工厂 | 给函数加 `tool_name`、`is_tool` 属性 | CrewAI `@tool` |
| `search` | 被装饰的函数 | 关键字匹配返回固定"搜索结果" | 工具（模拟） |
| `Agent` | dataclass | role、goal、backstory、`fn`（模拟 LLM 行为）、tools | Agent |
| `Task` | dataclass | description、expected_output、agent、context（上游任务列表） | Task |
| `SequentialCrew` | dataclass | 按声明顺序执行任务，串接输出，写记忆 | Crew + Sequential process |
| `HierarchicalCrew` | dataclass | manager 每轮挑一个专家，直到返回 `"done"` 或步数用尽 | Crew + Hierarchical process |
| `Flow` | 类 | `start` / `listen(topic)` 装饰器注册步骤；`kickoff` 按 topic 链执行 | CrewAI Flow |
| `Memory` | 类 | short-term 列表、long-term（文本 + 向量）、entity 字典；`recall_long_term` 余弦排序 | 记忆 |
| `_researcher` / `_writer` / `_editor` / `_manager` | 函数 | 模拟各角色的"LLM 输出" | 模拟 LLM |
| `build_agents` | 函数 | 构造三个 Agent | 团队定义 |
| `main` | 函数 | 5 个演示：Sequential、Hierarchical、Flow、记忆检索、第二次 kickoff | 入口 |

数据流（Sequential）：`{"topic": ...}` → researcher（调用 `search` 工具）→ 输出作为 `prior` → writer（取前 60 字符）→ editor（取前 60 字符）→ 每步写 short-term 与 long-term。

---

## 3. 逐段精讲

### 3.1 `tool` 装饰器与 `search`

```python
def tool(name: str):
    def decorator(fn):
        fn.tool_name = name  # type: ignore[attr-defined]
        fn.is_tool = True  # type: ignore[attr-defined]
        return fn
    return decorator


@tool("Search the web")
def search(query: str) -> str:
    """Return top results for the query."""
    ...
```

- 这是**带参数的装饰器**：`tool("Search the web")` 先返回 `decorator`，再用它装饰 `search`。等价于 `search = tool("Search the web")(search)`。
- 装饰器只给函数对象挂了两个属性，函数本身原样返回。Python 函数是对象，可以随意添加属性；`# type: ignore` 是告诉类型检查器"我知道这样做不规范"。
- 讲义说 CrewAI 的 `@tool`"Signature is the schema; docstring is the description the LLM sees"。这里**没有**生成 schema，也没有使用 docstring——真实实现会用 `inspect.signature` 读参数、用 `fn.__doc__` 作描述，打包成 LLM 可读的工具定义。
- `search` 的"搜索结果"是关键字匹配的固定字符串：`"agent engineering"` 与 `"crewai"` 各有一组，否则返回 generic。

### 3.2 `Agent` 与 `Task`

```python
@dataclass
class Agent:
    role: str
    goal: str
    backstory: str
    fn: Callable[..., str]
    tools: list[Callable[..., str]] = field(default_factory=list)


@dataclass
class Task:
    description: str
    expected_output: str
    agent: Agent
    context: list["Task"] = field(default_factory=list)
```

- 字段与 CrewAI 的表面一致，多了一个 `fn`：用 Python 函数模拟"这个角色的 LLM 会怎么回答"。真实系统中，role / goal / backstory 会被拼进 system prompt，`fn` 的位置是一次 LLM 调用。
- ⚠️ 在本代码中 `goal`、`backstory`、`Task.description`、`Task.expected_output` **全都没有被读取**。讲义强调"`expected_output` is the contract"、"The backstory is load-bearing"，但这里它们只是装饰性的字符串。这正好可以拿来理解讲义的 pitfall："Skipping `expected_output`. Without a contract per task, downstream tasks pick up whatever the LLM produced."
- `context: list["Task"]`：引用自身类型需要加引号（前向引用）。
- 讲义提到的 `output_pydantic` 字段没有实现（测验 Q12 给出了标准库版的"结构化输出 + 重试"）。

### 3.3 `SequentialCrew.kickoff`：按顺序串接输出

```python
    def kickoff(self, inputs):
        outputs = []
        prior = inputs.get("topic", "")
        by_task = {}
        for task in self.tasks:
            if task.context:
                joined = "\n\n".join(
                    by_task[id(t)] for t in task.context if id(t) in by_task
                )
                agent_input = joined or prior
            else:
                agent_input = prior
            out = task.agent.fn(agent_input, task.agent.tools, self.memory)
            outputs.append(f"[{task.agent.role}] {out}")
            by_task[id(task)] = out
            prior = out
            if self.memory is not None:
                self.memory.write_short_term(task.agent.role, out)
                self.memory.write_long_term(task.agent.role, out)
        return outputs
```

- 默认把**上一个任务的输出**（`prior`）作为下一个任务的输入，这就是讲义说的"Output of task N is available as `context` to task N+1"。
- 声明了 `context` 时，把所有上游任务的输出用空行拼接作为输入；用 `id(t)`（对象身份）作为字典键，因为 dataclass 默认不可哈希。
- ⚠️ `context` 引用了**还没执行**的任务时，`if id(t) in by_task` 会把它静默跳过，拼接为空字符串后回落到 `prior`——配置错误不会报错（实测：把 editor 任务放在 researcher 之前，editor 拿到的是原始 topic）。
- ⚠️ 默认链式传递与角色无关：任务顺序一乱，researcher 也会把 editor 的输出当成"主题"去搜索（实测）。
- `agents` 字段存了但没有使用：执行完全由 `tasks` 驱动，这与讲义"Tasks reference agents. The Crew sequences tasks"一致。
- 每个任务都写 short-term 和 long-term 记忆，没有任何筛选——即讲义 pitfall "Memory always-on"。

### 3.4 `HierarchicalCrew.kickoff` 与 `_manager`

```python
    def kickoff(self, topic):
        outputs = []
        current = topic
        done = set()
        for _ in range(self.max_steps):
            pick = self.manager.fn(done, [], None)
            if pick == "done":
                outputs.append("[manager] done")
                break
            specialist = self.specialists.get(pick)
            if specialist is None:
                outputs.append(f"[manager] unknown pick {pick!r}")
                break
            out = specialist.fn(current, specialist.tools, self.memory)
            outputs.append(f"[manager -> {specialist.role}] {out}")
            current = out
            done.add(pick)
            if self.memory is not None:
                self.memory.write_short_term(specialist.role, out)
        return outputs


def _manager(prior, tools, memory):
    done = prior if isinstance(prior, set) else set()
    if "researcher" not in done:
        return "researcher"
    if "writer" not in done:
        return "writer"
    if "editor" not in done:
        return "editor"
    return "done"
```

- 每轮先问 manager 选谁，再让专家干活；manager 返回 `"done"` 时结束，返回未知名字时记录并结束（这是对 LLM 输出做白名单校验的雏形）。
- **调用次数**：manager 4 次（3 次派活 + 1 次判断 done）+ 专家 3 次 = 7 次，Sequential 只要 3 次（已实测）。这就是讲义的"manager-LLM token tax"。注意讲义自己的表述不一致："six LLM calls instead of five"与"adds a manager LLM call before every specialist call"（按后者 5 个任务应是 10～11 次）。
- ⚠️ manager 只看到"已派过的角色集合"`done`，看不到任何专家的输出，所以它不可能做讲义所说的"refuse or re-route"——本质是按固定顺序派活，与 Sequential 等价。
- ⚠️ 不使用 `Task` 对象：没有 description、expected_output，专家之间也没有 context 声明。
- ⚠️ 只写 short-term，不写 long-term（与 Sequential、Flow 不一致）。
- ⚠️ 步数用尽时静默结束：`max_steps=3` 时输出里没有 `"[manager] done"`，也没有任何警告（实测）。
- `self.manager.fn(done, [], None)`：复用了 agent 函数的三参数签名，但第一个参数这里传的是集合而不是文本，所以 `_manager` 里要用 `isinstance(prior, set)` 判断——同一个签名承载两种含义，可读性较差。

### 3.5 `Flow`：事件驱动的确定性流程

```python
    def listen(self, topic):
        def decorator(fn):
            self.listeners[topic] = fn
            return fn
        return decorator

    def kickoff(self, payload):
        if self.start_step is None:
            return []
        self.trace = []
        topic, out = self.start_step(payload)
        self.trace.append(("start", topic, out))
        while topic in self.listeners:
            step = self.listeners[topic]
            result = step(out)
            if result is None:
                break
            topic, out = result
            self.trace.append((step.__name__, topic, out))
        return self.trace
```

- `start` 是普通装饰器（直接接收函数）；`listen(topic)` 是带参数的装饰器工厂。两者都把函数登记到 `self` 上，再原样返回函数——所以 `main()` 里的 `@flow.start def kickoff(...)` 定义的函数仍然可以单独调用、单独测试，这正是 Flow"每一步都是普通 Python"的好处。
- 每个步骤返回 `(下一个 topic, 输出)`；`kickoff` 用 `while` 循环沿 topic 链执行，直到没有监听者或某一步返回 `None`。
- trace 用 `step.__name__` 记录步骤名，所以输出里能看到 `on_researched`、`on_drafted`。
- ⚠️ `self.listeners[topic] = fn`：同一个 topic 只能有一个监听者，后注册的会**静默覆盖**先注册的，无法扇出（实测）。
- ⚠️ 没有步数上限：topic 成环（A → B → A）就会无限循环。skill 文件要求 Flow 的步骤构成 DAG，但代码没有检查。
- ⚠️ 返回 `None` 的终止步骤不进 trace：demo 中的 `on_edited` 执行了，但 trace 只有三行。
- 每次 `kickoff` 都重置 `self.trace`。
- 测验 Q11 给出了支持多监听者、带 `max_steps`、记录终止步骤的改写版。

### 3.6 `Memory`：三个存储与"哈希向量"

```python
    def _embed(self, text):
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "little")
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(self.dim)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def recall_long_term(self, query, k=2):
        if not self.long_term:
            return []
        q = self._embed(query)
        scored = [(r, v, float(np.dot(q, e))) for r, v, e in self.long_term]
        scored.sort(key=lambda row: row[2], reverse=True)
        return scored[:k]
```

- `_embed`：用文本的 SHA-256 前 8 字节作为随机数种子，生成一个 16 维标准正态向量并归一化。好处是**确定**（同一文本永远得到同一向量），可以离线复现。
- `recall_long_term`：单位向量的点积就是余弦相似度，按分数降序取前 k 条。
- ⚠️ **没有语义**：哈希对输入极其敏感，`"brief"` 与 `"brief."` 的余弦只有 0.319；不同文本之间的分数相当于随机数（16 维时标准差约 0.24）。实测查询 `"final brief"` 时，以 "final brief" 开头的 editor 输出反而排在最后（−0.071）。只有查询与某条记录**完全相同**时余弦才是 1.0。讲义"mocked similarity uses numpy"的"mocked"要理解为"排序结果没有意义"。
- ⚠️ 类 docstring 写"Four-store memory matching CrewAI's short, long, entity, contextual"，实际只有三个存储，没有 contextual；entity 只有写入方法 `write_entity`，没有读取方法，demo 也从未使用。
- ⚠️ 没有去重：Sequential 与 Flow 写入了完全相同的 editor 输出，所以 `recall_long_term("brief")` 返回两条一模一样的记录。
- ⚠️ 所有 agent 函数都接收 `memory` 参数却从不读取，记忆对输出没有任何影响。
- `reset_short_term` 只在第二次 kickoff 前调用一次；第一部分的 Sequential、Hierarchical、Flow 共向 short-term 写了 9 条（实测 Sequential 后 3 条、Hierarchical 后 6 条）。

### 3.7 模拟的角色函数

```python
def _researcher(prior, tools, memory):
    topic = prior if isinstance(prior, str) else ""
    search_fn = next(
        (t for t in tools if getattr(t, "is_tool", False)
         and "search" in getattr(t, "tool_name", "").lower()),
        None,
    )
    sources = search_fn(topic) if search_fn else "src1, src2, src3"
    return f"3 sources on {topic}: {sources}"


def _writer(prior, tools, memory):
    text = prior if isinstance(prior, str) else ""
    return f"draft (3 paragraphs) from sources: {text[:60]}"
```

- researcher 在自己的工具列表里找"名字含 search 的工具"：`next(生成器, None)` 取第一个满足条件的元素，找不到返回 `None`；`getattr(t, "is_tool", False)` 在属性不存在时返回默认值，避免 `AttributeError`。
- 按名字子串找工具很脆弱：改名为 "Web lookup" 就找不到了。真实 CrewAI 中由 LLM 根据工具描述决定调用哪个工具。
- writer / editor 只截取上游输出的前 60 个字符拼进自己的输出——所以 trace 里能看到输出一层套一层地被截断。所谓 "3 paragraphs"、"800 words" 只是写在字符串里的说法，从未被生成或校验：这恰好演示了讲义的"brittle handoffs"（输出契约只存在于文字描述中）。

### 3.8 `main`：五个演示

| 演示 | 内容 | 观察点 |
|------|------|-------|
| 1. SequentialCrew | 三个 Task 按顺序执行 | 输出逐级嵌套、被截断 |
| 2. HierarchicalCrew | manager 依次派 researcher、writer、editor，然后 done | 结果与 Sequential 相同，但多了 4 次 manager 调用 |
| 3. Flow | `kickoff` → `on_researched` → `on_drafted`（`on_edited` 返回 None） | 步骤与 topic 固定，可重放 |
| 4. `recall_long_term('brief')` | 取前 2 条 | 两条完全相同的 editor 记录 |
| 5. 第二次 Sequential | 先清空 short-term | long-term 9 条、short-term 3 条 |

`main()` 中定义 Flow 步骤时用到了**闭包**：`kickoff`、`on_researched` 等内部函数直接使用外层的 `memory` 变量。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| agent 行为用固定函数模拟 | 离线、确定、无需 API key | 体现不了 LLM 的随机性；backstory、goal 不起作用 |
| `@tool` 只打标记 | 展示装饰器形状 | 没有 schema 与描述；真实实现从签名与 docstring 生成工具定义 |
| 默认把上一输出当输入 | 最简单的 Sequential 语义 | 不读 `expected_output`；`context` 配置错误被静默忽略 |
| manager 是规则函数 | 结果可预测 | 看不到专家输出，不能拒绝或改派；真实 manager 是带上下文的 LLM 调用 |
| Flow 用 dict 登记监听者 | 代码短 | 一个 topic 只能一个监听者；无环检测、无步数上限 |
| 哈希随机向量做 embedding | 无需模型、确定 | 没有语义，检索排序是随机的；生产用 embedding 模型 + 向量库 |
| 每步都写 long-term | 演示"跨运行保留" | 重复写入、库膨胀、检索变吵；应只写持久事实并去重 |
| 输出截断到 60 字符 | trace 好读 | 信息在 handoff 中丢失；真实系统应传结构化对象 |
| 依赖 numpy | 方便向量运算 | 与讲义"stdlib"的说法不符；16 维向量用纯 Python 也能算 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 带参数的装饰器 | `@tool("Search the web")`、`@flow.listen("researched")` | 外层函数接收参数并返回真正的装饰器 |
| 方法作为装饰器 | `@flow.start` | 绑定方法也是可调用对象，可以直接当装饰器用 |
| 给函数对象加属性 | `fn.tool_name = name` | 函数是对象，可以挂任意属性 |
| `# type: ignore[...]` | `fn.is_tool = True  # type: ignore[attr-defined]` | 让类型检查器忽略这一行的特定错误 |
| `Callable[..., str]` | `fn: Callable[..., str]` | 参数任意、返回 str 的可调用对象 |
| `@dataclass` + `field(default_factory=list)` | `tools: list[...] = field(default_factory=list)` | 可变默认值必须用工厂 |
| 前向引用字符串 | `context: list["Task"]`、`memory: "Memory \| None"` | 引用尚未定义的类型 |
| `id(obj)` | `by_task[id(task)] = out` | 对象身份标识，可作为字典键 |
| `str.join` + 生成器 | `"\n\n".join(by_task[id(t)] for t in task.context if ...)` | 用分隔符拼接可迭代对象 |
| `or` 回落 | `agent_input = joined or prior` | 空字符串为假值，回落到 `prior` |
| `next(生成器, 默认值)` | `next((t for t in tools if ...), None)` | 取第一个满足条件的元素 |
| `getattr(obj, name, default)` | `getattr(t, "is_tool", False)` | 属性不存在时返回默认值 |
| `isinstance` | `prior if isinstance(prior, set) else set()` | 运行时类型判断 |
| `fn.__name__` | `step.__name__` | 函数名，用于 trace |
| 元组解包 | `topic, out = result` | 一次取出多个返回值 |
| `hashlib.sha256(...).digest()[:8]` | `_embed` | 取哈希的前 8 个字节 |
| `int.from_bytes(b, "little")` | `_embed` | 字节串转整数（小端序） |
| `np.random.default_rng(seed)` | `_embed` | NumPy 新式随机数生成器，固定种子可复现 |
| `np.linalg.norm` / `np.dot` | 归一化与点积 | 单位向量的点积即余弦相似度 |
| `list.sort(key=..., reverse=True)` | `scored.sort(key=lambda row: row[2], reverse=True)` | 原地按分数降序 |
| f-string 格式符 | `{score:+.3f}`、`{pick!r}`、`{output[:60]}` | 显示正负号的 3 位小数；repr；表达式切片 |
| 闭包 | `main()` 中 Flow 步骤使用外层 `memory` | 内层函数引用外层变量 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，瞬间完成；部分长行截断）：

```text
1. SequentialCrew (researcher -> writer -> editor)
  [researcher] 3 sources on agent engineering 2026: src1: agent loop, src2: tool use, src3: memory
  [writer] draft (3 paragraphs) from sources: 3 sources on agent engineering 2026: src1: agent loop, src2:
  [editor] final brief (tightened, 800 words): draft (3 paragraphs) from sources: 3 sources on agent engine

2. HierarchicalCrew (manager routes)
  [manager -> researcher] 3 sources on agent engineering 2026: ...
  [manager -> writer] draft (3 paragraphs) from sources: ...
  [manager -> editor] final brief (tightened, 800 words): ...
  [manager] done

3. Flow (deterministic, event-driven)
  [start] topic='researched' out=3 sources on agent engineering 2026: src1: agent loop, src2:
  [on_researched] topic='drafted' out=draft (3 paragraphs) from sources: 3 sources on agent engine
  [on_drafted] topic='edited' out=final brief (tightened, 800 words): draft (3 paragraphs) fro

4. Memory: recall_long_term('brief')
  [editor] score=+0.255 value=final brief (tightened, 800 words): draft (3 parag
  [editor] score=+0.255 value=final brief (tightened, 800 words): draft (3 parag

5. Second kickoff (long-term memory survives)
  long_term entries: 9
  short_term entries (this run): 3
```

逐项解读：

- **Sequential**：researcher 调用 `search`，命中 `"agent engineering"` 这组固定结果；writer、editor 各截取上游前 60 个字符，形成层层嵌套。
- **Hierarchical**：结果与 Sequential 完全相同——因为 manager 的规则就是按固定顺序派活；区别只是多了 manager 的 4 次调用和最后的 `done`。
- **Flow**：三行 trace，topic 依次为 `researched`、`drafted`、`edited`；`on_edited` 返回 `None`，没有进入 trace。Flow 的输出与 Crew 一致，但它的步骤与顺序由代码固定。
- **记忆检索**：两条相同记录分别来自 Sequential 与 Flow 写入的同一字符串；+0.255 只是两个哈希随机向量的点积，与 "brief" 的语义无关。
- **第二次 kickoff**：long-term 从 6 增加到 9（Hierarchical 不写 long-term），short-term 清空后只剩本次的 3 条。第二次运行的输出与第一次完全相同——记忆"存活"了，但没有被使用。

额外的探针实验（导入模块后调用，不修改源码）：

| 实验 | 结果 |
|------|------|
| 包装计数器统计 Hierarchical 调用 | manager 4 次、专家 3 次 |
| `HierarchicalCrew(max_steps=3)` | 三个专家都执行，但没有 `[manager] done`，无警告 |
| `recall_long_term("final brief")` | editor 排最后（−0.071） |
| 查询与 editor 输出完全相同 | editor 得分 1.0 |
| `"brief"` 与 `"brief."` 的向量余弦 | 0.319 |
| editor 任务 `context=[researcher 任务]` 但排在前面 | context 被静默忽略，editor 拿到原始 topic |
| 同一 topic 注册两个监听者 | 只执行后注册的那个 |

---

## 7. 动手改一改

1. **Sequential → Flow（讲义练习 1）**：已在 demo 第 3 部分完成；请再写一个"重放测试"：同一 payload 跑两次 Flow，断言 trace 完全相同；对 Hierarchical 换成随机选择的 manager 再做同样测试，体会可重放性的差别。
2. **实体记忆（讲义练习 2）**：给 `Memory` 加 `recall_entity`，让 writer 按客户套餐调整语气；long-term 写入去重（参考测验 Q10）。
3. **会拒绝的 manager（讲义练习 3）**：manager 看到全部输出，writer 不足 3 段就打回重写，并让 writer 重做时读取 researcher 的输出（参考测验 Q9）。
4. **`BaseTool` 风格的工具（讲义练习 4）**：写一个 `SearchTool` 类，持有缓存字典、带 `args_schema`（可用 dataclass 表示）和重试逻辑；与 `@tool` 版本对比 trace。
5. **结构化输出与重试（讲义练习 5）**：为 editor 定义 `Brief(title, summary, sections)`，第一次故意输出截断的 JSON，验证带错误提示的重试（参考测验 Q12）。
6. **修 Flow 与真实 embedding**：让 `Flow` 支持多监听者与 `max_steps`（参考测验 Q11）；把 `_embed` 换成简单的词袋向量（按词计数后归一化），观察 `"final brief"` 的检索排序变得合理。

---

## 8. 常见坑

- **以为写了 `expected_output` 就有契约**：契约必须被传给 agent 并在输出端校验，否则只是注释。
- **Hierarchical 的 manager 看不到输出**：那就只是更贵的 Sequential；确认 manager 的输入里有先前任务的结果。
- **步数用尽静默结束**：要在 trace 中明确区分"done"和"max_steps reached"。
- **context 引用顺序错误**：引用尚未执行的任务时，本实现不报错，下游拿到错误输入。
- **哈希向量冒充语义检索**：确定性 ≠ 语义；用它做演示可以，用它评估"记忆是否有用"会得出错误结论。
- **记忆一直开着且不去重**：同一内容反复写入，检索结果被重复项占满。
- **同一 topic 注册多个监听者**：dict 实现会静默覆盖。
- **Flow 中出现环**：没有步数上限时会无限循环。
- **把带副作用的工具交给 Crew**：讲义："POST, DELETE, payment belong in a Flow step, never a Crew tool."
- **backstory 写太长**：讲义建议 200 词以内；五个 agent 各 2000 词会在第一次工具调用前就耗尽上下文。
