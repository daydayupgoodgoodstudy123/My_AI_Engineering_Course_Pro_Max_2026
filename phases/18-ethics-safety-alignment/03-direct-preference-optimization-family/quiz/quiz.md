# 测验 · 直接偏好优化方法家族（The Direct Preference Optimization Family）

> **阶段 18 · 伦理、安全与对齐 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | RLHF-with-KL 的闭式最优解 | `max E[r] − β·KL(π‖π_ref)` 的解是 `π*(y|x) = π_ref(y|x)·exp(r(x,y)/β) / Z(x)`，反解得 `r = β·log(π*/π_ref) + β·log Z(x)` |
| 2 | DPO 的推导关键 | 把上式代入 Bradley-Terry 偏好似然，`β·log Z(x)` 只依赖 x，在 `r(y_w) − r(y_l)` 中**相消**，剩下只含策略参数的损失——不再需要显式 reward model |
| 3 | 隐式奖励（implicit reward） | `β·log(π(y|x)/π_ref(y|x))`；DPO 的 margin 就是 chosen 与 rejected 的隐式奖励之差 |
| 4 | DPO 的三个失效模式 | 隐式奖励差无上界；Degraded Chosen（chosen 的绝对 log-prob 也可能下降，只要 rejected 降得更快）；分布外偏好对给出任意的隐式奖励 |
| 5 | IPO | 把 log-sigmoid 换成对固定目标 `1/(2β)` 的平方误差，margin 被"拉向"有界目标；偏好强度与隐式奖励差成正比，不会爆炸 |
| 6 | KTO | 不需要成对数据：单条样本 + "好/坏"二值标签，用前景理论（prospect theory）效用，对损失加更大权重（loss aversion） |
| 7 | SimPO | 去掉参考策略，用**长度归一化**的 log-likelihood 加 margin `γ`，消除 DPO 的长度偏置 |
| 8 | ORPO | `L = L_NLL(y_w) + λ·L_OR`，SFT 项本身就是正则项，无参考模型，从 base 模型一步训完 |
| 9 | BPO | 讲义：在 DPO 上加"一行修正"，惩罚 chosen 绝对 log-prob 的**下降**；讲义报告在 Llama-3.1-8B-Instruct 数学推理上比 DPO 高 10.1% |
| 10 | DAA 仍会过度优化 | 讲义：Rafailov et al.（NeurIPS 2024）显示 DPO/IPO/SLiC 的 gold reward–KL 曲线同样是"先升后崩"——DAA 没有逃出 Goodhart，只是换了"咬人"的位置 |

### 核心技能（能动手做到）

- [ ] 从 RLHF-with-KL 目标出发，在纸上推导出 DPO 损失，并指出 `Z(x)` 在哪一步相消
- [ ] 写出 DPO、IPO、KTO、SimPO、ORPO 的损失公式，并说出每个方法修的是 DPO 的哪个假设
- [ ] 手算 DPO/IPO/ORPO 在给定 log-prob 下的 margin、loss 和梯度权重 `1 − σ(margin)`
- [ ] 读懂 `code/main.py` 中 6 种损失的手写梯度，指出哪些是精确梯度、哪些做了简化（ORPO 漏 `1/(1−p)`、KTO 用 log-sigmoid 代替 sigmoid、BPO 的惩罚是双向的）
- [ ] 解释为什么本代码里"IPO 的 win_rate 最高"不能说明 IPO 最好（步数、学习率、SGD 噪声）
- [ ] 根据数据形态（成对/非成对、偏好强度分布、长度分布）和训练阶段选择偏好损失，并列出训练中要盯的日志指标

---

## 二、基础自测（选择题）

**Q1.** DPO 之所以能跳过显式的 reward model，最准确的原因是：

- A. 偏好数据本身不需要标量奖励，所以 RLHF 的奖励模型一直是多余的
- B. DPO 在内部的第二个优化循环里隐式地训练了一个奖励模型
- C. RLHF-with-KL 的最优策略有闭式解，奖励可以写成 `β·log(π*/π_ref) + β·log Z(x)`；代入 Bradley-Terry 似然后 `Z(x)` 相消，只剩策略参数
- D. Bradley-Terry 模型对任何奖励函数都恰好不变

