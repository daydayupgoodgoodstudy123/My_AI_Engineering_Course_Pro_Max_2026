# 测验 · 将指令遵循作为 Alignment 信号（Instruction-Following as Alignment Signal）

> **阶段 18 · 伦理、安全与对齐 · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 预训练模型为什么"不听话" | 它的任务是续写网页文本；问"写一个反转列表的函数"，常常续写出另一个提示。讲义："The model is doing its job — the job is wrong." |
| 2 | InstructGPT 三阶段 | SFT（交叉熵模仿示范）→ 奖励模型 RM（成对偏好的 Bradley-Terry 损失）→ PPO（最大化 RM 分数 − β·KL 到 SFT 策略） |
| 3 | Stage 1：SFT | 讲义：约 13k 条来自标注员和 OpenAI API 的提示；让模型"回答"而不是"续写"，但不提供"多个合理答案中哪个更好"的信号 |
| 4 | Stage 2：Bradley-Terry RM | `L_RM = −log σ(r(x, y_w) − r(x, y_l))`，把排序变成二分类；RM 通常由 SFT 模型初始化、把 LM head 换成标量 head；讲义："6B was enough for the 175B InstructGPT" |
| 5 | Stage 3：KL 惩罚 | `J(π) = E[r(x,y)] − β·KL(π‖π_SFT)`；没有 KL，优化器会找到 RM 没见过、却打高分的对抗样本。β 太小 → reward hacking，太大 → 相对 SFT 没有提升 |
| 6 | KL 正则下的最优策略 | 解析解 `π*(a) ∝ π_SFT(a)·exp(r(a)/β)`：β 是"相信奖励"与"贴近 SFT"之间的温度；本节代码在 β ≥ 0.5 时收敛到这个解 |
| 7 | Alignment tax 与 PPO-ptx | RLHF 后在 SQuAD、HellaSwag、DROP 等基准上退步；PPO-ptx 在目标中加入 `γ·E[log π(x)]`（预训练数据的似然）来抵消 |
| 8 | 1.3B 胜过 175B | 讲义：1.3B InstructGPT 约 70% 的时间被标注员偏好于 175B GPT-3。对齐与能力是两个轴；能力上限由基座模型决定，RLHF 不能教会新事实 |
| 9 | 本节是阶段 18 的参照点 | reward hacking 攻击 Stage 2，DPO 合并 Stage 2+3，CAI 替换人类标注员，sycophancy 说明标注员信号有偏，alignment faking 说明策略可以绕过 Stage 3 |
| 10 | 代码中的简化与偏差 | 三臂 bandit + 精确期望的策略梯度（不是 PPO）；RM 与真实效用排序一致，所以 β=0 与 β=0.1 几乎一样（KL 0.354 vs 0.340），**没有出现 reward hacking**；Run 3 的 +0.5 偏置不足以翻转排序 |

### 核心技能（能动手做到）

- [ ] 写出 InstructGPT 三阶段各自的输入数据、损失函数与输出
- [ ] 手算 Bradley-Terry 损失及其梯度 `1 − σ(r_w − r_l)`，解释 RM 为何只学到"相对分数"
- [ ] 推导 KL 正则目标的解析最优解 `π_SFT·exp(r/β)/Z`，并用它预测不同 β 下的最终策略
- [ ] 读懂 `stage3_ppo` 的梯度公式，说出它与真正 PPO（比值裁剪、价值函数、优势基线）的区别
- [ ] 设计一个能"真正看到 reward hacking"的实验：让 RM 与真实效用排序不一致，并同时追踪代理奖励与真实效用
- [ ] 用"三阶段 + 正则项 + 偏好来源 + alignment tax"四个维度诊断任意 RLHF 类方法

---

## 二、基础自测（选择题）

**Q1.** InstructGPT 三个阶段及其损失，正确的是：

- A. SFT 用 Bradley-Terry 损失；RM 用交叉熵；PPO 不需要正则项
- B. SFT 用交叉熵模仿示范；RM 用成对偏好的 Bradley-Terry 损失；PPO 最大化 RM 分数并减去 β·KL(π‖π_SFT)
- C. 先训练 RM，再用 RM 直接生成 SFT 数据，最后用 DPO 微调
- D. SFT 用 PPO；RM 用 MSE 回归人工打分；最后一步用交叉熵

**Q2.** 对一条偏好样本（`y_w` 优于 `y_l`），Bradley-Terry 奖励模型的损失是：

