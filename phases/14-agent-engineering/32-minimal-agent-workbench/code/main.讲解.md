# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 32 节 最小 Agent 工作台 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（可反复运行，每次推进一步） ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`）
>
> **副作用**：在 `code/workdir/` 下创建并更新 `AGENTS.md`、`agent_state.json`、`task_board.json`。想从头再来，删掉 `code/workdir/` 即可。

---

## 1. 这份代码在考察什么

讲义的论点是："最小有用工作台 = 三个文件"。这份代码把三个文件真的写到磁盘上，再用一个**单轮状态机**演示 agent 如何"读状态 → 必要时从任务板取活 → 推进一步 → 写回状态"：

1. **`AGENTS.md` 是路由器**：常量 `AGENTS_MD` 只有 13 行，指向状态文件、任务板、规则文档和验证命令。
2. **状态是系统记录**：每次运行都从 `agent_state.json` 读入、在结束时写回；第二次运行能接着第一次继续，**不依赖任何聊天历史或进程内存**。
3. **任务板是队列**：`task_board.json` 中的任务带 `status`，没有活动任务时取第一个 `todo`。
4. **可恢复性**：讲义说"Re-run it to see how the second turn picks up where the first left off"——每次运行都是一个独立进程，连续性完全来自文件。

> 一句话：**把 agent 的"记忆"从对话里搬到仓库文件里，进程可以随时死掉，工作不会丢。** 同时也要看到它的简化：改文件是假的、验证是缺的、改哪些文件是写死的。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ROOT` | 模块常量 | `code/workdir/`，三个文件的落盘目录 | 演示用"空仓库" |
| `AGENTS_MD` | 多行字符串常量 | 路由文件内容 + 完成定义 + 验证命令 | Instructions surface（路由器） |
| `AgentState` | dataclass | 活动任务、改动文件、假设、阻塞、下一步 | State surface |
| `Task` | dataclass | id、goal、owner、acceptance、status | 任务板条目 |
| `write_initial` | 函数 | 三个文件**不存在时**才写入初始内容 | 幂等初始化 |
| `load_state` / `load_board` | 函数 | JSON → dataclass | 反序列化 |
| `save_state` / `save_board` | 函数 | dataclass → JSON | 序列化、持久化 |
| `run_one_turn` | 函数 | 单轮状态机：取任务 / 推进一步 / 标记完成 | Agent loop 的一次迭代 |
| `main` | 函数 | 初始化 → 读 → 打印 → 跑一轮 → 写 → 打印 | 驱动 |

数据流：`main` → `write_initial`（仅首次）→ `load_state` + `load_board` → 打印 before → `run_one_turn` → `save_state` + `save_board` → 打印 after。下一次运行从磁盘重新读取，形成跨进程的循环。

---

## 3. 逐段精讲

### 3.1 路由文件 `AGENTS_MD`

```python
AGENTS_MD = """# AGENTS.md

This repo runs with a workbench. Read these before acting:

1. `agent_state.json` — where the last session stopped.
2. `task_board.json` — what is in flight, what is next.
3. `docs/agent-rules.md` — startup, scope, definition of done (load on demand).

Definition of done: the task referenced by `agent_state.active_task_id` has
`status == "done"` on `task_board.json` and the verification command listed in
its `acceptance` has exited 0.

Verification command: `python3 -m pytest -x`
""".lstrip()
```

- 正好覆盖讲义要求的四个指向：状态文件、任务板、更深的规则（"load on demand"）、验证命令。
- 写成后共 13 行，满足配套 skill 的 10–80 行约束。
- `.lstrip()` 去掉开头可能的空白，保证文件第一行就是标题。
- ⚠️ 引用的 `docs/agent-rules.md` **从未被创建**。用练习 4 的 lint 检查会报 `missing reference: docs/agent-rules.md`（测验 Q12 实测）。配套 skill 要求同时生成这个占位文件。
- ⚠️ 讲义建议"commands first, style last"，这里验证命令放在最后一行；对于 13 行的文件影响不大，但在真实的长文件里应放在前面。

### 3.2 两个数据类

```python
@dataclass
class AgentState:
    active_task_id: str | None
    touched_files: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_action: str = ""


