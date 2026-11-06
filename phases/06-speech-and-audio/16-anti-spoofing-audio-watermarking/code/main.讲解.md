# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 16 节 语音反欺骗和音频水印 — ASVspoof 5、AudioSeal、WaveVerify ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无命令行参数，纯 Python DFT 较慢，约 15 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`），不需要 audioseal / torch

---

## 1. 这份代码在考察什么

真实的反欺骗检测器（AASIST、RawNet2）和水印（AudioSeal）都是神经网络。这份脚本用几个数值小把戏模拟它们的**接口和评估流程**，让你把"防御管线"的形状看清楚：

1. **合成"真/假"语音**：真实语音 = 基频 + 谐波 + 宽带噪声；伪造语音 = 基频 + 一个 6 kHz 的"不自然"高频分量 + 极低噪声。
2. **频谱特征检测器**：手写加窗分帧 DFT，计算高频能量占比作为"伪造分数"——对应讲义 Step 1"合成语音常有异常的高频能量"。
3. **EER 评估**：扫描阈值，找 FAR ≈ FRR 的点——ASVspoof 的标准指标。
4. **水印嵌入/提取**：把 16 bit payload 藏进波形再读出来，计算比特准确率（Bit Recovery Accuracy）。
5. **对照基准**：打印讲义中 AASIST、AudioSeal、WavMark 以及变调攻击的数字。

> ⚠️ 先说结论：这份脚本的 **Step 3（EER）和 Step 4（水印）各有一个实质性 bug**，打印出的 `EER ≈ 100%` 和 `bit accuracy: 31.2%` 都不是"玩具方法效果差"，而是代码写错了。本讲解会把它们当作最好的学习材料：**评估代码本身也需要被测试**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `synth_real_speech(n_samples, seed)` | 函数 | 220 Hz + 440 Hz 正弦 + 0.02σ 噪声 | 真实（bona fide）语音 |
| `synth_fake_speech(n_samples, seed)` | 函数 | 220 Hz + 6000 Hz 正弦 + 0.002σ 噪声 | 伪造（spoof）语音 |
| `magnitude_spectrum(audio, n_fft)` | 函数 | Hann 窗分帧 + 朴素 DFT，累加各帧幅度谱 | 频谱特征 |
| `toy_detector_score(audio)` | 函数 | 4–8 kHz 能量占总能量的比例，越高越像伪造 | 反欺骗检测器（CM） |
| `toy_watermark_embed(audio, payload_bits)` | 函数 | 在 16 个等距位置加 ±0.0005 | 水印生成器 |
| `toy_watermark_detect(audio, n_bits)` | 函数 | 读取那 16 个位置样本的正负号 | 水印检测器 |
| `main()` | 演示入口 | Step 1–5：合成 → 打分 → EER → 水印 → 基准表 | — |

数据流：`synth_* → toy_detector_score（内部调 magnitude_spectrum）→ 阈值扫描算 EER`；另一条线 `synth_real_speech → toy_watermark_embed → toy_watermark_detect → 比特准确率`。

---

## 3. 逐段精讲

### 3.1 合成"真/假"语音

```python
def synth_real_speech(n_samples=16000, seed=0):
    rng = random.Random(seed)
    out = []
    for i in range(n_samples):
        base = 0.2 * math.sin(2 * math.pi * 220 * i / 16000)
        harmonic = 0.08 * math.sin(2 * math.pi * 440 * i / 16000)
        noise = 0.02 * rng.gauss(0, 1.0)
        out.append(base + harmonic + noise)
    return out


def synth_fake_speech(n_samples=16000, seed=0):
    rng = random.Random(seed)
    out = []
    for i in range(n_samples):
        base = 0.2 * math.sin(2 * math.pi * 220 * i / 16000)
        ultra_flat = 0.05 * math.sin(2 * math.pi * 6000 * i / 16000)
        out.append(base + ultra_flat + 0.002 * rng.gauss(0, 1.0))
    return out
```

