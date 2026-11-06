# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 37 节 运行时反馈循环 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（无参数） ｜ **依赖**：仅标准库（`subprocess`、`re`、`json`、`uuid`、`shlex`、`time`、`dataclasses`、`pathlib`）；需要系统里有 `python3` 命令；运行时会在 `code/` 下**删除并重建** `feedback_record.jsonl*`

---

## 1. 这份代码在考察什么

这份代码实现了讲义中的 feedback runner：一个包在 `subprocess.run` 外面的薄层，让 agent 执行的每条命令都留下结构化、可回放的记录。对应讲义的这些概念：

1. **结构化捕获**：argv、stdout、stderr、退出码、耗时、开始时间、agent 的预期备注。
2. **确定性截断**：头 5 行 + 尾 30 行 + `...truncated N lines...` 标记。
3. **Refuse-on-null**：拿不到退出码（超时、程序不存在）时 `exit_code=None`，`loop_can_advance` 返回 `False`。
4. **写入时脱敏**（生产模式 1）：在追加 JSONL 之前用正则替换密钥。
5. **轮转**（生产模式 2）：当前文件到 1 MB 就轮转为 `.1`…`.5`。
6. **重试链**（生产模式 3）：`command_id` + `parent_command_id`，可以回溯"失败 → 重试"。

> 一句话：**让 agent 读到的是"命令真实发生了什么"，而不是它自己对结果的想象**。代码同时也留下了几个值得深挖的安全与健壮性缺口（argv 未脱敏、正则漏报、截断与脱敏的顺序、未捕获的 `PermissionError`）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `HEAD_LINES` / `TAIL_LINES` / `ROTATE_BYTES` / `MAX_ROTATIONS` | 常量 | 截断与轮转参数 | token 预算、轮转策略 |
| `REDACTION_PATTERNS` | 常量（正则列表） | 5 类密钥模式及替换文本 | 写入时脱敏 |
| `FeedbackRecord` | dataclass | 一条记录的全部字段 | feedback record |
| `redact` | 函数 | 依次应用所有模式，返回 (文本, 命中数) | 脱敏 |
| `deterministic_tail` | 函数 | 头 + 尾截断，返回 (文本, 截掉行数) | 确定性截断 |
| `_process_capture` | 函数 | 先截断再脱敏 | 捕获流水线 |
| `maybe_rotate` | 函数 | 文件超限时依次重命名 | 轮转 |
| `run_with_feedback` | 函数 | 核心：执行命令、处理三种结果、追加 JSONL | feedback runner |
| `loop_can_advance` | 函数 | `exit_code is not None` | refuse-on-null |
| `load_all` | 函数 | 读取当前 + 轮转文件，按 `command_id` 去重 | loader |
| `retry_chain` | 函数 | 沿 `parent_command_id` 回溯 | 重试链 |
| `main` | 函数 | 清空旧记录，跑 5 条 demo 命令，打印，重建重试链 | demo |

数据流：`main` 删除旧 JSONL → `run_with_feedback(argv)` → `subprocess.run` → `_process_capture`（截断 → 脱敏）→ `FeedbackRecord` → `maybe_rotate` → 追加一行 JSON → `load_all` / `retry_chain` 读回。

---

## 3. 逐段精讲

### 3.1 常量与脱敏模式

```python
HERE = Path(__file__).parent
RECORD = HERE / "feedback_record.jsonl"

HEAD_LINES = 5
TAIL_LINES = 30
ROTATE_BYTES = 1 * 1024 * 1024  # 1 MB
MAX_ROTATIONS = 5

REDACTION_PATTERNS = [
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?key|token)\s*[:=]\s*\S+"),
     r"\1=[REDACTED]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA[REDACTED]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]+"), "xox-[REDACTED]"),
    (re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"),
     "[REDACTED PRIVATE KEY]"),
]
```

