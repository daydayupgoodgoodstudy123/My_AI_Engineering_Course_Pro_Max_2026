# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 08 节 角色专业化：规划者、Critic、执行者与验证者 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`），无需 LLM、API key 或网络

---

## 1. 这份代码在考察什么

这份 130 行左右的脚本用一个最小例子（实现 `add_two(a, b)`）演示四角色流水线：

1. **角色分工**：`planner` 产出结构化 `Spec`，`executor_*` 产出 `Artifact`（代码字符串），`critic` 做"LLM 式"的表面审阅，`verifier` 真正执行代码跑测试。
2. **结构化 I/O**：每个角色的输入输出都是 dataclass（`Spec`、`Artifact`、`CriticReport`、`VerifierReport`），对应讲义"Explicit I/O schema per role"。
3. **critic 与 verifier 的差异**：同一段"看起来没问题"的错误代码 `return a * b`，critic 放行、verifier 拦截。
4. **All-LLM 反模式的后果**：如果流水线里只有 critic，这个 bug 就会被交付。

> 一句话：**用"看起来对 vs 跑起来对"的对比，说明为什么至少需要一个由代码决定 pass/fail 的 verifier**。同时要看清：它的 critic 只是三条字符串匹配，`exec` 也不是真正的 sandbox，讲义 Ship It 里的修订循环和预算在代码中并没有实现。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Spec` | dataclass | 任务名、签名、描述、测试用例 `list[tuple[tuple, int]]` | planner 的输出 schema |
| `Artifact` | dataclass | 只有一个字段 `code: str` | executor 的输出 schema |
| `CriticReport` | dataclass | `approved` + `notes` | critic 的输出：接受/拒绝 + 理由 |
| `VerifierReport` | dataclass | `passed` + `failures` | verifier 的输出：pass/fail + 证据 |
| `planner` | 函数 | 把一句愿望变成固定的 `Spec`（硬编码 3 个测试） | Planner |
| `executor_correct` / `executor_buggy` | 函数 | 分别返回 `a + b` 与 `a * b` 的代码字符串 | Executor（两种行为） |
| `critic` | 函数 | 检查代码里是否含 `def`、`return`、函数名 | Critic（主观、可被骗） |
| `verifier` | 函数 | `exec` 代码，取出函数，逐个跑测试 | Verifier（确定性） |
| `run_pipeline` | 函数 | 依次调用四个角色并打印结论 | 流水线编排 |
| `main` | 函数 | 跑"正确"和"有 bug"两个场景，打印要点 | 演示入口 |

数据流：`user_wish (str)` → `planner` → `Spec` → `executor` → `Artifact` → `critic` → `CriticReport`；`Artifact` → `verifier` → `VerifierReport` → `run_pipeline` 根据两份报告给出 RESULT。

---

## 3. 逐段精讲

### 3.1 四个 dataclass：角色之间的"合同"

```python
@dataclass
class Spec:
    task_name: str
    signature: str
    description: str
    tests: list[tuple[tuple, int]]


@dataclass
class CriticReport:
    approved: bool
    notes: list[str] = field(default_factory=list)
```

- 讲义 Ship It 第二条："Explicit I/O schema per role. The planner returns a spec, not prose"。这里的 dataclass 就是 schema：下游角色只读字段，不去解析一段自由文本。
- `tests: list[tuple[tuple, int]]` 表示"(参数元组, 期望值)"的列表，例如 `((1, 2), 3)`。
- `field(default_factory=list)`：可变默认值必须这样写。如果写 `notes: list[str] = []`，dataclass 会直接报 `ValueError: mutable default <class 'list'> for field notes is not allowed`，因为所有实例会共享同一个列表。
- 报告类都带"证据"字段（`notes` / `failures`），对应讲义"Output: pass/fail with evidence"。

### 3.2 Planner：从愿望到 spec

```python
def planner(user_wish: str) -> Spec:
    return Spec(
        task_name="add_two",
        signature="add_two(a: int, b: int) -> int",
        description=user_wish,
        tests=[((1, 2), 3), ((10, 20), 30), ((-5, 5), 0)],
    )
