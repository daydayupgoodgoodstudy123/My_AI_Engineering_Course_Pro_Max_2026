# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 29 节 基于 Harness 的端到端 Coding Agent ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下）或 `cd code && python3 main.py`；测试：`python3 -m pytest code/tests/ -v` ｜ **依赖**：仅标准库（`json`、`os`、`re`、`shutil`、`subprocess`、`tempfile`、`time`、`uuid`、`contextlib`、`dataclasses`、`typing`）；运行时会用 `sys.executable` 启动子进程跑 unittest，无需网络
>
> 本讲解同时覆盖 fixture 文件 `fixture_repo/src/fizz.py`（2 行）、`fixture_repo/tests/__init__.py`（空文件）和 `fixture_repo/tests/test_fizz.py`，见第 3.10 节与第 9 节。

---

## 1. 这份代码在考察什么

这是 Track A（第 25–29 课）的"总装"课：把前四课的部件——gate chain、sandbox、观察 ledger、span/metric——缩小后重新写在一个文件里，再用一个**确定性状态机**扮演 coding agent，去修一个 fixture 仓库里的 off-by-one bug。

它考察的是：

1. **集成思维**：一次工具调用要依次经过 policy → gate chain → 工具执行（sandbox / 路径检查）→ 观察记账 → span 与 metric → 回到 policy。讲义："Compose them and the seams show."
2. **policy seam**：agent 的决策被压缩成 `next_action()` 与 `observe()` 两个方法；换成 LLM 时 harness 不变。
3. **预算**：步数预算与观察 token 预算分别在哪里、以什么时机检查。
4. **纵深防御**：gate 看意图（工具名、参数文本），sandbox 看执行（可执行文件、路径、超时、输出大小）。
5. **验收**：demo 末尾的硬断言（解决、步数 < 12、预算未超、零拒绝）。

> 一句话：**agent 真正的工程量在 harness 上，模型（这里是状态机）只是插在接缝上的一个部件**。同时要看清：这份实现的"bug 定位"是硬编码的，被拒绝的调用没有 span，步数边界有 bug，`run_tests` 能执行任意命令——这些都是讨论"接缝"的好素材。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Observation` / `ObservationLedger` / `estimate_tokens` | dataclass + 函数 | 记录每次观察的文本与 token 估算（`len//4`），求累计 | 第 25 课 观察预算 |
| `ToolCall` / `GateDecision` / `GateContext` | 冻结/普通 dataclass | 一次调用的描述、单个 gate 的判定、判定所需上下文 | gate 接口 |
| `WhitelistGate` / `RegexGate` / `BudgetGate` | dataclass | 工具名白名单、参数文本黑名单正则、观察预算 | 第 25 课 gate |
| `ChainOutcome` / `GateChain` | dataclass | 依次执行 gate，遇到第一个拒绝即短路 | gate chain |
| `SandboxResult` / `Sandbox` | dataclass | denylist、路径 jail、`subprocess.run` 超时与输出截断 | 第 26 课 sandbox |
| `GenAISpan` / `InMemoryExporter` / `JSONLExporter` | dataclass / 类 | 精简版 span 与两个 exporter | 第 28 课 trace |
| `Counter` / `Histogram` / `MetricsRegistry` / `prometheus_text` | dataclass / 函数 | 精简版 metric 与文本输出 | 第 28 课 metric |
| `SpanBuilder` | dataclass | `span()` context manager：计时、状态、导出、更新工具 metric | Tracer |
| `AgentStep` / `AgentRunReport` | dataclass | 每步记录与整次运行报告 | 运行结果 |
| `CodingAgentPolicy` | 类 | 六状态状态机：`next_action` 给出动作，`observe` 推进状态 | policy seam |
| `tool_read_file` / `tool_write_file` / `tool_run_tests` | 函数 | 三个工具的实现 | 工具层 |
| `_fixture_root` / `prepare_scratch_repo` | 函数 | 把 `fixture_repo/` 复制到临时目录 | 任务环境 |
| `AgentRun` | dataclass | 主循环：预算、gate、span、分派、记账 | agent loop |
| `build_default_chain` | 函数 | 组装默认 gate chain | 配置 |
| `run_demo` | 函数 | 跑一遍、打印、硬断言、返回退出码 | 演示 / 验收 |

数据流：`run_demo` → `prepare_scratch_repo()` 得到临时仓库 → 构造 `GateChain`、`Sandbox`、`SpanBuilder` → `AgentRun.run()`：开 `gen_ai.chat` span → 循环 { `policy.next_action` → `ToolCall` → `chain.evaluate` →（放行）开 tool span → `tool_*` → `Observation` 入 ledger → `policy.observe` } → `AgentRunReport` → 打印步骤、span 数、Prometheus 摘要 → 断言。

---

## 3. 逐段精讲

### 3.1 观察 ledger 与 token 估算

```python
@dataclass
class ObservationLedger:
    rows: list[Observation] = field(default_factory=list)

    def record(self, obs: Observation) -> None:
        self.rows.append(obs)

    def cumulative(self) -> int:
        return sum(r.tokens for r in self.rows)


def estimate_tokens(text: str) -> int:
    return 0 if not text else max(1, len(text) // 4)
```

- "4 个字符约 1 个 token"是英文文本的粗略经验值；中文、代码、traceback 偏差都不小，真实系统应使用模型对应的 tokenizer。
- `max(1, ...)` 保证非空文本至少计 1 token；空文本计 0。
- ledger 只追加不删除，`cumulative()` 每次全量求和，O(n)；步数少时无所谓。
- 本次运行 5 次观察分别是 17、481、143、7、25 token，合计 673（见第 6 节）。

### 3.2 Gate chain：白名单、正则、预算

