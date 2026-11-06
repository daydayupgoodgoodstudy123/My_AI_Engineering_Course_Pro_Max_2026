# 测验 · 奖励建模 & RLHF（Reward Modeling & RLHF）

> **阶段 09 · 强化学习 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要奖励模型 | "好回答"写不成闭式奖励函数，但人类很容易比较两个回答谁更好——成对偏好便宜、可规模化 |
| 2 | RLHF 三阶段 | SFT（示范数据微调）→ RM（成对偏好训练奖励模型）→ PPO（对 RM 优化 + 对参考模型的 KL 惩罚） |
| 3 | Bradley-Terry 损失 | `L(φ) = -E[log σ(R(x,y₊) - R(x,y₋))]`，奖励差就是偏好的 log-odds |
| 4 | RM 的结构 | 通常从 SFT 模型初始化，同一个 transformer 主干 + 一个输出标量的线性 head |
| 5 | KL 惩罚 | `r_total = R_φ(x,y) - β·KL(π_θ‖π_ref)`，是正则项而非硬信赖域；β 常取 0.01~0.05；讲义称它是"RLHF 最重要的旋钮" |
| 6 | Reward hacking / 过优化 | RM 只在训练分布上可信，策略会找到 RM 打高分但实际很差的输出；症状是 RM 分数持续上升而人类评估持平或下降 |
| 7 | 长度作弊 | RM 常隐式偏好长回答，策略学会注水；对策是长度归一化奖励或长度感知的 RM |
| 8 | 2026 现状 | 对齐调优以 DPO 为主（无 RM、无 PPO）；推理能力用 GRPO + 可验证奖励；PRM 给推理步骤打分；RLAIF/Constitutional AI 用 AI 生成偏好 |
| 9 | 自适应 β | 观测 KL 偏离目标时调整 β，使每步 KL 维持在目标附近；TRL 的 `adap_kl_ctrl` 提供这类机制 |
| 10 | 关键诊断 | 平均 KL(π_θ‖π_ref)、奖励曲线与留出的人类评估对比、clip fraction |

### 核心技能（能动手做到）

- [ ] 推导 Bradley-Terry 损失对奖励差的梯度 `-(1 - σ(Δ))`，并手算线性 RM 的一步更新
- [ ] 写出数值稳定的 `sigmoid`，说明为什么 `x ≤ 0` 时要换一种写法
- [ ] 运行 `main.py`，解读 RM 权重排序和 holdout 准确率，说清为什么这里准确率能到 1.0
- [ ] 指出本节代码中 KL 惩罚"与动作无关、期望梯度为 0"的问题，并改成逐样本的 `log π_θ(y) - log π_ref(y)` 惩罚，验证 β 扫描时 KL 明显受控
- [ ] 写出 KL 正则目标的闭式最优解 `π*(y) ∝ π_ref(y)·exp(R(y)/β)`，并据此解释 DPO 的出发点
- [ ] 能针对"对齐 / 推理 / 安全 / 推理时对齐"不同目标，选出 DPO、GRPO、RLHF-PPO、Best-of-N 中合适的方法

---

## 二、基础自测（选择题）

**Q1.** RLHF 选择收集"成对比较"而不是让标注员直接给回答打 1~10 分，最主要的原因是：

- A. 成对比较的数据量更小
- B. 人类给出绝对分数时尺度不一致、噪声大，而判断"哪个更好"更容易、更一致
- C. 成对比较不需要 SFT 模型
- D. 绝对分数无法用于训练神经网络

**Q2.** Bradley-Terry 模型下，若 `R(x, y_A) - R(x, y_B) = 0`，则模型预测 `P(y_A ≻ y_B)` 为：

- A. 0
- B. 0.5
- C. 1
- D. 取决于 β

**Q3.** RLHF 第三阶段在奖励中加入 `-β·KL(π_θ‖π_ref)` 的最主要目的是：

- A. 加快 PPO 的收敛速度
- B. 让策略停留在 RM 训练分布附近，防止找到"RM 打高分但实际很差"的输出（reward hacking）
- C. 替代 PPO 的裁剪
- D. 让 RM 的准确率更高