- 头 5 行、尾 30 行：尾部给得多，因为错误堆栈和测试总结在最后。
- 每个模式是 `(编译好的正则, 替换文本)` 二元组；在模块加载时 `re.compile` 一次，避免每次调用重新编译。
- `(?i)` 是行内标志，表示忽略大小写；`\1` 在替换文本中引用第 1 个捕获组（键名），所以 `password: x` 会被改写成 `password=[REDACTED]`。
- `[\s\S]*?` 是"跨行的非贪婪任意字符"：`.` 默认不匹配换行，`[\s\S]` 则匹配一切，`*?` 让它在遇到第一个 `END` 时就停。
- 讲义列出的模式是 `^Bearer `、`password=`、`api[_-]?key=`、`AKIA[0-9A-Z]{16}`、`xox[baprs]-`；代码额外覆盖了 `secret`、`token`、`access_key` 与 PEM 私钥。
- ⚠️ **`\b` 与下划线**：`\b` 是单词边界，而 `_` 是单词字符。`OPENAI_API_KEY=sk-abc123` 中 `API` 前面是 `_`，没有 `\b`，整条规则不匹配（实测 0 次命中）。最常见的环境变量写法反而漏了。
- ⚠️ **误报**：`token: 4096`（LLM 日志里的 token 计数）会被替换；`bearer of bad news` 会被替换成 `Bearer [REDACTED] bad news`。
- ⚠️ `\S+` 是贪婪的，会连同后面的引号、分号一起吞掉（`password=hunter2');` 整段被替换）。

### 3.2 `FeedbackRecord`

```python
@dataclass
class FeedbackRecord:
    command_id: str
    parent_command_id: str | None
    command: list[str]
    stdout_tail: str
    stderr_tail: str
    exit_code: int | None
    duration_ms: int
    started_at: float
    agent_note: str
    error: str | None = None
    truncations: dict[str, int] = field(default_factory=dict)
    redactions: dict[str, int] = field(default_factory=dict)
```

| 字段 | 讲义要求 | 说明 |
|------|---------|------|
| `command` | 是 | argv 列表，可重放 |
| `stdout_tail` / `stderr_tail` | 是 | 截断 + 脱敏后的文本 |
| `exit_code` | 是 | `int` 或 `None`（没拿到） |
| `duration_ms` | 是 | 整数毫秒 |
| `started_at` | 是 | Unix 时间戳（秒，浮点） |
| `agent_note` | 是 | 执行前写下的预期 |
| `command_id` / `parent_command_id` | 生产模式 3 | 重试链 |
| `error` | 讲义 refuse-on-null 部分 | 超时、程序不存在时的原因 |
| `truncations` / `redactions` | 代码新增 | 每个流截掉多少行、脱敏命中多少次 |

- 字段顺序有讲究：没有默认值的字段必须排在有默认值的字段前面，否则 dataclass 定义时就会报错。
- 讲义练习 1 的 `cwd` 字段尚未加入。

### 3.3 确定性截断与捕获流水线

```python
def deterministic_tail(text: str, head: int = HEAD_LINES, tail: int = TAIL_LINES) -> tuple[str, int]:
    lines = text.splitlines()
    if len(lines) <= head + tail:
        return text, 0
    cut = len(lines) - head - tail
    return "\n".join(lines[:head] + [f"...truncated {cut} lines..."] + lines[-tail:]), cut


def _process_capture(text: str) -> tuple[str, int, int]:
    """Truncate first, then redact. Returns (text, cut_lines, redaction_hits)."""
    tailed, cut = deterministic_tail(text)
    redacted, hits = redact(tailed)
    return redacted, cut, hits
```

- 100 行输入 → `cut = 65`，输出 5 + 1 + 30 = 36 行（实测）。35 行及以下原样返回。
- "确定性"体现在：没有随机、没有时间依赖，同样输入永远得到同样输出（skill 把"依赖时钟或随机采样的截断"列为 hard reject）。
- 细节：未截断时返回原文（保留结尾换行），截断时用 `"\n".join` 重新拼接（丢掉结尾换行）——同一个函数的两条路径格式不完全一致，对 agent 无大碍，但做字节级比较时要注意。
- ⚠️ **只按行截断**：一行 5,000,000 字符的输出 `cut=0`，原样写入记录（实测）。minified JSON、进度条、base64 都可能是超长单行。需要再加字符/字节上限。
- ⚠️ **先截断再脱敏的安全漏洞**：多行秘密（PEM 私钥）的 `BEGIN` 行如果落在被截掉的中间部分，尾部剩下的密钥行就匹配不上私钥规则。实测：10 行日志 + 52 行私钥块，脱敏命中 0 次、泄漏 29 行密钥内容；改为先脱敏再截断后泄漏 0 行。先截断的好处是正则只需扫描约 35 行，性能更好，但安全上不可取。

