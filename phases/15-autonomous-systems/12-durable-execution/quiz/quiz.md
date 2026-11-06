# 测验 · 长时间运行的后台 Agents：Durable Execution（Long-Running Background Agents: Durable Execution）

> **阶段 15 · 自主系统 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么不能用 `while True` | 讲义的 4 小时 agent 例子：主机重启后朴素循环从头再来，工具副作用重复执行、用户被重复询问、40 次 LLM 调用重复计费 |
| 2 | Workflow | 确定性的编排代码：定义 activity 的顺序、分支、等待；必须确定，才能从事件日志重放而不发生分歧 |
| 3 | Activity | 非确定、可能失败、可能有副作用的工作单元（LLM 调用、工具调用、写文件、HTTP 请求），执行前后都记录 |
| 4 | Event log 与 replay | 日志记录每次 activity 的开始、完成、失败、重试；恢复时 workflow 从头重跑，已完成的 activity 直接返回日志结果，只有未完成的才真跑 |
| 5 | LLM 调用为何是 activity | 非确定（temperature > 0，甚至 temperature 0 也会随模型版本漂移）、昂贵、会失败（限流、超时）、可能有副作用 |
| 6 | `thread_id` 与 checkpoint 后端 | 以 `thread_id` 区分会话、恢复时读最新 checkpoint；PostgreSQL 耐久可查询（LangGraph 默认），SQLite 仅开发用，Redis 需开 AOF/快照，Cloudflare Durable Objects 按唯一键分布 |
| 7 | 人工输入是一等状态 | workflow 在"等人批准"处暂停，外部队列持有请求，批准到达后从同一点恢复；不是轮询循环 |
| 8 | 35 分钟退化 | 讲义：METR 观察到连续运行超过约 35 分钟可靠性下降，任务时长翻倍失败率约变为 4 倍；持久化不能修复它，只是让你能跑得比可靠性允许的更久 |
| 9 | 何时不该用 | 几分钟内结束且无人工输入的任务、纯只读检索、必须在单个上下文窗口内端到端完成的任务 |
| 10 | 至少一次 + 幂等 | activity 在 `started` 与 `done` 之间崩溃会被重新执行；副作用 activity 必须带幂等键 |

### 核心技能（能动手做到）

- [ ] 跑通 `code/main.py`，解释朴素重试 5 次 vs 持久化重试 3 次 activity 执行的来源，并能改变崩溃点预测新的次数
- [ ] 读懂三层嵌套的 `activity` 装饰器，说清"查日志 → started → 执行 → done"每一步的作用
- [ ] 指出本代码"按名字 + 参数查缓存"与真实引擎"按事件序号重放"的区别，并构造出二者行为不同的例子
- [ ] 在 workflow 中引入挂钟时间，演示重放分歧，再用"把读时钟包成 activity"修复
- [ ] 为副作用 activity 设计幂等键，说明它如何把"至少一次"变成"效果上恰好一次"
- [ ] 为一个数小时的自主任务设计 checkpoint 位置、恢复流程和 HITL-on-resume 策略

---

## 二、基础自测（选择题）

**Q1.** 按讲义的划分，下列哪一项说法正确？

- A. workflow 可以自由调用 LLM，因为 LLM 在 temperature 0 时是确定的
- B. activity 必须是确定性的，workflow 则可以非确定
- C. workflow 是确定性的编排代码；LLM 调用、工具调用、HTTP 请求等非确定的工作应作为 activity，并记录输入与输出
- D. workflow 和 activity 只是同一个概念的两种叫法

**Q2.** 运行 `code/main.py`，朴素重试与持久化重试中 activity **真正被执行**的总次数分别是：

- A. 5 和 3
- B. 3 和 3
- C. 6 和 3
- D. 5 和 1

**Q3.** 关于 replay（重放），下列描述最准确的是：

- A. 恢复时从崩溃的那一行代码继续执行，之前的代码不再运行
- B. 恢复时把所有 activity 重新执行一遍，再与日志结果比对
- C. 恢复时只读取最后一个 checkpoint 的变量快照，不需要事件日志
- D. 恢复时 workflow 代码从头重跑，已完成的 activity 直接返回日志中的结果、不重新执行，只有未完成的 activity 才真正运行

**Q4.** 讲义认为 LLM 调用"exactly the activity profile"，下列哪一项**不是**讲义给出的理由？