**Q4.** 训练中发现 RM 分数一路上升，但留出的人类评估分数先升后降。最可能的情况是：

- A. 学习率太小
- B. 发生了过优化 / reward hacking；应提前停止、提高 β、扩充 RM 训练数据
- C. RM 太准确了
- D. KL 惩罚太大

**Q5.** 关于 DPO 与 RLHF-PPO，下列说法正确的是：

- A. DPO 仍需要单独训练奖励模型，再用 PPO 优化
- B. DPO 用闭式推导把 RM 训练和 PPO 两个阶段合并成一个在偏好数据上的监督式损失，不需要显式 RM 和在线采样
- C. DPO 只适用于可验证奖励的数学题
- D. DPO 的计算量通常比 PPO 大

**Q6.** 关于 GRPO（讲义描述），正确的是：

- A. 用 critic 估计每个 token 的价值
- B. 用组内相对奖励作 baseline 替代 critic，奖励常来自验证器（代码能否运行、数学答案是否匹配），主导推理模型训练
- C. 必须使用人类偏好训练的 RM
- D. 不需要任何采样

**Q7.** Process Reward Model（PRM）与普通（结果）奖励模型的区别是：

- A. PRM 只看最终答案
- B. PRM 对推理的中间步骤/部分解打分，可提供更细粒度的信号
- C. PRM 不能用于 GRPO
- D. PRM 就是 Bradley-Terry 模型的别名

**Q8.** RLHF 中 KL 惩罚系数 β 设得过大，最可能的现象是：

- A. 策略快速偏离参考模型并出现 reward hacking
- B. 策略几乎不变，RM 分数提升很少
- C. RM 准确率下降
- D. 长度作弊加剧

---

## 三、动手 / 代码题

**Q9.**（手算）本节 RM 训练循环如下（`w` 是 `defaultdict(float)`，初始全 0，`lr=0.1`）：

```python
r_pos = score(w, y_pos)
r_neg = score(w, y_neg)
p = sigmoid(r_pos - r_neg)
grad_scale = 1 - p
for t, c in bag(y_pos).items():
    w[t] += lr * grad_scale * c
for t, c in bag(y_neg).items():
    w[t] -= lr * grad_scale * c
```

依次喂入两对数据：
1. `y_pos=("clear", "clear")`, `y_neg=("rude", "vague")`
2. `y_pos=("clear", "kind")`, `y_neg=("rude", "rude")`

写出每一步的 `r_pos`、`r_neg`、`p` 和更新后的 `w`。并解释：为什么系数是 `1 - p`？当 RM 已经非常确信（p→1）时会怎样？

**Q10.**（找 bug）`rlhf_loop` 中每个样本的奖励是：

```python
probs_new = policy_probs(theta, p_idx)
token = sample_token(probs_new, rng)
probs_ref = policy_probs(reference, p_idx)
rm_score = w.get(VOCAB[token], 0.0)
kl_term = kl(probs_new, probs_ref)
reward = rm_score - beta * kl_term
```

运行 `main.py` 得到：

```text
beta=0.01   initial: RM=-0.111 KL=0.000   final: RM=+1.185 KL=2.293
beta=0.1    initial: RM=-0.111 KL=0.000   final: RM=+1.186 KL=2.265
beta=1.0    initial: RM=-0.111 KL=0.000   final: RM=+1.179 KL=1.831
```

β 放大了 100 倍，最终 KL 却只从 2.29 降到 1.83（12 个 token 的最大可能 KL 是 `ln 12 ≈ 2.48`）。(a) 从策略梯度的角度解释为什么这里的 KL 惩罚几乎不起作用；(b) 给出修正写法。

**Q11.**（读代码）本节的 `sigmoid` 写成：

```python
def sigmoid(x):
    if x > 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)
```

为什么不直接写 `1.0 / (1.0 + math.exp(-x))`？请给出一个会让朴素写法出问题的输入，并说明 `log σ(Δ)` 在框架里通常怎么算。

