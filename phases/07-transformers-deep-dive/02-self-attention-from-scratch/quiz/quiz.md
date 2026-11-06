# 测验 · Self-Attention 从头开始（Self-Attention from Scratch）

> **阶段 07 · Transformers 深入 · 第 02 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/self_attention.py](../code/self_attention.py) ｜ 代码讲解：[code/self_attention.讲解.md](../code/self_attention.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 软数据库查找 | 传统查找是"精确匹配返回一个值"，attention 是"query 与所有 key 算相似度，返回所有 value 的加权混合" |
| 2 | Q / K / V 三个投影 | 同一个输入 X 分别乘 `Wq (d, dk)`、`Wk (d, dk)`、`Wv (d, dv)`：Q 表示"我在找什么"，K 表示"我包含什么"，V 表示"被选中时我提供什么" |
| 3 | 分数矩阵 `QKᵀ` | 形状 `(n, n)`，第 i 行是第 i 个 token 对所有 token 的打分；这是 O(n²) 复杂度的来源 |
| 4 | 缩放 `1/√dk` | q、k 各分量独立且方差为 1 时，点积方差约为 dk；除以 √dk 把方差拉回 1，防止 softmax 饱和、梯度消失 |
| 5 | 数值稳定的 softmax | softmax 对每行加同一常数不变，先减去行最大值，指数项都 ≤ 1，避免 `exp` 上溢 |
| 6 | 加权求和 | `output_i = Σ_j w_ij · v_j`，每行权重非负且和为 1，输出是 value 的凸组合，形状 `(n, dv)` |
| 7 | 一行公式 | `Attention(Q, K, V) = softmax(QKᵀ / √dk) · V` |
| 8 | 置换等变 | 没有位置编码时，打乱输入行的顺序，输出行按同样方式被打乱——self-attention 本身不知道顺序 |
| 9 | 因果 mask | softmax 前把未来位置的分数设为 `-inf`，权重变 0，其余位置按原相对比例重新归一化；decoder 自回归生成靠它 |
| 10 | 多头 attention | 每头维度 `dk = d_model / h`，各头独立算 attention，拼接后乘 `Wo`；能同时关注不同类型的关系 |

### 核心技能（能动手做到）

- [ ] 只用 NumPy 实现数值稳定的 `softmax` 和 `scaled_dot_product_attention`，并验证每行权重和为 1
- [ ] 说出 `self_attention.py` 主程序中每个张量的形状：`X (6,16)` → `Q, K, V (6,8)` → `scores (6,6)` → `output (6,8)`
- [ ] 给 `scaled_dot_product_attention` 加 `mask` 参数，实现因果 mask，并验证权重矩阵上三角全为 0
- [ ] 用随机向量做实验，验证点积方差 ≈ dk、缩放后 ≈ 1
- [ ] 解释为什么运行结果中 "Head 1" 的权重与单头 `SelfAttention` 完全一样，并修改种子方案
- [ ] 写一段代码验证 self-attention 的置换等变性
- [ ] 读懂 ASCII heatmap 的映射规则（`level = int(w * 4 / w_max)`）

---

## 二、基础自测（选择题）

**Q1.** 设 q、k 都是 64 维向量，各分量独立、均值 0、方差 1。点积 `q·k` 的方差约为：

- A. 1
- B. 8
- C. 64
- D. 4096

**Q2.** 本节主程序中 `X` 形状为 `(6, 16)`，`Wq`、`Wk`、`Wv` 形状均为 `(16, 8)`。`scores` 和 `output` 的形状分别是：

- A. `(6, 6)` 和 `(6, 8)`
- B. `(8, 8)` 和 `(6, 8)`
- C. `(6, 6)` 和 `(6, 16)`
- D. `(16, 16)` 和 `(6, 16)`

**Q3.** 代码中 `softmax` 先做 `x - np.max(x, axis=-1, keepdims=True)`，主要目的是：

- A. 让输出分布更尖锐
- B. softmax 对整行加减同一常数结果不变；减去最大值后所有指数项 ≤ 1，避免 `exp` 上溢
- C. 让梯度变大，加快训练
- D. 保证输出之和为 1

**Q4.** 用"数据库查找"类比 attention，下列说法正确的是：

- A. Q 与 V 做点积得到分数，再对 K 加权求和
- B. Q 与 K 做点积得到分数，softmax 后对 V 加权求和
- C. K 与 V 做点积得到分数，再对 Q 加权求和
- D. Q、K、V 两两做点积，三个结果取平均

**Q5.** 在 softmax 之前把第 i 行中 `j > i` 的分数设为 `-inf`（因果 mask），第 i 行的权重会：

- A. 未来位置变为 0，其余位置按原来的相对比例重新归一化，和仍为 1
- B. 未来位置变为负数，整行之和小于 1
- C. 所有未被 mask 的位置都变成 `1/(i+1)`
- D. 只影响 V，不影响权重

**Q6.** 不加位置编码时，把输入 X 的行顺序打乱（例如把第 0 行和第 3 行交换），self-attention 的输出会：

- A. 完全不变
- B. 输出的行按同样方式交换（置换等变）
- C. 变成和原来无关的随机结果
- D. 形状不匹配而报错

**Q7.** 多头 attention，`d_model = 512`，8 个头。每个头的 Q/K/V 维度以及与"单头 512 维"相比的投影计算量分别是：

- A. 512；计算量是单头的 8 倍
- B. 64；投影矩阵的总参数量与单头 512 维基本相同
- C. 4096；计算量是单头的 1/8
- D. 8；每个头只负责一个维度

---

## 三、动手 / 代码题

**Q8.** 运行 `self_attention.py` 会发现，"MULTI-HEAD SELF-ATTENTION" 部分 **Head 1** 的权重矩阵与前面单头 `SelfAttention` 的矩阵逐位相同。结合下面的代码解释原因，并给出修改建议。

```python
# 主程序
d_model = 16
dk = 8
dv = 8
attn = SelfAttention(d_model, dk, dv, seed=42)

# MultiHeadSelfAttention.__init__
self.dk = d_model // n_heads
self.dv = d_model // n_heads
self.heads = [
    SelfAttention(d_model, self.dk, self.dv, seed=seed + i)
    for i in range(n_heads)
]
# 主程序：mha = MultiHeadSelfAttention(d_model, n_heads, seed=42)，n_heads = 2
```

**Q9.** 完成讲义练习 1：给 `scaled_dot_product_attention` 加一个可选参数 `mask`（布尔矩阵，`True` 表示允许关注），被屏蔽的位置在 softmax 前设为 `-inf`。然后回答：已知不加 mask 时 "cat" 行（第 2 行）的前两个权重是 `0.130, 0.165`，加因果 mask 后这一行会变成多少？最后一行 "mat" 会变吗？

**Q10.** 预测下面代码的输出（不需要精确到小数点后很多位，说明是正常概率、0/1 还是 `nan` 即可），并解释为什么本节演示里 "(Numerically stable - no overflow)" 这句话在 float64 下其实"证明力不足"。

```python
import numpy as np

def naive_softmax(x):
    e = np.exp(x)
    return e / e.sum()

print(naive_softmax(np.array([100.0, 200.0, 300.0])))                     # (a) float64
print(naive_softmax(np.array([100.0, 200.0, 300.0], dtype=np.float32)))   # (b) float32
print(naive_softmax(np.array([1000.0, 2000.0, 3000.0])))                  # (c) float64
print(softmax(np.array([1000.0, 2000.0, 3000.0])))                        # (d) 本节的 softmax
```

---

## 四、面试高频题

**Q11.**（基础必考）请手推 scaled dot-product attention 的完整流程：输入是什么、每一步做什么、各张量形状、时间与空间复杂度。

**Q12.**（原理深挖）为什么要除以 `√dk`？为什么不是除以 `dk`？不除会怎样？

**Q13.**（原理深挖）为什么要用三个不同的投影矩阵得到 Q、K、V？如果让 Q 和 K 共用一个投影（`Wq = Wk`），会有什么问题？

**Q14.**（追问型）self-attention、cross-attention 与 Bahdanau attention 有什么区别？分别出现在模型的什么位置？

**Q15.**（工程实践）在一个 batch 里同时存在 padding 和因果约束，mask 应该怎么实现？为什么用 `-inf`（或极大负数）而不是把权重乘 0？如果某一行被全部 mask 掉会发生什么？

---

## 五、参考答案与解析

### Q1 — 答案：C

`q·k = Σ_{i=1}^{64} q_i k_i`，每一项 `q_i k_i` 均值 0、方差 `1×1 = 1`，64 个独立项相加方差为 64，标准差为 8。实测（2 万个样本）：dk = 4、64、512 时方差分别约为 4.0、64.5、508，除以 √dk 后都约为 1.0。B 是标准差，容易混淆；D 是 dk²。

### Q2 — 答案：A

`Q = X @ Wq` → `(6,16)@(16,8) = (6,8)`；`K` 同理 `(6,8)`；`scores = Q @ K.T` → `(6,8)@(8,6) = (6,6)`；`output = weights @ V` → `(6,6)@(6,8) = (6,8)`。注意单头输出维度是 `dv = 8` 而不是 `d_model = 16`——要回到 16 维需要多头拼接或额外的输出投影（代码中 `MultiHeadSelfAttention` 的输出就是 `(6,16)`）。

### Q3 — 答案：B

`softmax(x - c) = softmax(x)`，因为分子分母同乘 `e^{-c}`。减去最大值后最大的指数项是 `e⁰ = 1`，其余都在 (0, 1]，不会溢出；分母至少为 1，也不会出现除以 0。D 是 softmax 本来就有的性质，与减最大值无关；A、C 是"温度"调节的效果，而减常数不改变分布。

### Q4 — 答案：B

Query 去和每个 Key 比对（点积 = 相似度），softmax 把相似度变成权重，再用权重混合 Value。K 负责"被匹配"，V 负责"被取走的内容"，二者解耦：一个 token "长得像什么"和"它能提供什么信息"可以不同。

### Q5 — 答案：A

`e^{-inf} = 0`，被 mask 的位置权重为 0；softmax 的分母只剩允许位置的指数和，所以剩余权重按原来的相对比例放大，和仍为 1。B 错：softmax 输出永远非负；C 错：只有在原始分数都相等时才会均匀；D 错：mask 作用于分数/权重。

### Q6 — 答案：B

设置换矩阵为 P，`Q' = PXWq = PQ`，`K' = PK`，`V' = PV`，于是 `softmax(PQKᵀPᵀ/√dk) = P·softmax(QKᵀ/√dk)·Pᵀ`，输出 `= P·W·Pᵀ·P·V = P·(W·V)`。即输出被同样地置换。实测 `np.allclose(o1[perm], o2)` 为 `True`。这说明 self-attention 天生没有顺序概念，"cat sat on mat" 和 "mat on sat cat" 对它来说只是同一组 token 的不同排列——所以需要第 04 节的位置编码。

### Q7 — 答案：B

`dk = 512 / 8 = 64`。8 个头的 Wq 合起来是 8 × (512×64) = 512×512，与单头 512 维的投影参数量相同，总 FLOPs 也基本相当；多头的收益在于"在 8 个不同子空间里各自算一份 attention 分布"，而不是增加计算。A、C 混淆了维度切分的方向；D 把头数当成了每头维度。

### Q8 — 参考答案

**原因**：`n_heads = 2` 时每个头的 `dk = dv = 16 // 2 = 8`，正好等于主程序里单头的 `dk = dv = 8`；而第 0 个头的种子是 `seed + 0 = 42`，与单头 `SelfAttention(..., seed=42)` 完全相同。`SelfAttention.__init__` 用 `np.random.default_rng(seed)` 按同样的顺序、同样的形状抽取 `Wq`、`Wk`、`Wv`，所以两者的权重逐元素相同（实测 `np.allclose(mha.heads[0].Wq, attn.Wq)` 为 `True`），输入 X 又是同一个，权重矩阵自然一样。

**这不是数学错误，但会误导读者**以为"多头的第一个头就是单头 attention"。修改建议：

```python
# 方案 1：让多头的种子与单头错开
mha = MultiHeadSelfAttention(d_model, n_heads, seed=100)

# 方案 2：在类内部用一个 rng 依次生成所有头的权重（更接近真实实现）
rng = np.random.default_rng(seed)
self.Wq = rng.normal(0, scale, (d_model, d_model))   # 一次生成，再按列切成 h 份
```

真实框架（如 PyTorch `nn.MultiheadAttention`）就是用一个 `(d_model, d_model)` 的大矩阵完成所有头的投影，再 reshape 成 `(n, h, dk)`。第 03 节会这样实现。

### Q9 — 参考答案

```python
def scaled_dot_product_attention(Q, K, V, mask=None):
    dk = Q.shape[-1]
    scores = Q @ K.T / np.sqrt(dk)
    if mask is not None:
        scores = np.where(mask, scores, -np.inf)   # False 的位置不允许关注
    weights = softmax(scores)
    output = weights @ V
    return output, weights


n = 6
causal = np.tril(np.ones((n, n), dtype=bool))      # 下三角（含对角线）为 True
attn = SelfAttention(16, 8, 8, seed=42)
Q, K, V = X @ attn.Wq, X @ attn.Wk, X @ attn.Wv
out, w = scaled_dot_product_attention(Q, K, V, mask=causal)
print(w.round(3))
```

实测输出的前两行和最后一行：

```text
[[1.    0.    0.    0.    0.    0.   ]
 [0.441 0.559 0.    0.    0.    0.   ]
 ...
 [0.18  0.186 0.102 0.296 0.089 0.148]]
```

- 第 1 行 "The" 只能看自己，权重必为 1。
- "cat" 行只剩前两个位置，按比例重新归一化：`0.130 / (0.130 + 0.165) ≈ 0.441`，`0.165 / 0.295 ≈ 0.559`。
- 最后一行 "mat" 本来就能看到所有位置，**不变**。
- 每一行的 `max` 一定是有限值（对角线永远允许），所以 `softmax` 里的减最大值不会出现 `-inf - (-inf) = nan`。

### Q10 — 参考答案

| 输入 | 输出 | 原因 |
|------|------|------|
| (a) float64 `[100,200,300]` | 约 `[1.4e-87, 3.7e-44, 1.0]`，正常 | float64 的 `exp` 上限约在 `x ≈ 709`，`e³⁰⁰ ≈ 1.9e130` 没有溢出 |
| (b) float32 `[100,200,300]` | `[nan, nan, nan]`（伴随溢出警告） | float32 的上限约 `3.4e38`，`e¹⁰⁰ ≈ 2.7e43` 已经是 `inf`，`inf / inf = nan` |
| (c) float64 `[1000,2000,3000]` | `[nan, nan, nan]` | 超过 709，全部变成 `inf` |
| (d) 本节 `softmax` | `[0. 0. 1.]` | 减最大值后变成 `[-2000, -1000, 0]`，`exp` 后为 `[0, 0, 1]` |

所以演示中的 `[100, 200, 300]` 在 float64 下即便用朴素 softmax 也不会溢出，这句提示要用 float32（GPU 训练常用 fp16/bf16，上限更低）或更大的 logits 才能真正体现差别。fp16 的上限只有 65504，`e¹²` 就已经超过了——这就是混合精度训练里 attention softmax 通常要在 fp32 中计算的原因之一。

### Q11 — 参考回答要点

1. **输入**：序列表示 `X ∈ ℝ^{n×d}`。
2. **投影**：`Q = XWq (n×dk)`、`K = XWk (n×dk)`、`V = XWv (n×dv)`，时间 O(n·d·dk)。
3. **打分**：`S = QKᵀ / √dk (n×n)`，时间 O(n²·dk)，空间 O(n²)。
4. **（可选）mask**：因果 / padding 位置置 `-inf`。
5. **归一化**：对每行 softmax（先减行最大值），得到 `A (n×n)`，每行和为 1。
6. **聚合**：`O = AV (n×dv)`，时间 O(n²·dv)。
7. **复杂度**：总计 O(n²·d + n·d²)；n 大时 n² 项主导，这是长上下文的瓶颈。
- **加分点**：能写出 `softmax(QKᵀ/√dk)V` 并说明每一步的直觉（Q 问、K 答、V 给）；提到多头时 `dk = d_model/h`；指出 Flash Attention 不改变 FLOPs，只消除 n×n 矩阵的显存落地。
- **常见误区**：把 softmax 做在列方向（应该沿 key 维度，即每个 query 一行）；忘记缩放。

### Q12 — 参考回答要点

- **为什么缩放**：若 q、k 各分量独立、均值 0、方差 1，点积方差为 dk，标准差 √dk。dk = 64 时分数常在 ±十几甚至几十，softmax 输入差值大 → 输出接近 one-hot → 雅可比 `diag(p) - ppᵀ` 接近 0 → 梯度消失，训练早期很难学。
- **为什么是 √dk 而不是 dk**：目标是让分数的**方差**回到 1（标准差回到 1）。方差是平方量，除以 √dk 使方差除以 dk，正好归一；除以 dk 会把方差压到 `1/dk`，分数几乎都接近 0，softmax 接近均匀分布，模型很难形成尖锐的注意力，同样不利于学习。
- **不缩放会怎样**：初始化阶段 attention 分布过尖，梯度很小，收敛慢或不稳定；本质上等价于一个很低的 softmax 温度。
- **加分点**：提到 QK-Norm（对 q、k 做归一化）等变体也是为了控制 logits 的尺度；指出这个推导依赖"分量独立、方差 1"的假设，实际中由初始化和 LayerNorm 近似保证。

### Q13 — 参考回答要点

- **解耦三种角色**：Q 决定"我想找什么"，K 决定"我以什么特征被找到"，V 决定"被找到后交出什么信息"。三者用不同投影，模型可以学到"按语法角色匹配、按语义内容传递"这类非对称关系。
- **若 `Wq = Wk`**：
  1. 打分矩阵 `QQᵀ` 是**对称的**：i 对 j 的打分等于 j 对 i 的打分，无法表达"形容词关注名词，但名词不关注形容词"这类有方向的关系；
  2. 对角线是 `|q_i|²`，通常比非对角项大，token 倾向于主要关注自己；
- **若去掉 V（直接用 X）**：输出只能是原输入的凸组合，表达能力受限，也无法改变维度。
- **加分点**：提到工程上为了省显存出现的 MQA / GQA 共享的是 **K、V 在头之间的投影**（第 03 节），而不是 Q 与 K 共享，二者不要混淆。

### Q14 — 参考回答要点

| 类型 | Q 来自 | K、V 来自 | 典型位置 |
|------|--------|-----------|---------|
| Self-attention | 同一序列 X | 同一序列 X | Transformer encoder 每层；decoder 每层（带因果 mask） |
| Cross-attention | decoder 当前状态 | encoder 输出 | 原始 Transformer、T5/BART 的 decoder；多模态里文本读图像特征 |
| Bahdanau attention（2014） | RNN decoder 的隐状态 | RNN encoder 的所有隐状态 | 嫁接在 RNN seq2seq 上，打分用一个小 MLP（加性 attention） |

- 核心区别：self-attention 让序列"自己看自己"，取代了递归；cross-attention 连接两个序列；Bahdanau attention 是历史起点，用加性打分 `vᵀ tanh(W₁h + W₂s)` 而不是缩放点积。
- **加分点**：说明 2017 年 Transformer 的关键一步是"把 attention 从 RNN 的配件变成唯一的机制"（讲义原话："what if attention is the only mechanism?"）；cross-attention 的细节见第 05 节。

### Q15 — 参考回答要点

- **实现**：用布尔 mask 组合
  - padding mask：形状 `(B, 1, 1, n_k)`，key 是 padding 的位置为 False；
  - 因果 mask：形状 `(1, 1, n_q, n_k)` 的下三角；
  - 两者按位与（广播）得到 `(B, 1, n_q, n_k)`，在 softmax 前 `scores.masked_fill(~mask, -inf)`。
- **为什么不是"权重乘 0"**：softmax 之后再乘 0，剩余权重之和小于 1，分布不再归一；而在 softmax 之前加 `-inf`，被屏蔽的位置自然得到 0，剩余权重自动重新归一化（见 Q5、Q9）。
- **全被 mask 的行**：整行都是 `-inf`，减最大值时出现 `-inf - (-inf) = nan`，整行权重变 `nan` 并沿梯度扩散。常见处理：用一个有限的极大负数（如 dtype 最小值）代替 `-inf`、对全 mask 行单独置零、或保证至少保留一个位置（例如因果 mask 的对角线）。
- **混合精度注意**：fp16 下 `-1e9` 会溢出成 `-inf`，要用 `torch.finfo(dtype).min` 一类与 dtype 匹配的值。
- **加分点**：提到 padding 通常只需屏蔽 key 维度（query 是 padding 的行输出在 loss 中会被忽略）。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 01 线性代数直觉](../../../01-math-foundations/01-linear-algebra-intuition/docs/zh.md)：点积 = 相似度，矩阵乘 = 变换。
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：softmax 减最大值、浮点上溢下溢。
- [阶段 03 · 08 Weight 初始化和训练稳定性](../../../03-deep-learning-core/08-weight-initialization/docs/zh.md)：代码中 `sqrt(2/(fan_in+fan_out))` 的 Xavier 初始化。
- [阶段 05 · 10 Attention 机制——突破](../../../05-nlp-foundations-to-advanced/10-attention-mechanism/docs/zh.md)：Bahdanau attention，本节的历史起点。
- [阶段 07 · 01 为什么选择 Transformers](../../01-why-transformers/docs/zh.md)：为什么要用"广播式"的 attention 取代递归。

### 本节被哪些后续内容用到
- [阶段 07 · 03 多头 Attention](../../03-multi-head-attention/docs/zh.md)：把本节的列表式多头改写成 reshape 式，并引入 GQA/MQA。
- [阶段 07 · 04 位置编码](../../04-positional-encoding/docs/zh.md)：解决本节发现的置换等变问题。
- [阶段 07 · 05 完整的 Transformer](../../05-full-transformer/docs/zh.md)：因果 mask、cross-attention、残差与 LayerNorm 组装成完整模型。
- [阶段 07 · 07 GPT — 因果语言建模](../../07-gpt-causal-language-modeling/docs/zh.md)：因果 mask 的主战场。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../12-kv-cache-flash-attention/docs/zh.md)：本节 O(n²) 分数矩阵的工程优化。
- [阶段 19 · 33 多头 Self-Attention](../../../19-capstone-projects/33-multihead-self-attention/docs/zh.md)：综合项目中重写本节内容。

### 延伸关键词
`scaled dot-product attention` · `additive attention` · `softmax temperature` · `causal mask` · `padding mask` · `permutation equivariance` · `QK-Norm` · `Flash Attention` · `attention sink`
