# 测验 · Emu3：通过下一 Token 预测生成图像与视频（Emu3: Next-Token Prediction for Image and Video Generation）

> **阶段 12 · 多模态 AI · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **提示**：本节中文讲义机器翻译质量很差，有几处意思完全译反（例如把 "beats SDXL" 译成"比 SDXL 差"），请以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Emu3 的核心论点 | 一个 Llama 式 decoder-only Transformer，只用 next-token prediction（NTP）一种损失，在"文本 + 图像 VQ token + 视频 VQ token"的统一词表上训练，就能同时做生成和理解 |
| 2 | Tokenizer 是质量天花板 | 离散 token 能否重建细节取决于视觉 tokenizer；讲义："Tokenizer quality is the ceiling"，Emu3 的贡献部分在于"训了一个很好的 tokenizer" |
| 3 | 图像 token 数 | 每个 token 覆盖 8×8 像素：512×512 → 64×64 = 4,096 个 token，codebook 大小 32,768；token 数随边长**平方**增长 |
| 4 | 3D（时空）VQ | 视频按时空小立方体量化（讲义写 4×4×4），利用相邻帧冗余；4 秒 8 FPS 256×256 → `64 × 64 × 8 = 32,768` 个 token |
| 5 | 单一损失 + 模态权重 | 所有模态共用同一个交叉熵，只在训练时按模态乘上权重平衡贡献；模型从数据格式（`<image>`、`<video>` 标签）里学会何时输出哪种 token |
| 6 | 一个权重、三种角色 | Emu3-Gen（文生图）、Emu3-Chat（看图说话/VQA）、Emu3-Stage2（视频生成/理解）只是不同 prompt 模板，没有任务专用 head |
| 7 | Classifier-free guidance（CFG） | 有/无条件各算一次 logits，`mixed = u + γ(c − u)`；γ = 0 纯无条件，γ = 1 纯条件，γ > 1 放大"条件带来的差异" |
| 8 | Temperature | 讲义：感知任务 1.0、图像生成 0.8；太高出伪影，太低模式坍缩 |
| 9 | 推理成本是硬伤 | 自回归逐 token 解码：4,096 token ÷ 30 tok/s ≈ 2 分钟/张（SDXL 2–5 秒）；开 CFG 还要再翻倍 |
| 10 | 统一模型路线 | 若 NTP 能在生成上追平扩散，就不再需要单独的文本编码器、扩散调度器和 VAE；Show-o、Janus-Pro、Transfusion 等都在此论点上延伸或反驳 |

### 核心技能（能动手做到）

- [ ] 给定分辨率、空间/时间压缩倍率、时长和 FPS，手算图像和视频的 token 数，并估算自回归生成延迟
- [ ] 写出 CFG 的 logit 混合公式，说清 γ = 0、1、>1 各自的含义，并能算出一个小例子的 softmax 结果
- [ ] 指出 CFG 在大 γ 下收敛到的是 `argmax(c − u)` 而不是"条件分布的众数"，并构造反例
- [ ] 读懂 `code/main.py` 的 `TokCost`、`cfg_mix`、`softmax`、`sample`，指出 `demo_sampling` 实验设计上的混杂变量
- [ ] 用 `6 × N × D` 估算 Emu3-7B 的训练 FLOPs，并换算成 GPU-hours
- [ ] 根据延迟预算和"是否需要理解 + 生成"在 Emu3 家族与扩散模型之间做选型

---

## 二、基础自测（选择题）

**Q1.** Emu3 的图像 tokenizer 每个 token 对应 8×8 像素。一张 512×512 的图像会变成多少个 image token？

- A. 1,024
- B. 2,048
- C. 4,096
- D. 32,768

**Q2.** CFG 的混合公式为 `mixed = uncond + γ · (cond − uncond)`。当 γ = 1 时：

- A. 等价于只使用条件 logits，没有任何引导效果
- B. 等价于只使用无条件 logits
- C. 等价于条件与无条件 logits 的平均
- D. 分布被锐化成 one-hot

**Q3.** 讲义设定视频 tokenizer 时空各压缩 4 倍。一段 4 秒、8 FPS、256×256 的视频片段有多少个 token？

