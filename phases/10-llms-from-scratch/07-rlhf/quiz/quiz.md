# 测验 · RLHF：奖励模型 + PPO（RLHF: Reward Model + PPO）

> **阶段 10 · 从零构建 LLM · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | SFT 的盲区 | SFT 把每条示范都当作"同样好"，无法表达"A 比 B 好"；RLHF 用偏好信号补上这一点 |
| 2 | 三阶段流水线 | SFT → 奖励模型（RM）→ PPO；PPO 阶段从 SFT 初始化策略，并冻结一份 SFT 作为参考模型 |
| 3 | 奖励模型结构 | 把 LM 头换成标量头；取**最后一个 token** 的隐藏状态投影成一个分数（因果注意力下它看过整条序列） |
| 4 | Bradley-Terry 损失 | `P(A ≻ B) = σ(r_A − r_B)`，`loss = −log σ(r_chosen − r_rejected)`；两者相等时 loss = ln 2 ≈ 0.693 |
| 5 | 为什么用成对比较 | 人不擅长给绝对分（7.3 还是 7.5？），但擅长比较；BT 模型把相对比较转成一致的标量分数 |
| 6 | RLHF 目标 | `max E[R(x, y)] − β · KL(π ‖ π_ref)`；讲义：InstructGPT 的 β = 0.02 |
| 7 | PPO 裁剪 | `ratio = π_new / π_old`，`loss = −min(ratio·A, clip(ratio, 1−ε, 1+ε)·A)`，ε 常取 0.2；限制单次更新幅度 |
| 8 | 优势函数 | `A = reward − baseline`；高于平均的回复概率被提高、低于平均的被压低 |
| 9 | Reward hacking | 策略利用 RM 的盲区：啰嗦、谄媚、含糊其辞、格式堆砌；缓解：更强 KL、对抗样本、多 RM |
| 10 | 规模参照 | 讲义：InstructGPT 33K 对比、6B RM、β 0.02；Llama 2 Chat 约 1M 对比、70B RM；RM 准确率约 72%，标注者一致率约 73% |

### 核心技能（能动手做到）

- [ ] 手算 Bradley-Terry 损失与偏好概率，并推导它对奖励头的梯度 `(σ(Δ) − 1)(h_chosen − h_rejected)`
- [ ] 手算 PPO 裁剪目标在 A > 0 / A < 0、ratio 在区间内外四种情况下的取值与是否有梯度
- [ ] 计算两个离散分布之间的 KL，并说明 RLHF 中 KL 通常按 token 计算、只在回复部分计算
- [ ] 读懂本节代码，指出 RM 梯度错误、PPO 只是随机噪声、输入格式不一致、截断等问题
- [ ] 列出 PPO 阶段同时需要的模型（策略、参考、奖励、价值）并估算显存压力
- [ ] 设计偏好数据采集与 RM 评估方案，识别长度等混杂偏差

---

## 二、基础自测（选择题）

**Q1.** 在 Bradley-Terry 模型中，回复 A 优于回复 B 的概率是：

- A. `r_A / (r_A + r_B)`
- B. `softmax([r_A, r_B])` 中 B 的那一项
- C. `σ(r_A − r_B)`
- D. `σ(r_A) · (1 − σ(r_B))`

**Q2.** 奖励模型给 chosen 和 rejected 打出完全相同的分数时，`bradley_terry_loss` 的值约为：

- A. 0.693
- B. 0
- C. 1.0
- D. 0.313

**Q3.** 讲义解释为什么收集"成对比较"而不是"绝对打分"，最主要的理由是：

- A. 成对比较的数据量更小，标注成本更低
- B. 成对比较可以直接用于 SFT
- C. 绝对打分无法用神经网络拟合
- D. 人很难稳定地给出绝对分数，但比较两个回复哪个更好要可靠得多

**Q4.** 本节 `RewardModel.forward` 只取最后一个位置的隐藏状态 `x[:, -1, :]` 来计算奖励，原因是：

- A. 最后一个 token 总是句号，语义最稳定
- B. 在因果注意力下，最后一个位置已经关注过序列中的所有 token，表示最完整
- C. 这样可以省掉注意力计算
- D. 第一个位置的隐藏状态总是全零

