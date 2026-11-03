# 测验 · MCP Tasks 扩展：在无状态核心上运行持久任务（MCP Tasks Extension: Durable Work on a Stateless Core）

> **阶段 13 · 工具与协议 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么 Tasks 是扩展 | 2025-11-25 中 Tasks 是实验性核心特性；2026-07 重新设计为官方扩展 `io.modelcontextprotocol/tasks`，按需启用，不扩大所有人的核心协议；扩展规范仍是 draft，要锁定 SDK 支持的版本 |
| 2 | 何时用 task | 可能超过普通请求超时、已有 worker 队列负责执行、客户端需要重启后恢复、执行中需要暂停等待输入、取消与持久结果是产品需求；便宜的确定性查询**不要**用 task |
| 3 | 无状态核心 + 有状态应用 | 协议层无会话；task id 是**显式的应用状态**：返回前先持久化、客户端可保存并在重启后轮询、可路由到任意共享存储的副本、每个任务方法都要授权 |
| 4 | 四种生命周期 | 协议元数据（一次请求，`_meta`）、传输工作（一次 stdio 请求或 HTTP 响应）、MRTR 续传（一次重试序列，`requestState`）、持久任务（跨请求/副本/重启，共享存储） |
| 5 | 服务端决定是否创建任务 | 旧的客户端标志 `params._meta.task.required` 已删除；客户端每次声明扩展能力，服务端决定某次 `tools/call` 是否返回 `resultType: "task"`（CreateTaskResult）；未声明扩展返回 `-32021` |
| 6 | durable-before-return | 只有当 `tasks/get` 能解析该 id 时才能返回句柄；最终一致存储要等读可见 |
| 7 | 三个当前方法 | `tasks/get`（快照轮询，结果总是 `resultType: "complete"`）、`tasks/update`（提交 `inputResponses`，返回空确认）、`tasks/cancel`（协作式取消，返回空确认）；`tasks/status`、`tasks/result`、`tasks/list` 已移除 |
| 8 | 两层判别字段 | 外层 `resultType: "complete"` 表示 `tasks/get` 这个 RPC 完成；`status` 表示任务状态（`working`/`input_required`/`completed`/`cancelled`/`failed`）；完成时嵌套的 `result.resultType` 表示原 tool call 完成 |
| 9 | 创建前 vs 创建后的输入 | 创建前需要输入：核心 MRTR，重试原 `tools/call`；创建后需要输入：任务进入 `input_required`，通过 `tasks/get` 看到 `inputRequests`、用 `tasks/update` 回答，**不重试**原调用；输入键在任务生命周期内唯一 |
| 10 | 失败语义与所有权 | 工具结果 `isError: true` 仍是 `completed`；延迟执行中的 JSON-RPC 错误使任务 `failed` 并存于 `error`；`ttlMs` 从创建起算；知道 task id 不等于有权访问，每个方法都检查租户与主体 |

### 核心技能（能动手做到）

- [ ] 判断一个工具是否应该做成 task，并说出 task 带来的额外复杂度
- [ ] 写出 `tools/call` → `tasks/get` → `tasks/update` → `tasks/get` 的完整消息序列，标出每一步的 `resultType` 与 `status`
- [ ] 正确构造 Streamable HTTP 头：`Mcp-Method` 为方法名，`Mcp-Name` 在任务方法上镜像 `params.taskId`、在 `tools/call` 上为工具名
- [ ] 区分请求取消（`notifications/cancelled`）与任务取消（`tasks/cancel`），并解释网关为何要分两张路由表
- [ ] 读懂 `TaskStore` 的"临时文件 + 原子 rename"持久化，并指出多实例下的陈旧缓存与丢失更新问题
- [ ] 跑通 `main.py` 与 17 个单元测试，完成讲义练习中的部分更新、所有权、租约、过期清理

---

## 二、基础自测（选择题）

**Q1.** 关于 2026-07-28 中 Tasks 的定位，下列说法正确的是：

