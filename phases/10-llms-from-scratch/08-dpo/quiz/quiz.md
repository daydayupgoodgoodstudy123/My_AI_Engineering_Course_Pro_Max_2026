# 测验 · DPO：直接偏好优化（DPO: Direct Preference Optimization）

> **阶段 10 · 从零构建 LLM · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | RLHF 目标的闭式解 | `max E[R] − β·KL(π‖π_ref)` 的最优策略为 `π*(y|x) = π_ref(y|x)·exp(R(x,y)/β) / Z(x)` |
| 2 | 隐式奖励 | 反解得 `R(x,y) = β·log(π*(y|x)/π_ref(y|x)) + β·log Z(x)`：奖励藏在策略与参考模型的概率比里 |
| 3 | Z(x) 为何消失 | 代入 Bradley-Terry 后，chosen 与 rejected 共享同一个 prompt x，`β log Z(x)` 在差值中相互抵消 |
| 4 | DPO 损失 | `L = −log σ(β·[(log π(y_w) − log π_ref(y_w)) − (log π(y_l) − log π_ref(y_l))])`；初始时 π = π_ref，loss = ln 2 |
| 5 | DPO 梯度 | `∇L = −β·σ(−logit)·[∇log π(y_w) − ∇log π(y_l)]`：隐式奖励排错得越厉害，权重越大 |
| 6 | β 的含义 | 对应 RLHF 的 KL 系数：β 小 → 允许大幅偏离参考模型；β 大 → 贴近参考；讲义常用 0.1–0.5 |
| 7 | 序列 log 概率 | 对 `prompt + response` 前向一次，只对回复 token 的 log 概率**求和**；每对样本需 4 次前向（2 模型 × 2 回复） |
| 8 | 与 RLHF 的对比 | 显存中 2 个模型（策略 + 冻结参考）vs PPO 的 3–4 个；无 RM、无采样、像监督学习一样稳定；但它是**离线**的 |
| 9 | 家族方法 | KTO（非成对好/坏标签）、ORPO（SFT 与偏好合一、无参考）、SimPO（长度归一化平均 log 概率作奖励、无参考） |
| 10 | 实际部署 | 讲义：Zephyr-7B（Mistral 7B → UltraChat SFT → UltraFeedback DPO）、Llama 3 的对齐流程中使用了 DPO |

### 核心技能（能动手做到）

- [ ] 从 RLHF 目标出发推导 DPO 损失，说清 `Z(x)` 为何抵消
- [ ] 手算 DPO 损失、隐式奖励与 margin，并判断梯度方向
- [ ] 正确实现"只对回复 token 求和"的序列 log 概率，处理好错位与截断
- [ ] 读懂本节 `dpo_train`，指出它的更新是随机噪声，并写出正确的梯度
- [ ] 识别本节评估中"平局记为错误""噪声级 margin 决定准确率"等问题
- [ ] 写出 KTO、SimPO、长度归一化 DPO 的损失，并比较它们需要的数据与模型

---

## 二、基础自测（选择题）

**Q1.** 在 DPO 推导中，隐式奖励 `R(x,y) = β·log(π(y|x)/π_ref(y|x)) + β·log Z(x)` 里的配分函数 `Z(x)` 很难计算。DPO 损失中它是怎么消失的？

- A. 假设 `Z(x) = 1`，直接忽略
- B. Bradley-Terry 只用两个回复奖励的差值，二者对应同一个 prompt x，`β·log Z(x)` 相减抵消
- C. 用蒙特卡洛采样估计 `Z(x)` 后代入
- D. `Z(x)` 被吸收进了学习率

**Q2.** DPO 训练开始时，策略模型与参考模型权重完全相同。此时任意一对样本的 DPO 损失等于：

- A. 0
- B. 1.0
- C. 0.5
- D. ln 2 ≈ 0.693

**Q3.** β = 0.1。某对样本中，策略模型对 chosen / rejected 的序列 log 概率为 −9 / −13，参考模型为 −10 / −12。DPO 损失约为：

- A. 0.598
- B. 0.693
- C. 0.798
- D. 0.127

