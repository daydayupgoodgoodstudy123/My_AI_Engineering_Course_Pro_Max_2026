# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 01 节 综合项目 01：终端原生 Coding Agent ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数；在 `code/` 目录下运行） ｜ **依赖**：仅标准库（`json`、`os`、`subprocess`、`time`、`dataclasses`、`typing`）；无需网络、API key 或 GPU。同目录下另有一个 TypeScript 版 `ts/`（需 Node.js + `npm install`，依赖 `zod`、`tsx`、`typescript`），见 3.9。

---

## 1. 这份代码在考察什么

讲义要你用 35 小时构建一个"CLI 进、PR 出"的完整 coding agent：Bun + Ink 的 TUI、TodoWrite 计划、6 个经 MCP 暴露的工具、E2B / Daytona 沙箱、8 种 hook、三层预算、OpenTelemetry 追踪、在 SWE-bench Pro 上与 mini-swe-agent 对比。

`main.py` 不是这个完整系统，而是它的**最小骨架**。模块 docstring 说得很清楚："The hard architectural primitive ... is the plan-act-observe-recover loop with bounded context, a structured plan state, a sandboxed tool dispatcher, and hook callbacks at every lifecycle point." 为了让循环逻辑可观察、可测试，它把 LLM 换成了一个**确定性脚本**。

它对应讲义的这些概念：

1. **计划状态（TodoWrite）**：`TodoItem` / `PlanState`，每轮整体重写；
2. **预算**：`Budget` 的 50 轮 / 200k tokens / $5 三道上限；
3. **hook 总线**：`HookBus` 的 8 种事件，`PreToolUse` 上挂破坏性命令拦截；
4. **工具面**：`read_file`（带沙箱路径检查）、`run_shell`（带超时），输出截断到 4096 个字符；
5. **主循环**：`run_agent` 中的"预算检查 → 模型一步 → PreToolUse → 执行 → PostToolUse"。

同时要看清它**没有实现**的部分：没有真实模型、观察结果不回灌给模型、没有 Recover 逻辑、只有 2 个工具、没有真正的沙箱和 worktree、没有 PreCompact / 持久化 / OTel。这些空白，以及几处真实的 bug（路径前缀绕过、预算超支、失败后仍报告完成），正是本节练习和面试追问的重点。

> 一句话：**用 240 行标准库代码把 coding agent 的"循环 + 计划 + 预算 + hook + 工具"骨架摆出来，让你看清 harness 的形状——也看清一个骨架离可用的 harness 还差什么。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TodoItem` | dataclass | 一条计划项：`id`、`description`、`status`、`note` | TodoWrite 条目 |
| `PlanState` | dataclass | `goal` + `items`；`summary()` 渲染为 `[x]/[>]/[ ]/[!]` 列表 | 计划状态 |
| `Budget` | dataclass | 三个上限 + 三个已用量；`step()` 记账，`exceeded()` 返回停止原因 | 三层成本控制 |
| `HookFn` | 类型别名 | `Callable[[dict], dict]` | hook 函数签名 |
| `HookBus` | 类 | 8 种事件的监听器表；`on()` 注册，`fire()` 依次调用 | 2026 hook 面 |
| `TRUNCATE_BYTES` | 常量 4096 | 工具输出截断上限（实际按字符截断） | 输出截断 |
| `tool_read_file` | 函数 | 沙箱内读文件，`realpath` 前缀检查 | 工具 + 沙箱 |
| `tool_run_shell` | 函数 | `subprocess.run(shell=True)`，带超时，合并 stdout/stderr | 工具 |
| `TOOLS` | 字典 | 工具名 → 函数 | 工具分派表 |
| `SCRIPT` | 列表 | 3 步脚本：每步给出计划、工具调用、tokens、cost | 假模型的"剧本" |
| `model_step` | 函数 | 按轮次返回脚本内容；超出脚本则结束 | 被替身的 LLM |
| `destructive_guard` | 函数 | `PreToolUse` hook：命中 `rm -rf` / `shutdown` 则标记 blocked | 破坏性命令拦截 |
| `run_agent` | 函数 | 主循环，注册 hook、记账、分派工具、收集 trace | plan/act/observe 循环 |
| `main` | 函数 | 以 `code/` 目录为沙箱运行一次，打印计划、预算、trace | 演示入口 |

数据流：`main()` → `run_agent(task, sandbox)` → 每轮：`budget.exceeded()` → `model_step()` 得到 `{plan, tool, tokens, cost}` → 整体替换 `plan.items` → `budget.step()` → `PreToolUse`（可能 blocked）→ `TOOLS[name](sandbox, **args)` → `PostToolUse` 写入 trace → 下一轮；结束时 `SessionEnd` → 返回 `{plan 摘要, budget 字典, trace 列表}`。

---

## 3. 逐段精讲

### 3.1 计划状态：`TodoItem` 与 `PlanState`

```python
@dataclass
class TodoItem:
    id: int
    description: str
    status: str  # "pending" | "in_progress" | "done" | "failed"
    note: str = ""


