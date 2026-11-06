# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 03 节 实时语音助手——从 ASR 到 LLM 再到 TTS ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`、`enum`），不需要麦克风、音频库、网络或 API key
>
> 同目录下的 `code/ts/` 是一个 TypeScript 版本（WebSocket 协议、VAD、编排器），不在本讲解范围内。

---

## 1. 这份代码在考察什么

模块 docstring 说得很清楚："The hard architectural primitive in a 2026 voice agent is not the ASR or the TTS. It is the streaming scheduler..."。所以这份代码**不处理任何真实音频**，而是用"模拟的 20ms 帧"驱动一个**逐帧调度器**，考察：

1. **帧流抽象**：每 20ms 一帧，携带 VAD 判定（是否人声）和 ASR 的累积 partial。
2. **轮次检测**：VAD 连续静音 ≥ 500ms **且** turn detector 分数 ≥ 0.6 才提交（讲义 Build It 第 3 步）。
3. **状态机**：`IDLE → LISTENING → WAITING → THINKING / TOOL → SPEAKING`，barge-in 时回到 `LISTENING`。
4. **工具 side channel 与 filler**：工具超过 300ms 未返回就"说"一句 filler。
5. **延迟记账**：记录轮次提交、LLM 首 token、TTS 首个音频的时间。

> 一句话：**把语音 agent 的"何时开口、何时闭嘴、等工具时说什么"写成一个由时间戳驱动的状态机**。但要注意它的延迟口径、turn detector 启发式、barge-in 触发方式都有明显简化，正好是讨论真实系统难点的切入口。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Frame` | dataclass | 一帧：时间戳、是否人声、当前累积 partial | 20ms PCM 帧 + VAD + streaming ASR |
| `synth_call` | 函数 | 生成"120ms 静音 + 每词 320ms 语音 + 2200ms 静音"的帧序列 | 模拟来电 |
| `turn_completion_score` | 函数 | 按句末标点与词数给出完成度分数 | LiveKit turn detector 的替身 |
| `State` | Enum | 6 个状态 | 调度器状态机 |
| `Metrics` | dataclass | 事件日志 + 关键时间戳 + 计数器；`latency_ms()` | 延迟记账 / 可观测性 |
| `Tool` / `WEATHER` | dataclass / 常量 | 名称、模拟延迟 420ms、结果 | side channel 工具 |
| `run_session` | 函数 | 逐帧推进状态机，处理 barge-in、轮次提交、工具、LLM、TTS | 流式调度器 |
| `main` | 函数 | 会话 1：带工具的正常通话；会话 2：被打断的通话 | 演示 |

数据流：`synth_call(script)` → 帧列表 → `run_session(frames, use_tool, barge_in_at_ms)` 逐帧：barge-in 检查 → 按状态处理（听 / 判断轮次 / 发起 LLM / 等工具 / 等首 token / 等首音频）→ 返回 `Metrics` → `main` 打印事件日志与时间。

---

## 3. 逐段精讲

### 3.1 `Frame` 与 `synth_call`：模拟音频流

```python
@dataclass
class Frame:
    t_ms: int              # timestamp ms since session start
    is_speech: bool        # VAD verdict (Silero v5 stand-in)
    partial: str = ""      # ASR cumulative partial (Deepgram Nova-3 stand-in)
```

- 真实系统中，一帧是 20ms 的 PCM 音频，`is_speech` 由 Silero VAD 给出，`partial` 由 streaming ASR 异步推送。这里把三者合进一个对象，ASR **零延迟**、VAD **零误差**。

```python
def synth_call(script, start_ms=0, noise=0.0):
    words = script.split()
    frames = []
    t = start_ms
    for _ in range(6):                       # 120ms 前导静音
        frames.append(Frame(t_ms=t, is_speech=random.random() < noise))
        t += 20
    partial = ""
    for w in words:
        partial = (partial + " " + w).strip()
        for _ in range(16):                  # 每个词 320ms
            frames.append(Frame(t_ms=t, is_speech=True, partial=partial))
            t += 20
    for _ in range(110):                     # 2200ms 尾随静音
        frames.append(Frame(t_ms=t, is_speech=False, partial=partial))
        t += 20
    return frames
