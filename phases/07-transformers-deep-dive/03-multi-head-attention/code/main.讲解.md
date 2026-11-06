# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 03 节 多头 Attention ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`typing`），不需要 NumPy

---

## 1. 这份代码在考察什么

上一节用 NumPy 写了单头 attention，并用"一个列表装多个独立 `SelfAttention`"的方式拼出多头。这一节换了一个角度：**只用标准库**，自己造一个最小的 `Matrix` 类，然后按真实框架的思路实现多头：

1. **一次投影、再拆头**：Q/K/V 各用一个 `(d_model, d_model)` 矩阵算出来，再按列切成 `n_heads` 份——这就是 PyTorch 里 `reshape + transpose` 的逐元素版本。
2. **每头独立 attention、拼接、输出投影 `Wo`**：理解"头之间只在 `Wo` 处混合"。
3. **GQA（Grouped-Query Attention）**：K/V 头数少于 Q 头数，通过"复制引用"让多个 Q 头共享同一组 K/V。
4. **KV cache 账本**：用元素个数直观对比 MHA 与 GQA 的缓存大小。
5. **底层功底**：行优先存储、`i * cols + j` 下标换算、三重循环矩阵乘法——面试手写 attention 时这些都是基本功。

> 一句话：**这份代码把"拆头—并行 attention—拼接—投影"以及"GQA 只是让 K/V 少几个头"这两件事，拆到了每一个下标。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Matrix` | 类 | 行优先存储的二维浮点矩阵，提供 `get/set/row` | 张量的内存布局 |
| `randn_matrix(rows, cols, rng, scale=None)` | 函数 | 生成高斯随机矩阵，默认 Xavier 缩放 | 权重初始化 |
| `matmul(A, B)` | 函数 | i-k-j 顺序的三重循环矩阵乘法 | 线性投影、`QKᵀ`、`AV` |
| `transpose(A)` | 函数 | 转置 | `Kᵀ` |
| `softmax_rows(A)` | 函数 | 每行减最大值后做 softmax | attention 权重 |
| `scaled_dot_product_attention(Q, K, V)` | 函数 | 单头 `softmax(QKᵀ/√dk)V` | 单头 attention |
| `split_heads(X, n_heads)` | 函数 | 按列把 `(N, d_model)` 切成 `n_heads` 个 `(N, d_head)` | Split |
| `combine_heads(heads)` | 函数 | 把多个 `(N, d_head)` 按列拼回 `(N, d_model)` | Concat |
| `multi_head_attention(...)` | 函数 | 投影 → 拆头 → 逐头 attention → 拼接 → `Wo` | MHA |
| `grouped_query_attention(...)` | 函数 | 同上，但 K/V 只有 `n_kv_heads` 个头，复用给多个 Q 头 | GQA |
| `print_matrix` | 函数 | 打印矩阵（本文件中未被调用） | 调试工具 |
| `main()` | 函数 | 2 头 MHA 演示 + 4Q/2KV 的 GQA 演示 + KV cache 对比 | 演示入口 |

数据流：`X (6×8)` → `matmul` 得 `Q, K, V (6×8)` → `split_heads` 得 2 个 `(6×4)` → 每头 `scaled_dot_product_attention` 得 `(6×4)` 输出和 `(6×6)` 权重 → `combine_heads` 得 `(6×8)` → 乘 `Wo (8×8)` 得 `(6×8)`。

---

## 3. 逐段精讲

### 3.1 `Matrix`：一维列表 + 行优先下标

```python
class Matrix:
    """Row-major 2D matrix of floats. Just enough ops for attention."""

    __slots__ = ("rows", "cols", "data")

    def __init__(self, rows: int, cols: int, fill: float = 0.0, data=None):
        self.rows = rows
        self.cols = cols
        if data is not None:
            self.data = data
        else:
            self.data = [fill] * (rows * cols)

    def get(self, i: int, j: int) -> float:
        return self.data[i * self.cols + j]

    def set(self, i: int, j: int, v: float) -> None:
        self.data[i * self.cols + j] = v

    def row(self, i: int) -> List[float]:
        return self.data[i * self.cols:(i + 1) * self.cols]
