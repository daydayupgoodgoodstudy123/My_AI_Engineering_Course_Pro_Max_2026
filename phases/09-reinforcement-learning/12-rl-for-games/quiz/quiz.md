# 测验 · 游戏强化学习——AlphaZero、MuZero 和 LLM 推理时代（RL for Games — AlphaZero, MuZero, and the LLM-Reasoning Era）

> **阶段 09 · 强化学习 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 统一视角 | self-play + search + policy improvement：自我对弈产生数据，搜索改进原始策略，网络监督学习搜索的输出 |
| 2 | AlphaZero | 单个 policy-value 网络 `f_θ(s) → (p, v)` + MCTS；以 MCTS 访问分布 π 为策略目标、对局结果 z 为价值目标；损失 `(v - z)² - πᵀlog p + c‖θ‖²` |
| 3 | PUCT | `a* = argmax Q(s,a) + c·p(a\|s)·√N(s) / (1 + N(s,a))`：平衡价值估计（利用）与先验/访问次数（探索） |
| 4 | MuZero | 不需要已知规则：学习潜空间模型 `h`（编码）、`g`（潜在状态转移 + 奖励）、`f`（策略 + 价值），MCTS 在学到的潜空间里进行；可用于棋类与 Atari |
| 5 | GRPO | 无 critic 的 PPO 变体：每个 prompt 采样 G 个回答，组相对优势 `A_i = (r_i - mean) / std`，加对参考策略的 KL；奖励来自验证器 |
| 6 | 为什么推理用 GRPO | 不训练价值网络省显存；组内基线天然处理"只在最后给奖励"的稀疏信号；按 prompt 归一化让难易不同的题目可比 |
| 7 | R1-Zero vs R1 | R1-Zero：基座直接 GRPO（准确性 + 格式奖励），学会长推理但可读性差；R1：冷启动 SFT → 推理 GRPO（加语言一致性奖励）→ 拒绝采样 + 第二轮 SFT → 全场景 GRPO |
| 8 | 蒸馏 | R1 的推理轨迹用于 SFT 小模型（学生端不做 RL）；讲义：强 RL 教师的蒸馏在学生规模上胜过从零 RL |
| 9 | 搜索 vs 无搜索 | 长视界完全信息博弈仍靠搜索（AlphaZero/MuZero）；LLM 推理在生产中尚无 MCTS，用完整 rollout 上的 GRPO + best-of-N；PRM 暗示步骤级搜索可能回归 |
| 10 | 领域地图 | 不完全信息博弈（扑克）用 CFR + 深度学习；大型多人策略游戏用 PPO + 自博弈 + 联盟；组合优化用 AlphaZero 变体（AlphaTensor、AlphaDev） |

### 核心技能（能动手做到）

- [ ] 手算一组 0/1 奖励的组相对优势，解释"全对/全错时优势为 0"的含义与后果
- [ ] 运行 `main.py`，解读 GRPO 的 reward 与 KL 曲线，以及与 REINFORCE 的对比
- [ ] 指出代码中 KL 项更新 `probs - probs_ref` 实际对应的是哪个方向的 KL，并写出 `KL(π_θ‖π_ref)` 对 logits 的精确梯度
- [ ] 识别"GRPO 每次更新用 8 个样本、REINFORCE 只用 1 个"导致的不公平比较，设计等样本预算的对照实验
- [ ] 写出 PUCT 选择函数，并说明 c、先验 p、访问次数 N 如何影响探索
- [ ] 能针对给定领域（围棋、扑克、Atari、数学推理、对话对齐）选择 AlphaZero / MuZero / CFR / GRPO / DPO

---

## 二、基础自测（选择题）

**Q1.** AlphaZero 训练策略头时使用的目标是：

- A. 人类棋谱中的落子
- B. MCTS 在该局面下的访问次数分布 π
- C. 网络自己输出的先验 p
- D. 对局结果 z

