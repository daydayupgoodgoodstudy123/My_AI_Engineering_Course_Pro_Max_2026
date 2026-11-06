# 测验 · 近端策略优化（Proximal Policy Optimization, PPO）

> **阶段 09 · 强化学习 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | A2C 的浪费 | A2C 是严格 on-policy 的，一次 rollout 只能做一次更新；rollout 很贵，用一次就扔太浪费 |
| 2 | 重要性比率 | `r_t(θ) = π_θ(a_t\|s_t) / π_old(a_t\|s_t)`，衡量新策略相对采样策略的偏离；数值上用 `exp(log π_θ - log π_old)` 计算 |
| 3 | TRPO → PPO | TRPO 用硬 KL 约束 + 共轭梯度求解；PPO 用一个裁剪目标替代，"one extra line of code" |
| 4 | 裁剪代理目标 | `L^CLIP = E[min(r·A, clip(r, 1-ε, 1+ε)·A)]`，ε 通常取 0.2 |
| 5 | 裁剪的方向性 | A>0 且 r>1+ε、或 A<0 且 r<1-ε 时梯度为 0（已经往"有利方向"走够了）；往"不利方向"偏离时不裁剪，梯度继续纠正 |
| 6 | 完整损失与训练循环 | `L^CLIP - c_v·(V - V_target)² + c_e·H`；收集 N×T → 冻结 GAE 与 `log π_old` → K 个 epoch × 若干 minibatch → 丢弃数据 |
| 7 | 三大诊断指标 | mean KL（约 0~0.02，超过 0.1 要减 K 或 LR）、clip fraction（约 0.1~0.3）、explained variance（应逐渐接近 1） |
| 8 | KL 惩罚变体 | `L^PG - β·KL(π_θ‖π_old)`，自适应调 β；裁剪版更流行，KL 版在 RLHF 中延续（对参考模型的 KL） |
| 9 | 常见坑 | ε 误调、K 过大、无奖励/advantage 归一化、LR 不衰减、比率直接相除、梯度符号写反 |
| 10 | PPO 家族 | RLHF 用 PPO + 参考模型 KL；GRPO 去掉 critic；DPO 把 PPO+KL 闭式化为偏好损失 |

### 核心技能（能动手做到）

- [ ] 在 rollout 时正确缓存 `log π_old(a|s)` 和 `V_old(s)`，并说明为什么更新期间它们必须保持不变
- [ ] 给定 (advantage, ratio) 判断是否被裁剪、梯度系数是多少，并画出 A>0 / A<0 两种情况下 `L^CLIP` 关于 r 的分段线性图
- [ ] 从零实现 K epoch × minibatch 的 PPO 更新循环，并统计 mean KL 与 clip fraction
- [ ] 找出并修复"多条轨迹拼接后 GAE 跨回合泄漏"的 bug
- [ ] 实现 explained variance 诊断，并据三大指标给出调参动作（调 K、LR、ε）
- [ ] 把裁剪目标替换为自适应 KL 惩罚（β 加倍/减半规则），比较稳定性
- [ ] 说清 PPO 在 RLHF 中需要哪几个模型、KL 惩罚加在哪里、为什么 GRPO 能省掉 critic

---

## 二、基础自测（选择题）

**Q1.** PPO 相比 A2C 最核心的改进是：

- A. 引入了 critic 网络
- B. 用裁剪的重要性比率，使同一批 rollout 可以安全地做多个 epoch 的更新
- C. 改成了 off-policy，可以使用任意旧数据的 replay buffer
- D. 去掉了 advantage，只用回报

**Q2.** 设 ε=0.2，某样本 advantage `A = +1`，当前比率 `r = 1.3`。该样本对 θ 的策略梯度贡献是：

- A. `1.3 · ∇log π`
- B. `1.2 · ∇log π`
- C. 0（被裁剪）
- D. `-1.3 · ∇log π`

**Q3.** 设 ε=0.2，某样本 `A = -1`，当前比率 `r = 1.3`（坏动作的概率反而被提高了）。PPO 会：

- A. 裁剪，梯度为 0
- B. 不裁剪，继续给出梯度把这个动作的概率往下压
- C. 把 r 强行设回 1
- D. 丢弃这个样本

**Q4.** 关于 TRPO 和 PPO，下列说法正确的是：

