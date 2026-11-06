# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 12 节 构建语音助手管道——第 6 阶段综合项目 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在 `code/` 目录下 `python3 main.py`（docstring 写的是在小节根目录运行 `python3 code/main.py`），无命令行参数，约 0.5 秒（主要是 `time.sleep` 模拟的模型延迟） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`time`）；没有真实的麦克风、模型或网络

---

## 1. 这份代码在考察什么

docstring："Simulates a full user turn: mic → VAD → STT → LLM (with tool-call) → TTS. Prints per-stage latency + decision trace." 这是第 6 阶段的综合项目，把前面各节的组件用桩函数（stub）串成一轮完整的对话：

1. **麦克风流**：用生成器（generator）按 20 ms 一块"实时"产出音频，模拟 `sounddevice` 的回调队列。
2. **VAD 收音**：能量 VAD + 300 ms pre-roll + 400 ms 静音挂起时间，决定一句话从哪开始、到哪结束——讲义"三种故障"中的首字截断就靠 pre-roll 解决。
3. **工具调用**：LLM 返回 `tool_calls` 列表，运行时分发执行（`set_timer`）。
4. **TTS 与播放**：合成返回音频块列表，再逐块播放。
5. **用户感知延迟预算**：把"等待静音挂起"的 400 ms 也算进去，与 800 ms 的目标比较。

> 一句话：**它是一份可运行的架构图**——每个函数对应讲义七个组件中的一个，替换成 Silero / Whisper / GPT-4o / Kokoro 就是一个真实的助手；而它的简化之处（串行、非流式、没有打断）正好是生产中需要补上的部分。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应讲义组件 |
|---------|------|------|------------|
| `mic_generator(duration_s, sr, chunk_ms, speech_mask)` | 生成器函数 | 按 `speech_mask` 逐块产出 320 点的语音/静音噪声，附带真值标签 | 1. 音频采集 |
| `vad(chunk, threshold_dbfs)` | 函数 | RMS 电平高于 −35 dBFS 判为语音 | 2. VAD |
| `streaming_stt(utterance, sr)` | 函数 | `sleep(80 ms + 时长 × 50 ms)`，返回固定转写 | 3. 流式 STT（桩） |
| `llm_with_tools(transcript)` | 函数 | `sleep(120 ms)`；文本含 "timer" 时返回工具调用 + 回复 | 4. LLM + 工具 |
| `dispatch_tool(name, args)` | 函数 | 执行 `set_timer`，返回到期时间戳 | 4. 工具分发 |
| `streaming_tts(text)` | 函数 | `sleep(100 ms)`，按单词切成"音频块"列表 | 5. 流式 TTS（桩） |
| `play(audio_chunks)` | 函数 | 每块 `sleep(20 ms)` | 6. 播放 |
| `main()` | 函数 | Step 1–6：收音、STT、LLM + 工具、TTS + 播放、预算、参考技术栈 | 串联 |

第 7 个组件"打断处理"在代码中**没有实现**（讲义 Use It 说这份代码"wires all seven components"，与实际不符）。

---

## 3. 逐段精讲

### 3.1 `mic_generator`：用生成器模拟音频流

```python
def mic_generator(duration_s=2.0, sr=16000, chunk_ms=20, speech_mask=None):
    rng = random.Random(0)
    n_chunks = int(duration_s * 1000 / chunk_ms)
    if speech_mask is None:
        speech_mask = [False] * 5 + [True] * 60 + [False] * 20
    for i in range(min(n_chunks, len(speech_mask))):
        is_speech = speech_mask[i]
        n = int(sr * chunk_ms / 1000)
        if is_speech:
            chunk = [0.2 * rng.gauss(0, 1.0) for _ in range(n)]
        else:
            chunk = [0.003 * rng.gauss(0, 1.0) for _ in range(n)]
        yield chunk, is_speech
```

