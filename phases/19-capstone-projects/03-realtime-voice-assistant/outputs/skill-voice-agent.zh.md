---
name: voice-agent
description: Build a real-time voice agent with sub-800ms first-audio-out, barge-in handling, and mid-conversation tool use.
version: 1.0.0
phase: 19
lesson: 03
tags: [capstone, voice, webrtc, livekit, pipecat, asr, tts, streaming]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给域名( 客户支持、 排期、 零售助理) 配置 WebRTC 声音 agent 将端到端第一舱的距离维持在800米以下 处理驳船入场时 tool calls和包装丢失。

构建计划 :

1. 站起来,一个活生生的 Agents 1.0 房间, 与一个网络客户端连接麦克风音频。 添加一个 Twilio PSTN 网关, 用于电话覆盖 。
2. Run streaming ASR( 深层Nova-3 托管或快速耳语在 g5. xm) 上显示。 订阅部分和最终记录誊本 。
3. 在 20 米框上运行 Silero VAD v5。 在语音终端上, 与 LiveKit 转盘检测器得分最新部分 ; commit 只有在VAD沉默时才能完成500米,完成分为0.6。
4. 流动 LLM (GPT-4o-realtime, Gemini 2.5 Flash或级联 Claude 海库4.5. 交第一 token 20米之内到达TTS
5. 流 TTS (Cartesia Sonic-2 或 11Labs Flash v3) 。 第一个音频块必须在第一个时段的 200 米内离开服务器 LLM token.
6. 插座: 当 VAD 在讲演或思考中检测到新的用户演讲时, 取消 TTS, 放下剩余 LLM 输出,重新武装 ASR。 `tts_canceled` span.
7. 工具侧通道: 同时运行函数; 如果延迟度 > 300ms, 则发出确认填充器, 这样音频流就不会停止 。
8. 记录100个电话。根据被搁置的记录、哈明VAD基准的错误截止率、第50页第一排、国家情报和质量控制部以及3%的包装下降下的行为,测量WER。
9. 装配合成呼叫器,对单 g5.xig 的50 个同时调用进行测试;报告保持第一降出p95。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | 端到端的延迟度 | 超过100个电话,每100个电话,每100个电话中,50个第一个电话打出不到800米 |
| 20 | 转弯质量 | 假截断率低于Hamming VAD基准的3% |
| 20 | 工具使用正确性 | Mid-conversation tool calls 返回正确数据, 不拖动音频 |
| 20 | 包装损失下的可靠性 | 输入3%的包滴, 并转换稳定 |
| 15 | Eval harness completeness | 使用公共配置的可复制测量 |

艰难的拒绝 :

- Non-streaming 管道(批量ASR、批量TTS)不能击中潜伏目标。
- 任何不立即取消 TTS 缓冲的驳入政策。 延迟取消会产生最差的用户经验回归。
- Tool calls 同步阻断 LLM 流。 它们必须运行在侧频道上。

拒绝规则 :

- 拒绝在没有 VAD 或转折检测器的情况下部署。 固定超时切换结果导致不可接受的截断率。
- 拒绝报告MOS, 而不记录它是人称的还是国家情报和质量控制局的代理。
- 拒绝报告“X下50个潜伏时间”,不至少100个录音电话,并公布通话 traces.

输出: 包含 LiveKit 的回购 agent 工人, PSTN 网关配置, 100调用电量 harness,一个公开的朗富斯语音仪表板,与一个主机竞争者(Retell, Vapi,或)的对等比较。 OpenAI Realtime API 并记录你观察到的三个最大的转弯故障 以及每个故障的探测器调整
