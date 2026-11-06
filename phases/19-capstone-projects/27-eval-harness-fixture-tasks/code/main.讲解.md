# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 27 节 使用固定测试任务的评估 Harness（Eval Harness with Fixture Tasks） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 下），或在小节根目录运行 `python3 code/main.py`；测试：`python3 -m pytest tests/ -v` 或 `python3 -m unittest discover tests` ｜ **依赖**：只用标准库（`json`、`os`、`re`、`shutil`、`statistics`、`subprocess`、`tempfile`、`time`、`dataclasses`、`typing`）；运行测试需要 `pytest`（也可直接用标准库 `unittest`），`shell_exit_zero` 的单元测试依赖 POSIX 的 `true` / `false` 命令
>
> 本讲解同时覆盖 `tasks/` 下 5 个夹具任务（10 个 `.py` 文件 + 5 个 `task.json`，见 3.9 节）以及 `tests/test_main.py`（见第 9 节）。夹具文件只有 2～15 行，是"被评测的数据"而不是程序逻辑，所以不单独写讲解。

---

## 1. 这份代码在考察什么

这是一个**给 coding agent 打分的评测框架（eval harness）**。它不包含任何 LLM，考察的是"怎样把'agent 修好了 bug'变成一个可复现、可比较的数字"：

1. **夹具任务（fixture task）的结构**：讲义把任务定义为 goal + setup + verifier 三元组，代码落地为目录约定 `task.json` + `buggy/` + `expected/`。
2. **确定性 verifier**：`file_equals`、`regex_match`、`shell_exit_zero` 三种判定方式，以及用注册表按名字分派。
3. **候选者协议（candidate protocol）**：harness 只认 `Callable[[FixtureTask, str], SampleResult]`，agent 的内部实现可以随意替换。
4. **采样隔离**：每个 sample 都用全新的临时目录，保证 k 次采样相互独立。
5. **指标聚合**：pass@1、pass@k（`1 - (1-p)^k`）、平均与 p95 延迟、成本。
6. **Harness 自测**：参考 candidate 必须全部通过、noop candidate 必须全部失败，用来证明 harness 和夹具本身没问题。

> 一句话：**评测的可信度来自"确定性的判定 + 隔离的采样 + 固定的任务集"**。这份代码把骨架搭得很清楚，但 verifier 的误判、延迟自报、异常处理、pass@k 口径等地方都做了简化，读代码时要把这些"简化点"当作重点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `FixtureTask` | dataclass | 一个评测任务：id、goal、buggy/expected 目录、verifier 名字与参数 | fixture task |
| `SampleResult` | dataclass | candidate 一次运行的自报结果：延迟、成本、备注 | 候选者协议的返回值 |
| `VerificationOutcome` | dataclass | verifier 的判定：`passed` + `detail` | 确定性判定 |
| `TaskReport` / `EvalReport` | dataclass | 每任务 / 全局的聚合结果，带 `to_dict()` | 结构化报告 |
| `pass_at_k` / `p95` | 函数 | 计算 pass@k、95 分位延迟 | 指标 |
| `verify_file_equals` / `verify_regex_match` / `verify_shell_exit_zero` | 函数 | 三种内置 verifier | verifier |
| `VERIFIER_REGISTRY` | dict | verifier 名字 → 函数 | 注册表分派 |
| `load_fixture` / `load_all_fixtures` | 函数 | 从目录读取 `task.json`，按名字排序加载全部夹具 | 固定、可复现的任务集 |
| `apply_known_fixes` | 函数（candidate） | 把 `expected/` 拷进 scratch 目录：参考答案 | harness 自测（应得 1.0） |
| `noop_candidate` | 函数（candidate） | 什么都不做 | harness 自测（应得 0.0） |
| `EvalHarness` | dataclass | 准备 scratch → 跑 candidate → 验证 → 聚合 | harness 主体 |
| `run_demo` | 函数 | 加载夹具、跑两种 candidate、打印 JSON、校验结果、返回退出码 | demo / 自测入口 |
| `tasks/task_00X_*/` | 数据目录 | 5 个夹具：`task.json` + `buggy/*.py` + `expected/*.py` | 评测集 |

数据流：`run_demo` → `load_all_fixtures(tasks/)` 得到 5 个 `FixtureTask` → `EvalHarness(k).run(candidate)`：对每个任务 × 每个 sample 执行 `_prepare_scratch`（复制 buggy）→ `candidate(task, scratch)` → `_verify`（查注册表、调 verifier）→ 记录 → `rmtree` → 汇总成 `TaskReport` → 汇总成 `EvalReport` → `json.dumps` 打印 → 检查 pass@1 → `sys.exit(返回码)`。

---

## 3. 逐段精讲

### 3.1 数据类：任务、样本、判定、报告

```python
@dataclass
class FixtureTask:
    """A single evaluation task."""

    id: str
    goal: str
    setup_dir: str
    expected_dir: str
    verifier_name: str
    verifier_args: dict[str, Any]
    root: str = ""
```

- `setup_dir` 指向 `buggy/`，`expected_dir` 指向 `expected/`，`verifier_name` + `verifier_args` 来自 `task.json` 的 `verifier` 块。`goal` 是要交给 agent 的 prompt，但**整个 harness 中没有任何地方使用它**（参考 candidate 不需要读 goal），真实 LLM candidate 才会用到。
- `to_dict()` 只导出 id / goal / verifier，在本文件中没有被调用。

```python
@dataclass
class SampleResult:
    task_id: str
    sample_index: int
    latency_ms: float
    cost_units: float = 0.0
    notes: str = ""
```

- 这是 candidate 必须返回的"回执"。注意它**没有 `passed` 字段**：是否通过只由 verifier 决定，不信任 agent 的自我声明——这正是讲义第一个失败模式 "unverified pass" 的对策。
- ⚠️ 与讲义不一致：讲义说 SampleResult 包含 `success_self_reported, latency_ms, cost_units, edits`，代码中是 `task_id, sample_index, latency_ms, cost_units, notes`。代码的选择（不要自报成功）其实更合理。
- ⚠️ 两个 candidate 都把 `sample_index` 写死为 0，harness 也从不读取它（报告里的 `sample_index` 是 harness 自己的循环变量），这个字段实际上没有用处。

