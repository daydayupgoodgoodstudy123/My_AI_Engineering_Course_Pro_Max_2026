# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 08 节 近端策略优化（PPO） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 0.3 秒跑完） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这份代码在和上一节相同的 4×4 GridWorld 上，用纯 Python 实现了 PPO-Clip 的完整训练循环。环境、特征、softmax、采样等基础函数与第 07 节几乎一字不差，**真正的新东西集中在三处**：

1. **rollout 时冻结 `log π_old(a|s)` 和 `V_old(s)`**：这是重要性比率和 GAE 的"快照"，整个更新期间不变。
2. **多 epoch × minibatch 的更新**：同一批数据被打乱、切块、反复用 K=4 次——这正是 PPO 比 A2C 更省样本的地方。
3. **裁剪 → 梯度置零**：`clipped` 判断 + `pg_scale = ratio * adv` 或 `0.0`，一行实现 PPO 的核心思想。
4. **诊断指标**：mean KL 和 clip fraction 的计算方式。

> 一句话：**PPO = A2C + "比率 × advantage" + "走太远就停"**。读懂 `ppo_update` 里那十几行，你就理解了 RLHF、GRPO 等方法共用的更新骨架。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `reset` / `step` / `features` / `softmax` / `logits` / `value` / `sample` / `init_*` | 函数 | 与第 07 节相同：网格环境、one-hot 特征、线性 actor 与 critic | 基础设施 |
| `collect_rollout()` | 函数 | 8 个环境各跑最多 50 步，拼成一个 buffer，存下 `log_pi_old` 和 `v_old` | rollout + 旧策略快照 |
| `gae()` | 函数 | 在拼接后的 buffer 上倒序算 GAE | 优势估计（⚠️ 有边界 bug） |
| `normalize()` | 函数 | minibatch 内 advantage 标准化 | advantage normalization |
| `ppo_update()` | 函数 | K epoch × minibatch 的裁剪更新 + critic 回归，返回 KL 和 clip fraction | PPO-Clip 核心 |
| `greedy_policy` / `print_policy` | 函数 | 打印 argmax 策略箭头图 | 可视化 |
| `evaluate()` | 函数 | 用**采样**策略跑若干回合，返回平均**未折扣**回报 | 评估 |
| `main()` | 函数 | 60 轮"采样 → GAE → 更新"，每 10 轮打印指标 | 训练主循环 |

数据流：`main` 每轮调用 `collect_rollout` → `gae` → `ppo_update(theta, w, ...)`（原地修改 `theta`、`w`）→ 每 10 轮 `evaluate`。

---

## 3. 逐段精讲

### 3.1 rollout：给旧策略拍快照

```python
def collect_rollout(theta, w, rng, horizon=50, n_envs=8):
    buffer = []
    for _ in range(n_envs):
        s = reset()
        for _ in range(horizon):
            x = features(s)
            probs = softmax(logits(theta, x))
            a = sample(probs, rng)
            s_next, r, done = step(s, a)
            buffer.append({
                "x": x,
                "a": a,
                "r": r,
                "done": done,
                "v_old": value(w, x),
                "log_pi_old": math.log(max(probs[a], 1e-12)),
            })
            if done:
                break
            s = s_next
    return buffer
```

- 和第 07 节相比，关键变化是存 `log_pi_old`（**对数**概率）而不是整个 `probs`。PPO 只需要"被采样动作"在旧策略下的对数概率，用于后面 `exp(logp - log_pi_old)`。讲义 Step 1："The snapshot is taken once, at rollout time. It does not change during the update epochs."
- `max(probs[a], 1e-12)` 防止 `log(0)` 得到 `-inf`。
- `v_old` 是采样时 critic 的估计，GAE 只用它，保证 K 个 epoch 里 advantage 是固定常数。
- "8 个环境"在这里是**串行**模拟的：同一个函数里循环 8 次、每次从 (0,0) 开始一个新回合，最多 50 步。真实的向量化环境会并行步进并在回合结束时自动 reset。
- 所有轨迹被**首尾相接**放进一个扁平列表 `buffer`，这为下一节的 bug 埋下了伏笔。

