# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 39 节 Reviewer Agent：将实现者与评分者分开 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（无参数） ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`）；运行时会在 `code/` 下写 `review_report_T-001.json`、`review_report_T-002.json`

---

## 1. 这份代码在考察什么

这份代码是 reviewer agent 的**骨架**：它读取 builder 留下的产物（diff 摘要、状态、feedback、gate 结论），按讲义的五维 rubric 打分，给出 `pass` / `soft_fail` / `hard_fail`。对应讲义的概念：

1. **reviewer 的输入**：`ReviewerInputs` 把 builder 的各类产物打包，reviewer 只读不写。
2. **五维 rubric**：problem fit、scope discipline、assumptions、verification quality、handoff readiness，每维 0–2 分。
3. **结论规则**：任一维为 0 或总分 < 5 → hard fail；≥ 7 → pass；其余 soft fail。
4. **报告落盘**：每个任务一份 JSON，供人类评审从"已写好的报告"开始。

讲义明确说："Each function is deterministic and stub-grade for the lesson; real implementations would call an LLM."所以这份代码要学的是**结构**（输入是什么、按维度打分、每维一个函数、结论规则、报告格式），而每个打分函数的具体判断都只是占位。

> 一句话：**把"另一个角色按固定 rubric 审阅 builder 的产物"这件事的骨架搭出来**。同时要看清 stub 打分有多容易被刷分或误判——这正好说明为什么真实 reviewer 需要锚点、证据、置信度与校准集。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ReviewerInputs` | dataclass | 任务 id、目标、diff 摘要、状态、feedback、gate 结论 | builder 产物 |
| `DimensionScore` | dataclass | 维度名、分数、说明 | rubric 单项 |
| `ReviewReport` | dataclass | 总分、结论、各维度 | `review_report.json` |
| `score_problem_fit` | 函数 | goal 中的长词是否出现在被改文件路径里 | Problem fit |
| `score_scope_discipline` | 函数 | 看 gate findings 中的 scope 项 | Scope discipline |
| `score_assumptions` | 函数 | 状态中是否记录了假设 | Assumptions |
| `score_verification` | 函数 | feedback 的退出码 | Verification quality |
| `score_handoff` | 函数 | 任务是否关闭、是否有 `next_action` | Handoff readiness |
| `SCORERS` | 列表 | 五个打分函数 | rubric |
| `review` | 函数 | 依次打分、求和、按规则给结论 | reviewer 主循环 |
| `main` | 函数 | 两个场景：clean 与 "wrong problem"，写报告并打印 | demo |

数据流：`ReviewerInputs` → `SCORERS` 中五个函数各产出一个 `DimensionScore` → `review` 求和并判定 → `main` 写 `review_report_<task>.json` 并打印表格。

---

## 3. 逐段精讲

### 3.1 输入与输出

```python
@dataclass
class ReviewerInputs:
    task_id: str
    goal: str
    diff_summary: dict[str, list[str]]
    state: dict[str, object]
    feedback: list[dict[str, object]]
    verdict: dict[str, object]
```

对应讲义流程图中的 "diff + state + feedback + verdict"：

| 字段 | 来源 | 在 demo 中的形状 |
|------|------|----------------|
| `goal` | 合同（第 36 节）的 `goal` | `"add input validation to signup"` |
| `diff_summary` | git diff | `{"touched": [文件路径...]}`，只有文件名、没有内容 |
| `state` | 仓库状态文件（第 34 节） | `active_task_id`、`assumptions`、`next_action` |
| `feedback` | 第 37 节的 JSONL | `[{"command": ..., "exit_code": ...}]` |
| `verdict` | 第 38 节 gate 报告 | `{"passed": ..., "findings": [...]}` |

- "reviewer 不能改 diff"在这里体现为：输入只是数据，`review` 函数不写任何 builder 产物。不过 dataclass 默认是可变的，若要从代码层面强制只读，可以用 `@dataclass(frozen=True)`，并把字典包成 `types.MappingProxyType`。
- ⚠️ `diff_summary` 只有文件路径，没有改动内容——reviewer 无从判断"改得对不对"，这是后面多个打分函数只能看表面特征的根源。

```python
@dataclass
class ReviewReport:
    task_id: str
    total: int
    verdict: str
    dimensions: list[DimensionScore] = field(default_factory=list)
