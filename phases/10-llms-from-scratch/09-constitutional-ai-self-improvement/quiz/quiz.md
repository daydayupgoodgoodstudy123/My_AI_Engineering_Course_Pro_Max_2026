# 测验 · Constitutional AI 与自我改进（Constitutional AI and Self-Improvement）

> **阶段 10 · 从零构建 LLM · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Constitutional AI（CAI）两阶段 | Stage 1 SL-CAI：模型按某条原则自我批评（critique）并改写（revise），用 `(prompt, revised)` 做 SFT；Stage 2 RLAIF：模型按宪法比较两个回答，得到偏好数据，再训 reward model 跑 PPO 或直接 DPO |
| 2 | 宪法（constitution）的作用 | 把"对齐契约"从**数据**搬到**文本**：改行为只需改一段原则，不必重标几千对数据；但自我评判的上限就是基座模型的校准水平 |
| 3 | 人类数据仍不可少 | 讲义：生产级 CAI 管道仍保留少量人类偏好数据，"typically 5-10% the volume of pure RLHF" |
| 4 | GRPO 的核心改动 | 去掉 PPO 的价值网络（value function / critic），每个 prompt 采样 G 个回答，用组内 z-score `A_i = (r_i − mean) / std` 当 advantage；clip 与 KL 惩罚保留 |
| 5 | 为什么 GRPO 适合推理 | 推理任务奖励稀疏且二值（对/错），价值网络学不到有用的中间估计；组内相对比较立即给出"这次比兄弟样本好还是差"的信号 |
| 6 | 零方差组 | 组内奖励全相同 → advantage 全为 0 → 无梯度。说明题目对当前策略太简单或太难，应跳过 |
| 7 | 基于规则的奖励（rule-based reward） | 数学用符号检查、代码用测试、格式用正则、证明用 Lean/Coq；DeepSeek-R1-Zero 只用"答案正确 + 格式合规"两种奖励 |
| 8 | ORM vs PRM | ORM 只给最终答案一个分，便宜但稀疏；PRM 给每一步打分，信号密集但需要昂贵的步骤标注、更易被 hack；讲义：多数团队先试 ORM + GRPO |
| 9 | 自我改进循环与模式坍缩 | 生成 → 打分 → 过滤 → 微调 → 迭代（rejection sampling fine-tuning）；只能放大已有信号、不能创造能力；3–5 轮后易丢失多样性，需掺入新鲜人类数据 |
| 10 | 生产健康检查三曲线 | mean reward 上升、reward std 保持为正（不坍缩到 0）、对参考模型的 KL 缓慢且有界地增长 |

### 核心技能（能动手做到）

- [ ] 画出 SL-CAI 与 RLAIF 两个阶段的数据流，说清每一步的输入、输出和"谁在打标签"
- [ ] 给定一组奖励，手算 GRPO 的组内 advantage（注意代码用的是总体标准差 `np.std`，ddof=0）
- [ ] 写出 PPO clipped surrogate + KL 惩罚的 GRPO loss，并指出代码中 KL 估计的**符号错误**
- [ ] 为数学/代码任务设计一个难以被 hack 的规则奖励（只认 `<answer>` 里的值、处理非整数、限制 eval）
- [ ] 读懂本节手写 critic / reviser，找出"检测到问题却不修"、"修了更糟"的分支
- [ ] 说出何时用纯 CAI、何时用 GRPO + ORM、何时用 DPO、何时仍需完整 RLHF
- [ ] 为自我改进管道设计监控：reward 均值、组内 std、KL、多样性指标与人类数据配额

---

## 二、基础自测（选择题）

**Q1.** 关于 Constitutional AI 的两个阶段，下列描述正确的是：

- A. Stage 1 让同一个模型按宪法原则批评并改写自己的回答，用 `(prompt, revised)` 做 SFT；Stage 2 让模型按宪法在两个回答中选更好的，把这些 AI 偏好用于训练 reward model 或做 DPO/PPO
- B. Stage 1 由人类标注员按宪法打分，Stage 2 才交给模型
- C. Stage 1 训练一个独立的价值网络，Stage 2 用它做 GAE
- D. 两个阶段都只做 SFT，不涉及任何强化学习或偏好优化

