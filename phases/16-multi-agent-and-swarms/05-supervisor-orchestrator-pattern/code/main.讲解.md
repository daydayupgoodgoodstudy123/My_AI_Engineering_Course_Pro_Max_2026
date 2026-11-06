# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 05 节 监督者与编排者—工作者模式 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数，约 0.3 秒） ｜ **依赖**：仅标准库（`threading`、`time`、`dataclasses`），无需 LLM、无需网络

---

## 1. 这份代码在考察什么

讲义介绍的是 Anthropic Research 系统背后的 **supervisor / orchestrator-worker 模式**：一个 lead agent 负责规划、拆分子问题、分派给多个 worker 并行执行，最后汇总（synthesize）。这份代码用线程模拟这一过程：

1. **规划（plan）**：`Lead.plan` 把一个查询拆成 3 个子问题。
2. **并行分派（fan-out）**：每个子问题交给一个 `Worker`，在独立线程中运行；每个 worker 只拿到自己的子问题——对应讲义的 "fresh context per subagent"。
3. **汇合（join）与汇总（synthesize）**：lead 等待所有线程结束，只读取 worker 的摘要（不读原始材料），拼成最终答案。
4. **可观测性**：`Trace` 记录 plan、每个 worker 的 start/done、synthesize 的时间戳。
5. **墙钟收益**：3 个各 0.3 秒的 worker 并行运行，总耗时约 0.3 秒，而顺序执行需要约 0.9 秒——讲义的 `max(worker_times) + plan + synthesis` 而非 `sum(worker_times)`。

> 一句话：**用最少的代码展示"拆分—并行—汇总"的结构和它带来的墙钟加速，同时也暴露出一个玩具实现缺了哪些生产必需品（超时、冲突检测、按复杂度调节 worker 数）。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `WorkerResult` | dataclass | 子问题、摘要、消耗 token、耗时 | worker 交回的"窄 artifact" |
| `TraceEntry` / `Trace` | dataclass | 带锁的事件日志（worker_id、事件、时间、子问题） | 可观测性（Ship It 的 Observability） |
| `fake_web_fetch` | 函数 | `sleep(0.3)` 后返回一句假摘要 | 模拟工具调用延迟 |
| `Worker` | 类 | 记录 start → 调用 fetch → 写结果到共享列表的指定槽位 → 记录 done | Worker / subagent |
| `Lead.plan` | 方法 | 用模板把查询拆成 3 个子问题 | 规划 / 分解 |
| `Lead.synthesize` | 方法 | 把各 worker 的摘要按行拼接 | 汇总 |
| `Lead.run` | 方法 | plan → 启动线程 → join → synthesize → 统计 | supervisor 主流程 |
| `render_trace` | 函数 | 按相对时间打印 trace | 观察并行性 |
| `main` | 函数 | 运行一次并打印 trace、答案、统计 | 演示入口 |

数据流：`main` → `Lead.run(query)` → `plan` 得到 3 个子问题 → 为每个子问题创建 `Worker` 和 `Thread` 并 `start` → 各线程 `fake_web_fetch` 后写 `results[i]` → 主线程 `join` 全部 → `synthesize` → 返回 `(answer, stats)` → `render_trace` 打印。

---

## 3. 逐段精讲

### 3.1 数据类：结果与 trace

```python
@dataclass
class WorkerResult:
    sub_question: str
    summary: str
    tokens_spent: int
    wall_time: float

@dataclass
class Trace:
    entries: list[TraceEntry] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def log(self, worker_id: int, event: str, sub_question: str = "") -> None:
        with self._lock:
            self.entries.append(
                TraceEntry(worker_id=worker_id, event=event, t=time.time(), sub_question=sub_question)
            )
```

- `WorkerResult` 就是讲义说的 "Each arrow is a handoff with a narrow artifact"：worker 交回的只有摘要和少量元数据，lead 不接触原始材料。
- `Trace.log` 被多个线程同时调用，所以用锁保护 `append`。在 CPython 中 `list.append` 本身是原子的，但加锁是正确的习惯：一旦记录逻辑变复杂（先读后写、多个字段），没有锁就会出现竞态。
- `t=time.time()` 在锁内取时间，保证 `entries` 的顺序与时间戳顺序一致。
- ⚠️ `wall_time` 被计算并保存，但 `main` 从未打印它；`worker_id=-1` 被用来表示 lead，是一种"魔法值"写法。

### 3.2 Worker：在自己的线程里干活

```python
def fake_web_fetch(query: str) -> str:
    time.sleep(0.3)
    return f"Summary for '{query}': 3 key findings from 5 sources."

class Worker:
    def run(self, sub_question: str, results: list[WorkerResult | None], idx: int) -> None:
        start = time.time()
        self.trace.log(self.worker_id, "start", sub_question)
        summary = fake_web_fetch(sub_question)
        elapsed = time.time() - start
        results[idx] = WorkerResult(sub_question=sub_question, summary=summary,
                                    tokens_spent=800, wall_time=elapsed)
        self.trace.log(self.worker_id, "done", sub_question)
```

