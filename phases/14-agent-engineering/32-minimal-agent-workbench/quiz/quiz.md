# 测验 · 最小 Agent 工作台（The Minimal Agent Workbench）

> **阶段 14 · Agent 工程 · 第 32 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 最小工作台 = 三个文件 | `AGENTS.md`（路由）、`agent_state.json`（状态）、`task_board.json`（任务队列）；讲义："Three files is the floor, not the ceiling." |
| 2 | `AGENTS.md` 是路由器而不是手册 | 只指向四样东西：状态文件、任务板、更深的规则文档、验证命令；讲义："Long manuals get ignored. Short routers get followed." |
| 3 | `agent_state.json` 是系统记录 | 记录 active task id、touched files、assumptions、blockers、next action；每轮读、结束时写；下个会话读它而不是回放聊天 |
| 4 | `task_board.json` 是队列 | 每个任务有 id、goal、owner（builder / reviewer / human）、acceptance、status（todo / in_progress / done / blocked）；状态为空时从这里取活 |
| 5 | 任务板要小 | 讲义："when it grows past a screen, you have a planning problem, not a board problem"；配套 skill 规定超过 12 个未完成任务就拒绝 |
| 6 | 嵌套 `AGENTS.md` | 从工作文件向仓库根逐级查找并拼接，子目录扩展根文件（nearest wins）；Codex 的 `AGENTS.override.md` 是替换而非扩展，且仅 Codex 支持 |
| 7 | 反模式 | 冲突的指令（AMBIG-SWE：解决率 48.8% → 28%）、没有执行命令的风格规则、先写风格后写命令、为人而非为 agent 写作 |
| 8 | 跨工具软链接 | `ln -s AGENTS.md CLAUDE.md` 等，让所有 coding agent 共享同一个事实来源 |
| 9 | 单轮状态机（代码） | 无活动任务 → 取 todo；有活动任务 → 依次"改 app.py → 改 test_app.py → 标记 done"，每次运行只推进一步 |
| 10 | 代码与讲义的差距 | 代码没有打印 diff、没有真正写文件、没有跑验证命令就标记 done，`docs/agent-rules.md` 也不存在 |

### 核心技能（能动手做到）

- [ ] 为任意仓库写出不超过 80 行、只做路由的 `AGENTS.md`，并给出验证命令
- [ ] 设计 `agent_state.json` 与 `task_board.json` 的字段，说明每个字段被谁读、被谁写
- [ ] 预测 `main.py` 连续运行 N 次后的状态与任务板内容
- [ ] 给任务板加 `priority` 字段，修改取任务逻辑并保持旧文件兼容
- [ ] 写一个 `lint_workbench.py`：`AGENTS.md` 超长或引用不存在的文件时失败
- [ ] 解释为什么状态要落在文件而不是聊天记录里，以及写文件时要注意的一致性问题

---

## 二、基础自测（选择题）

**Q1.** 讲义所说"最小有用工作台"的三个文件是：

- A. `AGENTS.md`、`README.md`、`Makefile`
- B. `CLAUDE.md`、`.cursorrules`、`.github/copilot-instructions.md`
- C. `AGENTS.md`、`agent_state.json`、`task_board.json`
- D. `agent_state.json`、`failure_modes.json`、`scope.json`

**Q2.** 讲义主张 `AGENTS.md` 应该是"短路由器"而不是"长手册"，核心理由是：

- A. 长手册会被模型忽略或只被部分概括；短路由只在相关时把 agent 引向更深的文档，更容易被遵循
- B. 模型无法读取超过 80 行的文件
- C. 短文件可以省下全部 token 成本，因此是唯一考虑
- D. 长手册会让模型产生幻觉，因此必须完全删除规则文档

**Q3.** 在一个全新的 `workdir/` 上**第一次**运行 `python3 code/main.py` 之后，状态是：

- A. `active_task_id="T-001"`，`touched_files=["app.py"]`
- B. `active_task_id=None`，任务板不变
- C. `active_task_id="T-002"`，`touched_files=[]`
- D. `active_task_id="T-001"`，`touched_files=[]`，T-001 变为 `in_progress`

**Q4.** 从全新 `workdir/` 开始，连续运行 `main.py`，第几次运行结束后 T-001 的状态变成 `done`？