**Q4.** 关于 DPO 中的 β，正确的说法是：

- A. β 是学习率的别名
- B. β 越大，策略越容易偏离参考模型
- C. β 对应 RLHF 目标里的 KL 系数：β 越大，对偏离参考模型的约束越强
- D. β 只影响评估，不影响训练

**Q5.** DPO 训练时 GPU 上需要同时保留的模型是：

- A. 策略、参考、奖励模型
- B. 只有策略模型
- C. 策略、奖励、价值模型
- D. 策略模型与冻结的参考模型

**Q6.** 你的产品只收集到了用户对单条回复的"赞 / 踩"，没有成对比较。讲义介绍的方法中最直接适用的是：

- A. KTO
- B. DPO
- C. SimPO
- D. ORPO

**Q7.** 关于 DPO 与 PPO 式 RLHF 的区别，正确的是：

- A. DPO 需要先训练奖励模型，再用它给偏好对打标签
- B. DPO 需要在训练中不断从当前策略采样新回复
- C. DPO 在固定的离线偏好数据上训练，不会利用当前策略新生成的样本；PPO 是在线的
- D. DPO 训练比 SFT 还多一个价值模型

**Q8.** 运行本节代码：训练 5 个 epoch，loss 始终是 0.6931、margin 始终是 0.0000；"pre-DPO 准确率"为 0.0%，"post-DPO"为 33.3%；β 扫描中 β = 0.3 的准确率为 100%。最准确的解释是：

- A. DPO 在小数据上无法学习，只有 β = 0.3 有效
- B. 策略更新只是 1e-7 量级的随机噪声，margin 只有约 1e-5；初始时策略与参考完全相同，奖励相等被记为"错误"，所以是 0%；之后的准确率只是噪声符号的随机结果
- C. 学习率 5e-6 太小，换成 5e-5 就会收敛
- D. 序列 log 概率计算错误，导致所有 margin 恒为 0

---

## 三、动手 / 代码题

**Q9.** 阅读 `compute_sequence_log_prob`：

```python
def compute_sequence_log_prob(model, prompt_tokens, response_tokens, max_seq_len=128):
    full_sequence = prompt_tokens + response_tokens
    if len(full_sequence) > max_seq_len:
        full_sequence = full_sequence[:max_seq_len]
    ...
    input_ids = np.array(full_sequence[:-1]).reshape(1, -1)
    target_ids = np.array(full_sequence[1:])
    ...
    prompt_len = len(prompt_tokens)
    response_start = max(0, prompt_len - 1)
    response_end = len(target_ids)
    ...
    response_log_probs = log_probs[response_start:response_end, :]
    response_targets = target_ids[response_start:response_end]
```

1. 以 `prompt = "What is 15 times 7?"`（19 字节）、`preferred = "15 times 7 is 105."`（18 字节）为例：`input_ids` 有多少个 token？`response_start` 是多少？第一个被累加的是哪个目标 token、由哪个输入位置预测？一共累加了多少项？
2. 为什么起点是 `prompt_len − 1` 而不是 `prompt_len`？
3. 6 对数据中，有多少条序列因超过 128 被截断？例如 "What year did World War II end?" 的 rejected（123 字节）实际只计入了多少个回复 token？这对 DPO 有什么影响？
4. 这里的 prompt 和 response 之间没有任何分隔符或模板，会有什么问题？

**Q10.** 阅读 `dpo_train` 的更新：

```python
            loss, metrics = dpo_loss(pi_logprob_w, pi_logprob_l, ref_logprob_w, ref_logprob_l, beta)

            update_direction = 1.0 if metrics["logit"] < 0 else -0.1
            for block in policy_model.blocks:
                block.ffn.W1 += lr * update_direction * np.random.randn(*block.ffn.W1.shape) * 0.01
                block.ffn.W2 += lr * update_direction * np.random.randn(*block.ffn.W2.shape) * 0.01
```