- A. `(r(x, y_w) − r(x, y_l))²`
- B. `−log r(x, y_w)`
- C. `max(0, 1 − r(x, y_w) + r(x, y_l))`
- D. `−log σ(r(x, y_w) − r(x, y_l))`

**Q3.** Stage 3 中 KL 惩罚最主要防范的是：

- A. 优化器找到 RM 打高分、但人类并不偏好的对抗性输出（RM 从没见过这些输出）
- B. 训练过程中的显存溢出
- C. RM 的过拟合
- D. 生成的文本过短

**Q4.** 关于 alignment tax 与 PPO-ptx，说法正确的是：

- A. alignment tax 指 RLHF 需要额外支付的 API 费用
- B. PPO-ptx 通过增大 β 来减少对 SFT 的偏离
- C. RLHF 后模型在未被奖励的标准基准上退步；PPO-ptx 在 RL 目标中加入预训练数据的对数似然项 `γ·E[log π(x)]` 来抵消
- D. PPO-ptx 用人类标注替代奖励模型

**Q5.** 讲义称 1.3B InstructGPT 约 70% 的时间被标注员偏好于 175B GPT-3。下列结论与讲义一致的是：

- A. 参数量不再重要，小模型的知识已经超过大模型
- B. RLHF 能让模型学会预训练中没见过的事实
- C. 标注员更偏好短回答，所以小模型胜出
- D. 对齐与能力是不同的轴；能力上限由基座模型决定，RLHF 只是在基座的分布上重新加权行为

**Q6.** 运行 `main.py`，Run 1（β = 0.1）与 Run 2（β = 0.0）的结果最接近下列哪一项？

- A. Run 1 停在 SFT 分布附近，Run 2 全部押注 C
- B. 两者几乎一样：都把约 97% 的概率放在 B 上，最终 KL 分别约 0.340 和 0.354 nats
- C. Run 2 的最终奖励远高于 Run 1
- D. Run 2 出现数值溢出，程序报错

**Q7.** 在三臂 bandit 中，KL 正则目标的最优策略是 `π*(a) ∝ π_SFT(a)·exp(r(a)/β)`。已知 `π_SFT = [0.18, 0.63, 0.19]`、`r = [−0.146, +0.716, −0.569]`，当 β = 1.0 时 `π*` 约为：

- A. `[0.100, 0.831, 0.069]`
- B. `[0, 1, 0]`
- C. `[0.18, 0.63, 0.19]`
- D. `[0.333, 0.333, 0.333]`

**Q8.** 讲义说 InstructGPT 的奖励模型通常这样初始化：

- A. 随机初始化的小型 MLP
- B. 直接使用 175B GPT-3 的最后一层
- C. 由 SFT 模型初始化，把 LM head 换成输出标量的 head
- D. 由人工规则打分器蒸馏得到

---

## 三、动手 / 代码题

**Q9.** `main.py` 的 Run 2 标题是 "beta = 0.00 (no KL — reward hacking shows up)"，讲义 "Use It" 也说关掉 KL 后"reward hacking appear inside 50 update steps"。实际输出：

```text
Stage 2 RM complete.
  Reward per action: ['-0.146', '+0.716', '-0.569']

Run 1: beta = 0.10 (standard InstructGPT)
  RLHF probs    : ['0.017', '0.969', '0.014']
  Final KL      : 0.340 nats
Run 2: beta = 0.00 (no KL — reward hacking shows up)
  RLHF probs    : ['0.015', '0.973', '0.012']
  Final KL      : 0.354 nats
```

1. 标注员的真实效用是 `[0.0, 1.0, −0.3]`。Run 2 收敛到 B，这算 reward hacking 吗？为什么？
2. 为什么 β = 0.1 和 β = 0 几乎没区别？（提示：用 `π_SFT·exp(r/β)` 估算 β = 0.1 时的最优策略。）
3. 设计一个 β 扫描实验，让 KL 的作用"看得见"。

**Q10.** Run 3 想演示"RM 有 bug 时 KL 只能部分阻止利用"：

```python
    rm_buggy = stage2_reward_model(bias=[0.5, 0.0, 0.0])
    rlhf3, r3, kl3 = stage3_ppo(sft, rm_buggy, beta=0.1)
```

输出 RM 为 `['-0.105', '+0.862', '-0.757']`，最终策略 `['0.015', '0.974', '0.011']`。

