# 测验 · 语音 Agents：Pipecat 与 LiveKit（Voice Agents: Pipecat and LiveKit）

> **阶段 14 · Agent 工程 · 第 22 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义机翻质量较差（如把 ms 译成"米"、把 barge-in 译成"驳船"），有疑义请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 语音 agent 不是"文本循环 + TTS" | 延迟预算约 600 ms、音频天然是片段（partial）、轮次检测本身是一个模型、传输层从电话 SIP 到 WebRTC 都有 |
| 2 | 经典级联管道 | `VAD (Silero) → STT → LLM（上下文 user/assistant 交替）→ TTS → transport` |
| 3 | Pipecat 的 frame 模型 | `Frame → FrameProcessor` 链；DOWNSTREAM（source → sink：音频进、TTS 出）与 UPSTREAM（反馈与控制：取消、指标、barge-in）两个方向 |
| 4 | Pipecat 的生命周期与传输 | `PipelineTask` 管生命周期事件（`on_pipeline_started` / `on_pipeline_finished` / `on_idle_timeout`）与 observers；传输支持 Daily、LiveKit、SmallWebRTCTransport、FastAPI WebSocket、WhatsApp；Pipecat Flows 做状态机式对话 |
| 5 | LiveKit Agents | 通过 WebRTC 把模型接到用户；核心概念 `Agent`、`AgentSession`、`entrypoint`、`AgentServer`；有语义轮次检测、原生 MCP、SIP 电话 |
| 6 | 两类语音 agent | MultimodalAgent：直接音频进出（如 OpenAI Realtime），中间没有文本；VoicePipelineAgent：STT → LLM → TTS 级联，换来文本级控制 |
| 7 | Barge-in（用户插话打断） | 用户开口时 agent 必须停嘴：需要 UPSTREAM 的 cancel frame 一路传回 TTS 和 LLM，TTS 要能在句中截断 |
| 8 | STT 置信度 | 低置信度转写不能当"福音"喂给 LLM，要设门槛或请用户确认/重复 |
| 9 | 延迟预算 | 讲义：VAD 20–60、STT partial 100–250、LLM 首 token 150–400、TTS 首音频 100–200、传输 RTT 30–80（ms）；450–600 ms 为高端，800–1200 ms 常见，>1500 ms 体验像"坏了" |
| 10 | 托管平台 | 讲义：Vapi（优化后的高端栈约 450–600 ms）、Retell（180 通测试电话端到端约 600 ms）构建在这些框架之上；没有 WebRTC 团队时选平台 |

### 核心技能（能动手做到）

- [ ] 画出 Pipecat 风格管道，说明 frame 在 DOWNSTREAM 与 UPSTREAM 两个方向上的流动路径
- [ ] 按各阶段延迟区间估算端到端延迟，并指出哪一段是优化重点
- [ ] 读懂本节玩具管道，指出它的 barge-in 演示为什么**实际上没有截断任何音频**，并改成流式 TTS 让截断真正发生
- [ ] 实现基于置信度的 STT 门控（讲义练习 2）
- [ ] 给管道加一个按阶段记录到达时间的 observer（讲义练习 1）
- [ ] 根据产品形态在 Pipecat、LiveKit Agents、Vapi/Retell、MultimodalAgent 之间做选型

---

## 二、基础自测（选择题）

**Q1.** 关于 Pipecat 的两个 frame 流向，下列说法正确的是：

- A. DOWNSTREAM 负责取消与指标，UPSTREAM 负责把音频送往 TTS
- B. 两个方向没有区别，只是命名习惯
- C. DOWNSTREAM 从 source 到 sink（音频进、TTS 出）；UPSTREAM 用于反馈与控制（取消、指标、barge-in）
- D. UPSTREAM 只在电话（SIP）传输中使用

**Q2.** LiveKit Agents 的两类语音 agent 中，"能拿到中间文本、便于做文本级控制（过滤、改写、记录）"的是哪一类？

- A. VoicePipelineAgent：STT → LLM → TTS 级联
- B. MultimodalAgent：直接音频进出
- C. 两者都不能
- D. 只有接入 Pipecat 之后才可以

