# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 29 节 生产运行时：队列、事件与定时任务 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`collections.deque`、`dataclasses`、`typing`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义的核心观点是"**同样的 Agent 逻辑，套上不同的外壳**"——先选运行时形态，再选框架。代码用一个固定的假 Agent（`_agent_fn`，返回 5 个步骤）分别套上 5 种外壳：

1. **Request-response**：同步调用，只返回最终结果。
2. **Streaming**：用生成器逐步交出每一步。
3. **Queue-based**：入队 → worker 拉取 → 失败重试 → 超过次数进 DLQ（dead-letter queue，死信队列）。
4. **Event-driven**：订阅/发布式的事件总线。
5. **Scheduled**：cron 的"替身"，只打印"将会触发什么事件"。

第六种形态 durable execution 讲义明确说交给 Lesson 13（LangGraph checkpointing），这里没有实现。

> 一句话：**运行时形态决定了哪些失败是"可存活"的**——同步请求扛不住长任务，队列没有 DLQ 会丢任务，后台任务没有 trace 会让失败隐形。读这份代码时，要特别注意 worker 中一个只在随机失败时才暴露的重试 bug。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `_agent_fn` | 函数 | 假 Agent：返回 parse/plan/step1/step2/final 5 个字符串 | 被包装的 Agent 逻辑 |
| `request_response` | 函数 | 调用 Agent，只返回最后一步 | Request-response |
| `streaming` | 生成器函数 | 逐个 `yield` Agent 的步骤 | Streaming |
| `Job` | dataclass | 任务 ID、负载、已尝试次数 | 队列任务 |
| `QueueRuntime` | dataclass | `queue`（deque）、`dlq`（list）、`enqueue`、`worker` | Queue-based + DLQ |
| `EventBus` | dataclass | `subscribe` 注册处理器、`publish` 分发事件 | Event-driven |
| `main` | 函数 | 依次演示 5 种形态 | 演示 |

数据流：同一个 `_agent_fn` 被五种外壳调用 → request-response 取最后一步；streaming 逐步打印；队列 worker 循环取任务、按 `fail_policy` 决定重试/DLQ/执行；事件总线按事件类型调用处理器；schedule 列表只打印。

---

## 3. 逐段精讲

### 3.1 假 Agent 与 request-response

```python
def _agent_fn(input_text: str) -> list[str]:
    steps = [
        f"parse: {input_text[:40]}",
        f"plan: 3-step plan",
        f"step 1: search",
        f"step 2: read",
        f"final: answered {input_text[:20]}",
    ]
    return steps


def request_response(input_text: str) -> str:
    steps = _agent_fn(input_text)
    return steps[-1]
```

- `_agent_fn` 代表"一个 Agent 的完整执行"，返回所有步骤组成的**列表**——这一点对 3.2 节至关重要。
- `request_response` 只返回 `steps[-1]`（最终答案）：调用方必须等整个 Agent 跑完才能拿到任何东西。讲义："Synchronous HTTP. User waits for completion. Only viable for short tasks (<30s)."
- 中间三个 f-string（`f"plan: 3-step plan"` 等）没有任何占位符，`f` 前缀是多余的，不影响结果。
- 生产中这一层还需要：请求超时、取消、OTel span；任务超过 30 秒就应改为"提交任务 → 返回任务 ID → 轮询或 webhook"的异步形态。

### 3.2 Streaming：生成器（但是伪流式）

```python
def streaming(input_text: str) -> Iterable[str]:
    for step in _agent_fn(input_text):
        yield step
```

- 函数体含 `yield`，调用它返回一个**生成器**，调用方用 `for` 逐个取值。`main` 中每取一个就打印一行 `chunk: ...`，模拟 SSE/WebSocket 的逐块推送。
- ⚠️ **伪流式**：`_agent_fn(input_text)` 会先完整执行、返回整个列表，之后 `for` 才开始迭代。所以第一个 chunk 要等全部工作完成才会出现——**首 token 延迟 = 总延迟**，流式的 UX 收益为零。把 `_agent_fn` 替换成 sleep 0.2 秒的版本实测，第一个 `next()` 在约 0.2 秒后才返回。
- 真正的流式要求 Agent 本身是生成器：每完成一步就 `yield` 一步（`yield from agent_steps(...)`），见测验 Q11。
- 生成器天然支持 backpressure：消费者不调用 `next()`，生成器就停在 `yield` 处不往下执行（讲义练习 4）。

### 3.3 `Job` 与 `QueueRuntime`：入队

