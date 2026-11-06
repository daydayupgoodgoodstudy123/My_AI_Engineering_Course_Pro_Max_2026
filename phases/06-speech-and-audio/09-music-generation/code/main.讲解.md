# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 09 节 音乐生成——MusicGen、Stable Audio、Suno 与许可制度的剧变 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在 `code/` 目录下 `python3 main.py`（docstring 写的是在小节根目录运行 `python3 code/main.py`），无命令行参数 ｜ **依赖**：仅 Python 标准库（`random`，实际上也没有真正用到随机性）

---

## 1. 这份代码在考察什么

docstring 说得很直白：这是一个"音乐生成卡通"（music-generation cartoon）。真正的音乐生成用神经编解码器语言模型（MusicGen、ACE-Step）或潜扩散（Stable Audio），而这份代码在**符号层面**演示"随时间排列的 token"这个思想：

1. **提示词 → 结构化参数**：从自然语言里抽取调（key）、风格（genre）、速度（BPM）。这对应真实系统中的"文本条件"。
2. **符号化的音乐 token**：和弦用级数（1–7）表示，再映射到具体调；鼓点用 16 步网格的字符表示（`X` 底鼓、`o` 军鼓、`.` 休止）。
3. **按时间平铺**：把 4 小节的和弦循环、1 小节的鼓点模式平铺到 8 小节——"token over time"的最小形态。
4. **2026 模型速查表**：把讲义的模型地图打印出来，并给出开源/商业/法律的要点。

> 一句话：**用查表 + 字符串拼接，把"音乐是随时间排列的离散符号"讲清楚**；顺便，它的提示词解析里藏着两个值得动手修的 bug。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `MAJOR_KEYS` | 字典常量 | 4 个大调中按 I–vii° 排列的 7 个顺阶和弦 | 调性与和弦级数 |
| `COMMON_PROGRESSIONS` | 字典常量 | 5 种风格的 4 和弦级数进行 | 风格 → 和声模板 |
| `DRUM_PATTERNS` | 字典常量 | 5 种风格的 16 步鼓点（1 小节） | 节奏 token 网格 |
| `chord_progression(key, genre, bars)` | 函数 | 级数进行循环到 `bars` 小节并映射为具体和弦 | 和声序列生成 |
| `drum_pattern(genre, bars)` | 函数 | 1 小节鼓点重复 `bars` 次 | 节奏序列生成 |
| `fake_generate(prompt, rng)` | 函数 | 从提示词解析调、风格、BPM，组装成一首"曲子"字典 | 文本条件 → 生成 |
| `visualize(piece)` | 函数 | 打印曲子的参数、和弦、鼓点 | 输出展示 |
| `main()` | 函数 | 4 个提示词的演示 + 模型速查表 + 要点 | 整体演示 |

数据流：`prompt → fake_generate`（解析出 `key / genre / bpm`）→ 调用 `chord_progression` 和 `drum_pattern` → 返回字典 → `visualize` 打印。

---

## 3. 逐段精讲

### 3.1 三张查表：把乐理写成数据

```python
MAJOR_KEYS = {
    "C": ["C", "Dm", "Em", "F", "G", "Am", "Bdim"],
    "G": ["G", "Am", "Bm", "C", "D", "Em", "F#dim"],
    # ...
}

COMMON_PROGRESSIONS = {
    "pop":     [1, 5, 6, 4],
    "ballad":  [1, 6, 4, 5],
    "jazz":    [2, 5, 1, 6],
    "rock":    [1, 4, 5, 1],
    "lofi":    [6, 4, 1, 5],
}

DRUM_PATTERNS = {
    "pop":    "X.o.X.o.X.o.X.o.",
    # ...
    "lofi":   "X...o...X...o.o.",
    "jazz":   "X.oox.oxX.oox.ox",
    "trap":   "Xooox.oxXooox.ox",
}
```

