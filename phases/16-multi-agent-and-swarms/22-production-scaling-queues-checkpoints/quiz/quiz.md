# 测验 · 生产扩展：队列、Checkpoints 与持久性（Production Scaling — Queues, Checkpoints, Durability）

> **阶段 16 · 多智能体与集群 · 第 22 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Durable execution | 工作队列 + checkpoint：每个 super-step 后持久化状态，任意 worker 崩溃后，另一 worker 在 lease 过期后从最新 checkpoint 恢复 |
| 2 | 三个前提 | 状态可序列化、恢复可确定性重放（LLM 调用结果需记录或交给外部确定性来源）、副作用幂等（或带去重键） |
| 3 | LangGraph runtime | 讲义："每个 super-step 后按 `thread_id` 写 checkpoint（默认 Postgres）"；`interrupt()` 可无限期等待人工输入并释放 worker；Temporal 按 activity 写，Restate 用事件溯源日志 |
| 4 | MegaAgent（arXiv:2408.09955） | 每个 agent 一个生产者—消费者队列，三态 Idle / Processing / Response；两层协调：组内聊天 + 组间 admin 聊天，使成本随 agent 数线性增长 |
| 5 | async vs 每任务一线程 | LLM 调用是 I/O 密集型；讲义："线程在等 token 时 99% 空闲，每个约 1MB"；协程在 I/O 上主动让出；CPU 密集的后处理仍用线程/进程 |
| 6 | Bedi 的"从简单开始" | FastAPI + Postgres（每次运行一行、乐观并发、`pg_notify` 或 Celery 做后台任务）；讲义："约 100 个并发 agent 运行以下通常就够"，测到失败再升级 |
| 7 | Exactly-once 的工程实现 | 实际是"至少一次投递 + 幂等消费"：每次运行一个去重键、outbox 模式、补偿事务 |
| 8 | Rainbow deployment | 多个运行时版本同时在线，长时间运行的 agent 不必在每次部署时被杀；新版本先灰度，旧版本等其上的 agent 跑完再下线 |
| 9 | 生产清单 | 持久状态、幂等副作用、async I/O 层、至少一次 + 去重、rainbow/canary、可观测性（每个 agent 的 trace、super-step 审计、重试计数） |
| 10 | 本节代码的真实情况 | checkpoint 恢复演示正确，但没有 lease、没有副作用与去重；三态队列只是单线程状态机；async 与线程只差约 1.7 倍（讲义说线程要"几秒"），内存差异只是打印出来的说法，没有测量 |

### 核心技能（能动手做到）

- [ ] 用 SQLite/Postgres 实现按 `(thread_id, super_step)` 为主键的 checkpoint 表，并从最新一行恢复
- [ ] 指出"副作用之后、checkpoint 之前崩溃"会导致副作用重复，并用去重键/outbox 修复
- [ ] 用一条带条件的 `UPDATE` 实现 lease（租约），防止两个 worker 同时恢复同一个 thread
- [ ] 逐步追踪三态队列的状态变化，并说出它离真正的生产者—消费者队列还差什么
- [ ] 正确地对比 asyncio 与线程：同时测耗时与内存，并解释"每线程 1MB"指的是什么
- [ ] 根据负载、运行时长、人工等待、部署频率，在 FastAPI + Postgres、LangGraph/Temporal、自研 outbox + 事件溯源之间做选择

---

## 二、基础自测（选择题）

**Q1.** 讲义列出的 durable execution 正常工作的三个前提是：

- A. 使用 Postgres、使用 Kubernetes、使用 Python asyncio
- B. 状态可序列化、恢复可确定性重放、副作用幂等
- C. 所有 LLM 调用 temperature 为 0、单一 worker、内存中保存状态
- D. 每步都人工审核、每步都写日志、每步都重试三次

**Q2.** 讲义中"exactly-once effective"语义的工程做法是：

- A. 让消息队列保证每条消息恰好投递一次
- B. 关闭所有重试
- C. 把副作用放进 LLM 的 prompt 里
- D. 至少一次投递 + 幂等消费者（每次运行带去重键，配合 outbox、补偿事务）

