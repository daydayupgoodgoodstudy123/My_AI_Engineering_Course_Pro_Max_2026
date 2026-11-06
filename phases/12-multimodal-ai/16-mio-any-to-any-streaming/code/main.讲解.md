# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 16 节 MIO 与任意模态互转的 Streaming Multimodal Models ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）

---

## 1. 这份代码在考察什么

MIO 的工程难点不在某个算法，而在"把四种模态塞进一个模型"带来的**记账问题**。这份 160 行的脚本把其中三本账算给你看：

1. **词表账**：文本、图像、语音、音乐各占一段不重叠的 ID 区间，再加上分隔标签，总词表多大——对应讲义 "Four tokenizers for four modalities" 与练习 3。
2. **路由账**：每种输入该交给哪个 tokenizer——对应讲义的 tokenizer 栈。
3. **延迟账**：从用户说完到第一段音频播出（TTFAB）要经过哪些环节、各花多少毫秒——对应讲义 "Streaming decode" 与 "Latency budget"。

最后还用文字演示了 chain-of-visual-thought 的四个步骤。

> 一句话：**any-to-any 模型的设计约束，大部分可以用"ID 区间"和"毫秒预算"两张表说清**。同时要注意：代码的词表比讲义多了一个说不通的槽位，延迟模型对 prompt 长度的依赖方向也反了。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `VocabSlot` | `@dataclass` + `@property end` | 一个词表区间：名字、起点、大小，`end` 为半开区间终点 | 共享词表的 ID 区间 |
| `build_vocab` | 函数 | 按计划表依次分配 11 个区间，游标累加 | 不重叠的 ID 分配 |
| `print_vocab` | 函数 | 打印区间表与总大小 | 词表大小 |
| `route_inputs` | 函数 | 按 `kind` 给每个输入标注 tokenizer 路径 | 四个 tokenizer |
| `LatencyTrace` | `@dataclass` | 一个延迟环节：标签 + 毫秒 | 延迟预算条目 |
| `streaming_decode_latency` | 函数 | 生成 5 个环节的延迟列表 | TTFAB 组成 |
| `print_trace` | 函数 | 累加打印，并按 500/800 ms 阈值给出结论 | 对话感判定 |
| `demo_chain_of_visual_thought` | 函数 | 打印 4 步视觉思维链 | chain-of-visual-thought |
| `main` | 函数 | 依次执行以上各部分 | — |

数据流：`build_vocab()` → `print_vocab()`；`inputs` 列表 → `route_inputs()` → 打印；`streaming_decode_latency(2.0, 8)` → `print_trace()`；`demo_chain_of_visual_thought()`。四块彼此独立，没有共享状态，也没有任何随机性。

---

## 3. 逐段精讲

### 3.1 `VocabSlot`：用半开区间描述一段 ID

```python
@dataclass
class VocabSlot:
    name: str
    start: int
    size: int

    @property
    def end(self) -> int:
        return self.start + self.size
```

- `end` 是 `@property`：像字段一样访问（`s.end`），但每次都由 `start + size` 现算，不会和另外两个字段不一致。
- 区间是**半开**的 `[start, end)`：文本 `[0, 32000)` 就是讲义写的 `0..31999`。这和 Python 的 `range`、切片约定一致，相邻区间可以无缝拼接（上一个的 `end` 就是下一个的 `start`）。

### 3.2 `build_vocab`：游标式分配

```python
    plan = [
        ("text BPE",      32000),
        ("image SEED",     4096),
        ("speech L0",      4096),
        ("speech L1..L7", 4096),
        ("music",          8192),
        ("<image>",           1),
        ("</image>",          1),
        ("<speech>",          1),
        ("</speech>",         1),
        ("<music>",           1),
        ("</music>",          1),
    ]
    for name, size in plan:
        slots.append(VocabSlot(name=name, start=cursor, size=size))
        cursor += size
```

- **游标分配**：每个区间从当前 `cursor` 开始，分配完把游标后移 `size`。只要计划表里的大小都正确，就**保证不重叠、不留空隙**——这是讲义"disjoint ID ranges"的最简实现。
- 共享词表的意义：同一个整数只代表一种东西；输入 embedding 和输出投影覆盖整个词表，模型在 `<speech>` 之后输出的 token 自然落在语音区间。
- ⚠️ **与讲义不一致**：讲义布局合计约 48K（`32000 + 4096 + 4096 + 8192 + 7 个分隔符 = 48,391`），代码多了一个 `speech L1..L7`（4,096），合计 52,486，且分隔符只有 6 个。
- ⚠️ **这个槽位说不通**：讲义说残差层 L1..L7 由主干之外的"parallel-decoded residual quantizer"预测——那它们根本不需要进主干词表；如果真要让主干输出 7 层残差码，每层都有自己的码本，需要 `7 × K` 个 ID，一个 4,096 的共享槽位会把"第 2 层的码 5"和"第 6 层的码 5"混成同一个 ID。
- ⚠️ 音乐同理：讲义说音乐是 4–8 层码本的残差 VQ，这里只给了一段 8,192 的区间，相当于只放了一层（或者假设残差层也由外部解码器负责）。
- **练习 3 的答案**可以直接从这里算：讲义口径 48,394 × 4,096 ≈ 198M 参数（输入 embedding），输出层不共享再翻倍 ≈ 396M；按代码的 52,486 则约 215M。