- `MAJOR_KEYS` 的每个列表按大调顺阶和弦排列：I 大、ii 小、iii 小、IV 大、V 大、vi 小、vii° 减。这样"级数"就成了与调无关的**相对 token**，换调只需换一张表——这与"同一旋律换音色"的旋律条件思想类似。
- `COMMON_PROGRESSIONS` 是经典进行：pop 的 I–V–vi–IV、jazz 的 ii–V–I–vi 等。
- `DRUM_PATTERNS` 每个字符串 16 个字符，代表一小节的 16 个十六分音符位置。
- ⚠️ 图例只说明了 `kick=X snare=o`，但 jazz、trap 模式里出现的小写 `x` 没有定义（可以理解为踩镲/叠钹之类，代码没说明）。
- ⚠️ 这些模式是示意性的：只有 lofi 的 `X...o...X...o.o.` 是"底鼓在 1、3 拍，军鼓在 2、4 拍"的经典反拍；pop 的写法是每拍底鼓、每个反拍八分音符军鼓，不必当作标准鼓谱。
- ⚠️ 表之间不对齐：`trap` 只有鼓点没有和弦进行，`ballad` 只有和弦进行没有鼓点。由于风格只从 `COMMON_PROGRESSIONS` 里识别，`trap` 鼓点永远用不到；`ballad` 的鼓点会回落到 pop。

### 3.2 `chord_progression`：循环、截断、映射

```python
def chord_progression(key, genre, bars=8):
    scale = MAJOR_KEYS[key]
    pat = COMMON_PROGRESSIONS.get(genre, COMMON_PROGRESSIONS["pop"])
    repeats = bars // len(pat) + 1
    seq = (pat * repeats)[:bars]
    return [scale[i - 1] for i in seq]
```

- `dict.get(genre, 默认值)`：未知风格回落到 pop，不抛 `KeyError`。
- `pat * repeats`：列表乘法把列表重复多次；`+ 1` 保证即使 `bars` 不是 4 的倍数也够长，再用 `[:bars]` 截断。`bars=8` 时会多算一轮（12 个再截到 8 个），无害。
- `scale[i - 1]`：乐理级数从 1 开始，Python 下标从 0 开始，所以要减 1。
- 每小节一个和弦，这就是一条长度为 `bars` 的"和弦 token 序列"。

### 3.3 `drum_pattern`：字符串平铺

```python
def drum_pattern(genre, bars=8):
    base = DRUM_PATTERNS.get(genre, DRUM_PATTERNS["pop"])
    return (base * bars)[: bars * 16]
```

- 字符串乘法 `base * bars` 把一小节重复 `bars` 次；`[: bars * 16]` 截断在这里其实是多余的（长度已经正好是 `bars × 16`），起保险作用。
- 8 小节 × 16 步 = 128 个字符。与真实模型对比：每个字符代表一个十六分音符，在 120 BPM 下是 125 ms；而 MusicGen 生成的是编解码器 token，按 MusicGen 论文为每秒 50 帧、每帧 4 个 codebook，时间分辨率高得多、也"不可读"得多。
- ⚠️ 每一小节都完全一样，没有过门（fill）和变化——真实音乐生成模型的难点恰恰在于"重复与变化的平衡"，讲义 Pitfalls 说 AR 模型超过 30 秒会陷入循环。

### 3.4 `fake_generate`：提示词解析（含两个 bug）

```python
def fake_generate(prompt, rng=None):
    rng = rng or random.Random(0)
    prompt_lower = prompt.lower()
    key = "C"
    for k in MAJOR_KEYS:
        if f" {k.lower()}" in " " + prompt_lower:
            key = k
            break
    genre = "pop"
    for g in COMMON_PROGRESSIONS:
        if g in prompt_lower:
            genre = g
            break
    bars = 8
    bpm = 120
    for token in prompt_lower.split():
        if token.endswith("bpm"):
            try:
                bpm = int(token[:-3])
            except ValueError:
                pass
    return {
        "key": key,
        # ...
        "chords": chord_progression(key, genre, bars),
        "drums": drum_pattern(genre, bars),
    }
```

