# 代码讲解 · information_theory.py

> **所属小节**：阶段 01 · 数学基础 · 第 09 节 信息论 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python information_theory.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy

---

## 1. 这份代码在考察什么

这份脚本把讲义中的每个信息论公式都写成一个十行以内的纯 Python 函数，然后用一连串小实验把它们串起来：

1. **从"意外程度"到熵**：`information_content` → `entropy`，看清熵就是"信息量的期望"。
2. **交叉熵、KL 与损失函数的关系**：数值验证 `H(P,Q) = H(P) + KL(P‖Q)`，以及"交叉熵损失 = 负对数似然"。
3. **softmax + 交叉熵**：从 logits 出发计算分类损失，体会"减最大值"的数值稳定技巧。
4. **多变量信息量**：联合熵、条件熵、互信息，以及互信息在特征选择中的实际用法。
5. **工程中的两个"日常"概念**：困惑度（perplexity）和 label smoothing，各自对应一个 demo。

> 一句话：**你每天调用的 `CrossEntropyLoss`、论文里的 perplexity、RLHF 里的 KL 惩罚，都能在这 360 行里找到最朴素的实现**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `information_content(p, base)` | 函数 | `-log p`，处理 p≤0 与 p≥1 的边界 | 信息量 / 意外程度 |
| `entropy(probs, base)` | 函数 | `Σ p·I(p)`，跳过 p=0 | 熵 |
| `cross_entropy(p, q, base)` | 函数 | `-Σ p·log q`；p>0 而 q≤0 时返回 `inf` | 交叉熵 |
| `kl_divergence(p, q, base)` | 函数 | `CE - H` | KL 散度 |
| `mutual_information(joint, base)` | 函数 | 从联合概率表计算 `Σ p(x,y)·log(p(x,y)/(p(x)p(y)))` | 互信息 |
| `softmax(logits)` | 函数 | 减最大值后 exp 再归一化 | softmax |
| `cross_entropy_loss(true_class, logits)` | 函数 | `-log softmax(logits)[true_class]` | 分类损失 |
| `negative_log_likelihood(labels, all_logits)` | 函数 | 多个样本 CE 的平均 | NLL |
| `perplexity(avg_ce, base)` | 函数 | `e^CE` 或 `2^CE` | 困惑度 |
| `conditional_entropy` / `joint_entropy` | 函数 | `H(Y|X)` 与 `H(X,Y)` | 条件熵、联合熵 |
| `label_smoothing_demo` | 演示 | 4 个 ε 下的软标签熵与 CE | Label smoothing |
| `feature_selection_mi_demo` | 演示 | 用 MI 给 4 个合成特征排序 | 特征选择 |
| `if __name__ == "__main__":` 主块 | 演示 | 依次跑 9 段实验并打印 | — |

依赖关系：`entropy → information_content`；`kl_divergence → cross_entropy + entropy`；`negative_log_likelihood → cross_entropy_loss → softmax`；`label_smoothing_demo → softmax + cross_entropy + entropy`；`feature_selection_mi_demo → mutual_information`。

---

## 3. 逐段精讲

### 3.1 信息量与熵

```python
def information_content(p, base=2):
    if p <= 0:
        return float('inf')
    if p >= 1:
        return 0.0
    return -math.log(p) / math.log(base)


def entropy(probs, base=2):
    return sum(
        p * information_content(p, base)
        for p in probs if p > 0
    )
```

- `-math.log(p) / math.log(base)` 是**换底公式**：`log_b(p) = ln(p) / ln(b)`。`base=2` 得到 bits，`base=math.e` 得到 nats。
- 边界处理：
  - `p <= 0` 返回无穷大——"不可能事件发生了"是无限意外；
  - `p >= 1` 直接返回 `0.0`——必然事件没有信息量。这里显式返回 0 还顺带避免了 `-math.log(1.0)` 得到 `-0.0`、打印成 `-0.0000` 的尴尬。
- `entropy` 中的 `if p > 0` 实现了约定 **`0·log 0 = 0`**（极限 `lim p→0 p·log p = 0`）。不加这个过滤，`p=0` 会得到 `0 * inf = nan`。
- 熵就是"信息量的期望"：每个结果的意外程度按概率加权平均。

### 3.2 交叉熵与 KL 散度

