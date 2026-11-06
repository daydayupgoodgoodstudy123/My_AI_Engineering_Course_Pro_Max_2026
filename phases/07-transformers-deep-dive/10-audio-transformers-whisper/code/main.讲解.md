# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 10 节 音频 Transformers — Whisper 架构 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`），不需要 `librosa`、`torch` 或 Whisper 本体

---

## 1. 这份代码在考察什么

讲义的判断是：生产中你真正会"碰"的不是 Whisper 的权重，而是**它前面的预处理**和**它前面的提示前缀**。所以这份代码只做这两件事：

1. **分帧（framing）**：16 kHz 采样，帧长 400 点（25 ms）、帧移 160 点（10 ms），理解"多少秒 → 多少帧"。
2. **补齐到 30 秒窗口**：Whisper 永远处理 3000 帧（30 秒）的固定窗口，短音频要补齐、长音频要截断。
3. **每帧一个特征**：用"对数能量"代替 80 维 log-mel，只为展示流水线的形状（讲义："Per-frame energy stands in for mel bins for pedagogy"）。
4. **Task token 前缀**：`<|startoftranscript|> <|语种|> <|任务|> [<|notimestamps|>]`，一个极小的"控制面"切换转写/翻译/时间戳。
5. **尺寸表**：打印 tiny 到 large-v3、turbo 的层数、宽度、头数。

> 一句话：**Transformer 看到的只是"一张 帧数 × 特征 的图"加"几个控制 token"**——搞清楚这两样的形状，就搞清楚了 Whisper 的输入接口。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SAMPLE_RATE / FRAME_SIZE / HOP / MAX_SECONDS / TARGET_FRAMES` | 模块级常量 | 16000 Hz、400 点、160 点、30 秒、3000 帧 | Whisper 的固定预处理参数 |
| `sine_wave(freq, duration_s, sr)` | 函数 | 生成正弦波采样点 | 合成测试音频 |
| `frame_signal(x, frame_size, hop)` | 函数 | 按窗长/帧移切出重叠的帧 | Framing（STFT 的第一步） |
| `frame_energy(frame)` | 函数 | 帧内平方和取对数 | log-mel 的教学替身 |
| `pad_or_clip(frames, target)` | 函数 | 补零帧或截断到目标帧数 | 30 秒固定窗口 |
| `whisper_prompt(lang, task, timestamps)` | 函数 | 生成 task token 列表 | decoder 前缀控制任务 |
| `main()` | 入口 | 演示 1 秒/5 秒分帧、补齐、能量、三个提示示例、尺寸表 | — |

数据流：`sine_wave → frame_signal → pad_or_clip`（形状演示）和 `frame_signal → frame_energy`（特征演示）；`whisper_prompt` 独立演示 decoder 侧的输入。

---

## 3. 逐段精讲

### 3.1 常量：把"毫秒"换算成"采样点"

```python
SAMPLE_RATE = 16000
FRAME_SIZE = 400   # 25 ms at 16 kHz
HOP = 160          # 10 ms at 16 kHz
MAX_SECONDS = 30
TARGET_FRAMES = 3000  # 30 s / 10 ms
```

- 换算关系：`采样点数 = 秒数 × 采样率`。`0.025 × 16000 = 400`，`0.010 × 16000 = 160`。
- 帧长 25 ms 大于帧移 10 ms，所以**相邻帧有 15 ms 重叠**。语音在 20–30 ms 内可近似看作"平稳"，这是语音处理沿用几十年的经典设置。
- `TARGET_FRAMES = 3000` 是 `30 s / 10 ms`。这些值在 Whisper 里是写死的：模型的位置编码就是按 1500 个 encoder 时间步（3000 帧下采样 2 倍）训练的，改了就对不上。
- 用全大写模块常量是 Python 的约定，表示"不应在运行时修改"。

### 3.2 合成音频

```python
def sine_wave(freq, duration_s, sr=SAMPLE_RATE):
    n = int(duration_s * sr)
    return [math.sin(2 * math.pi * freq * i / sr) for i in range(n)]
```

- 第 i 个采样点的时间是 `i / sr` 秒，`sin(2π · f · t)` 就是频率 f 的正弦波。
- 1 秒 → 16000 个采样点；5 秒 → 80000 个。
- 默认参数 `sr=SAMPLE_RATE` 引用了模块常量：默认值在**函数定义时**求值，之后再改 `SAMPLE_RATE` 不会影响它。

### 3.3 分帧

```python
def frame_signal(x, frame_size=FRAME_SIZE, hop=HOP):
    frames = []
    for start in range(0, len(x) - frame_size + 1, hop):
        frames.append(x[start:start + frame_size])
    return frames
