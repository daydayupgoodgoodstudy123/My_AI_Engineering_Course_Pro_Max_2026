# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 09 节 并行、Swarm 与网络化架构 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数，约 4.2 秒） ｜ **依赖**：仅标准库（`queue`、`threading`、`time`、`dataclasses`）

---

## 1. 这份代码在考察什么

脚本在同一组"耗时不等"的任务上比较三种调度方式：

1. **顺序执行**（1 个 worker）：基线，耗时 = 总工作量。
2. **固定分配**（4 个 worker，每个任务预先指定给某个 worker）：模拟 supervisor 提前派活，但分配得很糟。
3. **Swarm**（4 个 worker 从共享 `queue.Queue` 拉任务）：没有中央调度，谁空闲谁拿下一个。

它要说明讲义的核心论点：**当任务耗时差异大、难以预测时，"拉取式"的共享队列能自动均衡负载**，而预分配会被最忙的 worker 拖垮。同时它也展示了 swarm 的代价：没有中央轨迹，调试只能靠每任务 ID 与持久日志（脚本最后一行）。

> 一句话：**用 8 个 `time.sleep` 任务演示"拉取式队列 = 自适应负载均衡"**。需要看清的是：它的"固定分配"是刻意构造的最坏情况，而 swarm 的好结果也依赖于队列里慢任务恰好排在前面。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Task` | dataclass | `task_id`、`duration`、`pre_assigned`（仅固定分配使用） | 工作单元 |
| `fake_work` | 函数 | `time.sleep(duration)` 模拟一次 LLM/工具调用 | I/O 密集型工作 |
| `run_sequential` | 函数 | 单线程依次处理所有任务 | 基线 |
| `run_fixed_assignment` | 函数 | 按 `pre_assigned` 分组，每个线程串行跑自己的列表 | supervisor 式预分配 |
| `run_swarm` | 函数 | 共享 `queue.Queue`，每个线程循环 `get_nowait` 直到队列空 | swarm / 拉取式调度 |
| `make_tasks` | 函数 | 4 个 0.4s 慢任务 + 4 个 0.1s 快任务，并给出"最坏"预分配 | 可变耗时工作负载 |
| `main` | 函数 | 打印理想时间、三种策略的耗时与计数、加速比 | 演示入口 |

数据流：`make_tasks` → 同一个任务列表分别交给 `run_sequential` / `run_fixed_assignment` / `run_swarm` → 每个函数返回 `(耗时, 每 worker 任务数)` → `main` 打印并计算加速比。

---

## 3. 逐段精讲

### 3.1 `Task` 与 `fake_work`

```python
@dataclass
class Task:
    task_id: int
    duration: float
    pre_assigned: int  # for the fixed-assignment baseline


def fake_work(task: Task) -> str:
    time.sleep(task.duration)
    return f"task-{task.task_id}-done"
```

- `pre_assigned` 只服务于固定分配基线；swarm 完全忽略它——这正是"没有中央分配"的体现。
- `time.sleep` 是阻塞系统调用，会**释放 GIL**。所以多个线程同时 `sleep` 时互不影响，模拟的是"agent 在等 LLM API 返回"的 I/O 密集场景。若把它换成纯 Python 的计算循环，线程版本几乎得不到加速（CPython GIL），需要多进程。
- 返回值（`"task-0-done"`）在三个调度函数里都**没有被收集**——讲义图中的 "results pool" 在代码里不存在，只统计了任务数。

### 3.2 顺序基线

```python
def run_sequential(tasks: list[Task]) -> tuple[float, dict[int, int]]:
    t0 = time.time()
    counts: dict[int, int] = {0: 0}
    for t in tasks:
        fake_work(t)
        counts[0] += 1
    return time.time() - t0, counts
