# 参考答案讲解：Provenance（06/16）

计时结束后再看。参考实现在同目录的 `provenance/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修检测器

**现象**：解锁后的第一个错误是 `average_spectrum` 里的 ZeroDivisionError，而那里的除法本身没有错。

**顺着往上找**：测试给的 clip 正好 256 个样本，也就是一帧。`average_spectrum` 除以帧数，帧数是 0，因为 `frame_starts(256, 256)` 是 `range(0, 0, 256)`。课里的 `magnitude_spectrum` 用的也是 `range(0, len(audio) - n_fft, n_fft)`：1 秒的音频只切出 62 帧，最后一个完整帧被漏掉（测验 Q11a）。

**依次修五处**：

1. `frame_starts`：终点加 1，写成 `range(0, n_samples - n_fft + 1, n_fft)`。
2. `power_spectrum`：返回 `re * re + im * im`，不开方。课里的代码累加的是幅度，名字却叫能量占比。幅度会把弱的 bin 抬高：幅度比 2:1 的两个音，能量比是 4:1，高频占 1/5；按幅度算是 1/3。
3. `high_band`：FFT 点数是 `2 * (len(spec) - 1)`，不是 `len(spec)`。256 点 FFT 的单边谱有 129 个 bin，bin k 的中心频率是 k·sr/256，bin 64 正好是 4 kHz。课里直接取 `spec[len(spec) // 2:]`，也就是 sr/4 以上，只有在 16 kHz 时它才等于 4 kHz。
4. `toy_detector_score`：去掉两个能量上的 1e-12，直接用高频能量除以总能量；占比为 0（静音就是这样）时返回 FLOOR_DB，其余情况返回 `max(FLOOR_DB, 10 * log10(share))`。
5. `average_spectrum`：每帧的功率谱只算一次，再按 bin 求平均。原来的推导式外层是 bin、内层是帧，每个 bin 都把每帧的 DFT 重算一遍。8 帧要 1 秒左右，改完大约 8 毫秒。

**第 4 处为什么要这样修**：原代码给两个能量各加 1e-12，是想躲开 log(0)。静音时两个能量都是 0，占比变成 1e-12/1e-12 = 1，也就是 0 dB，成了最可疑的分数。只把静音单独处理、留着这个常数也不行：常数在安静的 clip 上占了比重，同一段音频小 80 dB，分数就变了，而伪造检测器的分数不能随播放音量变化。正确的做法是在占比上截断：占比本身和音量无关，截断只影响本来就低于下限的分数。

**护栏**：除了上面的音量护栏，“分数在下限处截断”这一条针对去掉 max、改成给占比加 1e-10 的写法，1 kHz 纯音会得 −99.49 而不是 −100。另外两条针对差一错误和 bin 换算的过度修复：`range(0, n_samples, n_fft)` 会把结尾 200 个样本的残帧也算进来；`2 * len(spec)` 会让 bin 64 落在 3969 Hz，漏掉正好 4 kHz 的音。

## Part 2 审计日志

参考实现只有一张表：自增的 `entry_id` 负责顺序，也就是 1、2、3 的 id；`threshold` 和 `score` 存在 REAL 列里；`at` 转成 UTC 后存成 ISO 文本；`verdict` 由日志自己按 `score >= threshold` 算出来再存，所以它不会和存下来的数字矛盾。

容易漏的几点：

- **commit 和重开**：用 `with self._db:` 自动提交；建表写 `IF NOT EXISTS`。
- **NaN 在 Python 里拦**：SQLite 把 NaN 存成 NULL，靠 NOT NULL 约束也拦得住，但报的是 IntegrityError。更要紧的是，NaN 和任何阈值比较都是 False，不拦的话，坏掉的检测器会把所有 clip 都判成真人。
- **数字原样存**：校准扫出来的阈值是 0.30000000000000004，分数 0.3 的 clip 差这一点点，判 bonafide。round、格式化成固定位数的小数、float32，都会把两个数变成一样，审计时重新判定就和记录对不上。Python 的 float 存进 REAL 列，或者用 `repr` 存成文本，都能原样读回。
- **时间转成 UTC**：只接受带时区的时间，存之前 `astimezone(timezone.utc)`。审计记录要跨地区比较和排序，统一成 UTC 最省事。
- **flips**：拿存下来的分数，按同一个 `>=` 规则和新阈值重判，只看这一个模型。阈值改到 0.3 时，分数正好 0.3 的那一条翻成 spoof。这就是课里 Pitfalls 说的“在你自己的域上校准”：改阈值之前，先看清它会改变哪些已经做过的判定。

## Part 3 水印定位

`locate` 分三步：

1. 扫一遍概率，记下连续“严格大于阈值”的区间，左闭右开；扫完后还开着的区间收在 `len(probs)`。
2. 相邻区间之间的间隙不超过 `round(max_gap_s * sr)` 个样本时，连成一段。
3. 去掉长度小于 `round(min_s * sr)` 的段。

顺序很重要：先连再删。测试里 150 个样本的段和 90 个样本的段只隔 10 个样本，连起来是 250 个样本；先删短段的话，90 的那段已经没了。pyannote 的 Binarize 也是这个顺序：先填短间隙，再删短段。

`iou` 把两两相交的长度加起来当交集，并集用 |P| + |T| − 交集。一段可能和对面好几段相交，所以不能按位置配对，也不能每段只取最大的那个重叠。两个列表都为空时返回 1.0。

端到端那一段把前三关串起来：真人语音、生成语音、真人语音各半秒，配方来自课里的 `synth_real_speech` 和 `synth_fake_speech`，水印概率只在中间那半秒高。整段只有三分之一带水印。AudioSeal 的 `detect_watermark` 对整段只给一个数（超过 0.5 的样本所占的比例），这里大约是 0.33，按 0.5 判就是“没有水印”。逐样本定位找到的是 [8000, 16000)：2.5 毫秒的误报被去掉，12.5 毫秒的掉点被连上。同一个 clip 经过 Part 1 的检测器得 −16.1 dB，高于 −18 dB 的阈值，判 spoof，写进 Part 2 的日志；只有真人语音的 clip 得 −20.6 dB，判 bonafide。

## Part 4 实时告警

一个 async generator，状态有四个：平滑值 `s`、上一个分数的时间、当前告警的峰值（没有告警时是 None）、下一次最早能告警的时间。

```python
async for batch in batches:
    for t, score in batch:
        s = score if s is None else s + (1 - 0.5 ** ((t - last) / half_life_s)) * (score - s)
        last = t
        if peak is None:
            if s >= raise_at and t >= earliest:
                peak = s
                yield sse("alarm", {"t": t, "score": s})
        elif s < clear_below:
            yield sse("clear", {"t": t, "peak": peak})
            peak, earliest = None, t + cooldown_s
        else:
            peak = max(peak, s)
if peak is not None:
    yield sse("clear", {"t": last, "peak": peak})
```

- 平滑系数按两次分数之间隔了多久来算。窗口被跳过时（静音、丢包），旧的证据按半衰期衰减，不会因为“只隔了一个分数”就还占一半的权重。测试里 6.0 到 8.0 秒之间没有分数，8.0 秒的系数是 0.9375。
- 迟滞：到 0.75 告警，跌破 0.5 才解除，中间不改状态。分数在阈值附近抖动时，告警不会来回闪。两个边界都按 docstring：正好 0.75 算“到了”，正好 0.5 不算“跌破”。
- 冷却期从解除时刻算，只拦新告警，不停平滑。
- 每个事件一判定就 yield；结尾还开着的告警，在最后一个分数的时刻解除，已经解除的不再发。
- 测试里的分数和时间都取二进制下能精确表示的值，所以期望结果能写成精确的浮点数。`2 ** (-dt / half_life_s)`、`(1 - a) * s + a * score` 这类等价写法在这些值上算出来逐位相同。

## Part 5 manifest 链

先校验 active manifest 的 `c2pa.hash.data`，它绑定的是手里这份音频的字节。然后从 active manifest 开始做深度优先遍历，`path` 记当前路径，`done` 记已经查完的 manifest：

- ingredient 指向 `path` 里的 manifest 就是环，报 ValueError。这一步放在校验哈希之前：带内容哈希的引用不可能真的绕回自己，绕回来的 store 一定是写坏了，要直接报错，不能当成一个普通的 mismatch。
- 指向 `done` 里的 manifest 是菱形，正常，不再重复检查。
- 没有 `manifest` 字段的 ingredient（mix 里的 music bed）没带内容凭证，跳过，不算问题。
- 找不到报 `ingredient.manifest.missing`，哈希不对报 `ingredient.hashedURI.mismatch`，这两种链接都不往下走。
- 每个 manifest 记下它唯一的 parentOf；有两个时报 `manifest.multipleParents`，记成没有。
- 遍历到的 manifest 里（包括 active 自己），只要有一个 action 带 trainedAlgorithmicMedia，就记 ai_generated。store 里没走到的 manifest 和这份音频无关，不算。

history 从 active 开始，沿记下的 parentOf 一直走到没有为止。problems 收集在 set 里，最后排序；有了 `done`，被两条路径引用的 manifest 也只查一次。

“去掉 TTS 的 manifest”那一条最值得记住：ai_generated 变成了 False，两条 `ingredient.manifest.missing` 是仅剩的线索。课里说 C2PA 一重新编码就能剥掉，所以要和水印、检测器一起用，Part 3 和 Part 1 补的就是这一块。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里顺着调用链调试频谱代码，建一个能原样存取浮点数和时间的 SQLite 日志，实现带边界条件的区间后处理和 IoU，写一个按流时间工作的 async 告警器，以及在带哈希引用的 DAG 上做校验和遍历。它不涉及 AASIST、RawNet2 或 AudioSeal 的训练和推理，不涉及真实的 C2PA 签名、证书和 JUMBF 容器，也不涉及 ASVspoof 上的 EER 评估。课里练习 2 和练习 3 的内容需要另外动手跑。