### 3.4 轮转

```python
def maybe_rotate() -> None:
    if not RECORD.exists() or RECORD.stat().st_size < ROTATE_BYTES:
        return
    for idx in range(MAX_ROTATIONS, 0, -1):
        src = RECORD.with_suffix(RECORD.suffix + (f".{idx - 1}" if idx > 1 else ""))
        if src == RECORD:
            src = RECORD
        dst = RECORD.with_suffix(RECORD.suffix + f".{idx}")
        if src.exists():
            if idx == MAX_ROTATIONS and dst.exists():
                dst.unlink()
            try:
                src.rename(dst)
            except FileNotFoundError:
                pass
```

- 倒序 `idx = 5, 4, 3, 2, 1`：`.4 → .5`（先删旧 `.5`）、`.3 → .4`、…、`.1 → .2`、当前文件 → `.1`。必须从大到小，否则会覆盖还没挪走的文件。
- `RECORD.with_suffix(".jsonl.1")`：把最后一个后缀 `.jsonl` 替换为 `.jsonl.1`，得到 `feedback_record.jsonl.1`。
- `if src == RECORD: src = RECORD` 是一行无效代码（赋值给自己），可以删除。
- 在**追加之前**检查：只有当前文件已经 ≥ 1 MB 才轮转，所以文件会比阈值多出一条记录的大小（把阈值改成 600 字节实测，文件 660 字节）。
- 实测（阈值 600 字节、16 条记录）：留下当前 + `.1`…`.5` 共 6 个文件、每个 2 条，最早 4 条被丢弃。
- `try/except FileNotFoundError: pass` 是为了容忍"别的进程刚刚挪走了文件"，但没有锁，并发轮转仍然不安全（skill 要求对追加加文件锁）。

### 3.5 `run_with_feedback`：三条路径

```python
    started = time.time()
    command_id = uuid.uuid4().hex[:12]
    base_kwargs = dict(command_id=command_id, parent_command_id=parent_command_id,
                       command=command, started_at=started, agent_note=agent_note)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s)
        out, cut_out, red_out = _process_capture(completed.stdout)
        err, cut_err, red_err = _process_capture(completed.stderr)
        record = FeedbackRecord(stdout_tail=out, stderr_tail=err,
            exit_code=completed.returncode,
            duration_ms=int((time.time() - started) * 1000),
            truncations={"stdout": cut_out, "stderr": cut_err},
            redactions={"stdout": red_out, "stderr": red_err},
            **base_kwargs)
```

- `subprocess.run(command, ...)` 传的是**列表**，没有 `shell=True`：参数不会被 shell 解析，`$HOME`、`;`、`|` 都只是普通字符，杜绝 shell 注入（skill 的 hard reject）。
- `capture_output=True` 等价于 `stdout=PIPE, stderr=PIPE`；`text=True` 让输出解码为 `str`。
- `timeout=timeout_s`（默认 30 秒）：超时后子进程被 kill，抛 `TimeoutExpired`。
- `uuid.uuid4().hex[:12]`：随机 UUID 的前 12 个十六进制字符（48 位），demo 规模下冲突概率可以忽略。
- `base_kwargs` + `**base_kwargs`：把三条分支共用的字段先放进一个字典，再展开为关键字参数，避免重复。
- 耗时用 `time.time()` 相减：系统时间被 NTP 调整时可能出现负数或跳变，测耗时应该用 `time.monotonic()`。