- A. 4,096
- B. 8,192
- C. 16,384
- D. 32,768

**Q4.** 关于 Emu3 的训练目标，正确的是：

- A. 文本用 NTP，图像用扩散去噪损失，两者相加
- B. 只有一个 next-token prediction 损失，按模态乘以不同权重平衡贡献
- C. 先用 CLIP 对比损失对齐，再用 NTP 微调
- D. 图像 token 用 MSE 回归连续 latent，文本 token 用交叉熵

**Q5.** 关于 Emu3-Gen、Emu3-Chat、Emu3-Stage2，下列说法正确的是：

- A. 三者各有独立的 Transformer 主干，只共享 tokenizer
- B. Emu3-Gen 额外接了一个扩散解码头
- C. Emu3-Chat 使用 CLIP 视觉编码器，Emu3-Gen 使用 VQ tokenizer
- D. 三者底层是同一套权重，区别只在 prompt 模板和输入输出模态

**Q6.** 按代码中 30 tokens/s 的解码速度、不开 CFG，生成一张 1024×1024 图像（8×8 压缩）大约需要：

- A. 约 2 分钟
- B. 约 4.5 分钟
- C. 约 9 分钟
- D. 约 36 分钟

**Q7.** 在自回归图像生成中启用 CFG，每生成一个 image token 至少需要几次模型前向（不考虑把两路拼成一个 batch 的实现技巧）？

- A. 1 次
- B. 2 次：一次带完整 caption，一次带空 caption
- C. γ 次
- D. 4,096 次

**Q8.** 讲义给出的 Emu3 推荐 temperature 是：

- A. 感知任务 1.0，图像生成 0.8
- B. 感知任务 0.8，图像生成 1.0
- C. 所有任务都用 0，即贪心解码
- D. 图像生成用 1.5，以增加多样性

---

## 三、动手 / 代码题

**Q9.** 代码 `demo_sampling` 结尾打印："higher gamma converges on the conditional modes"。考虑下面这个两类别的例子：

```python
cond   = [3.0, 2.8]
uncond = [2.5, 0.0]
for gamma in [1, 3, 7]:
    print(gamma, softmax(cfg_mix(cond, uncond, gamma)))
```

1. 写出三种 γ 下的概率（保留 3 位小数）。
2. 条件分布本身的众数（mode）是哪个 token？γ 很大时选中的是哪个 token？
3. 用公式说明 γ → ∞ 时 CFG 收敛到什么，并据此修正代码里那句注释。

**Q10.** 阅读 `demo_sampling`：

```python
    cond = [[random.gauss(0, 2) for _ in range(K)] for _ in range(steps)]
    uncond = [[random.gauss(0, 1) for _ in range(K)] for _ in range(steps)]
    tokens_no_cfg = sample_tokens(cond, uncond, gamma=1.0, temp=1.0)
    tokens_cfg3 = sample_tokens(cond, uncond, gamma=3.0, temp=0.8)
    tokens_cfg7 = sample_tokens(cond, uncond, gamma=7.0, temp=0.8)
```

实际输出为：

```text
  no CFG      : [13, 12, 13, 1, 14, 14, 7, 11]
  CFG gamma=3 : [13, 0, 1, 1, 14, 14, 7, 11]
  CFG gamma=7 : [13, 0, 1, 1, 14, 14, 7, 11]
```

1. 这个对比实验有哪**两个**混杂因素，使得"no CFG 与 CFG 的差异来自 γ"这个结论不严谨？
2. 这个"采样器"为什么不算真正的**自回归**采样？真实的 Emu3 解码循环应该是什么样？
3. 请改写实验，使其只改变一个变量，并让三组共用同一串随机数。

**Q11.** `token_table` 把延迟算成 `tokens / 30.0`。

1. 补全讲义练习 1：1024×1024 和 2048×2048 各多少 token、按 30 tok/s 各需多久？
2. 如果开启 CFG 且两路前向**串行**执行，512×512 的延迟变成多少？如果把两路拼成 batch=2 一起算，延迟大约怎样变化？为什么？
3. 除了 token 数线性增长，图像变大还会让每步变慢——原因是什么？以 2048×2048 相对 512×512 为例，自注意力的总计算量大约是多少倍？