```python
@dataclass
class Job:
    jid: str
    payload: str
    attempt: int = 0


@dataclass
class QueueRuntime:
    queue: deque[Job] = field(default_factory=deque)
    dlq: list[Job] = field(default_factory=list)
    fail_rate: int = 0
    counter: int = 0

    def enqueue(self, payload: str) -> str:
        self.counter += 1
        jid = f"j{self.counter:03d}"
        self.queue.append(Job(jid=jid, payload=payload))
        return jid
```

- `deque`（双端队列）从左边取（`popleft`）、右边放（`append`）都是 O(1)，适合做 FIFO 队列；用 `list.pop(0)` 则是 O(n)。
- `field(default_factory=deque)`：每个 `QueueRuntime` 实例有自己独立的队列，避免可变默认值共享。
- `f"j{self.counter:03d}"`：整数补零到 3 位，得到 `j001`、`j002`……
- `attempt` 记录已尝试次数，是重试与 DLQ 决策的依据。
- ⚠️ `fail_rate` 字段**从未使用**——看起来像是为讲义练习 2（模拟 10% 失败）预留的，但失败实际由 `worker` 的 `fail_policy` 参数决定。

### 3.4 `worker`：重试与 DLQ（有 bug）

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

流程：取出任务 → 尝试次数 +1 → 失败且未满 3 次：放回队尾、记 retry → 失败且已满 3 次：进 DLQ → 否则执行 Agent。

- `fail_policy` 是一个"判断这个任务这次会不会失败"的函数，由调用方传入，演示中是 `fail_b`：payload 为 `"long job B"` 就失败。
- 失败的任务被 `append` 到**队尾**，所以 j003 会在 j002 的第二次尝试之前完成——输出顺序 `j001, j002 retry, j003, j002 retry, j002 DLQ` 就是这么来的。
- 最多尝试 3 次：attempt=1、2 时重试，attempt=3 时进 DLQ。

⚠️ **关键 bug：每次尝试调用 `fail_policy` 两次**。第一个 `if` 调用一次，第二个 `if` 又调用一次。演示中 `fail_b` 是确定性的，两次结果相同，看不出问题。但讲义练习 2 要求"模拟 10% 失败"，若用 `random.random() < 0.10`：

| 情形 | 概率 | 结果 |
|------|------|------|
| 第 1 次尝试：第一次判定成功、第二次判定失败 | 0.9 × 0.1 = 0.09 | **从未重试就进 DLQ** |
| 第 2 次尝试进 DLQ | 0.1 × 0.9 × 0.1 = 0.009 | 只重试了 1 次 |
| 第 3 次尝试进 DLQ | 0.1³ = 0.001 | 正常路径 |
| 合计 | ≈ 0.10 | 1,000 个任务约 100 个进 DLQ |

实测（1,000 个任务，3 个随机种子）：DLQ 大小 100、87、89，其中第 1 次尝试就进 DLQ 的分别为 88、79、84 个；而正确实现的期望只有 `1000 × 0.1³ = 1` 个（修复后实测 2、1、1）。修复方法是把判定结果存进变量只求值一次（测验 Q9）。如果 `fail_policy` 代表真实的执行，两次调用还意味着同一步被执行两次。

其他简化：

- ⚠️ **at-most-once**：`popleft()` 在执行前就把任务移出队列，worker 崩溃时任务彻底丢失。生产队列用 ack + visibility timeout 实现 at-least-once。
- ⚠️ **立即重试**：没有退避，限流类错误会在毫秒内耗尽重试次数。应使用指数退避 + 抖动，并区分可重试/不可重试错误。
- ⚠️ **DLQ 不记录失败原因**：只有 `Job` 本身，没有错误信息、步骤、trace ID。
- 失败只在执行**之前**由 `fail_policy` 判定；Agent 执行过程中本身不会失败，也没有"在第 37 步失败"这种讲义开头描述的情况。

### 3.5 `EventBus`：订阅与发布

```python
@dataclass
class EventBus:
    subscribers: dict[str, list[Callable[[str], str]]] = field(default_factory=dict)

    def subscribe(self, event_type: str, handler: Callable[[str], str]) -> None:
        self.subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event_type: str, payload: str) -> list[tuple[str, str]]:
        results: list[tuple[str, str]] = []
        for handler in self.subscribers.get(event_type, []):
            results.append((event_type, handler(payload)))
        return results
```

- `subscribers` 是"事件类型 → 处理器列表"的字典，一个事件可以有多个处理器。
- `setdefault(event_type, [])`：键不存在时先放入空列表并返回它，再 `append`——一行完成"没有就创建"。
- `publish` 同步地依次调用每个处理器，收集返回值。
- 演示中注册了 `pr.opened`（跑检查）和 `memory.consolidate`（整理记忆），对应讲义 "Agents subscribe to triggers: new email, PR opened, cron fire"。
- ⚠️ **无订阅者的事件被静默丢弃**：`publish("eval.nightly", ...)` 返回 `[]`（已实测），不报错、不记录。skill 要求事件形态有"explicit subscriber registry + replay path"。
- ⚠️ **没有异常隔离**：第一个处理器抛异常时，后面的处理器不会执行，异常直接传到调用方（已实测 `RuntimeError: boom`）。
- ⚠️ 同步执行：一个慢处理器会阻塞整个发布；真实系统中事件进入消息队列，由各自的消费者异步处理。

