---
name: alm-picker
description: Pick an audio-language model, benchmark subset, output modality (text vs speech), and guardrails for an audio-understanding task.
version: 1.0.0
phase: 6
lesson: 10
tags: [alm, lalm, qwen-omni, audio-flamingo, gemini-audio, mmau]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定任务（语音/声音/音乐/多音频/长音频，输出modality，延迟，许可证），输出：

1. 模型。 Qwen2.5-Omni-7B · Qwen3-Omni · SALMONN · Audio Flamingo 3 · AF-Next · LTU · GAMA · Gemini 2.5 Pro (API) · GPT-4o 音频 (API)。一句话理由。
2. 要验证的基准子集。 MMAU-Pro 语音/声音/音乐/多音频·LongAudioBench·AudioCaps·ClothoAQA。选择与用户任务匹配的轴。
3. 输出modality。仅文本·文本+语音（Qwen-Omni、GPT-4o 音频）。如果需要，额外演讲的预算 decoder。
4. Guardrails。当模型的多音频分数 < 30%（接近随机）时，拒绝需要多音频比较的 prompts。在 LALM 之前进行 Diarize，输入时间超过 10 分钟。
5. 升级。这个任务什么时候应该回归到一个专门的模型——用于转录的 Whisper、用于分类的 BEAT、用于二值化的 pyannote。 LALM 并不是两者中最好的。

在未验证 MMAU-Pro 多音频子集上的模型分数 > 40% 的情况下，拒绝交付多音频比较任务。拒绝没有上游二值化的长音频（> 10 分钟）。标记任何使用供应商报告的数字而无需独立重新验证的部署。

输入示例：“合规审核：转录 10 分钟的银行通话录音 + 检测 agent 是否阅读了强制披露。”

输出示例：
- 模型：用于转录的 Whisper-large-v3-turbo + Gemini 2.5 Pro（通过 API）用于对转录本进行披露检查 QA。直接处理原始音频的 LALM 很诱人，但长音频 LALM 的准确性会下降到超过 10 分钟。
- 基准子集：MMAU-Pro 语音子集 (Gemini 2.5 Pro = 73.4%) — 涵盖语音推理轴。还要抽查您自己的 50 个电话黄金套装。
- 输出 modality：纯文本。审计报告不需要语音输出。
- Guardrails：首先使用 pyannote 3.1 进行日记化；分别发送每个说话者的片段；记录每次调用的置信度得分。
- 升级：如果呼叫未通过披露检查，则路由至人工审核员而不是自主标记。
