# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 09 节 奖励建模 & RLHF ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 0.1 秒跑完） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`collections.Counter / defaultdict`）

---

## 1. 这份代码在考察什么

讲义说得很直白："No real LLM — the *shape* of the pipeline matters, not the scale." 这份代码把 RLHF 缩成一个玩具：回答是 1~2 个单词，奖励模型是词袋上的线性打分器，策略是"每个 prompt 一个 12 维 softmax"。它想让你看清：

1. **偏好数据的形状**：`(prompt, 被偏好的回答, 被拒绝的回答)` 三元组，和真实 RLHF 一模一样。
2. **Bradley-Terry 奖励模型**：只用成对比较，学出每个词的"好坏权重"；梯度系数为什么是 `1 - p`。
3. **PPO 式策略优化 + KL 惩罚**：对 RM 分数做 advantage 标准化、裁剪更新，并用 β 控制与参考策略的距离。
4. **β 扫描**：观察不同 β 下"RM 分数 vs KL"的权衡——以及本代码实现中 KL 惩罚的一个关键缺陷（见 3.6）。

> 一句话：**RLHF = 用成对偏好拟合一个打分器，再用 RL 去"讨好"这个打分器，同时用 KL 拴住别跑太远。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `PROMPTS` / `GOOD` / `BAD` / `VOCAB` | 常量 | 3 个 prompt，6 个好词，6 个坏词，合并排序后共 12 个 token | 玩具数据空间 |
| `bag(tokens)` | 函数 | 词袋计数 `Counter` | 回答的特征表示 |
| `sigmoid(x)` | 函数 | 数值稳定的 σ | BT 模型的概率 |
| `score(w, tokens)` | 函数 | `R(y) = Σ w[t]·count(t)` | 线性奖励模型 |
| `sample_pair(rng)` | 函数 | 生成 (prompt, 两个好词, 两个坏词) | 合成偏好数据 |
| `train_rm()` | 函数 | 逐对做 BT 梯度上升 | RLHF 阶段 2：RM 训练 |
| `rm_accuracy()` | 函数 | 在新的随机样本上测成对准确率 | RM 评估 |
| `softmax` / `policy_probs` / `sample_token` | 函数 | 策略：每个 prompt 一行 logits | `π_θ(y\|x)` |
| `kl(p, q)` | 函数 | 离散分布的 KL 散度 | KL(π_θ‖π_ref) |
| `rlhf_loop()` | 函数 | 采样 16 条 → 算奖励（RM − β·KL）→ 标准化 → 裁剪更新 | RLHF 阶段 3：PPO + KL |
| `main()` | 函数 | 训练 RM、打印权重和准确率、对 3 个 β 跑 RLHF | 演示入口 |

数据流：`main` → `train_rm` 得到权重字典 `w` → `rm_accuracy(w)` → 对 β ∈ {0.01, 0.1, 1.0} 各调用一次 `rlhf_loop(w, ...)`，打印首尾两轮的 RM 分数与 KL。

⚠️ 代码打印的标题是 "Stage 1: reward model" 和 "Stage 2: PPO-RLHF"，而讲义的编号是 SFT=阶段 1、RM=阶段 2、PPO=阶段 3。代码省略了 SFT（参考策略直接取均匀分布），所以编号前移了一位，阅读时对应一下即可。

---

## 3. 逐段精讲

### 3.1 数据：一个"必然可分"的偏好集

```python
PROMPTS = ("help me", "answer me", "explain this")
GOOD = ("clear", "specific", "kind", "thorough", "precise", "helpful")
BAD = ("vague", "rude", "wrong", "short", "cold", "careless")
VOCAB = tuple(sorted(set(GOOD + BAD)))

def sample_pair(rng):
    x = rng.choice(PROMPTS)
    y_pos = (rng.choice(GOOD), rng.choice(GOOD))
    y_neg = (rng.choice(BAD), rng.choice(BAD))
    return x, y_pos, y_neg
```

- `VOCAB` 用 `sorted(set(...))` 去重并排序，保证 token 下标在每次运行中固定（`set` 的迭代顺序不保证稳定，排序后才可复现）。
- 每对数据中"好回答"全是好词、"坏回答"全是坏词，**完美可分、没有标注噪声**。这就是为什么后面 RM 准确率能到 1.000。真实数据中讲义估计约 30% 的标签有噪声或歧义。
- `prompt x` 被生成但在 RM 中没有用到（`_` 丢弃）——这个 RM 是**与 prompt 无关**的，`R(x, y) = R(y)`。真实 RM 的输入是 prompt 和回答拼接后的完整序列。