**Q2.** 训练刚开始时 `π = π_ref`（策略就是参考模型的拷贝），对任意偏好对，DPO 损失的值是：

- A. `ln 2 ≈ 0.693`，与 β 无关
- B. 0，因为策略还没偏离参考模型
- C. 1.0
- D. `β · ln 2`，随 β 变化

**Q3.** IPO 损失为 `(h_w − h_l − 1/(2β))²`，其中 `h = log(π/π_ref)`。取本节代码的默认 `β = 0.1`，IPO 把每一对的 log-ratio 差往哪个目标值拉？

- A. 0.05
- B. 0.2
- C. 1.0
- D. 5.0

**Q4.** 一次 DPO 更新后，某偏好对的 `log π(y_w)` 从 −1.0 变为 −1.5，`log π(y_l)` 从 −1.0 变为 −3.0（参考模型两者都是 −1.0）。下列说法正确的是：

- A. chosen 的概率下降了，所以 DPO 损失一定上升
- B. margin 从 0 变成 `β × 1.5`，DPO 损失下降；但 chosen 的绝对概率也下降了——这就是 Degraded Chosen 现象
- C. 这种情况在 DPO 中不可能发生，因为 DPO 只会提高 chosen 的概率
- D. 这是 IPO 特有的问题，DPO 不会出现

**Q5.** 你的产品只收集到大量"点赞 / 点踩"日志：每条回复只有一个二值标签，没有同一 prompt 下的成对比较。最直接适用的方法是：

- A. KTO
- B. DPO
- C. IPO
- D. SimPO

**Q6.** 关于 SimPO，下列说法正确的是：

- A. 它保留参考策略，只是在 DPO 上加了一个 margin
- B. 它把 log-sigmoid 换成了 identity 映射
- C. 它在 SFT 的 NLL 上加 odds-ratio 项，从 base 模型一步训完
- D. 它去掉参考策略，用 `(β/|y|)·log π(y|x)` 做长度归一化，再减去 margin `γ`

**Q7.** 下面哪个方法**不需要参考模型**，并且可以从 base 模型**单阶段**训练到对齐模型（不需要单独的 SFT checkpoint）？

- A. DPO
- B. IPO
- C. ORPO
- D. BPO

**Q8.** 讲义引用 Rafailov et al.（NeurIPS 2024）关于 DAA 过度优化的研究，其结论是：

- A. DPO 会过度优化，但 IPO 和 SimPO 不会
- B. DPO、IPO、SLiC 的 gold reward 随 KL 预算变化同样呈现 Gao et al. 式的"先升后崩"曲线，KL 正则并不能稳定它
- C. 只要成对数据超过 10 万条，过度优化就会消失
- D. DAA 因为没有显式奖励模型，从设计上消除了 Goodhart 效应

---

## 三、动手 / 代码题

**Q9.** 阅读 `train_dpo` 中 BPO 分支：

```python
        elif variant == "bpo":
            # DPO + penalty on decreases of log_pi_w
            g_margin = -(1.0 - sigmoid(margin))
            anchor_pen = -1.0 * (log_pi_w - log_ref_w)  # push chosen toward/above ref
            grad = [beta * (g_margin * gw_i - g_margin * gl_i) - 0.05 * anchor_pen * gw_i
                    for gw_i, gl_i in zip(gw, gl)]
```

（`apply_grad` 执行的是 `logits -= lr * grad`，`gw` 是 `∂log π(y_w)/∂logits`。）

1. 额外那一项 `−0.05 · anchor_pen · gw` 等价于在损失上加了什么项？写出它的表达式。
2. 当 chosen 的 log-ratio `Δ_w = log π(y_w) − log π_ref(y_w)` **为正**（chosen 已经比参考模型更可能）时，这一项会把 `log π(y_w)` 往哪个方向推？这与注释"penalty on decreases"和讲义的描述一致吗？
3. 改写成只惩罚"下降"的单向版本。