```python
    except subprocess.TimeoutExpired as exc:
        partial_out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        ...
        record = FeedbackRecord(..., exit_code=None, error=f"timeout after {timeout_s}s", ...)
    except FileNotFoundError as exc:
        record = FeedbackRecord(stdout_tail="", stderr_tail="", exit_code=None,
                                duration_ms=..., error=str(exc), **base_kwargs)
```

- 超时：`TimeoutExpired` 上的 `stdout` 可能是 `bytes`（即使 `text=True`），也可能是 `None`，代码两种都处理了。实测：`print('started'); sleep(5)`、超时 1 秒 → `exit_code=None`，`error='timeout after 1s'`，部分输出 `'started\n'` 被保留，`duration_ms≈1003`。
- 程序不存在：argv 方式下由 Python 直接 `exec`，失败时抛 `FileNotFoundError`（不会像 shell 那样得到退出码 127）。
- ⚠️ 只捕获了这两种异常。没有执行权限的脚本抛 `PermissionError`、`cwd` 不存在抛 `FileNotFoundError`/`NotADirectoryError` 等，前者会**直接冒出 runner、不写任何记录**（实测）。讲义要求"在拿到退出码前出错也要落一条 `exit_code: null` 的记录"，应改为 `except OSError`。

```python
    maybe_rotate()
    with RECORD.open("a") as fh:
        fh.write(json.dumps(asdict(record)) + "\n")
    return record
```

- JSONL：每行一个完整 JSON 对象，追加写入、按行读取，不需要整体解析。
- ⚠️ **argv 未脱敏**：`asdict(record)` 直接序列化 `command`、`agent_note`、`error`，只有 stdout/stderr 经过了 `redact`。demo 中 `leak` 命令的 argv 本身就含有 `Bearer ya29.AbCdEf`、`password=hunter2`、`AKIAIOSFODNN7EXAMPLE`，它们原样写进了 JSONL（实测）。这与"redact at write"的初衷相悖。

### 3.6 `loop_can_advance`

```python
def loop_can_advance(record: FeedbackRecord) -> bool:
    return record.exit_code is not None
```

- 它判断"有没有反馈"，而不是"成功没有"：`exit_code=2` 返回 `True`（agent 应该读 stderr 并做出反应），超时或程序不存在返回 `False`。
- 判断成功需要另外检查 `exit_code == 0`，这是第 38 节 verification gate 的职责。

### 3.7 `load_all` 与 `retry_chain`

```python
    def _rotation_key(p: Path) -> int:
        suffix = p.name[len(RECORD.name):]
        if not suffix:
            return 0  # active file
        try:
            return int(suffix.lstrip("."))
        except ValueError:
            return 99
    paths = sorted(HERE.glob(RECORD.name + "*"), key=_rotation_key, reverse=True)
    by_id: dict[str, FeedbackRecord] = {}
    for path in paths:
        ...
        for line in text.splitlines():
            ...
            try:
                record = FeedbackRecord(**json.loads(line))
            except (json.JSONDecodeError, TypeError):
                continue
            by_id[record.command_id] = record  # active file wins (last loaded)
    return list(by_id.values())
```

- 排序键：当前文件 0，`.1` → 1，…；`reverse=True` 让最老的 `.5` 先读、当前文件最后读。同一个 `command_id` 出现多次时后读的覆盖前面的，所以"当前文件优先"。
- 无法解析的后缀（如 `.lock`）给 99，会被最先读；读不了就跳过。
- `FeedbackRecord(**json.loads(line))`：把 dict 展开成关键字参数重建 dataclass；字段不匹配时抛 `TypeError`，坏行（半截 JSON）抛 `JSONDecodeError`，都静默跳过。
- ⚠️ 讲义说"agent 的循环只读当前文件"、skill 要求 loader "Cap at the last N or paginate"，但 `load_all` 读取所有轮转文件并返回全部记录，没有上限（上限只由轮转间接保证，约 6 MB）。

