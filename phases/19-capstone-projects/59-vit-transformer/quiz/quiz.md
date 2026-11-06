# 测验 · Vision Transformer Encoder（Vision Transformer Encoder）

> **阶段 19 · 综合项目 · 第 59 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | ViT-Base 配方 | 12 层、12 头、hidden 768、head_dim 64、FFN 4 倍扩展（3072）、GELU、pre-LN，最后接一个 LayerNorm |
| 2 | Pre-LN block | `x = x + attn(ln1(x))`；`x = x + ffn(ln2(x))`。残差主干上没有 LayerNorm，所以需要一个最终的 `norm` |
| 3 | 合并的 qkv 投影 | 一个 `Linear(768, 2304)` 同时算 Q、K、V，`reshape(b, n, 3, h, hd).permute(2, 0, 3, 1, 4)` 拆成 3 个 `(b, h, n, hd)` |
| 4 | 缩放点积注意力 | `softmax(QKᵀ · 1/√64) · V`，分数形状 `(b, 12, 197, 197)`；每一行和为 1 |
| 5 | 无 mask | 视觉 encoder 是双向的，任意 token 都能看任意 token；causal mask 只用于文本解码器的自注意力 |
| 6 | 参数量 | 每个 block 7,087,872（含全部 bias 与 2 个 LN），12 个 block + 最终 LN = 85,056,000；加前端 591,360，合计 **85,647,360** |
| 7 | CLS pooling | 输出序列第 0 个 token 的最终隐状态作为整图表示；它在前端与图像无关，靠逐层注意力汇聚信息 |
| 8 | 残差流的范数增长 | pre-LN 下子层输出不断累加到残差主干，CLS 范数从 0.53 逐层增长到约 35.8；最终 LN 把它拉回 `≈ sqrt(768) = 27.71` |
| 9 | 计算量分布 | 序列 197 时，每层 MLP 约占 2/3 的乘加，QKV/输出投影约 1/3，`QKᵀ` 与 `AV` 只占约 4%（讲义练习 4："The MLP layer dominates"） |
| 10 | 家族变体 | 宽度/深度不同（ViT-L：1024/24/16）、池化方式（CLS / 平均 / 注意力池化）、位置编码（正弦 / 可学习 / 2D RoPE）、register tokens，block 数学不变 |

### 核心技能（能动手做到）

- [ ] 手写 pre-LN Transformer block：合并 qkv、拆头、缩放点积、合头、输出投影、GELU FFN、两条残差
- [ ] 逐项算出 ViT-B/16（或任意宽度/深度）的参数量，并解释与"86M"的口径差异
- [ ] 解释为什么 pre-LN 需要最终 LayerNorm，以及最终 CLS 范数为何约等于 `sqrt(hidden)`
- [ ] 正确地从完整前向中取出每一层的注意力图（不要绕过 `ln1`），并计算注意力熵
- [ ] 为 block 增加 `attn_mask` 参数（因果 / padding），使之可复用为解码器 block
- [ ] 为 encoder 增加 register tokens，并保持 CLS 输出接口不变

---

## 二、基础自测（选择题）

**Q1.** 按本节代码（qkv、out、fc1、fc2 都带 bias，两个 LayerNorm 各有 γ、β），ViT-Base 的**一个** block 有多少参数？

- A. 7,087,872
- B. 7,080,960
- C. 7,077,888
- D. 4,718,592

**Q2.** demo 中 CLS 的范数在第 12 层之后是 35.802，经过最终 LayerNorm 变成 27.713。27.713 这个数最可能的来源是：

- A. 随机巧合，与模型结构无关
- B. 最终 LN 把每个 token 的范数裁剪到固定上限
- C. LN 初始化时 γ = 1、β = 0，输出在 768 维上均值 0、方差 1，范数 ≈ `sqrt(768) ≈ 27.71`
- D. 等于第 0 层 CLS 范数乘以 12 个 head

**Q3.** `self.qkv(x).reshape(b, n, 3, h, hd).permute(2, 0, 3, 1, 4)` 之后张量的形状是：