```python
def cross_entropy(p, q, base=2):
    total = 0.0
    for pi, qi in zip(p, q):
        if pi > 0:
            if qi <= 0:
                return float('inf')
            total += pi * (-math.log(qi) / math.log(base))
    return total


def kl_divergence(p, q, base=2):
    return cross_entropy(p, q, base) - entropy(p, base)
```

- 期望是在**真实分布 p** 下取的，所以只遍历 `pi > 0` 的位置；`pi = 0` 的类别对交叉熵没有贡献。
- `pi > 0` 但 `qi <= 0`：模型说"绝不可能"，结果却发生了，交叉熵为无穷大，**提前返回** `inf`。这正是为什么模型输出永远要保证概率严格大于 0（softmax 天然满足）。
- `kl_divergence` 直接用讲义的恒等式 `KL = CE - H` 实现，代码最短，也最能体现"KL 就是多花的那部分码长"。
- ⚠️ 设计取舍：用减法实现 KL 时，若两个大数非常接近，理论上可能出现 `-1e-17` 这类极小负数；直接按定义 `Σ p·log(p/q)` 计算更稳。在本文件的示例中（包括 `KL(P‖P)`）结果都是精确的 0 或正数。
- 不对称性：`KL(P‖Q)` 用 P 加权，`KL(Q‖P)` 用 Q 加权，`[0.9,0.1]` 与 `[0.5,0.5]` 的两个方向分别是 0.5310 与 0.7370 bits。

### 3.3 互信息、条件熵、联合熵

```python
def mutual_information(joint_probs, base=2):
    rows = len(joint_probs)
    cols = len(joint_probs[0])

    margin_x = [sum(joint_probs[i][j] for j in range(cols)) for i in range(rows)]
    margin_y = [sum(joint_probs[i][j] for i in range(rows)) for j in range(cols)]

    mi = 0.0
    for i in range(rows):
        for j in range(cols):
            pxy = joint_probs[i][j]
            if pxy > 0 and margin_x[i] > 0 and margin_y[j] > 0:
                mi += pxy * math.log(pxy / (margin_x[i] * margin_y[j])) / math.log(base)
    return mi
```

- 输入是二维联合概率表：**行对应 X，列对应 Y**。`margin_x` 是行和（`p(x)`），`margin_y` 是列和（`p(y)`）——这就是"边缘化"。
- 公式 `I(X;Y) = Σ p(x,y)·log[p(x,y) / (p(x)p(y))]`：如果 X、Y 独立，`p(x,y) = p(x)p(y)`，每一项的 log 都是 0，MI = 0。
- 三重 `> 0` 判断防止 `log(0)` 和除零。实际上 `pxy > 0` 已蕴含两个边缘概率 > 0，后两个条件属于防御性写法。
- 一个有趣的巧合：`dependent = [[0.45, 0.05], [0.05, 0.45]]` 的 MI 是 0.5310 bits，与 `KL([0.9,0.1]‖[0.5,0.5])` 完全相同。原因是 `I(X;Y) = E_x[KL(p(y|x) ‖ p(y))]`，而这里每一行的条件分布都是 `[0.9, 0.1]`（或其镜像），边缘分布是 `[0.5, 0.5]`。

```python
def conditional_entropy(joint_probs, base=2):
    # ...
    for i in range(rows):
        for j in range(cols):
            pxy = joint_probs[i][j]
            if pxy > 0 and margin_x[i] > 0:
                p_y_given_x = pxy / margin_x[i]
                h_yx -= pxy * math.log(p_y_given_x) / math.log(base)
    return h_yx
```

- `H(Y|X) = -Σ p(x,y)·log p(y|x)`，其中 `p(y|x) = p(x,y) / p(x)`。注意权重是**联合概率** `p(x,y)`，而不是条件概率。
- `h_yx -= ...` 用减法累加，因为 log 概率是负数，减去负数等于加上正的信息量。
- `joint_entropy` 就是把二维表当成一个长度为 `rows×cols` 的分布来算熵。
- 主程序用它们验证链式法则 `H(X,Y) = H(X) + H(Y|X)`：`1.0000 + 0.4690 = 1.4690`。

### 3.4 softmax 与交叉熵损失

```python
def softmax(logits):
    max_logit = max(logits)
    exps = [math.exp(z - max_logit) for z in logits]
    total = sum(exps)
    return [e / total for e in exps]


def cross_entropy_loss(true_class, logits):
    probs = softmax(logits)
    return -math.log(probs[true_class])
```