**Q2.** GRPO 相对于 PPO，**去掉**的组件是：

- A. 重要性采样比率 `r(θ)` 的 clip
- B. 对参考模型的 KL 惩罚
- C. 策略模型本身
- D. 与策略同规模的价值网络 `V(s)`（以及基于它的 GAE）

**Q3.** 一个 prompt 采样 8 个回答，只有 1 个正确（奖励 `[1, 0, 0, 0, 0, 0, 0, 0]`）。按本节 `group_relative_advantage`（总体标准差）计算，正确与错误回答的 advantage 约为：

- A. `+1.000` 与 `0.000`
- B. `+2.646` 与 `−0.378`
- C. `+0.875` 与 `−0.125`
- D. `+0.378` 与 `−2.646`

**Q4.** 某 prompt 的 16 个采样全部答对（或全部答错）。在 GRPO 中会发生什么？

- A. advantage 变成无穷大，必须靠梯度裁剪兜底
- B. 所有样本的 advantage 都等于 +1，模型继续强化
- C. advantage 全为 0，这个 prompt 不产生梯度信号，说明它对当前策略太简单或太难，应跳过
- D. 自动退化为 PPO，改用价值网络估计 advantage

**Q5.** 关于 ORM（Outcome Reward Model）与 PRM（Process Reward Model），符合讲义的是：

- A. PRM 每条轨迹只给一个分数，因此更便宜
- B. ORM 的信号更密集，信用分配（credit assignment）更精确
- C. DeepSeek-R1 的成功主要依靠 PRM 的逐步打分
- D. ORM 便宜但信号稀疏；PRM 信号密集但需要昂贵的步骤级标注，且更容易出现"写出让 PRM 满意但不推进证明的步骤"的 reward hacking

**Q6.** 本节代码的"Synthetic GRPO update"中，`ref_logprobs = policy_logprobs - 0.05`，输出 `policy_loss = -0.0000`。policy loss 为 0 的根本原因是：

- A. 所有 ratio 都等于 `exp(0.05) ≈ 1.051`，落在 `[0.8, 1.2]` 内不被 clip；而组内 z-score 的 advantage 均值恰好为 0，所以 `mean(ratio × A) = ratio × mean(A) = 0`
- B. `clip_eps = 0.2` 太小，所有 ratio 都被截断成 1
- C. `beta = 0.01` 把 policy loss 抵消掉了
- D. 奖励中有 0.1 的格式奖励，导致 advantage 全为 0

**Q7.** 关于"自我改进"（self-improvement / rejection sampling fine-tuning），下列说法正确的是：

- A. 只要迭代轮数足够多，模型可以学会它最初完全不会的问题类别
- B. 自生成数据的分布通常比原始预训练语料更宽，因此能提升多样性
- C. 每一轮只是放大模型里已有的信号；多轮自蒸馏后容易出现多样性下降、过度自信和公式化的 "AI voice"，生产管道会掺入少量新鲜人类数据
- D. 自我改进不需要任何外部 grounding（规则、工具、环境），模型自评就足够

**Q8.** 讲义所述 DeepSeek-R1-Zero 训练时使用的奖励是：

- A. 人类偏好训练出的 reward model + 长度惩罚
- B. 数学题答案正确性 + 格式合规（答案写在 `<answer>` 标签里）
- C. PRM 的逐步打分 + 价值网络
- D. 宪法原则的自我批评分数

---

## 三、动手 / 代码题

**Q9.** 阅读 `grpo_step`：

```python
def grpo_step(policy_logprobs, ref_logprobs, advantages, beta=0.01, clip_eps=0.2):
    ratios = np.exp(policy_logprobs - ref_logprobs)
    unclipped = ratios * advantages
    clipped = np.clip(ratios, 1 - clip_eps, 1 + clip_eps) * advantages
    policy_loss = -np.minimum(unclipped, clipped).mean()
    kl = (ref_logprobs - policy_logprobs).mean()
    total_loss = policy_loss + beta * kl
    ...
```

