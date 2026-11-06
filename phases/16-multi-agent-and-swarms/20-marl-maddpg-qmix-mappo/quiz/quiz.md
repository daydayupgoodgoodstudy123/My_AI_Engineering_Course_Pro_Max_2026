# 测验 · 多智能体强化学习（MARL）：MADDPG、QMIX、MAPPO（MARL — MADDPG, QMIX, MAPPO）

> **阶段 16 · 多智能体与集群 · 第 20 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要 MARL 专门算法 | 独立 RL：每个 agent 看到的环境因他人学习而非平稳；集中式 RL：一个控制器管全部，不可扩展且违反执行约束 |
| 2 | CTDE | Centralized Training, Decentralized Execution：训练时用全局信息，部署时每个 agent 只看自己的观察 `o_i` |
| 3 | MADDPG（Lowe et al., NeurIPS 2017） | 每个 agent 一个 actor `μ_i(o_i)` + 一个能看全部观察和动作的 critic `Q_i(x, a_1..a_n)`；可用于合作、竞争、混合场景；critic 输入随 N 增长，讲义："没有近似时难以扩展到约 10 个 agent 以上" |
| 4 | QMIX（Rashid et al., ICML 2018） | 只适用于合作；`Q_tot = f(Q_1..Q_n)` 且 `∂f/∂Q_i ≥ 0`，保证 `argmax Q_tot` 可由各 agent 独立 `argmax Q_i` 得到；SMAC 上表现突出 |
| 5 | 单调性的局限 | 收益结构不能单调分解时（如一个 agent 为团队牺牲）QMIX 会失败；QTRAN、QPLEX 等扩展放宽了这一约束 |
| 6 | MAPPO（Yu et al., NeurIPS 2022） | PPO + 集中式 value function；在 particle-world、SMAC、Google Research Football、Hanabi 上以很少调参匹敌或超过 off-policy 方法；讲义："2026 年合作 MARL 的默认 baseline" |
| 7 | 非平稳性的三种应对 | MADDPG：critic 看全部动作；QMIX：在联合 Q 空间学习；MAPPO：集中式 value 抑制他人策略变化带来的方差 |
| 8 | 与 LLM agent 的关系 | router 训练（MAPPO 适合）、角色涌现（QMIX 式分解强制互补）、共享工具/预算下的多 agent 工具使用；但讲义："2026 年多数生产系统是用 prompt 写策略而不是训练策略" |
| 9 | CTDE 作为设计纪律 | 设计时假设全局可见，运行时强制每个 agent 只看 `o_i`；防止系统暗中依赖共享状态 |
| 10 | 本节代码的真实情况 | 环境是 **2 个 pellet**（讲义说 1 个）；三种"CTDE"实现共用同一个集中式分配函数，结果逐位相同（2.73 步），而且每一步执行都读取了双方位置，**并不是去中心化执行** |

### 核心技能（能动手做到）

- [ ] 用一句话分别说清 MADDPG、QMIX、MAPPO 的"训练时看什么、执行时看什么"
- [ ] 手算一个小例子，验证单调混合（`w ≥ 0`）下联合 argmax 等于各自 argmax，并构造一个加性分解失败的矩阵博弈
- [ ] 读出本节代码中 MADDPG/QMIX/MAPPO 三个函数为何结果完全相同，并指出 `_assigned_targets` 违反了 CTDE 的执行约束
- [ ] 区分"最小化总距离"和"最小化完成时间（makespan）"两种目标，找出分配函数次优的反例
- [ ] 用 BFS 求出本环境的真实最优步数，作为评估各策略的上限
- [ ] 根据任务属性（合作/竞争、动作空间、同构/异构、奖励稀疏度、数据量）选择 MARL 算法，或判断应该先用 prompt 级策略

---

## 二、基础自测（选择题）

**Q1.** 关于 CTDE，下列说法正确的是：

- A. 训练和执行时，每个 agent 都只能看自己的观察
- B. 训练时 critic 可以看到所有 agent 的观察和动作；部署时每个 agent 只用自己的观察驱动自己的 actor
- C. 训练时只有一个中央控制器，部署时也由它统一下发动作
- D. 训练时各 agent 互不可见，部署时共享全部状态