```python
@dataclass(frozen=True)
class ToolCall:
    turn: int
    tool: str
    argv: tuple[str, ...]
    payload: str = ""
```

- `frozen=True` 让 `ToolCall` 不可变，gate 之间无法篡改调用内容；`argv` 用元组也是为了不可变。
- `payload` 是 `write_file` 的写入内容，也会被 `RegexGate` 扫描。

```python
@dataclass
class RegexGate:
    patterns: tuple[re.Pattern[str], ...]
    name: str = "regex"

    @classmethod
    def from_strings(cls, items: tuple[str, ...]) -> "RegexGate":
        return cls(patterns=tuple(re.compile(p) for p in items))

    def evaluate(self, call: ToolCall, ctx: GateContext) -> GateDecision:
        haystack = " ".join(call.argv) + " " + call.payload
        for pat in self.patterns:
            if pat.search(haystack):
                return GateDecision(False, self.name, f"refused pattern {pat.pattern!r}")
        return GateDecision(True, self.name, "clean")
```

- `@classmethod` 作为备选构造器，把字符串列表预编译为正则。
- ⚠️ 黑名单天然不完整：`\brm\s+-rf\b` 拦不住 `rm -r -f`、`rm --recursive`、`find -delete`、`python -c "shutil.rmtree(...)"`。
- ⚠️ 默认链中的 `^/etc/` 锚定的是**整个 haystack 的开头**（`" ".join(argv)`），`cat /etc/passwd` 的开头是 `cat`，因此不匹配（已实测放行，最终靠 sandbox 路径 jail 拦下）。

```python
@dataclass
class BudgetGate:
    max_tokens: int
    name: str = "budget"

    def evaluate(self, call, ctx):
        used = ctx.ledger.cumulative()
        if used >= self.max_tokens:
            return GateDecision(False, self.name, f"observation budget exhausted: {used}/{self.max_tokens}")
        return GateDecision(True, self.name, f"{self.max_tokens - used} remaining")
```

- 调用**之前**检查已用量；它无法预知这次调用会产生多少输出。
- `GateContext` 把 ledger 传进来，gate 本身无状态。`current_turn` 字段在本文件中没有被任何 gate 使用。

```python
@dataclass
class GateChain:
    gates: tuple[Any, ...]

    def evaluate(self, call, ctx) -> ChainOutcome:
        decisions: list[GateDecision] = []
        for gate in self.gates:
            decision = gate.evaluate(call, ctx)
            decisions.append(decision)
            if not decision.allow:
                return ChainOutcome(decisions=decisions)
        return ChainOutcome(decisions=decisions)
```

- **短路**：第一个拒绝后不再执行后面的 gate，`decisions` 只包含已执行的部分；`deny_reason` 返回 `"[gate名] 原因"`。
- 顺序有意义：便宜的 gate（白名单）放前面，依赖状态的 gate（预算）放后面。
- gate 用"鸭子类型"：只要有 `evaluate(call, ctx)` 方法即可，`gates: tuple[Any, ...]` 没有声明接口。

### 3.3 Sandbox：denylist、路径 jail、超时、截断

```python
@dataclass
class Sandbox:
    project_root: str
    timeout_seconds: float = 10.0
    max_output_bytes: int = 32 * 1024
    denylist: frozenset[str] = frozenset({"rm", "sudo", "mkfs", "dd", "curl", "wget", "chmod", "kill"})

    def __post_init__(self) -> None:
        self.project_root = os.path.realpath(self.project_root)
```

- `frozenset` 是不可变集合，可以安全地作为 dataclass 默认值（不可变对象不需要 `default_factory`）。
- `__post_init__` 在自动生成的 `__init__` 之后运行，把根目录规范化为真实路径。这一步很关键：macOS 上 `/tmp` 是 `/private/tmp` 的符号链接，不规范化的话后面 `startswith` 比较会全部失败。

```python
    def _path_jail(self, argv: list[str]) -> str | None:
        for arg in argv[1:]:
            if not arg or arg.startswith("-"):
                continue
            if "/" not in arg and ".." not in arg:
                continue
            candidate = arg if os.path.isabs(arg) else os.path.join(self.project_root, arg)
            resolved = os.path.realpath(candidate)
            if resolved != self.project_root and not resolved.startswith(self.project_root + os.sep):
                return f"path {arg!r} resolves outside root"
        return None
```

- 只检查"看起来像路径"的参数（含 `/` 或 `..`），`realpath` 会解析 `..` 与符号链接，再判断是否仍在根目录内。
- `+ os.sep` 防止前缀误判：根为 `/tmp/repo` 时，`/tmp/repo2/x` 不应被视为在内部。
- ⚠️ 不含 `/` 的参数直接跳过：仓库里一个指向外部的符号链接 `link`，`cat link` 不会被检查（实测 `_path_jail(["cat", "link"])` 返回 `None`）。
- ⚠️ 藏在代码字符串里的路径（`python -c "open('/etc/passwd')"`）完全看不到。路径 jail 只是"参数级"检查，不是 OS 级隔离。

```python
        started = time.perf_counter()
        try:
            proc = subprocess.run(argv, cwd=self.project_root, capture_output=True,
                                  timeout=self.timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            return SandboxResult(argv=argv, exit_code=TIMED_OUT_EXIT, timed_out=True, ...)
        except FileNotFoundError as exc:
            return SandboxResult(argv=argv, exit_code=DENIED_EXIT, denied=True, reason=f"not found: {exc}", ...)
        elapsed = (time.perf_counter() - started) * 1000.0
        out = (proc.stdout or b"")[: self.max_output_bytes]
```