```

- **行优先（row-major）**：二维矩阵存成一个长度 `rows × cols` 的一维列表，元素 `(i, j)` 位于 `i * cols + j`。这和 NumPy 默认的 C order、PyTorch 的连续张量完全一样。理解这一点，才能明白为什么"拆头"要先 `reshape(N, h, d_head)` 再 `transpose`，而不能直接 `reshape(h, N, d_head)`（测验 Q3、Q8）。
- **`__slots__`**：声明实例只有这三个属性，Python 就不再为每个实例创建 `__dict__`，省内存、属性访问略快，也能防止拼错属性名时悄悄新建属性。
- **`[fill] * (rows * cols)`**：用列表乘法一次性创建全 0 列表。对不可变的 float 这样写是安全的（若元素是列表就会出现"同一个对象被引用多次"的坑）。
- **`row(i)`** 用切片返回一行的**副本**，修改它不会影响矩阵本身。
- ⚠️ `data` 参数被直接引用而不复制；本文件中没有使用这个参数，所以无害。

### 3.2 `randn_matrix` 与 `matmul`

```python
def randn_matrix(rows, cols, rng, scale=None):
    if scale is None:
        scale = math.sqrt(2.0 / (rows + cols))
    m = Matrix(rows, cols)
    for i in range(rows * cols):
        m.data[i] = rng.gauss(0.0, scale)
    return m


def matmul(A: Matrix, B: Matrix) -> Matrix:
    assert A.cols == B.rows, f"{A.cols} vs {B.rows}"
    out = Matrix(A.rows, B.cols)
    for i in range(A.rows):
        for k in range(A.cols):
            aik = A.get(i, k)
            if aik == 0.0:
                continue
            base_i = i * B.cols
            base_k = k * B.cols
            for j in range(B.cols):
                out.data[base_i + j] += aik * B.data[base_k + j]
    return out
```

- **`scale=None` 哨兵**：不传就用 Xavier 标准差 `sqrt(2/(fan_in+fan_out))`；`main()` 生成输入 `X` 时显式传 `scale=1.0`，模拟标准正态的 embedding。
- **`rng` 作为参数传入**：所有随机数来自同一个 `random.Random(42)` 实例，依次抽取，因此整个程序可复现。注意 GQA 部分的权重是**接着**同一个 rng 抽取的，所以和 MHA 部分的权重不同。
- **i-k-j 循环顺序**：教科书写法是 i-j-k（内层对 k 求和），这里把 k 提到中间层：先取出 `A[i][k]`，再把 `B` 的第 k 行整行乘上它累加到 `out` 的第 i 行。好处是最内层连续访问 `B.data` 和 `out.data`（缓存友好），这也是 BLAS 类库的基本思路之一。
- **`if aik == 0.0: continue`**：遇到 0 直接跳过一整行的乘加，是稀疏输入下的小优化；对随机稠密矩阵几乎不触发。
- **`assert` 带消息**：维度不匹配时报 `AssertionError: 8 vs 4` 这样的提示，比 `IndexError` 好排查。GQA 中若 `Wk` 宽度设错，`QKᵀ` 这一步就会被这个断言拦下。
- 复杂度：`O(A.rows × A.cols × B.cols)`。

### 3.3 `softmax_rows` 与单头 attention

```python
def softmax_rows(A: Matrix) -> Matrix:
    out = Matrix(A.rows, A.cols)
    for i in range(A.rows):
        row = A.row(i)
        m = max(row)
        exps = [math.exp(x - m) for x in row]
        s = sum(exps)
        for j, e in enumerate(exps):
            out.set(i, j, e / s)
    return out


