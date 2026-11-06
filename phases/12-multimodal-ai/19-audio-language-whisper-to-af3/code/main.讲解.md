# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 19 节 音频语言模型：从 Whisper 到 Audio Flamingo 3 的演进 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`），无需 NumPy、GPU 或网络

---

## 1. 这份代码在考察什么

讲义的技术主线是"音频编码器 → Q-Former → LLM"。代码用纯 Python 把前两段的骨架搭出来，再用一张表说明 cascade 与 end-to-end 的能力边界：

1. **log-Mel 频谱**（`demo_melspec`）：合成波形 → 分帧 → 朴素 DFT 求幅值 → "Mel" 滤波 → 对数压缩。对应学习目标 "Compute a log-Mel spectrogram from a waveform"。
2. **音频 Q-Former**（`demo_qformer`）：8 个 query 对 99 个帧做 softmax 注意力，输出 8 个 token。对应 "Build an audio Q-former"。
3. **任务覆盖表**（`task_coverage_table`）：10 类音频任务在 cascade 与 end-to-end 下能否完成。对应 "Explain cascaded vs end-to-end"。
4. **2026 配方**：打印编码器、桥接、LLM、训练数据和按需思考的推荐组合。

> 一句话：**音频进 LLM 之前，要先变成 (时间, 频率) 的二维特征，再被一组固定数量的 query 压缩成 token**。代码为了跑得动做了大量简化（只算 64 个频点、线性矩形滤波器、不加窗、Q-Former 无投影），这些简化本身就是理解真实实现的好切入点。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `synth_waveform` | 函数 | 生成 440 Hz（振幅 0.5）+ 880 Hz（振幅 0.2）的 1 秒正弦叠加 | 测试信号 |
| `window_frames` | 函数 | 25 ms 窗、10 ms 跳分帧（不补零、不加窗） | STFT 分帧 |
| `naive_dft_mag` | 函数 | 对一帧逐频点做 O(N·K) 的 DFT，返回前 `n_bins` 个幅值 | 傅里叶变换 |
| `mel_filterbank` | 函数 | 把 64 个频点线性均分给 20 个"矩形"滤波器 | Mel 滤波器组（简化） |
| `apply_mel` / `log_compress` | 函数 | 矩阵-向量乘；逐元素 `log(1 + x)` | 滤波、对数压缩 |
| `demo_melspec` | 函数 | 串起上面的步骤，只处理第一帧并打印 | log-Mel 演示 |
| `QFormer` | dataclass | 随机 query + 无投影的点积注意力 | Audio Q-Former |
| `demo_qformer` | 函数 | 对 99 个随机 20 维帧运行 Q-Former | 固定长度输出 |
| `task_coverage_table` | 函数 | 打印硬编码的任务对照表 | cascade vs end-to-end |
| `main` | 函数 | 依次运行并打印 2026 配方 | — |

数据流：`demo_melspec`：`synth_waveform` → `window_frames` → `naive_dft_mag(frames[0])` → `mel_filterbank` + `apply_mel` → `log_compress`。`demo_qformer` **并不使用**上面算出的 log-Mel，而是重新生成随机帧——两个演示是互相独立的。

---

## 3. 逐段精讲

### 3.1 合成波形与分帧

```python
def synth_waveform(duration_s: float = 1.0, sr: int = 16000) -> list[float]:
    n = int(duration_s * sr)
    freq = 440
    return [0.5 * math.sin(2 * math.pi * freq * i / sr) +
            0.2 * math.sin(2 * math.pi * 880 * i / sr)
            for i in range(n)]


def window_frames(x: list[float], sr: int, win_ms: int = 25, hop_ms: int = 10) -> list[list[float]]:
    win = int(sr * win_ms / 1000)
    hop = int(sr * hop_ms / 1000)
    frames = []
    i = 0
    while i + win <= len(x):
        frames.append(x[i:i + win])
        i += hop
    return frames
```

