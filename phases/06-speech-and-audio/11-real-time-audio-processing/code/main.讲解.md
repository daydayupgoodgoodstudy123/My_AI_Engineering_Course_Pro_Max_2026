# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 11 节 实时音频处理 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在 `code/` 目录下 `python3 main.py`（docstring 写的是在小节根目录运行 `python3 code/main.py`），无命令行参数，约 0.5 秒（大部分是 `time.sleep` 模拟的模型延迟） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`time`）。同目录还有一个 Rust 版本 `main.rs`（20 ms 帧的增益 + 流式 FIR 基准测试），本文只讲 Python 版

---

## 1. 这份代码在考察什么

docstring："Simulates an audio chunk stream through VAD → STT → LLM → TTS with a latency budget. No real models; tracks timing to show where budget goes." 它要你建立的直觉是：

1. **音频是按固定节拍到来的块（chunk）**：20 ms 一块，16 kHz 下 320 个采样点。
2. **VAD 门控**：用 RMS → dBFS 的能量阈值区分"有人说话"和"静音"，决定什么时候开始/结束收音。
3. **延迟预算**：用 `time.sleep` 模拟 STT、LLM、TTS 首块的耗时，并用墙钟时间实测每个阶段，画出条形图。
4. **生产中的预算分布**：打印一张 2026 年生产系统的分阶段典型延迟表，并给出 sub-500 ms 与 sub-200 ms 的技术栈。

> 一句话：**实时系统的核心不是"算得多快"，而是"每一级占多少毫秒、能不能并行"**；这份代码用最朴素的串行实现把预算摆在你面前，同时也恰好展示了讲义和 skill 文件反对的"整句缓冲"做法。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CHUNK_MS`、`VAD_THRESHOLD_DBFS` | 模块常量 | 20 ms 帧长、−40 dBFS 的 VAD 阈值 | 帧 / VAD 阈值 |
| `rms_dbfs(chunk)` | 函数 | 计算一块音频的均方根电平（dBFS） | 能量 / 响度 |
| `simulate_chunk(is_speech, rng)` | 函数 | 生成 320 点的高斯噪声块：语音 σ=0.15，静音 σ=0.002 | 模拟音频流 |
| `vad(chunk, threshold_dbfs)` | 函数 | 电平高于阈值即判为语音 | 能量 VAD |
| `fake_stt` / `fake_llm` / `fake_tts_first_audio` | 函数 | 用 `time.sleep` 模拟各阶段延迟，返回固定结果 | STT / LLM / TTS（首块） |
| `main()` | 函数 | 生成音频流 → VAD 收音 → 串行调用三阶段并计时 → 打印预算表 | 端到端延迟预算 |

数据流：`simulate_chunk × 95 → chunks` →（VAD 循环）→ `buffered` 采样点 → `fake_stt(时长)` → `fake_llm` → `fake_tts_first_audio`，每一步记录毫秒数存进 `budget` 字典。

---

## 3. 逐段精讲

### 3.1 常量与 `rms_dbfs`：音量的工程单位

```python
CHUNK_MS = 20
VAD_THRESHOLD_DBFS = -40.0


def rms_dbfs(chunk):
    rms = (sum(x * x for x in chunk) / len(chunk)) ** 0.5
    return 20.0 * math.log10(max(rms, 1e-10))
```

- **RMS（均方根）**：`√(Σx² / N)`，衡量一块信号的平均能量。
- **dBFS（相对满幅分贝）**：`20·log10(RMS)`。满幅（振幅 1.0）为 0 dBFS，越安静越负。用对数刻度是因为人耳对响度的感知近似对数，而且音频动态范围很大（第 01、02 节）。
- `max(rms, 1e-10)`：防止全零输入时 `log10(0)` 抛 `ValueError`；此时返回 −200 dBFS。
- 帧长 20 ms 是讲义推荐的"常见选择"，也和 WebRTC Opus 的 20 ms 帧一致。

### 3.2 `simulate_chunk`：用两种幅度的噪声模拟"说话"和"安静"

```python
def simulate_chunk(is_speech, rng):
    n = int(0.001 * CHUNK_MS * 16000)
    if is_speech:
        return [0.15 * rng.gauss(0, 1.0) for _ in range(n)]
    return [0.002 * rng.gauss(0, 1.0) for _ in range(n)]