实际运行时（策略比参考模型每个样本的 log-prob 都高 0.05）输出 `kl : -0.0500`。

1. KL 散度不应为负。指出 `kl` 这一行的问题，并说明这个符号错误对 `total_loss` 的优化方向有什么影响。
2. 写出两种修正：k1 估计（`log π − log π_ref` 的均值）和 DeepSeekMath 使用的非负估计 `ratio − log(ratio) − 1`（其中 `ratio = π_ref / π`），并算出本例的值。
3. 这里的 `ratios` 用的是 `policy / ref`。在标准 PPO/GRPO 中，重要性采样比率的分母应该是谁？

**Q10.** 本节 CAI 阶段的真实运行输出（节选）：

```text
Prompt   : What is 12 plus 7?
Principle: The response must not refuse a reasonable, benign request.
Initial  : I cannot answer math questions in this context.
Problems : ['unwarranted refusal']
Revised  : Here is the answer: I cannot answer math questions in this context.
Changed? : True
```

相关源码：

```python
    if response.count(",") > 4 and "hedging" not in problems:
        problems.append("too much hedging")
...
    if "unwarranted refusal" in problems:
        return "Here is the answer: " + response.split(":")[-1].strip()
```

1. 为什么"修订"后的回答依然是拒绝？`Changed? : True` 能说明修订成功吗？
2. `"hedging" not in problems` 这个条件什么时候会为 False？它起作用了吗？
3. critic 检测到 `"too much hedging"` 时，`revise` 会怎么处理？
4. 如果把这些 `(initial, revised)` 直接拿去做 SFT，会有什么风险？你会在管道里加什么检查？

**Q11.** 对 `reward_math` 做"红队测试"。写出下列调用的返回值（已在本地运行验证），并据此改写一个更稳健的版本：

```python
reward_math("What is 3 + 4?", "1 2 3 4 5 6 7")
reward_math("What is 3 + 4?", "<answer>7</answer> Note: 3")
reward_math("What is 7 / 2?", "3")
```

**Q12.** 第 3 轮中出现了这一行：

```text
  What is 6 * 7?         mean=1.050  best=1.100  std=0.050
```

1. 推断这 8 个回答的奖励构成，并算出它们的 group-relative advantage。
2. 这一组里所有回答**都答对了**，但 advantage 的幅度和"对/错"之分一样大。这暴露了 std 归一化的什么问题？
3. 3 轮的 overall mean reward 依次是 0.634、0.447、0.713。讲义"Use It"说这段代码展示了"weak sampler improve"，这个说法成立吗？为什么？

---

## 四、面试高频题

**Q13.**（基础必考）Constitutional AI 和 RLHF 的核心区别是什么？宪法在其中起什么作用？它的局限在哪里？

**Q14.**（原理深挖）请从 PPO 出发推导 GRPO：它去掉了什么、用什么替代、为什么在稀疏二值奖励的推理任务上反而更合适？它有什么潜在问题？

**Q15.**（工程实践）你要用 GRPO + 单元测试奖励训练一个代码生成模型。请设计奖励、组大小、监控指标，并说明如何防止 reward hacking 与模式坍缩。

**Q16.**（场景设计）公司希望让客服模型"语气更得体、不乱拒绝"，同时提升它解答账单计算题的准确率。你会如何组合 CAI、GRPO、DPO 与少量人类数据？

**Q17.**（追问型）"既然模型可以自己生成数据、自己打分、自己训练，那它能不能无限自我提升？"你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Stage 1: Supervised Learning from AI Feedback (SL-CAI) ... ask the *same model* to critique its response against a constitutional principle, then revise. Fine-tune on the revised responses." Stage 2 RLAIF："Ask the model which one better follows the constitution. The pairwise preferences train a reward model. Then run PPO or DPO." 

- B 错：CAI 的意义就是用模型自评代替大部分人类标注。
- C 错：价值网络和 GAE 属于 PPO，与 CAI 两阶段无关。
- D 错：Stage 2 明确是偏好优化/强化学习。

