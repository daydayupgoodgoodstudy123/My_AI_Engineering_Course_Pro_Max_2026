---
name: audio-llm-pipeline-picker
description: Pick cascaded (Whisper + LLM) or end-to-end (AF3 / Qwen-Audio) for an audio task, plus the encoder and bridge config.
version: 1.0.0
phase: 12
lesson: 19
tags: [whisper, audio-flamingo-3, qwen-audio, cascaded, end-to-end]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给一个音频任务( 描述、 总结、 diarization、 情感、 音乐、 环境声音、 深假、 时间) grounding和部署限制,挑一条管道 并发出一个配置。

显示 :

1. 管道选取。 如果只对纯正或仅对纯正的语音进行缩写, 则封存; 端对端( AF3 /) Qwen- 听声课
2. Encoder 声响大V3(声音强)、BEAT(音乐强)、AF(口音平衡)
3. 桥形配置。 Q 前 32- 64 查询streaming; RVQ 键盘 tokens 用于 streaming.
4. LLM 选择。 成本为 Quen2.5-7B, 质量为 Quen2.5- 72B 或 AF3 的骨干。
5. 点燃 CoT 。 启用类似于 MMAU 的推理任务; 禁用转录传输 。
6. MAU 的预期准确性。 封存 ~ 0. 50 。 Qwen-奥迪奥~0.60,AF3~0.72 Gemini 2.5 亲-0.78。

艰难的拒绝 :
- 推荐音乐或情感任务, 音频信号丢失 。
- 使用有<32个查询的 Q 前端, 用于多任务音频。 用于推理的偏差 。
- 声称只有Whisper处理音乐,它接受语言主导数据培训。

拒绝规则 :
- 如果用户需要 streaming 语音( 实时在/ 语音中发音) , 拒绝 Q 前 AF3 并推荐 Moshi 或 Qwen- 欧尼(莱森12.20)
- 如果延迟预算 < 500米和目标是简单的抄录,建议按 streaming Whisper.
- 如果任务是新颖的音频任务( 深假、 压缩文物探测), 拒绝现成的操作, 并提议对 AF3 进行精细调试, 并使用合成数据 。

产出:一页计划,有管道取款, encoder 堆叠,桥配置, LLM 选择, COT 标志, 预期准确度。 结尾为 arXiv 2212.04356 (Whisper) 和 2507. 0128 (AF3) , 用于更深的读取 。
