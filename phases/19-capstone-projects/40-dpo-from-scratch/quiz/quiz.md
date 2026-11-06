# 测验 · 从零实现直接偏好优化（Direct Preference Optimization from Scratch）

> **阶段 19 · 综合项目 · 第 40 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Bradley-Terry 偏好模型 | `P(y_w ≻ y_l | x) = σ(r(x, y_w) − r(x, y_l))`：只有奖励**差**有意义，任何只依赖 x 的项都会抵消 |
| 2 | KL 约束下的最优策略 | `max E[r] − β·KL(π‖π_ref)` 的解是 `π*(y|x) = π_ref(y|x)·exp(r/β)/Z(x)`；反解得 `r = β·log(π*/π_ref) + β·log Z(x)` |
| 3 | DPO loss | `L = −log σ(β·[(log π_θ(y_w) − log π_ref(y_w)) − (log π_θ(y_l) − log π_ref(y_l))])`；`log Z(x)` 在差值中抵消，无需显式奖励模型、无需 PPO |
| 4 | 隐式奖励 | `r̂(x, y) = β·(log π_θ(y|x) − log π_ref(y|x))`；本节 `dpo_loss` 返回的 `margin` 是两条回答 log-ratio 之差（尚未乘 β） |
| 5 | 梯度方向 | `∂L/∂log π_θ(y_w) = −β(1 − σ(z)) < 0`、`∂L/∂log π_θ(y_l) = +β(1 − σ(z)) > 0`：推高 chosen、压低 rejected；z 越大梯度越小（sigmoid 饱和） |
| 6 | 序列对数概率 | 把 prompt + completion 拼起来前向一次，只对 completion 的每个 token 取 `log p(token | 前文)` 并求和；prompt 位置不计分 |
| 7 | 参考模型不变性 | 参考模型冻结（`requires_grad=False`、`eval()`），其 log-prob 只在训练开始前算一次；策略模型通过 `load_state_dict` 从参考模型初始化 |
| 8 | 起点处的 loss | 策略 = 参考时 z = 0，loss = `ln 2 ≈ 0.693`；这是检查实现的第一道健全性测试 |
| 9 | 长度偏差 | 对数概率按 token 求和，越长越负；本节 rejected 普遍比 chosen 长得多，**随机初始化的模型**就有 +293 的原始 margin |
| 10 | 变体 | IPO：`(margin − 1/(2β))²`，不饱和、收敛到固定 margin；长度归一化；label smoothing（cDPO）；参考模型换成更小的模型 |

### 核心技能（能动手做到）

- [ ] 从 RLHF 目标出发，推导出 DPO loss，并说清 `Z(x)` 为什么会抵消
- [ ] 给定四个对数概率和 β，手算 DPO loss、隐式奖励差和对 chosen log-prob 的梯度
- [ ] 写出只对 completion 计分的 `sequence_log_prob`，并能处理超长序列与批量 padding
- [ ] 实现参考模型冻结、log-prob 预计算、策略从参考模型复制这三条不变性，并写测试锁定
- [ ] 区分训练日志中的"隐式 margin"与评估时的"原始 log-prob margin"，识别长度偏差和过度优化
- [ ] 实现 IPO、长度归一化、label smoothing 三种变体，并在同一 fixture 上比较行为

---

## 二、基础自测（选择题）

**Q1.** 训练开始前策略与参考模型权重完全相同。对任意一个三元组，第一步的 DPO loss 是多少？

- A. 0
- B. β
- C. `ln β`
- D. `ln 2 ≈ 0.693`

**Q2.** β = 0.2。某三元组上 `(log π_θ(y_w) − log π_ref(y_w)) − (log π_θ(y_l) − log π_ref(y_l)) = +5`，DPO loss 约为：

- A. 0.693
- B. 0.313
- C. 1.313
- D. 0.0067

**Q3.** β = 1，四个对数概率都为 0（z = 0）。`dpo_loss` 对 `logp_w_pol` 的梯度是：

- A. −0.5
- B. +0.5
- C. −1.0
- D. 0

