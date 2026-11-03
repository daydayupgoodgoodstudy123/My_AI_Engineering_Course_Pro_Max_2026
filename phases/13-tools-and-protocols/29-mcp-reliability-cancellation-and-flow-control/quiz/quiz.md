# 测验 · MCP 可靠性、取消与流量控制（MCP Reliability, Cancellation, and Flow Control）

> **阶段 13 · 工具与协议 · 第 29 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义是机器翻译，质量很差（例如把 race 译成"种族"、mutation 译成"突变"、ledger 译成"分类账"），遇到看不懂的句子请直接读英文版。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 取消信号随传输而不同 | stdio：客户端发 `notifications/cancelled`（fire-and-forget，服务端不回 JSON-RPC 响应）；Streamable HTTP：关闭该请求的响应流，**不要** POST 取消通知 |
| 2 | 服务端发起的取消很窄 | 服务端发 `notifications/cancelled` 只用于在 stdio 上终止 `subscriptions/listen`，不能用来取消任意客户端请求 |
| 3 | 取消是一场竞争（race） | "取消先到"→ 抑制最终响应；"完成先到"→ 保留响应、忽略迟到的取消；两端都无法证明对方先看到哪个事件，所以每个请求只能有**一个终态** |
| 4 | 两个时钟 | idle timeout（距上次有效活动）可以被 progress 重置；maximum timeout（距请求开始）**永不重置**；progress token 存在 ≠ 无限超时 |
| 5 | 请求取消 ≠ `tasks/cancel` | `tasks/cancel` 是普通 MCP 请求，成功只代表"服务端确认了取消意图"；Task 可能继续 `working`，直到 worker 在 checkpoint 看到标记，也可能先完成 |
| 6 | JSON-RPC id 不是幂等键 | id 只关联请求和响应；换新 id 重试一次扣款就会执行两次。幂等需要应用层 idempotency key + 参数指纹 + 已提交结果 |
| 7 | 原子、持久的 ledger 边界 | "查键 → 执行 → 存结果"分三步是不安全的；用 `BEGIN IMMEDIATE` 把查键、副作用、计数器、结果写入放进同一个 SQLite 事务；返回值从存储的 JSON 重建（防御性拷贝） |
| 8 | 重试矩阵 | Safe（只读）：可换新 id 重试；Conditional（有持久幂等键）：同键同参数重试；Unsafe（无业务去重）：不自动重试，先对账（reconcile）。`readOnlyHint`/`idempotentHint` 只是不可信提示 |
| 9 | 背压（backpressure） | 有界队列；progress 可替换（合并 / 丢最旧）并标记 `needs_refetch`；最终响应不可丢；SSE 加 `X-Accel-Buffering: no`，安静的长流发 `:` 注释保活，但保活不算 progress |
| 10 | 重连就是重新拉取 | 2026-07-28 版 Streamable HTTP 不支持 `Last-Event-ID` 续传；重连要新开 listen 请求、恢复过滤器、按权威方法 refetch；用带上限的指数退避 + jitter 防止重连风暴 |

### 核心技能（能动手做到）

- [ ] 给定传输方式（stdio / Streamable HTTP），写出正确的客户端取消动作，并说明服务端收到后该做什么、不该做什么
- [ ] 画出"取消先到 / 完成先到"两种事件顺序下的终态、是否有最终响应、哪一方该忽略什么
- [ ] 给定 idle / maximum 超时和一串 progress 时间点，推算 `timeout_signal` 在某个时刻返回什么
- [ ] 用 SQLite `BEGIN IMMEDIATE` 实现带参数指纹的幂等 ledger，并用"两个连接 + barrier"的并发测试证明只执行一次
- [ ] 对任意一个工具调用做重试分类（safe / conditional / unsafe），并说出依据
- [ ] 推演 `BoundedSseBuffer` 在给定容量和事件序列下的队列内容与 `dropped_progress`
- [ ] 计算 `retry_delay_ms` 每个 attempt 的取值区间，并解释 jitter 为什么能防止重连风暴

---

## 二、基础自测（选择题）

**Q1.** 客户端通过 **stdio** 调用一个耗时工具，用户点了"取消"。正确的做法是：

- A. 调用 `tasks/cancel`，参数是该请求的 JSON-RPC id
- B. 关闭该请求的 SSE 响应流
- C. 发送 `notifications/cancelled`（带 `requestId` 和可选 `reason`），不期待任何 JSON-RPC 响应
- D. 发送 `notifications/cancelled`，并等待服务端返回 `{"result": "cancelled"}` 确认

