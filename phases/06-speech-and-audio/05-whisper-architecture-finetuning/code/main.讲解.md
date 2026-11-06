# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 05 节 Whisper——架构与 Fine-Tuning ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math` 被 import 但未使用）；不需要安装 `whisper` / `transformers`，也不下载模型

---

## 1. 这份代码在考察什么

Whisper 本身动辄几百 MB 到几 GB，这份脚本不加载任何模型，而是用"纸笔计算"的方式把 Whisper 的**工程常识**变成可运行的数字：

1. **提示格式**：`<|startoftranscript|><|语言|><|任务|><|notimestamps|>` 怎么拼，语言/任务/时间戳如何切换。
2. **帧预算**：秒数 → mel 帧数 → encoder token 数，理解"30 秒 = 3000 帧 = 1500 token"。
3. **长音频切块**：30 秒窗口、5 秒重叠的切块调度表。
4. **参数量估算**：用公式估算各尺寸 Whisper 的 encoder / decoder / embedding 参数，理解 Turbo 砍掉的是什么。
5. **LoRA 预算**：r=16、只调 `q_proj/v_proj` 时可训练参数有多少。

> 一句话：**面试和方案评审里，能当场算出"多少帧、多少 token、多少参数、LoRA 训多少"的人，比只会调用 `model.transcribe()` 的人可信得多**。不过要注意，本文件的 Turbo 参数估算和 LoRA 估算各有一个 bug（见 3.5、3.6），正好用来练习"验算"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SPECIAL`、`LANG` | 全局字典 | 特殊 token 与语言 token 的字符串 | 多任务提示 |
| `build_prompt` | 函数 | 按语言、任务、是否要时间戳拼出 decoder 提示 | 提示格式 |
| `chunk_schedule` | 函数 | 生成带重叠的 30 秒切块区间 | 长音频切块 |
| `encoder_frames` | 函数 | 秒数 → mel 帧数（不补边公式） | 帧预算 |
| `transformer_params` | 函数 | 估算 encoder / decoder / embedding 参数 | 模型规模 |
| `lora_params` | 函数 | 估算 LoRA 可训练参数（简化版） | 参数高效微调 |
| `main()` | 演示入口 | 6 个步骤 | — |

各函数互相独立，`main()` 依次调用并打印。

---

## 3. 逐段精讲

### 3.1 特殊 token 与提示拼装

```python
SPECIAL = {
    "SOT":            "<|startoftranscript|>",
    "EOT":            "<|endoftext|>",
    "TRANSCRIBE":     "<|transcribe|>",
    "TRANSLATE":      "<|translate|>",
    "NO_TIMESTAMPS":  "<|notimestamps|>",
    "NO_SPEECH":      "<|nospeech|>",
}

LANG = {"en": "<|en|>", "fr": "<|fr|>", "ja": "<|ja|>"}


def build_prompt(language, task="transcribe", timestamps=False):
    toks = [SPECIAL["SOT"], LANG[language]]
    toks.append(SPECIAL["TRANSCRIBE"] if task == "transcribe" else SPECIAL["TRANSLATE"])
    if not timestamps:
        toks.append(SPECIAL["NO_TIMESTAMPS"])
    return toks
```

- 顺序固定：起始符 → 语言 → 任务 →（可选）不要时间戳。decoder 从这串 token 之后开始自回归生成，最后以 `<|endoftext|>` 结束。
- **语言 token 表示音频说的是什么语言**，任务 token 决定转写还是翻译成英文。所以"法语音频翻成英文"是 `<|fr|><|translate|>`（Step 1 的第二行）。
- 要时间戳时**不加** `<|notimestamps|>`，模型会在文本中穿插 `<|0.00|>`、`<|2.40|>` 这类时间戳 token（每 0.02 秒一个，属于 51k 词表）。
- 真实实现里这些都是**token id**，不是字符串；这里用字符串只是为了打印直观。
- ⚠️ `SPECIAL["EOT"]`、`SPECIAL["NO_SPEECH"]` 定义了但没用到。`task` 参数只要不是 `"transcribe"` 就当作翻译，传错字符串（如 `"transcription"`）也不会报错。`LANG[language]` 只有 3 种语言，传 `"de"` 会 `KeyError`。

### 3.2 帧预算

```python
def encoder_frames(seconds, sr=16000, hop=160):
    samples = int(seconds * sr)
    return 1 + (samples - 400) // hop
