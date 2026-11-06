# 代码讲解 · self_attention.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 02 节 Self-Attention 从头开始 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python self_attention.py`（无命令行参数） ｜ **依赖**：`numpy`（不需要 PyTorch、不需要 GPU）

---

## 1. 这份代码在考察什么

这是整个 Transformer 阶段最核心的一段代码：用不到 150 行 NumPy，把 `softmax(QKᵀ/√dk)V` 这一行公式拆成能看见、能打印的每一步。

1. **Q / K / V 投影**：同一个输入 `X` 乘三个不同的权重矩阵，得到"提问""标签""内容"三种表示。
2. **缩放点积 attention**：打分 → 缩放 → softmax → 对 value 加权求和，每一步对应一行代码。
3. **数值稳定的 softmax**：减去最大值，防止 `exp` 溢出。
4. **多头 attention 的最朴素版本**：多个独立的单头 attention 并排运行，拼接后乘 `Wo`。
5. **可视化**：把 6×6 权重矩阵打印成数字表和 ASCII 热力图，直观感受"每个 token 在看谁"。

> 一句话：**先在 NumPy 里把每个矩阵的形状都打印出来、对上号，以后读 PyTorch / HuggingFace 的 attention 源码时，你就知道每一行在做什么。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `softmax(x)` | 函数 | 沿最后一维做数值稳定的 softmax | 分数 → 概率分布 |
| `scaled_dot_product_attention(Q, K, V)` | 函数 | 计算 `softmax(QKᵀ/√dk)V`，返回输出和权重 | attention 的一行公式 |
| `SelfAttention` | 类 | 持有 `Wq/Wk/Wv`，`forward(X)` 做投影并调用上面的函数 | 单头 self-attention |
| `MultiHeadSelfAttention` | 类 | 持有 h 个 `SelfAttention` + 输出投影 `Wo` | 多头 attention（列表实现） |
| `print_attention_matrix` | 函数 | 打印带 token 表头的权重表 | 可视化 |
| `ascii_heatmap` | 函数 | 把权重映射成 `" ░▒▓█"` 五级字符 | 可视化 |
| `if __name__ == "__main__":` | 演示入口 | 单头 → 多头 → softmax 演示 | — |

数据流：`X (6,16)` →（`SelfAttention.forward`）→ `Q, K, V (6,8)` →（`scaled_dot_product_attention`）→ `scores (6,6)` → `weights (6,6)` → `output (6,8)`；多头时两个头各输出 `(6,8)`，拼接成 `(6,16)`，再乘 `Wo (16,16)` 得到 `(6,16)`。

---

## 3. 逐段精讲

### 3.1 `softmax`：减最大值的数值稳定写法

```python
def softmax(x):
    shifted = x - np.max(x, axis=-1, keepdims=True)
    exp_x = np.exp(shifted)
    return exp_x / np.sum(exp_x, axis=-1, keepdims=True)
```

- **数学**：`softmax(x)_i = e^{x_i} / Σ_j e^{x_j}`，把任意实数向量变成非负、和为 1 的概率分布。
- **为什么减最大值**：`softmax(x - c) = softmax(x)`（分子分母同乘 `e^{-c}`）。取 `c = max(x)` 后，最大的指数项是 `e⁰ = 1`，其余在 (0, 1]，**不会上溢**；分母至少为 1，**不会除以 0**。
- **`axis=-1`**：沿最后一维（每一行）做 softmax。对 `(n, n)` 的分数矩阵来说，就是"每个 query 在所有 key 上的分布"。
- **`keepdims=True`**：保持被归约的那一维（长度变成 1），形状从 `(6,)` 变成 `(6, 1)`，这样 `(6,6) - (6,1)` 能正确**广播**到每一行。如果忘了 `keepdims`，`(6,6) - (6,)` 会按**列**广播，结果悄悄出错。
- 同一个函数对 1 维输入（演示里的 `logits`）也成立，因为 `axis=-1` 对 1 维数组就是唯一的那一维。

### 3.2 `scaled_dot_product_attention`：一行公式拆成四行

```python
def scaled_dot_product_attention(Q, K, V):
    dk = Q.shape[-1]
    scores = Q @ K.T / np.sqrt(dk)
    weights = softmax(scores)
    output = weights @ V
    return output, weights
```

