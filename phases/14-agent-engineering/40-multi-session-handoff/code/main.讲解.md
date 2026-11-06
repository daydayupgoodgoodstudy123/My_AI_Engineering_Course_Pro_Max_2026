# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 40 节 跨会话 Handoff ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（无参数） ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`）；运行时会在 `code/` 下写 `handoff.md` 与 `handoff.json`

---

## 1. 这份代码在考察什么

这份代码实现了讲义中的 handoff 生成器：在会话结束时，从工作台产物（状态、gate 结论、review 报告、feedback、diff 摘要）**自动生成**交接包，而不是让 agent 手写总结。对应讲义的概念：

1. **七个字段**：`summary`、`changed_files`、`commands_run`、`failed_attempts`、`open_risks`、`next_action`、`verdict_pointer`。
2. **两种形态、同一来源**：先构造 `HandoffPayload`（JSON 的来源），再从它渲染 Markdown——"JSON wins"。
3. **Feedback 裁剪**：最后 K 条 + 所有非零退出的记录。
4. **风险派生**：从 gate findings、状态中的 blockers、review 总分推导 `open_risks`。
5. **确定性**：没有时间戳和随机数，同样输入得到字节相同的输出（mission 的验收标准之一）。

> 一句话：**把"上个会话做了什么、下个会话第一步做什么"从 agent 的记忆里搬到一个可生成、可校验的文件里**。阅读时也要注意它在"缺失产物时用占位文字填充""`None` 退出码被忽略""没有清理检查"等地方是 fail open 的。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TAIL_K = 5` | 常量 | 尾部保留条数 | feedback trim 的 K |
| `WorkbenchSnapshot` | dataclass | 生成器的全部输入 | 工作台快照 |
| `HandoffPayload` | dataclass | 七个字段 + `feedback_tail` | `handoff.json` |
| `trim_feedback` | 函数 | 尾部 K 条 + 非零退出，按 `id()` 去重 | feedback 裁剪 |
| `derive_risks` | 函数 | 从 findings、blockers、review 总分生成风险列表 | `open_risks` |
| `generate_handoff` | 函数 | 构造 payload，渲染 Markdown | 生成器 |
| `_bullets`（内部函数） | 函数 | 空列表时输出 `- none` | 渲染辅助 |
| `main` | 函数 | 构造 demo 快照，写两个文件并打印 Markdown | demo |

数据流：`WorkbenchSnapshot` → `generate_handoff`（`derive_risks` + `trim_feedback` → `HandoffPayload` → Markdown 行列表）→ `main` 写 `handoff.md`（Markdown）与 `handoff.json`（`asdict(payload)`）。

---

## 3. 逐段精讲

### 3.1 输入与输出结构

```python
@dataclass
class WorkbenchSnapshot:
    task_id: str
    state: dict[str, object]
    verdict: dict[str, object]
    review: dict[str, object]
    feedback: list[dict[str, object]]
    diff_summary: dict[str, list[str]]
```

对应讲义流程图的四个输入（`agent_state.json`、`verification_report.json`、`review_report.json`、`feedback_record.jsonl`）再加 diff 摘要。讲义说 "A loader that gathers state, verdict, review, and feedback into a single `WorkbenchSnapshot`"，但代码中没有加载器，快照在 `main()` 里用字面量构造。

```python
@dataclass
class HandoffPayload:
    task_id: str
    summary: str
    changed_files: list[str]
    commands_run: list[str]
    failed_attempts: list[str]
    open_risks: list[dict[str, str]]
    next_action: str
    verdict_pointer: dict[str, str]
    feedback_tail: list[dict[str, object]] = field(default_factory=list)
