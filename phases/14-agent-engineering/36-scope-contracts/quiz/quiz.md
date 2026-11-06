# 测验 · Scope Contracts 与任务边界（Scope Contracts and Task Boundaries）

> **阶段 14 · Agent 工程 · 第 36 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Scope creep（范围蔓延） | 每一处改动"当时都有合理理由"，合在一起却是另一个没被评审过的变更；agent 会善意地叙述每一步，所以它是**最缺乏监控**的失败模式 |
| 2 | 解法不是更严的 prompt | 讲义："The fix is not a stricter prompt"——而是一份**落盘的合同** + 一个把结果与承诺对比的**检查** |
| 3 | 合同的七个字段 | `task_id`、`goal`、`allowed_files`、`forbidden_files`、`acceptance_criteria`、`rollback_plan`、`approvals_required` |
| 4 | 负空间是合同的一半 | 没有 `forbidden_files` 的合同是不完整的；代码中 forbidden 的判断**优先于** allowed |
| 5 | 用 glob 而非原始路径 | 文件会在会话间被重构移动，glob（`app/**/*.py`）能扛住；但本节用 `fnmatch` 实现，`*` 会跨越 `/`、`**` 不能匹配零层目录 |
| 6 | Rollback 也是 scope 的一部分 | 写回滚计划会逼作者想清楚"会坏在哪"；无法回滚的合同不应被批准 |
| 7 | Scope check 就是 diff check | 读取 touched files、allowed/forbidden globs、实际跑过的 acceptance 命令，每个违规是一个带标签的 finding，交给 verification gate |
| 8 | 两个高度：feature list 与 task contract | 合同只约束"本任务能写哪些文件"；`feature_list.json` 约束"本会话做哪个 feature"，同一时间最多一个 `in_progress` |
| 9 | 严重度分层 + violation budget | 代码中 forbidden → `block`，普通越界 → `warn`，文档类越界 → `info`；`warn` 的数量超过预算才判失败 |
| 10 | 时间/网络预算与最小权限合并 | `time_budget_minutes`、`network_egress`（`None` 不执行 / `[]` 全拒 / 列表为白名单）；多合同合并：allowed 交集、forbidden 并集、时间取 min、审批累加 |

### 核心技能（能动手做到）

- [ ] 为一个具体任务写出完整的 scope contract，七个字段一个不缺，尤其能写出合理的 `forbidden_files` 与可执行的 `rollback_plan`
- [ ] 读懂 `scope_check` 的四路分类（forbidden / in-scope / soft / off-scope），能预测任意一组 touched files 的 findings 与 `passed()`
- [ ] 说清 `fnmatch` 与真正 glob（gitignore、`pathlib.full_match`）在 `*`、`**` 上的语义差异，并预判它导致的误判
- [ ] 按最小权限原则合并两份合同，并指出"对 glob 字符串求交集"在语义上的漏洞
- [ ] 把 violation budget 改成按文件计数、给 `scripts/**` 等路径族加硬性 block（讲义练习 2）
- [ ] 写出 `feature_list.json` 的启动检查：最多一个 `in_progress`、`active` 与合同 `task_id` 一致

---

## 二、基础自测（选择题）

**Q1.** 讲义说 scope creep 是 agent 工作中"最缺乏监控（most under-monitored）"的失败模式，主要原因是：

- A. agent 对每一步都给出善意且看似合理的叙述，单看每一步都说得通，合起来却是一个与评审时不同的变更
- B. scope creep 极少发生，不值得专门监控
- C. 测试会自动发现所有越界改动
- D. 越界改动总会让 agent 崩溃报错，所以大家默认不需要额外监控

**Q2.** 在本节的 `scope_check` 中，如果某个路径**同时**匹配 `allowed_files` 和 `forbidden_files`，它会被归入：

- A. `in_scope_writes`，因为 allowed 是正向授权
- B. `soft_off_scope_writes`，按 info 处理
- C. 两个列表都会出现，产生两条 finding
- D. `forbidden_writes`，产生一条 `block` 级 finding

**Q3.** 本节用 `fnmatch.fnmatch(path, pattern)` 匹配 glob。对模式 `lib/**/*.py`，下列哪个路径**不会**被匹配？

