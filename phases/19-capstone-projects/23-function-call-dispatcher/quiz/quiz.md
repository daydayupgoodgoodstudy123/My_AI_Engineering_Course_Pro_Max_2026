# 测验 · 函数调用分派器（Function Call Dispatcher）

> **阶段 19 · 综合项目 · 第 23 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 分派器的位置 | 位于 harness 循环（第 20 节）与工具注册表（第 21 节）之间；讲义："The dispatcher is the only layer that knows about timers, retries, and idempotency." |
| 2 | 处理顺序 | 查工具（`not_found`）→ 校验参数（`schema`）→ 预算（`budget_exceeded`）→ 幂等缓存/在途请求 → 信号量 → 带超时与重试地执行 handler |
| 3 | 每次调用的超时 | `asyncio.wait_for(handler(...), timeout)`；超时取消 handler 任务并返回 `DispatchError(kind="timeout")`；记录中的 `timeout_ms` 可被单次调用覆盖 |
| 4 | 幂等性决定能否重试超时 | 非幂等工具（如 `db.write`）超时后可能已经提交，重试会重复副作用，所以只重试 `idempotent=True` 的工具 |
| 5 | 可重试的错误 | 只有 `timeout`（仅幂等工具）与 `transient`（handler 抛 `TransientError`）；`schema`、`not_found`、`internal` 都是确定性的，重试只会浪费预算 |
| 6 | 指数退避 + 抖动 | 最多 3 次；第 2 次前等待 `0.1s × (1 + U[0, 0.5])`，第 3 次前 `0.4s × (1 + U[0, 0.5])`；抖动避免大量客户端同时重试 |
| 7 | 幂等键去重 | 同一 key 在途时，后到者等待在途 future 并复用结果；完成后结果缓存 60 秒以吸收迟到的重试。key 由调用方提供 |
| 8 | 统一错误信封 | `DispatchError{kind, message, attempts, jsonrpc_code}`；`not_found` → `-32601`，`schema` → `-32602`，其余 → `-32603` |
| 9 | 有界并发 | 信号量（默认 8）包住每次执行，`gather` 一次扇出 40 个调用时同时运行的不超过上限 |
| 10 | 与循环的衔接 | 讲义：`schema`/`not_found` → `on_error` 并重新规划；`timeout`/`transient` → `on_error`；`budget_exceeded` → `on_budget_exceeded` |

### 核心技能（能动手做到）

- [ ] 读懂 `_run_with_retries` 的 while 循环，推演任意 handler 行为下的尝试次数与返回值
- [ ] 计算退避等待时间的范围，并用可注入的 `sleep` 写出不依赖真实时间的测试
- [ ] 说清 `asyncio.wait_for` 的取消语义，以及它为什么管不住阻塞式同步 handler
- [ ] 找出幂等去重在信号量饱和、leader 被取消时失效的原因并修复
- [ ] 为幂等键设计稳定、可跨进程复现的生成方式
- [ ] 把 `DispatchError.kind` 映射到第 20 节循环的状态转移与 hook

---

## 二、基础自测（选择题）

**Q1.** 本节分派器对**非幂等**工具的超时默认不重试，原因是：

- A. 非幂等工具的超时时间通常很短，重试也会再次超时
- B. JSON-RPC 规范禁止重试
- C. 重试会让预算计数出错
- D. 该工具可能在超时前已经部分或全部生效（如写库、扣款），重试可能重复副作用

**Q2.** 讲义中的幂等键（idempotency key）去重机制主要防止的是：

- A. 两个不同的工具使用相同的参数
- B. 原始调用仍在进行时，重试又发起了一次，两次请求同时打到后端（如重复扣款）
- C. 模型生成了不合法的 JSON
- D. 信号量被耗尽

**Q3.** 在本节代码中，以下哪些情况会触发重试（假设尚有剩余次数）？