**Q2.** MuZero 相比 AlphaZero 最关键的变化是：

- A. 去掉了 MCTS
- B. 不再需要已知的游戏规则，而是学习一个潜空间动力学模型，在潜空间中搜索
- C. 改用人类数据预训练
- D. 只能用于 Atari

**Q3.** GRPO 中某个 prompt 采样 G=8 个回答，奖励全部为 1。这一组对参数更新的贡献是：

- A. 最大的正向更新
- B. 优势全为 0，几乎没有策略梯度信号（只剩 KL 项）
- C. 优势全为 1
- D. 会导致除零错误、训练崩溃

**Q4.** 关于 GRPO 相比 PPO 用于 LLM 推理的优势，下列说法**错误**的是：

- A. 不需要训练价值网络，省下大量显存
- B. 组内均值作为 baseline，天然适合只在回答末尾给出的稀疏奖励
- C. 按 prompt 归一化，难易不同的题目的优势可比
- D. 不需要任何奖励信号，也不需要采样

**Q5.** DeepSeek-R1-Zero 的主要问题是：

- A. 数学能力很差
- B. 推理链可读性差、混用语言、缺乏风格打磨
- C. 无法产生长推理链
- D. 需要人类偏好奖励模型

**Q6.** 对于扑克这类不完全信息博弈，讲义及其 skill 文件推荐的方法是：

- A. AlphaZero（PUCT + 自博弈）
- B. CFR（反事实遗憾最小化）+ 深度学习
- C. GRPO
- D. 纯 DQN

**Q7.** 讲义 Pitfalls 中关于 GRPO 组大小 G 的说法，正确的是：

- A. G=1 最好，节省计算
- B. G 太小时组 baseline 噪声大，优势信号不可靠；常用 G 在 8~64
- C. G 越大越好，没有代价
- D. G 只影响 KL，不影响优势

**Q8.** PUCT 公式 `Q(s,a) + c·p(a|s)·√N(s) / (1 + N(s,a))` 中，某个动作被访问得越多（N(s,a) 增大），其探索项会：

- A. 增大
- B. 减小，使搜索转向先验高但访问少的动作
- C. 不变
- D. 变为负数

---

## 三、动手 / 代码题

**Q9.**（手算）`grpo_step` 中的优势计算为：

```python
mean_r = sum(rewards) / G
var_r = sum((r - mean_r) ** 2 for r in rewards) / G
std_r = math.sqrt(var_r) + 1e-8
advs = [(r - mean_r) / std_r for r in rewards]
```

G=8，分别计算以下两组的优势：(a) 难题，`rewards = [1,1,0,0,0,0,0,0]`；(b) 易题，`rewards = [1,1,1,1,1,1,1,0]`。比较两组中"答对"与"答错"的优势大小，说明这种归一化对难题和易题分别意味着什么。

**Q10.**（找不一致）`grpo_step` 中 KL 惩罚的更新为：

```python
probs_ref = policy_probs(reference, p_idx)
kl = sum(p * (math.log(max(p, 1e-12)) - math.log(max(q, 1e-12))) for p, q in zip(probs, probs_ref))
...
for i in range(N_ANSWERS):
    theta[p_idx][i] -= beta * (probs[i] - probs_ref[i])
```

`kl` 统计的是 `KL(π_θ‖π_ref)`，讲义损失写的也是 `β·KL(π_θ‖π_ref)`。(a) `probs[i] - probs_ref[i]` 是哪个量对 logit `z_i` 的梯度？(b) 写出 `KL(π_θ‖π_ref)` 对 `z_i` 的精确梯度并改写这段更新。

**Q11.**（实验设计）`main` 中这样对比两种方法：

```python
theta_grpo, hist_grpo = train_grpo(updates=400, rng=random.Random(3))
theta_rf, hist_rf = train_reinforce(updates=400, rng=random.Random(3))
```

