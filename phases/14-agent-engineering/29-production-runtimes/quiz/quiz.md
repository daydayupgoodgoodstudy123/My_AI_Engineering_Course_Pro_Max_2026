# 测验 · 生产运行时：队列、事件与定时任务（Production Runtimes: Queue, Event, Cron）

> **阶段 14 · Agent 工程 · 第 29 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 六种运行时形态 | request-response、streaming、durable execution、queue-based / background、event-driven、scheduled；**先选形态，再选框架** |
| 2 | Request-response | 同步 HTTP，用户等待结果；只适合短任务（< 30s）；代表栈 Agno（Python + FastAPI）、Mastra（TypeScript） |
| 3 | Streaming | SSE / WebSocket 渐进输出，LiveKit 扩展到 WebRTC 语音；观测首 token 延迟、逐块耗时、尾延迟 |
| 4 | Durable execution | 每一步后 checkpoint 状态，失败后自动从最后一步恢复；LangGraph 的核心差异点；步数未知且重启成本高时必需 |
| 5 | Queue-based | 任务入队 → worker 拉取 → 结果经 webhook / pub-sub 回流；长程 Agent 必需（讲义引用 Anthropic：每任务"dozens-to-hundreds of steps"）；观测队列深度、单任务耗时分布、DLQ 大小 |
| 6 | Event-driven | Agent 订阅触发器（新邮件、PR 打开、cron 触发）；Claude Managed Agents、CrewAI Flows；观测触发源、事件到启动延迟 |
| 7 | Scheduled | cron 形态的周期性 Agent，与 durable execution 组合，让失败的夜间任务在下一次触发时恢复；skill 要求加锁防止重叠运行 |
| 8 | Observability 是承重墙 | 没有 OTel GenAI span + Langfuse/Phoenix/Opik 后端，就无法调试在第 40 步失败的多步 Agent——"快速调试"与"加日志从头重跑"的区别 |
| 9 | 四种失败方式 | 形态选错（5 分钟任务用同步请求）、没有 DLQ（失败任务消失）、后台工作不导出 trace、跳过 durable 状态（> 30s 且不能重启的任务） |
| 10 | 本节代码的关键缺陷 | `worker` 每次尝试调用 `fail_policy` **两次**，随机失败时约 10% 的任务进 DLQ 且多数从未重试；"streaming" 是先算完再逐条 yield 的伪流式 |

### 核心技能（能动手做到）

- [ ] 给定任务的时长、步数、触发方式和延迟预算，选出运行时形态，并说明是否需要叠加 durable execution
- [ ] 读懂 `QueueRuntime.worker` 的重试与 DLQ 逻辑，手推任意失败策略下的输出序列
- [ ] 找出并修复"失败判定被调用两次"的 bug，用 10% 随机失败做模拟并解释 DLQ 数量（讲义练习 2）
- [ ] 把伪流式改造成真正的生成器流式，并设计带 backpressure 的流式输出（讲义练习 4）
- [ ] 为事件总线补上"无订阅者事件"与"处理器异常"的处理；为定时任务加分布式锁
- [ ] 列出每种形态必须采集的可观测性指标

---

## 二、基础自测（选择题）

**Q1.** 下列哪一项**不是**讲义列出的六种生产运行时形态之一？

- A. GPU 弹性伸缩（GPU autoscaling）
- B. Durable execution
- C. Event-driven
- D. Scheduled

**Q2.** 讲义认为 request-response（同步 HTTP）形态只适用于：

- A. 任何任务，只要配合足够大的超时时间
- B. 需要数百步的长程任务
- C. 短任务（大约 30 秒以内），用户等待结果
- D. 必须保证可从失败中恢复的任务

**Q3.** Durable execution 的核心性质是：

- A. 所有任务都在内存中执行以提高速度
- B. 每一步之后 checkpoint 状态，失败时从最后一个成功的步骤自动恢复
- C. 每个任务至少重试 3 次
- D. 只在 cron 任务中使用