```

- 起点从 0 开始，每次前进 `hop`，最后一帧必须完整地落在信号里，所以上界是 `len(x) - frame_size + 1`。帧数公式：`⌊(N − frame_size) / hop⌋ + 1`。
- 1 秒：`⌊15600 / 160⌋ + 1 = 98` 帧；30 秒：2998 帧——都比"每 10 ms 一帧"少 2 帧，因为两端没有补齐。
- ⚠️ 与 Whisper 官方的差异：官方先把**音频**补齐到 480,000 点，再用 `torch.stft`（默认 `center=True`，两端各补半个窗口）计算频谱，得到 3001 帧再丢掉最后一帧，恰好 3000。官方还会对每帧乘 Hann 窗再做 FFT，这里都省略了。
- 切片 `x[start:start + frame_size]` 会**复制**出一个新列表，所以帧之间互不影响；代价是内存约为原信号的 `400 / 160 = 2.5` 倍。NumPy 中可以用 stride tricks 做"零拷贝"的重叠视图。

### 3.4 每帧对数能量

```python
def frame_energy(frame):
    """Sum-of-squares energy, log-scaled. Stand-in for mel power."""
    e = sum(v * v for v in frame)
    return math.log(e + 1e-9)
```

- 平方和就是这一帧的总能量（功率）。真实 log-mel 会先 FFT 得到每个频率的功率，再用 80 个（large-v3 为 128 个）三角形 mel 滤波器把功率分组求和，最后取 log——能量被**按频带拆开**，这里则把所有频率**加在一起**成了一个数。
- `+ 1e-9`：防止静音帧 `log(0)`（`math.log(0)` 会抛 `ValueError`）。全零帧会得到 `log(1e-9) ≈ −20.72`。
- ⚠️ 本例中前 5 帧都是 `+5.298`：400 个采样点恰好是 440 Hz 的 11 个完整周期，`Σ sin² = 200`，`ln(200) = 5.298`。换成 880 Hz 结果一样——这说明单个能量值**完全分辨不出音高**，必须用频带特征。
- 自然对数 `math.log` 与 Whisper 用的 `log10` 只差一个常数倍，不影响"压缩动态范围"的作用。

### 3.5 补齐 / 截断到 30 秒

```python
def pad_or_clip(frames, target):
    if len(frames) >= target:
        return frames[:target]
    pad_frame = [0.0] * len(frames[0]) if frames else [0.0] * FRAME_SIZE
    return frames + [pad_frame] * (target - len(frames))
```

- 超过 3000 帧就截断（`frames[:target]`），不足就在末尾补全零帧。Whisper 永远只看一个 30 秒窗口，所以长音频必须由外部分块（讲义："No long-form context beyond 30 s without external chunking"）。
- `if frames else` 处理空输入：没有帧时用 `FRAME_SIZE` 作为补齐帧的长度。
- ⚠️ `[pad_frame] * k` 生成的是**同一个列表对象的 k 个引用**。演示中只读不写，所以没问题；一旦有代码原地修改某个补齐帧，所有补齐帧会一起变。安全写法是 `[[0.0] * width for _ in range(k)]`。
- ⚠️ 补齐的是"帧"（原始采样片段），而官方补齐的是"音频"。结果在形状上一致，但官方的补齐区域会经过同样的 STFT + log-mel + 动态范围裁剪（`max(log_spec, log_spec.max() − 8)`），数值处理更稳。

### 3.6 Task token 前缀

```python
def whisper_prompt(lang="en", task="transcribe", timestamps=True):
    tokens = ["<|startoftranscript|>", f"<|{lang}|>", f"<|{task}|>"]
    if not timestamps:
        tokens.append("<|notimestamps|>")
    return tokens