**Q12.** 讲义练习 4：讲义称 Emu3（7B 参数、约 300B 训练 token）的训练成本"roughly comparable to Llama-2-7B pretraining (2k-4k GPU-years on A100-class silicon)"。

1. 用 `FLOPs ≈ 6 × N × D` 估算训练 FLOPs。
2. 假设 A100 BF16 峰值 312 TFLOPS、MFU（模型 FLOPs 利用率）40%，折合多少 GPU-hours / GPU-years？
3. 这与讲义的 "2k-4k GPU-years" 是否一致？你会如何修订这句话？

---

## 四、面试高频题

**Q13.**（基础必考）Emu3 的核心论点是什么？传统观点为什么认为"图像生成必须用扩散"，Emu3 又是如何反驳的？

**Q14.**（原理深挖）Classifier-free guidance 在扩散模型和自回归模型中分别怎么做？γ 的大小对生成结果有什么影响？它的代价是什么？

**Q15.**（工程实践）自回归图像生成为什么慢？请给出至少四种加速思路，并说明各自的代价。

**Q16.**（场景设计）你要为一个产品选型：A 产品只做电商海报文生图、要求 5 秒内出图；B 产品需要"生成图片、描述图片、并回答关于用户上传图片的问题"。分别选 Emu3 家族还是扩散模型？理由是什么？

**Q17.**（追问型）视频为什么要用 3D（时空）tokenizer 而不是逐帧用 2D tokenizer？讲义练习 2 问"为什么是 4×4×4 而不是 8×8×1"，你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：C

`(512 / 8)² = 64² = 4,096`。A 是 256×256 的 token 数（或 Chameleon 的 1,024 token/张，那是更粗的 16×16 压缩）；B 没有对应含义；D 是 codebook 大小 32,768，不是 token 数——codebook 大小决定每个 token 的取值范围（约 15 bit），而 token 数由压缩倍率决定，两者不要混淆。

### Q2 — 答案：A

`u + 1 · (c − u) = c`，γ = 1 就是普通的条件生成，"没有额外引导"。B 对应 γ = 0；C 对应 γ = 0.5；D 只在 γ → ∞ 时才趋近（而且趋近的是 `argmax(c − u)`，见 Q9）。代码 `demo_cfg` 的输出中，γ = 1.0 那一行的 logits 正好等于 `cond = [2.0, 4.0, 1.0, 3.5, 0.5]`，可作验证。

### Q3 — 答案：D

帧数 `4 × 8 = 32`，时间压缩 4 倍 → 8；空间 `256 / 4 = 64` → 每帧 `64 × 64 = 4,096`；合计 `4,096 × 8 = 32,768`。代码 `TokCost("video 4s @8fps 256x256", 256, 4, 4.0, 8, 4)` 实际输出 32768，与讲义一致。A 只是一帧（时间片）的 token；B、C 是算错了时间或空间压缩的结果。（补充：Emu3 论文原文描述的视频 tokenizer 是时间 4×、空间 8×8 压缩，按那个口径同一片段是 `32 × 32 × 8 = 8,192` 个 token——讲义的 4×4×4 与论文口径可能不一致，建议核对原文。）

### Q4 — 答案：B

讲义："Emu3 uses one objective: next-token prediction on a shared vocabulary... Weights are multiplied by modality-specific factors during training to balance contribution, but the loss function is identical." A 是 Transfusion（下一节）的做法；C 中 "No CLIP loss" 是讲义明确否定的；D 是连续 latent 的回归式生成，与离散 token 的交叉熵无关。

### Q5 — 答案：D

讲义："No task-specific heads. Just different prompt templates. Same checkpoint." A、C 与"同一 checkpoint、无任务专用模块"矛盾；B 把 Emu3 与 Transfusion/扩散混为一谈——Emu3 推理时图像 token 由同一个 LM head 输出，再由 VQ 解码器还原像素。

### Q6 — 答案：C

