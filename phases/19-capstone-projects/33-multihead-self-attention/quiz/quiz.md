# 测验 · 多头 Self-Attention（Multi-Head Self-Attention）

> **阶段 19 · 综合项目 · 第 33 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 形状契约 | 输入 `(B, T, D)` → 输出 `(B, T, D)`；内部 `(B, H, T, d_head)`，`d_head = D // H`，要求 `D % H == 0` |
| 2 | 合并的 QKV 投影 | 一个 `Linear(D, 3D)` 再 `chunk(3)`，与三个 `Linear(D, D)` 数学等价，但只发起一次 matmul |
| 3 | 拆头 / 合头 | `view(B,T,H,dh).transpose(1,2)` 拆头；`transpose(1,2).contiguous().view(B,T,D)` 合头；漏掉 transpose 不报错但结果错 |
| 4 | 缩放点积 | `scores = Q Kᵀ / √d_head`，形状 `(B, H, T, T)`；不缩放时分数方差 ≈ d_head，softmax 饱和、梯度消失 |
| 5 | 因果 mask | `tril(ones(L, L))` 存为 buffer，前向切 `[:T, :T]`，`masked_fill(mask == 0, -inf)`，未来位置权重为 0 |
| 6 | softmax 的维度 | 沿最后一维（key 维）归一化：每个 query 行和为 1 |
| 7 | 输出投影 | 合头后再过 `Linear(D, D)`，让不同头的信息混合；块内只有 QKV 与输出两层有参数 |
| 8 | 注意力权重检查 | `return_weights=True` 返回 `(B, H, T, T)`，可以画热力图看每个头在看哪里 |
| 9 | 玩具训练的局限 | repeat 任务每行只有一个 id，看任何位置都能答对，所以训练后的头**不会**呈现"看前一个 token"的模式 |
| 10 | 本节没做的 | FFN、残差、LayerNorm（下一节）；RoPE/ALiBi；推理用 KV cache |

### 核心技能（能动手做到）

- [ ] 不看代码写出 `MultiHeadSelfAttention.forward`，并在每一步标出张量形状
- [ ] 计算一个注意力块的参数量（含 bias）：`D·3D + 3D + D·D + D`
- [ ] 手算 3×3 的带因果 mask 的 softmax 权重
- [ ] 写测试验证三条性质：未来位置权重为 0、每行和为 1、修改未来 token 不影响过去的输出
- [ ] 解释 `-inf` 与 `-1e9` 两种 mask 写法在"整行被屏蔽"和 FP16 下的差异
- [ ] 为注意力块加上 KV cache 的增量前向，并验证与完整前向逐位一致
- [ ] 用 `F.scaled_dot_product_attention(is_causal=True)` 替换手写实现并验证等价

---

## 二、基础自测（选择题）

**Q1.** `MultiHeadSelfAttention(d_model=32, n_heads=4, max_context_length=12)` 一共有多少个可训练参数？

- A. 4,096
- B. 3,168
- C. 4,224
- D. 8,384

**Q2.** demo 中输入 `x` 为 `(16, 12, 32)`、`n_heads=4`。`q = self._split_heads(q)` 之后 `q` 的形状是：

- A. `(16, 4, 12, 8)`
- B. `(16, 12, 4, 8)`
- C. `(16, 4, 12, 32)`
- D. `(64, 12, 8)`

**Q3.** 注意力分数要除以 `√d_head` 的原因是：

- A. 让每一行 softmax 后的和等于 1
- B. 减少 matmul 的计算量
- C. 实现因果 mask
- D. q、k 各分量独立、方差为 1 时，点积方差约等于 `d_head`；不缩放会让 softmax 进入饱和区、梯度很小

**Q4.** 本节因果 mask 的实现是 `causal_mask = torch.tril(torch.ones(L, L))`，前向中 `scores.masked_fill(mask_slice == 0, float("-inf"))`。下列说法正确的是：

- A. 被填成 `-inf` 的是下三角（含对角线），即过去的位置
- B. 被填成 `-inf` 的是严格上三角（列号 > 行号），即未来的位置；对角线保留，所以每一行至少有一个有效位置
- C. mask 是一个可训练参数，会随训练更新
- D. mask 在 softmax 之后乘到权重上

**Q5.** 合头之后还要经过 `out_proj = Linear(D, D)`，讲义给出的主要理由是：

