# 测验 · 面向 LLMs 的 Swarm 优化（PSO、ACO）（Swarm Optimization for LLMs (PSO, ACO)）

> **阶段 16 · 多智能体与集群 · 第 19 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | PSO（Particle Swarm Optimization，Kennedy & Eberhart 1995） | `v ← w·v + c1·r1·(p_best − x) + c2·r2·(g_best − x)`，`x ← x + v`；w 是惯性，c1 是认知（个体经验），c2 是社会（群体经验） |
| 2 | ACO（Ant Colony Optimization，Dorigo 1992） | 按信息素（pheromone）强度加权选择路径；好的解按质量沉积信息素；信息素随时间蒸发（decay） |
| 3 | LMPSO（arXiv:2504.09247） | 粒子是候选输出，"速度"是一段 prompt（描述如何朝 p_best/g_best 修改），由 LLM 生成新候选；适合可解析、可自动评分的结构化输出 |
| 4 | Model Swarms（arXiv:2410.11163） | 把每个专家 LLM（参数，如 LoRA 增量）当作粒子，在参数子空间做 PSO；讲义："9 个数据集上比 12 个基线平均提升 13.3%，每轮只用 200 个样本" |
| 5 | AMRO-S（arXiv:2603.12933） | ACO 式多 agent 路由：task-type × agent 信息素矩阵；可解释的路由证据；quality-gated 异步更新把推理与学习解耦；讲义："4.7x speedup" |
| 6 | Quality gate（质量门） | 只有质量达标的运行才沉积信息素，否则"快但错"的 agent 会积累信息素并锁死在坏路由上 |
| 7 | 适用边界 | PSO：连续/可映射到连续的空间、评估便宜自动、种群 10–30；ACO：路由/路径选择、任务类型重复出现、需要可解释证据；都不适用：需要人工评审的 fitness、PSO 覆盖不了的离散组合空间（改用 GA）、严格实时 |
| 8 | 为什么仍有用 | 只需要一个 evaluator（打分函数），不需要可微信号；对离散 prompt、路由决策这类不可微对象门槛低 |
| 9 | 成本与稳定性 | 成本 = 粒子数 × 迭代数 × 单次评估成本（20 × 50 × $0.02 ≈ $20）；decay/惯性控制探索—利用；分布漂移（catastrophic drift）时旧 p_best 与信息素会过时，需要重置 |
| 10 | 本节代码的关键事实 | fitness 的 ripple 符号写反，(0.72, 0.40) 处只有 0.84，真实最大值约 1.0094 位于中心周围 4 个对称点；ACO 路由比随机提升 +30.7%，但离"总选最优 agent"的上限（约 0.83）仍有距离 |

### 核心技能（能动手做到）

- [ ] 手算一步 PSO 的速度与位置更新（含越界截断），说清 w、c1、c2 各自的作用
- [ ] 读懂 `PheromoneRouter` 的轮盘赌选择、按任务类型蒸发和带质量门的沉积，并推算"从未被强化的信息素最终值"（0.95^50 ≈ 0.077）
- [ ] 发现并修复 fitness 函数中 ripple 的符号错误，让最优点真正位于 (0.72, 0.40) 且最大值为 1
- [ ] 设计 quality gate 阈值实验，解释阈值过低和过高各自的失败方式
- [ ] 为 PSO/ACO 方案估算 LLM 调用预算，并设计分布漂移时的重置/下限（pheromone floor）策略
- [ ] 根据问题特征（搜索空间、fitness 来源、预算）在 PSO、ACO、GA、RL/DPO、手工调参之间做选择

---

## 二、基础自测（选择题）

**Q1.** PSO 速度更新公式 `v ← w·v + c1·r1·(p_best − x) + c2·r2·(g_best − x)` 中，体现"向整个群体学习"的是哪一项？

- A. `w·v`
- B. `c1·r1·(p_best − x)`
- C. `c2·r2·(g_best − x)`
- D. `x ← x + v`

**Q2.** 在 LMPSO 中，"速度（velocity）"对应的是：

- A. 一段 prompt，描述如何把当前输出朝个体最优/全局最优修改，由 LLM 据此生成下一个候选
- B. LLM 的 temperature 参数
- C. 模型权重的梯度
- D. 每个粒子每秒生成的 token 数

**Q3.** 关于 Model Swarms（arXiv:2410.11163），讲义中正确的描述是：