| 行 | 形状（主程序） | 含义 |
|----|---------------|------|
| `dk = Q.shape[-1]` | 8 | 从张量本身读取维度，不依赖外部参数 |
| `Q @ K.T` | `(6,8)@(8,6) = (6,6)` | 第 (i, j) 项 = 第 i 个 query 与第 j 个 key 的点积 |
| `/ np.sqrt(dk)` | `(6,6)` | 缩放，让分数方差回到约 1 |
| `softmax(scores)` | `(6,6)` | 每行变成概率分布 |
| `weights @ V` | `(6,6)@(6,8) = (6,8)` | 每个输出是所有 value 的加权平均 |

- **为什么除以 `√dk`**：若 q、k 各分量独立、方差 1，点积的方差就是 dk。dk = 64 时标准差为 8，分数动辄 ±十几，softmax 会接近 one-hot，梯度几乎为 0。除以 √dk 把方差拉回 1。（实验验证见测验 Q1。）
- **为什么同时返回 `weights`**：真实框架为了省显存通常不返回它，这里返回是为了可视化和教学。
- ⚠️ `K.T` 只对 **2 维**矩阵正确。如果 Q、K 带 batch 维 `(B, n, dk)`，`.T` 会把所有轴倒序变成 `(dk, n, B)`，结果错误；批量版要写成 `K.swapaxes(-1, -2)` 或 `np.einsum("bid,bjd->bij", Q, K)`。
- ⚠️ 没有 `mask` 参数，所以这里是**双向** attention（每个 token 能看到所有 token，包括"未来"的）。讲义练习 1 让你自己加因果 mask，参考实现见测验 Q9。

### 3.3 `SelfAttention`：三个投影矩阵

```python
class SelfAttention:
    def __init__(self, d_model, dk, dv, seed=42):
        rng = np.random.default_rng(seed)
        scale_qk = np.sqrt(2.0 / (d_model + dk))
        self.Wq = rng.normal(0, scale_qk, (d_model, dk))
        self.Wk = rng.normal(0, scale_qk, (d_model, dk))
        scale_v = np.sqrt(2.0 / (d_model + dv))
        self.Wv = rng.normal(0, scale_v, (d_model, dv))
        self.dk = dk

    def forward(self, X):
        Q = X @ self.Wq
        K = X @ self.Wk
        V = X @ self.Wv
        return scaled_dot_product_attention(Q, K, V)
```

- **"self"-attention 的含义**：Q、K、V 都来自同一个 `X`。如果 K、V 来自另一个序列（如 encoder 输出），就是 cross-attention（第 05 节）。
- **初始化 `std = sqrt(2 / (fan_in + fan_out))`**：这是 Xavier/Glorot 正态初始化，目标是让前向输出和反向梯度的方差在层与层之间大致不变。这里 `d_model = 16, dk = 8`，`std = sqrt(2/24) ≈ 0.289`。
- **`np.random.default_rng(seed)`**：NumPy 推荐的新式随机数生成器，每个实例有独立状态，用同一个 `seed` 就能复现同样的权重。注意 `Wq` 和 `Wk` 是从同一个 rng **依次**抽取的，所以二者不同；但只要 `seed`、形状、抽取顺序都一样，两个 `SelfAttention` 实例的权重就会**完全相同**（3.4 节会遇到这个现象）。
- **为什么 Q/K/V 用不同矩阵**：Q 决定"我想找什么"、K 决定"我以什么被找到"、V 决定"被找到时交出什么"。如果 `Wq = Wk`，分数矩阵会变成对称的，无法表达"i 关注 j 但 j 不关注 i"这样的方向性关系。
- ⚠️ `self.dk` 被存下来，但 `forward` 并没有用它（`scaled_dot_product_attention` 自己从 `Q.shape[-1]` 读取），属于冗余字段。
- ⚠️ 没有偏置项（bias）。原始 Transformer 的线性层带 bias，很多现代 LLM（如 LLaMA 系列）的 attention 投影则去掉了 bias，这里的简化恰好与后者一致。

### 3.4 `MultiHeadSelfAttention`：最朴素的多头实现

```python
class MultiHeadSelfAttention:
    def __init__(self, d_model, n_heads, seed=42):
        assert d_model % n_heads == 0
        self.n_heads = n_heads
        self.dk = d_model // n_heads
        self.dv = d_model // n_heads
        self.heads = [
            SelfAttention(d_model, self.dk, self.dv, seed=seed + i)
            for i in range(n_heads)
        ]
        rng = np.random.default_rng(seed + n_heads)
        scale = np.sqrt(2.0 / (d_model + d_model))
        self.Wo = rng.normal(0, scale, (n_heads * self.dv, d_model))

    def forward(self, X):
        head_outputs = []
        all_weights = []
        for head in self.heads:
            out, w = head.forward(X)
            head_outputs.append(out)
            all_weights.append(w)
        concatenated = np.concatenate(head_outputs, axis=-1)
        output = concatenated @ self.Wo
        return output, all_weights
```