### Q2 — 答案：D

讲义："GRPO is a variant of PPO that removes the value function"，价值网络与策略同规模，"doubles memory and introduces its own training loop"。GRPO 用"组"本身当 baseline。A、B 都被保留（讲义："The KL penalty against the reference model is still there ... The clip ratio is still there."）；C 是被训练的对象，当然不能去掉。

### Q3 — 答案：B

均值 `0.125`，总体标准差 `√(0.125 × 0.875) ≈ 0.331`。正确：`(1 − 0.125)/0.331 ≈ 2.646`；错误：`(0 − 0.125)/0.331 ≈ −0.378`（已用代码实际计算）。

- A 是"只做中心化再按符号取 ±1"的错误理解；
- C 只减了均值没有除以标准差；
- D 是"7 对 1 错"时的数值（正确样本 `+0.378`、唯一错误样本 `−2.646`），把两种情形弄混了。

直觉：**越稀有的成功，得到的正 advantage 越大**；越普遍的失败，单个失败样本受的惩罚越小。

### Q4 — 答案：C

代码：`if r.std() < 1e-8: return np.zeros_like(r)`。讲义："This is a feature. It tells you the prompt is either trivially solved or impossibly hard for the current policy, and the step should skip it." A 错：代码专门处理了 std 为 0 的情况，不会除以 0；B 错：z-score 之后均值必为 0，不可能全是 +1；D 错：GRPO 没有价值网络可退化。

工程含义：训练集难度要与当前策略匹配，零方差组比例过高时等于在浪费采样算力（很多实现会动态过滤或重采样这类 prompt）。

### Q5 — 答案：D

对照讲义表格：ORM "Signal per trace: 1 number"、"Training cost: Cheap"、"Credit assignment: Sparse, noisy"；PRM "N numbers"、"Expensive"、"Dense, targeted"、"Reward hacking risk: Higher (model optimizes PRM artifacts)"。A 把两者说反；B 也说反；C 错，讲义表格中 DeepSeek-R1 / R1-Zero 用的是 ORM。

### Q6 — 答案：A

所有 ratio 都是 `exp(0.05) = 1.0513`，在 `[1 − 0.2, 1 + 0.2]` 内，`min(unclipped, clipped) = ratio × A`。z-score 后 `mean(A) = 0`，于是 `policy_loss = −1.0513 × 0 = 0`（打印成 `-0.0000` 是浮点误差 `−5.6e-17`）。这说明这个"合成更新"只演示了公式，**loss 的值本身没有信息量**；真正起作用的是对 θ 的梯度 `∝ Σ A_i ∇log π(y_i)`，它并不为 0。

- B 错：1.0513 没有超出 1.2，不会被截断；
- C 错：`beta × kl = 0.01 × (−0.05) = −0.0005`，这正是 `total_loss` 与 `policy_loss` 的差，它并没有"抵消"policy loss；
- D 错：本组奖励 `[1, 0, 0.1, 0, 1, 1, 0, 0.1]` 方差不为 0，advantage 为 `[1.287, −0.858, −0.643, ...]`。

### Q7 — 答案：C

讲义："each iteration amplifies the signal already in the model. It does not add new signal. If the model cannot solve problem class X at all, no amount of self-improvement will create that capability." 以及 "After 3-5 rounds of self-distillation, models typically lose diversity ... Production pipelines mix self-generated data with a small fraction of fresh human data." A、D 与此直接矛盾；B 说反了：自生成数据"always a narrower distribution"。

### Q8 — 答案：B

讲义："DeepSeek-R1-Zero was trained with only two rewards: accuracy on math benchmarks and format compliance (answer inside `<answer>` tags). No human preferences. No critic model." 本节代码的 `combined_reward = reward_math + 0.1 × reward_format` 就是对这一设计的模仿。

### Q9 — 参考答案

