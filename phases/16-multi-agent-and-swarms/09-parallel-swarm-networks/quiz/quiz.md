# 测验 · 并行、Swarm 与网络化架构（Parallel / Swarm / Networked Architectures）

> **阶段 16 · 多智能体与集群 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 提示：中文讲义为机器翻译，有几处会误导：把论文名 Matrix 译成"矩阵"、把 orchestrator 译成"管弦乐/指挥员"、把 "100ms" 译成"100米"、把 durable queue 译成"长队列"、把 "Worker idempotency" 后半句译成"工人必须有能力"（应为"worker 必须幂等"）。请对照英文版阅读。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Swarm 的形状 | 没有中央决策者：worker 从共享队列/事件总线拉取任务，处理后写回结果池，必要时再投递后续任务 |
| 2 | 为什么需要 swarm | supervisor 在几个 worker 时可行，到数百个时自己变成瓶颈——"谁做什么"的每个决定都要经过它 |
| 3 | 适用场景 | 大量**相互独立**的子任务、耗时**差异大**、看重吞吐而非顺序 |
| 4 | 不适用场景 | 有严格先后依赖的流程、需要一个连贯全局计划的任务（如研究报告）、需要容易复现和调试的场景 |
| 5 | 自动负载均衡 | 快的 worker 做完立刻拉下一个任务，不需要提前预测耗时；本节演示中 swarm 用 0.50s 达到理想并行时间 |
| 6 | Matrix（arXiv:2511.21686） | 控制流和数据流都是分布式队列上的序列化消息；协作变成"这个 agent 订阅哪个 topic"；用确定性与可追踪性换可扩展性 |
| 7 | 饥饿与热点 | 长任务可能一直轮不到（starvation），或某个 worker 处理了绝大多数任务（hot-spotting）；对策：带 aging 的优先队列、worker 专业化、back-pressure |
| 8 | 生产要求 | 幂等 worker（任务可能被重复拉取）、持久化队列（Kafka / Redis Streams / 数据库）、每任务 trace ID、back-pressure |
| 9 | 线程模拟 I/O | 代码用 `threading` + `time.sleep` 模拟 LLM 调用；`sleep` 会释放 GIL，所以线程能真正并行"等待"，但 CPU 密集任务不行 |
| 10 | 贪心调度不等于最优 | 共享队列本质是"谁空闲谁拿下一个"的 list scheduling；结果依赖队列中的任务顺序，长任务排在后面时可能明显劣于最优 |

### 核心技能（能动手做到）

- [ ] 用 `queue.Queue` + `threading` 写出一个"多个 worker 从共享队列拉任务"的 swarm，并统计每个 worker 的任务数和总耗时
- [ ] 手算顺序执行、固定分配、swarm 三种策略在给定任务集上的 wall-clock 时间
- [ ] 解释为什么本节"固定分配"慢，并指出：如果分配合理（例如轮询），固定分配也能达到同样的 0.50s
- [ ] 用 `queue.PriorityQueue` 实现优先级调度，避开 dataclass 不可比较的坑，并实现 aging 防饥饿
- [ ] 为 swarm 加上崩溃重试、哨兵退出、`q.join()` 等待，使 worker 幂等、任务不丢
- [ ] 根据任务独立性、耗时分布、顺序要求、可调试性要求，判断该用 swarm 还是 supervisor

---

## 二、基础自测（选择题）

**Q1.** Swarm 架构与 supervisor 架构最本质的区别是：

- A. swarm 中每个 agent 使用更强的模型
- B. swarm 只能有 4 个 worker
- C. swarm 没有中央决策者，worker 自己从共享队列/事件总线拉取任务、异步处理、写回结果
- D. swarm 的 worker 之间必须两两直接通信

**Q2.** 下列哪个任务**最适合**用 swarm？

- A. 对 10 万个网页分别做抽取和分类，每页耗时从几百毫秒到十几秒不等，互不依赖
- B. 撰写一份需要统一论点和结构的长篇研究报告
- C. 一个"先建表、再导入数据、再建索引"的严格有序的数据库迁移
- D. 金融审计流程，要求一条完整、可复现的决策轨迹