**Q4.** demo 在 DPO 训练**之前**就打印 `initial chosen-rejected margin = +257.1123`。额外实测：连 warmup 都不做的随机初始化模型，这个值也有 +293。最主要的原因是：

- A. warmup 只在 chosen 上训练，模型已经学会了偏好
- B. 参考模型没有冻结
- C. 这个 margin 是"原始对数概率之差"，按 token 求和；rejected 有 46–78 个字节，chosen 只有 2–48 个字节，更长的序列累加了更多负的 log-prob
- D. β 取得太大

**Q5.** 训练日志最后一行是 `epoch 30: loss=0.0000 margin=+98.0749`，而结尾打印 `FINAL margin = +355.1893 (initial was +257.1123)`。两个 "margin" 的关系是：

- A. 两者是同一个量，差异来自随机性
- B. 日志里的是隐式 margin `(log π_θ − log π_ref)_w − (log π_θ − log π_ref)_l`，FINAL 的是策略下原始的 `log π_θ(y_w) − log π_θ(y_l)`；由于参考模型的原始 margin 就是 257.1，二者约满足 `355.2 ≈ 257.1 + 98.1`
- C. FINAL margin 已经乘了 β
- D. 日志里的 margin 是在参考模型上计算的

**Q6.** 从第 2 个 epoch 起 loss 显示为 0.0000，margin 停在约 98 附近几乎不再增长。正确的解释是：

- A. 学习率衰减到 0 了
- B. 参考模型在第 2 个 epoch 后被解冻
- C. 优化器状态被重置了
- D. sigmoid 已饱和：z = 0.2 × 98 ≈ 19.6，loss ≈ 3×10⁻⁹，梯度 `−β(1 − σ(z))` 几乎为 0，这正是讲义所说"sigmoid 饱和抑制了梯度"的结构性 KL 约束

**Q7.** 对比 DPO 训练前后（策略 vs 参考）每个三元组的对数概率，实测发现：

- A. 12 个 chosen 中有 10 个对数概率**下降**（平均 −8.5，"Define function." 降了 46），rejected 平均下降约 107；margin 变大主要靠"rejected 降得更多"
- B. 所有 chosen 的对数概率都上升了，rejected 基本不变
- C. chosen 与 rejected 都上升，但 chosen 升得更多
- D. 两者都不变，只有隐式奖励变化

**Q8.** 关于本节代码如何保证"参考模型不变"，下列说法**错误**的是：

- A. `build_models` 把参考模型所有参数设为 `requires_grad=False` 并调用 `eval()`
- B. `train_dpo` 在训练循环开始前，用 `torch.no_grad()` 一次性计算并缓存所有参考 log-prob
- C. 优化器同时包含了参考模型的参数，但学习率为 0，所以它不会更新
- D. 策略模型通过 `policy.load_state_dict(reference.state_dict())` 从（warmup 后的）参考模型复制权重

---

## 三、动手 / 代码题

**Q9.** 阅读 `sequence_log_prob` 的核心部分：

```python
    full = list(prompt_ids) + list(completion_ids)
    if len(full) > model.max_len:
        full = full[-model.max_len :]
        prompt_len = max(0, len(full) - len(completion_ids))
    else:
        prompt_len = len(prompt_ids)
    ...
    log_probs = F.log_softmax(logits, dim=-1)
    completion_targets = torch.tensor(full[prompt_len:], ...)
    pred_positions = torch.arange(prompt_len - 1, len(full) - 1, ...)
    if prompt_len == 0:
        pred_positions = torch.arange(0, len(full) - 1, ...)
        completion_targets = torch.tensor(full[1:], ...)
    gathered = log_probs[0, pred_positions, completion_targets]
```

1. prompt 长 4、completion 长 3（共 7 个 token）时，`pred_positions` 和 `completion_targets` 各是什么？为什么用 `prompt_len - 1` 开始？
2. fixture 中 `"What is the capital of France?"` 的 rejected 拼起来有 98 个 token，而 `max_len = 96`。会发生什么？对 DPO 的 log-ratio 有影响吗？
3. 当 completion 本身比 `max_len` 还长（`prompt_len == 0` 分支）时，哪些 completion token 没有被计分？

