# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 22 节 生产扩展：队列、Checkpoints 与持久性 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数；会在系统临时目录建一个 SQLite 文件并在结束时删除） ｜ **依赖**：仅标准库（`asyncio`、`sqlite3`、`threading`、`json`、`tempfile`、`enum`、`dataclasses` 等）

---

## 1. 这份代码在考察什么

讲义把"多 agent 系统上生产"归结为一层 durable execution（持久执行）。代码用三个小演示对应其中三个核心构件：

1. **Checkpoint 恢复**：SQLite 表按 `(thread_id, super_step)` 存状态；worker 1 在第 3 步"崩溃"，worker 2 从最新 checkpoint 接着跑完——对应讲义的"每个 super-step 写 checkpoint、崩溃后从最新一行恢复"（LangGraph 的做法）。
2. **每个 agent 的三态队列**：Idle → Processing → Response 的状态机——对应 MegaAgent 的 per-agent 队列。
3. **async vs 线程**：500 个 50ms 的模拟 LLM 调用，分别用 `asyncio.gather` 和 500 个线程跑，比较耗时——对应讲义"LLM 调用是 I/O 密集型，async 是架构而不是优化"。

> 一句话：**用最少的标准库代码展示"状态落盘—从断点续跑—轻量并发"三件事**。同时要清楚它省略了什么：lease、幂等副作用/outbox、真正的生产者—消费者并发、内存测量、rainbow 部署——这些恰恰是讲义 Ship It 清单的重点，也是测验的考点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CheckpointStore` | 类 | 建表、`write` 写一行、`latest` 取最新一行 | checkpoint 存储 |
| `run_agent_with_checkpoint` | 函数 | 从最新 checkpoint 恢复或从头开始，每步 +1 并写 checkpoint，可在指定步"崩溃" | super-step 执行 + 恢复 |
| `AgentState` | Enum | `IDLE` / `PROCESSING` / `RESPONSE` | MegaAgent 三态 |
| `AgentQueue` | dataclass | 入队、`step()` 推进状态机 | per-agent 队列 |
| `demo_queue` | 函数 | 入队 2 条消息，调用 7 次 `step()` 并打印 | 状态机演示 |
| `sim_llm_call_async` / `sim_llm_call_sync` | 函数 | `asyncio.sleep` / `time.sleep` 模拟 50ms 的调用 | I/O 等待 |
| `bench_async` / `bench_threads` | 函数 | `gather` N 个协程 / 启动并 join N 个线程，计时 | 并发模型对比 |
| `demo_async_vs_threads` | 函数 | 各跑 500 个并打印比值 | async vs 线程 |
| `demo_checkpoint_resume` | 函数 | 临时数据库 → 崩溃 → 读最新 → 恢复 → 删除文件 | 崩溃恢复演示 |
| `main` | 函数 | 依次运行三个演示，打印结论 | 入口 |

数据流：`main` → `demo_checkpoint_resume`（`CheckpointStore` → `run_agent_with_checkpoint(crash_at=3)` 抛异常 → `latest` → 再次 `run_agent_with_checkpoint`）→ `demo_queue` → `demo_async_vs_threads`（`asyncio.run(bench_async(500))` → `bench_threads(500)`）。

---

## 3. 逐段精讲

### 3.1 `CheckpointStore`：一张表就是一个 checkpoint 日志

```python
class CheckpointStore:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT NOT NULL,
                super_step INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (thread_id, super_step)
            )
        """)

    def write(self, thread_id: str, super_step: int, state: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO checkpoints (thread_id, super_step, state_json) VALUES (?, ?, ?)",
            (thread_id, super_step, json.dumps(state)),
        )
        self.conn.commit()
```

- **复合主键 `(thread_id, super_step)`**：每个运行（thread）每一步一行，天然形成"追加式日志"，也保留了历史（可以回放、审计、回滚）。
- **`json.dumps(state)`**：状态必须可序列化——这就是讲义第一个前提"Serializable state"。带数据库连接、文件句柄的对象无法这样保存。
- **`INSERT OR REPLACE`**：同一步写两次会覆盖（实测写两次后只有 1 行，内容为后一次）。这让"重做某一步后再写 checkpoint"是幂等的；但它也会静默掩盖两个 worker 并发写同一步的冲突。
- **每次写完都 `commit()`**：保证这一步落盘后才继续——崩溃后最多丢失"正在执行的那一步"。
- `?` 占位符参数化查询：防 SQL 注入，也免去手动转义。

```python
    def latest(self, thread_id: str) -> tuple[int, dict] | None:
        row = self.conn.execute(
            "SELECT super_step, state_json FROM checkpoints WHERE thread_id = ? ORDER BY super_step DESC LIMIT 1",
            (thread_id,),
        ).fetchone()
        if row is None:
            return None
        return row[0], json.loads(row[1])
```

- 取最大的 super_step 即最新状态；主键索引让这个查询很快。
- `(thread_id,)`：单元素元组必须带逗号，否则只是加了括号的字符串。

### 3.2 `run_agent_with_checkpoint`：恢复 + 逐步执行

```python
    restored = store.latest(thread_id)
    if restored:
        super_step, state = restored
        super_step += 1
    else:
        super_step = 0
        state = {"counter": start}

    while state["counter"] < goal:
        if crash_at is not None and super_step == crash_at:
            print(f"    worker crashes at super_step={super_step}")
            raise RuntimeError("simulated crash")
        state["counter"] += 1
        store.write(thread_id, super_step, dict(state))
        super_step += 1
    return state["counter"]
```

- **恢复逻辑**：有 checkpoint 就从"最新步 + 1"继续，否则从 0 开始。恢复时 `start` 参数被忽略（状态以 checkpoint 为准）。
- **崩溃点在每步开头**：step 3 开始时就抛异常，这一步什么都没做，所以恢复后重做 step 3 没有任何副作用——这是一个"恰好安全"的崩溃位置。
- ⚠️ **真实情况更危险**：如果崩溃发生在"执行副作用之后、写 checkpoint 之前"，恢复后该步会被**重做**，副作用重复。测验 Q9 的实验：给每一步加一次"扣费"，崩溃放在扣费之后，结果扣费 6 次（step 3 两次）；加入以 `thread_id:super_step` 为键的去重后恢复为 5 次。去重记录必须持久化（与 checkpoint 同一事务，或交给支持 idempotency key 的外部服务），这就是讲义的 outbox 模式。
- ⚠️ **没有 lease**：讲义的恢复流程是"lease 超时 → 另一个 worker 接手"。这里 worker 2 是在同一进程里直接调用的；如果两个 worker 并发恢复同一个 `thread_id`，会各自从同一步开始重复执行（测验 Q10 给出了用条件 `UPDATE` 实现 lease 的代码）。
- ⚠️ "崩溃"是 Python 异常，同一进程、同一个数据库连接继续使用；真实崩溃是进程消失，未提交的事务回滚。
- `dict(state)`：写入前复制一份，避免后续修改影响已序列化的对象（这里 `json.dumps` 已经立即序列化，复制是防御性写法）。

### 3.3 `demo_checkpoint_resume`：临时数据库与清理

```python
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        store = CheckpointStore(db_path)
        try:
            run_agent_with_checkpoint(store, "t-1", crash_at=3, goal=5)
        except RuntimeError:
            pass
        last = store.latest("t-1")
        assert last is not None
        ...
        final = run_agent_with_checkpoint(store, "t-1", goal=5)
    finally:
        os.unlink(db_path)
```

- `NamedTemporaryFile(delete=False)` 只是借它生成一个唯一的文件名，`with` 结束后文件保留，由 SQLite 打开。
- `try/finally` 保证无论成功与否都删除数据库文件。
- ⚠️ 删除前没有 `store.conn.close()`。Linux 上可以删除已打开的文件，但在 Windows 上 `os.unlink` 会因文件被占用而失败。
- `assert last is not None`：既是检查，也帮助类型检查器把 `last` 的类型收窄为元组。

### 3.4 `AgentQueue`：三态状态机

```python
class AgentState(enum.Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    RESPONSE = "response"


@dataclass
class AgentQueue:
    agent_id: str
    state: AgentState = AgentState.IDLE
    in_queue: list[dict] = field(default_factory=list)
    out_queue: list[dict] = field(default_factory=list)

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

- 每条消息走完一个循环需要 3 次 `step()`：进入 PROCESSING（只改状态）→ 出队并产出回复、进入 RESPONSE → 回到 IDLE。两条消息 6 步，demo 调了 7 次，最后一次停在 idle。
- 用 `Enum` 而不是裸字符串：拼写错误会在运行时立刻暴露，`.value` 用于打印。
- ⚠️ 与讲义"producer-consumer queue"和 Takeaways"scale to thousands of concurrent agents"相比，这只是一个单线程、内存中的状态机：没有并发的生产者/消费者、不是线程安全的、不持久、没有失败重试和死信队列、没有 MegaAgent 的组内/组间两层协调、没有背压。
- ⚠️ `list.pop(0)` 是 O(n)，应使用 `collections.deque.popleft()` 或 `asyncio.Queue`。
- 若外部代码在 PROCESSING 状态清空了 `in_queue`，`pop(0)` 会抛 `IndexError`——状态与数据不一致时缺少保护。

### 3.5 async vs 线程

```python
async def sim_llm_call_async(delay: float = 0.05) -> None:
    await asyncio.sleep(delay)

async def bench_async(n: int) -> float:
    t0 = time.perf_counter()
    await asyncio.gather(*(sim_llm_call_async() for _ in range(n)))
    return time.perf_counter() - t0

def bench_threads(n: int) -> float:
    t0 = time.perf_counter()
    threads = [threading.Thread(target=sim_llm_call_sync) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return time.perf_counter() - t0
```

- `asyncio.gather(*(...))`：用生成器表达式创建 500 个协程对象，`*` 解包成参数，事件循环在单线程里并发地等待它们。`await asyncio.sleep` 时主动让出控制权。
- 线程版：先全部 `start()` 再全部 `join()`，500 个线程同时 `time.sleep`。**`time.sleep` 会释放 GIL**，所以线程也是真正并发等待的，总耗时并不是 500 × 50ms。
- `time.perf_counter()`：高精度单调时钟，适合测量耗时（不要用 `time.time()`）。
- ⚠️ 打印的"allocate ~1MB per thread stack"是**写死的说法**，代码并没有测量内存（讲义 Build It 说"reports wall-clock and peak memory (approximated)"）。另行测量（每种情况一个独立进程，`ru_maxrss` 增量）：5000 并发时线程约 54.6 MB（每个约 11 KB）、协程约 8.3 MB（每个约 1.7 KB），差 6–7 倍；"1MB/8MB 每线程"是栈的**虚拟地址预留**，物理内存按需分配。
- ⚠️ 讲义预期"thread version takes several seconds"，实测只有约 0.09 s（1.7 倍）；差距主要来自线程的创建/销毁开销，并随并发数增大而扩大（5000 时 0.67 s vs 0.08 s）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| SQLite + JSON 存 checkpoint | 零依赖、可直接查看 | 生产用 Postgres（LangGraph 默认）；大状态放对象存储，checkpoint 存引用；状态 schema 需版本化 |
| 每步 `commit` | 崩溃最多丢一步 | 写放大；可按 super-step 批量提交 |
| `INSERT OR REPLACE` | 重写同一步幂等 | 掩盖并发冲突；应配合 lease + fencing token |
| 用异常模拟崩溃 | 演示简单 | 不是真的进程退出；没有 lease、心跳、超时接管 |
| 无副作用的计数器 | 让恢复一定正确 | 回避了最难的部分；真实系统必须有去重键/outbox |
| 内存中的三态状态机 | 直观展示状态转移 | 不并发、不持久、无重试；生产用消息队列或 `asyncio.Queue` + 持久化 |
| `asyncio.sleep`/`time.sleep` 模拟 LLM | 可控、可复现 | 真实 LLM 调用还有连接池、速率限制、流式输出；线程版差距主要在创建开销 |
| 内存差异只打印不测量 | 省事 | 结论缺乏证据；应用 `tracemalloc`/`ru_maxrss` 实测 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `sqlite3` 基础 | `sqlite3.connect(path)`、`conn.execute(sql, params)`、`.fetchone()`、`conn.commit()` | 标准库内置的嵌入式数据库 |
| 参数化 SQL | `"... VALUES (?, ?, ?)", (thread_id, super_step, ...)` | 用 `?` 占位，防注入 |
| 单元素元组 | `(thread_id,)` | 逗号才是元组的标志 |
| 三引号多行字符串 | `"""CREATE TABLE ..."""` | 写多行 SQL |
| `json.dumps` / `json.loads` | `json.dumps(state)`、`json.loads(row[1])` | 字典 ↔ JSON 字符串 |
| 联合类型 | `tuple[int, dict] \| None`、`int \| None = None` | 可能返回 `None` 的函数 |
| 元组解包 | `super_step, state = restored` | 一次取出两个值 |
| 抛出与捕获异常 | `raise RuntimeError(...)`、`except RuntimeError: pass` | 模拟崩溃；`pass` 表示忽略 |
| `try/finally` | `demo_checkpoint_resume` | 无论是否出错都执行清理 |
| `with` 上下文管理器 | `with tempfile.NamedTemporaryFile(...) as f:` | 自动关闭文件 |
| `assert` | `assert last is not None` | 断言条件成立，否则抛 `AssertionError` |
| `enum.Enum` | `class AgentState(enum.Enum)`、`a.state.value` | 有名字的常量集合 |
| `@dataclass` + `field` | `in_queue: list[dict] = field(default_factory=list)` | 可变默认值用工厂函数 |
| `async def` / `await` | `async def sim_llm_call_async(...)`、`await asyncio.sleep(delay)` | 定义协程；在 I/O 处让出 |
| `asyncio.gather` + 解包 | `await asyncio.gather(*(coro() for _ in range(n)))` | 并发等待多个协程 |
| `asyncio.run` | `asyncio.run(bench_async(500))` | 创建事件循环并运行到结束 |
| `threading.Thread` | `Thread(target=sim_llm_call_sync)`、`.start()`、`.join()` | 创建、启动、等待线程 |
| `time.perf_counter` | `t0 = time.perf_counter()` | 高精度计时 |
| `str.format` 与条件表达式 | `"{:.1f}x".format(a / b if b > 0 else float("inf"))` | 防止除以 0 |
| f-string 宽度 | `{a.state.value:11s}` | 左对齐宽 11 |

---

## 6. 运行结果解读

实际运行（Python 3，总耗时约 0.23 秒）：

```text
CHECKPOINT RESUME — worker crashes mid-run, second worker resumes
  worker 1 starts thread t-1, targeting counter=5
    worker crashes at super_step=3
  last checkpoint: super_step=2, state={'counter': 3}
  worker 2 resumes thread t-1
  worker 2 completed; final counter = 5

PER-AGENT QUEUE — 3-state machine (idle / processing / response)
  initial: idle  in_queue=2
  state=processing  in=2 out=0
  state=response    in=1 out=1
  state=idle        in=1 out=1
  state=processing  in=1 out=1
  state=response    in=0 out=2
  state=idle        in=0 out=2
  state=idle        in=0 out=2

ASYNC vs THREADS — 500 concurrent 'LLM calls' (50ms each)
  async (asyncio):  0.054 s
  threads:          0.089 s
  ratio: threads are 1.7x slower (and allocate ~1MB per thread stack)
```

逐项解读：

- **Checkpoint**：worker 1 完成了 step 0–2（counter 1–3），在 step 3 开始时崩溃；worker 2 从 `(2, {'counter': 3})` 恢复，执行 step 3、4，最终 counter = 5，没有重复也没有丢失。讲义"checkpoint resume succeeds after simulated crash"成立。
- **三态队列**：每条消息 3 步，与 3.4 的追踪一致；第 7 步队列为空，保持 idle。
- **async vs 线程**：async 0.054 s，几乎等于单次 50ms 延迟，说明 500 个协程完全并发；线程 0.089 s，同样是并发等待，只是多了创建 500 个线程的开销。讲义预期"线程需要几秒、内存大几个数量级"在本 demo 中都没有体现（数值依机器不同而变化）。另行测量的扩展数据：

| 并发数 | async 耗时 | 线程耗时 | async 内存增量 | 线程内存增量 |
|-------|-----------|---------|--------------|------------|
| 500 | 0.054 s | 0.110 s | 1.4 MB | 7.6 MB |
| 2000 | 0.061 s | 0.250 s | 3.6 MB | 23.6 MB |
| 5000 | 0.079 s | 0.666 s | 8.3 MB | 54.6 MB |

  趋势很清楚：async 的耗时与内存几乎不随并发数增长，线程两者都近似线性增长。这才是讲义"at LLM-agent scale, async is the architecture"的实际依据。

---

## 7. 动手改一改

1. **副作用与去重**：在每一步加一次"扣费"（往列表或一张表里写记录），把崩溃点移到扣费之后、写 checkpoint 之前，观察重复扣费；再加一张 `effects(dedup_key PRIMARY KEY)` 表，与 checkpoint 在**同一事务**中写入，验证恢复后不再重复（参考测验 Q9）。
2. **Outbox**（讲义练习 2）：把副作用改为写入 `outbox(id, dedup_key, payload, done)`；另写一个执行器循环读取未完成的行、执行、标记 done；故意让执行器运行两次，确认外部效果只发生一次。
3. **Lease 与 fencing**：用测验 Q10 的 `acquire` 实现租约，在两个 `threading.Thread` 中同时恢复同一个 `thread_id`，确认只有一个能执行；再加一个递增的 `lease_version`，写 checkpoint 时校验版本。
4. **真正的生产者—消费者**：把 `AgentQueue` 改为基于 `asyncio.Queue` 的协程：一个生产者不断入队，多个 agent 消费者并发处理，处理逻辑里 `await asyncio.sleep` 模拟 LLM；统计吞吐量，并加上最大队列长度做背压。
5. **测量内存**：给 `demo_async_vs_threads` 加上 `tracemalloc` 或 `resource.getrusage` 的测量，把并发数扩展到 2000、5000，复现 6 节的表格。
6. **Rainbow deploy**（讲义练习 3）：写两个版本的 `run_agent` 函数（v1、v2），新建的 `thread_id` 按哈希一半路由到各版本，把版本号写进 checkpoint；恢复时按 checkpoint 中的版本选择函数，确认进行中的 v1 运行不会被 v2 接管。

---

## 8. 常见坑

- **以为有 checkpoint 就不会重复执行**：checkpoint 之间的工作都可能被重做，副作用必须幂等。
- **去重记录放在内存里**：进程崩溃就丢了，等于没有去重；必须持久化并与状态在同一事务中更新，或用外部服务的 idempotency key。
- **check-then-act 抢租约**：先 `SELECT` 再 `UPDATE` 会产生竞态，必须用一条带条件的 `UPDATE` 并检查 `rowcount`。
- **状态里放不可序列化的对象**：数据库连接、锁、打开的文件、lambda 都无法 `json.dumps`；状态要设计成纯数据。
- **在 async 代码里调用阻塞函数**：`time.sleep`、同步 HTTP 客户端、CPU 密集计算会卡住整个事件循环；用 `asyncio.to_thread` 或进程池隔离。
- **用"每线程 1MB"推导内存**：那是虚拟栈预留，不是常驻内存；要做容量规划请实测。
- **用 `list.pop(0)` 做队列**：O(n)；用 `deque` 或 `asyncio.Queue`。
- **部署时杀掉长运行 agent**：多小时的运行需要 rainbow 部署和版本化的 checkpoint schema。