**Q2.** QMIX 要求混合函数对每个 `Q_i` 单调非减（`∂Q_tot/∂Q_i ≥ 0`），最直接的好处是：

- A. 让 QMIX 可以用于竞争性任务
- B. 让 critic 的输入维度不随 agent 数增长
- C. 让训练变成 on-policy，更稳定
- D. 保证联合动作的 `argmax Q_tot` 可以由每个 agent 独立地 `argmax Q_i` 得到，从而支持去中心化执行

**Q3.** 关于 MAPPO，讲义的结论是：

- A. 它是带集中式 value function 的 PPO；在多个基准上以很少的调参匹敌或超过 off-policy MARL，是 2026 年合作 MARL 的默认 baseline
- B. 它是 off-policy 方法，依赖经验回放
- C. 它只在 SMAC 上有效，在 Hanabi 上明显落后于 QMIX
- D. 它需要为每个环境精细调参才能稳定

**Q4.** MARL 中的"非平稳性（non-stationarity）"指的是：

- A. 奖励函数会随时间随机变化
- B. 环境的物理规则不固定
- C. 从单个 agent 的视角看，环境包含了其它正在学习的 agent，它们的策略在变，所以环境也在变
- D. 观察中带有噪声

**Q5.** 讲义指出的 MADDPG 主要失效模式是：

- A. 只能用于离散动作空间
- B. 只能用于纯合作任务
- C. 必须在部署时也使用集中式 critic
- D. 每个 critic 的输入包含所有 agent 的动作，随 agent 数增长，没有近似时难以扩展到约 10 个以上

**Q6.** 实际运行本节 `code/main.py`（500 个 episode，4×4 网格）的输出最接近：

- A. independent 3.21；MADDPG-style、QMIX-style、MAPPO-style 都是 2.73
- B. independent 约 6 步；三种 CTDE 变体约 3.5 步
- C. independent 2.73；三种 CTDE 变体 3.21
- D. 三种 CTDE 变体结果各不相同，MAPPO 最好

**Q7.** 上题中三种"CTDE"实现的结果逐位相同，根本原因是：

- A. 随机种子相同，巧合
- B. 三种算法在这个小网格上都已训练到收敛
- C. QMIX-style 与 MADDPG-style 都调用同一个 `_assigned_targets` 做集中式分配，MAPPO-style 直接 `return run_maddpg_style(...)`，三者是同一个脚本策略
- D. 三者都使用了单调混合网络

**Q8.** 按本节技能文件 `skill-marl-picker` 的建议，一个"合作与竞争并存、连续动作空间"的任务，在 MAPPO baseline 之外最该考虑的是：

- A. QMIX
- B. MADDPG
- C. 独立 Q-learning（IQL）
- D. 不用 baseline，直接上 QPLEX

---

## 三、动手 / 代码题

**Q9.** 阅读 MADDPG-style 的执行循环：

```python
def run_maddpg_style(env: Env, max_steps: int = 50) -> int:
    """Centralized critic assigns each agent a distinct pellet; each agent's
    actor moves toward its assigned target. Deploy-time only the actors run."""
    steps = 0
    while not env.done and steps < max_steps:
        t0, t1 = _assigned_targets(env)
        env.agent0 = step_toward(env.agent0, t0)
        env.agent1 = step_toward(env.agent1, t1)
        ...
```

1. docstring 说"Deploy-time only the actors run"。这段代码在每一步执行时用到了哪些信息？它符合 CTDE 的"去中心化执行"吗？
2. 写一个**真正只用本地信息**的执行策略：每个 agent 只知道自己的位置和 pellet 位置（不知道对方位置），但可以事先约定规则。
3. 已实测：这种"约定"策略在 4×4 上平均 3.154 步，6×6 上 4.548 步；集中式分配为 2.726 / 4.014；independent 为 3.212 / 4.654。这些数字说明了 CTDE 中"训练时的全局信息"到底应该起什么作用？

**Q10.** `_assigned_targets` 的分配规则是"最小化两个 agent 的曼哈顿距离之和"：

```python
    cost_pq = manhattan(env.agent0, p) + manhattan(env.agent1, q)
    cost_qp = manhattan(env.agent0, q) + manhattan(env.agent1, p)
    return (p, q) if cost_pq <= cost_qp else (q, p)
```