- A. PPO 的理论保证严格强于 TRPO
- B. TRPO 用硬 KL 约束，每次更新要做共轭梯度求解；PPO 用裁剪目标近似信赖域，只需一阶优化
- C. PPO 必须计算 Fisher 信息矩阵
- D. 两者都允许无限次复用旧数据

**Q5.** 训练中观察到 clip fraction 长期在 0.5 以上，mean KL 约 0.15。最合理的调整是：

- A. 增大学习率、增大 K
- B. 减小 K（epoch 数）或学习率
- C. 把 ε 调到 0.5
- D. 关掉 advantage 标准化

**Q6.** 计算重要性比率时推荐 `exp(log_new - log_old)` 而不是 `new / old`，主要原因是：

- A. 速度更快
- B. 数值稳定：概率可能极小，直接相除容易下溢/除零，在 log 空间相减更稳
- C. 两者数学上不相等
- D. 为了让比率恒大于 1

**Q7.** PPO 在 RLHF 中最常见的形态是：

- A. 不用奖励模型，直接用人类实时打分
- B. 对参考模型加 KL 惩罚，奖励来自奖励模型、在回答结束时给出
- C. 不需要任何 KL 约束，因为裁剪已经足够
- D. 使用 replay buffer 存储数百万条旧回答反复训练

**Q8.** 关于 PPO 是否 on-policy，最准确的说法是：

- A. 完全 off-policy
- B. 严格 on-policy，和 A2C 一样每批数据只用一次
- C. 名义上 on-policy，但 K>1 个 epoch 用的是"略微 off-policy"的数据，靠重要性比率和裁剪保证安全
- D. 取决于是否使用 GAE

---

## 三、动手 / 代码题

**Q9.**（预测输出）本节代码中判断裁剪和计算梯度系数的逻辑是：

```python
clipped = (adv > 0 and ratio > 1 + eps) or (adv < 0 and ratio < 1 - eps)
...
if not clipped:
    pg_scale = ratio * adv
else:
    pg_scale = 0.0
```

取 `eps=0.2`，对下面 5 组 `(adv, ratio)` 分别写出 `clipped`、`pg_scale`，以及裁剪目标 `min(r·A, clip(r, 0.8, 1.2)·A)` 的值：

`(1.0, 1.3)`、`(1.0, 0.7)`、`(-1.0, 0.7)`、`(-1.0, 1.3)`、`(1.0, 1.1)`

并说明：为什么 `pg_scale` 是 `ratio * adv` 而不是 `adv`？

**Q10.**（找 bug）`collect_rollout` 把 8 个环境的轨迹**首尾相接**放进同一个 `buffer`，然后调用：

```python
def gae(buffer, gamma=0.99, lam=0.95):
    T = len(buffer)
    advantages = [0.0] * T
    gae_val = 0.0
    for t in reversed(range(T)):
        next_v = 0.0 if buffer[t]["done"] else (buffer[t + 1]["v_old"] if t + 1 < T else 0.0)
        delta = buffer[t]["r"] + gamma * next_v - buffer[t]["v_old"]
        gae_val = delta + gamma * lam * gae_val
        advantages[t] = gae_val
    returns = [a + buffer[t]["v_old"] for t, a in enumerate(advantages)]
    return advantages, returns
```

考虑一个手工构造的 buffer（`gamma=1.0, lam=1.0`）：环境 A 走 2 步终止，环境 B 走 2 步被截断（真实的下一状态价值为 -3）：

```python
buf = [
    {"r": -1.0, "v_old": -2.0, "done": False},
    {"r": -1.0, "v_old": -1.0, "done": True},   # 环境 A 结束
    {"r": -1.0, "v_old": -5.0, "done": False},  # 环境 B 开始
    {"r": -1.0, "v_old": -4.0, "done": False},  # 环境 B 被 horizon 截断
]
```

(a) 这里 critic 对每个状态的估计其实都是准确的，真实 advantage 应该全为 0。代码会输出什么？(b) 指出两处问题，并给出修复方案。

**Q11.**（扩展）`ppo_update` 只返回 `mean_kl` 和 `clip_frac`，没有讲义 Step 5 提到的 **explained variance**，也没有 Step 4 的**熵奖励**。请：(a) 写一个 `explained_variance(y_true, y_pred)` 函数；(b) 说明熵奖励应该加在 `ppo_update` 的哪一行、怎么加（给出线性 softmax 下的梯度形式）。

**Q12.**（读输出）运行本节代码得到：

