# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 15 节 Streaming 语音到语音 — Moshi、Hibiki 和全双工对话 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`time`），不需要 moshi / torch / GPU

---

## 1. 这份代码在考察什么

Moshi 是一个 7B 级别的模型，真要跑需要 GPU 和模型权重。这份脚本把所有"真货"都换成了几行占位函数，**只保留架构的形状**，让你看清：

1. **三条流**：用户的 Mimi token 流（输入）、Moshi 自己的 Mimi token 流（输出）、Moshi 的文本流（inner monologue）是如何随时间步一起增长的。
2. **每个 80 ms 步里的顺序**：编码用户帧 → 预测文本 token → 预测 8 个码本 → 解码成音频。
3. **条件依赖靠 append 顺序表达**：在什么时刻把什么东西放进历史列表，就决定了"谁能看到谁"——这和讲义 Step 3 的训练目标一一对应。
4. **实时约束**：每帧代表 80 ms 音频，处理一帧必须少于 80 ms，否则就会越积越多、跟不上。
5. **全景对照**：最后打印 2026 年主流流式语音到语音（S2S）模型的延迟与许可对照表。

> 一句话：**全双工 = 每 80 ms 一步的"吃一帧用户音频、吐一帧自己的音频（先想文本）"循环**；看懂这个循环的数据依赖，就看懂了 Moshi 的骨架。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `FRAME_MS = 80`、`CODEBOOKS = 8`、`SAMPLE_RATE = 24000` | 模块常量 | 帧长、码本数、采样率 | Mimi：12.5 Hz（80 ms/帧）× 8 码本，24 kHz |
| `fake_mimi_encode(audio_80ms)` | 函数 | 把一帧音频变成 8 个 0–1023 的整数 | Mimi 编码器（占位） |
| `fake_mimi_decode(tokens)` | 函数 | 把 8 个整数变回 1920 个样本的正弦波 | Mimi 解码器（占位） |
| `depth_transformer(context_text, context_user_mimi, context_moshi_mimi)` | 函数 | 睡 3 ms，返回 8 个伪随机码本 | Temporal + Depth Transformer 的音频头（占位） |
| `inner_monologue_next_token(text_so_far, user_mimi_stream)` | 函数 | 睡 2 ms，返回 `"tok_N"` | 文本流 / inner monologue（占位） |
| `simulate_user_speech(n_frames)` | 函数 | 生成 n 帧扫频正弦，模拟用户说话 | 麦克风输入 |
| `main()` | 演示入口 | 25 帧主循环 → 打印流长度、每帧耗时、模型对照表 | — |

数据流（每个时间步 t）：`user_chunk → fake_mimi_encode → user_mimi.append` → `inner_monologue_next_token → moshi_text.append` → `depth_transformer → moshi_mimi.append` → `fake_mimi_decode → out_audio`，并用 `time.time()` 计时。

---

## 3. 逐段精讲

### 3.1 常量：把 Mimi 的规格写死在顶部

```python
FRAME_MS = 80
CODEBOOKS = 8
SAMPLE_RATE = 24000
```

- `80 ms` 一帧 = 每秒 12.5 帧，正是第 13 节讲的 Mimi 帧率；`8` 个码本也是 Mimi 的配置。
- 24 kHz 下一帧有 `24000 × 80 / 1000 = 1920` 个样本，后面多处用 `int(SAMPLE_RATE * FRAME_MS / 1000)` 计算它。
- 全大写命名是 Python 约定的"常量"写法（语言本身并不阻止修改）。集中定义的好处是：想模拟别的 codec，只改这三行即可。

### 3.2 占位编解码器

```python
def fake_mimi_encode(audio_80ms):
    s = sum(abs(x) for x in audio_80ms) / max(1, len(audio_80ms))
    rng = random.Random(int(s * 1000))
    return [rng.randint(0, 1023) for _ in range(CODEBOOKS)]


def fake_mimi_decode(tokens):
    s = sum(tokens) / (1024.0 * CODEBOOKS)
    n = int(SAMPLE_RATE * FRAME_MS / 1000)
    return [0.1 * s * math.sin(2.0 * math.pi * 220.0 * i / SAMPLE_RATE) for i in range(n)]
```