### 3.3 `print_vocab`：对齐打印

```python
    print(f"  {'slot':<18}{'start':>8}{'end':>8}{'size':>8}")
    for s in slots:
        print(f"  {s.name:<18}{s.start:>8}{s.end:>8}{s.size:>8}")
    total = slots[-1].end
```

- `slots[-1].end` 就是总词表大小——因为区间连续无空隙，最后一个区间的终点等于总数。
- 名字左对齐 18 列、数字右对齐 8 列，是表格打印的常用写法。

### 3.4 `route_inputs`：四个 tokenizer 的分派

```python
    for inp in inputs:
        kind = inp["kind"]
        if kind == "text":
            path = "BPE"
        elif kind == "image":
            path = "SEED-Tokenizer"
        elif kind in ("speech", "voice"):
            path = "SpeechTokenizer residual-VQ"
        elif kind == "music":
            path = "Encodec"
        else:
            path = "UNKNOWN"
        routed.append({**inp, "path": path})
```

- 对应讲义的 tokenizer 栈：BPE、SEED-Tokenizer、SpeechTokenizer 残差 VQ、Encodec。`voice` 作为 `speech` 的别名。
- `{**inp, "path": path}`：字典解包，复制原字典并添加/覆盖 `path` 键，不修改调用方传入的字典。
- ⚠️ 大小写敏感：`"Speech"` 会落到 `UNKNOWN`；`"video"` 也没有分支。实测两者都返回 `UNKNOWN`。
- ⚠️ 未知模态**静默**返回字符串而不是报错，错误会被推迟到下游才暴露。更好的写法是"字典查表 + `raise ValueError`"（测验 Q12）。

### 3.5 `streaming_decode_latency`：TTFAB 的五项

```python
def streaming_decode_latency(prompt_audio_seconds=2.0, model_size_b=8):
    trace = []
    trace.append(LatencyTrace("mic audio -> speech tokens", prompt_audio_seconds * 20))
    trace.append(LatencyTrace("prefill prompt tokens", 80 * (model_size_b / 8.0)))
    trace.append(LatencyTrace("first output token", 40 * (model_size_b / 8.0)))
    trace.append(LatencyTrace("residual-VQ layers 1..7", 30))
    trace.append(LatencyTrace("speech decoder (Encodec-like)", 80))
    return trace
```

五项与讲义 "Latency budget" 一一对应：

| 环节 | 代码 | 讲义 |
|------|------|------|
| 麦克风 → 音频 token | `秒数 × 20`（2 s → 40 ms） | 约 50 ms |
| prefill | `80 × size/8`（8B → 80 ms） | 约 100 ms（8B） |
| 首个输出 token | `40 × size/8`（8B → 40 ms） | 约 50 ms |
| 残差 VQ 层 1..7 | 30 ms | 与语音解码器合计约 100–150 ms |
| 语音解码器 | 80 ms | （同上） |
| **合计** | **270 ms** | **约 300 ms 起** |

- prefill 与首 token 按 `model_size_b / 8.0` 线性缩放：模型越大越慢，这个方向是对的（实测 70B 时合计 1,200 ms，1B 时 165 ms）。
- 残差层是固定 30 ms，体现的是"并行解码"——若 7 层由主干串行生成，按首 token 的 40 ms 计要 280 ms（讲义练习 2）。
- ⚠️ **依赖方向反了**：
  - "mic → tokens" 随**整段**语音时长增长（30 秒语音 → 600 ms），但流式系统在用户说话期间就持续编码，停下后只剩最后一个 chunk，应是常数；
  - "prefill" 与 prompt 长度**无关**，但一次性 prefill 的耗时应与 prompt token 数（含历史）成正比，流式增量 prefill 则只剩尾部少量 token。
- ⚠️ 各项数字都比讲义小，合计 270 ms 已低于讲义说的 "~300ms minimum"。

### 3.6 `print_trace`：累加与阈值判定

