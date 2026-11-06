# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 36 节 Scope Contracts 与任务边界 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（无参数） ｜ **依赖**：仅标准库（`fnmatch`、`json`、`time`、`dataclasses`、`pathlib`）；运行时会在 `code/closed/` 下写一个归档 JSON

---

## 1. 这份代码在考察什么

这份代码把讲义里的"scope contract（任务范围合同）"落成一个可执行的检查器，覆盖讲义的这些概念：

1. **合同即数据**：用 `@dataclass ScopeContract` 表达七个核心字段，外加生产模式里的 `time_budget_minutes`、`network_egress`、`violation_budget` 和文档软路径。
2. **scope check 就是 diff check**：把一次运行的 touched files、跑过的命令、耗时、访问过的网络主机（`RunSummary`）与合同对比，产出带严重度的 `Finding`。
3. **负空间优先**：forbidden 先于 allowed 判断。
4. **严重度分层 + 违规预算**：`block` / `warn` / `info` 三级，`warn` 在预算内不判失败。
5. **最小权限合并**：项目级合同与任务级合同合并成一份"有效合同"。
6. **归档**：任务结束后把报告写到 `closed/` 下。

> 一句话：**把"不要越界"从 prompt 中的一句愿望，变成一个读合同、读 diff、输出可拒绝 finding 的函数**。同时它也暴露了几个典型实现陷阱（glob 语义、按字符串合并 glob、预算计数单位、归档覆盖），这些正是本讲解和测验的重点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ScopeContract` | dataclass | 合同的全部字段，含默认值 | scope contract schema |
| `RunSummary` | dataclass | 一次运行的事实：改了哪些文件、跑了哪些命令、耗时、访问的主机 | diff + 运行记录 |
| `Finding` | dataclass | 一条违规：代码、严重度、详情 | tagged finding |
| `ScopeReport` | dataclass + `passed()` | 分类结果 + findings + 是否超预算 | 交给 verification gate 的报告 |
| `matches_any` | 函数 | 路径是否匹配任一 glob（`fnmatch`） | glob 匹配 |
| `merge_contracts` / `_merge_egress` / `_min_optional` | 函数 | 最小权限合并 | multi-contract merge |
| `scope_check` | 函数 | 核心：四路分类 + 各维度检查 + 预算 | diff check |
| `archive` | 函数 | 把报告写到 `closed/<task_id>.json` | 合同随任务归档 |
| `main` | 函数 | 构造两份合同、合并、跑 clean/creep 两次检查、打印、归档 | demo |

数据流：`project_wide` + `task` → `merge_contracts` → `effective` → `scope_check(effective, clean / creep)` → 打印 findings 与 `passed()` → `archive` 写 `closed/T-001.json`。

---

## 3. 逐段精讲

### 3.1 合同与运行记录的数据结构

```python
@dataclass
class ScopeContract:
    task_id: str
    goal: str
    allowed_files: list[str]
    forbidden_files: list[str]
    acceptance_criteria: list[str]
    rollback_plan: str
    approvals_required: list[str] = field(default_factory=list)
    time_budget_minutes: int | None = None
    network_egress: list[str] | None = None  # None = no enforcement, [] = deny-all, [...] = allowlist
    violation_budget: int = 0
    docs_paths_soft: list[str] = field(default_factory=lambda: ["docs/**", "README.md", "**/*.md"])
```

- 前六个字段没有默认值，是**必填**的；讲义里七个字段中只有 `approvals_required` 给了默认空列表。
- `network_egress` 的三态设计很关键：`None` = 不检查；`[]` = 全部拒绝；`["a.com"]` = 白名单。用 `None` 和 `[]` 区分"没写"和"写了但为空"，是配置类数据常用的技巧。
- `violation_budget=0` 默认零容忍。
- `docs_paths_soft` 默认把 `docs/**`、`README.md`、任意 `.md` 视为"软路径"：越界写这些文件只记 `info`。注意这里**单独**列了 `"README.md"`，因为 `fnmatch` 下 `**/*.md` 要求路径里至少有一个 `/`，匹配不到根目录的 `README.md`（见 3.2）。
- ⚠️ 讲义的严重度建议是"docs 越界通常 `warn`，scripts/migrations/生产配置越界一律 `block`"；代码是"docs → `info`，其他越界 → `warn`，只有 forbidden → `block`"，比讲义更宽松。

```python
@dataclass
class RunSummary:
    touched_files: list[str]
    commands_run: list[str]
    elapsed_minutes: float = 0.0
    network_hosts: list[str] = field(default_factory=list)
