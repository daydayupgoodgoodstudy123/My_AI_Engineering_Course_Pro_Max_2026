# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 42 节 综合项目：交付可复用的 Agent 工作台包 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在本节目录下执行；产物写入 `../outputs/agent-workbench-pack/`） ｜ **依赖**：仅标准库（组装器用 `json`、`pathlib`；打包进去的脚本用 `argparse`、`subprocess`、`importlib.util`、`shutil` 等）；安装器需要 bash

---

## 1. 这份代码在考察什么

`main.py` 是一个**组装器（assembler）**：它把第 33–40 节逐个造出的 surface 以字符串常量的形式内嵌在一个文件里，运行时写出一个可整体复制的目录 `outputs/agent-workbench-pack/`。考察点有三层：

1. **打包边界**：什么进 pack（schema、四个脚本、四份文档、安装器、`VERSION`），什么不进（具体任务、厂商 SDK、入职文字）。
2. **安装与版本**：`bin/install.sh` 如何"拒绝无 `--force` 的覆盖"并在目标仓库写 `.workbench-version`；组装器本身如何做到幂等。
3. **打包进去的运行时**：init 探针、feedback runner、verification gate、handoff 生成器四个脚本各自的输入输出约定——也就是 surface 之间的**契约**。

本讲解除了讲 `main.py` 本身，也会逐个讲它内嵌的五段脚本（安装器 + 四个 Python 脚本），因为那才是 pack 的真正内容；并且用"在空目录中实际安装、实际跑一遍"的结果指出几处契约断裂。

> 一句话：**把一整个 workbench 压成一个可 `cp -r` 的、带版本号的目录**——同时它也是检验"surface 之间契约是否对得上"的最好场合。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 / 来源 |
|---------|------|------|---------------|
| `HERE` / `PACK` / `PACK_VERSION` | 模块常量 | 组装目标目录 `<本节>/outputs/agent-workbench-pack/`；版本 `1.0.0` | 版本即契约 |
| `AGENTS_MD` | 模板字符串 | 短路由：先读 state、board，再读四份文档；含 `{version}` 占位 | Instructions（第 33 节） |
| `AGENT_RULES_MD` 等四份文档 | 字符串常量 | 规则、可靠性策略、handoff 协议、评审标准 | 第 33、26、40、39 节 |
| `STATE_SCHEMA` / `BOARD_SCHEMA` / `SCOPE_SCHEMA` | dict | 三个 JSON Schema | State（34）、Scope（36） |
| `INSTALL_SH` | 字符串（bash） | 安装器 | 本节新增 |
| `INIT_AGENT_PY` | 字符串（Python） | 环境探针，写 `init_report.json` | 第 35 节 |
| `RUN_WITH_FEEDBACK_PY` | 字符串（Python） | 结构化执行命令，追加 `feedback_record.jsonl` | 第 37 节 |
| `VERIFY_AGENT_PY` | 字符串（Python） | 确定性 gate，写 `outputs/verification/<task>.json` | 第 38 节 |
| `GENERATE_HANDOFF_PY` | 字符串（Python） | 生成 `handoff.json` + `handoff.md` | 第 40 节 |
| `SCRIPT_FILES` | dict | 脚本文件名 → 内容 | 批量写出 |
| `PACK_README` | 字符串 | pack 说明与 Quickstart | 文档 |
| `write()` | 函数 | 建父目录 + 写文件 | 幂等写入 |
| `main()` | 函数 | 依次写出全部文件、设置可执行位、打印文件树 | 入口 |

数据流（组装期）：`main()` → `write(PACK / ..., 常量)` × 15 个文件 → `chmod 0o755`（脚本与安装器）→ `PACK.rglob("*")` 打印文件树。

数据流（使用期，在目标仓库）：`install.sh` 复制 pack → `init_agent.py` 写 `init_report.json` → `run_with_feedback.py -- <cmd>` 追加 `feedback_record.jsonl` → `verify_agent.py <task>` 读 contract/feedback/scope 报告/规则报告，写 `outputs/verification/<task>.json` → `generate_handoff.py <task>` 读以上全部，写 `outputs/handoff/<session>/`。

---

## 3. 逐段精讲

### 3.1 路径与版本常量

```python
HERE = Path(__file__).parent
PACK = HERE.parent / "outputs" / "agent-workbench-pack"

PACK_VERSION = "1.0.0"
```

