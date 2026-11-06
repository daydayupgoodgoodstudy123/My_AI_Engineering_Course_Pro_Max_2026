# 测验 · Show-o 与离散扩散统一模型（Show-o and Discrete-Diffusion Unified Models）

> **阶段 12 · 多模态 AI · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Show-o 的定位 | 两种模态都离散（像 Chameleon），但图像不逐 token 生成，而是用 MaskGIT 式**掩码离散扩散**并行生成 |
| 2 | MaskGIT 推理 | 从全 `<MASK>` 出发，每步并行预测所有被 mask 的 token，只提交置信度最高的一部分，其余重新 mask，8–16 步填满 |
| 3 | MaskGIT 训练 | 随机抽一个 mask 比例，把图像 VQ token 按比例遮住，只在被遮位置算交叉熵——"BERT 用到图像生成上" |
| 4 | 混合注意力 | 文本因果；同一图像块内双向（被 mask 的 token 要看到其他所有图像 token）；图看前文、文看前图 |
| 5 | 统一的交叉熵 | 讲义：NTP 可看作"只 mask 最后一个 token"的特例，图像是"随机 mask 一个子集"，两者都是 `<MASK>` 位置上的交叉熵 |
| 6 | 步数对比 | Chameleon/Emu3：每张图 1024–4096 次前向；Transfusion：约 20 步；Show-o：约 16 步，每步一次完整前向 |
| 7 | 一个 checkpoint 四种任务 | 文本生成、VQA、文生图、inpainting（局部重绘），由 prompt 格式选择；inpainting 直接来自掩码训练目标 |
| 8 | Mask 日程 | 讲义：`mask_ratio(t) = cos(πt / 2T)`，t = 0 时全 mask、t = T 时全揭开；cosine 早期少揭、后期多揭 |
| 9 | 质量上限 | 仍受 tokenizer 限制（"still lossy by tokenizer"）；追求顶级画质时选连续扩散（Transfusion/MMDiT） |
| 10 | 2026 分类图 | 离散 + NTP（Chameleon、Emu3）/ 离散 + 掩码扩散（Show-o、MaskGIT、Muse）/ 连续 + 扩散（Transfusion、MMDiT、DiT）/ VLM 内连续 + flow（JanusFlow、InternVL-U） |

### 核心技能（能动手做到）

- [ ] 写出 MaskGIT 的训练步和迭代解码循环，说清"预测 → 按置信度排序 → 提交 top-k → 其余重新 mask"
- [ ] 给定 token 总数 N 与步数 T，按 cosine 或 linear 日程算出每步应揭开的 token 数
- [ ] 指出 `code/main.py` 中 `keep_ratio` 把"全局 mask 比例"误用成"剩余 mask 的提交比例"的问题，以及 `cos(π/2)` 浮点误差导致的多走一步
- [ ] 解释为什么并行解码不能一步完成（条件独立假设），并能用一个 toy 例子演示
- [ ] 计算离散 token 表示相对原始像素的压缩比（讲义练习 4）
- [ ] 在 Show-o、Transfusion/MMDiT、Emu3/Chameleon、Janus-Pro 之间按延迟、画质、是否需要 inpainting 做选型

---

## 二、基础自测（选择题）

**Q1.** Show-o 生成图像的方式是：

- A. 像 Emu3 一样逐个 token 自回归生成 1,024 个 image token
- B. 在 VAE 的连续 latent 上做 20 步 flow matching 去噪
- C. 先生成一张低分辨率图，再用超分模型放大
- D. 从全 `<MASK>` 的 token 网格出发，每步并行预测所有被 mask 的 token，只提交最有把握的一部分，迭代约 16 步

**Q2.** MaskGIT / Show-o 图像部分的训练目标是：

- A. 随机抽一个 mask 比例遮住图像 VQ token，只在被遮位置上计算交叉熵
- B. 预测加在连续 patch 上的高斯噪声，MSE 损失
- C. 对所有图像 token 做从左到右的 next-token prediction
- D. 用对比损失对齐图像与文本 embedding

**Q3.** 按讲义的对比，生成一张图需要的完整 Transformer 前向次数，正确的是：

- A. Show-o 约 1,000 次，Transfusion 约 16 次
- B. 三者相同，都约 20 次
- C. Emu3/Chameleon 为每张图 1,024–4,096 次；Transfusion 约 20 次；Show-o 约 16 次
- D. Emu3 只需 1 次，因为所有 token 共享一个前向

