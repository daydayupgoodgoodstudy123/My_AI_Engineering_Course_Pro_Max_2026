---
name: skill-cmer-monitor
description: Instrument a production VLM endpoint with Cross-Modal Error Rate monitoring, dashboards, and alerts
version: 1.0.0
phase: 4
lesson: 25
tags: [vlm, production, monitoring, hallucination]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="cmer-monitor"></a>

# CMER监视器

将跨模态 alignment 视为一流的生产 KPI。

<a id="when-to-use"></a>

## 何时使用

- 部署任何生成基于图像的文本的 VLM 端点。
- 调查幻觉反应的报告。
- 跟踪输入 distribution shift 是否会降低模型 grounding 的性能。

<a id="inputs"></a>

## 输入

- `vlm_output`：生成的文本。
- `text_confidence`：`[0, 1]`中softmax之后的每token的平均概率。计算为`exp(mean(log_probs))`。不传原始logits；原始 logits 是无界的，`conf_threshold` 假设有一个概率。
- `image_embedding`：图像的 CLIP 系列 embedding（DINOv3、SigLIP、CLIP）。
- `text_embedding`：生成文本的 CLIP 系列 embedding。
- 可选 `prompt_type`：分组标签（vqa / ocr / 字幕 / agent）。

<a id="per-request-computation"></a>

## 每个请求的计算

```python
import torch

def cmer_flag(image_emb, text_emb, text_conf, sim_thr=0.25, conf_thr=0.8):
    if image_emb.shape != text_emb.shape:
        raise ValueError(f"emb shape mismatch: {image_emb.shape} vs {text_emb.shape}")
    image_emb = image_emb / (image_emb.norm() + 1e-8)
    text_emb = text_emb / (text_emb.norm() + 1e-8)
    sim = float((image_emb * text_emb).sum())
    flagged = (text_conf > conf_thr) and (sim < sim_thr)
    return {"sim": sim, "flagged": flagged}
```

Embeddings 是来自独立 CLIP 系列 encoder 的一维 PyTorch tensors (`torch.float32`)。如果您使用 NumPy 数组，请将 `.norm()` 交换为 `np.linalg.norm(...)` 并相应地转换输出。

将 `sim`、`text_conf`、`flagged`、`prompt_type`、`timestamp`、`model_version`、`request_id` 存储到您的监控管道（普罗米修斯、DataDog、OpenTelemetry）。

<a id="aggregate-metric"></a>

## 聚合指标

```
CMER = (flagged requests in window) / (total requests in window)
```

每个端点、每个提示 _ 类型、每个模型版本的报告。

<a id="alert-thresholds"></a>

## 警报阈值

- 基线 CMER：建立超过 7 天的正常流量。
- 警告：1 小时内 CMER >= 1.5 倍基线。
- 严重：30 分钟内 CMER >= 2 倍基线或任何窗口 > 15% 绝对值。

<a id="dashboard-panels"></a>

## 仪表板

1. 随着时间的推移，CMER（5 分钟时段，7 天窗口）。
2. CMER按提示符_类型（堆叠条）。
3. 每小时 `sim` 的分布（柱状图）。
4. 最高的幻觉输出（每天抽取 20 个标记响应样本以供人工审核）。

<a id="actions-when-cmer-spikes"></a>

## CMER 峰值时的操作

1. 对标记的请求进行采样。
2. 验证模型版本没有因疏忽而更改。
3. 检查输入分布（新文件格式？新图像源？以不同方式压缩？）。
4. 将受影响的流量路由至人工审核，直至峰值解决。
5. 如果尖峰持续存在，则微调或更换模型；不要抑制警报。

<a id="rules"></a>

## 规则

- 切勿使用VLM自己的embeddings计算CMER；使用独立的 encoder（DINOv3、SigLIP 或 CLIP-L/14）。否则，您正在测量模型的自一致性，而不是 alignment。
- 始终记录原始 `sim` 值，而不仅仅是 `flagged` 位； distribution shifts 在标志率更改之前显示在下四分位数。
- 请勿在没有 CMER 监控的情况下运送 VLM 端点； hallucinations 是主要的生产故障模式，如果没有此指标，则保持沉默。
- 对于敏感领域（医疗、法律、金融），将`sim_threshold`提高到0.35或更高；标志条件是 `sim < sim_threshold`，因此较高的阈值会捕获更多可能未接地的输出 - 这是高风险使用的正确默认值。