- `HERE` 是 `code/`，`HERE.parent` 是本节目录，所以 pack 写到与 `code/` 并列的 `outputs/` 下——**直接在仓库中运行会覆盖已提交的产物**。实测生成内容与仓库中已提交的 `outputs/agent-workbench-pack/` 逐字节一致，所以 git 看不到变化。
- 版本号只在这里定义一次，再通过 `AGENTS_MD.format(version=PACK_VERSION)` 和写 `VERSION` 文件两处使用，避免手写两份导致漂移。

### 3.2 `AGENTS.md`：短路由

```python
AGENTS_MD = """# AGENTS.md
...
1. `agent_state.json` — where the last session stopped.
2. `task_board.json` — what is in flight, what is next.
3. `docs/agent-rules.md` — startup, forbidden, done, uncertainty, approval.
...
Verification command: see `acceptance_criteria` in the active task on the board.

Pack version: {version}
""".lstrip()
```

- 它只是一个**路由**：告诉 agent 先读什么、按什么顺序读，具体内容在其它文件里。这与第 32 节"别写 3000 行 `AGENTS.md`"的主张一致。
- `{version}` 是 `str.format` 占位符；`.lstrip()` 去掉三引号后紧跟的换行。
- ⚠️ 字段名不一致：这里说 board 上的任务有 `acceptance_criteria`，但 `BOARD_SCHEMA` 中该字段叫 `acceptance`；`acceptance_criteria` 是 scope contract 的字段。agent 按 `AGENTS.md` 去 board 上找会找不到。

### 3.3 四份文档

```python
AGENT_RULES_MD = """# Agent Rules

## startup/state-file-fresh
- category: startup
- check: state_file_fresh
Agent must read agent_state.json before any tool call.
...
"""
```

- 五条规则覆盖第 33 节的五个类别：startup、forbidden、definition_of_done、uncertainty、approval；每条都有 `- check:` 名，意在对应一个可执行的检查函数。
- ⚠️ 这五个 `check:` 名在 `scripts/` 中**没有任何同名实现**；`verify_agent.py` 读取的 `outputs/rule_report.json` 也没有脚本生成。本节 skill 明确把 "Rules without a corresponding check function" 列为 Hard reject，pack 自身没有满足（测验 Q11 的 `lint_pack.py` 实测报出 5 条）。
- `RELIABILITY_POLICY_MD` 把第 26 节的五种失败模式（幻觉动作、scope creep、级联错误、上下文丢失、工具误用）各自映射到一个 surface，并声明 "agents cannot self-override"。
- `HANDOFF_PROTOCOL_MD` 规定 7 个必填字段，并写明 "Missing fields halt the session-end hook"——但 `generate_handoff.py` 从不因缺字段停止（见 3.10）。
- `REVIEWER_RUBRIC_MD`：5 维 × 0–2 分；≥ 7 且无 0 分为 pass，5–6 为 soft fail，< 5 或有 0 分为 hard fail，与第 39 节代码一致。

### 3.4 三个 JSON Schema

```python
STATE_SCHEMA = {
    "$id": "agent_state.schema.json",
    "type": "object",
    "required": ["schema_version", "active_task_id", "touched_files", "next_action"],
    "properties": {
        "schema_version": {"type": "integer", "enum": [1]},
        "active_task_id": {"type": ["string", "null"]},
        ...
```

| Schema | 顶层类型 | 必填字段 | 值得注意的约束 |
|--------|---------|---------|--------------|
| `agent_state` | object | `schema_version`、`active_task_id`、`touched_files`、`next_action` | `schema_version` 只能是 1；`active_task_id` 可为 null |
| `task_board` | array | 每项：`id`、`goal`、`owner`、`acceptance`、`status` | `id` 匹配 `^T-\d{3,}$`；`owner` ∈ builder/reviewer/human；`acceptance` 至少 1 条 |
| `scope_contract` | object | `task_id`、`goal`、`allowed_files`、`forbidden_files`、`acceptance_criteria`、`rollback_plan` | `approvals_required` 可选 |

- 用 Python dict 表示 schema，再 `json.dumps(..., indent=2)` 写出，避免手写 JSON 的引号与逗号错误。
- `r"^T-\d{3,}$"` 是原始字符串（raw string），`\d` 不会被 Python 当成转义。
- ⚠️ 讲义说 "The target repo's `agent_state.json` records which pack version it was initialized against"，但 `STATE_SCHEMA` 没有任何 pack 版本字段；实际版本记录在安装器写的 `.workbench-version`。
- ⚠️ pack 中**没有任何脚本**用这些 schema 做校验（标准库没有 JSON Schema 校验器）。schema 目前只是文档性质的契约。