- **编码**：算出这一帧的平均绝对幅度 `s`，用 `int(s * 1000)` 当随机种子，生成 8 个 0–1023 的整数——形状与真实 Mimi 一致：每帧 8 个码本、每个码本 1024 种取值。
- `max(1, len(...))` 防止空帧时除以 0。
- **解码**：把 8 个 token 的均值归一化到 [0, 1)，当作 220 Hz 正弦的幅度（最大约 0.1），输出 1920 个样本。形状正确（一帧进、一帧出），内容没有意义。
- ⚠️ **编码器几乎是"常数"**：`simulate_user_speech` 生成的每一帧幅度都是 0.15，`mean(|0.15·sin|) ≈ 0.15 × 2/π ≈ 0.0955`，与频率几乎无关，所以 25 帧的种子全是 `95`，**25 帧用户音频被编码成了完全相同的 8 个 token**（实测只有 1 种组合）。对本脚本的目的（演示结构和计时）没有影响，但如果你想在此基础上做"模型对用户输入做出反应"的实验，必须先换一个对内容敏感的编码方式（测验 Q10 给出了用 `hashlib` 的写法）。
- ⚠️ 真实 Mimi 是学出来的卷积 + Transformer 编码器 + RVQ，码本 0 还被蒸馏成语义码本；这里完全没有这些。

### 3.3 两个"模型"占位函数

```python
def depth_transformer(context_text, context_user_mimi, context_moshi_mimi):
    time.sleep(0.003)
    rng = random.Random(len(context_user_mimi) + len(context_moshi_mimi))
    return [rng.randint(0, 1023) for _ in range(CODEBOOKS)]


def inner_monologue_next_token(text_so_far, user_mimi_stream):
    time.sleep(0.002)
    return f"tok_{len(text_so_far)}"
```

- **签名才是重点**：`depth_transformer` 接收三条流的历史，`inner_monologue_next_token` 接收已说的文本和用户音频——这表达了"谁以谁为条件"。函数体只是占位。
- `time.sleep(0.003)` / `time.sleep(0.002)` 模拟推理耗时：音频头 3 ms、文本头 2 ms。所以第 6 节测到的每帧约 5–6 ms，绝大部分就是这 5 ms 的睡眠。
- `random.Random(len(...) + len(...))`：用历史长度当种子，第 t 步的种子是 `(t+1) + t = 2t+1`，保证输出可复现、每步不同。
- `f"tok_{len(text_so_far)}"`：第 t 步返回 `tok_t`，方便你一眼看出文本流和时间步对齐。
- ⚠️ 命名上的简化：真实 Moshi 中，**大的 Temporal Transformer**（7B）每 80 ms 走一步、汇总三条流的历史，然后由**小的 Depth Transformer** 在帧内顺序预测 8 个码本（讲义："A small 2-layer 'depth transformer' predicts them sequentially within 80 ms"）。这里把两者合并成了一个叫 `depth_transformer` 的函数，并且 8 个码本是一次性生成的，没有体现"帧内逐码本顺序预测"。
- ⚠️ `context_text` 参数没有被使用；`user_mimi_stream` 也没有被使用。

### 3.4 模拟用户说话

```python
def simulate_user_speech(n_frames):
    audio = []
    for i in range(n_frames):
        chunk = [0.15 * math.sin(2 * math.pi * (220 + 20 * i) * j / SAMPLE_RATE) for j in range(int(SAMPLE_RATE * FRAME_MS / 1000))]
        audio.append(chunk)
    return audio
```

- 返回一个"帧的列表"：第 i 帧是频率 `220 + 20i` Hz、幅度 0.15 的正弦，共 1920 个样本。25 帧 = 2 秒，频率从 220 Hz 扫到 700 Hz。
- 一次性生成全部帧，再在主循环里逐帧消费——这是对"麦克风每 80 ms 推来一帧"的离线模拟。真实系统里帧是**随时间到达**的（讲义 Step 2 用 `async for chunk_80ms in mic_stream_at_12_5_hz()`）。
- ⚠️ 每帧的相位都从 `j = 0` 重新开始，帧与帧之间的波形不连续（会有"咔嗒"声），对占位数据无所谓。

### 3.5 主循环：一步 = 80 ms

