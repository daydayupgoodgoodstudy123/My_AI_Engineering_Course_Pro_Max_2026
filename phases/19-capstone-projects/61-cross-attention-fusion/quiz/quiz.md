# 测验 · Cross-Attention 融合（Cross-Attention Fusion）

> **阶段 19 · 综合项目 · 第 61 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Early fusion vs late fusion | early fusion 把图像 token 与文本 token 拼成一条序列（Chameleon、Emu3）；late fusion 让文本与视觉保持两条流，在每个 block 里用 cross-attention 架桥（Flamingo、BLIP-2、IDEFICS） |
| 2 | Cross-attention 的定义 | Q 来自文本流，K、V 来自视觉 memory：`softmax(Q_text · K_imgᵀ / √d) · V_img` |
| 3 | 形状规律 | Q `(B,H,Nt,d)`，K/V `(B,H,Nv,d)`，分数 `(B,H,Nt,Nv)`，输出 `(B,Nt,hidden)`——**输出长度永远跟着 query 走**，与 Nv 无关 |
| 4 | 两种 mask 纪律 | 文本 self-attention 用 `(Nt,Nt)` 下三角因果 mask；单图 + caption 的 cross-attention **不加 mask**，因为图像在生成前已完全可见、patch 之间没有时间顺序 |
| 5 | Decoder block 组成 | 三个 pre-LN 子层：`x += self_attn(ln1(x))` → `x += cross_attn(ln2(x), memory)` → `x += ffn(ln3(x))`，每个子层有自己的 LayerNorm |
| 6 | 图像侧 KV cache | 图像 memory 在整个解码期间不变，其 K/V 投影可以每层只算一次、每个 decode step 复用；这是 late fusion 生成便宜的原因 |
| 7 | 代价 | 每个 block 多一个注意力子层；cross-attention 分数矩阵是 `Nt × Nv`，图像分辨率高时（如 Nv = 576）成为主导开销 |
| 8 | Flamingo tanh gate | 在 cross-attention 残差上乘 `tanh(α)`、α 初始化为 0：初始时模型等价于纯文本 LM，再逐步"打开"图像通路 |
| 9 | Q-Former（BLIP-2） | 一组固定的 32 个可学习 query 通过 cross-attention 读取图像特征，再投影到 LM 的 embedding 空间——本质上也是 cross-attention |
| 10 | 形状校验 | 把 mask 形状、batch 不一致、KV cache 形状错误变成显式 `ValueError`，而不是让 loss 曲线"静默地坏掉" |

### 核心技能（能动手做到）

- [ ] 用 PyTorch 写出多头 cross-attention：Q 与 KV 使用不同的投影（`q_proj: hidden→hidden`，`kv_proj: vision_dim→2·hidden`），并说清每一步张量形状
- [ ] 写出因果 self-attention，正确使用 `torch.tril` 布尔 mask 与 `masked_fill(~mask, -inf)`
- [ ] 手算本节 `VisionLanguageDecoder` 的参数量 4,746,752，并说出 cross-attention 子层与 self-attention 子层为何参数一样多
- [ ] 区分"同一次前向内复用 K/V"与"跨 decode step 复用 K/V"，能写出真正一次构建、多步复用的图像 KV cache
- [ ] 在 cross-attention 残差上加 Flamingo tanh gate，并验证 gate = 0 时输出与图像无关
- [ ] 为多图交错（interleaved）输入构造 `(Nt, Nv)` 的 cross-attention mask，并处理"某行全被屏蔽"导致 NaN 的问题

---

## 二、基础自测（选择题）

**Q1.** 关于 early fusion 与 late fusion，下列说法正确的是：

- A. early fusion 指视觉 encoder 先于文本 decoder 运行，late fusion 指视觉 encoder 后运行
- B. late fusion 把图像 token 和文本 token 拼接成一条序列，再做统一的 self-attention
- C. early fusion 把图像 token 与文本 token 拼成一条序列；late fusion 让两条流分开，文本在每个 block 里通过 cross-attention 读取图像
- D. late fusion 中图像流需要在每个 decode step 重新经过视觉 encoder