- A. `(b, n, 3, h, hd)`
- B. `(b, h, n, 3 * hd)`
- C. `(3, b, n, h, hd)`
- D. `(3, b, h, n, hd)`

**Q4.** demo 的 "attention sanity" 打印 `block 0 head 0 CLS row stddev : 0.0000`。最主要的原因是：

- A. softmax 实现有 bug，所有权重都相同
- B. 这段代码直接把 `encoder.front(img)` 喂给 `attn`，**绕过了 `ln1`**；未归一化的输入加上随机初始化，使 CLS 这一行几乎是均匀的 1/197（实测 std ≈ 2.1e-5，四舍五入显示为 0）
- C. CLS 的位置编码为 0 导致注意力全部相同
- D. `store_attn=True` 会把注意力替换成均匀分布

**Q5.** 关于注意力 mask，下列说法正确的是：

- A. ViT encoder 需要 causal mask，否则 CLS 会"偷看"后面的 patch
- B. 视觉-语言解码器中的 cross-attention 需要 causal mask
- C. ViT encoder 不用 mask；在解码器中，文本自注意力用 causal mask，而 text→vision 的 cross-attention 不加 mask（整张图对每个文本位置都可见）
- D. 只有 CLS 这一行需要 mask

**Q6.** 序列长度 197、hidden 768 时，ViT-Base 每层前向的乘加次数中，占比最大的是：

- A. FFN 的两个线性层（约 9.3 亿，约占 2/3）
- B. `QKᵀ` 与 `attn @ V`（约 0.6 亿）
- C. LayerNorm
- D. softmax

**Q7.** 在 pre-LN 结构中，CLS 范数随层数增长（0.53 → 13.7 → 20.0 → … → 35.8）的原因是：

- A. 注意力权重之和大于 1
- B. GELU 会放大输入
- C. 位置编码在每一层重复相加
- D. 每个子层的输出都直接累加到残差主干上，主干本身从不被归一化（LN 只作用于子层的输入）

**Q8.** 本节 encoder 总参数 85,647,360，而 ViT-B/16 常被称为"86M"。两者的差距主要来自：

- A. 本节少了几层 block
- B. 常见的 ViT-B/16 实现使用 197×768 的可学习位置 embedding（151,296）并带有分类头；本节用 0 参数的正弦位置、没有分类头
- C. 本节的 FFN 只扩展 2 倍
- D. 本节没有 qkv bias

---

## 三、动手 / 代码题

**Q9.** demo 的注意力检查代码如下：

```python
encoder.vit.blocks[0].attn(encoder.front(img), store_attn=True)
attn = encoder.vit.blocks[0].attn.last_attn
```

1. 这段代码观察到的注意力与真实前向中 block 0 的注意力有什么不同？
2. 改写成"从一次完整前向中取出每一层的注意力"，并计算每层 CLS 行（对 12 个头取平均）的熵，与均匀分布的熵 `ln 197 ≈ 5.283` 比较。
3. 随机初始化时注意力为什么接近均匀？

**Q10.** 讲义练习 3：给 `MultiHeadSelfAttention.forward`、`Block.forward` 增加 `attn_mask` 参数，使同一 block 可以作为因果解码器 block 使用。要求：支持形状 `(n, n)` 的布尔 mask（`True` 表示允许关注），写出关键代码，并给出一个验证因果性的测试思路。

**Q11.** 讲义练习 1：给 `VisionEncoder` 增加 `num_registers` 个可学习的 register tokens，插在 CLS 之后、patch 之前；它们不加位置编码，最终输出中要去掉，`forward` 的返回接口 `(tokens, cls)` 不变。写出关键代码。

**Q12.** 用本节代码实例化 `ViTConfig(hidden=1024, depth=24, heads=16)`（ViT-L/16 的宽度与深度，FFN 仍为 4 倍）。

