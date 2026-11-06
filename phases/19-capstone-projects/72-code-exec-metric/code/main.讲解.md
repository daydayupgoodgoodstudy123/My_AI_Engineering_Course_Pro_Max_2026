# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 72 节 代码执行评估指标 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（测试：`python3 -m pytest -q`） ｜ **依赖**：标准库（`subprocess`、`select`、`json`、`re`、`math` 等）+ 第三方 `numpy`（仅用于求平均）；需要类 Unix 系统（`select` 作用于管道）

---

## 1. 这份代码在考察什么

代码生成任务的"正确"只有一个定义：**通过测试**。这份代码搭出评估 harness 的执行层：

1. **抽取**：从模型的自由文本里取出第一个 ```` ``` ```` 代码块（与第 70 课的 `extract_code_block` 对应）。
2. **隔离执行**：把候选代码和断言拼成一个 runner 脚本，交给**全新的** Python 子进程（`python -I -c script`），配墙钟超时、256 KB 输出上限、import denylist。
3. **计分**：分数 = 通过断言数 / 断言总数；五种退出码（`pass / assertion_fail / syntax_error / timeout / error`）作为元数据。
4. **pass@k**：HumanEval 式无偏估计，对多题取平均。

讲义的核心论断："The wall-clock timeout and the output cap are the load-bearing controls"——denylist 只是兜底。读代码时要带着两个问题：**哪些失败被可靠地转化成了 0 分？哪些地方可以被候选代码钻空子？**

> 一句话：**把"不可信代码跑一遍看能不能过测试"做成一个永远返回同一种形状、永远不会拖垮宿主的函数**——并清楚它离真正的沙箱还差多远。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CODE_BLOCK_RE` | 正则常量 | 匹配带可选语言标签的代码块 | 代码抽取 |
| `DEFAULT_TIMEOUT_S` / `MAX_TIMEOUT_S` / `OUTPUT_CAP_BYTES` | 常量 | 3s / 30s / 256 KB | 资源控制 |
| `EXIT_*` / `EXIT_CODES` | 常量 | 五种退出码 | 失败分类 |
| `ExecResult` | dataclass | 分数、退出码、通过数、总数、细节、逐条结果 | 统一结果形状 |
| `RUNNER_TEMPLATE` | 多行字符串 | 子进程里运行的脚本：denylist、编译、执行、逐条 eval、写 JSON | runner 模板 |
| `extract_code` | 函数 | 代码块 → 字符串；有反引号但匹配失败 → `None`；无反引号 → 原文 | 抽取 |
| `_build_runner` | 私有函数 | 用 `repr` 把代码和断言安全地嵌入模板 | 脚本生成 |
| `run_candidate` | 函数 | 启动子进程，`select` 循环读取，超时/溢出处理，解析 JSON | 执行器 |
| `score_code_exec` | 函数 | 抽取 + 执行，返回分数 | 指标入口 |
| `pass_at_k` | 函数 | 单题无偏 pass@k | pass@k |
| `pass_at_k_estimator` | 函数 | 多题平均 | pass@k 聚合 |
| `_demo_examples` / `demo` | 函数 | 5 个例子覆盖 4 种退出码 + pass@k 演示 | 自检 |

数据流：`prediction` → `extract_code` → `_build_runner(code, assertions)` → `Popen([python, -I, -c, script])` → 子进程：替换 `__import__` → `compile` → `exec` → 逐条 `eval` → `stdout` 写 JSON → 父进程：`select` 读取（截止时间、256 KB）→ `json.loads` → `ExecResult(score, exit_code, ...)`。

---

## 3. 逐段精讲

### 3.1 常量与结果形状

```python
DEFAULT_TIMEOUT_S = 3.0
MAX_TIMEOUT_S = 30.0
OUTPUT_CAP_BYTES = 256 * 1024

EXIT_CODES = (EXIT_PASS, EXIT_ASSERTION_FAIL, EXIT_SYNTAX_ERROR, EXIT_TIMEOUT, EXIT_ERROR)

@dataclass
class ExecResult:
    score: float
    exit_code: str
    passed: int
    total: int
    detail: str = ""
    per_assertion: list[bool] = field(default_factory=list)
```