1. 这个更新的期望方向是什么？`update_direction` 的正负号起作用吗？
2. 写出 DPO 损失对 `log π(y_w)`、`log π(y_l)` 的偏导数，以及 `log π(y)` 对回复位置 logits 的梯度。
3. 我们只对输出头（`token_embed`，weight tying）实现了正确的 DPO 梯度，lr = 0.05、β = 0.1、训练 15 个 epoch：平均 loss 从第 1 个 epoch 的 0.354 降到 0.0035，训练集准确率 6/6；但最后一个 epoch 中 chosen 的平均 log 比率是 −24.2、rejected 是 −87.0。chosen 的概率为什么也下降了？这说明了 DPO 的什么特性？

**Q11.** 关于本节的评估：

```python
    pre_accuracy = evaluate_preference_accuracy(sft_model, reference_model, PREFERENCE_DATA, beta=0.1)
    ...
        if preferred_reward > rejected_reward:
            correct += 1
```

1. 为什么 pre-DPO 准确率恰好是 0.0%？合理的"训练前基线"应该是多少？
2. β 扫描输出了 66.7%、33.3%、100%、83.3% 四个准确率，讲义据此讨论"β 的最佳区间"。这些数字能支持任何结论吗？
3. 列出一个可信的 DPO 评估方案应包含的指标。

**Q12.** 讲义练习 2 与 SimPO 都涉及长度归一化。

1. SimPO 的隐式奖励为 `r(y) = (β/|y|)·log π(y|x)`，损失为 `−log σ(r(y_w) − r(y_l) − γ)`。用本节随机初始化模型在第一对数据上的实测值计算：chosen 31 个 token，`log π = −175.28`；rejected 98 个 token，`log π = −553.32`；取 β = 2.0、γ = 0.5。
2. 如果去掉参考模型、又**不做**长度归一化（直接用 `β·log π(y)` 作奖励，β = 0.1），同样两条回复的 margin 是多少？会导致什么问题？
3. 为什么标准 DPO 有参考模型时，"总 log 概率随长度变小"的问题在初始时并不出现？DPO 训练后又可能出现什么长度相关的偏差？

---

## 四、面试高频题

**Q13.**（基础必考）请从 RLHF 的优化目标出发，推导 DPO 的损失函数，并解释"Your Language Model is Secretly a Reward Model"这句话。

**Q14.**（原理深挖）分析 DPO 的梯度。它和直接"提高 chosen 似然、降低 rejected 似然"（unlikelihood）有什么本质区别？为什么训练中 chosen 的似然有时也会下降？

**Q15.**（工程实践）你要用 DPO 对齐一个 7B 的 SFT 模型。请给出数据准备、超参数、训练监控与评估方案。

**Q16.**（场景设计）对比 RLHF（PPO）、DPO、KTO、ORPO、SimPO，在下面三种情况下分别选哪个？(a) 只有用户点赞点踩日志；(b) 显存只够放一个 7B 模型；(c) 需要在线、多目标地持续优化一个大模型。

**Q17.**（追问型）DPO 有哪些已知缺陷？业界如何改进（如 iterative / online DPO）？

---

## 五、参考答案与解析

### Q1 — 答案：B

`P(y_w ≻ y_l) = σ(R(x,y_w) − R(x,y_l))`，两项的 `β·log Z(x)` 完全相同，相减为 0。讲义："The Z(x) terms cancel because both responses condition on the same prompt x." A 是错误的假设（`Z(x)` 一般不为 1）；C 是不必要的；D 毫无依据。

### Q2 — 答案：D

π = π_ref 时两个 log 比率都是 0，`logit = 0`，`−log σ(0) = ln 2 ≈ 0.6931`。本节运行中 loss 始终是 0.6931，恰恰说明策略几乎没有离开参考模型（见 Q8、Q10）。

### Q3 — 答案：A

chosen 比率 `−9 − (−10) = +1`，rejected 比率 `−13 − (−12) = −1`，`logit = 0.1 × (1 − (−1)) = 0.2`，`loss = −log σ(0.2) ≈ 0.598`（已用代码 `dpo_loss(-9, -13, -10, -12, beta=0.1)` 验证，隐式奖励分别为 +0.1 / −0.1，margin 0.2）。C（0.798）是比率方向相反（logit = −0.2）时的 loss；B 是 logit = 0 时的值。