```python
@dataclass
class TaskReport:
    task_id: str
    k: int
    passes: int
    pass_rate: float
    pass_at_k: float
    mean_latency_ms: float
    p95_latency_ms: float
    mean_cost: float
    samples: list[dict] = field(default_factory=list)
```

- `samples` 用 `field(default_factory=list)`：可变默认值必须这样写，否则所有实例会共享同一个列表（dataclass 会直接报错，禁止写 `= []`）。
- `to_dict()` 中用 `round(..., 4)` / `round(..., 3)` 控制 JSON 输出精度。
- `EvalReport` 的字段为 `k / pass_at_1 / pass_at_k / mean_latency_ms / p95_latency_ms / total_cost / tasks`。⚠️ 讲义架构图里写的是 "total tasks / mean cost"，代码给的是 `total_cost`，也没有任务总数字段（只能数 `tasks` 列表）。

### 3.2 pass@k 与 p95

```python
def pass_at_k(empirical_pass_rate: float, k: int) -> float:
    """Probability of at least one pass in k independent samples."""

    if k <= 0:
        return 0.0
    p = max(0.0, min(1.0, empirical_pass_rate))
    return 1.0 - (1.0 - p) ** k
```

- 思路：单次失败概率为 `1-p`，k 次独立采样全部失败的概率为 `(1-p)^k`，取补集即"至少一次成功"。
- `max(0.0, min(1.0, x))` 把输入**夹紧（clamp）**到 [0, 1]，防止调用方传入非法值（测试 `test_clamps_out_of_range` 专门验证这一点）。
- 数值示例（已实际计算）：p = 0.6 时 k = 1、2、3、5、10 分别为 0.6、0.84、0.936、0.9898、0.9999；p = 0.05 时 pass@20 ≈ 0.6415。
- ⚠️ **口径问题**：这是用经验通过率 p̂ 代入的 plug-in 估计。HumanEval 论文（Chen et al., 2021）使用的无偏估计是 `1 - C(n-c,k)/C(n,k)`（n 次采样、c 次通过）。由于 `(1-x)^k` 是凸函数，plug-in 估计**系统性偏低**。本 harness 恰好采样 k 次再按同一个 k 计算，偏差最大：例如 5 次中通过 1 次，plug-in 给出 0.6723，而"5 次中至少通过一次"的直接观测（以及无偏估计）是 1.0。详见测验 Q11。
- ⚠️ 讲义说 "A pass@1 of 0.6 … A pass@5 of 0.95"，但按讲义自己的公式，p = 0.6 时 pass@5 = 0.98976，0.95 只是示意数字。

```python
def p95(values: list[float]) -> float:
    """Sample 95th percentile via nearest-rank."""

    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = max(0, int(round(0.95 * len(sorted_values))) - 1)
    return sorted_values[min(idx, len(sorted_values) - 1)]
```

- 先排序，再取第 `round(0.95·n)` 个值（下标减 1）。只返回实际出现过的值，不做插值。
- ⚠️ 自称 "nearest-rank"，但标准 nearest-rank 用的是**向上取整** `ceil(0.95·n)`。用 `round` 会在部分 n 上取低一档（已实测）：

| n | 0.95·n | 代码返回第几小 | ceil 版返回第几小 |
|---|--------|---------------|------------------|
| 19 | 18.05 | 18 | 19 |
| 20 | 19.0 | 19 | 19 |
| 30 | 28.5 | 28（银行家舍入，`round(28.5)=28`） | 29 |
| 70 | 66.5 | 66 | 67 |
| 100 | 95.0 | 95 | 95 |

  对 n 较大的延迟统计影响不大，但测试只覆盖了 n = 20 这种"整好"的情况，没有暴露问题。修正：`idx = math.ceil(0.95 * n) - 1`。

### 3.3 Verifier 1：`file_equals`

```python
def verify_file_equals(task, scratch_dir, args) -> VerificationOutcome:
    rel = args.get("path")
    if not isinstance(rel, str):
        return VerificationOutcome(False, "verifier args missing 'path'")
    actual = os.path.join(scratch_dir, rel)
    expected = os.path.join(task.expected_dir, rel)
    ...
    normalize = bool(args.get("normalize_trailing_newline", True))
    if normalize:
        actual_text = actual_text.rstrip("\n") + "\n"
        expected_text = expected_text.rstrip("\n") + "\n"
    if actual_text == expected_text:
        return VerificationOutcome(True, f"file {rel!r} matches expected")
    return VerificationOutcome(False, f"file {rel!r} differs from expected")
```

- 对 scratch 中的文件和 `expected/` 中的同名文件做**逐字比较**，唯一的宽容是统一末尾换行（默认开启，可用 `normalize_trailing_newline: false` 关闭）。
- 所有错误情况（缺参数、缺文件）都**返回失败而不是抛异常**：verifier 永远给出 true/false + 原因，这是"确定性 verifier"的好习惯。
- 适用场景：讲义说它适合 "fix this bug in this exact way" 类任务，例如 task_003 修拼写。
- ⚠️ 风险是**误杀**：`range(1, n+1)`（少了空格）或用 `count = 1` 的等价修法都会失败（已实测，见测验 Q9）。不处理 `\r\n`，Windows 换行也会被判不同。
- ⚠️ `rel` 没有做路径校验，`../` 之类的路径可以读到 scratch 目录之外的文件；夹具由作者编写时问题不大，但若 verifier 参数来自不受信任的来源就需要限制。

### 3.4 Verifier 2：`regex_match`