**Q10.** 运行 `python3 main.py` 得到：

```text
  true optimum : ['0.241', '0.537', '0.132', '0.089']
  DPO       probs=['0.231', '0.636', '0.086', '0.047']  win_rate=0.636
  IPO       probs=['0.032', '0.943', '0.024', '0.001']  win_rate=0.943
  BPO       probs=['0.253', '0.507', '0.141', '0.098']  win_rate=0.507
  ORPO      probs=['0.247', '0.364', '0.193', '0.196']  win_rate=0.364
```

有同学据此总结："IPO 对齐效果最好，ORPO 最差，DPO 已经收敛到最优。"请逐条反驳：

1. `win_rate` 实际计算的是什么？它是讲义所说的 "win rate" 吗？
2. 在 Bradley-Terry 数据无限多时，DPO（`β = 0.1`、参考 logits `[0.1, 0.2, −0.1, −0.2]`）的**总体最优策略**是什么？它和 `true optimum` 一致吗？DPO 跑完 2000 步到达那里了吗？
3. 为什么 IPO 的 0.943 不可靠？（提示：IPO 的梯度里没有 β 因子，而目标是 5；考虑单样本 SGD 的噪声。）
4. ORPO 为什么停在 0.364 附近？

**Q11.** 手算 ORPO 的 odds-ratio 项，并检查代码的梯度简化。

1. 设 `π(y_w) = 0.5`、`π(y_l) = 0.2`，求 `odds(y_w)`、`odds(y_l)`、`log(odds_w/odds_l)` 和 `L_OR = −log σ(log(odds_w/odds_l))`。
2. `log odds(y) = log p − log(1 − p)` 对 logits 的梯度是多少？代码写的是 `lam * g_or * (gw_i - gl_i)`，漏了什么因子？在本节默认 `λ = 0.1` 下这个简化影响大吗？

**Q12.** 讲义练习 3 要求"让 rejected 平均比 chosen 长 2 倍，数值展示 DPO 的长度利用以及 SimPO 的修复"。

1. 本代码里 `train_simpo` 的 `lens = [1, 1, 1, 1]`。为什么在这个"单动作"玩具里，无论把 `lens` 设成什么都无法真正复现长度偏置？
2. 设计一个最小可行的改造方案（可以描述数据结构和损失计算，不必写完整代码），让"序列长度"真实影响 log-prob。
3. 手算：`log π(y_w) = −12`（6 个 token）、`log π(y_l) = −10`（2 个 token），无参考模型的"原始 log-prob 差"与 SimPO 的 margin（`β = 1.5`、`γ = 0.5`）分别是多少？哪个更偏好 chosen？

---

## 四、面试高频题

**Q13.**（基础必考）请从 RLHF-with-KL 的目标函数出发推导 DPO 损失，并说明推导依赖了哪些假设。

**Q14.**（原理深挖）DPO 训练日志里常看到 chosen 和 rejected 的 log-prob 一起下降。为什么会这样？它有什么危害？IPO、BPO、ORPO 分别从什么角度缓解？

**Q15.**（工程实践）你负责一个 7B 模型的偏好对齐阶段，手上有 20 万条成对偏好数据。你会如何选择损失、设置超参数，并在训练中监控哪些指标来判断"是否开始过度优化"？

**Q16.**（追问型）有人说："DPO 没有显式 reward model，所以不存在 reward hacking。"你怎么回应？

**Q17.**（场景设计）一个客服产品同时有三类数据：少量专家标注的成对偏好、大量用户点赞/点踩、以及一批人工改写的高质量回复。请设计一个后训练方案，说明每类数据用什么损失、按什么顺序训练。

---

## 五、参考答案与解析

### Q1 — 答案：C