```

- 这几个 token 放在 decoder 输入的最前面，模型在训练时就见过这种约定，所以"改前缀就是改任务"——讲义称之为"语音版的指令微调"。
- `lang` 是**输入音频**的语种；`task` 为 `transcribe`（同语种转写）或 `translate`（翻译成英文）。
- `timestamps=False` 时追加 `<|notimestamps|>`，模型就不再输出 `<|0.00|>` 这类时间戳 token；默认开启时间戳时，模型会以 0.02 秒为粒度预测它们。
- 讲义原文说"A 4-token prefix"，代码在开启时间戳时返回 3 个 token、关闭时返回 4 个；讲义示例中的第 4 个 `<|0.00|>` 是开启时间戳时 decoder 输出的第一个时间戳 token。
- ⚠️ 这里返回的是字符串列表；真实使用中由 Whisper tokenizer 把它们映射成特殊 token id。

### 3.7 `main()`：演示与尺寸表

```python
    configs = [
        ("tiny",      39,  4,  384,  6),
        # ...
        ("large-v3",1550, 32, 1280, 20),
        ("turbo",    809, 32, 1280, 20),
    ]
    print(f"  {'name':<10}  {'params(M)':>10}  {'layers':>7}  {'d_model':>8}  {'heads':>6}")
    for name, p, L, d, h in configs:
        print(f"  {name:<10}  {p:>10}  {L:>7}  {d:>8}  {h:>6}")
```

- f-string 里的 `<10`、`>10` 分别是左对齐、右对齐并占 10 格，用来打印整齐的表格；表头也用同样的宽度，保证列对齐。
- turbo 的 `layers = 32` 指 encoder 层数；它的 decoder 只有 4 层（代码最后一行注释了这一点）。
- 讲义 Step 3/4 中写"24 层（for large）"的 encoder/decoder，与这里的尺寸表（large 32 层）不一致，以尺寸表为准；24 层的是 medium。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不用 FFT，只算每帧能量 | 纯标准库即可运行，突出"帧数 × 特征"的形状 | 失去频率信息；生产中用 `whisper.log_mel_spectrogram` 或 `librosa` / `torchaudio` |
| 正弦波作为输入 | 可控、可手算验证（如 `ln 200`） | 不像真实语音；验证特征时应换成真实录音 |
| 先分帧再补帧 | 代码最简单 | 与官方"先补音频再 STFT"的帧数、边界处理略有差异 |
| 无边界补齐、无加窗 | 少写代码 | 帧数比 `秒数 × 100` 少 2；频谱泄漏（真实实现用 Hann 窗） |
| 提示前缀用字符串列表 | 一眼看懂任务控制面 | 真实实现是特殊 token id，由 tokenizer 处理 |
| 尺寸表硬编码 | 方便对比各规模 | 数字取自讲义，未实际计算参数量 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `SAMPLE_RATE = 16000` | 全大写命名，约定不修改 |
| 默认参数引用常量 | `def frame_signal(x, frame_size=FRAME_SIZE, hop=HOP)` | 默认值在定义时求值一次 |
| 列表推导式 | `[math.sin(2 * math.pi * freq * i / sr) for i in range(n)]` | 一行生成采样点 |
| `range(start, stop, step)` | `range(0, len(x) - frame_size + 1, hop)` | 以帧移为步长遍历起点 |
| 切片 | `x[start:start + frame_size]`、`frames[:target]` | 左闭右开，返回新列表 |
| 生成器表达式 | `sum(v * v for v in frame)` | 不建中间列表直接求和 |
| 条件表达式 | `[0.0] * len(frames[0]) if frames else [0.0] * FRAME_SIZE` | 空列表为假值 |
| 列表乘法的引用陷阱 | `[pad_frame] * (target - len(frames))` | 重复的是同一个对象的引用 |
| 列表拼接 | `frames + [...]` | 返回新列表，不修改原列表 |
| `list.append` | `tokens.append("<\|notimestamps\|>")` | 在末尾添加一个元素 |
| f-string 嵌入表达式 | `f"<\|{lang}\|>"`、`f"{FRAME_SIZE / SAMPLE_RATE * 1000:.0f} ms"` | 花括号里可以写任意表达式；`.0f` 不保留小数 |
| f-string 对齐 | `f"{name:<10}"`、`f"{p:>10}"`、`f"{'name':<10}"` | `<` 左对齐，`>` 右对齐；字面量字符串也可以格式化 |
| `str.join` | `", ".join(f"{e:+.3f}" for e in energies[:5])`、`"  ".join(toks)` | 用分隔符拼接字符串序列；`+` 让正数也显示符号 |
| 元组列表 + 解包 | `for name, p, L, d, h in configs` | 每行一个配置，循环中一次取出 |

---

## 6. 运行结果解读

实际运行（Python 3.13）输出：

```text
=== Whisper preprocessing pipeline ===
target: 30s audio at 16000 Hz
frame:  400 samples (25 ms)
hop:    160 samples (10 ms)