### 3.5 `bin/install.sh`：安装器

```bash
set -euo pipefail

FORCE="${1:-}"
TARGET="$(pwd)"
PACK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

required=("AGENTS.md" "VERSION" "docs" "schemas" "scripts")
for path in "${required[@]}"; do
    if [[ ! -e "$PACK_ROOT/$path" ]]; then
        echo "missing pack source: $PACK_ROOT/$path" >&2
        exit 1
    fi
done

if [[ -e "$TARGET/AGENTS.md" && "$FORCE" != "--force" ]]; then
    echo "AGENTS.md already exists. Pass --force to overwrite." >&2
    exit 1
fi

cp "$PACK_ROOT/AGENTS.md" "$TARGET/AGENTS.md"
mkdir -p "$TARGET/docs" "$TARGET/schemas" "$TARGET/scripts"
cp -r "$PACK_ROOT/docs/." "$TARGET/docs/"
...
cat "$PACK_ROOT/VERSION" > "$TARGET/.workbench-version"
```

逐行要点：

| 片段 | 含义 |
|------|------|
| `set -euo pipefail` | 任一命令失败即退出（`-e`）、使用未定义变量报错（`-u`）、管道中任一环节失败即视为失败（`pipefail`） |
| `FORCE="${1:-}"` | 取第一个参数，未提供时为空串（配合 `-u` 不会报错） |
| `TARGET="$(pwd)"` | **安装目标是当前目录**，所以要在目标仓库里执行 `/path/to/pack/bin/install.sh` |
| `PACK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"` | 由脚本自身路径推出 pack 根目录的绝对路径，与从哪里调用无关 |
| `required=(...)` + `for` | 先确认 pack 源完整，缺任何一项立刻失败（fail-closed） |
| `[[ -e ... && "$FORCE" != "--force" ]]` | 用 `AGENTS.md` 是否存在判断"是否已安装" |
| `cp -r "$PACK_ROOT/docs/." "$TARGET/docs/"` | 末尾的 `/.` 表示"复制目录内容"而不是把目录本身嵌套进去 |
| `cat VERSION > .workbench-version` | 在目标仓库留下版本锁 |

讲义要求的四件事对照：

| 讲义要求 | 实现情况 |
|---------|---------|
| 无 `--force` 拒绝覆盖已有 pack | 已实现（仅以 `AGENTS.md` 为判据） |
| 复制 pack 到目标仓库 | 已实现（不复制 `bin/`、`README.md`） |
| 存在 `.github/workflows/` 时接入 CI | **未实现** |
| 打印下一步 | 已实现 |
| （Production 部分）符号链接 `CLAUDE.md -> AGENTS.md` | **未实现** |

- ⚠️ 冲突检测太粗：目标仓库若已有自己的 `docs/agent-rules.md` 或 `scripts/` 同名文件、但没有 `AGENTS.md`，会被**静默覆盖**；而且 pack 文档被直接混进项目原有的 `docs/` 目录。
- ⚠️ 提示 "next: edit task_board.json"，但安装器并不创建 `task_board.json` 或 `agent_state.json`（这本身符合"安装器不碰状态"的原则，但用户需要知道从哪里拿模板）。
- ⚠️ `README.md` 的 Quickstart 写 `bin/install.sh`，如果在 pack 目录下照抄执行，`TARGET` 就是 pack 自己（会因 `AGENTS.md` 已存在而拒绝）。正确用法是在目标仓库中以路径调用。
- 除 `--force` 外的任何参数都会被静默忽略，例如 `--dry-run` 不会报错，但也不会生效。

### 3.6 `scripts/init_agent.py`：环境探针

```python
REQUIRED_PYTHON = (3, 10)
REQUIRED_DEPS: list[str] = []
TEST_COMMAND = os.environ.get("WORKBENCH_TEST_COMMAND", "python3")
REQUIRED_ENV: list[str] = []
FRESH_SECONDS = 24 * 60 * 60

def _probe_state() -> tuple[str, str, str]:
    if not STATE_PATH.exists():
        return ("state_freshness", "warn", "no state file yet")
    age = time.time() - STATE_PATH.stat().st_mtime
    ...
```

