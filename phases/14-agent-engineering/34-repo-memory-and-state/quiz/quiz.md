# 测验 · 代码仓库记忆与持久状态（Repo Memory and Durable State）

> **阶段 14 · Agent 工程 · 第 34 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Repo memory（仓库记忆） | 状态以 JSON 文件存在仓库里，有 schema、原子写入、可 diff；讲义："Chat is a transient feed; the repo is the system of record." |
| 2 | 什么该进仓库记忆 | 活动任务、本次改动文件、假设、阻塞、下一步；不该进：原始聊天记录、token 级推理轨迹、"用户似乎很沮丧"、采样结果、厂商模型 id |
| 3 | 耐久性测试 | "三个月后在 CI 重跑时还有用吗？"有用 → 仓库；没用 → telemetry（遥测） |
| 4 | Schema-first | JSON Schema 是契约：必填键、允许的 status、禁止数组为 `null`、id 格式 `T-\d{3,}`、`schema_version`；"a bad write is a refused write" |
| 5 | 原子写入 | 同目录 `tempfile.mkstemp` → 写入 → `fsync` → `os.replace`；半截文件比没有文件更糟 |
| 6 | 迁移 | 状态带 `schema_version`；改 schema 时随附迁移脚本；遇到无法迁移的版本拒绝加载 |
| 7 | 幂等键 | 非幂等工具调用（发邮件、插库、上传）执行前把调用 ID 记入 `pending_calls.jsonl`，重试时命中则跳过并用缓存结果 |
| 8 | 大产物与状态分离 | CSV、长转录、生成文件单独存放（或对象存储），状态里只存路径 |
| 9 | 事件溯源 + 快照 | 每次变更追加到 `state.events.jsonl`，定期快照到 `state.json`；恢复 = 读快照 + 重放之后的事件，与 Postgres WAL 同构 |
| 10 | 代码与讲义差距 | 自写验证器隐含"禁止额外字段"（与标准 JSON Schema 默认不同）；没有 `update` 方法；任务板从未被修改，导致状态与任务板不一致 |

### 核心技能（能动手做到）

- [ ] 为 `agent_state.json` 和 `task_board.json` 写出 JSON Schema，覆盖 required、type、enum、pattern、items
- [ ] 读懂并能复现 `validate` 递归验证器，说出它与标准 `jsonschema` 库在哪些输入上结论不同
- [ ] 正确实现原子写入，并说清每一步防的是哪种故障
- [ ] 实现 `StateManager.update` 和 v1 → v2 的迁移（`blockers` 改名为 `risks`），未知版本拒绝加载
- [ ] 解释"原子重命名"能防什么、不能防什么（并发下的丢失更新），并给出锁或乐观并发方案
- [ ] 为非幂等工具调用设计幂等键与恢复流程

---

## 二、基础自测（选择题）

**Q1.** 讲义判断"某条信息该不该进仓库记忆"的测试是：

- A. 它是否由模型生成
- B. 三个月后在 CI 重跑时它是否还有用：有用进仓库，没用进 telemetry
- C. 它的大小是否小于 1 KB
- D. 用户是否在聊天中提到过它

**Q2.** 按讲义表格，下列哪一项**属于**仓库记忆？

- A. 原始聊天记录
- B. token 级推理轨迹
- C. "用户似乎很沮丧"
- D. agent 做出的假设（assumptions）

**Q3.** 讲义描述的原子写入步骤是：

- A. 在目标文件同目录用 `tempfile.mkstemp` 建临时文件 → 写入 → `fsync` → `os.replace` 覆盖目标
- B. 直接 `path.write_text(content)`，失败时捕获异常并忽略
- C. 先删除目标文件，再写入新文件
- D. 在 `/tmp` 下写临时文件，再 `shutil.copy` 到目标

**Q4.** `atomic_write` 中 `tempfile.mkstemp(..., dir=path.parent)` 特意把临时文件建在**目标文件所在目录**，主要原因是：

- A. 节省磁盘空间
- B. 让临时文件的权限与目标文件一致
- C. 重命名只有在同一文件系统内才是原子的；跨设备时 `os.replace` 会失败（或退化为复制）
- D. 方便 git 跟踪临时文件

**Q5.** 用本节的 `validate` 校验一个合法状态，但额外多了一个字段 `"last_run": "2026-10-12"`，结果是：