### 3.2 GAE：在拼接的 buffer 上倒序递推（⚠️ 边界 bug）

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

公式和第 07 节一样：`δ_t = r + γV(s') - V(s)`，`A_t = δ_t + γλ·A_{t+1}`，`returns = A + V` 作为 critic 目标。但这里 buffer 中有**多条轨迹**，于是出现两个问题：

- ⚠️ **跨回合泄漏**：某环境在 t 步 `done=True` 时，`next_v` 被正确置 0，但 `gae_val` 没有清零——它里面装的是 buffer 中**下一个环境第一步**的 advantage，会以 `γλ≈0.94` 的权重加到本回合终止步上，再一路传播到本回合所有步。正确写法是 `gae_val = delta + gamma * lam * (1 - done) * gae_val`。
- ⚠️ **截断处引用错误状态**：环境被 `horizon=50` 截断时 `done=False`，此时 `buffer[t + 1]` 是**下一个环境的起点 (0,0)**，用它的价值做 bootstrap 毫无道理；如果是 buffer 的最后一条，又会把截断当成终止（`next_v=0`）。

用一个手工 buffer（critic 完全准确，真实 advantage 应全为 0）实测，这个函数输出 `[3.0, 3.0, 3.0, 3.0]`，修复后输出 `[0, 0, 0, 0]`。在这个 4×4 小网格上，用 5 个随机种子对比修复前后，最终回报都在 -6.1~-6.2 左右，影响不明显（回合很短，大部分轨迹以 `done` 结束，critic 很快变准，标准化又吸收了一部分偏移）；但在长回合任务里这是会严重拖累训练的经典 bug。修复代码见测验 Q10。

### 3.3 `ppo_update` 第一部分：冻结目标、准备统计量

```python
def ppo_update(theta, w, buffer, advantages, returns, lr_a=0.05, lr_v=0.1, eps=0.2, epochs=4, batch=32, rng=None):
    rng = rng or random.Random(0)
    for rec, adv, ret in zip(buffer, advantages, returns):
        rec["adv"] = adv
        rec["ret"] = ret

    kl_total = 0.0
    kl_count = 0
    clip_hits = 0
    total = 0
```

- 把 advantage 和 return 直接写进每条记录的字典里，之后 shuffle 时它们跟着样本走，不会错位。这对应讲义训练循环的第 2、3 步："freeze them as constants"、"Freeze `π_θ_old`"。
- 默认超参：`eps=0.2`（讲义的事实标准）、`epochs=4`、`batch=32`。讲义说的标准组合是 K=10、minibatch 64；这里 buffer 只有约 50~400 条，所以用更小的值。
- 注意 `buffer` 里的字典被**原地修改**（加了 `adv`、`ret` 两个键）——函数有副作用，调用方的 buffer 也变了。

### 3.4 `ppo_update` 第二部分：K epoch × minibatch

```python
    for _ in range(epochs):
        shuffled = buffer[:]
        rng.shuffle(shuffled)
        for i in range(0, len(shuffled), batch):
            mb = shuffled[i : i + batch]
            adv_norm = normalize([rec["adv"] for rec in mb])
```

- `buffer[:]` 浅拷贝列表（字典本身共享），再 `shuffle`：每个 epoch 用不同的顺序和不同的 minibatch 划分，打破时间相关性。
- `range(0, len, batch)` + 切片：标准的 minibatch 切分写法，最后一块可能不满 32。
- **advantage 标准化在 minibatch 内做**（CleanRL 也是这种做法）。讲义 Pitfalls："Forgetting advantage normalization ... wrecks PPO on most benchmarks."

### 3.5 `ppo_update` 第三部分：比率、裁剪、梯度

