# 测验 · 通过隔离与合并契约委派 Agent 任务（Delegate Agent Work with Isolation and Merge Contracts）

> **阶段 14 · Agent 工程 · 第 45 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 并行的前提是独立 | 讲义："Parallel agents save wall time only when the work is independent." 否则只是把一个清楚的任务变成一个失败更快的协调问题 |
| 2 | 并行性测试 | 可委派的四种情况：两项调查回答不同 unknown；两项实现拥有不相交的文件和契约；reviewer 只读检查已完成产物；慢的外部检查与本地工作同时进行 |
| 3 | 必须串行的情况 | 多个 agent 需要同一批文件、同一个未解决的决定，或同一个可变环境 |
| 4 | 工作单元是契约 | 六个字段：Goal（一个可观察结果）、Owner（一个负责人）、Paths（独占写权限）、Dependencies、Proof（交给集成者的精确证据）、Handoff（改了哪些文件、做了哪些决定、剩余风险） |
| 5 | 隔离的三层 | 文件系统隔离（独立 worktree/沙箱）、所有权隔离（契约规定谁能改哪些路径）、状态隔离（独立日志和输出，防止覆盖彼此证据） |
| 6 | 文件系统隔离 ≠ 所有权 | 两个干净的 worktree 仍可能产出相互冲突的设计；共享接口必须在开工前由 merge contract 定下来 |
| 7 | 集成者的六项职责 | 核对 handoff 与分配的 scope；读 proof 输出而非 worker 摘要；按依赖顺序合并；跑跨单元的完整 gate；拒绝隐藏的 scope 扩张；把冲突记录为新决定而非悄悄修改 |
| 8 | 集成不应重做 | 讲义："If integration requires rewriting most of a worker's result, the original decomposition was wrong." |
| 9 | Calibrated autonomy | 在证据和回滚能力强的地方给自由，在后果严重的地方设检查点；改变公开行为、风险、权限或不可逆成本的选择仍归人 |
| 10 | 本节代码的边界 | 路径重叠用 `PurePosixPath` 的父子关系判断；遇到未知依赖或环时 `delegation_plan` 直接抛异常而不是返回 blocked；blocked（路径冲突、缺 proof）时仍输出 waves；`..`、glob、`.` 都没处理 |

### 核心技能（能动手做到）

- [ ] 用"并行性测试"判断一个拆分是真独立还是"看起来独立"，并说出隐藏的共享决定
- [ ] 为每个工作单元写出六字段契约，尤其是独占路径和 proof
- [ ] 读懂 `paths_overlap`：解释 `PurePosixPath.parents` 如何判断父子路径，以及它的盲区
- [ ] 手算 `waves()`，并指出 `delegation_plan` 在异常输入下的崩溃与不一致
- [ ] 实现合并闸门：用每个单元的实际改动文件核对其契约（讲义练习 4）
- [ ] 设计取消规则：某单元失败时，计算需要取消的全部下游单元（讲义练习 5）

---

## 二、基础自测（选择题）

**Q1.** 按讲义的"并行性测试"，下列哪种情况**适合**委派给并行 agent？

- A. 两项实现分别拥有不相交的文件和契约
- B. 团队刚好有多余的 agent 配额
- C. 为了更快，让两个 agent 同时改同一个文件的不同函数
- D. 把同一个尚未决定的产品问题拆给两个 agent 各自实现一版

**Q2.** 为每个 worker 准备独立的 git worktree（文件系统隔离），**不能**保证的是：

- A. worker 不会意外覆盖彼此工作目录中的文件
- B. 每个 worker 有自己的工作目录
- C. 两个 worker 不会对共享接口做出相互冲突的设计
- D. 每个 worker 有自己的检出（checkout）

**Q3.** 按讲义 Build It 的建议，把示例中 `docs` 单元的路径改为 `("app/",)`，`delegation_plan` 的实际结果是：

- A. `status: ready`，因为 `docs` 与 `api` 没有依赖关系
- B. `status: blocked`，`conflicts` 为 `['api and docs overlap at app/api / app/']`
- C. `status: blocked`，冲突发生在 `docs` 与 `integration` 之间
- D. 抛出 `ValueError`

**Q4.** 调用 `delegation_plan([WorkUnit("a", "o", ("x",), ("zz",), "t")])`（依赖了不存在的单元），实际结果是：