- A. 让模型在块内就能混合不同头的输出，否则各头只能等到后续层才重新组合
- B. 把 `(B, H, T, T)` 的权重变回 `(B, T, D)`
- C. 实现残差连接
- D. 让输出维度从 `3D` 变回 `D`

**Q6.** 关于"一个 `Linear(D, 3D)` + `chunk(3)`"与"三个独立的 `Linear(D, D)`"，正确的是：

- A. 前者参数更少
- B. 前者只能用于单头注意力
- C. 两者数学上不等价，因为 `chunk` 会打乱特征顺序
- D. 两者数学等价（`3D×D` 的权重就是三个 `D×D` 权重的堆叠），前者只发起一次 matmul，通常更快

**Q7.** demo 在 repeat 任务上训练后，loss 降到 0.0036，但热力图中 head 0 主要看位置 1、2，并没有"看前一个 token"。最合理的解释是：

- A. 训练失败了，模型只是记住了训练集
- B. 因果 mask 写错了，导致模型看到了未来
- C. 任务里每一行所有位置都是同一个 id，看任何位置都能拿到答案，所以模型没有必要学"看前一个"
- D. 热力图的字符映射把数值画反了

**Q8.** 有人建议把 `float("-inf")` 换成 `-1e9`。关于两者的区别，正确的是：

- A. 两者在任何情况下结果完全相同
- B. 如果某一行**全部**被屏蔽（例如再叠加 padding mask），`-inf` 会让 softmax 输出 NaN，`-1e9` 会得到均匀分布；本节纯因果 mask 不会出现全屏蔽行
- C. `-1e9` 在 FP16 下仍是有限值，因此更安全
- D. `-inf` 会让梯度变成 NaN，所以不能用于训练

---

## 三、动手 / 代码题

**Q9.** 有人"简化"了合头函数：

```python
    def _merge_heads(self, x: torch.Tensor) -> torch.Tensor:
        b, h, t, dh = x.shape
        return x.contiguous().view(b, t, h * dh)
```

1. 这段代码会报错吗？结果对不对？
2. 用本节测试中的哪一个能抓住这个 bug？为什么"输出形状正确"的测试抓不住？

**Q10.** 手算题。单头、`T = 3`，已经除过 `√d_head` 的分数矩阵为

```text
S = [[1, 2, 3],
     [0, 1, 2],
     [2, 0, 1]]
```

施加本节的因果 mask 后做按行 softmax，写出 3×3 的权重矩阵（保留 4 位小数）。

**Q11.** 讲义说本节"不实现 KV cache"，且"它会改变 K、V 的形状契约，但不改变 Q"。请为 `MultiHeadSelfAttention` 写一个增量前向 `forward_cached(x_new, past=None)`，返回 `(out, (k, v))`，并回答：

1. mask 应该切哪一块？如果仍然写 `self.causal_mask[:t_new, :t_new]` 会怎样？
2. 如何验证你的实现正确？

**Q12.** 生产代码通常不会自己存一张 `(L, L)` 的 mask。

1. 本节 `causal_mask` 是 float32 的 `L × L` 张量。`L = 1024` 和 `L = 131,072` 时各占多少内存？
2. 用 `F.scaled_dot_product_attention` 改写注意力核心，并说明改写后会失去本节的哪个功能。

---

## 四、面试高频题

**Q13.**（基础必考）请完整讲一遍多头自注意力的前向计算，标出每一步的张量形状，并给出时间与显存复杂度。

**Q14.**（原理深挖）为什么要除以 `√d_k`？请从方差推导，并说明不缩放时 softmax 的梯度会发生什么。

**Q15.**（原理深挖）多头注意力和"一个 `d_head = D` 的单头注意力"相比，参数量和计算量有什么区别？多头的好处到底是什么？

**Q16.**（工程实践）如果要把本节的注意力块用在生产环境，你会改哪些地方？（从 kernel、mask、精度、推理几个角度）

**Q17.**（追问型）你怎么写测试证明一个注意力实现是"因果"的？只检查权重矩阵上三角为 0 够不够？如果再加上 padding mask 要注意什么？

---

## 五、参考答案与解析

### Q1 — 答案：C

- `qkv_proj`：`32 × 96 + 96 = 3,168`
- `out_proj`：`32 × 32 + 32 = 1,056`
- 合计 **4,224**（已实际运行验证）。mask 是 buffer，dropout 无参数。

