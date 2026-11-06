# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 11 节 Stable Diffusion——架构与 Fine-Tuning ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：标准库 `os`、`torch`（顶层导入，必需）；真正出图还需要 `diffusers`、`transformers`、`accelerate`、CUDA GPU，并需联网下载 SD 1.5 权重。缺任一项时脚本会打印说明并跳过真实推理

---

## 1. 这份代码在考察什么

本节讲义的定位是"Learn + Use"：不从零重建 Stable Diffusion，而是熟练使用 `diffusers` 这套生产 API。这份脚本相应地是一个**"能在任何机器上跑通的说明书"**：

1. **记住 SD 管线的关键数字**：各代模型的文本编码器、去噪器参数量、latent 形状、VAE 缩放系数、默认 CFG。
2. **建立 CFG 的直觉**：不同 `guidance_scale` 预期会看到什么现象（其中有一个标签与讲义不一致，见 3.3）。
3. **真实文生图调用的最小模板**：加载管线、换成 DPM-Solver++ 调度器、固定随机种子、25 步出图、保存。
4. **优雅降级**：没装 `diffusers` 或没有 GPU 时不崩溃，打印原因后继续。
5. **LoRA 训练的骨架**：把训练循环打印出来，和第 10 节的 DDPM 训练步对照。

> 一句话：**SD = 在 VAE latent 里跑的 DDPM + 文本 cross-attention + CFG + 快速调度器**；这份代码让你先把"有哪些零件、默认值是多少、怎么调用"记牢。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `has_diffusers()` | 函数 | 尝试 `import diffusers`，返回是否可用 | 可选依赖检测 |
| `describe_pipeline()` | 函数 | 打印文本编码器、参数量、latent 形状、缩放系数、默认 CFG | 管线组件与关键数字 |
| `cfg_sweep_demo()` | 函数 | 对 6 个 guidance 值打印预期效果 | Classifier-free guidance |
| `text_to_image_stub(prompt, seed)` | 函数 | 条件满足时用 SD 1.5 + DPM-Solver++ 真正出图，否则打印跳过原因 | 文生图、换调度器、可复现 |
| `lora_training_sketch()` | 函数 | 打印 LoRA 训练伪代码 | LoRA 微调 |
| `main()` | 演示入口 | 依次调用以上四个函数 | — |

调用关系是线性的：`main → describe_pipeline → cfg_sweep_demo → text_to_image_stub（内部调用 has_diffusers）→ lora_training_sketch`。

---

## 3. 逐段精讲

### 3.1 `has_diffusers`：探测可选依赖

```python
def has_diffusers():
    try:
        import diffusers  # noqa: F401
        return True
    except ImportError:
        return False
```

- **"试着导入"是检测可选依赖的标准写法**：导入成功返回 True，抛出 `ImportError` 就返回 False，不让整个脚本崩溃。
- 只捕获 `ImportError`，而不是笼统的 `Exception`：如果 `diffusers` 装了但内部出错，这类真正的问题会暴露出来。
- `# noqa: F401`：告诉 flake8 等 linter"这个导入虽然没被使用，但是故意的"（F401 是"导入未使用"的规则编号）。
- ⚠️ 文件顶部的 `import torch` 没有类似保护：没装 PyTorch 时脚本第一行就会失败，连说明文字都打印不出来。

### 3.2 `describe_pipeline`：管线的关键数字

```python
def describe_pipeline():
    print("[stable diffusion pipeline]")
    print("  text_encoder:   CLIP-L (SD 1.5) / CLIP-L+G (SDXL) / T5-XXL (SD3, FLUX)")
    print("  unet_params:    860M (SD 1.5) / 2.6B (SDXL) / 12B (FLUX)")
    print("  vae_latent:     4 x 64 x 64 for 512x512 input, 4 x 128 x 128 for 1024x1024")
    print("  vae_scale:      0.18215 (SD 1.5/2), 0.13025 (SDXL)")
    print("  default_cfg:    7.5")
```

逐行对应讲义：

| 行 | 含义 | 讲义出处 |
|----|------|---------|
| `text_encoder` | SD 1.x 用 CLIP 文本塔；SDXL 用 CLIP-L + CLIP-G 两个；SD3 / FLUX 引入 T5-XXL | Concept · The pipeline |
| `unet_params` | 去噪器参数量：约 860M / 2.6B / 12B，增长主要来自注意力层 | The U-Net architecture |
| `vae_latent` | VAE 空间下采样 8 倍、4 通道：512→64、1024→128 | Latent diffusion |
| `vae_scale` | 把 latent 方差缩放到约 1 的常数，不同 VAE 不同 | Key Terms · VAE scale factor |
| `default_cfg` | SD 默认 guidance scale 7.5 | Classifier-free guidance |