```

- 用的是第 02 节"不补边"的分帧公式（帧长 400、帧移 160）：1 秒 → 98 帧，10 秒 → 998 帧，30 秒 → **2998 帧**。
- ⚠️ 但紧接着的打印语句说"30 s → 3000 frames"。差 2 帧的原因：Whisper 用 `torch.stft` 时是 center 补边的，帧数为 `1 + 480000 // 160 = 3001`，再丢掉最后一帧得到 3000。这个函数没有模拟这一点。
- ⚠️ 函数名叫 `encoder_frames`，但返回的是 **mel 帧数**；encoder 前端的 stride-2 卷积之后才是 1500 个 encoder token。
- ⚠️ 极短输入会返回负数：`encoder_frames(0.01)` → `1 + (160 − 400) // 160 = 1 + (−2) = −1`（Python 整除向负无穷取整）。

### 3.3 切块调度

```python
def chunk_schedule(total_seconds, chunk_s=30.0, stride_s=5.0):
    if total_seconds <= chunk_s:
        return [(0.0, total_seconds)]
    out = []
    start = 0.0
    step = chunk_s - stride_s
    while start < total_seconds:
        end = min(total_seconds, start + chunk_s)
        out.append((round(start, 2), round(end, 2)))
        if end == total_seconds:
            break
        start += step
    return out
```

- 窗口 30 秒，相邻窗口**重叠** `stride_s = 5` 秒，所以每次前进 `step = 25` 秒。重叠的目的：避免一个词刚好被切在边界上，两侧窗口至少有一个能完整听到它。
- `end = min(total_seconds, start + chunk_s)`：最后一块不越界；`min` 返回的就是 `total_seconds` 本身，所以 `end == total_seconds` 的浮点比较是安全的。
- `if end == total_seconds: break`：最后一块已经覆盖到结尾就停止，避免再生成一个完全落在已覆盖区域内的块。
- 600 秒 → 24 块；`stride_s=0` → 20 块。
- 设计取舍：
  - ⚠️ 只给出区间，不处理重叠区的转写合并（重复文本需要去重或按时间戳裁剪）。
  - ⚠️ 固定时间切块可能切在词中间。讲义推荐的 WhisperX 用 VAD 在静音处切，更自然，也顺便避免把静音送进模型（防幻觉）。
  - `round(..., 2)` 只是为了打印整洁；`start += step` 的累加在步长不是"好数"时会累积浮点误差，更稳妥的写法是 `start = i * step`。

### 3.4 参数量估算公式

```python
def transformer_params(n_layers, d_model, d_ff, n_heads, vocab):
    # per-layer: 4 * d_model^2 (q,k,v,o) + 2 * d_model * d_ff + layer norms
    per_block = 4 * d_model * d_model + 2 * d_model * d_ff + 4 * d_model
    enc = n_layers * per_block
    dec = n_layers * (per_block + 4 * d_model * d_model + 4 * d_model)  # +cross-attn
    embed = vocab * d_model + 3000 * d_model  # token embed + pos embed (audio side 3000)
    return enc, dec, embed
```

- **encoder block**：注意力的 Q、K、V、O 四个 `d×d` 矩阵 → `4d²`；MLP 两个矩阵 `d×d_ff` 和 `d_ff×d` → `2·d·d_ff`；`4d` 近似两个 LayerNorm 的参数（各有 γ、β）。
- **decoder block**：比 encoder 多一个 cross-attention（再一组 `4d²`）和一个 LayerNorm（`+2d`，代码写的是 `+4d`，近似）。
- **embedding**：词表 × d（输出层与输入 embedding 共享权重，只算一次）；再加上位置编码。
- `n_heads` 参数**没有被使用**——多头只是把 `d` 切成几份，不改变参数量，这是一个值得注意的事实。
- 以 Large-v3（32 层、d=1280、d_ff=5120）为例：encoder block 19.67M、decoder block 26.22M；总计 1538.7M，与官方 1.55B 非常接近。
- ⚠️ 近似之处：忽略了 encoder 前端两层卷积（Large 约 5M）和大部分 bias；`3000 * d_model` 也不准确——encoder 的位置编码对应 1500 个位置且是固定的正弦编码（不可训练），decoder 的可学习位置编码是 448 个位置。作为数量级估算可以接受。

