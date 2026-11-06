# 测验 · Actor-Critic — A2C 和 A3C（Actor-Critic — A2C and A3C）

> **阶段 09 · 强化学习 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要 critic | REINFORCE 直接用 Monte Carlo 回报 `G_t`，方差极大；减去一个只依赖状态的 baseline `b(s)` 期望不变、方差下降，最好用的 baseline 就是学出来的 `V̂(s)` |
| 2 | Actor 与 Critic | Actor 是策略 `π_θ(a\|s)`，用 policy gradient 更新；Critic 是价值函数 `V_φ(s)`，用 `(V_φ(s) - target)²` 做回归 |
| 3 | Advantage（优势） | `A(s,a) = Q(s,a) - V(s)`，"这个动作比平均水平好多少"；它是乘在 `∇log π` 前面的系数 |
| 4 | MC advantage vs TD residual | `G_t - V(s_t)` 无偏但方差高；`δ_t = r + γV(s') - V(s)` 有偏（依赖 V 的准确度）但方差低得多 |
| 5 | n-step advantage | 前 n 步用真实奖励、第 n 步用 `γⁿV(s_{t+n})` bootstrap 收尾；n=1 是纯 TD，n=∞ 是 MC |
| 6 | GAE(λ) | `A_t = Σ (γλ)ˡ δ_{t+l}`，对所有 n-step 优势做指数加权；λ=0 → TD，λ=1 → MC，常用 λ=0.95 |
| 7 | 组合损失 | `L = -E[A·log π] + c_v·E[(V - G)²] - c_e·E[H(π)]`，典型 `c_v≈0.5`、`c_e≈0.01` |
| 8 | A2C vs A3C | A3C：多线程异步把梯度推到共享参数（无锁，CPU 友好）；A2C：N 个环境同步批处理，一次 rollout 一次更新，GPU 友好，是今天的默认 |
| 9 | On-policy 约束 | A2C 的数据只能用于一次更新；想多轮复用就需要重要性采样修正——这正是 PPO 加的东西 |
| 10 | 工程要点 | critic 预热、advantage 标准化、共享 trunk + 分离 head、熵奖励防止塌缩、奖励尺度归一化 |

### 核心技能（能动手做到）

- [ ] 从零写出 `gae_advantages`：倒序遍历轨迹，正确处理终止状态（`done` 时下一状态价值为 0），并验证 λ=1 时 `returns` 等于折扣 MC 回报
- [ ] 手算一条 3 步轨迹在 λ=0 / λ=0.5 / λ=1 下的优势，并说出偏差-方差的变化方向
- [ ] 写出 softmax 线性策略的 `∇_θ log π(a|s) = (1[i=a] - π_i)·x`，并据此实现 actor 更新
- [ ] 给出熵 `H(π)` 对 logit 的正确梯度 `-π_i(log π_i + H)`，并用有限差分验证
- [ ] 把单环境 rollout 改造成"截断时用 `V(s_T)` bootstrap"，理解 truncation 与 termination 的区别
- [ ] 运行 `main.py`，解读学习曲线、贪心策略箭头图和 critic 价值表，说出为什么最终回报约为 -6
- [ ] 能画出 A2C / A3C / PPO / IMPALA / GRPO 之间的"演化关系"，并说出每一步改了什么

---

## 二、基础自测（选择题）

**Q1.** 在 policy gradient 中把 `G_t` 换成 `G_t - b(s_t)`（`b` 只依赖状态、不依赖动作），下列说法正确的是：

- A. 梯度估计的期望改变了，但方差降低了
- B. 梯度估计的期望不变，方差通常降低
- C. 梯度估计的期望和方差都不变，只是数值更好看
- D. 只有当 `b(s_t)` 恰好等于真实 `V(s_t)` 时梯度才无偏

**Q2.** GAE 中把 λ 设为 0，得到的优势估计等价于：

- A. Monte Carlo 优势 `G_t - V(s_t)`
- B. 一步 TD residual `δ_t = r_{t+1} + γV(s_{t+1}) - V(s_t)`
- C. 恒为 0
- D. n=5 的 n-step 优势

**Q3.** 关于 GAE 的 λ，下列说法**错误**的是：

