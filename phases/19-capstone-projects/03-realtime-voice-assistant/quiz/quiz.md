# 测验 · 实时语音助手——从 ASR 到 LLM 再到 TTS（Capstone 03 — Real-Time Voice Assistant (ASR to LLM to TTS)）

> **阶段 19 · 综合项目 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义机器翻译错误很多（如把 "800ms" 译成"800米"、把 "barge-in" 译成"驳船进来"、把 "bar" 译成"酒吧"），请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 端到端 streaming 流水线 | 讲义：五个流式阶段——audio in（WebRTC/PSTN）→ streaming ASR → turn detection → streaming LLM → streaming TTS；"You cannot get there by stitching three REST calls" |
| 2 | VAD 与 turn detector 的分工 | VAD（Silero v5）逐 20ms 帧判断"有没有人声"；turn detector 读 ASR partial 判断"这句话说完了没有"；讲义规则：静音 ≥ 500ms **且** 完成度分数 > 0.6 才提交 |
| 3 | First-audio-out | 讲义定义：从用户**停止说话**到第一个音频包离开服务器；目标 100 通电话 p50 < 800ms |
| 4 | 每一跳的延迟预算 | ASR 首个 partial < 300ms；TTS 首个音频块在 LLM 首 token 后 200ms 内发出；工具超过 300ms 就先说 filler |
| 5 | Barge-in | 用户在 agent 说话时开口：立即取消 TTS、丢弃剩余 LLM 输出、重新激活 ASR，并上报 `tts_canceled` span |
| 6 | 工具 side channel | 工具调用并发执行、不阻塞音频；慢于 300ms 时先说 "one second, let me check" |
| 7 | Backpressure | 丢包时暂存 partial、提高 VAD 语音门限、避免在未确认的消息上继续说话 |
| 8 | 质量指标 | WER < 8%（Hamming VAD 基准、15 dB SNR）、false-cutoff rate < 3%、TTS MOS > 4.2、单台 g5.xlarge 50 路并发 |
| 9 | 调度器状态机 | 本节代码：`IDLE → LISTENING → WAITING → THINKING / TOOL → SPEAKING`，barge-in 回到 `LISTENING` |
| 10 | 延迟口径陷阱 | 代码的 `latency_ms()` 从"轮次提交"算起，漏掉了约 480ms 的 VAD 静音等待；按讲义口径，会话 1 实际是 1220ms |

### 核心技能（能动手做到）

- [ ] 画出 ASR / VAD / turn detector / LLM / TTS / tool 的流式时序图，并标出每一跳的延迟预算
- [ ] 读懂本节逐帧调度器，手推会话 1 每个事件的时间戳（2840 → 3140 → 3260 → 3400 → 3580）
- [ ] 指出代码的延迟口径与讲义定义不一致，并改成"用户停止说话 → 首个音频"
- [ ] 找出启发式 turn detector 的两类失败：短句永远不提交、悬空介词结尾被误判为说完
- [ ] 实现"始终开启"的 barge-in（包括 TOOL 状态），并统计 false cutoff
- [ ] 为慢工具设计 filler 与打断仲裁策略（硬取消 / 先完成工具 / 排队到下一轮）
- [ ] 说清 cascaded（ASR→LLM→TTS）与 speech-to-speech realtime 模型的取舍

---

## 二、基础自测（选择题）

**Q1.** 讲义说 "You cannot get there by stitching three REST calls."，根本原因是：

- A. REST 接口不支持音频格式
- B. 三个服务商的 API key 无法共用
- C. 串行的"整段 ASR → 整段 LLM → 整段 TTS"要等每一步完全结束才能开始下一步，延迟相加，达不到 800ms；必须每一跳都流式、流水线化
- D. REST 调用无法携带对话历史

**Q2.** 讲义 Build It 第 3 步中，"turn complete（轮次结束）"的提交条件是：