### 3.2 数值稳定的 sigmoid

```python
def sigmoid(x):
    if x > 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)
```

- 两个分支数学上相等（第二个是分子分母同乘 `e^x`），但保证 `math.exp` 的参数永远 ≤ 0，不会溢出。朴素写法在 `x = -1000` 时会调用 `math.exp(1000)`，Python 直接抛 `OverflowError`。
- 这和 softmax "先减最大值" 是同一个思想。

### 3.3 线性奖励模型与 Bradley-Terry 训练

```python
def score(w, tokens):
    return sum(w.get(t, 0.0) * c for t, c in bag(tokens).items())

def train_rm(n_pairs=500, lr=0.1, rng=None):
    rng = rng or random.Random(0)
    w = defaultdict(float)
    for _ in range(n_pairs):
        _, y_pos, y_neg = sample_pair(rng)
        r_pos = score(w, y_pos)
        r_neg = score(w, y_neg)
        p = sigmoid(r_pos - r_neg)
        grad_scale = 1 - p
        for t, c in bag(y_pos).items():
            w[t] += lr * grad_scale * c
        for t, c in bag(y_neg).items():
            w[t] -= lr * grad_scale * c
    return w
```

这是讲义 Step 2 的直接实现，对应损失 `L = -log σ(R(y₊) - R(y₋))`。

- **梯度推导**：`dL/dΔ = -(1 - σ(Δ))`，`Δ = R₊ - R₋`；对词 t 的权重，`dΔ/dw[t] = count₊(t) - count₋(t)`。梯度下降后正好是"好回答里的词加 `lr·(1-p)·c`，坏回答里的词减 `lr·(1-p)·c`"。
- **`1 - p` 的含义**：模型越确信（p→1），更新越小；判错的样本（p 小）更新最大。和逻辑回归一模一样——BT 本质上就是**对奖励差做逻辑回归**。
- `defaultdict(float)`：访问不存在的键时自动创建并返回 0.0，所以 `w[t] += ...` 不用先判断键是否存在。`score` 里用 `w.get(t, 0.0)` 则是**只读**访问，不会往字典里插入新键。
- ⚠️ 一次只用一对样本做 SGD（batch size = 1），没有正则化。真实 RM 是 transformer + 标量 head，用 mini-batch 训练，通常只训 1 个 epoch 以免过拟合。

### 3.4 RM 评估

```python
def rm_accuracy(w, n_pairs=200, rng=None):
    rng = rng or random.Random(1)
    correct = 0
    for _ in range(n_pairs):
        _, y_pos, y_neg = sample_pair(rng)
        if score(w, y_pos) > score(w, y_neg):
            correct += 1
    return correct / n_pairs
```

- "成对准确率"是 RM 最常用的离线指标：RM 给被偏好回答的分数是否更高。
- 用不同的随机种子（默认 `Random(1)`）生成"留出集"。⚠️ 但由于词表只有 12 个词，留出集和训练集中出现的回答组合几乎重叠，这并不是真正意义上的泛化测试。

### 3.5 策略：每个 prompt 一行 logits

```python
def policy_probs(theta, prompt_idx):
    return softmax(theta[prompt_idx])
```

- `theta` 是 3×12 的列表：每个 prompt 独立地有一个 12 维 logits 向量，"回答"就是从中采样**一个** token。这相当于一个只生成 1 个 token 的语言模型。
- 初始 `theta` 全 0 → 均匀分布；`reference = [row[:] for row in theta]` 拷贝一份作为冻结的参考策略（扮演 `π_SFT`）。`row[:]` 逐行拷贝，避免两者共享同一个内层列表。

### 3.6 RLHF 主循环：采样、奖励、KL（⚠️ 关键缺陷）