- 五个探针各返回 `(name, status, detail)` 三元组：Python 版本、依赖可导入、测试命令在 PATH 上、环境变量存在、state 文件新鲜度。
- 状态有三档：`pass` / `warn` / `fail`；只有 `fail` 让脚本返回 1。state 缺失或超过 24 小时只是 `warn`。
- `importlib.util.find_spec(d)` 检查模块能否被找到而不真正导入；`shutil.which(cmd)` 在 PATH 中查找可执行文件。
- `ROOT = Path(__file__).resolve().parent.parent`：脚本位于 `<repo>/scripts/`，所以 ROOT 是目标仓库根目录；`init_report.json` 写在仓库根。
- 依赖列表、环境变量列表默认为空，`TEST_COMMAND` 默认只是 `python3`——"测试命令在 PATH 上"并不能说明测试能跑。这些是"每个仓库安装后需要填写"的槽位，但 README 没有说明。
- `width = max(len(n) for n, _, _ in probes)` 再用 `f"{name:<{width}}"` 做**嵌套格式说明**，按最长名字对齐。

### 3.7 `scripts/run_with_feedback.py`：结构化命令执行

```python
def deterministic_tail(text: str) -> tuple[str, int]:
    lines = text.splitlines()
    if len(lines) <= HEAD_LINES + TAIL_LINES:
        return text, 0
    cut = len(lines) - HEAD_LINES - TAIL_LINES
    return "\n".join(lines[:HEAD_LINES] + [f"...truncated {cut} lines..."] + lines[-TAIL_LINES:]), cut
```

- 输出超过 35 行时保留前 5 行和后 30 行，中间写明截掉了多少行。"确定性"指同样的输入总得到同样的截断结果——给 agent 的上下文可预测，且明确告知被截断（而不是悄悄丢掉）。

```python
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s)
        ...
    except subprocess.TimeoutExpired as exc:
        partial_out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        ...
            exit_code=None, error=f"timeout after {timeout_s}s",
    except FileNotFoundError as exc:
        record.update(stdout_tail="", stderr_tail="", exit_code=None, ...)
    with RECORD.open("a") as fh:
        fh.write(json.dumps(record) + "\n")
```

- 三种结局都会写记录：正常结束（有退出码）、超时（`exit_code=None` + 部分输出）、命令不存在（`exit_code=None` + 错误信息）。"没有退出码"本身就是一条需要 gate 关注的事实。
- `TimeoutExpired` 携带的 `stdout` 即使设置了 `text=True` 也可能是 bytes，所以代码先判断类型再解码——这是一个真实的 Python 细节。
- `RECORD.open("a")`：**追加模式**，日志只增不删，便于审计；但也导致了 gate 的"历史失败永远阻塞"问题（见 3.8）。
- 记录中没有 `task_id`、`session_id`、git commit，后续无法按任务或代码版本过滤。

```python
    ap.add_argument("command", nargs="+")
    ap.add_argument("--note", default="")
```

- ⚠️ 被执行的命令本身带 `-` 开头的参数时必须用 `--` 分隔。实测 `run_with_feedback.py python3 -m pytest -q` → `error: unrecognized arguments: -m pytest -q`，退出码 2，**没有写任何记录**；`run_with_feedback.py -- python3 -m pytest -q` 才正常。
- `return 0 if rec.get("exit_code") == 0 else 1`：runner 的退出码跟随被执行命令，超时或命令不存在都返回 1。

### 3.8 `scripts/verify_agent.py`：确定性 gate

```python
def check_acceptance(accept: list[str], feedback: list[dict]) -> list[dict]:
    findings: list[dict] = []
    commands_run = [_normalize_command(r.get("command")) for r in feedback]
    accept_set = set(accept)
    for cmd in accept:
        if cmd not in commands_run:
            findings.append({"code": "acceptance.missing", "severity": "block", "detail": f"never ran: {cmd}"})
    for r in feedback:
        cmd_str = _normalize_command(r.get("command"))
        if r.get("exit_code") is None:
            findings.append({"code": "feedback.null_exit", "severity": "block", ...})
        elif r.get("exit_code") != 0 and cmd_str in accept_set:
            findings.append({"code": "acceptance.failed", "severity": "block", ...})
    return findings
```