- A. 非确定：temperature > 0；即使 temperature 0 也会随模型版本漂移
- B. LLM 调用速度极快、几乎不花钱，因此适合频繁重试
- C. 可能失败：限流、超时
- D. 可能有副作用：如果它会调用工具

**Q5.** 关于 checkpoint 后端，讲义的说法是：

- A. SQLite 只适合本地开发，跨主机会丢数据；Redis 很快，但不配置 AOF/快照就是易失的
- B. Redis 是 LangGraph 的默认后端，因为它最快
- C. PostgreSQL 无法在部署之后保留状态
- D. 任何后端都可以，只要代码里有 `thread_id`

**Q6.** 讲义说"Doubling the task duration roughly quadruples the failure rate"。若某 agent 在 35 分钟任务上的失败率是 5%，按这条经验法则，70 分钟和 140 分钟任务的失败率约为：

- A. 10% 和 20%
- B. 10% 和 40%
- C. 20% 和 80%
- D. 25% 和 125%

**Q7.** 下列哪个场景**最不适合**引入 durable execution？

- A. 一个需要过夜等待经理审批、第二天继续执行的报销 agent
- B. 一个运行 6 小时、会多次调用有副作用工具的自主编码任务
- C. 一个会跨越多次部署、需要在重启后继续的后台研究 agent
- D. 一个 30 秒内完成、只读地检索几篇文档并回答问题的问答 agent

**Q8.** 在本节的 `activity` 装饰器中，如果进程在 `fn(*args)` 执行完毕、但还没写入 `done` 事件时崩溃，恢复后会发生什么？

- A. `lookup` 找到 `started` 事件，直接返回 `None`
- B. `lookup` 只认 `done` 事件，于是该 activity 被再执行一次——副作用可能重复发生
- C. 引擎检测到不一致，抛出 non-determinism 错误
- D. 该 activity 被永久跳过，workflow 用默认值继续

---

## 三、动手 / 代码题

**Q9.** 阅读 `EventLog.lookup`：

```python
    def lookup(self, name: str, args: tuple) -> dict | None:
        for ev in self.events():
            if ev["name"] == name and ev["args"] == list(args) and ev["status"] == "done":
                return ev
        return None
```

分别预测下面三段代码的行为，并解释原因：

```python
calls = []
@activity("sample")
def sample(x):
    calls.append(x); return len(calls)
print(sample(log, 1), sample(log, 1), len(calls))       # (a)

@activity("pair")
def pair(x): return (x, x + 1)
r1 = pair(log, 1); r2 = pair(log, 1); print(r1 == r2)   # (b)

@activity("targ")
def targ(t): return sum(t)
targ(log, (1, 2)); targ(log, (1, 2)); print(count_runs(log))   # (c)（假设日志里只有这两次调用）
```

**Q10.** 构造"activity 执行到一半崩溃"的场景：一个模拟发邮件的 activity，第一次执行时在副作用发生之后、`return` 之前抛异常。

1. 恢复后邮件一共发了几次？日志里留下了哪些事件？
2. 设计一个幂等键方案，使重试不会重复发邮件。幂等键应该由什么派生？

**Q11.** 讲义练习 3：在 workflow 中引入挂钟时间。

```python
@activity("send_digest")
def send_digest(kind): return f"sent:{kind}"

def wf(log, hour, crash):
    kind = "morning" if hour < 12 else "evening"     # workflow 内读"时钟"
    r = send_digest(log, kind)
    if crash: raise RuntimeError("crash")
    return r
```

第一次以 `hour=10, crash=True` 运行，第二次（恢复）以 `hour=20, crash=False` 运行，共用同一个日志。

1. 一共发出了几份 digest？本引擎会报错吗？Temporal 这类引擎会怎么处理？
2. 修改代码，使恢复后的分支与第一次一致。

**Q12.** 讲义练习 2：给引擎加上 `thread_id`。

1. 如果两个会话共用当前的日志文件、调用 `workflow(log, "hello")`，会出现什么问题？
2. 给出一种改法（关键代码即可），并说明为什么讲义说 checkpoint "keyed by `thread_id`; latest-wins on resume"。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 durable execution？请用 workflow、activity、event log、replay 四个概念解释它如何让一个运行 4 小时的 agent 在主机重启后继续。

**Q14.**（原理深挖）为什么 workflow 代码必须是确定性的？哪些常见写法会破坏确定性？真实引擎如何处理"必须读时钟/随机数"的需求？

**Q15.**（工程实践）durable execution 能保证 exactly-once 吗？对"扣款""发邮件"这类副作用 activity，你会怎么设计？

