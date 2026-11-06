---
name: video-qa
description: Build a video understanding pipeline with scene segmentation, multi-vector indexing, temporal grounding, and timestamped citations.
version: 1.0.0
phase: 19
lesson: 12
tags: [capstone, video, multimodal, gemini, qwen-vl, molmo, transnet, qdrant]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


建立接收管道和查询系统, 以(开始、结束)时间戳加上框架预览回答自然语言问题。

构建计划 :

1. 最热门的视频(YouTube URLs 或 MP4) ; 需要的话, 降为 720 p 。
2. 与 TransNetV2 或 PyScene 检测的场景分割; 发射 `[{scene_id, start_ms, end_ms, keyframe_path}]`.
3. 使用 Whiseper-V3-turbo (快速耳语)的自动记录器制作字级时间戳; 每场切片。
4. VLM 字幕使用 Gemini 2.5 Pro或Quen3-VL-Max或Molmo 2; 发布标题+框架 embedding.
5. 以每场景三个名为矢量的 Qdrant 多矢量指数( 缩放)_组合, 框架_缩写,抄本_和有效载荷 {视频_身份, 现场_ID, 开始_毫秒, 结尾_MS, 键盘_url}.
6. 查询:三个平行的密集查询; reciprocal rank fusion 组合; 上K=5 场景。
7. Temporal grounding 改进(开始、结束)在顶层的场景中。
8. 甚低频集成( VLM)Gemini 2.5 Pro),附有查询+上三段场景剪辑+记录誊本;需要 `(video_id, start_ms, end_ms)` citations.
9. Eval on ActionsNet-QA, NeXT-GQA, 加上100格的手贴定制。 报告整体和每个问题类( 描述、 计数、 动作类型) 的准确性 。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | Temporal grounding IoU | 静脉注射 grounding set |
| 20 | 质量评估准确性 | NeXT-GQA 和 100 格调自定义集 |
| 20 | 最显著的输出 | 每美元指数的视频时数 |
| 20 | 用户界面和引用 UX | 时间戳链接、缩略图条、跳到框架 |
| 15 | Hallucination rate | 单独报告的计算和动作类型准确性 |

艰难的拒绝 :

- 将每个场景的向量集中在一起的管道。 要显示类别区分, 需要多矢量 。
- 答复不引用( 开始、 结束) 。
- 报告一个总体准确性,不包含计算/行动分明细目。
- 无法直接接收场景框架的 VLM 合成( 只文本输入会丢失) visual grounding).

拒绝规则 :

- 拒绝提供许可证来源不明的视频;要求每段视频上贴有许可证标签_id.
- 拒绝要求“实时”反应,其比率高于所测量的输送量。
- 拒绝隐藏计数/动作 hallucination 数字在整体精确度数字中。

输出:包含场景分割 + ASR + 字幕管道、多矢量 Qdrant 收藏、时间 grounding 适配器, 15 个显示时间戳深链接的查看器, 3个基准电子算法结果( 活动网络- QA, NeXT- GQA, 自定义) , 以及一个写入命名您所观察到的三个计算或动作类型故障类别, 以及减少每个类别的检索或合成变化 。
