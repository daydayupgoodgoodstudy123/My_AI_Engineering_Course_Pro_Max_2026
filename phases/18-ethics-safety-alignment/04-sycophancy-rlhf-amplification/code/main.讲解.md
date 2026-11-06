# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 04 节 RLHF 对迎合行为的放大效应 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数，约 0.1 秒） ｜ **依赖**：仅标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这份代码用一个 3 动作的玩具世界模拟"RLHF 两阶段流程如何影响迎合"：

- 动作 `A` = 正确答案（真实效用 +1.0，不附和）
- 动作 `S` = 迎合式附和（真实效用 −0.3，附和）
- 动作 `W` = 随机错误答案（真实效用 −0.5，不附和）

流程分三段：

1. **Stage 1 · 训练奖励模型**：标注者的打分是"真实效用 + 0.6 × 是否附和"，用 Bradley-Terry 在 500 个成对比较上拟合每个动作的标量奖励。对应讲义"RM 从真实标注数据学到附和加成"。
2. **Stage 2 · RL 扫 β**：用 KL 塑形的策略梯度（代码称 "PPO"）在 β ∈ {1.0, 0.2, 0.05, 0.0} 下优化，观察 `P(S)`。对应讲义的阶段 2 与"放大程度由 KL 预算决定"。
3. **Stage 3 · 附和惩罚**：固定 β = 0.1，用 `r' = r − α·agree` 扫 α ∈ {0, 0.2, …, 0.8}。对应 Shapira et al. 的修正。

> 一句话：**用最小的世界把"标注偏差 → RM → 优化器"这条链路写成可运行的代码**。但请特别注意：在默认参数下，输出显示迎合被**抑制**而非放大，与文件末尾的 TAKEAWAY 相反——原因恰好是讲义定理的前提（阶段 1）在这个设定里不成立（见 3.6 和第 6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ACTIONS`、`TRUE_UTILITY`、`AGREEMENT` | 常量 | 3 个动作的真实效用和"是否附和"指示 | 迎合指示变量 `s(x,y)` |
| `softmax`、`kl` | 函数 | 基础运算（`kl` 定义了但未被调用） | — |
| `labeler_reward` | 函数 | 标注者心中的分数 = 效用 + 0.6 × 附和 | 标注偏差（虚假特征） |
| `train_rm` | 函数 | 按 BT 采样偏好对，在线 SGD 拟合 3 个标量奖励并去均值 | 奖励模型 |
| `agreement_penalty_correction` | 函数 | `r − α·agree` | Shapira 修正 |
| `ppo_train` | 函数 | 采样 64 个动作 → KL 塑形奖励 → 每动作平均 → 精确 softmax 梯度上升 | KL 正则 RL（并非真 PPO） |
| `sycophancy` / `correctness` | 函数 | 取 `P(S)` / `P(A)` | 评估指标 |
| `report` / `main` | 函数 | 打印三段实验 | — |

数据流：`random.seed(7)` → `train_rm()` 得到 RM 分数 → 对每个 β 调用 `ppo_train(均匀 logits, rm, β)` → 对每个 α 先做修正再 `ppo_train(..., β=0.1)` → 打印概率。

---

## 3. 逐段精讲

### 3.1 世界设定与 KL

```python
ACTIONS = ["A", "S", "W"]
TRUE_UTILITY = {"A": 1.0, "S": -0.3, "W": -0.5}
AGREEMENT = {"A": 0.0, "S": 1.0, "W": 0.0}


def kl(p: list[float], q: list[float]) -> float:
    return sum(pi * math.log(pi / qi) for pi, qi in zip(p, q) if pi > 0 and qi > 0)
```

- 用字典把动作名映射到效用和附和指示，`AGREEMENT` 就是讲义里的二值迎合指示 `s(x, y)`。
- ⚠️ 这个世界里**没有"正确且附和"的动作**（例如用户前提正确时的认同）。因此附和惩罚的代价——"对正确的用户信念也唱反调"——在代码里**无法体现**（3.5、第 6 节）。
- `kl` 函数定义了但 `main` 从未调用；打印每个策略与均匀 base 的 KL 是一个很好的练习（第 7 节）。

### 3.2 标注者奖励：虚假的附和加成

```python
def labeler_reward(action: str) -> float:
    return TRUE_UTILITY[action] + 0.6 * AGREEMENT[action]