- A. λ 越大越接近 MC，偏差越小、方差越大
- B. λ 越小越依赖 critic，critic 不准时偏差会变大
- C. λ 与 γ 的作用完全相同，调一个就够了
- D. 2026 年常用的默认值约为 0.95

**Q4.** 组合损失 `L = -E[A·log π] + c_v·E[(V - G)²] - c_e·E[H(π)]` 中，熵项前面是负号，意味着：

- A. 最小化 L 会降低策略熵，让策略更快变确定
- B. 最小化 L 会鼓励更高的熵，延缓策略过早变成确定性
- C. 熵项只影响 critic
- D. 负号是笔误，应为正号

**Q5.** 关于 A2C 和 A3C，下列说法正确的是：

- A. A3C 需要 replay buffer 来打散样本相关性
- B. A2C 是异步的，A3C 是同步的
- C. A3C 的多个 worker 各自跑环境、异步把梯度推到共享参数，靠"不同轨迹"天然去相关；A2C 把 N 个环境同步批处理，更适合 GPU
- D. A3C 必须加锁，否则参数会损坏、无法训练

**Q6.** A2C 用同一批 rollout 连续做 10 个 epoch 的梯度更新，最主要的问题是：

- A. 显存不够
- B. 第一次更新后策略已经变了，旧数据不再来自当前策略，梯度变得有偏；需要重要性采样修正（PPO 的做法）
- C. critic 会变成无偏估计
- D. 熵会自动变大

**Q7.** 训练初期 critic 是随机初始化的，直接开启 actor 更新最可能导致：

- A. 没有任何影响，因为 baseline 不改变期望
- B. baseline 不提供有用信息，advantage 基本是噪声，actor 在噪声上训练；可先预热 critic 或用较小的 actor 学习率
- C. critic 会因此发散到无穷
- D. 策略熵立即变为 0

**Q8.** 对一个 batch 的 advantage 做"减均值、除标准差"的标准化，主要作用是：

- A. 让 advantage 变成无偏估计
- B. 让梯度幅度不随奖励尺度/任务剧烈变化，训练更稳定，几乎零成本
- C. 替代 critic，从而不需要价值网络
- D. 保证每个动作的概率都上升

---

## 三、动手 / 代码题

**Q9.**（预测输出）本节代码的 `gae_advantages` 如下：

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

给定一条 3 步轨迹（每步奖励 -1，第 3 步到达终点）：

```python
traj = [{"r": -1.0, "v": -2.0, "done": False},
        {"r": -1.0, "v": -1.5, "done": False},
        {"r": -1.0, "v": -0.5, "done": True}]
```

取 `gamma=1.0`，分别写出 `lam=0.0`、`lam=0.5`、`lam=1.0` 时的 `advantages` 和 `returns`。λ=1 时的 `returns` 有什么特殊含义？

**Q10.**（找 bug）`actor_critic` 中 actor 的更新写成：

```python
for i in range(N_ACTIONS):
    grad_logpi = (1.0 if i == node["a"] else 0.0) - probs[i]
    entropy_grad = -math.log(max(probs[i], 1e-12)) - 1.0
    for j in range(N_FEAT):
        theta[i][j] += lr_a * (adv * grad_logpi + ent_coef * entropy_grad * probs[i]) * node["x"][j]
```

其中 `entropy_grad * probs[i]` 想表达的是熵 `H = -Σ π_k log π_k` 对第 i 个 logit 的梯度。请判断它是否精确；如果不精确，写出正确公式并改写这段代码。（提示：检查 4 个分量之和是否为 0。）

**Q11.**（扩展）`rollout` 最多走 `max_steps=100` 步。如果第 100 步还没到终点，`gae_advantages` 对最后一步会把 `next_v` 设为 `0.0`。这在语义上有什么问题？请修改 `rollout` 和 `gae_advantages`，让"被截断（truncated）"的轨迹用 `V(s_T)` 做 bootstrap，而"真正终止（terminated）"的轨迹仍用 0。

**Q12.**（读输出）运行 `main.py` 最后一行输出为 `final mean return (last 150 eps) = -6.11  (optimal = -6.0)`，而 critic 价值表里左下角 `(3,0)` 的值是 `-14.06`，远比 `(0,0)` 的 `-6.08` 更负。请解释：(a) 为什么"最优 -6.0"这个对比并不严格？(b) 为什么 `(3,0)` 的价值估计这么离谱？