- A. 它在 prompt 字符串上做 PSO，速度是自然语言指令
- B. 它用 ACO 在专家模型之间做路由
- C. 它需要对专家模型做完整的反向传播
- D. 每个粒子是一个专家 LLM（参数），在共享的低维参数子空间上做无梯度更新；9 个数据集上平均比 12 个基线高 13.3%

**Q4.** AMRO-S 强调的 quality-gated 更新，主要是为了防止：

- A. 信息素矩阵占用过多内存
- B. "快但错"的 agent 不断积累信息素，系统锁死在坏路由上
- C. 推理速度过快
- D. 不同任务类型之间互相干扰

**Q5.** 每次 LLM 评估约 $0.02，跑一个 20 粒子、50 次迭代的 PSO，评估费用约为：

- A. $20
- B. $2
- C. $200
- D. $1,000

**Q6.** 下列哪个场景**最不适合**用 PSO 或 ACO？

- A. 在 [0, 1]² 上调两个连续的生成参数，fitness 由自动测试给出
- B. 同类任务反复出现，需要可解释地把任务分给多个 agent
- C. 调 LoRA 增量这种低维连续参数
- D. 每个候选都需要人工评审才能打分

**Q7.** 本节 `PheromoneRouter` 的 `decay = 0.05`，且只在**该任务类型被路由时**对这一行蒸发。200 个任务按 4 种类型轮流出现，一个从未被强化的 (task_type, agent) 信息素最终约为：

- A. 0.000
- B. 0.077
- C. 0.358
- D. 0.950

**Q8.** 代码中 `fitness` 的 docstring 说"narrow peak at (0.72, 0.40)"，`main` 也打印"optimum = 1.0000 at (0.72, 0.40)"。实际上：

- A. (0.72, 0.40) 处 fitness 为 1.0，是全局最大值
- B. (0.72, 0.40) 处 fitness 为 0，函数在那里被截断
- C. (0.72, 0.40) 处 fitness 只有 0.84，真实最大值约 1.0094，位于中心周围的 4 个对称点
- D. fitness 没有最大值，PSO 会发散

---

## 三、动手 / 代码题

**Q9.** 阅读 fitness 函数：

```python
def fitness(x: list[float]) -> float:
    cx, cy = 0.72, 0.40
    dx, dy = x[0] - cx, x[1] - cy
    dist2 = dx * dx + dy * dy
    ripple = 0.08 * (math.cos(8 * math.pi * dx) + math.cos(8 * math.pi * dy))
    return max(0.0, 1.0 - 6.0 * dist2 - ripple)
```

1. 计算 (0.72, 0.40) 处的值；解释为什么 PSO 最终输出 `g_best=1.0094`，比"optimum = 1.0000"还高。
2. 真实最大值大约在哪里？（提示：沿一个维度最大化 `−6d² − 0.08·cos(8πd)`。）
3. 修改一行，使最大值恰好为 1 且位于 (0.72, 0.40)。

**Q10.** 手算一步 PSO（`w = 0.6, c1 = c2 = 1.2`，位置截断到 [0, 1]）：

- `x = (0.50, 0.50)`，`v = (0.10, −0.05)`
- `p_best = (0.60, 0.40)`，`g_best = (0.82, 0.50)`
- 本代码对每个粒子只抽一次 `r1 = 0.5, r2 = 0.25`，两个维度共用

求更新后的 `v` 与 `x`。再指出：本代码"每个粒子共用一组 r1、r2"与经典 PSO 有何不同？会带来什么影响？

**Q11.** 讲义练习 3 要求"加一个 quality gate，阈值 0.7"。实际上代码已有阈值 0.6 的质量门。对不同阈值各跑 100 个种子（200 个任务）的平均结果：

| 阈值 | 随机路由质量 | ACO 路由质量 | 前 100 个任务选中最优 agent 的比例 | 后 100 个任务选中最优 agent 的比例 |
|------|-----------|-----------|--------------------------|--------------------------|
| 0.0（无门） | 0.501 | 0.618 | 0.42 | 0.62 |
| 0.6（默认） | 0.501 | 0.675 | 0.50 | 0.80 |
| 0.7 | 0.501 | 0.673 | 0.49 | 0.78 |
| 0.85 | 0.501 | 0.649 | 0.45 | 0.70 |

1. 为什么无门（阈值 0）收敛更慢？
2. 为什么阈值 0.85 又变差了？请具体分析 `planning` 这一行。（亲和度：planning 上 coder 0.4、mathematician 0.5、writer 0.6，质量噪声为 ±0.15 均匀分布。）
3. 若每次都选最优 agent，期望质量约 0.83。ACO 的 0.65–0.68 与它的差距来自哪里？