### 3.6 `main`：五种外壳

```python
    print("\n5. scheduled (cron stand-in)")
    schedule = [
        ("02:00", "memory.consolidate"),
        ("03:00", "eval.nightly"),
    ]
    for when, event in schedule:
        print(f"  {when}: would fire {event}")
```

- 前四段分别演示 3.1–3.5 的组件。
- 第五段"scheduled"只是打印一个时间表，**没有调度器、没有和 `EventBus` 相连、没有锁**。其中 `eval.nightly` 在总线上也没有订阅者——如果真的发布，事件会被静默丢弃（见 3.5）。skill 对 cron 的要求是"lock file or distributed lock to prevent overlapping runs"，讲义要求与 durable execution 组合。测验 Q12 给出了一个带锁、连到总线、记录未处理事件的 `Scheduler`。
- 最后打印的 "same agent logic, four outer shells" 与实际演示的 5 段不一致；文件 docstring 也写的是 "Four production runtime shapes"，而讲义说代码展示 "five traces"、讲的是 "six runtime shapes"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 同一个 `_agent_fn` 套 5 种外壳 | 突出"形态与 Agent 逻辑正交" | 假 Agent 不会失败、没有耗时，无法体现各形态在故障下的差异 |
| `_agent_fn` 返回列表 | 简单 | streaming 变成伪流式；真实 Agent 应该是生成器或异步迭代器 |
| 失败由 `fail_policy` 注入 | 便于构造确定性的失败用例 | 被调用两次，随机失败时 DLQ 被放大约 100 倍；应只求值一次 |
| `deque` + 立即放回队尾 | 演示重试顺序 | 无退避、无 ack、at-most-once；生产用 SQS/BullMQ/Celery，配 visibility timeout 与幂等 |
| DLQ 用 list 保存 Job | 演示"失败任务不消失" | 缺失败原因与 trace ID；需支持查看与重放 |
| 同步事件总线 | 代码短 | 无订阅者静默丢弃、处理器异常互相影响；生产用消息队列与审计日志 |
| cron 只打印 | 避免引入调度依赖 | 没有锁、没有和总线连接；生产用 Kubernetes CronJob（`concurrencyPolicy: Forbid`）+ durable 框架 |
| 不实现 durable execution | 讲义安排在 Lesson 13 | 本节所有形态都不能从中途恢复 |
| 没有任何 trace / 指标 | 演示聚焦形态 | 讲义说可观测性是承重墙：至少需要队列深度、单任务耗时、DLQ 大小、首 token 延迟等指标 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 生成器函数 `yield` | `def streaming(...): for step in ...: yield step` | 调用后得到生成器，按需逐个产生值；执行在 `yield` 处暂停 |
| `Iterable[str]` 返回注解 | `-> Iterable[str]` | 声明返回"可迭代的字符串序列"（生成器满足此类型） |
| `collections.deque` | `queue: deque[Job]`、`self.queue.popleft()` | 双端队列，两端增删都是 O(1) |
| `@dataclass` + 方法 | `class QueueRuntime: def enqueue(...)` | dataclass 既保存数据也可以定义方法 |
| `field(default_factory=...)` | `field(default_factory=deque)`、`field(default_factory=dict)` | 可变默认值必须用工厂函数 |
| 关键字参数构造 | `Job(jid=jid, payload=payload)` | 按字段名传参，更清晰 |
| f-string 格式符 | `f"j{self.counter:03d}"` | 整数宽度 3、左侧补 0 |
| 无占位符的 f-string | `f"plan: 3-step plan"` | 合法但多余，`f` 前缀可以去掉 |
| 负索引 | `steps[-1]` | 取最后一个元素 |
| `while 容器:` | `while self.queue:` | 容器非空为真，空则退出循环 |
| `Callable[[Job], bool]` | `fail_policy: Callable[[Job], bool]` | 接收 `Job`、返回布尔值的函数，即"策略函数" |
| 函数作为参数 | `rt.worker(fail_policy=fail_b)` | 把判断逻辑作为参数注入，便于测试 |
| 嵌套函数 | `main` 内的 `def fail_b(job)`、`def on_pr_opened(payload)` | 只在 `main` 内使用的小函数 |
| `dict.setdefault` | `self.subscribers.setdefault(event_type, []).append(handler)` | 键不存在则插入默认值并返回 |
| `dict.get(key, default)` | `self.subscribers.get(event_type, [])` | 键不存在返回默认值，不抛 `KeyError` |
| 元组列表与解包 | `for jid, status in results:`、`for when, event in schedule:` | 遍历时直接拆开二元组 |
| 未使用的导入 | `Any` | 导入了但没有使用 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，瞬间完成）：

