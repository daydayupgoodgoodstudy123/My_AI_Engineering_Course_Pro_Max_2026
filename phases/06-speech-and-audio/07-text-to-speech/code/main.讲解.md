# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 07 节 文本转语音 (TTS) — 从 Tacotron 到 F5 和 Kokoro ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在 `code/` 目录下 `python3 main.py`（docstring 写的是在小节根目录运行 `python3 code/main.py`，效果相同），无命令行参数 ｜ **依赖**：仅 Python 标准库（`random`；`math` 被导入但没有用到）。不会真的合成声音，真实合成需要安装 kokoro 或 f5-tts（见讲义）

---

## 1. 这份代码在考察什么

这份脚本不发出任何声音，它只模拟 TTS 管线里**声学模型之前和之内**的"排时间表"工作，让你看清一段文字是怎样变成"多少个 mel 帧、多少个采样点"的：

1. **文本前端 / G2P**：用一张玩具字形→音素表（ARPABet 风格符号）做贪心最长匹配，体会"音素是通用桥梁"，也亲眼看到没有文本归一化时数字会被丢掉。
2. **时长预测（duration）**：FastSpeech 2 这类非自回归模型的核心是"每个音素占几帧"。代码用一张查表 + 随机扰动来代替真正的 duration predictor。
3. **mel 帧时间表**：把整数帧数乘以 hop（12.5 ms）累加，得到每个音素的起止时间——这就是 length regulator 展开后的时间轴。
4. **帧 ↔ 采样点 ↔ 内存的换算**：12.5 ms × 24 kHz = 300 个采样点/帧，这个数必须与 vocoder 的上采样倍率一致。
5. **2026 年的质量榜**：把讲义中的 UTMOS / CER / 参数量表格打印出来，建立"质量—体积"的直觉。

> 一句话：**用不到 140 行标准库代码，把"文本 → 音素 → 帧数 → 时间轴 → 采样点"这条链路的每一步都摊开给你看**，真正的神经网络只是把其中的查表换成了学习出来的预测器。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `G2P` | 字典常量 | 字形片段（1–3 个字符）→ 音素列表；标点映射为停顿符号 | 文本前端、grapheme-to-phoneme |
| `DURATION_FRAMES` | 字典常量 | 每个音素的典型帧数（12.5 ms hop） | FastSpeech 2 的 duration 统计 |
| `phonemize(text)` | 函数 | 小写化后从左到右贪心最长匹配，输出音素序列 | G2P |
| `duration(phones, jitter, seed)` | 函数 | 查表得到基础帧数，加 ±10% 随机扰动，至少 1 帧 | duration predictor（替身） |
| `mel_schedule(phones, durs, hop_ms)` | 函数 | 累加时间，返回每个音素的 `(音素, 起始 ms, 结束 ms)` 和总时长 | length regulator / 对齐 |
| `main()` | 函数 | 依次打印 5 个步骤的结果 | 整条管线的演示 |

数据流：`text → phonemize → phones → duration → durs → mel_schedule → (schedule, total_ms)`，最后再用 `sum(durs)` 换算采样点和内存。

---

## 3. 逐段精讲

### 3.1 `G2P` 表：把"规则"写成数据

```python
G2P = {
    " ":    ["_"],
    "a":    ["AH"],  "b":    ["B"],  "c":    ["K"],  "d":    ["D"],  "e":    ["EH"],
    # ...
    "u":    ["UH"],  "v":    ["V"],  "w":    ["W"],  "x":    ["K", "S"],
    # ...
    "the":  ["DH", "AH"],
    "ing":  ["IH", "NG"],
    "er":   ["ER"],
    "sh":   ["SH"],
    # ...
    ".":    ["_PAUSE_"],
    ",":    ["_SHORT_"],
    "?":    ["_PAUSE_"],
    "!":    ["_PAUSE_"],
}
```

