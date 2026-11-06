# 测验 · 跨会话 Handoff（Multi-Session Handoff）

> **阶段 14 · Agent 工程 · 第 40 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 坏 handoff 的代价 | 下一个会话重新发现、重跑同样的命令、重问人类同样的问题，"花 30 分钟找回上个会话最后 30 秒"；这个代价在任务生命周期内每个会话都要付一次 |
| 2 | 七个字段 | `summary`、`changed_files`、`commands_run`、`failed_attempts`、`open_risks`、`next_action`、`verdict_pointer` |
| 3 | `next_action` 是承重字段 | 除了 `next_action` 什么都有的文档只是**状态报告**，不是 handoff |
| 4 | 生成而非手写 | 手写的 handoff 会在"难熬的一天"被跳过；agent 的职责是让工作台处于可被生成器总结的状态 |
| 5 | 两种形态 | `handoff.md` 给人看，`handoff.json` 给下一个 agent 加载；同源生成，若不一致以 JSON 为准 |
| 6 | Feedback 裁剪 | 只带最后 K 条 + 所有非零退出的记录；完整日志按需加载，交接包保持小巧 |
| 7 | 先清理再交接 | 工作区已提交、无临时文件、测试绿（或红但写进 `open_risks`）、feature board 与现实一致、分支正确；清理阶段输出 `clean_state.json`，空列表是生成 handoff 的前提 |
| 8 | Handoff ≠ compaction | compaction 延长一个会话；handoff 干净地结束一个会话并在新上下文中开始下一个 |
| 9 | 一条分支一个 active handoff | 带上 `branch`、`last_known_good_commit`、`status`（`active / superseded / archived`），过期的归档，只有 active 的驱动下一个会话 |
| 10 | 在 50–75% 上下文时收尾 | 讲义引实践经验：在上下文还完整时写 handoff 便宜，等到 95% 模型已开始"迷失"时才写就贵了 |

### 核心技能（能动手做到）

- [ ] 读懂 `generate_handoff`，能说出七个字段各自从哪个产物派生
- [ ] 手算 `trim_feedback` 在任意记录序列上的输出，并指出它在顺序、`None` 退出码、上限方面的问题
- [ ] 写一个生成前的 preflight：缺 gate 报告、缺 `next_action`、工作区不干净时拒绝生成
- [ ] 验证生成器的幂等性（同样输入 → 字节相同的输出），并说出哪些写法会破坏幂等
- [ ] 为 handoff 加上 `branch`、`last_known_good_commit`、`status`，实现"新 handoff 使旧的 superseded"
- [ ] 解释 handoff 与 compaction 的区别，以及什么时候应主动结束会话

---

## 二、基础自测（选择题）

**Q1.** 讲义说 handoff 中"承重（load-bearing）"的字段是哪一个？

- A. `next_action`——缺了它，文档只是一份状态报告，不是 handoff
- B. `summary`——最先被人阅读
- C. `changed_files`——diff 一目了然
- D. `verdict_pointer`——证明任务完成

**Q2.** 如果 `handoff.md` 和 `handoff.json` 的内容不一致，应该：

- A. 以 Markdown 为准，因为人类读的是它
- B. 以较新的那个文件为准
- C. 以 JSON 为准；Markdown 只是 JSON 的渲染
- D. 两个都作废，重新手写

**Q3.** 本节 demo 的 feedback 有 4 条记录（`pytest`→0、`ruff check .`→0、`pytest test_signup.py`→1、`pytest test_signup.py`→0），`TAIL_K=5`。`trim_feedback` 的返回值是：

- A. 只有那条退出码为 1 的记录
- B. 全部 4 条，按原顺序；失败记录已在尾部窗口中，按 `id()` 去重后不再重复
- C. 5 条，失败记录出现两次
- D. 空列表，因为记录数少于 K

**Q4.** 讲义如何区分 compaction 与 handoff？

