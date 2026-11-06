# 测验 · 时序差分——Q-Learning 与 SARSA（Temporal Difference — Q-Learning & SARSA）

> **阶段 09 · 强化学习 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | TD(0) | `V(s) ← V(s) + α[r + γV(s') − V(s)]`：每走一步就更新，无需模型、无需完整回合 |
| 2 | TD 误差 | `δ = r + γV(s') − V(s)`，是 MC 中 `G_t − V(s_t)` 的在线版本 |
| 3 | 自举（bootstrapping） | 目标里用了当前估计 `V(s')`：带来偏差，但方差大幅下降 |
| 4 | Q-learning | 目标 `r + γ max_a' Q(s',a')`，off-policy，学的是 `Q*`，与行为策略无关 |
| 5 | SARSA | 目标 `r + γ Q(s',a')`，`a'` 是实际要执行的下一个动作，on-policy，学的是当前 ε-greedy 策略的 `Q^π` |
| 6 | 悬崖行走 | Q-learning 学到贴着悬崖的最短路线但探索时常掉崖；SARSA 把探索噪声算进价值，走更安全的远路 |
| 7 | Expected SARSA | 用 `Σ π(a'\|s') Q(s',a')` 代替采样的 `Q(s',a')`，方差更低 |
| 8 | n-step 与 TD(λ) | n=1 是 TD，n=∞ 是 MC；TD(λ) 按 `(1−λ)λ^{n−1}` 加权平均所有 n |
| 9 | 最大化偏差 | 对含噪估计取 max 会系统性高估；Double Q-learning 用两张表解耦"选择"与"评估" |
| 10 | 超参经验 | α 常取 0.05–0.3；ε 从高衰减到低；Q=0 对负奖励任务是乐观初始化 |

### 核心技能（能动手做到）

- [ ] 能手算一次 Q-learning / SARSA / Expected SARSA 的更新，并说清三者目标的差别
- [ ] 能从零实现表格型 Q-learning 和 SARSA，正确处理终止步（目标只有 `r`，不再自举）
- [ ] 能用解析的 `Q*` 检查学到的 Q 表，解释为什么 Q-learning 的 `max_a Q` 等于 `V*` 而 SARSA 的偏低
- [ ] 能搭建悬崖行走环境，复现"Q-learning 贴崖、SARSA 绕远"的经典结果
- [ ] 能说出"回合被步数上限截断"时该不该继续自举
- [ ] 能解释最大化偏差的来源，并写出 Double Q-learning 的更新

---

## 二、基础自测（选择题）

**Q1.** 相比 Monte Carlo，TD(0) 最核心的两个优势是：

- A. 无偏、不需要探索
- B. 每一步都能在线更新（不必等回合结束），且目标的方差更低
- C. 不需要奖励信号、不需要折扣因子
- D. 一定收敛到全局最优，且不需要调学习率

**Q2.** 已知 `Q(s,a) = -2`，执行后得到 `r = -1`，到达 `s'`，其 Q 值为 `{up: -3, down: -1, left: -4, right: -2}`。ε-greedy 策略这次"探索"选了 `a' = left`。取 `α = 0.5`、`γ = 0.9`，Q-learning 和 SARSA 更新后的 `Q(s,a)` 分别是：

- A. Q-learning：-1.95；SARSA：-3.3
- B. Q-learning：-3.3；SARSA：-1.95
- C. 两者都是 -1.95
- D. Q-learning：-1.9；SARSA：-4.6

**Q3.** 为什么说 Q-learning 是 off-policy 的？

- A. 因为它使用经验回放
- B. 因为目标中的 `max` 假设从 `s'` 之后执行贪心策略，与智能体实际怎么探索无关，所以学到的是 `Q*`
- C. 因为它不需要策略
- D. 因为它只能离线训练

**Q4.** 在经典悬崖行走任务中（掉下悬崖奖励 -100），固定 ε = 0.1 训练后：

- A. SARSA 学到贴着悬崖的最短路线，Q-learning 绕远
- B. Q-learning 的贪心策略贴着悬崖走（最短），但训练中因探索经常掉崖，在线平均回报反而更差；SARSA 走离悬崖更远的安全路线
- C. 两者学到完全相同的路线和回报
- D. 两者都无法到达终点

**Q5.** 关于 Expected SARSA，正确的是：