- `argv` 列表形式调用、不经过 shell（没有 `shell=True`），避免 shell 注入；但 argv[0] 若本身是 `bash -c` 或解释器，就等于把 shell 交了出去。
- `cwd=self.project_root`：子进程在仓库根运行，所以 `tests/test_fizz.py` 这种相对路径成立。
- `timeout` 到期时 `subprocess.run` 会杀掉子进程并抛 `TimeoutExpired`；`check=False` 表示非 0 退出码不抛异常，由调用方自己看 `returncode`。
- `time.perf_counter()` 是单调高精度计时器，适合测耗时（不受系统时间调整影响）。
- 输出按**字节**截断到 32KB，可能截断在多字节 UTF-8 字符中间，后面 `decode(errors="replace")` 会把残缺字符变成 `�`。
- 特殊退出码 `DENIED_EXIT = -100`、`TIMED_OUT_EXIT = -101`，与真实进程的退出码（0–255，被信号杀死时为负的信号值）区分开。
- 没有限制网络、内存、CPU、可写目录——这些需要容器/namespace/rlimit 等 OS 级手段。

### 3.4 精简版 span 与 metric（来自第 28 课）

```python
@dataclass
class GenAISpan:
    trace_id: str
    span_id: str
    parent_span_id: str
    name: str
    start_unix_nano: int
    end_unix_nano: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = STATUS_UNSET
    status_message: str = ""
```

讲义说这些部件是"copied with the same names as lessons 25-28"，但与第 28 课相比有几处删减/差异：

| 项目 | 第 28 课 | 本课 |
|------|---------|------|
| `GenAISpan` | 有 `kind`、`events` | 都没有，因此无法挂 gate 决策 event |
| 异常处理 | ERROR + `exception` event | 只有 ERROR 与 message |
| `Histogram` 默认桶 | 5…2500, 5000, 10000 | 少了 2500 与 10000，最大有限桶为 5000 |
| label 转义 | `_format_labels` 处理 `\`、`"`、换行 | `prometheus_text` 不转义 |
| `# HELP` 行 | 有 | 无 |
| `_sum` / `_count` 顺序 | sum 在前 | count 在前（顺序不影响解析） |
| `JSONLExporter.close()` | 关闭后 `fh` 不置空 | 关闭后 `fh = None`，之后再导出会重新打开文件（比第 28 课更稳健） |

`SpanBuilder.span` 的逻辑与第 28 课相同：`yield` 前创建 span，正常结束设 OK，异常设 ERROR 并重新抛出，`finally` 中记结束时间、导出、若有 `gen_ai.tool.name` 则更新 `tools_called_total` 与 `tool_latency_ms`。导出在 `finally` 中且没有异常保护，所以 exporter 出错会覆盖业务异常（第 28 课测验 Q10 讨论过）。

### 3.5 `CodingAgentPolicy`：确定性状态机

```python
    def next_action(self, last_obs: Observation | None) -> tuple[str, tuple[str, ...], str]:
        if self.state == "SURVEY":
            return ("read_file", ("src/fizz.py",), "")
        if self.state == "RUN_TESTS":
            python = sys.executable
            return ("run_tests", (python, "-m", "unittest", "tests/test_fizz.py"), "")
        if self.state == "INSPECT":
            return ("read_file", ("tests/test_fizz.py",), "")
        if self.state == "FIX":
            assert self.identified_bug_file is not None
            assert self.identified_fix is not None
            return ("write_file", (self.identified_bug_file,), self.identified_fix)
        if self.state == "VERIFY":
            ...
        return ("noop", (), "")
```

- 返回三元组 `(tool, argv, payload)`，这就是"policy seam"的输出格式；LLM 版本要把模型的 tool call 解析成同样的三元组。
- `next_action` 只依赖 `self.state`，参数 `last_obs` 完全没用到（docstring 也说是"Pure function of self.state"）。
- `sys.executable` 用当前解释器的绝对路径，保证子进程和父进程是同一个 Python。
- `assert` 用于检查前置条件；注意 `python -O` 会删除所有 `assert`，生产代码中应改用显式 `if ...: raise`。
- 与讲义的差异：讲义说 SURVEY "reads the project listing"、INSPECT "reads the failing source file"；代码中 SURVEY 读 `src/fizz.py`，INSPECT 读 `tests/test_fizz.py`，也没有 `list_dir` 工具。

```python
    def observe(self, tool: str, exit_code: int, text: str) -> None:
        if self.state == "SURVEY" and tool == "read_file":
            self.state = "RUN_TESTS"; return
        if self.state == "RUN_TESTS" and tool == "run_tests":
            if exit_code == 0:
                self.tests_passed = True
                self.state = "HALT"; return
            self.last_test_stderr = text
            self.state = "INSPECT"; return
        if self.state == "INSPECT" and tool == "read_file":
            if "expected" in self.last_test_stderr and "fizz" in self.last_test_stderr.lower():
                self.identified_bug_file = "src/fizz.py"
                self.identified_fix = "def fizz(n):\n    return [i if i % 3 else 'fizz' for i in range(1, n + 1)]\n"
            else:
                self.identified_bug_file = "src/fizz.py"
                self.identified_fix = "...与上面完全相同..."
            self.state = "FIX"; return
        ...
```

状态转移表：

| 当前状态 | 动作 | 观察条件 | 下一状态 |
|---------|------|---------|---------|
| SURVEY | `read_file(src/fizz.py)` | 任意 | RUN_TESTS |
| RUN_TESTS | `run_tests` | 退出码 0 | HALT（`tests_passed=True`） |
| RUN_TESTS | `run_tests` | 退出码 ≠ 0 | INSPECT（保存测试输出） |
| INSPECT | `read_file(tests/test_fizz.py)` | 任意 | FIX（设定修复内容） |
| FIX | `write_file(src/fizz.py, payload)` | 任意 | VERIFY |
| VERIFY | `run_tests` | 任意 | HALT（`tests_passed = exit_code == 0`） |
| 其他组合 | — | — | 不变 |