```python
    for t, user_chunk in enumerate(user_audio_stream):
        frame_start = time.time()

        user_tokens = fake_mimi_encode(user_chunk)
        user_mimi.append(user_tokens)

        next_text = inner_monologue_next_token(moshi_text, user_mimi)
        moshi_text.append(next_text)

        next_moshi_tokens = depth_transformer(
            context_text=moshi_text,
            context_user_mimi=user_mimi,
            context_moshi_mimi=moshi_mimi,
        )
        moshi_mimi.append(next_moshi_tokens)

        out_audio = fake_mimi_decode(next_moshi_tokens)
        frame_ms = (time.time() - frame_start) * 1000
        per_frame_ms.append(frame_ms)
```

这是全文件最重要的十几行。**append 的先后顺序**精确地编码了讲义 Step 3 的训练目标：

| 调用时刻 | 此时各列表包含的下标 | 讲义 Step 3 |
|---------|-------------------|------------|
| 调 `inner_monologue_next_token` | `user_mimi[0..t]`、`moshi_text[0..t-1]` | 用 `user_mimi[0..t]`、`moshi_text[0..t-1]` 预测 `moshi_text[t]` |
| 调 `depth_transformer` | `user_mimi[0..t]`、`moshi_text[0..t]`、`moshi_mimi[0..t-1]` | 先有 `moshi_text[t]`，再预测 `moshi_mimi[t, 0..7]` |

- **先文本后音频**：`moshi_text.append(next_text)` 写在 `depth_transformer` 调用之前，所以音频头能看到本步的文本 token——这就是 inner monologue "先想好说什么再发声"的含义。
- **用户音频 `[0..t]`、自己的音频 `[0..t-1]`**：模型能听到用户的最新一帧，但自己这一帧还没说出来，当然不能以它为条件——这就是自回归。
- **全双工体现在哪里**：每一步都**同时**有输入（用户帧）和输出（Moshi 帧），不存在"等用户说完再回答"的阶段。用户说话时 Moshi 也在输出 token（可能是沉默、附和或自己的话），这正是它能插话、能被打断、能"mhm"的基础。
- 关键字参数调用 `depth_transformer(context_text=..., ...)`：参数多、含义相近时，用关键字传参能避免顺序写错。
- `out_audio` 只解码、没有播放，也没有被后续使用——真实客户端会把它送往扬声器（讲义 Step 2 的 `await play(audio)`）。
- ⚠️ 没有模拟讲义说的 **80 ms 声学延迟**（理论延迟 160 ms 中的第二个 80 ms）：这里第 t 帧的 8 个码本在第 t 步一次性生成。
- ⚠️ 这是**同步的单线程循环**，"同时"只是逻辑上的。真实部署是讲义 Step 1/2 的形态：`asyncio` 里麦克风上行和扬声器下行两个任务并发运行，用 WebSocket 双向收发 80 ms 的 Mimi 帧。

### 3.6 统计每帧延迟

```python
    avg = sum(per_frame_ms) / len(per_frame_ms)
    p95 = sorted(per_frame_ms)[int(len(per_frame_ms) * 0.95)]
    print(f"  mean: {avg:.2f} ms   p95: {p95:.2f} ms   target: &lt; 80 ms per frame (realtime)")
```

- **P95** 的算法：排序后取第 `int(25 × 0.95) = 23` 个元素（从 0 计），即第 24 小的值。这是"最近秩法"的一种简单近似；样本只有 25 个时，P95 基本就是次大值。实际工程中会用 `statistics.quantiles` 或 NumPy 的 `percentile`。
- 为什么看 P95 而不只看均值：实时音频关心的是**最坏情况**——只要有一帧处理超过 80 ms，播放就会卡顿或需要更大的缓冲。
- ⚠️ 字符串里的 `&lt;` 是 HTML 实体，Python 不会把它转成 `<`，终端上会原样打印 `&lt; 80 ms`（见第 6 节）。应写成 `< 80 ms`。
- ⚠️ 计时用的是 `time.time()`（墙上时钟，可能被系统校时调整）；测量时间间隔更推荐 `time.perf_counter()`（单调、高精度）。

### 3.7 模型对照表与 takeaways

```python
    rows = [
        ("Moshi (Kyutai)",       "200 ms L4",   "full-duplex dialogue, EN+FR",    "CC-BY 4.0"),
        ("Hibiki",                "12.5 Hz",    "EN↔FR streaming translation",   "CC-BY 4.0"),
        # ...
        ("GPT-4o Realtime",        "~300 ms",     "closed, API",                   "commercial"),
        ("Gemini 2.5 Live",       "~350 ms",     "closed, API",                   "commercial"),
    ]
```