**Q10.** 讲义 stretch goal 1：长度归一化。

1. 实测参考模型（warmup 后）的**长度归一化** margin（每 token 平均 log-prob 之差）为 3.66，DPO 后为 4.87；而原始 margin 从 257 变成 355。解释为什么原始 margin 不适合作为"是否学会偏好"的指标。
2. 修改 `train_dpo`，增加 `length_normalise: bool` 选项，用 `length_normalised_log_prob` 计算四个 log-prob。注意 β 的量纲会发生什么变化？

**Q11.** 讲义 stretch goal 2 和 3：

1. 讲义写 IPO 是"用 `(z − 1)²` 替换 sigmoid + log"，代码 `ipo_loss` 却是 `(margin − 1/(2β))²`。两者有什么区别？用代码的版本在本 fixture 上训练（其余不变），实测每个 epoch 的平均 margin 最终稳定在 2.47–2.54，rejected 平均只下降约 8（DPO 下降约 107）。解释这个现象。
2. 写一个带 label smoothing 的 DPO loss（假设偏好标签有 ε 的概率是反的），并说明它在 z 很大时的行为与原始 DPO 有何不同。

**Q12.** 讲义说 demo "trains for thirty steps"，而代码是 30 个 epoch、每个 epoch 对 12 个三元组**逐个**做一次 `opt.step()`。

1. 实际共做了多少次参数更新？这种 batch size = 1 的写法有什么问题？
2. 写一个 `batch_log_probs(model, prompts, completions)`：把多条 prompt + completion 右侧 padding 成一个 batch，一次前向得到每条 completion 的对数概率之和，并说明为什么在本节的因果模型下右侧 padding 不需要额外的 attention mask。

---

## 四、面试高频题

**Q13.**（基础必考）DPO 和 RLHF（奖励模型 + PPO）有什么区别？DPO 省掉了什么、依赖什么假设？

**Q14.**（原理深挖）请推导 DPO loss，并解释 β 的作用：β 大或小分别意味着什么？

**Q15.**（原理深挖）DPO 训练中经常观察到"chosen 的对数概率也在下降"，这是 bug 吗？为什么会发生？有什么风险和对策？

**Q16.**（工程实践）你要在一个 7B SFT 模型上跑 DPO，工程上需要注意什么？（显存、参考模型、数据、监控指标、超参）

**Q17.**（追问型）DPO 有哪些已知的失效模式？IPO、长度归一化、label smoothing 分别针对哪个问题？

---

## 五、参考答案与解析

### Q1 — 答案：D

策略 = 参考时两个 log-ratio 都是 0，`z = 0`，`σ(0) = 0.5`，`−log 0.5 = ln 2`。测试 `test_zero_margin_loss_is_log_two` 正是验证这一点。实际 demo 中第 1 个 epoch 的平均 loss 只有 0.0687，是因为第 1 个三元组更新后，共享参数让其余 11 个三元组的 margin 也迅速变大，只有第一步是 `ln 2`。A 是完全学会后的极限；B、C 无依据。

### Q2 — 答案：B

`z = β × margin = 0.2 × 5 = 1`，`loss = −log σ(1) = log(1 + e⁻¹) ≈ 0.3133`（已实际计算）。A 是 z = 0；C 是 margin = −5 的情况（`log(1 + e¹) ≈ 1.313`）；D 是把 β 当成 1 计算 z = 5 的结果（`log(1 + e⁻⁵) ≈ 0.0067`）。注意 β 越小，同样的 log-ratio 差距换来的 loss 下降越少。

### Q3 — 答案：A

`∂L/∂log π_θ(y_w) = −β(1 − σ(z)) = −1 × (1 − 0.5) = −0.5`。用 autograd 实测 `lw.grad = tensor(-0.5)`。负梯度意味着梯度下降会**增大** chosen 的对数概率（讲义 "The Sign of the Gradient"）。对 rejected 的梯度是 +0.5（B 是它的值）。C 漏了 `(1 − σ)`；D 只在 z → ∞ 时成立。