**Q2.** 客户端通过 **Streamable HTTP** 调用同一个工具，要取消它。按讲义（MCP 2026-07-28），正确做法是：

- A. 关闭这个请求对应的 HTTP / SSE 响应流
- B. 向 MCP 端点再 POST 一条 `notifications/cancelled`
- C. 等服务端主动发 `notifications/cancelled` 过来
- D. 带一个空的 `Last-Event-ID` 重新发起请求

**Q3.** 用代码中的 `RequestCoordinator`：stdio 请求在 0 ms 开始，`idle_timeout_ms=500`、`max_timeout_ms=2000`，有 progress token。progress 依次在 400、800、1200、1600、1999 ms 到达（值 1～5）。在 `now_ms=2000` 调用 `timeout_signal`，返回：

- A. `None`，因为最近一次 progress 只过去了 1 ms
- B. `{"action": "close_response_stream", ..., "reason": "maximum timeout"}`
- C. `notifications/cancelled`，`reason` 为 `"idle timeout"`
- D. `notifications/cancelled`，`reason` 为 `"maximum timeout"`

**Q4.** 一个 Streamable HTTP 请求**没有** progress token，`idle_timeout_ms=500`、`max_timeout_ms=2000`，服务端安静地工作了 500 ms。此时 `timeout_signal(now_ms=500)` 的结果是：

- A. `None`，因为没有 progress token 就不受 idle timeout 约束
- B. `{"action": "close_response_stream", "requestId": 10, "reason": "idle timeout"}`
- C. `None`，要等到 2000 ms 才会触发
- D. 抛出 `ReliabilityError`，因为没有 token 的请求不能计算超时

**Q5.** 客户端对一个 durable Task 调用 `tasks/cancel`，收到 `{"resultType": "complete"}`。这能说明：

- A. 服务端已经接受了取消意图；Task 可能仍是 `working`，甚至可能最终变成 `completed`
- B. worker 已经停止，Task 状态已经是 `cancelled`
- C. Task 的持久结果已被删除
- D. Task 一定会在下一次轮询时变为 `cancelled`

**Q6.** 一个 `charge_account` 工具没有任何业务去重，响应在网络上丢了。按讲义的重试矩阵，客户端应该：

- A. 立即用同一个 JSON-RPC id 重试，服务端会自动去重
- B. 只要工具描述里有 `idempotentHint: true` 就可以自动重试
- C. 换一个新的 JSON-RPC id 重试，因为新 id 能让服务端区分两次调用
- D. 不自动重试，先对账（reconcile）确认那次扣款是否已经发生

**Q7.** 运行 `main.py` 时，`BoundedSseBuffer(3)` 先收到同一 token `"progress-9"` 的 6 条 progress（值 0～5），再收到一条最终响应。打印的 `buffer size and dropped progress` 是：

- A. `3 3`
- B. `2 5`
- C. `1 6`
- D. `3 4`

**Q8.** 在 `MutationLedger` 上依次执行：

```python
first = ledger.charge("acct-7", 1200, rpc_id=41, idempotency_key="checkout-7")
second = ledger.charge("acct-7", 1200, rpc_id=42, idempotency_key="checkout-7")
```

下列说法正确的是：

- A. `second["rpcId"] == 42`，`ledger.executions == 2`
- B. `first is second` 为 `True`，因为返回的是同一份缓存结果
- C. `second == first` 且 `second["rpcId"] == 41`，`ledger.executions == 1`
- D. 第二次调用抛出 `ReliabilityError`，因为 rpc_id 变了

---

## 三、动手 / 代码题

**Q9.** 阅读 `reconnect_plan`：

```python
def reconnect_plan(
    previous_subscription_id: int | str,
    affected_resources: list[str],
    *,
    unsafe_mutation_was_in_flight: bool,
) -> dict[str, Any]:
    return {
        "newSubscriptionId": f"{previous_subscription_id}-retry",
        "sendLastEventId": False,
        "refetch": sorted(set(affected_resources)),
        "retryUnsafeMutation": not unsafe_mutation_was_in_flight,
    }
```