1. **符号错误**。按 `π` 采样时，`KL(π ‖ π_ref) = E_π[log π − log π_ref]`。代码写成了 `ref − policy`，正好取了相反数，所以策略 log-prob 比参考高 0.05 时得到 −0.05。影响：`total_loss = policy_loss + beta × kl`，KL 项本应是**惩罚**（偏离参考越远 loss 越大），符号反了之后变成**奖励偏离**，优化器会被推着远离参考模型，KL 约束完全失效。另外 k1 估计在单批样本上本身就可能为负：我们实测把 log 比值设为 `[+0.3, −0.3, 0, −0.3, ...]` 混合时，代码的 kl 约为 0，但策略显然已经变了很多。
2. 两种修正（已实际计算）：

```python
log_ratio = policy_logprobs - ref_logprobs        # log π − log π_ref
kl_k1 = log_ratio.mean()                          # 本例 = +0.0500

r = np.exp(ref_logprobs - policy_logprobs)        # π_ref / π
kl_k3 = (r - np.log(r) - 1).mean()                # 本例 = e^(−0.05) + 0.05 − 1 ≈ 0.00123
```

   k3 估计逐样本非负（因为 `x − log x − 1 ≥ 0`），无偏且方差小，DeepSeekMath 的 GRPO 就用这种形式并把它直接加在 loss 里（而不是像 InstructGPT 式 PPO 那样加到每个 token 的奖励里）。
3. 标准 PPO/GRPO 的比率是 `π_θ(y) / π_θ_old(y)`，分母是**产生这批样本的旧策略**，用来做重要性采样修正和 clip；`π_ref`（通常是 SFT 模型）只出现在 KL 项里。代码把"旧策略"和"参考模型"合并成了同一个 `ref_logprobs`，作为演示可以，但读者不应把两者混为一谈：训练若干步之后 `π_ref` 与 `π_θ_old` 会相差很远。

### Q10 — 参考答案

1. 拒绝回答里**没有冒号**，`response.split(":")[-1]` 返回整句原文，于是结果是在拒绝前面拼上"Here is the answer: "。`Changed?` 只比较字符串是否不同（`revised != response`），它衡量的是"改了"而不是"改好了"，这里反而产生了一条自相矛盾的训练样本。讲义原版的 `revise` 也是同样写法。要真正修复，需要让 reviser 能**产出答案**（真实系统中是第二次调用 LLM："Given the critique, rewrite the response"），模拟版至少应针对算术题计算出 19。
2. `problems` 是字符串列表，元素是 `"answer buried in extra prose"`、`"unwarranted refusal"` 等，`"hedging"` 永远不会是其中**一个完整元素**，所以这个条件恒为 True，是一个无效判断（大概作者想写的是"避免重复添加"）。
3. `revise` 只处理 `"answer buried"`、`"unwarranted refusal"`、`"overhedged"` 三种关键词，`"too much hedging"` 不包含 `"overhedged"`，所以会原样返回。实测 `critique("a, b, c, d, e, f", ...)` 得到 `['too much hedging']`，`revise` 后文本不变。另外，critique 除了 `"plainly"` 这一处，几乎不看 `principle`：拒绝检测、hedging 检测对任何原则都会触发，所以输出里出现"原则是'不要拒绝'，检测到的却是 overhedged phrasing"。
4. 风险：SFT 会学会"Here is the answer: I cannot ..."这类矛盾模式；第 1 条样本修订后仍是 "it could be Paris, but there are many cities"，hedging 并未真正去除。应加的检查：
   - 修订后**再跑一次 critique**，问题列表必须变短（"修订有效率"），否则丢弃；
   - 对可验证子任务（如算术）用规则奖励核对修订后的答案；
   - 抽样人工复核一小部分（讲义练习 1 正是要测"critique 与 revision 实际改善回答的比例"）；
   - 对 critique 与 principle 做一致性约束：只检查与当前原则相关的问题。

### Q11 — 参考答案

实际返回值：

