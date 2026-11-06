# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 10 节 音频语言模型 — Qwen2.5-Omni、Audio Flamingo、GPT-4o Audio ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在 `code/` 目录下 `python3 main.py`（docstring 写的是在小节根目录运行 `python3 code/main.py`），无命令行参数；纯 Python 矩阵乘法，约需 5 秒 ｜ **依赖**：仅 Python 标准库（`random`；`math` 被导入但没有用到）

---

## 1. 这份代码在考察什么

docstring 说它展示的是"每个 2026 年 LALM 都在用的三组件模板：音频 encoder → projector → LLM decoder"，没有任何真正的神经网络，只有**形状**：

1. **音频 encoder 的输出形状**：3 秒音频 → `(150 帧, 1280 维)`，对应 Whisper-large encoder 每秒 50 帧、1280 维的特征。
2. **projector 做了什么**：把 1280 维特征线性映射到 LLM 的 4096 维 embedding 空间（加一个非线性）。
3. **音频与文本如何进入同一个序列**：音频项和文本 token 拼接成一条序列，交给 LLM。
4. **LLM 只看到"若干音频位置 + 若干文本位置"**：用一个假的回答函数把这件事说出来。
5. **现实检验**：打印讲义的 MMAU-Pro 成绩表，强调多音频任务接近随机。

> 一句话：**LALM 的工程本质是"把音频变成 LLM 能吃的 embedding 序列"**，这份代码把这件事的每一步形状都打印出来，并让你直观感受到纯 Python 做矩阵乘法有多慢。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `fake_audio_encoder(audio_seconds, dim)` | 函数 | 生成 `int(秒数 × 50)` 帧、每帧 1280 维的高斯随机特征 | 音频 encoder（Whisper-large 的帧率与维度） |
| `projector(features, audio_dim, llm_dim)` | 函数 | 随机权重的单层线性映射 1280 → 4096，再接 ReLU | projector / adapter |
| `interleave_with_text(audio_tokens, text_tokens)` | 函数 | 给每一项打上 `"AUDIO"` / `"TEXT"` 标签后拼接 | 多模态输入序列 |
| `fake_llm_answer(interleaved)` | 函数 | 统计两类项的个数并返回一句模拟回答 | LLM decoder |
| `main()` | 函数 | 5 个步骤 + 成绩表 + 要点 | 整体演示 |

数据流：`fake_audio_encoder → (150, 1280)` → 取前 8 帧 → `projector → (8, 4096)` → 用下标 `0..7` 代表这 8 个音频位置，与 5 个文本 token ID 拼接成长度 13 的序列 → `fake_llm_answer`。

---

## 3. 逐段精讲

### 3.1 `fake_audio_encoder`：50 帧/秒、1280 维

```python
def fake_audio_encoder(audio_seconds=3.0, dim=1280):
    rng = random.Random(0)
    n_frames = int(audio_seconds * 50)
    return [[rng.gauss(0, 0.5) for _ in range(dim)] for _ in range(n_frames)]
```

- `50` 是帧率：Whisper encoder 把 30 秒音频编码成 1500 个位置，即每帧 20 ms；`1280` 是 Whisper-large 的隐藏维度。这两个数决定了后面 LLM 要处理多少个音频位置。
- 嵌套列表推导：外层循环帧、内层循环维度，结果是"列表的列表"，相当于形状 `(n_frames, dim)` 的矩阵。
- `random.Random(0)` 是局部生成器，每次调用结果相同、互不干扰。
- ⚠️ 特征只是高斯噪声，和任何音频内容无关。真实 encoder 输入的是 mel 频谱（第 02、05 节）。
- 由此可以算出音频的"token 预算"：3 秒 = 150 帧，30 秒 = 1500 帧，10 分钟 = 30000 帧。讲义说"超过 10 分钟大多数模型的说话人归属会崩溃"，与这个量级直接相关；真实模型通常还会在时间维度上下采样，以减少送入 LLM 的位置数。

### 3.2 `projector`：把音频特征搬进 LLM 的 embedding 空间

```python
def projector(features, audio_dim=1280, llm_dim=4096):
    random.seed(1)
    W_down = [[random.gauss(0, 0.02) for _ in range(audio_dim)] for _ in range(llm_dim)]
    out = []
    for f in features:
        hidden = [sum(W_down[i][j] * f[j] for j in range(audio_dim)) for i in range(llm_dim)]
        hidden = [max(0.0, h) for h in hidden]
        out.append(hidden)
    return out
```

