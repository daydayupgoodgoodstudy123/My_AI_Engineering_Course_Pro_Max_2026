# 参考答案讲解：RunShape（14/29）

计时结束后再看。参考实现在同目录的 `runshape/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修队列

**现象**：解锁后的第一个错误是 `chaos.py` 里的 LookupError，而 `ScriptedFaults` 本身没有 bug。

**顺着往上找**：`fail_policy` 返回这次尝试的错误，不失败时返回 None。A 的脚本里只有一个结果 `[None]`，报错说它在第 1 次尝试时又被问了一次。调用它的是 `_attempt`：第一个 `if` 问一次，得到 None，条件不成立；接着为了进 DLQ 又问一次。这正是课里 `worker` 的写法。脚本是精确的，多问一次就报错；换成讲义练习 2 那种 10% 的随机失败，就不会报错，只是 DLQ 悄悄大了约 100 倍（代码讲解里的实测：1,000 个作业，DLQ 是 100、87、89 个，正确的期望约 1 个）。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. 每次尝试只问一次：`error = self.fail_policy(job)`，两个分支都用它。
2. 重试条件改成 `job.attempts <= self.max_retries`（等价于 `< self.max_attempts`）。原来的写法拿已经做过的尝试次数去和重试次数比，B 第 2 次失败就进了 DLQ，而它第 3 次本来会成功。
3. 死信分支要像成功分支那样把结局交出去：把作业记进 `_dead`，再 `_wake_waiters`。原来的代码只把作业放进 `dlq`、在 `job.error` 里记下最后一次的错误，等结果的调用方没人叫醒，`result()` 也查不到它死了。测试里每个调用方最多等 1 秒，于是报 `TimeoutError: nothing came back for j003 within 1 s`。这就是讲义 Where production runtimes fail 的 No DLQ：作业停在 DLQ 里，可对提交它的人来说，它悄悄消失了。`result()` 抛的 `DeadLettered` 带作业 id 和最后一次的错误，这里是 `500 upstream`。
4. 空闲 worker 不再每 50 毫秒醒一次：用一个 `asyncio.Event`，`enqueue()` 和 `stop()` 时 `set()`；worker 发现队列空了才 `clear()` 并等待，醒来后回到循环开头重新看队列。40 次“提交、等结果”从 2 秒左右降到几毫秒。

缺陷 3 和缺陷 4 都是调用方在等，根因不同：缺陷 4 的作业照常做完、结果照常交出，只是 worker 晚一个轮询间隔才开工；缺陷 3 是死信分支漏了交接，等多久都等不到。

缺陷 3 排在缺陷 2 后面露出来，是测试有意这样安排的：`run_jobs` 按 `rt.log` 判断作业是否都结束了，调用方拿到的结果放到日志断言之后才看。重试次数没修时，B 和 C 第 2 次尝试就死了，它们的调用方同样等不到，但日志断言先挂。

交接只做一半都过不了：只写 `_dead` 不叫醒，已经在等的调用方超时；只叫醒不写 `_dead`，被叫醒的调用方在 `result()` 里报 KeyError；直接对等待者 `set_exception`、不记下来，测试在运行结束后又问了一次 j003，这个后来的调用方超时。对等待者 `cancel()` 的话，调用方拿到的是 CancelledError，不是 DeadLettered。错误要用这次尝试问到的那个：进 DLQ 时再调一次 `fail_policy` 取错误，脚本用完报 LookupError；只在重试时记错误，带出去的是倒数第二次的 `429 rate limited`。

`publish` 的订阅者隔离起始代码已经做对了：每个订阅者单独 try/except，把 `(事件 id, 订阅者, "类型: 消息")` 记进 `dead_letters`，然后接着投递下一个。这几条断言留着，Part 5 改 `events.py` 时不能把它弄丢。

**护栏**：改成通知时最容易出三种错。每处理完一个作业就 `clear()` 一次的话，一次来 12 个作业，被唤醒的 worker 各做一个就又睡了，剩下的没人处理；`stop()` 不 `set()` 的话，睡着的 worker 永远看不到 `_stopping`；醒来不重新检查队列就 `popleft()`，几个 worker 一起醒时会对空队列报 IndexError。测试用 3 个 worker 和一次 12 个作业覆盖这几种情况，并用 agent 的调用记录确认每个作业只跑一次。把轮询间隔改成 1 毫秒，甚至改成 0（`sleep(0)` 忙等），也能过计时，但空闲的 worker 会一直空转，这一点留给追问。计时那一段每次等结果最多 1 秒：`enqueue()` 不唤醒空闲 worker 的话，这里报 TimeoutError。

## Part 2 持久作业表

参考实现只有一张表：`seq` 自增主键记加入顺序，`job_id` 是 uuid，`errors` 存成 JSON 数组，`died` 是进 DLQ 时分配的递增序号。

- **在 claim 时计数**：claim 在一个事务里选出到期最早的作业（`ORDER BY run_at_ms, seq`），改成 running 并把 attempts 加一，提交后才返回。这次尝试从此算数，进程中途崩溃也不例外。
- **打开时恢复**：构造函数找出所有 running 的作业，逐个调用 `fail(job_id, "interrupted")`。这和正常失败走同一条路：记错误、按次数退避、最后一次直接进 DLQ。测试里作业 a 两次在运行中“崩溃”，第二次是它的第 3 次尝试，于是打开时直接进了 DLQ，errors 是 `(trace, "interrupted", "interrupted")`。
- **退避**：`now + backoff_ms * 2 ** (attempts - 1)`，全是整数毫秒。测试最后让一个 max_attempts=4 的作业连续失败三次，等待依次是 1、2、4 秒；只看前两次的话，线性退避也是 1、2 秒。
- **到期**：`run_at_ms <= now`，等号成立就能领。
- **DLQ 的顺序**：`died` 取 `MAX(died) + 1`，和状态更新放在同一个事务里。用时间戳做不到：x 和 y 在同一毫秒死掉。
- **原样读回**：JSON 数组能原样存下带换行的报错；result 是 TEXT，空字符串读回来还是空字符串。complete 和 fail 都先检查作业是不是 running，done 或 dead 的作业再 complete 或 fail 都会报 ValueError。

## Part 3 cron

`parse_cron` 逐个字段拆：逗号分隔的每一项是 `*`、数字、`a-b`，或者其中的 `*`、`a-b` 后面跟 `/步长`。展开成 `range(start, end + 1, step)`，步长自然从范围起点数。日字段的 `*` 是 1 到 31，所以 `*/10` 是 1、11、21、31。周字段允许 0 到 7，最后用 `% 7` 把 7 并到 0。`days_restricted` 和 `weekdays_restricted` 记的是原始字段是不是单独一个 `*`，判断“任一匹配”时要用。`*/10` 也算受限，这一点和 Vixie cron 不同，Vixie cron 把以 `*` 开头的字段都当成没受限。

`next_fire` 先把 `after` 换成 UTC，抹掉秒，加一分钟，然后按天往后走：月份不在集合里就直接跳到下个月 1 号；某一天匹配，就在这一天里找第一个不早于起点的（时, 分）。判断一天是否匹配：两个日字段都受限时用“或”，否则用“与”（`*` 字段包含所有值）。Python 的 `weekday()` 周一是 0，换成 cron 的写法是 `(weekday() + 1) % 7`。找到的时间按 UTC 构造后返回，`after` 在别的时区也一样。

永远不会触发的情况只有一种：日字段受限、周字段是 `*`，而且所有选中的月份都没有这些日子。参考实现先做这个静态检查（每个月最多有几天，2 月按 29 天算），之后的循环就一定会结束。2 月 29 日最长要等 8 年（2096 年之后是 2104 年，因为 2100 年不是闰年），按天走也只是几千步，跳过不相关的月份后更少。测试的限值是 0.01 秒：按分钟找要 1 秒以上，按小时找也要将近 40 毫秒，参考实现不到 1 毫秒。

`missed` 从 last_fire 开始反复调用 `next_fire`，收集不晚于 now 的触发时间。“latest” 只跑最后一个；“skip” 只在最后一个正好落在 now 所在的那一分钟时才跑。剩下的个数就是 skipped，调度器应该把它报出来，而不是悄悄跳过。

## Part 4 SSE 流

结构是一个生产者任务、一份事件日志和一个 `asyncio.Condition`：

- `_log` 保存每条已经生成的 SSE 文本，事件 n 就是 `_log[n - 1]`；`_read` 是客户端已经拿到的最后一个 id。
- 生产者每一轮先等 `len(_log) - _read < ahead`，再看预算，再向 agent 要下一步。先等再要，agent 才会停在“还没开始做下一步”的地方。
- `events(last_event_id)` 把 `_read` 设成客户端报上来的 id，从日志里的这个位置往后读，读完已有的就在 Condition 上等新的；每交出一条就更新 `_read` 并通知生产者，交出 final 以后结束。`yield` 放在 `async with` 外面：拿着锁交出事件的话，客户端处理这条事件的整段时间里生产者都拿不到锁。
- 客户端断开只是关闭了这个生成器，生产者照常跑到缓冲满，然后停在那里；重连时从日志里补发。测试里第 2 条在断线时没送到，重连带的是 `1`，有日志才能把第 2 条再发一次。已经收到 final 的客户端带着 `7` 重连，循环一开始就满足结束条件，什么也不发。
- 预算只累加 `__anext__` 前后的时钟差。等客户端的时间在 `__anext__` 之外，不会被算进去。检查用的是 `worked >= budget_s`，正好用完就停，final 里报 `"budget"`，同时关闭 agent。
- 每个字符串是一条完整的 SSE 消息：`id`、`event`、一行 JSON 的 `data`，最后一个空行。

## Part 5 事件级联

用一个 FIFO 队列做广度优先，元素是 `(深度, 事件)`，根事件深度为 0：

- 出队时先看这个 id 在本次级联里有没有出现过，出现过就跳过，菱形和回环都靠这一步。
- 深度超过 max_depth：记进 truncated，不投递，也不展开。
- 没有订阅者：记进 unhandled。
- 否则按订阅顺序投递，跳过账本里已有的 `(事件 id, 订阅者)`。投递成功才写进账本，返回的事件以深度 + 1 入队；失败的记进 dead_letters，不写账本，也不进 unhandled（这个事件有订阅者）。返回 None 或空列表也是成功：`_deliver` 把它变成空列表，只有抛异常时才返回 None。

账本 `_handled` 跨多次 cascade 保留，所以同一个事件再发布一次就是重放：只有新加入的 auditor，或者上次失败的 evaluator 会收到。按订阅者记而不是按事件记，就是为了让重放只补缺的那部分。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的异步代码里调试，能把作业状态可靠地存进 SQLite，能实现 cron 的时间计算，能写一个有背压、能断线续传的 SSE 流，也能处理事件之间的图结构。它不涉及真实的消息队列（Celery、BullMQ、SQS）、多台机器之间的租约、真实的 HTTP 服务，也不涉及 durable execution 的检查点（课里说这部分在第 13 课用 LangGraph 讲）和 OpenTelemetry 追踪的接入。这些需要另外动手做。