**Q4.** 讲义所说"observability is load-bearing"（可观测性是承重的）指的是：

- A. 可观测性系统会增加服务器负载，需要单独扩容
- B. 只有在出现事故后才需要接入可观测性
- C. 日志越多越好
- D. 没有 OTel GenAI span 和 Langfuse/Phoenix/Opik 等后端，就无法调试一个在第 40 步失败的多步 Agent；这在生产中不是可选项

**Q5.** 运行本节代码，任务 `long job B` 每次都失败。它在进入 DLQ 之前**一共被尝试了几次**？

- A. 1 次
- B. 2 次
- C. 3 次
- D. 4 次

**Q6.** 讲义列出的 "No DLQ" 失败方式，后果是：

- A. 失败的任务悄无声息地消失
- B. 队列深度无限增长
- C. 成功的任务被重复执行
- D. worker 无法启动

**Q7.** 按 outputs 中的 skill，cron 形态的 Agent 必须配套什么？

- A. 改成同步请求以便观察
- B. 每次运行都重新部署
- C. 去掉重试，避免重复
- D. 锁文件或分布式锁，防止两次运行重叠；并与 durable execution 组合，让失败的运行能在下次触发时恢复

**Q8.** 本节的 `streaming` 函数如下。若 `_agent_fn` 整体需要 10 秒，客户端收到**第一个** chunk 大约在多少秒之后？

```python
def streaming(input_text: str) -> Iterable[str]:
    for step in _agent_fn(input_text):
        yield step
```

- A. 约 0 秒，因为生成器立即返回第一个值
- B. 约 10 秒，因为 `_agent_fn` 先算完全部步骤并返回列表，之后才开始 yield
- C. 约 2 秒（10 秒 / 5 步）
- D. 无法确定，取决于网络

---

## 三、动手 / 代码题

**Q9.** 阅读队列 worker：

```python
    def worker(self, fail_policy: Callable[[Job], bool]) -> list[tuple[str, str]]:
        results: list[tuple[str, str]] = []
        while self.queue:
            job = self.queue.popleft()
            job.attempt += 1
            if fail_policy(job) and job.attempt < 3:
                self.queue.append(job)
                results.append((job.jid, "retry"))
                continue
            if fail_policy(job):
                self.dlq.append(job)
                results.append((job.jid, "DLQ"))
                continue
            steps = _agent_fn(job.payload)
            results.append((job.jid, steps[-1]))
        return results
```

讲义练习 2 要求"模拟 10% 的任务失败，并展示 DLQ 大小"。把 `fail_policy` 换成 `lambda job: random.random() < 0.10`，入队 1,000 个任务。

1. 如果每次尝试的失败判定**只做一次**、最多尝试 3 次，DLQ 的期望大小是多少？
2. 用原代码，DLQ 的期望大小大约是多少？其中多大比例的任务**在第 1 次尝试就进了 DLQ**？请推导。
3. 修复这个 bug。

**Q10.** 继续看 `worker`：

1. `job = self.queue.popleft()` 发生在执行任务**之前**。如果 worker 进程在 `_agent_fn` 执行到一半时被 OOM 杀掉，这个任务会怎样？这属于哪种投递语义？
2. 重试时 `self.queue.append(job)` 立即放回队尾。这对"下游 API 限流导致的失败"有什么问题？
3. DLQ 里只存了 `Job` 本身。运维人员排查时还缺什么信息？
4. 给出生产级队列 worker 应有的四个机制。

**Q11.** 讲义练习 4："实现带 backpressure 的 streaming：客户端慢时暂停 Agent。这与 turn budget 如何相互作用？"

1. 先把 `_agent_fn` / `streaming` 改成**真正的**流式（每完成一步就 yield 一步）。
2. 用生成器说明 backpressure 是如何"天然"实现的。
3. 如果 Agent 被暂停在一次 LLM 调用的中途、或客户端断开，turn budget 与资源会出现什么问题？给出处理方案。