- **`assert d_model % n_heads == 0`**：每个头分到 `d_model / h` 维，必须整除。断言失败会直接抛 `AssertionError`，这是"快速失败"的防御式写法。
- **每个头是一个独立的 `SelfAttention`**，各有自己的 `Wq/Wk/Wv`（形状 `(16, 8)`），种子分别是 `42, 43`；`Wo` 用种子 `44`。
- **拼接**：`np.concatenate(..., axis=-1)` 把两个 `(6,8)` 沿最后一维接成 `(6,16)`。
- **输出投影 `Wo (16,16)`**：把各头的结果混合回 `d_model` 维，让不同头的信息能相互组合；没有它，各头输出只是简单并排。
- **参数量**：每头 `3 × 16 × 8 = 384`，两头 768，加 `Wo` 的 256，共 1024 = `4 × d_model²`，与"一个 `d_model` 维的单头 + 输出投影"相同。多头不增加参数，只是把同一维度切成多个子空间。
- **为什么 Head 1 和前面的单头结果一模一样**：主程序单头是 `SelfAttention(16, 8, 8, seed=42)`；多头的第 0 个头是 `SelfAttention(16, 16//2=8, 8, seed=42+0)`——维度和种子都一样，权重逐元素相同，输入又是同一个 `X`。这不是 bug，但容易误导读者以为"多头的第一个头天然等于单头"。换一个 `seed` 就能看到不同结果。
- ⚠️ **刻意的简化**：用 Python `for` 循环逐头计算，每个头做三次独立的小矩阵乘。真实实现会用一个 `(d_model, d_model)` 的大矩阵一次算出所有头的 Q，再 `reshape` 成 `(n, h, dk)` 并转置成 `(h, n, dk)`，所有头在一次批量 matmul 里并行完成——这是第 03 节的内容。

### 3.5 两个可视化函数

```python
def print_attention_matrix(weights, tokens):
    print(f"\n{'':>6}", end="")
    for token in tokens:
        print(f"{token:>6}", end="")
    print()
    for i, token in enumerate(tokens):
        print(f"{token:>6}", end="")
        for j in range(len(tokens)):
            print(f"{weights[i][j]:6.3f}", end="")
        print()
```

- `print(..., end="")`：不换行，用于在同一行连续输出多个单元格；每行末尾的 `print()` 负责换行。
- `f"{'':>6}"`：输出 6 个空格，给左上角的空单元格占位，让表头与数据列对齐。
- `f"{weights[i][j]:6.3f}"`：宽度 6、保留 3 位小数。

```python
def ascii_heatmap(weights, tokens, chars=" ░▒▓█"):
    # ...（表头部分同上）
    w_max = weights.max()
    for i in range(len(tokens)):
        print(f"{tokens[i]:>6}", end="")
        for j in range(len(tokens)):
            level = int(weights[i][j] * (len(chars) - 1) / w_max)
            level = min(level, len(chars) - 1)
            print(f"{'  ' + chars[level] + '   '}", end="")
        print()
```

- **映射规则**：`level = int(w × 4 / w_max)`，把 `[0, w_max]` 线性映射到 `0..4`，再查表取字符。全矩阵最大的那个权重得到 `█`。
- **`min(level, len(chars) - 1)`**：防御浮点误差让 `level` 恰好超过 4 时越界。
- 注意是用**整个矩阵**的最大值归一，而不是每行各自归一；所以热力图比较的是"全局强弱"。
- `w_max` 在循环外先算好，避免每个单元格都重新扫描一遍矩阵（讲义版本里写在循环内部，代码版做了这个小优化）。
- `f"{'  ' + chars[level] + '   '}"` 是把字符串拼接好再放进 f-string，等价于直接 `print('  ' + chars[level] + '   ', end="")`，每格宽 6，与表头对齐。

### 3.6 主程序：三段演示

```python
    rng = np.random.default_rng(42)
    X = rng.normal(0, 1, (n_tokens, d_model))
```