### 3.5 Turbo 分支：一个漏算 cross-attention 的 bug

```python
    configs = [
        # ...
        ("Large-v3",   32,  1280,  5120, 20,  51865),
        ("Turbo",       4,  1280,  5120, 20,  51865),  # 4-layer decoder
    ]
    # ...
    for name, layers, d, d_ff, heads, vocab in configs:
        enc, dec, embed = transformer_params(layers, d, d_ff, heads, vocab)
        if name == "Turbo":
            enc_big, _, embed_big = transformer_params(32, d, d_ff, heads, vocab)
            dec = enc  # 4 decoder layers match 4-layer mini
            enc = enc_big
            embed = embed_big
        total = enc + dec + embed
```

- 思路：Turbo = 32 层 encoder + 4 层 decoder。先用 `layers=4` 算一遍，再用 32 层算 encoder。
- ⚠️ **bug**：`dec = enc` 把"4 层 **encoder** block"的参数量赋给了 decoder，而 `transformer_params(4, ...)` 返回的 `dec`（4 层 **decoder** block，含 cross-attention）本来已经是正确的值，却被覆盖了。结果 decoder 只算出 78.7M，正确值约 104.9M；总量 778.2M，修正后约 804.4M，与讲义的 809M 吻合得多。
- 修复：删掉 `dec = enc` 这一行即可。
- `embed = embed_big` 其实是多余的（embedding 与层数无关，两次计算结果相同）。

### 3.6 LoRA 预算：两处简化

```python
def lora_params(n_layers, d_model, rank=16, modules=("q_proj", "v_proj")):
    per_module = 2 * d_model * rank
    per_block = len(modules) * per_module
    return n_layers * 2 * per_block  # encoder + decoder
```

- 每个 LoRA 模块是 `ΔW = B·A`，A 为 `r×d`、B 为 `d×r`，参数 `2·d·r`（第 01 阶段线性代数一节的同一个公式）。r=16、d=1280 时每个模块 40,960 个参数。
- `n_layers * 2` 假设 encoder 与 decoder 层数相同，各层都只有 `q_proj`、`v_proj` 两个目标模块。
- ⚠️ 两处简化导致数字偏小：
  1. Turbo 传入 `layers = 4`，encoder 只按 4 层算了，但 Turbo 的 encoder 有 32 层；
  2. decoder 的 cross-attention 也有 `q_proj`、`v_proj`，在 HF 的 Whisper 实现中 PEFT 按名字匹配会一起加上 LoRA，这里没算。
- 修正后：Turbo `32×81,920 + 4×163,840 = 3,276,800 ≈ 3.28M`，正好对应讲义 Step 3 注释的 "~3M trainable / 809M total"；Large-v3 约 7.86M；Medium 约 4.72M。原代码打印的是 0.655M / 5.243M / 3.146M。
- 结论不变：可训练参数只占总量的 0.4% 左右——这就是 LoRA 能"省显存 4×"的来源（还要加上优化器状态只为这 0.4% 的参数保存）。

### 3.7 Step 5 的循环写法与 Step 6

```python
    for name, layers, d, *_ in configs[3:6]:
        lp = lora_params(layers, d, rank=16)
        print(f"  {name:<10}  LoRA-trainable: {lp/1e6:.3f} M")
```