- 都是 16 kHz、1 秒（16000 个样本）。真实语音有 220 Hz 基频 + 440 Hz 二次谐波（真人发声有谐波结构）+ 较强的宽带噪声（真实录音环境）。
- 伪造语音缺了谐波，却多了一个 6000 Hz 的纯音，噪声也低了 10 倍——用来模拟讲义说的"合成语音常有异常平坦/突出的高频能量"以及"过于干净"。
- 各段用不同种子（真实 0–19，伪造 100–119），噪声各不相同，但信号结构完全一样，所以两类分数会非常集中（见第 6 节）。
- ⚠️ 极度简化：真实的伪造检测线索远比"一个 6 kHz 纯音"微妙（相位不连续、声码器伪影、韵律异常等），这也是为什么生产中必须用 AASIST 这类学习型模型。

### 3.2 加窗分帧幅度谱（朴素 DFT）

```python
def magnitude_spectrum(audio, n_fft=256):
    result = [0.0] * (n_fft // 2 + 1)
    window = [0.5 - 0.5 * math.cos(2 * math.pi * i / (n_fft - 1)) for i in range(n_fft)]
    chunks = [audio[i : i + n_fft] for i in range(0, len(audio) - n_fft, n_fft)]
    for chunk in chunks:
        for k in range(n_fft // 2 + 1):
            re, im = 0.0, 0.0
            for j in range(n_fft):
                angle = -2 * math.pi * k * j / n_fft
                re += window[j] * chunk[j] * math.cos(angle)
                im += window[j] * chunk[j] * math.sin(angle)
            result[k] += math.sqrt(re * re + im * im)
    return result
```

- **Hann 窗** `0.5 − 0.5·cos(2πi/(N−1))`：让每帧两端平滑衰减到 0，减少频谱泄漏（第 02 节的内容）。
- **分帧**：每 256 个样本一帧、不重叠（hop = n_fft）。16 kHz 下每帧 16 ms，频率分辨率 `16000 / 256 = 62.5 Hz`。
- **只算 `n_fft // 2 + 1 = 129` 个频点**：实数信号的频谱共轭对称，后一半是冗余的；129 个频点覆盖 0–8000 Hz（奈奎斯特频率）。
- **DFT 定义**：`X[k] = Σⱼ w[j]·x[j]·e^(−2πi·kj/N)`，代码把复指数拆成 `cos`（实部）和 `sin`（虚部）分别累加，最后取模长。
- **各帧幅度相加**：得到整段音频的"平均频谱形状"（未除以帧数，但后面只用比例，所以无所谓）。
- ⚠️ **off-by-one**：`range(0, len(audio) - n_fft, n_fft)` 的终点是开区间，16000 个样本只切出 62 帧，最后一个完整帧（起点 15744）被漏掉。应写 `len(audio) - n_fft + 1`。
- ⚠️ **慢**：每帧 129 × 256 次内层循环、每次两次三角函数调用；40 段音频共约 8200 万次迭代，这就是脚本要跑约 15 秒的原因。生产中用 FFT（`numpy.fft.rfft`），每帧从 `O(N²)` 降到 `O(N log N)`。

### 3.3 玩具检测器：高频能量占比

```python
def toy_detector_score(audio):
    spec = magnitude_spectrum(audio)
    total = sum(spec) or 1e-9
    high_band = sum(spec[len(spec) // 2 :]) / total
    return high_band
```

- `spec[64:]` 对应频点 64–128，即 **4000–8000 Hz**；返回这一段幅度占全部幅度的比例。
- `sum(spec) or 1e-9`：`or` 的短路求值——如果总和为 0（假值），就用 1e-9，避免除零。
- **分数方向**：伪造语音有 6 kHz 纯音，所以**分数越高越像伪造**。记住这一点，3.4 的 bug 就出在这里。
- 和讲义 Step 1 的 `spectral_rolloff` 思路一致（都是"高频能量是否异常"），只是特征换成了更简单的高频占比。

### 3.4 EER 扫描——以及分数方向 bug

```python
    candidates = sorted(set(real_scores + fake_scores))
    best = (1.0, 0.0, 0.0, 0.0)
    for t in candidates:
        far = sum(1 for s in fake_scores if s >= t) / len(fake_scores)
        frr = sum(1 for s in real_scores if s < t) / len(real_scores)
        if abs(far - frr) < best[0]:
            best = (abs(far - frr), t, far, frr)
    gap, t, far, frr = best
    print(f"  EER ≈ {(far + frr) * 50:.2f}%  at threshold {t:.4f}")
```

