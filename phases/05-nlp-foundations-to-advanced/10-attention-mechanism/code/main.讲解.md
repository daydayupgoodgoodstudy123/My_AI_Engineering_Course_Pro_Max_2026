# 代码讲解 · main.py

> **所属小节**：阶段 05 · NLP 基础到进阶 · 第 10 节 Attention 机制——突破 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py` ｜ **依赖**：仅 Python 标准库（`math`）；讲义中的 NumPy 版本和 `nn.MultiheadAttention` 示例不在本文件里

---

## 1. 这份代码在考察什么

讲义用 NumPy 写了 attention，这份代码则退一步，用**纯 Python 列表**重写了两种经典打分方式，并加入了讲义版本没有的维度检查：

1. **数值稳定的 softmax**：先减最大值，再取指数、归一化。
2. **Luong dot attention**：分数 = decoder 状态与每个 encoder 状态的点积；权重 = softmax；上下文 = 加权平均。
3. **Bahdanau additive attention**：分数 = `v_aᵀ · tanh(W_a·s + U_a·h_i)`，通过一个小前馈网络打分。
4. **形状意识**：`dot`、`matvec`、`dot_attention` 都在入口检查长度，把讲义"Shapes (the thing that bites everyone)"落实为代码里的 `ValueError`。
5. **看清"对齐"从哪里来**：dot attention 不需要训练就体现相似度；而手写参数的加性 attention 输出几乎均匀、甚至"对错了"——对齐能力要靠学习。

> 一句话：**每一步都看得见的 attention**——把讲义的五步流程（query → 打分 → softmax → 加权和 → 上下文）逐行实现，并用三个 decoder 状态观察权重如何移动。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `softmax(scores)` | 函数 | 减最大值后归一化为概率分布 | attention 权重 `α` |
| `dot(a, b)` | 函数 | 带长度检查的点积 | 相似度打分 |
| `dot_attention(decoder_state, encoder_states)` | 函数 | Luong dot：打分 → softmax → 加权平均 | 乘性 attention |
| `matvec(M, v)` | 函数 | 带形状检查的矩阵×向量 | `W_a·s`、`U_a·h` 投影 |
| `tanh_vec(v)` | 函数 | 逐元素 tanh | 加性打分的非线性 |
| `additive_attention(decoder_state, encoder_states, W_a, U_a, v_a)` | 函数 | Bahdanau 加性打分 → softmax → 加权平均 | 加性 attention |
| `main()` | 函数 | 3 个 encoder 状态（cat/sat/mat），分别用两种 attention 观察权重 | 演示入口 |

调用关系：`dot_attention → dot, softmax`；`additive_attention → matvec, tanh_vec, dot, softmax`；两者最后都用同一段循环计算上下文向量。

---

## 3. 逐段精讲

### 3.1 数值稳定的 softmax

```python
def softmax(scores):
    m = max(scores)
    exps = [math.exp(s - m) for s in scores]
    total = sum(exps)
    return [e / total for e in exps]
```

- 公式 `softmax(x)_i = exp(x_i) / Σ exp(x_j)`。所有 `x_i` 同减一个常数 m，分子分母同乘 `e^(-m)`，结果不变。
- 减去最大值后，最大的指数项是 `e⁰ = 1`，其他都在 (0, 1]，**不会上溢**；不减的话，分数为 1000 时 `math.exp(1000)` 会抛 `OverflowError`。
- 输出非负、和为 1——这就是"注意力权重"的定义。
- ⚠️ 边界：空列表时 `max([])` 抛 `ValueError`；全部为 `-inf`（例如 padding 全被 mask）时 `-inf - (-inf) = nan`，得到全 `nan` 的权重。加 mask 时要处理这个情况（测验 Q10）。

### 3.2 带检查的点积与 Luong dot attention

```python
def dot(a, b):
    if len(a) != len(b):
        raise ValueError(f"dot: length mismatch {len(a)} vs {len(b)}")
    return sum(x * y for x, y in zip(a, b))
```

- 关键的防御：`zip` 遇到长度不同的序列会**静默截断**，这正是讲义技能卡警告的"silently broadcast"类 bug——不报错、结果却是错的。这里显式检查并抛出带具体数字的异常。

```python
def dot_attention(decoder_state, encoder_states):
    if not encoder_states:
        raise ValueError("dot_attention: encoder_states must not be empty")
    d_s = len(decoder_state)
    for i, h in enumerate(encoder_states):
        if len(h) != d_s:
            raise ValueError(
                f"dot_attention: encoder_states[{i}] length {len(h)} != decoder_state length {d_s}"
            )
    scores = [dot(decoder_state, h) for h in encoder_states]
    weights = softmax(scores)
    dim = len(encoder_states[0])
    context = [0.0] * dim
    for w, h in zip(weights, encoder_states):
        for d in range(dim):
            context[d] += w * h[d]
    return context, weights