1. 列出这段实验设计的三个问题（提示：讲义练习 2 说的是给哪个动作加偏置？`stage2_reward_model` 第二次调用时随机数状态如何？+0.5 能否翻转排序？）。
2. 固定同一个 RM 后，我们测得下表（"真实效用" = `Σ π(a)·utility(a)`，SFT 为 0.573）：

| A 上的偏置 | β | 最终策略 | KL | 真实效用 |
|-----------|---|---------|----|---------|
| +0.5 | 0.1 | [0.035, 0.948, 0.016] | 0.290 | 0.943 |
| +1.5 | 0.1 | [0.920, 0.068, 0.012] | 1.317 | **0.064** |
| +1.5 | 1.0 | [0.331, 0.615, 0.054] | 0.119 | 0.598 |

请解读这张表，说明"代理奖励 + 优化压力"如何导致真实效用下降，以及 β 起了什么作用。

**Q11.** 手算题：

1. `r_w − r_l` 分别为 0、1、−1 时，Bradley-Terry 损失和 `stage2_reward_model` 中的更新量 `lr·(1 − s)`（lr = 0.05）各是多少？
2. 用 Run 1 打印的策略 `[0.017, 0.969, 0.014]` 和 SFT `[0.18, 0.63, 0.19]` 计算 `KL(π‖π_SFT)`（单位 nats）。
3. 标注员示范分布是 `softmax([0, 1, −0.3])`，算出它；再说明为什么 SFT 打印的是 `[0.180, 0.630, 0.190]`。

**Q12.** 阅读 `stage3_ppo` 的核心部分：

```python
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
        probs = pi.probs()
        grad = [0.0, 0.0, 0.0]
        for a in range(3):
            for b in range(3):
                indicator = 1.0 if a == b else 0.0
                grad[b] += advantages[a] * probs[a] * (indicator - probs[b])
        pi.logits = [l + lr * g for l, g in zip(pi.logits, grad)]
```

1. `grad[b]` 计算的是哪个函数对 logit `b` 的梯度？为什么说它是"精确期望梯度"而不是 REINFORCE 的采样估计？
2. 某个动作在一个 batch 中一次都没被采到时，它的 `advantages[a]` 是多少？这隐含了什么假设？
3. 与真正的 PPO 相比，这里缺了哪些部分？写出 PPO 的 clipped surrogate 目标。

---

## 四、面试高频题

**Q13.**（基础必考）请完整描述 InstructGPT 的 RLHF 流水线：每个阶段的数据、损失、输出各是什么？为什么需要三个阶段而不是直接用人类偏好做监督学习？

**Q14.**（原理深挖）KL 惩罚在 RLHF 中的作用是什么？请从"KL 正则目标的解析最优解"角度解释 β 的含义，并说明 β 过大、过小各会发生什么。

**Q15.**（原理深挖）什么是 alignment tax？PPO-ptx 如何缓解它？还有哪些替代做法？

**Q16.**（工程实践）给你一份声称"对齐了模型"的新方法论文，你会用什么框架快速判断它改了 RLHF 的哪一部分、风险在哪？

**Q17.**（追问型）"1.3B InstructGPT 胜过 175B GPT-3"说明了什么、没说明什么？为什么讲义说这个比例在生产流量的隐藏测试提示上会更高？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义三阶段：SFT 用"standard cross-entropy loss"；RM 用 Bradley-Terry 成对损失；Stage 3 用 PPO 最大化 `E[r] − β·KL(π‖π_SFT)`。

- A 把 SFT 与 RM 的损失对调，且去掉了最关键的 KL。
- C 描述的不是 InstructGPT；DPO 是后来的方法（第 03 节），它合并了 Stage 2 和 3。
- D 顺序和损失都不对；RM 学的是成对比较，不是绝对分数回归。

### Q2 — 答案：D

`L_RM = −log σ(r(x, y_w) − r(x, y_l))`：偏好概率建模为两者奖励差的 sigmoid，最大化"被偏好者胜出"的对数似然。只依赖奖励**差**，所以 RM 的绝对值没有意义（代码因此把奖励中心化）。

- A 是回归损失，需要绝对分数标签。
- B 没有比较项。
- C 是 hinge（margin ranking）损失，是另一种排序损失，不是 Bradley-Terry。

### Q3 — 答案：A