- 键是字形片段（1–3 个字符），值是**音素列表**——因为一个字母可能对应多个音素，例如 `"x" → ["K", "S"]`。值统一用列表，后面就能统一用 `extend` 拼接。
- 音素符号用的是 ARPABet 风格（`AH`、`DH`、`NG`…），讲义 Key Terms 提到英语在 ARPABet 中有 39 个音素。
- 空格映射为 `"_"`（词边界），标点映射为两种停顿：逗号 `_SHORT_`、句末 `_PAUSE_`。这说明**韵律（停顿）信息也是在文本前端产生的**。
- ⚠️ 刻意简化：每个字母只有一种读法（`"a"` 永远是 `AH`），完全不处理英语的不规则拼读；源码注释也说明真实系统用 espeak-ng 或 g2p-en（CMU 词典）。
- ⚠️ 表里没有数字。这正好演示了讲义 Pitfalls 的第一条："No text normalizer"。

### 3.2 `phonemize`：贪心最长匹配

```python
def phonemize(text):
    text = text.lower()
    phones = []
    i = 0
    while i < len(text):
        matched = False
        for length in (3, 2, 1):
            if i + length <= len(text):
                chunk = text[i : i + length]
                if chunk in G2P:
                    phones.extend(G2P[chunk])
                    i += length
                    matched = True
                    break
        if not matched:
            i += 1
    return phones
```

- **为什么从 3 试到 1**：先尝试最长的片段，这样 `"sh"` 会被识别成 `SH` 而不是 `S` + `HH`，`"the"` 会被识别成 `DH AH`。这叫**贪心最长匹配（greedy longest match）**，分词器、词法分析器里也常见。
- `if i + length <= len(text)` 防止切片越界取到不足长度的片段（Python 切片越界不会报错，但会得到更短的字符串，可能误匹配）。
- `matched` 是一个**标志变量**：内层 `for` 找到匹配就 `break`；如果三种长度都没匹配，外层就 `i += 1` 跳过这个字符。
- ⚠️ 跳过未知字符是**静默**的：`"6"` 不在表里，直接消失，所以示例句里的 "at 6 pm" 最后只剩 `AH T _ _ P M`。生产系统应该在 G2P 之前做归一化（6 → six），并对 OOV 有兜底而不是丢弃。
- ⚠️ 没有单词边界概念：`"mother"` 会在位置 2 先匹配到 `"the"`，结果是 `M AO DH AH R`，`"er"` 被拆散了。"Dr." 中的句点也会被当作句末停顿 `_PAUSE_`。
- 复杂度：每个位置最多尝试 3 次字典查找，O(n)。

### 3.3 `DURATION_FRAMES` 与 `duration`：duration predictor 的替身

```python
# Typical durations (frames @ 12.5 ms hop); roughly matches FastSpeech stats
DURATION_FRAMES = {
    "AA": 9, "AE": 7, "AH": 6, "AO": 8, "AW": 9, "AY": 8, "B": 4, "CH": 6,
    # ...
    "_": 3,           # word boundary
    "_SHORT_": 6,     # comma pause
    "_PAUSE_": 12,    # sentence pause
}

def duration(phones, jitter=0.1, seed=0):
    random.seed(seed)
    out = []
    for p in phones:
        base = DURATION_FRAMES.get(p, 5)
        noise = int(round(base * random.uniform(-jitter, jitter)))
        out.append(max(1, base + noise))
    return out
```

- 表里元音（`AA` 9 帧、`AW` 9 帧）普遍比塞音（`B`、`D`、`T` 4 帧）长，符合语音学直觉；句末停顿 12 帧 = 150 ms，逗号 6 帧 = 75 ms。
- `DURATION_FRAMES.get(p, 5)`：查不到的音素默认 5 帧，避免 `KeyError`。
- `jitter` 模拟"同一个音素在不同语境下长短不同"。真正的 FastSpeech 2 是一个神经网络，根据上下文为每个音素预测时长；这里用查表 + 均匀噪声代替。
- `max(1, ...)`：每个音素至少 1 帧，否则这个音素在输出中会被"吃掉"。这是 length regulator 的硬约束。
- ⚠️ 量化吃掉了抖动：`noise = round(base × U(-0.1, 0.1))`，当 `base ≤ 5` 时 `|base × 0.1| ≤ 0.5`，取整后恒为 0。实际运行中大多数辅音的帧数与查表值完全一样，只有 6 帧以上的音素偶尔 ±1。
- ⚠️ `random.seed(seed)` 修改的是**全局**随机状态，会影响同一进程中所有使用 `random` 模块的代码。更干净的写法是 `rng = random.Random(seed)`。