- **生成器**：函数里有 `yield`，调用时不会立刻执行，而是返回一个可迭代对象；`for chunk, truth in mic_generator()` 每迭代一次，函数运行到下一个 `yield` 产出一块。这与真实麦克风"一块一块到来"的形态一致，也是讲义 Step 1 `mic_stream` 的写法（那里用 `queue.Queue` 接收 `sounddevice` 回调的数据再 `yield`）。
- `speech_mask=None` 再在函数内赋默认值：这是避免"可变默认参数陷阱"的标准写法（如果写成 `speech_mask=[False]*5 + ...`，这个列表会在所有调用之间共享）。
- 默认掩码：5 块静音（100 ms）+ 60 块语音（1.2 s）+ 20 块静音（400 ms），共 85 块；`duration_s=2.0` 对应 100 块，`min(...)` 取较小值，所以实际只产出 85 块。
- 语音 σ=0.2 → 约 −14 dBFS；静音 σ=0.003 → 约 −50 dBFS；VAD 阈值 −35 dBFS 在中间。
- 同时产出真值标签 `is_speech`，便于评估 VAD 的准确率（`main` 里接收为 `truth`，但没有使用）。
- ⚠️ 生成器是"瞬间"产出的，不像真实麦克风那样每 20 ms 才来一块。所以 Step 1 打印的"in 12 ms wall time"只是生成噪声的耗时，真实收音这一句话需要约 1.7 秒。

### 3.2 `vad`：与第 11 节相同的能量门控

```python
def vad(chunk, threshold_dbfs=-35.0):
    rms = (sum(x * x for x in chunk) / len(chunk)) ** 0.5
    return 20.0 * math.log10(max(rms, 1e-10)) > threshold_dbfs
```

- RMS → dBFS → 与阈值比较，返回布尔值。`max(rms, 1e-10)` 防止对 0 取对数。
- 讲义建议生产中用 Silero VAD（概率阈值 0.5、起始阈值 0.3）。能量 VAD 的阈值单位是 dBFS，Silero 的阈值是 0–1 的语音概率，两者不能混用。

### 3.3 收音循环：pre-roll + 静音挂起（含一个重复 bug）

```python
    buffered = []
    pre_roll = []
    triggered = False
    silent_ms = 0
    turn_start = time.time()
    for chunk, truth in mic_generator():
        pre_roll.append(chunk)
        if len(pre_roll) > 15:
            pre_roll.pop(0)
        if vad(chunk):
            if not triggered:
                for c in pre_roll:
                    buffered.extend(c)
                triggered = True
            buffered.extend(chunk)
            silent_ms = 0
        elif triggered:
            silent_ms += 20
            buffered.extend(chunk)
            if silent_ms >= 400:
                break
```

这是本文件最核心的一段，对应讲义 Step 2 的 `capture_turn`：

- **pre-roll**：`pre_roll` 是最近 15 块（300 ms）的滑动窗口，超过 15 块就 `pop(0)` 丢掉最旧的。VAD 第一次触发时，把窗口里的音频全部放进 `buffered`，这样即使 VAD 判定晚了一点，句首的音频也不会丢——讲义"First-word clip"的标准解法（Key Terms：保留 200–400 ms）。
- **triggered 状态**：`False` 表示还在等用户开口；`True` 之后才开始累计静音。
- **静音挂起**：触发后遇到静音块，`silent_ms += 20` 并继续收音（保留句中停顿）；任何语音块都会把 `silent_ms` 清零；累计到 400 ms 才认为说完、`break`。讲义组件表建议 500 ms，代码用的是 400 ms。
- ⚠️ **bug：触发块被加入两次**。`pre_roll.append(chunk)` 发生在 VAD 判断**之前**，所以第一次触发时 `pre_roll` 已经包含当前块；随后 `buffered.extend(chunk)` 又加了一次。计数：触发时 `pre_roll` 有 6 块（5 块静音 + 触发块），再加触发块 1 次、其余 59 个语音块、20 个静音块，共 86 块 × 320 = **27520** 个采样点，与运行结果一致；正确值应为 85 块 = 27200。讲义 Step 2 的 `capture_turn` 有同样的问题。修复方法：把 `pre_roll.append(chunk)` 移到判断之后（见测验 Q9）。
- ⚠️ 没有实现讲义要求的"最短语音时长 250 ms"，一次短促的噪声也会触发收音。
- ⚠️ `pre_roll` 用列表 + `pop(0)` 实现滑动窗口，`pop(0)` 是 O(n)；用 `collections.deque(maxlen=15)` 更简洁高效（讲义 Step 2 就是这样写的）。
- 末尾 `silent_ms` 停在 400，后面在 Step 5 中被直接当作"端点检测等待"计入延迟。

### 3.4 STT 与 LLM + 工具调用