RLHF-with-KL 目标的最优解为 `π*(y|x) = π_ref(y|x)·exp(r(x,y)/β)/Z(x)`。反解得 `r(x,y) = β·log(π*/π_ref) + β·log Z(x)`。Bradley-Terry 只用到 `r(x,y_w) − r(x,y_l)`，`β·log Z(x)` 只依赖 x，两项相减后消失，于是损失只剩策略参数。

- A 错：偏好学习依然假设存在一个潜在的标量奖励（Bradley-Terry），只是不显式训练它。
- B 错：DPO 只有一个优化循环，隐式奖励是"读出来"的，不是另外训练的。
- D 错：Bradley-Terry 对奖励加一个**只依赖 x 的常数**不变，而不是对任意奖励函数不变——这正是 `Z(x)` 能相消的原因。

### Q2 — 答案：A

`π = π_ref` 时两个 log-ratio 都是 0，margin = `β × (0 − 0) = 0`，损失 `−log σ(0) = −log 0.5 = ln 2 ≈ 0.693`。β 只缩放 margin，margin 为 0 时与 β 无关，所以 D 错。B 混淆了"损失为 0"与"margin 为 0"。这和预训练时"初始 loss ≈ ln V"一样，是 DPO 训练第一步的健全性检查：初始 loss 偏离 0.693 说明参考模型和策略没对齐（比如加载了不同权重或 tokenizer 模板不一致）。

### Q3 — 答案：D

`1/(2β) = 1/(2 × 0.1) = 5.0`。代码中 `target = 1.0 / (2 * beta)` 也是 5。注意这是 **log-ratio 之差**（未乘 β）的目标，单位是 nats。5 nats 意味着 chosen/rejected 相对参考模型的概率比被拉开约 `e⁵ ≈ 148` 倍，这是一个很"激进"的目标——这也部分解释了为什么本代码中 IPO 离参考模型最远（见 Q10）。选项 B（0.2）是 `2β`，C（1.0）是 `β = 0.5` 时的目标。

### Q4 — 答案：B

两个 log-ratio：`h_w = −1.5 − (−1.0) = −0.5`，`h_l = −3.0 − (−1.0) = −2.0`。margin = `β·(h_w − h_l) = β × 1.5`；β = 0.1 时 margin = 0.15，loss 从 0.693 降到 `−log σ(0.15) ≈ 0.621`。DPO 只关心**相对**排序，所以只要 rejected 降得更快，chosen 下降也能让损失下降，这就是讲义说的 Degraded Chosen Response。A 错在把绝对概率和相对 margin 混为一谈；C 正好说反；D 错，IPO 也只约束差值，同样可能出现，但讲义将其列为 DPO 的失效模式、BPO 专门针对它。

### Q5 — 答案：A

KTO 的核心卖点就是**不需要成对数据**：给单条输出一个 desirable/undesirable 标签，用前景理论的价值函数 `σ(β·log(π/π_ref) − z_ref)` 计算效用，对"坏"样本加更大的权重。讲义："you can use unpaired data, which is far more plentiful." DPO、IPO、SimPO 都要求同一 prompt 下的 `(y_w, y_l)` 成对数据。

### Q6 — 答案：D

SimPO：`L = −log σ((β/|y_w|)·log π(y_w) − (β/|y_l|)·log π(y_l) − γ)`。两点关键：①没有 `π_ref`；②按长度归一化，使训练信号与生成时的"平均 token 似然"一致，消除"越长的 y_w 天然有越大 log-prob 差"带来的长度偏置。A 是错误描述（SimPO 恰好去掉了参考策略）；B 是 IPO；C 是 ORPO。

### Q7 — 答案：C

ORPO：`L = L_NLL(y_w) + λ·L_OR`，NLL 项就是 SFT 损失，同时充当正则项，因此不需要参考模型，可以从 base 模型一步训练到对齐模型。DPO、IPO、BPO 都依赖 `π_ref`（通常是 SFT 后的模型），因此需要"先 SFT 再偏好优化"的两阶段流程。SimPO 也不需要参考模型，但通常仍在 SFT 模型上做，不以"单阶段"为卖点。

### Q8 — 答案：B

