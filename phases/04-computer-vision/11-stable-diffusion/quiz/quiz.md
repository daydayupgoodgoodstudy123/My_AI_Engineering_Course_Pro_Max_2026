# 测验 · Stable Diffusion——架构与 Fine-Tuning（Stable Diffusion — Architecture & Fine-Tuning）

> **阶段 04 · 计算机视觉 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过（或读懂）代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 潜空间扩散（latent diffusion） | 预训练 VAE 把 3×512×512 图像压成 4×64×64 latent，扩散全程在 latent 上做，数值量减少 48 倍，消费级 GPU 才跑得动 |
| 2 | 五个组件 | VAE（编解码，冻结）、文本编码器（CLIP / T5）、U-Net 去噪器（含 cross-attention）、调度器（采样算法）、可选的安全检查器 |
| 3 | Cross-attention | 在 U-Net 每个分辨率的 Transformer 块里，latent token 做 Query，文本 token 做 Key/Value，把提示词注入去噪过程 |
| 4 | Classifier-free guidance | 训练时约 10% 概率丢掉文本条件，一个模型同时学会有条件/无条件预测；推理时 `ε = ε_uncond + w·(ε_cond − ε_uncond)`，SD 默认 `w = 7.5` |
| 5 | VAE 缩放系数 | latent 乘 0.18215（SD 1.x/2.x）或 0.13025（SDXL），把方差缩放到约 1，匹配扩散的噪声假设 |
| 6 | img2img 与 inpainting | img2img：编码 → 加部分噪声（`strength`）→ 去噪 → 解码；inpainting：只重新生成 mask 白色区域 |
| 7 | 调度器 | DDIM、Euler ancestral、DPM-Solver++ 2M Karras（20–30 步，生产默认）、LCM/Turbo（1–4 步）；与权重解耦，换调度器不用重训 |
| 8 | LoRA 微调 | 冻结基座，在注意力层注入 `W + α·(A @ B)`，r 常取 4–32；适配器 10–50 MB，可加载、缩放、融合（fuse）或卸载 |
| 9 | 生产选型 | 模型族（SD 1.5 / SDXL / SD3 / FLUX）、调度器、精度（fp16 / bf16 / int8）、额外控制（ControlNet） |

### 核心技能（能动手做到）

- [ ] 给定分辨率和 VAE 下采样倍数，算出 latent 形状和压缩比
- [ ] 写出 CFG 的组合函数，并能说清 `w = 0 / 1 / 7.5 / 15` 各自的含义与现象
- [ ] 用 `diffusers` 完成文生图、换调度器、img2img、inpainting、加载 LoRA 的完整调用
- [ ] 把讲义里的 LoRA 训练伪代码改写成符合 `diffusers` API 的正确训练步（冻结、缩放系数、清零梯度、只优化 LoRA 参数）
- [ ] 计算某个线性层加 LoRA 后新增的参数量，并解释 B 初始化为 0 的原因
- [ ] 根据延迟、保真度、许可证约束，为一个产品选出模型族、调度器、精度组合

---

## 二、基础自测（选择题）

**Q1.** 用 SD 1.5 的 VAE（空间下采样 8 倍、4 通道）生成 768×768 的图像，latent 形状与"像素数值量 / latent 数值量"之比分别是：

- A. `4×96×96`，48 倍
- B. `4×64×64`，108 倍
- C. `3×96×96`，64 倍
- D. `4×192×192`，12 倍

**Q2.** 在 CFG 公式 `ε = ε_uncond + w·(ε_cond − ε_uncond)` 中，`w = 1` 表示：

- A. 完全无条件生成
- B. 普通的条件生成（只用 `ε_cond`，不做额外放大）
- C. 文本条件强度加倍
- D. 关闭文本编码器

**Q3.** 开启 CFG 后，每个去噪步的计算量大约变成原来的：

- A. 不变，因为只是一次线性组合
- B. 约 2 倍，因为每步要分别预测有条件和无条件的噪声（通常把两者拼成一个 batch 一起算）
- C. 约 `w` 倍
- D. 约一半