---

## 四、面试高频题

**Q13.**（基础必考）为什么在 policy gradient 中减去 baseline 不会引入偏差？请给出推导，并说明为什么 `V(s)` 是一个"好"的 baseline。

**Q14.**（原理深挖）解释 GAE(λ) 的公式与直觉。γ 和 λ 都是 0~1 之间的折扣，它们的作用有什么本质区别？实践中怎么调？

**Q15.**（工程实践）A3C 和 A2C 有什么区别？为什么 2026 年的主流是 GPU 批处理的 A2C（及其后继 PPO），而不是 A3C？IMPALA 又解决了什么问题？

**Q16.**（工程实践）你训练一个 A2C agent，发现 300 次更新后回报停滞，策略熵已降到 0.05。请列出你会检查的点以及对应的修复手段。

**Q17.**（结合大模型）在 LLM 的 RLHF/推理强化学习中，PPO 需要一个和 policy 同规模的 critic。为什么这很贵？GRPO 这类方法是怎么"去掉 critic"的？代价是什么？

**Q18.**（追问型）面试官追问："actor 和 critic 要不要共享网络？" 请从图像输入、损失量纲、梯度干扰三个角度回答。

---

## 五、参考答案与解析

### Q1 — 答案：B

关键恒等式：`E_{a~π}[∇log π(a|s)·b(s)] = b(s)·Σ_a ∇π(a|s) = b(s)·∇Σ_a π(a|s) = b(s)·∇1 = 0`。所以减去任何**只依赖状态**的 baseline 都不改变期望，A 错。方差通常下降，因为 `G_t - b(s_t)` 的数值范围被"居中"了。C 错在方差确实变了。D 错在：任何状态函数都保持无偏，`V(s)` 只是方差最小的近似最优选择（讲义："The best tractable baseline is `V̂(s_t)`"）。

### Q2 — 答案：B

`A^GAE = Σ (γλ)ˡ δ_{t+l}`，λ=0 时只剩 `l=0` 项，即 `δ_t`。A 是 λ=1 的情形；D 是固定 n 的 n-step，不是 GAE 的特例端点。

### Q3 — 答案：C

γ 是**问题定义**的一部分（我们在乎多远的未来回报），改变 γ 就改变了要优化的目标；λ 是**估计器**的参数，只在偏差和方差之间做权衡，不改变目标本身（λ=1 时 GAE 对给定 γ 是无偏的）。所以 C 错。A、B、D 都正确。

### Q4 — 答案：B

最小化 `L` 等价于最大化 `c_e·H(π)`，即奖励高熵、惩罚过早确定。讲义 Pitfalls："Without `c_e > 0`, policy becomes near-deterministic in a few hundred updates and stops exploring." A 方向反了；C 错，熵只和 actor 有关；D 错，负号是刻意的。

### Q5 — 答案：C

A3C 的卖点正是"No replay buffer needed — workers decorrelate by running different trajectories"，A 错。B 把同步/异步说反了。D 错：讲义明确"No locks on the master — races are ok, they just add noise"（Hogwild 式更新）。C 准确描述了二者，以及 GPU 时代 A2C 占主导的原因。

### Q6 — 答案：B

讲义 Pitfalls："A2C reuses data for exactly one update. More and your gradient is biased (importance-sampling correction is what PPO adds)." 第一次更新后 `π_θ` 已不是采样时的策略，继续用旧样本估计的 `E_{π_θ}[...]` 就不再正确。PPO 用比率 `π_θ/π_old` 加裁剪来安全地多轮复用。

### Q7 — 答案：B

随机 critic 给出的 `V(s)` 和真实价值无关，`A = G - V` 或 `δ` 几乎是随机数。虽然 MC 形式的 baseline 理论上仍无偏，但方差可能比不用 baseline 还大；TD/GAE 形式则直接引入大偏差。讲义建议"Warm up the critic for a few hundred steps before turning on the policy gradient, or use a slow actor learning rate"。A 只说对了一半（期望），忽略了方差和 TD 偏差。