**Q3.** 关于 Bedi 的"Scaling Agentic Software"，讲义的结论是：

- A. 在实测负载证明不够之前，用 FastAPI + Postgres 即可；约 100 个并发 agent 运行以下通常足够
- B. 任何多 agent 系统都应该从第一天起使用 Temporal
- C. 应该完全放弃数据库，只用内存事件循环
- D. 必须使用 actor 模型框架

**Q4.** MegaAgent 的架构特点是：

- A. 所有 agent 共享一个全局队列，没有状态机
- B. 每个 agent 一个线程，线程之间共享内存
- C. 每个 agent 一个生产者—消费者队列，状态为 Idle / Processing / Response；组内聊天 + 组间 admin 聊天两层协调
- D. 用区块链记录每个 agent 的消息

**Q5.** 运行本节 `demo_checkpoint_resume`（`crash_at=3`、`goal=5`），输出中"最后一个 checkpoint"和最终结果是：

- A. super_step=3，counter=4；最终 counter=5
- B. super_step=3，counter=3；最终 counter=6
- C. 没有 checkpoint，worker 2 从头开始，最终 counter=5
- D. super_step=2，counter=3；最终 counter=5

**Q6.** `AgentQueue` 入队 2 条消息后，至少要调用多少次 `step()` 才能处理完两条消息并回到 `idle`？

- A. 2
- B. 6
- C. 4
- D. 7

**Q7.** 在本环境实际运行 `demo_async_vs_threads`（500 个 50ms 的模拟调用），结果最接近：

- A. async 约 0.054 s，线程约 0.089 s，线程慢约 1.7 倍
- B. async 约 0.054 s，线程约 25 s（500 × 50ms 串行）
- C. async 约 0.5 s，线程约 5 s
- D. 两者都约 25 s

**Q8.** 讲义中 Anthropic 多 agent 研究系统使用的 rainbow deployment，主要解决的是：

- A. 让不同用户看到不同颜色的 UI
- B. 把所有 agent 的状态存到彩虹表里
- C. 多个运行时版本同时在线，长时间运行的 agent 不会因为每次代码部署而被杀掉；新版本先在一部分流量上灰度，旧版本等其上的 agent 跑完再下线
- D. 每次部署前清空所有正在运行的 agent

---

## 三、动手 / 代码题

**Q9.** 阅读 checkpoint 恢复的核心循环：

```python
    while state["counter"] < goal:
        if crash_at is not None and super_step == crash_at:
            raise RuntimeError("simulated crash")
        state["counter"] += 1
        store.write(thread_id, super_step, dict(state))
        super_step += 1
```

假设每一步在 `counter += 1` 之前要做一个真实副作用"向用户扣费一次"，并且崩溃发生在**扣费之后、写 checkpoint 之前**（step 3）。

1. worker 2 恢复后，总共会扣费几次？哪一步被重复？
2. 实测：不做去重时扣费记录为 `['t-1:0', 't-1:1', 't-1:2', 't-1:3', 't-1:3', 't-1:4']`。请用"去重键"修复，并说明去重记录**必须存在哪里**才能在真实崩溃后仍然有效。
3. 原代码的 `INSERT OR REPLACE` 对"同一个 super_step 被写两次"意味着什么？这对恢复是好事还是坏事？

**Q10.** 讲义的恢复流程是"worker 崩溃 → lease 过期 → 另一个 worker 接手 thread_id"。原代码完全没有 lease。

1. 如果两个 worker 同时对 `t-1` 调用 `run_agent_with_checkpoint`，会发生什么？
2. 用一张 `leases(thread_id, owner, expires_at)` 表和一条带条件的 `UPDATE` 实现 `acquire(conn, thread_id, owner, ttl)`：只有在无人持有、自己持有、或租约已过期时才能获得。给出代码并说明为什么要用 `rowcount` 判断成功。
3. lease 能完全防止"两个 worker 同时执行"吗？还需要什么配合？

**Q11.** `AgentQueue.step` 的实现：

