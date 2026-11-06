# 测验 · 综合项目 01：终端原生 Coding Agent（Capstone 01 — Terminal-Native Coding Agent）

> **阶段 19 · 综合项目 · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（另有 TypeScript 版 [code/ts/README.md](../code/ts/README.md)） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Harness 才是难点 | 讲义："the hard part is not the model call but the tool loop, the sandbox, and the cost ceiling on a 50-turn run"；多数失败不是模型错误，而是工具循环不稳定、上下文污染、token 成本失控、破坏性文件操作 |
| 2 | 四个面：Plan / Act / Observe / Recover | Plan 维护 TodoWrite 式计划；Act 分派工具调用；Observe 捕获 stdout/stderr/退出码、截断后回灌；Recover 处理工具错误且不撑爆上下文、不死循环 |
| 3 | TodoWrite 计划状态 | 带类型的 pending / in_progress / done 条目；模型每轮**整体重写**（不增量修改）；持久化到 `.agent/state.json` 以便崩溃后恢复 |
| 4 | 八种 hook 事件 | `PreToolUse`、`PostToolUse`、`SessionStart`、`SessionEnd`、`UserPromptSubmit`、`Notification`、`Stop`、`PreCompact`：运维方注入策略、遥测与 guardrail 的扩展点 |
| 5 | 沙箱与 worktree | 每个任务在 E2B / Daytona 新容器中运行，`git worktree add -b agent/$TASK_ID` 挂载独立分支；harness 从不触碰宿主文件系统；成功或失败都销毁 worktree |
| 6 | 三层成本控制 | 每轮 token 上限、每会话美元预算、硬性轮数上限；默认 50 轮、200k 上下文、每任务 $5；`PreCompact` 在 150k 时把旧轮次压缩为"先前状态"块 |
| 7 | 工具输出截断 | 每次工具调用输出上限约 4k tokens，防止一次 ripgrep 返回 8MB 结果导致上下文污染和成本失控 |
| 8 | 可观测性 | OpenTelemetry span + GenAI 语义约定（`gen_ai.*`），发到自托管 Langfuse；评分要求 100% 工具调用都有 span、逐轮 token 记账 |
| 9 | 评估方法 | 30 个 SWE-bench Pro Python 任务，与 mini-swe-agent 在**同一批任务**上比较 pass@1、每任务轮数与美元成本；pass@1 = 首次运行即解决、不重试不偷看测试集 |
| 10 | 本节代码的定位 | `main.py` 用标准库实现了 plan/act/observe 循环骨架：脚本化假模型、2 个工具、8 事件 hook 总线、预算；没有真实模型、沙箱、MCP、OTel、PreCompact |

### 核心技能（能动手做到）

- [ ] 画出 harness 的主循环：预算检查 → 模型给出计划与工具调用 → PreToolUse → 执行 → PostToolUse → 下一轮，并标出每个 hook 的触发点
- [ ] 读懂 `main.py` 的 `PlanState`、`Budget`、`HookBus`、`run_agent`，说清每轮的 token/美元记账与停止条件
- [ ] 找出 `tool_read_file` 的路径前缀判断漏洞，并用 `os.path.commonpath` 修复
- [ ] 说明为什么"字符串黑名单式"的破坏性命令拦截必然不完整，沙箱才是根本防线
- [ ] 补上 Recover：工具失败时把错误作为观察回灌给模型，计划不能在失败后被标记为 done
- [ ] 为 harness 写 hook：`Stop` 轨迹记录、`PostToolUse` 逐轮 token 记账、`PreCompact` 压缩触发
- [ ] 设计一个公平的 SWE-bench Pro 对比实验（相同任务、相同预算、pass@1）

---

## 二、基础自测（选择题）

**Q1.** 讲义把 harness 拆成四个"面"（surface），另加 2026 年的 hooks。这四个面是：

- A. Fetch、Embed、Rank、Synthesize
- B. Plan、Act、Observe、Recover
- C. Train、Evaluate、Deploy、Monitor
- D. Encode、Decode、Sample、Stream

**Q2.** 下列哪一项**不是**讲义列出的八种 hook 事件之一？

- A. `PreCompact`
- B. `UserPromptSubmit`
- C. `PreModelCall`
- D. `Notification`

