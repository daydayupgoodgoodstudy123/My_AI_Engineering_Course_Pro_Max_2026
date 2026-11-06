# 测验 · 局部重绘（Inpainting）、扩图（Outpainting）与图像编辑（Inpainting, Outpainting & Image Editing）

> **阶段 08 · 生成式 AI · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三类编辑任务 | Inpainting：重绘 mask 内、保留 mask 外；Outpainting：重绘画布外（mask 反过来）；Image editing：整图重生成但保持语义/结构（SDEdit、InstructPix2Pix） |
| 2 | 朴素做法（mask 重注入） | 每个采样步把未遮挡区域替换成"按当前噪声水平加噪的原图"，只让模型补 mask 内部；能用，但边界容易出现接缝 |
| 3 | 专用 inpainting 模型 | U-Net 输入从 4 通道变成 9 通道：`噪声潜变量(4) + VAE 编码的原图(4) + mask(1)`，训练时随机遮挡，模型能"看到"周围内容 |
| 4 | SDEdit | 把原图加噪到中间时刻 `t`，再用新提示词从 `t` 去噪到 0；`t/T` 越大越自由、越不像原图，无需重训 |
| 5 | InstructPix2Pix | 在 `(输入图, 指令, 输出图)` 三元组上微调；推理时有图像、文本两个 CFG 系数 |
| 6 | RePaint | 用普通无条件扩散模型，在反向过程中周期性"跳回更吵的状态"再重新去噪，减少接缝，适合没有专用 inpaint 模型的情况 |
| 7 | 常见坑 | 接缝（mask 膨胀 8–16 px）、mask 泄漏、小 mask 配高 CFG 会过饱和、SDEdit 的保真度断崖、提示词要描述整张图 |
| 8 | 生产管线 | SAM 出 mask → 扩散模型 inpaint；编辑是延迟敏感型任务（目标 5 秒内往返）；Flux-Kontext 用单次前向直接处理"原图 + 指令" |

### 核心技能（能动手做到）

- [ ] 运行 `code/main.py`，解释为什么被补全的维度会和被固定的维度"同号"
- [ ] 能说清 `inpaint` 里"先把未遮挡维度替换成加噪原图、最后再还原成原值"这两步分别为什么必要
- [ ] 扫描被遮挡维度的比例（1/5 → 5/5），量化补全结果与上下文的一致率，找到"退化为无条件生成"的点
- [ ] 在玩具代码上实现 SDEdit（从 `t₀` 开始反向），并验证 `t₀` 越大越偏离原样本、越接近数据流形
- [ ] 能描述 9 通道 inpaint 模型的输入构造和训练方式
- [ ] 能为"去掉背景里的招牌""换天空""扩画布""修手"等任务选出 mask 方式、模型和关键参数

---

## 二、基础自测（选择题）

**Q1.** 朴素的 inpainting 做法中，每个采样步把未遮挡区域替换成什么？

- A. 原始干净图像（不加噪）
- B. 原图按**当前时间步**的噪声水平前向加噪后的版本
- C. 全零
- D. 模型上一步对该区域的预测

**Q2.** Stable Diffusion 的专用 inpainting U-Net 有 9 个输入通道，它们是：

- A. RGB 原图（3）+ 噪声（3）+ mask（3）
- B. 噪声潜变量（4）+ VAE 编码的原图（4）+ mask（1）
- C. 噪声潜变量（4）+ 文本 embedding（4）+ 时间步（1）
- D. 噪声潜变量（4）+ ControlNet 特征（4）+ mask（1）

**Q3.** 用 SDEdit 把一张照片改成油画风格，同时希望**保留原图的大致构图**，按讲义的经验值，起始噪声水平 `t/T` 最合适的是：

- A. 0.0
- B. 约 0.3：几乎不变，只有细微风格变化
- C. 约 0.6：中等编辑，保留粗粒度结构
- D. 约 0.95：基本从噪声重新生成

**Q4.** 关于 InstructPix2Pix，下列说法正确的是：

- A. 不需要任何训练，直接修改采样过程
- B. 在 `(输入图, 指令, 输出图)` 三元组上微调，推理时有图像和文本两个引导系数
- C. 必须提供 mask 才能编辑
- D. 只能做全局风格迁移，不能添加物体