**Q2.** 本节默认配置：`hidden = 256`、`heads = 8`、文本长度 `Nt = 10`、图像 token 数 `Nv = 197`、batch = 2。`CrossAttention.forward` 的**输出**形状是：

- A. `(2, 10, 256)`
- B. `(2, 207, 256)`
- C. `(2, 197, 256)`
- D. `(2, 10, 197)`

**Q3.** 一个同时包含 self-attention 与 cross-attention 的 decoder block（单图 + 一段 caption）中，哪一个需要因果 mask？

- A. 两个都需要
- B. 只有 cross-attention 需要，因为图像 patch 也是按光栅顺序排列的
- C. 两个都不需要，训练时用 teacher forcing 就足够
- D. 只有文本 self-attention 需要；图像在生成前已完全可见，cross-attention 不加 mask

**Q4.** 同样的配置下（B=2、H=8、Nt=10、Nv=197、head_dim=32），cross-attention 内部 `scores = q @ k.transpose(-2, -1)` 的形状是：

- A. `(2, 8, 10, 10)`
- B. `(2, 8, 10, 197)`
- C. `(2, 8, 197, 197)`
- D. `(2, 10, 8, 197)`

**Q5.** 图像侧的 K/V 能在整个解码过程中只算一次、反复复用，根本原因是：

- A. 图像 memory 在解码过程中不随新生成的文本 token 变化，`kv_proj(memory)` 的结果也就不变
- B. PyTorch 的 `nn.Linear` 会自动缓存上一次的输出
- C. cross-attention 不需要 softmax，所以结果可以直接累加
- D. 文本 token 的 Q 也不会变化，所以整个注意力输出都能缓存

**Q6.** 默认配置下（`hidden = vision_dim = 256`，所有 Linear 带 bias），一个 `CrossAttention` 子层的参数量是：

- A. 65,792
- B. 131,584
- C. 197,376
- D. 263,168

**Q7.** `causal_mask(length)` 返回 `torch.tril(torch.ones(length, length, dtype=torch.bool))`，在 `CausalSelfAttention` 中这样使用：`scores.masked_fill(~mask..., float("-inf"))`。下列理解正确的是：

- A. `mask[i, j] = True` 表示位置 i **不能**看位置 j
- B. `mask[i, j] = True` 表示位置 i **可以**看位置 j（j ≤ i）；取反后把 j > i 的分数填成 −∞
- C. 因为对角线是 True，位置 i 看不到自己
- D. `masked_fill` 会把 True 的位置设为 −∞，所以 mask 的上三角是被保留的部分

**Q8.** 讲义练习 1 要在 cross-attention 残差上加 Flamingo 风格的 tanh gate：`x = x + tanh(α) · cross_attn(ln2(x), memory)`，α 初始化为 0。下列说法正确的是：

- A. α = 0 时 cross-attention 的所有参数都会得到较大的梯度，因此训练更快
- B. α = 0 时 `tanh(α) = 1`，模型一开始就完全使用图像信息
- C. α = 0 时该 block 的输出与图像 memory 无关，模型初始等价于纯文本 decoder，随后 α 被训练逐渐"打开"图像通路
- D. gate 的作用是替代 LayerNorm

---

## 三、动手 / 代码题

**Q9.** `main()` 最后一段打印 "cross-attention output norm per text position (head 0, sample 0)"：

```python
    block = decoder.blocks[0]
    ln_x = block.ln2(decoder.tok_emb(text_ids) + decoder.pos_emb(torch.arange(10)))
    with torch.no_grad():
        cross_out = block.cross_attn(ln_x, memory)
    norms = cross_out[0].norm(dim=-1).tolist()
```

