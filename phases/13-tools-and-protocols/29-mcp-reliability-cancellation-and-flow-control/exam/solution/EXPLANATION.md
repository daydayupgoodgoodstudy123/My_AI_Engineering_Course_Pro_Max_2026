# 参考答案讲解：reliablerpc（13/29）

计时结束后再看。参考实现在同目录的 `reliablerpc/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修取消竞态和缓冲

**现象**：解锁后的第一个错误是 `buffer.py` 里的 `StreamClosed: write to a closed response stream`，而 buffer 拒绝往关掉的流里写，本身没有错。

**顺着往上找**：traceback 的上一层是 `RequestCoordinator.complete`。请求 7 走 Streamable HTTP，客户端已经关了它的响应流，`close_http_stream` 把它标成 cancelled 并关了流。`complete()` 只判断了 completed，没有判断 cancelled，于是照样拼出响应往流里写。讲义说取消先到时服务器要“suppress the response”，报错的位置在 buffer，出错的位置在 coordinator。

**依次修四处**：

1. `complete()`：请求已经 cancelled 就返回 None，什么都不写。
2. `_cancel()`：请求已经结束（completed 或 cancelled）就什么都不改。stdio 的 `receive_stdio_cancellation` 和 HTTP 的 `close_http_stream` 都走这里，所以改一处两条路都修好；只改 stdio 那条，HTTP 上完成之后再关流照样会把 completed 改成 cancelled。
3. `progress()`：请求不在 in_progress 就返回 None。讲义："Notifications stop after completion or cancellation."
4. buffer 改成按序号存消息，另用一个 deque 按先后记下进度消息的序号：

```python
self._messages: dict[int, dict] = {}   # dict 本身保持插入顺序
self._progress: deque[int] = deque()   # 队列里进度消息的序号，最旧的在左边

def _drop_oldest_progress(self) -> bool:
    if not self._progress:
        return False
    del self._messages[self._progress.popleft()]
    self._lose_progress()
    return True
```

队尾消息用 `next(reversed(self._messages))` 取，合并时原地替换，序号不变，所以 deque 不用动。drain 时 dict 和 deque 一起清空，否则下一轮会按旧序号去删已经不在的消息。原来的写法每次都从头找第一条进度：5000 条响应排在前面时，每推一次都要跨过 5000 个元素，5000 次推送约 1 秒；现在每次推送是常数时间，同样的工作 1.3 毫秒左右。

**护栏**：提速时最省事的写法是 `deque(maxlen=capacity)`，满了自动挤掉最旧的一条。可最旧的往往是一条响应，而响应永远不能丢。讲义的策略有五条：相邻的同一个 token 合并；满了丢最旧的进度；丢了就标记需要重新拉取；保住最终响应；要保住一条响应就得丢另一条响应时，宁可报错。测试为每一条都配了断言：合并只看队尾那一条，越过响应不合并，而且先于容量判断，队列满了也是原地替换；丢的是最旧的进度，不管它是哪个 token；满了全是响应时，新进度直接丢掉并计数，新响应抛 ReliabilityError，队列不变。

本课代码里合并也算丢失：计入 `dropped_progress`，并置 `needs_refetch`。这是偏保守的选择，被合并掉的旧值已经被同一个 token 的新值取代了；题目按本课代码走。

## Part 2 幂等账本

参考实现在 `entries` 之外只加一张表：

```sql
CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    result_json TEXT NOT NULL
)
```

`call()` 的骨架：

```python
fingerprint = _fingerprint(name, arguments)   # sha256(json.dumps({"tool", "arguments"}, sort_keys=True))
self._db.execute("BEGIN IMMEDIATE")
try:
    if key is not None:
        stored = SELECT fingerprint, result_json ... WHERE idempotency_key = key
        if stored is not None:
            if stored[0] != fingerprint:
                raise IdempotencyConflict(...)
            self._db.execute("COMMIT")
            return json.loads(stored[1])
    result_json = json.dumps(tool(self._db, arguments, rpc_id=rpc_id), sort_keys=True)
    if key is not None:
        INSERT INTO idempotency_records ...
    self._db.execute("COMMIT")
except BaseException:
    if self._db.in_transaction:
        self._db.execute("ROLLBACK")
    raise