**Q5.** RePaint 相对朴素 mask 重注入的主要改进是：

- A. 训练一个 9 通道的专用模型
- B. 在反向过程中周期性地跳回更吵的时刻再重新去噪，让 mask 内外更好地协调，减少接缝
- C. 用 SAM 生成更精确的 mask
- D. 把 CFG 提高到 10 以上

**Q6.** 想把照片里椅子上的空位补上一只猫，提示词写哪个更好？

- A. `a cat`
- B. `cat, high quality, 8k`
- C. `A cat sitting on a chair`（描述编辑后的**整张图**）
- D. 留空，让模型自己补

**Q7.** 关于 outpainting，下列说法**错误**的是：

- A. 它本质上是把 mask 反过来的 inpainting：遮住新增画布，保留原图
- B. 训练目标与 inpainting 相同
- C. 原图在新画布中占比越小越好，给模型最大的发挥空间
- D. 可以用 SDXL 的 outpaint 模式或 Flux-Fill 配合 outpaint mask 实现

**Q8.** 用朴素方法 inpaint 后边界出现明显接缝，讲义建议的修复是：

- A. 把 mask 收缩几个像素
- B. 把 mask 膨胀 8–16 像素，或者换用专用的 inpainting 模型
- C. 提高 CFG
- D. 减少采样步数

---

## 三、动手 / 代码题

**Q9.** 阅读 `inpaint` 的核心循环：

```python
    x = [rng.gauss(0, 1) for _ in range(d)]
    for t in range(T - 1, -1, -1):
        a_bar = alpha_bars[t]
        for i in range(d):
            if not mask[i]:
                x[i] = math.sqrt(a_bar) * clean[i] + math.sqrt(1 - a_bar) * rng.gauss(0, 1)
        t_emb = sin_embed(t, T, t_dim)
        eps_hat, _ = forward(x, t_emb, net)
        # ... 标准 DDPM 反向一步，得到新的 x
    for i in range(d):
        if not mask[i]:
            x[i] = clean[i]
    return x
```

(a) 为什么未遮挡维度要写成 `√ᾱ_t·clean + √(1−ᾱ_t)·ε`，而不是直接写 `x[i] = clean[i]`？
(b) 循环结束后为什么还要再把未遮挡维度设回 `clean[i]`？
(c) 被遮挡维度从来没有被直接赋值成与 `clean` 相关的值，它们是怎么"知道"应该和上下文同号的？

**Q10.**（讲义练习 1）写一段实验代码：训练好网络后，分别遮挡最后 `k = 1…5` 个维度，每种情况跑 200 次 `inpaint`，统计"被补全维度的符号与真实簇符号一致"的比例。先预测趋势，再说明 `k = 5` 时结果应该是多少、为什么。

**Q11.** 复用 `main.py` 的网络和调度，实现一个 SDEdit 函数 `sdedit(net, alphas, alpha_bars, T, t_dim, d, source, t0, rng)`：把 `source` 加噪到 `t0`，再从 `t0` 反向去噪到 0。用一个"不在数据流形上"的源样本 `[1, 1, -1, -1, 1]`（正负混杂）测试 `t0 ∈ {5, 20, 39}`，预测结果与源样本的距离、以及结果"五维同号"的比例如何变化。

---

## 四、面试高频题

**Q12.**（基础必考）讲讲扩散模型做 inpainting 的几种方法：朴素 mask 重注入、专用 9 通道模型、RePaint。各自的原理和优缺点是什么？

**Q13.**（原理深挖）SDEdit 为什么"加噪再去噪"就能实现编辑？它和 img2img 的 `strength` 参数是什么关系？`t` 怎么选？什么是"保真度断崖"？

**Q14.**（原理深挖）InstructPix2Pix 是怎么训练的？推理时两个 CFG 系数分别控制什么？它和 SDEdit 相比适合什么场景？

**Q15.**（场景设计）客户发来一张完美的商品图，背景里有一块碍眼的招牌，要求删掉招牌，其他像素保持完全一致。另外还要把这张方图扩成 16:9 横幅。请设计完整方案。

**Q16.**（工程实践）编辑类产品要求 5 秒内往返。请拆解一次"点选物体 → 重绘"的延迟构成，并给出优化手段。

