# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 03 节 直接偏好优化方法家族 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数，约 0.1 秒） ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

这份代码把 DPO 家族的 6 个损失放在同一个极小的环境里"并排阅读"：

1. **同一套数据**：4 个动作、真实效用 `TRUE_UTILITY = [0.2, 1.0, −0.4, −0.8]`，按 Bradley-Terry 模型采样 500 个偏好对；另外为 KTO 采样 500 条"好/坏"单标签。
2. **同一个策略参数化**：4 维 logits 的 softmax 策略，参考策略 logits 为 `[0.1, 0.2, −0.1, −0.2]`。
3. **6 种手写梯度**：DPO、IPO、BPO 共用 `train_dpo`（用 `variant` 区分），SimPO、KTO、ORPO 各有一个训练函数，全部用单样本 SGD。
4. **观察结果**：打印训练后的动作概率、"win_rate"（实际是最优动作的概率）和 logits。

对应讲义的核心概念：隐式奖励 `β·log(π/π_ref)`、DPO 的 log-sigmoid、IPO 的有界平方目标、KTO 的非成对效用与 loss aversion、SimPO 的无参考 + 长度归一化 + margin、ORPO 的 NLL + odds-ratio、BPO 的 chosen 保护项。

> 一句话：**把 6 个偏好损失的公式落到 4 行 softmax 梯度上，看清它们的结构差异**。但它的数值结果受学习率、步数和 SGD 噪声的影响远大于方法本身——读输出时必须带着这一点（见第 6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `N_ACTIONS`、`TRUE_UTILITY` | 常量 | 4 个动作及其真实效用 | 真实偏好来源 |
| `softmax` / `logsoftmax` / `sigmoid` | 函数 | 数值稳定的基础运算 | — |
| `sample_pref_pair` | 函数 | 随机取两个动作，按 `σ(u_i − u_j)` 决定谁胜 | Bradley-Terry 偏好 |
| `Policy` | dataclass | 保存 logits；`logprob`、`grad_logprob` | 策略 π 与 `∇log π` |
| `apply_grad` | 函数 | `logits -= lr * grad` | 梯度下降 |
| `make_policy_and_ref` | 函数 | 返回两个 logits 相同的独立策略 | π 初始化为 π_ref |
| `train_dpo(variant=...)` | 函数 | DPO / IPO / BPO 三种损失 | 有参考模型的成对方法 |
| `train_simpo` | 函数 | 无参考、长度归一化 + margin | SimPO |
| `train_kto` | 函数 | 单标签 + loss aversion | KTO |
| `train_orpo` | 函数 | NLL + odds-ratio（简化梯度） | ORPO |
| `win_rate` | 函数 | 返回策略在真实最优动作上的概率 | 评估（名字有误导） |
| `report` / `main` | 函数 | 打印并串联全部实验 | — |

数据流：`random.seed(1)` → 采 500 个偏好对 + 500 个 KTO 标签 → 打印 REF → 依次训练 DPO、IPO、BPO、SimPO、KTO、ORPO（每个都从参考策略出发、2000 步）→ 打印概率与 logits → 打印 TAKEAWAY。

---

## 3. 逐段精讲

### 3.1 数值稳定的基础函数

```python
def logsoftmax(logits: list[float]) -> list[float]:
    m = max(logits)
    z = math.log(sum(math.exp(x - m) for x in logits)) + m
    return [x - z for x in logits]


def sigmoid(x: float) -> float:
    if x > 30:
        return 1.0
    if x < -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))
```

- `logsoftmax` 用 log-sum-exp 技巧：先减最大值再求和，避免 `exp` 溢出，`z` 就是 `log Σ exp(x)`。
- `sigmoid` 在 |x| > 30 时直接截断成 0/1，避免 `math.exp(-x)` 在 x 很负时溢出（`math.exp(1000)` 会抛 `OverflowError`）。代价是 `log(sigmoid(x))` 在截断区会出现 `log 0`——本代码只用 sigmoid 算梯度系数，没有直接取 log，所以不会出问题。

### 3.2 Bradley-Terry 采样偏好对

```python
def sample_pref_pair() -> tuple[int, int, float]:
    i, j = random.sample(range(N_ACTIONS), 2)
    p_i_beats_j = sigmoid(TRUE_UTILITY[i] - TRUE_UTILITY[j])
    if random.random() < p_i_beats_j:
        return i, j, p_i_beats_j
    return j, i, 1 - p_i_beats_j
```

