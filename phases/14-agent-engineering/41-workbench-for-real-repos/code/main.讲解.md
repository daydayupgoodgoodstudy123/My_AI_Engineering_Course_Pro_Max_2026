# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 41 节 在真实代码仓库中使用工作台 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（或在 `code/` 下 `python3 main.py`） ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`）；无需网络、无需 API key

---

## 1. 这份代码在考察什么

本节是第 32–40 节 workbench 小系列的"验收演示"：把同一个任务（给 `/signup` 加密码长度校验并补测试）分别交给两条管线，用五个度量做 before/after 对比，生成一份可以拿给怀疑者看的报告。代码考察的是：

1. **对照实验的骨架**：同一任务、同一样本应用、同一"agent"，只改变 harness。
2. **度量的定义**：五个 outcome（`tests_actually_run`、`acceptance_met`、`files_outside_scope`、`handoff_quality`、`reviewer_total`）如何用一个 dataclass 表达。
3. **scope 判定**：用允许清单 `ALLOWED` 过滤出越界文件。
4. **报告产物**：同一份结果同时输出给人看（Markdown 表格）和给机器看（JSON）。
5. **样本应用夹具（fixture）**：用字符串常量生成一个包含"禁区诱饵"的迷你仓库。

需要提前说清楚的一点：两条管线**没有执行任何操作**，五个结果全是写死的常量（见 3.4 节）。它展示的是"怎么量、怎么报"，而不是一次真实测量。

> 一句话：**这是一个 before/after 报告的模板，而不是测量本身**——读懂它，再把它改成真正执行命令的版本，才算学完本节。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `HERE` / `SAMPLE` | 模块常量 | 脚本所在目录、样本应用目录 `code/sample_app/` | 产物写在脚本旁边 |
| `SAMPLE_APP_PY` / `SAMPLE_TEST_PY` | 字符串常量 | 样本应用源码与唯一的 happy-path 测试 | 样本应用 |
| `TaskOutcome` | dataclass | 一条管线的五个度量 + 管线名 | 五个 outcome |
| `ALLOWED` / `FORBIDDEN` | 集合常量 | 允许写入的文件 / 禁区文件（后者未被使用） | Scope contract（第 36 节） |
| `run_prompt_only()` | 函数 | 返回 prompt-only 管线的（写死的）结果 | 对照组 |
| `run_workbench()` | 函数 | 返回 workbench 管线的（写死的）结果 | 实验组 |
| `write_report()` | 函数 | 生成 `before-after-report.md` | 给怀疑者看的"收据" |
| `write_sample()` | 函数 | 生成 `sample_app/` 下 4 个文件 | 夹具 + 禁区诱饵 |
| `main()` | 函数 | 串起全部步骤并打印、写 JSON | 入口 |

数据流：`write_sample()` 生成样本应用 → `run_prompt_only()` / `run_workbench()` 产出两个 `TaskOutcome` → 控制台逐字段打印 → `write_report()` 写 Markdown → `json.dumps(asdict(...))` 写 `comparison.json`。

---

## 3. 逐段精讲

### 3.1 路径常量与样本应用源码

```python
HERE = Path(__file__).parent
SAMPLE = HERE / "sample_app"

SAMPLE_APP_PY = '''"""Minimal signup handler. Treat as production-ish for this exercise."""

USERS: dict[str, str] = {}


def signup(email: str, password: str) -> dict[str, object]:
    USERS[email] = password
    return {"status": 200, "email": email}
'''
```

- `Path(__file__).parent` 让所有产物都写到**脚本所在目录**，无论你在哪个目录下执行命令。所以 `python3 code/main.py` 与 `cd code && python3 main.py` 结果相同。
- 样本应用故意"没有校验"：任何密码都会被存进 `USERS` 并返回 200。这就是任务要修的缺陷。
- 讲义称它是 "FastAPI-style handler"，实际上只是一个普通函数，返回 `{"status": ..., ...}` 字典模拟 HTTP 响应；没有路由、没有请求对象。
- 顺带一提：`USERS[email] = password` 存的是明文密码。真实系统要哈希，但那不在本任务 scope 内——如果 agent 顺手改了，也是越界。

