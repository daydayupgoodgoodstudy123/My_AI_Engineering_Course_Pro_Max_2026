# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 10 节 多 Agent RL ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 0.3 秒跑完） ｜ **依赖**：仅 Python 标准库（`random`、`collections.defaultdict`）

---

## 1. 这份代码在考察什么

这份代码搭了一个最小的**合作型双智能体**环境，并用两种表格 Q-learning 去解它，让你直观对比多智能体 RL 的两个极端：

1. **Markov Game 的最小实现**：联合状态 = 两个智能体位置的元组，联合动作 = 两个动作的元组，**共享**一个奖励。
2. **独立 Q-learning（IQL）**：每个智能体各有一张 Q 表，只决定自己的动作，把队友当成环境的一部分——对应讲义的 regime 1。
3. **联合 Q-learning**：一张 Q 表覆盖 16 个联合动作，相当于一个"中央大脑"同时控制两个智能体——拥有正确的全局视角，代价是动作空间 `|A|²`。
4. **学习曲线对比**：动作空间大小如何影响探索速度，非平稳性在松耦合任务中影响有多大。

> 一句话：**IQL 是"各自为战、碰运气配合"，联合 Q 是"一个大脑指挥全队"；CTDE（MAPPO、QMIX）就是在两者之间找平衡。**

⚠️ 讲义 Build It 部分描述的是 6×6 网格、目标 `(5,5)`、起点 `(0,0)` 与 `(5,0)`；而本代码实际是 **5×5 网格、目标 `(4,4)`、起点 `(0,0)` 与 `(4,0)`**，以代码为准。讲义 Step 3 的"边缘化分散执行"和 Step 4 的"自博弈"在代码中没有实现。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GRID / GOAL / ACTIONS / DELTAS` | 常量 | 5×5 网格、共同目标 (4,4)、四个动作 | 环境定义 |
| `move(pos, action)` | 函数 | 单个智能体移动一步，撞墙原地不动 | 单体动力学 |
| `reset()` / `step(state, action_pair)` | 函数 | 联合状态复位；执行联合动作，返回共享奖励 | Markov Game |
| `default_q()` | 函数 | 新状态的 Q 值字典 `{动作: 0.0}` | Q 表默认值工厂 |
| `epsilon_greedy()` | 函数 | ε-贪心选单个智能体的动作 | 探索策略 |
| `independent_q()` | 函数 | 两张 Q 表，各自 TD 更新 | IQL |
| `joint_q_learning()` | 函数 | 一张 Q 表，动作是 `(a1, a2)` 元组 | 集中式联合 Q |
| `block_mean()` | 函数 | 每 150 回合平均一次回报 | 平滑学习曲线 |
| `evaluate_ind()` / `evaluate_joint()` | 函数 | ε=0 的贪心评估 | 策略评估 |
| `main()` | 函数 | 两种方法各训练 1500 回合，打印曲线与评估 | 演示入口 |

数据流：`main` 分别调用 `independent_q` 和 `joint_q_learning`（同一种子 `Random(1)`）→ 用 `block_mean` 对比学习曲线 → 用两个 `evaluate_*` 做贪心评估。

---

## 3. 逐段精讲

### 3.1 环境：两个智能体、一个共享奖励

```python
def move(pos, action):
    dr, dc = DELTAS[action]
    r, c = pos
    return (min(max(r + dr, 0), GRID - 1), min(max(c + dc, 0), GRID - 1))


def reset():
    return ((0, 0), (GRID - 1, 0))


def step(state, action_pair):
    a1_pos, a2_pos = state
    new1 = move(a1_pos, action_pair[0])
    new2 = move(a2_pos, action_pair[1])
    done = (new1 == GOAL) and (new2 == GOAL)
    reward = 10.0 if done else -1.0
    return (new1, new2), reward, done
```

- **联合状态**是嵌套元组 `((r1, c1), (r2, c2))`，可以直接当字典的键（元组可哈希）。联合状态空间大小 25×25 = 625。
- **共享奖励**：两者拿到同一个数，属于讲义所说的"fully cooperative"Markov Game。
- **结束条件**：两个智能体**同时**站在目标上。智能体 1 从 (0,0) 出发至少要 8 步，智能体 2 从 (4,0) 出发只要 4 步——所以先到的智能体 2 必须"等"。环境没有 "stay" 动作，但 `move` 中的 clamp 让撞墙等于原地不动，智能体可以靠"对着墙走"来等待。最优回报是 8 步：`-1×7 + 10 = 3`。
- 两个智能体可以重叠在同一格（没有碰撞），这是一个简化。

### 3.2 Q 表：`defaultdict` + 字典

```python
def default_q():
    return {a: 0.0 for a in ACTIONS}


