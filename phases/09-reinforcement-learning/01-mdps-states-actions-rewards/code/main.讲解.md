# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 01 节 MDP、状态、动作与奖励 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`random`）

---

## 1. 这份代码在考察什么

这份不到 120 行的脚本，把 MDP 的五个对象全部"落地"成了可以运行的 Python：

1. **环境 = 一个 `step` 函数**：状态、动作、转移、奖励、终止，五行代码就是一个完整的 MDP（γ 在评估时传入）。
2. **策略 = 返回动作分布的函数**：`π(a|s)` 直接用字典 `{动作: 概率}` 表示，随机策略和"贪心"策略只差一个字典。
3. **两种估计策略好坏的方式**：用 rollout（采样整局、累加奖励）做**蒙特卡洛估计**，用 Bellman 方程做**精确的迭代策略评估**。
4. **γ 的物理意义**：同一个随机策略在 γ = 0.5 / 0.9 / 0.99 下给出完全不同的价值表，直观展示"有效视野 ≈ 1/(1-γ)"。

> 一句话：**先把问题写成 `(S, A, P, R, γ)`，再谈算法**——后面所有 RL 算法都是在优化这同一个结构。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GRID`、`TERMINAL`、`ACTIONS` | 模块常量 | 4×4 网格、右下角终点、四个方向的位移 | 状态空间 S、动作空间 A |
| `all_states()` | 函数 | 枚举全部 16 个格子 | S 的显式列举 |
| `step(state, action)` | 函数 | 返回 `(下一状态, 奖励, 是否结束)` | 转移 P + 奖励 R |
| `uniform_policy` / `greedy_policy` | 函数 | 返回动作概率字典 | 策略 π(a\|s) |
| `sample_action(dist, rng)` | 函数 | 按概率分布抽一个动作 | 从 π 采样 |
| `rollout(policy, rng, max_steps)` | 函数 | 从 (0,0) 跑一局，返回总奖励和步数 | 回报 G 的一次采样 |
| `policy_evaluation(policy, gamma, ...)` | 函数 | 反复应用 Bellman 期望方程直到收敛 | 迭代策略评估 |
| `print_value_grid` | 函数 | 把价值字典打印成 4×4 表格 | — |
| `main()` | 函数 | 对两个策略做 rollout 和多种 γ 的评估 | — |

数据流：`main → rollout → sample_action + step`（采样路线）；`main → policy_evaluation → step`（精确计算路线）。两条路线都只通过 `step` 接触环境——这正是"环境接口"的思想。

---

## 3. 逐段精讲

### 3.1 环境定义：常量 + `step`

```python
GRID = 4
TERMINAL = (3, 3)
ACTIONS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def step(state, action):
    if state == TERMINAL:
        return state, 0.0, True
    dr, dc = ACTIONS[action]
    r, c = state
    nr = min(max(r + dr, 0), GRID - 1)
    nc = min(max(c + dc, 0), GRID - 1)
    return (nr, nc), -1.0, (nr, nc) == TERMINAL
```

- **状态**用元组 `(行, 列)` 表示。元组不可变、可哈希，能直接当字典的键（`values[(r, c)]`）。
- **动作**映射成 `(Δ行, Δ列)`：注意"上"是行号减 1，因为第 0 行在最上面。
- **撞墙**：`min(max(x, 0), GRID - 1)` 是经典的 clamp（夹紧），越界的移动会被夹回边界，等价于"原地不动但仍付出 -1"。
- **奖励**：每步 -1。它把"尽快到达终点"编码成"最大化回报"——最短路径 6 步，最优回报 -6。
- **吸收终止态**：在终点调用 `step` 返回 `0.0` 奖励并停留原地。这保证了 `V(TERMINAL) = 0`，Bellman 方程不会从终点"漏出"虚假奖励。
- 转移是**确定性**的：同样的 `(s, a)` 永远得到同样的 `s'`。讲义练习 3 会把它改成随机的。
- ⚠️ 简化：环境是全局常量 + 纯函数，没有像 Gymnasium 那样封装成带 `reset()/step()` 的类；好处是一眼看完、易于在 DP 中枚举。

### 3.2 策略：返回字典的函数

```python
def uniform_policy(_state):
    return {a: 1.0 / len(ACTIONS) for a in ACTIONS}


def greedy_policy(_state):
    return {"down": 0.5, "right": 0.5, "up": 0.0, "left": 0.0}
```