### Q4 — 答案：C

β 来自 RLHF 目标中的 `β·KL`。讲义："small beta means large deviations are allowed, large beta keeps the model close to the reference." B 说反了；A 错，学习率是另一个超参数；D 错，β 直接决定 logit 的尺度和梯度权重。

### Q5 — 答案：D

DPO 需要冻结参考模型来计算 `log π_ref`（也可以预先算好缓存下来，此时训练中只需策略模型）。A、C 是 PPO 式 RLHF 的配置；B 是 SimPO / ORPO 这类无参考方法。

### Q6 — 答案：A

KTO 只需要每条回复的"好 / 坏"标签（讲义："KTO works with unpaired feedback"）。DPO、SimPO、ORPO 都需要成对的 chosen / rejected。

### Q7 — 答案：C

DPO 是离线算法：偏好对在训练前就固定了，训练中不生成新回复。这正是讲义"When RLHF Beats DPO"中"Iterative alignment"一条的含义。A 错：DPO 不需要奖励模型；B 描述的是 PPO；D 错：DPO 没有价值模型。

### Q8 — 答案：B

已实际验证：5 个 epoch 内 `|margin|` 最大只有约 1.0e-5，策略 `W1` 的最大变化约 7e-7。初始时 `sft_model` 与 `reference_model` 完全相同，隐式奖励都是 0，`0 > 0` 为假，6 对全判错 → 0.0%。训练后的 margin 是 ±1e-5 的噪声，正负号决定了 33.3%、66.7%、100%、83.3% 这些"准确率"，与 β 毫无关系。C 错：问题不在步长，而在根本没有梯度；D 错：log 概率计算本身是对的（见 Q9），margin 为 0 是因为两个模型几乎一样。

### Q9 — 参考答案

1. `full_sequence` 长 `19 + 18 = 37`；`input_ids = full_sequence[:-1]` 有 **36** 个 token；`target_ids` 也是 36 个。`response_start = 19 − 1 = 18`，`response_end = 36`。第一个被累加的是 `target_ids[18] = full_sequence[19]`，即回复的第一个字节 `'1'`，由输入位置 18（prompt 最后一个字节 `'?'`）预测。共累加 `36 − 18 = 18` 项，正好是回复的 18 个 token。
2. 因为错位一位：位置 i 的 logits 预测的是 `full_sequence[i+1]`。回复第一个 token 位于 `full_sequence[prompt_len]`，它由位置 `prompt_len − 1` 预测，所以切片从 `prompt_len − 1` 开始。写成 `prompt_len` 会漏掉回复的第一个 token。
3. **6 条**被截断（已用代码验证）：第 1、3、4、5 对的 rejected，以及第 6 对的两条。"World War II" 的 rejected 只计入 `128 − 31 = 97` 个回复 token（原 123 个），丢掉了结尾 "specifically in 1945." 这部分。影响：DPO 比较的是"被截断的 rejected"与"完整的 chosen"，而截断恰恰发生在长回复上——这与"rejected 更啰嗦"的偏好方向混在一起，模型学到的信号被扭曲。生产中通常优先截断 prompt、或丢弃超长样本，并保证 chosen 与 rejected 用同样的规则处理。
4. 没有分隔符或 chat template：模型无法区分 prompt 在哪里结束、回复从哪里开始（"What is 15 times 7?15 times 7 is 105."），与 SFT 阶段的格式也不一致。DPO 的 log 概率必须在与 SFT / 推理**完全相同的模板**下计算，否则优化的是一个模型在推理时永远不会遇到的条件分布。

### Q10 — 参考答案