- A. `lib/a/foo.py`
- B. `lib/foo.py`
- C. `lib/a/b/foo.py`
- D. `lib/x/y.py`

**Q4.** 项目级合同的 `network_egress = None`，任务级合同的 `network_egress = []`。按本节 `merge_contracts` 的规则，合并结果是：

- A. `None`，因为有一方不执行限制
- B. `["*"]`，表示全部放行
- C. `[]`，即全部拒绝（deny-all），任何外部访问都会产生 `block`
- D. 抛出异常，因为两者类型不同

**Q5.** 一份合同 `allowed_files=["app.py"]`、`violation_budget=1`，没有 forbidden，也不涉及文档路径。一次运行写了 `app.py` 和 10 个 `lib/x0.py … lib/x9.py`，并跑了全部 acceptance 命令。按本节代码，`scope_check(...).passed()` 的结果是：

- A. `False`，因为 10 个越界文件大于预算 1
- B. `False`，因为越界写入是 `block` 级别
- C. `False`，因为 `over_budget=True`
- D. `True`，因为 10 个越界文件只被合并成**一条** `warn` finding，1 不大于预算 1

**Q6.** 关于 `feature_list.json`，讲义规定的不变式与执行方式是：

- A. 同一时间最多一个 `in_progress`；这本身是一个启动检查，若出现两个，会话拒绝启动，直到人类解决
- B. 同一时间最多三个 `in_progress`，以便并行推进
- C. feature list 是写在 prompt 里的一句提醒，agent 自觉遵守即可
- D. `in_progress` 的数量不限，只要每个 feature 都有 `done_when`

**Q7.** 运行 `python3 code/main.py`，creep 那次运行输出 `passed=False over_budget=False`。`over_budget` 为 `False` 的原因是：

- A. creep 运行耗时 42.1 分钟，没超过 60 分钟的项目预算
- B. 合并后的 `violation_budget` 是 1，越界数量没超过
- C. 它没有任何 `warn` 级 finding：`README.md` 落入文档软路径（info），`scripts/release.sh` 和 `migrations/001_init.sql` 落入 forbidden（block）
- D. `over_budget` 只在 clean 运行时才会计算

**Q8.** 讲义坚持 feature list 必须是一个**文件**而不是一条聊天消息，理由是：

- A. JSON 文件比聊天消息更省 token
- B. 聊天会滚出上下文窗口，而文件能跨会话、跨 agent 持久存在，并且可以被启动检查机械地读取
- C. 聊天消息无法包含中文
- D. 只有文件才能被 LLM 读懂

---

## 三、动手 / 代码题

**Q9.** 阅读 `merge_contracts` 中的这一行：

```python
        allowed_files=sorted(set(parent.allowed_files) & set(child.allowed_files)),
```

项目级合同 `allowed_files=["app.py", "lib/**/*.py"]`、`violation_budget=1`；任务级合同 `allowed_files=["lib/auth/*.py"]`、`violation_budget=1`。agent 只修改了 `lib/auth/login.py`。

1. 合并后的 `allowed_files` 是什么？`scope_check` 会给出什么 finding，`passed()` 是多少？
2. 这说明"对 glob 字符串求交集"有什么语义问题？
3. 给出一个正确实现"两份合同都必须允许该路径"的方案。

**Q10.** 讲义说 violation budget 让"minor scope slips within budget are surfaced as warnings; only when the budget is exceeded does the merge gate refuse"。阅读：

```python
    if off_scope:
        findings.append(Finding("scope.off_scope", "warn", f"off-scope writes: {off_scope}"))
    ...
    warn_count = sum(1 for f in findings if f.severity == "warn")
    over_budget = warn_count > contract.violation_budget
```

1. 这个实现的预算是按什么计数的？它和讲义的意图有何偏差？（结合 Q5）
2. 写一个 `scope_check_v2(contract, run, hard=("scripts/**", "migrations/**", "config/prod/**"))`：预算按**越界文件数**计；越界路径命中 `hard` 时直接 `block`（讲义练习 2 的"docs 软失败、scripts 硬失败"）。

**Q11.** `main()` 结尾调用了两次 `archive`：