- `random.sample(range(4), 2)` 不放回地取两个不同动作。
- `σ(u_i − u_j)` 就是 Bradley-Terry 的胜率。例如 action 1 对 action 3：`σ(1.8) ≈ 0.858`，所以有约 14% 的概率出现"差的赢了"的**噪声对**。
- 返回值第三项是"这一对实际胜者的胜率"，即**偏好强度**。本次 500 对的平均强度只有 0.611（实测），最小 0.142——说明不少样本是反向的。讲义说"真实偏好强度随样本对变化"，就是指这一点。
- 注意：各训练函数都把 `strength` 读出来后**没有使用**，IPO 也没有用它（IPO 是通过"同一对正反出现的频率"隐式体现强度的）。

### 3.3 策略与 `∇log π`

```python
@dataclass
class Policy:
    logits: list[float]

    def logprob(self, a: int) -> float:
        return logsoftmax(self.logits)[a]

    def grad_logprob(self, a: int) -> list[float]:
        probs = softmax(self.logits)
        return [(1.0 if b == a else 0.0) - probs[b] for b in range(N_ACTIONS)]
```

- softmax 策略的对数概率梯度：`∂ log π(a)/∂ logit_b = 1[a=b] − π(b)`。这是本文件所有损失共用的"积木"，记作 `gw`（chosen）和 `gl`（rejected）。
- 一个重要性质：这 4 个分量之和恒为 0。所以提高某个动作的 log-prob，必然把其它动作的概率挤下去——在"只有 4 个动作"的世界里，chosen 的 log-prob 下降很容易发生（见 3.4 的 Degraded Chosen 讨论）。

```python
def apply_grad(p: Policy, grad: list[float], lr: float) -> None:
    p.logits = [l - lr * g for l, g in zip(p.logits, grad)]
```

- 约定：`grad` 是**损失**对 logits 的梯度，做梯度**下降**。读后面每个分支时都要记住这个符号约定。

### 3.4 `train_dpo`：DPO、IPO、BPO 三合一

```python
        margin = beta * ((log_pi_w - log_ref_w) - (log_pi_l - log_ref_l))
        gw = pi.grad_logprob(w)
        gl = pi.grad_logprob(l)
        if variant == "dpo":
            # L = -log sigmoid(margin). dL/dmargin = -(1 - sigmoid(margin)).
            g_margin = -(1.0 - sigmoid(margin))
            grad = [beta * (g_margin * gw_i - g_margin * gl_i)
                    for gw_i, gl_i in zip(gw, gl)]
```

**DPO**：

- `margin` 就是隐式奖励之差 `β·(h_w − h_l)`，`h = log π − log π_ref`。
- 链式法则：`∂L/∂margin = −(1 − σ(margin))`，`∂margin/∂logits = β·(gw − gl)`。代码与公式一致，是**精确梯度**。
- `1 − σ(margin)` 是样本权重：margin 越负（排错），权重越接近 1；margin 很大时权重趋近 0，"学够了就不学"。
- 梯度里有 β 因子：β = 0.1 时每步的有效步长只有 `lr × β = 0.005`，这是本代码 DPO 在 2000 步内远未收敛的主要原因（见第 6 节）。

```python
        elif variant == "ipo":
            target = 1.0 / (2 * beta)
            diff = (log_pi_w - log_ref_w) - (log_pi_l - log_ref_l) - target
            g_margin = 2 * diff
            grad = [g_margin * (gw_i - gl_i) for gw_i, gl_i in zip(gw, gl)]
```

**IPO**：

- 损失 `(h_w − h_l − 1/(2β))²`，导数 `2·diff·(gw − gl)`，同样是精确梯度。
- β = 0.1 时目标为 **5**（nats），而初始 `diff = −5`，单步就能让 logits 移动约 `0.05 × 2 × 5 × |gw − gl|`，最大约 0.5。梯度里**没有 β 因子**，所以 IPO 的有效步长比 DPO 大两个数量级。
- 对同一对 `(i, j)`，如果 i 胜 `n_ij` 次、j 胜 `n_ji` 次，平方损失的最优点是 `h_i − h_j = 5·(n_ij − n_ji)/(n_ij + n_ji)`，即与经验偏好强度 `2p − 1` 成正比，而且**有界**（不超过 5）——这正是讲义说的 "Preference strength and implicit-reward gap are proportional. No blow-up."
- 但"有界"是针对**最优点**说的；单样本 SGD 在最优点附近抖动很厉害（测验 Q10：实测 action 1 概率在 0.048～0.989 之间跳）。