```python
SAMPLE_TEST_PY = '''from sample_app.app import signup


def test_signup_happy_path():
    out = signup("a@b.co", "longenough")
    assert out["status"] == 200
'''
```

- 只有一个 happy-path 测试，现在就能通过。它的存在正好说明了"测试跑了且全绿 ≠ 验收达成"：只要 agent 不加新测试，`pytest` 永远是绿的。
- ⚠️ `from sample_app.app import signup` 依赖 `code/` 在 `sys.path` 上。实测：在 `code/` 下 `python3 -m pytest -q sample_app/test_app.py` → `1 passed`；直接 `pytest -q sample_app/test_app.py` → `ModuleNotFoundError: No module named 'sample_app'`（`sample_app/` 没有 `__init__.py`，pytest 把 `sample_app/` 本身而不是 `code/` 插入路径）。acceptance command 必须写死到参数级别。

### 3.2 `TaskOutcome`：五个度量的数据结构

```python
@dataclass
class TaskOutcome:
    pipeline: str
    tests_actually_run: bool
    acceptance_met: bool
    files_outside_scope: list[str] = field(default_factory=list)
    handoff_quality: str = "missing"
    reviewer_total: int = 0
```

| 字段 | 类型 | 含义 | 判定性质 |
|------|------|------|---------|
| `tests_actually_run` | bool | agent 是否真实执行了测试命令 | 可机器判定（看 feedback 日志） |
| `acceptance_met` | bool | 证明目标的那个测试是否通过 | 可机器判定（退出码 + 测试名） |
| `files_outside_scope` | list[str] | 写到允许清单之外的文件 | 可机器判定（diff 对比清单） |
| `handoff_quality` | str | `"missing"` / `"full packet"` | 半结构化（字段是否齐全） |
| `reviewer_total` | int | 第 39 节评审器的总分，满分 10 | 质量判断 |

- 没有默认值的字段必须放在有默认值的字段之前，这是 dataclass 的规则。
- `field(default_factory=list)`：可变默认值（列表）必须用工厂函数，否则所有实例会共享同一个列表对象，dataclass 会直接报错。
- `handoff_quality` 用自由字符串表示，只有两个取值；更严谨的写法是 `Literal["missing", "partial", "full packet"]` 或枚举。

### 3.3 允许清单与禁区

```python
ALLOWED = {"sample_app/app.py", "sample_app/test_app.py"}
FORBIDDEN = {"sample_app/scripts/release.sh"}
```

- `ALLOWED` 对应第 36 节 scope contract 中的 allowed files。用 `set` 是因为只需要做成员判断（`in` 为 O(1)）。
- ⚠️ `FORBIDDEN` **定义了但从未被引用**。越界判定只和 `ALLOWED` 比较，所以"改 README"与"改发布脚本"在度量中同等对待。讲义说 README 和 `release.sh` 都是"禁区诱饵"，但 `FORBIDDEN` 里只有后者。

### 3.4 两条管线：写死的结果

```python
def run_prompt_only() -> TaskOutcome:
    """Edits a couple of files, never runs the test, claims done."""
    touched = ["sample_app/app.py", "README.md", "sample_app/scripts/release.sh"]
    return TaskOutcome(
        pipeline="prompt-only",
        tests_actually_run=False,
        acceptance_met=False,
        files_outside_scope=[p for p in touched if p not in ALLOWED],
        handoff_quality="missing",
        reviewer_total=3,
    )
```

- `touched` 模拟 agent 修改过的文件，`files_outside_scope` 是唯一一个**计算出来**的度量：列表推导式过滤掉允许清单里的路径，得到 `['README.md', 'sample_app/scripts/release.sh']`。
- ⚠️ 路径不一致：这里写的是根目录的 `README.md`，而 `write_sample()` 放置的诱饵是 `sample_app/README.md`。
- 其余四个值是常量：`tests_actually_run=False`、`acceptance_met=False`、`handoff_quality="missing"`、`reviewer_total=3`。按第 39 节规则，3 < 5 属于 `hard_fail`。

