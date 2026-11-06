---
name: skill-vit-patch-and-pos-embed-inspector
description: Verify a ViT's patch embedding and positional embedding shapes match the model's expected sequence length
version: 1.0.0
phase: 4
lesson: 14
tags: [vision-transformer, debugging, pytorch]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


<a id="vit-patch-and-positional-embedding-inspector"></a>

# ViT Patch 和位置 Embedding 检查员

最常见的 ViT 移植错误：将在 224x224 下预训练的 checkpoint 加载到配置为 384x384 的模型中（反之亦然）。位置 embedding 的序列长度错误，模型会默默地产生垃圾。

<a id="when-to-use"></a>

## 何时使用

- Fine-tuning 以非默认分辨率预训练的 ViT。
- 审计ViT-B/16和ViT-B/32之间的weight端口失败的原因；检查器将标记 patch 大小不匹配，以便调用者知道交换架构而不是强制端口。
- 调试 ViT，加载没有错误，但训练效果很差。

<a id="inputs"></a>

## 输入

- `model`：实例化的ViT `nn.Module`。
- `expected_image_size`：该模型将在生产中看到高x宽。
- `patch_size`：预期 patch 大小。

<a id="steps"></a>

## 步骤

1. 在模型内找到 patch embedding 转换。报告其`kernel_size`、`stride`、`in_channels`、`out_channels`。
2. 计算 patches 的预期数量。对于方形图像：`(image_size / patch_size)^2`。对于矩形：`(H / patch_size) * (W / patch_size)`。需要`H % patch_size == 0`和`W % patch_size == 0`；否则标记并拒绝。
3. 找到学习到的位置 embedding。报告其形状 `(1, N, dim)`。
4. 将 `N` 与 `num_patches + 1`（带 CLS）或 `num_patches`（不带 CLS）进行比较。不匹配意味着 checkpoint 以不同的分辨率或 patch 大小进行预训练。
5. 检查 patch 转换的 `out_channels` 是否等于位置 embedding 的 `dim`。
6. 如果模型应该为新分辨率插值 embeddings，请验证插值实用程序是否存在（大多数 `timm` ViTs 通过 `resize_pos_embed` 自动执行此操作）。

<a id="report"></a>

## 报告

```
[vit-inspector]
  image_size:         HxW
  patch_size:         <int>
  num_patches (computed): <int>
  patch_conv:         k=<int>  s=<int>  in=<int>  out=<int>
  pos_embed shape:    (1, N, dim)
  has CLS token:      yes | no
  pos_embed N:        <int>    expected: <int>
  verdict:            ok | mismatch

[if mismatch]
  action:  reinitialise pos_embed for new sequence length
  tool:    timm.models.vision_transformer.resize_pos_embed
```

<a id="rules"></a>

## 规则

- 切勿在没有警告的情况下默默地插入；展示动作，以便用户知道预训练的位置结构可能已经发生变化。
- 如果 patch_size 不匹配，则拒绝推荐插值 - 交换到正确的架构。
- 不要尝试将模型固定到位；报告和建议。