```python
    def step(self) -> None:
        if self.state == AgentState.IDLE and self.in_queue:
            self.state = AgentState.PROCESSING
        elif self.state == AgentState.PROCESSING:
            msg = self.in_queue.pop(0)
            self.out_queue.append({"reply_to": msg, "body": f"{self.agent_id} processed {msg}"})
            self.state = AgentState.RESPONSE
        elif self.state == AgentState.RESPONSE:
            self.state = AgentState.IDLE
```

1. 写出 demo 中 7 次 `step()` 后每次的 `state / in / out`。
2. 列出它与"能扩展到数千个 agent 的生产者—消费者队列"之间至少 4 个差距（Takeaways 声称"scale to thousands of concurrent agents"）。
3. `self.in_queue.pop(0)` 的时间复杂度是多少？应换成什么？

**Q12.** 讲义预期"async 处理 500 个并发调用 < 1 s；线程版要几秒，且每个并发单元的内存大几个数量级"。在本环境另行测量（每种情况单独起一个进程，用 `resource.getrusage` 的 `ru_maxrss` 增量估算内存）：

| 并发数 | async 耗时 | 线程耗时 | async 内存增量 | 线程内存增量 |
|-------|-----------|---------|--------------|------------|
| 500 | 0.054 s | 0.110 s | 1.4 MB | 7.6 MB |
| 2000 | 0.061 s | 0.250 s | 3.6 MB | 23.6 MB |
| 5000 | 0.079 s | 0.666 s | 8.3 MB | 54.6 MB |

（本机 `ulimit -s` 为 8192 KB，`threading.stack_size()` 返回 0，即使用平台默认值。）

1. 为什么线程版也只用了零点几秒，而不是 500 × 50ms = 25 s？
2. 按表估算每个线程、每个协程的常驻内存。讲义说的"每线程约 1MB"（本机默认其实是 8MB）指的是什么？为什么和测到的不一样？
3. 那么在 LLM agent 场景里，async 真正的优势在哪里？什么时候 async 反而会出问题？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 durable execution？一个 agent 运行到一半 worker 崩溃了，完整的恢复流程是什么？需要满足哪些前提？

**Q14.**（原理深挖）分布式系统里为什么做不到"真正的 exactly-once"？对于按次计费的 agent 运行，你会如何实现"effectively exactly-once"？讲一下 outbox 模式。

**Q15.**（工程实践）团队要上线一个多 agent 产品，有人主张直接上 Temporal，有人主张 FastAPI + Postgres。你如何决策？给出升级到 durable-execution 引擎的具体触发条件。

**Q16.**（场景设计）设计一个支持 2,000 个并发"深度研究" agent 的系统：每个运行 10 分钟到 3 小时，约 20% 需要等待人工审批（可能等一整夜），每周发布两次。请给出存储、队列、执行模型、部署与可观测性方案。

**Q17.**（追问型）LLM 调用本身是非确定性的，"确定性重放"怎么做到？如果恢复时重新调用 LLM 得到了不同的结果，会出什么问题？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义 "Requirements for this to work"：Serializable state（带活数据库连接的闭包无法存活）、Deterministic resume（相同状态和输入产生相同动作，或把 LLM 调用交给外部确定性来源）、Idempotent side effects（外部调用幂等或带去重键）。
- A 是具体技术选型，不是前提；
- C 中"单一 worker、内存状态"恰恰无法从崩溃中恢复；
- D 与讲义无关。

### Q2 — 答案：D

讲义："For paid agent runs, you need 'exactly-once effective' (at-least-once delivery + idempotent consumer)"，手段是每次运行的去重键、outbox 模式、补偿事务。
- A：在会崩溃、会超时的分布式环境里，投递层无法保证恰好一次；
- B：关闭重试会丢消息；
- C：与幂等性无关。

### Q3 — 答案：A

讲义："For loads under ~100 concurrent agent-runs on manageable tasks, this is often all you need. Upgrade when you measure it failing." 技能文件也把"给 10 个并发运行的原型推荐 Temporal"列为硬拒绝。B、C、D 都与讲义相反或无关。

### Q4 — 答案：C