```python
def archive(report: ScopeReport) -> Path:
    out = HERE / "closed" / f"{report.task_id}.json"
    ...
    archive(clean_report)
    archive(creep_report)
```

1. 运行结束后 `code/closed/` 里有几个文件？内容属于哪次运行？
2. 讲义说运行后会得到 `scope_report.json`、合同关闭后归档到 `outputs/scope/closed/`、`scope_check` 返回 `(violations, in_scope, off_scope)`。与代码逐项对照，指出不一致之处。
3. 怎样修改归档，才能让同一 task 的多次运行都留下可审计的记录？

**Q12.** 讲义把"一次只做一个 feature"从 prompt 里的一句话变成"从磁盘读出的值 + 由 gate 强制的检查"，但本节代码并没有实现 `feature_list.json`。请写 `check_feature_list(fl: dict, task_id: str | None) -> list[str]`，至少检查：status 合法、最多一个 `in_progress`、`active` 存在且就是那个 `in_progress`、scope contract 的 `task_id` 等于 `active`。并给出讲义示例数据上的结果，以及把 `full-text-search` 也改成 `in_progress` 后的结果。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 scope contract？它包含哪些字段？为什么讲义说 `forbidden_files` 是"合同的一半"、`rollback_plan` 也是 scope 的一部分？

**Q14.**（原理深挖）为什么"在 prompt 里写'请不要改无关文件'"挡不住 scope creep，而"磁盘上的合同 + diff 检查"可以？请从 agent 行为、可审计性、强制点三个角度说明，并说明它与 verification gate 的关系。

**Q15.**（工程实践）一个仓库同时有项目级合同和任务级合同。请设计合并语义（allowed、forbidden、时间、网络、审批、violation budget、软路径），并指出本节代码合并实现中至少两个会导致"过宽"或"过窄"的问题。

**Q16.**（场景设计）你要在团队的 Claude Code + GitHub PR 流程里落地 scope contract。请给出从任务创建、agent 执行、CI 检查到合并归档的完整设计，并说明如何避免这个 gate "因为太烦被团队关掉"。

**Q17.**（追问型）agent 在修登录 bug 时发现必须改一下数据库驱动（在合同的 allowed 之外）才能修好。它应该怎么做？系统层面怎么支持这种情况？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Each touch had a plausible reason in the moment. Together they are a different change than the one that was reviewed."以及"the agent narrates each step in good faith"。正因为每一步的叙述都合理，人类逐步看日志时不会警觉，只有把**总 diff** 与**承诺**对比才能发现。B 与事实相反（讲义举的"修登录 bug 却改了 5 处"是常态）；C 错，测试只验证功能，不检查"改了不该改的文件"，越界改动完全可能让测试照样通过；D 错，scope creep 是**静默**的，不会崩溃。

### Q2 — 答案：D

代码中的判断顺序：

```python
        if matches_any(path, contract.forbidden_files):
            forbidden.append(path)
        elif matches_any(path, contract.allowed_files):
            in_scope.append(path)
```

forbidden 先判，所以命中 forbidden 就不会再看 allowed。这是"拒绝优先（deny overrides allow）"的标准做法：例如 allowed 写了 `app/**`，forbidden 写了 `app/migrations/**`，迁移文件应被拦下。A 是"allow 优先"，会让负空间形同虚设；B 只有前两者都不命中时才轮到软路径；C 错，`if/elif` 保证每个路径只进一个桶。

### Q3 — 答案：B

`fnmatch` 不认识 `**`，它把 `**` 当作两个 `*`，而每个 `*` 可以匹配任意字符（**包括 `/`**）。`lib/**/*.py` 实际要求 "`lib/` + 任意 + `/` + 任意 + `.py`"，即 `lib/` 之后**至少还要有一个 `/`**。实际运行：

```text
lib/foo.py    lib/**/*.py  False
lib/a/foo.py  lib/**/*.py  True
```