- A. 返回 `status: blocked`，并有一个 `missing_dependencies` 字段
- B. 返回 `status: ready`
- C. 返回 `status: blocked`，`waves` 为 `[]`
- D. 抛出 `ValueError: unknown dependency`，函数没有返回计划

**Q5.** `paths_overlap("app/../app/api", "app/api")` 的实际返回值是：

- A. `False`，因为 `PurePosixPath` 不会折叠 `..`
- B. `True`，因为两者指向同一目录
- C. 抛出异常
- D. 取决于操作系统

**Q6.** 下列哪一项**不是**讲义要求集成者（integrator）做的事？

- A. 读 proof 的实际输出，而不只是 worker 的总结
- B. 按依赖顺序合并改动
- C. 把 worker 的结果大部分重写一遍，以统一风格
- D. 把冲突记录为新的决定，而不是悄悄修改

**Q7.** 讲义中的 calibrated autonomy（校准过的自主性）指的是：

- A. 让 agent 自主完成全部工作，人只看最终结果
- B. 每一步都需要人工批准
- C. 给每个 agent 设定一个固定的自主等级，与任务无关
- D. 在证据和回滚能力强的地方给 agent 自由，在后果严重的地方设置人工检查点

**Q8.** 下列哪一种拆分**只是看起来独立**？

- A. 一个只读的调研 worker 产出事实表，另一个 worker 等它完成后再实现
- B. API worker 和文档 worker 并行，但 409 响应的错误体格式还没有决定，两人都要自己定
- C. 一个耗时的外部兼容性检查在后台跑，本地继续开发
- D. reviewer 只读检查一个已经完成的产物

---

## 三、动手 / 代码题

**Q9.** 阅读 `delegation_plan`：

```python
def delegation_plan(units: list[WorkUnit]) -> dict:
    ids = [unit.id for unit in units]
    duplicate_ids = sorted({unit_id for unit_id in ids if ids.count(unit_id) > 1})
    overlap = conflicts(units)
    missing_proof = [unit.id for unit in units if not unit.proof.strip()]
    return {
        "status": "ready" if not duplicate_ids and not overlap and not missing_proof else "blocked",
        "duplicate_ids": duplicate_ids,
        "conflicts": overlap,
        "missing_proof": missing_proof,
        "waves": waves(units) if not duplicate_ids else [],
        "units": [asdict(unit) for unit in units],
    }
```

1. 找出两个问题：一个让函数在某些输入下**崩溃**，一个让 blocked 计划仍然**输出调度**。分别给出触发它们的实测输入和结果。
2. 对比第 44 节的 `plan_document`，说明哪种行为更安全。
3. 写出修正版。

**Q10.** `paths_overlap` 的实现：

```python
def paths_overlap(left: str, right: str) -> bool:
    a = PurePosixPath(left)
    b = PurePosixPath(right)
    return a == b or a in b.parents or b in a.parents
```

1. 解释 `a in b.parents` 的含义，并说明为什么 `app/api` 与 `app/api_v2` 不会被误判重叠（字符串前缀判断就会误判）。
2. 实测下列输入的结果并指出哪些是隐患：`("app/api/", "app/api")`、`("./app/api", "app/api")`、`("app/../app/api", "app/api")`、`("app/**", "app/api/routes.py")`、`(".", "docs/api.md")`、`("App/api", "app/api")`。
3. 写一个更严格的 `normalize(path)`，拒绝 glob、空路径、`.`、越出仓库的路径，并让 `..` 被正确折叠。

**Q11.** 讲义练习 4："Add a merge gate that checks the final changed-file set against all unit contracts." 请实现 `merge_gate(units, changed_by_unit)`：输入每个单元实际改动的文件（例如来自各自 worktree 的 `git diff --name-only`），输出越出契约的改动。用示例计划给出一个通过、一个失败的例子。

**Q12.** 讲义练习 5："Define a cancellation rule for a worker whose dependency becomes invalid." 请：

1. 写出 `cancel_dependents(units, failed)`，返回因 `failed` 失效而需要取消的全部（传递）下游单元；
2. 给出在示例计划中 `api` 失败、`integration` 失败时的结果；
3. 说明除了"取消"之外，取消规则还应该规定哪些事情。

---

## 四、面试高频题

**Q13.**（基础必考）什么时候应该把任务拆给多个并行 agent？什么时候不应该？请举例。

**Q14.**（原理深挖）隔离的三层分别解决什么问题？为什么"每个 agent 一个 worktree"仍然不够？

