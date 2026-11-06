# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到进阶 · 第 08 节 文本的 CNNs 和 RNNs ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅 Python 标准库（`math`）；讲义中的 PyTorch 版 `TextCNN` / `LSTMClassifier` 不在本文件里

---

## 1. 这份代码在考察什么

讲义的"Build It"部分给了 PyTorch 版 TextCNN 和 LSTM 分类器，而这份 `main.py` 只有 50 多行纯 Python，刻意把两个最核心的直觉拆出来、算给你看：

1. **梯度消失是"连乘"造成的**：普通 RNN 的梯度每往回走一步就要乘一次循环权重，`0.9` 连乘 100 次只剩 `2.66e-05`。
2. **1D 卷积 = 可学习的 n-gram 检测器**：宽度为 k 的 filter 在词向量序列上滑动，每个窗口算一次"逐元素相乘再求和 + bias"，再过 ReLU。
3. **全局最大池化 = 定长、位置无关的特征**：不管句子多长，每个 filter 只留下最强的一次激活。
4. **形状与边界**：输出长度 `L - k + 1`、句子比 filter 短时怎么办——这些是写 PyTorch 版本时最常踩的坑。

> 一句话：**不用任何框架，亲手把"卷积 + 池化"和"梯度连乘"各算一遍**，再去读 `nn.Conv1d`、`nn.LSTM` 的代码时就知道每个张量在干什么。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `vanishing_gradient_sim(seq_len, recurrent_weight)` | 函数 | 返回 `w ** seq_len` | 普通 RNN 的梯度消失（标量直觉模型） |
| `conv1d_over_embeddings(embeddings, filter_matrix, bias)` | 函数 | 在词向量序列上做 valid 1D 卷积 + ReLU | TextCNN 的卷积层 |
| `max_pool(values)` | 函数 | 取最大值，空列表返回 0.0 | 全局最大池化（global max-pool over time） |
| `main()` | 函数 | 打印两段演示：梯度衰减表、TextCNN 前向 | 演示入口 |

数据流：`main()` 先用 4 个长度调用 `vanishing_gradient_sim` 打印衰减；再构造 5×3 的词向量矩阵和两个 filter（宽 2、宽 3），分别 `conv1d_over_embeddings → max_pool`，得到一个 2 维的"句子特征向量"。

---

## 3. 逐段精讲

### 3.1 梯度消失模拟：一行 `math.pow`

```python
def vanishing_gradient_sim(seq_len, recurrent_weight=0.9):
    return math.pow(recurrent_weight, seq_len)
```

- 对应讲义 Step 3：普通 RNN `h_t = f(W·x_t + U·h_{t-1} + b)` 中，损失对早期隐状态的梯度要经过 `seq_len` 次"乘以 U"。把 U 简化成标量 `w`，衰减系数就是 `wᵀ`。
- `math.pow(x, y)` 与 `x ** y` 结果相同，返回 `float`。
- 为什么默认 `0.9`：一个"看起来很接近 1"的数也会在 100 步后衰减到十万分之三——直观展示指数的威力。
- ⚠️ 刻意的简化：真实的梯度是一串**雅可比矩阵**连乘 `Π diag(f'(·))·Uᵀ`，起决定作用的是矩阵的谱半径，而且 tanh 的导数 ≤ 1 会让衰减更快。标量模型只保留了"连乘"这个本质。
- 这个函数只演示了 **消失**（w < 1）；w > 1 时同一个公式就是 **爆炸**（`1.1¹⁰⁰ ≈ 1.38e4`），可以自己改参数试试。

### 3.2 打印衰减表：f-string 格式符

```python
    print("=== vanishing gradient sim ===")
    for length in [10, 50, 100, 200]:
        print(f"  len={length:3d}  w=0.9  gradient attenuation = {vanishing_gradient_sim(length):.2e}")
    print("  a plain RNN loses 99.99% of its gradient by step 100.")
```