```

- ⚠️ 报告中没有证据引用和置信度，而 skill 把"Review reports that omit citations"列为 hard reject，讲义练习 3 要求 `confidence` 字段。

### 3.2 Problem fit：文件名关键词匹配

```python
def score_problem_fit(inputs: ReviewerInputs) -> DimensionScore:
    files = inputs.diff_summary.get("touched", [])
    goal = inputs.goal.lower()
    keywords = [w for w in goal.split() if len(w) > 4]
    hits = sum(any(k in f.lower() for f in files) for k in keywords)
    score = min(2, hits)
    return DimensionScore("problem_fit", score, f"keyword hits across touched files: {hits}")
```

- `len(w) > 4` 是一个粗糙的"停用词过滤"：`"add input validation to signup"` → `['input', 'validation', 'signup']`（`add`、`to` 被滤掉）。
- `sum(any(...) for k in keywords)`：对每个关键词，只要它出现在**任一**文件路径里就算 1（`True` 在求和时当作 1）。
- `min(2, hits)`：封顶 2 分。
- ⚠️ 实测问题：
  - 正确的 T-001（`app/signup.py`、`tests/test_signup.py`）只命中 `signup`，得 1 分；
  - 只写一份 `docs/input_validation_signup_notes.md` 的改动三词全中，**总分 10、`pass`**；
  - 改对了 `app/auth/register.py`（同义词）的改动得 0 分，**`hard_fail`**。
  这既能被刷分（起个好名字）也会误杀（用了同义词），衡量的是"文件名像不像目标"而不是"问题有没有被解决"。

### 3.3 Scope discipline：读 gate 的 findings

```python
def score_scope_discipline(inputs: ReviewerInputs) -> DimensionScore:
    off = inputs.verdict.get("findings", [])
    block_scope = [f for f in off if f.get("code") == "scope.forbidden"]
    if block_scope:
        return DimensionScore("scope_discipline", 0, "forbidden writes present")
    warn_scope = [f for f in off if f.get("code") == "scope.off_scope"]
    return DimensionScore("scope_discipline", 1 if warn_scope else 2, f"off-scope warnings: {len(warn_scope)}")
```

- 有 forbidden 写入 → 0；有越界 warn → 1；都没有 → 2。
- 变量名 `off` 其实是全部 findings，不只是越界项，命名略有误导。
- 讲义对这一维的提问是"Were edits confined to the contract **or was the contract grown deliberately**?"——有意且经过批准的扩大不应扣分，但代码只看 finding 是否存在，无法区分"偷偷越界"与"按流程扩大合同"。
- 这一维本质上是在复用 gate 的结果；真正的语义评审应该看越界改动是否有理由、是否在报告里被说明。

### 3.4 Assumptions：有没有写

```python
def score_assumptions(inputs: ReviewerInputs) -> DimensionScore:
    assumptions = inputs.state.get("assumptions") or []
    if not assumptions:
        return DimensionScore("assumptions", 1, "no assumptions recorded; either work was trivial or undocumented")
    return DimensionScore("assumptions", 2, f"{len(assumptions)} assumptions recorded")
```

- `x or []`：键不存在（`None`）或为空时都得到空列表。
- 没有假设给 1 分而不是 0 分，note 解释了原因："要么工作太简单，要么没记录"——stub 无法区分，所以给中间分。
- ⚠️ 只要写了任意一条假设就是满分，不判断假设是否合理、是否"本该被质疑"（讲义的提问："Are all hidden assumptions written down somewhere reviewable?"）。

### 3.5 Verification quality：只看退出码

```python
def score_verification(inputs: ReviewerInputs) -> DimensionScore:
    exits = [rec.get("exit_code") for rec in inputs.feedback]
    if any(code is None for code in exits):
        return DimensionScore("verification_quality", 0, "feedback log has missing exit codes")
    if all(code == 0 for code in exits) and exits:
        return DimensionScore("verification_quality", 2, "all feedback exit zero")
    return DimensionScore("verification_quality", 1, "mixed exit codes in feedback")