**Q17.**（追问型）为什么"小 mask + 高 CFG"容易得到一块过饱和的补丁？为什么朴素方法会有接缝？分别怎么修？

---

## 五、参考答案与解析

### Q1 — 答案：B

在时刻 `t`，模型期望整个输入都处在同一噪声水平 `x_t` 上。所以未遮挡区域要用前向公式 `√ᾱ_t·x₀ + √(1−ᾱ_t)·ε` 加噪到当前水平（讲义 Step 3 的 `inpaint_step` 正是这样写的）。A 的问题是噪声水平不一致：一半干净、一半很吵，输入就不在训练分布上（见 Q9）。D 等于不使用原图信息，就成了无条件生成。

### Q2 — 答案：B

`concat([noisy_latent(4), encoded_image(4), mask(1)])`。原图先经过 VAE 编码（被遮挡部分抹掉），mask 下采样到潜空间分辨率后作为 1 个通道。训练时随机遮挡，让模型学会"根据看得见的周边补全被遮住的部分"。SD-Inpaint、SDXL-Inpaint、Flux-Fill 都用这种（或类似的）输入。

### Q3 — 答案：C

讲义经验值：`0.3` 几乎与原图一致，只有细微风格变化；`0.6` 中等编辑，保留粗粒度结构；`0.9` 几乎从噪声生成。改成"油画"属于比较明显的风格变化，又要保留构图，选 0.6 左右。还要注意 Pitfalls 中的"保真度断崖"：0.5 → 0.6 之间可能突然丢失主体身份，需要扫描并保存检查点。

### Q4 — 答案：B

讲义："Fine-tune a diffusion model on `(input_image, instruction, output_image)` triples……Two CFG scales: image scale and text scale."它需要训练（A 错），不需要 mask（C 错），也能做"add a dragon"这类局部添加（D 错）。

### Q5 — 答案：B

RePaint 使用标准的无条件模型、无需重训，在反向过程中"resample——偶尔跳回更吵的状态再重新生成"。每次跳回再去噪，mask 内外的信息就多一轮相互协调的机会，从而减少接缝。A 是专用 inpaint 模型的做法。

### Q6 — 答案：C

讲义 Pitfalls："The prompt should describe the *whole* image, not just the new content."提示词作用于整个去噪过程，只写 `a cat` 会让模型试图在 mask 区域塞进一张"以猫为主体的整图"，与周围的透视、尺度、光照不协调。

### Q7 — 答案：C

原图是 outpainting 唯一的锚点，占比太小时模型缺少上下文，容易"幻觉"出不协调的内容。配套 skill 文件甚至规定：原图占新画布不足 30% 时拒绝 outpaint。A、B、D 都是讲义原话。

### Q8 — 答案：B

讲义：接缝是因为朴素方法中"信息没有跨越 mask 边界流动"，修复方法是把 mask 膨胀 8–16 像素（给模型一圈过渡区，让它重绘边缘），或者直接用专用 inpaint 模型。收缩 mask（A）会让接缝更明显；提高 CFG（C）反而容易得到过饱和的补丁。

### Q9 — 参考答案

(a) 网络在时刻 `t` 只在"整体处于噪声水平 `t`"的输入上训练过。如果未遮挡维度直接是干净值，而被遮挡维度还在噪声里，输入就是一种从没见过的混合状态，`eps_hat` 的预测会失准，反向公式还会把那些"干净值"当成含噪值继续去噪、把它们推偏。用 `q(x_t | x₀)` 采样，可以保证整个输入在统计上与训练时一致。

(b) 反向步对所有维度都做了更新（包括未遮挡维度），最后一步 `t = 0` 输出的是模型"去噪后的版本"，不一定精确等于原值。inpainting 的承诺是**未遮挡区域与原图逐像素一致**，所以最后要硬性还原。

(c) 信息通过**网络的联合预测**传过去。网络输入的是完整的 5 维 `x`，它在训练中学到了"5 个维度同属一个簇、同号"的相关性。未遮挡维度带着加噪后的原图信息进入网络，网络对被遮挡维度的噪声预测 `eps_hat[3..4]` 会受到前三维的影响，于是被补全的维度被一步步拉向与上下文一致的簇。这正对应真实图像中"模型根据周边内容补全纹理"的机制。