**Q4.** 按讲义的 LoRA 训练方案，下列哪部分会接收梯度并被更新？

- A. VAE 编码器
- B. 文本编码器
- C. U-Net 原始权重
- D. 注入到注意力层的低秩矩阵 A、B

**Q5.** img2img 中把 `strength` 设为 1.0，结果与输入图几乎无关，原因是：

- A. 1.0 会关闭 VAE
- B. `strength` 决定去噪前加多少噪声，1.0 相当于把输入 latent 完全加噪成纯噪声，再从头生成，原图信息被抹掉
- C. 1.0 会把 CFG 关掉
- D. 这是 bug

**Q6.** SD U-Net 中 cross-attention 的 Q、K、V 分别来自：

- A. Q、K、V 都来自文本嵌入
- B. Q 来自图像 latent 的空间位置（token），K、V 来自文本编码器输出的 token 序列
- C. Q 来自文本，K、V 来自 latent
- D. Q、K、V 都来自 latent，文本只用于选择调度器

**Q7.** 训练和推理时 latent 都要乘以 0.18215（SD 1.5），其作用是：

- A. 把 latent 的方差缩放到约 1，使之与扩散过程假设的单位方差噪声尺度匹配
- B. 把图像从 [0,255] 缩放到 [0,1]
- C. 把 latent 量化成 int8
- D. 这是文本嵌入的温度系数

---

## 三、动手 / 代码题

**Q8.** 阅读 `cfg_sweep_demo`：

```python
def cfg_sweep_demo():
    values = [1.0, 3.0, 5.0, 7.5, 10.0, 15.0]
    print("\n[cfg sweep values to try on a real pipeline]")
    for w in values:
        effect = (
            "unconditional" if w <= 1.0
            else "creative but weak prompt adherence" if w < 5.0
            else "standard" if w <= 8.0
            else "strong adherence, possible oversaturation" if w <= 12.0
            else "heavy artefacts"
        )
        print(f"  w={w:5.1f}  expected: {effect}")
```

(a) 写出 `w = 1.0` 和 `w = 7.5` 两行的完整输出（注意格式符 `:5.1f`）。
(b) `w = 1.0` 被标成 `"unconditional"`，这与讲义一致吗？请改正这段链式条件表达式。

**Q9.** 写一个函数 `cfg_combine(eps_uncond, eps_cond, w)`（用 Python 列表即可），并计算：`eps_uncond = [0.2, -0.1]`、`eps_cond = [0.5, 0.3]` 时，`w = 0, 1, 7.5` 的结果。从结果说明为什么 `w` 过大会出现过饱和和伪影。

**Q10.** 下面是讲义与代码中的 LoRA 训练伪代码。请找出至少 4 处如果照搬到 `diffusers` 会出错或不符合讲义描述（"只有 LoRA 矩阵接收梯度"）的地方，并写出修正后的训练步。

```python
for step, batch in enumerate(dataloader):
    images, prompts = batch
    latents = vae.encode(images).latent_dist.sample() * 0.18215
    t = torch.randint(0, num_train_timesteps, (batch_size,))
    noise = torch.randn_like(latents)
    noisy_latents = scheduler.add_noise(latents, noise, t)
    text_emb = text_encoder(tokenizer(prompts))
    pred_noise = unet(noisy_latents, t, text_emb)       # LoRA weights injected
    loss = F.mse_loss(pred_noise, noise)
    loss.backward()
    optimizer.step()
```

**Q11.** 某个 U-Net 自注意力层的 `to_q` 是 `320 → 320` 的线性层，cross-attention 的 `to_k` 是 `768 → 320`（768 是 CLIP-L 文本嵌入维度）。

(a) 分别计算 r = 4 时 LoRA 新增的参数量，以及占原权重参数量的比例（不计 bias）。
(b) LoRA 中通常把 B（或讲义记号中的第二个矩阵）初始化为 0，为什么？
(c) `pipe.fuse_lora(lora_scale=0.8)` 之后想换另一个 LoRA，应该先做什么？