**Q3.** 按讲义给出的典型 2026 年各阶段延迟（VAD、STT partial、LLM 首 token、TTS 首音频、传输 RTT），把五段的**下限**相加、**上限**相加，分别约为：

- A. 450 ms / 600 ms
- B. 600 ms / 1500 ms
- C. 800 ms / 1200 ms
- D. 400 ms / 990 ms

**Q4.** 讲义对端到端延迟的分档是：

- A. <1500 ms 都算高端
- B. 450–600 ms 为高端，800–1200 ms 常见，超过 1500 ms 感觉像坏了
- C. 800–1200 ms 为高端，450–600 ms 只在实验室能达到
- D. 延迟不重要，只要回答正确即可

**Q5.** 运行本节 `main.py`，scenario 2（"refund please"之后从 transport 发出 UPSTREAM cancel），`transport.delivered` 中这次回复被送出了多少个词？

- A. 0 个，cancel 让 TTS 什么都没说
- B. 3 个，cancel 在第 3 个词后生效
- C. 7 个，与 scenario 1 相同
- D. 14 个，整句都已送出，cancel 到达时 TTS 早已说完

**Q6.** 在原始代码的任何一次运行中，下列哪一条 trace **永远不会**出现？

- A. `TTS: cut mid-word after [...]`
- B. `TTS: cancel received; drop pending audio`
- C. `LLM: cancelled`
- D. `transport: sent 14 words`

**Q7.** 本节代码中，从 `transport` 发出的 `Frame("cancel", None, direction="upstream")` 依次经过哪些处理器？

- A. 只到 TTS 为止
- B. transport → llm → tts → stt → vad
- C. transport → tts → llm → stt → vad
- D. vad → stt → llm → tts → transport

**Q8.** 用户说"refund please"，STT 给出转写 "refund pleats"、置信度 0.41。按讲义"Where this pattern goes wrong"的建议，最合适的处理是：

- A. 原样交给 LLM，让 LLM 自己猜
- B. 低于门槛时不把转写交给 LLM，而是请用户重复或确认
- C. 直接挂断，避免错误回答
- D. 把置信度阈值调到 0，保证每句话都能进 LLM

---

## 三、动手 / 代码题

**Q9.** 原代码 `TTS.process` 处理文本 frame 的部分：

```python
        if frame.kind == "text":
            self.cancelled = False
            words = str(frame.payload).split()
            emitted: list[str] = []
            for w in words:
                if self.cancelled:
                    self.trace.append(f"TTS: cut mid-word after {emitted}")
                    break
                emitted.append(w)
            self.trace.append(f"TTS: emitted {emitted}")
            super().process(Frame("tts_audio", emitted))
```

`main` 中的 barge-in 是这样触发的：

```python
    vad.process(Frame("audio_chunk", "refund please"))
    transport.process(Frame("cancel", None, direction="upstream"))
```

1. 为什么 `if self.cancelled:` 分支永远进不去？
2. 讲义说"The trace shows ... a barge-in cancel that stops TTS mid-utterance"，实际输出符合吗？
3. 改写 TTS（以及一个会在第 3 个词后"插话"的 transport），让截断真正发生。

**Q10.** 下面的顺序在真实系统中很常见：用户在 LLM 还在生成时就插话了，cancel 先到 TTS，随后 LLM 的回复文本才到。

```python
tts2 = TTS("tts2"); t2 = Transport("t2"); link(tts2, t2)
tts2.process(Frame("cancel", None, direction="upstream"))
tts2.process(Frame("text", "late reply still spoken"))
print(t2.delivered)
```

1. 输出是什么？为什么？
2. `LLM.process` 收到 cancel 时做了什么、没做什么？
3. 给出一个能正确处理"取消先于数据到达"的设计。

**Q11.**（讲义练习 2）实现置信度门控的 STT：VAD 送来的 payload 改为 `(text, confidence)`；置信度低于 0.6 时不调用 LLM，直接让 TTS 说 "Sorry, could you repeat that?"。要求复用原有的 `VAD / LLM / TTS / Transport`。