- A. Tasks 是核心协议的强制部分，所有服务端都必须实现
- B. Tasks 依赖 `Mcp-Session-Id` 把任务绑定到连接上
- C. 客户端通过 `params._meta.task.required: true` 要求服务端以任务模式执行
- D. Tasks 是官方扩展 `io.modelcontextprotocol/tasks`，客户端每次请求声明支持，服务端决定某次 `tools/call` 是否返回任务

**Q2.** `tasks/get` 的响应为 `{"resultType": "complete", "status": "working", ...}`。正确的理解是：

- A. `tasks/get` 这个 RPC 已经完成；它所描述的任务仍在运行
- B. 任务已经完成，可以读取结果
- C. 响应自相矛盾，客户端应报错
- D. 应该再调用 `tasks/result` 获取结果

**Q3.** 任务在执行中需要用户批准大纲。在当前扩展中，客户端应该：

- A. 用新 id 重试原来的 `tools/call`，带上 `inputResponses` 和 `requestState`
- B. 调用 `tasks/result` 并在参数中带上批准结果
- C. 通过 `tasks/get` 看到 `inputRequests`，然后用 `tasks/update` 提交 `inputResponses`，之后继续轮询
- D. 等待服务端通过反向 JSON-RPC 请求发来 `elicitation/create`

**Q4.** 对 `tasks/cancel` 返回的空确认 `{"resultType": "complete"}`，客户端应如何理解？

- A. worker 已经停止，任务状态一定是 `cancelled`
- B. 服务端记录了取消意图；取消是协作式的，任务可能先完成、忽略取消或稍后才转换状态，需继续通过 `tasks/get` 观察
- C. 任务已被删除，再调 `tasks/get` 一定返回 not found
- D. 等同于发送了 `notifications/cancelled`

**Q5.** 一个工具调用在任务中执行完毕，产出了 `isError: true` 的正常工具结果（例如"报告数据源为空"）。任务状态应为：

- A. `completed`，并在 `result` 中内联这个 `isError: true` 的 CallToolResult
- B. `failed`，并把它放进 `error`
- C. `cancelled`
- D. 保持 `working`，等待客户端重试

**Q6.** 使用 Streamable HTTP 发送 `tasks/update`（`params.taskId = "tsk_786512e29e0d"`）时，`Mcp-Name` 头应为：

- A. `tasks/update`
- B. `generate_report`
- C. 不需要该头
- D. `tsk_786512e29e0d`

**Q7.** 为什么当前扩展**没有** `tasks/list`？

- A. 因为任务数量太多，列表性能太差
- B. 无会话的服务端无法安全推断"哪些任务属于这个连接"；需要历史的应用应提供带显式过滤与所有权规则的授权领域工具
- C. 因为 `tasks/get` 已经可以返回所有任务
- D. 因为任务 id 是公开信息，客户端可以自己枚举

**Q8.** 关于 `ttlMs`，讲义的说法是：

- A. 从任务完成时开始计算，承诺完成后至少保留结果这么久
- B. 是建议的轮询间隔
- C. 从任务创建时开始计算，可以变化，可以是 `null`；服务端可以让过期任务失败并稍后删除，它不是"完成后保留多久"的承诺
- D. 是每次 `tasks/get` 响应在客户端缓存的时长

---

## 三、动手 / 代码题

**Q9.** 运行 `main.py`，前六行输出为：

```text
id=0 resultType=complete status=ack
id=1 resultType=task status=working
id=2 resultType=complete status=working
id=3 resultType=complete status=input_required
id=4 resultType=complete status=ack
id=5 resultType=complete status=completed
```

1. 每一行分别对应哪个方法调用？`status=ack` 是协议字段吗？
2. id=1 之后，`run_demo` 执行了 `service = TaskService(directory)`。这一步在演示什么？
3. 在 id=2 与 id=3 之间、id=4 与 id=5 之间分别发生了什么？为什么 worker 是"显式推进"而不是后台线程？
4. 写出 id=5 响应中**两个** `resultType` 的位置和含义。

**Q10.** 下面的代码在同一目录上创建两个服务实例（模拟两个副本），已实测：