```python
def retry_chain(command_id: str) -> list[FeedbackRecord]:
    records = {r.command_id: r for r in load_all()}
    chain: list[FeedbackRecord] = []
    cursor: str | None = command_id
    while cursor and cursor in records:
        chain.append(records[cursor])
        cursor = records[cursor].parent_command_id
    return list(reversed(chain))
```

- 从最新一次往回走到没有父节点（或父节点已不在记录中）为止，再反转成"最老 → 最新"。
- 父记录被轮转丢弃后，链条会**静默截断**，看起来像"第一次就成功"——正是讲义担心的"重试看起来像独立的成功"。
- 没有环检测：如果手工构造了互相指向的记录会死循环（正常使用中 `command_id` 是新生成的，不会出现）。

### 3.8 `main()`：5 条 demo 命令

```python
    for path in HERE.glob("feedback_record.jsonl*"):
        path.unlink()
    ok = run_with_feedback(["python3", "-c", "print('hello')"], agent_note="expect hello")
    leak = run_with_feedback(["python3", "-c", "print('Authorization: Bearer ya29.AbCdEf'); ..."], ...)
    fail = run_with_feedback(["python3", "-c", "import sys; sys.exit(2)"], ...)
    retry = run_with_feedback([...], parent_command_id=fail.command_id)
    missing = run_with_feedback([shlex.split("does-not-exist")[0]], agent_note="probe missing binary")
```

- 开头**删除所有旧记录**：这与讲义"Tail the file across re-runs to see the loop accumulate"、mission"accumulates one record per command across re-runs"相矛盾——每次运行都从零开始，记录不会跨运行累积。
- 讲义/mission 说 demo 跑"success、failure、slow"三条命令；实际是 ok、leak、fail、retry、missing 五条，**没有 slow/超时的例子**（超时分支只能自己构造测试）。mission 还把脱敏和轮转列为 out of scope，但代码已经实现了。
- `shlex.split("does-not-exist")[0]` 等价于字符串 `"does-not-exist"`，只是示范 `shlex` 可以把命令字符串安全地切成 argv。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| argv 列表、无 `shell=True` | 无 shell 注入、命令可精确重放 | 不能用管道、通配符；需要时显式调用 `bash -c` 并单独审计 |
| 头 5 + 尾 30 行截断 | 确定性、错误在尾部 | 对超长单行无效；应再加字节上限 |
| 先截断再脱敏 | 正则只扫约 35 行 | 多行秘密被切开后漏网；应先脱敏 |
| 只脱敏 stdout/stderr | 实现简单 | argv、`agent_note`、`error` 中的秘密原样落盘 |
| 正则脱敏 | 无依赖、可审计 | 有漏报（`_API_KEY=`）和误报（`token: 4096`）；需正反例回归测试与已知值替换 |
| 追加前轮转、保留 5 份 | 当前文件大小有界 | 无锁，并发不安全；父记录被丢弃后重试链断裂 |
| `exit_code=None` 表示无反馈 | 明确区分"失败"和"不知道" | 只覆盖超时与程序不存在；应捕获所有 `OSError` |
| `time.time()` 计时 | 简单 | 应用 `time.monotonic()` |
| 12 位 UUID 作为 `command_id` | 简短可读 | 规模极大时需要完整 UUID |
| `main` 先清空旧记录 | demo 输出稳定 | 与讲义"跨运行累积"描述不符 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `subprocess.run` | `subprocess.run(command, capture_output=True, text=True, timeout=timeout_s)` | 启动子进程并等待结束，返回 `CompletedProcess`（含 `returncode`、`stdout`、`stderr`） |
| 捕获特定异常 | `except subprocess.TimeoutExpired as exc:`、`except FileNotFoundError as exc:` | 多个 `except` 按顺序匹配；`as exc` 拿到异常对象 |
| 多异常元组 | `except (json.JSONDecodeError, TypeError):` | 一个分支处理多种异常 |
| 条件表达式 | `exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")` | `A if 条件 else B` |
| `bytes.decode(errors="replace")` | 同上 | 非法字节替换为 `�` 而不是抛错 |
| 正则 `re.compile` / `subn` | `pattern.subn(replacement, out)` | `subn` 返回 (新字符串, 替换次数) |
| 行内标志与反向引用 | `(?i)`、`r"\1=[REDACTED]"` | 忽略大小写；替换文本中引用捕获组 |
| 原始字符串 | `r"\bAKIA[0-9A-Z]{16}\b"` | 反斜杠不转义，写正则必备 |
| 元组返回与解包 | `out, cut_out, red_out = _process_capture(...)` | 函数一次返回多个值 |
| `**kwargs` 展开 | `FeedbackRecord(..., **base_kwargs)`、`FeedbackRecord(**json.loads(line))` | 把字典展开为关键字参数 |
| `dict(...)` 关键字构造 | `base_kwargs = dict(command_id=..., ...)` | 用关键字参数构造字典 |
| 列表切片与拼接 | `lines[:head] + [marker] + lines[-tail:]` | 取前 N、后 N 个元素 |
| `str.splitlines` / `"\n".join` | `text.splitlines()` | 按行拆分 / 用换行拼接 |
| 倒序 `range` | `range(MAX_ROTATIONS, 0, -1)` | 5, 4, 3, 2, 1 |
| `pathlib` 文件操作 | `RECORD.stat().st_size`、`src.rename(dst)`、`dst.unlink()`、`HERE.glob(...)`、`RECORD.with_suffix(...)` | 查大小、重命名、删除、通配查找、替换后缀 |
| `with ... open("a")` | `with RECORD.open("a") as fh:` | 追加模式打开，离开代码块自动关闭 |
| 嵌套函数 | `load_all` 内的 `_rotation_key` | 只在本函数内使用的辅助函数 |
| `sorted(key=..., reverse=True)` | `sorted(paths, key=_rotation_key, reverse=True)` | 自定义排序键、降序 |
| 字典推导式 | `{r.command_id: r for r in load_all()}` | 构建 id → 记录的索引 |
| `while` 循环 + 游标 | `while cursor and cursor in records:` | 沿指针链表遍历 |
| `reversed` | `list(reversed(chain))` | 反转顺序 |
| `uuid` | `uuid.uuid4().hex[:12]` | 随机唯一 id |
| f-string 的 `!r` | `f"{rec.stdout_tail!r}"` | 用 `repr()` 显示，换行会显示成 `\n` |
| `x or default` | `rec.parent_command_id or '-'`、`rec.redactions or '-'` | 空值（`None`、空字典）时显示占位符 |
| dataclass 默认值顺序 | `error: str \| None = None` 放在最后 | 有默认值的字段必须在无默认值字段之后 |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时目录副本中执行，退出码 0；`cid` 为随机值，每次不同）：

