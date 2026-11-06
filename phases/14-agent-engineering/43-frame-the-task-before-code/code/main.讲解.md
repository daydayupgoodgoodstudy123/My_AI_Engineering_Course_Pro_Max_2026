# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 43 节 在 Agent 编写代码前界定任务 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在本节目录下 `python3 code/main.py`；测试 `python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`dataclasses`、`pathlib`；测试用 `unittest`、`importlib.util`）

---

## 1. 这份代码在考察什么

讲义的主张是："coding agent 的第一个工作单元不是编辑，而是有仓库证据支撑的 task frame。"这份不到 90 行的代码把这个主张变成一个可运行的小工具：

1. **把 task frame 建模成数据**：`TaskFrame` 的字段对应讲义的六个字段（Goal、Repository facts、Allowed paths、Forbidden paths、Acceptance evidence、Unknowns）。
2. **"事实要有收据"**：`RepositoryFact` 把主张（claim）与证据（evidence）绑在一起，证据为空即视为"不受支持的事实"。
3. **验证器给出拒绝原因**：`validate()` 返回问题列表而不是一个布尔值，每种破坏方式对应一条不同的原因。
4. **渲染成一屏可读的文档**：`render()` 输出 Markdown，状态为 `READY` 或 `BLOCKED`，阻塞原因写在文档末尾。

它同时也是一个"最小实现"：只做结构完整性检查，讲义中更细的要求（unknown 分类、glob 路径、证据格式、拒绝 "tests pass"）都没有落到代码里，这些差距正好是练习的切入点。

> 一句话：**把"开工前想清楚"变成一个会说"不"的数据结构**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `RepositoryFact` | 不可变 dataclass | `claim` + `evidence` | 事实要有收据 |
| `TaskFrame` | dataclass | 六个字段的容器 | Task frame |
| `validate(frame)` | 函数 | 返回问题列表；空列表表示可开工 | 有界、有证据、有验收 |
| `render(frame)` | 函数 | 生成 Markdown，含状态与阻塞原因 | 一屏可读的 frame |
| `example()` | 函数 | 讲义中的"防止重复邮件"示例 | 示例 frame |
| `main()` | 函数 | 渲染示例并写入 `outputs/task-frame.md` | 产物供下一节使用 |
| `tests/test_main.py` | 测试 | 5 个 `unittest` 用例 | 见第 9 节 |

数据流：`example()` 构造 `TaskFrame` → `render()` 内部调用 `validate()` 决定 `READY/BLOCKED` → 拼接 Markdown → `main()` 写入 `outputs/task-frame.md` 并打印。

---

## 3. 逐段精讲

### 3.1 文件头与两个数据类

```python
@dataclass(frozen=True)
class RepositoryFact:
    claim: str
    evidence: str


@dataclass
class TaskFrame:
    goal: str
    allowed_paths: list[str]
    forbidden_paths: list[str]
    acceptance: list[str]
    facts: list[RepositoryFact] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
```

- 文件头注释列出了讲义路径和两篇 canonical source（Nuseibeh & Easterbrook 的需求工程路线图、SWE-agent 论文），说明这段代码对应的理论来源。
- `RepositoryFact` 用 `frozen=True`：事实一旦记录就不应被悄悄改写；要改就换一个新对象。frozen 实例不能给属性赋值，并且可以哈希。
- `TaskFrame` 不是 frozen 的：frame 在侦察过程中会不断补充，测试里也直接修改它的字段（`frame.goal = " "`）。
- 字段与讲义六字段的对应：

| 讲义字段 | 代码字段 | 是否必填 |
|---------|---------|---------|
| Goal | `goal: str` | 必填（非空白） |
| Repository facts | `facts: list[RepositoryFact]` | 可为空 |
| Allowed paths | `allowed_paths: list[str]` | 必填（非空） |
| Forbidden paths | `forbidden_paths: list[str]` | 必填（非空） |
| Acceptance evidence | `acceptance: list[str]` | 必填（非空） |
| Unknowns | `unknowns: list[str]` | 可为空，且不影响状态 |

- 有默认值的字段（`facts`、`unknowns`）放在最后，这是 dataclass 的要求；列表默认值必须用 `field(default_factory=list)`。

### 3.2 `validate()`：返回原因而不是布尔值