---

## 四、面试高频题

**Q12.**（基础必考）请从"输入一句提示词"开始，完整描述 Stable Diffusion 生成一张图的过程；再说明它的训练阶段哪些组件是冻结的、损失是什么。

**Q13.**（原理深挖）为什么要在 VAE 的 latent 空间里做扩散？这样做的代价是什么？讲义说"随机 latent 解码出来是垃圾"，这说明了什么？

**Q14.**（原理深挖）Classifier-free guidance 的原理是什么？为什么叫"classifier-free"？`w` 太大会怎样，有哪些缓解办法？

**Q15.**（工程实践）运营给你 15 张公司吉祥物的图，希望 SD 能在各种场景里画出它。请给出完整的 LoRA 微调方案，以及如何判断过拟合。

**Q16.**（场景设计）你要上线一个文生图 API：P95 延迟 < 2 秒、单卡 24 GB、需要商用。请给出模型、调度器、精度、控制方式与安全方面的选型，并说明取舍。

---

## 五、参考答案与解析

### Q1 — 答案：A

`768 / 8 = 96`，latent 为 `4×96×96 = 36,864` 个数；像素为 `3×768×768 = 1,769,472` 个数；比值 `1,769,472 / 36,864 = 48`。压缩比只取决于"下采样 8 倍 + 3 通道变 4 通道"：`3·8·8 / 4 = 48`，与分辨率无关。讲义的代码输出也给出了 1024×1024 对应 `4×128×128`。

### Q2 — 答案：B

代入 `w = 1`：`ε = ε_uncond + (ε_cond − ε_uncond) = ε_cond`，就是普通的条件预测，没有额外放大。讲义原文："w=0 is unconditional, w=1 is plain conditional, w>1 pushes the output toward being more conditioned on the prompt"。（`diffusers` 中 `guidance_scale ≤ 1` 时会直接关闭 CFG，只算条件分支，结果同样是普通条件生成。）

### Q3 — 答案：B

每一步需要 `ε_cond` 和 `ε_uncond` 两次 U-Net 预测。实现上通常把 latent 复制一份、文本嵌入拼成 `[空提示, 提示]`，作为 batch=2 一次前向，耗时和显存都接近翻倍。线性组合本身的开销可以忽略。负向提示词（negative prompt）就是用它的嵌入替换"空提示"的那一路。

### Q4 — 答案：D

讲义 Step 6："Only the LoRA matrices receive gradient; the base U-Net, VAE, and text encoder are frozen"。这样 batch=1 + gradient checkpointing 可以在 8 GB 显存里训练。也有方案同时给文本编码器加 LoRA，但那不是本节讲义描述的配置。

### Q5 — 答案：B

`strength` 决定从扩散过程的哪个时间点开始去噪：0 表示不加噪声（原样返回），1.0 表示加噪到最大噪声水平——此时 latent 与纯高斯噪声几乎无异，原图结构被完全抹掉，等价于文生图。讲义建议风格迁移用 0.5–0.7：既保留构图，又能改变风格。

### Q6 — 答案：B

把 latent 特征图的每个空间位置看作一个 token，作为 Query；文本编码器输出的 token 序列（SD 1.5 中为 77 个 768 维向量）经线性投影后作为 Key 和 Value。于是每个空间位置都能"查询"提示词里与之相关的词。self-attention 才是 Q、K、V 都来自 latent。

### Q7 — 答案：A

VAE 编码器输出的原始 latent 方差远大于 1；乘以 0.18215 后约为单位方差，这样前向加噪 `√ᾱ·x_0 + √(1−ᾱ)·ε` 中信号与噪声的相对比例才符合调度器的设计。解码前要除回这个系数。讲义 Key Terms："Constant that rescales the VAE's raw latent to roughly unit variance; hardcoded in every SD pipeline"。SDXL 的 VAE 不同，系数是 0.13025。