- 波形是两个正弦的和：440 Hz（A4 音）振幅 0.5，880 Hz（高八度）振幅 0.2，共 16,000 个采样点。
- `win = 400`、`hop = 160` 点。帧数 = `⌊(16000 − 400) / 160⌋ + 1 = 98`，运行输出也是 98。
- ⚠️ 提示语 "should be ~99 at 1s" 不准确：不补零时是 98；Whisper 用 center 模式在两端补零，每秒 100 帧，30 秒 3,000 帧（讲义的 `(3000, 80)`）。
- ⚠️ 没有乘窗函数（等价于矩形窗）。本例 440 Hz 恰好在 400 点内是 11 个整周期，所以没有频谱泄漏；换成 450 Hz 就会泄漏（测验 Q12 实测：不加窗时离峰值 ±2 个频点以外的能量占 3.9%，加 Hann 窗后降到 0.017%）。

### 3.2 朴素 DFT

```python
def naive_dft_mag(frame: list[float], n_bins: int = 64) -> list[float]:
    n = len(frame)
    out = []
    for k in range(n_bins):
        re = 0.0
        im = 0.0
        for i, x in enumerate(frame):
            angle = -2 * math.pi * k * i / n
            re += x * math.cos(angle)
            im += x * math.sin(angle)
        out.append(math.sqrt(re * re + im * im))
    return out
```

- 直接按定义 `X[k] = Σ x[i]·e^(−2πjki/N)` 计算，实部用 cos、虚部用 sin，再取模。复杂度 O(N × n_bins) = 400 × 64 = 25,600 次乘加/帧；真实系统用 FFT，O(N log N)。
- 第 k 个频点的频率是 `k × sr / N = 40k` Hz。440 Hz → k = 11，880 Hz → k = 22。
- 单频正弦在整周期时的幅值 = 振幅 × N / 2：`0.5 × 200 = 100`、`0.2 × 200 = 40`。实测第一帧的 64 个幅值里只有这两个非零。
- ⚠️ 只计算了前 64 个频点，覆盖 0–2,520 Hz；完整单边谱应有 `N/2 + 1 = 201` 个频点、覆盖到 8 kHz。讲义说 Mel 滤波器覆盖 0–8000 Hz，代码只覆盖了约三分之一的频带。

### 3.3 "Mel" 滤波器组与对数压缩

```python
def mel_filterbank(n_bins: int = 64, n_mels: int = 20) -> list[list[float]]:
    """Triangular Mel filter bank (simplified, linear warp as proxy)."""
    fbank = []
    band = n_bins // n_mels
    for m in range(n_mels):
        row = [0.0] * n_bins
        start = m * band
        end = min(start + band, n_bins)
        for k in range(start, end):
            row[k] = 1.0 / (end - start)
        fbank.append(row)
    return fbank


def apply_mel(spec_mag: list[float], fbank: list[list[float]]) -> list[float]:
    return [sum(w * s for w, s in zip(row, spec_mag)) for row in fbank]


def log_compress(xs: list[float]) -> list[float]:
    return [math.log(1 + x) for x in xs]
```

- `band = 64 // 20 = 3`：第 m 个滤波器覆盖频点 `3m, 3m+1, 3m+2`，每个权重 1/3——实质是"每 3 个频点求平均"。
- ⚠️ 名不副实：docstring 说 "Triangular Mel"，实际是**线性**刻度、**矩形**形状、**不重叠**；20 × 3 = 60，频点 60–63 没有被任何滤波器覆盖。真实 Mel 滤波器在 `mel = 2595·log10(1 + f/700)` 刻度上等距、三角形、相邻重叠一半，低频窄高频宽（实现见测验 Q9）。
- `apply_mel` 是"滤波器矩阵 × 幅值向量"：`(20, 64) @ (64,) → (20,)`。
- `log(1 + x)` 压缩动态范围，`+1` 保证 x = 0 时结果为 0 而不是 −∞。讲义写的就是 `log(1 + x)`；Whisper 的实际做法是对功率谱取 `log10` 后截断、缩放。
- 第一帧的结果：第 3 个滤波器（频点 9–11）平均得 `100/3 = 33.3`，`ln(34.3) = 3.54`；第 7 个滤波器（频点 21–23）得 `40/3 = 13.3`，`ln(14.3) = 2.66`；其余为 0。