### Q8 — 答案：B

标准化只是对 advantage 做仿射变换：它会改变梯度的尺度，并且减去 batch 均值也不再是严格无偏，所以 A 错；但它让不同 batch、不同任务的梯度幅度可比，"Stabilizes training massively at near-zero cost"。C 错：标准化不能替代 critic。D 错：标准化后约一半样本的 advantage 为负，对应动作的概率会下降。

### Q9 — 参考答案

逐步倒推（`gamma=1.0`）：

| t | next_v | δ_t |
|---|--------|-----|
| 2 | 0（done） | -1 + 0 - (-0.5) = **-0.5** |
| 1 | v₂ = -0.5 | -1 + (-0.5) - (-1.5) = **0.0** |
| 0 | v₁ = -1.5 | -1 + (-1.5) - (-2.0) = **-0.5** |

- `lam=0.0`：`advantages = [-0.5, 0.0, -0.5]`，`returns = [-2.5, -1.5, -1.0]`
- `lam=0.5`：A₂ = -0.5；A₁ = 0 + 0.5·(-0.5) = -0.25；A₀ = -0.5 + 0.5·(-0.25) = -0.625 → `advantages = [-0.625, -0.25, -0.5]`，`returns = [-2.625, -1.75, -1.0]`
- `lam=1.0`：`advantages = [-1.0, -0.5, -0.5]`，`returns = [-3.0, -2.0, -1.0]`

（以上数值已在本地导入 `main.py` 实际运行验证。）

λ=1 时 `returns = A + V` 恰好等于**折扣 Monte Carlo 回报** `G_t`（这里 γ=1，就是剩余步数的负数：-3、-2、-1）。因为 λ=1 时 δ 序列求和会"望远镜式"相消：`Σ γˡδ_{t+l} = G_t - V(s_t)`。这也说明 critic 的回归目标 `returns` 在 λ=1 时退化为 MC 目标，λ<1 时是 TD(λ) 目标。

### Q10 — 参考答案

**不精确。** 设 `p = softmax(z)`，`H = -Σ_k p_k log p_k`。对 logit 求导：

```text
∂H/∂z_i = -Σ_k (∂p_k/∂z_i)(log p_k + 1)
        = -Σ_k p_k(δ_ki - p_i)(log p_k + 1)
        = -p_i(log p_i + 1) + p_i·Σ_k p_k(log p_k + 1)
        = -p_i(log p_i + 1) + p_i(1 - H)
        = -p_i(log p_i + H)
```

代码写的是 `p_i·(-log p_i - 1) = -p_i(log p_i + 1)`，只算到了 `∂H/∂p_i · p_i`，漏掉了 softmax Jacobian 中 `-p_i p_k` 那一项。验证方法：正确梯度对 4 个分量求和为 `-Σp_i log p_i - H = 0`（softmax 对所有 logit 加同一常数不变，梯度之和必为 0），而代码版本之和是 `H - 1 ≠ 0`。用 logits `[0.5, -0.2, 1.3, 0.1]` 做有限差分：数值梯度 `[0.060, 0.109, -0.271, 0.102]`，代码给出 `[0.109, 0.133, -0.162, 0.134]`，差距明显。

修正：

```python
probs = node["probs"]
H = -sum(p * math.log(max(p, 1e-12)) for p in probs)
for i in range(N_ACTIONS):
    grad_logpi = (1.0 if i == node["a"] else 0.0) - probs[i]
    entropy_grad = -probs[i] * (math.log(max(probs[i], 1e-12)) + H)   # 精确的 ∂H/∂z_i
    for j in range(N_FEAT):
        theta[i][j] += lr_a * (adv * grad_logpi + ent_coef * entropy_grad) * node["x"][j]
```

为什么原代码仍然能训练出接近最优的策略：`ent_coef=0.01` 很小，熵项只是一个微弱的正则；误差项 `p_i(H-1)` 的作用相当于"H>1 时轻微推高大概率动作、H<1 时轻微压低"，并不会主导更新方向。但在 PyTorch 里写 `-c_e * entropy.mean()` 交给 autograd 就不会有这个问题——这也是生产代码不手写梯度的原因。

### Q11 — 参考答案