1. 这段代码真的是"head 0"的输出范数吗？`cross_out[0]` 的形状是什么、范数是在什么维度上算的？
2. 在真实前向中，第 0 个 block 的 `ln2` 的输入是什么？这里的 `ln_x` 少了哪一步？
3. 打印出的 10 个范数都在 0.75–0.81 之间、非常接近。结合"随机初始化 + 随机 memory"解释为什么。

**Q10.** 运行结果显示 `max drift cache vs uncached : 0.000000e+00`，讲义据此说"KV-cache 重用检查确认相同 logits"。

```python
    def forward(self, text_ids, memory, use_cache=False):
        ...
        cache = self.build_kv_cache(memory) if use_cache else [None] * len(self.blocks)
        for block, kv in zip(self.blocks, cache):
            x = block(x, memory=memory, text_mask=mask, kv_cache=kv)
```

1. 为什么 drift 恰好是 0 而不是 1e-7 量级？
2. 这个检查**没有**证明哪件事？现有 `forward` 在逐 token 生成时能省掉多少图像 K/V 计算？
3. 写一个 `greedy_caption(decoder, memory, bos_id, steps)`：图像 KV cache 在循环外只构建一次，循环内每步复用。

**Q11.** 完成讲义练习 1：写一个 `GatedDecoderBlock(DecoderBlock)`，在 cross-attention 残差上加 `tanh(gate)`，`gate` 初始化为 0。然后回答：

1. 如何用两个不同的随机 memory 验证"gate = 0 时 block 输出与图像无关"？
2. gate = 0 时对 `out.sum()` 反向传播，`gate.grad` 与 `cross_attn.q_proj.weight.grad` 分别是什么情况？这对训练意味着什么？

**Q12.** 讲义练习 2：同一个 decoder 消费交错的"图 0、文本段 0、图 1、文本段 1"。设 memory 前 5 个 token 属于图 0、后 5 个属于图 1；文本 token 0–3 属于段 0、4–7 属于段 1，规则是"每段文本只看紧挨在它前面的那张图"。

1. 写出构造 `(Nt, Nv)` 布尔 mask 的一行代码，并画出结果。
2. 如果序列开头还有两个文本 token 出现在任何图像之前（段号记为 −1），对它们的 cross-attention 行直接 `masked_fill(-inf)` 再 softmax 会发生什么？应该如何处理？
3. 现有 `CrossAttention.forward` 需要改哪些地方才能接收这个 mask？

---

## 四、面试高频题

**Q13.**（基础必考）self-attention 和 cross-attention 的区别是什么？请用 vision-language decoder 举例，写出 Q、K、V 的来源以及分数矩阵和输出的形状。

**Q14.**（原理深挖）early fusion（Chameleon、Emu3）和 late fusion（Flamingo、BLIP-2）各有什么优缺点？如果要求"加入视觉能力后纯文本能力不能退化"，你会选哪种，为什么？

**Q15.**（工程实践）一个图像描述（captioning）服务用本节这种 late-fusion decoder。请分析单次请求的计算与显存开销，说明图像侧 KV cache 和文本侧 KV cache 各缓存什么、多大，以及高分辨率图像（Nv 从 197 增到 576 甚至更多）时你会怎么优化。

**Q16.**（场景设计）要支持"多张图片与多段文本交错"的多轮对话（例如用户先发图 A 提问，再发图 B 让模型对比），你会如何设计 cross-attention 的 mask、位置信息和缓存？

**Q17.**（追问型）面试官问："你说 cross-attention 不需要 mask，那 batch 里每张图的 token 数不一样怎么办？" 请回答，并说明在哪些情况下 cross-attention 必须加 mask。

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Concatenating image tokens and text tokens into one sequence is one fusion option (early fusion...). Cross-attention is the other (late fusion...)"。A 把"融合"理解成运行先后顺序，概念错误；B 描述的是 early fusion；D 恰好相反——late fusion 的优点之一就是图像流"每张图只算一次，在每个解码步复用"。

### Q2 — 答案：A