**Q4.** 讲义说 Show-o 的 inpainting 能力"comes for free"，原因是：

- A. Show-o 额外训练了一个 inpainting 专用头
- B. 训练目标本身就是"根据未遮住的 token 预测被遮住的 token"，推理时把要重绘的区域设为 `<MASK>`、其余保持不变即可
- C. inpainting 在像素空间完成，与 Transformer 无关
- D. 它复用了 Stable Diffusion 的 inpainting 模型

**Q5.** `code/main.py` 的 `cosine_schedule(T)` 返回 `cos(π(t+1) / 2T)`。当 T = 8 时，`step 3` 的 mask_ratio 是：

- A. 0.924
- B. 0.831
- C. 0.707
- D. 0.556

**Q6.** 在 Show-o 的混合注意力 mask 中，为什么图像块内部必须是**双向**的？

- A. 每一步要同时预测图中任意位置被 mask 的 token，这些位置需要看到图中所有已揭开的 token，而揭开顺序由置信度决定、不是从左到右
- B. 因为图像 token 不需要位置编码
- C. 为了让文本 token 能看到未来的文本
- D. 双向注意力的计算量比因果注意力小

**Q7.** 讲义练习 4：512×512 图像在 Show-o 中是 1,024 个 token，词表 K = 16,384。相对 24 bit 原始像素（6,291,456 bit），离散表示的数据量与压缩比约为：

- A. 1,024 bit，约 6,144 倍
- B. 16,384 bit，约 384 倍
- C. 14,336 bit（约 1.75 KiB），约 44 倍
- D. 14,336 bit（约 1.75 KiB），约 439 倍

**Q8.** 讲义"Where Show-o sits"把 LlamaGen 列在"离散 token + 掩码扩散"一类。结合讲义练习 5，LlamaGen 实际上属于哪一类？

- A. 连续 latent + 扩散
- B. 离散 token + 自回归 next-token 预测（Llama 式逐 token 生成图像）
- C. 离散 token + 掩码扩散，与 Show-o 完全相同
- D. 连续 + flow matching

---

## 三、动手 / 代码题

**Q9.** 代码中每一步的提交数量由下面两行决定：

```python
        keep_ratio = max(0.15, 1 - ratios[step])
        tokens = step_unmask(tokens, prompt_seed, keep_ratio)
# step_unmask 内部：
    n_to_keep = max(1, int(len(masked_indices) * keep_ratio))
```

实际运行的 trace 中每步 masked 数为 `16 → 14 → 12 → 10 → 8 → 5 → 2 → 1 → 0`。

1. 每步实际揭开了多少个 token？
2. 按 MaskGIT 的语义，`mask_ratio(t)` 表示"这一步之后**整张图**还应保持 mask 的比例"。N = 16、T = 8 时每步应揭开多少个？
3. 两者的"形状"有什么本质差别？问题出在哪一行？请改写 `sample` 的这部分逻辑。

**Q10.** 用 `T = 1` 调用 `sample(prompt_seed=3, T=1)`，期望 1 步揭开全部 16 个 token，但 trace 是 `16 → 1 → 0`，走了 2 步。

1. 解释原因（提示：`math.cos(math.pi / 2)` 的值是多少？`int(16 * keep_ratio)` 是多少？）。
2. 为什么 T = 8 时最后一步没暴露这个问题？
3. 给出一个稳健的修法。

**Q11.** 用 `prompt_seed = 0, 3, 5` 分别采样，最终结果为：

```text
seed 0:  0  1  2  3  4  5  6  7  0  1  2  3  4  5  6  7
seed 3:  3  4  5  6  7  0  1  2  3  4  5  6  7  0  1  2
seed 5:  5  6  7  0  1  2  3  4  5  6  7  0  1  2  3  4
```

1. 从 `mock_logits` 的代码说明：最终 token 由什么决定？已经揭开的 token 对被 mask 位置的预测有没有影响？
2. 讲义 "Use It" 说 mock transformer "predicts logits based on a prompt and the currently-unmasked tokens"，这与代码一致吗？
3. 讲义练习 1 问"为什么不能一步揭开全部 token"。这份 mock 能演示答案吗？请设计一个最小的 mock 改动来演示"一步并行解码会产生不一致"。

**Q12.** 讲义练习 3：对 T = 8，分别用 cosine 和 linear 日程，计算 N = 16 与 N = 1,024 时每步揭开的 token 数。哪个更"均衡"？cosine 的设计意图是什么？