```python
A = main.TaskService(d); B = main.TaskService(d)
tid = A.dispatch(make_request(1, "tools/call", {...}))["result"]["taskId"]
B.dispatch(make_request(2, "tasks/get", {"taskId": tid}))
# -> {"error": {"code": -32602, "message": "task not found"}}
```

1. 任务明明已经写入磁盘，为什么 B 找不到？这违背了讲义的哪条承诺？
2. 继续：A 推进 worker 到 `input_required`、提交批准、再推进到 `completed`；随后**陈旧的** B 调用 `advance_worker(tid)`。实测磁盘上的任务变成了 `input_required`、`stage=1`。解释这次"丢失更新"是怎么发生的，为什么 `issued_keys` 的重复检查没能拦住它。
3. 给出修复方案（至少包括：读路径、写路径的并发控制、worker 租约）。

**Q11.** 阅读 `tasks_update`：

```python
        if task.status == "input_required":
            answer = responses.get("approve_outline")
            if isinstance(answer, dict):
                action = answer.get("action")
                if action in {"decline", "cancel"}:
                    task.status = "cancelled"
                    ...
                elif action == "accept" and isinstance(answer.get("content"), dict):
                    if answer["content"].get("approved") is True:
                        task.status = "working"
                        task.stage = 2
                        ...
        return complete()
```

1. 用户提交 `{"action": "accept", "content": {"approved": false}}`，会发生什么？任务最终会怎样？
2. 本实现把 `decline` 和 `cancel` 都映射为任务 `cancelled`。讲义怎么评价这种选择？与第 12 节对 decline/cancel 的处理有何不同？
3. 讲义练习 1：再加一个输入键 `choose_format`（`pdf` / `html`），要求两个键都回答后才继续。请改写 `advance_worker` 的 stage 0 与 `tasks_update`，并说明"部分更新"、"已回答键被再次提交"、"未知键"三种情况各怎么处理。

**Q12.** `TaskStore.persist`：

```python
    def persist(self, task: Task) -> None:
        path = self.directory / f"{task.task_id}.json"
        temporary = self.directory / f"{task.task_id}.tmp"
        temporary.write_text(json.dumps(asdict(task), indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)
        self.tasks[task.task_id] = task
```

1. 为什么先写 `.tmp` 再 `replace`，而不是直接写 `.json`？`reload` 为什么不会读到半个文件？
2. 这样做能保证断电后数据一定在吗？还缺什么？
3. 讲义练习 5：加入过期清理。写出 `tasks_get` 中处理过期任务的逻辑，并说明如何"区分过期任务与格式错误的 id，同时不泄露其他租户任务的存在"。

---

## 四、面试高频题

**Q13.**（基础必考）MCP 2026-07-28 号称"无状态"，那 Tasks 扩展的持久任务不就是状态吗？二者矛盾吗？

**Q14.**（原理深挖）对比核心 MRTR 与 Tasks 扩展中的输入流程：各自的续传载体、重试方式、适用时机是什么？为什么一个任务里的 `inputRequests` 键必须在整个生命周期内唯一？

**Q15.**（工程实践）你要把一个"生成大型报表"的工具做成多副本部署的 MCP 任务服务，请给出存储、worker、所有权、轮询、过期的设计。

**Q16.**（场景设计）网关同时代理普通请求与任务。用户在 `tools/call` 返回任务句柄后关闭了浏览器标签页，又在另一台设备上点了"取消"。网关应该如何路由与处理？

**Q17.**（追问型）从 2025-11-25 实验版 Tasks 迁移到当前扩展，有哪些 breaking change？迁移时你会怎么做？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："The July 2026 redesign moves them into the official `io.modelcontextprotocol/tasks` extension so clients and servers can opt into the extra lifecycle"；"The old client flag `params._meta.task.required` is gone. The client declares extension support, then the server decides whether a particular `tools/call` becomes a task." A 错，扩展是可选的；B 错，2026-07-28 没有 `Mcp-Session-Id`，任务靠持久化的 id；C 是已删除的旧机制（测试 `test_server_directed_creation_returns_task_result` 还特意断言请求 `_meta` 中没有 `task` 字段）。