- A. 本节验证器拒绝（报 `unexpected fields ['last_run']`），而标准 `jsonschema` 库在同一 schema 下接受
- B. 两者都接受
- C. 两者都拒绝
- D. 本节验证器接受，标准 `jsonschema` 拒绝

**Q6.** 讲义提出的"幂等键"模式是：

- A. 所有工具调用都重试三次，取多数结果
- B. 只对读操作记录调用 ID
- C. 每次重启时清空所有待处理调用
- D. 非幂等调用**执行前**把调用 ID 写入 `pending_calls.jsonl`；重试时发现 ID 已存在就跳过调用、使用缓存结果

**Q7.** 运行 `python3 code/main.py` 后，`workdir/agent_state.json` 的 `active_task_id` 是 `T-001`，那么 `workdir/task_board.json` 中 T-001 的 `status` 是：

- A. `in_progress`
- B. `todo`
- C. `done`
- D. 文件不存在

**Q8.** 状态 schema 中 `active_task_id` 定义为 `{"type": ["string", "null"], "pattern": r"^(T-\d{3,}|)$"}`。以下哪组值**全部**能通过本节验证器？

- A. `None`、`"T-01"`、`"T-001"`
- B. `"T-001"`、`"t-001"`、`""`
- C. `None`、`""`、`"T-0001"`、`"T-001\n"`
- D. `"T-001"`、`"T-bogus"`

---

## 三、动手 / 代码题

**Q9.** 讲义和 mission 都说要实现 `StateManager.load`、`StateManager.update`、`StateManager.commit`，但代码里只有 `load` 和 `commit`。

1. 实现 `update(**changes)`：读取 → 合并 → 验证 → 原子写入；验证失败时磁盘上的文件不得改变。
2. `main()` 把 `active_task_id` 设为 `T-001`，却没有把任务板上 T-001 改成 `in_progress`。写一个跨文件一致性检查 `check_consistency(state, board)`，列出至少两条应当成立的不变量。

**Q10.** 讲义练习 3：加 `schema_version`（已存在）并写出 v1 → v2 的迁移：把 `blockers` 改名为 `risks`。要求：

- 迁移函数可以链式执行（v1 → v2 → v3…）；
- 对已是最新版本的文件幂等；
- 遇到未知版本时拒绝加载（fail loud）。

**Q11.** 讲义练习 5："Run two agents against the same state file with a 50 ms write race. What goes wrong and how does the atomic rename save you?"

下面的代码模拟了两个 agent 交错读写：

```python
mgr = StateManager(state_path, STATE_SCHEMA)
a = mgr.load()
b = mgr.load()
a["touched_files"].append("app.py")      # agent A 记录改动
b["blockers"].append("db down")          # agent B 记录阻塞
mgr.commit(a)
mgr.commit(b)
print(mgr.load())
```

1. 最终文件内容是什么？丢了什么？
2. 原子重命名在这个场景里"救"了什么、"没救"什么？
3. 给出一种修复方案。

**Q12.** 阅读 `atomic_write`：

```python
def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise
```

1. 运行后用 `ls -l` 查看 `workdir/agent_state.json` 的权限，会看到什么？为什么？这在团队仓库里会造成什么问题？
2. 若在 `fsync` 之后、`os.replace` 之前进程被 `kill -9`，磁盘上会留下什么？下一次启动应如何处理？
3. 为了在断电后也保证"重命名本身"已经落盘，POSIX 上还需要多做哪一步？
4. 讲义提到的 Hive 项目 bug 与这段代码的区别是什么？

---

## 四、面试高频题

**Q13.**（基础必考）agent 的长期状态为什么要放在仓库文件里？哪些东西应该放、哪些不该放？为什么要先写 schema？

**Q14.**（原理深挖）请讲清楚"原子写入"的实现：每一步防的是什么故障？它能解决并发写的问题吗？

**Q15.**（工程实践）agent 在调用"发送邮件"工具之后、写入 checkpoint 之前崩溃了。恢复时如何避免重复发送？请设计完整机制。

**Q16.**（场景设计）一个需要连续运行数天的 long-horizon agent，你需要既能"从崩溃处恢复"，又能"事后逐步复盘它的每个决策"。请设计状态存储方案。

**Q17.**（追问型）上线三个月后要给状态加字段、改字段名。你如何做 schema 演进而不让正在运行的 agent 崩溃？这与 LangGraph checkpointer 有什么关系？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："The test is durability: would this be useful three months from now in a CI rerun? If yes, repo. If no, telemetry." A、C、D 都不是判断标准：模型生成的"下一步"同样要进仓库；大小只决定"放状态里还是单独存成产物并存路径"（见核心知识点 8）。

