---
name: skill-noise-schedule-designer
description: Produce a linear, cosine, or sigmoid beta schedule given T and target corruption level, plus SNR plot
version: 1.0.0
phase: 4
lesson: 10
tags: [computer-vision, diffusion, noise-schedule, training]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="noise-schedule-designer"></a>

# 噪音表设计师

Beta 时间表控制每个扩散步骤保留多少信号。糟糕的时间表会限制每个下游决策的训练效率和样本质量。

<a id="when-to-use"></a>

## 何时使用

- 开始新的扩散训练并选择 T 和 beta。
- 调试一个diffusion model产生模糊的样本（计划过于激进）或无法学习结构（计划过于温和）。
- 比较报告不同时间表的论文的设计。

<a id="inputs"></a>

## 输入

- `T`：时间步数，通常为 100-1000。
- `type`：线性 | 余弦 | sigmoid.
- `target_alpha_bar_final`：保持在 t=T 时的信号分数，默认 0.001（99.9% 已损坏）。
- 可选的 `image_resolution` — 较大的图像受益于损坏速度较慢的计划（余弦或移位计划）。

<a id="schedule-formulas"></a>

## 附表公式

<a id="linear"></a>

### 线性
```
beta_t = beta_start + (beta_end - beta_start) * (t - 1) / (T - 1)
```
默认：beta_start=1e-4，beta_end=0.02（DDPM论文）。

<a id="cosine-nichol--dhariwal-2021"></a>

### 余弦（Nichol 和 Dhariwal，2021）
```
alpha_bar_t = cos^2((t/T + s) / (1 + s) * pi/2)
beta_t = 1 - alpha_bar_t / alpha_bar_{t-1}
```
s = 0.008。信号保持时间更长；低步数时效果更好。

<a id="sigmoid"></a>

### Sigmoid
```
alpha_bar_t = 1 / (1 + exp(k * (t/T - 0.5)))
```
k = 6 至 12。良好的中间立场；某些 SDXL 变体使用。

<a id="steps"></a>

## 步骤

1. 计算每个公式的贝塔值。
2. 预计算 `alphas`、`alphas_cumprod`、`sqrt_alphas_cumprod`、`sqrt_one_minus_alphas_cumprod`。
3. 计算SNR_t = alpha_bar_t / (1 - alpha_bar_t);生成随时间变化的 SNR 摘要。
4. 验证`alphas_cumprod[T-1]`是否在`target_alpha_bar_final`的10%以内；否则调整 beta_end（线性）、s（余弦）或 k (sigmoid) 并重试。
5. 报告三checkpoints：
   - `t=T*0.25` — 早期腐败
   - `t=T*0.5` — 中途
   - `t=T*0.75` — 接近最终版本

<a id="report"></a>

## 报告

```
[schedule]
  type:   <name>
  T:      <int>
  beta_start: <float>   beta_end: <float>

[signal retention]
  t=0.25T:  alpha_bar=<X>  SNR=<X>
  t=0.5T:   alpha_bar=<X>  SNR=<X>
  t=0.75T:  alpha_bar=<X>  SNR=<X>
  t=T:      alpha_bar=<X>  SNR=<X>

[warnings]
  - <if alpha_bar collapses before 0.75T>
  - <if beta_end produces NaN in log-SNR>
```

<a id="rules"></a>

## 规则

- 切勿使用任何 `alpha_bar_t <= 0` 发出时间表；将值限制在 1e-5 以下并发出警告。
- 余弦是低步数 sampling（< 30 步）的默认建议。
- 线性是 `quality_target == research` 的默认设置 — DDPM 基线以线性计划报告。
- 当 `image_resolution > 256` 时，建议改变时间表（Chen，2023）以在高分辨率下保留更多信号。
