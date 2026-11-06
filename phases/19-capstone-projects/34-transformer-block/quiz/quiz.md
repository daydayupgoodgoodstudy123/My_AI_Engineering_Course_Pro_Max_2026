# 测验 · 从零实现 Transformer 模块（Transformer Block from Scratch）

> **阶段 19 · 综合项目 · 第 34 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Block 的四个零件 | LayerNorm、多头因果注意力、残差连接、逐位置 MLP；输入输出都是 `(B, T, D)` |
| 2 | Pre-LN | `x = x + attn(ln1(x))`；`x = x + mlp(ln2(x))`。LN 在残差支路里，残差主干不被归一化；需要在整个栈的最后加 `final_ln` |
| 3 | Post-LN | `x = ln1(x + attn(x))`；`x = ln2(x + mlp(x))`。2017 年原始论文的做法，梯度每层都要穿过 LN，深层时需要 warmup |
| 4 | LayerNorm 细节 | 沿最后一维求均值和**有偏**方差（`unbiased=False`），`eps=1e-5`，可学习 `scale`/`shift` |
| 5 | MLP | `D → 4D → D`，GELU（代码用 tanh 近似），逐 token 独立计算，不混合 token |
| 6 | 因果 mask | 布尔 `triu(..., diagonal=1)` 存为 buffer，`masked_fill(mask, -inf)` 屏蔽未来位置 |
| 7 | 残差的两个作用 | 梯度在深度方向上是"相加"的通路；每个 block 学的是对表示的增量更新，而非整体替换 |
| 8 | Dropout 位置 | 不能放在残差恒等路径上；代码实际有三处：注意力权重、注意力输出、MLP 输出（讲义说"两处"） |
| 9 | 参数量 | 每个 block `12D² + 13D`（含 bias 与两个 LN）；D=768 时 7,087,872，D=192 时 444,864 |
| 10 | 演示的陷阱 | demo 的 loss 是 LayerNorm 输出的平方和，它几乎是常数 `B·T·D`，因此"210 倍梯度比"不能说明 pre-LN 更好训练 |

### 核心技能（能动手做到）

- [ ] 不看代码写出 `LayerNorm`、`MultiHeadAttention`、`FeedForward`、`TransformerBlock`（含 `pre_ln` 开关）
- [ ] 手算任意 `d_model` 下一个 block 的参数量，并算出去掉 bias 能省多少（讲义练习 1）
- [ ] 写出 RMSNorm，并说清它与 LayerNorm 的差别（讲义练习 2）
- [ ] 用"扰动未来 token"的方法测试因果性
- [ ] 识别"loss 对输入不敏感"导致的无效梯度实验，并设计一个能真正比较 pre-LN 与 post-LN 的实验
- [ ] 解释为什么 post-LN 需要 warmup、pre-LN 可以不用，以及 pre-LN 的代价

---

## 二、基础自测（选择题）

**Q1.** 下列哪一个是本节代码 `pre_ln=True` 分支的写法？

- A. `x = self.ln1(x + self.attn(x))`；`x = self.ln2(x + self.mlp(x))`
- B. `x = x + self.attn(self.ln1(x))`；`x = x + self.mlp(self.ln2(x))`
- C. `x = self.attn(self.ln1(x))`；`x = self.mlp(self.ln2(x))`
- D. `x = self.ln1(x) + self.attn(x)`；`x = self.ln2(x) + self.mlp(x)`

**Q2.** demo 配置 `d_model=192, num_heads=6, mlp_expansion=4, use_bias=True`，一个 `TransformerBlock` 有多少参数？

- A. 442,368
- B. 2,694,144
- C. 443,136
- D. 444,864

**Q3.** demo 用 `loss = out.pow(2).sum()` 计算 embedding 的梯度范数，其中 `out` 是 `final_ln` 的输出。这个 loss 的问题是：

- A. LayerNorm 输出每个 token 的均方值恒约为 1，所以 loss ≈ `B·T·D`（实测 12287.9 vs 12288），几乎与输入无关，梯度只来自 `eps` 项，数值极小且不反映真实训练信号
- B. 平方和会让梯度爆炸
- C. 平方和不可导
- D. 没有问题，这是衡量梯度流的标准做法

**Q4.** 讲义说 dropout 应该放在"两处，而不是三处"。本节 `MultiHeadAttention` + `FeedForward` 实际在哪些地方用了 dropout？