- A. VAD 连续静音 500ms **且** turn detector 对最新 partial 的完成度分数 > 0.6
- B. VAD 连续静音 200ms 即可
- C. ASR 返回 final transcript 即可
- D. turn detector 分数 > 0.6 即可，不需要 VAD

**Q3.** 本节代码会话 1 输出 `turn latency = 740ms`。这个数字衡量的是：

- A. 用户停止说话到首个音频输出的时间，与讲义的 first-audio-out 定义一致
- B. LLM 首 token 到 TTS 首个音频的时间
- C. 工具调用的耗时
- D. 从"轮次提交"（2840ms）到首个音频（3580ms）的时间，不含用户停止说话后约 480ms 的 VAD 静音等待

**Q4.** 关于 barge-in，下列做法正确的是：

- A. 等当前句子播完再停，以免听起来突兀
- B. VAD 检测到用户新的语音时立即取消 TTS 流、丢弃剩余 LLM 输出、重新激活 ASR
- C. 降低 TTS 音量，继续播放
- D. 暂停 ASR，等 agent 说完再听

**Q5.** 本节代码中 `turn_completion_score("tell me a long story about")` 的返回值是：

- A. 0.2
- B. 0.55
- C. 0.95
- D. 0.75

**Q6.** 讲义要求工具调用超过 300ms 时让 agent 先说 "one second, let me check"。其主要目的是：

- A. 避免长时间沉默让用户以为断线或再次开口，同时工具在 side channel 上继续执行
- B. 降低 LLM 的 token 费用
- C. 给 ASR 更多时间生成 final transcript
- D. 让工具调用改为同步执行

**Q7.** 运行代码，会话 1 中 `filler 'one second, let me check'` 这一行的时间戳是：

- A. 2840ms
- B. 3260ms
- C. 3140ms
- D. 3400ms

**Q8.** 用户说 "I want to book a table……（停顿 600ms）……for four people tonight"，agent 在停顿处就提交了轮次并开始回答。这类问题应该由哪个指标直接衡量？

- A. WER
- B. false-cutoff rate
- C. TTS MOS
- D. first-audio-out p50

---

## 三、动手 / 代码题

**Q9.** 延迟口径。会话 1 的帧序列由 `synth_call("what is the weather in tokyo tomorrow")` 生成：前 6 帧静音（0–100ms），每个词 16 帧（320ms），之后 110 帧静音，每帧 20ms。

```python
    def latency_ms(self) -> int:
        if self.turn_complete_ms and self.first_audio_out_ms:
            return self.first_audio_out_ms - self.turn_complete_ms
        return -1
```

1. 最后一个语音帧的时间戳是多少？用户"停止说话"是在哪一刻？
2. 按讲义的 first-audio-out 定义，会话 1 的真实延迟是多少？是否达到 800ms 目标？
3. 如果把 filler 也算作"首个音频"，延迟又是多少？代码为什么没有这样算？
4. 修改 `run_session` 与 `Metrics`，记录 `user_stop_ms` 并按讲义口径计算延迟。

**Q10.** 启发式 turn detector：

```python
def turn_completion_score(partial: str) -> float:
    if not partial:
        return 0.0
    if partial.rstrip().endswith(("?", ".", "!")):
        return 0.95
    n = len(partial.split())
    if n < 3:
        return 0.2
    if n < 6:
        return 0.55
    return 0.75
```

1. 用户只说 "yes please"（2 个词）会发生什么？实际运行会打印多少行日志？
2. `synth_call` 生成的 partial 里会出现 `?` 吗？0.95 这一分支在 `main()` 中会被触发吗？
3. 给出至少三处改进，并写出修改后的代码。

**Q11.** Barge-in 的触发条件：

```python
        if (barge_in_at_ms is not None and f.t_ms >= barge_in_at_ms
                and state in (State.SPEAKING, State.THINKING)
                and f.is_speech):
            m.barge_ins += 1
            m.log(f"{f.t_ms}ms BARGE-IN: cancel TTS, re-arm ASR")
            state = State.LISTENING
            tts_stream_started_at = -1
            llm_stream_started_at = -1
            continue
```