### Q2 — 答案：D

讲义表格中 Belongs 列：Active task id、Touched files this session、**Assumptions the agent made**、Open blockers、Next action。A、B、C 都在 "Does not belong" 列。假设之所以要持久化，是因为下一个会话或 reviewer 需要知道"之前的工作建立在什么前提上"，前提一旦被推翻，相关改动都要复查。

### Q3 — 答案：A

讲义："write to a tempfile, fsync, rename over the target"，并在 Production patterns 中给出具体做法："`tempfile.mkstemp` in the same directory as the target, write, `fsync`, `os.replace` (atomic rename on POSIX and Windows)"。

- B 正是讲义引用的 Hive 项目 bug：`write_text()` + 吞掉异常，导致会话在损坏的状态上恢复且毫无信号；
- C 删除与写入之间崩溃会让文件彻底消失；
- D 跨文件系统时无法原子替换，`copy` 本身也不是原子的。

### Q4 — 答案：C

`rename(2)` 的原子性只在同一文件系统内成立；`/tmp` 常常是独立的 tmpfs，跨设备 `os.replace` 会抛 `OSError: [Errno 18] Invalid cross-device link`，而 `shutil.move` 会退化为"复制 + 删除"，失去原子性。B 恰好相反：`mkstemp` 创建的文件权限固定为 `0600`，替换后目标文件的权限也变成了 `0600`（见 Q12）。

### Q5 — 答案：A

实测：

```text
extra field   ours=REJECT: $: unexpected fields ['last_run'] | jsonschema=ok
```

本节 `validate` 对每个对象都检查 `set(value.keys()) - set(properties.keys())`，相当于对所有对象隐式设置了 `"additionalProperties": false`。标准 JSON Schema 的默认行为是**允许**额外属性，除非显式写 `additionalProperties: false`。

这是一个"更严格但不声明"的差异：把 `schemas/agent_state.schema.json` 交给别的工具（例如 CI 里用 `jsonschema` 库）验证时，会得到不同的结论。正确做法是在 schema 中**显式**写上 `"additionalProperties": false`，让两种验证器一致。另一个实测差异：`schema_version: 1.0` 被本节验证器拒绝（`isinstance(1.0, int)` 为假），而 `jsonschema` 按规范把小数部分为零的数视为 integer 而接受。

### Q6 — 答案：D

讲义："log every tool call ID before execution into a `pending_calls.jsonl`. On retry, check for the ID; if present, skip the call and use the cached result." 关键在于"执行**前**记录"——如果执行后才记录，崩溃恰好发生在两者之间时就无法知道调用是否已经发生。讲义还指出 LangGraph 的 checkpointer 会持久化 pending writes，原因相同。

### Q7 — 答案：B

实际运行输出中任务板为：

```text
    "status": "todo"
```

`main()` 只改了状态（`active_task_id = "T-001"`、`next_action`），任务板在初始提交后从未被修改。两个文件各自都通过了 schema 验证，但**合起来是矛盾的**：状态说"正在做 T-001"，任务板说"T-001 还没开始"。单文件 schema 无法表达跨文件约束，需要额外的一致性检查（Q9）。讲义 Build It 说脚本会"mutates them across two turns"，实际只有一次对状态的修改。

### Q8 — 答案：C

逐项实测（本节验证器与 `jsonschema` 结论相同）：

| 值 | 结果 | 原因 |
|----|------|------|
| `None` | 通过 | type 允许 `null`，pattern 只对字符串生效 |
| `""` | 通过 | pattern 中的 `\|)` 分支允许空串 |
| `"T-0001"` | 通过 | `\d{3,}` 是"至少 3 位" |
| `"T-001\n"` | 通过 | Python 的 `$` 可以匹配字符串末尾换行符之前的位置 |
| `"T-01"` | 拒绝 | 只有 2 位数字 |
| `"t-001"` | 拒绝 | 大小写敏感 |
| `"T-bogus"` | 拒绝 | 正是 demo 里被拒的坏写入 |

启示：`None` 和 `""` 两种值都表示"没有活动任务"，读取方要同时处理两种情况——应只保留一种；如需严格匹配，Python 中用 `re.fullmatch` 或 `\Z` 代替 `$`。