- ⚠️ **修复是硬编码的**：`if` 与 `else` 两个分支完全一样，讲义所说的"via a regex"并不存在。条件里的 `"expected"` 之所以命中，是因为 unittest 输出包含测试方法名 `test_n_1_expected_single` 等，而不是因为分析了失败信息。改成真正推断补丁的写法见测验 Q10。
- ⚠️ `observe` 忽略了 `exit_code` 在 SURVEY/INSPECT/FIX 中的含义：即使 `read_file` 返回"file not found"（退出码 1）或 `write_file` 失败，状态也照样前进。
- 未知组合"不推进"，配合步数预算可以防止死循环，但也意味着会一直重复同一个动作直到预算耗尽。
- `last_test_stderr` 名不副实：`tool_run_tests` 返回的是 stdout + stderr 拼接后的文本。

### 3.6 三个工具

```python
def tool_read_file(sandbox: Sandbox, argv: tuple[str, ...]) -> tuple[int, str]:
    path = argv[0]
    full = os.path.join(sandbox.project_root, path)
    real = os.path.realpath(full)
    if not (real == sandbox.project_root or real.startswith(sandbox.project_root + os.sep)):
        return (DENIED_EXIT, f"path {path!r} outside root")
    if not os.path.isfile(real):
        return (1, f"file not found: {path}")
    with open(real, "r", encoding="utf-8") as fh:
        return (0, fh.read())
```

- `os.path.join(root, "/etc/passwd")` 遇到绝对路径会丢弃前面的 root，得到 `/etc/passwd`；随后的 `realpath` + 前缀检查能拦下它。`../../etc/passwd` 同样被拦（实测返回 `(-100, "path '../../etc/passwd' outside root")`）。
- 读文件**不经过** `Sandbox.run`，而是直接在本进程里 `open`——讲义说 "Every tool execution goes through the sandbox"，实际只有 `run_tests` 经过 sandbox，读写只复用了 sandbox 的根目录做路径检查。
- 没有大小限制：读一个巨大文件会直接塞满观察预算。

```python
def tool_write_file(sandbox, argv, payload) -> tuple[int, str]:
    path = argv[0]
    full = os.path.join(sandbox.project_root, path)
    real = os.path.realpath(os.path.dirname(full)) if os.path.dirname(full) else sandbox.project_root
    if not (real == sandbox.project_root or real.startswith(sandbox.project_root + os.sep)):
        return (DENIED_EXIT, f"dir {path!r} outside root")
    os.makedirs(os.path.dirname(full) or sandbox.project_root, exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(payload)
    return (0, f"wrote {len(payload)} bytes to {path}")
```

- 只检查**目录**的真实路径：若目标文件本身是指向仓库外的符号链接，`open(full, "w")` 会顺着链接写到外面。更严格的做法是检查 `realpath(full)`，或用 `os.open(..., O_NOFOLLOW)`。
- `os.path.dirname(full)` 永远非空（`full` 是拼在 root 后面的），所以条件表达式的 `else` 分支实际不会走到。
- 整文件覆盖写，没有备份/diff；也没有限制可写路径——`tests/` 同样可写，agent 可以"改测试让测试通过"（测验 Q17）。
- 返回信息里的 `len(payload)` 是**字符数**而不是字节数（本例都是 ASCII，两者相同：74）。

```python
def tool_run_tests(sandbox, argv) -> tuple[int, str]:
    result = sandbox.run(list(argv))
    if result.denied:
        return (DENIED_EXIT, result.reason)
    if result.timed_out:
        return (TIMED_OUT_EXIT, result.reason)
    out = result.stdout.decode("utf-8", errors="replace") + result.stderr.decode("utf-8", errors="replace")
    return (result.exit_code, out)
```

- unittest 把结果写到 **stderr**，所以要把 stdout 和 stderr 拼起来给 policy 看。
- ⚠️ argv 完全由 policy 决定，白名单只检查工具名 `run_tests`，于是 `run_tests` 实际上是"执行任意命令"。实测 `[sys.executable, "-c", "import os; print(os.listdir('/etc'))"]` 通过 gate 与 sandbox 并成功读到了 `/etc` 的内容。修复：让 `run_tests` 不接受 argv，由 harness 固定命令（测验 Q11）。

### 3.7 准备 scratch 仓库

```python
def prepare_scratch_repo() -> str:
    scratch = tempfile.mkdtemp(prefix="agent-e2e-")
    src = _fixture_root()
    for dirpath, _dirs, files in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        dst_root = scratch if rel == "." else os.path.join(scratch, rel)
        os.makedirs(dst_root, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(dirpath, f), os.path.join(dst_root, f))
    return scratch
```

- 每次运行都复制一份全新的 fixture，agent 改的是副本，原始 fixture 永远保持"有 bug"的状态——这样 demo 和测试才能反复运行。
- `os.walk` 递归遍历；`relpath` 求相对路径后在目标处重建目录；`copy2` 连同修改时间等元数据一起复制。等价于 `shutil.copytree(src, scratch, dirs_exist_ok=True)`。
- `_fixture_root()` 用 `os.path.abspath(__file__)` 定位，不依赖当前工作目录。
- ⚠️ 临时目录**从不删除**：demo 运行一次、测试套件运行一次，会在 `/tmp` 留下约 10 个 `agent-e2e-*` 目录（实测）。
- ⚠️ 若有人在 `fixture_repo/` 里直接跑过测试，生成的 `__pycache__` 也会被复制过去。

### 3.8 `AgentRun.run`：主循环

