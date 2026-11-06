# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 05 节 完整的 Transformer — Encoder + Decoder ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`typing`）

---

## 1. 这份代码在考察什么

前三节分别实现了 attention、多头和位置编码，这一节把它们装进**可以堆叠的 block**，再组成一个 2 层 encoder + 2 层 decoder 的完整前向过程：

1. **Block 的"脚手架"**：残差连接、归一化、FFN 如何包在 attention 外面，让模型能堆深。
2. **Pre-norm 接线方式**：`x + f(Norm(x))`，2026 年的默认做法。
3. **现代组件**：RMSNorm 代替 LayerNorm，SwiGLU 代替 ReLU-FFN（两者的旧版本也写好了，便于对照）。
4. **Encoder 与 decoder 的区别**：encoder 双向；decoder 有因果 mask 的自注意力 + cross-attention。
5. **一个函数两种用法**：`multi_head_attention(..., kv_source=enc_out)` 让同一段代码同时实现 self-attention 和 cross-attention。

> 一句话：**attention 是主角，但让它能堆 32 层、80 层的，是残差、归一化和 FFN 这些"脚手架"——这份代码把脚手架的每一根钢管都摆在你面前。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Matrix`（含 `copy`） | 类 | 行优先二维矩阵（同第 03 节，多了 `copy`） | 张量 |
| `randn` / `matmul` / `transpose` / `add` | 函数 | 随机初始化、矩阵乘、转置、逐元素相加 | 基础算子；`add` 用于残差 |
| `softmax_rows(A, mask=None)` | 函数 | 带可选布尔 mask 的逐行 softmax | 因果 mask |
| `layer_norm` / `rms_norm` | 函数 | 两种逐行归一化（无可学习参数） | Norm |
| `silu` / `ffn_swiglu` / `ffn_relu` | 函数 | 两种 FFN | FFN |
| `scaled_dot_product_attention(Q, K, V, causal=False)` | 函数 | 单头 attention，可选因果 mask | attention |
| `multi_head_attention(..., causal=False, kv_source=None)` | 函数 | 多头；`kv_source` 不为空时就是 cross-attention | MHA / cross-attn |
| `BlockParams` | 类 | 一个 block 的全部权重（含 cross-attn 权重） | 参数容器 |
| `encoder_block(x, p)` | 函数 | pre-norm：自注意力 + FFN，各带残差 | Encoder block |
| `decoder_block(x, enc_out, p)` | 函数 | pre-norm：因果自注意力 + cross-attn + FFN | Decoder block |
| `main()` | 函数 | 随机 src/tgt → 2 层 encoder → 2 层 decoder → 打印 | 前向演示 |

数据流：`src (6×8)` → encoder block ×2 → `enc_out (6×8)`；`tgt (5×8)` → decoder block ×2（每层都读同一个 `enc_out`）→ `dec_out (5×8)`。

---

## 3. 逐段精讲

### 3.1 基础算子：与第 03 节相同，多了 `copy` 和 `add`

```python
    def copy(self):
        return Matrix(self.rows, self.cols, data=list(self.data))

def add(A, B):
    assert (A.rows, A.cols) == (B.rows, B.cols)
    return Matrix(A.rows, A.cols, data=[a + b for a, b in zip(A.data, B.data)])
```

- `Matrix`、`randn`、`matmul`、`transpose` 与第 03 节几乎一样（讲义："copied to this file for independence"），这里的 `matmul` 去掉了维度断言。
- **`add` 就是残差连接**：`x + sublayer(x)`。先用元组比较 `(rows, cols)` 断言形状一致——残差要求子层输入输出形状完全相同，这也是为什么 attention 和 FFN 的输出都必须回到 `d_model` 维。
- `copy` 用 `list(self.data)` 复制底层列表，得到一个独立的矩阵（本文件 `main()` 没用到，测验中用它做因果性实验）。
- `Matrix.__init__` 里的 `data if data is not None else [...]` 是条件表达式的一行写法。

### 3.2 `softmax_rows`：带 mask 的数值稳定 softmax

```python
def softmax_rows(A, mask=None):
    out = Matrix(A.rows, A.cols)
    for i in range(A.rows):
        row = A.row(i)
        if mask is not None:
            row = [row[j] if not mask[i][j] else float("-inf") for j in range(A.cols)]
        m = max(v for v in row if v != float("-inf"))
        exps = [math.exp(v - m) if v != float("-inf") else 0.0 for v in row]
        s = sum(exps)
        for j, e in enumerate(exps):
            out.set(i, j, e / s if s > 0 else 0.0)
    return out