而 `grpo_step` 每次更新采样 `G=8` 个回答，`reinforce_step` 每次只采样 1 个。(a) 这个对比在"环境交互/采样预算"上公平吗？(b) 如果把 REINFORCE 增加到 3200 次更新（与 GRPO 的 400×8 样本数相同），你预计谁按样本数学得更快？为什么这并不否定 GRPO 在 LLM 上的价值？

**Q12.**（扩展）讲义练习 Hard：把回答扩展为两个 token 的"推理链"，验证器对**整对** token 打分。请写出 `grpo_step_chain` 的核心逻辑（策略可设为两步独立的 softmax：第一步依赖 prompt，第二步依赖 prompt 和第一个 token），并说明组优势如何"传播"到两个位置。

---

## 四、面试高频题

**Q13.**（基础必考）详细讲解 AlphaZero 的训练流程：网络结构、MCTS 如何使用 `(p, v)`、自博弈如何产生训练数据、损失函数各项的含义。为什么说 MCTS 是一个"策略改进算子"？

**Q14.**（原理深挖）MuZero 学习的 `h, g, f` 三个函数分别做什么？它的模型为什么不需要重建原始观测？相比 AlphaZero，它在什么场景下更有优势？

**Q15.**（结合大模型）写出 GRPO 的目标函数，解释组相对优势、KL 项的作用。与 PPO-RLHF 相比少了哪些组件？GRPO 有哪些已知的问题或坑？

**Q16.**（结合大模型）描述 DeepSeek-R1 的训练流程，并对比 R1-Zero。为什么 R1 还要做"拒绝采样 + 第二轮 SFT"？为什么小模型用蒸馏而不是直接 RL？

**Q17.**（场景设计）你要训练一个能写 Python 函数并通过单元测试的 7B 代码模型，用 GRPO。请设计奖励（验证器）、组大小、KL、长度处理和防作弊措施。

**Q18.**（追问型）面试官追问："讲义说 GRPO 是把 AlphaZero 的配方用到 LLM 推理上，但 GRPO 里根本没有搜索。你怎么理解这个类比？LLM 推理未来会引入 MCTS 吗？"

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："At move t, the MCTS visit distribution π_t becomes the policy training target." 价值头的目标才是对局结果 z（D）。C 是"自己学自己"，不会带来改进；A 是 AlphaGo（初代）用的，AlphaZero 强调"Zero human knowledge"。

### Q2 — 答案：B

讲义："MuZero ... Removes the requirement that the rules are known ... learn a latent dynamics model ... MCTS runs in the learned latent space." MuZero 仍然使用 MCTS（A 错），且同时适用于围棋、国际象棋、将棋和 Atari（D 错）。

### Q3 — 答案：B

全为 1 时 `mean_r = 1`、`var_r = 0`、`std_r = 1e-8`，每个优势是 `0 / 1e-8 = 0`，策略梯度项为 0，只剩 KL 项在起作用。代码中的 `+1e-8` 正是为了避免 D 中的除零。这是 GRPO 的已知性质：**全对或全错的组不提供学习信号**，因此要选择难度合适的题目（太简单或太难的题都在浪费采样）。

### Q4 — 答案：D

GRPO 每个 prompt 要采样 G 个回答，奖励来自验证器。A、B、C 正是讲义转述的 DeepSeekMath 中的三个理由："no value network to train, halving memory"、"the group baseline naturally handles the sparse end-of-trajectory reward"、"per-prompt normalization makes advantages comparable across problems of wildly different difficulty"。

### Q5 — 答案：B

讲义："The downside: its chains of thought are often unreadable, mix languages, and lack stylistic polish." R1-Zero 的数学分数接近 o1-preview 水平，回答长度大幅增长（A、C 错）；它的奖励是规则化的准确性 + 格式奖励，不是人类偏好 RM（D 错）。

### Q6 — 答案：B