```python
        for _ in range(16):
            p_idx = rng.randrange(len(PROMPTS))
            probs_new = policy_probs(theta, p_idx)
            token = sample_token(probs_new, rng)
            probs_ref = policy_probs(reference, p_idx)
            rm_score = w.get(VOCAB[token], 0.0)
            kl_term = kl(probs_new, probs_ref)
            reward = rm_score - beta * kl_term
            log_pi_old = math.log(max(probs_new[token], 1e-12))
            rollouts.append((p_idx, token, probs_new, reward, log_pi_old, kl_term))
```

- 每轮采 16 个 (prompt, token)，用 RM 打分，减去 `β·KL`，对应讲义的 `r_total = R_φ(x,y) - β·KL(π_θ‖π_ref)`。
- 存 `log_pi_old` 供后面算重要性比率，和第 08 节一样。

⚠️ **问题所在**：`kl(probs_new, probs_ref)` 是两个**完整分布**之间的 KL，对同一个 prompt 来说，不管采样到哪个 token，它的值都一样——**与动作无关**。策略梯度里，一个与动作无关的项乘以 `∇log π(a)` 后期望为 0（`Σ_a π(a)∇log π(a) = 0`，正是"baseline 不改变期望"的那个恒等式）。所以这个 KL 惩罚在期望上**不会把策略拉回参考模型**，它只是在不同 prompt 之间造成奖励偏移、增大 batch 奖励的方差，从而在标准化后稍微缩小 RM 信号——这就是为什么运行结果中 β 从 0.01 增大到 1.0，最终 KL 只从 2.29 降到 1.83。

正确做法是用**被采样 token 的对数比率**作为单样本 KL 估计（真实 LLM RLHF 中逐 token 的 KL 惩罚就是这样做的）：

```python
log_ratio = math.log(max(probs_new[token], 1e-12)) - math.log(max(probs_ref[token], 1e-12))
reward = rm_score - beta * log_ratio
```

实测修改后（同样 150 轮、同样种子），β=0.01/0.1/1.0 的最终 KL 变为 1.96/0.82/0.36，与 KL 正则目标的闭式最优解 `π* ∝ π_ref·exp(R/β)`（KL 分别约 2.16/0.92/0.37）吻合。讲义 Step 3 的示例代码也采用了整分布 KL 的写法，同样有这个问题。完整分析见测验 Q10。

### 3.7 advantage 标准化与裁剪更新

```python
        rewards = [rec[3] for rec in rollouts]
        mean_r = sum(rewards) / len(rewards)
        var_r = sum((r - mean_r) ** 2 for r in rewards) / len(rewards)
        sd_r = math.sqrt(var_r) + 1e-8
        advs = [(r - mean_r) / sd_r for r in rewards]

        for (p_idx, token, probs_new_at_rollout, _r, log_pi_old, _kl), adv in zip(rollouts, advs):
            probs = policy_probs(theta, p_idx)
            logp = math.log(max(probs[token], 1e-12))
            ratio = math.exp(logp - log_pi_old)
            clipped = (adv > 0 and ratio > 1 + eps) or (adv < 0 and ratio < 1 - eps)
            if clipped:
                continue
            for i in range(len(VOCAB)):
                grad = (1.0 if i == token else 0.0) - probs[i]
                theta[p_idx][i] += lr * ratio * adv * grad
```

- **没有 critic**：advantage 直接是"奖励减去 batch 均值再除以标准差"——用 batch 均值做 baseline。这其实更接近 GRPO / REINFORCE-with-baseline 的思路，而不是带 value head 的完整 PPO。⚠️ 而且 16 个样本混合了 3 个 prompt，用的是**全 batch 共享**的 baseline，而不是每个 prompt 各自的 baseline。
- **裁剪更新**：和第 08 节的 `ppo_update` 一样，被裁剪就 `continue`（梯度为 0），否则 `θ += lr·ratio·adv·∇log π`。因为 logits 直接就是参数，`∇_θ log π = onehot - probs`，不需要再乘特征。
- 只做**一遍**更新（没有多 epoch）。但由于同一 prompt 在 16 个样本中会重复出现、`theta` 在循环中被原地修改，后面样本的 `ratio` 会偏离 1，所以裁剪仍可能触发。
- 元组解包时用 `probs_new_at_rollout`、`_r`、`_kl` 接住但不使用，下划线前缀表示"故意忽略"。

### 3.8 记录与主函数

