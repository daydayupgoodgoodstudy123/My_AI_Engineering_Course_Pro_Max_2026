# 代码讲解 · main.py

> **所属小节**：阶段 20 · 递归自我改进 · 第 03 节 算力瓶颈：纯软件智能爆炸为何会停滞 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py [--scenario software-only|compute-growth|both] [--automation 30] [--compute-growth 4] [--compute-fraction 0.40] [--agents 128] [--gpus 8] [--cycles 50] [--jitter 0.0] [--seed 7] [--human-decision]` ｜ **依赖**：仅标准库（`argparse`、`heapq`、`itertools`、`math`、`random`、`statistics`、`collections`、`dataclasses`、`typing`）

---

## 1. 这份代码在考察什么

讲义的核心论点是：AI 研究流水线里有一个阶段——实验算力——AI 劳动力再多、再快也无法缩短。于是"纯软件智能爆炸"的总加速比有天花板。这份代码把这个论点做成两层可以动手验证的模型：

1. **Amdahl 定律层**：把一个研究周期拆成五个阶段（ideation 0.15、coding 0.25、experiment-compute 0.40、evaluation 0.15、decision 0.05），劳动阶段的倍率是 `k`，算力阶段的倍率是 `g`，总加速比 `S = 1 / Σ f_i / m_i`。扫一遍 `k = 1 … 1000`，看它如何逼近 `g / f_compute`。
2. **GPU 队列层**：`N` 个 agent 副本共用 `C` 块 GPU 的闭合队列。每个 agent 思考 → 提交一个实验 → 排队等 GPU → 读结果 → 再思考。吞吐量被 `C / E` 封顶，超过"拐点"之后再加副本只会拉长队列。

三个场景做对照：`software-only`（算力固定）、`compute-growth`（劳动力固定、算力增长）、`both`（两者都动，默认）。

> 一句话：**用 Amdahl 定律和一个闭合队列证明"30× 的 agent 跑 30× 快"换不来 900× 的研究速度——实验阶段和共享的 GPU 池决定了上限**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DEFAULT_SEED = 7`、`SWEEP` | 常量 | 默认种子；`k`/`g` 的扫描点 (1, 2, 5, 10, 30, 100, 300, 1000) | 可复现、扫描范围 |
| `Stage` | dataclass（frozen） | 一个阶段：名字、占基线周期的份额、种类（labour / compute） | 流水线阶段 |
| `BASE_STAGES` / `build_stages` | 常量 / 函数 | 五个默认阶段；按 `--compute-fraction` 重新缩放劳动阶段 | `f_i` |
| `multipliers_for` | 函数 | 给每个阶段分配倍率：劳动 `k`、算力 `g`、人工决策 1 | `m_i` |
| `cycle_time` / `amdahl_speedup` | 函数 | `Σ f_i / m_i` 与其倒数 | Amdahl 定律 |
| `asymptote` | 函数 | 被加速阶段趋于 0 时的极限加速比 `1 / Σ 固定阶段 f_i / m_i` | 天花板 `g / f_compute` |
| `k_for_fraction_of_asymptote` | 函数 | 达到天花板某个比例（如 95%）所需的 `k` | "再加劳动力也没用"的位置 |
| `QueueResult` | dataclass | 队列模拟的全部统计量 | 吞吐、利用率、等待、周期时间 |
| `simulate_queue` | 函数 | 事件驱动的闭合队列模拟（堆 + FIFO 队列） | 串行 vs 并行 |
| `agent_sweep` / `pool_ceiling` / `saturation_point` | 函数 | 1, 2, 4, … 的副本数序列；池上限 `C / E`；"再翻倍增益 < 5%"的拐点 | 饱和曲线 |
| `print_*` / `run_queue_block` | 函数 | 对齐表格输出 | 报告 |
| `main` | 函数 | 解析参数、按场景跑两层模型、用计算结果拼 HEADLINE | 入口 |

数据流：命令行参数 → `build_stages` → `multipliers_for` → Amdahl 扫描表 → 对每个副本数 `simulate_queue` → 队列表 + 池上限 + 拐点 → 由数字生成的 HEADLINE。

---

## 3. 逐段精讲

### 3.1 阶段定义与重新缩放

```python
@dataclass(frozen=True)
class Stage:
    name: str
    fraction: float
    kind: str  # LABOUR (AI copies can speed it up) or COMPUTE (needs GPUs)


def build_stages(compute_fraction: float = 0.40) -> tuple[Stage, ...]:
    base_labour = sum(s.fraction for s in BASE_STAGES if s.kind == LABOUR)
    scale = (1.0 - compute_fraction) / base_labour
    out = []
    for s in BASE_STAGES:
        frac = compute_fraction if s.kind == COMPUTE else s.fraction * scale
        out.append(Stage(s.name, frac, s.kind))
    return tuple(out)
```