**Q12.** 讲义练习 2 讨论"catastrophic drift"。在 ACO 路由上做实验：先跑 200 个任务，然后把 coder 与 writer 的能力对调，再跑 200 个任务，每 50 个任务统计一次"选中当前最优 agent"的比例（100 个种子平均）：

```text
无下限      : [0.40, 0.59, 0.74, 0.86 | 0.29, 0.36, 0.51, 0.64]
下限 τ_min=0.3: [0.40, 0.59, 0.68, 0.73 | 0.35, 0.48, 0.60, 0.67]
```

（`|` 处发生漂移；"下限"指每次沉积后把该行信息素截断到不低于 0.3。）

1. 写出加入信息素下限的代码（改 `deposit` 即可）。
2. 解释这组数字体现的探索—利用权衡。
3. 讲义 Ship It 还给了哪种应对漂移的办法？

---

## 四、面试高频题

**Q13.**（基础必考）讲一下 PSO 和 ACO 的核心更新规则，并分别说明它们适合解决哪类问题。

**Q14.**（原理深挖）既然 LLM 的 prompt 是离散字符串，PSO 是连续优化算法，LMPSO 是如何把两者接起来的？这种做法丢掉了什么、保留了什么？

**Q15.**（工程实践）你要用 ACO 思路做一个多 agent 路由器上线，有哪些关键工程设计？

**Q16.**（场景设计）团队有一个 prompt 在评测集上得分 62%，想用 swarm 方法优化。请给出完整方案，包括搜索空间、fitness、种群规模、预算和停止条件，并说明什么情况下你会劝他们不要用 swarm。

**Q17.**（追问型）ACO 路由和 multi-armed bandit（如 UCB、Thompson sampling）有什么异同？如果面试官追问"为什么不直接用 bandit"，你怎么答？

---

## 五、参考答案与解析

### Q1 — 答案：C

`c2·r2·(g_best − x)` 把粒子拉向**全群体**目前找到的最好位置，是"社会"项。
- A 是惯性项，保持原来的运动方向；
- B 是"认知"项，拉向粒子自己的历史最优；
- D 是位置更新，不是速度中的一项。

### Q2 — 答案：A

讲义："Velocity is a *prompt* that describes how to modify the current output toward the personal/global best. The LLM generates the new output from the velocity prompt." 惯性对应"make small incremental changes"这样的提示。
- B：本节代码把 temperature 当作被优化的**位置**坐标之一，不是速度；
- C：LMPSO 是无梯度方法；
- D：与算法无关。

### Q3 — 答案：D

讲义："Each 'particle' is an expert LLM (parameters)... Reported: 13.3% average gain over 12 baselines on 9 datasets, with just 200 instances per iteration." 关键洞见是专家模型本来就在一个共享的低维参数流形（adapter、LoRA 增量）附近。
- A 是 LMPSO 的做法；
- B 是 AMRO-S；
- C 与"gradient-free update"矛盾。

### Q4 — 答案：B

讲义："without it, fast-but-wrong agents accrue pheromone, and the system locks in on bad routes." 质量门让信息素只在质量检查通过后更新，同时允许推理路径不等待学习（异步更新）。A、C、D 都不是讲义给出的理由。

### Q5 — 答案：A

`20 × 50 × $0.02 = $20`，与讲义"a 20-particle PSO running 50 iterations costs ~$20"一致。严格来说还要加上初始化时的 20 次评估（本代码 20 粒子 30 轮共评估 `20 + 20×30 = 620` 次）。B 少了一个数量级；C、D 是把数字乘错的结果。

### Q6 — 答案：D

讲义 "Do not use either when: Fitness requires human review (too expensive per iteration)"。
- A 正是 PSO 的典型场景（连续、自动评分）；
- B 正是 ACO 的典型场景（重复出现的路由 + 可解释）；
- C 是 Model Swarms 的场景。

### Q7 — 答案：B

200 个任务按 `i % 4` 轮流，每种类型被路由 50 次。每次路由都对该行所有 agent 乘 `(1 − 0.05)`，从未被强化的条目为 `1.0 × 0.95^50 ≈ 0.0769`。实际运行的信息素表里，大量条目正是 `0.077`。
- A：乘法衰减不会到 0；
- C 是 `0.95^20`；
- D 是只蒸发一次。