**Q3.** 运行 `code/main.py`，固定分配（Fixed assignment）的耗时是 1.70s、计数为 `{0: 5, 1: 1, 2: 1, 3: 1}`。worker 0 为什么处理了 5 个任务？

- A. 因为 worker 0 的线程最先启动，抢到了更多任务
- B. 因为固定分配也是从共享队列拉任务
- C. 因为 Python 的 GIL 让其他线程无法运行
- D. 因为 `make_tasks` 把 4 个慢任务都分给 worker 0，而快任务按 `(i - 3) % 4` 分配，第 7 号任务算出 `(7 - 3) % 4 = 0`，也落到了 worker 0；所以它要串行跑 `4×0.4 + 0.1 = 1.7s`

**Q4.** 本节任务集总工作量 2.00 work-seconds、4 个 worker，swarm 实测 0.50s。下面哪个解释正确？

- A. swarm 把每个任务拆成了 4 份并行执行
- B. 队列先放 4 个慢任务：4 个 worker 各拿一个慢任务（0.4s），做完后各拿一个快任务（0.1s），总计 0.5s，恰好等于理想并行时间 2.00 / 4
- C. swarm 跳过了一半任务
- D. swarm 让 `time.sleep` 的时间减半

**Q5.** 代码用 Python 线程模拟并行，CPython 有 GIL，为什么 4 个线程仍能把 2.00s 的工作压到 0.50s？

- A. `time.sleep` 会释放 GIL，线程在"等待"时互不阻塞；这对应 LLM API 调用这类 I/O 密集型工作。若换成纯 CPU 计算，线程几乎得不到加速
- B. CPython 的 GIL 只在主线程上生效
- C. `queue.Queue` 会自动把任务分发到多个 CPU 核心
- D. Python 3.13 已经默认移除了 GIL

**Q6.** 关于 Matrix（arXiv:2511.21686），讲义的描述是：

- A. 它是一个中央 supervisor 框架，用矩阵运算给 worker 分配任务
- B. 它把所有 agent 放进一个群聊，由 LLM 选择下一个发言者
- C. 它要求每个 agent 使用相同的 system prompt
- D. 控制流和数据流都作为序列化消息在分布式队列中传递，没有中央协调者；容错来自消息持久化，用确定性与可追踪性换取可扩展性

**Q7.** 讲义 Ship It 要求 worker 必须**幂等（idempotent）**，主要原因是：

- A. 幂等的 worker 运行更快
- B. worker 处理到一半崩溃时，任务可能被再次拉取执行；同一任务执行两次必须得到同样结果、不产生重复副作用
- C. 幂等能保证任务按顺序完成
- D. 幂等可以替代持久化队列

**Q8.** 讲义提出的缓解"长任务饥饿（starvation）"的手段**不包括**：

- A. 带 aging（等待越久优先级越高）的优先队列
- B. worker 专业化：部分 worker 只接"长"任务
- C. 增加更多同质 worker，让所有 worker 都优先拉最快的任务
- D. back-pressure：限制进入队列的快任务数量

---

## 三、动手 / 代码题

**Q9.** Swarm 是"谁空闲谁拿队首任务"的贪心调度。用本节的 `run_swarm`、4 个 worker，在下面两个任务序列上计算（或运行）wall-clock 时间：

- 序列 ①：12 个 0.1s 任务在前，1 个 1.0s 任务在最后；
- 序列 ②：1 个 1.0s 任务在前，12 个 0.1s 任务在后。

总工作量都是 2.2 work-seconds。哪个更快？最优调度是多少？这对讲义"swarm distributes unevenly but optimally"的说法意味着什么？

**Q10.** 讲义练习 2 要求用 `queue.PriorityQueue` 做优先级。某同学这样写：

```python
pq = queue.PriorityQueue()
for t in tasks:
    pq.put((t.importance, t))   # 数字越小越重要
```