- `frozen=True` 让 `Stage` 不可变、可哈希——阶段是配置，不该在运行中被改。
- `--compute-fraction` 只改算力份额，四个劳动阶段按原比例分掉剩下的 `1 − f_compute`。例如 0.20 时，ideation 变成 0.20、coding 0.333、evaluation 0.20、decision 0.067，总和仍是 1。
- 份额之和为 1 是后面所有公式的前提，测试 `test_fractions_sum_to_one_for_any_compute_share` 专门检查它。

### 3.2 Amdahl 定律三件套

```python
def cycle_time(stages, mult):
    return sum(s.fraction / mult[s.name] for s in stages)


def amdahl_speedup(stages, mult):
    return 1.0 / cycle_time(stages, mult)


def asymptote(stages, mult, accelerated):
    acc = set(accelerated)
    fixed = sum(s.fraction / mult[s.name] for s in stages if s.name not in acc)
    return math.inf if fixed == 0 else 1.0 / fixed
```

- 时间单位是"一个基线研究周期"（人类、未自动化）。`cycle_time` 就是加速后的周期长度，`amdahl_speedup` 是它的倒数。
- `asymptote` 把被加速的阶段当作时间趋于 0，只剩固定阶段。默认情况下固定阶段只有 experiment-compute，倍率 `g`，所以极限是 `g / 0.40`；`--human-decision` 时 decision 也固定在 1×，极限变成 `1 / (0.40 + 0.05) = 2.22×`。
- `k_for_fraction_of_asymptote` 解方程 `1 / (L / k + F) = frac / F`，得 `k = L / (F (1/frac − 1))`。`frac = 0.95` 时 `k = 19 L / F = 19 × 0.6 / 0.4 = 28.5`——与 AI 2027 的"30× 更快"几乎重合，这是讲义反复强调的巧合。

### 3.3 `simulate_queue()`：事件驱动的闭合队列

```python
    seq = itertools.count()
    events: list[tuple[float, int, int, int]] = []
    for a in range(agents):
        heapq.heappush(events, (labour_time, next(seq), SUBMIT, a))
    ...
    while events and events[0][0] <= horizon:
        now, _, kind, agent = heapq.heappop(events)
        if kind == SUBMIT:
            submitted += 1
            if free > 0:
                start(agent, now, now)
            else:
                waiting.append((agent, now))
        else:
            completed += 1
            free += 1
            if agent in last_finish:
                cycle_times.append(now - last_finish[agent])
            last_finish[agent] = now
            heapq.heappush(events, (now + labour_time, next(seq), SUBMIT, agent))
            if waiting:
                nxt, t_sub = waiting.popleft()
                start(nxt, t_sub, now)
```

- 这是连续时间、事件驱动的模拟：事件是 `(时间, 序号, 类型, agent)` 四元组放进最小堆；`itertools.count()` 产生的序号保证同一时刻的事件按插入顺序处理（FIFO 且确定）。
- 每个 agent 的状态机只有两类事件：`SUBMIT`（思考完、提交实验）和 `FINISH`（实验结束）。agent 读完结果才会开始下一轮思考——这就是"下一个想法依赖上一个实验结果"的串行约束。
- `free` 是空闲 GPU 数，`waiting` 是 FIFO 队列。`FINISH` 释放 GPU 后立刻把队头拉上来，所以池子一旦饱和就永远满载。
- `start()` 里记录等待时间 `now − submit_time`，并把忙时累加到 `busy`（截断到 `horizon`），用于算利用率。
- 守恒律：每次 `SUBMIT` 要么进 `start`（变 running），要么进 `waiting`；每次 `FINISH` 把 running 减一。所以 `submitted = completed + queued + running` 恒成立——测试 `test_conservation_*` 检查它。
- 抖动：`experiment_duration()` 在 `jitter > 0` 时乘上 `exp(N(0, σ) − σ²/2)`，这是均值为 1 的对数正态，用 `random.Random(seed)` 实例而不是全局 RNG。`jitter = 0` 时根本不碰 RNG，所以不同种子结果完全一样。

### 3.4 上限、拐点与饱和点

