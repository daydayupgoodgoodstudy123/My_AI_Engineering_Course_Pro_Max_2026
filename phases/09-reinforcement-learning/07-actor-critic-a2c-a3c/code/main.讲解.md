# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 07 节 Actor-Critic — A2C 和 A3C ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 0.2 秒跑完） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy / PyTorch

---

## 1. 这份代码在考察什么

这份代码在 4×4 GridWorld 上，用纯 Python 实现了一个"单环境版 A2C"：线性 softmax 策略（actor）+ 线性价值函数（critic）+ GAE(λ) 优势估计。它想让你亲手搞清楚：

1. **critic 到底在干什么**：`V_φ(s)` 用 MSE 回归到 `returns`，再作为 baseline 从回报里减掉，得到低方差的 advantage。
2. **GAE 的倒序递推**：`gae = δ_t + γλ·gae` 一行代码如何把 TD 和 MC 统一起来，以及终止状态 `done` 怎样切断 bootstrap。
3. **softmax 策略梯度的闭式形式**：`∇_θ log π = (1[i=a] - π_i)·x`，不需要自动微分。
4. **组合损失的三项**：策略梯度 + 价值回归 + 熵奖励，在代码里分别对应哪几行。
5. **工程小技巧**：advantage 标准化、数值稳定的 softmax、学习率分离。

> 一句话：**这是 PPO、IMPALA、GRPO 的"祖先骨架"**——把它读懂，后面所有带 "advantage" 的算法都只是在这个骨架上加零件。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GRID / TERMINAL / ACTIONS / DELTAS` | 常量 | 4×4 网格，终点 (3,3)，四个动作 | MDP 定义 |
| `reset()` / `step()` | 函数 | 环境：起点 (0,0)，每步奖励 -1，撞墙原地不动 | 环境动力学 |
| `features(state)` | 函数 | 把格子编码成 16 维 one-hot | 特征工程（线性函数近似≈查表） |
| `softmax` / `logits` / `sample` | 函数 | 线性 logits → 概率 → 按概率采样动作 | 随机策略 `π_θ(a\|s)` |
| `value(w, x)` | 函数 | 线性 critic `V = w·x` | `V_φ(s)` |
| `rollout()` | 函数 | 用当前策略跑一条轨迹，记录 x/a/r/probs/v/done | on-policy 采样 |
| `gae_advantages()` | 函数 | 倒序计算 GAE 优势和 critic 目标 | GAE(λ)、TD residual |
| `normalize()` | 函数 | advantage 零均值单位方差 | advantage normalization |
| `actor_critic()` | 函数 | 主训练循环：采样 → GAE → 更新 critic 和 actor | A2C 主循环 |
| `greedy_policy` / `print_policy` / `block_mean` / `main` | 函数 | 评估与打印 | 结果可视化 |

数据流：`actor_critic` 每个 episode 调用 `rollout` 得到轨迹 → `gae_advantages` 得到 `advs, returns` → `normalize(advs)` → 遍历每一步，先用 `returns[t]` 更新 critic，再用 `advs_norm[t]` 更新 actor → 记录本回合的折扣回报。

---

## 3. 逐段精讲

### 3.1 环境：一个"每步扣 1 分"的迷宫

```python
def step(state, action_idx):
    if state == TERMINAL:
        return state, 0.0, True
    dr, dc = DELTAS[ACTIONS[action_idx]]
    r, c = state
    nr = min(max(r + dr, 0), GRID - 1)
    nc = min(max(c + dc, 0), GRID - 1)
    return (nr, nc), -1.0, (nr, nc) == TERMINAL
```

- 每走一步奖励 -1，到达 (3,3) 结束。所以"最大化回报"="用最少步数到终点"，从 (0,0) 出发最优是 6 步（3 下 + 3 右，任意顺序）。
- `min(max(x, 0), GRID-1)` 是 clamp 写法：撞墙就停在原地（但照样扣 1 分）。
- 返回三元组 `(next_state, reward, done)`，与 Gym 早期 API 相似。⚠️ 没有区分 `terminated` 和 `truncated`，超时截断由 `rollout` 的 `max_steps` 处理，见 3.5。

### 3.2 特征与线性模型：one-hot = 查表

```python
def features(state):
    x = [0.0] * N_FEAT
    r, c = state
    x[r * GRID + c] = 1.0
    return x

def logits(theta, x):
    return [sum(w * xi for w, xi in zip(theta[a], x)) for a in range(N_ACTIONS)]

def value(w, x):
    return sum(wj * xj for wj, xj in zip(w, x))
