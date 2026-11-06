# 测验 · 将 Harness 封装为库：Subagents 与会话存储（The Harness as a Library — Subagents and Session Store）

> **阶段 14 · Agent 工程 · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Client SDK vs Agent SDK | `anthropic` 是原始 Messages API，循环、工具、状态都归你；`claude-agent-sdk` 是 Claude Code 的 harness 做成的库，内置工具执行、MCP、hooks、subagent、session store |
| 2 | 内置工具 | 讲义：SDK 自带 10+ 工具（文件读写、shell、grep、glob、web fetch 等），自定义工具走标准 tool schema 注册 |
| 3 | Subagent 的两个用途 | **并行**（20 个模块各找测试文件 = 20 个并行任务）与**上下文隔离**（子 agent 用自己的 context window，只把结果交回 orchestrator） |
| 4 | Session store 五个方法 | `append`、`load`、`list_sessions`、`delete`（级联删除 subagent 会话）、`list_subkeys`；与 TypeScript 版协议一致 |
| 5 | `--session-mirror` | CLI 标志，把转录（transcript）边流式生成边镜像到外部文件，用于调试 |
| 6 | Hooks | `PreToolUse` / `PostToolUse`（拦截或审计工具调用）、`SessionStart` / `SessionEnd`、`UserPromptSubmit`、`PreCompact`、`Stop`、`Notification` |
| 7 | W3C trace context | 调用方活跃的 OTel span 通过 W3C trace context 传进 CLI 子进程，多进程运行在后端显示为同一条 trace |
| 8 | Claude Managed Agents | 托管替代方案（beta header `managed-agents-2026-04-01`），面向长时间异步任务，内置 prompt caching 与 compaction，用控制权换托管基础设施 |
| 9 | 三种失败模式 | subagent over-spawn（100 个小任务开 100 个子 agent，开销占主导，应批处理）、hook creep（hooks 越加越多拖慢启动）、session bloat（会话堆积，需过期策略） |
| 10 | 本节代码的简化 | 工具调用是预先写死的脚本、"token" 按空格分词计数、subagent 实际**顺序**执行且结果不回传、级联删除只删一层 |

### 核心技能（能动手做到）

- [ ] 说清 Client SDK 与 Agent SDK 的分工，并能判断某个产品该用哪一个（或 Managed Agents）
- [ ] 读懂 `Harness.run_agent` 与 `_dispatch`：hook 在哪里触发、工具异常如何转成字符串、每一轮如何写入 session
- [ ] 根据代码手算 orchestrator 与 subagent 的 `context_tokens`，并解释为什么 orchestrator 的数字"保持不变"
- [ ] 把 `SessionStore.delete` 改成递归级联删除，修复孙级会话残留
- [ ] 用线程池把 `spawn_subagents` 改成真正并行，并让 orchestrator 汇总子 agent 的摘要
- [ ] 写一个按会话限流的 `PreToolUse` hook，并指出现有 hook 签名缺少什么信息
- [ ] 估算"每任务一个 subagent / 批处理 / 不用 subagent"三种方案的 orchestrator 上下文与总 token 开销

---

## 二、基础自测（选择题）

**Q1.** 关于 Anthropic Client SDK（`anthropic`）与 Claude Agent SDK（`claude-agent-sdk`），正确的是：

- A. 二者功能相同，只是包名不同
- B. Client SDK 自带 shell、grep 等内置工具，Agent SDK 只提供 Messages API
- C. Client SDK 是原始 Messages API，循环与状态由你维护；Agent SDK 是把 Claude Code 的 harness 做成库，内置工具执行、MCP、hooks、subagent、session store
- D. Agent SDK 只能托管运行，不能在自己的进程里使用

**Q2.** 讲义记录的 subagent 两个用途是：

- A. 并行化（parallelization）与上下文隔离（context isolation）
- B. 认证与授权
- C. 缓存与限流
- D. 日志与指标