而任务的评价指标是"两个 pellet 都被收集所需的步数"。种子 58 的初始状态：agent0 在 (1,0)，agent1 在 (1,1)，pellet 在 (1,3) 和 (3,2)，`list(pellets_remaining)` 的顺序是 `[(3,2), (1,3)]`。

1. 计算两种分配的"距离和"与"完成时间"，说明代码会选哪种、结果是几步、最优是几步。
2. 这类目标错配在 500 个 episode 中出现了 13 次。用 BFS 求得的真实最优平均为 2.698 步。请修改分配函数，使其按完成时间（makespan）优先、距离和作为平局决胜。

**Q11.** 讲义与代码之间存在多处不一致。请至少找出 5 处（提示：环境设定、类名、预期输出、Env 的 docstring、Takeaways 的描述、未使用的函数），并说明哪一处对学习者的误导最大。另外，讲义练习 1 问"在 6×6 网格上 independent 与 MAPPO-style 的差距是变大还是变小"，实测 6×6 为 4.654 vs 4.014，请给出结论。

**Q12.** 值分解手算。

1. 两个 agent 各有两个动作，`Q_1 = [1, 3]`，`Q_2 = [2, 0]`。混合函数 `Q_tot = w1·Q_1(a1) + w2·Q_2(a2)`，`w1, w2 ≥ 0`。分别取 `(w1, w2) = (1, 1)、(0.5, 2)、(3, 0.1)`，联合 argmax 是什么？与各自 argmax 一致吗？
2. 矩阵博弈（行是 agent 1 的动作，列是 agent 2 的动作）：

```text
        a2=0   a2=1   a2=2
a1=0      8    -12    -12
a1=1    -12      0      0
a1=2    -12      0      0
```

用加性分解 `Q_tot = Q_1(a1) + Q_2(a2)`（VDN）在 9 个格子上做最小二乘拟合，求 `Q_1`、`Q_2` 和贪心联合动作，它的真实收益是多少？这说明了什么？

---

## 四、面试高频题

**Q13.**（基础必考）解释 CTDE。为什么独立学习和完全集中式控制都不理想？MADDPG 是如何实现 CTDE 的？

**Q14.**（原理深挖）QMIX 的单调性约束解决了什么问题、又牺牲了什么？举一个单调分解表达不了的协作场景。

**Q15.**（原理深挖）为什么 MAPPO 这样一个"简单"的 on-policy 方法能成为合作 MARL 的默认 baseline？on-policy 与 off-policy 在 MARL 中各有什么利弊？

**Q16.**（场景设计）你负责一个 LLM 多 agent 系统：一个 router 决定把用户请求交给检索、总结、写代码三个子 agent 中的哪一个。团队提议"用 MAPPO 训练 router"。你如何判断是否值得训练？如果要做，环境、观察、动作、奖励怎么定义？

**Q17.**（追问型）讲义说"CTDE 即使不训练也是有用的设计模式"。请结合本节代码的问题说明：一个号称 CTDE 的多 agent 系统，你会检查哪些地方来确认它真的做到了"去中心化执行"？在 LLM agent 系统中，非平稳性通常以什么形式出现？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："train with global information, deploy with local policies"；MADDPG 中"at deploy time, each agent only sees `o_i` and calls `mu_i(o_i)`"。
- A 是独立学习（independent RL）；
- C 是完全集中式控制，讲义指出它不可扩展且违反执行约束；
- D 把训练和执行颠倒了。

### Q2 — 答案：D

单调性保证：每个 `Q_i` 取最大时，`Q_tot` 也取最大，于是联合 argmax 可以分解为各自 argmax。讲义："That is exactly the decentralized execution property you need."
- A 错：QMIX 只适用于合作（技能文件也把"QMIX 用于混合合作-竞争"列为硬拒绝）；
- B 描述的是 MADDPG 的问题，与单调性无关；
- C 错：QMIX 是基于 Q-learning 的 off-policy 方法。

### Q3 — 答案：A

讲义："MAPPO matches or beats off-policy MARL methods on particle-world, SMAC, Google Research Football, Hanabi, MPE. Minimal hyperparameter tuning required. Stable training; reproducible across seeds." 以及"MAPPO is the default baseline for cooperative MARL"。
- B：PPO 是 on-policy；
- C、D 与讲义结论相反。