```

| 字段 | 派生自 | 代码中的派生方式 |
|------|-------|----------------|
| `summary` | review + verdict | `f"task {id}: review={...}, gate={...}"` |
| `changed_files` | diff 摘要 | `diff_summary["touched"]` |
| `commands_run` | feedback | 每条记录的 `command` 转成字符串 |
| `failed_attempts` | feedback | 退出码不是 0 也不是 `None` 的记录 |
| `open_risks` | verdict + state + review | `derive_risks` |
| `next_action` | state | `state["next_action"]`，缺失时用占位文字 |
| `verdict_pointer` | task_id | 拼出两个固定路径 |
| `feedback_tail` | feedback | `trim_feedback` |

- ⚠️ 讲义生产模式要求的 `branch`、`last_known_good_commit`、`status`（`active | superseded | archived`）没有出现。
- ⚠️ `summary` 只是 review 与 gate 的状态，不是讲义所说的"One paragraph of what was done"。

### 3.2 `trim_feedback`：尾部 + 失败

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

- `records[-TAIL_K:]`：列表短于 5 时返回整个列表，不会报错。
- `exit_code not in (0, None)`：只保留"有退出码且非 0"的记录。
- `id(r)`：对象在内存中的身份标识。尾部和失败列表都切自同一个 `records`，同一条记录是同一个对象，`id` 相同即可去重；内容相同的两条独立记录 `id` 不同，会都保留（它们确实是两次运行）。
- demo 输入 4 条、K=5：结果就是原顺序的 4 条（失败那条已在尾部，被去重）。
- ⚠️ 实测问题（构造 100 条中 34 条失败 + 1 条超时 + 5 条成功）：
  - 结果 **39 条**，没有上限（skill："A feedback tail longer than 30 entries" 是 hard reject）；
  - **超时记录（`None`）被排除**——"没有拿到反馈"恰恰是下一个会话最该知道的失败之一（第 37 节的 refuse-on-null）；
  - **顺序被打乱**：先放尾部 5 条，再放从头开始的旧失败，前 7 条是 `d0…d4, c0, c3`；
  - 按 `id()` 去重较脆弱，用下标更清晰（测验 Q9 给出了按下标、保序、含 `None`、带上限的版本）。

### 3.3 `derive_risks`：三类风险

```python
def derive_risks(snapshot: WorkbenchSnapshot) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    for f in snapshot.verdict.get("findings", []) or []:
        if isinstance(f, dict) and f.get("severity") in ("warn", "block"):
            risks.append({"severity": str(f.get("severity")), "detail": str(f.get("detail"))})
    for blocker in snapshot.state.get("blockers") or []:
        risks.append({"severity": "warn", "detail": f"open blocker: {blocker}"})
    raw_total = snapshot.review.get("total", 10)
    try:
        safe_total = int(raw_total)
    except (TypeError, ValueError):
        safe_total = 10
    if safe_total < 7:
        risks.append({"severity": "warn", "detail": f"review total {raw_total} below 7"})
    return risks
```

- `.get("findings", []) or []`：键不存在时用默认值 `[]`；键存在但值为 `None` 时，`or []` 再兜底。两层防御。
- `isinstance(f, dict)`：防御性检查，跳过格式不对的 finding。
- 状态中的 blocker 一律记为 warn。
- review 总分 < 7（讲义的 soft fail 阈值）→ warn。
- ⚠️ **fail open**：review 缺失时默认 10 分；`total` 是 `"n/a"` 这类无法转换的值时也当 10 分——"不知道"被当成"满分"，风险被静默吞掉（实测 `review={"verdict": "hard_fail", "total": "n/a"}` 不产生任何 review 风险）。更安全的默认值是 0 或直接报"review 缺失"。
- ⚠️ 只看 `total`，不看 review 的 `verdict`：`hard_fail` 但总分 ≥ 7（某维为 0）的情况不会产生风险。
- 讲义要求测试为红时要把失败写进 `open_risks`，代码没有从 feedback 派生这类风险。

### 3.4 `generate_handoff`：先 JSON，后 Markdown

```python
def generate_handoff(snapshot: WorkbenchSnapshot) -> tuple[str, HandoffPayload]:
    next_action = str(snapshot.state.get("next_action") or "no next_action recorded; needs human")
    payload = HandoffPayload(
        task_id=snapshot.task_id,
        summary=f"task {snapshot.task_id}: review={snapshot.review.get('verdict')}, gate={snapshot.verdict.get('passed')}",
        changed_files=snapshot.diff_summary.get("touched", []),
        commands_run=[str(r.get("command")) for r in snapshot.feedback],
        failed_attempts=[
            f"{r.get('command')} -> exit {r.get('exit_code')}"
            for r in snapshot.feedback
            if r.get("exit_code") not in (0, None)
        ],
        open_risks=derive_risks(snapshot),
        next_action=next_action,
        verdict_pointer={
            "verdict": f"outputs/verification/{snapshot.task_id}.json",
            "review": f"outputs/review/{snapshot.task_id}.json",
        },
        feedback_tail=trim_feedback(snapshot.feedback),
    )
