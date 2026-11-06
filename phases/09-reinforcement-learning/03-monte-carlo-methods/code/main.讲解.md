# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 03 节 Monte Carlo 方法——从完整回合中学习 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 1–2 秒） ｜ **依赖**：仅 Python 标准库（`random`、`collections.defaultdict`）

---

## 1. 这份代码在考察什么

前两节都"偷看"了环境模型；这一节开始，智能体**只能跑回合、看回报**。代码做两件事：

1. **MC 策略评估**：用 20000 个随机回合的平均回报估计 `V^π`，并与第 01 节用 Bellman 方程算出的精确值对比——体会"采样代替求和"的代价（采样误差 + 截断偏差）。
2. **MC 控制**：ε-greedy + 采样平均更新 Q，从零学出一条最优路径——体会探索的必要性和"只在常去的状态上可靠"的局限。
3. **三个可复用的积木**：`rollout`（交互循环）、`returns_from`（反向算回报）、增量均值更新 `V += (G − V)/n`。后面 REINFORCE、PPO 都会再用到前两个。

> 一句话：**MC = 跑完一整局，再回头给每一步算总账**；不需要模型，但需要回合能结束、需要足够的样本和探索。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GRID`、`TERMINAL`、`ACTIONS`、`DELTAS` | 常量 | 与第 01 节相同的确定性 4×4 GridWorld | 环境 |
| `reset()` / `step(state, action)` | 函数 | 极简的 gym 风格接口 | 只能采样、不能查询模型 |
| `rollout(policy, rng, max_steps)` | 函数 | 跑一个回合，返回 `[(s, a, r), ...]` | 轨迹 |
| `returns_from(trajectory, gamma)` | 函数 | 反向扫描计算每一步的 `G_t` | 回报 |
| `uniform_policy(_state, rng)` | 函数 | 随机选一个动作 | 被评估的策略 π |
| `mc_policy_evaluation(...)` | 函数 | first-visit MC 估计 `V^π` | MC 预测 |
| `mc_control(...)` | 函数 | ε-greedy MC 控制，返回 Q、贪心策略、回报日志 | MC 控制 |
| `print_V` / `print_policy` | 函数 | 打印价值表与箭头策略（未访问的状态打印 `?`） | — |
| `main()` | 函数 | 先评估、再控制 | — |

数据流：`mc_* → rollout → policy + step`，得到轨迹后 `returns_from` 计算回报，再用增量均值更新 `V` 或 `Q`。注意 MC **只在回合结束后**才更新估计。

---

## 3. 逐段精讲

### 3.1 环境：只暴露 `reset` 和 `step`

```python
def reset():
    return (0, 0)


def step(state, action):
    if state == TERMINAL:
        return state, 0.0, True
    dr, dc = DELTAS[action]
    r, c = state
    nr = min(max(r + dr, 0), GRID - 1)
    nc = min(max(c + dc, 0), GRID - 1)
    return (nr, nc), -1.0, (nr, nc) == TERMINAL
```

- 环境与第 01 节完全相同（确定性、每步 -1、终点吸收），所以 `V^π(0,0)` 的精确值就是第 01 节算出的 -39.41。
- 讲义强调：MC "No model, only `env.reset()` and `env.step(s, a)`"。代码里 MC 函数**从不调用**任何"列出所有后继"的函数，这是与第 02 节 `transitions` 的本质区别。
- ⚠️ 简化：`step` 需要调用方传入 `state`（环境本身不保存状态），真实的 Gymnasium 环境是有状态对象 `env.step(action)`。

### 3.2 `rollout`：交互循环

```python
def rollout(policy, rng, max_steps=200):
    trajectory = []
    state = reset()
    for _ in range(max_steps):
        action = policy(state, rng)
        state_next, reward, done = step(state, action)
        trajectory.append((state, action, reward))
        state = state_next
        if done:
            break
    return trajectory
```

- 记录的三元组是 `(s_t, a_t, r_{t+1})`：动作发生时的状态、选的动作、这一步得到的奖励。终止状态本身不记录（它没有动作）。
- 策略签名是 `policy(state, rng)`，把随机数生成器传进去，保证可复现。
- ⚠️ `max_steps=200` 截断：被截断的回合**没有真正结束**，但 `returns_from` 会把它当作"后面奖励为 0"。随机策略约 2% 的回合被截断，导致估计偏乐观约 0.1（讲义 Pitfalls："make sure you count it correctly"）。

### 3.3 `returns_from`：反向一遍算出所有回报

```python
def returns_from(trajectory, gamma):
    returns = []
    G = 0.0
    for _, _, r in reversed(trajectory):
        G = r + gamma * G
        returns.append(G)
    returns.reverse()
    return returns