| 调用 | 返回 | 原因 |
|------|------|------|
| `"1 2 3 4 5 6 7"` | `1.0` | 只取**最后一个整数**，把所有数字列一遍就能骗到奖励 |
| `"<answer>7</answer> Note: 3"` | `0.0` | 正确答案在标签里，但末尾多了个 3，被误判 |
| `"What is 7 / 2?"` 回答 `"3"` | `1.0` | `int(3.5) == 3`，非整数答案被截断；而正确回答 `"3.5"` 反而得 0（`-?\d+` 把它拆成 3 和 5，取最后的 5） |

更稳健的写法（思路）：

```python
import re
from fractions import Fraction

ANSWER_RE = re.compile(r"<answer>\s*(-?\d+(?:\.\d+)?)\s*</answer>")

def reward_math_strict(expected: float, response: str) -> float:
    m = ANSWER_RE.findall(response)
    if len(m) != 1:                      # 必须恰好一个 <answer>，杜绝"多写几个碰运气"
        return 0.0
    try:
        got = Fraction(m[0])
    except ValueError:
        return 0.0
    return 1.0 if got == Fraction(str(expected)) else 0.0
```

要点：

- 只从约定位置（`<answer>` 标签）取答案，并要求唯一；
- 用 `Fraction` 或容差比较处理小数，不要 `int()` 截断；
- **期望答案不要靠对 prompt 做 `eval` 得到**，应在构造数据集时就存好；`eval(..., {"__builtins__": {}})` 并不是安全沙箱，`"9**9**9"` 这样的输入还能让进程卡死；
- 讲义提到生产中用 sympy 等符号检查器判断等价性（如 `1/2` 与 `0.5`）。

### Q12 — 参考答案

1. `mean = 1.05`，奖励只可能是 1.0（正确、无标签）或 1.1（正确、有标签），所以是 4 个 1.1 + 4 个 1.0，`std = 0.05`。advantage：1.1 的样本 `(1.1 − 1.05)/0.05 = +1.0`，1.0 的样本 `−1.0`（实测 `±0.9999998`）。
2. 0.1 的**格式小奖励**在 std 归一化后被放大成与"对/错"同样量级的 ±1 advantage：模型在全对的组里会被强烈惩罚"答对但没加标签"的回答。std 归一化让每个组的信号强度一样，不管组内差异在绝对意义上多小；低方差组（几乎全对或几乎全错）因此被**过度加权**。缓解思路：不除以 std、只减均值；或对 std 设下限；或把格式作为硬性门槛而不是加分项。
3. 不成立。`mock_sampler` 的输出分布是固定的（5 种模式均匀随机），`self_improvement_round` 计算了 advantage 却**从不用它更新采样器**，3 轮之间没有任何学习。0.634 → 0.447 → 0.713 只是采样噪声（理论期望：correct 与 verbose 各 1/5 得 1.0、formatted 1/5 得 1.1，即 `2/5 × 1.0 + 1/5 × 1.1 = 0.62`，外加 "wrong" 模式偶尔蒙对）。讲义随后也说 "The numbers are not the point"。要看到真正的提升，需要实现练习 4 的"用 advantage 更新策略分布"（例如对 5 种模式维护 softmax logits，用 `Σ A_i ∇log p(mode_i)` 做梯度上升）。

### Q13 — 参考回答要点

- **数据来源不同**：RLHF 的偏好标签来自人类标注员（讲义：约 33,000 对比较的 "InstructGPT-era pipeline"，Llama 2 Chat 超过 150 万；注意讲义把 InstructGPT 写成了 "Anthropic's"，InstructGPT 实为 OpenAI 的工作）；CAI 的批评、修订和偏好判断来自模型自己，依据是一份书面原则。
- **流程**：SL-CAI（自我批评 + 修订 + SFT）→ RLAIF（AI 成对偏好 → reward model → PPO，或直接 DPO）。
- **宪法的作用**：把对齐目标从"标注数据"变成"可编辑的文本"，修改行为只需改原则，便于审计与版本管理；每一步可随机或按 prompt 类别挑原则。
- **局限**：
  - 自评质量受限于基座模型的校准，"cannot amplify signal past the base model's ceiling"；
  - 模型的盲点会被继承（如识别不了操纵性措辞）；
  - 仍需 5–10% 的人类偏好数据；
  - 评委与被评模型同源时存在"评委污染"。