```python
        with self.builder.span("gen_ai.chat", attributes={
                "gen_ai.system": "track-a-harness",
                "gen_ai.request.model": "deterministic-policy",
                "gen_ai.operation.name": "chat"}) as chat_span:
            for step_index in range(self.step_budget):
                if policy.state == "HALT":
                    halted_reason = "policy reached HALT"
                    solved = policy.tests_passed
                    break
                tool, argv, payload = policy.next_action(last_obs)
                if tool == "noop":
                    halted_reason = "policy emitted noop"
                    break
                turn = step_index + 1
                call = ToolCall(turn=turn, tool=tool, argv=argv, payload=payload)
                ctx = GateContext(ledger=ledger, current_turn=turn)
                outcome = self.chain.evaluate(call, ctx)
                if not outcome.allow:
                    refused_legal += 1
                    steps.append(AgentStep(..., allow=False, exit_code=DENIED_EXIT, notes="gate refused"))
                    halted_reason = f"gate refused: {outcome.deny_reason}"
                    break
```

- 整次运行包在一个 `gen_ai.chat` span 里，所有工具 span 都以它为父。严格来说这更像 `invoke_agent` span（一次 agent 任务），而不是一次模型 chat 调用。
- `for ... in range(step_budget)` 天然实现步数上限；`for ... else` 的 `else` 只在循环**没有被 break**时执行，用来标记"预算耗尽"。
- ⚠️ **边界 bug**：HALT 只在每轮开头检查。若第 `step_budget` 步恰好让 policy 进入 HALT，循环随即结束，`solved` 保持 `False`，`halted_reason` 为 "step budget exhausted"。实测 `step_budget=5` → `solved=False`；`step_budget=6` → `solved=True`、仍只用 5 步。修复是在 `policy.observe(...)` 之后立刻检查 HALT（测验 Q9）。
- gate 拒绝后**直接结束运行**，而不是把拒绝理由作为观察反馈给 policy 让它换个做法——对确定性 policy 合理，对 LLM agent 通常应反馈。
- ⚠️ 被拒绝的调用不产生 span（gate 判定在 tool span 之外），与讲义架构图的 `Refuse → Span ERROR` 不符。
- ⚠️ `refused_legal` 统计的是**所有**被拒绝的调用，不区分工具是否"合法"，名字容易误解。

```python
                with self.builder.span("gen_ai.tool.execution", parent=chat_span, attributes={
                        "gen_ai.tool.name": tool,
                        "gen_ai.tool.call.id": f"call_{step_index:03d}"}) as tool_span:
                    if tool == "read_file":
                        exit_code, text = tool_read_file(self.sandbox, argv)
                    elif tool == "write_file":
                        exit_code, text = tool_write_file(self.sandbox, argv, payload)
                    elif tool == "run_tests":
                        exit_code, text = tool_run_tests(self.sandbox, argv)
                    else:
                        exit_code, text = (DENIED_EXIT, f"unknown tool {tool!r}")
                    tool_span.attributes["gen_ai.tool.result.bytes"] = len(text)
                    tool_span.attributes["exit_code"] = exit_code

                obs = Observation(turn=turn, tool=tool, text=text, tokens=estimate_tokens(text))
                ledger.record(obs)
                last_obs = obs
                steps.append(AgentStep(index=step_index, state=policy.state, ..., exit_code=exit_code,
                                       notes=f"obs_tokens={obs.tokens}"))

                if ledger.cumulative() > self.observation_budget:
                    halted_reason = f"observation budget {self.observation_budget} exceeded"
                    break

                policy.observe(tool, exit_code, text)
```

- 分派用 `if/elif` 链；第 21、23 课会用工具注册表 + 分派器取代它。
- tool span 只要块内没抛异常就是 `OK`，测试失败（exit 1）也是 OK；`exit_code` 是没有命名空间前缀的自定义 attribute。`gen_ai.tool.result.bytes` 存的是 `len(text)`，即字符数而非字节数。
- `AgentStep.state` 记录的是**执行前**的状态（`observe` 还没调用），所以打印出来的 state 正好是"为什么做这一步"。
- 观察预算在执行**之后**检查（`>`），超出后才停：`observation_budget=300` 时，第 2 步一下子累计到 498 才停止（实测）。注意它与 `BudgetGate` 的 `>=` 判定、以及 `build_default_chain(budget=...)` 是**两个独立设置**的预算——讲义开头说的"预算只在一处被追踪"的接缝问题，在这里以"两处各自追踪、参数可能不一致"的形式出现。
- 预算超出时 `break` 发生在 `policy.observe` 之前，policy 看不到最后一次观察。

### 3.9 `build_default_chain` 与 `run_demo`

```python
def build_default_chain(budget: int = 4000) -> GateChain:
    python = os.path.basename(sys.executable)
    return GateChain(gates=(
        WhitelistGate(allowed=frozenset({"read_file", "write_file", "run_tests"})),
        RegexGate.from_strings(items=(r"\brm\s+-rf\b", r"\bsudo\b", r"^/etc/")),
        BudgetGate(max_tokens=budget),
    ))
```

- 第一行的 `python` 变量从未使用，是遗留代码（可能原本打算做 argv 白名单）。
- 默认预算 4000，`run_demo` 与测试都显式传 8000。

`run_demo` 依次：准备仓库 → 组装 chain/sandbox/metrics/两个 exporter → 运行 → 关闭 JSONL → 打印汇总、每步结果、span 数、Prometheus 摘要（只保留 counter 行和 histogram 的 `_count`、`_sum` 行）→ 四条硬断言：

```python
    if not report.solved: ... return 1
    if len(report.steps) >= 12: ... return 1
    if report.observation_tokens > report.max_observation_budget: ... return 1
    if report.refused_legal_tool_calls != 0: ... return 1
    return 0
```