**Q5.** PPO 裁剪目标中 ε = 0.2。某个 token 的优势 A = +2，新旧策略概率比 ratio = 1.5。该 token 的目标项 `min(ratio·A, clip(ratio)·A)` 等于：

- A. 2.4
- B. 3.0
- C. 2.0
- D. 1.6

**Q6.** RLHF 目标中 KL 惩罚项 `β · KL(π ‖ π_ref)` 的主要作用是：

- A. 加快 PPO 收敛
- B. 让奖励模型更准确
- C. 防止策略偏离 SFT 模型太远，从而去钻奖励模型的空子（reward hacking）
- D. 降低生成时的显存占用

**Q7.** 下列哪一项**不是**讲义表格中列出的 reward hacking 表现？

- A. 回复越来越长（Verbosity）
- B. 无论用户说什么都表示赞同（Sycophancy）
- C. 回避给出明确答案（Hedging）
- D. 拒绝使用任何项目符号和标题，只输出纯文本

**Q8.** 运行本节代码，PPO 训练 20 个 episode 的 KL 始终显示 `0.0000`，最后的对比表中 RLHF 的平均奖励（−0.3674）略高于 SFT（−0.4303）。最准确的解释是：

- A. KL 系数 0.02 太大，把策略完全锁死在参考模型上
- B. 策略"更新"只是量级约 1e-8 的随机噪声，模型几乎没变；两者奖励的差异来自各自独立采样的随机性
- C. PPO 已经收敛，所以 KL 为 0
- D. 奖励模型训练失败，所有回复的奖励都相同

---

## 三、动手 / 代码题

**Q9.** 阅读奖励模型训练中的更新步骤：

```python
            r_preferred = rm.forward(preferred_ids)[0]
            r_rejected = rm.forward(rejected_ids)[0]
            loss = bradley_terry_loss(r_preferred, r_rejected)
            ...
            diff = r_preferred - r_rejected
            grad = sigmoid(diff) - 1.0

            rm.reward_head -= (
                lr
                * grad
                * rm.ln_f.forward(rm.embedding.forward(preferred_ids))[
                    :, -1, :
                ].flatten()
            )
```

已知 `r = h_last · w`（`w` 即 `reward_head`，`h_last` 是经过全部 Transformer block 和 `ln_f` 后最后一个位置的隐藏状态）。

1. 推导 `loss = −log σ(r_p − r_r)` 对 `w` 的梯度。
2. 代码的更新式和正确梯度相比有哪两处错误？
3. 既然梯度是错的，为什么准确率还能从 66.7% 升到 83.3%？只训练 `reward_head` 还有什么局限？

**Q10.** 关于本节奖励模型的**输入**：

```python
def tokenize_for_reward(prompt, response, vocab_size=256):
    ...
    return prompt_tokens + [0] + response_tokens
```

训练时 `preferred_tokens[:max_seq_len]`（128）截断；PPO 和 `compare_models` 中则是 `reward_model.forward(np.array(response_tokens[:max_seq_len]))`，其中 `response_tokens = prompt_tokens + 生成的 20 个 token`。

1. 6 对偏好数据共 12 条序列，有多少条超过 128 个 token 被截断？截断对"取最后一个 token 打分"的 RM 意味着什么？
2. PPO 阶段送进 RM 的序列与 RM 训练时的序列格式有什么不一致？会带来什么问题？
3. 6 对数据中，有 4 对的 preferred 比 rejected 短得多。这对 RM 学到的东西有什么风险？

**Q11.** 手算：

1. ε = 0.2，对下面四种情况分别写出 `min(ratio·A, clip(ratio, 0.8, 1.2)·A)` 的值，并判断此时目标对 ratio 是否还有梯度：(a) A = +2, ratio = 1.5；(b) A = +2, ratio = 0.5；(c) A = −2, ratio = 1.5；(d) A = −2, ratio = 0.5。
2. 两个二元分布 `π = [0.5, 0.5]`、`π_ref = [0.9, 0.1]`，计算 `KL(π ‖ π_ref)` 和 `KL(π_ref ‖ π)`。KL 对称吗？
3. 本节 `compute_kl_divergence` 对 `response_ids` 的**所有位置**（包括 prompt 部分）求 KL 再取平均。RLHF 中通常应该怎么算？