- ⚠️ **最重要的简化**：`X` 是随机数，不是真实的词向量，`Wq/Wk/Wv` 也没有经过训练。所以打印出的注意力模式**没有任何语言学含义**，"the" 关注自己多一点只是随机性的结果。真实模型的 attention 模式是训练出来的。
- 最后的 softmax 演示用 `[100, 200, 300]` 说明"数值稳定、没有溢出"。⚠️ 严格来说，在 float64 下朴素 softmax 对这组数也不会溢出（`e³⁰⁰ ≈ 1.9e130`，float64 上限约 `1.8e308`，即 `x ≈ 709`）；用 float32 或 `[1000, 2000, 3000]` 才能看到朴素版本输出 `nan`（详见测验 Q10）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 NumPy、2 维矩阵 | 每一步的形状都清楚可见 | 没有 batch 维、没有自动求导；生产用 PyTorch 的 `F.scaled_dot_product_attention` |
| 返回 `weights` | 便于打印和可视化 | 需要存 n×n 矩阵；Flash Attention 等实现默认不返回 |
| 没有 mask | 先讲清双向 attention 的基本形态 | decoder 必须加因果 mask，batch 训练必须加 padding mask |
| 多头用 Python 列表逐头算 | 直观对应"多个独立的 attention" | 慢；真实实现用一个大矩阵 + reshape，所有头一次 matmul |
| Xavier 正态初始化 | 保持前后向方差稳定 | 现代 LLM 常用更小的 std（如 0.02）或针对深度缩放的初始化 |
| 投影没有 bias | 代码更短 | 原始 Transformer 有 bias；不少现代 LLM 也去掉了 |
| 随机 `X` 而非真实 embedding | 不依赖分词器与预训练权重 | attention 模式没有语义含义 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import ... as` | `import numpy as np` | 给模块起别名，`np` 是社区约定 |
| `class` 与 `__init__` | `class SelfAttention: def __init__(self, d_model, dk, dv, seed=42)` | 定义类与构造函数；默认参数 `seed=42` |
| 实例属性 | `self.Wq = ...`、`self.heads = [...]` | 存在对象上的数据，其他方法通过 `self.` 访问 |
| 返回元组与解包 | `return output, weights`；`out, w = head.forward(X)` | 一次返回多个值，调用方一次拆开 |
| 列表推导式 | `[SelfAttention(...) for i in range(n_heads)]` | 一行构造对象列表 |
| `assert` | `assert d_model % n_heads == 0` | 条件不成立时抛 `AssertionError`，用于检查前置条件 |
| 整除与取模 | `d_model // n_heads`、`d_model % n_heads` | `//` 向下取整除，`%` 取余 |
| `enumerate` | `for i, token in enumerate(tokens)`、`for h, hw in enumerate(head_weights)` | 同时拿到下标和元素 |
| `print(..., end="")` | `print(f"{token:>6}", end="")` | 不换行，用于逐格打印表格 |
| f-string 格式符 | `f"{token:>6}"`、`f"{weights[i][j]:6.3f}"`、`f"{probs.sum():.4f}"` | `>6` 右对齐宽 6；`6.3f` 宽 6 保留 3 位小数 |
| f-string 内嵌表达式 | `f"{' '.join(sentence)}"`、`f"{'':>6}"` | 花括号里可以写任意表达式 |
| 字符串乘法 | `"=" * 60` | 重复字符串，常用于画分隔线 |
| 字符串索引 | `chars[level]` | 字符串也能按下标取字符 |
| NumPy `@` | `X @ self.Wq`、`Q @ K.T` | 矩阵乘法运算符 |
| NumPy `.T` / `.shape` | `K.T`、`Q.shape[-1]` | 转置；形状元组，`[-1]` 取最后一维 |
| NumPy 归约 + `keepdims` | `np.max(x, axis=-1, keepdims=True)` | 沿某轴求最大值并保留该轴，便于广播 |
| NumPy 广播 | `x - np.max(...)`、`exp_x / np.sum(...)` | 形状 `(6,6)` 与 `(6,1)` 自动对齐运算 |
| `np.random.default_rng` | `rng = np.random.default_rng(seed)`；`rng.normal(0, std, shape)` | 新式随机数生成器，可复现 |
| `np.concatenate` | `np.concatenate(head_outputs, axis=-1)` | 沿指定轴拼接数组列表 |
| `.round()` | `probs.round(4)` | 数组逐元素四舍五入 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行演示 |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 self_attention.py`（NumPy 2.5.3）的关键输出：

```text
Tokens: 6, d_model: 16, dk: 8, dv: 8
Input shape: (6, 16)

Output shape: (6, 8)
```

- 输入 6 个 token、每个 16 维；单头输出 `(6, 8)`，维度是 `dv` 而不是 `d_model`。

```text
         The   cat   sat    on   the   mat
   The 0.176 0.299 0.127 0.120 0.142 0.136
   cat 0.130 0.165 0.120 0.086 0.271 0.227
   sat 0.176 0.242 0.236 0.102 0.132 0.112
    on 0.106 0.046 0.272 0.193 0.126 0.258
   the 0.112 0.204 0.112 0.098 0.369 0.105
   mat 0.180 0.186 0.102 0.296 0.089 0.148