讲义 Use It："Imperfect info card games (poker) | CFR + deep learning (DeepStack, Libratus, Pluribus)"；skill 文件："Refuse AlphaZero on imperfect-info games (route to CFR)." 原因是不完全信息下"状态"是信息集，最优策略往往是混合策略，单纯的树搜索 + 价值估计不再适用。

### Q7 — 答案：B

讲义："Below G = 4, the advantage signal is noisy; standard choice is G = 8 to 64." C 错：G 越大采样成本越高。（讲义原文说"Variance of the group baseline goes like 1/√G"，严格说是组均值的**标准误差**按 `1/√G` 下降，方差按 `1/G` 下降。）

### Q8 — 答案：B

探索项的分母是 `1 + N(s,a)`，访问越多探索加成越小；分子 `√N(s)` 随父节点总访问次数缓慢增长，使得长期没被访问的动作的探索加成逐渐变大。于是搜索会在"价值高的动作"（Q 大）和"先验高但还没怎么试的动作"之间平衡。

### Q9 — 参考答案

(a) 难题：`mean = 0.25`，`std = √(0.25×0.75) ≈ 0.433`。答对：`(1 - 0.25)/0.433 ≈ +1.732`；答错：`(0 - 0.25)/0.433 ≈ -0.577`。

(b) 易题：`mean = 0.875`，`std = √(0.875×0.125) ≈ 0.331`。答对：`(1 - 0.875)/0.331 ≈ +0.378`；答错：`(0 - 0.875)/0.331 ≈ -2.646`。

（已实际计算验证；两组的优势之和都为 0。）

含义：
- **难题**上少数答对的样本获得很大的正优势——"罕见的成功被强力强化"，这是 GRPO 能从稀疏奖励中学习的关键。
- **易题**上少数答错的样本获得很大的负优势——"偶发的失误被强力纠正"，而答对的样本只得到很小的正优势（本来就会做）。
- 如果不除以 std，难题与易题的优势量级完全取决于正确率，这就是讲义所说的"per-prompt normalization makes advantages comparable"。
- 副作用：std 很小时（几乎全对或全错）优势会被放大，噪声也被放大；也有研究讨论去掉 std 归一化的变体，这属于延伸阅读范畴。

### Q10 — 参考答案

(a) 设 `p = softmax(z)`、`q = π_ref` 固定。反向 KL `KL(q‖p) = Σ q_k log q_k - Σ q_k log p_k`，对 `z_i` 求导：`-Σ_k q_k(δ_ki - p_i) = p_i - q_i`。所以 `probs[i] - probs_ref[i]` 是 **`KL(π_ref‖π_θ)`**（即以参考策略为"数据"的交叉熵）的梯度，而不是代码打印的、讲义损失里写的 `KL(π_θ‖π_ref)`。用 logits `[1.0, -0.5, 0.3, 0.0]`、均匀参考做有限差分验证：`p - q = [0.229, -0.143, -0.012, -0.074]` 与 `∂KL(q‖p)/∂z` 完全一致，而 `∂KL(p‖q)/∂z = [0.241, -0.107, -0.047, -0.088]`。

两者都会把策略拉回参考策略，所以训练仍然有效，但"统计的 KL"和"优化的 KL"不是同一个量。

(b) 正向 KL 的精确梯度：

```text
∂KL(p‖q)/∂z_i = p_i · (log p_i - log q_i - KL(p‖q))
```

改写：

```python
probs_ref = policy_probs(reference, p_idx)
kl = sum(p * (math.log(max(p, 1e-12)) - math.log(max(q, 1e-12))) for p, q in zip(probs, probs_ref))
...
for i in range(N_ANSWERS):
    log_ratio = math.log(max(probs[i], 1e-12)) - math.log(max(probs_ref[i], 1e-12))
    theta[p_idx][i] -= beta * probs[i] * (log_ratio - kl)
```