```

- 真实 planner 会调用 LLM，把模糊愿望变成函数名、签名、验收标准；这里直接硬编码，`user_wish` 只被原样塞进 `description`。
- 三个测试恰好都能区分 `a + b` 与 `a * b`：`1×2=2`、`10×20=200`、`-5×5=-25`。如果换成 `((2, 2), 4)` 和 `((0, 0), 0)`，`a * b` 也能全部通过（已验证）——**verifier 的强度完全取决于这里的测试**。
- ⚠️ 测试被放进了 `Spec`，而 `Spec` 会整体传给 executor。真实系统中这等于把答案给了答题者：一个返回 `{(1,2):3, (10,20):30, (-5,5):0}[(a,b)]` 的"背答案"实现能同时骗过 critic 和 verifier（已验证）。生产中应保留隐藏测试只给 verifier。

### 3.3 Executor：两种行为

```python
def executor_correct(spec: Spec) -> Artifact:
    return Artifact(code="def add_two(a, b):\n    return a + b\n")


def executor_buggy(spec: Spec) -> Artifact:
    return Artifact(code="def add_two(a, b):\n    return a * b\n")
```

- 两者结构完全相同，只差一个运算符——这正是"plausible but wrong"（貌似合理但错误）的 LLM 输出的缩影。
- 函数作为参数传给 `run_pipeline`（Python 中函数是一等对象），方便切换场景。
- 讲义提到的 communicative dehallucination（缺信息先问 planner）在这里没有体现：executor 不会提问，也收不到反馈。

### 3.4 Critic：表面模式匹配

```python
def critic(spec: Spec, art: Artifact) -> CriticReport:
    notes: list[str] = []
    if "def" not in art.code:
        notes.append("missing def statement")
    if "return" not in art.code:
        notes.append("missing return")
    if spec.task_name not in art.code:
        notes.append(f"function name does not match spec '{spec.task_name}'")
    approved = not notes
    return CriticReport(approved=approved, notes=notes)
```

- 用三条 `in` 子串检查模拟"LLM 只看表面"：只要像一个函数定义、有 return、名字对，就批准。
- `approved = not notes`：空列表为假，`not []` 为 `True`，即"没有意见就批准"。
- 这个 critic 的局限（均已实际运行验证）：

| 输入代码 | critic | verifier | 说明 |
|---------|--------|----------|------|
| `return a * b` | 批准 | 失败 | 本节演示的漏报 |
| `def add_two(a, b)`（缺冒号） | 批准 | `exec error: expected ':'` | 看不出语法错误 |
| `# add_two` 注释 + `def f(a, b)` | 批准 | `no callable 'add_two'` | 函数名是子串匹配 |
| `add_two = lambda a, b: a + b` | **拒绝** | 通过 | 误报：正确代码被拒 |

- 讲义说 critic 能抓"品味问题"（taste issues）；这里的实现其实只检查形式，没有真正对照 `spec.description` 判断意图。真实场景中应由 LLM 读 spec 和代码给出带理由的评审。

### 3.5 Verifier：执行代码、跑测试

```python
def verifier(spec: Spec, art: Artifact) -> VerifierReport:
    ns: dict = {}
    try:
        exec(art.code, ns, ns)
    except Exception as e:
        return VerifierReport(passed=False, failures=[f"exec error: {e}"])
    fn = ns.get(spec.task_name)
    if not callable(fn):
        return VerifierReport(passed=False, failures=[f"no callable '{spec.task_name}' produced"])
    failures: list[str] = []
    for args, expected in spec.tests:
        try:
            got = fn(*args)
        except Exception as e:
            failures.append(f"call {args} raised {e}")
            continue
        if got != expected:
            failures.append(f"call {args}: expected {expected}, got {got}")
    return VerifierReport(passed=not failures, failures=failures)
```

逐步拆解：

1. `exec(art.code, ns, ns)`：在一个新字典里执行代码字符串，`def add_two` 会把函数对象放进 `ns["add_two"]`。传入同一个字典作 globals 和 locals，保证函数内部能看到同一个命名空间。语法错误（`SyntaxError` 是 `Exception` 子类）会被捕获并变成失败证据。
2. `ns.get(...)` + `callable(fn)`：防御"代码执行了但没定义所需函数"的情况。
3. 对每个测试 `fn(*args)` 解包调用；调用异常记一条失败并 `continue`，不让一个用例的异常中断整个检查。
4. `got != expected` 做相等比较。⚠️ 这意味着返回 `3.0` 或 `True`（`True == 1`）也会被判对——签名里的 `-> int` 没被检查（已验证 `return float(a + b)` 通过）。

⚠️ 讲义称之为"sandbox (`exec`)"，但它**不是沙箱**：
- `exec` 会自动注入 `__builtins__`，生成的代码可以 `import os`、读写文件、联网；
- 没有超时：`while True: pass` 会让 `fn(*args)` 永不返回，整个流水线挂死；
- 没有内存限制。

更稳妥的做法是子进程 + 超时 + 容器级隔离（测验 Q10 有可运行的子进程版本）。