### Q8 — 参考答案

(a) `:5.1f` 表示总宽度 5、保留 1 位小数，右对齐：

```text
  w=  1.0  expected: unconditional
  w=  7.5  expected: standard
```

（已在临时目录用桩模块代替 `torch` 实际运行验证。）

(b) **不一致。** 按讲义，`w = 0` 才是无条件，`w = 1` 是普通条件生成。代码把所有 `w ≤ 1.0` 都标成 "unconditional"，`w = 1.0` 那一行是错的。修正示例：

```python
        effect = (
            "unconditional" if w == 0.0
            else "plain conditional (no guidance)" if w <= 1.0
            else "creative but weak prompt adherence" if w < 5.0
            else "standard" if w <= 8.0
            else "strong adherence, possible oversaturation" if w <= 12.0
            else "heavy artefacts"
        )
```

链式条件表达式从左到右求值，第一个为真的分支生效；所以区间的边界顺序很重要，`w == 0.0` 必须放在 `w <= 1.0` 之前。

### Q9 — 参考答案

```python
def cfg_combine(eps_uncond, eps_cond, w):
    return [u + w * (c - u) for u, c in zip(eps_uncond, eps_cond)]

u, c = [0.2, -0.1], [0.5, 0.3]
for w in (0, 1, 7.5):
    print(w, [round(v, 4) for v in cfg_combine(u, c, w)])
# 0   [0.2, -0.1]   —— 无条件
# 1   [0.5, 0.3]    —— 普通条件
# 7.5 [2.45, 2.9]   —— 沿 (cond − uncond) 方向外推 7.5 倍
```

解释：CFG 不是在两个预测之间插值，而是**沿"条件方向"外推**。`w = 7.5` 时噪声预测的数值已经是 `ε_cond` 的好几倍，远离模型在训练中见过的范围；`w` 越大，每一步对 latent 的修改越激进，累积起来使 latent 偏离 VAE 能正常解码的区域，表现为颜色过饱和、对比度过高、"烧焦"般的伪影。讲义练习 1 让你用 `[1, 3, 5, 7.5, 10, 15]` 观察这一现象。

### Q10 — 参考答案

问题清单：

1. **缺少 `optimizer.zero_grad()`**：梯度会在每一步累加，这在任何 PyTorch 训练循环里都是 bug。
2. **没有冻结、也没有注入 LoRA**：伪代码只在注释里说"LoRA weights injected"。需要先冻结 VAE、文本编码器、U-Net（`requires_grad_(False)`），再给 U-Net 注入 LoRA，并且优化器只接收 LoRA 参数——否则谈不上"只有 LoRA 矩阵接收梯度"。
3. **`tokenizer(prompts)` 返回的是字典**，不能直接喂给文本编码器；需要 padding 到固定长度、`return_tensors="pt"`，取 `input_ids`，再取编码器输出的 `last_hidden_state`（`[0]`）。
4. **`unet(...)` 返回的是输出对象**而不是张量；`diffusers` 的 `UNet2DConditionModel` 需要用 `encoder_hidden_states=` 传文本嵌入，并通过 `.sample` 取出噪声预测。
5. **缩放系数硬编码**：最好用 `vae.config.scaling_factor`，换成 SDXL 时自动变成 0.13025。
6. **时间步设备**：`torch.randint` 默认在 CPU 上，应与 latent 同设备；VAE 编码与文本编码不需要梯度，可放在 `torch.no_grad()` 里省显存。

修正后的训练步（按 `diffusers` + `peft` 的常见写法）：