```

- **mask 约定**：`mask[i][j] == True` 表示"屏蔽"（与第 02 节测验里"True 表示允许"的写法相反，读代码时要注意约定）。
- 被屏蔽的位置先替换成 `-inf`；求最大值时**跳过** `-inf`，避免 `-inf - (-inf) = nan`；指数时直接给 0。
- `e / s if s > 0 else 0.0`：如果整行都被屏蔽，`s = 0`，输出全 0 而不是除零。⚠️ 但在此之前，`max()` 面对空生成器会先抛 `ValueError`，所以这层防御实际上走不到。本程序的因果 mask 总保留对角线，不会出现整行屏蔽。

### 3.3 两种归一化

```python
def layer_norm(X, eps=1e-5):
    # ...
        mean = sum(row) / len(row)
        var = sum((v - mean) ** 2 for v in row) / len(row)
        denom = math.sqrt(var + eps)
        for j in range(X.cols):
            out.set(i, j, (row[j] - mean) / denom)

def rms_norm(X, eps=1e-6):
    # ...
        rms = math.sqrt(sum(v * v for v in row) / len(row) + eps)
        for j in range(X.cols):
            out.set(i, j, row[j] / rms)
```

| | LayerNorm | RMSNorm |
|--|-----------|---------|
| 公式 | `(x − mean) / √(var + ε)` | `x / √(mean(x²) + ε)` |
| 结果 | 均值 0、方差 1 | RMS 为 1，不居中 |
| `[1,2,3,4]` 的输出 | `[-1.342, -0.447, 0.447, 1.342]` | `[0.365, 0.730, 1.095, 1.461]` |
| 运算 | 两次归约（均值、方差） | 一次归约 |

- 都是**逐行**（逐 token）归一化，不跨 token、不跨 batch——这与 BatchNorm 不同，对变长序列和小 batch 都友好。
- `eps` 防止除以 0；`1e-5`（PyTorch `nn.LayerNorm` 的默认值）和 `1e-6` 都是常见取值。
- 方差除以 `len(row)`（总体方差），与 PyTorch 的 LayerNorm 一致。
- ⚠️ **简化**：两者都没有可学习的缩放 `γ`（和 LayerNorm 的偏置 `β`）。真实实现里 `y = norm(x) · γ (+ β)`，`γ` 初始化为 1。
- ⚠️ `layer_norm` 定义了但**从未被调用**；讲义 Step 4 说"把 LayerNorm 换成 RMSNorm"，实际代码一直用 RMSNorm，没有对照运行。

### 3.4 两种 FFN

```python
def silu(x):
    return x / (1.0 + math.exp(-x))


def ffn_swiglu(X, W1, W2, W3):
    h1 = matmul(X, W1)
    h3 = matmul(X, W3)
    gated = Matrix(h1.rows, h1.cols)
    for i in range(len(h1.data)):
        gated.data[i] = silu(h1.data[i]) * h3.data[i]
    return matmul(gated, W2)


def ffn_relu(X, W1, W2):
    h = matmul(X, W1)
    for i in range(len(h.data)):
        if h.data[i] < 0:
            h.data[i] = 0.0
    return matmul(h, W2)