1. 会话 1 调用时 `barge_in_at_ms=None`。如果用户在 agent 说话时开口，会发生什么？
2. 在会话 1 的工具执行期间（2900–3060ms）插入语音帧并设 `barge_in_at_ms=2900`，结果如何？为什么？
3. 用户在 6 个词后停顿 600ms 再接着说 4 个词：默认参数下和 `barge_in_at_ms=0` 时分别会怎样？`Metrics.false_cutoffs` 会变化吗？
4. 写出修复方案。

**Q12.** 延迟预算与讲义自洽性：

1. 代码中 VAD 静音阈值 500ms、模拟 LLM TTFT 140ms、TTS 首块 180ms。不调用工具时，用户停止说话到首个音频的最小延迟是多少？离 800ms 目标还剩多少余量？
2. 讲义 "Use It" 的示例日志里，`[tool ] ... @1140ms` 而 `[tts  ] first audio-out @1040ms: "Tokyo tomorrow will be partly cloudy..."`。这段日志有什么自相矛盾之处？
3. 讲义要求"静音 500ms 才提交"又要求"p50 < 800ms"，生产系统一般怎样同时满足？

---

## 四、面试高频题

**Q13.**（基础必考）请画出一个实时语音 agent 的流式架构，并给出从"用户停止说话"到"听到第一个音频"的延迟预算拆解。

**Q14.**（原理深挖）VAD 和 turn detector 有什么区别？为什么只用 VAD + 固定静音超时不够？静音阈值、完成度阈值调高或调低分别会带来什么问题？

**Q15.**（工程实践）你要实现 barge-in。除了"取消 TTS"，还有哪些工程细节？（提示：回声、对话历史、取消传播、误触发。）

**Q16.**（场景设计）用户问"帮我查一下明天东京的天气然后订一个下午三点的会议"，涉及两个慢工具（800ms、1.5s）。请设计工具调度、filler 策略，以及用户在工具执行期间插话时的处理策略（讲义练习 2 的三种策略）。

**Q17.**（追问型）既然 GPT-4o-realtime、Gemini Live 这类 speech-to-speech 模型已经能端到端处理语音，为什么还有很多团队坚持用 cascaded 的 ASR → LLM → TTS 架构？

---

## 五、参考答案与解析

### Q1 — 答案：C

非流式串联时，总延迟 ≈ 整段 ASR + 整段 LLM 生成 + 整段 TTS 合成，每一步都要等上一步完全结束。流式流水线让各阶段重叠：ASR 边听边出 partial，LLM 首 token 一出来就交给 TTS，TTS 首块一合成就发出。skill 文件的 hard reject："Non-streaming pipelines (batch ASR, batch TTS) cannot hit the latency target."

- A、B、D 都不是本质原因：REST 可以传音频、可以携带历史；key 问题与延迟无关。

### Q2 — 答案：A

讲义原文："Only commit to 'turn complete' when VAD says silence for 500ms and the turn-detector scores completion > 0.6." 两个条件缺一不可：只看 VAD 会在用户思考停顿时抢话；只看语义完成度无法区分"说完了"和"还在说"。

- B：200ms 太短，正常说话的停顿就会触发。
- C：final transcript 本身也依赖端点检测，不能代替 turn detection。
- D：没有 VAD 就无法知道用户是否还在发声。
- 代码实现为 `silence_run_ms >= 500` 且 `score >= 0.6`（`>=` 与讲义的 `>` 略有出入，影响不大）。

### Q3 — 答案：D