1. 当两个任务的 `importance` 相同时会发生什么？为什么？如何修复？
2. 设计一个模拟：低优先级任务（基础优先级 5）在 tick 0 入队，之后每个 tick 来一个高优先级任务（优先级 1），单 worker 每个 tick 处理一个任务。不做 aging 时低优先级任务何时被处理？若有效优先级 = 基础优先级 − aging_rate × 等待 tick 数，aging_rate 为 0.5 和 0.1 时分别在第几个 tick 被处理（平局时先入队者优先）？

**Q11.** 阅读 `make_tasks` 与 `run_fixed_assignment`：

```python
def make_tasks(n_workers: int = 4) -> list[Task]:
    """8 tasks: half fast (0.1s), half slow (0.4s). Pre-assignment is pessimal:
    worker 0 gets all slow tasks, others get fast ones."""
    tasks: list[Task] = []
    for i in range(8):
        is_slow = i < 4
        tasks.append(
            Task(
                task_id=i,
                duration=0.4 if is_slow else 0.1,
                pre_assigned=0 if is_slow else (i - 3) % n_workers,
            )
        )
    return tasks
```

1. docstring 说"others get fast ones"，实际每个 worker 分到哪些任务？
2. 如果改成轮询分配 `pre_assigned = task_id % 4`，固定分配的耗时是多少？
3. 由此说明：本节"swarm 比固定分配快 3.40×"这个数字到底证明了什么、没证明什么？

**Q12.** 本节 `run_swarm` 的 worker 是这样退出的：

```python
    def worker(wid: int) -> None:
        while True:
            try:
                task = q.get_nowait()
            except queue.Empty:
                return
            fake_work(task)
            with lock:
                counts[wid] += 1
            q.task_done()
```

1. 如果 `fake_work` 抛出异常，会发生什么？任务去哪了？
2. 讲义说 worker 可以"optionally enqueue follow-ups"（投递后续任务）。在这种动态场景下，"队列空就退出"有什么问题？
3. 请改写成：失败任务最多重试 2 次、结果按 `task_id` 写入（重复执行也幂等）、用 `q.join()` 等待全部完成、再用哨兵 `None` 通知 worker 退出。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 swarm（去中心化）多 agent 架构？它和 supervisor 架构各适合什么场景？

**Q14.**（原理深挖）为什么 swarm 能"自动负载均衡"？它在什么情况下会变差？请结合调度理论（list scheduling、LPT）和饥饿/热点问题回答。

**Q15.**（工程实践）把本节的线程 + `queue.Queue` 演示改造成生产系统，你需要补哪些东西？

**Q16.**（场景设计）你要构建一个每天处理 50 万张客服工单的分类 + 摘要 + 路由系统，其中 5% 的工单需要多步调查。你会怎么组合 swarm 与 supervisor？

**Q17.**（追问型）Anthropic 的多 agent 研究系统为什么选择 supervisor（orchestrator-worker）而不是 swarm？Swarm 的"去中心化"在调试上要付出什么代价？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义开头："Contrast with supervisor: no central decider. Agents read a shared event bus, pick up work asynchronously, write results back." 协调被"烘焙"进了事件总线的语义里。A 与架构无关；B 只是本节演示用的数量；D 描述的是全连接网状通信，swarm 的 worker 通常只与队列交互。

### Q2 — 答案：A

独立、耗时差异大、看重吞吐——正好是讲义 "When swarm fits" 的三条。B 需要"single coherent plan"，讲义："A swarm of researchers produces independent facts, not a coherent report."；C 有严格顺序，swarm 可能让第 3 步先于第 2 步执行；D 需要单一连贯的审计轨迹，`skill-swarm-fit` 明确要求此时拒绝 swarm、改用确定性图（如 LangGraph）。

### Q3 — 答案：D

`make_tasks` 中 `i = 0..3` 是慢任务，`pre_assigned = 0`；`i = 4..7` 是快任务，`(i − 3) % 4` 分别为 1、2、3、**0**。所以 worker 0 分到 4 慢 + 1 快，串行耗时 `1.6 + 0.1 = 1.7s`，其他 worker 0.1s 后就闲着。A、B 错：固定分配根本不抢任务，每个 worker 只处理自己的列表；C 错：`sleep` 期间 GIL 已释放。