### Q2 — 答案：A

讲义："`tasks/get` itself completed, so its result always has `resultType: "complete"`. The nested task can still have `status: "working"`." 并专门指出这是"a common parser bug"。B 混淆了两个字段；C 错，这是规范设计；D 错，`tasks/result` 已被移除，任务完成后下一次 `tasks/get` 直接在 `result` 中内联原 CallToolResult。

### Q3 — 答案：C

讲义 "Input needed after task creation"：任务设为 `input_required`，`tasks/get` 暴露 `inputRequests`，客户端用 `tasks/update` 提交，"The client does not retry the original `tools/call`." A 是**创建前**需要输入时的核心 MRTR 做法；B 中 `tasks/result` 已不存在；D 错，2026-07-28 服务端不发反向请求。

### Q4 — 答案：B

讲义："`tasks/cancel` signals intent and returns an empty complete acknowledgement. That acknowledgement does not guarantee the worker stopped." 本节代码的 worker 会立即把状态改成 `cancelled`（并且幂等），但讲义提醒"A production client must still treat cancellation as cooperative"。C 错，取消不等于删除；D 错，`notifications/cancelled` 用于取消一次进行中的请求，"Do not use `notifications/cancelled` to cancel a task."

### Q5 — 答案：A

讲义："A normal tool result with `isError: true` is still a `completed` task because the tool call produced its defined result." 只有延迟执行中发生 **JSON-RPC 错误**才使任务 `failed`，并把 JSON-RPC error 对象放在 `error` 下（排除 B）。`cancelled` 用于取消或用户拒绝等情形（C）；D 无依据。

### Q6 — 答案：D

讲义："For all three task methods, `Mcp-Name` mirrors `params.taskId`. It does not repeat the JSON-RPC method name." 方法名放在 `Mcp-Method` 头里（排除 A）。B 是 `tools/call` 时 `Mcp-Name` 的值（代码 `make_http_request` 中 `tools/call` 取 `params.name`）。代码对三个任务方法缺少 `taskId` 时直接抛 `ValueError`（实测 `tasks/get requires a name for Mcp-Name`），说明该头是必需的（排除 C）。

### Q7 — 答案：B

讲义："There is no `tasks/list`. Sessionless servers cannot safely infer which tasks belong in a connection-scoped list. Applications that need history should expose an authorized domain tool with explicit filters and ownership rules." A、C 不是原因；D 恰好相反——"Knowing a task id must not grant access"，task id 也不应可枚举。

### Q8 — 答案：C

讲义："`ttlMs` is measured from creation and may change... A server may fail and later delete an expired task. Do not describe it as a promise to retain a completed result for that many milliseconds after completion." 任务形状中 `ttlMs` 可以是 `null`（无声明上限）。B 是 `pollIntervalMs`；D 混淆了第 10 节结果缓存提示中的 `ttlMs`——同名字段，在任务对象中含义不同。本节代码 `ttl_ms=900_000`（15 分钟），但**从未执行过期检查**（见 Q12）。

### Q9 — 参考答案

1. 对应关系：

| id | 方法 | 说明 |
|----|------|------|
| 0 | `server/discover` | 普通 complete 结果 |
| 1 | `tools/call` | 服务端决定创建任务，返回 `resultType: "task"`、`status: "working"` |
| 2 | `tasks/get` | RPC complete，任务 working |
| 3 | `tasks/get` | 任务 input_required，含 `inputRequests.approve_outline` |
| 4 | `tasks/update` | 空确认 |
| 5 | `tasks/get` | 任务 completed，内联结果 |

   `status=ack` **不是**协议字段：`main()` 打印时用 `result.get('status', 'ack')`，空确认结果中没有 `status`，于是显示占位词 `ack`。