```

- `n = 0.001 × 20 × 16000 = 320`：毫秒转秒再乘采样率。注意 `0.001 * 20 * 16000` 是浮点运算，结果 320.0，`int()` 转成整数；如果写成 `CHUNK_MS * 16000 // 1000` 可以全程用整数，避免浮点误差导致少一个采样点的风险。
- 语音块 σ=0.15 → 约 −16 dBFS；静音块 σ=0.002 → 约 −54 dBFS（实测 −16.2 与 −54.2）。阈值 −40 dBFS 在两者之间，留有充足余量。
- ⚠️ 刻意简化：真实语音不是白噪声，音量起伏很大，句中有清辅音、停顿；背景也不总是 −54 dBFS 的安静。能量 VAD 遇到 −35 dBFS 的空调噪声就会一直判为"有语音"。讲义推荐生产中用 Silero VAD。
- `rng` 由调用方传入（依赖注入），保证可复现。

### 3.3 VAD 收音循环：简单但"一碰就断"的端点检测

```python
    chunks = [simulate_chunk(True, rng) for _ in range(75)]
    chunks += [simulate_chunk(False, rng) for _ in range(20)]
    # ...
    buffered = []
    in_speech = False
    for c in chunks:
        active = vad(c)
        if active:
            buffered.extend(c)
            in_speech = True
        elif in_speech and len(buffered) >= 16000 * 0.3:
            break
    print(f"  buffered {len(buffered) / 16000:.3f} s of speech")
```

- 音频流：75 块语音（1.5 s）+ 20 块静音（0.4 s），共 95 块 = 1900 ms。
- 循环逻辑：语音块就追加到 `buffered`；遇到静音块时，如果已经进入过语音状态并且缓冲 ≥ 0.3 s（4800 个采样点），就认为"一句话说完了"，`break`。
- `in_speech` 是一个**状态标志**：防止开头的静音（还没开始说话）触发结束。
- ⚠️ 没有静音挂起时间（hang-over）：只要出现**一个** 20 ms 的静音块就结束。真实说话中的换气、词间停顿都会把句子切断。测验 Q10 的实测：对"0.5 s 语音 + 0.1 s 停顿 + 0.5 s 语音"，这段代码只收到 0.5 s；加 300 ms 挂起时间后能完整收到 1.1 s。skill 文件示例的参数是"min speech 220 ms、silence hang-over 400 ms"。
- ⚠️ 这里把**整句话缓冲完**才往下走，这正是 skill 文件拒绝的做法："Refuse deploys that buffer entire utterances before STT"。真实流式系统会边收音边把每个 chunk 推给流式 ASR。
- 讲义 Step 1 介绍的 ring buffer 在这份代码中并没有出现，`buffered` 只是一个不断增长的普通列表（讲义 Exercise 1 说本脚本"模拟 ring buffer + 能量 VAD、10 秒的流"，与实际代码不符：这里没有 ring buffer，流长 1.9 秒）。

### 3.4 三个假模型：用 `sleep` 表示延迟

```python
def fake_stt(utterance_duration_s):
    latency_ms = 80 + utterance_duration_s * 50
    time.sleep(latency_ms / 1000.0)
    return "hello world"

def fake_llm(text):
    time.sleep(0.15)
    return "sure, one second"

def fake_tts_first_audio(text):
    time.sleep(0.10)
    return "(audio chunk)"
```

- `fake_stt` 的延迟 = 80 ms 固定开销 + 每秒音频 50 ms：**与句子长度成正比**，这是"整句送 ASR"的典型特征。1.5 s → 155 ms；6 s → 380 ms。
- `fake_llm` 固定 150 ms，可理解为"首 token 延迟"；`fake_tts_first_audio` 固定 100 ms，即 TTS 的 TTFA（time to first audio，首音延迟），与讲义预算表的"TTS (first chunk) 100 ms"一致。
- 三个函数的参数 `text` 都没被使用，返回值也是固定字符串——它们只负责"占用时间"。
- `time.sleep` 的实际时长会略长于请求值（操作系统调度），所以测出来是 155.3、150.1、100.2 ms 这样的数。

### 3.5 计时与条形图：分阶段测量

```python
    budget = {}
    t = time.time()

    t0 = time.time()
    text = fake_stt(len(buffered) / 16000.0)
    budget["STT"] = (time.time() - t0) * 1000
    # ... LLM、TTS TTFA 同理
    total = (time.time() - t) * 1000
    # ...
    for stage, ms in budget.items():
        bar = "#" * int(ms / 10)
        print(f"    {stage:<10s}  {ms:>6.1f} ms  {bar}")
    print(f"  end-to-end: {total:.1f} ms   (target: &lt; 500 ms)")
```

