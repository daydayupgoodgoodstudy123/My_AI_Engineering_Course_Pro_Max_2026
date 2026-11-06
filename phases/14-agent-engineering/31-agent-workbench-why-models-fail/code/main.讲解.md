# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 31 节 Agent 工作台工程：能力强的模型为什么仍会失败 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节根目录执行；在 `code/` 下执行 `python3 main.py` 效果相同） ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`），无需 API key、无需网络
>
> **副作用**：每次运行都会写（覆盖）`outputs/failure_modes.json`。

---

## 1. 这份代码在考察什么

这是工作台（workbench）迷你系列的第一节，代码刻意做得很小：用一个**规则桩（stub）**代替真实 LLM，把同一个仓库任务（"给 `/signup` 加输入校验并写一个通过的测试"）跑两次：

1. **prompt-only**：七个 surface 一个都没有；
2. **workbench**：七个 surface 全部接上。

然后对比两次运行的"症状"：是否越界写文件、是否真的跑过测试、是否宣称成功、是否真的通过。它对应讲义的几个核心概念：

- **七个 surface**：`WORKBENCH_SURFACES` 列表；
- **"缺哪个 surface → 出哪种症状"**：`stub_agent` 里的四个 `if` 分支；
- **失败模式报告**：`failure_report` + `outputs/failure_modes.json`；
- **能力与可靠性分离**：两次运行用的是**同一个** agent 函数，唯一的变量是 surfaces。

> 一句话：**模型不变，只改变包裹它的 surface，结果就从"假成功 + 越界写入"变成"真通过 + 范围内写入"。** 但也要看清：这是一个确定性的演示，结论是"写死"在分支里的，并不是测出来的。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `WORKBENCH_SURFACES` | 模块常量（list） | 七个 surface 的名称 | 七个工作台表面 |
| `RepoTask` | dataclass | 任务描述、允许/禁止文件、验收标准 | Scope 合约的雏形 |
| `RunResult` | dataclass | 一次运行的观测结果 + `missing_surfaces()` | 失败模式记录 |
| `stub_agent` | 函数 | 根据有哪些 surface 决定行为 | 被工作台包裹的 agent |
| `failure_report` | 函数 | 把 `RunResult` 转成可序列化的报告字典 | 失败模式报告 |
| `main` | 函数 | 构造任务、跑两次、打印、写 JSON | 实验驱动 |

数据流：`main` 构造 `RepoTask` → `stub_agent(task, [])` 与 `stub_agent(task, WORKBENCH_SURFACES)` → 两个 `RunResult` → `failure_report` → 打印 + 写 `outputs/failure_modes.json`（只写 prompt-only 那份）。

---

## 3. 逐段精讲

### 3.1 七个 surface 与两个数据类

```python
WORKBENCH_SURFACES = [
    "instructions", "state", "scope", "feedback",
    "verification", "review", "handoff",
]

@dataclass
class RepoTask:
    description: str
    allowed_files: list[str]
    forbidden_files: list[str]
    acceptance: list[str]
```

- 列表顺序与讲义表格一致。用字符串而不是枚举，便于直接写进 JSON。
- `RepoTask` 已经有了 Scope 合约的三要素：`allowed_files`、`forbidden_files`、`acceptance`（第 36 节会把它扩展成完整的 scope contract）。
- 注意：在本文件里，`forbidden_files`、`acceptance`、`description` **从未被读取**，只有 `allowed_files` 被 `stub_agent` 用到。

```python
@dataclass
class RunResult:
    label: str
    surfaces_present: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    tests_run: bool = False
    declared_success: bool = False
    actually_passing: bool = False
    notes: list[str] = field(default_factory=list)

    def missing_surfaces(self) -> list[str]:
        return [s for s in WORKBENCH_SURFACES if s not in self.surfaces_present]
```

- 关键在于 `declared_success` 与 `actually_passing` **分成两个字段**：讲义里"Agent 宣布成功但测试失败"的症状，就体现为二者不一致。
- `field(default_factory=list)`：可变默认值必须用工厂函数，否则所有实例会共享同一个列表（见第 5 节）。
- `missing_surfaces()` 用列表推导式求"全集 − 已有"，并保持 `WORKBENCH_SURFACES` 的顺序。

### 3.2 `stub_agent`：surface 决定行为

