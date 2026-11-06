# 测验 · 迭代调度器（Iteration Scheduler）

> **阶段 19 · 综合项目 · 第 56 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Worklist vs scheduler | 平铺的工作列表按提交顺序执行；调度器读取已完成实验的结果（fan-in），据此**重排**后续假设的优先级 |
| 2 | Hypothesis 与 branch | `branch` 是研究方向、也是 UCB 统计的键；一个 branch 下可以有多个 `Hypothesis`（一次次试验）。统计存在 `BranchStats(runs, reward_sum)` 里 |
| 3 | UCB1 打分 | `mean + c·sqrt(ln(total_runs) / runs)`；`runs == 0` 直接给 `+inf`，保证每个 branch 至少被试一次；默认 `c = √2` |
| 4 | explore / exploit | 贪心只追当前领先者、从不探索；均匀轮询从不利用；UCB 用"均值 + 置信区间宽度"在两者之间折中，`c` 越大越偏探索 |
| 5 | 剪枝门与选择器分离 | 选择器（picker）只负责排序；剪枝在 `runs >= prune_after_runs`（默认 3）且 `mean < prune_floor`（默认 0.2）时把整个 branch 标记为 pruned，并从队列删掉它的剩余假设 |
| 6 | asyncio 并行槽位 | 每个派发的假设 `asyncio.create_task(runner(hyp))`；主循环 `asyncio.wait(..., return_when=FIRST_COMPLETED)`，任一槽位空出就立刻补派 |
| 7 | paper.trigger fan-out | branch **均值**首次 `>= paper_threshold`（默认 0.7）时发一次 `paper.trigger`，`paper_triggered` 标志保证每个 branch 只触发一次 |
| 8 | expander fan-out | **单个结果**的 `reward >= paper_threshold` 时调用 `expander` 生成后续假设并追加到队列；本节的确定性 expander 每次生成 2 个 |
| 9 | 两种预算与 stop_reason | `max_experiments`（在**派发时**计数）与 `max_seconds`（只在任务完成之间检查，属于"软"上限）；触发后停止派发、等待在途任务（drain），`stop_reason ∈ {queue_empty, max_experiments, deadline}` |
| 10 | Trace 与报告 | 每个决定写一条 `TraceEvent`（dispatch / result / error / paper.trigger / prune / expand / result.drain）；`SchedulerReport` 汇总 branch 统计、实验数、墙钟时间与触发列表，供第 57 节读取 |

### 核心技能（能动手做到）

- [ ] 手算任意 `(runs, mean, total_runs, c)` 组合下的 UCB1 分数，并预测调度器下一步会选哪个 branch
- [ ] 用 `asyncio.create_task` + `asyncio.wait(FIRST_COMPLETED)` 写出"N 个槽位始终保持满载"的派发循环
- [ ] 读懂 `IterationScheduler.run` 中"处理完成 → 更新统计 → 触发/剪枝/扩展 → 检查预算 → 补派"的顺序，并能指出预算检查的时机
- [ ] 解释本节 demo 中 branch-b/c/d 只各跑 1 次、branch-c 没被剪枝的真实原因
- [ ] 为调度器补上"在途任务计入统计（virtual loss）"、"硬墙钟上限（取消在途任务）"、"失败计入统计"三类改进
- [ ] 用 `unittest` 编写异步调度器的测试（`asyncio.run` 包一层），验证并行加速、预算退出和剪枝

---

## 二、基础自测（选择题）

**Q1.** `c = √2`。branch A 已完成 4 次、平均奖励 0.8；branch B 已完成 1 次、平均奖励 0.5；全局共完成 5 次。按本节 `ucb_score`，调度器下一步优先选：

- A. A，因为它的平均奖励更高，UCB 分数约 1.70 vs 0.50
- B. A 和 B 分数相同，按队列顺序选
- C. B，A 的分数约 1.70，B 的分数约 2.29
- D. B，因为 runs 更少的 branch 总是得到 `+inf`

**Q2.** 运行 `main.py` 的 demo（4 个种子假设、20 次实验）后，branch-a 跑了 17 次，branch-b/c/d 各只跑了 1 次。最根本的原因是：