```

- ⚠️ **`next_action` 占位**：缺失时填入 `"no next_action recorded; needs human"`。字段于是"非空"，mission 的"non-empty `next_action`"被形式上满足，但这正是讲义说的"状态报告冒充 handoff"。skill 要求的是**拒绝**生成（并拒绝关闭会话）。
- ⚠️ **不检查 gate 是否存在、是否为绿**：skill："If the verification report is missing, refuse to generate the packet."实测 gate 为红、`next_action="merge"` 的快照照样生成了交接包。
- ⚠️ **`verdict_pointer` 不校验文件存在**：路径按讲义约定拼出 `outputs/verification/<id>.json`、`outputs/review/<id>.json`，而第 38、39 节的代码实际写在 `code/verification_report_<id>.json`、`code/review_report_<id>.json`——指针指向不存在的文件。
- `str(r.get("command"))`：feedback 来自第 37 节时 `command` 是 argv 列表，会被渲染成 `"['pytest', '-x']"` 这种 Python 字面量形式；用 `shlex.join` 更合适。
- `failed_attempts` 同样排除了 `None` 退出码。
- ⚠️ 没有清理检查：讲义用了整整一节讲"Leave a clean state"（工作区、临时文件、测试、feature board、分支），清理阶段产出的 `clean_state.json` 为空是生成器的前置条件——代码没有实现。

```python
    def _bullets(items: list[str]) -> list[str]:
        return items or ["- none"]

    md_lines = [
        f"# Handoff: {payload.task_id}",
        "",
        f"**Summary.** {payload.summary}",
        "",
        "## Changed files",
        *_bullets([f"- `{f}`" for f in payload.changed_files]),
        ...
        "## Next action",
        f"{payload.next_action}",
        "",
        "## Receipts",
        f"- verdict: `{payload.verdict_pointer['verdict']}`",
        f"- review:  `{payload.verdict_pointer['review']}`",
    ]
    return "\n".join(md_lines) + "\n", payload
```

- Markdown 完全由 `payload` 渲染，保证"Markdown 是 JSON 的渲染"。`feedback_tail` 只在 JSON 里，Markdown 不展示——渲染是子集，不算不一致。
- `*_bullets([...])`：列表字面量中的 `*` 解包，把子列表的元素平铺进外层列表。
- `_bullets` 让空段落显示 `- none`，而不是一个空标题。
- ⚠️ 命令里如果含反引号，`` f"- `{c}`" `` 会破坏 Markdown 格式；生产中应转义或改用代码块。

### 3.5 `main()`：demo 快照

```python
    snapshot = WorkbenchSnapshot(
        task_id="T-001",
        state={"active_task_id": None,
               "blockers": ["awaiting decision on rate-limit window"],
               "next_action": "open PR with current diff and request review"},
        verdict={"passed": True, "findings": [{"severity": "warn", "detail": "off-scope: README.md"}]},
        review={"verdict": "pass", "total": 8},
        feedback=[
            {"command": "pytest", "exit_code": 0},
            {"command": "ruff check .", "exit_code": 0},
            {"command": "pytest test_signup.py", "exit_code": 1},
            {"command": "pytest test_signup.py", "exit_code": 0},
        ],
        diff_summary={"touched": ["app/signup.py", "tests/test_signup.py", "README.md"]},
    )
    md, payload = generate_handoff(snapshot)
    (HERE / "handoff.md").write_text(md)
    (HERE / "handoff.json").write_text(json.dumps(asdict(payload), indent=2) + "\n")
    print(md)