```python
    total = 0.0
    for t in trace:
        total += t.ms
        print(f"  {t.label:<38}  +{t.ms:>5.0f} ms   (cumul {total:>6.0f})")
    ...
    if total < 500:
        print(f"  -> conversational feel (GPT-4o-class)")
    elif total < 800:
        print(f"  -> acceptable (first-gen open any-to-any)")
    else:
        print(f"  -> sluggish, consider smaller model or parallel decode")
```

- 边打印边累加，`cumul` 列显示截至每一步的累计延迟，一眼看出哪一项"吃掉"最多时间。
- 500 ms 阈值对应讲义的对话感标准。
- ⚠️ 结论措辞有问题：讲义说 MIO/AnyGPT 实测在 400–600 ms，outputs 技能文件把"声称 MIO 的 TTFAB 与 GPT-4o 相当"列为硬性拒绝项；而代码用一组偏乐观的估计算出 270 ms 就打出 "GPT-4o-class"。玩具估算不应给出这种对真实系统的评价。
- 后三个 `print(f"...")` 里没有任何占位符，`f` 前缀是多余的（无害，但 lint 工具会提示）。

### 3.7 `demo_chain_of_visual_thought`

```python
    steps = [
        "user text -> vision tokens",
        "model sketches intermediate image <image> ... </image>",
        "model emits text analysis of sketch",
        "model concludes with yes/no + justification",
    ]
    for i, s in enumerate(steps, 1):
        print(f"    step {i}: {s}")
```

- 对应讲义的三步（先画草图、再分析、再作答），代码把"输入编码"单列为第 1 步。
- `enumerate(steps, 1)`：从 1 开始编号。
- 第 1 步写作 "user text -> vision tokens" 略不准确：问题里的照片应经图像 tokenizer 变成 vision token，文本走 BPE。
- 结尾一句 "wins on spatial-reasoning benchmarks; hurts latency" 点出了它的取舍：在语音对话这种延迟敏感场景里，多生成一张图（上千 token）可能直接把 TTFAB 推过 500 ms。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 游标式分配 ID 区间 | 自动保证不重叠、连续 | 需要额外校验计划表本身合理（如残差层是否该进词表）；生产中还要预留扩展区与特殊 token |
| 半开区间 `[start, end)` | 与 Python 习惯一致，拼接无缝 | 与讲义闭区间写法差 1，读表时要注意 |
| 单独的 `speech L1..L7` 槽 | 想表达"残差层也有 ID" | 与"残差层由外部并行解码"矛盾；若要进词表需 7 × K 个 ID |
| if/elif 路由 + `UNKNOWN` | 直观 | 大小写敏感、静默失败；应字典查表 + 报错 |
| 线性延迟模型 | 一眼看出各项量级 | 对 prompt 长度的依赖方向错误；真实预算应来自 profile |
| 500/800 ms 阈值 + 结论文案 | 把数字翻译成产品判断 | 用乐观估计得出"GPT-4o-class"会误导 |
| 无随机、纯打印 | 输出完全可复现 | 不涉及任何真实 tokenizer 或模型 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| `@dataclass` | `class VocabSlot: name: str; start: int; size: int` | 自动生成构造函数 |
| `@property` | `def end(self) -> int: return self.start + self.size` | 只读的"计算属性"，用 `s.end` 访问，不加括号 |
| 元组列表 + 解包循环 | `for name, size in plan:` | 每个元组拆成两个变量 |
| 关键字参数构造 | `VocabSlot(name=name, start=cursor, size=size)` | 清晰表明每个值的含义 |
| 负索引 | `slots[-1].end` | 取最后一个元素 |
| f-string 中嵌入字面量 | `f"{'slot':<18}"`、`f"{'(vocab size)':>16}"` | 表头也用同样的宽度格式 |
| f-string 格式符 | `{t.ms:>5.0f}`、`{total:>6.0f}`、`{total:.0f}` | 右对齐宽度 + 0 位小数 |
| 无占位符的 f-string | `print(f"  -> conversational feel ...")` | 合法但多余，普通字符串即可 |
| `in` 判断元组 | `kind in ("speech", "voice")` | 多个别名一起判断 |
| 字典解包合并 | `{**inp, "path": path}` | 复制字典并新增键，不修改原字典 |
| 字典取值 | `inp["kind"]`、`r['payload']` | 键不存在会抛 `KeyError` |
| 默认参数 | `def streaming_decode_latency(prompt_audio_seconds: float = 2.0, model_size_b: int = 8)` | 调用时可省略或用关键字覆盖 |
| `/` 真除法 | `model_size_b / 8.0` | 结果为浮点数 |
| `enumerate(..., 1)` | `for i, s in enumerate(steps, 1)` | 指定起始编号 |
| `if / elif / else` 链 | `print_trace` 的阈值判断 | 第一个为真的分支执行 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，瞬间完成，输出完全确定）：