**Q12.**（扩展）KL 正则的 RL 目标 `max_π E_{y~π}[R(y)] - β·KL(π‖π_ref)` 有闭式最优解 `π*(y) = π_ref(y)·exp(R(y)/β) / Z`。请写一个函数 `optimal_policy(rewards, ref_probs, beta)` 返回 π*，并回答：(a) 对本节训练出的 RM（好词权重约 +1.0~+1.2，坏词约 -1.0~-1.2）、均匀参考策略，β 从 0.01 增大到 1.0 时，π* 的 KL 会怎样变化？(b) 这个闭式解和 DPO 有什么关系？

---

## 四、面试高频题

**Q13.**（基础必考）请完整描述 InstructGPT 式的 RLHF 三阶段流程：每个阶段的输入数据、训练目标、产出模型分别是什么？

**Q14.**（原理深挖）推导 Bradley-Terry 奖励模型的损失函数，并说明它的两个性质：(1) 奖励只确定到一个与回答无关的常数偏移；(2) 为什么 RM 输出的绝对数值不能直接跨 prompt 比较。

**Q15.**（原理深挖）什么是 reward hacking？请举出至少三种在 LLM RLHF 中常见的表现形式，并给出系统性的缓解手段。

**Q16.**（场景设计）2026 年，你负责一个 70B 对话模型的后训练，目标包括：日常对话的有用性与无害性、数学/代码推理能力、安全拒答。请设计一条后训练流水线，说明每个目标用什么方法（DPO / GRPO / RLHF-PPO / Best-of-N / Constitutional AI）以及为什么。

**Q17.**（工程实践）RLHF-PPO 训练中你该监控哪些指标？如果观察到 KL(π_θ‖π_ref) 持续上升到 10 以上、回答越来越长，你会怎么处理？

**Q18.**（追问型）面试官追问："奖励模型要比策略模型大吗？" 讲义说 RM 至少要和策略一样大，你怎么看？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Writing that reward function by hand is impossible ... But humans can compare two outputs and mark a preference. That is cheap to collect at scale." 不同标注员对"7 分"的理解差别很大，而相对判断更一致。A 不是主因；C、D 都不成立（绝对分数也能做回归训练，只是噪声大）。

### Q2 — 答案：B

`P(y_A ≻ y_B) = σ(R_A - R_B) = σ(0) = 0.5`。讲义："The difference in reward implies a log-odds of preference." 奖励差为 0 意味着两者等可能被偏好。D 混淆了 RLHF 第三阶段的 KL 系数 β。

### Q3 — 答案：B

讲义："Without it, PPO will happily find reward-hacking strategies — the RM was only trained on in-distribution completions ... The KL keeps π_θ near the manifold where the RM was trained." C 错：PPO 的裁剪约束的是 `π_θ` 与每轮快照 `π_old` 的距离，KL 惩罚约束的是与固定 `π_ref` 的距离，两者并存。

### Q4 — 答案：B

讲义 Pitfalls："Symptoms: reward climbs indefinitely while human eval score plateaus or drops. Fix: stop early, raise β, broaden RM training data." 这就是 Goodhart 定律：指标一旦成为优化目标就不再是好指标。D 方向相反——KL 太大会让策略几乎不动，不会出现这种"指标与真实质量背离"。

### Q5 — 答案：B

讲义："DPO (Rafailov 2023): closed-form algebra collapses Stage 2+3 into a single supervised loss over preference data. No RM, no PPO. Same quality on alignment benchmarks for a fraction of the compute." C 描述的是 GRPO + 验证器的典型场景；D 方向相反。

### Q6 — 答案：B

讲义："GRPO (DeepSeek 2024–2025): PPO with a group-relative baseline instead of a critic, reward from a *verifier* (code runs / math answer matches) instead of a human-trained RM. Dominant for reasoning models." GRPO 每个 prompt 要采样一组回答，D 错。

### Q7 — 答案：B

讲义："Process reward models (PRMs): score partial solutions (each reasoning step), used in both RLHF and GRPO variants for reasoning." 普通的结果奖励模型（ORM）只看最终输出。PRM 让长推理链中的信用分配更细，但标注成本更高。