- A. 只有注意力 softmax 之后一处
- B. 注意力 softmax 之后、MLP 第二个线性层之后，共两处
- C. 注意力 softmax 之后、注意力输出投影之后、MLP 第二个线性层之后，共三处——都在残差支路里，没有放在残差恒等路径上
- D. 残差相加之后

**Q5.** 测试 `test_normalizes_last_dim_to_zero_mean_unit_var` 用 `out.std(dim=-1)` 检查标准差，容差设为 `1e-2` 而不是 `1e-5`。最可能的原因是：

- A. LayerNorm 的 `eps` 太大
- B. `torch.std` 默认用无偏估计（除以 N−1），而 LayerNorm 用有偏方差（除以 N）；D=64 时结果约为 `√(64/63) ≈ 1.0079`
- C. 随机输入的方差不稳定
- D. `scale` 参数初始化不为 1

**Q6.** 关于本节代码 `pre_ln=False` 的分支，正确的是：

- A. 它与 pre-LN 只是写法不同，数学上等价
- B. 它在残差主干上没有任何 LayerNorm
- C. 它会让输出形状变成 `(B, T, 4D)`
- D. 每个子层的输出与输入相加后再过 LayerNorm，所以每个 block 的输出都被归一化（实测输出标准差约 1.0000），梯度回传时每层都要穿过 LN

**Q7.** 讲义练习 1：12 层、768 维的模型，把所有线性层的 `bias` 去掉能省多少参数？（LayerNorm 的 `shift` 不算 bias）

- A. 82,944
- B. 6,912
- C. 36,864
- D. 9,216

**Q8.** 关于本节的 `FeedForward`，正确的是：

- A. 它在序列维上做卷积，混合相邻 token
- B. 隐藏层宽度是 `2D`
- C. 对每个 token 独立应用同一个 `D → 4D → D` 的两层网络，激活是 tanh 近似的 GELU；token 之间的信息交换只发生在注意力里
- D. 它的激活函数是 ReLU

---

## 三、动手 / 代码题

**Q9.** 运行 demo 得到：

```text
Pre-LN  embedding grad norm: 0.002251
Post-LN embedding grad norm: 0.000011
Pre-LN / Post-LN ratio    : 210.24x
```

1. 证明：对 LayerNorm 的输出 `y`（`scale=1, shift=0`），`Σ y² = D · var / (var + eps)`，从而 `loss = out.pow(2).sum()` 几乎是常数。
2. 如果把 `depth` 改成 1，你预测比值会怎样变化？这说明了什么？
3. 设计一个更合理的"一次反传"比较：把 loss 换成 `(out * R).sum()`（R 为固定随机张量），预测结果。

**Q10.** 讲义练习 2：手写 RMSNorm 替换 LayerNorm。

1. 写出实现，并说明它与 LayerNorm 的两点区别。
2. 如何验证你的实现？RMSNorm 的输出每个 token 的均值是 0 吗？

**Q11.** 讲义练习 3：给 `MultiHeadAttention` 加一个开关，返回第一个头的注意力权重 `(B, T, T)`。写出修改后的 `forward`，并说明：权重应该在 dropout 之前还是之后取？如何确认修改没有改变原来的输出？

**Q12.** 既然 Q9 的实验无效，请设计一个能真正体现"pre-LN 不需要 warmup、post-LN 需要"的实验，并预测（或实际跑出）结果。

---

## 四、面试高频题

**Q13.**（基础必考）画出一个 decoder-only Transformer block 的结构，说明 pre-LN 与 post-LN 的区别，以及为什么现代 LLM 都用 pre-LN。

**Q14.**（原理深挖）从梯度传播的角度解释：为什么 post-LN 在深层时需要 learning rate warmup？pre-LN 有没有代价？

**Q15.**（工程实践）LLaMA 系列在 GPT-2 block 的基础上做了哪些改动？如果把 MLP 换成 SwiGLU，隐藏层宽度一般怎么取才能保持参数量不变？

**Q16.**（追问型）Dropout 应该放在 block 的哪些位置？为什么不能放在残差主干上？大模型预训练时还用 dropout 吗？

**Q17.**（场景设计）你训练一个 24 层模型，前几百步 loss 不降、偶尔出现 loss spike 甚至 NaN。请给出排查思路和可能的修复方法。

---

## 五、参考答案与解析

### Q1 — 答案：B

代码原文：