```text
1. request-response (synchronous)
  result: final: answered list project files

2. streaming (generator)
  chunk: parse: review this PR
  chunk: plan: 3-step plan
  chunk: step 1: search
  chunk: step 2: read
  chunk: final: answered review this PR

3. queue-based (with retry and DLQ)
  j001: final: answered long job A
  j002: retry
  j003: final: answered long job C
  j002: retry
  j002: DLQ
  queue: 0   dlq: 1

4. event-driven (subscriber pattern)
  pr.opened -> ran checks on #123 add feature
  memory.consolidate -> consolidated session_001

5. scheduled (cron stand-in)
  02:00: would fire memory.consolidate
  03:00: would fire eval.nightly
```

逐项解读：

- **1. request-response**：只有最后一步。中间发生了什么，调用方完全看不到。
- **2. streaming**：5 个 chunk 依次出现。在终端里看起来是"流式"，但所有 chunk 其实都是在 `_agent_fn` 返回后才开始产出的（见 3.2）。
- **3. queue**：
  - j001、j003 一次成功；
  - j002 尝试 3 次（两次 retry 后进 DLQ），由于重试放回队尾，j003 插在 j002 的两次尝试之间；
  - 最终 `queue: 0  dlq: 1`：队列清空，失败任务停在 DLQ 中而不是消失——这就是讲义"No DLQ → Failed jobs vanish"的反面示范。
  - 这一段的输出在修复"重复调用 `fail_policy`"的 bug 前后完全一样，bug 只在随机失败下暴露（3.4）。
- **4. event-driven**：两个事件各被一个处理器处理。
- **5. scheduled**：只是打印，没有任何事件真的被发布。

---

## 7. 动手改一改

1. **修复重试 bug（讲义练习 2）**：把 `fail_policy(job)` 的结果存进变量只求值一次；入队 1,000 个任务，用 `random.random() < 0.10` 模拟失败，对比修复前（约 100 个进 DLQ）和修复后（约 1 个）的 DLQ 大小，并打印"队列深度、DLQ 大小、平均尝试次数"三项指标。
2. **at-least-once**：给 `QueueRuntime` 增加 `in_flight` 字典；`popleft` 后放入 `in_flight`，执行成功后才删除；模拟 worker 崩溃（执行中抛异常），在下一轮把超时的 `in_flight` 任务放回队列。再思考：重复执行会带来什么问题，需要怎样的幂等键？
3. **退避与失败原因**：给 `Job` 增加 `next_run_at` 与 `errors: list[str]`，重试时设置 `2 ** attempt` 秒的退避；DLQ 中打印每个任务的失败原因列表。
4. **真正的流式与 backpressure（讲义练习 4）**：把 `_agent_fn` 改成生成器，每步之间 `time.sleep(0.2)`；测量首个 chunk 的延迟；再写一个"慢客户端"每 1 秒才取一次，观察 Agent 的执行节奏。
5. **事件总线加固**：`publish` 对每个处理器 `try/except`，失败的 `(event, handler, error)` 放入事件 DLQ；无订阅者的事件记入 `unhandled` 并打印告警。
6. **调度器（讲义练习 3）**：实现测验 Q12 的 `Scheduler`，把 `eval.nightly` 接到一个"读取当天 20 条 trace 并打分"的处理器上，模拟同一时刻触发两次，验证锁让第二次被跳过。

---

## 8. 常见坑

- **以为生成器就是流式**：如果被包装的函数先算完再返回列表，`yield` 只是在"回放"结果，首 token 延迟没有任何改善。
- **在条件判断里重复调用有随机性/副作用的函数**：`if f(x) and ...:` 之后再 `if f(x):`，两次结果可能不同；应把结果存进变量。
- **确定性的测试掩盖了 bug**：演示中 `fail_b` 恒为真或恒为假，重复调用看不出问题；测试要覆盖随机、间歇性失败。
- **先出队再执行**：进程崩溃即丢任务；需要 ack 机制。
- **立即重试**：对限流和瞬时故障无效，反而放大流量。
- **事件没人订阅就消失**：没有报错的"静默丢弃"是最难排查的故障之一。
- **cron 不加锁**：上一次还没跑完，下一次又开始，轻则重复工作，重则数据损坏（skill 原话）。
- **长任务挂在同步请求上**：超过 30 秒就应改为异步任务 + 轮询/回调。
