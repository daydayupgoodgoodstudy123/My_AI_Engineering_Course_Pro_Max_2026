# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 19 节 面向 LLMs 的 Swarm 优化（PSO、ACO） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

这份约 180 行的脚本把两个经典群体智能算法放进"LLM 时代"的语境：

1. **PSO（讲义称 LMPSO）**：在 2 维连续参数空间（可以想象成 temperature 与 top_k 权重）上，用 20 个粒子、30 轮迭代寻找 fitness 峰值。fitness 是一个写死的数学函数，**没有调用任何 LLM**，代替"评估一次 prompt 配置"。
2. **ACO（讲义称 AMRO-S）**：3 个 agent（coder、mathematician、writer）× 4 种任务类型（code、math、writing、planning），用信息素矩阵做路由，与随机路由对比平均质量，并带有阈值 0.6 的 quality gate。

对应讲义的核心概念：PSO 速度更新三项（惯性/认知/社会）、ACO 的"按信息素选择—按质量沉积—蒸发"、quality-gated 更新、可解释的路由证据。

> 一句话：**两个算法都只需要一个打分函数（evaluator），不需要梯度**——这正是它们适合 prompt、路由这类不可微对象的原因。同时要看清代码的简化：fitness 的符号写反、PSO 里没有"速度即 prompt"、ACO 没有延迟建模和信息素下限。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Particle` | dataclass | 位置 `x`、速度 `v`、个体最优 `p_best` 及其 fitness | PSO 粒子 |
| `fitness` | 函数 | 带波纹的二次函数，模拟"一次评估" | 黑盒 evaluator |
| `run_lmpso` | 函数 | 初始化种群 → 30 轮速度/位置更新 → 返回每轮 g_best 历史 | PSO 主循环 |
| `PheromoneRouter` | 类 | 信息素矩阵、轮盘赌 `choose`、蒸发 + 质量门沉积 `deposit` | ACO / AMRO-S |
| `AGENT_TASK_AFFINITY` | 字典常量 | 每个 agent 在每类任务上的期望质量 | 模拟环境（真值） |
| `simulate_task` | 函数 | 亲和度 + 均匀噪声 ±0.15，截断到 [0, 1] | 一次 agent 执行 |
| `run_amro_s` | 函数 | 200 个任务，每个任务同时跑随机路由和 ACO 路由 | 对比实验 |
| `print_pheromone_table` | 函数 | 打印最终信息素表 | 可解释证据 |
| `main` | 函数 | 打印 PSO 收敛曲线、ACO 对比与信息素表 | 入口 |

数据流：
- PSO：`run_lmpso` → 随机初始化 20 粒子 → 每轮每粒子更新 `v`、`x` → `fitness` → 更新 `p_best`/`g_best` → 返回历史 → `main` 每 5 轮画一行 `#` 条形图。
- ACO：`run_amro_s` → 对第 i 个任务取 `task_types[i % 4]` → 随机路由打分 + `router.choose` → `simulate_task` → `router.deposit` → 返回两个平均质量和 router → 打印信息素表。

---

## 3. 逐段精讲

### 3.1 fitness：本该是"窄峰"，实际是"环形高地"

```python
def fitness(x: list[float]) -> float:
    cx, cy = 0.72, 0.40
    dx, dy = x[0] - cx, x[1] - cy
    dist2 = dx * dx + dy * dy
    ripple = 0.08 * (math.cos(8 * math.pi * dx) + math.cos(8 * math.pi * dy))
    return max(0.0, 1.0 - 6.0 * dist2 - ripple)
```

- 主体 `1 − 6·dist2` 是一个以 (0.72, 0.40) 为顶点的倒碗；`ripple` 加上波纹，让地形有多个局部极值，PSO 比"纯碗"更有挑战。
- ⚠️ **符号错误**：ripple 在中心取最大值 +0.16，被**减去**后中心只有 `0.84`，变成了一个凹陷。沿每个维度最大化 `−6d² − 0.08·cos(8πd)` 得 `d ≈ ±0.0997`，所以真实最大值约 `1.00945`，位于中心周围 4 个对称点（网格搜索得到 (0.6205, 0.3005) 等）。
- 这解释了运行输出里 `final g_best=1.0094` 比"optimum = 1.0000"还高的怪现象；默认种子最终的 g_best 位置是 `(0.8197, 0.4996)`。
- 修复方法：`1.0 - 6.0 * dist2 + ripple - 0.16`，此时最大值恰为 1，位于中心（见测验 Q9）。
- docstring 说"Rastrigin-style"：Rastrigin 函数是"二次项 + 余弦波纹"的经典多峰测试函数，这里借用了它的形状思路。