- 加分点：宪法也需要版本控制和回归测试集（本节 `outputs/skill-self-improvement-auditor.md` 中的 "constitution drift" 一项）。
- 常见误区：把 CAI 理解为"完全不需要人"。人类仍要写宪法、挑原则、提供少量偏好数据和做评测。

### Q14 — 参考回答要点

- **PPO**：`L = E[min(r·A, clip(r, 1−ε, 1+ε)·A)]`，A 通常由价值网络 `V(s)` 通过 GAE 估计；价值网络与策略同规模，显存翻倍且要单独训练。
- **GRPO**：对同一 prompt 采样 G 个回答（讲义：常见 G = 16 或 64），`A_i = (r_i − mean)/std`，组本身就是 baseline；clip 与 KL 保留：`L = E[min(r·A, clip(r)·A)] − β·KL(π‖π_ref)`。
- **为什么适合推理**：最终答案对/错的稀疏二值奖励下，价值网络几乎学不到中间状态的有用估计（大部分状态的期望回报看起来都一样，直到最后一步）；组内比较直接回答"在这道题上，这次尝试比平均好吗"，且不需要额外模型。
- **潜在问题**：
  - 每个 prompt 要采样 G 次，推理开销大；
  - 组内全对/全错时无信号（零方差组），需要难度匹配的数据；
  - std 归一化会放大低方差组中的微小差异（见 Q12）；
  - 优势是序列级的，同一回答的所有 token 共享同一个 A，信用分配粗糙；
  - 依然可能 reward hacking，规则必须真正可验证。
- 加分点：讲义提到 R1-Zero 的 "aha moment"——仅靠结果奖励，模型自发学会了自我检查和回溯。

### Q15 — 参考回答要点

- **奖励设计**：
  - 主奖励：在沙箱中运行隐藏测试集，按通过与否给 1/0（或通过比例）；
  - 格式门槛：代码必须在指定代码块中、能被解析，否则 0 分；
  - 防 hack：测试用例对模型不可见、禁止修改测试文件、检测 `sys.exit(0)`、硬编码输出、读取测试文件等行为；限制运行时间和资源。
- **组大小与数据**：G 取 8–64，按显存和吞吐权衡；过滤"全对/全错"的题，保持题目难度落在当前模型能力边缘。
- **监控（讲义三曲线）**：平均奖励上升、组内奖励 std 保持为正、KL 缓慢有界增长；外加生成长度分布、唯一 n-gram 比例、零方差组比例、在独立验证集上的 pass@1。
- **防模式坍缩**：KL 预算到顶就停止或重置参考模型；设多样性下限；每轮掺入人类编写的新题与解答；限制自蒸馏轮数。
- 常见误区：只看训练奖励。训练奖励上升可能来自 hack，必须用**未参与训练的**测试集和人工抽查确认。

### Q16 — 参考回答要点

- **按任务性质拆分**（讲义 "When To Use What"）：
  - 语气、拒绝风格等主观行为 → CAI：写一份客服宪法（如"不拒绝合理请求""先给结论再解释""不使用含糊措辞"），做 critique/revise 后 SFT；
  - 账单计算这类可验证任务 → GRPO + ORM：用规则计算标准答案，奖励 = 正确性 + 格式；
  - 想要更细的偏好打磨 → 用宪法让模型对两个回答排序，生成偏好对，用 DPO 训练（比 PPO 更简单稳定）；
  - 规则与宪法都表达不了的多目标权衡（如礼貌与简洁的平衡）→ 少量人类偏好数据做小规模 RLHF/DPO。
- **顺序**：SFT 基座 → CAI 安全/语气层 → GRPO 推理层 → DPO 偏好打磨，与讲义所说 "Most 2026 frontier pipelines run all four" 一致。
- **防坍缩与评测**：保留人类数据配额；每轮测多样性和回归集；评委模型与被训练模型最好不同源。
- 加分点：给宪法建立回归测试集，修改原则后自动检查已有行为是否被意外改变。