```text
ok: cid=c6fc6b207a2f parent=- exit=0 duration_ms=18 redactions={'stdout': 0, 'stderr': 0}
leak: cid=c5ae2dd18cc1 parent=- exit=0 duration_ms=14 redactions={'stdout': 3, 'stderr': 0}
  stdout after redaction: 'Authorization: Bearer [REDACTED]\npassword=[REDACTED]\nAKIA[REDACTED]\n'
fail: cid=840ce3baaa5c parent=- exit=2 duration_ms=12 redactions={'stdout': 0, 'stderr': 0}
retry: cid=791070e774e2 parent=840ce3baaa5c exit=0 duration_ms=10 redactions={'stdout': 0, 'stderr': 0}
missing: cid=bcd74d24c2cc parent=- exit=None duration_ms=0 redactions=-
  error: [Errno 2] No such file or directory: 'does-not-exist'

retry chain for 791070e774e2: ['840ce3baaa5c', '791070e774e2'] (oldest -> newest)
5 records persisted in feedback_record.jsonl
```

逐项解读：

- **ok**：退出码 0，耗时十几毫秒（主要是启动 Python 解释器）。
- **leak**：stdout 中 3 处秘密分别被 Bearer、`password` 键值、`AKIA` 三条规则命中，`redactions={'stdout': 3}`。但是查看 JSONL 第二行，`"command"` 字段里**原样保存着** `Bearer ya29.AbCdEf`、`password=hunter2`、`AKIAIOSFODNN7EXAMPLE`——秘密仍在磁盘上（见 3.5）。
- **fail**：`exit=2`，`loop_can_advance` 会返回 `True`（有反馈），但它显然不是成功。
- **retry**：`parent=840ce3baaa5c`，即 fail 那条；最后的重试链 `['840ce3baaa5c', '791070e774e2']` 按"最老 → 最新"排列，审计者能看到"先失败后恢复"。
- **missing**：`exit=None`，`error` 来自 `FileNotFoundError`；`redactions` 是空字典，打印成 `-`；`loop_can_advance` 返回 `False`。
- **5 records**：`load_all` 读回 5 条；因为 `main` 一开始删除了旧文件，重复运行也总是 5 条，不会累积。