2. 新建 `TaskService` 会让 `TaskStore.__init__` 调用 `reload()` 从磁盘重新读取所有任务，模拟"进程重启"或"请求被路由到另一个副本"；id=2 仍能查到任务，证明 durable-before-return 与重启恢复（测试 `test_task_is_durable_before_handle_is_returned`）。
3. id=2→3 之间：`service.advance_worker(task_id)`，stage 0 → 发出 `approve_outline` 表单、状态变 `input_required`、stage 1；id=4→5 之间：再次 `advance_worker`，stage 2 → 生成结果、状态 `completed`、stage 3（stage 2 是 `tasks_update` 收到批准后设置的）。讲义："The worker advances explicitly instead of sleeping in a background thread. That makes every state transition deterministic and keeps the protocol example separate from queue mechanics."
4. 外层 `result.resultType = "complete"`：`tasks/get` 这个 RPC 完成；`result.result.resultType = "complete"`：被内联的原始 `tools/call` 结果（CallToolResult）完成。嵌套结果还带自己的 `_meta.serverInfo`（测试 `test_completed_task_inlines_original_tool_result` 断言）。

### Q10 — 参考答案

1. `TaskStore` 在**构造时**把磁盘上的任务一次性读进 `self.tasks` 字典，之后 `get` 只查内存，从不回读磁盘。B 构造时任务还不存在，所以永远看不到 A 后来创建的任务（实测 `task not found`；手动 `B.store.reload()` 后才看到 `working`）。这违背了讲义："The id can route to any replica backed by the same durable store"，以及"Moving a task record into process memory does not make MCP stateful. It makes the application unreliable."
2. 丢失更新过程：B 内存中的任务副本停留在"working、stage 0、`issued_keys=[]`"。A 把磁盘上的任务推进到 `completed`。B 调用 `advance_worker`：读到的是**自己的陈旧副本**，认为 stage 0，于是重新发出 `approve_outline`、设为 `input_required`、`stage=1`，再 `persist` 覆盖磁盘文件——已完成的结果被抹掉（实测磁盘上为 `input_required 1 ['approve_outline']`）。`issued_keys` 检查拦不住，是因为它检查的也是陈旧副本中的 `issued_keys`（空列表）。本质是"读—改—写"没有任何版本检查或锁。
3. 修复：
   - **读路径**：每次 `get` 都从共享存储读最新版本（或带版本号的缓存 + 失效），不长期持有内存副本。
   - **写路径**：乐观并发控制——任务带 `version` 字段，写入时 `UPDATE ... WHERE task_id=? AND version=?`，影响行数为 0 就重读重试；文件存储可用 `fcntl` 文件锁或"比较后交换"。
   - **worker 租约**（讲义练习 3）：worker 推进前先获取带过期时间的租约（`lease_owner`、`lease_expires_at`），只有持有有效租约的实例才能推进；租约过期后其他实例可接管，避免两个副本同时完成同一任务。
   - 状态转换做成"只能前进"的状态机校验（例如 `completed` 不能回到 `input_required`），作为最后一道防线。

### Q11 — 参考答案

1. 实测：返回空确认，任务**保持 `input_required`**，`advance_worker` 也不会推进（它只处理 `working`）。由于代码从不检查 `ttlMs` 过期，任务会无限期卡住，用户的"不批准"被静默忽略。更合理的做法是把 `approved: false` 视为拒绝：转为 `cancelled`，或返回一个"已完成的拒绝结果"，或重新生成大纲并发出一个**新的**输入键（如 `approve_outline_v2`，因为键不能复用）。
2. 讲义："User refusal can produce `cancelled`, a completed refusal result, or another domain-specific safe outcome. Document the choice." 本节选择了 `cancelled`，是允许的，但要写进文档。差异：第 12 节中 `decline` 是终局、`cancel` 可重试（MRTR 的 state 不被消耗）；而这里 `cancel`（用户只是关掉了对话框）也让整个任务终结，用户无法回来再批准——对于长任务，这可能过于严厉，可以考虑 `cancel` 时保持 `input_required` 直到 `ttlMs` 到期。
3. 改写思路：