---

## 四、面试高频题

**Q13.**（基础必考）请解释 MaskGIT / Show-o 的掩码离散扩散：训练怎么做、推理怎么做？与 BERT 有什么关系？

**Q14.**（原理深挖）并行解码为什么需要多步？步数太少、太多分别会怎样？mask 日程和"按置信度提交"各起什么作用？

**Q15.**（原理深挖）请对比 Emu3（离散自回归）、Show-o（离散掩码扩散）、Transfusion（连续扩散）三条路线在推理步数、单步成本、画质上限、训练复杂度上的差异。

**Q16.**（工程实践）一个开源权重产品需要 VQA + 文生图 + 局部重绘，延迟预算 10 秒/张。你会选哪个家族？如果预算变成 2 秒，或要求"顶级画质"，选择怎么变？

**Q17.**（追问型）Show-o 说文本 NTP 和图像掩码预测是"同一种损失"。这种统一说法严格吗？文本能不能也用掩码并行解码？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："Start from a fully-masked image... At each step, predict all masked tokens in parallel, then keep the top-K most confident predictions and re-mask the rest. After ~8-16 iterations, all tokens are filled in." A 是 Emu3/Chameleon；B 是 Transfusion；C 是级联超分，与本节无关。

### Q2 — 答案：A

讲义："sample a masking ratio uniformly from [0, 1], apply it to the image's VQ tokens, train the transformer to recover the masked ones. Exactly what BERT did for text." B 是连续扩散（Transfusion）；C 是 Emu3 的训练方式；D 是 CLIP。（补充：MaskGIT 原论文训练时 mask 比例是先抽 `r ~ U(0,1)` 再经日程函数 `γ(r)` 映射，讲义的"uniformly"是简化说法。）

### Q3 — 答案：C

讲义的对比："Chameleon / Emu3: N_tokens forward passes, typically 1024-4096 per image. Transfusion: ~20 steps. Show-o: ~16 steps." A 把数字张冠李戴；B 忽略了自回归逐 token 的成本；D 错误——自回归必须一个 token 一次前向。

### Q4 — 答案：B

讲义："The inpainting capability comes for free from the masked-prediction training. Mask a region of the VQ-token grid, feed the rest plus a text prompt, predict the masked tokens." 推理循环与文生图完全相同，只是初始状态不是全 mask。outputs 技能文件对比："Show-o is free; Transfusion adds a mask channel; Emu3 needs a separate fine-tune."

### Q5 — 答案：C

`cos(π × 4 / 16) = cos(π/4) ≈ 0.707`（代码实际输出 `step  3  mask_ratio = 0.707`）。A 是 step 1，B 是 step 2，D 是 step 4。注意代码用 `t + 1`，所以 step 0 已经是 0.981 而不是讲义公式中 t = 0 时的 1.0。

### Q6 — 答案：A

讲义："Image tokens: full bidirectional within the image block (so the masked tokens can see every other image token during prediction)." MaskGIT 的揭开顺序由置信度决定，可能先揭开右下角再揭开左上角；因果 mask 会让左上角永远看不到右下角已揭开的内容。B、D 不成立；C 与文本因果的要求相反。

### Q7 — 答案：D

`1,024 × log2(16,384) = 1,024 × 14 = 14,336 bit = 1,792 字节 = 1.75 KiB`；原始像素 `512 × 512 × 24 = 6,291,456 bit = 768 KiB`；比值 `6,291,456 / 14,336 ≈ 438.9`（已用 Python 计算）。C 的比例算错了一个数量级；A、B 用错了 bit 数。约 440 倍的压缩意味着大量高频细节交给 tokenizer 的解码器"脑补"，这就是讲义所说"still lossy by tokenizer"的根源。

### Q8 — 答案：B

LlamaGen（arXiv:2406.06525）是用 Llama 式 Transformer 对图像 VQ token 做**逐 token 自回归**生成的模型，讲义练习 5 正是让你对比"LlamaGen 的自回归"与"Show-o 的掩码方法"。所以讲义分类图把 LlamaGen 列进"离散 + 掩码扩散"与练习 5 自相矛盾，应归入 Chameleon/Emu3 那一类。

### Q9 — 参考答案