讲义："The gold-reward-vs-KL curves have the same Gao et al. peak-and-collapse shape. The implicit reward queries out-of-distribution samples during training; KL regularization does not stabilize this." 结论是 DAA 只是把被过度优化的对象从"奖励模型"换成了"相对参考策略的比值"。A、C 都不是讲义的结论；D 恰是讲义和 `outputs/skill-preference-loss-selector.md` 明确列为 hard reject 的说法。

### Q9 — 参考答案

1. 设 `Δ_w = log π(y_w) − log π_ref(y_w)`。代码中 `anchor_pen = −Δ_w`，额外梯度为 `−0.05 · (−Δ_w) · gw = 0.05 · Δ_w · gw`。由于 `∂Δ_w/∂logits = gw`，它正是 `L_extra = 0.025 · Δ_w²` 的梯度。完整损失等价于

   ```
   L_BPO(code) = −log σ(β(Δ_w − Δ_l)) + 0.025 · (log π(y_w) − log π_ref(y_w))²
   ```

2. `Δ_w > 0` 时额外梯度为正，`logits -= lr * grad` 会**降低** `log π(y_w)`，把它拉回参考值。也就是说这一项是**双向**的 L2 锚：chosen 下降时往上拉，上升时也往下拉。注释写 "penalty on decreases"，内联注释写 "push chosen toward/above ref"，讲义写 "penalizes downward moves on the chosen response"——实现只做到了 "toward"，没做到 "above"。在本次运行里 BPO 的 action 1 概率（0.507）明显低于 DPO（0.636），一部分原因就是这个对称锚在阻止 chosen 上升。
3. 单向版本（只在 `Δ_w < 0` 时惩罚）：

   ```python
   pen = min(0.0, log_pi_w - log_ref_w)          # 只保留下降部分
   grad = [beta * g_margin * (gw_i - gl_i) + 0.05 * pen * gw_i
           for gw_i, gl_i in zip(gw, gl)]
   ```

   对应损失 `0.025 · min(0, Δ_w)²`。我们在同一份数据上实际跑了对比（种子 11、2000 步）：双向版 action 1 概率 0.483、chosen 平均 drift −0.012；单向版 0.553、drift −0.043——单向版允许 chosen 往上走，策略更接近 DPO，但仍明显比 DPO（drift −0.155）更"保 chosen"。注意讲义没有给出 BPO 论文的精确公式，代码里的系数 0.05 也是任意选取的，不能把它当作论文的复现。

### Q10 — 参考答案

1. `win_rate(pi)` 返回的是"策略把多少概率放在真实效用最高的动作（action 1）上"，即 `P(action 1)`，**不是**两两对比的胜率。讲义 "Use It" 还说会画出 win rate、chosen-log-prob drift 和 implicit-reward spread，但代码既没有画图，也没有输出后两项。
2. 总体最优满足 `σ(β(h_i − h_j)) = σ(u_i − u_j)`，即 `log π*_i = log π_ref,i + u_i/β + const`。β = 0.1 时 `u/β = [2, 10, −4, −8]`，实际计算得 `π* ≈ [0.0003, 0.9997, 0.0000, 0.0000]`，几乎是确定性策略，与打印的 `true optimum = softmax(u) = [0.241, 0.537, 0.132, 0.089]` 完全不同（后者相当于"β = 1 且参考策略均匀"时的最优）。DPO 跑完 2000 步只到 0.636，因为 DPO 梯度里有 β = 0.1 的因子，有效学习率只有 `0.05 × 0.1 = 0.005`。我们把步数加到 20,000 后，DPO 变为 `[0.001, 0.999, 0.000, 0.000]`，chosen 平均 drift 从 −0.155 变为 −4.40——这正是"小 β 下 DPO 越训越远离参考模型"的过度优化趋势。
3. IPO 的梯度是 `2·(h_w − h_l − 5)·(gw − gl)`，没有 β 因子，而且初始残差高达 −5，单步可以让 logits 移动约 0.5。每步只抽一个样本，偏好对里又有大量"反向"的噪声对（平均偏好强度仅 0.61），于是 SGD 在最优点附近剧烈抖动。实测：同样设置下 IPO 在第 1000–6000 步之间 action 1 概率在 **0.048～0.989** 之间跳动；换随机种子 1/2/3 得到 0.786、0.521、0.804；全批量梯度下降求得的 IPO 最优约为 `[0.120, 0.836, 0.032, 0.012]`。0.943 只是某一时刻的快照。
4. ORPO 的损失由 NLL 主导（λ = 0.1），NLL 的最优解是"chosen 样本的经验分布"。500 对数据里各动作作为 y_w 的频率是 `[0.252, 0.396, 0.208, 0.144]`；ORPO 训练 2000 步后为 `[0.247, 0.364, 0.193, 0.196]`，20,000 步后为 `[0.214, 0.441, 0.190, 0.155]`，正在向这个经验分布（再加一点 odds-ratio 推力）靠拢。这不是"ORPO 差"，而是 ORPO 的设计本来就是"以 SFT 为锚"。