```

- 任何 null 退出码 → 0；全部为 0 且非空 → 2；否则 1。
- `all(...) and exits`：`all([])` 为 `True`（空集上的全称命题为真），所以要加 `and exits` 排除空列表。
- ⚠️ `feedback=[]` 落到最后一行：得 1 分，note 却是 "mixed exit codes"——没有任何证据却拿到中间分，且说明文字错误（实测）。
- ⚠️ "先失败、修复后重试成功"也是 1 分（"mixed"），而这是正常流程。
- ⚠️ 讲义的问题是"验收命令是否真的证明了目标，还是只证明了更弱的版本"。退出码检查是 gate 的工作（"don't ask the reviewer to redo what the gate already proves"），这一维在真实实现中应读测试内容并与 goal 对照。

### 3.6 Handoff readiness

```python
def score_handoff(inputs: ReviewerInputs) -> DimensionScore:
    if inputs.state.get("active_task_id"):
        return DimensionScore("handoff_readiness", 1, "active task not closed in state")
    if inputs.state.get("next_action"):
        return DimensionScore("handoff_readiness", 2, "next_action set, task closed")
    return DimensionScore("handoff_readiness", 0, "no next_action recorded")
```

| 状态 | 分数 |
|------|-----|
| 还有活动任务（未关闭） | 1 |
| 任务已关闭且有 `next_action` | 2 |
| 任务已关闭但没有 `next_action` | 0 |

- 判断顺序决定结果：只要 `active_task_id` 非空就返回 1，不再检查 `next_action`。所以"任务没关、也没写下一步"也是 1 分，反而高于"任务关了但没写下一步"的 0 分——顺序值得推敲。
- 第 40 节的 handoff 会把这些字段系统化。

### 3.7 `review`：求和与结论

```python
SCORERS = [score_problem_fit, score_scope_discipline, score_assumptions, score_verification, score_handoff]


def review(inputs: ReviewerInputs) -> ReviewReport:
    dims = [fn(inputs) for fn in SCORERS]
    total = sum(d.score for d in dims)
    has_zero = any(d.score == 0 for d in dims)
    if has_zero or total < 5:
        verdict = "hard_fail"
    elif total >= 7:
        verdict = "pass"
    else:
        verdict = "soft_fail"
    return ReviewReport(task_id=inputs.task_id, total=total, verdict=verdict, dimensions=dims)
```

- **函数作为一等对象**：`SCORERS` 是函数列表，`[fn(inputs) for fn in SCORERS]` 依次调用。新增维度（讲义练习 1）只需写一个函数并加进列表。
- 结论规则与讲义 Key Terms 一致："Hard fail: Total below 5 or any dimension at 0"；"Soft fail: Total below 7"。
- 穷举 3⁵ = 243 种分数组合可知：`pass` 对应总分 7–10（且无 0 分）；`soft_fail` 只可能是总分 5 或 6 且无 0 分；任何含 0 分的组合都是 `hard_fail`，哪怕总分是 8。
- ⚠️ `review` **完全不看 `verdict["passed"]`**：gate 未通过（`passed=False`）甚至根本没有 gate 报告（`verdict={}`）时，T-001 的输入照样拿 9 分 `pass`（实测）。skill 规定："If the builder produces no verification report, refuse to run the reviewer."
- ⚠️ 没有置信度下限、没有证据要求、没有校准——这些都是讲义和 skill 对真实 reviewer 的要求。

### 3.8 `main()`：两个场景

```python
    clean = ReviewerInputs(task_id="T-001", goal="add input validation to signup",
        diff_summary={"touched": ["app/signup.py", "tests/test_signup.py"]},
        state={"active_task_id": None, "assumptions": ["users sign up with email + password only"],
               "next_action": "pick next task from board"},
        feedback=[{"command": "pytest", "exit_code": 0}],
        verdict={"passed": True, "findings": []})
    wrong = ReviewerInputs(task_id="T-002", goal="add input validation to signup",
        diff_summary={"touched": ["docs/api.md"]},
        state={"active_task_id": "T-002", "assumptions": [], "next_action": ""},
        feedback=[{"command": "pytest", "exit_code": 0}],
        verdict={"passed": True, "findings": [{"code": "scope.off_scope", "severity": "warn"}]})