讲义描述的 MegaAgent：`state ∈ {Idle, Processing, Response}`、`in_queue`/`out_queue`，协调分为组内聊天（intra-group chat）与组间 admin 聊天（inter-group admin chat），组内密集、组间稀疏，使成本在数千 agent 规模下保持线性。A、B、D 都不是论文描述的结构。

### Q5 — 答案：D

实际输出：

```text
    worker crashes at super_step=3
  last checkpoint: super_step=2, state={'counter': 3}
  worker 2 resumes thread t-1
  worker 2 completed; final counter = 5
```

worker 1 成功执行 step 0、1、2（counter 变为 1、2、3 并各写一行），在 step 3 开始时崩溃。worker 2 读到 `(2, {'counter': 3})`，从 `super_step = 3` 继续，写 step 3、4，counter 到 5。
- A 错：step 3 没有写出；
- B 错：恢复不会重复已完成的步，最终是 5；
- C 错：有 3 个 checkpoint。

### Q6 — 答案：B

每条消息需要 3 次 `step()`：IDLE → PROCESSING（只是切换状态）、PROCESSING → RESPONSE（真正出队并产出回复）、RESPONSE → IDLE。两条消息共 6 次。demo 调用了 7 次，第 7 次因为队列已空，停在 `idle`。
- A、C 低估了状态机的步数；
- D 是 demo 的调用次数，不是"至少需要"的次数。

### Q7 — 答案：A

本环境实测：`async (asyncio): 0.054 s`、`threads: 0.089 s`、`ratio: threads are 1.7x slower`。`time.sleep` 会释放 GIL，500 个线程是真正并发等待的，所以线程版也远小于 25 s。讲义"thread version takes several seconds"在这个 demo 中不成立（具体数值因机器而异）。
- B 是串行执行的耗时；
- C、D 与实测不符。

### Q8 — 答案：C

讲义："multiple versions of the agent runtime run concurrently so long-running agents do not have to be killed on every code deploy. Canary new versions on a slice of traffic; retire old versions when their agents finish." 技能文件把"多小时 agent 运行使用单版本部署"列为硬拒绝。A、B 是望文生义；D 恰好是 rainbow 要避免的。

### Q9 — 参考答案

1. step 0、1、2 各扣一次；step 3 扣费后崩溃，checkpoint 没写；worker 2 从 step 3 重新执行，再扣一次，然后 step 4 再扣一次。总共 **6 次**，step 3 被重复扣费（实测结果正是 `['t-1:0', 't-1:1', 't-1:2', 't-1:3', 't-1:3', 't-1:4']`）。这就是"至少一次执行"的本质：checkpoint 之间的工作可能重做。

2. 修复：为每个副作用生成确定性的去重键 `f"{thread_id}:{super_step}"`，执行前检查是否已执行：

```python
key = f"{thread_id}:{super_step}"
if not already_done(key):          # 查询持久化的去重表
    charge(user, amount, idempotency_key=key)
    mark_done(key)
```

实测加去重后扣费为 5 次（`t-1:3` 只出现一次）。**去重记录必须持久化**，不能是进程内存（真实崩溃会丢失）。最稳妥的做法有两种：
- 把去重键交给外部服务（大多数支付 API 支持 idempotency key），由对方保证同一个键只扣一次；
- outbox 模式：在**同一个数据库事务**里写入 checkpoint 和"待执行的副作用"行，再由独立的执行器读取 outbox 执行并标记完成；执行器本身也用去重键，确保重试安全。

3. `INSERT OR REPLACE` 让同一个 `(thread_id, super_step)` 写两次时**覆盖**而不是报错（实测写两次后表中仍只有 1 行，内容为后一次）。对"重做同一步"的恢复是好事：重放后的 checkpoint 写入是幂等的，不会因主键冲突失败。代价是它会静默覆盖——如果两个 worker 并发执行同一步并写出不同的状态，后写者赢，冲突被掩盖（见 Q10）。

### Q10 — 参考答案

1. 两个 worker 都会读到同一个最新 checkpoint，都从同一个 super_step 开始执行，各自重复执行全部剩余步骤（以及其中的副作用），并通过 `INSERT OR REPLACE` 互相覆盖 checkpoint。结果：副作用加倍、状态取决于谁最后写。