```python
def streaming_stt(utterance, sr=16000):
    time.sleep(0.08 + len(utterance) / sr * 0.05)
    return "set a timer for five minutes"

def llm_with_tools(transcript):
    time.sleep(0.12)
    if "timer" in transcript:
        return {
            "tool_calls": [{"name": "set_timer", "args": {"seconds": 300}}],
            "text": "Sure, setting a 5 minute timer.",
        }
    return {"tool_calls": [], "text": "OK."}

def dispatch_tool(name, args):
    time.sleep(0.01)
    if name == "set_timer":
        return {"ok": True, "expires_at": time.time() + args["seconds"]}
    return {"ok": False}
```

- `streaming_stt` 名为"流式"，但延迟 = 80 ms + 每秒音频 50 ms，与整句长度成正比——这其实是整句识别的特征。1.72 s 的音频对应 166 ms。
- `llm_with_tools` 返回一个字典：`tool_calls` 是"要调用哪些工具、参数是什么"的列表，`text` 是要说的话。结构与真实 API 的工具调用响应类似（名称 + JSON 参数）。
- `dispatch_tool` 是**运行时分发**：按名字找到对应实现并执行，返回结构化结果。未知工具返回 `{"ok": False}`，给 LLM 留下错误信号。讲义 Pitfalls 要求工具失败时把错误交回 LLM 重试一次，再优雅降级。
- ⚠️ 简化 1：真实流程中，LLM 先返回工具调用，运行时执行后要把结果**再送回 LLM**，由第二次调用生成最终回复（讲义 Step 4 中的 `continue_streaming(result)`）。这里一次就返回了回复文本，省掉了第二次 LLM 往返的延迟。
- ⚠️ 简化 2：工具结果（`expires_at`）只是被打印出来，没有影响回复内容；计时 `t_llm` 也只包住 `llm_with_tools`，`dispatch_tool` 的 10 ms 没有计入预算。
- `if "timer" in transcript` 是关键词路由，用来模拟"LLM 决定调用哪个工具"。

### 3.5 TTS 与播放

```python
def streaming_tts(text):
    time.sleep(0.10)
    return [f"(audio chunk: {word})" for word in text.split()]

def play(audio_chunks):
    for _ in audio_chunks:
        time.sleep(0.02)
```

- `streaming_tts` 用 100 ms 模拟首音延迟（TTFA），然后按单词返回 6 个"音频块"。真实的流式 TTS 是生成器或异步迭代器：第一块合成好就交出去，后面的边合成边播放；这里是一次性返回整个列表，并不流式。
- `play` 每块 20 ms，`t_play` 被测出来但没有打印，也没有进入预算——因为用户感知的是"第一个音频出来的时间"，而不是播完的时间。
- ⚠️ 播放是同步阻塞的：在 `play` 期间程序无法检测用户插话。讲义 Pitfalls："TTS that blocks. Synchronous TTS blocks the event loop."——要实现打断，播放必须放在异步任务或独立线程中，并且可以被取消（讲义 Step 5、测验 Q12）。

### 3.6 Step 5：用户感知延迟预算

```python
    stages = [
        ("VAD + capture (after end-of-speech)", silent_ms),
        ("STT",  t_stt),
        ("LLM + tool",  t_llm),
        ("TTS TTFA",    t_tts_ttfa),
    ]
    total = sum(ms for _, ms in stages)
    for name, ms in stages:
        bar = "#" * int(ms / 10)
        print(f"  {name:<40s} {ms:>6.1f} ms  {bar}")
    print(f"  TOTAL user-perceived (to first audio): {total:.1f} ms   (target: &lt; 800 ms)")
```

- 这里最值得学习的设计是第一行：把 `silent_ms`（400 ms 的静音挂起）计入用户感知延迟。用户停嘴后，系统还要"再听 400 ms 确认没声音了"，这段时间用户是能感觉到的。它是本例中最大的单项，占总延迟的一半。
- `sum(ms for _, ms in stages)` 用生成器表达式求和，`_` 丢弃名字。
- 结果 786.4 ms，刚好低于 800 ms 目标。若按讲义组件表把挂起时间改成 500 ms，总延迟约 886 ms 就会超标。
- ⚠️ 与第 11 节相同的 bug：字符串里写的是 HTML 实体 `&lt;`，终端会原样打印 `&lt;`，应改为 `<`。
- ⚠️ 预算是串行相加的，没有网络、没有第二次 LLM 调用、只测一次（没有 P95）。

### 3.7 Step 6：参考技术栈

```python
    stacks = [
        ("LiveKit + Deepgram + GPT-4o + Cartesia",       "350-500 ms", "industry default"),
        # ...
        ("whisper.cpp + llama.cpp + Kokoro-ONNX",         "offline",    "edge / privacy"),
    ]
    for s, lat, note in stacks:
        print(f"  {s:<46s} {lat:<12s} {note}")
```

