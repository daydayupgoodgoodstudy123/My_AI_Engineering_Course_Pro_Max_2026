# 测验 · Flamingo：面向 Few-Shot VLM 的门控 Cross-Attention（Flamingo and Gated Cross-Attention for Few-Shot VLMs）

> **阶段 12 · 多模态 AI · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 注：中文讲义的数字有机翻错误（如把 "43M interleaved pages" 译成"4300M"、把 "27M short video clips" 译成"2 700 短片"），本测验数字以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Flamingo 的两个"第一" | 讲义：单个模型处理任意交错的图像/视频/文本序列；VLM 能做 in-context few-shot（给 3 个图文示例即可描述新图，无梯度更新） |
| 2 | 不改 LLM 输入流 | 冻结的 Chinchilla 70B 照常做因果 self-attention；视觉信息通过**插在 LLM 层之间**的新 cross-attention 层注入 |
| 3 | Gated cross-attention | `y = tanh(alpha) · cross_attn(x, visual) + x`，`alpha` 是可学习标量、初始化为 0，所以第 0 步模型与原 LLM 完全一致 |
| 4 | 插入频率 | 讲义：每 M = 4 层 LLM 插一个 gated cross-attention 块 |
| 5 | Perceiver resampler | K 个可学习 latent（Flamingo K = 64）对任意数量的 patch 做 cross-attention，再做 self-attn + FFN，6 个 block 后输出 64 个 1024 维视觉 token；196 个或 900 个 patch 都输出 64 个 |
| 6 | 视频 | 每帧各自 resample 出 64 个 latent，加时间位置编码，整段视频为 `T × 64` 个视觉 token |
| 7 | 交错输入的 mask | 文本 token 只能 cross-attend 到**它之前最近的那一张**图（Flamingo 的选择；"看到之前所有图"也是可行方案） |
| 8 | 训练数据 | M3W 43M 交错网页 + 图文对（ALIGN + LTIP）+ VTP 27M 视频片段；开源复现语料 OBELICS（141M 网页） |
| 9 | 家族 | OpenFlamingo（3B/4B/9B 开源复现）、Otter（在 MIMIC-IT 上指令微调）、Idefics 系列 |
| 10 | 与 BLIP-2 对比 | BLIP-2：输入端一次性 32 token，单图 VQA 便宜；Flamingo：多层 cross-attention，few-shot 与交错输入强，但训练约 10B 参数、数千 TPUv4 训练数周 |

### 核心技能（能动手做到）

- [ ] 写出 gated residual `y = tanh(alpha)·cross + x`，并用数值实验证明 `alpha = 0` 时 `y == x` 严格成立
- [ ] 推导 `alpha = 0` 时各参数的梯度：为什么只有 `alpha` 有梯度、cross-attention 自身的权重梯度为 0
- [ ] 根据交错序列构造"只看最近一张前置图像"的 cross-attention mask，并正确处理"前面没有图像"的文本 token
- [ ] 实现一个带共享可学习 latent、Q/K/V 投影的 Perceiver resampler block，并说明本节代码版本缺少了什么
- [ ] 计算 Flamingo 类模型的可训练参数比例与视觉 token 开销，并与 BLIP-2 对比
- [ ] 能根据 loss 曲线和 benchmark 退化诊断"门开得太快 / 太慢"

---

## 二、基础自测（选择题）

**Q1.** Flamingo 的 gated cross-attention 中，`alpha` 初始化为 0。这样设计的主要目的是：

- A. 让 cross-attention 在训练初期就能输出强烈的视觉信号
- B. 防止 cross-attention 的 softmax 溢出
- C. `tanh(0) = 0`，新插入的分支在初始化时贡献为零，模型在第 0 步与冻结的预训练 LLM 完全相同，文本能力不受破坏
- D. 让 `alpha` 在训练中保持为 0

**Q2.** Perceiver resampler 的 K = 64。一张 224×224 图像（196 个 patch）和一张 480×480 图像（900 个 patch）经过 resampler 后分别得到：

- A. 都是 64 个视觉 token（讲义中为 1024 维）
- B. 196 个和 900 个
- C. 64 个和 900 个
- D. 都是 196 个

**Q3.** 对于 `y = tanh(alpha) · cross(x; W) + x`，在初始化 `alpha = 0` 时进行一次反向传播，下列说法正确的是：

