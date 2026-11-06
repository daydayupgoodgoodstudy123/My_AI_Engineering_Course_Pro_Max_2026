# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 04 节 位置编码 — 正弦、RoPE、ALiBi ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

attention 天生不知道顺序。这份代码用几个十几行的小函数，把三代位置编码方案各实现一遍，并用数值实验验证它们最关键的性质：

1. **正弦绝对位置编码**：`sin/cos` 多频率表是怎么算出来的，前几个位置长什么样。
2. **RoPE 的相对位置性质**：旋转是按**绝对**位置做的，但 `q·k` 只依赖**相对**距离——用四对"gap 相同、绝对位置不同"的位置做实验，结果完全一致。
3. **RoPE 的 base**：base 越大，旋转越慢；这是 NTK-aware、YaRN 等长上下文扩展技巧调节的"旋钮"。
4. **ALiBi**：不改 embedding，只在分数上加一个与距离成正比的惩罚，每个头一个斜率。

> 一句话：**这份代码把"位置编码 = 往 attention 里注入顺序信号"的三种做法，压缩成可以手算、可以验证的几十行代码。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sinusoidal_pe(n, d, base=10000.0)` | 函数 | 生成 `n × d` 的正弦位置表 | 绝对位置编码（Vaswani 2017） |
| `apply_rope(x, pos, base=10000.0)` | 函数 | 把向量 x 的每对 `(2i, 2i+1)` 维旋转 `pos·θ_i` | RoPE |
| `dot(a, b)` | 函数 | 点积 | attention 打分 |
| `alibi_slopes(n_heads)` | 函数 | 生成几何级数斜率 `2^(-8(h+1)/H)` | ALiBi 每头斜率 |
| `alibi_bias(n_heads, seq_len, causal=True)` | 函数 | 生成每个头的 `(seq_len, seq_len)` 偏置矩阵 | ALiBi 偏置（可合并因果 mask） |
| `demo_sinusoidal` | 演示 | 打印前 4 个位置、前 4 维 | 观察多频率 |
| `demo_rope_relative` | 演示 | 4 对 gap = 2 的位置，比较旋转后的点积 | RoPE 相对位置性质 |
| `demo_rope_base_scaling` | 演示 | 同一对位置在 3 个 base 下的分数 | base 对旋转速度的影响 |
| `demo_alibi` | 演示 | 打印 4 个头的斜率和 head 0 的偏置矩阵 | ALiBi |
| `main()` | 入口 | 依次调用四个演示 | — |

四个演示互相独立；`demo_rope_*` 依赖 `apply_rope` 和 `dot`，`demo_alibi` 依赖 `alibi_slopes` 和 `alibi_bias`。

---

## 3. 逐段精讲

### 3.1 `sinusoidal_pe`：多频率正弦表

```python
def sinusoidal_pe(n, d, base=10000.0):
    pe = [[0.0] * d for _ in range(n)]
    for pos in range(n):
        for i in range(d // 2):
            theta = pos / (base ** (2 * i / d))
            pe[pos][2 * i] = math.sin(theta)
            pe[pos][2 * i + 1] = math.cos(theta)
    return pe
```

- 对应公式 `PE[pos, 2i] = sin(pos / 10000^(2i/d))`、`PE[pos, 2i+1] = cos(...)`。
- **多频率**：第 i 对维度的角频率是 `1 / 10000^(2i/d)`。i = 0 时频率为 1（波长 2π ≈ 6.3 个位置），i 越大频率越低。`d = 8` 时四对的波长分别约为 6.3、62.8、628、6283 个位置。低维像"秒针"区分相邻位置，高维像"时针"区分远距离位置。
- **为什么 sin、cos 成对**：`(sin(pω), cos(pω))` 是单位圆上的一个点，位置每加 k，这个点就旋转 `kω`，是一个只依赖 k 的线性变换——这正是 RoPE 思想的前身。
- **`[[0.0] * d for _ in range(n)]`**：必须用列表推导创建二维列表。如果写成 `[[0.0] * d] * n`，n 行会是**同一个列表对象**的 n 个引用，改一行全都变。
- ⚠️ 要求 `d` 为偶数；若 d 为奇数，最后一维保持 0。
- ⚠️ 这里只生成位置表，没有演示"加到 embedding 上"（讲义：`X' = X + PE[:N]`）。

### 3.2 `apply_rope`：成对旋转

```python
def apply_rope(x, pos, base=10000.0):
    """Rotate even/odd pairs of x by angle pos * theta_i."""
    d = len(x)
    out = list(x)
    for i in range(d // 2):
        theta = pos / (base ** (2 * i / d))
        c = math.cos(theta)
        s = math.sin(theta)
        a = x[2 * i]
        b = x[2 * i + 1]
        out[2 * i] = a * c - b * s
        out[2 * i + 1] = a * s + b * c
    return out
```

- 把 `(x[2i], x[2i+1])` 看成平面上的一个点，乘以旋转矩阵 `[[cos, −sin], [sin, cos]]`，旋转角为 `pos · θ_i`，`θ_i = base^(-2i/d)`。注意这里变量名 `theta` 存的已经是"角度 = pos × θ_i"。
- **为什么只依赖相对位置**：旋转矩阵满足 `R(α)ᵀR(β) = R(β − α)`，于是 `R(mθ)q · R(nθ)k = qᵀR((n−m)θ)k`。展开到单个二维平面：

```text
q'·k' = cos((m−n)θ)·(a₁b₁ + a₂b₂) + sin((m−n)θ)·(a₁b₂ − a₂b₁)
```

  既有 cos 项也有 sin 项（讲义 Step 2 只提到 cos 因子，不完整）；sin 项使 RoPE 能区分 `m − n = 2` 和 `m − n = −2`，即编码的是**有方向**的相对位置。
- **`out = list(x)` 再逐个改写**：先复制一份，读取永远从原始 `x` 读（`a = x[2*i]`），写入 `out`，避免边读边写的混乱。讲义说 "operates in-place"，实际代码返回新列表，不修改输入。
- **保范性**：旋转不改变向量长度，所以 RoPE 不会放大或缩小 q、k 的模长。
- ⚠️ **配对方式**：这里用相邻维度 `(2i, 2i+1)` 配对（RoFormer 论文写法）。HuggingFace 的 Llama 等实现用 `rotate_half`，把 `(i, i + d/2)` 配成一对。两者数学等价，但训练出的权重不能混用，否则模型输出会悄悄劣化（测验 Q14）。
- ⚠️ 真实模型中 d 是 **`d_head`**（每个头的维度），RoPE 在每一层、每个头内分别作用于 Q 和 K；这里用一个独立向量演示。

### 3.3 `dot` 与 RoPE 相对位置实验

```python
def demo_rope_relative():
    rng = random.Random(0)
    d = 16
    q = [rng.gauss(0, 1) for _ in range(d)]
    k = [rng.gauss(0, 1) for _ in range(d)]

    pairs = [(3, 5), (7, 9), (100, 102), (1024, 1026)]
    for pq, pk in pairs:
        q_rot = apply_rope(q, pq)
        k_rot = apply_rope(k, pk)
        d_prod = dot(q_rot, k_rot)
        print(f"{pq:>6}  {pk:>6}  {pk - pq:>4}  {d_prod:>18.6f}")
```

- 这就是讲义 Step 4 的验证：同一对原始向量 q、k，放在四组不同的绝对位置，但 gap 都是 2——四个点积到小数点后 6 位完全一致。
- `random.Random(0)` 创建独立的随机数生成器，结果可复现。
- 这个实验也可以用来**检测实现 bug**：如果忘了旋转 k，或者 q、k 用了不同的 base，四行就不会相同。

### 3.4 `demo_rope_base_scaling`：base 的作用

```python
    for base in [10000, 100000, 1_000_000]:
        q_rot = apply_rope(q, pos=4096, base=base)
        k_rot = apply_rope(k, pos=4098, base=base)
        print(f"  base={base:>8d}  score={dot(q_rot, k_rot):+.6f}")
```

- `θ_i = base^(-2i/d)`：base 越大，i ≥ 1 的各对维度旋转越慢，同一相位需要更长的距离才会"绕回"。这是 NTK-aware 缩放、Llama 等模型使用更大 base 的出发点。
- ⚠️ 这个演示的说服力有限：因为分数只依赖 gap（= 2），所以 `(4096, 4098)` 和 `(0, 2)` 的分数完全相同（已验证），"4096"这个大位置其实不起作用；三个 base 的分数差别也很小，只说明"base 改变了各维度的角度"。
- ⚠️ 一个容易忽略的细节：i = 0 时 `base^0 = 1`，第 0 对维度的旋转速度与 base 无关（每位置 1 弧度）。所以 base 增大到 100 万，分数也不会收敛到未旋转的 `q·k`（本例为 1.944）。
- 演示标题写着 "NTK-aware"，但代码只是直接换 base；真正的 NTK-aware 公式是 `base' = base · s^(d/(d−2))`（讲义 Use It 部分）。

### 3.5 ALiBi：斜率与偏置矩阵

```python
def alibi_slopes(n_heads):
    return [2 ** (-8 * (h + 1) / n_heads) for h in range(n_heads)]


def alibi_bias(n_heads, seq_len, causal=True):
    slopes = alibi_slopes(n_heads)
    out = []
    for m in slopes:
        head_bias = []
        for i in range(seq_len):
            row = []
            for j in range(seq_len):
                if causal and j > i:
                    row.append(float("-inf"))
                else:
                    row.append(-m * abs(i - j))
            head_bias.append(row)
        out.append(head_bias)
    return out
```

- **斜率**：`2^(-8/H), 2^(-16/H), …, 2^(-8)`，是一个几何级数。4 个头时为 `0.25, 0.0625, 0.0156, 0.0039`；8 个头时为 `1/2, 1/4, …, 1/256`。
- **偏置**：`bias[h][i][j] = -m_h · |i − j|`，在 softmax **之前**加到第 h 个头的分数上。距离越远惩罚越大；斜率大的头"近视"（关注局部），斜率小的头"远视"（几乎均匀）。
- **`causal=True`**：把 `j > i` 的位置设为 `float("-inf")`，相当于把因果 mask 和 ALiBi 合并成一个矩阵，decoder 中一次相加即可。
- 返回的是三层嵌套列表：`[头][行][列]`。
- ⚠️ 原论文的斜率公式针对头数为 2 的幂的情况；头数不是 2 的幂时论文另有插值规则，这里没有处理。
- ⚠️ 没有演示"加到分数上再 softmax"的完整过程；测验 Q10(c) 给出了参考实现。

### 3.6 `demo_alibi` 与 `-0.00`

```python
    bias = alibi_bias(n_heads, seq_len=6, causal=False)
    for row in bias[0]:
        print("  " + "  ".join(f"{v:+6.2f}" for v in row))
```

- 演示时用 `causal=False`，打印出对称矩阵，看得更清楚。
- 对角线打印为 `-0.00`：`-m * abs(0)` 在 IEEE 754 浮点中是**负零** `-0.0`，数值上等于 0，`+` 格式符会把它的符号显示出来。不影响计算。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python、逐元素循环 | 每个公式都能对上一行代码 | 慢；生产中预先算好 `cos/sin` 缓存表，向量化地作用于整个 `(B, h, N, d_head)` 张量 |
| RoPE 用相邻维配对 | 与论文公式一一对应 | 很多框架用 `rotate_half` 配对，两者权重不兼容 |
| 每次调用都重算 `base ** (2i/d)` | 代码短 | 生产中只算一次频率表（`inv_freq`），按位置广播 |
| ALiBi 偏置可选合并因果 mask | decoder 中一次加法搞定 | 真实实现通常在 kernel 内即时计算偏置，不物化 `(h, N, N)` 矩阵 |
| base 演示只换 base | 直观展示"旋转变慢" | 真正的长上下文扩展需要 NTK/YaRN 公式 + 微调 + NIAH 验证 |
| 用随机 q、k 验证性质 | 性质与具体数值无关 | 真实模型中 q、k 来自学习到的投影 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块 docstring / 函数 docstring | 文件开头；`"""Rotate even/odd pairs ..."""` | 说明用途，可用 `help()` 查看 |
| 默认参数 | `base=10000.0`、`causal=True` | 调用时可以省略 |
| 关键字参数调用 | `sinusoidal_pe(n=8, d=8)`、`apply_rope(q, pos=4096, base=base)` | 按名字传参，可读性更好 |
| 幂运算 `**` | `base ** (2 * i / d)`、`2 ** (-8 * (h + 1) / n_heads)` | 支持小数和负指数 |
| 整除 `//` | `range(d // 2)` | 向下取整的除法 |
| 二维列表的正确创建 | `[[0.0] * d for _ in range(n)]` | 每行是独立列表；`[[0.0]*d]*n` 会共享同一行 |
| 列表复制 | `out = list(x)` | 浅拷贝，修改 `out` 不影响 `x` |
| 生成器表达式 | `sum(x * y for x, y in zip(a, b))` | 点积的惯用写法 |
| 列表推导式 | `[rng.gauss(0, 1) for _ in range(d)]` | 一行生成随机向量 |
| 元组列表 + 解包 | `pairs = [(3, 5), ...]`；`for pq, pk in pairs` | 遍历时直接拆成两个变量 |
| `float("-inf")` | `row.append(float("-inf"))` | 负无穷，`math.exp(-inf) == 0.0` |
| 条件组合 | `if causal and j > i:` | `and` 短路求值 |
| `random.Random(seed)` | `rng = random.Random(0)` | 独立、可复现的随机数生成器 |
| f-string 格式符 | `f"{v:+.3f}"`、`f"{base:>8d}"`、`f"{d_prod:>18.6f}"`、`f"{v:+6.2f}"` | `+` 总是显示符号；`>8d` 右对齐的整数；`.6f` 6 位小数 |
| `str.join` | `"  ".join(f"{v:+.3f}" for v in pe[pos][:4])` | 用分隔符拼接 |
| 切片 | `pe[pos][:4]` | 取前 4 个元素 |
| 数字分隔符 | `1_000_000` | 仅为可读 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py` 的输出：

```text
=== sinusoidal positional encoding ===
first 4 positions, first 4 dims:
  pos=0: +0.000  +1.000  +0.000  +1.000
  pos=1: +0.841  +0.540  +0.100  +0.995
  pos=2: +0.909  -0.416  +0.199  +0.980
  pos=3: +0.141  -0.990  +0.296  +0.955
```

- `pos=0`：所有角度为 0，sin = 0、cos = 1。
- 前两列（i = 0，频率 1）变化剧烈：`sin(1)=0.841、sin(2)=0.909、sin(3)=0.141`，3 个位置就转了大半圈。
- 后两列（i = 1，频率 1/10）变化缓慢：`sin(0.1)≈0.100、sin(0.2)≈0.199`，几乎线性。这就是"低维变化快、高维变化慢"的多频率结构（讲义练习 1 让你画成热力图观察条纹）。

```text
=== RoPE: dot product depends only on relative distance ===
 pos_q   pos_k   gap      <q_rot, k_rot>
     3       5     2           -6.530165
     7       9     2           -6.530165
   100     102     2           -6.530165
  1024    1026     2           -6.530165
all rows with gap=2 should have matching dot products.
```

- 四行完全一致，验证了 RoPE 的核心性质。作为对照：未旋转时 `q·k ≈ 1.573`；把 `(0, 2)` 放进去也得到 `-6.530165`；如果把位置换成 `(5, 3)`（gap = −2），结果变成 `-2.320`——说明 RoPE 编码的相对位置是有方向的。

```text
=== RoPE base scaling (NTK-aware for long context) ===
  base=   10000  score=+1.331200
  base=  100000  score=+1.368584
  base= 1000000  score=+1.388781
larger base = slower rotation = longer context without phase wrap.
```

- base 增大，i ≥ 1 的维度旋转变慢，分数略有变化。由于只依赖 gap，这三个分数与位置 `(0, 2)` 时的结果完全相同。由于第 0 对维度不受 base 影响，分数不会回到未旋转的 `q·k ≈ 1.944`。

```text
=== ALiBi bias matrix ===
slopes for 4 heads: 0.2500, 0.0625, 0.0156, 0.0039
head 0 bias (closer tokens get smaller penalty):
   -0.00   -0.25   -0.50   -0.75   -1.00   -1.25
   -0.25   -0.00   -0.25   -0.50   -0.75   -1.00
   ...
```

- 斜率是 `2^-2, 2^-4, 2^-6, 2^-8`。
- head 0 的偏置矩阵是对称的 Toeplitz 矩阵（每条对角线上的值相同），只依赖 `|i − j|`。距离 5 的惩罚为 −1.25：若原始分数相同，softmax 后最近与最远 token 的权重比约为 `e^1.25 ≈ 3.5`。
- 对角线 `-0.00` 是浮点负零，见 3.6 节。

```text
takeaway: RoPE encodes relative position in the dot product itself.
ALiBi skips embeddings entirely. sinusoidal is a footnote by 2026.
```

---

## 7. 动手改一改

1. **画正弦热力图**（讲义练习 1）：生成 `sinusoidal_pe(512, 128)`，用 matplotlib（如已安装）或打印 ASCII 字符，观察"维度越高，条纹越宽"。
2. **验证 RoPE 的方向性**：在 `pairs` 中加入 `(5, 3)`、`(9, 7)`，确认 gap = −2 的行互相一致、但与 gap = +2 不同。
3. **制造 bug 再检测**：把 `k_rot = apply_rope(k, pk)` 改成 `k_rot = k`，观察四行结果不再一致。这是 RoPE 实现的最小单元测试。
4. **实现 `rotate_half` 版本**：写 `apply_rope_half(x, pos)`，把 `(x[i], x[i + d/2])` 配成一对旋转；验证它同样满足相对位置性质，但与 `apply_rope` 的输出不同。
5. **实现 NTK-aware base**：写 `ntk_base(base, scale, d) = base * scale ** (d / (d - 2))`，对比 `scale = 4` 时各维度的 `θ_i` 与原始 base 的比值，观察高频维几乎不变、低频维被拉伸。
6. **完成 ALiBi attention**：把 `alibi_bias(..., causal=True)` 加到一个随机分数矩阵上做 softmax，检查上三角权重为 0、每行和为 1，并比较斜率最大与最小的头的权重分布。

---

## 8. 常见坑

- **只旋转 q 不旋转 k（或用了不同的 base / 位置偏移）**：相对位置性质立刻失效，且不会报错。
- **把 RoPE 用在 V 上**：没有必要，会把位置相位混进输出。
- **RoPE 配对方式不一致**：相邻配对与 `rotate_half` 配对的权重不能混用。
- **ALiBi 偏置加在 softmax 之后**：会破坏归一化；必须加在 softmax 之前的分数上。
- **`[[0.0] * d] * n` 创建二维表**：n 行共享同一个列表，修改一行全部改变。
- **只改 base / 最大长度就上线长上下文**：通常还需要微调，并在完整目标长度上做 NIAH 与困惑度验证。
