---
name: skill-lora-training-setup
description: Write a full LoRA training config for a custom dataset, including captions, rank, batch size, and learning rate
version: 1.0.0
phase: 4
lesson: 11
tags: [computer-vision, stable-diffusion, lora, fine-tuning]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="lora-training-setup"></a>

# LoRA 训练设置

将微调意图的描述转换为具体的训练配置，准备传递给 `diffusers` 或 `kohya_ss`。

<a id="when-to-use"></a>

## 何时使用

- 针对主题（人、物体、角色）、风格（艺术家、品牌）或概念（姿势、灯光）训练 LoRA。
- 使用更多数据扩展现有 LoRA。
- 调试 LoRA 运行，其输出与训练图像欠拟合或过拟合。

<a id="inputs"></a>

## 输入

- `purpose`：主题 | 风格 | 概念
- `num_images`：有多少训练图像可用
- `base_model`：SD 1.5 | SDXL | SD3 | 通量
- `gpu_vram_gb`: 8 | 12 | 16 | 24 | 48+
- `caption_source`：手册 | BLIP2 生成 | 数据集原生

<a id="rank-picker"></a>

## 排名选择器

| 目的 | 排名 | 阿尔法 |
|---------|------|-------|
| 主题 | 8-16 | 等级 |
| 风格 | 16-32 | 排名 * 2 |
| 概念 | 32-64 | 等级 |

更高的排名 = 更多的容量，小数据集上的 overfitting 风险更大。 Alpha 缩放 LoRA 的效果强度； `alpha == rank` 是安全默认值。样式是已记录的例外：`alpha == rank * 2` 提供了更强大的样式推动，但代价是将样式烘焙得太硬的风险更大 - 仅当主题保真度不是目标时才使用。

<a id="training-step-target"></a>

## 训练步骤目标

- `subject` 具有 5-20 张图像：500-1500 步。
- `style` 30-100 张图像：1500-4000 步。
- `concept` 具有 100 多个图像：4000-10000 个步骤。

超调后果自负——记住了训练图像的 LoRA 无法概括。

<a id="learning-rate"></a>

## Learning rate

- 文本 encoder LoRA：`1e-4` 用于 SD 1.5，`5e-5` 用于 SDXL。
- U-Net LoRA：`1e-4` 适用于 SD 1.5，`1e-4` 适用于 SDXL。
- FLUX/SD3：`5e-5`为transformer，文字encoders通常被冻结。
- 当`num_images < 15`（受试者）或训练超过3000步时将LR减半；小型数据集和长时间运行都受益于更温和的更新。

<a id="scheduler"></a>

## 调度程序

- `cosine_with_warmup`（默认）：warmup 在前 5-10% 的步骤中，然后是余弦衰减。当`steps >= 1000`时使用；衰减尾部给出了更清晰的最终样本。
- `constant`：仅用于非常短的运行（`steps < 500`）或恢复之前的 LoRA 时，您希望保留当前学习的 features 而不重新退火。

<a id="caption-format"></a>

## 字幕格式

- 主题：在每个标题前添加一个唯一的触发器 token（“myperson”）。保持触发器 token 很少见，这样它就不会覆盖现有概念。避免真实的单词和俗名。
- 样式：在每个标题末尾附加一个唯一的样式标签（“...in mystyle style”）。将标签本身视为罕见触发器 token — `mystyle`，而不是 `impressionism`，后者已经映射到真实概念。
- 概念：描述每个标题中的概念；无触发 token。概念本身（例如“低角度拍摄”）是锚点。

<a id="output-config"></a>

## 输出配置

```yaml
model:
  base: <base_model HF id>
  precision: fp16 | bf16

lora:
  rank: <int>
  alpha: <int>
  targets: unet.cross_attention  # and/or unet.to_q, to_k, to_v, to_out

training:
  steps:          <int>
  batch_size:     <int, tuned to gpu_vram_gb>
  grad_accum:     <int, usually 1 on >=16 GB, 4 on <=12 GB>
  learning_rate:  <float>
  optimizer:      AdamW8bit | AdamW
  scheduler:      cosine_with_warmup | constant
  warmup_steps:   <int>
  save_every:     <int>

data:
  images_dir:     <path>
  caption_source: <manual | BLIP2 | native>
  trigger_token:   <string if purpose==subject>
  resolution:      <512 for SD 1.5, 1024 for SDXL>
  aspect_ratio_bucketing: true
  augmentation:
    flip:          true
    color_jitter:  false

validation:
  prompts:
    - "<trigger> ...test prompt..."
    - "<trigger> in a different scene"
  every_steps: 250
```

<a id="report"></a>

## 报告

```
[lora setup]
  purpose:   <subject|style|concept>
  base:      <model>
  rank:      <int>
  steps:     <int>
  batch:     <int>   grad_accum: <int>
  lr:        <float>
  vram est.: <float> GB
```

<a id="rules"></a>

## 规则

- 绝不推荐`rank > 64`；上面的LoRA就变成了迷你微调，失去了“适配器”的性质。
- 对于 `num_images < 5`，强烈警告 - 每次 1-3 个图像上的身份 LoRAs 都会过度拟合。
- 对于 `gpu_vram_gb < 12`，需要 AdamW8bit 和 gradient 检查点。
- 如果是 `base_model == FLUX` 和 `gpu_vram_gb < 24`，则路由到 `schnell` 变体，并注意训练速度较慢。
- 切勿跳过验证 prompts；没有样本网格的 LoRA 是无法评估的。