```text
SHARED VOCABULARY LAYOUT
  slot                 start     end    size
  text BPE                 0   32000   32000
  image SEED           32000   36096    4096
  speech L0            36096   40192    4096
  speech L1..L7        40192   44288    4096     ← 讲义没有这一段
  music                44288   52480    8192     ← 讲义中音乐从 40192 开始
  <image>              52480   52481       1
  </image>             52481   52482       1
  <speech>             52482   52483       1
  </speech>            52483   52484       1
  <music>              52484   52485       1
  </music>             52485   52486       1
  TOTAL                52486    (vocab size)    ← 讲义约 48K

ROUTER: four inputs -> four tokenizers
  text      'Hello'  -> BPE
  image     'cat.png'  -> SEED-Tokenizer
  voice     'user.wav'  -> SpeechTokenizer residual-VQ   ← voice 是 speech 的别名
  music     'loop.mp3'  -> Encodec

STREAMING DECODE LATENCY (time-to-first-audio-byte)
  mic audio -> speech tokens              +   40 ms   (cumul     40)   ← 2 s × 20
  prefill prompt tokens                   +   80 ms   (cumul    120)
  first output token                      +   40 ms   (cumul    160)
  residual-VQ layers 1..7                 +   30 ms   (cumul    190)   ← 并行解码
  speech decoder (Encodec-like)           +   80 ms   (cumul    270)
  total TTFAB: 270 ms
  -> conversational feel (GPT-4o-class)     ← 与讲义"MIO 400–600 ms"矛盾
```

逐项解读：

- **词表**：区间首尾相接、无重叠，验证了游标分配的正确性；但总量比讲义多 4,095（多一个 4,096 槽、少一个分隔符）。
- **路由**：四种输入各得其所；这组 demo 输入都是小写且在白名单内，所以没有暴露 `UNKNOWN` 问题。
- **延迟**：prefill 是单项最大（80 ms），残差层并行后只占 30 ms。总计 270 ms 低于讲义给出的约 300 ms 最低值。改变参数实测：说 10 秒 → 430 ms；说 30 秒 → 830 ms（主要是 mic 项 600 ms，这在流式系统中是不合理的）；模型 70B → 1,200 ms。
- **思维链**：四步文字说明，无计算。

---

## 7. 动手改一改

1. **（练习 3）对齐讲义词表**：删掉 `speech L1..L7`，补一个分隔符（凑满讲义的 7 个），确认总数为 48,391；再写一个 `embedding_params(V, d=4096, tied=True)` 计算参数量。
2. **把残差层放进词表的正确做法**：改为 7 个独立区间（每层 1,024 或 4,096），观察词表膨胀到多少；思考为什么讲义选择让外部并行解码器负责残差层。
3. **修正延迟模型**：增加 `chunk_ms` 与 `streaming_prefill` 参数，让 mic 项为常数、prefill 在非流式时与 prompt token 数成正比（参考测验 Q10），再分别比较说 2 秒和 30 秒时的 TTFAB。
4. **（练习 2）串行 vs 并行残差**：增加 `parallel_residual: bool` 参数，串行时残差项为 `7 × first_token_ms`，打印两种设置下的 TTFAB 并判断是否越过 500 ms。
5. **（练习 1）预算表**：把讲义 "Latency budget" 的数字（50/100/50/100–150）做成一组参数，输出最小与最大两种 TTFAB，并把结论文案改成"与 GPT-4o（约 250 ms）、Moshi（160 ms）相比差多少"。
6. **健壮路由**：改成字典查表 + `strip().lower()` + 未知模态报错，并新增 `video` 路由（抽帧走图像 tokenizer 或 3D tokenizer，需要新增 `<video>`/`</video>` 区间）。

---

## 8. 常见坑

- **词表区间重叠或留空**：要么同一 ID 代表两种东西，要么浪费 embedding 行；用游标分配并断言 `slots[i].end == slots[i+1].start`。
- **把多层码本塞进一个共享区间**：不同层同一下标会被合并，信息丢失。
- **半开/闭区间混用**：`end = start + size` 是开区间终点，与讲义 `0..31999` 写法差 1。
- **流式系统里让编码延迟随整段语音增长**：用户说话期间就应持续编码与 prefill，停顿后只处理尾部。
- **忽略 VAD 等待与网络往返**：真实 TTFAB 还包括"判断用户说完"的时间。
- **用乐观估算宣称"GPT-4o 级"**：技能文件明确拒绝这种说法，延迟结论要基于实测。
- **路由大小写敏感、静默失败**：`"Speech"` 变成 `UNKNOWN` 不会报错，问题会在下游才暴露。
- **为所有问题启用视觉思维链**：对简单问答和实时语音只会增加延迟。
