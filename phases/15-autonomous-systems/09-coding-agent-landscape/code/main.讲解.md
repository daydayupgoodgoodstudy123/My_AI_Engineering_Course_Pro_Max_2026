# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 09 节 自主 Coding Agent 生态概览（2026） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数；需要 Python 3.10+，因为用到 `zip(..., strict=True)`） ｜ **依赖**：仅标准库（`json`、`dataclasses`）

---

## 1. 这份代码在考察什么

讲义的核心论点是"脚手架是承重结构"，并对比了两种执行架构：**JSON tool call**（一轮一个结构化动作，宿主校验后执行）和 **CodeAct**（模型输出一段代码，在 sandbox 中执行，一个动作可以改很多东西）。这份代码用一个极小的内存"仓库"把两者放在一起比：

1. 仓库里有 3 个文件，各有一个 bug；有 3 个"测试"。
2. 两个脚手架用**同一个**确定性 stub "模型"（查表修复），只有"每个动作能做多少事"不同。
3. 比较三个指标：通过的测试数、用掉的轮数、单个动作的爆炸半径（改了几个文件）。

它能演示的是"同样的模型，脚手架不同，轮数和爆炸半径就不同"。它**不能**演示的是讲义说的"solves more tasks"（stub 模型永远不会失败）、"每个 JSON 动作被独立校验"（代码里没有校验器），以及真正的测试执行（测试是子串匹配）。读这份代码时要把"演示了什么"和"声称了什么"分开。

> 一句话：**把同一个"模型"装进两种脚手架，用轮数和爆炸半径说明——组合性与可审计性是一对交换**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `INITIAL_REPO` | 字典 | 3 个带 bug 的文件（文件名 → 源码字符串） | 待修复仓库 |
| `TESTS` | 列表 | `(路径, 测试表达式)`，表达式从未被执行 | 测试套件 |
| `FIXES` | 字典 | 路径 → `(旧串, 新串)` 的修复规则 | stub "模型"的知识 |
| `run_tests` | 函数 | 用子串匹配判断每个文件是否"修好" | 测试运行器（简化） |
| `_apply_fix` | 函数 | 就地对某个文件应用修复 | 编辑动作 |
| `JsonScaffold` | dataclass | 每轮只修一个失败文件，返回一个 JSON 动作 | JSON tool call |
| `CodeActScaffold` | dataclass | 每轮修好所有失败文件，返回一段"代码"字符串 | CodeAct |
| `report` | 函数 | 打印一行对比 | 结果展示 |
| `main` | 函数 | 两个脚手架各跑一次 + HEADLINE | 入口 |

数据流：`main` → `JsonScaffold().run()`（循环 `step` → `run_tests` → `_apply_fix` → 返回 JSON，直到 `done`）→ `CodeActScaffold().run()`（同上，但一步修多个）→ `report` 打印 passed / turns / blast-radius。

---

## 3. 逐段精讲

### 3.1 迷你世界：仓库、测试、修复表

```python
INITIAL_REPO = {
    "app.py": "def add(a, b):\n    return a - b\n",
    "util.py": "def lower(s):\n    return s.upper()\n",
    "cli.py": "VERSION = 'v0.0'\n",
}

TESTS = [
    ("app.py", "add(2, 3) == 5"),
    ("util.py", "lower('AB') == 'ab'"),
    ("cli.py", "VERSION == 'v1.0'"),
]

FIXES: dict[str, tuple[str, str]] = {
    "app.py": ("a - b", "a + b"),
    "util.py": ("s.upper()", "s.lower()"),
    "cli.py": ("v0.0", "v1.0"),
}
```

- 仓库用"文件名 → 源码字符串"的字典表示，足以模拟"编辑文件"。
- 3 个 bug 都是 1 行改动——恰好对应讲义所说 SWE-bench Verified 的"简单尾部"（161/500 题只需 1–2 行）。
- `FIXES` 就是 stub "模型"：它直接知道答案。真实 agent 必须先**定位**（retrieval）再**修改**再**验证**，而这里三步都被一张表取代了。
- 类型注解 `dict[str, tuple[str, str]]` 表示"字符串 → 二元组"。

### 3.2 测试运行器：其实是子串匹配