- **减最大值**是 softmax 的标准数值稳定写法：`softmax(z) = softmax(z - c)` 对任意常数 c 成立；取 `c = max(z)` 后最大的指数是 `exp(0) = 1`，不会上溢（`math.exp(1000)` 会抛 `OverflowError`），分母至少为 1。
- 由于标签是 one-hot，交叉熵 `-Σ p·log q` 退化为 `-log q[true_class]`——讲义说"That is the entire cross-entropy loss formula for classification"。
- ⚠️ 刻意的简化：先算概率再取 log。当 logits 差距很大时（超过约 745），较小类别的概率在 float64 中下溢为 `0.0`，`math.log(0.0)` 抛出 `ValueError: math domain error`。例如 `cross_entropy_loss(1, [1000.0, 0.0])` 会崩溃，正确答案应为 1000。更稳的写法是直接计算 log-softmax：`logsumexp(z) - z[true_class]`，这也是 PyTorch `CrossEntropyLoss` 只接收 logits 的原因。
- 由 `loss_c = logsumexp(z) - z_c` 可知：同一组 logits 下，不同真实类别的 loss 之差恰好等于 logits 之差（输出中 0.4170 / 1.4170 / 2.3170 两两相差 1.0 和 0.9）。

### 3.5 负对数似然与困惑度

```python
def negative_log_likelihood(labels, all_logits):
    return sum(
        cross_entropy_loss(label, logits)
        for label, logits in zip(labels, all_logits)
    ) / len(labels)


def perplexity(avg_cross_entropy, base="e"):
    if base == "e":
        return math.exp(avg_cross_entropy)
    return 2 ** avg_cross_entropy
```

- `negative_log_likelihood` 就是对每个样本的交叉熵损失求平均。主程序再用 `-Σ math.log(softmax(lg)[lb]) / n` 这种"似然"写法算一遍，两者差值为 `0.00e+00`——**因为它们本来就是同一组浮点运算**。这个 demo 的意义在于让你从两种视角写出同一个公式：交叉熵视角与最大似然视角。
- 困惑度 = 平均交叉熵的指数：nats 用 `e^x`，bits 用 `2^x`。
- ⚠️ 接口不一致：本文件其他函数的 `base` 都是数值（`2`、`math.e`），唯独 `perplexity` 用字符串 `"e"`。如果顺手写 `perplexity(ce, base=math.e)`，`math.e == "e"` 为 False，函数会**静默**返回 `2 ** ce`（例如 `perplexity(1.0, base=math.e)` 返回 2.0 而不是 2.718）。更一致的写法是 `def perplexity(avg_ce, base=math.e): return base ** avg_ce`。

### 3.6 Label smoothing 演示

```python
    for eps in epsilons:
        soft_target = [eps / num_classes] * num_classes
        soft_target[true_class] = (1 - eps) + eps / num_classes

        ce = cross_entropy(soft_target, probs, base=math.e)
        target_entropy = entropy(soft_target, base=math.e)
        label = "hard" if eps == 0.0 else f"eps={eps}"
```

- 构造软标签：先把每个类别都设为 `ε/K`，再把真实类别改为 `(1-ε) + ε/K`，与讲义公式 `(1-ε)·hard + ε/K` 等价，总和仍为 1。
- 用 `base=math.e`（nats）与 PyTorch 的约定一致。
- 观察输出：ε 从 0 增到 0.2，目标熵从 0 增到 0.5875，CE 从 0.2455 增到 0.6105。注意 CE 变大**不代表模型变差**——模型（同一组 logits）没变，变的是目标；而且 CE 的下界变成了 `H(target)`，不再能降到 0。
- 可以验证分解式：ε=0.1 时 `0.9 × CE(hard) + 0.1 × CE(uniform)` ≈ 0.4280，与输出一致。

### 3.7 互信息特征选择演示

```python
    target = [random.choice([0, 1]) for _ in range(n)]

    features = {}
    features["strong_signal"] = [t ^ (1 if random.random() < 0.1 else 0) for t in target]
    features["weak_signal"] = [t ^ (1 if random.random() < 0.35 else 0) for t in target]
    features["noise"] = [random.choice([0, 1]) for _ in range(n)]
    features["constant"] = [0] * n
    # ...
    for name, feat in features.items():
        joint = [[0, 0], [0, 0]]
        for f, t in zip(feat, target):
            joint[f][t] += 1
        joint_p = [[c / n for c in row] for row in joint]
        mi = mutual_information(joint_p, base=2)
```