### 3.2 PSO 初始化

```python
    rng = random.Random(seed)
    w, c1, c2 = 0.6, 1.2, 1.2
    bounds = ((0.0, 1.0), (0.0, 1.0))

    particles: list[Particle] = []
    for _ in range(n_particles):
        x = [rng.uniform(*bounds[0]), rng.uniform(*bounds[1])]
        v = [rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1)]
        f = fitness(x)
        particles.append(Particle(x=list(x), v=v, p_best=list(x), p_best_fit=f))

    g_best = max(particles, key=lambda p: p.p_best_fit)
    g_best_x = list(g_best.p_best)
    g_best_fit = g_best.p_best_fit
```

- `w = 0.6`（惯性）、`c1 = c2 = 1.2`（认知、社会）：都是常见取值范围内的保守设置，惯性小于 1 保证速度会衰减，粒子最终会"停下来"。
- 位置在 [0, 1]² 里均匀撒点，速度很小（±0.1）。
- `x=list(x)`、`p_best=list(x)`：**复制**列表。如果 `p_best` 和 `x` 指向同一个列表，之后 `p.x[d] += ...` 会顺带改掉 `p_best`，个体最优就失效了。这是本段最值得注意的细节。
- 20 个随机点在一个 1×1 的小方格里已经覆盖得很密，默认种子下第 0 轮 g_best 已达 0.9601。所以"收敛曲线"在这个演示里并不明显。

### 3.3 PSO 主循环：速度 = 惯性 + 认知 + 社会

```python
    for _ in range(iterations):
        for p in particles:
            r1, r2 = rng.random(), rng.random()
            for d in range(2):
                cognitive = c1 * r1 * (p.p_best[d] - p.x[d])
                social = c2 * r2 * (g_best_x[d] - p.x[d])
                p.v[d] = w * p.v[d] + cognitive + social
                p.x[d] += p.v[d]
                p.x[d] = max(bounds[d][0], min(bounds[d][1], p.x[d]))
            f = fitness(p.x)
            if f > p.p_best_fit:
                p.p_best = list(p.x)
                p.p_best_fit = f
                if f > g_best_fit:
                    g_best_x = list(p.x)
                    g_best_fit = f
        history.append(g_best_fit)
```

- 三项分别对应讲义公式：`w·v`（保持方向）、`c1·r1·(p_best − x)`（回到自己见过的好地方）、`c2·r2·(g_best − x)`（向群体最好处靠拢）。
- **异步更新**：g_best 在每个粒子评估后立即更新，后面的粒子当轮就能用上新的 g_best（另一种写法是整轮评估完再统一更新，称同步 PSO）。
- 位置截断 `max(lo, min(hi, x))` 把粒子关在边界内。
- ⚠️ 与经典 PSO 的差异：
  - `r1, r2` 每个粒子只抽一次、两维共用；经典写法是每个维度独立抽取，以增加方向多样性；
  - 只截断位置，没有限制速度（`v_max`），撞墙时也不把速度清零；
  - 整个过程没有任何 LLM：讲义"Each particle's 'LLM generation' is simulated as a scripted fitness function"——所谓 LMPSO 只是标准数值 PSO，"速度即 prompt"的机制没有被模拟（讲义练习 4 让你思考丢掉了什么）。
- 评估次数：初始化 20 次 + 30 轮 × 20 次 = **620 次**。按讲义 $0.02/次的估算，这次演示相当于约 $12.4 的 LLM 评估费用。

### 3.4 `PheromoneRouter`：轮盘赌选择