2. 参考实现（已在 SQLite 上测试：w1 在 t=100 获得；w2 在 t=110 失败；租约 30 s 过期后 w2 在 t=131 获得；w1 在 t=132 失败）：

```python
def acquire(conn, thread_id: str, owner: str, ttl: float = 30.0, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    conn.execute("INSERT OR IGNORE INTO leases VALUES (?, NULL, 0)", (thread_id,))
    cur = conn.execute(
        "UPDATE leases SET owner = ?, expires_at = ? "
        "WHERE thread_id = ? AND (owner IS NULL OR owner = ? OR expires_at < ?)",
        (owner, now + ttl, thread_id, owner, now),
    )
    conn.commit()
    return cur.rowcount == 1
```

"检查 + 设置"必须在**同一条** `UPDATE` 语句里完成（数据库保证原子性），然后用 `rowcount` 判断是否真的更新了那一行。若写成"先 SELECT 看看有没有人持有，再 UPDATE"，两个 worker 可能同时看到"没人持有"，再同时写入——经典的 check-then-act 竞态。

3. 不能完全防止。持有者可能因为 GC 停顿、网络分区等"以为自己还持有"，但租约已过期、被别人接手，于是两边同时在跑。还需要：
   - **续约**（heartbeat）：长步骤执行期间定期延长租约；
   - **fencing token**：每次获得租约时递增一个版本号，写 checkpoint 时带上并校验（`WHERE lease_version = ?`），过期持有者的写入会被拒绝；
   - **幂等副作用**：即使出现重复执行，外部效果也不会翻倍（Q9）。

### Q11 — 参考答案

1. 逐步追踪（与实际输出一致）：

| 第几次 step | state | in | out |
|-----------|-------|----|-----|
| 初始 | idle | 2 | 0 |
| 1 | processing | 2 | 0 |
| 2 | response | 1 | 1 |
| 3 | idle | 1 | 1 |
| 4 | processing | 1 | 1 |
| 5 | response | 0 | 2 |
| 6 | idle | 0 | 2 |
| 7 | idle | 0 | 2 |

2. 差距：
   - **没有生产者/消费者**：只有一个调用方在同一线程里依次调用 `step()`；没有并发的入队方和处理方；
   - **不是线程/协程安全**：`list` 的并发 `append`/`pop` 没有同步机制；真实实现应使用 `asyncio.Queue` 或消息中间件；
   - **不持久**：进程重启后队列和状态全部丢失，与本节"durability"主题矛盾；
   - **没有失败处理**：处理失败时没有重试、死信队列、超时；
   - **没有两层协调**：MegaAgent 的组内/组间聊天完全没有体现；
   - **没有背压**：`in_queue` 可以无限增长；
   - 所以 Takeaways 的"scale to thousands of concurrent agents"并没有被这段代码证明。

3. `list.pop(0)` 需要把后面所有元素前移一位，是 **O(n)**。应换成 `collections.deque` 的 `popleft()`（O(1)），在异步场景中用 `asyncio.Queue`。

### Q12 — 参考答案

1. `time.sleep` 期间线程会释放 GIL，操作系统可以让 500 个线程同时"睡眠等待"，所以总耗时约等于单次延迟加上线程创建/调度开销，而不是串行相加。同理，LLM 调用是网络 I/O，线程在等待时也会释放 GIL。线程版的额外耗时主要来自**创建和销毁** 500–5000 个线程（耗时随数量近似线性增长：0.11 → 0.25 → 0.67 s），而 async 几乎不随数量增长（0.054 → 0.079 s）。

2. 常驻内存（RSS）估算：线程约 `54.6 MB / 5000 ≈ 11 KB`，协程约 `8.3 MB / 5000 ≈ 1.7 KB`——差约 6–7 倍，不是"几个数量级"。"每线程 1MB（或本机默认 8MB）"指的是线程栈的**虚拟地址空间预留**，操作系统按页按需分配物理内存，线程只用到栈的很小一部分，所以 RSS 远小于预留值。不过虚拟地址空间、内核线程结构、调度开销、`ulimit -u` 等进程/线程数限制依然真实存在，数万线程时会成为瓶颈。另外：原代码只是**打印**了"allocate ~1MB per thread stack"，并没有测量。