```python
def validate(frame: TaskFrame) -> list[str]:
    issues: list[str] = []
    if not frame.goal.strip():
        issues.append("goal is empty")
    if not frame.allowed_paths:
        issues.append("allowed paths are empty")
    if not frame.forbidden_paths:
        issues.append("forbidden paths are empty")
    if not frame.acceptance:
        issues.append("acceptance evidence is empty")
    for fact in frame.facts:
        if not fact.evidence.strip():
            issues.append(f"unsupported fact: {fact.claim}")
    overlap = sorted(set(frame.allowed_paths) & set(frame.forbidden_paths))
    if overlap:
        issues.append(f"paths are both allowed and forbidden: {', '.join(overlap)}")
    return issues
```

逐条检查与讲义的对应：

| 检查 | 对应讲义 | 说明 |
|------|---------|------|
| `goal.strip()` 非空 | "What observable behavior must change?" | 只含空格也算空 |
| allowed 非空 | "Where may the change land?" | 没有允许路径就无处下手 |
| forbidden 非空 | "What must remain untouched?" | 要求显式写出"负空间"，哪怕只有一条 |
| acceptance 非空 | "Write the proof before the patch" | 没有证明计划就不能开工 |
| 每个 fact 的 evidence 非空 | "Facts need receipts" | 空收据 → `unsupported fact: <claim>` |
| allowed ∩ forbidden 为空 | 边界不能自相矛盾 | 用集合交集，`sorted` 保证输出顺序稳定 |

- 返回 `list[str]` 的好处：调用方既能用 `not issues` 判断是否可开工，又能把每条原因展示给人；讲义要求"四种破坏各自得到不同原因"，只有返回列表才能做到。
- ⚠️ 只检查"有没有"，不检查"对不对"：
  - `facts` 为空列表 → 不报错（讲义建议记录两三个事实）；
  - evidence 写 `"trust me"` → 不报错（任何非空字符串都算收据）；
  - acceptance 写 `"tests pass"` → 不报错（讲义原话："'Tests pass' is not a proof plan"）；
  - allowed 里有 `"  "` 这样的空白路径 → 不报错（列表非空即可）。
- ⚠️ 路径重叠只比较**字符串完全相等**：`migrations/0007_unique_email.py` 与 `migrations/**` 不会被判为冲突（实测返回 `[]`）。示例 frame 的 forbidden 恰好都是 glob 形式，这个检查对它们完全无效。
- ⚠️ `unknowns` 完全不参与验证：讲义要求 agent 在 human unknown 处暂停，但代码里 unknown 只是字符串，示例中带一个 unknown 的 frame 状态依然是 `READY`。

### 3.3 `render()`：一屏可读的 frame

```python
def render(frame: TaskFrame) -> str:
    issues = validate(frame)
    status = "READY" if not issues else "BLOCKED"
    lines = [f"# Task Frame: {frame.goal}", "", f"Status: {status}", "", "## Repository facts"]
    lines.extend(f"- {fact.claim} (`{fact.evidence}`)" for fact in frame.facts)
    lines.extend(["", "## Allowed paths"])
    lines.extend(f"- `{path}`" for path in frame.allowed_paths)
    ...
    if issues:
        lines.extend(["", "## Blocking issues"])
        lines.extend(f"- {item}" for item in issues)
    return "\n".join(lines) + "\n"
```

- `render` 内部再调用一次 `validate`，保证"状态"与"内容"永远一致，不可能出现文档写着 READY、实际却有问题的情况。
- `"READY" if not issues else "BLOCKED"` 是条件表达式。
- `lines.extend(生成器表达式)`：把每个事实/路径格式化成一行 Markdown 列表项追加进去；证据和路径用反引号包起来，渲染成代码样式，便于复制。
- 阻塞时不会拒绝渲染，而是在末尾追加 "Blocking issues" 小节——BLOCKED 的 frame 本身就是"为什么还不能开工"的说明书。
- 小瑕疵：goal 为空时标题变成 `# Task Frame: `；某个列表为空时只有小节标题、没有任何条目（例如 acceptance 为空时 "## Acceptance evidence" 下是空的），读者需要看末尾的阻塞原因才知道是缺失而不是漏印。

### 3.4 `example()` 与 `main()`

