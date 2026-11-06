# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 56 节 迭代调度器 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下）；测试：`python3 -m unittest discover -s tests` 或 `python3 -m pytest -q tests` ｜ **依赖**：标准库（`asyncio`、`dataclasses`、`math`、`json`、`time`）+ 第三方 `numpy`（只用于生成带噪声的奖励）

---

## 1. 这份代码在考察什么

这份代码是自动科研流水线（第 50–57 节）中的"大脑"：它不生成假设、也不真正做实验，只负责**决定下一个实验跑什么、何时停止、何时通知下游**。它考察：

1. **多臂老虎机（multi-armed bandit）思想**：把每个研究方向（branch）当作一条臂，用 UCB1 在"利用当前最好方向"和"探索尝试较少的方向"之间折中。
2. **asyncio 并发**：用 `create_task` 把实验放进 N 个并行槽位，用 `asyncio.wait(FIRST_COMPLETED)` 做 fan-in，任一槽位空出就补派。
3. **调度决策的分层**：打分（picker）、剪枝（prune gate）、fan-out（paper.trigger 与 expander）、预算（max_experiments / max_seconds）各自独立，便于测试。
4. **可观测性**：每个决定写一条 `TraceEvent`，最终汇总成 `SchedulerReport`，供第 57 节的端到端演示读取。

> 一句话：**用不到 300 行代码实现"带 UCB 打分、并行槽位、剪枝、fan-out 和双预算的异步实验调度器"**。同时要看清它在并行反馈、失败处理和截止时间上的简化——这些正是面试追问的高发区。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Hypothesis` | dataclass | 一个待做的实验：`id`、`branch`、`payload` | 假设队列的元素 |
| `Result` | dataclass | 一次实验的结果：`hypothesis_id`、`branch`、`reward` | result bus 上的消息 |
| `BranchStats` | dataclass | 每个 branch 的 `runs`、`reward_sum`、`pruned`、`paper_triggered`；`mean` 是 property | UCB 统计 |
| `TraceEvent` / `SchedulerReport` | dataclass | 事件日志与最终报告，均带 `to_dict()` | Trace 与报告 |
| `Runner` / `Expander` | 类型别名 | `Hypothesis → Awaitable[Result]`、`Result → list[Hypothesis]` | 可插拔的实验执行器与扩展器 |
| `ucb_score` | 函数 | UCB1 打分，`runs == 0` 返回 `+inf` | UCB 评分 |
| `IterationScheduler._pick_next` | 方法 | 遍历队列，跳过已剪枝 branch，返回 UCB 最高的下标 | picker |
| `IterationScheduler.run` | async 方法 | 派发 → 等待 → 更新统计 → 触发/剪枝/扩展 → 检查预算 → 补派 → drain | 主循环 |
| `make_deterministic_runner` | 工厂函数 | 返回一个 `async def run(hyp)`：奖励 = 基准 + N(0, σ)，裁剪到 [0,1]，`sleep` 若干毫秒 | 模拟实验 |
| `deterministic_expander` | 函数 | 为一个结果生成 2 个同 branch 的后续假设，id 加 `-f1`/`-f2` 后缀 | follow-up fan-out |
| `demo_async` / `demo` | 函数 | 4 个 branch、3 个槽位、20 次实验的演示 | 演示入口 |

数据流：`demo()` → `asyncio.run(demo_async())` → 构造种子假设与 runner → `IterationScheduler.run(seed)`（循环：`_pick_next` → `create_task(runner)` → `asyncio.wait` → 更新 `BranchStats` → paper.trigger / prune / expand → 预算检查）→ `SchedulerReport.to_dict()` → `json.dumps` 打印。

---

## 3. 逐段精讲

### 3.1 数据结构：`Hypothesis`、`Result`、`BranchStats`

```python
@dataclass
class Hypothesis:
    id: str
    branch: str
    payload: dict = field(default_factory=dict)