### Q4 — 答案：C

讲义："When multiple agents learn simultaneously, each agent's environment (which includes others' policies) is non-stationary. Classical single-agent RL proofs break." A、B、D 描述的是其它类型的不确定性，不是 MARL 特有的非平稳性。

### Q5 — 答案：D

讲义："critics grow with N agents (input includes all actions). Does not scale past ~10 agents without approximations."
- A 错：MADDPG 基于 DDPG，原本面向连续动作；
- B 错：讲义说它适用于合作、竞争和混合场景；
- C 错：部署时只运行 actor。

### Q6 — 答案：A

实际输出：

```text
  independent (no coord) avg_steps_to_goal = 3.21
  MADDPG-style (CTDE)  avg_steps_to_goal = 2.73
  QMIX-style (mono decomp) avg_steps_to_goal = 2.73
  MAPPO-style (centralized V) avg_steps_to_goal = 2.73
```

- B 是讲义"Expected output"的说法（independent ~6、CTDE ~3.5），与代码不符；
- C 把两组数字颠倒；
- D 错，三者完全相同（见 Q7）。

### Q7 — 答案：C

`run_qmix_style` 在剩 2 个 pellet 时调用 `_assigned_targets`，剩 1 个时让两者都去那一个——这与 `_assigned_targets` 在 1 个 pellet 时的返回值 `(pellets[0], pellets[0])` 完全一样；`run_mappo_style` 的函数体就是 `return run_maddpg_style(env, max_steps)`。所以三者是**同一个确定性脚本策略**，结果逐位相同不是"三种算法收敛到相似策略"的证据。
- A：与种子无关，换任何种子都相同；
- B：代码里没有任何训练；
- D：代码里没有任何 Q 值或混合网络。

### Q8 — 答案：B

技能文件："Switch to ... MADDPG when mixed (cooperative + competitive) + continuous actions"。
- A：QMIX 只适合合作，"Using QMIX for mixed cooperative-competitive tasks"是硬拒绝；
- C：IQL 没有处理非平稳性；
- D：技能文件要求首次实验先跑 MAPPO baseline，QPLEX 是单调约束过强时才考虑的扩展。

### Q9 — 参考答案

1. 每一步都调用 `_assigned_targets(env)`，它读取了 **agent0 和 agent1 两者的位置**和全部 pellet。也就是说执行时每个 agent 的目标依赖于对方的实时位置，这是**集中式执行**（一个看全局的调度器在每步分配任务），不符合 CTDE 的"部署时每个 agent 只看 `o_i`"。docstring 的说法与实现不符。

2. 一个只用本地信息 + 事先约定的策略（已实际运行）：

```python
def run_convention(env: Env, max_steps: int = 50) -> int:
    steps = 0
    while not env.done and steps < max_steps:
        rem = sorted(env.pellets_remaining)       # 双方都能看到 pellet，排序规则是事先约定的
        t0, t1 = rem[0], rem[-1]                   # agent0 取"最小"的 pellet，agent1 取"最大"的
        env.agent0 = step_toward(env.agent0, t0)   # 只用自己的位置
        env.agent1 = step_toward(env.agent1, t1)
        env.collect_if_on_pellet()
        steps += 1
    return steps
```

只剩一个 pellet 时 `rem[0] == rem[-1]`，两者都去那里。

3. 数字解读：

| 策略 | 执行时信息 | 4×4 | 6×6 |
|------|----------|-----|-----|
| independent（各自追最近） | 本地 | 3.212 | 4.654 |
| 约定（按坐标排序分工） | 本地 + 约定 | 3.154 | 4.548 |
| 集中式分配（代码中的"CTDE"） | 全局 | 2.726 | 4.014 |
| BFS 最优 | 全局 + 规划 | 2.698 | 3.944 |

约定策略消除了"抢同一个 pellet"，但分工与距离无关，所以只比 independent 好一点。集中式分配好得多，但它是用执行时的全局信息换来的。CTDE 的意义在于：**训练时**利用全局信息（集中式 critic/value 知道对方在哪、谁更近）去学习一个**只依赖本地观察**的策略，使去中心化策略尽量接近集中式的效果。这份代码只展示了"集中式的效果"，没有展示"如何把它蒸馏到本地策略"。

