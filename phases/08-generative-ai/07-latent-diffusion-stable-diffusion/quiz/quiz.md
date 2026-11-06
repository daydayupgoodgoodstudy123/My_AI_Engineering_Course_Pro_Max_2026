# 测验 · 潜空间扩散（Latent Diffusion）与 Stable Diffusion（Latent Diffusion & Stable Diffusion）

> **阶段 08 · 生成式 AI · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两阶段训练 | 第一阶段训练 VAE（`E(x)→z`，`D(z)→x`）后冻结；第二阶段只在潜变量 `z` 上训练扩散模型，推理时先采样 `z₀` 再 `x = D(z₀)` |
| 2 | 为什么省算力 | 每个空间轴下采样 8 倍：512×512×3 → 64×64×4，U-Net 处理的空间位置少 64 倍；高频纹理交给解码器，扩散只负责语义结构 |
| 3 | VAE 的损失设计 | 重建（L1 + LPIPS 感知损失）+ 很小权重的 KL，常加对抗损失让解码更清晰；KL 小是因为不需要直接从 `z` 的先验里采样 |
| 4 | 损失函数不变 | 扩散损失与第 06 节 DDPM 完全相同（预测噪声的 MSE 或 flow matching），只是把数据域换成了 `z` |
| 5 | 文本条件 = 冻结文本编码器 + cross-attention | 每个 U-Net block 里 `Q = 图像特征，K = V = 文本 token`；文本只能通过这条路径影响图像 |
| 6 | Classifier-Free Guidance（CFG） | 训练时约 10% 概率把条件换成 null；推理时 `ε_cfg = (1+w)·ε_cond − w·ε_uncond`，`w` 越大越贴合条件、多样性越低 |
| 7 | VAE 缩放系数 | SD 1.x 编码后要乘 `scaling_factor ≈ 0.18215`（即除以约 5.4），让潜变量接近单位方差；忘了它扩散会在错误方差上训练 |
| 8 | 架构演进 | U-Net → DiT/MMDiT；文本编码器 CLIP → T5-XXL；潜通道 4 → 16（SD3、Flux） |
| 9 | 消费级显卡部署 | 分阶段加载（编码器 → DiT → VAE 依次进出显存）+ 4-bit 量化 + CPU offload，12B 的 Flux 也能挤进 8GB |

### 核心技能（能动手做到）

- [ ] 运行 `code/main.py`，能解释 CFG 扫描中每个 `w` 下两类样本均值的变化，以及为什么"同一套 DDPM 损失换到 `z` 上照样能用"
- [ ] 给定分辨率和 VAE 下采样倍数/通道数，手算潜变量形状与压缩比（如 1024² → 128×128×4）
- [ ] 手写 CFG 组合函数，并证明讲义的 `(1+w)·ε_c − w·ε_u` 与 diffusers 的 `guidance_scale` 写法等价（`s = 1 + w`）
- [ ] 能指出 `scaling_factor` 应该在编码后乘、解码前除，并说清楚忘记它的后果
- [ ] 能为 Flux-12B 做显存估算（参数量 × 每参数字节数），说出分阶段加载 / 4-bit / offload 各自省了什么、代价是什么
- [ ] 能按场景（窄领域微调、开源文生图、极速推理、图像编辑）选出合适的底座模型并给出理由

---

## 二、基础自测（选择题）

**Q1.** Latent Diffusion 相比像素空间扩散能大幅降低计算量，最根本的原因是：

- A. 潜空间扩散只需要更少的采样步数
- B. 扩散网络处理的张量空间尺寸大幅缩小（每轴 8 倍下采样），感知上不重要的高频细节交给 VAE 解码器
- C. VAE 编码器会把噪声提前去除，扩散网络只需要做一步预测
- D. 潜空间扩散用更小的 U-Net，所以每步 FLOPs 更低

**Q2.** 某 VAE 每个空间轴下采样 8 倍、潜变量 4 通道。输入 1024×1024 的 RGB 图像，潜变量形状是：

- A. 64×64×4
- B. 128×128×4
- C. 128×128×16
- D. 256×256×4

**Q3.** Stable Diffusion 第一阶段 VAE 的 KL 项权重通常设得很小，原因是：