```python
def pool_ceiling(gpus, stages, compute_g):
    exp_time = sum(s.fraction / compute_g for s in stages if s.kind == COMPUTE)
    return gpus / exp_time


def saturation_point(rows, tol=0.05):
    for prev, nxt in zip(rows, rows[1:]):
        if prev.throughput > 0 and (nxt.throughput - prev.throughput) / prev.throughput < tol:
            return prev.agents
    return None
```

- 池上限 `C / E`：8 块 GPU、每个实验 0.40 周期 → 每周期最多完成 20 个实验。
- 解析拐点在 `run_queue_block` 里算：`knee = ceiling × cycle_time(单个 agent)`。`k = 30` 时单 agent 周期 0.42，拐点 8.4；`k = 1` 时周期 1.0，拐点 20。思考越快的 agent，固定 GPU 池能喂饱的副本数越少。
- `saturation_point` 是经验拐点：扫描序列里第一个"再翻倍吞吐增益 < 5%"的副本数。注意它只在扫描点（1, 2, 4, 8, …）上判断，所以可能和解析拐点差半个倍程（默认运行里经验值 8、解析值 8.4；`both` 场景经验值 16、解析值 9.6）。

### 3.5 `main()`：场景与 HEADLINE

```python
    if "software-only" in asyms:
        sw_asym = asyms["software-only"]
        sp_k = amdahl_speedup(stages, sw_mult)
        k95 = k_for_fraction_of_asymptote(stages, multipliers_for(stages, 1.0, 1.0, args.human_decision), acc, 0.95)
        print(f"  Software-only ceiling: with compute fixed, no amount of AI labour beats {sw_asym:.2f}x ({fixed_txt}).")
        print(f"  At k = {k:g}x the pipeline runs {sp_k:.2f}x faster ({sp_k / sw_asym:.1%} of the ceiling); ...")
```

- `--scenario` 决定打印哪些 Amdahl 列和哪些队列块；`print_amdahl_table` 把用到的极限值以字典返回，HEADLINE 只从这个字典和重新计算的数字拼句子，没有一句硬编码结论。
- 参数校验：`k`、`g` 必须 ≥ 1，`cycles` ≥ 1，否则 `parser.error` 直接退出并给出提示。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 五个阶段、固定份额 | 和讲义的表格一一对应，公式一眼能核 | 真实流水线份额要靠测量（实验排队日志、代码评审时长）；生产中用 `--compute-fraction` 之外的逐阶段参数 |
| 时间单位 = 一个基线周期 | 让队列模型在 `N = 1, C = 1` 时严格退化成 Amdahl 公式（测试 `test_single_agent_single_gpu_reproduces_amdahl`） | 失去绝对时长（小时/天）；要换算得乘上真实周期长度 |
| 算力增长 `g` 建模为"每个实验更短" | 与 Amdahl 的算力倍率同义，使两层模型一致 | "买更多芯片"应该是 `C × g`，不缩短单个实验——讲义练习 5 让你加这个模式 |
| 闭合队列（agent 等结果才继续） | 体现"下一个想法依赖上一个结果"的串行约束 | 真实研究者会并行挂多个实验；可以给每个 agent 一个在途实验上限参数 |
| 连续时间事件驱动而非离散 tick | 不会因为取整把 `0.6 / 30 = 0.02` 的思考时间压成 1 tick | 代码多了堆和序号；离散 tick 更直观但精度差 |
| 均值保持的对数正态抖动 | 让"上限是均值陈述"这一点可演示 | 真实实验时长是重尾的（失败重跑、OOM）；可换成 Pareto 或混合分布 |
| 确定性优先，`random.Random(seed)` 实例 | 复现；不同模块互不干扰 | 无 |
| HEADLINE 全由数字生成 | 改参数不会出现过时结论 | 句子模板比硬编码啰嗦 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class Stage` | 不可变数据类，实例可哈希、不可赋值 |
| 生成器表达式求和 | `sum(s.fraction / mult[s.name] for s in stages)` | 不建中间列表 |
| `heapq.heappush` / `heappop` | 事件堆 | 最小堆：总是弹出时间最早的事件 |
| `itertools.count()` | `seq = itertools.count(); next(seq)` | 无限递增序号，用作堆中的平局打破者 |
| `collections.deque` | `waiting.append(...)`、`waiting.popleft()` | 两端 O(1) 的 FIFO 队列 |
| `nonlocal` | `start()` 里修改 `free`、`busy` | 嵌套函数改写外层函数的局部变量 |
| `statistics.fmean` | `statistics.fmean(waits)` | 浮点均值，比 `mean` 快且总返回 float |
| `math.inf` / `math.nan` | `asymptote` 返回 `inf`；无周期时 `mean_cycle_time = nan` | 特殊浮点值，用 `math.isnan` 判断 |
| `zip(rows, rows[1:])` | `saturation_point` | 相邻元素成对 |
| f-string 格式 | `{sp:>8.2f}x`、`{r.utilization:>7.1%}`、`{g:g}` | 宽度、小数位、百分比（`.1%`）、`g` 去掉多余的零 |
| `format(g, 'g')` 拼在列标题里 | `'with compute x' + format(g, 'g')` | 在 f-string 外部做格式化 |
| `argparse` 的 `choices` 与 `parser.error` | `--scenario`；`parser.error("...")` | 枚举校验；自定义错误并以非零退出 |
| `from __future__ import annotations` | 文件开头 | 允许 `int | None`、`tuple[Stage, ...]` 等注解在 3.9 上也能写 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.12，默认 `--scenario both`，seed 7，0.1 秒），节选：

```text
AMDAHL SWEEP: labour automated by k; experiment compute fixed (g = 1) vs grown 4x
       k  software-only  of asym.    compute x4 only      both  of asym.
       1x          1.00x    40.0%              1.43x     1.43x    14.3%
      30x          2.38x    95.2%              1.43x     8.33x    83.3%   ← AI 2027 的 30×：纯软件只剩 5% 可赢
    1000x          2.50x    99.9%              1.43x     9.94x    99.4%
  asymptotes: software-only 2.50x   both (k -> inf, g = 4) 10.00x        ← 1/0.40 与 4/0.40

  software-only: labour 30x, compute fixed (experiment = 0.40 cycles)
   agents  submitted  completed  queued  exp/cycle    util  mean wait  cycle time
        8        960        952       0      19.04   95.2%       0.00       0.42   ← 拐点以下：零等待
       16       1008        992       8      19.84  100.0%       0.38       0.80   ← 池满，开始排队
      128       1120        992     120      19.84  100.0%       5.60       6.40   ← 吞吐不变，每个副本慢 15×
  pool ceiling = 20.00 exp/cycle; analytic knee = 8.4 agents (ceiling x single-agent cycle time)