```

- 时间轴（会话 1，7 个词）：静音 0–100ms；语音帧 120–2340ms（共 112 帧，用户在 **2360ms** 停止说话）；静音帧 2360–4540ms。总共 228 帧。
- partial 是**累积的**：第 3 个词的帧 partial 为 `"what is the"`，模拟 ASR 不断修正、加长的中间结果。
- `noise` 只作用于前 6 帧，用来模拟背景噪声让 VAD 误判；`main()` 中 `noise=0`，所以 `random.seed(0)` 实际上不影响结果——整个程序是确定的。
- ⚠️ partial 从不带标点（`split` 后再拼接），见 3.2。

### 3.2 `turn_completion_score`：启发式 turn detector

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

- 规则：有句末标点 0.95；否则按词数 0.2 / 0.55 / 0.75。门限是 0.6，所以**没有标点时至少要 6 个词**才可能提交。
- `str.endswith` 可以接收一个**元组**，任一后缀匹配即为真。
- ⚠️ 失败案例一（抢话）：`"tell me a long story about"` 6 个词、介词结尾，得 0.75，会话 2 因此在 2520ms 提交。
- ⚠️ 失败案例二（永不提交）：`"yes please"` 得 0.2。实际运行：轮次永远不提交，并且静音满 500ms 后**每一帧**都打印一行 "SILENCE but score=0.20, waiting"，共 86 行。
- ⚠️ 由于 `synth_call` 的 partial 没有标点，0.95 分支在 `main()` 中从未触发。
- 真实的 LiveKit turn detector 是读 partial 文本的小型 Transformer，学的是"语义上说完了没有"，而不是数词。

### 3.3 `State` 与 `Metrics`

```python
class State(Enum):
    IDLE = auto()
    LISTENING = auto()   # user is mid-utterance
    WAITING = auto()     # VAD says silence, checking turn score
    THINKING = auto()    # LLM streaming but no TTS yet
    SPEAKING = auto()    # TTS streaming out
    TOOL = auto()        # side-channel tool in flight
```

- `auto()` 自动分配枚举值，我们只关心名字。用枚举而不是字符串，可以避免拼写错误。
- `WAITING` 其实是一个**瞬时状态**：进入后在同一帧就转到 `THINKING` 或 `TOOL`（见 3.5）。注释说"checking turn score"，但打分在 LISTENING 分支里就已完成。

```python
@dataclass
class Metrics:
    events: list[str] = field(default_factory=list)
    turn_complete_ms: int = 0
    first_llm_token_ms: int = 0
    first_audio_out_ms: int = 0
    false_cutoffs: int = 0
    barge_ins: int = 0

    def latency_ms(self) -> int:
        if self.turn_complete_ms and self.first_audio_out_ms:
            return self.first_audio_out_ms - self.turn_complete_ms
        return -1
```

- ⚠️ **延迟口径与讲义不一致**：讲义定义 first-audio-out 为"从用户停止说话到第一个音频包离开服务器"，代码从"轮次提交"算起，漏掉了约 480ms 的静音等待。会话 1 打印 740ms，按讲义口径应为 3580 − 2360 = 1220ms。
- ⚠️ `false_cutoffs` 在整个文件中**从未被赋值**，永远是 0。
- ⚠️ 时间戳字段只在"等于 0 时"才写入，所以只记录**第一轮**；多轮对话需要按轮次重置或改成列表。
- 用 `0` 表示"尚未发生"有一个隐患：如果事件真的发生在 0ms 就分不清。更稳妥的是用 `None`。

### 3.4 barge-in 检查（每帧最先执行）

```python
    for f in frames:
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