```

- 这是一个"健康"的快照：gate 通过、review 8 分、失败后重试成功、有明确的 `next_action`。
- 文件写在 `code/` 下；skill 规定的位置是 `outputs/handoff/<session_id>/`。
- `asdict(payload)` 会递归转换嵌套结构，`json.dumps(indent=2)` 输出缩进格式。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 先构造 payload 再渲染 Markdown | 保证两种形态同源，JSON 为准 | 无 |
| 生成而非手写 | 难熬的一天也不会被跳过 | 生成的 `summary` 很单薄；可从 diff、合同 goal、review 中拼出一段话 |
| 尾部 K 条 + 非零退出 | 交接包小、失败历史保留 | 无上限、排除 `None`、顺序被打乱；应保序、含 `None`、限 30 条 |
| `id()` 去重 | 一行实现 | 依赖对象身份，脆弱；用下标 |
| 缺失值用默认值（`next_action` 占位、review 10 分） | 生成器永不失败 | fail open；应拒绝生成并要求人类介入 |
| `verdict_pointer` 按约定拼路径 | 简单 | 不校验存在；与第 38/39 节实际路径不一致 |
| 无时间戳、无随机 | 幂等，重复运行字节相同 | 需要生成时间时应来自输入产物或放在包外 |
| 不做清理检查、不写 feature list | demo 简单 | 讲义要求 `clean_state.json` 为空才生成；handoff 应把完成的 feature 写回 `done` |
| 无 `branch` / `status` 等元数据 | demo 简单 | 多 agent 场景必须有，见测验 Q12 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 类型注解 | `class HandoffPayload:` | 自动生成构造函数；注解描述字段类型 |
| `field(default_factory=list)` | `feedback_tail` | 可变默认值 |
| 负数切片 | `records[-TAIL_K:]` | 取最后 K 个；不足 K 个时返回全部 |
| `not in` 元组 | `r.get("exit_code") not in (0, None)` | 不等于其中任何一个 |
| `id()` | `key = id(r)` | 对象身份，只在对象存活期间唯一 |
| `set` 去重 | `seen: set[int] = set()` | O(1) 成员检查 |
| `continue` | `if key in seen: continue` | 跳过本次循环 |
| `dict.get(k, default) or []` | `snapshot.verdict.get("findings", []) or []` | 键缺失与值为 `None` 都兜底 |
| `isinstance` | `isinstance(f, dict)` | 类型检查 |
| `try/except (TypeError, ValueError)` | `int(raw_total)` | 转换失败时走兜底分支 |
| 返回元组 | `-> tuple[str, HandoffPayload]`、`md, payload = generate_handoff(...)` | 一次返回两个值并解包 |
| 内部函数 | `def _bullets(items)` 定义在 `generate_handoff` 内 | 只在本函数内使用 |
| 列表内 `*` 解包 | `*_bullets([...])` | 把子列表元素平铺到外层列表字面量中 |
| 列表推导式 + 条件 | `[f"..." for r in snapshot.feedback if ...]` | 过滤 + 格式化 |
| f-string 内嵌 dict 取值 | `f"- [{r['severity']}] {r['detail']}"` | f-string 内用另一种引号 |
| `"\n".join(lines) + "\n"` | 拼 Markdown | 以换行结尾，便于 diff 与幂等比较 |
| `Path` 拼接与写文件 | `(HERE / "handoff.md").write_text(md)` | 括号让 `/` 先计算 |
| `json.dumps(asdict(...), indent=2)` | 写 `handoff.json` | dataclass → dict → JSON |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时目录副本中执行，退出码 0）打印的 Markdown：

```text
# Handoff: T-001

**Summary.** task T-001: review=pass, gate=True

## Changed files
- `app/signup.py`
- `tests/test_signup.py`
- `README.md`

## Commands run
- `pytest`
- `ruff check .`
- `pytest test_signup.py`
- `pytest test_signup.py`

## Failed attempts
- pytest test_signup.py -> exit 1

