<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="capstone-03--real-time-voice-assistant-asr-to-llm-to-tts"></a>

# 综合项目 03：实时语音助手——从 ASR 到 LLM 再到 TTS

> 声音 agent 感觉右侧有端到端的潜伏在800米以下, 知道什么时候你停止说话, 处理驳船进来, 并且可以调用工具而不拖延。 retell, Vapi, LiveKit Agents,而Pipecat在2026年就都撞到了这个酒吧。他们用同样的形状:a streaming ASR,转基因检测器,a streaming LLM, 和一个 streaming TTS, 全部通过 WebRTC 连接, 每跳一次都用大量潜伏预算。 构建一个, 测量 WER 和MOS 和错误的截断率, 并按包损失来运行 。

**类型:** Capstone
**语言:** Python (agent + 管道), TypeScript (网络客户端)
**先修要求:** 第六阶段(语音和音频),第七阶段(transformers阶段11(LLM 工程,第13阶段(工具),第14阶段(agents17阶段(基础设施)
**实施阶段:** P6 P7 P11 P13 P14 P17 国家妇女委员会
**时间:** 30小时

<a id="problem"></a>

## 问题

2025-2026年,声音是AUX型最快的动向,技术上限每季度下降。 OpenAI Realtime API, Gemini 2.5 现场,卡特西亚音速-2,11Labs Flash v3, LiveKit Agents 1.0, 和 0.0. 70 的 Pipecat 全部将800 ms第一楼的关闭线放在可达范围。 酒吧不仅仅是延迟。 它是一种互动感: 不切断用户, 不切断用户, 恢复中句中断, 调用工具中聊天, 而不拖动音频、 幸存的静电移动网络 。

缝三针是进不去的 REST 电话 建筑已经铺好 streaming 结束。 构建它和失败模式变得可见: 一个 VAD 调频, 用于在背景电视上播放电话音频发动, 一个等待永远无法出现的标点的转折检测器, 一个缓冲400米的 TTS 。 综合项目是一次在负载下修补这些 并发布一个隐蔽与质量报告 。

<a id="concept"></a>

## 概念

输油管有五条 streaming stages: **音频输入** (浏览器或 PSTN 的网络RTC) **ASR** (streaming 深格拉姆Nova-3或快速耳语的部分记录), **转弯检测** (VAD加上一个小转角探测器模型,读取部分补全提示的笔录) **LLM** (streaming tokens 转弯一结束 **TTS** (streaming 音频在~ 200米之内 LLM token).

三个交叉问题。 **Barge-in**:当用户开始在 agent 暂时取消,ASR马上会接 **工具使用**: 中聊天函数调用(weather, calendar)必须运行在侧端频道上,不拖动音频; agent 预填确认 token 如果潜伏超过300米 **Backpressure**:在包损失下,保留部分记录,VAD提高语音门槛值, agent 避免为未知信息说话

测量栏是定量的。 Hamming VAD基准值为15 dB SNR时, WER低于8%。 测得的电话,第一个投出 p50 低于800米。 误截率低于3%。 TTS, MOS高于4.2。 单 g5.x大时, 50 同时调用。 这些是可交付的 。

<a id="architecture"></a>

## 建筑

```
browser / Twilio PSTN
        |
        v
   WebRTC / SIP edge
        |
        v
  LiveKit Agents 1.0  (or Pipecat 0.0.70)
        |
   +----+--------------+--------------+-----------------+
   |                   |              |                 |
   v                   v              v                 v
  ASR              VAD v5         turn-detector     side-channel
(Deepgram         (Silero)          (LiveKit)        tools
 Nova-3 /         speech-gate    completion score    (weather,
 Whisper-v3)      per 20ms        on partials        calendar)
   |                   |              |
   +--------+----------+--------------+
            v
        LLM (streaming)
     GPT-4o-realtime / Gemini 2.5 Flash /
     cascaded Claude Haiku 4.5
            |
            v
        TTS streaming
     Cartesia Sonic-2 / ElevenLabs Flash v3
            |
            v
     audio back to caller
            |
            v
   OpenTelemetry voice traces -> Langfuse
```

<a id="stack"></a>

## 堆栈

- 运输:LiveKit Agents 1.0 (网络传输中心) + Twilio PSTN 网关; 管道 0.0.70 作为备用框架
- 高级记者:Diepgram Nova-3(streaming或快速耳语
- VAD: Silero VAD v5 加上 LiveKit 转盘检测器( 小) transformer 部分记录誊本)
- LLM: OpenAI GPT- 4个实时,集中整合 Gemini 2.5 Flash或级联 Claude 海库4.5(百万亿)streaming 补全, 单独的音频路径)
- TTS: 卡特西亚音频-2(最低第一字节)、 11Labs Flash v3 或自发主机的开放源码 Orpheus
- 工具:天气/日历/预订快速MCP侧道; agent 如果工具使用 > 300 ms , 则预选填充器
- Observability: 开放遥测语音波段,朗弗斯语音 traces 带音频重播
- 部署: 用于自托管Whisper+Orpheus的单 g5. xig (24GB VRAM); 托管 APIs 最低潜伏

```figure
ce-voice-latency
```

<a id="build-it"></a>

## 动手实现

1. **WebRTC 会话 。** 设置一个 LiveKit 房间和一个网络客户端, 向上流传麦克风音频。 在服务器上附加 agent 加入房间的工人

2. **ASR streaming.** 向深格拉姆Nova-3进料 20米的PCM框架(或更快地进行耳语) GPU订阅部分和最后记录,记录每个部分的延迟。

3. **快速自动识别器和转动探测器** 在框架流中运行 Silero VAD v5。 在语音终端事件上, 向 LiveKit 转盘检测器射击最新部分记录。 只有此选项 commit 转换到“完成”当 VAD 表示 500米的静音,转计分数完成 > 0.6。

4. **LLM stream.** 转弯完成后, 开始 LLM 与运行中的谈话通话 加上最后的笔录。 tokens 出来,第一次 token交给TTS

5. **TTS流。** Cartesia Sonic-2 流音块返回。 第一个块必须在第一个磁盘的200米内离开服务器 LLM token。将块从 LiveKit 室中抽取;客户端通过 WebRTC 的杂乱缓冲播放。

6. **Barge-in.** 当 VAD 检测到新的用户语句时, TTS 正在播放, 立即取消 TTS 流, 丢弃剩余 LLM 输出,并重新武装 ASR。 `tts_canceled` span.

7. **工具侧通道** 将天气和日历登记为调用功能的工具。 被引用时, 同时同时发出调用; 如果调用未在300米内解决, 则使用 LLM 释放“ 一秒钟, 让我检查” 作为填充器; 一旦工具返回, 便恢复 。

8. **Eval harness.** 记录100次通话。计算 WER(对缓期发言记录)、错误截止率(用户在中发音时取消TTS)、第一个宣布半发电话、TTS MOS(人或国家质和质和质和量数据)以及一个急减测试(投放3%的包)。

9. **装弹测试** 驱动50个同时呼叫 以一个g5.xig 和合成呼叫器。 测量持续第一降出 p95 。

<a id="use-it"></a>

## 实际应用

```
caller: "what is the weather in tokyo tomorrow"
[asr  ] partial @280ms: "what is the"
[asr  ] partial @540ms: "what is the weather"
[turn ] completion score 0.82 at @820ms; commit
[llm  ] first token @960ms
[tool ] weather.tokyo tomorrow -> 68/52 partly cloudy @1140ms
[tts  ] first audio-out @1040ms: "Tokyo tomorrow will be partly cloudy..."
turn latency: 1040ms user-stop -> audio-out
```

<a id="ship-it"></a>

## 交付成果

`outputs/skill-voice-agent.md` 是一个可交付文件。根据一个域(客户支持、调度或信息站),它会显示一个 LiveKit agent 简要记录/VAD/LLM/TTS管道调整到测量栏。

| Weight | 标准 | 如何衡量 |
|:-:|---|---|
| 25 | 端到端的延迟度 | 超过100个电话,每100个电话,每100个电话中,50个第一个电话打出不到800米 |
| 20 | 转弯质量 | 假截断率低于Hamming VAD基准的3% |
| 20 | 工具使用正确性 | Mid-conversation tool calls 返回正确的数据,不延迟音频 |
| 20 | 包装损失下的可靠性 | 输入3%的包滴, 并转换稳定 |
| 15 | Eval harness completeness | 使用公共配置的可复制测量 |
| **100** | | |

<a id="exercises"></a>

## 练习

1. 交换深格3 以在 g5. x 大小上快速传出 V3 涡轮。 测量延迟和 WER 差距。 确定位置 CPU-与-GPU 决定权很重要。

2. 增加中断仲裁政策: agent 当用户在 tool call比较三个政策( 硬取消、 完成工具- 后停、 下个回合) 。

3. 运行一个对称的转弯检测器测试: 给用户长的暂停时间中断。 标出 VAD 静音阈值和最小误截截点的转弯检测器分数阈值, 而不吹过900米 。

4. 同样的部署 agent 将 PSTN 与 WebRTC 比较。 请解释 Qitter- boffer 和 cocuc 的差别 。

5. 添加非英语语言语音活动检测(日语、西班牙语) 。 测量 Silero VAD v5 假触发率与语言特有微调 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|-----------------|------------------------|
| 转弯检测 | "结束的言语" | 分类者认为,鉴于 VAD 的沉默和部分记录,用户已发言 |
| 打断 | "中断处理" | 当 VAD 检测到新用户语音时, 取消中位播放 TTS |
| First-audio-out | "Latency" | 从用户停止说话到第一个离开服务器的音频包的时间 |
| 虚拟AD | 声音门 | 将音频框架归类为语音对静默的模型; Silero VAD v5 是 2026 默认值 |
| 抖动缓冲器 | "奥迪奥的光滑" | 客户端缓冲, 简短保存包以吸收网络差异 |
| Filler | "Acknowledgment token" | 短句 agent 当工具变慢时, 发出避免沉默的信号 |
| 金属氧化物半导体 | "众人之见" | 语言质量感知评级;国家新闻和质量控制是自动代理 |

<a id="further-reading"></a>

## 进一步阅读

- [LiveKit Agents 1.0](https://github.com/livekit/agents) - 参考WebRTC agent framework
- [Pipecat](https://github.com/pipecat-ai/pipecat) 备选 Python-first streaming agent framework
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime) 综合演讲模式参考
- [深格罗姆·新星-3文档](https://developers.deepgram.com/docs) — streaming ASR参考文献
- [西莱罗 VAD v5](https://github.com/snakers4/silero-vad) - 南澳大利亚州参照模型
- [卡特西亚音速2](https://docs.cartesia.ai) - 低延迟 TTS 参考
- [重现 AI 结构](https://docs.retellai.com) 制作声音 agent architecture
- [Vapi.ai 生产堆](https://docs.vapi.ai) 另类生产参考