验证方法：各分量之和应为 0（`Σ p_i·log_ratio_i - KL·Σp_i = KL - KL = 0`）。另外讲义 Step 3 的示例用的是 `theta -= beta * (theta - reference)`（logits 空间的 L2 拉回），与代码又不相同——三种写法都是"拉回参考"的正则，但只有上面这一种是讲义损失的精确梯度。真实的 GRPO 实现通常在每个 token 上用 `π_ref/π_θ - log(π_ref/π_θ) - 1` 这一无偏、非负的估计量来近似 `KL(π_θ‖π_ref)`。

### Q11 — 参考答案

(a) **不公平。** 400 次更新中 GRPO 消耗 `400 × 8 = 3200` 个样本（每个样本都要调用一次验证器），REINFORCE 只消耗 400 个。讲义 Step 4 写的是"Same setup, same compute"，但代码按"更新次数"而不是"样本数"对齐。

(b) 按样本数，REINFORCE 反而更快。实测 REINFORCE 跑 3200 次更新、每 400 个样本求一次平均奖励：`0.615, 0.927, 0.965, 0.983, …`；而 GRPO 对应的每 400 个样本：`0.355, 0.590, 0.782, 0.855, …`。原因：在这个只有 3 个 prompt、4 个答案的 bandit 上，REINFORCE 每个样本就做一次参数更新，更新次数是 GRPO 的 8 倍；GRPO 把 8 个样本平均成一次更新（`lr / G`），降低了方差，但在这种噪声本来就小的问题上，"多走几步"比"每步更准"更划算。

这不否定 GRPO 在 LLM 上的价值：
- LLM 上一次参数更新极其昂贵，而对同一 prompt 并行生成 G 个回答很便宜（共享 prompt 的 KV cache、批量推理），所以"每次更新用一组样本"是自然的；
- 真实 REINFORCE 没有 baseline 时方差极大（奖励全为正时会把所有采样到的回答都推高），在长序列上方差问题远比 bandit 严重；
- GRPO 要比较的真正对手是"带 critic 的 PPO"：省掉与策略同规模的价值网络。

正确的对照实验应当固定**样本预算**（或 wall-clock / FLOPs），并使用多个种子，报告学习曲线的均值与方差。

### Q12 — 参考答案

```python
def grpo_step_chain(theta1, theta2, rng, G=8, lr=0.1):
    # theta1[p][a1]：第一步 logits；theta2[p][a1][a2]：第二步 logits
    p_idx = rng.randrange(N_PROMPTS)
    probs1 = softmax(theta1[p_idx])
    group = []
    for _ in range(G):
        a1 = sample(probs1, rng)
        probs2 = softmax(theta2[p_idx][a1])
        a2 = sample(probs2, rng)
        r = verify_chain(p_idx, a1, a2)        # 验证器只看整条序列
        group.append((a1, probs2, a2, r))
    rewards = [g[3] for g in group]
    mean_r = sum(rewards) / G
    std_r = math.sqrt(sum((r - mean_r) ** 2 for r in rewards) / G) + 1e-8
    for a1, probs2, a2, r in group:
        A = (r - mean_r) / std_r               # 序列级优势
        for i in range(N_ANSWERS):             # 位置 1：∇log π(a1 | prompt)
            theta1[p_idx][i] += (lr / G) * A * ((1.0 if i == a1 else 0.0) - probs1[i])
        for i in range(N_ANSWERS):             # 位置 2：∇log π(a2 | prompt, a1)
            theta2[p_idx][a1][i] += (lr / G) * A * ((1.0 if i == a2 else 0.0) - probs2[i])
```

（已实测：取 3 个 prompt 的目标序列分别为 `(2,1)`、`(0,3)`、`(3,0)`，`theta1` 为 3×4、`theta2` 为 3×4×4 的全 0 初始化，2000 次更新中每 250 次的平均组奖励从约 0.29 升到约 0.99；随机猜中的概率只有 1/16。）