**Q3.** 下列哪一个**不是**讲义列出的 session store 接口？

- A. `append(session_id, message)`
- B. `list_subkeys(session_id)`
- C. `delete(session_id)`
- D. `summarize(session_id)`

**Q4.** 运行 `code/main.py`，orchestrator 的 `context_tokens` 打印为 11。它是怎么算出来的？

- A. 用 tokenizer 对三条消息编码后的 token 总数
- B. 按空格切分计词：prompt `"review these three modules"` 4 + 工具结果 `"[/project: 7 files]"` 3 + 输出 `"processed 1 tools; session=session_main"` 4
- C. 按字符数除以 4 估算
- D. orchestrator 的 4 + 三个 subagent 各自汇报的结果

**Q5.** `main.py` 最后打印 `... 16 hook events total`。16 是怎么来的？

- A. 4 种 hook × 4 个 session，每个 hook 只触发一次，与工具调用无关
- B. 4 次 `run_agent`（1 个 orchestrator + 3 个 subagent），每次 1 个 `session_start` + 1 次工具调用的 `pre`/`post` + 1 个 `session_end` = 4 个事件
- C. 16 是 `hook_log[:10]` 的截断误差
- D. 每个 subagent 触发 4 个、orchestrator 触发 4 个，再加上 `delete` 触发的 4 个级联事件

**Q6.** 讲义中，在"模型看到用户输入之前"对其进行处理的 hook 是：

- A. `PreToolUse`
- B. `PreCompact`
- C. `SessionStart`
- D. `UserPromptSubmit`

**Q7.** 讲义说调用方的 OTel span 如何进入 CLI 子进程？

- A. 通过 W3C trace context 传播，整个多进程运行在后端显示为一条 trace
- B. 通过共享文件系统上的日志文件拼接
- C. 只能在 provider 的控制台里看到，无法跨进程
- D. 每个子进程各自生成独立的 trace，无法关联

**Q8.** 关于 Claude Managed Agents，讲义的描述是：

- A. 一个开源的本地 harness，比 Agent SDK 控制粒度更细
- B. 只用于语音场景的流式 API
- C. 托管替代方案（beta header `managed-agents-2026-04-01`），面向长时间异步工作，内置 prompt caching 与 compaction，用控制权换取托管基础设施
- D. Agent SDK 的一个 hook 类型

---

## 三、动手 / 代码题

**Q9.** 阅读 `SessionStore.delete`：

```python
    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        for sub in self._subkeys.get(session_id, []):
            self._sessions.pop(sub, None)
        self._subkeys.pop(session_id, None)
```

subagent 自己又派生了 subagent（`x` → `x.sub01` → `x.sub01.sub02`）。执行 `store.delete("x")` 后：

1. `store.list_sessions()` 和 `store._subkeys` 分别还剩什么？
2. 这违反了讲义与 `outputs` 的哪条要求？
3. 改写 `delete`，使其递归级联删除任意深度的子会话。

**Q10.** 讲义 "Build It" 说 demo 中"main agent spawns 3 subagents **in parallel** ... **aggregates results**"，最后一行打印 `subagent results return to orchestrator; orchestrator context is preserved.`

1. 对照 `spawn_subagents` 与 `main()`，代码真的做到了"并行"和"汇总结果"吗？`orchestrator context tokens remain: 11` 说明了什么？
2. 用 `concurrent.futures.ThreadPoolExecutor` 写一个真正并行的 `spawn_subagents_parallel`。注意 `self._sub_counter` 应该在哪里递增？为什么？
3. 如何让 orchestrator 真正"收到结果"而上下文仍然有界？

**Q11.** 讲义练习 2："实现一个 `PreToolUse` hook，对 `write_file` 按会话限流（每会话每分钟 5 次）。"

