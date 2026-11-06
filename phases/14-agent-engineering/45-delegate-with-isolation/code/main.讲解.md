# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 45 节 通过隔离与合并契约委派 Agent 任务 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在本节目录下 `python3 code/main.py`；测试 `python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib.PurePosixPath`；测试用 `unittest`、`importlib.util`）

---

## 1. 这份代码在考察什么

讲义的核心论点："并行 agent 只有在工作真正独立时才省时间。"这份代码把"真正独立"中最容易机械检查的部分落成代码：

1. **工作单元即契约**：`WorkUnit` 记录 ID、负责人、独占路径、依赖、proof。
2. **所有权隔离**：`paths_overlap` + `conflicts` 检查任意两个单元的路径是否相同或有父子关系——讲义 Build It："Change the docs unit to own `app/`. The plan should block."
3. **执行波次**：`waves` 用分层拓扑排序算出哪些单元可以并行、集成单元何时开始。
4. **委派计划文档**：`delegation_plan` 汇总重复 ID、路径冲突、缺失 proof 和波次，写成 `outputs/delegation-plan.json`。

它只覆盖了讲义"隔离三层"中的**所有权隔离**；文件系统隔离（worktree）和状态隔离（独立日志/输出）属于运行时，代码没有涉及。

> 一句话：**在派活之前，用机器检查"谁拥有哪些路径、谁要等谁、凭什么算完成"**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `WorkUnit` | 不可变 dataclass | `id`、`owner`、`paths`、`depends_on`、`proof` | 工作单元契约（讲义六字段中的五个，缺 Goal、Handoff） |
| `paths_overlap(left, right)` | 函数 | 两条路径相同或互为祖先即重叠 | 独占写权限 |
| `conflicts(units)` | 函数 | 两两比较所有单元的所有路径 | 所有权隔离 |
| `waves(units)` | 函数 | 分层拓扑排序；未知依赖或环抛 `ValueError` | 安全执行波次 |
| `delegation_plan(units)` | 函数 | 汇总重复 ID、冲突、缺 proof、波次 | 委派计划 |
| `example()` | 函数 | api、docs 并行，integration 收尾 | 讲义 mermaid 图 |
| `main()` | 函数 | 写 `outputs/delegation-plan.json` 并打印 | 产物 |
| `tests/test_main.py` | 测试 | 6 个 `unittest` 用例 | 见第 9 节 |

数据流：`example()` → `delegation_plan()`（内部 `conflicts()` → `paths_overlap()`；`waves()`）→ `json.dumps(indent=2)` → 写文件并打印。

---

## 3. 逐段精讲

### 3.1 文件头与 `WorkUnit`

```python
# Reference: Git worktree documentation, git-scm.com/docs/git-worktree.
# Reference: Lamport, Time, Clocks, and the Ordering of Events, 1978.

@dataclass(frozen=True)
class WorkUnit:
    id: str
    owner: str
    paths: tuple[str, ...]
    depends_on: tuple[str, ...]
    proof: str
```

- 文件头引用了 git worktree（文件系统隔离的标准工具）和 Lamport 的"事件顺序"论文（依赖关系定义了"先于"关系，波次就是一种偏序的分层）；代码本身没有用到时钟。
- 与讲义六字段的对照：

| 讲义字段 | 代码 | 说明 |
|---------|------|------|
| Goal | 无 | 示例中只能从 `id` 猜测目标 |
| Owner | `owner` | 示例中三个单元三个不同的 owner |
| Paths | `paths` | 独占写权限；可以是目录（`app/api`）或文件 |
| Dependencies | `depends_on` | 必须先完成的单元 |
| Proof | `proof` | 交给集成者的命令 |
| Handoff | 无 | 改了哪些文件、做了哪些决定、剩余风险——需在运行时由 worker 交回 |

- `frozen=True` + 元组字段：契约一旦下发就不可在运行中被悄悄修改。

### 3.2 `paths_overlap`：基于路径组件的父子判断

```python
def paths_overlap(left: str, right: str) -> bool:
    a = PurePosixPath(left)
    b = PurePosixPath(right)
    return a == b or a in b.parents or b in a.parents
```