```python
        elif variant == "bpo":
            # DPO + penalty on decreases of log_pi_w
            g_margin = -(1.0 - sigmoid(margin))
            anchor_pen = -1.0 * (log_pi_w - log_ref_w)  # push chosen toward/above ref
            grad = [beta * (g_margin * gw_i - g_margin * gl_i) - 0.05 * anchor_pen * gw_i
                    for gw_i, gl_i in zip(gw, gl)]
```

**BPO**：

- 前半部分与 DPO 完全相同。
- 额外项 `−0.05 · anchor_pen · gw = 0.05 · Δ_w · gw`，是损失 `0.025 · Δ_w²` 的梯度，其中 `Δ_w = log π(y_w) − log π_ref(y_w)`。
- ⚠️ 这是一个**双向**的 L2 锚：Δ_w < 0 时把 chosen 往上拉（符合讲义"惩罚下降"），Δ_w > 0 时**也会**把 chosen 往下拉（讲义没有这个意思）。注释 "penalty on decreases" 与实现不符。只惩罚下降的写法是把 `anchor_pen` 换成 `min(0, Δ_w)` 对应的项（测验 Q9 给出了代码和实测对比）。
- 系数 0.05 是硬编码的，没有随 β 缩放，也没有来自论文。讲义没有给出 BPO 的精确公式，这里只能算"一种 chosen 保护项"的示意。

### 3.5 `train_simpo`：无参考 + 长度归一化 + margin

```python
    pi, _ = make_policy_and_ref()
    lens = [1, 1, 1, 1]  # trivial in single-action toy; illustrative
    for _ in range(steps):
        w, l, _ = random.choice(pairs)
        log_pi_w = pi.logprob(w) / lens[w]
        log_pi_l = pi.logprob(l) / lens[l]
        margin = beta * (log_pi_w - log_pi_l) - gamma
        ...
        g_margin = -(1.0 - sigmoid(margin))
        grad = [beta * (g_margin * gw_i / lens[w] - g_margin * gl_i / lens[l])
                for gw_i, gl_i in zip(gw, gl)]
```

- `pi, _ = ...`：参考策略被直接丢弃——SimPO 不需要 `π_ref`（初始 logits 仍然与参考相同）。
- `margin = β·(log π_w/|y_w| − log π_l/|y_l|) − γ`，β = 1.5、γ = 0.5。梯度推导与 DPO 相同，是精确梯度。
- ⚠️ `lens` 全为 1，长度归一化在这里是**空操作**。代码注释也承认 "trivial in single-action toy"。讲义练习 3（rejected 比 chosen 长 2 倍）在这个玩具上无法真正完成，需要把回复改成 token 序列（测验 Q12）。
- margin `γ` 的作用：要求 chosen 的（归一化）log-prob 至少比 rejected 高 `γ/β`，才会让权重 `1 − σ(margin)` 变小。

### 3.6 `train_kto`：单标签 + loss aversion

```python
        value = beta * (log_pi_y - log_ref_y) - z_ref
        if desirable:
            v = sigmoid(value)  # want up
            g_value = -(1 - v)
        else:
            v = sigmoid(-value)
            g_value = (1 - v) * 2.0  # loss aversion weight
        gy = pi.grad_logprob(y)
        grad = [beta * g_value * gy_i for gy_i in gy]
```

- 输入是 `(动作, 是否 desirable)` 的单条标签，不需要成对数据。`main` 里一个动作被标为 desirable 的概率是 `σ(u_a)`（基于**绝对**效用）。
- desirable：`g_value = −(1 − σ(value))`，对应损失 `−log σ(value)`，梯度下降会提高该动作的 log-ratio。
- undesirable：`g_value = 2·σ(value)`，对应损失 `−2·log σ(−value)`，压低该动作；系数 2.0 就是 loss aversion（坏样本权重更大）。
- ⚠️ 两处简化：
  1. KTO 论文的损失是 `λ·(1 − σ(·))` 形式（直接用价值函数），这里用的是 `−log σ(·)` 的梯度，形式更像"单边 DPO"；
  2. `z_ref` 固定为 0；KTO 论文里它是策略与参考模型之间 KL 的估计值，作为参考点。
- 讲义公式 `v = σ(β·log(π/π_ref) − z_ref)` 与 `value` 的定义一致。

### 3.7 `train_orpo`：NLL + odds-ratio