- `configs[3:6]` 取 Medium、Large-v3、Turbo 三行。
- `name, layers, d, *_ = ...` 是**扩展解包**：只要前三个字段，剩下的打包进 `_` 丢弃。
- Step 6 只是打印讲义 Use It 表格的精简版：离线英文用 `large-v3-turbo + whisperx + Silero VAD`，词级时间戳用 WhisperX，流式用 whisper-streaming 或 Parakeet-TDT，端侧用 whisper-tiny int8 或 Moonshine，低资源语言做 LoRA 微调。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不加载模型，只做"纸笔计算" | 零依赖、零下载，专注建立数量直觉 | 无法验证真实行为；生产中用 `whisper.tokenizer`、`model.num_parameters()` 实测 |
| 用字符串表示特殊 token | 打印直观 | 真实接口是 token id；应使用官方 tokenizer 生成提示 |
| 不补边的帧数公式 | 与第 02 节一致 | 与 Whisper 的 3000 帧差 2 帧；生产直接调用 `whisper.audio.log_mel_spectrogram` |
| 固定时长 + 重叠切块 | 实现简单、可预测 | 可能切在词中间、需要合并重叠文本；生产用 VAD 切块（WhisperX） |
| 参数量公式忽略卷积、bias、位置编码细节 | 抓主要矛盾 | 误差约 1%；Turbo 分支另有漏算 cross-attention 的 bug |
| LoRA 估算假设 enc/dec 同层数、不含 cross-attn | 公式简短 | Turbo 被低估约 5 倍；应分别传入 enc/dec 层数并计入 cross-attention |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 字典常量 | `SPECIAL = {"SOT": "<\|startoftranscript\|>", ...}` | 用有意义的键名代替"魔法字符串" |
| 默认参数 | `def build_prompt(language, task="transcribe", timestamps=False)` | 常用配置作为默认值 |
| 条件表达式 | `SPECIAL["TRANSCRIBE"] if task == "transcribe" else SPECIAL["TRANSLATE"]` | 一行 if-else |
| `str.join` | `' '.join(p_en)` | 用空格把 token 列表拼成字符串 |
| `while` + `break` | `chunk_schedule` 中的循环 | 条件循环；满足结束条件时提前跳出 |
| `min` / `round` | `min(total_seconds, start + chunk_s)`、`round(start, 2)` | 取较小值；保留 2 位小数 |
| 整除 `//`（负数向下取整） | `(samples - 400) // hop` | `-240 // 160 == -2`，不是 -1 |
| 元组列表 | `configs = [("Tiny", 4, 384, 1536, 6, 51865), ...]` | 每行一个配置 |
| 元组解包 | `for name, layers, d, d_ff, heads, vocab in configs` | 一次取出所有字段 |
| 扩展解包 `*_` | `for name, layers, d, *_ in configs[3:6]` | 只取前几个字段，其余丢弃 |
| `_` 丢弃返回值 | `enc_big, _, embed_big = transformer_params(...)` | 不需要的返回值用 `_` 接收 |
| 切片 | `configs[3:6]`、`schedule[:6]` | 取子列表 |
| f-string 格式 | `f"{secs:4.1f}s"`、`f"{start:6.1f} s"`、`f"{name:<10}"`、`f"{total/1e6:7.1f}"` | 宽度 + 精度；`<` 左对齐；可在花括号内做除法 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.02 秒）：

```text
=== Step 1: build a Whisper decoder prompt ===
  EN transcribe, no ts: <|startoftranscript|> <|en|> <|transcribe|> <|notimestamps|>
  FR->EN translate:    <|startoftranscript|> <|fr|> <|translate|> <|notimestamps|>
  JA with timestamps:  <|startoftranscript|> <|ja|> <|transcribe|>

=== Step 2: encoder frame budget ===
   1.0s @16 kHz, 10 ms hop -> 98 frames
  10.0s @16 kHz, 10 ms hop -> 998 frames
  30.0s @16 kHz, 10 ms hop -> 2998 frames
  Whisper zero-pads all inputs to 30 s -> 3000 frames after stride-2 conv -> 1500 encoder tokens

=== Step 3: chunk schedule for a 10-min clip ===
  chunks (30 s window, 5 s stride): 24
       0.0 s ->   30.0 s
      25.0 s ->   55.0 s
      50.0 s ->   80.0 s
      75.0 s ->  105.0 s
     100.0 s ->  130.0 s
     125.0 s ->  155.0 s
    ... (18 more)

=== Step 4: param counts for Large-v3-turbo vs Large-v3 ===
  variant     enc     dec     embed   total  (approx, M params)
  Tiny           7.1     9.4    21.1     37.6
  Base          18.9    25.2    28.1     72.2
  Small         85.0   113.3    42.1    240.4
  Medium       302.1   402.8    56.2    761.1
  Large-v3     629.3   839.2    70.2   1538.7
  Turbo        629.3    78.7    70.2    778.2

=== Step 5: LoRA-r=16 on q_proj,v_proj reduces trainable params 100x+ ===
  Medium      LoRA-trainable: 3.146 M
  Large-v3    LoRA-trainable: 5.243 M
  Turbo       LoRA-trainable: 0.655 M

=== Step 6: 2026 inference recipes ===
  offline English, best WER      -> large-v3-turbo via whisperx + Silero VAD
  ...
```