- A. 两者是同一件事的两种叫法
- B. compaction 用于多 agent，handoff 用于单 agent
- C. handoff 是 compaction 的一个步骤，在 95% 上下文时自动触发
- D. compaction 延长一个会话；handoff 干净地结束一个会话，并在新上下文中开始下一个；原地压缩开始降质时，应写 handoff、结束会话

**Q5.** 讲义引用的实践经验认为，什么时候收尾并生成 handoff 效果最好？

- A. 上下文用到 95%、模型提示即将溢出时
- B. 每完成一个工具调用就生成一次
- C. 上下文用到 50–75% 时，趁上下文仍然完整
- D. 只在任务完全完成后生成

**Q6.** 构造 106 条 feedback：前 100 条中下标是 3 的倍数的退出码为 1（共 34 条），第 101 条是一次超时（`exit_code=None`），最后 5 条成功。`trim_feedback` 的结果是：

- A. 39 条，且那条超时（`None`）记录**不在**结果中
- B. 30 条，正好等于 skill 规定的上限
- C. 5 条，只保留尾部
- D. 40 条，超时记录也被当作失败保留

**Q7.** 关于"Leave a clean state"，讲义的要求是：

- A. 清理是一个好习惯，有时间就做
- B. 只要 `handoff.md` 写得足够详细，工作区脏一点没关系
- C. 清理在生成 handoff **之后**进行
- D. 清理是生成 handoff 之前的独立阶段，并且是一项检查而非习惯；它输出 `clean_state.json`，阻塞问题列表为空是生成器的前置条件

**Q8.** 多 agent 协作中，讲义认为 handoff 必须带上哪些元数据，才能避免"过期 handoff"导致的混乱？

- A. 模型名称与 temperature
- B. `branch`、`last_known_good_commit`，以及 `status`（`active | superseded | archived`）；每个分支与主题只有一个 active
- C. 会话的 token 用量
- D. 生成时间即可

---

## 三、动手 / 代码题

**Q9.** 阅读 `trim_feedback`：

```python
def trim_feedback(records: list[dict[str, object]]) -> list[dict[str, object]]:
    tail = records[-TAIL_K:]
    nonzero = [r for r in records if r.get("exit_code") not in (0, None)]
    out: list[dict[str, object]] = []
    seen: set[int] = set()
    for r in tail + nonzero:
        key = id(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out
```

1. 结合 Q6 的输入，指出这个函数的至少三个问题（提示：顺序、`None`、上限、`id()`）。
2. 写 `trim_feedback_v2(records, k=5, cap=30)`：保留最后 k 条 + 所有 `exit_code != 0` 的记录（含 `None`），超过上限时优先保留最近的失败，输出保持时间顺序。给出在 Q6 输入上的结果。

**Q10.** 下面两个快照都能被 `generate_handoff` 顺利生成交接包：

```python
s1 = WorkbenchSnapshot("T-9", state={}, verdict={}, review={},
                       feedback=[{"command": ["pytest", "-x"], "exit_code": None}], diff_summary={})
s2 = WorkbenchSnapshot("T-8", state={"next_action": "merge"},
                       verdict={"passed": False, "findings": [{"severity": "block", "detail": "acceptance.missing"}]},
                       review={"verdict": "hard_fail", "total": "n/a"}, feedback=[], diff_summary={"touched": []})
```

1. 分别写出生成结果中的 `next_action`、`summary`、`open_risks`、`failed_attempts`、`commands_run`，指出其中的问题。
2. 按讲义与 skill 的拒绝规则写一个 `preflight(snapshot, clean_issues) -> list[str]`，返回非空就拒绝生成；给出 s1、s2 和一个正常快照的结果。

**Q11.** mission 的验收标准之一是"Re-running the script with the same inputs produces an identical packet"（讲义练习 4：生成器幂等）。

1. 如何验证？本节代码是否满足？
2. 如果给 payload 加上 `generated_at = time.time()`、用 `set` 收集 `changed_files`、或在 `verdict_pointer` 里写绝对路径，分别会怎样破坏幂等？应如何改？
3. `trim_feedback` 里用 `id(r)` 去重，会不会破坏幂等？会不会带来别的问题？

