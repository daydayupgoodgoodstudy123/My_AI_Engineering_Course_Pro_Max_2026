# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 03 节 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`），无需 NumPy / PyTorch

---

## 1. 这份代码在考察什么

这份代码只实现 Q-Former 中**最关键的一步**：一组固定的 learnable query 对冻结 ViT 的 patch token 做 cross-attention，再线性投影到 LLM 的维度。具体考察：

1. **Cross-attention 的数据来源**：Q 来自 query，K/V 来自图像 patch；输出个数等于 query 数，与 patch 数无关——这就是"压缩"。
2. **注意力权重的可解释性**：打印每个 query 的 top-5 patch 和注意力熵，看 query 是"盯着少数 patch"还是"平均地看"。
3. **投影到 LLM 维度**：最后一个线性层把 query 输出变成 LLM 能接收的 token。

讲义中 Q-Former 的其它部分——query 之间的 self-attention、FFN、12 层堆叠、text 路径、ITC/ITM/ITG 三种损失、与 LLM 的拼接和训练——都**没有**实现。

> 一句话：**用两层嵌套循环看清"8 个 query 如何从 64 个 patch 中各取所需，最后变成 8 个 LLM token"**。同时要注意：代码规模和讲义不一致，两个 DEMO 的对比结论也被初始化尺度带偏了（见 3.6、3.7）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `NUM_PATCH`、`PATCH_DIM`、`NUM_QUERY`、`QUERY_DIM`、`LLM_DIM` | 模块常量 | 64、16、8、16、24 | 规模（讲义为 256、128、32、128、512） |
| `rng = random.Random(42)` | 模块级随机数生成器 | 所有随机向量共用，保证可复现 | — |
| `vec` / `mat` | 函数 | 生成 `N(0,1)` 向量 / 矩阵（行列表） | 参数初始化 |
| `matmul_vec` | 函数 | `M · v`（矩阵乘向量） | 线性层 |
| `dot` / `softmax` | 函数 | 点积 / 减最大值的稳定 softmax | 注意力基本运算 |
| `make_patches` | 函数 | 64 个 16 维"patch token" | 冻结 ViT 的输出 |
| `make_queries` | 函数 | 8 个 16 维 query | Learnable queries |
| `cross_attention` | 函数 | Q/K/V 投影 → 缩放点积 → softmax → 加权求和 | Cross-attention |
| `linear_project` | 函数 | 每个输出向量乘 `W_out` | 投影到 LLM 维度 |
| `top_patches_per_query` | 函数 | 每行权重排序取前 k | 注意力可视化 |
| `summarize_attention` | 函数 | 打印熵与 top-5 | 注意力集中程度 |
| `demo_untrained` | 函数 | 随机 query + 随机 W | "未训练"的桥 |
| `demo_biased` | 函数 | query = 指定 patch 的副本，W = 单位矩阵 | "对齐后"的桥（模拟） |
| `main` | 函数 | 运行两个 DEMO 并打印要点 | — |

数据流：`make_patches`（冻结 ViT 输出 `64 × 16`）+ `make_queries`（`8 × 16`）→ `cross_attention`（`attn: 8 × 64`，`attended: 8 × 16`）→ `linear_project`（`8 × 24`）→ "准备送入 LLM"。

---

## 3. 逐段精讲

### 3.1 常量与随机数生成器

```python
NUM_PATCH = 64
PATCH_DIM = 16
NUM_QUERY = 8
QUERY_DIM = 16
LLM_DIM = 24

rng = random.Random(42)
```

- 规模被缩小为讲义的约 1/4～1/20，以便纯 Python 循环瞬间跑完。
- ⚠️ 文字说明没有同步：模块 docstring 写"256 patch tokens / 32 learnable query vectors"，`make_queries` 的 docstring 写"32 learnable query vectors, dim 16"，TAKEAWAYS 打印"(32 queries, 256 patches)"，讲义 Use It 写"256 个 dim 128 的 patch、32 个 query、投影到 512"。实际运行是 8 × 64、投影到 24。
- `rng` 是**模块级**的单一生成器，所有调用依次消耗它。这意味着 `demo_biased` 里的 `make_patches()` 生成的 patch 取决于 `demo_untrained` 之前消耗了多少随机数——单独调用 `demo_biased()` 会得到不同的结果。