A 是两层都不带 bias 的权重量（`4 × 32²`）；B 只算了 QKV 投影；D 是整个 `TinyAttentionLM`（再加 token embedding `64×32` 和 LM head `32×64+64`）的参数量。

### Q2 — 答案：A

`qkv_proj(x)` 为 `(16, 12, 96)`，`chunk(3, dim=-1)` 得三个 `(16, 12, 32)`；`_split_heads` 先 `view(16, 12, 4, 8)` 再 `transpose(1, 2)` 得到 `(16, 4, 12, 8)`。B 是 transpose 之前的形状；C 没有把 D 切开；D 是把 B·H 合并后的形状，PyTorch 的 `matmul` 不需要这样做，四维张量会自动把前两维当成 batch。

### Q3 — 答案：D

若 q、k 每个分量独立、均值 0、方差 1，`q·k = Σ q_i k_i` 的方差为 `d_head`。我们实测：`d = 4、64、512` 时点积方差约为 `3.97、64.1、506`，除以 `√d` 后都约为 1。分数尺度过大时 softmax 接近 one-hot（例如 `[1,2,3,4]` 的 softmax 为 `[0.03, 0.09, 0.24, 0.64]`，乘 8 之后变成 `[0.00, 0.00, 0.00, 1.00]`），雅可比矩阵接近 0，梯度几乎传不回去。A 是 softmax 本身的性质；B、C 与缩放无关。

### Q4 — 答案：B

`tril` 保留下三角（含对角线）为 1、严格上三角为 0；`mask == 0` 选中的就是列号大于行号的"未来"位置，填 `-inf` 后 softmax 权重为 0。对角线始终保留，所以不会出现整行 `-inf`。demo 实测 `sum over future cells : 0.000000`、每行和为 1.0000。C 错：用 `register_buffer` 注册，不是参数；D 错：mask 在 softmax **之前**加到分数上（乘到权重上需要再归一化）。

### Q5 — 答案：A

讲义："The output projection lets the model mix the heads. Without it, the H heads would only ever recombine through later layers and the block would be artificially constrained." B 是 `weights @ V` 再合头完成的；C 残差在下一节的 block 里；D 描述的是 `chunk`，输出投影的输入本来就是 `D` 维。

### Q6 — 答案：D

`[W_q; W_k; W_v]` 堆成 `(3D, D)`，`x @ Wᵀ` 的三段输出分别就是 `x @ W_qᵀ`、`x @ W_kᵀ`、`x @ W_vᵀ`，`chunk` 按最后一维切开，顺序不变。参数量相同（`3D² + 3D`），A 错；它与头数无关，B 错。讲义还提到合并后"三个子矩阵在同一个参数张量里，可以一起初始化"。

### Q7 — 答案：C

`_make_repeat_batch` 每行只采一个 id 并复制到整行，目标是输入右移一位，所以每个位置的目标都等于"当前 token"。由于每个位置的 value 都含有同一个 token 的信息，注意力看哪儿都能拿到答案。我们打印了训练后各头第 11 行的权重：head 0 集中在位置 1–2（0.24、0.55），head 1 集中在位置 0（0.79），head 2 近似均匀，head 3 在位置 0–1——**没有一个头是"前一个 token"头**。模型预测全部正确（12 个位置都预测出 id 4），loss 很低是真实的，A、B 错；D 错，热力图映射是 `int(v × 10)`，数值越大字符越"重"。代码 docstring 说"A single attention head looking one token back is enough to solve it"——这句话没错，但这个任务并**不需要**这样做，所以热力图无法展示讲义说的"头的专门化"。

### Q8 — 答案：B

`softmax([-inf, -inf, -inf])` 实测为 `[nan, nan, nan]`（`exp(-inf - (-inf))` 无定义），`softmax([-1e9]*3)` 为 `[0.33, 0.33, 0.33]`。纯因果 mask 保留对角线，不会整行屏蔽，所以本节用 `-inf` 是安全的；一旦叠加 padding mask（某个 query 本身是 padding，所有 key 都被屏蔽），就要特别处理。C 错：`-1e9` 超出 FP16 的表示范围（最大约 65504），实测 `torch.tensor(-1e9).half()` 为 `-inf`，并不更"安全"；常见做法是 `torch.finfo(dtype).min`。D 错：只要每行至少有一个有限值，`-inf` 位置的 softmax 输出就是精确的 0，梯度也正常。