**Q12.** 讲义的生产模式要求"One active handoff per branch and topic"。请写 `register_handoff(index, new)`：

- `index` 是已有 handoff 的列表，每项含 `id`、`branch`、`topic`、`last_known_good_commit`、`status`；
- 新 handoff 注册为 `active`，同一 `branch` + `topic` 下原来的 `active` 改为 `superseded`；
- 断言注册后同一 branch + topic 只有一个 `active`。

依次注册 `h1(feat/signup, T-001)`、`h2(feat/signup, T-001)`、`h3(feat/search, T-002)`，写出最终状态。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 handoff packet？它的七个字段分别回答什么问题？为什么讲义强调 `next_action`？

**Q14.**（原理深挖）handoff 与上下文 compaction 有什么本质区别？为什么讲义建议"压缩开始降质时，写 handoff 并开新会话"，而不是继续压缩？

**Q15.**（工程实践）请设计一个会话结束钩子：它在什么条件下运行、先做什么检查、生成什么、拒绝什么、产物放在哪里。

**Q16.**（场景设计）同一个任务先用 Claude Code 做了一半，再交给 Codex 继续，期间还有另一个 agent 在相邻分支上工作。如何保证 handoff 在不同产品、不同 agent 之间可靠传递？

**Q17.**（追问型）handoff 里应该放"给人类的问题"吗？什么样的问题进 handoff，什么样的问题应该直接在聊天里问？（讲义练习 3）

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："The `next_action` field is the load-bearing one. A handoff with everything except `next_action` is a status report, not a handoff."下一个会话最需要的是"第一步做什么"，这能让它在第一分钟就开始工作。B、C、D 都是有用字段，但缺了它们，下一个会话仍然知道从哪里开始；缺了 `next_action` 则不知道。

### Q2 — 答案：C

讲义："Both come from the same source artifacts. If they diverge, the JSON wins."skill 更进一步："JSON is the source; markdown is a render of JSON."本节代码正是先构造 `HandoffPayload`，再从它渲染 Markdown。A 与讲义相反；B、D 都不是讲义的规则。注意：Markdown 没有渲染 `feedback_tail`，它只在 JSON 中——这是"渲染是子集"，不算不一致。

### Q3 — 答案：B

`tail = records[-5:]` 就是全部 4 条；`nonzero` 只有第 3 条，它与 `tail` 中的第 3 条是**同一个 dict 对象**，`id()` 相同，被跳过。所以结果是原顺序的 4 条（实测 `handoff.json` 的 `feedback_tail` 即如此）。A 忽略了尾部窗口；C 忽略了去重；D 错，切片 `[-5:]` 在列表短于 5 时返回整个列表。

### Q4 — 答案：D

讲义："Compaction extends a session; handoff closes one cleanly and starts the next."并引用 Hermes Issue #20372：原地压缩开始降质时，agent 应写一份紧凑的 handoff、结束会话、在新上下文中继续。"The mistake is to keep compressing until quality collapses."A、B 错；C 错，讲义恰恰建议不要等到 95%。

### Q5 — 答案：C

讲义："The hand-written-pattern playbook (CLAUDE.md + HANDOVER.md) reports best results when the session ends at 50-75% context budget instead of 95%."在上下文完整时生成交接包成本低；等到压缩产物污染了状态，模型已经在丢失位置，代价高。A 正是要避免的；B 太频繁、没有必要；D 错，任务没完成时才最需要 handoff。

### Q6 — 答案：A

实测：`len 39`，`has null? False`。

- `tail` = 最后 5 条（全部成功）；
- `nonzero` 过滤条件是 `exit_code not in (0, None)`，34 条退出码为 1 的记录都在，**超时记录（`None`）被排除**；
- 5 + 34 = 39 条，超过 skill 规定的 30 条上限（"A feedback tail longer than 30 entries" 是 hard reject）。