1. 当 `unsafe_mutation_was_in_flight=False` 时，返回的 `retryUnsafeMutation` 是什么？这个字段的语义有什么问题？
2. 同一个订阅连续断开两次、三次，`newSubscriptionId` 会变成什么？会有什么隐患？
3. 讲义的重连步骤有 5 步，这个函数覆盖了哪几步、缺了哪几步？
4. 给出一个改进版本。

**Q10.** `BoundedSseBuffer` 的推演与改进。

1. 容量 3，依次 `push_progress("a",0)`、`("b",1)`、`("a",2)`、`("b",3)`，再 `push_final({"id":1})`。写出每一步后的 `events` 与最终的 `dropped_progress`。
2. 下面这段会得到什么？这违反了讲义里的哪条规则？

```python
b = BoundedSseBuffer(3)
b.push_progress("a", 1)
b.push_final({"id": 1})
b.push_progress("a", 2)
print(b.events)
```

3. 在"同 token 6 条 progress"的场景里，`needs_refetch` 是 `True`，但队列里留下的恰好是最新值 5。你认为"合并（coalesce）"该不该触发 refetch？为什么？
4. 现有测试 `test_bounded_buffer_coalesces_progress_and_preserves_final` 覆盖了"丢最旧 progress"那条路径吗？

**Q11.** 完成讲义 Practice Lab 的核心部分：给 `MutationLedger` 增加 `reserve_inventory(tenant, sku, quantity, *, rpc_id, idempotency_key)`。要求：

- 指纹绑定 SKU、数量、租户和**操作名**；
- 没有 key 时拒绝执行（禁止自动重试的前提是"根本不接受无键调用"或"标记为 unsafe"，这里选前者）；
- 同键同参数返回第一次的预留；同键改数量报错且不新增预留；
- 关闭重开 ledger 后能按 key 对账（reconcile）。

写出实现，并说明为什么指纹里要包含操作名。

**Q12.** 手算 `retry_delay_ms`：

```python
def retry_delay_ms(client_id: str, attempt: int) -> int:
    ceiling = min(8_000, 250 * (2**attempt))
    floor = max(1, ceiling // 2)
    digest = hashlib.sha256(f"{client_id}:{attempt}".encode("utf-8")).digest()
    jitter = int.from_bytes(digest[:4], "big") % max(1, ceiling - floor + 1)
    return floor + jitter
```

1. 写出 attempt = 0、1、4、5、10 时返回值的取值区间。
2. 讲义写 "attempt 0: up to 250 ms"，代码实际是哪种 jitter 策略？和 "full jitter" 有什么区别？
3. 如果 1 万个客户端都用同一个 `client_id`（比如都写死成 `"default"`），会怎样？

---

## 四、面试高频题

**Q13.**（基础必考）MCP 里客户端如何取消一个正在进行的请求？stdio 和 Streamable HTTP 有什么不同？取消和完成同时发生时，服务端和客户端各自应该怎么处理？

**Q14.**（原理深挖）为什么说"新的 JSON-RPC id 不是幂等"？设计一个支付类工具的幂等方案：存什么、怎么保证并发安全、真实的外部支付 API 不在你的数据库事务里时怎么办？

**Q15.**（工程实践）一个工具会高频推送 progress，客户端在弱网环境下消费很慢，中间还有 Nginx 反向代理。你会如何设计服务端的 SSE 输出，保证内存有界、最终结果不丢、进度能及时到达？

**Q16.**（场景设计）你的 MCP 服务端刚从故障中恢复，1 万个客户端的 `subscriptions/listen` 流同时断开。请设计客户端的重连与状态恢复策略。

**Q17.**（追问型）产品界面上用户点了"停止任务"，界面立刻显示"已停止"，但后台 worker 还在跑，最后还把结果写进去了。问题出在哪？请求取消和 `tasks/cancel` 应该如何区分与配合？

---

## 五、参考答案与解析

### Q1 — 答案：C

stdio 只有一条共享的双向通道，没有"每请求一条流"可以关闭，所以用通知：`{"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":41,"reason":"..."}}`。讲义："The notification is fire-and-forget. The server emits no JSON-RPC response to it." 代码中 `receive_stdio_cancellation` 无论如何都 `return None`，测试 `test_stdio_cancellation_is_notification_and_suppresses_response` 明确断言返回 `None`。

- A 错：`tasks/cancel` 针对 durable Task，不针对普通 RPC。
- B 错：那是 Streamable HTTP 的做法。
- D 错：通知没有响应，等"确认"会永远等不到。

### Q2 — 答案：A

