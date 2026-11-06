# 测验 · 带拒绝列表与路径隔离的 Sandbox 执行器（Sandbox Runner with Denylist and Path Jail）

> **阶段 19 · 综合项目 · 第 26 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两层防护的分工 | verification gate（第 25 课）决定调用"该不该跑"；sandbox 决定"跑的时候能做什么"。两者是模型与操作系统之间的两层 |
| 2 | 三类常见失败 | 危险可执行文件（`sudo`、`rm -rf`、`mkfs`、`dd`）、argv 把戏（`python3 -c`、`bash -c`、`node -e`）、路径逃逸（`../../etc/passwd`） |
| 3 | 四条拒绝轴 | 名称（denylist，按 basename）、argv（解释器 + `-c/-e` 类标志）、结构（`shell=False` 时的 shell 元字符）、路径（realpath 前缀检查）；全部在派生子进程**之前**完成 |
| 4 | Path jail | 对"像路径"的参数做 `os.path.realpath`，要求结果等于 root 或以 `root + os.sep` 开头；用 realpath 而不是字面路径，才能挡住符号链接逃逸 |
| 5 | 无斜杠的符号链接 | `link.txt -> /etc/passwd` 不含 `/`，`_looks_like_path` 会漏掉；代码额外用 `os.path.lexists(root/arg)` 把它抓回来做检查 |
| 6 | 子进程执行 | `subprocess.run(argv, shell=False, cwd, env=白名单环境变量, capture_output=True, timeout=...)`；cwd 也必须在 root 内 |
| 7 | 输出截断 | stdout/stderr 超过 `max_output_bytes` 时保留前 N 字节并追加 `[sandbox: output truncated]` 标记，`truncated=True` |
| 8 | 结构化结果 | `SandboxResult(argv, exit_code, stdout, stderr, truncated, timed_out, denied, reason, duration_ms)`；拒绝 −100、超时 −101；`ok` = 退出码 0 且未拒绝未超时 |
| 9 | 不是真正的沙箱 | 讲义："The sandbox is not a security boundary in the operating system sense"；没有 namespaces、cgroups、seccomp、gVisor、Firecracker，是开发期 guardrail |
| 10 | 生产中要叠加的层 | 非特权容器 / microVM、去掉 capabilities、项目目录只读挂载 + scratch 可写、ulimit 限制内存与 CPU、环境变量白名单 |

### 核心技能（能动手做到）

- [ ] 给定任意 argv，说出它会被哪条拒绝轴挡下（或放行），并给出 `reason` 字符串的大意
- [ ] 解释 `startswith(root + os.sep)` 与 `startswith(root)` 的区别，构造一个能区分二者的例子
- [ ] 找出本节解释器检查、路径检查、元字符检查的至少 6 种绕过或误杀，并说明根因
- [ ] 解释 `subprocess.run(timeout=...)` 超时时只杀直接子进程、输出在截断前已全部进内存这两个问题，并用 `Popen(start_new_session=True)` + `os.killpg` + 增量读取修复
- [ ] 说清 `shell=True` 配合列表 argv 时 `subprocess` 的真实语义，以及为什么本节在 `shell=True` 时几乎所有检查都失效
- [ ] 能为生产环境的 coding agent 设计一套 OS 级隔离方案

---

## 二、基础自测（选择题）

**Q1.** 本节 demo 最后一项是 `sandbox.run([echo, "x" * 4096])`（`max_output_bytes=512`）。demo 打印的徽章是什么？

- A. `TRUNCATED`
- B. `DENIED`，因为输出过大
- C. `EXIT 141`
- D. `OK`，因为 `ok` 只看退出码、拒绝和超时，不看 `truncated`

**Q2.** 执行 `sandbox.run(["python3", "-cimport this"])`（注意 `-c` 与代码之间没有空格）。结果是：

- A. 放行并执行，输出 "The Zen of Python"——`^-c$` 只匹配恰好等于 `-c` 的参数
- B. 被解释器检查拒绝，因为参数以 `-c` 开头
- C. 被 shell 元字符检查拒绝
- D. 被 path jail 拒绝，因为 `import this` 像路径