### Q4 — 答案：C

`evaluate_margins` 计算的是 `log π_θ(y_w) − log π_θ(y_l)`，每条都是逐 token log-prob 的**和**。fixture 中 chosen 长 2–48 字节，rejected 长 46–78 字节；随机初始化时每个字节的 log-prob 约 `−ln 260 ≈ −5.6`，rejected 自然低得多。实测随机初始化时第一个三元组 chosen −34.8、rejected −372.9，平均 margin +293。warmup 在 chosen 上训练（A）会让 chosen 变得更可能，但这里绝大部分 margin 来自长度。讲义 stretch goal 1 提到的"length bias"在这个 fixture 上被放大到极致。B、D 与这个量无关（它甚至不涉及参考模型和 β）。

### Q5 — 答案：B

`train_dpo` 中日志的 `margin` 来自 `dpo_loss` 的第二个返回值 `diff_w − diff_l`，即**隐式** margin（相对参考模型的 log-ratio 之差）；`FINAL margin` 来自 `evaluate_margins`，是策略下**原始**的 chosen − rejected。因为 `原始(策略) = 原始(参考) + 隐式`，而训练开始时策略 = 参考，`initial = 257.1123` 就是参考的原始 margin，于是 `257.11 + 98.07 ≈ 355.19`（日志里的 98.07 是第 30 个 epoch 中边训练边记录的平均值，所以有 0.002 的出入）。两个量同名为 "margin" 是本节输出最容易让人误读的地方。C 错：两者都没乘 β；`dpo_loss` 的文档把 `margin` 称作"implicit reward difference"也不准确——按讲义定义，隐式奖励差应是 `β × margin`。

### Q6 — 答案：D

实测：β = 0.2、margin = 98 时 `loss = 3.07×10⁻⁹`，对 chosen log-prob 的梯度在 float32 下已经是 −0.0。第 2 个 epoch 的平均 loss 只有 1.07×10⁻⁶。讲义 "Why DPO works"："the sigmoid saturates, which damps the gradient when the policy moves too far"。代码没有学习率调度（A 错）、参考模型始终冻结（B 错）、优化器只创建一次（C 错）。注意"饱和"只是让梯度变小，并不是硬约束：在 12 条数据上训练 360 步，策略已经把 rejected 压低了约 100 nats，这是典型的过度优化。

### Q7 — 答案：A

实测 chosen 对数概率变化（策略 − 参考）：`[-2.18, -2.4, -5.66, +0.28, -0.33, -0.25, -10.83, -6.81, -17.98, -46.45, -4.12, -5.42]`，只有 "Compute 2 + 3." 一条上升；rejected 变化在 −71.7 到 −185.3 之间，平均 −106.6。DPO 的 loss 只依赖**差值**，梯度虽然对 chosen 是"向上推"，但参数是共享的，压低 rejected 的更新会连带把 chosen 也拉下来（两条回答共享大量字节和词汇模式时尤甚；最长的 chosen——"Define function." 的 48 字节回答——下降最多）。讲义说"watch the chosen log-prob rise relative to rejected"——是**相对**上升，绝对值并不保证。B、C、D 与实测不符。

### Q8 — 答案：C

`train_dpo` 中 `opt = torch.optim.Adam(policy.parameters(), lr=cfg.lr)`，优化器里**只有策略模型**的参数，参考模型根本不在其中。A、B、D 都是代码中真实存在的三重保护，对应讲义 "Reference Invariance" 一节列出的三条性质。测试 `test_reference_log_probs_unchanged_after_policy_training` 验证训练前后参考 log-prob 不变。小细节：demo 为了 warmup 先解冻参考模型、训练后再重新冻结，顺序必须是"warmup → 复制给策略 → 重新冻结"。

### Q9 — 参考答案