`latency_ms()` = `first_audio_out_ms − turn_complete_ms` = 3580 − 2840 = 740。但 `turn_complete_ms` 是 VAD 静音累计到 500ms 的时刻，用户其实在 2360ms 就停止说话了（最后一个语音帧从 2340ms 开始，到 2360ms 结束）。讲义 Key Terms 定义 first-audio-out 为 "Time from user stops speaking to the first audio packet leaving the server"，按此口径是 3580 − 2360 = **1220ms**，超出 800ms 目标。

- A 是常见误读；B 是 180ms（3400 → 3580）；C 是 420ms（2840 → 3260）。

### Q4 — 答案：B

讲义 Build It 第 6 步："cancel the TTS stream immediately, drop the remaining LLM output, and re-arm the ASR. Publish a `tts_canceled` span." skill 文件的 hard reject 也写明："Any barge-in policy that does not cancel the TTS buffer immediately."

- A：延迟取消是体验最差的情形；C：降音量仍在"抢话"；D：正好反了，ASR 必须马上接收用户的新语音。

### Q5 — 答案：D

该字符串没有句末标点，有 6 个词，`n < 6` 不成立，落到最后的 `return 0.75`。这恰恰暴露了启发式的问题：以介词 "about" 结尾，明显没说完，却拿到了高于 0.6 门限的分数。会话 2 正是因此在 2520ms 提交了轮次。真正的 turn detector（讲义：LiveKit 的小型 Transformer）会读语义，这类句子得分应很低。

### Q6 — 答案：A

沉默超过几百毫秒，用户就会怀疑没听见或断线，开始重复或追问，进而触发 barge-in 和更多混乱。filler 填补沉默，工具在 side channel 上并发执行。讲义 Key Terms："Short phrase the agent emits to avoid silence when a tool is slow."

- B、C、D 都不是目的；D 正好违背了"不阻塞"的要求。

### Q7 — 答案：C

轮次在 2840ms 提交，同一帧进入 `TOOL` 状态并记录 `tool_started_at = 2840`；之后每帧检查 `f.t_ms − tool_started_at >= 300`，第一次满足是 3140ms。工具延迟 420ms，在 3260ms 返回（B）；再加 140ms 模拟 TTFT，3400ms 出首 token（D）。A 是轮次提交时间。

### Q8 — 答案：B

false cutoff 就是"用户还没说完，agent 就认为轮次结束而抢话"。讲义要求 false-cutoff rate < 3%，练习 3 专门要求用"句中长停顿"做对抗测试。

- A：WER 衡量转写准确率；C：MOS 衡量合成语音质量；D：衡量响应速度。降低 false cutoff 和降低延迟往往是一对矛盾（见 Q14）。

### Q9 — 参考答案

1. 语音帧从 120ms 开始，7 个词 × 16 帧 = 112 帧，最后一个语音帧时间戳为 `120 + 111 × 20 = 2340ms`，覆盖到 2360ms。用户在 **2360ms** 停止说话。此后第 25 个静音帧（2840ms）时 `silence_run_ms` 累计到 500，轮次提交。
2. 3580 − 2360 = **1220ms**，未达到 p50 < 800ms 的目标。其中 VAD 等待 480ms、工具 420ms、TTFT 140ms、TTS 180ms。不调用工具时（`use_tool=False`，已实际运行）首个音频在 3160ms，也正好是 800ms。
3. filler 在 3140ms 说出，如果算作首个音频，延迟是 3140 − 2360 = 780ms。代码里 filler 只写了一行日志，**并没有真的把音频送进 TTS**，也没有更新 `first_audio_out_ms`。讲义把 filler 设计成"让用户尽快听到声音"的手段，因此评估时应把 filler 的音频也计入，或分别报告"首个音频"和"首个实质性回答音频"两个指标。
4. 参考修改：
   ```python
   @dataclass
   class Metrics:
       ...
       user_stop_ms: int = 0

       def latency_ms(self) -> int:
           if self.user_stop_ms and self.first_audio_out_ms:
               return self.first_audio_out_ms - self.user_stop_ms
           return -1

   # run_session 的 LISTENING 分支中：
           if f.is_speech:
               silence_run_ms = 0
               final_partial = f.partial or final_partial
           else:
               if silence_run_ms == 0:
                   m.user_stop_ms = f.t_ms        # 第一个静音帧 = 用户停止说话
               silence_run_ms += 20
   ```
   同时在 filler 分支里，若 `m.first_audio_out_ms == 0` 则记录首个音频时间（如果决定把 filler 计入）。修改后会话 1 报告 1220ms。