而在 gitignore / `pathlib.PurePath.full_match`（Python 3.13）语义中，`**/` 可以匹配零层目录，`lib/foo.py` 是会匹配的。反过来，`fnmatch` 下 `app/*.py` 会匹配 `app/sub/x.py`（`*` 跨了 `/`），比真 glob 更宽。同理，代码默认的软路径 `**/*.md` 匹配不到根目录的 `README.md`，所以默认值里又单独加了 `"README.md"`。A、C、D 都至少含两个 `/`，均匹配。

### Q4 — 答案：C

```python
def _merge_egress(a, b):
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return sorted(set(a) & set(b))
```

`None` 表示"这一方不执行限制"，所以服从另一方，结果是 `[]`。`[]` 在 `scope_check` 中不是"不检查"：只要 `run.network_hosts` 非空，所有 host 都不在白名单里，产生 `network.unallowed_host`（block）。实际验证：`_merge_egress(None, []) == []`、`_merge_egress([], ["a"]) == []`（deny-all 保持 deny-all）。A 把 `None` 当成了"更强"的一方，恰好违背最小权限；B、D 代码中不存在。

### Q5 — 答案：D

实际运行结果：`passed=True over_budget=False`，`len(off_scope_writes)=10`。所有越界路径被收集到同一个列表，只追加**一条** `scope.off_scope` finding，`warn_count = 1`，`1 > 1` 为假。所以预算实际上是"warn 类 finding 的条数"而不是"越界文件个数"：预算 ≥ 1 时，越界 1 个文件和越界 100 个文件的结果一样。A 是讲义意图下的合理结果，但不是代码的行为；B 错，普通越界在代码里是 `warn`，只有 forbidden 是 `block`；C 错，`over_budget` 为 False。详见 Q10。

### Q6 — 答案：A

讲义："the invariant 'at most one `in_progress`' is itself a startup check (Phase 14 · 33): if the list shows two, the session refuses to start until a human resolves it."这正是本阶段反复强调的"把规则从 prompt 变成可执行约束"。B 违背"一次一个 feature"；C 正是讲义要否定的做法（prompt 中的规则 agent 可以合理化绕过）；D 混淆了 `done_when`（完成判据）与并发约束。

### Q7 — 答案：C

creep 的 touched files 分类结果：`app.py` → in-scope；`README.md` → 不在 allowed，命中 `docs_paths_soft` 里的 `"README.md"` → info；`scripts/release.sh`（来自项目级合同）与 `migrations/001_init.sql`（命中任务级的 `migrations/**`）→ forbidden → block。没有任何路径落入普通 off-scope，所以没有 `warn`，`warn_count = 0`，不超预算。它的 `passed=False` 来自 4 条 block：forbidden、acceptance 未运行、42.1 分钟超过 30 分钟（合并后取 min）、访问了 `evil.example`。A 错，合并后预算是 `min(60, 30) = 30`；B 错，合并后 `violation_budget = min(1, 0) = 0`；D 错，两次运行都计算。这个 demo 的副作用是：**`warn` + 预算的路径在 demo 中从未被触发过**。

### Q8 — 答案：B

讲义："the feature list is a file, not a chat message, because the chat scrolls out of context and the file persists across sessions and across agents."并且 handoff（第 40 节）会把完成的 feature 写回 `done`，下一个会话打开时看到的是准确的看板。A 不是理由；C、D 都是错误陈述。

### Q9 — 参考答案

1. 实际运行：

   ```text
   merged allowed: []
   [('warn', 'scope.off_scope', "off-scope writes: ['lib/auth/login.py']")] True
   ```

   `{"app.py", "lib/**/*.py"} ∩ {"lib/auth/*.py"} = ∅`，合并后**什么都不允许**；`lib/auth/login.py` 成为普通越界（warn），但由于预算 `min(1,1)=1`，`passed()` 仍为 `True`。