- 合成数据：`t ^ 1` 是按位异或，相当于把 0/1 翻转。`strong_signal` 以 10% 概率翻转目标，`weak_signal` 以 35% 概率翻转。
- 理论值（目标平衡时）：`I = 1 - H_b(翻转率)`，强信号 `1 - H(0.1) ≈ 0.531`，弱信号 `1 - H(0.35) ≈ 0.066`。实测 0.5860 与 0.0693，差异来自 200 个样本的随机性（以及目标并非严格 50/50，实际为 87/113）。
- `joint[f][t] += 1`：直接用特征值和目标值（都是 0/1）作为下标，构造 2×2 计数表，再除以 n 得到经验联合概率。这是"plug-in 估计"。
- `noise` 的 MI 为 0.0110 而非 0：**有限样本下 plug-in MI 估计有正偏差**，因为经验联合分布几乎不可能恰好等于边缘分布之积。`constant` 的 MI 恰好为 0：它的边缘分布是确定的，熵为 0，不可能和任何东西共享信息。
- `"#" * int(mi * 200)` 画了一个简易横向条形图。

### 3.8 主程序中的困惑度实验

```python
    random.seed(123)
    vocab_size = 50
    sequence_length = 100
    true_tokens = [random.randint(0, vocab_size - 1) for _ in range(sequence_length)]
    token_logits = [[random.gauss(0, 1) for _ in range(vocab_size)] for _ in range(sequence_length)]
```

- 用随机 logits 模拟一个"什么都没学会的模型"。结果 `Perplexity: 81.23` 比均匀猜测的 50 还高。
- 原因：`CE = logsumexp(z) - z_true`，对标准正态 logits，`E[logsumexp] ≈ log 50 + 0.5`，而 `E[z_true] = 0`，所以期望 PPL ≈ `50 × e^{0.5} ≈ 82.4`。随机 logits 会"随机地自信"，比一视同仁的均匀分布更差。
- ⚠️ 打印的最后一句"The model is better than random if perplexity < vocab size"是判断准则，但 demo 本身恰好是一个**不满足**该准则的例子，代码没有点明，阅读时要注意。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 所有函数带 `base` 参数、默认 bits | 与信息论传统一致，数值直观（公平硬币 = 1 bit） | 深度学习框架默认 nats；混用时要显式换算 |
| `0·log0 = 0` 用 `if p > 0` 实现 | 避免 `0 * inf = nan` | NumPy 中用掩码或 `scipy.special.xlogy` |
| `KL = CE - H` | 代码最短、直接体现恒等式 | 直接按 `Σ p·log(p/q)` 计算更稳；`scipy.special.rel_entr` |
| softmax 减最大值 | 防止 `exp` 上溢 | 生产中还要做 log-softmax，避免 `log(0)` |
| `cross_entropy_loss` 先 softmax 再 log | 与讲义公式一一对应，便于理解 | 极端 logits 下会 `ValueError`；框架用 `logsumexp - z_true` |
| 互信息用 plug-in 频率估计 | 简单直观 | 有限样本正偏差；连续变量需分箱或 KNN 估计（如 `mutual_info_classif`） |
| 合成数据 + 固定种子 | 结果可复现，已知"真实答案" | 真实数据要做置换检验确认显著性 |
| `perplexity` 用字符串 `"e"` 区分底数 | 写法直观 | 与其他函数的数值 `base` 不一致，容易误用 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def entropy(probs, base=2)`、`def perplexity(avg_cross_entropy, base="e")` | 不传时使用默认值；默认值的类型要与调用习惯一致 |
| `float('inf')` | `return float('inf')` | 正无穷，表示"无限意外" |
| 换底公式 | `-math.log(p) / math.log(base)` | `math.log(x)` 默认是自然对数；也有 `math.log2` |
| `math.e` / `math.log2` | `base=math.e`、`math.log2(math.e)` | 常数 e；以 2 为底的对数 |
| 带过滤的生成器表达式 | `sum(p * information_content(p, base) for p in probs if p > 0)` | `if` 写在末尾表示筛选元素 |
| 提前 `return` | `cross_entropy` 中遇到 `qi <= 0` 立即返回 `inf` | 不必遍历完 |
| 增强赋值 | `total += ...`、`h_yx -= ...`、`joint[f][t] += 1` | 原地累加 / 累减 |
| 嵌套列表推导 | `[[random.gauss(0, 1) for _ in range(n_classes)] for _ in range(n_samples)]`、`[[c / n for c in row] for row in joint]` | 生成二维列表 |
| 列表乘法 + 下标赋值 | `hard_target = [0.0] * num_classes; hard_target[true_class] = 1.0` | 先建全 0 列表再改一个位置 |
| 按位异或 `^` | `t ^ (1 if random.random() < 0.1 else 0)` | 对 0/1 来说，`^ 1` 就是翻转 |
| 条件表达式 | `"hard" if eps == 0.0 else f"eps={eps}"` | 一行 if-else |
| 字典 + `.items()` | `for name, feat in features.items()` | 遍历键值对；Python 3.7+ 保持插入顺序 |
| `sort(key=..., reverse=True)` | `mi_scores.sort(key=lambda x: x[1], reverse=True)` | 原地按元组第二个元素降序排序 |
| `random` 模块 | `random.seed(42)`、`random.choice([0, 1])`、`random.randint(0, n-1)`、`random.gauss(0, 1)`、`random.random()` | 设种子；随机选择；闭区间随机整数；正态分布；[0,1) 均匀分布 |
| `str.join` + 生成器中的 f-string | `', '.join(f'{p:.4f}' for p in probs)` | 把格式化后的数字用逗号拼接 |
| f-string 格式符 | `{name:20s}`、`{p:<8.4f}`、`{label:>8s}`、`{abs(ce_avg - nll_avg):.2e}` | 宽度与对齐（`<` 左、`>` 右）；`.2e` 科学计数法 |
| 相邻字符串自动拼接 | `print(f"  {label:>8s}  target=..." f"H(target)=...")` | 括号内相邻的字符串字面量会被自动连接，便于折行 |
| 字符串乘法 | `"#" * int(mi * 200)`、`"=" * 60` | 画条形图、分隔线 |
| `if __name__ == "__main__":` | 文件末尾的大段演示 | 直接运行才执行；被 `import` 时只得到函数 |

---

## 6. 运行结果解读

实际运行（`timeout 60 python3 information_theory.py`，约 0.03 秒），关键输出：

```text
INFORMATION CONTENT (SURPRISE)
  Fair coin heads       p=0.5000    surprise=1.0000 bits
  Rolling a 6           p=0.1667    surprise=2.5850 bits
  1-in-1000 event       p=0.0010    surprise=9.9658 bits      ← log2(1000)
  Certain event         p=1.0000    surprise=0.0000 bits