1. 实际揭开数：`2, 2, 2, 2, 3, 3, 1, 1`（已逐步复算）。
2. MaskGIT 语义：第 s 步之后应剩 `floor(N × ratio_s)` 个 mask。ratio = `[0.981, 0.924, 0.831, 0.707, 0.556, 0.383, 0.195, 0]` → 剩余 `15, 14, 13, 11, 8, 6, 3, 0` → 每步揭开 `1, 1, 1, 2, 3, 2, 3, 3`（已用 Python 计算）。
3. **本质差别**：cosine 的意图是"早期少揭（此时几乎没有上下文，预测最不可靠）、后期多揭"；代码却是前期每步揭 2 个（还被 `max(0.15, …)` 抬高）、最后两步只揭 1 个——**形状反了**。原因是 `keep_ratio = 1 - ratios[step]` 本该是"全局已揭开比例"，却被 `step_unmask` 当成"剩余 mask 中要提交的比例"来乘 `len(masked_indices)`。改写：

   ```python
   def sample(prompt_seed, T=8):
       tokens = [MASK] * SEQ_LEN
       traces = [list(tokens)]
       for step, ratio in enumerate(cosine_schedule(T)):
           remaining = sum(t == MASK for t in tokens)
           target_masked = 0 if step == T - 1 else min(remaining - 1, math.floor(SEQ_LEN * ratio))
           n_commit = max(1, remaining - target_masked)
           tokens = step_unmask_k(tokens, prompt_seed, n_commit)   # 直接按个数提交
           traces.append(list(tokens))
       return traces
   ```

   其中 `step_unmask_k` 把 `n_to_keep` 改为直接传入的个数。这样最后一步强制清零，也顺带解决了 Q10 的浮点问题。已实际运行：masked 数变为 `16 → 15 → 14 → 13 → 11 → 8 → 6 → 3 → 0`，正好 8 步；`T = 1` 时变为 `16 → 0`。

### Q10 — 参考答案

1. `math.cos(math.pi / 2) = 6.12e-17`（不是精确的 0），`keep_ratio = 1 − 6.12e-17 = 0.9999999999999999`，`int(16 × 0.9999999999999999) = int(15.999999999999998) = 15`。于是第一步只揭开 15 个，剩 1 个交给末尾的 `while any(...)` 兜底循环，多走了一步（已实际运行验证：`[16, 1, 0]`）。
2. T = 8 时最后一步只剩 1 个 mask，`int(1 × 0.9999…) = 0`，被 `max(1, …)` 抬成 1，碰巧掩盖了问题。
3. 修法：
   - 最后一步不依赖浮点，直接"全部提交"（Q9 的 `step == T - 1` 分支）；
   - 或用 `round`/加一个小 epsilon：`int(n * keep_ratio + 1e-9)`；
   - 更根本的是用"目标剩余个数"的整数逻辑，而不是浮点比例相乘后再截断。

### Q11 — 参考答案

1. `mock_logits` 对第 i 个位置只做三件事：高斯噪声（σ = 0.3）、在 `(prompt_seed + i) % VOCAB` 上加 2.5、若该位置**自己**已揭开则在自己的 token 上加 3.0。被 mask 位置的 logits **与其他位置是否揭开、揭开成什么完全无关**。2.5 的偏置远大于 0.3 的噪声，所以 argmax 永远是偏置 token（我们重复 1 万次、16 万个位置，没有一次例外）。最终序列就是 `(seed + i) % 8`；揭开顺序只由噪声决定。
2. 不一致。代码没有任何"看已揭开 token"的机制，讲义描述过度了。
3. 不能演示。在这个 mock 里一步全部揭开和八步揭开结果完全相同。最小改动示例：让每个位置倾向于"等于左邻 + 1"，并给第一个位置两个同样好的候选：

   ```python
   def mock_logits_dep(tokens, prompt_seed=0):
       logits = []
       for i, t in enumerate(tokens):
           base = [random.gauss(0, 0.3) for _ in range(VOCAB)]
           if i == 0:
               base[prompt_seed % VOCAB] += 2.0; base[(prompt_seed + 4) % VOCAB] += 2.0  # 双峰
           elif tokens[i - 1] != MASK:
               base[(tokens[i - 1] + 1) % VOCAB] += 3.0                              # 依赖左邻
           else:
               base[(prompt_seed + i) % VOCAB] += 1.0; base[(prompt_seed + 4 + i) % VOCAB] += 1.0
           if t != MASK:
               base[t] += 3.0
           logits.append(base)
       return logits
   ```

   一步并行解码时，每个位置各自在两个"模式"里按噪声选，序列会在两种模式之间来回跳（不连贯）；多步解码时，先提交的 token 会通过"左邻 + 1"约束后面的 token，序列保持一致。已实际运行验证（配合 Q9 的修正版 `sample`，200 次试验，统计相邻位置不满足"+1"的断点数）：T = 1 平均 7.47 个断点，T = 8 平均 2.19 个，T = 16 平均 0.21 个。一个 T = 1 的样例是 `7 0 5 6 7 4 5 2 7 4 5 6 7 0 1 2`，明显由两种模式的片段拼成。这正是练习 1 的答案：**并行预测假设被 mask 的 token 之间条件独立**，一步提交全部会把不同模式的片段拼在一起。