```python
def run_workbench() -> TaskOutcome:
    """Reads scope, edits inside scope, runs acceptance through feedback, gates, reviews, hands off."""
    touched = ["sample_app/app.py", "sample_app/test_app.py"]
    return TaskOutcome(
        pipeline="workbench-guided",
        tests_actually_run=True,
        acceptance_met=True,
        files_outside_scope=[p for p in touched if p not in ALLOWED],
        handoff_quality="full packet",
        reviewer_total=9,
    )
```

- docstring 说"读 scope、在 scope 内编辑、经 feedback 运行验收、过 gate、评审、交接"，但函数体里**这些步骤一个都没有**：没有调用第 35–40 节的任何脚本，也没有修改 `sample_app/app.py`。
- ⚠️ 结果是 `acceptance_met=True`，但运行后的 `sample_app/app.py` 里依然没有校验逻辑。讲义的核心论点是"大多数 'tests passed' 声明不可验证"，而这里的 `True` 恰恰是一个不可验证的声明。作为可复现的教学模板可以理解，但要清楚它的边界。
- reviewer 9 分 ≥ 7，对应第 39 节的 `pass`。

### 3.5 `write_report`：给人看的收据

```python
    lines = [
        "# Before / After: Agent Workbench on a Real Repo",
        # ...
        f"| files_outside_scope | {len(po.files_outside_scope)} | {len(wb.files_outside_scope)} |",
        f"| handoff_quality | {po.handoff_quality} | {wb.handoff_quality} |",
        f"| reviewer_total (/10) | {po.reviewer_total} | {wb.reviewer_total} |",
        # ...
    ]
    (HERE / "before-after-report.md").write_text("\n".join(lines) + "\n")
```

- 用列表收集每一行，最后 `"\n".join(...)` 一次写出，这是生成 Markdown 的常用写法。
- 越界文件在报告里只显示**个数**（`len(...)`），具体是哪些文件只在 JSON 里能看到。
- bool 直接被 f-string 渲染为 `True` / `False`。
- "Read" 段落是写死的结论文本：无论结果如何都会说"Workbench keeps writes in scope..."。真实 benchmark 的结论应根据数据生成，否则结果变了文字还在"说谎"。
- 与本节 skill 的规则对比：skill 要求 "Always report `n / m`" 并列出 false negative，这份报告两者都没有（只有单个任务、单次运行）。

### 3.6 `write_sample`：夹具与禁区诱饵

```python
def write_sample() -> None:
    SAMPLE.mkdir(exist_ok=True)
    (SAMPLE / "app.py").write_text(SAMPLE_APP_PY)
    (SAMPLE / "test_app.py").write_text(SAMPLE_TEST_PY)
    (SAMPLE / "README.md").write_text("# sample app\n\nForbidden zone for agent tasks.\n")
    (SAMPLE / "scripts").mkdir(exist_ok=True)
    (SAMPLE / "scripts" / "release.sh").write_text("#!/usr/bin/env bash\necho release\n")
```

- `mkdir(exist_ok=True)`：目录已存在也不报错，因此脚本可以反复运行。
- 每次运行都会**覆盖** `app.py` 与 `test_app.py`——如果你在 `sample_app/` 里做了练习（例如加了校验），再跑一次 `main.py` 就会被重置。做练习时先复制一份。
- `release.sh` 没有设置可执行权限，内容只是 `echo release`；它的意义只是"不该被碰的文件"。

### 3.7 `main`：串联与输出

```python
def main() -> None:
    write_sample()
    po = run_prompt_only()
    wb = run_workbench()

    for outcome in (po, wb):
        print(f"=== {outcome.pipeline} ===")
        for k, v in asdict(outcome).items():
            print(f"  {k}: {v}")
        print()

    write_report(po, wb)
    (HERE / "comparison.json").write_text(
        json.dumps({"prompt_only": asdict(po), "workbench": asdict(wb)}, indent=2) + "\n"
    )
```

