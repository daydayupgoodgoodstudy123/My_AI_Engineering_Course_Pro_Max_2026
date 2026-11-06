---
name: video-vlm-frame-planner
description: Plan frame sampling, per-frame pooling, output format, and benchmark targets for a video-language model deployment.
version: 1.0.0
phase: 12
lesson: 17
tags: [video-vlm, temporal-grounding, tmrope, dynamic-fps, benchmarks]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给视频任务( 动作识别, 时间 grounding、总结、监测、 agent- 工作流程重播和部署限制(模式背景、延迟预算、工作量),发布框架 sampling 和产出计划。

显示 :

1. 框架取样器选择。 稳定内容的统一, 混合运动的动态FPS, 动作重的事件驱动, 关键框架+视频的字符串 。
2. 高详细、3x3默认、4x4或6x6 agent 内容密度低于覆盖范围的工作流程。
3. 时间编码。 Qwen2.5- VL- family 的TMROPE; 学习的时间 embedding 用于小模型;单剪任务没有编码。
4. 输出格式。 JSON 与 `{event, start, end, confidence}` 用于 grounding; 用于汇总的免费文本; token- 限制混合流动。
5. 基准计划:一般视频MME,Temprogass grounding, EgoSchema 表示长方位。指定预期的精度级。
6. 背景/延迟预算。 tokens = 持续时间 * fps * tokens_每_框架。如果超过上下文的40%,要警告它。

艰难的拒绝 :
- 提议穿制服 sampling 失去高峰事件
- Claiming token- 有限输出匹配 JSON 下游分析的准确性。 JSON 更强
- 推荐视频-LLaMA 旧建筑不再具有竞争力

拒绝规则 :
- 如果持续时间 > 10分钟和上下文 < 32k,则拒绝并建议等级总结或 agentic 检索( Lesson 12.18).
- 如果目标准确度是边界(在 Gemini 2.5 Pro on VideoMME),拒绝打开7B型号,需要32B+或专有。
- 如果7B时,在大于30秒的弹夹上,动态FPS目标 > 8,则拒绝潜伏,并建议降低上限。

产出:一页框架计划,带有取样器、集合、时间编码、输出格式、基准目标、上下文估计。LLaMA)用于比较阅读。