**Q12.**（讲义练习 1 + 延迟预算）
1. 取讲义各阶段延迟区间的**中点**，估算一次"用户说完 → 用户听到第一个音"的端到端延迟。它落在讲义哪一档？
2. 不修改原有类，写一个 `instrument(proc, ...)`，记录每个 frame 到达各处理器的时刻（相对起点的毫秒数）。
3. 如果要把端到端压到 600 ms 以内，你优先优化哪一段？为什么"流式"是关键？

---

## 四、面试高频题

**Q13.**（基础必考）一个级联式语音 agent 由哪些阶段组成？每个阶段的作用和典型延迟是多少？为什么说它"不是文本 agent 外面套一个 TTS"？

**Q14.**（原理深挖）MultimodalAgent（直接音频进出，如 OpenAI Realtime）与 VoicePipelineAgent（STT → LLM → TTS）各有什么优缺点？什么场景下你宁可多付延迟也要选级联？

**Q15.**（原理深挖）Barge-in 在工程上要解决哪些问题？为什么需要 UPSTREAM 控制帧？一个"正确"的打断流程是怎样的？

**Q16.**（场景设计）给一家银行设计电话客服语音 agent（呼入走电话网络、要查询账户、对延迟和合规都敏感）。请给出架构选型、延迟预算和安全措施。

**Q17.**（追问型）你上线的语音 agent 用户反馈"反应慢、老抢话"。你如何排查和优化？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："DOWNSTREAM — source → sink (audio in, TTS out). UPSTREAM — feedback and control (cancellation, metrics, barge-in)." A 把两个方向说反了；B 错，方向决定 frame 往哪个处理器走（代码中 `Processor.process` 根据 `direction` 选择 `next` 或 `prev`）；D 无依据，UPSTREAM 与传输类型无关。

### Q2 — 答案：A

讲义："VoicePipelineAgent — STT → LLM → TTS cascade; gives text-level control." 中间有文本，就可以做内容过滤、PII 脱敏、日志记录、改写话术。B 的 MultimodalAgent "Audio in, audio out; no text in the middle"，延迟更低但失去了文本级控制。C、D 均错。

### Q3 — 答案：D

已用 Python 计算：下限 `20 + 100 + 150 + 100 + 30 = 400 ms`，上限 `60 + 250 + 400 + 200 + 80 = 990 ms`，中点之和 695 ms。也就是说，即使每一段都做到区间下限，也只剩约 50–200 ms 的余量来容纳轮次检测等待、网络抖动、工具调用——这就是讲义"Sum your chain before shipping"的意思。A 是讲义的"高端"区间；C 是"常见"区间；B 混合了不同档位。

### Q4 — 答案：B

讲义："End-to-end 450–600ms is premium. 800–1200ms is common. Anything > 1500ms feels broken." skill 文件也把"冷启动端到端超过 1500 ms"列为拒绝上线的条件。A、C 与讲义相反；D 忽视了语音交互对延迟极其敏感。

### Q5 — 答案：D

实际运行输出：`transport: sent 14 words`。整个 DOWNSTREAM 链是**同步函数调用**：`vad.process(...)` 返回时，LLM 已经生成、TTS 已经把 14 个词全部"说完"、transport 已经发送。之后 `transport.process(cancel)` 才开始执行，只能在各处理器 trace 里留下"cancelled"记录，没有任何音频被截断。A、B 是讲义描述的预期效果，但代码并没有实现；C 是 scenario 1 的词数。

### Q6 — 答案：A

`for w in words:` 循环体内只有 `emitted.append(w)`，不调用任何外部代码，`self.cancelled` 在循环开始前刚被设为 `False`，单线程下没有任何途径在循环中把它改成 `True`，所以 `cut mid-word` 分支是**不可达代码**。B、C 在 scenario 2 中都出现了（cancel 帧确实传到了 TTS 和 LLM，只是来得太晚）；D 是 scenario 2 中 transport 的真实输出。

### Q7 — 答案：C