**Q12.** 阅读事件总线与"定时任务"：

```python
    def publish(self, event_type: str, payload: str) -> list[tuple[str, str]]:
        results: list[tuple[str, str]] = []
        for handler in self.subscribers.get(event_type, []):
            results.append((event_type, handler(payload)))
        return results
...
    schedule = [
        ("02:00", "memory.consolidate"),
        ("03:00", "eval.nightly"),
    ]
    for when, event in schedule:
        print(f"  {when}: would fire {event}")
```

1. 如果 cron 真的在 03:00 发布 `eval.nightly`，会发生什么？
2. 如果某个事件有两个处理器，第一个抛异常，第二个会执行吗？
3. 写一个最小的 `Scheduler`：到点时把事件发布到 `EventBus`；同一事件上一次还没结束时不重复触发（锁）；没有订阅者的事件记入"未处理事件"列表。

---

## 四、面试高频题

**Q13.**（基础必考）生产环境中 Agent 有哪几种运行时形态？分别适合什么任务？

**Q14.**（原理深挖）什么是 durable execution？它和"失败了就整体重试"有什么本质区别？实现它需要解决哪些问题（尤其是副作用）？

**Q15.**（工程实践）设计一个处理"每天数千个代码审查请求、每个请求 2–10 分钟、有数十步工具调用"的 Agent 后台系统。说明队列、重试、DLQ、durable 状态和可观测性的设计。

**Q16.**（场景设计）用户反馈"昨晚的夜间评测报告没有生成"，但系统没有任何告警。你会如何排查？事后应该补上哪些机制？

**Q17.**（追问型）什么时候应该把自托管的长程 Agent 迁移到托管服务（如讲义提到的 Claude Managed Agents）？迁移前需要评估什么？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Production agents run on six runtime shapes: request-response, streaming, durable execution, queue-based background, event-driven, and scheduled." GPU 弹性伸缩是推理基础设施层的话题（阶段 17），不是 Agent 运行时形态。B、C、D 都在六种之中。

### Q2 — 答案：C

讲义："Synchronous HTTP. User waits for completion. Only viable for short tasks (<30s)." A 正是讲义批评的 "Wrong shape choice. Picking request-response for a 5-minute task. Users hang up; workers pile up; retries compound."；B 应该用 queue-based；D 应该用 durable execution。

### Q3 — 答案：B

讲义："State checkpointed after every step; auto-resumes on failure... Essential when step count is unknown and recovery cost is high." A 与"持久"相反——内存状态在进程崩溃时会丢失；C 是重试策略，不是 durable；D 错，cron 只是可以**组合** durable execution。

### Q4 — 答案：D

讲义："Without OpenTelemetry GenAI spans (Lesson 23) plus a Langfuse/Phoenix/Opik backend (Lesson 24), you cannot debug a multi-step agent that failed at step 40. This is not optional for production." "Load-bearing" 是建筑比喻：承重墙拆掉房子就塌了。A 是字面误读；B、C 都不是讲义的意思。

### Q5 — 答案：C

实际输出：

```text
  j001: final: answered long job A
  j002: retry
  j003: final: answered long job C
  j002: retry
  j002: DLQ
```

第 1 次尝试（attempt=1 < 3）→ retry；第 2 次（attempt=2 < 3）→ retry；第 3 次（attempt=3，不满足 `< 3`）→ 第二个 `if fail_policy(job)` 为真 → DLQ。共尝试 3 次、重试 2 次。注意 j002 重试时被放回队尾，所以 j003 先于 j002 的第二次尝试完成。

### Q6 — 答案：A

讲义："No DLQ. Queue workers without dead-letter. Failed jobs vanish." skill 的 hard reject 同样写着 "Queue-based without DLQ. Failed jobs vanish."。DLQ 是失败任务的"停车场"，让人能看到、排查、重放。B 是无限重试的后果；C 与 DLQ 无关。

### Q7 — 答案：D