- **48 倍压缩**：`(3·512·512) / (4·64·64) = 786,432 / 16,384 = 48`；换成 1024 分辨率也是 48 倍（`3·8·8/4`），因为压缩比只取决于下采样倍数和通道数。
- ⚠️ 这一行是"速记"，有两处需要知道的简化：①FLUX（以及 SD3）的去噪器是 Transformer（DiT 类）而不是 U-Net，标签 `unet_params` 对它并不准确，讲义正文也说"the denoiser (U-Net or DiT)"；②SD3 和 FLUX 并非只用 T5-XXL，同时也使用 CLIP 文本编码器。面试时这些细节值得说准。

### 3.3 `cfg_sweep_demo`：CFG 的经验刻度

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

- 这 6 个值正是讲义练习 1 要你在真实管线上扫描的 `guidance_scale`。
- **链式条件表达式**：`A if c1 else B if c2 else C ...` 从左到右判断，第一个为真的条件生效，相当于一串 `if / elif / else`。外层括号允许它跨多行书写。
- 刻度含义（CFG 公式 `ε = ε_uncond + w·(ε_cond − ε_uncond)`）：
  - `w < 5`：提示词约束弱，画面更"自由"；
  - `5 ≤ w ≤ 8`：常用区间，SD 默认 7.5；
  - `8 < w ≤ 12`：提示词遵循度高，开始出现过饱和；
  - `w > 12`：明显伪影——沿条件方向外推太远，latent 偏离 VAE 能正常解码的区域。
- `f"{w:5.1f}"`：总宽 5、1 位小数、右对齐，所以 `1.0` 打印成 `"  1.0"`，让各行对齐。
- ⚠️ **与讲义不一致**：代码把 `w ≤ 1.0` 全部标成 "unconditional"。按讲义，`w = 0` 才是无条件生成，`w = 1` 是普通的条件生成（`ε = ε_cond`，没有额外放大）；`diffusers` 中 `guidance_scale ≤ 1` 也只是关闭 CFG、仍然使用文本条件。所以 `w = 1.0` 那一行的标签是错的，应改为类似 "plain conditional (no guidance)"（修正写法见测验 Q8）。

### 3.4 `text_to_image_stub`：真实调用的最小模板

```python
def text_to_image_stub(prompt, seed=42):
    print(f"\n[text_to_image] prompt={prompt!r} seed={seed}")
    if not has_diffusers():
        print("  diffusers not installed. `pip install diffusers transformers accelerate` to run.")
        return None
    if not torch.cuda.is_available():
        print("  CUDA not available; running SD on CPU is extremely slow. Skipping real call.")
        return None
    from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler
    pipe = StableDiffusionPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        torch_dtype=torch.float16,
    ).to("cuda")
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
    gen = torch.Generator("cuda").manual_seed(seed)
    out = pipe(prompt, guidance_scale=7.5, num_inference_steps=25, generator=gen).images[0]
    path = os.path.expanduser("~/sd_demo.png")
    out.save(path)
    print(f"  saved: {path}")
```

- **卫语句（guard clause）**：先检查前置条件，不满足就打印原因并提前 `return`，主逻辑不用嵌套在多层 `if` 里。
- `{prompt!r}`：`!r` 调用 `repr()`，字符串会带引号打印，空格、特殊字符一目了然。
- **函数内导入**：`from diffusers import ...` 放在检查之后，没有 `diffusers` 的机器根本不会执行这一行。
- `from_pretrained(..., torch_dtype=torch.float16)`：以半精度加载，显存减半、讲义说"no visible quality loss"；`.to("cuda")` 把整条管线（VAE、文本编码器、U-Net）搬上 GPU。
- **换调度器只需一行**：`DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)` 复用原调度器的配置（训练时的 β 调度、时间步数等），只换采样算法——调度器与 U-Net 权重解耦，不需要重训。讲义 Step 1 称"the default DPM-Solver++"，但 SD 1.5 模型仓库配置里的默认调度器是 PNDM（`PNDMScheduler`），并不是 DPM-Solver++；所以这里显式替换一次是必要的，不依赖仓库的默认设置。
- `torch.Generator("cuda").manual_seed(seed)`：固定初始噪声，同样的提示词 + 种子 + 参数得到同一张图，便于对比不同参数。
- `pipe(...)` 的三个关键参数：`guidance_scale=7.5`（CFG）、`num_inference_steps=25`（DPM-Solver++ 25 步约等于 DDIM 50 步）、`generator`（可复现）。返回对象的 `.images` 是 PIL 图像列表。
- `os.path.expanduser("~/sd_demo.png")`：把 `~` 展开为当前用户的主目录，保存到用户目录而不是当前工作目录。
- ⚠️ 模型仓库 ID `runwayml/stable-diffusion-v1-5` 与讲义一致；但该仓库后来已被原作者下架，现在若无本地缓存，可能需要改用社区维护的镜像（如 `stable-diffusion-v1-5/stable-diffusion-v1-5`）。运行前请先在 Hugging Face 上确认。