### Q4 — 答案：B

FIFO 队列里前 4 个是慢任务。4 个线程几乎同时启动，各拿一个慢任务；0.4s 后同时空闲，各拿一个快任务；0.5s 全部完成，计数 `{0: 2, 1: 2, 2: 2, 3: 2}`。这与理想值 `2.00 / 4 = 0.50s` 一致。A 错，任务是不可分割的；C、D 无依据。注意本例 swarm 的分布恰好是**均匀**的，讲义 "swarm distributes unevenly" 在这组数据上并未体现。

### Q5 — 答案：A

`time.sleep` 是阻塞系统调用，执行期间释放 GIL，其他线程可以继续运行。这正好模拟了"agent 大部分时间在等 LLM API 返回"的 I/O 密集场景。B 错：GIL 作用于所有线程；C 错：`queue.Queue` 只是线程安全的队列，不负责调度到 CPU；D 错：Python 3.13 只是提供了可选的 free-threaded 构建，默认构建仍有 GIL。如果 `fake_work` 换成纯 Python 计算循环，线程版本几乎没有加速，需要 `multiprocessing` 或多机。

### Q6 — 答案：D

讲义："both control flow and data flow are serialized messages on distributed queues. No central coordinator. Fault tolerance comes from message durability. Scalability is the message broker's problem, not the system's." 以及 "The tradeoff is explicit: determinism and traceability for scalability." A 是被中文机翻"矩阵"误导的干扰项；B 是群聊（第 10 节）；C 无依据。

### Q7 — 答案：B

讲义："A task may be pulled more than once if a worker crashes mid-run. Workers must be idempotent." 持久化队列通常提供"至少一次（at-least-once）"投递：worker 拿到任务但没来得及确认就崩了，任务会被重新投递。若 worker 有副作用（发邮件、扣款、写数据库），必须用任务 ID 去重或 upsert，保证执行两次和一次效果相同。A、C 与幂等无关；D 错，幂等与持久化是互补的两项要求（`skill-swarm-fit` 两者都列为 hard reject 条件）。

### Q8 — 答案：C

讲义给出的三条缓解措施正是 A、B、D。C 恰恰是饥饿的**成因**："If all workers pull the fastest-available task, long-running tasks never get picked until they are the only ones left."

### Q9 — 参考答案

已用本节 `run_swarm` 实际运行：

| 序列 | wall-clock | 每个 worker 的任务数 |
|------|-----------|---------------------|
| ① 12 快在前，1 慢在后 | ≈ 1.30s | `{0: 4, 1: 3, 2: 3, 3: 3}` |
| ② 1 慢在前，12 快在后 | ≈ 1.00s | `{0: 1, 1: 4, 2: 4, 3: 4}` |

推导：① 4 个 worker 用 0.3s 处理完 12 个快任务，然后其中一个再花 1.0s 处理慢任务，其他 3 个闲着 → 1.3s。② 一个 worker 先拿慢任务（1.0s），其余 3 个在 0.4s 内处理完 12 个快任务 → 1.0s。最优调度的下界是 `max(最长任务, 总量 / worker 数) = max(1.0, 0.55) = 1.0s`，所以 ② 已是最优，① 比最优慢 30%。

结论：共享队列是**贪心的 list scheduling**，它能"自适应"地把任务分给空闲 worker，但结果依赖队列顺序。Graham 的经典结论是贪心 list scheduling 最坏为最优的 `2 − 1/m` 倍（m 为机器数）；把任务按耗时降序排队（LPT，Longest Processing Time first）可以把最坏比降到 `4/3 − 1/(3m)`。因此"unevenly but optimally"应理解为"通常接近最优、无需预知耗时"，而不是"总是最优"。本节演示把慢任务放在队首，恰好就是 LPT 顺序。

### Q10 — 参考答案

1. 优先级相同时，元组比较会继续比较第二个元素 `Task`。`@dataclass` 默认不生成 `<`，于是抛出 `TypeError: '<' not supported between instances of 'Task' and 'Task'`（已实际运行验证）。修复：加一个单调递增的序号做平局裁决，例如

   ```python
   import itertools
   seq = itertools.count()
   pq.put((t.importance, next(seq), t))
   ```

   这样同优先级按入队顺序（FIFO）出队，`Task` 永远不会被比较。也可以用 `@dataclass(order=True)` 并把排序字段放在最前，但用序号更清晰。