**Q16.**（场景设计）讲义练习 5：为一个 6 小时的自主编码任务设计 checkpoint 策略——在哪里 checkpoint？崩溃后如何恢复？哪些操作在恢复时需要重新获得人工批准？

**Q17.**（追问型）既然有了 durable execution，agent 就能一直跑下去了吗？它和"35 分钟退化"是什么关系？什么情况下不该用它？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Workflow: deterministic orchestration code... Activity: a non-deterministic, potentially failing unit of work. LLM call, tool call, file write, HTTP request." A 错：讲义明确 "even temperature 0 drifts across model versions"，LLM 调用不能放在 workflow 里；B 把两者的要求说反了；D 显然错误，二者分工正是该模式的核心。

### Q2 — 答案：A

朴素重试：第 1 次尝试执行 `fetch_docs`、`call_llm` 后崩溃（2 次），日志被 `reset_log` 清空，第 2 次从头执行 3 个 activity（3 次），合计 5。持久化重试：第 1 次同样执行 2 次，第 2 次 `fetch_docs`、`call_llm` 被 `[replay]`，只有 `write_report` 真正执行，合计 3（输出 "3 total activity starts across attempts"）。B 忽略了朴素组浪费的 2 次；C 多算了一次；D 只数了第 2 次尝试中真正执行的那一次。

### Q3 — 答案：D

讲义："on recovery, the workflow code re-runs from the start; every activity that already completed returns its logged result without re-executing. Only activities that had not completed are actually run." A 描述的是"恢复调用栈"，Python 进程崩溃后调用栈不可恢复，这正是需要重放的原因；B 重新执行就失去了意义（会重复计费、重复副作用）；C 描述的是快照式 checkpoint，而讲义的模式依赖事件日志。

### Q4 — 答案：B

讲义列的是"Non-deterministic / Expensive (money and latency) / Potentially failing / Side-effectful"。B 恰好相反：LLM 调用**昂贵**（钱和延迟都贵），这才是"已完成的调用不要重做"的动机。

### Q5 — 答案：A

讲义："SQLite: local-dev only; loses data across hosts. Redis: fast but ephemeral unless AOF/snapshot configured." B 错，LangGraph 默认是 PostgreSQL；C 错，PostgreSQL "durable, queryable, survives deploys"；D 错，后端是否能在部署/重启后保留数据是关键，`thread_id` 只解决会话隔离。

### Q6 — 答案：C

"时长翻倍、失败率约 ×4"即失败率 ∝ 时长²：70 分钟 = 5% × 4 = 20%；140 分钟 = 5% × 16 = 80%。A 是线性增长；B 混用了线性与平方；D 用的是 ×5 且超过 100%，说明没有意识到这只是**在失败率较低时才近似成立的经验法则**——失败率不可能超过 100%，时长继续加倍时曲线必然变缓。工程含义：长任务要拆成多段，每段在可靠区间内，段与段之间设 checkpoint 和人工检查。

### Q7 — 答案：D

讲义 "When durable execution is the wrong answer"：短于几分钟且无人工输入的运行（开销大于收益）、严格只读的信息检索。D 两条都满足。A 需要过夜等待人工输入（讲义 "an overnight approval arrives and the workflow picks up in the morning"）；B 是长时程且有副作用；C 需要跨部署存活——这三者都是 durable execution 的典型场景。

### Q8 — 答案：B

`lookup` 的条件包含 `ev["status"] == "done"`，只有 `started` 的事件不会命中，于是 `wrapper` 重新写一条 `started` 并再执行一次 `fn(*args)`。已实际验证：一个第一次执行时在副作用后抛异常的 activity，恢复后副作用共执行 2 次，日志状态序列为 `['started', 'started', 'done']`。A 错，`lookup` 不返回 `started` 事件；C 错，本引擎没有任何一致性检测；D 错，不会跳过。这就是"至少一次"语义，需要幂等键（见 Q10）。

### Q9 — 参考答案

已实际运行验证：