1. 现有 `Hooks.pre_tool_use` 的签名是 `Callable[[str, dict], None]`，`_dispatch` 调用 `hook(tool_name, args)`。要实现"按会话"限流，缺了什么信息？hook 又如何表达"拒绝"？
2. 现在若 hook 内部 `raise PermissionError`，会发生什么？对 session 与 `session_end` hook 有什么影响？
3. 写出一个可测试的限流 hook（时钟可注入），并说明如何把拒绝变成结构化的工具结果。

**Q12.**（计算题，对应讲义练习 1）orchestrator 要审查 20 个模块。假设：orchestrator 自身提示 50 token；每个模块的 `read_file` 结果 2,000 token；子 agent 交回 orchestrator 的摘要每个任务 100 token，一个"5 模块批次"的合并摘要 300 token；每启动一个 subagent 的固定开销（系统提示 + 工具定义）3,000 token。比较三种方案的 orchestrator 上下文大小与总 token 消耗：

- (a) 不用 subagent，orchestrator 自己读 20 个文件；
- (b) 每个模块一个 subagent（20 个）；
- (c) 每 5 个模块一个 subagent（4 个）。

---

## 四、面试高频题

**Q13.**（基础必考）Anthropic 的 Client SDK 和 Claude Agent SDK 有什么区别？什么情况下你会直接用 Client SDK？

**Q14.**（原理深挖）subagent 的"上下文隔离"具体隔离了什么？它节省了什么、又付出了什么代价？什么时候不该用 subagent？

**Q15.**（工程实践）如何用 `PreToolUse` / `PostToolUse` 等 hooks 搭建一套工具调用的权限与审计系统？如何避免 hook creep？

**Q16.**（场景设计）为一个多租户的 coding agent 产品设计 session store：存储后端、subagent 会话的组织方式、删除与过期策略、隐私（含 `--session-mirror`）各怎么做？

**Q17.**（追问型）什么时候从自托管的 Agent SDK 切到 Claude Managed Agents？如果 agent 跨了多个进程（你的服务 → CLI 子进程 → MCP server），trace 怎么串起来？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Client SDK (`anthropic`). Raw Messages API. You own the loop, the tools, the state." 与 "Agent SDK (`claude-agent-sdk`). Built-in tool execution, MCP connections, hooks, subagent spawning, session store. The Claude Code loop as a library."
A 忽略了 harness 层；B 把两者说反了；D 错，Agent SDK 是可以 import 的库，托管的是 Managed Agents。

### Q2 — 答案：A

讲义："Two purposes documented by Anthropic: 1. Parallelization ... 2. Context isolation." B、C、D 都是通用基础设施功能，与 subagent 无关。

### Q3 — 答案：D

讲义列出的 session store 接口是 `append`、`load`、`list_sessions`、`delete`、`list_subkeys`。`summarize` 不是 session store 的接口——压缩上下文属于 compaction（对应 `PreCompact` hook 的时机），不是存储层的职责。

### Q4 — 答案：B

`run_agent` 中三处累加都是 `len(xxx.split())`，即按空白切词：

| 内容 | `split()` 结果 | 计数 |
|------|---------------|------|
| `"review these three modules"` | 4 个词 | 4 |
| `"[/project: 7 files]"` | `["[/project:", "7", "files]"]` | 3 |
| `"processed 1 tools; session=session_main"` | 4 个片段 | 4 |

合计 11（已实际运行验证）。同理 subagent：`"review module a"` 3 + `"[content of a.py: 42 lines]"` 5 + 输出 4 = 12。这只是"词数"，真实 token 数通常更多（标点、路径会被切成多个 token）。D 错在 orchestrator 从未收到 subagent 的结果（见 Q10）。

### Q5 — 答案：B

每次 `run_agent`：开始触发 `session_start`，每个工具调用在 `_dispatch` 中触发一次 `pre` 和一次 `post`，结束触发 `session_end`。orchestrator 与三个 subagent 各有 1 次工具调用，所以 `4 × (1 + 2 + 1) = 16`。`main()` 只打印前 10 条（`hook_log[:10]`），所以输出停在 `pre[read_file]: {'path': 'b.py'}`。A 忽略了 pre/post 按工具调用计；D 错，`delete` 不触发任何 hook。