1. 手算一个 block 的参数量和 encoder（不含前端）的参数量。
2. 前端（P=16、224 分辨率）有多少参数？
3. 与 ViT-Base 相比，每个 block 的参数变成了多少倍？为什么接近 `(1024/768)²`？

---

## 四、面试高频题

**Q13.**（基础必考）请写出 ViT 一个 encoder block 的前向计算（pre-LN），标出每一步的张量形状（batch B、序列 197、hidden 768、12 头），并说出参数主要集中在哪里。

**Q14.**（原理深挖）Pre-LN 和 Post-LN 有什么区别？为什么现代 Transformer 普遍用 pre-LN？pre-LN 有什么代价或副作用？

**Q15.**（原理深挖）如何从 ViT 得到整张图的表示？CLS pooling、平均池化、注意力池化、register tokens 各有什么特点？给 VLM 的语言模型时又通常怎么用？

**Q16.**（工程实践）要在高分辨率图像（如 1024×1024、P=16）上跑 ViT，计算和显存会出现什么问题？你会用哪些手段优化？

**Q17.**（追问型）注意力为什么要除以 `√d_k`？如果去掉，随机初始化时会发生什么？结合本节"注意力接近均匀"的现象说明。

---

## 五、参考答案与解析

### Q1 — 答案：A

逐项计算（d = 768，FFN 3072）：

| 部分 | 权重 | bias | 小计 |
|------|------|------|------|
| qkv | `768 × 2304 = 1,769,472` | 2,304 | 1,771,776 |
| out | `768 × 768 = 589,824` | 768 | 590,592 |
| fc1 | `768 × 3072 = 2,359,296` | 3,072 | 2,362,368 |
| fc2 | `3072 × 768 = 2,359,296` | 768 | 2,360,064 |
| ln1 + ln2 | — | — | `4 × 768 = 3,072` |
| 合计 | | | **7,087,872** |

`12 × 7,087,872 + 1,536（最终 LN） = 85,056,000`，与 demo 打印的 `vit params : 85,056,000` 一致。B 漏了所有线性层的 bias；C 只有线性层权重；D 只是 FFN 权重。讲义表格"about 7.1M"指的就是这个量级。

### Q2 — 答案：C

LayerNorm 对每个 token 在特征维上做 `(x − μ) / sqrt(σ² + ε) · γ + β`。初始化时 γ = 1、β = 0，输出的 768 个分量均值 0、方差约 1，于是 L2 范数 `= sqrt(Σ x_i²) = sqrt(768 · 1) ≈ 27.7128`。实测 27.713，差异来自 `eps = 1e-6`。讲义说"The CLS norm drifts upward as the layers compose, then stabilizes at the final LayerNorm"——"stabilizes"其实就是被 LN 重新标准化。B 错，LN 不是裁剪；D 无依据。

### Q3 — 答案：D

`qkv(x)` 输出 `(b, n, 2304)`，`reshape(b, n, 3, h, hd)` 把 2304 拆成"3 个矩阵 × 12 头 × 64 维"，`permute(2, 0, 3, 1, 4)` 把维度重排为 `(3, b, h, n, hd)`。于是 `qkv[0]`、`qkv[1]`、`qkv[2]` 分别是 `(b, h, n, hd)` 的 Q、K、V，可以直接做批量矩阵乘。这种"先 3 后头"的拆分顺序必须与权重的含义一致——加载外部预训练权重时如果对方的布局是 `(h, 3, hd)`，就需要转换。

### Q4 — 答案：B

真实的 block 前向是 `x + attn(ln1(x))`，而 demo 直接 `attn(encoder.front(img))`。我们实测：绕过 `ln1` 时 CLS 行的标准差约 2.1e-5（最大 0.005124、最小 0.005032，均值 1/197 = 0.005076）；加上 `ln1` 后标准差约 1.0e-3（最大 0.0073、最小 0.0031）。两种情况下注意力都接近均匀（随机初始化），但绕过 `ln1` 让 CLS（范数只有 0.53）产生的 query 几乎只剩 bias，与各 key 的点积差异极小，于是更加均匀。A 错，行和为 1.000000 说明 softmax 正确；C 不是主因；D 错，`store_attn` 只是保存一份 `detach()` 的副本。