**Q3.** `shell=False` 时执行 `sandbox.run(["echo", "f(x)"])`，结果是：

- A. 放行，输出 `f(x)`
- B. 被 denylist 拒绝
- C. 被拒绝：`argv contains shell metachar ')' in 'f(x)'`——尽管 `shell=False` 时括号根本不会被 shell 解释
- D. 被 path jail 拒绝

**Q4.** path jail 中写的是 `resolved.startswith(root + os.sep)` 而不是 `resolved.startswith(root)`。这样做主要是为了：

- A. 兼容 Windows 的反斜杠
- B. 防止"前缀相同的兄弟目录"被误判为在 root 内，例如 root 为 `/tmp/proj`，参数解析为 `/tmp/proj2/x`
- C. 让 `..` 能被正确解析
- D. 提高字符串比较速度

**Q5.** project root 内有一个符号链接 `link.txt -> /some/outside/secret.txt`。执行 `sandbox.run(["cat", "link.txt"])`（cwd 为默认的 root）。结果是：

- A. 被拒绝：虽然 `link.txt` 不含 `/`，但 `os.path.lexists(root/link.txt)` 为真，于是做了 realpath 检查，发现解析到 root 之外
- B. 放行，因为 `_looks_like_path("link.txt")` 返回 `False`
- C. 被 denylist 拒绝，因为 `cat` 在 denylist 中
- D. 抛出 `FileNotFoundError`

**Q6.** 关于本节的退出码约定，下列说法正确的是：

- A. −100 与 −101 可能和"被信号 100/101 杀死"的子进程返回码混淆
- B. 输出被截断时退出码固定为 −102
- C. 只有策略拒绝才会得到 −100
- D. POSIX 下 `subprocess` 用负数 −N 表示"被信号 N 杀死"，常规信号编号都小于 65，所以 −100/−101 不会与之冲突；但"可执行文件不存在"也被报告为 `denied=True`、−100，与策略拒绝混在一起

**Q7.** demo 中 `sandbox.run([yes, "y"])`（超时 2 秒、`max_output_bytes=512`）。实测结果最准确的描述是：

- A. `timed_out=True`，`stdout` 为空，因为超时时输出被丢弃
- B. `timed_out=True`、`truncated=True`、`stdout` 为 541 字节（512 + 29 字节标记），但 Python 进程峰值内存约 3.4 GB——截断发生在**全部**读入内存之后
- C. `truncated=True`，进程在输出达到 512 字节时被立即终止，耗时远小于 2 秒
- D. `denied=True`，因为 `yes` 在 denylist 中

**Q8.** 调用 `sandbox.run(["cat /etc/hostname"], shell=True)`。结果是：

- A. 被 denylist 拒绝
- B. 被 path jail 拒绝，因为 `/etc/hostname` 在 root 之外
- C. 放行并执行，读到了 root 之外的文件：basename 检查对象是整条命令字符串，`shell=True` 跳过元字符检查，path jail 只检查 `argv[1:]`（为空）
- D. 被元字符检查拒绝，因为字符串里有空格

---

## 三、动手 / 代码题

**Q9.** 解释器检查：

```python
INTERPRETER_FLAG_PATTERNS = (re.compile(r"^-c$"), re.compile(r"^-e$"), re.compile(r"^--eval$"),
                             re.compile(r"^--exec$"), re.compile(r"^-cu$"), re.compile(r"^-ce$"))

def _check_argv_interpreter(argv, cfg):
    name = _basename(argv[0])
    if name not in cfg.interpreter_block:
        return None
    for arg in argv[1:]:
        for pat in INTERPRETER_FLAG_PATTERNS:
            if pat.match(arg):
                return "..."
    return None
```

1. 列出至少 6 种能执行任意代码却**通过**本检查（且不含 shell 元字符）的调用，并说明每种绕过的原因。
2. 讲义说"any interpreter run with a `-c`-like flag is just a shell call with extra steps"。你会如何重新设计这条规则，让它不依赖枚举标志？