- 讲义："The runner returns the same shape no matter what fails"。无论超时、崩溃还是语法错误，调用方拿到的都是 `ExecResult`，不会有异常冒泡到 harness。
- 退出码用字符串常量而不是 `Enum`，方便直接写进 JSON 报告。
- **注意**：讲义说 `timeout_s` 可以通过 `task.metadata.timeout_s` 按任务配置，并且"the validator from lesson 70 caps the value at thirty seconds"。实际上第 70 课的校验器不检查 `metadata` 的内容；30 秒上限是在本文件 `run_candidate` 里用 `min(..., MAX_TIMEOUT_S)` 实现的。

### 3.2 runner 模板（上）：denylist

```python
_DENIED_MODULES = {
    'subprocess', 'socket', 'shutil', 'requests', 'urllib',
    'urllib.request', 'urllib.error', 'urllib.parse', 'ctypes',
    'http.client', 'asyncio.subprocess',
}

_real_import = _builtins.__import__
def _guarded_import(name, *args, **kwargs):
    base = name.split('.')[0]
    if name in _DENIED_MODULES or base in _DENIED_MODULES:
        raise ImportError("denied module: %s" % name)
    return _real_import(name, *args, **kwargs)
_builtins.__import__ = _guarded_import

import os as _os
def _denied_system(_cmd):
    raise OSError("os.system denied")
_os.system = _denied_system
```

- **机制**：`import x` 语句最终调用 `builtins.__import__`。把它换成带检查的版本，所有后续 `import`（包括标准库内部的 `import`）都要过这道关。`base` 检查让 `import urllib.request` 因首段 `urllib` 被拒。
- `os.system` 不是模块，没法靠 import 拦截，于是直接把 `os` 模块上的函数替换掉——候选代码 `import os` 拿到的是同一个模块对象（`sys.modules` 缓存），看到的就是被替换后的版本。
- `json, sys, traceback` 在 hook 安装**之前**导入，runner 自己不受影响。
- **注意**：讲义说 runner "rewrites imports of dangerous modules to a stub that raises `ImportError("denied")`"，代码实际是 import hook，报错信息为 `denied module: <name>`。
- **注意**：**误伤**（实测）：`import tempfile` → 内部 `import shutil` 被拒；`import asyncio` → 内部导入 `socket` 被拒。合法代码因依赖链被判 `error`。
- **注意**：**绕过**（实测均得 `pass`）：
  - `importlib.import_module("socket")`：不经过 `builtins.__import__`；
  - `import posix; posix.system(...)`：只替换了 `os.system`，底层 `posix.system` 还在；
  - `builtins.__import__.__globals__['_real_import']`：hook 函数的全局命名空间里就放着原始 `__import__`，装回去即可。
- 讲义自己也说："We do not pretend this is bulletproof. Determined adversarial code can escape any in-process sandbox in Python."

### 3.3 runner 模板（下）：编译、执行、逐条断言

```python
CODE = __PLACEHOLDER_CODE__
ASSERTIONS = __PLACEHOLDER_ASSERTIONS__

ns = {}
status = {"exit_code": "pass", "results": [], "detail": ""}
try:
    compiled = compile(CODE, "<candidate>", "exec")
except SyntaxError as exc:
    status["exit_code"] = "syntax_error"
    ...
try:
    exec(compiled, ns)
except Exception as exc:
    status["exit_code"] = "error"
    status["detail"] = "exec error: %s" % exc
    ...
passed = 0
for assertion in ASSERTIONS:
    try:
        ok = bool(eval(assertion, ns))
    except Exception as exc:
        ok = False
        status["detail"] = "assertion error: %s" % exc
    status["results"].append(ok)
    if ok:
        passed += 1
```

- **三阶段**对应三种失败：
  - `compile` 失败 → `syntax_error`（只有语法错误才算）；
  - `exec` 顶层抛异常 → `error`（包括 denylist 的 `ImportError`、`import numpyy` 这种拼错模块名、顶层 `raise`）。**注意**：讲义把 "did not import" 也归入 `syntax_error`，代码中它是 `error`。
  - 断言 `eval` 抛异常 → 该条记为失败（`assertion_fail`），而不是 `error`。