- 放在循环开头，保证"用户一开口就优先处理"，这与讲义"cancel the TTS stream immediately"一致；`continue` 跳过本帧其余逻辑。
- 取消动作体现为把 `tts_stream_started_at`、`llm_stream_started_at` 置为 −1，对应"丢弃剩余 LLM 输出、停止 TTS"。
- ⚠️ 触发需要调用方**预先给出** `barge_in_at_ms`。会话 1 传入 `None`，于是 barge-in 被完全关闭——用户在 agent 说话时开口会被无视。真实系统中 barge-in 应始终由 VAD 驱动。
- ⚠️ 状态元组不含 `State.TOOL`：工具执行期间用户说话同样被忽略（我们在 2900–3060ms 插入语音帧验证过，事件序列不变）。讲义练习 2 恰好要求设计这种情况的仲裁策略。
- ⚠️ 没有重置 `silence_run_ms`、`tool_started_at`、`filler_emitted`，也没有发出讲义要求的 `tts_canceled` span。

### 3.5 LISTENING → 轮次提交 → WAITING

```python
        if state == State.IDLE:
            if f.is_speech:
                state = State.LISTENING
                m.log(f"{f.t_ms}ms LISTENING")

        elif state == State.LISTENING:
            if f.is_speech:
                silence_run_ms = 0
                final_partial = f.partial or final_partial
            else:
                silence_run_ms += 20
                if silence_run_ms >= 500:
                    score = turn_completion_score(final_partial)
                    if score >= 0.6:
                        state = State.WAITING
                        m.turn_complete_ms = f.t_ms
                        ...
```

- 用户说话时清零静音计数器，并记录最新 partial（`f.partial or final_partial`：partial 为空字符串时保留旧值）。
- 静音帧每帧加 20ms，第 25 个静音帧（2360 + 24 × 20 = **2840ms**）时达到 500，打分 0.75 ≥ 0.6，提交。
- 注意下一段是 **`if state == State.WAITING:`（新的 `if`，不是 `elif`）**，所以提交轮次的同一帧就会继续执行发起 LLM 的逻辑——这是让"提交"和"发起请求"之间零延迟的小技巧。

### 3.6 发起 LLM 与工具：WAITING / TOOL

```python
        if state == State.WAITING:
            llm_stream_started_at = f.t_ms + 140  # simulated time-to-first-token
            state = State.THINKING
            m.log(f"{f.t_ms}ms LLM call fired")
            if use_tool:
                tool_started_at = f.t_ms
                state = State.TOOL

        elif state == State.TOOL:
            if tool_started_at >= 0 and not filler_emitted:
                if f.t_ms - tool_started_at >= 300:
                    filler_emitted = True
                    m.log(f"{f.t_ms}ms filler 'one second, let me check'")
            if tool_started_at >= 0 and f.t_ms - tool_started_at >= WEATHER.latency_ms:
                tool_done_at = f.t_ms
                m.log(f"{f.t_ms}ms tool result: {WEATHER.result}")
                llm_stream_started_at = f.t_ms + 140
                state = State.THINKING
```

- 用"未来时间戳"模拟异步：`llm_stream_started_at = t + 140` 表示 140ms 后首 token 到达；之后的帧比较 `f.t_ms >= llm_stream_started_at` 即可。这是离散事件模拟的常见写法。
- 会话 1：2840 发起；3140 时已过 300ms → filler；3260 时已过 420ms → 工具返回；把首 token 时间改到 3400。
- ⚠️ 简化之处：
  - 是否调用工具由参数 `use_tool` 决定，且在 LLM 产出任何内容之前就发起——真实流程是 LLM 先流式输出一个 tool call，再由调度器执行工具；
  - 名义上"并发"，实际上 LLM 首 token 要等工具返回后再 +140ms，等价于"工具串行阻塞了回答"；
  - filler 只写了日志，没有送入 TTS，也没有更新 `first_audio_out_ms`；
  - 工具超时、失败都没有处理；`tool_done_at` 赋值后从未使用。