`link(vad, stt, llm, tts, transport)` 建立双向链表。`Transport.process` 遇到非 `tts_audio` 帧调用 `Processor.process`，方向为 upstream 时转给 `prev`（tts）；TTS 处理 cancel 后 `super().process(frame)` 继续转给 llm；LLM 同理转给 stt；STT、VAD 不认识 cancel，走默认转发，到 VAD 时 `prev is None` 停止。实际 trace 中 `transport saw cancel`、`tts saw cancel`、`llm saw cancel`、`stt saw cancel`、`vad saw cancel` 均出现。D 是 DOWNSTREAM 顺序。

### Q8 — 答案：B

讲义："STT confidence ignored. Low-confidence transcripts fed to the LLM as if gospel. Gate on confidence or request confirmation." skill 文件也把"Confidence-blind STT"列为硬性不合格。A 会让 LLM 一本正经地回答"pleats（褶子）"；C 体验极差；D 等于关闭门控。实现见 Q11。

### Q9 — 参考答案

1. **不可达**：`self.cancelled = False` 之后紧接着的 `for` 循环中没有任何函数调用或让出控制权的点（没有 `await`、没有线程、没有把词逐个交给下游）。TTS 一口气把整句拆成词、放进 `emitted`，然后一次性发出一个 `tts_audio` 帧。cancel 帧只有在 `vad.process(...)` 整个调用栈返回之后才会被处理。
2. **不符合**。实测 transport 送出了全部 14 个词，`TTS: cut mid-word` 从未出现；trace 只证明 cancel 帧"路过"了 TTS 和 LLM。另外 `cut mid-word` 的措辞也不准确——逐词循环最多只能在**词与词之间**截断。
3. 改成**逐词流式发送**，让 cancel 有机会在发送过程中到达（已运行验证）：

```python
class StreamingTTS(TTS):
    def process(self, frame):
        if frame.kind == "text":
            self.cancelled = False
            emitted = []
            for w in str(frame.payload).split():
                if self.cancelled:                       # 现在可能为 True 了
                    self.trace.append(f"TTS: cut after {emitted}")
                    break
                emitted.append(w)
                Processor.process(self, Frame("tts_audio", [w]))   # 每个词立即下发
            return
        super().process(frame)


class BargeInTransport(Transport):
    def __init__(self, name, barge_after):
        super().__init__(name)
        self.barge_after, self.sent = barge_after, 0

    def process(self, frame):
        if frame.kind == "tts_audio":
            self.sent += len(frame.payload)
            self.delivered.append(list(frame.payload))
            if self.sent == self.barge_after:            # 模拟用户在第 3 个词后开口
                self.trace.append("transport: user barged in")
                Processor.process(self, Frame("cancel", None, direction="upstream"))
            return
        super().process(frame)
```

运行结果：`delivered words: ['sure,', 'I', 'can']`，TTS trace 末尾出现 `TTS: cut after ['sure,', 'I', 'can']`。这里依赖的是"同步递归调用中 cancel 在下游发送时被处理"；真实框架用异步队列/任务，TTS 在每个音频块之间检查取消标志或直接被取消任务。

### Q10 — 参考答案

1. 输出 `[['late', 'reply', 'still', 'spoken']]`（已运行验证）。原因：TTS 在收到 `text` 帧时**第一件事就是 `self.cancelled = False`**，把之前收到的取消信号清掉了。也就是说，取消只对"正在说的话"有效（而且如 Q9 所示，实际上连这也做不到），对"马上要说的话"无效。
2. `LLM.process` 收到 cancel 只是在 trace 里写一行 `LLM: cancelled`，然后继续往上游转发。它**没有**中止正在进行的生成、没有丢弃待发送的回复，也没有记录"本轮已作废"。
3. 设计：给每一轮对话分配一个 **turn id / generation id**（单调递增）。
   - 用户新一轮开口（VAD 检测到语音）时，turn id 加 1，并发出 UPSTREAM cancel，携带"作废所有 < 新 turn id 的输出"；
   - LLM、TTS 给自己产出的每个 frame 打上 turn id；
   - 任何处理器收到 turn id 小于"当前有效 turn id"的数据帧直接丢弃；
   - LLM 收到 cancel 时真正取消流式请求（关闭连接/取消任务），节省费用；
   - 上下文中记录"助手这句话只说出了前 N 个词"，避免下一轮 LLM 以为用户听完了整句。
   这样不论 cancel 与数据谁先到，结果都一致。