**Q12.** 阅读 `ppo_training` 的更新：

```python
        total_reward = reward - kl_coeff * kl
        ...
        for block in policy_model.blocks:
            update_scale = lr * total_reward
            block.ffn.W1 += update_scale * np.random.randn(*block.ffn.W1.shape) * 0.01
            block.ffn.W2 += update_scale * np.random.randn(*block.ffn.W2.shape) * 0.01
```

1. 和讲义描述的 PPO 相比，这里缺少了哪些关键组件？
2. 这个"更新"的期望方向是什么？为什么它不可能提高奖励？
3. 写出一个最小可行的策略梯度更新（REINFORCE + baseline + KL 惩罚）的伪代码，说明需要从模型中拿到哪些量。

---

## 四、面试高频题

**Q13.**（基础必考）请完整描述 RLHF 的三个阶段，以及 PPO 阶段 GPU 上需要同时存在哪些模型、各自是否参与训练。

**Q14.**（原理深挖）写出 RLHF 中 PPO 的优化目标。KL 惩罚具体是怎么加到奖励里的？裁剪、优势估计、价值模型各起什么作用？β 怎么选？

**Q15.**（原理深挖）什么是 reward hacking？为什么它几乎不可避免？如何检测与缓解？

**Q16.**（工程实践）你负责为一个客服助手构建奖励模型，请设计偏好数据采集、RM 训练与评估方案。RM 准确率做到多少算好？

**Q17.**（追问型）RLHF + PPO 的工程痛点是什么？业界有哪些替代或简化方案？

---

## 五、参考答案与解析

### Q1 — 答案：C

Bradley-Terry：`P(A ≻ B) = exp(r_A) / (exp(r_A) + exp(r_B)) = σ(r_A − r_B)`。注意 B 选项"softmax 中 B 的那一项"是 `P(B ≻ A)`，方向反了。A 是 BT 模型在"正分数"参数化下的另一种写法（`p_A/(p_A+p_B)`），但在奖励可以为负的对数参数化中不成立；D 不是任何标准模型。

### Q2 — 答案：A

`Δ = 0` 时 `σ(0) = 0.5`，`−log 0.5 = ln 2 ≈ 0.693`。本次运行 Epoch 1 的平均 loss 为 0.6474，接近 ln 2，说明 RM 初始时几乎分不出好坏。D（0.313）是 `Δ = 1` 时的 loss；B 是 `Δ → +∞` 的极限。

### Q3 — 答案：D

讲义："humans are terrible at assigning absolute quality scores ... but very good at relative comparisons." A 错：标注一次比较需要读两个回复，成本并不低（讲义：InstructGPT 每次比较约 5 分钟）；B 错：偏好数据用于 RM 训练或 DPO，而不是 SFT；C 错：绝对分数完全可以用回归拟合，问题在于标签噪声大、标注者之间尺度不一致。

### Q4 — 答案：B

因果 mask 下位置 i 只能看到 ≤ i 的 token，只有最后一个位置看过全部 prompt + response。A 错：句号只是本数据的巧合，而且本节有 7 条序列被截断后最后一个 token 根本不是句号（见 Q10）；C、D 均不成立。讲义练习 1 要求对比 mean pooling。

### Q5 — 答案：A

`ratio·A = 1.5 × 2 = 3.0`，`clip(1.5, 0.8, 1.2)·A = 1.2 × 2 = 2.4`，取 min 得 2.4。此时裁剪分支生效，目标对 ratio 的梯度为 0——策略已经把这个"好动作"的概率提高了 50%，PPO 不再继续奖励它，以免一步走太远。B 是未裁剪值；C 是 ratio = 1 时的值；D 无对应。

### Q6 — 答案：C

讲义："The KL penalty says: you can improve, but you can't become a completely different model." RM 只在有限的偏好数据上训练，存在盲区；策略越偏离 SFT 分布，越容易进入 RM 打分不可靠的区域。A 错：KL 惩罚通常让收敛更慢、更稳；B 错：KL 不改变 RM；D 错：计算 KL 反而需要额外跑一次参考模型的前向。

### Q7 — 答案：D