`(1024 / 8)² = 16,384` 个 token，`16,384 / 30 ≈ 546 s ≈ 9.1 分钟`（代码实际输出 `546.1s`）。A 是 512×512（136.5 s）；B 是把 token 数算成 8,192；D 是 2048×2048（2,184.5 s ≈ 36 分钟）。而且这还是**低估**：没算 CFG 翻倍，也没算序列变长后每步注意力变慢（见 Q11）。

### Q7 — 答案：B

讲义："generate twice, once with the full caption, once with an empty caption, mix the logits"。每一步都要分别跑条件分支和无条件分支，两条分支各有自己的 KV cache。实现上常把两路拼成 batch=2 一次前向，墙钟时间增加不到 2 倍，但计算量和 KV cache 显存仍是 2 倍。C 混淆了"引导强度"和"前向次数"；D 是整张图的 token 数。

### Q8 — 答案：A

讲义："Emu3's recommended temperature is 1.0 for perception, 0.8 for image generation." B 说反了；C 贪心会让图像生成模式坍缩、纹理重复；D 讲义明确说 temperature 太高会产生伪影（artifacts）。注意本节代码 `sample_tokens` 的默认值 `temp=0.8` 与讲义一致。

### Q9 — 参考答案

1. 已实际运行验证：

   | γ | mixed logits | 概率 |
   |---|-------------|------|
   | 1 | `[3.0, 2.8]` | `[0.550, 0.450]` |
   | 3 | `[4.0, 8.4]` | `[0.012, 0.988]` |
   | 7 | `[6.0, 19.6]` | `[0.000, 1.000]` |

2. 条件分布的众数是 token 0（0.55 > 0.45）。γ ≥ 3 时选中的几乎必然是 token 1——**排序被翻转了**。
3. `mixed = u + γ(c − u) = γ(c − u) + u`。γ → ∞ 时 `(c − u)` 项主导，softmax 收敛到 `argmax(c − u)` 的 one-hot，也就是"**条件相对无条件提升最多**"的 token。token 0 的条件 logit 只比无条件高 0.5，token 1 高 2.8，所以大 γ 选 token 1。注释应改为："higher gamma sharpens toward the tokens the condition boosts most (argmax of cond − uncond), not necessarily the conditional mode"。
   - 这正是 CFG 的本意：放大"prompt 带来的信息"。但也解释了 γ 过大时的副作用：画面过饱和、多样性下降、偏离自然图像分布。
   - 在代码的 toy 数据里，`argmax(c − u)` 恰好与 `argmax(c)` 相同（8 步都是 `[13, 0, 1, 1, 14, 14, 7, 11]`），所以看起来像"收敛到条件众数"——这只是巧合。

### Q10 — 参考答案

1. **两个混杂因素**：
   - **γ 和 temperature 同时变了**："no CFG" 用 `gamma=1.0, temp=1.0`，CFG 两组用 `temp=0.8`。降温本身就会让分布变尖，无法区分差异是 γ 带来的还是 T 带来的。
   - **随机数不同**：三次 `sample_tokens` 依次消耗全局 `random` 流，每组看到的是不同的随机数 `r`。即使分布完全相同，结果也可能不同。
   - 已逐步检查：γ=1、T=1 时每步最大概率只有 0.34–0.82（例如第 2 步最大概率 0.486、第 3 步 0.339），所以采到非众数很正常；γ=3、T=0.8 时 8 步中有 6 步的最大概率 ≥ 0.83（另两步为 0.635 与 0.532）。γ=3 与 γ=7 输出完全相同，是因为这几步的分布已经很尖。
2. **不是真正的自回归**：`cond`/`uncond` 的 8 行 logits 是事先随机生成、彼此独立的，第 t 步的 logits 不依赖前面采到的 token。真实解码中，每采出一个 token 都要追加到两条序列（有 caption / 空 caption）末尾，再各做一次前向得到下一步的 `c_t`、`u_t`：

   ```python
   seq_c, seq_u = prompt_ids + [BOI], empty_ids + [BOI]
   for t in range(num_image_tokens):
       c = model(seq_c)[-1]; u = model(seq_u)[-1]      # 两次前向（或 batch=2）
       tok = sample(softmax(cfg_mix(c, u, gamma), temperature))
       seq_c.append(tok); seq_u.append(tok)            # 两路都追加同一个 token
   ```

