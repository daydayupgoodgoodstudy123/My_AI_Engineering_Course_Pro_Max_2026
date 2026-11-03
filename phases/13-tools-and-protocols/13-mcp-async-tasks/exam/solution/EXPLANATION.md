# 参考答案讲解：DurableTask（13/13）

计时结束后再看。参考实现在同目录的 `durabletask/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修轮询和取消

**现象**：解锁后的第一个错误是 `_fail_if_overdue` 里的 `TypeError: '<' not supported between instances of 'datetime.datetime' and 'NoneType'`，而测试轮询的 report 有 15 分钟的 ttl，没有理由碰到 None。

**顺着往上找**：traceback 是 `tasks_get` → `_fail_overdue` → `_fail_if_overdue`。`_fail_overdue` 在回答任何一次轮询之前，把 store 里每个任务都检查一遍，于是查到了 ttlMs 为 null 的 archive。`expires_at()` 对它返回 None（docstring 写着），调用方却直接拿去比较。出错的任务不是被轮询的任务，这一关想练的就是这个。

**依次修五处**：

1. `_fail_if_overdue` 先取 `deadline = task.expires_at()`，`deadline is None` 时直接返回：没有期限的任务永远不过期。
2. `tasks_get` 的外层 resultType 永远是 `"complete"`：tasks/get 这次调用完成了，任务自己的状态在 status。原代码按任务是否结束在 `task` 和 `complete` 之间切换，正是课里说的 parser bug，只是写在了服务器端。直接 `return complete(**task.to_wire())`。
3. `tasks_cancel` 的 else 改成 `elif task.status == "input_required"`。working 的任务只记下请求（cancel_requested，statusMessage 为 "Cancellation requested."），worker 在下一步才停；等输入的任务没有 worker 在跑，马上 cancelled；已经结束的任务什么都不改，连 lastUpdatedAt 都不动。
4. `Task.expires_at` 从 `created_at` 算。课里说 ttlMs 从创建时刻算，不是从最后一次更新算；按 lastUpdatedAt 算的话，任务每变一次状态就续一次命。
5. `tasks_get` 不再扫整个 store，只对被轮询的任务做过期检查：`task = self._fail_if_overdue(self._owned_task(...))`。`tasks_cancel` 同理。

**护栏**：扫描不能直接删掉，否则过期的任务在 tasks/get 里永远是 working。按时钟节流（每秒扫一次）也不算修好：真实的客户端按 pollIntervalMs 轮询，测试的计时循环每次轮询都让时钟前进 1 秒，节流的扫描照样每次都跑。过期的边界是 `now >= createdAt + ttlMs`，刚好满 ttlMs 就算过期；过期是一次修改，要 `_save`，lastUpdatedAt 记的是发现它过期的时刻。

## Part 2 共享目录的任务库

每个任务一个文件 `<taskId>.json`，内容是 `dataclasses.asdict(task)`，两个时间戳换成 wire 格式：

```python
def _encode(task: Task) -> str:
    record = asdict(task)
    record["created_at"] = format_time(task.created_at)
    record["last_updated_at"] = format_time(task.last_updated_at)
    return json.dumps(record, indent=2, sort_keys=True)