- A. 它是 off-policy 的，等价于 Q-learning
- B. 用下一状态动作价值在 π 下的期望代替采样的 `Q(s',a')`，去掉了"采样 a'"这一处随机性，方差更低
- C. 它需要环境模型
- D. 它比 SARSA 方差更高

**Q6.** Q-learning 的"最大化偏差"（maximization bias）指的是：

- A. Q 值总是被低估
- B. 当 Q 估计含噪声时，`E[max_a Q̂(s,a)] ≥ max_a E[Q̂(s,a)]`，取 max 会系统性高估
- C. ε-greedy 探索不足导致的偏差
- D. 学习率太大导致的偏差

**Q7.** 一个连续控制任务被设置了 1000 步的上限。第 1000 步时回合因"超时"被强制结束（并不是真正的失败或成功）。这一步的 TD 目标应该是：

- A. `r`（当作终止，不再自举）
- B. `r + γ V(s')`（继续自举，因为 `s'` 之后环境其实还会继续）
- C. 0
- D. `-100`，惩罚超时

---

## 三、动手 / 代码题

**Q8.** 下面是本节代码中 SARSA 的核心循环。请回答：(a) 为什么 `done` 分支里的更新是 `alpha * (r - Q[s][a])`，而不是 `r + gamma * Q[s_next][...]`？(b) 为什么 `a_next` 要在**更新之前**就选好，并在下一轮直接使用？如果每轮循环开头都重新调用 `epsilon_greedy` 选动作，会变成什么？

```python
        s = reset()
        a = epsilon_greedy(Q, s, rng, epsilon)
        total = 0.0
        for _ in range(200):
            s_next, r, done = step(s, a)
            total += r
            if done:
                Q[s][a] += alpha * (r - Q[s][a])
                break
            a_next = epsilon_greedy(Q, s_next, rng, epsilon)
            target = r + gamma * Q[s_next][a_next]
            Q[s][a] += alpha * (target - Q[s][a])
            s, a = s_next, a_next
```

**Q9.** 运行结果中，Q-learning 的贪心策略几乎全是 `v`：

```
  Q-learning greedy policy
   v v v v
   v v v v
   v v v v
   > > > .
```

这是最优策略吗？为什么箭头都是 `v` 而不是 `>`？另外，实测 3000 回合后 Q-learning 在每个状态的 `max_a Q(s,a)` 与 `V*(s)` 的差都小于 0.001，而 SARSA 的 `max_a Q((0,0),a) ≈ -6.24`，比 `V*(0,0) ≈ -5.85` 低。为什么？

**Q10.** 运行结果中，两种算法最后 500 回合的平均回报都约为 -6.6，而最优回报是 -6.0。学到的贪心策略明明已经最优，差距从哪里来？如果想让训练后期的回报接近 -6，代码该怎么改？

**Q11.** 讲义练习 2：实现 4×12 的悬崖行走（起点 `(3,0)`，终点 `(3,11)`，`(3,1)`–`(3,10)` 是悬崖：掉下去奖励 -100 并传送回起点）。用 ε = 0.1、α = 0.5、γ = 1 分别训练 Q-learning 和 SARSA 500 回合，比较最后 100 回合的平均回报与贪心路线。

---

## 四、面试高频题

**Q12.**（基础必考）Q-learning 和 SARSA 的区别是什么？on-policy 和 off-policy 的本质区别？各举一个适用场景。

**Q13.**（原理深挖）TD 为什么比 MC 方差低、但有偏？TD、MC、DP 在"是否自举 / 是否采样"上如何划分？n-step 回报和 TD(λ) 如何在两者之间权衡？

**Q14.**（原理深挖）Q-learning 为什么会高估？Double Q-learning 如何解决？它和 Double DQN 是什么关系？

**Q15.**（工程实践）调一个表格型 Q-learning 智能体时，α、ε、Q 初始化各自怎么设？如何判断训练是否正常？

**Q16.**（追问型）讲义的术语表说 GLIE 是"Q-learning 收敛所需的条件"。这个说法准确吗？Q-learning 和 SARSA 的收敛条件分别是什么？

---

## 五、参考答案与解析

### Q1 — 答案：B

TD 用一步目标 `r + γV(s')`：①每个转移之后立即更新，不必等回合结束（还能用于不终止的任务）；②目标只包含一步的随机性，方差远低于累积整条轨迹随机性的 MC 回报。代价是自举带来偏差，所以 A 错。C、D 都不成立：TD 同样需要奖励和 γ，收敛也依赖步长条件和充分探索。