- `compile` 与 `exec` 分开，才能把语法错误和运行时错误区分成两种退出码。`"<candidate>"` 是伪文件名，出现在报错信息里（如 `SyntaxError: expected ':' (<candidate>, line 1)`）。
- `exec(compiled, ns)`：用一个**新字典**当全局命名空间，候选代码定义的 `add` 等名字都落在 `ns` 里；`eval(assertion, ns)` 在同一个命名空间里求值断言。`exec` 会自动往 `ns` 里放一个 `__builtins__`。
- 断言必须是**表达式**：`eval("assert f() == 1")` 会报语法错误，被记为失败（实测 `assertion_fail`，detail 为 `invalid syntax`）。
- `bool(...)` 判定真值：断言写成 `"f()"` 时返回 `[1]` 也算通过；候选代码返回一个 `__eq__` 永远为真的对象，就能让所有 `== 期望值` 断言通过（实测 `pass 1.0`）。
- `except Exception` 不捕获 `KeyboardInterrupt`、`SystemExit`。候选代码 `sys.exit(0)` 会让进程在写 JSON 前退出，父进程拿到空 stdout → `status = {}` → `error`、detail 为空。
- `detail` 只保留**最后一条**失败断言的异常信息。

结尾的退出码判定：

```python
if passed < len(ASSERTIONS):
    status["exit_code"] = "assertion_fail" if passed > 0 or len(ASSERTIONS) > 0 else status["exit_code"]
    if passed == len(ASSERTIONS):
        status["exit_code"] = "pass"
elif len(ASSERTIONS) > 0:
    status["exit_code"] = "pass"
sys.stdout.write(json.dumps(status))
```

- 父进程保证断言非空，所以这段逻辑等价于 `"pass" if passed == len(ASSERTIONS) else "assertion_fail"`；条件表达式中的 `or len(...) > 0` 与内层 `if passed == len(...)` 都是不会生效的冗余分支（测验 Q12）。
- **注意**：**结果信道与候选代码共用 stdout**：候选代码里任何 `print` 都会把文本混进 JSON 前面，父进程解析失败 → `error / non-json output`（实测：功能正确但带一行 `print('debug')` 的代码得 0 分）。同理，候选代码可以自己写一段 `{"exit_code":"pass",...}` 再 `os._exit(0)`，在断言根本没运行的情况下拿到满分（实测）。

### 3.4 `extract_code` 与 `_build_runner`

```python
def extract_code(text: str) -> str | None:
    m = CODE_BLOCK_RE.search(text)
    if m:
        return m.group(1)
    if "```" in text:
        return None
    return text

def _build_runner(code: str, assertions: list[str]) -> str:
    script = RUNNER_TEMPLATE
    script = script.replace("__PLACEHOLDER_CODE__", repr(code))
    script = script.replace("__PLACEHOLDER_ASSERTIONS__", repr(list(assertions)))
    return script
```

- 三种情况：匹配到代码块 → 块内容；有反引号却匹配失败（未闭合、语言标签后有空格、```` ```c++ ````）→ `None`；完全没有反引号 → 把整段文本当代码。
- **注意**：与第 70 课 `post_process(..., "extract_code_block")` 不同：那里匹配失败时**原样返回**。第 75 课 runner 写 `extract_code(processed) or processed`，又把 `None` 换回了原文。
- **用 `repr` 嵌入**是关键的安全细节：`repr(code)` 生成一个合法的 Python 字符串字面量，代码里的引号、换行、反斜杠都被正确转义，候选代码不可能"跳出"字符串、篡改 runner 本身的语句。如果用 f-string 直接拼接源码，候选代码里一个 `"""` 就能注入任意 runner 级代码。
- **注意**：两次 `str.replace` 有先后顺序问题：代码先被嵌入，若候选代码里恰好含有 `__PLACEHOLDER_ASSERTIONS__` 字样，第二次替换会把断言列表的 `repr`（带单引号）塞进代码的字符串字面量里，**破坏 runner 的语法**。实测 `x = "__PLACEHOLDER_ASSERTIONS__"` 这样的候选得到 `error / subprocess exit 1: SyntaxError`。插入的内容来自任务作者而非候选代码，所以候选代码借此只能让自己得 0 分、无法注入语句；但它说明"字符串模板 + replace"是脆弱的——更稳妥的做法是先替换断言、再替换代码，或者干脆通过 stdin/文件把数据以 JSON 传给固定的 runner 脚本。

