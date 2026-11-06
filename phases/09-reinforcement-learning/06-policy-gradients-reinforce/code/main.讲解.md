# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 06 节 Policy Gradient — REINFORCE 从头开始 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，不到 1 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

前五节都在学"价值"，再从价值里挑动作；这一节**直接学策略**。代码用一个线性 softmax 策略在同一个 4×4 GridWorld 上实现 REINFORCE，并对比"不带基线"和"带滑动平均基线"两个版本：

1. **策略参数化**：每个动作一行权重，`logits = θ·x`，`π = softmax(logits)`。
2. **采样与记录**：rollout 时把每一步的 `(x, a, r, probs)` 存下来，供事后计算梯度。
3. **REINFORCE 核心公式**：`θ += lr · G_t · ∇log π(a_t|s_t)`，其中 softmax 的梯度是 `e_a − π`（讲义："Burn it into muscle memory."）。
4. **Reward-to-go**：用从 t 开始的回报 `G_t`，而不是整条轨迹的总回报。
5. **基线**：减去回报的滑动平均，降低方差。

> 一句话：**让好结果对应的动作更可能发生、坏结果对应的动作更不可能发生**——`loss = −advantage · log_prob` 这一行，就是 PPO、GRPO 的祖先。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GRID`…`step(state, action_idx)` | 常量 / 函数 | 确定性 GridWorld，动作用下标 0–3 | 环境 |
| `features(state)` | 函数 | 16 维 one-hot | 状态特征 x |
| `init_theta(rng)` | 函数 | 4×16 的权重矩阵，`N(0, 0.1)` 初始化 | 策略参数 θ |
| `logits(theta, x)` | 函数 | 每个动作一个打分 `θ_a · x` | `f_θ(s, a)` |
| `softmax(z)` | 函数 | 数值稳定的 softmax | `π_θ(a\|s)` |
| `sample(probs, rng)` | 函数 | 按概率抽动作下标 | 从 π 采样 |
| `rollout(theta, rng, max_steps)` | 函数 | 跑一个回合，记录 `(x, a, r, probs)` | 轨迹 τ |
| `returns_to_go(traj, gamma)` | 函数 | 反向计算 `G_t` | reward-to-go |
| `reinforce(episodes, lr, gamma, use_baseline, rng)` | 函数 | 训练主循环 | REINFORCE（± 基线） |
| `greedy_policy` / `print_policy` / `block_mean` | 函数 | 提取 argmax 策略、打印、分块平均 | 结果展示 |
| `main()` | 函数 | 同一种子下训练两个版本并对比 | 对照实验 |

数据流：`reinforce` → `rollout`（`features` → `logits` → `softmax` → `sample` → `step`）→ `returns_to_go` → 逐步累加梯度到 `theta`。

---

## 3. 逐段精讲

### 3.1 策略：线性打分 + softmax

```python
def init_theta(rng):
    return [[rng.gauss(0, 0.1) for _ in range(N_FEAT)] for _ in range(N_ACTIONS)]


def logits(theta, x):
    return [sum(w * xi for w, xi in zip(theta[a], x)) for a in range(N_ACTIONS)]


def softmax(z):
    m = max(z)
    exps = [math.exp(zi - m) for zi in z]
    Z = sum(exps)
    return [e / Z for e in exps]
```

- `theta` 是 4×16：第 a 行是动作 a 的权重向量。输入是 one-hot，所以 `logits[a] = theta[a][状态编号]`——本质上是一个"每个状态每个动作一个分数"的表格策略。讲义："Use a linear policy (one weight vector per action) for a tabular env. For Atari, swap in a CNN and keep the softmax head."
- **数值稳定的 softmax**：先减去最大值 `m` 再取 `exp`。数学上不改变结果（分子分母同乘 `e^{-m}`），但避免了 `exp(1000)` 溢出。
- 初始化标准差 0.1 很小，初始策略接近均匀随机，保证一开始有足够的探索。

### 3.2 采样与 rollout：把 `probs` 一起存下来

```python
def sample(probs, rng):
    x = rng.random()
    cum = 0.0
    for a, p in enumerate(probs):
        cum += p
        if x <= cum:
            return a
    return N_ACTIONS - 1


def rollout(theta, rng, max_steps=100):
    traj = []
    s = reset()
    for _ in range(max_steps):
        x = features(s)
        probs = softmax(logits(theta, x))
        a = sample(probs, rng)
        s_next, r, done = step(s, a)
        traj.append((x, a, r, probs))
        if done:
            break
        s = s_next
    return traj