```

- `r * GRID + c` 把二维坐标拉平成 0~15 的下标。one-hot 特征下，线性模型 `θ[a]·x` 恰好等于"取出 `θ[a][s]`"，所以这其实是**表格型** actor-critic，只是写成了线性函数近似的样子。
- 这样设计的好处：代码结构和"换成神经网络"时完全一致（`features` → 网络 trunk，`theta` → policy head，`w` → value head），但每个参数的含义一目了然。
- `theta` 形状是 `[N_ACTIONS][N_FEAT]` = 4×16，`w` 是 16 维。

### 3.3 数值稳定的 softmax 与采样

```python
def softmax(z):
    m = max(z)
    exps = [math.exp(zi - m) for zi in z]
    Z = sum(exps)
    return [e / Z for e in exps]

def sample(probs, rng):
    x = rng.random()
    cum = 0.0
    for a, p in enumerate(probs):
        cum += p
        if x <= cum:
            return a
    return N_ACTIONS - 1
```

- 先减去最大值再 `exp`：数学上不变（分子分母同乘 `e^{-m}`），但能避免 `exp(1000)` 溢出。这是面试必考的数值稳定写法。
- `sample` 是"逆 CDF 采样"：把 [0,1) 切成长度为 `p_a` 的小段，看随机数落在哪段。最后的 `return N_ACTIONS - 1` 是兜底：浮点累加后 `cum` 可能是 0.9999999 而 `x` 恰好更大。
- 用传入的 `rng`（`random.Random` 实例）而不是全局 `random`，保证实验可复现、互不干扰。

### 3.4 初始化：actor 小随机，critic 全零

```python
def init_theta(rng):
    return [[rng.gauss(0, 0.1) for _ in range(N_FEAT)] for _ in range(N_ACTIONS)]

def init_w(_rng):
    return [0.0] * N_FEAT
```

- actor 用小高斯噪声打破对称，初始策略接近均匀分布（高熵，利于探索）。
- critic 初始化为 0：所有 `V(s)=0`，相当于"一开始没有 baseline"。`_rng` 前面的下划线是 Python 约定，表示"这个参数故意不用"，保留它只是为了和 `init_theta` 签名一致。

### 3.5 rollout：on-policy 采样一整条轨迹

```python
def rollout(theta, w, rng, max_steps=100):
    traj = []
    s = reset()
    for _ in range(max_steps):
        x = features(s)
        probs = softmax(logits(theta, x))
        a = sample(probs, rng)
        s_next, r, done = step(s, a)
        traj.append({"x": x, "a": a, "r": r, "probs": probs, "v": value(w, x), "done": done})
        if done:
            break
        s = s_next
    return traj
```

- 每一步存下 6 个字段：特征 `x`、动作 `a`、奖励 `r`、**采样时的动作概率 `probs`**、**采样时的价值估计 `v`**、是否结束 `done`。
- 存 `probs` 是为了后面算 `∇log π` 时不用再前向一次；存 `v` 是为了让 GAE 用"同一时刻的 critic"来计算 δ。这和 PPO 实现里存 `old_log_prob`、`old_value` 是同一个思路。
- ⚠️ 截断问题：如果 100 步还没到终点，最后一步的 `done=False`，但 `gae_advantages` 会因为 `t + 1 < T` 不成立而把 `next_v` 设为 0——**把超时当成了终止**，没有用 `V(s_T)` bootstrap。在这个小网格里学会之后几乎不会超时，影响很小；但在长视界任务中这是经典 bug（修复方法见测验 Q11）。

### 3.6 GAE：一行递推统一 TD 与 MC

```python
def gae_advantages(traj, gamma=0.99, lam=0.95):
    T = len(traj)
    advantages = [0.0] * T
    gae = 0.0
    for t in reversed(range(T)):
        next_v = 0.0 if traj[t]["done"] else (traj[t + 1]["v"] if t + 1 < T else 0.0)
        delta = traj[t]["r"] + gamma * next_v - traj[t]["v"]
        gae = delta + gamma * lam * gae
        advantages[t] = gae
    returns = [a + traj[t]["v"] for t, a in enumerate(advantages)]
    return advantages, returns