```

- 耗时 ≈ `4 × 0.4 + 4 × 0.1 = 2.0s`，即总工作量（work-seconds）。
- 返回 `(float, dict)` 元组，三个调度函数接口一致，方便 `main` 统一处理。
- 计时用 `time.time()`（墙钟时间）。严格的性能测量更推荐 `time.perf_counter()`，它单调且精度更高。

### 3.3 固定分配：supervisor 式预分配

```python
def run_fixed_assignment(tasks: list[Task], n_workers: int) -> tuple[float, dict[int, int]]:
    per_worker: dict[int, list[Task]] = {i: [] for i in range(n_workers)}
    for t in tasks:
        per_worker[t.pre_assigned].append(t)
    counts: dict[int, int] = {i: 0 for i in range(n_workers)}

    def worker(wid: int) -> None:
        for t in per_worker[wid]:
            fake_work(t)
            counts[wid] += 1

    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_workers)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    return time.time() - t0, counts
```

- 先按 `pre_assigned` 把任务分桶，然后每个线程只跑自己桶里的任务。总耗时 = **最忙那个 worker 的串行耗时**（makespan）。
- `worker` 是嵌套函数（闭包），直接读写外层的 `per_worker` 和 `counts`。
- `counts[wid] += 1` 没加锁：每个线程只写自己的键，不存在两个线程同时改同一个键的竞争，所以这里是安全的（与 swarm 版本加锁形成对比）。
- 先全部 `start()` 再全部 `join()`：如果写成"start 一个 join 一个"，就退化成顺序执行。

### 3.4 Swarm：共享队列拉取

```python
def run_swarm(tasks: list[Task], n_workers: int) -> tuple[float, dict[int, int]]:
    q: queue.Queue = queue.Queue()
    for t in tasks:
        q.put(t)
    counts: dict[int, int] = {i: 0 for i in range(n_workers)}
    lock = threading.Lock()

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

- `queue.Queue` 是线程安全的 FIFO 队列，内部自带锁，多个线程同时 `get` 不会拿到同一个任务。
- `get_nowait()` 在队列空时立即抛 `queue.Empty`，worker 就退出。因为任务在启动线程前已全部入队，这种"空即结束"在静态任务集下是正确的。
- `with lock:` 保护计数器。这里其实也是"每线程写自己的键"，锁不是必需的，但它示范了"共享状态要加锁"的好习惯。
- `q.task_done()` 用来配合 `q.join()`，但代码里没有调用 `q.join()`，而是用线程 `join()` 等待。
- 关键行为：**worker 只在空闲时才拉任务**，所以耗时短的 worker 会自然地多拿任务——这就是讲义说的 "fast workers pull next jobs"。

⚠️ 与讲义 Ship It 的差距：
- 如果 `fake_work` 抛异常，线程直接结束，任务丢失、`task_done` 不会调用——没有重试，也谈不上幂等；
- 讲义说 worker 可以"投递后续任务"，但"队列空就退出"在动态场景下会让其他 worker 过早退出；
- 没有优先级、没有 trace ID、队列是内存态的。
- 测验 Q12 给出了带重试、哨兵退出和 `q.join()` 的改写版本。

### 3.5 `make_tasks`：刻意构造的最坏预分配

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

实际生成的任务（已打印验证）：

| task_id | duration | pre_assigned |
|---------|----------|--------------|
| 0–3 | 0.4 | 0 |
| 4 | 0.1 | 1 |
| 5 | 0.1 | 2 |
| 6 | 0.1 | 3 |
| 7 | 0.1 | **0** |

- ⚠️ `(7 − 3) % 4 = 0`，所以 worker 0 除了 4 个慢任务还多了 1 个快任务，共 5 个、1.7s。docstring "others get fast ones" 和 `main` 里的说明都漏了这一点。
- 队列中慢任务排在前面，相当于"按耗时降序"（LPT）排队，这是贪心调度的有利顺序。如果把 1 个长任务放到许多短任务之后，swarm 会明显劣于最优（测验 Q9：1.30s vs 1.00s）。
- 如果改成轮询分配 `pre_assigned = i % 4`，固定分配同样只要 0.50s（已验证）。所以 3.40× 的差距来自"分配得很糟"，而不是"预分配本质上必然更慢"。

### 3.6 `main`：理想时间与加速比

```python
    total_work = sum(t.duration for t in tasks)
    print(f"Ideal parallel time with {n_workers} workers: {total_work / n_workers:.2f}s")
    ...
    speedup_vs_seq = seq_time / swarm_time if swarm_time > 0 else float("inf")
```