skill："For cron: lock file or distributed lock to prevent overlapping runs"，拒绝规则："If the user wants cron + no lock, refuse. Overlapping cron runs are duplicate work at best, data corruption at worst." 讲义："Combine with durable execution so a failing nightly run resumes next tick." A、B、C 都与讲义无关或相反。

### Q8 — 答案：B

`_agent_fn` 返回的是一个**已经算好的列表**，`for step in _agent_fn(input_text)` 要等整个函数执行完才开始迭代。所以第一个 chunk 要等全部工作完成后才发出——首 token 延迟等于总延迟，这是"伪流式"。我们把 `_agent_fn` 替换成一个 sleep 0.2 秒的版本实测，`next(g)` 在约 0.2 秒后才返回。A 只在 `_agent_fn` 本身是生成器时成立；C 是真正流式下的期望。

### Q9 — 参考答案

1. **正确实现**：任务只有连续 3 次都失败才进 DLQ，概率 `0.1³ = 0.001`，1,000 个任务期望约 **1 个**。修复后用 3 个随机种子实测为 2、1、1。
2. **原代码**：每次尝试调用了两次 `fail_policy`，两次结果独立：
   - 第 1 次尝试：第一次判定为"成功"（0.9）但第二次判定为"失败"（0.1）→ 直接进 DLQ，概率 `0.9 × 0.1 = 0.09`；
   - 第 2 次尝试进 DLQ：`0.1（第 1 次重试）× 0.9 × 0.1 = 0.009`；
   - 第 3 次尝试进 DLQ：`0.1 × 0.1 × 0.1 = 0.001`（此时第一个 `if` 因 attempt=3 不成立，只看第二次判定；同时第一个判定调用仍会被求值并消耗一次随机数）；
   - 合计约 `0.1`，即 1,000 个任务约 **100 个**进 DLQ，其中约 90% 在第 1 次尝试就进了 DLQ、**从未被重试**。
   - 实测（3 个种子）：DLQ 大小 100、87、89；第 1 次尝试就进 DLQ 的分别是 88、79、84 个。比正确值高出约两个数量级。
   - 另外一个副作用：失败判定为"成功"时任务会被执行；而判定为"失败"时，同一次尝试里还会再调用一次——如果 `fail_policy` 代表真实的执行（如调用外部 API），这意味着**同一步被执行两次**。
3. 修复：每次尝试只判定一次，并把最大尝试次数参数化。

```python
    def worker(self, fail_policy, max_attempts: int = 3):
        results = []
        while self.queue:
            job = self.queue.popleft()
            job.attempt += 1
            failed = fail_policy(job)               # 只求值一次
            if failed and job.attempt < max_attempts:
                self.queue.append(job)
                results.append((job.jid, "retry"))
            elif failed:
                self.dlq.append(job)
                results.append((job.jid, "DLQ"))
            else:
                results.append((job.jid, _agent_fn(job.payload)[-1]))
        return results
```

   对演示中确定性的 `fail_b`，修复前后输出完全相同（已实测），所以这个 bug 在演示里看不出来——只有做讲义练习 2 的随机失败时才暴露。

### Q10 — 参考答案

1. 任务在 `popleft()` 时就已经离开队列，进程崩溃后它既不在队列里也不在 DLQ 里，**彻底丢失**。这是 **at-most-once**（至多一次）投递。生产队列（SQS、BullMQ、Celery 的 `acks_late`）采用 **at-least-once**：worker 先"租用"任务（visibility timeout），完成后再 ack 删除；超时未 ack 的任务自动重新可见。
2. 立即重试会在限流窗口内反复撞墙，三次尝试可能在几毫秒内全部用完，然后进 DLQ——实际上只要等几秒就能成功。应使用**指数退避 + 抖动**（exponential backoff with jitter），并区分可重试错误（429、超时）与不可重试错误（400 参数错误，直接进 DLQ）。
3. DLQ 只记录了 `jid`、`payload`、`attempt`，缺少：每次失败的错误类型与信息、失败时间、所在步骤、trace ID（用于跳转到 Langfuse/Phoenix 查看完整执行过程）。讲义："Opaque background work... Failures are invisible until the user reports them."
4. 生产级 worker 机制：
   - **ack / visibility timeout**：保证 at-least-once，崩溃不丢任务；
   - **幂等性**：因为 at-least-once 会重复投递，任务与副作用需要幂等键；
   - **退避重试 + 错误分类**，超过上限进 DLQ 并记录原因，DLQ 支持重放；
   - **可观测性**：队列深度、单任务耗时分布、DLQ 大小（讲义列出的三个指标），以及每个任务的 trace 导出；
   - 长任务再叠加 **durable execution**：失败后从最后一步恢复，而不是从头重跑。

