# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 35 节 面向 Agents 的初始化脚本 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py [--no-cache] [--write-lkg]` ｜ **依赖**：仅标准库（`argparse`、`hashlib`、`importlib.util`、`json`、`os`、`re`、`shutil`、`subprocess`、`sys`、`time`、`dataclasses`、`pathlib`）；`--write-lkg` 和 LKG 差异探测需要 `git` 且脚本位于 git 仓库内
>
> **副作用**：在 `code/workdir/` 下写 `init_report.json`、`prereqs.lock`；`--write-lkg` 时写 `last_known_good.json`。

---

## 1. 这份代码在考察什么

讲义说："Every session that starts cold pays a tax." 这份代码就是讲义里的 `init_agent.py`：在 agent 启动前运行一组**确定性探测（probe）**，写出 `init_report.json`，有阻断性失败就以非零退出，拒绝启动 agent。

它覆盖了讲义的三层内容：

1. **基础探测**：Python 版本、依赖可导入、测试命令可解析、必需环境变量、状态文件新鲜度。
2. **生产模式**：LKG（last-known-good）差异预算、带 TTL 的 `prereqs.lock` 缓存、每个探测的耗时预算（超过 3 秒降级为 warn）。
3. **Fail loud**：报告 `ok=false` 时打印到 stderr 并返回 1，`raise SystemExit(main())` 把它变成进程退出码。

> 一句话：**把 agent 每次会话都要重新摸索的环境信息，变成一个可缓存、可接入 CI/hook 的确定性脚本。** 但要注意它的缓存失效有明显漏洞，"block severity"也只是字面说法。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 路径常量 `WORK`、`STATE_PATH`、`REPORT_PATH`、`LOCK_PATH`、`LKG_PATH` | 模块常量 | 所有产物都在 `code/workdir/` | — |
| 配置常量 `REQUIRED_*`、`*_SECONDS`、`LKG_FILE_DIFF_BUDGET` | 模块常量 | 探测的阈值与要求 | 可配置的探测 |
| `SHA_PATTERN` | 编译好的正则 | 校验 LKG 中的提交哈希 | 输入校验 |
| `Probe` | dataclass | `name`、`status`、`detail`、`duration_ms` | 探测结果形状 |
| `_timed` | 装饰器 | 计时；超预算的 pass 改为 warn | 耗时预算（练习 5） |
| `probe_runtime` / `probe_dependencies` / `probe_test_command` / `probe_env` / `probe_state_freshness` | 函数 ×5 | 讲义列出的五个基础探测 | 探测表 |
| `probe_lkg_diff` | 函数 | 与 LKG 比较改动文件数 | LKG 锚定（练习 1） |
| `_deps_fingerprint` / `lock_is_fresh` / `write_lock` | 函数 | 锁文件缓存 | lock + TTL |
| `run_probes` | 函数 | 依次运行 6 个探测 | — |
| `main` | 函数 | 解析参数 → LKG 钉住 / 缓存短路 / 探测 → 报告 → 退出码 | 入口 |

数据流：`argparse` → （`--write-lkg`：`git rev-parse HEAD` → 写 LKG → 返回）→ （锁新鲜且无 `--no-cache`：直接返回 0）→ `run_probes()` → 写 `init_report.json` → 打印表格 → `ok` 为假返回 1；为真写锁、返回 0。

---

## 3. 逐段精讲

### 3.1 配置常量

```python
REQUIRED_PYTHON = (3, 10)
REQUIRED_DEPS = ["json", "dataclasses"]
REQUIRED_TEST_COMMAND = "python3"
REQUIRED_ENV_VARS: list[str] = []
STATE_FRESHNESS_SECONDS = 24 * 60 * 60
LOCK_TTL_SECONDS = 24 * 60 * 60
PROBE_BUDGET_SECONDS = 3.0
LKG_FILE_DIFF_BUDGET = 50
```