```python
    if re.search(pattern, text, re.MULTILINE):
        return VerificationOutcome(True, f"file {rel!r} matched {pattern!r}")
    return VerificationOutcome(False, f"file {rel!r} did not match {pattern!r}")
```

- `re.search` 在全文任意位置查找；`re.MULTILINE` 让 `^` / `$` 匹配**每一行**的开头和结尾，而不只是整个字符串的开头和结尾。
- 讲义："the function must exist and return X" 类任务，有多种可接受写法时使用。
- ⚠️ 风险是**误放**：正则只看文本，不看语义和结构。实测：
  - task_002 中把 `return result` 缩进进 `for` 循环，`factorial(5)` 返回 2，却能匹配 `^\s*return\s+result\s*$`；
  - task_004 中 `return sorted(items)[::-1]`（结果错误）和注释 `# return items[::-1]`（函数仍返回 None）都能匹配。
- 同时也会**误杀**：`return result * 1`、`return (result)`、`out.reverse(); return out` 都不匹配。

### 3.5 Verifier 3：`shell_exit_zero`

```python
    argv = args.get("argv")
    if not isinstance(argv, list) or not argv:
        return VerificationOutcome(False, "verifier args need 'argv' list")
    timeout = float(args.get("timeout_seconds", 10.0))
    try:
        proc = subprocess.run(
            list(argv),
            cwd=scratch_dir,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return VerificationOutcome(False, "shell command timed out")
    except FileNotFoundError as exc:
        return VerificationOutcome(False, f"shell command not found: {exc}")
    if proc.returncode == 0:
        return VerificationOutcome(True, "command exited zero")
    return VerificationOutcome(False, f"command exited {proc.returncode}")
```

- 用**参数列表**（argv）而不是字符串调用、不经过 shell（`shell=False` 是默认值），避免命令注入和引号转义问题。
- `cwd=scratch_dir`：命令在 agent 的工作目录里执行，所以 `python3 -c "from linked_list import ..."` 能直接导入 scratch 中的文件。
- `capture_output=True` 收集 stdout/stderr，防止刷屏；`check=False` 表示非零退出码不抛异常，由代码自己判断；超时和命令不存在都转换成"失败"。
- 讲义："This catches 'the tests must pass' tasks." 这是唯一检验**行为**的 verifier，最接近"真的修好了"。
- ⚠️ 讲义说它会 "through the sandbox from lesson 26"，而代码直接调用 `subprocess.run`，没有拒绝列表、没有资源限制（docstring 承认了这一点）。
- ⚠️ 收集到的 stdout/stderr 被丢弃，失败时 `detail` 只有 "command exited 1"，排查时看不到断言信息。可以把 `proc.stderr` 的最后几行写进 `detail`。
- ⚠️ 5 个内置夹具**没有一个**使用 `shell_exit_zero`，它只在单元测试中被覆盖。

### 3.6 注册表与夹具加载

```python
VERIFIER_REGISTRY: dict[str, Verifier] = {
    "file_equals": verify_file_equals,
    "regex_match": verify_regex_match,
    "shell_exit_zero": verify_shell_exit_zero,
}
```

- `Verifier = Callable[[FixtureTask, str, dict[str, Any]], VerificationOutcome]` 是**类型别名**，统一三个函数的签名。夹具 JSON 只写名字，新增 verifier 只需写一个函数并注册，不用改 harness 主循环（开闭原则）。

```python
def load_fixture(task_dir: str) -> FixtureTask:
    spec_path = os.path.join(task_dir, "task.json")
    with open(spec_path, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    setup = os.path.join(task_dir, "buggy")
    expected = os.path.join(task_dir, "expected")
    return FixtureTask(
        id=spec["id"],
        goal=spec["goal"],
        setup_dir=setup,
        expected_dir=expected,
        verifier_name=spec["verifier"]["name"],
        verifier_args=spec["verifier"].get("args", {}),
        root=task_dir,
    )


def load_all_fixtures(tasks_root: str) -> list[FixtureTask]:
    tasks: list[FixtureTask] = []
    for name in sorted(os.listdir(tasks_root)):
        ...
```

- `setup` / `expected` 目录是**约定的固定名字**，不从 JSON 读取。⚠️ 讲义说 JSON 中有一个 `setup` 块（"files to drop into the scratch dir"），实际的 `task.json` 和代码都没有这个块。
- `sorted(os.listdir(...))`：`os.listdir` 的顺序取决于文件系统，排序后任务顺序固定——对应讲义 "in a reproducible order"。
- 只加载含 `task.json` 的子目录，其它目录被静默忽略。
- ⚠️ 加载时不校验 verifier 名字是否存在、参数是否齐全，也不检查目录名与 `id` 是否一致（task_00X 两者恰好相同）。拼错的 verifier 要到运行时才变成"失败"，容易被误读为 agent 能力差。
- ⚠️ 讲义第三个失败模式 "per-task drift"（任务被改名导致集合不同）在代码中并没有专门处理：报告只列出 task_id，没有任务集指纹（如内容哈希），需要外部脚本自行对比。

### 3.7 两个内置 candidate

```python
def apply_known_fixes(task: FixtureTask, scratch_dir: str) -> SampleResult:
    start = time.perf_counter()
    if os.path.isdir(task.expected_dir):
        for dirpath, _dirs, files in os.walk(task.expected_dir):
            rel = os.path.relpath(dirpath, task.expected_dir)
            dst_root = scratch_dir if rel == "." else os.path.join(scratch_dir, rel)
            os.makedirs(dst_root, exist_ok=True)
            for filename in files:
                shutil.copy2(os.path.join(dirpath, filename), os.path.join(dst_root, filename))
    elapsed = (time.perf_counter() - start) * 1000.0
    return SampleResult(task_id=task.id, sample_index=0, latency_ms=elapsed,
                        cost_units=1.0, notes="reference candidate")
```