- A. 所有参数的梯度都是 0，因此模型永远无法开始学习
- B. `alpha` 的梯度为 0，cross-attention 权重 `W` 的梯度不为 0
- C. 所有参数都有正常大小的梯度
- D. `W` 的梯度为 0（被 `tanh(0) = 0` 乘掉），但 `alpha` 的梯度为 `(1 − tanh²0) · Σ (∂L/∂y)·cross = Σ (∂L/∂y)·cross`，一般不为 0，所以门会先打开，`W` 随后开始学习

**Q4.** 序列为 `IMG0 t0a t0b IMG1 t1a t1b t1c IMG2 t2a`。按 Flamingo 的 mask 规则，文本 token `t1b` 可以 cross-attend 到哪些图像？

- A. IMG0、IMG1、IMG2
- B. 只有 IMG1
- C. IMG0 和 IMG1
- D. 不能看任何图像

**Q5.** 讲义练习 1：Flamingo-9B = 9B LLM（冻结）+ 1.4B gated cross-attention 层 + 64M resampler。可训练参数约占总参数的：

- A. 约 14%
- B. 约 0.6%
- C. 约 1.4%
- D. 约 86%

**Q6.** 本节代码的 `perceiver_resampler` 中有这样一行：

```python
    latents = [vec(dim) for _ in range(num_latents)]
```

它与讲义描述的 Perceiver resampler 相比，最本质的问题是：

- A. latent 的维度应该比 patch 大
- B. 应该用 `np.random` 而不是 `random`
- C. num_latents 应该等于 patch 数
- D. latent 应当是**模型参数**、对所有图像共享，但这里每次调用都重新随机采样，同一张图两次 resample 得到不同结果（实测最大差异约 1.14）

**Q7.** 关于 BLIP-2 与 Flamingo 的对比（讲义表格），说法正确的是：

- A. BLIP-2 原生支持交错多图输入，Flamingo 只支持单图
- B. Flamingo 的 few-shot in-context 能力是论文核心卖点，并且以交错输入为设计目标；BLIP-2 更适合低预算的单图 VQA
- C. 两者都需要解冻 LLM
- D. Flamingo 训练的参数比 BLIP-2 少

**Q8.** 技能文件 `skill-gated-bridge-diagnostic` 认为：一个 Flamingo 式模型微调后，纯文本 benchmark 明显退化。最可能的原因和修复方向是：

- A. 门开得太慢，应提高 `alpha` 的初始值
- B. resampler 的 latent 数太多，应减少到 1
- C. 门开得太快、视觉分支覆盖了文本表示；应把 `alpha` 初始化得更接近 0、降低门的学习率或在前 N 步冻结门
- D. LLM 被冻结了，应解冻 LLM 全量微调

---

## 三、动手 / 代码题

**Q9.** 门的数值行为。代码 DEMO 2 打印了 `alpha` 与 `tanh(alpha)` 的对应关系：

```text
    alpha= 0.0  tanh(alpha)=+0.0000
    alpha= 0.5  tanh(alpha)=+0.4621
    alpha= 1.0  tanh(alpha)=+0.7616
    alpha= 2.0  tanh(alpha)=+0.9640
    alpha= 5.0  tanh(alpha)=+0.9999
```

1. 分别计算这 5 个点上门对 `alpha` 的导数 `1 − tanh²(alpha)`。
2. `alpha` 被更新到 5 之后会发生什么？为什么说"门开太大"不仅影响文本能力，还会让门本身难以再调整？
3. 为什么代码中 `alpha = 0` 时 "max delta vs input = 0.000000" 是**严格**的 0，而不仅仅是很小？如果把门换成 `sigmoid(alpha)` 并初始化 `alpha = 0`，还能保持这一性质吗？

**Q10.** 代码 `interleaved_mask` 构造了 mask，但没有在任何 cross-attention 中使用它。

1. 若序列为 `["t_pre", "IMG0", "t0a", "IMG1", "t1a", "t1b"]`，`interleaved_mask` 返回什么？`t_pre` 这一行有什么特点？
2. 如果用"把不允许的位置设为 −∞ 再 softmax"的方式实现 masked cross-attention，`t_pre` 这一行会出现什么数值问题？应如何处理？
3. 写一个 `masked_gated_xattn(text_hidden, image_tokens, mask, alpha)`：每张图有多个 resampler token，按 mask 只看允许的图像；没有可看图像时 cross 分支输出为 0。用上面的序列验证 `alpha = 0` 时所有输出等于输入。