注意：信息素与"时间"无关，只与该类型被路由的次数有关；没有"下限"，所以长期不被选中的 agent 几乎再也选不中（见 Q12）。

### Q8 — 答案：C

中心处 `dx = dy = 0`，`ripple = 0.08 × (1 + 1) = 0.16`，`fitness = 1 − 0 − 0.16 = 0.84`。因为 ripple 是**减去**的，中心反而是一个局部凹陷；真实最大值约 1.0094，位于 `(0.72 ± 0.0997, 0.40 ± 0.0997)` 四个点附近（网格搜索得到 (0.6205, 0.3005) 等）。默认运行最终的 g_best 位置是 `(0.8197, 0.4996)`，正是其中之一。
- A 是代码注释的说法，与实际不符；
- B 错：0.84 远大于截断阈值 0；
- D 错：函数有界。

### Q9 — 参考答案

1. 中心处 `1 − 0 − 0.16 = 0.84`。ripple 的取值范围是 `[−0.16, 0.16]`，被减去后，在 `cos(8π·d) = −1` 附近反而会**加** 0.08；这抵消了一部分距离惩罚，所以最大值超过 1。
2. 单维最大化 `g(d) = −6d² − 0.08·cos(8πd)`：数值求解得 `d ≈ ±0.0997`，`g ≈ 0.004724`。两个维度独立，因此最大值 `1 + 2 × 0.004724 ≈ 1.00945`，与输出的 `1.0094` 一致，位于 `(0.62, 0.30)`、`(0.62, 0.50)`、`(0.82, 0.30)`、`(0.82, 0.50)` 附近。
3. 修复（让 ripple 在中心处达到最大，并减去它的最大值 0.16 做归一化）：

```python
    return max(0.0, 1.0 - 6.0 * dist2 + ripple - 0.16)
```

因为 `ripple ≤ 0.16`，`−6·dist2 + ripple − 0.16 ≤ 0`，只有在中心取等号，最大值恰为 1。实际验证：修复后默认种子的 g_best 历史为 `0.999954 → … → 1.000000`。顺带说明：默认种子下初始 20 个粒子里已有一个离中心很近，所以"收敛过程"在这个演示里并不明显；讲义说的"from random to near-optimal"在原代码中也只是从 0.9601 到 1.0094。

### Q10 — 参考答案

维度 0：
- `cognitive = 1.2 × 0.5 × (0.60 − 0.50) = 0.06`
- `social = 1.2 × 0.25 × (0.82 − 0.50) = 0.096`
- `v₀ = 0.6 × 0.10 + 0.06 + 0.096 = 0.216`，`x₀ = 0.50 + 0.216 = 0.716`

维度 1：
- `cognitive = 1.2 × 0.5 × (0.40 − 0.50) = −0.06`
- `social = 1.2 × 0.25 × (0.50 − 0.50) = 0`
- `v₁ = 0.6 × (−0.05) − 0.06 + 0 = −0.09`，`x₁ = 0.50 − 0.09 = 0.41`

结果：`v = (0.216, −0.09)`，`x = (0.716, 0.41)`，都在 [0, 1] 内，不需要截断。

与经典 PSO 的差异：经典写法通常对**每个维度**独立抽取 r1、r2（`r1 = rng.random()` 放进 `for d` 循环里）。共用一组随机数时，认知/社会两项在各维度上按同一比例缩放，粒子的运动方向被限制在 `p_best − x` 与 `g_best − x` 张成的平面内的固定比例组合上，搜索的"方向多样性"降低；在高维问题上更容易早熟收敛。本例只有 2 维，影响很小。另外，代码只截断了位置，没有截断速度、也没有在撞墙时把速度清零，粒子可能反复贴在边界上。

### Q11 — 参考答案

1. **无门**：任何一次运行都会沉积 `0.2 × quality`，差 agent（质量 0.2–0.5）也会得到不少信息素，好坏 agent 之间的差距拉开得慢，选中最优 agent 的比例在后 100 个任务中只有 0.62。
2. **阈值 0.85**：planning 上最好的 writer 质量范围是 `0.6 ± 0.15 = [0.45, 0.75]`，**永远过不了 0.85 的门**；coder（[0.25, 0.55]）和 mathematician（[0.35, 0.65]）也过不了。于是 planning 行只有蒸发、没有沉积，三个 agent 同比例衰减、相对比例永远是 1:1:1，路由在这一行退化成随机。阈值 0.6 时，writer 通过的概率约 50%，mathematician 约 16.7%，coder 为 0，planning 行仍能学到 writer。结论：**门槛要相对于各任务类型的可达质量来设定**，统一的绝对阈值会让"天然更难"的任务类型永远学不到。
3. 与上限 0.83 的差距来自**学习成本**（前期探索阶段在大量选择次优 agent）和**持续探索**（轮盘赌按比例选择，即使收敛后仍有一定概率选到次优者）；此外 planning 行即使学会也只有 0.6 的期望质量。随机路由的理论期望约 0.50（12 个亲和度的平均，考虑截断后约 0.502），与实测 0.501 吻合。