### Q10 — 参考答案

1. 距离：agent0→(1,3) = 3，agent0→(3,2) = 4；agent1→(1,3) = 2，agent1→(3,2) = 3。
   - 分配 A：agent0→(1,3)、agent1→(3,2)：距离和 3 + 3 = 6，完成时间 max(3, 3) = **3**；
   - 分配 B：agent0→(3,2)、agent1→(1,3)：距离和 4 + 2 = 6，完成时间 max(4, 2) = **4**。

   距离和打平。由于 `pellets[0] = (3,2)`，`cost_pq = 4 + 2 = 6 <= cost_qp = 3 + 3 = 6`，返回 `(p, q)`，即分配 B。实际轨迹：agent1 第 2 步收集 (1,3)，之后两个 agent 一起追 (3,2)，第 4 步才完成；最优是 3 步。平局决胜依赖集合迭代顺序，选错就多走一步。

2. 修正（完成时间优先，距离和决胜）：

```python
def _assigned_targets(env: Env):
    pellets = list(env.pellets_remaining)
    if len(pellets) == 1:
        return pellets[0], pellets[0]
    p, q = pellets
    a, b = env.agent0, env.agent1
    key_pq = (max(manhattan(a, p), manhattan(b, q)), manhattan(a, p) + manhattan(b, q))
    key_qp = (max(manhattan(a, q), manhattan(b, p)), manhattan(a, q) + manhattan(b, p))
    return (p, q) if key_pq <= key_qp else (q, p)
```

元组比较先比第一个元素（makespan），相等再比第二个（距离和）。实测修正后 4×4 平均 2.704 步（原 2.726，BFS 最优 2.698），6×6 为 3.96 步（原 4.014，最优 3.944）。剩下的一点差距来自"顺路经过另一个 pellet 也能收集"、走法的先后选择等只有全局搜索才能发现的情况。教训：**分配/奖励的目标函数必须与真实评价指标一致**，这正是讲义 Ship It 里"MARL 对奖励设计极其敏感"的一个小型例子。

### Q11 — 参考答案

不一致之处：

| # | 讲义 | 代码 |
|---|------|------|
| 1 | 环境只有 1 个 pellet，"任一 agent 到达即奖励 1 并结束" | 2 个 pellet，两个都被收集才结束 |
| 2 | 类 `IndependentAgents`、`MADDPGStyle`、`QMIXStyle`、`MAPPOStyle` | 只有函数 `run_independent` 等 |
| 3 | 预期：independent 约 6 步，CTDE 约 3.5 步，4×4 最优为 3 | 实测 3.21 与 2.73；BFS 最优平均 2.698 |
| 4 | "centralized critic computes a joint value; actor policies update from it" | 没有 critic、没有 value、没有任何更新 |
| 5 | `Env` docstring：步数代价、碰撞多付一步 | 碰撞代价没有实现 |
| 6 | Takeaways："only the closer agent moves per step" | 两个 agent 每步都移动；`move_or_wait` 定义了但从未调用 |
| 7 | "QMIX：每个 agent 选本地 Q 更高的 pellet" | QMIX-style 调用的是集中式分配，与 MADDPG-style 相同 |

误导最大的是第 1 条和第 7 条：在**单 pellet**的任务里，两个 agent 都冲向同一个 pellet 本来就是最优的，根本不存在"协调"问题；而三个"不同算法"共用一个函数，会让人误以为"三种算法在部署时收敛到相同策略"是被实验证实的结论。

6×6 结论：差距的**绝对值**从 3.212 − 2.726 = 0.486 步增加到 4.654 − 4.014 = 0.640 步（变大），但**相对值**从约 15.1% 降到约 13.8%（略降）。回答这类问题时要说明比较的是哪种口径。

### Q12 — 参考答案

1. 各自 argmax：agent 1 选动作 1（Q=3），agent 2 选动作 0（Q=2）。三组权重下实际计算的联合 argmax 都是 `(1, 0)`，与各自 argmax 一致。原因：`w ≥ 0` 时 `Q_tot` 对每个 `Q_i` 单调不减，每一项各自取最大，和就最大。若某个 `w < 0`，对应的 agent 应该选**最小** Q，分解就失效了——这就是 QMIX 要求单调性的原因。