讲义："Without it, the optimizer finds adversarial examples — strings that score high under the RM because the RM never saw them, not because humans actually prefer them." RM 只在 SFT 分布附近见过数据，离开这片区域它的打分不可信；KL 把策略拴在 SFT 附近。

- B、D 与 KL 无关。
- C：RM 的过拟合要靠 RM 训练时的验证集与正则处理，KL 处理的是**策略**对 RM 的过度利用。

### Q4 — 答案：C

讲义："After RLHF, the model is preferred by humans but regresses on standard benchmarks (SQuAD, HellaSwag, DROP)… fix it with PPO-ptx: mix pre-training gradients into the RL objective"，目标为 `J_ptx(π) = J(π) + γ·E_{x~D_pretrain}[log π(x)]`。

- A 是字面误解。
- B：PPO-ptx 不改 β，而是加入预训练似然项。
- D：RM 仍然保留。

### Q5 — 答案：D

讲义从这个数字读出两点："Alignment is a different axis from capability" 与 "The capability floor is set by the base model. You cannot RLHF a base model into knowing facts it never saw."

- A、B 正是讲义否定的说法；skill 文件也把"RLHF teaches new facts"列为 hard reject。
- C：讲义没有这样的说法。

### Q6 — 答案：B

实际运行：Run 1 `['0.017', '0.969', '0.014']`、KL 0.340；Run 2 `['0.015', '0.973', '0.012']`、KL 0.354；两者的最终奖励都是 +0.689。原因见 Q9：这个 RM 与真实效用排序一致，而且 β = 0.1 相对奖励尺度太小，KL 几乎不起作用。

- A、C、D 与实际输出不符。

### Q7 — 答案：A

`w = π_SFT · exp(r/β)`：`0.18·e^{−0.146} = 0.1556`、`0.63·e^{0.716} = 1.2894`、`0.19·e^{−0.569} = 0.1076`，归一化后约 `[0.100, 0.831, 0.069]`（已用 Python 计算）。代码在 β = 1.0、300 步时实际得到 `[0.097, 0.835, 0.067]`，与解析解吻合。

- B 是 β → 0（只看奖励）的极限。
- C 是 β → ∞（完全不动）的极限。
- D 是均匀分布，与两者都无关。

### Q8 — 答案：C

讲义："The RM is usually initialized from the SFT model with the LM head replaced by a scalar head." 这样 RM 一开始就"理解"SFT 模型生成的文本分布。

- A、B、D 都不是讲义的说法。

### Q9 — 参考答案

1. **不算。** reward hacking 指"代理奖励上升、真实目标不升反降"。这里 RM `[−0.146, +0.716, −0.569]` 与真实效用 `[0, 1, −0.3]` 排序完全一致，B 既是 RM 最爱也是标注员最爱。Run 2 收敛到 B，真实效用从 SFT 的 0.573 升到约 0.97——这是"mode-seeking（只押最高分动作）"，而不是 hacking。在一个 RM 无误的 bandit 里，β = 0 的最优解本来就是 argmax。讲义练习 1 要求解释的正是这种 mode-seeking。
2. 用解析解估算：β = 0.1 时 `exp(r/β)` 把奖励差放大到 `exp(8.62) ≈ 5,500` 倍，最优策略约为 `[0.0001, 0.9999, 0.0000]`——几乎等同于 β = 0 的 argmax。也就是说 β = 0.1 相对奖励尺度（约 ±0.7）**太小**，两次运行在 300 步内都还没收敛，差别只取决于优化速度，而不取决于 KL。（真实 RLHF 中 β 的合适数值取决于奖励尺度，不能脱离 RM 谈 β。）
3. β 扫描（固定随机种子，300 步；"最优解"列为解析解）：

| β | 最终策略 | KL | 解析最优解 |
|---|---------|----|-----------|
| 0.0 | [0.015, 0.973, 0.012] | 0.354 | argmax = B |
| 0.1 | [0.017, 0.969, 0.014] | 0.341 | [0.0001, 0.9999, 0.0] |
| 0.5 | [0.043, 0.928, 0.029] | 0.244 | [0.047, 0.931, 0.022] |
| 1.0 | [0.097, 0.835, 0.067] | 0.106 | [0.100, 0.831, 0.069] |
| 2.0 | [0.138, 0.744, 0.118] | 0.031 | [0.138, 0.744, 0.118] |
| 5.0 | [0.163, 0.679, 0.158] | 0.005 | [0.163, 0.679, 0.158] |