1s signal → 16000 samples → 98 frames
5s signal → 80000 samples → 498 frames
after pad to 30s: 3000 frames  (target 3000)
first 5 frame log-energies: +5.298, +5.298, +5.298, +5.298, +5.298
```

- `98 frames`：`⌊(16000 − 400) / 160⌋ + 1 = 98`，讲义练习 1 说"约 100"——差的 2 帧来自没有边界补齐。
- `498 frames`：5 秒同理，比 500 少 2。
- `3000 frames`：`pad_or_clip` 补了 2502 个零帧，凑满 30 秒窗口——不管你说了 1 秒还是 29 秒，Whisper encoder 都处理同样长度的输入，这也是短语音"浪费"算力的原因。
- `+5.298` ×5：每帧都是 11 个完整周期，能量恒为 200，`ln 200 = 5.298`。

```text
=== task prompts — what flips Whisper's behavior ===
  English transcription with timestamps:
    <|startoftranscript|>  <|en|>  <|transcribe|>
  French translation to English, no timestamps:
    <|startoftranscript|>  <|fr|>  <|translate|>  <|notimestamps|>
  Japanese transcription with timestamps:
    <|startoftranscript|>  <|ja|>  <|transcribe|>
```

- 三种行为只差一两个 token。注意法语翻译用的是 `<|fr|>`（音频语种），而不是 `<|en|>`（目标语种）。

```text
=== Whisper size table (large-v3 geometry) ===
  name         params(M)   layers   d_model   heads
  tiny                39        4       384       6
  ...
  large-v3          1550       32      1280      20
  turbo              809       32      1280      20

turbo = large-v3 encoder + 4-layer decoder. 8x faster decoding.
```

- 从 tiny 到 large-v3，宽度从 384 到 1280、层数从 4 到 32，参数量差 40 倍。
- turbo 与 large-v3 宽度、encoder 层数相同，参数量却少了近一半——几乎全部来自 decoder 从 32 层减到 4 层。

---

## 7. 动手改一改

1. **讲义练习 1**：把 `sine_wave` 的时长改成 30 秒，确认得到 2998 帧；再给 `frame_signal` 加一个 `center=True` 选项（两端各补 `frame_size // 2` 个 0），验证 30 秒信号变为 3001 帧。
2. **修 `pad_or_clip` 的引用问题**：用列表推导式创建独立的补齐帧，并写一个断言 `padded[-1] is not padded[-2]`。
3. **能量区分不了音高**：分别对 440 Hz 和 880 Hz 计算帧能量，确认相同；再用 `numpy.fft.rfft` 计算每帧频谱，找出峰值所在的频率 bin，确认两者不同。
4. **讲义练习 2（完整 log-mel）**：用 NumPy 实现 Hann 窗 → `rfft`（n_fft=400）→ 功率谱 → 80 个 mel 三角滤波器 → `log10` → `max(x, x.max() − 8)` → `(x + 4) / 4`，输出形状 `(80, 帧数)`。
5. **提示前缀校验**：给 `whisper_prompt` 加参数检查——`task` 只能是 `transcribe` 或 `translate`，`lang` 必须在一个支持语种集合中，否则抛 `ValueError`。
6. **讲义练习 3（分块）**：写 `chunk_audio(x, win_s=10, overlap_s=2)`，返回每块的采样点和起始时间（秒），为后续合并时间戳做准备。

---

## 8. 常见坑

- **采样率不匹配**：Whisper 只接受 16 kHz；44.1 kHz 的音频不重采样直接送进去，所有帧对应的时长都错了，识别结果会严重变差。
- **把帧数算成 `秒数 × 100`**：是否做边界补齐会差 1–2 帧，形状不匹配时常因此报错。
- **`[obj] * n` 的共享引用**：补齐帧、二维数组初始化时最常见的 Python 陷阱。
- **`log(0)`**：静音段必须加 epsilon 或 clamp，否则得到 `-inf` 或抛异常。
- **翻译任务的语种 token 写成目标语言**：`<|translate|>` 永远翻译成英文，语种 token 应写源语言。
- **以为 Whisper 能处理任意长音频**：超过 30 秒必须分块；不分块会被直接截断，后面的内容全部丢失。