### Q12 — 参考答案

已用 Python 计算（"之后剩余 = floor(N × ratio)"）：

| 日程 | N = 16 每步揭开 | N = 1,024 每步揭开 |
|------|---------------|------------------|
| cosine | `1, 1, 1, 2, 3, 2, 3, 3` | `20, 58, 95, 127, 156, 177, 192, 199` |
| linear | `2, 2, 2, 2, 2, 2, 2, 2` | `128 × 8` |

- **linear 更"均衡"**（每步一样多）；cosine 是**前少后多**。
- cosine 的设计意图：第一步几乎没有上下文，预测质量最差，只提交极少数最有把握的 token 来"定调"（构图、主体）；随着上下文增多，预测越来越可靠，后面的步可以大胆一次提交更多。讲义说 cosine "concentrates mass on mid-range ratios where prediction is most informative"，linear "also work but plateau faster"。
- N = 16 时 cosine 的结果因为取整出现 `3, 2` 的小波动；N 越大曲线越平滑。

### Q13 — 参考回答要点

- **训练**：图像先经 VQ tokenizer 变成 token 网格；随机抽 mask 比例，把对应数量的 token 替换成 `<MASK>`；Transformer（图像块内双向注意力）预测被遮位置，交叉熵只算在被遮位置。
- **推理**：全 `<MASK>` → 每步一次前向，得到所有位置的分布 → 采样/取 argmax 并记录置信度 → 按日程决定本步保留多少，提交置信度最高的，其余重新 mask → 重复 8–16 步。
- **与 BERT 的关系**：同样是 masked language modeling；区别是 BERT 只做理解（固定 15% 比例），MaskGIT 把比例扩展到 0–100% 并配上迭代解码，变成了生成模型。
- **Show-o 的扩展**：把它放进一个因果 LLM 里，文本走 NTP，图像走掩码预测，混合注意力 mask，一个 checkpoint 做文本、VQA、文生图、inpainting。
- 加分点：MaskGIT 推理时会给置信度加上随温度退火的 Gumbel 噪声，增加多样性。

### Q14 — 参考回答要点

- **为什么多步**：一次前向给出的是每个位置的**边缘分布**，并行采样相当于假设它们条件独立。图像 token 之间强相关，一步全部提交会把不同"模式"的局部拼在一起（Q11 的演示）。多步让后提交的 token 以先提交的 token 为条件，近似联合分布。
- **步数太少**：不一致、伪影、细节差；**步数太多**：速度优势消失，但质量提升递减。讲义：8–16 步。
- **mask 日程**：决定每步提交多少——cosine 前少后多，先定全局结构再填细节。
- **按置信度提交**：优先确定最有把握的 token，把难的位置留到上下文更充分时再决定；也是 inpainting、编辑能自然工作的原因。
- 常见误区：把"步数"与"扩散时间步 1000"混淆——掩码扩散的训练比例是连续的，推理步数可以自由选择。

### Q15 — 参考回答要点

| 维度 | Emu3（离散自回归） | Show-o（离散掩码扩散） | Transfusion（连续扩散） |
|------|------------------|---------------------|---------------------|
| 推理前向次数 | 每 token 一次，1,024–4,096 | 约 16 次 | 约 20 次 |
| 单步内容 | 一次只出 1 个 token（可用 KV cache） | 一次预测所有被 mask 的 token | 一次对所有 patch 去噪 |
| 画质上限 | 受 tokenizer 限制 | 受 tokenizer 限制 | 连续表示，无量化损失，讲义认为最高 |
| 训练复杂度 | 最简单：单一 NTP | 单一交叉熵（NTP + 掩码预测） | 两种损失需调权重 |
| inpainting | 需单独微调 | 天然支持 | 需加 mask 通道 |