- 参考 candidate 直接把**标准答案**拷进工作目录，相当于一个"神谕（oracle）"，只用于 harness 自测：如果它都过不了，说明 verifier 或夹具写错了。
- `os.walk` 递归遍历；`os.path.relpath` 算出相对路径，`rel == "."` 表示根目录；`makedirs(exist_ok=True)` 在目标处重建子目录结构；`shutil.copy2` 复制内容和元数据（修改时间等）。
- `cost_units=1.0` 是假定的成本，所以 demo 中 5 个任务的 `total_cost` = 5.0。
- ⚠️ 它能这样"作弊"，是因为 candidate 拿到的是**完整的 `FixtureTask`**（包括 `expected_dir` 路径和 regex pattern）。真实 LLM agent 如果能读文件系统，同样可以读到答案——这是评测设计中的**答案泄漏**问题。生产中应只给 agent goal 和工作目录。
- `noop_candidate`：计时后立刻返回，cost 为 0。⚠️ 它内部的 `start` / `elapsed` 什么也没包住，延迟约为 0，只是保持接口形状一致。

### 3.8 `EvalHarness`：主循环

```python
@dataclass
class EvalHarness:
    tasks: list[FixtureTask]
    k: int = 1
    verifier_registry: dict[str, Verifier] = field(
        default_factory=lambda: dict(VERIFIER_REGISTRY)
    )
```

- `default_factory=lambda: dict(VERIFIER_REGISTRY)`：每个 harness 实例拿到注册表的**一份拷贝**，在某个实例上注册自定义 verifier 不会污染全局表。

```python
    def _verify(self, task, scratch_dir):
        verifier = self.verifier_registry.get(task.verifier_name)
        if verifier is None:
            return VerificationOutcome(False, f"unknown verifier {task.verifier_name!r}")
        return verifier(task, scratch_dir, task.verifier_args)

    def _prepare_scratch(self, task):
        scratch = tempfile.mkdtemp(prefix=f"eval-{task.id}-")
        ...  # 与 apply_known_fixes 相同的 os.walk + copy2，把 buggy/ 复制进来
        return scratch
```

- 未知 verifier 返回失败而不是抛 `KeyError`（已实测：`detail` 为 `unknown verifier 'pytest_passes'`）。
- `tempfile.mkdtemp(prefix=...)` 在系统临时目录下创建一个唯一的新目录，例如 `/tmp/eval-task_001_fizzbuzz_offbyone-xxxx`；前缀带任务 ID，方便调试时识别。
- 复制 `buggy/` 的代码与 `apply_known_fixes` 几乎一模一样，可以抽成一个 `_copy_tree(src, dst)` 辅助函数（或用 `shutil.copytree(src, dst, dirs_exist_ok=True)`）。

```python
    def run(self, candidate: Candidate) -> EvalReport:
        task_reports: list[TaskReport] = []
        for task in self.tasks:
            samples, latencies, costs, passes = [], [], [], 0
            for sample_index in range(self.k):
                scratch = self._prepare_scratch(task)
                try:
                    sample = candidate(task, scratch)
                    outcome = self._verify(task, scratch)
                    latencies.append(sample.latency_ms)
                    costs.append(sample.cost_units)
                    if outcome.passed:
                        passes += 1
                    samples.append({...})
                finally:
                    shutil.rmtree(scratch, ignore_errors=True)
            pass_rate = passes / self.k if self.k else 0.0
            task_reports.append(TaskReport(..., pass_at_k=pass_at_k(pass_rate, self.k), ...))
```

（为节省篇幅，`samples` 等的初始化合并成了一行，原代码是分行写的。）

- **每个 sample 都有新的 scratch**：k 次采样都从 buggy 状态开始，彼此独立。如果复用目录，第 2 次 sample 会在第 1 次的产出上继续，pass rate 会被抬高。
- `try/finally` 保证无论成功与否都删除临时目录，`ignore_errors=True` 让清理失败不掩盖真正的错误。
- 一个 sample 的完整记录：`sample_index / latency_ms / cost_units / passed / detail / notes`，`detail` 让人能回答"为什么失败"。
- ⚠️ **没有 `except`**：candidate 抛出的异常会终止整个 `run`，已完成任务的结果全部丢失（实测抛出 `RuntimeError`）。真实 LLM agent 的网络错误、解析错误几乎一定会发生，应当捕获后记为失败（测验 Q10 给出了 `_run_one` 实现）。也没有给 candidate 设置超时。
- ⚠️ **延迟是自报的**：`latencies.append(sample.latency_ms)`，harness 自己不计时。实测一个 `sleep(0.05)` 却报告 0.001 ms 的 candidate，报告里就是 0.001。讲义说 "Latency is wall-clock per sample"，应由 harness 在调用前后用 `perf_counter` 计时。
- ⚠️ 所有任务、所有 sample **串行执行**，任务多、agent 慢时需要并行。

```python
        per_sample_pass_at_1 = [
            (1.0 if r.passes > 0 else 0.0)
            if r.k == 1
            else min(1.0, r.pass_rate)
            for r in task_reports
        ]
        pass_at_1_value = statistics.mean(per_sample_pass_at_1) if per_sample_pass_at_1 else 0.0
        pass_at_k_value = statistics.mean([r.pass_at_k for r in task_reports]) if task_reports else 0.0
        all_latencies = [float(s["latency_ms"]) for r in task_reports for s in r.samples]
        total_cost = sum(float(s["cost_units"]) for r in task_reports for s in r.samples)
```

- **全局 pass@1 = 各任务 pass_rate 的平均**（"宏平均"，每个任务权重相同）。k = 1 时 `passes > 0` 等价于 `pass_rate == 1`；k > 1 时 `min(1.0, pass_rate)` 中的 `min` 也是多余的——两个分支的结果都等于 `pass_rate`，整段可以简化为 `[r.pass_rate for r in task_reports]`。
- **全局 pass@k = 各任务 pass@k 的平均**。
- `all_latencies` 是**嵌套推导式**：外层遍历任务，内层遍历该任务的 samples。⚠️ 它读取的是已经 `round(..., 3)` 过的值，全局延迟统计会带一点舍入误差。
- `total_cost` 用**生成器表达式**直接求和，不需要先建列表。