```

- **入口检查**：空输入、`d_s != d_h` 都提前报错，并在消息里指出是第几个 encoder 状态出了问题。这对应讲义："`dot` requires `d_s == d_h`. Hard constraint."
- **三步核心**：
  1. `scores`：每个 encoder 位置一个标量 `sᵀh_i`；
  2. `weights = softmax(scores)`：形状 `(T_enc,)`，和为 1；
  3. `context = Σ w_i · h_i`：形状 `(d_h,)`，与单个 encoder 状态相同。
- 讲义 NumPy 版是 `weights @ encoder_states`（`(T,) @ (T, d_h) → (d_h,)`），这里用双重循环手动累加，含义完全相同。
- 对应 Q/K/V：`decoder_state` 是 query，`encoder_states` 既是 key（用来打分）又是 value（用来加权求和）。
- 返回 `(context, weights)` 两个值：`main()` 只用 `weights` 打印，`context` 是 decoder 真正要用的东西。

### 3.3 `matvec` 与 `tanh_vec`：加性打分的积木

```python
def matvec(M, v):
    for i, row in enumerate(M):
        if len(row) != len(v):
            raise ValueError(f"matvec: row {i} length {len(row)} != vector length {len(v)}")
    return [sum(M[i][j] * v[j] for j in range(len(v))) for i in range(len(M))]


def tanh_vec(v):
    return [math.tanh(x) for x in v]
```

- `matvec`：`M` 形状 `(行数, len(v))`，输出长度 = 行数。`W_a` 是 `(d_attn, d_s) = (2, 3)`，所以 `W_a·s` 是 2 维——正是讲义形状表的推导。
- 同样先检查每一行的长度，避免 `range(len(v))` 越界或截断。
- `tanh_vec`：逐元素 tanh，对应公式里的非线性。

### 3.4 Bahdanau 加性 attention

```python
def additive_attention(decoder_state, encoder_states, W_a, U_a, v_a):
    projected_dec = matvec(W_a, decoder_state)
    scores = []
    for h in encoder_states:
        projected_enc = matvec(U_a, h)
        combined = tanh_vec([projected_enc[i] + projected_dec[i] for i in range(len(v_a))])
        scores.append(dot(v_a, combined))
    weights = softmax(scores)
    # ... 上下文计算与 dot_attention 相同
```

- 公式 `e_i = v_aᵀ · tanh(W_a·s + U_a·h_i)`，逐项对应：
  - `projected_dec = W_a·s`：`(d_attn,)`，**循环外只算一次**，因为它对所有位置都一样；
  - `projected_enc = U_a·h_i`：`(d_attn,)`，每个位置一次；
  - `combined = tanh(两者相加)`：`(d_attn,)`；
  - `dot(v_a, combined)`：压成一个标量——讲义强调的"`v_a` 就是把 attention 维向量变成标量的投影"。
- 讲义 NumPy 版把所有位置一次算完：`encoder_states @ U_a.T` 得 `(T_enc, d_attn)`，再与 `(d_attn,)` 的 `projected_dec` 广播相加。这里用 `for h in encoder_states` 逐个算，更直观。
- 🔍 **一个非常值得注意的性质**：`W_a·s` 对所有位置是同一个向量。如果没有 tanh，分数就是"公共常数 + 各位置自己的项"，常数在 softmax 中被抵消，decoder 状态**完全不影响**权重。所以加性 attention 里 decoder 状态只能通过 tanh 的非线性改变位置间的相对分数（测验 Q9(b) 有证明和实测）。
- ⚠️ 简化之处：
  1. 列表推导用 `range(len(v_a))`，默认 `U_a`、`W_a` 的行数等于 `len(v_a)`，但没有显式检查；
  2. 没有检查 `encoder_states` 是否为空（会在 `softmax` 的 `max([])` 处报错）；
  3. `W_a、U_a、v_a` 是手写的固定数值，不是训练出来的。

### 3.5 演示：三个 encoder 状态，权重怎么移动

```python
    H = [
        [1.0, 0.0, 0.2],
        [0.5, 0.5, 0.1],
        [0.1, 0.9, 0.3],
    ]
    positions = ["cat", "sat", "mat"]

    print("=== Luong dot attention ===")
    for name, s in [("close to 'cat'", [0.9, 0.1, 0.2]), ("close to 'mat'", [0.1, 0.9, 0.3]), ("neutral", [0.4, 0.4, 0.2])]:
        _, weights = dot_attention(s, H)
        pretty = {p: round(w, 3) for p, w in zip(positions, weights)}
        print(f"  decoder state {name:20s} -> weights {pretty}")