- A. KL 项会让训练发散，必须尽量关掉
- B. 我们不需要直接从 `z` 的标准正态先验里采样，`z` 的分布由第二阶段的扩散模型来建模；KL 太强反而损害重建质量
- C. 小 KL 权重能让潜变量严格服从 N(0, I)，便于扩散
- D. KL 项只在推理时起作用，训练时可以忽略

**Q4.** 按讲义的 CFG 公式 `ε_cfg = (1+w)·ε_cond − w·ε_uncond`，当 `w = 0` 时：

- A. 等价于完全无条件生成，忽略类别/文本
- B. 等价于只用条件预测 `ε_cond`，不做额外的引导放大
- C. 模型不去噪，直接输出输入噪声
- D. 引导强度最大，样本最贴合条件

**Q5.** 在 Stable Diffusion 1.x 的 U-Net 中，文本提示词影响图像生成的主要方式是：

- A. 把文本 embedding 拼接到潜变量的通道维上，作为额外输入通道
- B. 在 cross-attention 中用文本 token 作 Query、图像特征作 Key/Value
- C. 在 cross-attention 中用图像特征作 Query、文本 token 作 Key 和 Value
- D. 先用文本 embedding 训练一个分类器，再用分类器梯度引导采样

**Q6.** 用 SD 1.x 的 VAE 训练自己的潜空间扩散模型时，忘了乘 `scaling_factor ≈ 0.18215`，最直接的后果是：

- A. 潜变量的空间分辨率变成原来的 5 倍
- B. 潜变量的标准差约为预期的 5 倍多，前向加噪公式假设的"信号 ≈ 单位方差"被破坏，模型在错误的方差尺度上训练
- C. 文本编码器的输出维度不匹配，直接报错
- D. 没有任何影响，因为 U-Net 有 GroupNorm 会自动归一化

**Q7.** 下列哪一项**不是**讲义总结的文生图架构演进趋势？

- A. 用 DiT（在潜变量 patch 上运行的 transformer）替换 U-Net
- B. 把文本编码器从 T5 换回 CLIP，以获得更好的提示词遵循能力
- C. 增加潜变量通道数（4 → 16），给细节留出更多余量
- D. 扩大文本编码器规模

**Q8.** 把 12B 参数的 Flux DiT 用 4-bit 量化加载，仅权重就大约占用：

- A. 1.5 GB
- B. 6 GB
- C. 12 GB
- D. 24 GB

---

## 三、动手 / 代码题

**Q9.** `main.py` 训练循环中有这样一行：

```python
use_c = NULL_CLASS if rng.random() < 0.1 else c
c_emb = one_hot(use_c, num_classes_inc_null)
```

(a) `inp = x_t + t_emb + c_emb` 拼起来的输入长度是多少？`W1` 的形状是什么？
(b) 如果把 `0.1` 改成 `0.0`（永远不丢弃标签），再用 `w = 3` 采样，会发生什么？为什么？

**Q10.** diffusers 等库通常用 `guidance_scale`（记作 `s`）写 CFG：`ε = ε_u + s·(ε_c − ε_u)`。请写一个函数 `cfg_diffusers(eps_c, eps_u, s)`，并用随机数验证它与 `main.py` 中的 `(1 + w) * eps_c[0] - w * eps_u[0]` 在 `s = 1 + w` 时完全相等。再回答：diffusers 里常见的 `guidance_scale = 7.5` 对应讲义里的 `w` 是多少？

**Q11.**（找 bug）`main.py` 用 `T = 40` 调用下面的调度：

```python
def make_schedule(T):
    betas = [1e-4 + (0.02 - 1e-4) * t / (T - 1) for t in range(T)]
    ...
```

而采样时从 `z = rng.gauss(0, 1)` 开始。请计算（或估算）`alpha_bars[T-1]`，指出训练与采样之间的不一致，并给出一种修正。

---

## 四、面试高频题

**Q12.**（基础必考）什么是 Latent Diffusion？为什么 Stable Diffusion 不直接在像素空间做扩散？两个阶段分别训练什么、推理时数据怎么流动？

**Q13.**（原理深挖）讲一讲 Classifier-Free Guidance：训练时要做什么改动？推理时怎么组合？为什么 `w` 太大会出现过饱和、"油腻"的图？它的推理成本是多少？