### Q12 — 参考答案

1. 加下限（类似 MAX-MIN Ant System 的 τ_min）：

```python
    def deposit(self, task_type: str, agent: str, quality: float, floor: float = 0.3) -> None:
        row = self.pheromones[task_type]
        for a in self.agents:
            row[a] *= (1.0 - self.decay)
        if quality >= self.quality_threshold:
            row[agent] += self.reinforce * quality
        for a in self.agents:
            row[a] = max(floor, row[a])
```

2. **探索—利用权衡**：
   - 无下限时，漂移前收敛更彻底（最后 50 个任务 0.86 vs 0.73），因为落选者的信息素衰减到约 0.077，几乎不再被选中；但漂移后恢复更慢（第一个窗口 0.29 vs 0.35，第二个 0.36 vs 0.48）。
   - 有下限时，始终保留一定的探索概率，漂移前的"利用"打了折扣，但漂移后能更快重新发现新最优。
   - 这就是讲义所说"too fast decay → forget solutions; too slow → stuck on early local optima"的另一个侧面：没有下限的信息素会把"记忆"变成"偏见"。
3. 讲义："Reset decay on distribution shift. When your eval distribution changes, aged pheromones are stale; reset or double the decay rate temporarily." 此外还要监控 best-fitness/信息素的稳定性，以便发现漂移。

### Q13 — 参考回答要点

- **PSO**：种群中每个粒子有位置和速度；每轮 `v ← w·v + c1·r1·(p_best − x) + c2·r2·(g_best − x)`，`x ← x + v`，评估后更新 p_best/g_best。w 大偏探索，c2 大偏向群体（收敛快但易早熟）。适合连续或可嵌入连续空间的黑盒优化（生成参数、LoRA 增量、prompt embedding）。
- **ACO**：在图上，按信息素（常再乘启发式）概率选择下一步；完成后按解的质量沉积信息素；全体蒸发。适合路径选择、路由、组合优化中的"重复决策"问题。
- **共同点**：只需要 evaluator、无梯度、基于种群/群体记忆。
- 加分点：说出 AMRO-S 用 task-type × agent 矩阵把 ACO 用于 agent 路由；说出 PSO 种群 10–30 的经验值及其成本含义。

### Q14 — 参考回答要点

- **连接方式**：把粒子定义为候选输出（如数学表达式、程序），把"速度"定义为一段描述修改方向的 prompt（参考 p_best 与 g_best），让 LLM 充当"位置更新算子"生成新候选；惯性对应"小步修改"之类的指令。fitness 由自动评估（运行测试、计算表达式）给出。
- **保留了什么**：种群、个体最优/全局最优的记忆、"向好解靠拢"的社会学习结构、无梯度。
- **丢掉了什么**：数值速度的可加性和可控步长（prompt 的"步长"不精确）；收敛性分析；每步成本从一次函数计算变成一次 LLM 调用。本节代码只在 2 维数值空间上跑经典 PSO，完全没有模拟"速度即 prompt"（讲义练习 4 正是让你比较二者）。
- **适用条件**：输出可解析、fitness 自动、种群小（讲义 10–30）。
- 常见误区：以为 LMPSO 是在 prompt 的 embedding 上做连续 PSO。

### Q15 — 参考回答要点

- **状态设计**：`task_type × agent` 信息素矩阵，持久化存储，可审计（讲义"interpretable routing evidence"）。
- **选择策略**：按信息素比例的轮盘赌，或 softmax/ε-greedy；设置信息素**下限/上限**，防止早熟锁死（见 Q12）。
- **质量门**：只有通过质量检查的运行才沉积；阈值按任务类型分别设定（见 Q11 的 planning 行）。
- **异步更新**：推理快速路径只读信息素，评估与沉积放到后台队列，避免评估延迟拖慢请求（AMRO-S 的解耦思想，讲义练习 5）。
- **漂移处理**：监控各行的分布稳定性，发生分布变化时重置或临时加倍 decay。
- **冷启动**：均匀初始化 + 预热任务（技能文件示例为 200 个预热任务）。
- **可观测性**：每轮记录信息素表、路由分布和质量；按 agent 统计质量与延迟。