1. `full` 长 7，`prompt_len = 4`。`pred_positions = arange(3, 6) = [3, 4, 5]`，`completion_targets = full[4:7]`（3 个 token）。因为位置 i 的 logits 预测位置 i+1 的 token：completion 的第一个 token 在下标 4，由下标 3（prompt 的最后一个 token，即 RESP）的输出来预测；最后一个 token 在下标 6，由下标 5 预测。`log_probs[0, pred_positions, completion_targets]` 是成对的高级索引，一次取出 3 个值再求和。
2. 98 > 96，从**左边**截掉 2 个 token：INST 标记和 `'W'` 被丢掉，`prompt_len = 96 − 66 = 30`，completion 的 66 个 token 全部计分，但条件变成了"没有 INST、缺一个字母的 prompt"。策略和参考用的是同一套截断，所以 log-ratio 仍然是在同一条件下比较，DPO loss 依然自洽；但这条 rejected 的条件分布与其它样本不同（模型从没在训练里见过不以 INST 开头的序列）。更好的做法是截断 completion 尾部或丢弃超长样本，并在数据加载时报告。
3. `prompt_len == 0` 时，`full` 只剩 completion 的最后 `max_len` 个 token；代码把 `full[1:]` 作为目标，所以①被左截断丢掉的 completion 前缀不计分，②保留部分的**第一个** token 也不计分（它没有前文可以条件化）。实测 `max_len = 8`、completion 长 10 时只累加了 7 项。这会让超长 completion 的 log-prob 被系统性高估（项数更少），而且对 chosen/rejected 的影响不对称。

### Q10 — 参考答案

1. 原始 margin 里绝大部分是长度差带来的常数偏移：随机初始化就有 +293，warmup 后 +257——它告诉你"短的更可能"，而不是"好的更可能"。只有扣掉这个偏移（看隐式 margin，或看长度归一化 margin）才能判断 DPO 学到了什么。长度归一化后，参考模型 3.66 → 策略 4.87，提升约 1.2 nats/token，这才是更可比的量。另外，chosen 与 rejected 都没有 EOS，"短"本身并不能被模型表达为"在这里停止"（与第 39 节相同的问题），所以本 fixture 上"偏好短回答"无法转化为生成行为。
2. 参考修改：

```python
def train_dpo(policy, reference, tok, triples, cfg, log=print, length_normalise=False):
    lp = length_normalised_log_prob if length_normalise else sequence_log_prob
    ...
            lp_w_ref = lp(reference, prompt, chosen).detach()
            lp_l_ref = lp(reference, prompt, rejected).detach()
    ...
            lp_w_pol = lp(policy, prompt, chosen)
            lp_l_pol = lp(policy, prompt, rejected)
```

   β 的量纲变化：原来 log-ratio 是整条序列的和（几十到上百 nats），归一化后是每 token 的平均（通常小一到两个数量级），要达到同样的 `z`，β 需要相应放大（例如乘以平均长度）。这也是一些长度归一化变体（如 SimPO 一类方法）使用比标准 DPO 大得多的 β 的原因——具体取值应在验证集上调。

### Q11 — 参考答案

1. 讲义的 `(z − 1)²` 是简化写法；代码采用的是 IPO 原论文常见形式 `(h − 1/(2β))²`，其中 `h` 是隐式 margin（未乘 β）。两者都把 margin "拉向一个固定目标"而不是"推向无穷"，区别只在目标值与缩放：代码版的最优 margin 是 `1/(2β) = 2.5`（β = 0.2），测试 `test_ipo_minimum_at_target_margin` 验证 margin 等于目标时 loss 为 0。实测 IPO 训练的平均 margin 在前几个 epoch 有振荡（1.87、6.25、−5.03），之后稳定在 2.47–2.54，rejected 平均只下降约 8.1、chosen 下降约 5.6，远小于 DPO 的 −107：平方损失在 margin 超过目标时会**反向**推回，不存在 sigmoid 那种"越推越远但梯度趋零"的过度优化。
2. 参考实现（conservative DPO 的形式）：