- 策略的接口是"给状态、回动作分布"，正好对应 `π(a|s)`。两个策略都**不看状态**（参数名用 `_state` 表示"故意不用"），所以它们是"无记忆、与位置无关"的策略。
- `uniform_policy` 用字典推导式生成 `{up: 0.25, down: 0.25, ...}`，写成 `1.0 / len(ACTIONS)` 而不是硬编码 0.25，动作数变了也不用改。
- `greedy_policy` 名字叫 greedy，但它**并不是最优策略**：在最下面一行时它仍有 50% 概率选 "down"，撞墙浪费一步；最右列同理。所以它的期望回报约 -7.9，而不是 -6。⚠️ 这是刻意的"接近最优但不完美"的对照组。

### 3.3 `sample_action`：按概率抽样

```python
def sample_action(dist, rng):
    x = rng.random()
    total = 0.0
    for a, p in dist.items():
        total += p
        if x <= total:
            return a
    return next(iter(dist))
```

- 这是**逆累积分布采样**（轮盘赌）：在 `[0, 1)` 里抽一个均匀数 `x`，沿着累计概率走，第一次超过 `x` 的那个动作被选中。概率越大的动作占的"区间"越长。
- 最后一行 `return next(iter(dist))` 是**兜底**：如果浮点累加后 `total` 略小于 1（例如 0.9999999），而 `x` 恰好落在缝隙里，就返回第一个动作，避免返回 `None`。
- `rng` 作为参数传入，而不是用全局 `random`：每次实验都能用独立、可复现的随机数流（`main` 里两个策略分别用 `Random(42)`）。
- 生产中通常写 `rng.choices(list(dist), weights=dist.values())[0]` 或 `np.random.choice`，功能相同。

### 3.4 `rollout`：采样一整局

```python
def rollout(policy, rng, max_steps=200):
    state = (0, 0)
    total = 0.0
    steps = 0
    for _ in range(max_steps):
        action = sample_action(policy(state), rng)
        state, reward, done = step(state, action)
        total += reward
        steps += 1
        if done:
            break
    return total, steps
```

- 这就是 RL 的**交互循环**：看状态 → 选动作 → 环境返回新状态和奖励 → 累计。后面所有算法（MC、Q-learning、DQN、REINFORCE）的外层都是这个循环。
- `total` 是**未折扣**的回报（相当于 γ=1）。对这个一定会终止的任务没问题，但要注意它和后面 `policy_evaluation` 的 γ=0.99 结果不可直接比较。
- `max_steps=200` 是**截断保护**：随机游走理论上可能走很久，截断保证程序结束。⚠️ 代价是对极长回合的回报估计偏"乐观"（实测 5000 局里有 121 局被截在 200 步）。
- `for _ in range(...)` 中的 `_` 表示"循环变量不使用"。

### 3.5 `policy_evaluation`：迭代 Bellman 期望方程

```python
def policy_evaluation(policy, gamma=0.99, tol=1e-6, max_iter=2000):
    values = {s: 0.0 for s in all_states()}
    for _ in range(max_iter):
        delta = 0.0
        new_values = dict(values)
        for state in all_states():
            if state == TERMINAL:
                continue
            v = 0.0
            for action, pi_a in policy(state).items():
                s_next, reward, _ = step(state, action)
                v += pi_a * (reward + gamma * values[s_next])
            delta = max(delta, abs(v - values[state]))
            new_values[state] = v
        values = new_values
        if delta < tol:
            break
    return values
```

逐行对应公式 `V(s) ← Σ_a π(a|s) [r + γ V(s')]`：

- `for action, pi_a in policy(state).items()` 对应 `Σ_a π(a|s)`；
- `step(state, action)` 给出确定的 `s'` 和 `r`——因为转移是确定的，公式里对 `s'` 的求和只有一项；
- `reward + gamma * values[s_next]` 就是方括号里的"一步奖励 + 折扣后的落脚点价值"。

设计要点：

- **同步更新**：`new_values = dict(values)` 复制一份新表，本轮所有计算都读旧表 `values`，整轮结束再替换。讲义里的版本是原地更新（直接写 `V[s] = v`），两者收敛到同一个 `V^π`，原地版通常更快，同步版结果与遍历顺序无关、更贴近数学定义。
- **收敛判据**：`delta` 记录本轮所有状态中最大的变化量（无穷范数），小于 `tol` 就停。γ<1 时 Bellman 算子是压缩映射，误差按 γ 的速率几何收缩。
- **`max_iter` 兜底**：防止 γ 很接近 1 时迭代太久。⚠️ 如果因为达到 `max_iter` 而退出，函数不会提示"未收敛"，生产代码应该记录或告警。
- 跳过 `TERMINAL`：终点价值保持初始值 0，与 `step` 的吸收态设计配合。