```python
from peft import LoraConfig

vae.requires_grad_(False)
text_encoder.requires_grad_(False)
unet.requires_grad_(False)
unet.add_adapter(LoraConfig(r=8, lora_alpha=8, init_lora_weights="gaussian",
                            target_modules=["to_k", "to_q", "to_v", "to_out.0"]))
lora_params = [p for p in unet.parameters() if p.requires_grad]
optimizer = torch.optim.AdamW(lora_params, lr=1e-4)
num_train_timesteps = noise_scheduler.config.num_train_timesteps

for step, (images, prompts) in enumerate(dataloader):
    images = images.to(device)                                   # 已归一化到 [-1, 1]
    with torch.no_grad():
        latents = vae.encode(images).latent_dist.sample() * vae.config.scaling_factor
        ids = tokenizer(prompts, padding="max_length", truncation=True,
                        max_length=tokenizer.model_max_length, return_tensors="pt").input_ids
        text_emb = text_encoder(ids.to(device))[0]

    noise = torch.randn_like(latents)
    t = torch.randint(0, num_train_timesteps, (latents.shape[0],), device=device)
    noisy_latents = noise_scheduler.add_noise(latents, noise, t)

    pred_noise = unet(noisy_latents, t, encoder_hidden_states=text_emb).sample
    loss = F.mse_loss(pred_noise.float(), noise.float())

    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
```

这与第 10 节 `train_step` 的结构完全一样——只是数据从像素换成了 latent、网络多了文本条件、可训练参数只剩 LoRA。

### Q11 — 参考答案

(a) LoRA 新增参数 = `r·(d_in + d_out)`：
- `to_q`（320→320）：`4·(320 + 320) = 2,560`；原权重 `320·320 = 102,400`；占比 **2.5%**。
- `to_k`（768→320）：`4·(768 + 320) = 4,352`；原权重 `768·320 = 245,760`；占比约 **1.8%**。

整个 U-Net 上加起来也只是百万量级的参数，所以适配器文件只有几 MB 到几十 MB（讲义：10–50 MB），而基座有约 860M 参数。

(b) 把其中一个矩阵初始化为 0，则训练开始时 `A @ B = 0`，模型输出与原始基座**完全一致**；训练从"原模型"出发平滑地学习增量，不会一上来就被随机扰动破坏已经学好的生成能力。另一个矩阵用随机初始化，保证梯度不为 0、能够开始学习。

(c) 先 `pipe.unfuse_lora()`。`fuse_lora` 把 `W + scale·ΔW` 直接写进基座权重以省去推理时的额外计算，代价是不能直接切换；讲义："Call `pipe.unfuse_lora()` before loading a different adapter"。不融合时则可以动态调整 `lora_scale` 或叠加多个 LoRA。

### Q12 — 参考回答要点

- **推理流程**：①分词后经文本编码器（SD 1.5 为 CLIP ViT-L 文本塔）得到 token 嵌入序列；同时准备空提示（或负向提示）的嵌入。②在 latent 空间采样初始噪声 `4×64×64`。③调度器决定时间步序列（如 DPM-Solver++ 25 步）；每一步 U-Net 以 `(latent, t, 文本嵌入)` 为输入预测噪声，cross-attention 在每个分辨率注入文本；有条件/无条件两路按 CFG 组合；调度器据此更新 latent。④最终 latent 除以缩放系数，经 VAE 解码器得到 512×512 图像。⑤可选的安全检查器过滤输出。
- **训练阶段**：VAE 先单独训练好并冻结；文本编码器使用预训练 CLIP 并冻结；只训练 U-Net。数据流：图像 → VAE 编码 → 乘缩放系数 → 随机 t、加噪 → U-Net 预测噪声 → MSE，与第 10 节 DDPM 一样；同时以约 10% 的概率把文本换成空提示，让同一模型学会无条件预测，供 CFG 使用。
- **加分点**：指出调度器与权重解耦（训练用 DDPM 的 1000 步，推理可换任何调度器）；SDXL / SD3 / FLUX 只是替换了文本编码器、去噪器（U-Net 或 DiT）和 VAE，模板相同。

### Q13 — 参考回答要点