### Q10 — 参考答案

1. 2 个词得分 0.2，永远低于 0.6，轮次**永远不会提交**。更糟的是，静音满 500ms 后每一帧都会再打印一次 "SILENCE but score=0.20, waiting"。实际运行：共 87 行日志（1 行 LISTENING + 86 行 waiting，从 1240ms 一直到最后一帧 2940ms），`turn_complete_ms` 保持 0。"yes please"、"no"、"thanks" 这类短回答在对话中极其常见，这个启发式会让 agent 永远沉默。
2. 不会。`synth_call` 只做 `script.split()` 再拼接，partial 从不带标点；`main()` 中两个脚本也都没有标点。因此 0.95 分支在演示中从未触发。真实 ASR（如 Deepgram）会给 partial/final 加标点，这时规则才有意义。若把脚本改成 `"book it?"`，实际运行得到 `score=0.95`，提交在 1240ms。
3. 改进思路（任选三处以上）：
   - **最长静音兜底**：静音超过例如 1500ms，无论分数多少都提交，避免永远沉默；
   - **只评估一次或在 partial 变化时再评估**，避免每帧打印/调用模型；
   - **悬空词惩罚**：以介词、连词、冠词（about / and / the / to …）结尾时大幅降分；
   - **短句不按词数惩罚**：常见的完整短回答（yes / no / thanks / okay）直接给高分；
   - **自适应静音阈值**：分数高时 300ms 就提交，分数低时等到 1000ms 以上。
   ```python
   DANGLING = {"about", "and", "or", "the", "a", "to", "of", "for", "with", "but", "so"}
   SHORT_COMPLETE = {"yes", "no", "yeah", "nope", "thanks", "okay", "ok", "sure"}

   def turn_completion_score(partial: str) -> float:
       words = partial.lower().rstrip("?.! ").split()
       if not words:
           return 0.0
       if partial.rstrip().endswith(("?", ".", "!")):
           return 0.95
       if words[-1] in DANGLING:
           return 0.1
       if words[0] in SHORT_COMPLETE and len(words) <= 3:
           return 0.85
       return 0.55 if len(words) < 6 else 0.75

   def silence_needed_ms(score: float) -> int:      # 自适应：越确定，等得越短
       return 300 if score >= 0.85 else 500 if score >= 0.6 else 1500
   ```
   在调度器中把 `silence_run_ms >= 500 and score >= 0.6` 改为 `silence_run_ms >= silence_needed_ms(score)`，并在 `silence_run_ms >= 1500` 时无条件提交。修改后 "tell me a long story about" 得 0.1，不会抢话；"yes please" 得 0.85，300ms 后就提交。

### Q11 — 参考答案

1. `barge_in_at_ms is not None` 为假，整个 barge-in 分支被跳过。agent 会**无视用户**继续"说话"——barge-in 实际上是一个靠外部预先指定时间的开关，而不是由 VAD 实时驱动的能力。
2. 实际运行：插入的语音帧被完全忽略，事件序列与原会话 1 完全一样（filler 3140、tool 3260、首 token 3400、首音频 3580）。原因是条件只检查 `State.SPEAKING` 和 `State.THINKING`，**不含 `State.TOOL`**；而 TOOL 状态下的处理逻辑也不看 `is_speech`。讲义练习 2 恰好要求设计"工具执行中被打断"的仲裁策略，代码没有覆盖。
3. 实际运行（6 个词结束于 2040ms，停顿 600ms，2640ms 起继续说）：
   - 默认参数（`None`）：2520ms 提交 "i want to book a table"，2660ms 首 token，2840ms 开始播音；用户后半句 "for four people tonight" 被完全忽略，agent 在用户说话时继续说。
   - `barge_in_at_ms=0`：2520ms 提交，2640ms 用户继续说话触发 BARGE-IN，回到 LISTENING；4400ms 重新提交完整句子 "i want to book a table for four people tonight"，4720ms 首音频。这一次 agent 的抢话被及时纠正，但它本质上是一次 **false cutoff**。
   - 两种情况下 `false_cutoffs` 都是 0——这个字段在代码中**从未被赋值**。