2. 模拟结果（已用 Python 运行，50 个 tick）：
   - 不做 aging：低优先级任务**一直没被处理**——每个 tick 都有新的优先级 1 任务到来，5 永远排不到前面，这就是饥饿；
   - aging_rate = 0.5：在第 **8** 个 tick 被处理（`5 − 0.5 × 8 = 1`，与新来的高优先级任务打平，先入队者优先）；
   - aging_rate = 0.1：在第 **40** 个 tick 被处理（`5 − 0.1 × 40 = 1`）。

   aging 把"最长等待时间"从无穷变成有界：`(基础优先级差) / aging_rate`。aging 太快会让优先级失去意义，太慢则长任务等待过久，需要按 SLA 调参。

### Q11 — 参考答案

1. 实际分配：worker 0 → 任务 0、1、2、3（慢）+ 任务 7（快）；worker 1 → 任务 4；worker 2 → 任务 5；worker 3 → 任务 6。docstring 和打印语句 "worker 0 got all 4 slow tasks; other workers idle after their fast ones" 都没提到 worker 0 还多了一个快任务，这才是计数 `{0: 5, ...}` 和 1.70s 的来源（而不是 1.60s）。
2. 轮询分配时每个 worker 恰好 1 慢 + 1 快，耗时 0.50s（已运行验证：`0.50s, {0: 2, 1: 2, 2: 2, 3: 2}`），与 swarm 一样。
3. 3.40× 证明的是"**糟糕的**预分配会被最慢的 worker 拖垮，而 swarm 不需要预测耗时也能避免这一点"。它没有证明"swarm 比任何集中式分配都快"：当耗时已知时，supervisor 用 LPT 或轮询完全可以做到同样好。swarm 真正的优势在于**耗时未知、波动大、任务源源不断**的场景，以及去掉中央调度器这个瓶颈和单点故障。讲义原文也说 "A supervisor has to anticipate duration."

### Q12 — 参考答案

1. 异常会冒出 `worker` 函数，该线程打印 `Exception in thread ...` 后终止：这个任务**丢失**（计数不加、没有结果、没有重试），`q.task_done()` 也没被调用（若有人 `q.join()` 会永远等待）。其他线程继续工作，所以总耗时可能"看起来正常"，问题被静默掩盖。
2. "队列空就退出"在静态任务集上可行，但在动态场景下：worker A 正在处理任务时，其他 worker 发现队列暂时为空就退出了；A 稍后投递的后续任务只能由 A 自己串行处理，并行度丢失。更糟的情况是如果投递者也退出了，任务就无人处理。正确做法是"阻塞等待 + 显式结束信号"。
3. 参考实现（已运行验证：注入"任务 3 第一次执行时崩溃"、任务 0 完成后派生后续任务 100，结果所有任务 `[0..7, 100]` 都完成，无死信）：

   ```python
   def run_swarm_robust(tasks, n_workers, max_retries=2):
       q = queue.Queue()
       for t in tasks:
           q.put((t, 0))                       # (任务, 已重试次数)
       results, dead = {}, []
       lock = threading.Lock()

       def worker(wid):
           while True:
               item = q.get()                   # 阻塞等待
               if item is None:                 # 哨兵：收到才退出
                   q.task_done()
                   return
               task, attempt = item
               try:
                   out = fake_work(task)
                   with lock:
                       results[task.task_id] = out   # 按 task_id 写入，重复执行也幂等
               except Exception:
                   if attempt < max_retries:
                       q.put((task, attempt + 1))    # 重新入队
                   else:
                       with lock:
                           dead.append(task.task_id) # 死信
               finally:
                   q.task_done()                # 无论成败都要确认

       threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_workers)]
       for th in threads:
           th.start()
       q.join()                                 # 等全部任务（含重试、后续任务）完成
       for _ in threads:
           q.put(None)
       for th in threads:
           th.join()
       return results, dead
   ```

   要点：重新入队/派生后续任务发生在当前任务 `task_done()` 之前，所以 `q.join()` 不会提前返回；`finally` 保证确认；死信列表对应生产中的 DLQ（dead-letter queue）。