- 讲义要求"超过 300ms 才说 filler"，代码用 `>= 300`，边界上略有差别。

### 3.7 THINKING → SPEAKING：首 token 与首音频

```python
        elif state == State.THINKING:
            if llm_stream_started_at > 0 and f.t_ms >= llm_stream_started_at:
                if m.first_llm_token_ms == 0:
                    m.first_llm_token_ms = f.t_ms
                    m.log(f"{f.t_ms}ms LLM first token")
                tts_stream_started_at = f.t_ms + 180
                state = State.SPEAKING

        elif state == State.SPEAKING:
            if tts_stream_started_at > 0 and f.t_ms >= tts_stream_started_at:
                if m.first_audio_out_ms == 0:
                    m.first_audio_out_ms = f.t_ms
                    m.log(f"{f.t_ms}ms TTS first audio-out")
```

- 首 token 一到就把它"交给 TTS"，180ms 后出首个音频，满足讲义"200ms 内"的要求。
- 进入 `SPEAKING` 后就再也不会离开（除非 barge-in）：没有"说完 → 回到 LISTENING/IDLE"的转移，所以一个会话只能完成一轮对话。
- 由于帧粒度是 20ms，所有时间都会被"取整"到帧边界。

### 3.8 `main()`：两个演示会话

```python
    frames = synth_call("tell me a long story about", start_ms=0)
    for i in range(8):
        idx = len(frames) - 20 + i
        if 0 <= idx < len(frames):
            frames[idx] = Frame(t_ms=frames[idx].t_ms, is_speech=True,
                                partial=frames[idx].partial)
    m = run_session(frames, use_tool=False,
                    barge_in_at_ms=frames[-20].t_ms - 60)
```