```

- 递推 `G_t = r_{t+1} + γ G_{t+1}`，从末尾往前算，每步 O(1)，整条轨迹 O(T)。若正向对每个 t 重新求和，是 O(T²)。
- `reversed(trajectory)` 返回一个反向迭代器（不复制列表）；`for _, _, r in ...` 用 `_` 丢掉状态和动作。
- 最后 `returns.reverse()` 原地翻转，让 `returns[t]` 与 `trajectory[t]` 对齐，后面用 `zip` 配对。
- 例：三步奖励都是 -1、γ=0.9 → `[-2.71, -1.9, -1.0]`。

### 3.4 `mc_policy_evaluation`：first-visit + 增量均值

```python
def mc_policy_evaluation(policy, episodes, gamma=0.99, rng=None):
    rng = rng or random.Random(0)
    V = defaultdict(float)
    counts = defaultdict(int)
    for _ in range(episodes):
        trajectory = rollout(policy, rng)
        returns = returns_from(trajectory, gamma)
        seen = set()
        for (s, _, _), G in zip(trajectory, returns):
            if s in seen:
                continue
            seen.add(s)
            counts[s] += 1
            V[s] += (G - V[s]) / counts[s]
    return V, counts
```

- **first-visit**：每个回合新建一个 `seen` 集合，同一状态只在第一次出现时计入。去掉 `seen` 就是 every-visit。
- **增量均值** `V += (G − V)/n`：数学上等于"所有样本的平均"，但不用存下所有回报；把 `1/n` 换成常数 α 就是讲义说的"通往 TD 的一步"。
- `defaultdict(float)` / `defaultdict(int)`：访问不存在的键时自动创建 0.0 / 0，省去 `if s not in V` 的判断。终点 `(3,3)` 从不出现在轨迹里，打印时读 `V[(3,3)]` 会自动得到 0.0——恰好就是终点的正确价值。
- `rng = rng or random.Random(0)`：调用方没传 rng 时用固定种子的默认值。
- `zip(trajectory, returns)` 把每一步和它的回报配对；`(s, _, _), G` 是**嵌套解包**。
- 返回 `counts` 方便检查访问次数：`(0,0)` 是起点，每个回合都访问，所以计数恰好等于回合数 20000。

### 3.5 `mc_control`：ε-greedy + 采样平均

```python
def mc_control(episodes, gamma=0.99, epsilon=0.1, rng=None):
    rng = rng or random.Random(0)
    Q = defaultdict(lambda: {a: 0.0 for a in ACTIONS})
    counts = defaultdict(lambda: {a: 0 for a in ACTIONS})

    def policy(state, local_rng):
        if local_rng.random() < epsilon:
            return local_rng.choice(ACTIONS)
        return max(Q[state], key=Q[state].get)

    returns_log = []
    for ep in range(episodes):
        trajectory = rollout(policy, rng)
        returns = returns_from(trajectory, gamma)
        seen = set()
        for (s, a, _), G in zip(trajectory, returns):
            if (s, a) in seen:
                continue
            seen.add((s, a))
            counts[s][a] += 1
            Q[s][a] += (G - Q[s][a]) / counts[s][a]
        if returns:
            returns_log.append(returns[0])
    greedy = {s: max(Q[s], key=Q[s].get) for s in Q}
    return Q, greedy, returns_log
```

- **嵌套 defaultdict**：`defaultdict(lambda: {a: 0.0 for a in ACTIONS})`，第一次访问某状态时自动生成"每个动作 Q=0"的小字典。工厂函数必须是可调用对象，所以要用 `lambda` 包一层。
- **内部函数 `policy` 是闭包**：它引用外层的 `Q` 和 `epsilon`；每次回合后 `Q` 被更新，`policy` 下次调用就自动用上新 Q——这就是"评估 → 改进"在代码中的样子（MC 控制 = 采样版策略迭代）。
- **ε-greedy**：以 ε 概率在**全部**动作中随机选（可能选中贪心动作本身），所以贪心动作的总概率是 `1 − ε + ε/4 = 0.925`。
- `max(Q[state], key=Q[state].get)`：遍历字典的键（动作），按 Q 值取最大。平局时返回第一个（`up`）。
- **以 `(s, a)` 为单位的 first-visit**：`seen` 存的是状态-动作对。
- **乐观初始化（隐含）**：奖励全是 -1，Q 初始为 0 比任何真实 Q 都高，所以没试过的动作看起来"最好"，会被贪心选中——这在 ε 之外又提供了一些探索。
- `returns_log` 记录每回合的 `G_0`（**折扣**回报）。
- ⚠️ 采样平均（`1/n`）对非平稳的策略不友好：早期坏策略产生的回报永远留在平均值里。讲义 Pitfalls 指出常数 α 可以缓解。
- ⚠️ `greedy` 只对 `Q` 中出现过的状态生成（defaultdict 访问过才有键）；`print_policy` 对缺失的状态打印 `?`。

### 3.6 `main`：评估 + 控制

```python
    rng = random.Random(1)
    V, counts = mc_policy_evaluation(uniform_policy, episodes=20000, gamma=0.99, rng=rng)
    # ...
    print(f"V(0,0) DP  reference   = -39.41   (from lesson 02 of this phase)")
    # ...
    _Q, greedy, log = mc_control(episodes=30000, gamma=0.99, epsilon=0.1, rng=rng2)
    # ...
    tail = log[-5000:]