### 3.5 `run_candidate`（上）：启动子进程

```python
def run_candidate(code, assertions, timeout_s=DEFAULT_TIMEOUT_S) -> ExecResult:
    if not assertions:
        return ExecResult(0.0, EXIT_ERROR, 0, 0, detail="no assertions provided")
    timeout_s = min(max(0.1, float(timeout_s)), MAX_TIMEOUT_S)
    script = _build_runner(code, assertions)
    try:
        proc = subprocess.Popen(
            [sys.executable, "-I", "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception as exc:
        return ExecResult(0.0, EXIT_ERROR, 0, len(assertions), detail=f"spawn error: {exc!r}")
```

- 空断言直接判 `error`：没有断言就无法定义"正确"。
- `min(max(0.1, t), 30.0)` 把超时**夹**在 [0.1, 30] 秒。
- `sys.executable`：用与当前相同的解释器，避免 PATH 上的 `python` 是另一个版本。
- `-I`（isolated mode）：忽略 `PYTHON*` 环境变量、不加入用户 site-packages、不把当前目录/脚本目录加入 `sys.path`——候选代码无法通过在工作目录放一个同名模块来劫持导入。
- `-c script`：脚本作为命令行参数传入。讲义说"pass the code on stdin"，代码实际用 `-c`；超长脚本可能触及操作系统的命令行长度上限（Linux 单个参数约 128 KB）。
- **注意**：讲义说 runner 用 `subprocess.run(..., timeout=t)` 并捕获 `TimeoutExpired`；代码用的是 `Popen` + 手写循环，因为 `subprocess.run` 无法在读取过程中实施"累计输出超过 256 KB 就杀进程"的控制。

### 3.6 `run_candidate`（中）：截止时间 + 非阻塞读取

```python
    with proc:
        deadline = time.monotonic() + timeout_s
        stdout_chunks: list[bytes] = []
        stdout_bytes = 0
        overflow = False
        timed_out = False
        fd = proc.stdout
        os.set_blocking(fd.fileno(), False)
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                r, _, _ = select.select([fd], [], [], min(remaining, 0.1))
                if r:
                    chunk = fd.read(8192)
                    if chunk is None:
                        continue
                    if chunk == b"":
                        break
                    stdout_bytes += len(chunk)
                    if stdout_bytes > OUTPUT_CAP_BYTES:
                        overflow = True
                        break
                    stdout_chunks.append(chunk)
                elif proc.poll() is not None:
                    tail = fd.read()
                    ...
                    break
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=1.0)
            stderr_bytes = proc.stderr.read() if proc.stderr else b""
```

- **`time.monotonic()`**：单调时钟，不受系统时间调整影响，适合算截止时间。
- **`os.set_blocking(..., False)`**：管道设为非阻塞，`read` 没数据时返回 `None` 而不是卡住。
- **`select.select([fd], [], [], timeout)`**：最多等 `min(剩余时间, 0.1)` 秒，有数据可读时返回。每 0.1 秒醒来一次检查截止时间和子进程状态。
- 三种退出循环的方式：
  1. 读到 `b""`（EOF）：子进程关闭了 stdout，正常结束；
  2. 累计字节超过 256 KB：`overflow = True`；
  3. 到达截止时间：`timed_out = True`。
- `elif proc.poll() is not None`：子进程已退出但 `select` 没报告可读时，把剩余数据一次读完。
- `finally` 中如果子进程还活着就 `kill()`（SIGKILL），然后最多等 1 秒回收，避免僵尸进程。`with proc:` 保证管道最终被关闭。
- **注意**：**stderr 不在 `select` 里**，直到 `finally` 才读。候选代码往 stderr 写超过管道缓冲区（Linux 上通常 64 KB）的数据就会阻塞，表现为**假超时**（实测写 10 MB 到 stderr → 3 秒后 `timeout`）。
- **注意**：`select` 在 Windows 上只支持 socket，这段代码只能在类 Unix 系统上运行；讲义末尾也提到不同平台对 SIGKILL 的处理不同，建议放进 Docker。
- 超时包含**解释器启动时间**（本机每次约 0.05 秒）：`timeout_s=0.01` 会被夹到 0.1 秒，正确代码仍能通过（实测 `pass`），但更紧的预算下可能误判。