### Q9 — 参考答案

1. 实现（已运行验证）：

```python
class StateManager:
    ...
    def update(self, **changes):
        state = self.load()            # 读入时也做验证，坏文件不会被"修改后保存"
        state.update(changes)
        self.commit(state)             # commit 内部先 validate 再 atomic_write
        return state
```

   验证：`update(next_action="b", touched_files=["app.py"])` 成功；`update(active_task_id="bad")` 抛 `SchemaError`，磁盘上的 `active_task_id` 仍是原值。因为 `commit` 在写文件**之前**验证，坏写入根本不会触碰磁盘——这就是"a bad write is a refused write"。

2. 一致性检查：

```python
def check_consistency(state, board):
    errors = []
    ids = [t["id"] for t in board]
    if len(ids) != len(set(ids)):
        errors.append("duplicate task ids on board")
    active = state["active_task_id"] or None          # 把 "" 也视为无任务
    if active is not None:
        task = next((t for t in board if t["id"] == active), None)
        if task is None:
            errors.append(f"active task {active} not on board")
        elif task["status"] != "in_progress":
            errors.append(f"active task {active} has status {task['status']!r}, expected 'in_progress'")
    in_prog = [t["id"] for t in board if t["status"] == "in_progress"]
    if len(in_prog) > 1:
        errors.append(f"more than one in_progress task: {in_prog}")
    return errors
```

   不变量：活动任务必须存在于任务板上且状态为 `in_progress`；任务 id 唯一（schema 无法表达，实测重复 id 能通过两种验证器）；单 agent 场景下最多一个 `in_progress`。本节 demo 运行后会得到 `active task T-001 has status 'todo', expected 'in_progress'`。

### Q10 — 参考答案

```python
import copy

STATE_SCHEMA_V2 = copy.deepcopy(STATE_SCHEMA)
STATE_SCHEMA_V2["properties"]["schema_version"]["enum"] = [2]
STATE_SCHEMA_V2["properties"]["risks"] = STATE_SCHEMA_V2["properties"].pop("blockers")

def migrate_1_to_2(s):
    s = dict(s)
    s["risks"] = s.pop("blockers", [])     # blockers 不是必填，缺失时给空数组而不是 null
    s["schema_version"] = 2
    return s

MIGRATIONS = {1: migrate_1_to_2}           # 以后加 2: migrate_2_to_3 即可链式执行
CURRENT = 2

def migrate(raw):
    v = raw.get("schema_version")
    while v != CURRENT:
        if v not in MIGRATIONS:
            raise SchemaError(f"cannot migrate from schema_version={v!r}")
        raw = MIGRATIONS[v](raw)
        v = raw["schema_version"]
    return raw
```

实测：v1 状态迁移后通过 v2 schema 验证；对 v2 再次调用 `migrate` 结果不变（幂等）；`schema_version: 7` 抛出 `SchemaError: cannot migrate from schema_version=7`。

接入方式：`load()` 中先 `migrate(raw)` 再 `validate(raw, 当前 schema)`，迁移后立即 `commit` 写回，使磁盘文件升级到新版本。注意要用 `copy.deepcopy` 复制 schema，直接改 `STATE_SCHEMA` 会把 v1 的定义也改掉（嵌套字典是共享的）。讲义："ship a migration script next to the schema bump; `tools/migrate_state.py` runs idempotently on every startup."

### Q11 — 参考答案

1. 实测最终内容：`touched_files: []`、`blockers: ["db down"]`。agent A 记录的 `app.py` **丢了**——经典的 lost update（丢失更新）：两者基于同一个旧快照修改，后写者整体覆盖了先写者。
2. 原子重命名**救了**：文件永远是某一个完整版本（A 的或 B 的），不会出现两次写入交错导致的半截 JSON 或混合内容，读者也不会读到写了一半的文件。原子重命名**没救**：逻辑层面的并发冲突——"last writer wins"。配套 skill 也明确说："atomic rename is necessary but not sufficient"。
3. 修复方案（任选其一并说明取舍）：
   - **文件锁**：`fcntl.flock` 包住"读-改-写"整个过程（只在同一台机器上有效）；
   - **乐观并发**：状态里加 `revision` 整数，`commit(state, expected_revision)` 时先重新读取磁盘版本，若 `revision` 已变就拒绝并让调用方重读后重试，成功写入时 `revision += 1`；
   - **按字段合并 / 事件追加**：每个 agent 只追加事件（"A touched app.py"、"B blocked: db down"），由单一 writer 归并成快照，从根本上避免覆盖；
   - **换存储**：讲义练习 4 的 SQLite 自带事务，适合多进程。