```

- ⚠️ 参考值 `-39.41` 其实来自**第 01 节**（均匀随机策略的迭代策略评估），不是第 02 节（第 02 节算的是滑动环境中最优策略的 `V* ≈ -6.43`）。数值是对的，注释写错了。
- `_Q`：变量名以下划线开头，表示"接收了但不打算用"。
- `log[-5000:]` 取最后 5000 个回合，用来衡量训练后期的表现。
- ⚠️ 打印的 "optimal return = -6.0" 是**未折扣**的步数，而 `log` 里是 γ=0.99 的**折扣**回报；最优路径的折扣回报是 `-(1 + 0.99 + … + 0.99⁵) ≈ -5.85`。两者口径不同，对比时要注意。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用 `reset/step`，不用模型 | 体现 MC 的核心：只需采样 | 需要大量回合，方差大 |
| 反向扫描算回报 | O(T)，一次遍历 | 无 |
| first-visit | 样本独立、易分析，与讲义一致 | every-visit 每回合数据更多 |
| 采样平均 `1/n` | 对固定策略是精确均值、无偏 | MC 控制中策略在变，旧样本"拖后腿"；可改用常数 α |
| 固定 ε = 0.1 | 简单、保证持续探索 | 收敛到的是最优 ε-soft 策略；生产中常用 ε 衰减（GLIE） |
| Q 初始化为 0（奖励为负） | 写法最简单，碰巧形成乐观初始化 | 依赖奖励符号；奖励为正时就没有这个效果 |
| `max_steps=200` 截断 | 保证程序结束 | 引入截断偏差；应区分 terminated / truncated |
| `defaultdict` 存表 | 只为访问过的状态分配空间 | 大状态空间仍需函数近似 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from collections import defaultdict` | 文件开头 | 从标准库模块中导入单个名字 |
| `defaultdict(float)` / `defaultdict(int)` | `V = defaultdict(float)` | 访问不存在的键时自动用 `float()`=0.0 / `int()`=0 填充 |
| `defaultdict(lambda: ...)` | `defaultdict(lambda: {a: 0.0 for a in ACTIONS})` | 默认值是"可变对象"时要用工厂函数，每个键得到独立的新字典 |
| `set()` 集合 | `seen = set()`、`seen.add((s, a))`、`if s in seen` | O(1) 成员判断；元素必须可哈希（元组可以） |
| `reversed(...)` | `for _, _, r in reversed(trajectory)` | 返回反向迭代器，不复制列表 |
| `list.reverse()` | `returns.reverse()` | 原地翻转，返回 `None`（不要写 `x = x.reverse()`） |
| 嵌套解包 | `for (s, _, _), G in zip(trajectory, returns)` | 一次拆开 `((s, a, r), G)` 两层结构 |
| `or` 提供默认值 | `rng = rng or random.Random(0)` | `rng` 为 `None` 时取右边；注意任何"假值"都会被替换 |
| 内部函数 / 闭包 | `def policy(state, local_rng): ... Q[state] ...` | 内部函数可以读取外层函数的局部变量，并看到它们之后的变化 |
| `dict.get` 作为 key 函数 | `max(Q[state], key=Q[state].get)` | 按值取最大的键，即 argmax |
| `rng.choice(seq)` | `rng.choice(ACTIONS)` | 从序列中等概率随机选一个 |
| 列表切片取尾部 | `log[-5000:]` | 负数索引从末尾数起 |
| 条件表达式嵌套 | `arrows[...] if ... else ("." if ... else "?")` | 一行多分支；可读性一般，复杂时建议改写成函数 |
| `_` 前缀变量 | `_Q, greedy, log = mc_control(...)`、参数 `_state` | 约定：不使用的变量 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 1.3 秒）的输出：