### 3.9 夹具任务（`tasks/`）逐个说明

每个夹具都是：`task.json`（id、goal、verifier）+ `buggy/<文件>.py`（agent 的起点）+ `expected/<文件>.py`（参考答案）。下表中的"buggy 行为"和"expected 行为"都已实际运行验证：

| 任务 | 文件 | bug（diff） | buggy 行为 | expected 行为 | verifier |
|------|------|------------|-----------|--------------|---------|
| task_001_fizzbuzz_offbyone | `fizzbuzz.py`（10 行） | `range(1, n)` → `range(1, n + 1)` | `fizzbuzz(5)` 打印 `1, 2, Fizz, 4`，少了最后的 `Buzz` | 打印 `1, 2, Fizz, 4, Buzz` | `file_equals` |
| task_002_factorial_missing_return | `factorial.py`（4 → 5 行） | 末尾补 `return result` | `factorial(5)` 返回 `None` | 返回 `120` | `regex_match`：`^\s*return\s+result\s*$` |
| task_003_error_message_typo | `errors.py`（3 行） | `recieved` → `received` | `str(BadInputError(3))` 为 `recieved unexpected value: 3` | `received unexpected value: 3` | `file_equals` |
| task_004_empty_reverse | `reverse.py`（2 行） | `pass` → `return items[::-1]` | `reverse_list([1,2,3])` 返回 `None` | 返回 `[3, 2, 1]` | `regex_match`：`return\s+(.+\[::-1\]|list\(reversed\(.+\)\))` |
| task_005_linked_list_traversal | `linked_list.py`（15 行） | `node = head.nxt` → `node = head` | 3 个节点返回 2，单节点返回 0 | 返回 3 / 1，空链表 0 | `file_equals` |

各夹具涉及的 Python 知识和设计要点：

- **task_001**：`range(a, b)` 是左闭右开区间，`range(1, n)` 只到 n−1，这是最经典的 off-by-one（差一）错误。`if i % 15 == 0` 必须放在 `% 3`、`% 5` 之前，否则 15 会先被判成 Fizz。
- **task_002**：Python 函数没有 `return` 时隐式返回 `None`。regex verifier 允许 `return result` 前有任意缩进，因此也会放过"放进循环体里"的错误写法。
- **task_003**：`f"...{value!r}"` 中 `!r` 表示用 `repr()` 格式化（字符串会带引号）；`super().__init__(msg)` 把消息交给 `Exception`，`str(exc)` 即为该消息。拼写修复只有一种正确写法，适合用 `file_equals`。
- **task_004**：`items[::-1]` 是步长为 −1 的切片，返回一个**新的**反转列表，不修改原列表；`list(reversed(items))` 等价。`items.reverse()` 是原地反转并返回 `None`，`return items.reverse()` 是常见错误（regex 也确实不会匹配它）。⚠️ goal 中说 "verify with the bundled assertion"，但这个夹具**没有附带任何断言或测试**，verifier 只是一个正则。
- **task_005**：`Node` 用 `nxt` 而不是 `next` 作为属性名，避免与内置函数 `next` 同名造成混淆。`while node is not None` 遍历链表，与 `None` 比较要用 `is`。⚠️ goal 说 "Fix it by initialising the counter to 0"，但 buggy 代码里 `count` **本来就是 0**，真正要改的是起始节点；而用 `count = 1` 修复（功能正确）会被 `file_equals` 判失败。
- ⚠️ 讲义描述 task_004 为 "empty function body"，buggy 版本其实是 `pass`，严格说不是空函数体（Python 不允许真正的空函数体），而是"什么都不做、返回 None"。

总体来看，5 个夹具里 3 个用 `file_equals`、2 个用 `regex_match`，**没有一个真正运行代码**。这使得 harness 的自测非常稳定，但也意味着它测量的是"是否写出了和参考答案一样（或像）的文本"，而不是"bug 是否真的修好了"。生产评测（如讲义先修中的 SWE-bench）以运行测试为主。

### 3.10 `run_demo` 与入口

```python
def _tasks_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")
```

- 用 `__file__` 的绝对路径定位 `tasks/`，所以无论在 `code/` 下运行还是在小节根目录运行 `python3 code/main.py`，都能找到夹具（两种方式都已实测）。

```python
    harness = EvalHarness(tasks=tasks, k=1)
    report = harness.run(apply_known_fixes)
    print(json.dumps(report.to_dict(), indent=2))
    if report.pass_at_1 < 1.0:
        print(..., file=sys.stderr)
        return 1
    ...
    harness_noop = EvalHarness(tasks=tasks, k=3)
    noop_report = harness_noop.run(noop_candidate)
    ...
    if noop_report.pass_at_1 > 0.0:
        ...
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(run_demo())
```