### Q16 — 参考回答要点

- **先确定 fitness**：在固定评测集上自动打分（准确率/通过率），LLM judge 需要校准；没有自动 fitness 就先建 evaluator（技能文件拒绝规则）。
- **搜索空间**：
  - 连续部分（temperature、top_p、少样本数量等）→ PSO，种群 10–20；
  - prompt 文本本身 → LMPSO 式（LLM 作为变异/更新算子）或遗传算法（离散组合空间，讲义建议用 GA）。
- **预算**：`粒子数 × 迭代数 × 每次评估成本`，而每次评估 = 评测集大小 × 单次调用成本，往往远大于讲义的 $0.02；先在小评测子集上跑，再在全集上验证最佳候选。
- **停止条件**：g_best 连续若干轮无提升、达到预算上限、或在保留集上提升不显著。
- **防过拟合**：评测集分成优化集与保留集，最终只报告保留集分数。
- **劝退场景**：fitness 需要人工评审；预算很小（技能文件：低于 $100 时建议手工调参 + 缓存）；分布每天变化（改用在线学习/bandit）。

### Q17 — 参考回答要点

- **相同点**：都在"多个选项（agent）里反复选择，并根据回报更新偏好"；ACO 路由的每一行本质上就是一个按回报加权的多臂老虎机。
- **不同点**：
  - bandit 有明确的探索—利用理论（UCB 置信上界、Thompson 后验采样），有 regret 保证；ACO 的蒸发、沉积量、质量门是启发式参数，没有理论保证；
  - ACO 的蒸发天然适合非平稳环境（旧证据会衰减），标准 UCB 则需要滑动窗口/折扣版本；
  - ACO 的信息素表直接可解释，便于审计；
  - ACO 可扩展到多步路径（图上的序列决策），bandit 通常是一步决策。
- **怎么回答"为什么不用 bandit"**：对于单步路由，bandit（如 Thompson sampling + 折扣）常常是更有理论依据的选择，值得作为基线；ACO 的优势在于多步路径、可解释性和团队熟悉度。讲义技能文件也提到"分布每天变化时推荐在线学习或 bandit"。
- 加分点：指出本节 ACO 没有下限导致的"锁死"问题，与 bandit 中探索不足导致的线性 regret 是同一个现象。

---

## 六、关联知识点

### 前置知识
- [阶段 16 · 09 并行、Swarm 与网络化架构](../../09-parallel-swarm-networks/docs/zh.md)：讲义列出的先修课，swarm 架构的基本形态。
- [阶段 16 · 14 面向 Agents 的共识与拜占庭容错](../../14-consensus-and-bft/docs/zh.md)：讲义列出的先修课，群体如何聚合信息。
- [阶段 01 · 08 优化](../../../01-math-foundations/08-optimization/docs/zh.md)：梯度方法与无梯度方法的对比基础。
- [阶段 14 · 11 结合 HTN 与演化搜索的 Planning](../../../14-agent-engineering/11-planning-htn-and-evolutionary/docs/zh.md)：另一类基于种群的无梯度搜索。

### 本节被哪些后续内容用到
- [阶段 16 · 21 Agent 经济体系、Token 激励与声誉](../../21-agent-economies/docs/zh.md)：声誉分数与信息素一样，是"按历史质量加权选择 agent"的机制。
- [阶段 16 · 22 生产扩展：队列、Checkpoints 与持久性](../../22-production-scaling-queues-checkpoints/docs/zh.md)：异步更新、队列化评估的生产实现。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../../17-infrastructure-and-production/16-model-routing/docs/zh.md)：生产中的路由策略，与 ACO 路由思想相通。
- [阶段 15 · 03 AlphaEvolve：演化式 Coding Agents](../../../15-autonomous-systems/03-alphaevolve-evolutionary-coding/docs/zh.md)：LLM 作为变异算子的演化搜索，与 LMPSO 思路相近。

### 延伸关键词
`PSO` · `inertia weight` · `cognitive / social coefficient` · `ACO` · `pheromone evaporation` · `MAX-MIN Ant System` · `LMPSO` · `Model Swarms` · `AMRO-S` · `quality gate` · `catastrophic drift` · `multi-armed bandit` · `Thompson sampling` · `genetic algorithm` · `black-box optimization`