### Q11 — 参考答案

```python
class GatedSTT(STT):
    def __init__(self, name, threshold=0.6):
        super().__init__(name)
        self.threshold = threshold

    def process(self, frame):
        if frame.kind == "vad_speech":
            text, conf = frame.payload
            if conf < self.threshold:
                self.trace.append(f"STT: low confidence {conf:.2f} for {text!r}")
                Processor.process(self, Frame("text", "Sorry, could you repeat that?"))
                return
            self.trace.append(f"STT: -> {text!r} ({conf:.2f})")
            Processor.process(self, Frame("transcript", text))
            return
        super().process(frame)
```

把 `STT("stt")` 换成 `GatedSTT("stt")` 后依次送入 `("hello", 0.93)` 与 `("refund pleats", 0.41)`，实际输出 `transport.delivered == [['hi', 'there'], ['Sorry,', 'could', 'you', 'repeat', 'that?']]`；LLM 的 trace 中只有一次真正的生成，第二次只是 `llm saw text`（原样转发）。

要点：
- 直接发 `text` 帧而不是 `transcript` 帧，**复用**了 LLM 对未知帧"原样转发"的默认行为，所以不必改 LLM；
- 新帧的 kind 是 `text` / `transcript`，所以写 `super().process(...)`（会进入 `STT.process` 的 else 分支再转发）也能工作；这里用 `Processor.process(self, ...)` 只是更直接地表达"转发给下一个处理器"。**不能**做的是把原始 `vad_speech` 帧交给 `super().process`——父类会把元组 `str()` 成 `"('refund pleats', 0.41)"` 当作转写；
- 生产中还应：连续多次低置信度时转人工；把低置信度片段与澄清事件记入 trace；对关键实体（金额、账号）单独要求确认。

### Q12 — 参考答案

1. 中点：VAD 40 + STT 175 + LLM 275 + TTS 150 + 传输 55 = **695 ms**，介于"高端（450–600）"与"常见（800–1200）"之间。
2. 参考实现（用 `time.sleep` 按中点模拟各阶段耗时，已运行验证）：

```python
import time

STAGE_COST_MS = {"vad": 40, "stt": 175, "llm": 275, "tts": 150, "transport": 55}

def instrument(proc, t_start, arrivals):
    inner = proc.process                       # 保存原方法（已绑定实例）
    def timed(frame):
        if frame.direction == "downstream":
            arrivals.append((proc.name, frame.kind,
                             (time.perf_counter() - t_start[0]) * 1000))
            time.sleep(STAGE_COST_MS[proc.name] / 1000)
        inner(frame)
    proc.process = timed                       # 实例属性覆盖类方法
```

输出：

```text
vad       got audio_chunk  at      0 ms
stt       got vad_speech   at     40 ms
llm       got transcript   at    215 ms
tts       got text         at    491 ms
transport got tts_audio    at    641 ms
end-to-end 696 ms
```

能生效的原因：`Processor.process` 里调用的是 `self.next.process(frame)`，属性查找先找实例属性，所以被替换的 `timed` 会被调用。生产中应把每次"frame 穿过处理器"记为一个 OTel span（skill 文件第 5 条，第 23 节）。

3. 优先级：**LLM 首 token**（区间最宽、绝对值最大，150–400 ms）与 **STT**（100–250 ms）。手段：
   - 全链路**流式**：STT 输出 partial 转写，LLM 流式输出 token，TTS 拿到第一个短句就开始合成——各阶段重叠执行，端到端延迟约等于"各阶段首包延迟之和"而不是"各阶段完整处理时间之和"。skill 文件把"LLM calls without streaming"列为硬性不合格；
   - 选更小/更快的模型、就近部署、复用连接；
   - 轮次检测更聪明（语义 turn detection），少等无谓的静音；
   - 或改用 MultimodalAgent 直接音频进出，去掉 STT/TTS 两跳。

### Q13 — 参考回答要点