**Q10.** Path jail：

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
            return "... resolves outside project root ..."
    return None
```

`Sandbox.run` 允许传入 `cwd`（只要它在 root 内）。

1. 解释为什么 `["cp", "hello.txt", "--target-directory=/tmp/outside"]` 能把文件写到 root 之外。
2. root 下有 `src/link -> /etc/hostname`。比较 `run(["cat", "src/link"])` 与 `run(["cat", "link"], cwd=root/src)` 的结果，并解释。
3. 反过来，`run(["cat", "../hello.txt"], cwd=root/src)` 读的明明是 root 内的文件，为什么被拒绝？
4. 写出修复思路（至少 3 点）。

**Q11.** 超时与输出上限。

1. root 内有脚本 `spawn.sh`：`sleep 43 &`、`echo started`、`wait`。执行 `run(["sh", "spawn.sh"])`，超时 0.5 秒。超时后 `sleep 43` 还在运行吗？为什么？讲义说 "the sandbox kills the process group"，代码做到了吗？
2. 为什么 `yes y` 会让 Python 进程峰值内存达到 GB 级？
3. 写一个 `bounded_run(argv, cwd, env, timeout, max_bytes)`：增量读取 stdout/stderr，超过上限立即终止；超时或结束时杀掉整个进程组。

**Q12.** shell 模式：

```python
def _check_shell_metachars(argv, shell):
    if shell:
        return None
    for arg in argv:
        for meta in SHELL_METACHARS:
            if meta in arg:
                return "argv contains shell metachar ...; set shell=True to opt in"
    return None
```

1. `shell=False` 时，`subprocess` 会把 `;`、`|`、`&` 交给 shell 解释吗？那这条检查实际上防住了什么、误杀了什么？
2. `subprocess.run(["echo hi; rm -rf .", "x"], shell=True)` 在 POSIX 上实际执行的是什么？本节 `_check_executable_denylist` 对它会怎么判断？
3. 拒绝信息写着 "set shell=True to opt in"，从安全角度看有什么问题？给出你的改法。

---

## 四、面试高频题

**Q13.**（基础必考）verification gate 与 sandbox 有什么区别？为什么两层都需要？

**Q14.**（原理深挖）为什么说 denylist（拒绝列表）式的 sandbox "不是真正的安全边界"？真正的隔离靠什么？

**Q15.**（工程实践）实现一个可靠的 path jail 要注意哪些坑？（提示：符号链接、相对路径基准、`--opt=value`、TOCTOU）

**Q16.**（场景设计）为一个能执行任意测试命令的 coding agent 设计生产级执行环境，要求说出隔离、资源、网络、凭据、审计各层的做法。

**Q17.**（追问型）agent 说"我需要 `pip install` 一个包才能跑测试"，而你的 sandbox 拒绝了网络。你怎么处理？

---

## 五、参考答案与解析

### Q1 — 答案：D

```python
    badge = ("OK" if result.ok else "DENIED" if result.denied
             else "TIMEOUT" if result.timed_out else f"EXIT {result.exit_code}")
