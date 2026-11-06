# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 26 节 带拒绝列表与路径隔离的 Sandbox 执行器 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（约 6 秒，含两次 2 秒超时）；测试：`python3 -m pytest -q tests` ｜ **依赖**：仅标准库（`subprocess`、`os`、`re`、`tempfile`、`time`、`json`、`dataclasses`、`typing`）；demo 会调用系统的 `ls`、`echo`、`cat`、`sleep`、`yes`（POSIX 环境）

---

## 1. 这份代码在考察什么

这份代码实现了 agent harness 中位于 verification gate（第 25 课）之后的**执行层**：一个包装 `subprocess.run` 的 `Sandbox`，在派生子进程之前做四类拒绝检查，执行时限制 cwd、环境变量、时间和返回的输出大小。

1. **按名称拒绝**：可执行文件 basename 在 denylist 中（`rm`、`sudo`、`curl`、`dd`……）。
2. **按 argv 结构拒绝**：解释器（`python3`、`bash`、`node`……）带 `-c`/`-e` 类标志。
3. **按 shell 元字符拒绝**：`shell=False` 时参数中出现 `;`、`|`、`&`、`>`、`$(` 等。
4. **路径隔离（path jail）**：像路径的参数经 `realpath` 后必须位于 project root 内，挡住 `../` 与符号链接逃逸。
5. **执行约束**：cwd 必须在 root 内；环境变量只保留白名单；墙钟超时；stdout/stderr 截断并打标记。
6. **结构化结果**：`SandboxResult` 用退出码哨兵值（拒绝 −100、超时 −101）和布尔标志描述结果，供可观测性与评估使用。

> 一句话：**把 agent 最常见的危险调用在执行前变成响亮的、结构化的拒绝。** 讲义自己也强调它"不是操作系统意义上的安全边界"；读代码时要特别留意它的绕过面——这些都是面试中关于 sandbox 的经典追问。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DENIED_EXIT_CODE` / `TIMED_OUT_EXIT_CODE` | 常量 | −100 / −101 哨兵退出码 | 结构化结果 |
| `DEFAULT_DENYLIST` | `frozenset` | 24 个被禁可执行文件名 | 名称轴 |
| `DEFAULT_INTERPRETER_BLOCK` | `frozenset` | 14 个解释器名 | argv 轴 |
| `INTERPRETER_FLAG_PATTERNS` | 正则元组 | `-c`、`-e`、`--eval`、`--exec`、`-cu`、`-ce` 精确匹配 | argv 轴 |
| `SHELL_METACHARS` | 字符串元组 | `; \| & > < \` $( ${ )` | 结构轴 |
| `TRUNCATION_MARKER` | bytes | 29 字节的截断标记 | 输出截断 |
| `SandboxResult` | dataclass | 执行结果，`ok` 属性与 `to_dict()` | 结构化结果 |
| `SandboxConfig` | dataclass | root、输出上限、超时、denylist、解释器集合、环境变量白名单；`__post_init__` 规范化 root | 配置 |
| `_check_executable_denylist` | 函数 | basename 查 denylist | 名称轴 |
| `_check_argv_interpreter` | 函数 | 解释器 + 被禁标志 | argv 轴 |
| `_check_shell_metachars` | 函数 | `shell=False` 时查元字符 | 结构轴 |
| `_looks_like_path` / `_check_path_jail` | 函数 | 识别路径参数并做 realpath 前缀检查 | 路径轴 |
| `truncate_stream` | 函数 | 保留前 N 字节 + 标记 | 输出截断 |
| `Sandbox.run` | 方法 | 依次检查 → 校验 cwd → 清洗环境 → `subprocess.run` → 处理超时/找不到命令 → 截断 | 执行器 |
| `find_executable` / `_which` | 函数 | 在 PATH 中查找可执行文件 | demo 跨平台 |
| `_seed_project_root` / `_print_outcome` / `run_demo` | 函数 | 建临时 root、打印徽章、跑一组合法与对抗调用 | 演示 |

数据流：`run_demo` → `_seed_project_root()` 建临时目录（`hello.txt`、`src/main.py`）→ `SandboxConfig(max_output_bytes=512, timeout_seconds=2.0)` → 对每个 argv 调用 `Sandbox.run`：名称 → 解释器 → 元字符 → 路径 → cwd → 环境 → `subprocess.run` → `SandboxResult` → `_print_outcome` 打印 `OK / DENIED / TIMEOUT / EXIT n`。