### Q5 — 答案：C

ViT encoder 是双向的（讲义："No mask"）。讲义原文又说"The decoder-side cross-attention in lesson 61 will use a causal mask"，但第 61 节讲义明确写的是"causal mask for self-attention, no mask for cross-attention"——因果性约束的是**文本 token 之间**不能看未来，而图像整体对每个文本位置都是已知的，cross-attention 不需要 mask。两节讲义在这一点上互相矛盾，以第 61 节为准。A 错，图像没有"未来"；B 是第 59 节讲义的错误说法；D 无依据。

### Q6 — 答案：A

每层乘加（MAC）估算，N = 197、d = 768：

- FFN：`2 × N × d × 4d = 8Nd² ≈ 9.30 亿`
- QKV + 输出投影：`4Nd² ≈ 4.65 亿`
- `QKᵀ` + `attn @ V`：`2N²d ≈ 0.60 亿`

FFN 约占 64%。注意力的 `N²` 项只有在序列很长时才会占主导：当 `2N²d` 与 `12Nd²` 可比，即 `N ≈ 6d ≈ 4600` 时，两者相当。这与讲义练习 4 的结论一致："The MLP layer dominates wall time, not attention"（实际耗时还受内存访问、softmax 等影响，以 profiler 为准）。

### Q7 — 答案：D

pre-LN 的残差主干是 `x ← x + f(LN(x))`：每个子层的输出直接相加，主干上没有任何归一化，所以范数一般随深度增长（实测 0.534 → 13.69 → 19.96 → 24.63 → 28.79 → 32.47 → 35.80）。这也是 pre-LN **必须**在最后加一个 LayerNorm 的原因：否则下游头看到的特征尺度随深度变化。A 错，softmax 权重和恰为 1；B 错，GELU 对正数近似恒等、对负数压缩，不会系统性放大；C 错，位置编码只在前端加一次。

### Q8 — 答案：B

本节：前端 591,360（投影 + CLS，正弦位置 0 参数）+ 85,056,000 = 85,647,360。若改用可学习位置 `197 × 768 = 151,296`，并加一个 1000 类分类头 `768 × 1000 + 1000 = 769,000`，合计 `85,647,360 + 151,296 + 769,000 = 86,567,656`，即常说的约 86.6M。A、C、D 都不符合代码（12 层、`mlp_ratio = 4.0`、`qkv` 带 bias）。讲义表格把"12 blocks about 85M、plus front end about 86M total"写成了约数。

### Q9 — 参考答案

1. 区别：(1) 绕过了 `ln1`，输入尺度和分布与真实前向不同；(2) 只能观察 block 0；(3) 这次调用没有放在 `torch.no_grad()` 里，会建立不必要的计算图。所以它反映的不是模型真正使用的注意力。
2. 正确做法——让 `store_attn` 沿完整前向传下去（代码本身已支持）：

   ```python
   import math, torch
   with torch.no_grad():
       encoder(img, store_attn=True)                      # 每个 block 的 attn.last_attn 都被保存
   for i, blk in enumerate(encoder.vit.blocks):
       a = blk.attn.last_attn[0, :, 0]                    # (heads, keys)：CLS 这一行
       ent = -(a * a.clamp_min(1e-12).log()).sum(-1).mean().item()
       print(f"layer {i:2d}  CLS entropy {ent:.4f}  (uniform {math.log(a.shape[-1]):.4f})")
   ```

   实测（`torch.manual_seed(0)` 初始化）：layer 0 熵 5.2704、layer 5 熵 5.2756、layer 11 熵 5.2795，均匀分布熵 5.2832，最大权重不到 0.01——随机初始化的 ViT 注意力几乎均匀。
