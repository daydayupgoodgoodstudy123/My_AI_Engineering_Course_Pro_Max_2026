# 代码讲解 · main.py

> **所属小节**：阶段 12 · 多模态 AI · 第 20 节 全模态模型：Qwen2.5-Omni 与 Thinker-Talker 分工 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`），不处理任何真实音频，无需 GPU、无需网络

---

## 1. 这份代码在考察什么

实时语音助手的核心指标不是准确率，而是**延迟**。这份代码完全不碰音频，只做"延迟记账"：

1. **TTFAB 计算器**（`ttfab` / `print_ttfab`）：把"用户说完 → 第一个音频样本"拆成 6 个组件，按 Thinker 规模、Talker 规模、采样率、是否带视觉估算每一项，并给出体验等级——对应学习目标 "Compute the time-to-first-audio-byte (TTFAB) budget ... component by component"。
2. **半双工轮次交接**（`simulate_turn_taking` / `demo_vad`）：用 VAD 静音阈值判断用户说完——对应讲义 "VAD and turn-taking"。
3. **双工模式与开源方案对照**：打印 half-duplex / turn-taking / full-duplex 的说明和 Mini-Omni、Moshi、Qwen2.5-Omni、Qwen3-Omni 的定位。

> 一句话：**语音产品的体验由"最慢那一段"决定，而 Thinker 的 prefill 往往就是那一段**。代码的估算模型非常粗（延迟与参数量线性成正比），VAD 演示的数字还自相矛盾——发现并修正它们，就是本节最好的练习。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `StreamConfig` | dataclass | Thinker 参数量（B）、Talker 参数量（M）、麦克风采样率、是否带视觉 | 部署配置 |
| `LatencyComponent` | dataclass | 组件名 + 毫秒数 | 延迟预算的一行 |
| `ttfab(cfg)` | 函数 | 按配置计算 6 个组件的延迟 | TTFAB 分解 |
| `print_ttfab(cfg)` | 函数 | 打印逐项与累计延迟，按总和分档评级 | 体验等级 |
| `VADEvent` | dataclass | 时间点 + 事件描述 | 轮次交接时间线 |
| `simulate_turn_taking(silence_threshold_ms)` | 函数 | 返回写死的 6 个事件 | 半双工 VAD |
| `demo_vad` / `duplex_modes` | 函数 | 打印时间线 / 三种模式说明 | 双工模式 |
| `main` | 函数 | 跑 4 种配置 + VAD + 双工说明 + 开源方案表 | — |

数据流：`main` 构造 4 个 `StreamConfig` → 逐个 `print_ttfab`（内部调用 `ttfab`）→ `demo_vad`（`simulate_turn_taking`）→ `duplex_modes` → 打印 OPEN STREAMING DESIGNS。

---

## 3. 逐段精讲

### 3.1 两个 dataclass：配置与延迟项

```python
@dataclass
class StreamConfig:
    thinker_b: int
    talker_m: int
    mic_sr: int = 16000
    include_vision: bool = False


@dataclass
class LatencyComponent:
    name: str
    ms: float