```python
        if self.pre_ln:
            x = x + self.attn(self.ln1(x))
            x = x + self.mlp(self.ln2(x))
        else:
            x = self.ln1(x + self.attn(x))
            x = self.ln2(x + self.mlp(x))
```

A 是 post-LN；C 没有残差；D 把 LN 放到了残差主干上又没对子层输入归一化，不是标准结构。

### Q2 — 答案：D

- 权重：注意力 `3D² + D² = 4D²`，MLP `D·4D + 4D·D = 8D²`，共 `12D² = 442,368`；
- bias：QKV `3D` + 输出 `D` + fc1 `4D` + fc2 `D` = `9D = 1,728`；
- 两个 LayerNorm：`4D = 768`。

合计 `442,368 + 1,728 + 768 = 444,864`（已实际运行验证）。A 只算权重；C 漏了 bias；B 是 demo 打印的整个栈（6 个 block + `128×192` 的 embedding + `final_ln`）：`6 × 444,864 + 24,576 + 384 = 2,694,144`。

### Q3 — 答案：A

LayerNorm 把每个 token 的向量归一化为均值 0、（有偏）方差约 1，平方和就约等于 D。我们实测 pre-LN 栈的 loss 为 12287.91、post-LN 为 12287.88，理论值 `2 × 32 × 192 = 12288`。loss 几乎不随输入变化，梯度只来自 `var/(var+eps)` 里 `eps` 带来的微小偏差，所以两个梯度都非常小（0.0023 和 0.000011），二者的比值反映的是 LN 的数值细节，而不是"梯度流是否顺畅"。B、C 错；D 错，衡量梯度流应该使用对输出敏感的 loss（见 Q9）。

### Q4 — 答案：C

`MultiHeadAttention` 里有 `attn_dropout`（softmax 之后）和 `resid_dropout`（`out_proj` 之后），`FeedForward` 里还有一个（`fc2` 之后），共三处。三处都在残差**支路**内部，符合讲义"不要放在残差恒等路径上"的原则；但讲义的"Dropout in two places, not three"与代码不一致——GPT-2 的参考实现本身就在注意力输出投影之后也有 residual dropout。D 正是讲义警告不要做的。

### Q5 — 答案：B

`LayerNorm.forward` 用 `x.var(unbiased=False)`（除以 N），而 `torch.std` 默认 `unbiased=True`（除以 N−1）。所以 LN 输出用 `std()` 测得的标准差是 `√(N/(N−1))`，D=64 时约 1.0079（实测 `[1.0079, 1.0079, 1.0079]`），用 `1e-5` 容差会失败。A 错：`eps=1e-5` 的影响约 `1e-5/var`，远小于 0.008；C、D 不成立（`scale` 初始为全 1）。

### Q6 — 答案：D

post-LN 的每个 block 都以 LN 结尾，输出被重新归一化（我们用 `(2, 16, 384)`、6 头的输入实测：post-LN 输出标准差 1.0000，pre-LN 为 1.0240）。反传时梯度必须穿过每一层的 LN。A 错：讲义练习 4 正是要验证两者输出不同（实测 `allclose` 为 False）；B 说的是 pre-LN；C 错，形状不变。

### Q7 — 答案：A

每个 block 的 bias：`3·768 + 768 + 4·768 + 768 = 9 × 768 = 6,912`；12 层共 **82,944**（已实际计算：`use_bias=True` 的 block 为 7,087,872，`False` 为 7,080,960）。B 是单个 block 的；C 是 12 层的注意力 bias（`12 × 3,072`）；D 只算了每层一个 768 维的 bias 向量（`12 × 768`）。82,944 只占 124M 的约 0.07%——去 bias 的主要动机不是省参数，而是简化、稳定训练与便于张量并行等工程考虑。

### Q8 — 答案：C

`fc1: Linear(D, 4D)` → `nn.GELU(approximate="tanh")` → `fc2: Linear(4D, D)` → dropout。所有操作只作用在最后一维，序列中各位置互不影响（讲义："No tokens talk to each other inside the MLP"）。tanh 近似与精确 GELU 在 `[-3, 3]` 上的最大差约 `4.7e-4`（实测），GPT-2 原版就用 tanh 近似。

### Q9 — 参考答案