β 越大，策略越贴近 SFT、KL 越小；β ≥ 0.5 时数值解与解析解吻合。想看到 reward hacking，还必须让 RM 与真实效用**不一致**（见 Q10）。

### Q10 — 参考答案

1. 三个问题：
   - **偏置加错了动作**：讲义练习 2 说"+0.5 bias for action B"，代码给的是 A。（其实给 B 加偏置也看不到 hacking，因为 B 本来就是真实最优；讲义与代码各有问题。）
   - **RM 被重新拟合**：`stage2_reward_model` 第二次调用时全局 `random` 状态已经变了，抽到的 500 对偏好不同，得到一个**不同的** RM（B 从 +0.716 变成 +0.862），再叠加偏置。于是 Run 1 与 Run 3 的差别混入了"换了一个 RM"的噪声。应该复用 `rm` 再加偏置。
   - **+0.5 不足以翻转排序**：中心化后 A 仍低于 B（−0.105 < +0.862），RM 的最爱还是 B，策略照样收敛到 B，没有任何"利用"可看。代码注释"With KL on, partial exploitation"与输出不符。
2. 解读：
   - +0.5 时 RM 排序仍是 B > A，策略照常收敛到 B，真实效用 0.943，无害。
   - +1.5 时 RM 变成 A（0.854）> B（0.216），β = 0.1 下策略把 92% 押在 A 上，**代理奖励上升（0.787），真实效用从 0.573 跌到 0.064**——这就是 reward hacking：优化压力把代理与真实目标之间的缝隙放大了。
   - 同样的坏 RM，β = 1.0 时策略只把 A 提到 0.331、仍保留 0.615 的 B，真实效用 0.598，略高于 SFT。KL 把策略拴在 SFT 附近，限制了对 RM 错误的利用，代价是真实最优也无法完全达到。
   - 结论：KL 不能"修复"坏 RM，只能限制利用的幅度；β 的选择取决于你对 RM 有多不信任——这正是第 02 节 Goodhart 定律的主题。

### Q11 — 参考答案

1. 用 `L = −log σ(d)`、更新量 `0.05·(1 − σ(d))`（已用 Python 计算）：

| d = r_w − r_l | 损失 | 1 − σ(d) | 更新量 |
|--------------|------|---------|-------|
| 0 | 0.693（= ln 2） | 0.500 | 0.025 |
| 1 | 0.313 | 0.269 | 0.0134 |
| −1 | 1.313 | 0.731 | 0.0366 |

RM 已经"排对"的样本（d > 0）梯度小，排错的样本（d < 0）梯度大，这是 logistic 损失的典型性质。

2. `KL = Σ π log(π/π_SFT) = 0.017·ln(0.017/0.18) + 0.969·ln(0.969/0.63) + 0.014·ln(0.014/0.19) ≈ −0.0401 + 0.4171 − 0.0365 ≈ 0.341` nats，与打印的 0.340 一致（差别来自四舍五入）。
3. `softmax([0, 1, −0.3]) = [1, 2.718, 0.741] / 4.459 ≈ [0.224, 0.610, 0.166]`。SFT 是在 200 条示范上做的**闭式 MLE**（计数频率取对数），打印的 `[0.180, 0.630, 0.190]` 就是 200 个样本里 A、B、C 的出现比例（36、126、38 次）。样本有限造成与真实分布的偏差——SFT 继承了示范数据的采样噪声。注意 docstring 说"single-step gradient move"，实际代码是闭式解，没有梯度步。

### Q12 — 参考答案

1. 设 `J(θ) = Σ_a π_θ(a)·Â(a)`，其中 `Â(a)` 视为常数。softmax 的导数 `∂π_a/∂θ_b = π_a(1[a=b] − π_b)`，所以 `∂J/∂θ_b = Σ_a Â(a)·π_a·(1[a=b] − π_b)`，正是代码的双重循环。它对**所有**动作按当前概率加权求和，相当于在已知每个动作平均奖励的前提下计算期望梯度；REINFORCE 则只对采到的动作用 `∇log π(a)·(R − b)` 做单样本估计。这里采样只用于估计每个动作的平均（成形）奖励。
2. 为 0。隐含假设是"没采到的动作，其成形奖励视为 0"。由于奖励已经中心化，0 大致等于平均奖励，所以偏差不大；但若奖励没有中心化（例如全为正），没被采到的动作就会被系统性地低估。随着策略变尖，小概率动作越来越难被采到，这个效应会加剧。
3. 缺少的部分：
   - 没有 old policy 与重要性比值 `ρ = π_θ(a)/π_old(a)`，也没有在同一批数据上做多轮更新；
   - 没有 clip；
   - 没有价值函数 / 优势基线（GAE）；
   - 没有 token 级的序列建模（bandit 只有一步）；
   - KL 作为奖励成形项（`r − β·log(π/π_SFT)`），与 InstructGPT 的做法一致，但梯度没有穿过 penalty 中的 π。