**Q3.** 要在破坏性 shell 命令（如删除工作区外的文件）**执行之前**拦截它，最合适的 hook 是：

- A. `PreToolUse`
- B. `PostToolUse`
- C. `Stop`
- D. `SessionStart`

**Q4.** 在 `code/` 目录下运行 `python3 main.py`，关于输出的说法正确的是：

- A. 打印 5 个 trace 事件，其中包含一个 `stop` 事件
- B. `read_file` 成功读取了课程根目录的 README.md，返回 4096 字节
- C. 由于 `rm -rf` 被拦截，计划中第 3 项显示为 `[!]`
- D. 打印 4 个 trace 事件；`read_file` 因 `code/README.md` 不存在而失败（`ok: false`），但计划三项仍全部显示 `[x]`

**Q5.** 讲义的成本控制设定是：

- A. 50 轮、200k 上下文、每任务 $5；在 150k 时由 `PreCompact` 把旧轮次压缩成先前状态块
- B. 100 轮、1M 上下文、每任务 $50；超出后自动切换到更便宜的模型
- C. 不设轮数上限，只按美元预算停止
- D. 50 轮、200k 上下文；超出后执行 `git reset --hard` 并重试

**Q6.** 关于计划状态（TodoWrite），讲义的要求是：

- A. 模型每轮只能追加一条新条目，不能修改已有条目
- B. 计划只保存在内存中，崩溃后从头开始
- C. 模型每轮以工具调用的形式**整体重写**计划状态，并持久化到 `.agent/state.json` 以便崩溃后恢复
- D. 计划由 harness 自动生成，模型不参与

**Q7.** `main.py` 中的沙箱路径检查如下：

```python
full = os.path.join(sandbox, path)
if not os.path.realpath(full).startswith(os.path.realpath(sandbox)):
    raise RuntimeError("path escapes sandbox")
```

若 `sandbox = "/work/sb"`，且存在同级目录 `/work/sb-evil/`，下列哪个 `path` 能**绕过**检查读到沙箱外的文件？

- A. `"../../../etc/passwd"`
- B. `"/etc/passwd"`
- C. `"notes/../a.txt"`
- D. `"../sb-evil/secret.txt"`

**Q8.** 关于本节的评估方法，下列说法正确的是：

- A. 可以在每次失败后 `git reset --hard` 重试，取最好的一次作为 pass@1
- B. pass@1 指首次运行即解决任务、不重试也不偷看测试集；且必须与 mini-swe-agent 在相同的 30 个任务上对比
- C. 只需报告自己 harness 的通过率，不需要基线
- D. 讲义要求在 SWE-bench Verified 上与 Live-SWE-agent 的 79.2% 直接比较

---

## 三、动手 / 代码题

**Q9.** 修复 Q7 中的路径检查漏洞。要求：

1. 解释为什么 `startswith` 判断会被 `../sb-evil/secret.txt` 绕过，而 `../../../etc/passwd` 和 `/etc/passwd` 不会；
2. 用 `os.path.commonpath` 写出修复版本；
3. 对比 TypeScript 版 `tools.ts` 的写法，说明它为什么没有这个漏洞。

**Q10.** `destructive_guard` 的实现是：

```python
def destructive_guard(payload):
    cmd = payload.get("args", {}).get("cmd", "")
    if "rm -rf" in cmd or "shutdown" in cmd:
        payload["blocked"] = True
        payload["reason"] = "destructive command blocked by PreToolUse hook"
    return payload
```

预测下列命令是否被拦截，并据此说明"黑名单"方法的局限，以及讲义的架构用什么来兜底：

```text
rm -rf /           rm -fr /           rm -r -f /         rm  -rf /（两个空格）
RM -RF /           grep shutdown_handler src
```

**Q11.** 阅读 `run_agent` 的主循环（节选）：

```python
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
        ...
        try:
            result = TOOLS[name](sandbox, **args)
            hooks.fire("PostToolUse", {"tool": name, "ok": True, "bytes": len(result)})
        except Exception as exc:
            hooks.fire("PostToolUse", {"tool": name, "ok": False, "error": str(exc)})
        turn += 1
```