```python
# advance_worker, stage 0：一次发出两个键
for key in ("approve_outline", "choose_format"):
    if key in task.issued_keys:
        raise RuntimeError("task input request key cannot be reused")
task.issued_keys += ["approve_outline", "choose_format"]
task.input_requests = {"approve_outline": {...}, "choose_format": {...}}
task.answers = {}                         # 新字段：已收到的有效回答

# tasks_update
if task.status == "input_required":
    for key, answer in responses.items():
        if key not in task.input_requests:      # 未知、已被取代或已回答的键：忽略
            continue
        if not isinstance(answer, dict):
            continue
        if answer.get("action") in {"decline", "cancel"}:
            task.status = "cancelled"; task.input_requests = {}; break
        if answer.get("action") == "accept" and valid(key, answer.get("content")):
            task.answers[key] = answer["content"]
            del task.input_requests[key]        # 已回答的键从未决集合移除
    if task.status == "input_required" and not task.input_requests:
        task.status = "working"; task.stage = 2
    self.store.save(task)
return complete()
```

   - **部分更新**：只回答了一个键时，它从 `input_requests` 中移除，任务仍为 `input_required`，下一次 `tasks/get` 只显示剩余的键（讲义："A partial update can leave the task in `input_required` until all required keys are answered."）。
   - **已回答的键再次提交**：它已不在 `input_requests` 中，被忽略，不会覆盖第一次的回答。
   - **未知键**：忽略并仍返回空确认（测试 `test_unknown_input_response_is_ignored` 验证了现有代码的这一行为）。
   - `answers` 要随任务一起持久化，`Task` dataclass 需要新增字段（注意 `Task(**data)` 读旧文件时新字段要有默认值）。

### Q12 — 参考答案

1. 直接写 `.json` 时，进程在写到一半崩溃会留下截断的 JSON，`reload` 解析时抛异常导致整个服务无法启动。先写临时文件、再 `Path.replace`（底层 `os.replace`），在同一文件系统上 rename 是原子的：读者要么看到旧文件、要么看到完整的新文件。`reload` 只 `glob("*.json")`，残留的 `.tmp` 文件不会被读取。
2. 不能完全保证。`write_text` 之后数据可能还在操作系统页缓存里，断电会丢；严格的持久化需要对临时文件 `fsync`、rename 后再对**目录** `fsync`。此外这是单机文件，多副本仍需共享存储（数据库、对象存储 + 条件写）。讲义："A multi-replica service should use a shared durable store and a worker lease or equivalent concurrency control."
3. 过期处理思路：

```python
def _is_expired(task: Task, now: datetime) -> bool:
    if task.ttl_ms is None:
        return False
    created = datetime.fromisoformat(task.created_at.replace("Z", "+00:00"))
    return (now - created).total_seconds() * 1000 >= task.ttl_ms

def tasks_get(self, params, *, principal):
    ...
    task_id = params.get("taskId")
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        raise McpError(-32602, "invalid taskId")          # 格式错误：与租户无关，可以明说
    task = self.store.find(task_id)
    if task is None or task.owner != principal:
        raise McpError(-32602, "task not found")          # 不存在 / 不属于你：同一个错误
    if _is_expired(task, datetime.now(timezone.utc)):
        if task.status not in TERMINAL_STATUSES:
            task.status = "failed"
            task.error = {"code": -32603, "message": "task expired"}
            self.store.save(task)
        # 或者已被清理任务删除 -> 同样返回 "task not found"
    return complete(**task.to_wire())
```

   - **格式错误**（如 `tsk_` 前缀缺失、长度不对）只取决于输入本身，可以返回明确的 `invalid taskId`。
   - **不存在**与**属于其他租户**必须返回**同一个**错误，否则攻击者可以探测别人的任务 id 是否存在——当前代码 `_owned_task` 已经这样做（统一为 `task not found`）。
   - **过期**只在所有权检查**通过之后**才区分，所以不会泄露跨租户信息。
   - 后台清理：定期扫描过期且已超过保留期的任务并删除；删除后的查询返回 `task not found`。
   - 实现时注意 `created_at` 是带 `Z` 的 ISO 字符串，Python 3.11 之前 `fromisoformat` 不认 `Z`，所以先替换为 `+00:00`。