```

- `branch` 是 UCB 统计的键；同一 branch 下可以有多个假设（讲义："the branch is the research direction; the hypothesis is one trial within it"）。
- `payload: dict = field(default_factory=dict)`：可变默认值必须用 `default_factory`，否则所有实例会共享同一个字典（dataclass 会直接报错阻止你写 `= {}`）。
- 每个类都有 `to_dict()`，返回 `dict(self.payload)` 这样的**浅拷贝**，避免外部修改报告时反过来改动内部状态。

```python
@dataclass
class BranchStats:
    branch: str
    runs: int = 0
    reward_sum: float = 0.0
    pruned: bool = False
    paper_triggered: bool = False

    @property
    def mean(self) -> float:
        return (self.reward_sum / self.runs) if self.runs else 0.0
```

- 只存"次数 + 总和"，均值按需计算——这是增量统计的标准做法，更新是 O(1)。
- `runs == 0` 时 `mean` 返回 0.0 以避免除零；但 UCB 不会用到这个值，因为 `ucb_score` 先判断 `runs == 0`。

### 3.2 UCB1 打分

```python
def ucb_score(branch_stats: BranchStats, total_runs: int, c: float) -> float:
    if branch_stats.runs == 0:
        return float("inf")
    if total_runs == 0:
        return branch_stats.mean
    return branch_stats.mean + c * math.sqrt(math.log(max(total_runs, 1)) / branch_stats.runs)
```

- 对应讲义公式 `mean_reward + c * sqrt(ln(total_runs) / runs)`。
- 第一项是"利用"，第二项是"探索奖励"：`runs` 越小越大；`total_runs` 增长时以 `ln` 的速度缓慢增大，保证冷门 branch 迟早会被重访。
- 数值示例（测验 Q1）：A `runs=4, mean=0.8`、B `runs=1, mean=0.5`、总数 5、`c=√2` → A ≈ 1.697，B ≈ 2.294，选 B。
- `total_runs == 0` 的分支实际上不可达（`runs > 0` 意味着 `total_runs > 0`），`max(total_runs, 1)` 也是防御性写法。

### 3.3 构造函数：参数与校验

```python
    def __init__(self, runner, slots=3, max_experiments=50, max_seconds=30.0,
                 exploration_c=math.sqrt(2.0), paper_threshold=0.7,
                 prune_floor=0.2, prune_after_runs=3, expander=None) -> None:
        if slots < 1:
            raise ValueError("slots must be >= 1")
        if max_experiments < 1:
            raise ValueError("max_experiments must be >= 1")
```

- 所有策略参数都可配置，测试正是靠把 `paper_threshold` 设成 0.99 / 2.0、`prune_floor` 设成 -1.0 来**关掉**不想测的行为——这是"小而正交的开关"带来的可测试性。
- 只校验了 `slots` 与 `max_experiments`；`max_seconds <= 0`、`prune_after_runs < 1` 等没有校验。

### 3.4 选择器 `_pick_next`

```python
    def _pick_next(self, queue, stats) -> int | None:
        best_idx: int | None = None
        best_score = -float("inf")
        total_runs = sum(s.runs for s in stats.values())
        for idx, hyp in enumerate(queue):
            bs = stats.get(hyp.branch)
            if bs is not None and bs.pruned:
                continue
            score = ucb_score(bs or BranchStats(branch=hyp.branch),
                              total_runs, self.exploration_c)
            if score > best_score:
                best_score = score
                best_idx = idx
        return best_idx
