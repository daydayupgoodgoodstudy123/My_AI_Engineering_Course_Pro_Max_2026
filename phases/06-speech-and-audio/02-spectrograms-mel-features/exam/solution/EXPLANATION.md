# 参考答案讲解：MelKit（06/02）

计时结束后再看。参考实现在同目录的 `melkit/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修 log-mel 代码

**现象**：解锁后的第一个错误是 `mel_filterbank` 里的 ValueError：`mel filter 18 of 40 covers no FFT bins`。这个检查本身没错，报错的函数也没有 bug。

**顺着往上找**：打印滤波器边缘对应的 FFT bin，会看到后面二十多个边缘全被截在最后一个 bin（128）上。边缘的算法是先在 mel 轴上等分 `hz_to_mel(fmin)` 到 `hz_to_mel(fmax)`，再用 `mel_to_hz` 换回 Hz。docstring 说 1000 Hz 约等于 1000 mel，代码却返回 2303；`hz_to_mel(4000)` 应该是 2146，代码返回 4941。它用的是自然对数，而 2595 是配 log10 的常数，两者差 ln 10 ≈ 2.3 倍。`mel_to_hz` 仍然按 10 的幂反算，mel 轴的上端换回来远远超过 Nyquist（fmax 为 4 kHz 时约 55 kHz），一半以上的边缘越界。报错文字容易让人以为是 n_fft 太小、mel 太多，根因却是换算常数。这一关想练的是：报错的位置往往不是出错的位置。

**依次修四处**：

1. `hz_to_mel` 改用 `math.log10`，与 docstring 和 `mel_to_hz` 一致。把 `mel_to_hz` 改成 `math.exp` 也能让滤波器组恢复正常，但 1000 Hz 会变成 2303 mel，下一条断言会拦住。改成 `1127 * ln` 是 HTK 的另一种写法，可它和 `mel_to_hz` 里的 10 的幂并不严格互逆，3000 Hz 往返一次差 0.03 Hz，往返断言也会拦住。
2. 修好第 1 处，报错变成 `mel filter 0 of 40 covers no FFT bins (n_fft=256, sr=16000)`。测试传的是 8 kHz，括号里却是 16000：`log_mel_spectrogram` 调 `mel_filterbank` 时只传了 `fmin` 和 `fmax`，`sr` 用了默认值。按 16 kHz 换算，每个 bin 宽 62.5 Hz，最低的三个边缘落在 0、1、1 号 bin 上，第 0 个滤波器没有宽度。把 `sr` 传进去就好；参考答案还去掉了这个默认值，以后再漏传，调用时就会报 TypeError。课里的“采样率不一致”通常发生在上游重采样，这里是同一个坑出现在一次函数调用里。
3. `whisper_log_mel` 先把所有帧取 log10，求出整段 clip 的最大值，再统一截到“最大值 − 8”，最后做 (x + 4) / 4。原来的写法在每一帧里各求一次最大值，安静的帧就保留了比整段最响处低 80 dB 以上的细节。测试的两帧里，第一帧是安静的，所以只看第一帧求最大值也会被拦住。
4. `apply_filterbank` 只遍历每个滤波器的非零区间。80 个滤波器只覆盖 0 到 8 kHz，也就是 1025 个 bin 里的前 341 个，每个 bin 最多落在两个滤波器里，非零权重一共 590 个；展开成稠密矩阵却有 82,000 个权重。稠密写法 600 帧约 1.3 秒，只遍历非零区间约 9 毫秒。课里 `apply_filterbank` 的 `if w:` 只跳过了乘法，循环仍然走完全部 1025 个 bin，约 0.7 秒，同样过不了。

**护栏**：

- 第 2 处最省事的“修法”是把默认值改成 8000，8 kHz 的用例就过了。测试另外用 16 kHz、`n_fft=512`、`fmax=4000` 算同一个 1 kHz 正弦波：bin 宽同样是 31.25 Hz，滤波器组和 8 kHz 时一模一样，必须落在同一个频带。默认值写死成 8000 时，这段音频会落到第 11 个频带。
- 第 4 处的稀疏写法要和稠密矩阵的结果一致（容差 1e-12），区间起点错开一个 bin 会被拦住。
- 删掉“covers no FFT bins”这个检查也能让第一个错误消失，但滤波器组仍然是错的，1 kHz 的正弦波会落到编号 7 的频带。

功率谱、`power_to_db` 和 `log_mel` 在 starter 里就是对的。测试仍然检查它们：音量翻倍时 log-mel 加 log 4，说明 mel 用的是功率 |X|² 而不是幅度；功率差 100 倍是 20 dB；数字静音落在 log(floor)，而 1e-9 这种高于 floor 的能量取的是它自己的对数，不能写成 `log(v + floor)`。

## Part 2 特征缓存

参考实现一条记录一个文件。文件名是 `sha256(clip_id + "\0" + config_id)`，内容是 12 字节的头（魔数、帧数、每帧维数）加上小端 float64。写入时先写临时文件再 `os.replace`，不会留下写了一半的文件；读出时核对头里的形状和数据长度，对不上就报错。`clip_hash` 用 sha256 依次哈希采样率（8 字节整数）和每个样本的 8 字节 float64。

容易漏的几点：

- **精度**：特征按 float64 原样存。float32 会把 0.1 + 0.2 改掉，把 5e-324 变成 0，把 -1e300 变成 -inf。JSON 也能存准，Python 的 float 经过 `json.dumps` 和 `json.loads` 能原样还原。
- **宽度是元数据**：短于一帧的 clip 有 0 行特征。只存行的话，读回来就不知道每行应该有 40 个值，所以形状要单独存。
- **键要包含配置**：同一个 clip 在 80 mel 和 128 mel 下是两条记录。键里没有配置，旧特征就会交给新模型，这正是课里说的 mel 数不一致，而且不报错。
- **采样率是 clip 的一部分**：同一串样本在 8 kHz 和 16 kHz 下时长和音高都不同。哈希的精度也要是完整的 float64：测试里两段音频只差最低一位（`math.nextafter`），`f"{x:.16g}"` 都分不出来，要 17 位有效数字，或者直接哈希 8 字节的原始值。
- **逐行对 n_feats 校验，先校验再写**：测试的第一个坏矩阵每行 2 个值，行与行一致，只是不等于 3；第二个三行分别有 3、2、4 个值，第一行是对的，总数正好 9 = 3 × 3。只查第一行、只查行与行是否一致、只查总数，都会放过其中一个。先写后校验的话，下次会读出一个完全合法的 3 × 3 矩阵。

## Part 3 delta 和 CMVN

`deltas` 对每一帧 t、每个 n = 1..width，取 `frames[min(t + n, last)]` 和 `frames[max(t - n, 0)]`，按 n 加权求差，再除以 `2·Σn²`。下标先夹到 `[0, last]`，就是边缘复制。

- 直线 `c[t] = t` 的 delta 在内部是 1，在两端是 0.5 和 0.8：边缘帧被复制，斜率被压平了一部分。
- 负下标是 Python 里最容易漏的坑：`frames[t - n]` 在 t = 0 时不报错，取到的是最后几帧。补零则会在边缘造出一个假的跳变。
- `add_deltas` 每一阶都对上一阶求 delta，宽度依次取 `windows`，默认 `(2, 2)` 对应 HTK 的 DELTAWINDOW 和 ACCWINDOW。阶数就是 `windows` 的长度，`windows=[]` 只剩静态特征，Part 5 的配置里还会出现只有一阶的 `[3]`。抛物线 t² 的 delta-delta 在内部是 2。

`cmvn` 先按列转置，每一维求均值和总体标准差，再除以 `max(std, floor)`，返回新的行。按帧归一化、用样本标准差、常数维没有 floor、原地改输入，测试都会拦住。原地修改的后果要到 Part 4 才显出来：那里会拿同一批帧的不同前缀反复调用 `cmvn()`，所以这一关先确认输入没有被改动。最后一段把 Part 1 的 40 维 log-mel 接上 delta 和 delta-delta，得到 120 维，CMVN 之后每一维均值 0、方差 1。

## Part 4 在线 CMVN

```python
for frame in frames:
    self._update(frame)          # Welford：count、mean、M2
    self.held.append(frame)
    if self.count >= self.warmup:
        out += [self._normalize(f) for f in self.held]
        self.held = []