### Q13 — 参考回答要点

- **不矛盾**："无状态"指的是**协议层**：没有 `initialize`、没有协议会话、没有 `Mcp-Session-Id`，每个请求自带版本与能力，任何实例都能处理任何请求。
- **任务是显式的应用状态**：服务端在返回句柄前持久化；客户端保存 task id，重启后继续轮询；id 可路由到任何共享同一存储的副本；每个方法都做授权；过期由任务字段定义而不是传输生命周期。
- **与隐式会话状态的区别**：会话状态挂在连接上，看不见、难重放、难审计、难路由，连接一断就丢；任务状态有名字（id）、有所有者、有生命周期、可查询。
- 讲义四种生命周期表格是很好的答题框架：协议元数据、传输工作、MRTR 续传、持久任务。
- 常见误区：把任务记录放在进程内存——"That does not make MCP stateful. It makes the application unreliable."（本节代码的内存缓存就有这个问题，见 Q10）

### Q14 — 参考回答要点

| 维度 | 核心 MRTR | Tasks 扩展输入 |
|------|----------|---------------|
| 时机 | 任务创建**前**（同步请求内） | 任务创建**后**（执行中暂停） |
| 服务端返回 | 原请求返回 `resultType: "input_required"` | 任务 `status: "input_required"`，`tasks/get` 暴露 `inputRequests` |
| 续传载体 | 签名的 `requestState`（客户端回显） | 服务端持久化的任务记录（按 task id） |
| 客户端动作 | 用新 id **重试原方法**，带 `inputResponses` + `requestState` | 发送 `tasks/update`，**不**重试原方法 |
| 确认 | 重试的响应就是下一步结果 | 空确认，状态变化可能最终一致，需继续轮询/订阅 |

- **键唯一的原因**：同一任务可能多次轮询看到同一个未决键，客户端要据此对 UI 去重；网络重试可能让同一个回答提交多次；如果键被复用，服务端无法区分"对旧问题的迟到回答"和"对新问题的回答"，可能把用户对旧大纲的批准当成对新大纲的批准。所以服务端要记录所有已发出的键（代码中的 `issued_keys`），并忽略未知、已被取代或已回答的键。
- 加分点：讲义建议"只在同步 MRTR 轮次结束后才创建任务"。

### Q15 — 参考回答要点

- **存储**：共享事务型数据库（如 Postgres）一张 `tasks` 表：`task_id`、`tenant_id`、`owner`、`operation`、`status`、`status_message`、时间戳、`ttl_ms`、`poll_interval_ms`、`stage`、`input_requests`、`issued_keys`、`result_ref`/`error`、`version`、`lease_owner`、`lease_expires_at`。大结果放对象存储，任务里存授权的资源句柄（技能文件要求"Refuse an unbounded result payload"）。
- **创建**：在事务中插入记录并提交，确保读可见后才返回 `resultType: "task"`；同时把任务推入队列。
- **worker**：从队列取任务，获取租约（条件更新），按状态机推进；每次写入带版本检查；租约过期可被其他 worker 接管；状态只能前进。
- **所有权**：每个 `tasks/get/update/cancel` 与订阅都按 `(tenant, principal)` 查询；不存在与无权限返回同一个错误。
- **轮询**：返回 `pollIntervalMs`（可随阶段调整，例如排队时 5 秒、执行中 1 秒）；对过于频繁的轮询限流；提供 `subscriptions/listen` + `notifications/tasks` 作为可选推送。
- **过期**：`ttlMs` 从创建起算；过期未完成的任务标记 `failed`；定期清理超过保留期的记录与结果对象。
- **取消**：`tasks/cancel` 记录取消意图，worker 在检查点上协作停止。
- **可观测性**：按 task id 关联日志与追踪；监控队列深度、任务时长、过期率。

### Q16 — 参考回答要点