要点：
- 序列的对数概率是两步之和：`log π(o) = log π(a1|q) + log π(a2|q, a1)`，所以 `A·∇log π(o)` 自然分解为**同一个优势**乘以两个位置各自的梯度——这就是讲义提示的"compute group advantage per full sequence, propagate to both token positions"。
- 这正是 GRPO 在 LLM 上的做法：一个回答的所有 token 共享同一个（序列级）优势。代价是信用分配粗糙：如果第一个 token 对了、第二个错了，第一个 token 也会被惩罚，只能靠大量样本平均出来。PRM（过程奖励）就是为了提供更细的步骤级信号。
- 生产实现还会按回答长度归一化（讲义 Pitfalls 的 "Length bias"）。

### Q13 — 参考回答要点

- **网络**：一个塔 `f_θ(s) → (p, v)`，p 是合法动作上的先验，v 是当前局面的期望结果。
- **MCTS**：每步从根节点模拟若干次；选择阶段用 PUCT 选边（`Q + c·p·√N/(1+N_a)`）；到达叶子时用网络给出 `(p, v)` 展开并用 v 作为 bootstrap 值回传（不做随机 rollout）；回传更新路径上的 N 和 Q。
- **自博弈**：用 MCTS 的访问分布 `π_t`（可带温度）选择实际落子，一局结束得到结果 `z ∈ {+1, 0, -1}`，每一步产生训练样本 `(s_t, π_t, z)`。
- **损失**：`(v - z)²`（价值回归）、`-πᵀlog p`（让先验逼近搜索分布）、`c‖θ‖²`（L2 正则）。
- **为什么 MCTS 是策略改进算子**：用网络先验 + 价值做前瞻搜索得到的访问分布 π 通常比原始先验 p 更强；让 p 去拟合 π，相当于把搜索"蒸馏"进网络；更强的网络又让下一次搜索更强——这就是讲义统一循环中的 `policy_target = search.improved_policy(...)`。
- **加分点**：讲义 Pitfalls 的 "Search-policy mismatch"——网络太小无法表示搜索分布时训练会停滞；讲义提到 AlphaZero 各游戏用了几千万局自博弈。

### Q14 — 参考回答要点

- **三个函数**（讲义）：`h(s)` 把观测编码为潜在状态；`g(s_latent, a)` 预测下一个潜在状态和即时奖励；`f(s_latent)` 预测策略先验和价值。MCTS 在 `g` 展开的潜空间树上运行。
- **为什么不需要重建观测**：MuZero 的模型只被训练去预测对规划有用的量（奖励、价值、策略），而不是像素。潜在状态不必和真实状态一一对应，只要基于它做的搜索能给出正确的价值和策略即可。这省去了建模大量与决策无关的细节（如 Atari 背景）。
- **优势场景**：规则未知或难以写成模拟器的环境（Atari、真实世界控制）；同一套算法覆盖棋类和像素游戏（讲义："one algorithm, no rule knowledge"）。
- **局限**：模型误差会在长展开中累积；计算开销大（讲义 Pitfalls "Compute floor"）。后续 Stochastic MuZero 加入随机动力学和机会节点，扩展到西洋双陆棋类游戏；Muesli、Gumbel MuZero 提升样本效率并改进搜索。
- **加分点**：联系第 11 节——MuZero 学到的模型本质上是一个"可规划的仿真器"，与世界模型方向相通。

### Q15 — 参考回答要点