```

- 每一帧先计入统计量，再决定是否放出，所以帧 t 用的是 0..t 的统计量；预热期间的帧一起等到第 warmup 帧，用的是前 warmup 帧的统计量。合起来就是 `cmvn(frames[:max(t + 1, warmup)])[t]`，最后一帧与离线的按句 CMVN 一致。
- 统计量逐帧更新，与切块方式无关，三种切法的输出逐位相同。
- flush 放出还扣着的帧。流比 warmup 短时，结果就是对这几帧做离线 CMVN。
- Welford 每帧 O(dim)，不用保存历史帧。每来一帧就对目前所有帧重算 `cmvn()`，结果相同，但是 O(T²)，1000 帧时慢两百多倍。

这一关对应课里的 normalization drift：同一段音频，按句 CMVN 和在线 CMVN 给出的前几百帧并不相同。训练时用哪一种，上线就要用哪一种。

## Part 5 配置合并和指纹

`merge` 先深拷贝 base，再把每个 override 递归合并进去：两边都是 dict 时往下走；其他情况（数字、字符串、None、list）用 override 的深拷贝整体替换；遇到下层没有的键，报 KeyError，消息里带完整路径，例如 `unknown config key 'mel.n_mel'`。顶层的 `sample_rte` 也一样要报。

深拷贝要从 base 开始。另一种常见写法是每一层 `out = dict(below)` 再递归：被覆盖的子树是新建的，看起来没问题，但没被覆盖的子树（比如 `log`）仍然是 `DEFAULTS` 里的那个对象，改结果就会改到 `DEFAULTS`。None 是普通值，`fmax: None` 的意思是 Nyquist，不能当成“没设置”跳过。

`fingerprint` 是 `json.dumps(config, sort_keys=True, separators=(",", ":"))` 的 sha256：

- `sort_keys` 在每一层都排序，所以键顺序不影响结果；list 保持原来的顺序。
- json 用 `repr` 写浮点数，1e-10 和 1e-12 不会被写成同一个字符串。
- sha256 在每个进程里都一样。内置 `hash()` 对字符串加了随机盐，换一个进程就变；拿它做磁盘缓存的键，重启后一条也命中不了。

最后一段把 Part 2 串进来：`FeatureService` 用 `clip_hash` 和 `fingerprint` 组成缓存键，同一个配置换个键顺序会命中缓存，n_mels 改了就重新计算。课里的技能文件要求特征管线和训练配置完全一致，这个指纹就是检查“一致”的依据。

## 这套题证明了什么，没证明什么

通过了说明你能在纯 Python 的特征代码里顺着调用链调试，查出 mel 换算和采样率传递的错误，照 Whisper 的做法缩放 log-mel，利用滤波器组的稀疏性，设计能精确存取的特征缓存，实现 delta、CMVN 和它的流式版本，以及处理分层的嵌套配置。它不涉及 FFT、Slaney 式归一化和按连续频率计算的三角滤波器，也不涉及与 librosa、torchaudio、Whisper 前端的逐位对齐、SpecAugment 和真实音频解码。课里的练习 2 和练习 3（扫 n_mels 和 frame_len、在 AudioMNIST 上比较三种特征）需要另外动手跑。
