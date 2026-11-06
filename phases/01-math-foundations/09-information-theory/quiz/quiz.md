# 测验 · 信息论（Information Theory）

> **阶段 01 · 数学基础 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/information_theory.py](../code/information_theory.py) ｜ 代码讲解：[code/information_theory.讲解.md](../code/information_theory.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 信息量（surprise） | `I(x) = -log p(x)`；越不可能的事件信息量越大，必然事件信息量为 0 |
| 2 | 熵 entropy | `H(P) = -Σ p·log p`，平均意外程度；均匀分布最大（K 类时为 `log K`），确定分布为 0 |
| 3 | 交叉熵 cross-entropy | `H(P,Q) = -Σ p·log q`；标签为 one-hot 时退化为 `-log q(true_class)`，就是分类损失 |
| 4 | KL 散度 | `D_KL(P‖Q) = H(P,Q) - H(P) ≥ 0`；不对称、不是距离；P 固定时最小化交叉熵 ⇔ 最小化 KL |
| 5 | 交叉熵 = 负对数似然 | 平均 `-log q(yᵢ)` 就是 NLL；最小化交叉熵 = 最大化训练数据的似然 |
| 6 | softmax + 交叉熵 | softmax 先减最大值保证数值稳定；对 logits 的梯度就是 `预测概率 - one-hot 标签` |
| 7 | 联合熵、条件熵、互信息 | `H(X,Y) = H(X) + H(Y|X)`；`I(X;Y) = H(X) + H(Y) - H(X,Y)`，对称、非负、独立时为 0 |
| 8 | 互信息做特征选择 | 能捕捉任意统计依赖（含非线性），相关系数只能捕捉线性关系 |
| 9 | Label smoothing | 软标签 `(1-ε)·hard + ε/K` 提高目标分布的熵，防止 logits 无限增大，起正则化与改善校准的作用 |
| 10 | bits / nats 与困惑度 | log₂ → bits，ln → nats（PyTorch 默认）；`PPL = e^{CE}`（nats）或 `2^{CE}`（bits），表示"等效候选数" |

### 核心技能（能动手做到）

- [ ] 不用 NumPy，从零实现 `entropy`、`cross_entropy`、`kl_divergence`，并在 `[0.7,0.2,0.1]` 与两个模型分布上验证 `H(P,Q) = H(P) + KL(P‖Q)`
- [ ] 手写数值稳定的 `softmax` 和 `cross_entropy_loss`，能说明为什么用 `logsumexp(z) - z_true` 比 `-log(softmax(z)[true])` 更稳
- [ ] 从联合概率表算出边缘分布、`H(X,Y)`、`H(Y|X)`、`I(X;Y)`，并用两种公式交叉验证互信息
- [ ] 给定一串 `(真实 token, logits)`，计算序列困惑度（讲义练习 4），并能把 bits 与 nats 的结果互相换算
- [ ] 用互信息给 4 个二值特征排序（强信号 / 弱信号 / 噪声 / 常数），并解释噪声特征 MI 不为 0 的原因
- [ ] 实现 label smoothing，说明加了平滑后训练 loss 的理论下界为什么不再是 0

---

## 二、基础自测（选择题）

**Q1.** 一个均匀的 8 面骰子，其熵是：

- A. 1 bit
- B. 2.58 bits
- C. 3 bits
- D. 8 bits

**Q2.** 关于 KL 散度 `D_KL(P‖Q)`，下列说法正确的是：

- A. `D_KL(P‖Q) = D_KL(Q‖P)`，所以它是一种距离
- B. 当 Q 比 P "更好"时，KL 可以为负
- C. `D_KL(P‖Q) ≥ 0`，当且仅当 `P = Q` 时等于 0
- D. 只要 Q 在某个 `p(x) = 0` 的位置取 0，KL 就是无穷大

**Q3.** 某语言模型在测试集上的平均交叉熵为每 token 2.0 nats，它的困惑度约为：

- A. 2.0
- B. 4.0
- C. 7.39
- D. 100

**Q4.** 模型 A 报告的平均交叉熵为 3.0 bits/token，模型 B 报告的是 2.1 nats/token（同一个 tokenizer、同一份测试集）。哪个困惑度更低？

- A. A 更低
- B. B 更低
- C. 一样
- D. 单位不同，无法比较

**Q5.** 使用 `ε = 0.1`、4 分类的 label smoothing，真实类别为第 3 类。训练时交叉熵损失的**理论最小值**是：

- A. 0
- B. 目标分布 `[0.025, 0.025, 0.925, 0.025]` 自身的熵，约 0.349 nats
- C. ε = 0.1
- D. `log 4 ≈ 1.386` nats

**Q6.** logits 为 `[2.0, 1.0, 0.1]`，真实类别为 0，softmax 结果为 `[0.6590, 0.2424, 0.0986]`。交叉熵损失对 logits 的梯度是：

- A. `[0.6590, 0.2424, 0.0986]`
- B. `[-0.3410, 0.2424, 0.0986]`
- C. `[0.3410, -0.2424, -0.0986]`
- D. `[-1.0, 0.0, 0.0]`

**Q7.** 决策树在每个节点选择划分特征 X 时，"信息增益最大"等价于：

- A. 使 `H(X)` 最大
- B. 使 `H(Y|X)` 最大
- C. 使互信息 `I(X;Y) = H(Y) - H(Y|X)` 最大
- D. 使联合熵 `H(X,Y)` 最大

**Q8.** 设 X 是公平硬币，Y = X（完全复制）。则 `I(X;Y)` 和 `H(X,Y)` 分别为：

- A. 0 bit，2 bits
- B. 1 bit，1 bit
- C. 1 bit，2 bits
- D. 2 bits，1 bit

---

## 三、动手 / 代码题

**Q9.** 写出下面代码的输出（保留 4 位小数），并解释为什么三个 loss 两两之差恰好等于对应 logits 之差。

```python
logits = [2.0, 1.0, 0.1]
probs = softmax(logits)
for c in range(3):
    l = cross_entropy_loss(c, logits)
    print(f"    Class {c}: loss={l:.4f}  prob={probs[c]:.4f}")
```

**Q10.**（找 bug）`information_theory.py` 里有两处"能运行、但在某些输入下会出错"的地方，请分别指出现象并修复：

```python
def cross_entropy_loss(true_class, logits):
    probs = softmax(logits)
    return -math.log(probs[true_class])


def perplexity(avg_cross_entropy, base="e"):
    if base == "e":
        return math.exp(avg_cross_entropy)
    return 2 ** avg_cross_entropy
```

提示：试试 `cross_entropy_loss(1, [1000.0, 0.0])`，以及仿照文件里其他函数的习惯写 `perplexity(1.0, base=math.e)`。

**Q11.**（解释现象）`PERPLEXITY IN LANGUAGE MODELS` 这一段用 `random.gauss(0, 1)` 生成 50 维随机 logits、随机真实 token，结果是 `Avg CE loss: 4.3973 nats`，`Perplexity: 81.23`，比"均匀猜测"的 50 还差。(a) 为什么随机 logits 反而比均匀分布更差？请估算期望的困惑度。(b) 如果把所有 logits 都设为 0，困惑度是多少？

**Q12.**（实现）完成讲义练习 4：写 `sequence_perplexity(pairs)`，输入 `[(true_token_index, logits), ...]`，返回序列困惑度（nats 口径），要求对极端 logits（如 `[1000.0, 0.0]`）不会因为 `log(0)` 崩溃。再写一个 `mi_from_entropies(joint)`，用 `H(X) + H(Y) - H(X,Y)` 计算互信息，并在 `partial = [[0.3, 0.2], [0.1, 0.4]]` 上与 `mutual_information` 的结果（0.1245 bits）对照。

---

## 四、面试高频题

**Q13.**（基础必考）分类任务为什么用交叉熵损失而不是 MSE？请从概率（最大似然）、梯度、优化三个角度回答。

**Q14.**（原理深挖）熵、交叉熵、KL 散度三者是什么关系？KL 为什么不对称？`KL(P‖Q)` 和 `KL(Q‖P)` 作为优化目标时行为有什么不同？请举出它们在 VAE、知识蒸馏、RLHF 中的用法。

**Q15.**（工程实践）你要比较两个 LLM 的困惑度：一个报 PPL=12，另一个报 PPL=9。这个比较可能有哪些"坑"？困惑度在工程上应该怎么正确计算和汇报？

**Q16.**（原理深挖）Label smoothing 做了什么？从信息论角度为什么它能起到正则化作用、改善校准？它有什么副作用或不适用的场景？

**Q17.**（场景设计）你有 300 个候选特征（含连续和类别特征）要为一个二分类模型做筛选，打算用互信息排序。请说明具体怎么做，以及互信息方法的局限和对应的补救措施。

---

## 五、参考答案与解析

### Q1 — 答案：C

均匀分布 `H = log₂ K = log₂ 8 = 3 bits`——等于"用二进制编号区分 8 个结果所需的位数"。B 是 6 面骰子的熵（`log₂ 6 ≈ 2.585`，代码输出 `Fair die (6 sides) H = 2.5850 bits`）。

### Q2 — 答案：C

由 Gibbs 不等式，`D_KL(P‖Q) ≥ 0`，当且仅当两个分布处处相等时为 0。A 错：代码中 `P=[0.9,0.1]`、`Q=[0.5,0.5]` 时 `KL(P‖Q)=0.5310`、`KL(Q‖P)=0.7370`，明显不对称。B 错：P 是"真实分布"，交叉熵 `H(P,Q)` 的最小值就是 `H(P)`，KL 不可能为负。D 说反了：只有当 `p(x) > 0` 而 `q(x) = 0` 时才是无穷大；`p(x) = 0` 的位置对 KL 没有贡献（代码中 `cross_entropy` 遇到 `pi > 0 且 qi <= 0` 返回 `inf`，`pi = 0` 的项直接跳过）。

### Q3 — 答案：C

nats 口径下 `PPL = e^{CE} = e² ≈ 7.39`，意思是模型平均"像在约 7.4 个等可能的 token 中挑一个"。A 把交叉熵直接当成困惑度；B 是误用了 `2^CE`。

### Q4 — 答案：A

统一换算：A 的 `PPL = 2³ = 8`；B 的 `PPL = e^{2.1} ≈ 8.17`。A 更低。也可以把 B 换成 bits：`2.1 / ln2 ≈ 3.03 bits > 3.0 bits`。D 错：只要知道单位，就能换算（1 nat = 1.4427 bits）；真正"无法比较"的情况是 tokenizer 不同，见 Q15。

### Q5 — 答案：B

`CE(soft, q) = H(soft) + KL(soft‖q) ≥ H(soft)`，当模型输出 q 恰好等于软标签时取到下界。软标签 `[0.025, 0.025, 0.925, 0.025]` 的熵约为 0.349 nats（代码 `label_smoothing_demo` 打印 `H(target)=0.3488`）。这说明 label smoothing 下模型**不会再被激励把正确类概率推到 1**，logits 也就不会无限增大——这正是它的正则化机制。A 是 one-hot 目标时的下界。

### Q6 — 答案：B

softmax + 交叉熵对 logits 的梯度为 `p - y`：`[0.6590-1, 0.2424-0, 0.0986-0] = [-0.3410, 0.2424, 0.0986]`。梯度下降沿负梯度方向更新：正确类的 logit 增大，其余类的 logit 减小，且错误类的"惩罚力度"正比于它被分到的概率。讲义说这是交叉熵与 softmax "天生一对"的原因：梯度干净、有界、不会饱和。C 是负梯度方向；A 忘了减去标签。

### Q7 — 答案：C

信息增益 = 划分前标签的熵 `H(Y)` - 划分后的加权条件熵 `H(Y|X)` = `I(X;Y)`。由于 `H(Y)` 在同一个节点是常数，最大化信息增益等价于讲义说的"最小化 `H(Y|X)`"。B 正好相反。

### Q8 — 答案：B

`I(X;X) = H(X) = 1 bit`（讲义："A variable shares all its information with itself"）。联合分布只有 `(0,0)` 和 `(1,1)` 两个结果各 0.5，所以 `H(X,Y) = 1 bit`。用公式验证：`I = H(X) + H(Y) - H(X,Y) = 1 + 1 - 1 = 1`。C 是独立时的联合熵（2 bits）配上了依赖时的互信息，二者矛盾。

### Q9 — 参考答案

输出：

```
    Class 0: loss=0.4170  prob=0.6590
    Class 1: loss=1.4170  prob=0.2424
    Class 2: loss=2.3170  prob=0.0986
```

推导：`-log softmax(z)_c = -log(e^{z_c} / Σe^{z_k}) = logsumexp(z) - z_c`。`logsumexp(z)` 对三个类别都相同（约 2.4170），所以

- `loss₁ - loss₀ = z₀ - z₁ = 2.0 - 1.0 = 1.0`
- `loss₂ - loss₁ = z₁ - z₂ = 1.0 - 0.1 = 0.9`

这也说明了**交叉熵对 logits 是"线性 + logsumexp"的结构**：这正是框架中 `log_softmax` 和 `CrossEntropyLoss` 直接以 logits 作为输入的原因。

### Q10 — 参考答案

**问题 1：`cross_entropy_loss` 在极端 logits 下抛出 `ValueError`。** `softmax([1000, 0])` 中第二项是 `exp(0 - 1000)`，在 float64 下下溢为 `0.0`，于是 `math.log(0.0)` 抛出 `ValueError: math domain error`（实测 logits 差距超过约 745 就会触发；差距为 700 时还能算出 `700.0`）。数学上正确的 loss 应该是 1000。

修复：在 log 空间直接计算 log-softmax，不经过概率：

```python
def cross_entropy_loss(true_class, logits):
    m = max(logits)
    log_z = m + math.log(sum(math.exp(z - m) for z in logits))   # logsumexp
    return log_z - logits[true_class]
```

`sum(...)` 中最大项为 `exp(0) = 1`，所以 `log` 的参数 ≥ 1，永远不会是 0。PyTorch 的 `CrossEntropyLoss` 接收 logits 而不是概率，内部就是这样做的。

**问题 2：`perplexity` 的 `base` 参数约定与其他函数不一致。** 文件中 `entropy`、`cross_entropy` 都用数值底数（`base=2`、`base=math.e`），而 `perplexity` 用字符串 `"e"` 判断。调用 `perplexity(1.0, base=math.e)` 时 `math.e == "e"` 为 False，落入 `2 ** 1.0`，**静默返回 2.0 而不是 e ≈ 2.718**；`base=10` 也会错误地返回 `2**x`。

修复：统一用数值底数，直接 `base ** x`：

```python
def perplexity(avg_cross_entropy, base=math.e):
    return base ** avg_cross_entropy     # nats 用 e，bits 用 2
```

这类"不抛异常但结果错误"的 bug 最危险，接口设计应保持全文件一致。

### Q11 — 参考答案

(a) 对随机 logits，`CE = logsumexp(z) - z_true`。真实 token 是随机选的，`E[z_true] = 0`；而 `logsumexp(z) = log Σₖ e^{zₖ} ≈ log(K·E[e^z]) = log K + σ²/2`（标准正态 `E[e^z] = e^{1/2}`）。所以

- 期望 `CE ≈ log 50 + 0.5 ≈ 3.912 + 0.5 = 4.412 nats`，
- 期望 `PPL ≈ 50 × e^{0.5} ≈ 82.4`，

与实测 `4.3973` 和 `81.23` 吻合。直觉：随机 logits 会"随机地自信"——把概率集中到某些错误 token 上，平均下来比"一视同仁"的均匀分布更差。由 Jensen 不等式也可以看出，在 `E[z_true]=0` 的前提下，logits 的任何随机波动都会增大 `logsumexp`。

(b) logits 全为 0 时 softmax 是均匀分布，每个 token 的 `CE = log 50`，`PPL = 50`（实测 `49.99999999999999`）。所以讲义说 "The model is better than random if perplexity < vocab size"，这里的 "random" 指**均匀猜测**的基线，而这个 demo 中随机 logits 的"模型"其实连基线都不如——代码没有点明这一点。

### Q12 — 参考答案

```python
import math
from information_theory import entropy, joint_entropy, mutual_information


def sequence_perplexity(pairs):
    if not pairs:
        raise ValueError("empty sequence")
    total_nll = 0.0
    for true_idx, logits in pairs:
        m = max(logits)
        log_z = m + math.log(sum(math.exp(z - m) for z in logits))  # logsumexp
        total_nll += log_z - logits[true_idx]                       # -log softmax
    return math.exp(total_nll / len(pairs))     # 先对 NLL 取平均，再取指数


def mi_from_entropies(joint, base=2):
    hx = entropy([sum(row) for row in joint], base)           # 行和 = p(x)
    hy = entropy([sum(col) for col in zip(*joint)], base)     # 列和 = p(y)
    return hx + hy - joint_entropy(joint, base)


pairs = [(1, [5.0, 2.0, 0.5]), (0, [2.0, 1.0, 0.1]), (2, [0.0, 0.0, 0.0])]
print(sequence_perplexity(pairs))                      # ≈ 4.5948
print(mi_from_entropies([[0.3, 0.2], [0.1, 0.4]]))     # ≈ 0.1245
print(mutual_information([[0.3, 0.2], [0.1, 0.4]]))    # ≈ 0.1245
```

要点：

- 三个 token 的 NLL 分别为 `3.0591`（讲义练习 2 的答案）、`0.4170`、`log 3 ≈ 1.0986`，平均后取 `exp` 得 `≈ 4.5948`。
- **先平均 NLL 再取指数**（几何平均），而不是对每个 token 的困惑度做算术平均。
- 用 logsumexp 计算，`[1000.0, 0.0]` 这类输入不会因 `log(0)` 崩溃；但若平均 NLL 本身极大（如 1000），`math.exp` 仍会 `OverflowError`——这时应直接汇报 NLL，或者说明困惑度"溢出"。
- `zip(*joint)` 是转置技巧，把行列表变成列元组；两种互信息公式在 `partial` 上的结果只在小数点后第 15 位有差异（浮点误差）。

### Q13 — 参考回答要点

- 概率角度：分类模型输出类别分布 q，假设标签服从 Categorical(q)，最大化似然 `∏ q(yᵢ)` ⇔ 最小化 `-Σ log q(yᵢ)`，这正是交叉熵（讲义"Maximum likelihood view"）。MSE 对应的是"高斯噪声"假设，用于回归。
- 梯度角度：softmax + CE 对 logits 的梯度是 `p - y`，误差越大梯度越大。sigmoid/softmax + MSE 的梯度会多乘一项 `p(1-p)`，当模型"错得很自信"（p≈0 但标签是 1）时，这一项趋于 0，梯度消失，学不动。
- 优化角度：对逻辑回归，CE 关于参数是凸的；sigmoid + MSE 是非凸的，存在平坦区。
- 信息论角度：CE = H(P) + KL(P‖Q)，最小化它就是让模型分布逼近真实分布。
- 加分点：工程上直接对 logits 用 `CrossEntropyLoss`（内部 log-softmax），不要先 softmax 再取 log；多标签任务用 `BCEWithLogitsLoss`。

### Q14 — 参考回答要点

- 关系：`H(P,Q) = H(P) + D_KL(P‖Q)`。熵是"用最优编码时的平均码长"，交叉熵是"用 Q 的编码去编 P 的数据时的平均码长"，KL 是多花的那部分。P 固定时三者中只有 KL 随 Q 变化，所以最小化 CE ⇔ 最小化 KL。
- 不对称原因：期望是在**第一个分布**下取的。`KL(P‖Q)` 用 P 加权，惩罚"P 有质量而 Q 没有"的地方。
- 优化行为：
  - **前向 KL `KL(P‖Q)`**（最小化 over Q）：Q 必须覆盖 P 的所有高概率区域，否则代价无穷 → "mode-covering"，Q 倾向于铺开。最大似然训练就是前向 KL。
  - **反向 KL `KL(Q‖P)`**：Q 在 P 为 0 的地方不能有质量，但可以忽略 P 的某些模式 → "mode-seeking"，Q 倾向于锁定一个峰。
- 应用：
  - VAE：ELBO 中的 `KL(q(z|x)‖p(z))` 把后验近似拉向先验（变分推断用的是反向 KL 形式）。
  - 知识蒸馏：让学生分布逼近教师的软标签分布（常用带温度的 `KL(teacher‖student)`）。
  - RLHF：在奖励中加 `-β·KL(π‖π_ref)`，防止策略偏离参考模型太远、出现奖励投机。
- 常见误区：把 KL 叫"距离"并用在需要三角不等式的地方；需要对称有界的度量时可以考虑 JS 散度。

### Q15 — 参考回答要点

- 可能的坑：
  1. **Tokenizer 不同**：PPL 是"每 token"的指标，词表更大、切分更粗的 tokenizer 每个 token 承载更多信息，PPL 天然不同；跨 tokenizer 要换成 bits-per-byte / bits-per-character 之类与切分无关的指标。
  2. **单位不同**：bits 口径用 `2^CE`，nats 口径用 `e^CE`，混用会差很多（见 Q4）。
  3. **测试集不同、上下文长度不同**：长上下文、滑动窗口步长不同都会影响 PPL。
  4. **数据污染**：测试集出现在训练语料里会让 PPL 虚低。
  5. **是否计入特殊 token / padding**：padding 位置必须 mask 掉。
- 正确计算：对所有有效 token 的 NLL 求和，除以有效 token 总数，再取 `exp`（**几何平均**），不要对每个句子的 PPL 做算术平均。
- 解释：PPL=9 表示模型平均像在 9 个等可能选项中做选择；讲义提到 GPT-2 在常见基准上约 30，现代模型在熟悉领域能到个位数。
- 加分点：PPL 低不等于下游任务好（尤其是对齐后的聊天模型，RLHF 往往会提高 PPL）；PPL 适合比较同一 tokenizer 下的预训练/继续预训练质量。

### Q16 — 参考回答要点

- 做法：`soft = (1-ε)·one_hot + ε/K`，等价于 `L = (1-ε)·CE(hard, q) + ε·CE(uniform, q)`；第二项惩罚偏离均匀分布的预测（讲义公式中的 `H_uniform(prediction)` 指的就是均匀分布对预测的交叉熵）。
- 信息论解释：one-hot 目标熵为 0，要让 CE 降到 0 必须 `q(true) → 1`，即 logits 差距 → ∞，模型被推向极端自信；软标签熵 > 0（ε=0.1、K=4 时约 0.349 nats），loss 下界变为 `H(soft)`，最优 logits 是有限值，自然限制了置信度。
- 好处：防止 logits 爆炸、正则化、改善校准（预测概率更接近真实正确率），在大规模分类与机器翻译中常用（ε=0.1 是常见值）。
- 副作用：
  - 会抹掉类别之间的"相对相似性"信息，用带 label smoothing 训练的教师做知识蒸馏，效果可能变差（Müller et al., 2019, *When Does Label Smoothing Help?*）。
  - 训练 loss 不再能降到 0，监控曲线时要以 `H(soft)` 为下界来解读。
  - 类别非常不平衡或标签本身就是概率分布（软标签）时需谨慎。
- 加分点：PyTorch `nn.CrossEntropyLoss(label_smoothing=0.1)` 内置该功能。

### Q17 — 参考回答要点

- 步骤：
  1. 类别特征直接统计联合频率表；连续特征先**分箱**（等频分箱更稳）或用 KNN 型估计器（如 sklearn 的 `mutual_info_classif`，基于 Kraskov 等人的方法）。
  2. 对每个特征算 `I(Xᵢ; Y)`，按分数排序取 top-k，或用交叉验证决定 k。
  3. 用一个随机打乱标签的"置换基线"估计噪声水平，过滤掉 MI 不显著高于基线的特征。
- 局限与补救：
  - **有限样本偏差**：plug-in 估计总是 ≥ 0，即使独立也会偏正（本节 demo 中纯噪声特征的 MI 为 0.0110 bits 而不是 0）。用置换检验或偏差修正。
  - **分箱敏感**：箱数太多会高估 MI，太少会丢信息；需要固定策略并做稳健性检查。
  - **只看单变量**：忽略特征间冗余（两个高度相关的特征会同时排前），也看不到交互效应（如 XOR：单个特征 MI 为 0，组合起来完全决定 Y）。补救：mRMR（最大相关最小冗余）、条件互信息、基于模型的特征重要性或递归特征消除。
  - **高基数类别特征**（如 ID）会因为"记住"样本而 MI 虚高，需要做频率截断或正则化。
- 加分点：说明 MI 的优势——对非线性、非单调关系同样有效，相关系数做不到（讲义对比表）；常数特征 MI 恰为 0（demo 中 `constant MI = 0.0000`）。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 06 概率和分布](../../06-probability-and-distributions/docs/zh.md)：期望、联合分布、边缘分布、条件概率、独立性。
- [阶段 01 · 07 贝叶斯定理](../../07-bayes-theorem/docs/zh.md)：最大似然估计（MLE）——"交叉熵 = 负对数似然"的另一半。