```python
def example() -> TaskFrame:
    return TaskFrame(
        goal="Prevent duplicate email addresses during signup",
        allowed_paths=["app/accounts.py", "tests/test_accounts.py"],
        forbidden_paths=["migrations/**", "deploy/**"],
        acceptance=["python3 -m unittest tests.test_accounts"],
        facts=[
            RepositoryFact("Account writes use AccountStore", "app/accounts.py:18"),
            RepositoryFact("Duplicate errors use status 409", "tests/test_accounts.py:44"),
        ],
        unknowns=["Whether email comparison is case-insensitive"],
    )
```

- 这是讲义开头那个"听起来具体其实不具体"的需求被 frame 之后的样子：goal 写成行为（"防止注册时出现重复邮件"），不是文件改动。
- 两条事实都是 `文件:行号` 形式的收据。注意本节并没有真正的 `app/accounts.py`，这些行号是示意。
- forbidden 用了 glob：`migrations/**` 表达了"本切片不允许做数据库迁移"——这直接排除了"用数据库唯一约束"的方案，是一个有分量的边界。
- acceptance 是一条完整命令，但没有写出"哪个测试证明了什么主张"；按讲义标准，更好的写法是点名具体测试方法并附一句它证明的主张。
- unknown "邮件比较是否大小写不敏感"是讲义 "Is comparison case-insensitive?" 的原样落地；它很可能是 human unknown（会改变产品行为），但当前代码不会因此暂停。
- **每次调用都返回新对象**：测试中 `frame.forbidden_paths.append(...)` 修改的只是这一次返回的列表，不会污染其他测试。

```python
def main() -> None:
    output = Path(__file__).resolve().parents[1] / "outputs" / "task-frame.md"
    output.write_text(render(example()), encoding="utf-8")
    print(output.read_text(encoding="utf-8"))
```

- `parents[1]`：`parents[0]` 是 `code/`，`parents[1]` 是本节目录，所以写到 `<本节>/outputs/task-frame.md`。
- 写完再读回来打印，确认磁盘上的内容就是渲染结果。
- 注意：直接运行会**覆盖**仓库里已提交的 `outputs/task-frame.md`（实测内容完全相同）；`outputs/task-frame.zh.md` 是单独的中文翻译，不由本脚本生成。
- `outputs/` 目录必须已存在，否则 `write_text` 抛 `FileNotFoundError`（脚本没有 `mkdir`）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 dataclass 表示 frame | 字段即文档，类型清晰，可直接构造与修改 | 可以进一步给 `TaskFrame` 加 `to_json()`，与第 36 节 scope contract 对接 |
| `RepositoryFact` frozen | 事实不应被悄悄修改 | 推翻事实时需要显式替换，也便于记录修订历史 |
| `validate` 返回原因列表 | 可解释、可测试、满足"不同破坏不同原因" | 原因是自由文本；生产中可用错误码（如 `frame.goal_empty`）便于程序处理 |
| 只做非空和字符串交集检查 | 简单、零依赖 | 挡不住 glob 冲突、假收据、"tests pass"、human unknown；见测验 Q10–Q12 |
| `render` 内部调用 `validate` | 状态与内容永远一致 | 每次渲染都重新验证（开销可忽略） |
| 输出 Markdown | 人类可读、一屏可见，可直接进 PR 描述 | 机器读取不方便；可同时输出 JSON 给下一节使用 |
| unknown 是字符串 | 降低使用门槛 | 无法区分 discoverable/decidable/human/deferred，也就无法让 human unknown 阻塞 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件顶部 | 注解延迟求值 |
| `@dataclass(frozen=True)` | `class RepositoryFact` | 生成 `__init__`、`__eq__`、`__hash__`，实例不可修改 |
| `@dataclass` + `field(default_factory=list)` | `facts: list[RepositoryFact] = field(default_factory=list)` | 可变默认值必须用工厂 |
| 内置泛型注解 | `list[str]`、`list[RepositoryFact]` | 3.9+ 写法 |
| `str.strip()` 判空 | `if not frame.goal.strip():` | 去掉首尾空白后为空串即为假 |
| 空列表为假 | `if not frame.allowed_paths:` | 空容器在布尔上下文中为 `False` |
| 集合交集 | `set(a) & set(b)` | 求两个集合共同元素 |
| `sorted` | `sorted(set(...))` | 集合无序，排序后输出稳定、便于测试 |
| `str.join` | `', '.join(overlap)`、`"\n".join(lines)` | 用分隔符拼接字符串 |
| f-string | `f"unsupported fact: {fact.claim}"`、``f"- {fact.claim} (`{fact.evidence}`)"`` | 嵌入表达式；反引号只是普通字符 |
| 条件表达式 | `"READY" if not issues else "BLOCKED"` | 一行内二选一 |
| `list.extend` + 生成器表达式 | `lines.extend(f"- `{path}`" for path in frame.allowed_paths)` | 惰性生成并逐个追加 |
| `Path.resolve().parents[1]` | `Path(__file__).resolve().parents[1]` | 绝对路径的第 2 层父目录 |
| `write_text(..., encoding="utf-8")` | `output.write_text(render(example()), encoding="utf-8")` | 显式指定编码，避免平台默认编码差异 |
| `if __name__ == "__main__":` | 文件末尾 | 被测试导入时不会执行 `main()` |