- `PurePosixPath` 是"纯路径"：只做字符串层面的路径运算，不访问文件系统，所以文件不存在也能比较；`Posix` 保证无论在什么操作系统上都用 `/` 作分隔符。
- `b.parents` 是 `b` 的祖先序列：`PurePosixPath("app/api/routes.py").parents` 依次为 `app/api`、`app`、`.`。`a in b.parents` 即"a 是 b 的祖先"。
- 按**组件**比较，所以 `app/api` 与 `app/api_v2` 不重叠（测试 `test_sibling_paths_do_not_overlap` 覆盖了兄弟目录的情况）；若用字符串 `startswith` 就会误判。
- 构造时会做的规范化：去掉尾部 `/`、多余的 `//` 和单独的 `.`。实测 `("app/api/", "app/api")`、`("./app/api", "app/api")` 都是 `True`。
- ⚠️ 不做的规范化（实测）：

| 输入 | 结果 | 隐患 |
|------|------|------|
| `"app/../app/api"` vs `"app/api"` | `False` | `..` 不折叠，可绕过检查 |
| `"app/**"` vs `"app/api/routes.py"` | `False` | glob 被当作名为 `**` 的目录 |
| `"."` vs `"docs/api.md"` | `True` | `.`（以及空字符串 `""`）是一切路径的祖先，等于"拥有整个仓库" |
| `"App/api"` vs `"app/api"` | `False` | 大小写不敏感的文件系统上是同一目录 |

  修正思路：先用 `posixpath.normpath` 折叠 `..`，拒绝 glob、空路径、`.` 和越出仓库的路径（测验 Q10）。

### 3.3 `conflicts`：两两比较

```python
def conflicts(units: list[WorkUnit]) -> list[str]:
    found: list[str] = []
    for index, left in enumerate(units):
        for right in units[index + 1:]:
            for left_path in left.paths:
                for right_path in right.paths:
                    if paths_overlap(left_path, right_path):
                        found.append(f"{left.id} and {right.id} overlap at {left_path} / {right_path}")
    return found
```

- `enumerate` + `units[index + 1:]`：只比较每一对无序组合一次（i < j），避免 `a-b` 和 `b-a` 重复报告，也不和自己比较。
- 四重循环：单元对 × 左路径 × 右路径。复杂度 O(单元数² × 路径数²)，对一次委派的规模（几个到十几个单元）完全没问题。
- 冲突消息同时给出两条具体路径，便于定位：讲义的例子会输出 `api and docs overlap at app/api / app/`。
- 冲突检查**与依赖关系无关**：即使 `b` 依赖 `a`（二者串行），只要路径重叠也会被判为冲突。实测 `a` 拥有 `app`、`b` 拥有 `app/x.py` 且依赖 `a` → `blocked`。这是一个偏严格的设计：它保证"每个路径只有一个负责人"，但也意味着集成单元不能修改上游单元的文件——这与讲义"集成者不重做工作、只读审查"的理念一致。
- 同一个单元内部的路径重叠（例如 `("app", "app/api")`）不检查，也无害。

### 3.4 `waves`：分层拓扑排序

```python
def waves(units: list[WorkUnit]) -> list[list[str]]:
    remaining = {unit.id: set(unit.depends_on) for unit in units}
    known = set(remaining)
    if any(not deps <= known for deps in remaining.values()):
        raise ValueError("unknown dependency")
    done: set[str] = set()
    result: list[list[str]] = []
    while remaining:
        ready = sorted(key for key, deps in remaining.items() if deps <= done)
        if not ready:
            raise ValueError("dependency cycle")
        result.append(ready)
        done.update(ready)
        for key in ready:
            del remaining[key]
    return result
```

- 与第 44 节 `execution_waves` 是同一算法：每轮取出所有依赖都已完成的单元作为一波。
- 示例：第 1 轮 `api`、`docs` 都无依赖 → `['api', 'docs']`；第 2 轮 `integration` 的依赖都已完成 → `['integration']`。
- `known = set(remaining)`：对字典调用 `set()` 得到键的集合。
- `any(not deps <= known ...)`：只要有一个单元的依赖不是已知 ID 的子集，就存在未知依赖。
- ⚠️ 错误消息不带细节：`"unknown dependency"`、`"dependency cycle"` 都不说是哪个单元，比第 44 节的消息退步了。
- ⚠️ 与第 44 节相同，字典推导式会让重复 ID 静默覆盖；本节由 `delegation_plan` 在有重复 ID 时跳过 `waves` 来规避。

### 3.5 `delegation_plan`：汇总，但不够防御

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

