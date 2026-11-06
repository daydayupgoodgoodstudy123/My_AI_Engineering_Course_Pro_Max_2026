# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 04 节 时序差分——Q-Learning 与 SARSA ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，不到 0.1 秒） ｜ **依赖**：仅 Python 标准库（`random`、`collections.defaultdict`）

---

## 1. 这份代码在考察什么

这是整个阶段 09 的"枢纽"代码：后面的 DQN、Actor-Critic、PPO 都是在这里的一步 TD 更新上加函数近似和各种技巧。代码在同一个 4×4 GridWorld 上并排实现两种 TD 控制算法：

1. **SARSA（on-policy）**：目标 `r + γQ(s', a')`，a' 是**实际要执行**的下一个动作。
2. **Q-learning（off-policy）**：目标 `r + γ max_a' Q(s', a')`，假设之后走贪心动作。
3. **"只差一行"**：讲义原话——两者唯一的区别就是计算 target 的那一行，以及由此带来的"什么时候选下一个动作"。
4. **与 MC 的对比**：每走一步就更新（不等回合结束），3000 回合不到 0.1 秒就学到最优路径。
5. **学习曲线**：用分块平均（每 500 回合）观察收敛，并认识"训练回报包含探索代价"。

> 一句话：**TD = 用"一步真实奖励 + 对下一步的估计"当目标，边走边学**；Q-learning 和 SARSA 的差别在于"下一步"按谁的策略估计。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GRID`、`TERMINAL`、`ACTIONS`、`DELTAS`、`reset`、`step` | 常量 / 函数 | 与前两节相同的确定性 GridWorld | 环境（只能采样） |
| `epsilon_greedy(Q, state, rng, epsilon)` | 函数 | ε 概率随机，否则取 Q 最大的动作 | 行为策略 |
| `sarsa(episodes, alpha, gamma, epsilon, rng)` | 函数 | SARSA 训练，返回 Q 表与每回合回报 | on-policy TD 控制 |
| `q_learning(...)` | 函数 | Q-learning 训练，返回 Q 表与每回合回报 | off-policy TD 控制 |
| `greedy_policy(Q)` | 函数 | 从 Q 表提取贪心策略 | 策略提取 |
| `print_policy(policy, title)` | 函数 | 打印箭头图，未访问的状态显示 `?` | — |
| `block_means(xs, block)` | 函数 | 分块求平均，生成学习曲线 | 平滑 |
| `main()` | 函数 | 同一种子下训练两种算法并对比 | 对照实验 |

调用关系：`sarsa` / `q_learning` → `reset`、`step`、`epsilon_greedy`；`main` → 两个训练函数 → `block_means`、`greedy_policy`、`print_policy`。

---

## 3. 逐段精讲

### 3.1 `epsilon_greedy`：行为策略

```python
def epsilon_greedy(Q, state, rng, epsilon):
    if rng.random() < epsilon:
        return rng.choice(ACTIONS)
    q = Q[state]
    return max(ACTIONS, key=lambda a: q[a])
```

- 以 ε 的概率在**全部 4 个动作**中随机选（包括贪心动作本身），否则选 Q 最大的动作。所以贪心动作的总概率是 `1 − ε + ε/4 = 0.925`。
- `max(ACTIONS, key=...)` 按**固定顺序** `("up", "down", "left", "right")` 遍历，平局时返回第一个——稳定的 tie-break（第 02 节讲过）。上一节 MC 代码写的是 `max(Q[state], key=Q[state].get)`，遍历字典的键，效果相同，因为字典也按插入顺序。
- `q = Q[state]` 先取出该状态的小字典，避免在 lambda 中重复查外层 defaultdict。
- `Q` 是 `defaultdict`，第一次访问某状态时自动创建 `{a: 0.0 ...}`。所有奖励都是 -1，所以 Q=0 是**乐观初始化**：没试过的动作看起来最好，会被优先尝试（讲义 Pitfalls 第一条）。

### 3.2 `sarsa`：先选 a'，再更新，再执行 a'

```python
def sarsa(episodes, alpha=0.1, gamma=0.99, epsilon=0.1, rng=None):
    rng = rng or random.Random(0)
    Q = defaultdict(lambda: {a: 0.0 for a in ACTIONS})
    returns = []
    for _ in range(episodes):
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
        returns.append(total)
    return Q, returns