### 3.7 `run_candidate`（下）：把各种结局归一

```python
    if timed_out:
        return ExecResult(0.0, EXIT_TIMEOUT, 0, len(assertions), detail=f"timeout after {timeout_s:.2f}s")
    if overflow:
        return ExecResult(0.0, EXIT_ERROR, 0, len(assertions), detail="output overflow")
    stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
    if proc.returncode != 0:
        ...
        return ExecResult(0.0, EXIT_ERROR, 0, len(assertions), detail=f"subprocess exit {proc.returncode}: {stderr_text[:200]}")
    try:
        status = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        return ExecResult(0.0, EXIT_ERROR, 0, len(assertions), detail="non-json output")

    exit_code = status.get("exit_code", EXIT_ERROR)
    results = list(status.get("results", []))
    passed = sum(1 for r in results if r)
    total = len(assertions)
    score = passed / total if total else 0.0
    if exit_code not in EXIT_CODES:
        exit_code = EXIT_ERROR
    if exit_code == EXIT_PASS and passed < total:
        exit_code = EXIT_ASSERTION_FAIL
    if exit_code == EXIT_ASSERTION_FAIL and passed == total and total > 0:
        exit_code = EXIT_PASS
    return ExecResult(score, exit_code, passed, total, detail=detail, per_assertion=results)
```

- 优先级：超时 > 溢出 > 非零返回码 > JSON 解析失败 > 正常。前四种一律 0 分。
- `total` 用父进程自己的 `len(assertions)`，不信任子进程报告的数量；但 `passed` 来自子进程的 `results`，所以伪造 `results` 仍然有效。
- `errors="replace"` 解码：非法 UTF-8 字节被替换成 `�`，不会因编码问题抛异常。
- 子进程被信号杀死时返回码为负数（如 `KeyboardInterrupt` 导致 `-2`）。
- `score_code_exec` 只是 `extract_code` + `run_candidate(...).score`，抽取失败（`None`）时直接 0 分。

### 3.8 pass@k

```python
def pass_at_k(n: int, c: int, k: int) -> float:
    if n < 0 or c < 0 or k <= 0:
        raise ValueError("n, c >= 0 and k > 0")
    if c > n:
        raise ValueError("c cannot exceed n")
    if k > n:
        return float(c > 0)
    if n - c < k:
        return 1.0
    log_prob = 0.0
    for i in range(k):
        log_prob += math.log(n - c - i) - math.log(n - i)
    return float(1.0 - math.exp(log_prob))
```

- 数学：`1 − C(n−c, k)/C(n, k) = 1 − Π_{i=0}^{k−1} (n−c−i)/(n−i)`。在 log 空间累加，n = 200、k = 100 时也不会溢出。实测 `pass_at_k(200, 10, 1) = 0.05`、`k=10` 约 0.409、`k=100` 约 0.999。
- `n − c < k`：任何 k 个样本中必然有通过的，返回 1（同时避免 `log(0)`）。
- `k > n`：组合公式无定义，代码返回 `c > 0`，是一个乐观的近似；更严谨的做法是要求 `n ≥ k`。
- `pass_at_k_estimator` 对每道题算 pass@k，再用 `np.mean` 求平均——这是 numpy 在本文件中唯一的用途，换成 `statistics.fmean` 就能去掉第三方依赖。
- 第三题 c = 0 → 所有 k 都是 0；`pass_at_k(10, 0, 5)`：`n − c = 10 ≥ 5`，乘积为 1，结果 0。

### 3.9 demo