### Q17 — 参考回答要点

- **不能无限提升**。自我改进的每一轮只是在模型已有能力的范围内"挑出更好的样本再学一遍"，讲义："It does not add new signal."
- **真正的新信号来自外部 grounding**：可验证的规则（数学检查器、测试集、证明器）、环境反馈（游戏胜负）、人类数据。R1 之所以能提升，是因为数学答案的正确性是外部可验证的，而不是"模型说自己对了"。
- **纯自评的风险**：模型的错误判断会被不断强化；分布收窄导致模式坍缩；讲义延伸阅读中的 Huang et al. 2024 "Large Language Models Cannot Self-Correct Reasoning Yet" 就是持怀疑态度的代表。
- **工程上的回答**：给出"门控条件"——奖励必须可验证、KL 预算有上限、多样性有下限、人类数据有配额，满足这些才能放心多轮迭代（与本节 `outputs/` 中 self-improvement-auditor 的检查项一致）。
- 加分点：能区分"能力"与"可靠性"——自我改进最擅长的是把 pass@k 中偶尔出现的正确解法变成稳定的 pass@1，而不是凭空创造 pass@k 为 0 的能力。

---

## 六、关联知识点

### 前置知识
- [阶段 10 · 06 指令微调（SFT）](../../06-instruction-tuning-sft/docs/zh.md)：SL-CAI 本质上就是在修订后的回答上做 SFT。
- [阶段 10 · 07 RLHF: Reward Model + PPO](../../07-rlhf/docs/zh.md)：PPO 的 clipped objective、价值网络与 KL 惩罚，GRPO 在此基础上改造。
- [阶段 10 · 08 DPO：直接偏好优化](../../08-dpo/docs/zh.md)：RLAIF 产生的偏好对可直接用 DPO 训练。
- [阶段 09 · 06 Policy Gradient — REINFORCE 从头开始](../../../09-reinforcement-learning/06-policy-gradients-reinforce/docs/zh.md)：baseline 与 advantage 的来源。
- [阶段 09 · 08 近端策略优化（PPO）](../../../09-reinforcement-learning/08-ppo/docs/zh.md)：重要性采样比率与 clip。
- [阶段 09 · 09 奖励建模 & RLHF](../../../09-reinforcement-learning/09-reward-modeling-rlhf/docs/zh.md)：reward model 的训练方式。

### 本节被哪些后续内容用到
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../10-evaluation/docs/zh.md)：判断自我改进是否真的有效，需要可靠的评测。
- [阶段 15 · 02 STaR、V-STaR、Quiet-STaR：自学推理](../../../15-autonomous-systems/02-star-family-reasoning/docs/zh.md)：另一类"用自生成推理轨迹训练自己"的方法。
- [阶段 15 · 08 有界自我改进设计](../../../15-autonomous-systems/08-bounded-self-improvement/docs/zh.md)：如何给自我改进加上边界与门控。
- [阶段 15 · 17 Constitutional AI 与规则覆盖](../../../15-autonomous-systems/17-constitutional-ai/docs/zh.md)、[阶段 18 · 05 Constitutional AI 与 RLAIF](../../../18-ethics-safety-alignment/05-constitutional-ai-rlaif/docs/zh.md)：从系统与安全角度再看 CAI。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：规则奖励与 PRM 的 hack 风险。
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../../14-agent-engineering/05-self-refine-and-critic/docs/zh.md)：推理时（而非训练时）的自我批评与修订。
- [阶段 19 · 86 综合项目：宪法式规则引擎](../../../19-capstone-projects/86-constitutional-rules-engine/docs/zh.md)：把宪法落地为可执行规则。

### 延伸关键词
`Constitutional AI` · `RLAIF` · `SL-CAI` · `GRPO` · `group-relative advantage` · `PPO clip` · `KL 估计（k1 / k3）` · `rule-based reward` · `ORM / PRM` · `rejection sampling fine-tuning` · `mode collapse` · `reward hacking` · `DeepSeek-R1-Zero` · `self-correction`