```

按名字 `(S, A, R, S', A')` 逐行对应：

- 回合开始前就选好第一个动作 `a`；循环里执行 `(s, a)` 得到 `r, s_next`；
- **先选 `a_next`**（用当前 Q 的 ε-greedy），用它构造目标 `r + γQ(s', a')`；
- 更新 `Q[s][a] += α(target − Q[s][a])`——这就是 `Q ← Q + α·δ`，`δ` 是 TD 误差；
- `s, a = s_next, a_next`：下一轮**真的执行**刚才用于目标的那个 `a_next`，保证"评估的策略 = 执行的策略"（on-policy）。
- **终止处理**：`done` 时目标只有 `r`（终止态之后没有回报），不再读取 `Q[s_next]`。
- **截断处理**：`range(200)` 跑满时直接结束回合，最后一次更新已用 `r + γQ(s', a')` 自举——相当于把截断视为"非终止"，与讲义 Pitfalls 推荐的做法一致。
- `total` 是**未折扣**的回报，直接对应"步数的负数"，可与最优 -6 比较。
- 内层循环变量也叫 `_`，与外层 `for _ in range(episodes)` 同名——Python 允许，但两层都不使用循环变量，所以没问题。

### 3.3 `q_learning`：目标里换成 max

```python
def q_learning(episodes, alpha=0.1, gamma=0.99, epsilon=0.1, rng=None):
    # ...
        s = reset()
        total = 0.0
        for _ in range(200):
            a = epsilon_greedy(Q, s, rng, epsilon)
            s_next, r, done = step(s, a)
            total += r
            if done:
                Q[s][a] += alpha * (r - Q[s][a])
                break
            best_next = max(Q[s_next].values())
            target = r + gamma * best_next
            Q[s][a] += alpha * (target - Q[s][a])
            s = s_next
```

- 与 SARSA 的唯一本质区别：`best_next = max(Q[s_next].values())`。目标不关心下一步实际做什么，所以动作可以在每轮开头**现选**，不必提前选好 a'。
- `Q[s_next].values()` 取出 4 个动作的 Q 值，`max` 直接取最大值（不需要知道是哪个动作）。
- 这一个 `max` 让 Q-learning 学到的是**贪心策略**的价值 `Q*`，而数据来自 ε-greedy——off-policy。讲义："That one symbol is the difference between on-policy and off-policy."
- ⚠️ 表格 + 确定性环境下没有明显的最大化偏差；若奖励有噪声，`max` 会系统性高估（讲义练习 3，Double Q-learning）。

### 3.4 `greedy_policy` 与 `print_policy`

```python
def greedy_policy(Q):
    return {s: max(ACTIONS, key=lambda a: q[a]) for s, q in Q.items()}
```

- 字典推导式遍历 `Q.items()`，每个状态取 Q 最大的动作。只有**出现在 Q 里**（被访问过）的状态才有策略；`print_policy` 对缺失的状态打印 `?`，对终点打印 `.`。
- lambda 中引用的 `q` 是推导式当前迭代的值，且 lambda 在 `max` 内立即执行完，不会有闭包晚绑定问题。

### 3.5 `block_means`：学习曲线

```python
def block_means(xs, block):
    return [sum(xs[i : i + block]) / block for i in range(0, len(xs) - block + 1, block)]
```

- `range(0, len(xs) - block + 1, block)` 生成每块的起点 0, 500, 1000, …；`xs[i : i + block]` 切出一块求平均。
- `- block + 1` 保证只统计**完整**的块：3000 个回合正好 6 块；若有 3100 个，最后 100 个会被丢掉。
- 分块平均是最简单的平滑方法；讲义练习 1 用的是每 100 回合一块。

### 3.6 `main`：公平对照

```python
    episodes = 3000
    rng = random.Random(42)
    Q_sarsa, ret_sarsa = sarsa(episodes, rng=rng)
    rng = random.Random(42)
    Q_ql, ret_ql = q_learning(episodes, rng=rng)
    # ...
    for i, (a, b) in enumerate(zip(block_means(ret_sarsa, 500), block_means(ret_ql, 500))):
        print(f"  block {i+1}: sarsa={a:7.2f}   q-learning={b:7.2f}")
