# 代码讲解 · main.py

> **所属小节**：阶段 13 · 工具与协议 · 第 29 节 MCP 可靠性、取消与流量控制 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`；测试 `python3 -m unittest discover tests -v` ｜ **依赖**：仅标准库（`hashlib`、`json`、`sqlite3`、`tempfile`、`threading`、`dataclasses`、`pathlib`、`typing`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

这是一个**确定性模拟器**：没有 sleep、没有 socket、没有随机故障，事件发生的顺序完全由调用者控制。它把讲义里"MCP 协议之外、应用必须自己负责"的六件事各做成一个小组件：

1. **取消信号随传输而不同**：stdio 发 `notifications/cancelled`，Streamable HTTP 关闭响应流（`RequestCoordinator.client_cancel_signal`）。
2. **取消与完成的竞争**：每个请求只有一个终态，取消先到就抑制响应，完成先到就忽略迟到的取消（`complete` / `receive_stdio_cancellation`）。
3. **两个时钟**：progress 可以重置 idle timeout，但不能重置 maximum timeout（`timeout_signal`）。
4. **业务幂等**：新的 JSON-RPC id 不是幂等；用 SQLite 事务把"查键 + 副作用 + 计数 + 存结果"原子化（`MutationLedger`）。
5. **背压**：有界 SSE 缓冲，progress 可合并/丢弃，最终响应不可丢（`BoundedSseBuffer`）。
6. **恢复**：SSE 头、保活注释、重连即 refetch、指数退避 + jitter；以及 `tasks/cancel` 只是"确认意图"（`DurableTaskService`）。

> 一句话：**用可重复的事件序列，把分布式系统里最贵的那几类 bug（迟到的响应、重复扣款、慢消费者、重连风暴）变成可以断言的确定结果。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `STDIO` / `STREAMABLE_HTTP` / `IN_PROGRESS` / `COMPLETED` / `CANCELLED` | 模块常量 | 传输与请求状态的字符串常量 | 传输、终态 |
| `ReliabilityError` | 异常类（继承 `ValueError`） | 违反可靠性不变量时抛出 | 显式失败 |
| `InFlightRequest` | dataclass | 一个在途请求：id、传输、开始时间、两个超时、progress token、状态、响应 | 请求记录 |
| `RequestCoordinator` | 类 | 启动请求、发 progress、算超时、生成/接收取消、完成、服务端取消订阅 | 取消竞争、两个时钟 |
| `RetryDecision` + `classify_retry` | frozen dataclass + 函数 | 按"有无副作用、有无幂等键"返回 safe / conditional / unsafe | 重试矩阵 |
| `MutationLedger` | 类（上下文管理器） | 文件型 SQLite ledger，`charge()` 在一个 `BEGIN IMMEDIATE` 事务里完成查键、计数、写结果 | 原子幂等边界 |
| `DurableTask` + `DurableTaskService` | dataclass + 类 | `cancel` 只置标记，`worker_checkpoint` 才变 `cancelled`，`finish` 可能先完成 | `tasks/cancel` 语义 |
| `BoundedSseBuffer` | 类 | 有界队列：合并相邻同 token progress、满了丢最旧 progress、保留 final | 背压 |
| `sse_response_headers` / `sse_keepalive` | 函数 | 返回防代理缓冲的 SSE 头和 `:` 注释行 | 代理缓冲、保活 |
| `reconnect_plan` | 函数 | 新订阅 id、不发 `Last-Event-ID`、refetch 列表、是否重放不安全变更 | 重连即 refetch |
| `retry_delay_ms` | 函数 | 由 `client_id` 和 attempt 确定性算出带上限的指数退避 + jitter | 防重连风暴 |
| `main` | 函数 | 依次演示两种竞争、幂等扣款、缓冲过载、Task 取消 | 演示 |

数据流：`main()` → `RequestCoordinator`（请求 7：idle 超时 → stdio 取消 → `complete` 返回 `None`；请求 8：先完成 → 迟到取消被忽略）→ 临时目录里的 `MutationLedger`（同键两次扣款）→ `BoundedSseBuffer(3)`（6 条 progress + final）→ `DurableTaskService`（ack 后仍 `working`，checkpoint 后 `cancelled`）→ 打印 8 行结论。

---

## 3. 逐段精讲

### 3.1 常量、异常与 `InFlightRequest`

```python
@dataclass
class InFlightRequest:
    request_id: int | str
    operation: str
    transport: str
    started_at_ms: int
    idle_timeout_ms: int
    max_timeout_ms: int
    progress_token: int | str | None = None
    last_activity_ms: int = 0
    last_progress: float | None = None
    state: str = IN_PROGRESS
    cancel_reason: str | None = None
    response: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.last_activity_ms = self.started_at_ms