Cross-attention 的输出长度由 **query** 决定：`(attn @ v)` 为 `(B,H,Nt,hd)`，`transpose(1,2).reshape(b, nt, d)` 得到 `(2, 10, 256)`。B 把两条流长度相加（那是 early fusion 拼接后的长度）；C 是 memory 的形状；D 是去掉头维后的注意力权重形状，不是输出。测试 `test_output_shape_independent_of_key_length` 正是验证 Nv = 10 和 Nv = 50 时输出都是 `(2, 6, hidden)`。

### Q3 — 答案：D

文本是自回归生成的，位置 t 不能看 t 之后的文本，所以文本 self-attention 用下三角因果 mask。图像在任何文本生成之前就已完整给出，patch 之间没有时间顺序，也不存在"信息泄漏"问题，所以 cross-attention 不加 mask（讲义 "Why no mask on cross-attention"）。B 错：光栅顺序只是存储顺序，不是生成顺序；C 错：teacher forcing 恰恰需要因果 mask 才不会让模型偷看答案。我们实测：把第 9 个文本 token 换掉，位置 0–8 的 logits 变化为 0.0，只有位置 9 变化（约 2.11），证明因果 mask 生效。

### Q4 — 答案：B

`q` 为 `(2, 8, 10, 32)`，`k.transpose(-2, -1)` 为 `(2, 8, 32, 197)`，相乘得 `(2, 8, 10, 197)`：每个样本、每个头一个 `Nt × Nv` 的矩阵，softmax 在最后一维（197 个图像 token）上做。A 是文本 self-attention 的分数形状；C 是图像内部 self-attention（ViT 里）的形状；D 维度顺序错。

### Q5 — 答案：A

图像 memory 在解码开始前就固定，`kv_proj(memory)` 与文本无关，所以每层的 K、V 可以只算一次。B 错：`nn.Linear` 没有任何缓存；C 错：cross-attention 有 softmax；D 错：每个 decode step 都有新 token 的 Q，注意力输出必须重算，能缓存的只有 K/V。

### Q6 — 答案：D

`q_proj`: `256×256 + 256 = 65,792`；`kv_proj`: `256×512 + 512 = 131,584`；`out`: `65,792`。合计 `263,168`（我们用 `sum(p.numel())` 实测验证）。它与 `CausalSelfAttention`（`qkv: 256×768+768 = 197,376` + `out: 65,792` = 263,168）完全相等——因为 `vision_dim == hidden`，两者都是"三个 hidden×hidden 投影 + 一个输出投影"。A 是单个 `q_proj` 或 `out`；B 是 `kv_proj`；C 是 self-attention 的合并 `qkv`。若 `vision_dim ≠ hidden`，cross-attention 的 `kv_proj` 参数量会随 `vision_dim` 变化。

### Q7 — 答案：B

docstring 写明 "Cell [i, j] is True if token i may attend to token j (j <= i)"。代码用 `~mask` 取反，把 **False**（j > i，未来位置）的分数填为 −∞。A 把语义说反了；C 错：对角线为 True，自己可以看自己（这也保证每一行至少有一个可见位置，softmax 不会出现全 −∞ 的 NaN）；D 把 `masked_fill` 的作用对象说反——它填的是传入的那个布尔张量为 True 的位置，而这里传入的是 `~mask`。

### Q8 — 答案：C

`tanh(0) = 0`，cross-attention 残差被乘以 0，block 退化为"self-attention + FFN"的纯文本 block。我们实测：gate = 0 时用两个不同的随机 memory，block 输出最大差异为 0.0。讲义："The gate starts at 0; the model recovers text-only behavior before mixing the image stream in." A 错：gate = 0 时 cross-attention 内部参数的梯度恰好为 0（见 Q11）；B 错：`tanh(0) = 0` 不是 1；D 错：gate 与 LayerNorm 无关。

### Q9 — 参考答案