### 3.4 `mel_schedule`：把帧数铺成时间轴

```python
def mel_schedule(phones, durs, hop_ms=12.5):
    schedule = []
    t = 0.0
    for p, d in zip(phones, durs):
        schedule.append((p, t, t + d * hop_ms))
        t += d * hop_ms
    return schedule, t
```

- 每个音素占 `d` 帧，每帧 `hop_ms` 毫秒，所以它的区间是 `[t, t + d × hop)`；`t` 不断累加，得到首尾相接的时间轴。
- 这就是 FastSpeech 的 **length regulator** 在时间维度上的样子：把音素序列按时长"拉伸"成帧序列，再交给 decoder 生成 mel。
- 函数返回一个**元组** `(schedule, t)`，调用方用 `sched, total_ms = mel_schedule(...)` 一次拿到两个结果。
- 12.5 ms 是 hop（相邻两帧的间隔），不是窗长；第 02 节讲过 mel 帧是带重叠的短时窗口。
- ⚠️ 用浮点累加时间，长句会积累极小的舍入误差；更稳妥的是累加整数帧数，再统一乘以 hop。

### 3.5 `main()` 的 Step 4：帧 → 采样点 → 内存

```python
    total_frames = sum(durs)
    audio_samples = total_frames * 300  # 12.5 ms @ 24 kHz = 300 samples
    print(f"  mel frames: {total_frames}  audio samples @ 24 kHz: {audio_samples}")
    print(f"  pipeline memory budget: {total_frames * 80 * 4 / 1024:.1f} KB (mel, float32)")
```

- `0.0125 s × 24000 Hz = 300`：每个 mel 帧对应 300 个波形采样点。vocoder 的工作就是把每一帧"展开"成这 300 个点，所以 vocoder 的总上采样倍率必须等于 300。
- 讲义 Step 4 的 HiFi-GAN 用 `upsample_rates=[8, 8, 2, 2]`，乘积为 256，对应的是 hop = 256 个采样点的配置。两处数字不同不是错误，而是两套不同的参数；但它提醒你：**声学模型和 vocoder 必须使用同一个 hop**，否则时长和音高都会错。
- 内存：`帧数 × 80 个 mel 通道 × 4 字节（float32）`。210 帧只有约 65.6 KB，mel 本身很小；真正占内存的是模型权重和波形（63000 个 float32 采样点约 246 KB）。
- 24 kHz 与讲义中 Kokoro 的输出采样率一致；如果下游是 16 kHz，需要重采样。

### 3.6 Step 3 和 Step 5：打印格式

```python
    print(f"  first 10 frames:")
    for p, s, e in sched[:10]:
        print(f"    {p:<10} {s:6.1f} – {e:6.1f} ms")
```

- `sched[:10]` 取前 10 个元素，`for p, s, e in ...` 直接把三元组解包成三个变量。
- ⚠️ 标签写的是 "first 10 frames"，但 `sched` 的每一项是一个**音素段**（可能跨 4–12 帧），打印的其实是"前 10 个音素的时间区间"。这里的 `f"  first 10 frames:"` 也没有任何占位符，`f` 前缀是多余的。

```python
    table = [
        ("ground truth",   4.08, 1.2,   "—"),
        ("F5-TTS",         3.95, 2.1,   "335M"),
        # ...
    ]
    print("  | Model             | UTMOS | CER%  | Size |")
    for name, u, c, s in table:
        print(f"  | {name:<17} | {u:.2f}  | {c:.1f}   | {s:<4} |")
```