- A. 每个 branch 在种子里只有 1 个假设，而 expander 只在单次奖励 `>= 0.7` 时为该 branch 生成后续假设——只有 branch-a 能做到，于是队列里只剩 branch-a 的假设，UCB 根本没有可比较的对象
- B. UCB 的探索项太小，b/c/d 的分数一直低于 a
- C. b/c/d 在第 3 次实验后被剪枝了
- D. `max_experiments = 20` 的预算只允许每个 branch 跑 1 次

**Q3.** 关于 `experiments_run` 计数器，正确的是：

- A. 每当一个实验**成功返回** `Result` 时加 1
- B. 只在 drain 阶段统计
- C. 抛异常的实验不计入
- D. 在**派发**（`create_task`）时加 1，所以在途、失败的实验都计入预算

**Q4.** `asyncio.wait(in_flight.keys(), return_when=asyncio.FIRST_COMPLETED)` 的行为是：

- A. 等待所有任务完成后才返回
- B. 只要至少一个任务完成就返回 `(done, pending)`；`done` 可能包含多个同时完成的任务，是一个**集合**
- C. 返回第一个完成任务的结果值
- D. 会自动取消其余未完成的任务

**Q5.** `prune_floor = 0.2`、`prune_after_runs = 3`。下列哪个 branch 会在最后一个结果到达后被剪枝？

- A. 奖励依次为 `[0.1, 0.2, 0.25]`
- B. 奖励依次为 `[0.05, 0.05]`
- C. 奖励依次为 `[0.1, 0.1, 0.45]`
- D. 奖励依次为 `[0.3, 0.1, 0.2, 0.25, 0.25]`

**Q6.** 关于两种 fan-out 的触发条件，正确的是：

- A. 两者都看 branch 均值，且都只触发一次
- B. 两者都看单次奖励，每次满足都触发
- C. paper.trigger 看单次奖励；expander 看 branch 均值
- D. paper.trigger 看 branch **均值**且每个 branch 只触发一次；expander 看**单次结果**的奖励，每次满足都会生成后续假设

**Q7.** `slots = 2`、`max_seconds = 0.1`，runner 每次 `await asyncio.sleep(0.5)`，种子里有 5 个假设。实际运行结果最接近：

- A. `stop_reason = "deadline"`，`wall_seconds ≈ 0.1`，在途任务被取消
- B. `stop_reason = "queue_empty"`，5 个都跑完
- C. `stop_reason = "deadline"`，但 `wall_seconds ≈ 0.5`：截止时间只在任务完成之间检查，且在途任务会被 drain 等完
- D. 抛出 `asyncio.TimeoutError`

**Q8.** 种子为 `[A1(branch A), A2(branch A), B1(branch B)]`，`slots = 2`，开局派发的两个假设是：

- A. A1 和 B1，因为调度器保证先探索不同 branch
- B. A1 和 A2：在途的 branch A 仍是 `runs = 0`，分数为 `+inf`，与 B 相同，按队列顺序（严格 `>`）先选到 A2
- C. A2 和 B1
- D. 随机两个

---

## 三、动手 / 代码题

**Q9.** 下面的 runner 对 branch `"bad"` 总是抛异常：

```python
async def flaky(h):
    if h.branch == "bad":
        raise RuntimeError("boom")
    return Result(h.id, h.branch, 0.5)

seed = [Hypothesis("g1", "good"), Hypothesis("g2", "good")] + \
       [Hypothesis(f"b{i}", "bad") for i in range(4)]
IterationScheduler(flaky, slots=1, max_experiments=10, prune_floor=0.2)
```

1. 跑完后 `bad` 的 `runs`、`pruned` 分别是多少？4 个 bad 假设会不会全被派发？
2. 结合 `run()` 中处理异常的代码，说明为什么"总是失败的 branch"反而会被**优先**调度。
3. 给出一种修复方案（代码层面）。

