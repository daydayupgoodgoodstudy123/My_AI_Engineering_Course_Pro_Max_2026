# 参考答案讲解：TurnKit（06/14）

计时结束后再看。参考实现在同目录的 `turnkit/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修能量门

**现象**：解锁后的第一个错误是 `dbfs` 里的 `ValueError: math domain error`，而 `dbfs` 本身没有 bug。

**顺着往上找**：传给 `math.log10` 的是 -0.05。这个“电平”来自 `rms`：`[0.3, -0.4]` 交替的帧，样本的均值是 -0.05，均方根才是 0.3536（-9.03 dBFS）。`rms` 写成了普通均值，正负样本互相抵消，结果可以是负数。`dbfs` 只把 0.0 当作数字静音特殊处理，这对真正的 RMS 是对的。把 `dbfs` 改成 `max(level, 1e-10)` 或 `abs(level)` 能让报错消失，可电平还是错的，同一条断言会接着挂。这一关想练的是：报错的位置往往不是出 bug 的位置。

**依次修四处**：

1. `rms` 改成先平方、再求均值、再开方。
2. `energy_gate` 为了省掉开方，算的是均方，也就是功率；阈值换算成的却是幅度 `10 ** (dB / 20)`。功率要和 `limit * limit`（等于 `10 ** (dB / 10)`）比，或者开方后再和 `limit` 比。原来的写法让门限实际变成了 -20 dBFS，-30 和 -38 dBFS 的帧都被当成静音。
3. hangover 的帧数是 `hangover_ms // frame_ms`。原来除的是 `frame_len`（采样点数），8 kHz 和 16 kHz 下都得 0，hangover 等于没有。
4. `apply_hangover` 只记住最近一个响帧的下标，一遍扫完。原来每一帧都从头找一遍最近的响帧，是 O(n²)：测试里的 16,000 帧（20 ms 一帧，约 5 分钟）是 20 秒说话加一长段静音，要 1.3 秒左右，改完约 0.4 毫秒。从当前帧往回找、碰到响帧就停也不够：在说话的地方很快，可静音里的每一帧都要一路往回走到那段话，还是 O(n²)，要 1.1 秒左右。

**护栏**：改成 O(n) 时，最常见的两种写法都会在边上出错：

- 记“距上一个响帧多少帧”的计数器从 0 开始，开头的静音会被当成上一个响帧的 hangover，前几帧变成语音。参考实现用 `last = None` 表示“还没有响帧”。
- 用 `any(loud[i - frames : i + 1])` 取窗口，开头几帧的起点是负数，Python 把它当成从末尾数，切片变成空的，第一帧明明是响帧也会被判成静音。

## Part 2 语音段表

参考实现用两张表：`recordings` 记每个 recording 的采样率，`segments` 记 `(recording, start_sample, end_sample)`。边界存 INTEGER。SQLite 的整数是 64 位，48 kHz 下 13 小时的偏移超过 2³¹，也照样存准。

`add` 的步骤：

1. 在 Python 里校验：`0 <= start < end`，采样率和这个 recording 已有的一致，否则报 `ValueError`。
2. 查出同一个 recording 里 `start_sample <= end AND end_sample >= start` 的行。等号让首尾相接的段也算在内，这正是左闭右开区间的“相接”。
3. 和查到的行取并集，删掉旧行，插入合并后的一行。整个过程放在一个 `with self._db:` 事务里，结束时自动 commit。
4. 表里已有的段互不重叠、互不相接，所以一次查询就能找全所有要合并的段，包括新段同时接上两边的情况。

容易漏的几点：

- **精度**：按毫秒存，16 kHz 下 16001 变成 1000 ms，读回来是 16000；按 REAL 秒存、读回时用 `int()` 截断，1001 这类值会少一个采样点。采样点是这个领域的原始单位，秒和毫秒只用来显示。
- **区间端点**：相接要合并，空一个采样点就不合并。按闭区间想，两种情况会弄反。
- **包含**：新段整个落在已有段里面也是重叠，上面的条件能查到它，返回的是包住它的那段。只查“已有段的端点是否落在新区间里”会漏掉，表里就会出现两行互相重叠的段。
- **按 recording**：查询要带上 `recording = ?`。漏了它，重开后加的 room-2 [0, late) 会把 call-7 的段全并走。
- **重开**：建表要写 `IF NOT EXISTS`；没有 commit 的话，关闭后数据就没了。
- **顺序**：`segments()` 按 `start_sample` 排序。按 rowid 排是插入顺序，测试最后插入的那段在时间上最早。

## Part 3 轮次检测

参考实现的状态只有几项：是否在说话、当前这段连续语音（idle 时）或连续静音（speaking 时）有多少个采样点和它从哪里开始、已经处理到的位置，以及 pre-roll 不能越过的下限（上一轮的结尾）。

```python
if not self.speaking:
    if not is_speech:
        self.run = 0                      # 语音必须连续：课里的代码漏了这一行
        return None
    ...                                   # 累计；够 min_speech 就 START
    return TurnEvent("start", max(self.run_start - self.pre_roll, self.floor), self.position)
if is_speech:
    self.run = 0                          # 停顿结束，静音重新计时
    return None
...                                       # 累计；够 hangover 就 END
return self._end(self.run_start)          # 最后一个语音帧的结尾
```