### Q13 — 参考回答要点

- **定义**：没有中央 orchestrator，worker 订阅共享队列/事件总线，异步拉取任务、处理、写回结果，可投递后续任务。协调靠消息语义（topic、队列类型），而不是"supervisor 选谁"。
- **swarm 适合**：大量独立任务（抓取、转换、分类）、耗时波动大、看重吞吐、规模大到中央调度器会成为瓶颈。
- **supervisor 适合**：任务之间有依赖、需要全局计划和综合（研究报告）、需要清晰可审计的决策轨迹、规模不大。
- **代价**：讲义："The tradeoff is explicit: determinism and traceability for scalability."
- 加分点：说出两者可以组合——supervisor 做规划和综合，执行层用 swarm 扇出；以及 LangGraph 的 "Swarm Architecture" 和 AutoGen v0.4 的 actor 模型更接近 swarm。

### Q14 — 参考回答要点

- **为什么自动均衡**：worker 只在空闲时拉任务，"拉"本身就是根据实时负载做决策；快的 worker 自然多做，不需要预先估计每个任务耗时。本节演示中 swarm 0.50s 即理想值，而糟糕的预分配要 1.70s。
- **什么时候变差**：
  - 队列顺序不好：长任务排在最后，会出现"大家都闲着、只有一个 worker 在跑长任务"的尾部效应（Q9 中 1.30s vs 最优 1.00s）；贪心 list scheduling 最坏为 `2 − 1/m` 倍最优，LPT 排序可改善；
  - 饥饿：若按"最快可用"或固定优先级拉取，长任务/低优先级任务可能永远轮不到（Q10）；
  - 热点：任务耗时呈重尾分布，或某类任务只有少数 worker 能处理，导致个别 worker 处理了大部分任务；讲义练习 3 用"某 worker 任务数 ≥ 最慢 worker 的 3 倍"检测；
  - 生产者快于消费者：队列无限增长，需要 back-pressure。
- **对策**：带 aging 的优先级、长短任务分队列/专用 worker、有界队列、长任务切片（chunking）、监控每个 worker 的任务数和队列长度。

### Q15 — 参考回答要点

- **持久化队列**：`queue.Queue` 只在内存里，进程挂了任务全丢；生产用 Kafka、Redis Streams、NATS JetStream、SQS 或数据库队列。
- **投递语义与幂等**：通常是 at-least-once；worker 用任务 ID 去重、副作用用 upsert/幂等键；用 ack/lease 机制，超时未确认的任务重新投递。
- **重试与死信**：有限次数重试 + 指数退避，超限进 DLQ，人工或离线处理。
- **可观测性**：每个任务带 trace ID，worker 记录开始/结束/失败事件；指标包括队列长度、处理时延分布、每 worker 吞吐、重试率（可接入 OpenTelemetry）。
- **back-pressure 与限流**：有界队列、生产者限速；同时遵守下游 LLM API 的速率限制（这往往是真正的瓶颈）。
- **并发模型**：I/O 密集的 LLM 调用用 asyncio 比"一任务一线程"更省资源（阶段 16 · 22 讨论 fiber/async）；CPU 密集用多进程或多机。
- **防饥饿**：优先级 + aging，或长短任务分队列。
- **优雅退出**：哨兵或关闭信号，`join` 等待在途任务完成。

### Q16 — 参考回答要点

- **分层组合**：
  - 95% 的常规工单：分类 + 摘要 + 路由彼此独立、耗时波动大 → swarm：按类型分 topic（内容路由），专用 worker 订阅自己的类型，持久化队列 + 幂等 worker；
  - 5% 需要多步调查的工单：有依赖、需要连贯结论 → 由分类 worker 投递到"调查"队列，再由 supervisor 型 agent 规划步骤、调用工具、汇总结论；
  - 需要合规审计的子流程（退款、账户变更）走确定性图，保留完整 trace。