```

- 讲义说有一个"diff parser"把 touched files + 命令列表变成 `RunSummary`，代码中并没有解析器，`RunSummary` 在 `main()` 里手工构造。真实场景可以用 `git diff --name-only <base>...HEAD` 得到 touched files。
- `commands_run` 只记录"跑了什么命令"，**不记录退出码**——"跑了"不等于"通过了"，这一点由第 37、38 节补上。

```python
@dataclass
class ScopeReport:
    ...
    over_budget: bool

    def passed(self) -> bool:
        return not self.over_budget and not any(f.severity == "block" for f in self.findings)
```

- 通过条件：没超预算，且没有任何 `block`。`info` 永远不影响结果。

### 3.2 glob 匹配：`fnmatch` 的语义陷阱

```python
def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)
```

`fnmatch` 是 shell 风格通配，不是 gitignore 风格的路径 glob：

| 路径 | 模式 | `fnmatch` 结果 | 真 glob（如 `pathlib.full_match`）期望 |
|------|------|---------------|-------------------------------------|
| `lib/foo.py` | `lib/**/*.py` | False | True（`**/` 可匹配零层目录） |
| `lib/a/foo.py` | `lib/**/*.py` | True | True |
| `app/sub/x.py` | `app/*.py` | **True**（`*` 跨越了 `/`） | False |
| `README.md` | `**/*.md` | False | True |
| `docs/a/b.md` | `docs/**` | True | True |

（以上均为实际运行结果。）

- 两个方向都会出错：`**` 规则**过窄**（漏掉直接子文件），单个 `*` 规则**过宽**（跨目录）。对 allowed 来说过宽意味着漏放，对 forbidden 来说过窄意味着漏拦。
- `fnmatch.fnmatch` 还会按操作系统做大小写规范化（Windows 上不区分大小写），`fnmatch.fnmatchcase` 才是严格区分的。
- 生产中可用 `pathlib.PurePosixPath(path).full_match(pattern)`（Python 3.13+）、`pathspec` 库（gitignore 语义）或 `wcmatch`。

### 3.3 最小权限合并

```python
def merge_contracts(parent: ScopeContract, child: ScopeContract) -> ScopeContract:
    return ScopeContract(
        task_id=child.task_id,
        goal=child.goal or parent.goal,
        allowed_files=sorted(set(parent.allowed_files) & set(child.allowed_files)),
        forbidden_files=sorted(set(parent.forbidden_files) | set(child.forbidden_files)),
        acceptance_criteria=list(dict.fromkeys(parent.acceptance_criteria + child.acceptance_criteria)),
        rollback_plan=child.rollback_plan or parent.rollback_plan,
        approvals_required=list(dict.fromkeys(parent.approvals_required + child.approvals_required)),
        time_budget_minutes=_min_optional(parent.time_budget_minutes, child.time_budget_minutes),
        network_egress=_merge_egress(parent.network_egress, child.network_egress),
        violation_budget=min(parent.violation_budget, child.violation_budget),
        docs_paths_soft=sorted(set(parent.docs_paths_soft) | set(child.docs_paths_soft)),
    )
```

逐字段对照讲义：

| 字段 | 合并方式 | 是否符合最小权限 |
|------|---------|----------------|
| `allowed_files` | 字符串集合**交集** | 意图对，实现有漏洞（见下） |
| `forbidden_files` | 并集 | 正确：任一禁止即禁止 |
| `acceptance_criteria` | 拼接去重（保序） | 正确：两边的验收都要跑 |
| `approvals_required` | 拼接去重 | 正确：审批累加 |
| `time_budget_minutes` | 取 min（`None` 服从另一方） | 正确 |
| `network_egress` | `None` 服从另一方，否则交集 | 正确，`[]` 保持 deny-all |
| `violation_budget` | 取 min | 正确 |
| `docs_paths_soft` | **并集** | ⚠️ 过宽：软路径会把越界降级，取并集等于放宽 |
| `goal` / `rollback_plan` | `child or parent` 二选一 | 可接受，但项目级回滚步骤会被丢掉 |

- ⚠️ **glob 字符串求交集的问题**：glob 描述的是路径集合，字符串不相等不代表集合不相交。项目级 `["app.py", "lib/**/*.py"]` 与任务级 `["lib/auth/*.py"]` 合并后 `allowed_files == []`，任务本来合法的 `lib/auth/login.py` 变成越界。demo 中两边都写了字面相同的 `app.py`、`test_app.py`，所以问题没暴露。正确做法是在**路径层面**分别检查两份 allowed 列表再取"与"（测验 Q9）。
- `list(dict.fromkeys(...))`：利用 dict 键唯一且保持插入顺序，实现"保序去重"；`sorted(set(...))` 则是"去重 + 排序"，顺序会变。

```python
def _merge_egress(a, b):
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return sorted(set(a) & set(b))
```

- 实际验证：`_merge_egress(None, []) == []`、`_merge_egress([], ["a"]) == []`、`_merge_egress(["a","b"], ["b","c"]) == ["b"]`。
- 注意 `if a is None` 而不是 `if not a`：后者会把 `[]`（全拒）误当成"未设置"，这是三态字段最常见的 bug。

### 3.4 `scope_check`：四路分类

```python
    for path in run.touched_files:
        if matches_any(path, contract.forbidden_files):
            forbidden.append(path)
        elif matches_any(path, contract.allowed_files):
            in_scope.append(path)
        elif matches_any(path, contract.docs_paths_soft):
            soft_off_scope.append(path)
        else:
            off_scope.append(path)
    missing = [c for c in contract.acceptance_criteria if c not in run.commands_run]
```

- 判断顺序 = 优先级：**forbidden > allowed > 软路径 > 普通越界**。forbidden 先判实现了 "deny overrides allow"。
- `if/elif/else` 保证每个路径只进一个桶。
- `missing`：合同要求的 acceptance 命令中，哪些不在 `commands_run` 里。⚠️ 这是**精确字符串匹配**：合同写 `pytest`，实际跑的是 `python -m pytest`，也会被判"没跑"（已实际验证 `missing == ['pytest']`）。生产中应规范化命令或用命令 ID。

### 3.5 生成 findings 与预算判断

```python
    findings: list[Finding] = []
    if forbidden:
        findings.append(Finding("scope.forbidden", "block", f"forbidden writes: {forbidden}"))
    if off_scope:
        findings.append(Finding("scope.off_scope", "warn", f"off-scope writes: {off_scope}"))
    if soft_off_scope:
        findings.append(Finding("scope.soft_off_scope", "info", f"docs/markdown off-scope: {soft_off_scope}"))
    if missing:
        findings.append(Finding("acceptance.missing", "block", f"acceptance not run: {missing}"))
    if contract.time_budget_minutes is not None and run.elapsed_minutes > contract.time_budget_minutes:
        findings.append(Finding("time.over_budget", "block", ...))
    if contract.network_egress is not None and run.network_hosts:
        bad_hosts = [h for h in run.network_hosts if h not in contract.network_egress]
        if bad_hosts:
            findings.append(Finding("network.unallowed_host", "block", ...))

    warn_count = sum(1 for f in findings if f.severity == "warn")
    over_budget = warn_count > contract.violation_budget
```

| finding code | 严重度 | 触发条件 |
|-------------|--------|---------|
| `scope.forbidden` | block | 写了 forbidden 路径 |
| `scope.off_scope` | warn | 写了既不 allowed 也不是软路径的文件 |
| `scope.soft_off_scope` | info | 越界写了文档类文件 |
| `acceptance.missing` | block | 有验收命令没跑 |
| `time.over_budget` | block | 耗时 **严格大于** 预算（等于时不触发） |
| `network.unallowed_host` | block | 访问了白名单外的主机 |

- 每一类违规**最多一条** finding，文件列表塞在 `detail` 里。
- ⚠️ **预算计数单位的问题**：`warn_count` 数的是 warn 级 finding 的条数，而 warn 只有 `scope.off_scope` 一种，所以 `warn_count ∈ {0, 1}`。结果：预算 0 → 任何越界都失败；预算 ≥ 1 → 越界 1 个和越界 100 个一样通过。实际运行：`allowed=["app.py"]`、预算 1、写了 10 个 `lib/x*.py` → `passed=True`。讲义中的 violation budget 本意是"小的越界在预算内报警，超出拒绝"，应按越界文件数计（测验 Q10）。
- 时间和网络检查都是**事后**检查：讲义说"the runtime refuses to continue past it"，那是运行时强制；这里只是在结束后报告。

### 3.6 归档

```python
def archive(report: ScopeReport) -> Path:
    out = HERE / "closed" / f"{report.task_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({..., "passed": report.passed(), "closed_at": time.time()}, indent=2) + "\n")
    return out
```

- `HERE = Path(__file__).parent`，所以写在 `code/closed/` 下，不是讲义说的 `outputs/scope/closed/`，也没有讲义"Output"里提到的 `scope_report.json`。
- ⚠️ 文件名只用 `task_id`：`main()` 里 clean 和 creep 两份报告的 `task_id` 都是 `T-001`，第二次写入**覆盖**第一次，最终只剩 creep 的记录（已实际验证）。
- `closed_at` 用 `time.time()`，每次运行都不同，输出不可复现。
- `mkdir(parents=True, exist_ok=True)`：目录不存在就递归创建，已存在也不报错。

### 3.7 `main()`：两份合同、两次运行

```python
    project_wide = ScopeContract(task_id="P-PROJECT", ...,
        allowed_files=["app.py", "test_app.py", "lib/**/*.py"],
        forbidden_files=["scripts/release.sh", "config/prod.yaml"],
        time_budget_minutes=60, violation_budget=1,
        network_egress=["api.openai.com", "api.anthropic.com"])
    task = ScopeContract(task_id="T-001", goal="add input validation to /signup",
        allowed_files=["app.py", "test_app.py"], forbidden_files=["migrations/**"],
        acceptance_criteria=["pytest -x test_app.py::test_signup_rejects_short_password"],
        time_budget_minutes=30, violation_budget=0, network_egress=["api.anthropic.com"])