- A. 幂等工具超时；以及 handler 抛出 `TransientError`（无论工具是否幂等）
- B. 所有异常都会重试
- C. 只有 schema 校验失败
- D. 只有非幂等工具超时

**Q4.** `Dispatcher` 中 `asyncio.Semaphore(concurrency)` 保护的是：

- A. 防止同一个幂等键被执行两次
- B. 保证结果按调用顺序返回
- C. 限制同时执行的 handler 数量，避免 `gather` 一次扇出过多调用压垮后端
- D. 防止 handler 超时

**Q5.** `max_attempts=3`，handler 连续抛 `TransientError`。第 2 次失败之后、第 3 次尝试之前，`_backoff` 返回的等待时间范围是：

- A. 0.1 – 0.15 秒
- B. 0.4 – 0.6 秒
- C. 0.8 – 1.2 秒
- D. 固定 0.4 秒

**Q6.** 参数没有通过 schema 校验时，`dispatch` 返回的结果是：

- A. 先重试 3 次再返回 `kind="schema"`
- B. `kind="internal"`，`jsonrpc_code=-32603`
- C. 抛出 `ValueError`
- D. `kind="schema"`、`attempts=0`、`jsonrpc_code=-32602`，handler 一次都没有被调用

**Q7.** 演示中的 `slow` 工具：`idempotent=True`、`timeout_ms=10`，handler 每次 `await asyncio.sleep(0.05)`，`max_attempts=3`。`dispatch("slow", {"n": 1})` 的结果是：

- A. `kind="timeout"`，handler 被调用 3 次，期间还有两段真实的退避等待（合计约 0.5–0.75 秒）
- B. `kind="timeout"`，handler 只被调用 1 次
- C. `DispatchOk(result=1)`，因为 0.05 秒很短
- D. `kind="transient"`，attempts 为 3

**Q8.** 讲义说幂等键应由调用方（harness/planner）提供，而不是分派器根据参数自动生成，原因是：

- A. 分派器无法访问参数
- B. 自动生成会让缓存占用太多内存
- C. 仅凭参数推导 key，会让两个语义不同但参数恰好相同的调用（如两次有意的相同扣款）被误判为同一次
- D. Python 的 `hash` 函数太慢

---

## 三、动手 / 代码题

**Q9.** 阅读 `dispatch` 与 `_run_with_retries` 中幂等相关的代码：

```python
        if idempotency_key is not None:
            ...
            inflight = self._inflight.get(idempotency_key)
            if inflight is not None:
                ...
                res = await inflight.future
                ...
        async with self._sem:
            return await self._run_with_retries(rec, args, timeout_ms_override, idempotency_key)
```

```python
        if idempotency_key is not None:
            future = loop.create_future()
            self._inflight[idempotency_key] = _InFlight(future=future, started_at=time.monotonic())
```

设 `concurrency=1`，一个慢调用正占用信号量，此时两个**相同幂等键**的调用几乎同时到达。

1. handler 会被执行几次？为什么测试 `test_inflight_dedupe` 没有发现这个问题？
2. 给出修复方案。

**Q10.** 继续看幂等去重的两个边界情况：

1. leader（第一个持有该 key 的调用）所在任务在 handler 运行期间被外部 `cancel()`，正在 `await inflight.future` 的 follower 会怎样？
2. 带幂等键的调用失败、且没有任何 follower 时，程序退出前会看到 `Future exception was never retrieved` 警告。为什么？
3. 如何修复这两个问题？

**Q11.** 写一个同步 handler：

```python
def h():
    time.sleep(0.2)
    return "late"
```

注册时 `timeout_ms=10`。`dispatch` 的返回值是什么？为什么超时没有生效？生产中应该如何为同步或 CPU 密集型 handler 实现真正的超时？

**Q12.** 讲义建议 harness 用 `f"{step_id}:{tool_name}:{hash(args)}"` 生成幂等键。

