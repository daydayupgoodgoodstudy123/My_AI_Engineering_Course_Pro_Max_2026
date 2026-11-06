# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 12 节 游戏强化学习——AlphaZero、MuZero 和 LLM 推理时代 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 0.03 秒跑完） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

讲义说："The code in `code/main.py` implements **GRPO in miniature** — a bandit with multiple groups of samples. The algorithm is the same as on an LLM; only the policy and environment are simpler." 本节讲义覆盖 AlphaZero、MuZero、GRPO 三大架构，但代码**只实现了 GRPO**（没有 MCTS，也没有学习的动力学模型）。它想让你掌握：

1. **验证器奖励（verifiable reward）**：答案对就给 1，错就给 0——不需要人类偏好、不需要奖励模型。
2. **组采样 + 组相对优势**：同一个 prompt 采 G=8 个回答，用组均值做 baseline、组标准差做归一化——这是 DeepSeekMath 提出、DeepSeek-R1 使用的关键技巧。
3. **无 critic 的策略梯度**：优势直接乘 `∇log π`，不需要价值网络。
4. **对参考策略的 KL 正则**：把策略往初始（参考）策略拉，防止漂移。
5. **与无 baseline 的 REINFORCE 对比**：看组 baseline 对学习曲线的影响（以及这个对比本身的公平性问题）。

> 一句话：**GRPO = REINFORCE + "同题多答、组内相对打分" + KL 拴绳。** 把 3 个 prompt × 4 个答案换成"数学题 × 整段推理回答"，就是 R1 的训练循环。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `QUESTIONS` / `N_PROMPTS` / `N_ANSWERS` | 常量 | 3 道"题"，每题 4 个候选答案，正确答案下标分别为 2、0、3 | 题库 |
| `softmax` / `policy_probs` / `sample` | 函数 | 每个 prompt 一行 logits → 概率 → 采样答案 | 策略 `π_θ(o\|q)`（相当于 LLM 的最后一层） |
| `verify(p_idx, answer)` | 函数 | 答对返回 1.0，否则 0.0 | 验证器（单元测试 / 答案匹配） |
| `grpo_step()` | 函数 | 采 G 个答案 → 组相对优势 → 策略梯度 + KL 拉回 | GRPO 核心 |
| `reinforce_step()` | 函数 | 采 1 个答案，用原始奖励做策略梯度 | 无 baseline 的 REINFORCE |
| `train_grpo()` / `train_reinforce()` | 函数 | 训练循环，记录奖励（和 KL） | 训练 |
| `evaluate()` | 函数 | 贪心选答案，统计准确率 | 评估 |
| `main()` | 函数 | 训练两种方法 400 次更新，打印分块曲线和准确率 | 演示入口 |

数据流：`main` → `train_grpo`（反复调用 `grpo_step`）与 `train_reinforce`（反复调用 `reinforce_step`），两者都用 `Random(3)` → 每 50 次更新求平均 → `evaluate` 贪心准确率。

---

## 3. 逐段精讲

### 3.1 题库与验证器

```python
QUESTIONS = (
    {"prompt": "what is 1+2",      "correct": 2, "n_answers": 4},
    {"prompt": "what is 3*3",      "correct": 0, "n_answers": 4},
    {"prompt": "capital of France", "correct": 3, "n_answers": 4},
)
N_PROMPTS = len(QUESTIONS)
N_ANSWERS = 4

def verify(p_idx, answer):
    return 1.0 if answer == QUESTIONS[p_idx]["correct"] else 0.0
```

- 每道题的"答案"是 0~3 的下标，`correct` 字段指定哪个下标是对的（prompt 文本只是装饰，与答案下标无语义关系）。
- `verify` 就是讲义说的 "a tiny verifier environment"。真实 GRPO 中它是"运行单元测试"或"比较数学答案"，关键性质相同：**确定性、可自动判定、0/1 奖励**。
- `n_answers` 字段没有被使用，代码统一用常量 `N_ANSWERS = 4`。
- 用元组 + 字典存题库：元组表示题库不可变，字典让每道题的字段有名字。

### 3.2 策略：每题一个 softmax

```python
def policy_probs(theta, p_idx):
    return softmax(theta[p_idx])
```

- `theta` 是 3×4 的 logits 表，每个 prompt 一行。讲义："Equivalent to the final-layer output of an LLM conditioned on a prompt."
- 与 LLM 的区别：LLM 的"回答"是一长串 token，`log π(o|q)` 是所有 token 的对数概率之和；这里回答只有一个 token。讲义练习 Hard 就是把它扩展到两个 token。

### 3.3 GRPO 第一步：组采样与组相对优势

