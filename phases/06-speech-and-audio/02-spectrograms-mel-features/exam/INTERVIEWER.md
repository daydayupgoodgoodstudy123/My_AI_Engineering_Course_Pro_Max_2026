# 面试官手册：MelKit（06/02）

候选人计时期间不要看。候选人手里只有 README、`melkit/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 能改测试里的 n_fft、n_mels 吗？ | "No. The tests stay as written." |
| 1 | mel_filterbank 的默认采样率要留着吗？ | "Your call. Every caller has to pass the real rate." |
| 1 | Whisper 会把音频补到 30 秒，这里要补吗？ | "No. Scale the frames you are given, as one clip." |
| 2 | 缓存文件用什么格式？ | "Your call. It has to give back exactly the same floats and the same shape." |
| 2 | 同一个键写两次怎么办？ | "Replace the old entry, as the docstring says. The tests never write a key twice." |
| 2 | 要考虑多个进程同时写吗？ | "Not for the tests. Tell me what you would do." |
| 3 | 边缘之外的帧怎么取？ | "Copies of the first and last frame, as the docstring says." |
| 3 | 标准差除以 N 还是 N − 1？ | "N, the number of frames." |
| 3 | floor 加在标准差上还是方差上？ | "On the standard deviation, as the docstring says." |
| 4 | 预热之前能用训练集的全局统计吗？ | "Not in this version. Hold the frames back." |
| 4 | flush 之后还会再 push 吗？ | "No. flush means the stream has ended." |
| 4 | 某一帧的维度不对？ | "That's a bug upstream. Raise a ValueError." |
| 5 | override 能删掉一个键吗？ | "No. None is an ordinary value: fmax None means Nyquist." |
| 5 | 原来是标量、override 给了 dict？ | "The override replaces it whole." |
| 5 | 0 和 0.0 的指纹要一样吗？ | "Not required. The tests don't cover it." |

## 每关：要看什么、提示、追问

### Part 1 修 log-mel 代码（目标 12 分钟）

一个测试里叠了 4 个缺陷和 2 个护栏：

1. `hz_to_mel` 用了自然对数 `math.log`，配的却是 log10 的常数 2595。错误不在 `hz_to_mel` 报出来，而是在上一层的 `mel_filterbank` 里报 `mel filter 18 of 40 covers no FFT bins`：mel 范围被放大约 2.3 倍，换回 Hz 后一半以上的滤波器边缘越过 Nyquist，被截到最后一个 bin，从编号 18 的滤波器起宽度为零。报错看起来像“n_fft 太小、mel 太多”，根因却是换算常数。
2. 修好第 1 处，报的还是 covers no FFT bins，只是换成了 `mel filter 0 of 40`，括号里写着 `sr=16000`，而测试传的是 8000。`log_mel_spectrogram` 调 `mel_filterbank` 时没有传 `sr`，用上了默认的 16 kHz：每个 bin 被当成 62.5 Hz 宽，最低的几个边缘挤到同一个 bin 上。这就是课里的“采样率不一致”，只不过发生在一次函数调用里。
3. `whisper_log_mel` 在每一帧里各取最大值再往下截 8，docstring 写的是整段 clip 里最响的值。按帧截断时，安静的帧保留了比整段最响处低 80 dB 以上的细节，和 Whisper 训练时见到的分布对不上。
4. `apply_filterbank` 把稀疏的滤波器展开成稠密矩阵，每帧把 80 × 1025 个权重全部乘一遍，600 帧要 1.3 秒左右。只遍历每个滤波器的非零区间，大约 9 毫秒。
5. 护栏一：同一个 1 kHz 正弦波在 16 kHz、`fmax=4000` 下也必须落在第 18 个频带。为了让 8 kHz 的用例通过而把默认值改成 8000，这里会落到第 11 个频带。
6. 护栏二：稀疏写法的结果要和稠密矩阵一致（容差 1e-12）。区间错开一个 bin，这条断言会拦住。

另外三种常见的错误修法都有断言拦住：删掉“covers no FFT bins”这个检查，1 kHz 的正弦波会落到编号 7 的频带；把 `mel_to_hz` 改成 `math.exp`，1000 Hz 会变成 2303 mel；改成 `1127 * ln`，3000 Hz 往返一次差 0.03 Hz。

测试里关于功率（音量翻倍加 log 4）、dB、静音下限的几条断言一开始就能通过，它们约束的是候选人修改时不能改坏的行为。

计时断言的余量：参考写法和 `sum(map(operator.mul, f.weights, frame[f.start:f.start + len(f.weights)]))` 都在 10 毫秒左右，逐个下标的生成器写法约 17 毫秒。写成 `zip(f.weights, frame[f.start:])` 也能过，但每个滤波器都把剩下的频谱复制一遍，约 50 毫秒，离限值只有 2 倍，机器忙时可能超时。遇到这种写法，问候选人这个切片要复制多少个元素。

看什么：是不是先看 traceback 停在哪一层；修完第一处又看到同一条报错时，会不会读出括号里的 `sr=16000`；是不是打印 edges 或 `hz_to_mel(4000)` 看实际数值；是不是对照 docstring；每改一处就重跑。

提示：
- H1："The error says a filter covers no bins. Which FFT bins do the filter edges land on?"
- H2："What should hz_to_mel(4000) be, and what does it return? Which sample rate was this filterbank built for?"
- H3：直接指出 `hz_to_mel` 的对数底，或者 `log_mel_spectrogram` 里漏传的 `sr`。

追问：
- "librosa defaults to sr=22050. How does a default sample rate bite in production?"（漏传时静默用默认值，输出形状不变，每个频带对应的频率却全错了。让采样率成为必填参数，并在两端记录它）
- "Why does Whisper clamp at the clip's maximum minus 8 rather than at a fixed floor?"（下限跟着这段音频最响的地方走，整体音量变大或变小时，被截掉的部分不变；比最响处低 80 dB 以上的部分基本是噪声）
- "The lesson's code uses max(v, eps). Why is that better than v + eps?"（不改动正常数值，只给接近 0 的值兜底）
- "Why is the dense matmul fine in NumPy but slow here?"（NumPy 的矩阵乘法是向量化的；纯 Python 里每一次乘法都有解释器开销，所以要利用稀疏性）
- "How would you catch a model trained on 80 mels being served 128?"（两端都记录特征形状并断言，课里的第一条坑）

### Part 2 特征缓存（目标 12 分钟）

坑：
- 用 float32 存（`array("f")` 或 struct 的 `"f"`）：0.1 + 0.2 变了，5e-324 变成 0，-1e300 变成 -inf。
- 只存行不存宽度：短于一帧的 clip 是 0 行特征，读回来宽度就没了。测试要 `(0, 40)`。
- 键里没有 config：同一个 clip 换了 n_mels，读到的还是旧特征，也就是课里说的 mel 数不一致，而且不报错。
- clip 哈希里没有采样率：同一串样本在 8 kHz 和 16 kHz 下是两段不同的音频。
- 哈希精度：测试里两段音频只差最后一个样本的最低一位（`math.nextafter`）。用 float32、`round`、`f"{x:.6f}"`，甚至 `f"{x:.16g}"` 来哈希，都会撞上同一个键；float64 要 17 位有效数字才能区分，`repr` 或 8 字节的 `struct` 才够。
- 校验要逐行对 `n_feats`：测试给了两个坏矩阵，一个每行 2 个值（行与行一致，但不等于 3），一个三行分别 3、2、4 个值（第一行是对的，总数正好 9 = 3 × 3）。只查第一行、只查行与行是否一致、只查总数，都会漏掉其中一个。
- 先写文件再校验：被拒绝的矩阵已经落盘。第二个坏矩阵正好能被读成一个完全合法的 3 × 3 矩阵。
- 存在内存里的 dict：重新打开就没了。

可以接受的写法：用 JSON 存也能一位不差。同一个键写两次时跳过不写，测试也拦不住；内容寻址的键对应的特征本来不变，这样做说得通，但 docstring 要求覆盖，让候选人说出自己的选择。

追问：
- "The model consumes float32 anyway. Why insist on exact round trips?"（缓存不应该悄悄改变数值；要压缩就在写入前明确转换，并让读写两端用同一种精度）
- "Two workers compute the same clip at the same time?"（写临时文件再 `os.replace`，替换是原子的；两边内容相同，谁最后写都一样）
- "What else belongs in the key?"（特征代码的版本、依赖库版本；配置指纹在 Part 5）
- "The cache directory keeps growing?"（按访问时间淘汰，设容量上限）

### Part 3 delta 和 CMVN（目标 12 分钟）

坑：
- 分母是 2·Σn²（width=2 时是 10）。写成 Σn²，斜率翻倍。
- 边缘要复制首尾帧。Python 的负下标不报错，`frames[t - n]` 在开头会绕到最后几帧；补零会在边缘造出假的跳变；镜像取帧（`frames[abs(t - n)]`）让直线在两端的 delta 变成 0，而不是 0.5。
- delta-delta 是对 delta 再求 delta，而且第二阶用自己的宽度（测试里 `windows=[2, 1]`）。用二阶差分，或者两阶都用 `windows[0]`，内部数值一样，边缘对不上。
- 阶数由 `windows` 的长度决定，`windows=[]` 只返回静态特征。写死两阶会在这里报 IndexError。
- CMVN 按维度、沿时间计算，不是按帧计算。测试用 4 × 2 的矩阵，方向错了数值完全不同。
- `cmvn` 返回新的行，不能原地改输入。原地归一化漏过去的话，Part 4 的测试会对同一批帧反复调用 `cmvn()`，报错的位置会让人摸不着头脑。
- 用总体标准差（除以帧数），不是 `statistics.stdev` 的样本标准差。
- 常数维要有 floor，否则除零。静音时卡在 log(floor) 的频带就是这种维度。
- 最后一段把 Part 1 的 log-mel 接上 delta 和 CMVN：40 维变成 120 维，每一维均值 0、方差 1。

测试拦不住、但值得追问的写法：floor 加在方差上（`sqrt(max(var, floor))`），等于把标准差的下限抬到 1e-4，和 docstring 不一致；一遍算出 E[x²]−E[x]² 的方差，在这组数据上也能过，问它在特征带大偏移时为什么不稳定。

追问：
- "Deltas before CMVN or after? Does it matter?"（均值在差分里抵消；方差归一化会改变 delta 的尺度。这里先 delta 后 CMVN）
- "Per-utterance CMVN needs the whole utterance. What do you do in streaming?"（引到 Part 4）
- "Give a concrete way normalization drift ships."（训练按句 CMVN，上线换成全局统计或在线统计，形状不变、不报错，WER 变差）

### Part 4 在线 CMVN（目标 12 分钟）

坑：
- 统计量要跨块累积，不能每块重新开始。
- 不能先把一整块加进统计量再归一化这一块：那样某一帧用到了它后面的帧，结果随切块方式变化。
- 前 warmup 帧要扣住，凑齐后一起放出，用的是这 warmup 帧的统计量；之后每帧一到就输出，统计量包含它自己。
- 预热看的是累计帧数：写成 `count > warmup` 会晚放一帧；用 `len(self.held) >= warmup` 判断，预热结束后又会重新开始扣帧。
- Welford 的方差是 M2 除以帧数，与 `cmvn()` 一致；除以 count − 1 对不上。
- flush 要放出还扣着的帧；流比 warmup 短时也要有输出。
- 第三维是常数 1.5，需要 floor。
- 计时断言：每来一帧就对目前所有帧重算一遍 `cmvn()`，结果完全正确，但 1000 帧要 0.5 到 0.6 秒，是 O(T²)。用 Welford 的运行均值和 M2，每帧 O(dim)，约 2 毫秒。

追问：
- "100 warm-up frames is a second of latency at a 10 ms hop. Alternatives?"（用训练集的全局统计做先验，帧数多了再逐渐过渡到运行统计；或者滑动窗口）
- "The speaker changes halfway through the stream?"（累积统计反应慢；滑动窗口或指数遗忘）
- "You trained with per-utterance CMVN and you serve with this. Problem?"（是，就是课里的 normalization drift；训练也用同样的在线方案，或者两边都用全局统计）
- "Why not keep a running sum and sum of squares?"（这样写能通过测试，Kaldi 的 CMVN 统计量也是这么存的；但数值大、方差小时相减会抵消有效位，Welford 更稳）

### Part 5 配置合并和指纹（目标 12 分钟）

坑：
- dict 要递归合并。`{**a, **b}` 或 `update` 会把整个 `mel` 子树换掉，`fmin` 和 `fmax` 就没了。
- list 整体替换，不拼接，也不按位置合并。
- 不能改到输入：浅拷贝 base 会改坏模块级的 `DEFAULTS`，之后所有配置都跟着错；把 override 里的 list 直接放进结果，结果一改，override 也变了。每一层用 `dict(below)` 复制再递归的写法，被覆盖的子树是新的，没被覆盖的子树（比如 `log`）仍然和 `DEFAULTS` 共用，测试会改 `cfg["log"]` 来查这一点。
- 未知键报 KeyError，并且带点分路径 `mel.n_mel`。只报叶子名 `n_mel` 时，测试的 `match` 对不上。顶层的拼写错误同样要报，比如 `sample_rte`：悄悄收下的话，前端会按默认的 16 kHz 跑，又是课里的采样率不一致。
- None 是普通值：`fmax: None` 表示 Nyquist。把 None 当成“没设置”而保留下层的值，指纹不变，测试会拦住。
- 指纹与键顺序无关，每一层都要排序。`json.dumps(..., sort_keys=True)` 能做到，只对顶层排序不行。
- list 的顺序是内容的一部分：`windows` 为 `[2, 3]` 和 `[3, 2]` 时特征不同，不能为了“规范化”把 list 也排序。
- 不能用内置 `hash()`：字符串的 hash 每个进程都不同（PYTHONHASHSEED），磁盘缓存每次重启都会全部失效。测试会起两个子进程来比对。
- 最后一段：同一个配置换个键顺序，要命中 Part 2 的缓存；n_mels 改了，要重新计算。

追问：
- "Why reject unknown keys instead of ignoring them?"（`n_mel` 这种拼写错误会悄悄退回默认的 80，正是 mel 数不一致的来源）
- "Should 0 and 0.0 get the same fingerprint? True and 1?"（Python 里它们相等，但配置语义不同；要么在加载时规范类型，要么接受多算一次）
- "The front-end code itself changes. Is the fingerprint still enough?"（不够，要把特征代码版本也放进键里）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看数据、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出采样率和特征配置在训练、上线两端一致，缓存失效、延迟、数值稳定 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