### Q6 — 答案：D

讲义："`UserPromptSubmit` — act on user input before the model sees it." `PreToolUse` 作用于工具调用之前；`PreCompact` 在上下文压缩之前；`SessionStart` 用于会话初始化。注意本节代码只实现了 `pre_tool_use`、`post_tool_use`、`session_start`、`session_end` 四种。

### Q7 — 答案：A

讲义："OTel spans active on the caller propagate into the CLI subprocess via W3C trace context headers. The whole multi-process trace shows up as one trace in your backend." 其他选项都与"跨进程合并为一条 trace"的结论相反。

### Q8 — 答案：C

讲义："The hosted alternative (beta header `managed-agents-2026-04-01`). Long-running async work, built-in prompt caching, built-in compaction. Trade control for managed infrastructure." A 把"托管"说成了"本地"；B、D 与讲义无关。

### Q9 — 参考答案

1. 已实际运行验证：

```text
before: ['x', 'x.sub01', 'x.sub01.sub02']  {'x': ['x.sub01'], 'x.sub01': ['x.sub01.sub02']}
after delete: ['x.sub01.sub02']  {'x.sub01': ['x.sub01.sub02']}
```

`delete` 只删除了 `x` 和它的**直接**子会话 `x.sub01`，孙会话 `x.sub01.sub02` 的数据、以及 `_subkeys["x.sub01"]` 这条索引都残留了下来，成了"孤儿"。

2. 讲义："`delete(session_id)` — with cascade to subagent sessions"；`outputs` 的硬规则："Session stores without a cascade-delete policy. Orphaned subagent sessions bloat storage." 残留数据既造成 session bloat，也可能违反"用户要求删除数据"的隐私义务。

3. 递归版本（已验证删除后 `[]`、`{}`）：

```python
    def delete(self, session_id: str) -> None:
        for sub in self._subkeys.pop(session_id, []):
            self.delete(sub)                      # 先递归删子树
        self._sessions.pop(session_id, None)
```

要点：用 `pop` 同时取出并删除索引；先删子树再删自己。真实存储（SQLite）可用外键 `ON DELETE CASCADE` 或递归 CTE 实现；嵌套极深时可改成显式栈的迭代版本，避免递归深度限制。

### Q10 — 参考答案

1. **都没有做到**：
   - `spawn_subagents` 是普通 `for` 循环，三个 subagent **依次**执行；
   - 每个 `AgentRun.output` 被收进 `sub_runs` 列表后只用于打印，从未 `append` 到 orchestrator 的 session，也没有加到 `orchestrator_run.context_tokens`；而且 orchestrator 的 `run_agent` 在 spawn 之前就已结束（已触发 `session_end`）。
   - 所以 `orchestrator context tokens remain: 11` 只是"同一个整数没被改过"，并不能证明"结果回传后上下文仍然有界"。真正能说明隔离效果的对比是：若 orchestrator 自己读三个文件，它的上下文是 23（已验证），而 subagent 方案下原始文件内容留在各自 12 个词的子上下文里。
2. 参考实现（已验证：每次工具调用 sleep 0.2 s 时，顺序版 0.60 s，并行版 0.20 s）：

```python
from concurrent.futures import ThreadPoolExecutor

    def spawn_subagents_parallel(self, parent, tasks, max_workers=5):
        jobs = []
        for prompt, calls in tasks:              # 在主线程里分配 ID
            self._sub_counter += 1
            jobs.append((f"{parent}.sub{self._sub_counter:02d}", prompt, calls))
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(self.run_agent, sid, p, c, parent) for sid, p, c in jobs]
            return [f.result() for f in futures]  # 保持提交顺序
```

`_sub_counter += 1` 不是原子操作，如果放进各线程里执行会出现竞态（两个子 agent 拿到同一个 ID）；在提交前于主线程统一分配最简单。`SessionStore` 若换成真实数据库，还需要连接池或锁。