ENTROPY
  Fair coin                  H = 1.0000 bits
  Biased coin (99/1)         H = 0.0808 bits                   ← 几乎没有不确定性
  Fair die (6 sides)         H = 2.5850 bits                   ← log2(6)，6 面骰子的最大熵
  Loaded die                 H = 2.1610 bits                   ← 不均匀 → 熵变小

CROSS-ENTROPY AND KL DIVERGENCE
  H(true):              1.1568 bits
  H(true, good):        1.1896 bits    KL(true || good): 0.0328 bits
  H(true, bad):         3.0219 bits    KL(true || bad):  1.8651 bits
  Good: 1.1568 + 0.0328 = 1.1896  (CE = 1.1896)               ← 恒等式成立

KL DIVERGENCE IS NOT SYMMETRIC
  KL(P || Q) = 0.5310 bits
  KL(Q || P) = 0.7370 bits

CROSS-ENTROPY LOSS FOR CLASSIFICATION
  Softmax:      [0.6590, 0.2424, 0.0986]
  CE loss:      0.4170 nats
  Perplexity:   1.52                                           ← e^0.417
    Class 0: loss=0.4170  Class 1: loss=1.4170  Class 2: loss=2.3170   ← 差值 = logits 差值

CROSS-ENTROPY = NEGATIVE LOG-LIKELIHOOD
  Cross-entropy loss:    1.400910 nats
  Neg log-likelihood:    1.400910 nats
  Difference:            0.00e+00

MUTUAL INFORMATION
  Independent:   MI = 0.0000 bits
  Dependent:     MI = 0.5310 bits
  Partial:       MI = 0.1245 bits

BITS VS NATS
    1 bit = 0.6931 nats      1 nat = 1.4427 bits