```

- `sample` 是逆累积分布采样（第 01 节讲过）；兜底返回最后一个动作，防止浮点累加不到 1。
- **记录 `probs`**：计算梯度 `e_a − π` 需要采样时的概率分布。事先存好，更新时就不必再做一次前向，而且保证梯度是在**采样时的参数** θ_old 处计算的（见 3.4）。
- 存的是特征 `x` 而不是状态元组，因为更新公式里要乘 `x[j]`。
- ⚠️ `max_steps=100` 截断：没走到终点的回合也会被拿来更新，回报为 `-(1 − 0.99¹⁰⁰)/0.01 ≈ -63.4`。

### 3.3 `returns_to_go`：反向计算回报

```python
def returns_to_go(traj, gamma):
    G = 0.0
    out = []
    for _, _, r, _ in reversed(traj):
        G = r + gamma * G
        out.append(G)
    out.reverse()
    return out
```

- 与第 03 节的 `returns_from` 完全相同：`G_t = r_{t+1} + γG_{t+1}`，O(T)。
- 这里的 `G_t` 就是讲义说的 **reward-to-go**：只包含 t 及之后的奖励，因为动作 `a_t` 不可能影响之前已经拿到的奖励。

### 3.4 `reinforce`：核心更新

```python
def reinforce(episodes, lr=0.05, gamma=0.99, use_baseline=False, rng=None):
    rng = rng or random.Random(0)
    theta = init_theta(rng)
    baseline = 0.0
    returns_log = []
    for ep in range(episodes):
        traj = rollout(theta, rng)
        returns = returns_to_go(traj, gamma)
        if use_baseline:
            baseline = 0.95 * baseline + 0.05 * returns[0]
        for (x, a, _r, probs), G in zip(traj, returns):
            adv = G - (baseline if use_baseline else 0.0)
            for i in range(N_ACTIONS):
                grad = (1.0 if i == a else 0.0) - probs[i]
                for j in range(N_FEAT):
                    theta[i][j] += lr * adv * grad * x[j]
        returns_log.append(returns[0] if returns else 0.0)
    return theta, returns_log
```

逐项对应公式 `θ ← θ + lr · Σ_t (G_t − b) · ∇_θ log π_θ(a_t|s_t)`：

- **`grad = e_a − π`**：`(1.0 if i == a else 0.0) - probs[i]` 是 `∇_z log π(a|s)` 的第 i 个分量（z 为 logits）。由于 `z_i = θ_i · x`，链式法则再乘 `x[j]` 就得到 `∂log π/∂θ[i][j]`。
- **`+=` 是梯度上升**：我们要最大化 J，所以沿梯度方向走（PyTorch 里写成最小化 `−adv · log_prob`）。
- **逐步更新 = 整条轨迹一次更新**：每一步的增量只依赖 rollout 时记录的 `probs`、`x`、`a` 和预先算好的 `G`，与正在被修改的 `theta` 无关，所以逐步累加等价于"在 θ_old 处求整条轨迹的梯度再更新一次"。
- **one-hot 的效果**：`x[j]` 只有一个为 1，所以每一步只修改**当前状态那一列**的 4 个权重——更新是"局部"的，不会影响其他状态（与 DQN 一样，这让问题接近表格情形）。
- **基线**：`baseline` 是起点回报 `G_0` 的指数滑动平均（衰减 0.95）。
  - ⚠️ 它在计算优势**之前**就混入了当前回合的 `G_0`（权重 0.05），而 `G_0` 与本回合的动作相关，严格来说会给梯度引入少量偏差；规范写法是先用旧基线算优势，再更新基线。
  - ⚠️ 它是一个**与状态无关**的标量，却被减到每个时间步的 `G_t` 上。回合后期的 `G_t` 接近 0（例如 -1），而基线约等于整局回报（例如 -10），于是后期步骤的优势都是较大的正数，无论动作好坏都被抬高。这仍然无偏（常数基线），但降方差效果有限；更好的做法是状态相关的基线 `V̂(s)`——这正是下一节 Actor-Critic 的出发点。
- `returns_log` 记录 `returns[0]`，即**折扣后**的起点回报。⚠️ 与 `main` 中打印的未折扣 "-6.0" 口径不同（见第 6 节）。
- ⚠️ 没有回报归一化、没有熵奖励、没有梯度裁剪。讲义 Pitfalls 建议总是把 G 归一化；不做的后果见第 6 节和第 8 节。

### 3.5 `greedy_policy`：只看 argmax

```python
def greedy_policy(theta):
    policy = {}
    for r in range(GRID):
        for c in range(GRID):
            if (r, c) == TERMINAL:
                continue
            z = logits(theta, features((r, c)))
            policy[(r, c)] = ACTIONS[max(range(N_ACTIONS), key=lambda i: z[i])]
    return policy