**Q15.**（工程实践）请设计一个多 agent 并行开发的集成流程：worker 交回什么、集成者检查什么、按什么顺序合并、冲突怎么处理？

**Q16.**（场景设计）要做"注册时防止重复邮件"：涉及 API 实现、数据库迁移、API 文档、前端错误提示四部分。请决定哪些可以并行委派、哪些必须串行或交给人，并写出各单元的契约要点。

**Q17.**（追问型）讲义说"如果集成需要重写 worker 的大部分结果，说明原来的拆分是错的"。在实践中你如何尽早发现拆分错误，而不是等到集成时？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义列出的第二种可委派情况："two implementations own disjoint files and contracts." B 违反开篇原则："Do not delegate because more agents are available."；C、D 分别命中讲义"保持串行"的条件：需要同样的文件、同一个未解决的决定。

### Q2 — 答案：C

讲义："Filesystem isolation does not solve ownership. Two clean worktrees can still produce conflicting designs." A、B、D 都是 worktree 能提供的保障。设计冲突要靠 merge contract 在开工前确定共享接口来解决。

### Q3 — 答案：B

实测：`status: blocked`，`conflicts: ['api and docs overlap at app/api / app/']`。`PurePosixPath("app/")` 规范化为 `app`，它是 `app/api` 的父目录，所以重叠。冲突检查与依赖关系无关（A 错）；`integration` 只拥有 `tests/test_integration.py`，与 `app` 无关（C 错）；不会抛异常（D 错）。值得注意的是，这个 blocked 计划的 `waves` 仍然是 `[['api', 'docs'], ['integration']]`（见 Q9）。

### Q4 — 答案：D

实测抛出 `ValueError: unknown dependency`。`delegation_plan` 只在有重复 ID 时跳过 `waves()`，其余情况都直接调用，而 `waves()` 对未知依赖和环都会抛异常；`delegation_plan` 没有捕获。所以调用方拿不到 blocked 计划，只得到一个崩溃，而且消息没有指出是哪个单元的哪个依赖。A、B、C 都是"如果写得更好"才会出现的结果。

### Q5 — 答案：A

实测 `False`。`PurePosixPath` 是"纯"路径，不访问文件系统，也**不折叠 `..`**（因为在有符号链接的文件系统上，`a/../b` 不一定等于 `b`）；它只会去掉多余的 `/` 和单独的 `.`，所以 `"app/api/"`、`"./app/api"` 都能正确规范化为 `app/api`。于是两个单元可以用 `app/../app/api` 这样的写法绕过重叠检查拥有同一个目录。D 错，`PurePosixPath` 在任何系统上都按 POSIX 规则处理。

### Q6 — 答案：C

讲义："The integrator does not rebuild the work"，并且"If integration requires rewriting most of a worker's result, the original decomposition was wrong." A、B、D 分别是集成者六项职责中的第 2、3、6 项。

### Q7 — 答案：D

讲义："This is calibrated autonomy: the system grants freedom where evidence and rollback are strong, and requires a checkpoint where consequence is high." A 忽略了高后果的决定；B 浪费了自动化的价值；C 的关键错误是"与任务无关"——校准是按后果和可回滚性逐项进行的。

### Q8 — 答案：B

讲义练习 2："Find a proposed parallel split that only looks independent. State the shared decision." B 中两人的文件虽然不相交，但共享一个未解决的决定（错误体格式），并行的结果很可能是两种格式。A 是串行依赖，不是虚假并行；C、D 分别是讲义列出的第四、第三种可委派情况。

### Q9 — 参考答案

1. 两个问题（均已实测）：
   - **崩溃**：`waves(units)` 在未知依赖或环时抛 `ValueError`，`delegation_plan` 没有捕获。输入 `[WorkUnit("a","o",("x",),("zz",),"t")]` → `ValueError: unknown dependency`；输入 `a↔b` 互相依赖 → `ValueError: dependency cycle`。
   - **blocked 仍输出调度**：只有 `duplicate_ids` 会让 `waves` 置空。路径冲突时（Q3）`waves` 是 `[['api', 'docs'], ['integration']]`；缺 proof 时（`proof="  "`）`status: blocked`、`missing_proof: ['a']`，但 `waves: [['a']]`。下游如果只读 `waves` 就开始派发，就会执行一个被判为不安全的计划。
