<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="voice-agents-pipecat-and-livekit"></a>

# 语音 Agents：Pipecat 与 LiveKit

> Voice agents 2026年的一流生产类别。 Python 输油管(VAD STT ) LLM TTS 运输 。 LiveKit Agents 将AI模型与用户连接到WebRTC。 生产延迟度针对450-600米的地段,即高价堆放。

**类型:** 学习
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop阶段14 · 12 (工作流程模式)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 描述Pipecat基于框架的管道:Downstream(源代码)和UPSTREAM(控制)。
- 命名导音管道阶段, 并运输 Pipecat 支持 。
- 解释 LiveKit Agents'两个声音 agent 课程( 数学、 语音、 语言) 和适合的课
- 总结2026年生产时滞的期望及其驱动建筑选择的方式。

<a id="the-problem"></a>

## 问题

Voice agents 不是一个有 TTS 螺旋线的文本循环。 延迟预算是残酷的 (~ 600ms) , 部分音频是默认的, 转盘检测是一个模型, 传输范围从电话 SIP 到 WebRTC 。 您可以建立基于框架的管道( Pipecat) , 或者靠平台( LiveKit) 。

<a id="the-concept"></a>

## 概念

<a id="pipecat-pipecat-aipipecat"></a>

### 管道(管道-i/管道)

- Python 以框架为基础的管道框架。
- `Frame` → `FrameProcessor` chain.
- 两个流程方向 :
  - **DOWNSTREAM** - 源头 沉入水中(Audio in, TTS out)
  - **UPSTREAM** 反馈和控制(取消、衡量标准、驳入)。
- `PipelineTask` 管理活动周期( 运行)`on_pipeline_started`, `on_pipeline_finished`, `on_idle_timeout`)和衡量标准/跟踪/RTVI观察员。

典型输油管:

```
VAD (Silero) → STT → LLM (context alternates user/assistant) → TTS → transport
```

运输:每日,LiveKit,小型网络运输, FastAPI 韦伯套餐,什么App

管道流动增加了结构化对话(国家机器)。管道云是管理运行的时间。

<a id="livekit-agents-livekitagents"></a>

### LiveKit Agents (livekit/agents)

- 连接AI模型到网络上的用户
- 主要概念: `Agent`, `AgentSession`, `entrypoint`, `AgentServer`.
- 两个声音 agent classes:
  - **MultimodalAgent** 直接通过 OpenAI 实时或同等。
  - **VoicePipelineAgent** - STT LLM TTS 级联; 提供文本级控制 。
- 通过一个语义转换检测 transformer 模型.
- Native MCP integration.
- 通过SIP的电话。
- 50+无型号的模型 API 通过 LiveKit 键 Inference; 通过插件增加200+。

<a id="commercial-platforms"></a>

### 商业平台

Vapi (在优化的溢价堆叠上 ~ 450 - 600 ms) 和 Retell (在180个测试电话中端到端~ 600 ms) 都建在这些上面。 如果您想要一个没有 WebRTC 团队的管理式语音堆放, 请选择一个平台 。

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **不准入内** 用户中断; agent 继续说话。 需要 UPSTREAM 取消 Pipecat 的框架, 等值 LiveKit 。
- **STT 信任被忽视 。** 向法庭提供的低信任记录 LLM 像是福音一样,有自信或要求确认的门
- **TTS 中断句** 当输油管取消中断层时 TTS需要知道或切断音频。
- **长期预算被忽视。** 每个部件加50 -200米 运输前要填上你的链条

<a id="typical-2026-latencies"></a>

### 典型的2026年逾期

- VAD:20-60米
- STT部分: 100-250米
- LLM first token:150-400米
- TTS 第一次音频: 100- 200米
- 运输遥控飞机:30-80米

端到端450-600米是溢价。 800-1200米是常见的。 任何超过1500米的东西都感觉破碎。

```figure
voice-pipeline
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 是一个基于框架的玩具管道,其用途是:

- `Frame` 类型( 音频、 音稿、 文本、 tts)_音频、控制)
- `Processor` 接口 `process(frame)`.
- 由脚本定义的处理器组成五阶段管道（VAD → STT → LLM → TTS → 传输）。
- 一辆UPSTREAM取消框架 以展示驳船进入。

运行：

```
python3 code/main.py
```

该 trace 显示正常流动和驳船进入取消 停止TTS中断层。

<a id="use-it"></a>

## 实际应用

- **Pipecat** 完全控制——自定义处理器, Python- 首先是可插接的供应商
- **LiveKit Agents** 用于网络RTC第一组部署和电话。
- **瓦皮/ 重试** 被收听的声音 agents 没有WebRTC团队。
- **OpenAI 实时/ Gemini Live** 直接音频/音频输出(穆特莫代尔代理)。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-voice-pipeline.md` 架子架上带有VAD+STT+的Pipecat形语音管道 LLM + TTS+运输加驳船装卸。

<a id="exercises"></a>

## 练习

1. 在玩具管道中添加一个量度观察器: 每秒计数框架。 潜伏层在哪里积累?
2. 执行信任定格的STT:低于门槛,请求“你能重复一遍吗?”
3. 添加语义转弯检测:简单规则——如果转弯的转弯以“?"结尾。
4. 读取 Pipecat 的运输文档。 交换小网络传输( stub) 的 Stdlib 运输工具 。
5. 测量 OpenAI 实时对STT+LLM+TTS 级联在同一查询上。文本级控制需要多少时间?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 框架 | "Event" | 输油管中的数据输入单位(音频、记录、文本、控制) |
| Processor | "管道阶段" | 带有进程( 框架) 的处理器 |
| DOWNSTREAM | 前进的流 | 要沉入的源头: 音频进入, 语音输出 |
| UPSTREAM | 后退的流体 | 控制:取消、公制、驳入 |
| 虚拟AD | "声音活动检测" | 检测用户说话时 |
| 语义转弯检测 | "聪明的末日" | 用户完成的基于模型的决定 |
| MultimodalAgent | "直接的音频 agent" | 音频输入, 音频退出; 中间没有文字 |
| VoicePipelineAgent | "Cascade agent" | STT + 卫星导航系统 LLM + TTS; 文本级控制 |

<a id="further-reading"></a>

## 进一步阅读

- [管道文档](https://docs.pipecat.ai/getting-started/introduction) 以框架为基础的管道、加工器、运输
- [LiveKit Agents docs](https://docs.livekit.io/agents/) - WebRTC+声音原始
- [Vapi](https://vapi.ai/) 管理语音平台
- [重温 AI](https://www.retellai.com/) 管理下的声音,竖立标志