1. 把预算改为 `Budget(max_dollars=0.03)` 运行，最终 `dollars_used` 是多少？超支的那一轮的工具调用有没有执行？
2. 工具的返回值 `result` 去了哪里？模型能"看到"它吗？这对 Observe 和 Recover 意味着什么？
3. 默认运行中 `read_file` 失败了，但计划三项全是 `[x]`。从 harness 的角度，应该如何防止"失败后仍报告完成"？
4. `run_agent` 的返回值能否告诉调用者"这次是正常完成还是因预算停止"？

**Q12.** 关于 `HookBus`：

```python
    def fire(self, event, payload):
        for fn in self._hooks[event]:
            payload = fn(payload) or payload
        return payload
```

1. 如果某个 hook 返回空字典 `{}`，`fire` 返回什么？为什么？
2. `hooks.on("PreTooluse", fn)`（大小写拼错）会发生什么？
3. 默认运行里 `Stop` 事件被触发了，为什么 trace 中没有 `stop` 记录？加一行注册代码使 trace 中出现它，trace 事件数会变成多少？

---

## 四、面试高频题

**Q13.**（基础必考）一个 coding agent 的 harness 由哪些部分组成？为什么说"难点不在模型调用"？

**Q14.**（原理深挖）长时间运行（50 轮）的 coding agent 为什么容易出现上下文污染与成本失控？讲义给出了哪些机制来控制？`PreCompact` 压缩可能丢失什么？

**Q15.**（工程实践）如何保证 coding agent 不会破坏宿主环境？请从沙箱、worktree、hook、权限、网络几个层次回答，并说明 `PreToolUse` 黑名单为什么不够。

**Q16.**（场景设计）你要证明自己的 harness 比 mini-swe-agent 更好。请设计评估方案：数据、指标、对照条件、需要报告的内容，以及哪些做法会让结论无效。

**Q17.**（追问型）讲义练习 2 说：加一个 reviewer 子 agent 审查 diff，"通常会让 SWE-bench 通过率降到单 agent 基线以下"。为什么？什么情况下 reviewer 才值得加？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："The harness has four surfaces. **Plan** ... **Act** ... **Observe** ... **Recover** ..."，并补充 "The 2026 shape adds one more thing: **hooks**"。A 是 RAG 流程；C 是 MLOps 生命周期；D 是生成式模型推理步骤。

### Q2 — 答案：C

讲义列出的八种是 `PreToolUse`、`PostToolUse`、`SessionStart`、`SessionEnd`、`UserPromptSubmit`、`Notification`、`Stop`、`PreCompact`。`main.py` 中 `HookBus.EVENTS` 正是这八个。`PreModelCall` 是编造的干扰项。

### Q3 — 答案：A

`PreToolUse` 在工具执行之前触发，可以返回 `blocked: True` 阻止执行（讲义 Build It 第 5 步："`PreToolUse` destructive-command guard that blocks `rm -rf` outside the worktree"）。`PostToolUse` 在执行之后，已经来不及；`Stop`、`SessionStart` 与单次工具调用无关。

### Q4 — 答案：D

实际运行输出（节选）：

```text
  [x] 1. locate target file
  [x] 2. read and diagnose
  [x] 3. apply fix and verify
---
turns=3 tokens=2700 dollars=$0.050
---
trace events: 4
  {"event": "start", ...}
  {"event": "tool", "tool": "run_shell", "ok": true, "bytes": 18}
  {"event": "tool", "tool": "read_file", "ok": false, "error": "[Errno 2] No such file or directory: '.../code/README.md'"}
  {"event": "end", "turns": 3, "tokens": 2700, "dollars": 0.05}
```

`sandbox` 被设为 `main.py` 所在的 `code/` 目录，而 README 位于 `code/ts/README.md`，所以读取失败。A 错：`Stop` 被触发了，但没有注册任何监听器，所以 trace 里没有 stop 记录（TypeScript 版注册了，所以它有 5 个事件）；B 错；C 错：脚本里根本没有 `rm -rf`。最值得注意的是：**工具失败了，计划却全部标为完成**——这是脚本化模型的产物，也暴露了 Recover 缺失（见 Q11）。

### Q5 — 答案：A