```

- `H` 三行分别代表 "cat / sat / mat" 位置的 encoder 状态（与讲义 Step 3 相同）。
- 三个 decoder 状态：像 cat、像 mat、中性。`"close to 'mat'"` 的状态 `[0.1, 0.9, 0.3]` 就是 `H` 的第 3 行本身。
- `for name, s in [(...), (...)]`：遍历 `(名字, 向量)` 元组列表并解包。
- `{p: round(w, 3) for p, w in zip(positions, weights)}`：字典推导，把权重和位置名配对，打印更易读。
- `_, weights = ...`：用 `_` 丢弃不需要的上下文向量。
- `{name:20s}`：字符串左对齐、宽 20，让输出成列。

```python
    W_a = [[0.6, 0.3, 0.1], [0.1, 0.5, 0.4]]
    U_a = [[0.5, 0.2, 0.3], [0.2, 0.6, 0.2]]
    v_a = [0.8, 0.6]
```

- `d_attn = 2`，`d_s = d_h = 3`：`W_a`、`U_a` 都是 `2×3`，`v_a` 是 2 维。形状与讲义表格一致。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 列表 | 每次乘加都可见，零依赖 | 慢；生产中用 NumPy/PyTorch，一次矩阵乘法 `QKᵀ` 算完所有分数 |
| 入口处显式检查长度 | 把"形状 bug"变成清晰的异常，拒绝静默截断 | 有少量开销；框架中通常在单元测试里断言形状 |
| softmax 减最大值 | 防止上溢 | 无；但未处理全 `-inf` 的 NaN 情况 |
| `W_a·s` 放在循环外 | 它对所有位置相同，只算一次 | 无，这是正确的优化 |
| 单个 decoder 状态、无 batch | 聚焦一步 attention 的核心 | 实际实现带 batch 维，形状为 `(batch, T_dec, T_enc)` |
| 无 padding mask | 演示数据没有 padding | 真实变长 batch 必须 mask，否则 pad 位置会分走权重（测验 Q10） |
| 加性 attention 用手写参数 | 不需要训练就能跑 | 权重近乎均匀、不体现对齐；真实模型中 `W_a、U_a、v_a` 由反向传播学习 |
| 两个函数重复"加权求和"代码 | 每个函数可独立阅读 | 工程上应抽成 `weighted_sum(weights, values)` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `math.exp` / `math.tanh` | `math.exp(s - m)`、`math.tanh(x)` | 指数与双曲正切；`math.exp` 参数过大抛 `OverflowError` |
| 内置 `max` / `sum` | `max(scores)`、`sum(exps)` | 求最大值、求和 |
| 列表推导式 | `[e / total for e in exps]` | 逐元素构造新列表 |
| 生成器表达式 | `sum(x * y for x, y in zip(a, b))` | 点积，不建中间列表 |
| `zip` | `zip(weights, encoder_states)` | 按位置配对；长度不同会静默截断，所以代码先做检查 |
| `raise ValueError(...)` | `raise ValueError(f"dot: length mismatch ...")` | 主动抛异常，阻止错误数据继续传播 |
| f-string 插值 | `f"encoder_states[{i}] length {len(h)} != ..."` | 在错误信息里放入具体数值，便于定位 |
| 括号内隐式续行 | `raise ValueError(\n f"..." \n)` | 括号里的表达式可以跨行书写 |
| 真值判断 | `if not encoder_states:` | 空列表为 False |
| `enumerate` | `for i, h in enumerate(encoder_states):` | 同时拿下标和元素，用于报错信息 |
| 嵌套列表推导式 | `[sum(M[i][j] * v[j] for j in range(len(v))) for i in range(len(M))]` | 矩阵×向量 |
| 元组解包 + `_` | `_, weights = dot_attention(s, H)` | 丢弃不需要的返回值 |
| 字典推导式 | `{p: round(w, 3) for p, w in zip(positions, weights)}` | 位置名 → 权重 |
| f-string 宽度 | `{name:20s}` | 字符串占 20 格、左对齐 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，仅标准库）的完整输出：

```text
=== Luong dot attention ===
  decoder state close to 'cat'       -> weights {'cat': 0.464, 'sat': 0.305, 'mat': 0.231}
  decoder state close to 'mat'       -> weights {'cat': 0.219, 'sat': 0.317, 'mat': 0.464}
  decoder state neutral              -> weights {'cat': 0.333, 'sat': 0.327, 'mat': 0.34}