### Q10 — 参考答案

```python
import random
from main import (make_schedule, init_net, train, sample_data, inpaint)

rng = random.Random(5)
T, t_dim, hidden, d = 40, 8, 32, 5
alphas, alpha_bars = make_schedule(T)
net = init_net(d, t_dim, hidden, rng)
train(net, alpha_bars, T, steps=5000, lr=0.01, t_dim=t_dim, d=d, rng=rng)

for k in range(1, d + 1):
    agree = tot = 0
    for _ in range(200):
        clean, cluster = sample_data(rng, d)
        mask = [i >= d - k for i in range(d)]      # 遮挡最后 k 维
        out = inpaint(net, alphas, alpha_bars, T, t_dim, d, clean, mask, rng)
        s = -1.0 if cluster == 0 else 1.0
        for i in range(d):
            if mask[i]:
                tot += 1
                agree += out[i] * s > 0
    print(f"masked {k}/5: sign agreement {agree / tot:.3f}")
```

实测输出（同一种子）：

```text
masked 1/5: sign agreement 0.960
masked 2/5: sign agreement 0.980
masked 3/5: sign agreement 0.920
masked 4/5: sign agreement 0.740
masked 5/5: sign agreement 0.452
```

解读：
- 上下文越多（遮挡越少），一致率越高，k = 1–3 时都在 92% 以上；
- k = 4 时只剩 1 个维度做上下文，而且它每步都被重新加噪，信息很弱，一致率降到 74%；
- **k = 5 时完全没有上下文，就是无条件生成**，补出来的簇与 `clean` 的簇无关，一致率理论上约 50%（实测 0.452，是 200 次采样的随机波动）。所以讲义问"什么时候等同于无条件生成"，答案是上下文为 0（k = 5）；k = 4 已经明显退化。

### Q11 — 参考答案

```python
import math

def reverse_step(net, x, t, alphas, alpha_bars, T, t_dim, d, rng):
    t_emb = sin_embed(t, T, t_dim)
    eps_hat, _ = forward(x, t_emb, net)
    beta_t = 1 - alphas[t]
    mean = [(x[i] - beta_t / math.sqrt(1 - alpha_bars[t]) * eps_hat[i]) / math.sqrt(alphas[t])
            for i in range(d)]
    if t > 0:
        return [mean[i] + math.sqrt(beta_t) * rng.gauss(0, 1) for i in range(d)]
    return mean

def sdedit(net, alphas, alpha_bars, T, t_dim, d, source, t0, rng):
    a_bar = alpha_bars[t0]
    x = [math.sqrt(a_bar) * s + math.sqrt(1 - a_bar) * rng.gauss(0, 1) for s in source]
    for t in range(t0, -1, -1):          # 只走 t0 → 0 这一段
        x = reverse_step(net, x, t, alphas, alpha_bars, T, t_dim, d, rng)
    return x
```

用源样本 `[1, 1, -1, -1, 1]` 各跑 100 次，实测：

| `t0` | `t0/T` | 与源样本的平均平方距离 | 五维同号（落在数据流形上）的比例 |
|------|--------|---------------------|-------------------------------|
| 5 | 0.12 | 0.25 | 0.00 |
| 20 | 0.50 | 2.97 | 0.34 |
| 39 | 0.97 | 6.62 | 0.91 |

这正是 SDEdit 的**保真度–真实度权衡**：`t0` 小，几乎原样返回（保真高），但样本仍然"不像真数据"；`t0` 大，结果被拉回数据流形（真实度高），却离原样本很远。真实图像中，"源图像"可能是一张手绘草图（不在照片流形上），SDEdit 就是用这个机制把它"照片化"的。注意本代码用的 `T = 40` 调度有 `ᾱ_T ≈ 0.667`，所以即使 `t0 = 39` 也保留了一部分源信息。

### Q12 — 参考回答要点