- 演示用的要求都"必然满足"：依赖是两个标准库模块、测试命令是 `python3` 本身、环境变量列表为空——所以默认运行一定走"happy path"。真实项目中应换成 `requirements.txt` 中的包、`pytest` 之类的真实测试命令、`OPENAI_API_KEY` 之类的必需变量。
- 讲义的数字在这里一一落地：24 小时新鲜度与锁 TTL、3 秒探测预算、50 个文件的漂移预算。
- 注意 `REQUIRED_TEST_COMMAND = "python3"` 只能证明"解释器在 PATH 上"，并不能证明测试命令能跑（讲义："The agent must know how to verify"）。

### 3.2 结果形状与计时装饰器

```python
@dataclass
class Probe:
    name: str
    status: str
    detail: str
    duration_ms: int = 0


def _timed(probe_fn):
    def _wrap(*a, **kw) -> Probe:
        started = time.time()
        result = probe_fn(*a, **kw)
        result.duration_ms = int((time.time() - started) * 1000)
        if result.duration_ms > PROBE_BUDGET_SECONDS * 1000 and result.status == "pass":
            result.status = "warn"
            result.detail = f"{result.detail} (slow: {result.duration_ms}ms > {int(PROBE_BUDGET_SECONDS * 1000)}ms)"
        return result
    return _wrap
```

- `Probe` 就是讲义 Key Terms 中的 "A deterministic function returning `(name, status, detail)`"，多了一个耗时字段。没有 `severity` 字段——讲义和 mission 反复说的"block-severity probe"在代码里并不存在，所有 `fail` 都是阻断，所有 `warn` 都不阻断。
- `_timed` 是一个**装饰器**：`@_timed` 写在函数定义上方，等价于 `probe_runtime = _timed(probe_runtime)`。`_wrap(*a, **kw)` 接收任意参数原样转发。
- 超预算时**只把 pass 降为 warn**，fail 保持 fail（实测：50 ms 的慢 pass 探测在预算 10 ms 时变为 `warn`，detail 追加 `(slow: 50ms > 10ms)`；慢 fail 不变）。这对应讲义练习 5："A probe that runs longer than three seconds is a workbench smell"——是"异味"，不是错误。
- 装饰器只能事后计时，**不能打断**一个卡住的探测；真正防卡死要靠子进程的 `timeout=`（见 3.4）。
- 小瑕疵：`time.time()` 是墙上时钟，可能被 NTP 调整；计时更适合用 `time.perf_counter()`。另外没有用 `functools.wraps`，被装饰后函数的 `__name__` 变成 `_wrap`。

### 3.3 五个基础探测

```python
@_timed
def probe_runtime() -> Probe:
    major, minor = sys.version_info[:2]
    if (major, minor) >= REQUIRED_PYTHON:
        return Probe("runtime", "pass", f"python {major}.{minor}")
    return Probe("runtime", "fail", f"need >= {REQUIRED_PYTHON}, have {major}.{minor}")

@_timed
def probe_dependencies() -> Probe:
    missing = [dep for dep in REQUIRED_DEPS if importlib.util.find_spec(dep) is None]
    ...

@_timed
def probe_test_command() -> Probe:
    if shutil.which(REQUIRED_TEST_COMMAND): ...

@_timed
def probe_env() -> Probe:
    missing = [k for k in REQUIRED_ENV_VARS if not os.environ.get(k)]
    ...

@_timed
def probe_state_freshness() -> Probe:
    if not STATE_PATH.exists():
        return Probe("state_freshness", "warn", "no state file yet; first run")
    age = time.time() - STATE_PATH.stat().st_mtime
    ...
```

| 探测 | 手段 | 失败时 | 说明 |
|------|------|-------|------|
| `runtime` | `sys.version_info[:2] >= (3, 10)` | fail | 元组按字典序比较，`(3, 9) < (3, 10)` 正确；若比较字符串 `"3.9" > "3.10"` 就会出错 |
| `dependencies` | `importlib.util.find_spec(dep)` | fail | **只查找、不导入**，快且无副作用；但对 `"pkg.sub"` 这种带点的名字，父包不存在时会抛 `ModuleNotFoundError`（实测），而不是返回 `None` |
| `test_command` | `shutil.which` | fail | 只检查可执行文件在 PATH 上 |
| `env` | `os.environ.get(k)` 为假 | fail | 空字符串也算缺失；只打印变量名，不打印值，避免泄露 secret |
| `state_freshness` | 状态文件的 mtime | **warn** | 不存在 → warn（首次运行）；超过 24h → warn；用 mtime 判断在 `git checkout` 后会失真 |