逐段解读：

- **Step 1**：日语那行没有 `<|notimestamps|>`，表示要求输出时间戳。
- **Step 2**：98 / 998 / 2998 是"不补边"公式的结果；最后一行说明的 3000 → 1500 才是 Whisper 的真实情况（见 3.2）。
- **Step 3**：起点每次 +25 秒，共 24 块；最后一块是 575 → 600 秒。
- **Step 4**：
  - 估算值与官方参数量对比：Tiny 37.6M（官方 39M）、Base 72.2M（74M）、Small 240.4M（244M）、Medium 761.1M（769M）、Large-v3 1538.7M（1.55B）——误差都在 1–4%，主要来自被忽略的卷积和 bias。
  - 小模型的 embedding 占比很大：Tiny 的 21.1M embedding 超过一半参数，因为词表 51,865 × 384 是固定开销。
  - decoder 比 encoder 大约 33%，多出的就是 cross-attention。
  - ⚠️ Turbo 的 `dec = 78.7` 偏小（应约 104.9），总量应约 804M（官方 809M），见 3.5。
- **Step 5**：⚠️ 三个数字都偏小，Turbo 尤甚（0.655M vs 正确的约 3.28M），见 3.6。即便按修正后的数字，LoRA 也只训练约 0.4% 的参数，标题"100x+"的结论依然成立。

---

## 7. 动手改一改

1. **修 Turbo bug**：删掉 `dec = enc`，确认 Turbo 一行变为约 `629.3 104.9 70.2 804.4`。
2. **修 LoRA 估算**：改写为 `lora_params(n_enc, n_dec, d_model, rank=16)`，decoder 每层计入 4 个模块（自注意力 + cross-attention 的 q/v），确认 Turbo ≈ 3.277M、Large-v3 ≈ 7.864M。
3. **修帧数**：把 `encoder_frames` 改成 center 补边并丢掉最后一帧的版本：`(samples // hop + 1) - 1`，再除以 2 得到 encoder token 数；确认 30 秒 → 3000 → 1500，并对 0.01 秒不再返回负数。
4. **扩展提示**：给 `build_prompt` 加一个 `prev_text` 参数，在 `<|startoftranscript|>` 前面加上 `<|startofprev|>` 和上一段文本（Whisper 的 `condition_on_previous_text` 就是这样把上文喂给 decoder 的），思考为什么这会导致幻觉级联。
5. **合并重叠转写**：假设每块输出带词级时间戳的列表 `[(word, t_start, t_end), ...]`，实现"每块只保留距离块边界超过 2.5 秒的词"的合并函数，在一个人工构造的例子上测试。
6. **对照真实模型**（需要联网和安装 `transformers`，本环境不具备）：加载 `openai/whisper-large-v3-turbo`，用 `sum(p.numel() for p in model.parameters())` 与估算值对比；套上 `LoraConfig(r=16, target_modules=["q_proj","v_proj"])` 后调用 `print_trainable_parameters()`，验证约 3.28M。

---

## 8. 常见坑

- **语言 token 与任务 token 混淆**：语言 token 描述音频的语言，任务 token 决定转写还是翻译；"法语 → 英文"是 `<|fr|><|translate|>`，不是 `<|en|>`。
- **帧数差一两帧**：分帧时是否补边（center）、是否丢掉最后一帧，会让帧数差 1–3 帧；与预训练模型对接时要逐一核对，最好直接调用官方预处理。
- **把 mel 帧数当成 encoder 序列长度**：中间还有一个 stride-2 卷积；30 秒对应 1500 个 encoder 位置，时间戳粒度 0.02 秒正是由此而来。
- **参数估算漏算 cross-attention**：encoder-decoder 模型的 decoder 每层比 encoder 多一组注意力；本文件的 Turbo 和 LoRA 估算都栽在这里。
- **LoRA 的 target_modules 按名字匹配**：`["q_proj", "v_proj"]` 会同时命中自注意力和 cross-attention，可训练参数比"只算自注意力"多；需要时用更精确的模块路径限定。
- **重叠切块不去重**：5 秒重叠区的内容会被转写两次，直接拼接会出现重复句子。