### 3.4 Audio Q-Former 骨架

```python
@dataclass
class QFormer:
    n_queries: int
    hidden: int

    def __post_init__(self):
        self.queries = [[random.gauss(0, 0.1) for _ in range(self.hidden)]
                        for _ in range(self.n_queries)]

    def forward(self, frames: list[list[float]]) -> list[list[float]]:
        out = []
        for q in self.queries:
            scores = [sum(qi * fi for qi, fi in zip(q, f)) for f in frames]
            m = max(scores)
            exps = [math.exp(s - m) for s in scores]
            z = sum(exps)
            weights = [e / z for e in exps]
            agg = [sum(w * f[k] for w, f in zip(weights, frames))
                   for k in range(self.hidden)]
            out.append(agg)
        return out
```

- `@dataclass` 自动生成 `__init__(n_queries, hidden)`；`__post_init__` 在构造后执行，用来生成 `n_queries × hidden` 的随机 query 矩阵。
- `forward` 对每个 query：与每一帧做点积得到 99 个分数 → 减最大值后 softmax → 用权重对所有帧加权求和，得到一个 `hidden` 维向量。8 个 query 输出 8 个 token，**输出长度与帧数无关**——这正是 Q-Former"把任意长音频压成固定数量 token"的核心性质。
- ⚠️ 与真实 Q-Former 的差距：
  - 没有 `W_q / W_k / W_v` 投影，query 直接与原始帧点积，所以要求 `hidden` 必须等于帧维度；
  - 没有 `1/√d` 缩放；
  - query 是随机数，没有训练；没有 self-attention、FFN、多层堆叠；
  - 输入帧是 `random.gauss` 生成的 99 个随机向量，不是 `demo_melspec` 算出的 log-Mel（那边是 98 帧、只算了第一帧）。
- 我们在 `random.seed(6)` 下复现了这次运行：第一个 query 的注意力权重最大约 0.032、最小约 0.002，而均匀分布是 1/99 ≈ 0.010——随机 query 的注意力接近均匀，几乎等于"对所有帧求平均"，这就是"未训练的 query"该有的样子。

### 3.5 任务覆盖表与 2026 配方

```python
    tasks = [
        ("transcription",            "yes", "yes"),
        ...
        ("emotion inference",        "no",  "yes"),
        ...
        ("deepfake detection",       "no",  "yes"),
    ]
    ...
    print("  end-to-end: required for acoustic-only signals (~40% of MMAU)")
```

- 表格是硬编码的定性判断，与讲义 "Cascaded vs end-to-end" 一节一致：凡是信息"在声音里而不在文字里"的任务，cascade 都标为 no 或 partial。
- ⚠️ "~40% of MMAU" 在讲义中没有出处，属于代码作者的估计。讲义 "Use It" 说有 "Cascaded-vs-end-to-end comparison on a toy task"，实际只是打印这张表，没有在任何玩具任务上跑对比。

```python
    print("  encoder : AF-Whisper + BEATs concat")
    print("  bridge  : 64-query Q-former")
    print("  LLM     : Qwen2.5-7B with audio tokens")
```