**Q14.**（原理深挖）文本是怎么进入 Stable Diffusion 的？SD3/Flux 的 MMDiT 与 SD 1.x 的 cross-attention 有什么区别？为什么新模型普遍改用 T5-XXL？

**Q15.**（工程实践）你只有一张 8GB 显存的消费级显卡，要跑 Flux.1-dev（12B）。请给出方案并做显存估算，说明每一步的代价。

**Q16.**（追问型）负向提示词（negative prompt）在实现上是怎么工作的？"空负向提示词"和"不传负向提示词"一定等价吗？

**Q17.**（场景设计）下列场景你分别选什么底座：①只有某垂直领域的成对数据、要尽快上线；②开源权重、开放领域文生图；③开源且推理最快；④以"图 + 文本指令"做编辑。另外，SDXL 上训练的 LoRA 能不能直接用到 SD3 上？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义的核心论点：像素空间里大部分 FLOPs 都花在"把感知上不重要的高频纹理推过网络"上。VAE 每轴下采样 8 倍后，U-Net 处理的空间位置是原来的 1/64，讲义给出"约 64 倍更少的 FLOPs"。A 错：步数与是否在潜空间无关（SD 仍然常用 30–50 步）；C 错：VAE 编码的是干净图像，不负责去噪；D 错：讲义强调的是"Same U-Net"，同一个网络、更小的输入。

### Q2 — 答案：B

1024 / 8 = 128，通道 4，所以是 128×128×4——这正是讲义表格中 SDXL 的潜变量形状。C 是 SD3/Flux 的 16 通道 VAE；A 是 512² 输入时 SD 1.x 的形状。

### Q3 — 答案：B

传统 VAE 需要强 KL 让 `z` 贴近 N(0, I)，因为生成时要直接从先验采样。而在 LDM 里，`z` 的分布由第二阶段的扩散模型来学，第一阶段只需"压得小、还原得好"。所以 KL 只用很小的权重做轻度正则，防止潜空间方差失控。C 错在"严格服从"——恰恰相反，权重小意味着不强求；这也是为什么还需要额外的 `scaling_factor` 把方差拉回单位尺度。

### Q4 — 答案：B

`w = 0` 时 `ε_cfg = ε_cond`，就是普通条件扩散，没有额外放大条件信号。讲义说它是"no guidance（full diversity）"，指的是不做引导、多样性最高，**不是**无条件生成（A）。完全无条件对应的是只用 `ε_uncond`（在 diffusers 写法里是 `s = 0`）。

### Q5 — 答案：C

讲义原话：每个 U-Net block 取 `[Q = image features, K = V = text tokens]`。Query 来自图像，意思是"每个图像位置去文本里找自己需要的信息"，输出与图像特征同形状，可以残差加回 `h`。B 把 Q/K/V 搞反了；A 是 inpainting 模型给 mask 和被遮图像用的方式（拼通道），不是文本注入方式；D 是 classifier guidance，正是 CFG 想替代的做法。

### Q6 — 答案：B

`scaling_factor` 的作用是把 VAE 潜变量缩放到大约单位方差（讲义 Key Terms："Divides latents by ~5.4"）。忘了乘，潜变量 std 约为 5 倍多。前向加噪 `z_t = √ᾱ·z₀ + √(1−ᾱ)·ε` 默认信号和噪声在同一量级，信号过大会让各时间步的信噪比整体偏离设计值，最后一步也去不干净信号，训练与采样都会出问题。D 错：GroupNorm 归一化的是网络内部特征，改变不了加噪公式里信号与噪声的相对比例。

### Q7 — 答案：B

趋势恰恰相反：讲义写"scale the text encoder (T5 beats CLIP for prompt adherence)"，SD3 和 Flux 都用了 T5-XXL。A、C、D 都是讲义列出的趋势。

### Q8 — 答案：B

4-bit = 0.5 字节/参数，`12B × 0.5 B = 6 GB`，与讲义 Production note 中的估算一致。D 是 bf16（2 字节/参数）的大小，C 是 8-bit 的大小。还要另外留出激活值的空间，所以 8GB 卡上必须配合分阶段加载。

### Q9 — 参考答案