```python
        self.pheromones = {t: {a: 1.0 for a in agents} for t in task_types}

    def choose(self, task_type: str, rng: random.Random) -> str:
        table = self.pheromones[task_type]
        total = sum(table.values())
        r = rng.random() * total
        upto = 0.0
        for a, p in table.items():
            upto += p
            if r <= upto:
                return a
        return self.agents[-1]
```

- 信息素矩阵是嵌套字典：`pheromones[task_type][agent]`，全部初始化为 1.0（一开始对每个 agent 一视同仁）。
- 轮盘赌（roulette-wheel selection）：在 `[0, total)` 上抽一个点，看它落在哪个 agent 的"扇区"里，选中概率与信息素成正比。
- 末尾的 `return self.agents[-1]` 是浮点误差兜底（`r` 恰好略大于累加和时）。
- 经典 ACO 的选择概率是 `τ^α · η^β`（信息素乘启发式），这里只有 `τ`、α = 1、没有启发式项 η。

### 3.5 蒸发与带质量门的沉积

```python
    def deposit(self, task_type: str, agent: str, quality: float) -> None:
        for a in self.agents:
            self.pheromones[task_type][a] *= (1.0 - self.decay)
        if quality >= self.quality_threshold:
            self.pheromones[task_type][agent] += self.reinforce * quality
```

- **蒸发**：只对当前任务类型这一行乘 `0.95`，所以衰减速度取决于"这类任务被路由的次数"，而不是时间。200 个任务中每类 50 次，从未被强化的条目最终是 `0.95^50 ≈ 0.077`——运行结果表中大量的 `0.077` 就是这么来的。
- **沉积**：质量 ≥ 0.6 时才给被选中的 agent 加 `0.2 × quality`。这就是 AMRO-S 的 quality gate。
- ⚠️ 没有信息素下限（τ_min）：落选者衰减到 0.077 后几乎再也选不中，分布一旦漂移恢复很慢（测验 Q12 的实验：加 0.3 的下限后，漂移后第一个 50 任务窗口的正确率从 0.29 提到 0.35，第二个窗口从 0.36 提到 0.48）。
- ⚠️ 统一的绝对阈值对"天然更难"的任务类型不友好：planning 的最优 agent（writer）期望只有 0.6，只有一半运行能过 0.6 的门；阈值提到 0.85 时 planning 行将永远学不到（测验 Q11）。
- ⚠️ 讲义说 quality gate 防止"fast-but-wrong agents"，但代码根本没有建模速度/延迟，也没有"快但错"的 agent。

### 3.6 环境与对比实验

```python
AGENT_TASK_AFFINITY = {
    "coder": {"code": 0.9, "math": 0.5, "writing": 0.3, "planning": 0.4},
    "mathematician": {"code": 0.4, "math": 0.95, "writing": 0.2, "planning": 0.5},
    "writer": {"code": 0.2, "math": 0.2, "writing": 0.9, "planning": 0.6},
}

def simulate_task(agent: str, task_type: str, rng: random.Random) -> float:
    base = AGENT_TASK_AFFINITY[agent][task_type]
    return max(0.0, min(1.0, base + rng.uniform(-0.15, 0.15)))
```

- 每类任务的最优 agent：code→coder，math→mathematician，writing→writer，planning→writer。
- 理论基线（考虑截断，数值积分）：随机路由期望质量约 **0.502**；每次都选最优 agent 的"oracle"约 **0.831**。

```python
    for i in range(n_tasks):
        tt = task_types[i % len(task_types)]
        rand_agent = rng.choice(agents)
        rq = simulate_task(rand_agent, tt, rng)
        random_router_quality += rq
        aco_agent = router.choose(tt, rng)
        aq = simulate_task(aco_agent, tt, rng)
        aco_quality += aq
        router.deposit(tt, aco_agent, aq)
```