**Q10.** Q8 暴露了一个并行问题：同一 branch 的多个假设会因为"统计还没回来"而被同时派发。请修改 `_pick_next`，让它在计算 UCB 时把**在途任务**也考虑进去（提示：业界称为 virtual loss / pending count）。写出新的函数签名与核心代码，并说明 `run()` 中需要怎样传参。

**Q11.** Q7 说明 `max_seconds` 不是硬上限。请改写主循环，使截止时间到达时：(1) `asyncio.wait` 不再无限等待；(2) 在途任务被取消；(3) trace 中记录被取消的假设。写出关键代码。

**Q12.** 阅读 demo 输出（节选）：

```text
"stop_reason": "max_experiments", "experiments_run": 20,
branch-a: runs 17, mean 0.834, paper_triggered true
branch-b: runs 1,  mean 0.565
branch-c: runs 1,  mean 0.136, pruned false
branch-d: runs 1,  mean 0.355
trace 计数: dispatch 20, result 20, expand 17, paper.trigger 1
```

1. branch-c 的均值 0.136 明显低于 `prune_floor = 0.25`，为什么没被剪枝？
2. 运行结束时队列里还剩多少个假设？写出算式。
3. 如果想让 demo 真正展示"UCB 在多个 branch 间分配实验 + 剪枝"，最小的改动是什么？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 explore–exploit 权衡？UCB1 的公式是什么，每一项的含义是什么？和 ε-greedy、Thompson Sampling 相比各有什么特点？

**Q14.**（原理深挖）UCB1 的理论保证依赖哪些假设？把它用在"自动科研调度"这种场景里，有哪些假设被违反了？会带来什么后果？

**Q15.**（工程实践）本节用 asyncio 实现并行槽位。如果真实实验是"跑 20 分钟的 GPU 训练脚本"或"CPU 密集的 NumPy 计算"，直接把它写成 `async def` 会有什么问题？你会怎样改造？

**Q16.**（场景设计）请设计一个生产级的研究调度器：每天有上百个由 LLM 生成的假设、每个实验消耗不同的 GPU 小时，预算以美元计。你会如何设计数据模型、调度策略、预算控制、容错与可观测性？

**Q17.**（追问型）"UCB 在并行/批量场景下还成立吗？"——请说明延迟反馈带来的问题和常见对策，并结合本节代码指出对应的位置。

---

## 五、参考答案与解析

### Q1 — 答案：C

实际计算（已用 `ucb_score` 运行验证）：

- A：`0.8 + √2 · sqrt(ln5 / 4) = 0.8 + 1.4142 × 0.6343 ≈ 1.6971`
- B：`0.5 + √2 · sqrt(ln5 / 1) = 0.5 + 1.4142 × 1.2686 ≈ 2.2941`

B 的均值低，但只试过 1 次，置信区间很宽，探索项更大，所以选 B。A 错在只算了 B 的均值、忽略了探索项（`c = 0` 时才会得到 0.8 vs 0.5）；B 错，分数不同；D 错，只有 `runs == 0` 才是 `+inf`，B 已经跑过 1 次。

### Q2 — 答案：A

`make_deterministic_runner` 的基准奖励是 a=0.85、b=0.55、c=0.15、d=0.40，噪声 σ=0.05。`deterministic_expander` 只在 `result.reward >= paper_threshold (0.7)` 时被调用，只有 branch-a 的结果能达到。所以 b/c/d 的唯一假设跑完后，队列里全是 `h-a-1-f1`、`h-a-1-f1-f1` 这类 branch-a 的后续假设；`_pick_next` 只能在同一个 branch 内比较，分数全部相同，等价于 FIFO。B 错，UCB 从来没有机会比较不同 branch；C 错，b/c/d 都只有 1 次运行，达不到 `prune_after_runs = 3`；D 错，预算是全局的，不是按 branch 分配。

### Q3 — 答案：D

`dispatch_until_full` 里每次 `create_task` 之后立刻 `experiments_run += 1`。因此预算衡量的是"派出去的工作量"，包括之后抛异常的实验（异常只写 `error` trace，不会退还预算）。A、C 是常见误解；B 错，drain 阶段只是等在途任务完成，不再改动计数。

### Q4 — 答案：B