- **阶段**（讲义的典型延迟）：
  1. VAD（20–60 ms）：判断用户是否在说话、何时停下，常用 Silero；
  2. STT（partial 100–250 ms）：把音频流式转成文字；
  3. LLM（首 token 150–400 ms）：基于交替的 user/assistant 上下文生成回复；
  4. TTS（首音频 100–200 ms）：把文字流式合成语音；
  5. Transport（RTT 30–80 ms）：WebRTC / 电话 SIP / WebSocket 把音频送到用户。
- **为什么不是"文本循环 + TTS"**（讲义 The Problem）：
  - 延迟预算极紧（约 600 ms），必须全链路流式；
  - 输入是连续的部分音频，何时"说完"需要一个模型来判断（turn detection）；
  - 用户随时会插话，需要反向控制通道（barge-in）；
  - 转写有错误和置信度，需要门控；
  - 传输层多样，电话、WebRTC 各有协议。
- 加分点：知道 Pipecat 的 `PipelineTask` 生命周期事件和 observers；知道 LiveKit 提供语义 turn detection 与 SIP。

### Q14 — 参考回答要点

| 维度 | MultimodalAgent（直接音频） | VoicePipelineAgent（级联） |
|------|---------------------------|--------------------------|
| 延迟 | 少两跳，通常更低 | 各阶段延迟叠加 |
| 副语言信息 | 能感知语气、情绪、停顿 | 转成文字后丢失 |
| 文本级控制 | 中间没有文本，难以过滤/审计 | 可以在文本层做 guardrail、PII 脱敏、日志 |
| 组件可替换性 | 绑定单一模型供应商 | STT、LLM、TTS 可各选最优供应商 |
| 调试 | 难以定位是"听错"还是"想错" | 每一跳都有可检查的中间结果 |

- **宁可多付延迟也选级联的场景**：金融、医疗等需要合规审计、需要逐字记录和内容过滤的场景；需要特定语言/口音最优 STT 的场景；需要用特定品牌音色 TTS 的场景；需要复杂工具调用并精确控制回复文本的场景。
- 讲义练习 5 要求实测两者在同一问题上的延迟差，正是在量化"文本级控制的代价"。

### Q15 — 参考回答要点

- **要解决的问题**：
  1. 检测：VAD/turn detection 判断用户真的开口了（而不是咳嗽、背景噪声、"嗯"）；
  2. 停嘴：立即停止播放 TTS 音频（包括已缓冲在传输层/客户端的部分）；
  3. 停想：取消 LLM 的流式生成与未完成的 TTS 合成，避免浪费和"迟到的回复"；
  4. 状态修正：上下文里记录助手实际说出的部分，而不是完整回复；
  5. 重新进入聆听状态，处理用户新的一轮输入。
- **为什么需要 UPSTREAM**：检测到插话的位置在管道"下游"（传输层/用户侧），而需要停止的是"上游"的 TTS、LLM；DOWNSTREAM 只能把数据往用户方向推，必须有一条反向的控制通道（讲义："Requires UPSTREAM cancel frames in Pipecat, equivalent in LiveKit"）。
- **正确流程的关键**：取消必须在"数据还没全部发出"时生效——即 TTS 必须流式、分块发送并在块之间检查取消（本节玩具代码恰好没有做到，见 Q9）；取消与数据的先后顺序不确定，需要 turn id 机制（见 Q10）；TTS 要能句中截断（讲义 "TTS mid-sentence cutoff"）。
- 常见误区：只在 trace 里打日志就以为实现了打断；把所有 VAD 触发都当插话（应结合语义判断"附和词"）。

### Q16 — 参考回答要点

- **架构选型**：
  - 呼入电话 → 需要 SIP：LiveKit Agents（讲义："Telephony via SIP"）或托管平台 Vapi/Retell；skill 文件规定"电话优先但没有 SIP 适配器就拒绝上线"；
  - 合规要求文本审计 → 选 **VoicePipelineAgent 级联**，在文本层做 PII 脱敏、内容过滤、全量转写存档；
  - 查询账户 → LLM 通过工具调用访问后端，敏感操作二次确认；可利用 LiveKit 的原生 MCP 集成接工具。