```python
        mean_kl = sum(rec[5] for rec in rollouts) / len(rollouts)
        mean_rm = sum(rec[3] + beta * rec[5] for rec in rollouts) / len(rollouts)
        history.append((it + 1, mean_rm, mean_kl))
```

- `rec[3] + beta * rec[5]` 把 KL 惩罚加回去，还原出纯 RM 分数。用下标访问元组可读性较差，生产代码应使用 `namedtuple` 或 `dataclass`。
- 记录的是**本轮采样时**（更新前）的指标。

```python
    for beta in (0.01, 0.1, 1.0):
        _, hist = rlhf_loop(w, updates=150, beta=beta, rng=random.Random(0))
```

- 三个 β 使用同一个种子 `Random(0)`，保证差异来自 β 而非随机性——这是做超参对比实验的正确姿势。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 回答 = 1~2 个词，RM = 词袋线性模型 | 讲义："the shape of the pipeline matters, not the scale" | 真实 RM 是 transformer + 标量 head，从 SFT 初始化 |
| 合成、完美可分的偏好 | 让 RM 一定能学会，聚焦流程 | 真实偏好约 30% 噪声；需要一致性过滤或 BT 温度 |
| RM 与 prompt 无关 | 简化 | 真实 RM 输入是 prompt + response |
| 省略 SFT，参考策略 = 均匀分布 | 减少代码 | 真实 `π_ref = π_SFT`，策略也从它初始化 |
| batch 均值作 baseline、无 critic | 代码短 | 真实 RLHF-PPO 有 value head；GRPO 用每个 prompt 的组内均值 |
| 整分布 KL 作为奖励项 | 写起来直观 | ⚠️ 与动作无关，几乎不约束策略；应用被采样 token 的对数比率 |
| 单次更新、无多 epoch | 简化 | 真实 PPO 做 K epoch；TRL 等库还提供自适应 β |
| 三个 β 共用同一种子 | 公平对比 | 生产中还要多种子取平均 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from ... import ...` | `from collections import Counter, defaultdict` | 从标准库模块导入特定类 |
| 元组拼接 + `set` + `sorted` | `tuple(sorted(set(GOOD + BAD)))` | 合并、去重、排序、转回不可变元组 |
| `collections.Counter` | `Counter(tokens)` | 计数字典：`Counter(("clear","clear"))` → `{'clear': 2}` |
| `collections.defaultdict` | `w = defaultdict(float)` | 缺失键自动初始化为 `float()` 即 0.0 |
| `dict.get(key, default)` | `w.get(t, 0.0)` | 只读访问，键不存在时返回默认值且不插入 |
| `.items()` 遍历 | `for t, c in bag(y_pos).items()` | 同时拿键和值 |
| `rng.choice` / `rng.randrange` | `rng.choice(GOOD)`、`rng.randrange(len(PROMPTS))` | 随机选元素 / 随机整数下标 |
| 多分支提前 `return` | `sigmoid` 中 `if x > 0: return ...` | 不需要 `else` |
| 列表推导式拷贝二维列表 | `[row[:] for row in theta]` | 逐行浅拷贝，内外层都独立 |
| `sorted(..., key=lambda ...)` | `sorted(w, key=lambda t: -w[t])[:6]` | 按权重降序取前 6；对字典排序得到的是键 |
| 嵌套元组解包 | `for (p_idx, token, ..., _kl), adv in zip(rollouts, advs)` | 一次解开 `zip` 产出的 `(元组, adv)` |
| `_` 前缀变量 | `_r`、`_kl`、`_, y_pos, y_neg = ...` | 约定：接收但不使用 |
| 生成器表达式求和 | `sum(rec[5] for rec in rollouts)` | 不建中间列表 |
| f-string 对齐与符号 | `f"{tok:<10}"`、`f"{w[tok]:+.3f}"`、`f"{beta:<5}"` | `<10` 左对齐宽 10；`+` 显示正负号 |
| `continue` | `if clipped: continue` | 跳过当前样本 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，Python 3.13，约 0.1 秒）输出：

```text
=== Stage 1: reward model (Bradley-Terry pairwise logistic) ===

top positive-weight tokens:
  helpful    w = +1.187
  clear      w = +1.165
  kind       w = +1.080
  specific   w = +1.051
  thorough   w = +1.047
  precise    w = +0.993