**问题**：`next_v = 0` 的含义是"之后再也没有奖励了"，这对**真正终止**（到达 `TERMINAL`）是对的；但被 `max_steps` 截断时智能体其实还在格子里，后面还会继续每步 -1。把它当成终止，会让最后几步的 TD 目标系统性偏乐观（这里奖励为负，少算了未来的 -1），critic 和 advantage 都带偏差。这就是 Gymnasium 区分 `terminated` 与 `truncated` 的原因。

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
    # 截断：用 critic 对"下一个状态"的估计收尾；终止：0
    last_value = 0.0 if traj[-1]["done"] else value(w, features(s))
    return traj, last_value


def gae_advantages(traj, gamma=0.99, lam=0.95, last_value=0.0):
    T = len(traj)
    advantages = [0.0] * T
    gae = 0.0
    for t in reversed(range(T)):
        if traj[t]["done"]:
            next_v = 0.0
        elif t + 1 < T:
            next_v = traj[t + 1]["v"]
        else:
            next_v = last_value          # 截断时 bootstrap
        delta = traj[t]["r"] + gamma * next_v - traj[t]["v"]
        gae = delta + gamma * lam * gae
        advantages[t] = gae
    returns = [a + traj[t]["v"] for t, a in enumerate(advantages)]
    return advantages, returns