- 与讲义表格一致的五套方案：商用默认、DIY 开源、全双工单模型、托管平台、离线边缘。
- 对比本模拟的 786 ms：已经落在 Pipecat 开源栈的 500–800 ms 区间；要进入 350–500 ms，需要真正的流式 STT、更短的端点检测和更快的 LLM 首 token。

### 3.8 `main()` 开头的 `random.seed(0)`

- `main` 中的 `random.seed(0)` 没有实际作用：音频由 `mic_generator` 内部的 `random.Random(0)` 生成，与全局随机状态无关。保留它不会出错，但会误导读者以为有地方用了全局 `random`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 生成器模拟麦克风 | 与真实"逐块到来"的接口一致，可直接替换为 `sounddevice` 队列 | 产出不按实时节奏；真实采集要在回调线程中进行 |
| 能量 VAD（−35 dBFS） | 零依赖、结果确定 | 对噪声敏感；生产用 Silero VAD + 起始/结束双阈值 |
| pre-roll 15 块（300 ms） | 解决首字截断 | 当前实现会重复加入触发块；用 `deque` 并在判断后入队 |
| 静音挂起 400 ms | 容忍句中停顿 | 直接增加每轮延迟；生产叠加语义轮次检测 |
| `sleep` 模拟各模型 | 无需模型即可观察预算 | 串行、无抖动、无长尾 |
| 一次返回工具调用 + 回复 | 代码简洁 | 真实流程有第二次 LLM 调用；需要过渡语、超时、重试 |
| 同步 TTS 与播放 | 流程直观 | 无法打断；生产用 asyncio 任务 / 独立线程并支持取消 |
| 预算计入静音挂起 | 反映真实用户感知 | 仍缺网络、P95、第二次 LLM 调用等项 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 `None` + 函数内赋值 | `speech_mask=None` → `if speech_mask is None: speech_mask = [...]` | 避免可变默认参数在多次调用间共享 |
| 列表乘法与拼接 | `[False] * 5 + [True] * 60 + [False] * 20` | 快速构造掩码 |
| 生成器函数 `yield` | `yield chunk, is_speech` | 惰性地逐块产出数据 |
| 迭代时解包元组 | `for chunk, truth in mic_generator():` | 每次拿到 `(块, 真值)` |
| `min` 防越界 | `range(min(n_chunks, len(speech_mask)))` | 取两个上限中较小的 |
| 列表当队列 | `pre_roll.append(chunk)`、`pre_roll.pop(0)` | 可用但 `pop(0)` 是 O(n)，推荐 `deque` |
| 布尔状态机 | `triggered = False / True`、`silent_ms = 0` | 用几个变量表达"等待开口 → 收音中 → 结束" |
| `if / elif` 嵌套 | `if vad(chunk): ... elif triggered: ...` | 只有触发后才累计静音 |
| 字典与嵌套结构 | `{"tool_calls": [{"name": ..., "args": {...}}], "text": ...}` | 模拟 LLM 的结构化响应 |
| 字典取值 | `response["tool_calls"]`、`call["name"]`、`args["seconds"]` | 按键读取 |
| 子串判断 | `if "timer" in transcript:` | 关键词路由 |
| `time.sleep` / `time.time` | `time.sleep(0.12)`、`(time.time() - t0) * 1000` | 模拟延迟、打点计时（耗时测量更推荐 `perf_counter`） |
| f-string 中的表达式与字典 | `{len(buffered)/16000:.3f}`、`{response['text']!r}` | 内联计算；外层双引号、内层单引号 |
| f-string 对齐 | `{name:<40s}`、`{ms:>6.1f}`、`{s:<46s}` | 左/右对齐并指定宽度 |
| 列表推导 + f-string | `[f"(audio chunk: {word})" for word in text.split()]` | 按单词生成"音频块" |
| `_` 忽略变量 | `for _ in audio_chunks`、`sum(ms for _, ms in stages)` | 不需要的值 |
| 字符串乘法画条形图 | `"#" * int(ms / 10)` | 每 10 ms 一个 `#` |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，总耗时约 0.55 秒）的完整输出：