讲义 Build It 第 7 步："Hard cutoffs: 50 turns, 200k context, $5 per task. `PreCompact` hook summarizes older turns into a prior-state block at the 150k mark"。`main.py` 的 `Budget` 默认值也是 `max_turns=50`、`max_tokens=200_000`、`max_dollars=5.00`。D 中的 `git reset --hard` 重试恰恰是技能文件的硬性拒绝项。

### Q6 — 答案：C

讲义："Model rewrites the full state each turn as a tool call — do not let it mutate incrementally. Persist plan to `.agent/state.json` so crashes can resume." 整体重写的好处是计划始终自洽、易于校验和持久化；增量修改容易累积不一致。`main.py` 用 `plan.items = step["plan"]` 实现了"整体替换"，但**没有**持久化到文件。

### Q7 — 答案：D

`"../sb-evil/secret.txt"` 解析后是 `/work/sb-evil/secret.txt`，字符串上以 `/work/sb` 开头，`startswith` 返回 True，检查被绕过。我们在临时目录中实测：`tool_read_file(sb, "../sb-evil/secret.txt")` 成功返回了 `TOP SECRET`。A 解析为 `/etc/passwd`，C 解析为沙箱内文件；B 是绝对路径，`os.path.join` 会丢弃 `sandbox` 部分，解析为 `/etc/passwd`，A、B 都会被正确拦截（实测抛出 `path escapes sandbox`）。

### Q8 — 答案：B

讲义 Key Terms："pass@1 ... Fraction of SWE-bench tasks solved on the first run without retry or test-set peeking"；技能文件硬性拒绝："Eval numbers reported without a matched baseline run on the same 30 issues" 与 "'Pass rate' claims that depend on `git reset --hard` between retries"。D 混淆了数据集：79.2% 是 Live-SWE-agent 在 SWE-bench **Verified** 上的成绩，本项目的评估目标是 SWE-bench **Pro** 子集、基线是 mini-swe-agent。

### Q9 — 参考答案

1. `startswith` 是**字符串前缀**判断，不是**路径层级**判断。`/work/sb-evil/...` 与 `/work/sb` 共享前缀 `/work/sb`，但它们是兄弟目录。`../../../etc/passwd` 和 `/etc/passwd` 解析后是 `/etc/passwd`，与 `/work/sb` 没有公共前缀，所以会被拦住。
2. 修复（已在临时目录验证：兄弟目录被拦截，沙箱内文件正常读取）：

```python
def tool_read_file(sandbox: str, path: str) -> str:
    root = os.path.realpath(sandbox)
    full = os.path.realpath(os.path.join(sandbox, path))
    if os.path.commonpath([full, root]) != root:
        raise RuntimeError("path escapes sandbox")
    with open(full, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()[:TRUNCATE_BYTES]
```

   也可以用 `full == root or full.startswith(root + os.sep)`，或 Python 3.9+ 的 `pathlib.Path(full).is_relative_to(root)`。`realpath` 会解析符号链接，防止"沙箱内的符号链接指向沙箱外"。
3. TypeScript 版 `tools.ts`：

```ts
if (full !== root && !full.startsWith(root + path.sep)) {
  throw new Error("path escapes sandbox");
}
```

   在前缀后加上路径分隔符 `path.sep`，`/work/sb-evil` 不以 `/work/sb/` 开头，因此被拦截。它还在 `realpathSync` 失败（文件不存在）时统一抛出 "path escapes sandbox"。

注意：这只是应用层的纵深防御。讲义的设计是"All tool calls execute inside the sandbox. Host filesystem is unreachable"——即使这里有漏洞，容器边界也能兜底。

### Q10 — 参考答案

实测结果：

| 命令 | 是否拦截 | 说明 |
|------|---------|------|
| `rm -rf /` | 是 | 精确子串匹配 |
| `rm -fr /` | **否** | 选项顺序不同 |
| `rm -r -f /` | **否** | 选项拆开 |
| `rm  -rf /` | **否** | 多一个空格 |
| `RM -RF /` | **否** | 大小写（在大小写敏感的系统上 `RM` 本身通常不是有效命令，但说明匹配逻辑脆弱） |
| `grep shutdown_handler src` | **是（误报）** | 子串 "shutdown" 命中 |