- `{length:3d}`：整数右对齐、宽度 3，让 `10` 和 `100` 对齐成一列。
- `{...:.2e}`：科学计数法、保留 2 位小数，适合跨越十几个数量级的数（`3.49e-01` 到 `7.06e-10`）。
- 最后一行的 "99.99%"：`1 - 2.66e-5 ≈ 99.997%`，说"丢掉了 99.99% 以上"是准确的。
- ⚠️ 小瑕疵：字符串里把 `w=0.9` 写死了，如果你改了 `recurrent_weight` 却忘了改这段文字，打印会自相矛盾。更稳妥的写法是把 `w` 作为变量一起格式化。

### 3.3 1D 卷积：TextCNN 的核心

```python
def conv1d_over_embeddings(embeddings, filter_matrix, bias=0.0):
    filter_width = len(filter_matrix)
    embed_dim = len(embeddings[0])
    out = []
    for i in range(len(embeddings) - filter_width + 1):
        total = bias
        for k in range(filter_width):
            for d in range(embed_dim):
                total += embeddings[i + k][d] * filter_matrix[k][d]
        out.append(max(total, 0.0))
    return out
```

逐行理解：

- **数据布局**：`embeddings` 是 `[seq_len][embed_dim]`（每行一个词的向量）；`filter_matrix` 是 `[filter_width][embed_dim]`——filter 覆盖 `filter_width` 个连续的词，并且看到每个词的**全部** embedding 维度。这正是讲义说的"宽度 3 的 filter 是可学习的 trigram 检测器"。
- **外层循环** `range(len(embeddings) - filter_width + 1)`：窗口起点 i 从 0 滑到最后一个能放下整个 filter 的位置，输出长度 = `L - k + 1`（不 padding、步长 1，即 "valid" 卷积）。5 个词、宽 2 → 4 个输出；宽 3 → 3 个输出。
- **内两层循环**：窗口内所有 `k × d` 个位置"对应相乘再求和"，再加 `bias`。这在数学上是**互相关**（不翻转核），深度学习里习惯也叫卷积。
- **`max(total, 0.0)`**：就是 ReLU。注意函数名叫 `conv1d`，但它其实把"卷积 + 激活"合在一起了，对应讲义 PyTorch 代码的 `F.relu(conv(x))`。
- **bias 为负数**（演示中是 -0.5 / -0.4）：相当于一个"激活门槛"，只有窗口与 filter 足够匹配时才输出正值——这让 filter 更像一个"检测器"。
- ⚠️ 简化之处：
  1. 每种宽度只有 1 个 filter；真实 TextCNN 每种宽度 64–100 个（讲义：3 种宽度 × 100 = 300 个 n-gram 检测器）；
  2. 三重 Python 循环是 `O((L-k+1)·k·d)` 次标量乘法，真实框架会向量化成一次矩阵乘法（见测验 Q9 的 NumPy 版本）；
  3. `embeddings[0]` 在空输入时会 `IndexError`，没有防御。

**与 PyTorch 的对应**：讲义里 `nn.Conv1d(embed_dim, n_filters, kernel_size=k)` 的权重形状是 `(n_filters, embed_dim, k)`，输入要先 `transpose(1, 2)` 变成 `[batch, embed_dim, seq_len]`——embedding 维是"通道"，沿 seq_len 滑动。本文件的 `filter_matrix[k][d]` 正好是 PyTorch 权重里某一个 filter 的转置 `weight[f, d, k]`。

### 3.4 全局最大池化

```python
def max_pool(values):
    return max(values) if values else 0.0
```

- 每个 filter 的整条激活序列只保留最大值 → **输出长度与句长无关**，这就是 TextCNN 能直接接一个固定大小全连接层的原因。
- **位置不变**：讲义例子——"not good" 出现在评论开头还是中间，触发的是同一个最大值。代价是丢掉了"在哪里、出现几次"的信息。
- `x if cond else y` 是**条件表达式**。空列表（句子比 filter 短）时返回 `0.0`：因为 ReLU 输出本来就 ≥ 0，0.0 等价于"这个 n-gram 完全没出现"，是一个合理的默认值。PyTorch 中遇到同样情况会直接报错，需要把输入 pad 到至少最大 filter 宽度。
- 讲义中 LSTM 分类器同样用 `out.max(dim=1).values` 做时间维最大池化，理由是"最后一个隐状态会被序列末尾的信息主导"。