- 这是一个**双向自测**：参考答案必须全部通过（verifier 不误杀标准答案），什么都不做必须全部失败（夹具不是白送分的）。任一条件不满足，进程以退出码 1 结束，可以直接放进 CI。
- 错误信息写到 `sys.stderr`，正常报告写到 stdout，便于用管道把 JSON 交给其它脚本。
- ⚠️ 讲义说 demo 会打印 "pass@1, pass@5"，实际 demo 只跑了 k = 1（参考）和 k = 3（noop），从没有计算 pass@5。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用标准库、无 LLM | 可复现、零依赖，专注 harness 本身 | 真实 candidate 需要接入 LLM agent，带来随机性、超时和费用 |
| 夹具 = `task.json` + `buggy/` + `expected/` 目录约定 | 结构简单，便于人工增删任务 | 讲义中的 `setup` 块没有实现；生产中通常还会有隐藏测试目录和环境描述 |
| `SampleResult` 不含"是否成功" | 不信任 agent 自报，只信 verifier | 合理；但延迟和成本仍然是自报的，应由 harness 测量 |
| 三种 verifier + 注册表 | 覆盖"精确修改 / 多种写法 / 行为正确"三类任务；可扩展 | `file_equals` 易误杀、`regex_match` 易误放；生产以运行测试为主，并在 sandbox 中执行 |
| verifier 出错返回失败而非抛异常 | 报告永远完整，失败有原因 | 配置错误与能力不足混在一起；应在加载阶段校验 |
| 每个 sample 一个新的 `mkdtemp` 目录 | 保证 k 次采样独立 | 大仓库复制开销大；生产用容器快照或写时复制 |
| plug-in pass@k `1-(1-p)^k` | 公式简单直观 | 系统性偏低，与 HumanEval 口径不同；应使用无偏估计并报告 c/n |
| p95 用 `round` 取秩 | 实现简短 | 部分 n 下比标准 nearest-rank 低一档；改用 `ceil` 或 `statistics.quantiles` |
| 串行执行、无异常捕获、无超时 | 代码短小、易读 | 一个 candidate 崩溃或卡死会拖垮整轮评测；生产需并行、捕获异常、设预算 |
| candidate 拿到完整 `FixtureTask` | 参考 candidate 需要 `expected_dir` | 真实 agent 可以偷看答案；应只传 goal 和工作目录 |
| 参考 / noop 双向自测 | 一次性验证 harness、verifier、夹具 | 只能证明"不改不过、标准答案能过"，不能证明"改错了也不过" |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟类型注解的求值，可以在旧版本 Python 中写 `list[dict]`、引用尚未定义的类型 |
| `@dataclass` | `class FixtureTask:`、`class EvalHarness:` | 根据类型注解自动生成 `__init__`、`__repr__`、`__eq__` |
| 带默认值的字段 | `root: str = ""`、`k: int = 1` | 有默认值的字段必须写在无默认值字段之后 |
| `field(default_factory=...)` | `field(default_factory=list)`、`field(default_factory=lambda: dict(VERIFIER_REGISTRY))` | 可变默认值必须用工厂函数，每个实例各得一份 |
| 类型注解与内置泛型 | `dict[str, Any]`、`list[FixtureTask]`、`-> VerificationOutcome` | 只是提示，运行时不检查 |
| `typing.Callable` 类型别名 | `Candidate = Callable[[FixtureTask, str], SampleResult]` | 描述"接收哪些参数、返回什么"的函数类型；给它起个名字更易读 |
| 函数作为参数 / 字典值 | `harness.run(apply_known_fixes)`、`VERIFIER_REGISTRY["file_equals"]` | Python 中函数是一等对象，可以传递、存入字典 |
| `lambda` | `lambda: dict(VERIFIER_REGISTRY)` | 匿名函数，这里无参数，返回注册表的拷贝 |
| `dict.get(key, default)` | `args.get("timeout_seconds", 10.0)`、`registry.get(name)` | 键不存在时返回默认值（或 `None`），不抛 `KeyError` |
| `isinstance` 防御式检查 | `if not isinstance(rel, str):` | 校验来自 JSON 的参数类型 |
| f-string 与转换符 | `f"file {rel!r} matches expected"`、`f"{value!r}"` | `!r` 调用 `repr()`，字符串会带引号 |
| f-string 宽度格式 | `f"  - {t.id:32s} verifier=..."` | `:32s` 左对齐、宽度 32；id 超过 32 个字符时不会截断（task_002 的 id 有 33 个字符，所以输出中对不齐） |
| `with open(...) as fh` | 读取 `task.json` 和源文件 | 上下文管理器，离开代码块时自动关闭文件；显式指定 `encoding="utf-8"` |
| `json.load` / `json.dumps(indent=2)` | 加载夹具、打印报告 | JSON 与 dict 互相转换；`indent` 美化输出 |
| `re.search` + `re.MULTILINE` | `re.search(pattern, text, re.MULTILINE)` | 在任意位置查找；多行模式下 `^` / `$` 匹配每一行 |
| `subprocess.run` | `subprocess.run(list(argv), cwd=..., capture_output=True, timeout=..., check=False)` | 运行外部命令；返回 `CompletedProcess`，`.returncode` 为退出码 |
| 多个 `except` / `try-finally` | `except subprocess.TimeoutExpired:`、`except FileNotFoundError as exc:`；`run` 中的 `finally` | 分别处理不同异常；`finally` 无论是否异常都执行清理（但异常仍会向上抛出） |
| 文件系统工具 | `tempfile.mkdtemp(prefix=...)`、`os.walk`、`os.path.relpath`、`os.makedirs(exist_ok=True)`、`shutil.copy2`、`shutil.rmtree` | 建唯一临时目录（需自己删）；递归遍历 `(dirpath, dirnames, filenames)`（`_dirs` 的下划线表示不使用）；算相对路径；建目录不怕已存在；复制保留元数据；删除整棵目录树 |
| `time.perf_counter()` / `statistics.mean` | 计算 `elapsed`、`statistics.mean(latencies)` | 高精度单调时钟；求平均（空列表会抛异常，所以代码先判断 `if latencies`） |
| 条件表达式 | `passes / self.k if self.k else 0.0` | `A if 条件 else B` |
| 推导式中的条件表达式 | `[(1.0 if r.passes > 0 else 0.0) if r.k == 1 else min(1.0, r.pass_rate) for r in ...]` | 嵌套的三元表达式，可读性差，本例中可以简化 |
| 嵌套推导式 | `[float(s["latency_ms"]) for r in task_reports for s in r.samples]` | 两层 `for` 从左到右对应外层、内层循环 |
| 生成器表达式 | `sum(float(s["cost_units"]) for r in ... for s in ...)` | 不建中间列表，边算边求和 |
| `max(0.0, min(1.0, x))` | `pass_at_k` | 把数值夹紧到区间内的惯用写法 |
| `round` 的银行家舍入 | `int(round(0.95 * n))` | `round(28.5) == 28`、`round(29.5) == 30`：.5 时舍入到偶数 |
| `print(..., file=sys.stderr)` | 错误信息 | 写到标准错误流，与正常输出分开 |
| `sys.exit(run_demo())` + `if __name__ == "__main__":` | 文件末尾 | 被直接运行时才执行 demo；返回值作为进程退出码，被 `import`（例如测试）时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`cd code && python3 main.py`，耗时不到 1 秒，退出码 0；延迟数值每次运行会略有不同）：