- 5 个例子分别期望：`pass`、`assertion_fail`、`syntax_error`、`timeout`（`time.sleep(10)` + 0.6 秒预算）、`error`（`import subprocess` 被拒）。
- **注意**：名为 `one_assertion_fails` 的例子，`add` 返回 `a + b + 1`，**两条断言都失败**，所以期望分数是 0.0。真正的"部分通过"见测试 `test_partial_assertions_fail`。
- 最后用三道题、每题 10 个样本演示 pass@1/5/10。
- 未使用的导入：`tempfile`、`Iterable`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 每个候选一个全新子进程 | 超时可杀、崩溃不影响宿主、状态不串 | 每次约 50 ms 启动开销；生产用预热容器池 |
| `python -I -c` | 隔离环境变量与 `sys.path`，不落盘 | 命令行长度有限；讲义说用 stdin，实现用 `-c` |
| `repr` 嵌入代码和断言 | 防止候选代码注入 runner 语句 | 依赖 `repr` 的正确性；更稳妥的是通过文件/stdin 传数据 |
| `builtins.__import__` hook | 实现简单、跨模块生效 | 可被 `importlib`、`posix`、`__globals__` 绕过；会误伤 `tempfile`/`asyncio`；生产用容器 + seccomp |
| `select` + 非阻塞读 + 截止时间 | 同时实现超时与输出上限 | 仅类 Unix；stderr 未纳入，可能假超时 |
| 结果写到 stdout | 不需要额外文件或管道 | 候选 `print` 导致 0 分；结果可被伪造；应使用独立信道或定界符 + 进程外判定 |
| 断言用 `eval` 表达式 | 任务作者写起来简单 | 不能写语句；真值判定宽松；讲义建议最终换成真正的单元测试文件 |
| 分数为通过比例 | 部分正确有部分分 | 多数基准（HumanEval）按"全部通过"计 0/1；两者不可混比 |
| pass@k 连乘 + log | 数值稳定 | `k > n` 时返回乐观值 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 原始多行字符串 | `RUNNER_TEMPLATE = r""" ... """.strip()` | `r` 防止反斜杠转义；`.strip()` 去掉首尾空行 |
| `str.replace` 模板 | `script.replace("__PLACEHOLDER_CODE__", repr(code))` | 简单的占位符替换 |
| `repr()` 生成字面量 | `repr(code)`、`repr(list(assertions))` | 得到可以被 Python 重新解析的字符串/列表字面量 |
| `%` 格式化 | `"denied module: %s" % name` | 旧式格式化；模板里避免用 f-string 的花括号与 JSON 混淆 |
| `*args, **kwargs` | `def _guarded_import(name, *args, **kwargs)` | 接收并原样转发任意参数 |
| 猴子补丁（monkey patch） | `_builtins.__import__ = _guarded_import`、`_os.system = _denied_system` | 运行时替换模块属性 |
| `compile` / `exec` / `eval` | `compile(CODE, "<candidate>", "exec")`、`exec(compiled, ns)`、`eval(assertion, ns)` | 编译源码、执行语句、求值表达式；`ns` 作全局命名空间 |
| 多个 `except` 分支 | `except SyntaxError` … `except Exception` | 先捕获具体异常，再兜底 |
| `subprocess.Popen` | `Popen([...], stdout=PIPE, stderr=PIPE)` | 启动子进程并接管其输出 |
| `with proc:` | `with proc:` | `Popen` 支持上下文管理，退出时关闭管道并等待 |
| `select.select` | `select.select([fd], [], [], 0.1)` | 等待文件描述符可读，带超时 |
| `os.set_blocking` | `os.set_blocking(fd.fileno(), False)` | 设置非阻塞 I/O |
| `time.monotonic()` | `deadline = time.monotonic() + timeout_s` | 单调时钟，算时间差专用 |
| `try/finally` | 循环外的 `finally: proc.kill()` | 无论正常还是异常都执行清理 |
| `bytes` 拼接与解码 | `b"".join(chunks).decode("utf-8", errors="replace")` | 高效拼接字节；容错解码 |
| 元组解包占位 | `r, _, _ = select.select(...)` | `_` 表示不关心的值 |
| 条件表达式 | `passed / total if total else 0.0` | 防止除零 |
| `@dataclass` + `field` | `per_assertion: list[bool] = field(default_factory=list)` | 可变默认值 |
| 联合类型注解 | `def extract_code(text: str) -> str \| None` | 返回字符串或 `None` |
| 生成器表达式计数 | `sum(1 for r in results if r)` | 数真值个数 |
| `math.log` 累加 | `log_prob += math.log(n - c - i) - math.log(n - i)` | 用对数把连乘变成连加 |
| f-string 格式符 | `{result.exit_code:14s}`、`{result.score:.2f}`、`{exc!r}` | 宽度、精度、repr |
| 字典 `.get` 默认值 | `ex.get("timeout_s", DEFAULT_TIMEOUT_S)` | 可选字段 |
| `or` 提供默认值 | `extract_code(ex["prediction"]) or ""` | 左侧为 `None`/空时取右侧 |