- `W_down` 的形状是 `(4096, 1280)`；对每一帧 `f`（1280 维）计算 `hidden[i] = Σ_j W[i][j]·f[j]`，即矩阵乘向量，得到 4096 维。
- `max(0.0, h)` 就是 ReLU。讲义 Step 2 的 `AudioProjector` 用的是 `Linear → GELU → Linear` 两层结构，这里简化成"一层 + ReLU"、没有 bias。
- 权重初始化 `N(0, 0.02²)` 是 Transformer 常用的初始化标准差。
- 为什么"只训练 projector 就能对齐"：encoder 和 LLM 都冻结，只有这一小块矩阵在学习"把 Whisper 的特征翻译成 LLM 看得懂的向量"——讲义的 Stage 1。
- ⚠️ 命名：叫 `W_down`，但它把维度从 1280 **升**到 4096（讲义的 `self.down = nn.Linear(audio_dim, llm_dim)` 也是同样的命名），不要被名字误导。
- ⚠️ `random.seed(1)` 修改全局随机状态，而且**每次调用 `projector` 都会重新生成一遍权重**——真实模型的权重是训练后固定的参数，只创建一次。
- ⚠️ 性能：每帧 `4096 × 1280 ≈ 524 万`次乘加，生成权重也要 524 万次 `random.gauss`。所以 `main()` 只投影了前 8 帧（`feats[:8]`），整个脚本仍需约 5 秒。用 numpy 一次 `(T, 1280) @ (1280, 4096)` 就能瞬间完成（参考测验 Q10）。
- 数值直觉：ReLU 前每个元素的标准差约 `√1280 × 0.02 × 0.5 ≈ 0.36`，所以 ReLU 会把大约一半的值置零（实测第一帧 48.4%），均值约 0.146。

### 3.3 `interleave_with_text`：音频与文本进入同一个序列

```python
def interleave_with_text(audio_tokens, text_tokens):
    return [("AUDIO", a) for a in audio_tokens] + [("TEXT", t) for t in text_tokens]
```

```python
    text_tokens = [2345, 1098, 7,   9821, 65]
    interleaved = interleave_with_text(list(range(len(projected))), text_tokens)
```

- 每一项是一个 `(类型, 值)` 元组，两个列表推导用 `+` 拼接：先 8 个音频项，再 5 个文本项，总长 13。
- 讲义说 LLM "Takes interleaved text + audio tokens"：在真实模型里，文本 token ID 先经过词表 embedding 查表变成向量，音频位置直接使用 projector 输出的向量，二者拼成一个 `(L, 4096)` 的输入矩阵。
- ⚠️ 名不副实：①这里并没有"交错"，只是"音频在前、文本在后"的拼接；真实聊天模板中音频位于用户消息内部，前后有特殊的起止标记。②传入的音频项是下标 `0..7`，而不是 projector 输出的 4096 维向量，`projected` 实际上只被用来取了长度。测验 Q11 给出了"在占位符处插入音频 embedding"的写法。
- `text_tokens` 里的数字是随意编的 token ID，`7,   9821` 中间的多个空格只是排版，不影响语义。

### 3.4 `fake_llm_answer`：LLM 只是"看到了多少个位置"

```python
def fake_llm_answer(interleaved):
    n_audio = sum(1 for k, _ in interleaved if k == "AUDIO")
    n_text = sum(1 for k, _ in interleaved if k == "TEXT")
    return f"(simulated) given {n_audio} audio tokens + {n_text} text tokens, I would answer..."
```

- 用带条件的生成器表达式计数：`sum(1 for ... if ...)`。`for k, _ in interleaved` 把每个元组解包，`_` 表示不关心的值。
- 这一步刻意"什么都不做"：它提醒你，从 LLM 的角度看，音频只是序列里的一段 embedding，后续的自回归生成与纯文本 LLM 完全相同。
- 真实模型在这里调用 `generate`，讲义 Step 1 展示了用 transformers 调用 Qwen2.5-Omni 的写法（具体类名和参数以模型卡为准）。

### 3.5 `main()` 的 Step 5：成绩表与要点