```python
            for rec, adv in zip(mb, adv_norm):
                x = rec["x"]
                probs = softmax(logits(theta, x))
                logp = math.log(max(probs[rec["a"]], 1e-12))
                ratio = math.exp(logp - rec["log_pi_old"])

                clipped = (adv > 0 and ratio > 1 + eps) or (adv < 0 and ratio < 1 - eps)
                if clipped:
                    clip_hits += 1
                total += 1
                kl_total += rec["log_pi_old"] - logp
                kl_count += 1

                if not clipped:
                    pg_scale = ratio * adv
                else:
                    pg_scale = 0.0

                for action in range(N_ACTIONS):
                    grad_logpi = (1.0 if action == rec["a"] else 0.0) - probs[action]
                    for j in range(N_FEAT):
                        theta[action][j] += lr_a * pg_scale * grad_logpi * x[j]
```

这是全文件最重要的十几行：

- **用当前 θ 重新前向**：`probs` 是用**此刻**的 `theta` 算的，不是 rollout 时的旧概率——这样比率才能反映"新策略偏离了多少"。
- **比率在 log 空间计算**：`exp(logp - log_pi_old)`，讲义 Pitfalls 明确要求，避免概率很小时相除不稳定。
- **`clipped` 的判断**正是 `min(r·A, clip(r)·A)` 取到裁剪项的条件：
  - A>0 且 r>1+ε：好动作已经被推高够多 → 停；
  - A<0 且 r<1-ε：坏动作已经被压低够多 → 停；
  - 其他情况（包括 A>0 但 r<1、A<0 但 r>1 这种"走反了"的情况）都不裁剪，梯度继续纠正。
- **`pg_scale = ratio * adv`**：`∇(r·A) = A·r·∇log π`。r 就是重要性权重。第一个 minibatch 时 r≈1，退化为 A2C。
- **梯度上升**：`theta += lr * pg_scale * grad_logpi * x`，与讲义 Step 3 的写法一致。
- ⚠️ 判断用的是严格不等号 `>`、`<`，讲义示例用的是 `>=`、`<=`；在边界点 r 恰好等于 1±ε 时两者差别可以忽略（连续值几乎不会正好相等）。
- ⚠️ 与讲义的完整损失相比，这里**省略了熵奖励**（讲义 Step 4 要求加上），也没有 `c_v` 系数（critic 用独立的学习率）。

### 3.6 `ppo_update` 第四部分：critic 回归与诊断返回

```python
                err = rec["ret"] - value(w, x)
                for j in range(N_FEAT):
                    w[j] += lr_v * err * x[j]

    mean_kl = kl_total / max(1, kl_count)
    clip_frac = clip_hits / max(1, total)
    return mean_kl, clip_frac
```

- critic 同样做 K 个 epoch：目标 `ret` 固定，`value(w, x)` 用当前 `w`，即 LMS 回归。很多 PPO 实现还会对 value loss 做裁剪（value clipping），这里没有实现。
- **mean KL**：`log π_old - log π_θ` 的样本平均，是 KL(π_old‖π_θ) 的单样本估计（k1）。它在期望上非负，但有限样本下可以为负——这就是输出中出现 `mean_KL=-0.0046` 的原因。另外它是在**更新过程中**逐样本累加、跨所有 epoch 平均的，口径偏"过程平均"。
- **clip fraction**：只统计"梯度被置零"的样本。讲义定义是"比率落在 [1-ε, 1+ε] 之外的比例"，范围更大，所以代码的值偏小。
- `max(1, kl_count)` 防止空 buffer 时除以 0。

### 3.7 评估与主循环

```python
def evaluate(theta, rng, episodes=50):
    total = 0.0
    for _ in range(episodes):
        s = reset()
        ep_total = 0.0
        for _ in range(50):
            probs = softmax(logits(theta, features(s)))
            a = sample(probs, rng)
            s, r, done = step(s, a)
            ep_total += r
            if done:
                break
        total += ep_total
    return total / episodes
```

- 评估用的是**采样**策略（不是 argmax），并且是**未折扣**的回报，所以和 "optimal = -6.0" 直接可比（这一点比第 07 节的日志口径更严谨）。
- 评估时传入独立的 `random.Random(it)`，不消耗训练用的 `rng`，评估不会影响训练的随机序列。

```python
    for it in range(updates):
        buffer = collect_rollout(theta, w, rng)
        advantages, returns = gae(buffer)
        mean_kl, clip_frac = ppo_update(theta, w, buffer, advantages, returns, rng=rng)
```