```

调用处改为 `traj, last_v = rollout(...)`、`gae_advantages(traj, ..., last_value=last_v)`。注意循环在截断时最后一次执行了 `s = s_next`，所以循环结束后的 `s` 正是 `s_T`。验证：两步截断轨迹 `v=[-2,-1.5]`、`γ=λ=1`、`last_value=-1` 时，原版给出 `advantages=[0.0, 0.5]`，修正版给出 `[-1.0, -0.5]`，后者把"还没走完的路"算进去了。这正是讲义 Key Terms 中 **Bootstrap** 的含义："Truncate the rollout, add `γ^n V(s_{t+n})` to close the sum."

### Q12 — 参考答案

(a) `returns_log` 里记录的是**折扣回报**：`mc_return = r + gamma * mc_return`，γ=0.99。最优路径 6 步、每步 -1，折扣后是 `-(1 + 0.99 + … + 0.99⁵) ≈ -5.85`，而不是 -6.0。-6.0 是**未折扣**的最优步数。所以 -6.11 与真正的折扣最优值相差约 0.26，主要来自策略仍有随机性（softmax 采样）偶尔多走一两步。

(b) critic 是一个 one-hot 线性模型（等价于查表），只有被访问到的状态才会被更新。学到的策略几乎总是先向右再向下（或沿对角线），`(3,0)` 这类远离最优路径的格子很少被访问，其价值主要来自训练早期随机策略下的长回合，之后几乎不再更新，所以停留在一个"很差"的旧估计上。`(3,3)` 是 0，是因为终点在 rollout 里从不作为"当前状态"出现。这说明：**critic 只在 on-policy 分布上准确**——这也是 actor-critic 方法"只对当前策略访问的状态负责"的典型现象。

### Q13 — 参考回答要点

- **推导**：policy gradient `∇J = E[Σ_t ∇log π(a_t|s_t)·(G_t - b(s_t))]`。对 baseline 项，固定 `s_t` 对动作取期望：`E_a[∇log π(a|s)·b(s)] = b(s)·Σ_a π(a|s)∇log π(a|s) = b(s)·Σ_a ∇π(a|s) = b(s)·∇1 = 0`。所以 baseline 项的期望为 0，不引入偏差。
- **为什么 V(s) 好**：方差最小化的最优 baseline 近似就是 `E[G_t|s_t] = V(s_t)`（精确最优 baseline 还带 `‖∇log π‖²` 权重，但实践中用 V 足够）。减去它后，乘子变成 advantage：比平均好就加强、比平均差就削弱，符号信息更干净。
- **关键前提**：baseline 不能依赖当前动作 `a_t`，否则上面的求和推不出 0。
- **加分点**：指出"MC advantage 无偏但用 TD/GAE 估计时会因为 V 不准引入偏差"；提到 Konda & Tsitsiklis 的双时间尺度（critic 学得比 actor 快）收敛结果。
- **常见误区**：以为"baseline 必须等于真实 V 才无偏"。

### Q14 — 参考回答要点

- **公式**：`δ_t = r_{t+1} + γV(s_{t+1}) - V(s_t)`，`A_t^{GAE} = Σ_{l≥0} (γλ)ˡ δ_{t+l}`。等价于对 1-step、2-step、…、∞-step 优势按 `(1-λ)λ^{n-1}` 做加权平均。
- **两个端点**：λ=0 → `δ_t`（低方差、高偏差，强依赖 critic）；λ=1 → `G_t - V(s_t)`（无偏、高方差）。
- **γ vs λ**：γ 定义"优化什么"（有效视界 ≈ `1/(1-γ)`），属于目标；λ 只决定"怎么估计这个目标的优势"，属于估计器。改 γ 会改变最优策略，改 λ 不会。
- **实现**：倒序递推 `gae = δ_t + γλ·gae`，O(T)；遇到终止要把 `next_v` 置 0 并截断递推，遇到截断要 bootstrap。
- **调参**：从 γ=0.99、λ=0.95 起步；critic 很准时可降低 λ 换更低方差；奖励稀疏、critic 不可靠时提高 λ。讲义练习建议扫 `λ ∈ {0, 0.5, 0.9, 0.95, 1.0}` 画"最终回报 vs 样本效率"找甜点。
- **加分点**：说出 `returns = advantages + values` 就是 TD(λ) 回报，作为 critic 的回归目标。

### Q15 — 参考回答要点

- **A3C**（Mnih et al. 2016）：N 个 worker 线程，各自一个环境、各自前向/反向，异步把梯度推到共享参数，无锁（race 只增加噪声）。不需要 replay buffer，靠多条不同轨迹去相关。证明了用 CPU 也能大规模训练。
- **A2C**：一个进程里跑 N 个环境，把观测堆成 `[N, obs_dim]` 的 batch，一次批量前向/反向，同步更新。确定性更好、更容易复现和调试，GPU 利用率高。
- **为什么 A2C 胜出**：GPU 喜欢大 batch；异步更新带来"梯度过时（stale gradient）"问题；同步版本与 PPO 的 rollout-then-update 结构天然兼容。讲义："In 2026, GPU-based A2C (batched parallel envs) dominates because GPUs want large batches."
- **IMPALA**：把"采样（actor）"和"学习（learner）"解耦到不同机器，actor 用的策略可能落后于 learner，因此数据是轻度 off-policy 的；用 **V-trace** 做截断重要性采样修正。讲义表格："IMPALA = A3C + V-trace off-policy correction"。
- **加分点**：能说出 A2C 的 batch 维度是 `N_envs × T_steps`，以及向量化环境（vectorized env）的实现方式。

### Q16 — 参考回答要点

按"最常见 → 较少见"排查：

1. **熵塌缩**：熵 0.05 已经很低。检查 `c_e` 是否为 0 或过小；讲义的 skill 文件建议"Flag any run with `c_e = 0` and observed entropy < 0.1 as entropy-collapsed"。修复：提高 `c_e`（如 0.01→0.02）、对熵系数做退火而非一开始就很小。
2. **advantage 未标准化 / 奖励尺度过大**：大幅度的 advantage 会让 softmax 迅速饱和。修复：per-batch 标准化 advantage，用 running std 归一化奖励。
3. **critic 不准**：看 value loss 和 explained variance；critic 落后时 advantage 是噪声。修复：critic 预热、提高 critic 学习率或 `c_v`、分离 critic 的优化器。
4. **学习率过大**：actor 一步就把策略推到确定。修复：降 actor 学习率、加梯度裁剪。
5. **违反 on-policy 约束**：是否不小心复用了旧 rollout 做多次更新？
6. **截断/终止处理错误**：timeout 被当成终止会让 critic 学错。
- **加分点**：给出监控指标清单——策略熵、approx KL（新旧策略差异）、value loss、explained variance、advantage 均值/方差、梯度范数。

### Q17 — 参考回答要点

- **为什么贵**：LLM 的 PPO 里 critic 通常和 policy 同规模（例如都是 7B），需要额外的参数、优化器状态和前/反向计算，显存和计算接近翻倍；而且 token 级价值很难学准，critic 的偏差会直接污染 advantage。
- **GRPO 的思路**：讲义表格把它概括为"A2C without the critic — group-relative advantage"。对同一个 prompt 采样一组回答，用组内奖励的均值（和标准差）做 baseline：`A_i = (r_i - mean(r)) / std(r)`。组均值相当于用同一 prompt 的多个样本去估计 `V(prompt)`，基本满足 Q13 的条件（严格说组均值包含样本自身的奖励，会把期望梯度缩放 `(1-1/G)` 倍；RLOO 用"留一均值"消除这一点）。
- **代价**：每个 prompt 要采样多条回答，推理开销上升；advantage 是序列级的，信用分配粒度粗；组内全对或全错时 advantage 为 0，没有学习信号。
- **加分点**：把 DPO 也放进谱系——讲义称其为"A2C collapsed into a preference-ranking loss, no sampling"；指出这些方法本质上都在找"更便宜的 baseline"。详细内容见第 08、09、12 节。

### Q18 — 参考回答要点

- **图像输入**：建议共享特征提取 trunk（CNN/ViT），分出 policy head 和 value head。讲义："The shared features free-ride on both losses." 样本效率更高、显存更省。
- **损失量纲**：value loss 的尺度依赖奖励尺度，可能比 policy loss 大几个数量级，会主导共享 trunk 的梯度。所以要用 `c_v`（如 0.5）平衡，并做奖励/回报归一化。
- **梯度干扰**：两个目标可能冲突，critic 的回归梯度会扰动 actor 学到的特征。低维状态（如 MuJoCo 关节角）时常用两个独立网络；PPO 的一些实现也默认分离。
- **结论**：图像/大模型 → 共享 trunk + 分离 head + 调好 `c_v`；低维连续控制 → 常分离网络。可以做消融实验决定。
- **常见误区**：共享网络后只用一个学习率、不调 `c_v`，结果 value loss 把 policy 特征"冲掉"。

---

## 六、关联知识点

### 前置知识
- [阶段 09 · 04 时序差分——Q-Learning 与 SARSA](../../04-q-learning-sarsa/docs/zh.md)：TD 目标 `r + γV(s')`、bootstrap 的概念，是 TD residual δ 的来源。
- [阶段 09 · 06 Policy Gradient — REINFORCE](../../06-policy-gradients-reinforce/docs/zh.md)：`∇log π` 的 score-function 推导和 softmax 策略梯度，本节直接在其上加 critic。
- [阶段 09 · 03 Monte Carlo 方法](../../03-monte-carlo-methods/docs/zh.md)：MC 回报 `G_t` 的无偏/高方差特性。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：熵 `H(π)` 的定义，熵奖励的数学基础。

### 本节被哪些后续内容用到
- [阶段 09 · 08 近端策略优化（PPO）](../../08-ppo/docs/zh.md)：PPO = A2C + 裁剪重要性比率，复用本节的 GAE 与组合损失。
- [阶段 09 · 09 奖励建模 & RLHF](../../09-reward-modeling-rlhf/docs/zh.md)：RLHF 的 PPO 阶段用的就是 actor-critic 结构。
- [阶段 09 · 10 多 Agent RL](../../10-multi-agent-rl/docs/zh.md)：MAPPO / 集中式 critic（CTDE）在多智能体场景扩展了 critic 的输入。
- [阶段 09 · 12 游戏强化学习](../../12-rl-for-games/docs/zh.md)：AlphaZero 的 policy + value 双头网络、GRPO 的无 critic 优势估计。
- [阶段 10 · 07 RLHF](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)：在 LLM 上实现 PPO 的 actor-critic。
- [阶段 16 · 20 MARL：MADDPG / QMIX / MAPPO](../../../16-multi-agent-and-swarms/20-marl-maddpg-qmix-mappo/docs/zh.md)：集中式 critic 的多智能体 actor-critic。

### 延伸关键词
`TD(λ)` · `eligibility trace` · `V-trace (IMPALA)` · `SAC / soft actor-critic` · `DDPG / TD3` · `explained variance` · `vectorized env` · `Hogwild!` · `terminated vs truncated` · `two-timescale stochastic approximation`