1. 当 `args` 是 `{"id": 42}` 这样的字典时，这行代码能运行吗？
2. 即便换成 `hash(str(args))`，还有什么问题？
3. 写一个稳定的 `make_idempotency_key(step_id, tool_name, args)`。
4. 另外：工具 schema 没有禁止额外属性时，`dispatch("t", {"id": 1, "extra": 2})`（handler 签名为 `lambda id: id`）返回什么 kind？合理吗？

---

## 四、面试高频题

**Q13.**（基础必考）设计工具调用的重试策略：哪些错误该重试、哪些不该？为什么要用指数退避，为什么还要加抖动（jitter）？

**Q14.**（原理深挖）解释幂等性与幂等键。本节"进程内在途去重 + 60 秒结果缓存"能提供什么保证、不能提供什么保证？真正防止重复扣款需要什么？

**Q15.**（工程实践）在 asyncio 中给工具调用加超时，有哪些陷阱？单次超时与整体截止时间（deadline）有什么区别？

**Q16.**（场景设计）planner 一次产出 40 个并行工具调用，其中一半打同一个外部 API。你如何设计并发控制、限流、熔断与预算，使系统既快又不会压垮后端？

**Q17.**（追问型）分派器返回的 `DispatchError` 应该如何回到第 20 节的 harness 循环和模型？不同的 `kind` 分别该怎么处理？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："A `db.write` that timed out may or may not have committed. Retrying duplicates the write. The dispatcher honors the `idempotent` flag from the registry record." 代码：

```python
                except asyncio.TimeoutError:
                    last_error = DispatchError(kind="timeout", ...)
                    if not rec.idempotent:
                        break
```

A 不是原因；B 错，JSON-RPC 不涉及重试策略；C 错，预算与此无关（本节甚至不在重试时扣预算）。测试 `test_timeout_non_idempotent_no_retry` 断言 handler 只执行了 1 次。

### Q2 — 答案：B

讲义："A retry that fires while the original is still in flight is a real production bug ... If the tool is `payments.charge`, you charged twice." A 恰恰是讲义说"不要用参数推导 key"的原因；C 由 schema 校验处理；D 无关。

### Q3 — 答案：A

超时分支检查 `rec.idempotent`；但 `TransientError` 分支**不检查**幂等性：

```python
                except TransientError as exc:
                    last_error = DispatchError(kind="transient", message=str(exc), attempts=attempt)
                    if attempt >= self.max_attempts:
                        break
                    await self._sleep(_backoff(attempt))
                    continue
```

实测：非幂等工具连续抛 `TransientError` 时 handler 被执行 3 次。这种设计的隐含约定是"handler 抛 `TransientError` 即声明本次失败没有产生副作用"，责任在 handler 作者。B 错，普通异常直接映射为 `internal` 不重试（`test_random_exception_no_retry`）；C 错，schema 错误不会重试（`test_schema_error_does_not_retry`）；D 说反了。

### Q4 — 答案：C

讲义："The dispatcher wraps `gather` in a semaphore. Default concurrency limit is eight." 测试 `test_semaphore_bounds_inflight` 用 20 个调用、`concurrency=3` 验证峰值不超过 3。A 是幂等键的职责（而且信号量反而会让幂等去重失效，见 Q9）；B 由 `gather` 保证，与信号量无关；D 由 `wait_for` 负责。

### Q5 — 答案：B

```python
def _backoff(attempt: int) -> float:
    base = 0.1 * (4 ** (attempt - 1))
    return base * (1 + random.random() * 0.5)
```

第 2 次失败后调用 `_backoff(2)`：`base = 0.1 × 4 = 0.4`，乘以 `[1, 1.5)` 得 `[0.4, 0.6)`。A 是 `_backoff(1)`（第 1 次失败后、第 2 次尝试前）；C 是 `_backoff(3)` 的范围，但 `max_attempts=3` 时第 3 次失败后直接 `break`，不会调用它；D 忽略了抖动。与讲义表格"attempt 3 → delay 0.4s × (1 + random[0..0.5])"一致。

### Q6 — 答案：D