2. glob 是"路径集合"的描述，**字符串相等 ≠ 集合包含关系**。`lib/auth/*.py` 描述的集合明明是 `lib/**/*.py` 的子集，按语义交集应当是 `lib/auth/*.py`，但字符串交集为空——结果"过窄"。反过来，两个字符串相同但含义不同的情况不会出现，所以这个实现只会错杀，不会漏放；但错杀后又被预算放行，等于合同失去意义。本节 demo 恰好两边都写了 `app.py`、`test_app.py`，所以没暴露问题。
3. 正确做法是**不在 glob 层面求交集，而在路径层面求"与"**：保留两份 allowed 列表，检查时要求路径同时被两份列表匹配。

   ```python
   def allowed_by_all(path, contracts):
       return all(matches_any(path, c.allowed_files) for c in contracts)
   ```

   实际运行：`allowed_by_all("lib/auth/login.py", [parent, child]) == True`，`allowed_by_all("app.py", [parent, child]) == False`（任务级不允许 app.py，正确）。实现上可以把合并后的合同表示为 `allowed_files_all_of: list[list[str]]`；forbidden 的并集则可以直接拼接列表（字符串并集对"任一禁止即禁止"是语义正确的）。

### Q10 — 参考答案

1. 计数单位是"`warn` 级 finding 的条数"。由于所有普通越界只生成一条 finding，`warn_count` 最大只能是 1（本节代码中只有 `scope.off_scope` 一种 warn）。于是：预算 = 0 时，任何越界都失败；预算 ≥ 1 时，任意数量的越界都通过。讲义的意图是"小的越界在预算内只报警，超出才拒绝"，应当按越界**文件数**（或越界事件数）计。
2. 参考实现（已在临时目录实际运行）：

   ```python
   def scope_check_v2(contract, run, hard=("scripts/**", "migrations/**", "config/prod/**")):
       rep = scope_check(contract, run)
       hard_hits = [p for p in rep.off_scope_writes if matches_any(p, list(hard))]
       soft = [p for p in rep.off_scope_writes if p not in hard_hits]
       if hard_hits:
           rep.findings.append(Finding("scope.hard_off_scope", "block", f"hard off-scope: {hard_hits}"))
       rep.over_budget = len(soft) > contract.violation_budget
       return rep
   ```

   结果：10 个越界 → `passed=False, over_budget=True`；1 个越界 → `passed=True, over_budget=False`（在预算内）；写了 `scripts/deploy.sh` → `passed=False`（出现 `block`）。更干净的写法是在 `scope_check` 内部先按路径族分桶，避免同一路径既报 warn 又报 block；路径族与严重度的映射应写在**合同里**（讲义："This asymmetry has to live in the contract, not in the runtime"）。

### Q11 — 参考答案

1. 只有 **1 个**文件 `closed/T-001.json`，内容是 creep 运行（`"passed": false`）。两份报告的 `task_id` 都是合并后合同的 `T-001`，第二次 `write_text` 覆盖了第一次，clean 运行的记录丢失。
2. 不一致之处：
   - 讲义/mission 说输出 `scope_report.json`，代码不生成这个文件，生成的是 `code/closed/T-001.json`；
   - 讲义说归档到 `outputs/scope/closed/`，代码写到 `HERE / "closed"`，即 `code/closed/`；
   - 讲义说 `scope_check` 返回 `(violations, in_scope, off_scope)`，代码返回 `ScopeReport` dataclass（多了 forbidden、soft、missing、findings、over_budget）；
   - 讲义说有"diff parser 把 touched files + commands 变成 RunSummary"，代码中 `RunSummary` 是手工构造的，没有解析器；mission 还提到 schema validator，代码中没有；
   - mission 把"time budgets, network egress"列为 out of scope，但代码已经实现了它们。
3. 让文件名唯一并且不可覆盖，例如 `closed/{task_id}/{run_id}.json`（run_id 用时间戳或 UUID），或追加写入 `closed/{task_id}.jsonl`；同时把合同本体、touched files、commands 一起写进去，归档才可审计。另外，`closed_at=time.time()` 让输出不可复现，测试时可注入时钟。

### Q12 — 参考答案

```python
def check_feature_list(fl: dict, task_id: str | None = None) -> list[str]:
    errors = []
    feats = fl.get("features", [])
    ids = [f["id"] for f in feats]
    if len(ids) != len(set(ids)):
        errors.append("duplicate feature id")
    allowed_status = {"todo", "in_progress", "done", "blocked"}
    for f in feats:
        if f.get("status") not in allowed_status:
            errors.append(f"{f['id']}: unknown status {f.get('status')!r}")
    in_prog = [f["id"] for f in feats if f.get("status") == "in_progress"]
    if len(in_prog) > 1:
        errors.append(f"more than one in_progress: {in_prog}")
    active = fl.get("active", "")
    if active:
        if active not in ids:
            errors.append(f"active {active!r} not in features")
        elif in_prog and in_prog != [active]:
            errors.append(f"active {active!r} != in_progress {in_prog}")
        if task_id is not None and task_id != active:
            errors.append(f"scope contract task_id {task_id!r} != active {active!r}")
    return errors
```