B 是应有的上限但代码没有实现；C 忽略了失败记录；D 错在 `None` 被显式排除。讽刺的是，`None` 恰恰代表"没有拿到反馈"（第 37 节的 refuse-on-null），是下一个会话最该知道的失败之一，`failed_attempts` 同样把它排除了。

### Q7 — 答案：D

讲义："Cleanup is its own phase, run before the handoff, and it is a check, not a habit, because a habit is the thing that gets skipped on a hard day."以及"The cleanup phase emits a `clean_state.json` of blocking issues; an empty list is the precondition the handoff generator asserts before it writes a packet."A 正是讲义否定的"习惯"；B 错，"A perfect `handoff.md` is worthless if the next session opens to a half-applied diff"；C 顺序反了。注意：本节代码并没有实现清理检查。

### Q8 — 答案：B

讲义："Always include `branch`, `last_known_good_commit`, and a `status` of `active | superseded | archived`. Stale handoffs are archived; only the active one drives the next session. This is the difference between handoff-as-notes and handoff-as-state."A、C、D 都无法解决"多个 handoff 中哪一个有效"的问题。本节代码的 `HandoffPayload` 没有这三个字段（练习见 Q12）。

### Q9 — 参考答案

1. 问题：
   - **`None` 被排除**：超时、程序不存在等"没有反馈"的记录既不进 `feedback_tail`（除非恰好在尾部），也不进 `failed_attempts`；
   - **没有上限**：Q6 的输入得到 39 条，失败越多越长，违反 skill 的 30 条上限；
   - **顺序不是时间顺序**：先放尾部 K 条，再放所有旧的失败记录，读者看到的是"最新 5 条 + 从头开始的失败"，时间线被打乱（实测前 7 条是 `d0…d4, c0, c3`）；
   - **按 `id()` 去重**：依赖"尾部与失败列表引用的是同一批 Python 对象"。这里两者都切自同一个 `records` 列表，所以有效；内容相同的两条独立记录不会被合并（这是对的——它们是两次运行）。但这种写法很脆弱：一旦尾部或失败列表来自不同的加载/拷贝（例如失败记录是从轮转文件重新读出的），同一条记录就会出现两次。用记录在列表中的**下标**去重更清晰可靠。
2. 参考实现（已运行）：

   ```python
   def trim_feedback_v2(records, k=5, cap=30):
       tail_idx = set(range(max(0, len(records) - k), len(records)))
       fail_idx = [i for i, r in enumerate(records) if r.get("exit_code") != 0]   # 含 None
       keep = set(tail_idx)
       for i in reversed(fail_idx):                 # 最近的失败优先
           if len(keep) >= cap:
               break
           keep.add(i)
       return [records[i] for i in sorted(keep)]    # 恢复时间顺序
   ```

   在 Q6 输入上：返回 **30** 条，从 `c30` 开始（更早的失败因上限被舍弃），末尾是 `c99, timeout-cmd, d0, d1, d2, d3, d4`——超时记录被保留，且按时间排序。讲义练习 2 还建议对失败运行与成功运行采用不同的裁剪策略（例如失败的命令保留更长的 stderr 尾部）。

### Q10 — 参考答案

1. 实测结果：

   | 字段 | s1 | s2 |
   |------|----|----|
   | `next_action` | `no next_action recorded; needs human` | `merge` |
   | `summary` | `task T-9: review=None, gate=None` | `task T-8: review=hard_fail, gate=False` |
   | `open_risks` | `[]` | `[{'severity': 'block', 'detail': 'acceptance.missing'}]` |
   | `failed_attempts` | `[]` | `[]` |
   | `commands_run` | `["['pytest', '-x']"]` | `[]` |

   问题：
   - s1 没有 gate 报告、没有 review、没有 `next_action`，生成器用一句占位文字填充了 `next_action`，于是"`next_action` 非空"这一验收条件被**形式上满足**——实际上这是一份状态报告，违反 skill："A handoff without a `next_action`"、"If the verification report is missing, refuse to generate the packet"。
   - s1 的超时命令不在 `failed_attempts` 里；argv 列表被渲染成 Python 列表的字符串形式。
   - s2 的 gate 是红的、review 是 `hard_fail`，交接包却告诉下一个会话"merge"。`review.total` 为 `"n/a"` 时被当成 10 分处理，review 风险被静默吞掉（fail open）。
   - 两者的 `verdict_pointer` 都指向 `outputs/verification/<id>.json`、`outputs/review/<id>.json`，生成器不检查文件是否存在；而第 38、39 节的代码实际上把报告写在 `code/verification_report_<id>.json`、`code/review_report_<id>.json`，指针指向的文件并不存在。
   - `summary` 只有 review 与 gate 状态，不是讲义所说的"One paragraph of what was done"。
