# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 44 节 制定有证据支撑的执行计划 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在本节目录下 `python3 code/main.py`；测试 `python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`；测试用 `unittest`、`importlib.util`）

---

## 1. 这份代码在考察什么

讲义的核心论点："计划不是更漂亮的待办清单，而是一张依赖图——每个变更都有理由，每个终点都有证明。"这份代码把它落成三个能力：

1. **工作项建模**：`WorkItem` 的五个字段正好是讲义要求的五个承诺——Identifier、Change、Evidence、Dependencies、Proof。
2. **执行前拒绝坏计划**：`validate()` 实现讲义六条拒绝规则中的五条机械检查（ID 重复、无证据、无 proof、依赖未知项、环）。
3. **计算执行波次**：`execution_waves()` 用分层拓扑排序把工作项分成若干"波"，同一波内可并行，体现"先契约、后实现与文档并行、最后集成"。

最终产物 `outputs/evidence-plan.json` 是下一节委派的输入（讲义："It becomes the delegation contract in the next lesson"）。

> 一句话：**把"先做什么、凭什么、怎么算完成"变成一张能被机器检查和调度的图**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `WorkItem` | 不可变 dataclass | `id`、`change`、`evidence`、`depends_on`、`proof` | 五个承诺 |
| `validate(items)` | 函数 | 返回问题列表；先查结构，再借 `execution_waves` 查环 | 六条拒绝规则中的五条 |
| `execution_waves(items)` | 函数 | 分层拓扑排序；未知依赖或环时抛 `ValueError` | 安全并发 |
| `plan_document(items)` | 函数 | 组装 `status / issues / waves / items` 字典 | 计划的 JSON 形态 |
| `example()` | 函数 | 重复邮件任务的四个工作项 | contract → impl/docs → integration |
| `main()` | 函数 | 写 `outputs/evidence-plan.json` 并打印 | 产物 |
| `tests/test_main.py` | 测试 | 7 个 `unittest` 用例 | 见第 9 节 |

数据流：`example()` → `plan_document()`（内部 `validate()` → 若无问题再 `execution_waves()`）→ `json.dumps(indent=2)` → 写文件并打印。

---

## 3. 逐段精讲

### 3.1 文件头与 `WorkItem`

```python
# Reference: PERT, U.S. Navy Special Projects Office, 1958.
# Reference: CPM, Kelley and Walker, Eastern Joint Computer Conference, 1959.

@dataclass(frozen=True)
class WorkItem:
    id: str
    change: str
    evidence: tuple[str, ...]
    depends_on: tuple[str, ...]
    proof: str
```

- 文件头引用了 PERT 与 CPM 两种经典项目网络方法，代码借用的是它们"用依赖图安排工作"的思想；它没有工期，也不计算关键路径。
- `frozen=True`：工作项一旦写入计划就不可修改，要改就换一个新对象——这让"计划变更"成为显式动作。
- `evidence` 和 `depends_on` 用 `tuple[str, ...]`（任意长度的字符串元组）而不是 `list`：frozen dataclass 的字段最好也是不可变的，否则 `item.evidence.append(...)` 仍能修改内容；元组还能哈希。
- 五个字段与讲义五个承诺的对应：

| 讲义承诺 | 字段 | 示例（`implementation` 项） |
|---------|------|---------------------------|
| Identifier | `id` | `"implementation"` |
| Change | `change` | `"Reject normalized duplicates"` |
| Evidence | `evidence` | `("app/accounts.py:18",)` |
| Dependencies | `depends_on` | `("contract",)` |
| Proof | `proof` | `"python3 -m unittest tests.test_accounts"` |

- 注意单元素元组要写成 `("app/accounts.py:18",)`，结尾的逗号不能省；`()` 是空元组。

### 3.2 `validate()`：五条机械检查

```python
def validate(items: list[WorkItem]) -> list[str]:
    issues: list[str] = []
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        issues.append("work item ids must be unique")
    known = set(ids)
    has_unknown_dependency = False
    for item in items:
        if not item.evidence:
            issues.append(f"{item.id} has no repository evidence")
        if not item.proof.strip():
            issues.append(f"{item.id} has no proof command")
        missing = sorted(set(item.depends_on) - known)
        if missing:
            has_unknown_dependency = True
            issues.append(f"{item.id} depends on unknown items: {', '.join(missing)}")
    if not has_unknown_dependency:
        try:
            execution_waves(items)
        except ValueError as error:
            issues.append(str(error))
    return issues
```