实际运行：讲义示例数据 + `task_id="import-pdf"` → `[]`；把 `full-text-search` 改成 `in_progress`、`task_id="full-text-search"` →

```text
["more than one in_progress: ['import-pdf', 'full-text-search']",
 "active 'import-pdf' != in_progress ['import-pdf', 'full-text-search']",
 "scope contract task_id 'full-text-search' != active 'import-pdf'"]
```

非空即拒绝启动会话。`active` 为空时按讲义应"选一个 `todo` 并写回"，这一步应由初始化脚本（第 35 节）完成并落盘，而不是让 agent 在对话里口头决定。

### Q13 — 参考回答要点

- **定义**：每个任务一份落盘文件，agent 在任务开始时读、verifier 在任务结束时读，把"别越界"从愿望变成检查。
- **字段**：`task_id`（关联看板）、`goal`（评审者可验证的一句话）、`allowed_files`（glob）、`forbidden_files`（glob）、`acceptance_criteria`（证明完成的测试命令）、`rollback_plan`（运维可执行的一段话）、`approvals_required`（范围外需要人类签字的动作）。生产中再加 `time_budget_minutes`、`network_egress`、`violation_budget`、严重度映射。
- **forbidden 是一半**：allowed 只说"能去哪"，forbidden 说"绝不能碰"（发布脚本、迁移、生产配置）；且 forbidden 应优先于 allowed，否则宽松的 allowed glob 会把高危路径包进去。
- **rollback 是 scope**：写回滚计划会逼你想清楚影响面；"无法回滚的合同不应被批准"。`see runbook` 这种空话在 skill 中是 hard reject。
- 加分点：提到 glob 优于原始路径（扛重构），并能指出 `fnmatch` 的 `**` 语义陷阱。

### Q14 — 参考回答要点

- **agent 行为**：越界的每一步都有当下合理的理由，模型会在叙述中把它合理化；prompt 规则是"软约束"，上下文一长就被稀释或被更紧迫的目标压过。
- **可审计性**：合同是一个版本化文件，评审者能看到"承诺了什么"；diff 是客观事实。二者对比得到的是带标签的 finding（文件 + 原因），而不是"感觉它改多了"。
- **强制点**：检查发生在 agent 之外（CI、merge gate），不依赖模型自觉；违规可以 `block` 合并、触发中断。
- **与 verification gate 的关系**：讲义流程图中 scope 检查是 verification gate 的前置输入——in scope 才进入验证，否则 block + 提出开放问题。scope 回答"改的是不是该改的"，verification 回答"改得对不对"，两者正交。
- 加分点：引用讲义中的实践数据——某实践者在调用 agent 前先写 YAML 合同，三周内"钻牛角尖"率从 52% 降到 21%，且没有换模型（讲义："The contract did the work, not the model"）。

### Q15 — 参考回答要点

- **合并语义（讲义）**：`allowed_files` 交集（两份都允许才允许）；`forbidden_files` 并集（任一禁止即禁止）；`time_budget_minutes` 取最小；`approvals_required` 累加；`network_egress`：`None` 服从另一方、两个列表求交、`[]` 保持全拒。
- **代码中的问题**：
  - allowed 对 glob **字符串**求交集，`lib/**/*.py ∩ lib/auth/*.py = ∅`，过窄（见 Q9）；应在路径层面对两份列表分别匹配再取"与"。
  - `docs_paths_soft` 取**并集**：软路径会把越界降级为 info，并集等于放宽，不符合最小权限；应取交集（或让严重度取更严的一方）。
  - `violation_budget` 取 min 是对的，但预算本身按 finding 条数计（见 Q10），合并后依然"过宽"。
  - `goal`、`rollback_plan` 用 `child or parent` 二选一，项目级的通用回滚步骤可能被丢掉；更稳妥的是拼接。