- 理想并行时间 = 总工作量 / worker 数 = 0.50s，这是任何调度的下界之一（另一个下界是最长单个任务 0.4s，取二者较大值）。
- 条件表达式 `a if cond else b` 防止除以 0；`float("inf")` 表示无穷大。
- 加速比 = 基线耗时 / swarm 耗时。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| `time.sleep` 模拟工作 | 结果确定、几乎不占 CPU，适合演示 I/O 密集的 LLM 调用 | 不能代表 CPU 密集任务；真实系统中耗时还受 API 限流影响 |
| 线程 + `queue.Queue` | 标准库即可实现，代码短 | 内存队列，进程崩溃全部丢失；生产用 Kafka / Redis Streams / 数据库队列；LLM 场景更常用 asyncio |
| `get_nowait` + 空即退出 | 静态任务集下最简单的终止条件 | 不支持动态投递后续任务；生产用阻塞 `get` + 哨兵/关闭信号 |
| 不处理异常、不重试 | 聚焦调度对比 | 任务会静默丢失；需要重试、死信队列、幂等 worker |
| 最坏情况的预分配 | 放大 swarm 的优势，便于观察 | 夸大了差距；合理的预分配（轮询、LPT）同样能到 0.50s |
| 慢任务排在队首 | 让 swarm 达到理想时间 | 隐含了 LPT 顺序；顺序不利时 swarm 也会有尾部空等 |
| 只统计计数，不收集结果 | 输出简洁 | 讲义中的 "results pool" 未实现；生产需要结果存储与 trace ID |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可直接写 `list[Task]` 等 |
| `@dataclass` | `class Task:` | 自动生成 `__init__`/`__repr__`/`__eq__`；默认**不**生成 `<`，所以 `Task` 不能直接放进 `PriorityQueue` 比较 |
| 类型注解 | `-> tuple[float, dict[int, int]]` | 声明返回"浮点数 + 字典"的元组 |
| 字典推导式 | `{i: [] for i in range(n_workers)}` | 为每个 worker 建一个空列表 |
| 列表推导式 | `[threading.Thread(target=worker, args=(i,)) for i in range(n_workers)]` | 一次创建多个线程对象 |
| 单元素元组 | `args=(i,)` | 逗号不可省略，`(i)` 只是加了括号的整数 |
| 嵌套函数 / 闭包 | `def worker(wid)` 定义在函数内部 | 可读写外层函数的 `counts`、`q` 等变量（修改容器内容不需要 `nonlocal`） |
| `threading.Thread` | `.start()` / `.join()` | 启动线程 / 等待线程结束 |
| `threading.Lock` + `with` | `with lock: counts[wid] += 1` | 进入时加锁、离开时自动释放，即使中途异常也会释放 |
| `queue.Queue` | `q.put(t)`、`q.get_nowait()`、`q.task_done()` | 线程安全队列；`get_nowait` 空时抛 `queue.Empty` |
| `try / except` 控制流程 | `except queue.Empty: return` | 用异常表示"没有更多任务" |
| 生成器表达式 | `sum(t.duration for t in tasks)` | 不建中间列表直接求和 |
| 条件表达式 | `0.4 if is_slow else 0.1`、`... if swarm_time > 0 else float("inf")` | 一行内的 if/else |
| 取模 | `(i - 3) % n_workers` | 余数，用于循环分配（本例的"漏网之鱼"就出在这里） |
| f-string 格式符 | `{total_work:.2f}`、`{speedup_vs_seq:.2f}x` | 保留 2 位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，`python3 main.py`，总计约 4.2 秒）：

```text
Swarm architecture demo — variable-duration workload
--------------------------------------------------------
8 tasks, 4 slow (0.4s) + 4 fast (0.1s)
Total work-seconds: 2.00s
Ideal parallel time with 4 workers: 0.50s

Sequential (1 worker):      wall=2.00s, counts={0: 8}
Fixed assignment (4 workers): wall=1.70s, counts={0: 5, 1: 1, 2: 1, 3: 1}
  worker 0 got all 4 slow tasks; other workers idle after their fast ones.
Swarm (4 workers):            wall=0.50s, counts={0: 2, 1: 2, 2: 2, 3: 2}
  load balances automatically — slow workers finish first, fast pull next job.

Swarm speedup vs sequential: 4.00x
Swarm speedup vs fixed:      3.40x

Takeaway: swarm wins when duration varies and assignment is hard to predict.
Tradeoff: no central trace; debugging requires per-task IDs and durable logs.
```

