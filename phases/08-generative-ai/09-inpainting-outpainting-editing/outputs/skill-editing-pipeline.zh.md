---
name: editing-pipeline
description: Plan an image-editing pipeline from source + edit description to a ready-to-ship output.
version: 1.0.0
phase: 8
lesson: 09
tags: [inpaint, outpaint, edit, sam]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定源图像、目标编辑（删除 X、用 Z 替换 Y、扩展画布、重新设计区域、更改季节/一天中的时间）和质量栏（草稿/作品集/打印），输出：

1. 掩码策略。显式画笔蒙版、SAM 2 单击/框 prompt、文本短语上的 Grounded-SAM 或 MBG（用于背景去除）。一句话理由。
2. 基础模型+模式。 SD-Inpaint / SDXL-Inpaint / Flux-Fill / Flux-Kontext 用于指令编辑，或 SDEdit 噪声级别 (0.3 / 0.6 / 0.9)（如果没有遮罩）。
3. Prompt 脚手架。描述编辑后的整个图像，而不仅仅是新内容。包括负prompt。
4. CFG+力量+羽毛。遮罩羽毛 8-16 px； CFG ~5-7 用于 SDXL-inpaint，3-4 用于 Flux。完全再生时强度为 0.8-1.0，保存时强度为 0.3-0.5。
5. Guardrails。 NSFW / deepfake / 商标检测钩子，换脸策略门，可逆性（保存掩码+种子）。

未经明确的政策检查，拒绝对可识别的公众人物进行身份编辑。拒绝在没有至少 30% 的原始画布作为锚点的情况下覆盖图像（上下文太少会使模型产生幻觉）。将 t/T > 0.7 和保真度目标“保留主题”的任何 SDEdit 运行标记为可能不匹配。