| 讲义拒绝规则 | 代码实现 | 消息 |
|------------|---------|------|
| ID 重复 | `len(ids) != len(set(ids))` | `work item ids must be unique` |
| 无证据 | `not item.evidence` | `<id> has no repository evidence` |
| 无 proof | `not item.proof.strip()` | `<id> has no proof command` |
| 依赖未知项 | `set(depends_on) - known` | `<id> depends on unknown items: ...` |
| 存在环 | 调用 `execution_waves` 捕获 `ValueError` | `dependency cycle among: ...` |
| 第一个不可逆动作早于相关不确定性解决 | **未实现**（讲义说需要判断） | — |

- 一次遍历收集**全部**问题，而不是遇到第一个就返回：对一个"无证据 + 无 proof + 依赖未知"的工作项，实测输出三条：`['a has no repository evidence', 'a has no proof command', 'a depends on unknown items: zz']`。
- `set(item.depends_on) - known`：集合差，得到依赖中不存在的 ID；`sorted` 保证消息顺序稳定。
- **为什么有未知依赖时跳过环检测**：`execution_waves` 开头也会检查未知依赖并抛出同样的消息，若不跳过就会重复报告。代价是：同时存在未知依赖和环时，环会被暂时"藏起来"——实测 `a→b, b→(a, q)` 只报告 `b depends on unknown items: q`，修好之后才会看到环。
- ⚠️ 证据检查只看元组是否为空：`evidence=("",)` 能通过（实测 `[]`），与 proof 用了 `strip()` 的标准不一致。
- ⚠️ 只检查 proof 非空，`"review contract"` 这种不可执行的描述也能通过。

### 3.3 `execution_waves()`：分层拓扑排序

```python
def execution_waves(items: list[WorkItem]) -> list[list[str]]:
    known = {item.id for item in items}
    for item in items:
        missing = sorted(set(item.depends_on) - known)
        if missing:
            raise ValueError(f"{item.id} depends on unknown items: {', '.join(missing)}")
    remaining = {item.id: set(item.depends_on) for item in items}
    waves: list[list[str]] = []
    completed: set[str] = set()
    while remaining:
        ready = sorted(item_id for item_id, deps in remaining.items() if deps <= completed)
        if not ready:
            cycle = ", ".join(sorted(remaining))
            raise ValueError(f"dependency cycle among: {cycle}")
        waves.append(ready)
        completed.update(ready)
        for item_id in ready:
            del remaining[item_id]
    return waves
```

逐步执行示例计划：

| 轮次 | `completed` | 就绪（`deps <= completed`） | 本轮波次 |
|------|------------|---------------------------|---------|
| 1 | `{}` | `contract`（无依赖） | `['contract']` |
| 2 | `{contract}` | `docs`、`implementation`（都只依赖 contract） | `['docs', 'implementation']` |
| 3 | `{contract, docs, implementation}` | `integration` | `['integration']` |
| — | `remaining` 为空 | 结束 | |

- 这是 Kahn 算法的"按层"版本：普通 Kahn 每次取一个入度为 0 的节点，这里每轮取**全部**就绪节点作为一波，同一波内的项可以并行。
- `deps <= completed`：集合的子集判断，表示"所有依赖都已完成"。
- `sorted(...)`：同一波内按字母序排列，保证输出确定（所以是 `docs` 在 `implementation` 前，与讲义描述的顺序无关）。
- 先检查未知依赖再排序：否则一个依赖了不存在项的工作项永远不会就绪，会被误报为"环"。测试 `test_execution_waves_rejects_unknown_dependency_before_cycle_detection` 专门锁定这一点。
- ⚠️ 环报错列出 `remaining` 中的**所有**项：`a↔b` 加下游 `c→a` 时报 `dependency cycle among: a, b, c`，`c` 并不在环中（见测验 Q9 的 DFS 修正）。
- ⚠️ `remaining` 是字典推导式，重复 ID 后者覆盖前者。直接调用（不经过 `validate`）时，两个 `a`（一个无依赖、一个依赖 `b`）加一个 `b` 得到 `[['b'], ['a']]`，第一个 `a` 被静默丢失。
- 复杂度：每轮扫描全部剩余项，最坏 O(n²)；对几十个工作项的计划完全够用。