3. async 的真正优势：
   - 并发单元极轻（KB 级），数万并发连接仍可控；
   - 创建与切换代价小，适合流式 token、长连接；
   - 取消、超时、`gather` 等结构化并发原语方便。

   async 出问题的场景：CPU 密集的同步代码（embedding、tokenize、大 JSON 解析）或阻塞调用（同步 HTTP 客户端、`time.sleep`）会**阻塞整个事件循环**，所有协程一起卡住。应把它们放进 `asyncio.to_thread`/`run_in_executor` 或进程池（讲义："Separate your I/O layer from your CPU layer"）。

### Q13 — 参考回答要点

- **定义**：执行引擎在每个 super-step（或 activity）后把程序状态持久化，使任何 worker 在任何崩溃后都能接着跑。
- **恢复流程**（讲义）：worker 在某步中途崩溃 → lease 超时 → 另一个 worker 获得该 `thread_id` 的租约 → 读取最新 checkpoint → 从下一步继续 → 借助幂等性保证副作用不重复。
- **前提**：状态可序列化；确定性重放（LLM 结果要记录）；副作用幂等或带去重键。
- **参考实现**：LangGraph（每个 super-step 一行，按 `thread_id` 存 Postgres；`interrupt()` 等待人工）、Temporal（按 activity）、Restate（事件溯源日志）。
- 加分点：说出 checkpoint 粒度的权衡——粒度越细，重做越少，但写放大越大；以及"等待人工时释放 worker"对资源的意义。

### Q14 — 参考回答要点

- **为什么做不到**：发送方无法区分"消息丢了"和"确认丢了"，只能重试；重试就可能重复（Two Generals 问题的工程版本）。所以投递层只能做到至少一次或至多一次。
- **effectively exactly-once = 至少一次 + 幂等消费**：
  - 每次运行/每个副作用一个确定性的去重键（如 `run_id:step`）；
  - 外部 API 支持 idempotency key 时直接传入；
  - 消费端维护持久化的"已处理键"表，与业务写入放在同一事务里。
- **Outbox 模式**：业务状态变更和"要发出的副作用"在同一个本地数据库事务中写入（状态表 + outbox 表）；独立的 relay/执行器轮询 outbox，执行外部调用，成功后标记完成；失败重试，依靠去重键保证幂等。好处是消除了"数据库写成功但消息没发出"或反过来的双写不一致。
- **补偿事务**：外部副作用成功但跟踪写入失败时，安排补偿（如退款）。
- 加分点：讲义指出这些是标准的数据库工程模式，"The LLM tax is only that LLM calls are slow"；技能文件把"付费副作用没有 outbox"列为硬拒绝。

### Q15 — 参考回答要点

- **默认**：Bedi 规则——先用 FastAPI + Postgres（每个运行一行、乐观并发、`pg_notify`/Celery 做后台任务、应用层重试），并在优化前先打点（每次运行延迟直方图、每步耗时、重试次数、失败分类）。
- **升级触发条件**（讲义 Ship It + 技能文件）：
  - 小时级的人工等待（human-in-the-loop），需要 `interrupt`/resume 且释放 worker；
  - 跨区域协调；
  - 复杂的重试/补偿策略；
  - 实测并发与时长超出 Tier 1 的能力（技能文件示例：p99 运行时长超过 10 分钟或并发超过 200 时再考虑升级）。
- **组织条件**：没有 on-call 工程师时，Temporal/LangGraph runtime 的运维投入不足，应留在 Tier 1（技能文件拒绝规则）。
- **决策方式**：用压测数据而非直觉；先列出具体问题，再看引擎能否解决，避免"premature adoption burns time on ceremonies"。

### Q16 — 参考回答要点