局限：shell 语言的表达方式无穷多（选项重排、变量展开、别名、`find -delete`、用脚本语言删除文件、`;` / `&&` 拼接多条命令），黑名单永远列不全，同时又会误报正常命令。改进思路：

- 用 `shlex.split` 解析参数并按语义判断（我们实测这样能拦住前五种变体、并消除 `grep shutdown_handler` 的误报），但对 `echo hi; rm -rf /` 这种用 `;` 拼接的复合命令仍然漏掉（实测返回 False），除非不用 `shell=True` 或先按操作符拆分；
- 更好的是**白名单**：只允许 `ls`、`cat`、`pytest`、`git status/diff` 等明确需要的命令；
- 根本兜底是讲义的架构：E2B / Daytona 沙箱 + 独立 worktree，"Host filesystem is unreachable"；网络默认关闭（练习 3 要求验证 `curl` 外部 URL 被拦截）。技能文件也拒绝"禁用破坏性命令拦截"，因为它是纵深防御的一层，而不是唯一一层。

TypeScript 版用正则 `/\brm\s+-rf\b/` 并先 `toLowerCase()`，能处理多空格和大小写，但 `rm -fr`、`rm -r -f` 仍然漏掉。

### Q11 — 参考答案

1. **预算超支**：实测 `Budget(max_dollars=0.03)` 时，第 1 轮花 0.02（未超），第 2 轮开始时检查仍未超（0.02 < 0.03），于是调用模型、记账到 0.04，并**执行了第 2 轮的工具调用**（`read_file`）；第 3 轮开始时才检查出 `dollar_limit` 停止。最终 `dollars_used = 0.04`，超出上限 33%。原因是预算检查只在每轮开头做，"记账"发生在检查之后。改进：记账后立即再检查一次（TypeScript 版就加了 `postStepLimit` 检查，在执行工具前停止），或在调用模型前根据预估成本预检。真实系统中模型调用本身就是主要开销，通常还需要按 `max_tokens` 预留额度。
2. **工具结果被丢弃**：`result` 只用于计算 `len(result)` 写入 trace，**从未传回模型**；`model_step(plan, turn)` 的输入只有计划和轮次。也就是说，demo 的 Observe 只做了"记录"，没有做"回灌"；Recover 也没有实现——工具报错只是记一条 `ok: False`，下一轮模型照样按脚本推进。真实 harness 应把截断后的输出（或错误信息）作为下一轮的观察放进消息历史。
3. **防止"失败后报告完成"**：
   - 把错误作为观察回灌给模型，让它决定重试或修改计划；
   - harness 层校验：同一条计划项关联的工具调用失败后，不允许直接标为 `done`，或要求后续有成功的验证步骤（例如测试通过）才能完成——这就是"verification gate"的思路；
   - TypeScript 版在返回值中计算 `passed = completed && allDone`，但它同样不检查工具是否成功；它在 TS 版的 demo 中之所以没有暴露问题，是因为 `sandbox` 指向 `ts/` 目录，README.md 恰好存在（实测 `read_file ok: true, bytes: 1286`）。
4. **不能**。Python 版返回 `{"plan", "budget", "trace"}`，停止原因只通过 `Stop` 事件传给 hook，而 `Stop` 没有监听器，所以调用者只能通过"计划是否全部完成"去猜。实测 `max_turns=2` 时计划停在 `[>] 2`，返回值里没有 `turn_limit` 字样。应该在返回值中加入 `stop_reason`。

### Q12 — 参考答案

1. 返回**原 payload**。`fn(payload) or payload`：空字典 `{}` 在布尔上下文中为假，`or` 会取右侧的原 payload。实测 `bus.on("PreToolUse", lambda p: {})` 后 `fire` 返回 `{'tool': 'x'}`。这个写法的本意是"hook 返回 None 时沿用原 payload"，但会把"hook 故意返回空字典"也当成 None。更明确的写法是 `result = fn(payload); payload = payload if result is None else result`。另外 `destructive_guard` 是**原地修改**传入的字典，返回值和原对象是同一个；而 TS 版返回 `{...payload, blocked: true}` 新对象，副作用更少。
2. `self._hooks[event]` 找不到键，抛出 `KeyError: 'PreTooluse'`（实测）。这是"快速失败"，比静默忽略好；更友好的做法是在 `on()` 中检查 `event in self.EVENTS` 并给出清晰报错。
3. `run_agent` 只为 `PreToolUse`、`PostToolUse`、`SessionStart`、`SessionEnd` 注册了监听器，`Stop` 被 `fire` 了但没人处理。在注册区加一行：