@dataclass
class Task:
    id: str
    goal: str
    owner: str
    acceptance: list[str]
    status: str = "todo"
```

- `AgentState` 的五个字段一一对应讲义："the active task id, the touched files, the assumptions made, the blockers, and the next action"。
- `active_task_id: str | None`：`None` 表示"当前没有活动任务"，是状态机的第一个判断条件。
- 数组字段默认空列表而不是 `None`，符合 skill："never `null` for arrays"——读取方不必到处判空。
- `Task.status` 只有字符串约定（`todo | in_progress | done | blocked`），没有校验；`owner` 同理。
- 本文件中 `assumptions` 与 `blockers` 从未被写入，`blocked` 状态也从未出现——它们是给后续课程预留的槽位。

### 3.3 幂等初始化 `write_initial`

```python
def write_initial(state_path: Path, board_path: Path, agents_path: Path) -> None:
    if not agents_path.exists():
        agents_path.write_text(AGENTS_MD)
    if not state_path.exists():
        state_path.write_text(json.dumps(asdict(AgentState(active_task_id=None)), indent=2) + "\n")
    if not board_path.exists():
        board = [Task(id="T-001", ...), Task(id="T-002", ...)]
        board_path.write_text(json.dumps([asdict(t) for t in board], indent=2) + "\n")
```

- 每个文件都先 `exists()` 再写：**只在缺失时初始化，绝不覆盖**。这正是"重复运行能接续"的前提——如果每次都重写，第二次运行就回到原点了。
- 三个文件各自独立判断：删掉其中一个再运行，只有那个文件会被重建。例如只删 `task_board.json`，状态里却还指着 `T-001`，新任务板的 T-001 是 `todo`，`run_one_turn` 会在"有活动任务"分支里继续推进它。
- `asdict(...)` 把 dataclass 递归转成 dict，再 `json.dumps(..., indent=2)`，末尾补一个换行，方便 git diff。
- 种子任务 T-002 的 acceptance 是自然语言（"docs/api.md mentions /signup constraints"），并不是一个能"以 0 退出"的命令，与 `AGENTS.md` 的完成定义不匹配。

### 3.4 读写四件套

```python
def load_state(state_path: Path) -> AgentState:
    raw = json.loads(state_path.read_text())
    return AgentState(**raw)

def load_board(board_path: Path) -> list[Task]:
    return [Task(**t) for t in json.loads(board_path.read_text())]
```

- `AgentState(**raw)`：把字典按键名展开成关键字参数。这让 JSON 与 dataclass 字段**强绑定**：
  - JSON 多一个键（如练习 1 的 `last_run`）→ `TypeError: unexpected keyword argument`（已实测）；
  - JSON 少一个**无默认值**的键 → `TypeError: missing ... argument`。
- 没有 try/except：JSON 损坏（例如写到一半进程被杀）会让程序直接崩溃。
- `save_*` 用 `write_text` 直接覆盖，不是原子写入；且先写 state 再写 board，两次写之间崩溃会造成两文件不一致。生产中应"写临时文件 + `os.replace`"。

### 3.5 状态机 `run_one_turn`

```python
def run_one_turn(state, board):
    if state.active_task_id is None:
        nxt = next((t for t in board if t.status == "todo"), None)
        if nxt is None:
            state.next_action = "no work on the board, idle"
            return state, board
        nxt.status = "in_progress"
        state.active_task_id = nxt.id
        state.next_action = f"start work on {nxt.id}: {nxt.goal}"
        return state, board

    active = next((t for t in board if t.id == state.active_task_id), None)
    if active is None:
        state.active_task_id = None
        state.next_action = f"active task missing from board; resetting and picking new work"
        return state, board
    if "app.py" not in state.touched_files:
        state.touched_files.append("app.py")
        state.next_action = f"add test for {active.id} acceptance"
        return state, board
    if "test_app.py" not in state.touched_files:
        state.touched_files.append("test_app.py")
        state.next_action = f"run verification command for {active.id}"
        return state, board

    active.status = "done"
    state.active_task_id = None
    state.touched_files = []
    state.next_action = "pick next task from board"
    return state, board