```

- 两个场景的 gate 结论都是 `passed: True`、测试都退出 0——这正是讲义开场的情形："gate 说通过，但做错了事"。
- `wrong` 只改了 `docs/api.md`。讲义/mission 称它为 "right tests, wrong problem"，但 demo 里其实没有"正确的测试"，只有一条笼统的 `pytest` 记录；更贴切的描述是"测试通过，但改动与目标无关"。
- 报告写到 `HERE / f"review_report_{case.task_id}.json"`（`code/` 下）。skill 规定的规范路径是 `outputs/review/<task_id>.json`。
- `f"{d.name:22}"`：字符串左对齐、宽度 22，用来对齐打印表格。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 每维一个函数 + `SCORERS` 列表 | 结构清晰、易扩展、易单测 | 无 |
| 确定性 stub 打分 | 课程自包含、可复现 | 可被刷分、会误杀；生产中换成带锚点和证据的 LLM 打分 |
| 只用文件路径做 diff 摘要 | 简单 | 无法判断改动内容；真实 reviewer 要读 diff 正文 |
| reviewer 复用 gate 的 scope findings、退出码 | 少写代码 | 重做 gate 的工作；讲义要求 reviewer 专注语义判断 |
| 0/1/2 三档 + 总分阈值 | 粗粒度、易对齐 | 缺少锚点描述时会"collapse to vibes"（skill） |
| 任一维 0 → hard fail | 让单一致命问题不被其他高分掩盖 | 总分 8 也可能 hard fail，需要在报告中说明原因 |
| 不检查 gate 是否通过 | demo 简单 | 应先确认 gate 为绿再评审（skill 拒绝规则） |
| 报告写在 `code/` | demo 简单 | 规范路径 `outputs/review/<task_id>.json`，并贴到 PR |
| 无置信度、无证据、无校准 | demo 简单 | 讲义练习 3、4 与 skill 都要求补上 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class ReviewerInputs:` | 自动生成构造函数等 |
| `field(default_factory=list)` | `dimensions: list[DimensionScore] = field(default_factory=list)` | 可变默认值 |
| 类型注解 | `dict[str, list[str]]`、`list[dict[str, object]]` | 描述数据结构 |
| 函数作为一等对象 | `SCORERS = [score_problem_fit, ...]`、`[fn(inputs) for fn in SCORERS]` | 函数可以放进列表、作为值传递和调用 |
| `str.lower()` / `str.split()` | `inputs.goal.lower().split()` | 小写化、按空白切词 |
| 子串判断 `in` | `k in f.lower()` | 字符串包含 |
| 布尔值求和 | `sum(any(...) for k in keywords)` | `True` 当 1、`False` 当 0 |
| `any` / `all` | `any(code is None for code in exits)`、`all(code == 0 for code in exits)` | `all([])` 为 `True`，要注意空集合 |
| `x or []` | `inputs.state.get("assumptions") or []` | `None` 或空值时取默认 |
| 条件表达式 | `1 if warn_scope else 2` | 三元表达式 |
| `min` 封顶 | `min(2, hits)` | 限制最大值 |
| 带条件的列表推导式 | `[f for f in off if f.get("code") == "scope.forbidden"]` | 过滤 |
| `if/elif/else` 链 | `review` 的结论判定 | 按顺序匹配第一个为真的分支 |
| `asdict` + `json.dumps(indent=2)` | 写报告 | dataclass → dict → 格式化 JSON |
| `Path.write_text` | `out.write_text(...)` | 一次写入整个文件 |
| f-string 宽度 | `f"{d.name:22}"` | 字符串默认左对齐、占 22 个字符 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时目录副本中执行，退出码 0）：