1. **不是 head 0**。`cross_out` 是 `out` 投影之后的结果，形状 `(2, 10, 256)`；`cross_out[0]` 取的是 **sample 0**，形状 `(10, 256)`；`.norm(dim=-1)` 是在全部 256 维（8 个头拼接后再经输出投影）上求 L2 范数。标签里的 "head 0" 不符合实际。要看单头，需要在 `CrossAttention` 内部取 `(attn @ v)[:, 0]`（形状 `(B, Nt, 32)`），且是输出投影之前。
2. 真实前向中，block 0 的 `ln2` 输入是 `x + self_attn(ln1(x))`，其中 `x = tok_emb + pos_emb`。这里直接用 `ln2(tok_emb + pos_emb)`，**跳过了 self-attention 残差**。所以打印值只是"示意性"的，并不是真实前向中的中间量。另外 `ln_x` 是在 `torch.no_grad()` 外面计算的，会多建一份计算图（不影响结果，只是多余开销）。
3. memory 是标准正态随机张量、权重是随机初始化，每个文本位置的 query 不同，但随机 K 下注意力分布都接近均匀（197 个 token 的平均），输出近似"所有 V 的平均"再经投影——不同位置的输出因此非常相似、范数接近。这说明未训练的 cross-attention 还没有学会"把不同的词对齐到不同的区域"，打印值只能用来检查数值是否正常（没有 NaN、量级合理）。

### Q10 — 参考答案

1. 两条路径执行的是**完全相同的浮点运算**：`use_cache=True` 只是先在 `build_kv_cache` 里调用同一个 `project_memory(memory)`，再把结果传给 block；`use_cache=False` 是在 block 内部调用同一个函数。同样的输入、同样的算子、同样的顺序，结果逐位相同，因此 drift 恰好为 0。
2. 它只证明了"把 `project_memory` 提前算出来再传入"与"在内部算"等价，**没有证明跨 decode step 的复用**。现有 `forward` 每次调用都会重新 `build_kv_cache(memory)`；如果用它逐 token 生成 N 个 token，图像 K/V 会被算 N 次，一次也没有省。另外文本侧也没有 self-attention 的 KV cache，每步都要对全部已生成的文本重算。
3. 参考实现（图像 KV 只构建一次）：

```python
@torch.no_grad()
def greedy_caption(decoder, memory, bos_id, steps):
    cache = decoder.build_kv_cache(memory)          # 每层 (k, v)，循环外只算一次
    ids = torch.full((memory.shape[0], 1), bos_id, dtype=torch.long)
    for _ in range(steps):
        nt = ids.shape[1]
        x = decoder.tok_emb(ids) + decoder.pos_emb(torch.arange(nt)).unsqueeze(0)
        mask = causal_mask(nt)
        for block, kv in zip(decoder.blocks, cache):
            x = block(x, memory=memory, text_mask=mask, kv_cache=kv)
        logits = decoder.head(decoder.norm(x))[:, -1]
        ids = torch.cat([ids, logits.argmax(-1, keepdim=True)], dim=1)
    return ids
```

要点：`build_kv_cache` 放在循环外；`steps + 1` 不能超过 `max_text_len = 32`（否则 `pos_emb` 越界）；这里每步仍对全部文本重算 self-attention，若要进一步优化需再加文本侧的增量 KV cache，只计算新 token 的 Q/K/V。

### Q11 — 参考答案

```python
class GatedDecoderBlock(DecoderBlock):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.gate = nn.Parameter(torch.zeros(1))

    def forward(self, x, memory, text_mask, kv_cache=None):
        x = x + self.self_attn(self.ln1(x), mask=text_mask)
        x = x + torch.tanh(self.gate) * self.cross_attn(self.ln2(x), memory, kv_cache=kv_cache)
        x = x + self.ffn(self.ln3(x))
        return x
```