**Q11.** 阅读 `perceiver_resampler`：

```python
def perceiver_resampler(patches, num_latents, num_blocks=2):
    dim = len(patches[0])
    latents = [vec(dim) for _ in range(num_latents)]
    for _ in range(num_blocks):
        attended = cross_attention(latents, patches, patches)
        latents = [add(lat, att) for lat, att in zip(latents, attended)]
    return latents
```

`vec` 用 `rng.gauss(0, 0.3)` 生成。

1. 与讲义描述（K = 64、6 个 block、每个 block 为 cross-attn + self-attn + FFN）相比，列出全部简化之处。
2. 估算一下：两个 16 维 `N(0, 0.3²)` 向量点积的标准差约是多少？乘以 `1/√16` 后呢？这对注意力分布意味着什么？（实测 8 个 latent 在 36 个 patch 上的平均注意力熵为 3.579，`ln 36 = 3.584`。）
3. 在这种情况下，resampler 实际上退化成了什么操作？

**Q12.** 视觉 token 开销对比。设一个 few-shot prompt 包含 4 张图（3 个示例 + 1 个查询），LLM 共 80 层：

1. BLIP-2 式（每图 32 token 拼到输入）会让 LLM 的输入序列增加多少 token？
2. Flamingo 式（每图 64 个 resampler token，每 4 层插一个 gated cross-attention，文本只看最近一张图）会让 LLM 的输入序列增加多少 token？共有多少个 gated cross-attention 层？每个文本 token 在每个这样的层里 attend 多少个视觉 token？
3. 技能文件说视觉 token 预算为 "K latents x N cross-attn insertion points"。按这个口径，每张图的"视觉 token 读取量"是多少？为什么说这个开销与 BLIP-2 的开销性质不同？

---

## 四、面试高频题

**Q13.**（基础必考）请介绍 Flamingo 的整体架构：哪些模块冻结、哪些训练？Perceiver resampler 和 gated cross-attention 各解决什么问题？

**Q14.**（原理深挖）为什么 gated cross-attention 要用 `tanh(alpha)` 并初始化为 0？在深度学习中还有哪些类似的"零初始化保持原模型"技巧？

**Q15.**（原理深挖）Flamingo 规定文本 token 只能 cross-attend 到最近的一张前置图像。那么在 few-shot prompt 中，模型如何利用前面的示例图像？这个设计有什么取舍？

**Q16.**（工程实践）你在 OpenFlamingo 上做领域微调，发现：(a) 图像描述指标提升了，但纯文本问答下降明显；(b) 另一组实验中纯文本没变，但模型基本不看图。分别如何诊断与修复？

**Q17.**（追问型）既然 Flamingo 的 few-shot 与交错输入能力这么强，为什么后来的开源 VLM（LLaVA 系、Idefics2 之后）大多把视觉 token 直接拼进 LLM 输入，而不再用逐层 gated cross-attention？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："A Flamingo at step 0 is a perfect Chinchilla 70B on text-only inputs." 视觉条件是"additive, gated, and zero at initialization"。A 说反了：初始时视觉信号为 0。B 与门无关（softmax 溢出靠减最大值解决）。D 错：`alpha` 是可学习的，训练中会离开 0，门逐渐打开。

### Q2 — 答案：A

讲义："A 224x224 image (196 patches) and a 480x480 image (900 patches) both exit as 64 resampler tokens." resampler 的输出长度等于 latent 数 K，与输入 patch 数无关，这使得 LLM 侧的 cross-attention 层"无论 prompt 中有几张图、每张图多大，都看到同样的形状"。本节代码 DEMO 1 以 K = 8 演示了同样的性质：36、196、900 个 patch 都输出 8 个 latent。

### Q3 — 答案：D