3. 控制变量的改法：

   ```python
   def sample_with(rng, cond, uncond, gamma, temp):
       out = []
       for c, u in zip(cond, uncond):
           probs = softmax(cfg_mix(c, u, gamma), temperature=temp)
           r, acc = rng.random(), 0.0
           out.append(next((i for i, p in enumerate(probs) if (acc := acc + p) >= r), len(probs) - 1))
       return out

   for g in [1.0, 3.0, 7.0]:                 # 只改 γ，T 固定 0.8
       print(g, sample_with(random.Random(123), cond, uncond, g, 0.8))   # 每组用同一个种子
   ```

   这样三组共用同一串 `r`（common random numbers），差异只来自 γ。实际运行输出：

   ```text
   1.0 [0, 0, 6, 1, 14, 0, 7, 11]
   3.0 [13, 0, 1, 1, 14, 0, 7, 11]
   7.0 [13, 0, 1, 1, 14, 0, 7, 11]
   ```

   在同样的随机数下，γ 从 1 升到 3 改变了第 1、3 步的选择（向 `argmax(c − u)` 靠拢），而第 6 步三组都落在 token 0 上——说明即使开了 CFG，只要该步分布不是 one-hot，仍然有采样随机性。

### Q11 — 参考答案

1. 已实际运行：1024×1024 → `128² = 16,384` token，546.1 s ≈ 9.1 分钟；2048×2048 → `256² = 65,536` token，2,184.5 s ≈ 36.4 分钟。分辨率翻倍 → token 数 ×4 → 延迟至少 ×4。
2. 串行 CFG：每个 token 两次前向，`4,096 × 2 / 30 ≈ 273 s ≈ 4.6 分钟`。拼成 batch=2：decode 阶段是显存带宽瓶颈，读一次权重可以服务两条序列，所以墙钟时间增加远小于 2 倍（理想情况下接近 136.5 s 再加一些），但 KV cache 显存翻倍。可以给 `TokCost` 加一个 `cfg_passes` 字段，延迟写成 `tokens * cfg_passes / tps`。
3. 序列越长，每一步 decode 都要对前面所有 token 做注意力、读取越来越大的 KV cache，所以"30 tok/s"不是常数。整段生成的自注意力总计算量约与 `L²` 成正比：`(65,536 / 4,096)² = 256` 倍（已计算）。另外 KV cache 显存与 L 成正比，65K token 的单张图已接近长上下文 LLM 的量级——这就是 outputs 技能文件里"拒绝用 Emu3 做 4K 图像"的原因。

### Q12 — 参考答案

1. `6 × 7×10⁹ × 3×10¹¹ = 1.26 × 10²² FLOPs`。
2. 有效算力 `312 × 0.4 ≈ 125 TFLOPS`：`1.26×10²² / 1.25×10¹⁴ ≈ 1.0×10⁸ s ≈ 2.8 万 GPU-hours ≈ 3.2 GPU-years`（已用 Python 计算；MFU 取 50% 时约 2.2 万 GPU-hours）。
3. **不一致，差了约三个数量级**。"2k-4k GPU-years" ≈ 1,750 万–3,500 万 GPU-hours，远超 7B 模型在 300B token 上的需求。作为参照，Llama 2 论文报告 7B 模型在 2T token 上用了约 18.4 万 A100 GPU-hours（约 21 GPU-years）。合理的改写是"约数万 A100 GPU-hours（数个 GPU-years），与同规模 LLM 预训练同一量级"。
   - 注意 `6ND` 只计 Transformer 主体，不含 tokenizer 训练、数据过滤和多阶段训练；另外图像/视频序列很长，注意力部分的 FLOPs 比纯文本占比更高，真实值会偏大一些，但不可能大到上千 GPU-years。

### Q13 — 参考回答要点

- **传统观点**：①离散 image token 丢信息，重建不出细节；②自回归采样要连续生成上千个 token，误差逐步累积。所以 SD、DALL-E 3、Imagen、Midjourney 都用扩散。
- **Emu3 的反驳**：更好的视觉 tokenizer + 足够规模 + 单一 NTP 损失，就能在同一模型里做到扩散级生成质量，同时做理解。
  - tokenizer：8×8 压缩、32,768 codebook，讲义称重建 PSNR 30.5 dB，接近 SD 连续 latent 的 32 dB；
  - 训练：所有模态共享词表与交叉熵，只按模态加权；
  - 推理：借用扩散的 CFG 提升质量。