- 每个阶段前记 `t0`，结束后用差值乘 1000 转成毫秒，存入字典；`t` 记录整体起点。这是最朴素的"分阶段打点"，生产中会换成 tracing（如 OpenTelemetry span）并统计 P50/P95/P99（skill 文件要求）。
- 条形图：每 10 ms 一个 `#`，一眼看出 STT 和 LLM 是大头。
- `time.time()` 是墙钟时间，可能受系统时钟调整影响；测量耗时更推荐 `time.perf_counter()`（单调、高精度）。
- ⚠️ **bug**：最后一行字符串里写的是 HTML 实体 `&lt;`，Python 不会把它转成 `<`，终端上会原样打印 `(target: &lt; 500 ms)`。应改为 `(target: < 500 ms)`。
- ⚠️ 这里的 end-to-end 是**严格串行**之和（约 405 ms），而且没有包含用户说话的 1.5 秒和端点检测等待的静音时间。真实流式系统里 STT 与说话并行，LLM 的前几个 token 一到就送 TTS，三段会大量重叠。

### 3.6 Step 4：生产系统的预算分布

```python
    rows = [
        ("network in",  "50-100"),
        ("VAD",          "20-80"),
        ("STT stream",   "100-300"),
        ("LLM stream",   "100-500"),
        ("TTS TTFA",     "100-300"),
        ("network out",  "50-100"),
        ("TOTAL",        "400-1400"),
    ]
```

- 与讲义开头的预算表（总计约 400 ms）相比，这张表多了上下行网络，并且给的是范围：最乐观 400 ms、最差 1400 ms。范围上下限分别相加正好是 420 和 1380，`TOTAL` 写成了取整后的 400–1400。
- VAD 这里写 20–80 ms，而讲义预算表写 10 ms：前者更接近"包含判定等待"的实际开销，后者是模型本身的推理时间。读表时注意口径。
- 最后两行给出两类架构：sub-500 ms 的级联栈（LiveKit + Silero + Deepgram + GPT-4o + Cartesia），以及 sub-200 ms 的全双工端到端模型（Moshi、Sesame CSM，第 15 节）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 高斯噪声模拟语音/静音 | 电平可控，VAD 结果确定 | 真实语音与噪声的区分远难于此；生产用 Silero 等模型 VAD |
| 能量阈值 VAD（−40 dBFS） | 一行公式，便于理解 dBFS | 对背景噪声敏感；需要自适应噪声底或模型 VAD |
| 遇到第一个静音块就结束 | 代码最短 | 句中停顿会切断句子；生产需要 hang-over + 最短语音时长 + 语义轮次检测 |
| 整句缓冲后再 STT | 流程直观 | 延迟随句长增长；生产用流式 ASR 边说边转 |
| `time.sleep` 模拟模型 | 无需任何模型即可观察预算 | 只能演示串行耗时，无法体现并行和抖动 |
| 三阶段严格串行 | 计时简单 | 生产中用异步流水线让阶段重叠 |
| `time.time()` 打点 | 标准库直接可用 | 应使用 `perf_counter()`；生产用 tracing + 分位数统计 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `CHUNK_MS = 20`、`VAD_THRESHOLD_DBFS = -40.0` | 全大写命名表示"不应修改的配置" |
| 默认参数引用常量 | `def vad(chunk, threshold_dbfs=VAD_THRESHOLD_DBFS)` | 默认值在函数定义时求值一次 |
| 生成器表达式 + 幂运算 | `(sum(x * x for x in chunk) / len(chunk)) ** 0.5` | 求均方根 |
| `math.log10` | `20.0 * math.log10(max(rms, 1e-10))` | 常用对数，转换为分贝 |
| `max` 做下限保护 | `max(rms, 1e-10)` | 防止对 0 取对数 |
| 列表推导 | `[simulate_chunk(True, rng) for _ in range(75)]` | 批量生成 |
| `+=` 拼接列表 | `chunks += [...]` | 原地扩展列表 |
| `list.extend` | `buffered.extend(c)` | 把一块的所有采样点追加进去 |
| 布尔状态标志 | `in_speech = False ... in_speech = True` | 记录"是否已经开始说话" |
| `if / elif` + `break` | `elif in_speech and len(buffered) >= 16000 * 0.3: break` | 条件满足时提前退出循环 |
| `time.sleep` / `time.time` | `time.sleep(0.15)`、`(time.time() - t0) * 1000` | 暂停指定秒数；读取当前时间戳 |
| 字典记录结果 | `budget["STT"] = ...`；`for stage, ms in budget.items()` | 字典保持插入顺序，打印顺序与执行顺序一致 |
| 字符串乘法 | `"#" * int(ms / 10)` | 画文本条形图 |
| f-string 格式符 | `{stage:<10s}`、`{ms:>6.1f}`、`{len(buffered) / 16000:.3f}` | `s` 表示字符串类型，`<10` 左对齐；`>6.1f` 右对齐 1 位小数 |
| `!r` | `{text!r}` | 用 `repr` 显示，带引号 |
| `random.seed` vs `random.Random` | `random.seed(0)`；`rng = random.Random(0)` | 本文件真正使用的是局部 `rng`，`random.seed(0)` 没有实际作用 |