讲义："Do not POST `notifications/cancelled` for an ordinary HTTP request. Stream closure is the cancellation signal." 代码中 HTTP 传输的 `client_cancel_signal` 返回 `{"action": "close_response_stream", ...}`，没有 `method` 字段（测试 `assertNotIn("method", signal)`）。

- B 是讲义"生产失败模式"表中的第一行反例。
- C 错：服务端发起的取消只用于 stdio 的 `subscriptions/listen`。
- D 错：2026-07-28 版不支持 `Last-Event-ID` 续传，而且它与取消无关。

### Q3 — 答案：D

`timeout_signal` 先算 `hard_due = now - started_at >= max_timeout`：2000 − 0 ≥ 2000，为真；`reason = "maximum timeout" if hard_due else "idle timeout"`，硬超时优先。传输是 stdio，所以返回 `notifications/cancelled`（已实际运行验证：`{'requestId': 11, 'reason': 'maximum timeout'}`）。

- A 错：这正是讲义强调的"progress 可以重置 idle 时钟，但永远不能取消最大期限"。
- B 错：传输是 stdio，不是 HTTP。
- C 错：idle 只过了 1 ms，不满足；而且即便两者都满足，代码也优先报 maximum。

### Q4 — 答案：B

没有 progress token 时，`progress()` 直接返回 `None`、不更新 `last_activity_ms`；`last_activity_ms` 在 `__post_init__` 中被设为 `started_at_ms = 0`。于是 500 ms 时 `idle_due = 500 − 0 >= 500` 为真，返回 HTTP 版本的取消信号（已实际运行验证）。

这揭示了一个容易忽略的推论：**没有 progress 的请求，idle timeout 实际上就是它的寿命上限**。如果某个工具正常就要跑 1 秒且不发 progress，500 ms 的 idle 设置会把每一次调用都取消掉。配置 idle timeout 时要考虑工具是否发 progress。

- A、C 错：idle 时钟对没有 token 的请求同样生效。
- D 错：代码不会因此报错。

### Q5 — 答案：A

讲义："A successful `tasks/cancel` result does not prove the worker stopped. The task may remain `working` until a worker checkpoint observes the flag. Work may complete before that checkpoint." 代码中 `cancel()` 只设置 `cancel_requested = True`；实际验证：`cancel` 后先调 `finish()`，Task 变成 `completed`，之后 `worker_checkpoint()` 也不会把它改成 `cancelled`。

- B、D 错：取消是协作式的，不保证终态是 `cancelled`。
- C 错：取消意图与删除结果无关；讲义还强调 HTTP 连接关闭时不能抹掉 durable Task 状态。

### Q6 — 答案：D

无业务去重的变更属于 **Unsafe**：讲义 "Do not retry automatically; reconcile first"。代码 `classify_retry(side_effect=True, idempotency_key=None)` 返回 `"unsafe"`，理由是 "a new JSON-RPC id cannot deduplicate a side effect"。

- A 错：同一个 id 重发在协议上本就不合规（跟踪期间 id 必须唯一），且服务端不会做业务去重。
- B 错：讲义："Tool annotations such as `readOnlyHint` and `idempotentHint` remain untrusted hints."
- C 错：新 id 恰恰会让服务端把它当成新的扣款，执行两次（测试 `test_new_json_rpc_id_does_not_deduplicate_mutation`：两张不同的 receipt，`executions == 2`）。

### Q7 — 答案：B

第 1 条进入队列；第 2～6 条每条都发现"队尾是同 token 的 progress"，走**合并**分支替换队尾，`dropped_progress` 加 1，共加 5 次。此时队列只有 1 条 `{"value": 5}`。`push_final` 时 `len(events)=1 < 3`，直接追加。最终 2 条、丢弃计数 5（实际运行输出 `buffer size and dropped progress: 2 5`）。

- A：以为每条都会占位直到满 3 条——忽略了合并。
- C：以为第 1 条也算丢弃且最终响应未入队。
- D：把"丢最旧"和"合并"混在一起推演。

### Q8 — 答案：C

第二次调用在事务里查到 `checkout-7`，指纹相同，直接 `COMMIT` 并 `return json.loads(stored_json)`。存储的结果是**第一次执行时**写入的，所以 `rpcId` 仍是 41，receipt 是 `charge-001`；计数器没动，`executions == 1`（实际运行验证：两次返回 `{'account': 'acct-7', 'cents': 1200, 'receipt': 'charge-001', 'rpcId': 41}`）。