```python
def dpo_loss_smoothed(logp_w_pol, logp_l_pol, logp_w_ref, logp_l_ref, beta, eps=0.1):
    margin = (logp_w_pol - logp_w_ref) - (logp_l_pol - logp_l_ref)
    z = beta * margin
    loss = -(1 - eps) * F.logsigmoid(z) - eps * F.logsigmoid(-z)
    return loss, margin
```

   ε = 0.1 时实测：z = 0 → 0.693，z = 5 → 0.507，z = 20 → 2.0。原始 DPO 在 z → ∞ 时 loss → 0、梯度 → 0；平滑版本在 z 很大时 `−ε·log σ(−z) ≈ ε·z` 线性增长，梯度变成反向的，最优点在 `z* = log((1−ε)/ε) = log 9 ≈ 2.2`。它承认"标签可能是错的"，因此不会无限地拉大 margin。

### Q12 — 参考答案

1. `30 epoch × 12 = 360` 次 `opt.step()`，不是讲义说的 30 步。batch size = 1 的问题：①每一步只看一个偏好对，梯度噪声大、顺序固定（不打乱），前面的三元组对后面影响很大（第 1 个 epoch 平均 loss 只有 0.069 就是因为第一步之后其它样本已被"顺带"优化）；②每一步只对一个三元组做 2 次独立的策略前向（chosen、rejected 各一次；参考 log-prob 已预先缓存），无法利用批量并行；③生产 DPO 都是小批量（chosen 与 rejected 拼在同一 batch），loss 取 batch 平均。
2. 参考实现（已在本节模型上验证与逐条计算的结果一致，最大误差约 3×10⁻⁵）：

```python
def batch_log_probs(model, prompts, completions, pad_id=InstructionTokenizer.PAD_ID):
    seqs = [list(p) + list(c) for p, c in zip(prompts, completions)]
    T = max(len(s) for s in seqs)
    ids = torch.full((len(seqs), T), pad_id, dtype=torch.long)
    loss_mask = torch.zeros(len(seqs), T, dtype=torch.bool)
    for b, (p, s) in enumerate(zip(prompts, seqs)):
        ids[b, :len(s)] = torch.tensor(s)
        loss_mask[b, len(p):len(s)] = True                         # 只在 completion 计分
    logp = F.log_softmax(model(ids), dim=-1)                         # (B, T, V)
    tok_lp = logp[:, :-1].gather(-1, ids[:, 1:].unsqueeze(-1)).squeeze(-1)  # (B, T-1)
    return (tok_lp * loss_mask[:, 1:]).sum(dim=1)                    # (B,)
```

   右侧 padding 时，pad 都在真实 token 之后，因果 mask 保证真实 token 看不到它们；pad 位置自己的输出被 `loss_mask` 排除。左侧 padding 或 packing 时就需要额外的 attention mask 和位置编号处理。实践中常把 chosen 与 rejected 拼成 `2B` 的一个 batch，一次前向得到全部四类 log-prob 中的两类。

### Q13 — 参考回答要点

- **RLHF（经典）**：①在偏好数据上训练奖励模型（Bradley-Terry）；②用 PPO 让策略最大化奖励并加 KL 惩罚。PPO 阶段要同时维护策略、参考、奖励模型（通常还有价值模型），要在线采样，训练不稳定，且易出现 reward hacking（讲义 "The Problem"）。
- **DPO**：利用 KL 约束下最优策略的闭式解，把奖励写成 `β·log(π/π_ref) + β·log Z(x)`，代入 Bradley-Terry 后 `Z(x)` 抵消，得到只依赖四个对数概率的监督式 loss。不需要显式奖励模型、不需要采样、不需要 PPO。
- **依赖的假设**：偏好服从 Bradley-Terry；离线数据覆盖了策略会生成的分布（DPO 是离线方法）；参考模型是一个合理的起点（通常是 SFT 模型）。
- **代价**：仍需要在训练中保留参考模型（或预先缓存参考 log-prob，本节就是这么做的）；不能像在线 RL 那样从模型自身的新样本中学习（可通过迭代/在线 DPO 缓解）。
- 加分：讲义 "Why DPO works"——在 BT 模型下两者最优解相同（相差奖励参数化方式），隐式奖励在 x 的函数意义下可辨识。