### 3.4 LKG 差异探测

```python
@_timed
def probe_lkg_diff() -> Probe:
    if not LKG_PATH.exists():
        return Probe("lkg_diff", "warn", "no last_known_good.json; pin one after first successful merge")
    try:
        lkg = json.loads(LKG_PATH.read_text())
        baseline = lkg.get("commit")
        if not baseline:
            return Probe("lkg_diff", "warn", "lkg file present but commit field empty")
    except json.JSONDecodeError as exc:
        return Probe("lkg_diff", "fail", f"lkg file unreadable: {exc}")
    if not isinstance(baseline, str) or not SHA_PATTERN.match(baseline):
        return Probe("lkg_diff", "warn", "lkg commit invalid; skipped")
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", baseline, "HEAD"],
            capture_output=True, text=True, timeout=2.0, cwd=HERE,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return Probe("lkg_diff", "warn", "git unavailable or slow; skipped")
    if out.returncode != 0:
        return Probe("lkg_diff", "warn", f"git diff failed: {out.stderr.strip()[:60]}")
    changed = [ln for ln in out.stdout.splitlines() if ln.strip()]
    if len(changed) > LKG_FILE_DIFF_BUDGET:
        return Probe("lkg_diff", "fail", f"{len(changed)} files changed since {baseline[:7]} (budget {LKG_FILE_DIFF_BUDGET})")
    return Probe("lkg_diff", "pass", f"{len(changed)} files changed since {baseline[:7]}")
```

- 分支很多，每个都给出结构化的结论：没有 LKG → warn；LKG JSON 损坏 → fail；commit 字段为空或格式不合法 → warn；git 不存在、超时、命令失败 → warn；超预算 → fail；否则 pass。
- **防命令注入**：`subprocess.run` 传的是**参数列表**而不是字符串（没有 `shell=True`），而且先用 `SHA_PATTERN`（7–40 位十六进制）校验 `baseline`。否则 LKG 文件中写入 `--output=/etc/xxx` 之类的内容就可能被 git 当作选项解析。
- `timeout=2.0` 才是真正的超时保护，与 3 秒预算一致。
- 实测（临时 git 仓库：先 5 个文件提交并 `--write-lkg`，再新增 51 个文件提交）：`lkg_diff fail 3ms 52 files changed since 85fbd61 (budget 50)`。第 52 个文件是被 `git add -A` 一起提交的 `code/workdir/last_known_good.json`——init 的产物应加入 `.gitignore`。
- ⚠️ `try` 只捕获 `JSONDecodeError`：LKG 文件内容为 `[]` 时 `lkg.get` 抛 `AttributeError`，脚本以 traceback 崩溃（实测）。
- ⚠️ `git diff A HEAD` 只比较提交，不含未提交的工作区修改和未跟踪文件。
- 许多异常情况都只是 `warn`（例如 git 不可用），意味着在没有 git 的环境中漂移预算形同虚设；是否应升级为 fail 取决于团队策略。

### 3.5 锁文件缓存

```python
def _deps_fingerprint() -> str:
    h = hashlib.sha256()
    h.update(str(sorted(REQUIRED_DEPS)).encode())
    h.update(REQUIRED_TEST_COMMAND.encode())
    h.update(str(sorted(REQUIRED_ENV_VARS)).encode())
    h.update(str(REQUIRED_PYTHON).encode())
    return h.hexdigest()[:16]


def lock_is_fresh() -> bool:
    if not LOCK_PATH.exists():
        return False
    try:
        lock = json.loads(LOCK_PATH.read_text())
    except json.JSONDecodeError:
        return False
    if not isinstance(lock, dict) or lock.get("fingerprint") != _deps_fingerprint():
        return False
    written_at = lock.get("written_at", 0)
    ...
    age = time.time() - written_at
    return age < LOCK_TTL_SECONDS
```