### Q8 — 答案：B

讲义 Pitfalls："Too low β → drift and reward hacking. Too high β → policy barely changes." 极端情况下 β→∞，最优策略就是参考模型本身。

### Q9 — 参考答案

| 步 | r_pos | r_neg | p = σ(Δ) | 更新后 w |
|---|---|---|---|---|
| 1 | 0.0 | 0.0 | 0.5 | `clear=0.1, rude=-0.05, vague=-0.05` |
| 2 | 0.1 | -0.1 | 0.5498 | `clear=0.145, kind=0.045, rude=-0.14, vague=-0.05` |

推导：第 1 步 `grad_scale = 0.5`；`clear` 出现 2 次，`w[clear] += 0.1·0.5·2 = 0.1`；`rude`、`vague` 各 -0.05。第 2 步 `r_pos = w[clear] + w[kind] = 0.1 + 0 = 0.1`，`r_neg = 2·w[rude] = -0.1`，`Δ = 0.2`，`p = σ(0.2) ≈ 0.5498`，`grad_scale ≈ 0.4502`；`clear`、`kind` 各 +0.045，`rude` 出现 2 次 → `-0.1·0.4502·2 ≈ -0.09`，变为 -0.14。（已用代码实际验证。）

为什么是 `1 - p`：损失 `L = -log σ(Δ)`，`dL/dΔ = -(1 - σ(Δ))`。梯度下降 `w -= lr·dL/dw`，而 `dΔ/dw[t] = c_pos(t) - c_neg(t)`（词频），所以 `w[t] += lr·(1-p)·c_pos(t)`，`w[t] -= lr·(1-p)·c_neg(t)`——正是代码。当 RM 已经很确信（p→1）时 `1-p→0`，这对样本几乎不再产生更新——逻辑回归"自动关注难样本"的性质；被判错的样本（p 很小）梯度最大。

### Q10 — 参考答案

(a) `kl(probs_new, probs_ref)` 是**整个分布**之间的 KL，对同一个 prompt、同一时刻采样出的**任何 token 都相同**——它与所选动作无关。策略梯度中，一个与动作无关的量乘以 `∇log π(a|s)` 的期望为 0（和 baseline 不改变期望是同一个恒等式 `Σ_a π(a)∇log π(a) = 0`），所以它在期望上**不会把策略往参考模型拉**。它唯一的作用是让不同 prompt 之间的奖励出现偏移、抬高 batch 内奖励的标准差，从而在标准化后缩小 RM 信号的 advantage，间接拖慢学习——所以 β=1.0 时 KL 略低，但远没有被"约束住"。

(b) 用**被采样 token** 的对数比率作为 KL 的单样本估计（这也是 LLM RLHF 中逐 token KL 惩罚的标准写法）：

```python
log_ratio = math.log(max(probs_new[token], 1e-12)) - math.log(max(probs_ref[token], 1e-12))
reward = rm_score - beta * log_ratio
```

它对 `y ~ π_θ` 的期望正是 `KL(π_θ‖π_ref)`，且随动作变化：越是被策略"过度偏爱"（相对参考模型）的 token，惩罚越大。实测修正后（150 次更新，同样种子）：

| β | 原代码最终 KL | 修正后最终 KL | 闭式最优 π* 的 KL |
|---|---|---|---|
| 0.01 | 2.293 | 1.963 | 2.161 |
| 0.1 | 2.265 | 0.817 | 0.915 |
| 1.0 | 1.831 | 0.364 | 0.366 |

修正后 KL 随 β 单调、显著下降，并且与 Q12 的理论最优值吻合；原代码即使把 β 调到 10，最终 KL 仍有约 0.90。讲义 Step 3 的示例代码也是同样的写法，阅读时要注意。

### Q11 — 参考答案

