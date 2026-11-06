# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 01 节 将指令遵循作为 Alignment 信号 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`），无需 PyTorch、无需 GPU

---

## 1. 这份代码在考察什么

这份约 210 行的代码把 InstructGPT 的三阶段 RLHF 流水线压缩到一个**三臂 bandit**（只有动作 A、B、C，没有序列）上：

1. **Stage 1 SFT**：标注员按 `softmax(utility)` 示范动作，SFT 用计数频率做最大似然估计。
2. **Stage 2 RM**：标注员对随机两两组合按 Bradley-Terry 概率给出偏好，用 SGD 拟合每个动作一个标量奖励。
3. **Stage 3 "PPO"**：在 KL 成形奖励 `r(a) − β·log(π(a)/π_SFT(a))` 上做策略梯度，跟踪平均奖励与 `KL(π‖π_SFT)`。
4. **对照实验**：β = 0.1、β = 0、以及"RM 有 bug（A 上 +0.5）"三次运行。

它让讲义里的每个公式都对应到几行可以单步调试的代码：softmax 策略、KL、BT 梯度、softmax 策略梯度。但运行结果**并不支持**代码和讲义中"关掉 KL 就出现 reward hacking"的说法——这恰好是理解 reward hacking 本质的好入口：reward hacking 需要"代理与真实目标不一致"，而这里的 RM 与真实效用排序一致。

> 一句话：**用三个数字的 logits 演完 SFT → RM → KL 正则策略优化，并且（在你读懂输出之后）说明"KL 只是限制利用，代理错了才会有 hacking"。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `softmax` / `kl` | 函数 | 数值稳定 softmax；离散 KL 散度 | 策略参数化、KL 惩罚 |
| `Policy` | dataclass | 3 个 logits；`probs`、`sample`、`logprob`、`copy` | 语言模型策略的极简替身 |
| `labeler_true_utility` | 函数 | 真实效用 `[0.0, 1.0, −0.3]`：偏好 B、对 A 中立、略反感 C | "人类偏好"的真值 |
| `stage1_sft` | 函数 | 200 条示范 → 计数频率 → log 频率作为 logits | Stage 1 SFT |
| `stage2_reward_model` | 函数 | 500 对 BT 偏好 → SGD 拟合 3 个标量奖励 → 可选偏置 → 中心化 | Stage 2 RM |
| `stage3_ppo` | 函数 | 300 步 × 32 样本，KL 成形奖励的策略梯度；记录奖励与 KL 轨迹 | Stage 3 RL + KL |
| `report` | 函数 | 打印 SFT/RLHF 分布、RM、最终/最大奖励、最终 KL | 实验报告 |
| `main` | 函数 | 跑 SFT、RM，三次 Stage 3 实验 | 驱动 |

数据流：模块级 `random.seed(0)` → `stage1_sft()` 得到 `sft` → `stage2_reward_model()` 得到 `rm` → `stage3_ppo(sft, rm, β)` ×2 → 重新拟合带偏置的 `rm_buggy` → `stage3_ppo(sft, rm_buggy, 0.1)` → 每次 `report` 打印。

---

## 3. 逐段精讲

### 3.1 工具函数：softmax 与 KL

```python
def softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    z = sum(exps)
    return [e / z for e in exps]


def kl(p: list[float], q: list[float]) -> float:
    return sum(pi * math.log(pi / qi) for pi, qi in zip(p, q) if pi > 0 and qi > 0)
```

- softmax 先减最大值防止 `exp` 溢出，结果不变。
- `kl(p, q) = Σ p·log(p/q)`，单位是 nats（自然对数）。本代码总是以 `kl(π, π_SFT)` 调用，即讲义里的 `KL(π‖π_SFT)`——**反向 KL**（以当前策略为权重），它对"π 把概率放到 π_SFT 很小的地方"惩罚最重。
- `if pi > 0 and qi > 0` 跳过零概率项：`p=0` 时该项本应为 0（正确）；`q=0, p>0` 时 KL 本应为无穷大，这里却被静默跳过——在 softmax 策略下概率永远 > 0，所以不会触发。

### 3.2 `Policy`：三个 logits 就是全部参数

```python
@dataclass
class Policy:
    logits: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])

    def sample(self) -> int:
        r = random.random()
        cum = 0.0
        for i, p in enumerate(self.probs()):
            cum += p
            if r < cum:
                return i
        return len(self.logits) - 1
```