## Open risks
- [warn] off-scope: README.md
- [warn] open blocker: awaiting decision on rate-limit window

## Next action
open PR with current diff and request review

## Receipts
- verdict: `outputs/verification/T-001.json`
- review:  `outputs/review/T-001.json`
```

逐项解读：

- **Summary**：只有 review 与 gate 的状态，读者仍不知道"做了什么"（加输入验证）。
- **Commands run**：`pytest test_signup.py` 出现两次——第一次失败、第二次成功，这正是 `failed_attempts` 要保留的历史。
- **Failed attempts**：只有那条退出码 1 的记录。下一个会话据此知道"这个测试曾经失败过"，不会再从头排查。
- **Open risks**：gate 的 README 越界 warn + 状态中的 blocker（速率限制窗口待决定）；review 8 分 ≥ 7，不产生风险。
- **Next action**：来自状态文件的明确第一步。
- **Receipts**：按约定拼出的路径（实际文件并不存在于这些位置）。
- `handoff.json` 中的 `feedback_tail` 是全部 4 条（见 3.2）。

幂等性验证：连续运行两次，`handoff.json`、`handoff.md` 的 MD5 完全相同（`72d65b1a…`、`0f44de9e…`），满足 mission 的"identical packet"。

补充实验（均实测）：

| 输入 | 结果 |
|------|------|
| 100 条（34 条失败）+ 1 条超时 + 5 条成功 | `feedback_tail` 39 条，超时记录不在其中，顺序被打乱 |
| 空状态、空 verdict、空 review | 照样生成；`next_action` 为占位文字，`summary` 为 `review=None, gate=None` |
| gate 为红、review `hard_fail`、`total="n/a"`、`next_action="merge"` | 照样生成；review 风险被吞掉，`next_action` 仍是 `merge` |

---

## 7. 动手改一改

1. **修裁剪**：实现 `trim_feedback_v2(records, k=5, cap=30)`——按下标保序、包含 `None` 退出码、超过 30 条时优先保留最近的失败（参考测验 Q9）；同步让 `failed_attempts` 包含 `None`。
2. **preflight**：在生成前检查 gate 报告是否存在、`next_action` 是否为空、`clean_state.json` 是否为空、gate 为红时 `next_action` 是否合理，任何一项不满足就拒绝（参考测验 Q10）；`verdict_pointer` 指向的文件不存在时同样拒绝。
3. **讲义练习 1**：加 `assumptions_to_validate` 字段——列出 builder 记录、但 reviewer 在 assumptions 维度打分不超过 1 的假设。
4. **讲义练习 3、5**：加 "questions for the human" 与 "next session prereqs"（下一个会话行动前必须加载的产物列表）两个段落。
5. **多 agent 元数据**：给 payload 加 `branch`、`last_known_good_commit`、`status`，实现 `register_handoff` 让新 handoff 自动 supersede 同一分支同一主题的旧 handoff（参考测验 Q12）。
6. **写回 feature list**：任务关闭时把 `feature_list.json` 中对应 feature 的状态改成 `done`、清空 `active`（第 36 节），并用一个测试验证生成器两次运行输出完全相同（讲义练习 4）。

---

## 8. 常见坑

- **用占位文字填 `next_action`**：字段非空不等于有下一步；没有 `next_action` 就应拒绝生成。
- **默认值让"未知"变成"满意"**：review 缺失默认 10 分是 fail open；对风险评估来说，未知应当被当作风险。
- **忽略 `None` 退出码**：超时与启动失败是最需要交接的失败。
- **交接包无限增长**：失败记录越多越长，最终又回到"读不完"的问题；必须设上限。
- **指针不校验**：指向不存在文件的"收据"没有意义。
- **只写文档、不清理工作区**：讲义："A handoff built on a dirty tree is not a handoff, it is a forwarded mess."
- **破坏幂等的小细节**：时间戳、`set` 迭代顺序、绝对路径、目录遍历不排序。
- **在课程目录直接运行**：会在 `code/` 下生成 `handoff.md`、`handoff.json`。