---

## 6. 运行结果解读

实际运行（Python 3.13，Linux）：

```text
$ time python3 main.py
  [OK] passes_all               exit=pass           score=1.00 detail=
  [OK] one_assertion_fails      exit=assertion_fail score=0.00 detail=
  [OK] syntax_error             exit=syntax_error   score=0.00 detail=SyntaxError: expected ':' (<candidate>, line 1)
  [OK] timeout                  exit=timeout        score=0.00 detail=timeout after 0.60s
  [OK] denylist_subprocess      exit=error          score=0.00 detail=exec error: denied module: subprocess
  pass@1=0.100  pass@5=0.426  pass@10=0.667

real    0m0.835s
```

逐项解读：

- **passes_all**：3 条断言全部通过 → `pass`、1.00。
- **one_assertion_fails**：两条断言都失败 → `assertion_fail`、0.00；`detail` 为空，因为断言只是返回 `False`，没有抛异常。
- **syntax_error**：`def add(a, b)` 缺冒号，`compile` 阶段失败；Python 3.13 的报错信息是 `expected ':'`。
- **timeout**：`time.sleep(10)` 在 0.6 秒预算下被杀。整个 demo 只花了 0.84 秒，说明超时控制确实生效、没有等满 10 秒。
- **denylist_subprocess**：`import subprocess` 在 `exec` 阶段被 hook 拒绝 → `error`。
- **pass@k**：三题 c = 2、1、0（n = 10）。pass@1 = (0.2 + 0.1 + 0)/3 = 0.100；pass@5 = (0.778 + 0.5 + 0)/3 = 0.426；pass@10 = (1 + 1 + 0)/3 = 0.667。
- 退出码 0：5 个例子的退出码和分数都符合预期。

补充实测（不在 demo 中，用来理解边界）：

| 候选 | 结果 |
|------|------|
| 正确代码 + 函数内 `print('debug')` | `error`，`non-json output`，0 分 |
| `import tempfile` | `error`，`denied module: shutil` |
| `importlib.import_module('socket')` | `pass`（绕过） |
| `posix.system('true')` | `pass`（绕过） |
| `while True: print('x'*1000)` | `error`，`output overflow`（0.09 秒） |
| 向 stderr 写 10 MB | `timeout`（3.00 秒，假超时） |
| 写伪造 JSON + `os._exit(0)` | `pass`，1.0（结果伪造） |

---

## 7. 动手改一改

1. **修复结果信道**：给 runner 的输出加定界标记（如 `\n__AIE_RESULT__` + JSON），父进程只解析最后一个标记之后的内容，让 `print` 不再导致 0 分；确认无限打印仍被 256 KB 上限截断（参考测验 Q9）。
2. **修复 stderr 假超时**：把 `stderr` 改为 `subprocess.DEVNULL`，或纳入 `select` 并计入同一个输出上限；用"写 10 MB 到 stderr"的候选验证结果变成 `output overflow` 或正常完成。
3. **区分导入错误**：在 runner 中单独捕获 `ImportError`，新增 detail 前缀 `import error:`（或新增退出码），让报告能区分"代码错误"和"依赖/denylist 问题"。
4. **加资源限制**：在 `Popen` 中用 `preexec_fn` 调用 `resource.setrlimit` 限制内存（`RLIMIT_AS`）和 CPU 秒数（`RLIMIT_CPU`），测试 `x = [0] * 10**10` 这样的候选。
5. **严格的 pass@k**：让 `pass_at_k` 在 `k > n` 时抛 `ValueError`，并补测试；再写一个函数，从同一批样本同时给出 k = 1、10、100 的结果。
6. **进阶：容器化**：把 runner 放进一个无网络、只读根文件系统、非 root 的 Docker 容器执行，比较启动开销，并验证 Q10 中的绕过手段是否还能造成实际破坏。

---

## 8. 常见坑