- 真实 LLM 的策略是"给定提示时对 token 序列的分布"；这里退化成"对 3 个动作的分布"，参数就是 3 个 logits。
- `sample` 用**逆 CDF 采样**：在 [0,1) 抽一个数，看它落在累积概率的哪一段。最后的 `return len - 1` 防止浮点累加误差让 `cum` 略小于 1 时漏掉最后一段。
- `copy` 返回新对象并复制列表（`list(self.logits)`），避免 RL 更新时改动 SFT 策略。
- `logprob` 定义了但没有被调用（`stage3_ppo` 里直接写了 `math.log(pi.probs()[a] + 1e-12)`）。

### 3.3 Stage 1：SFT = 计数频率的 MLE

```python
    utility = labeler_true_utility()
    target = softmax(utility)
    # ... 按 target 采样 200 个示范动作 ...
    counts = [0.0, 0.0, 0.0]
    for a in demos:
        counts[a] += 1
    total = sum(counts)
    logits = [math.log(c / total + 1e-6) for c in counts]
    m = sum(logits) / 3
    logits = [x - m for x in logits]
    return Policy(logits=logits)
```

- 标注员的示范分布是 `softmax([0, 1, −0.3]) ≈ [0.224, 0.610, 0.166]`。
- 类别分布的最大似然解就是样本频率，所以 SFT 直接把 `log(频率)` 当作 logits。本次 200 条示范中 A/B/C 各出现 36/126/38 次，SFT 策略为 `[0.180, 0.630, 0.190]`——与真实示范分布有偏差，这是有限示范的采样噪声。
- `+ 1e-6` 防止某个动作 0 次时 `log(0)`；减去均值让 logits 中心化，softmax 结果不变。
- ⚠️ docstring 说"with a single-step gradient move"，但代码是**闭式解**，没有任何梯度步。
- 对应讲义：SFT 让模型学会"标注员会怎么做"，但不知道"多个合理答案里哪个更好"。

### 3.4 Stage 2：Bradley-Terry 奖励模型

```python
    for _ in range(n_pairs):
        i, j = random.sample(range(3), 2)
        p_prefer_i = 1 / (1 + math.exp(-(utility[i] - utility[j])))
        winner = i if random.random() < p_prefer_i else j
        loser = j if winner == i else i
        diff = r[winner] - r[loser]
        s = 1 / (1 + math.exp(-diff))
        r[winner] += lr * (1 - s)
        r[loser] -= lr * (1 - s)
    if bias:
        r = [ri + bi for ri, bi in zip(r, bias)]
    m = sum(r) / 3
    return [x - m for x in r]
```

- **数据生成**：随机选两个不同动作（`random.sample` 无放回），标注员以 `σ(u_i − u_j)` 的概率偏好 i——标注员本身就是一个 BT 模型，带噪声。
- **SGD**：损失 `L = −log σ(r_w − r_l)` 对 `r_w` 的梯度是 `−(1 − σ)`，对 `r_l` 是 `+(1 − σ)`。梯度下降即 `r_w += lr·(1 − s)`、`r_l −= lr·(1 − s)`。已排对（`diff` 大）的样本更新小，排错的更新大。
- **中心化**：BT 只依赖奖励差，加常数不改变任何偏好概率；RL 中加常数也不改变最优策略（在 softmax 策略梯度中常数项的梯度期望为 0）。
- 拟合结果 `[−0.146, +0.716, −0.569]`，与真实效用中心化后的 `[−0.233, +0.767, −0.533]` 接近——**排序完全一致**。
- `bias` 参数在中心化**之前**加入，所以 +0.5 的偏置中心化后只让 A 相对其他两项高出 0.5，并被平均分摊。

### 3.5 Stage 3：KL 成形奖励的策略梯度

```python
    for _ in range(steps):
        advantages = [0.0, 0.0, 0.0]
        counts = [0, 0, 0]
        total_r = 0.0
        for _ in range(batch):
            a = pi.sample()
            r_a = reward[a]
            penalty = beta * (math.log(pi.probs()[a] + 1e-12)
                              - math.log(sft_probs[a] + 1e-12))
            shaped = r_a - penalty
            advantages[a] += shaped
            counts[a] += 1
            total_r += r_a
        for a in range(3):
            if counts[a] > 0:
                advantages[a] /= counts[a]
```