1. 设 `μ`、`var` 为某个 token 向量的均值和有偏方差，`y_i = (x_i − μ)/√(var + eps)`，则 `Σ y_i² = Σ (x_i − μ)² / (var + eps) = D·var / (var + eps)`。当 `var ≫ eps` 时它约等于 D，与输入几乎无关；对输入的导数正比于 `D·eps/(var+eps)²`，被 `eps = 1e-5` 压得极小。整个 loss ≈ `B·T·D = 12288`。
2. 我们实测 `depth = 1, 6, 12` 时比值分别为 **256.8×、210.2×、162.9×**——深度越**浅**比值越**大**，与"post-LN 在深层梯度衰减"的说法正好相反。说明这个比值与深度带来的梯度衰减无关，是 loss 退化 + 两种结构末端 LN 数值细节的产物（post-LN 栈最后连续两个 LN：最后一个 block 的 `ln2` 和 `final_ln`，第二个 LN 的输入方差已经恰好≈1）。
3. 用固定随机读出 `R`，loss 对输出线性、对输入敏感。实测 embedding 梯度范数（pre / post）：depth 1 为 `113.54 / 113.52`，depth 6 为 `109.84 / 109.33`，depth 12 为 `113.32 / 113.97`，比值 **≈ 1.00**。逐层看 depth 12 的输入梯度范数：pre-LN 从顶层 84 增到底层 112，post-LN 在 105–112 之间。也就是说，**在初始化时、一次反传**看不出两者的数量级差异。讲义和 docstring 中"pre-LN 的 embedding 梯度大一个数量级，这是 pre-LN 无需 warmup 的经验信号"这一结论没有被这个 demo 支持，真正的差别要在训练动态里看（Q12）。

### Q10 — 参考答案

```python
class RMSNorm(nn.Module):
    def __init__(self, d_model: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.eps = eps
        self.scale = nn.Parameter(torch.ones(d_model))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = torch.sqrt(x.pow(2).mean(dim=-1, keepdim=True) + self.eps)
        return self.scale * x / rms
```

1. 区别：①**不减均值**，只除以均方根（RMS）；②**没有 `shift`**，参数量减半（每层 D 个而不是 2D 个）。计算更省，LLaMA 系列使用它。
2. 验证：形状不变（`(2, 16, 64)` 进出）；与 PyTorch 内置 `nn.RMSNorm(64, eps=1e-6)` 对比 `allclose` 为 True（已实测）；输出每个 token 的 `mean(y²)` 为 1.0000。均值**不是 0**：对 `randn*3+1` 的输入，输出各 token 均值约 0.29–0.37（实测）——这正是"不中心化"的体现。替换后整个 block 的输出形状不变（讲义练习 2 的要求）。

### Q11 — 参考答案

```python
    def forward(self, x, return_first_head=False):
        batch, seq, dim = x.shape
        q, k, v = self.qkv(x).split(self.d_model, dim=-1)
        q, k, v = [z.view(batch, seq, self.num_heads, self.head_dim).transpose(1, 2)
                   for z in (q, k, v)]
        scores = q @ k.transpose(-2, -1) / math.sqrt(self.head_dim)
        scores = scores.masked_fill(self.causal_mask[:seq, :seq], float("-inf"))
        attn = F.softmax(scores, dim=-1)
        first_head = attn[:, 0].detach()          # (B, T, T)，在 dropout 之前取
        attn = self.attn_dropout(attn)
        out = (attn @ v).transpose(1, 2).contiguous().view(batch, seq, dim)
        out = self.resid_dropout(self.out_proj(out))
        return (out, first_head) if return_first_head else out
```

- 应在 dropout **之前**取：之后的权重被随机置零并放大，行和不为 1，不是模型"真正的"注意力分布。`detach()` 避免把可视化张量挂在计算图上。
- 验证：①`torch.triu(first_head, diagonal=1)` 的最大绝对值为 0（实测 0.0）；②把原模块的 `state_dict` 加载进新模块，`eval()` 下比较 `out` 与原输出，`allclose` 为 True（实测）。
- 注意保留原来的 `seq > context_length` 检查（上面为简洁省略了）。

### Q12 — 参考答案

实验设计：在 block 栈上加位置 embedding 和 LM head，做一个需要注意力的语言建模任务（例如长度 8 的随机片段重复 8 次，下一个 token 等于 8 个位置之前的 token）；12 层、`d_model=192`、6 头，Adam，**不做 warmup**，分别在 lr = 3e-4、1e-3、3e-3 下训练 pre-LN 和 post-LN 各 300 步，记录每 50 步的平均 loss。