- **结果**（讲义转述）：MJHQ-30K FID 5.4 vs SDXL 5.6；VQAv2 75.1 vs LLaVA-1.6 72.4；GenEval 0.54 vs 0.55 基本打平（严格说略低）。
- **意义**：统一模型不再需要独立的文本编码器、扩散调度器和 VAE，"一个 Transformer + 每模态一个 tokenizer + 规模"。
- 常见误区：说"Emu3 完全不用扩散技巧"——它在推理时用了 CFG；说"Emu3 比扩散快"——恰恰相反。

### Q14 — 参考回答要点

- **扩散中的 CFG**：训练时以一定概率丢弃条件（空 prompt），同一个网络学会条件与无条件两种去噪；推理时每一步 `ε = ε_u + γ(ε_c − ε_u)`。
- **自回归中的 CFG**：同理，对每个 token 位置分别用"完整 caption"和"空 caption"做前向，在 **logits** 上混合 `u + γ(c − u)`，再 softmax 采样；两路序列追加同一个采样结果。
- **γ 的影响**：γ = 0 无条件、γ = 1 普通条件生成、γ > 1 放大 prompt 带来的差异——图文一致性更强、画面更"干净"，但多样性下降，γ 过大会过饱和、出伪影。讲义给的典型范围是 3.0–7.0。大 γ 下收敛到 `argmax(c − u)`（见 Q9）。
- **代价**：每步两次前向（或 batch=2）、两份 KV cache；训练时需要留一部分无条件样本（caption dropout）。
- 加分点：CFG 可以理解为在 `log p(x|c) − log p(x)` 这个"隐式分类器"方向上加强，近似从 `p(x) · p(c|x)^γ` 采样；temperature 与 γ 都会让分布变尖，调参时要一起考虑。

### Q15 — 参考回答要点

- **为什么慢**：一张 512×512 图要串行生成 4,096 个 token，每步一次完整前向（开 CFG 是两次）；decode 是显存带宽瓶颈，GPU 算力用不满；序列越长每步注意力越贵。讲义：约 2 分钟/张 vs SDXL 2–5 秒。
- **加速思路与代价**：
  1. **KV cache + 批处理并发**：基础操作；代价是显存，长序列 + CFG 下 KV cache 很大。
  2. **Speculative decoding**：小模型起草、大模型并行验证；讲义说它能"narrow the gap"，但图像 token 熵较高、接受率不如文本。
  3. **更高压缩率的 tokenizer**：如 16×16 压缩让 token 数降为 1/4；代价是重建质量下降（质量天花板降低）。
  4. **并行/掩码式解码**：MaskGIT、Show-o（下一节之后）一次预测多个被 mask 的 token，十几步完成；代价是需要改训练目标。
  5. **Next-scale 预测（VAR）**：从粗到细逐尺度生成，每个尺度内并行。
  6. **Multi-token prediction** 等一次预测多个 token 的头。
- 结论：讲义说这些手段"narrow the gap but do not close it"，自回归图像生成的推理成本是长期存在的取舍。

### Q16 — 参考回答要点

- **A 产品（纯文生图、< 5 秒）**：选扩散（SDXL / SD3 / Flux 类）。outputs 技能文件的拒绝规则：延迟预算 < 5 s/张时拒绝 Emu3。Emu3 512×512 就要约 2 分钟。
- **B 产品（生成 + 描述 + 理解第三方图片）**：选 Emu3 家族统一模型。技能文件："If product must emit images AND describe them AND reason about third-party images, recommend Emu3-family"；扩散模型本身不能理解图像，要额外接一个 VLM，系统变成两套模型。
- **补充考量**：
  - 许可证：技能文件提醒部分 Emu3 版本仅限研究用途，商用前先查许可；
  - 一定要给出 CFG 配置（典型 γ = 3，强遵循 5–7），否则质量崩；
  - 超高分辨率（2048+）不适合 Emu3：token 数和 KV cache 爆炸。