做法本身是标准的：把所有出现过的分数当作候选阈值，对每个阈值算 FAR 与 FRR，取二者最接近的点，EER ≈ `(FAR + FRR) / 2`（代码里 `× 50` 是"除以 2 再乘 100 变成百分数"）。`sorted(set(...))` 去重并排序；`sum(1 for ... if ...)` 是"数满足条件的元素个数"的惯用写法。

**bug 在于 FAR/FRR 的定义假设"分数越高越像真人"**（讲义 Step 3 的 `eer()` 也是这么写的，对 bona fide 分数是对的）：

| 代码里的名字 | 实际计算的是 | 在"分数越高越假"时的真实含义 |
|------------|------------|--------------------------|
| `far = P(fake ≥ t)` | 伪造分数 ≥ 阈值的比例 | 伪造被**正确拦截**的比例（= 1 − 真正的 FAR） |
| `frr = P(real < t)` | 真实分数 < 阈值的比例 | 真人被**正确放行**的比例（= 1 − 真正的 FRR） |

本例中真实分数在 0.190–0.198、伪造在 0.210–0.211，**完全分开**。在 t = 0.2101 处，`far = 1.0`、`frr = 1.0`，差为 0，被选为最佳点，于是打印 `EER ≈ 100%`——一个完美的检测器被评成了"全错"。

修复：让 FAR/FRR 与分数方向一致（或把分数取负再用原代码）：

```python
        far = sum(1 for s in fake_scores if s < t) / len(fake_scores)    # 伪造被放过
        frr = sum(1 for s in real_scores if s >= t) / len(real_scores)   # 真人被拦下
```

修复后实测 EER = **0.00%**（阈值 0.2101 处 FAR = FRR = 0）。

> ⚠️ 教训：EER 只是一个"交点"，它对分数方向没有任何自检能力。写评估代码时，先用一个人造的完美分类器（EER 应为 0）和一个随机分类器（EER 应接近 50%）做单元测试。

### 3.5 玩具水印——以及"检测的是宿主而不是水印"的 bug

```python
def toy_watermark_embed(audio, payload_bits):
    out = list(audio)
    step = max(1, len(audio) // len(payload_bits))
    for i, bit in enumerate(payload_bits):
        idx = i * step
        if idx < len(out):
            out[idx] = out[idx] + (0.0005 if bit else -0.0005)
    return out


def toy_watermark_detect(audio, n_bits=16):
    step = max(1, len(audio) // n_bits)
    out = []
    for i in range(n_bits):
        idx = i * step
        if idx < len(audio):
            out.append(1 if audio[idx] > 0 else 0)
    return out
```

- **嵌入**：16000 个样本、16 bit → 每隔 `step = 1000` 个样本改一个点：比特 1 加 0.0005，比特 0 减 0.0005。`list(audio)` 先复制，不改原始音频。
- **检测**：读同样 16 个位置，样本 > 0 判 1，否则判 0。
- ⚠️ **bug**：检测器读的是**样本的正负号**，而这个正负号几乎完全由原始语音决定——实测这 16 个位置的原始样本绝对值在 0.0025 到 0.23 之间，都比 ±0.0005 的扰动大，水印一个符号都翻转不了。把**没加水印**的原始音频送进 `toy_watermark_detect`，得到的结果与加了水印的**一模一样**。所谓 31.2% 的比特准确率，只是 16 位里有 5 位碰巧与宿主信号的符号吻合。
- 要做到可检出，有两种方向（测验 Q10 有完整代码）：
  1. **非盲检测**：用 `watermarked[idx] − clean[idx]` 的符号判比特，100% 恢复，但检测时需要原始音频；
  2. **盲检测（扩频）**：每个比特铺满一整段，乘上只有收发双方知道的 ±1 伪随机序列，检测时做相关。实测强度 0.01 时 20 段音频全部 100% 恢复，强度 0.0005（本代码的强度）时只有约 52%。
- 这正好说明了真实水印的核心权衡：**强度 / 可检出性 vs 不可感知性**，以及为什么 AudioSeal 要把生成器和检测器联合训练、在压缩/EQ/加噪等增强下学习。

### 3.6 Step 5：基准对照表与 takeaways

```python
    rows = [
        ("AASIST (ASVspoof 2019 LA)",    "0.42% EER",  "detection SOTA"),
        ("NeXt-TDNN + WavLM (2025)",     "0.42% EER",  "detection SOTA"),
        ("Robust method on ASVspoof 5",  "7.23% EER",  "real-world"),
        ("AudioSeal (pre-attack)",       "&gt; 99% bit acc","localized watermark"),
        ("WavMark (pre-attack)",         "99.52% bit acc","legacy watermark"),
        ("All (under pitch shift)",       "&lt; 60% bit acc","universal attack"),
    ]
```