`FIRST_COMPLETED` 表示"至少一个完成就返回"，返回值是 `(done, pending)` 两个集合。多个任务在同一轮事件循环中完成时，`done` 里会有多个——这正是 demo trace 中经常出现"连续 3 条 result 才接 1 条 dispatch"的原因。A 是 `ALL_COMPLETED`；C 错，返回的是 Task 集合，需要 `task.result()` 取值；D 错，`asyncio.wait` 不会取消任何任务（`asyncio.wait_for` 超时才会取消）。另外注意 `done` 是集合，迭代顺序不保证与完成顺序一致。

### Q5 — 答案：A

- A：`runs = 3`，均值 `0.5500/3 ≈ 0.1833 < 0.2` → 剪枝。
- B：均值 0.05 很低，但 `runs = 2 < 3`，还不满足最少次数。
- C：均值 `≈ 0.2167`，不低于 0.2。
- D：均值 `≈ 0.22`，不低于 0.2。

剪枝看的是**累计均值**而不是最后一次奖励；条件是 `runs >= prune_after_runs and mean < prune_floor`（严格小于）。

### Q6 — 答案：D

代码原文：

```python
if (not bs.paper_triggered) and bs.mean >= self.paper_threshold and bs.runs >= 1:
    bs.paper_triggered = True
    ...
if self.expander is not None and result.reward >= self.paper_threshold:
    followups = self.expander(result)
```

paper.trigger 用的是 `bs.mean`（branch 均值）加一次性标志；expander 用的是 `result.reward`（这一次的奖励），没有次数限制，所以 demo 里 branch-a 的 17 个结果触发了 17 次 expand、却只有 1 次 paper.trigger。两者共用 `paper_threshold` 这个阈值，但语义不同——这是读代码时容易混淆的地方。

### Q7 — 答案：C

已实际运行验证：`stop_reason = deadline`，`wall_seconds ≈ 0.501`，`experiments_run = 2`。原因有二：(1) `deadline_hit()` 只在 `asyncio.wait` 返回之后检查，而 `asyncio.wait` 本身没有 `timeout`，必须等到第一个任务完成（0.5s）；(2) 跳出主循环后，代码对剩余在途任务逐个 `await task`（drain），不会取消。所以 `max_seconds` 只能阻止"派发新实验"，不能限制单个实验的耗时。A 是许多人期望的行为，但代码没有实现（见 Q11）；D 错，代码里没有 `wait_for`。

### Q8 — 答案：B

已实际运行验证：派发顺序为 `['A1', 'A2', 'B1']`。`_pick_next` 用的 `stats` 只在任务**完成**后更新，A1 在途期间 branch A 依然 `runs = 0 → +inf`；A2 与 B1 分数都是 `+inf`，而 `if score > best_score` 是严格大于，平局时保留先遍历到的下标，A2 排在前面。这说明"untried 优先"在并行时会失效——同一个 branch 被并发试了两次，而 B 要等到槽位空出。修复见 Q10。A 是讲义描述的理想行为；C、D 与代码不符。

### Q9 — 参考答案

1. 已实际运行：`bad` 的 `runs = 0`、`pruned = False`，4 个 bad 假设**全部**被派发，trace 中出现 `dispatch, error, dispatch, error, ...`，最终 `stop_reason = queue_empty`。
2. 主循环的异常分支是：

   ```python
   except Exception as exc:
       trace.append(TraceEvent(kind="error", ...))
       continue
   ```

   `continue` 跳过了 `bs.runs += 1`。于是失败的 branch 永远是 `runs = 0`，UCB 分数恒为 `+inf`——它会被**最优先**调度，同时又永远达不到剪枝所需的 `runs >= 3`。这是"失败被当成没发生"的典型 bug，在真实系统里会让一个配置错误的方向吃光预算。此外 drain 阶段的 `except Exception: ... continue` 连 error trace 都不写。
3. 修复思路（任选其一或组合）：
   - 把失败当作奖励 0 的一次运行：`bs.runs += 1; bs.reward_sum += 0.0`，再走正常的剪枝检查；
   - 在 `BranchStats` 中加 `failures` 字段，`failures >= k` 时直接剪枝（与"低产出"分开统计，便于排查）；
   - drain 阶段同样记录 `error` 事件，保证 trace 完整。