- ⚠️ 与讲义不一致的两处：
  - 讲义把 AF-Whisper 定义为"Whisper + BEATs 特征拼接"，这里又写"AF-Whisper + BEATs concat"，等于把 BEATs 拼了两次；
  - 讲义说 AF3 的骨干是 "Qwen2 7B"，这里写 "Qwen2.5-7B"。两处说法应统一，具体以 AF3 论文（arXiv:2507.08128）为准。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯标准库、朴素 DFT | 每一步都能看清，零依赖 | O(N²) 很慢；生产用 `torch.stft` / `librosa`（FFT） |
| 只算 64 个频点、只处理第一帧 | 控制纯 Python 的运行时间 | 丢掉 2.5 kHz 以上频带；真实特征是 `(帧数, 80)` 的整张图 |
| 不补零、不加窗 | 代码最短 | 帧数 98 而不是 100；非整周期信号会泄漏；生产用 Hann 窗 + center 补零 |
| 测试信号选 440/880 Hz | 恰好整周期，频谱干净、便于手算 | 掩盖了不加窗的问题 |
| 线性矩形"Mel"滤波器 | 不需要 mel 换算 | 低频分辨率不足、高频过细；生产用三角形 Mel 滤波器（80 或 128 个） |
| `log(1 + x)` | 无需处理 log(0) | 与 Whisper 的 `log10` + 截断归一化不同，预训练编码器的输入必须严格匹配其训练时的特征 |
| Q-Former 无投影、随机 query | 突出"固定 query 读任意长输入"的结构 | 不能学习；真实 Q-Former 是多层 Transformer，带投影、self-attn、FFN，并经两阶段训练 |
| 任务表与配方硬编码 | 传达讲义结论 | 没有实验支撑；"~40% of MMAU" 等数字需要核实 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 带换行的列表推导式 | `[0.5 * math.sin(...) + 0.2 * math.sin(...) for i in range(n)]` | 括号内可以自由换行 |
| 切片 | `x[i:i + win]` | 取出从 i 开始的 `win` 个元素（新列表） |
| `while` 循环 | `while i + win <= len(x): ... i += hop` | 步长不固定或终止条件复杂时用 while |
| `enumerate` | `for i, x in enumerate(frame)` | 同时拿到下标和值 |
| `math` 函数 | `math.sin`、`math.cos`、`math.sqrt`、`math.log`、`math.exp`、`math.pi` | 标准库数学函数，`math.log` 是自然对数 |
| `zip` 并行遍历 | `sum(w * s for w, s in zip(row, spec_mag))` | 两个列表逐元素配对；配合生成器表达式实现点积 |
| 生成器表达式 | `sum(qi * fi for qi, fi in zip(q, f))` | 不建中间列表，直接求和 |
| 嵌套推导式 | `[[random.gauss(0, 1) for _ in range(20)] for _ in range(99)]` | 生成 99 × 20 的二维列表 |
| 整除 | `n_bins // n_mels` | 结果向下取整（64 // 20 = 3） |
| `@dataclass` + `__post_init__` | `class QFormer: ... def __post_init__(self)` | 自动构造函数之后再做额外初始化 |
| 元组列表 + 解包 | `for name, cas, e2e in tasks` | 一次取出三列 |
| f-string 中的推导式 | `{[round(v, 2) for v in log_mel[:10]]}` | 花括号里可放任意表达式 |
| f-string 对齐 | `{name:<30}{cas:<14}` | 左对齐、固定宽度，打印表格 |
| `random.gauss(mu, sigma)` | `random.gauss(0, 0.1)` | 正态分布随机数 |
| 类型注解 | `-> list[list[float]]` | 返回"浮点数列表的列表" |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，约 0.1 秒）：

```text
LOG-MEL SPECTROGRAM (1s @ 16kHz, 25ms win, 10ms hop, 20 mel bins)
------------------------------------------------------------
  frames : 98 (should be ~99 at 1s)
  per-frame mel dim: 20
  first frame log-mel (rounded): [0.0, 0.0, 0.0, 3.54, 0.0, 0.0, 0.0, 2.66, 0.0, 0.0]...

AUDIO Q-FORMER (N=8 queries over 20-dim frames)
------------------------------------------------------------
  input frames: 99
  output tokens: 8 of dim 20
  each token attends over the full audio by soft attention weights

CASCADED (Whisper -> LLM) vs END-TO-END AUDIO-LLM
  ...（10 行任务表，略）
  cascaded: fast + reliable for text-extractable signals
  end-to-end: required for acoustic-only signals (~40% of MMAU)
```