2. 最小二乘拟合结果（已用 NumPy 计算）：`Q_1 = Q_2 = [−3.111, −1.778, −1.778]`，`Q_tot` 的最大值出现在 `a1 ∈ {1, 2}, a2 ∈ {1, 2}`（值 −3.556），贪心联合动作的真实收益是 **0**，而最优联合动作 `(0, 0)` 的收益是 **8**。原因：动作 0 在"对方不配合"时代价 −12，加性分解只能看到"动作 0 平均很差"，看不到"双方同时选 0 最好"这种**必须同时协调**的结构。这正是讲义所说"单调约束过于严格、有些任务的收益不能单调分解"，也是 QTRAN、QPLEX 等扩展要解决的问题。QMIX 的单调混合网络比纯加性（VDN）表达能力强，但同样受单调性约束。

### Q13 — 参考回答要点

- **独立学习的问题**：每个 agent 把其它 agent 当成环境的一部分，而其它 agent 在学习，环境非平稳，单 agent RL 的收敛保证失效。
- **完全集中式的问题**：联合动作空间随 agent 数指数增长，不可扩展；而且部署时往往没有全局通信/观察（讲义："violates execution constraints"）。
- **CTDE**：训练时利用全局信息降低方差、稳定学习；执行时每个 agent 只用本地观察。
- **MADDPG 的实现**：每个 agent 有 actor `μ_i(o_i)` 和 critic `Q_i(x, a_1, …, a_n)`；critic 用 TD 更新，actor 用确定性策略梯度 `∇θ μ_i(o_i) · ∇a_i Q_i` 更新；因为 critic 看到了所有人的动作，从它的视角环境是平稳的。部署时丢掉 critic，只跑 actor。
- 加分点：说出 MADDPG 可用于竞争与混合场景（每个 agent 有自己的 critic 和奖励），以及 critic 输入随 N 增长的扩展性问题。

### Q14 — 参考回答要点

- **解决的问题**：信用分配（credit assignment）+ 去中心化执行。团队只有一个全局奖励时，用混合网络把 `Q_tot` 分解到每个 agent 的 `Q_i`；单调性保证各 agent 独立贪心就能得到联合最优（讲义："argmax distributes cleanly"）。混合网络的权重可以由全局状态生成（训练时用全局信息），但执行时只需要 `Q_i`。
- **牺牲**：表达能力。只能表示"每个 agent 的 Q 越高，团队越好"的结构；需要"某个 agent 牺牲自己的局部收益换团队收益"或"必须同时选同一个动作才有回报"的任务无法表示（见 Q12 的矩阵博弈）。
- **为什么在 SMAC 上成功**：同构单位、局部观察、全局奖励，结构天然适合值分解（讲义）。
- **扩展**：QTRAN、QPLEX 放宽单调约束（讲义）。
- 常见误区：把 QMIX 用于竞争或混合场景。

### Q15 — 参考回答要点

- **MAPPO 是什么**：每个 agent 一个策略（常共享参数），value function 输入全局状态；用 PPO 的 clip 目标做策略更新。
- **为什么成为 baseline**（讲义 + Yu et al. 2022）：在 particle-world、SMAC、GRF、Hanabi、MPE 上匹敌或超过 MADDPG、QMIX 及其扩展；几乎不需要调参；跨种子稳定、可复现。社区此前低估了 on-policy MARL。
- **on-policy 的利弊**：样本效率较低（数据用完即弃），但不受经验回放中"他人旧策略"导致的数据过时影响，在非平稳的多 agent 环境里反而更稳；PPO 的 clip 限制了每次策略变化幅度，也间接降低了对他人的扰动。
- **off-policy 的利弊**：可复用经验、样本效率高；但回放池中的数据是在他人旧策略下产生的，非平稳性会让旧样本"变质"，训练更难稳定。
- 加分点：讲义 Ship It——"Start with MAPPO"，先复现 baseline 再追更复杂的方法；技能文件把"第一次实验不用 MAPPO"列为硬拒绝。

### Q16 — 参考回答要点