- 思路与讲义一致："idempotent probe + content hash = skip"：配置没变、且锁在 24 小时内 → 跳过探测。
- `lock_is_fresh` 很"防御"：文件不存在、JSON 损坏、不是字典、指纹不符、时间戳类型不对，全部返回 `False`（宁可重跑，也不误判缓存有效）——这里比 `probe_lkg_diff` 多做了 `isinstance(lock, dict)` 检查。
- `sorted(...)` 让列表顺序不影响指纹；`hexdigest()[:16]` 截取前 16 个十六进制字符（64 位），对缓存键足够。
- ⚠️ **指纹哈希的是配置常量**，不是讲义说的"dependency manifest hash"，也不包含实际环境（包是否还在、环境变量是否还在、解释器是否换了）。
- ⚠️ **失败运行不删除旧锁**（实测）：有 `DEMO_KEY` 时通过并写锁 → 删除 `DEMO_KEY` 后 `--no-cache` 运行退出 1 → 再不带参数运行，锁仍新鲜，**退出 0**。一次明确的失败被下一次普通运行掩盖了。
- ⚠️ 缓存命中时不写报告，`init_report.json` 停留在上一次的内容。

### 3.6 `main`：三条路径

```python
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-cache", action="store_true", ...)
    ap.add_argument("--write-lkg", action="store_true", ...)
    args = ap.parse_args(argv)
    ...
    probes = run_probes()
    report = {
        "timestamp": time.time(),
        "probes": [asdict(p) for p in probes],
        "ok": all(p.status != "fail" for p in probes),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    width = max(len(p.name) for p in probes)
    for p in probes:
        print(f"  {p.name:<{width}}  {p.status:>4}  {p.duration_ms:>4}ms  {p.detail}")
    if not report["ok"]:
        print("\ninit failed; refuse to launch agent", file=sys.stderr)
        return 1
    write_lock()
    print("\ninit ok (lock refreshed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- `main(argv=None)`：`parse_args(None)` 读取真实命令行；测试时可传入 `["--no-cache"]`。这让 `main` 既是 CLI 入口又能在代码里直接调用（测验中的实验就是这样做的）。
- 三条路径：
  1. `--write-lkg`：执行 `git rev-parse HEAD` 并写 LKG，**不跑任何探测**直接返回。只捕获 `FileNotFoundError` 和 `CalledProcessError`，超时会抛未捕获的 `TimeoutExpired`。实测在非 git 目录下返回 1 并打印 `lkg pin failed: ... exit status 128`。
  2. 锁新鲜且无 `--no-cache`：打印 `skipping probes`，返回 0。
  3. 正常探测：写报告 → 打印表格 → 按 `ok` 返回。
- `ok` 只看 `status != "fail"`；warn 不影响。
- 打印对齐：`{p.name:<{width}}` 是**嵌套格式规范**——宽度本身来自变量 `width`（这里是最长名字 `state_freshness` 的 15）。
- 失败信息写到 `sys.stderr`，正常信息写到 stdout，便于在 CI 中区分。
- `raise SystemExit(main())`：把 `main` 的返回值变成进程退出码，这是 fail loud 的最后一环。
- 报告和锁都用 `write_text` 非原子写入；第 34 节的 `atomic_write` 应在这里复用。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 每个探测一个函数，返回统一的 `Probe` | 易于增删、报告结构统一 | 新增探测要改代码；练习 4 讨论改成注册表（YAML/JSON）的取舍 |
| 装饰器统一计时 | 不在每个探测里重复计时代码 | 只计时不打断；卡住的探测要靠子进程 timeout |
| status 只有 pass/warn/fail，没有 severity | 简单 | 与讲义"block-severity"不符；应把"结果"与"是否阻断"拆成两个字段 |
| 锁文件 + TTL 短路 | 让重复运行几乎零成本，可以挂在每个 hook 上 | 指纹不含真实环境、失败不删锁、命中不写报告——缓存可能掩盖失败 |
| LKG 差异用 git 子进程 | 复用 git 的能力，参数列表 + SHA 校验防注入 | 依赖 git；不含工作区改动；异常大多只降为 warn |
| 失败写 stderr + 非零退出 | fail loud，wrapper 能感知 | wrapper 若写了 `\|\| true` 或管道丢失退出码，就前功尽弃 |
| 演示配置必然通过 | 运行即得 happy path | 看不到真实失败；用 `--no-cache` + 设置 `REQUIRED_ENV_VARS` 才能演示 mission 中的"缺环境变量翻转退出码" |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 装饰器 | `@_timed` 写在 `def probe_runtime()` 上方 | 等价于 `probe_runtime = _timed(probe_runtime)`，用函数包装函数 |
| 闭包 | `_timed` 内部定义并返回 `_wrap` | `_wrap` 记住了外层的 `probe_fn` |
| `*args, **kwargs` | `def _wrap(*a, **kw)`、`probe_fn(*a, **kw)` | 接收并转发任意位置参数与关键字参数 |
| 元组比较 | `(major, minor) >= REQUIRED_PYTHON` | 按元素依次比较，适合版本号 |
| 切片 | `sys.version_info[:2]`、`baseline[:7]`、`stderr.strip()[:60]` | 取前若干个元素/字符 |
| `importlib.util.find_spec` | `find_spec(dep) is None` | 查找模块而不导入 |
| `shutil.which` | `shutil.which("python3")` | 在 PATH 中查找可执行文件，找不到返回 `None` |
| `os.environ.get` | `os.environ.get(k)` | 读取环境变量，不存在返回 `None` |
| `Path.stat().st_mtime` | 状态文件修改时间 | 返回自 epoch 起的秒数 |
| `re.compile` | `SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")` | 预编译正则，重复使用更快 |
| `subprocess.run` 参数列表 | `["git", "diff", "--name-only", baseline, "HEAD"]` | 不经过 shell，参数不会被解释，防注入 |
| `capture_output=True, text=True, timeout=2.0, cwd=HERE` | 同上 | 捕获输出为字符串、2 秒超时、指定工作目录 |
| `subprocess.check_output` | `git rev-parse HEAD` | 返回输出；退出码非零时抛 `CalledProcessError` |
| 多异常捕获 | `except (FileNotFoundError, subprocess.TimeoutExpired):` | 元组里列出多个异常类型 |
| `hashlib.sha256` | `h.update(...)`、`h.hexdigest()` | 增量喂入字节，得到十六进制摘要 |
| `str.encode()` | `str(sorted(REQUIRED_DEPS)).encode()` | 字符串 → 字节，哈希只接受字节 |
| `isinstance` 多类型 | `isinstance(written_at, (int, float))` | 第二个参数可以是类型元组 |
| `argparse` | `add_argument("--no-cache", action="store_true")` | 布尔开关；`args.no_cache` 中横线变下划线 |
| `all()` + 生成器 | `all(p.status != "fail" for p in probes)` | 全部满足才为真 |
| `max()` + 生成器 | `max(len(p.name) for p in probes)` | 求最长名字，用于对齐 |
| 嵌套格式规范 | `f"{p.name:<{width}}"`、`{p.status:>4}`、`{p.duration_ms:>4}` | 宽度可以来自变量；`<` 左对齐、`>` 右对齐 |
| `print(..., file=sys.stderr)` | 失败信息 | 输出到标准错误 |
| `raise SystemExit(main())` | 文件末尾 | 把返回值作为进程退出码 |
| 联合类型默认参数 | `def main(argv: list[str] \| None = None)` | 既能命令行调用，也能在测试中传参 |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时目录副本中运行；该副本不是 git 仓库）。