3. 原因：权重随机且量级小，Q、K 的点积在 `1/√64` 缩放后彼此差别很小，softmax 输入接近常数，输出就接近均匀。训练后注意力才会变得尖锐、有结构；讲义练习 1 用"注意力熵"衡量 register tokens 对注意力图平滑度的影响，比较时要用**训练后**的模型。

### Q10 — 参考答案

```python
class MultiHeadSelfAttention(nn.Module):
    def forward(self, x, store_attn=False, attn_mask=None):
        b, n, d = x.shape
        h, hd = self.cfg.heads, self.cfg.head_dim
        q, k, v = self.qkv(x).reshape(b, n, 3, h, hd).permute(2, 0, 3, 1, 4)
        scores = (q @ k.transpose(-2, -1)) * self.scale          # (b, h, n, n)
        if attn_mask is not None:
            if attn_mask.shape[-2:] != (n, n):
                raise ValueError(f"mask shape {tuple(attn_mask.shape)} != ({n}, {n})")
            scores = scores.masked_fill(~attn_mask, float("-inf"))  # 广播到 (b, h, n, n)
        attn = F.softmax(scores, dim=-1)
        ...

class Block(nn.Module):
    def forward(self, x, store_attn=False, attn_mask=None):
        x = x + self.attn(self.ln1(x), store_attn=store_attn, attn_mask=attn_mask)
        x = x + self.ffn(self.ln2(x))
        return x

causal = torch.tril(torch.ones(n, n, dtype=torch.bool))          # 下三角：只能看自己和过去
```

验证因果性的测试思路：随机输入 `x`，复制一份 `x2` 并只修改最后一个位置 `x2[:, -1] += 1`；用因果 mask 前向后，除最后一个位置外的所有输出应 `allclose`。另外检查 `last_attn` 的严格上三角全为 0。注意：若某一行被全部屏蔽（例如 padding mask 遮住了所有 key），`-inf` 会让 softmax 输出 NaN，需要至少保留一个可见位置或改用一个很大的负数。也可以直接调用 `F.scaled_dot_product_attention(q, k, v, attn_mask=..., is_causal=...)`。

### Q11 — 参考答案

```python
class VisionEncoder(nn.Module):
    def __init__(self, cfg=None, num_registers: int = 4):
        super().__init__()
        self.cfg = cfg or ViTConfig()
        self.front = VisionFrontEnd(self.cfg.front_end_config())
        self.vit = ViT(self.cfg)
        self.num_registers = num_registers
        if num_registers > 0:
            self.registers = nn.Parameter(torch.zeros(1, num_registers, self.cfg.hidden))
            nn.init.trunc_normal_(self.registers, std=0.02)

    def forward(self, x, store_attn=False):
        tokens = self.front(x)                                   # (B, 1+N, D)，已含位置编码
        if self.num_registers > 0:
            reg = self.registers.expand(tokens.shape[0], -1, -1)  # 不加位置编码
            tokens = torch.cat([tokens[:, :1], reg, tokens[:, 1:]], dim=1)
        tokens = self.vit(tokens, store_attn=store_attn)
        if self.num_registers > 0:                               # 输出时去掉 registers
            tokens = torch.cat([tokens[:, :1], tokens[:, 1 + self.num_registers:]], dim=1)
        return tokens, tokens[:, 0]
```

要点：registers 在前端加完位置编码**之后**插入，所以不带位置；插在 CLS 之后，保证 `tokens[:, 0]` 仍是 CLS；ViT block 对序列长度不敏感，无需改动。返回前剥离 registers，下游看到的形状依旧是 `(B, 197, D)`。

### Q12 — 参考答案

已用代码实例化验证。

1. 一个 block（d = 1024，FFN 4096）：
   - qkv：`1024 × 3072 + 3072 = 3,148,800`
   - out：`1024 × 1024 + 1024 = 1,049,600`
   - fc1：`1024 × 4096 + 4096 = 4,198,400`
   - fc2：`4096 × 1024 + 1024 = 4,195,328`
   - 两个 LN：`4 × 1024 = 4,096`
   - 合计 **12,596,224**；24 个 block + 最终 LN（2,048）= **302,311,424**。