```

- **SiLU / Swish**：`silu(x) = x · sigmoid(x) = x / (1 + e^{-x})`。`silu(-1) ≈ -0.269`、`silu(0) = 0`、`silu(2) ≈ 1.762`：平滑、负区间有小的非零值。
- **SwiGLU**：`(SiLU(X·W1) ⊙ (X·W3)) · W2`。`W3` 分支是"门"，与激活分支逐元素相乘，按输入动态调节每个隐藏单元。
- **逐位置（position-wise）**：FFN 对每一行（每个 token）独立做同样的运算，不在 token 之间交换信息——交换信息是 attention 的工作。
- `ffn_relu` 直接在 `h` 上原地把负数置 0，就是 ReLU。
- ⚠️ `math.exp(-x)` 在 `x < -709` 左右会抛 `OverflowError`（已验证 `silu(-1000.0)` 报错）。本程序数值很小不会触发；稳健写法是按符号分段计算 sigmoid，或用 NumPy 的向量化实现。
- ⚠️ 讲义 Step 1 列出了 `gelu(x)`，代码中没有这个函数。

### 3.5 attention：`causal` 与 `kv_source`

```python
def scaled_dot_product_attention(Q, K, V, causal=False):
    dk = Q.cols
    scores = matmul(Q, transpose(K))
    inv = 1.0 / math.sqrt(dk)
    for i in range(len(scores.data)):
        scores.data[i] *= inv
    mask = None
    if causal:
        mask = [[j > i for j in range(scores.cols)] for i in range(scores.rows)]
    w = softmax_rows(scores, mask=mask)
    return matmul(w, V)


def multi_head_attention(X, Wq, Wk, Wv, Wo, n_heads, causal=False, kv_source=None):
    Q = matmul(X, Wq)
    kv_input = kv_source if kv_source is not None else X
    K = matmul(kv_input, Wk)
    V = matmul(kv_input, Wv)
    d_head = Q.cols // n_heads
    head_outs = []
    for h in range(n_heads):
        Qh = Matrix(Q.rows, d_head, data=[Q.get(i, h * d_head + j) for i in range(Q.rows) for j in range(d_head)])
        # Kh、Vh 同理
        head_outs.append(scaled_dot_product_attention(Qh, Kh, Vh, causal=causal))
    # ... 拼接后乘 Wo
```

- **因果 mask**：`[[j > i ...]]` 生成上三角为 `True` 的矩阵，位置 i 不能看 `j > i` 的未来位置。
- **`kv_source`**：
  - 为 `None` 时，K、V 也来自 `X` → **self-attention**；
  - 传入 `enc_out` 时，Q 来自 decoder 的 `X`，K、V 来自 encoder 输出 → **cross-attention**。此时分数矩阵形状是 `(tgt_len, src_len) = (5, 6)`，不再是方阵。
- **拆头**用嵌套列表推导：`[Q.get(i, h*d_head + j) for i in range(Q.rows) for j in range(d_head)]`，外层 i、内层 j，按行优先顺序生成第 h 个头的数据，等价于第 03 节的 `split_heads`。
- 拼接时用 `concat = Matrix(X.rows, Q.cols)`：行数取 `X.rows`（query 的个数），对 cross-attention 也正确。
- ⚠️ 如果给 cross-attention 传 `causal=True`，mask 会按 `j > i` 屏蔽**源序列**中"编号大于目标位置"的 token，语义错误但不会报错（测验 Q9）。

### 3.6 `BlockParams`：一个 block 的全部权重

```python
class BlockParams:
    """All weights for one encoder or decoder block."""
    def __init__(self, d, n_heads, ffn_expansion, rng, use_swiglu=True):
        # ...
        self.Wq = randn(d, d, rng)
        # Wk, Wv, Wo 同理
        h = int(d * ffn_expansion)
        if use_swiglu:
            self.W1 = randn(d, h, rng)
            self.W2 = randn(h, d, rng)
            self.W3 = randn(d, h, rng)
        else:
            self.W1 = randn(d, h, rng)
            self.W2 = randn(h, d, rng)
        # cross-attention (decoder)
        self.Wq_x = randn(d, d, rng)
        # Wk_x, Wv_x, Wo_x 同理
