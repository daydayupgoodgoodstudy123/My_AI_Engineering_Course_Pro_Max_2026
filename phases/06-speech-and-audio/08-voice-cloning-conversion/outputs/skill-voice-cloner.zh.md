---
name: voice-cloner
description: Pick cloning approach (zero-shot / conversion / adaptation), consent artifact, watermark, and safety filters for a voice-cloning deployment.
version: 1.0.0
phase: 6
lesson: 08
tags: [voice-cloning, voice-conversion, watermark, consent, safety]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定任务（语言、可用参考长度、适应预算、许可限制、同意状态、部署规模），输出：

1. 方法。 Zero-shot克隆（F5-TTS / VibeVoice / Orpheus / OpenVoice V2）·语音转换（kNN-VC / OpenVoice V2音色）·扬声器适配（XTTS v2 + LoRA / VITS全程微调）。
2. 参考准备。所需长度、SNR (≥ 20 dB)、单声道 16 kHz+、静音修剪、`ref_text`（必须与 F5-TTS 完全匹配）。拒绝音乐床引用。
3. 同意神器。来自语音所有者的明确录音同意。模板：名称+日期+目的+范围+撤销程序。储存 7 年以上。
4. 水印。每个输出上嵌入 AudioSeal 16 位有效负载。在 CI 中配置检测器以在发布音频之前验证是否存在。
5. 安全过滤器。命名实体（名人/政治家/未成年人）prompt-拒绝；每个用户每小时的速率限制；每个克隆代的audit log；终止开关。

拒绝在没有水印策略的情况下进行克隆。无论是否同意，都拒绝克隆名人/政客/未成年人。拒绝 3 秒以下或 SNR < 20 dB 的参考。拒绝 F5-TTS 进行商业部署 (CC-BY-NC)。在没有明确标记口音转移差距的情况下拒绝跨语言克隆。

输入示例：“辅助功能应用程序：让 ALS 患者在说话时存储声音，然后在失声后通过 TTS 说话。英语、美国。”

输出示例：
- 方法：OpenVoice V2（MIT，zero-shot，6 秒参考）。具有固有同意的可访问性用例；病人是声音的主人。
- 参考准备：在录音室质量条件（安静的房间、USB 麦克风、24 kHz）下录制 5 × 6 秒的剪辑。存储原始+转录本。建立质心参考以确保稳定性。
- 同意：数字签名+证明目的的视频确认（“诊断后语音重用”），存储在加密卷上，保留 10 年。撤销热线。
- 水印：AudioSeal 16位有效负载编码`patient_id` + `clip_id`；检测器在 CI 的每一代上运行。
- 安全性：硬过滤命名实体prompts；记录每一代；投资回报率仅限于患者登录的应用程序实例。没有 API 曝光。