- **KL 成形奖励**：`shaped = r(a) − β·[log π(a) − log π_SFT(a)]`。对它在 π 下取期望，正好是 `E_π[r] − β·KL(π‖π_SFT)`——讲义的 Stage 3 目标。InstructGPT 也是把 KL 以"每 token 奖励惩罚"的形式加进去的。
- 每个动作的"优势"实际是该动作在 batch 中的**平均成形奖励**，没有减去基线；未被采到的动作优势为 0（奖励已中心化，所以 0 近似平均值，偏差不大）。
- `total_r` 只累加**原始 RM 奖励**（不含惩罚），所以报告里的 "Final reward" 是代理奖励，不是真实效用——代码从头到尾都没有衡量真实效用，因此无法直接展示"代理升、真实降"的 Goodhart 现象。

```python
        probs = pi.probs()
        grad = [0.0, 0.0, 0.0]
        for a in range(3):
            for b in range(3):
                indicator = 1.0 if a == b else 0.0
                grad[b] += advantages[a] * probs[a] * (indicator - probs[b])
        pi.logits = [l + lr * g for l, g in zip(pi.logits, grad)]
        reward_traj.append(total_r / batch)
        kl_traj.append(kl(pi.probs(), sft_probs))
```

- 这是 `J = Σ_a π_a·Â_a` 对 logit `b` 的精确梯度：`∂π_a/∂θ_b = π_a(1[a=b] − π_b)`。所以它是"用采样估计每个动作的平均奖励，再算精确期望梯度"，而不是 REINFORCE 的单样本 `∇log π(a)·R` 估计，也不是 PPO（没有比值、没有 clip、没有价值函数）。docstring 的"Toy REINFORCE-with-KL (a stripped-down PPO)"是一种宽松说法。
- 梯度**上升**（`l + lr * g`），学习率 0.1，300 步。
- KL 惩罚里的 `π(a)` 当作常数（没有对它求导），与"KL 作为奖励成形项"的常见实现一致。

**这个更新收敛到哪里？** KL 正则目标的解析最优解是 `π*(a) ∝ π_SFT(a)·exp(r(a)/β)`。我们用 β 扫描验证（300 步、固定种子）：

| β | 代码结果 | 解析解 |
|---|---------|-------|
| 0.5 | [0.043, 0.928, 0.029] | [0.047, 0.931, 0.022] |
| 1.0 | [0.097, 0.835, 0.067] | [0.100, 0.831, 0.069] |
| 2.0 | [0.138, 0.744, 0.118] | [0.138, 0.744, 0.118] |

β 较大时完全吻合；β = 0.1 时解析解约为 `[0.0001, 0.9999, 0]`，300 步远未收敛，所以 β = 0.1 与 β = 0 的结果几乎一样。

### 3.6 `report` 与 `main`

```python
    rlhf, r_traj, kl_traj = stage3_ppo(sft, rm, beta=0.1)
    rlhf2, r2, kl2 = stage3_ppo(sft, rm, beta=0.0)
    rm_buggy = stage2_reward_model(bias=[0.5, 0.0, 0.0])
    rlhf3, r3, kl3 = stage3_ppo(sft, rm_buggy, beta=0.1)
```