- 加分点：把合并语义写进合同 schema（讲义："State this in the contract schema so the merge is mechanical and reviewable"），并为合并函数写性质测试（合并结果永远不比任一方更宽）。

### Q16 — 参考回答要点

- **任务创建**：从 `feature_list.json` 选定 `active` feature，用 `/scope` 类命令生成合同并作为会话上下文钉住；subagent 行动前先读合同。
- **执行期**：时间预算到点时运行时拒绝继续；网络出口按白名单；需要越界时通过 LangGraph interrupt 之类的机制停下来问人。
- **CI**：合同作为 PR 中的文件提交，CI 对 merge diff 跑 scope checker；非零退出码阻止合并；结果写入 PR 评论。
- **归档**：任务关闭后把合同和报告归档到 `outputs/scope/closed/`，且每次运行一个文件（避免 Q11 的覆盖问题）。
- **避免被关掉**：分级严重度（docs `warn`/`info`，scripts、migrations、生产配置 `block`）；violation budget 让小越界只报警；误报可以通过"修改合同 + 人工批准"快速解决；定期看指标（越界率、误报率）。讲义："The budget is the difference between a gate that ships and a gate that gets disabled by the team that hated it."
- 常见误区：一上来就全部 `block`，一周后团队绕过或关掉检查。

### Q17 — 参考回答要点

- **agent 侧**：不应"顺手改了再说"。应停下，产出一个开放问题（讲义流程图中的 "block + open question"）：说明需要改哪个文件、为什么、影响与回滚方式。
- **系统侧**：
  - 合同的 `approvals_required` 列出可申请的越界动作；运行时用 human-in-the-loop 中断（讲义提到 LangGraph interrupts、OpenAI Agents SDK 的工具审批策略）；
  - 人类决定"扩大合同"（新版本合同、记录原因）还是"让 agent 退回"；
  - 扩大后的合同依然要满足 feature 级约束：任务的 allowed 必须在 active feature 的范围内。
- **事后**：越界原因进入复盘，若频繁发生说明合同起草时对影响面估计不足，应改进合同模板而不是放宽检查。
- 常见误区：给 agent 一个"可以自己修改合同"的工具——这等于取消了合同。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 32 最小 Agent 工作台](../../32-minimal-agent-workbench/docs/zh.md)：scope contract 是工作台中的一个组件，本节在其基础上细化"任务边界"。
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../33-instructions-as-executable-constraints/docs/zh.md)：把规则从 prompt 变成可检查的约束，feature list 的"最多一个 in_progress"就是这样一条启动检查。
- [阶段 14 · 26 失效模式：Agents 为什么会失败](../../26-failure-modes-agentic/docs/zh.md)：scope creep 属于 agent 的典型失败模式。
- [阶段 14 · 27 Prompt Injection 与 PVE 防御](../../27-prompt-injection-defense/docs/zh.md)：讲义提到与 scope 锁配合的注入防御；网络白名单也能限制被注入后的外泄。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../../13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/docs/zh.md)：最小权限原则在工具层面的体现。

### 本节被哪些后续内容用到
- [阶段 14 · 37 运行时反馈循环](../../37-runtime-feedback-loops/docs/zh.md)：把实际执行的命令与结果反馈回合同的 acceptance。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：消费本节的 scope 报告，把 scope 违规作为拒绝理由。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)：评审者审计已关闭的合同归档。
- [阶段 14 · 40 跨会话 Handoff](../../40-multi-session-handoff/docs/zh.md)：把完成的 feature 状态写回 `done`。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../../15-autonomous-systems/15-propose-then-commit/docs/zh.md)、[阶段 15 · 16 Checkpoints 与 Rollback](../../../15-autonomous-systems/16-checkpoints-rollback/docs/zh.md)：审批边界与回滚的系统化实现。

### 延伸关键词
`scope creep` · `least privilege` · `deny overrides allow` · `glob vs fnmatch` · `violation budget` · `severity tiers` · `network egress allowlist` · `feature_list.json` · `merge gate` · `human-in-the-loop interrupt` · `rollback plan`