### Q10 — 参考答案

思路：维护每个 branch 的在途数量 `pending`，打分时把在途任务视为"已经跑过、但奖励暂按某个保守值计"，从而压低同 branch 的再次派发。

```python
from collections import Counter

def _pick_next(self, queue, stats, pending: Counter) -> int | None:
    total = sum(s.runs for s in stats.values()) + sum(pending.values())
    best_idx, best_score = None, -float("inf")
    for idx, hyp in enumerate(queue):
        bs = stats.get(hyp.branch) or BranchStats(branch=hyp.branch)
        if bs.pruned:
            continue
        n = bs.runs + pending[hyp.branch]          # 在途也计入次数
        if n == 0:
            score = float("inf")
        else:
            mean = bs.reward_sum / n               # virtual loss：在途按 0 奖励计
            score = mean + self.exploration_c * math.sqrt(math.log(max(total, 1)) / n)
        if score > best_score:
            best_idx, best_score = idx, score
    return best_idx
```

`run()` 中：派发时 `pending[hyp.branch] += 1`，任务完成（无论成功或失败）时 `pending[hyp.branch] -= 1`，调用改为 `self._pick_next(queue, stats, pending)`。验证：Q8 的种子会派发 `A1, B1`。"按 0 奖励计"偏悲观；也可以只把 `pending` 加到分母 `n` 上而不拉低均值，或者用当前均值作为占位奖励，属于强度不同的 virtual loss。

### Q11 — 参考答案

```python
while in_flight:
    remaining = self.max_seconds - (time.monotonic() - t0)
    if remaining <= 0:
        stop_reason = "deadline"
        break
    done, _ = await asyncio.wait(in_flight.keys(), timeout=remaining,
                                 return_when=asyncio.FIRST_COMPLETED)
    if not done:                       # 超时，没有任何任务完成
        stop_reason = "deadline"
        break
    ...                                # 原有的处理逻辑

if stop_reason == "deadline":
    for task, hyp in list(in_flight.items()):
        task.cancel()
        trace.append(TraceEvent(kind="cancel",
                                payload={"hypothesis_id": hyp.id, "branch": hyp.branch}))
    await asyncio.gather(*in_flight.keys(), return_exceptions=True)  # 让取消真正落地
    in_flight.clear()
```

要点：`asyncio.wait(timeout=...)` 超时返回空的 `done`，不会抛异常；`task.cancel()` 只是请求取消，需要再 `await`（这里用 `gather(..., return_exceptions=True)` 吞掉 `CancelledError`）；`max_experiments` 触发时是否也取消在途任务属于策略选择——已经花了钱的实验通常值得等完。被取消的实验不应计入 `BranchStats`，但应保留在 trace 中。

### Q12 — 参考答案

1. 剪枝要求 `runs >= prune_after_runs (3)`，branch-c 只有 1 个种子假设、跑了 1 次，而它的奖励（0.136）低于 0.7，不会触发 expander，也就没有第 2、3 次机会。**demo 实际上没有展示剪枝**——剪枝只在测试 `test_low_yield_branch_is_pruned_after_threshold_runs`（每个 branch 5 个假设）里出现。
2. 队列剩余 = 种子 4 + expand 17 次 × 2 − 派发 20 = **18** 个。expander 每次加 2、每次只消耗 1，队列呈指数式膨胀（讲义说剪枝"keeps the queue bounded"，但对高产 branch 的扩展并没有上限）。
3. 最小改动：让每个 branch 在种子里有多个假设，例如 `seed = [Hypothesis(f"h-{b}-{i}", f"branch-{b}") for b in "abcd" for i in range(5)]`。这样 `_pick_next` 有了跨 branch 的比较对象，branch-c 在跑满 3 次、均值 < 0.25 后会被剪枝。另一个思路是给 expander 设上限（每个 branch 最多扩展 k 次），避免队列被单个 branch 占满。

### Q13 — 参考回答要点