```python
        # NLL term
        gw = pi.grad_logprob(w)
        # odds ratio term (simplified)
        odds_w = math.exp(log_pi_w) / (1 - math.exp(log_pi_w) + 1e-6)
        odds_l = math.exp(log_pi_l) / (1 - math.exp(log_pi_l) + 1e-6)
        log_ratio = math.log(odds_w + 1e-6) - math.log(odds_l + 1e-6)
        g_or = -(1 - sigmoid(log_ratio))
        gl = pi.grad_logprob(l)
        grad = [-gw_i + lam * g_or * (gw_i - gl_i)
                for gw_i, gl_i in zip(gw, gl)]
```

- `-gw_i`：NLL 项 `−log π(y_w)` 的梯度，下降方向就是提高 chosen 的概率——这是 SFT 项，也是 ORPO 的"正则项"。
- `odds(p) = p/(1−p)`；`+1e-6` 防止 `p → 1` 时除零、`odds → 0` 时 `log 0`。
- ⚠️ 梯度简化：`log odds(y)` 对 logits 的精确梯度是 `gy/(1 − p_y)`，代码用了 `gy`，漏掉 `1/(1−p)`。λ = 0.1 时 NLL 主导，实测影响可以忽略（精确版 `[0.297, 0.370, 0.208, 0.125]` 与简化版 `[0.297, 0.370, 0.209, 0.125]`），但 `p_w → 1` 或 λ 较大时差别会变大。
- 由于 NLL 主导，ORPO 的不动点接近"y_w 的经验分布"（本数据为 `[0.252, 0.396, 0.208, 0.144]`），而不是"最优动作"。

### 3.8 评估与主流程

```python
def win_rate(pi: Policy) -> float:
    probs = softmax(pi.logits)
    true_probs = softmax(TRUE_UTILITY)
    ranked = sorted(range(N_ACTIONS), key=lambda a: -true_probs[a])
    best = ranked[0]
    return probs[best]
```

- 先按真实效用排序找到最优动作（action 1），返回策略在它上面的概率。⚠️ 这不是"胜率"：讲义"Use It"说会画出 win rate、chosen-log-prob drift 和 implicit-reward spread，代码没有画图，也没有计算后两项。
- `sorted(..., key=lambda a: -true_probs[a])` 是降序排序的常见写法。

```python
    pairs = [sample_pref_pair() for _ in range(500)]
    labels = []
    for _ in range(500):
        a = random.randrange(N_ACTIONS)
        desirable = random.random() < sigmoid(TRUE_UTILITY[a])
        labels.append((a, desirable))
```

- 所有方法共用一个全局随机数生成器：训练顺序改变，后面每个方法的结果都会变。要可复现地单独比较某个方法，应在每次训练前重新设定种子或使用独立的 `random.Random(seed)` 实例。
- 打印的 `true optimum = softmax(TRUE_UTILITY)` 只是"β = 1、参考策略均匀"时的最优解，**不是任何一个方法在本设置下的目标**。例如 DPO（β = 0.1）的总体最优是 `π_ref·exp(u/0.1)` 归一化后的 `[0.0003, 0.9997, 0, 0]`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 4 动作 softmax 策略代替语言模型 | 损失公式与梯度一眼可见，0.1 秒跑完 | 没有序列、没有长度、没有 token 共享，长度偏置与 Degraded Chosen 的真实机制无法体现；生产用 TRL 等库在 LLM 上算序列 log-prob |
| 手写梯度 | 让读者看到每个损失的链式法则 | ORPO、KTO 做了简化，BPO 的锚是双向的；生产用 autograd |
| 单样本 SGD、固定 2000 步、统一 lr | 代码最短 | 各方法有效步长差两个数量级（IPO 无 β 因子），结果主要反映步长而非方法；应分别调参、多种子、跑到收敛或在相同 KL 下比较 |
| BT 噪声偏好对 | 模拟"偏好强度不一" | `strength` 被读出但未使用 |
| `win_rate = P(最优动作)` | 一个数就能比较 | 名不副实；应同时报告 chosen/rejected log-prob 漂移、KL、隐式奖励分布 |
| KTO 用 `z_ref = 0`、log-sigmoid 形式 | 简单 | 与 KTO 论文的价值函数和 KL 参考点不同 |
| SimPO `lens = [1,1,1,1]` | 单动作玩具没有长度 | 长度归一化成为空操作 |
| 全局 `random.seed(1)` | 整体可复现 | 方法之间共享 RNG，改动顺序会改变所有结果 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟类型注解求值，旧版本 Python 也能写 `list[float]` |
| 类型注解 | `def softmax(logits: list[float]) -> list[float]` | 标注参数与返回值类型，不影响运行 |
| 元组返回类型 | `-> tuple[int, int, float]`、`-> tuple[Policy, Policy]` | 一次返回多个值 |
| `@dataclass` | `class Policy: logits: list[float]` | 自动生成 `__init__`、`__repr__` 等，适合"装数据的类" |
| 列表推导式 | `[math.exp(x - m) for x in logits]` | 一行生成新列表 |
| 生成器表达式 | `sum(math.exp(x - m) for x in logits)` | 不建中间列表，直接求和 |
| 条件表达式 | `(1.0 if b == a else 0.0)` | 三元运算，写指示函数 |
| `zip` | `zip(gw, gl)`、`zip(p.logits, grad)` | 并行遍历多个列表 |
| 元组解包 | `w, l, strength = random.choice(pairs)`、`pi, _ = make_policy_and_ref()` | `_` 表示丢弃不用的值 |
| 关键字默认参数 | `train_dpo(pairs, beta=0.1, steps=2000, lr=0.05, variant="dpo")` | 调用时可只改需要的参数 |
| `raise ValueError(variant)` | `else: raise ValueError(variant)` | 非法参数立即报错，避免静默走错分支 |
| `list(...)` 复制 | `Policy(list(ref_logits))` | 两个策略各持一份副本，修改 π 不会影响 π_ref |
| `lambda` + `sorted` | `sorted(range(N), key=lambda a: -true_probs[a])` | 按自定义键排序；取负实现降序 |
| `random` 模块 | `random.sample`、`random.choice`、`random.randrange`、`random.random` | 不放回抽样、随机选一个、随机整数、[0,1) 均匀数 |
| f-string 格式符 | `f'{p:.3f}'`、`f'{l:+.2f}'`、`{name:8s}` | 3 位小数；带正负号；左对齐占 8 格 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，固定 `random.seed(1)`，约 0.1 秒）：