**第 1 次（全新 workdir）**，退出码 0：

```text
  runtime          pass     0ms  python 3.13
  dependencies     pass     0ms  all of ['json', 'dataclasses'] importable
  test_command     pass     0ms  python3 resolvable on PATH
  env              pass     0ms  all of [] present
  state_freshness  warn     0ms  no state file yet; first run
  lkg_diff         warn     0ms  no last_known_good.json; pin one after first successful merge

init ok (lock refreshed)
```

**第 2 次（紧接着）**，退出码 0：

```text
prereqs.lock fresh (TTL 86400s); skipping probes
```

**第 3 次（`--no-cache`）**：输出与第 1 次相同，退出码 0，报告与锁被刷新。

**`--write-lkg`（非 git 目录）**，退出码 1：

```text
fatal: not a git repository (or any of the parent directories): .git
lkg pin failed: Command '['git', 'rev-parse', 'HEAD']' returned non-zero exit status 128.
```

逐项解读：

- 五个基础探测在演示配置下必然通过；`state_freshness`（没有状态文件）和 `lkg_diff`（没有 LKG）是 warn，不影响 `ok`。
- 所有耗时都是 0 ms：这些探测都是毫秒以下的本地操作，远低于 3 秒预算。
- `init_report.json` 包含 `timestamp`、6 个探测的完整字段和 `"ok": true`；`prereqs.lock` 只有 `fingerprint`（如 `0973aea701371251`）与 `written_at`。
- 第 2 次运行连报告都没有重写，所以 mission 所说的"twice in a row is a no-op except for the timestamp"在代码中表现为"第二次什么都不做"。