- 任务按 code、math、writing、planning 轮流出现（`i % 4`），不是随机流。
- 随机路由和 ACO 路由共用一个 `rng`，二者的噪声是交错抽取的——"同一任务流"指任务类型序列相同，不是噪声相同。
- ⚠️ 讲义 Build It 说"Measures quality and latency"、"reduces latency (fewer retries)"，代码只测了质量，没有延迟和重试。讲义还说"100 routed tasks"和"打印随时间变化的分布"，代码是 200 个任务、只打印最终表。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用解析函数代替 LLM 评估 | 毫秒级运行、可复现 | 无法体现"速度即 prompt"；真实 LMPSO 每步要调 LLM 生成候选并跑评测 |
| 2 维参数空间 | 便于可视化与手算 | 高维时种群规模和收敛行为完全不同 |
| r1、r2 每粒子一组 | 代码简单 | 方向多样性下降；经典 PSO 每维独立抽取 |
| 只截断位置，不限速度 | 简单 | 粒子可能贴墙抖动；生产常用 `v_max` 或反弹 |
| 信息素按任务类型蒸发 | 每类任务独立学习 | 冷门任务类型的记忆衰减很慢；无下限会锁死 |
| 绝对质量阈值 0.6 | 简单直观 | 对难任务类型不公平；应按任务类型设定或用相对排名 |
| 同步"推理 + 学习" | 便于对比 | AMRO-S 的核心是异步解耦；生产中沉积应放到后台队列 |
| 只打印最终信息素表 | 输出简洁 | 讲义 Ship It 建议记录每轮信息素/g_best，便于排查 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class Particle` | 自动生成构造函数，字段带类型注解 |
| 类型注解 | `list[float]`、`tuple[float, float, PheromoneRouter]` | 文档作用，运行时不检查 |
| 解包传参 `*` | `rng.uniform(*bounds[0])` | 把元组 `(0.0, 1.0)` 展开成两个位置参数 |
| 列表复制 | `list(x)`、`list(p.x)` | 创建新列表，避免多个名字指向同一个可变对象 |
| `max` + `key` + `lambda` | `max(particles, key=lambda p: p.p_best_fit)` | 按某个属性取最大元素 |
| 链式比较截断 | `max(lo, min(hi, x))` | 把值夹在区间内（clamp） |
| 多重赋值 | `w, c1, c2 = 0.6, 1.2, 1.2`、`dx, dy = ...` | 一行给多个变量赋值 |
| 嵌套字典推导式 | `{t: {a: 1.0 for a in agents} for t in task_types}` | 构造二维表 |
| 增强赋值 | `*= (1.0 - self.decay)`、`+= self.reinforce * quality` | 原地乘、加 |
| `for ... return` + 兜底返回 | `choose` 中的轮盘赌 | 循环中满足条件提前返回，循环结束后给默认值 |
| `dict.keys()` 转列表 | `list(AGENT_TASK_AFFINITY.keys())` | 字典保序，得到 `["coder", "mathematician", "writer"]` |
| 取模轮转 | `task_types[i % len(task_types)]` | 循环使用列表元素 |
| 返回元组 | `return rq_avg, aq_avg, router` | 多返回值，调用处解包 |
| `range` 步长 | `range(0, len(history), 5)` | 每 5 个取一个 |
| 字符串乘法 | `"#" * max(1, int(history[i] * 40))` | 画 ASCII 条形图 |
| f-string 格式符 | `{a:>14s}`、`{x:>14.3f}`、`{v:+.1f}%`、`{i:3d}` | 右对齐宽 14；3 位小数；强制显示正负号 |
| `str.join` + 生成器 | `" ".join(f"{a:>14s}" for a in router.agents)` | 拼接表头 |
| `math.cos`、`math.pi` | `math.cos(8 * math.pi * dx)` | 标准库数学函数 |

---

## 6. 运行结果解读

实际运行（Python 3，耗时约 0.06 秒）：

```text
LMPSO — 20 particles, 30 iterations, 2D parameter space
  iter   0  g_best=0.9601  ######################################
  iter   5  g_best=1.0054  ########################################
  iter  10  g_best=1.0094  ########################################
  ...
  iter  30  g_best=1.0094  ########################################
  final g_best=1.0094 (optimum = 1.0000 at (0.72, 0.40))   ← 声称的最优值是错的