---

## 3. 逐段精讲

### 3.1 常量：denylist、解释器集合与标志模式

```python
DEFAULT_DENYLIST: frozenset[str] = frozenset({"rm", "sudo", "mkfs", "mkfs.ext4", "mkfs.fat",
    "curl", "wget", "chmod", "dd", "kill", "pkill", "shutdown", "reboot", "halt", "poweroff",
    "eval", "exec", "base64", "nc", "ncat", "telnet", "su", "iptables", "ufw"})

INTERPRETER_FLAG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^-c$"), re.compile(r"^-e$"), re.compile(r"^--eval$"),
    re.compile(r"^--exec$"), re.compile(r"^-cu$"), re.compile(r"^-ce$"),
)

SHELL_METACHARS: tuple[str, ...] = (";", "|", "&", ">", "<", "`", "$(", "${", ")")
```

- 用 `frozenset` 做 O(1) 成员判断，且不可变，避免运行中被改。
- `eval`、`exec` 是 **shell 内建命令**，不是可执行文件；`shell=False` 时它们根本无法作为 `argv[0]` 被执行，放在 denylist 里只有象征意义。
- denylist 是"已知坏名字"的枚举：`unlink`、`shred`、`find -delete`、`mv`、`python3.13`、`busybox` 等都不在其中。
- 标志模式全是 `^...$` **精确匹配**：`-cimport this`、`-Ic`、`-ec`、`-lc`、`-E`、`-p`、`-m` 都不会被识别（测验 Q9 实测了这些绕过）。
- `")"` 被单独列为元字符，带来大量误杀：`echo "f(x)"` 会被拒绝。巧合的是，这也挡住了许多含括号的 `-c` 绕过代码（如 `-cprint('x')`）。

### 3.2 `SandboxResult` 与 `SandboxConfig`

```python
@dataclass
class SandboxResult:
    argv: list[str]
    exit_code: int
    stdout: bytes = b""
    ...
    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.denied and not self.timed_out
```

- `ok` **不考虑 `truncated`**：输出被截断但退出码为 0 时 `ok=True`，demo 中 `echo big (truncated)` 的徽章就是 `OK`。
- `to_dict()` 只输出 stdout/stderr 的**字节数**，不输出内容，适合直接写进日志。
- 讲义描述的退出码：拒绝 −100、超时 −101、截断保留真实退出码并置标志。POSIX 下 −N 表示"被信号 N 杀死"，信号编号不超过 64，所以哨兵值不会冲突。

```python
@dataclass
class SandboxConfig:
    project_root: str
    ...
    denylist: frozenset[str] = field(default_factory=lambda: DEFAULT_DENYLIST)
    env_allowlist: tuple[str, ...] = ("PATH", "HOME", "LANG", "LC_ALL", "TERM")

    def __post_init__(self) -> None:
        self.project_root = os.path.realpath(self.project_root)
```

- `__post_init__` 在 dataclass 自动生成的 `__init__` 之后执行：把 root 规范化一次（例如 macOS 上 `/tmp` 实际是 `/private/tmp`），之后所有比较都基于这个值。
- `field(default_factory=lambda: DEFAULT_DENYLIST)`：frozenset 本身不可变，直接写默认值也可以；用工厂函数是一种防御性写法。
- 环境变量白名单保留了 `PATH` 和 `HOME`：子进程依然能按 PATH 找到所有系统命令，也知道 home 目录在哪里。

### 3.3 名称检查与解释器检查

```python
def _basename(executable: str) -> str:
    return os.path.basename(executable.strip())

def _check_executable_denylist(argv, cfg):
    if not argv:
        return "empty argv"
    name = _basename(argv[0])
    if not name:
        return f"executable {argv[0]!r} has no basename"
    if name in cfg.denylist:
        return f"executable {name!r} is on the denylist"
    return None
```

- 取 basename 让 `/bin/rm`、`/usr/bin/rm` 都归一到 `rm`（讲义："Aliases ... all resolve to the same basename"）。
- 返回值约定：`None` 表示通过，字符串表示拒绝理由——所有 `_check_*` 都遵循这个约定，`run` 里可以统一处理。
- ⚠️ 只看 `argv[0]`：`env rm ...`、`xargs rm`、`nice rm` 等包装器会让真正的命令出现在后面的参数里，完全不被检查（实测 `["env", "rm", "--version"]` 被执行）。
- ⚠️ 按名字而不是按文件身份：把 `rm` 复制成 `myrm` 后执行即可绕过（本例中 `cp /usr/bin/rm myrm` 恰好被 path jail 挡住，但 agent 可以用别的方式得到同样的二进制）。

```python
def _check_argv_interpreter(argv, cfg):
    name = _basename(argv[0])
    if name not in cfg.interpreter_block:
        return None
    for arg in argv[1:]:
        for pat in INTERPRETER_FLAG_PATTERNS:
            if pat.match(arg):
                return (f"interpreter {name!r} invoked with refused flag {arg!r}; "
                        "use a script file instead of -c/-e")
    return None
```

- 双层循环：每个参数 × 每个模式。注意它检查**所有**参数，所以 `python3 script.py -c` 也会被拒（`-c` 可能只是脚本自己的参数）。
- ⚠️ 实测绕过：`python3 -cimport this`、`python3 -Ic "import this"`、`python3.13 -c ...`、`python3 -m this`、`bash -lc`、`sh -ec`、`perl -E`、`node -p` 均被执行。
- ⚠️ 拒绝理由建议 "use a script file instead"，而 agent 往往可以写文件——"先写脚本再执行"与 `-c` 的危险程度相同。

### 3.4 shell 元字符检查

```python
def _check_shell_metachars(argv, shell):
    if shell:
        return None
    for arg in argv:
        for meta in SHELL_METACHARS:
            if meta in arg:
                return (f"argv contains shell metachar {meta!r} in {arg!r}; "
                        "set shell=True to opt in")
    return None
```

- `shell=False` 时 argv 经 `execve` 原样传给程序，这些字符**不会被任何 shell 解释**，检查只能捕捉"模型以为在写 shell"的意图，并误杀 `f(x)`、`?a=1&b=2` 这类合法参数（实测）。
- ⚠️ `shell=True` 时直接放行，而那才是元字符真正危险的场景。
- ⚠️ 拒绝信息 "set shell=True to opt in" 等于告诉模型绕过方法。

`shell=True` 的真实语义：POSIX 上 `subprocess.run(["cmd string", "a", "b"], shell=True)` 执行的是 `/bin/sh -c "cmd string" a b`，**只有第一个元素是命令**。此时：
- `_basename("cat /etc/hostname")` 是 `"hostname"`（最后一个 `/` 之后），不在 denylist；
- path jail 只看 `argv[1:]`，为空；
- 实测 `run(["cat /etc/hostname"], shell=True)` 读出了 root 外的文件，`["echo would-run; rm --version | head -1"]` 也被执行。

### 3.5 Path jail

```python
_PATH_HINT = re.compile(r"[/\\]|^\.{1,2}$")

def _looks_like_path(arg: str) -> bool:
    if not arg:
        return False
    if _PATH_HINT.search(arg):
        return True
    return False
```

- 含 `/` 或 `\`，或恰好是 `.`、`..`，就认为像路径。`"hello.txt"`、`"..."`、`"~"` 都返回 `False`（实测）。docstring 说还会看"常见路径后缀"，代码并没有实现。

```python
def _check_path_jail(argv, cfg):
    root = cfg.project_root
    for arg in argv[1:]:
        if not arg or arg.startswith("-"):
            continue
        if not _looks_like_path(arg) and not os.path.lexists(os.path.join(root, arg)):
            continue
        candidate = arg
        if not os.path.isabs(candidate):
            candidate = os.path.join(root, candidate)
        resolved = os.path.realpath(candidate)
        if resolved != root and not resolved.startswith(root + os.sep):
            return (f"path argument {arg!r} resolves outside project root "
                    f"({resolved!r} not under {root!r})")
    return None
```

逐行理解：

| 步骤 | 作用 | 例子 |
|------|------|------|
| 跳过以 `-` 开头的参数 | 选项不是路径 | `-n` 跳过 |
| `lexists(root/arg)` 补丁 | 无斜杠但在 root 下存在的名字也检查，`lexists` 对"悬空"符号链接也返回真 | `link.txt -> /etc/passwd` 被抓到 |
| 相对路径拼到 root 上 | 以 root 为基准 | `../../etc/passwd` → `root/../../etc/passwd` |
| `realpath` | 解析 `..` 与所有符号链接 | 得到 `/etc/passwd` |
| `== root` 或以 `root + os.sep` 开头 | 防止 `/tmp/proj2` 被当成 `/tmp/proj` 内 | `<root>2/x` 被拒（实测） |

⚠️ 已实测的问题：
- **选项里的路径不检查**：`["cp", "hello.txt", "--target-directory=/tmp/outside"]` 被放行，文件被写到 root 之外。
- **基准不一致**：检查以 root 为基准，执行以 `cwd` 为基准。`run(["cat", "link"], cwd=root/src)`（`src/link -> /etc/hostname`）被放行并读出主机名；`run(["cat", "../hello.txt"], cwd=root/src)` 读的是 root 内文件却被拒。
- **argv[0] 不检查**：可执行文件可以位于任何地方，包括 root 内 agent 新写的文件。
- **TOCTOU**：检查后到程序真正打开文件之间，符号链接可以被替换。
- 讲义说每条拒绝轴都是 "a pure function of the call"，但 path jail 读取了文件系统（`realpath`、`lexists`），结果依赖调用时刻的磁盘状态。

### 3.6 `Sandbox.run`：检查顺序与 cwd

```python
        argv_list = list(argv)
        result = SandboxResult(argv=argv_list, exit_code=DENIED_EXIT_CODE)

        for check in (_check_executable_denylist, _check_argv_interpreter):
            reason = check(argv_list, self.config)
            if reason is not None:
                result.denied = True
                result.reason = reason
                return result

        shell_reason = _check_shell_metachars(argv_list, shell=shell)
        ...
        path_reason = _check_path_jail(argv_list, self.config)
        ...
        work_cwd = cwd or self.config.project_root
        real_cwd = os.path.realpath(work_cwd)
        if real_cwd != self.config.project_root and not real_cwd.startswith(
            self.config.project_root + os.sep):
            result.denied = True
            result.reason = f"cwd {work_cwd!r} not under project root"
            return result
```

- 先构造一个"默认拒绝"的结果对象（`exit_code=-100`），任何检查失败就填上理由直接返回——**fail closed**（默认拒绝）的写法。
- 前两个检查签名相同（`(argv, cfg)`），放进元组循环；元字符检查签名不同（需要 `shell`），单独调用。
- 检查顺序：名称 → 解释器 → 元字符 → 路径 → cwd，从便宜到昂贵，与第 25 课的 gate 链同一思路。
- cwd 同样做 realpath 前缀检查。但如前所述，path jail 没有使用这个 cwd 作为相对路径的基准。

### 3.7 环境清洗与子进程执行

```python
        env: dict[str, str] = {}
        for key in self.config.env_allowlist:
            if key in parent_env:
                env[key] = parent_env[key]

        started = time.perf_counter()
        try:
            proc = subprocess.run(argv_list, shell=shell, cwd=real_cwd, env=env,
                                  capture_output=True, timeout=self.config.timeout_seconds,
                                  input=stdin, check=False)
```

- **环境变量白名单**：`API_KEY`、`AWS_*` 等不会传给子进程（实测 `env` 只输出 `PATH`、`HOME`、`TERM`，本机没有设置 `LANG/LC_ALL`）。传入 `env=` 后，子进程按这个 env 里的 `PATH` 查找可执行文件。
- `capture_output=True` 等价于 `stdout=PIPE, stderr=PIPE`；`check=False` 表示非零退出码不抛异常，由结果对象表达。
- `time.perf_counter()`：单调、高精度计时器，适合测耗时（不受系统时间调整影响）。
- ⚠️ `capture_output` 会把**全部**输出读进内存，截断是之后才做的。实测 `yes y` 在 2 秒超时内让 Python 进程峰值内存达到约 3.4 GB，而最终返回的 stdout 只有 541 字节。

### 3.8 超时与找不到命令

```python
        except subprocess.TimeoutExpired as exc:
            stdout_raw = exc.stdout or b""
            ...
            return SandboxResult(argv=argv_list, exit_code=TIMED_OUT_EXIT_CODE, ...,
                                 timed_out=True, reason=f"wall-clock timeout after {self.config.timeout_seconds}s", ...)
        except FileNotFoundError as exc:
            return SandboxResult(argv=argv_list, exit_code=DENIED_EXIT_CODE, ...,
                                 denied=True, reason=f"executable not found: {exc}", ...)
```

- 超时：`subprocess.run` 内部对子进程调用 `kill()`，POSIX 实现会把超时前已读到的输出放进 `exc.stdout/exc.stderr`，这里再截断后返回。
- ⚠️ **只杀直接子进程**：讲义说 "the sandbox kills the process group"，代码没有 `start_new_session`/`os.killpg`。实测 `sh spawn.sh`（内含 `sleep 43 &`）超时返回后 1 秒，`sleep 43` 仍在运行（状态 `S`）。
- ⚠️ 命令不存在被报告为 `denied=True`、−100，与策略拒绝混在一起；`PermissionError`（argv[0] 是不可执行文件）没有捕获，实测会直接抛异常中断调用方。
- 修复方案（`Popen(start_new_session=True)` + 增量读取 + `os.killpg`）见测验 Q11，已实测：`yes y` 峰值内存降到约 12 MB，孙进程被一并杀掉。

### 3.9 截断

```python
def truncate_stream(buf: bytes, max_bytes: int) -> tuple[bytes, bool]:
    if len(buf) <= max_bytes:
        return buf, False
    head = buf[:max_bytes]
    return head + TRUNCATION_MARKER, True
```

- 返回 `(新内容, 是否截断)` 二元组，调用处用元组解包接收。
- 截断后长度为 `max_bytes + 29`（标记长度），测试中用 `<= max_output_bytes + 200` 给了余量。
- 按字节切片可能把一个多字节 UTF-8 字符切成两半，下游解码要用 `errors="replace"`。
- 标记写进流内容本身，模型能直接看到"输出被截断"；同时 `truncated` 标志给程序读。

### 3.10 Demo 辅助函数

```python
def _which(name: str) -> str | None:
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(entry, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None
```

- 一个简化版 `shutil.which`：遍历 PATH，找第一个存在且可执行的文件。demo 用绝对路径调用 `ls/cat/sleep/yes`，所以打印的标签是手写的短名字。
- `_seed_project_root` 用 `tempfile.mkdtemp(prefix="sandbox-demo-")` 建临时目录，但**从不删除**；测试中的 `_make_root()` 同样如此（实测跑一次测试会在 `/tmp` 留下 20 个 `sandbox-test-*`、1 个 `sandbox-outside-*`、1 个 `sandbox-demo-*`）。
- `_print_outcome` 用链式条件表达式决定徽章，`{label:38s}` 左对齐到 38 个字符宽。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 结构化检查而非 OS 隔离 | 纯标准库、跨平台、易教学；讲义定位为 "development-time guardrail" | 能被多种方式绕过；生产需容器/microVM、seccomp、只读挂载 |
| denylist（拒绝列表）按 basename | 简单、拒绝理由可读 | 不完备（包装器、改名、版本后缀）；应改为命令白名单 + 文件身份 |
| 解释器标志精确匹配 | 实现简单 | 组合选项、连写、`-m`、`-E`、`-p` 绕过；应要求"解释器 + root 内脚本"且不带选项 |
| `shell=False` 时拦元字符 | 捕捉"在写 shell"的意图 | 误杀合法参数；`shell=True` 时全部失效；应禁止 `shell=True` 或 `shlex` 解析后逐 token 检查 |
| realpath + `root + os.sep` 前缀 | 挡住 `..` 与符号链接逃逸、兄弟目录 | 选项内路径、cwd 基准不一致、TOCTOU；最终应由内核在打开时约束 |
| 默认拒绝的结果对象 | fail closed | — |
| 环境变量白名单 | 防止密钥泄漏给子进程 | `HOME` 仍暴露；生产中凭据不应出现在 agent 可达的任何位置 |
| `subprocess.run(timeout=...)` | 一行实现超时 | 只杀直接子进程、不限内存；应用新进程组 + `killpg` + 增量读取或 cgroup |
| 输出事后截断 + 标记 | 模型和程序都能知道发生了截断 | 内存无上界；`ok` 不反映截断 |
| 命令不存在记为 `denied` | 统一的失败表示 | 与策略拒绝混淆；建议独立的 `not_found` 状态，并捕获 `PermissionError` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 带类型注解的模块常量 | `DEFAULT_DENYLIST: frozenset[str] = frozenset({...})` | 注解只是提示；`frozenset` 是不可变集合 |
| `@dataclass` + `__post_init__` | `SandboxConfig.__post_init__` | 自动 `__init__` 之后执行额外初始化（这里规范化路径） |
| `field(default_factory=lambda: ...)` | `denylist: frozenset[str] = field(default_factory=lambda: DEFAULT_DENYLIST)` | 用 lambda 作为默认值工厂 |
| `@property` | `SandboxResult.ok` | 计算属性 |
| `X \| None` 返回类型 | `def _check_...(...) -> str \| None` | "返回理由字符串或 None" 的约定 |
| 仅限关键字参数 | `def run(self, argv, *, shell=False, cwd=None, stdin=None)` | `shell` 等只能用关键字传入，避免位置参数误用 |
| `Sequence[str]` / `Iterable[str]` | `argv: Sequence[str]`、`candidates: Iterable[str]` | 接受 list、tuple 等任意序列/可迭代对象 |
| 函数作为元组元素 | `for check in (_check_executable_denylist, _check_argv_interpreter):` | 函数是一等对象，可以放进容器循环调用 |
| `re.compile` + `match` / `search` | `pat.match(arg)`、`_PATH_HINT.search(arg)` | `match` 从开头匹配，`search` 任意位置 |
| 原始字符串正则 | `r"[/\\]\|^\.{1,2}$"` | 字符类、锚点、量词 `{1,2}` |
| f-string 的 `!r` 与格式宽度 | `f"{argv[0]!r}"`、`f"  - {label:38s} -> {badge}"` | `!r` 加引号显示；`:38s` 左对齐占 38 字符 |
| bytes 字面量与拼接 | `b"\n[sandbox: output truncated]\n"`、`head + TRUNCATION_MARKER` | 子进程输出是 bytes |
| 切片 | `buf[:max_bytes]` | 取前 N 个字节 |
| 返回元组与解包 | `stdout_buf, stdout_truncated = truncate_stream(...)` | 一次返回多个值 |
| `subprocess.run` 关键参数 | `capture_output=True, timeout=..., input=stdin, check=False, env=env, cwd=real_cwd` | 捕获输出、超时、stdin 数据、不因非零退出抛异常 |
| 多个 `except` 分支 | `except subprocess.TimeoutExpired as exc:`、`except FileNotFoundError as exc:` | 不同异常不同处理 |
| `exc.stdout or b""` | 超时分支 | `None` 时用空字节兜底 |
| `time.perf_counter()` | 计算 `duration_ms` | 单调高精度计时 |
| `os.path` 系列 | `realpath`、`lexists`、`isabs`、`join`、`basename`、`isfile`、`access(..., os.X_OK)` | 路径规范化、符号链接存在性、可执行性判断 |
| `with open(...) as fh` | `_seed_project_root` | 上下文管理器，自动关闭文件 |
| `tempfile.mkdtemp(prefix=...)` | `_seed_project_root` | 创建唯一临时目录（需自行删除） |
| 链式条件表达式 | `"OK" if result.ok else "DENIED" if result.denied else ...` | 多分支的一行写法，可读性一般 |
| `sys.exit(run_demo())` | 文件末尾 | 用返回值作为进程退出码 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，Linux，总耗时约 5.7 秒，退出码 0）：

```text
SANDBOX DEMO
project_root=/tmp/sandbox-demo-qw3gcxct

legal calls:
  - ls .                                   -> OK
  - echo hello                             -> OK
  - cat hello.txt                          -> OK
  - cat src/main.py                        -> OK

denied by name:
  - rm -rf .                               -> DENIED
      reason: executable 'rm' is on the denylist
  - sudo apt update                        -> DENIED
      reason: executable 'sudo' is on the denylist
  - curl http://x                          -> DENIED
      reason: executable 'curl' is on the denylist

denied by argv interpreter:
  - python3 -c '...'                       -> DENIED
      reason: interpreter 'python3' invoked with refused flag '-c'; use a script file instead of -c/-e
  - bash -c '...'                          -> DENIED
      reason: interpreter 'bash' invoked with refused flag '-c'; use a script file instead of -c/-e

denied by shell metachar:
  - echo a ; rm -rf                        -> DENIED
      reason: argv contains shell metachar ';' in ';'; set shell=True to opt in

denied by path jail:
  - cat ../../etc/passwd                   -> DENIED
      reason: path argument '../../etc/passwd' resolves outside project root ('/etc/passwd' not under '/tmp/sandbox-demo-qw3gcxct')
  - cat /etc/passwd                        -> DENIED
      reason: path argument '/etc/passwd' resolves outside project root (...)

timeout / truncation:
  - sleep 5 (cap 2)                        -> TIMEOUT
      reason: wall-clock timeout after 2.0s
  - yes y (truncated)                      -> TIMEOUT
      reason: wall-clock timeout after 2.0s
  - echo big (truncated)                   -> OK

{
  "project_root": "/tmp/sandbox-demo-qw3gcxct",
  "sandbox_ok": true
}
```

逐项解读：

- **合法调用**：`ls .` 中 `.` 被识别为路径，realpath 等于 root 本身，放行；`cat src/main.py` 含斜杠，解析后在 root 内。
- **名称拒绝**：三条都在第一道检查就返回，没有派生任何子进程。
- **解释器拒绝**：`-c` 精确匹配。换成 `-cimport this` 或 `-Ic` 就会被执行（测验 Q2、Q9）。
- **元字符拒绝**：`;` 作为独立参数出现。注意即使放行，`shell=False` 下 echo 也只会把 `;` 原样打印，不会执行 `rm`。
- **路径拒绝**：root 位于 `/tmp/sandbox-demo-xxx`，两级 `..` 回到 `/`，所以解析结果是 `/etc/passwd`。
- **`sleep 5`**：2 秒后超时，`exit_code=-101`。
- **`yes y`**：标签写的是 "(truncated)"，徽章却是 `TIMEOUT`——`yes` 永不结束，一定先超时；结果同时 `truncated=True`，stdout 541 字节（512 + 29）。用 `resource.getrusage` 测得这一步让 Python 进程峰值内存约 3.4–3.5 GB：输出在截断前已全部读入内存。
- **`echo big`**：4097 字节输出被截断为 541 字节，但退出码 0，徽章是 `OK`——`ok` 不看截断。
- **JSON 尾巴**：`sandbox_ok: true` 是写死的，不代表任何检查结果；demo 总是返回 0。
- demo 结束后临时目录仍留在 `/tmp`，需要手动清理。

---

## 7. 动手改一改

1. 给 `SandboxResult` 增加 `status` 字段（`ok / denied / not_found / timed_out / truncated / error`），把 `FileNotFoundError` 从 `denied` 中分离出来，并捕获 `PermissionError`；修改 `_print_outcome` 让截断显示为 `TRUNCATED`。
2. 让 `_check_path_jail` 接收实际 `cwd`，以它为相对路径基准；同时解析 `--opt=value` 与 `-oVALUE` 形式。为测验 Q10 的三个场景各写一个测试。
3. 用 `Popen(start_new_session=True)` + `selectors` 增量读取 + `os.killpg` 重写执行部分（参考测验 Q11），写测试验证：`yes y` 很快结束且 stdout 不超过上限，`sh spawn.sh` 超时后不留孙进程。
4. 把解释器检查改为结构约束：解释器后必须紧跟一个位于 root 内的 `.py/.sh` 文件且之前不得有任何选项；把 `env`、`xargs`、`nice`、`timeout` 加入"包装器"列表并递归检查被包装的命令；用 `re.fullmatch(r"python[\d.]*", name)` 处理版本后缀。
5. 禁止 `shell=True`，或改成：`shlex.split` 解析命令串，拒绝含 `;`、`&&`、`||`、`|`、重定向、命令替换的输入，再对 token 列表走与 `shell=False` 相同的所有检查；同时修改拒绝信息，不再提示 "set shell=True to opt in"。
6. 进阶：在 Linux 上用 `unshare`/容器运行同一批 demo 调用（只读挂载项目目录、禁网），对比哪些攻击在结构检查失效后仍被 OS 层挡住。

---

## 8. 常见坑

- **以为 `shell=False` 下元字符危险**：它们不会被解释；真正危险的是 `shell=True`，而本节在 `shell=True` 时几乎所有检查都失效。
- **`subprocess.run(list, shell=True)`**：POSIX 上只有第一个元素是命令，其余是 `$0`、`$1`……很多人以为会拼成一条命令。
- **字符串前缀当路径前缀**：`startswith(root)` 会把 `/tmp/proj2` 当成 `/tmp/proj` 内部；必须加 `os.sep`。
- **用字面路径而不是 realpath**：符号链接逃逸。
- **相对路径基准不一致**：检查用 root、执行用 cwd，既漏判又误判。
- **忽略选项中的路径**：`--output=/etc/x` 之类完全不被检查。
- **超时只杀直接子进程**：后台孙进程会存活；需要进程组或 cgroup。
- **`capture_output` + 事后截断**：内存无上界，`yes` 两秒就能吃掉数 GB。
- **把"找不到命令"算作策略拒绝**：污染拒绝统计。
- **测试与 demo 不清理临时目录**：长期运行 CI 会在 `/tmp` 堆积大量目录。
- **拒绝信息泄露绕过方法**：模型会照着做。

---

## 9. 测试在验证什么

运行方式：在 `code/` 目录下执行 `python3 -m pytest -q tests`（或 `python3 -m unittest discover -s tests`）。实际运行结果：**26 passed**（约 6–7 秒，主要耗时在 `test_demo_main_exits_zero` 中的两次 2 秒超时；该测试同样会触发 `yes y` 的 GB 级内存占用）。测试用 `tempfile.mkdtemp` 建目录但不清理，每次运行会在 `/tmp` 留下 22 个目录。

| 测试类 / 测试 | 验证的性质 |
|-------------|-----------|
| `DenylistPureChecks.test_denies_rm` / `test_denies_full_path_rm` / `test_allows_echo` | `rm` 与 `/bin/rm` 都按 basename 被拒，理由含 `denylist`；`echo` 放行 |
| `InterpreterChecks`（4 个） | `python3 -c`、`bash -c`、`node -e` 被拒（理由含解释器名）；`python3 script.py` 放行 |
| `ShellMetacharChecks`（4 个） | `a;`、`a\|grep` 被拒；`shell=True` 时跳过检查；`echo hello` 放行 |
| `PathJailChecks.test_relative_inside_root_allowed` | `f.txt`（存在于 root，经 `lexists` 进入检查）解析在 root 内，放行 |
| `PathJailChecks.test_traversal_outside_root_denied` / `test_absolute_outside_root_denied` | `../../etc/passwd`、`/etc/passwd` 被拒，理由含 `outside project root` |
| `PathJailChecks.test_flag_arg_skipped` | 以 `-` 开头的参数不做路径检查（这也正是 `--target-directory=/x` 绕过的来源） |
| `PathJailChecks.test_slashless_symlink_to_outside_is_denied` | root 内无斜杠的符号链接 `link.txt` 指向外部文件时被拒；平台不支持符号链接时跳过 |
| `TruncateTests`（2 个） | 未超限原样返回；超限时以前 50 字节开头、包含 `truncated` 标记 |
| `SandboxIntegrationTests.test_echo_runs_ok` | 真实执行 `echo hello`，`ok` 为真，stdout 含 `hello` |
| `test_rm_refused` / `test_bash_c_refused` / `test_traversal_refused` | 端到端拒绝：退出码 −100、理由含 `interpreter` / `outside project root` |
| `test_truncation_fires_on_large_stdout` | 4096 字节输出被截断，长度不超过上限 + 200 |
| `test_timeout_fires` | `sleep 2` 在 0.3 秒超时，`timed_out` 为真、退出码 −101 |
| `test_demo_main_exits_zero` | `run_demo()` 返回 0（由于 demo 写死返回 0，这只验证"不抛异常"） |
| `test_interpreter_block_covers_canonical_set` | 解释器集合包含 `python3`、`bash`、`node` |

覆盖空白：
- 解释器检查的绕过（`-cimport this`、`-Ic`、`python3.13`、`-m`、`perl -E`、`node -p`、`env` 包装）；
- `shell=True` 下的整体失效；
- 选项内路径、cwd 基准不一致的绕过与误杀；
- 超时后孙进程存活、内存无上界；
- `PermissionError` 未捕获、`not found` 被算作 `denied`。
