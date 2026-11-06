---
name: skill-dcgan-scaffold
description: Write a complete DCGAN scaffold from z_dim, image_size, and num_channels, including training loop and sample saver
version: 1.0.0
phase: 4
lesson: 9
tags: [computer-vision, gan, dcgan, scaffolding]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="dcgan-scaffold"></a>

# DCGAN支架

给定三个 parameters，发出一个可运行的 DCGAN 项目框架，其架构大小适合目标图像分辨率。

<a id="when-to-use"></a>

## 何时使用

- 在小数据集上开始新的生成实验。
- 通过一个最小的示例来教授 DCGAN 基础知识。
- 原型制作条件 GANs（标签注入发生在同一支架中）。

<a id="inputs"></a>

## 输入

- `image_size`：32、64、128之一（必须是2的幂）。
- `num_channels`：1（灰度）或3（RGB）。
- `z_dim`：通常为 64 或 128。
- `with_spectral_norm`：是 | 不；默认是。

<a id="architecture-sizing"></a>

## 架构规模

G 中的转置转换块和 D 中的跨步转换块的数量取决于 `image_size`：

| image_size | G块 | D块 |
|------------|----------|----------|
| 32         | 4        | 4        |
| 64         | 5        | 5        |
| 128        | 6        | 6        |

每个附加块都会使空间维度加倍 (G) 或减半 (D)。 Feature 计数从 32 开始，并以 `feat_base * 2^block_index` 缩放。

<a id="output-files"></a>

## 输出文件

- `model.py` — 生成器 + 鉴别器类
- `train.py` — 训练循环、损失、优化器设置
- `sample.py` — 示例网格保护程序
- `config.json` — hyperparameters
- `README.md` — 10 行快速入门

<a id="report"></a>

## 报告

```
[scaffold]
  image_size:       <int>
  num_channels:     <int>
  z_dim:            <int>
  spectral_norm:    yes | no

[arch]
  G blocks:         <N>, channels: [list]
  D blocks:         <N>, channels: [list]
  G params (est):   <N>
  D params (est):   <N>

[training defaults]
  optimizer:   Adam(lr=2e-4, betas=(0.5, 0.999))
  batch_size:  64
  epochs:      50
  sample_every: 1 epoch

[files written]
  - model.py
  - train.py
  - sample.py
  - config.json
  - README.md
```

<a id="rules"></a>

## 规则

- 训练期间始终在 G 的输出上使用 `nn.Tanh()`，并将数据缩放为 [-1、1]。
- 始终在 D 中使用 `LeakyReLU(0.2)`。
- 当 `with_spectral_norm == yes` 时，用 `spectral_norm()` 包装 D 中的每个 conv，并从 D 中删除 BatchNorm。将 BatchNorm 保留在 G 中。
- 切勿为 image_size > 128 发出支架 — DCGAN 在此之上会变得不稳定；将用户指向 StyleGAN 或 diffusion model。