```text
task T-001: total=9/10 verdict=pass
  problem_fit            1  keyword hits across touched files: 1
  scope_discipline       2  off-scope warnings: 0
  assumptions            2  1 assumptions recorded
  verification_quality   2  all feedback exit zero
  handoff_readiness      2  next_action set, task closed

task T-002: total=5/10 verdict=hard_fail
  problem_fit            0  keyword hits across touched files: 0
  scope_discipline       1  off-scope warnings: 1
  assumptions            1  no assumptions recorded; either work was trivial or undocumented
  verification_quality   2  all feedback exit zero
  handoff_readiness      1  active task not closed in state
```

逐项解读：

- **T-001（clean）**：9 分 `pass`，满足 mission 的"clean change scores at least 7"。唯一的扣分在 problem fit：只有 `signup` 出现在路径里，`input`、`validation` 没有。
- **T-002（wrong problem）**：
  - problem fit 0：`docs/api.md` 不含任何关键词；
  - scope discipline 1：gate findings 中有一条 `scope.off_scope`；
  - assumptions 1：没有记录假设；
  - verification quality 2：测试退出 0——gate 和测试都"通过"了，这正是讲义要说明的情形；
  - handoff readiness 1：任务还处于活动状态；
  - 总分 5 不满足 `< 5`，结论 `hard_fail` 是由 problem fit 的 0 分触发的。若 problem fit 为 1，总分 6，结论会是 `soft_fail`。
- 两份报告写到了 `code/review_report_T-001.json`、`code/review_report_T-002.json`。

补充实验（均实测，其余输入与 T-001 相同）：

| 改动 | 总分 | 结论 |
|------|-----|------|
| `touched=["docs/input_validation_signup_notes.md"]` | 10 | pass |
| `touched=["app/auth/register.py"]` | 8 | hard_fail |
| `feedback=[]` | 8 | pass（verification 得 1，note 写 "mixed exit codes"） |
| gate `passed=False` | 9 | pass |
| `verdict={}` | 9 | pass |

---

## 7. 动手改一改

1. **前置条件**：实现 `review_v2`——没有 gate 报告或 gate 未通过时返回 `refused`（参考测验 Q10）。
2. **证据与置信度（讲义练习 3）**：给 `DimensionScore` 加 `evidence: list[str]` 与 `confidence: float`；任一维度缺证据或最低置信度 < 0.6 时结论改为 `needs_human`（参考测验 Q11）。
3. **锚点 rubric**：为五个维度各写 0/1/2 的锚点描述，放进 `docs/reviewer-rubric.md`；把它们拼进 reviewer 的 system prompt，并要求输出 JSON（分数、锚点编号、证据、置信度）。
4. **换成 LLM 打分**：保持 `SCORERS` 结构不变，把 `score_problem_fit` 换成调用模型的版本，输入 goal、合同和 diff 正文；用不同于 builder 的 system prompt。
5. **校准集（讲义练习 4）**：整理 10 个历史任务（输入 + 人类给出的结论），写一个脚本计算 reviewer 与历史结论的一致率，低于 80% 时让 CI 失败。
6. **位置偏差缓解**：在做"两个候选方案哪个更好"的比较时，两种顺序都评一次，只计一致的胜出（参考测验 Q12）；再加一个领域专属的第六维（讲义练习 1）。

---

## 8. 常见坑

- **用表面特征打分**：文件名关键词、"有没有写假设"、退出码，这些都能被 builder 轻易满足，也会误杀合理改动。
- **reviewer 重做 gate 的工作**：退出码、forbidden 写入是 gate 的职责；reviewer 应回答"是不是对的问题、验收是否证明了目标"。
- **gate 没过就评审**：浪费成本，而且可能给一个失败的任务打出 `pass`。
- **`all([])` 为 `True`**：判断"全部成功"时要先排除空列表，否则"没有证据"会被当成"全部成功"。
- **只看总分**：任一维为 0 就是 hard fail，报告里要写清楚是哪一维。
- **reviewer 有写权限**：一旦 reviewer 能改 diff，builder 与 reviewer 之间的差距就消失了（skill 的第一条 hard reject）。
- **复用 builder 的 system prompt**："Same model is fine; same prompt is not."
- **在课程目录直接运行**：会在 `code/` 下生成两份报告文件。