- 硬编码自讲义的"2026 performance numbers"表。注意 Hibiki 一栏填的是帧率 12.5 Hz 而非延迟，和其他行的"延迟"列不是同一种量。
- takeaways 中的 "160 ms theoretical latency floor (80 ms frame + 80 ms acoustic delay)" 就是讲义的延迟账本；"pipelines (lesson 12) still win for tool-use" 对应讲义"Moshi does not win: Tool calling"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用占位函数代替模型 | 零依赖、零 GPU，突出数据流 | 输出没有语义；生产用 `moshi` 包 + GPU 推理服务 |
| 用 append 顺序表达条件依赖 | 和训练目标的 `[0..t]` / `[0..t-1]` 一一对应，直观 | 真实模型用因果 mask 和 KV cache 实现同样的依赖 |
| 合并 Temporal 与 Depth Transformer | 代码更短 | 丢失了"帧内逐码本顺序预测"这一关键结构 |
| `time.sleep` 模拟推理耗时 | 让延迟统计有可观察的数字 | 测出的是设定值；真实延迟取决于模型规模与硬件 |
| 同步单线程循环 | 易读、易调试 | 真实系统用 asyncio / Rust futures 双向并发流式收发 |
| 每帧固定 8 个码本一次生成 | 省略声学延迟 | Moshi 中声学 token 相对语义延迟一帧，构成 160 ms 理论下限的一半 |
| 统计 mean + P95 | 实时系统关注尾延迟 | 生产中还会看 P99、抖动，以及端到端（用户停 → Moshi 开口）延迟 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `FRAME_MS = 80` | 全大写表示"约定不改"的常量 |
| 生成器表达式 | `sum(abs(x) for x in audio_80ms)` | 求和时不建中间列表 |
| 列表推导式 | `[rng.randint(0, 1023) for _ in range(CODEBOOKS)]` | 生成 8 个随机整数 |
| 嵌套推导式（在循环中） | `[0.15 * math.sin(...) for j in range(...)]` | 生成一帧的 1920 个样本 |
| `random.Random(seed)` | `random.Random(int(s * 1000))` | 独立随机数生成器；相同种子 → 相同序列 |
| `rng.randint(a, b)` | `rng.randint(0, 1023)` | 闭区间 [a, b] 的随机整数（包含 1023） |
| `time.sleep` | `time.sleep(0.003)` | 阻塞当前线程指定秒数 |
| `time.time()` 计时 | `(time.time() - frame_start) * 1000` | 秒 → 毫秒；测间隔更推荐 `time.perf_counter()` |
| `enumerate` | `for t, user_chunk in enumerate(user_audio_stream)` | 同时取时间步下标和帧 |
| 关键字参数调用 | `depth_transformer(context_text=moshi_text, ...)` | 按名字传参，可读、不怕顺序错 |
| 切片 | `moshi_text[:5]` | 取前 5 个元素 |
| `sorted` + 下标 | `sorted(per_frame_ms)[int(len(per_frame_ms) * 0.95)]` | 返回新列表（不改原列表），再按位置取分位数 |
| f-string 格式符 | `{avg:.2f}`、`{name:<20}`、`{len(user_audio_stream)*FRAME_MS}` | 保留 2 位小数、左对齐宽度 20、花括号内可写表达式 |
| 多元组解包 | `for name, lat, desc, lic in rows` | 一次拆出 4 个字段 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（约 0.2 秒）的输出：

```text
=== Moshi-style full-duplex simulation — 80 ms frames, 8 codebooks ===

processed 25 frames (2000 ms wall audio)
  user_mimi:    25 × 8 codebooks
  moshi_mimi:   25 × 8 codebooks
  moshi_text:   25 tokens   (first 5: ['tok_0', 'tok_1', 'tok_2', 'tok_3', 'tok_4'])

=== per-frame latency ===
  mean: 5.84 ms   p95: 6.46 ms   target: &lt; 80 ms per frame (realtime)

=== 2026 streaming S2S model cheatsheet ===
  | model                | latency   | description                     | license      |
  | Moshi (Kyutai)       | 200 ms L4 | full-duplex dialogue, EN+FR     | CC-BY 4.0    |
  | Hibiki               | 12.5 Hz   | EN↔FR streaming translation     | CC-BY 4.0    |
  | Hibiki-Zero (Feb 26) | 12.5 Hz   | 5 langs, no aligned data        | CC-BY 4.0    |
  | Sesame CSM-1B        | 200 ms    | context-TTS (not full duplex)   | Apache-2.0   |
  | GPT-4o Realtime      | ~300 ms   | closed, API                     | commercial   |
  | Gemini 2.5 Live      | ~350 ms   | closed, API                     | commercial   |
```