- 三行就是讲义的训练循环 1~5 步：采样 → 算 GAE → K epoch 更新 →（下一轮丢弃旧 buffer，重新采样）。`theta` 和 `w` 是列表，在 `ppo_update` 里被**原地修改**，所以不需要返回值。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 存 `log_pi_old` 而非整个分布 | 比率只需被采样动作的对数概率 | 若要算精确 KL 或熵正则则需要存整个分布（离散动作时便宜） |
| `exp(logp - log_old)` | 数值稳定 | 与框架里 `log_prob` 输出天然契合 |
| 记录字典中写入 `adv`/`ret` | shuffle 时不会错位 | 有副作用；生产中用张量 + 索引 |
| K=4、batch=32 | 小 buffer 下的合理值 | 讲义标准值 K=10、batch 64；K 过大易失稳 |
| minibatch 内标准化 advantage | 与 CleanRL 一致，稳定梯度尺度 | 也可以在整个 batch 上标准化 |
| 手写"裁剪即梯度为 0" | 直观展示 `min/clip` 的梯度含义 | 生产中直接写 `-torch.min(r*A, clamp(r)*A).mean()` 交给 autograd |
| 无熵奖励、无 value clip、无 LR 衰减、无梯度裁剪 | 突出核心 | 讲义 Pitfalls 建议 LR 线性衰减到 0；生产都会加这些 |
| 拼接 buffer 上直接跑 GAE | 代码短 | ⚠️ 跨回合泄漏、截断处 bootstrap 错误；应按 done/截断边界切断递推 |
| 串行模拟 8 个环境 | 讲清算法 | 生产用向量化环境并行步进、自动 reset |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组常量与字典 | `ACTIONS = (...)`、`DELTAS = {...}` | 固定配置用不可变元组；映射用字典 |
| 字典字面量作记录 | `buffer.append({"x": x, "a": a, ...})` | 每条 transition 是一个字典 |
| 动态给字典加键 | `rec["adv"] = adv` | 字典可随时增加字段；注意这是原地修改 |
| `zip` 同时遍历三个序列 | `for rec, adv, ret in zip(buffer, advantages, returns)` | 按位置配对，长度不一时以最短为准 |
| 切片浅拷贝 | `shuffled = buffer[:]` | 复制列表本身，元素（字典）仍共享 |
| `random.Random.shuffle` | `rng.shuffle(shuffled)` | 原地打乱，返回 `None` |
| 带步长的 `range` | `range(0, len(shuffled), batch)` | 0, 32, 64…，用于切 minibatch |
| 列表推导式 | `[rec["adv"] for rec in mb]` | 从记录中抽一列 |
| 布尔表达式组合 | `(adv > 0 and ratio > 1 + eps) or (adv < 0 and ratio < 1 - eps)` | `and` 优先级高于 `or`，括号让意图更清楚 |
| 条件表达式 | `0.0 if buffer[t]["done"] else (...)` | 一行 if/else |
| `math.log` / `math.exp` | `math.exp(logp - rec["log_pi_old"])` | 对数/指数，比率在 log 空间计算 |
| `max(1, n)` 防零除 | `kl_total / max(1, kl_count)` | 简洁的防御写法 |
| 可变对象原地修改 | `theta[action][j] += ...` | 列表作为参数传入，函数内修改对调用方可见 |
| f-string 格式符 | `f"{it+1:3d}"`、`f"{mean_kl:+.4f}"`、`f"{clip_frac:.3f}"` | `3d` 宽度 3 的整数；`+` 强制显示正负号 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才训练 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13，约 0.3 秒）输出：