### 3.2 线性代数小工具

```python
def vec(n):
    return [rng.gauss(0, 1) for _ in range(n)]

def mat(rows, cols):
    return [vec(cols) for _ in range(rows)]

def matmul_vec(M, v):
    return [sum(r * x for r, x in zip(row, v)) for row in M]
```

- 矩阵用"行的列表"表示，`mat(rows, cols)` 的形状是 `(rows, cols)`。
- `matmul_vec(M, v)` 计算 `M · v`：输出长度 = `M` 的行数。所以 `W_k = mat(QUERY_DIM, PATCH_DIM)` 把 16 维 patch 映射到 16 维 key；`W_out = mat(LLM_DIM, QUERY_DIM)` 把 16 维映射到 24 维。这与 PyTorch `nn.Linear` 的权重形状 `(out, in)` 一致。
- ⚠️ 所有权重都是 `N(0, 1)`，**没有**按 `1/√fan_in` 缩放。这是本文件最重要的"隐藏变量"，直接导致 3.6 节的注意力饱和和输出数值很大。

### 3.3 稳定 softmax

```python
def softmax(xs):
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    z = sum(exps)
    return [e / z for e in exps]
```

- 先减最大值再 `exp`，数学上不变，数值上避免溢出。本文件中 logit 可以达到几十（见 3.6），不减最大值就有溢出风险。

### 3.4 Cross-attention 核心

```python
def cross_attention(queries, patches, W_q, W_k, W_v):
    Q = [matmul_vec(W_q, q) for q in queries]
    K = [matmul_vec(W_k, p) for p in patches]
    V = [matmul_vec(W_v, p) for p in patches]
    d = len(Q[0])
    scale = 1.0 / math.sqrt(d)

    attn_weights = []
    out = []
    for q in Q:
        logits = [dot(q, k) * scale for k in K]
        weights = softmax(logits)
        attn_weights.append(weights)
        mixed = [0.0] * d
        for i, w in enumerate(weights):
            for j in range(d):
                mixed[j] += w * V[i][j]
        out.append(mixed)
    return out, attn_weights
```

形状追踪（代码规模 / 讲义规模）：

| 步骤 | 代码规模 | 讲义规模 |
|------|---------|---------|
| `queries` | `(8, 16)` | `(32, 128)` |
| `patches` | `(64, 16)` | `(256, 128)` |
| `Q = W_q · q` | `(8, 16)` | `(32, 128)` |
| `K, V = W_k · p, W_v · p` | `(64, 16)` | `(256, 128)` |
| 每个 q 的 `logits` | 长度 64 | 长度 256 |
| `attn_weights` | `(8, 64)`，每行和为 1 | `(32, 256)` |
| `mixed = Σ_i w_i · V[i]` | `(8, 16)` | `(32, 128)` |

- **Q 只来自 query，K/V 只来自 patch**——这正是讲义 Key Terms 中"Q from here, K/V from there"的含义。
- 输出个数 = query 数（8），不管有多少 patch。把 patch 数从 64 改为 1024，输出仍然是 8 个向量，只是每个 query 要在更多 patch 上做 softmax。
- `scale = 1/√d` 是缩放点积注意力的标准做法，用来抵消点积方差随维度增长。
- 内层 `mixed[j] += w * V[i][j]` 就是矩阵乘 `weights @ V` 的手写版，每个输出是所有 value 的凸组合。
- 只有单头，没有输出投影 `W_o`，没有残差、LayerNorm、FFN。真实 Q-Former 每层是"self-attn → cross-attn → FFN"，并且是多头。

### 3.5 投影与注意力摘要

```python
def linear_project(xs, W):
    return [matmul_vec(W, x) for x in xs]

def summarize_attention(attn):
    ...
    for weights in attn:
        e = -sum(w * math.log(w + 1e-12) for w in weights)
        entropies.append(e)
    max_e = math.log(NUM_PATCH)
```

