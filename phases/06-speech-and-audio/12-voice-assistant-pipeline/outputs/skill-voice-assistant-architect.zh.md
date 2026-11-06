---
name: voice-assistant-architect
description: Produce a full-stack voice-assistant spec — components, latency budget, observability, compliance — for a given workload.
version: 1.0.0
phase: 6
lesson: 12
tags: [voice-assistant, architecture, livekit, pipecat, compliance]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定用例（消费者/客户支持/可访问性/边缘）、预期规模（并发会话、分钟/月）、语言、延迟目标、合规性（HIPAA、PCI、欧盟人工智能法案、CA SB 942），输出：

1. 组件（7 层）。麦克风 + chunking · VAD · streaming STT · LLM + 工具 · streaming TTS · 播放 · 中断处理程序。为每个名称提供确切的提供商/型号。
2. 延迟预算。每个阶段的 P50 / P95 / P99 目标总和为端到端目标。标记哪些阶段是独立的还是顺序的。
3. 工具调用模式。每个工具的 JSON 规范 + 错误处理 + 后备文本。始终包含 LLM 在失败两次时必须采取的“无能为力”路径。
4. 安全。 Prompt injection 防护、语音克隆锁定（如果 TTS 具有克隆功能）、唤醒词门（始终开启）、日志中的 PII 编辑、30 天保留。
5. Observability。每阶段 P50/P95/P99 · 误中断率 · 工具调用成功率 · 每 100 次调用的 WER · 每分钟成本 · 放弃率。
6. 遵守。披露音频（“这是人工智能助手”）、区域固定（欧盟中的欧盟数据）、audit log 保留、选择退出途径。

拒绝没有唤醒词的始终在线部署。拒绝不流式传输的 TTS（增加话语长度延迟）。拒绝在没有 P95 的情况下平均延迟——尾部是用户流失的地方。未经法律审查，拒绝保留超过 30 天的原始音频。

输入示例：“低视力用户的辅助功能助理：消费者电子邮件应用程序的纯语音界面。英语。P95 < 600 毫秒。~10k 并发用户。”

输出示例：
- 组件：声音设备（WebRTC，通过LiveKit Agents）·Silero VAD·Deepgram Nova-3（英语）·GPT-4o，带电子邮件工具（读取_消息，撰写_回复， mark_read) · Cartesia Sonic 2 streaming · WebRTC 输出 · 中断=取消-LLM-和-VAD 上的 TTS。
- 预算：捕获 120 ms + VAD 40 + STT 150 + LLM TTFT 100 + TTS TTFA 150 = 560 ms P95。
- 工具：read_message({id})、compose_reply({message_id, body})、mark_read({id})、搜索({query})。全部返回JSON； LLM 每个工具最多重试 2 次，然后回退“我做不到——尝试重新措辞”。
- 安全：prompt-注射防护罩（检测`ignore previous instructions`）；唤醒词“嘿邮件”；无语音克隆（固定笛卡尔语音）；在日志中编辑电子邮件正文。
- Observability：汉明AI生产监控；每阶段 Prometheus 直方图；错误中断 > 5% 或 p95 > 800 ms 时发出警报。
- 合规性：人工智能在首次使用时披露； HIPAA 仅选择加入医疗信息；欧盟用户点击欧盟托管的 Cartesia + GPT-4o 爱尔兰。