```python
        errs = self.registry.validate(name, args)
        if errs:
            return DispatchError(kind="schema", message="; ".join(errs), attempts=0,
                                 jsonrpc_code=ERR_INVALID_PARAMS)
```

校验在执行之前，`attempts=0`。讲义："Schema errors are deterministic. Retrying does not change the outcome and burns the budget." 测试 `test_schema_failure_returns_invalid_params`、`test_schema_error_does_not_retry` 覆盖了这一点。A、B、C 都不符合代码。

### Q7 — 答案：A

每次 `wait_for(..., 0.01)` 都在 handler 睡满 0.05 秒前超时；工具是幂等的，所以重试：第 1 次后睡 `_backoff(1)` ∈ [0.1, 0.15)，第 2 次后睡 `_backoff(2)` ∈ [0.4, 0.6)，第 3 次后达到上限返回 `kind="timeout"`、`attempts=3`。演示没有注入假 `sleep`，所以这是**真实等待**——整个 `python main.py` 实测耗时约 0.96 秒，大部分花在这里。B 是非幂等工具的行为；C 错；D 混淆了 kind。

### Q8 — 答案：C

讲义："The dispatcher does not invent keys, because deriving a key from arguments alone makes two semantically-different calls look the same." 官方 `quiz.json` 的答案也是"two semantically-different calls collide if they happen to share args"。例如用户确实想给同一账户转两次相同金额。A、B、D 都不是原因（D 中 `hash` 的问题见 Q12，但与"谁来生成"无关）。

### Q9 — 参考答案

1. **执行 2 次**（实测：两个调用分别得到结果 1 和 2）。原因是"登记在途"发生在 `_run_with_retries` 内部，即**拿到信号量之后**；而"检查在途"发生在**等待信号量之前**。信号量被占满时，两个调用都检查到"没有在途"，然后一起排队等信号量，轮到时各自执行一次 handler。
   测试没有发现，是因为 `test_inflight_dedupe` 使用默认的 `concurrency=8`：第一个调用拿信号量不需要等待，会在第一次让出事件循环之前就同步地登记 future，第二个调用随后就能看到它。演示中的 `idempotency_pair` 更弱：`noop` 是同步 lambda，第一个调用在让出之前就执行完毕，第二个调用直接命中**结果缓存**，并没有走"等待在途 future"的路径。
2. 修复：把"创建 future 并登记到 `_inflight`"移到 `dispatch` 中、`async with self._sem` **之前**，并把 future 传给 `_run_with_retries`；`_inflight.pop` 放在 `dispatch` 的 `finally` 中：

```python
            fut = asyncio.get_running_loop().create_future()
            self._inflight[idempotency_key] = _InFlight(future=fut, started_at=time.monotonic())
            try:
                async with self._sem:
                    return await self._run_with_retries(rec, args, timeout_ms_override,
                                                        idempotency_key, fut)
            finally:
                self._inflight.pop(idempotency_key, None)
```

   已在副本上实测：修复后同样场景 handler 只执行 1 次，两个调用都得到结果 1，原 12 个测试全部通过。应再补一条"`concurrency=1` 且信号量被占用时仍只执行一次"的测试。

### Q10 — 参考答案

1. **follower 永远挂起**（实测：给 follower 套 0.3 秒超时后仍然超时）。leader 被取消时，`CancelledError` 是 `BaseException`，不会被 `except Exception` 捕获，直接进入 `finally`——`finally` 只把 key 从 `_inflight` 中删掉，没有给 future 设置结果或异常，等待它的 follower 就再也等不到了。
2. leader 失败时调用 `future.set_exception(...)`；没有 follower 时这个异常从未被任何人读取，future 被垃圾回收时 asyncio 会记录 `Future exception was never retrieved`（实测出现该警告）。功能上无害，但会污染日志。
3. 修复：
   - 在 `finally` 中检查 `if not fut.done(): fut.set_exception(_DispatchedError(DispatchError(kind="internal", message="leader cancelled", attempts=0)))`（也可以让 follower 自己重新发起执行）；
   - 给 future 加一个读取异常的回调：`fut.add_done_callback(lambda f: f.cancelled() or f.exception())`；
   - follower 等待时用 `await asyncio.shield(fut)`，避免 follower 自己被取消时把共享 future 一起取消。
   已在副本上实测：修复后 follower 立即得到 `internal: leader cancelled`，警告消失。