```text
EVAL HARNESS DEMO
loaded 5 fixture task(s)

  - task_001_fizzbuzz_offbyone       verifier=file_equals
  - task_002_factorial_missing_return verifier=regex_match     ← id 长 33 个字符，超过 :32s，对不齐
  - task_003_error_message_typo      verifier=file_equals
  - task_004_empty_reverse           verifier=regex_match
  - task_005_linked_list_traversal   verifier=file_equals

running reference candidate (apply_known_fixes), k=1 ...
{
  "k": 1,
  "pass_at_1": 1.0,
  "pass_at_k": 1.0,
  "mean_latency_ms": 0.329,       ← 5 个 sample 的平均（candidate 自报的复制耗时）
  "p95_latency_ms": 0.433,        ← n=5：round(4.75)=5，取最大值，即 task_001 的 0.433
  "total_cost": 5.0,              ← 每个 sample cost_units=1.0，共 5 个
  "tasks": [
    {
      "task_id": "task_001_fizzbuzz_offbyone",
      "k": 1,
      "passes": 1,
      "pass_rate": 1.0,
      "pass_at_k": 1.0,
      "mean_latency_ms": 0.433,
      "p95_latency_ms": 0.433,
      "mean_cost": 1.0,
      "samples": [
        {
          "sample_index": 0,
          "latency_ms": 0.433,
          "cost_units": 1.0,
          "passed": true,
          "detail": "file 'fizzbuzz.py' matches expected",
          "notes": "reference candidate"
        }
      ]
    },
    {
      "task_id": "task_002_factorial_missing_return",
      ...
          "detail": "file 'factorial.py' matched '^\\\\s*return\\\\s+result\\\\s*$'",
      ...
    },
    ...（task_003～005 结构相同，均 passed: true）
  ]
}

running noop candidate (should fail every fixture), k=3 ...
{
  "noop_pass_at_1": 0.0,
  "noop_pass_at_k": 0.0,
  "noop_k": 3
}
```

逐项解读：

- **加载 5 个夹具**：按目录名排序，顺序固定。
- **参考 candidate：pass@1 = pass@k = 1.0**：5 个任务都通过，说明 3 个 `file_equals` 与 expected 逐字一致，2 个 `regex_match` 的正则能匹配参考答案。这是 harness 的"阳性对照"。
- **延迟**：这里的毫秒数是复制一个小文件的耗时（0.25～0.43 ms），完全是 candidate 自报的。各任务的 `p95_latency_ms` 与 `mean_latency_ms` 相同，因为 k = 1 时每个任务只有一个样本。
- **`detail` 中的四个反斜杠**：pattern 本身含 `\s`；`{pattern!r}` 用 `repr` 把它显示成 `\\s`；`json.dumps` 再把每个 `\` 转义成 `\\`，于是屏幕上看到 `\\\\s`。这是两层转义叠加，不是 bug。
- **noop：pass@1 = 0.0（k = 3，共 15 个 sample）**：每个 buggy 文件都被自己的 verifier 拒绝，这是"阴性对照"。noop 报告只打印了 3 个汇总数字，没有打印每个任务的详情。
- **退出码 0**：两项自测都满足。若修改任何一个 expected 文件使其与 verifier 不符，`run_demo` 就会打印 `ERROR` 并返回 1。

补充实验（为本讲解和测验额外运行，脚本不在仓库中）：

| 实验 | 结果 | 说明 |
|------|------|------|
| task_002 把 `return result` 放进循环 | passes = 1，但 `factorial(5) = 2` | regex 误放 |
| task_004 写 `return sorted(items)[::-1]` / 注释 `# return items[::-1]` | 都 passes = 1 | regex 误放 |
| task_001 写 `range(1, n+1)`、task_005 写 `count = 1` | 都 passes = 0，功能却正确 | file_equals 误杀 |
| candidate 抛 `RuntimeError` | 整个 `run` 中止 | 缺少异常处理 |
| candidate `sleep(0.05)` 但自报 0.001 ms | 报告 `mean_latency_ms = 0.001` | 延迟自报 |
| 60% 概率修复的随机 candidate，k = 5，`random.seed(0)` | 各任务通过 `[3,4,2,1,2]`，pass@1 = 0.48，pass@k = 0.9012 | pass@k 远高于 pass@1 |
| 把 task_002 的 verifier 换成 `shell_exit_zero` + 断言 | 参考通过、noop 和"循环内 return"都失败 | 行为验证能抓住 regex 漏掉的错误 |

---

## 7. 动手改一改