### Q12 — 参考答案

1. 实测权限为 `-rw-------`（`0o600`），而同目录的 `schemas/*.json`（用 `write_text` 写）是 `-rw-r--r--`。原因：`mkstemp` 出于安全总是以 `0600` 创建文件，`os.replace` 保留的是临时文件的 inode 和权限。后果：同组的其他用户、以不同用户运行的 CI/reviewer 进程可能读不了状态文件。修复：替换前 `os.chmod(tmp_name, 0o644)`，或复制原文件的权限位。
2. 会留下一个 `agent_state.json.xxxxxxxx` 临时文件，目标文件仍是旧的完整版本（这正是原子写入的意义）。`except` 分支在 `kill -9` 时不会执行，所以启动时应清理匹配 `agent_state.json.*` 的残留临时文件，并在 `.gitignore` 中忽略它们。
3. 对**所在目录**再做一次 `fsync`：`dfd = os.open(path.parent, os.O_RDONLY); os.fsync(dfd); os.close(dfd)`。`fsync(文件)` 只保证文件内容落盘，目录项（"这个名字现在指向新 inode"）的更新在断电时仍可能丢失。
4. 讲义描述的 Hive bug：状态用 `write_text()` 直接写，异常被捕获并静默吞掉，半截写入让会话在损坏状态上恢复且没有任何信号。本节代码的两点不同：写临时文件再原子替换，任何时刻目标文件都是完整的；`except` 里清理临时文件后 `raise` 重新抛出，失败是**响亮的**。我们实测：向 `atomic_write` 传入 `None` 时抛出 `TypeError`，原文件不变，也没有残留临时文件。

### Q13 — 参考回答要点

- **为什么放仓库**：聊天会关闭、被截断、换模型就消失；讲义开场的失败场景就是新会话读到陈旧笔记、重做已完成的工作，甚至重写已完成的文件。仓库文件可版本化、可 diff、可审查，被下一个会话、下一个 agent、下一个 reviewer 共同读取。
- **放什么**：活动任务 id、本次改动文件、假设、阻塞、下一步（以及 schema_version）。
- **不放什么**：原始聊天、token 级推理、情绪推测、采样结果、厂商模型 id；还有 skill 中的硬拒绝：token、PII。大产物只存路径。判断标准是"三个月后 CI 重跑还有没有用"。
- **为什么先写 schema**："Without it, every agent invents new fields, every reviewer learns a new shape, and every CI script has to special-case past versions. With it, a bad write is a refused write."
- **加分点**：数组用空数组而不是 `null`（"`null` is a write-time bug masquerading as data"）；`schema_version` 为迁移留口子；指出本节验证器隐含禁止额外字段，应在 schema 里显式声明。

### Q14 — 参考回答要点

| 步骤 | 防的故障 |
|------|---------|
| 在目标同目录建临时文件 | 保证后续 rename 在同一文件系统内，才能原子 |
| 写入临时文件 | 写一半崩溃只影响临时文件，目标文件完好 |
| `flush` + `fsync` | 把 Python 缓冲区和内核页缓存刷到磁盘，避免"重命名成功但内容还在内存里"，断电后得到空文件或零字节 |
| `os.replace` | 原子地把名字指向新文件：读者要么看到旧版，要么看到新版 |
| （可选）`fsync` 目录 | 让重命名本身在断电后也持久 |
| 异常时删除临时文件并重新抛出 | 不留垃圾、不吞错误 |

- **能否解决并发**：不能。它保证"文件不会被写坏"，不保证"不会丢更新"（见 Q11）。多写者需要锁、乐观并发（revision 号 + compare-and-swap）或单写者的事件归并。
- **加分点**：提到 `mkstemp` 的 `0600` 权限陷阱；Windows 上 `os.replace` 在目标被其他进程打开时可能失败，需要重试。

### Q15 — 参考回答要点