3. 让每个 subagent 产出一个**简短摘要**，orchestrator 把摘要（而不是原始工具结果）追加到自己的 session，并据此生成最终回答：

```python
summaries = [r.output for r in sub_runs]
for s in summaries:
    store.append(parent, Turn("tool", f"subagent: {s}"))
    orchestrator_run.context_tokens += len(s.split())
```

orchestrator 上下文增长量 = 摘要总长度，而不是原始文件总长度——这才是讲义说的 "only results return to the orchestrator. The orchestrator's budget is preserved."

### Q11 — 参考答案

1. **缺少 session_id**：hook 只拿到 `(tool_name, args)`，无法知道是哪个会话在调用，也就无法"按会话"计数。应把签名改为 `hook(session_id, tool_name, args)`（需要 `_dispatch` 接收 `session_id` 参数）。**缺少拒绝通道**：返回值被忽略（类型是 `None`），hook 只能"审计"，不能"拦截"。讲义说 `PreToolUse` 用于 "gate or audit tool calls"，因此应让 hook 返回一个决策（如 `"allow"` / `"deny"` + 原因），或者抛一个约定好的异常由 `_dispatch` 捕获。
2. 已验证：hook 抛出的 `PermissionError` **不会**被捕获（`_dispatch` 的 `try` 只包住了 `tool.fn(**args)`），会一路传出 `run_agent`。结果是：该会话只写入了 `user` 轮次，没有 `assistant` 轮次；`session_end` hook 永远不会触发（setup/teardown 不对称，可能泄漏资源）；后续工具调用全部丢失。
3. 参考实现（已用注入时钟验证：第 1–5 次 `ok`，第 6、7 次 `deny`，61 秒后恢复 `ok`）：

```python
import time
from collections import defaultdict, deque

class ToolDenied(Exception):
    pass

def make_rate_limiter(limit=5, window=60.0, clock=time.monotonic):
    history = defaultdict(deque)                  # session_id -> 调用时间队列
    def hook(session_id, tool_name, args):
        if tool_name != "write_file":
            return
        now = clock()
        q = history[session_id]
        while q and now - q[0] >= window:         # 滑动窗口：丢弃过期记录
            q.popleft()
        if len(q) >= limit:
            raise ToolDenied(f"write_file rate limit: {limit}/{window:.0f}s")
        q.append(now)
    return hook
```

在 `_dispatch` 中：

```python
        try:
            for hook in self.hooks.pre_tool_use:
                hook(session_id, tool_name, args)
        except ToolDenied as e:
            result = f"denied: {e}"               # 作为工具结果交还模型
            ...                                   # 仍然触发 post hook 记审计
            return result
```

这样被拒绝的调用变成模型可以理解、可以据此调整的工具结果，会话也能正常结束。另外注意：本节代码根本没有注册 `write_file` 工具（讲义 "Build It" 说有），需要先补上。

### Q12 — 参考答案

（已用 Python 计算）

| 方案 | orchestrator 上下文 | 各 subagent 上下文 | subagent 固定开销 | 总 token |
|------|------------------|------------------|-----------------|---------|
| (a) 不用 subagent | `50 + 20×2000 = 40,050` | — | 0 | 40,050 |
| (b) 每任务一个 | `50 + 20×100 = 2,050` | `50 + 2000 + 100 = 2,150`，×20 = 43,000 | `20×3000 = 60,000` | 105,050 |
| (c) 每 5 个一批 | `50 + 4×300 = 1,250` | `50 + 5×2000 + 300 = 10,350`，×4 = 41,400 | `4×3000 = 12,000` | 54,650 |

结论：