朴素写法在 x 很负时，`math.exp(-x)` 会变成 `exp(很大的数)`：例如 `x = -1000` 时 `math.exp(1000)` 直接抛 `OverflowError: math range error`（Python 的 `math.exp` 溢出会抛异常，而 NumPy 会返回 `inf` 并给出警告）。分支写法保证 `exp` 的参数永远 ≤ 0：x>0 时算 `exp(-x)`，x≤0 时算 `exp(x)`，两者都在 (0, 1] 内，不会溢出。实测 `sigmoid(-1000) = 0.0`、`sigmoid(1000) = 1.0`。

框架里计算 BT 损失时不会先算 σ 再取 log（σ 接近 0 时 `log` 会得到 `-inf`），而是直接用 `logsigmoid`（如 PyTorch 的 `F.logsigmoid(r_pos - r_neg)`），或等价的 `-softplus(-Δ)`，内部做了同样的数值稳定处理。

### Q12 — 参考答案

```python
import math

def optimal_policy(rewards, ref_probs, beta):
    # π*(y) ∝ π_ref(y) · exp(R(y)/β)，在 log 空间计算避免溢出
    logits = [math.log(max(p, 1e-12)) + r / beta for r, p in zip(rewards, ref_probs)]
    m = max(logits)
    exps = [math.exp(z - m) for z in logits]
    Z = sum(exps)
    return [e / Z for e in exps]
```

(a) 用本节 RM（`train_rm(n_pairs=600, rng=random.Random(42))`）和均匀参考策略实测：β=0.01 时 KL≈2.16、期望奖励≈+1.185（几乎只选权重最大的一两个好词）；β=0.1 时 KL≈0.92、期望奖励≈+1.133；β=1.0 时 KL≈0.37、期望奖励≈+0.87（好词概率约是坏词的 `e^{2.2}≈9` 倍，但没有塌缩到单一 token）。β 越大，π* 越接近参考策略。

(b) DPO 的出发点就是这个闭式解：把它反解成 `R(y) = β·log(π*(y)/π_ref(y)) + β·log Z`，代入 Bradley-Terry 损失后，`β·log Z` 只与 prompt 有关，在 `R(y₊) - R(y₋)` 中**相互抵消**，于是得到只含策略对数比率的损失 `-log σ(β·[log π(y₊)/π_ref(y₊) - log π(y₋)/π_ref(y₋)])`。讲义说的"closed-form algebra collapses Stage 2+3 into a single supervised loss"就是指这一步，也解释了 skill 文件里"DPO (implicit KL)"的说法。详见阶段 10 · 08。

### Q13 — 参考回答要点

| 阶段 | 输入数据 | 目标 | 产出 |
|---|---|---|---|
| 1. SFT | 人类撰写的示范回答（prompt, response） | next-token 交叉熵 | `π_SFT`：倾向良好行为，但动作空间仍不受约束 |
| 2. RM | 同一 prompt 下的回答对 `(y₊, y₋)`，人类标注偏好 | Bradley-Terry：`-log σ(R(y₊) - R(y₋))` | `R_φ(x, y)`：从 SFT 初始化，主干 + 标量 head |
| 3. PPO | prompt 集合（在线采样回答） | 最大化 `R_φ(x,y) - β·KL(π_θ‖π_ref)` | 对齐后的策略 `π_θ`（从 `π_SFT` 初始化，`π_ref = π_SFT` 冻结） |

- 关键细节：RM 只给完整回答打分，advantage 在 token 级轨迹上计算；KL 是正则项不是硬约束；β 常取 0.01~0.05。
- 加分点：说出 PPO 阶段同时存在四个模型（policy、ref、RM、value），以及 PPO 内部的裁剪 KL（对 `π_old`）与 RLHF 的 KL（对 `π_ref`）的区别。
- 常见误区：以为 RM 是在 PPO 中继续训练的——标准流程中 RM 在第三阶段是冻结的。

### Q14 — 参考回答要点