### 3.4 `plan_document()`：计划的 JSON 形态

```python
def plan_document(items: list[WorkItem]) -> dict:
    issues = validate(items)
    return {
        "status": "ready" if not issues else "blocked",
        "issues": issues,
        "waves": execution_waves(items) if not issues else [],
        "items": [asdict(item) for item in items],
    }
```

- 有任何问题就 `blocked`，并且**不输出波次**（`[]`）——避免下游拿到一份部分正确的调度去执行。测试 `test_invalid_documents_never_emit_execution_waves` 锁定了这一点。
- `asdict(item)` 把 dataclass 转字典，元组字段保持为元组，`json.dumps` 会把元组写成 JSON 数组。
- 计划文档里没有 `status` per item、`artifacts`、`proof_ran_at` 等字段——讲义 "Design for Interruption" 要求的可恢复信息需要自行扩展（测验 Q11）。

### 3.5 `example()`：重复邮件任务的计划

```python
def example() -> list[WorkItem]:
    return [
        WorkItem("contract", "Define duplicate-email behavior", ("tests/test_accounts.py:44",), (), "review contract"),
        WorkItem("implementation", "Reject normalized duplicates", ("app/accounts.py:18",), ("contract",), "python3 -m unittest tests.test_accounts"),
        WorkItem("docs", "Document the 409 response", ("docs/api.md:72",), ("contract",), "python3 scripts/check_links.py"),
        WorkItem("integration", "Run the complete acceptance gate", ("pyproject.toml:31",), ("implementation", "docs"), "python3 -m unittest"),
    ]
```

- 结构与讲义的 mermaid 图一致：Contract → Implementation / Documentation → Integration gate。
- 证据沿用了第 43 节 task frame 中的收据（`tests/test_accounts.py:44`、`app/accounts.py:18`），并新增了 `docs/api.md:72`、`pyproject.toml:31`；这些都是示意路径，仓库中并不存在。
- ⚠️ `contract` 的 proof 是 `"review contract"`，不是讲义说的 "exact check"。
- ⚠️ `implementation` 写的是 "Reject **normalized** duplicates"：第 43 节把"邮件比较是否大小写不敏感"列为 unknown，这里却直接假定要规范化——计划悄悄回答了一个尚未授权的问题。按讲义第六条规则，应在实现前加一个人类决策项（测验 Q10）。
- `docs` 的 proof `check_links.py` 只能证明链接没坏，不能证明文档写对了 409 契约，proof 与 change 的对应关系偏弱。

### 3.6 `main()`

```python
def main() -> None:
    output = Path(__file__).resolve().parents[1] / "outputs" / "evidence-plan.json"
    output.write_text(json.dumps(plan_document(example()), indent=2) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))
```