```text
  update  10  mean_return=-12.00  mean_KL=+0.0159  clip_frac=0.112
  update  20  mean_return= -7.42  mean_KL=-0.0046  clip_frac=0.136
  update  30  mean_return= -6.40  mean_KL=+0.0046  clip_frac=0.010
```

(a) mean KL 为什么会出现**负数**？KL 散度不是非负的吗？(b) 代码里的 `clip_frac` 和讲义定义的"比率落在 `[1-ε, 1+ε]` 之外的样本比例"是否完全一样？

---

## 四、面试高频题

**Q13.**（基础必考）请写出 PPO 的裁剪目标，并分 A>0 和 A<0 两种情况解释 `min` 和 `clip` 各自的作用。为什么说它是一种"悲观的下界"？

**Q14.**（原理深挖）PPO 和 TRPO 的关系是什么？PPO 的裁剪真的能保证新旧策略的 KL 很小吗？如果不能，工程上还有什么兜底手段？

**Q15.**（工程实践）你接手一个 PPO 训练任务，回报曲线剧烈震荡且偶尔崩溃。请给出排查清单（至少 6 项），并说明每项对应看什么指标。

**Q16.**（结合大模型）描述 PPO 在 RLHF 中的完整流程：需要几个模型？奖励怎么构成？KL 惩罚加在哪里，为什么？

**Q17.**（场景设计）你要在一个 10 亿参数的推理模型上做 RL，预算有限。你会选 PPO、GRPO 还是 DPO？请说明各自的数据需求、显存开销与适用前提。

**Q18.**（追问型）面试官追问："PPO 的 K 个 epoch 里，为什么 advantage 要冻结成常数、而不是每个 epoch 重新用最新的 critic 计算？"

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义开篇："PPO wraps the policy gradient in a clipped importance ratio so you can do 10+ epochs on the same data without the policy exploding." A 错：critic 在 A2C 里就有了。C 错：PPO 仍是"on-policy-ish"，每批数据用完就丢，不使用长期 replay buffer。D 错：PPO 依然用 GAE advantage。

### Q2 — 答案：C

A>0 且 r=1.3>1+ε=1.2：`min(1.3·1, 1.2·1) = 1.2`，取的是裁剪项，它对 θ 是常数，梯度为 0。含义：好动作的概率已经比旧策略高出 30%，超过了允许的 20%，不再继续推。B 是目标函数值而不是梯度。

### Q3 — 答案：B

A<0 且 r=1.3：`r·A = -1.3`，`clip(r)·A = 1.2·(-1) = -1.2`，`min` 取 `-1.3`，即**未裁剪**项，梯度照常流动，把这个坏动作的概率往下压。这就是 `min` 的作用：往"不利方向"偏离时不提供保护，让梯度纠正错误。只有当 A<0 且 r<1-ε（坏动作已经被压低足够多）时才裁剪。

### Q4 — 答案：B

讲义："TRPO ... constrain each update so the KL divergence between old and new policy stays below δ ... requires a conjugate-gradient solve per update"；PPO "replaces the hard trust-region constraint with a simple clipped objective"，理论保证只是"good-enough"，所以 A 错。C 是 TRPO（自然梯度）的特征。D 错：两者都只能在旧策略附近有限复用。

### Q5 — 答案：B

讲义诊断规则："If [KL] blows past 0.1, reduce K_EPOCHS or LR"；clip fraction "If ~0.5+, you are over-fitting the rollout → lower them." A 方向相反。C：讲义的 skill 文件明确拒绝 `ε > 0.3`（unsafe trust region）。D 会让训练更不稳定。

### Q6 — 答案：B

讲义 Pitfalls："Always `exp(log_new - log_old)` for numerical stability, not `new / old`." 在 LLM 场景中单个 token 的概率可能是 1e-20 量级，直接存概率再相除容易下溢；而且框架本来就输出 log-prob。C 错：数学上两者相等。

### Q7 — 答案：B

讲义 Use It 表："RLHF for LLMs | PPO with KL penalty to reference model, reward from RM at end of response"。C 错：对参考模型的 KL 是独立于裁剪的约束，用来防止 reward hacking 和语言能力退化。

### Q8 — 答案：C

讲义 Key Terms："PPO is nominally on-policy but K>1 epochs uses slightly-off-policy data safely." 第一个 epoch 的第一个 minibatch 是严格 on-policy 的（r≈1），之后策略逐渐偏离，靠比率修正 + 裁剪限制偏离程度。