讲义表格中的四种是 Verbosity、Sycophancy、Hedging、Format gaming，其中 Format gaming 是"过度使用项目符号和标题"，与 D 恰好相反。

### Q8 — 答案：B

已实际验证：每步更新量为 `1.5e-5 × reward(约 −0.3) × 0.01 × N(0,1)`，约 5e-8；我们把类似量级的噪声叠加 20 次后计算 KL，只有约 2.4e-10，四位小数下显示为 0。对比表的差异来自两次独立采样：我们用**同一个** SFT 模型和自己比（`compare_models(sft, sft, ...)`）重复三次，平均奖励差分别为 +0.09、+0.14、−0.16，比表中的 +0.063 还大。A 错：KL 项乘以 0.02 后完全可以忽略，不存在"锁死"；C 错：根本没有在优化；D 错：RM 对 6 对数据的打分各不相同，准确率 5/6。

### Q9 — 参考答案

1. 记 `Δ = r_p − r_r = (h_p − h_r)·w`，`loss = −log σ(Δ)`，`d loss / dΔ = σ(Δ) − 1`，所以

   ```text
   ∂loss/∂w = (σ(Δ) − 1) · (h_p − h_r)
   ```

   其中 `h_p`、`h_r` 是 chosen / rejected 序列**经过全部 Transformer block 和 ln_f 后**最后一个位置的隐藏状态。

2. 两处错误：
   - **特征算错了**：`rm.ln_f.forward(rm.embedding.forward(preferred_ids))` 跳过了全部 4 个 Transformer block，用的是"最后一个 token 的 embedding + 位置 embedding 再做 LayerNorm"，而不是 RM 实际用来打分的 `h_last`；
   - **漏掉了 rejected 一侧**：正确梯度是 `h_p − h_r`，代码只用了 `h_p`。结果是不断把 `w` 推向"chosen 最后一个 token 的 embedding 方向"，同时也会抬高任何以同样 token 结尾的序列的分数。

3. 能"凑巧"变好的原因：更新确实让 `w` 与"chosen 序列末尾特征"更对齐，而这与真实 `h_p` 有一定相关；加上只有 6 对数据，准确率从 4/6 变成 5/6 只需要一对翻转。我们实测：初始准确率 4/6；按代码训练后 5/6，`reward_head` 的范数变化只有 0.02（初始范数 0.25）；改用正确梯度、同样 lr = 1e-4 训练 10 个 epoch 可达到 6/6。
   只训练 `reward_head` 的局限：Transformer 主体是随机初始化且冻结的，RM 只能在随机特征上做线性分类，无法学到"简洁、准确"等语义；真实 RM 从 SFT 模型初始化并全量微调（讲义："Take the SFT model, replace the language modeling head ... with a scalar head"）。

### Q10 — 参考答案

1. **7 条**被截断（已用代码验证）：第 1、3、4、5 对的 rejected，以及第 6 对的 preferred 与 rejected 都超过 128（长度 134–155）。截断后最后一个 token 落在句子中间（如 `"...known for the E"`、`"...in the mid-1"`），RM 恰恰只看最后一个位置，于是它评判的是一个被腰斩的回复。这也解释了为什么"更啰嗦 = 更差"这一特征在截断后可能被部分抹掉。修正：增大 `max_seq_len`，或从左侧截断 prompt、保证回复完整。
2. 训练时的格式是 `prompt + [0] + response`（用字节 0 作分隔符）；PPO 和评估时直接把 `prompt + 生成内容` 送进 RM，**没有分隔符 0**。RM 从未见过这种格式，打分属于分布外（OOD）输入，奖励信号不可靠——这本身就是 reward hacking 的温床。正确做法是 RM 训练与打分共用同一个 `tokenize_for_reward`（或同一个 chat template）。
3. 6 对中 preferred / rejected 的字符数分别为 31/109、71/68、18/116、29/105、27/123、126/109：有 4 对 preferred 明显更短。RM 很可能学到"越短越好"这一**捷径特征**（与讲义中 verbosity 偏差方向相反，但本质相同），PPO 时策略就会去生成过短甚至空的回复来骗分。真实标注中也常有长度偏差，需要构造长度受控的对比对，或在评估中单独分析长度与奖励的相关性。

### Q11 — 参考答案