PPO 的 clipped surrogate：

```
L_CLIP(θ) = E_t[ min( ρ_t(θ)·Â_t , clip(ρ_t(θ), 1 − ε, 1 + ε)·Â_t ) ]
ρ_t(θ) = π_θ(a_t | s_t) / π_θ_old(a_t | s_t)
```

这里的 ε（通常 0.1–0.2）限制了每次更新的步长；RLHF 中通常再在奖励里减去 `β·log(π/π_SFT)`。代码 docstring 自己也承认是"Toy REINFORCE-with-KL (a stripped-down PPO)"。

### Q13 — 参考回答要点

- **Stage 1 SFT**：数据为人工写的（提示, 理想回答）对（讲义：约 13k 条提示）；损失为交叉熵；输出一个会"回答"而不是"续写"的模型。
- **Stage 2 RM**：对每个提示从 SFT 模型采样 K 个回答，标注员排序；拆成成对比较，用 Bradley-Terry 损失训练；RM 由 SFT 初始化、换标量 head；讲义："6B was enough for the 175B InstructGPT"。
- **Stage 3 PPO**：在提示分布上采样，RM 打分，目标 `E[r] − β·KL(π‖π_SFT)`，可加 PPO-ptx 项。
- **为什么不直接监督**：示范数据只告诉模型"一个可接受的答案"，不告诉它"多个合理答案中哪个更好"；比较比写示范更便宜、更一致；RM 把有限的人类比较泛化到任意新回答，RL 再在模型自己的分布上优化（on-policy），覆盖 SFT 看不到的情况。
- 加分点：说出 RM 只学到奖励差、所以要中心化/归一化；说出 KL 通常作为 token 级奖励成形项实现。

### Q14 — 参考回答要点

- **作用**：把策略拴在 SFT 附近；RM 只在这片区域可信，远离它就会出现 RM 打高分、人类不认可的对抗输出（讲义 Stage 3）。
- **解析解**：目标 `max_π E_π[r] − β·KL(π‖π_SFT)` 的最优解是 `π*(y) = π_SFT(y)·exp(r(y)/β)/Z`。β 就是"温度"：
  - β → 0：`exp(r/β)` 极尖，退化为 argmax(r)，完全相信 RM——讲义的"Too low: reward hacking"；
  - β → ∞：退化为 π_SFT——"Too high: no improvement over SFT"；
  - 本节代码在 β ≥ 0.5 时实测收敛到这个解（β = 1.0：`[0.097, 0.835, 0.067]` vs 解析 `[0.100, 0.831, 0.069]`）。
- **β 的尺度问题**：β 只有相对奖励尺度才有意义；本节 β = 0.1 对 ±0.7 的奖励来说几乎等于 0。
- 加分点：DPO（第 03 节）正是从这个解析解出发，把奖励表示为 `β·log(π/π_ref)`，从而跳过显式 RM 和 RL；skill 文件也强调 β 没有通用数值，只能在保留的能力基准上扫描选择。

### Q15 — 参考回答要点

- **定义**：RLHF 后人类偏好提高，但在没有被奖励的标准基准（讲义：SQuAD、HellaSwag、DROP）上退步。原因是 RL 只优化 RM 关心的行为，其余能力在参数漂移中被遗忘。
- **PPO-ptx**：`J_ptx = J + γ·E_{x~D_pretrain}[log π(x)]`，在 RL 梯度中混入预训练语言建模梯度，像"复习"一样保留通用能力。讲义："PPO-ptx became standard. Anthropic, DeepMind, and Meta all use some variant."
- **其他做法**（skill 文件列举）：混入 SFT 数据、rehearsal buffer；更大的 β（更贴近 SFT）；评测时同时报告偏好指标与能力基准。
- 常见误区：只报告偏好胜率而不报告能力基准——skill 文件要求明确指出这种情况。