```

`echo` 输出 4097 字节，截断为 512 + 29 字节标记 = 541 字节，`truncated=True`，但退出码为 0、未拒绝、未超时，`ok` 为 `True`，徽章是 `OK`（实际运行输出 `echo big (truncated) -> OK`）。徽章逻辑里没有 `TRUNCATED` 分支（A 错）；超大输出不会导致拒绝（B 错）；C 是 SIGPIPE 场景的退出码，与本例无关。教训：下游如果只看 `ok`，会忽略"模型只看到了部分输出"这一事实。

### Q2 — 答案：A

`INTERPRETER_FLAG_PATTERNS` 都是 `^...$` 精确匹配。`"-cimport this"` 不等于 `"-c"`，检查放行；参数里也没有 shell 元字符（空格不在列表中）；不像路径。Python 允许 `-c` 与代码连写，于是实测输出 "The Zen of Python, by Tim Peters"。B 是"本该如此"的期望；C、D 都不成立。同类绕过还有 `-Ic`、`python3.13 -c`、`-m` 等，见 Q9。

### Q3 — 答案：C

`SHELL_METACHARS` 包含 `")"`，`")" in "f(x)"` 为真，实测被拒：`argv contains shell metachar ')' in 'f(x)'; set shell=True to opt in`。但 `shell=False` 时 argv 直接交给 `execve`，括号、分号、`&` 都只是普通字符，不会被解释。这条检查在 `shell=False` 时误杀合法参数（如带 `&` 的 URL、带括号的正则、函数签名），而在真正危险的 `shell=True` 时反而完全跳过（Q8、Q12）。

### Q4 — 答案：B

字符串前缀不等于路径前缀：`"/tmp/proj2/x".startswith("/tmp/proj")` 为 `True`。加上 `os.sep` 后变成判断是否以 `"/tmp/proj/"` 开头，兄弟目录就被正确拒绝（已实测：`<root>2/x` 被拒）。`resolved != root` 则单独放行 root 本身（如 `ls .`）。A 不对：`os.sep` 在 Windows 上是 `\`，但这里的目的不是兼容；C 是 `realpath` 的职责；D 无关。

### Q5 — 答案：A

`_looks_like_path("link.txt")` 为 `False`（没有斜杠，也不是 `.`/`..`），但代码随后检查 `os.path.lexists(os.path.join(root, arg))`——`lexists` 对符号链接本身返回真（即使目标不存在）。于是对它做 `realpath`，解析到 root 之外，拒绝。这正是测试 `test_slashless_symlink_to_outside_is_denied` 覆盖的场景。B 是没有 `lexists` 补丁时的行为；`cat` 不在 denylist（C 错）；检查阶段不会打开文件（D 错）。注意这个补丁只对"相对 root"的路径有效，cwd 不是 root 时会失效（Q10）。

### Q6 — 答案：D

POSIX 下 `Popen.returncode` 为 −N 表示子进程被信号 N 终止；Linux 常规信号与实时信号编号最大为 64，−100/−101 不会撞上。讲义："three sentinel codes for denied (-100), timed_out (-101), and truncated (the exit code is the real one, with a flag set)"——截断不改退出码（B 错）。但代码把 `FileNotFoundError`（命令不存在）也报告成 `denied=True`、`exit_code=-100`、`reason="executable not found: ..."`，与策略拒绝混在一起（C 错）。下游评估（第 27 课）如果按 `denied` 统计"被策略拦下的次数"，会把"拼错命令名"算进去。另外 `PermissionError`（argv[0] 是不可执行文件）**没有被捕获**，实测会直接抛出异常。

### Q7 — 答案：B

实测：`exit=-101, timed_out=True, truncated=True, len(stdout)=541`，`ru_maxrss` 约 3423 MB（单独运行 demo 时约 3537 MB）。原因：`subprocess.run(capture_output=True, timeout=2)` 在 2 秒内持续把 `yes` 的输出读进内存；超时时 POSIX 实现把已读到的输出放进 `TimeoutExpired.stdout`，然后才由 `truncate_stream` 截成 512 字节。所以 `max_output_bytes` 限制的是"返回给模型的大小"，不是"sandbox 进程消耗的内存"。A 错：超时时已读输出被保留；C 是理想行为（Q11 的修复）；D 错：`yes` 不在 denylist。

### Q8 — 答案：C

实测放行并输出主机名。逐条分析：
- `_basename("cat /etc/hostname")` 等于 `os.path.basename(...)`，取最后一个 `/` 之后的部分 → `"hostname"`，不在 denylist；
- 解释器检查：`"hostname"` 不在解释器集合；
- 元字符检查：`shell=True` 直接返回 `None`；
- path jail：只遍历 `argv[1:]`，这里为空。

同理 `["echo would-run; rm --version | head -1"]` 在 `shell=True` 下也被执行了（实测输出了 `rm (GNU coreutils) 9.4`）。`shell=True` 让本节几乎所有检查失效。

### Q9 — 参考答案

1. 绕过（括号内为实测结果；为避免触发元字符检查，示例代码都不含 `( ) ; |` 等）：

| 调用 | 绕过原因 |
|------|---------|
| `python3 -cimport this` | 标志与代码连写，`^-c$` 不匹配（实测执行） |
| `python3 -Ic "import this"` | 组合短选项 `-Ic` 不在枚举中（实测执行） |
| `python3.13 -c "import this"` | basename 是 `python3.13`，不在解释器集合（实测执行） |
| `python3 -m this` / `python3 -m http.server` | `-m` 运行任意模块，未被列入（实测执行） |
| `bash -lc "echo X"`、`sh -ec "echo X"` | 组合选项；列表里只有 `-ce`，没有 `-ec`、`-lc`（实测执行） |
| `perl -E "say 'X'"` | 大写 `-E` 未列入（实测执行） |
| `node -p "1+1"` | `-p`（print-eval）未列入（实测输出 `2`） |
| `env rm --version` / `env python3 ...` | `argv[0]` 是 `env`，被包装的命令完全不检查（实测执行了 `rm`） |
| `python3 script.py` | 讲义推荐的"用脚本文件代替 -c"，但脚本内容可以是任何东西，且 agent 可以先写文件再执行 |

另外 `find . -delete`、`find -exec`、`xargs`、`git -c core.pager=...` 等非解释器命令同样能间接执行或删除。

2. 重新设计：
   - **白名单优先**：只允许明确列出的命令及其参数形态（如 `pytest [路径]`、`python3 <root 内脚本>`），其余一律拒绝；
   - **规范化可执行文件**：用 `shutil.which` 解析出真实路径，再按 `realpath` 后的文件身份判断（防 `python3.13`、复制改名、`busybox` 多调用二进制）；拒绝 `env`、`xargs`、`nice`、`timeout` 等包装器，或递归检查被包装的命令；
   - **解释器规则改为结构约束**：解释器后必须**紧跟**一个位于 root 内的脚本路径，且之前不允许任何选项；
   - **执行层兜底**：不论检查多严，都要有 OS 级隔离（Q14），因为字符串层面无法穷举所有执行代码的方式。

### Q10 — 参考答案

1. `--target-directory=/tmp/outside` 以 `-` 开头，在第一行就被 `continue` 跳过，根本没做路径检查。实测文件被复制到 root 之外的目录。同类：`tar -C/`、`--output=/etc/x`、`-o/tmp/x` 等"选项=路径"或"选项连写路径"的形式。
2. 实测：`["cat", "src/link"]`（cwd=root）被拒，因为含 `/`，realpath 解析到 `/etc/hostname`；而 `["cat", "link"]`（cwd=root/src）**放行并读出了主机名**：`link` 不含 `/`，`lexists(root/link)` 为假（链接在 `root/src` 下而不是 root 下），于是跳过检查；子进程却是在 `root/src` 中运行，打开的正是那个符号链接。根因：**检查时的相对路径基准（root）与执行时的基准（cwd）不一致**。
3. 实测拒绝理由：`'../hello.txt' resolves outside project root ('/tmp/hello.txt' not under ...)`——检查按 root 拼接得到 `root/../hello.txt`，而子进程按 `root/src/../hello.txt` 解析，实际在 root 内。同一个根因导致误杀。
4. 修复思路：
   - 相对路径以**实际 cwd** 为基准解析（`os.path.join(real_cwd, arg)`），并对 `lexists` 也用同一基准；
   - 解析 `--opt=value` 与 `-oVALUE` 形式，取出值部分同样做 jail 检查；对不认识的选项保守处理；
   - 检查 argv[0] 本身（可执行文件路径）是否允许，例如禁止执行 root 内由 agent 新写入的文件，或要求可执行文件位于只读系统目录；
   - 认识到这是 **TOCTOU**（检查时刻与使用时刻不同）：检查后、`cat` 打开前，符号链接可以被替换。真正可靠的做法是让操作系统在打开时强制约束（容器内只挂载项目目录、只读 bind mount，或 Linux `openat2` 的 `RESOLVE_BENEATH`）。

### Q11 — 参考答案

1. 还在运行。实测超时 0.5 秒后返回 `timed_out=True`，1 秒后 `ps` 仍能看到 `sleep 43`（状态 `S`）。`subprocess.run` 超时时只对**直接子进程**（`sh`）调用 `kill()`，后台的孙进程被重新挂到 init 下继续运行。代码没有创建新的进程组/会话，也没有调用 `os.killpg`，讲义 "kills the process group" 与代码不符。
2. `capture_output=True` 让 `communicate()` 把管道中所有输出读进内存，截断在拿到完整字节串之后才发生；`yes` 每秒能写出 GB 级数据，2 秒超时足以让内存涨到约 3.4 GB（实测）。`max_output_bytes` 只约束返回值。
3. 参考实现（已在本机验证：`yes y` 在 512 字节处立即被杀，峰值内存约 12 MB；`sh spawn.sh` 超时后 `sleep` 进程只剩已被杀死的 defunct 记录；`echo hi` 正常返回 0）：

```python
import os, signal, subprocess, time, selectors

