# 参考答案讲解：WavLab（06/01）

计时结束后再看。参考实现在同目录的 `wavlab/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 PCM 编解码

**现象**：解锁后的第一个错误是 `encode_pcm16` 里的 `struct.error: 'h' format requires -32768 <= number <= 32767`（Python 3.10 写作 `short format requires (-32767 -1) <= number <= 32767`），而 `encode_pcm16` 只负责把整数打包，那一行本身没有 bug。

**顺着往上找**：越界的数是 32768，来自 `float_to_pcm16(1.0)`。它先把浮点数裁到 [-1, 1]，再乘 32768，而 1.0 × 32768 正好比 int16 的上限大 1。饱和要放在缩放之后，裁的是整数：`max(-32768, min(32767, round(x * 32768)))`。这一关想练的是：报错的位置往往不是出 bug 的位置。

只在 `encode_pcm16` 里把打包前的整数夹到 int16 范围，第一个断言也能过，但 `float_to_pcm16(1.0)` 还是返回 32768，以后谁直接调用它都会出错。所以测试紧接着单独检查 `float_to_pcm16`，要求修在根因上。

**依次修四处**：

1. `float_to_pcm16`：先缩放，再把整数饱和到 [-32768, 32767]。
2. `decode_pcm16`：按帧交织拆声道，`values[c::n_channels]`。原代码按声道分块切，单声道正好不受影响，立体声全错。
3. `float_to_pcm16`：`int()` 向零截断，改成 `round()`。0.6 个量化步应该是 1，截断成了 0。课里的 `write_wav` 就是这样写的，测验 Q10 讲的往返误差，一个来源就在这里。
4. `encode_pcm16`：每一帧都 `ints = ints + [...]`，相当于把整个列表复制一遍，是 O(n²)，40,000 个样本大约要 1.6 秒。改成一个列表推导式，大约 7 毫秒。

**护栏**：最顺手的修法是把 32768 换成 32767，1.0 就不溢出了，课里的 `write_wav` 也是这么写的。但读的时候除以 32768、写的时候乘 32767，32767 读回来是 0.99997，再写就只剩 32766：每存一次，响的样本就掉一个量化步。测试把 65,536 个 int16 值全部解码再编码，要求一个都不变，这种修法过不去。

## Part 2 WAV 归档

参考实现自己拼文件头，没有用 wave 模块：

```python
fmt = struct.pack("<HHIIHH", 1, n_channels, sample_rate, sample_rate * block_align, block_align, 8 * width)
return _chunk(b"RIFF", b"WAVE" + _chunk(b"fmt ", fmt) + _chunk(b"data", data))
```

`_chunk` 写出 id、size 和 payload，size 是奇数时再补一个 0 字节。RIFF 的 payload 是用 `_chunk` 拼出来的，所以补齐字节自然算进了 RIFF 的 size，而 data 自己的 size 不算它。

容易漏的几点：

- **每帧字节数和每秒字节数**都要乘声道数。只算一个声道，立体声的文件头就和 wave 模块对不上。
- **24-bit**：每个样本 3 个字节、小端补码，满幅是 2²³。写的时候和 16-bit 一样四舍五入、饱和到 [−2²³, 2²³ − 1]；读的时候用 `int.from_bytes(..., "little", signed=True)` 做符号扩展，否则 -1 会读成 16,777,215。
- **位深跟着 Audio 走**：读回来的 Audio 带着 sample_width=3，再写还是 24-bit，`encode_wav(decode_wav(blob)) == blob`。
- **补齐字节**：wave 模块不写它，RIFF 的 size 也就少算 1。测试里 9 字节的 24-bit data 后面必须有一个 0，RIFF 的 size 要算上它，data 的 size 不算。wave 模块读这样的文件没有问题。
- **校验**：`zip(*channels)` 会把不等长的声道静默截到最短，要先检查；8-bit WAV 是无符号的另一套编码，归档不收。

16-bit 和 24-bit 整数网格上的浮点数，乘 2¹⁵ 或 2²³ 都是精确的，所以读出来的 Audio 和写进去的完全相等。

## Part 3 主频

核心几行（参考实现里另外处理了 log(0) 和分母为 0）：

```python
mean = sum(samples) / n
mags = dft_magnitudes([(x - mean) * w for x, w in zip(samples, hann(n))])
k = max(range(1, n // 2), key=mags.__getitem__)
a, b, c = (math.log(m) for m in mags[k - 1 : k + 2])
return (k + 0.5 * (a - c) / (a - 2 * b + c)) * sample_rate / n
```

- **峰值插值**：过 (−1, a)、(0, b)、(1, c) 三点的抛物线，顶点在 (a − c) / (2(a − 2b + c))。课里的 `peak_freq` 把 440 Hz 报成 437.5 Hz，插值后是 440.18 Hz。
- **对数幅度**：Hann 窗的主瓣接近高斯形，取对数后接近抛物线，所以在对数幅度上插值偏差小。同样的 440 Hz，用线性幅度是 439.43 Hz，不加窗是 438.25 Hz，顶点符号写反是 434.82 Hz。
- **直流**：先减均值。只跳过 bin 0 不够，因为 Hann 窗会把直流漏到 bin 1，0.6 的直流偏移在 bin 1 上比 0.2 的正弦还响。课里的 `peak_freq` 没跳过 bin 0，测验 Q12 提过这个问题。
- **混叠**：先对采样率取模，再关于 sr/2 翻折。课里 Step 5 用的 `sr − f` 只在 sr/2 < f < sr 时成立，12 kHz 在 10 kHz 采样下会算成 −2000，实际是 2000。只减一次 sr 也不够：26 kHz 减一次还剩 16 kHz，再套 `sr − f` 得到 −6000，实际是 4000。测试最后用 DFT 实测这几个音，峰值和公式算出的混叠频率相差不到 0.25 Hz。

## Part 4 流式降采样

用一个只保留最近 31 个样本的 deque 存滤波器历史，外加一个记录整条流样本下标的整数：

```python
async for chunk in chunks:
    pending += chunk
    whole = len(pending) - len(pending) % 2
    (samples,) = decode_pcm16(pending[:whole], 1)
    pending = pending[whole:]
    out = []
    for x in samples:
        recent.appendleft(x)
        if index % factor == 0:
            acc = 0.0
            for h, v in zip(taps, recent):
                acc += h * v
            out.append(acc)
        index += 1
    if out:
        yield encode_pcm16([out])
```

`recent[0]` 是最新的样本，所以 `taps[k]` 乘的正是 `decimate()` 里的 `samples[n - k]`。

- 半个样本留在 `pending` 里，等下一次 read 补齐。
- 滤波器历史在 `recent` 里跨 read 保留。开头用 0 填满，和 `decimate()` 里“开始之前的样本当 0”一致；每个输出按同样的顺序求和，所以结果和 `decimate()` 逐位相同，怎么切 read 都一样。
- 输出用 `encode_pcm16` 打包，四舍五入和饱和都和 Part 1 一样。测试允许和 `decimate()` 差半个量化步，所以换一种求和顺序也能过；`int()` 截断会差到将近一步，过不了。
- “每 3 个取 1 个”看的是整条流的下标 `index`，不是 read 内的下标。
- 有输出才 yield。空块会让识别器以为流结束了。
- 滤波器是因果的，只用当前和过去的样本，所以第一个 read 一到就能输出，第一块出来时只拉取了 1 次 read。
- 这个滤波器把 24 kHz 下 7 kHz 的音（课里 Step 6 的例子，直接抽取会折到 1 kHz）压低了约 72 dB，440 Hz 的增益是 0.999。

## Part 5 RIFF chunk 树

每次调用只读一个 chunk，遇到容器就递归读它的子 chunk，然后返回下一个 chunk 的位置：

```python
def _read_chunk(blob, pos, end, prefix, out):
    chunk_id = blob[pos : pos + 4]
    (size,) = struct.unpack_from("<I", blob, pos + 4)
    start, stop = pos + 8, pos + 8 + size
    if stop > end:
        raise ValueError(...)
    name = prefix + chunk_id.decode("latin-1")
    if chunk_id in CONTAINERS:
        name += ":" + blob[start : start + 4].decode("latin-1")
        out.append((name, start, size))
        child = start + 4
        while child < stop:
            child = _read_chunk(blob, child, stop, name + "/", out)
    else:
        out.append((name, start, size))
    return stop + size % 2
```

参考实现里还检查了 chunk 头不完整和容器缺类型的情况；`walk` 先确认文件以 RIFF 开头。改了扩展名的 MP3 以 ID3 标签开头，不检查的话会被当成一个空的叶子 chunk。

- `end` 是父 chunk 的结尾，不是文件的结尾。测试里的 INAM 声称有 50 字节，超出了它所在的 LIST，但没有超出文件，只和文件总长比较查不出来。
- 越界只看 payload 本身（`stop > end`），不看补齐字节，所以父 chunk 的最后一个子 chunk 缺补齐字节也能读。wave 模块写的奇数长度 24-bit 文件就是这样，RIFF 的 size 是 45。
- 容器记下的 offset 是 `start`，也就是 4 字节类型所在的位置，和叶子一样是 payload 的起点，`blob[offset : offset + size]` 对每个 chunk 都是它的 payload。
- 下一个位置是 `stop + size % 2`，跳过补齐字节。INAM 的 "Zoë\0" 是 5 个字节，漏了这一步，后面全部错位。
- 只有 RIFF 和 LIST 递归。JUNK 里那段旧的 LIST 是编辑器删 chunk 时留下的，只能当叶子。
- 结果是按文件顺序排的列表，同名 chunk 都在。
- `info_tags` 在 walk 的结果里找 `RIFF:xxxx/LIST:INFO/<id>`，去掉结尾的 NUL，再按 UTF-8 解码。

## 这套题证明了什么，没证明什么

通过了说明你能在这个规模的代码里调试 PCM 编解码，按规范写出逐字节正确的二进制文件，实现带插值的频率估计，写有状态的流式滤波器，以及递归解析嵌套的二进制结构。它不涉及 FFT、真实录音的解码（FLAC、MP3、Opus）、有理数倍的重采样，也不涉及滤波器本身的设计。课里的练习 2（48 kHz 录音降到 16 kHz 后对比混叠）和练习 3（手写 STFT）需要另外动手跑。