- 会话 2 共 212 帧，倒数第 20 帧是 `t = 3840ms`；把 3840–3980ms 的 8 帧改成语音，模拟用户开口；`barge_in_at_ms = 3780`。
- `Frame` 没有设置 `frozen=True`，但这里仍然新建对象替换，而不是修改原对象的字段——两种写法都可以。
- 被打断后用户的新语音只有 160ms，之后只剩 240ms 静音，不足 500ms，所以会话结束时没有第二次提交。新语音帧的 partial 仍是旧句子（模拟不够真实）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用模拟帧代替真实音频 | 聚焦调度逻辑，无需音频依赖 | ASR 零延迟、VAD 零误差，看不到真实抖动；生产中接 LiveKit/Pipecat 的音频流 |
| 逐帧同步循环 + "未来时间戳"模拟异步 | 确定、可复现、易于手推 | 真实系统用 asyncio / 事件驱动，各阶段真正并发 |
| 启发式 turn detector | 无模型可用 | 短句永不提交、悬空词抢话；生产用 LiveKit turn detector 等模型 + 自适应静音阈值 + 最长静音兜底 |
| 固定 500ms 静音阈值 | 与讲义一致 | 吃掉约 60% 的 800ms 预算；可用投机生成、自适应端点 |
| 延迟从轮次提交算起 | 只衡量"系统处理"部分 | 与讲义定义不符，低估约 480ms |
| barge-in 由 `barge_in_at_ms` 开关控制 | 便于构造演示 | 默认关闭、不覆盖 TOOL 状态；应始终由 VAD 驱动 |
| filler 只记录日志 | 演示时机 | 真实系统要把 filler 送进 TTS，并计入首音频 |
| 工具在轮次提交时就发起 | 简化 | 真实流程由 LLM 决定是否、何时调用工具 |
| 单轮状态机，SPEAKING 无出口 | 代码短 | 多轮对话需要"播放结束 → LISTENING"的转移和按轮次重置的指标 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许在注解中使用 `int \| None` 等新写法而不在运行时求值 |
| `@dataclass` + 默认值 | `class Frame: partial: str = ""` | 自动生成构造函数；有默认值的字段放后面 |
| `field(default_factory=list)` | `events: list[str] = field(default_factory=list)` | 可变默认值必须用工厂，避免多个实例共享同一个列表 |
| 行尾注释 | `t_ms: int  # timestamp ms since session start` | 给字段写说明 |
| `Enum` + `auto()` | `class State(Enum): IDLE = auto()` | 枚举类型，`auto()` 自动编号 |
| 成员判断 | `state in (State.SPEAKING, State.THINKING)` | 元组成员测试 |
| 联合类型注解 | `barge_in_at_ms: int \| None = None` | 参数可以是 int 或 None（Python 3.10+ 语法） |
| `is not None` | `barge_in_at_ms is not None` | 与 None 比较要用 `is`，不要用 `==` |
| `for _ in range(16)` | `synth_call` 中 | `_` 表示不需要的循环变量 |
| 链式比较的替代写法 | `if 0 <= idx < len(frames):` | Python 支持数学式的连续比较 |
| `str.endswith(tuple)` | `partial.rstrip().endswith(("?", ".", "!"))` | 任一后缀匹配即为真 |
| `.strip()` / `.rstrip()` / `.split()` | `(partial + " " + w).strip()` | 去首尾空白 / 去尾部空白 / 按空白切分 |
| `or` 取默认值 | `f.partial or final_partial` | 左边为空字符串时取右边 |
| `if / elif` 链与独立 `if` | `if state == State.WAITING:` 前没有 `elif` | 独立 `if` 让同一帧内可以连续经过两个状态 |
| `continue` | barge-in 分支末尾 | 跳过本次循环剩余部分 |
| f-string 格式符 | `f"(score={score:.2f})"`、`f"{f.t_ms}ms ..."` | `.2f` 保留两位小数 |
| 负数索引 | `frames[-20]` | 倒数第 20 个元素 |
| `random.random()` / `random.seed` | `random.random() < noise`、`random.seed(0)` | 生成 [0,1) 随机数；固定种子可复现 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，结果完全确定）：

```text
=== session 1: clean call with tool (weather) ===
  120ms LISTENING
  2840ms TURN COMPLETE (score=0.75) partial='what is the weather in tokyo tomorrow'
  2840ms LLM call fired
  3140ms filler 'one second, let me check'
  3260ms tool result: 68/52 partly cloudy
  3400ms LLM first token
  3580ms TTS first audio-out
  turn_complete  @ 2840ms
  first_llm_tok  @ 3400ms
  first_audio_out @ 3580ms
  turn latency   = 740ms

=== session 2: user barges in mid-response ===
  120ms LISTENING
  2520ms TURN COMPLETE (score=0.75) partial='tell me a long story about'
  2520ms LLM call fired
  2660ms LLM first token
  2840ms TTS first audio-out
  3840ms BARGE-IN: cancel TTS, re-arm ASR
  barge_ins = 1
```

逐项解读：

| 时间 | 事件 | 来源 |
|------|------|------|
| 120ms | 第一个语音帧，IDLE → LISTENING | 6 帧前导静音之后 |
| 2360ms | 用户停止说话（日志里没有这一行） | 7 词 × 320ms 结束 |
| 2840ms | 静音满 500ms（第 25 个静音帧），7 个词得 0.75，提交并发起 LLM 与工具 | 3.5、3.6 |
| 3140ms | 工具已运行 300ms，filler | `>= 300` |
| 3260ms | 工具 420ms 返回 | `WEATHER.latency_ms` |
| 3400ms | 首 token = 工具返回 + 140ms | 模拟 TTFT |
| 3580ms | 首音频 = 首 token + 180ms | 模拟 TTS 首块 |