```

- `StreamConfig` 的单位很重要：`thinker_b` 以**十亿（B）**为单位，`talker_m` 以**百万（M）**为单位。`StreamConfig(thinker_b=7, talker_m=300)` 就是 7B Thinker + 300M Talker。
- 有默认值的字段（`mic_sr`、`include_vision`）必须写在无默认值字段之后，这是 dataclass 的规则。
- `LatencyComponent` 让 `ttfab` 返回"带名字的数字列表"，打印时既能显示名称又能累加。

### 3.2 `ttfab`：六个组件的估算模型

```python
def ttfab(cfg: StreamConfig) -> list[LatencyComponent]:
    components = []
    mic_ms = 40 + (cfg.mic_sr // 8000) * 5
    components.append(LatencyComponent("mic -> speech tokens", mic_ms))

    prefill = 100 * (cfg.thinker_b / 7.0)
    if cfg.include_vision:
        prefill += 80
    components.append(LatencyComponent("Thinker prefill (prompt + history)", prefill))

    first_text = 40 * (cfg.thinker_b / 7.0)
    components.append(LatencyComponent("Thinker first text token", first_text))

    talker_first = max(15, 20 * (cfg.talker_m / 300.0))
    components.append(LatencyComponent("Talker first speech tokens", talker_first))

    rvq_decode = 30
    components.append(LatencyComponent("residual-VQ decode (8 layers parallel)", rvq_decode))

    wave_decode = 70
    components.append(LatencyComponent("waveform decoder (SNAC-class)", wave_decode))
    return components
```

逐项对照讲义 "Production latency budget"：

| 组件 | 代码公式 | 7B/300M/16 kHz 取值 | 讲义区间 |
|------|---------|-------------------|---------|
| mic → 语音 token | `40 + (sr // 8000) × 5` | 50 | 40–80 |
| Thinker prefill | `100 × B/7`，带视觉 +80 | 100（视觉 180） | 7B 时 100–200 |
| 首个文本 token | `40 × B/7` | 40 | 40 |
| Talker 首批语音 token | `max(15, 20 × M/300)` | 20 | 20（处理）+ 40（提交） |
| RVQ 解码 | 常数 30 | 30 | 30 |
| 波形解码 | 常数 70 | 70 | 50–80 |

- 采样率项：`16000 // 8000 = 2` → 50 ms；48 kHz → 70 ms。整除让 44.1 kHz 也算成 5 × 5 + 40 = 65 ms。
- Talker 项有 15 ms 下限，所以 200M Talker 也是 15 ms（而不是 13.3）。
- ⚠️ **线性缩放过于粗糙**：prefill 和首 token 都与 `thinker_b` 成正比，72B 时分别是 1,109 ms 和 411 ms，总 TTFAB 1,690 ms，比讲义"70B 为 600–900 ms"高近一倍。现实中 70B 必然多卡张量并行（单卡放不下 140 GB 的 FP16 权重），延迟会被卡数摊薄；prefill 受算力限制，首 token 受显存带宽限制，两者的缩放规律也不同（测验 Q9 给出了 roofline 式估算）。
- ⚠️ **少了一项**：讲义的 "First speech tokens commit: 40ms" 在代码里没有对应，这使代码的 7B 结果（305–310 ms）低于讲义下限 320 ms。
- ⚠️ **没算 VAD 静音**：TTFAB 按定义从"用户说完"算起，VAD 至少要等一个静音阈值（~200 ms）才能确认用户说完，这段时间不在 `ttfab()` 里。
- "8 layers parallel"：假设 8 层残差码本可以并行解码，所以 RVQ 只花 30 ms；若逐层串行，耗时和所需 token 速率都会成倍增加（见测验 Q11）。

### 3.3 `print_ttfab`：累计与评级

```python
    total = 0.0
    for c in ttfab(cfg):
        total += c.ms
        print(f"  {c.name:<40}  +{c.ms:>5.0f} ms  ({total:>6.0f})")
    print(f"  TTFAB = {total:.0f} ms", end=" ")
    if total < 250:
        print("  -> GPT-4o class")
    elif total < 400:
        print("  -> conversational")
    elif total < 700:
        print("  -> noticeable but usable")
    else:
        print("  -> sluggish, user drift")
    return total
```

- 每行同时打印"本项 +x ms"和"累计 (y)"，这是做延迟预算时最直观的格式——一眼能看出哪一项把总数推过了门槛。
- `print(..., end=" ")` 不换行，让评级接在同一行后面。
- 分档阈值：<250 "GPT-4o 级"，<400 "对话感"，<700 "可感知但可用"，其余"迟钝"。注意讲义正文说 "< 500ms — below that, the user stops noticing the lag"，与代码 400 ms 的分档不完全一致，都是经验值。
- `return total` 让调用方可以拿到总延迟（`main` 中没有使用）。

### 3.4 VAD 轮次交接：写死的时间线

```python
def simulate_turn_taking(silence_threshold_ms: int = 200) -> list[VADEvent]:
    events = []
    events.append(VADEvent(0, "user starts speaking"))
    events.append(VADEvent(450, "user audio tokens streaming"))
    events.append(VADEvent(3800, "user stops speaking"))
    events.append(VADEvent(3800 + silence_threshold_ms, "VAD triggers end-of-turn"))
    events.append(VADEvent(3800 + silence_threshold_ms + 200, "Thinker begins prefill"))
    events.append(VADEvent(3800 + silence_threshold_ms + 400, "Talker first audio out"))
    return events
```

- 半双工的逻辑：用户停止说话后，VAD 要连续检测到 `silence_threshold_ms` 的静音才判定"轮到模型"。阈值越短越灵敏，但越容易在用户思考停顿时抢话。
- ⚠️ **数字自相矛盾**：用户 3,800 ms 说完，模型 4,400 ms 出声，间隔 **600 ms**；但 `demo_vad` 最后打印 "net response lag after user stops: ~400ms"，漏掉了 200 ms 的 VAD 等待。
- ⚠️ 时间线与 `ttfab()` 完全脱节：VAD 触发后又空等 200 ms 才 prefill，从开始 prefill 到出声只给了 200 ms，而上面算出的 TTFAB 是 305–390 ms。
- 修正方法：让时间线从 `ttfab(cfg)` 的分项累加得到（测验 Q10，7B/200M 实测间隔 505 ms）。这个结果说明 VAD 阈值本身就占了"对话感"预算的近一半。

### 3.5 双工模式与开源方案表

```python
    modes = [
        ("half-duplex",  "user speaks, model listens; swap; clear turns"),
        ("turn-taking",  "VAD silence detects end-of-turn (200-400ms)"),
        ("full-duplex",  "both can speak; requires training + backchannel data"),
    ]
```

- 讲义学习目标说有三种模式（half-duplex、turn-taking、full-duplex），正文只展开了两种；从内容看 turn-taking 是实现 half-duplex 的机制（靠 VAD 判定轮次），并不是独立于 half-duplex 的第三种模式。
- 开源方案表把 Qwen3-Omni 标为 "(11/25)"，与讲义一致；但讲义参考文献中 Qwen3-Omni 的 arXiv 编号是 2509.17765，即 2025 年 9 月，发布时间应以论文为准。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只做延迟记账，不处理音频 | 聚焦"预算思维"，零依赖 | 无法验证任何数字；生产中要在每个环节打时间戳实测 P50/P95 |
| prefill / 首 token 与参数量线性成正比 | 一行公式 | 72B 得到 1,690 ms，远超讲义 600–900 ms；应按"算力 / 带宽 / 卡数"建模 |
| Talker 延迟设 15 ms 下限 | 小模型也有固定开销 | 说明 Talker 不是瓶颈，缩小它几乎不省时间 |
| RVQ、波形解码取常数 | 与模型规模无关 | 实际取决于解码器结构和音频块长度 |
| 少算"语音 token 提交"一项 | 合并进 Talker 项 | 7B 结果比讲义下限还低 10–15 ms |
| TTFAB 不含 VAD 静音 | 只算模型侧 | 用户感知延迟被低估约 200 ms |
| VAD 时间线写死 | 演示事件顺序 | 与 `ttfab` 脱节、打印的 lag 错误；应由配置推导 |
| 体验分档 250/400/700 | 给出直观评级 | 经验阈值，与讲义"<500 ms"表述不完全一致 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 带默认值字段 | `mic_sr: int = 16000`、`include_vision: bool = False` | 有默认值的字段必须排在无默认值字段之后 |
| 关键字参数构造 | `StreamConfig(thinker_b=7, talker_m=200, include_vision=False)` | 按名字传参，可读性好、顺序无关 |
| 类型注解 | `def ttfab(cfg: StreamConfig) -> list[LatencyComponent]:` | 参数是配置对象，返回延迟项列表 |
| 整除与真除 | `cfg.mic_sr // 8000`；`cfg.thinker_b / 7.0` | `//` 向下取整得整数；`/` 得浮点数 |
| `max` 设下限 | `max(15, 20 * (cfg.talker_m / 300.0))` | 结果至少为 15 |
| 累加器模式 | `total = 0.0; for c in ...: total += c.ms` | 边遍历边累计 |
| f-string 格式 | `{c.name:<40}`、`{c.ms:>5.0f}`、`{total:>6.0f}` | 左对齐 40 宽；右对齐 5 宽 0 位小数；右对齐 6 宽 |
| `print(..., end=" ")` | `print(f"  TTFAB = {total:.0f} ms", end=" ")` | 以空格结尾而非换行，下一次 print 接在同一行 |
| `if / elif / else` 链 | 体验分档 | 按顺序匹配第一个成立的条件 |
| 元组列表 + 解包 | `for mode, note in modes:` | 两列数据一起遍历 |
| 对象属性访问 | `e.time_ms`、`e.kind`、`c.name` | dataclass 字段即属性 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，瞬间完成）：

```text
CONFIG: Thinker=7B  Talker=200M  mic=16000Hz  vision=False
  mic -> speech tokens                      +   50 ms  (    50)
  Thinker prefill (prompt + history)        +  100 ms  (   150)
  Thinker first text token                  +   40 ms  (   190)
  Talker first speech tokens                +   15 ms  (   205)
  residual-VQ decode (8 layers parallel)    +   30 ms  (   235)
  waveform decoder (SNAC-class)             +   70 ms  (   305)
  TTFAB = 305 ms   -> conversational

CONFIG: Thinker=7B  Talker=300M  mic=16000Hz  vision=True
  ...（prefill 180，Talker 20）
  TTFAB = 390 ms   -> conversational

CONFIG: Thinker=72B  Talker=300M  mic=16000Hz  vision=True
  Thinker prefill (prompt + history)        + 1109 ms  (  1159)
  Thinker first text token                  +  411 ms  (  1570)
  TTFAB = 1690 ms   -> sluggish, user drift

CONFIG: Thinker=70B  Talker=1000M  mic=16000Hz  vision=True
  Thinker prefill (prompt + history)        + 1080 ms  (  1130)
  Thinker first text token                  +  400 ms  (  1530)
  Talker first speech tokens                +   67 ms  (  1597)
  TTFAB = 1697 ms   -> sluggish, user drift

HALF-DUPLEX TURN-TAKING (VAD silence 200ms)
  t=  3800 ms  user stops speaking
  t=  4000 ms  VAD triggers end-of-turn
  t=  4200 ms  Thinker begins prefill
  t=  4400 ms  Talker first audio out
  net response lag after user stops: ~400ms
```

逐项解读：

- **7B 两种配置**：305 ms 和 390 ms，都落在"conversational"档。视觉输入带来的 +80 ms prefill 是两者差距的主要来源（另有 Talker 15 → 20 ms）。
- **72B vs 70B + 1B Talker**：两者总延迟几乎相同（1,690 vs 1,697 ms）——Thinker 小了 2B 省下约 40 ms，Talker 大了 700M 多花约 47 ms。更重要的是：**在 Thinker 主导的延迟里，Talker 的规模几乎无关紧要**，这与讲义"Talker 做大只会更慢、不会更好"的观点一致。
- **72B 的 1,690 ms** 比讲义 70B 的 600–900 ms 高很多，是线性缩放模型的产物（见 3.2）。
- **VAD 时间线**：从 3,800 到 4,400 是 600 ms，打印的 "~400ms" 是错的。若把 VAD 的 200 ms 加到 7B/200M 的 305 ms 上，用户感知延迟约 505 ms，已经越过讲义 500 ms 的对话感门槛。

---

## 7. 动手改一改

1. **补齐分项**：在 `ttfab` 中加入讲义的 "First speech tokens commit: 40ms" 和一项 `vad_silence_ms`（新增到 `StreamConfig`，默认 200），重新运行，看 7B 配置还能否保持在 400 ms 以内。
2. **修 VAD 演示**：把 `simulate_turn_taking` 改成接收 `StreamConfig`，由 `ttfab` 的分项累加出各事件时间，并正确计算"用户说完到第一声"（参考测验 Q10，7B/200M 为 505 ms）。
3. **更真实的规模模型**：给 `StreamConfig` 增加 `n_gpus`、`prompt_tokens`，用"prefill ≈ 2 × 参数 × token / (卡数 × FLOPS × 利用率)"、"首 token ≈ 参数 × 2 字节 / (卡数 × 带宽)"重写两项，比较 70B 在 1 卡（仅理论）和 4 卡时的结果。
4. **讲义练习 1**：为"目标 300 ms、7B + 300M"写一个求解器，枚举 Thinker 规模、波形解码器延迟（50–80）、是否带视觉，输出所有满足 TTFAB ≤ 300 ms 的组合。
5. **讲义练习 5**：写 `talker_rtf(talker_tok_per_s, base_hz=50, n_codebooks=1)`，计算实时率，分别在 1 层与 8 层串行码本下判断 30/80/200 tok/s 的 Talker 能否跟上。
6. **进阶**：用 `asyncio` 写一个三段流水线模拟（Thinker 每 40 ms 产出一个文本 token → Talker 每个文本 token 产出若干语音 token → 解码器按块输出音频），记录首个音频块时间和整句完成时间，体会"流式"与"等整句生成完再合成"的差别。

---

## 8. 常见坑

- **把 TTFT 当 TTFAB**：首个文本 token 出来不等于用户听到声音，后面还有 Talker、RVQ、波形解码和播放缓冲。
- **忘记 VAD 等待**：固定静音阈值直接加在每一轮的延迟上；它往往比 Talker、RVQ 加起来还大。
- **用平均值做预算**：真实系统要看 P95/P99，偶发的长 prefill（长对话历史）会让体验骤降。
- **以为 Talker 越大越好**：Talker 必须跟上 ≥ 50 tok/s 的语音速率，做大只会更慢（skill 文件明确否决 70B Talker）。
- **使用非流式语音解码器**：必须等整句语音 token 才能解码，TTFAB 会直接爆炸。
- **以为全双工换个 VAD 就行**：全双工需要模型学会边听边说，必须有专门的双声道训练数据。
- **线性外推大模型延迟**：大模型几乎总是多卡部署，延迟取决于卡数、带宽和算力利用率，而不是参数量的简单倍数。