```

- 打分是**按假设所属 branch** 进行的：同一 branch 的假设分数相同。
- `score > best_score` 是严格大于，平局时保留队列中**靠前**的那个——这就是讲义说的"breaks ties on iteration order, not random choice"，也是 demo 可复现的原因之一。
- `bs or BranchStats(...)`：`stats` 里还没有这个 branch（例如 expander 引入的新 branch）时临时造一个 `runs=0` 的统计，得到 `+inf`。
- 复杂度 O(队列长度)，每次派发都扫一遍；队列很长时可以改成按 branch 分桶的优先队列。
- ⚠️ **并行下的缺陷**：`stats` 只在任务**完成**后更新，在途任务不计入。种子 `[A1, A2, B1]`、2 个槽位时，实际派发顺序是 `A1, A2, B1`——A 仍是 `runs = 0 → +inf`，与 B 平局，按顺序选了 A2（测验 Q8 已运行验证；修复见测验 Q10 的 virtual loss）。

### 3.5 主循环 `run()`：初始化与三个闭包

```python
    async def run(self, seed: list[Hypothesis]) -> SchedulerReport:
        queue: list[Hypothesis] = list(seed)
        stats = {h.branch: BranchStats(branch=h.branch) for h in seed}
        in_flight: dict[asyncio.Task[Result], Hypothesis] = {}
        ...
        def deadline_hit() -> bool:
            return (time.monotonic() - t0) >= self.max_seconds

        def budget_hit() -> bool:
            return experiments_run >= self.max_experiments

        def dispatch_until_full() -> None:
            nonlocal experiments_run
            while queue and len(in_flight) < self.slots and not budget_hit() and not deadline_hit():
                idx = self._pick_next(queue, stats)
                if idx is None:
                    return
                hyp = queue.pop(idx)
                ...
                task = asyncio.create_task(self.runner(hyp))
                in_flight[task] = hyp
                experiments_run += 1