---

## 6. 运行结果解读

实际运行（Python 3.13，总耗时约 0.45 秒）的完整输出：

```text
=== Step 1: simulate 1.5 s of user speech as 20 ms chunks ===
  generated 95 chunks, 20 ms each = 1900 ms

=== Step 2: VAD-gate and buffer speech ===
  buffered 1.500 s of speech

=== Step 3: simulate STT / LLM / TTS with timing ===
  user said: 'hello world'
  agent replied: 'sure, one second'

  latency breakdown:
    STT          155.3 ms  ###############
    LLM          150.1 ms  ###############
    TTS TTFA     100.2 ms  ##########
  end-to-end: 405.6 ms   (target: &lt; 500 ms)

=== Step 4: where the 2026 production budget goes ===
  | stage           | typical ms |
  | network in      |     50-100 |
  | VAD             |      20-80 |
  | STT stream      |    100-300 |
  | LLM stream      |    100-500 |
  | TTS TTFA        |    100-300 |
  | network out     |     50-100 |
  | TOTAL           |   400-1400 |

  sub-500 ms: LiveKit + Silero + Deepgram + GPT-4o + Cartesia
  sub-200 ms: Moshi (full-duplex) or Sesame CSM — different architecture (see lesson 15)
```

逐段解读：

- **Step 1**：75 + 20 = 95 块 × 20 ms = 1900 ms。
- **Step 2**：75 个语音块全部通过 VAD（1.500 s），第一个静音块到来时缓冲已超过 0.3 s，循环结束。因为模拟的语音中间没有停顿，"一碰就断"的问题没有暴露。
- **Step 3**：STT = 80 + 1.5 × 50 = 155 ms，LLM 150 ms，TTS 100 ms，合计约 405 ms，低于 500 ms 的目标。如果用户说 6 秒，STT 变成 380 ms，总计约 630 ms 就超标了——整句缓冲的代价。最后一行可以看到 `&lt;` 被原样打印的 bug。
- **Step 4**：生产预算表，`TOTAL` 的范围说明：同样的架构，选型和网络条件不同，可以相差三倍以上。

---

## 7. 动手改一改

1. 修复 `&lt;` bug；把所有 `time.time()` 换成 `time.perf_counter()`。
2. 给 VAD 循环加入 300 ms 的静音挂起时间和 200 ms 的最短语音时长，再在语音中间插入 5 个静音块，验证句子不会被切断（参考测验 Q10）。
3. 把背景噪声的 σ 从 0.002 调到 0.02（约 −34 dBFS），观察 VAD 的行为；再实现"前 10 块估计噪声底，阈值 = 噪声底 + 15 dB"的自适应 VAD。
4. 用 `collections.deque(maxlen=...)` 实现讲义 Step 1 的 ring buffer，让 VAD 循环从 ring buffer 中按 320 点读取，并统计溢出丢弃的样本数。
5. 用 `asyncio` 改写 Step 3：STT 每收到一个 chunk 就"部分转写"，LLM 在拿到最终文本后以每 20 ms 一个 token 的速度流式输出，TTS 在收到前 5 个 token 后开始，测量"用户停止说话 → 第一个音频块"的时间。
6. 进阶：编译运行 `main.rs`（`rustc --edition 2021 -O main.rs`），对比 Rust 单帧 DSP 的 P99 耗时与 20 ms 帧预算，理解 headroom（余量）的含义。

---

## 8. 常见坑

- **HTML 实体混入代码**：`&lt;` 在 Python 字符串中不会被转义，会原样输出。
- **没有 hang-over 的端点检测**：一个 20 ms 的停顿就结束整句，用户会被频繁"抢话"。
- **整句缓冲后再识别**：延迟随句长增长，是 skill 文件明确拒绝的做法。
- **用平均延迟评估**：一次测量或平均值掩盖长尾，应统计每个阶段的 P95 / P99。
- **用 `time.time()` 测耗时**：受系统时钟调整影响，用 `time.perf_counter()`。
- **能量 VAD 遇到稳定噪声**：背景噪声超过阈值时 VAD 永远"在说话"，端点永远不触发。