补充实验（均在临时目录实际运行）：

| 实验 | 结果 |
|------|------|
| `sleep(5)`、`timeout_s=1` | `exit_code=None`，`error='timeout after 1s'`，保留部分输出 `'started\n'`，`duration_ms=1003` |
| 执行无执行权限的脚本 | 抛 `PermissionError`，**不写记录** |
| 100 行输出 | `...truncated 65 lines...`，共 36 行 |
| 一行 5,000,000 字符 | 不截断（`cut=0`） |
| 10 行日志 + 52 行私钥 | 先截断再脱敏：命中 0 次，泄漏 29 行密钥 |
| `export OPENAI_API_KEY=sk-abc123` | 未脱敏 |
| 阈值 600 字节、16 条记录 | 6 个文件 × 2 条，`load_all` 返回 12 条 |

---

## 7. 动手改一改

1. **讲义练习 1**：给 `FeedbackRecord` 加 `cwd` 字段，`run_with_feedback` 增加 `cwd` 参数并传给 `subprocess.run`；同时把异常分支改为 `except OSError`，确保任何启动失败都落一条记录（参考测验 Q12）。
2. **讲义练习 2（强化版）**：把脱敏改为"先脱敏再截断"，并对 `command` 每个元素、`agent_note`、`error` 也做脱敏；为每种模式写正例和反例 fixture（包括 `OPENAI_API_KEY=`、`token: 4096`），用 `pytest` 断言。
3. **字节上限**：在行截断之后加一个按字符的头 + 尾截断（如 64,000 字符），让超长单行也有上界。
4. **讲义练习 3/4**：给追加与轮转加 `fcntl.flock` 文件锁；`retry_chain` 在父记录缺失时返回一个"链条不完整"的标记，而不是静默截断。
5. **loader 上限**：实现 `load_recent(n=20, task_id=None)`，只读当前文件末尾 N 条，供 agent 热循环使用；`load_all` 留给 CI 与 reviewer。
6. **讲义练习 5**：写一个终端小工具，读 JSONL，高亮最近一次非零退出码，显示命令、退出码、耗时、stderr 尾部、`agent_note` 与实际结果的对比、重试链、截断与脱敏计数。

---

## 8. 常见坑

- **把 `loop_can_advance` 当作"成功"**：它只说明拿到了退出码；成功要看 `exit_code == 0`。
- **只脱敏输出、不脱敏命令**：argv 里的秘密照样落盘，而且在 `ps` 中对同机用户可见。秘密应通过环境变量或文件传入。
- **依赖 `\b` 的脱敏正则**：`_` 是单词字符，`XXX_API_KEY=` 这类写法会漏网。
- **先截断后脱敏**：多行秘密被切开后匹配失败。
- **以为 `text=True` 时超时异常里的输出一定是 `str`**：`TimeoutExpired.stdout` 可能是 `bytes` 或 `None`，要像代码一样分别处理。
- **用 `time.time()` 测耗时**：系统时间调整会导致错误的耗时；用 `time.monotonic()`。
- **期待退出码 127**：那是 shell 的约定；argv 方式下程序不存在会抛 `FileNotFoundError`。
- **在课程目录直接运行**：`main` 会删除并重建 `code/feedback_record.jsonl*`；只想看效果时可以复制到临时目录运行。