- **延迟预算**（目标约 800 ms 内，电话网络本身有额外延迟）：VAD 40、STT 流式 150、LLM 首 token 300（工具调用期间先说一句过渡语"我帮您查一下"）、TTS 首音频 120、传输 80。
- **安全与合规**：音频传输加密（skill 文件："PII audio without encryption in transit"即拒绝）；身份验证（不能只凭声音）；低置信度时复述确认金额、账号；所有工具调用与回复记录 trace（第 23、24 节）；barge-in 必须可用。
- 加分点：说明"何时转人工"、对 STT 的领域词表/热词定制、压测并发。

### Q17 — 参考回答要点

- **"反应慢"**：
  - 先度量：给每个 frame 穿过每个处理器打时间戳（Q12 的 observer，或 OTel span），拿到各阶段 P50/P95，而不是凭感觉；
  - 常见瓶颈：LLM 首 token 慢（模型太大、提示太长、没开流式）、TTS 等整句才合成、轮次检测等待静音时间过长、跨区域网络；
  - 对策：全链路流式、缩短系统提示与上下文、换更快模型、TTS 按短句切分、就近部署。
- **"老抢话"**（agent 在用户还没说完时就回答）：
  - 原因：VAD 静音阈值太短，用户思考时的停顿被当成说完；
  - 对策：使用语义 turn detection（讲义：LiveKit "Semantic turn detection via a transformer model"；练习 3 的"以问号结尾"规则只是最简单的近似），结合语义完整性和静音时长；对附和词（"嗯""对"）不触发新回合。
- **两者的权衡**：静音阈值调长 → 少抢话但更慢；调短 → 更快但抢话。语义轮次检测是同时改善两者的手段。
- 加分点：用录音回放构造回归测试集，每次调整后对比延迟与误打断率。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：语音 agent 的"思考"部分仍是 agent loop。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：级联管道本身就是一种固定工作流。
- [阶段 06 · 04 语音识别 (ASR) — CTC、RNN-T、Attention](../../../06-speech-and-audio/04-speech-recognition-asr/docs/zh.md)：STT 阶段的原理。
- [阶段 06 · 07 文本转语音 (TTS) — 从 Tacotron 到 F5 和 Kokoro](../../../06-speech-and-audio/07-text-to-speech/docs/zh.md)：TTS 阶段的原理。
- [阶段 06 · 14 语音活动检测与对话轮次交接](../../../06-speech-and-audio/14-voice-activity-detection-turn-taking/docs/zh.md)：VAD 与 turn detection。

### 本节被哪些后续内容用到
- [阶段 14 · 23 OpenTelemetry GenAI 语义约定](../../23-otel-genai-conventions/docs/zh.md)：为每个 frame/阶段打 span，度量延迟。
- [阶段 14 · 24 Agent 可观测性（Observability）：Langfuse、Phoenix、Opik](../../24-agent-observability-platforms/docs/zh.md)：把语音管道的 trace 送到可观测平台。
- [阶段 06 · 15 Streaming 语音到语音 — Moshi、Hibiki 和全双工对话](../../../06-speech-and-audio/15-streaming-speech-to-speech-moshi-hibiki/docs/zh.md)：直接音频进出（MultimodalAgent 一侧）的模型路线。
- [阶段 12 · 20 全模态模型：Qwen2.5-Omni 与 Thinker-Talker 分工](../../../12-multimodal-ai/20-omni-models-thinker-talker/docs/zh.md)：端到端语音模型的架构。
- [阶段 19 · 03 综合项目 03：实时语音助手——从 ASR 到 LLM 再到 TTS](../../../19-capstone-projects/03-realtime-voice-assistant/docs/zh.md)：完整实现一个实时语音助手。

### 延伸关键词
`Pipecat` · `LiveKit Agents` · `frame / FrameProcessor` · `DOWNSTREAM / UPSTREAM` · `VAD (Silero)` · `semantic turn detection` · `barge-in` · `MultimodalAgent / VoicePipelineAgent` · `WebRTC` · `SIP` · `time-to-first-token` · `streaming TTS` · `latency budget`
