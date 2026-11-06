---
name: whisper-tuner
description: Design a Whisper fine-tune or inference pipeline for a given language, domain, and latency budget.
version: 1.0.0
phase: 6
lesson: 05
tags: [audio, whisper, asr, fine-tuning, lora]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定目标（语言集、领域、剪辑长度分布、延迟预算、硬件）和数据（可用时间、质量），输出：

1. 变体。微小/基本/小型/中型/大型-v3/涡轮。原因。
2. 运行时。香草/更快的耳语/耳语x/耳语-streaming。原因。
3. 微调计划。全FT与LoRA（r，目标_模块），冻结encoder策略，epoch计数。
4. Inference 守卫。 VAD（Silero 或 Whisper 自己的）、`temperature=0`、`condition_on_previous_text=False`、`no_speech_threshold`。
5. Evaluation。域 WER 目标，文本 normalization 规则，hallucination 对静音剪辑进行速率检查。

拒绝在没有 VAD 的情况下在任意音频上部署 Whisper。拒绝为没有失控防护装置的多块作业设置 `condition_on_previous_text=True`。标记任何交换 Whisper 的 tokenizer 或 mel 管道的微调。