```text
  true utility : [0.2, 1.0, -0.4, -0.8]
  true optimum : ['0.241', '0.537', '0.132', '0.089']      ← softmax(u)，并非任何方法的目标

  REF       probs=['0.273', '0.302', '0.223', '0.202']  win_rate=0.302  logits=['+0.10', '+0.20', '-0.10', '-0.20']
  DPO       probs=['0.231', '0.636', '0.086', '0.047']  win_rate=0.636  logits=['+0.39', '+1.40', '-0.60', '-1.19']
  IPO       probs=['0.032', '0.943', '0.024', '0.001']  win_rate=0.943  logits=['+0.03', '+3.42', '-0.24', '-3.22']
  BPO       probs=['0.253', '0.507', '0.141', '0.098']  win_rate=0.507  logits=['+0.21', '+0.90', '-0.37', '-0.74']
  SimPO     probs=['0.181', '0.522', '0.173', '0.123']  win_rate=0.522  logits=['-0.16', '+0.90', '-0.20', '-0.54']
  KTO       probs=['0.254', '0.633', '0.060', '0.052']  win_rate=0.633  logits=['+0.53', '+1.44', '-0.91', '-1.05']
  ORPO      probs=['0.247', '0.364', '0.193', '0.196']  win_rate=0.364  logits=['+0.02', '+0.41', '-0.22', '-0.21']
```

逐项解读：

- **REF**：参考 logits `[0.1, 0.2, −0.1, −0.2]`，action 1 只比其它略高。
- **6 个方法都把概率移向 action 1**，TAKEAWAY 的第一句成立。
- **讲义练习 1 要的"chosen log-prob drift"**：代码没打印，我们用相同种子复现了训练过程，对 500 对求 `log π(y_w) − log π_ref(y_w)` 的平均值：

  | 方法 | chosen 平均漂移 | rejected 平均漂移 | 与参考的 KL |
  |------|---------------|-----------------|-----------|
  | DPO | −0.155 | −0.788 | 0.285 |
  | IPO | −1.286 | −2.895 | 0.946 |
  | BPO | −0.012 | −0.368 | 0.109 |
  | SimPO | −0.010 | −0.290 | 0.108 |
  | KTO | −0.191 | −0.842 | 0.302 |
  | ORPO | +0.015 | −0.059 | 0.010 |

  BPO 确实比 DPO 更好地保住了 chosen（−0.012 vs −0.155），与讲义练习 1 的预期一致。但要注意：①这部分来自双向锚（它也限制了 chosen 上升）；②在 4 动作世界里，"chosen"集合包含许多非最优动作（噪声对的胜者），提高 action 1 必然压低它们，所以平均 chosen 漂移为负不全是 DPO 病理。
