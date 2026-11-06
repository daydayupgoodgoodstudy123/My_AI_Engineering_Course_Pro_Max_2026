---
name: codec-picker
description: Pick a neural audio codec (EnCodec / DAC / SNAC / Mimi) for a given generative or compression task.
version: 1.0.0
phase: 6
lesson: 13
tags: [codec, encodec, dac, snac, mimi, rvq, semantic-tokens]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定任务（生成 LM、压缩、全双工对话、音乐编辑、保真度目标），输出：

1. 编解码器。 EnCodec-24k · EnCodec-48k · DAC-44.1k · SNAC-24k · Mimi · （后备：用​​于非神经压缩的 Opus）。一句话理由。
2. 帧率+码本。比特率预算、码本计数（通常为 4-12）、目标剪辑持续时间的序列长度。
3. Tokenization方案。扁平化 vs 分层化 (SNAC) vs 语义+声学 (Mimi)。 LM如何消耗tokens。
4. Decoder。编解码器内 decoder · 外部声码器 (HiFi-GAN) · 仅 LM（无声码器，直接预测编解码器 tokens）。解释一下为什么。
5. 培训影响。需要训练encoder/decoder吗？微调域音频（仅限语音→特定于域的音乐）？是现成的冷冻的吗？

在延迟预算紧张的情况下，拒绝用于 AR-LM 工作负载的 DAC — 86 Hz 帧速率 × 8 个代码本 = 每 10 秒 5,504 个 tokens，对于快速生成来说太长。拒绝 Mimi 的音乐——它是语音调音的。拒绝使用 EnCodec 进行语义条件生成——没有语义密码本，文本中的语音模糊。

输入示例：“构建用于文本转语音 TTS 的 AR LM。目标 TTFA 200 毫秒。仅限英语。”

输出示例：
- 编解码器：咪咪。语义+声学拆分可实现文本→码本0→码本1-7分解，既快速又支持语音克隆。
- 帧速率 + 码本：12.5 Hz·8 个码本·4.4 kbps。 10 秒 = 1,000 tokens。
- Tokenization：首先根据文本+说话人参考预测码本0；然后在给定码本 0 + 说话者参考（深度 transformer 模式）的情况下预测码本 1-7。
- Decoder：咪咪内置decoder，无需外接声码器。
- 训练：训练文本到编解码器LM；冻结咪咪。