我们的实测结果（同一初始化与数据；`ln 128 ≈ 4.85` 为"只学到均匀分布"的水平，理论下限约 `7/64 × ln 128 ≈ 0.53`）：

| lr | Pre-LN（每 50 步平均） | Post-LN（每 50 步平均） |
|----|----------------------|------------------------|
| 3e-4 | 4.86 → 4.46 → 3.97 → 2.01 → 0.75 → **0.64** | 4.80 → 4.38 → 3.99 → 2.97 → 0.86 → **0.60** |
| 1e-3 | 4.88 → 3.90 → 0.94 → 0.58 → 0.55 → **0.55** | 4.95 → 4.91 → 4.90 → 4.88 → 4.88 → **4.88**（卡住） |
| 3e-3 | 4.99 → … → **4.81**（卡住） | 5.00 → … → **4.87**（卡住） |

解读：小学习率时两者都能学会；lr = 1e-3 不 warmup 时 post-LN 卡在均匀分布附近，pre-LN 正常收敛到接近下限；lr 再大两者都失败。这才是"pre-LN 对学习率更宽容、post-LN 需要 warmup"的直接证据。进一步可以给 post-LN 加线性 warmup（如前 100 步从 0 升到 1e-3），观察它能否恢复训练。

### Q13 — 参考回答要点

- 结构：`x → LN → 因果多头注意力 → +x → LN → MLP(D→4D→D, GELU) → +` ，输入输出同形 `(B, T, D)`。
- Pre-LN：LN 在子层之前、残差支路内；残差主干是恒等路径，梯度可以不经任何 LN 直达底层。整个栈末尾需要一个 `final_ln`。
- Post-LN：LN 在残差相加之后，每层输出被归一化；梯度要穿过每层的 LN。
- 为什么现代 LLM 用 pre-LN：训练更稳定、对学习率更宽容、可以去掉或缩短 warmup，深层更容易训练（Q12 的实验：lr = 1e-3 无 warmup 时只有 pre-LN 能学）。讲义："Pre-LN is the configuration GPT-2 onward ships with."
- 加分点：说出 GPT-2 在 pre-LN 之外还对残差投影做了按层数缩放的初始化（下一节代码实现了 `1/√(2·num_layers)`）。

### Q14 — 参考回答要点

- **Post-LN**：输出 `y = LN(x + F(x))`。反传时 `∂y/∂x` 要乘以 LN 的雅可比（除以当前方差的标准差、减去均值方向的投影）。残差相加后方差变大，LN 把它压回来，梯度也被相应缩放；层层相乘后，靠近输入的层梯度变小，而靠近输出的层梯度相对很大。训练初期用大学习率时，顶层参数更新过猛，容易发散或卡住，所以需要先用很小的学习率 warmup，让参数进入稳定区域。
- **Pre-LN**：`y = x + F(LN(x))`，`∂y/∂x = I + ∂F/∂x`，恒等项保证梯度至少能原样传回，不依赖任何 LN 的缩放。
- **Pre-LN 的代价**：
  - 残差流的方差随深度增长（我们实测 12 层 pre-LN 栈在初始化时残差流标准差从 1.01 增到 1.37），越深的层对残差流的相对贡献越小，有"深层变得冗余"的现象；
  - 需要额外的 `final_ln`；
  - 同等条件下最终效果有时略逊于调好 warmup 的 post-LN，因此出现了各种折中方案（如在子层输出再加一个 norm 的 sandwich-norm、DeepNorm 等）。
- 加分点：能引用"Pre-LN 可以去掉 warmup"这一类研究结论（如 2020 年关于 Transformer 中 LayerNorm 位置的分析工作），并说明本节 demo 的梯度比值实验不能作为证据（Q9）。

### Q15 — 参考回答要点

- 改动（讲义 Use It 一节）：LayerNorm → **RMSNorm**；GELU → **SiLU**（实际是 SwiGLU 门控 MLP）；绝对位置 embedding → **RoPE**；线性层**去 bias**；再加上 GQA 等推理优化。block 骨架（pre-norm + 两个残差子层）不变。
- SwiGLU：`MLP(x) = W_down(SiLU(W_gate x) ⊙ W_up x)`，有 3 个矩阵。若隐藏宽度为 h，参数量 `3·D·h`；原 MLP 是 `2·D·4D = 8D²`。令 `3Dh = 8D²` 得 `h = 8D/3 ≈ 2.67D`，实践中再取整到 64 或 256 的倍数。
- 加分点：说明这些改动都是"在同一个形状契约下替换零件"，所以本节的 block 只需替换 `LayerNorm`、`FeedForward` 和注意力中的 Q/K 变换就能变成 LLaMA 风格。