- `linear_project` 对应讲义 Stage 2 的"Project the 32 query outputs to the LLM's embedding dim via a small linear layer"。
- **注意力熵** `H = -Σ w log w`：均匀分布时最大，为 `ln 64 ≈ 4.159`；one-hot 时为 0。`+ 1e-12` 防止 `log(0)`。熵是衡量"注意力是否集中"最简单的标量指标。
- `sorted(range(len(weights)), key=lambda i: -weights[i])[:k]`：按权重降序排列下标，取前 k 个——一种不依赖 NumPy 的 `argsort`。

### 3.6 DEMO 1：未训练的桥

```python
    patches = make_patches()
    queries = make_queries()
    W_q = mat(QUERY_DIM, QUERY_DIM)
    W_k = mat(QUERY_DIM, PATCH_DIM)
    W_v = mat(QUERY_DIM, PATCH_DIM)
    attended, attn = cross_attention(queries, patches, W_q, W_k, W_v)
```

- 直觉上"未训练 = 注意力弥散"，但实际输出的平均熵只有 **0.199**（均匀分布为 4.159），8 个 query 中 6 个的 top-1 权重 ≥ 0.99。
- 原因：Q、K 的每个分量是 16 项 `N(0,1)·N(0,1)` 之和，方差约 16；Q·K 再对 16 项求和，方差约 4096；乘以 1/4 后标准差约 16。实测 512 个 logit 的标准差为 **13.2**。softmax 输入相差几十，输出必然是 one-hot。
- 另一个现象：query 1 和 query 6 都盯着 p57，query 3 和 query 5 都盯着 p13——多个 query 的"分工"重复了。真实训练中也会担心 query 塌缩到相同的 patch 上，ITC/ITM/ITG 的多样化目标在一定程度上抑制了这种情况。
- 投影后的数值（如 −35.66）很大，同样是 `N(0,1)` 初始化在两层连乘后放大的结果。

### 3.7 DEMO 2：用 patch 副本作为 query

```python
    favored = [5, 17, 33, 48, 60, 2, 11, 27]
    queries = [list(patches[i]) for i in favored]
    W_q = [[1.0 if i == j else 0.0 for j in range(QUERY_DIM)]
           for i in range(QUERY_DIM)]
    ...
```