- **(a)** 输出 `1 1 1`：第一次调用真正执行，`calls` 变为 `[1]`、返回 1；第二次调用 `lookup("sample", (1,))` 命中第一次的 `done` 事件，打印 `[replay]` 并返回 1，原函数没有被调用，`len(calls)` 仍为 1。**同名同参的两次合法调用被合并成一次**。如果这是"对同一 prompt 采样两次取多数票"，第二个样本永远等于第一个。
- **(b)** 输出 `False`：第一次执行返回元组 `(1, 2)`，写入 JSON 后变成 `[1, 2]`；第二次命中日志，返回列表 `[1, 2]`，`(1, 2) == [1, 2]` 为 `False`。**首次运行与重放返回的类型不同**，workflow 若依赖类型（如作为字典键、做 `isinstance` 判断）就会出现重放分歧。
- **(c)** 输出 `2`：参数 `((1, 2),)` 转成 `list(args)` 是 `[(1, 2)]`，而日志里存的是 `[[1, 2]]`，`[[1, 2]] == [(1, 2)]` 为 `False`，**永远不命中**，每次都重新执行。

根本原因：`lookup` 做的是"按名字 + 参数查缓存"（memoization），且比较的是 JSON 序列化前后的值。真实引擎（Temporal 等）按**事件序号**重放：第 k 次 activity 调用对应历史中的第 k 条记录，并且用显式的序列化器保证类型一致；如果第 k 次调用的类型/名字与历史不符，就报 non-determinism 错误，而不是悄悄执行或悄悄合并。

### Q10 — 参考答案

1. 实测代码：

   ```python
   @activity("side")
   def side(x):
       side.n = getattr(side, "n", 0) + 1
       if side.n == 1:
           raise RuntimeError("crash mid-activity")   # 副作用已发生，但没走到 return
       return "sent"
   ```

   第一次调用写入 `started` 后执行，副作用发生（`side.n = 1`），随后抛异常，`done` 没有写入；恢复后 `lookup` 未命中，再次写 `started` 并执行。结果：**副作用执行 2 次**，日志状态为 `['started', 'started', 'done']`。真实世界里这就是"邮件发了两封""扣了两次款"。

2. 幂等键方案：
   - 键由**workflow 实例 + activity 在 workflow 中的位置**确定性地派生，例如 `f"{thread_id}:{seq}:{activity_name}"`，或 Temporal 中的 `workflow_id + activity_id`。关键是：**同一次逻辑调用的每次重试，键都相同**；不同的逻辑调用，键不同。不能用时间戳或随机 UUID（每次重试都会变）。
   - 在 `wrapper` 写 `started` 时就把键记入日志，并把键传给下游服务（如邮件 API、支付 API 的 `Idempotency-Key` 头）。
   - 下游服务记住已处理的键，对重复键直接返回第一次的结果而不再执行。
   - 这样"至少一次的投递"+"幂等的处理"= 效果上的恰好一次。讲义 skill 文件："If the user proposes a durable workflow with no explicit idempotency on side-effect activities, refuse and require idempotency keys first."

### Q11 — 参考答案

1. 已实际运行：第一次 `hour=10` 走 `morning` 分支，执行 `send_digest('morning')` 后崩溃；恢复时 `hour=20` 走 `evening` 分支，`lookup("send_digest", ("evening",))` 未命中，于是**又真正发出了一份 evening digest**。共发出 **2 份**（日志中 `['morning']` 和 `['evening']` 各有一对 started/done）。本引擎**不会报错**，因为它只是按名字+参数查表，分歧表现为"缓存未命中、默默执行"。Temporal 会在重放时把 workflow 发出的命令序列与历史比对，发现第 1 个命令的参数不一致，抛出 non-determinism 错误，阻止 workflow 继续，从而避免二次副作用。
2. 修复：把读时钟变成一个被记录的 activity（相当于 Temporal 的 `workflow.now()` 或 side-effect 注册）：

   ```python
   @activity("now_hour")
   def now_hour(_tick): return current_hour()   # 第一次真实读取并记录

   def wf2(log, crash):
       h = now_hour(log, "t0")                     # 重放时返回日志里的 10
       kind = "morning" if h < 12 else "evening"
       ...
   ```

   实测：恢复时 `now_hour` 与 `send_digest('morning')` 都被 `[replay]`，只发出 1 份 digest。讲义 Key Terms："Non-determinism ... Wall clock, random, LLM output; must be registered as side effect."

### Q12 — 参考答案