- A. 第 2 次
- B. 第 4 次
- C. 第 3 次
- D. 第 5 次

**Q5.** 讲义引用 ICLR 2026 的 AMBIG-SWE 数据，说明 `AGENTS.md` 中哪种反模式的代价？

- A. 相互冲突的指令会让 agent 从交互模式静默退化为贪心模式，解决率从 48.8% 降到 28%
- B. 文件过短会让解决率从 28% 降到 0%
- C. 使用软链接会让不同工具读到不同内容
- D. 写了验证命令反而会降低解决率

**Q6.** 关于嵌套 `AGENTS.md`，讲义描述正确的是：

- A. 只读取仓库根目录的 `AGENTS.md`，子目录中的文件会被忽略
- B. 只读取离工作文件最近的那一个，其余全部丢弃
- C. 所有工具都支持 `AGENTS.override.md`，推荐跨工具使用
- D. 从工作文件向仓库根逐级查找并拼接所有 `AGENTS.md`，子目录文件扩展根文件；`AGENTS.override.md` 是 Codex 特有的替换机制

**Q7.** 继续运行脚本到 T-002（"document the new /signup contract"，验收标准是 `docs/api.md mentions /signup constraints`）。代码在处理 T-002 时记录的 `touched_files` 会是：

- A. `["docs/api.md"]`
- B. `[]`，因为文档任务不改文件
- C. `["app.py", "test_app.py"]`
- D. 抛出 `KeyError`

**Q8.** 按配套 skill（`outputs/skill-minimal-workbench.md`），任务的 `owner` 字段应取哪类值？

- A. `agent` / `model` / `human`
- B. `builder` / `reviewer` / `human`——owner 是角色而不是实体
- C. 具体模型名，例如 `claude` / `gpt`
- D. 留空，由 agent 自行决定

---

## 三、动手 / 代码题

**Q9.** `main.py` 写出的 `AGENTS.md` 规定了完成定义：

```text
Definition of done: the task referenced by `agent_state.active_task_id` has
`status == "done"` on `task_board.json` and the verification command listed in
its `acceptance` has exited 0.
```

而 `run_one_turn` 的最后一段是：

```python
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

1. 这段代码与完成定义矛盾在哪里？
2. 修改 `run_one_turn`，让它接受一个 `verify: Callable[[Task], bool]` 参数：验证通过才标记 `done`；失败则把任务标为 `blocked`、在 `state.blockers` 里写原因。
3. 标记 `done` 时把 `touched_files` 清空，会丢失什么信息？

**Q10.** 讲义练习 2：给任务加 `priority` 字段，让取任务逻辑总是挑选优先级最高的 `todo`。请写出修改后的 `Task` 与取任务代码，并说明：已有的 `task_board.json`（没有 `priority` 键）还能被 `load_board` 读取吗？如何保证兼容？

**Q11.** 讲义练习 1：给 `agent_state.json` 加 `last_run` 时间戳，文件超过 24 小时未更新时拒绝运行，除非操作员确认。

1. 如果只往 JSON 里加 `"last_run": "..."` 而不改 `AgentState`，`load_state` 会发生什么？
2. 写出实现（提示：`datetime.now(timezone.utc)`、ISO 8601 字符串、环境变量或命令行参数作为"操作员确认"）。

**Q12.** 讲义练习 4：写一个 `lint_workbench.py`，当 `AGENTS.md` 超过 80 行或引用了不存在的文件时以非零退出。把它运行在 `main.py` 生成的 `workdir/` 上，结果是什么？这说明了什么？

---

## 四、面试高频题

**Q13.**（基础必考）如果让你给一个新仓库搭建最小的 agent 工作台，你会放哪些文件？每个文件里放什么、谁读、谁写？

**Q14.**（原理深挖）为什么 agent 的状态要放在文件里而不是聊天历史里？把状态放进文件后，又会遇到哪些新的工程问题（一致性、并发、损坏）？

**Q15.**（工程实践）在一个大型 monorepo 中，多个团队、多种 coding agent（Claude Code、Codex、Cursor、Copilot）并存。你如何组织 `AGENTS.md`？有哪些必须避免的写法？

**Q16.**（场景设计）一个需要 3 天、跨多个会话完成的重构任务。请设计任务板和"会话启动/结束协议"，确保任何一个新会话都能无缝接手。

**Q17.**（追问型）三个文件里，丢掉哪一个最痛？为什么？（讲义练习 5）

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义开篇："The smallest useful workbench is three files: a root instructions router, a state file, and a task board." 对应 `AGENTS.md`、`agent_state.json`、`task_board.json`。B 是同一个路由文件在不同工具中的名字（讲义建议用软链接统一）；A 是传统仓库文件；D 混入了第 31 节的输出文件。

### Q2 — 答案：A

讲义："Anything longer goes in deeper docs, loaded only when needed. Long manuals get ignored. Short routers get followed." 并举例 3000 行的 `AGENTS.md`："The model loads it, ignores the parts it cannot summarize"。

- B 错：80 行是配套 skill 和练习 4 定下的**工程约束**，不是模型的读取上限；
- C 错：token 成本只是理由之一，核心是"能否被遵循"；
- D 错：规则不是删除，而是下沉到 `docs/agent-rules.md`，按需加载。

### Q3 — 答案：D

实际运行第 1 次的输出：

```text
after turn:
  active task : T-001
  touched     : []
  next action : 'start work on T-001: add input validation to /signup'
  board status: [('T-001', 'in_progress'), ('T-002', 'todo')]