```

写的时候先编码（编码失败时什么都还没碰），再写进同一目录下的临时文件，最后 `os.replace` 到 `<taskId>.json`；任何一步失败都删掉临时文件。读的时候每次只读这一个文件，读不到就是 None。

容易漏的几点：

- **不缓存**：课里的 `TaskStore` 在构造时把目录读进字典，之后只读内存。另一个实例新建或修改的任务，它永远看不到。这正是课里说的“把任务记录放进进程内存不会让 MCP 有状态，只会让应用不可靠”。反过来，每次 get 都重读整个目录也不行，2000 个任务时慢上百倍。
- **原子替换**：rename 换的是目录项，旧文件的内容一个字节都没动。已经打开旧文件的读者读到完整的旧记录，之后打开的读到完整的新记录。原地重写时，读者可能读到截断的文件，进程在写到一半时崩溃，文件就坏了。
- **时间戳**：`isoformat()` 给的是 `+00:00`，`str(datetime)` 中间是空格，都不是别的实例写的 `2026-08-21T10:30:00Z`。读回要得到 aware 的 UTC datetime，用 `parse_time`；Python 3.11 之前的 `fromisoformat` 不认 `Z`。
- **只收 JSON 能装下的东西**：`default=format_time` 会把 structuredContent 里偶然混进来的 datetime 悄悄变成字符串，读回来就不是原值了。让 json.dumps 报 TypeError，旧记录保持不变。
- **文件名来自客户端**：任务 id 先过 `check_task_id`，`../elsewhere/tsk_...` 这样的 id 永远变不成路径。列任务时只认 `<taskId>.json`，崩溃留下的临时文件和 Part 5 的 `.lease` 都不是任务。
- **原样读回**：`ttl_ms` 为 null 就写 null，`issued_keys` 保持发出的顺序，嵌套的 CallToolResult 和 structuredContent 经过 json 能原样还原，包括 `0.1 + 0.2` 和非 ASCII 文本。

## Part 3 worker 和按 key 的输入

`step` 先读任务，只处理 working 的任务；cancel_requested 的任务直接 cancelled，工具不跑。然后把参数和已有的回答（副本）交给工具，按返回值改状态：

- `NeedInput`：先看这些 key 有没有发过（`issued_keys` 记着任务一生中发出的所有 key），发过就让任务 failed，错误码 -32603；否则 input_required，inputRequests 正好是这些请求，key 追加进 `issued_keys`。
- `Done`：completed，statusMessage 是 Done 的 message，result 是 `{"resultType": "complete", **工具的结果, "_meta": serverInfo}`，和直接 tools/call 返回的一样。`isError: true` 只是结果的一部分，任务照样 completed。
- 工具抛 `McpError`：failed，statusMessage 是错误的 message，error 是 `to_error()` 的结果，没有 data 就没有 data 键。

不存在的 id，worker 直接返回 False。

`tasks_update` 先查所有者（`_owned_task`，别人的任务和不存在的 id 回一样的错误），和 tasks/get 一样先做过期检查（过期的任务先 failed，回答就没有可落的地方了），再查 inputResponses 是不是对象。只有任务正在等的 key、而且回答是 elicitation 结果（accept 带 content 对象，或者 decline、cancel）才算数；答上的 key 从 inputRequests 里删掉、回答存进 answers。一个都没答上就什么都不改；全部答完时任务回到 working，statusMessage 为 "Input received."。

这样，未知的 key、已经回答过的 key 和被新请求取代的 key 都自然被忽略，第一个回答算数，部分回答保持 input_required。decline 也是回答：课里说拒绝可以导致 cancelled、一个完成的拒绝结果或别的安全结局，要写进文档，这里交给工具决定，测试里的工具收到 decline 后换了一份大纲（approve_outline_2）。

## Part 4 subscriptions/listen 的 SSE 流

最省事的写法是每次都直接调 `service.tasks_get`，带上 listen 请求自己的 `_meta`，再去掉 resultType 和 `_meta`：所有者检查、过期检查和快照格式都和 tasks/get 一模一样，推送“等同于那一刻的 tasks/get”就自然成立。

```python
def snapshot(task_id):
    result = service.tasks_get({"taskId": task_id, "_meta": meta}, principal=principal)
    return {key: value for key, value in result.items() if key not in ("resultType", "_meta")}
```

流程：

1. 校验请求（含 Tasks 扩展），失败就在发出任何东西之前抛 McpError。
2. 对请求里的每个 id 取一次快照，取不到（不存在、别人的、格式不对）就静默跳过，重复的跳过。取到的就是接受的 id，快照记作基线；已经结束的任务也接受，只是不再监视。
3. 发确认，列出接受的 id。
4. 每个 tick，对每个还在看的任务取快照，和上次发出的（或基线）整份比较，不同就发 `notifications/tasks`；快照到了终态就不再看它。只比 status 或 lastUpdatedAt 都会漏：时间戳只到秒，同一秒里的修改看不出来。
5. 没有要看的任务了，就发 listen 请求的结果（`_meta` 里 serverInfo 和 subscriptionId 并列），流结束。

每条消息都是一个 SSE 事件：`data: ` 加一行紧凑的 JSON，再一个空行；`_meta` 里的 subscriptionId 就是请求的 id，类型不变。

## Part 5 租约和过期清理

租约是 `<taskId>.lease` 文件，内容是持有者和到期时刻（注入时钟加 lease_ms）。参考实现先写临时文件，再 `os.link` 到租约路径：link 在目标已存在时失败，所以是独占创建，而且租约文件一出现就是完整的。

- `acquire`：有租约、属于别人、没过期，就返回 False；过期了（或者本来就是自己的）就删掉重建，自己的租约这样就续上了。
- `holds`：租约在、是自己的、没过期。
- `release`：只删自己的租约。

`step` 先 acquire，拿不到就返回 False；工具返回后先确认 `holds`，不再持有就什么都不提交；无论怎样（包括任务根本没活可干），最后都在 finally 里 release。这样，持有者卡住超过租约、被别人接管并完成之后，它回来也不会覆盖结果；租约到期但还没人接管时也不提交，因为它不知道别人是不是正要开始。

`sweep` 遍历所有任务：没有 ttl 或还没到期的跳过；到期且已经结束的删除；到期还没结束的（working 和 input_required）用 `_fail_if_overdue` 先 failed（EXPIRED_ERROR，盖上这一刻的 lastUpdatedAt），留给下一次 sweep 删除。删掉的任务就没有了，tasks/get 回 task not found，和从来没有过的 id 一样；别人的任务也是 task not found，而且因为先查所有者再查过期，别人的请求碰不到你的任务；格式不对的 id 在 store 里就被拦下，回 invalid taskId。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的服务里调试两层 resultType 和协作式取消，写出多实例共享、原子替换的文件存储，实现按 key 回答的任务状态机和失败语义，写出按所有者过滤、只推变化的 SSE 订阅流，以及带过期和 fencing 的租约和先失败后删除的清理。

它没证明的：租约接管时两个 worker 同时发现过期租约的竞争、请求取消和任务取消的竞态（第 29 课），断电后的持久性（fsync），真实的 HTTP 服务器、`Mcp-Name` 头和认证，`server/discover` 与扩展协商的完整流程，以及旧版 `tasks/status`、`tasks/result` 的迁移。这些要回到课里的代码和后面的课去动手。
