# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 17 节 将 Harness 封装为库：Subagents 与会话存储 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`typing`），无需 API key、无需安装 `claude-agent-sdk`

---

## 1. 这份代码在考察什么

这份 218 行的代码用标准库模仿 Claude Agent SDK 的 harness "形状"。它不调用任何模型，工具调用序列是预先写好的脚本，目的是把 harness 的四个基础设施部件单独拎出来看：

1. **工具注册与分发**：`ToolRegistry` 按名称注册工具，`Harness._dispatch` 统一执行并把异常转成字符串结果。
2. **生命周期 hooks**：`pre_tool_use`、`post_tool_use`、`session_start`、`session_end` 四类回调在固定时机触发（讲义列出的 `UserPromptSubmit`、`PreCompact`、`Stop`、`Notification` 未实现）。
3. **Session store**：`append`、`load`、`list_sessions`、`delete`（带级联）、`list_subkeys`，与讲义列出的接口一一对应。
4. **Subagent 与上下文隔离**：每个 subagent 有自己的 session ID（`父ID.subNN`）和自己的 `context_tokens` 计数，orchestrator 的计数不受影响。

> 一句话：**把"Claude Code 的循环做成库"拆成工具、hook、会话、子 agent 四块积木**。阅读时也要看清它的简化：subagent 其实是顺序执行的，结果没有回传给 orchestrator，级联删除只删一层，hook 不能拒绝工具调用。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Tool` | dataclass | 名称、描述、可调用对象 | 工具定义 |
| `ToolRegistry` | 类 | `register` / `get` / `names`，内部是 `dict[str, Tool]` | 内置工具 + 自定义工具注册 |
| `Hooks` | dataclass | 四个回调列表 | Lifecycle hooks |
| `Turn` | dataclass | 一条消息：`role` + `content` | 会话中的一轮 |
| `SessionStore` | 类 | 内存中的会话表 + 父→子索引 | Session store |
| `AgentRun` | dataclass | 单次运行的结果：session ID、上下文词数、工具调用记录、输出 | 运行结果 |
| `Harness` | 类 | `_dispatch`（执行工具 + hooks）、`run_agent`（跑一个 agent）、`spawn_subagents`（派生子 agent） | Harness / agent loop |
| `_read_file_demo` / `_list_dir_demo` | 函数 | 假工具，返回固定格式字符串 | 内置工具的替身 |
| `main` | 函数 | 注册工具与 hooks → orchestrator 运行 → 派生 3 个 subagent → 打印 store 与 hook 日志 → 级联删除 | 演示 |

数据流：`main` 构造 `ToolRegistry` + `Hooks` + `SessionStore` → `Harness.run_agent(orchestrator)` → `Harness.spawn_subagents` 循环调用 `run_agent(sub, parent_session=...)` → 每次 `run_agent`：`session_start` → 记 user 轮 → 逐个 `_dispatch`（pre hook → 工具 → post hook）并记 tool 轮 → 记 assistant 轮 → `session_end`。

---

## 3. 逐段精讲

### 3.1 工具与注册表

```python
@dataclass
class Tool:
    name: str
    description: str
    fn: Callable[..., str]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)
```

- `Callable[..., str]`：任意参数、返回字符串的函数。
- `_tools` 以下划线开头，表示"内部使用"；外部通过 `get` 访问，找不到返回 `None`。
- 同名再次 `register` 会**静默覆盖**，没有冲突检查。
- `names()` 返回排序后的工具名（`sorted(dict)` 对键排序），但 `main` 从未调用它。
- ⚠️ 讲义 "Build It" 说注册了内置的 `read_file`、`write_file`、`list_dir`，实际 `main` 只注册了 `read_file` 和 `list_dir`，**没有 `write_file`**（讲义练习 2 正好要对 `write_file` 限流）。
- `description` 在代码里没有被使用；在真实 SDK 中它会进入工具 schema，告诉模型何时使用该工具。

### 3.2 Hooks 与 Turn

```python
@dataclass
class Hooks:
    pre_tool_use: list[Callable[[str, dict[str, Any]], None]] = field(default_factory=list)
    post_tool_use: list[Callable[[str, str], None]] = field(default_factory=list)
    session_start: list[Callable[[str], None]] = field(default_factory=list)
    session_end: list[Callable[[str], None]] = field(default_factory=list)