```

合并后的有效合同：allowed `["app.py", "test_app.py"]`（`lib/**/*.py` 被交掉）、forbidden 三条、时间 30、预算 0、网络只允许 `api.anthropic.com`、审批继承项目级的 "any new runtime dependency"。

- `clean`：只改 `app.py`、`test_app.py`，跑了验收命令，12.4 分钟，只访问 anthropic → 无 finding。
- `creep`：改了 `app.py`、`README.md`、`scripts/release.sh`、`migrations/001_init.sql`，没跑验收，42.1 分钟，访问了 `evil.example` → 4 条 block + 1 条 info。
- 注意 creep 中没有一个文件落入"普通越界"，所以 **warn + 预算这条路径在 demo 中从未被触发**。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 合同用 dataclass 表达 | 字段清晰、可 `asdict` 序列化 | 没有 schema 校验（mission 提到的 validator 未实现）；生产用 JSON Schema / pydantic 校验 |
| `fnmatch` 匹配 glob | 标准库、零依赖 | `**`、`*` 语义与 gitignore 不同；生产用 `pathspec` 或 `PurePath.full_match` |
| forbidden 优先 | deny overrides allow | 无 |
| 每类违规合并成一条 finding | 报告简洁 | 预算只能数到 1；应按文件计数或每个文件一条 finding |
| docs 越界记 `info` | 文档改动风险低，避免噪音 | 比讲义（`warn`）更宽松；越界改文档完全"免费" |
| 严重度写死在代码里 | demo 简单 | 讲义要求路径族→严重度的映射写在**合同**里 |
| glob 字符串求交集 | 实现一行 | 语义错误，会错杀合法路径；应路径层面分别匹配 |
| acceptance 精确字符串匹配、只看"跑没跑" | 简单 | 不看退出码；命令写法不同就误判；第 37/38 节补全 |
| 时间、网络事后检查 | 无需接入运行时 | 真正的预算应在运行时强制中断 |
| 归档文件名 = task_id | 一个任务一份记录 | 多次运行互相覆盖；应加 run_id 或用 JSONL 追加 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可以写 `list[str] \| None` 等新语法而不在定义时求值 |
| `@dataclass` | `class ScopeContract:` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `field(default_factory=...)` | `field(default_factory=list)` | 可变默认值必须用工厂，否则所有实例共享同一个列表 |
| `default_factory=lambda: [...]` | `docs_paths_soft` 的默认值 | 用 lambda 返回一个**新的**预填列表 |
| 联合类型 `X \| None` | `time_budget_minutes: int \| None = None` | 可为整数或 `None`（Python 3.10+ 语法） |
| 生成器表达式 + `any` | `any(fnmatch.fnmatch(path, p) for p in patterns)` | 短路求值：遇到第一个 True 就停 |
| 集合运算 | `set(a) & set(b)`、`set(a) \| set(b)` | 交集、并集 |
| 保序去重 | `list(dict.fromkeys(a + b))` | dict 键唯一且保持插入顺序 |
| 列表推导式带条件 | `[c for c in ... if c not in run.commands_run]` | 过滤 |
| `sum` + 生成器计数 | `sum(1 for f in findings if f.severity == "warn")` | 统计满足条件的个数 |
| `is None` 判断 | `if a is None:` | 区分 `None` 与空列表 `[]`（`not []` 也是 True） |
| `or` 取默认值 | `child.goal or parent.goal` | 左边为假值（空串）时取右边 |
| 链式比较条件 | `contract.time_budget_minutes is not None and run.elapsed_minutes > ...` | `and` 短路，先排除 `None` 再比较 |
| f-string 格式符 | `f"elapsed {run.elapsed_minutes:.1f}m"` | 保留 1 位小数 |
| `asdict` | `json.dumps(asdict(effective), indent=2)` | dataclass → dict，便于 JSON 序列化（嵌套 dataclass 也会递归转换） |
| `pathlib` | `HERE / "closed" / f"{...}.json"`、`out.parent.mkdir(parents=True, exist_ok=True)`、`out.write_text(...)` | 用 `/` 拼路径；递归建目录；一次写入文本 |
| `Path(__file__).parent` | `HERE = Path(__file__).parent` | 脚本所在目录，使输出位置与工作目录无关 |
| 方法返回布尔 | `def passed(self) -> bool` | dataclass 里也可以定义普通方法 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时目录副本中执行，退出码 0）：

```text
effective contract: {
  "task_id": "T-001",
  "goal": "add input validation to /signup",
  "allowed_files": ["app.py", "test_app.py"],                        ← lib/**/*.py 被字符串交集去掉
  "forbidden_files": ["config/prod.yaml", "migrations/**", "scripts/release.sh"],   ← 并集
  "acceptance_criteria": ["pytest -x test_app.py::test_signup_rejects_short_password"],
  "rollback_plan": "revert the commit and redeploy the previous build tag",
  "approvals_required": ["any new runtime dependency"],              ← 继承自项目级
  "time_budget_minutes": 30,                                          ← min(60, 30)
  "network_egress": ["api.anthropic.com"],                            ← 交集
  "violation_budget": 0,                                              ← min(1, 0)
  "docs_paths_soft": ["**/*.md", "README.md", "docs/**"]
}
（实际输出中列表是逐行展开的，这里为节省篇幅压成一行）