### 3.5 演示数据：5 个词、3 维向量、两个 filter

```python
    embeddings = [
        [1.0, 0.2, 0.5],
        [0.8, 0.9, 0.1],
        [0.3, 0.4, 0.7],
        [0.6, 0.5, 0.5],
        [0.1, 0.8, 0.2],
    ]
    filter_w2 = [[0.5, 0.0, 0.5], [0.2, 0.3, 0.1]]
    filter_w3 = [[0.3, 0.3, 0.3], [0.2, 0.4, 0.1], [0.5, 0.2, 0.1]]

    act_w2 = conv1d_over_embeddings(embeddings, filter_w2, bias=-0.5)
    act_w3 = conv1d_over_embeddings(embeddings, filter_w3, bias=-0.4)
```

- 手算 `act_w2[0]`（窗口 = 第 0、1 个词）：
  - `[1.0, 0.2, 0.5]·[0.5, 0.0, 0.5] = 0.75`
  - `[0.8, 0.9, 0.1]·[0.2, 0.3, 0.1] = 0.44`
  - `0.75 + 0.44 - 0.5 = 0.69`，ReLU 后仍为 0.69 ✔
- 本例中所有窗口的原始分数都是正的，所以 ReLU 没有"截断"任何值。你可以把 bias 调到 -0.8 看看哪些位置会变成 0（见第 7 节练习）。
- 两个 filter 分别池化后拼成 `[0.69, 0.94]`——这就是一个"2 维句子向量"，真实 TextCNN 会把它送进 dropout + 全连接层做分类。
- `[round(x, 2) for x in act_w2]`：打印前保留两位小数，避免 `0.19999999999999996` 这样的浮点噪声。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python、不依赖 PyTorch | 任何环境都能跑，每次乘加都看得见 | 极慢；生产中用 `nn.Conv1d`（cuDNN 优化）或至少 NumPy 向量化 |
| 用标量 `wᵀ` 模拟梯度消失 | 一行代码讲清"连乘导致指数衰减" | 忽略了雅可比矩阵、激活导数；真实分析看谱半径 |
| 卷积与 ReLU 合并在一个函数里 | 演示更紧凑 | 职责不单一；框架中卷积层与激活层分开，方便替换激活函数 |
| 每种宽度只有 1 个 filter | 输出能一眼看懂 | 表达能力极弱；真实模型每种宽度 64–100 个 filter |
| valid 卷积（不 padding） | 实现最简单 | 句子短于 filter 时无输出；生产中 pad 到最小长度并用 mask |
| 空列表池化返回 0.0 | 与 ReLU 下界一致，避免 `max([])` 报错 | 掩盖了"输入太短"的问题；生产中应显式校验 |
| 不实现 LSTM | 讲义已有 PyTorch 版；本文件只演示动机 | 想深入可自己用 NumPy 写一个单步 LSTM cell |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def vanishing_gradient_sim(seq_len, recurrent_weight=0.9)` | 调用时不传就用默认值 |
| 关键字参数调用 | `conv1d_over_embeddings(embeddings, filter_w2, bias=-0.5)` | 按名字传参，可读性更好 |
| `math.pow` | `math.pow(recurrent_weight, seq_len)` | 幂运算，返回 float，等价于 `**` |
| 嵌套列表（二维数组） | `embeddings[i + k][d]` | 列表的列表，用两次下标访问 |
| `range(n)` | `range(len(embeddings) - filter_width + 1)` | 生成 0…n-1；n ≤ 0 时为空，循环不执行 |
| 内置 `max` | `max(total, 0.0)`、`max(values)` | 两个数取大（实现 ReLU）/ 序列取最大 |
| 条件表达式 | `max(values) if values else 0.0` | 一行 if-else；空列表在布尔上下文中为 False |
| 列表推导式 + `round` | `[round(x, 2) for x in act_w2]` | 逐元素保留 2 位小数 |
| f-string 宽度格式 | `{length:3d}` | 整数占 3 位、右对齐 |
| f-string 科学计数法 | `{...:.2e}` | 如 `2.66e-05` |
| f-string 定点格式 | `{max_pool(act_w2):.2f}` | 保留 2 位小数 |
| 无占位符的 f-string | `f"  5 tokens x 3 embed_dim"` | 合法但多余，普通字符串即可 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，仅标准库）的完整输出：

```text
=== vanishing gradient sim ===
  len= 10  w=0.9  gradient attenuation = 3.49e-01
  len= 50  w=0.9  gradient attenuation = 5.15e-03
  len=100  w=0.9  gradient attenuation = 2.66e-05
  len=200  w=0.9  gradient attenuation = 7.06e-10
  a plain RNN loses 99.99% of its gradient by step 100.