1. 更新量 = `lr × (+1.0 或 −0.1) × 0.01 × N(0, I)`。`N(0, I)` 关于 0 对称，乘以正数或负数分布不变，所以无论 `update_direction` 取什么，**期望更新都是 0**，正负号只改变噪声幅度（1.0 vs 0.1）。这不是梯度下降，DPO 损失没有对参数产生任何影响。
2. 记 `logit = β[(ℓ_w − ℓ_w^ref) − (ℓ_l − ℓ_l^ref)]`，`ℓ = log π(y|x)`：

   ```text
   ∂L/∂ℓ_w = −β·σ(−logit)
   ∂L/∂ℓ_l = +β·σ(−logit)
   ∂ℓ/∂z_t = onehot(y_t) − softmax(z_t)     （z_t 为回复第 t 个位置的 logits，只对回复位置非零）
   ```

   再由 `logits = h @ Eᵀ` 链式求得 `E` 的梯度 `Σ_t (∂L/∂z_t)ᵀ h_t`，或交给 autograd 反传到全部参数。
3. DPO 只约束**差值** `(ℓ_w − ℓ_w^ref) − (ℓ_l − ℓ_l^ref)` 变大，并不要求 `ℓ_w` 本身上升。把 rejected 的概率压低往往比提高 chosen 更"便宜"，尤其当 chosen 与 rejected 共享大量 token（本数据都以相同 prompt 开头、常含相同短语）时，压低共享模式会同时拉低两者。我们的实验中 rejected 下降得更多（−87.0 vs −24.2），margin 变大、loss 趋近 0，但 chosen 的绝对似然也下降了——这就是常说的"DPO 会降低 chosen 似然 / 似然偏移"现象。β 越大越不明显（同一实验 β = 0.5 时 chosen 只降到 −4.5）。缓解：增大 β、加入 chosen 上的 SFT 项（讲义练习 3 的 ORPO 式组合损失），或使用对此做了约束的变体。

### Q11 — 参考答案

1. 训练前策略与参考完全相同，所有隐式奖励都是 0；`preferred_reward > rejected_reward` 用严格大于，平局全部记为错，所以是 0.0%。合理的基线是"平局"（隐式奖励在训练前本来就没有区分能力）：应单独统计平局，或者把基线定义为随机猜测的 50%。
2. 不能。四次实验的 margin 都在 1e-5 量级，loss 都是 0.6931，准确率只取决于随机噪声的符号；而且训练集只有 6 对，一对翻转就是 16.7 个百分点。讲义"小 β 学得快但可能退化、大 β 稳定但慢"的结论本身没错，但本代码的输出不能作为证据。
3. 可信的评估方案：
   - **held-out 偏好集**上的隐式奖励准确率与 margin 分布（`rewards/accuracies`、`rewards/margins`）；
   - 训练中分别跟踪 chosen 与 rejected 的 log 比率（检测 Q10 的似然下降）；
   - 与参考模型的 KL（或 log 比率均值），确认没有跑太远；
   - **生成式评估**：在新 prompt 上生成回复，用人工或强模型做胜率对比（如 MT-Bench、AlpacaEval 一类）；
   - 回复长度统计（DPO 容易让回复变长）；
   - 通用能力回归测试；多个随机种子、报告方差。

### Q12 — 参考答案

1. （已用 Python 计算）`r_w = 2.0 × (−175.28 / 31) ≈ −11.308`，`r_l = 2.0 × (−553.32 / 98) ≈ −11.292`，`r_w − r_l − γ ≈ −0.016 − 0.5 = −0.516`，`loss = −log σ(−0.516) ≈ 0.984`。随机模型下每个 token 的平均 log 概率都约为 `−ln 256 ≈ −5.6`，所以长度归一化后两条回复的奖励几乎相同——这是合理的"无偏好"起点；γ 要求 chosen 至少领先一个 margin，所以初始 loss 高于 ln 2。
2. `margin = 0.1 × (−175.28 − (−553.32)) ≈ 37.8`，`loss ≈ 0`。模型"什么都没学"就已经 100% 偏好 chosen，仅仅因为它短——总 log 概率随长度线性下降。在这样的奖励下，优化会推着模型生成越来越短的回复，这正是无参考方法必须做长度归一化的原因。讲义练习 2 所说"总 log 概率会偏向较短回复"指的就是这种情况。
3. 有参考模型时，DPO 用的是 `log π − log π_ref`：长度带来的"总 log 概率更低"在两个模型中同样存在，初始时完全抵消（本节 margin 恰为 0）。但训练后，DPO 的奖励是逐 token 比率之和，长回复有更多 token 可以积累比率，实践中常观察到 DPO 模型回复**变长**（长度利用）。所以 SimPO 等方法用长度归一化 + margin γ 来控制，评估时也要报告长度。（顺带：本节 `outputs/` 提示词把 SimPO 的 γ 写成"长度归一化指数"，实际上 γ 是目标奖励 margin。）