### 3.6 `run_pipeline`：顺序编排与结论判定

```python
    crep = critic(spec, art)
    print(f"  [critic] approved={crep.approved}, notes={crep.notes}")
    vrep = verifier(spec, art)
    print(f"  [verifier] passed={vrep.passed}, failures={vrep.failures}")
    if crep.approved and vrep.passed:
        print("  RESULT: ship it.")
    elif not vrep.passed:
        print("  RESULT: verifier blocked ship (deterministic catch).")
    elif not crep.approved:
        print("  RESULT: critic blocked ship (subjective catch).")
```

- 结论优先级：都通过 → 交付；否则 verifier 失败优先报告；否则才是 critic 拒绝。两者都失败时只会显示 "verifier blocked"。
- `art.code.replace(chr(10), chr(10)+'    ')`：`chr(10)` 就是 `"\n"`，这样写是因为 Python 3.12 之前 f-string 的 `{}` 表达式里不能出现反斜杠；作用是给代码每行加缩进再打印。
- ⚠️ 与讲义 Ship It 不一致的地方：
  - 讲义说"critic 先跑（便宜），verifier 后跑（慢）"，代码虽然顺序如此，但 critic 拒绝时 verifier **照样运行**，没有"短路省成本"；
  - 讲义说"最多 2 轮 critic–executor 修订后升级给人"，代码**没有修订循环**，executor 也收不到反馈；
  - 讲义 Build It 说"critic misses the bug because it looks plausible"，在这里 critic 是被"设计成"看不出的——它根本不读运算符。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 dataclass 表示角色间消息 | 显式 schema，下游不用解析自由文本 | 生产中常用 Pydantic/JSON Schema，并配合 LLM 的 structured output |
| planner 硬编码 spec | 让演示确定、可复现 | 真实 planner 是 LLM；spec 要包含验收标准，并区分公开/隐藏测试 |
| executor 是两个固定函数 | 用一个运算符差异制造"貌似合理"的 bug | 真实 executor 是 LLM + 工具，需要能接收反馈并提问 |
| critic 用字符串匹配模拟 LLM | 无需 API 也能演示"被表面骗过" | 会误报（`lambda`）和漏报（语法错误）；真实 critic 用 LLM 并对照 spec 意图 |
| verifier 用 `exec` + 3 个测试 | 最短路径展示"确定性检查" | 不是沙箱、无超时；测试少且泄露给 executor。应使用子进程/容器、隐藏测试、属性测试 |
| 两份报告都跑、只打印结论 | 便于对比两种角色各自的判断 | 生产中 critic 不通过应短路；需要修订循环与预算、升级给人 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值（作为字符串保存），可以在注解里引用尚未定义的类，也减少运行时开销 |
| `@dataclass` | `class Spec:` 上方 | 根据带类型注解的字段自动生成 `__init__`、`__repr__`、`__eq__` |
| `field(default_factory=list)` | `notes: list[str] = field(default_factory=list)` | 可变默认值的正确写法，每个实例得到一个新列表 |
| 内置泛型注解 | `list[tuple[tuple, int]]`、`list[str]` | Python 3.9+ 可直接用 `list[...]` 而不必 `typing.List` |
| 函数返回类型注解 | `def planner(user_wish: str) -> Spec:` | 只是提示，运行时不强制检查 |
| 函数作为参数 | `run_pipeline(..., executor_correct, ...)` | 函数是一等对象，可以像变量一样传递，再 `executor(spec)` 调用 |
| `in` 子串检查 | `"def" not in art.code` | 判断字符串是否包含子串 |
| `exec` | `exec(art.code, ns, ns)` | 动态执行代码字符串；第二、三个参数是 globals 与 locals 字典 |
| `dict.get` | `ns.get(spec.task_name)` | 键不存在时返回 `None` 而不是抛 `KeyError` |
| `callable` | `if not callable(fn):` | 判断对象能否被调用（函数、lambda、带 `__call__` 的对象） |
| `try / except ... as e` + `continue` | 测试循环中 | 捕获单个用例的异常，记录后继续下一个 |
| 元组解包 + `*args` 调用 | `for args, expected in spec.tests:`、`fn(*args)` | 循环中拆开 `(参数, 期望)`；`*` 把元组展开为位置参数 |
| 真值测试 | `approved = not notes` | 空列表为假，`not []` 为 `True` |
| f-string | `f"call {args}: expected {expected}, got {got}"` | 字符串内嵌表达式 |
| `chr(10)` | `art.code.replace(chr(10), chr(10)+'    ')` | `chr(10)` 即换行符，绕开旧版 f-string 不能含反斜杠的限制 |
| 字符串乘法 | `print("-" * 70)` | 重复字符串 70 次 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`，瞬间完成）：

```text
Role specialization pipeline — planner, executor, critic, verifier
----------------------------------------------------------------------