- **推导**：BT 假设 `P(y₊ ≻ y₋ | x) = exp(R₊)/(exp(R₊)+exp(R₋)) = σ(R₊ - R₋)`。对标注数据做最大似然，即最小化负对数似然 `L = -E[log σ(R(x,y₊) - R(x,y₋))]`。
- **性质 1（平移不变）**：损失只依赖奖励**差**，`R(x,y) + c(x)` 对任意只依赖 prompt 的 `c(x)` 给出相同的损失。所以 RM 的零点是任意的。
- **性质 2（不可跨 prompt 比较）**：由于每个 prompt 都有一个"自由的"偏移 `c(x)`，prompt A 下 3.0 分的回答不一定比 prompt B 下 1.0 分的回答更好。实践中常对 RM 输出做归一化（如减去参考回答的分数或做 batch 标准化），PPO 中也会做 advantage 标准化。
- **加分点**：BT 是 1952 年的模型（讲义），还可扩展为 Plackett-Luce 处理多回答排序；标注噪声大时可以加温度或过滤低一致性样本（讲义："~30% of human labels are noisy or ambiguous"）。
- **常见误区**：把 RM 输出当作"绝对质量分"写进业务阈值。

### Q15 — 参考回答要点

- **定义**：策略利用 RM 的缺陷，获得高 RM 分数却没有真正变好（Goodhart 定律）。根因是 RM 只在 SFT 分布附近训练过，分布外的输出其打分不可信。
- **常见表现**：
  1. **长度作弊**：RM 隐式偏好长回答，策略学会注水（讲义 Pitfalls）；
  2. **谄媚（sycophancy）**：附和用户观点更容易拿到人类偏好；
  3. **格式/措辞投机**：堆砌 RM 偏爱的套话、列表、免责声明；
  4. **过度拒答或过度自信**：取决于 RM 在安全维度上的偏差；
  5. **分布外乱码**：极端情况下出现 RM 打高分的异常文本。
- **缓解手段**：
  - KL 惩罚 / 自适应 β（讲义：最重要的旋钮）；
  - 提前停止，保留**盲测的人类评估集**做过优化守卫（skill 文件："Flag any pipeline that does not hold back a blind human-eval set"）；
  - 扩充、迭代 RM 数据（在当前策略的输出上重新标注）；
  - 长度归一化奖励或长度感知 RM；多个 RM（有用性 / 安全分开）；
  - 用可验证奖励替代学习奖励（适用时）。
- **加分点**：提到 RM ensemble 或不确定性惩罚；把"奖励曲线与人类评估分离"作为告警规则。

### Q16 — 参考回答要点

参照讲义 Use It 表的分层思路：

| 目标 | 方法 | 理由 |
|---|---|---|
| 有用性 / 无害性 | SFT → DPO（讲义："DPO preferred over RLHF-PPO"） | 偏好数据充足，DPO 无需 RM 和在线采样，成本低、稳定 |
| 数学 / 代码推理 | GRPO + 验证器奖励（单元测试通过、答案匹配） | 奖励可验证，不怕 RM 被 hack；省掉 critic |
| 长程多步任务 | PPO / GRPO + PRM | 需要步骤级信用分配 |
| 安全拒答 | RLHF-PPO + 独立的安全 RM，或 Constitutional AI | 安全是 RM 密集、需细粒度控制的环节；讲义："PPO-only for the RM-intensive or safety-critical steps" |
| 上线前快速对齐 | Best-of-N + RM 在解码时打分 | 不训练策略，推理换质量 |

- 工程要点：每个阶段都设 KL / 回归监控；安全 RM 与有用性 RM 分开；红队集与拒答率作为发布门槛（skill 文件的 Safety gate）。
- 加分点：讨论阶段顺序（先 SFT 再偏好优化再推理 RL，或交替进行），以及 RLAIF 用于扩充偏好数据。

### Q17 — 参考回答要点

- **必看指标**：平均 KL(π_θ‖π_ref)（讲义："the top diagnostic in real RLHF"）、RM 奖励均值与方差、留出人类/强模型评估、平均回答长度、PPO 的 clip fraction 与 value loss、熵。
- **KL 超过 10 且回答变长**：讲义 Step 4 指出 KL 超过约 5~10 就说明策略已经远离 `π_SFT`，叠加长度上升，基本可以判定为过优化 + 长度作弊。
- **处理**：
  1. 回滚到 KL 较低、人类评估最好的 checkpoint（提前停止）；
  2. 提高 β 或启用自适应 β 并设合理的目标 KL；
  3. 奖励做长度归一化，或在 RM 训练数据中加入"长而差"的负例；
  4. 检查 KL 的计算方式是否正确（例如是否真的是逐 token 的对数比率，见 Q10）；
  5. 降低学习率 / PPO epoch 数。