### Q13 — 参考回答要点

- **起点**：`max_π E_{x,y~π}[R(x,y)] − β·KL(π(·|x) ‖ π_ref(·|x))`。
- **闭式解**：对每个 x 这是带 KL 正则的分布优化，最优解为 Gibbs 分布 `π*(y|x) = π_ref(y|x)·exp(R(x,y)/β) / Z(x)`，`Z(x) = Σ_y π_ref(y|x)·exp(R/β)`。
- **反解奖励**：`R(x,y) = β·log(π*(y|x)/π_ref(y|x)) + β·log Z(x)`。
- **代入 BT**：`P(y_w ≻ y_l) = σ(R_w − R_l)`，`Z(x)` 抵消，得到只含策略与参考模型 log 概率的表达式。
- **最大似然**：在偏好数据上最小化 `−log P`，即 DPO 损失。
- **"Secretly a Reward Model"**：任何语言模型 π 与参考 π_ref 一起，都隐式定义了一个奖励 `β·log(π/π_ref)`；训练 π 就等价于训练这个奖励模型，同时它又恰好是该奖励下的最优策略，所以不需要单独的 RM 和 RL。
- 加分点：说明推导假设了"最优策略可以被参数化模型表示"、偏好服从 BT 模型；以及 DPO 与 RLHF 优化的是同一个目标，但只在偏好数据的支撑集上进行。

### Q14 — 参考回答要点

- **梯度**：`∇L = −β·σ(r̂_l − r̂_w)·[∇log π(y_w) − ∇log π(y_l)]`，其中 `r̂ = β·log(π/π_ref)`。
- **与 unlikelihood 的区别**：
  - 有一个**自适应权重** `σ(r̂_l − r̂_w)`：隐式奖励排错（rejected 得分更高）时权重接近 1，已经排对且 margin 很大时权重趋近 0，自动停止推动，避免像朴素 unlikelihood 那样无限压低 rejected 而导致退化；
  - 以 π_ref 为锚：衡量的是相对参考模型的变化，而不是绝对概率。
- **chosen 似然下降的原因**：损失只约束差值；chosen 与 rejected 往往共享大量 token 和前缀，压低共享部分同时影响两者；在 softmax 下把概率质量从 rejected 挪开，也可能挪到两者之外的序列上。本节实验中 chosen 的 log 比率降到 −24.2（见 Q10）。
- 加分点：缓解手段包括更大的 β、在 chosen 上加 SFT / NLL 项、使用 IPO 等对 margin 做正则化的变体（避免偏好确定时 logit 被推向无穷）。

### Q15 — 参考回答要点

- **数据**：
  - 偏好对最好是**当前 SFT 模型自己生成**的回复（on-policy 或接近），由人工或强模型评判；混用其他模型生成的数据会造成分布偏移；
  - 平衡 chosen / rejected 的长度，避免长度捷径；去重、去污染；
  - 统一使用 SFT 时的 chat template。
- **超参数**：β 0.1–0.5（`outputs/` 建议扫描 0.05、0.1、0.2、0.5）；学习率比 SFT 更低（约 5e-7 – 5e-6 量级，配 AdamW）；1–3 个 epoch；有效 batch 32–128 对；参考模型 = 冻结的 SFT 检查点，log 概率可预先计算缓存。
- **监控**：loss、隐式奖励准确率与 margin、chosen / rejected log 比率分别的曲线、与参考的 KL、生成长度。
- **评估**：held-out 偏好准确率 + 生成式胜率评估 + 通用能力回归 + 安全评测。
- **工程**：7B 全参数 DPO 需要策略的训练状态 + 参考模型的推理权重（第 05 节显存账本）；显存不足时可用 LoRA，并把参考模型实现为"关闭 adapter 的同一模型"。