`∂y/∂W = tanh(alpha) · ∂cross/∂W`，在 `alpha = 0` 时为 0；`∂y/∂alpha = (1 − tanh²alpha) · cross`，在 0 处等于 `cross`。我们用有限差分实测：令 L = 所有输出元素之和，`dL/dalpha ≈ −1.75405`，与 `Σ cross = −1.75405` 完全一致。所以第一步只有门在动，门一旦离开 0，`W` 立即获得非零梯度。A 错：门本身有梯度，不会卡死。B 说反了。C 错。这和 LoRA 把 B 矩阵初始化为 0 的效果相同：初始输出不变、但训练可以启动（LoRA 中 A 有非零初始化，B 的梯度非零）。

### Q4 — 答案：B

`t1b` 之前的图像有 IMG0、IMG1，最近的是 IMG1。代码运行的 DEMO 3 中 `t1a`、`t1b`、`t1c` 三行都只有 IMG1 列为 `ok`。A 会让文本看到"未来"的 IMG2，破坏因果性；C 是"看所有前置图像"的方案，讲义说也合理，但 Flamingo 选择了只看最近一张。

### Q5 — 答案：A

`(1.4 + 0.064) / (9 + 1.4 + 0.064) = 1.464 / 10.464 ≈ 14.0%`（已用 Python 计算）。D 是冻结部分的比例。注意这是按讲义"9B LLM"的口径计算；若把 Flamingo-9B 理解为"总参数 9B"，则冻结的 LLM 约为 7B 左右，比例会变成约 17%——做此类计算时先说明口径。

### Q6 — 答案：D

讲义："The Perceiver resampler has K fixed learnable latents"。可学习 latent 应在 `__init__` 中创建一次、对所有图像共享，训练时更新。代码每次调用 `perceiver_resampler` 都重新采样随机 latent：我们对同一组 36 个 patch 连续调用两次，输出的最大逐元素差异约 1.14。同一张图得到不同表示，这在真实模型里是不可接受的。A、B、C 都不是本质问题；C 甚至违背了 resampler"固定 K 个输出"的设计初衷。

### Q7 — 答案：B

讲义表格："Few-shot in-context: Weak（BLIP-2）/ Strong — the paper's centerpiece（Flamingo）"；"Interleaved inputs: No native support / Yes, the design target"；"Pick BLIP-2 for single-image VQA on a budget. Pick Flamingo/Idefics2 for interleaved, few-shot, or multi-image reasoning." A 说反；C 错，两者 LLM 都冻结；D 错，Flamingo 训练约 10B，BLIP-2 只有 188M。

### Q8 — 答案：C

技能文件："suggest whether the gate opened too fast (loses text capability), too slow (fails to use visual input) ... initialize alpha closer to 0 if text degraded, raise the learning rate on the gate parameter, or freeze the gate for the first N steps." 讲义 Ship It 也说："Useful for debugging why a fine-tune degraded text performance (answer: the gate got too wide too fast)." A 是"门太慢"的修复方向。D 与 Flamingo"冻结 LLM 保持文本能力"的设计思想背道而驰，而且会进一步加剧文本退化风险。

### Q9 — 参考答案

1. `1 − tanh²(alpha)`（已用 Python 计算）：alpha = 0 → 1.0；0.5 → 0.7864；1.0 → 0.4200；2.0 → 0.0707；5.0 → 0.0002。
2. alpha = 5 时门几乎全开（0.9999），视觉分支以近乎满权重叠加到文本表示上；同时门的导数只剩 0.0002，即使后续 loss 想把门关小，梯度也几乎传不过去——tanh 进入**饱和区**。所以"门开太快"不只是破坏文本能力，还会让模型很难自行纠正。实践中常给门单独设置较小的学习率或预热。
3. 因为 `math.tanh(0.0)` 精确等于 `0.0`，`scale(c, 0.0)` 得到全 0 向量，再加到 `t` 上不产生任何舍入误差，所以是**严格**相等（讲义练习 2 要求在 PyTorch 中验证 `y == x`）。若改成 `sigmoid(alpha)` 且 alpha = 0，门值为 0.5，初始化时就混入一半的视觉分支，不再保持原 LLM；必须把 alpha 初始化为很大的负数才近似为 0，但那时 sigmoid 也处于饱和区、梯度很小。这就是选用 tanh 且以 0 为中心的原因。

### Q10 — 参考答案