return json.loads(result_json)
```

几个决定：

- **`BEGIN IMMEDIATE` 放在查键之前**。它一开始就拿写锁，第二个副本的 `BEGIN IMMEDIATE` 会一直等到第一个提交，再查键时就能看到记录，于是重放。普通的 `BEGIN` 是延迟的：第二个副本先拿读锁查到“没有”，等它要写时，SQLite 发现自己在读事务里、对方握着写锁，直接报 `database is locked`，不会调用 busy handler。查键放在事务外、或者用 Python 默认的隐式事务（只在 INSERT、UPDATE 前才自动 BEGIN），都是讲义说的“check key, run mutation, store result”三步，第二个副本会再执行一次。
- **工具的副作用和记录在同一个事务里**。工具通过传给它的连接写 `entries`，抛异常时 ROLLBACK 把这一行一起撤掉。测试里的工具写完扣款就崩溃，重试之后必须只扣一次。
- **失败也要 ROLLBACK**。冲突、工具异常都走 `except BaseException`。漏掉的话，这个连接一直停在事务里握着写锁，下一次调用报 `cannot start a transaction within a transaction`，别的副本也只能等到超时。
- **指纹**：工具名加参数的规范 JSON。`sort_keys=True` 会递归排序，所以嵌套的 `cart` 键顺序不同也是同样的参数；只排第一层（`sorted(arguments.items())`）不够。工具名必须在里面，否则 `refund_account` 能拿 `charge_account` 的键拿到一张扣款收据。JSON-RPC id 不能在里面，新 id 的重试恰恰要命中旧记录。
- **返回值永远从存储的 JSON 重建**，第一次调用也一样。调用方改返回的 dict，改的只是自己那一份；内存缓存会把同一个对象交给所有调用方，浅拷贝挡不住对嵌套 dict 的修改。
- **重放原样返回**，包括第一次的 `rpcId: 41`。JSON-RPC 的关联靠外层响应的 id，结果体里的 rpcId 记录的是真正执行的那次调用。

测试的最后一段让另一个 Python 进程扮演第二个副本：第一次调用的工具在事务里通知它开始重试，再等 0.4 秒。正确的实现里，第二个副本这 0.4 秒一直在等锁，等到以后重放第一次的结果。进程内的 `threading.Lock` 在这里不起作用，讲义也说了，进程锁既挡不住别的副本，也撑不过重启。

## Part 3 重试分类和取消信号

`classify_retry` 照讲义的重试矩阵，只看应用自己的 contract：

```python
contract = contracts.get(call.params.get("name"))
if contract is None:
    return RetryDecision("unsafe", None)
if not contract.side_effect:
    return RetryDecision("safe", NewRequest("tools/call", copy.deepcopy(call.params)))
key = arguments.get(contract.idempotency_key) if contract.idempotency_key else None
if isinstance(key, str) and key:
    return RetryDecision("conditional", NewRequest("tools/call", copy.deepcopy(call.params)))
return RetryDecision("unsafe", None)
```

`tools` 参数（服务器的 tools/list）完全不用。讲义："Tool annotations such as readOnlyHint and idempotentHint remain untrusted hints." 测试里 `send_email` 和 `rotate_keys` 都自称只读、幂等，一个有副作用而且服务器不去重，一个应用根本不认识，两个都是 unsafe。键必须是非空字符串，空串和数字都算没有键。conditional 的重试原样发同样的 params，新的 JSON-RPC id 由传输层分配。

`cancel_signal` 先看是不是任务，再看传输：

- 有 `task_id`：`NewRequest("tasks/cancel", {"taskId": ...})`。第 13 课讲过，tools/call 返回任务句柄时那个请求就已经完成了，关它的流、发 `notifications/cancelled` 都碰不到任务。`tasks/cancel` 是一个普通请求，成功只说明服务器收下了取消意图。
- stdio：`Notify(notifications/cancelled)`，params 里 `requestId` 原样用调用的 id，有 reason 才写 reason。它是通知，没有 id，服务器也不回。
- Streamable HTTP：`CloseStream(request_id)`。讲义："Do not POST notifications/cancelled for an ordinary HTTP request. Stream closure is the cancellation signal."

`server_cancel_signal` 只放行 stdio 上的 `subscriptions/listen`，其余一律 ReliabilityError。

## Part 4 双时钟的 SSE 流

循环里同时盯着三样东西：worker 的下一个事件（拉一个看一个）、下一次保活的时刻、两个截止里较早的那个。

```python
while True:
    at_ms, event = next(self.worker, (None, None))      # None：worker 卡住了
    while True:
        deadline = min(hard_deadline, last_progress_at + idle_timeout_ms)
        keepalive_at = last_write_at + keepalive_ms
        if deadline <= keepalive_at and (at_ms is None or deadline <= at_ms):
            clock.advance_to(deadline); outcome = ...; return     # 先判断截止
        if at_ms is not None and at_ms <= keepalive_at:
            break                                                 # 事件先到
        clock.advance_to(keepalive_at); last_write_at = keepalive_at
        yield b":\n\n"                                            # 安静期的保活
    clock.advance_to(at_ms)
    ...  # Done：写最终响应并 return；Progress：有 token 且值更大才写，并刷新两个时间