1. 固定文本输入 `x`，分别用两份不同的 `torch.randn(2, 197, 256)` 作为 memory 前向，比较输出差的最大绝对值。我们实际运行得到 **0.0**——gate = 0 时 block 完全不受图像影响。
2. 实测：`gate.grad ≈ 21.36`（非零），`cross_attn.q_proj.weight.grad` 的范数为 **0.0**。原因：输出对 cross 参数的导数要乘上 `tanh(gate) = 0`，而对 gate 的导数是 `(1 − tanh²(gate)) · cross_out`，不为 0。意味着训练初期只有 gate 先动，gate 离开 0 后 cross-attention 参数才开始收到梯度。这正是 Flamingo 的设计意图：在冻结的 LM 上插入新层，初始不扰动 LM 的行为，再平滑地引入图像信息。注意如果 gate 和 cross 参数**同时**是 0 初始化，两者都不会被更新（梯度互相乘 0），所以只能把 gate 置 0，cross 参数仍需正常随机初始化。

### Q12 — 参考答案

1. 构造方法（已实际运行）：

```python
seg_of_text = torch.tensor([0, 0, 0, 0, 1, 1, 1, 1])
img_of_mem  = torch.tensor([0] * 5 + [1] * 5)
mask = seg_of_text[:, None] == img_of_mem[None, :]      # (Nt, Nv) = (8, 10)
```

```text
1 1 1 1 1 0 0 0 0 0
1 1 1 1 1 0 0 0 0 0
1 1 1 1 1 0 0 0 0 0
1 1 1 1 1 0 0 0 0 0
0 0 0 0 0 1 1 1 1 1
0 0 0 0 0 1 1 1 1 1
0 0 0 0 0 1 1 1 1 1
0 0 0 0 0 1 1 1 1 1
```

   这是"只看最近一张图"的规则（Flamingo 的做法）；若改成"看之前所有图"，用 `img_of_mem[None, :] <= seg_of_text[:, None]`。

2. 段号为 −1 的行全为 False，整行分数都是 −∞，`softmax` 得到 `exp(-inf)/0 = NaN`——我们实测这一行 10 个值全是 `nan`，而且 NaN 会通过后续计算污染整个 batch 的 loss。处理方法：①对全屏蔽行在 softmax 后把输出置 0（`attn = attn.nan_to_num(0.0)` 或先算 `has_any = mask.any(-1)` 再乘上去）；②或者让这些位置的 cross-attention 残差直接跳过（Flamingo 的做法是让图像之前的文本 token 不做 cross-attention，输出置零）。用 `-1e9` 代替 `-inf` 不会 NaN，但会变成对所有图像 token 均匀平均，语义是错的。
3. 改动：给 `CrossAttention.forward` 增加 `mask: torch.Tensor | None = None` 参数；校验形状为 `(Nt, Nv)` 或 `(B, Nt, Nv)`；在 softmax 前 `scores = scores.masked_fill(~mask[:, None], -inf)`（广播到头维）；处理全屏蔽行；`DecoderBlock.forward` 与 `VisionLanguageDecoder.forward` 也要把 `cross_mask` 一路传下去——这也正是讲义中 `DecoderBlock.forward(text_tokens, image_tokens, text_mask, cross_mask)` 写法所预留的参数，而当前代码里并没有这个参数。

### Q13 — 参考回答要点

- **self-attention**：Q、K、V 都来自同一条序列。文本 decoder 中 `Q,K,V = f(text)`，分数 `(B,H,Nt,Nt)`，需要因果 mask。
- **cross-attention**：Q 来自一条流，K、V 来自另一条流。vision-language decoder 中 `Q = W_q · text`，`K,V = W_kv · image_memory`，分数 `(B,H,Nt,Nv)`，softmax 在 Nv 维上做，输出 `(B,Nt,hidden)`——长度跟着 query。
- **直观含义**：每个文本 token 发出一个"问题"，在所有图像 patch 中找相关的区域，把这些区域的信息加权汇总回来，实现"把词 grounding 到区域"。
- **投影维度**：K/V 投影的输入维是 `vision_dim`，可以与文本 `hidden` 不同（本节 `kv_proj = Linear(vision_dim, 2·hidden)`），这让 cross-attention 天然承担了一部分模态对齐的作用。
- 加分点：在原始 Transformer 的 encoder-decoder 结构（翻译模型）中，decoder 的 cross-attention 读取 encoder 输出，与这里是同一个机制，只是 encoder 从文本换成了 ViT。

