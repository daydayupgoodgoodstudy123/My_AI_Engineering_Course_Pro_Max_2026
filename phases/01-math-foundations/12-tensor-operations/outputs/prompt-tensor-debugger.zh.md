---
name: prompt-tensor-debugger
description: Step-by-step debugging prompt for tensor shape errors in deep learning code
phase: 1
lesson: 12
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


我的深度学习代码中有 tensor 形状错误。帮我解决一下。

**错误消息：** [将错误粘贴到此处]

**我的tensor形状：**
- [名称]：[形状]
- [名称]：[形状]

**我想做的操作：** [描述一下]

---

调试时，请严格遵循以下流程：

**第一步：识别操作类型。**
什么操作产生了错误？将其映射到以下之一：
- 矩阵乘法/线性层（内部尺寸必须匹配）
- 广播（从右对齐，每个暗淡必须等于或1）
- 连接（除猫维度外所有维度都匹配）
- 卷积（期望特定的等级和通道位置）
- 重塑（必须保留全部元素）

**第2步：写出形状合约。**
对于确定的操作，明确地写出预期的形状：
```
matmul(A, B): A is (..., m, k), B is (..., k, n) -> (..., m, n)
broadcast(A, B): align right, each pair must be (equal) or (one is 1)
cat([A, B], dim=d): all dims match except dim d
Linear(in_f, out_f): input last dim must equal in_f
Conv2d(in_c, out_c, k): input must be (B, in_c, H, W)
```

**第3步：查找不匹配项。**
将实际形状与合同进行比较。确定违反规则的确切维度。

**第 4 步：选择最小修复。**
从此表中选择：

| 症状 | 修复 |
|---|---|
| 缺少批次尺寸 | `.unsqueeze(0)` |
| 缺少通道尺寸 | `.unsqueeze(1)` |
| 额外尺寸 - 1 维 | `.squeeze(dim)` |
| matmul 的内部变暗错误 | `.transpose(-1, -2)` 或检查 weight 形状 |
| 需要 NHWC 提供的 NCHW | `.permute(0, 3, 1, 2)` |
| 需要 NCHW 提供的 NHWC | `.permute(0, 2, 3, 1)` |
| 展平线性空间暗淡 | `.flatten(1)` 或 `.reshape(B, -1)` |
| 分头：(B,T,D) 至 (B,H,T,D/H) | `.reshape(B, T, H, D//H).transpose(1, 2)` |
| 合并头：(B,H,T,D/H) 至 (B,T,D) | `.transpose(1, 2).reshape(B, T, H*(D//H))` |
| 与 .view() 不连续的 tensor | `.contiguous().view(...)` 或使用 `.reshape(...)` |

**第 5 步：验证修复。**
显示每一步生成的形状。确认所有元素在任何重塑过程中均得到保留。确认现在满足操作的形状合同。

**第6步：检查静默错误。**
即使形状匹配，也要验证：
- 广播是沿着预期的轴发生的（并非偶然）
- 归约是在正确的维度上求和
- 批次维度（dim 0）在整个 forward pass 中保留
- 当维度顺序很重要时，使用转置 + 重塑（不仅仅是重塑）

将您的回复格式设置为：
```
OPERATION: [what operation failed]
EXPECTED: [shape contract]
ACTUAL: [what shapes were provided]
MISMATCH: [which dimension, why]
FIX: [exact code]
RESULT: [shapes after fix]
```