| 方法 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| 朴素 mask 重注入 | 每步把未遮挡区替换为 `q(x_t|x₀)`，只让模型生成 mask 内 | 任何文生图模型都能直接用，无需训练 | 模型"看不见"上下文的真实内容（只看到每步重新加噪的版本），边界容易出现接缝、风格不协调 |
| 专用 9 通道模型 | 输入拼上 VAE 编码的被遮原图和 mask，随机遮挡训练 | 上下文作为干净的条件信号输入，补全最连贯；生产默认 | 需要额外训练；每个底座都要有对应的 inpaint 版本 |
| RePaint | 无条件模型 + 反向过程中周期性跳回更吵的时刻重新去噪 | 无需重训，接缝更少 | 采样步数成倍增加，速度慢 |

- **加分点**：outpainting 只是 mask 反过来；mask 膨胀与羽化；diffusers 中对应 `StableDiffusionInpaintPipeline`、`FluxFillPipeline`。
- **常见误区**：以为朴素方法的"最后还原未遮挡区"就能消除接缝——接缝问题出在 mask 内部生成时缺少信息交互。

### Q13 — 参考回答要点

- **原理**：前向加噪先抹掉高频细节，再抹掉粗结构。加噪到中间时刻 `t`，高频细节（纹理、笔触）已被噪声淹没，而低频结构（构图、大色块）还保留着；从 `t` 开始用新提示词反向去噪，模型在保留下来的粗结构上按新条件重新画细节。整个过程无需重训。
- **与 img2img 的关系**：img2img 的 `strength` 本质上就是 `t/T`。`strength = 0.3` 只跑最后 30% 的步数，`1.0` 等价于文生图。
- **选 `t`**：讲义给出 0.3 / 0.6 / 0.9 三档；配套 skill 建议"保留主体"时 strength 用 0.3–0.5，完全重生成用 0.8–1.0，并对"`t/T > 0.7` 且要求保留主体"的请求发出警告。
- **保真度断崖**：主体身份可能在很窄的区间内突然丢失（讲义例子是 0.5 → 0.6），因此要扫描多个 `t` 并保存检查点，不能只试一个值。
- **加分点**：能用玩具实验说明这个权衡（Q11 的表格）。

### Q14 — 参考回答要点

- **训练**：在 `(输入图, 编辑指令, 输出图)` 三元组上微调扩散模型，输入图作为额外的图像条件（与潜变量拼接）。论文中这些三元组是合成的：先用大语言模型生成指令和编辑后的描述，再用文生图模型配合 Prompt-to-Prompt 生成成对图像。
- **两个 CFG**：
  - 图像引导 `s_I`：越大越忠实于输入图；
  - 文本引导 `s_T`：越大越严格执行指令。
  - 两者独立可调，论文的组合方式大致是 `ε̂ = ε(∅,∅) + s_I·(ε(I,∅) − ε(∅,∅)) + s_T·(ε(I,T) − ε(I,∅))`。
- **与 SDEdit 对比**：SDEdit 用"新的描述"+ 噪声水平控制编辑，必须写出编辑后的整图描述，而且只有一个"保真度旋钮"；InstructPix2Pix 直接接受"把它变成日落"这样的**指令**，结构保持得更好。讲义 Use It 表中"Make it sunset"对应 InstructPix2Pix 或 Flux-Kontext。
- **加分点**：Flux-Kontext 是更新的方案，单次前向就能处理"原图 + 指令"，不需要 mask 和噪声扫描。

### Q15 — 参考回答要点

**删除招牌（inpainting）**：
1. **mask**：用 SAM 点选或框选招牌，或者用 Grounded-SAM 输入文本短语 "sign" 自动分割；mask 膨胀 8–16 px 并羽化。
2. **模型**：小目标移除用 SD-Inpaint 或 Flux-Fill（讲义 Use It："Remove object, small mask"）。
3. **提示词**：描述删除后的整张图（如"商品放在木桌上，背景是干净的砖墙"），负向提示词写 text、logo、sign。
4. **参数**：mask 小，CFG 要调低（避免过饱和补丁）；固定 seed，保存 mask 以便复现。
5. **像素一致**：最后把 mask 外区域用原图逐像素覆盖回去，避免 VAE 编解码带来的轻微色偏。

**扩成 16:9（outpainting）**：
1. 把原图放到 16:9 画布中央，左右新增区域作为 mask（与原图有少量重叠并羽化）；原图占比远超 30%，锚点足够。
2. 用 SDXL outpaint 模式或 Flux-Fill；提示词描述整幅横幅画面。