```

- 时间全部用整数毫秒，由调用者传入（`started_at_ms`、`now_ms`），这就是"没有 sleep 的确定性模拟"的关键：时间是参数，不是 `time.time()`。
- `__post_init__` 把"最后活动时间"初始化为开始时间，所以 idle 时钟从请求开始就在走。⚠️ 这意味着即使构造时显式传了 `last_activity_ms` 也会被覆盖。
- `state` 只有三个值，`IN_PROGRESS` 是唯一的非终态；后面所有方法都靠"只在 `IN_PROGRESS` 时允许转移"来保证**单一终态**。
- `ReliabilityError` 继承 `ValueError`，所以既可以精确捕获，也能被通用的 `except ValueError` 接住。

### 3.2 `RequestCoordinator.start`：入口校验

```python
        if type(request_id) not in (int, str):
            raise ReliabilityError("request id must be an integer or string")
        if progress_token is not None and type(progress_token) not in (int, str):
            raise ReliabilityError("progress token must be an integer or string")
        if request_id in self.requests:
            raise ReliabilityError("request ids must be unique while tracked")
        if transport not in {STDIO, STREAMABLE_HTTP}:
            raise ReliabilityError("unsupported transport")
        if idle_timeout_ms <= 0 or max_timeout_ms < idle_timeout_ms:
            raise ReliabilityError("timeouts must be positive and maximum must cover idle")
```

- 用 `type(x) not in (int, str)` 而不是 `isinstance`：`isinstance(True, int)` 为 `True`，而 JSON-RPC id 不应是布尔值；`type()` 精确比较还会拒绝 `int` 的子类（测试里的 `DerivedInt(7)`）。
- **先做类型检查、再查字典**：如果 `request_id` 是 `[]` 或 `{}`，直接 `in self.requests` 会抛 `TypeError: unhashable type`，所以顺序很重要（测试名 `..._before_lookup` 就是在强调这一点）。
- `max_timeout_ms < idle_timeout_ms` 被拒绝：最大期限必须覆盖 idle 期限，否则 idle 永远没机会生效。
- ⚠️ 请求记录永远不会从 `self.requests` 删除，所以"跟踪期间唯一"实际上等于"协调器生命周期内唯一"，长时间运行会无限增长——模拟器可以这样，生产需要在终态后一段时间清理。

### 3.3 `progress`：单调递增、只在进行中发送

```python
        request = self.requests[request_id]
        if request.state != IN_PROGRESS or request.progress_token is None:
            return None
        if request.last_progress is not None and value <= request.last_progress:
            raise ReliabilityError("progress must increase")
        request.last_progress = value
        request.last_activity_ms = now_ms
```

- 终态后或没有 progress token 时返回 `None`：讲义 "Notifications stop after completion or cancellation"；没有 token 就不能发 progress 通知。
- `value <= last_progress` 直接抛错：MCP 要求 progress 值必须递增。
- **重置 idle 时钟**：`last_activity_ms = now_ms`。但它**不碰** `started_at_ms`，所以 maximum timeout 不受影响。
- 通知格式：`{"jsonrpc":"2.0","method":"notifications/progress","params":{"progressToken":..., "progress":..., "total"?:..., "message"?:...}}`，`total`、`message` 只在提供时才放进去。
- ⚠️ 讲义说要"Rate-limit progress"，代码没有实现限速；也不检查 `now_ms` 是否已超过期限（实测：1999 ms 后已到最大期限，2500 ms 时 `progress()` 仍会被接受，因为超时只有在调用 `timeout_signal` 时才被"发现"）。

### 3.4 `timeout_signal`：两个时钟

```python
        hard_due = now_ms - request.started_at_ms >= request.max_timeout_ms
        idle_due = now_ms - request.last_activity_ms >= request.idle_timeout_ms
        if not hard_due and not idle_due:
            return None
        reason = "maximum timeout" if hard_due else "idle timeout"
        return self.client_cancel_signal(request_id, reason=reason)
```

- 两个条件都用 `>=`：正好到期也算超时。
- 同时满足时报 `maximum timeout`（硬期限优先，原因更明确）。
- 它**只生成信号，不改状态**。模拟的是"客户端发现超时 → 发出取消"，服务端收到后（`receive_stdio_cancellation` / `close_http_stream`）才变成 `CANCELLED`。
- 讲义的例子（progress 在 400/800/1200）：1500 ms 时 idle 只过了 300 ms、总时长 1500 < 2000 → `None`；2000 ms 时 `hard_due` → `maximum timeout`。
- ⚠️ 推论：**没有 progress token 的请求，idle timeout 就是它的寿命上限**。实测 HTTP 请求无 token、500 ms 时即返回 `{'action': 'close_response_stream', 'requestId': 10, 'reason': 'idle timeout'}`。不发 progress 的长工具需要更大的 idle 值。

### 3.5 取消信号的生成与接收

```python
    def client_cancel_signal(self, request_id, *, reason):
        request = self.requests[request_id]
        if request.transport == STDIO:
            return {
                "jsonrpc": "2.0",
                "method": "notifications/cancelled",
                "params": {"requestId": request_id, "reason": reason},
            }
        return {
            "action": "close_response_stream",
            "requestId": request_id,
            "reason": reason,
        }