- **以为 denylist 是安全边界**：它只是兜底，至少有三种实测可行的绕过方式。
- **候选代码里的 `print`**：会让正确代码得 0 分（`non-json output`）。
- **把断言写成语句**：`"assert f() == 1"` 不能 `eval`，永远失败；要写 `"f() == 1"`。
- **真值断言过宽**：`"f()"` 只要返回非空对象就通过；`==` 断言可以被自定义 `__eq__` 骗过。
- **stderr 写太多**：表现为超时，而不是输出溢出。
- **代码块格式稍有偏差**：```` ```py  ```` 后有空格、```` ```c++ ````、未闭合，`extract_code` 都返回 `None`，0 分。
- **把 `import` 失败当成语法错误**：代码中是 `error`。
- **用标准库中依赖被禁模块的模块**：`tempfile`、`asyncio` 会被误伤。
- **混用"通过比例"和"全部通过"**：本节分数是比例，HumanEval 的 pass@k 以"全部测试通过"为一次成功；第 75 课用 `score >= 0.999999` 把比例转成 0/1。
- **在 Windows 上运行**：`select` 不支持管道。
- **超时设得太紧**：超时包含约 50 ms 的解释器启动时间。

---

## 9. 测试在验证什么

测试文件：`tests/test_exec.py`（`unittest` 风格）。通过 `sys.path.insert` 把 `code/` 加入路径，导入五个退出码常量和主要函数。

运行方式：

```bash
cd code
python3 -m pytest -q            # 或：python3 -m unittest discover tests
```

实际运行结果：`21 passed in 0.77s`（每个 `run_candidate` 测试都真实启动子进程；超时测试本身耗时约 0.5 秒）。

| 测试类 | 测试 | 验证的性质 |
|--------|------|-----------|
| `TestExtractCode` | `test_extracts_python_block` | 取出 `python` 代码块内容，不含反引号 |
| | `test_extracts_untagged_block` | 无语言标签的代码块也能取出 |
| | `test_no_block_no_backticks_returns_raw` | 无反引号时原样返回 |
| | `test_backticks_but_unclosed_returns_none` | 未闭合 → `None` |
| `TestRunCandidate` | `test_all_assertions_pass` | `pass`、score 1.0、passed = total = 2 |
| | `test_partial_assertions_fail` | 一真一假 → `assertion_fail`、score 0.5 |
| | `test_syntax_error` | 缺冒号 → `syntax_error`、0 分 |
| | `test_timeout` | 顶层 `time.sleep(5)`、预算 0.5 秒 → `timeout` |
| | `test_runtime_error_during_assertion` | 断言中抛异常 → `assertion_fail`（不是 `error`） |
| | `test_denied_import_subprocess` | `import subprocess` → `error`，detail 含 `denied` |
| | `test_no_assertions_yields_error` | 空断言 → `error`（不启动子进程） |
| `TestScoreCodeExec` | `test_score_from_fenced_block` / `test_score_zero_on_bad_block` | 端到端：抽取 + 执行 + 计分 |
| | `test_unclosed_block_scores_zero` | 未闭合代码块 → 0 分 |
| `TestPassAtK` | `test_pass_at_1_equals_c_over_n` | `pass_at_k(10, 3, 1) == 0.3` |
| | `test_pass_at_k_perfect` / `test_pass_at_k_none_pass` | c = n → 1；c = 0 → 0 |
| | `test_pass_at_k_known_value` | 与 `1 − comb(9,5)/comb(10,5)` 对比，精确到 8 位 |
| | `test_pass_at_k_when_k_greater_than_n_minus_c` | `n − c < k` → 1 |
| | `test_pass_at_k_estimator_over_tasks` | 两题平均：pass@1 = 0.5，pass@3 = 1.0 |
| | `test_invalid_inputs_raise` | 负数 n、c > n、k = 0 都抛 `ValueError` |

讲义说测试 "exercise the four exit codes"，实际覆盖了全部五种（`pass`、`assertion_fail`、`syntax_error`、`timeout`、`error`）。测试没有覆盖的地方：

- 输出溢出（`output overflow`）；
- 候选代码 `print` 导致的 `non-json output`；
- stderr 大量输出导致的假超时；
- denylist 的绕过与误伤；
- `k > n` 时 `pass_at_k` 的行为；
- 子进程被信号杀死（负返回码）。