### Q11 — 参考答案

1. 真正的流式：

```python
def agent_steps(input_text):
    yield f"parse: {input_text[:40]}"
    yield "plan: 3-step plan"
    yield "step 1: search"          # 每完成一步立即交出
    yield "step 2: read"
    yield f"final: answered {input_text[:20]}"

def streaming(input_text):
    yield from agent_steps(input_text)
```

2. 生成器是**拉模式**：只有消费者调用 `next()`，生成器才会继续执行到下一个 `yield`。客户端慢 → 服务端发送缓冲区满 → 服务端不再 `next()` → Agent 自然停在 `yield` 处，不会继续调用工具和 LLM。这就是 backpressure（背压）。在 asyncio / SSE 框架中对应 `await response.write()` 的阻塞。
3. 问题与方案：
   - Agent 暂停期间仍占用连接、内存，可能持有锁或数据库事务；暂停时间应计入超时，超过上限就中止。
   - LLM 调用本身无法"暂停一半"——它要么完成要么取消，暂停只能发生在步骤之间；已经发出的 LLM 请求仍会产生费用。
   - turn budget（轮次/步数预算）通常按"步数"计，与墙钟时间无关；但若预算按时间计，客户端慢会让 Agent 无辜地耗尽预算。应把"Agent 工作时间"与"等待客户端时间"分开计量。
   - 客户端断开时：要能检测（`GeneratorExit` / 连接关闭事件）并取消后续步骤；若任务有价值，转为后台队列任务继续（结果通过 webhook 返回），这需要 durable 状态才能无缝衔接。

### Q12 — 参考答案

1. `eval.nightly` 没有任何订阅者，`self.subscribers.get(event_type, [])` 返回空列表，`publish` 返回 `[]`（已实测）——**事件被静默丢弃，不报错、不记录**。这正是 Q16 场景的典型根因。另外，演示中的 schedule 只是 `print`，根本没有和 `EventBus` 连起来。
2. 不会。第一个处理器抛出的异常直接从 `publish` 传播出去，后面的处理器不再执行（已实测：抛出 `RuntimeError: boom`）。应对每个处理器做异常隔离，并把失败记入事件的 DLQ。
3. 参考实现：

```python
import threading
from dataclasses import dataclass, field

@dataclass
class Scheduler:
    bus: EventBus
    schedule: list[tuple[str, str]]
    unhandled: list[tuple[str, str]] = field(default_factory=list)
    locks: dict[str, threading.Lock] = field(default_factory=dict)

    def tick(self, now: str) -> list[tuple[str, str]]:
        fired = []
        for when, event in self.schedule:
            if when != now:
                continue
            lock = self.locks.setdefault(event, threading.Lock())
            if not lock.acquire(blocking=False):          # 上一次还在跑：跳过
                fired.append((event, "skipped: previous run still active"))
                continue
            try:
                if not self.bus.subscribers.get(event):
                    self.unhandled.append((now, event))   # 无订阅者：记录而不是丢弃
                    fired.append((event, "unhandled"))
                    continue
                fired.extend(self.bus.publish(event, f"tick@{now}"))
            finally:
                lock.release()
        return fired
```

   要点：单机用进程内锁仅作演示，多副本部署时必须用分布式锁（Redis、数据库行锁、Kubernetes CronJob 的 `concurrencyPolicy: Forbid`）；"未处理事件"应触发告警。