逐项解读：

- **98 帧**：`(16000 − 400) // 160 + 1`，不补零的正确结果；提示里的 "~99" 和 Whisper 的 100 都不是这个算法能得到的。
- **20 维**：每帧经 20 个滤波器得到 20 个值（真实系统是 80 或 128）。
- **3.54 与 2.66**：分别是 440 Hz（落在频点 11，属于第 3 个滤波器）和 880 Hz（频点 22，属于第 7 个滤波器）的能量，计算过程见 3.3 节。其余位置严格为 0，因为整周期正弦没有泄漏。
- **Q-Former**：99 帧进、8 个 token 出，演示了"输出长度固定"。这里的 99 是 `demo_qformer` 自己生成的随机帧数，与上面的 98 无关。
- **任务表**：cascade 在 5 类纯声学任务上是 "no"、在说话人分离和时间定位上是 "partial"，与讲义一致。

---

## 7. 动手改一改

1. **补齐频谱**：把 `n_bins` 改成 `400 // 2 + 1 = 201`，对全部 98 帧计算，得到 `(98, 201)` 的幅值谱；记录纯 Python 的耗时，再用 `numpy.fft.rfft` 对比速度。
2. **真正的 Mel**：实现三角形 Mel 滤波器组（参考测验 Q9），设为 80 个 Mel bin、`fmax = 8000`，得到 `(98, 80)` 的 log-Mel，并打印最大值所在的 Mel 通道，确认 440 Hz 落在低频区。
3. **加窗与补零**：给每帧乘 Hann 窗，并在信号两端各补 200 个零，验证帧数变成 101（再去掉最后一帧即为 100）；把测试频率改成 450 Hz，比较加窗前后的频谱泄漏。
4. **接通两段演示**：让 `demo_qformer` 直接使用第 2 步得到的 `(98, 80)` log-Mel 作为输入帧（`hidden=80`），观察输出形状 `(8, 80)`。
5. **加投影的 Q-Former**：按测验 Q11 加入 `W_q/W_k/W_v` 和 `1/√d` 缩放，把 query 数分别设为 32 和 64，估算下游 LLM 需要处理的 token 数差异（讲义练习 3）。
6. **进阶**：用 `openai-whisper` 或 `transformers` 的 `WhisperFeatureExtractor` 对同一段波形提特征，与你的实现逐元素比较，找出剩余的差异（功率谱 vs 幅值谱、`log10`、截断与缩放、Slaney Mel）。

---

## 8. 常见坑

- **采样率不匹配**：Whisper 只接受 16 kHz；直接把 44.1/48 kHz 的音频按 16 kHz 解释，频率会整体偏移、特征完全错乱。务必先重采样。
- **帧数算错**：要区分"是否补零"（98 vs 100 帧/秒），否则与预训练模型的位置编码长度对不上。
- **以为不加窗也没事**：本例信号恰好整周期，真实音频几乎不可能如此。
- **把线性均分当 Mel**：低频（语音基频、乐器音高）分辨率会严重不足。
- **特征归一化与预训练不一致**：用冻结编码器时，log 的底数、截断、缩放都必须与其训练时完全一致。
- **混淆编码器帧数与 LLM token 数**：Whisper 30 秒 → 1,500 个编码器位置；经 64-query Q-Former 后只剩 64 个 LLM token，二者相差 23 倍。
- **Q-Former 的 hidden 维度**：无投影实现要求 query 维度等于帧维度；加了投影后二者可以不同。