### Q9 — 参考答案

1. **不报错，但结果错误**。`x` 的形状是 `(b, h, t, dh)`，元素总数与 `(b, t, h·dh)` 相同，`view` 能成功；但内存中的顺序是"先头、后位置"，直接 view 会把**同一个头的不同位置**拼成一个 token 的特征向量。正确做法是先 `transpose(1, 2)` 把内存顺序换成"先位置、后头"，再 `contiguous().view(...)`。
2. `TestHeadSplit.test_split_then_merge_round_trip`：它先拆头再合头，断言 `torch.allclose(merged, x)`。我们实测错误版本的往返结果与 `x` **不相等**，正确版本相等。只检查形状的测试（如 `test_output_shape_matches_input`）抓不住，因为形状完全正确——这正是"形状对了不代表数据对了"的典型例子。（另外 `contiguous()` 在这里是必要的：`transpose` 后的张量不连续，`view` 会报错；可以改用 `reshape`，它在必要时自动复制。）

### Q10 — 参考答案

因果 mask 把 `S[0,1]、S[0,2]、S[1,2]` 置为 `-inf`：

- 第 0 行：只剩 `[1]` → `[1.0000, 0, 0]`
- 第 1 行：`softmax([0, 1]) = [e⁰, e¹] / (1 + e) = [0.2689, 0.7311]` → `[0.2689, 0.7311, 0]`
- 第 2 行：`softmax([2, 0, 1])`：`e² = 7.389`、`e⁰ = 1`、`e¹ = 2.718`，和为 11.107 → `[0.6652, 0.0900, 0.2447]`

```text
[[1.0000, 0.0000, 0.0000],
 [0.2689, 0.7311, 0.0000],
 [0.6652, 0.0900, 0.2447]]
```

已用 PyTorch 实际计算验证。注意第 0 个位置永远只能看自己，权重恒为 1。

### Q11 — 参考答案

```python
import math
import torch
import torch.nn.functional as F

def forward_cached(self, x_new, past=None):
    b, t_new, d = x_new.shape
    q, k, v = self.qkv_proj(x_new).chunk(3, dim=-1)
    q, k, v = self._split_heads(q), self._split_heads(k), self._split_heads(v)
    if past is not None:                                  # 拼接历史 K、V（沿时间维 dim=2）
        pk, pv = past
        k = torch.cat([pk, k], dim=2)
        v = torch.cat([pv, v], dim=2)
    t_total = k.shape[2]
    start = t_total - t_new                               # 新 query 的绝对起始位置
    scores = q @ k.transpose(-2, -1) / math.sqrt(self.d_head)   # (B, H, t_new, t_total)
    mask = self.causal_mask[start:t_total, :t_total]
    scores = scores.masked_fill(mask == 0, float("-inf"))
    w = F.softmax(scores, dim=-1)
    out = self.out_proj(self._merge_heads(w @ v))
    return out, (k, v)
```

1. 新 query 的绝对位置是 `start .. t_total-1`，key 的位置是 `0 .. t_total-1`，所以 mask 要取 `causal_mask[start:t_total, :t_total]`，形状 `(t_new, t_total)`。如果仍写 `[:t_new, :t_new]`：
   - `t_new = 1` 时 mask 是 `(1, 1)` 的 `[[1]]`，广播后**什么也没屏蔽**——恰好也是对的（单个最新 token 本来就能看全部历史），bug 被掩盖；
   - `t_new > 1`（例如一次喂入多 token 的 prompt 续写）时，`(2, 2)` 的 mask 无法与 `(…, 2, 5)` 的分数广播，实测报 `RuntimeError: The size of tensor a (2) must match the size of tensor b (5)`。
   这也是讲义说"Q 的形状契约不变（仍是新 token 数），K、V 变成全部历史长度"的含义。
2. 验证：随机输入 `x (1, 8, 24)`，先整体前向得到 `full`；再先喂前 3 个 token、然后逐个喂剩下 5 个，把各步输出拼起来。我们实测两者 `allclose` 为 `True`，最大误差约 `8.9e-8`。还要注意 `eval()` 模式（关闭 dropout），并且位置编码也要按 `start` 偏移（第 32 节的位置模块不支持，需要改造）。

### Q12 — 参考答案