### Q11 — 参考答案

返回 `DispatchOk(result="late")`，耗时约 0.2 秒（实测 0.201 秒）——**超时完全没有生效**。原因：

- `_invoke` 对同步函数直接调用 `handler(**args)`，`time.sleep` 阻塞了整个事件循环线程；
- `asyncio.wait_for` 的超时依赖事件循环在到期时调度"取消"回调，而循环被阻塞，回调没有机会运行；
- 等同步函数返回时，协程已经拿到结果正常结束，超时机制什么也没做。
- 同时，阻塞期间所有其他并发调用也全部停滞。

生产做法：

- 同步 I/O handler 用 `await asyncio.to_thread(handler, **args)`（或 `loop.run_in_executor`）放到线程池，`wait_for` 至少能让**分派器**按时返回；但线程无法被强制终止，handler 仍会在后台跑完，必须配合幂等语义理解"超时 ≠ 没有执行"。
- 需要硬超时（可强杀）的 handler 放到子进程中执行，超时后终止进程——这正是第 26 节沙箱执行器的思路。
- CPU 密集型任务用进程池。
- 在注册时标记 handler 是否为 async，禁止长时间阻塞的同步 handler 直接在事件循环中运行。

### Q12 — 参考答案

1. 不能。`hash({"id": 42})` 抛 `TypeError: unhashable type: 'dict'`（实测）——字典是可变对象，不可哈希。
2. `hash(str(...))` 虽能运行，但 Python 对字符串的哈希**每个进程随机化**（`PYTHONHASHSEED`），重启后同一参数得到不同 key，跨进程/跨重启的去重失效；而且 `str(dict)` 依赖键的插入顺序，`{"a":1,"b":2}` 与 `{"b":2,"a":1}` 会得到不同的 key。
3. 参考实现：

```python
import hashlib, json

def make_idempotency_key(step_id: int, tool_name: str, args: dict) -> str:
    canon = json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]
    return f"{step_id}:{tool_name}:{digest}"
```

   `sort_keys=True` 保证键顺序无关；`sha256` 跨进程稳定。`step_id` 来自 planner，保证"同一步骤的重试"共享 key、"不同步骤的相同调用"不共享。
4. 返回 `kind="internal"`、`jsonrpc_code=-32603`，消息是 `TypeError: ... got an unexpected keyword argument 'extra'`（实测）。这不合理：这是**参数问题**，应归为 `schema`/`-32602`，模型才能据此修正。修复方式：schema 使用 `additionalProperties: false`（第 21 节扩展），或在调用前用 `inspect.signature(handler).bind(**args)` 检查，失败时返回 `schema` 错误。另外本节的 `_walk` 只检查 `object`/`integer`/`string`/`array` 四种类型，`number`、`boolean` 根本不检查（实测 `{"x": "str"}` 通过了 `number` 校验）。

### Q13 — 参考回答要点

- **该重试**：瞬时性故障——超时（仅幂等操作）、连接重置、限流（429）、服务端 5xx、handler 明确声明的 `TransientError`。
- **不该重试**：确定性故障——参数/schema 错误、方法不存在、权限拒绝、业务规则拒绝；讲义："Retrying does not change the outcome and burns the budget." 非幂等操作的超时也不应自动重试。
- **指数退避**：每次失败后等待时间成倍增长（本节 ×4：0.1 → 0.4 秒），给下游恢复时间，避免持续施压。
- **抖动**：大量客户端同时失败、同时按相同节奏重试，会形成周期性的"重试风暴"；加入随机因子（本节乘以 `1 + U[0, 0.5]`）打散重试时间点。
- **上限**：最大次数（本节 3）以及总时长上限；重试次数应计入预算。
- 加分点：本节把 `sleep` 设计为可注入参数，测试用假 sleep，既快又确定；讲义"Going further"提到的熔断器（circuit breaker）是重试的补充——持续失败时直接快速失败。