def scaled_dot_product_attention(Q: Matrix, K: Matrix, V: Matrix):
    dk = Q.cols
    scale = 1.0 / math.sqrt(dk)
    scores = matmul(Q, transpose(K))
    for i in range(scores.rows * scores.cols):
        scores.data[i] *= scale
    weights = softmax_rows(scores)
    out = matmul(weights, V)
    return out, weights
```

- 与上一节 NumPy 版逻辑完全相同：每行减最大值防溢出 → 指数 → 归一化。
- **缩放的写法**：先算 `scale = 1/√dk`，再对 `scores.data` 一维遍历做原地乘法——因为数据是一维列表，不需要两层循环。
- 这里的 `dk = Q.cols` 是**每个头的维度** `d_head`（主程序中为 4 或 2），而不是 `d_model`。多头时缩放因子用的是 `√d_head`，这一点面试常被追问。

### 3.4 `split_heads` / `combine_heads`：拆头与拼接

```python
def split_heads(X: Matrix, n_heads: int) -> List[Matrix]:
    assert X.cols % n_heads == 0, "d_model not divisible by n_heads"
    d_head = X.cols // n_heads
    heads = []
    for h in range(n_heads):
        H = Matrix(X.rows, d_head)
        for i in range(X.rows):
            for j in range(d_head):
                H.set(i, j, X.get(i, h * d_head + j))
        heads.append(H)
    return heads
```

- 第 `h` 个头取所有行（所有 token）的第 `h*d_head … (h+1)*d_head - 1` 列。例如 `d_model = 8, n_heads = 2` 时，head 0 取第 0–3 列，head 1 取第 4–7 列。
- 这与讲义 NumPy 版 `X.reshape(n, n_heads, d_head).transpose(1, 0, 2)` 逐元素等价（已验证）。真实框架里 reshape 和 transpose 往往只改"步长（stride）"而不复制数据，这里则是真的逐元素复制。
- `combine_heads` 是逆操作：把第 h 个头的第 j 列放回第 `h*d_head + j` 列。split 再 combine 应该原样还原。
- ⚠️ 返回的是 `List[Matrix]` 而不是一个三维张量，所以后面要用 Python 循环逐头计算；真实实现是一个 `(h, N, d_head)` 张量配合一次批量 matmul（讲义："Adding heads is free"）。

### 3.5 `multi_head_attention`：完整的 MHA

```python
def multi_head_attention(X: Matrix, Wq, Wk, Wv, Wo, n_heads: int):
    Q = matmul(X, Wq)
    K = matmul(X, Wk)
    V = matmul(X, Wv)
    Qh = split_heads(Q, n_heads)
    Kh = split_heads(K, n_heads)
    Vh = split_heads(V, n_heads)
    head_outs = []
    per_head_weights = []
    for q, k, v in zip(Qh, Kh, Vh):
        o, w = scaled_dot_product_attention(q, k, v)
        head_outs.append(o)
        per_head_weights.append(w)
    concat = combine_heads(head_outs)
    return matmul(concat, Wo), per_head_weights