@dataclass
class PlanState:
    goal: str
    items: list[TodoItem] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"GOAL: {self.goal}"]
        for it in self.items:
            mark = {"pending": " ", "in_progress": ">", "done": "x", "failed": "!"}[it.status]
            lines.append(f"  [{mark}] {it.id}. {it.description}")
        return "\n".join(lines)
```

- 对应讲义 Build It 第 2 步的"typed TodoWrite schema (pending / in_progress / done items with notes)"。代码多了一个 `failed` 状态，渲染为 `[!]`。
- `status: str` 只用注释说明了取值范围，类型上并不受约束；写错状态（如 `"Done"`）会在 `summary()` 的字典查找时抛 `KeyError`。更严格的写法是 `Literal["pending", "in_progress", "done", "failed"]` 或 `Enum`——TypeScript 版就用了联合类型 `type Status = "pending" | "in_progress" | "done" | "failed"`，编译期即可检查。
- `items: list[TodoItem] = field(default_factory=list)`：dataclass 中可变默认值必须用 `default_factory`，否则所有实例会共享同一个列表（Python 会直接报错 `ValueError: mutable default ... is not allowed`）。
- `summary()` 用一个临时字典把状态映射为符号，是一种简洁的"查表代替 if-elif"写法。
- 讲义要求把计划持久化到 `.agent/state.json` 以便崩溃恢复，代码**没有实现**持久化。

### 3.2 预算：`Budget`

```python
@dataclass
class Budget:
    max_turns: int = 50
    max_tokens: int = 200_000
    max_dollars: float = 5.00
    turns_used: int = 0
    tokens_used: int = 0
    dollars_used: float = 0.0

    def step(self, tokens: int, dollars: float) -> None:
        self.turns_used += 1
        self.tokens_used += tokens
        self.dollars_used += dollars

    def exceeded(self) -> str | None:
        if self.turns_used >= self.max_turns:
            return "turn_limit"
        if self.tokens_used >= self.max_tokens:
            return "token_limit"
        if self.dollars_used >= self.max_dollars:
            return "dollar_limit"
        return None
```

- 三个默认值正是讲义 Build It 第 7 步的 "50 turns, 200k context, $5 per task"。`200_000` 中的下划线是数字分隔符，只为可读。
- `exceeded()` 返回**停止原因字符串**或 `None`，调用方可以写 `if stop := budget.exceeded()` 或 `stop = ...; if stop:`。三个检查有先后，同时超出时只报第一个。
- **语义差异**：讲义的 "200k context" 指**单次请求的上下文窗口**，而 `tokens_used` 是**整个会话的累计 token**。累计 token 更接近"成本"，上下文大小则需要另外跟踪（这也是 `PreCompact` 在 150k 时触发的依据）。代码把两者混为一个计数器。
- 讲义还提到"per-turn token ceiling"（每轮上限），代码没有实现。
- `step()` 不检查负数输入；TypeScript 版加了 `RangeError`。
- 浮点累加：0.02 + 0.02 + 0.01 在本例中恰好得到 0.05，但一般来说美元金额累加会有浮点误差，生产中常用整数"微美元"或 `decimal.Decimal` 记账。

### 3.3 hook 总线：`HookBus`

```python
HookFn = Callable[[dict[str, Any]], dict[str, Any]]