```

- 一个对象装下 block 的全部权重，`encoder_block` / `decoder_block` 通过 `p.Wq` 等属性读取——类似 PyTorch 中 `nn.Module` 持有参数，但没有自动求导。
- `h = int(d * ffn_expansion)`：`d = 8, 2.0` → 16。
- 参数量（`d = 8, h = 16`）：自注意力 256，SwiGLU 384，cross-attention 256。
- ⚠️ **encoder block 也创建了 cross-attention 权重**（`Wq_x` 等），但 `encoder_block` 从不使用，白白占用参数和随机数序列。生产代码会为 encoder / decoder 分别定义参数类，或只在需要时创建。
- ⚠️ 所有线性层都没有 bias（与讲义"Bias terms: No"的 2026 默认一致）。

### 3.7 `encoder_block` 与 `decoder_block`：pre-norm 接线

```python
def encoder_block(x, p):
    # pre-norm self-attention + residual
    h = rms_norm(x)
    a = multi_head_attention(h, p.Wq, p.Wk, p.Wv, p.Wo, p.n_heads)
    x = add(x, a)
    # pre-norm FFN + residual
    h = rms_norm(x)
    f = ffn_swiglu(h, p.W1, p.W2, p.W3) if p.use_swiglu else ffn_relu(h, p.W1, p.W2)
    return add(x, f)


def decoder_block(x, enc_out, p):
    # 1) masked self-attention
    h = rms_norm(x)
    a = multi_head_attention(h, p.Wq, p.Wk, p.Wv, p.Wo, p.n_heads, causal=True)
    x = add(x, a)
    # 2) cross-attention to encoder output
    h = rms_norm(x)
    a = multi_head_attention(h, p.Wq_x, p.Wk_x, p.Wv_x, p.Wo_x, p.n_heads, kv_source=enc_out)
    x = add(x, a)
    # 3) FFN
    h = rms_norm(x)
    f = ffn_swiglu(h, p.W1, p.W2, p.W3) if p.use_swiglu else ffn_relu(h, p.W1, p.W2)
    return add(x, f)
```

- **固定的三行模式**：`h = norm(x)` → `a = sublayer(h)` → `x = add(x, a)`。注意残差加的是**未归一化的 `x`**，这就是 pre-norm：残差主干上没有任何变换，梯度可以从顶层直达底层。
- 对比 post-norm（原论文）：`x = norm(add(x, sublayer(x)))`。
- **encoder**：两个子层，自注意力不带 mask，双向。
- **decoder**：三个子层。只有第 1 个子层带因果 mask；第 2 个子层 cross-attention 的 K/V 来自 `enc_out`，不需要 mask（源序列在推理时一开始就完整可见）。
- **注意 `enc_out` 不做归一化**：在 pre-norm 架构中，encoder 栈末尾通常还会有一个 final norm，这里省略了。
- 条件表达式 `ffn_swiglu(...) if p.use_swiglu else ffn_relu(...)` 在一行内切换两种 FFN。
- ⚠️ **刻意的简化**：
  - pre-norm 的残差流范数会随深度增长（测验 Q10 实测 12 层从 4.7 增到 9.7），真实模型会在整个栈的最后加一个 final norm，这里没有；
  - 没有 dropout；
  - decoder 中没有 padding mask。

### 3.8 `main()`：只验证形状的前向演示

```python
    rng = random.Random(42)
    d = 8
    n_heads = 2
    ffn_expansion = 2.0
    src_len = 6
    tgt_len = 5

    src = randn(src_len, d, rng, scale=0.5)
    tgt = randn(tgt_len, d, rng, scale=0.5)

    enc_params = [BlockParams(d, n_heads, ffn_expansion, rng) for _ in range(2)]
    dec_params = [BlockParams(d, n_heads, ffn_expansion, rng) for _ in range(2)]

    enc_out = src
    for p in enc_params:
        enc_out = encoder_block(enc_out, p)

    dec_out = tgt
    for p in dec_params:
        dec_out = decoder_block(dec_out, enc_out, p)