1. 两个会话共用同一个日志时，会话 B 调用 `fetch_docs(log, "hello")` 会命中会话 A 写下的 `done` 事件，**直接重放 A 的结果**——即使 B 本该重新抓取（比如数据已变化、或 B 属于另一个用户）。更糟的是 `write_report` 也会被"重放"，B 以为报告已经写好，实际上写的是 A 的。这既是正确性问题，也是数据隔离（跨租户泄漏）问题。
2. 改法（任选其一）：

   ```python
   # 方案 1：每个 thread_id 一个日志
   def log_for(thread_id: str) -> EventLog:
       return EventLog(os.path.join(tmpdir, f"{thread_id}.json"))

   # 方案 2：同一存储，事件带 thread_id，lookup 时比对
   def lookup(self, thread_id, name, args):
       for ev in self.events():
           if (ev["thread_id"] == thread_id and ev["name"] == name
                   and ev["args"] == list(args) and ev["status"] == "done"):
               return ev
   ```

   讲义说 LangGraph、Microsoft Agent Framework、Cloudflare Durable Objects、Claude Code Routines 都收敛到同一形状："a `thread_id` identifies the session; each state transition persists to a backend; resume reads the latest checkpoint." `thread_id` 是持久状态的**作用域**，恢复时用它找到"这个会话"最新的 checkpoint（latest-wins），而不是任何会话的状态。在数据库后端里，`thread_id` 通常就是主键/分区键的一部分。

### Q13 — 参考回答要点

- **定义**：一种执行模型，让长时间运行的流程在进程崩溃、主机重启、部署升级后从最近的进度继续，而不是从头再来。
- **四个概念**：
  - **workflow**：确定性的编排代码，描述"先做什么、再做什么、在哪等待"；
  - **activity**：非确定/可能失败/有副作用的步骤（LLM 调用、工具调用、HTTP、写文件），带重试、超时；
  - **event log**：持久化存储，记录每个 activity 的开始、完成（含结果）、失败、重试，以及 workflow 的每个决策；
  - **replay**：恢复时 workflow 从头重跑，已完成的 activity 直接用日志结果，只有未完成的才真正执行。
- **对 4 小时 agent 的效果**（讲义 The Problem）：已完成的 3 次工具调用不会重复执行，用户已批准的事项不会重复询问，已做的 LLM 调用不会重复计费。
- 加分点：类比讲义提到的 React 基于虚拟 DOM 重渲染、Git 从提交重建工作区——"确定性的重放 + 记录下来的外部输入 = 可重建的状态"。

### Q14 — 参考回答要点

- **为什么必须确定**：重放靠"同样的 workflow 代码 + 同样的 activity 结果 → 同样的执行路径"。如果 workflow 本身的决策会变，重放时就会走到与历史不同的分支，日志里的结果对不上号，轻则重复执行副作用（Q11），重则状态错乱。讲义："Determinism in the orchestrator is what makes durability cheap."
- **破坏确定性的写法**：在 workflow 中读挂钟（`time.time()`）、随机数、UUID、环境变量、全局可变状态；直接调用 LLM 或 HTTP；遍历无序集合并依赖其顺序；在升级 workflow 代码时改变 activity 调用顺序。
- **真实引擎的处理**：
  - 提供确定性 API：如 `workflow.now()`、确定性随机数、side-effect 注册——第一次执行时取值并写入历史，重放时从历史读取；
  - 重放时比对命令序列与历史，不一致就报 non-determinism 错误；
  - workflow 代码版本化（versioning/patching），让老的运行按老逻辑重放。
- 常见误区：以为把 temperature 设为 0 就能把 LLM 调用放进 workflow。

### Q15 — 参考回答要点

- **不能天然保证 exactly-once**：activity 执行和"记录完成"之间总有时间窗口，崩溃发生在窗口内时，恢复后只能重新执行——这是至少一次（at-least-once）。本节代码中 `started` 与 `done` 之间就是这个窗口（Q8、Q10）。
- **设计**：
  1. 每个副作用 activity 带**确定性派生**的幂等键（`thread_id + 序号 + 名称`，或业务主键如订单号），重试时键不变；
  2. 下游支持幂等（支付、邮件 API 常见的 `Idempotency-Key`），或在自己的服务里维护"已处理键"表，同一事务中写结果与键；
  3. 不支持幂等的外部系统，先查询再执行（"查询是否已扣款"），或拆成"预留 → 确认"两步；
  4. 为 activity 配置合理的重试策略（指数退避、最大次数）和超时，区分可重试错误与不可重试错误；
  5. 对高风险副作用叠加 HITL（第 15 节）。
- 讲义 skill 文件的上线前要求：必须有"重放测试"——运行、中途崩溃、重放、断言没有重复副作用。
- 加分点：说明"效果上的恰好一次 = 至少一次投递 + 幂等处理"。

### Q16 — 参考回答要点