```

`state.active_task_id is None`，于是走"取任务"分支：取第一个 `todo`，置为 `in_progress`，写 `next_action` 后**立即返回**——这一轮不碰任何文件。A 是第 2 次运行的结果。

### Q4 — 答案：B

每次运行只推进一步（已实际连续运行 10 次验证）：

| 运行 | 动作 | T-001 状态 |
|------|------|-----------|
| 1 | 取任务 | in_progress |
| 2 | touched += app.py | in_progress |
| 3 | touched += test_app.py | in_progress |
| 4 | 标记 done，清空 active 和 touched | **done** |
| 5 | 取 T-002 | done |

第 8 次运行后 T-002 也变成 done，第 9、10 次输出 `no work on the board, idle`。

### Q5 — 答案：A

讲义："Conflicting instructions silently drop the agent from interactive to greedy mode (ICLR 2026 AMBIG-SWE: 48.8% → 28% resolve rate); number priorities instead of stacking them flat." 解决办法是给规则编号定优先级，而不是平铺。C 正好相反：软链接是为了让所有工具读到**同一份**内容；D 与讲义"commands first"的建议相反。

### Q6 — 答案：D

讲义："Codex, Cursor, Claude Code, and Copilot all walk from the working file toward the repo root and concatenate every `AGENTS.md` they find on the way. Sub-directory files extend the root file. Codex adds `AGENTS.override.md` to replace rather than extend; the override mechanism is Codex-specific and avoid it for cross-tool work." 另外讲义提到 OpenAI 主仓库中有 88 个 `AGENTS.md`，每个子组件一个。

- A、B 都与"逐级拼接"不符；
- C 错在"所有工具都支持"——讲义明确说它是 Codex 特有的，跨工具时应避免。

### Q7 — 答案：C

`run_one_turn` 中改哪个文件是**写死**的：不管任务是什么，都先 `app.py` 再 `test_app.py`。实际运行第 6、7 次：

```text
  active task : T-002
  touched     : ['app.py', 'test_app.py']
  next action : 'run verification command for T-002'
```

一个"写文档"的任务改了代码和测试，却没碰 `docs/api.md`——这恰好是第 31 节说的 Scope 缺失症状（"Edits leak into unrelated code"），只是在这个最小工作台里还没有 scope 合约来拦截。

### Q8 — 答案：B

skill 的硬拒绝条款："Tasks whose `owner` is `agent` or `model`. Owners are roles, not entities." 讲义正文也写明 owner 是 `builder`、`reviewer` 或 `human`。用角色而不是实体，后续才能做到"builder 不能批准自己的作业"（第 39 节 reviewer）。注意：本节代码的取任务逻辑**没有检查 owner**，会把 owner 为 `reviewer` 或 `human` 的任务也拿来做。

### Q9 — 参考答案

1. **矛盾**：完成定义要求"验收中列出的验证命令以 0 退出"，代码在第 4 次运行时只是看到两个文件都在 `touched_files` 里，就直接 `active.status = "done"`——验证命令从未执行。`next_action` 写着 "run verification command"，但下一轮并没有运行它。此外 T-002 的 `acceptance` 是一句自然语言（`docs/api.md mentions /signup constraints`），根本不是可执行命令。
2. 参考实现：

```python
from typing import Callable

