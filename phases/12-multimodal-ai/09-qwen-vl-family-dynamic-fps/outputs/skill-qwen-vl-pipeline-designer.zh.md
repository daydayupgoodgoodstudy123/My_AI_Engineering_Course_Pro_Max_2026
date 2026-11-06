---
name: qwen-vl-pipeline-designer
description: Configure a Qwen2.5-VL or Qwen3-VL deployment — resolution bounds, dynamic-FPS policy, window-attention flag, and JSON agent output mode — for a target video or image task.
version: 1.0.0
phase: 12
lesson: 09
tags: [qwen-vl, m-rope, dynamic-fps, json-agent, video-understanding]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


任务描述(图像质量A、视频动作识别、UI-)agent 工作流程、OCR-Heaty文档、安全摄像机监测 streaming 和部署限制(context window, 临时预算, GPU 类别),发出可运行的 Quen2.5-VL 或 Quen3-VL 配置。

显示 :

1. 分辨率界限。 `min_pixels` 和 `max_pixels` 为任务选择的文档和 UI: 最高值 (1,806,336 = 1344x1344 等值) 。 照片: 默认值。 视频框: 下方以保存框架数 。
2. 固定的低级FPS; 中度动态2-4; 高度动态4-8。 tokens 任务涉及时间的 grounding.
3. 框架预算。 tokens 每部视频=持续时间 * fps * tokens_每_框架。适合可用环境(允许20%的宽度) prompt + 输出)。
4. Window attention。启用 > 720p 输入;在低频情况下禁用 attention 更便宜一点
5. 输出模式。 用于字幕或质量评估的自由格式文本; JSON 工具调用 agent 和 grounding tasks; `<box>` 检测标记
6. Inference kwargs. 用户通过的具体命令 `process_vision_info` + 前进模型。

艰难的拒绝 :
- 将 Quen2-VL (原始, 前置-2.5) 提议为新工程的默认值。 它缺少动态 FPS 和绝对时间 tokens.
- 声称M -RoPE 需要一张位置表。它不是——这是它的整个销售点。
- 使用固定的 1 FPS 进行高音频视频, 然后期待正确动作识别。 取样器必须适应 。

拒绝规则 :
- 如果请求 FPS * duration * tokens_每_框架超过 context window,拒绝并提议集合或缩减框架。
- 如果用户想要在 > 30s 视频上使用 > 7B 模型和 < 40GB VRAM, 请拒绝并推荐框架缩小或更大 GPU.
- 如果用户要求为 a/ 秒的 free- flash 输出 agent 任务、拒绝和建议 JSON 输出模式,工具预申报模式 prompt.

输出: 含有分辨率界限、 FPS 政策、 框架预算、 窗口- 的一页配置attention 旗帜,输出模式, inference 以arxiv 2502.13923(Quen2.5-VL)和251.12631(Quen3-VL)结束,以便更深入地采取后续行动。