- 讲义还说 Show-o 每步成本低于 Transfusion（"discrete vocab logits vs continuous MSE loss"）——这一点需要谨慎：推理时不算损失，每步成本主要是一次 Transformer 前向，两者在同规模下相近。
- 结论：Show-o 是"离散路线的提速版"，Transfusion 是"质量优先的连续路线"。

### Q16 — 参考回答要点

- **10 秒、需要 VQA + 文生图 + inpainting、开源**：选 Show-o 家族。outputs 技能文件："Proposing Emu3 / Chameleon when inference latency is <10s per image" 是拒绝项；Show-o 约 16 步、inpainting 免费、单一损失训练稳定。
- **2 秒**：技能文件："If the user wants <2s per image generation, refuse Show-o and recommend Stable Diffusion + a separate VLM for understanding. Accept the multi-model complexity."
- **顶级画质**：技能文件："refuse Show-o / Emu3 and recommend Transfusion-family (MMDiT) or JanusFlow"，因为离散 tokenizer 是天花板。
- 其他需要交代的：tokenizer 选择（离散家族用 IBQ/MAGVIT-v2/SBER 类）、许可证、从 Show-o 迁移到 Transfusion 的路径。

### Q17 — 参考回答要点

- **严格吗**：形式上两者都是"在 `<MASK>`/目标位置上的交叉熵"，讲义把 NTP 看成"只 mask 最后一个 token"的特例。但实现上 Show-o 对文本和图像用不同的注意力（因果 vs 双向）、不同的 mask 方式，通常两项损失分开计算再加权求和，所以"同一个损失公式"更准确的说法是"同一种交叉熵、两种 mask 方式"。
- **文本能否并行**：可以，这就是离散扩散语言模型（如 masked diffusion LM）的方向；但文本 token 之间的依赖更强、可接受的错误更少，并行解码容易不通顺，所以 Show-o 仍让文本走自回归。
- **关键差异**：图像对局部误差更宽容（单个 token 不完美人眼不易察觉），文本一个错字就能改变语义——这也是讲义"Pick by task"背后的直觉。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 13 Transfusion：在同一个 Transformer 中结合 Autoregressive 文本与扩散图像](../../13-transfusion-autoregressive-diffusion/docs/zh.md)：混合注意力 mask 与两损失训练，本节的直接对照。
- [阶段 12 · 12 Emu3：通过下一 Token 预测生成图像与视频](../../12-emu3-next-token-for-generation/docs/zh.md)：离散自回归路线及其速度瓶颈。
- [阶段 12 · 11 Chameleon：仅用 Token 的早期融合 Multimodal Models](../../11-chameleon-early-fusion-tokens/docs/zh.md)：离散图像 token 与统一词表。
- [阶段 08 · 06 Diffusion Models — 从头开始的 DDPM](../../../08-generative-ai/06-diffusion-ddpm-from-scratch/docs/zh.md)：连续扩散的基础，对比离散扩散。
- [阶段 05 · 19 子词 Tokenization——BPE、WordPiece、Unigram、SentencePiece](../../../05-nlp-foundations-to-advanced/19-subword-tokenization/docs/zh.md)：离散 token 与词表的基本概念。

### 本节被哪些后续内容用到
- [阶段 12 · 15 Janus-Pro：用于统一 Multimodal Models 的解耦 Encoders](../../15-janus-pro-decoupled-encoders/docs/zh.md)：在统一模型中把理解与生成的视觉编码器拆开。
- [阶段 12 · 16 MIO 与任意模态互转的 Streaming Multimodal Models](../../16-mio-any-to-any-streaming/docs/zh.md)：离散 token 路线扩展到语音与音乐。
- [阶段 08 · 09 局部重绘（Inpainting）、扩图（Outpainting）与图像编辑](../../../08-generative-ai/09-inpainting-outpainting-editing/docs/zh.md)：扩散模型中的 inpainting 做法，对比本节"免费"的 inpainting。
- [阶段 08 · 19 视觉 Autoregressive 建模（VAR）：下一尺度预测](../../../08-generative-ai/19-visual-autoregressive-var/docs/zh.md)：另一种少步离散图像生成方法。

### 延伸关键词
`MaskGIT` · `Muse` · `masked discrete diffusion` · `iterative parallel decoding` · `cosine mask schedule` · `confidence-based remasking` · `Gumbel noise` · `MAGVIT-v2` · `LlamaGen` · `Show-o2` · `masked diffusion language model` · `inpainting`