def epsilon_greedy(q_table, state, rng, epsilon):
    if rng.random() < epsilon:
        return rng.choice(ACTIONS)
    q = q_table[state]
    return max(ACTIONS, key=lambda a: q[a])
```

- `defaultdict(default_q)` 访问没见过的状态时，自动调用 `default_q()` 生成全 0 的动作值字典——"按需建表"，不用预先枚举 625 个状态。
- 为什么要写成函数 `default_q` 而不是直接传一个字典？因为 `defaultdict` 需要的是**工厂函数**，每次调用都返回一个**新的**字典；如果所有状态共享同一个字典对象，改一个就全改了。
- `max(ACTIONS, key=...)` 在 Q 值并列时返回 `ACTIONS` 中**第一个**最大者（`"up"`）。所以所有未学习的状态都会贪心地选 `up`。
- `epsilon=0.0` 时 `rng.random() < 0` 恒为假，就是纯贪心——评估函数正是这么复用它的。

### 3.3 独立 Q-learning：各学各的

```python
def independent_q(episodes=1500, alpha=0.1, gamma=0.95, epsilon=0.15, rng=None):
    rng = rng or random.Random(0)
    Q1 = defaultdict(default_q)
    Q2 = defaultdict(default_q)
    returns_log = []
    for _ in range(episodes):
        s = reset()
        total = 0.0
        for _ in range(100):
            a1 = epsilon_greedy(Q1, s, rng, epsilon)
            a2 = epsilon_greedy(Q2, s, rng, epsilon)
            s_next, r, done = step(s, (a1, a2))
            total += r
            if done:
                Q1[s][a1] += alpha * (r - Q1[s][a1])
                Q2[s][a2] += alpha * (r - Q2[s][a2])
                break
            target1 = r + gamma * max(Q1[s_next].values())
            target2 = r + gamma * max(Q2[s_next].values())
            Q1[s][a1] += alpha * (target1 - Q1[s][a1])
            Q2[s][a2] += alpha * (target2 - Q2[s][a2])
            s = s_next
        returns_log.append(total)
    return Q1, Q2, returns_log