4. 修复：
   ```python
   ACTIVE = (State.THINKING, State.TOOL, State.SPEAKING)

   if state in ACTIVE and f.is_speech:                 # 始终开启，由 VAD 驱动
       m.barge_ins += 1
       if f.t_ms - m.turn_complete_ms < 1500:          # 提交后很快就被打断：疑似抢话
           m.false_cutoffs += 1
       m.log(f"{f.t_ms}ms BARGE-IN: cancel TTS/tool, re-arm ASR")
       state = State.LISTENING
       silence_run_ms = 0
       tts_stream_started_at = llm_stream_started_at = -1
       tool_started_at = -1                              # 或按策略保留工具结果
       filler_emitted = False
       continue
   ```
   另外还需要：每个轮次重置 `first_llm_token_ms`/`first_audio_out_ms`（现在只记录第一轮）；用回声消除或"最短语音时长"过滤 agent 自己的声音和咳嗽等误触发；上报 `tts_canceled` span。更严格的 false cutoff 判定是"被打断后用户说的内容是上一句的延续"（例如新 partial 以旧 partial 为前缀），而不是简单看时间。

### Q12 — 参考答案

1. 按代码的帧粒度：静音等待 480ms（第 25 个静音帧）+ TTFT 140ms + TTS 首块 180ms = **800ms**。实际运行 `use_tool=False` 得到首音频 3160ms，3160 − 2360 = 800ms。也就是说，即使 LLM 和 TTS 都很快，仅凭"静音 500ms 才提交"这一条规则就吃掉了大约 60% 的预算，p50 < 800ms 几乎没有余量。
2. 时间线自相矛盾：TTS 在 1040ms 就说出了 "Tokyo tomorrow will be partly cloudy"，而天气工具 1140ms 才返回结果——agent 不可能在工具返回前说出工具结果。另外这一轮的 turn latency 1040ms 本身也超过了讲义自己设定的 800ms 目标。这段日志应理解为示意，而非真实测量。
3. 常见做法：
   - **自适应端点**：turn detector 很有把握时（如问句、完整陈述）把静音阈值降到 200–300ms，没把握时才等更久；
   - **投机执行（speculative / preemptive generation）**：静音一开始就用当前 partial 预先调用 LLM（甚至 TTS），若用户继续说话就丢弃，确认轮次结束时直接播放已生成的内容；
   - **filler / 回应词**：先播放短确认音或 filler，把"首个音频"提前；
   - 选择首包延迟低的 ASR/TTS（讲义：Deepgram Nova-3 首个 partial < 300ms、Cartesia Sonic-2 "lowest first-byte"），以及 prompt caching、就近部署减少网络往返。

### Q13 — 参考回答要点

- **架构**：客户端（浏览器 WebRTC / 电话 PSTN）→ 媒体边缘（LiveKit / Twilio）→ agent worker：
  - streaming ASR（20ms PCM 帧，持续输出 partial/final）；
  - VAD（Silero v5，逐帧语音/静音）+ turn detector（读 partial 打分）；
  - LLM 流式输出 token，首 token 立即交给 TTS；
  - streaming TTS 分块发回，客户端经 jitter buffer 播放；
  - 工具在 side channel 并发执行；OpenTelemetry voice span → Langfuse。