top negative-weight tokens:
  cold       w = -1.163
  vague      w = -1.119
  wrong      w = -1.089
  careless   w = -1.072
  rude       w = -1.062
  short      w = -1.021

RM pairwise accuracy on holdout (200 pairs) = 1.000

=== Stage 2: PPO-RLHF against RM with KL penalty ===

beta=0.01   initial: RM=-0.111 KL=0.000   final: RM=+1.185 KL=2.293
beta=0.1    initial: RM=-0.111 KL=0.000   final: RM=+1.186 KL=2.265
beta=1.0    initial: RM=-0.111 KL=0.000   final: RM=+1.179 KL=1.831
```

逐段解读：

- **RM 权重**：6 个好词全部为正（约 +1.0~+1.2），6 个坏词全部为负（约 -1.0~-1.2），讲义预期 "w assigns positive weights to good-word tokens and negative to bad"。权重大小的差异只来自各词被采样到的次数不同，没有语义含义。
- **准确率 1.000**：数据完美可分（好回答只含好词），任何正确符号的权重都能 100% 排对。真实 RM 的成对准确率通常远低于此。
- **initial RM=-0.111, KL=0.000**：第一轮策略就是均匀的参考策略，KL 为 0；16 个样本的平均 RM 分数接近 0（好坏词各半）。
- **final RM≈+1.18**：策略学会几乎只输出权重最高的好词（`helpful`、`clear` 约 +1.17~+1.19）。
- **KL 列是本节最值得琢磨的地方**：β 放大 100 倍，最终 KL 只从 2.29 降到 1.83，RM 分数几乎不变。按 RLHF 理论，β=1.0 时策略应当明显停留在参考分布附近（闭式最优解的 KL 约 0.37）。原因就是 3.6 中分析的"整分布 KL 与动作无关"。改成逐样本的对数比率后，β 才真正成为"RM 分数 vs KL"的调节旋钮。

---

## 7. 动手改一改

1. **RM 留出准确率**（讲义练习 Easy）：用 500 对训练、另外 100 对测试，确认准确率 > 90%；再在 `sample_pair` 中以 30% 概率交换 `y_pos`/`y_neg` 模拟标注噪声，观察权重和准确率的变化。
2. **修正 KL 惩罚**：按 3.6 改成逐样本对数比率，重新跑 β ∈ {0.0, 0.1, 1.0}（讲义练习 Medium），画出每轮的 RM 分数与 KL。
3. **闭式最优解对照**：实现测验 Q12 的 `optimal_policy`，把修正后训练得到的策略与 π* 的 KL 进行比较。
4. **按 prompt 分组的 baseline**：把 batch 均值改成"每个 prompt 内的均值"，这就是 GRPO 的组相对 advantage 思想。
5. **长度作弊模拟**：让回答可以是 1~4 个词，并把 RM 改成"每个好词 +1，总分不做长度归一化"，观察策略是否学会输出更长的回答；再改成长度归一化奖励对比。
6. **DPO**（讲义练习 Hard）：在同样的偏好数据上直接优化 `-log σ(β·[log π(y₊)/π_ref(y₊) - log π(y₋)/π_ref(y₋)])`，与 RLHF 结果比较。

---

## 8. 常见坑

- **与动作无关的 KL 惩罚**：用整分布 KL 当奖励不会给策略任何"回到参考模型"的梯度；用被采样 token 的 `log π_θ - log π_ref`，或把 KL 作为可求导的 loss 项。
- **朴素 sigmoid / log(sigmoid)**：极端奖励差会溢出或得到 `log(0)`；用分支写法或框架的 `logsigmoid`。
- **把 RM 准确率 1.0 当成"RM 很好"**：玩具数据完美可分；真实场景中准确率高也不代表在策略的新分布上可靠——这正是 reward hacking 的根源。
- **`defaultdict` 的副作用**：用 `w[t]` 读取不存在的键会插入新键；只读时用 `w.get(t, 0.0)`。
- **参考策略与训练策略共享引用**：`reference = theta` 会让二者指向同一对象，"冻结"失效；本代码用 `[row[:] for row in theta]` 避免了这个问题。讲义 Step 5 也提醒："you must not accidentally share parameters with policy"。
- **β 对比实验不固定种子**：不同 β 的差异会被随机性淹没；本代码对每个 β 都用 `Random(0)`。