1. （已用 Python 验证）

   | 情况 | ratio·A | clip·A | min | 对 ratio 有无梯度 |
   |------|--------|--------|-----|-----------------|
   | (a) A=+2, ratio=1.5 | 3.0 | 2.4 | **2.4** | 无（已经涨够了，被裁剪） |
   | (b) A=+2, ratio=0.5 | 1.0 | 1.6 | **1.0** | 有（好动作的概率被压低了，要拉回来） |
   | (c) A=−2, ratio=1.5 | −3.0 | −2.4 | **−3.0** | 有（坏动作概率反而升高了，要压下去） |
   | (d) A=−2, ratio=0.5 | −1.0 | −1.6 | **−1.6** | 无（已经压够了，被裁剪） |

   规律：取 min 是"悲观估计"，只在"朝有利方向走过头"时截断；朝不利方向偏离时不截断，保证能纠正。

2. `KL(π ‖ π_ref) = 0.5 ln(0.5/0.9) + 0.5 ln(0.5/0.1) ≈ 0.5108`；`KL(π_ref ‖ π) = 0.9 ln(0.9/0.5) + 0.1 ln(0.1/0.5) ≈ 0.3681`。不对称。RLHF 用的是 `KL(π ‖ π_ref)`（期望在策略自己的样本上取），它在 `π` 给某个 token 高概率而 `π_ref` 给极低概率时惩罚很重，正好抑制"跑到参考模型认为不可能的区域"。
3. 本节对所有位置的完整分布算精确 KL 再平均，prompt 部分也被计入（prompt 位置的 KL 与策略的"回复行为"无关，会稀释信号）。常见实现：只在**生成的回复 token** 上，用采样到的 token 计算 `log π(y_t | ·) − log π_ref(y_t | ·)` 作为逐 token 的 KL 估计，把 `−β ×` 它加到每个 token 的奖励上，RM 分数只加在最后一个 token 上；然后按序列求和（而不是平均）。

### Q12 — 参考答案

1. 缺少的组件：
   - 生成 token 在策略下的 **log 概率**（以及旧策略的 log 概率），从而算不出 `ratio`；
   - **优势**：没有 baseline / 价值模型，直接用原始奖励；
   - **裁剪**：根本没有 `clip(ratio, 1−ε, 1+ε)`；
   - **梯度**：没有任何从 log 概率反传到参数的步骤；
   - 每批数据多轮（讲义：4 个 PPO epoch）复用、mini-batch 等。
2. 更新量是 `lr · total_reward · 0.01 · ε`，其中 `ε ~ N(0, I)` 与奖励、与模型输出都无关，**期望为 0**。奖励的大小只改变噪声的幅度，正负号只翻转一个本来就对称的随机方向。因此它只是随机游走，不可能系统性地提高奖励。
3. 最小可行版本（伪代码）：

   ```python
   baseline = 0.0
   for episode in range(N):
       y, logp_old = policy.sample(prompt)             # 记录每个生成 token 的 log π
       logp_ref = ref.logprob(prompt, y)               # 参考模型对同一批 token 的 log 概率
       r = reward_model(format_for_rm(prompt, y))      # 与 RM 训练时同一格式
       kl = (logp_old - logp_ref).sum()                # 只在回复 token 上
       R = r - beta * kl
       A = R - baseline                                # 优势
       baseline = 0.9 * baseline + 0.1 * R             # 滑动平均 baseline
       loss = -(A * policy.logprob(prompt, y).sum())   # REINFORCE；PPO 则换成裁剪的 ratio·A
       loss.backward(); optimizer.step()
   ```

   需要从模型中拿到：生成 token 的 log 概率（策略、旧策略、参考模型各一份）、RM 标量奖励；完整 PPO 还需要价值模型输出 `V(s_t)` 来做 GAE。用 NumPy 手写这些反传非常繁琐，这也是实际都用 PyTorch + TRL / OpenRLHF 等框架的原因。

### Q13 — 参考回答要点