### Q14 — 参考回答要点

- **推导**：
  1. RLHF 目标 `max_π E_{y~π}[r(x,y)] − β·KL(π‖π_ref)`；
  2. 最优解 `π*(y|x) = π_ref(y|x)·exp(r(x,y)/β)/Z(x)`；
  3. 反解 `r(x,y) = β·log(π*(y|x)/π_ref(y|x)) + β·log Z(x)`；
  4. 代入 `P(y_w ≻ y_l) = σ(r_w − r_l)`，`β·log Z(x)` 抵消；
  5. 用参数化策略 π_θ 代替 π*，对偏好数据做最大似然：`L = −E[log σ(β·(Δ_w − Δ_l))]`，`Δ = log π_θ − log π_ref`。
- **β 的作用**：β 是 KL 惩罚强度，也是 sigmoid 的"温度"。
  - β 大：KL 约束强，隐式奖励 = β·log-ratio，同样的偏好只需较小的 log-ratio 变化就能使 sigmoid 饱和，策略离参考更近、更保守；
  - β 小：允许策略偏离参考更远，需要更大的 log-ratio 才能把 loss 降下来，更容易过度优化、遗忘 SFT 能力。
  - 本节 β = 0.2：margin 达到约 98 时 z ≈ 19.6 才饱和；若 β = 0.1，同样 margin 下 loss 仍有 5.5×10⁻⁵（实测），会继续推。
- 加分：梯度权重 `σ(−z)` 相当于"模型越是判错（z 越小）的样本权重越大"，这是 DPO 自带的难例加权。

### Q15 — 参考回答要点

- **不是 bug，是 DPO 目标的性质**：loss 只约束 `Δ_w − Δ_l`，没有约束 `Δ_w` 本身的符号。只要 rejected 下降得比 chosen 多，loss 就下降。本节实测 12 个 chosen 中 10 个的 log-prob 下降（平均 −8.5），rejected 平均 −107。
- **为什么会发生**：chosen 与 rejected 往往共享大量前缀、词汇和格式，压低 rejected 的梯度通过共享参数也压低了 chosen；当 margin 已经很大时，进一步降低两者的概率仍可能降低 loss。概率质量被挪到了**两者之外**的序列上。
- **风险**：模型对"好回答"本身的似然下降，可能生成训练数据之外的、不可预期的内容；在数学/代码等需要精确答案的任务上可能变差；过度优化后输出变长或变怪。
- **对策**：在 loss 中加入 chosen 的 SFT/NLL 项（如 DPO + λ·NLL(y_w)）；较大的 β 或早停；IPO/label smoothing 限制 margin；监控 chosen 与 rejected 的绝对 log-prob、隐式奖励的准确率与 margin、与参考模型的 KL。
- 加分：说出"likelihood displacement / 概率挤出"这一现象的名字，并给出监控指标。

### Q16 — 参考回答要点

- **显存**：策略需要梯度与优化器状态，参考模型只做前向。可以①把参考模型放在低精度或另一张卡；②像本节一样**预先计算并缓存**所有参考 log-prob（数据集固定时最省事）；③用 LoRA 训练策略，此时"关闭 LoRA 适配器"即为参考模型，不必加载两份权重。
- **数据**：偏好对质量比数量重要；chosen 与 rejected 应来自相近的分布（最好由 SFT 模型自己采样再标注），避免长度、格式等"捷径"——本节 fixture 中 chosen 一律更短，就是典型的捷径；检查数据中两者长度分布。
- **模板一致**：prompt 必须与 SFT 时的 chat 模板一致，completion 包含 EOS；只对 completion 计分。
- **超参**：β 常见在 0.1 左右起步（视实现而定，要在验证集上调）；学习率比 SFT 更小；1–3 个 epoch，过多 epoch 容易过度优化（本节 30 epoch 在 12 条数据上已严重过拟合）。
- **监控**：loss、隐式奖励准确率（`margin > 0` 的比例）、平均 margin、chosen/rejected 的绝对 log-prob、与参考模型的 KL、生成长度；定期在固定 prompt 集上生成并用 judge/人工评估。
- **批处理**：chosen 与 rejected 拼成一个 batch 一次前向；超长样本截断 completion 尾部而非 prompt。