### Q9 — 参考答案

| (adv, ratio) | clipped | pg_scale | 裁剪目标值 |
|---|---|---|---|
| (1.0, 1.3) | True | 0.0 | 1.2 |
| (1.0, 0.7) | False | 0.7 | 0.7 |
| (-1.0, 0.7) | True | 0.0 | -0.8 |
| (-1.0, 1.3) | False | -1.3 | -1.3 |
| (1.0, 1.1) | False | 1.1 | 1.1 |

（已用代码中的判断逻辑实际计算验证。）

解读：
- (1.0, 0.7)：好动作的概率反而降低了，`min(0.7, 0.8) = 0.7` 取未裁剪项，梯度继续推高它。
- (-1.0, 0.7)：坏动作已经被压低 30%，`min(-0.7, -0.8) = -0.8` 取裁剪项（常数），梯度为 0。

为什么是 `ratio * adv`：未裁剪时目标是 `r(θ)·A = (π_θ/π_old)·A`，对 θ 求导得 `A·∇π_θ/π_old = A·(π_θ/π_old)·∇log π_θ = r·A·∇log π_θ`。代码随后乘以 `grad_logpi`（即 `∇log π`），所以系数是 `ratio * adv`。在第一个 epoch 开始时 r≈1，它退化为 A2C 的 `A·∇log π`；之后 r 偏离 1，相当于用重要性权重修正"数据来自旧策略"这一事实。

### Q10 — 参考答案

(a) 逐步倒推（γ=λ=1）：

- t=3：不是 done 但 `t+1 < T` 不成立 → `next_v = 0`；`δ = -1 + 0 - (-4) = 3`；`gae_val = 3`
- t=2：`next_v = -4`；`δ = -1 - 4 + 5 = 0`；`gae_val = 0 + 3 = 3`
- t=1：done → `next_v = 0`；`δ = -1 + 0 + 1 = 0`；但 `gae_val = 0 + 1·3 = 3`（**泄漏**）
- t=0：`next_v = -1`；`δ = -1 - 1 + 2 = 0`；`gae_val = 3`

代码输出 `advantages = [3.0, 3.0, 3.0, 3.0]`，而正确答案是 `[0, 0, 0, 0]`（已实际运行验证）。

(b) 两处问题：

1. **跨回合泄漏**：遇到 `done=True` 时只把 `next_v` 置 0，却没有把递推变量 `gae_val` 清零，于是下一条轨迹（在 buffer 中排在后面）的 advantage 以 `γλ` 的权重"漏"进了上一条轨迹的终止步。标准写法是 `gae_val = delta + gamma * lam * (1 - done) * gae_val`。
2. **截断当作终止 / 引用错误状态**：环境被 `horizon=50` 截断时 `done=False`。若它在 buffer 中间，`next_v` 会取到**下一个环境起点 (0,0)** 的价值——一个完全无关的状态；若它在 buffer 末尾，`next_v=0`，把截断当终止。两种情况下 `gae_val` 也都没被截断。

修复（在 rollout 时记录每条轨迹的末尾和真正的下一状态价值）：

```python
# collect_rollout 内：
last = done or t == horizon - 1          # 需要把内层循环改为 for t in range(horizon)
buffer.append({
    "x": x, "a": a, "r": r, "done": done, "last": last,
    "v_next": 0.0 if done else value(w, features(s_next)),
    "v_old": value(w, x),
    "log_pi_old": math.log(max(probs[a], 1e-12)),
})

def gae(buffer, gamma=0.99, lam=0.95):
    T = len(buffer)
    advantages = [0.0] * T
    gae_val = 0.0
    for t in reversed(range(T)):
        if buffer[t]["last"]:                 # 轨迹边界：终止用 0，截断用 V(s_{t+1})
            gae_val = 0.0
            next_v = buffer[t]["v_next"]
        else:
            next_v = buffer[t + 1]["v_old"]
        delta = buffer[t]["r"] + gamma * next_v - buffer[t]["v_old"]
        gae_val = delta + gamma * lam * gae_val
        advantages[t] = gae_val
    returns = [a + buffer[t]["v_old"] for t, a in enumerate(advantages)]
    return advantages, returns
```