```python
    result = RunResult(label="prompt-only" if not surfaces else "workbench")
    result.surfaces_present = list(surfaces)

    has_scope = "scope" in surfaces
    has_state = "state" in surfaces
    has_verification = "verification" in surfaces
    has_feedback = "feedback" in surfaces
```

- `list(surfaces)` 做一份拷贝，避免 `result` 和调用方共享同一个列表对象（workbench 那轮传入的是全局常量 `WORKBENCH_SURFACES`）。
- 只取了 4 个布尔开关：**instructions、review、handoff 三个 surface 在代码中没有任何行为差异**。
- `label` 规则很粗：只要传了任何 surface，就叫 "workbench"。

接下来四个分支，每个分支对应讲义表格里的一行"Failure when missing"：

| 分支 | 有该 surface 时 | 缺该 surface 时（写入 notes） | 讲义中的症状 |
|------|----------------|------------------------------|-------------|
| Scope | 只写 `allowed_files` | 额外写 `README.md`、`scripts/release.sh` | Edits leak into unrelated code |
| Feedback | `tests_run=True` | "never ran the test command, guessed at output" | Agent declares success on a 400 |
| Verification | `actually_passing=True` | `actually_passing=False` 但仍 `declared_success=True` | "Looks good" reaches main |
| State | （无 note） | "no state file written, next session restarts from zero" | Each session restarts from zero |

```python
    if has_verification:
        result.actually_passing = True
        result.declared_success = True
        result.notes.append("verification gate proved acceptance criteria met")
    else:
        result.declared_success = True
        result.actually_passing = False
        result.notes.append("declared success without running acceptance checks")
```

- `declared_success` 在两个分支里都是 `True`：agent **总是**宣称成功。区别只在于有没有 gate 去证实。这其实已经实现了讲义练习 2 所说的"fake success claim"。
- ⚠️ `actually_passing` 只看 `has_verification`，不看 `tests_run`。实测 `surfaces=["verification"]` 时得到 `tests_run=False, actually_passing=True`——没跑测试却"证明"通过。真实的 verification gate 必须以 Feedback 捕获的命令输出为输入，并且 fail closed（讲义："Verification — a function. Deterministic over inputs ... Fails closed."）。

### 3.3 `failure_report`：结构化的失败报告

```python
def failure_report(result: RunResult) -> dict[str, object]:
    return {
        "label": result.label,
        "missing_surfaces": result.missing_surfaces(),
        "off_scope_writes": [
            f for f in result.files_touched if f not in {"app.py", "test_app.py"}
        ],
        "tests_run": result.tests_run,
        "declared_success": result.declared_success,
        "actually_passing": result.actually_passing,
        "notes": result.notes,
    }
```

- 返回普通 `dict`，可以直接 `json.dumps`——这是"机器可读 surface"的最小形态（讲义 Key Terms："A named, machine-readable input the agent reads or writes every turn"）。
- `off_scope_writes` 相当于 Verification 中的 **scope check**，是在事后对"实际写了哪些文件"做比对。
- ⚠️ 白名单写死为 `{"app.py", "test_app.py"}`，没有使用 `task.allowed_files`（函数签名里根本没有 `task`）。实测把任务允许文件扩为 `["app.py", "test_app.py", "validators.py"]` 后，workbench 那轮会误报 `off_scope_writes: ['validators.py']`。
- ⚠️ mission 的验收标准要求"lists each missing surface with matching symptom"，但报告里 `missing_surfaces` 与 `notes` 是两个独立列表，没有一一对应；7 个缺失 surface 只对应 4 条 note。

### 3.4 `main`：跑两次、打印、落盘

```python
    prompt_only = stub_agent(task, surfaces=[])
    workbench = stub_agent(task, surfaces=WORKBENCH_SURFACES)
    ...
    out = Path(__file__).parent.parent / "outputs" / "failure_modes.json"
    out.write_text(json.dumps(failure_report(prompt_only), indent=2) + "\n")
    print(f"\nwrote {out.relative_to(out.parent.parent.parent.parent.parent)}")
```