- 这些数字来自讲义的"ASVspoof 5""AudioSeal""The gap adversaries exploit"几节。最关键的一行是最后一行：**变调攻击下所有水印的比特准确率都低于 60%**——所以要"检测 + 水印"双保险。
- ⚠️ 讲义原文把 0.42% EER（ASVspoof 2019 LA）归于 "NeXt-TDNN + SSL features"，而这里第一行把同一个数字也标给了 AASIST，两行重复，阅读时以讲义为准。
- ⚠️ `"&gt;"`、`"&lt;"` 是 HTML 实体，Python 会原样打印成 `&gt; 99%`、`&lt; 60%`，本意是 `>` 和 `<`；同时它们让字符串变长，撑破了 `{m:<16}` 的列宽，表格右边框错位（见第 6 节）。Step 4 的 `print` 里也有同样的 `&gt;`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用正弦组合合成"真/假"语音 | 可控、可复现，差异一目了然 | 与真实伪造音频的线索相去甚远；生产用 ASVspoof 等真实数据集 |
| 手写朴素 DFT | 不依赖 NumPy，看清 DFT 定义 | 慢（约 15 秒）；生产用 FFT / 现成 STFT |
| 单一手工特征（高频占比） | 体现"频谱异常"的直觉 | 极易被绕过；生产用 AASIST / RawNet2 / SSL 特征 |
| 用 EER 评估 | 与 ASVspoof 指标一致 | 必须先定义分数方向；本代码方向搞反 |
| 逐点 ±0.0005 的水印 | 演示"嵌入 → 读出 → 算比特准确率"的流程 | 检测读的是宿主符号，水印无效；应用扩频 + 相关或学习型水印 |
| 不模拟攻击 | 代码短 | 真实评估要测压缩、加噪、变速、变调后的比特恢复率 |
| 硬编码基准表 | 把玩具结果与真实数字放在一起对照 | 数字以讲义为准，注意表中的重复与 HTML 实体 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def synth_real_speech(n_samples=16000, seed=0)` | 调用时可省略 |
| 列表乘法初始化 | `result = [0.0] * (n_fft // 2 + 1)` | 元素是不可变的 float，这样写是安全的 |
| 列表切片 | `audio[i : i + n_fft]`、`spec[len(spec) // 2 :]` | 取子列表；省略终点表示"到末尾" |
| 列表推导式 | `[audio[i : i + n_fft] for i in range(0, ..., n_fft)]` | 一行完成分帧 |
| 三层嵌套循环 | 帧 × 频点 × 样本 | DFT 的直接实现；复杂度 `O(帧数 × N²)` |
| 多重赋值 | `re, im = 0.0, 0.0` | 一行初始化两个变量 |
| `or` 提供默认值 | `total = sum(spec) or 1e-9` | 左边为假（0）时取右边 |
| 条件表达式 | `(0.0005 if bit else -0.0005)`、`1 if audio[idx] > 0 else 0` | 二选一的表达式 |
| 计数惯用法 | `sum(1 for s in fake_scores if s >= t)` | 统计满足条件的元素个数 |
| `set` 去重 + `sorted` | `sorted(set(real_scores + fake_scores))` | 列表相加后去重再排序 |
| 元组打包/解包 | `best = (abs(far - frr), t, far, frr)`；`gap, t, far, frr = best` | 用元组携带多个"最佳"值 |
| `zip` 配对比较 | `sum(1 for a, b in zip(payload, recovered) if a == b)` | 逐位比较两个比特列表 |
| f-string 格式符 | `{(far + frr) * 50:.2f}`、`{t:.4f}`、`{bit_acc * 100:.1f}`、`{name:<30}` | 花括号里可写表达式；`.2f` 保留两位小数；`<30` 左对齐 |
| `random.Random(seed)` | `rng = random.Random(seed)` | 独立、可复现的随机数生成器 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（约 14 秒）的输出：

```text
=== Step 1: synthesize real vs fake speech ===
  20 real, 20 fake, 16000 samples each

=== Step 2: score with toy spectral detector ===
  real  mean: 0.194
  fake  mean: 0.211

=== Step 3: sweep threshold → EER ===
  EER ≈ 100.00%  at threshold 0.2101
    (on toy data — real AASIST on ASVspoof 2019 LA: 0.42% EER)

=== Step 4: watermark embed + detect (toy) ===
  payload:   [1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 0]
  recovered: [0, 0, 1, 1, 1, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1]
  bit accuracy: 31.2%   (toy; real AudioSeal: &gt; 99% pre-attack)

=== Step 5: 2026 benchmarks ===
  | method                         | metric           | note              |
  | AASIST (ASVspoof 2019 LA)      | 0.42% EER        | detection SOTA    |
  | NeXt-TDNN + WavLM (2025)       | 0.42% EER        | detection SOTA    |
  | Robust method on ASVspoof 5    | 7.23% EER        | real-world        |
  | AudioSeal (pre-attack)         | &gt; 99% bit acc | localized watermark |
  | WavMark (pre-attack)           | 99.52% bit acc   | legacy watermark  |
  | All (under pitch shift)        | &lt; 60% bit acc | universal attack  |
```

逐段解读：

- **Step 2**：伪造均值 0.211 高于真实均值 0.194，方向符合预期。差距看似很小，但额外实验显示两类**完全不重叠**：真实 0.1900–0.1977，伪造 0.2101–0.2110。因为每类内部只有噪声不同，分数非常集中。
- **Step 3 的 100%**：这是 3.4 所说的分数方向 bug。正确答案是 EER = 0%。注意括号里拿 0.42% 来对比，会让读者误以为"玩具检测器比 AASIST 差得多"，其实恰恰相反——在这份极其简单的合成数据上它是完美的。
- **Step 4 的 31.2%**：这是 3.5 所说的 bug，`recovered` 一行其实就是那 16 个位置原始语音的符号；不加水印也会得到同一行。
- **Step 5**：最后一行"变调攻击下 < 60%"是全节最重要的结论；表中 `&gt;` / `&lt;` 原样打印，并使两行列宽错位。

---

## 7. 动手改一改

1. **修 EER**：按 3.4 修改 FAR/FRR 定义，确认得到 0%；再写一个单元测试：`real = [0.1, 0.2]`、`fake = [0.8, 0.9]` 时 EER 必须为 0；`real` 与 `fake` 来自同一随机分布时 EER 应接近 50%。
2. **让任务变难**：把伪造语音的 6 kHz 幅度从 0.05 降到 0.005，或者给真实语音也加一点高频分量，观察两类分数开始重叠、EER 上升。
3. **修水印**：先实现非盲检测（与原始音频求差），确认 100%；再实现测验 Q10 的扩频盲检，扫描强度 0.0005 / 0.002 / 0.005 / 0.01，画出"强度 vs 比特准确率"。
4. **加攻击**：对扩频水印施加"加噪（SNR 10 dB）""整体取反（乘 −1）""循环平移 500 个样本"三种攻击，看哪种最致命，体会讲义中"同步"和"时域编辑"的难点（WaveVerify 针对的正是反转、变速）。
5. **提速**：预计算 `cos/sin` 表，或在有 NumPy 的环境里改用 `numpy.fft.rfft`，比较运行时间；顺手修掉分帧的 off-by-one。
6. **换特征**：实现讲义 Step 1 的 `spectral_rolloff`，与高频占比特征比较 EER。

---

## 8. 常见坑

- **分数方向不统一**：一个模块输出"真实度"、另一个模块按"伪造度"算 FAR/FRR，结果可以从 0% 翻成 100%，而且不会报错。
- **水印强度远小于宿主信号却用逐点符号检测**：等于在读宿主信号；盲检测必须靠扩频、相关或学习型检测器把宿主"平均掉"。
- **从不在"无水印"音频上测检测器**：负样本测试是发现上面这个 bug 最快的方法——检测器在干净音频上也"检出"了 payload，说明它根本没在看水印。
- **分帧 off-by-one**：`range(0, len - n, n)` 会漏掉最后一个完整帧，应为 `len - n + 1`。
- **HTML 实体混入字符串**：`&gt;`、`&lt;` 会原样打印，还会撑坏格式化宽度。
- **把玩具指标和真实基准直接比较**：合成数据上的 EER 与 ASVspoof 上的 EER 没有可比性，玩具结果只用来验证流程正确。