1. 返回 `[[False, False], [True, False], [False, True], [False, True]]`（已实际运行）。`t_pre` 这一行全为 False——它前面没有任何图像。
2. 若对全 −∞ 的行做 softmax，会出现 `exp(−∞ − (−∞)) = exp(nan)`，得到 NaN，并在后续计算中扩散。处理方法：对"没有可看图像"的行，直接把 cross 分支输出置 0（相当于该位置纯文本），或者在 softmax 后把这些行乘以一个 0/1 的有效性掩码。本节代码的 `interleaved_mask` 用 `continue` 跳过了这类行，但没有给出后续 attention 如何处理。
3. 参考实现（基于本节代码的工具函数，已实际运行）：

```python
import math
from main import vec, dot, softmax, add, scale, interleaved_mask

def masked_gated_xattn(text_hidden, image_tokens, mask, alpha):
    gate = math.tanh(alpha)
    d = len(text_hidden[0])
    out = []
    for t, x in enumerate(text_hidden):
        keys = [tok for i, toks in enumerate(image_tokens) if mask[t][i] for tok in toks]
        if not keys:                       # 前面没有图像：cross 分支为 0
            out.append(list(x))
            continue
        w = softmax([dot(x, k) / math.sqrt(d) for k in keys])
        cross = [sum(wi * k[j] for wi, k in zip(w, keys)) for j in range(d)]
        out.append(add(x, scale(cross, gate)))
    return out

seq = ["t_pre", "IMG0", "t0a", "IMG1", "t1a", "t1b"]
mask = interleaved_mask(seq)
imgs = [[vec(16) for _ in range(4)] for _ in range(2)]   # 每张图 4 个 resampler token
txt = [vec(16) for _ in range(4)]
```

验证结果：`alpha = 0` 时 4 个文本 token 的最大偏差均为 0.0；`alpha = 2` 时为 `[0.0, 0.192, 0.248, 0.2483]`——`t_pre` 始终不变，其余三个 token 混入了各自最近图像的信息。注意 key 是"该图的全部 resampler token"，mask 的粒度是**图像**而不是单个 token；本节代码把一张图简化成序列中的一个位置。

### Q11 — 参考答案

1. 简化之处：
   - latent 每次调用重新随机采样，不是共享的可学习参数（Q6）；
   - 没有 Q/K/V 投影，直接用 latent 当 Q、patch 同时当 K 和 V；
   - 每个 block 只有 cross-attention + 残差，没有 latent 之间的 self-attention 和 FFN，也没有 LayerNorm；
   - 规模：K = 8、2 个 block、16 维，讲义为 K = 64、6 个 block、输出 1024 维；
   - 没有视频所需的时间位置编码。
2. 每个乘积 `x·y` 的方差为 `0.3² × 0.3² = 0.0081`，16 项求和方差约 0.13，标准差约 0.36；乘以 1/4 后约 0.09。实测 logit 标准差 0.089，与估算一致。logit 几乎全相等，softmax 接近均匀分布——平均熵 3.579，几乎等于上限 ln 36 = 3.584。
3. 每个 latent 拿到的 `attended` 都约等于"所有 patch 的平均值"，所以 resampler 退化为"**平均池化 + 各自的随机偏移**"：8 个 latent 加上了几乎相同的向量，彼此的差异主要来自随机初始值。真实 resampler 依靠可学习投影和训练让不同 latent 关注不同区域。（这与第 03 节代码的问题正好相反：那里 `N(0,1)` 初始化导致注意力饱和成 one-hot。两者都说明初始化尺度决定了未训练注意力的形态。）

### Q12 — 参考答案

1. BLIP-2 式：`4 × 32 = 128` 个 token 进入 LLM 输入序列，每一层的 self-attention 和 KV cache 都要为它们付费。
2. Flamingo 式：视觉 token **不进入** LLM 的输入序列（序列中只放图像位置标记），输入长度增加约为 0；gated cross-attention 层数 = `80 / 4 = 20`；每个文本 token 在每个这样的层里只 attend 最近一张图的 64 个 resampler token。
3. 按技能文件口径：每张图 `64 × 20 = 1,280` 次"视觉 token 读取"。性质不同之处：BLIP-2 的开销体现为**上下文长度**（占用窗口、增大 KV cache，且与后续所有文本 token 的 self-attention 相互作用）；Flamingo 的开销体现为**额外的层与参数**（约 1.4B～10B 的 cross-attention 参数、每个插入点的一次额外 attention），上下文窗口不被视觉 token 占用。所以图像多时 Flamingo 更省上下文，但每次前向要多走 20 个 cross-attention 层。