- **结果回传方式**：线程函数不能直接 `return` 给调用方，所以 lead 预先分配一个长度为 3 的列表，每个 worker 写自己的下标 `idx`。不同线程写不同下标，互不冲突，因此这里不需要锁。
- **为什么线程能并行**：`time.sleep` 会释放 GIL（全局解释器锁），3 个线程可以同时"等待"。真实场景里的网络请求、LLM API 调用也是 I/O 等待，同样适合用线程。若 worker 是 CPU 密集型的纯 Python 计算，GIL 会让线程几乎无法并行（见第 6 节实测）。
- **fresh context**：worker 只收到自己的 `sub_question`，看不到 lead 的规划过程，也看不到其它 worker 的结果——这就是讲义 "The workers never see each other's work until the lead synthesizes"。
- `tokens_spent=800` 是写死的常数，用来演示成本统计。

### 3.3 Lead.plan：模板式分解

```python
def plan(self, query: str) -> list[str]:
    return [
        f"{query} -- historical origins",
        f"{query} -- state of the art 2026",
        f"{query} -- open problems",
    ]
```

- 真实的 lead 用 LLM 分解；这里用固定模板，无论查询多简单或多复杂都拆成 3 份。
- ⚠️ 讲义的第一条工程经验是 **"Scale effort to query complexity"**（简单查询 1 个 agent、3–10 次工具调用；复杂查询 10+ 个 agent），这里完全没有体现。
- ⚠️ 子问题是"原查询 + 后缀"，worker 仍然拿到了整个原查询；讲义强调"Without explicit scope boundaries, workers drift beyond their assigned sub-question"，生产中应给每个子问题写明边界与输出格式。

### 3.4 Lead.run：fan-out / join / synthesize

```python
results: list[WorkerResult | None] = [None] * len(sub_questions)
threads: list[threading.Thread] = []
for i, sq in enumerate(sub_questions):
    w = Worker(worker_id=i, trace=self.trace)
    th = threading.Thread(target=w.run, args=(sq, results, i))
    threads.append(th)
    th.start()

for th in threads:
    th.join()

self.trace.log(worker_id=-1, event="synthesize")
synthesis = self.synthesize(query, [r for r in results if r is not None])
total_wall = time.time() - t0
total_tokens = sum((r.tokens_spent for r in results if r is not None)) + 1200
```

- **先全部 start，再逐个 join**：这是并行的关键。如果写成"start 一个就 join 一个"，就退化成顺序执行，耗时 0.9 秒。
- `[None] * len(sub_questions)` 预分配结果槽；`None` 表示"该 worker 没有交回结果"，`synthesize` 会过滤掉它们（`run` 里已经过滤一次，`synthesize` 内又过滤一次，重复但无害）。
- `th.join()` **没有超时**：任何一个 worker 卡住，lead 就永远等下去。讲义 Ship It 要求"Any worker that exceeds 2× median runtime gets killed"，练习 2 要求 0.5 秒超时。注意 Python 线程无法被强制杀死，只能 `join(timeout=...)` 后不再等待（线程会继续在后台运行），所以生产中常用进程、asyncio 的取消或任务队列实现真正的超时。
- **token 统计**：`3 × 800 + 1200 = 3600`，1200 代表 lead 自己的规划与汇总开销。讲义说多 agent 约是单 agent 的 15 倍 token，这里没有给出单 agent 基线来对比。
- `self.trace.log(worker_id=-1, event="plan", sub_question=str(len(sub_questions)))` 把"子问题数量"塞进了 `sub_question` 字段，所以 trace 中显示为 `plan | 3`——字段语义被借用了。

### 3.5 Lead.synthesize：只拼接，不处理冲突

```python
def synthesize(self, query: str, results: list[WorkerResult]) -> str:
    ok = [r for r in results if r is not None]
    parts = [f"- {r.sub_question}: {r.summary}" for r in ok]
    return f"Answer to '{query}':\n" + "\n".join(parts)
```

- 只读 worker 的摘要，符合 "The lead never sees the raw papers — only the worker summaries"。
- ⚠️ 没有冲突检测：讲义把"静默地选择一边"列为最糟糕的失败（"Silent picking of one side is the worst failure"），练习 3 要求在汇总时检测矛盾。这里所有摘要都是同一个模板，自然也不会冲突。
- 没有标注哪些子问题缺失：若某个 worker 失败（结果为 `None`），汇总里只是少了一行，用户无从得知。

### 3.6 render_trace 与 main