- 这是讲义里 LibriTTS test-clean 表格的**硬编码副本**（按 UTMOS 从高到低排序），不是现场测出来的。
- 值得读出的结论：Kokoro 只有 82M，CER 1.8% 却比 335M 的 F5-TTS（2.1%）还低；Parler-TTS Large 2.3B 参数并没有换来更高的 UTMOS——**参数量不等于质量**。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 字符级查表 G2P | 不依赖 espeak / CMU 词典，标准库即可运行 | 不规则拼读全错；生产用 espeak-ng、g2p-en + 词典 + OOV 模型 |
| 未知字符静默跳过 | 代码短，不会崩 | 数字、符号被丢掉；生产必须先做文本归一化 |
| 查表 + 均匀噪声代替 duration predictor | 让"每个音素几帧"这个概念直观可见 | 无上下文；真实模型按上下文预测，且小帧数下的噪声被取整吃掉 |
| 固定 `seed` | 结果可复现，便于讲解 | 使用全局 `random.seed`，有副作用；应使用 `random.Random(seed)` |
| hop 12.5 ms、24 kHz、80 维 mel | 常见 TTS 配置，算出 300 采样点/帧这个整数 | 必须与 vocoder 的上采样倍率一致（讲义 HiFi-GAN 示例是 256） |
| 质量表硬编码 | 让学习者一眼看到 2026 年的模型格局 | 数字会过时；真实对比要在同一测试集上自己跑 UTMOS / CER |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块文档字符串 | 文件开头的 `"""TTS internals demo: ..."""` | 说明用途和运行方式，`help()` 能读到 |
| 字典字面量（值为列表） | `"x": ["K", "S"]` | 一个键对应多个值时用列表做值 |
| `str.lower()` | `text = text.lower()` | 统一小写，让查表不区分大小写 |
| `while` + 手动下标 | `while i < len(text): ... i += length` | 步长不固定（1、2 或 3）时比 `for` 更合适 |
| 遍历元组 | `for length in (3, 2, 1):` | 按指定顺序尝试多个候选值 |
| 字符串切片 | `text[i : i + length]` | 取子串；越界不会报错，只会变短 |
| `in` 判断字典键 | `if chunk in G2P:` | O(1) 的成员判断 |
| `list.extend` vs `append` | `phones.extend(G2P[chunk])`、`out.append(...)` | `extend` 把列表元素逐个加入；`append` 加入一个整体 |
| 标志变量 + `break` | `matched = True; break` | 跳出内层循环并告诉外层"已找到" |
| `dict.get(key, default)` | `DURATION_FRAMES.get(p, 5)` | 键不存在时返回默认值，不抛 `KeyError` |
| 默认参数 | `def duration(phones, jitter=0.1, seed=0)` | 调用时可省略这些参数 |
| `random` 模块 | `random.seed(seed)`、`random.uniform(-jitter, jitter)` | 设种子保证可复现；均匀分布采样 |
| `int(round(x))` 与 `max` | `int(round(base * ...))`、`max(1, base + noise)` | 取整并设下限；注意 `round` 对 .5 采用银行家舍入 |
| `zip` | `for p, d in zip(phones, durs):` | 把两个等长序列按位置配对 |
| 返回元组 / 元组解包 | `return schedule, t`；`sched, total_ms = mel_schedule(...)` | 一次返回、接收多个值 |
| 列表切片 + 解包循环 | `for p, s, e in sched[:10]:` | 取前 10 项，并把每个三元组拆成三个变量 |
| f-string 格式符 | `{text!r}`、`{p:<10}`、`{s:6.1f}`、`{u:.2f}` | `!r` 用 `repr` 显示（带引号）；`<10` 左对齐占 10 格；`6.1f` 宽 6、1 位小数 |
| f-string 中的条件表达式 | `{'...' if len(phones) > 20 else ''}` | 超过 20 个才显示省略号 |
| `str.join` | `' '.join(phones[:20])` | 用空格把列表拼成字符串 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，被导入时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时不到 1 秒）的完整输出：

```text
=== Step 1: grapheme to phoneme ===
  text: 'Please remind me to water the plants at 6 pm.'
  phones (42): P L EH AH S EH _ R EH M IH N D _ M EH _ T AO _...

=== Step 2: estimate per-phoneme duration ===
  durations (frames): [5, 5, 6, 6, 6, 6, 3, 5, 6, 5, 5, 5, 4, 3, 5, 6, 3, 4, 8, 3]...

=== Step 3: mel frame schedule (12.5 ms hop) ===
  total duration: 2625.0 ms  (2.62 s)
  first 10 frames:
    P             0.0 –   62.5 ms
    L            62.5 –  125.0 ms
    EH          125.0 –  200.0 ms
    AH          200.0 –  275.0 ms
    S           275.0 –  350.0 ms
    EH          350.0 –  425.0 ms
    _           425.0 –  462.5 ms
    R           462.5 –  525.0 ms
    EH          525.0 –  600.0 ms
    M           600.0 –  662.5 ms

=== Step 4: total mel frames sent to vocoder ===
  mel frames: 210  audio samples @ 24 kHz: 63000
  pipeline memory budget: 65.6 KB (mel, float32)

=== Step 5: 2026 TTS quality board (UTMOS / CER / size) ===
  | Model             | UTMOS | CER%  | Size |
  | ground truth      | 4.08  | 1.2   | —    |
  | F5-TTS            | 3.95  | 2.1   | 335M |
  | Kokoro v0.19      | 3.87  | 1.8   | 82M  |
  | XTTS v2           | 3.81  | 3.5   | 470M |
  | Parler-TTS L      | 3.76  | 2.8   | 2.3B |
  | VITS              | 3.62  | 3.1   | 25M  |
```