**质检**：边界接缝、光照方向、透视线是否连续；商品本身是否被改动。

### Q16 — 参考回答要点

- **延迟构成**（讲义数字）：SAM mask 约 200 ms（SAM-H）+ VAE 编解码合计约 500 ms + 30 步 SDXL-Inpaint 1024² 在 L4 上 3–4 s。这是 batch=1、低并发、"首结果延迟"敏感的场景，而不是吞吐敏感的场景。
- **优化手段**：
  - SAM-H 换 SAM-ViT-B（约 40 ms，质量损失很小）；单图编辑不要用 SAM 2（视频版有时序开销）；
  - 迭代编辑时复用上一轮的潜变量，省掉一次 VAE 编码；
  - 减少步数或换蒸馏模型；
  - 直接用 Flux-Kontext 这类"单次前向处理原图 + 指令"的模型，"把多阶段合并"（讲义：H100 上约 1.5 s 完成一次编辑）。
- **加分点**：区分 TTFT 敏感与吞吐敏感的服务形态；把 mask 生成与 VAE 编码并行化；预热模型、避免冷启动。

### Q17 — 参考回答要点

- **小 mask + 高 CFG**：CFG 会沿条件方向外推、放大颜色和对比度。大图上这些效应被大面积内容"稀释"，小 mask 上则集中在一小块，与周围的低饱和上下文形成反差，显得像一块"贴上去"的过饱和补丁。修复：小编辑降低 CFG（讲义 Pitfalls），配合 mask 羽化。
- **接缝**：朴素方法中，mask 外每步都被强制替换为"原图加噪"，mask 内是模型生成的内容，模型生成 mask 内时看不到 mask 外的真实干净内容，边界两侧的纹理和光照协调不足（讲义："gradient info doesn't flow across the mask"）。修复：mask 膨胀 8–16 px 给出过渡带、RePaint 式重采样、换专用 9 通道 inpaint 模型。
- **另一个相关坑**：mask 泄漏——如果条件图未遮挡区域本身质量差或有噪声，会污染 mask 内的生成，可以先轻度去噪或模糊。

---

## 六、关联知识点

### 前置知识
- [阶段 08 · 06 从头开始的 DDPM](../../06-diffusion-ddpm-from-scratch/docs/zh.md)：本节代码的网络、调度、反向采样全部沿用 DDPM；inpaint 只是改了每一步的输入。
- [阶段 08 · 07 潜空间扩散与 Stable Diffusion](../../07-latent-diffusion-stable-diffusion/docs/zh.md)：9 通道 inpaint 模型的"潜变量 + VAE 编码图"都来自 LDM。
- [阶段 08 · 08 ControlNet、LoRA 与条件控制](../../08-controlnet-lora-conditioning/docs/zh.md)：修手修脸时配合 ControlNet-Openpose。

### 本节被哪些后续内容用到
- [阶段 08 · 10 视频生成](../../10-video-generation/docs/zh.md)：视频编辑中同样会用到 mask 与加噪再去噪的思路。
- [阶段 08 · 14 评估：FID、CLIP 分数、人类偏好](../../14-evaluation-fid-clip-score/docs/zh.md)：评估编辑的保真度与提示词遵循度。
- [阶段 04 · 07 语义分割 U-Net](../../../04-computer-vision/07-semantic-segmentation-unet/docs/zh.md)、[阶段 04 · 24 SAM 3 开放词汇分割](../../../04-computer-vision/24-sam3-open-vocab-segmentation/docs/zh.md)：mask 的来源。
- [阶段 08 · 04 条件 GAN 与 Pix2Pix](../../04-conditional-gans-pix2pix/docs/zh.md)：图像到图像翻译的 GAN 前身，可与 InstructPix2Pix 对比。

### 延伸关键词
`mask 重注入` · `9-channel inpaint U-Net` · `Flux-Fill` · `SDEdit / img2img strength` · `InstructPix2Pix` · `RePaint resampling` · `Prompt-to-Prompt` · `mask dilation / feather` · `SAM / SAM 2 / Grounded-SAM` · `Flux-Kontext`