```

- 每类 hook 是一个**列表**，可以注册多个回调，按顺序执行。
- 签名都返回 `None`：hook 只能"看"，不能"改"或"拒绝"。讲义说 `PreToolUse` 用于 "gate or audit tool calls"，本代码只实现了 audit。
- ⚠️ `pre_tool_use` 只收到 `(tool_name, args)`，**没有 session_id**——无法实现"按会话限流"这类策略（测验 Q11）。

`Turn(role, content)` 是会话中一条消息，`role` 取 `"user"`、`"tool"`、`"assistant"`。

### 3.3 SessionStore：五个接口 + 父子索引

```python
class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, list[Turn]] = {}
        self._subkeys: dict[str, list[str]] = {}

    def append(self, session_id: str, turn: Turn) -> None:
        self._sessions.setdefault(session_id, []).append(turn)

    def load(self, session_id: str) -> list[Turn]:
        return list(self._sessions.get(session_id, []))
```

- `setdefault(key, [])`：键不存在时先放入空列表再返回，一行完成"没有就创建，然后追加"。
- `load` 返回 `list(...)` **浅拷贝**：调用方修改返回的列表不会影响存储；但列表里的 `Turn` 对象仍是同一个（浅拷贝的含义）。
- 两张表：`_sessions` 存消息，`_subkeys` 存"父会话 → 子会话 ID 列表"。

```python
    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        for sub in self._subkeys.get(session_id, []):
            self._sessions.pop(sub, None)
        self._subkeys.pop(session_id, None)

    def list_subkeys(self, session_id: str) -> list[str]:
        return list(self._subkeys.get(session_id, []))

    def link_sub(self, parent: str, sub: str) -> None:
        self._subkeys.setdefault(parent, []).append(sub)
```

- `pop(key, None)`：删除并返回，键不存在时返回默认值而不报 `KeyError`。
- ⚠️ **级联只有一层**：删除父会话时只删直接子会话，子会话自己的子会话（孙级）及其 `_subkeys` 索引都会残留。我们实际构造 `x → x.sub01 → x.sub01.sub02` 后 `delete("x")`，剩下 `['x.sub01.sub02']` 和 `{'x.sub01': ['x.sub01.sub02']}`。修复：递归删除（测验 Q9）。
- `link_sub` 不是讲义列出的接口，是 harness 内部用来建立父子关系的辅助方法；重复调用会产生重复项。
- 全部在内存里，进程退出即丢失；讲义说的是 "session persistence"，生产需落到 SQLite/数据库。`--session-mirror` 也没有实现。

### 3.4 `Harness._dispatch`：工具执行的唯一入口

```python
    def _dispatch(self, tool_name: str, args: dict[str, Any]) -> str:
        for hook in self.hooks.pre_tool_use:
            hook(tool_name, args)
        tool = self.tools.get(tool_name)
        if tool is None:
            result = f"error: unknown tool {tool_name!r}"
        else:
            try:
                result = tool.fn(**args)
            except Exception as e:
                result = f"error: {type(e).__name__}: {e}"
        for hook in self.hooks.post_tool_use:
            hook(tool_name, result)
        return result
```

- 所有工具调用都经过这里，hooks 才能做到"横切"（cross-cutting）——这正是讲义说的 hooks 的价值。
- 未知工具与工具内部异常都被转成 `"error: ..."` 字符串，作为工具结果交回，**不会让 agent 崩溃**。我们实测：调用不存在的 `nope` 得到 `"error: unknown tool 'nope'"`；除零得到 `"error: ZeroDivisionError: division by zero"`；漏传参数得到 `"error: TypeError: <lambda>() missing 1 required positional argument: 'path'"`。
- `type(e).__name__` 取异常类名；`{tool_name!r}` 用 `repr` 给名字加引号。
- 注意 pre hook 在"查找工具"之前触发，所以即使是未知工具，pre/post hook 也都会执行（审计上可以看到模型尝试调用了不存在的工具，这是好事）。
- ⚠️ `try` 只包住了 `tool.fn(**args)`，hook 抛出的异常不会被捕获：pre hook 抛异常会直接中断整个 `run_agent`，该会话缺少 assistant 轮次，`session_end` 也不会触发。

### 3.5 `Harness.run_agent`：一次 agent 运行

```python
    def run_agent(self, session_id: str, prompt: str,
                  tool_calls: list[tuple[str, dict[str, Any]]],
                  parent_session: str | None = None) -> AgentRun:
        for hook in self.hooks.session_start:
            hook(session_id)
        if parent_session is not None:
            self.store.link_sub(parent_session, session_id)

        run = AgentRun(session_id=session_id)
        self.store.append(session_id, Turn("user", prompt))
        run.context_tokens += len(prompt.split())

        for tool_name, args in tool_calls:
            result = self._dispatch(tool_name, args)
            run.tool_calls.append((tool_name, args, result))
            self.store.append(session_id, Turn("tool", f"{tool_name}: {result}"))
            run.context_tokens += len(result.split())

        output = f"processed {len(tool_calls)} tools; session={session_id}"
        run.output = output
        self.store.append(session_id, Turn("assistant", output))
        run.context_tokens += len(output.split())

        for hook in self.hooks.session_end:
            hook(session_id)
        return run