AMRO-S — 200 tasks routed across 3 agents × 4 task-types
  random routing avg quality: 0.498     ← 理论值约 0.502
  ACO routing    avg quality: 0.651     ← oracle 上限约 0.831
  improvement: +30.7%

  final pheromone table (after 200 tasks):
  task_type             coder  mathematician         writer
  code                  2.756          0.077          0.077
  math                  0.088          2.823          0.077
  writing               0.077          0.077          2.507
  planning              0.077          0.077          0.575
```

逐项解读：

- **PSO 第 10 轮就到 1.0094 并停住**：这是 3.1 所说的真实最大值（≈ 1.00945），而不是"超过最优"。说明 PSO 确实找到了全局最优，只是代码的注释和打印把最优点写错了。初始值 0.9601 已经很高，是因为 20 个点撒在一个很小的方格里。
- **ACO +30.7%**：在讲义预期的"~30–40%"范围内。用 100 个种子平均，默认设置的 ACO 质量约 0.675，后 100 个任务中选中最优 agent 的比例约 0.80。
- **信息素表就是"可解释的路由证据"**：code、math、writing 三行都已明显收敛到正确 agent；planning 行 writer 只有 0.575，因为 writer 在 planning 上只有一半运行能过 0.6 的门，学习信号弱。
- **0.077 与 0.088**：0.077 = 0.95^50（从未被强化）；0.088 说明 coder 在 math 上早期偶尔过过门（coder 的 math 质量范围 [0.35, 0.65]）。
- **补充实验**（临时脚本，不修改原文件）：
  - 种群规模（讲义练习 1，50 个种子平均，到达真实最优 0.002 以内的平均轮数）：5 粒子 11.3 轮（50 次中 49 次到达），10 粒子 6.2 轮，20 粒子 4.3 轮，50 粒子 2.7 轮——轮数随规模下降，但总评估次数（粒子数 × 轮数）在 20 以上不再划算；
  - 修复 fitness 符号后，g_best 从 0.999954 收敛到 1.000000，最优点回到 (0.72, 0.40)。

---

## 7. 动手改一改

1. **修 fitness**：把 `- ripple` 改成 `+ ripple - 0.16`，确认最优值为 1、位置为 (0.72, 0.40)；再把 `main` 中写死的"optimum = 1.0000"改为由网格搜索算出的值。
2. **种群规模实验**（讲义练习 1）：对 5、10、20、50 粒子各跑 50 个种子，同时统计"到达最优所需轮数"和"所需评估次数"，找出评估次数最少的规模。
3. **经典 PSO 写法**：把 `r1, r2` 移进 `for d` 循环；加 `v_max = 0.2` 速度截断；在 10 维版本的 fitness 上比较两种写法。
4. **漂移实验**（讲义练习 2）：第 30 轮后把峰值中心移到 (0.3, 0.7)，观察 g_best 是否还停在旧位置；比较"重置所有 p_best 与 g_best"与"不重置"两种策略。
5. **ACO 质量门与下限**（讲义练习 3）：对阈值 0、0.6、0.7、0.85 做对比（参考测验 Q11）；再给 `deposit` 加 τ_min 下限，做测验 Q12 的漂移实验。
6. **异步沉积**（讲义练习 5）：给 `simulate_task` 加一个模拟延迟，把 `deposit` 放到 `queue.Queue` + 后台线程中，比较路由请求的平均延迟与学习速度。

---

## 8. 常见坑

- **相信注释而不验证最优点**：本代码的"optimum = 1.0000 at (0.72, 0.40)"是错的；用网格搜索或解析求导验证一下就能发现。
- **忘记复制列表**：`p_best = x`（不复制）会让个体最优随着位置一起变，PSO 退化成无记忆的随机游走。
- **惯性 w ≥ 1**：速度不会衰减，粒子在边界间来回乱飞，不收敛。
- **信息素没有下限**：早期运气差的 agent 被永久"打入冷宫"，分布漂移后恢复很慢。
- **统一的绝对质量阈值**：难任务类型的最优 agent 也过不了门，这一行退化为随机路由。
- **把 PSO 用在离散组合空间**：讲义建议此时改用遗传算法；把离散选项强行映射成连续坐标再取整，常常效果很差。
- **只看"相对随机提升 30%"**：还要和 oracle 上限（约 0.83）比，才知道还有多少改进空间。