### Q13 — 参考回答要点

| 形态 | 适合 | 关键观测 |
|------|------|---------|
| Request-response | < 30s、用户等待的短任务（聊天式 UX） | HTTP 日志 + OTel span |
| Streaming | 需要渐进输出、语音/视频 | 首 token 延迟、逐块耗时、尾延迟 |
| Durable execution | 步数未知、重启代价高的长任务 | checkpoint 状态、恢复次数 |
| Queue-based | 分钟到小时级、用户不等待 | 队列深度、单任务耗时分布、DLQ 大小 |
| Event-driven | 对外部事件反应（新邮件、PR） | 触发源、事件到启动延迟 |
| Scheduled | 周期性维护（记忆整理、评测、成本报告） | 是否按时运行、运行时长、重叠 |

- 讲义原则："Pick the shape before you pick the framework."；durable 可以叠加在其他形态之上。
- 加分点：列举栈——Agno/Mastra（request-response）、LiveKit/Pipecat（流式语音）、LangGraph（durable）、Celery/BullMQ/SQS（队列）、CrewAI Flows/Claude Managed Agents（事件）、Kubernetes CronJob（定时）。

### Q14 — 参考回答要点

- **定义**：每一步执行后把状态持久化（checkpoint），进程崩溃或机器重启后从最后一个完成的步骤继续。
- **与整体重试的区别**：整体重试会从第 1 步重新开始——重复花费前面所有 LLM 调用的成本和时间，且重新执行有副作用的步骤（再发一次邮件、再创建一次 PR）；长程任务（数十到数百步）几乎不可能一次跑通。skill："'No durable state, we'll just retry.' Long horizons must checkpoint."
- **要解决的问题**：
  - 状态序列化（对话历史、工具结果、计划）与存储后端（数据库、对象存储）；
  - 副作用的幂等：恢复时如何知道"第 37 步的发送邮件是否已经成功"——需要幂等键或"先记录意图、再执行、再记录完成"；
  - LLM 的非确定性：恢复后重新调用 LLM 可能得到不同结果，因此已完成步骤的输出必须持久化，而不是重算；
  - 版本兼容：代码升级后旧 checkpoint 还能否恢复。
- 加分点：讲义提到 AutoGen v0.4 的 actor 模型把失败隔离在单个 Agent 内；LangGraph 的 checkpointer 是其核心差异点（Lesson 13）。

### Q15 — 参考回答要点

- **形态**：2–10 分钟、数十步、用户不等待 → queue-based + durable execution；入口用 webhook（PR 事件）触发，即事件驱动 + 队列。
- **队列**：SQS/BullMQ/Celery；at-least-once + visibility timeout；按仓库或租户做公平调度，避免单个大客户占满 worker。
- **重试**：区分可重试（429、超时、5xx）与不可重试错误；指数退避 + 抖动；最多 N 次后进 DLQ，DLQ 条目包含错误、步骤、trace ID，支持一键重放。
- **durable 状态**：每步 checkpoint；发布评论等副作用用幂等键（例如 `review_id + step`）；恢复时跳过已完成步骤。
- **可观测性**：每个任务一条 trace（OTel GenAI span），导出到 Langfuse/Phoenix；指标——队列深度、等待时间、单任务耗时分布、成功率、DLQ 大小、每任务 token 成本；告警阈值。
- **容量**：按"每天数千 × 平均 6 分钟"估算并发 worker 数（例如 3,000 × 6 分钟 = 18,000 worker·分钟/天，均摊约 12.5 个并发，按峰值系数放大）。
- 常见误区：把 10 分钟的任务挂在同步 HTTP 请求上（讲义："Users hang up; workers pile up; retries compound"）。

### Q16 — 参考回答要点