- 错误信息写到 `sys.stderr`，返回值作为进程退出码，CI 可以直接用。
- 讲义列出的五条验收中，"Every step has a corresponding span" 与 "Prometheus 输出包含 ..." 两条没有在 `run_demo` 中断言（后者在测试里有，前者测试里以"tool span 数 == steps 数"间接验证，但只在没有拒绝的情况下成立）。
- `traces.jsonl` 写在 scratch 仓库里，随临时目录一起留在 `/tmp`。

### 3.10 Fixture 仓库：`fizz.py`、`tests/__init__.py`、`test_fizz.py`

`fixture_repo/src/fizz.py`（有 bug 的版本，2 行）：

```python
def fizz(n):
    return [i if i % 3 else 'fizz' for i in range(1, n)]
```

- 列表推导式 + 条件表达式：`i % 3` 非 0（真）时保留 `i`，为 0（假）时换成 `'fizz'`。
- bug：`range(1, n)` 不包含 `n`，`fizz(5)` 只得到 `[1, 2, 'fizz', 4]`；正确写法 `range(1, n + 1)`。
- 名字叫 fizz，只处理 3 的倍数，没有 FizzBuzz 的 5 / 15 规则——fixture 只需要一个最小的 off-by-one。

`fixture_repo/tests/__init__.py`：空文件，把 `tests` 变成常规包。`python -m unittest tests/test_fizz.py` 会把路径转换成模块名 `tests.test_fizz` 再导入，失败输出里显示的也是 `tests.test_fizz.FizzTests.test_n_1_expected_single`。`src/` 没有 `__init__.py`，`from src.fizz import fizz` 依靠 Python 3 的隐式命名空间包也能工作。

`fixture_repo/tests/test_fizz.py`：

```python
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from src.fizz import fizz

class FizzTests(unittest.TestCase):
    def test_n_5_expected_list(self):
        expected_fizz_result = [1, 2, 'fizz', 4, 5]
        self.assertEqual(fizz(5), expected_fizz_result)
    def test_n_1_expected_single(self):
        self.assertEqual(fizz(1), [1])
    def test_n_3_expected_three(self):
        self.assertEqual(fizz(3), [1, 2, 'fizz'])
```

- 把仓库根加入 `sys.path`，保证不论从哪里启动都能 `import src.fizz`。
- 三个用例分别覆盖 n=5（一般情况）、n=1（最小边界）、n=3（恰好在 fizz 上结束）。有 bug 时三个都失败：`[] != [1]`、`[1, 2] != [1, 2, 'fizz']`、`[1, 2, 'fizz', 4] != [1, 2, 'fizz', 4, 5]`——每一处都是"实际比期望少最后一个元素"，这正是推断 off-by-one 的信号（测验 Q10）。
- 方法名里的 `expected` 恰好让 policy 的 `"expected" in ...` 条件成立。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 在一个文件里重写第 25–28 课的部件 | 本课独立运行、不依赖兄弟目录 | 与原课实现出现漂移（桶、event、转义不同）；生产中应抽成共享包 |
| 确定性状态机代替 LLM | 离线、可复现、测试能断言精确步数 | 修复是硬编码的，证明的是 harness 管道而非 agent 能力；换 LLM 后要做统计评估 |
| policy 只有 `next_action` / `observe` | 接缝清晰 | `AgentRun` 写死了 `CodingAgentPolicy`，需改成可注入的 factory/Protocol |
| gate 链短路 + 黑名单正则 | 简单、可解释的拒绝理由 | 黑名单不完整；应以白名单（工具 + argv 模板）为主 |
| `run_tests` 接受任意 argv | 让 policy 自己决定测试命令 | 等于任意命令执行；应固定命令或模板匹配 |
| 参数级路径 jail | 不依赖操作系统特性 | 符号链接、代码字符串中的路径都能绕过；生产用容器/namespace/只读挂载 |
| `len//4` 估 token | 零依赖 | 对 traceback、中文偏差大；用真实 tokenizer |
| 观察预算事后检查、gate 预算事前检查，两处分别配置 | 各管一段 | 会超支、参数可能不一致；统一预算对象，执行时截断输出 |
| 拒绝即终止运行 | 简化流程 | LLM agent 通常应把拒绝反馈给模型；且拒绝应留下 span |
| 每次复制 fixture 到临时目录 | 原 fixture 不被改坏、可重复运行 | 从不清理；用 `TemporaryDirectory` 或测试的 `tearDown` 删除 |
| 整文件覆盖写 | 实现简单 | 无法审查最小改动、易误伤；用 patch/diff 工具并限制可写目录 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class ToolCall:` | 实例不可变，赋值会抛 `FrozenInstanceError`；还可哈希 |
| `field(default_factory=list)` | `rows: list[Observation] = field(default_factory=list)` | 可变默认值必须用工厂 |
| `__post_init__` | `Sandbox.__post_init__` | dataclass 自动 `__init__` 之后的钩子，用于规范化字段 |
| `frozenset` | `denylist: frozenset[str] = frozenset({...})` | 不可变集合，可作为默认值 |
| `@classmethod` 备选构造器 | `RegexGate.from_strings(...)` | 用 `cls(...)` 构造实例 |
| `@property` | `ChainOutcome.allow`、`SandboxResult.ok` | 计算属性 |
| `all()` + 生成器 | `all(d.allow for d in self.decisions)` | 全部为真才为真；空序列返回 True |
| 返回元组 / 元组解包 | `exit_code, text = tool_read_file(...)` | 一次返回多个值 |
| 类型注解 `X \| None`、`tuple[str, ...]` | `def deny_reason(self) -> str \| None` | `...` 表示任意长度元组 |
| `!r` 转换 | `f"tool {call.tool!r} not in allow-set"` | 用 `repr()` 显示，字符串带引号 |
| f-string 宽度与补零 | `f"call_{step_index:03d}"`、`{step.state:10s}` | 3 位补零；宽度 10 左对齐 |
| `for ... else` | `AgentRun.run` | `else` 仅在循环未被 `break` 时执行 |
| `try / except 多个异常` | `except subprocess.TimeoutExpired:` / `except FileNotFoundError as exc:` | 分别处理超时与找不到可执行文件 |
| `subprocess.run` | `capture_output=True, timeout=..., check=False` | 捕获输出、超时、非 0 不抛异常 |
| `bytes` 切片与解码 | `(proc.stdout or b"")[: self.max_output_bytes]`、`.decode("utf-8", errors="replace")` | 字节截断；无效字节替换为 `�` |
| `os.path` 系列 | `realpath`、`join`、`isabs`、`relpath`、`dirname`、`basename` | 路径规范化与拼接 |
| `os.walk` | `for dirpath, _dirs, files in os.walk(src)` | 递归遍历目录树，`_dirs` 表示不使用 |
| `tempfile.mkdtemp` | `tempfile.mkdtemp(prefix="agent-e2e-")` | 创建临时目录（需自行删除） |
| `@contextmanager` | `SpanBuilder.span` | 用生成器写 context manager |
| 字典解包 | `{**label_dict, "le": "+Inf"}` | 合并字典 |
| 条件表达式嵌在 f-string 外 | `"{" + ",".join(...) + "}" if key else ""` | 注意优先级：整个拼接作为真分支 |
| `assert` | `assert self.identified_fix is not None` | 调试断言，`-O` 下会被移除 |
| `sys.executable` | `(python, "-m", "unittest", ...)` | 当前解释器路径 |
| `sys.exit(run_demo())` | 文件末尾 | 返回值作为退出码 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`cd code && python3 main.py`，退出码 0；临时目录名每次不同）：

```text
END-TO-END CODING AGENT DEMO
scratch repo: /tmp/agent-e2e-p5bph66i