- `rng = rng or random.Random(0)`：常见的"可选依赖注入"写法——调用方可以传入自己的随机数生成器，否则用固定种子。⚠️ 但 `rng` 之后**一次都没用到**，生成过程完全确定。真实模型的采样（温度、top-k）才是多样性的来源。
- **调性识别 bug**：`f" {k.lower()}" in " " + prompt_lower` 在提示词前补一个空格，然后查找"空格 + 调名字母"。它只看单词首字母，所以任何以 c/g/d/a 开头的单词都会被当成调号。实测 `"gentle ballad in D"` → G（"gentle"）、`"chill lofi in A"` → C（"chill"）、`"pop punk at 170 BPM"` → A（"at"）。本文件的 4 个示例提示词恰好没触发这个问题。
- **风格识别**：子串匹配 + 先到先得。"jazz swing" 能识别为 jazz；但不在表里的风格（如 trap、hip-hop）都会回落到 pop。
- **BPM 解析 bug**：`split()` 把 "128 bpm" 切成 `"128"` 和 `"bpm"`；只有 `"bpm"` 以 "bpm" 结尾，而 `int("")` 抛 `ValueError` 被静默吞掉，BPM 保持 120。实测只有写成 "128bpm" 才能解析。运行输出里两个带 BPM 的提示词都显示 `tempo: 120 bpm`，就是这个原因。
- ⚠️ 两个 bug 的共同教训：`try/except: pass` 和"找不到就用默认值"会把解析失败**隐藏**起来。讲义 Pitfalls 的"Tempo drift"提醒我们要用 beat tracking 在生成后核对 BPM——在这份代码里，连 BPM 都没传进去。修复写法见测验 Q8、Q9（用正则 `(\d{2,3})\s*bpm\b` 和 `\bin\s+([a-g][#b]?)\b`）。
- 返回一个字典作为"曲子"的结构化表示，便于后续打印或渲染成 MIDI（讲义 Exercise 1 提到可以用 MIDI 渲染器播放）。

### 3.5 `visualize` 与 `main`：展示与速查表

```python
def visualize(piece):
    print(f"  key: {piece['key']}  genre: {piece['genre']}  tempo: {piece['bpm']} bpm  bars: {piece['bars']}")
    print(f"  chords: {' | '.join(piece['chords'])}")
```

- f-string 里访问字典要用另一种引号：外层双引号，内层 `piece['key']` 用单引号。
- `' | '.join(...)` 用竖线把和弦拼成类似乐谱小节线的样子。

```python
    models = [
        ("MusicGen-large",     3300, "30 s",  "no",  "MIT"),
        # ...
        ("Suno v5 (closed)",      0, "4 min",  "yes", "commercial"),
    ]
    print("  | model               | params (M) | length | vocals | license        |")
    for name, p, length, v, lic in models:
        print(f"  | {name:<20} | {p:>10} | {length:>6} | {v:<12} | {lic:<14} |")
```