### Q13 — 参考回答要点

- **冻结**：视觉 encoder 和 LLM（Chinchilla 70B）。讲义："All 70B weights untouched."
- **训练**：Perceiver resampler + 插入的 gated cross-attention 层（讲义表格："~10B trained"）。
- **Perceiver resampler** 解决"图像数量和分辨率可变"：K = 64 个可学习 latent 对任意数量的 patch 做 cross-attention，6 个 block 后输出固定 64 个 token；视频每帧 64 个 latent 加时间编码。
- **Gated cross-attention** 解决"不改 LLM 输入流却要注入视觉"：每 M = 4 层插一个块，文本 token 作 Q，视觉 token 作 K/V；`tanh(alpha)` 门初始化为 0，保证第 0 步等于原 LLM。
- **交错输入**：通过 cross-attention mask 让每个文本 token 只看最近的前置图像。
- **训练数据**：M3W 43M 交错网页 + 图文对 + VTP 27M 视频片段。
- 加分点：Flamingo 的 few-shot 能力来自冻结 LLM 本身的 in-context learning 被完整保留——"the frozen LLM's in-context learning capability carries through the gated cross-attention"。

### Q14 — 参考回答要点

- **原因**：
  1. 保持预训练 LLM：零初始化让新分支在开始时是恒等映射（no-op），不会因为随机初始化的 cross-attention 输出噪声而破坏 70B 模型的语言能力；
  2. 平滑打开：`tanh` 连续可导、以 0 为中心，`alpha` 离开 0 时视觉贡献平滑增长，上界为 1，不会无限放大；
  3. 梯度可启动：`alpha = 0` 处 `tanh` 导数为 1，门的梯度最大（Q3、Q9）。
- **类似技巧**：
  - LoRA：`ΔW = B·A`，B 初始化为 0，初始时模型不变（[阶段 11 · 08](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)）；
  - ControlNet 的 zero convolution：控制分支用零初始化的卷积接回主干（[阶段 08 · 08](../../../08-generative-ai/08-controlnet-lora-conditioning/docs/zh.md)）；
  - 残差块最后一层零初始化（让深层网络初始时接近恒等映射）。
- 常见误区：以为门初始为 0 会导致"梯度为 0、学不动"——门本身的梯度不为 0。

### Q15 — 参考回答要点

- **如何利用前面的示例**：文本 token 虽然只直接 cross-attend 最近的一张图，但 LLM 自身的因果 self-attention 能看到**所有**之前的文本 token；而示例的文本 token（如 "A photo of a cat."）在各自的 cross-attention 中已经吸收了对应图像的信息。于是查询图像后的文本 token 可以通过 self-attention 间接获取前面所有图文对的信息，从而形成 few-shot 模式。
- **为什么只看最近一张**：讲义练习 4 要求读论文 2.4 节。从设计上看：mask 简单、每个文本 token 的 cross-attention 开销固定（只有 64 个视觉 token）、自然支持任意数量的图像，并且训练时与推理时的图像数可以不同。
- **代价**：如果问题需要同时比较多张图的细节（"第一张和第三张图里的狗颜色一样吗？"），模型只能通过已经"文字化"的中间表示间接比较，细粒度视觉信息可能丢失；"看所有前置图像"能缓解，但 cross-attention 的 key 数随图像数线性增长。
- 加分点：讲义练习 5 让你设计 0～8 个示例时的准确率曲线——一般会随示例数增加而上升并逐渐饱和。

### Q16 — 参考回答要点

- **情况 (a)：文本退化**——门开得太快或太大。
  - 诊断：记录每层 `tanh(alpha)` 随训练的变化；在纯文本 benchmark 上对比微调前后；检查是否有门接近 ±1。
  - 修复：降低门参数的学习率或对门做 warmup；前 N 步冻结门；混入纯文本数据一起训练；确认 LLM 确实被冻结（技能文件 "LLM freeze depth"）。
- **情况 (b)：不看图**——门开得太慢。
  - 诊断：`tanh(alpha)` 一直接近 0；做消融，把图像换成空白图或随机图，若输出几乎不变即说明视觉没被利用。
  - 修复：提高门的学习率；检查 cross-attention mask 是否错误地屏蔽了所有图像（例如 mask 全 False）；检查 resampler 输出尺度是否过小。