### Q2 — 答案：A

- Q-learning 目标：`r + γ max Q(s',·) = -1 + 0.9 × (-1) = -1.9`；更新：`-2 + 0.5 × (-1.9 − (-2)) = -1.95`。
- SARSA 目标：`r + γ Q(s', left) = -1 + 0.9 × (-4) = -4.6`；更新：`-2 + 0.5 × (-4.6 − (-2)) = -3.3`。

SARSA 把"下一步会探索到一个糟糕动作"的事实算进了 `Q(s,a)`，Q-learning 则假设下一步会走最好的动作。D 是两个**目标值**，不是更新后的 Q。补充：若用 Expected SARSA（ε=0.1，4 个动作），期望为 `0.925×(-1) + 0.025×(-3-4-2) = -1.15`，目标 `-1 + 0.9×(-1.15) = -2.035`，更新后约 -2.02。

### Q3 — 答案：B

off-policy 的定义是"被学习的目标策略 ≠ 产生数据的行为策略"。Q-learning 的行为策略是 ε-greedy，但目标里的 `max` 对应贪心策略，学的是贪心（最优）策略的价值 `Q*`。A 是 DQN 的工程技巧，不是 off-policy 的定义（不过 off-policy 正是能用回放的前提）；C、D 不成立。

### Q4 — 答案：B

Q-learning 的目标假设"之后都走最优动作"，所以它认为贴崖走是最好的，却没把"走在崖边时 ε 探索会掉下去"计入价值；训练中它经常因此吃 -100。SARSA 的目标用实际执行（含探索）的下一个动作，"在崖边随机一步就可能 -100"会体现在价值里，于是学会离崖更远的路线，在线回报更好。讲义："With training, both reach optimal at ε → 0." 本测验 Q11 有实测数据。

### Q5 — 答案：B

Expected SARSA 的目标 `r + γ Σ_a' π(a'|s') Q(s',a')` 对下一个动作求期望，消除了采样 `a'` 的方差，仍然是 on-policy 目标（当 π 是贪心策略时它就退化成 Q-learning）。不需要环境模型——只需要知道自己的策略 π。

### Q6 — 答案：B

由 Jensen 不等式，`max` 是凸函数，`E[max_a Q̂] ≥ max_a E[Q̂]`。当所有动作的真值相同而估计有噪声时，取 max 总会挑中"碰巧被高估"的那个。讲义 Pitfalls："The max operator is biased upward when Q is noisy." Double Q-learning（以及 DQN 中的 DDQN）用来修正这一点。

### Q7 — 答案：B

超时截断不是 MDP 的真正终止——如果时间允许，智能体还会继续获得奖励。把它当作终止（目标只有 `r`）会让价值估计系统性偏差。讲义 Pitfalls："Standard: treat cap as non-terminal, keep bootstrapping." 这就是 Gymnasium 区分 `terminated`（真正终止，不自举）和 `truncated`（截断，继续自举）的原因。本节代码中 200 步上限截断时，最后一次更新已经用了 `r + γQ(s', a')` 自举，符合这一原则。

### Q8 — 参考答案

(a) `done=True` 说明 `s_next` 是终止态，之后没有任何奖励，`V(终止态) = 0`，所以目标就是 `r`。如果写成 `r + γQ[s_next][...]`，会读取终止态的 Q 值——它虽然一直是初始的 0，结果碰巧不错，但这依赖"终止态的 Q 永远不被更新"这一隐含前提；一旦初始化改成非零（例如乐观初始化为 +10），终止态的虚假价值就会泄漏进来。显式写 `r` 更安全、语义更清楚。