### 3.5 `lora_training_sketch`：LoRA 训练骨架

```python
def lora_training_sketch():
    print("\n[lora training pseudocode]")
    pseudo = """
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
"""
    print(pseudo)
```

- 用**三引号多行字符串**保存一段代码文本，再原样打印——它只是展示，不会被执行，所以里面的 `vae`、`unet` 等名字未定义也没关系。
- 与第 10 节 `train_step` 逐行对照：

| 第 10 节 DDPM | 本节 LoRA 训练 |
|--------------|---------------|
| `x0`（像素） | `latents = vae.encode(images)... * 0.18215`（latent，缩放到单位方差） |
| `q_sample(x0, t, noise)` | `scheduler.add_noise(latents, noise, t)` |
| `model(x_t, t)` | `unet(noisy_latents, t, text_emb)`（多了文本条件） |
| `F.mse_loss(pred, noise)` | 同样的 MSE |
| 更新全部参数 | 只更新注入的 LoRA 矩阵 |

- ⚠️ 作为伪代码它省略了不少东西，直接照搬会出错：缺 `optimizer.zero_grad()`；没有冻结 VAE / 文本编码器 / U-Net，也没有注入 LoRA；`tokenizer(...)` 返回字典而非张量；`unet(...)` 返回输出对象，需要 `encoder_hidden_states=` 传参并取 `.sample`。符合 `diffusers` API 的完整写法见测验 Q10。
- LoRA 的核心公式（讲义）：`W_q + α·(A @ B)`，`A: (d_in, r)`、`B: (r, d_out)`，r 常取 4–32。例如 `320→320` 的投影在 r=4 时只新增 2,560 个参数（原权重的 2.5%）。

### 3.6 `main()`

```python
def main():
    describe_pipeline()
    cfg_sweep_demo()
    text_to_image_stub("a dog riding a skateboard in tokyo, studio ghibli style")
    lora_training_sketch()
```

四个步骤互不依赖，`text_to_image_stub` 失败（返回 None）也不影响后面的打印。提示词与讲义 Step 1 相同。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用打印代替真实推理 | 任何机器都能跑，先建立概念 | 学不到真实的出图效果；有 GPU 时应跑完讲义 Step 1–5 |
| 可选依赖用 `try/import` 检测 | 缺包时优雅降级 | `torch` 本身没做同样的保护 |
| 无 GPU 时直接跳过 | SD 在 CPU 上极慢 | 可改用 `enable_model_cpu_offload` 或小模型做 CPU 演示 |
| 显式换成 DPM-Solver++ | 25 步得到 50 步 DDIM 的质量 | 不同调度器风格略有差异，应在评测集上对比 |
| fp16 + 固定种子 | 省显存、可复现 | 部分老显卡 fp16 有数值问题，可改 bf16 |
| LoRA 训练只给伪代码 | 聚焦结构 | 实际训练用 `diffusers` 的训练脚本或 `peft` |
| 关键数字写死在字符串里 | 方便记忆 | 会随新模型过时，也有简化（FLUX 不是 U-Net） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块文档字符串 | 文件开头的 `"""Stable Diffusion usage examples..."""` | 说明文件用途，可通过 `__doc__` 读取 |
| 默认参数 | `def text_to_image_stub(prompt, seed=42)` | 不传时使用默认值 |
| `try / except ImportError` | `has_diffusers()` | 只捕获导入失败，检测可选依赖 |
| 函数内导入 | `from diffusers import StableDiffusionPipeline, ...` | 用到时才导入，避免缺包时整个文件无法加载 |
| 卫语句 / 提前返回 | `if not has_diffusers(): ...; return None` | 不满足条件就尽早退出 |
| 链式条件表达式 | `"unconditional" if w <= 1.0 else ... if ... else ...` | 多分支的表达式写法，从左到右取第一个为真的分支 |
| f-string 宽度与精度 | `f"{w:5.1f}"` | 宽 5、1 位小数、右对齐 |
| f-string `!r` | `f"prompt={prompt!r}"` | 用 `repr()` 显示，字符串带引号 |
| 三引号多行字符串 | `pseudo = """ ... """` | 保留换行和缩进的原样文本 |
| 链式方法调用 | `torch.Generator("cuda").manual_seed(seed)`、`from_pretrained(...).to("cuda")` | 方法返回对象本身或新对象，可以连续调用 |
| 列表索引 | `pipe(...).images[0]` | 取出第一张图 |
| `os.path.expanduser` | `os.path.expanduser("~/sd_demo.png")` | 展开 `~` 为用户主目录 |
| `# noqa` 注释 | `import diffusers  # noqa: F401` | 让 linter 忽略某条规则 |
| `if __name__ == "__main__":` | 文件末尾 | 只有直接运行时才执行 `main()` |

