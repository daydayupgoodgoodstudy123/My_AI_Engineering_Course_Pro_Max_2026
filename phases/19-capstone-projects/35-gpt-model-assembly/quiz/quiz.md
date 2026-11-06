# 测验 · 组装 GPT 模型（GPT Model Assembly）

> **阶段 19 · 综合项目 · 第 35 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | GPT 的完整计算图 | token embedding + learned 位置 embedding → embedding dropout → N 个 pre-LN block → `final_ln` → LM head → logits `(B, T, V)` |
| 2 | 124M 参考配置 | vocab 50257、context 1024、d_model 768、12 头、12 层；本节代码精确得到 **124,439,808** 个参数（含全部 bias） |
| 3 | 参数分布 | token 表 38,597,376（约 31%）、位置表 786,432（约 0.6%）、12 个 block 共 85,054,464（约 68%）、`final_ln` 1,536 |
| 4 | Weight tying | `self.lm_head.weight = self.tok_embed.weight`，同一个 `Parameter` 用两次；不共享时多 `V × D = 38,597,376` 个参数 |
| 5 | 残差投影缩放初始化 | 所有线性层与 embedding 用 `N(0, 0.02²)`；`out_proj` 与 `fc2` 的权重再乘 `1/√(2·num_layers)`，防止残差流随深度增长 |
| 6 | 位置 id 缓存 | `position_ids = arange(context_length)` 注册为 buffer，前向切片 `[:T]`，避免每次分配 |
| 7 | 自回归生成 | 只取最后一个位置的 logits → 除以 temperature → top-k 截断 → softmax → `multinomial` 采样 → 拼接 |
| 8 | 滑动窗口 | 每步只把最后 `context_length` 个 token 送进模型；超长 prompt 也能生成，但最早的 token 被丢弃 |
| 9 | 采样参数 | T < 1 更尖锐、T > 1 更平坦；top-k = 1 等价于贪心；本节代码要求 T > 0 |
| 10 | 计数与共享 | `model.parameters()` 本身就会对共享参数去重；`state_dict()` 里仍有两个键指向同一张量 |

### 核心技能（能动手做到）

- [ ] 不看代码写出 `GPTModel.__init__` 与 `forward`，包括 weight tying、位置 id buffer 与初始化
- [ ] 手算 GPT-2 Small 的参数量，并解释 124,439,808 每一项的来源
- [ ] 用 `data_ptr()` 或 `is` 验证两个参数是否真正共享存储
- [ ] 实现 temperature、top-k、top-p、贪心与正确的 repetition penalty
- [ ] 解释残差投影缩放初始化的原理，并用实验验证它对残差流尺度的影响
- [ ] 估算一个 GPT 模型的显存与每 token 的前向计算量

---

## 二、基础自测（选择题）

**Q1.** 按本节代码，GPT-2 Small 参考配置（weight tying 开启）的参数量是：

- A. 124,402,944
- B. 124,439,808
- C. 163,037,184
- D. 85,054,464

**Q2.** 关于 `self.lm_head.weight = self.tok_embed.weight`，正确的是：

- A. 这行代码把 embedding 的数值复制给 LM head，之后两者各自训练
- B. 只有在 `torch.no_grad()` 中执行才能共享
- C. 它让两个模块引用同一个 `nn.Parameter`，优化器只更新一个矩阵，两侧的梯度累加到同一个 `.grad` 上
- D. 共享后 `state_dict()` 只剩一个键

**Q3.** 本节 `_scale_residual_projections` 对哪些权重乘了 `1/√(2·num_layers)`？

- A. 所有线性层
- B. 只有 QKV 投影
- C. token embedding 与位置 embedding
- D. 注意力的 `out_proj` 与 MLP 的 `fc2`——这两个线性层的输出直接加到残差流上

**Q4.** 已知 `generate` 的写法：`window = tokens[:, -model.cfg.context_length:]`。tiny 配置 `context_length=64`，prompt 长度 80，生成 4 个新 token。下列说法正确的是：

- A. 每一步送入模型的窗口长度都是 64，最终返回的 `tokens` 形状是 `(1, 84)`
- B. 第一步会因为 80 > 64 报错
- C. 返回的 `tokens` 只保留最后 64 个
- D. 每一步窗口长度递增：80、81、82、83