### Q14 — 参考回答要点

- **Early fusion（拼接成一条序列）**：
  - 优点：结构统一，一个 Transformer 处理所有模态，模态间在每一层充分交互；容易扩展到"生成图像 token"（Chameleon、Emu3 用离散图像 token 实现统一的 next-token prediction）。
  - 缺点：图像 token 占用上下文长度，self-attention 代价随 `(Nt+Nv)²` 增长；图像 token 进入 LM 主干后会改变 LM 的分布，纯文本能力可能退化。
- **Late fusion（cross-attention 架桥）**：
  - 优点：文本流保持"干净"，可以冻结原 LM，纯文本能力得以保留（讲义："the text stream stays clean and the model preserves text-only capabilities"）；图像 K/V 每张图只算一次，生成长 caption 也便宜。
  - 缺点：每个 block（或每隔 K 个 block）多一个子层和参数；模态交互只在 cross-attention 处单向发生（文本读图像，图像不读文本）。
- **"纯文本能力不能退化"的选择**：late fusion + 冻结 LM + 零初始化的 tanh gate（Flamingo 配方），初始时等价于原 LM。
- 加分点：LLaVA 这类"投影层 + 把图像 token 拼进 LM 输入"的方案在结构上更接近 early fusion（见第 60 节投影层）；BLIP-2 的 Q-Former 先用 32 个 query 通过 cross-attention 把图像压缩，再投影进 LM，是两者的折中。

### Q15 — 参考回答要点

- **计算**：每层 cross-attention 分数是 `Nt × Nv`，self-attention 是 `Nt × Nt`。讲义练习 3 的设置 `Nt = 64, Nv = 576`：self 分数 4,096 个、cross 分数 36,864 个，cross 是 self 的 **9 倍**（实际计算），高分辨率时 cross-attention 主导开销。
- **图像侧 KV cache**：每层缓存 `K, V`，形状 `(B, H, Nv, hd)`。本节配置下每个样本 `4 层 × 2 × 197 × 256 = 403,456` 个值，FP32 约 1.6 MB（实际计算）。在请求开始时一次性计算，整个解码期间只读不写，不随生成长度增长。
- **文本侧 KV cache**：每层缓存已生成文本 token 的 self-attention K、V，随生成长度线性增长，每步追加一个 token。
- **ViT 只跑一次**：讲义"the heavy ViT runs once"，视觉 encoder 的输出与 cross KV 都在 prefill 阶段完成。
- **高分辨率优化**：
  - 用 Perceiver Resampler（Flamingo）或 Q-Former（BLIP-2，32 个 query）把 Nv 压缩到固定的少量 token；
  - 只在部分层插入 cross-attention（"每 K 个 LM block 插一个"）；
  - patch merge / pooling 降低 token 数；
  - 对 cross KV cache 做低精度存储。
- 常见误区：以为"有 KV cache 就不用重算任何东西"——每步的 Q 和注意力分数仍需计算，cache 省掉的是 `kv_proj(memory)`。

### Q16 — 参考回答要点

- **Cross-attention mask**：为每个样本记录每个文本 token 所属的段号和每个图像 token 所属的图号，构造 `(B, Nt, Nv)` 布尔 mask。规则可选"只看最近一张图"（Flamingo）或"看之前所有图"；对比类问题（"A 和 B 哪里不同"）往往需要后者。
- **全屏蔽行**：出现在第一张图之前的文本没有可看的图像，需要输出置 0，避免 NaN（见 Q12）。
- **位置信息**：给每张图加图像序号 embedding 或在文本中插入 `<image_1>` 之类的标记 token，让模型能区分"图 A"与"图 B"。
- **缓存**：每张新图到来时只为它计算 K/V 并追加到 memory cache，旧图的 K/V 保留；多轮对话中图像 cache 与文本 KV cache 一起随会话保存，超过预算时可淘汰最早的图。
- **batch 处理**：不同样本图片数不同，memory 需要 padding 并配合 key padding mask。
- 加分点：说出 IDEFICS 是 Flamingo 配方的开源复现，交错图文是其训练数据的主要形式。