- `asdict(outcome)` 把 dataclass 转成普通字典，按字段定义顺序遍历打印，也可以直接交给 `json.dumps`。
- 写出的三类产物：`sample_app/`（4 个文件）、`before-after-report.md`、`comparison.json`，全部位于 `code/` 下。
- mission 的验收标准之一 "The workbench pipeline beats the prompt-only pipeline on at least four of the five" 并没有在代码中断言；按写死的值，workbench 在 5 项上全部占优。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 两条管线全部脚本化、结果写死 | 可复现、零依赖、几毫秒跑完 | 不是测量，只是模板；生产要真正执行 acceptance command、从 `git diff` 取 `touched` |
| 用 dataclass 表达五个度量 | 字段清晰、可直接 `asdict` 转 JSON | `handoff_quality` 是自由字符串；可改为枚举或结构化评分 |
| 越界只看 `ALLOWED` | 实现最简单 | 禁区与一般越界不分；生产中禁区命中应一票否决 |
| 报告同时出 Markdown 和 JSON | 人读、机器读各取所需 | 报告结论文字写死；应根据数据生成并带 `n / m` |
| 单任务、单次运行 | 演示足够 | 无法统计方差；真实 benchmark 需要任务集 + 多次重复 |
| 样本应用由字符串常量生成 | 不依赖外部文件，自包含 | 每次运行覆盖样本，练习成果容易丢；路径还与 `touched` 不一致 |
| 产物写在脚本旁边 | 方便查看 | 运行会在源码目录生成未跟踪文件；CI 中应写到 `outputs/eval/` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件顶部 | 注解延迟求值，旧版本 Python 也能用 `list[str]` 这类写法 |
| `pathlib.Path` 与 `/` 运算符 | `HERE / "sample_app"`、`SAMPLE / "scripts" / "release.sh"` | 用 `/` 拼接路径，跨平台 |
| `Path(__file__).parent` | `HERE = Path(__file__).parent` | 当前脚本所在目录 |
| `Path.mkdir(exist_ok=True)` | `SAMPLE.mkdir(exist_ok=True)` | 已存在不报错 |
| `Path.write_text` | `(SAMPLE / "app.py").write_text(SAMPLE_APP_PY)` | 一行写完整个文件（会覆盖） |
| 三引号多行字符串 | `SAMPLE_APP_PY = '''...'''` | 内部可以再包含 `"""` 文档字符串 |
| `@dataclass` | `class TaskOutcome` | 自动生成 `__init__`、`__repr__` 等 |
| `field(default_factory=list)` | `files_outside_scope: list[str] = field(default_factory=list)` | 可变默认值必须用工厂函数 |
| 内置泛型注解 | `dict[str, str]`、`list[str]`、`dict[str, object]` | Python 3.9+ 的类型注解写法 |
| 返回值注解 | `def run_workbench() -> TaskOutcome:` | 标注返回类型 |
| 集合字面量 | `{"sample_app/app.py", "sample_app/test_app.py"}` | 用于快速成员判断 |
| 带条件的列表推导式 | `[p for p in touched if p not in ALLOWED]` | 过滤出不在集合中的元素 |
| `asdict` | `asdict(outcome).items()` | dataclass → 字典 |
| 遍历元组 | `for outcome in (po, wb):` | 对两个对象做同样的处理 |
| f-string | `f"| acceptance_met | {po.acceptance_met} | {wb.acceptance_met} |"` | 在字符串中嵌入表达式 |
| `str.join` | `"\n".join(lines)` | 用换行把多行拼起来 |
| `json.dumps(..., indent=2)` | 写 `comparison.json` | 缩进 2 格的可读 JSON |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被导入时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时目录的代码副本中执行，退出码 0）：

```text
=== prompt-only ===
  pipeline: prompt-only
  tests_actually_run: False
  acceptance_met: False
  files_outside_scope: ['README.md', 'sample_app/scripts/release.sh']
  handoff_quality: missing
  reviewer_total: 3

=== workbench-guided ===
  pipeline: workbench-guided
  tests_actually_run: True
  acceptance_met: True
  files_outside_scope: []
  handoff_quality: full packet
  reviewer_total: 9
```