- **讲义中的简化目标**：`L_GRPO(θ) = -E[(1/G) Σ_i A_i · log π_θ(o_i|q)] + β·KL(π_θ‖π_ref)`，`A_i = (r_i - mean(r)) / std(r)`。
- **完整形式的补充**（DeepSeekMath 原论文）：与 PPO 一样使用重要性比率和裁剪 `min(r_t·A_i, clip(r_t, 1-ε, 1+ε)·A_i)`，在每个 token 上计算并按回答长度平均，KL 项直接放在损失里（而不是像 PPO-RLHF 那样加到奖励中）。
- **组相对优势的作用**：同一 prompt 的组均值作 baseline（相当于用采样估计 `V(q)`；严格说它包含样本自身奖励，会把期望梯度缩放 `(1-1/G)`，RLOO 用留一均值避免），组标准差归一化让不同难度的题可比。
- **KL 的作用**：防止策略偏离参考模型太远，避免语言能力退化和对验证器的投机。
- **相比 PPO-RLHF 少了什么**：讲义："No reward model, no critic, no MCTS. Group-relative baseline replaces all three."——用验证器替代学习的 RM、用组 baseline 替代 critic。
- **已知坑**（讲义 Pitfalls + 推理）：
  1. 验证器被钻空子（单元测试覆盖不全会强化 bug）；
  2. G 太小噪声大；
  3. 长度偏差（不同长度回答的对数概率不可比）；
  4. 全对/全错的组不提供信号，需要难度合适的题目；
  5. 序列级优势让 token 级信用分配粗糙。
- **加分点**：提到 TRL 的 `GRPOTrainer` 是讲义推荐的生产参考实现。

### Q16 — 参考回答要点

- **R1-Zero**：DeepSeek-V3 基座、不做 SFT，直接 GRPO；奖励 = 准确性（规则判定答案/单测）+ 格式（`<think>…</think>`）。平均回答长度大幅增长，数学分数接近 o1-preview；问题是可读性差、语言混杂。
- **R1 四阶段**（讲义）：
  1. **冷启动 SFT**：几千条格式干净的长 CoT 示范，给 RL 一个可读的起点；
  2. **推理 GRPO**：准确性 + 格式 + **语言一致性**奖励；
  3. **拒绝采样 + 第二轮 SFT**：从 RL checkpoint 采约 60 万条推理轨迹，只保留答案正确、CoT 可读的，再混入约 20 万条非推理数据（写作、问答、自我认知），重新微调基座；
  4. **全场景 GRPO**：推理用规则奖励，通用对齐用偏好奖励。
- **为什么要拒绝采样 + SFT**：把 RL 阶段"发现"的好推理行为筛选出来，作为干净的监督数据固化下来；同时补回非推理能力，避免模型只会做题。
- **为什么小模型蒸馏**：讲义："Distillation of a strong RL teacher consistently beats RL from scratch at the student's scale." 小模型自己探索很难发现长推理策略，直接学习强教师的轨迹更高效；论文发布了 6 个蒸馏的稠密模型（Qwen-1.5B 到 Llama-70B），学生端不做 RL。
- **加分点**：指出 R1-Zero 证明了"纯 RL + 可验证奖励"能涌现长推理，R1 则是把它变成可用产品的工程配方。

### Q17 — 参考回答要点

- **奖励/验证器**：在沙箱中执行生成的函数，跑隐藏单元测试；奖励 = 通过率或全部通过才给 1；另加格式奖励（代码块可解析）。讲义 Pitfalls："Unit tests that pass for a buggy solution reinforce the bug. Design verifiers that catch edge cases."——测试要覆盖边界情况，最好多组随机测试 + 属性测试。
- **防作弊**：沙箱隔离、禁止读取测试文件、禁止硬编码期望输出（检测与测试用例字面量相同的返回值）、限制运行时间与资源；保留人工抽检。
- **组大小**：G = 8~16 起步（讲义推荐 8~64）；按通过率筛题，丢弃组内全对或全错比例过高的题，或用课程学习逐步提高难度。
- **KL**：设一个较小的 β 并监控 `KL(π_θ‖π_ref)`；KL 持续上升而通过率不涨时警惕作弊。
- **长度处理**：按 token 数归一化损失，设最大生成长度；监控平均长度，防止无意义的冗长。
- **诊断**：验证器通过率、KL、熵、长度、留出题集的 pass@1/pass@k（skill 文件："verifier pass rate, KL to reference"）。
- **加分点**：先用强模型的正确解做冷启动 SFT（参照 R1），再上 GRPO。