- `_normalize_command` 把列表形式的命令用空格拼成字符串，以便和 contract 中的字符串比较。因此 contract 里要写成与 runner 记录**逐字一致**的形式（`python3 check.py`，而不是 `python check.py` 或多一个空格）。
- 三类 finding：验收命令从未运行（`acceptance.missing`）、任意命令没有退出码（`feedback.null_exit`，包括非验收命令）、验收命令退出码非零（`acceptance.failed`），全部是 block。
- ⚠️ 第二个循环遍历**全部历史记录**：实测"先失败一次、修好后再成功一次"，gate 仍报 `acceptance.failed`。TDD 的"先红后绿"流程会被永久卡住。应只看每条命令的最新记录，并按任务、代码版本过滤（测验 Q10）。

```python
def check_scope(scope_report: dict) -> list[dict]:
    if scope_report.get("forbidden_writes"):   # block
    if scope_report.get("off_scope_writes"):   # warn
```

- 禁区写入为 block、一般越界为 warn——这正是第 41 节代码没有做到的区分。

```python
def run_checks(task_id: str) -> dict[str, object]:
    accept = list(_load_json(ROOT / f"outputs/scope/closed/{task_id}.json", {}).get("acceptance_criteria", []))
    feedback = _load_jsonl(ROOT / "feedback_record.jsonl")
    scope_report = _load_json(ROOT / f"outputs/scope/closed/{task_id}.report.json", {})
    rule_report = _load_json(ROOT / "outputs/rule_report.json", [])
    findings = check_acceptance(accept, feedback) + check_scope(scope_report) + check_rules(rule_report)
    return {"task_id": task_id, "passed": not any(f["severity"] == "block" for f in findings), "findings": findings}
```

- `passed` 的定义：没有任何 block 级 finding。warn 不影响通过。
- ⚠️ **fail-open**：四个输入文件缺失时都退化为空默认值。实测在刚安装的空仓库中 `verify_agent.py T-001` 输出 `"passed": true, "findings": []`，退出码 0。而且 `<task>.report.json` 和 `rule_report.json` 在 pack 中没有任何脚本生成，也就是说 scope 检查和规则检查在默认安装下**永远不会触发**。修正思路：证据缺失本身就是 block（测验 Q9）。

### 3.9 `scripts/generate_handoff.py`：交接包

```python
def derive_risks(verdict: dict, state: dict, review: dict) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    for f in verdict.get("findings", []) or []:
        if isinstance(f, dict) and f.get("severity") in ("warn", "block"):
            risks.append(...)
    for blocker in state.get("blockers") or []:
        risks.append({"severity": "warn", "detail": f"open blocker: {blocker}"})
    try:
        total = int(review.get("total", 10))
    except (TypeError, ValueError):
        total = 10
    if total < 7:
        risks.append(...)
    return risks
```

- 风险来源三处：gate 的 finding、state 中的 blocker、评审总分低于 7。
- `x or []` 是防御 `None` 的惯用法：`verdict.get("findings")` 可能是 `None`。
- ⚠️ 评审报告缺失时 `review={}`，`get("total", 10)` 取默认 10 分，**不产生任何风险**。缺失被当成满分（测验 Q12）。

```python
    payload = {
        "session_id": session_id or str(int(time.time())),
        "summary": f"task {task_id}: gate={verdict.get('passed')} review={review.get('verdict')}",
        "changed_files": diff.get("touched", []),
        "commands_run": [str(r.get("command")) for r in feedback],
        "failed_attempts": [... for r in feedback if r.get("exit_code") not in (0, None)],
        ...
    }
    out = ROOT / "outputs" / "handoff" / payload["session_id"]
```

- 同一份 payload 写成 `handoff.json`（给下一个 agent）和 `handoff.md`（给人），对应第 40 节"双格式"的约定。
- 默认 `session_id` 是秒级时间戳，同一秒内两次生成会互相覆盖。
- `changed_files` 来自 `outputs/diff_summary.json`，同样没有脚本生成，实测总是 `- none`。
- `commands_run` 用 `str(list)` 渲染，得到 `['python3', 'check.py']` 这样的 Python 列表字面量，可读性一般；用 `shlex.join` 会更好。
- `_render_markdown` 中 `def bullets(items): return [f"- {x}" for x in items] or ["- none"]`：空列表为假值，于是返回占位行；`*bullets(...)` 把返回的列表**解包**进外层列表。
- ⚠️ `handoff-protocol.md` 说缺字段要让 session-end hook 停下，但这里所有缺失都被默认值填上、永远返回 0（除非抛异常）。

### 3.10 `write()` 与 `main()`：组装