- **740ms 不是讲义口径**：按"用户停止说话 → 首音频"是 1220ms，超出 800ms 目标。拆开看：VAD 等待 480 + 工具 420 + TTFT 140 + TTS 180。如果 filler 真被播出，用户在 3140ms（停止说话后 780ms）就能听到声音。我们另外运行 `use_tool=False`，首音频在 3160ms，即 800ms——静音等待一项就占了 60%。
- **会话 2 的提交本身就是一次抢话**："tell me a long story about" 显然没说完，但 6 个词拿到 0.75 分。演示的本意是展示 barge-in，却顺带展示了启发式 turn detector 的 false cutoff。
- **barge-in 在 3840ms 而不是 3780ms**：`barge_in_at_ms = 3780` 只是"允许触发"的最早时间，真正触发还需要 `is_speech` 为真，插入的语音帧从 3840ms 开始。
- 被打断后没有第二轮：新语音后只剩 240ms 静音，不足 500ms。
- **与讲义 "Use It" 对比**：讲义示例中 TTS 在 1040ms 就说出了工具结果，而工具 1140ms 才返回，时间线自相矛盾；且示例的 1040ms 也超过了讲义自己的 800ms 目标。

---

## 7. 动手改一改

1. **修正延迟口径**：在 `Metrics` 中加入 `user_stop_ms`（LISTENING 分支里第一个静音帧的时间），让 `latency_ms()` 返回"用户停止说话 → 首音频"，确认会话 1 输出 1220ms（测验 Q9）。
2. **让 filler 真正发声**：filler 触发时若 `first_audio_out_ms == 0` 就记录它，并分别报告"首个音频"与"首个实质回答音频"两个指标。
3. **改进 turn detector**：加入悬空词惩罚、短句白名单、最长静音兜底（如 1500ms 无条件提交）与"按分数自适应的静音阈值"；构造讲义练习 3 的"句中长停顿"测试，比较 false cutoff 与延迟（测验 Q10）。
4. **始终开启 barge-in**：去掉 `barge_in_at_ms` 开关，把 `State.TOOL` 加入可打断状态，并在"提交后很快被打断且新 partial 是旧 partial 的延续"时累加 `false_cutoffs`（测验 Q11）。
5. **多轮对话**：给 SPEAKING 加一个"模拟播放时长"，播完回到 LISTENING；把时间戳指标改成每轮一条记录，计算多轮的 p50/p95。
6. **进阶：真正的并发**：用 `asyncio` 重写——VAD/ASR 一个协程、LLM 流一个协程、TTS 一个协程、工具一个任务，用 `asyncio.Event` 或队列通信，barge-in 时 `task.cancel()`。对比两种实现中"取消传播"的难度。

---

## 8. 常见坑

- **延迟口径不统一**：从"轮次提交"、"ASR final"还是"用户停止说话"算起，数字可以差几百毫秒；报告时必须写清起点，并用 p50/p95 而非平均值。
- **turn detector 只数词或只看标点**：真实 ASR partial 的标点可能滞后或缺失；短回答（"yes"）和悬空结尾（"about"）是两个最常见的反例。
- **没有最长等待兜底**：分数一直不过门限时，agent 会永远沉默。
- **barge-in 只停 TTS**：还要停 LLM 流、清空已缓冲的音频、按策略处理工具，并把 assistant 消息截断到实际播放的部分。
- **忽略回声**：没有回声消除时，agent 会被自己的声音"打断"。
- **filler 只做不算**：filler 是降低感知延迟的关键手段，评估时却没计入，导致报告的延迟与用户感受不符。
- **用 0 表示"未发生"**：`if self.turn_complete_ms` 在事件恰好发生在 0ms 时会误判；用 `None` 更安全。
- **每帧重复打分并打印日志**：静音期间每 20ms 调用一次 turn detector 模型，既浪费算力又刷屏；应在 partial 变化或静音跨过阈值时才评估。