**Q5.** logits 为 `[1.0, 5.0, 2.0, 4.0, 3.0]`，`temperature=1.0`、`top_k=2`。采样到 id 1（logit 5.0）的概率约为：

- A. 0.636
- B. 0.731
- C. 0.500
- D. 1.000

**Q6.** 关于 `top_k_filter`，正确的是：

- A. 它总是恰好保留 k 个 token
- B. 它会改变保留下来的 logits 的数值
- C. 它在 softmax 之后把概率置 0
- D. 它保留所有 `>= 第 k 大值` 的 logits；若有并列，保留的数量可能多于 k（例如 `[3, 3, 3, 1, 0.5]`、k=2 时保留 3 个）

**Q7.** 用 tiny 配置（`d_model=64`、`num_layers=2`、`vocab_size=512`、`context_length=64`），初始化后输出的 out_proj 权重标准差约为：

- A. 0.010
- B. 0.020
- C. 0.004
- D. 0.0

**Q8.** 讲义练习 4 要求实现"把 prompt 或历史中出现过的 token 的 logit **除以**一个常数（> 1）"的 repetition penalty。这个描述的问题是：

- A. 除法会让 logits 变成 NaN
- B. 除法对负的 logit 反而会**增大**它（如 −2 / 1.3 = −1.54），让已出现过的 token 更容易被采到；正确做法是正 logit 除以、负 logit 乘以惩罚系数
- C. 惩罚应该加在概率上而不是 logits 上
- D. 没有问题

---

## 三、动手 / 代码题

**Q9.** 手算 GPT-2 Small（本节配置）的参数量：

1. 逐项列出 token 表、位置表、一个 block（分注意力、MLP、LN）、`final_ln`，求和得到 124,439,808。
2. demo 中 untied 模型为 163,037,184，差值是多少？为什么说 tying 让 embedding "同时得到输入侧与输出侧的梯度"？
3. 把位置 embedding 换成 sinusoidal（讲义练习 2），参数量变为多少？

**Q10.** `count_parameters` 的实现：

```python
def count_parameters(model: nn.Module) -> int:
    seen: dict[int, int] = {}
    for param in model.parameters():
        seen[id(param)] = param.numel()
    return sum(seen.values())
```

1. 如果改成 `sum(p.numel() for p in model.parameters())`，tied 模型的结果会翻倍吗？
2. 什么情况下用 `id()` 去重仍然必要？`state_dict()` 中 `tok_embed.weight` 与 `lm_head.weight` 是两个键吗？

**Q11.** 为 `generate` 增加 `top_p` 与 `greedy` 两个参数（讲义练习 3、5）。写出 `top_p_filter(logits, top_p)`，并用 logits `[2.0, 1.0, 0.5, 0.0, -1.0]`、`top_p = 0.8` 验证保留了哪几个 token、保留的总概率是多少。

**Q12.** 讲义"Production patterns"第一条说：残差投影若用与其他线性层相同的 std，残差流会随深度增长。请设计一个实验验证 `_scale_residual_projections` 的作用，并预测 12 层、`d_model=192` 时初始化状态下残差流标准差的增长倍数。

---

## 四、面试高频题

**Q13.**（基础必考）从 token ids 到下一个 token 的采样，GPT 的前向与生成要经过哪些步骤？每一步的形状是什么？

**Q14.**（原理深挖）Weight tying 是什么？为什么能用？它有什么好处和潜在问题？

**Q15.**（原理深挖）为什么要把残差投影的初始化标准差乘 `1/√(2N)`？这里的 2 和 N 分别是什么？

**Q16.**（工程实践）124M 的 GPT-2 推理和训练分别大约需要多少显存？每生成一个 token 大约需要多少 FLOPs？本节的 `generate` 有哪些性能问题？

**Q17.**（追问型）temperature、top-k、top-p、repetition penalty 分别解决什么问题？它们的应用顺序有讲究吗？讲义说"temperature near zero collapses to greedy"，本节代码为什么不允许 T = 0？

---

## 五、参考答案与解析

### Q1 — 答案：B