```

- stdio：一条标准 JSON-RPC **通知**（没有 `id` 字段）。
- HTTP：不是 JSON-RPC 消息，而是一个"动作描述"——关闭该请求的响应流。测试断言它**没有** `method` 字段，防止有人把取消 POST 出去。

```python
    def receive_stdio_cancellation(self, notification):
        if notification.get("method") != "notifications/cancelled":
            return None
        params = notification.get("params")
        if not isinstance(params, dict):
            return None
        request_id = params.get("requestId")
        if type(request_id) not in (int, str):
            return None
        request = self.requests.get(request_id)
        if request is None or request.transport != STDIO or request.state != IN_PROGRESS:
            return None
        request.state = CANCELLED
        ...
        return None
```

- **每条路径都返回 `None`**：通知是 fire-and-forget，服务端绝不回 JSON-RPC 响应。
- 防御层层递进：方法名不对、`params` 不是 dict、`requestId` 类型不对（包括 `True`、`[]`、`{}`）、未知 id、不是 stdio 请求、已经是终态——全部**静默忽略**。讲义："Turning those races into new errors would create more races."
- `reason` 只有是字符串才保存，否则记为 `None`。
- 这里也用 `type()` 先过滤再 `.get()`，避免不可哈希的 id 抛 `TypeError`。

`close_http_stream` 是 HTTP 侧的对应物：只有请求存在、是 HTTP、且仍在进行时才改为 `CANCELLED` 并记一条事件；其余情况同样静默。

### 3.6 `complete`：竞争的另一半

```python
        request = self.requests[request_id]
        if request.state == CANCELLED:
            return None
        if request.state == COMPLETED:
            return request.response
        response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        request.state = COMPLETED
        request.response = response
        self.events.append(response)
        return response
```

- **取消先到**：返回 `None`，相当于"worker 跑完了，但服务端抑制响应"。
- **重复完成**：返回第一次的响应，新的 `result` 被丢弃（测试 `test_completed_subscription_rejects_late_server_cancellation` 中第二次 `complete` 传了 `"changed": True`，返回的仍是原响应）——终态不可改写，`complete` 本身是幂等的。
- **完成先到**：之后再收到取消，`receive_stdio_cancellation` 看到 `state != IN_PROGRESS` 直接忽略。

`server_cancel_subscription` 把讲义"服务端发起的取消很窄"写成硬约束：只有 stdio + `subscriptions/listen` + 仍在进行时才允许，否则抛 `ReliabilityError`。⚠️ 小不一致：它把状态改成 `CANCELLED`，但既不设置 `cancel_reason`，也不往 `self.events` 里记事件，与另外两条取消路径不同。

### 3.7 `classify_retry`：重试矩阵

```python
    if not side_effect:
        return RetryDecision("safe", "operation is read-only by application contract")
    if idempotency_key:
        return RetryDecision("conditional", "retry only with the same idempotency key and identical arguments")
    return RetryDecision("unsafe", "a new JSON-RPC id cannot deduplicate a side effect")