```python
def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main() -> None:
    write(PACK / "AGENTS.md", AGENTS_MD.format(version=PACK_VERSION))
    ...
    for name, body in SCRIPT_FILES.items():
        write(PACK / "scripts" / name, body)
        (PACK / "scripts" / name).chmod(0o755)
    write(PACK / "bin" / "install.sh", INSTALL_SH)
    (PACK / "bin" / "install.sh").chmod(0o755)
    write(PACK / "VERSION", PACK_VERSION + "\n")
    write(PACK / "README.md", PACK_README)

    for path in sorted(PACK.rglob("*")):
        if path.is_file():
            print(path.relative_to(PACK.parent.parent))
```

- **幂等性**来自"每次都用同样的内容整体覆盖"：不读旧文件、不追加、不依赖上次运行的状态。代价是文件修改时间每次都会变；更讲究的做法是"内容相同就不写"。
- `mkdir(parents=True, exist_ok=True)`：一次创建多级目录，已存在也不报错。
- `chmod(0o755)`：`0o` 前缀是八进制，755 表示所有者可读写执行、其他人可读可执行。
- 内嵌脚本里的 `"\\n"`：外层是普通三引号字符串，`\\n` 写出到文件后变成 `\n`，这样生成的 Python 源码里才是换行转义而不是真实换行。这是"用字符串生成代码"时最容易出错的地方。
- 打印的文件树中还出现了 `AGENTS.zh.md`、`docs/*.zh.md` 等文件——它们是仓库里已有的中文翻译，`main.py` 不生成它们，只是 `rglob` 扫到了。
- ⚠️ 组装器**不会删除** pack 中多余的旧文件：如果某次版本去掉了一个脚本，旧文件会残留在 `outputs/` 里，被安装器一并复制。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 全部内容以字符串常量内嵌在一个 `main.py` 中 | 单文件、零依赖、组装结果完全可复现 | 内嵌代码没有语法高亮、无法单独测试，还要处理 `\\n` 转义；生产中 pack 应是一个真实目录/仓库，脚本有自己的测试 |
| 每次整体覆盖写出 | 幂等简单 | 不清理残留文件；mtime 每次变化 |
| bash 安装器 | 零依赖，`cp` 即可 | 冲突检测只看 `AGENTS.md`；不支持 `--dry-run`；Windows 不友好；讲义练习 2 建议改写成 Python |
| 版本写入 `.workbench-version` | 不修改用户状态文件 | 与讲义"记录在 `agent_state.json`"的说法不一致；需要 lint 校验 |
| Schema 用 dict 生成 JSON | 避免手写 JSON 出错 | 没有脚本用它们校验；标准库无 JSON Schema 校验器，生产中可引入 `jsonschema` 或手写最小校验 |
| gate 输入缺失时取空默认值 | 脚本不会因缺文件崩溃 | fail-open：空仓库也能通过；生产中缺证据应为 block |
| feedback 日志只追加 | 审计友好 | gate 读全部历史，先红后绿永远失败；应加 task/session/commit 字段并只看最新记录 |
| 规则带 `check:` 名但无实现 | 先把契约写下来 | 违反本节 skill 的 Hard reject；应补检查函数或把规则移出 pack |
| handoff 缺数据时用默认值 | 总能生成交接包 | 缺评审被当成满分；与"缺字段即停止"的协议矛盾 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 三引号多行字符串 | `AGENT_RULES_MD = """..."""` | 保留换行；内嵌 Python 源码时用 `'''...'''` 以便内部使用 `"""` |
| `str.format` 占位 | `AGENTS_MD.format(version=PACK_VERSION)` | 用关键字参数填充 `{version}` |
| `.lstrip()` | `""" ... """.lstrip()` | 去掉开头空白（这里是三引号后的换行） |
| 原始字符串 | `r"^T-\d{3,}$"` | 反斜杠不转义，适合写正则 |
| 转义的转义 | 内嵌脚本中的 `"\\n"` | 外层字符串里的 `\\n` 写入文件后成为 `\n` |
| 嵌套 dict 字面量 | `STATE_SCHEMA = {"type": "object", ...}` | 直接表达 JSON 结构 |
| 带类型注解的变量 | `SCRIPT_FILES: dict[str, str] = {...}`、`REQUIRED_DEPS: list[str] = []` | 标注容器元素类型 |
| `dict.items()` 遍历 | `for name, body in SCRIPT_FILES.items():` | 同时取键和值 |
| 八进制字面量 | `chmod(0o755)` | Unix 权限位 |
| `Path.rglob` + `sorted` | `sorted(PACK.rglob("*"))` | 递归列出所有文件并排序，输出稳定 |
| `Path.relative_to` | `path.relative_to(PACK.parent.parent)` | 打印相对路径 |
| `Path.resolve()` | `Path(__file__).resolve().parent.parent` | 先变成绝对路径再取父目录，避免相对路径或符号链接带来的偏差 |
| 元组返回值 | `def _probe_runtime() -> tuple[str, str, str]` | 一次返回多个值 |
| 推导式中的元组解包 | `[{"name": n, "status": s, "detail": d} for n, s, d in probes]` | 遍历三元组 |
| 生成器表达式 + `max` | `max(len(n) for n, _, _ in probes)` | 不建中间列表求最大值 |
| 嵌套格式说明 | `f"{name:<{width}}  {status:>4}"` | 宽度本身来自变量 |
| `x or default` | `verdict.get("findings", []) or []`、`session_id or str(int(time.time()))` | `None`/空值时取默认 |
| `try/except` 多异常 | `except (TypeError, ValueError):` | 一次捕获多种异常 |
| 异常对象属性 | `exc.stdout`（`subprocess.TimeoutExpired`） | 超时异常携带部分输出 |
| `isinstance` 分支 | `exc.stdout.decode(...) if isinstance(exc.stdout, bytes) else (...)` | 条件表达式处理 bytes/str 两种情况 |
| `with ... open("a")` | `with RECORD.open("a") as fh:` | 追加写，退出时自动关闭文件 |
| `dict.update(**kw)` | `record.update(stdout_tail=out, exit_code=...)` | 一次添加多个键 |
| `argparse` | `ap.add_argument("command", nargs="+")` | `nargs="+"` 收集一个或多个位置参数 |
| `raise SystemExit(main())` | 每个脚本末尾 | 把 `main()` 的返回值作为进程退出码 |
| 列表解包 | `*bullets(p["changed_files"])` | 把子列表展开进外层列表字面量 |
| `str \| None` 联合类型 | `session_id: str \| None = None` | 3.10+ 语法；配合 `from __future__ import annotations` 可在旧版本注解中使用 |
| `print(..., file=sys.stderr)` | `print("verification failed", file=sys.stderr)` | 错误信息写到标准错误 |

