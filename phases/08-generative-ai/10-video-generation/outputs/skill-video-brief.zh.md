---
name: video-brief
description: Translate a video brief into a model + prompt + shot plan for a 2026 video generator.
version: 1.0.0
phase: 8
lesson: 10
tags: [video, diffusion, sora, veo, kling]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定视频简介（时长、宽高比、风格、主题、摄像机计划、音频需求、保真度条、预算），输出：

1. 模型+托管。 Sora、Veo 3、Kling 2.1、Runway Gen-3、Pika 2.0、CogVideoX、HunyuanVideo、WAN 2.2 或 Mochi-1。与持续时间/质量/许可证相关的一句话原因。
2. Prompt 脚手架。 (a) 摄像机语言（建立、跟踪、移动、起重机、手持），(b) 主题 + 动作，(c) 灯光 + 风格，(d) 负 prompt 或风格切换。索拉的目标是 50-150 tokens，跑道的目标是 20-60。
3. 拍摄计划。单剪辑与拼接多镜头、关键帧或第一帧锚点、每个镜头的 I2V 与 T2V。
4. 种子+再现性。每镜头种子、版本引脚、工具存储库。
5. 质量检查清单。逐帧消除闪烁、身份一致性、物理违规、水印合规性。
6. 音频。 Veo 3 中的本机，或者附加的（ElevenLabs、Suno 或许可的 Stem + lip-sync pass）。

拒绝承诺在免费套餐上以 1080p 进行 > 10 秒的连续运动（Pika / Kling / Runway 上限为 10 秒；较长的运行需要缝合）。拒绝在未发布的情况下生成真人的肖像。标记任何暗示 2026 年实时 4K 生成的简报 - 目前最好的是在托管端点上每 6 秒剪辑以 1080p 生成约 30 秒。