```python
def grpo_step(theta, reference, rng, G=8, beta=0.01, lr=0.1):
    p_idx = rng.randrange(N_PROMPTS)
    probs = policy_probs(theta, p_idx)
    samples = [sample(probs, rng) for _ in range(G)]
    rewards = [verify(p_idx, s) for s in samples]
    mean_r = sum(rewards) / G
    var_r = sum((r - mean_r) ** 2 for r in rewards) / G
    std_r = math.sqrt(var_r) + 1e-8
    advs = [(r - mean_r) / std_r for r in rewards]
```

这是 GRPO 的灵魂，对应讲义公式 `A_i = (r_i - mean_r) / std_r`：

- **同一道题采 G=8 个回答**，组成一个"组"。
- **组均值做 baseline**：它是同一 prompt 下"平均能拿多少分"的蒙特卡洛估计，扮演了 PPO 中 critic（`V(s)`）的角色，却不需要训练任何网络。严格来说，组均值里也包含样本自己的奖励 `r_i/G` 这一项，所以它不完全独立于该样本的动作：在不做 std 归一化时，这只会把期望梯度整体缩放 `(1 - 1/G)` 倍、方向不变；RLOO 等方法用"去掉自己的留一均值"作 baseline 来消除这一点。
- **组标准差归一化**：让难题（正确率低）和易题（正确率高）的优势量级可比。例如 8 个里对 2 个时，答对者优势约 +1.73、答错者约 -0.58；8 个里对 7 个时，答对者约 +0.38、答错者约 -2.65。
- **`+ 1e-8`**：全对或全错时 `var_r = 0`，加小常数避免除零；此时所有优势都是 0，**这一组不产生策略梯度**——GRPO 的已知性质，意味着太简单或太难的题都在浪费采样。
- ⚠️ 这里用的是总体标准差（除以 G）；用除以 G-1 的样本标准差也很常见，差别不大。

### 3.4 GRPO 第二步：KL 的监控值

```python
    probs_ref = policy_probs(reference, p_idx)
    kl = sum(p * (math.log(max(p, 1e-12)) - math.log(max(q, 1e-12))) for p, q in zip(probs, probs_ref))
```

- 计算当前策略与参考策略在这道题上的 `KL(π_θ‖π_ref) = Σ p·(log p - log q)`，只用于**记录**，返回给 `main` 打印。
- `max(p, 1e-12)` 防止 `log(0)`。
- 参考策略 `reference` 在 `train_grpo` 中是初始 θ（全 0）的拷贝，即均匀分布；对应真实 R1 流程中的冷启动 SFT 模型或基座模型。

### 3.5 GRPO 第三步：策略梯度 + KL 拉回

```python
    for a, A in zip(samples, advs):
        for i in range(N_ANSWERS):
            grad_logpi = (1.0 if i == a else 0.0) - probs[i]
            theta[p_idx][i] += (lr / G) * A * grad_logpi

    for i in range(N_ANSWERS):
        theta[p_idx][i] -= beta * (probs[i] - probs_ref[i])

    return mean_r, kl
```

- **策略梯度部分**：对组内每个样本，`θ += (lr/G)·A·∇log π(a)`，正好是讲义损失 `-(1/G) Σ A_i·log π_θ(o_i|q)` 的梯度下降（等价于对 `(1/G) Σ A_i log π` 做梯度上升）。`∇_z log π(a) = onehot(a) - probs` 是 softmax 的闭式梯度。
- 注意 `probs` 在整个组的更新中保持**更新前**的值——8 个样本的梯度都在同一个参数点计算后累加，相当于一次 batch 梯度。
- **没有重要性比率和裁剪**：这是 REINFORCE 式的单次更新。DeepSeekMath 中的完整 GRPO 和 PPO 一样使用 `min(r·A, clip(r)·A)` 并可多次复用一组样本；讲义的简化公式和本代码都省略了这一部分。
- **KL 拉回**：`θ -= β·(p - p_ref)`。⚠️ 有两处值得注意：
  1. `p - q` 实际是 **`KL(π_ref‖π_θ)`** 对 logits 的梯度，而不是第 3.4 节记录的、讲义损失中写的 `KL(π_θ‖π_ref)`。后者的精确梯度是 `p_i·(log p_i - log q_i - KL)`。两种都能把策略拉回参考，但"优化的量"和"监控的量"不一致（推导与修正见测验 Q10）。
  2. 讲义 Step 3 的示例写的是 `θ -= β·(θ - θ_ref)`（logits 空间 L2），与代码也不同。
- `β = 0.01` 很小，所以 KL 会随训练持续上升（策略越来越确定），这在下面的输出中可以看到。

### 3.6 对照组：无 baseline 的 REINFORCE