```

- `hard_deadline` 只在开头算一次，进度只刷新 `last_progress_at`。讲义的例子里 1999 ms 的进度把空闲截止推到 2499 ms，最大截止仍在 2000 ms，2100 ms 才到的结果写不出去。
- 截止的判断放在处理事件之前，同一时刻截止优先。
- 保活只刷新 `last_write_at`，不刷新 `last_progress_at`。讲义："Keepalive is not progress."
- 不递增的进度值、没有 token 时的进度，都不写，也不刷新空闲时钟；所以没有 token 的请求，空闲时钟从开始算（本课代码的 `timeout_signal` 也是这样）。最终响应不需要 token。
- 被取消就直接 return：讲义说取消之后不再为这个请求发任何消息，所以也不发错误响应。
- finally 里关闭 worker。正常写完、被截止取消、客户端提前关流（生成器在 yield 处收到 GeneratorExit），三种结束都会走到这里，相当于讲义说的 "stop work, free resources"。测试一直持有 CallStream 对象，不能指望垃圾回收替你关闭 worker。

## Part 5 穷举取消竞态

```python
seen = {start}
frontier = deque([(start, ())])
while frontier:
    world, trace = frontier.popleft()
    if len(trace) >= max_depth:
        continue
    for event in events:
        after = model.step(world, event)
        if after is None or after in seen:
            continue
        path = trace + (event,)
        if after.problem is not None:
            return Counterexample(path, after.problem)
        seen.add(after)
        frontier.append((after, path))
return None
```

- World 是冻结的 dataclass，比较时不看里面的 coordinator 和 client 对象，所以可以直接放进 set 去重。不去重的话，同一个状态被成千上万条交错各走一遍：这个模型去重后 840 步，不去重 3.6 万步，`max_progress` 再大一点就指数爆炸。
- 广度优先保证第一个找到的反例最短；同一层按父节点出队的顺序、再按 events 的顺序生成，所以它也是这一层里按事件顺序最靠前的。测试把 events 换个顺序、去掉 `cancel`，预期的反例都跟着变。
- 修好的 Part 1 协调器跑完所有交错都没有违规。把 Part 1 的三个缺陷分别放回去（测试里的三个子类），explore 都能给出 4 步的最短故事，比如 `start, cancel, complete, server_hears`：客户端放弃，worker 先完成，迟到的取消把已完成的请求改成了 cancelled。客户端用了放弃之后才到的响应，也会被抓住。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着 traceback 找到上一层的根因，理解“取消先到”和“完成先到”各自该怎么收尾，能为慢消费者写出常数时间、不丢响应的有界队列；能用 `BEGIN IMMEDIATE` 把查键、副作用和结果放进一个事务，并且知道指纹为什么要规范化；能按应用自己的 contract 做重试分类，按传输和生命周期选取消信号；能写出两套时钟加保活的流式输出，以及带去重、能给出最短反例的广度优先搜索。它不涉及真实的套接字、HTTP 服务器和反向代理（代理头只检查了是否写出），不涉及真正的外部支付和 transactional outbox，也不涉及重连时的 refetch 计划和带抖动的指数退避（本课的 `reconnect_plan`、`retry_delay_ms` 留给追问），以及持久任务本身的状态机（第 13 课）。