```

- **工具调用是参数传入的脚本**：`tool_calls` 由调用方事先决定，没有模型根据上一个结果决定下一步——这是本代码最大的简化。真实 harness 的循环是"模型输出 tool_use → 执行 → 结果回填 → 再问模型"。
- **上下文计数**：`len(text.split())` 按空白切词，是 token 数的粗略替身。orchestrator 的 11 = 4（prompt）+ 3（工具结果）+ 4（输出），subagent 的 12 = 3 + 5 + 4。
- 每一步都 `append` 到 session store：user → tool → assistant，因此每个会话 `turns=3`。
- `parent_session` 不为 `None` 时登记父子关系，这就是 `list_subkeys` 的数据来源。
- 类型注解 `str | None` 表示"字符串或 None"（Python 3.10+ 语法，这里因 `from __future__ import annotations` 在更早版本也能解析）。
- 输出文本 `"processed 1 tools"` 是模板字符串，没有处理单复数。

### 3.6 `spawn_subagents`：子会话 ID 与"隔离"

```python
    def spawn_subagents(self, parent_session: str,
                        tasks: list[tuple[str, list[tuple[str, dict[str, Any]]]]]
                        ) -> list[AgentRun]:
        runs: list[AgentRun] = []
        for prompt, tool_calls in tasks:
            self._sub_counter += 1
            sub_session = f"{parent_session}.sub{self._sub_counter:02d}"
            run = self.run_agent(sub_session, prompt, tool_calls,
                                 parent_session=parent_session)
            runs.append(run)
        return runs
```

- 每个 subagent 拿到独立的 session ID，例如 `session_main.sub01`；`{...:02d}` 把计数器补零到两位。
- 每个 subagent 有自己的 `AgentRun` 和 `context_tokens`——"上下文隔离"在这里体现为"各算各的"。
- ⚠️ **不是并行**：讲义说 "spawns 3 subagents in parallel"，实际是 `for` 循环顺序执行。改成线程池即可并行（测验 Q10），但要在主线程里先分配 ID，否则 `_sub_counter += 1` 会有竞态。
- ⚠️ `_sub_counter` 是 Harness 级全局计数，不按父会话归零：先给 `p1` 派生一个、再给 `p2` 派生一个，得到 `p1.sub01`、`p2.sub02`。
- ⚠️ **结果没有回到 orchestrator**：返回的 `runs` 只在 `main` 里打印，没有写进父会话，也没加到父的 `context_tokens`。

### 3.7 `main()`：演示流程

```python
    hook_log: list[str] = []
    hooks = Hooks(
        pre_tool_use=[
            lambda n, a: hook_log.append(f"pre[{n}]: {a}")
        ],
        post_tool_use=[
            lambda n, r: hook_log.append(f"post[{n}]: {r[:30]}")
        ],
        session_start=[lambda s: hook_log.append(f"session_start[{s}]")],
        session_end=[lambda s: hook_log.append(f"session_end[{s}]")],
    )
```

- 用 `lambda` 写一行 hook，**闭包**捕获外层的 `hook_log` 列表，所有事件都追加到同一个列表里。
- `r[:30]` 截断结果，避免审计日志过长。

```python
    orchestrator_run = harness.run_agent(
        parent,
        "review these three modules",
        [("list_dir", {"path": "/project"})],
    )
    ...
    sub_runs = harness.spawn_subagents(parent, [
        ("review module a", [("read_file", {"path": "a.py"})]),
        ...
    ])
    ...
    print(f"  orchestrator context tokens remain: "
          f"{orchestrator_run.context_tokens}")
    ...
    store.delete(parent)
    print(f"  remaining sessions: {store.list_sessions()}")