HEADLINE (every number below is computed from the inputs above)
  Software-only ceiling: with compute fixed, no amount of AI labour beats 2.50x (1 / f_compute = 1 / 0.40).
  At k = 30x the pipeline runs 2.38x faster (95.2% of the ceiling); at k = 1000x only 2.50x.
  95% of the ceiling is reached at k = 28.5x; everything past that is spent waiting on experiments.
  Growing compute 4x lifts the ceiling to 10.00x (= g / f_compute); at k = 30x that gives 8.33x, i.e. 3.50x more than software alone.
  Queue [software-only]: 8 GPUs cap useful experiments at 20.00/cycle; doubling past 8 agents adds < 5% throughput (analytic knee 8.4).
    1 agent: 2.38 exp/cycle, wait 0.00; 128 agents: 19.84 exp/cycle, wait 5.60 cycles, per-agent cycle time 0.42 -> 6.40 cycles (15.2x slower per copy).
```

逐项解读：

- **Amdahl 表**：`k` 从 30 到 1000，纯软件加速只从 2.38× 涨到 2.50×。`compute x4 only` 一列恒为 1.43×——劳动力不动时算力再多也只能吃掉 0.40 那一块。两者都动才到 8.33×。
- **队列表**：吞吐在 8 个 agent 时 19.04，16 个时 19.84，之后纹丝不动；`queued` 列正好等于 `N − 8`（池满后多出的副本都在排队）。`completed` 停在 992 而不是 1000 = 20 × 50，是因为前 0.02 个周期 GPU 空着，且第 50 周期末尾正在跑的 8 个实验没算完成——`submitted − completed − queued = 8 = running`，守恒成立。
- **周期时间**：128 个副本时每个副本 6.40 个周期才完成一次实验，正是 Little 定律 `N / X = 128 / 20 = 6.4`。这就是 Burtsev 说的"周期长度成为限制性时间尺度"。

**非默认运行 1**：`python3 main.py --automation 1 --agents 256 --scenario software-only`（人类速度的劳动力）：

```text
       16        800        792       0      15.84   79.2%       0.00       1.00
       32       1008        984      16      19.68   98.8%       0.60       1.60
      256       1232        984     240      19.68   98.8%      10.35      12.80
  pool ceiling = 20.00 exp/cycle; analytic knee = 20.0 agents (ceiling x single-agent cycle time)
  Queue [software-only]: ... doubling past 32 agents adds < 5% throughput (analytic knee 20.0).