```

- `src`、`tgt` 直接用随机矩阵代替"token embedding + 位置编码"。
- 先跑完整个 encoder 栈，再让 decoder 的**每一层**都读取同一个 `enc_out`。
- `src_len = 6`、`tgt_len = 5`：故意取不同长度，说明 decoder 与 encoder 的序列长度互不约束。
- ⚠️ **与讲义的差异**：讲义 Step 2–3 描述了 `embed + sinusoidal`、"final LN before the output projection"、输出形状 `(5, vocab)`；代码里没有 embedding 表、位置编码、final norm 和输出投影，decoder 输出是 `(5, 8)`。最后一行打印 "minus RoPE" 也承认了位置信号缺失。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| Pre-norm | 残差主干是恒等路径，深层训练稳定 | 残差流范数随深度增长，需要 final norm |
| RMSNorm、无 γ/β | 少一次归约；聚焦公式本身 | 生产中有可学习 γ（RMSNorm 无 β） |
| SwiGLU 为默认 | 2026 年主流 FFN | 多一个矩阵；扩展比应取 ≈ 8/3 以对齐参数（此处 2.0） |
| 一个函数 + `kv_source` 兼顾 self/cross | 少写重复代码，突出两者唯一区别 | 真实实现中 cross-attn 的 K/V 可以对 encoder 输出只算一次并缓存 |
| `BlockParams` 统一创建所有权重 | 实现简单 | encoder 白建了 cross-attn 权重；生产中按需创建 |
| 随机 src/tgt、无 embedding/输出头 | 讲义："this lesson is about the architecture, not the loss" | 无法训练、无法生成；第 07、08、14 节补齐 |
| 纯 Python 逐元素运算 | 每一步可见 | 极慢；生产中用 PyTorch + Flash Attention |
| 没有 bias、没有 dropout | 对齐现代 LLM 设定，代码更短 | 训练小模型时 dropout 往往仍有用 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `__slots__` | `__slots__ = ("rows", "cols", "data")` | 限定实例属性 |
| 条件表达式 | `data if data is not None else [fill] * (rows * cols)`；`e / s if s > 0 else 0.0` | 一行的 if-else |
| 带默认值的关键字参数 | `causal=False, kv_source=None`、`use_swiglu=True` | 用默认值让同一函数支持多种模式 |
| `None` 判断 | `if mask is not None:`、`kv_source if kv_source is not None else X` | 判断"有没有传"，用 `is` 而不是 `==` |
| 元组比较 + `assert` | `assert (A.rows, A.cols) == (B.rows, B.cols)` | 一次比较两个维度 |
| 列表推导 + 条件表达式 | `[row[j] if not mask[i][j] else float("-inf") for j in range(A.cols)]` | 推导式里嵌入 if-else |
| 带过滤的生成器 | `max(v for v in row if v != float("-inf"))` | 只对满足条件的元素求最大值；为空时 `max` 抛 `ValueError` |
| 嵌套推导（双 for） | `[Q.get(i, h*d_head + j) for i in range(Q.rows) for j in range(d_head)]` | 前一个 for 是外层循环 |
| 二维布尔列表 | `[[j > i for j in range(...)] for i in range(...)]` | 生成因果 mask |
| `zip` | `zip(A.data, B.data)` | 逐元素配对相加 |
| `enumerate` | `for h, H in enumerate(head_outs)` | 同时拿下标和元素 |
| 幂与开方 | `(v - mean) ** 2`、`math.sqrt(var + eps)` | 方差与标准差 |
| `math.exp` 与溢出 | `math.exp(-x)` | 参数过大抛 `OverflowError` |
| 类作参数容器 | `class BlockParams` + `p.Wq` | 用对象组织一组相关数据 |
| 列表推导创建对象 | `[BlockParams(d, n_heads, ffn_expansion, rng) for _ in range(2)]` | 一行创建多层参数 |
| 变量重绑定 | `x = add(x, a)`、`enc_out = encoder_block(enc_out, p)` | 每次得到新对象，旧对象不被修改 |
| f-string 格式符 | `f"{v:+.3f}"` | 总是显示正负号、3 位小数 |
| `random.Random(seed)` | `rng = random.Random(42)` | 可复现的独立随机数生成器 |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py` 的完整输出：