- **为什么**：像素空间里大部分计算花在人眼不敏感的高频细节上。先用 VAE 去掉感知冗余（8 倍下采样，48 倍数值压缩），扩散模型就可以把全部容量用于建模语义和构图；训练与采样的计算大幅下降，讲义给出的对比是从每张图几十秒降到两秒以内。
- **代价**：①生成质量的上限受 VAE 重建能力限制——小字、细纹理、小人脸等细节可能在编解码中丢失或变形；②多了一个需要单独训练、并要与扩散模型配套的组件（缩放系数、通道数）；③编辑类任务需要先编码，编码近似可逆但非完全可逆。后续模型（如 SD3）通过增加 latent 通道数来提升重建质量。
- **"随机 latent 解码是垃圾"**：有效图像只占据 latent 空间中的一个特定子流形，VAE 解码器只在这个子流形附近训练过。扩散模型的任务正是把高斯噪声一步步搬到这个子流形上。这也解释了 img2img（从真实图像的 latent 出发）为什么能保住结构。
- **加分点**：SD 的 VAE 训练用了重建 + 感知损失 + patch 判别器的对抗损失，这是第 09 节 GAN 思想的延续。

### Q14 — 参考回答要点

- **原理**：早期的 classifier guidance 需要额外训练一个在带噪图像上工作的分类器，用它的梯度 `∇log p(c | x_t)` 推动采样。由贝叶斯公式，`∇log p(c | x_t) = ∇log p(x_t | c) − ∇log p(x_t)`，而分数与噪声预测成正比（`∇log p(x_t) ∝ −ε`），所以这个"隐式分类器梯度"正比于 `ε_cond − ε_uncond`。CFG 用同一个模型的两种预测代替分类器——因此叫 classifier-free。
- **训练**：以约 10% 的概率把条件替换为空嵌入，一个模型学会两种预测。
- **w 的权衡**：`w` 越大，提示词遵循度越高、样本越"典型"，但多样性下降；过大（quiz.json 中给出的经验阈值约为 9–12，代码里 `w > 12` 标为 heavy artefacts）会过饱和、出现伪影。SD 默认 7.5。
- **缓解**：把 `w` 控制在 5–9；对 CFG 结果做重缩放（CFG rescale）；只在部分时间步施加 guidance 或对 guidance 做调度（quiz.json 提到的 CFG scheduling）；用负向提示词明确排除不想要的内容。蒸馏模型（如 LCM、Turbo）通常要求很低的 guidance 甚至不用。
- **常见误区**：以为 CFG 是"两个模型平均"——它是同一模型、外推而不是平均。

### Q15 — 参考回答要点

- **数据**：15 张图做裁剪/去背景处理，统一到 512（SD 1.5）或 1024（SDXL）；为每张图写描述，并加入一个罕见的触发词（如 `sks_mascot`），让 LoRA 把身份绑定到这个词上；描述里写清背景、姿态等可变因素，避免模型把背景也学成身份的一部分。
- **训练配置**：冻结基座，只训 LoRA（rank 8–32 起步，讲义说 r 常取 4–32）；学习率约 1e-4 量级；batch 1–2 + gradient checkpointing + fp16/bf16，8 GB 级显存可行；步数从约 1,000 步开始，每隔几百步保存一次检查点。本节 `outputs/skill-lora-training-setup.md` 就是用来生成这类配置的。
- **防过拟合**：每个检查点用一组固定的"新场景"提示词和固定种子出图，看身份是否保持、背景和姿态是否仍能变化；如果所有图都长得像训练图（同样的背景、构图），或者不加触发词也会出现吉祥物，说明过拟合/概念泄漏；可以加入同类别的正则化图（DreamBooth 的 prior preservation 思路）。
- **推理**：`load_lora_weights` 后用 `lora_scale`（如 0.6–1.0）调节强度；上线时可 `fuse_lora` 提速，切换前先 `unfuse_lora`。
- **评估**：身份一致性可用人工评审，也可用图像嵌入（如 CLIP 图像相似度）与参考图比较；提示词遵循度用 CLIP score（第 08 阶段第 14 节）。

### Q16 — 参考回答要点