```text
=== PPO on 4x4 GridWorld (60 updates, 8 envs x 50 steps, eps=0.2, K=4) ===

  update  10  mean_return=-12.00  mean_KL=+0.0159  clip_frac=0.112
  update  20  mean_return= -7.42  mean_KL=-0.0046  clip_frac=0.136
  update  30  mean_return= -6.40  mean_KL=+0.0046  clip_frac=0.010
  update  40  mean_return= -6.76  mean_KL=-0.0052  clip_frac=0.010
  update  50  mean_return= -6.28  mean_KL=+0.0060  clip_frac=0.032
  update  60  mean_return= -6.26  mean_KL=+0.0083  clip_frac=0.024

  greedy policy
   v v > v
   > v v v
   v > v v
   > > > .

final evaluated return (200 episodes) = -6.14  (optimal = -6.0)
```

逐行解读：

- **mean_return**：第 10 轮 -12，第 30 轮已到 -6.4，之后在 -6.3 附近波动。实测每轮 buffer 从早期的 200~380 条缩到后期的约 50 条（8 个环境 × 每回合约 6 步），60 轮总共只用了约 4900 步环境交互；每批数据被用了 4 次，这就是 PPO 的样本效率来源。
- **mean_KL**：始终在 ±0.02 以内，符合讲义"Should stay in [0, 0.02]"的健康范围。出现负值是因为 k1 估计量的样本噪声（见 3.6），不代表出错。
- **clip_frac**：训练早期 0.11~0.14（策略变化快，裁剪经常触发，符合讲义 0.1~0.3 的推荐区间）；后期降到 0.01~0.03，因为策略基本收敛、advantage 小，比率很少越界。按讲义"If ~0, the clip never triggers → raise LR or K_EPOCHS"的规则，后期可以考虑加大步长——但这里任务已经解决，不必再调。
- **greedy policy**：所有格子都指向"向右或向下"，都是最短路径动作；从 (0,0) 出发 `v v` 然后 `> v ...`，6 步到达终点。和第 07 节的箭头图不同，但同样最优——这个网格的最优策略不唯一。
- **final -6.14**：未折扣回报，最优 -6.0；差的 0.14 来自评估时按概率采样（策略仍保留少量随机性）。

---

## 7. 动手改一改

1. **K 扫描**（讲义练习 Medium）：把 `ppo_update` 的 `epochs` 依次设为 1、4、10、30，记录 mean_KL 和回报，找出 KL 开始失控的 K。`epochs=1` 时基本就是 A2C。
2. **修复 GAE 边界**：按测验 Q10 在 rollout 里加 `last`/`v_next` 字段，修改 `gae`，用手工 buffer 验证输出为 0。
3. **标准 clip fraction**：额外统计 `abs(ratio - 1) > eps` 的比例，和代码里的 `clip_frac` 并排打印，观察差别。
4. **加熵奖励和 explained variance**：参考测验 Q11 实现，打印每轮的平均熵和 EV。
5. **KL early stopping**：在每个 epoch 结束时如果 `mean_kl > 0.015` 就 `break`，比较在 `epochs=30` 时是否还能稳定训练。
6. **自适应 KL 惩罚**（讲义练习 Hard）：去掉裁剪，改为 `pg_scale = ratio * adv` 并减去 `β·∇KL`，每轮根据 KL 与目标值的比较把 β 加倍或减半。

---

## 8. 常见坑

- **`log_pi_old` 在更新中被覆盖**：快照必须在 rollout 时拍下并保持不变；如果每个 epoch 重新计算"旧概率"，比率恒为 1，裁剪永远不触发，PPO 退化为多次 A2C 更新（有偏）。
- **梯度符号写反**：讲义："A flipped sign is the most common PPO bug." 手写梯度时是 `+=`（上升）；用 autograd 时 loss 是 `-L^CLIP`。
- **拼接 buffer 后 GAE 不切断**：done 处要乘 `(1 - done)`，截断处要用本轨迹自己的 `V(s_{T})` bootstrap。
- **把裁剪理解成对称夹紧**：裁剪只在"有利方向"截断梯度；`A>0, r<1-ε` 或 `A<0, r>1+ε` 都**不**裁剪。
- **KL 为负就以为算错**：单样本 KL 估计可以为负，看趋势和量级即可；需要非负估计可用 `(r - 1) - log r`。
- **字典原地修改的副作用**：`ppo_update` 会给 buffer 里每条记录加键；如果在别处复用同一个 buffer，要意识到它已被改动。