结论：玩具里的横向比较主要反映"有效学习率、步数和目标尺度"的差异，而非方法本身的优劣。公平比较至少要做到：每个方法单独调学习率、多种子平均、训练到收敛或在相同 KL 预算下比较。

### Q11 — 参考答案

1. `odds(y_w) = 0.5/0.5 = 1`，`odds(y_l) = 0.2/0.8 = 0.25`，`log(odds_w/odds_l) = ln 4 ≈ 1.386`，`L_OR = −log σ(1.386) ≈ 0.223`（已用 Python 计算验证）。
2. `∂ log odds(y)/∂ log p = 1 + p/(1−p) = 1/(1−p)`，所以 `∂ log odds(y)/∂ logits = gy/(1−p_y)`。精确梯度应为 `g_or · (gw/(1−p_w) − gl/(1−p_l))`，代码写成 `g_or · (gw − gl)`，漏掉了两个 `1/(1−p)` 因子（代码注释也承认 "simplified"）。在 λ = 0.1 时 NLL 项占主导，我们用精确梯度重跑得到 `[0.297, 0.370, 0.208, 0.125]`，简化版为 `[0.297, 0.370, 0.209, 0.125]`，几乎没有差别；但当 `p_w` 接近 1 时 `1/(1−p_w)` 会很大，精确版的 odds-ratio 推力会明显增强，λ 较大时不能忽略。另外，代码在计算 odds 时加了 `+1e-6`，用于防止 `p = 1` 时除零。

### Q12 — 参考答案

1. 这个玩具里一个"回复"就是一个动作，`log π(y)` 是单个 softmax 概率的对数。长度只是一个人为给定的常数：把它设成 2 或 3 只是把该动作的梯度缩小常数倍，等价于给不同动作配置不同的学习率，并不存在"多一个 token 就多一份负 log-prob"的机制。所以 `lens` 改成任何值都只是重新加权，无法体现"长回复 log-prob 天然更负"这一长度偏置的来源。
2. 最小改造：把回复改成 token 序列，每个 token 从同一个 softmax（或按位置的 softmax）中采样，`log π(y) = Σ_t log π(y_t)`；构造数据时让 rejected 平均长度是 chosen 的 2 倍；DPO 用序列总 log-prob，SimPO 用 `log π(y)/|y|`。然后比较两者训练后"生成长度的期望"和"真正偏好的 token 的概率"。
3. 原始差：`−12 − (−10) = −2`，按总 log-prob 看会偏好 rejected（因为 chosen 更长）。SimPO margin：`1.5 × (−12/6) − 1.5 × (−10/2) − 0.5 = −3 + 7.5 − 0.5 = 4.0`，按平均 token 似然看 chosen（每 token −2）明显好于 rejected（每 token −5），于是 SimPO 偏好 chosen。这说明长度归一化去掉了"长度"这个与质量无关的因素。注意 DPO 用的是相对参考模型的 log-ratio，参考模型的长度效应会部分抵消，但讲义指出 DPO 仍存在长度偏置。