2. 前端：`3 × 16 × 16 × 1024 + 1024 = 787,456`，加 CLS 1024，共 **788,480**；encoder 总计 303,099,904。
3. `12,596,224 / 7,087,872 ≈ 1.777`，而 `(1024/768)² ≈ 1.778`。因为 block 参数几乎全部来自 `d × d` 级别的矩阵（`12d²`），bias 和 LN 只是 `O(d)` 的零头；宽度变为 4/3 倍，参数变为 16/9 倍。总参数还要再乘以深度比 24/12 = 2。

### Q13 — 参考回答要点

- **前向**（B × 197 × 768）：
  1. `h = LN1(x)` → `(B, 197, 768)`；
  2. `qkv = h @ W_qkv + b` → `(B, 197, 2304)` → reshape/permute → Q、K、V 各 `(B, 12, 197, 64)`；
  3. `scores = Q Kᵀ / 8` → `(B, 12, 197, 197)`，`softmax` 按最后一维；
  4. `o = attn @ V` → `(B, 12, 197, 64)` → transpose + reshape → `(B, 197, 768)` → `W_out` 投影；
  5. `x = x + o`（残差 1）；
  6. `x = x + fc2(GELU(fc1(LN2(x))))`，中间 `(B, 197, 3072)`（残差 2）。
- **参数分布**：每 block 约 7.09M，FFN 约 4.72M（2/3），注意力投影约 2.36M（1/3）；12 层共约 85M。
- 加分点：说明形状在 block 内外保持不变，这是可以任意堆叠的前提；整个 encoder 最后还有一个 LN。

### Q14 — 参考回答要点

- **Post-LN**（原始 Transformer）：`x = LN(x + f(x))`，LN 位于残差主干上。深层时梯度要穿过每一层的 LN，初期训练不稳定，通常依赖仔细的 learning-rate warmup。
- **Pre-LN**：`x = x + f(LN(x))`，主干是一条恒等路径，梯度可以直达底层，深模型更容易训练（讲义："the gradient flow at depth 12+ is night and day"）。
- **代价 / 副作用**：
  - 主干不归一化，激活范数随深度增长（本节实测 0.53 → 35.8），必须在最后加 LN；
  - 深层子层的输出相对主干越来越"小"，有研究认为这会降低深层的有效贡献；
  - 讲义说 pre-LN "trains stably without learning-rate warm-up tricks"，这有些夸张——实践中 ViT 训练仍普遍使用 warmup，pre-LN 只是降低了对 warmup 的敏感度。
- 加分点：提到 RMSNorm、QK-Norm 等进一步稳定训练的变体（以具体论文为准）。

### Q15 — 参考回答要点

- **CLS pooling**（本节）：一个可学习 token 在每层通过注意力汇聚全局信息，最终取第 0 个位置；简单，但只用一个向量，且依赖训练让它学会"总结"。
- **平均池化**：对所有 patch token 取平均；无额外参数、对位置更"公平"；讲义提到 SigLIP 使用平均池化（第 59 节"Use It"）。
- **注意力池化**：用一个（或多个）可学习 query 对所有 token 做一次 cross-attention，加权汇总，表达力更强。
- **register tokens**（DINOv2）：额外的可学习 token，吸收全局统计、让 patch 的注意力图更干净；本身不作为输出。
- **VLM 中**：通常不只取一个池化向量，而是把全部（或下采样后的）patch token 经投影层送给语言模型，保留空间细节；第 60 节为了演示对齐才只用 CLS。
- 常见误区：以为 CLS 天生包含图像信息——在前端它对所有图像都一样（第 58 节测试），全靠后续注意力。

### Q16 — 参考回答要点

