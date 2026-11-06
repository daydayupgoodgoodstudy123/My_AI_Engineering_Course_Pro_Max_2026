# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 11 节 从仿真到现实的迁移 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 0.2 秒跑完） ｜ **依赖**：仅 Python 标准库（`random`、`collections.defaultdict`）

---

## 1. 这份代码在考察什么

讲义说这份代码是"a tiny demonstration of domain randomization on a GridWorld with noisy transitions"。它用"打滑概率 slip"模拟仿真与现实之间的参数差异：

1. **参数化的仿真器**：`step(state, action, slip, rng)` 暴露一个物理参数 `slip`（在真实机器人中可以是摩擦、质量、电机增益）。
2. **两种训练方式**：策略 A 只在 `slip=0` 的"完美仿真"里训练；策略 B 每回合从 `Uniform[0, 0.3]` 采样 slip——这就是 Domain Randomization。
3. **零样本评估**：在一组"真实" slip 上评估两个策略，其中 0.5、0.7 在 DR 的训练范围之外（OOD）。
4. **同等算力对比**：两者都训练 3000 回合、同样的超参和种子。

> 一句话：**DR = 训练时把"仿真是哪一个"也当成随机变量。** 但读完本文你会发现：这个具体的环境其实**没能**展示出 DR 的优势——理解"为什么没有"，比代码本身更有价值。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GRID / TERMINAL / ACTIONS / DELTAS` | 常量 | 5×5 网格，终点 (4,4) | 环境定义 |
| `step(state, action, slip, rng)` | 函数 | 以概率 `slip` 把动作换成垂直方向之一，每步 -1 | 参数化仿真器 |
| `default_q` / `epsilon_greedy` | 函数 | Q 表默认值、ε-贪心 | 表格 Q-learning 基础件 |
| `train_fixed(slip, ...)` | 函数 | 固定 slip 训练 3000 回合 | 无 DR 的基线（策略 A） |
| `train_dr(slip_low, slip_high, ...)` | 函数 | 每回合采样 slip 训练 | Domain Randomization（策略 B） |
| `evaluate(Q, slip, ...)` | 函数 | 贪心策略在给定 slip 下跑 200 回合求平均回报 | 零样本"真机"评估 |
| `main()` | 函数 | 训练两个策略，在 6 个 slip 上对比打印 | 演示入口 |

数据流：`main` → `train_fixed(0.0)` 与 `train_dr(0.0, 0.3)`（各自用 `Random(1)`）→ 对每个 slip 调用两次 `evaluate` → 打印对比表。

---

## 3. 逐段精讲

### 3.1 参数化的"仿真器"

```python
def step(state, action, slip, rng):
    if state == TERMINAL:
        return state, 0.0, True
    if rng.random() < slip:
        perp = ("left", "right") if action in ("up", "down") else ("up", "down")
        action = rng.choice(perp)
    dr, dc = DELTAS[action]
    r, c = state
    nr = min(max(r + dr, 0), GRID - 1)
    nc = min(max(c + dc, 0), GRID - 1)
    return (nr, nc), -1.0, (nr, nc) == TERMINAL
```

- 以概率 `slip`，实际执行的动作被换成与意图**垂直**的两个方向之一（各 `slip/2`）。这就是讲义 Step 1 的 `random_perpendicular(action)`。例如选 `right`、slip=0.3：实际右 0.7、上 0.15、下 0.15。
- `rng` 作为参数传入而不是用全局 `random`：训练和评估可以使用彼此独立、可复现的随机流。
- 撞墙原地不动（clamp），每步奖励 -1，到达 (4,4) 结束。最优回报在 slip=0 时为 -8（曼哈顿距离 8）。
- 设计意图：`slip` 是一个"仿真与现实可能不同"的物理参数。真实机器人里它对应摩擦系数、质量、电机增益等。

### 3.2 两种训练：固定参数 vs 随机参数

```python
def train_fixed(slip, episodes=3000, alpha=0.1, gamma=0.95, eps=0.15, rng=None):
    rng = rng or random.Random(0)
    Q = defaultdict(default_q)
    for _ in range(episodes):
        s = (0, 0)
        for _ in range(100):
            a = epsilon_greedy(Q, s, rng, eps)
            s_next, r, done = step(s, a, slip, rng)
            if done:
                Q[s][a] += alpha * (r - Q[s][a])
                break
            best_next = max(Q[s_next].values())
            Q[s][a] += alpha * ((r + gamma * best_next) - Q[s][a])
            s = s_next
    return Q
```

```python
def train_dr(slip_low, slip_high, episodes=3000, alpha=0.1, gamma=0.95, eps=0.15, rng=None):
    ...
    for _ in range(episodes):
        slip_ep = rng.uniform(slip_low, slip_high)
        ...
            s_next, r, done = step(s, a, slip_ep, rng)