- **上下文隔离的收益**：orchestrator 的上下文从 40K 降到 1–2K，可以继续承担后续对话和更多任务，不会被原始文件内容撑满。
- **总成本并不更低**：原始内容只是从 orchestrator 挪到了子 agent，再加上每个 subagent 的固定开销，(b) 的总 token 是 (a) 的约 2.6 倍——这正是讲义说的 over-spawn："Overhead dominates. Batch instead."
- **批处理是折中**：(c) 保持了 orchestrator 有界，同时把固定开销从 60K 降到 12K。单个子 agent 的上下文变成约 10K，仍需确认它不超出子 agent 自己的窗口。
- 何时选 (a)：任务少、结果短、后续不再需要大量上下文时，不必开 subagent（`outputs`："Spawning a subagent for a single-tool task" 是硬拒绝项）。

### Q13 — 参考回答要点

- **Client SDK**：封装 Messages API 的请求/响应、流式、tool use 的数据结构；循环、工具执行、重试、状态持久化都要自己写。
- **Agent SDK**：Claude Code 的 harness 作为库，提供开箱即用的 agent 循环、内置工具（讲义：10+）、MCP 连接、hooks、subagent、session store、trace 传播。
- **直接用 Client SDK 的场景**：
  - 单轮或简单多轮对话、分类、抽取，没有工具执行；
  - UX 依赖原始流式输出而不需要工具（`outputs`："If the agent depends on raw LLM streaming for UX without tool use, refuse the Agent SDK and recommend the Client SDK directly."）；
  - 需要完全掌控循环（例如自研编排、多 provider 路由）。
- 加分点：类比第 16 节——OpenAI Agents SDK 也是在 Responses API 上加 Agent/Handoff/Guardrail/Session/Tracing；两家的"SDK 分层"思路一致。

### Q14 — 参考回答要点

- **隔离了什么**：subagent 拥有独立的 context window 和预算；它读取的大量原始材料（文件内容、搜索结果、日志）只留在自己的上下文里，交回 orchestrator 的只是结果/摘要。
- **节省了什么**：orchestrator 的上下文保持有界，不会因为中间材料而触发压缩或遗忘早期指令；不同子任务的内容互不干扰（减少"上下文污染"）；可以并行，缩短墙钟时间。
- **代价**：
  - 每个 subagent 都有固定开销（系统提示、工具定义），总 token 往往更高（见 Q12）；
  - 摘要会丢信息，orchestrator 只能看到子 agent 选择汇报的内容；
  - 调试更难，需要 `list_subkeys`、`get_subagent_messages()` 之类的接口读子转录；
  - 并发带来竞态与资源争用。
- **不该用的时候**：单个工具调用就能完成的任务；子任务之间强依赖、需要共享大量中间状态；任务很多但很小（应批处理）。
- 常见误区：以为 subagent 能"免费扩容上下文"——总 token 一分不少，只是换了位置。

### Q15 — 参考回答要点

- **权限**：`PreToolUse` 中按工具名 + 参数做 allow/deny（路径白名单、禁止危险 shell 命令、按会话限流），拒绝时返回结构化原因而不是让 harness 崩溃（对比 Q11 的问题）。
- **审计**：`PostToolUse` 记录工具名、参数摘要、结果摘要、耗时、会话 ID；与 trace 关联。
- **生命周期**：`SessionStart` 准备环境（加载配置、挂 MCP），`SessionEnd` / `Stop` 清理；`UserPromptSubmit` 做规则注入或敏感词检查；`PreCompact` 在压缩前持久化关键信息。
- **避免 hook creep**：
  - `outputs` 硬规则："Hooks should be microseconds to milliseconds. Long work belongs in a subagent."；
  - 统一注册表，记录每个 hook 的负责人与用途；讲义建议 "Review hooks quarterly"；
  - 监控每个 hook 的耗时与启动时间。
- 加分点：hook 抛异常时要保证 `session_end` 之类的清理 hook 仍然执行（`try/finally`），本节代码没有做到。

### Q16 — 参考回答要点