- A 错：那是不带 key 时的行为。
- B 错：每次都从 JSON 重建新的 dict，`first is second` 为 `False`——这正是"防御性拷贝"，测试中有 `assertIsNot(first, second)`。
- D 错：rpc_id 不参与指纹，指纹只有 `account` 和 `cents`。

这道题也说明：重放结果里的 `rpcId` 是"原始请求的 id"，不是本次请求的 id；把它当作"本次响应关联字段"使用会出错，JSON-RPC 关联应以外层 `id` 为准。

### Q9 — 参考答案

1. `not False == True`，即"没有不安全变更在途时，`retryUnsafeMutation` 为 `True`"。这在逻辑上是空洞的（根本没有可重试的东西），而读者或下游代码很容易把它理解成"允许自动重试不安全变更"。讲义的原则是 "Do not replay an unsafe mutation just because its response was lost"——不安全变更**永远**不应自动重放，这个字段应恒为 `False`；真正有信息量的是"是否需要先对账"。
2. 第二次断开时传入 `"listen-1-retry"`，得到 `"listen-1-retry-retry"`，依此类推，字符串无限增长；而且新 id 完全由旧 id 决定，如果两个并行组件都对同一订阅做恢复，会生成**相同的 id**，违反"跟踪期间 id 唯一"（`RequestCoordinator.start` 会对重复 id 抛错）。此外，整数 id 7 会变成字符串 `"7-retry"`，类型悄悄改变。
3. 覆盖：①新请求新 id（部分）、③ refetch、⑤不重放不安全变更（但语义有误）；并明确 `sendLastEventId=False`。缺失：②恢复订阅过滤器（plan 里没有 filter）、④按稳定标识去重应用状态；另外 plan 没有把退避时间（`retry_delay_ms`）带进来。
4. 改进版（已运行验证）：

```python
def reconnect_plan(previous_subscription_id, affected_resources, *,
                   unsafe_mutation_was_in_flight, attempt, subscription_filter):
    return {
        "newSubscriptionId": f"{previous_subscription_id}-retry-{attempt}",  # 或用 uuid4
        "sendLastEventId": False,
        "restoreFilter": subscription_filter,
        "refetch": sorted(set(affected_resources)),
        "retryUnsafeMutation": False,                     # 恒为 False
        "reconcileBeforeRetry": unsafe_mutation_was_in_flight,
    }
```

### Q10 — 参考答案

1. 逐步推演（已实际运行验证）：
   - `a0`：`[a0]`
   - `b1`：队尾 token 不同，不合并，`[a0, b1]`
   - `a2`：`[a0, b1, a2]`
   - `b3`：队尾是 a，不合并；`len=3 >= 3`，丢最旧 progress `a0`（dropped=1），追加 → `[b1, a2, b3]`
   - `final`：`len=3 >= 3`，再丢最旧 progress `b1`（dropped=2），追加 → `[a2, b3, final]`
   - 最终 `dropped_progress = 2`，`needs_refetch = True`。注意"合并"只看**相邻**的队尾，交替 token 时合并永远不发生。
2. 结果是 `[progress a=1, final, progress a=2]`——**最终响应之后还出现了 progress**。讲义："Notifications stop after completion or cancellation." `RequestCoordinator.progress()` 会在完成后返回 `None`，但 `BoundedSseBuffer` 自己没有这层检查，两者是独立组件，直接使用 buffer 时会写出违规流。修复：记录已完成的 token，之后的 progress 直接丢弃（不计入 refetch）。
3. 合并时被覆盖的旧值已被新值"取代"，客户端最终看到的仍是最新进度，信息并没有丢失——讲义自己也说 "Progress is replaceable. A later progress value supersedes an earlier one"。因此可以认为合并不必标记 `needs_refetch`，只有"丢最旧"（客户端可能错过某个 token 的全部更新）才需要 refetch。代码把两者都计入 `dropped_progress` 并置 `needs_refetch=True`，是偏保守的做法：安全但会造成不必要的 refetch。改进版（已运行验证）中合并后 `dropped_progress=0`、`needs_refetch=False`。
4. 没有。该测试只推同一个 token，20 条全部走合并分支，`_drop_oldest_progress` 从未被调用。应该补一个"多 token 交替 + 满容量"的测试，以及"容量被 final 占满后 push_final 抛错"的测试。