2. 参考实现（已运行）：

   ```python
   def preflight(s, clean_issues):
       errs = []
       if not s.verdict or "passed" not in s.verdict:
           errs.append("verification report missing")
       if not s.state.get("next_action"):
           errs.append("next_action missing: this would be a status report")
       if clean_issues:
           errs.append(f"dirty workbench: {clean_issues}")
       if s.verdict.get("passed") is False and "merge" in str(s.state.get("next_action", "")).lower():
           errs.append("next_action suggests merge but gate is red")
       total = s.review.get("total")
       if not isinstance(total, int):
           errs.append(f"review total not an int: {total!r}")
       return errs
   ```

   结果：
   - s1 → `['verification report missing', 'next_action missing: this would be a status report', 'review total not an int: None']`
   - s2（附带 `clean_issues=['untracked file: scratch.tmp']`）→ `["dirty workbench: [...]", 'next_action suggests merge but gate is red', "review total not an int: 'n/a'"]`
   - 正常快照 → `[]`

   "merge" 的关键词判断只是示意；更稳妥的做法是：gate 为红时，生成器自动把 `next_action` 设为"修复 block finding X"并要求人类确认。skill 还要求：diff 为空但会话超过 5 分钟时先报告异常（怀疑会话卡死）。

### Q11 — 参考答案

1. 验证：运行两次，对两次的 `handoff.md`、`handoff.json` 做字节比较或哈希。实测两次运行的 MD5 完全相同（`handoff.json` 为 `72d65b1a…`，`handoff.md` 为 `0f44de9e…`），本节代码满足幂等：没有时间戳、没有随机数、输入是固定的字面量、列表顺序固定、`json.dumps` 对 dict 按插入顺序输出。
2. 破坏幂等的写法与改法：
   - `generated_at = time.time()`：每次都不同。改为取输入产物中的确定性时间（如最后一条 feedback 的 `started_at`、HEAD commit 的时间），或把生成时间放在 packet 之外的元数据文件里；也可以在比较时排除该字段。
   - 用 `set` 收集 `changed_files`：字符串的哈希在不同进程中会随机化（`PYTHONHASHSEED`），集合的迭代顺序可能变化。改为 `sorted(set(...))`。
   - 写绝对路径：换一台机器、换一个工作目录就不同。用相对于仓库根的路径。
   - 同理还有：`uuid`、遍历目录时不排序（`glob` 的返回顺序依赖文件系统）、浮点格式不固定等。
3. `id(r)` 只在单次运行内用于去重，不会出现在输出中，**不破坏幂等**。但它依赖"尾部列表与失败列表引用同一个对象"，若在两者之间对记录做了拷贝，去重就会失效；用下标去重更稳妥（见 Q9）。

### Q12 — 参考答案

```python
def register_handoff(index, new):
    for h in index:
        if h["branch"] == new["branch"] and h["topic"] == new["topic"] and h["status"] == "active":
            h["status"] = "superseded"
    new = dict(new, status="active")
    index.append(new)
    actives = [h for h in index
               if h["branch"] == new["branch"] and h["topic"] == new["topic"] and h["status"] == "active"]
    assert len(actives) == 1
    return index
```

实测最终状态：`[('h1', 'superseded'), ('h2', 'active'), ('h3', 'active')]`——h2 取代了同一分支同一主题的 h1；h3 位于另一分支，互不影响。