### Q17 — 参考回答要点

- **"不需要 mask"的前提**：单张图、固定 token 数（如 197 = 196 patch + 1 CLS）、图像在生成前完整可见。此时没有未来信息可泄漏，也没有无效 token。
- **必须加 mask 的情况**：
  1. **Padding**：batch 中图像 token 数不同（任意分辨率、不同图片数），需要 key padding mask 把补齐的 memory 位置屏蔽，否则 query 会注意到无意义的 padding 向量；
  2. **交错多图**：限制每段文本只看对应的图（讲义练习 2、Q12）；
  3. **无图样本**：纯文本样本混在 batch 里，需要让 cross-attention 输出为 0。
- **实现**：mask 形状 `(B, 1, 1, Nv)`（padding）或 `(B, 1, Nt, Nv)`（交错），广播到头维；处理全屏蔽行。
- 加分点：指出本节代码的 `CrossAttention` 没有 mask 参数、只校验 batch 维一致，`memory` 最后一维与 `vision_dim` 不一致时抛出的是 PyTorch 的 `RuntimeError`（矩阵乘形状不匹配）而不是讲义所说的"清晰的 `ValueError`"。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 33 多头 Self-Attention](../../33-multihead-self-attention/docs/zh.md)：本节 `CausalSelfAttention` 的 reshape/permute 拆头写法来自这里。
- [阶段 19 · 34 从零实现 Transformer 模块](../../34-transformer-block/docs/zh.md)：pre-LN 残差 block 结构，本节在其中插入了第三个子层。
- [阶段 19 · 59 Vision Transformer Encoder](../../59-vit-transformer/docs/zh.md)：memory 的 197 个 token（196 patch + CLS）就是 ViT 的输出形状。
- [阶段 19 · 60 用于 Modality Alignment 的投影层](../../60-projection-layer-modality-align/docs/zh.md)：上一节只对齐"一个图像向量与一个 caption 向量"，本节扩展到 token 级对齐。
- [阶段 07 · 05 完整的 Transformer — Encoder + Decoder](../../../07-transformers-deep-dive/05-full-transformer/docs/zh.md)：encoder-decoder 中的 cross-attention 是同一机制。

### 本节被哪些后续内容用到
- [阶段 19 · 62 视觉与语言联合 Pretraining](../../62-vision-language-pretraining/docs/zh.md)：在此类 decoder 上加入 captioning 目标做预训练。
- [阶段 19 · 63 多模态 Evaluation](../../63-multimodal-eval/docs/zh.md)：评估 caption 与检索质量。
- [阶段 12 · 04 Flamingo：面向 Few-Shot VLM 的门控 Cross-Attention](../../../12-multimodal-ai/04-flamingo-gated-cross-attention/docs/zh.md)：tanh gate 与交错图文的完整设计。
- [阶段 12 · 03 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former](../../../12-multimodal-ai/03-blip2-qformer-bridge/docs/zh.md)：32 个 query 的 cross-attention 压缩器。
- [阶段 12 · 11 Chameleon：仅用 Token 的早期融合 Multimodal Models](../../../12-multimodal-ai/11-chameleon-early-fusion-tokens/docs/zh.md)：early fusion 的代表。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：文本侧 KV cache 的实现。

### 延伸关键词
`cross-attention` · `late fusion / early fusion` · `memory tokens` · `causal mask` · `key padding mask` · `gated cross-attention (tanh gate)` · `Perceiver Resampler` · `Q-Former` · `interleaved image-text` · `encoder-decoder attention` · `KV cache`