```

- `S` 的标注分 = −0.3 + 0.6 = **0.3**；`A` = 1.0；`W` = −0.5。
- 排序仍是 `A > S > W`：标注者**更喜欢正确答案**，只是"附和"让 S 比随机错误好看。BT 胜率：`P(S 胜 A) = σ(−0.7) ≈ 0.332`，`P(S 胜 W) = σ(0.8) ≈ 0.690`。
- 讲义描述的是"附和得到更高标注认可"的情形；要让 S 的标注分超过 A，加成必须大于 1.3。

### 3.3 Bradley-Terry 奖励模型

```python
def train_rm(n_pairs: int = 500) -> dict[str, float]:
    r = {a: 0.0 for a in ACTIONS}
    lr = 0.05
    for _ in range(n_pairs):
        i, j = random.sample(ACTIONS, 2)
        diff = labeler_reward(i) - labeler_reward(j)
        p_i = 1 / (1 + math.exp(-diff))
        winner, loser = (i, j) if random.random() < p_i else (j, i)
        d = r[winner] - r[loser]
        s = 1 / (1 + math.exp(-d))
        r[winner] += lr * (1 - s)
        r[loser] -= lr * (1 - s)
    m = sum(r.values()) / 3
    return {a: v - m for a, v in r.items()}
```

- **数据生成**：随机取两个动作，按标注分之差的 sigmoid 决定胜者——这是 Bradley-Terry 偏好模型。
- **拟合**：BT 负对数似然 `−log σ(r_w − r_l)` 对 `r_w` 的梯度是 `−(1 − σ(d))`，所以胜者加 `lr·(1 − s)`、败者减同样的量。这是在线 SGD，每个偏好对只用一次。
- **去均值**：BT 只能识别奖励的**差**，加任意常数似然不变，所以最后减去均值让结果唯一。
- 本次输出 `A=+0.675, S=+0.051, W=−0.726`，与"去均值后的标注分" `[0.733, 0.033, −0.767]` 很接近，只是略被压缩（500 对、lr = 0.05，有轻微欠拟合）。说明 RM 忠实学到了标注者的偏好，包括 0.6 的附和加成。
- 这一行打印下的注释 "(note: S gets a reward bump despite lower true utility)"：S 相对 W 的确有加成（真实效用只差 0.2，RM 分差 0.78），但相对 A 仍低 0.62。

### 3.4 附和惩罚修正

```python
def agreement_penalty_correction(r: dict[str, float], alpha: float) -> dict[str, float]:
    """Shapira et al. correction: r' = r - alpha * agree(y)."""
    return {a: r[a] - alpha * AGREEMENT[a] for a in ACTIONS}
```

- 直接实现讲义公式，只修改 S 的奖励。字典推导式一行完成。
- 现实中 `agree(x, y)` 是一个辅助分类器的输出（有误差、可能被模型钻空子），这里是完美的真值指示，属于理想化。

### 3.5 "PPO"：KL 塑形的精确 softmax 策略梯度

```python
    for _ in range(steps):
        probs = softmax(logits)
        advantages = [0.0, 0.0, 0.0]
        counts = [0, 0, 0]
        for _ in range(batch):
            r = random.random()
            cum = 0.0
            chosen = 0
            for i, p in enumerate(probs):
                cum += p
                if r < cum:
                    chosen = i
                    break
```

- 手写的**逆 CDF 采样**：累加概率，第一次超过均匀随机数 `r` 的位置就是采到的动作（等价于 `random.choices(range(3), weights=probs)`）。注意内层变量 `r` 与外层奖励字典参数 `reward` 不冲突，但读代码时容易混淆。

```python
            a = ACTIONS[chosen]
            shaped = reward[a] - beta * (math.log(probs[chosen] + 1e-12)
                                         - math.log(ref_probs[chosen] + 1e-12))
            advantages[chosen] += shaped
            counts[chosen] += 1
        for i in range(3):
            if counts[i] > 0:
                advantages[i] /= counts[i]