- **阶段 1：SFT**——在指令数据上微调 base 模型（第 06 节）。
- **阶段 2：RM**——用 SFT 模型对同一 prompt 生成多个回复，标注者比较；从 SFT 初始化、换成标量头，用 BT 损失训练。
- **阶段 3：PPO**——策略从 SFT 初始化，采样回复 → RM 打分 → 减去 KL 惩罚 → PPO 更新。
- **PPO 阶段同时存在的模型**：
  - 策略（actor）：训练；
  - 参考模型（冻结的 SFT）：只前向，算 KL；
  - 奖励模型：只前向；
  - 价值模型（critic）：训练，通常从 RM 初始化，用来估计优势。
  也就是"4 个模型、2 个在训练"。讲义说"三个模型（SFT、奖励、策略）"，是把参考模型算作 SFT、并省略了价值模型的简化说法。
- 加分点：显存压力很大，常见做法是参考模型与策略共享权重 + LoRA（关掉 adapter 就是参考模型），或者把 RM / 参考模型放到单独的推理节点上。

### Q14 — 参考回答要点

- **目标**：`max_π E_{x, y~π}[ R(x, y) ] − β · KL(π(·|x) ‖ π_ref(·|x))`。
- **KL 怎么加**：常见做法是逐 token 奖励 `r_t = −β (log π(y_t|·) − log π_ref(y_t|·))`，最后一个 token 再加上 RM 分数。
- **优势估计**：价值模型给出 `V(s_t)`，用 GAE 计算每个 token 的优势 `A_t`；没有价值模型时可以用同一 prompt 下多次采样的平均奖励作 baseline（GRPO 的思路）。
- **裁剪**：`L = −E[min(ratio_t·A_t, clip(ratio_t, 1−ε, 1+ε)·A_t)]`，ε ≈ 0.2；允许同一批数据做多轮更新而不跑飞（见 Q11 的四种情况）。
- **价值损失**：`(V(s_t) − 目标回报)²`，常与策略损失加权一起优化。
- **β 的选择**：讲义列出 InstructGPT 0.02、Llama 2 0.01、Anthropic 论文 0.001。太小 → reward hacking（练习 5）；太大 → 学不动。也可以用自适应 KL 控制：设定目标 KL，实测 KL 偏大时调大 β、偏小时调小 β。
- 常见误区：把 KL 当成固定正则项算在整个分布上（本节代码的做法），或在 prompt token 上也算 KL。

### Q15 — 参考回答要点

- **定义**：策略在优化代理目标（RM 分数）时找到让分数变高、但真实质量没有变好甚至变差的输出（讲义："finding outputs that score high on the reward model but are actually nonsensical"）。本质是 Goodhart 定律：一个指标一旦成为优化目标，就不再是好指标。
- **为什么不可避免**：RM 只是在有限数据上训练的近似；策略的优化压力会把它推到 RM 没见过的区域。
- **典型表现**：啰嗦（长度偏差）、谄媚、含糊其辞、格式堆砌（讲义表格），以及利用特定短语。
- **检测**：
  - 监控 KL 曲线、平均回复长度、熵；
  - 定期用**人工**或独立的强模型评估，与 RM 分数对比：RM 分数持续上升而人工评分持平或下降，就是 hacking 的信号；
  - 用一个未参与训练的"金标准" RM 做对照。
- **缓解**：更大的 β、提前停止、RM 集成（多个 RM 取保守值）、对抗样本迭代训练 RM、长度惩罚 / 长度归一化、多目标奖励（讲义练习 4）、定期用新策略的样本重新采集偏好数据。
- 加分点：本节的 6 对数据中有 4 对 preferred 更短（Q10），就是一个会诱发"越短越好"捷径的数据偏差。

### Q16 — 参考回答要点

- **数据采集**：
  - prompt 来自真实客服日志（脱敏）+ 少量分布外 prompt；
  - 用 SFT 模型在不同温度下各生成 2–4 个回复；
  - 制定评分细则（有用性、无害性、诚实、简洁的权重，参见 `outputs/` 中的提示词）；
  - 标注者校准轮、插入一致性检查题、多人标注同一对以估计一致率；
  - 控制长度偏差：构造长度相近的对比对。