```text
=== first-visit MC, uniform-random policy, 20000 episodes, gamma=0.99 ===
  V^pi(s)
    -38.89  -37.56  -35.77  -33.94
    -37.69  -35.80  -32.76  -29.75
    -35.69  -32.72  -26.93  -19.80
    -33.78  -29.63  -19.86    0.00

V(0,0) MC estimate     = -38.89
V(0,0) DP  reference   = -39.41   (from lesson 02 of this phase)
visit counts at (0,0)  = 20000

=== epsilon-greedy MC control, 30000 episodes ===
  greedy policy recovered
   > v < <
   > > v v
   > > > v
   > > > .

mean return over last 5000 episodes = -6.54
(optimal return on this 4x4 GridWorld = -6.0)
```

逐项解读：

- **MC 价值表**与第 01 节 γ=0.99 的精确表（`-39.41 -38.19 -36.25 -34.64 …`）整体吻合，误差在 0.5–0.9 之间，而且**全部偏高**（偏乐观）：所有状态共用同一批回合，采样误差是相关的；200 步截断也让估计系统性偏乐观。注意精确表关于对角线**严格对称**，而 MC 表不对称（`(0,1)` 是 -37.56，`(1,0)` 是 -37.69）——这就是采样噪声的直接证据。
- **-38.89 vs -39.41**：差 0.52。单回合 `G_0` 标准差约 21，标准误约 0.15；另行用其他种子测得 -39.29、-39.26、-39.17、-38.71，说明种子 1 偏高一些。另外约 0.1 来自 200 步截断造成的乐观偏差。讲义说"5 万回合误差约 0.1"，与 `21/√50000 ≈ 0.09` 一致。
- **visit counts = 20000**：起点每个回合都会被访问一次（first-visit 只计一次）。
- **恢复的贪心策略**：从 `(0,0)` 按箭头 `> v > v > v` 走 6 步到终点，是一条最优路径。但 `(0,2)`、`(0,3)` 的箭头指向左——这两个状态在最终策略下几乎不被访问，它们的 Q 主要来自训练早期（策略很差时）的样本，采样平均又不会遗忘旧样本，所以估计不准。MC 控制只保证"常去的状态"上的策略可靠。
- **-6.54**：最后 5000 回合的平均**折扣**回报。最优路径的折扣回报是 -5.85，差距来自 ε=0.1 的探索：每一步仍有 7.5% 的概率选非贪心动作，偶尔多走几步。打印的 "-6.0" 是未折扣步数，口径不同。

---

## 7. 动手改一改

1. 讲义练习 1：每 500 个回合记录一次 `V[(0,0)]`，画出它随回合数逼近 -39.41 的曲线，观察误差大致按 `1/√n` 缩小。
2. 删掉 `mc_policy_evaluation` 中的 `seen` 判断，改成 every-visit，比较 `(0,0)` 的访问计数（会变成十几万）和估计值。
3. 把 `rollout` 改成返回"是否被截断"，在 `mc_policy_evaluation` 中丢弃被截断的回合，看估计值是否更接近 -39.41。
4. 讲义练习 2：分别用 `epsilon ∈ {0.01, 0.1, 0.3}` 跑 `mc_control`，比较最后 5000 回合的平均回报和恢复出的策略，体会探索太少（Q 不准）与探索太多（执行代价高）的权衡。
5. 把 `mc_control` 中的 `/ counts[s][a]` 换成常数 `α = 0.05`，看 `(0,2)`、`(0,3)` 的箭头是否被纠正。
6. 讲义练习 3：用均匀随机的行为策略估计一个确定性目标策略的 `V^π(0,0)`，实现普通 IS 与加权 IS 并比较方差（参考答案见测验 Q11）。

---

## 8. 常见坑

- **截断当作终止**：被 `max_steps` 截断的回合，其回报缺了尾巴，估计会系统性偏乐观。
- **`returns` 忘记翻转**：`zip(trajectory, returns)` 会把第一步配上最后一步的回报，结果完全错误却不报错。
- **`defaultdict` 的副作用**：在 `policy` 里读 `Q[state]` 也会**创建**新键；打印或统计 Q 的大小时要意识到这一点。
- **用可变对象做默认值**：写成 `defaultdict({a: 0.0 for a in ACTIONS})` 会直接报错（需要可调用对象）；若共享同一个字典，所有状态会互相污染，必须用 `lambda` 每次新建。
- **比较口径不一致**：折扣回报 vs 未折扣步数、不同小节的参考值，比较前先确认 γ 和环境是否相同。
- **纯贪心不探索**：把 `epsilon` 设为 0，学到的策略可能很差，而且路径外状态的 Q 几乎没有样本。