```

- softmax 是单调的，logits 的 argmax 就是概率的 argmax，所以不必真的算 softmax。
- 训练时用的是**随机策略**（按概率采样），贪心策略只是用于展示"最可能的动作"。

### 3.6 `main`：对照实验

```python
    episodes = 2000
    rng = random.Random(42)
    _, r_plain = reinforce(episodes, use_baseline=False, rng=rng)
    rng = random.Random(42)
    theta_b, r_base = reinforce(episodes, use_baseline=True, rng=rng)
```

- 两个版本使用同一种子的新生成器，初始参数完全相同（`init_theta` 先消耗随机数）。
- 打印每 200 回合的平均回报、带基线版本的贪心策略、最后 200 回合的均值。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 线性 softmax + one-hot | 等价于表格策略，梯度可以手写 | 无泛化；真实任务用神经网络 + 自动求导 |
| rollout 时存 `probs` | 梯度在 θ_old 处计算，逐步更新与批量更新等价 | 存储开销；框架中通常存 `log_prob` |
| 每个回合更新一次 | 最朴素的 REINFORCE | 方差大；生产中每次更新用一批回合 |
| reward-to-go | 正确且降方差（讲义："Always use reward-to-go"） | 无 |
| 标量滑动平均基线 | 实现最简单 | 与状态无关，后期步骤优势被系统性抬高；当前回合混入基线有轻微偏差；用 `V̂(s)` 更好 |
| 不归一化回报、lr=0.05 | 代码简短 | 回报量级几十时一步更新过大，部分随机种子会塌缩卡死（见第 6 节） |
| 省略 `γ^t` 因子 | 业界通行写法 | 严格来说优化的不是 `E[G_0]` 的精确梯度 |
| 回合上限 100 步 | 防止早期随机策略跑太久 | 截断回合的回报偏乐观 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import math` | `math.exp(zi - m)` | 标准库数学函数 |
| 模块级常量由其他常量推导 | `N_ACTIONS = len(ACTIONS)`、`N_FEAT = GRID * GRID` | 改一处，处处生效 |
| 列表乘法 | `x = [0.0] * N_FEAT` | 创建全零列表 |
| 嵌套列表推导式 | `[[rng.gauss(0, 0.1) for _ in range(N_FEAT)] for _ in range(N_ACTIONS)]` | 4×16 的二维列表 |
| 生成器表达式点积 | `sum(w * xi for w, xi in zip(theta[a], x))` | 手写向量内积 |
| `enumerate` | `for a, p in enumerate(probs)` | 同时得到动作下标和概率 |
| 条件表达式 | `(1.0 if i == a else 0.0)`、`(baseline if use_baseline else 0.0)` | 一行 if-else，这里构造 one-hot `e_a` |
| 嵌套解包 + 下划线 | `for (x, a, _r, probs), G in zip(traj, returns)` | `_r` 表示"取出但不用" |
| `reversed` + `list.reverse()` | `returns_to_go` 中 | 反向遍历、原地翻转 |
| 关键字参数与默认值 | `reinforce(episodes, lr=0.05, gamma=0.99, use_baseline=False, rng=None)` | 调用时可只改需要的参数，如 `use_baseline=True` |
| `rng or 默认值` | `rng = rng or random.Random(0)` | 未传入时使用固定种子 |
| 条件表达式防空列表 | `returns[0] if returns else 0.0` | 空列表时不越界（实际上轨迹至少有 1 步） |
| f-string 格式 | `f"{a:7.2f}"`、`{sum(r_plain[-200:])/200:.2f}` | 宽度与小数位 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.4 秒）的输出：

```text
=== REINFORCE on 4x4 GridWorld, 2000 episodes, lr=0.05, gamma=0.99 ===

learning curves (mean return per 200 episodes):
  block 1: vanilla= -10.03   with-baseline= -15.39
  block 2: vanilla=  -6.01   with-baseline=  -6.14
  block 3: vanilla=  -5.98   with-baseline=  -5.97
  ...
  block 10: vanilla=  -5.90   with-baseline=  -5.88

  final greedy policy (with-baseline)
   > > v ^
   < > > v
   < v > v
   ^ < ^ .

final mean return (last 200 eps): vanilla=-5.90   with-baseline=-5.88
(optimal return on this 4x4 GridWorld = -6.0)
```