```

- orchestrator 先跑完（已触发 `session_end`），再派生 subagent。
- "remain: 11" 打印的是同一个从未被修改的整数——它说明 subagent 的 token 没有计入 orchestrator，但并没有演示"结果回传后仍然有界"。
- 两个相邻的 f-string 会被 Python 自动拼接成一个字符串（隐式字符串拼接）。
- 最后的级联删除在本例中有效，是因为只有一层子会话。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 工具调用序列预先写死 | 不需要模型即可演示 harness 部件 | 看不到真正的 agent 循环；真实 SDK 由模型逐步决定 tool_use |
| 词数代替 token 数 | 无需 tokenizer | 只是量级示意；生产用 tokenizer 或 API 返回的 usage |
| `_dispatch` 吞掉工具异常 | 工具出错不让 agent 崩溃，错误交给模型处理 | hook 异常没有兜底；应 `try/finally` 保证 `session_end` |
| hook 返回 `None` | 实现最简单 | 无法"拦截"；真实 `PreToolUse` 可以给出允许/拒绝决策 |
| hook 签名不带 session_id | 简化 | 无法做按会话的策略（限流、配额） |
| 内存 dict 存会话 | 零依赖 | 进程退出即丢；生产用 SQLite/数据库，加过期策略 |
| 一层级联删除 | 演示只有一层子会话 | 孙级会话残留；应递归删除或数据库级联 |
| subagent 顺序执行 | 输出确定、易读 | 没有并行收益；应使用线程池/asyncio 并控制并发数 |
| 子结果不回传 orchestrator | 代码最短 | "上下文隔离"只演示了一半；应回传摘要并计入父上下文 |
| 子会话 ID 用 `父.subNN` | 从 ID 即可看出层级 | 计数器全局递增；并发时需在主线程分配 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件顶部 | 注解延迟求值，`Tool \| None` 等新语法在旧版本也能解析 |
| `@dataclass` | `Tool`、`Hooks`、`Turn`、`AgentRun` | 自动生成构造函数等，适合数据容器 |
| `field(default_factory=list)` | `Hooks` 的四个列表、`AgentRun.tool_calls` | 每个实例一个新列表，避免共享可变默认值 |
| 联合类型 `X \| None` | `def get(...) -> Tool \| None`、`parent_session: str \| None = None` | 表示"可能为 None" |
| 复杂类型注解 | `list[tuple[str, list[tuple[str, dict[str, Any]]]]]` | 嵌套描述"任务列表"的结构：(prompt, [(工具名, 参数)]) |
| `Callable[..., str]` | `Tool.fn` | `...` 表示任意参数 |
| `dict.setdefault` | `self._sessions.setdefault(session_id, []).append(turn)` | 没有键就先插入默认值，并返回该值 |
| `dict.get` / `dict.pop` 带默认值 | `self._tools.get(name)`、`self._sessions.pop(sub, None)` | 键不存在时不报错 |
| `list(...)` 浅拷贝 | `return list(self._sessions.get(session_id, []))` | 返回新列表，元素仍是原对象 |
| `sorted(dict)` | `sorted(self._tools)` | 对字典的键排序 |
| `try / except Exception as e` | `_dispatch` 中 | 捕获工具中的任意异常并转成字符串 |
| `type(e).__name__` | `f"error: {type(e).__name__}: {e}"` | 取异常类名，如 `ZeroDivisionError` |
| `**kwargs` 解包 | `tool.fn(**args)` | 字典展开为关键字参数 |
| 元组解包 in for | `for tool_name, args in tool_calls:`、`for prompt, tool_calls in tasks:` | 遍历时直接拆开元组 |
| `lambda` + 闭包 | `lambda n, a: hook_log.append(...)` | 匿名函数，引用外层变量 `hook_log` |
| f-string 格式符 | `{self._sub_counter:02d}`、`{tool_name!r}`、`{r[:30]}` | 补零宽度、repr、表达式切片 |
| 隐式字符串拼接 | `f"  orchestrator context tokens remain: " f"{...}"` | 相邻字符串字面量自动连接 |
| 实例属性计数器 | `self._sub_counter += 1` | 在多次调用间保持状态 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，瞬间完成，输出确定）：

```text
======================================================================
CLAUDE AGENT SDK SHAPE — Phase 14, Lesson 17
======================================================================

orchestrator starts
  orchestrator context tokens: 11

spawn three subagents (context isolation)
  sub session_main.sub01  tokens=12  tool_calls=1
  sub session_main.sub02  tokens=12  tool_calls=1
  sub session_main.sub03  tokens=12  tool_calls=1
  orchestrator context tokens remain: 11

session store
  session_main  turns=3
  session_main.sub01  turns=3
  session_main.sub02  turns=3
  session_main.sub03  turns=3
  subkeys of session_main: ['session_main.sub01', 'session_main.sub02', 'session_main.sub03']