```

- 两种算法使用**同一种子的新生成器**，超参相同（α=0.1、ε=0.1、γ=0.99），确保差异只来自算法本身。
- `enumerate(zip(...))` 同时拿到块编号和两条曲线的对应值；`(a, b)` 是嵌套解包。注意这里的 `a`、`b` 只是数值，与"动作 a"无关。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 两个算法分开写成独立函数 | 便于逐行对比"只差一行" | 有重复代码；工程上会抽象出 `target_fn` |
| 固定 α=0.1 | 讲义建议 α 取 0.05–0.3 并观察曲线 | 理论收敛需要衰减步长；随机环境中要更小 |
| 固定 ε=0.1 | 简单、持续探索 | 训练回报永远含探索代价（约 -6.6）；生产中用 ε 衰减或单独评估 |
| Q 初始化为 0 | 负奖励任务中天然是乐观初始化 | 奖励为正时会变成悲观初始化 |
| 终止时目标只用 `r` | 终止态价值为 0，显式写出更安全 | 无 |
| 200 步截断后不做特殊处理 | 最后一步已经自举，等价于"截断不当终止" | 生产中显式区分 terminated / truncated |
| 记录未折扣回报 | 直接对应步数，易与 -6 比较 | 与 γ=0.99 下的 Q 值口径不同 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组常量 | `ACTIONS = ("up", "down", "left", "right")` | 固定顺序，决定 tie-break |
| `defaultdict(lambda: {...})` | `Q = defaultdict(lambda: {a: 0.0 for a in ACTIONS})` | 新状态自动得到"全 0"的动作值字典 |
| `lambda` 作为 key | `max(ACTIONS, key=lambda a: q[a])` | argmax：返回让 Q 最大的动作 |
| `dict.values()` + `max` | `max(Q[s_next].values())` | 只要最大值本身，不要动作 |
| 复合赋值 | `Q[s][a] += alpha * (target - Q[s][a])` | 原地更新嵌套字典中的值 |
| 多重赋值 | `s, a = s_next, a_next` | 先计算右边所有值再同时赋给左边 |
| `break` 提前退出循环 | `if done: ... break` | 回合结束时跳出内层 `for`；跑满 200 次则自然结束（截断） |
| `rng or 默认值` | `rng = rng or random.Random(0)` | 未传入时用固定种子 |
| 列表切片 | `xs[i : i + block]`、`ret_sarsa[-500:]` | 取一段 / 取最后 500 个 |
| `range(start, stop, step)` | `range(0, len(xs) - block + 1, block)` | 按步长生成块起点 |
| 列表推导式 | `[sum(xs[i : i + block]) / block for i in range(...)]` | 一行算出所有块平均 |
| 字典推导式 + `items()` | `{s: max(...) for s, q in Q.items()}` | 从 Q 表生成策略 |
| `enumerate(zip(...))` | `for i, (a, b) in enumerate(zip(...))` | 同时得到下标与配对元素 |
| f-string 表达式 | `f"block {i+1}: sarsa={a:7.2f}"`、`{sum(ret_sarsa[-500:])/500:.2f}` | 花括号内可以写任意表达式 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.07 秒）的输出：

```text
=== 4x4 GridWorld, 3000 episodes, alpha=0.1, eps=0.1, gamma=0.99 ===

learning curves (mean return per block of 500 episodes):
  block 1: sarsa=  -9.41   q-learning=  -9.30
  block 2: sarsa=  -6.67   q-learning=  -6.67
  block 3: sarsa=  -6.55   q-learning=  -6.54
  block 4: sarsa=  -6.63   q-learning=  -6.62
  block 5: sarsa=  -6.67   q-learning=  -6.68
  block 6: sarsa=  -6.58   q-learning=  -6.59

  SARSA greedy policy
   > > v v
   v > v v
   > > v v
   > > > .

  Q-learning greedy policy
   v v v v
   v v v v
   v v v v
   > > > .