额外实验（import 后调用 `main`，或在临时 git 仓库中运行）：

| 场景 | 结果 |
|------|------|
| `REQUIRED_ENV_VARS=["DEMO_KEY"]`，变量存在，`--no-cache` | 退出 0，写锁 |
| 删除 `DEMO_KEY`，不带参数 | **退出 0**（锁短路，没发现缺失） |
| 删除 `DEMO_KEY`，`--no-cache` | 退出 1，`env fail missing env vars: ['DEMO_KEY']` |
| 紧接着不带参数 | **退出 0**（失败没有让旧锁失效） |
| git 仓库，LKG 后新增 51 个文件并提交 | `lkg_diff fail 52 files changed ... (budget 50)`，退出 1 |
| LKG 文件内容为 `[]` | `AttributeError` 崩溃 |
| LKG commit 为 `"zzz"` | `lkg_diff warn lkg commit invalid; skipped` |

---

## 7. 动手改一改

1. **修缓存漏洞**：失败时 `LOCK_PATH.unlink(missing_ok=True)`；指纹中加入依赖清单文件哈希、`sys.executable`、必需环境变量的存在性；env 与 state 探测每次都跑（参考测验 Q9）。
2. **加 severity**：`Probe` 增加 `severity` 字段，只有 `block` 级 fail 才非零退出；为 `state_freshness` 设计"异常结束 + 过期 → block"的规则（参考测验 Q10）。
3. **讲义练习 2**：锁超过 7 天时**拒绝启动**（不是重新探测，而是要求人工确认），与 24 小时的"跳过探测"TTL 区分开。
4. **加固 LKG**：检查 JSON 顶层类型；`--write-lkg` 前先跑一遍探测、全部通过才允许钉基线；把 `workdir/` 加入 `.gitignore`；可选地把未提交改动也计入预算。
5. **讲义练习 4：注册表**：把探测改为数据驱动（例如 `probes.json` 中列出 `{"name": "env", "kind": "env_vars", "args": [...], "severity": "block"}`），用字典把 `kind` 映射到函数。讨论取舍：配置更易审查，但失去了类型检查与 IDE 跳转。
6. **进阶：接入 hook 与 CI**：写一个 `pre_task.sh`（`set -euo pipefail`）调用本脚本；再写一个 GitHub Actions job，上传 `init_report.json` 作为 artifact，agent job 用 `needs:` 依赖它。

---

## 8. 常见坑

- **把 warn 当作没事**：`state_freshness` 和 `lkg_diff` 的很多异常都只是 warn，默认不会阻止启动。
- **缓存掩盖失败**：失败后旧锁仍有效，下一次普通运行直接通过。
- **指纹只哈希配置**：环境变了（卸载包、删变量、换解释器），缓存不会失效。
- **`find_spec` 的点号陷阱**：`find_spec("pkg.sub")` 在 `pkg` 不存在时抛 `ModuleNotFoundError`，需要 `try`。
- **只检查可执行文件存在**：`shutil.which("python3")` 不代表 `pytest` 装好了、测试能跑。
- **用 mtime 判断新鲜度**：`git checkout`、复制文件都会改 mtime。
- **init 产物进了 git**：`workdir/` 中的文件被提交后，会计入 LKG 差异预算。
- **包装脚本吞退出码**：`|| true`、没有 `pipefail` 的管道、Makefile 的 `-` 前缀都会让 fail loud 失效。
- **在报告里打印 secret 值**：只能报告变量名和是否存在。