bash 部分：`set -euo pipefail`、`"${1:-}"`（缺省值展开）、`$(...)` 命令替换、数组 `("a" "b")` 与 `"${arr[@]}"`、`[[ -e path ]]` 文件存在测试、`>&2` 重定向到标准错误。

---

## 6. 运行结果解读

**组装器**（Python 3.13，在临时目录的本节副本中运行，退出码 0）：

```text
outputs/agent-workbench-pack/AGENTS.md
outputs/agent-workbench-pack/AGENTS.zh.md          ← 仓库中已有的翻译，非 main.py 生成
outputs/agent-workbench-pack/README.md
outputs/agent-workbench-pack/README.zh.md
outputs/agent-workbench-pack/VERSION
outputs/agent-workbench-pack/bin/install.sh
outputs/agent-workbench-pack/docs/agent-rules.md
...
outputs/agent-workbench-pack/schemas/task_board.schema.json
outputs/agent-workbench-pack/scripts/generate_handoff.py
outputs/agent-workbench-pack/scripts/init_agent.py
outputs/agent-workbench-pack/scripts/run_with_feedback.py
outputs/agent-workbench-pack/scripts/verify_agent.py
```

- 共 21 个文件（15 个由 `main.py` 写出：`AGENTS.md`、4 份文档、3 个 schema、4 个脚本、`install.sh`、`VERSION`、`README.md`；另外 6 个是已有的 `.zh.md`）。
- 与仓库中已提交的 `outputs/` 做 `diff -r`：完全一致；再运行一次：仍然一致——满足 mission 的"幂等"验收。脚本和安装器权限为 `-rwxr-xr-x`。

**在空目录中安装并试用**（逐条实测）：