- 技能文件提醒："Assuming zero init always survives training" 是错误假设；某些开源复现使用了较小的非零初始化。
- 加分点：给出监控指标——每层门值、视觉分支输出范数与文本残差范数之比。

### Q17 — 参考回答要点

- **工程复杂度**：逐层 cross-attention 需要改动 LLM 内部结构，每换一个 LLM 底座就要重新插层；把视觉 token 拼进输入只需要一个 projector，任何 decoder-only LLM 都能直接用，生态兼容性更好（vLLM 等推理框架也更容易支持）。
- **参数和训练成本**：Flamingo 需要训练约 10B 的 cross-attention 参数；LLaVA 式 projector 只有几千万参数（第 05 节）。
- **质量**：当允许解冻 LLM 时，LLM 自身的 self-attention 直接处理视觉 token，表达能力更强；讲义第 03 节也指出 MLP projector "lets the LLM attend over raw patches"。
- **Flamingo 路线仍有价值的场景**：讲义："Flamingo-style gated cross-attention remains in production where backbone freezing is required"；以及需要处理大量图像但上下文有限的场景。
- 注意：讲义说"Idefics2 dropped the resampler in favor of direct patch tokens with adaptive pooling"。这一说法建议对照 Idefics2 论文核对：按笔者理解，Idefics2 放弃的主要是 gated cross-attention 结构（改为把视觉 token 拼入 LLM 输入），同时仍用一种可学习的池化把每张图压缩到固定数量的 token。面试中可以说"Idefics 系列从 cross-attention 转向了 fully-autoregressive 的输入拼接方式"，并以原论文为准。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 03 从 CLIP 到 BLIP-2：作为 Modality 桥梁的 Q-Former](../../03-blip2-qformer-bridge/docs/zh.md)：learnable query + cross-attention 的思想，Perceiver resampler 与 Q-Former 同源。
- [阶段 12 · 02 CLIP 与视觉语言对比 Pretraining](../../02-clip-contrastive-pretraining/docs/zh.md)：Flamingo 的视觉 encoder 来自对比预训练（讲义提到 ALIGN 数据）。
- [阶段 07 · 05 完整的 Transformer — Encoder + Decoder](../../../07-transformers-deep-dive/05-full-transformer/docs/zh.md)：decoder 中 cross-attention 的原型。
- [阶段 07 · 07 GPT — 因果语言建模](../../../07-transformers-deep-dive/07-gpt-causal-language-modeling/docs/zh.md)：冻结 LLM 的因果 self-attention 与 in-context learning。
- [阶段 03 · 08 Weight 初始化和训练稳定性](../../../03-deep-learning-core/08-weight-initialization/docs/zh.md)：零初始化、初始化尺度对注意力形态的影响。

### 本节被哪些后续内容用到
- [阶段 12 · 05 LLaVA 与视觉指令微调](../../05-llava-visual-instruction-tuning/docs/zh.md)：另一条路线——把视觉 token 直接拼入输入。
- [阶段 12 · 07 开放 Weight VLM 的构建方案：真正重要的因素](../../07-open-weight-vlm-recipes/docs/zh.md)：cross-attention vs 输入拼接的消融。
- [阶段 12 · 11 Chameleon：仅用 Token 的早期融合 Multimodal Models](../../11-chameleon-early-fusion-tokens/docs/zh.md)：讲义提到的 early-fusion 路线。
- [阶段 12 · 17 视频语言模型：时间 Tokens 与 Grounding](../../17-video-language-temporal-grounding/docs/zh.md)：视频的逐帧 resample 与时间编码。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：同样依赖"零初始化保持原模型"的思想。
- [阶段 19 · 61 Cross-Attention 融合](../../../19-capstone-projects/61-cross-attention-fusion/docs/zh.md)：综合项目中实现 cross-attention 融合。

### 延伸关键词
`gated cross-attention` · `tanh gate` · `zero initialization` · `Perceiver resampler` · `interleaved image-text` · `in-context learning` · `M3W / OBELICS` · `OpenFlamingo` · `Otter / MIMIC-IT` · `Idefics` · `cross-attention mask` · `Chinchilla`