- **吞吐估算**：50 万/天 ≈ 5.8 张/秒（平均）。`skill-swarm-fit` 的拒绝规则是"每秒少于 10 个独立单元就不用 swarm"，按平均值算其实**低于**门槛；只有当白天高峰是平均的 2 倍以上、或每张工单会扇出多个子任务（分类、摘要、路由各算一个单元）时，swarm 的弹性才划算。面试中应主动做这个估算，而不是默认上 swarm——如果达不到门槛，一个 supervisor + 并行工具调用往往就够了。
- **防饥饿**：VIP/紧急工单高优先级，但普通工单要 aging，保证 SLA 上限。
- **观测**：每张工单一个 trace ID，贯穿 swarm 阶段与 supervisor 阶段。
- 常见误区：把所有工单都交给一个 supervisor 逐个分派——它会成为瓶颈；或把调查类工单也丢进 swarm——各 worker 只会产出零散事实。

### Q17 — 参考回答要点

- 研究任务需要**一个连贯的全局计划和最终综合**：要决定拆成哪些子问题、何时停止、如何把结果整合成一致的报告。讲义："Complex research questions benefit from a planner. A swarm of researchers produces independent facts, not a coherent report." 讲义延伸阅读也引用了 Anthropic 工程博客，说明该系统明确选择了 supervisor 而不是 swarm。
- **swarm 的调试代价**：没有中央日志，执行顺序由线程/消息到达时间决定，难以复现；一个错误结果可能来自任意 worker 的任意一次执行；要靠每任务 trace ID、持久化事件日志、确定性重放来弥补。
- 讲义："Debugging. With no central log and asynchronous work, reproducing a bug is expensive."
- 加分点：说明 supervisor 的执行层内部也可以并行扇出（并行子 agent），但"谁来做、做到哪一步、怎样汇总"仍由中央决定——这是"并行"与"去中心化"两个概念的区别。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 05 监督者与编排者—工作者模式](../../05-supervisor-orchestrator-pattern/docs/zh.md)：swarm 的对照组，本节"固定分配"即 supervisor 风格。
- [阶段 16 · 04 多 Agent 的基本单元模型](../../04-primitive-model/docs/zh.md)：agent、消息、队列等基本原语。
- [阶段 16 · 06 层级架构及其失效模式](../../06-hierarchical-architecture/docs/zh.md)：中心化结构在规模上的瓶颈。
- [阶段 13 · 03 并行 Tool Calls 与工具调用中的 Streaming](../../../13-tools-and-protocols/03-parallel-and-streaming-tool-calls/docs/zh.md)：I/O 并发的基础。

### 本节被哪些后续内容用到
- [阶段 16 · 13 共享记忆与黑板模式](../../13-shared-memory-blackboard/docs/zh.md)：另一种去中心化协作：共享状态而不是共享队列。
- [阶段 16 · 19 面向 LLMs 的 Swarm 优化（PSO、ACO）](../../19-swarm-optimization-pso-aco/docs/zh.md)：群体智能意义上的 "swarm"。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../22-production-scaling-queues-checkpoints/docs/zh.md)：持久化队列、lease、幂等与 async（讲义中说的"Lesson 22 内容路由"大致对应这里，但该节并未专门讲 content-based routing）。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：去中心化系统的级联错误。
- [阶段 14 · 28 Orchestration 模式：监督者、Swarm 与层级结构](../../../14-agent-engineering/28-orchestration-patterns/docs/zh.md)：从 agent 工程角度比较三种编排。
- [阶段 14 · 29 生产运行时：队列、事件与定时任务](../../../14-agent-engineering/29-production-runtimes/docs/zh.md)：队列与事件驱动运行时。

### 延伸关键词
`work queue` · `work stealing` · `pub/sub` · `event bus` · `Matrix (arXiv:2511.21686)` · `LangGraph Swarm` · `at-least-once delivery` · `idempotency key` · `dead-letter queue` · `back-pressure` · `priority aging` · `list scheduling / LPT` · `GIL` · `asyncio`