(a) `x_t` 是长度 1 的列表 `[z_t]`，`t_emb` 长度 `t_dim = 8`，`c_emb` 长度 `num_classes_inc_null = 3`，Python 列表的 `+` 是**拼接**，所以 `inp` 长度为 `1 + 8 + 3 = 12`。`init_net(1, t_dim, num_classes_inc_null, hidden, rng)` 中 `W1 = randn_matrix(hidden, x_dim + t_dim + c_dim)`，即 **32×12**。

(b) 永远不丢弃标签，网络在训练中**从未见过** `one_hot(NULL_CLASS)`（即 `[0, 0, 1]`）。采样时 `eps_u` 来自一个没训练过的输入区域，是一个近似随机的函数值。CFG 计算 `4·ε_c − 3·ε_u`，相当于把一个无意义的向量放大 3 倍再减掉，结果会严重偏离真实噪声，样本均值、方差都可能跑偏甚至发散。

结论：**CFG 的前提是同一个网络同时学会了条件和无条件两种预测**，标签丢弃（condition dropout）就是为了用一套权重训练出"隐式的无条件模型"，不必另外训练一个网络。

### Q10 — 参考答案

```python
import random

def cfg_lesson(eps_c, eps_u, w):
    return (1 + w) * eps_c - w * eps_u

def cfg_diffusers(eps_c, eps_u, s):
    return eps_u + s * (eps_c - eps_u)

rng = random.Random(0)
for _ in range(1000):
    ec, eu, w = rng.gauss(0, 1), rng.gauss(0, 1), rng.uniform(0, 15)
    assert abs(cfg_lesson(ec, eu, w) - cfg_diffusers(ec, eu, 1 + w)) < 1e-9
print("equivalent")
```

推导：`ε_u + s·(ε_c − ε_u) = s·ε_c − (s−1)·ε_u`，令 `s = 1 + w` 就得到 `(1+w)·ε_c − w·ε_u`。所以 diffusers 的 `guidance_scale = 7.5` 对应讲义的 `w = 6.5`；diffusers 中 `s = 1` 才是"不引导"，对应讲义的 `w = 0`。

面试中经常有人把两种约定混用。讲义 Pitfalls 中的"`w > 10` 过饱和、甜区 3–7"按讲义的 `w` 来理解，换成 `s` 大约要加 1。

### Q11 — 参考答案

直接算：

```python
T = 40
betas = [1e-4 + (0.02 - 1e-4) * t / (T - 1) for t in range(T)]
ab = 1.0
for b in betas:
    ab *= 1 - b
print(ab)   # ≈ 0.667
```

`alpha_bars[39] ≈ 0.667`，所以训练时最后一个时间步的 `z_t = 0.817·z₀ + 0.577·ε`，**信号仍然占主导**。这组 β（1e-4 → 0.02）是 DDPM 原论文为 `T = 1000` 设计的，T 缩到 40 后累计加的噪声远远不够。

不一致：训练时网络在 `t = 39` 看到的是"均值约 ±0.82、标准差约 0.6"的输入，而采样从 `N(0, 1)` 起步——起点分布与训练分布不同（终端信噪比不为 0）。这会让样本均值整体偏向 0，例如实际运行中 `w=0` 时 class 0 的均值是 −1.68，而真实数据均值是 −2。

修正（任选其一）：
- 按 `1000 / T` 的比例放大 β，或者直接把 β 上限调大。把调度改成 `1e-3 → 0.2` 后 `ᾱ_T ≈ 0.013`，同样随机种子下重跑，`w` 从 0 增到 7 时 class 1 的均值从 +2.06 单调升到 +2.82，正好对应讲义练习 1 说的"引导强了，类均值被推出真实均值之外"；
- 改用 cosine 调度，或用 rescale 方法强制终端 SNR = 0；
- 增大 `T`。

加分点：真实的 SD 也有类似的"终端 SNR 不为 0"问题，后续工作会把调度重新缩放到 zero terminal SNR。

### Q12 — 参考回答要点

- **定义**：先训练一个 VAE（first stage）把图像压到低维潜空间并冻结，再在潜空间里训练扩散模型（second stage）。
- **动机**：512² 像素扩散的张量是 `[B,3,512,512]`，讲义估算单步约 100 GFLOPS、50 步约 5 TFLOPS/张。大部分算力花在高频纹理上，而这些纹理可以由有损 VAE 解码器负责。
- **数据流**：
  - 训练：`x → E(x) → z（× scaling_factor）→ 加噪得到 z_t → U-Net/DiT 预测 ε → MSE`；
  - 推理：`z_T ~ N(0,I) → 逐步去噪 → z₀ → ÷ scaling_factor → D(z₀) → x`；
  - 文本经冻结的文本编码器后通过 cross-attention 注入。