1. `L × L × 4` 字节：`L = 1024` 时为 **4 MiB**；`L = 131,072` 时为 `2³⁴` 字节 = **64 GiB**（已计算）。长上下文模型不可能把这样一张表放进显存。
2. 改写：

```python
    q, k, v = self.qkv_proj(x).chunk(3, dim=-1)
    q, k, v = self._split_heads(q), self._split_heads(k), self._split_heads(v)
    context = F.scaled_dot_product_attention(
        q, k, v,
        dropout_p=self.attn_dropout.p if self.training else 0.0,
        is_causal=True,
    )
    out = self.out_dropout(self.out_proj(self._merge_heads(context)))
```

我们实测改写后输出与原实现 `allclose`（atol 1e-6）。`is_causal=True` 让 kernel 内部按下标判断是否屏蔽，不需要物化 mask；在 GPU 上还可能走 FlashAttention 等融合 kernel，不必存下 `(B, H, T, T)` 的权重矩阵。代价：**拿不到注意力权重**——`return_weights=True` 无法再实现，可视化/可解释性分析时要退回手写实现。

### Q13 — 参考回答要点

- 步骤与形状：
  1. `x (B, T, D)` → `qkv_proj` → `(B, T, 3D)` → `chunk` → 3 × `(B, T, D)`；
  2. 拆头 → `(B, H, T, d_head)`；
  3. `scores = Q Kᵀ / √d_head` → `(B, H, T, T)`；
  4. 加因果 mask（上三角 `-inf`）→ 沿最后一维 softmax → 权重 `(B, H, T, T)`；
  5. `weights @ V` → `(B, H, T, d_head)`；
  6. 合头 → `(B, T, D)` → `out_proj` → `(B, T, D)`。
- 复杂度：投影部分 `O(T·D²)`；分数与加权求和 `O(T²·D)`；显存方面若物化权重矩阵是 `O(B·H·T²)`。长序列时 `T²` 项占主导。
- 加分点：说出 FlashAttention 通过分块计算 + 在线 softmax，避免物化 `T×T` 矩阵，把显存降到 `O(T)` 级别，计算量不变但 IO 大幅减少。

### Q14 — 参考回答要点

- 推导：设 `q_i, k_i` 独立，均值 0，方差 1，则 `E[q_i k_i] = 0`，`Var(q_i k_i) = E[q_i²]E[k_i²] = 1`，`Var(q·k) = Σ Var(q_i k_i) = d_k`。除以 `√d_k` 后方差回到 1，与头维无关（讲义："keeps the variance of the scores roughly constant across head sizes"）。
- 不缩放的后果：分数标准差约 `√d_k`（d_k = 64 时为 8），softmax 输出接近 one-hot。softmax 的雅可比为 `diag(p) − p pᵀ`，当 p 接近 one-hot 时所有元素都接近 0，梯度消失，训练停滞（讲义："The gradients in that regime are tiny and learning stalls"）。
- 加分点：缩放因子本质是 softmax 的"温度"；有的工作（如 QK-Norm）对 q、k 先做归一化，再用可学习的温度。
- 常见误区：说"除以 d_k"——是除以 `√d_k`；或者说缩放是为了"让权重和为 1"。

### Q15 — 参考回答要点

- **参数量相同**：无论 H 是多少，QKV 投影都是 `D × 3D`、输出投影 `D × D`；多头只是把 D 维切成 H 段。
- **计算量基本相同**：分数计算 `H × T² × d_head = T² × D`，与单头 `d_head = D` 一样；只是 softmax 要做 H 次（`H × T²` 个元素）。
- **好处**：
  - 每个头在不同的 `d_head` 维子空间里计算相似度，可以同时关注不同的模式（前一个 token、句首、语法依存……），讲义："Some heads attend to the immediately previous token. Some heads attend to the start of the sequence..."；
  - 单头只能给出**一个**加权平均，多个相关位置会被"平均掉"；多头相当于多个独立的加权平均再拼接；
  - 每个头的 `Q Kᵀ` 是秩 ≤ d_head 的低秩双线性形式，多头 = 多个低秩注意力的组合。
- 代价：d_head 过小时（如本节建议的 `H=8, D=32 → d_head=4`）每个头的表达能力有限。实测把头数改成 8，repeat 任务三轮 loss 为 `2.8814 → 0.0475 → 0.0035`，与 4 头几乎一样——这个任务太简单，体现不出差别。
- 加分点：MQA/GQA 让多个查询头共享 K、V 头，以减小 KV cache。