要点：
- 下一个会话启动时只加载 `status == "active"` 且 `branch` 与当前分支一致的 handoff；`last_known_good_commit` 用于确认工作区没有偏离（HEAD 不同就先核对）。
- 超过一段时间未使用的 superseded 条目转为 `archived`。
- 这与第 36 节 feature list"最多一个 `in_progress`"是同一类不变式：用文件中的状态 + 启动检查代替口头约定。

### Q13 — 参考回答要点

- **定义**：会话结束时由生成器从工作台产物自动生成的交接包，有 Markdown（人读）和 JSON（agent 读）两种形态，JSON 为准。
- **七个字段**：
  - `summary`：做了什么（一段话）；
  - `changed_files`：diff 一览；
  - `commands_run`：实际执行了什么（来自 feedback，不是 agent 的叙述）；
  - `failed_attempts`：试过什么、为什么没成功——避免下一个会话重蹈覆辙；
  - `open_risks`：下个会话可能踩的坑及严重度；
  - `next_action`：下个会话的第一步；
  - `verdict_pointer`：gate 与 review 报告的路径，可追溯。
- **为什么 `next_action` 承重**：其余字段描述过去，只有它定义未来的第一步；没有它就是状态报告。
- 加分点：生成而非手写；配合清理检查；带 `branch`/`last_known_good_commit`/`status`。

### Q14 — 参考回答要点

- **compaction**：在同一会话内把历史消息压缩（摘要、隐藏旧消息、服务端加密 blob 等），让会话继续。讲义列举：Codex CLI 的服务端 compact 端点及本地 "handoff summary" 回退、Claude Code 在 95% 上下文时的五阶段渐进压缩、OpenCode 的按时间戳隐藏 + 5 个标题的 LLM 摘要。
- **handoff**：结束当前会话，把"压缩后仍需保留的东西"序列化成可移植的结构化产物，在全新上下文中继续。
- **为什么不一直压缩**：每次压缩都会丢信息，摘要的摘要会越来越失真；模型在接近上下文上限时表现下降。讲义："The mistake is to keep compressing until quality collapses; the fix is to budget for an early, clean handoff."
- **结构化的好处**：三种 compaction 机制不同，但交接包的 schema 不变（"Compaction strategies vary; the packet schema does not"），因此可以跨产品使用。
- 加分点：50–75% 上下文时收尾的经验；handoff 由确定性生成器从产物生成，而不是让已经降质的模型去写摘要。

### Q15 — 参考回答要点

- **触发**：用户关闭会话、上下文达到 50–75% 预算、任务关闭、运行时检测到压缩质量下降时。
- **顺序**：
  1. 清理阶段：检查工作区（未提交改动、临时文件、调试输出）、测试状态、feature board 是否与现实一致、分支是否正确 → 输出 `clean_state.json`；
  2. 确认 gate 报告存在（skill：没有 verdict 就拒绝），需要人工评审时确认 review 报告存在；
  3. 生成 `handoff.json`，再从 JSON 渲染 `handoff.md`；
  4. 校验 schema：七个字段齐全、`next_action` 非空且不是占位文字、feedback tail ≤ 30；
  5. 更新 feature list 的状态（第 36 节："The handoff writes the finished feature's status back to `done`"），注册为 active handoff 并 supersede 旧的。
- **拒绝**：工作区脏、缺 gate 报告、缺 `next_action`、diff 为空但会话超过 5 分钟（先报告异常）。拒绝时不允许关闭会话（skill："refuses to close the session if any field is missing"）。
- **产物位置**：`outputs/handoff/<session_id>/handoff.{md,json}`；Markdown 也可直接作为 PR 描述。

### Q16 — 参考回答要点