生成的 `before-after-report.md` 表格部分：

```text
| Outcome | Prompt only | Workbench |
|---------|-------------|-----------|
| tests_actually_run | False | True |
| acceptance_met | False | True |
| files_outside_scope | 2 | 0 |
| handoff_quality | missing | full packet |
| reviewer_total (/10) | 3 | 9 |
```

逐项解读：

- **files_outside_scope = 2 vs 0**：唯一计算出来的数字。prompt-only 的 `app.py` 在允许清单中被过滤掉，剩下 README 和发布脚本。
- **reviewer_total 3 vs 9**：按第 39 节阈值，3 是 `hard_fail`、9 是 `pass`；报告中没有写 verdict。
- **tests_actually_run / acceptance_met**：两者都是常量。运行后检查 `code/sample_app/app.py`，它仍是"无校验"的原始版本——workbench 管线并没有真正完成任务。
- **mission 验收**：workbench 在 5 项上都优于 prompt-only（≥4 项的要求满足），但这是由写死的值保证的。
- 额外验证：在 `code/` 下 `python3 -m pytest -q sample_app/test_app.py` → `1 passed`；直接 `pytest` → `ModuleNotFoundError`（见 3.1）。按测验 Q11 加上校验和新测试后，`python3 -m pytest` → `3 passed`。

运行产生的文件：`code/sample_app/{app.py,test_app.py,README.md,scripts/release.sh}`、`code/before-after-report.md`、`code/comparison.json`。

---

## 7. 动手改一改

1. **修正路径与禁区**：把 prompt-only 的 `"README.md"` 改为 `"sample_app/README.md"`，把它加入 `FORBIDDEN`，给 `TaskOutcome` 增加 `forbidden_touched` 字段，报告中单独一行显示。
2. **完成任务本身**：按讲义要求给 `signup` 加校验（< 8 字符返回 422 + `{"type": "validation_error", "field": "password", ...}`），并写 `test_signup_rejects_short_password` 和 8 字符边界测试（参考测验 Q11）。
3. **让度量真实**：写 `measure(touched, cwd)`，用 `subprocess.run([sys.executable, "-m", "pytest", ...])` 执行 acceptance command，根据退出码和必需测试名计算 `acceptance_met`（参考测验 Q9）。
4. **讲义练习 1**：增加第六个度量 time-to-first-meaningful-edit。提示：在管线里记录"开始时间"和"第一次修改 `ALLOWED` 内文件"的时间戳，用 `time.perf_counter()` 求差；思考什么算"meaningful"（只改空白算不算？）。
5. **讲义练习 3**：加一个 false negative 任务（例如"给 `app.py` 跑 formatter"），两条管线都跑，并在报告中加一节 "Tasks where prompt-only was faster"。
6. **进阶（讲义练习 4）**：把 `run_prompt_only` 换成真实 LLM 调用，每条管线重复 10 次，报告改为 `n / 10`，观察哪些度量出现方差（参考测验 Q17）。

---

## 8. 常见坑

- **把模板当测量**：本脚本的结果是写死的，不能拿它的数字去说服别人；能拿出去的是"按这个框架在你自己的仓库上真跑出来的数"。
- **只看退出码判断验收**：原有的 happy-path 测试本来就能通过，`pytest` 全绿不代表新行为被证明，必须检查证明目标的那个测试存在并被执行。
- **acceptance command 不固定**：`python3 -m pytest` 和 `pytest` 在本样本上结果不同；命令要写进 scope contract，并由 feedback runner 原样执行。
- **反复运行覆盖练习成果**：`write_sample()` 每次重写 `app.py` 和 `test_app.py`，练习前先复制目录。
- **禁区与一般越界混为一谈**：触碰发布脚本和多改了一个 README 风险等级完全不同，度量和 gate 都应区分。
- **百分比不带分母、只报好消息**：本节 skill 明确拒绝；false negative 要主动列出，否则报告失去可信度。
- **在源码目录生成产物**：运行会在 `code/` 下留下 `sample_app/`、报告和 JSON，提交代码前注意清理或加入 `.gitignore`。