- 每个元组 5 个字段，`for name, p, length, v, lic in models` 一次解包。
- `{p:>10}` 右对齐数字，`{name:<20}` 左对齐文本。⚠️ 表头的列宽与数据行不一致（如 `vocals` 列表头宽 6、数据宽 12），所以打印出来的竖线没对齐。
- ⚠️ 闭源模型的参数量用 `0` 表示"未知"，而讲义表中是 `?`；直接读表容易误解为"0 参数"。用 `None` 并打印成 `?` 更清楚。
- ⚠️ 许可列沿用讲义的 "MIT"。注意 audiocraft 官方说明中 MIT 是**代码**许可，MusicGen 预训练**权重**是 CC-BY-NC 4.0；商用前务必分别核查代码、权重、训练数据和生成物的条款。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 符号层（和弦级数、鼓点字符）代替音频 | 可读、可手算，直观展示"token over time" | 没有音色、力度、人声；真实模型生成神经编解码器 token 或潜变量 |
| 级数 + 调表的两级映射 | 与调无关的相对表示，换调只换表 | 只支持 4 个大调，不支持小调、转调 |
| 查表 + 子串匹配解析提示词 | 零依赖，代码短 | 误识别调性、丢失 BPM；生产中用正则/解析器或直接把文本编码为条件 embedding |
| 不使用随机性 | 输出可复现，便于讲解 | 没有多样性；`rng` 参数形同虚设 |
| 4 小节进行 + 1 小节鼓点平铺 | 一眼看出"循环结构" | 恰好演示了讲义说的"重复/漂移"问题：没有任何段落变化 |
| 速查表硬编码 | 一屏看完模型格局 | 数字和许可会过时，`0` 表示未知容易误读 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 字典常量（值为列表 / 字符串） | `MAJOR_KEYS`、`DRUM_PATTERNS` | 用数据表达规则 |
| `dict.get(key, default)` | `COMMON_PROGRESSIONS.get(genre, COMMON_PROGRESSIONS["pop"])` | 找不到键时用默认值 |
| 整除 `//` | `bars // len(pat) + 1` | 向下取整的除法 |
| 列表乘法 / 字符串乘法 | `pat * repeats`、`base * bars` | 把序列重复 n 次 |
| 切片截断 | `(pat * repeats)[:bars]`、`token[:-3]` | 取前 n 个；`[:-3]` 去掉最后 3 个字符 |
| 列表推导 | `[scale[i - 1] for i in seq]` | 逐个映射 |
| `x or 默认值` | `rng = rng or random.Random(0)` | 参数为 `None` 时提供默认对象 |
| 遍历字典的键 | `for k in MAJOR_KEYS:` | 直接遍历字典得到键（Python 3.7+ 保持插入顺序） |
| 子串判断 `in` | `if g in prompt_lower:` | 字符串包含判断 |
| `str.split()` / `endswith` | `prompt_lower.split()`、`token.endswith("bpm")` | 按空白切分；判断后缀 |
| `try / except ValueError` | `int(token[:-3])` | 捕获转换失败；`pass` 会静默吞掉错误 |
| 返回字典 | `return {"key": key, ...}` | 用字典打包多个结果 |
| f-string 嵌套引号 | `{piece['key']}` | 外层双引号、内层单引号 |
| f-string 对齐 | `{name:<20}`、`{p:>10}` | 左/右对齐并指定宽度 |
| `str.join` | `' \| '.join(piece['chords'])`（表格中竖线已转义） | 用分隔符拼接列表 |
| 元组列表解包 | `for name, p, length, v, lic in models:` | 一次取出 5 个字段 |
| `!r` 转换 | `print(f"prompt: {p!r}")` | 用 `repr` 显示，带引号 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 0.02 秒）的输出（鼓点行较长，这里截断显示前 32 个字符）：