2. 第 44 节的 `plan_document` 用 `"waves": execution_waves(items) if not issues else []`，并且 `validate` 把环/未知依赖转为 issue 而不是让异常逃出——"有任何问题就不输出调度"，并且永远返回一份文档。这更安全：调用方只需检查 `status`，不需要同时处理异常。
3. 修正版（已实际运行验证：未知依赖 → `schedule_error: 'unknown dependency'`、`waves: []`；环 → `'dependency cycle'`；缺 proof → `waves: []`；示例仍为 `ready`，波次不变）：

```python
def delegation_plan(units: list[WorkUnit]) -> dict:
    ids = [u.id for u in units]
    duplicate_ids = sorted({i for i in ids if ids.count(i) > 1})
    overlap = conflicts(units)
    missing_proof = [u.id for u in units if not u.proof.strip()]
    schedule_error, plan_waves = None, []
    if not duplicate_ids:
        try:
            plan_waves = waves(units)
        except ValueError as e:
            schedule_error = str(e)
    blocked = bool(duplicate_ids or overlap or missing_proof or schedule_error)
    return {
        "status": "blocked" if blocked else "ready",
        "duplicate_ids": duplicate_ids,
        "conflicts": overlap,
        "missing_proof": missing_proof,
        "schedule_error": schedule_error,
        "waves": [] if blocked else plan_waves,
        "units": [asdict(u) for u in units],
    }
```

再进一步：让 `waves()` 的异常消息带上具体单元（如 `a depends on unknown units: zz`），像第 44 节那样。

### Q10 — 参考答案

1. `b.parents` 是 `b` 的所有祖先路径序列，例如 `PurePosixPath("app/api/routes.py").parents` 依次是 `app/api`、`app`、`.`。`a in b.parents` 即"a 是 b 的祖先目录"。它按**路径组件**比较，`app/api` 不是 `app/api_v2` 的祖先，所以实测 `False`；如果用 `"app/api_v2".startswith("app/api")` 就会误判为重叠。
2. 实测结果：

| 输入 | 结果 | 评价 |
|------|------|------|
| `"app/api/"`, `"app/api"` | `True` | 正确，尾部 `/` 被规范化 |
| `"./app/api"`, `"app/api"` | `True` | 正确，单独的 `.` 被去掉 |
| `"app/../app/api"`, `"app/api"` | `False` | **隐患**：`..` 不折叠，可绕过检查 |
| `"app/**"`, `"app/api/routes.py"` | `False` | **隐患**：glob 被当作字面目录名 `**` |
| `"."`, `"docs/api.md"` | `True` | **隐患**：拥有 `.` 等于拥有整个仓库，与所有人冲突；空字符串 `""` 也等价于 `.` |
| `"App/api"`, `"app/api"` | `False` | **隐患**：在大小写不敏感的文件系统（macOS、Windows 默认）上它们是同一目录 |

3. 参考实现（已实际运行验证：`app/../app/api` 与 `app/api` → `True`；`.`、`""`、`app/**`、`../secrets` 都被拒绝）：

```python
import posixpath

def normalize(p: str) -> str:
    if not p.strip() or any(c in "*?[" for c in p):
        raise ValueError(f"invalid ownership path: {p!r}")
    n = posixpath.normpath(p)                     # 折叠 . 和 ..
    if n in (".", "..") or n.startswith("../") or n.startswith("/"):
        raise ValueError(f"path escapes or owns repo root: {p!r}")
    return n

def paths_overlap_strict(left: str, right: str) -> bool:
    a, b = normalize(left), normalize(right)
    return a == b or b.startswith(a + "/") or a.startswith(b + "/")
```

`posixpath.normpath` 按字符串折叠 `..`，对于"仓库内的所有权路径"这种不涉及符号链接的场景是合适的；拼接 `"/"` 后再做前缀判断就避免了 `app/api` 与 `app/api_v2` 的误判。大小写问题可以在 normalize 中统一 `lower()`（如果团队约定仓库路径不区分大小写），或在 lint 中禁止只差大小写的路径。

### Q11 — 参考答案

```python
def owns(unit: WorkUnit, path: str) -> bool:
    f = normalize(path)
    return any(f == normalize(p) or f.startswith(normalize(p) + "/") for p in unit.paths)

def merge_gate(units: list[WorkUnit], changed_by_unit: dict[str, list[str]]) -> list[str]:
    by_id = {u.id: u for u in units}
    findings = []
    for uid, files in changed_by_unit.items():
        if uid not in by_id:
            findings.append(f"unknown unit {uid} reported changes")
            continue
        for f in files:
            if not owns(by_id[uid], f):
                findings.append(f"{uid} changed {f} outside its contract")
    return findings
```