1. **新增一个夹具**（入门）：仿照现有目录写 `task_006_*`，例如 `is_palindrome` 忘了忽略大小写。先确认参考 candidate 能通过、noop 不能通过，再运行 `python3 main.py` 观察报告变化。
2. **修正 p95**（入门）：把 `int(round(0.95 * n))` 改为 `math.ceil(0.95 * n)`，补一个 n = 19 的测试，期望返回 19；再对比 `statistics.quantiles(values, n=100)[94]` 的插值结果。
3. **让 harness 更健壮**（中级）：实现测验 Q10 的 `_run_one`——捕获 candidate 异常并记为失败、由 harness 用 `perf_counter` 计时、保留自报延迟以便对照；进一步用 `concurrent.futures` 给 candidate 加超时。
4. **改用行为验证**（中级）：把 task_002、task_004、task_005 的 verifier 改成 `shell_exit_zero` + 断言（参考测验 Q9），验证"循环内 return""`count = 1`"等变体的判定是否变得合理；同时把 `proc.stderr` 的最后几行写进 `detail`。
5. **无偏 pass@k 与报告口径**（中级）：增加 `n_samples` 参数，与报告用的 k 分开；实现 `1 - C(n-c,k)/C(n,k)`，在报告中同时输出 `c`、`n`、plug-in 与无偏两种 pass@k。
6. **回归对比脚本**（进阶）：把两次运行的 `EvalReport` JSON 存盘，写一个 `compare(old, new)`：任务集不同（加入任务内容哈希）就报错；否则列出 pass→fail / fail→pass 的翻转、pass@1 差值及其 bootstrap 置信区间——这正是讲义所说的 "regression-tracking script"。
7. **防答案泄漏**（进阶）：修改 candidate 协议，只传 `goal` 和 `scratch_dir`；参考 candidate 改为在构造时通过闭包拿到答案目录。思考：真实 agent 还可能通过哪些途径接触到 `expected/`？

---

## 8. 常见坑

- **复用 scratch 目录**：k > 1 时后一个 sample 会继承前一个的修改，pass rate 虚高。
- **相信 agent 自报**：成功与否只能由 verifier 判定；延迟、成本也最好由 harness 测量（本代码只做到了前者）。
- **把 regex 当成正确性检查 / 把 `file_equals` 失败当成 agent 错误**：前者看不出缩进位置、注释和语义错误，后者会因空格、`\r\n` 或等价写法误杀。
- **混用 pass@k 口径、只报 pass@k**：plug-in 与无偏估计在小样本下差别很大；pass@5 = 0.9 而 pass@1 = 0.48 时，单次调用一半会失败。
- **verifier 名字拼错**：会被记为"失败"，看起来像 agent 变差了，应在加载阶段校验。
- **`shell_exit_zero` 不经 sandbox**：agent 写的代码会以当前用户权限被执行。
- **`round()` 的银行家舍入**：`round(2.5) == 2`，用来取秩时容易差一档。
- **单元测试依赖 `true` / `false` 命令**：Windows 上没有这两个程序，`test_true_passes` 会失败。

---

## 9. 测试在验证什么

`tests/test_main.py` 共 20 个 `unittest` 测试，可以用 pytest 或标准库运行：

```bash
cd code
python3 -m pytest tests/ -v          # 讲义写法（在小节根目录则为 python3 -m pytest code/tests/ -v）
python3 -m unittest discover tests   # 不装 pytest 也可以
```

文件开头通过 `sys.path.insert(0, os.path.dirname(HERE))` 把 `code/` 加入导入路径，所以能 `from main import ...`；`TASKS_DIR` 指向真实的 `code/tasks/`。

| 测试类 | 测试 | 验证的性质 |
|-------|------|-----------|
| `PassAtKMathTests` | `test_zero_pass_rate` | p = 0 时 pass@5 = 0 |
| | `test_full_pass_rate` | p = 1 时 pass@5 = 1 |
| | `test_partial_pass_rate` | p = 0.5、k = 2 时为 0.75（`1 - 0.5²`），用 `assertAlmostEqual` 比较浮点数 |
| | `test_k_zero` | k = 0 时返回 0（代码有显式分支；即使没有分支，`1 - (1-p)^0` 也等于 0，所以这个测试区分不出分支是否存在） |
| | `test_clamps_out_of_range` | p = −1 或 2 时结果仍在 [0, 1] 内（夹紧逻辑） |
| | `test_p95_empty` | 空列表返回 0.0 而不是抛异常 |
| | `test_p95_nearest_rank` | 1..20 的 p95 为 19。⚠️ n = 20 时 `round` 与 `ceil` 结果相同，测不出 3.2 节指出的取秩偏差 |
| `FileEqualsTests` | `test_exact_match_passes` / `test_difference_fails` / `test_missing_scratch_file_fails` | 内容相同通过、不同失败、文件不存在失败（而不是抛异常）。`setUp` 中创建的 `expected/` 子目录没有被用到，是无害的残留代码 |
| `RegexMatchTests` | `test_match_passes` / `test_no_match_fails` | `return\s+42` 能匹配 `return 42`，`return\s+99` 不能 |
| `ShellExitZeroTests` | `test_true_passes` / `test_false_fails` / `test_missing_argv` | 退出码 0 通过、1 失败、缺 `argv` 失败。依赖 POSIX 命令 `true` / `false` |
| `FixtureLoadingTests` | `test_loads_all_bundled_fixtures` | 5 个夹具 ID 都能加载，且每个都有 `buggy/` 与 `expected/` 目录 |
| `HarnessEndToEndTests` | `test_reference_candidate_passes_all` | 参考 candidate 在 k = 1 下 pass@1 = pass@k = 1.0，每个任务 passes = 1 |
| | `test_noop_candidate_fails_all` | noop 在 k = 2 下 pass@1 = pass@k = 0.0 |
| | `test_report_serialises` | 报告能 `json.dumps`，且包含 `pass_at_1` 与任务 ID |
| | `test_demo_main_exits_zero` | `run_demo()` 返回 0（测试时会把完整报告打印到 stdout） |

实际运行结果：

```text
collected 20 items
tests/test_main.py::PassAtKMathTests::test_clamps_out_of_range PASSED
...
tests/test_main.py::HarnessEndToEndTests::test_report_serialises PASSED
============================== 20 passed in 0.08s ==============================
```

测试**没有覆盖**的地方（也是值得补充的测试）：

- verifier 的误放 / 误杀（例如"循环内 return"必须失败）——这类"变异测试"最能暴露 regex verifier 的弱点；
- candidate 抛异常、超时时 harness 的行为；
- k > 1 且部分通过时的 pass@1 / pass@k 聚合（目前只测了全过和全不过两个极端）；
- 未知 verifier 名字的处理；
- `normalize_trailing_newline` 的开关、`shell_exit_zero` 的超时分支。