### Q16 — 参考回答要点

用讲义 skill 文件的四步框架：

1. **逐阶段映射**：SFT / RM / RL 三个阶段分别是保留、修改、删除还是替换（例如 DPO：Stage 2 被隐式奖励替代、Stage 3 变成分类损失；CAI：标注员被 AI 评审 + 宪法替代）。
2. **正则检查**：是否保留参考策略锚点（显式 KL、隐式 β·log 比值、冻结）？没有锚点 + 任何不完美代理 = reward hacking 风险。
3. **偏好来源审计**：人类、AI 评审、宪法还是自我博弈？偏好来源的偏差会直接传递成 sycophancy 等问题（第 04 节）。
4. **alignment tax 检查**：是否有 PPO-ptx、SFT 混合等手段？只报告偏好指标、不报告能力基准要明确指出。

- 最后给出"这个方法在上述选择下最大的单一失效模式"。
- 加分点：能现场把 DPO、CAI、RLAIF 套进这张表。

### Q17 — 参考回答要点

- **说明了什么**：对用户而言，"按指令做事、不胡说"比"更多知识"更影响偏好；对齐是独立于能力的轴；对齐训练的性价比很高。
- **没说明什么**：没说明小模型能力更强——讲义："The capability floor is set by the base model"；RLHF 不能注入新知识；偏好胜率也不等于安全或真实（后续 sycophancy、reward hacking 都会说明标注员偏好本身是有偏的代理）。
- **为什么隐藏生产提示上比例更高**（讲义练习 4，参考思路）：
  - 标注员自己写的提示往往更"像任务"、更明确，原始 GPT-3 在这类提示上也有机会靠续写碰对；真实用户的提示更随意、更依赖"理解意图"，未经指令微调的基座更容易续写跑偏；
  - 隐藏提示来自真实 API 流量，正是 SFT/RM 数据的来源分布，InstructGPT 恰好针对它训练；
  - 原始 GPT-3 需要精心的 few-shot 提示才能表现好，而生产提示通常没有这种工程。
- 常见误区：把这个结果理解为"参数量不重要"。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 06 指令微调（SFT）](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：Stage 1 的完整实现。
- [阶段 10 · 07 RLHF: Reward Model + PPO](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)：Stage 2、3 的工程细节。
- [阶段 10 · 08 DPO：直接偏好优化](../../../10-llms-from-scratch/08-dpo/docs/zh.md)：讲义练习 5 要求用 DPO 替换 PPO。
- [阶段 09 · 08 近端策略优化（PPO）](../../../09-reinforcement-learning/08-ppo/docs/zh.md)、[阶段 09 · 06 Policy Gradient — REINFORCE 从头开始](../../../09-reinforcement-learning/06-policy-gradients-reinforce/docs/zh.md)：理解本节代码与真正 PPO 的差别。
- [阶段 09 · 09 奖励建模 & RLHF](../../../09-reinforcement-learning/09-reward-modeling-rlhf/docs/zh.md)：Bradley-Terry 奖励模型。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：KL 散度的定义与性质。

### 本节被哪些后续内容用到
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../02-reward-hacking-goodhart/docs/zh.md)：攻击 Stage 2 的代理奖励。
- [阶段 18 · 03 直接偏好优化方法家族](../../03-direct-preference-optimization-family/docs/zh.md)：合并 Stage 2 与 3。
- [阶段 18 · 04 RLHF 对迎合行为的放大效应](../../04-sycophancy-rlhf-amplification/docs/zh.md)：标注员信号本身有偏。
- [阶段 18 · 05 Constitutional AI 与 RLAIF](../../05-constitutional-ai-rlaif/docs/zh.md)：用 AI 和宪法替换人类标注员。
- [阶段 18 · 07 潜伏 Agents：持续性欺骗](../../07-sleeper-agents-persistent-deception/docs/zh.md)、[阶段 18 · 09 伪装 Alignment](../../09-alignment-faking/docs/zh.md)：策略绕过 Stage 3 的方式。

### 延伸关键词
`InstructGPT` · `SFT` · `reward model` · `Bradley-Terry` · `PPO` · `KL penalty` · `β / KL coefficient` · `PPO-ptx` · `alignment tax` · `mode-seeking` · `reward hacking` · `reference policy` · `DPO` · `RLAIF`