- **预算拆解示例**（以 800ms 为目标）：端点检测 200–500ms → LLM 首 token 150–300ms → TTS 首块 ≤ 200ms（讲义硬性要求）→ 网络与 jitter buffer 50–100ms。端点检测往往是最大的一块。
- 加分点：指出"先 TTS 第一句、后面边生成边合成"的句级切分；说出 TTFT、首字节、jitter buffer 等术语；强调必须测 p50/p95 而不是平均值。

### Q14 — 参考回答要点

- **VAD**：声学层面的二分类（这一帧是不是人声），反应快但不懂语义，会被背景电视、咳嗽触发（讲义："a VAD tuned for phone audio firing on background TV"）。
- **turn detector**：语义层面判断"这句话是否完整"，读的是 ASR partial；讲义中 LiveKit 用的是一个小型 Transformer。
- **只用 VAD + 固定超时的问题**：人在思考、列举时常有 500ms 以上的停顿，固定超时会抢话；为了不抢话把超时调长，又会让所有回答都变慢。skill 文件的拒绝规则："Fixed-timeout turn-taking produces unacceptable cutoff rates."
- **阈值调节的取舍**：
  - 静音阈值调低 / 完成度门限调低 → 更快，但 false cutoff 上升；
  - 调高 → 更稳，但延迟上升，用户以为 agent 卡住了；
  - 讲义练习 3：在"不超过 900ms"约束下最小化 false cutoff。
- 加分点：把阈值做成与分数相关的自适应函数；丢包时提高 VAD 门限（讲义 backpressure 一段）。

### Q15 — 参考回答要点

- **回声消除（AEC）**：agent 自己的声音从扬声器进入麦克风，会被 VAD 当成用户说话，导致"自己打断自己"。WebRTC 客户端一般自带 AEC，电话场景需要服务端处理。
- **误触发过滤**：要求连续若干帧语音（如 ≥ 200ms）或 ASR 出现实际词语才算 barge-in，避免咳嗽、"嗯"打断回答；也有产品把 "嗯哼" 这类 backchannel 识别出来并忽略。
- **取消传播**：一次取消要同时停掉 TTS 合成、已缓冲但未播放的音频（服务端和客户端 jitter buffer 都要清）、正在进行的 LLM 流式请求（节省 token），以及按策略处理进行中的工具调用。
- **对话历史**：把 assistant 消息**截断到实际播放出去的部分**再写入历史，否则模型会以为用户听到了它没听到的内容。
- **可观测性**：上报 `tts_canceled` span（讲义第 6 步），记录被打断的位置，用于统计 false cutoff 和调参。
- 常见误区：只停 TTS 不停 LLM，结果下一轮又把旧回答的剩余部分播出来。

### Q16 — 参考回答要点

- **调度**：LLM 发出 tool call 后，两个工具若无依赖则**并发**执行；有依赖（例如要先确认日程再预订）则串行，但每一步都在 side channel 上运行，主音频流不阻塞。
- **filler**：首个工具超过 300ms 未返回即播放 filler（讲义第 7 步）；1.5s 的工具可再加第二段进度提示（"正在帮你订会议"），避免长时间沉默；filler 要有多种说法，避免机械重复。
- **结果合成**：先返回的结果可以先说（"东京明天多云，68/52 华氏度"），再说会议预订结果；即"边到边说"。
- **工具执行中被打断**（讲义练习 2 的三种策略）：
  1. 硬取消（hard cancel）：立即取消工具和回复，最灵敏，但有副作用的工具（订会议）可能处于中间状态；
  2. 先完成工具再停（finish-tool-then-stop）：保证一致性，结果留给下一轮使用；
  3. 排队到下一轮（queue next turn）：不打断当前工具，把用户新话语排队。
  - 实践中按工具类型选择：只读工具可以硬取消；有副作用的写操作应先完成或回滚，并在下一轮告知用户。