### Q17 — 参考回答要点

- **过度优化 / 饱和**：sigmoid loss 在小数据上会把 margin 推得很大（本节 margin ≈ 98、loss ≈ 0），rejected 被无限压低。→ **IPO** 用平方损失把 margin 拉向固定目标 `1/(2β)`（本节实测稳定在约 2.5）；**早停**、较大的 β。
- **标签噪声**：人类偏好不一致，错误标签在 DPO 中会被"无限信任"。→ **label smoothing（cDPO）**：在 z 很大时 loss 反而上升，最优 margin 有限（ε = 0.1 时 `z* = log 9 ≈ 2.2`）。
- **长度偏差**：对数概率求和让长度与 margin 纠缠；如果偏好数据中 chosen 普遍更长（常见于真实数据），DPO 会把模型推向冗长；若普遍更短（本节），则推向简短。→ **长度归一化**，或在数据层面平衡长度、加入长度惩罚。
- **chosen 似然下降**：见 Q15。→ 加 NLL 正则项。
- **分布偏移**：离线数据不是当前策略生成的。→ 迭代/在线 DPO：用当前模型采样、重新标注、再训练。
- **参考模型选择**：讲义 stretch goal 4 用更小的参考模型（蒸馏风格），可以省显存，但会改变 KL 锚点的含义，需要重新调 β。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 39 通过监督式 Fine-Tuning 进行指令微调](../../39-instruction-tuning-sft/docs/zh.md)：DPO 的参考模型通常就是 SFT 模型；本节 `TinyGPT` 与 tokenizer 与第 39 节同构。
- [阶段 19 · 35 组装 GPT 模型](../../35-gpt-model-assembly/docs/zh.md)：decoder-only 结构与因果 mask。
- [阶段 10 · 07 RLHF: Reward Model + PPO](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)：DPO 所替代的经典流程，Bradley-Terry 奖励模型与 KL 约束。
- [阶段 10 · 08 DPO：直接偏好优化](../../../10-llms-from-scratch/08-dpo/docs/zh.md)：DPO 的概念与推导。
- [阶段 09 · 09 奖励建模 & RLHF](../../../09-reinforcement-learning/09-reward-modeling-rlhf/docs/zh.md)：奖励模型与偏好学习的强化学习背景。

### 本节被哪些后续内容用到
- [阶段 19 · 41 完整 Evaluation 流程](../../41-eval-pipeline/docs/zh.md)：用更完整的评估判断 DPO 前后的真实效果，而不只看 margin。
- [阶段 18 · 03 直接偏好优化方法家族](../../../18-ethics-safety-alignment/03-direct-preference-optimization-family/docs/zh.md)：IPO、KTO、ORPO 等变体的系统介绍。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：过度优化与本节 margin 失控的关系。
- [阶段 18 · 04 RLHF 对迎合行为的放大效应](../../../18-ethics-safety-alignment/04-sycophancy-rlhf-amplification/docs/zh.md)：偏好优化可能放大的行为偏差。
- [阶段 19 · 07 端到端 Fine-Tuning 流程](../../07-end-to-end-fine-tuning-pipeline/docs/zh.md)：数据 → SFT → DPO → 服务的完整工程流程。

### 延伸关键词
`Bradley-Terry` · `implicit reward` · `KL-regularized RL` · `partition function Z(x)` · `β (KL strength)` · `reference model` · `IPO` · `cDPO / label smoothing` · `length normalization` · `SimPO` · `likelihood displacement` · `online / iterative DPO` · `reward hacking` · `logsigmoid`