- 三次实验共用一个全局随机数流，所以每次运行的样本不同；结果可复现（`random.seed(0)` 在模块顶部），但实验之间**不是**同样随机条件下的对照。
- ⚠️ Run 3 **重新拟合**了一个 RM（随机状态已变，B 的奖励从 +0.716 变为 +0.862），再加偏置；+0.5 加在中心化前，结果 A = −0.105 仍远低于 B = +0.862，策略照样收敛到 B——注释"With KL on, partial exploitation"没有发生。
- ⚠️ 讲义练习 2 说偏置加在 **B** 上，代码加在 **A** 上；讲义练习 1 说"200 PPO steps"，代码默认 300 步。
- `report` 中 `r_traj.index(max(r_traj))` 找最大奖励首次出现的步数；`r_traj` 是每个 batch 的平均，含采样噪声。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 三臂 bandit 代替语言模型 | 所有量都能打印、能手算 | 没有序列、没有 token 级 KL、RM 不会遇到"分布外输入"，所以真正的 reward hacking 机制（RM 在没见过的输出上出错）无法出现 |
| SFT 用闭式 MLE | 一行出结果 | 与真实的梯度下降微调不同；docstring 描述不准确 |
| RM 为每个动作一个标量 | BT 公式一目了然 | 真实 RM 是神经网络，在训练分布外会给出任意分数 |
| 奖励中心化 | BT 与 RL 都对常数不敏感，数值更稳 | 生产中常做奖励归一化/白化 |
| KL 写进奖励（成形） | 与 InstructGPT 实现一致 | 需要选择 β；β 只有相对奖励尺度才有意义 |
| 精确期望梯度，无 clip、无价值函数 | 代码短、方差小 | 不是 PPO；真实 PPO 需要比值裁剪、GAE、多 epoch 小批量 |
| 只记录代理奖励 | 简单 | 看不到 Goodhart 现象；应同时记录真实效用 |
| 全局随机流、Run 3 重新拟合 RM | 写起来方便 | 实验之间混入"换了 RM"的噪声；应复用同一 RM、为每次实验单独设种子 |
| 不实现 PPO-ptx | bandit 没有"预训练能力"可遗忘 | 讲义的 alignment tax 无法在此演示 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值；使 `list[float] \| None` 这类写法在较旧版本也能用作注解 |
| 内置泛型注解 | `def softmax(logits: list[float]) -> list[float]` | Python 3.9+ 可直接写 `list[float]` |
| `X \| None` 联合类型 | `bias: list[float] \| None = None` | 等价于 `Optional[list[float]]` |
| 返回元组的注解 | `-> tuple[Policy, list[float], list[float]]` | 一次返回多个值 |
| 字符串形式的前向引用 | `def copy(self) -> "Policy":` | 在类体内引用自身类型（有了 `__future__` 后引号可省） |
| `@dataclass` + `field(default_factory=lambda: [...])` | `logits: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])` | 可变默认值必须用工厂；`lambda` 返回一个新列表 |
| 列表推导式 | `[math.exp(x - m) for x in logits]` | 逐元素构造新列表 |
| 带条件的生成器表达式 | `sum(pi * math.log(pi / qi) for pi, qi in zip(p, q) if pi > 0 and qi > 0)` | 不建中间列表，直接求和 |
| `zip` | `zip(pi.logits, grad)` | 并行遍历两个序列 |
| `enumerate` | `for i, p in enumerate(self.probs()):` | 同时拿到下标与值 |
| `random.sample` | `random.sample(range(3), 2)` | 无放回抽 2 个不同元素 |
| 条件表达式 | `winner = i if random.random() < p_prefer_i else j` | 三元运算 |
| 关键字参数调用 | `stage3_ppo(sft, rm, beta=0.1)` | 让实参含义一目了然 |
| 嵌套 f-string 与格式符 | `[f'{p:.3f}' for p in sft.probs()]`、`{r_traj[-1]:+.3f}` | `.3f` 三位小数；`+` 总是显示正负号 |
| 负索引 | `r_traj[-1]` | 取最后一个元素 |
| `list.index` | `r_traj.index(max(r_traj))` | 返回第一次出现的位置 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 0.1 秒）：

```text
Stage 1 SFT complete.
  SFT policy: ['0.180', '0.630', '0.190']          ← 200 条示范的频率（36/126/38）

Stage 2 RM complete.
  Reward per action: ['-0.146', '+0.716', '-0.569'] ← 与真实效用排序一致

Run 1: beta = 0.10 (standard InstructGPT)
  RLHF probs    : ['0.017', '0.969', '0.014']
  Final reward  : +0.689
  Final KL      : 0.340 nats
  Max reward    : +0.716 at step 75

Run 2: beta = 0.00 (no KL — reward hacking shows up)
  RLHF probs    : ['0.015', '0.973', '0.012']
  Final reward  : +0.689
  Final KL      : 0.354 nats
  Max reward    : +0.716 at step 49

Run 3: buggy RM (+0.5 on action A), beta = 0.10
  RLHF probs    : ['0.015', '0.974', '0.011']
  Reward model  : ['-0.105', '+0.862', '-0.757']    ← 重新拟合的 RM，A 仍远低于 B
  Final reward  : +0.862
  Final KL      : 0.356 nats
```

逐项解读：