```

- **与上一节的区别**：上一节每个头有自己的 `(16, 8)` 小矩阵；这里只有一个 `(8, 8)` 的 `Wq`，算完再拆。数学上两者等价（把大矩阵按列切开就是各头的小矩阵），但"一次大投影"在 GPU 上效率高得多。
- `zip(Qh, Kh, Vh)` 让第 h 个 Q 头只和第 h 个 K、V 头配对——各头在 attention 计算中互不通信。
- 拼接后乘 `Wo`：这是**头与头之间唯一的信息混合点**。
- 返回每个头的权重矩阵列表，方便打印对比。

### 3.6 `grouped_query_attention`：K/V 少几个头

```python
def grouped_query_attention(X: Matrix, Wq, Wk, Wv, Wo, n_heads: int, n_kv_heads: int):
    """Same as MHA but K and V have fewer heads, repeated to match Q."""
    Q = matmul(X, Wq)
    K = matmul(X, Wk)
    V = matmul(X, Wv)
    Qh = split_heads(Q, n_heads)
    Kh_small = split_heads(K, n_kv_heads)
    Vh_small = split_heads(V, n_kv_heads)
    repeat = n_heads // n_kv_heads
    Kh = [Kh_small[i // repeat] for i in range(n_heads)]
    Vh = [Vh_small[i // repeat] for i in range(n_heads)]
    # ... 之后与 MHA 相同，但不返回权重
```

- **只改了 K/V**：`Wk、Wv` 的输出宽度是 `d_head × n_kv_heads`，拆成 `n_kv_heads` 个头。
- **分组映射 `i // repeat`**：`n_heads = 4, n_kv_heads = 2` 时 `repeat = 2`，Q 头 0、1 → KV 头 0；Q 头 2、3 → KV 头 1。连续的 Q 头为一组，与 `np.repeat(kv, repeat, axis=0)` 的结果一致。
- **"复制"其实是引用**：`Kh` 列表里同一个 `Matrix` 对象出现了两次，并没有真的复制数据。这正是 GQA 省显存的本质——KV cache 只需存 `n_kv_heads` 份，计算时让多个 Q 头去读同一份。
- **退化情况**：`n_kv_heads == n_heads` 时 `repeat = 1`，就是 MHA（已验证输出逐位相同）；`n_kv_heads == 1` 时所有 Q 头共享一组，就是 MQA。
- ⚠️ 没有检查 `n_heads % n_kv_heads == 0`。如果不整除（例如 4 和 3），`repeat = 1`，`Kh_small[i // 1]` 在 i = 3 时会越界抛 `IndexError`。
- ⚠️ GQA **不减少** attention 的计算量：仍然是 `n_heads` 个 `(N, N)` 矩阵；它减少的是 K/V 投影参数和 KV cache。

### 3.7 `main()`：演示与 KV cache 账本

```python
    d_model = 8
    n_heads = 4
    n_kv = 2
    Wq = randn_matrix(d_model, d_model, rng)
    Wk = randn_matrix(d_model, (d_model // n_heads) * n_kv, rng)
    Wv = randn_matrix(d_model, (d_model // n_heads) * n_kv, rng)
    Wo = randn_matrix(d_model, d_model, rng)
    # ...
    kv_cache_full = n_heads * n * (d_model // n_heads) * 2
    kv_cache_gqa = n_kv * n * (d_model // n_heads) * 2
```

- GQA 演示：`d_head = 8 // 4 = 2`，K/V 宽度 `2 × 2 = 4`，所以 `Wk、Wv` 是 `(8, 4)`。参数量：`Wq 64 + Wk 32 + Wv 32 + Wo 64 = 192`，比同配置 MHA 的 256 少 1/4。
- KV cache 公式：`头数 × 序列长度 × d_head × 2`，最后的 `× 2` 代表 K 和 V 两份。真实估算还要乘**层数**和**每个元素的字节数**（fp16 为 2），见测验 Q10。
- `kv_cache_full // kv_cache_gqa` 用整除得到倍数 2，等于 `n_heads / n_kv`。
- ⚠️ 两个 token "the"（位置 0 和 4）在 `X` 中是两行**不同**的随机数，因为这里 X 是随机生成的，不是查词表得到的 embedding。真实模型里两者的 token embedding 相同，区别只来自位置编码。
- ⚠️ 讲义 Step 4 说"用 4 个头运行 MHA 并打印每个头"，代码实际 MHA 演示是 2 个头（4 个头用在 GQA 演示中，且 GQA 不打印权重）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯标准库 + 自制 `Matrix` | 每个下标都可见，理解内存布局 | 极慢；生产用 PyTorch 张量 + 批量 matmul |
| 一维列表行优先存储 | 与 NumPy/PyTorch 内存布局一致 | 需要手动换算下标 |
| 一次大投影再按列拆头 | 对应真实框架的实现方式 | 这里逐元素复制；真实框架只改 stride（view） |
| 逐头 Python 循环 | 直观 | 真实实现是一次 `(h, N, d_head)` 批量 matmul，"加头免费" |
| GQA 用列表引用实现共享 | 体现"KV 只存一份"的本质 | 框架里用 `repeat_interleave` / `expand`，或 kernel 直接支持 GQA（如 `enable_gqa=True`） |
| KV cache 只数元素个数 | 突出 `n_heads / n_kv_heads` 的倍数关系 | 实际要乘层数、batch、字节数 |
| 没有 mask、没有 batch 维 | 聚焦多头本身 | decoder 需要因果 mask，训练需要 batch 与 padding mask |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块 docstring | 文件开头三引号 | 说明文件用途 |
| `class` 与 `__init__` | `class Matrix: def __init__(self, rows, cols, fill=0.0, data=None)` | 定义类；带默认值的参数 |
| `__slots__` | `__slots__ = ("rows", "cols", "data")` | 限定实例属性，省内存、防拼写错误 |
| 类型注解 | `rows: int`、`-> float`、`-> None`、`-> List[float]` | 只是提示，不在运行时强制检查 |
| `typing.List` | `from typing import List`；`List[Matrix]` | 泛型列表注解（Python 3.9+ 也可直接写 `list[Matrix]`） |
| `None` 作默认值哨兵 | `scale=None` ... `if scale is None:` | 区分"没传"和"传了某个值" |
| 列表乘法 | `[fill] * (rows * cols)` | 快速创建重复元素的列表（元素是不可变对象时安全） |
| 切片 | `self.data[i * self.cols:(i + 1) * self.cols]` | 取一段连续元素，返回新列表 |
| `assert` + 消息 | `assert A.cols == B.rows, f"{A.cols} vs {B.rows}"` | 断言失败时附带说明 |
| 增强赋值 | `out.data[base_i + j] += ...`、`scores.data[i] *= scale` | 原地累加 / 原地缩放 |
| `continue` | `if aik == 0.0: continue` | 跳过本次循环剩余部分 |
| 列表推导式 | `[math.exp(x - m) for x in row]`、`[Kh_small[i // repeat] for i in range(n_heads)]` | 一行构造列表 |
| `zip` 三路解包 | `for q, k, v in zip(Qh, Kh, Vh)` | 同时遍历三个列表 |
| `enumerate` | `for j, e in enumerate(exps)`、`for h, H in enumerate(heads)` | 同时拿下标和元素 |
| 返回元组 | `return out, weights`；`o, _ = ...` | `_` 表示忽略不用的返回值 |
| `random.Random(seed)` / `rng.gauss` | `rng = random.Random(42)`；`rng.gauss(0.0, scale)` | 独立的随机数生成器实例，可复现 |
| 嵌套 f-string 格式 | `f"{v:>{width}.{prec}f}"` | 宽度和精度本身也可以是变量 |
| `str.join` + 生成器 | `"  ".join(f"..." for v in row)` | 用分隔符拼接字符串 |
| `print(..., end="")` | `print(f"{t:>7}", end="")` | 不换行打印 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py` 的完整输出：

```text
=== multi-head attention: 2 heads, d_model=8, d_head=4 ===
input  shape: (6, 8)
output shape: (6, 8)
```

- 多头 attention 的输入输出形状相同，都是 `(N, d_model)`——这让它可以和残差连接直接相加（第 05 节）。

```text
-- head 0 attention weights --
          the    cat    sat     on    the    mat
   the  0.147  0.214  0.262  0.154  0.121  0.102
   cat  0.113  0.230  0.217  0.156  0.219  0.065
   sat  0.125  0.158  0.092  0.132  0.352  0.142
    on  0.103  0.245  0.346  0.154  0.103  0.048
   the  0.132  0.238  0.389  0.112  0.053  0.077
   mat  0.177  0.177  0.228  0.161  0.111  0.146

-- head 1 attention weights --
          the    cat    sat     on    the    mat
   the  0.180  0.161  0.136  0.217  0.167  0.139
   cat  0.141  0.167  0.109  0.210  0.257  0.116
   sat  0.186  0.171  0.141  0.166  0.116  0.219
    on  0.140  0.179  0.143  0.297  0.119  0.121
   the  0.153  0.095  0.153  0.222  0.339  0.039
   mat  0.144  0.171  0.209  0.157  0.157  0.163
```

- 每行和为 1（例如 head 0 第一行 0.147 + 0.214 + 0.262 + 0.154 + 0.121 + 0.102 = 1.000）。
- **两个头的模式明显不同**：head 0 中有 4 行把最大权重给了 "sat"（第 3 列）；head 1 的分布更分散，列总和最大的是 "on"（第 4 列）。同一个输入、不同的投影子空间 → 不同的注意力分布，这就是多头的意义。
- 两个 "the" 的行完全不同，因为它们在随机 `X` 中是不同的向量（见 3.7 节）。
- 权重整体比较平坦（最大不到 0.4）：随机初始化 + `1/√d_head` 缩放，softmax 远未饱和。
- 再次提醒：未训练的随机权重，模式没有语言学含义。

```text
=== GQA: 4 Q heads, 2 KV heads ===
output shape: (6, 8)
KV cache elements (MHA):  96
KV cache elements (GQA):  48  (2x smaller)
```

- GQA 的输出形状与 MHA 相同，对后续层完全透明。
- KV cache：`4 × 6 × 2 × 2 = 96` vs `2 × 6 × 2 × 2 = 48`，缩小 `n_heads / n_kv = 2` 倍。放到 Llama 3 70B（64 Q 头 / 8 KV 头）上就是 8 倍。

---

## 7. 动手改一改

1. **验证 split/combine 互逆**：随机生成一个 `6×8` 矩阵，`combine_heads(split_heads(M, 2))` 后逐元素比较，应完全相同。
2. **验证 GQA 的退化**：同一组 `d_model × d_model` 权重下，`grouped_query_attention(..., n_heads=4, n_kv_heads=4)` 与 `multi_head_attention(..., n_heads=4)` 输出应逐位相同。
3. **实现 MQA**（讲义练习 2）：令 `n_kv = 1`，`Wk、Wv` 形状变为 `(8, 2)`；算出参数量和 KV cache 的变化，再把公式推广到 `N = 2048`。
4. **加整除检查**：在 `grouped_query_attention` 开头加 `assert n_heads % n_kv_heads == 0`，并测试 `n_heads=4, n_kv_heads=3` 时原代码的报错。
5. **输出 GQA 的权重**：让 `grouped_query_attention` 也返回各头的权重，观察共享同一 KV 头的 Q 头 0 和 1 的模式是否相似（提示：K 相同、Q 不同，模式仍然不同）。
6. **进阶**：用 NumPy 重写成 `(h, N, d_head)` 张量 + 一次 `@` 批量矩阵乘，再与本文件结果对比，并用 `time.perf_counter()` 比较 `d_model = 256、N = 128` 时两者的速度。

---

## 8. 常见坑

- **用错 reshape 拆头**：`reshape(h, N, d_head)` 会跨 token 切分；正确做法是先 `reshape(N, h, d_head)` 再转置。
- **缩放因子用错**：多头时应除以 `√d_head`，而不是 `√d_model`。
- **GQA 分组约定不一致**：连续分组（`i // repeat`）与交错分组（`i % n_kv`）都能训练，但加载已有权重时必须与原实现一致，否则结果悄悄出错。
- **误以为 GQA 降低了 attention 计算量**：它省的是 K/V 投影参数和 KV cache，`n_heads` 个 `(N, N)` 分数矩阵一个都没少。
- **KV cache 漏乘因子**：忘记 K、V 两份（`× 2`）、层数、batch 或字节数，估算会差一个数量级。
- **`n_heads % n_kv_heads != 0`**：代码没有检查，会在列表索引时越界。