```python
def render_trace(trace: Trace, t0: float) -> None:
    for e in trace.entries:
        rel = round(e.t - t0, 3)
        sq = f" | {e.sub_question}" if e.sub_question else ""
        tag = "LEAD" if e.worker_id == -1 else f"W{e.worker_id}"
        print(f"  +{rel:>5}s  {tag:>4}  {e.event}{sq}")
```

- `{rel:>5}` 右对齐到宽度 5；因为 `rel` 是 `round` 后的浮点数，`0.0` 显示为 `  0.0`，`0.301` 显示为 `0.301`。
- `main` 最后两行 "Sequential baseline would be ~0.9s" 和 "Parallel actual is ~0.35s" 是**写死的字符串**，并不是实际测量值；实测并行约 0.301 秒。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 `threading` 而非 `asyncio` / 多进程 | 标准库、写法直观，`sleep` 释放 GIL | CPU 密集任务无法并行；无法强制取消线程；生产多用 asyncio 或任务队列 |
| 预分配结果列表、按下标写入 | 线程间无需加锁即可回传结果 | 结果与 worker 的对应关系靠下标，容易写错；可用 `concurrent.futures` 的 `Future` |
| 模板式 `plan` 固定拆 3 份 | 演示结构 | 不随复杂度调整；生产由 LLM 估计复杂度、决定 worker 数 |
| `join()` 无超时 | 代码最短 | 一个卡住的 worker 拖死整个请求；需要超时 + "缺失结果"标注 |
| `synthesize` 直接拼接 | 演示"只读摘要" | 无冲突检测、无引用；生产需要显式标注分歧与来源 |
| 固定 token 计数 | 演示成本统计 | 与真实用量无关；生产要按调用实测并设每 worker 的 token 上限 |
| 带锁的 Trace | 并发写日志的正确做法 | 只在内存中；生产应接入 OpenTelemetry 等追踪系统 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许 `WorkerResult \| None` 这样的新式注解在旧版本中使用 |
| `@dataclass` | `WorkerResult`、`TraceEntry`、`Trace` | 自动生成构造函数等 |
| 字段默认值 | `sub_question: str = ""` | 有默认值的字段必须放在无默认值字段之后 |
| `field(default_factory=...)` | `field(default_factory=list)` | 每个实例独立的可变默认值 |
| `X \| None` 联合类型 | `list[WorkerResult \| None]` | 元素可以是结果或 `None` |
| `tuple[str, dict]` 返回注解 | `def run(...) -> tuple[str, dict]` | 返回一个二元组 |
| `threading.Thread(target=..., args=...)` | `threading.Thread(target=w.run, args=(sq, results, i))` | 在新线程中调用 `w.run(sq, results, i)`；`args` 必须是元组 |
| `start()` / `join()` | `th.start()`、`th.join()` | 启动线程 / 等待线程结束 |
| `threading.Lock` + `with` | `with self._lock:` | 互斥锁，离开代码块自动释放 |
| `time.time()` / `time.sleep()` | `start = time.time()`、`time.sleep(0.3)` | 当前时间戳（秒）/ 休眠；测耗时更推荐 `time.perf_counter()` |
| 列表乘法 | `[None] * len(sub_questions)` | 创建定长列表（元素是不可变的 `None`，所以安全） |
| 生成器表达式 | `sum((r.tokens_spent for r in results if r is not None))` | 不建中间列表直接求和；外层多了一对括号，可省略 |
| `enumerate` | `for i, sq in enumerate(sub_questions)` | 同时拿下标和元素 |
| `round` | `round(total_wall, 3)` | 保留 3 位小数 |
| f-string 对齐 | `f"{rel:>5}s"`、`f"{tag:>4}"` | `>` 右对齐，数字为宽度 |
| `str.replace` | `answer.replace("\n", "\n  ")` | 给多行文本每行加缩进 |
| `dict.items()` | `for k, v in stats.items()` | 遍历键值对 |

---

## 6. 运行结果解读

实际运行（Python 3.13）：

```text
Supervisor / Orchestrator-Worker demo
------------------------------------------

Trace (+seconds relative to plan start):
  +  0.0s  LEAD  plan | 3
  +  0.0s    W0  start | What changed in multi-agent systems 2023 to 2026? -- historical origins
  +0.001s    W1  start | ... -- state of the art 2026
  +0.001s    W2  start | ... -- open problems
  +0.301s    W0  done | ... -- historical origins
  +0.301s    W2  done | ... -- open problems          ← 完成顺序不固定
  +0.301s    W1  done | ... -- state of the art 2026
  +0.301s  LEAD  synthesize

Final synthesis:
  Answer to 'What changed in multi-agent systems 2023 to 2026?':
  - ... -- historical origins: Summary for '... -- historical origins': 3 key findings from 5 sources.
  ...

Stats:
  wall_clock_seconds: 0.301
  total_tokens: 3600
  worker_count: 3

Sequential baseline would be ~0.9s (3 * 0.3s).
Parallel actual is ~0.35s. That's the supervisor win.   ← 写死的文字，实测是 0.301s
```