- **explore–exploit**：资源有限时，要在"继续投入目前最好的方向"（exploit）和"尝试了解还不充分的方向"（explore）之间分配；只 exploit 可能被早期的运气锁死在次优方向，只 explore 则浪费预算。
- **UCB1**：`score = x̄_i + c·sqrt(ln N / n_i)`。`x̄_i` 是该臂（branch）的平均奖励；`n_i` 是它被试的次数；`N` 是总次数；第二项是置信上界的宽度——试得越少越宽，随 `ln N` 缓慢增长，保证每条臂都会被偶尔重访。经典 UCB1 取 `c = √2`（本节默认值）。
- **对比**：
  - ε-greedy：以概率 ε 随机探索，简单但探索是"盲目"的，不区分哪条臂更不确定；
  - UCB：确定性、"乐观面对不确定性"，探索集中在不确定性大的臂上；
  - Thompson Sampling：对每条臂维护后验分布、按采样值选择，实践中效果常常最好，天然随机，便于并行。
- 加分点：说明 UCB 是"乐观主义"原则；能指出本节 `runs == 0 → +inf` 对应"每条臂先各拉一次"的初始化。

### Q14 — 参考回答要点

- **UCB1 的典型假设**：奖励有界（如 [0,1]）、每条臂的奖励分布**平稳**且独立同分布、每拉一次立刻得到反馈、臂的集合固定。
- **本场景的违背**：
  - **非平稳**：同一 branch 下后续假设由 expander 生成，质量可能越来越好或越来越差，历史均值滞后；
  - **延迟反馈 / 并行**：多个实验同时在途，统计滞后（见 Q8、Q17）；
  - **臂集合动态变化**：expander 不断增加假设，剪枝不断删除 branch；
  - **奖励定义**：奖励来自评估器（第 53 节），本身带噪声、甚至有偏；
  - **成本不等**：不同实验的耗时、GPU 成本不同，UCB 只看次数不看成本。
- **后果**：可能过早放弃一个"慢热"方向；被单个高噪声结果误导；预算被昂贵实验吃掉。
- **对策**：滑动窗口 / 折扣 UCB 应对非平稳；按成本归一化的奖励（reward per GPU-hour）；剪枝前要求足够样本并给出置信区间；对奖励做校准。
- 常见误区：以为 UCB 有"理论保证"就可以直接用——保证只在其假设下成立。

### Q15 — 参考回答要点

- **asyncio 的本质**：单线程事件循环 + 协作式调度，只有在 `await` 处才会切换。本节 runner 用 `await asyncio.sleep(...)` 模拟 I/O，所以能"并行"。
- **CPU 密集**：如果 runner 在 `async def` 里直接做 NumPy 大计算，期间不 `await`，整个事件循环被阻塞，其他槽位、截止时间检查都停摆——"3 个槽位"退化成串行。对策：`await loop.run_in_executor(ProcessPoolExecutor(), fn, args)` 或 `asyncio.to_thread`（释放 GIL 的库可用线程）。
- **长时间 GPU 作业**：调度器不应在进程内执行，而应把实验提交给作业系统（Slurm、Kubernetes Job、Ray），runner 变成"提交 + 轮询/回调"的协程；用 `asyncio.create_subprocess_exec` 启动子进程也可以。这样还能获得隔离、重试、超时和资源配额。
- **容错**：每个实验要有超时（`asyncio.wait_for`）和取消；结果要持久化，调度器重启后能恢复（讲义 Going further 的第一条）。
- 加分点：指出 `time.monotonic()` 测的是墙钟时间，而讲义写"asyncio time"——两者在本例中等价，但若要配合 `loop.time()` 的调度应保持一致。

### Q16 — 参考回答要点