```python
    models = [
        ("Gemini 2.5 Pro",    "~60%", "73.4%", "51.9%", "64.9%", "~22%"),
        # ...
        ("Qwen2.5-Omni-7B",   "52.2%", "57.4%","47.6%", "61.5%", "~20%"),
        ("Audio Flamingo 3",  "~54%",  "—",    "—",     "—",     "—"),
    ]
    print("  | model              | overall | speech | sound  | music  | multi  |")
    for name, o, s, snd, m, mu in models:
        print(f"  | {name:<18} | {o:>7} | {s:>6} | {snd:>6} | {m:>6} | {mu:>6} |")
```

- 所有数值都存成**字符串**（因为含 `~` 和 `—`），只用于打印，不能直接参与比较计算。
- 这是讲义 MMAU-Pro 表格的硬编码副本（少了"Audio Flamingo Next"那一行）。值得读出的结论：
  - Qwen2.5-Omni-7B 总分 52.2%，与 GPT-4o Audio 的 52.5% 只差 0.3 个百分点——开源与闭源的差距在总分上基本消失；
  - 多音频列在约 20%–26.5% 之间，4 选 1 的随机水平是 25%，所有模型都不具备可靠的多音频比较能力；
  - speech 列普遍高于 sound 列，语音理解比环境声理解成熟。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用高斯噪声代替 encoder 输出 | 只关心形状 `(帧数, 1280)` | 没有任何语义；真实用 Whisper / BEATs / WavLM 等 encoder |
| 纯 Python 矩阵乘法 | 零依赖、每一步可见 | 极慢（每帧 524 万次乘加）；生产用 GPU 张量运算 |
| 只投影前 8 帧 | 控制运行时间 | 序列长度与真实不符；真实要投影全部帧（或先下采样） |
| 单层 + ReLU 的 projector | 最简"线性映射 + 非线性" | 讲义版本是 Linear-GELU-Linear；权重应只创建一次 |
| 用下标代表音频项 | 便于打印序列 | 掩盖了"音频项是连续向量、文本项需要查表"的关键区别 |
| 拼接而非真正交错 | 代码最短 | 真实模板中音频嵌在消息内部并带起止标记 |
| 成绩表存为字符串 | 能保留 `~`、`—` 等符号 | 无法排序、计算；需要分析时应存数值 + 缺失标记 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def fake_audio_encoder(audio_seconds=3.0, dim=1280)` | 不传参时使用默认值 |
| `int()` 截断 | `int(audio_seconds * 50)` | 浮点转整数（向零截断） |
| 嵌套列表推导 | `[[rng.gauss(0, 0.5) for _ in range(dim)] for _ in range(n_frames)]` | 生成二维列表（矩阵） |
| `_` 占位变量 | `for _ in range(dim)`、`for k, _ in interleaved` | 不使用的循环变量或解包值 |
| 局部 vs 全局随机数 | `random.Random(0)` vs `random.seed(1)` | 前者独立可复现；后者改变全局状态 |
| 生成器表达式求和 | `sum(W_down[i][j] * f[j] for j in range(audio_dim))` | 点积的写法 |
| 二维列表下标 | `W_down[i][j]` | 先取第 i 行，再取第 j 列 |
| 切片 | `feats[:8]`、`interleaved[:12]` | 取前 n 项 |
| 元组列表 | `[("AUDIO", a) for a in audio_tokens]` | 给每个元素打标签 |
| 列表拼接 `+` | `[...] + [...]` | 连接两个列表 |
| 带条件的计数 | `sum(1 for k, _ in interleaved if k == "AUDIO")` | 统计满足条件的元素个数 |
| `list(range(n))` | `list(range(len(projected)))` | 生成 `0..n-1` 的列表 |
| f-string 对齐 | `{name:<18}`、`{o:>7}` | 左对齐 / 右对齐并指定宽度 |
| f-string 嵌入表达式 | `{len(feats)}`、`{len(feats[0])}` | 直接在花括号里调用函数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 4.8 秒，主要花在 projector 生成权重和纯 Python 矩阵乘法上）的完整输出：

```text
=== Step 1: encode 3 s of audio → features (pretend Whisper-large) ===
  audio features: (150 frames, 1280 dim)

=== Step 2: projector → LLM embedding space ===
  projected (first 8 frames): (8, 4096)