demo 实际输出 `reference params : 124,439,808`，与 Hugging Face GPT-2 的参数量一致（本节注意力和 MLP 都带 bias）。A 是阶段 10 第 04 节代码漏掉注意力 bias 后的数字；C 是 untied 模型（多一份 `50257 × 768`）；D 是 12 个 block 的合计。

### Q2 — 答案：C

把模块属性赋值为另一个 `Parameter`，两个模块就引用同一个对象（实测 `m.lm_head.weight is m.tok_embed.weight` 为 True，`data_ptr()` 相同）。前向中它被用了两次（查表与输出投影），autograd 把两处的梯度累加到同一个 `.grad`。A 是"复制"，讲义明确指出复制会让两者漂移、tying 失去意义；B 不需要；D 错：实测 `state_dict()` 中 `tok_embed.weight` 与 `lm_head.weight` 两个键都在，只是指向同一块存储。

### Q3 — 答案：D

```python
    def _scale_residual_projections(self) -> None:
        scale = 1.0 / math.sqrt(2 * self.cfg.num_layers)
        for block in self.blocks:
            block.attn.out_proj.weight.data.mul_(scale)
            block.mlp.fc2.weight.data.mul_(scale)
```

这两个线性层的输出直接加进残差流，每个 block 加两次、共 `2N` 次。缩小它们的初始化可以让残差流的方差在深度方向上保持稳定。QKV、`fc1` 与 embedding 保持 std 0.02。

### Q4 — 答案：A

`tokens[:, -64:]` 永远只取最后 64 个，所以模型不会报错（`forward` 中 `seq > context_length` 的检查不会触发）；`tokens` 本身持续增长，最终 `(1, 80 + 4) = (1, 84)`，与 demo 的 `generated shape : (1, 84)` 一致。B 错在有滑动窗口；C 错，窗口只影响输入，不截断返回值；D 是没有滑动窗口时的情况。

### Q5 — 答案：B

top-k = 2 保留 5.0 和 4.0，其余为 `-inf`；softmax 只在两者间进行：`e⁵ / (e⁵ + e⁴) = 1 / (1 + e⁻¹) ≈ 0.7311`（已实际计算）。A 是不做 top-k、直接对 `[5,4,3,2,1]` 做 softmax 时最大值的概率（0.6364）；C 忽略了 logit 差；D 是贪心。

### Q6 — 答案：D

```python
    values, _ = torch.topk(logits, top_k, dim=-1)
    threshold = values[..., -1:]
    return torch.where(logits < threshold, torch.full_like(logits, float("-inf")), logits)
```

阈值是第 k 大的值，严格小于阈值的才被屏蔽。并列时保留数可能 > k（实测 `[3, 3, 3, 1, 0.5]`、k=2 保留 3 个）。测试 `test_top_k_filter_keeps_exactly_k` 用的是互不相同的值，所以测不出这一点。B 错：保留下来的 logits 原样不变；C 错：它在 softmax **之前**把 logits 置为 `-inf`。

### Q7 — 答案：A

初始化 std 0.02，再乘 `1/√(2×2) = 0.5`，得到约 0.010（实测 0.00999）。B 是 QKV 等其他线性层（实测 0.0201）；C 是 12 层时的值 `0.02/√24 ≈ 0.0041`。

### Q8 — 答案：B

logit 可以是负数。"除以 1.3"让正 logit 变小（2.0 → 1.54），却让负 logit **变大**（−2.0 → −1.54），惩罚变成了奖励。常见实现（如 Hugging Face transformers 中的 repetition penalty）是：`logit > 0` 时除以 penalty，`logit < 0` 时乘以 penalty（实测 `[2.0, −2.0]` → `[1.54, −2.60]`）。A、C、D 都不对：除法不会产生 NaN；在 logits 上操作是常规做法。

### Q9 — 参考答案

1. 逐项（D = 768）：

| 部分 | 计算 | 参数 |
|------|------|------|
| token embedding | `50257 × 768` | 38,597,376 |
| 位置 embedding | `1024 × 768` | 786,432 |
| 一个 block：注意力 | `768×2304 + 2304 + 768×768 + 768` | 2,362,368 |
| 一个 block：MLP | `768×3072 + 3072 + 3072×768 + 768` | 4,722,432 |
| 一个 block：两个 LN | `4 × 768` | 3,072 |
| 一个 block 合计 | | 7,087,872 |
| 12 个 block | `12 × 7,087,872` | 85,054,464 |
| `final_ln` | `2 × 768` | 1,536 |
| LM head | 与 token 表共享 | 0 |
| **合计** | | **124,439,808** |