=== Correct executor output ===
  [planner] spec: add_two(a: int, b: int) -> int with 3 tests
  [executor] produced:
    def add_two(a, b):
        return a + b
    
  [critic] approved=True, notes=[]
  [verifier] passed=True, failures=[]
  RESULT: ship it.

=== Buggy executor output (looks plausible; fails runtime) ===
  [planner] spec: add_two(a: int, b: int) -> int with 3 tests
  [executor] produced:
    def add_two(a, b):
        return a * b
    
  [critic] approved=True, notes=[]
  [verifier] passed=False, failures=['call (1, 2): expected 3, got 2', 'call (10, 20): expected 30, got 200', 'call (-5, 5): expected 0, got -25']
  RESULT: verifier blocked ship (deterministic catch).

Key insight: the critic passes the buggy code because it looks fine.
Only the verifier -- deterministic test execution -- catches the semantic bug.
All-LLM pipelines (no verifier) would ship the bug. Classic MAST failure mode.
```

逐项解读：

- **场景一**：正确代码，两个角色都通过，交付。代码末尾的 `\n` 被替换成"换行 + 4 空格"，所以输出里多了一行只有空格的空行。
- **场景二**：critic `notes=[]` 说明三条规则都满足——它根本没看运算符；verifier 给出的三条失败就是"证据"：每条都包含输入、期望值、实际值。下游（executor 修订或人工）拿到这三条就能定位问题。
- **结尾三行**是脚本写死的结论，对应讲义的"All-LLM anti-pattern"：如果流水线只有 critic，`a * b` 会被交付。
- 注意 verifier 在两个场景都被执行，即便在真实系统里 critic 拒绝时可以跳过它。

---

## 7. 动手改一改

1. **讲义练习 1**：给 verifier 加静态检查"`return` 恰好出现 1 次"。分别对 `a * b`、带 `if a > 100: return 0` 分支的实现、`lambda` 实现运行，观察它抓到了什么、误报了什么（参考测验 Q12）。
2. **加强测试**：把 `tests` 改成 `((2, 2), 4), ((0, 0), 0)`，确认 `executor_buggy` 能通过；再加一个"随机 100 对整数检查 `fn(a, b) == a + b`"的属性测试，让它重新被抓住。
3. **隐藏测试**：给 `Spec` 拆出 `public_tests` 和 `hidden_tests`，executor 只能看到前者；写一个"背答案"的 executor，验证它在隐藏测试上失败。
4. **修订循环**：按测验 Q11 改写 `run_pipeline` 为 `run_with_revisions`，critic 不通过时短路、把 notes/failures 作为反馈传给 executor，最多 2 轮后返回 `escalate_to_human`。
5. **讲义练习 2 + communicative dehallucination**：增加 `requirements_analyst` 角色；让 executor 在 spec 缺字段（例如没说溢出时怎么办）时返回一个 `Question(to="planner", text=...)` 对象而不是代码，由编排器转交并带着回答重新调用 executor。
6. **进阶**：把 verifier 换成子进程 + 超时实现，构造 `while True: pass` 的 executor，确认流水线在 2 秒后得到 `timeout` 失败而不是挂死。

---

## 8. 常见坑

- **把 LLM-as-judge 当 verifier**：只要 pass/fail 由模型决定，它就是 critic，仍可能被貌似合理的输出骗过。
- **测试太弱或可被过拟合**：`(2,2)→4` 这类对称输入无法区分加法和乘法；测试放进 executor 可见的 spec 会被"背答案"。
- **以为 `exec` 是沙箱**：它能访问 `__builtins__`、文件系统和网络，且没有超时。执行不可信代码要用进程/容器隔离。
- **critic 一票否决**：critic 会误报（本例的 `lambda`）。critic 的拒绝应作为可申诉的反馈，verifier 的失败才是硬门槛。
- **修订循环不设预算**：critic 与 executor 可能来回拉锯，消耗大量 token；讲义建议最多 2 轮后升级给人。
- **dataclass 可变默认值**：`notes: list[str] = []` 会直接报错，必须用 `field(default_factory=list)`。
- **只比较值不比较类型**：`3.0 == 3`、`True == 1` 都成立，若签名要求 `int`，需要额外 `isinstance` 检查。