- **模型**：先看许可证——讲义提到 SD3 / FLUX 有严格的许可要求，商用前必须逐条确认；需要高保真时选 SDXL 一档，追求最低延迟和最大社区生态时可选 SD 1.5。
- **调度器**：DPM-Solver++ 2M Karras 20–30 步是讲义给出的生产默认；若 2 秒仍不够，用 LCM-LoRA / Turbo 类蒸馏模型降到 1–4 步（讲义："LCM-LoRA when latency is under 1s"），代价是一定的质量和多样性。
- **精度与加速**：4090 级显卡用 fp16，A100 及更新用 bf16；显存紧张时用 int8 量化（如 `bitsandbytes`）；生产 API 可用 `diffusers + accelerate` 或 `optimum-nvidia` + TensorRT 编译；CFG 的两路预测合成一个 batch。
- **控制**：需要构图/姿态控制时加 ControlNet（canny、depth、pose），注意它会增加每步计算量。
- **安全与合规**：开启安全检查器或接入独立的内容审核；对提示词做过滤；记录生成日志；视需要加水印。
- **验证**：用固定提示集压测 P95 延迟与显存；用 FID / CLIP score + 人工评审做质量回归。
- **取舍总结**：步数、分辨率、模型大小、CFG 都直接换算成延迟，需要在质量回归集上找到"刚好满足 SLA"的组合。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 10 图像生成 — Diffusion Models](../../10-image-generation-diffusion/docs/zh.md)：DDPM 训练目标、DDIM 采样、时间嵌入——SD 就是搬进 latent 空间的 DDPM。
- [阶段 07 · 02 从零实现 Self-Attention](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：理解 cross-attention 的 Q/K/V。
- [阶段 04 · 18 开放词表视觉——CLIP](../../18-open-vocab-clip/docs/zh.md)：SD 1.x 的文本编码器来自 CLIP。
- [阶段 08 · 02 自编码器与 VAE](../../../08-generative-ai/02-autoencoders-vae/docs/zh.md)：latent 从哪里来。
- [阶段 11 · 08 LoRA 微调](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：LoRA 在大语言模型上的原理与实践。

### 本节被哪些后续内容用到
- [阶段 04 · 23 Diffusion Transformers 与 Rectified Flow](../../23-diffusion-transformers-rectified-flow/docs/zh.md)：SD3 / FLUX 一代把 U-Net 换成 DiT、把 DDPM 换成 rectified flow。
- [阶段 04 · 26 单目深度和几何估计](../../26-monocular-depth/docs/zh.md)：Marigold 把预训练 SD 2 的 U-Net 用作深度估计骨干。
- [阶段 04 · 28 世界模型与视频扩散](../../28-world-models-video-diffusion/docs/zh.md)：潜空间扩散扩展到视频。
- [阶段 08 · 07 潜空间扩散与 Stable Diffusion](../../../08-generative-ai/07-latent-diffusion-stable-diffusion/docs/zh.md)：更深入的 latent diffusion 讲解。
- [阶段 08 · 08 ControlNet、LoRA 与条件控制](../../../08-generative-ai/08-controlnet-lora-conditioning/docs/zh.md)：讲义提到的 ControlNet 与 LoRA 的展开。
- [阶段 08 · 09 Inpainting、Outpainting 与编辑](../../../08-generative-ai/09-inpainting-outpainting-editing/docs/zh.md)：img2img、inpainting 的更多编辑技巧。
- [阶段 08 · 14 生成模型评估：FID 与 CLIP Score](../../../08-generative-ai/14-evaluation-fid-clip-score/docs/zh.md)：如何评估文生图质量与提示词遵循度。

### 延伸关键词
`LDM (Rombach et al.)` · `AutoencoderKL` · `negative prompt` · `CFG rescale` · `DPM-Solver++ 2M Karras` · `LCM-LoRA / SDXL Turbo` · `DreamBooth / prior preservation` · `peft LoraConfig` · `ControlNet / T2I-Adapter` · `SDXL refiner` · `MMDiT`