clean run findings:
  passed=True over_budget=False

creep run findings:
  [block] scope.forbidden: forbidden writes: ['scripts/release.sh', 'migrations/001_init.sql']
  [info] scope.soft_off_scope: docs/markdown off-scope: ['README.md']
  [block] acceptance.missing: acceptance not run: ['pytest -x test_app.py::test_signup_rejects_short_password']
  [block] time.over_budget: elapsed 42.1m > budget 30m
  [block] network.unallowed_host: egress to non-allowlisted hosts: ['evil.example']
  passed=False over_budget=False

archived under closed/
```

逐项解读：

- **有效合同**：每个字段都可以按 3.3 节的表格手工推出来。`sorted(set(...))` 让 forbidden 和软路径按字母排序，所以顺序与原始定义不同。
- **clean 运行**：没有任何 finding（for 循环不打印），`passed=True`。
- **creep 运行**：
  - `scripts/release.sh` 来自项目级 forbidden、`migrations/001_init.sql` 匹配任务级 `migrations/**`，合并为一条 block；
  - `README.md` 不在 allowed 里，但命中软路径，只是 `info`——这正是讲义"docs 软失败"的思路（但讲义建议 `warn`）；
  - 验收命令没跑、超时（42.1 > 30）、访问 `evil.example`，各一条 block；
  - `over_budget=False`：没有 warn 级 finding，`0 > 0` 为假；失败完全由 block 造成。
- **归档**：`code/closed/` 里只有 `T-001.json` 一个文件，内容是 creep 运行（`"passed": false`），clean 运行的记录被覆盖了。注意运行脚本会在课程目录内生成这个 `closed/` 目录。
- **与讲义的出入**：讲义说输出"the contract, the two runs, the per-run verdicts, and a saved `scope_report.json`"——前三项有，`scope_report.json` 没有。讲义还说"The checker flags the creep with the exact file and reason"，代码确实在 `detail` 中给出了文件列表和原因。

---

## 7. 动手改一改

1. **讲义练习 2（严重度分层）**：在合同中加入 `severity_by_path: dict[str, str]`（如 `{"docs/**": "warn", "scripts/**": "block", "migrations/**": "block"}`），越界路径按首个命中的模式定严重度；并把 violation budget 改成按越界文件数计（参考测验 Q10）。
2. **换掉 `fnmatch`**：用 `pathlib.PurePosixPath(p).full_match(pattern)`（Python 3.13+）重写 `matches_any`，验证 `lib/foo.py` 能匹配 `lib/**/*.py`、`app/sub/x.py` 不再匹配 `app/*.py`。
3. **修复合并**：把 `allowed_files` 合并改成"路径层面两份都允许"，例如合并结果保存 `allowed_all_of: list[list[str]]`；把 `docs_paths_soft` 改为交集。为合并写一个性质测试：对任意路径，合并合同允许 ⇒ 两份原合同都允许。
4. **讲义练习 1/4（网络与时间）**：代码已有事后检查，改成运行时强制——写一个 `Budget` 上下文管理器，在 agent 循环每一步前检查 `time.monotonic()`，超时抛异常；网络请求经过一个检查 host 的包装函数。
5. **修复归档**：文件名改为 `closed/{task_id}/{run_id}.json`，或追加写入 `closed/{task_id}.jsonl`；把 `closed_at` 改为可注入的时钟，便于测试。
6. **讲义练习 3（从 goal 推导 allowed）**：用静态规则（如 "signup" → `app.py`, `tests/test_signup*.py`）从 `goal` 推 `allowed_files`，找出第一个失败的例子（同义词、跨模块改动、测试文件命名不一致），体会为什么 skill 要求"任务描述不限定区域时拒绝推导"。

---

## 8. 常见坑

- **把 `fnmatch` 当 gitignore glob 用**：`**` 不能匹配零层目录、`*` 会跨 `/`。同时检查 allowed（过宽 → 漏放）和 forbidden（过窄 → 漏拦）两个方向。
- **对 glob 字符串做集合运算**：字符串交集 ≠ 路径集合交集。
- **用 `if not x` 判断三态字段**：`network_egress=[]`（全拒）会被当成"没设置"。必须用 `is None`。
- **以为"跑了验收命令"等于"验收通过"**：`commands_run` 没有退出码；还要求命令字符串精确一致。
- **预算单位不清**：数 finding 还是数文件，结果天差地别；预算 ≥ 1 时本代码对越界几乎不设防。
- **软路径越加越多**：`**/*.md` 会把任何目录下的 Markdown（包括 `prompts/*.md`、`AGENTS.md` 这类会影响 agent 行为的文件）降级为 info。高影响的 Markdown 文件应显式列进 forbidden 或 allowed。
- **归档覆盖**：同一个 task 多次运行只保留最后一次，审计时会丢失证据。
- **在课程目录里直接运行**：脚本会在 `code/closed/` 写文件；只想看输出时可以复制到临时目录运行。