### Q11 — 参考答案

参考实现（继承原 ledger，复用同一个连接和 `idempotency_records` 表；已运行验证全部要求，包括两个连接 + barrier 并发只产生 1 条预留、重开后对账成功）：

```python
class InventoryLedger(MutationLedger):
    def __init__(self, path):
        super().__init__(path)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS reservations ("
            " reservation_id TEXT PRIMARY KEY, tenant TEXT, sku TEXT, quantity INTEGER)")

    @staticmethod
    def _op_fingerprint(operation, **args):
        payload = json.dumps({"operation": operation, **args},
                             sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def reserve_inventory(self, tenant, sku, quantity, *, rpc_id, idempotency_key):
        if not idempotency_key:
            raise ReliabilityError("reserve_inventory requires an idempotency key")
        if type(quantity) is not int or quantity <= 0:
            raise ReliabilityError("quantity must be a positive int")
        fp = self._op_fingerprint("reserve_inventory", tenant=tenant, sku=sku, quantity=quantity)
        scoped_key = f"{tenant}:reserve_inventory:{idempotency_key}"
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT fingerprint, result_json FROM idempotency_records "
                    "WHERE idempotency_key = ?", (scoped_key,)).fetchone()
                if row is not None:
                    if row[0] != fp:
                        raise ReliabilityError("idempotency key was reused with different arguments")
                    self._connection.execute("COMMIT")
                    return json.loads(row[1])
                n = self._connection.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] + 1
                rid = f"rsv-{n:03d}"
                self._connection.execute("INSERT INTO reservations VALUES (?,?,?,?)",
                                         (rid, tenant, sku, quantity))
                result = {"reservation": rid, "tenant": tenant, "sku": sku,
                          "quantity": quantity, "rpcId": rpc_id}       # 不含任何支付/密钥字段
                rj = json.dumps(result, sort_keys=True, separators=(",", ":"))
                self._connection.execute("INSERT INTO idempotency_records VALUES (?,?,?)",
                                         (scoped_key, fp, rj))
                self._connection.execute("COMMIT")
                return json.loads(rj)
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def reconcile(self, tenant, idempotency_key):
        row = self._connection.execute(
            "SELECT result_json FROM idempotency_records WHERE idempotency_key = ?",
            (f"{tenant}:reserve_inventory:{idempotency_key}",)).fetchone()
        return None if row is None else json.loads(row[0])
```

为什么要绑定操作名（和租户）：原 `_fingerprint` 只哈希 `{"account", "cents"}`，`idempotency_records` 表是所有操作共用的。如果两个不同操作恰好用了同一个 key 字符串，后一个操作要么被误判成"重放"直接拿到别的操作的结果，要么被误判成"参数不同"而报错。把操作名放进指纹（以及把 `tenant:operation:` 前缀放进 key 本身）可以让 key 的命名空间互相隔离，也防止 A 租户的 key 命中 B 租户的记录。

另外注意讲义的提醒：如果库存在另一个服务里，本地 SQLite 事务并不能让远端预留"原子化"，需要远端接受同一个幂等键，或用 transactional outbox 把本地提交可靠地传递出去。

### Q12 — 参考答案

1. 区间都是 `[ceiling // 2, ceiling]`（闭区间，因为 jitter 取 `% (ceiling − floor + 1)`）：

| attempt | ceiling | 区间 (ms) | 实测 a/b/c/d 四个客户端 |
|---------|---------|-----------|------------------------|
| 0 | 250 | [125, 250] | 218, 236, 228, 157 |
| 1 | 500 | [250, 500] | 434, 358, 342, 370 |
| 4 | 4000 | [2000, 4000] | 3471, 3673, 2565, 3431 |
| 5 | 8000（`250×32`，刚好到上限） | [4000, 8000] | 4788, 5156, 7323, 5786 |
| 10 | 8000（上限） | [4000, 8000] | — |

2. 这是 "equal jitter"（一半固定、一半随机）：保证至少等待 `ceiling/2`，避免过快重试；"full jitter" 是在 `[0, ceiling]` 里均匀取值，分散得更开但可能非常快地重试。讲义写 "up to 250 ms"，与代码一致但没提下限 125 ms。讲义也说 "The invariant is distribution, not a specific formula"，两种都可以。
3. jitter 由 `sha256(f"{client_id}:{attempt}")` 决定，相同 `client_id` + 相同 attempt 得到**完全相同**的延迟——1 万个客户端会在同一毫秒一起重连，jitter 完全失效，重连风暴照样发生。确定性 jitter 只适合测试；生产中要用每个实例唯一的 id（如安装 id + 进程 id）作为种子，或像讲义说的直接用运行时随机数。