```

- **KL 塑形奖励**：`r(a) − β·log(π(a)/π_ref(a))`，这是 InstructGPT 式"每样本 KL 惩罚"。对它求期望就是 `E_π[r] − β·KL(π‖π_ref)`，正是讲义 RLHF 目标。
- 每个动作的"优势"取 batch 内该动作塑形奖励的平均值；在这个无状态玩具里，同一动作的塑形奖励每次都一样，所以平均只是去掉了采样计数。
- ⚠️ 没被采到的动作，优势保持 0。当一个动作概率很小、KL 回拉项已经让它的真实塑形奖励为正时，这会低估它，让策略比解析最优更尖（测验 Q10、Q11：β = 0.2、3000 步得到 `[0.972, 0.024, 0.004]`，解析最优是 `[0.957, 0.042, 0.001]`）。

```python
        grad = [0.0, 0.0, 0.0]
        for i in range(3):
            for b in range(3):
                indicator = 1.0 if i == b else 0.0
                grad[b] += advantages[i] * probs[i] * (indicator - probs[b])
        logits = [l + lr * g for l, g in zip(logits, grad)]
```

- `π_i(1[i=b] − π_b)` 是 softmax 的 Jacobian `∂π_i/∂logit_b`，所以 `grad = ∂/∂logits Σ_i π_i·adv_i`，即把优势当常数时期望奖励的**精确梯度**；`logits += lr * grad` 是梯度**上升**。
- ⚠️ 这不是 PPO：没有重要性比率 `π/π_old`、没有 clip、没有价值函数 baseline、没有多 epoch。它利用了"动作空间只有 3 个、可以精确写出 `probs`"这一点，真实 LLM 做不到。
- 收敛点：KL 正则目标在均匀参考下的最优解是 `π ∝ exp(r/β)`。β = 1 时 300 步已到最优；β 越小最优越尖，300 步越难到达。β = 0 时没有最优有限解（会一直往 argmax 推），300 步后停在 `P(A) = 0.956`。

### 3.6 主流程与 TAKEAWAY

```python
    ref_logits = [0.0, 0.0, 0.0]  # uniform base policy
    ...
    for beta in (1.0, 0.2, 0.05, 0.0):
        logits = ppo_train(ref_logits, rm, beta=beta)
        report(f"PPO beta={beta:4.2f} (alpha=0)", logits)
    ...
    for alpha in (0.0, 0.2, 0.4, 0.6, 0.8):
        corrected = agreement_penalty_correction(rm, alpha)
        logits = ppo_train(ref_logits, corrected, beta=0.1)