=== TextCNN conceptual pass ===
  5 tokens x 3 embed_dim
  width-2 filter activations: [0.69, 0.2, 0.32, 0.33]
  width-3 filter activations: [0.94, 0.88, 0.62]
  max-pooled features:        [0.69, 0.94]
```

逐行解读：

- `len= 10 … 3.49e-01`：10 步后还剩约 35% 的梯度，短序列问题不大。
- `len= 50 … 5.15e-03`：50 步就只剩 0.5%，这已经是一句普通长句的长度。
- `len=100 … 2.66e-05`：与讲义注释 "0.9 ^ 100 ≈ 2.7e-5" 一致——第 1 步几乎收不到来自第 100 步的学习信号。
- `len=200 … 7.06e-10`：彻底消失。讲义说 LSTM 在 200+ 步上也仍然吃力，是同一类问题的温和版本。
- `width-2 filter activations` 有 4 个值、`width-3` 有 3 个值：验证了输出长度 `L - k + 1`。
- `width-2` 的最大值在位置 0（`0.69`，第 0–1 个词），`width-3` 的最大值也在位置 0（`0.94`）：说明这两个"检测器"都在句首找到了最匹配的 n-gram。
- `max-pooled features: [0.69, 0.94]`：两种宽度各贡献 1 维，拼成定长特征向量。句子变成 50 个词，这里仍然是 2 维。

---

## 7. 动手改一改

1. **观察爆炸**：在 `main()` 的循环里额外打印 `vanishing_gradient_sim(length, 1.1)`，看 200 步时的数值（约 `1.9e8`），并把打印文本中写死的 `w=0.9` 改成变量。
2. **让 ReLU 起作用**：把 `filter_w2` 的 bias 从 `-0.5` 改成 `-0.8`，哪些位置会变成 0？最大池化结果变了吗？
3. **多个 filter**：把每种宽度扩展到 3 个随机 filter（`random.seed(0)`），输出一个 6 维的句子特征向量。
4. **向量化**：用 NumPy 的 `sliding_window_view` + `einsum` 重写卷积，并断言与原函数输出一致（参考测验 Q9）。
5. **加 padding**：实现 `same` 卷积（两侧各补 `(k-1)//2` 个零向量），让输出长度等于输入长度，比较池化结果的变化。
6. **进阶**：用 NumPy 写一个单步 LSTM cell（输入门、遗忘门、输出门、候选值），把遗忘门固定为 0.99，模拟 100 步后 `∂c_100/∂c_1 = 0.99¹⁰⁰ ≈ 0.366`，与普通 RNN 的 `2.66e-05` 对比。

---

## 8. 常见坑

- **输入比 filter 短**：本文件返回空列表、池化得 0.0；PyTorch 的 `nn.Conv1d` 会直接报错。批处理时要保证 pad 后长度 ≥ 最大 filter 宽度。
- **忘记 transpose**：PyTorch 中把 `[B, L, E]` 直接喂给 `nn.Conv1d(E, …)` 会报通道数不匹配，或者（当 L 恰好等于 E 时）静默地沿错误的维度卷积。
- **把 pad 位置也池化进去**：pad 的 embedding 为 0，但加上 bias 后激活不一定为 0；LSTM 在 pad 位置的输出更不是 0。最大池化前要用 mask 屏蔽。
- **以为门控能解决爆炸**：LSTM/GRU 主要缓解梯度消失，梯度爆炸仍需梯度裁剪。
- **把标量模拟当成定量结论**：`0.9¹⁰⁰` 只是直觉，真实网络的衰减速度取决于权重矩阵谱半径和激活函数导数。