```

- **每一行和为 1**（例如第一行 0.176 + 0.299 + 0.127 + 0.120 + 0.142 + 0.136 = 1.000）。
- **矩阵不对称**："The" 对 "cat" 是 0.299，"cat" 对 "The" 只有 0.130——因为 `Wq ≠ Wk`。
- **分布比较平坦**（最大 0.369，最小 0.046）：随机初始化 + √dk 缩放后，分数方差不大，softmax 没有饱和。这正是训练初期希望看到的状态。
- 再次强调：权重来自随机 `X` 和未训练的 `W`，没有语言学含义。

```text
         The   cat   sat    on   the   mat
   The  ░     ▓     ░     ░     ░     ░
   ...
   the  ░     ▒     ░     ░     █     ░
```

- 全局最大值是 "the"→"the" 的 0.369，映射为 `█`；"The"→"cat" 为 `int(0.299×4/0.369) = 3`，即 `▓`；0.046 映射为 0，即空格。

```text
Heads: 2
Output shape: (6, 16)

Head 1 attention weights:
   The 0.176 0.299 0.127 0.120 0.142 0.136
   ...
Head 2 attention weights:
   The 0.152 0.224 0.118 0.087 0.285 0.133
   ...
   mat 0.386 0.050 0.228 0.079 0.021 0.236
```

- 多头输出回到 `(6, 16)`：两个头各 `(6, 8)`，拼接后乘 `Wo (16, 16)`。
- **Head 1 与单头矩阵逐位相同**：维度和种子都一样（见 3.4 节）。
- **Head 2 的模式明显不同**：例如 "mat" 最关注 "The"（0.386），而 Head 1 中 "mat" 最关注 "on"（0.296）。不同的投影 = 不同的"关注视角"，这就是多头的意义。

```text
Logits:  [2.  1.  0.1]
Softmax: [0.659  0.2424 0.0986]
Sum:     1.0000

Large logits:  [100. 200. 300.]
Softmax:       [0. 0. 1.]
Sum:           1.0000
```

- `[2, 1, 0.1]` → `[0.659, 0.242, 0.099]`：经典的 softmax 示例。
- `[100, 200, 300]` → `[0, 0, 1]`：差值达到 100，softmax 完全变成 one-hot。这也直观说明了**不缩放时**大分数会让 softmax 饱和——此时梯度几乎为 0。

---

## 7. 动手改一改

1. **加因果 mask**（讲义练习 1）：给 `scaled_dot_product_attention` 加 `mask=None` 参数，用 `np.tril` 构造下三角 mask，验证权重矩阵上三角全为 0、每行仍然和为 1。
2. **验证缩放的作用**：去掉 `/ np.sqrt(dk)`，把 `dk` 改成 256，打印权重矩阵的每行最大值，观察分布是否变得更尖锐。
3. **验证置换等变**：把 `X` 的行打乱成 `X[perm]`，检查 `np.allclose(out[perm], out_perm)` 是否为 `True`。再思考：为什么这说明需要位置编码？
4. **修正多头的种子**：用 `MultiHeadSelfAttention(d_model, n_heads, seed=100)`，确认 Head 1 不再与单头相同。
5. **向量化多头**（讲义练习 2 进阶）：用一个 `(16, 16)` 的 `Wq` 一次算出所有头的 Q，再 `reshape(n, h, dk).transpose(1, 0, 2)`，用批量 matmul 一次算完所有头，与列表版结果对比。
6. **两句话对比**（讲义练习 3）：用两个不同的随机 `X`（相同长度）通过同一个 `SelfAttention` 实例，比较权重矩阵——权重 `W` 不变，但模式随输入而变，说明 attention 是"由内容决定的动态权重"。

---

## 8. 常见坑

- **忘记 `keepdims=True`**：`(n,n) - (n,)` 会按列广播，softmax 结果悄悄错误，不报错。
- **在 softmax 的错误维度上归一化**：必须沿 key 维度（`axis=-1`），保证"每个 query 的权重和为 1"。
- **对 3 维张量使用 `.T`**：会倒转所有轴；批量版要用 `swapaxes(-1, -2)`。
- **以为随机权重下的 attention 模式有含义**：未训练的模型，热力图只是随机结构。
- **mask 用"乘 0"而不是"加 -inf"**：softmax 之后再置零会破坏归一化；正确做法是在 softmax 之前把分数设为 `-inf`。
- **整行都被 mask**：全 `-inf` 的行在减最大值时得到 `nan`，要保证每行至少有一个可见位置或做特殊处理。