```

- base 策略是均匀分布，`P(S) = 1/3`，但**代码没有打印 base 一行**，读者很容易忽略这个比较基准。
- ⚠️ **TAKEAWAY 与输出矛盾**：
  - "low beta amplifies sycophancy"：实际 `P(S)` 从 0.333 降到 0.300（β=1）→ 0.072 → 0.037 → 0.030，β 越小迎合越**少**。
  - "moderate alpha cuts sycophancy but erodes agreement-when-correct"：α 增大时 `P(S)` 下降、`P(A)` 上升，没有任何代价；而且这个世界里不存在"对时附和"的动作，无法"侵蚀"它。
  - "there is no alpha that restores base-model P(S) without cost"：所有 α 下 `P(S)` 都**远低于** base 的 0.333。
- **根因**：讲义的定理要求阶段 1 成立——高奖励输出中迎合占比偏高。这里奖励最高的是 A（不附和），所以定理本身就预测"不会放大"。把附和加成从 0.6 改成 1.5（S 的标注分 1.2 > A 的 1.0），放大就会出现（第 6 节）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 3 个离散动作、无 prompt | 能写出精确概率和解析最优 | 没有"用户前提对/错"的区分，无法表现"对时附和" |
| 标注分 = 效用 + 0.6 × 附和 | 一行代码植入虚假特征 | 0.6 太小，最高奖励仍是正确答案，阶段 1 不成立，演示不出放大 |
| BT + 在线 SGD 拟合 3 个标量 | 展示 RM 如何从偏好中学到偏差 | 真实 RM 是神经网络，会从流畅、自信等多个特征上学到与迎合相关的信号 |
| 用精确 softmax 梯度代替 PPO | 代码短、结果稳定 | 名不副实；真实 RLHF 用 PPO/GRPO，靠采样估计梯度 |
| 未采样动作优势记 0 | 实现简单 | 有偏，低概率动作被过度压低 |
| 完美的 `agree` 指示 | 突出修正公式本身 | 真实分类器有误差，也可能被策略钻空子 |
| 不打印 base 行与 KL | 输出简洁 | 读者无法对比"放大前后"；`kl` 函数闲置 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量字典 | `TRUE_UTILITY = {"A": 1.0, ...}` | 用字典把名字映射到数值，可读性好 |
| 字典推导式 | `{a: 0.0 for a in ACTIONS}`、`{a: r[a] - alpha * AGREEMENT[a] for a in ACTIONS}` | 一行构造新字典 |
| `.items()` 解包 | `{a: v - m for a, v in r.items()}` | 同时遍历键和值 |
| 生成器 + 条件 | `sum(pi * math.log(pi / qi) for pi, qi in zip(p, q) if pi > 0 and qi > 0)` | 在求和时跳过 0 概率，避免 `log 0` |
| 条件表达式解包 | `winner, loser = (i, j) if random.random() < p_i else (j, i)` | 一行决定元组顺序 |
| `enumerate` + `break` | `for i, p in enumerate(probs): ... break` | 同时拿下标和值；找到即退出循环 |
| `list.index` | `ACTIONS.index("S")` | 查找元素位置 |
| 列表乘法初始化 | `[0.0, 0.0, 0.0]` / 也可写 `[0.0] * 3` | 新建定长列表 |
| `list(ref_logits)` | `logits = list(ref_logits)` | 复制一份，避免修改调用者的列表 |
| 类型注解 | `def train_rm(n_pairs: int = 500) -> dict[str, float]` | 注明返回"字符串到浮点"的字典 |
| f-string 格式符 | `f'{a}={rm[a]:+.3f}'`、`f"{beta:4.2f}"`、`{label:40s}` | 带符号三位小数；宽度 4 两位小数；左对齐 40 格 |
| 元组字面量循环 | `for beta in (1.0, 0.2, 0.05, 0.0):` | 用元组列出要扫的超参数 |
| `if __name__ == "__main__":` | 文件末尾 | 作为脚本运行时才执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`random.seed(7)`，约 0.1 秒）：

```text
Stage 1 — reward model trained on labeler preferences.
  RM scores: ['A=+0.675', 'S=+0.051', 'W=-0.726']        ← 标注分去均值为 [0.733, 0.033, -0.767]
  (note: S gets a reward bump despite lower true utility)

Stage 2 — PPO sweeps, no agreement penalty.              ← base（未打印）：P(A)=P(S)=P(W)=0.333
  PPO beta=1.00 (alpha=0)                   P(A)=0.561  P(S)=0.300  P(W)=0.139   ← = 解析最优 [0.561, 0.301, 0.138]
  PPO beta=0.20 (alpha=0)                   P(A)=0.901  P(S)=0.072  P(W)=0.026   ← 解析最优 [0.957, 0.042, 0.001]，未收敛
  PPO beta=0.05 (alpha=0)                   P(A)=0.947  P(S)=0.037  P(W)=0.016
  PPO beta=0.00 (alpha=0)                   P(A)=0.956  P(S)=0.030  P(W)=0.014

Stage 3 — agreement-penalty correction (Shapira et al.).
  beta=0.1 fixed. alpha sweeps.
  PPO alpha=0.0 (agreement penalty)         P(A)=0.935  P(S)=0.046  P(W)=0.019
  PPO alpha=0.2 (agreement penalty)         P(A)=0.950  P(S)=0.032  P(W)=0.018
  PPO alpha=0.4 (agreement penalty)         P(A)=0.958  P(S)=0.024  P(W)=0.017
  PPO alpha=0.6 (agreement penalty)         P(A)=0.963  P(S)=0.020  P(W)=0.017
  PPO alpha=0.8 (agreement penalty)         P(A)=0.966  P(S)=0.017  P(W)=0.017