- 加分点：对写操作做幂等设计，被打断重试时不会重复订会议。

### Q17 — 参考回答要点

- **speech-to-speech 的优势**：延迟最低、能保留语气和情感、天然支持全双工。
- **cascaded 仍流行的原因**：
  - **可控与可观测**：每一步都有文本中间结果，能做日志、审计、guardrail、PII 脱敏；
  - **可替换**：ASR、LLM、TTS 可分别选最优供应商或自托管（讲义的栈里就有 Deepgram + Claude Haiku 4.5 + Cartesia 的级联方案），也能分别优化成本；
  - **工具调用与 RAG**：文本 LLM 的生态（function calling、长上下文、prompt caching）更成熟；
  - **评估方便**：可以分别测 WER、LLM 正确率、MOS；
  - **成本**：音频 token 计费通常更贵。
- **取舍**：追求极致自然度和最低延迟时选 speech-to-speech；需要强控制、合规、复杂工具链时选 cascaded。讲义 Stack 中同时列出了 GPT-4o-realtime、Gemini 2.5 Flash Live 和 cascaded Claude Haiku 4.5 三种选择。
- 加分点：提到 Thinker-Talker 这类"内部级联、外部端到端"的折中架构。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 04 语音识别 (ASR) — CTC、RNN-T、Attention](../../../06-speech-and-audio/04-speech-recognition-asr/docs/zh.md)：理解 streaming ASR 的 partial/final 结果从何而来。
- [阶段 06 · 07 文本转语音 (TTS)](../../../06-speech-and-audio/07-text-to-speech/docs/zh.md)：TTS 首包延迟与音质（MOS）的来源。
- [阶段 06 · 11 实时音频处理](../../../06-speech-and-audio/11-real-time-audio-processing/docs/zh.md)：20ms 帧、缓冲区与实时约束。
- [阶段 06 · 14 语音活动检测与对话轮次交接](../../../06-speech-and-audio/14-voice-activity-detection-turn-taking/docs/zh.md)：Silero VAD 与 turn-taking，本节调度器的直接前置。
- [阶段 14 · 22 语音 Agents：Pipecat 与 LiveKit](../../../14-agent-engineering/22-voice-agents-pipecat-livekit/docs/zh.md)：讲义推荐的两个框架。
- [阶段 13 · 03 并行 Tool Calls 与工具调用中的 Streaming](../../../13-tools-and-protocols/03-parallel-and-streaming-tool-calls/docs/zh.md)：side channel 工具调用的基础。

### 本节被哪些后续内容用到
- [阶段 19 · 17 个人 AI 导师——自适应、多模态与记忆](../../17-personal-ai-tutor/docs/zh.md)：语音交互作为多模态导师的一个通道。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：语音延迟预算中的 LLM 部分。
- [阶段 17 · 22 对 LLM APIs 进行负载测试](../../../17-infrastructure-and-production/22-load-testing-llm-apis/docs/zh.md)：讲义第 9 步的 50 路并发压测。
- [阶段 06 · 15 Streaming 语音到语音 — Moshi、Hibiki 和全双工对话](../../../06-speech-and-audio/15-streaming-speech-to-speech-moshi-hibiki/docs/zh.md)：cascaded 之外的端到端路线。
- [阶段 06 · 17 音频 Evaluation — WER、MOS、UTMOS](../../../06-speech-and-audio/17-audio-evaluation-metrics/docs/zh.md)：讲义第 8 步评估指标的详细做法。

### 延伸关键词
`streaming ASR` · `Silero VAD` · `turn detection / endpointing` · `barge-in` · `AEC 回声消除` · `jitter buffer` · `first-audio-out` · `TTFT` · `filler / backchannel` · `speculative generation` · `WebRTC / SIP / PSTN` · `WER / MOS / NISQA` · `false cutoff` · `speech-to-speech`