逐项解读：

- **三个 start 几乎同时（0.000–0.001 秒）、三个 done 几乎同时（0.301 秒）**：说明三个 worker 真正重叠执行。done 的顺序每次运行可能不同（本次是 W0、W2、W1），这是线程调度的非确定性。
- **wall_clock_seconds = 0.301**：≈ `max(0.3, 0.3, 0.3)` + 极小的线程开销；顺序执行 3 次 `fake_web_fetch` 实测 0.901 秒，加速约 3 倍。
- **total_tokens = 3600**：`3 × 800 + 1200`。
- **扩大 worker 数（讲义练习 1）**：我们把 `plan` 改为拆成 N 份，实测：

| worker 数 | 墙钟（秒） | total_tokens |
|----------|-----------|-------------|
| 3 | 0.301 | 3,600 |
| 5 | 0.302 | 5,200 |
| 10 | 0.303 | 9,200 |
| 100 | 0.313 | 81,200 |
| 1000 | 0.390 | 801,200 |

  在这个 demo 里，线程创建开销在 1000 个 worker 时才增加约 0.09 秒，远小于顺序执行省下的时间，所以"spawn 开销超过并行收益"的拐点在本 demo 中实际上不会出现；真正的限制在别处：token 成本线性增长（1000 个 worker 是 3 个的 222 倍），以及真实环境中 API 限流、并发连接数和 lead 汇总上下文的长度。
- **CPU 密集型对照**：把 worker 换成纯 Python 的 300 万次累加，3 个顺序执行 0.234 秒，3 个线程并行 0.303 秒——GIL 下线程不能加速 CPU 密集任务，反而略慢。supervisor 模式的墙钟收益依赖于 worker 主要在等待 I/O（LLM API、网页抓取）。

---

## 7. 动手改一改

1. **讲义练习 1**：给 `Lead` 加参数 `n_workers`，让 `plan` 生成 N 个子问题，复现第 6 节的表格；再把 `fake_web_fetch` 的延迟改为 `random.uniform(0.1, 0.5)`，观察墙钟变成 `max` 而不是平均值。
2. **讲义练习 2：worker 超时**：把 `th.join()` 改为 `th.join(timeout=0.5 - 已用时间)`，对超时的 worker 在结果中标记 `TIMEOUT`，并在 trace 中记录 `timeout` 事件；让其中一个 worker 睡 1 秒验证。思考：线程仍在后台运行，如何避免它之后写入 `results`？
3. **讲义练习 3：冲突检测**：让两个 worker 返回带数值的结论（如"2024 年发布"与"2025 年发布"），在 `synthesize` 中用正则抽取年份并比较，不一致时输出 "DISAGREEMENT: ..." 而不是二选一。
4. **按复杂度调节**：写一个 `estimate_complexity(query)`（例如按问句中 "and"/"compare"/年份区间的数量打分），简单问题只派 1 个 worker，复杂问题派 5 个，并在 stats 中输出单 agent 基线的 token 与多 agent token 的比值。
5. **改用 `concurrent.futures`**：用 `ThreadPoolExecutor` 与 `as_completed` 重写 fan-out/join，体会 `Future` 如何同时解决"结果回传"和"超时"两个问题。
6. **token 上限**：给每个 worker 一个 token 预算（讲义 Ship It："Hard limit (say 10× the expected synthesis input)"），超出就截断摘要并在 trace 中告警。

---

## 8. 常见坑

- **start 一个 join 一个**：会把并行写成顺序执行，耗时翻 3 倍。
- **以为线程能加速一切**：CPython 的 GIL 让 CPU 密集型线程无法并行；I/O 密集才有收益。
- **join 不设超时**：一个卡住的 worker 拖死整个请求。
- **线程无法被杀死**：`join(timeout)` 只是"不等了"，线程仍在运行，可能在汇总之后才写入结果，造成数据竞争。
- **共享可变对象写同一位置**：本例每个 worker 写不同下标所以安全；若多个 worker 往同一个 list 里 `append` 再按顺序读取，结果顺序是不确定的。
- **把写死的提示语当成测量值**：`"Parallel actual is ~0.35s"` 只是文字，要看 `wall_clock_seconds`。
- **汇总时静默丢失失败的 worker**：`None` 被过滤掉后用户无从得知答案不完整，应显式列出缺失的子问题。
- **只看墙钟不看成本**：并行省时间，但 token 随 worker 数线性增加；讲义提醒多 agent 约 15 倍 token，只有任务价值足够高才值得。