2. 差值 `163,037,184 − 124,439,808 = 38,597,376 = 50257 × 768`（demo 的 `assert delta == expected_delta` 通过）。tying 后这个矩阵在前向中被用两次：输入侧是查表（只有本批出现的 token 行有梯度），输出侧是 `x @ Wᵀ`（每一行都有梯度，因为 softmax 覆盖整个词表），两部分梯度累加到同一个参数上。讲义："you also get a slightly cleaner gradient signal because the embedding and head update together"。
3. sinusoidal 位置表不是参数，参数量减少 786,432，变为 **123,653,376**。

### Q10 — 参考答案

1. 不会翻倍。`nn.Module.parameters()` 内部调用 `named_parameters(remove_duplicate=True)`，同一个 `Parameter` 对象只返回一次。我们实测 tiny 模型 `count_parameters` 与朴素求和都是 136,960；`named_parameters()` 返回 28 项，`named_parameters(remove_duplicate=False)` 返回 29 项（多出的就是 `lm_head.weight`）。所以本节的 `id()` 去重是"多一层保险"，不影响结果。
2. 仍然必要的场景：遍历方式不经过 `parameters()` 去重时，例如 `named_parameters(remove_duplicate=False)`、遍历 `state_dict().values()`、或者把多个模型的参数拼在一起统计。`state_dict()` 中确实有两个键（实测 `['tok_embed.weight', 'lm_head.weight']`），`torch.save` 会保留共享关系；但如果用 safetensors 等格式手工保存，往往需要只存一份、加载后重新绑定——第 37 节加载 GPT-2 权重时就要处理这一点。

### Q11 — 参考答案

```python
def top_p_filter(logits: torch.Tensor, top_p: float | None) -> torch.Tensor:
    if top_p is None or top_p >= 1.0:
        return logits
    sorted_logits, idx = torch.sort(logits, descending=True, dim=-1)
    probs = F.softmax(sorted_logits, dim=-1)
    cum = probs.cumsum(dim=-1)
    remove = cum - probs >= top_p            # 在它之前累计概率已经 ≥ p 的 token 去掉
    sorted_logits = sorted_logits.masked_fill(remove, float("-inf"))
    return torch.full_like(logits, float("-inf")).scatter(-1, idx, sorted_logits)
```

在 `generate` 中：

```python
                next_logits = logits[:, -1, :]
                if greedy:
                    next_token = next_logits.argmax(dim=-1, keepdim=True)
                else:
                    next_logits = next_logits / temperature
                    next_logits = top_k_filter(next_logits, top_k)
                    next_logits = top_p_filter(next_logits, top_p)
                    probs = F.softmax(next_logits, dim=-1)
                    next_token = torch.multinomial(probs, num_samples=1)
```

验证（已实际运行）：概率为 `[0.5630, 0.2071, 0.1256, 0.0762, 0.0280]`，累计 `[0.5630, 0.7701, 0.8958, ...]`。`top_p = 0.8` 时保留前 3 个（第 3 个之前累计 0.7701 < 0.8，第 4 个之前累计 0.8958 ≥ 0.8 被去掉），保留总概率 **0.8958 > 0.8**，满足讲义练习 5 的检查。`top_p = 0.5` 时只保留 1 个。`remove = cum - probs >= top_p` 保证"首个使累计超过 p 的 token"也被保留，集合永远非空。贪心模式下序列与 seed 无关（我们用 `top_k=1` 验证：seed 1 与 seed 99 的结果相同，为 `[1, 2, 3, 3, 3, 3, 3, 3, 3]`——随机初始化的模型会不断重复同一个 token）。

### Q12 — 参考答案

实验：构造 `GPTConfig(vocab_size=1000, context_length=64, d_model=192, num_heads=6, num_layers=12, dropout=0)` 的模型，`eval()` 后取一批随机 token，从 embedding 输出开始逐个 block 前向，记录每层残差流的标准差；再构造一个"撤销缩放"的版本（把 `out_proj`、`fc2` 的权重乘回 `√24`）做对照。