在 4×4 网格上用 5 个随机种子对比，原版与修复版最终回报都在 -6.1~-6.2 左右，差别很小（小网格、回合短、critic 很快变准，掩盖了偏差）；但在长回合任务和向量化环境（环境会自动 reset，一个 rollout 里包含多段回合，必须靠 done/截断标志切断递推）里，这是一个会让 critic 和 advantage 系统性出错的经典 bug。

### Q11 — 参考答案

(a)

```python
def explained_variance(y_true, y_pred):
    n = len(y_true)
    mean_t = sum(y_true) / n
    var_t = sum((y - mean_t) ** 2 for y in y_true) / n
    diff = [t - p for t, p in zip(y_true, y_pred)]
    mean_d = sum(diff) / n
    var_d = sum((d - mean_d) ** 2 for d in diff) / n
    return float("nan") if var_t == 0 else 1.0 - var_d / var_t

# 用法：在 ppo_update 之前
ev = explained_variance(returns, [rec["v_old"] for rec in buffer])
```

讲义公式 `1 - Var(V_target - V_pred) / Var(V_target)`：=1 表示 critic 完美，≈0 表示 critic 和"直接猜均值"一样，<0 表示比猜均值还差。

(b) 在 `for action in range(N_ACTIONS):` 那段 actor 更新里加熵项。线性 softmax 下 `∂H/∂z_i = -π_i(log π_i + H)`，所以：

```python
H = -sum(p * math.log(max(p, 1e-12)) for p in probs)
for action in range(N_ACTIONS):
    grad_logpi = (1.0 if action == rec["a"] else 0.0) - probs[action]
    ent_grad = -probs[action] * (math.log(max(probs[action], 1e-12)) + H)
    for j in range(N_FEAT):
        theta[action][j] += lr_a * (pg_scale * grad_logpi + c_e * ent_grad) * x[j]
```

注意 `probs` 是当前 θ 下重新计算的（不是 rollout 时的旧概率），熵项本身不参与裁剪。讲义完整损失 `L^CLIP - c_v·(V - V_target)² + c_e·H` 里熵是加号（最大化），`c_e` 常取 0.01。

### Q12 — 参考答案

(a) 代码用 `kl_total += rec["log_pi_old"] - logp` 并取平均，这是 KL(π_old‖π_θ) 的**单样本蒙特卡洛估计**（常称 k1 估计量）。只有对 `a ~ π_old` 取**期望**时它才等于非负的 KL；单个样本的 `log π_old - log π_θ` 可以为负（新策略提高了该动作概率），样本有限时平均值也可能为负。另外这里的 `logp` 是在一个 epoch 内不断更新的 θ 下计算的，且对所有 epoch 求平均，统计口径也不是严格的"更新后 KL"。生产中常改用 `((r - 1) - log r)` 这种恒非负、方差更低的估计量（k3）。

(b) 不完全一样。代码里 `clipped` 只统计**梯度被置零**的样本（A>0 且 r>1+ε，或 A<0 且 r<1-ε）；而讲义定义的 clip fraction 是"比率落在区间外"的比例，也包括 A>0 且 r<1-ε 这种"在区间外但没被裁剪"的样本。因此代码的 `clip_frac` 会偏小。CleanRL 等实现通常用 `mean(|r - 1| > ε)`。两种口径都能用，但比较阈值（0.1~0.3）时要统一。

### Q13 — 参考回答要点

- **公式**：`L^CLIP(θ) = E_t[min(r_t·A_t, clip(r_t, 1-ε, 1+ε)·A_t)]`，`r_t = π_θ(a_t|s_t)/π_old(a_t|s_t)`。
- **A>0**：目标随 r 线性增长，到 `1+ε` 后变成平顶（clip 生效，梯度为 0）——好动作最多推到旧概率的 1+ε 倍。r<1 时（好动作概率反而下降）`min` 选未裁剪项，梯度照常把它推回来。
- **A<0**：r 越小目标越大，到 `1-ε` 以下变平（梯度为 0）——坏动作最多压到 1-ε 倍。r>1 时（坏动作概率反而上升）不裁剪，梯度持续纠正。
- **悲观下界**：`min` 总是在"未裁剪目标"和"裁剪目标"中取更小的，因此 `L^CLIP ≤ r·A`（未裁剪的重要性采样代理目标），是对改进量的保守估计——只拿"有把握的收益"，不放大不可信的外推。
- **常见误区**：以为裁剪是对称地把 r 夹在 [0.8, 1.2]——实际上只在"有利方向"截断，"不利方向"不设限。
- **加分点**：能画出两张分段线性图；指出梯度为 0 的区域就是讲义所说的"flat roof / flat floor"。