```

这是整份代码的核心，对应讲义公式 `A_t^{GAE} = Σ_{l≥0} (γλ)ˡ δ_{t+l}`。

- **为什么倒序**：把求和式展开，`A_t = δ_t + γλ·A_{t+1}`。从最后一步往前算，每步 O(1)，总共 O(T)，不用写双重循环。
- **`next_v` 的三种情况**：
  - `done=True`：终止状态之后没有未来，`V(s')=0`；
  - 否则取下一步记录的 `v`（就是 `V(s_{t+1})`）；
  - 轨迹末尾但未终止：同样取 0（即 3.5 中提到的简化）。
- **`delta`** 就是 TD residual `δ_t = r + γV(s') - V(s)`，讲义叫它"one-step advantage estimate"。
- **`returns = advantages + values`**：这就是 critic 的回归目标，也叫 λ-return。λ=1 时它恰好等于折扣 MC 回报 `G_t`，λ=0 时等于一步 TD 目标 `r + γV(s')`。
- 注意 `gae` 在遇到 `done` 时没有显式清零——因为本代码每条轨迹只有最后一步可能 `done=True`，倒序时它是第一个被处理的，`gae` 本来就是 0。如果把多条轨迹拼接在一起（向量化环境），就必须写成 `gae = delta + gamma * lam * (1 - done) * gae`。

### 3.7 advantage 标准化

```python
def normalize(xs):
    if len(xs) < 2:
        return xs
    m = sum(xs) / len(xs)
    var = sum((x - m) ** 2 for x in xs) / len(xs)
    sd = math.sqrt(var) + 1e-8
    return [(x - m) / sd for x in xs]
```

- 讲义 Pitfalls："Normalize advantages to zero-mean/unit-std per batch. Stabilizes training massively at near-zero cost."
- `+ 1e-8` 防止所有 advantage 相同时除以 0。
- `len(xs) < 2` 时直接返回：只有一个元素时标准差为 0，标准化没有意义（若强行标准化会变成 0，等于这一步不学习）。
- 这里是**每条轨迹**单独标准化（因为 batch 就是一条轨迹）；真正的 A2C 会在 `N_envs × T` 的整个 batch 上标准化。

### 3.8 主循环：先 critic、后 actor

```python
        for t, node in enumerate(traj):
            target = returns[t]
            err = target - value(w, node["x"])
            for j in range(N_FEAT):
                w[j] += lr_v * err * node["x"][j]

            adv = advs_norm[t]
            probs = node["probs"]
            for i in range(N_ACTIONS):
                grad_logpi = (1.0 if i == node["a"] else 0.0) - probs[i]
                entropy_grad = -math.log(max(probs[i], 1e-12)) - 1.0
                for j in range(N_FEAT):
                    theta[i][j] += lr_a * (adv * grad_logpi + ent_coef * entropy_grad * probs[i]) * node["x"][j]
```

**critic 部分**：最小化 `½(target - w·x)²`，梯度下降就是 `w += lr_v · err · x`（经典 LMS / delta rule）。注意 `err` 用的是**当前**的 `w`（同一状态在轨迹中重复出现时，后面那次会看到前面更新后的值），而 `target` 是用 rollout 时的旧 `v` 算出来的固定目标——这相当于半梯度（semi-gradient）TD：目标不参与求导。

**actor 部分**：

- `grad_logpi = 1[i=a] - π_i`：softmax 策略下 `∂log π(a|s)/∂z_i` 的闭式解。由于 logits `z_i = θ[i]·x`，对 `θ[i][j]` 的梯度再乘以 `x[j]`。
- 更新方向是**梯度上升**（`+=`），因为我们在最大化 `E[A·log π]`。
- `adv` 用的是标准化后的值；`probs` 用的是 rollout 时存下的旧概率——相当于"在采样时刻的参数处计算梯度，再逐步累加"，这正是 on-policy 的一次性更新。
- 学习率分离：`lr_a=0.05`、`lr_v=0.1`，critic 学得更快，符合"双时间尺度"的直觉——baseline 要先准，actor 的梯度才可信。

**熵项**：意图是给 actor 加上 `c_e·∇H(π)`，防止策略过早变确定。⚠️ 这里的 `entropy_grad * probs[i] = -π_i(log π_i + 1)` 只是 `∂H/∂π_i · π_i`，**不是精确的 `∂H/∂z_i = -π_i(log π_i + H)`**，漏掉了 softmax Jacobian 的交叉项（一个检验方法：精确梯度在 4 个动作上求和为 0，代码版本求和为 `H-1`）。因为 `ent_coef=0.01` 很小，这个近似对结果影响不大，但不应该当作正确公式记下来。详细推导与修正见测验 Q10。

### 3.9 记录回报与评估

```python
        if traj:
            mc_return = 0.0
            for r in reversed([n["r"] for n in traj]):
                mc_return = r + gamma * mc_return
            returns_log.append(mc_return)
```

- 倒序累加 `G = r + γG`，得到本回合从起点出发的**折扣回报**（γ=0.99）。
- ⚠️ `main()` 最后把它和 "optimal = -6.0" 比较，但 -6.0 是**未折扣**的最优值；6 步的折扣最优回报是 `-(1 + 0.99 + … + 0.99⁵) ≈ -5.85`。读结果时要心里有数。

```python
def greedy_policy(theta):
    ...
            z = logits(theta, features((r, c)))
            policy[(r, c)] = ACTIONS[max(range(N_ACTIONS), key=lambda i: z[i])]
```

- 训练时按概率采样（探索），评估时取 argmax（利用）。`max(range(n), key=...)` 是 Python 里求 argmax 的惯用写法。

`block_mean(xs, block)` 把 1500 个回合按每 150 个分块求均值，平滑学习曲线。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| one-hot 特征 + 线性模型 | 等价于表格法，每个参数可解释；结构与神经网络版一致 | 无法泛化到未见状态；生产中用共享 CNN/MLP trunk + 两个 head |
| 手写梯度（不用 autograd） | 看清 `∇log π = 1[i=a] - π` 的本质 | 容易写错（熵梯度就是例子）；生产中用 PyTorch 定义 loss 交给 autograd |
| 单环境、单线程 | 讲清算法而非并行工程 | 讲义："rewriting to batched A2C is three lines of numpy"；生产用向量化环境 |
| rollout 时缓存 `probs` 和 `v` | 一次前向复用到更新，GAE 用一致的价值 | 与 PPO 存 `old_log_prob/old_value` 同理 |
| GAE(λ=0.95) | 讲义所说的 2026 默认值，偏差-方差折中 | 需要按任务扫 λ |
| per-trajectory advantage 标准化 | 稳定梯度尺度 | 真实 A2C 在整个 batch 上标准化 |
| critic 学习率大于 actor | baseline 先学准，actor 梯度才有意义 | 也可做 critic 预热或独立优化器 |
| 超时当作终止（`next_v=0`） | 代码更短 | 长视界任务会让 critic 系统性偏差；应区分 terminated/truncated |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `GRID = 4`、`ACTIONS = ("up", ...)` | 大写命名表示常量；元组不可变，适合放固定的动作集合 |
| 字典 | `DELTAS = {"up": (-1, 0), ...}` | 动作名 → 坐标偏移的映射 |
| 元组解包 | `dr, dc = DELTAS[...]`；`r, c = state` | 一次给多个变量赋值 |
| 链式比较返回布尔 | `(nr, nc) == TERMINAL` | 元组可以直接比较相等 |
| 列表乘法初始化 | `[0.0] * N_FEAT` | 创建定长列表；⚠️ 对可变元素（如 `[[]] * 3`）会共享引用，这里是浮点数所以安全 |
| 嵌套列表推导式 | `[[rng.gauss(0, 0.1) for _ in range(N_FEAT)] for _ in range(N_ACTIONS)]` | 生成二维列表；`_` 表示不使用的循环变量 |
| 生成器表达式 + `zip` | `sum(w * xi for w, xi in zip(theta[a], x))` | 逐元素相乘再求和，即点积 |
| `enumerate` | `for a, p in enumerate(probs)`；`for t, node in enumerate(traj)` | 同时拿下标和元素 |
| `reversed(range(T))` | GAE 倒序循环 | 从 T-1 递减到 0，不创建新列表 |
| 条件表达式（三元） | `0.0 if traj[t]["done"] else (...)` | 一行内的 if/else，可嵌套 |
| 字典作为记录 | `{"x": x, "a": a, "r": r, ...}` | 轻量的"结构体"；生产中更常用 `dataclass` 或 NumPy 数组 |
| `max(..., key=lambda ...)` | `max(range(N_ACTIONS), key=lambda i: z[i])` | 求 argmax |
| 切片 | `log[-150:]`、`xs[i : i + block]` | 取最后 150 个；按块取子列表 |
| `x or default` | `rng = rng or random.Random(0)` | `rng` 为 `None` 时用默认值 |
| `random.Random(seed)` | `random.Random(7)` | 独立的随机数生成器实例，可复现 |
| 参数名前缀 `_` | `def init_w(_rng)` | 约定：此参数故意不用 |
| f-string 格式符 | `f"{m:6.2f}"`、`f"{value(...):7.2f}"` | 宽度 6/7、保留 2 位小数，用于对齐表格 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13，约 0.2 秒）输出：

```text
=== A2C-style actor-critic with GAE(lam=0.95) on 4x4 GridWorld ===

learning curve (mean return per 150 episodes):
  block 1: mean return = -13.96
  block 2: mean return =  -7.23
  block 3: mean return =  -6.49
  block 4: mean return =  -6.17
  block 5: mean return =  -6.24
  block 6: mean return =  -6.34
  block 7: mean return =  -6.18
  block 8: mean return =  -6.18
  block 9: mean return =  -6.09
  block 10: mean return =  -6.11

  greedy policy from actor
   > > > v
   > v > v
   > > > v
   > > > .

critic values V_phi(s):
     -6.08   -5.13   -4.17   -3.20
     -8.10   -6.47   -3.67   -2.20
     -9.82   -5.15   -2.33   -1.19
    -14.06   -9.76   -3.37    0.00

final mean return (last 150 eps) = -6.11  (optimal = -6.0)
```

逐段解读：

- **学习曲线**：第 1 块 -13.96，说明初始近似均匀随机的策略平均要走约 15 步；第 2 块就降到 -7.23，第 4 块后稳定在 -6.1~-6.3。300 个回合左右就基本收敛，这就是讲义说的 critic 作为"低方差 teacher"的作用（想量化对比，可以按讲义练习 Easy 和上一节 REINFORCE 的结果放在一起比较）。
- **为什么停在 -6.1 而不是 -5.85**：回报是折扣回报（γ=0.99），最优是约 -5.85。训练时策略始终是按概率**采样**的，熵奖励也让它保留一点随机性，偶尔多走一步，所以略低于最优。
- **贪心策略箭头**：从 (0,0) 出发沿 `> > > v v v` 恰好 6 步到达终点；其余格子也都指向"向右或向下"，全部是最优动作（在这个网格里任何只往右/下走的路径都是最短路径）。
- **critic 价值表**：
  - 最优路径上的格子估值合理：(0,0)≈-6.08、(0,3)≈-3.20、(2,3)≈-1.19，大致等于"剩余折扣步数"的负数。
  - (3,0)=-14.06、(2,0)=-9.82 这些离最优路径较远的格子估值偏差很大：策略学好后几乎不访问它们，critic 只在早期随机阶段被更新过。**critic 只对 on-policy 分布负责**。
  - (3,3)=0.00：终点从不作为"当前状态"进入轨迹，权重保持初始值 0。

---

## 7. 动手改一改

1. **λ 扫描**（讲义练习 Hard）：把 `main()` 里的 `lam=0.95` 依次换成 `0, 0.5, 0.9, 1.0`，记录每个 block 的平均回报，看哪个 λ 收敛最快。
2. **关掉熵奖励**：设 `ent_coef=0.0`，在 `actor_critic` 中额外计算每回合的平均策略熵并打印，观察熵下降得多快。
3. **修正熵梯度**：按测验 Q10 把 `entropy_grad` 改成精确的 `-π_i(log π_i + H)`，并用有限差分在几个随机 logits 上验证；对比改前改后的学习曲线。
4. **处理截断**：按测验 Q11 让 `rollout` 返回 `last_value`，把 `max_steps` 改小到 8，对比修正前后 critic 价值表的差别。
5. **改成 MC advantage**（讲义练习 Easy）：设 `lam=1.0`，并和上一节 REINFORCE + running-mean baseline 比较达到 -6.5 所需的回合数。
6. **批量 A2C**：同时跑 8 个环境（8 个独立的 `rollout`），把 8 条轨迹的 advantage 拼起来统一标准化后再更新，观察学习曲线是否更平滑。

---

## 8. 常见坑

- **超时当终止**：`next_v=0` 只适用于真正终止；被截断的轨迹要用 `V(s_T)` bootstrap，否则 critic 学到错误的价值。
- **拼接轨迹忘记重置 GAE**：多条轨迹首尾相接时，要在 `done` 处乘 `(1 - done)` 截断递推，否则上一条轨迹的 advantage 会"漏"到下一条。
- **手写熵梯度写错**：`∂H/∂π` 和 `∂H/∂z` 不是一回事，softmax 的 Jacobian 不能漏。用"各分量之和应为 0"做快速自检。
- **advantage 符号与更新方向**：policy gradient 是梯度**上升**（`+=`）；如果改写成"最小化 loss"的形式，loss 前面要有负号。两者混用最容易把算法写反。
- **critic 太慢**：critic 不准时 advantage 就是噪声。本代码用 `lr_v > lr_a` 缓解；更稳妥的是先预热 critic。
- **把折扣回报和步数直接比较**：日志里的回报带 γ 折扣，和"最优 6 步"之间差一个 `(1-γⁿ)/(1-γ)` 的换算。