- **IPO 0.943 最高**：不是因为 IPO 更好，而是因为目标 5 nats 很大、梯度没有 β 因子、SGD 噪声大。全批量求得的 IPO 最优约为 `[0.120, 0.836, 0.032, 0.012]`；换种子 1/2/3 得到 0.786 / 0.521 / 0.804。
- **DPO 0.636 没收敛**：β = 0.1 时总体最优几乎把全部概率放到 action 1（0.9997）；步数加到 20,000 后 DPO 达到 0.999，chosen 漂移 −4.40、rejected −8.06——这正是小 β 下 DPO 远离参考模型、隐式奖励差持续增大的过度优化趋势。反过来，在 2000 步的固定预算下扫 β：β = 0.05 / 0.1 / 0.5 / 1.0 得到 action 1 概率 0.493 / 0.651 / 0.751 / 0.564（种子 11），与"β 越小越激进"的理论不单调——因为 β 同时缩小了梯度步长。
- **ORPO 0.364 最低**：NLL 主导，向"y_w 的经验分布"`[0.252, 0.396, 0.208, 0.144]` 靠拢，与参考模型 KL 只有 0.010。这是"以 SFT 为锚"的设计结果，不代表 ORPO 差。
- **KTO 与 DPO 接近**：两者梯度都带 β 因子；KTO 用的是不同数据（单标签），只能定性比较。

---

## 7. 动手改一改

1. **补全讲义承诺的指标**：给 `report` 增加三列——chosen 平均漂移、rejected 平均漂移、与参考策略的 KL，并把 `win_rate` 改名为 `p_best`。
2. **修正 BPO**：把双向锚改成只惩罚下降（`min(0, Δ_w)`），比较 action 1 概率和 chosen 漂移（参考测验 Q9：0.483 → 0.553）。再把系数 0.05 改成与 β 成比例，观察敏感性。
3. **公平比较**：给每个方法单独做学习率 sweep，跑 5 个种子取平均，并画出"action 1 概率 vs 与参考的 KL"曲线；或者全部改成全批量梯度，消除 SGD 噪声。
4. **讲义练习 2**：把 `sample_pref_pair` 改成"胜者永远是效用高的那个"（所有偏好对强度相同、无噪声），比较 6 种方法。预期：DPO 的 margin 会无限增大（logits 发散），IPO 停在 5 的目标附近。
5. **讲义练习 3（需改造）**：把回复改成 token 序列（例如长度 1–6 的动作串），`log π(y) = Σ log π(y_t)`，让 rejected 平均长 2 倍；比较 DPO 与 SimPO 训练后生成长度的变化。
6. **精确梯度**：修正 ORPO 的 `1/(1−p)` 因子，把 KTO 改成论文的 `λ·(1 − σ)` 形式并用批内 KL 估计 `z_ref`，再与原版对比（λ 增大到 1.0 时差异更明显）。

---

## 8. 常见坑

- **把 `win_rate` 当胜率**：它只是最优动作的概率，不能和论文里的 pairwise win rate（如 AlpacaEval）直接比较。
- **跨方法比较不调学习率**：DPO 梯度有 β 因子、IPO 没有，同一个 lr 下有效步长差约 20 倍以上；"谁更靠近最优动作"主要由步长决定。
- **只看单次 SGD 的最终迭代**：IPO 的结果在不同种子间从 0.52 到 0.80 不等，结论必须多种子平均。
- **以为 BPO 的锚只防下降**：本代码的实现是对称的 L2，会阻止 chosen 上升。
- **以为 `true optimum` 是训练目标**：它只是 `softmax(u)`；DPO 在 β = 0.1 时的目标是 `π_ref·exp(u/β)`，比它尖锐得多。
- **忘了 `log Z(x)` 只在同一个 x 内相消**：DPO 要求 chosen 与 rejected 来自**同一个 prompt**；把不同 prompt 的回复随意配对会破坏推导。
- **全局随机数共享**：在 `main` 里调换训练顺序，所有方法的数字都会变，不要把这种变化误认为方法差异。
- **ORPO/SimPO 没有参考模型 ≠ 没有正则**：ORPO 的 NLL 项、SimPO 的长度归一化和 margin 就是正则（`outputs/skill-preference-loss-selector.md` 把"无需正则"列为 hard reject）。