def run_one_turn(state, board, verify: Callable[[Task], bool] = lambda t: False):
    ...  # 前面的取任务 / 改文件分支不变
    if verify(active):
        active.status = "done"
        state.active_task_id = None
        state.touched_files = []
        state.next_action = "pick next task from board"
    else:
        active.status = "blocked"
        state.blockers.append(f"{active.id}: verification failed: {active.acceptance}")
        state.next_action = f"fix failing verification for {active.id}"
    return state, board
```

   默认 `verify` 返回 `False`（fail closed）：没有提供验证器时宁可阻塞也不放行。真实实现可以用 `subprocess.run(cmd, shell=False)` 执行 acceptance 中的命令并检查 `returncode == 0`。注意 `blocked` 的任务需要有人（或下一轮）处理：取任务分支只看 `todo`，所以还要在 `active_task_id` 不为空且任务为 `blocked` 时给出明确的 `next_action`。
3. 清空 `touched_files` 会丢掉"这个任务到底改了哪些文件"的记录，下一个会话（或 reviewer、handoff）无法知道 T-001 的改动范围。更好的做法是把它移到任务记录里（例如 `task.touched_files`）或写入 handoff/进度日志后再清空——第 34 节会把这类信息放进带 schema 的持久状态。

### Q10 — 参考答案

```python
@dataclass
class Task:
    id: str
    goal: str
    owner: str
    acceptance: list[str]
    status: str = "todo"
    priority: int = 0            # 数字越大越优先；带默认值，旧文件可读

def pick_next(board):
    todos = [t for t in board if t.status == "todo" and t.owner == "builder"]
    if not todos:
        return None
    return max(todos, key=lambda t: t.priority)   # 平局时 max 返回第一个，保持任务板顺序
```

- **兼容性**：`load_board` 用 `Task(**t)` 构造。旧 JSON 没有 `priority` 键，因为新字段带默认值 `0`，可以正常读取；如果新字段**没有默认值**，就会抛 `TypeError: missing 1 required positional argument`。注意 dataclass 要求带默认值的字段放在无默认值字段之后，所以 `priority` 要放在末尾。
- 顺带加了 `owner == "builder"` 过滤，修复了原代码不检查 owner 的问题（见 Q8）。
- `run_one_turn` 中把 `next((t for t in board if t.status == "todo"), None)` 换成 `pick_next(board)` 即可。

### Q11 — 参考答案

1. `load_state` 执行 `AgentState(**raw)`，未知键会变成未知关键字参数，抛出（已实际验证）：

```text
TypeError: AgentState.__init__() got an unexpected keyword argument 'last_run'
```

   也就是说：**JSON 的 schema 与 dataclass 是强耦合的**，往状态文件里加字段必须同步改代码；反过来，一个手工编辑过状态文件的人也可能让 agent 启动失败。

2. 参考实现：

```python
import os
from datetime import datetime, timedelta, timezone

@dataclass
class AgentState:
    active_task_id: str | None
    touched_files: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_action: str = ""
    last_run: str | None = None          # ISO 8601，带时区

def check_freshness(state, max_age=timedelta(hours=24)):
    if state.last_run is None:
        return                           # 首次运行
    age = datetime.now(timezone.utc) - datetime.fromisoformat(state.last_run)
    if age > max_age and os.environ.get("WORKBENCH_CONFIRM_STALE") != "1":
        raise SystemExit(f"state is {age} old; set WORKBENCH_CONFIRM_STALE=1 to continue")

# main() 中：load_state 之后调用 check_freshness(state)；save_state 之前
# state.last_run = datetime.now(timezone.utc).isoformat()
```

   要点：使用带时区的 UTC 时间，避免夏令时和时区混乱；"拒绝运行"要以非零状态退出并说明如何确认；首次运行（无 `last_run`）不应被拒。为什么要做这个检查：过期的状态可能描述的是一个早已被别人改动过的仓库，盲目继续会基于错误假设行动。

### Q12 — 参考答案

```python
import re, sys
from pathlib import Path