- **RM 训练**：从 SFT 检查点初始化、标量头、BT 损失，1–3 个 epoch（容易过拟合），保留 10–20% 验证集。
- **评估**：
  - 验证集成对准确率：讲义——InstructGPT RM 约 72%，标注者间一致率约 73%，RM 很难超过人类一致率，所以 70% 左右已属良好；
  - 边际（margin）分布与校准：`σ(Δ)` 是否接近真实偏好比例；
  - 分布外 prompt 上的准确率下降幅度；
  - 长度、格式等捷径特征与奖励的相关性分析。
- 加分点：RM 规模不应明显小于策略（讲义：小 RM 训练大模型有风险）；上线前做 SFT vs RLHF 的人工 A/B 盲评。

### Q17 — 参考回答要点

- **痛点**：
  - 显存与工程复杂度：4 个模型、生成与训练交替，吞吐低；
  - 超参数敏感：β、学习率、ε、PPO epoch、生成长度都会影响稳定性；
  - RM 质量决定上限，且容易被 hack；
  - 在线采样慢：每一步都要先生成回复。
- **替代 / 简化**：
  - **DPO**（下一节）：把 RLHF 目标的最优解代回，直接在偏好对上做分类式损失，不需要 RM 和 PPO 采样，只需策略 + 参考模型；
  - **GRPO** 等：去掉价值模型，用同一 prompt 下一组样本的平均奖励作 baseline；
  - **拒绝采样微调（Best-of-N + SFT）**：用 RM 从多个样本中选最好的再做 SFT（Llama 2 Chat 在 PPO 之外也使用了 rejection sampling）；
  - **RLAIF / Constitutional AI**：用 AI 反馈替代人工偏好标注（第 09 节）。
- 加分点：能说出"DPO 是离线的、只用固定偏好数据；PPO 是在线的、能从策略自己的新样本中学习"这一核心区别。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 06 指令微调（SFT）](../../06-instruction-tuning-sft/docs/zh.md)：RLHF 的起点；本节的策略和参考模型都应来自 SFT。
- [阶段 10 · 04 预训练 Mini GPT](../../04-pre-training-mini-gpt/docs/zh.md)：本节直接复用那里的 `MiniGPT`、`Embedding`、`TransformerBlock`。
- [阶段 09 · 06 Policy Gradient — REINFORCE 从头开始](../../../09-reinforcement-learning/06-policy-gradients-reinforce/docs/zh.md)：策略梯度与 baseline，Q12 的伪代码即来源于此。
- [阶段 09 · 07 Actor-Critic — A2C 和 A3C](../../../09-reinforcement-learning/07-actor-critic-a2c-a3c/docs/zh.md)：价值模型（critic）与优势估计。
- [阶段 09 · 08 近端策略优化（PPO）](../../../09-reinforcement-learning/08-ppo/docs/zh.md)：裁剪目标、GAE 的完整推导。
- [阶段 09 · 09 奖励建模 & RLHF](../../../09-reinforcement-learning/09-reward-modeling-rlhf/docs/zh.md)：从强化学习视角看奖励建模。
- [阶段 01 · 09 信息论](../../../01-math-foundations/09-information-theory/docs/zh.md)：KL 散度及其不对称性。

### 本节被哪些后续内容用到
- [阶段 10 · 08 DPO：直接偏好优化](../../08-dpo/docs/zh.md)：从 RLHF 目标推导出无需 RM、无需 PPO 的偏好优化。
- [阶段 10 · 09 Constitutional AI 与自我改进](../../09-constitutional-ai-self-improvement/docs/zh.md)：用 AI 反馈替代人工偏好。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：reward hacking 的系统讨论。
- [阶段 18 · 04 RLHF 对迎合行为的放大效应](../../../18-ethics-safety-alignment/04-sycophancy-rlhf-amplification/docs/zh.md)：讲义表格中的 Sycophancy。
- [阶段 18 · 05 Constitutional AI 与 RLAIF](../../../18-ethics-safety-alignment/05-constitutional-ai-rlaif/docs/zh.md)：对齐视角下的 AI 反馈。

### 延伸关键词
`Bradley-Terry` · `reward model` · `PPO-clip` · `GAE` · `value model / critic` · `per-token KL penalty` · `adaptive KL controller` · `reward hacking` · `Goodhart's law` · `length bias` · `reward model ensemble` · `rejection sampling / best-of-N` · `GRPO` · `RLAIF` · `TRL / OpenRLHF`