### 本节被哪些后续内容用到
- [阶段 01 · 13 数值稳定性](../../13-numerical-stability/docs/zh.md)：log-sum-exp、稳定的 softmax 与 log-softmax。
- [阶段 01 · 14 范数与距离](../../14-norms-and-distances/docs/zh.md)：KL 散度与真正的距离度量的区别。
- [阶段 02 · 04 决策树](../../../02-ml-fundamentals/04-decision-trees/docs/zh.md)：信息增益 = 互信息，熵作为划分准则。
- [阶段 02 · 18 特征选择](../../../02-ml-fundamentals/18-feature-selection/docs/zh.md)：基于互信息的过滤式特征选择。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：交叉熵、label smoothing 在神经网络中的使用。
- [阶段 08 · 02 自编码器与 VAE](../../../08-generative-ai/02-autoencoders-vae/docs/zh.md)：ELBO 中的 KL 项。
- [阶段 10 · 07 RLHF](../../../10-llms-from-scratch/07-rlhf/docs/zh.md)、[阶段 10 · 08 DPO](../../../10-llms-from-scratch/08-dpo/docs/zh.md)：KL 约束防止策略偏离参考模型。
- [阶段 10 · 10 评估](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)、[阶段 19 · 73 困惑度与校准](../../../19-capstone-projects/73-perplexity-calibration/docs/zh.md)：困惑度在 LLM 评估中的计算与使用。

### 延伸关键词
`Gibbs 不等式` · `Jensen-Shannon 散度` · `前向 / 反向 KL (mode-covering / mode-seeking)` · `ELBO` · `知识蒸馏 (Knowledge Distillation)` · `温度缩放 (Temperature Scaling)` · `bits-per-byte` · `信息瓶颈 (Information Bottleneck)` · `InfoNCE` · `mRMR 特征选择`