- **关键点**：扩散损失与第 06 节完全相同，"只是换了数据域"。
- **加分点**：两阶段解耦，同一个 VAE 可以服务多代扩散模型；但"潜空间不通用"——SDXL、SD3、Flux 的 VAE 不同，LoRA 不能混用。
- **常见误区**：以为 VAE 在推理时负责去噪；以为潜空间扩散步数更少。

### Q13 — 参考回答要点

- **训练改动**：以约 10% 的概率把条件（类别/文本）换成 null token，让同一个网络同时学会 `ε(z_t, c)` 和 `ε(z_t, ∅)`。
- **推理**：每步算两次，`ε_cfg = (1+w)·ε_c − w·ε_u`，即沿着"条件方向 `ε_c − ε_u`"外推。
- **直觉**：`ε_c − ε_u` 是"条件带来的那部分信号"，放大它就让样本更像"这个条件下最典型的样子"。Ho & Salimans 的推导中，它相当于隐式地用了一个分类器梯度 `∇log p(c|z_t)`，所以叫 classifier-free。
- **`w` 过大的问题**：外推越过数据流形，预测出的噪声幅度异常，表现为颜色过饱和、对比度过高、"油腻"、多样性坍缩。讲义建议 `w` 在 3–7。
- **成本**：每步两次前向，通常把条件/无条件拼成 batch=2 并行算，延迟接近不变、算力翻倍。Turbo/Lightning/schnell 等蒸馏模型把引导"蒸"进了权重，所以用 CFG=0（skill 文件建议 turbo/LCM 用 0）。
- **加分点**：能说出 diffusers 的 `guidance_scale` 与讲义 `w` 差 1。

### Q14 — 参考回答要点

- **SD 1.x**：冻结的 CLIP-L 文本编码器输出 77 个 token 的 embedding；U-Net 各 block 内做 `h = h + CrossAttention(Q=h, K=text, V=text)`。文本只影响图像，图像不反过来影响文本表示。
- **MMDiT（SD3/Flux）**：讲义定义是"text and image streams with joint attention"——文本和图像各走一条流，在 attention 中联合计算，信息双向流动。
- **为什么用 T5**：讲义说"T5 beats CLIP for prompt adherence"。CLIP 文本塔是用对比学习训练的，偏重整体语义匹配，且只有 77 个 token；T5-XXL 是大型语言模型的编码器，对长句、组合关系、数量、空间关系、文字渲染理解得更好。
- **工程坑**：SD3 需要 T5-XXL 且 ≥128 token，退化为只用 CLIP 会明显损失提示词遵循（讲义 Pitfalls），要检查是否真的启用了 T5。
- **常见误区**：认为文本是通过"拼接到输入通道"进入的。

### Q15 — 参考回答要点

讲义给出的三件套：

1. **分阶段加载**：T5-XXL、CLIP-L、12B MMDiT、VAE 不需要同时在显存里。先编码提示词，**删除**编码器 → 加载 DiT 去噪 → **删除** DiT → 加载 VAE 解码。8GB 卡一次只放得下一个阶段。
2. **4-bit 量化（bitsandbytes）**：`BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)`，作用在 T5 和 DiT 上。按讲义的估算：T5 约 10 GB → 约 1.25 GB，DiT `12B × 0.5 B ≈ 6 GB`，再加上激活值。讲义称文生图任务上质量损失几乎不可察觉。
3. **CPU offload**：`pipe.enable_model_cpu_offload()` 在前向推进时自动在 CPU 与 GPU 之间换模块，约增加 10–20% 延迟，但能跑起来。

- **取舍**：牺牲延迟和一点点质量换取能运行；生产环境应在 H100 上用 TP=2/4，而不是极限量化。
- **加分点**：提示词 embedding 可以缓存，同一提示词多次生成时不必重新加载 T5；激活显存随分辨率平方增长，降分辨率也能省显存。