实测（用示例计划）：

- 通过：`{"api": ["app/api/accounts.py", "tests/test_api.py"], "docs": ["docs/api.md"], "integration": ["tests/test_integration.py"]}` → `[]`
- 失败：`{"api": ["app/api/accounts.py", "app/models/user.py"], "docs": ["docs/api.md", "README.md"]}` → `['api changed app/models/user.py outside its contract', 'docs changed README.md outside its contract']`

要点：`changed_by_unit` 必须来自每个 worktree 的真实 diff（`git diff --name-only <base>...<branch>`），而不是 worker 的自述——这对应集成者职责第 2 条"读 proof 输出而不是摘要"和第 5 条"拒绝隐藏的 scope 扩张"。还应再检查一次"合并后的总改动集合 ⊆ 所有单元路径的并集"，防止集成者自己在合并时引入契约外的改动。

### Q12 — 参考答案

1. 参考实现（反向图 + 深度优先遍历）：

```python
def cancel_dependents(units: list[WorkUnit], failed: str) -> list[str]:
    rev: dict[str, set[str]] = {}
    for u in units:
        for d in u.depends_on:
            rev.setdefault(d, set()).add(u.id)
    out, stack = set(), [failed]
    while stack:
        for nxt in rev.get(stack.pop(), ()):
            if nxt not in out:
                out.add(nxt)
                stack.append(nxt)
    return sorted(out)
```

2. 实测：`api` 失败 → `['integration']`；`integration` 失败 → `[]`（没有下游）。注意 `docs` 不受影响，它和 `api` 在同一波但互不依赖。
3. 取消规则还应规定：
   - **什么算"失效"**：proof 失败、超时、worker 越界（merge gate 报告）、依赖单元的契约被修改（共享接口变了）；
   - **对已在运行的下游如何处理**：立即停止还是允许完成后丢弃；停止时要保留其日志与产物（状态隔离），供事后分析；
   - **对已完成的下游如何处理**：结果作废，需要在依赖修复后重跑 proof；
   - **谁来决定重启**：若失效源于产品决定变化，回到人类检查点（calibrated autonomy），而不是自动重派；
   - **记录**：把取消原因写进 handoff 和计划状态，避免下一个会话误以为这些单元已完成。

### Q13 — 参考回答要点

- **应该并行**（讲义四种情况）：两项调查回答不同的 unknown；两项实现拥有不相交的文件和契约；reviewer 只读检查已完成产物；慢的外部检查与本地工作同时进行。
- **不应该并行**：需要改同一批文件；依赖同一个未解决的决定；共用一个可变环境（同一个数据库、同一个端口、同一份缓存）。
- **例子**：API 实现与 API 文档在契约（409 + 错误体）已定的前提下可以并行；在契约未定时并行，就会出现两种格式。
- **原则**：讲义："Do not delegate because more agents are available." 并行省的是墙钟时间，代价是协调成本和更快的失败。
- 加分点：并行前先问"集成时需要做多少工作"，如果预期集成需要大量调和，说明不该拆。

### Q14 — 参考回答要点

- **文件系统隔离**（worktree / 沙箱）：防止**意外**的共享编辑——一个 worker 的未提交改动不会出现在另一个 worker 的目录里。
- **所有权隔离**（契约中的独占路径）：防止**有意**的重叠编辑——两个 worker 都"合理地"认为自己应该改 `app/accounts.py`。
- **状态隔离**（独立日志、输出目录）：防止一个 worker 覆盖另一个的证据，例如两人都写 `feedback_record.jsonl` 或 `outputs/verification/T-001.json`。
- **为什么 worktree 不够**：它只保证"物理上分开"，不保证"逻辑上一致"。两个干净的 worktree 可以各自引入一个不同的错误体格式、各自改一个共享常量，合并时要么冲突、要么更糟——不冲突但语义矛盾。讲义："The merge contract must resolve shared interfaces before work begins."
- 加分点：本节代码只实现了所有权隔离的一部分（路径重叠检查），文件系统隔离和状态隔离要靠运行时（worktree、按单元分目录的输出）实现。

### Q15 — 参考回答要点