```

- 两个函数**唯一的区别**是 `train_dr` 在每个回合开头用 `rng.uniform(slip_low, slip_high)` 抽一个 `slip_ep`，整个回合内保持不变——对应讲义 Step 2："At the start of each episode, sample slip ~ Uniform[0.0, 0.4]"（讲义写的是 0.4，代码用的是 0.3，以代码为准）。
- 学习算法是标准表格 Q-learning（第 04 节）：终止步目标为 `r`，否则为 `r + γ·max Q(s')`。讲义说"Train PPO / Q-learning / anything"——DR 与具体算法无关，它只改变训练数据的分布。
- 注意 Q 表**看不到** slip 的值：策略必须对所有 slip 用同一套动作。这是 DR 的标准设定——学到一个对参数分布"平均最优"的鲁棒策略。另一种思路是把参数（或其估计）作为输入，即讲义中的 teacher-student / 从历史推断参数。
- ⚠️ 两个函数代码几乎完全重复。工程上会写成一个函数 + "参数采样器"（如传入 `sample_slip=lambda rng: 0.0`），这样换成 ADR 课程也只需换采样器。

### 3.3 零样本评估

```python
def evaluate(Q, slip, episodes=200, rng=None):
    rng = rng or random.Random(42)
    total = 0.0
    for _ in range(episodes):
        s = (0, 0)
        ep_total = 0.0
        for _ in range(100):
            a = max(ACTIONS, key=lambda a: Q[s][a])
            s, r, done = step(s, a, slip, rng)
            ep_total += r
            if done:
                break
        total += ep_total
    return total / episodes
```

- 贪心策略（无探索）、未折扣回报、最多 100 步、200 回合平均。
- ⚠️ 每次调用都用新的 `Random(42)`，两个策略面对**完全相同的随机事件序列**（`step` 每步调用随机数的次数与动作无关）。这让对比"配对"了，降低了噪声；但也意味着结果只代表一条随机流，严格比较应使用多个评估种子并报告置信区间。
- `lambda a: Q[s][a]` 里的参数名 `a` 与外层变量 `a` 同名，是合法的（lambda 有自己的作用域），但可读性一般，最好换个名字。

### 3.4 主函数：同算力、同种子的对比

```python
    rng = random.Random(1)
    Q_fixed = train_fixed(0.0, rng=rng)
    rng = random.Random(1)
    Q_dr = train_dr(0.0, 0.3, rng=rng)
    ...
    for slip in (0.0, 0.1, 0.2, 0.3, 0.5, 0.7):
        r_fixed = evaluate(Q_fixed, slip)
        r_dr = evaluate(Q_dr, slip)
        label = ""
        if slip <= 0.3:
            label = "(in-support for DR)"
        else:
            label = "(OOD for DR)"
```

- 两次训练前都重置 `Random(1)`，保证"同样的计算预算和起点"。
- 评估 slip 覆盖训练支撑集内（0~0.3）和支撑集外（0.5、0.7），对应讲义 Step 3。
- `label = ""` 的初始赋值是多余的（后面 if/else 一定会覆盖），可以简化为条件表达式 `label = "(in-support for DR)" if slip <= 0.3 else "(OOD for DR)"`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 slip 模拟物理参数 | 一个标量就能表达"仿真与现实不同" | 真实 DR 同时随机化几十个参数（质量、摩擦、增益、延迟、噪声、视觉） |
| 每回合采样一次 slip | 与讲义一致，模拟"今天是哪个仿真" | 大规模并行仿真中每个环境各自一组参数 |
| 策略看不到 slip | 学习鲁棒的"平均"策略 | 教师-学生方法让学生从历史中推断参数 |
| 表格 Q-learning | 快、透明 | 生产中用 PPO + 数千并行环境 |
| 评估共享同一随机种子 | 配对比较，降低噪声 | 应多种子评估并报告方差 |
| ⚠️ 空旷网格作为任务 | 简单 | 最优策略与 slip 无关，DR 无从发挥（见第 6 节） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块常量与元组 | `TERMINAL = (GRID - 1, GRID - 1)` | 常量可以由其他常量计算 |
| 条件表达式选元组 | `("left", "right") if action in ("up", "down") else ("up", "down")` | `in` 判断成员，三元表达式二选一 |
| `rng.random()` / `rng.choice()` / `rng.uniform()` | `rng.uniform(slip_low, slip_high)` | `[0,1)` 均匀数、随机选元素、区间均匀数 |
| `collections.defaultdict` | `Q = defaultdict(default_q)` | 首次访问状态时自动建全 0 的动作值字典 |
| 字典推导式 | `{a: 0.0 for a in ACTIONS}` | 构造动作值字典 |
| `max(..., key=lambda ...)` | `max(ACTIONS, key=lambda a: Q[s][a])` | 求 argmax |
| `x or default` | `rng = rng or random.Random(0)` | 默认参数 |
| 链式 `min(max(...))` | `min(max(r + dr, 0), GRID - 1)` | 把坐标夹在 `[0, GRID-1]` |
| f-string 宽度与对齐 | `f"  {'slip':<10}{'fixed-slip policy':<22}"`、`f"{slip:<10.2f}"` | `<10` 左对齐宽 10；`<10.2f` 左对齐且两位小数 |
| f-string 里嵌套引号 | `f"{'slip':<10}"` | 外层双引号、内层单引号 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13，约 0.2 秒）输出：

```text
=== sim-to-real: train in 'sim', evaluate on 'real' ===
env: 5x5 GridWorld, slip = probability of perpendicular slip

training two policies with same compute budget:
  policy A: fixed slip = 0.0 (no domain randomization)
  policy B: slip ~ Uniform[0.0, 0.3] (domain randomization)

evaluation on 'real' slips (each 200 episodes greedy eval):
  slip      fixed-slip policy     DR-trained policy     
  0.00      -8.00                 -8.00                 (in-support for DR)
  0.10      -8.78                 -8.78                 (in-support for DR)
  0.20      -10.05                -9.78                 (in-support for DR)
  0.30      -11.35                -11.04                (in-support for DR)
  0.50      -16.72                -15.78                (OOD for DR)
  0.70      -28.73                -28.73                (OOD for DR)

takeaway: DR-trained policy degrades gracefully; fixed-slip policy is brittle out-of-distribution.
```

逐行解读：

- **slip=0.00**：两者都是 -8.00，都学到了最优的 8 步路线。
- **slip 增大时两者同步下降**：-8 → -8.8 → -10 → -11 → -16 → -29。差距最多约 0.9，slip=0.7 时完全相同。
- **为什么几乎一样**：实测两张 Q 表的贪心动作在**每个格子都是 `down` 或 `right`**——都是最优策略，只是并列的最短路线选择不同。在空旷网格中，最优策略与 slip 无关：打滑只会随机把你推偏，没有任何"更稳妥的路线"可以规避。回报下降几乎完全由物理决定：每步净前进期望约 `1 - slip`，期望步数约 `8/(1 - slip)`（slip=0.3 时约 11.4，slip=0.5 时 16，slip=0.7 时约 26.7），与表中数值吻合。
- **最后一行 takeaway 言过其实**：讲义 Step 4 说固定策略会"catastrophic drop"，但这组数据并不支持——换训练种子 1、2、3 重复，slip=0.7 时 DR 策略为 -28.73、-28.54、-29.68，固定策略都是 -28.73，DR 有时反而更差。两列差异处于随机噪声的量级。
- **怎样才能看到 DR 的作用**：环境中必须存在"最优行为依赖于参数"的结构。例如把底行中间三格改成悬崖（掉下去 -20）：固定 slip=0 的策略学会紧贴悬崖走（slip=0 时 -6），DR 策略学会绕远一点（slip=0 时 -8，体现讲义所说的"overly cautious"）；但在 slip=0.1~0.3 时 DR 稳定更好（例如 slip=0.3 时约 -15.2 vs -16.4~-16.9），slip=0.5（超出训练范围）时 DR 又不再占优。完整代码与数据见测验 Q11。

---

## 7. 动手改一改

1. **讲义练习 Easy/Medium**：在 slip ∈ {0.0, 0.1, 0.3, 0.5} 上画出两种策略的回报曲线；用 5 个训练种子 × 5 个评估种子，报告均值和标准差，判断差异是否显著。
2. **悬崖环境**：按测验 Q11 加入悬崖，重复对比，观察 DR 的"保守代价"和"鲁棒收益"。
3. **过度随机化**：在悬崖环境中把 DR 范围改成 `[0, 0.9]`，观察策略是否变得极度保守（讲义 Pitfalls："so risk-averse it never tries the optimal path"）。
4. **ADR 课程**（讲义练习 Hard）：从 `slip_high = 0` 开始，每 100 回合在当前上界评估一次，达标就把上界加 0.05，直到 0.3；统计达到目标所需的环境步数，与固定 DR 基线比较。
5. **把参数作为输入**：让 Q 表的键变成 `(s, round(slip_ep, 1))`，训练"知道自己在哪个仿真"的策略；再思考真机上 slip 未知时如何从历史中估计它——这就是教师-学生方法的雏形。
6. **合并重复代码**：把 `train_fixed` 与 `train_dr` 合成一个 `train(sample_slip, ...)`，其中 `sample_slip` 是一个函数。

---

## 8. 常见坑

- **用"一定能赢"的环境演示 DR**：如果最优策略与随机化的参数无关，DR 不可能带来收益，看到的差异只是噪声。先问：这个参数会改变最优行为吗？
- **单种子下结论**：本代码的每个结论都来自一个训练种子 + 一个评估种子；在 RL 中这远远不够。
- **共享随机流的错觉**：两个策略用同一个 `Random(42)` 评估会出现"完全相同"的数字，这不代表策略等价。
- **随机化的范围与维度**：范围太宽 → 过度保守；随机化了错误的维度 → 无效（讲义：随机化相机色调而真正的差距是电机延迟）。
- **把 OOD 表现当作承诺**：DR 只在训练支撑集附近有保证；超出范围（slip=0.5、0.7）没有任何理论保障。
- **讲义与代码参数不一致**：讲义写 DR 范围 `[0.0, 0.4]`，代码用 `[0.0, 0.3]`；阅读输出时以代码为准。
