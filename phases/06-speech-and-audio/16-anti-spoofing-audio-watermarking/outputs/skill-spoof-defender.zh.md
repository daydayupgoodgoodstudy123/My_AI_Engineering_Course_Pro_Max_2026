---
name: spoof-defender
description: Pick detection model, watermark, provenance manifest, and operational playbook for a voice-generation / voice-auth deployment.
version: 1.0.0
phase: 6
lesson: 16
tags: [anti-spoofing, watermark, audioseal, asvspoof, c2pa, voice-fraud]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定工作负载（voice-gen vs voice-auth、部署规模、合规区域、对手概况），输出：

1. 检测（CM）。 AASIST · RawNet2 · NeXt-TDNN + WavLM · 商业（Pindrop、Validsoft）。训练数据：ASVspoof 2019 / ASVspoof 5 / 特定领域。目标能效比。
2. 水印（出站生成）。 AudioSeal 16 位有效负载编码 `(model_id, user_id, generation_ts)` · WaveVerify (替代) · 无（有理由）。检测器在每次输出预装时在 CI 中运行。
3. 出处。使用部署者密钥签署的 C2PA 清单 · IPTC 元数据 · 无（对于非消费者音频）。
4. 语音验证防护（如果适用）。活跃度挑战（随机短语 TTS' + 转录）、重放攻击检测（AASIST + PA 模型）、每个通道的生物识别阈值 calibration。
5. 可操作。 Audit log 保留、同意工件保留（7 年以上）、滥用检测信号（突然的音量爆发、命名实体 prompts）、终止开关程序。

拒绝在没有 AudioSeal（或等效水印）的情况下部署语音生成。拒绝在没有反欺骗检测的情况下部署语音生物识别——语音克隆使得仅余弦身份验证很容易被绕过。拒绝仅依赖于来源清单的部署（可剥离）。在 ASVspoof 2019 上训练的垃圾检测阈值，用于无需通道 calibration 扫描的实际部署。

输入示例：“银行客户服务 IVR。语音生物识别解锁 + AI 生成的语音 agent。每月 1000 万次通话。美国 + 欧盟。”

输出示例：
- 检测：Pindrop 商业版（首选）或 NeXt-TDNN + WavLM 打开。对 ASVspoof 5 + 100k 银行特定呼叫样本进行培训。域内数据的目标 EER < 0.5%。
- 水印：每个出站 TTS 话语上的 AudioSeal 16 位有效负载；有效负载编码bank_id + session_id +时间戳。检测器在传输前进行验证。
- 出处：音频导出至客户工作流程的 C2PA 清单；仅限内部呼叫跳过。
- 语音验证：每次验证时的活性挑战（TTS 随机 4 位短语；用户重复 + 检测器 + 转录器）。每次入站身份验证尝试都会运行反欺骗。生物识别阈值为 FAR 0.1%、FRR 1%。
- 运营：同意保留 7 年 + audit log 地区（欧盟数据欧盟居民）。突然克隆请求量 > 2σ 时发出警报；滥用检测的终止开关。
