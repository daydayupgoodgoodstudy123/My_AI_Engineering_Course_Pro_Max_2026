# 面试官手册：WavLab（06/01）

候选人计时期间不要看。候选人手里只有 README、`wavlab/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 1.0 应该编码成 32767 还是 32768？ | "32767. It saturates; 32768 doesn't fit in an int16." |
| 1 | 正好差半个量化步时怎么舍入？ | "Python's round is fine. The tests stay away from exact halves." |
| 1 | 要不要加 dither？ | "No. Plain rounding." |
| 2 | 8-bit 或 32-bit float 的 WAV 要支持吗？ | "No. The archive only holds 16- and 24-bit PCM. Raise a ValueError." |
| 2 | WAVE_FORMAT_EXTENSIBLE 的文件头呢？ | "Also a ValueError, for now." |
| 2 | 可以用标准库的 wave 模块吗？ | "Sure, as long as the bytes come out right." |
| 2 | data 前后有别的 chunk 怎么办？ | "Our own files don't have any. Walking the chunks and skipping the ones you don't know is good practice; the tests don't cover it." |
| 3 | Hann 窗的分母用 N 还是 N − 1？ | "Use the hann() helper in the file. Either is accurate enough here." |
| 3 | 两个音一样响怎么办？ | "Take the lower bin. The tests don't cover ties." |
| 4 | 输入是 44.1 kHz 这种不是整数倍的呢？ | "Out of scope. The factor is always an integer." |
| 4 | 流在半个样本处结束怎么办？ | "Drop the stray byte." |
| 4 | 结尾要不要把滤波器剩下的输出冲出来？ | "No. The output ends where decimate() ends." |
| 5 | RIFF chunk 后面还有多余的字节？ | "Ignore them." |
| 5 | 录音机没回写文件头，size 是 0 或 0xFFFFFFFF？ | "Treat it as a broken file: ValueError." |
| 5 | INFO 里同一个标签出现两次？ | "The last one wins. The tests don't cover it." |

## 每关：要看什么、提示、追问

### Part 1 修 PCM 编解码（目标 10 分钟）

一个测试里叠了 4 个缺陷和 2 个护栏：

1. `float_to_pcm16` 先把浮点数裁到 [-1, 1]，再乘 32768，1.0 就成了 32768，超出 int16。错误不在 `float_to_pcm16` 报出来，而是在 `encode_pcm16` 的 `struct.pack` 里报 `struct.error`。
2. `decode_pcm16` 把字节按声道分块来切，没有按帧交织（L R L R）拆开。单声道看不出问题，立体声的值全错。课里的 `read_wav` 只认单声道，是同一类问题。
3. `float_to_pcm16` 用 `int()` 向零截断，没有四舍五入。这是课里 `write_wav` 的原样写法，测验 Q10 专门讲过。
4. `encode_pcm16` 每一帧都 `ints = ints + [...]`，把整个列表复制一遍，是 O(n²)。40,000 个样本大约要 1.6 秒。
5. 护栏：第一个断言后面紧跟着直接检查 `float_to_pcm16`。在 `encode_pcm16` 里把打包前的整数夹到 int16 范围，第一个断言也能过，但 `float_to_pcm16(1.0)` 还是 32768，会挂在 "float_to_pcm16 itself saturates"。
6. 护栏：每一个 int16 值解码再编码都必须原样回来。为了让 1.0 不溢出而把系数改成 32767（课里 `write_wav` 就是这么写的），会在这里挂掉：32767 读回来是 32767/32768，再乘 32767 只剩 32766。

看什么：是不是先读 traceback，找出是哪个值越界、它是哪个函数算出来的，再修在那个函数里，而不是修在报错的那一行；是不是先 `print(repr(...))` 看实际数据；每改一处就重跑。

提示：
- H1："Which value is out of range, and which function produced it?"
- H2："What does float_to_pcm16(1.0) return? What should it return?"
- H3：直接指出裁剪放在了缩放之前。

追问：
- "Some libraries read with 32768 but write with 32767. What happens to a file you decode and re-save ten times?"（每存一次，响的样本就掉一个量化步；本题读写用同一个系数，可以无损往返）
- "Is float32 enough to hold 16-bit audio?"（够。float32 有 24 位有效精度，课里 Key Terms 讲过）
- "When does dither matter?"（降低位深的时候，比如 24-bit 转 16-bit。解码后原样重编码不需要）

### Part 2 WAV 归档（目标 12 分钟）

坑：
- 文件头要和 wave 模块一字不差。每秒字节数和每帧字节数都要乘声道数，只算一个声道，立体声就对不上。
- 24-bit 样本是 3 个字节的小端补码，写的时候和 16-bit 一样要四舍五入、饱和，读的时候要做符号扩展。当成无符号读，-1 会变成 16,777,215。
- 读回来的 `Audio` 要带着 sample_width。只按 16-bit 处理的话，24-bit 的母带存一次就丢了 8 位。
- 奇数长度的 chunk 后面要补一个 0 字节：chunk 自己的 size 不算它，RIFF 的 size 要算它。wave 模块不写这个字节，测试专门对比了这一点。
- `zip(*channels)` 会把不等长的声道静默截到最短，要先检查，报 ValueError。
- 8-bit WAV 是无符号的另一套编码，归档不收，要报 ValueError。

追问：
- "A field recorder puts bext and iXML chunks before data, and a LIST:INFO chunk after it. What does your reader do?"（要按 chunk 遍历，跳过不认识的，data 只读它自己的 size 那么长。从第 44 字节一直读到文件末尾也能过本关，因为归档自己写的文件 data 总在最后，但遇到这种文件就会把别的 chunk 当成音频。按 chunk 遍历正是 Part 5）
- "An upload is 5 GB."（RIFF 的 size 只有 32 位，超过 4 GiB 要用 RF64 或 Wave64）
- "Two workers write the same archive key."（先写临时文件再原子 rename，或者用内容的 hash 做 key）

### Part 3 主频（目标 12 分钟）

坑：
- 先减均值再加窗。只跳过 bin 0 不够：Hann 窗会把直流漏到 bin 1，0.6 的直流偏移在 bin 1 上比 0.2 的正弦还响。
- 抛物线要拟合在对数幅度上，顶点在 k + (a − c) / (2(a − 2b + c))。符号写反，440 Hz 会算成 434.8 Hz；用线性幅度是 439.4 Hz；不加窗是 438.3 Hz。都超出 0.5 Hz 的容差。
- bin 换成 Hz 是 (k + δ) · sr / N。
- 混叠频率要先对采样率取模，再关于 sr/2 翻折。课里用的 `sr − f` 只在 sr/2 < f < sr 时成立，12 kHz 会算成 −2000。只减一次 sr 也不够：测试里的 26 kHz 是采样率的 2.6 倍，减一次还剩 16 kHz，应该落在 4000 Hz。
- 减掉均值后全是 0 的静音要报 ValueError。

追问：
- "Why log magnitudes?"（Hann 窗的主瓣接近高斯形，高斯取对数正好是抛物线，所以偏差小）
- "Would zero padding give better resolution?"（补零只让谱线更密，不提高真实分辨率。分辨率由窗长 N/sr 决定）
- "Make it fast for N = 16,000."（用 FFT；只关心某个已知频率时，用 Goertzel 算一个 bin）

### Part 4 流式降采样（目标 14 分钟）

坑：
- 一次 read 可能停在半个样本上。多出来的那个字节要留到下一次，不能丢。
- FIR 的历史样本要跨 read 保留，否则每个 read 开头的输出都会错。
- “每 3 个取 1 个”要按整条流的样本下标算，不能每个 read 从 0 重新数。
- 输出格式由测试的 `b"".join(...)` 加 `struct.unpack` 决定：yield 小端 int16 的 bytes，不是浮点数列表。
- 输出要像 `float_to_pcm16` 那样四舍五入、饱和，docstring 写了。测试只允许和 `decimate()` 差半个量化步，用 `int()` 截断会差到将近一步，和 Part 1 的第 3 个缺陷是同一个错误。
- 一次 read 没凑出新的输出样本时不能 yield 空块。docstring 写了，识别器会把空消息当成流结束。
- 数据一够就要 yield，不能先把流读完。测试会数被拉取了多少次 read。
- 写成普通的 async 函数时，测试报的是 `'async for' requires an object with __aiter__ method, got coroutine`，要会看出来这里需要 async generator。

追问：
- "The browser sends 44.1 kHz."（160/441 的有理数倍重采样，用多相滤波器；本题只做整数倍）
- "How much latency does this filter add?"（31 个 tap 的线性相位滤波器，群延迟 15 个输入样本，48 kHz 下约 0.3 ms）
- "The client disconnects mid-stream."（`aclose()` 会在 yield 处抛 GeneratorExit，资源在 finally 里释放）
- "The stream runs for an hour. How much does your generator keep in memory?"（只需要最近 31 个样本，加上不到一个样本的字节。把历史存成一直变长的列表也能过测试，但内存会一直涨）
- "The input is close to full scale."（这个滤波器有负的 tap，系数绝对值之和约 1.48，满幅附近的方波滤完会冲到 1.15 左右，所以输出要饱和。用 `encode_pcm16` 打包就自带饱和）
- "Why not just keep every third sample?"（课里 Step 5、6 的混叠。这个滤波器把 24 kHz 下 7 kHz 的音压低了约 72 dB，直接抽取的话它会折到 1 kHz）

### Part 5 RIFF chunk 树（目标 12 分钟）

坑：
- 要递归，层数不固定。AVI 的 LIST:strl 在 LIST:hdrl 里面，只写两层循环会漏掉。
- RIFF 和 LIST 的 payload 先是 4 字节的类型，后面才是子 chunk。offset 指向的是 payload 的起点，容器也一样：offset 是类型所在的位置，不是第一个子 chunk。测试检查每个 offset 前面 4 个字节正好是这个 chunk 的 size。
- 每一层都有补齐字节。INAM 的 "Zoë\0" 是 5 个字节，忘了跳过补齐字节，后面全部错位。
- 只有 RIFF 和 LIST 是容器。JUNK 里装着一段旧的 LIST（编辑器删 chunk 时改了名），也只能当叶子。
- 子 chunk 超出父 chunk 的范围要报 ValueError，不能读进兄弟 chunk 里。测试里的 INAM 声称有 50 字节，它所在的 LIST 只剩 4 字节，后面还跟着 64 字节的 data，所以只和文件总长比较是查不出来的。但父 chunk 的最后一个子 chunk 可以缺补齐字节：wave 模块写的文件就是这样，连 RIFF 本身的 size 都是奇数。
- 不以 RIFF 开头的文件要报 ValueError。测试用的是改了扩展名的 MP3（开头是 ID3 标签）。不检查的话，它会被当成一个 size 为 0 的叶子 chunk，“解析”得很顺利。
- 同名的 chunk（两个 labl）都要保留，按名字存进 dict 会丢。
- `info_tags` 只取 RIFF 下面一层的 LIST:INFO，去掉结尾的 NUL，按 UTF-8 解码。adtl 里的 labl 不是 INFO 标签。

追问：
- "A 6 GB recording?"（RF64：文件头换成 RF64，size 写 0xFFFFFFFF，真实大小放在 ds64 chunk 里）
- "The uploads are untrusted."（每一步都做边界检查；限制嵌套深度或者改用显式栈，防止恶意文件把递归打爆；限制总大小）
- "Read the INFO tags of a 2 GB file without loading it."（只读 chunk 头，用 seek 跳过 payload）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出规模、格式兼容、并发写、不可信输入 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