- 重复 ID：集合推导式 `{... if ids.count(unit_id) > 1}` 去重，再排序。`ids.count` 每次都扫描整个列表，是 O(n²)，规模小时无所谓；用 `collections.Counter` 更标准。
- 三类问题（重复 ID、路径冲突、缺 proof）任一存在即 `blocked`。
- ⚠️ **崩溃**：未知依赖或环时 `waves()` 抛出的 `ValueError` 没有被捕获。实测 `delegation_plan([WorkUnit("a","o",("x",),("zz",),"t")])` → `ValueError: unknown dependency`；`a↔b` → `ValueError: dependency cycle`。调用方拿不到一份 blocked 文档。
- ⚠️ **blocked 仍输出调度**：只有重复 ID 会让 `waves` 置空。路径冲突时实测 `waves` 仍为 `[['api', 'docs'], ['integration']]`；缺 proof 时 `waves: [['a']]`。对比第 44 节 `plan_document` "有问题就不输出波次"的做法，这里的不一致可能让下游按一个不安全的计划派发工作（修正见测验 Q9）。
- 不检查：同一 owner 是否被分配到同一波的多个单元；proof 是否可执行；路径是否真实存在。

### 3.6 `example()` 与 `main()`

```python
def example() -> list[WorkUnit]:
    return [
        WorkUnit("api", "worker-api", ("app/api", "tests/test_api.py"), (), "python3 -m unittest tests.test_api"),
        WorkUnit("docs", "worker-docs", ("docs/api.md",), (), "python3 scripts/check_links.py"),
        WorkUnit("integration", "reviewer", ("tests/test_integration.py",), ("api", "docs"), "python3 -m unittest"),
    ]
```

- 对应讲义的 mermaid 图：API 单元与 Docs 单元并行，各自交回 proof 和 handoff，再由集成审查和完整 gate 收尾。
- `api` 拥有整个 `app/api` 目录加一个测试文件；`docs` 只拥有一个文件——目录级所有权更宽松，但冲突面更大。
- 讲义图中写的是 "Read-only integration review"，但示例的 `integration` 单元拥有 `tests/test_integration.py` 的写权限，owner 又叫 `reviewer`。如果集成需要新增集成测试，应把它作为一个独立的工作单元，让 reviewer 保持只读（第 39 节：实现者与评分者分离）。
- 与第 44 节的关系：第 44 节的计划里 `docs` 和 `implementation` 都依赖 `contract`；这里的 `api` 和 `docs` 没有依赖——隐含前提是**契约已经在委派之前定好**（讲义："The merge contract must resolve shared interfaces before work begins"）。否则 api 与 docs 就是"看起来独立"的拆分。
- `docs` 的 proof 是链接检查，证明不了文档内容与 API 一致。

```python
def main() -> None:
    output = Path(__file__).resolve().parents[1] / "outputs" / "delegation-plan.json"
    output.write_text(json.dumps(delegation_plan(example()), indent=2) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))
```