```

- `list(seed)` 复制一份，避免修改调用方传入的列表。
- `in_flight` 用 **Task → Hypothesis** 的字典：完成时能通过 `in_flight.pop(task)` 找回是哪个假设。
- 三个内部函数是**闭包**：直接读外层的 `queue`、`stats`、`experiments_run`；其中 `dispatch_until_full` 需要给 `experiments_run` 赋值，所以要声明 `nonlocal`（只读的闭包不需要）。
- 派发条件：队列非空、有空槽位、预算未用完、未超时。
- `experiments_run += 1` 发生在**派发时**而不是完成时：预算计的是"派出去的工作量"，失败的实验也算（测验 Q3）。
- `asyncio.create_task` 立即把协程排进事件循环，但在当前协程 `await` 之前不会真正开始执行。
- `idx is None` 只在队列里**全是已剪枝 branch 的假设**时出现，此时直接返回；若此时也没有在途任务，主循环结束，`stop_reason` 仍是 `"queue_empty"`，尽管队列并不空（边界情况）。

### 3.6 主循环：fan-in 与统计更新

```python
        dispatch_until_full()

        while in_flight:
            done, _pending = await asyncio.wait(
                in_flight.keys(), return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                hyp = in_flight.pop(task)
                try:
                    result = task.result()
                except Exception as exc:
                    trace.append(TraceEvent(kind="error", ...))
                    continue
                bs = stats.setdefault(result.branch, BranchStats(branch=result.branch))
                bs.runs += 1
                bs.reward_sum += result.reward
```

- `asyncio.wait(..., FIRST_COMPLETED)` 至少有一个任务完成就返回，`done` 是一个**集合**，可能同时包含多个任务（demo trace 中常见连续 3 条 `result`）。
- `task.result()` 会把任务内部抛出的异常重新抛出，所以用 `try/except` 包住。
- `stats.setdefault(key, default)`：键不存在就插入默认值并返回它——一行完成"取或建"。
- ⚠️ **失败不计入统计**：`except` 分支直接 `continue`，`bs.runs` 不变。一个总是失败的 branch 永远 `runs = 0`，UCB 恒为 `+inf`，反而被最优先调度，也永远达不到剪枝门槛（测验 Q9 已运行验证：4 个 bad 假设全部被派发，`runs = 0, pruned = False`）。
- ⚠️ `done` 是集合，迭代顺序不保证等于完成顺序；同批结果的处理顺序会影响 expander 追加到队列的顺序。本节 demo 仍然可复现，是因为奖励在 runner **一被调用**（`sleep` 之前）就从共享的 `rng` 里抽好了，而派发顺序由队列顺序决定。

### 3.7 三个决策：paper.trigger、prune、expand

```python
                if (not bs.paper_triggered) and bs.mean >= self.paper_threshold and bs.runs >= 1:
                    bs.paper_triggered = True
                    triggers.append(result.branch)
                    trace.append(TraceEvent(kind="paper.trigger", ...))

                if (
                    (not bs.pruned)
                    and bs.runs >= self.prune_after_runs
                    and bs.mean < self.prune_floor
                ):
                    bs.pruned = True
                    queue[:] = [h for h in queue if h.branch != bs.branch]
                    trace.append(TraceEvent(kind="prune", ...))

                if self.expander is not None and result.reward >= self.paper_threshold:
                    followups = self.expander(result)
                    if followups:
                        queue.extend(followups)
                        trace.append(TraceEvent(kind="expand", ...))
```

| 决策 | 判据 | 次数 | 作用 |
|------|------|------|------|
| paper.trigger | branch **均值** `>= paper_threshold` | 每个 branch 最多 1 次（`paper_triggered` 标志） | 通知第 54 节论文写作器 |
| prune | `runs >= prune_after_runs` 且均值 `< prune_floor` | 每个 branch 最多 1 次 | 从队列删除该 branch 的剩余假设 |
| expand | **单次结果**的 `reward >= paper_threshold` | 每个满足条件的结果都触发 | 往队列追加后续假设 |

- `queue[:] = [...]` 是**原地切片赋值**：替换列表内容但保持同一个列表对象。这里写 `queue = [...]` 其实也能工作（闭包 `dispatch_until_full` 通过 cell 引用变量名，会看到新对象），但原地修改更明确地表达"修改那个共享的队列"，当别处也持有这个列表的引用时也不会出现"两份队列"的问题。
- `bs.runs >= 1` 在这里冗余（刚加过 1）。
- ⚠️ 剪枝之后，若该 branch 的某次结果恰好 `>= paper_threshold`，expander 仍会为它追加假设；这些假设会被 `_pick_next` 跳过但永远留在队列里。
- ⚠️ expander 每次加 2 个、只消耗 1 个，高产 branch 会让队列指数式膨胀：demo 结束时队列还剩 `4 + 17×2 − 20 = 18` 个假设。讲义说剪枝"keeps the queue bounded"，但对扩展没有限制。

### 3.8 预算检查与 drain

```python
            if budget_hit():
                stop_reason = "max_experiments"
                break
            if deadline_hit():
                stop_reason = "deadline"
                break

            dispatch_until_full()

        for task in list(in_flight.keys()):
            try:
                result = await task
            except Exception:
                in_flight.pop(task, None)
                continue
            bs = stats.setdefault(result.branch, BranchStats(branch=result.branch))
            bs.runs += 1
            bs.reward_sum += result.reward
            ...
            trace.append(TraceEvent(kind="result.drain", ...))
```

- 预算检查放在"处理完一批完成任务之后、补派之前"。
- ⚠️ **`max_experiments` 的边界**：派发第 N 个实验后计数已等于上限，下一次有任务完成时就会 `break` 并标记 `max_experiments`——即使队列里本来也没有更多工作。实测：3 个假设、预算 3 → `stop_reason = "max_experiments"`；预算 4 → `"queue_empty"`。
- ⚠️ **`max_seconds` 是软上限**：`asyncio.wait` 没有 `timeout`，截止时间只在任务完成后检查；之后 drain 阶段 `await task` 会把在途任务**等完**。实测：`max_seconds = 0.1`、每个实验 0.5s → `stop_reason = "deadline"`、`wall_seconds ≈ 0.501`（测验 Q7、Q11）。
- ⚠️ drain 阶段与主循环不一致：只做统计更新和 paper.trigger，**不做剪枝、不做扩展**，异常时也不写 `error` 事件；事件名是 `result.drain` 而不是 `result`。
- `for task in list(in_flight.keys())`：先复制成列表再遍历，因为循环体内会 `pop`，直接遍历字典视图会触发 "dictionary changed size during iteration"。
- `if not queue and not in_flight and stop_reason == "queue_empty": stop_reason = "queue_empty"` 是一句无效赋值，可以删除。

### 3.9 报告

```python
        return SchedulerReport(
            stop_reason=stop_reason,
            experiments_run=experiments_run,
            wall_seconds=wall,
            branches=sorted(stats.values(), key=lambda b: b.branch),
            paper_triggers=triggers,
            trace=trace,
        )
```

- `sorted(..., key=lambda b: b.branch)` 按 branch 名排序，保证报告顺序稳定。
- ⚠️ 讲义说每个决定"(pick, dispatch, result, prune, fan-out) emits one event"，学习目标还提到"per-iteration trace with branch scores"——但代码**没有 `pick` 事件**，`dispatch` 事件里也**不含 UCB 分数**，只有 `slot_count`。想做"为什么选它"的可解释性，需要把 `best_score` 一起写进 trace。

### 3.10 模拟 runner 与 expander

```python
def make_deterministic_runner(base_rewards, noise=0.05, delay_ms=5.0, seed=0) -> Runner:
    rng = np.random.default_rng(seed)

    async def run(hyp: Hypothesis) -> Result:
        base = base_rewards.get(hyp.branch, 0.5)
        bump = float(rng.normal(0.0, noise))
        reward = max(0.0, min(1.0, base + bump))
        await asyncio.sleep(delay_ms / 1000.0)
        return Result(...)

    return run
```

- **工厂函数 + 闭包**：`rng` 被内部的 `run` 捕获，所有调用共享同一个随机数生成器，奖励序列由"调用顺序"决定。
- `max(0.0, min(1.0, x))` 把奖励裁剪到 [0,1]——UCB1 的理论分析假设奖励有界。
- `await asyncio.sleep(...)` 模拟 I/O 等待，正是它让出控制权，多个槽位才能"并行"。若换成 CPU 密集计算而不 `await`，整个事件循环会被阻塞。
- `deterministic_expander` 用列表推导式生成 `f"{id}-f1"`、`f"{id}-f2"`，后续假设的 id 越来越长（如 `h-a-1-f1-f2-f1-f2`），可以直接看出"家谱"。

### 3.11 demo

```python
    runner = make_deterministic_runner(
        base_rewards={"branch-a": 0.85, "branch-b": 0.55, "branch-c": 0.15, "branch-d": 0.40},
        seed=7, delay_ms=2.0,
    )
    sched = IterationScheduler(runner=runner, slots=3, max_experiments=20,
        paper_threshold=0.7, prune_floor=0.25, prune_after_runs=3,
        expander=deterministic_expander)
```

- 4 个 branch 各 1 个种子假设；只有 branch-a（基准 0.85）能让单次奖励 ≥ 0.7 触发扩展。
- ⚠️ 这个设置让 demo **无法展示 UCB 选择与剪枝**：b/c/d 跑完唯一的假设后再没有机会，队列里只剩 branch-a 的后续假设（测验 Q2、Q12）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| UCB1 + `runs==0 → inf` | 简单、确定性、可测试；保证每个 branch 至少试一次 | 假设奖励平稳、反馈即时；生产中考虑折扣 UCB、Thompson Sampling、按成本归一化 |
| picker 与 prune 分离 | 排序和淘汰各自可测，参数可独立关闭 | 两套阈值需要一起调；剪枝只看均值，不看置信区间 |
| asyncio 单线程并发 | 无需线程锁，`stats` 修改天然串行 | CPU 密集实验会阻塞事件循环；真实实验应交给进程池或作业系统 |
| 派发时计入预算 | 预算衡量"已承诺的工作量"，防止失败重试无限消耗 | 失败实验不进统计（见下行），两处口径不一致 |
| 失败只写 trace、不计统计 | 实现简单 | 失败 branch 永远 `+inf`、永不剪枝；应把失败计为 0 奖励或单独计数 |
| 软截止时间 + drain | 已经花了成本的实验不浪费 | 单个慢实验可以无限拖长；生产应 `wait(timeout=...)` + 取消 + 单实验超时 |
| 内存中的队列与统计 | 演示足够 | 重启即丢失探索进度；讲义 Going further 第一条就是持久化 checkpoint |
| 不限制 expander | 演示"高产 branch 自我繁殖" | 队列无限增长、其他 branch 被淹没；应设每 branch 最大深度/配额 |
| `done` 集合直接迭代 | 代码简洁 | 同批结果的处理顺序不确定；需要严格复现时应按派发序号排序 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，可以在 3.8/3.9 上写 `int \| None`、`list[str]` 等新式注解 |
| `@dataclass` | `class Hypothesis` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `field(default_factory=dict)` | `payload: dict = field(default_factory=dict)` | 可变默认值的正确写法，每个实例一个新字典 |
| `@property` | `BranchStats.mean` | 像属性一样访问的计算值：`bs.mean` 而非 `bs.mean()` |
| 条件表达式 | `(self.reward_sum / self.runs) if self.runs else 0.0` | 三元表达式，防止除零 |
| 类型别名 | `Runner = Callable[[Hypothesis], Awaitable[Result]]` | 给复杂函数类型起名字，提升可读性 |
| `X \| None` | `expander: Expander \| None = None` | 可选类型（等价于 `Optional[X]`） |
| `float("inf")` | `return float("inf")` | 正无穷，任何有限数都比它小 |
| `async def` / `await` | `async def run(...)`、`await asyncio.wait(...)` | 定义协程；`await` 处让出控制权给事件循环 |
| `asyncio.create_task` | `task = asyncio.create_task(self.runner(hyp))` | 把协程包装成 Task 并调度执行 |
| `asyncio.wait` | `return_when=asyncio.FIRST_COMPLETED` | 等待一组任务，返回 `(done, pending)` 两个集合 |
| `asyncio.run` | `asyncio.run(demo_async())` | 创建事件循环、运行协程、关闭循环；程序入口用 |
| 闭包与 `nonlocal` | `dispatch_until_full` 中 `nonlocal experiments_run` | 内部函数修改外层函数的变量时需要声明 |
| 工厂函数返回闭包 | `make_deterministic_runner` 返回内部的 `run` | 内部函数"记住"了 `rng`、`base_rewards` 等外层变量 |
| `try/except Exception as exc` + `repr` | `"error": repr(exc)` | 捕获异常并把其表示写进日志 |
| `dict.setdefault` | `stats.setdefault(result.branch, BranchStats(...))` | 取值，不存在则插入默认值 |
| 原地切片赋值 | `queue[:] = [h for h in queue if ...]` | 保持列表对象身份，替换全部元素 |
| 列表推导式 / 字典推导式 | `{h.branch: BranchStats(branch=h.branch) for h in seed}` | 一行构造容器 |
| 生成器表达式 + `sum` | `sum(s.runs for s in stats.values())` | 不建中间列表的求和 |
| `sorted(key=lambda ...)` | `sorted(stats.values(), key=lambda b: b.branch)` | 按指定键排序 |
| `enumerate` | `for idx, hyp in enumerate(queue)` | 同时拿下标和元素 |
| `list(d.keys())` 再遍历 | `for task in list(in_flight.keys())` | 遍历时要修改字典，先拷贝键 |
| `time.monotonic()` | `t0 = time.monotonic()` | 单调时钟，适合测耗时，不受系统时间调整影响 |
| `np.random.default_rng(seed)` | `rng.normal(0.0, noise)` | NumPy 新式随机数生成器，固定种子可复现 |
| `json.dumps(indent=2)` | `print(json.dumps({...}, indent=2))` | 格式化输出 JSON |
| `if __name__ == "__main__"` | 文件末尾 | 直接运行时执行 demo，被测试导入时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3 + NumPy，`python3 main.py`，耗时约 0.36 秒）：

```text
{
  "stop_reason": "max_experiments",
  "experiments_run": 20,
  "wall_seconds": 0.0161,
  "paper_triggers": ["branch-a"],
  "branches": [
    {"branch": "branch-a", "runs": 17, "reward_sum": 14.1769, "mean": 0.8339, "pruned": false, "paper_triggered": true},
    {"branch": "branch-b", "runs": 1,  "reward_sum": 0.5649, "mean": 0.5649, "pruned": false, "paper_triggered": false},
    {"branch": "branch-c", "runs": 1,  "reward_sum": 0.1363, "mean": 0.1363, "pruned": false, "paper_triggered": false},
    {"branch": "branch-d", "runs": 1,  "reward_sum": 0.3555, "mean": 0.3555, "pruned": false, "paper_triggered": false}
  ]
}
```

（数字已截取到 4 位小数。）我们额外打印了 trace，事件计数为 `dispatch 20、result 20、expand 17、paper.trigger 1`，没有 `prune`、没有 `result.drain`。trace 开头：

```text
dispatch h-a-1 (slot_count 1) / dispatch h-b-1 (2) / dispatch h-c-1 (3)
result h-b-1 0.565 / result h-c-1 0.136 / result h-a-1 0.850
paper.trigger branch-a (mean 0.850) / expand branch-a [h-a-1-f1, h-a-1-f2]
dispatch h-d-1 (1) / dispatch h-a-1-f1 (2) / dispatch h-a-1-f2 (3)
```

逐项解读：

- **开局 3 个槽位全部用上**，派发 a、b、c；d 排在第 4 位，等第一批结果回来后才派发。第二批先派 `h-d-1`，因为 branch-d 还是 `runs = 0 → +inf`——这是 UCB 唯一一次真正起作用。
- **3 个结果在同一次 `asyncio.wait` 中返回**（delay 都是 2ms），处理顺序是 b、c、a（`done` 集合的迭代顺序）。
- **branch-a 跑了 17 次**：只有它能触发 expander，之后队列里全是它的后续假设；它的均值 0.834 接近基准 0.85（噪声 σ = 0.05，裁剪到 [0,1]）。
- **branch-c 没被剪枝**：均值 0.136 < 0.25，但只有 1 次运行，达不到 `prune_after_runs = 3`。
- **paper_triggers 只有 branch-a**：第一个结果 0.850 就让均值 ≥ 0.7，之后不再重复触发；而 expand 触发了 17 次（每个 a 的结果都 ≥ 0.7）。
- **stop_reason 是 max_experiments**：派发满 20 次后的下一次完成触发 `break`；此时在途任务恰好都已完成，所以没有 `result.drain` 事件。
- **wall_seconds 约 0.016**：20 个 2ms 实验、3 个槽位，理论下限约 `ceil(20/3) × 2ms ≈ 14ms`，与实测接近，说明槽位基本保持满载。

---

## 7. 动手改一改

1. **让 demo 展示剪枝**：每个 branch 放 5 个种子假设，重新运行，观察 branch-c 在第 3 次结果后出现 `prune` 事件，branch-b/d 的 runs 如何随 UCB 分配。
2. **调节探索系数**：把 `exploration_c` 分别设为 0、0.5、√2、3，统计各 branch 的 `runs` 分布。`c = 0` 退化为纯贪心（测验 Q1 中 A 0.8 vs B 0.5 直接选 A）。
3. **trace 可解释性**：在 `dispatch` 事件里加入 `ucb_score` 和当时的 `total_runs`，再写一个小函数把 trace 打印成时间线。
4. **virtual loss**：按测验 Q10 修改 `_pick_next`，验证种子 `[A1, A2, B1]` 在 2 个槽位下先派发 `A1, B1`。
5. **硬截止时间**：按测验 Q11 改造主循环（`asyncio.wait(timeout=...)` + `task.cancel()`），让 `test_deadline_caps_wall_clock` 在 runner 每次睡 1 秒时依然通过。
6. **持久化与恢复**（讲义 Going further）：每处理一个结果就把 `stats` 与 `queue` 写入 JSON；新增 `IterationScheduler.resume(path)`，验证中途"崩溃"后重启能继续而不重复已完成的实验。

---

## 8. 常见坑

- **把 `max_seconds` 当成硬上限**：它只阻止派发新实验，不会中断正在跑的实验（实测 0.1s 上限跑了 0.5s）。
- **失败被当成没发生**：失败 branch 永远 `runs = 0`，UCB 为 `+inf`，会被优先调度、永不剪枝。
- **并行下"先探索未试过的 branch"失效**：在途任务不计入统计，同一 branch 会被同时派发多次。
- **paper.trigger 与 expander 的判据混淆**：前者看均值、只一次；后者看单次奖励、每次都触发。
- **浮点边界**：剪枝用严格小于 `mean < prune_floor`。`(0.0 + 0.3 + 0.3) / 3` 在浮点下等于 `0.19999999999999998`，会被剪枝，而 `[0.2, 0.2, 0.2]` 的均值是 0.2，不会被剪枝。阈值比较最好留一点余量或用 `math.isclose`。
- **在 `async def` 里做 CPU 密集计算**：没有 `await` 就不让出控制权，所有槽位一起卡住。
- **遍历字典时修改它**：drain 阶段先 `list(in_flight.keys())` 再遍历，就是为了避免 `RuntimeError: dictionary changed size during iteration`。
- **以为 `done` 有序**：`asyncio.wait` 返回集合，需要确定顺序时要自己排序。

---

## 9. 测试在验证什么

测试文件：`code/tests/test_scheduler.py`（12 个测试）。它在文件开头把 `code/` 加进 `sys.path` 再 `from main import ...`；每个异步测试都用 `asyncio.run` 包一层（`aio_run` 辅助函数），因为 `unittest.TestCase` 的普通方法是同步的。

| 测试类 / 测试 | 验证的性质 | 关键设置 |
|--------------|-----------|---------|
| `TestUCB.test_zero_runs_branch_scores_infinity` | 未试过的 branch 得 `+inf` | `runs=0` |
| `TestUCB.test_high_mean_dominates_low_mean_with_equal_runs` | 次数相同时均值高者分数高 | 5 次，均值 0.9 vs 0.2 → 1.860 vs 1.160 |
| `TestUCB.test_exploration_bonus_helps_less_run_branch` | 探索项能让少试的 branch 胜出 | 100 次均值 0.5（0.804）vs 2 次均值 0.5（2.651） |
| `TestScheduling.test_untried_branches_are_picked_before_repeating` | 前 3 次派发覆盖 A、B、C | `slots=1`，种子按 A,B,C,A2,B2,C2 排列；`prune_floor=-1` 关掉剪枝 |
| `TestScheduling.test_parallel_slots_advance_wall_clock_less_than_serial` | 3 槽位耗时 < 1 槽位的 70% | 6 个 50ms 实验：串行约 0.3s，并行约 0.1s |
| `TestFanout.test_paper_trigger_fires_when_threshold_crossed` | 均值 ≥ 阈值时触发 | 奖励 0.9，阈值 0.7 |
| `TestFanout.test_paper_trigger_only_fires_once_per_branch` | 每个 branch 只触发一次 | 4 个 b1 结果，`paper_triggers == ["b1"]` |
| `TestFanout.test_expander_adds_followups` | expander 生成的后续假设被执行 | 1 个种子，最终 `b1.runs > 1` |
| `TestPruning.test_low_yield_branch_is_pruned_after_threshold_runs` | 低产 branch 被剪枝 | good 0.9 / bad 0.05，各 5 个假设，2 槽位 |
| `TestBudgets.test_max_experiments_caps_total_runs` | 实验数恰好等于上限，`stop_reason = max_experiments` | 50 个种子、上限 10、4 槽位 |
| `TestBudgets.test_deadline_caps_wall_clock` | 超时退出，`stop_reason = deadline`，总耗时 < 1s | 100 个 50ms 实验、`max_seconds=0.12` |
| `TestRunner.test_deterministic_runner_rewards_in_unit_interval` | 奖励被裁剪到 [0,1] | 基准 0.8、噪声 0.1 |

运行方式（在 `code/` 目录下）：

```bash
python3 -m unittest discover -s tests -v
# 或
python3 -m pytest -q tests
```

实际运行结果：`Ran 12 tests ... OK`（pytest：`12 passed in 0.87s`）。

值得注意的覆盖空白：

- `test_untried_branches_are_picked_before_repeating` 用的是 `slots=1`——恰好避开了并行下的 virtual loss 问题；改成 `slots=3` 并把种子排成 `A, A2, B, ...` 就会失败。
- `test_deadline_caps_wall_clock` 能通过，是因为单个实验只有 50ms；它验证的是"不再派发"，而不是"硬中断"。
- 没有测试覆盖 runner 抛异常的路径、drain 阶段、剪枝后 expander 的行为，以及 `max_experiments` 恰好等于工作总量时的 `stop_reason`。
