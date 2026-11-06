# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 14 节 用于 Agents 的 Actor 模型：异步消息与类型化运行时 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`collections.deque`、`dataclasses`、`typing`）；不需要 AutoGen、API key 或网络

---

## 1. 这份代码在考察什么

用 170 行标准库代码模仿 AutoGen v0.4 Core 层的 actor runtime：

1. **消息是唯一的交互方式**：`Message` 带 `sender / recipient / topic / body / mid`；actor 只通过 `runtime.send(...)` 发消息，不直接调用对方的方法。
2. **投递与处理解耦**：`send` 只把消息追加到队列就返回；`run_until_idle` 才真正一条条投递给接收方的 `receive`。
3. **故障隔离 + dead-letter queue**：handler 抛出的异常被 runtime 捕获，失败消息进入 `dead_letters`，其他消息照常处理。
4. **两 actor 协作**：`ChecklistAgent` 把 3 段代码分发给 `ReviewerAgent` 评审，收集结果后得出共识。

> 一句话：**把"调用"变成"发消息"，失败就被关在了单个 actor 的 handler 里**。但也要看清代价与简化：失败被隔离的同时也被"藏"了起来（`ChecklistAgent` 因此会过早得出共识）；代码用的是全局单队列、单线程，并没有讲义说的"每个 actor 私有收件箱"和"天然并发"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Message` | dataclass | 发送方、接收方、topic、body、自增编号 `mid` | Message（类型化载荷） |
| `Actor` | 基类 | 只有 `name` 和抽象的 `receive(message, runtime)` | Actor |
| `Runtime` | dataclass | 注册表、全局队列、DLQ、计数器、trace、处理上限 | Runtime / agent host |
| `Runtime.send` | 方法 | 生成 `mid`、入队、写 trace，立即返回 | 非阻塞发送 |
| `Runtime.run_until_idle` | 方法 | 出队 → 找 actor → `try receive` → 失败进 DLQ | 投递循环 + 故障隔离 |
| `ReviewerAgent` | Actor 子类 | `review`：子串检查 `eval(` 与 `except:`，回复结果；`crash_me`：故意抛异常 | 专项 agent |
| `ChecklistAgent` | Actor 子类 | `start`：把片段逐个发给 reviewer；`review_result`：收集结果、计算共识 | 协调 agent |
| `main` | 函数 | 注册两个 actor，发 `start` 与 `crash_me`，运行，打印 trace / 共识 / DLQ | 演示 |

数据流：`__user__ --start--> checklist --review×3--> reviewer --review_result×3--> checklist`；另有 `__user__ --crash_me--> reviewer`（抛异常 → DLQ）。所有消息都经过同一个 `runtime.queue`。

---

## 3. 逐段精讲

### 3.1 `Message` 与 `Actor`

```python
@dataclass
class Message:
    sender: str
    recipient: str
    topic: str
    body: Any
    mid: int = 0


class Actor:
    def __init__(self, name: str) -> None:
        self.name = name

    def receive(self, message: Message, runtime: "Runtime") -> None:
        raise NotImplementedError
```

- `Message` 是讲义里"Typed payload"的最简形式：路由信息（sender / recipient）+ 分类（topic）+ 内容（body）+ 编号（mid，由 runtime 分配）。
- `body: Any`：没有对载荷做类型约束。AutoGen Core 中消息通常是具体的 dataclass / Pydantic 类型，handler 按消息**类型**分派；本代码按 `topic` 字符串分派。
- `topic` 只是一个字段，没有订阅机制。讲义 Key Terms 中 Topic 是"Named publish-subscribe route between actors"，即发送方发往一个主题、由所有订阅者接收；这里实际是**点对点**直接寻址。
- `Actor.receive` 抛 `NotImplementedError`：相当于抽象方法，子类必须覆盖。也可以用 `abc.ABC` + `@abstractmethod` 在实例化时就报错。
- `"Runtime"` 加了引号：`Runtime` 在下面才定义，这是**前向引用**（文件开头有 `from __future__ import annotations`，其实不加引号也可以）。
- ⚠️ `Message` 是可变 dataclass，`body` 是引用传递：接收方修改 `message.body` 会影响发送方仍持有的对象。真正的 actor 系统要么序列化消息，要么使用不可变消息（`@dataclass(frozen=True)`）。`ChecklistAgent` 用 `dict(message.body)` 复制一份，就是在防这个问题。

### 3.2 `Runtime.send`：只入队，立即返回

```python
    def send(self, sender, recipient, topic, body):
        self.counter += 1
        msg = Message(sender=sender, recipient=recipient,
                      topic=topic, body=body, mid=self.counter)
        self.queue.append(msg)
        self.trace.append(
            f"[send m{msg.mid:03d}] {sender} -> {recipient} topic={topic} body={body}"
        )
```

- 这就是讲义"`send(agent_b, msg)` puts the message in agent_b's inbox and returns"的体现：发送方不会等待接收方处理。
- `counter` 全局自增，`mid` 因此全局唯一且单调，便于在 trace 中对照。
- 不检查接收方是否存在——到投递时才发现（进 DLQ）。这与真实的分布式系统一致：发送时往往无法知道对方是否在线。
- ⚠️ 讲义说每个 actor 有私有收件箱；这里是所有 actor 共享的**一个** `deque`。

### 3.3 `Runtime.run_until_idle`：投递循环与故障隔离

```python
    def run_until_idle(self) -> None:
        processed = 0
        while self.queue and processed < self.max_messages:
            msg = self.queue.popleft()
            actor = self.actors.get(msg.recipient)
            if actor is None:
                self.dead_letters.append((msg, f"no actor {msg.recipient!r}"))
                self.trace.append(f"[DLQ m{msg.mid:03d}] no actor {msg.recipient!r}")
                continue
            try:
                actor.receive(msg, self)
                self.trace.append(
                    f"[recv m{msg.mid:03d}] {actor.name} handled topic={msg.topic}"
                )
            except Exception as e:
                self.dead_letters.append((msg, f"{type(e).__name__}: {e}"))
                self.trace.append(
                    f"[FAIL m{msg.mid:03d}] {actor.name} raised "
                    f"{type(e).__name__}: {e}  (others keep running)"
                )
            processed += 1
```

- `deque.popleft()` 是 O(1) 的队首出队，这里实现了全局 **FIFO**。
- `try/except Exception`：这一行就是"故障隔离"的全部实现。handler 的异常不会冲出循环，失败消息连同错误描述一起进入 `dead_letters`。
- **trace 的顺序**：`[recv]` 是在 `receive` **返回之后**才写入的，而 handler 内部调用 `send` 时会先写 `[send]`。所以在 trace 里，一条消息引发的新消息总是出现在它自己的 `[recv]` 行之前。
- `max_messages=100`：防止消息风暴（例如两个 actor 无限互相回复）。
- ⚠️ 名字叫"until idle"，但达到上限时直接返回，队列里可能还有消息，调用方没有任何提示。实测两个 actor 互相 ping，返回时 `counter=101`、队列里还剩 1 条。
- ⚠️ 未知接收方走 `continue`，跳过了 `processed += 1`，不受上限约束。
- ⚠️ 失败不通知发送方：发送方不知道请求失败，只会一直等待（见 3.5）。
- ⚠️ handler 的效果不是原子的：handler 若先 `send` 再抛异常，已发出的消息仍会被投递（实测）。
- 单线程顺序执行：讲义说"actors process their inbox concurrently"，这里一次只处理一条消息，一个慢 handler 会阻塞所有 actor。

### 3.4 `ReviewerAgent`：专项评审

```python
    def receive(self, message, runtime):
        if message.topic == "review":
            code = str(message.body)
            issues = []
            if "eval(" in code:
                issues.append("uses eval")
            if "except:" in code:
                issues.append("bare except")
            ok = len(issues) == 0
            self.verdicts.append((code, ok))
            runtime.send(sender=self.name, recipient=message.sender,
                         topic="review_result", body={"ok": ok, "issues": issues})
        elif message.topic == "crash_me":
            raise RuntimeError("simulated handler failure")
```

- `self.verdicts` 是 actor 的**私有状态**：外部不应直接读取（Python 无法强制，只能靠约定）。
- 回复地址是 `message.sender`：典型的"请求—回复"模式，接收方不需要事先知道谁会找它。
- 评审规则是子串匹配（真实系统中是一次 LLM 调用或静态分析）：
  - 误报：`ast.literal_eval(` 包含 `eval(`，实测被判为 `uses eval`；
  - 漏报：`eval (x)`（有空格）实测被判为 ok；`except :`、`except BaseException:` 也检测不到。
  - 更可靠的做法是用 `ast.parse` 遍历语法树。
- `crash_me` 分支专门用来演示故障隔离。
- 未知 topic 会被**静默忽略**（既不报错也不回复）。

### 3.5 `ChecklistAgent`：分发与共识

```python
    def receive(self, message, runtime):
        if message.topic == "start":
            for snippet in message.body:
                runtime.send(sender=self.name, recipient=self.partner,
                             topic="review", body=snippet)
        elif message.topic == "review_result":
            self.results.append(dict(message.body))
            if all(r["ok"] for r in self.results):
                self.consensus = True
            if len(self.results) == 3:
                self.consensus = all(r["ok"] for r in self.results)
```

- `start` 时一次性 fan-out：每个片段一条 `review` 消息。这里体现了"不等待"：三条消息都发出后 handler 就返回了。
- 收到结果后追加到 `self.results`，再计算共识。
- ⚠️ **共识逻辑有三个问题**（均已实测）：
  1. **过早置 True**：只要"已收到的结果全部 ok"就置 True，第一个 ok 结果到达时 consensus 就成了 True。
  2. **写死 3**：最终判定只在恰好收到 3 个结果时触发。2 个片段 `["x=1", "eval(1)"]` → True；4 个片段 `["x=1","y=2","z=3","eval(1)"]` → 第 3 个时为 True，第 4 个失败也改不回来 → True。
  3. **等不齐**：reviewer 处理某个片段时抛异常，该消息进 DLQ，checklist 永远收不到第 3 个结果，consensus 停在 True。
- 讲义说两个 actor "exchange messages until consensus"，实际只有一轮"分发—回复"，没有协商。
- 修复思路：在 `start` 时记录期望数量；收齐（结果 + 失败）之后再下结论；runtime 在失败时给发送方回一条 `delivery_failed`。完整代码见测验 Q9。

### 3.6 `main`：编排演示

- 先发 m001（`start`，3 个片段）和 m002（`crash_me`），再 `run_until_idle()`。
- 第三个片段 `"def silent(): \n    try:\n        f()\n    except:\n        pass"` 是多行字符串，打印 trace 时会换行显示。
- 最后打印：完整 trace、`checklist.consensus`（直接读取了 actor 的内部状态——在 demo 中为了展示，真实系统应通过消息查询）、DLQ 内容。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 全局单 FIFO 队列 | 实现最短，trace 顺序确定 | 没有私有收件箱、没有并发；生产每个 actor 一个队列（`asyncio.Queue` 或消息中间件） |
| 单线程顺序投递 | 结果可复现、易读 | 慢 handler 阻塞全部 actor；生产用协程 / 线程池 / 多进程 |
| 按 `topic` 字符串分派 | 简单 | 拼写错误被静默忽略；生产按消息类型分派、对未知消息报警 |
| `body: Any` 可变引用 | 方便 | 接收方可篡改发送方数据；生产序列化或使用不可变消息 |
| `except Exception` 全部进 DLQ | 演示故障隔离 | 不区分可重试 / 不可重试；不通知发送方；没有重试 |
| `max_messages` 上限 | 防消息风暴 | 达到上限时静默返回；应返回状态或告警 |
| 子串匹配做代码评审 | 离线、确定 | 误报与漏报；生产用 AST / 静态分析 / LLM |
| 共识写死为 3 个结果 | 贴合 demo | 片段数变化或有失败时结论错误 |
| 两个 actor 固定来回 | 教学最小示例 | skill 文件认为两个 actor 固定来回应改用 prompt chain，actor 在 ≥3 个或需要异步并发时才值回成本 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `collections.deque` | `queue: deque[Message]`、`self.queue.popleft()` | 双端队列，两端增删都是 O(1)；`list.pop(0)` 是 O(n) |
| `@dataclass` + `field(default_factory=...)` | `actors: dict[str, Actor] = field(default_factory=dict)` | 可变默认值必须用工厂，否则所有 `Runtime` 实例共享同一个容器 |
| 继承与 `super().__init__` | `class ReviewerAgent(Actor)`、`super().__init__(name)` | 子类先调用父类构造函数初始化 `name` |
| 抽象方法的简易写法 | `raise NotImplementedError` | 调用未覆盖的方法时报错；更正式的写法是 `abc.abstractmethod` |
| 前向引用 | `runtime: "Runtime"` | 类型注解中引用后面才定义的类 |
| `try / except Exception as e` | `run_until_idle` 中 | 捕获所有普通异常（不包括 `KeyboardInterrupt` 等） |
| `type(e).__name__` | `f"{type(e).__name__}: {e}"` | 取异常类名，如 `RuntimeError` |
| `continue` | 未知 actor 分支 | 跳过本轮剩余代码，直接进入下一次循环 |
| f-string 补零 | `m{msg.mid:03d}` | 宽度 3、不足补 0，如 `m002` |
| `!r` | `{msg.recipient!r}` | 用 `repr()` 显示，字符串带引号 |
| 关键字参数调用 | `runtime.send(sender=self.name, recipient=..., ...)` | 参数多时更清晰 |
| `all()` + 生成器 | `all(r["ok"] for r in self.results)` | 全部为真才为真；空列表时为 True |
| `dict(...)` 浅复制 | `self.results.append(dict(message.body))` | 防止共享同一个字典对象 |
| 可选类型 | `self.consensus: bool \| None = None` | 三态：未决定 / 真 / 假 |
| 多行字符串转义 | `"def silent(): \n    try:\n ..."` | `\n` 表示换行 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，瞬间完成；为便于阅读，第三个片段的多行内容已省略）：

```text
[send m001] __user__ -> checklist topic=start body=[...3 个片段...]
[send m002] __user__ -> reviewer topic=crash_me body={}
[send m003] checklist -> reviewer topic=review body=def add(a, b): return a + b
[send m004] checklist -> reviewer topic=review body=def hazard(): eval('1+1')
[send m005] checklist -> reviewer topic=review body=def silent(): ...
[recv m001] checklist handled topic=start                  ← m003-m005 是处理 m001 时发出的
[FAIL m002] reviewer raised RuntimeError: simulated handler failure  (others keep running)
[send m006] reviewer -> checklist topic=review_result body={'ok': True, 'issues': []}
[recv m003] reviewer handled topic=review
[send m007] reviewer -> checklist topic=review_result body={'ok': False, 'issues': ['uses eval']}
[recv m004] reviewer handled topic=review
[send m008] reviewer -> checklist topic=review_result body={'ok': False, 'issues': ['bare except']}
[recv m005] reviewer handled topic=review
[recv m006] checklist handled topic=review_result
[recv m007] checklist handled topic=review_result
[recv m008] checklist handled topic=review_result

checklist consensus: False
dead-letter queue:   1 message(s)
  DLQ m002 (RuntimeError: simulated handler failure) __user__ -> reviewer topic=crash_me
```

逐项解读：

- **处理顺序**严格按全局 FIFO：m001 → m002 → m003～m005 → m006～m008。m002 在 m003 之前，是因为它在 `run_until_idle` 之前就入队了。
- **故障隔离**：m002 让 reviewer 抛异常，但 reviewer 随后照常处理了 m003～m005。注意：被隔离的是"一条消息的处理"，reviewer 对象本身没有被重启或标记为故障。
- **共识为 False**：三个结果是 ok / eval / bare except，第 3 个结果到达时重新计算为 False——这是"写死 3"刚好与片段数一致时的正确结果。但在处理 m006 之后、m007 之前的瞬间，consensus 其实是 True（过早共识）。
- **DLQ 只有 1 条**，即故意制造的 `crash_me`。

额外的探针实验（导入模块后调用，不修改源码）：

| 实验 | 结果 | 说明 |
|------|------|------|
| 片段 `["x=1", "eval(1)"]` | consensus = True | 过早置 True 且不会被纠正 |
| 片段 `["x=1","y=2","z=3","eval(1)"]` | consensus = True | 写死 3 |
| reviewer 在某个片段上抛异常 | consensus = True，DLQ 1 条 | 失败未通知，等不齐 |
| 原 demo，`max_messages=5` | consensus = True（只收到 1 个结果），队列剩 2 条 | 中途停止也"有结论" |
| `ast.literal_eval('1')` | `uses eval` | 子串匹配误报 |
| `eval (x)` | ok | 子串匹配漏报 |
| 两个 actor 互相 ping | `counter=101`，队列剩 1 条 | `run_until_idle` 返回时并不空闲 |
| handler 先 send 再抛异常 | 已发出的消息仍被投递 | 效果不是原子的 |

---

## 7. 动手改一改

1. **修复共识**：在 `start` 时记录期望数量，收齐（结果 + 失败）再下结论；runtime 在 handler 失败时向发送方回一条 `delivery_failed`（参考测验 Q9）。
2. **DLQ 策略（讲义练习 1）**：区分可重试与不可重试异常，可重试的最多重试 3 次；统计 DLQ 命中率；`run_until_idle` 返回"是否真正空闲"。
3. **私有收件箱 + 真并发**：用 `asyncio.Queue` 给每个 actor 一个收件箱、一个处理协程；用在途消息计数判断空闲；两个慢 actor 并发时测出耗时差异（参考测验 Q10）。
4. **SelectorGroupChat（讲义练习 2）**：写一个 selector actor 保存对话历史、挑选下一位发言者，`APPROVE` 或 `max_turns` 时终止（参考测验 Q12）。
5. **OTel 埋点（讲义练习 4）**：在 `run_until_idle` 中为每条消息记录一个 span 字典（开始 / 结束时间、`gen_ai.agent.name`、`gen_ai.operation.name`、`mid`、是否失败），最后打印成表格。
6. **跨进程传输（讲义练习 3）**：把 `send` 改为向一个本地 HTTP 服务 POST JSON，另一个进程拉取并处理；体会"分布式只是换了传输层"，以及随之而来的序列化、超时与重复投递问题。

---

## 8. 常见坑

- **把故障隔离当作"不用管失败"**：失败被关进 DLQ 之后，依赖它的 actor 会永远等待或基于不完整数据下结论；必须有失败通知与超时。
- **共识 / 汇总逻辑写死数量**：应该从请求中得出期望数量，并区分"未完成""失败""通过"三种状态。
- **共享可变消息体**：传递 dict / list 的引用等于共享内存，违反 actor 模型的前提。
- **以为单线程队列就是并发**：全局 FIFO 只是"异步风格"，没有并发收益；慢 handler 会阻塞所有人。
- **未知 topic 静默忽略**：拼写错误的 topic 不会报错，消息就这样消失了；至少要记录日志。
- **"until idle"其实没 idle**：达到处理上限时要显式告知调用方。
- **重试导致重复副作用**：handler 中途失败时已发出的消息不会撤回，重试前要考虑幂等。
- **只有两个 actor 却上 actor 框架**：skill 文件明确建议这种情况改用 prompt chain。