逐项解读：

- **"比最优还好"是口径问题**：日志记录的是 γ=0.99 的折扣回报，最优 6 步路径的折扣回报是 `-(1 + 0.99 + … + 0.99⁵) ≈ -5.85`，而打印的 "-6.0" 是未折扣步数。-5.88 / -5.90 的含义是"非常接近最优的 -5.85"；剩下的差距来自策略仍保留的少量随机性。
- **收敛速度**：两个版本在第 2 块（200–399 回合）就接近最优，与讲义"约 500 回合"的说法量级一致。
- **基线在第 1 块反而更差（-15.39 vs -10.03）**：单个种子的结果，且标量基线从 0 开始、要几十个回合才"追上"真实回报水平，期间后期步骤的优势被系统性抬高。基线的好处主要体现在方差上：另行实测最后 200 回合回报的标准差，不带基线约 0.31、带基线约 0.17。
- **贪心策略图的"怪箭头"**：从起点出发的路径 `(0,0)>(0,1)>(0,2)v(1,2)>(1,3)v(2,3)v` 恰好 6 步，是最优的；但 `(0,3)`、`(1,0)`、`(2,0)`、`(3,0)`、`(3,1)`、`(3,2)` 的箭头明显不对。这些状态在训练后期几乎不会被访问，参数停留在初始化附近（实测 `(3,2)` 的概率约 `[0.262, 0.254, 0.241, 0.243]`），argmax 只是初始化噪声。on-policy 方法只在策略会去的状态上可靠。
- **种子敏感性（重要）**：种子 42 很顺利，但另行用种子 0–9 运行不带基线的版本，有 3 个种子在 2000 回合后仍卡在每回合 `-63.4`（100 步走不到终点）。例如种子 1：`(0,0)` 的 logits 变成 `[11.3, -1.9, -8.1, -1.0]`，几乎确定地选 `up` 撞墙，`e_a − π ≈ 0`，梯度消失、无法自救。原因是回报量级几十、lr=0.05，一次更新能让 logit 跳约 3，softmax 很快饱和。实测把 lr 降到 0.01 或对回报做归一化后，10 个种子全部收敛；只加熵奖励（β ≤ 0.1）不能解决（熵的梯度在饱和时同样趋于 0）。详见测验 Q10。

---

## 7. 动手改一改

1. 修正口径：在 `rollout` 中额外统计未折扣步数，或把打印的最优值改为 -5.85。
2. 讲义练习 1：记录不带基线版本前 1000 回合的回报标准差，画学习曲线。
3. 把基线改为"先算优势再更新"，并改成**每个状态一个**滑动平均 `V[s]`，比较学习曲线与方差。
4. 加入回报归一化：每个回合把 `returns` 变成均值 0、标准差 1，用种子 0–9 验证是否不再卡死。
5. 讲义练习 3：加入熵奖励（梯度 `∂H/∂z_i = −π_i(log π_i + H)`，见测验 Q11），扫 `β ∈ {0, 0.01, 0.1, 1.0}`，记录最终回报和平均策略熵。
6. 改成每 10 个回合更新一次（先累加梯度，再统一更新），观察方差和收敛速度的变化。

---

## 8. 常见坑

- **符号写反**：REINFORCE 是梯度**上升**（`θ += ...`）；在 PyTorch 中对应最小化 `−adv · log_prob`。写成 `+adv · log_prob` 再最小化，策略会越学越差。
- **用更新后的参数重算概率**：如果在更新循环中用最新的 θ 重新计算 `probs`，梯度就不再是 θ_old 处的策略梯度；要么事先存好，要么先算完再统一更新。
- **基线依赖当前动作**：用 `Q(s, a)` 或混入当前回合回报的量当基线会引入偏差；基线只能依赖状态（或与当前动作无关的量）。
- **不归一化回报 + 大学习率**：softmax 饱和、策略塌缩到确定性的坏动作，`e_a − π ≈ 0` 后再也学不动。
- **只看一个种子**：本节代码换种子就可能失败；RL 实验要报告多种子的结果。
- **把贪心策略图当成全局最优策略**：路径外的状态几乎没有被训练，箭头没有意义。
- **混淆折扣与未折扣回报**：日志里的数值与"最优步数"比较前，先统一口径。
