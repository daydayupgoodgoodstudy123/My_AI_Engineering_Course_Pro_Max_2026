---
name: seq2seq-picker
description: Choose encoder-decoder vs decoder-only for a new sequence-to-sequence task.
version: 1.0.0
phase: 7
lesson: 8
tags: [transformers, t5, bart, seq2seq]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 seq2seq 任务（翻译/摘要/语音转文本/结构化提取/重写）、输入和输出长度分布以及质量与延迟优先级，输出：

1. 建筑学。其中之一：encoder-decoder（T5 / BART / Whisper-style）、decoder-仅指令调整、encoder-仅 + prompt 模板。一句话理由。
2. Pretraining 目标。跨度损坏 (T5)、去噪 (BART)、下一个 token（仅限 decoder）或“跳过 pretraining，微调现有 checkpoint”。将其命名为 checkpoint。
3. 输入格式。任务前缀字符串（T5 样式）与 system prompt（仅限 decoder）与原始 tokens（BART）。包括 BOS/EOS 处理。
4. Decoding strategy。波束搜索宽度和长度惩罚（翻译/摘要），或nucleus/min-p（类似聊天的任务）。说明该任务的具体内容。
5. 评估。适合任务的指标：BLEU / ROUGE / WER / F1 / exact match。包括测试分割大小。

拒绝推荐 encoder-only 用于生成输出。当输入已经是对话时，拒绝推荐 encoder-decoder — decoder-仅自然适合对话记忆。标记任何选择 decoder-only 用于语音转文本，而不提及 Whisper 作为要击败的基线。