逐项解读：

- **Sequential 2.00s**：等于总工作量，验证了 `sleep` 计时准确。
- **Fixed 1.70s**：worker 0 串行跑 4 慢 + 1 快 = 1.7s；其他 worker 0.1s 后就空闲了 1.6s。计数 `{0: 5, ...}` 中的 5 正是 `(7−3)%4 = 0` 的结果。
- **Swarm 0.50s**：4 个线程各拿 1 个慢任务，0.4s 后再各拿 1 个快任务；正好达到理想值，计数完全均匀 `{0: 2, 1: 2, 2: 2, 3: 2}`。讲义 Build It 说 "swarm distributes unevenly but optimally"，在这组数据上实际是**均匀**的；不均匀分布要在任务耗时更分散时才看得到（测验 Q9 的例子：`{0: 1, 1: 4, 2: 4, 3: 4}`）。
- **"slow workers finish first, fast pull next job"** 这句打印措辞有些混乱，实际含义是：先拿到慢任务的 worker 做完后，再去拉剩下的快任务。
- **加速比 4.00× / 3.40×**：讲义练习 1 的答案。4.00× 就是 worker 数，说明达到了线性加速；3.40× = 1.70 / 0.50。
- 线程启动和调度有毫秒级开销，多次运行数值可能在第三位小数上略有波动。

---

## 7. 动手改一改

1. **讲义练习 1**：记录三种策略的耗时，并把 `pre_assigned` 改为 `i % n_workers`（轮询），观察固定分配也能到 0.50s，思考 swarm 的真正优势是什么。
2. **顺序敏感性**：构造"12 个 0.1s + 1 个 1.0s"的任务，分别把长任务放在最前和最后，比较 swarm 的耗时（约 1.00s vs 1.30s），再实现"入队前按 `duration` 降序排序"（LPT）。
3. **讲义练习 2**：用 `queue.PriorityQueue`，入队元素写成 `(priority, seq, task)`，`seq` 来自 `itertools.count()`；再实现 aging（等待越久优先级越高），模拟持续有高优先级任务到达时低优先级任务是否饥饿。
4. **讲义练习 3**：实现热点检测——`max(counts.values()) >= 3 * min(counts.values())` 时打印警告。在"1 长 + 12 短"的负载上它会报警，思考这说明的是"耗时分布重尾"而不一定是故障。
5. **讲义练习 5**：把队列元素改成 `(task_type, payload)`，为每种类型建一个队列，worker 只订阅自己的类型（content-based routing）；测量当某一类型任务激增时的排队情况。
6. **进阶**：按测验 Q12 加上异常重试、死信列表、哨兵退出和 `q.join()`；再用 `asyncio.Queue` + `asyncio.sleep` 重写一遍，对比 1000 个并发任务时线程版与协程版的资源占用。

---

## 8. 常见坑

- **以为线程能加速一切**：只有 I/O 等待（`sleep`、网络）能在 CPython 线程中并行；CPU 密集任务需要多进程。
- **先 start 一个再 join 一个**：会把并行退化成串行，必须先全部 `start()` 再全部 `join()`。
- **`PriorityQueue` 里放不可比较对象**：优先级相同时会比较第二个元素，`Task` 没有 `<` 会抛 `TypeError`；加单调序号做平局裁决。
- **"队列空就退出"用在动态任务场景**：其他 worker 会在后续任务到来前退出；用阻塞 `get` + 哨兵。
- **worker 异常吞任务**：线程异常只打印栈、不传播到主线程，任务静默丢失；必须 `try/finally` + 重试 + 死信。
- **只调用 `task_done` 却从不 `join` 队列**（或反过来漏调 `task_done`）：前者无害但多余，后者会让 `q.join()` 永远阻塞。
- **把演示里的 3.40× 当成普遍结论**：它依赖刻意构造的最坏预分配和有利的队列顺序。
- **用 `time.time()` 做精细计时**：系统时间可能被调整，测量耗时应使用 `time.perf_counter()`。