| 操作 | 实际结果 | 解读 |
|------|---------|------|
| `bash <pack>/bin/install.sh` | `pack installed at version 1.0.0`，目标中出现 `AGENTS.md`、`docs/`、`schemas/`、`scripts/`、`.workbench-version` | 没有 `agent_state.json`、`task_board.json`、reviewer 脚本 |
| 再次执行（无 `--force`） | `AGENTS.md already exists. Pass --force to overwrite.`，退出码 1 | 拒绝覆盖生效 |
| `install.sh --force` | 重新安装，退出码 0 | |
| `python3 scripts/init_agent.py` | runtime/dependencies/test_command/env 均 `pass`，`state_freshness warn no state file yet`，退出码 0 | 依赖与环境变量列表为空，所以必然通过 |
| `python3 scripts/verify_agent.py T-001`（无任何证据） | `"passed": true, "findings": []`，退出码 0 | **fail-open** |
| `run_with_feedback.py python3 -m pytest -q` | `unrecognized arguments: -m pytest -q`，退出码 2 | 需要 `--` |
| contract 设 `python3 check.py`，先失败后成功，再跑 gate | `"passed": false`，`acceptance.failed: exit 1 on python3 check.py` | 历史失败永久阻塞 |
| 无评审报告时 `generate_handoff.py T-001 --session-id s1` | 生成 `handoff.md`；`open_risks` 只有 gate 的 block，没有"评审缺失"；Receipts 指向不存在的 review 文件 | 缺失被当满分 |

这些结果说明：pack 的**组装和安装**是可靠的，但 surface 之间的**契约**还有几处断裂。这也是 skill 要求 `lint_pack.py` 的原因。

---

## 7. 动手改一改

1. **补齐安装器**（讲义练习 2）：把 `install.sh` 改写成 `install.py`，支持 `--dry-run`（只打印将创建/覆盖的文件）和冲突报告（目标已有同名文件时列出并拒绝，除非 `--force`）；检测到 `.github/workflows/` 时写入一个运行 gate 的 workflow；创建 `CLAUDE.md -> AGENTS.md` 符号链接。
2. **写 `uninstall.sh`**（讲义练习 3）：只删 schemas、scripts、docs 中属于 pack 的文件和 `AGENTS.md`（支持 `--keep-agents-md`）；用 `git status --porcelain agent_state.json task_board.json` 判断状态文件是否有未提交改动，有则拒绝。思考"non-trivial history"的定义（例如 `git log` 中状态文件提交数 > 1）。
3. **写 `lint_pack.py`**（讲义练习 4）：检查 `VERSION` 格式、`AGENTS.md` 中的版本、schema 可解析、规则 `check:` 有实现、字段名一致（参考测验 Q11，在当前 pack 上应报出 6 条问题）。
4. **让 gate fail-closed**：缺 contract、acceptance 为空、缺 scope 报告或规则报告都产生 block；每条验收命令只看最新记录（参考测验 Q9、Q10）。同时给 `run_with_feedback.py` 的记录加上 `task_id` 与 `git rev-parse HEAD`。
5. **修 handoff**：评审缺失时加 block 风险，缺必填字段时返回非零退出码，Receipts 只列存在的文件（参考测验 Q12）。
6. **进阶**：给内嵌的四个脚本各写 3–5 个单元测试（可以把常量写到临时目录再 `import`），并把"组装 → 安装 → init → runner → gate → handoff"的端到端流程写成一个冒烟测试，接到 pack 自身仓库的 CI 中。

---

## 8. 常见坑

- **在 pack 目录里运行安装器**：`TARGET` 是当前目录，应在目标仓库中以 `/path/to/pack/bin/install.sh` 方式调用。
- **只靠 `AGENTS.md` 判断是否已安装**：目标仓库已有的同名文档或脚本会被静默覆盖。
- **命令带 `-` 参数时忘了 `--`**：runner 直接报错退出，不写任何记录；agent 若不看退出码，会误以为"已经跑过验收"。
- **contract 中的命令与实际执行的命令写法不同**：`_normalize_command` 是逐字比较，`python` 与 `python3`、多余空格都会导致 `acceptance.missing`。
- **把 gate 的 `passed: true` 当成证据**：先确认 contract、scope 报告、规则报告这些输入真的存在，否则通过毫无意义。
- **反复删 `feedback_record.jsonl` 来让 gate 通过**：这是在销毁审计记录；应修正 gate 只看最新、相关的记录。
- **生成代码时转义写错**：内嵌脚本里的 `"\\n"` 若写成 `"\n"`，生成的 Python 文件里字符串字面量会被真实换行打断，导致语法错误。
- **以为重复组装会清理旧文件**：`main.py` 只覆盖、不删除，被移除的脚本会残留在 `outputs/` 中并被安装出去。
- **把具体任务塞进 pack**：违反"任务属于目标仓库的 board"的边界，pack 就不再可移植。