### Q14 — 参考回答要点

- **关系**：两者都源于"信赖域"思想——每次更新不要离旧策略太远，以近似保证单调改进。TRPO 显式求解带 KL 约束的优化（共轭梯度 + 线搜索），二阶、实现复杂；PPO 用裁剪把约束"软化"到目标函数里，纯一阶 SGD，可配合 minibatch 和多 epoch。
- **裁剪能否保证 KL 小**：不能严格保证。裁剪只让**被裁剪的样本**不再贡献梯度，但参数共享会让其他样本的更新间接推动已裁剪样本的比率继续偏离；K 过大、LR 过大时 KL 仍会爆。Engstrom et al. (2020) 也指出 PPO 的很多稳定性来自"代码级技巧"而非裁剪本身。
- **兜底手段**：监控 approx KL 并在超过阈值时**提前停止**本轮 epoch（early stopping on KL）；限制 K（讲义建议 K>20 就容易失稳，skill 文件拒绝 K>30）；LR 线性衰减；梯度裁剪；advantage 与奖励归一化；或改用 KL 惩罚变体自适应调 β。
- **加分点**：提到 "What Matters In On-Policy RL"（Andrychowicz et al. 2021）对所有超参的消融。

### Q15 — 参考回答要点

| 排查项 | 看什么 / 怎么改 |
|---|---|
| 梯度符号 | 讲义："A flipped sign is the most common PPO bug." 最大化 surrogate = 最小化 `-L^CLIP` |
| 比率计算 | 是否用 `exp(logp_new - logp_old)`；`log π_old` 是否在 rollout 时缓存且更新期间不变 |
| mean KL | 稳定在 0~0.02；>0.1 → 减 K 或 LR，或加 KL early stop |
| clip fraction | 0.1~0.3；≈0 → 更新太保守；>0.4 持续 → 过拟合当前 rollout |
| explained variance | 应逐渐升高；长期 ≤0 说明 critic 没学好，advantage 是噪声 |
| advantage 归一化 | 是否 per-batch 零均值单位方差（讲义："Skipping it wrecks PPO"） |
| 奖励尺度 | 大奖励会"吃掉" clip 区间 → running-std 归一化奖励 |
| GAE 边界 | done/截断处是否正确截断递推、截断时是否 bootstrap（见 Q10） |
| LR 调度 | 是否线性衰减到 0 |
| 熵 | 是否塌缩到接近 0 |

加分点：先在小环境（CartPole/GridWorld）上复现参考实现（CleanRL 单文件 PPO）的曲线，再迁移到目标任务。

### Q16 — 参考回答要点

- **四个模型**：policy（被训练的 LLM，actor）、reference（冻结的 SFT 模型）、reward model（冻结，给整段回答打分）、value model（critic，常从 RM 或 policy 初始化）。
- **奖励构成**：讲义："reward from RM at end of response"——RM 分数只在最后一个 token 给出；每个 token 再加上 `-β·(log π_θ - log π_ref)` 的 KL 惩罚。也有实现把 KL 作为 loss 项而不是奖励项。
- **为什么要对参考模型 KL**：防止 policy 为了刷 RM 分数而偏离自然语言分布（reward hacking、输出退化、啰嗦）；RM 只在 SFT 分布附近可信，离开太远就会被"钻空子"。讲义："the KL variant survives in RLHF (where KL to the reference policy is a separate constraint you always want anyway)"。
- **训练循环**：采样 prompt → policy 生成回答（rollout）→ RM 打分 + KL → GAE（token 级）→ K epoch 裁剪更新 policy 和 value。
- **加分点**：区分两个 KL——PPO 内部 `π_θ` vs `π_old`（每轮 rollout 的快照，由裁剪控制）与 RLHF 的 `π_θ` vs `π_ref`（整个训练期间固定）。详见第 09 节和阶段 10 · 07。

### Q17 — 参考回答要点