- **交接包是"通用语"**：讲义："Build with one product (Claude Code), continue with another (Codex). The packet is the lingua franca."关键是 schema 与产品无关（`handoff.schema.json`），而不是依赖某个产品内部的 compaction 格式。
- **状态在文件里**：feature list、scope 合同、feedback JSONL、gate/review 报告都放在仓库中，handoff 只是指向它们的索引 + 摘要。
- **并发与过期**：每个 handoff 带 `branch`、`topic`、`last_known_good_commit`、`status`；同一分支 + 主题只有一个 active（Q12）；相邻分支的 agent 不会误读别人的 handoff。
- **启动检查**：新会话启动时校验当前分支、HEAD 与 `last_known_good_commit` 的关系，工作区是否干净；不一致时停下来问人。
- **下一会话的前置**：列出必须先加载的产物（讲义练习 5 的 "next session prereqs"）。
- 常见误区：把 handoff 当成聊天消息转发；多个 handoff 同时有效导致两个 agent 做同一件事。

### Q17 — 参考回答要点

- **进 handoff 的问题**：会**阻塞下一个会话**、需要人类决策且答案需要被记录下来的问题，例如"速率限制窗口取 1 分钟还是 5 分钟"（demo 中的 blocker）。它们应当带有默认假设与影响（若无人回答，下一个会话按什么假设继续、风险是什么），并出现在 `open_risks` 或单独的"questions for the human"列表中。
- **直接在聊天里问的问题**：当前会话内就能得到答复、答复后立即使用、不需要跨会话留存的问题。
- **阈值**：是否影响 `next_action`；是否是不可逆或高成本决策；是否会在未来多个会话中反复出现。满足任一条就进交接包。
- 结合讲义练习 1：builder 记录但 reviewer 打分不超过 1 的假设，应列入 `assumptions_to_validate`，交给人类确认。
- 常见误区：把所有问题都塞进交接包，导致它变成"待办大杂烩"；或者只在聊天里问，答案随会话结束而丢失。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 34 代码仓库记忆与持久状态](../../34-repo-memory-and-state/docs/zh.md)：生成器读取的状态文件来自这里。
- [阶段 14 · 37 运行时反馈循环](../../37-runtime-feedback-loops/docs/zh.md)：`commands_run`、`failed_attempts`、feedback tail 的来源，以及重试链。
- [阶段 14 · 38 Verification Gates](../../38-verification-gates/docs/zh.md)：`verdict_pointer` 指向的 gate 报告。
- [阶段 14 · 39 Reviewer Agent：将实现者与评分者分开](../../39-reviewer-agent/docs/zh.md)：被打包进交接包的 review 报告。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：feature list 的状态由 handoff 写回。
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../07-memory-virtual-context-memgpt/docs/zh.md)：上下文管理与"什么该写到外部存储"的基础。

### 本节被哪些后续内容用到
- [阶段 14 · 41 在真实代码仓库中使用工作台](../../41-workbench-for-real-repos/docs/zh.md)：在接近真实的样例应用上端到端演练。
- [阶段 14 · 42 综合项目：交付可复用的 Agent 工作台包](../../42-agent-workbench-capstone/docs/zh.md)：把生成器打包进工作台。
- [阶段 14 · 29 生产运行时：队列、事件与定时任务](../../29-production-runtimes/docs/zh.md)：把会话结束钩子接到队列、事件与定时触发上。
- [阶段 16 · 11 Handoffs 与例程：无状态 Orchestration](../../../16-multi-agent-and-swarms/11-handoffs-and-routines/docs/zh.md)：多 agent 之间的交接模式。
- [阶段 15 · 16 Checkpoints 与 Rollback](../../../15-autonomous-systems/16-checkpoints-rollback/docs/zh.md)、[阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../../16-multi-agent-and-swarms/22-production-scaling-queues-checkpoints/docs/zh.md)：持久化状态与恢复。

### 延伸关键词
`handoff packet` · `next_action` · `status report vs handoff` · `context compaction` · `fresh-session handoff` · `clean state` · `feedback trimming` · `idempotent generator` · `last_known_good_commit` · `active / superseded / archived` · `CLAUDE.md / HANDOVER.md` · `session-end hook`