def lint(root: Path, max_lines: int = 80) -> list[str]:
    errs = []
    p = root / "AGENTS.md"
    if not p.exists():
        return ["AGENTS.md missing"]
    text = p.read_text()
    n = len(text.splitlines())
    if n > max_lines:
        errs.append(f"AGENTS.md has {n} lines > {max_lines}")
    for ref in re.findall(r"`([\w./-]+\.(?:md|json|py|txt))`", text):
        if not (root / ref).exists():
            errs.append(f"missing reference: {ref}")
    return errs

if __name__ == "__main__":
    errors = lint(Path(sys.argv[1]))
    print("\n".join(errors) or "ok")
    sys.exit(1 if errors else 0)
```

在生成的 `workdir/` 上实际运行：`AGENTS.md` 共 13 行（满足 skill 要求的 10–80 行），但输出 `missing reference: docs/agent-rules.md`，退出码 1。

这说明：`main.py` 生成的路由指向了一个**不存在**的规则文档。配套 skill 明确要求同时生成 `docs/agent-rules.md` 占位文件，并且说"A router pointing at a missing gate is worse than no router"。路由失效是"静默"的——agent 去找文件扑空后通常会自行猜测，因此需要 lint 在 CI 中把关。实现上要注意正则只匹配反引号包裹、带扩展名的路径，避免把 `agent_state.active_task_id` 这类字段引用误判为文件。

### Q13 — 参考回答要点

- **`AGENTS.md`（路由）**：短（≤ 80 行），只指向状态文件、任务板、深层规则文档、验证命令；人写、agent 读。验证命令放在最前面。
- **`agent_state.json`（状态）**：`active_task_id`、`touched_files`、`assumptions`、`blockers`、`next_action`；agent 每轮读、每轮结束写；新会话启动时先读它。
- **`task_board.json`（队列）**：任务数组，每项 `id/goal/owner/acceptance/status`；人和 planner 写入任务，agent 更新状态；状态为空时 agent 从这里取下一个 `todo`。
- **加分点**：数组字段默认空数组而不是 `null`（skill 要求）；每个任务必须有 acceptance；任务板超过一屏（12 个未完成任务）说明需要先做规划；同时生成 `docs/agent-rules.md` 占位，避免路由悬空。
- **常见误区**：写一份几千行的 `AGENTS.md` 当作"工作台"。

### Q14 — 参考回答要点

- **为什么用文件**：讲义："Sessions die. Conversations get trimmed. The file does not." 聊天会被截断、压缩、在新会话中消失，还可能随模型更换而丢失；文件在仓库里，可 diff、可审查、可被任何工具读取，是唯一的"系统记录"。
- **新问题**：
  - **原子性**：`write_text` 不是原子操作，写到一半崩溃会留下损坏的 JSON；应写临时文件再 `os.replace`。
  - **跨文件一致性**：本节代码先写 state 再写 board，两次写入之间崩溃会造成"state 说在做 T-001、board 说 T-001 还是 todo"的不一致；需要以其中一个为准或合并为单次提交。
  - **schema 演进**：`AgentState(**raw)` 遇到未知键会崩溃（见 Q11），需要版本号和迁移。
  - **并发**：两个 agent 同时取任务会重复领取；需要锁或"compare-and-set"式的领取。
  - **腐化**：长期不更新的状态会过期（练习 1 的 24 小时检查）。
- **加分点**：提到第 31 节的原语——状态就是 session persistence，持久化语义比存储后端更重要；把状态文件纳入 git 后，提交历史本身就是审计日志。

### Q15 — 参考回答要点

- **结构**：根目录一个短 `AGENTS.md`（全局命令、规则路由），每个子组件一个 `AGENTS.md` 补充本组件的命令与约束；工具会从工作文件向根逐级拼接（讲义：OpenAI 主仓库有 88 个）。
- **单一事实来源**：用软链接让 `CLAUDE.md`、`.github/copilot-instructions.md`、`.cursorrules` 都指向 `AGENTS.md`；或用 Nx `nx ai-setup` 从一份配置生成。避免使用 Codex 特有的 `AGENTS.override.md`。
- **必须避免**：
  - 冲突的指令（AMBIG-SWE 解决率 48.8% → 28%）——用编号表达优先级；
  - 无法验证的风格规则（"遵循 Google Python Style Guide"）——每条风格规则配一个具体的 lint 命令；
  - 先写风格、后写命令——命令在前，风格在后；
  - 为人类写长篇解释——简洁本身就是特性。
- **加分点**：讲义引用 Augment Code 的测量：好的 `AGENTS.md` 带来的提升相当于从 Haiku 升级到 Opus，差的比没有还糟——所以要把 `AGENTS.md` 当作需要评测的代码，而不是随手写的文档；在 CI 中跑 lint（行数、引用存在性）。

### Q16 — 参考回答要点

- **任务板**：把 3 天的重构拆成若干个 1–2 小时、各自有可执行 acceptance 的任务；标注依赖与 owner；可用 JSON Lines（讲义练习 3）让每个任务一行，git diff 干净、合并冲突少。
- **会话启动协议**：读 `AGENTS.md` → 读 `agent_state.json`（检查 `last_run` 是否过期）→ 若有 active task，从 `next_action` 继续；否则按优先级从任务板取 `todo` → 先跑一次验证命令确认基线。
- **会话结束协议**：更新 `touched_files`、`assumptions`、`blockers`、`next_action`；任务完成须验证命令退出 0 才能标 done；未完成就写清楚"下一步做什么"；提交到 git。
- **遇到阻塞**：标 `blocked` 并在 `blockers` 里写原因，交给 `human` owner，而不是在聊天里描述。
- **加分点**：每个 `next_action` 写成可以直接执行的一句话（如"run verification command for T-001"），而不是"继续"；第 40 节的 handoff 会把这套协议正式化。

### Q17 — 参考回答要点

这是开放题，关键是给出论证。一种有说服力的回答：**丢掉 `agent_state.json` 最痛**。

- `AGENTS.md` 丢了可以从仓库结构、README、CI 配置大致重建，且内容变化慢；
- `task_board.json` 丢了，任务可以从 issue 跟踪、需求文档中恢复；
- `agent_state.json` 记录的是**只在运行时产生、别处没有副本**的信息：做到哪一步、做了哪些假设、卡在哪里、下一步是什么。丢了它，下个会话只能从零重新发现（第 31 节的 State 缺失症状："Each session restarts from zero"），甚至可能重复已经做过的破坏性操作。

也可以论证"任务板最痛"（它是队列，没有它就不知道"做完没有"），只要论证围绕"哪些信息不可从别处重建"展开即可。加分点：指出正因为状态最难重建，它也最需要原子写入、版本化和提交到 git。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 31 Agent 工作台工程：能力强的模型为什么仍会失败](../../31-agent-workbench-why-models-fail/docs/zh.md)：七个 surface；本节先落地 Instructions、State 和任务队列。
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：`run_one_turn` 就是一次循环迭代。
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../07-memory-virtual-context-memgpt/docs/zh.md)：为什么不能依赖上下文窗口保存长期状态。

### 本节被哪些后续内容用到
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../33-instructions-as-executable-constraints/docs/zh.md)：把 `docs/agent-rules.md` 占位变成可执行的规则。
- [阶段 14 · 34 代码仓库记忆与持久状态](../../34-repo-memory-and-state/docs/zh.md)：本节 `agent_state.json` 的完整 schema 版。
- [阶段 14 · 35 面向 Agents 的初始化脚本](../../35-initialization-scripts/docs/zh.md)：会话开始前自动检查这三个文件。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：解决本节"文档任务却改了代码"的问题。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：补上"验证命令退出 0 才能 done"。
- [阶段 14 · 40 跨会话 Handoff](../../40-multi-session-handoff/docs/zh.md)：会话结束协议的正式版本。

### 延伸关键词
`AGENTS.md` · `CLAUDE.md` · `nearest-wins precedence` · `AGENTS.override.md` · `symlink single source of truth` · `system of record` · `task board / queue` · `JSON Lines` · `atomic write (os.replace)` · `schema evolution` · `AMBIG-SWE`