- `W_q = W_k = W_v = I`（单位矩阵），所以 logit = `p_i · p_j / 4`。query i 是 patch `favored[i]` 的副本，它与自身的点积是 `‖p‖²`（期望 16），与其它 patch 的点积均值 0、标准差约 4。缩放后自身约 +4，其余标准差约 1——自身几乎总是最大，于是 8 个都打印 "YES"。
- ⚠️ docstring 说这个 DEMO 展示"attention concentrates (lower entropy)"，但按相同随机序列复现计算，它的 8 个熵为 3.423、3.604、3.283、2.197、2.931、2.607、0.908、3.112，平均 **2.758**，远**高于** DEMO 1 的 0.199。"对齐后"的注意力反而更弥散，因为单位矩阵没有放大作用，而 DEMO 1 的随机 `N(0,1)` 矩阵放大了 logit。两个 DEMO 的对比结论被初始化尺度主导了（测验 Q10）。
- 权重最高的 query 6（0.857）对应的 patch 11 范数平方为 26.4，是这 8 个中最大的——权重高低主要取决于 patch 本身的范数，而不是"学到了什么"。
- `list(patches[i])` 创建副本，避免 query 与 patch 共享同一个列表对象。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 嵌套循环 | 每个乘加都可见 | 极慢；生产用批量矩阵乘法 `softmax(QKᵀ/√d)V` |
| 规模缩小到 8 × 64 × 16 | 运行瞬间完成 | 文档和 TAKEAWAYS 未同步，读者容易混淆 |
| 单个 cross-attention | 聚焦"query 读 patch"这一核心机制 | 缺 self-attn、FFN、多层、多头；真实 Q-Former 12 层 |
| 权重 `N(0, 1)` | 写法最简单 | logit 标准差约 13，softmax 饱和；生产用 `N(0, 1/fan_in)`、Xavier 等初始化，或从 BERT-base 初始化（讲义练习 4） |
| 用 patch 副本 + 单位矩阵模拟"训练后" | 无需写训练循环 | 结论被初始化尺度带偏，熵反而更高；应在同一尺度下对比或真正训练 |
| 只投影、不接 LLM | 演示"变成 LLM token"即止 | 没有 Stage 1 的三种损失和 Stage 2 的 LM loss |
| 打印熵和 top-5 | 低成本可解释性 | 熵只是粗粒度指标；真实分析会把注意力映射回图像网格做热力图 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 延迟求值类型注解，可写 `list[list[float]]` |
| 模块级常量 | `NUM_PATCH = 64` | 全大写命名约定表示常量（Python 不强制） |
| 模块级共享对象 | `rng = random.Random(42)` | 所有函数共用一个生成器；调用顺序会影响结果 |
| 复杂类型注解 | `tuple[list[list[float]], list[list[float]]]` | 返回"两个矩阵组成的元组" |
| 多行 docstring | `"""Scaled dot-product cross-attention. ..."""` | 函数说明；注意要与实现同步 |
| 列表推导式 | `[vec(cols) for _ in range(rows)]`、`[matmul_vec(W_q, q) for q in queries]` | 构造矩阵、批量变换 |
| 嵌套推导式 + 条件表达式 | `[[1.0 if i == j else 0.0 for j in range(D)] for i in range(D)]` | 构造单位矩阵 |
| 生成器表达式 | `sum(r * x for r, x in zip(row, v))` | 点积 |
| `enumerate` | `for i, w in enumerate(weights)` | 同时取下标与值 |
| 元组返回与解包 | `attended, attn = cross_attention(...)`、`_, attn = ...` | `_` 表示忽略某个返回值 |
| `sorted` + `key` + 切片 | `sorted(range(n), key=lambda i: -weights[i])[:k]` | 用负号实现降序，取前 k 个 |
| `max` + `key` | `max(range(len(weights)), key=lambda k: weights[k])` | argmax 的纯 Python 写法 |
| `zip` 并行迭代 | `for i, (idxs, e) in enumerate(zip(top, entropies))` | 元组嵌套解包 |
| `str.join` + 生成器 | `", ".join(f"p{x:02d}({attn[i][x]:.3f})" for x in idxs[:5])` | 拼接格式化字符串 |
| f-string 格式符 | `{x:02d}`（补零到 2 位）、`{e:.3f}`、`{weights[top]:.3f}` | 宽度、补零、小数位 |
| `list(...)` 复制 | `list(patches[i])` | 浅复制，避免共享引用 |
| `round` | `[round(x, 2) for x in projected[0][:8]]` | 打印前截断 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3，瞬间完成）：

```text
DEMO: 8 queries attending over 64 patches
attention-weight summary (softmax over 64 patches)
  query 0: entropy 0.000/4.159, top-5 p46(1.000), p52(0.000), ...
  query 1: entropy 0.016/4.159, top-5 p57(0.998), p50(0.002), ...
  query 2: entropy 0.063/4.159, top-5 p06(0.990), p30(0.006), ...
  query 3: entropy 0.005/4.159, top-5 p13(0.999), p58(0.001), ...
  query 4: entropy 0.027/4.159, top-5 p20(0.996), p30(0.004), ...
  query 5: entropy 0.733/4.159, top-5 p13(0.536), p33(0.456), ...
  query 6: entropy 0.000/4.159, top-5 p57(1.000), p13(0.000), ...
  query 7: entropy 0.747/4.159, top-5 p19(0.542), p62(0.447), ...
  mean entropy: 0.199  (uniform baseline: 4.159)

output: 8 tokens of dim 24 -> ready for LLM
first token (trimmed): [-1.81, -35.66, -19.17, -32.65, -1.97, -15.36, -28.89, -29.87]

DEMO: queries initialized from specific patches -> concentration
  query_i should attend highest to patch[favored[i]]:
    query 0: top patch 5 (favored 5) weight 0.199 (YES)
    query 1: top patch 17 (favored 17) weight 0.155 (YES)
    query 2: top patch 33 (favored 33) weight 0.259 (YES)
    query 3: top patch 48 (favored 48) weight 0.603 (YES)
    query 4: top patch 60 (favored 60) weight 0.365 (YES)
    query 5: top patch 2 (favored 2) weight 0.482 (YES)
    query 6: top patch 11 (favored 11) weight 0.857 (YES)
    query 7: top patch 27 (favored 27) weight 0.309 (YES)
```