```python
def run_tests(repo: dict[str, str]) -> list[bool]:
    results = []
    for path, _expr in TESTS:
        src = repo.get(path, "")
        passed = False
        if path == "app.py":
            passed = "return a + b" in src
        elif path == "util.py":
            passed = "return s.lower()" in src
        elif path == "cli.py":
            passed = "VERSION = 'v1.0'" in src
        results.append(passed)
    return results
```

- `_expr`（例如 `"add(2, 3) == 5"`）被解包后**丢弃**，从未执行。所谓"测试"只是在源码里找特定子串。
- 后果：写在注释里的 `return a + b`、语法错误的文件、`return a + b` 前面还有一个错的 `return`，都会被判"通过"。
- `FIXES` 上方的注释说集中成一张表可以"avoid duplicating the if/elif chain"，但"什么算修好"的知识仍在这里以 if/elif 写死了一遍。新增测试路径而不改这里，该测试将永远失败（我们实测：加入 `db.py` 测试后两种脚手架都是 3/4）。
- 测验 Q11 给出了一个用 `exec` + `eval` 真正执行代码的版本（初始仓库 `[False, False, False]`，修复后 `[True, True, True]`），并说明真实 agent 必须把这一步放进 sandbox。

```python
def _apply_fix(repo: dict[str, str], path: str) -> bool:
    rule = FIXES.get(path)
    if rule is None:
        return False
    old, new = rule
    repo[path] = repo[path].replace(old, new)
    return True
```

- 前导下划线 `_apply_fix` 是"模块内部函数"的约定（`from main import *` 不会导出它）。
- `str.replace` 替换所有出现处；返回布尔值告诉调用者"是否真的有规则可用"。

### 3.3 JSON tool-call 脚手架：一轮一个动作

```python
@dataclass
class JsonScaffold:
    repo: dict[str, str] = field(default_factory=lambda: dict(INITIAL_REPO))
    turns: int = 0

    def step(self) -> str:
        self.turns += 1
        results = run_tests(self.repo)
        for (path, _), ok in zip(TESTS, results, strict=True):
            if ok:
                continue
            if _apply_fix(self.repo, path):
                return json.dumps({"tool": "edit", "path": path})
        return json.dumps({"tool": "done"})

    def blast_radius(self) -> int:
        return 1

    def run(self, max_turns: int = 10) -> tuple[int, int]:
        for _ in range(max_turns):
            action = self.step()
            if json.loads(action).get("tool") == "done":
                break
        passed = sum(run_tests(self.repo))
        return passed, self.turns
```

- `default_factory=lambda: dict(INITIAL_REPO)`：每个脚手架拿到仓库的**副本**，互不影响（字符串不可变，浅拷贝足够）。
- `zip(TESTS, results, strict=True)`：两个列表长度不一致时直接报错，防止静默错位；`(path, _)` 在 for 中做嵌套解包。
- 每次 `step()` 找到**第一个**失败的文件，修好它就立刻 `return`——这就是"一轮一个动作"。
- 实测动作序列：`edit app.py` → `edit util.py` → `edit cli.py` → `done`，`turns = 4`（含最后的 done 轮）。
- `sum(run_tests(...))`：`True` 在求和时当作 1，所以得到通过的测试数。
- ⚠️ **没有校验**：`_apply_fix` 在生成 JSON **之前**就已经修改了仓库，JSON 只是事后记录。真实的 JSON tool call 流程是"模型提议 → 宿主校验 → 宿主执行"，HEADLINE 所说的 "every action is independently validated" 在代码中不存在。测验 Q9 给出了三段式改写（实测同样 `(3, 4)`）。
- ⚠️ `blast_radius()` 返回写死的 1，是"静态上界"；而 CodeAct 的是"观测值"，两者口径不同（见 3.4）。

### 3.4 CodeAct 脚手架：一个动作改所有文件

```python
@dataclass
class CodeActScaffold:
    repo: dict[str, str] = field(default_factory=lambda: dict(INITIAL_REPO))
    turns: int = 0
    worst_touched: int = 0

    def step(self) -> str:
        self.turns += 1
        snippet_lines = []
        results = run_tests(self.repo)
        for (path, _), ok in zip(TESTS, results, strict=True):
            if ok:
                continue
            if _apply_fix(self.repo, path):
                snippet_lines.append(f"fs.write('{path}', ...)")
        self.worst_touched = max(self.worst_touched, len(snippet_lines))
        if not snippet_lines:
            return "done()"
        return "; ".join(snippet_lines)
```