### Q13 — 参考回答要点

- **stdio**：客户端发 `notifications/cancelled`，`params` 带 `requestId` 和可选 `reason`；这是通知，服务端不回响应。服务端应停止工作、释放资源、不再为该请求发送响应；对未知、格式错误、已完成的取消一律**静默忽略**（讲义："Turning those races into new errors would create more races"）。
- **Streamable HTTP**：每个请求有自己的响应流，客户端**关闭该流**即为取消；不要 POST 取消通知。服务端感知到断开后停止工作，不得再为该请求发消息。
- **服务端发起取消**：仅限 stdio 上终止 `subscriptions/listen`，代码 `server_cancel_subscription` 对其他情况直接抛错。
- **竞争处理**：每个请求只有一个终态。取消先到 → 状态 `cancelled`，之后 `complete()` 返回 `None`（不发响应）；完成先到 → 响应已发出，迟到的取消被忽略。客户端也要忽略它已放弃的请求的迟到响应。
- 加分点：能说出"网络延迟意味着双方都无法证明对方先看到了哪个事件"，所以设计目标是"任何顺序都有确定结果"，而不是"阻止竞争发生"；并提到两个时钟（idle + maximum）。

### Q14 — 参考回答要点

- **为什么 id 不是幂等**：JSON-RPC id 只关联一对请求/响应；重试时换了 id，服务端看到的是两条无关的消息，无法知道它们代表同一次结账。
- **存什么**：idempotency key（标识业务意图）、参数指纹（如规范化 JSON 的 SHA-256，绑定操作名、租户）、已提交结果。同键同参 → 返回存储结果；同键异参 → 拒绝。
- **并发安全**："查键 → 执行 → 存结果"是 check-then-act 竞态：两个 worker 都看到 key 不存在，都执行。必须把"占用 key + 副作用记录 + 结果"放在一个原子事务里（本节用 SQLite `BEGIN IMMEDIATE` 先拿写锁），或用唯一约束 + `INSERT` 抢占 key。进程内锁不跨副本、不跨重启。
- **返回防御性拷贝**：从存储的 JSON 重建结果，避免调用方修改返回对象污染后续重放。
- **外部副作用**：本地事务管不到外部支付 API。做法：①上游支持幂等键（把同一个 key 透传给支付服务商）；②transactional outbox：在本地事务里写"待执行"记录，由可靠的投递进程执行外部调用并回写；③崩溃后按 key 对账，而不是盲目重试。
- 常见误区：以为 `idempotentHint` 注解就够了；只在内存 dict 里存 key；指纹只比较部分参数。

### Q15 — 参考回答要点

- **有界队列**：每个流/每个客户端设置显式容量，拒绝无界队列（讲义："An unbounded queue converts slowness into memory exhaustion"）。
- **区分可丢与不可丢**：progress 可替换——相邻同 token 合并、满了丢最旧 progress，并标记"需要权威 refetch"；最终 JSON-RPC 响应不可丢，必要时为它预留容量；如果保留最终响应需要丢另一个最终响应，宁可报错（显式失败而不是静默丢失）。
- **速率限制**：服务端对 progress 限速（讲义提到 rate-limit，但本节代码没实现），避免快速 worker 淹没传输。
- **代理**：SSE 响应头 `Content-Type: text/event-stream`、`Cache-Control: no-cache`、`X-Accel-Buffering: no`（关闭 Nginx 缓冲），并调整代理的读超时。
- **保活**：安静时周期性发 SSE 注释 `:`，让中间设备不因空闲断开；但保活**不重置**业务的 idle timeout。
- 加分点：给出可观测指标——每流队列深度、丢弃计数、refetch 次数；说明 progress 值必须单调递增。

### Q16 — 参考回答要点