- **存储**：Postgres 存运行元数据与 checkpoint（`thread_id, super_step, state`），大对象（检索结果、文档）存对象存储，checkpoint 中只存引用；trace 单独存储（技能文件第 7 步）。
- **执行引擎**：运行时长达数小时、20% 需要隔夜人工等待 → Tier 2（LangGraph runtime 或 Temporal）。等待人工时持久化并释放 worker，审批到达后任意 worker 恢复。
- **队列与 lease**：任务队列 + 每个 `thread_id` 的租约 + 心跳续约 + fencing token。
- **执行模型**：LLM 与工具 I/O 全部 async；embedding、解析等 CPU 工作放到独立的进程池/服务；限制每个 worker 的并发与对模型 API 的速率。
- **副作用**：对外发送邮件、付费 API 调用走 outbox + 去重键。
- **部署**：每周两次发布、运行最长 3 小时且有隔夜等待 → rainbow deployment；按 `thread_id` 绑定运行时版本，新运行灰度到新版本，旧版本等其上的运行全部结束再下线；checkpoint 的状态 schema 需要版本化，以便跨版本恢复。
- **可观测性**：每个 agent 的 trace、super-step 审计、重试计数、队列深度、租约过期次数、等待人工的数量与时长。
- **容量估算**：2,000 并发 × async 的 KB 级开销本身不成问题，瓶颈通常是模型 API 的速率限制与成本。

### Q17 — 参考回答要点

- **做法**：把 LLM 调用当作"外部副作用"处理——第一次执行时把请求与**响应**记录进日志/checkpoint（事件溯源，Temporal 的 activity 结果、Restate 的 journal 就是这么做的）；恢复重放时直接读取记录的结果，而不是重新调用。讲义："or defers to an external deterministic oracle for LLM calls"。
- **temperature = 0 不够**：服务端模型版本更新、批处理与浮点非确定性、工具返回值变化都可能导致结果不同。
- **重新调用得到不同结果的问题**：
  - 后续步骤基于新结果走了不同的分支，与已经执行的副作用（例如已发送的邮件、已扣的费）不一致；
  - checkpoint 之后的状态与重放出来的状态冲突，审计日志对不上；
  - 计费重复（又调了一次 LLM）。
- **工程建议**：checkpoint 在每次 LLM 调用之后写；记录模型版本、prompt 与参数；对需要可复现的流程固定模型版本。
- 加分点：说明"确定性"指的是**编排逻辑**的确定性（相同的历史产生相同的下一步决策），非确定性的部分都要被记录下来作为输入。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 09 并行、Swarm 与网络化架构](../../09-parallel-swarm-networks/docs/zh.md)：讲义列出的先修课，并行执行的基础。
- [阶段 16 · 13 共享记忆与黑板模式](../../13-shared-memory-blackboard/docs/zh.md)：讲义列出的先修课，共享状态的组织方式。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：LangGraph checkpoint 的单 agent 版本。
- [阶段 14 · 29 生产运行时：队列、事件与定时任务](../../../14-agent-engineering/29-production-runtimes/docs/zh.md)：队列与事件驱动的运行时基础。
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../../15-autonomous-systems/12-durable-execution/docs/zh.md)：长时运行 agent 的持久执行。

### 本节被哪些后续内容用到
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：生产中多 agent 的失效分类与级联错误。
- [阶段 16 · 25 案例研究与 2026 年前沿进展](../../25-case-studies-2026-sota/docs/zh.md)：真实系统的扩展经验。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)：rainbow/canary 部署的展开。
- [阶段 17 · 22 对 LLM APIs 进行负载测试：为什么 k6 与 Locust 会产生误导](../../../17-infrastructure-and-production/22-load-testing-llm-apis/docs/zh.md)：Bedi 规则要求的"先测量再升级"。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../../15-autonomous-systems/16-checkpoints-rollback/docs/zh.md)：checkpoint 在回滚与安全上的用途。

### 延伸关键词
`durable execution` · `super-step` · `thread_id` · `lease / heartbeat` · `fencing token` · `idempotency key` · `outbox pattern` · `event sourcing` · `at-least-once delivery` · `compensating transaction` · `rainbow deployment` · `asyncio` · `GIL` · `backpressure` · `dead-letter queue` · `Temporal` · `Restate`