```python
hooks.on("Stop", lambda p: (trace.append({"event": "stop", **p}), p)[1])
```

   实测 trace 事件数从 4 变为 5，新增 `{"event": "stop", "reason": "complete", "turn": 2}`，与 TypeScript 版的输出一致。讲义 Build It 第 5 步要求的 "(d) `Stop` writes a final trace bundle" 正是挂在这里。

### Q13 — 参考回答要点

- **组成**：TUI / CLI 入口；计划状态（TodoWrite，整体重写、持久化）；工具分派器（read / edit / search / symbols / run / git，经 MCP 暴露）；观察处理（截断、摘要、错误回灌）；恢复逻辑；hook 总线（8 种事件）；预算与压缩；沙箱 + worktree；可观测性（OTel → Langfuse）；PR 提交。
- **难点不在模型调用**：模型调用是一个 HTTP 请求；真正的失败来自工具循环——讲义："Most failure modes are not model mistakes. They are tool-loop instability, context poisoning, runaway token cost, and destructive filesystem operations"，并举例"第 47 轮 ripgrep 返回 8MB 结果导致循环崩溃"。
- **加分点**：指出模型可替换（讲义通过 OpenRouter 做到 model-agnostic，练习 1 要求换成 Qwen3-Coder-30B），而 harness 质量决定同一模型能发挥多少；行业产品（Claude Code、Cursor、OpenCode 等）"从 50 英尺外看都一样"。

### Q14 — 参考回答要点

- **原因**：每轮的工具输出都会累积进上下文；一次大输出（日志、搜索结果、长文件）会挤掉计划和关键信息（上下文污染），并让后续每一轮都为这些 token 付费（成本随轮数近似平方增长，因为每轮都重新发送历史）。
- **机制**：
  - 每次工具输出截断到约 4k tokens；
  - 每轮 token 上限、每会话 $5、50 轮硬上限；
  - 150k 时 `PreCompact` 把旧轮次摘要成先前状态块，保留计划；
  - 计划状态独立于对话历史，压缩后仍完整。
- **压缩的损失**：具体的错误信息、文件行号、已尝试过的失败方案（导致重复尝试）、细微约束。讲义练习 4 要求测量用小模型（Haiku 4.5）做 3 倍压缩时损失多少计划保真度。
- 常见误区：只设美元上限——在单价低的模型上可能跑出几百轮死循环；轮数上限同样必要。

### Q15 — 参考回答要点

- **沙箱**：每任务一个新的 E2B / Daytona 容器，工具调用全部在容器内执行，宿主文件系统不可达。
- **worktree**：`git worktree add -b agent/$TASK_ID`，独立分支，成功或失败都销毁；只通过 PR 交付，技能文件拒绝直接推送 main。
- **hook**：`PreToolUse` 拦截破坏性命令、工作区外写入、未在白名单中的网络访问（技能文件："Any agent that can write outside the worktree or curl external URLs without an explicit allowlist hook" 是硬性拒绝项）；`PostToolUse` 审计记录。
- **权限**：GitHub App 使用细粒度 token，范围仅限目标仓库；敏感操作需要人工确认。
- **网络**：默认拒绝，按需加白名单。
- **为什么黑名单不够**：见 Q10——表达方式无穷、误报多；它是纵深防御中的一层，不能代替沙箱。
- 加分点：讲义练习 3 要求主动做沙箱逃逸测试并记录尝试；评分中 Safety 占 20 分。

### Q16 — 参考回答要点