```python
def reinforce_step(theta, rng, lr=0.1):
    p_idx = rng.randrange(N_PROMPTS)
    probs = policy_probs(theta, p_idx)
    a = sample(probs, rng)
    r = verify(p_idx, a)
    for i in range(N_ANSWERS):
        grad_logpi = (1.0 if i == a else 0.0) - probs[i]
        theta[p_idx][i] += lr * r * grad_logpi
    return r
```

- 每次只采 **1 个**答案，直接用原始奖励 `r ∈ {0, 1}` 乘 `∇log π`。
- 答错时 `r = 0`，**完全不更新**——错误答案不会被主动压低，只会因为正确答案被抬高而间接下降。这正是没有 baseline 的问题：奖励全为非负时，信号只能"推高被采到且奖励为正的动作"。
- ⚠️ 与 GRPO 相比，每次更新的**样本数相差 8 倍**（GRPO 400 次更新共 3200 个样本，REINFORCE 400 个）。讲义 Step 4 说"Same setup, same compute"，但代码是按更新次数而非样本数对齐的。

### 3.7 训练循环与评估

```python
def train_grpo(updates=500, rng=None):
    rng = rng or random.Random(0)
    theta = [[0.0] * N_ANSWERS for _ in range(N_PROMPTS)]
    reference = [row[:] for row in theta]
    ...

def evaluate(theta, episodes=200, rng=None):
    ...
        a = max(range(N_ANSWERS), key=lambda i: probs[i])
        total += verify(p_idx, a)
```

- `[[0.0] * N_ANSWERS for _ in range(N_PROMPTS)]`：外层用推导式、内层用列表乘法——外层必须用推导式，否则 `[[0.0]*4]*3` 会让三行共享同一个列表对象。
- `reference = [row[:] for row in theta]` 逐行拷贝，确保参考策略在训练中不被修改（"冻结"）。
- `evaluate` 随机抽 200 次题目，用 argmax 作答，统计准确率。由于只有 3 道题，只要每道题的最大概率答案正确，准确率就是 100%。
- `main` 中把 `block_mean` 定义为**嵌套函数**（函数里定义函数），只在 `main` 内部使用。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| bandit（单 token 回答） | 讲义："only the policy and environment are simpler"，聚焦损失与优势 | 真实 LLM 回答有数千 token，需要序列级优势 + 长度归一化 |
| 0/1 验证器 | 对应可验证奖励，规则清晰 | 真实验证器要防投机（测试覆盖、沙箱） |
| 组均值 / 组标准差 | GRPO 的核心，无需 critic | 全对/全错组无信号；std 很小时会放大噪声 |
| 无重要性比率与裁剪 | 单次更新时不需要 | 真实 GRPO 用 PPO 式裁剪并可多次复用一组样本 |
| `θ -= β(p - p_ref)` 作 KL 正则 | 简单、能拉回参考 | 与记录的 KL 方向不一致；生产中逐 token 用 KL 估计量放进损失 |
| 与无 baseline 的 REINFORCE 对比 | 突出 baseline 的作用 | 按更新次数对齐不公平；应按样本预算对齐并多种子 |
| 全部标准库实现 | 零依赖、一眼看懂 | 生产参考：TRL 的 `GRPOTrainer`（讲义推荐） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组里放字典 | `QUESTIONS = ({"prompt": ..., "correct": 2, ...}, ...)` | 不可变的记录集合 |
| 列表推导式 + 函数调用 | `[sample(probs, rng) for _ in range(G)]` | 采 G 个样本 |
| 推导式里调用验证器 | `[verify(p_idx, s) for s in samples]` | 逐个打分 |
| 生成器表达式 + `zip` | `sum(p * (...) for p, q in zip(probs, probs_ref))` | 逐元素计算再求和 |
| 条件表达式 | `1.0 if answer == ... else 0.0` | 一行 if/else |
| 外层推导 + 内层列表乘法 | `[[0.0] * N_ANSWERS for _ in range(N_PROMPTS)]` | 正确创建二维列表（各行独立） |
| 切片拷贝 | `[row[:] for row in theta]` | 逐行复制 |
| 元组返回与解包 | `return mean_r, kl`；`for m, _kl in hist_grpo` | 多返回值；`_kl` 表示忽略 |
| 嵌套函数 | `main` 里的 `def block_mean(...)` | 只在外层函数内可见 |
| f-string 里的推导式 | `f"prompts: {[q['prompt'] for q in QUESTIONS]}"` | 花括号里可以写任意表达式（注意引号嵌套） |
| f-string 对齐与百分比 | `f"{g:<16.3f}"`、`f"{grpo_acc*100:.1f}%"` | 左对齐宽 16、3 位小数；手动乘 100 显示百分比 |
| `max(range(n), key=...)` | `max(range(N_ANSWERS), key=lambda i: probs[i])` | argmax |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13，约 0.03 秒）输出：