```

可以画成一张状态转移表（每次运行只走一行，然后 `return`）：

| 条件 | 动作 | 写入的 `next_action` |
|------|------|---------------------|
| 无活动任务，板上有 `todo` | 取第一个 `todo` → `in_progress` | `start work on T-xxx: ...` |
| 无活动任务，板上无 `todo` | 什么也不做 | `no work on the board, idle` |
| 活动任务在板上找不到 | 清空活动任务 | `active task missing from board; ...` |
| `app.py` 未改 | `touched_files += app.py` | `add test for T-xxx acceptance` |
| `test_app.py` 未改 | `touched_files += test_app.py` | `run verification command for T-xxx` |
| 两个都改了 | 任务 → `done`，清空 active 与 touched | `pick next task from board` |

要点：

- **"一轮一步、立即返回"**：每个分支末尾都 `return`，所以每次运行只推进一个动作。这模拟了"会话随时可能结束"——即使每轮之后进程退出，状态也完整保存在文件里。
- `next((生成器), None)`：取第一个满足条件的元素，找不到返回默认值 `None`，避免 `StopIteration`。
- **防御分支**："active task missing from board" 处理了状态与任务板不一致的情况（例如有人手工删除了任务），选择"重置后重新取活"，而不是崩溃。
- `nxt.status = "in_progress"` 直接修改了 `board` 列表里的对象（引用语义），所以返回 `board` 时修改已经在里面了。
- ⚠️ **"改文件"是假的**：只是往 `touched_files` 里追加文件名，磁盘上并没有 `app.py`。讲义 Build It 第 3 步"Touches a single file inside scope"在代码里只是记账。
- ⚠️ **改哪些文件是写死的**：任何任务都是 `app.py` → `test_app.py`，包括"写文档"的 T-002（测验 Q7）。
- ⚠️ **没有验证就标记 done**：`next_action` 写着 "run verification command"，下一轮却直接 `active.status = "done"`，与 `AGENTS.md` 中"验证命令以 0 退出"的完成定义矛盾（测验 Q9）。
- ⚠️ **不检查 owner**：`owner` 为 `reviewer` 或 `human` 的任务也会被 builder 领走。
- ⚠️ 第 109 行的 f-string 没有任何占位符（`f"active task missing ..."`），多余但无害，linter（如 ruff 的 F541）会提示。

### 3.6 `main`：打印 before / after

```python
    print("before turn:")
    print(f"  active task : {state.active_task_id}")
    print(f"  next action : {state.next_action!r}")
    print(f"  todo on board: {[t.id for t in board if t.status == 'todo']}")
    state, board = run_one_turn(state, board)
    save_state(state_path, state)
    save_board(board_path, board)