```

- 输入是"应用契约上有没有副作用"，**不是**工具注解 `readOnlyHint`——讲义强调注解只是不可信提示。
- `if idempotency_key:` 用真值判断，空字符串 `""` 也被视为"没有键"→ unsafe，这是合理的。
- 它是纯函数，没有和 `MutationLedger` 连起来：ledger 并不会拒绝无键调用，只是每次都执行。

### 3.8 `MutationLedger`：原子幂等边界

**建表与连接**：

```python
        self._connection = sqlite3.connect(
            self.database_path,
            isolation_level=None,
            check_same_thread=False,
            timeout=5.0,
        )
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._connection.execute("PRAGMA journal_mode = WAL")
```

- `isolation_level=None`：关闭 Python `sqlite3` 模块的"隐式开事务"，改为由代码显式写 `BEGIN IMMEDIATE` / `COMMIT` / `ROLLBACK`，事务边界一目了然。
- `check_same_thread=False`：允许在别的线程里用这个连接（并发测试需要），线程安全由 `self._lock`（`RLock`）保证。
- `busy_timeout = 5000`：另一个连接持有写锁时最多等 5 秒，而不是立刻报 `database is locked`。
- WAL 模式：读写可以并发，写者之间仍然串行。
- 两张表：`mutation_counter`（`CHECK (singleton = 1)` 保证只有一行，模拟"业务副作用"）和 `idempotency_records`（`idempotency_key` 主键 + 指纹 + 结果 JSON）。

**指纹**：

```python
    @staticmethod
    def _fingerprint(account: str, cents: int) -> str:
        payload = json.dumps({"account": account, "cents": cents}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

- 规范化 JSON（排序键、紧凑分隔符）再 SHA-256，保证同样的参数总是得到同样的指纹。
- ⚠️ 只包含 `account` 和 `cents`，**不含操作名和租户**；而 `idempotency_records` 是一张通用表，以后加入第二种操作（讲义练习的 `reserve_inventory`）时 key 会互相串（见测验 Q11）。
- ⚠️ `1200` 和 `1200.0` 序列化不同（`"cents":1200` vs `"cents":1200.0`），实测同键传 `1200.0` 会被判为"参数不同"而报错。

**核心事务**：

```python
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                if idempotency_key is not None:
                    stored = ...SELECT fingerprint, result_json ... WHERE idempotency_key = ?
                    if stored is not None:
                        stored_fingerprint, stored_json = stored
                        if stored_fingerprint != fingerprint:
                            raise ReliabilityError("idempotency key was reused with different arguments")
                        self._connection.execute("COMMIT")
                        return json.loads(stored_json)

                execution_number = int(row[0]) + 1
                result = {"receipt": f"charge-{execution_number:03d}", "rpcId": rpc_id, ...}
                ...UPDATE mutation_counter SET executions = ?
                if idempotency_key is not None:
                    ...INSERT INTO idempotency_records(...)
                self._connection.execute("COMMIT")
                return json.loads(result_json)
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise
```

- `BEGIN IMMEDIATE` **在事务一开始就拿写锁**（RESERVED 锁）。普通的 `BEGIN`（DEFERRED）要到第一次写入才拿锁，两个连接可能都先读到"key 不存在"，然后都去写——这正是讲义说的 check-then-act 竞态。IMMEDIATE 让第二个连接在 `BEGIN` 处就等待，等它拿到锁时第一个已经提交，它会读到记录并走"重放"分支。
- 查键、读计数、写计数、写记录在**同一个事务**里：要么全部生效，要么全部回滚。崩溃发生在中间时不会出现"副作用发生了但没有记录"的模糊状态（在本模拟器里副作用就是计数器）。
- **同键不同参数**：抛错 → `except` 分支回滚 → 重新抛出。
- **返回防御性拷贝**：两条成功路径都 `json.loads(...)`，每次返回一个全新的 dict，调用方改返回值不会影响存储（测试 `test_mutating_returned_result_does_not_change_stored_result`）。
- 结果里的 `rpcId` 是**第一次**执行时的 id，重放时原样返回（实测第二次传 `rpc_id=42`，返回的 `rpcId` 仍是 41）。
- `except BaseException`（而不是 `Exception`）：连 `KeyboardInterrupt` 也要回滚，避免把连接留在打开的事务里。
- 无键调用：跳过查键和写记录，每次都执行（`receipt` 递增），这正是"新的 JSON-RPC id 不能去重"的反面演示。
- ⚠️ 只检查 `cents <= 0`，没有类型检查：实测 `charge("acct-7", True, ...)` 会成功，结果 `cents: True`。
- ⚠️ 讲义明确提醒：这里的"副作用"只是同一事务里的计数器。真实的支付/部署/外部 API 不会因为写了本地表就变原子，需要共享持久数据库事务、transactional outbox，或上游支持同一个幂等键。

`executions` 是一个 `@property`，读计数器；`__enter__/__exit__` 让 ledger 可以用 `with` 自动关闭。

### 3.9 `DurableTaskService`：ack 不是终态

```python
    def cancel(self, task_id):
        task = self.tasks[task_id]
        if task.status == "working":
            task.cancel_requested = True
        return {"resultType": "complete"}

    def worker_checkpoint(self, task_id):
        task = self.tasks[task_id]
        if task.status == "working" and task.cancel_requested:
            task.status = "cancelled"
        return task

    def finish(self, task_id):
        task = self.tasks[task_id]
        if task.status == "working":
            task.status = "completed"
        return task
```

- `cancel` 总是返回 `{"resultType": "complete"}`——这只是"请求处理完成"，不是"Task 已取消"。
- 只有 worker 走到 checkpoint 才会变成 `cancelled`；如果 worker 先调了 `finish`，Task 就是 `completed`（实测：`cancel` → `finish` → `checkpoint` 后状态为 `completed`，`cancel_requested=True` 但无效）。
- 对已终态的 Task 再 `cancel` 仍返回同样的 ack，不报错。

### 3.10 `BoundedSseBuffer`：可丢与不可丢

```python
    def push_progress(self, token, value):
        if self.events and self.events[-1].get("kind") == "progress":
            if self.events[-1].get("token") == token:
                self.events[-1] = {"kind": "progress", "token": token, "value": value}
                self.dropped_progress += 1
                self.needs_refetch = True
                return
        if len(self.events) >= self.capacity and not self._drop_oldest_progress():
            self.dropped_progress += 1
            self.needs_refetch = True
            return
        self.events.append({"kind": "progress", "token": token, "value": value})

    def push_final(self, response):
        while len(self.events) >= self.capacity:
            if not self._drop_oldest_progress():
                raise ReliabilityError("buffer cannot discard a final response")
        self.events.append({"kind": "final", "response": response})
```

对应讲义的五条策略：

| 讲义策略 | 代码位置 |
|---------|---------|
| 1. 合并相邻同 token progress | `push_progress` 第一个 `if`：只看**队尾** |
| 2. 满了丢最旧 progress | `_drop_oldest_progress()`：从头找第一个 `kind == "progress"` 删除 |
| 3. 标记需要 refetch | 每次合并/丢弃都 `needs_refetch = True` |
| 4. 保留最终响应 | `push_final` 循环丢 progress 腾位置 |
| 5. 保留 final 需要丢另一个 final 时拒绝 | 没有 progress 可丢时 `raise ReliabilityError` |

- 满了且队列里全是 final 时，新来的 progress 被直接丢弃（计数 +1），不会挤掉 final。
- `capacity < 2` 被拒绝：至少要能同时放一个 progress 和一个 final。
- ⚠️ 合并时最新值仍在队列里，信息没有真正丢失，但代码照样计入 `dropped_progress` 并要求 refetch，偏保守。
- ⚠️ 没有"该 token 已经 final"的检查：实测 `push_progress("a",1)` → `push_final` → `push_progress("a",2)` 得到 `[progress, final, progress]`，违反"完成后不再发通知"。
- ⚠️ 合并只看相邻：多个 token 交替时永远不合并，只能靠丢最旧。
- `drain()` 用 `list(self.events)` 先复制再 `clear()`，返回的列表不会因清空而变空。

### 3.11 恢复辅助函数

```python
def sse_response_headers():
    return {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

def sse_keepalive():
    return ":\r\n"
```

- `X-Accel-Buffering: no` 是 Nginx 认识的头，告诉代理不要缓冲这个响应；讲义说 2026 版 Streamable HTTP 规范推荐它。
- `":\r\n"` 是一行 SSE 注释（以冒号开头），客户端解析器会忽略它；目的只是让中间设备看到流量。它在 coordinator 里**不会**更新 `last_activity_ms`，正符合"保活不是 progress"。

```python
def reconnect_plan(previous_subscription_id, affected_resources, *, unsafe_mutation_was_in_flight):
    return {
        "newSubscriptionId": f"{previous_subscription_id}-retry",
        "sendLastEventId": False,
        "refetch": sorted(set(affected_resources)),
        "retryUnsafeMutation": not unsafe_mutation_was_in_flight,
    }
```

- `sorted(set(...))` 去重并排序，得到确定的 refetch 列表（测试中 `["notes://b","notes://a","notes://a"]` → `["notes://a","notes://b"]`）。
- ⚠️ `retryUnsafeMutation = not unsafe_mutation_was_in_flight`：没有不安全变更在途时它是 `True`，语义空洞且容易误读成"允许重放不安全变更"，应恒为 `False`，另用一个字段表示"需要先对账"。
- ⚠️ 新 id 是 `旧 id + "-retry"`，多次重连会变成 `-retry-retry`；整数 id 会变成字符串。讲义第 2 步"恢复订阅过滤器"在 plan 里没有体现。

```python
def retry_delay_ms(client_id, attempt):
    ceiling = min(8_000, 250 * (2**attempt))
    floor = max(1, ceiling // 2)
    digest = hashlib.sha256(f"{client_id}:{attempt}".encode("utf-8")).digest()
    jitter = int.from_bytes(digest[:4], "big") % max(1, ceiling - floor + 1)
    return floor + jitter
```

- 上限 `ceiling` 从 250 ms 起每次翻倍，8000 ms 封顶（attempt ≥ 5）；返回值落在 `[ceiling//2, ceiling]`，属于 "equal jitter"。
- jitter 来自 `sha256(client_id:attempt)` 的前 4 字节，同样输入总得到同样输出——测试可重复；不同客户端分散开。
- `2**attempt` 在 Python 里是任意精度整数，attempt 很大也不会溢出，`min` 会把它截到 8000。

### 3.12 `main()`：演示脚本

依次执行：

1. 请求 7（stdio、有 token）：100 ms 发 progress，600 ms 时 idle 超时（600 − 100 = 500 ≥ 500）→ 生成 stdio 取消 → 服务端接收 → `complete` 返回 `None`。
2. 请求 8（stdio、无 token）：先 `complete`，再收到"late user action"取消 → 被忽略，响应保留。
3. 临时目录里的 ledger：同键 `checkout-7` 扣款两次（rpc_id 41、42）。
4. `BoundedSseBuffer(3)`：同 token 6 条 progress，再 final。
5. Task：`cancel` → 读状态 → `worker_checkpoint` → 读状态。

`tempfile.TemporaryDirectory()` 保证 SQLite 文件（以及 WAL 的 `-wal`/`-shm` 文件）在演示结束后被清理。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 时间作为参数传入（`now_ms`） | 竞争顺序完全可控，测试确定 | 真实系统需要单调时钟和定时器；超时要主动触发而不是等调用者来问 |
| 单一终态 + "非进行中一律忽略" | 任意事件顺序都有确定结果 | 终态记录永不清理，生产需按 TTL 回收 |
| 无效取消静默忽略 | 讲义：把竞争变成新错误会制造更多竞争 | 需要日志/指标记录被忽略的取消，便于排查 |
| HTTP 取消表示为"动作"而非消息 | 强调"关闭流就是信号"，杜绝 POST 取消 | 真实服务端要从 ASGI/HTTP 框架感知断开 |
| SQLite + `BEGIN IMMEDIATE` | 单文件、标准库即可演示真正的跨连接原子性 | 多副本需要共享数据库（如 Postgres 唯一约束 + 事务）或上游幂等 |
| 结果存 JSON、读出时重建 | 天然的防御性拷贝，跨重启一致 | 结果很大时有序列化成本 |
| 指纹只含 account、cents | 演示足够 | 应包含操作名、租户、全部业务参数，并统一数值类型 |
| 合并也标记 refetch | 宁可多拉一次也不漏 | 可能产生不必要的 refetch 流量 |
| 缓冲不知道"已 final" | 组件保持简单 | 应在 token 完成后拒绝 progress，或由上层 coordinator 保证 |
| 确定性 jitter（哈希） | 测试可复现 | 生产用运行时随机数，或保证 client_id 唯一 |
| 不实现 progress 限速 | 篇幅 | 生产要按时间窗口限速，避免淹没传输 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可以在类内部引用自身类型（如 `-> MutationLedger`） |
| 联合类型 `X \| Y` | `request_id: int \| str`、`dict[str, Any] \| None` | Python 3.10+ 的类型联合写法；`None` 表示可选 |
| `@dataclass` | `InFlightRequest`、`DurableTask` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `__post_init__` | `self.last_activity_ms = self.started_at_ms` | dataclass 构造完成后的钩子，用于派生字段 |
| `@dataclass(frozen=True)` | `RetryDecision` | 不可变对象，赋值会抛 `FrozenInstanceError` |
| 仅限关键字参数 `*` | `def start(self, request_id, operation, *, transport, ...)` | `*` 之后的参数必须用 `name=value` 传，防止传错位置 |
| `type(x) in (...)` vs `isinstance` | `type(request_id) not in (int, str)` | 精确类型比较，排除 `bool` 和子类 |
| 集合字面量做成员判断 | `transport not in {STDIO, STREAMABLE_HTTP}` | 集合查找 O(1) |
| 条件表达式 | `"maximum timeout" if hard_due else "idle timeout"` | 三元运算 |
| `dict.get` | `notification.get("params")` | 键不存在返回 `None`，不抛 `KeyError` |
| 自定义异常 | `class ReliabilityError(ValueError)` | 继承内置异常，带文档字符串 |
| 上下文管理器协议 | `__enter__` / `__exit__`，`with MutationLedger(...) as ledger` | 离开 `with` 块自动 `close()` |
| `with lock:` | `with self._lock:` | 自动加锁/释放；`RLock` 允许同一线程重入 |
| `@property` | `def executions(self)` | 像属性一样读取：`ledger.executions` |
| `@staticmethod` | `_fingerprint` | 不需要 `self` 的方法 |
| `try / except BaseException / raise` | `charge()` 中回滚后重新抛出 | 清理后保持原异常；`BaseException` 也覆盖 `KeyboardInterrupt` |
| 元组解包 | `stored_fingerprint, stored_json = stored` | 一次拆出查询行的两列 |
| SQL 参数占位符 | `"... WHERE idempotency_key = ?", (idempotency_key,)` | 防 SQL 注入；单元素元组要带逗号 |
| 三引号多行字符串 | `"""CREATE TABLE IF NOT EXISTS ..."""` | 写多行 SQL |
| f-string 格式符 | `f"charge-{execution_number:03d}"` | 补零到 3 位：`charge-001` |
| 数字下划线 | `8_000`、`2_000` | 仅为可读性，等同 `8000` |
| `json.dumps(sort_keys=True, separators=(",", ":"))` | 指纹与结果序列化 | 规范化输出，保证同样内容得到同样字符串 |
| `hashlib.sha256(...).hexdigest()` / `.digest()` | 指纹、jitter | 十六进制字符串 / 原始字节 |
| `int.from_bytes(b, "big")` | `int.from_bytes(digest[:4], "big")` | 把 4 个字节按大端解释成整数 |
| `enumerate` + `del list[i]` | `_drop_oldest_progress` | 找到后立刻 `return`，避免边遍历边删除出错 |
| `sorted(set(...))` | `reconnect_plan` | 去重并排序 |
| `any(...)` 生成器表达式 | `any(event["kind"] == "final" for event in buffer.events)` | 只要有一个为真即返回 `True` |
| `tempfile.TemporaryDirectory()` | `main()` | 临时目录，`with` 结束自动删除 |
| `pathlib.Path` 的 `/` | `Path(directory) / "mutations.sqlite3"` | 拼接路径 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，`python3 main.py`）：

```text
cancel before completion returns: None
complete before cancel keeps response: True
idempotent receipts equal: True
mutation executions: 1
buffer size and dropped progress: 2 5
final response preserved: True
task cancel acknowledgement: complete
task status before and after worker checkpoint: working cancelled
```

逐行解读：

- **`cancel before completion returns: None`**：请求 7 在 100 ms 有 progress，600 ms 时 `600 − 100 = 500 ≥ 500` 触发 **idle timeout**（不是 maximum），生成的信号是 `{'method': 'notifications/cancelled', 'params': {'requestId': 7, 'reason': 'idle timeout'}}`；服务端接收后状态为 `cancelled`，worker 随后 `complete` 被抑制，返回 `None`。
- **`complete before cancel keeps response: True`**：请求 8 先完成，迟到的取消因为 `state != IN_PROGRESS` 被忽略，响应保留。
- **`idempotent receipts equal: True` / `mutation executions: 1`**：同键同参的第二次调用（rpc_id 42）走重放分支，receipt 都是 `charge-001`，计数器只加了一次。
- **`buffer size and dropped progress: 2 5`**：6 条同 token progress 合并成 1 条（值 5），合并 5 次计入 5；final 进来时还有空位，最终 2 条。注意这次运行**没有**触发"丢最旧"路径。
- **`final response preserved: True`**：队列里有 `kind == "final"` 的事件。
- **`task cancel acknowledgement: complete`** / **`working cancelled`**：ack 后 Task 仍是 `working`，checkpoint 之后才是 `cancelled`。

测试运行（`python3 -m unittest discover tests -v`）：**23 个测试全部通过，耗时约 0.04 秒**（见第 9 节）。

---

## 7. 动手改一改

1. **（入门）Interactive Lab**：按讲义四个场景（A 先取消后完成、B 先完成后取消、C 一直有 progress 直到最大期限、D 用 HTTP 关闭流）写一个脚本，打印每个场景的终态、是否有最终响应、线上的取消信号、客户端该忽略什么；再把 D 改成 stdio，观察信号如何变化。
2. **（入门）修 `reconnect_plan`**：把 `retryUnsafeMutation` 改为恒 `False`，新增 `reconcileBeforeRetry`、`restoreFilter` 和 `attempt` 参数（参考测验 Q9），并补测试。
3. **（进阶）给 `BoundedSseBuffer` 加"完成后拒收 progress"**，并补两个测试：多 token 交替触发丢最旧；容量被 final 占满时 `push_final` 抛错。
4. **（进阶）progress 限速**：给 `RequestCoordinator.progress` 加一个 `min_interval_ms`，间隔太短的 progress 只更新 `last_progress` 但不产生通知（想一想：被限速的 progress 该不该重置 idle 时钟？）。
5. **（进阶）Practice Lab**：实现 `reserve_inventory`（指纹含操作名、租户），完成讲义 10 条要求，包括两个连接 + barrier 的并发测试和重开对账（参考测验 Q11）。
6. **（挑战）去掉 `BEGIN IMMEDIATE`**：改成普通 `BEGIN`（DEFERRED），重复跑 `test_concurrent_same_key_commits_one_mutation` 多次，观察会发生什么（可能出现 `database is locked` 或唯一约束冲突），并解释为什么 IMMEDIATE 能把竞态变成排队。

---

## 8. 常见坑

- **HTTP 上 POST `notifications/cancelled`**：Streamable HTTP 的取消信号是关闭流，POST 会让两端对请求生命周期的理解不一致。
- **给取消通知回响应**：通知没有 `id`，回响应是协议错误；本代码所有接收路径都返回 `None`。
- **用 `isinstance(x, int)` 校验 id**：`True` 会混进来；不可哈希的值会在字典查找时抛 `TypeError`。
- **progress 重置所有期限**：只能重置 idle；maximum 从请求开始算，永不重置。
- **以为没有 progress 就没有 idle 超时**：恰恰相反，不发 progress 的请求会在 idle 期限被取消。
- **把新的 JSON-RPC id 当去重**：测试证明两次 rpc_id 不同、无键的扣款会执行两次。
- **"查键 → 执行 → 存结果"分三步**：并发下两个 worker 都执行；必须放进一个原子事务。
- **直接返回 ledger 内部对象**：调用方修改会污染后续重放；要返回拷贝。
- **指纹不含操作名/租户、数值类型不统一**：`1200` 和 `1200.0` 指纹不同。
- **合并 progress 时把 final 也合并/丢掉**：final 永远不可丢。
- **断线后用 `Last-Event-ID` 续传**：2026-07-28 版不支持，要新请求 + refetch。
- **所有客户端共用同一个 jitter 种子**：确定性 jitter 会让所有人同时重连。
- **把 `tasks/cancel` 的 ack 当"已停止"**：要轮询到终态。

---

## 9. 测试在验证什么

测试文件 `tests/test_main.py` 用 `importlib.util.spec_from_file_location` 按路径加载 `main.py`（模块名 `lesson29_main`），这样无论从哪个目录运行都能导入，也不会和其他小节的 `main` 冲突。`setUp` 为每个测试新建一个 `RequestCoordinator` 和一个临时目录（`addCleanup` 负责删除）。

运行：

```bash
cd phases/13-tools-and-protocols/29-mcp-reliability-cancellation-and-flow-control/code
python3 -m unittest discover tests -v
```

实际结果：`Ran 23 tests in 0.036s — OK`。

| 测试 | 验证的性质 |
|------|-----------|
| `test_stdio_cancellation_is_notification_and_suppresses_response` | stdio 信号是 `notifications/cancelled`、接收返回 `None`、之后 `complete` 被抑制 |
| `test_http_cancellation_closes_stream_without_notification` | HTTP 信号是 `close_response_stream` 且没有 `method`；关闭后 `complete` 返回 `None` |
| `test_completion_wins_race_and_late_cancellation_is_ignored` | 完成先到时状态保持 `completed`，响应 id 正确 |
| `test_unknown_and_malformed_cancellation_are_ignored` | 未知 id、缺 `params` 的通知都被忽略，请求仍在进行 |
| `test_unhashable_and_boolean_cancellation_ids_are_ignored` | `[]`、`{}`、`True` 作为 `requestId` 不会抛错也不会误取消（`subTest` 逐个检查） |
| `test_start_rejects_noncanonical_request_ids_before_lookup` | `True`、`[]`、`{}`、`1.5`、`None`、int 子类都被拒，且字典里没有残留 |
| `test_start_rejects_noncanonical_progress_tokens` | progress token 同样只接受精确的 int / str |
| `test_progress_resets_idle_timeout_but_not_maximum_timeout` | 讲义的 400/800/1200 例子：1500 ms 为 `None`，2000 ms 为 `maximum timeout` |
| `test_idle_timeout_cancels_when_progress_stops` | 100 ms 后不再有 progress，600 ms 触发 `idle timeout` |
| `test_progress_must_increase_and_stops_after_completion` | 相同值抛错；完成后 progress 返回 `None` |
| `test_new_json_rpc_id_does_not_deduplicate_mutation` | 无键两次扣款得到不同 receipt，`executions == 2` |
| `test_idempotency_key_deduplicates_identical_arguments` | 同键同参结果相等但不是同一对象，执行 1 次；同键改金额抛错 |
| `test_concurrent_same_key_commits_one_mutation` | 两个独立 ledger 连接 + `threading.Barrier(2)` 同时扣款，结果相同、只执行 1 次 |
| `test_mutating_returned_result_does_not_change_stored_result` | 篡改第一次返回值后重放，拿到的仍是 `acct` / `charge-001` |
| `test_committed_record_survives_ledger_reopen` | 关闭再打开同一文件，重放结果与原结果相同，执行仍为 1 |
| `test_retry_matrix_distinguishes_safe_conditional_and_unsafe` | 三种分类各一例 |
| `test_bounded_buffer_coalesces_progress_and_preserves_final` | 20 条同 token progress + final：长度 ≤ 3、有丢弃、需要 refetch、队尾是 final |
| `test_reconnect_refetches_without_last_event_id_or_unsafe_replay` | 新 id 为 `listen-1-retry`、不发 `Last-Event-ID`、不重放、refetch 去重排序 |
| `test_proxy_headers_and_keepalive_are_explicit` | SSE 头与 `":\r\n"` 保活 |
| `test_retry_backoff_is_bounded_and_spread_by_client` | attempt 4 时 4 个客户端延迟不全相同，且都在 [2000, 4000] |
| `test_task_cancellation_acknowledgement_is_not_final_status` | ack 后仍 `working`，checkpoint 后 `cancelled` |
| `test_server_cancellation_is_reserved_for_stdio_subscription` | stdio `subscriptions/listen` 可由服务端取消；普通 `tools/call` 抛错 |
| `test_completed_subscription_rejects_late_server_cancellation` | 已完成的订阅不能再被服务端取消；再次 `complete` 返回原响应 |

测试覆盖的空白（可作为练习补上）：

- `BoundedSseBuffer` 的"丢最旧 progress"和"final 满了抛错"两条路径没有被测试覆盖（现有测试只用一个 token，全部走合并分支）。
- `reconnect_plan` 在 `unsafe_mutation_was_in_flight=False` 时返回 `retryUnsafeMutation=True` 的语义问题没有测试。
- `DurableTaskService.finish` 抢在 checkpoint 之前完成（"完成赢得竞争"）的场景没有测试。
- progress 限速未实现，也就没有测试。