### Q13 — 参考回答要点

- **目标**：`max_π E_{x, y~π}[r(x,y)] − β·KL(π‖π_ref)`。
- **闭式解**：对每个 x，这是带熵正则的"指数族"问题，解为 `π*(y|x) = π_ref(y|x)·exp(r(x,y)/β)/Z(x)`，`Z(x) = Σ_y π_ref(y|x)·exp(r/β)`。
- **反解奖励**：`r(x,y) = β·log(π*(y|x)/π_ref(y|x)) + β·log Z(x)`。
- **代入 Bradley-Terry**：`P(y_w ≻ y_l | x) = σ(r(x,y_w) − r(x,y_l))`，`β·log Z(x)` 相消，用参数化的 `π_θ` 替换 `π*`，取负对数似然得 `L_DPO = −E log σ(β·log(π_θ(y_w)/π_ref(y_w)) − β·log(π_θ(y_l)/π_ref(y_l)))`。
- **依赖的假设**（讲义 "The wrinkle"）：最优解可达（模型容量足够、能优化到）；偏好数据是分布内的；参考策略是真正的锚点；此外还有偏好服从 Bradley-Terry 这一建模假设。每个家族成员修复的正是某个被违反的假设。
- 加分点：说明梯度 `∝ β·σ(−margin)·(∇log π(y_w) − ∇log π(y_l))`，即"排错的样本权重更大"；初始损失为 ln 2。

### Q14 — 参考回答要点

- **为什么一起降**：DPO 损失只依赖 `h_w − h_l`。在共享参数的大模型里，chosen 与 rejected 往往高度相似（共享大量 token），压低 rejected 的梯度会"顺带"压低 chosen；只要 rejected 降得更快，损失就继续下降。讲义称之为 Degraded Chosen Response。在本节玩具里也能看到：DPO 训练 2000 步后 chosen 的平均 log-ratio 为 −0.155，训练 20,000 步后为 −4.40（rejected 为 −8.06）。
- **危害**：概率质量被挤到既不是 chosen 也不是 rejected 的地方（可能是分布外的、未被评估过的输出）；生成质量和事实性下降；隐式奖励"看起来很好"但真实质量下降，属于过度优化的一种表现。
- **缓解**：
  - IPO：把 margin 拉向有界目标 `1/(2β)` 而不是推向无穷，减少"无止境地压 rejected"；
  - BPO：直接对 chosen 的绝对 log-prob 下降加惩罚（讲义描述）；
  - ORPO / 加 SFT 项：NLL 项直接把 chosen 的概率往上拉；
  - 工程手段：更大的 β、早停、监控 chosen log-prob。
- 常见误区：只看 reward accuracy（margin > 0 的比例）或 loss 判断训练正常。

### Q15 — 参考回答要点

- **选损失**：20 万条成对数据、两阶段流程 → DPO 作为基线，β 从保守值起扫（如 0.1 附近做 sweep）；检查数据长度比，若 `|y_w|/|y_l|` 明显偏离 1（skill 文件给的阈值是 1.5）就加 SimPO 对照；若偏好强度差异很大、DPO 出现饱和，加 IPO 对照；若 chosen log-prob 下降，加 BPO 或 SFT 项。讲义："Every lab runs all five on a battery and picks the winner per task."
- **超参**：β、学习率（通常比 SFT 小一个量级）、epoch 数（偏好数据多轮训练容易过拟合）、SimPO 的 γ、ORPO 的 λ——都只是 sweep 的起点。
- **监控指标**：
  - chosen / rejected 的 log-prob 及其各自相对参考模型的变化（是否双双下降）；
  - 隐式奖励 margin 的分布（是否无限增大）、reward accuracy；
  - 与参考模型的 KL；
  - 生成长度；
  - **留出的 gold 评估**：人工或强模型评估的胜率、能力基准（数学、代码、知识）是否回退。
- **过度优化的信号**：KL 持续增大而 gold 胜率先升后降；margin 继续变大但留出集评估不再提升；输出变长、变啰嗦。对策：早停、取 KL 适中的 checkpoint、增大 β、扩充/清洗数据。