- **同一个函数、同一个任务**，唯一变量是 `surfaces`——这就是讲义"Same model, same task"的对照实验设计。
- `Path(__file__).parent.parent`：`code/main.py` 的上两级是小节根目录，因此无论从哪个工作目录运行，输出都落在本小节的 `outputs/` 下（Python 3.9+ 中主脚本的 `__file__` 是绝对路径）。
- `out.relative_to(...)` 往上数 5 级（`failure_modes.json` → `outputs` → 小节 → `14-agent-engineering` → `phases` → 仓库根），只是为了打印一个从仓库根开始的相对路径。层级是硬编码的，挪动目录结构后打印内容就会变。
- 只把 prompt-only 的报告写进 JSON；workbench 的结果只打印。讲义说的"one-line verdict for the workbench run"在代码里并不存在，打印的是完整报告。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用规则桩代替 LLM | 结果确定、无需 API key，突出"surface 才是变量" | 结论被分支写死，演示的是"假设"而不是"测量"；真实评估要在 LLM agent 上多次采样（见第 30 节评估驱动开发） |
| 两次运行只改 surfaces | 构成干净的对照实验 | 只比较了"全无"与"全有"，看不出单个 surface 的边际贡献；可做 7 组消融（每次去掉一个） |
| `declared_success` 与 `actually_passing` 分开 | 让"假成功"可观测 | 生产中 `actually_passing` 必须来自真实测试输出，而不是一个布尔开关 |
| 报告输出为 JSON | 机器可读，可被下一个工具或会话读取 | 缺少 surface → 症状的映射、缺少证据（命令、退出码）字段 |
| scope check 放在报告阶段 | 实现简单 | 只能事后发现越界；生产中 Scope 应在写入前强制执行（ACL），verification 再兜底 |
| 白名单写死 | 代码短 | 与 `RepoTask` 脱节，换任务就误报；应从 `task.allowed_files` / `forbidden_files` 计算 |
| instructions/review/handoff 不建模 | 本节只做概念引入，后续 11 节逐个展开 | 学生可能误以为这三个 surface 不影响结果；可以在 notes 中至少输出它们的缺失症状 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值（存成字符串），可以在注解里提前引用尚未定义的类，也减少运行时开销 |
| `@dataclass` | `class RepoTask:` | 自动生成 `__init__`、`__repr__`、`__eq__`，适合"只装数据"的类 |
| `field(default_factory=list)` | `notes: list[str] = field(default_factory=list)` | 可变默认值必须用工厂函数；直接写 `= []` 时 dataclass 会报 `ValueError` |
| 内置泛型注解 | `list[str]`、`dict[str, object]` | Python 3.9+ 可直接用内置类型做泛型注解 |
| 返回类型注解 | `def missing_surfaces(self) -> list[str]:` | 只是提示，运行时不检查 |
| 条件表达式 | `"prompt-only" if not surfaces else "workbench"` | 一行 if/else；空列表为假值 |
| 成员测试 | `"scope" in surfaces`、`f not in {"app.py", ...}` | 列表是 O(n) 查找，集合是 O(1) |
| 列表推导式（带条件） | `[s for s in WORKBENCH_SURFACES if s not in self.surfaces_present]` | 过滤出缺失项并保持顺序 |
| 解包到列表字面量 | `[*task.allowed_files, "README.md", "scripts/release.sh"]` | `*` 把一个可迭代对象展开进新列表 |
| `list(...)` 拷贝 | `list(surfaces)` | 浅拷贝，避免共享可变对象 |
| 关键字参数调用 | `stub_agent(task, surfaces=[])` | 调用处更易读 |
| `dict.items()` 遍历 | `for k, v in failure_report(...).items():` | 同时拿到键和值 |
| `pathlib.Path` | `Path(__file__).parent.parent / "outputs" / "failure_modes.json"` | `/` 运算符拼接路径；`.parent` 取上一级；`.write_text` 写文件；`.relative_to` 求相对路径 |
| `json.dumps(..., indent=2)` | 写 `failure_modes.json` | 序列化为带缩进的 JSON 字符串 |
| f-string | `f"  {k}: {v}"`、`f"\nwrote {out...}"` | 字符串插值；`{v}` 对列表会调用 `str()`，因此打印出 `['README.md', ...]` |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行（测验中我们就是 import 后调用 `stub_agent` 做实验） |

---

## 6. 运行结果解读

实际运行（Python 3.13，退出码 0；为避免改动仓库，在临时目录的同结构副本中运行）：