### Q16 — 参考回答要点

- 合适的位置：注意力权重之后（attention dropout）、注意力输出投影之后和 MLP 输出之后（residual dropout，在与残差相加**之前**）、embedding 相加之后。本节代码用了前三个，第 35 节加了 embedding dropout。
- 不能放在残差主干上：如果对 `x` 本身做 dropout（`x = dropout(x) + F(x)`），恒等路径被随机打断，梯度和信息都无法稳定地穿过深层网络——讲义："breaks the additive identity that lets the gradient flow at depth"。
- 大模型预训练：数据量远大于参数量、通常只训一个 epoch 左右，过拟合不是主要矛盾，很多现代预训练直接把 dropout 设为 0；微调小数据集时可能再开启。
- 常见误区：在 eval 时忘记 `model.eval()`，dropout 仍在工作，导致评估结果偏差且不可复现（本节 demo 用 `_set_eval_mode` 关闭了它）。

### Q17 — 参考回答要点

- **先确认基础**：初始 loss 是否 ≈ `ln V`；因果 mask 是否正确（扰动测试）；数据与标签是否错位；有没有 `-inf` 整行屏蔽导致的 NaN。
- **结构**：是否为 pre-LN、是否有 `final_ln`；残差投影是否按层数缩放初始化（第 35 节）。
- **优化器**：加 warmup（几百到几千步线性升温）；降低峰值学习率；梯度裁剪（全局范数 1.0）；检查 Adam 的 `eps` 与 β2。
- **数值精度**：bf16 比 fp16 更不容易溢出；softmax 与 LN 在 fp32 中计算；loss spike 时检查是否有 logits 爆炸（可加 z-loss 或 QK-Norm）。
- **监控**：逐层梯度范数、激活范数、注意力熵；spike 出现时定位是哪一层、哪批数据。
- **处理 spike**：从最近的 checkpoint 回退并跳过出问题的数据批次，必要时降低学习率继续训练。
- 加分点：能用 Q12 这样的小规模对照实验先复现问题，再在大模型上验证修复。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 32 Token 与位置 Embeddings](../../32-token-positional-embeddings/docs/zh.md)：block 的输入从哪里来。
- [阶段 19 · 33 多头 Self-Attention](../../33-multihead-self-attention/docs/zh.md)：本节注意力子层的完整推导，本节改用布尔 mask 与 `split`。
- [阶段 07 · 05 完整的 Transformer — Encoder + Decoder](../../../07-transformers-deep-dive/05-full-transformer/docs/zh.md)：原始 post-LN Transformer 的结构。
- [阶段 03 · 08 Weight初始化和训练稳定性](../../../03-deep-learning-core/08-weight-initialization/docs/zh.md)：激活与梯度尺度的基础。
- [阶段 03 · 09 Learning Rate Schedules 和 Warmup](../../../03-deep-learning-core/09-learning-rate-schedules/docs/zh.md)：warmup 的作用。

### 本节被哪些后续内容用到
- [阶段 19 · 35 组装 GPT 模型](../../35-gpt-model-assembly/docs/zh.md)：把 12 个 pre-LN block 堆成 124M GPT，并加入残差投影缩放初始化。
- [阶段 19 · 36 训练循环与 Evaluation](../../36-training-loop-eval/docs/zh.md)：训练由本节 block 组成的模型。
- [阶段 19 · 44 带线性 Warmup 的余弦学习率](../../44-cosine-lr-warmup/docs/zh.md)：post-LN 需要、pre-LN 也常用的 warmup 调度。
- [阶段 19 · 45 Gradient Clipping（梯度裁剪）与 Mixed Precision（混合精度）](../../45-gradient-clipping-amp/docs/zh.md)：深层训练稳定性的另外两件工具。
- [阶段 10 · 14 开放模型：架构详解](../../../10-llms-from-scratch/14-open-models-architecture-walkthroughs/docs/zh.md)：LLaMA、Mistral 等对本节 block 的改动。

### 延伸关键词
`Pre-LN / Post-LN` · `RMSNorm` · `SwiGLU` · `residual stream` · `warmup` · `DeepNorm` · `sandwich norm` · `QK-Norm` · `residual dropout` · `GELU tanh approximation` · `loss spike`