- **不要续传**：2026-07-28 版 Streamable HTTP 不支持 `Last-Event-ID`，所以重连 = 新开一个 `subscriptions/listen` 请求（新 id）。
- **恢复状态**：恢复订阅过滤器；按权威方法 refetch 受影响的 tools / resources / prompts / Tasks；按稳定标识符去重本地状态。
- **不重放不安全变更**：断线期间响应丢失的变更，按重试矩阵处理：conditional 的用同键同参重试，unsafe 的先对账。
- **防重连风暴**：带上限的指数退避 + jitter（如本节 250 ms 起、翻倍、上限 8000 ms），jitter 种子必须每个客户端不同；再配合服务端的准入限流/排队，必要时返回"稍后重试"的提示。
- **服务端配合**：刚恢复时可以分批放行、限制并发 listen 数量；对 refetch 端点做缓存。
- 加分点：解释为什么不加 jitter 时，"所有客户端在 1 秒时同时重连"会把刚恢复的服务端再次打挂；以及确定性 jitter 在测试中的价值。

### Q17 — 参考回答要点

- **问题根源**：把 `tasks/cancel` 的成功响应当成了"已停止"。`tasks/cancel` 只是确认取消意图，worker 在下一个 checkpoint 才可能看到标记；在那之前工作可能已经完成并写入结果。
- **正确做法**：UI 在收到 ack 后显示"正在取消"，然后轮询或订阅 Task 状态，直到终态（`cancelled` 或 `completed`）再更新界面；终态为 `completed` 时如实展示结果，并说明"取消请求晚于完成"。
- **区分两种取消**：
  - 请求取消（stdio 通知 / 关闭 HTTP 流）：放弃**一个在途 RPC**，生命周期与连接绑定；
  - `tasks/cancel`：一个普通 MCP 请求，针对**一个 durable Task**，其生命周期超越单次请求和连接。
  - HTTP 连接关闭时**不能**抹掉 durable Task 状态——建 Task 的意义就是让它活得比连接久。
- **worker 端**：在有副作用的步骤之前检查取消标记（checkpoint），让取消尽量在副作用发生前生效；已产生的副作用需要补偿逻辑。
- 加分点：指出本节 `DurableTaskService.finish()` 在 `cancel_requested=True` 时仍会把 Task 置为 `completed`，正好演示了"完成赢得了竞争"。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 06 MCP 基础：无状态请求与 JSON-RPC](../../06-mcp-fundamentals/docs/zh.md)：JSON-RPC id、通知与响应的区别是理解取消和幂等的前提。
- [阶段 13 · 09 MCP 传输：stdio 与无状态 Streamable HTTP](../../09-mcp-transports/docs/zh.md)：取消信号为什么随传输不同。
- [阶段 13 · 13 MCP Tasks 扩展：在无状态核心上运行持久任务](../../13-mcp-async-tasks/docs/zh.md)：`tasks/cancel` 与 durable Task 生命周期。
- [阶段 13 · 28 MCP Tool Contracts 与内容](../../28-mcp-tool-contracts-and-content/docs/zh.md)：工具注解（`readOnlyHint`、`idempotentHint`）为何只是提示。

### 本节被哪些后续内容用到
- [阶段 13 · 30 MCP 注册表供应链：准入、漂移与 Rollback](../../30-mcp-registry-supply-chain-and-drift/docs/zh.md)：把可靠性证据纳入发布与准入。
- [阶段 13 · 31 MCP 一致性工程：版本管理、证据与运维](../../31-mcp-conformance-versioning-and-operations/docs/zh.md)：把取消、超时、重连等行为写成一致性测试与发布门禁。
- [阶段 13 · 23 综合项目：无状态工具生态系统](../../23-capstone-tool-ecosystem/docs/zh.md)：讲义 Capstone Connection 要求的可靠性证据清单。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：checkpoint 与持久执行的通用思想。
- [阶段 17 · 24 LLM 生产环境中的混沌工程](../../../17-infrastructure-and-production/24-chaos-engineering-llm/docs/zh.md)：用故障注入验证这些竞争与重连行为。
- [阶段 17 · 22 对 LLM APIs 进行负载测试](../../../17-infrastructure-and-production/22-load-testing-llm-apis/docs/zh.md)：慢消费者、流式响应与背压的压测。

### 延伸关键词
`notifications/cancelled` · `close response stream` · `cancellation race` · `idle / maximum timeout` · `progress token` · `tasks/cancel` · `idempotency key` · `argument fingerprint` · `BEGIN IMMEDIATE` · `transactional outbox` · `backpressure` · `progress coalescing` · `X-Accel-Buffering` · `SSE keepalive` · `Last-Event-ID` · `exponential backoff with jitter` · `thundering herd`