- **PPO**：需要在线采样 + 奖励信号（RM 或可验证奖励），四个模型同时在显存里（policy、ref、RM、critic），开销最大；优点是最通用、token 级信用分配。
- **GRPO**：讲义 Use It："PPO variant without critic"。每个 prompt 采样一组回答，用组内相对奖励做 advantage，省掉 critic（显存和计算显著下降）；特别适合**可验证奖励**（数学答案、单元测试）的推理任务。代价是每个 prompt 要多次采样。
- **DPO**：讲义："closed-form collapsing of PPO+KL, no online sampling"。只需要离线偏好对 (chosen, rejected)，像监督学习一样训练，只需 policy + ref 两个模型，最便宜；但不在线探索，效果受限于偏好数据的覆盖面。
- **推荐**：推理任务有可验证奖励 → 首选 GRPO；只有人类偏好数据、预算最紧 → DPO；奖励来自学习的 RM 且需要细粒度信用分配、资源充足 → PPO。
- **加分点**：指出三者共享同一个"advantage × log π + KL 约束"骨架，只是在"baseline 从哪来、是否在线采样"上做了不同取舍。

### Q18 — 参考回答要点

- **保持代理目标一致**：PPO 的理论是在旧策略处构造一个代理目标 `L(θ) = E_{π_old}[r(θ)·A^{π_old}]`，其中 advantage 属于**采样时的旧策略**。K 个 epoch 是在优化**同一个**代理目标；每个 epoch 重算 advantage 等于不断挪动目标，裁剪的语义（相对 `π_old` 的偏离）也会被破坏。
- **避免自我强化的偏差**：critic 也在同一批数据上训练，如果用刚拟合这批数据的 critic 重新算 advantage，advantage 可能被部分"拟合掉"（V 越贴近这批回报，`G - V` 越接近 0），策略信号变弱。
- **工程简单**：rollout 后一次性计算、冻结，minibatch 可以随意 shuffle。讲义训练循环第 2 步："Compute advantages (GAE), freeze them as constants."
- **对应代码**：`collect_rollout` 存下 `v_old` 和 `log_pi_old`，`gae` 只用 `v_old`；`ppo_update` 一开始就把 `adv`、`ret` 写进每条记录，整个 K epoch 不再改动。
- **加分点**：也有实现选择在每个 epoch 开始时用最新 critic 重新计算 advantage，大规模消融研究（如讲义推荐的 Andrychowicz et al. 2021）把这类"数据如何划分与复用"的细节当作可调设计选项来比较；但标准 PPO 训练循环和本节代码都是冻结的，改动它需要实验验证，不能想当然。

---

## 六、关联知识点

### 前置知识
- [阶段 09 · 06 Policy Gradient — REINFORCE](../../06-policy-gradients-reinforce/docs/zh.md)：`∇log π` 的推导，PPO 的比率梯度 `r·A·∇log π` 由此而来。
- [阶段 09 · 07 Actor-Critic — A2C 和 A3C](../../07-actor-critic-a2c-a3c/docs/zh.md)：GAE、组合损失、on-policy 约束；PPO = A2C + 裁剪比率。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：KL 散度与熵，理解信赖域和诊断指标。
- [阶段 01 · 16 采样方法](../../../01-math-foundations/16-sampling-methods/docs/zh.md)：重要性采样是比率 `π_θ/π_old` 的数学基础。

### 本节被哪些后续内容用到
- [阶段 09 · 09 奖励建模 & RLHF](../../09-reward-modeling-rlhf/docs/zh.md)：InstructGPT 式 RLHF 的第三阶段就是 PPO + 参考模型 KL。
- [阶段 09 · 10 多 Agent RL](../../10-multi-agent-rl/docs/zh.md)：MAPPO 把 PPO 扩展到多智能体。
- [阶段 09 · 12 游戏强化学习](../../12-rl-for-games/docs/zh.md)：GRPO 作为无 critic 的 PPO 变体，用于 LLM 推理强化学习。
- [阶段 10 · 07 RLHF](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)：在 LLM 上实现 PPO 的工程细节。
- [阶段 10 · 08 DPO](../../../10-llms-from-scratch/08-dpo/docs/zh.md)：把 PPO+KL 闭式化为偏好损失。
- [阶段 18 · 03 DPO 家族](../../../18-ethics-safety-alignment/03-direct-preference-optimization-family/docs/zh.md)：从对齐角度比较 PPO 与 DPO 系方法。

### 延伸关键词
`TRPO` · `natural policy gradient` · `PPO-KL / adaptive β` · `KL early stopping` · `approx KL (k1/k3 estimator)` · `PPG (Phasic Policy Gradient)` · `CleanRL` · `vectorized env` · `GRPO` · `RLOO` · `"37 implementation details of PPO"`