PERPLEXITY IN LANGUAGE MODELS
  Avg CE loss:       4.3973 nats
  Perplexity:        81.23           ← 比均匀猜测的 50 还差（见 3.8）

CONDITIONAL AND JOINT ENTROPY
  Dependent:   H(X,Y)=1.4690  H(Y|X)=0.4690  I(X;Y)=0.5310  H(X)=1.0000
  Independent: H(X,Y)=2.0000  H(Y|X)=1.0000  I(X;Y)=0.0000

LABEL SMOOTHING AND CROSS-ENTROPY
      hard  H(target)=0.0000  CE=0.2455
  eps=0.05  H(target)=0.2011  CE=0.3367
   eps=0.1  H(target)=0.3488  CE=0.4280
   eps=0.2  H(target)=0.5875  CE=0.6105

FEATURE SELECTION VIA MUTUAL INFORMATION
  Target balance: 87/113
       strong_signal  MI = 0.5860 bits
         weak_signal  MI = 0.0693 bits
               noise  MI = 0.0110 bits      ← 有限样本正偏差，不是真实依赖
            constant  MI = 0.0000 bits
```

解读要点：

- **熵的几个参照值**：公平硬币 1 bit、6 面骰子 `log₂6`、偏向硬币 0.08 bit——熵越大越"难猜"。
- **好模型 vs 坏模型**：好模型只比真实分布多花 0.0328 bit，坏模型多花 1.8651 bit——这就是"训练时 loss 下降"在信息论里的含义。
- **独立 vs 依赖**：独立时 `H(X,Y) = H(X) + H(Y) = 2`、`H(Y|X) = H(Y) = 1`；依赖时联合熵"少了" 0.5310 bit，恰好是互信息。
- **Label smoothing**：同一组预测下，ε 越大 CE 越大，但这反映的是目标变"软"了，而不是模型变差。

---

## 7. 动手改一改

1. **（入门）** 讲义练习 1：计算 26 个字母均匀分布的熵（`log₂26 ≈ 4.70` bits），再找一份英文字母频率表计算真实熵，解释为什么真实熵更低。
2. **（入门）** 讲义练习 2：对 logits `[5.0, 2.0, 0.5]`、真实类别 1 手算交叉熵（约 3.0591 nats），再用 `cross_entropy_loss` 验证；思考"什么样的 logits 能让 loss 恰好为 0"（答：只有在 logits 差距趋于无穷时才能无限逼近 0）。
3. **（进阶）** 把 `cross_entropy_loss` 改写成 `logsumexp(z) - z[true_class]` 的形式，确认 `cross_entropy_loss(1, [1000.0, 0.0])` 返回 1000 而不是抛出 `ValueError`。
4. **（进阶）** 修改 `perplexity` 为 `base ** avg_ce` 的数值底数接口，并写一个函数 `sequence_perplexity(pairs)` 完成讲义练习 4。
5. **（进阶）** 用 `mi_from_entropies = H(X) + H(Y) - H(X,Y)` 重新实现互信息，与 `mutual_information` 对照；再把 `n` 从 200 改成 20000，观察 `noise` 特征的 MI 如何趋近 0。
6. **（挑战）** 构造一个 XOR 场景：`target = a ^ b`，`a、b` 独立随机。分别计算 `I(a; target)`、`I(b; target)` 和 `I((a,b); target)`（把 `(a,b)` 编码成 0–3 的单变量），体会"单变量互信息看不到特征交互"。

---

## 8. 常见坑

- **bits 和 nats 混用**：`entropy` 默认 `base=2`，PyTorch 默认自然对数；比较数值前先统一单位（1 nat = 1.4427 bits）。
- **先 softmax 再 log**：极端 logits 下概率下溢为 0，`math.log(0)` 抛 `ValueError`；生产代码一律用 log-softmax / logsumexp。
- **`perplexity(ce, base=math.e)` 静默出错**：该函数只认字符串 `"e"`，传数值 e 会落入 `2 ** ce` 分支。
- **把 KL 当距离**：它不对称、不满足三角不等式；参数顺序写反，含义完全不同。
- **把有限样本的 MI 当真**：纯噪声特征也会得到正的 MI（本例 0.011 bits），需要和置换基线对比。
- **忘记 `0·log0 = 0` 约定**：直接对含 0 的分布求和会得到 `nan`。