- **SFT**：`[0.180, 0.630, 0.190]` 是样本频率，真实示范分布为 `[0.224, 0.610, 0.166]`。
- **RM**：与真实效用中心化后的 `[−0.233, +0.767, −0.533]` 接近，排序一致。
- **Run 1 vs Run 2**：几乎相同。KL 轨迹在第 10、50、100、300 步分别为 β=0：0.014、0.142、0.239、0.354；β=0.1：0.014、0.132、0.224、0.341。β=0.1 只让 KL 增长略慢一点。两者都把约 97% 的概率放到 B 上——B 正是标注员真正偏好的动作，真实效用从 SFT 的 0.573 升到约 0.97。**这是 mode-seeking，不是 reward hacking**。
- **"Max reward +0.716 at step 75/49"**：单个 batch 全部采到 B 时平均奖励就等于 B 的奖励 0.716，所以"最大值"只是达到上限的时刻，含采样噪声。
- **Run 3**：+0.5 偏置没有翻转排序，加上 RM 被重新拟合，结果与 Run 1 无实质区别。
- **要看到 reward hacking**：我们复用同一个 RM，把 A 的偏置加到 +1.5（RM 变为 `[0.854, 0.216, −1.069]`，A 成为 RM 最爱）：β=0.1 时策略变为 `[0.920, 0.068, 0.012]`，KL 1.317，**真实效用跌到 0.064**（低于 SFT 的 0.573）；β=1.0 时策略为 `[0.331, 0.615, 0.054]`，真实效用 0.598。这才是"代理错了 + 优化压力 → 真实目标受损，KL 限制受损程度"的完整演示。

---

## 7. 动手改一改

1. **（讲义练习 1）** 把 `steps` 改为 200、`beta=0.0`，报告动作分布（我们测得约 `[0.021, 0.961, 0.017]`，KL 0.319），并用一段话解释 mode-seeking：没有 KL 时，最优解就是把全部概率放到奖励最高的动作上。
2. **加入真实效用追踪**：在 `stage3_ppo` 中每步额外记录 `Σ π(a)·utility(a)`，在 `report` 中打印"代理奖励 vs 真实效用"两条轨迹。
3. **（讲义练习 2，修正版）** 复用同一个 `rm`，对 A 依次加 +0.5、+1.0、+1.5 的偏置，扫描 β ∈ {0, 0.1, 0.5, 1, 2}，找出"真实效用低于 SFT"的区域（参考第 6 节的结果）。
4. **验证解析解**：写函数 `optimal(sft_probs, r, beta)` 返回 `π_SFT·exp(r/β)/Z`，与 `stage3_ppo` 跑 1,000 步的结果对比；观察 β 越小需要的步数越多。
5. **（讲义练习 3）** 记录第 1、5、20、100 步的策略，用"真实效用的 BT 胜率"`σ(U(π) − U(π_SFT))` 近似"标注员偏好 RLHF 策略胜过 SFT 的比例"，画出随步数变化的曲线。
6. **进阶（讲义练习 5）**：在同样的 500 对偏好数据上实现 bandit 版 DPO：参数为 3 个 logits，损失 `−log σ(β·[log π(w)/π_SFT(w) − log π(l)/π_SFT(l)])`，比较达到同样代理奖励时 DPO 与本代码的 KL。

---

## 8. 常见坑

- **把 mode-seeking 当成 reward hacking**：策略变尖本身不是问题；只有当代理奖励与真实目标不一致、且优化把策略推向"代理高、真实低"的区域时才是 hacking。一定要同时度量代理与真实指标。
- **脱离奖励尺度谈 β**：β = 0.1 对 ±0.7 的奖励几乎等于没有正则；奖励放大 10 倍，同样的 β 效果完全不同。
- **实验之间共享随机流**：Run 3 重新拟合 RM，比较的已不只是"有没有偏置"。对照实验要固定除被研究变量之外的一切。
- **偏置加在中心化之前**：+0.5 被三等分后，A 相对 B、C 的提升小于直觉。
- **以为这是 PPO**：没有重要性比值、没有 clip、没有价值函数；它是精确期望梯度。阅读 RLHF 论文时要分清"PPO 的稳定化技巧"与"KL 正则目标本身"。
- **KL 方向**：代码用 `KL(π‖π_SFT)`（反向 KL），惩罚 π 在 π_SFT 小概率处放质量；写反方向会得到不同的行为。
- **`kl` 静默跳过 `q = 0`**：若换成可能输出精确 0 概率的策略（如 argmax），KL 会被低估而不是变成无穷大。