- **排查顺序**：
  1. 调度器是否触发了？查 cron 日志 / Kubernetes CronJob 历史（可能节点重启、调度器挂掉）；
  2. 事件是否发布、是否有订阅者？（本节代码中 `eval.nightly` 就没有订阅者，事件被静默丢弃）；
  3. 任务是否入队、是否被 worker 取走、是否在 DLQ 中？
  4. 是否与上一次运行重叠而被锁跳过，或因为没加锁导致两次运行互相覆盖？
  5. 运行是否在中途失败——看 trace 停在哪一步。
- **补上的机制**：
  - "应当发生的事件没有发生"的告警（dead man's switch / heartbeat 监控），而不只是"发生了错误"的告警；
  - 无订阅者事件、处理器异常都记录并告警；
  - DLQ 大小告警；
  - cron 加锁 + durable execution，失败的运行在下一次触发时恢复；
  - 后台任务必须导出 trace（讲义："Opaque background work"）。

### Q17 — 参考回答要点

- 讲义：Claude Managed Agents 是"Anthropic-hosted long-running async with caching + compaction"，开箱支持事件驱动。
- **适合迁移的信号**：自建的队列、durable 状态、上下文压缩、缓存等基础设施维护成本高；团队精力应放在业务逻辑；任务形态与托管服务支持的形态一致。
- **评估项**：
  - 数据与合规：代码、客户数据能否交给托管方处理，数据驻留要求；
  - 可观测性：能否导出 trace 到现有后端；
  - 工具接入：私有网络内的工具/数据库如何访问；
  - 成本模型：按用量计费 vs 自建的 worker 成本；
  - 锁定风险与可迁移性：状态、记忆能否导出；
  - SLA、限流、超时上限是否满足长程任务需求。
- 加分点：先迁移一类低风险的后台任务做试点，对比成功率、延迟与成本，再决定是否全面迁移。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：讲义明确把第六种形态 durable execution 交给这一节。
- [阶段 14 · 22 语音 Agents：Pipecat 与 LiveKit](../../22-voice-agents-pipecat-livekit/docs/zh.md)：streaming 形态在语音场景的延伸。
- [阶段 14 · 14 用于 Agents 的 Actor 模型：异步消息与类型化运行时](../../14-autogen-actor-model/docs/zh.md)：actor 模型的故障隔离。
- [阶段 14 · 18 生产级 Agent 运行时：快速实例化与类型化工作流](../../18-agno-and-mastra-runtimes/docs/zh.md)：Agno 与 Mastra 的 request-response 部署。
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)、[阶段 14 · 24 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik](../../24-agent-observability-platforms/docs/zh.md)："observability is load-bearing" 的具体实现。

### 本节被哪些后续内容用到
- [阶段 14 · 17 将 Harness 封装为库：Subagents 与会话存储](../../17-claude-agent-sdk/docs/zh.md)：讲义中托管长程运行的去处。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：夜间 cron 评测（讲义练习 3）。
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../../15-autonomous-systems/12-durable-execution/docs/zh.md)：durable execution 在自主系统中的深入。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../../15-autonomous-systems/16-checkpoints-rollback/docs/zh.md)：checkpoint 与回滚。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../../16-multi-agent-and-swarms/22-production-scaling-queues-checkpoints/docs/zh.md)：多 Agent 场景下的队列与持久化。
- [阶段 17 · 15 批处理 APIs：作为行业标准的五折优惠](../../../17-infrastructure-and-production/15-batch-apis/docs/zh.md)：不需要实时结果的后台任务的另一种形态。
- [阶段 17 · 23 AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：运行时出故障后的响应。

### 延伸关键词
`request-response` · `SSE / WebSocket` · `backpressure` · `durable execution` · `checkpointer` · `at-least-once / at-most-once` · `visibility timeout` · `idempotency key` · `exponential backoff + jitter` · `DLQ` · `distributed lock` · `dead man's switch` · `Claude Managed Agents`