### 3.6 `main`：两种估计 + 三个 γ

```python
    rng = random.Random(42)

    returns_random = [rollout(uniform_policy, rng)[0] for _ in range(5000)]
    mean_random = sum(returns_random) / len(returns_random)

    rng2 = random.Random(42)
    returns_greedy = [rollout(greedy_policy, rng2)[0] for _ in range(5000)]
    # ...
    for gamma in (0.5, 0.9, 0.99):
        values = policy_evaluation(uniform_policy, gamma=gamma)
        print_value_grid(values, f"gamma = {gamma}")
```

- `rollout(...)[0]` 只取总奖励，丢掉步数。
- 两个策略用**相同种子的独立生成器**，保证对比公平且可复现。
- 对随机策略用三种 γ 评估，展示折扣对价值表的影响；最后对 greedy 策略用 γ=0.99 评估作对比。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 环境写成纯函数 `step` | 可以在 DP 中对任意 `(s, a)` 直接查询，无需维护内部状态 | 真实环境（Gymnasium）是有状态的对象，只能 `reset/step` 采样，不能任意查询 |
| 策略返回概率字典 | 与 `π(a\|s)` 一一对应，同时支持采样和精确求期望 | 大动作空间用张量 / logits 表示 |
| 每步奖励 -1 | 把"最短路径"自然编码成"最大回报" | 真实任务的奖励设计要难得多，且容易 reward hacking |
| 同步（两份表）更新 | 与遍历顺序无关，易复现、易推理 | 原地更新通常收敛更快 |
| rollout 截断 200 步 | 保证程序结束 | 截断引入偏差；生产中要区分"终止"与"截断"（Gymnasium 的 `terminated` / `truncated`） |
| 显式传入 `rng` | 实验可复现、互不干扰 | 无 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组作为状态与字典键 | `TERMINAL = (3, 3)`、`values[(r, c)]` | 元组不可变、可哈希，可以当 dict 的 key；列表不行 |
| 元组解包 | `dr, dc = ACTIONS[action]`、`state, reward, done = step(...)` | 一次给多个变量赋值；函数可以"返回多个值"（实际是返回一个元组） |
| 字典字面量 | `{"up": (-1, 0), ...}` | 动作名到位移的映射 |
| 字典推导式 | `{a: 1.0 / len(ACTIONS) for a in ACTIONS}`、`{s: 0.0 for s in all_states()}` | 一行构造字典；遍历字典默认遍历键 |
| 列表推导式（双层） | `[(r, c) for r in range(GRID) for c in range(GRID)]` | 等价于两层嵌套 for，外层在前 |
| `dict.items()` | `for a, p in dist.items()` | 同时遍历键和值 |
| `dict(values)` | `new_values = dict(values)` | 浅拷贝一个字典；值是 float，浅拷贝就够了 |
| `min` / `max` 嵌套 | `min(max(r + dr, 0), GRID - 1)` | 把数值夹在区间内（clamp） |
| `_` 占位变量 | `for _ in range(max_steps)`、`s_next, reward, _ = step(...)`、参数 `_state` | 约定俗成表示"这个值我不用" |
| `next(iter(...))` | `return next(iter(dist))` | 取可迭代对象的第一个元素；Python 3.7+ 字典保持插入顺序 |
| 下标取返回值 | `rollout(uniform_policy, rng)[0]` | 从返回的元组中只取第一个 |
| `random.Random(seed)` | `rng = random.Random(42)` | 独立的随机数生成器实例，不影响全局 `random` |
| f-string 格式符 | `f"{values[(r, c)]:7.2f}"`、`f"{mean_random:.2f}"` | `:7.2f` 表示宽度 7、保留 2 位小数，用来对齐表格 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被导入时不执行 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.3 秒）的输出：