- **数据模型**：`Hypothesis(id, branch, payload, parent_id, created_by)`、`Experiment(id, hypothesis_id, status, cost, started_at, result)`、`BranchStats(runs, reward_sum, cost_sum, failures, pruned, last_updated)`；全部写入数据库，支持重启恢复（checkpoint UCB 统计）。
- **调度策略**：UCB / Thompson Sampling 打分，奖励按成本归一化或做多目标（讲义提到 Pareto 式选择器）；在途任务计入 virtual loss；对 expander 设"每个 branch 最大深度/最大扩展数"；对新 branch 设冷启动配额。
- **预算控制**：全局美元预算 + 每 branch 预算 + 单实验超时；派发前做"预计成本"检查；硬截止时取消在途任务。
- **容错**：失败计入统计（见 Q9）；可重试错误与不可重试错误分开；幂等的实验 ID，避免重复执行。
- **可观测性**：每个决策写结构化事件（dispatch / result / prune / expand / cancel），附 UCB 分数与理由；仪表盘展示槽位占用率、各 branch 均值与置信区间、预算燃烧曲线。
- **人类介入**：高价值的 paper.trigger 先进入人工审核队列；允许人工固定或屏蔽某个 branch。

### Q17 — 参考回答要点

- **问题**：经典 bandit 假设"拉一次、马上看到奖励、再决定下一次"。并行时，多个决策基于同一份过时的统计，容易把多个槽位都派给同一个"看起来最好/最不确定"的臂。本节代码中，`_pick_next` 只读已完成的 `stats`（`total_runs = sum(s.runs ...)`），Q8 中 A1、A2 被同时派发就是例证。
- **对策**：
  - virtual loss / pending count（见 Q10），MCTS 并行化中常用；
  - Thompson Sampling：每次决策独立采样，天然带来多样性；
  - 批量 UCB（batch bandits）：一次选一组，组内要求多样性；
  - 限制同一 branch 的并发数。
- **其他延迟反馈问题**：慢实验的结果晚到，统计偏向快实验；需要按"派发时间"而不是"完成时间"来理解数据。
- 加分点：指出 `done` 是集合、同批完成的结果处理顺序不确定，会影响 expander 追加到队列的顺序，进而影响后续派发——要做可复现实验，应对 `done` 按派发序号排序后再处理。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 50 研究假设生成器](../../50-hypothesis-generator/docs/zh.md)：本节队列里的 `Hypothesis` 从这里来。
- [阶段 19 · 52 实验执行器](../../52-experiment-runner/docs/zh.md)：本节的 `runner` 是它的异步化替身。
- [阶段 19 · 53 结果评估器](../../53-result-evaluator/docs/zh.md)：`reward` 的来源，奖励是否可靠直接决定 UCB 是否可靠。
- [阶段 09 · 01 MDP、状态、动作与奖励](../../../09-reinforcement-learning/01-mdps-states-actions-rewards/docs/zh.md)：奖励、探索与利用的基本概念。
- [阶段 14 · 04 Tree of Thoughts 与 LATS](../../../14-agent-engineering/04-tree-of-thoughts-lats/docs/zh.md)：LATS 使用 MCTS/UCT，同样依赖 UCB 式的探索项。

### 本节被哪些后续内容用到
- [阶段 19 · 57 端到端研究演示](../../57-end-to-end-research-demo/docs/zh.md)：直接导入本节的 `IterationScheduler`，读取 `SchedulerReport` 选出最佳 branch。
- [阶段 19 · 54 论文写作器](../../54-paper-writer/docs/zh.md)：`paper.trigger` 的下游消费者。
- [阶段 19 · 55 Critic 评审循环](../../55-critic-loop/docs/zh.md)：对选中 branch 的论文草稿做多轮评审。
- [阶段 15 · 05 AI Scientist v2](../../../15-autonomous-systems/05-ai-scientist-v2/docs/zh.md)：自主科研系统中的实验树搜索与调度。
- [阶段 14 · 29 生产运行时：队列、事件与定时任务](../../../14-agent-engineering/29-production-runtimes/docs/zh.md)：把内存中的调度器换成持久化队列与作业系统。

### 延伸关键词
`multi-armed bandit` · `UCB1` · `ε-greedy` · `Thompson Sampling` · `virtual loss` · `batch bandits` · `non-stationary bandit` · `asyncio.wait` · `FIRST_COMPLETED` · `task cancellation` · `run_in_executor` · `fan-in / fan-out`