=== Step 3: interleave with text token ids ===
  interleaved sequence length: 13
  first 12 items: [('AUDIO', 0), ('AUDIO', 1), ('AUDIO', 2), ('AUDIO', 3), ('AUDIO', 4), ('AUDIO', 5), ('AUDIO', 6), ('AUDIO', 7), ('TEXT', 2345), ('TEXT', 1098), ('TEXT', 7), ('TEXT', 9821)]

=== Step 4: LLM decoder generates an answer ===
  (simulated) given 8 audio tokens + 5 text tokens, I would answer...

=== Step 5: 2026 LALM benchmark board (MMAU-Pro) ===
  | model              | overall | speech | sound  | music  | multi  |
  | Gemini 2.5 Pro     |    ~60% |  73.4% |  51.9% |  64.9% |   ~22% |
  | Gemini 2.5 Flash   |    ~57% |  73.4% |  50.5% |  64.9% |  21.2% |
  | GPT-4o Audio       |   52.5% |      — |      — |      — |  26.5% |
  | Qwen2.5-Omni-7B    |   52.2% |  57.4% |  47.6% |  61.5% |   ~20% |
  | Audio Flamingo 3   |    ~54% |      — |      — |      — |      — |

takeaways:
  - every LALM = audio encoder + projector + LLM decoder
  - Qwen2.5-Omni-7B (Apache-2.0) is within 0.3 points of GPT-4o Audio
  - multi-audio reasoning is near-random (~22-26%) across ALL models in 2026
  - Audio Flamingo Next leads LongAudioBench (beats Gemini 2.5 Pro)
```

逐段解读：

- **Step 1**：`3.0 × 50 = 150` 帧，每帧 1280 维。
- **Step 2**：只投影了前 8 帧，所以是 `(8, 4096)`；如果投影全部帧应是 `(150, 4096)`。
- **Step 3**：8 个音频项 + 5 个文本项 = 13；只打印前 12 项，所以最后一个文本 token `65` 没有显示。音频项的值是下标而不是向量。
- **Step 4**：从 LLM 角度只看到"8 个音频位置 + 5 个文本位置"。
- **Step 5**：讲义成绩表。注意多音频列与 25% 的随机水平几乎重合；另外 Gemini 2.5 Pro 和 Flash 的 speech、music 两列数值完全相同，引用时最好回到原始排行榜核对。
- **takeaways**：四条结论与讲义开头的摘要一致。

---

## 7. 动手改一改

1. 用 numpy 重写 `fake_audio_encoder` 和 `projector`（`rng.normal` 生成矩阵、`@` 做矩阵乘法），投影全部 150 帧，对比运行时间。
2. 按讲义 Step 2 把 projector 改成 `Linear → GELU → Linear`，并加上 bias，打印参数量，确认约 22M。
3. 在 encoder 和 projector 之间加一个"相邻两帧拼接"的下采样：`(150, 1280) → (75, 2560)`，相应把 projector 输入维度改成 2560，观察送入 LLM 的音频位置减半。
4. 重写 `interleave_with_text`：在文本 token 中用一个占位符标记音频位置，在该处插入 `<audio_start>`、全部音频向量、`<audio_end>`，返回 `(L, 4096)` 的矩阵（参考测验 Q11）。
5. 写一个函数，输入音频时长（秒）、帧率、下采样倍数和 LLM 上下文长度，计算"这个模型最多能直接处理多长的音频"，分别代入 8K 和 32K 的上下文长度。
6. 进阶：按讲义 Step 3 的思路，在任意一个 LALM 上用 MMAU-Pro 的几道题做 sanity check，并按 `category` 分别统计准确率。

---

## 8. 常见坑

- **把音频项当成 token ID**：projector 输出的是连续向量，不经过词表；与文本 ID 混在一起处理是概念错误。
- **每次调用都重新生成权重**：`projector` 每次都 `random.seed(1)` 并重建 `W_down`，既慢又不符合"参数固定"的模型语义。
- **在库函数里设全局种子**：`random.seed(1)` 会影响同进程中其他代码的随机行为。
- **名字与行为不符**：`W_down` 实际升维，`interleave_with_text` 实际只是拼接，读代码时以行为为准。
- **低估音频序列长度**：50 帧/秒意味着 10 分钟音频有 3 万帧，直接送入 LLM 会撑爆上下文，需要下采样、分段或先做 diarization。
- **把成绩表当真值使用**：表中数值为字符串、部分为约数，且来自讲义的二手汇总，做决策前应回到官方排行榜并用官方评分器复测。