逐行解读：

- **25 帧 = 2000 ms**：25 × 80 ms。三条流长度相同（25），说明每一步都**同时**消费一帧用户音频、产出一帧 Moshi 音频和一个文本 token——三条流在时间上严格对齐，这就是"并行流"的含义。
- **user_mimi / moshi_mimi 都是 25 × 8**：每帧 8 个码本。按 12.5 Hz × 8 计，两路音频每秒合计 200 个 token。
- **moshi_text 为 `tok_0 … tok_4`**：文本 token 的编号等于时间步，确认每步恰好生成一个文本 token。
- **mean ≈ 5.8 ms，P95 ≈ 6.5 ms**（每次运行会有小幅波动）：其中 5 ms 是两个 `time.sleep`，其余是纯 Python 编解码循环。离 80 ms 的实时预算还很远，实时因子约 0.07。真实 Moshi 在 L4 上的预算就紧张得多——这也是一张卡只能承载少量会话的原因。
- **`&lt; 80 ms`**：HTML 实体被原样打印，属于源码里的小瑕疵（本意是 `< 80 ms`）。
- **对照表**：Moshi 200 ms、Sesame CSM 200 ms（TTFA）、GPT-4o Realtime 约 300 ms、Gemini 2.5 Live 约 350 ms；Hibiki 两行写的是帧率而不是延迟，阅读时注意区分。

---

## 7. 动手改一改

1. **修两个小瑕疵**：把 `&lt;` 改成 `<`；把 `time.time()` 换成 `time.perf_counter()`，比较统计结果是否更稳定。
2. **让编码器对内容敏感**：用 `hashlib.sha256` 对量化后的样本求摘要来生成 8 个 token，确认 25 帧得到 25 种不同组合（参考测验 Q10）。
3. **拆出 Depth Transformer**：新增 `temporal_step(...)` 返回一个"上下文向量"（比如一个整数），再写 `depth_step(context, prev_codes)` 循环 8 次、每次生成一个码本，体会"帧内顺序预测"。
4. **模拟 80 ms 声学延迟**：第 t 步只生成本帧的码本 0 和上一帧的码本 1–7，第 t 帧要到第 t+1 步才能解码；统计"第一帧可播放音频"相对开始的时间（应为 2 帧 = 160 ms 的音频时间）。
5. **压力测试实时预算**：把两个 `time.sleep` 调大到合计 90 ms，观察 P95 超过 80 ms；再加一个"积压帧数"计数器，看延迟如何随时间累积。
6. **（进阶）改成 asyncio 全双工**：用 `asyncio.Queue` 做麦克风队列，一个协程每 80 ms 放入一帧，另一个协程取帧、推理并"播放"，用 `asyncio.gather` 同时运行（对照讲义 Step 1/2）。

---

## 8. 常见坑

- **把占位耗时当真实性能**：5–6 ms 的"每帧延迟"大部分是 `time.sleep` 设定的，不能拿来评估 Moshi。
- **append 顺序写错**：把文本 append 挪到音频生成之后，或在推理前就 append 本帧的 Moshi 音频，都会悄悄破坏条件依赖（前者丢掉 inner monologue，后者等于"偷看答案"）。
- **用平均能量当特征**：本文件的伪编码器把所有帧编成了同一组 token；任何"指纹"或"量化"函数都要先检查区分度。
- **HTML 实体混入代码**：从网页或渲染后的 Markdown 复制代码时，`<`、`>`、`&` 可能变成 `&lt;`、`&gt;`、`&amp;`，在字符串里不会报错，只会悄悄打印错。
- **只看均值不看尾延迟**：实时音频以 P95/P99 为准，偶发的一次超时就会造成卡顿。
- **把全双工当万能方案**：代码对照表之外，讲义强调 Moshi 不擅长工具调用和长推理，企业 agent 仍以流水线为主。