---

## 6. 运行结果解读

当前环境没有安装 `torch`，脚本顶层的 `import torch` 会直接失败。为了看到脚本自身的输出，我在临时目录里复制了代码，并用一个只提供 `torch.cuda.is_available()`（返回 False）的**桩模块（stub）**代替 `torch` 运行了一次（没有安装任何包、没有修改源码）。由于 `diffusers` 也不存在，真实出图分支不会被执行，以下输出与"装了 torch、没装 diffusers"的机器完全一致：

```text
[stable diffusion pipeline]
  text_encoder:   CLIP-L (SD 1.5) / CLIP-L+G (SDXL) / T5-XXL (SD3, FLUX)
  unet_params:    860M (SD 1.5) / 2.6B (SDXL) / 12B (FLUX)
  vae_latent:     4 x 64 x 64 for 512x512 input, 4 x 128 x 128 for 1024x1024
  vae_scale:      0.18215 (SD 1.5/2), 0.13025 (SDXL)
  default_cfg:    7.5

[cfg sweep values to try on a real pipeline]
  w=  1.0  expected: unconditional
  w=  3.0  expected: creative but weak prompt adherence
  w=  5.0  expected: standard
  w=  7.5  expected: standard
  w= 10.0  expected: strong adherence, possible oversaturation
  w= 15.0  expected: heavy artefacts

[text_to_image] prompt='a dog riding a skateboard in tokyo, studio ghibli style' seed=42
  diffusers not installed. `pip install diffusers transformers accelerate` to run.

[lora training pseudocode]

for step, batch in enumerate(dataloader):
    images, prompts = batch
    ...
    optimizer.step()
```

逐段解读：

- **管线摘要**：五行就是本节要背下来的"数字表"。重点是 `4 x 64 x 64`（48 倍压缩）和 `0.18215`（训练与推理都必须用同一个缩放系数）。
- **CFG 刻度**：`w=5.0` 和 `w=7.5` 都落在 "standard"（`5 ≤ w ≤ 8`）。第一行 `w=1.0 → unconditional` 是错误标签（见 3.3）——这正好是一个"读输出时要带着讲义核对"的好例子。
- **文生图**：`prompt=` 后面带引号，是 `!r` 的效果；因为没有 `diffusers`，函数在第一个卫语句处返回。
- **有 diffusers 但没 GPU** 时会打印 `CUDA not available; ... Skipping real call.`；**两者都有**时会下载约数 GB 的权重，25 步后打印 `saved: /home/<用户>/sd_demo.png`。
- **伪代码**：原样打印的多行字符串，开头有一个空行，因为三引号后紧跟换行。

---

## 7. 动手改一改

1. 修正 `cfg_sweep_demo` 中 `w = 1.0` 的标签，并把 `0.0` 加入扫描列表（测验 Q8）。
2. 给顶层 `import torch` 也加上 `try/except`，让没有 PyTorch 的机器至少能打印前两段说明。
3. 有 GPU 时：用固定种子对 `guidance_scale ∈ [1, 3, 5, 7.5, 10, 15]` 各出一张图，拼成一行对比，找出开始出现伪影的值（讲义练习 1）。
4. 把调度器分别换成 `EulerAncestralDiscreteScheduler` 和 DDIM，在相同种子、相同步数下对比画面与耗时。
5. 仿照 `text_to_image_stub` 写一个 `img2img_stub`，对同一张图扫描 `strength ∈ [0.2, 0.4, 0.6, 0.8, 1.0]`（讲义练习 2）。
6. 把 `lora_training_sketch` 的伪代码改成符合 `diffusers` + `peft` API 的真实训练步（测验 Q10），在 10–20 张图上训练一个 LoRA（讲义练习 3）。

---

## 8. 常见坑

- **CFG 的 w=1 不是无条件**：`w = 0` 才是；`w = 1` 是普通条件生成。
- **缩放系数用错**：SD 1.5 用 0.18215、SDXL 用 0.13025；训练时乘、解码前除，任何一处不一致都会让结果发灰或炸裂。
- **调度器换了却以为要重训**：调度器与权重解耦，`from_config` 一行即可切换。
- **fuse 之后直接加载另一个 LoRA**：必须先 `unfuse_lora()`。
- **把伪代码当真代码**：缺 `zero_grad`、未冻结基座、未取 `.sample`，跑起来要么报错，要么在训练整个 U-Net。
- **模型仓库 ID 失效**：教程里的仓库可能已迁移，加载失败时先检查 Hugging Face 上的当前地址与许可证。