```text
=== full transformer forward pass ===
source shape:           (6, 8)
encoder output shape:   (6, 8)
target shape:           (5, 8)
decoder output shape:   (5, 8)
```

- 每个 block 的输入输出形状相同（残差连接的前提），所以 encoder 输出仍是 `(6, 8)`，decoder 输出仍是 `(5, 8)`。
- decoder 输出的行数由**目标序列**决定（5），与源序列长度（6）无关；cross-attention 的分数矩阵是 `5 × 6`。

```text
first 3 cells of encoder output:
  +0.263  -1.338  -0.318  -0.039
  +0.442  -1.696  +1.820  -0.824
  +0.139  -1.107  +0.876  -1.022

first 3 cells of decoder output:
  +0.578  -1.118  +2.352  -1.453
  -0.231  -1.505  +0.736  -1.752
  +1.638  -2.015  +0.222  -0.162
```

- 每行打印前 4 维。输入的标准差只有 0.5，输出已经出现 ±2 左右的值——这是 pre-norm 残差流"只加不归一化"的体现：每个子层的输出都直接累加到 `x` 上。
- 数值本身没有含义（随机权重、随机输入），关注点在于整条管线能跑通、形状正确。

```text
stack: 2-layer encoder + 2-layer decoder, pre-norm, RMSNorm, SwiGLU.
this is the 2026 block skeleton (minus RoPE).
```

- 补充两个额外验证（测验 Q9、Q10）：
  - 把第 5 个目标 token 改成全 9.0，decoder 前 4 行输出逐位不变，第 5 行变化——因果 mask 生效；
  - 改动源序列的某个 token，decoder 每一行都会变化——cross-attention 让每个目标位置都能看到全部源 token。

---

## 7. 动手改一改

1. **参数计数**（讲义练习 1）：写 `count_params(p, role)`，分别统计 encoder / decoder block 实际用到的参数；再算 `d=512, 扩展 4×, SwiGLU` 时的结果（应为 4,194,304）。
2. **切换旧组件**（讲义 Step 4 的反向）：给 `encoder_block` 加参数 `norm=rms_norm`，传入 `layer_norm` 运行；构造 `BlockParams(..., use_swiglu=False)` 运行 ReLU-FFN，确认形状不变。
3. **因果性单测**：按测验 Q9 修改最后一个目标 token，断言前面位置的输出不变。
4. **Post-norm 对比**（讲义练习 2）：实现 `post_norm_block`，比较 12 层后的激活范数——你会发现 post-norm 恒为 `√d`、pre-norm 逐层增长；再思考为什么 post-norm 的困难体现在梯度而不是激活上。
5. **补上缺失的部分**：加一个 embedding 表 `(vocab, d)`、第 04 节的正弦位置编码、栈末尾的 final RMSNorm、输出投影 `(d, vocab)`，让输出形状变为 `(5, vocab)`，与讲义 Step 3 对齐。
6. **进阶**：给 RMSNorm 加可学习的 `γ`，把 `silu` 改成数值稳定版本（`x ≥ 0` 时 `x / (1 + e^{-x})`，否则 `x · e^{x} / (1 + e^{x})`），并测试 `silu(-1000.0)`。

---

## 8. 常见坑

- **残差加错对象**：pre-norm 应是 `x + f(norm(x))`，写成 `norm(x) + f(norm(x))` 就丢掉了恒等主干。
- **忘记 final norm**：pre-norm 栈的残差流范数会增长，输出头前不归一化会让 logits 尺度失控。
- **cross-attention 加了因果 mask**：源序列后半部分对 decoder 不可见，不报错但结果错误。
- **decoder 的自注意力忘了 mask**：训练时"偷看答案"，loss 降得飞快，推理时完全失效。
- **SwiGLU 扩展比照搬 4×**：参数量比 ReLU-FFN 多 50%；对齐参数应取约 8/3。
- **`math.exp` 溢出**：标准库实现 SiLU/sigmoid 时，极端负输入会抛 `OverflowError`。