- 与 JSON 版唯一的区别：循环里**不 return**，把所有失败文件都修了，再把它们拼成一段"代码"。实测第 1 轮返回 `"fs.write('app.py', ...); fs.write('util.py', ...); fs.write('cli.py', ...)"`，第 2 轮 `done()`，`turns = 2`。
- `worst_touched` 记录单个动作实际改动的最大文件数（3）。注释解释了为何不用 `len(repo)`：观测值不会因为仓库里多了无关文件而虚高。
- ⚠️ 这里的"代码"是**字符串**，从未被执行；修改是 Python 宿主直接做的。真实 CodeAct 的风险在于这段代码在 sandbox 里能做"sandbox 允许的一切"（读写任意文件、联网、起进程），所以讲义说 CodeAct 的爆炸半径是"anything the sandbox runtime allows"，而不是"这次碰巧改了几个文件"。
- `"; ".join(...)`：用分号把多条语句拼成一行。

### 3.5 驱动与输出

```python
def report(name: str, passed: int, turns: int, blast: int) -> None:
    total = len(TESTS)
    print(f"  {name:<18}  passed {passed}/{total}  turns {turns:>2}  "
          f"blast-radius {blast}")
```

- `{name:<18}` 左对齐占 18 列，`{turns:>2}` 右对齐占 2 列，让两行对齐。
- 两个相邻的 f-string 会自动拼接。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 同一个确定性 stub 模型 | 隔离脚手架的影响，排除模型质量差异 | 模型永远不失败，无法体现 retrieval、verifier loop、"solves more tasks" 等讲义要点 |
| 仓库 = 内存字典 | 不需要文件系统和 sandbox | 无法演示真正的爆炸半径与隔离 |
| 测试 = 子串匹配 | 不用执行任意代码，安全简单 | 会接受错误补丁；生产用真实测试套件，并在 sandbox 中运行 |
| `FIXES` 集中成表 | 两个脚手架共享同一"模型知识" | `run_tests` 里仍写死了一遍判定逻辑 |
| JSON 动作在编辑后才生成 | 代码最短 | 没有"提议 → 校验 → 执行"的关卡；生产中校验器是 JSON 架构的安全核心 |
| CodeAct 的"代码"不执行 | 安全 | 体现不了 CodeAct 的真正风险面；生产中需要容器/VM、无外网、资源上限 |
| blast radius：JSON 静态 1、CodeAct 观测 3 | 直观 | 两种口径不可比；真实的爆炸半径应按"一个动作**能**影响什么"来定义 |
| turns 包含 done 轮 | 实现自然 | 口径需要说明：编辑动作实际是 3 对 1 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 多行字符串中的 `\n` | `"def add(a, b):\n    return a - b\n"` | 换行转义，让一行字面量表示多行源码 |
| 类型注解的复杂形式 | `FIXES: dict[str, tuple[str, str]]`、`-> tuple[int, int]` | 字典值是二元组；函数返回二元组 |
| 元组解包 | `old, new = rule`、`passed, turns = js.run()` | 一次给多个变量赋值 |
| for 中嵌套解包 | `for (path, _), ok in zip(TESTS, results, strict=True):` | `TESTS` 的元素本身是元组 |
| `zip(..., strict=True)` | 同上 | Python 3.10+：长度不一致时抛 `ValueError` |
| 字典 `.get` 带默认值 | `repo.get(path, "")` | 键不存在时返回空串 |
| `in` 做子串判断 | `"return a + b" in src` | 字符串包含关系 |
| `str.replace` / `str.join` | `repo[path].replace(old, new)`、`"; ".join(snippet_lines)` | 替换、拼接 |
| 布尔值求和 | `sum(run_tests(self.repo))` | `True == 1`、`False == 0` |
| `@dataclass` + `field(default_factory=...)` | `repo: dict[str, str] = field(default_factory=lambda: dict(INITIAL_REPO))` | 每个实例拿到独立副本 |
| `json.dumps` / `json.loads` | `json.dumps({"tool": "edit", "path": path})`、`json.loads(action).get("tool")` | 对象 ↔ JSON 字符串 |
| 前导下划线命名 | `_apply_fix`、`_expr` | 约定：内部使用 / 故意不用 |
| `max` 维护最大值 | `self.worst_touched = max(self.worst_touched, len(snippet_lines))` | 记录观测到的最大值 |
| f-string 对齐 | `{name:<18}`、`{turns:>2}` | 左/右对齐与宽度 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，确定性，无随机数）：