```text
=== 4x4 GridWorld, 5000 rollouts ===
random policy:  mean return = -58.67   (optimal = -6.00)
greedy  policy: mean return = -7.88

=== Policy evaluation V^pi(s) for uniform-random policy ===
  gamma = 0.5
     -2.00   -2.00   -2.00   -1.99
     -2.00   -2.00   -1.98   -1.95
     -2.00   -1.98   -1.92   -1.70
     -1.99   -1.95   -1.70    0.00

  gamma = 0.9
     -9.36   -9.22   -8.97   -8.75
     ...
  gamma = 0.99
    -39.41  -38.19  -36.25  -34.64
    -38.19  -36.41  -33.34  -30.40
    -36.25  -33.34  -27.60  -20.41
    -34.64  -30.40  -20.41    0.00

=== Policy evaluation V^pi(s) for greedy down+right policy (gamma=0.99) ===
  greedy policy
     -7.59   -6.66   -6.06   -5.82
     -6.66   -5.36   -4.41   -3.92
     -6.06   -4.41   -2.96   -1.98
     -5.82   -3.92   -1.98    0.00
```

逐项解读：

- **随机策略 -58.67**：随机游走平均要近 60 步才撞到终点，离最优 -6 差了约 10 倍——"缩小这个差距就是整个阶段 09 要做的事"。（讲义说"大约 -60 到 -80"，实测略好于这个范围；用 γ=1 精确评估得到的理论期望约 -59.4。）
- **greedy 策略 -7.88**：接近但不等于 -6，原因见 3.2 节：在底边/右边时仍会撞墙。
- **γ = 0.5**：几乎所有格子都是 `-2.00 = -1/(1-0.5)`，智能体"只看得见 2 步"，分不清离终点远近；只有终点旁边的 `(2,3)`、`(3,2)` 有 1/4 概率一步结束，才是 -1.70。
- **γ = 0.9 / 0.99**：价值表明显"以终点为中心向外递减"，γ 越大、远近差异越明显。讲义练习 2 问的"为什么 γ 越大，终点附近的价值增长越快"就体现在这里：γ=0.99 时 `(0,0)` 与 `(2,3)` 相差约 19，而 γ=0.5 时只差 0.3。
- **对称性**：价值表关于主对角线对称（例如 `(0,1)` 和 `(1,0)` 都是 -38.19），因为网格和终点关于对角线对称、随机策略也对称——这是检查实现是否正确的好方法。
- **-39.41 vs -58.67**：前者折扣 γ=0.99、后者未折扣，所以数值不同；详见测验 Q10。

---

## 7. 动手改一改

1. 把 rollout 次数改成 10000（讲义练习 1），同时计算回报的标准差（`statistics.pstdev`），感受随机策略的回报方差有多大（实测约 47）。
2. 写一个真正的最优策略：在最下面一行只向右、在最右一列只向下、其余位置一半向下一半向右。评估它，确认 `V(0,0)` 在 γ=1 时恰好是 -6。
3. 把 `policy_evaluation` 改成原地更新版本（删掉 `new_values`，直接写 `values[state] = v`），统计两种版本达到 `tol` 所需的迭代轮数。
4. 加一个"陷阱格"`(1, 1)`：进入时奖励 -10。观察随机策略价值表的变化。
5. 实现讲义练习 3 的"滑动"环境（以 `1-p` 按预期方向，`p/2` 各滑向两个垂直方向），对比均匀策略和 greedy 策略的 `V[start]` 变化，解释为什么前者不变、后者变差。
6. 用线性方程组直接求解 `V = (I - γP^π)⁻¹ R^π`（可以用 NumPy），与迭代结果对比。

---

## 8. 常见坑

- **终点不吸收**：如果在终点调用 `step` 仍然返回 -1 或继续移动，`V(TERMINAL)` 不再是 0，所有价值都会被污染。
- **把 rollout 均值和 γ<1 的 V 直接比较**：一个未折扣、一个折扣，数值本来就不一样。
- **截断当作终止**：被 `max_steps` 截断的回合并没有真正结束，后面学 TD/DQN 时若把截断当作终止（不再自举），会引入偏差。
- **γ=1 用在不保证终止的任务上**：策略评估会发散或一直跑到 `max_iter`；本任务对这两个策略是安全的，因为它们最终都会到达终点。
- **浮点概率累加**：`sample_action` 如果没有最后的兜底返回，极少数情况下会返回 `None`，导致 `ACTIONS[None]` 报 `KeyError`。
- **策略名字误导**：`greedy_policy` 不是最优策略，不要把 -7.88 当成最优回报。