```

- 每个智能体的 Q 表以**联合状态**为键（能看到队友在哪），但只对**自己的动作**估值：`Q1[s][a1]`。队友的动作 `a2` 被"平均"进了环境里——这就是讲义说的"treating others as part of the environment"。
- **TD 更新**：`Q ← Q + α(r + γ·max Q(s') - Q)`，标准 Q-learning。终止步的目标是 `r`（没有未来）。
- **非平稳性藏在哪里**：`Q1[s][a1]` 的目标取决于智能体 2 在 `s` 下会做什么，而智能体 2 的策略（由 `Q2` 决定）一直在变。同一个 `(s, a1)` 早期和后期得到的回报分布不同——这正是单智能体收敛性证明失效的原因。
- 每回合最多 100 步，超时直接开始下一回合（超时不做特殊处理）。
- `total` 是**未折扣**回报，便于和最优值 3 对比。

### 3.4 联合 Q-learning：一个大脑控制两个身体

```python
def joint_q_learning(episodes=1500, alpha=0.1, gamma=0.95, epsilon=0.15, rng=None):
    rng = rng or random.Random(0)
    joint_actions = [(a, b) for a in ACTIONS for b in ACTIONS]
    Q = defaultdict(lambda: {ja: 0.0 for ja in joint_actions})
    ...
            if rng.random() < epsilon:
                ja = rng.choice(joint_actions)
            else:
                ja = max(joint_actions, key=lambda a: Q[s][a])
            s_next, r, done = step(s, ja)
            total += r
            if done:
                Q[s][ja] += alpha * (r - Q[s][ja])
                break
            best_next = max(Q[s_next].values())
            Q[s][ja] += alpha * ((r + gamma * best_next) - Q[s][ja])
            s = s_next
```

- `joint_actions` 用双重列表推导生成 16 个 `(a1, a2)` 元组，作为 Q 表的"动作"。
- 这里用 `lambda` 作为 `defaultdict` 的工厂，效果和 `default_q` 一样，每次返回新字典；`lambda` 能"捕获"外层的 `joint_actions` 变量。
- 本质上就是把双智能体问题**还原成单智能体问题**：动作空间从 4 变成 16，环境对这个"大智能体"来说是平稳的，Q-learning 的收敛保证重新成立。
- 代价：①动作空间随智能体数指数增长（n 个智能体就是 `4ⁿ`）；②执行时需要一个能看到全局、统一下发动作的中央控制器，这在真实多机器人/多车辆系统中往往不现实。讲义 Step 3 提出可以在执行时"边缘化"成各自的策略 `π_i(s) = argmax_{a_i} max_{a_{-i}} Q(s, a)`，本代码没有实现（见测验 Q11）。
- ⚠️ 探索方式不同：联合 Q 以 ε 概率随机选**联合动作**，IQL 是两个智能体各自以 ε 概率随机。IQL 下"至少一个智能体在探索"的概率约为 `1-(0.85)² ≈ 0.28`，比联合 Q 的 0.15 更高。对比学习曲线时要记得这个混杂因素。

### 3.5 评估与曲线

```python
def block_mean(xs, block):
    return [sum(xs[i : i + block]) / block for i in range(0, len(xs) - block + 1, block)]

def evaluate_ind(Q1, Q2, episodes=100, rng=None):
    rng = rng or random.Random(42)
    ...
            a1 = epsilon_greedy(Q1, s, rng, 0.0)
            a2 = epsilon_greedy(Q2, s, rng, 0.0)
```

- `block_mean` 把 1500 个回合切成 10 块，每块 150 个求平均。`range(0, len - block + 1, block)` 保证最后不足一块的部分被丢弃。
- 评估时 `ε=0`，策略完全确定；环境也是确定性的，所以 100 个评估回合其实**一模一样**，均值就是单个回合的回报。`episodes=100` 在这里是冗余的，但如果环境有随机性就有意义了。
- 两个评估函数都共享 `Q[s]` 的 `defaultdict` 行为：评估时访问到没见过的状态会**往 Q 表里插入新条目**——评估有副作用，不过在本任务中不影响结果。

### 3.6 主函数：同种子公平对比

```python
    Q1, Q2, log_ind = independent_q(episodes=1500, rng=random.Random(1))
    Q_joint, log_joint = joint_q_learning(episodes=1500, rng=random.Random(1))

    print("learning curves (mean return per 150 episodes):")
    for i, (a, b) in enumerate(zip(block_mean(log_ind, 150), block_mean(log_joint, 150))):
        print(f"  block {i+1}: independent-Q = {a:7.2f}   joint-Q = {b:7.2f}")
```

- 两种方法使用同样的种子 `Random(1)`、同样的超参（α=0.1、γ=0.95、ε=0.15），差异主要来自算法本身（以及 3.4 提到的探索率差异）。
- `enumerate(zip(...))` 同时拿到块序号和两个方法的块均值。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 共享奖励的合作任务 | 最简单的 Markov Game，便于聚焦非平稳与协调 | 真实场景常是一般和、各自奖励 |
| IQL 的 Q 表以联合状态为键 | 每个智能体能看到队友位置，降低难度 | 真实 CTDE 中执行时只有本地观测；全局状态只给 critic |
| 联合 Q 作为对照 | 展示"正确的全局视角"与动作空间爆炸的取舍 | 生产中用 CTDE（MAPPO/QMIX）替代 |
| 撞墙 = 原地不动 | 不需要 stay 动作也能等待 | 真实环境常显式提供 no-op |
| 表格 Q-learning | 无需函数逼近，0.3 秒跑完 | 状态大时用神经网络 + 参数共享 |
| 同种子、同超参 | 公平对比 | 应多种子取均值与方差 |
| 未实现自博弈与边缘化执行 | 控制篇幅 | 见讲义 Step 3、4 与测验 Q11 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 嵌套元组 | `((0, 0), (GRID - 1, 0))` | 不可变、可哈希，能做字典键 |
| 元组解包 | `a1_pos, a2_pos = state`；`dr, dc = DELTAS[action]` | 一次取出多个元素 |
| 字典推导式 | `{a: 0.0 for a in ACTIONS}` | 一行构造"动作 → Q 值"字典 |
| 双重列表推导式 | `[(a, b) for a in ACTIONS for b in ACTIONS]` | 笛卡尔积，等价于 `itertools.product(ACTIONS, ACTIONS)` |
| `collections.defaultdict` | `defaultdict(default_q)`、`defaultdict(lambda: {...})` | 缺失键时调用工厂函数生成默认值 |
| `lambda` 与闭包 | `lambda: {ja: 0.0 for ja in joint_actions}` | 匿名函数，捕获外部变量 `joint_actions` |
| `max(..., key=lambda ...)` | `max(ACTIONS, key=lambda a: q[a])` | 按 Q 值取 argmax；并列时返回第一个 |
| `dict.values()` | `max(Q1[s_next].values())` | 取所有动作的 Q 值求最大 |
| `x or default` | `rng = rng or random.Random(0)` | 未传入时使用默认随机数生成器 |
| `random.Random` 实例 | `rng.random()`、`rng.choice(ACTIONS)` | 独立、可复现的随机源 |
| `break` | `if done: ... break` | 回合结束跳出步循环 |
| `enumerate(zip(...))` | `for i, (a, b) in enumerate(zip(...))` | 同时取序号和配对元素 |
| f-string | `f"{a:7.2f}"`、`f"({GRID-1}, 0)"` | 宽度 7、两位小数；花括号内可写表达式 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13，约 0.3 秒）输出：

```text
=== Cooperative 2-agent GridWorld (5x5, shared reward) ===
agents start at (0,0) and (4, 0); must both reach (4, 4)

learning curves (mean return per 150 episodes):
  block 1: independent-Q =  -55.03   joint-Q =  -98.59
  block 2: independent-Q =  -27.70   joint-Q =  -53.49
  block 3: independent-Q =  -13.60   joint-Q =  -21.27
  block 4: independent-Q =   -6.44   joint-Q =   -6.80
  block 5: independent-Q =   -1.01   joint-Q =    0.56
  block 6: independent-Q =    0.10   joint-Q =    0.40
  block 7: independent-Q =    0.44   joint-Q =    1.01
  block 8: independent-Q =    0.20   joint-Q =    0.56
  block 9: independent-Q =    0.55   joint-Q =    1.04
  block 10: independent-Q =    0.80   joint-Q =    0.85

final greedy evaluation (100 eps):
  independent-Q mean return = 3.00
  joint-Q       mean return = 3.00

note: joint-Q factors the global view correctly, but its action space is |A|^2.
CTDE methods (MAPPO, QMIX) keep decentralized actors but use a centralized critic.
```

逐段解读：

- **前期（block 1~3）**：联合 Q 明显更差（-98.59 vs -55.03）。block 1 的 -98.59 说明联合 Q 早期大多数回合都跑满 100 步超时（回报 -100）。原因是：每步奖励都是 -1，Q 值初始化为 0 相当于**乐观初始化**——任何试过的动作 Q 值都会变负，贪心选择就会换到下一个还没试过的动作（并列时按 `joint_actions` 顺序，从 `("up","up")` 开始）。于是联合 Q 在每个状态上要把 16 个联合动作都"试一遍"才会稳定下来；IQL 每张表只有 4 个动作，系统性试错快得多，再加上两个智能体独立探索，更早"撞"到目标。
- **中后期（block 5~10）**：两者都在 0~1 之间波动，联合 Q 略高。训练中的回报低于最优值 3，是因为 ε=0.15 的探索不断引入多余步数（IQL 的有效探索率更高，所以训练回报更低）。
- **贪心评估都等于 3.00**：两者都学到了 8 步的最优策略。实测 IQL 的贪心轨迹中，智能体 2 在 4 个时间步里选择撞墙（`left`、`left`、`down`、`down`）原地等待，与智能体 1 同时在第 8 步到达——这说明 IQL 在这个"松耦合 + 联合状态可见 + 确定性"的任务上足以学会简单的协调。
- **最后两行 note**：总结了本节的核心取舍——联合 Q 的全局视角正确但动作空间指数爆炸，CTDE 方法保留分散的 actor、只在训练时使用集中式 critic。

---

## 7. 动手改一改

1. **IQL 达到正回报需要多少回合**（讲义练习 Easy）：把 `block_mean` 的块大小改成 50，找出 IQL 块均值首次 > 0 的位置。
2. **公平探索**：把联合 Q 的探索改成"两个分量各以 ε 独立随机"，重新对比前期学习曲线。
3. **边缘化分散执行**：实现测验 Q11 的 `decentralized_actions`，用它评估训练好的联合 Q，并构造一个并列最优的情形观察协调失败。
4. **同时踏上目标**（讲义练习 Medium）：按测验 Q12 改写 `step`，比较 IQL 与联合 Q 的收敛情况。
5. **部分可观测**：让 `Q1` 只以智能体 1 自己的位置为键（`Q1[s[0]]`），`Q2` 同理，观察 IQL 是否还能学会"等待"——这才是 CTDE 要解决的真实场景。
6. **三个智能体**：加入第三个智能体，打印联合 Q 的表大小和训练时间，体会 `4ⁿ` 的增长。

---

## 8. 常见坑

- **`defaultdict` 工厂写成同一个对象**：`defaultdict(lambda: shared_dict)` 会让所有状态共享同一个 Q 字典；工厂必须每次返回**新**对象。
- **评估时修改 Q 表**：用 `Q[s]` 读取未见过的状态会插入新键；只读时用 `Q.get(s)` 或接受这个副作用。
- **并列 argmax 的隐性偏置**：`max` 在并列时总选第一个动作，未训练的状态会系统性地选 `up`；需要随机 tie-break 时要显式实现。
- **比较曲线时忽略探索率差异**：IQL 的"两个智能体各自 ε"与联合 Q 的"联合 ε"不是同一个探索强度。
- **以为 IQL 一定失败**：在松耦合、信息充分的任务里 IQL 往往是很强的基线（讲义："IPPO ... often underrated"）；它的失败主要出现在紧耦合、部分可观测、需要罕见联合动作的任务中。
- **把联合 Q 当成可部署方案**：它需要中央控制器和全局信息，真实多智能体系统通常做不到——这正是 CTDE 存在的理由。