- 写到 `<本节>/outputs/evidence-plan.json`；直接在仓库里运行会覆盖已提交的文件（实测内容完全相同）。
- 本脚本**不读取**第 43 节的 `task-frame.md`：讲义说 frame 是计划的输入，但代码里两者的衔接是人工完成的（示例中复制了 frame 的证据）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| `WorkItem` frozen + 元组字段 | 计划项不可悄悄修改，可哈希 | 状态（进度）无处存放；生产中把"定义"与"运行状态"分成两个结构 |
| `validate` 收集全部问题 | 一次看到所有缺陷 | 有未知依赖时环检测被跳过，问题需分两轮暴露 |
| 环检测复用 `execution_waves` | 少写一份图算法 | 报错列出所有剩余项而非环本身；可改用 DFS 求环路径 |
| 分层拓扑排序得到"波次" | 直观展示可并行的工作 | 不考虑工期与资源；需要排期时用 CPM 计算关键路径 |
| 波内 `sorted` | 输出确定、测试稳定 | 字母序不代表优先级 |
| blocked 时不输出波次 | 防止执行部分正确的计划 | — |
| 证据、proof 只查非空 | 简单 | `("",)`、`"review contract"` 都能通过；应校验格式与存在性 |
| 不可逆动作检查未实现 | 讲义说需要判断 | 可加"不可逆项的祖先中必须有审批项"的半自动检查 |
| JSON 作为产物 | 机器可读，供下一节委派 | 人类阅读需要渲染视图（讲义练习 5） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class WorkItem` | 不可变数据类 |
| 变长元组注解 | `evidence: tuple[str, ...]` | `...` 表示任意长度 |
| 单元素元组 | `("tests/test_accounts.py:44",)` | 结尾逗号不可省；`()` 是空元组 |
| 列表推导式 | `ids = [item.id for item in items]` | 提取所有 ID |
| 集合推导式 | `known = {item.id for item in items}` | 去重后的 ID 集合 |
| 字典推导式 | `remaining = {item.id: set(item.depends_on) for item in items}` | 重复键会被后者覆盖 |
| 集合差 / 子集 | `set(a) - known`、`deps <= completed` | 求缺失项；判断"全部依赖已完成" |
| `set.update` | `completed.update(ready)` | 批量加入元素 |
| `del dict[key]` | `del remaining[item_id]` | 删除键 |
| `while` 循环 + 空字典为假 | `while remaining:` | 字典空时结束 |
| 生成器表达式传给 `sorted` | `sorted(item_id for item_id, deps in remaining.items() if deps <= completed)` | 过滤并排序 |
| `try / except ... as` | `except ValueError as error: issues.append(str(error))` | 把异常消息转为问题条目 |
| `raise ValueError(f"...")` | 环、未知依赖 | 用异常表示无法调度 |
| 条件表达式 | `"ready" if not issues else "blocked"` | 二选一 |
| `asdict` | `[asdict(item) for item in items]` | dataclass → dict |
| `json.dumps(..., indent=2)` | `main()` | 生成可读 JSON；元组写成数组 |
| `Path(__file__).resolve().parents[1]` | `main()` | 本节目录 |
| 返回类型注解 | `-> list[list[str]]` | 嵌套列表 |

测试文件中额外出现：`assertRaisesRegex`（断言抛出异常且消息匹配正则）、`self.subTest(items=items)`（在一个测试中参数化多组输入，任何一组失败都会单独报告）。

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时目录的本节副本中执行，退出码 0）：

```text
{
  "status": "ready",
  "issues": [],
  "waves": [
    ["contract"],
    ["docs", "implementation"],
    ["integration"]
  ],
  "items": [
    {
      "id": "contract",
      "change": "Define duplicate-email behavior",
      "evidence": ["tests/test_accounts.py:44"],
      "depends_on": [],
      "proof": "review contract"
    },
    ...
  ]
}
```

（实际输出中每个数组元素各占一行，这里为节省篇幅做了合并。）

- 与仓库中已提交的 `outputs/evidence-plan.json` 逐字一致。
- **status: ready / issues: []**：四个工作项 ID 唯一、都有证据和 proof、依赖都存在、无环。
- **三个波次**：与讲义 "The example produces three waves" 一致。
- 额外实测的边界情况：

| 输入 | 结果 |
|------|------|
| `a→b, b→a, c→a` | `['dependency cycle among: a, b, c']`（`c` 被误列入环） |
| `a→a`（自依赖） | `['dependency cycle among: a']` |
| `evidence=("",)` | `[]`（空字符串证据通过） |
| 无证据、空白 proof、依赖 `zz` | 三条问题同时报告 |
| `a→b, b→(a, q)` | 只报 `b depends on unknown items: q`，环被暂时掩盖 |
| 示例 + 依赖 `contract` 的 `migration` | 波次 `[['contract'], ['docs', 'implementation', 'migration'], ['integration']]`，迁移与实现并行 |

---

## 7. 动手改一改

1. **讲义练习 1**：加一个 `migration` 项和一个人类审批项 `approve-normalization`，让迁移和实现都依赖审批；验证波次变为 `[['contract'], ['approve-normalization', 'docs'], ['implementation', 'migration'], ['integration']]`（参考测验 Q10）。
2. **讲义练习 2**：构造 `implementation` 依赖 `docs`、`docs` 依赖 `implementation` 的环，写下它背后隐藏的产品分歧（"错误体格式由谁先定"），再用一个 `contract` 节点打破它。
3. **讲义练习 3、4**：把一个有两个 proof 命令的项拆成两项；再加一个只依赖 `contract`、不碰实现和文档的第二波项（如 `changelog`），验证它出现在第二波（实测 `['changelog', 'docs', 'implementation']`）。
4. **更好的环报错**：实现 DFS `find_cycle`，让报错变成 `dependency cycle: a -> b -> a`，并单独列出被阻塞的下游项（参考测验 Q9）。
5. **可恢复性**：给计划加 `status`、`proof_ran_at`、`artifacts`，实现 `next_safe_items(items, completed)`（参考测验 Q11）。
6. **讲义练习 5**：写 `render_markdown(document)`，从 JSON 渲染 Markdown，并在测试中断言"重新渲染结果与提交的 Markdown 一致"（参考测验 Q12）。

---

## 8. 常见坑

- **单元素元组漏逗号**：`("app/accounts.py:18")` 是字符串而不是元组，`not item.evidence` 仍为假，看起来能工作，但 `asdict` 后在 JSON 里变成字符串，下游按数组处理就会出错。
- **把波内顺序当优先级**：`sorted` 只是为了输出稳定。
- **直接调用 `execution_waves` 跳过 `validate`**：重复 ID 会被静默合并。
- **看到"dependency cycle among"就去改列出的每一项**：列表包含下游被阻塞的项，先找出真正的环。
- **以为 `ready` 就代表计划好**：证据真实性、proof 是否可执行、不可逆动作的位置都没有被检查。
- **让计划悄悄回答 unknown**：从 task frame 继承来的 human unknown，必须在计划中变成显式的审批项，而不是写进某个工作项的 change 描述里。
- **直接在仓库中运行**：会覆盖已提交的 `outputs/evidence-plan.json`。

---

## 9. 测试在验证什么

测试文件 `code/tests/test_main.py` 用 `importlib` 按路径加载 `main.py`（模块名 `lesson44`）。

| 测试 | 构造 | 断言 | 验证的性质 |
|------|------|------|-----------|
| `test_example_has_three_execution_waves` | `example()` | 波次等于 `[['contract'], ['docs', 'implementation'], ['integration']]` | 分层拓扑排序与波内排序正确 |
| `test_missing_evidence_blocks_plan` | 证据为空元组的项 | 含 `a has no repository evidence` | 无证据被拒 |
| `test_missing_dependency_is_reported` | 依赖 `missing` | 某条问题含 `unknown items` | 未知依赖被报告 |
| `test_execution_waves_rejects_unknown_dependency_before_cycle_detection` | 同上，直接调 `execution_waves` | 抛 `ValueError`，消息匹配 `a depends on unknown items: missing` | 未知依赖优先于环检测，不会被误报为环 |
| `test_cycle_is_rejected` | `a↔b` | 抛 `ValueError`，消息含 `dependency cycle` | 环被检测 |
| `test_document_keeps_proof_commands` | `plan_document(example())` | `status == "ready"`，最后一项 proof 为 `python3 -m unittest` | JSON 文档保留 proof 字段 |
| `test_invalid_documents_never_emit_execution_waves` | 两组非法计划（无证据；重复 ID），用 `subTest` | `status == "blocked"` 且 `waves == []` | 非法计划不会输出部分调度 |

运行方式（在本节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：

```text
test_cycle_is_rejected (test_main.EvidencePlanTests.test_cycle_is_rejected) ... ok
test_document_keeps_proof_commands (test_main.EvidencePlanTests.test_document_keeps_proof_commands) ... ok
test_example_has_three_execution_waves (test_main.EvidencePlanTests.test_example_has_three_execution_waves) ... ok
test_execution_waves_rejects_unknown_dependency_before_cycle_detection (...) ... ok
test_invalid_documents_never_emit_execution_waves (...) ... ok
test_missing_dependency_is_reported (test_main.EvidencePlanTests.test_missing_dependency_is_reported) ... ok
test_missing_evidence_blocks_plan (test_main.EvidencePlanTests.test_missing_evidence_blocks_plan) ... ok

----------------------------------------------------------------------
Ran 7 tests in 0.001s

OK
```

测试没有覆盖的地方：

- 无 proof（空白字符串）没有单独测试；
- 环报错的**内容**（是否只列出环成员）没有断言，所以"把下游项也列进去"的问题不会被发现；
- 空字符串证据 `("",)`、重复 ID 直接传给 `execution_waves` 的行为没有测试；
- 讲义第六条（不可逆动作）没有任何检查，自然也没有测试。