solved=True halted=policy reached HALT
steps=5 obs_tokens=673/8000 refused_legal=0

steps:
  [0] SURVEY     read_file   argv=['src/fizz.py'] -> ok                       ← 17 token（70 字节源码）
  [1] RUN_TESTS  run_tests   argv=['/usr/bin/python3', '-m', 'unittest', 'tests/test_fizz.py'] -> exit=1   ← 481 token，3 个失败
  [2] INSPECT    read_file   argv=['tests/test_fizz.py'] -> ok                ← 143 token
  [3] FIX        write_file  argv=['src/fizz.py'] -> ok                       ← 7 token："wrote 74 bytes to src/fizz.py"
  [4] VERIFY     run_tests   argv=['/usr/bin/python3', '-m', 'unittest', 'tests/test_fizz.py'] -> ok    ← 25 token，Ran 3 tests ... OK

spans emitted: 6 (jsonl at /tmp/agent-e2e-p5bph66i/traces.jsonl)   ← 5 个 tool span + 1 个 chat span

--- prometheus exposition (excerpt) ---
# TYPE tools_called_total counter
tools_called_total{tool="read_file"} 2.0
tools_called_total{tool="run_tests"} 2.0
tools_called_total{tool="write_file"} 1.0
# TYPE tool_latency_ms histogram
tool_latency_ms_count{tool="read_file"} 2
tool_latency_ms_sum{tool="read_file"} 0.133044
tool_latency_ms_count{tool="run_tests"} 2
tool_latency_ms_sum{tool="run_tests"} 109.21033800000001   ← 两次启动子进程，约 55 ms/次
tool_latency_ms_count{tool="write_file"} 1
tool_latency_ms_sum{tool="write_file"} 0.155146
```

逐项解读：

- **5 步解决**，远小于 12 的上限；`refused_legal=0` 说明三个工具都在白名单内、参数没有触发正则、预算充足。
- **观察 token**：第一次跑测试的失败输出占了 71%（481/673）。真实 agent 中，测试与编译输出往往是上下文膨胀的主因。
- **第 1 步 `exit=1`**：这是预期中的失败，policy 据此进入 INSPECT；对应的 span 状态仍是 `OK`（`exit_code=1` 只记在 attribute 中）。
- **span 数 6**：没有拒绝时，tool span 数等于步数；chat span 最后结束、最后导出。
- **延迟**：`read_file` / `write_file` 在本进程内完成，0.1 ms 级；`run_tests` 要启动新的 Python 解释器，两次合计约 109 ms、平均约 55 ms 一次——比读写文件慢两个数量级（摘要只打印了 count/sum，具体落在哪个桶要看完整输出）。
- `109.21033800000001` 是浮点求和的表示误差，`prometheus_text` 直接 `str(sum(...))` 输出。
- 运行结束后 `/tmp/agent-e2e-*` 目录保留，包括改好的 `src/fizz.py` 和 `traces.jsonl`，可以打开查看。

我们额外做的实验（均为实测）：

| 改动 | 结果 |
|------|------|
| `step_budget=5` | `solved=False`、"step budget exhausted"、5 步（边界 bug） |
| `step_budget=6` | `solved=True`、5 步 |
| `observation_budget=300` | 第 2 步后累计 498 token 超限停止，`solved=False` |
| `build_default_chain(budget=300)` | 第 3 步被 `[budget] observation budget exhausted: 498/300` 拒绝；只有 3 个 span，被拒的一步没有 span |
| `run_tests` 传 `python -c "...listdir('/etc')"` | gate 与 sandbox 都放行，成功执行 |

---

## 7. 动手改一改

1. **修步数边界 bug**：在 `policy.observe` 之后检查 HALT；补一个 `step_budget=5` 时应成功的测试。
2. **真正推断补丁**：实现测验 Q10 的 `propose_fix`，并把 `AgentRun` 改为接收 `policy_factory` 参数；再造一个"实际比期望多一个元素"的 fixture，确认 policy 会停止而不是乱改。
3. **补齐可观测性**：把 gate 判定移进 tool span，被拒绝时设 ERROR 并记录 `agent.harness.gate.decision/reason`；给 `GenAISpan` 加回 `events`；把 `exit_code` 改名为 `agent.harness.exit_code`；让 `tools_called_total` 带 `status` label。
4. **加固安全**：让 `run_tests` 忽略 policy 给的 argv，固定为 `[sys.executable, "-m", "unittest", "discover", "-s", "tests"]`；`write_file` 只允许写 `src/` 且检查 `realpath(full)`；路径 jail 对所有参数做 `realpath` 检查。为每个绕过方式写一条测试。
5. **统一预算**：把观察预算做成一个对象，由 `BudgetGate` 与 `AgentRun` 共享；执行工具前把剩余额度传给工具，对 `run_tests` 输出按剩余额度截断（保留头尾）。
6. **进阶**：写一个 `LLMPolicy`，把观察拼成 prompt、要求模型输出 JSON tool call 并校验；没有 API key 时用"录制回放"的假模型跑通同一套测试；再加一个 `list_dir` 工具，让 SURVEY 名副其实。

---

## 8. 常见坑

- **HALT 检查放错位置**：在循环开头检查会让"最后一步恰好完成"被误判为预算耗尽。
- **把 harness 能力当成 agent 能力**：本课的修复是硬编码的，demo 通过只说明管道通了。
- **白名单只看工具名**：工具若接受任意 argv/代码，就等于开放了任意执行。
- **把正则黑名单当安全边界**：参数拆分、长短选项、换一个命令就能绕过；`^` 锚点锚的是整个拼接字符串。
- **路径检查只看目录或只看带 `/` 的参数**：符号链接可以逃逸；检查要用最终路径的 `realpath`，或干脆用 OS 级隔离。
- **事后检查预算**：一次大输出就能远超预算；应在执行时限制输出。
- **只用退出码决定 span 状态 / 完全不用**：两种极端都不好，要区分"harness 故障"（拒绝、超时）和"预期中的失败观察"（测试失败）。
- **fixture 被改坏**：一定要在副本上运行 agent；同时记得清理副本。
- **测试目录可写**：agent 可以改测试来"通过"，应限制写路径或校验测试文件哈希。

---

## 9. 测试在验证什么

### 9.1 `tests/test_main.py`（harness 测试）

运行：`cd code && python3 -m pytest -q tests`。实际结果：**16 passed in 0.56s**（每个端到端测试都会启动 unittest 子进程，并在 `/tmp` 留下 scratch 目录）。

| 测试 | 验证的性质 |
|------|-----------|
| `PolicyTransitionTests.test_initial_state` | 初始状态 SURVEY，第一个动作是 `read_file` |
| `test_survey_to_run_tests` | SURVEY 读完文件后进入 RUN_TESTS |
| `test_run_tests_pass_halts` | 首次测试通过（退出码 0）直接 HALT |
| `test_run_tests_fail_to_inspect` | 测试失败进入 INSPECT |
| `test_inspect_to_fix` | INSPECT 之后进入 FIX，且修复文件与内容非空（没有检查内容是否正确，也无法发现两个分支相同） |
| `GateChainTests.test_chain_refuses_unknown_tool` | 不在白名单的 `shell` 被拒绝 |
| `test_chain_refuses_rm_rf` | `run_tests` + `rm -rf /` 被正则 gate 拒绝（说明测试作者也意识到 `run_tests` 可以携带任意 argv） |
| `test_chain_allows_legal_call` | 合法的 `read_file(src/fizz.py)` 放行 |
| `SandboxTests.test_sandbox_runs_echo_in_repo` | sandbox 能在 scratch 仓库里启动 `python -V`（注释提到"use python -m"，但代码用的是 `-V`，注释与代码不符） |
| `test_sandbox_denies_rm` | `rm` 在 denylist，被拒绝 |
| `FixtureRepoTests.test_fixture_repo_has_buggy_fizz` | 复制出的 fixture 含 `range(1, n)` 且不含 `range(1, n + 1)`，保证原始 fixture 没被改坏 |
| `EndToEndTests.test_agent_solves_under_12_steps` | 端到端：解决、步数 < 12、零拒绝、预算未超 |
| `test_agent_emits_one_chat_span_and_one_per_tool_call` | 恰好 1 个 chat span；tool span 数等于步数；每个 tool span 都有 name 与 call id，父 span 是 chat span |
| `test_prometheus_text_includes_tools_called_total` | Prometheus 文本包含 `tools_called_total`、`tool="read_file"` 与 `tool_latency_ms_count` |
| `test_jsonl_export_roundtrip` | JSONL 每行可解析，含 name、attributes、status |
| `test_demo_main_exits_zero` | `run_demo()` 返回 0 |

测试没有覆盖：步数恰好等于预算的边界（会暴露 Q9 的 bug）、gate 拒绝时的 span 行为、观察预算超限路径、`run_tests` 执行任意命令、`write_file` 写测试文件、符号链接逃逸。

### 9.2 `fixture_repo/tests/test_fizz.py`（任务本身的验收测试）

它不是用来测试 harness 的，而是 agent 要"让它通过"的目标。直接在原始 fixture 上运行（`cd code/fixture_repo && python3 -m unittest tests/test_fizz.py`）的实际结果是 **`FAILED (failures=3)`**——这是**预期**的，fixture 必须保持有 bug。agent 在 scratch 副本中把 `range(1, n)` 改成 `range(1, n + 1)` 后，VERIFY 步骤的输出为 `Ran 3 tests ... OK`，退出码 0。注意不要把它当作项目的常规测试纳入 CI，否则会永远失败。