- **先判断是否值得训练**（讲义 + 技能文件）：需要同时具备 (a) 大量交互数据（技能文件建议至少约 1000 个 episode，否则用 prompt 级策略或监督微调）、(b) 清晰的奖励信号、(c) 训练基础设施投入意愿。否则先用 prompt 写 router 策略，或者用 bandit/规则路由。
- **如果要训练**：
  - **agent 与 CTDE**：router 是一个决策者，子 agent 也可以有"接受/转交"的策略；训练时 value function 看全局（完整对话、各子 agent 状态、历史成功率），执行时 router 只看请求特征与自己可见的上下文；
  - **观察**：请求 embedding、对话阶段、各子 agent 的负载与近期质量；
  - **动作**：选哪个子 agent（离散），可加"追问用户"等动作；
  - **奖励**：任务成功（自动评测或用户反馈）− 延迟/成本惩罚；警惕奖励投机（讲义："MARL is exquisitely sensitive to reward design"），做对抗测试；
  - **流程**：记录每个 agent 的观察与动作 → 离线训练 → 影子流量评估 → 灰度上线；每次实验 5–10 个种子。
- 加分点：说明 router 与子 agent 一起学习会带来非平稳性；把训练代码和执行代码分开，确保执行路径只看到 `o_i`。

### Q17 — 参考回答要点

- **检查清单**：
  - 每个 agent 的执行函数签名：输入是否只有 `o_i`？有没有偷偷读全局状态或其它 agent 的内部变量（本节 `_assigned_targets` 就在执行时读了双方位置）；
  - 是否有一个"调度器"每步给所有 agent 分配任务——如果有，那是集中式执行；
  - 训练代码与执行代码是否分离（讲义 Ship It）；
  - 断开 agent 间通信或屏蔽全局状态后，系统是否还能工作、性能下降多少；
  - 是否记录了每个 agent 的观察和动作，以便审计。
- **LLM 系统中的非平稳性**：讲义——"my agent worked last month, now that other agent upstream changed, mine misbehaves"。例如上游 agent 换了模型或 prompt，输出格式/风格变化，下游 agent 的 prompt 策略失效；工具 API 变更；共享预算被其它 agent 消耗。
- **应对**：显式的接口契约（结构化输出、schema 校验）、对上游变更做回归评测、版本固定；在有数据和奖励的情况下用 CTDE 训练（讲义："principled fix"），prompt 级修复更快但不持久。

---

## 六、关联知识点

### 前置知识
- [阶段 09 · 10 多Agent RL](../../../09-reinforcement-learning/10-multi-agent-rl/docs/zh.md)：多 agent RL 的基础概念，讲义列出的先修阶段。
- [阶段 09 · 07 Actor-Critic — A2C 和 A3C](../../../09-reinforcement-learning/07-actor-critic-a2c-a3c/docs/zh.md)：MADDPG 的 actor-critic 框架。
- [阶段 09 · 08 近端策略优化（PPO）](../../../09-reinforcement-learning/08-ppo/docs/zh.md)：MAPPO 的单 agent 基础。
- [阶段 09 · 05 深Q网络（DQN）](../../../09-reinforcement-learning/05-dqn/docs/zh.md)：QMIX 中每个 agent 的 Q 网络与 off-policy 学习。
- [阶段 16 · 09 并行、Swarm 与网络化架构](../../09-parallel-swarm-networks/docs/zh.md)：讲义列出的先修课。

### 本节被哪些后续内容用到
- [阶段 16 · 21 Agent 经济体系、Token 激励与声誉](../../21-agent-economies/docs/zh.md)：竞争/混合场景下的激励设计，与 MARL 的奖励设计问题相通。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../23-failure-modes-mast-groupthink/docs/zh.md)：多 agent 协调失败的分类。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../24-evaluation-coordination-benchmarks/docs/zh.md)：如何评测多 agent 协调。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../../17-infrastructure-and-production/16-model-routing/docs/zh.md)：router 训练的生产语境。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：讲义强调的奖励设计风险。

### 延伸关键词
`CTDE` · `MADDPG` · `QMIX` · `VDN` · `QTRAN` · `QPLEX` · `MAPPO` · `centralized critic` · `value decomposition` · `credit assignment` · `non-stationarity` · `on-policy / off-policy` · `SMAC` · `Hanabi` · `makespan` · `parameter sharing`