=== Bahdanau additive attention (d_attn=2) ===
  decoder state close to 'cat'       -> weights {'cat': 0.322, 'sat': 0.33, 'mat': 0.348}
  decoder state close to 'mat'       -> weights {'cat': 0.338, 'sat': 0.329, 'mat': 0.333}
```

逐行解读：

- **dot / close to 'cat'**：分数 `[0.94, 0.52, 0.24]`，softmax 后 `cat` 最高（0.464），与讲义 Step 3 给出的 `[0.464 0.305 0.231]` 完全一致。
- **dot / close to 'mat'**：分数 `[0.16, 0.53, 0.91]`，注意力移到 `mat`（0.464）——讲义说的"move the decoder state closer to the third encoder state and watch the weights shift"。
- **dot / neutral**：分数 `[0.44, 0.42, 0.46]` 彼此接近，权重几乎均匀（0.333 / 0.327 / 0.34）。
- 注意最大权重也只有 0.464：这些向量的点积差距不大，softmax 给出的是"软"分布，而不是 one-hot。把 decoder 状态放大 10 倍，最大权重会升到 0.98 左右（测验 Q8(c)），这正是 Transformer 要除以 `√d` 控制尺度的原因。
- **additive / 两个状态**：权重都在 0.32–0.35 之间，近乎均匀；而且"close to 'cat'"的状态反而给 `mat` 最高权重，"close to 'mat'"的状态反而给 `cat` 最高。原因是这些参数没有经过训练：`W_a·s` 对所有位置相同，位置间的差异主要来自 `U_a·h_i`，而 `v_a` 全为正，于是 `U_a·h` 较大的位置得分更高——与 decoder 状态"像谁"关系不大。**加性 attention 的对齐能力是学出来的**，dot attention 的点积则天然就是相似度。代码没有对这一点做说明，读者需要自己意识到这里的数字不代表"对齐"。

---

## 7. 动手改一改

1. **温度实验**：给 `dot_attention` 加一个参数 `temperature`，分数先除以它再 softmax，分别取 0.1、1、10，观察权重从 one-hot 到均匀的变化。
2. **padding mask**：实现 `masked_dot_attention`，在 `H` 后补两行零向量，比较 mask 与不 mask 的权重（参考测验 Q10）。
3. **Luong general**：实现 `general_attention(s, H, W)`，用一个 `3×6` 的 `W` 处理 6 维（模拟双向 encoder）的 encoder 状态；验证 `W` 为单位矩阵时与 `dot_attention` 一致。
4. **去掉 tanh**：把 `additive_attention` 里的 `tanh_vec` 换成恒等函数，确认两个 decoder 状态得到完全相同的权重，并解释原因。
5. **手调加性参数**：尝试设计 `W_a、U_a、v_a`（可以增加 `d_attn`），让"close to 'cat'"的状态在加性 attention 下也把最高权重给 `cat`。体会"学习参数"在做什么。
6. **批量化**：用 NumPy 改写为支持 `(batch, T_dec, d_s)` 与 `(batch, T_enc, d_h)` 的版本，并按讲义技能卡写断言：`weights.shape == (batch, T_dec, T_enc)`、`weights.sum(-1) ≈ 1`。

---

## 8. 常见坑

- **维度不一致却不报错**：`zip` 静默截断、NumPy 静默广播都会让形状 bug 变成"精度悄悄下降"。本代码用显式检查规避了前者。
- **softmax 归一化的维度错了**：批量实现中应在 encoder 位置维（最后一维 `T_enc`）上归一化，而不是 batch 维或特征维。
- **忘了 padding mask**：pad 位置分数为 0 也会分走权重（本例补两行零向量就会分走约 27%）。
- **全 mask 导致 NaN**：所有分数为 `-inf` 时 softmax 产生 `nan`，会沿反向传播污染整个模型。
- **混用 `s_{t-1}` 与 `s_t`**：Bahdanau 和 Luong 的约定不同，选一篇论文的约定并坚持。
- **把注意力权重当解释**：尤其是未训练或手写参数的 attention，权重几乎没有语义；即使训练好了，也要做消融/反事实检验。