(b) SARSA 的目标必须用"**实际将要执行**"的 `a'`，即 `(s, a, r, s', a')` 中的那个 a'。所以先选好 `a_next`，用它计算目标，然后**真的执行它**（`s, a = s_next, a_next`）。如果下一轮开头重新调用 `epsilon_greedy`，执行的动作就可能和更新时用的 `a'` 不同（ε 探索是随机的，Q 也刚被更新），目标对应的就不再是行为策略本身——算法变成了一种既不是 SARSA 也不是 Q-learning 的混合体，失去 on-policy 的含义。对比代码中的 `q_learning`：它在每轮开头选动作，因为它的目标用 `max`，与下一个实际动作无关。

### Q9 — 参考答案

**是最优策略。** 环境确定、每步 -1，任何只向下/向右走的路径都是 6 步。在 `(r, c)` 处，向下与向右通常都在最短路径上，`Q*` 完全相等。代码中 `max(ACTIONS, key=...)` 平局时返回 `ACTIONS = ("up", "down", "left", "right")` 中**排在前面的** down；只有最下面一行"向下"会撞墙，才选 right。实测 `(0,0)` 处 `{'up': -6.792, 'down': -5.852, 'left': -6.7928, 'right': -5.852}`，down 与 right 相等。

**为什么 Q-learning 的 `max Q = V*` 而 SARSA 偏低：**
- Q-learning 的目标用 `max`，在确定性环境中反复更新会收敛到 `Q*`，所以 `max_a Q(s,a) = V*(s) = -(1 − 0.99⁶)/(1 − 0.99) ≈ -5.852`。
- SARSA 学的是**行为策略本身**（ε=0.1 的 ε-greedy）的价值 `Q^π`：π 有 10% 的概率乱走，期望步数更多，所以价值更低（-6.24）。讲义："SARSA converges to `Q^π` for whatever ε-greedy π is running, which in the limit ε → 0 becomes `Q*`."
- 另外，两者对**很少被尝试的动作**（如 `(0,2)` 的 left）估计都不准，实测 `max|Q − Q*|` 约 0.6–0.8，主要来自这类状态-动作对。

### Q10 — 参考答案

差距来自**训练时的 ε 探索**：`returns` 记录的是训练回合中 ε-greedy 策略的实际回报，每一步有 `ε × 3/4 = 7.5%` 的概率选非贪心动作，偶尔会多走几步甚至撞墙，平均下来约 -6.6。贪心策略本身是最优的，只是执行时被探索"拖累"。

改进：
- **ε 衰减**：例如 `epsilon = max(0.01, 1.0 * 0.995 ** episode)`，前期多探索、后期几乎贪心（讲义：从 1.0 衰减到 0.05）；
- **分离评估**：训练照常，另外每隔若干回合用 ε=0 的贪心策略跑一局评估，单独记录评估回报——这是 RL 实验的标准做法，评估回报会是 -6。

### Q11 — 参考答案

```python
import random
from collections import defaultdict

ROWS, COLS = 4, 12
START, GOAL = (3, 0), (3, 11)
ACTIONS = ("up", "down", "left", "right")
DELTAS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def cliff_step(state, action):
    dr, dc = DELTAS[action]
    r = min(max(state[0] + dr, 0), ROWS - 1)
    c = min(max(state[1] + dc, 0), COLS - 1)
    if r == 3 and 1 <= c <= 10:          # 掉下悬崖：-100，并传送回起点（回合不结束）
        return START, -100.0, False
    return (r, c), -1.0, (r, c) == GOAL


def eps_greedy(Q, s, rng, eps):
    if rng.random() < eps:
        return rng.choice(ACTIONS)
    return max(ACTIONS, key=lambda a: Q[s][a])


def train(method, episodes=500, alpha=0.5, gamma=1.0, eps=0.1, seed=0):
    rng = random.Random(seed)
    Q = defaultdict(lambda: {a: 0.0 for a in ACTIONS})
    returns = []
    for _ in range(episodes):
        s, total = START, 0.0
        a = eps_greedy(Q, s, rng, eps)
        for _ in range(1000):
            s2, r, done = cliff_step(s, a)
            total += r
            a2 = eps_greedy(Q, s2, rng, eps)
            if done:
                target = r
            elif method == "sarsa":
                target = r + gamma * Q[s2][a2]               # 实际要走的下一个动作
            else:
                target = r + gamma * max(Q[s2].values())     # 贪心的下一个动作
            Q[s][a] += alpha * (target - Q[s][a])
            if done:
                break
            s, a = s2, a2
        returns.append(total)
    return Q, returns


def greedy_path(Q):
    s, path = START, [START]
    for _ in range(50):
        s, _, done = cliff_step(s, max(ACTIONS, key=lambda a: Q[s][a]))
        path.append(s)
        if done:
            break
    return path