```

← 思考慢的 agent 在两次提交之间让 GPU 空闲，所以 8 块 GPU 能喂饱 20 个人类，却只能喂饱 8.4 个 30× 的 agent。"30× 的副本数"在固定算力下大部分变成了排队。

**非默认运行 2**：`python3 main.py --seed 3 --jitter 0.5 --scenario software-only`（实验时长随机）：

```text
        1        129        128       0       2.56   11.9%       0.00       0.39   ← 单 agent 2.56 > 2.38：这组样本的实验偏短
      128       1143        1015     120      20.30  100.0%       5.47       6.27   ← 吞吐 20.30 > 上限 20.00
  Jitter sigma = 0.5 (seed 3): the ceiling above is a mean; variance adds queueing even below the knee.
```

← 上限 `C / E` 是对**平均**实验时长的陈述；抖动是均值保持的，但 128 次采样的样本均值可以落在 0.40 之下（这里约 0.394），于是实测吞吐略高于 20。换个种子就可能低于 20。

**非默认运行 3**：`python3 main.py --compute-fraction 0.20 --scenario software-only`：天花板 5.00×，`k = 30` 时 4.41×（88.2%），95% 要到 `k = 76.0`；池上限 40/周期，拐点 9.1。小规模实验把天花板翻倍，但没有消灭它。

---

## 7. 动手改一改

1. **（讲义练习 1）** 分别跑 `--scenario software-only` 和 `--scenario compute-growth`，把两张扫描表的极限值（2.50× 与 1.67×）和 `1 / f_compute`、`1 / f_labour` 对上，再把 `--compute-fraction` 改成 0.5 看两者是否相等。
2. **（讲义练习 2）** 跑 `--compute-fraction 0.20 --scenario software-only`，记录天花板、`k = 30` 的加速比和 95% 点；再试 0.10 与 0.03，验证讲义里"10× 需要算力份额降到 10%，30× 需要约 3%"。
3. **（讲义练习 3）** 对比 `--automation 1 --agents 256` 与默认的拐点（20.0 vs 8.4），再试 `--automation 5`、`--automation 100`，把拐点随 `k` 变化画成表。
4. **（讲义练习 4）** 用 `--jitter 0.5` 跑 `--seed 1` 到 `--seed 5`，记录 16 个 agent 的吞吐与平均等待范围；把 `jitter` 调到 1.0 看等待如何在拐点以下就出现。
5. **（讲义练习 5）** 给 `simulate_queue` 加一个 `more_gpus: bool` 参数：为真时 `gpus = int(gpus * compute_g)`、实验时长不变。在 `k = 30, g = 4` 下比较两种模式的池上限、拐点和 128 个副本时的周期时间。
6. **进阶**：给每个 agent 一个"在途实验上限" `inflight` 参数（默认 1）。`inflight = 4` 时，单个 agent 可以同时挂 4 个实验再等结果——这对应"把一个想法拆成一批消融实验"。观察拐点如何随 `inflight` 移动，并解释为什么它改变的是劳动力的并行度而不是池上限。

---

## 8. 常见坑

- **把 Amdahl 的极限读成"最多 2.5× 的进步"**：它是**流水线速度**的上限，不是能力增量的上限。每个周期带来多少能力（Lesson 02 的 `r`、`R_AI`）是另一回事；本节只说周期能转多快。
- **以为 `k → ∞` 的极限是常数**：它是 `g / f_compute`，会随算力增长 `g` 和算力份额 `f_compute` 变化。小规模实验、更好的实验设计都是在改 `f_compute`。
- **用扫描点上的经验拐点代替解析拐点**：`saturation_point` 只看 1, 2, 4, 8, … 这些点，`both` 场景报 16 而解析值是 9.6。要精确就看 `analytic knee`。
- **把带抖动的吞吐超过上限当 bug**：上限是均值陈述；样本均值会波动。多跑几个种子。
- **`completed` 不等于 `ceiling × horizon`**：启动期 GPU 空闲，期末有在途实验。看 `exp/cycle` 这一列，不要自己拿 `completed / cycles` 以外的方式重算。
- **把"算力增长"只建模成更快的芯片**：`E / g` 缩短周期，`C × g` 不缩短周期只提升吞吐。两种对 Burtsev 的"限制性时间尺度"含义完全不同（练习 5）。
- **把 `--human-decision` 当成可忽略的小修正**：decision 只占 5%，但一旦固定在 1×，天花板从 2.50× 掉到 2.22×；在 `g = 4` 时掉得更明显（10× → 6.67×）。监督环节保留人类是有算得出来的速度代价的——这是 Lesson 19 的主题。