class HookBus:
    EVENTS = ("SessionStart", "SessionEnd", "PreToolUse", "PostToolUse",
              "UserPromptSubmit", "Notification", "Stop", "PreCompact")

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookFn]] = {e: [] for e in self.EVENTS}

    def on(self, event: str, fn: HookFn) -> None:
        self._hooks[event].append(fn)

    def fire(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        for fn in self._hooks[event]:
            payload = fn(payload) or payload
        return payload
```

- `EVENTS` 是讲义列出的 8 种事件；类属性用元组，表示固定不变。
- `fire()` 实现了**管道式**（pipeline）调用：按注册顺序依次调用，上一个 hook 的返回值作为下一个的输入，最终返回给调用方。这让 `PreToolUse` hook 可以通过在 payload 中写入 `blocked: True` 来"否决"工具调用。
- `fn(payload) or payload`：hook 返回 `None` 时沿用原 payload。副作用是：返回空字典 `{}` 也会被当作"没返回"（实测 `fire` 返回原 payload）。更精确的写法是 `if result is not None`。
- `on()` 遇到未知事件名会抛 `KeyError`（实测 `on("PreTooluse", ...)` → `KeyError: 'PreTooluse'`）——"快速失败"是好事，但错误信息可以更友好。
- 8 种事件中，`run_agent` 实际 **fire** 了 5 种（SessionStart、PreToolUse、PostToolUse、Stop、SessionEnd），**注册监听器**的只有 4 种（Stop 没有监听器）；`UserPromptSubmit`、`Notification`、`PreCompact` 只是声明，从未触发。
- 真实系统（如讲义参考的 Claude Code）的 hook 往往是外部脚本，通过 stdin/stdout 传 JSON、用退出码表示放行或阻止；这里用进程内的 Python 函数模拟。

### 3.4 工具面：`tool_read_file` 与 `tool_run_shell`

```python
TRUNCATE_BYTES = 4096


def tool_read_file(sandbox: str, path: str) -> str:
    full = os.path.join(sandbox, path)
    if not os.path.realpath(full).startswith(os.path.realpath(sandbox)):
        raise RuntimeError("path escapes sandbox")
    with open(full, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()[:TRUNCATE_BYTES]
```

- `os.path.realpath` 会规范化 `..` 并解析符号链接，所以 `../../../etc/passwd` 会解析为 `/etc/passwd` 被拦截；`os.path.join(sandbox, "/etc/passwd")` 遇到绝对路径会丢弃前面的部分，同样被拦截（均已实测）。
- **漏洞：字符串前缀不等于目录包含**。若沙箱是 `/work/sb`，存在同级目录 `/work/sb-evil`，那么 `"../sb-evil/secret.txt"` 解析为 `/work/sb-evil/secret.txt`，它的字符串以 `/work/sb` 开头，检查通过。我们在临时目录中复现：读到了 `TOP SECRET`。修复方式是 `os.path.commonpath([full_real, root]) == root`，或在前缀后加 `os.sep`（TypeScript 版的写法，见 3.9）。
- 还有一个小问题：检查用的是 `realpath(full)`，但 `open()` 打开的是未解析的 `full`。在检查与打开之间如果符号链接被替换，就是经典的 TOCTOU（检查时与使用时不一致）问题；直接打开已解析的路径更稳妥。
- `errors="replace"`：遇到非 UTF-8 字节用 `�` 替换而不是抛异常，适合读取未知编码的仓库文件。
- `[:TRUNCATE_BYTES]` 截的是**字符**不是字节，也不是 token：实测 5000 个汉字截取后是 4096 个字符、12,288 个 UTF-8 字节。讲义要求的是"cap at 4k tokens per call"，4096 个英文字符大约只有 1k tokens，所以这里比讲义更保守；对中文则又超出不少。另外它先 `read()` 整个文件再截断，对超大文件会先把全部内容读进内存，可以改为 `fh.read(TRUNCATE_BYTES)`。

```python
def tool_run_shell(sandbox: str, cmd: str, timeout: int = 30) -> str:
    proc = subprocess.run(cmd, cwd=sandbox, shell=True, capture_output=True,
                          text=True, timeout=timeout)
    out = (proc.stdout + proc.stderr)[:TRUNCATE_BYTES]
    return f"exit={proc.returncode}\n{out}"


TOOLS: dict[str, Callable[..., str]] = {
    "read_file": tool_read_file,
    "run_shell": tool_run_shell,
}
```

- `subprocess.run(..., shell=True)`：命令字符串交给 `/bin/sh` 解释，支持管道和 `;`，但也意味着任何 shell 语法都能执行。**`cwd=sandbox` 只是设置工作目录，并不是隔离**——命令可以 `cd ..` 或访问任何绝对路径。真正的隔离依赖讲义中的 E2B / Daytona 容器。
- `capture_output=True` 捕获 stdout 与 stderr；`text=True` 返回字符串而非字节。
- `timeout=30`：超时会抛 `subprocess.TimeoutExpired`（实测 `sleep 2` 配 `timeout=1` 抛出该异常），在 `run_agent` 中会被 `except Exception` 捕获并记为 `ok: False`。注意 `shell=True` 时超时只会杀死 shell 进程，shell 启动的子进程可能残留。
- 返回 `exit=<code>\n<输出>`：把退出码放进观察结果，对应讲义 "Observe captures stdout / stderr / exit codes"。stdout 与 stderr 直接拼接，丢失了交错顺序和来源信息。
- `TOOLS` 只有 2 个工具，讲义要求 6 个（另有 `edit_file`、`ripgrep`、`tree_sitter_symbols`、`git`）。分派表模式使新增工具只需加一个字典项。

### 3.5 假模型：`SCRIPT` 与 `model_step`

```python
SCRIPT = [
    {"plan": [("locate target file", "in_progress"),
              ("read and diagnose", "pending"),
              ("apply fix and verify", "pending")],
     "tool": ("run_shell", {"cmd": "ls"}),
     "tokens": 1200, "cost": 0.02},
    {"plan": [("locate target file", "done"),
              ("read and diagnose", "in_progress"),
              ("apply fix and verify", "pending")],
     "tool": ("read_file", {"path": "README.md"}),
     "tokens": 900, "cost": 0.02},
    {"plan": [...全部 done...],
     "tool": None,  # terminal turn
     "tokens": 600, "cost": 0.01},
]


def model_step(plan: PlanState, turn: int) -> dict[str, Any]:
    """Stubbed model: returns a plan rewrite and (optionally) a tool call."""
    if turn >= len(SCRIPT):
        return {"plan": plan.items, "tool": None, "tokens": 200, "cost": 0.005}
    s = SCRIPT[turn]
    items = [TodoItem(i + 1, desc, status) for i, (desc, status) in enumerate(s["plan"])]
    return {"plan": items, "tool": s["tool"], "tokens": s["tokens"], "cost": s["cost"]}
```

- 每一步返回的结构就是"模型输出"的抽象：**完整的新计划** + **可选的工具调用** + **本轮 token 与成本**。`tool: None` 表示模型认为任务完成（终止轮）。
- 计划每轮都是全新构造的 `TodoItem` 列表，对应讲义"整体重写，不增量修改"。
- 列表推导式里 `for i, (desc, status) in enumerate(...)` 同时做了枚举和元组解包，`i + 1` 作为 1 起始的 id。
- 超出脚本长度时返回当前计划、`tool: None`，保证循环一定会结束。
- **关键限制**：`model_step` 的输入只有 `plan` 和 `turn`，**不包含任何工具输出**。也就是说，模型"看不到"观察结果，无论工具成功还是失败，它都按剧本推进。这就是为什么默认运行中 `read_file` 失败了，计划仍然全部变成 `done`。真实 harness 中，模型的输入是完整的消息历史（含每次工具结果）。
- 0.02 + 0.02 + 0.01 = 0.05 美元、1200 + 900 + 600 = 2700 tokens，这就是运行输出中 `turns=3 tokens=2700 dollars=$0.050` 的来源。

### 3.6 破坏性命令拦截：`destructive_guard`

```python
def destructive_guard(payload: dict[str, Any]) -> dict[str, Any]:
    cmd = payload.get("args", {}).get("cmd", "")
    if "rm -rf" in cmd or "shutdown" in cmd:
        payload["blocked"] = True
        payload["reason"] = "destructive command blocked by PreToolUse hook"
    return payload
```

- `payload.get("args", {}).get("cmd", "")`：链式 `get` 带默认值，对 `read_file` 这类没有 `cmd` 参数的调用也不会报错。
- 命中后**原地修改** payload 并返回同一个对象。
- 子串黑名单的问题（全部实测）：`rm -fr /`、`rm -r -f /`、`rm  -rf /`（两个空格）、`RM -RF /`、`find . -delete`、用 Python 的 `shutil.rmtree` 删除都**不会被拦截**；`grep shutdown_handler src` 却会被**误拦截**。
- 讲义的要求是"blocks `rm -rf` outside the worktree"——代码既不区分路径（worktree 内外一律拦截），也覆盖不了变体。改进方向见测验 Q10：`shlex` 解析、白名单、以及最根本的沙箱隔离。

### 3.7 主循环：`run_agent`

```python
def run_agent(task: str, sandbox: str) -> dict[str, Any]:
    plan = PlanState(goal=task, items=[])
    budget = Budget()
    hooks = HookBus()
    trace: list[dict[str, Any]] = []

    hooks.on("PreToolUse", destructive_guard)
    hooks.on("PostToolUse", lambda p: (trace.append({"event": "tool", **p}), p)[1])
    hooks.on("SessionStart", lambda p: (trace.append({"event": "start", **p}), p)[1])
    hooks.on("SessionEnd", lambda p: (trace.append({"event": "end", **p}), p)[1])

    hooks.fire("SessionStart", {"task": task, "sandbox": sandbox,
                                "started_at": time.time()})
```

- 每次运行都新建计划、预算、hook 总线和 trace 列表，运行之间互不影响。
- **lambda 元组技巧**：`lambda p: (trace.append({...}), p)[1]`。lambda 只能写一个表达式，作者用"构造二元组再取第 2 个元素"的方式在一个表达式里先执行 `append`（副作用，返回 `None`）再返回 `p`。可读性较差，普通 `def` 函数更清楚。
- `{"event": "tool", **p}`：字典解包，把 payload 的所有键合并进新字典。
- trace 就是本 demo 的"可观测性"：讲义要求的是 OTel span 发送到 Langfuse。

```python
    turn = 0
    while True:
        stop = budget.exceeded()
        if stop:
            hooks.fire("Stop", {"reason": stop, "turn": turn})
            break

        step = model_step(plan, turn)
        plan.items = step["plan"]
        budget.step(step["tokens"], step["cost"])

        call = step["tool"]
        if call is None:
            hooks.fire("Stop", {"reason": "complete", "turn": turn})
            break

        name, args = call
        pre = hooks.fire("PreToolUse", {"tool": name, "args": args})
        if pre.get("blocked"):
            hooks.fire("PostToolUse", {"tool": name, "blocked": True,
                                       "reason": pre.get("reason", "")})
            turn += 1
            continue

        try:
            result = TOOLS[name](sandbox, **args)
            hooks.fire("PostToolUse", {"tool": name, "ok": True,
                                       "bytes": len(result)})
        except Exception as exc:
            hooks.fire("PostToolUse", {"tool": name, "ok": False,
                                       "error": str(exc)})

        turn += 1
```

逐步对应讲义的四个面：

| 步骤 | 代码 | 对应 |
|------|------|------|
| 预算检查 | `budget.exceeded()` | 成本控制（轮数 / token / 美元） |
| 模型一步 | `model_step(plan, turn)` | 模型调用（这里是脚本） |
| 计划重写 | `plan.items = step["plan"]` | **Plan**：整体替换 |
| 记账 | `budget.step(...)` | token / 美元记账 |
| 终止判断 | `if call is None` | 模型声明完成 |
| 工具前 hook | `hooks.fire("PreToolUse", ...)` | guardrail，可 blocked |
| 执行工具 | `TOOLS[name](sandbox, **args)` | **Act** |
| 工具后 hook | `hooks.fire("PostToolUse", ...)` | **Observe**（只记录，不回灌） |
| 异常处理 | `except Exception` | **Recover**（只记录，不恢复） |

需要注意的细节与问题：

- **被拦截时也触发 `PostToolUse`**，payload 带 `blocked: True`，于是 trace 中能看到拦截记录（审计需要）。被拦截不会终止会话，下一轮继续。
- **预算可能超支一轮**：检查只在每轮开头。实测 `max_dollars=0.03` 时，第 2 轮开头 0.02 < 0.03 放行，记账后变为 0.04，第 2 轮的工具照样执行，第 3 轮开头才停止——最终超出上限 33%。TypeScript 版在记账后又检查了一次（`postStepLimit`）。
- **观察结果被丢弃**：`result` 只取了长度。模型下一轮看不到工具输出，所以 Observe 只完成了"捕获与记录"，没有完成"回灌"。
- **Recover 只是"不崩溃"**：`except Exception` 保证了工具异常不会让循环崩溃，但没有重试、没有把错误告诉模型、没有修改计划。讲义要求"handles tool errors without blowing the context window or looping forever"——前半句（不撑爆上下文）因为没有上下文所以谈不上，后半句（不无限循环）由预算兜底。
- **未知工具名**：`TOOLS[name]` 会抛 `KeyError`，被捕获后记录为 `error: "'edit_file'"`（实测），信息不够清楚，应在分派前校验工具名并返回可读的错误。
- **`**args` 解包**：工具调用的参数字典直接展开为关键字参数，`{"cmd": "ls"}` 变成 `tool_run_shell(sandbox, cmd="ls")`。如果模型给出了多余或拼错的参数，会抛 `TypeError`——这正是 TypeScript 版用 zod 做参数校验、以及第 21 节"带 Schema 校验的工具注册表"要解决的问题。

```python
    hooks.fire("SessionEnd", {"turns": budget.turns_used,
                              "tokens": budget.tokens_used,
                              "dollars": budget.dollars_used})

    return {"plan": plan.summary(), "budget": asdict(budget), "trace": trace}
```

- `SessionEnd` 记录最终用量。
- `asdict(budget)` 把 dataclass 递归转换为普通字典，便于 JSON 序列化。
- **返回值中没有停止原因**：是正常完成还是撞到预算，调用方只能从计划状态去猜（实测 `max_turns=2` 时返回值里看不到 `turn_limit`）。

### 3.8 入口：`main`

```python
def main() -> None:
    task = "demonstrate the plan-act-observe loop without network calls"
    sandbox = os.path.dirname(os.path.abspath(__file__))
    result = run_agent(task, sandbox)
    print(result["plan"])
    ...
    for ev in result["trace"]:
        print(" ", json.dumps(ev, default=str))
```

- 沙箱被设为 `main.py` 所在目录 `code/`。由于 `README.md` 位于 `code/ts/` 而不在 `code/`，脚本第 2 步的 `read_file README.md` 必然失败。
- `json.dumps(ev, default=str)`：遇到无法序列化的对象时调用 `str()` 兜底；这里 trace 中都是基本类型，`default` 实际上没有用到。
- `f"dollars=${...:.3f}"`：`$` 是普通字符，`:.3f` 保留 3 位小数。
- `run_shell` 的 `ls` 会真实执行；输出依赖目录内容（例如运行过导入实验后多出 `__pycache__`，`bytes` 就会变化）。

### 3.9 对照：TypeScript 版 `code/ts/`

`code/ts/` 是同一骨架的多文件 TypeScript 实现（`index.ts`、`harness.ts`、`hooks.ts`、`model.ts`、`tools.ts`、`plan.ts`、`eval.ts`、`repl.ts`、`types.ts`，以及两个测试文件）。它不在本讲解的单独讲解范围内，但与 `main.py` 对照很有启发：

| 方面 | `main.py` | TypeScript 版 |
|------|-----------|--------------|
| 运行时 | Python 标准库 | Node.js + `tsx`（讲义写的是 Bun，实际 `package.json` 用 tsx） |
| `run_shell` | **真实执行** `subprocess.run(shell=True)` | **桩**：`ls`、`git status` 返回固定文本，其余返回 `(stub) ran: ...` |
| 参数校验 | 无 | `zod` schema（`ReadFileArgs`、`RunShellArgs`，拒绝空字符串） |
| 路径检查 | `startswith(root)`，有前缀绕过漏洞 | `full !== root && !full.startsWith(root + path.sep)`，无此漏洞；`realpathSync` 失败也视为逃逸 |
| 拦截规则 | 子串 `"rm -rf"` / `"shutdown"` | 正则 `/\brm\s+-rf\b/`、`/\bshutdown\b/`，先 `toLowerCase()`；能处理多空格和大小写，仍漏 `rm -fr` |
| `Stop` 监听 | 无，trace 中没有 stop | 有，trace 中多一条 `stop` |
| 预算 | 每轮开头检查 | 开头检查 + 记账后再检查（`postStepLimit`），避免超支执行工具；但它把预算停止也标记为 `completed = true` |
| 结果 | `{plan, budget, trace}` | 增加 `passed = completed && allDone` |
| 评估 | 无 | `eval.ts` 跑 3 个离线任务，`index.ts` 断言 `passed=3 failed=0` |
| 交互 | 无 | `repl.ts`：`run <task>` / `eval` / `help` / `quit` |

我们把 `ts/` 复制到临时目录执行 `npm install` 后实际运行（未在课程目录内安装依赖）：

```text
$ npm start
GOAL: demonstrate the plan-act-observe loop without network calls
  [x] 1. locate target file
  [x] 2. read and diagnose
  [x] 3. apply fix and verify
---
turns=3 tokens=2700 dollars=$0.050
---
trace events: 5
  {"event":"start",...}
  {"event":"tool","tool":"run_shell","ok":true,"bytes":26}
  {"event":"tool","tool":"read_file","ok":true,"bytes":1286}
  {"event":"stop","reason":"complete","turn":2}
  {"event":"end","turnsUsed":3,"tokensUsed":2700,"dollarsUsed":0.05}
---
eval: passed=3 failed=0

$ npm test        # 13 个测试全部通过（harness 8 个、tools 5 个）
$ npm run typecheck   # tsc --noEmit 无报错
```

TS 版的 `sandbox` 是 `ts/` 目录，README.md 恰好在那里，所以 `read_file` 成功（1286 字节）；Python 版因沙箱是 `code/` 而失败。两者用的是同一份脚本，结果差异完全来自"沙箱目录里有没有这个文件"——这也说明脚本化模型对环境变化毫无反应。TS 测试覆盖了：脚本任务收敛到全部完成、离线评估 3/3、hook 按注册顺序触发、拦截 `rm -rf` 且放行 `ls`、轮数上限、计划渲染、REPL 命令解析、沙箱内读文件、拒绝 `../../../etc/passwd`、桩命令输出、zod 拒绝空参数、工具注册表。没有测试覆盖"同级目录前缀"和"拦截规则变体"这类边界情况。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用确定性脚本代替 LLM | 无网络、可复现、可测试，聚焦循环本身 | 模型不读观察结果，失败后仍报告完成；生产中通过 OpenRouter 等接入真实模型，并把工具结果放回消息历史 |
| 计划每轮整体替换 | 讲义要求"不增量修改"，状态始终自洽 | 每轮多花一些输出 token；需持久化到 `.agent/state.json` 才能崩溃恢复（未实现） |
| 管道式 `HookBus` | 简单、可组合，hook 能改写 payload 实现否决 | 进程内函数，无法像真实 harness 那样运行外部脚本、设超时、隔离故障 |
| 子串黑名单拦截 | 一行代码演示 `PreToolUse` 的用法 | 漏报和误报都很多；生产中用白名单 + 参数解析 + 容器沙箱 |
| `realpath` + `startswith` | 简短 | 兄弟目录前缀可绕过；用 `commonpath` 或加分隔符 |
| `run_shell` 真实执行、`cwd` 当沙箱 | 让 demo 有真实输出 | `cwd` 不是隔离；生产中所有命令在 E2B / Daytona 容器内执行 |
| 按字符截断 4096 | 实现简单 | 与讲义"4k tokens"不符；生产中按 token 计数截断，并保留头尾或摘要 |
| 每轮开头检查预算 | 逻辑直观 | 可能超支一轮；记账后再检查或预估后再调用 |
| trace 是内存列表 | 便于打印 | 没有 span 层级、耗时、`gen_ai.*` 属性；生产中用 OTel SDK 导出到 Langfuse |
| 只有 2 个工具 | 骨架足够演示分派 | 讲义要求 6 个工具经 MCP StreamableHTTP 暴露 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 第 13 行 | 注解延迟求值；配合 `str \| None`、`list[TodoItem]` 等新写法 |
| `@dataclass` | `class TodoItem`、`class PlanState`、`class Budget` | 自动生成 `__init__`、`__repr__`、`__eq__`；字段按顺序成为构造参数 |
| 带默认值的字段 | `note: str = ""`、`max_turns: int = 50` | 有默认值的字段必须排在无默认值字段之后 |
| `field(default_factory=list)` | `items: list[TodoItem] = field(default_factory=list)` | 可变默认值必须用工厂函数，每个实例得到新列表 |
| `asdict` | `asdict(budget)` | 把 dataclass（含嵌套）转换为字典 |
| 联合类型注解 | `def exceeded(self) -> str \| None:` | 返回字符串或 `None`（PEP 604 写法） |
| 数字分隔符 | `200_000` | 下划线只为可读，值为 200000 |
| 类型别名 | `HookFn = Callable[[dict[str, Any]], dict[str, Any]]` | 给复杂类型起名字，`Callable[[参数类型], 返回类型]` |
| 类属性 | `EVENTS = (...)` 写在类体中 | 所有实例共享；通过 `self.EVENTS` 访问 |
| 字典推导式 | `{e: [] for e in self.EVENTS}` | 每个事件一个新空列表 |
| `x or y` 默认值 | `payload = fn(payload) or payload` | `x` 为假值（`None`、`{}`、`0`、`""`）时取 `y` |
| 查表代替分支 | `{"pending": " ", ...}[it.status]` | 临时字典 + 下标访问 |
| `"\n".join(lines)` | `summary()` 末尾 | 用换行符连接字符串列表 |
| `with open(...) as fh` | `tool_read_file` | 上下文管理器，离开代码块自动关闭文件 |
| 切片截断 | `fh.read()[:TRUNCATE_BYTES]` | 取前 N 个字符；不足 N 时返回全部 |
| `subprocess.run` | `subprocess.run(cmd, cwd=..., shell=True, capture_output=True, text=True, timeout=...)` | 运行外部命令；`returncode`、`stdout`、`stderr` 属性 |
| `Callable[..., str]` | `TOOLS: dict[str, Callable[..., str]]` | `...` 表示参数任意 |
| 推导式中的元组解包 | `for i, (desc, status) in enumerate(s["plan"])` | `enumerate` 给出 `(序号, 元素)`，元素本身再解包 |
| 链式 `dict.get` | `payload.get("args", {}).get("cmd", "")` | 键不存在时返回默认值，避免 `KeyError` |
| lambda 中的元组技巧 | `lambda p: (trace.append({...}), p)[1]` | 在单个表达式里先执行副作用再返回值 |
| 字典解包合并 | `{"event": "tool", **p}` | 把 `p` 的键值并入新字典 |
| `while True` + `break` / `continue` | 主循环 | `break` 退出循环，`continue` 跳到下一轮 |
| 元组解包 | `name, args = call` | 工具调用是 `(名字, 参数字典)` 二元组 |
| `**kwargs` 调用 | `TOOLS[name](sandbox, **args)` | 把字典展开为关键字参数 |
| `try / except Exception as exc` | 工具执行 | 捕获所有普通异常，`str(exc)` 取错误信息 |
| `json.dumps(..., default=str)` | `main()` | 无法序列化的对象用 `str()` 转换 |
| f-string 格式符 | `f"dollars=${...:.3f}"` | 保留 3 位小数 |
| 入口守卫 | `if __name__ == "__main__": main()` | 被 import 时不运行（测验实验就是 import 后调用各函数） |

另外：文件 `import sys` 但从未使用，属于残留导入。

---

## 6. 运行结果解读

实际运行（`cd code && timeout 180 python3 main.py`，退出码 0）：

```text
GOAL: demonstrate the plan-act-observe loop without network calls
  [x] 1. locate target file
  [x] 2. read and diagnose
  [x] 3. apply fix and verify
---
turns=3 tokens=2700 dollars=$0.050
---
trace events: 4
  {"event": "start", "task": "demonstrate the plan-act-observe loop without network calls", "sandbox": ".../01-terminal-native-coding-agent/code", "started_at": 1791833397.4660702}
  {"event": "tool", "tool": "run_shell", "ok": true, "bytes": 18}
  {"event": "tool", "tool": "read_file", "ok": false, "error": "[Errno 2] No such file or directory: '.../01-terminal-native-coding-agent/code/README.md'"}
  {"event": "end", "turns": 3, "tokens": 2700, "dollars": 0.05}
```

逐项解读：

- **计划**：三项全部 `[x]`。这是脚本第 3 步写死的，不代表任务真的完成。
- **预算**：3 轮；tokens = 1200 + 900 + 600 = 2700；dollars = 0.02 + 0.02 + 0.01 = 0.05。远低于 50 轮 / 200k / $5 的上限。
- **trace 只有 4 条**：`start`、两次 `tool`、`end`。`Stop` 事件其实触发了（`reason: "complete"`），但没有监听器，所以没进 trace。TypeScript 版注册了 `Stop` 监听，有 5 条。
- **`run_shell ls`**：`ok: true, bytes: 18`，即 `"exit=0\n"`（7 个字符）+ `"main.py\nts\n"`（11 个字符）。真实执行了 `ls`。
- **`read_file README.md` 失败**：沙箱是 `code/`，而 README 在 `code/ts/`。错误被 `except` 捕获并记录，循环没有崩溃。
- **最重要的观察**：工具失败了，模型（脚本）却在下一轮把"read and diagnose"标为 `done`，最终报告全部完成。在真实系统里这就是"幻觉式完成"——harness 必须用验证步骤（测试通过、文件确实被修改）来把关，而不是相信模型的计划状态。
- 补充实验（详见测验 Q7–Q12）：
  - `max_dollars=0.03` 时停在第 2 轮结束后，`dollars_used = 0.04`，第 2 轮的工具照常执行（超支一轮）；
  - `max_turns=2` 时计划停在 `[>] 2. read and diagnose`，返回值中没有停止原因；
  - 在沙箱目录放入 README.md 后，`read_file` 成功（`ok: true`）；
  - 兄弟目录前缀 `../sb-evil/secret.txt` 可以绕过路径检查；
  - 拦截规则对 `rm -fr`、`rm -r -f`、多空格、大写都失效，对 `grep shutdown_handler` 误报。

---

## 7. 动手改一改

1. **补上 Stop 监听与停止原因**：注册 `hooks.on("Stop", ...)` 写入 trace，并在返回值中增加 `stop_reason`；确认 trace 事件数从 4 变成 5，`max_turns=2` 时返回 `turn_limit`。
2. **修复路径检查**：改用 `os.path.commonpath`，并为"兄弟目录前缀""符号链接指向沙箱外""绝对路径"各写一个测试；顺便把 `fh.read()[:N]` 改为 `fh.read(N)`。
3. **让 Observe 真正回灌**：给 `model_step` 增加 `observations` 参数（上一轮工具结果或错误），并写一个"会读观察"的脚本模型：工具失败时把对应计划项标为 `failed` 并重试一次，重试仍失败则结束并报告。验证默认运行中计划第 2 项显示为 `[!]` 而不是 `[x]`。
4. **预算与压缩**：在 `budget.step()` 之后再检查一次预算；增加 `context_tokens` 计数（区别于累计 tokens），超过 150k 时 `fire("PreCompact", ...)`，用一个简单函数把旧观察替换为摘要，计划保持不变（对应讲义练习 4 的思路）。
5. **更好的命令守卫**：用 `shlex.split` 解析命令、用白名单限制可执行程序，并拒绝含 `;`、`&&`、`|` 的复合命令；或者改为 `subprocess.run(argv_list, shell=False)`。用测验 Q10 的命令表做回归测试。
6. **进阶（讲义 Build It 3、5、6）**：补齐 `edit_file`（带 diff 预览）、`ripgrep`、`git` 工具；实现计划持久化到 `.agent/state.json` 并支持 `--resume`；把 trace 改为 OpenTelemetry span（`gen_ai.*` 属性），在 3 个固定任务上统计 pass@1、轮数与成本，写入 `eval/results.jsonl`。

---

## 8. 常见坑

- **把 `cwd` 当沙箱**：`subprocess.run(cwd=sandbox)` 只改变工作目录，命令可以访问任何路径。真正的隔离要靠容器（讲义：E2B / Daytona，宿主文件系统不可达）。在本机运行修改后的 `main.py` 时尤其要小心，`run_shell` 是真实执行的。
- **用字符串前缀判断目录包含**：`/work/sb-evil` 以 `/work/sb` 开头。用 `commonpath`、`is_relative_to` 或"前缀 + 分隔符"。
- **相信模型的计划状态**：计划显示全部完成不等于任务完成。默认运行中工具失败了，计划仍全部是 `[x]`。完成必须由验证（测试、diff）确认。
- **只在循环开头检查预算**：会多执行一轮。记账后再检查，或在调用前预估。
- **混淆"上下文大小"与"累计 token"**：前者决定何时压缩，后者决定花了多少钱；代码只有后者。
- **截断单位不一致**：代码按字符截断，讲义按 token；中文文本 4096 个字符约 12KB。
- **hook 返回空字典被忽略**：`fn(payload) or payload` 会把 `{}` 当作"没有返回"。
- **注册了事件却没监听**：`Stop` 被触发但没有监听器，看起来"什么也没发生"。为每个关心的事件写测试。
- **黑名单拦截给人虚假的安全感**：变体和复合命令很容易绕过，而误报会干扰正常开发命令。
- **讲义与代码的语言/运行时不一致**：讲义写 "TypeScript / Bun (harness), Python (eval scripts)"，但 Python 的 `main.py` 本身就是 harness，TypeScript 版用的是 Node.js + tsx 而不是 Bun，也没有 Ink TUI、MCP、E2B、OTel。把这两份代码当作"循环骨架"而不是讲义所描述系统的实现。
- **基准名混用**：讲义开头引用 Live-SWE-agent 在 SWE-bench **Verified** 上的 79.2%，而本项目的评估目标是 SWE-bench **Pro** 子集、基线是 mini-swe-agent，两者不能直接比较。
