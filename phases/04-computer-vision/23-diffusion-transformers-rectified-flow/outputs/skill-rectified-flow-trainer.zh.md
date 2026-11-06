---
name: skill-rectified-flow-trainer
description: Write a complete rectified-flow training loop with AdaLN DiT and Euler sampling
version: 1.0.0
phase: 4
lesson: 23
tags: [diffusion, rectified-flow, DiT, training]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="rectified-flow-trainer"></a>

# 整流流量训练器

生成一个干净、最小的训练循环，该循环可以在任何图像 tensor 数据集上成功训练具有修正流的小型 DiT。

<a id="when-to-use"></a>

## 何时使用

- 小规模重现 SD3 / FLUX 训练目标。
- 在相同数据上对修正流与 DDPM 进行基准测试。
- 为非标准领域（医疗、卫星）构建自定义整流流模型。

<a id="inputs"></a>

## 输入

- `model`：`nn.Module` 采用 `(x, t)` 并返回预测速度。
- `dataset`：模型域中干净图像的可迭代。
- `optimizer`：AdamW 与 `lr=1e-4`、`weight_decay=0.01`、`betas=(0.9, 0.99)`。
- `scheduler`：与 warmup 的余弦，默认 1000 warmup 步长。

<a id="training-step"></a>

## 训练步骤

```python
def rectified_flow_train_step(model, x0, optimizer, device):
    model.train()
    x0 = x0.to(device)
    n = x0.size(0)
    t = torch.rand(n, device=device)                     # uniform in [0, 1]
    epsilon = torch.randn_like(x0)
    x_t = (1 - t[:, None, None, None]) * x0 + t[:, None, None, None] * epsilon
    target_v = epsilon - x0                              # velocity target
    pred_v = model(x_t, t)
    loss = F.mse_loss(pred_v, target_v)
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()
    return loss.item()
```

<a id="sampling-euler"></a>

## Sampling（欧拉）

```python
@torch.no_grad()
def sample(model, shape, steps=20, device="cpu"):
    model.eval()
    x = torch.randn(shape, device=device)
    dt = 1.0 / steps
    t = torch.ones(shape[0], device=device)
    for _ in range(steps):
        v = model(x, t)
        x = x - dt * v
        t = t - dt
    return x
```

<a id="tips"></a>

## 温馨提示

- 使用`torch.rand`统一`t`； `t` 的 logit-normal 或 Sd3 样式加权 sampling 略有帮助，但不需要开始。
- 型号 weights 的 EMA 为标准做法；保持 `ema_model` 衰减为 0.9999。
- 条件模型的无分类器指导：训练期间有 10% 的概率用空/空 embedding 替换条件；在 inference 将 `v_uncond + w * (v_cond - v_uncond)` 与 `w` 混合大约 3-5。
- 对于LDM式训练（FLUX、SD3），整个循环在VAE latent space中运行；上面干净的`x0`实际上是`VAE.encode(image)`。
- 32x32 玩具数据集上的典型收敛：2000-5000 步。真实潜在 SD3 训练：数十万。

<a id="report"></a>

## 报告

```
[rectified flow training]
  steps:        <int>
  final loss:   <float>
  ema decay:    <float>
  vae?:         yes | no
  cfg dropout:  <fraction>

[sampling]
  default steps: 20
  schnell / turbo target: 4
  full quality reference: 50+ (for comparison only)
```

<a id="rules"></a>

## 规则

- 切勿在 RGB `uint8` 数据上使用图像空间速度目标来训练校正流；首先归一化为零均值，单位方差。
- 始终记录每个时间步长桶的训练损失；如果早期的时间步长（接近 0）比晚期的时间步长（接近 1）具有更高的损失，则速度参数化可能是错误的。
- 不要将整流流速目标与 DDPM 噪声目标混合在同一训练循环中；选择一个。
- 在Ampere+ GPUs上使用bfloat16训练；由于速度大小，float16 有时会在整流流中产生 NaN 梯度。