- 写到 `<本节>/outputs/delegation-plan.json`；直接在仓库中运行会覆盖已提交文件（实测内容相同）。
- 代码不读取第 44 节的 `evidence-plan.json`；讲义说那份计划"会成为下一节的委派契约"，两者的衔接需要自己完成。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 `PurePosixPath` 判断父子关系 | 按路径组件比较，不误判 `app/api_v2`；不依赖文件存在 | 不折叠 `..`、不识别 glob、`.` 吞掉一切；生产中先 `normpath` 并拒绝危险路径 |
| 冲突检查忽略依赖关系 | 保证每个路径只有一个负责人 | 串行单元也不能共享文件；需要时应显式"转移所有权" |
| 两两比较的四重循环 | 实现直接、输出带具体路径 | O(n²·m²)，规模大时可先按路径前缀分桶 |
| `waves` 抛异常表示不可调度 | 简单 | `delegation_plan` 未捕获，导致崩溃；消息不带单元名 |
| 只有重复 ID 才清空波次 | 防止字典覆盖导致的错误调度 | 冲突、缺 proof 时仍输出波次，与 `status` 矛盾 |
| `WorkUnit` 只有五个字段 | 聚焦可机械检查的部分 | 缺 Goal 与 Handoff；运行时还需要 worker 交回改动清单与决定 |
| 只做所有权隔离 | 规划期能做的检查 | 文件系统隔离（worktree）与状态隔离（分目录输出）要由运行时实现 |
| JSON 产物 | 机器可读，记录"为什么拆分是安全的" | 不包含拆分理由（并行性测试的哪一条成立），可加 `justification` 字段 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class WorkUnit` | 不可变数据类 |
| 变长元组注解 | `paths: tuple[str, ...]` | 任意长度的字符串元组 |
| `PurePosixPath` | `PurePosixPath(left)` | 纯路径运算，不访问磁盘，固定用 `/` |
| `.parents` 与 `in` | `a in b.parents` | 判断 a 是否为 b 的祖先目录 |
| 路径相等 | `a == b` | 规范化后的路径比较 |
| `enumerate` + 切片 | `for index, left in enumerate(units): ... units[index + 1:]` | 遍历所有无序对 |
| 多重嵌套循环 | 四层 `for` | 单元对 × 路径对 |
| 集合推导式 | `{unit_id for unit_id in ids if ids.count(unit_id) > 1}` | 找重复项并去重 |
| `list.count` | `ids.count(unit_id)` | 统计出现次数（O(n)） |
| 字典推导式 | `{unit.id: set(unit.depends_on) for unit in units}` | ID → 依赖集合 |
| `set(dict)` | `known = set(remaining)` | 取字典的键集合 |
| `any(生成器)` | `any(not deps <= known for deps in remaining.values())` | 只要有一个满足即为真 |
| 子集运算 | `deps <= done` | 依赖都已完成 |
| `while` + `del` | `del remaining[key]` | 逐轮删除已调度的项 |
| `raise ValueError(...)` | `raise ValueError("dependency cycle")` | 无法调度时抛异常 |
| 条件表达式 | `waves(units) if not duplicate_ids else []` | 二选一 |
| `asdict` + `json.dumps` | `[asdict(unit) for unit in units]` | 元组被写成 JSON 数组 |
| `Path.resolve().parents[1]` | `main()` | 本节目录 |

测试文件额外用到：`importlib.util.spec_from_file_location` 按路径加载模块；`assertTrue` / `assertFalse` / `assertEqual`。

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时目录的本节副本中执行，退出码 0），输出与仓库中已提交的 `outputs/delegation-plan.json` 逐字一致：

```text
{
  "status": "ready",
  "duplicate_ids": [],
  "conflicts": [],
  "missing_proof": [],
  "waves": [
    ["api", "docs"],
    ["integration"]
  ],
  "units": [ ... 三个单元的完整字段 ... ]
}
```

（实际输出中数组元素各占一行，这里做了合并。）

- **ready**：三个单元 ID 唯一；`app/api`、`tests/test_api.py`、`docs/api.md`、`tests/test_integration.py` 两两不重叠；都有 proof。
- **两个波次**：`api` 与 `docs` 并行，`integration` 等二者完成后执行。
- 讲义 Build It 的实验（把 `docs` 的路径改为 `app/`）实测：`status: blocked`，`conflicts: ['api and docs overlap at app/api / app/']`，但 `waves` 仍为 `[['api', 'docs'], ['integration']]`。
- 其他实测边界情况：

| 输入 | 结果 |
|------|------|
| 依赖不存在的单元 `zz` | `ValueError: unknown dependency`（函数崩溃） |
| `a↔b` 互相依赖 | `ValueError: dependency cycle`（函数崩溃） |
| proof 为空白 | `blocked`，`missing_proof: ['a']`，但 `waves: [['a']]` |
| `a` 拥有 `app`，`b` 拥有 `app/x.py` 且依赖 `a` | `blocked`（串行也算冲突），`waves: [['a'], ['b']]` |

---

## 7. 动手改一改

1. **讲义练习 1、3**：把一个你自己的真实改动拆成两个独立单元和一个集成者；再加一个只读调研单元（`paths=()`，proof 为"产出事实表 `outputs/research/facts.json`"），思考 `paths` 为空是否应该被允许、它的输出目录是否需要状态隔离。
2. **修 `delegation_plan`**：捕获 `waves()` 的异常转成 `schedule_error`，并让任何 blocked 情况都输出 `waves: []`（参考测验 Q9）。
3. **严格路径**：实现 `normalize`（`posixpath.normpath` + 拒绝 glob/空路径/`.`/越界），让 `app/../app/api` 被识别为与 `app/api` 重叠（参考测验 Q10）。
4. **讲义练习 4**：实现 `merge_gate(units, changed_by_unit)`，用每个 worktree 的 `git diff --name-only` 结果核对契约（参考测验 Q11）。
5. **讲义练习 5**：实现 `cancel_dependents(units, failed)`，并为"取消"写出完整规则：何为失效、运行中的下游怎么处理、日志如何保留、谁决定重启（参考测验 Q12）。
6. **补齐契约字段**：给 `WorkUnit` 加 `goal` 和 `justification`（满足并行性测试的哪一条），并要求 worker 交回 `handoff`（changed_files、decisions、risks）；在 `delegation_plan` 中检查同一波次的单元 owner 互不相同。

---

## 8. 常见坑

- **因为 agent 多就拆**：讲义第一条原则就是反对这个；并行只在真正独立时省时间。
- **只看文件不看决定**：路径不重叠不代表独立，两个单元仍可能共享一个未定的接口决定（"看起来独立"的拆分）。
- **用字符串前缀判断路径重叠**：`"app/api_v2".startswith("app/api")` 为真，会误报。
- **以为 `PurePosixPath` 会处理 `..`**：它不会；需要 `posixpath.normpath`。
- **把 `.` 或空字符串写进 paths**：等于宣称拥有整个仓库，会和所有单元冲突。
- **只看 `waves` 不看 `status`**：本节实现中 blocked 计划也可能带着波次。
- **不捕获 `delegation_plan` 的异常**：依赖写错一个字母，整个规划脚本就崩溃。
- **集成者"顺手修一下"worker 的代码**：这会让 proof 失效，也掩盖了拆分错误；应记录为新决定并退回。
- **直接在仓库中运行**：会覆盖已提交的 `outputs/delegation-plan.json`。

---

## 9. 测试在验证什么

测试文件 `code/tests/test_main.py` 用 `importlib` 按路径加载 `main.py`（模块名 `lesson45`）。

| 测试 | 构造 | 断言 | 验证的性质 |
|------|------|------|-----------|
| `test_example_is_safe` | `delegation_plan(example())` | `status == "ready"` | 示例拆分是安全的（正例基线） |
| `test_parent_and_child_paths_overlap` | `("app/api", "app/api/routes.py")` | `True` | 父目录与其中的文件重叠 |
| `test_sibling_paths_do_not_overlap` | `("app/api", "app/models")` | `False` | 兄弟目录不重叠 |
| `test_conflicting_ownership_blocks_plan` | `a` 拥有 `app`，`b` 拥有 `app/api.py` | `status == "blocked"` | 所有权冲突阻止计划 |
| `test_dependencies_create_merge_wave` | `waves(example())` | `[['api', 'docs'], ['integration']]` | 依赖产生集成波次 |
| `test_duplicate_work_unit_ids_block_the_plan` | 两个 `api` 单元 | `blocked`，`duplicate_ids == ['api']`，`waves == []` | 重复 ID 阻止计划且不输出调度 |

运行方式（在本节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：

```text
test_conflicting_ownership_blocks_plan (test_main.DelegationTests.test_conflicting_ownership_blocks_plan) ... ok
test_dependencies_create_merge_wave (test_main.DelegationTests.test_dependencies_create_merge_wave) ... ok
test_duplicate_work_unit_ids_block_the_plan (test_main.DelegationTests.test_duplicate_work_unit_ids_block_the_plan) ... ok
test_example_is_safe (test_main.DelegationTests.test_example_is_safe) ... ok
test_parent_and_child_paths_overlap (test_main.DelegationTests.test_parent_and_child_paths_overlap) ... ok
test_sibling_paths_do_not_overlap (test_main.DelegationTests.test_sibling_paths_do_not_overlap) ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.001s

OK
```

测试没有覆盖的地方：

- **未知依赖与环**：没有任何测试调用 `delegation_plan` 处理这两种输入，所以"函数会崩溃"没有被发现；
- **blocked 时的 waves**：只有重复 ID 一种情况断言了 `waves == []`，冲突和缺 proof 两种情况没有断言；
- **缺 proof**：`missing_proof` 字段没有任何测试；
- **路径规范化边界**：`..`、glob、`.`、大小写都没有测试；
- **前缀误判**：`test_sibling_paths_do_not_overlap` 用的是 `app/api` 与 `app/models`，没有覆盖更有迷惑性的 `app/api` 与 `app/api_v2`（实测也是 `False`，可以补上以锁定行为）。