```text
=== GRPO in miniature: tiny verifier bandit ===
prompts: ['what is 1+2', 'what is 3*3', 'capital of France']
correct answers: [2, 0, 3]

block   GRPO mean_r     GRPO mean_KL      REINFORCE mean_r  
1       0.355           0.0305            0.220             
2       0.590           0.2368            0.360             
3       0.782           0.5662            0.460             
4       0.855           0.7708            0.660             
5       0.890           0.9253            0.700             
6       0.927           1.0059            0.860             
7       0.912           1.0625            0.780             
8       0.953           1.1144            0.880             

greedy evaluation accuracy:
  GRPO       = 100.0%
  REINFORCE  = 100.0%

GRPO uses the group-mean as baseline and group-std for normalization —
no critic, no reward model. This is the DeepSeek-R1 recipe in one page.
```

逐段解读：

- **GRPO mean_r**：每次更新时组内 8 个样本的平均奖励，从 0.355（略高于随机的 0.25）升到 0.953。
- **GRPO mean_KL**：从 0.03 稳步升到 1.11。最大可能值是 `ln 4 ≈ 1.386`（完全确定的策略相对均匀分布）。β=0.01 太小，KL 正则几乎没有约束住策略——在这个问题里这是好事（我们希望它变确定），但在 LLM 上 KL 持续上升需要警惕（讲义 Step 5："mean KL to reference, policy entropy, reward-over-time"）。
- **REINFORCE mean_r**：每 50 次更新（即 50 个样本）的平均奖励，从 0.22 升到 0.88，曲线更抖（第 7 块从 0.86 回落到 0.78），因为每个点只基于单个样本的 0/1 奖励。
- **按更新次数看 GRPO 更快更稳**，但别急着下结论：GRPO 每次更新用了 8 个样本。实测把 REINFORCE 增加到 3200 次更新（与 GRPO 的样本总数相同），按每 400 个样本平均，REINFORCE 是 `0.615, 0.927, 0.965, 0.983, …`，而 GRPO 是 `0.355, 0.590, 0.782, 0.855, …`——**按样本数，REINFORCE 在这个小 bandit 上反而更快**。原因是它更新次数多 8 倍，而这个问题的方差本来就小。GRPO 在 LLM 上的价值在于：参数更新昂贵而同题并行采样便宜、长序列下无 baseline 的方差极大、以及省掉同规模的 critic。
- **贪心准确率都是 100%**：两者都已让每道题的正确答案概率最大。换 5 个种子重复，两者也都是 100%；GRPO 的正确答案概率约 0.93~0.95，REINFORCE 约 0.86~0.92（400 次更新时）。
- **最后两行**：总结了 GRPO 的卖点——没有 critic、没有奖励模型。

---

## 7. 动手改一改

1. **公平对比**（讲义练习 Medium 的前置）：把 `train_reinforce` 的 `updates` 改成 3200，按每 400 个样本分块，与 GRPO 并排比较。
2. **给 REINFORCE 加 baseline**：用滑动平均奖励作 baseline（`r - b`），观察答错时是否开始"主动压低"错误答案。
3. **修正 KL 梯度**：按测验 Q10 把 KL 更新改成 `p_i·(log p_i - log q_i - KL)`，把 β 调到 0.5，观察 KL 曲线是否被约束在较低水平。
4. **组大小扫描**：G ∈ {2, 4, 8, 32}，固定**样本总数**比较学习曲线（讲义 Pitfalls："Below G = 4, the advantage signal is noisy"）。
5. **加入 PPO 式裁剪**：每组样本更新 4 个 epoch，用 `exp(log π_new - log π_old)` 和裁剪，体验"真正的" GRPO 目标。
6. **两步推理链**（讲义练习 Hard）：参考测验 Q12，验证器只看整对 token，观察序列级优势如何同时训练两个位置。

---

## 8. 常见坑

- **全对/全错的组**：优势全为 0，浪费采样。实践中按正确率筛选题目或做课程学习。
- **不加 `+1e-8`**：组内奖励相同时除以 0。
- **监控的 KL 与优化的 KL 不一致**：本代码记录 `KL(π_θ‖π_ref)`，却按 `KL(π_ref‖π_θ)` 的梯度更新；调 β 时要清楚自己在约束哪个量。
- **按更新次数比较不同批大小的算法**：GRPO 每次更新用 G 个样本，必须按样本数（或计算量）对齐才公平。
- **把 baseline 写成依赖回答本身的量**：baseline 应只依赖 prompt，否则会引入偏差。组均值对组内每个样本都相同，但它包含了样本自身的奖励，会把期望梯度缩小 `(1 - 1/G)` 倍；G 很小时差别明显，可改用留一均值（RLOO）。
- **二维列表初始化**：`[[0.0] * 4] * 3` 会让三行共享同一个列表，改一行三行都变；本代码用推导式避免了这个坑。