final mean return (last 500 eps):  sarsa=-6.58   q-learning=-6.59
(optimal return on this 4x4 GridWorld = -6.0)
```

逐项解读：

- **学习曲线**：第 1 块（前 500 回合）平均 -9.4，包含早期的摸索；第 2 块起就稳定在 -6.6 左右——比 MC 快得多（上一节 MC 用了数万回合）。讲义说"两者在约 2000 回合后接近最优"，这里更快，因为环境很小且确定。
- **两者几乎一样**：这个 GridWorld 没有悬崖之类的"探索惩罚"，Q-learning 和 SARSA 的差别体现不出来。要看到差别，需要讲义练习 2 的悬崖行走（测验 Q11 实测：Q-learning 在线回报 -43、SARSA -20.8）。
- **为什么停在 -6.6 而不是 -6**：训练回报包含 ε=0.1 的探索——每步有 7.5% 概率选非贪心动作。贪心策略本身是最优的。
- **两张策略图都是最优的**：所有只向下/向右的路径都是 6 步。
  - Q-learning 收敛到 `Q*`，向下与向右的 Q 值精确相等（另行实测 `(0,0)` 处 down 与 right 都是 -5.852），平局时 `max` 取排在前面的 down，所以几乎全是 `v`；最下面一行向下会撞墙，才是 `>`。
  - SARSA 学的是 ε-greedy 策略的 `Q^π`，不同方向的值有细微差别，箭头更"杂"，但同样都是最短路径。另行实测 SARSA 的 `max Q(0,0) ≈ -6.24`，低于 `V*(0,0) ≈ -5.85`——它把探索代价算进了价值。
- **与 DP 对比**（讲义 Step 4）：另行实测 3000 回合后，Q-learning 在每个状态上 `max_a Q` 与 `V*` 的差小于 0.001；`max|Q − Q*|` 约 0.59，来自很少被尝试的动作（如 `(0,2)` 的 left）。

---

## 7. 动手改一改

1. 讲义练习 1：把 `block_means` 的块大小改为 100，打印前 2000 回合的学习曲线，比较两者谁先接近 -6.6。
2. 增加一个 `evaluate(Q)` 函数：用 ε=0 的贪心策略从 `(0,0)` 跑一局，确认回报恰好是 -6。
3. 加入 ε 衰减：`epsilon = max(0.01, 0.995 ** episode)`，观察最后 500 回合的平均回报是否接近 -6。
4. 实现 Expected SARSA：目标改为 `r + γ Σ_a' π(a'|s') Q(s',a')`，其中贪心动作概率 `1 − ε + ε/4`、其他动作 `ε/4`。
5. 讲义练习 2：实现 4×12 悬崖行走，比较两者的贪心路线与在线回报（参考测验 Q11）。
6. 讲义练习 3：给每步奖励加 `rng.gauss(0, 5)` 噪声，比较 Q-learning 与 Double Q-learning 对 `V*(0,0)` 的估计，观察最大化偏差。

---

## 8. 常见坑

- **SARSA 里 a' 选了却不执行**：在下一轮开头重新选动作，会让目标里的 a' 与实际执行的动作不一致，破坏 on-policy 性质。
- **终止步仍然自举**：`done` 时如果写 `r + γ max Q(s', ·)`，在 Q 非零初始化时会把终止态的虚假价值带进来。
- **把截断当终止**：步数上限导致的结束不是真正的终止，目标里应保留 `γV(s')`。
- **训练回报 ≠ 策略好坏**：ε-greedy 的训练回报包含探索代价，评估要用贪心策略单独跑。
- **状态不可哈希**：用列表或 NumPy 数组当状态会报 `TypeError: unhashable type`；用元组，连续值先离散化或取整（讲义 Pitfalls）。
- **忽视 tie-break**：Q 值相等时策略看起来"偏向某个方向"，往往只是平局规则造成的，并不代表算法有偏好。