逐项解读：

- **DEMO 1 熵接近 0**：不是"学到了"，而是 `N(0,1)` 权重让 logit 标准差约 13，softmax 饱和成 one-hot。query 5 和 query 7 是少数"两个 patch 平分"的情况，熵约 0.73 ≈ ln 2（0.693），恰好对应两项各约 0.5。
- **重复关注**：query 1 / query 6 都选 p57，query 3 / query 5 都选 p13。8 个 query 只覆盖了 6 个不同的主 patch。
- **投影输出数值很大**（−35.66）：两次 `N(0,1)` 线性变换连乘的结果，真实网络会用缩放初始化和 LayerNorm 控制尺度。
- **DEMO 2 全部 "YES"，但权重只有 0.155～0.857**：自身点积约为 ‖p‖²，与其它 patch 的点积是零均值噪声，所以自身最大几乎是必然的；权重高低主要由 patch 范数决定（patch 11 的 ‖p‖² 为 26.4，权重最高）。平均熵 2.758，高于 DEMO 1 的 0.199，与 docstring"concentration"的说法相反。
- 用 `N(0, 1/fan_in)` 缩放初始化重跑同样规模的随机 cross-attention（另取随机种子），平均熵约 3.47、最大权重约 0.70——这才是"未训练时注意力弥散"的典型样子。

---

## 7. 动手改一改

1. **同步规模**：把常量改成讲义的 `NUM_PATCH = 256, PATCH_DIM = 128, NUM_QUERY = 32, QUERY_DIM = 128, LLM_DIM = 512`，修正所有 docstring，记录运行时间（纯 Python 会明显变慢，体会为什么要用矩阵运算）。
2. **修正初始化**：把 `vec` 改为 `rng.gauss(0, 1 / math.sqrt(fan_in))`（需要给 `mat` 增加 fan_in 参数），重跑两个 DEMO，比较平均熵。现在"未训练"与"对齐后"的对比是否符合直觉？
3. **补全一层 Q-Former**：在 cross-attention 之前加 query 之间的 self-attention，之后加 FFN，每个子层带残差（参考测验 Q11 的 NumPy 实现）。
4. **多头**：把 16 维拆成 4 个头、每头 4 维，分别做注意力再拼接，打印每个头的平均熵。
5. **（讲义练习 5）**写一个函数，输入视频时长、FPS、每帧 token 数、上下文窗口，输出是否放得下以及占用比例；分别计算 Q-Former（32）与 MLP（576）。
6. **进阶**：给 query 写一个最小训练循环——目标是让 query i 的输出逼近 `V[favored[i]]`（MSE），手写对 query 的梯度或改用 PyTorch autograd，每 10 步打印平均熵，观察熵随训练下降。

---

## 8. 常见坑

- **初始化不缩放**：`N(0,1)` 权重让注意力在训练前就饱和，梯度几乎为 0，训练会很难启动。
- **把 Q 和 K/V 的来源弄反**：若 Q 来自 patch、K/V 来自 query，输出会变成 256 个而不是 32 个，压缩就失效了。
- **softmax 沿错误的维度**：应当对每个 query 在**全部 patch 上**归一化（每行和为 1）。
- **用"top-1 命中"评估注意力**：本文件 DEMO 2 的"全部 YES"几乎是构造必然，不能说明注意力质量；要结合熵、热力图和下游任务指标。
- **共享全局随机数生成器**：函数调用顺序会改变结果，单独调试某个 DEMO 时无法复现完整运行的数字。
- **文档与代码规模不一致**：读输出时以代码常量为准（8 × 64），不要按 docstring 的 32 × 256 去理解。