```

- `{...!r}` 用 `repr()` 显示字符串，带引号，空字符串会显示为 `''` 而不是什么都看不见。
- ⚠️ 讲义说脚本"prints the diff"，mission 也要求"Diff printed by the script shows the one file the turn touched"；实际只打印 before/after 摘要，没有 diff（也没有被改动的真实文件可以 diff）。
- `ROOT.mkdir(exist_ok=True)`：目录已存在时不报错；但只建一级，若父目录不存在会失败（这里父目录就是 `code/`，总是存在）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 三个独立文件 | 职责分离：路由（人写、少变）、状态（每轮变）、队列（任务级变化） | 跨文件一致性要自己保证；可以用单个目录 + 版本号，或把 state 与 board 合并提交 |
| JSON + dataclass | 机器可读、可 diff、标准库即可 | 字段与 dataclass 强耦合，改 schema 需迁移；第 34 节会引入 schema 与校验 |
| `exists()` 才初始化 | 幂等，重复运行不覆盖进度 | 文件损坏时不会自愈；可以加"校验失败 → 备份后重建" |
| 每轮只推进一步 | 演示"任何时刻中断都能恢复" | 真实 agent 一轮会做多步，需要在每个副作用之后都落盘 |
| `touched_files` 只记账 | 不需要真实仓库 | 无法演示 diff 与 scope 检查；真实实现应从 `git diff --name-only` 推导 |
| 完成时清空 `touched_files` | 状态只描述"当前任务" | 丢失了已完成任务的改动记录；应转存到任务记录或 handoff |
| 取第一个 `todo` | 简单 | 没有优先级、不看 owner、没有依赖；练习 2 加 priority |
| 非原子 `write_text` | 代码短 | 崩溃时可能留下半个 JSON；生产用临时文件 + `os.replace` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值；配合它，`str \| None` 写法在 3.9 上也能用于注解 |
| 联合类型 `X \| None` | `active_task_id: str \| None` | 表示"字符串或 None"，等价于 `Optional[str]` |
| 三引号多行字符串 | `AGENTS_MD = """# AGENTS.md ..."""` | 保留换行，适合内嵌模板文件 |
| 字符串方法链 | `"""...""".lstrip()` | 直接在字面量上调用方法 |
| `@dataclass` + `field(default_factory=list)` | `AgentState`、`Task` | 自动生成构造函数；可变默认值用工厂 |
| 字段顺序规则 | `status: str = "todo"` 放在最后 | dataclass 中带默认值的字段必须排在无默认值字段之后 |
| `dataclasses.asdict` | `asdict(AgentState(active_task_id=None))` | 递归把 dataclass 转成 dict，便于 `json.dumps` |
| `**dict` 解包 | `AgentState(**raw)`、`Task(**t)` | 字典键 → 关键字参数；键名必须与字段完全一致 |
| 生成器表达式 + `next` | `next((t for t in board if t.status == "todo"), None)` | 惰性查找第一个匹配项，提供默认值防止 `StopIteration` |
| 元组返回值与解包 | `-> tuple[AgentState, list[Task]]`、`state, board = run_one_turn(...)` | 一次返回多个值 |
| 列表推导式 | `[asdict(t) for t in board]`、`[(t.id, t.status) for t in board]` | 批量转换 |
| 对象引用语义 | `nxt.status = "in_progress"` | 修改的是列表中的同一个对象，无需写回列表 |
| f-string 与 `!r` | `f"{state.next_action!r}"` | `!r` 调用 `repr()`，字符串会带引号显示 |
| f-string 内的引号 | `{[t.id for t in board if t.status == 'todo']}` | 外层双引号时内部用单引号（3.12 起也可复用同种引号） |
| `pathlib` | `Path(__file__).parent / "workdir"`、`.exists()`、`.read_text()`、`.write_text()`、`.mkdir(exist_ok=True)` | 面向对象的路径操作 |
| `json.loads` / `json.dumps` | `json.loads(state_path.read_text())` | 字符串 ↔ Python 对象；`None` ↔ `null` |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行，import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时目录副本中从空 `workdir/` 开始连续运行 10 次，每次退出码均为 0）。前两次的完整输出：

```text
##### run 1
before turn:
  active task : None
  next action : ''
  todo on board: ['T-001', 'T-002']

after turn:
  active task : T-001
  touched     : []
  next action : 'start work on T-001: add input validation to /signup'
  board status: [('T-001', 'in_progress'), ('T-002', 'todo')]

##### run 2
before turn:
  active task : T-001
  next action : 'start work on T-001: add input validation to /signup'
  todo on board: ['T-002']

after turn:
  active task : T-001
  touched     : ['app.py']
  next action : 'add test for T-001 acceptance'
  board status: [('T-001', 'in_progress'), ('T-002', 'todo')]