### Q14 — 参考回答要点

- **幂等性**：同一操作执行一次与执行多次的效果相同（如"把状态设为 X"是幂等的，"余额加 10"不是）。
- **幂等键**：调用方为"一次逻辑操作"生成唯一标识，所有重试复用它，接收方据此识别重复。
- **本节能保证**：同一进程内、同一个 `Dispatcher` 实例中，相同 key 的并发调用只执行一次（修复 Q9 后），60 秒内的迟到重试直接返回缓存结果。
- **不能保证**：
  - 进程重启或多个 harness 实例之间不共享 `_inflight`/`_cache`；
  - 失败结果不缓存，失败后再用同一 key 调用会重新执行（如果失败发生在副作用之后，就会重复）；
  - handler 已在后端生效但超时返回时，进程内去重无从得知；
  - 缓存只在读取时检查过期，从不清理（实测 `cache_ttl_seconds=0` 时 100 个 key 全部留在内存中）。
- **真正防重复扣款**：把幂等键传给**后端**（例如作为请求头），由服务端持久化"key → 结果"并保证同一 key 只执行一次；分派器侧的去重只是第一道防线。
- 常见误区：认为"加了重试 + 幂等键缓存"就实现了 exactly-once；分布式系统中通常只能做到"至少一次投递 + 幂等处理"。

### Q15 — 参考回答要点

- **取消是协作式的**：`wait_for` 超时后会取消 handler 任务，但只有当 handler 正在 `await` 时取消才生效；阻塞式同步代码（Q11）、吞掉 `CancelledError` 的代码都会让超时失效。
- **取消不等于没执行**：超时只说明"在期限内没拿到结果"，后端可能已经执行——这是"非幂等不重试超时"的根本原因。
- **资源清理**：被取消的 handler 应在 `finally` 中释放连接、文件句柄；分派器的去重结构也要在取消时正确收尾（Q10）。
- **单次超时 vs 整体截止时间**：本节是每次尝试单独计时，最坏情况总耗时约 `max_attempts × timeout + 退避`（如 3 × 30 秒 + 0.75 秒）。生产中应同时有"整体 deadline"（由 harness 的 wall-clock 预算传入），重试前检查剩余时间是否足够，不够就直接失败。
- **信号量与超时**：本节超时计时从拿到信号量之后开始，排队时间不计入；而且退避期间仍持有信号量，会占住并发名额。
- 加分点：Python 3.11+ 的 `asyncio.timeout()` 上下文管理器；把 deadline 作为参数一路传递给下游调用（deadline propagation）。

### Q16 — 参考回答要点

- **全局并发上限**：分派器级信号量（本节默认 8），防止一次扇出耗尽连接或子进程。
- **按工具/后端分级**：为每个后端单独设置信号量或令牌桶限流（如外部 API 每秒 N 次），避免一个慢后端占满全局名额。
- **熔断器**（讲义"Going further"）：某工具在时间窗口内失败 N 次后进入冷却期，期间直接返回 `kind="circuit_open"`，冷却后半开试探。
- **预算**：每个调用（包括每次重试）都扣 tool-call 预算；本节只在开头检查 `budget_tool_calls_remaining <= 0`，既不扣减也不计重试（实测预算为 1 时仍执行了 3 次）；并发扇出时更需要原子地"预留"预算。
- **结果处理**：`gather_bounded` 返回与输入同序的结果列表，部分失败不影响其他调用；对失败的子集可以单独重新规划。
- **可观测性**：记录排队时间、执行时间、重试次数、熔断状态（讲义建议发出 `dispatch.attempt`、`dispatch.retry` 事件）。
- 常见误区：直接 `asyncio.gather(*40个调用)` 而不加限制；只设全局上限而忽略单一后端的承受能力。