- **数据**：固定的 30 个 SWE-bench Pro Python 任务（讲义），外加自己的 30 任务留出集（Stack 部分提到），以及 Terminal-Bench 2.0。任务列表事先固定，不能根据结果挑选。
- **对照条件**：mini-swe-agent 在**相同任务**、相同模型（或明确说明不同）、相同预算（50 轮、$5）下运行。
- **指标**：pass@1、每任务轮数、每任务美元与 token；把逐任务结果写入 `eval/results.jsonl`。
- **报告内容**：哪些任务你解决了而基线没解决、反之亦然（技能文件要求）；观察到的三大失败模式以及修复它们的 hook 改动；至少 5 次完整运行的 OTel trace 归档。
- **使结论无效的做法**：没有匹配基线；失败后 `git reset --hard` 重试再报告 pass@1；偷看测试集；对两边使用不同的预算或模型而不说明；只报告平均值不报告逐任务结果。
- 加分点：样本只有 30 个，pass@1 的差异要考虑统计不确定性（例如多次运行或报告置信区间）。

### Q17 — 参考回答要点

- **为什么常常变差**：reviewer 本身会出错。它的"误报"（把正确的 diff 判为有问题）会触发不必要的修改循环，可能把原本正确的修复改坏；每一次修订还会消耗轮数和预算，更容易撞到 50 轮 / $5 上限。讲义练习 2 的提示："Measure whether false-positive reviews drop SWE-bench pass rate below the single-agent baseline (hint: usually yes)"。
- **什么时候值得加**：reviewer 的判断有客观依据（运行测试、静态检查、类型检查）而不是纯粹的意见；reviewer 的精确率足够高；或者任务的错误代价很高（例如安全敏感改动），愿意用通过率换更低的错误合入率。
- **设计建议**：让 reviewer 只在验证失败时介入；限制修订轮数；把 reviewer 的结论作为"建议"而不是"必须修改"；用评估数据决定是否启用。
- 加分点：联系"实现者与评分者分离"的思想——分离本身有价值，但评分者必须比实现者更可靠，否则只是增加噪声。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：本项目主循环的原型。
- [阶段 14 · 02 ReWOO 与 Plan-and-Execute：解耦 Planning](../../../14-agent-engineering/02-rewoo-plan-and-execute/docs/zh.md)：计划状态与执行分离。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../../13-tools-and-protocols/09-mcp-transports/docs/zh.md)：讲义的工具传输层与练习 5。
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../../14-agent-engineering/19-benchmarks-swebench-gaia/docs/zh.md)：pass@1 与 SWE-bench 评估方法。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：三层预算的设计思想。
- [阶段 15 · 10 自主 Agents 的权限模式](../../../15-autonomous-systems/10-claude-code-permission-modes/docs/zh.md)：权限提示与破坏性操作控制。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../../14-agent-engineering/23-otel-genai-conventions/docs/zh.md)：`gen_ai.*` span 规范。

### 本节被哪些后续内容用到
- [阶段 19 · 20 Agent Harness 的循环契约](../../20-agent-harness-loop-contract/docs/zh.md)：把本节的主循环拆成可测试的契约。
- [阶段 19 · 21 带 Schema 校验的工具注册表](../../21-tool-registry-schema-validation/docs/zh.md)：对应 TS 版用 zod 校验工具参数。
- [阶段 19 · 25 Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：解决"工具失败仍报告完成"（Q11）。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：路径隔离与命令拦截的完整实现（Q9、Q10）。
- [阶段 19 · 27 使用固定测试任务的评估 Harness](../../27-eval-harness-fixture-tasks/docs/zh.md)、[阶段 19 · 28 通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability](../../28-observability-otel-traces/docs/zh.md)、[阶段 19 · 29 基于 Harness 的端到端 Coding Agent](../../29-end-to-end-coding-task-demo/docs/zh.md)：评估、可观测性与端到端演示。
- [阶段 18 · 30 两用风险：网络、生物、化学与核领域的能力提升](../../../18-ethics-safety-alignment/30-dual-use-risk-cyber-bio-chem-nuclear/docs/zh.md)：agentic coding 被滥用的真实案例，说明 harness 的权限与监控设计为何重要。

### 延伸关键词
`agent harness` · `plan-act-observe-recover` · `TodoWrite` · `hooks (PreToolUse / PostToolUse / PreCompact)` · `git worktree` · `E2B / Daytona sandbox` · `MCP Streamable HTTP` · `context compaction` · `cost governor` · `OpenTelemetry gen_ai.*` · `Langfuse` · `SWE-bench Pro` · `pass@1` · `mini-swe-agent` · `path traversal` · `allowlist vs denylist`