### Q16 — 参考回答要点

- **(a) 只有点赞 / 点踩**：KTO——天然支持非成对的二元反馈；注意好 / 坏样本比例的平衡（`outputs/` 建议 40%–60%）。也可以把同一 prompt 下的赞、踩回复配成对后用 DPO，但会丢掉大量无法配对的数据。
- **(b) 显存只够一个 7B 模型**：SimPO 或 ORPO（无需参考模型）；或者 DPO + 预先离线算好参考 log 概率；或 DPO + LoRA（参考模型 = 关闭 adapter）。
- **(c) 在线、多目标、持续优化大模型**：PPO 式 RLHF（或 GRPO 一类在线 RL）+ 多个 RM / 多目标奖励；讲义："RLHF pipelines can generate new responses with the current policy, have humans rate them, and retrain the reward model in an online loop." 也可以用 iterative / online DPO 作为折中。
- 加分点：讲义总结的趋势——每种新方法去掉一个复杂部件（RM 与 PPO → 成对数据 → 单独的 SFT 阶段 → 参考模型）。

### Q17 — 参考回答要点

- **已知缺陷**：
  - 离线：只在固定数据上学，无法探索、无法从自己的新错误中学习；数据与当前策略分布不一致时效果下降；
  - chosen 似然下降、长度利用（回复变长）；
  - 偏好接近确定（P ≈ 1）时，BT 损失会把 logit 推向无穷，过度偏离参考（IPO 等工作针对此点）；
  - 对 β 和数据质量敏感；隐式奖励不适合作为通用打分器。
- **改进**：
  - **Iterative / online DPO**：每轮用当前策略生成新回复，再由人或 RM / LLM 评判形成新偏好对（讲义练习 4）；
  - 在 chosen 上加 SFT 项（ORPO、练习 3）、长度归一化（SimPO、练习 2）；
  - 参考模型的选择（练习 5：base、早期检查点、EMA）。
- **工业实践**：讲义——Llama 3 的对齐流程使用了 DPO；常见组合是 SFT → 拒绝采样 / RM 打分构造偏好对 → DPO，多轮迭代。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 07 RLHF: Reward Model + PPO](../../07-rlhf/docs/zh.md)：DPO 的推导起点就是那里的 RLHF 目标与 Bradley-Terry 模型。
- [阶段 10 · 06 指令微调（SFT）](../../06-instruction-tuning-sft/docs/zh.md)：DPO 的策略与参考模型都来自 SFT 检查点。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：KL 散度与 Gibbs 分布形式的最优解。
- [阶段 09 · 09 奖励建模 & RLHF](../../../09-reinforcement-learning/09-reward-modeling-rlhf/docs/zh.md)：从强化学习视角理解偏好学习。

### 本节被哪些后续内容用到
- [阶段 10 · 09 Constitutional AI 与自我改进](../../09-constitutional-ai-self-improvement/docs/zh.md)：用 AI 反馈构造偏好对，再用 DPO / RL 训练。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../10-evaluation/docs/zh.md)：对齐后模型的评估方法。
- [阶段 18 · 03 直接偏好优化方法家族](../../../18-ethics-safety-alignment/03-direct-preference-optimization-family/docs/zh.md)：IPO、KTO、SimPO 等变体的系统梳理。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：DPO 中的长度利用同样是一种投机。
- [阶段 19 · 40 从零实现直接偏好优化](../../../19-capstone-projects/40-dpo-from-scratch/docs/zh.md)、[阶段 19 · 07 端到端 Fine-Tuning 流程](../../../19-capstone-projects/07-end-to-end-fine-tuning-pipeline/docs/zh.md)：综合项目中用 autograd 完整实现 DPO。

### 延伸关键词
`implicit reward` · `Bradley-Terry` · `partition function Z(x)` · `reference model` · `β sweep` · `chosen likelihood displacement` · `length exploitation` · `IPO` · `KTO` · `ORPO` · `SimPO` · `iterative / online DPO` · `UltraFeedback` · `TRL DPOTrainer`