hooks fired
  session_start[session_main]
  pre[list_dir]: {'path': '/project'}
  post[list_dir]: [/project: 7 files]
  session_end[session_main]
  session_start[session_main.sub01]
  pre[read_file]: {'path': 'a.py'}
  post[read_file]: [content of a.py: 42 lines]
  session_end[session_main.sub01]
  session_start[session_main.sub02]
  pre[read_file]: {'path': 'b.py'}
  ... 16 hook events total

delete parent (cascades to subs)
  remaining sessions: []

subagent results return to orchestrator; orchestrator context is preserved.
```

逐项解读：

- **orchestrator 11 / subagent 12**：按空白切词计数，见 3.5。如果 orchestrator 自己读这三个文件（不用 subagent），我们实测它的计数是 23（4 + 3×5 + 4）。subagent 方案把三份文件内容分散到三个独立上下文里——这就是"隔离"的直观含义。
- **"remain: 11"**：数字没有变化，是因为子结果根本没有写回 orchestrator。最后一行 "subagent results return to orchestrator" 与代码行为不符。
- **turns=3**：每个会话依次写入 user、tool、assistant 三条。
- **subkeys**：`list_subkeys` 返回三个子会话 ID，可用来渲染子 agent 树（讲义练习 3）。
- **16 个 hook 事件**：4 次 `run_agent` × (`session_start` + `pre` + `post` + `session_end`)；只打印前 10 条。可以清楚看到顺序执行：sub01 的 `session_end` 之后才是 sub02 的 `session_start`——如果是并行，这些事件会交错。
- **删除后为空**：父会话及三个直接子会话全部删除；若存在孙级会话则会残留（见 3.3）。

---

## 7. 动手改一改

1. **（入门）** 注册讲义提到但缺失的 `write_file` 工具（写到一个 dict 里模拟文件系统），再给某个 subagent 加一次 `write_file` 调用，观察 hook 日志与 turns 的变化。
2. **（修 bug）** 把 `SessionStore.delete` 改成递归级联（测验 Q9），并写一个小测试：三层嵌套删除后 `list_sessions()` 与 `_subkeys` 都为空。
3. **（讲义练习 2）** 把 hook 签名改为 `(session_id, tool_name, args)`，实现按会话的 `write_file` 限流（每分钟 5 次，时钟可注入），拒绝时以 `"denied: ..."` 作为工具结果返回，并用 `try/finally` 保证 `session_end` 一定触发（测验 Q11）。
4. **（讲义练习 1）** 用 `ThreadPoolExecutor` 实现并行 `spawn_subagents`，并实现"20 个任务按 5 个一批"的批处理；让每个 subagent 返回一条摘要写回 orchestrator 会话，比较"每任务一个 / 每批一个 / 不用 subagent"时 orchestrator 的 `context_tokens`（测验 Q10、Q12）。
5. **（讲义练习 3）** 用 `list_subkeys` 递归打印一棵子 agent 树（缩进表示层级），并构造 3 层嵌套观察 ID 形状。
6. **（进阶，讲义练习 4）** 安装 `claude-agent-sdk`（需要 API key 与 Claude Code CLI），把本玩具移植过去：对比真实 SDK 如何注册自定义工具、如何配置 hooks 与 subagent，记录本代码"建模错了"的地方。

---

## 8. 常见坑

- **把"计数没变"当作"隔离成功"**：orchestrator 的数字不变只是因为没有回传结果。真正的检验是"回传摘要后 orchestrator 的增长量 ≪ 原始材料"。
- **以为 subagent 省 token**：原始材料只是挪到了子上下文，再加上每个 subagent 的固定开销，总 token 往往更多；小任务应批处理（讲义：over-spawn）。
- **级联删除只删一层**：嵌套 subagent 时会留下孤儿会话，造成 session bloat 与隐私风险。
- **hook 抛异常**：会中断整个运行，`session_end` 不触发，会话缺少 assistant 轮次。hook 应快速、不抛异常，拒绝应通过约定的返回值或专用异常并在 harness 中捕获。
- **hook 里做重活**：`outputs` 要求 hook 在微秒到毫秒级；耗时工作放进 subagent。
- **并行时在线程里递增计数器**：`self._sub_counter += 1` 不是原子操作，可能产生重复 ID。
- **`load` 是浅拷贝**：改列表安全，改列表里的 `Turn` 对象会影响存储内容。
- **把 `--session-mirror` 指向共享位置**：转录里有 PII，只能镜像到按用户隔离、加密的存储。