- **连续**：课里的 `TurnDetector` 在 idle 状态下遇到静音什么也不做，`speech_ms` 一直累加，零星的点击声最后会凑成一轮。测试里每 10 帧一下点击，共 20 下，必须一个事件都没有。
- **按采样点比**：连续语音和连续静音都按采样点累计，再和 `min_speech`、`silence_hangover` 比。16 kHz、20 ms 一帧时，250 ms 是 12.5 帧，要到第 13 帧才够，和课里合成流在第 13 个语音 chunk 才 START 一致。用 `min_speech // frame_len` 算要几帧，会早一帧开始。
- **两种时间**：每个事件带两个位置。`sample` 是这一轮音频的边界，`decided` 是检测器知道这件事时的位置。START 判定晚了约 `min_speech_ms`，音频却要从语音起点再往前 `pre_roll_ms` 开始，所以首字不会丢；END 判定晚了一个 hangover，音频在最后一个语音帧结束的地方结束。
- **下限**：pre-roll 不能早于 0，也不能伸进上一轮。测试里 pre-roll 比 hangover 长，第二轮按 pre-roll 算会从 320 开始，必须停在上一轮结尾 960。
- **flush**：课里的 flush trick 是“判定说完了就让 STT 立即出结果”。检测器这边的 `flush()` 立即结束打开的轮次，结束位置同样是最后一个语音帧的结尾，不等 hangover；还没凑够最短语音的那段直接丢掉，之后的语音要重新攒够 `min_speech_ms`。最后一帧还是语音时，没有正在累计的静音，结束位置就是当前位置。flush 和 hangover 结束的轮次走同一个 `_end`，所以 flush 结束的那一轮同样是之后 pre-roll 的下限。

最后的端到端检查用的是课里那条合成流：第一轮的起点按 pre-roll 算是负数，停在 0；结尾是 17600，也就是语音结束后再加上 Part 1 那 100 ms 的 hangover。咳嗽经过能量门后只有 6 帧，不到 13 帧的最短语音，不算一轮。第二轮从 29120 往前推 300 ms，是 24320。如果照抄课里的写法，咳嗽那 6 帧会被算进第二轮，第二轮会从 20800 开始。服务在每一轮结束时把这一轮的音频交给 STT，紧接着发 flush，这就是课里 Step 4 的骨架。

## Part 4 级联流式

```python
async for chunk in chunks:
    pending.extend(chunk)
    while len(pending) >= frame_len:
        frame = pending[:frame_len]
        del pending[:frame_len]
        context.append(frame)             # deque(maxlen=context_frames)，每一帧都进
        frames += 1
        speech = False
        if gate(frame):                   # 第一层：每帧都跑，几乎不要钱
            calls += 1
            speech = model([x for f in context for x in f]) >= speech_prob
        if speech != speaking:
            speaking = speech
            yield _event("speech" if speech else "silence", {"sample": position})
        position += frame_len
yield _event("stats", {"frames": frames, "model_calls": calls, "skipped": frames - calls})
```

- **只在门后调用模型**：被门拒掉的帧直接判成静音，不调用模型；`skipped` 就是门替模型省下的调用次数。
- **context 不看门**：模型要看当前帧和它前面的几帧，不管那几帧有没有过门。门拒掉的帧也要进缓冲，否则模型看到的上下文和“每个过门帧都带着前文去问模型”不一样，判定会变。测试第 2 帧就是这样：前面两帧是静音，模型只看到三分之一的语音，判成不是语音；只缓存过门的帧，模型会看到满满一帧语音。
- **跨块**：帧和 context 都由缓冲区自然拼好，所以无论怎么切块，包括空块和一个采样点一块，结果都一样。
- **及时**：判定一变就 `yield`，第一个事件出来时正好拉取了 5 块。`while len(pending) > frame_len` 要多等一个采样点，先处理缓冲里已有的帧、再把新块加进去会晚一块，两种都会多拉一块。
- **位置用整数**：`position` 按采样点累加，事件里的位置不会漂移。
- **格式**：由测试的 `parse_sse` 决定：每个事件一行 `event:`、一行 `data:`，后面恰好一个空行。结尾不足一帧的 7 个采样点丢掉，不计入 `frames`。

## Part 5 重叠语音结构

```python
order = sorted(spurts, key=lambda s: (s[1], -s[2]))     # 同时开始时，长的在前
for speaker, start, end in order:
    ...                                                   # 自己和自己重叠就报 ValueError
    running = [n for n in running if n["end"] > start]    # 还没结束的 spurt，按时间顺序
    parent = next((n for n in reversed(running)
                   if n["end"] >= end and n["speaker"] != speaker), None)
```

- 按（开始，结束取负）排序后，包住当前 spurt 的那些一定已经出现过。在还没结束的 spurt 里从后往前找第一个包住它的，就是最里层的那个，所以能嵌任意多层。
- 只看开始时间会把“开始在里面、结束在外面”的那段也挂进去；这种是接过了话轮，是新的 turn。
- 区间左闭右开：结束于 `start` 的 spurt 已经结束，所以首尾相接不算嵌套，同一个人前后相接也不算重叠。
- backchannel 的判断用整数比较 `(end - start) * 1000 < backchannel_ms * sample_rate`，不经过浮点，也不会拿采样点直接和毫秒比。
- 每个人记一个“说到哪了”，下一段的开始早于它就是自己和自己重叠。这种输入说明上游没有合并（Part 2 的表会合并），报 ValueError。只和排序后的前一段比较，会漏掉中间隔着别人的情况，测试里 A 的两段之间就夹着 B。空的 spurt 也报 ValueError。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试 dB 和线性量的换算、按采样点精确地存储和合并区间、写对轮次状态机的边界（连续语音、pre-roll 回溯和下限、hangover、flush）、写一个跨块拼帧并且只在必要时调用模型的异步流，以及把重叠的区间建成树。它不涉及真实的 Silero 或 Cobra 模型和 ONNX 推理，不涉及在真实录音上调阈值、算 precision/recall 或 TPR@FPR，也不涉及语义 turn detector 的训练、回声消除和真实 STT 的 flush 接口。课里的练习 2 和练习 3 需要另外动手跑。