for method in ("q_learning", "sarsa"):
    Q, rets = train(method)
    path = greedy_path(Q)
    rows_used = sorted({r for r, _ in path[1:-1]})
    print(f"{method:10s}: mean return (last 100 eps) = {sum(rets[-100:]) / 100:7.2f}, "
          f"greedy path length = {len(path) - 1}, rows used = {rows_used}")
```

实测输出：

```
q_learning: mean return (last 100 eps) =  -43.04, greedy path length = 13, rows used = [2]
sarsa     : mean return (last 100 eps) =  -20.80, greedy path length = 17, rows used = [0, 1, 2]
```

解读：
- **Q-learning**：贪心路线 13 步（上 1、右 11、下 1），全程走在第 2 行——紧贴悬崖的最短路线。但训练中 ε=0.1 的随机动作常把它推下悬崖，在线平均回报只有 -43。
- **SARSA**：贪心路线 17 步，先爬到第 0 行（离悬崖最远），横穿后再下来。路线更长，但几乎不掉崖，在线平均回报 -20.8，明显更好。
- 结论：Q-learning 学的是"假如不再探索"的最优策略；SARSA 学的是"考虑到自己还会探索"时最好的策略。部署时如果探索仍在发生（或执行有噪声），SARSA 的保守更有价值。
- 实现细节：这里 `a2` 在两种方法中都提前选好并执行，Q-learning 只是目标不用它——对 Q-learning 来说，"先选后用"与"下一轮开头再选"等价。

### Q12 — 参考回答要点

- **区别只在目标那一行**：Q-learning `r + γ max_a' Q(s',a')`；SARSA `r + γ Q(s',a')`，a' 为实际执行的下一个动作。
- **本质**：on-policy 学的是"产生数据的那个策略"的价值；off-policy 学的是另一个目标策略（通常是贪心/最优策略）的价值，数据可以来自任何充分探索的行为策略。
- **后果**：Q-learning 收敛到 `Q*`，可以复用旧数据、他人数据（经验回放、离线数据）；SARSA 收敛到当前 ε-greedy 策略的 `Q^π`，更保守，但数据必须来自当前策略。
- **场景**：
  - Q-learning：可以充分模拟、只关心最终贪心策略的表现（游戏、仿真）；DQN 系列的基础；
  - SARSA / Expected SARSA：训练期间的安全也重要（真实机器人、在线系统），或部署时仍有探索噪声。
- **加分点**：用悬崖行走例子说明；指出 Expected SARSA 在 π 为贪心时等价于 Q-learning，是两者的统一。

### Q13 — 参考回答要点

- **方差**：MC 目标 `G_t` 累积了从 t 到回合结束所有动作、转移、奖励的随机性；TD 目标 `r + γV(s')` 只含一步随机性。
- **偏差**：TD 目标中的 `V(s')` 是当前估计，不等于真实 `V^π(s')`，所以目标有偏；MC 的 `G_t` 是 `V^π(s_t)` 的无偏样本。
- **划分**：

| | 采样（不需要模型） | 全宽度期望（需要模型） |
|---|---|---|
| 自举 | TD | DP |
| 不自举（到回合结束） | MC | 穷举搜索 |

- **折中**：n-step 回报 `r_{t+1} + … + γ^{n−1} r_{t+n} + γ^n V(s_{t+n})`，n 越大越接近 MC（偏差小、方差大）；TD(λ) 用 `(1−λ)λ^{n−1}` 对所有 n 加权平均，λ=0 是 TD(0)，λ=1 是 MC。讲义：深度 RL 中 n 常取 3–20；PPO 的 GAE 是 TD(λ) 思想在优势估计上的应用。
- **加分点**：指出 TD 还能用于不终止的连续任务，并且在 Markov 环境中通常比 MC 更样本高效。

### Q14 — 参考回答要点

- **高估原因**：目标里的 `max_a' Q(s',a')` 同时用同一组含噪估计做"**选**动作"和"**评**价值"。被噪声高估的动作更可能被选中，于是目标被系统性抬高；再通过自举一层层传播。
- **Double Q-learning（Hasselt, 2010）**：维护两张表 Q_A、Q_B。每次随机更新其中一张，例如更新 Q_A 时：`a* = argmax_a Q_A(s', a)`，目标 `r + γ Q_B(s', a*)`。选择和评估用独立的估计，噪声不再同向相关，偏差大幅降低（可能略微低估）。
- **与 Double DQN 的关系**：DDQN（下一节）不另建网络，而是复用 DQN 已有的两个网络：用在线网络选动作 `argmax_a Q(s', a; θ)`，用目标网络评估 `Q(s', a*; θ⁻)`。
- **加分点**：讲义练习 3——在每步奖励加上 σ=5 的高斯噪声后，Q-learning 会明显高估 `V*(0,0)`，Double Q-learning 不会；提到 TD3 的"双 critic 取最小"是同一思想在连续控制中的延伸。