- **加分点**：把"奖励上升但评估下降"写成自动告警，并在训练中定期用新策略的样本重新收集偏好、更新 RM。

### Q18 — 参考回答要点

- **讲义的立场**：Pitfalls 写道 "The RM needs to be at least as large as the policy. A tiny RM cannot faithfully score the policy's outputs."，skill 文件也拒绝使用比策略小的 RM。背后的直觉是：RM 要识别策略生成内容中的细微错误，能力不能弱于策略，否则容易被策略"骗过"。
- **需要补充的事实**：这并不是业界的硬性规律。例如 InstructGPT 论文中，175B 策略使用的是 6B 的 RM，作者给出的理由是节省计算且 175B RM 训练不稳定。很多开源流水线也用比策略小的 RM。
- **更稳妥的回答**：RM 越强，越不容易被 hack，过优化来得越晚；但 RM 规模受限于计算预算和训练稳定性。实践中用 KL 约束、提前停止、RM 集成、迭代更新 RM 来弥补 RM 能力不足。
- **加分点**：提到"弱监督强"（weak-to-strong）这一研究方向正是在研究"较弱的监督者如何约束更强的模型"。
- **常见误区**：把"RM 至少和策略一样大"当作无条件成立的定律背下来。

---

## 六、关联知识点

### 前置知识
- [阶段 09 · 08 近端策略优化（PPO）](../../08-ppo/docs/zh.md)：RLHF 第三阶段的优化器，裁剪目标与诊断指标。
- [阶段 09 · 07 Actor-Critic](../../07-actor-critic-a2c-a3c/docs/zh.md)：advantage、critic、组合损失。
- [阶段 05 · 05 情感分析](../../../05-nlp-foundations-to-advanced/05-sentiment-analysis/docs/zh.md)：讲义列出的前置——给文本打分的分类器，就是 RM 的雏形。
- [阶段 02 · 03 逻辑回归](../../../02-ml-fundamentals/03-logistic-regression/docs/zh.md)：Bradley-Terry 损失本质上是对"奖励差"做逻辑回归。

### 本节被哪些后续内容用到
- [阶段 09 · 12 游戏强化学习](../../12-rl-for-games/docs/zh.md)：GRPO 与可验证奖励，推理时代的 RL。
- [阶段 10 · 06 指令微调 SFT](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：RLHF 第一阶段。
- [阶段 10 · 07 RLHF](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)：在真实 LLM 上实现完整 RLHF。
- [阶段 10 · 08 DPO](../../../10-llms-from-scratch/08-dpo/docs/zh.md)：把 RM + PPO 合并成偏好损失。
- [阶段 10 · 09 Constitutional AI 与自我改进](../../../10-llms-from-scratch/09-constitutional-ai-self-improvement/docs/zh.md)：RLAIF。
- [阶段 18 · 02 Reward Hacking 与 Goodhart](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：过优化的系统讨论。
- [阶段 18 · 04 谄媚与 RLHF 放大](../../../18-ethics-safety-alignment/04-sycophancy-rlhf-amplification/docs/zh.md)：RLHF 带来的副作用。
- [阶段 18 · 11 可扩展监督与弱到强](../../../18-ethics-safety-alignment/11-scalable-oversight-weak-to-strong/docs/zh.md)：监督者弱于被监督模型时如何对齐。

### 延伸关键词
`Bradley-Terry` · `Plackett-Luce` · `InstructGPT` · `reward over-optimization scaling laws` · `RM ensemble` · `length-controlled win rate` · `RLAIF` · `PRM vs ORM` · `Best-of-N` · `adaptive KL controller` · `DPO / IPO / KTO` · `RLVR (verifiable rewards)`