- 加分点：B 产品也可以考虑"VLM + 扩散"的组合方案，对比运维复杂度与统一模型的跨任务一致性（例如编辑一张刚生成的图）。

### Q17 — 参考回答要点

- **为什么 3D**：相邻帧高度冗余。逐帧 2D tokenize 会让 token 数正比于帧数（32 帧 × 每帧 token），而时空立方体把 4 帧合并成一个时间片，token 数降为 1/4；同时 tokenizer 学到运动信息，生成时更容易保持时间一致性。
- **4×4×4 vs 8×8×1**：两者每个 token 都覆盖 64 个像素位置，token 总数相同。区别在于信息组织：8×8×1 只在单帧内压缩，完全不利用时间冗余，而且空间压缩更粗、单帧细节损失更大；4×4×4 把压缩"分摊"到时间维，空间分辨率保留更多，时间上平滑的内容几乎不损失信息。
- 以讲义例子：4 秒 8 FPS 256×256 → 32,768 token，单个片段就和长上下文 LLM 的 prompt 一样长，所以视频生成对 tokenizer 压缩率非常敏感。
- 加分点：指出讲义 4×4×4 的说法与 Emu3 论文（时间 4×、空间 8×8）可能不一致，并说明"时空压缩倍率是一个可调设计参数，需要在重建质量与序列长度之间折中"。

---

## 六、关联知识点

### 前置知识
- [阶段 12 · 11 Chameleon：仅用 Token 的早期融合 Multimodal Models](../../11-chameleon-early-fusion-tokens/docs/zh.md)：统一词表、早期融合，本节是它在生成质量上的放大版。
- [阶段 12 · 01 Vision Transformers 与 Patch-Token 基本单元](../../01-vision-transformer-patch-tokens/docs/zh.md)：图像切块与 token 数的计算方式。
- [阶段 08 · 02 自动编码器和变分自动编码器 (VAE)](../../../08-generative-ai/02-autoencoders-vae/docs/zh.md)：VQ tokenizer 的编码器—解码器基础。
- [阶段 08 · 07 潜空间扩散（Latent Diffusion）与 Stable Diffusion](../../../08-generative-ai/07-latent-diffusion-stable-diffusion/docs/zh.md)：本节对比的扩散路线与 CFG 的来源。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：next-token prediction、temperature 采样与 KV cache。

### 本节被哪些后续内容用到
- [阶段 12 · 13 Transfusion：在同一个 Transformer 中结合 Autoregressive 文本与扩散图像](../../13-transfusion-autoregressive-diffusion/docs/zh.md)：放弃离散图像 token，改用"NTP + 扩散"双损失。
- [阶段 12 · 14 Show-o 与离散扩散统一模型](../../14-show-o-discrete-diffusion-unified/docs/zh.md)：保留离散 token，但用掩码并行解码解决本节的速度问题。
- [阶段 12 · 15 Janus-Pro：用于统一 Multimodal Models 的解耦 Encoders](../../15-janus-pro-decoupled-encoders/docs/zh.md)：理解与生成用不同的视觉编码器。
- [阶段 12 · 16 MIO 与任意模态互转的 Streaming Multimodal Models](../../16-mio-any-to-any-streaming/docs/zh.md)：把统一词表扩展到语音与音乐。
- [阶段 08 · 19 视觉 Autoregressive 建模（VAR）：下一尺度预测](../../../08-generative-ai/19-visual-autoregressive-var/docs/zh.md)：另一条加速自回归图像生成的路线。
- [阶段 10 · 15 Speculative Decoding 与 EAGLE-3](../../../10-llms-from-scratch/15-speculative-decoding-eagle3/docs/zh.md)：讲义提到的缩小推理差距手段。

### 延伸关键词
`next-token prediction` · `VQ-VAE / VQGAN` · `MoVQGAN` · `codebook size` · `3D causal VQ` · `classifier-free guidance` · `caption dropout` · `MJHQ-30K / FID` · `GenEval` · `FVD` · `MaskGIT` · `VAR` · `6ND FLOPs 估算`