### Q15 — 参考回答要点

- **α**：讲义建议固定在 `[0.05, 0.3]` 并观察学习曲线；`1/n` 衰减理论上收敛但实践太慢；环境随机性大时取小一些。
- **ε**：从 1.0 开始衰减到 0.05 左右（GLIE 思想）；全程 ε=1.0 意味着从不利用，讲义的 skill 明确要标记这种情况。
- **Q 初始化**：负奖励任务中 Q=0 即乐观初始化，能促进探索；悲观初始化可能让贪心策略永远困在某个动作上。
- **诊断**：
  1. 学习曲线（每 100 回合平均回报）应上升并趋于平稳；
  2. 小环境上与 DP 的 `Q*` 比较（讲义：1 万回合后 `max|Q − Q*|` 应在约 0.5 以内）；
  3. 分开记录"训练回报（含探索）"和"贪心评估回报"；
  4. 检查终止态处理、状态是否可哈希（用元组、浮点状态先离散化/取整）。
- **加分点**：用多个随机种子报告均值和方差，而不是单次运行。

### Q16 — 参考回答要点

- **不完全准确。** Q-learning 收敛到 `Q*` 的条件（Watkins & Dayan, 1992）是：所有状态-动作对被**无限次访问**，步长满足 Robbins-Monro（`Σα = ∞`、`Σα² < ∞`），表格表示、有界奖励。它**不要求**行为策略最终变成贪心——哪怕行为策略一直是 ε=0.1 甚至均匀随机，Q 表也会收敛到 `Q*`，这正是 off-policy 的优势。
- **GLIE 的作用**：①对 SARSA 等 on-policy 方法，必须让 ε → 0，学到的 `Q^π` 才会趋向 `Q*`；②对 Q-learning，GLIE 保证的是"**智能体实际的行为**也最终变成最优"（训练回报收敛到最优），而不是 Q 表的收敛。
- **加分点**：本节代码就是证据——固定 ε=0.1 的 Q-learning 学到的 `max Q` 已与 `V*` 相差不到 0.001，而 SARSA 的 Q 仍对应 ε-greedy 策略。

---

## 六、关联知识点

### 前置知识
- [阶段 09 · 01 MDP、状态、动作与奖励](../../01-mdps-states-actions-rewards/docs/zh.md)：Bellman 方程、V 与 Q。
- [阶段 09 · 02 动态规划](../../02-dynamic-programming/docs/zh.md)：Q-learning 是采样版的值迭代；用 DP 的 `Q*` 检验实现。
- [阶段 09 · 03 Monte Carlo 方法](../../03-monte-carlo-methods/docs/zh.md)：增量均值、常数 α、ε-greedy、on/off-policy。

### 本节被哪些后续内容用到
- [阶段 09 · 05 DQN](../../05-dqn/docs/zh.md)：用神经网络近似 Q 的 Q-learning，加上经验回放、目标网络、Double DQN。
- [阶段 09 · 07 Actor-Critic](../../07-actor-critic-a2c-a3c/docs/zh.md)：critic 用 TD 误差作为 actor 的学习信号。
- [阶段 09 · 08 PPO](../../08-ppo/docs/zh.md)：GAE 是 TD(λ) 思想在优势估计上的应用。
- [阶段 09 · 10 多智能体 RL](../../10-multi-agent-rl/docs/zh.md)：独立 Q-learning（IQL）把其他智能体视为环境的一部分。
- [阶段 16 · 20 MARL：MADDPG、QMIX、MAPPO](../../../16-multi-agent-and-swarms/20-marl-maddpg-qmix-mappo/docs/zh.md)：值分解方法以 Q-learning 为基础。

### 延伸关键词
`TD(λ)` · `资格迹 (eligibility traces)` · `n-step SARSA` · `Expected SARSA` · `Double Q-learning` · `Robbins-Monro 条件` · `GLIE` · `乐观初始化` · `terminated vs truncated` · `悬崖行走 (Cliff Walking)`