- **worker 交回**（handoff）：改动文件列表（来自 diff）、做出的决定、剩余风险、proof 的原始输出（命令、退出码、日志路径）。
- **集成者检查**（讲义六项）：
  1. handoff 与分配的 scope 一致——merge gate 用真实 diff 核对路径（Q11）；
  2. 读 proof 的实际输出，必要时重跑；
  3. 按依赖顺序合并（先契约/上游，再下游）；
  4. 合并后跑跨单元的完整 gate；
  5. 拒绝隐藏的 scope 扩张；
  6. 冲突记录为新决定，交给相应负责人（必要时是人）。
- **冲突处理**：文本冲突说明所有权划分有漏洞；语义冲突（各自对接口做了不同假设）说明 merge contract 不完整——两者都应回溯修正拆分，而不是集成者"看着改"。
- **角色**：集成者最好是只读的 reviewer（第 39 节：实现者与评分者分离），不在合并时写新代码。
- 加分点：讲义引用的 Contract Net Protocol——任务分配与结果回报都通过明确的契约消息完成，这与"工作单元即契约"同一思路。

### Q16 — 参考回答要点

- **先串行的部分**：
  1. `contract`：定义 409 与错误体格式、邮件规范化规则——规范化规则改变产品行为，是**人类决定**；
  2. `migration`（数据库唯一约束、清理已有重复）：不可逆，需人类审批；它依赖规范化决定。
- **契约确定后可并行**：
  - `api`：独占 `app/api/**` 与 `tests/test_api.py`，proof 为聚焦测试；
  - `docs`：独占 `docs/api.md`，proof 为文档检查（最好包含对 409 示例的校验，而不仅是链接检查）；
  - `frontend`：独占前端错误提示相关文件，proof 为组件测试或浏览器旅程（指定视口与期望状态）。
- **集成**：`integration` 依赖以上全部，由只读 reviewer 执行完整 gate 和 merge gate。
- **不能并行的诱惑**：在规范化规则未定时让 `api` 与 `migration` 并行——二者共享一个未解决的决定。
- 加分点：给每个单元写出六字段契约，并说明各单元的输出目录相互独立（状态隔离）。

### Q17 — 参考回答要点

- **开工前**：
  - 用"共享决定清单"检查：把每个单元需要做的决定列出来，出现在两个单元里的决定必须先上移到 contract 单元或交给人；
  - 路径重叠检查之外，再检查**接口重叠**：两个单元是否读写同一个类型、常量、配置键、数据库表；
  - 预估集成工作量，如果预期要大量调和，就不拆。
- **执行中**：
  - 要求 worker 在改动契约外的接口前停下来上报（scope contract + gate）；
  - 早期交付小的中间产物（如接口桩、契约测试），集成者尽早做一次"试合并"；
  - 监控 merge gate：越界改动是拆分错误的早期信号。
- **事后**：把"这次拆分为什么错"记录为改进项，更新拆分检查清单（第 46 节：把纠正转化为系统改进）。
- 常见误区：用"集成者多花点时间修一修"掩盖拆分问题，下次还会重演。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 44 制定有证据支撑的执行计划](../../44-plan-from-evidence/docs/zh.md)：讲义列出的先修课；`evidence-plan.json` 是本节委派的输入，同一波次的工作项是候选的并行单元。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)：讲义列出的先修课；只读集成审查与 reviewer 角色。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：每个工作单元的独占路径即一份 scope contract。
- [阶段 14 · 43 在 Agent 编写代码前界定任务](../../43-frame-the-task-before-code/docs/zh.md)：human unknown 决定了哪些决定不能交给 worker。

### 本节被哪些后续内容用到
- [阶段 14 · 46 把每一次对 Agent 的纠正转化为系统改进](../../46-turn-feedback-into-system/docs/zh.md)：把错误的拆分沉淀为拆分检查规则。
- [阶段 14 · 28 Orchestration 模式：监督者、Swarm 与层级结构](../../28-orchestration-patterns/docs/zh.md)：多 agent 编排的更多模式。
- [阶段 16 · 01 为什么需要多 Agent？](../../../16-multi-agent-and-swarms/01-why-multi-agent/docs/zh.md)：多智能体系统何时值得引入。
- [阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../17-claude-agent-sdk/docs/zh.md)：在 SDK 层面派生 subagent。

### 延伸关键词
`git worktree` · `exclusive ownership` · `merge contract` · `integrator` · `merge gate` · `filesystem / ownership / state isolation` · `calibrated autonomy` · `mixed-initiative` · `Contract Net Protocol` · `cancellation rule` · `PurePosixPath.parents` · `posixpath.normpath`