```

10 次运行的摘要：

| 运行 | active task（after） | touched（after） | next action（after） | 任务板 |
|------|---------------------|-----------------|---------------------|--------|
| 1 | T-001 | [] | start work on T-001 | T-001 in_progress |
| 2 | T-001 | [app.py] | add test for T-001 acceptance | 同上 |
| 3 | T-001 | [app.py, test_app.py] | run verification command for T-001 | 同上 |
| 4 | None | [] | pick next task from board | **T-001 done** |
| 5 | T-002 | [] | start work on T-002 | T-002 in_progress |
| 6 | T-002 | [app.py] | add test for T-002 acceptance | 同上 |
| 7 | T-002 | [app.py, test_app.py] | run verification command for T-002 | 同上 |
| 8 | None | [] | pick next task from board | **T-002 done** |
| 9 | None | [] | no work on the board, idle | 全部 done |
| 10 | None | [] | no work on the board, idle | 全部 done |

解读：

- **跨进程接续成立**：第 2 次运行的 "before" 恰好是第 1 次的 "after"——满足 mission 的"Second run picks up where the first left off"。
- **每个任务需要 4 次运行**：取任务 1 次 + 两个文件各 1 次 + 完成 1 次。
- **第 4、8 次"完成"没有任何验证**：前一轮的 `next_action` 说要跑验证，但这一轮直接 done。
- **T-002 是文档任务，却"改了" app.py 和 test_app.py**：写死的动作序列与任务内容无关。
- **最终 `workdir/`**：`AGENTS.md`（13 行）、`agent_state.json`（`next_action: "no work on the board, idle"`）、`task_board.json`（两个任务均为 done）。没有 `docs/agent-rules.md`。

---

## 7. 动手改一改

1. **补齐路由目标**：在 `write_initial` 中同时创建 `docs/agent-rules.md`，每个 surface 一个 H2 占位（skill 要求），然后用练习 4 的 lint 验证不再报错。
2. **讲义练习 2：优先级**：给 `Task` 加 `priority: int = 0`（放在最后，带默认值以兼容旧文件），取任务时用 `max(todos, key=lambda t: t.priority)`，并顺便过滤 `owner == "builder"`（参考测验 Q10）。
3. **讲义练习 1：过期检查**：给 `AgentState` 加 `last_run: str | None = None`，保存时写入 UTC ISO 时间；超过 24 小时且未设置确认环境变量时以非零退出（参考测验 Q11）。
4. **让 done 名副其实**：给 `run_one_turn` 注入 `verify` 回调，验证失败把任务标 `blocked` 并写 `blockers`（参考测验 Q9）；再让 acceptance 统一成可执行命令。
5. **讲义练习 3：JSON Lines**：把 `task_board.json` 改成 `task_board.jsonl`，每行一个任务；对比修改一个任务状态时两种格式的 `git diff`。
6. **进阶：原子写入与真实 diff**：`save_*` 改为"写 `.tmp` 再 `os.replace`"；在 `workdir/` 中 `git init`，让每轮真正修改 `app.py`，并在 `main` 末尾打印 `git diff --stat`，满足 mission 的"prints the diff"。

---

## 8. 常见坑

- **每次运行都覆盖初始文件**：如果去掉 `exists()` 判断，第二次运行会回到起点，"可恢复"就失效了。
- **往 JSON 里加字段却不改 dataclass**：`AgentState(**raw)` 会抛 `TypeError`；反之新增无默认值字段会让旧文件读不进来。
- **数组字段用 `null`**：读取方要处处判空，skill 明确禁止。
- **路由指向不存在的文件**：agent 扑空后会自己猜，比没有路由更糟；用 lint 在 CI 中检查。
- **"状态说 A、任务板说 B"**：两个文件分开写入，中途崩溃就不一致；保留 "active task missing" 这类防御分支，并考虑原子写入。
- **把 `next_action` 写成"继续"**：应写成下一次会话可以直接执行的具体动作。
- **在 `code/` 下留着 `workdir/`**：它是运行产物，提交前记得清理或加入 `.gitignore`。