- **后端**：开发用 SQLite（`outputs` 默认），生产用托管数据库或 Redis；按 `tenant_id` 分区。
- **subagent 组织**：子会话 ID 带父前缀（如本节的 `session_main.sub01`），同时维护父→子索引，支持 `list_subkeys` 渲染子 agent 树（讲义练习 3）。
- **删除**：`delete` 必须递归级联（见 Q9），数据库层用外键级联保证一致性。
- **过期**：讲义针对 session bloat 建议 "Use `list_sessions` + expiry policy"；按最后活跃时间 TTL 清理，清理时同样级联。
- **隐私**：转录包含 PII；`--session-mirror` 只能镜像到按用户隔离、加密的存储（`outputs`："If the user asks for `--session-mirror` to a shared location, refuse."）；静态加密、访问审计。
- **并发**：同一会话的多个 subagent 并行写入时需要事务或追加日志结构，避免轮次错乱。

### Q17 — 参考回答要点

- **何时切换 Managed Agents**：
  - 任务持续数小时到数天、需要异步运行（`outputs`："If the product needs long-running async work (hours-to-days), refuse the self-hosted SDK and route to Claude Managed Agents."）；
  - 不想自己运维长时运行的进程、断点恢复、prompt caching 与 compaction；
  - 代价是控制权：自托管时可以自由定制 hooks、工具执行环境与部署位置。
- **跨进程 trace**：
  - 讲义：调用方的 OTel span 通过 W3C trace context 传播到 CLI 子进程；
  - 机制上是把当前 span 的 trace ID 和 span ID 以 `traceparent` 的形式传给下游（HTTP header 或子进程环境），下游以它为父 span 继续记录；
  - 对 MCP server 等更下游的进程同理逐跳传递，后端按 trace ID 把所有 span 拼成一棵树。
- 加分点：结合第 23 节的 OTel GenAI 语义约定，统一 span 名称与属性，才能在同一后端里比较不同 agent 的耗时与成本。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：Agent SDK 封装的就是这个循环。
- [阶段 14 · 10 技能库与终身学习（Voyager）](../../10-skill-libraries-voyager/docs/zh.md)：讲义列出的先修，可复用技能与 harness 的关系。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../16-openai-agents-sdk/docs/zh.md)：OpenAI 侧的对应 SDK，可对照 handoff 与 subagent、guardrail 与 hook。
- [阶段 13 · 22 Agent Skills：可移植契约与运行时边界](../../../13-tools-and-protocols/22-skills-and-agent-sdks/docs/zh.md)：skills 与 agent SDK 的运行时边界。
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../../13-tools-and-protocols/06-mcp-fundamentals/docs/zh.md)：Agent SDK 挂载的外部工具面。

### 本节被哪些后续内容用到
- [阶段 14 · 18 生产级 Agent 运行时：快速实例化与类型化工作流](../../18-agno-and-mastra-runtimes/docs/zh.md)：`outputs` 指向的下一步——生产运行时的形状。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：W3C trace context 与 span 属性。
- [阶段 14 · 28 Orchestration 模式：监督者、Swarm 与层级结构](../../28-orchestration-patterns/docs/zh.md)：orchestrator + subagent 属于监督者模式。
- [阶段 14 · 45 通过隔离与合并契约委派 Agent 任务](../../45-delegate-with-isolation/docs/zh.md)：把"上下文隔离"推广到任务委派。
- [阶段 15 · 10 自主 Agents 的权限模式](../../../15-autonomous-systems/10-claude-code-permission-modes/docs/zh.md)：`PreToolUse` 之上的权限体系。
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../../15-autonomous-systems/12-durable-execution/docs/zh.md)：Managed Agents 面向的长时异步场景。

### 延伸关键词
`claude-agent-sdk` · `subagent` · `context isolation` · `PreToolUse / PostToolUse` · `UserPromptSubmit` · `PreCompact` · `list_subkeys` · `get_subagent_messages` · `--session-mirror` · `W3C traceparent` · `Claude Managed Agents` · `compaction` · `cascade delete`