```text
=== prompt only ===
  label: prompt-only
  missing_surfaces: ['instructions', 'state', 'scope', 'feedback', 'verification', 'review', 'handoff']
  off_scope_writes: ['README.md', 'scripts/release.sh']
  tests_run: False
  declared_success: True
  actually_passing: False
  notes: ['touched unrelated files because scope was missing', 'never ran the test command, guessed at output', 'declared success without running acceptance checks', 'no state file written, next session restarts from zero']

=== workbench ===
  label: workbench
  missing_surfaces: []
  off_scope_writes: []
  tests_run: True
  declared_success: True
  actually_passing: True
  notes: ['captured stdout/stderr/exit code from the test run', 'verification gate proved acceptance criteria met']

wrote phases/14-agent-engineering/31-agent-workbench-why-models-fail/outputs/failure_modes.json
```

逐项解读：

- **prompt-only**：`declared_success=True` 而 `actually_passing=False`——这就是讲义开场"宣布成功、两个测试失败"的缩影；`off_scope_writes` 对应"第三个文件被改动"；`tests_run=False` 对应"没跑命令就猜结果"。
- **notes 只有 4 条**：分别来自 scope、feedback、verification、state 四个分支。instructions、review、handoff 虽然缺失，却没有症状输出。
- **workbench**：两条 notes 都是"正面证据"，`declared_success` 与 `actually_passing` 一致。
- **failure_modes.json**：内容就是 prompt-only 那份报告的 JSON 版本（7 个缺失 surface、2 个越界文件、4 条 notes）。
- **额外实验**（import 后调用，帮助理解分支逻辑）：

| 传入的 surfaces | off_scope_writes | tests_run | actually_passing |
|----------------|------------------|-----------|------------------|
| `["verification"]` | 2 个 | False | **True**（漏洞） |
| `["feedback"]` | 2 个 | True | False |
| `["scope"]` | [] | False | False |
| `["state","scope","feedback"]` | [] | True | False |
| `["instructions","review","handoff"]` | 2 个 | False | False（与全空时完全相同） |

---

## 7. 动手改一改

1. **把症状和 surface 对上**：加一个 `SYMPTOMS` 字典（取讲义表格第三列），在 `failure_report` 里输出 `{"symptoms": {surface: symptom}}`，满足 mission 的验收标准（参考测验 Q10）。
2. **修 verification 漏洞**：让 `actually_passing` 依赖 `has_verification and result.tests_run`；没有 feedback 时 verification 应 fail closed，并在 notes 里写明原因。
3. **去掉硬编码白名单**：把 `failure_report` 改成 `failure_report(result, task)`，用 `task.allowed_files` 计算越界，再用 `task.forbidden_files` 单独列出 `forbidden_writes`。
4. **消融实验**：循环 7 次，每次只去掉一个 surface，打印一张"去掉谁 → 哪些字段变坏"的表格。你会发现目前只有 4 个 surface 有影响——为 instructions、review、handoff 各设计一个可观测的行为差异（例如：没有 review 时 `self_approved=True`；没有 handoff 时 `handoff_written=False`）。
5. **讲义练习 4**：写一个会幻觉额外写入 `app_backup.py` 的 agent，比较"写入前 ACL 拦截"和"事后 scope check"两种实现，各自在报告里留下什么证据（参考测验 Q11）。
6. **进阶**：把桩换成一个真实的小任务——在临时目录里放 `app.py` 和 `test_app.py`，让 Feedback 用 `subprocess.run(["python3", "-m", "pytest", "-q"])` 捕获真实的退出码，再让 Verification 基于它判定通过与否。

---

## 8. 常见坑

- **把演示结论当实验结论**：本代码的"workbench 必然成功"是分支写死的，不能作为工作台有效性的证据；讲义中的证据来自外部报告（Terminal Bench、Vercel、Harvey 等）。
- **verification 不依赖真实输出**：只要开关打开就判通过，等于另一种形式的"builder marks own homework"。
- **白名单与任务脱节**：硬编码的 scope check 换个任务就误报或漏报。
- **可变默认参数**：在 dataclass 里写 `notes: list[str] = []` 会直接报错；在普通函数里写 `def f(x=[])` 则会在多次调用间共享同一个列表。
- **运行有副作用**：每次运行都会覆盖 `outputs/failure_modes.json`；在只读环境或 CI 里运行时要注意。
- **中文讲义误读**：中文讲义为机器翻译，例如"Agent 宣布400号战车成功"原文是"Agent declares success on a 400"（HTTP 400 错误），读不通时请对照英文。