```text
=== Step 1: prompt → symbolic music piece (toy) ===
prompt: 'upbeat pop in G major at 128 bpm'
  key: G  genre: pop  tempo: 120 bpm  bars: 8
  chords: G | D | Em | C | G | D | Em | C
  drums (kick=X snare=o): X.o.X.o.X.o.X.o.X.o.X.o.X.o.X.o.…（共 128 个字符）

prompt: 'slow lofi groove in C'
  key: C  genre: lofi  tempo: 120 bpm  bars: 8
  chords: Am | F | C | G | Am | F | C | G
  drums (kick=X snare=o): X...o...X...o.o.X...o...X...o.o.…

prompt: 'rock anthem in D at 140 bpm'
  key: D  genre: rock  tempo: 120 bpm  bars: 8
  chords: D | G | A | D | D | G | A | D
  drums (kick=X snare=o): X..oX..oX..oX..oX..oX..oX..oX..o…

prompt: 'jazz swing in A'
  key: A  genre: jazz  tempo: 120 bpm  bars: 8
  chords: Bm | E | A | F#m | Bm | E | A | F#m
  drums (kick=X snare=o): X.oox.oxX.oox.oxX.oox.oxX.oox.ox…

=== Step 2: 2026 music-gen model cheatsheet ===
  | model               | params (M) | length | vocals | license        |
  | MusicGen-large       |       3300 |   30 s | no           | MIT            |
  | Stable Audio Open    |       1200 |   47 s | no           | non-commercial |
  | ACE-Step XL (Apr 26) |       4000 | 2 min+ | yes          | Apache-2.0     |
  | YuE                  |       7000 | 2 min+ | yes          | Apache-2.0     |
  | Suno v5 (closed)     |          0 |  4 min | yes          | commercial     |
  | Udio v4 (closed)     |          0 |  4 min | yes + stems  | commercial     |

takeaways:
  - open models: MusicGen (instrumental), ACE-Step / YuE (full song)
  - commercial: Suno v5 = quality leader; Udio v4 = producer tools (stems + inpaint)
  - legal: Warner + UMG settlements (2025-2026) define safe zones
  - always tag AI-generated music with watermark + metadata disclosure
```

逐段解读：

- **pop in G**：I–V–vi–IV 在 G 大调是 G–D–Em–C，循环两遍凑满 8 小节。调识别正确，但 **tempo 是 120 而不是 128**——BPM 解析 bug。
- **lofi in C**：vi–IV–I–V 即 Am–F–C–G。没写 BPM，默认 120 是合理的。
- **rock in D**：I–IV–V–I 即 D–G–A–D，第 4、5 小节出现连续两个 D（一轮的结尾 + 下一轮的开头）。**tempo 同样应为 140**，却显示 120。
- **jazz in A**：ii–V–I–vi 即 Bm–E–A–F#m，乐理上正确。
- **速查表**：表头与数据行列宽不一致，竖线没有对齐；闭源模型的参数显示为 0。
- **takeaways**：总结了讲义的四个要点——开源器乐/整首歌、商业领导者、法律和解、水印与元数据披露。

---

## 7. 动手改一改

1. 用正则重写 BPM 解析（支持 "128 bpm"、"128bpm"、"90BPM"），重新运行，确认第 1、3 个提示词显示 128 和 140。
2. 用 `\bin\s+([a-g][#b]?)\b` 重写调性识别，用 "gentle ballad in D"、"chill lofi in A" 验证。
3. 给 `ballad` 补一个鼓点模式、给 `trap` 补一个和弦进行，让两张表的风格集合一致；再加一个检查：启动时断言两张表的键相同。
4. 真正用上 `rng`：每 4 小节随机把鼓点的最后 4 步换成一个过门（如 `"oooo"`），并用种子保证可复现。
5. 把输出写成 MIDI（可用 `mido` 等库，需自行安装）：和弦用三和弦音符、鼓点按 `bpm` 换算每步时长，在播放器里听一听。
6. 进阶：按讲义 Step 1 安装 audiocraft，用同样 4 个提示词生成 10 秒音频，用 librosa 的 beat tracking 检查实际 BPM 是否接近提示词要求。

---

## 8. 常见坑

- **静默吞异常**：`except ValueError: pass` 让 BPM 解析失败毫无痕迹；解析类代码至少要记录日志或提示用户。
- **只看首字母的子串匹配**：`" " + 字母` 会匹配任何以该字母开头的单词，示例提示词碰巧没触发，换个提示词就错。
- **查表不对齐**：两张表的风格集合不同，导致 `trap` 鼓点永远用不上、`ballad` 鼓点回落到 pop。
- **未使用的参数**：`rng` 被赋值却从未使用，读代码的人会误以为输出有随机性。
- **把 0 当未知**：速查表中闭源模型参数量为 0，应该用 `None` / `?`。
- **许可证只看一个字段**：讲义和代码都把 MusicGen 写成 MIT，但代码许可、权重许可、生成物权利可能不同，商用前要逐项核实。