实测（每 3 层取一个点）：

| 版本 | 第 0/3/6/9/12 层残差流标准差 | 12 层后 / 输入 |
|------|---------------------------|---------------|
| 有缩放（本节默认） | 0.0284, 0.0412, 0.0514, 0.0601, 0.0678 | **2.39 倍** |
| 无缩放 | 0.0284, 0.1564, 0.2286, 0.2846, 0.3301 | **11.62 倍** |

解读：每个 block 向残差流加两次增量。若每次增量与当前流近似独立、方差为 σ²，N 层后方差增加 `2Nσ²`；把增量的 std 缩小 `√(2N)` 倍，总增加量就与深度无关。嵌入初始 std 只有约 0.028，而一次未缩放的 `fc2` 输出就远大于它，所以无缩放版本的残差流迅速被 block 的输出"淹没"。

### Q13 — 参考回答要点

- 前向：
  1. `tokens (B, T)` → `tok_embed` `(B, T, D)`；`position_ids[:T]` → `pos_embed` `(T, D)`；相加（广播）→ embedding dropout；
  2. 12 个 pre-LN block，形状保持 `(B, T, D)`；
  3. `final_ln` → `lm_head`（与 `tok_embed` 共享）→ logits `(B, T, V)`。
- 生成：
  1. 取最后 `context_length` 个 token 作为窗口；
  2. 前向得 `(B, T, V)`，只取 `[:, -1, :]` → `(B, V)`；
  3. 除以 T → top-k/top-p 截断 → softmax → `multinomial` 得 `(B, 1)`；
  4. 拼接到序列，重复。
- 加分点：训练时对每个位置都计算 loss（一次前向得到 T 个训练信号）；生成时 `model.eval()` + `torch.no_grad()`，本节 `generate` 还用 `try/finally` 恢复原来的训练状态。

### Q14 — 参考回答要点

- 定义：输入 embedding 矩阵 `E (V, D)` 与输出投影共享，`logits = h @ Eᵀ`。
- 为什么能用：输入侧"token → 向量"和输出侧"向量 → token 打分"都需要一个"token 在 D 维空间中的位置"；共享后，与 h 方向相近的 token 得分高，语义一致。
- 好处：GPT-2 Small 省 38.6M 参数（约占无 tying 时的 24%）；罕见 token 也能从输出侧得到梯度（每一步每一行都有梯度）。
- 潜在问题：
  - 输入、输出的最佳表示不一定相同，大模型中参数占比小，很多大模型选择不共享；
  - 嵌入层初始化/学习率与输出层的需求可能冲突；
  - 保存、加载、分布式切分时要维护共享关系（必须是同一个 `Parameter`，不能复制——讲义 "Tie weights at parameter level, not just by copying"）。
- 加分点：能说出如何验证（`is`、`data_ptr()`）以及 `state_dict` 中仍有两个键。

### Q15 — 参考回答要点

- 残差流 `x_{l+1} = x_l + f(x_l)`。每个 block 有两个子层（注意力、MLP）往残差流里加东西，N 层共 `2N` 次相加——这就是 `2N` 的来源。
- 若每次增量的方差为 σ² 且大致独立，最终方差约 `Var(x_0) + 2Nσ²`，随深度线性增长。把产生增量的最后一个线性层（`out_proj`、`fc2`）的权重 std 缩小 `√(2N)` 倍，增量方差变成 `σ²/(2N)`，总增加量与深度无关。
- 为什么只缩这两个：它们是"写入残差流"的出口；QKV、`fc1` 的输出先经过 softmax/GELU 再被出口投影，缩放出口就够了。
- 实验证据（Q12）：12 层时无缩放残差流增长 11.6 倍，有缩放 2.4 倍。
- 加分点：pre-LN 的子层输入经过 LN，所以残差流变大不会直接让子层输入爆炸，但会让每层的"相对贡献"变小、`final_ln` 承受大尺度输入（讲义："pushes the final LayerNorm into a hot regime"）。

### Q16 — 参考回答要点