### Q16 — 参考回答要点

- 不成立。讲义："DAAs do not escape Goodhart. They change the surface where it bites from 'reward model over-optimized' to 'reference policy ratio over-optimized.'"
- 证据：Rafailov et al.（NeurIPS 2024）在多个数据集和 KL 预算下训练 DPO、IPO、SLiC，gold reward–KL 曲线与显式 RM 的 RLHF 一样先升后降。
- 机制：DPO 的隐式奖励 `β·log(π/π_ref)` 本身就是一个由有限偏好数据拟合出的代理；训练过程中策略会把概率移到偏好数据没覆盖到的区域，这些区域的隐式奖励没有约束，可以任意大。
- 补充：偏好数据本身的偏差（如标注者偏好更长、更迎合的回答，见第 04 节）会被 DPO 同样学到并放大。
- 对策与 RLHF 相同：更好的数据、集成/多评估器、早停、保留 gold 评估。

### Q17 — 参考回答要点

- **阶段 1：SFT**：用人工改写的高质量回复做 SFT，得到参考模型 `π_ref`。（如果想省掉单独的 SFT 阶段，也可以考虑 ORPO：把改写回复与对应的差回复组成成对数据，一步完成 SFT + 偏好。）
- **阶段 2：成对偏好**：用专家成对偏好做 DPO（或在长度偏置明显时用 SimPO）；专家数据量小、信号干净，β 取得保守一些，避免过拟合。
- **阶段 3：非成对反馈**：大量点赞/点踩用 KTO，它天然处理单条二值标签；注意用户反馈有选择偏差和迎合偏差（用户更喜欢被认同），需要先过滤或降权，并单独监控迎合行为（第 04 节）。
- **评估**：每个阶段后都跑留出的 gold 评估（专家盲评 + 能力回归），而不是只看训练损失或用户点赞率。
- 加分点：说明阶段顺序可以调整，也可以把 DPO 与 KTO 的数据混合训练；任何选择都要以留出评估为准，讲义明确"没有对所有任务都最优的方法"。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 01 将指令遵循作为 Alignment 信号](../../01-instruction-following-alignment-signal/docs/zh.md)：InstructGPT 的 SFT → RM → PPO 流程，以及本节推导所用的 RLHF-with-KL 目标。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../02-reward-hacking-goodhart/docs/zh.md)：Gao et al. 的过度优化曲线，理解"DAA 仍会过度优化"。
- [阶段 10 · 08 DPO：直接偏好优化](../../../10-llms-from-scratch/08-dpo/docs/zh.md)：DPO 的基础实现。
- [阶段 10 · 07 RLHF: Reward Model + PPO](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)、[阶段 09 · 09 奖励建模 & RLHF](../../../09-reinforcement-learning/09-reward-modeling-rlhf/docs/zh.md)：Bradley-Terry 奖励模型与 KL 正则。

### 本节被哪些后续内容用到
- [阶段 18 · 04 RLHF 对迎合行为的放大效应](../../04-sycophancy-rlhf-amplification/docs/zh.md)：讲义指出 DPO、PPO-with-KL、best-of-N 都按 `exp(r)` 加权，同样会放大迎合。
- [阶段 18 · 05 Constitutional AI 与 RLAIF](../../05-constitutional-ai-rlaif/docs/zh.md)：偏好信号可以来自 AI 标注者，DPO 家族同样适用。
- [阶段 18 · 11 可扩展监督与弱到强泛化](../../11-scalable-oversight-weak-to-strong/docs/zh.md)：当偏好标注者比模型弱时如何获得可靠信号。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：工程上通常用 LoRA 做 DPO 类训练。

### 延伸关键词
`Bradley-Terry` · `implicit reward` · `likelihood displacement` · `IPO` · `KTO` · `SimPO` · `ORPO` · `SLiC` · `length bias` · `reward over-optimization` · `KL budget` · `online / iterative DPO`