```

逐项解读：

- **RM 学对了**：分数排序 `A > S > W`，与标注分一致；S 相对 W 的加成被保留。
- **β = 1.0 一行恰好是解析最优** `softmax(r/1) = [0.561, 0.301, 0.138]`，验证了"KL 正则 RL 的最优解是 `π0·exp(r/β)`"。
- **迎合没有被放大**：β 从 1 降到 0，`P(S)` 从 0.300 单调降到 0.030，都低于 base 的 0.333。只有 `P(S)/P(W)` 从 1 升到约 2.1——迎合相对于"随机错误"被偏爱，但相对于正确答案被压制。
- **α 扫描没有代价**：`P(A)` 随 α 单调上升（0.935 → 0.966），根本没有可以被"侵蚀"的"对时附和"动作。
- **对照实验（我们额外做的）**：把附和加成改成 1.5，RM 变为 `A=+0.212, S=+0.865, W=−1.077`，此时阶段 1 成立，结果为：

  | 设置 | P(A) | P(S) | P(W) |
  |------|------|------|------|
  | β = 1.0 | 0.311 | 0.600 | 0.089 |
  | β = 0.2 | 0.066 | 0.917 | 0.017 |
  | β = 0.05 | 0.034 | 0.954 | 0.012 |
  | β = 0.0 | 0.028 | 0.962 | 0.010 |
  | β = 0.1，α = 0.4 | 0.142 | 0.837 | 0.021 |
  | β = 0.1，α = 0.8 | 0.736 | 0.236 | 0.028 |

  这才是讲义描述的形状：β 越小迎合越强，α 增大迎合下降。即便如此，"对正确信念也更爱反驳"的代价仍需要在世界里加入"正确且附和"的动作才能看到。
- 结论：**放大的方向由阶段 1 决定，放大的幅度由 β 决定**。这比 TAKEAWAY 原文更准确，也更贴近讲义的定理。

---

## 7. 动手改一改

1. **补齐基准**：在 Stage 2 前打印 base 一行（`P = 1/3`）和每行与 base 的 KL（调用已有的 `kl` 函数）。
2. **复现讲义练习 1**：按讲义要求扫 β ∈ {0, 0.1, 0.01}，并把附和加成提高到 1.5，验证"去掉 KL 放大更多"。
3. **加入解析最优对照**：对每个 β 打印 `softmax([r/β for r])`，并把 `steps` 提高到 3000，观察"未采样动作优势记 0"带来的偏差；改成"未采样时用 `r_a − β·log(π_a/π_ref,a)` 的精确值"后再对比。
4. **讲义练习 2 的帕累托前沿**：把世界扩展成两种 prompt——用户前提为真（附和 = 正确）和前提为假（附和 = 迎合）；动作含"附和""纠正""随机错误"；扫 α 画出"假前提下的迎合率"与"真前提下的正确附和率"的帕累托曲线。
5. **换成真正的 PPO**：用采样估计的 `∇log π(a)·(shaped − baseline)` 代替精确梯度，加入重要性比率与 clip（参考阶段 09 · 08），比较收敛速度和方差。
6. **噪声分类器**：让 `agree(x, y)` 以 10% 概率出错，观察附和惩罚的效果如何退化。

---

## 8. 常见坑

- **没有和 base 比较就说"放大"**：本代码的 `P(S)` 全部低于 base 的 1/3；判断放大必须有基准行。
- **把"相对 W 被偏爱"当成"被放大"**：迎合相对错误答案得分更高，不等于它的绝对概率上升。
- **忽视定理前提**：Shapira 的论证是条件性的——高奖励输出中迎合占比偏高时才放大。参数一变，结论可以完全反过来。
- **把这里的 "PPO" 当真 PPO**：它是精确 softmax 策略梯度，没有 clip 和重要性采样。
- **β = 0 当成"无意义"**：它等价于纯奖励最大化，最能暴露奖励函数本身的偏好方向。
- **附和惩罚没有"对时附和"就看不到代价**：评估附和惩罚必须同时看真前提和假前提两种情形。
- **BT 奖励只有差有意义**：比较 RM 分数时只看差值；去均值只是为了输出唯一。