- **显存**：参数 124.4M，FP32 权重约 498 MB，FP16/BF16 约 249 MB。训练时用 Adam 混合精度，每个参数约 16 字节（FP32 主权重 4 + 梯度 4 + Adam 两个状态 8，不同实现略有差异），约 2 GB，再加上与 batch、序列长度成正比的激活显存。
- **FLOPs**：前向每 token 约 `2 × 参数量 ≈ 0.25 GFLOPs`（矩阵乘的乘加），再加注意力的 `O(T·D·层数)` 项；训练（前向 + 反向）约为前向的 3 倍。
- **本节 `generate` 的性能问题**：
  - 没有 KV cache：每生成一个 token 都对整个窗口重算一遍；
  - 窗口满了以后每一步位置都在"平移"，即使加 KV cache 也必须重算（learned 绝对位置的固有问题）；
  - 手写注意力物化 `(B, H, T, T)`，没用 SDPA/FlashAttention；
  - `torch.manual_seed(seed)` 修改全局随机状态（实测调用 `generate(seed=42)` 后，外部的 `torch.rand` 序列被改变），更好的做法是传入独立的 `torch.Generator`。
- 加分点：说明 decode 阶段是 memory-bound，批量并发才能提高吞吐。

### Q17 — 参考回答要点

- **temperature**：整体调节分布的"尖锐程度"，不改变排序；以 `[5,4,3,2,1]` 为例，T = 0.5/1/2 时最大值概率分别为 0.865、0.636、0.429（实测）。
- **top-k**：固定保留 k 个候选，切掉长尾里的"胡言乱语"；k = 1 等价于贪心。
- **top-p**：保留累计概率达到 p 的最小集合，候选数随分布自适应。
- **repetition penalty**：降低已出现 token 的分数，缓解重复循环；要注意正负 logit 分别处理（Q8）。
- **顺序**：常见顺序是 repetition penalty → temperature → top-k → top-p → softmax → 采样。penalty 作用在原始 logits 上；截断在 temperature 之后进行，截断集合才与实际采样分布一致。
- **为什么不允许 T = 0**：`logits / 0` 产生 `inf`/`nan`，softmax 后无法采样。"T → 0 等于贪心"是极限意义上的说法，实现上应该用单独的贪心分支（讲义练习 3 的 `greedy=True`），或者把 T = 0 映射为 `argmax`。
- 加分点：线上对话常见 T≈0.7 + top-p≈0.9；需要确定性输出（如 JSON、代码）时用贪心或低温度。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 32 Token 与位置 Embeddings](../../32-token-positional-embeddings/docs/zh.md)：token 表与 learned 位置表，以及 weight tying 的初步讨论。
- [阶段 19 · 34 从零实现 Transformer 模块](../../34-transformer-block/docs/zh.md)：本节堆叠的 pre-LN block（本节代码在本地重新实现了一遍）。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：NumPy 版的同一结构，以及参数量口径的差异（124,402,944 vs 124,439,808）。
- [阶段 07 · 07 GPT — 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：next-token prediction 的数学。
- [阶段 03 · 08 Weight初始化和训练稳定性](../../../03-deep-learning-core/08-weight-initialization/docs/zh.md)：初始化尺度与方差传播。

### 本节被哪些后续内容用到
- [阶段 19 · 36 训练循环与 Evaluation](../../36-training-loop-eval/docs/zh.md)：用交叉熵训练本节的模型，并用 `generate` 做定性评估。
- [阶段 19 · 37 加载预训练 Weights](../../37-loading-pretrained-weights/docs/zh.md)：把 OpenAI 的 GPT-2 权重装进同样的结构，处理 tying 与参数命名。
- [阶段 19 · 38 通过替换输出头进行分类器 Fine-Tuning](../../38-classifier-finetuning/docs/zh.md)：把 LM head 换成分类头。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：本节 `generate` 缺少的推理优化。
- [阶段 10 · 12 Inference Optimization](../../../10-llms-from-scratch/12-inference-optimization/docs/zh.md)：采样与推理加速的更多工程细节。

### 延伸关键词
`weight tying` · `residual projection scaling` · `GPT-2 initialization` · `temperature` · `top-k` · `top-p / nucleus sampling` · `repetition penalty` · `sliding window context` · `KV cache` · `parameter counting` · `torch.multinomial`