```text
Same stub model, three-bug toy repo. Scaffold-only comparison.
----------------------------------------------------------------------
  JSON tool-call      passed 3/3  turns  4  blast-radius 1
  CodeAct (stub)      passed 3/3  turns  2  blast-radius 3
```

逐项解读：

- **passed 都是 3/3**：stub 模型对每个 bug 都有现成答案，任务完成率不会有差别。讲义 "Use It" 所说的 "CodeAct scaffold solves more tasks" 在默认输出里看不到。
- **turns 4 对 2**：JSON 是 3 次编辑 + 1 次 done；CodeAct 是 1 次编辑（改 3 个文件）+ 1 次 done。只数编辑动作是 3 对 1。
- **blast-radius 1 对 3**：JSON 是写死的上界 1；CodeAct 是观测到的单动作最大改动文件数 3。
- **轮数预算下的差别**（额外实验）：`JsonScaffold().run(max_turns=2)` → `(2, 2)`，只修好 2 个；`CodeActScaffold().run(max_turns=1)` → `(3, 1)`。在上下文、成本、超时都有限的真实场景里，这才是"同样预算下完成更多"的含义。
- HEADLINE 的定性结论（"scaffolding is the product"、"trade-off is what to audit"）与讲义一致；但 "JSON tool-calls get safety by construction since every action is independently validated" 描述的是真实系统，本代码并没有实现校验。

---

## 7. 动手改一改

1. **（讲义练习 1）** 打印两种脚手架的完整动作序列，说明各自的轮数和"每个动作的爆炸半径"；再用 `run(max_turns=1)`、`run(max_turns=2)` 重跑，比较通过数。
2. **加上真正的校验器**：按测验 Q9 把 JSON 脚手架改成"提议 → 校验 → 执行"，然后让 stub 模型偶尔提议一个白名单外的路径（如 `../secrets.env`），确认它被拒绝而仓库未被修改。
3. **真实测试**：用测验 Q11 的 `run_tests_real` 替换子串匹配；再构造一个"把 `return a + b` 写进注释"的错误补丁，比较两种测试的判断。
4. **让模型会失败**：给 stub 模型加入"30% 概率给出错误修复"，并加一个 verifier loop（失败就重试，最多 k 次），统计两种脚手架在固定轮数预算下的通过率——这才能体现讲义"verifier loop 是 10+ 分"的论点。
5. **重新定义爆炸半径**：把 CodeAct 的爆炸半径定义为"该动作有权限写入的文件数"（例如 sandbox 中整个仓库），把 JSON 的定义为"校验器允许的路径数"，重新输出对比。
6. **（讲义练习 4）进阶**：写一个函数，输入总分、简单题数量与简单题通过率，输出"排除简单尾部后的分数"；用测验 Q12 的两个假设模型验证排名差距的变化。

---

## 8. 常见坑

- **把事后日志当成校验**：先改仓库再生成 JSON，等于跳过了 JSON 架构最重要的安全关卡。
- **用子串匹配代替测试**：会接受注释里的"修复"和语法错误的文件；真实评测必须执行测试。
- **在宿主进程里执行 agent 写的代码**：`exec` 不是 sandbox；agent 代码能读写宿主文件、联网、死循环。
- **口径不一致的指标**：静态上界的 1 与观测值的 3 并列比较；turns 是否包含 done 轮也要写清。
- **用全知 stub 比"解决率"**：模型永不失败时，脚手架只能影响轮数，不能影响成功率。
- **把 Docker 当万能边界**：挂载宿主目录、Docker socket 或给 sandbox 生产凭证，会让隔离形同虚设。
- **只看公开基准的总分**：简单尾部会压缩模型差距、掩盖回退，选型要用自己分布上的评测。