- **问题本质**：至少一次（at-least-once）执行 + 非幂等副作用 = 重复副作用。
- **机制**：
  1. 为每次工具调用生成确定性的调用 ID（例如 `hash(task_id, step, tool, args)`），让同一个逻辑调用在重试时得到同一个 ID；
  2. **执行前**把 `{id, tool, args, status: "pending"}` 追加到 `pending_calls.jsonl`（并 fsync）；
  3. 执行后把结果写入，状态改为 `done`，再写 checkpoint；
  4. 恢复时：ID 为 `done` → 跳过并使用缓存结果；ID 为 `pending` → 结果未知，需要查询外部系统（邮件服务的发送记录）或把幂等键传给下游 API（许多支付/消息 API 支持 idempotency key，由对方去重）；不能确认时宁可升级给人处理，也不要盲目重发。
- **讲义依据**："Safe for reads; dangerous for emails, DB inserts, file uploads"，LangGraph checkpointer 持久化 pending writes 出于同样原因。
- **常见误区**：执行后才记日志；用随机 UUID 作调用 ID（重试时会生成新 ID，起不到去重作用）。

### Q16 — 参考回答要点

- **事件日志**：每次状态变更追加一条事件到 `state.events.jsonl`（时间戳、事件类型、前后值、触发原因、关联工具调用 ID），只追加不修改，用于审计与复盘。
- **快照**：定期（每 N 个事件或每个任务结束）把当前状态原子写入 `state.json`，记录快照对应的事件序号。
- **恢复**：读快照 → 重放快照之后的事件 → 校验 schema 与跨文件一致性 → 继续；讲义："The same shape Postgres uses internally for WAL."
- **大产物分离**：生成的 CSV、长日志、截图存成单独文件或对象存储，状态和事件里只存路径和哈希，checkpoint 保持小而快。
- **工具调用**：配合幂等键（Q15）。
- **复盘**：可以从任意事件序号重放出当时的状态，"replay agent decisions verbatim"。
- **代价**：更多磁盘、事件 schema 也需要版本化；需要日志轮转/压缩策略。
- **加分点**：状态文件和事件日志都纳入 git 或至少定期归档；读快照前先验证 schema，避免在坏快照上恢复。

### Q17 — 参考回答要点

- **版本号是契约**：状态带 `schema_version` 整数；加载时发现旧版本就按迁移链升级，发现**未知**版本（例如比代码还新）就拒绝加载（讲义："the manager refuses to read"）。
- **迁移脚本**：与 schema 变更一起提交，幂等，每次启动都跑（`tools/migrate_state.py`）；先加新字段、兼容读旧字段，再在下个版本删除旧字段（扩展-收缩两步走），避免新旧代码并存时互相读坏。
- **测试**：保留每个历史版本的样例文件，CI 中验证"任意旧版本 → 最新版本"都能迁移并通过验证。
- **与 LangGraph 的关系**：讲义："LangGraph checkpointers. Same idea, different storage"——checkpointer 把图状态持久化到 SQLite/Postgres；当 checkpointer 出问题、需要手工读状态时，你依靠的正是本节这种 schema 纪律。OpenAI Agents SDK 的 session store、Letta memory blocks（第 08 节）也是同一思路。
- **加分点**：迁移前先备份旧文件；迁移本身也用原子写入。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 32 最小 Agent 工作台](../../32-minimal-agent-workbench/docs/zh.md)：本节给第 32 节的三文件加上 schema 与原子写入。
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../07-memory-virtual-context-memgpt/docs/zh.md)：上下文内记忆与外部持久记忆的区别。
- [阶段 14 · 08 记忆块与休眠时计算](../../08-memory-blocks-sleep-time-compute/docs/zh.md)：讲义提到的 Letta memory blocks，同样的 schema 纪律。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：LangGraph checkpointer 是同一思想的框架实现。

### 本节被哪些后续内容用到
- [阶段 14 · 35 面向 Agents 的初始化脚本](../../35-initialization-scripts/docs/zh.md)：会话启动时调用状态管理器做检查。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：读取状态来判定完成。
- [阶段 14 · 40 跨会话 Handoff](../../40-multi-session-handoff/docs/zh.md)：handoff 包从同一 schema 读取。
- [阶段 14 · 29 生产运行时：队列、事件与定时任务](../../29-production-runtimes/docs/zh.md)：事件日志、幂等与重试在生产运行时中的形态。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../16-openai-agents-sdk/docs/zh.md)：session store 的可插拔后端。

### 延伸关键词
`JSON Schema` · `additionalProperties` · `schema_version` · `migration` · `atomic write` · `fsync` · `os.replace` · `lost update` · `optimistic concurrency` · `idempotency key` · `event sourcing` · `snapshot` · `WAL` · `checkpointer`