def bounded_run(argv, cwd, env, timeout, max_bytes):
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)   # 新会话 = 新进程组
    bufs = {proc.stdout: bytearray(), proc.stderr: bytearray()}
    sel = selectors.DefaultSelector()
    for f in bufs:
        sel.register(f, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    truncated = timed_out = False
    while sel.get_map():
        left = deadline - time.monotonic()
        if left <= 0:
            timed_out = True
            break
        for key, _ in sel.select(timeout=left):
            chunk = os.read(key.fd, 65536)
            if not chunk:                                   # EOF
                sel.unregister(key.fileobj)
                continue
            buf = bufs[key.fileobj]
            room = max_bytes - len(buf)
            if len(chunk) > room:                           # 超过上限：保留能放下的部分，立即停止
                buf += chunk[:max(room, 0)]
                truncated = True
                os.killpg(proc.pid, signal.SIGKILL)
                sel.unregister(key.fileobj)
            else:
                buf += chunk
    if not timed_out and not truncated:
        try:
            proc.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out = True
    try:
        os.killpg(proc.pid, signal.SIGKILL)   # 超时/超限杀整组；正常结束时清理残留孙进程
    except ProcessLookupError:
        pass
    rc = proc.wait()
    return rc, bytes(bufs[proc.stdout]), bytes(bufs[proc.stderr]), truncated, timed_out
```

要点：`start_new_session=True` 让子进程成为新进程组的组长，`os.killpg(proc.pid, ...)` 一次杀掉整组；增量读取保证内存上界约为 `2 × max_bytes`。注意正常结束时要先 `wait` 再 `killpg`，否则可能在进程退出前把它杀掉（返回码变成 −9）。更彻底的做法是用 cgroup 统一回收和限制资源。

### Q12 — 参考答案

1. 不会。`shell=False` 时 argv 经 `execve` 原样传给程序，`;`、`|`、`&`、`$(` 都只是普通字符。这条检查在 `shell=False` 下**防不住任何真实攻击**，只能捕捉"模型以为自己在写 shell 命令"的意图信号（例如 `echo a ; rm -rf` 会把 `;` 当作参数传给 echo，并不会执行 rm）；同时误杀了合法参数：`f(x)`、带 `&` 的 URL、`a>b` 形式的正则、`$` 开头的字符串等。
2. POSIX 上，`shell=True` 且 args 为列表时，`subprocess` 执行 `["/bin/sh", "-c", "echo hi; rm -rf .", "x"]`：**只有第一个元素是命令字符串**，后续元素成为 shell 的 `$0`、`$1`……于是 `rm -rf .` 会被 shell 执行。`_check_executable_denylist` 取 `os.path.basename("echo hi; rm -rf .")`，因为字符串里没有 `/`，结果就是整条字符串 `"echo hi; rm -rf ."`，不在 denylist 中，放行（若命令末尾是 `/`，basename 为空串，反而会以 "has no basename" 被拒——纯属巧合）。
3. 拒绝信息等于在**教模型如何绕过**：模型下一轮就会加上 `shell=True`，而 `shell=True` 恰恰跳过元字符检查，且其他检查也基本失效（Q8）。改法：
   - harness 层面不向模型暴露 `shell` 参数，或者直接禁止 `shell=True`；
   - 确有需要时，用 `shlex.split` 解析命令串，拒绝含控制操作符（`;`、`&&`、`|`、重定向、命令替换）的输入，再对每个 token 做与 `shell=False` 相同的检查后以列表方式执行；
   - 拒绝信息只说明"不允许什么"，不提示"打开什么开关可以绕过"。

### Q13 — 参考回答要点

- **gate（第 25 课）**：调用前的**策略判断**——工具在不在契约里、参数是否合法、是否超预算；纯函数、便宜、可审计，输出 ALLOW/DENY + 理由。
- **sandbox（本节）**：调用时的**执行约束**——用什么可执行文件、能碰哪些路径、跑多久、输出多大、继承哪些环境变量。讲义："The verification gate decides whether a tool call should run. The sandbox decides what happens when it does."
- **为什么两层都要**：gate 看到的是"意图"（工具名、参数），无法预知程序运行时的行为；sandbox 能在执行层面兜底。任何一层都可能被绕过，纵深防御让单点失误不至于造成损害。
- 再往下还有第三层：OS 级隔离（容器、microVM、seccomp），本节代码不包含。
- 加分点：两层的拒绝都应结构化地进入可观测性（第 28 课 `gen_ai.tool.execution` span）和评估（第 27 课按任务对比退出码）。

### Q14 — 参考回答要点

- **拒绝列表天然不完备**：可执行任意代码的方式无穷——改名复制的二进制、版本号后缀的解释器、`env`/`xargs` 包装、组合短选项、`-m`、构建工具钩子（`make`、`npm run`、`pytest` 插件）、agent 自己写的脚本……Q9、Q10 实测了十余种。
- **字符串层面的检查有 TOCTOU 和解析差异**：sandbox 理解的 argv 语义与目标程序的真实解析不一致。
- **进程没有被隔离**：本节子进程与 agent 同用户、同文件系统、同网络、同内核，讲义："Anything the subprocess can do, the sandbox can do."
- **真正的隔离**：
  - Linux namespaces（mount/pid/net/user）+ cgroups（CPU、内存、进程数）——容器的基础；
  - seccomp-bpf 限制系统调用；去掉 capabilities；非 root 用户；
  - gVisor（用户态内核）、Firecracker 等 microVM 提供更强的内核隔离；
  - 文件系统：项目目录只读挂载、单独可写 scratch、临时文件系统；
  - 网络：默认禁网或经出口代理白名单。
- 本节代码的价值：讲义称之为 "development-time guardrail"——把常见失误变成响亮的、可观测的拒绝。

### Q15 — 参考回答要点

- **用 realpath 而不是字面路径**：符号链接、`..` 都要先解析；比较时用 `root + os.sep` 前缀，防兄弟目录。
- **相对路径的基准必须是实际 cwd**（Q10 的误杀与绕过都源于此）。
- **识别所有"路径位置"**：位置参数、`--opt=path`、`-opath`、配置文件里引用的路径、stdin 内容；做不到完全识别就说明"字符串检查只能是辅助"。
- **不存在的路径**：`realpath` 对不存在的目标也会返回规范化结果，写新文件的场景要检查父目录。
- **TOCTOU**：检查与打开之间的窗口里，攻击者（或 agent 自己的另一个命令）可以替换符号链接。可靠方案是让内核在打开时约束：`openat2(RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS)`、`O_NOFOLLOW`、chroot/容器挂载只暴露项目目录。
- **大小写与规范化**：macOS/Windows 文件系统大小写不敏感，Unicode 规范化形式不同也会导致前缀比较失效。
- **argv[0] 本身**：别忘了可执行文件路径也可能指向 root 内 agent 新写入的文件。

### Q16 — 参考回答要点

- **隔离**：每个任务一个一次性容器或 microVM（Firecracker/gVisor），非 root 用户，去掉 capabilities，seccomp 默认配置；任务结束即销毁。
- **文件系统**：仓库以只读方式挂载，另给一个可写工作副本或 overlay；`/tmp` 用 tmpfs；不挂载宿主的 home、SSH 密钥、云凭据。
- **资源**：cgroup 限制 CPU、内存、进程数（防 fork bomb）、磁盘配额；墙钟超时并按进程组/cgroup 回收；输出流式读取并设上限（Q11）。
- **网络**：默认禁网；需要依赖时通过只允许包仓库域名的出口代理，或使用预装依赖的镜像；拒绝访问云元数据地址与内网网段。
- **凭据**：环境变量白名单（本节 `env_allowlist` 的思路）；需要的令牌采用短期、最小权限、按任务签发，不放进可被 agent 读取的位置。
- **审计**：每次执行记录 argv、cwd、退出码、耗时、截断/超时/拒绝标记、输出摘要，进入 trace（第 28 课）；拒绝次数作为评估信号（第 27 课）。
- **策略层**：gate 链（第 25 课）在前，命令白名单 + 结构化 argv 检查；高风险操作（推送、发布、删除）需要人工确认。

### Q17 — 参考回答要点

- **不要直接放开网络**，也不要让模型自己决定绕过（避免"set shell=True to opt in"式的提示）。
- 选项：
  1. **预构建环境**：根据仓库的依赖声明（`requirements.txt`、lockfile）预先构建镜像，执行阶段无需联网；
  2. **受控出口**：只允许访问包仓库（或内部镜像源）的代理，校验哈希/锁文件，禁止其他域名；
  3. **分阶段**：把"安装依赖"作为独立的、需要审批的步骤，在单独的环境中执行，产物再挂载进无网络的执行沙箱；
  4. **人工确认**：新依赖需要人工批准（供应链风险，参见阶段 13 关于注册表供应链的内容）。
- 同时记录这次请求和决策，作为审计与改进依据。
- 常见误区：为了让测试通过临时关闭 sandbox，或给 agent 一个通用的网络权限。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 25 Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：本节是 gate 放行之后的执行层。
- [阶段 19 · 24 计划—执行控制流程](../../24-plan-execute-control-flow/docs/zh.md)：计划中的每一步最终通过 sandbox 执行。
- [阶段 14 · 33 将 Agent 指令作为可执行约束](../../../14-agent-engineering/33-instructions-as-executable-constraints/docs/zh.md)：把"不许做什么"写成可执行检查。
- [阶段 14 · 38 Verification Gates](../../../14-agent-engineering/38-verification-gates/docs/zh.md)：验证门的概念。
- [阶段 13 · 26 Skill 权限、Sandboxes 与信任](../../../13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/docs/zh.md)：工具权限与沙箱的信任模型。
- [阶段 15 · 10 自主 Agents 的权限模式](../../../15-autonomous-systems/10-claude-code-permission-modes/docs/zh.md)：真实 coding agent 如何划分权限。

### 本节被哪些后续内容用到
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../27-eval-harness-fixture-tasks/docs/zh.md)：按任务比较 sandbox 结果的退出码。
- [阶段 19 · 28 OTel GenAI Spans 与 Prometheus Metrics](../../28-observability-otel-traces/docs/zh.md)：为每次 `Sandbox.run` 发出 `gen_ai.tool.execution` span。
- [阶段 19 · 29 基于 Harness 的端到端 Coding Agent](../../29-end-to-end-coding-task-demo/docs/zh.md)：把 gate 与 sandbox 两层接进完整 agent。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../../15-autonomous-systems/14-kill-switches-canaries/docs/zh.md)：执行层之外的运行时保护。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../../17-infrastructure-and-production/25-security-secrets-audit/docs/zh.md)：凭据管理与审计日志。

### 延伸关键词
`path traversal` · `realpath / symlink escape` · `TOCTOU` · `openat2 RESOLVE_BENEATH` · `allowlist vs denylist` · `shell=True` · `shlex` · `process group / killpg` · `start_new_session` · `cgroups` · `namespaces` · `seccomp` · `gVisor` · `Firecracker` · `egress proxy` · `least privilege`