### Q16 — 参考回答要点

- **Kernel**：用 `F.scaled_dot_product_attention` / FlashAttention，`is_causal=True`，不物化 mask 和权重矩阵（见 Q12）。
- **Mask**：不存 `L × L` buffer；需要 padding 时用布尔 mask 或变长（varlen）kernel；注意全屏蔽行的 NaN（Q8）。
- **精度**：bf16/fp16 训练时 softmax 在 fp32 中计算；mask 值用 `torch.finfo(dtype).min` 或布尔 mask。讲义学习目标提到"dtype handling"，但本节代码其实没有做任何 dtype 处理。
- **位置编码**：在 Q、K 上加 RoPE（讲义："compatible with either by transforming Q and K before the matmul"）。
- **推理**：KV cache（Q11）、GQA/MQA 减少 KV 头、分页管理 KV cache。
- **Dropout**：大模型预训练常把 attention dropout 设为 0；注意本节 `return_weights` 返回的是 dropout **之后**的权重，训练模式下行和不再为 1（实测 `attn_dropout=0.5` 时某行和为 1.56）。
- **初始化**：输出投影常按层数缩放初始化，保证残差流方差稳定。

### Q17 — 参考回答要点

- 本节测试的三层检查：
  1. 权重上三角为 0（`test_upper_triangle_has_zero_weight`）；
  2. 每行和为 1（`test_weight_rows_sum_to_one`）；
  3. **扰动测试**：修改位置 ≥ 4 的输入，位置 0–3 的输出不变（`test_future_tokens_do_not_change_past_output`）。
- 只看权重不够：权重为 0 只说明注意力这一步没有泄漏，但如果实现里有别的跨位置操作（例如错误地在序列维上做归一化、用了 `F.softmax(dim=-2)`、BatchNorm 混入了未来位置等），只有端到端的扰动测试能发现。更严格的版本：对每个位置 t 计算 `∂out[t] / ∂x[t']`，断言 `t' > t` 时梯度为 0。
- padding mask：
  - 与因果 mask 做逻辑与，屏蔽 padding 的 key；
  - padding 位置作为 query 时可能整行被屏蔽 → `-inf` 导致 NaN，要么用有限的极小值，要么在 softmax 后把这些行置 0，并在 loss 中忽略这些位置；
  - 左填充（left padding）在生成时更常用，位置编码也要相应调整。
- 加分点：测试要覆盖不同的 batch、不同的头，本节 demo 只检查了 batch 0、head 0，测试覆盖了全部。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 32 Token 与位置 Embeddings](../../32-token-positional-embeddings/docs/zh.md)：本节的输入 `(B, T, D)` 就来自那里，`TinyAttentionLM` 里也复制了一份精简版。
- [阶段 07 · 02 Self-Attention 从头开始](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：单头注意力的推导。
- [阶段 07 · 03 多头 Attention](../../../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md)：多头机制的概念介绍。
- [阶段 07 · 07 GPT — 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：因果 mask 的来源。
- [阶段 05 · 10 Attention机制——突破](../../../05-nlp-foundations-to-advanced/10-attention-mechanism/docs/zh.md)：注意力在 seq2seq 中的起源。

### 本节被哪些后续内容用到
- [阶段 19 · 34 从零实现 Transformer 模块](../../34-transformer-block/docs/zh.md)：在本节注意力外面加上 LayerNorm、FFN 和残差。
- [阶段 19 · 35 组装 GPT 模型](../../35-gpt-model-assembly/docs/zh.md)：堆叠多个 block 组成完整 GPT。
- [阶段 19 · 36 训练循环与 Evaluation](../../36-training-loop-eval/docs/zh.md)：真正训练这个注意力层。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：本节没做的 KV cache 与融合 kernel。
- [阶段 07 · 15 Attention 变体 — 滑动窗口、稀疏、差分](../../../07-transformers-deep-dive/15-attention-variants/docs/zh.md)：在同一形状契约下替换注意力模式。

### 延伸关键词
`scaled dot-product attention` · `causal mask` · `masked_fill` · `register_buffer` · `F.scaled_dot_product_attention` · `FlashAttention` · `KV cache` · `GQA / MQA` · `attention head specialization` · `induction head` · `QK-Norm`