```text
=== Step 1: capture turn via VAD gating ===
  captured 27520 samples (1.720 s) in 12 ms wall time

=== Step 2: streaming STT ===
  transcript: 'set a timer for five minutes'   stt latency: 166.1 ms

=== Step 3: LLM with tool calling ===
  tool_calls: [{'name': 'set_timer', 'args': {'seconds': 300}}]
  set_timer({'seconds': 300}) → {'ok': True, 'expires_at': 1791761406.6766698}
  reply text: 'Sure, setting a 5 minute timer.'   llm latency: 120.1 ms

=== Step 4: streaming TTS + playback ===
  TTFA: 100.2 ms    audio chunks: 6

=== Step 5: end-to-end budget ===
  VAD + capture (after end-of-speech)       400.0 ms  ########################################
  STT                                       166.1 ms  ################
  LLM + tool                                120.1 ms  ############
  TTS TTFA                                  100.2 ms  ##########
  TOTAL user-perceived (to first audio): 786.4 ms   (target: &lt; 800 ms)

=== Step 6: 2026 reference stacks ===
  LiveKit + Deepgram + GPT-4o + Cartesia         350-500 ms   industry default
  Pipecat + Whisper-stream + GPT-4o + Kokoro     500-800 ms   DIY-friendly
  Moshi (full-duplex single model)               200-300 ms   see lesson 15
  Vapi / Retell (managed)                        300-500 ms   fastest to ship
  whisper.cpp + llama.cpp + Kokoro-ONNX          offline      edge / privacy
```

逐段解读：

- **Step 1**：27520 个采样点 = 1.720 s = 86 块。其中 5 块是 pre-roll 带进来的静音、20 块是挂起期间的静音、60 块语音，再加 1 块重复的触发块（bug）。"12 ms wall time" 只是生成模拟数据的时间，不是真实收音时间。
- **Step 2**：`80 + 1.72 × 50 = 166` ms，与音频长度成正比。
- **Step 3**：关键词 "timer" 触发 `set_timer(300)`，`expires_at` 是"当前 Unix 时间戳 + 300 秒"，每次运行都不同。
- **Step 4**：回复 6 个单词 → 6 个音频块，首音 100 ms。
- **Step 5**：400 + 166 + 120 + 100 ≈ 786 ms，低于 800 ms 的目标，但余量只有十几毫秒；静音挂起是最长的一条。最后一行可以看到 `&lt;` 被原样打印的 bug。
- **Step 6**：参考栈，与讲义一致。

---

## 7. 动手改一改

1. 修复 pre-roll 重复 bug：把 `pre_roll` 换成 `collections.deque(maxlen=15)`，并把入队移到 VAD 判断之后，确认收音变为 27200 个采样点；同时修复 `&lt;`。
2. 加上"最短语音时长 250 ms"：在 `speech_mask` 开头插入 3 个孤立的语音块（模拟咳嗽），确认它们不会触发收音。
3. 把静音挂起改成 500 ms（讲义组件表的值），观察总延迟是否还低于 800 ms，并思考哪个阶段最值得优化。
4. 在 `llm_with_tools` 后增加"把工具结果送回 LLM 再生成回复"的第二次调用（再 `sleep(0.12)`），把 `dispatch_tool` 也纳入计时，重新计算预算；再加一句不等工具结果就先播出的过渡语，看首音时间如何变化。
5. 用 `asyncio` 重写 Step 4：TTS 与播放作为可取消的任务，同时用另一个协程读取 `mic_generator` 的后续块，一旦 VAD 触发就 `cancel()` 播放任务，并只把已播放的单词写入对话历史（参考测验 Q12）。
6. 进阶：按讲义 Use It 的清单，把 `vad` 换成 `silero-vad`、`streaming_stt` 换成 Whisper，在一段录好的 `.wav` 上测量 WER 和端到端延迟（讲义 Exercise 2）。

---

## 8. 常见坑

- **pre-roll 重复触发块**：先入队再判断，会把触发块加两次；讲义 Step 2 的 `capture_turn` 也有这个问题。
- **只统计模型耗时**：静音挂起时间、工具调用后的第二次 LLM 往返、网络都会被用户感知，必须计入预算。
- **"流式"名不副实**：STT 延迟随句长增长、TTS 一次性返回所有块，都说明并非真正的流式。
- **同步播放无法打断**：播放期间无法检测插话；需要异步任务或独立线程，并支持取消。
- **HTML 实体混入代码**：`&lt;` 在 Python 中不会被转义。
- **未使用的变量与全局种子**：`truth`、`t_play`、`random.seed(0)` 都没有实际作用，读代码时不要被它们误导。