- **问题**：1024/16 = 64，`64² = 4096` 个 token。注意力分数矩阵 `4096²` 每个头约 1677 万个元素，12 头、fp32 时单层约 0.8 GB，且注意力的 `N²` 项开始与 MLP 相当（Q6 中 `N ≈ 6d` 的分界）；激活显存随 batch 与层数线性增长。
- **计算侧**：用 `F.scaled_dot_product_attention`（FlashAttention / memory-efficient kernel，不显式存储 `N × N` 矩阵）——本节手写实现与它数值一致（我们实测最大误差 1e-7）；混合精度 bf16/fp16；`torch.compile`。
- **序列侧**：更大的 patch、窗口注意力或局部-全局混合注意力、token 合并/剪枝、先低分辨率全局再高分辨率局部裁剪（tiling）、动态分辨率。
- **训练侧**：梯度检查点（activation checkpointing）、更小 batch + 梯度累积。
- **度量**：按讲义练习 4 用 `torch.profiler` 实测，而不是凭直觉判断瓶颈。

### Q17 — 参考回答要点

- **原因**：若 q、k 的分量独立、均值 0、方差 1，则点积 `q · k` 的方差为 `d_k`；d_k = 64 时标准差为 8，softmax 输入跨度很大，输出接近 one-hot，梯度几乎为 0（饱和）。乘以 `1/√d_k` 把方差拉回约 1。
- **去掉会怎样**：初始化阶段注意力可能过早变得尖锐、随机地集中到少数 token 上，梯度信号很弱，训练不稳定。
- **与本节现象的关系**：本节 `nn.Linear` 默认初始化下 Q、K 的量级较小，再乘以 `1/8`，softmax 输入几乎是常数，所以注意力接近均匀（熵 5.27 vs 均匀 5.28）。这对训练起点是好事——每个 token 先"平均地"看所有 token，梯度能流向所有位置；随着训练，注意力逐渐变得有选择性。
- 加分点：缩放因子写在 `self.scale = 1.0 / math.sqrt(cfg.head_dim)`，用的是 `head_dim` 而不是 `hidden`；`F.scaled_dot_product_attention` 默认也使用 `1/√(最后一维)`。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 58 视觉 Encoder 的图像 Patches](../../58-vision-encoder-patches/docs/zh.md)：本节直接加载的 `VisionFrontEnd`。
- [阶段 19 · 33 多头 Self-Attention](../../33-multihead-self-attention/docs/zh.md)、[阶段 19 · 34 从零实现 Transformer 模块](../../34-transformer-block/docs/zh.md)：文本侧同一套 block，区别只在 mask。
- [阶段 07 · 03 多头 Attention](../../../07-transformers-deep-dive/03-multi-head-attention/docs/zh.md)：拆头与合头。
- [阶段 07 · 09 Vision Transformers (ViT)](../../../07-transformers-deep-dive/09-vision-transformers/docs/zh.md)、[阶段 04 · 14 Vision Transformers (ViT)](../../../04-computer-vision/14-vision-transformers/docs/zh.md)：ViT 的整体视角。

### 本节被哪些后续内容用到
- [阶段 19 · 60 用于 Modality Alignment 的投影层](../../60-projection-layer-modality-align/docs/zh.md)：冻结本节的 encoder，用 CLS 训练投影层。
- [阶段 19 · 61 Cross-Attention 融合](../../61-cross-attention-fusion/docs/zh.md)：文本 query 关注本节输出的视觉 token（注意那里的 mask 规则）。
- [阶段 19 · 62 视觉与语言联合 Pretraining](../../62-vision-language-pretraining/docs/zh.md)：对比学习预训练这个 encoder。
- [阶段 12 · 02 CLIP 与视觉语言对比 Pretraining](../../../12-multimodal-ai/02-clip-contrastive-pretraining/docs/zh.md)：CLIP 图像塔就是这样的 ViT。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：高分辨率 ViT 的注意力加速。

### 延伸关键词
`pre-LN / post-LN` · `fused qkv` · `scaled dot-product attention` · `F.scaled_dot_product_attention` · `GELU` · `mlp_ratio` · `CLS pooling` · `mean pooling` · `attention pooling` · `register tokens` · `attention entropy` · `ViT-B/L/H` · `activation checkpointing`