- **关闭标签页**：此时 `tools/call` 已经返回了任务句柄，原请求已完成；关闭传输只会结束请求级的东西（比如一个 `subscriptions/listen` 的 SSE 流），**不会**也**不能**停止持久任务。讲义："If `tools/call` has already returned `resultType: "task"`, that request is complete and closing its transport cannot name or stop the durable job."
- **另一台设备取消**：客户端发送新的、带认证的 `tasks/cancel` RPC，`params.taskId` 与 `Mcp-Name` 头相同；网关用 `Mcp-Name` 在**任务路由表**中找到拥有该任务的后端（不依赖会话粘性），后端校验所有权、记录取消意图、返回空确认。
- **两张表**：请求协调表（请求 id → 进行中的请求/响应流，响应结束即删除）与任务路由表（task id → 后端，保留到任务终态且超过保留期）。`notifications/cancelled` 只查第一张表。
- **客户端之后**：继续 `tasks/get` 观察状态，可能是 `cancelled`，也可能任务已先完成。
- 加分点：第 29 节会展开取消竞争、超时、幂等与背压规则。

### Q17 — 参考回答要点

- **breaking change**：
  - 能力：从核心特性变为扩展 `io.modelcontextprotocol/tasks`，在每个请求的 `clientCapabilities.extensions` 中声明；未声明返回 `-32021`。
  - 创建：客户端请求任务（`params._meta.task.required`）→ 服务端决定，返回 `resultType: "task"`。
  - 方法：`tasks/status`、`tasks/result`、`tasks/list` 移除；改为 `tasks/get`（结果内联在快照中）、`tasks/update`、`tasks/cancel`。
  - 输入：执行中输入通过 `tasks/get` + `tasks/update`，不再有服务端反向请求。
  - 通知：通过 `subscriptions/listen`（POST 响应 SSE）+ `notifications/tasks`，不再有独立 GET 事件流、会话 SSE 或 `Last-Event-ID` 重放。
- **迁移做法**：把旧方法名只保留在固定版本的 legacy 适配器中；核心存储与 worker 与线协议适配层分离；锁定扩展版本并跑一致性测试；测试中断言旧方法返回 `-32601`（本节 `test_removed_legacy_task_methods_are_not_found`）。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：`Mcp-Method`/`Mcp-Name` 头、POST 响应 SSE。
- [阶段 13 · 11 MCP 模型输入：Sampling 迁移与无状态 MRTR](../../11-mcp-sampling/docs/zh.md)：核心 MRTR 与 `requestState`，对照本节的任务内输入。
- [阶段 13 · 12 显式作用范围与无状态 Elicitation](../../12-mcp-roots-and-elicitation/docs/zh.md)：form 模式 elicitation 与 accept/decline/cancel。
- [阶段 13 · 10 MCP Resources 与 Prompts](../../10-mcp-resources-and-prompts/docs/zh.md)：`subscriptions/listen` 与 subscription ID。

### 本节被哪些后续内容用到
- [阶段 13 · 29 MCP 可靠性、取消与流量控制](../../29-mcp-reliability-cancellation-and-flow-control/docs/zh.md)：请求取消与任务取消的竞争、超时、幂等、背压（讲义直接引用）。
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：网关的请求表与任务路由表。
- [阶段 13 · 31 MCP 一致性工程：版本管理、证据与运维](../../31-mcp-conformance-versioning-and-operations/docs/zh.md)：锁定扩展版本与一致性场景。
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../../15-autonomous-systems/12-durable-execution/docs/zh.md)：持久执行的通用模式。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../../16-multi-agent-and-swarms/22-production-scaling-queues-checkpoints/docs/zh.md)：队列、租约与检查点。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：带人工输入暂停的持久工作流。

### 延伸关键词
`io.modelcontextprotocol/tasks` · `CreateTaskResult` · `resultType: task` · `tasks/get` · `tasks/update` · `tasks/cancel` · `pollIntervalMs` · `ttlMs` · `durable-before-return` · `atomic rename` · `fsync` · `optimistic concurrency` · `worker lease` · `notifications/tasks` · `Mcp-Name`