### Q16 — 参考回答要点

- **机制**：负向提示词的 embedding **替代** null embedding，用来计算 `ε_uncond`。于是 CFG 变成"从负向提示词的方向往正向提示词的方向外推"，主动远离负向描述的内容（如 low quality、错误的解剖结构）。
- **空 vs 不传**：讲义 Pitfalls 指出，空负向提示词会变成 null token，填了内容的负向提示词变成 `ε_uncond`，"These are not the same"；有些管线在未传入时会静默使用 null embedding。工程上要明确指定，并在复现实验时记录用的是哪一种。
- **注意**：蒸馏模型 CFG = 0 时根本不计算 `ε_uncond`，负向提示词无效。
- **加分点**：负向提示词不能"删除"已经强烈出现在正向提示词里的概念，只是改变外推方向；过长的负向提示词也会影响构图。

### Q17 — 参考回答要点

按讲义 Use It 表：
1. 窄领域、有成对数据 → **SDXL 微调（LoRA / 全量）**，生态成熟、上线最快；
2. 开放领域、开源权重 → **Flux.1-dev（12B）或 SD3.5-Large**（注意 Flux.1-dev 的许可限制商用）；
3. 最快推理、开源 → **Flux.1-schnell（1–4 步，Apache）或 SDXL-Lightning**；
4. 图 + 文本编辑 → **Flux.1-Kontext**，原生接受图像和文本作为输入。

LoRA 跨底座：**不能**。讲义 Pitfalls："A LoRA trained on SDXL latents will not work on SD3"，因为 VAE（潜空间）、骨干结构、权重形状都不同；diffusers 0.30+ 会拒绝加载不匹配的权重。

- **加分点**：选型还要考虑许可证、显存、是否需要 ControlNet/IP-Adapter 生态（SDXL 生态最完整）。

---

## 六、关联知识点

### 前置知识
- [阶段 08 · 02 自动编码器和 VAE](../../02-autoencoders-vae/docs/zh.md)：第一阶段的编码器/解码器、KL 项与重建损失。
- [阶段 08 · 06 从头开始的 DDPM](../../06-diffusion-ddpm-from-scratch/docs/zh.md)：本节代码直接沿用其加噪调度、噪声预测损失和反向采样。
- [阶段 07 · 09 Vision Transformers](../../../07-transformers-deep-dive/09-vision-transformers/docs/zh.md)：理解 DiT 中"潜变量切 patch 送进 transformer"。
- [阶段 07 · 02 自注意力从零实现](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：cross-attention 的 Q/K/V 机制。

### 本节被哪些后续内容用到
- [阶段 08 · 08 ControlNet、LoRA 与条件控制](../../08-controlnet-lora-conditioning/docs/zh.md)：在冻结的 SD 骨干上加结构控制和低秩适配。
- [阶段 08 · 09 局部重绘、扩图与图像编辑](../../09-inpainting-outpainting-editing/docs/zh.md)：在潜空间里做 mask 混合、SDEdit 等编辑操作。
- [阶段 08 · 10 视频生成](../../10-video-generation/docs/zh.md)：把潜空间扩散扩展到时空潜变量。
- [阶段 08 · 13 Flow Matching 与 Rectified Flows](../../13-flow-matching-rectified-flows/docs/zh.md)：SD3/Flux 采用的训练目标。
- [阶段 08 · 14 评估：FID、CLIP 分数、人类偏好](../../14-evaluation-fid-clip-score/docs/zh.md)：评估 CFG 对质量与多样性的影响。
- [阶段 04 · 11 Stable Diffusion](../../../04-computer-vision/11-stable-diffusion/docs/zh.md)、[阶段 04 · 23 Diffusion Transformer 与 Rectified Flow](../../../04-computer-vision/23-diffusion-transformers-rectified-flow/docs/zh.md)：从视觉方向再看一遍同一套架构。
- [阶段 10 · 11 量化](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：Production note 中 4-bit 量化的原理。

### 延伸关键词
`LDM` · `VAE scaling_factor` · `LPIPS` · `Classifier-Free Guidance` · `DiT / MMDiT` · `T5-XXL` · `zero terminal SNR` · `SDXL refiner` · `Turbo / Lightning 蒸馏` · `bitsandbytes 4-bit` · `CPU offload`