逐段解读：

- **Step 1**：42 个音素。"please" 被念成 `P L EH AH S EH`——"ea" 被拆成两个元音、末尾不发音的 "e" 也被念了出来，这就是字符级 G2P 的局限。完整序列的结尾是 `... AH T _ _ P M _PAUSE_`："6" 被静默丢弃，留下两个连续的词边界 `_ _`。
- **Step 2**：前几个值 `5, 5, 6, 6, 6, 6` 与查表值（P=5、L=5、EH=6、AH=6、S=6、EH=6）完全一样——小帧数下 ±10% 的抖动被取整吃掉了。完整列表最后一个是 `11`（`_PAUSE_` 的基础值 12 被扰动成 11）。
- **Step 3**：总时长 2625 ms = 210 帧 × 12.5 ms，与讲义开头"需要一段约 3 秒的音频"同一量级。时间表首尾相接：P 结束于 62.5 ms，L 就从 62.5 ms 开始。词边界 `_` 只有 3 帧 = 37.5 ms。
- **Step 4**：`210 × 300 = 63000` 个采样点，正好 2.625 s × 24000；mel 内存 `210 × 80 × 4 / 1024 = 65.625 KB`。
- **Step 5**：讲义表格的复述。注意它是**硬编码**的，不随运行变化。

---

## 7. 动手改一改

1. 在 `G2P` 里加入 `"ea": ["IY"]`、`"ck": ["K"]`，重新运行，观察 "please" 的音素和总时长如何变化。
2. 写一个 `normalize(text)`：把 0–9 转成英文单词、把 "Dr." 展开为 "doctor"、"pm" 展开为 "p m"，在 `phonemize` 之前调用，确认 "6" 不再丢失。
3. 把 `duration` 改成使用 `rng = random.Random(seed)`，并改为"浮点累计再取整"，验证小帧数音素也能得到扰动，同时总帧数基本不变。
4. 给 `mel_schedule` 加一个 `speed` 参数（例如 1.2 表示加速），把每个音素的帧数除以 `speed` 后取整（至少 1 帧），体会 FastSpeech 类模型"直接改时长即可控制语速"的优势。
5. 把 hop 改成 256 个采样点 @ 22.05 kHz（约 11.6 ms），同步修改 Step 3 和 Step 4 的常数，让它与讲义中 `upsample_rates=[8, 8, 2, 2]` 的 HiFi-GAN 对齐。
6. 进阶：安装 Kokoro（讲义 Step 2），用 Whisper 转写合成结果并计算 CER，复现讲义的"CER via ASR"评测流程。

---

## 8. 常见坑

- **静默丢弃未知字符**：数字、货币符号、表情符号直接消失，用户听到的句子缺字却没有任何报错。生产中要在 G2P 之前做归一化，并记录 OOV。
- **把标点一律当句末停顿**："Dr."、"e.g."、"3.14" 中的句点都会变成 150 ms 的停顿，句子被切碎。
- **全局 `random.seed`**：在库函数里设全局种子，会悄悄改变调用方其他代码的随机行为。
- **hop 与 vocoder 不一致**：本文件按 300 采样点/帧计算，讲义的 HiFi-GAN 示例是 256×；混用会让输出时长和音高同时出错。
- **把 "first 10 frames" 当成帧**：打印的是音素段，每段包含多个帧；读输出时不要误解。
- **浮点累加时间**：长文本里 `t += d * hop_ms` 会积累误差；对齐、剪辑类任务应以整数帧为准。