测试文件中的语法：

| 语法 | 例子 | 说明 |
|------|------|------|
| `importlib.util.spec_from_file_location` | `SPEC = importlib.util.spec_from_file_location("lesson43", MODULE_PATH)` | 按文件路径加载模块，不依赖 `sys.path` |
| `module_from_spec` + `exec_module` | `SPEC.loader.exec_module(module)` | 创建模块对象并执行其代码 |
| `sys.modules[SPEC.name] = module` | 注册模块 | 先注册再执行，dataclass 等需要通过模块名查找自身 |
| `unittest.TestCase` | `class TaskFrameTests(unittest.TestCase)` | 以 `test_` 开头的方法会被自动发现 |
| `assertEqual` / `assertIn` / `assertTrue` | `self.assertIn("goal is empty", ...)` | 各种断言 |
| `any(生成器)` | `any("both allowed and forbidden" in item for item in ...)` | 只要有一个元素满足即为真 |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时目录的本节副本中执行，退出码 0）：

```text
# Task Frame: Prevent duplicate email addresses during signup

Status: READY

## Repository facts
- Account writes use AccountStore (`app/accounts.py:18`)
- Duplicate errors use status 409 (`tests/test_accounts.py:44`)

## Allowed paths
- `app/accounts.py`
- `tests/test_accounts.py`

## Forbidden paths
- `migrations/**`
- `deploy/**`

## Acceptance evidence
- `python3 -m unittest tests.test_accounts`

## Unknowns
- Whether email comparison is case-insensitive
```

- 与仓库中已提交的 `outputs/task-frame.md` 逐字一致。
- **Status: READY**：goal、allowed、forbidden、acceptance 都非空，两条事实都有收据，路径字符串无交集，所以 `validate()` 返回 `[]`。
- 虽然有一条 unknown，状态仍是 READY——这是代码与讲义"human unknown 应暂停"之间的差距。
- 按讲义四种方式破坏后的实测结果：

| 破坏 | 输出 |
|------|------|
| goal 置空 | `['goal is empty']` |
| 去掉事实收据 | `['unsupported fact: Duplicate errors use status 409']` |
| 允许/禁止重叠 | `['paths are both allowed and forbidden: app/accounts.py']` |
| acceptance 置空 | `['acceptance evidence is empty']` |
| （额外）allowed 中加入 `migrations/0007_unique_email.py` | `[]`（glob 未被识别） |
| （额外）`facts=[]`、或 acceptance 写 `tests pass`、或 evidence 写 `trust me` | 均为 `[]` |

---

## 7. 动手改一改

1. **补测试**：为"acceptance 置空""forbidden 置空"各写一个测试，用 `assertEqual(validate(frame), [...])` 断言恰好只有一条原因（参考测验 Q9）。
2. **glob 冲突**：用 `fnmatch.fnmatchcase` 实现 `path_conflicts(allowed, forbidden)` 替换集合交集，验证 `migrations/0007_unique_email.py` 会被 `migrations/**` 拦下（参考测验 Q10）。
3. **unknown 分类**（讲义练习 3）：引入 `Unknown(question, kind)`，`kind` 取 discoverable/decidable/human/deferred；human 存在时状态为 `NEEDS_HUMAN`，并在 `render()` 中分组显示（参考测验 Q11）。
4. **证据与验收格式**（讲义练习 2、5）：要求 evidence 匹配 `路径:行号` 或 `$ 命令 -> 结果`；拒绝 "tests pass" 这类泛泛的验收；在 acceptance 中加一条 scope 收据，例如 `git diff --name-only` 只包含允许路径（参考测验 Q12）。
5. **验证收据真实存在**：给 `validate` 增加可选参数 `repo_root`，对 `路径:行号` 形式的证据检查文件是否存在、行号是否在范围内。
6. **用在真实仓库**（讲义练习 1）：为你自己仓库里的一个真实 bug 写一个 `TaskFrame`，不提出解决方案，只写事实、边界、验收和 unknowns，看它能否放进一屏。

---

## 8. 常见坑

- **把 READY 当作"可以放心开工"**：当前验证器只保证结构完整，不保证证据真实、unknown 已解决。
- **forbidden 写成 glob、allowed 写成具体文件**：字符串交集检测不到二者冲突，需要 glob 感知的检查。
- **事实写成主张**："应该返回 409"是需求，"`tests/test_accounts.py:44` 期望 409"才是事实。
- **验收只写 "tests pass" 或整个测试套件**：要点名证明目标的那个测试，以及它证明的主张。
- **把 unknown 当成失败而隐藏起来**：讲义："Unknowns Are Not Failures"；隐藏起来的 unknown 会变成埋在代码里的 assumption。
- **直接在仓库里运行 `main.py`**：会覆盖已提交的 `outputs/task-frame.md`；`outputs/` 不存在时会报错。
- **用 `assertIn` 测"不同原因"**：`assertIn` 不能证明"只有这一个原因"，多条原因同时出现时测试也会通过。

---

## 9. 测试在验证什么

测试文件 `code/tests/test_main.py` 用 `importlib` 按路径加载 `main.py`（模块名注册为 `lesson43`），因此不需要 `__init__.py`，也不依赖当前工作目录。

| 测试 | 构造 | 断言 | 验证的性质 |
|------|------|------|-----------|
| `test_example_is_ready` | 原样的 `example()` | `validate(...) == []` | 示例 frame 是完整的，可作为正例基线 |
| `test_empty_goal_blocks_work` | `frame.goal = " "` | 结果中含 `"goal is empty"` | 只有空白的 goal 也算空（`strip()` 生效） |
| `test_unsupported_fact_is_reported` | `facts = [RepositoryFact("A guess", "")]` | 含 `"unsupported fact: A guess"` | 没有收据的事实被点名报告 |
| `test_path_overlap_is_reported` | 把 `allowed_paths[0]` 加进 forbidden | 任一问题包含 `"both allowed and forbidden"` | 边界自相矛盾会被发现 |
| `test_render_includes_evidence_and_unknowns` | `render(example())` | 含 `Status: READY`、`app/accounts.py:18`、`case-insensitive` | 渲染结果包含状态、证据和 unknown |

运行方式（在本节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：

```text
test_empty_goal_blocks_work (test_main.TaskFrameTests.test_empty_goal_blocks_work) ... ok
test_example_is_ready (test_main.TaskFrameTests.test_example_is_ready) ... ok
test_path_overlap_is_reported (test_main.TaskFrameTests.test_path_overlap_is_reported) ... ok
test_render_includes_evidence_and_unknowns (test_main.TaskFrameTests.test_render_includes_evidence_and_unknowns) ... ok
test_unsupported_fact_is_reported (test_main.TaskFrameTests.test_unsupported_fact_is_reported) ... ok

----------------------------------------------------------------------
Ran 5 tests in 0.001s

OK
```

测试没有覆盖的地方：

- 讲义"四种破坏"中的**去掉 acceptance**没有测试；allowed/forbidden 为空也没有测试。
- 没有任何测试检查 BLOCKED 状态下 `render()` 的输出（"Blocking issues" 小节）。
- 没有反例测试来记录已知的局限（glob 重叠、空 facts、"tests pass"）。把这些写成"当前行为"的测试，修复时就会有明确的红灯转绿灯信号。
- 断言大多用 `assertIn`，不能证明"每种破坏只产生它自己那条原因"。