### Q18 — 参考回答要点

- **类比的含义**：讲义把三者统一为"self-play + search + policy improvement"。在 GRPO 中：
  - "对弈" ↔ 对同一题采样一组回答；
  - "搜索/改进" ↔ 用验证器在一组回答中挑出更好的（相对优势），相当于一种"采样 + 选择"的浅层改进算子，类似 best-of-N；
  - "策略蒸馏" ↔ 用优势加权的 log π 更新，把组内胜者的行为蒸馏进策略。
- **差异**：没有显式树搜索，没有对手（单人"游戏"），也没有价值网络；奖励来自验证器而非对局胜负。讲义也明确："No reward model, no critic, no MCTS."
- **会不会引入 MCTS**：讲义："LLM reasoning: no MCTS yet in production; GRPO on full rollouts, best-of-N for inference compute. Process reward models (PRMs) hint at step-level search being added back." 难点在于 token 级动作空间巨大、"状态"不易定义、步骤级价值难评估；PRM 提供步骤级打分后，在推理步骤（而非 token）粒度上做搜索是可能的方向。
- **加分点**：对比完全信息长视界博弈（围棋、国际象棋）仍由搜索主导，说明"搜索是否值得"取决于能否得到可靠的中间价值估计。

---

## 六、关联知识点

### 前置知识
- [阶段 09 · 05 深 Q 网络（DQN）](../../05-dqn/docs/zh.md)：Atari-DQN 是游戏 RL 的里程碑，也是讲义列出的前置。
- [阶段 09 · 08 近端策略优化（PPO）](../../08-ppo/docs/zh.md)：GRPO 是去掉 critic 的 PPO 变体。
- [阶段 09 · 09 奖励建模 & RLHF](../../09-reward-modeling-rlhf/docs/zh.md)：KL 到参考策略、reward hacking；GRPO 用验证器替代 RM。
- [阶段 09 · 10 多 Agent RL](../../10-multi-agent-rl/docs/zh.md)：自博弈与联盟训练。
- [阶段 09 · 07 Actor-Critic](../../07-actor-critic-a2c-a3c/docs/zh.md)：baseline 与 advantage；组均值 baseline 为什么基本不改变梯度方向，依据的是同一个恒等式 `Σ_a π(a)∇log π(a) = 0`。

### 本节被哪些后续内容用到
- [阶段 10 · 07 RLHF](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)：LLM 上的 RL 后训练工程。
- [阶段 10 · 20 DeepSeek-V3 解读](../../../10-llms-from-scratch/20-deepseek-v3-walkthrough/docs/zh.md)：R1 的基座模型。
- [阶段 14 · 04 Tree of Thoughts 与 LATS](../../../14-agent-engineering/04-tree-of-thoughts-lats/docs/zh.md)：在 LLM 推理中引入树搜索（含 MCTS 思路）。
- [阶段 15 · 02 STaR 系列推理](../../../15-autonomous-systems/02-star-family-reasoning/docs/zh.md)：用自生成的正确推理轨迹自我改进。
- [阶段 15 · 03 AlphaEvolve 演化式编程](../../../15-autonomous-systems/03-alphaevolve-evolutionary-coding/docs/zh.md)：组合优化/算法发现的新一代方法。
- [阶段 18 · 02 Reward Hacking 与 Goodhart](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：验证器被钻空子的系统讨论。

### 延伸关键词
`TD-Gammon` · `PUCT / UCT` · `AlphaGo Zero` · `KataGo` · `Gumbel MuZero` · `Stochastic MuZero` · `Muesli` · `CFR / Deep CFR` · `RLVR (verifiable rewards)` · `best-of-N` · `PRM vs ORM` · `rejection sampling fine-tuning` · `reasoning distillation` · `Dr. GRPO / DAPO`