- **在哪里 checkpoint**：
  - 每个 LLM 调用、每次工具调用（运行测试、写文件、git 操作）都是 activity，自动进入事件日志；
  - 在逻辑里程碑处做显式的"阶段 checkpoint"：完成需求分析、完成某个子模块并通过测试、提交一次 commit；代码状态本身用 git commit/分支保存，与事件日志关联；
  - 每次"等待人工输入"都是持久化的一等状态。
- **崩溃后恢复**：用 `thread_id` 找到最新 checkpoint → 重放事件日志重建 workflow 状态 → 校验外部世界是否与日志一致（工作区是否在记录的 commit 上、远端分支是否已被别人改动）→ 从第一个未完成的 activity 继续。
- **需要重新 HITL 的操作**（讲义 skill 文件 "HITL-on-resume policy"）：崩溃前获得的批准，若恢复时上下文已变化（时间过去很久、代码基线变了、依赖更新了），对以下动作要重新批准：推送到共享分支/合并 PR、修改 CI/部署配置、数据库迁移、删除文件或分支、任何花钱或对外发送的操作。理由：讲义指出 "an approval granted before the crash may re-fire an approved action when the context has changed"。
- **叠加的护栏**：按讲义的 35 分钟退化，把 6 小时拆成若干 30–60 分钟的段，每段结束跑测试并做人工抽检；叠加第 13 节的预算上限（token、美元、工具调用次数），与墙钟时间无关地封顶总消耗。
- 加分点：恢复后先做一次"现状核对"而不是盲目继续。

### Q17 — 参考回答要点

- **不能**。讲义："Durable execution does not fix this; it lets you run longer than the reliability profile supports." 持久化解决的是**基础设施层面**的失败（崩溃、重启、部署），不解决**模型层面**的可靠性随时长下降（错误累积、偏离目标、上下文劣化）。
- **关系**：持久化让长时间运行变得"便宜且可能"，因此反而更容易让 agent 跑进它不可靠的区间——讲义称这是"a new way to fail safely if the design is right and unsafely if the design is wrong"。安全模式：持久化 + 恢复时需要新鲜 HITL 的 checkpoint + 与墙钟无关的预算熔断（第 13 节）。
- **不该用的情况**（讲义）：几分钟内结束且没有人工输入的任务（开销大于收益）；纯只读检索；需要在一个上下文窗口内端到端完成的任务（某些推理、一次性生成）。
- 常见误区：把"能恢复"当作"能信任"；把 24 小时无人值守运行当成目标——skill 文件明确要拒绝没有 HITL checkpoint 的 24 小时无人值守运行。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 01 从聊天机器人转向长程 Agents](../../01-long-horizon-agents/docs/zh.md)：长程任务的可靠性衰减，是本节"35 分钟退化"的背景。
- [阶段 15 · 10 自主 Agents 的权限模式](../../10-claude-code-permission-modes/docs/zh.md)：恢复时需要重新批准哪些动作，取决于权限模式。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md)：LangGraph 中 checkpointer 与 `thread_id` 的实际用法。
- [阶段 11 · 16 Agent State Machines——图、节点与 Checkpoints](../../../11-llm-engineering/16-langgraph-state-machines/docs/zh.md)：状态机视角下的 checkpoint。
- [阶段 14 · 29 生产运行时：队列、事件与定时任务](../../../14-agent-engineering/29-production-runtimes/docs/zh.md)：后台任务运行时的基础设施。

### 本节被哪些后续内容用到
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../13-cost-governors/docs/zh.md)：叠加在持久化之上的预算熔断。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../15-propose-then-commit/docs/zh.md)：持久化的"等待人工"状态是 propose-then-commit 的前提。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../16-checkpoints-rollback/docs/zh.md)：在 checkpoint 基础上实现回滚。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../../16-multi-agent-and-swarms/22-production-scaling-queues-checkpoints/docs/zh.md)：多智能体场景下的持久化与队列。
- [阶段 19 · 47 Checkpoint 保存与恢复](../../../19-capstone-projects/47-checkpoint-save-resume/docs/zh.md)：综合项目中实现保存与恢复。

### 延伸关键词
`Temporal` · `workflow / activity` · `event sourcing` · `deterministic replay` · `non-determinism error` · `workflow.now()` · `idempotency key` · `at-least-once` · `exactly-once` · `thread_id` · `PostgreSQL checkpointer` · `Durable Objects` · `interrupt()` · `HITL-on-resume`