### Q17 — 参考回答要点

- **返回形式**：分派器不抛异常，返回 `DispatchOk` 或 `DispatchError`；harness 在 `AWAITING_TOOL` 的 `resume` 中把它变成 `{"result": ...}` 或 `{"error": ...}`，第 20 节代码会发出 `tool.result` 或 `tool.error`、触发 `on_error`。`to_envelope()` 生成 JSON-RPC 形状的错误对象，也可以经第 22 节传输层直接回给客户端。
- **按 kind 处理**（讲义）：
  - `schema`、`not_found`：确定性错误 → `on_error` 并触发重新规划；把错误详情（路径、期望类型）作为工具结果回传给模型，让它修正参数或换工具；
  - `timeout`、`transient`：分派器已经重试过（`attempts` 字段说明次数）→ `on_error`，可能重新规划、换备选工具或请求人工；
  - `budget_exceeded`：触发 `on_budget_exceeded`，循环暂停等待调用方决定；
  - `internal`：handler 的 bug，记录详情、告警，回传给模型时去掉敏感信息。
- **注意本节的不一致**：第 20 节的循环目前不会重新规划（`REFLECTING → PLANNING` 未实现），讲义描述的"replan"需要第 24 节的计划—执行控制流来落地。
- 加分点：错误回传给模型时保持简洁、结构化；同一错误连续出现时停止让模型重试，避免死循环消耗预算。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 20 Agent Harness 的循环契约](../../20-agent-harness-loop-contract/docs/zh.md)：分派结果回到循环的 `AWAITING_TOOL` pull point 与 hooks。
- [阶段 19 · 21 带 Schema 校验的工具注册表](../../21-tool-registry-schema-validation/docs/zh.md)：`idempotent`、`timeout_ms` 字段与参数校验。
- [阶段 19 · 22 通过换行分隔的 stdio 传输 JSON-RPC 2.0](../../22-jsonrpc-stdio-transport/docs/zh.md)：`jsonrpc_code` 与错误信封。
- [阶段 13 · 03 并行 Tool Calls 与工具调用中的 Streaming](../../../13-tools-and-protocols/03-parallel-and-streaming-tool-calls/docs/zh.md)：并行工具调用的来源。
- [阶段 14 · 06 工具使用与 Function Calling](../../../14-agent-engineering/06-tool-use-and-function-calling/docs/zh.md)：agent 中的工具调用循环。

### 本节被哪些后续内容用到
- [阶段 19 · 24 计划—执行控制流程](../../24-plan-execute-control-flow/docs/zh.md)：把分派器接到 plan-and-execute agent 上。
- [阶段 19 · 25 Verification Gates 与观察预算](../../25-verification-gates-observation-budget/docs/zh.md)：对工具结果做验证与预算控制。
- [阶段 19 · 26 带拒绝列表与路径隔离的 Sandbox 执行器](../../26-sandbox-runner-denylist/docs/zh.md)：真正可强制终止的执行环境。
- [阶段 19 · 28 通过 OTel GenAI Spans 与 Prometheus Metrics 实现 Observability](../../28-observability-otel-traces/docs/zh.md)：记录每次尝试与重试。
- [阶段 13 · 29 MCP 可靠性、取消与流量控制](../../../13-tools-and-protocols/29-mcp-reliability-cancellation-and-flow-control/docs/zh.md)：协议层的取消与流控。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：预算与重试的成本控制。

### 延伸关键词
`asyncio.wait_for` · `cooperative cancellation` · `asyncio.shield` · `asyncio.to_thread` · `exponential backoff` · `jitter` · `idempotency key` · `exactly-once vs at-least-once` · `semaphore` · `circuit breaker` · `deadline propagation` · `retry budget`
