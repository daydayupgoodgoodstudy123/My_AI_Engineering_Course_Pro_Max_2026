# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 03 节 音频分类——从 MFCC 上的 k-NN 到 AST 和 BEATs ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无命令行参数，约 6 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`collections.Counter`）

---

## 1. 这份代码在考察什么

这份脚本实现讲义里阶梯的**第一级**——"k-NN on MFCCs"基线，完整走一遍"造数据 → 提特征 → 池化成定长向量 → 最近邻分类 → 混淆矩阵"：

1. **特征复用**：上一节的 STFT → mel → log → DCT 管线被原样搬来，组合成 `featurize`。
2. **变长 → 定长**：音频长度各不相同，而 k-NN 需要定长向量；`summarize` 用"每维的均值 + 方差"把 MFCC 帧序列压成 26 维。
3. **最简单的分类器**：余弦相似度 + top-K 多数投票，没有任何训练参数，"训练"就是把样本存进 bank。
4. **评估习惯**：不仅打印准确率，还打印混淆矩阵（行 = 真实标签，列 = 预测标签），这是讲义强调的 per-class 视角的雏形。
5. **基线意识**：在上 BEATs / AST 之前，先用最便宜的方法确定"性能下限"。

> 一句话：**任何音频分类项目的第一天，都应该先跑出这样一个几分钟就能搭好的基线**，再决定值不值得上预训练大模型。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sine` / `add_noise` | 函数 | 合成纯音并叠加高斯噪声 | 合成数据集 |
| `hann` / `dft_mag` / `frame_signal` / `stft_mag` | 函数 | 分帧、加窗、STFT 幅度 | 第 02 节的 STFT |
| `hz_to_mel` / `mel_to_hz` / `mel_filterbank` / `apply_filterbank` | 函数 | mel 滤波器组投影 | 第 02 节的 mel 频谱 |
| `log_transform` / `dct_ii` | 函数 | 取对数、DCT 得 MFCC | 第 02 节的 MFCC |
| `featurize` | 函数 | 把上面串起来：波形 → MFCC 帧序列 | 特征提取管线 |
| `summarize` | 函数 | 时间轴 mean + var 池化 → 26 维 | 定长 embedding |
| `cosine` | 函数 | 余弦相似度（防零向量） | 相似度度量 |
| `knn` | 函数 | top-K 多数投票 | k-NN 分类 |
| `main()` | 演示入口 | 建 4 类数据集、分类、打印混淆矩阵 | 评估 |

数据流：`sine → add_noise → featurize（stft_mag → apply_filterbank → log_transform → dct_ii）→ summarize → knn（cosine）→ confusion`。

---

## 3. 逐段精讲

### 3.1 合成数据：纯音 + 高斯噪声

```python
def sine(freq_hz, sr, seconds, amp=0.5, phase=0.0):
    n = int(sr * seconds)
    return [amp * math.sin(2.0 * math.pi * freq_hz * i / sr + phase) for i in range(n)]


def add_noise(signal, sigma=0.05):
    return [s + random.gauss(0, sigma) for s in signal]
```

- 每个类别是一个固定频率的纯音，类内差异**只来自噪声**（`phase` 参数始终是默认值 0）。
- `random.gauss(0, sigma)` 产生均值 0、标准差 0.05 的高斯白噪声，信噪比约 `0.5²/2 ÷ 0.05² ≈ 50`（17 dB），相当干净。
- ⚠️ 这是一个"玩具"数据集：四个类别频率相差一个八度（200/400/800/1600 Hz），在 mel 轴上相距很远，几乎不可能分错。真实音频分类的难点（类内多样性、领域偏移、标签噪声）这里都不存在。

### 3.2 特征管线：沿用上一节

```python
def frame_signal(sig, frame_len, hop):
    n = 1 + max(0, (len(sig) - frame_len) // hop)
    return [sig[i * hop : i * hop + frame_len] for i in range(n)]


def apply_filterbank(spec, fb):
    out = []
    for frame in spec:
        row = [sum(w * frame[k] for k, w in enumerate(f) if w) for f in fb]
        out.append(row)
    return out
```

大部分函数与第 02 节相同（详见 [第 02 节代码讲解](../../02-spectrograms-mel-features/code/main.讲解.md)），只有两处小改动：

- `frame_signal` 用 `1 + max(0, ...)` 代替了上一节的"长度不足返回空列表"：短音频会返回 **1 帧**而不是 0 帧。⚠️ 但这一帧的长度小于 `frame_len`，随后 `stft_mag` 里的 `f[j] for j in range(frame_len)` 会 `IndexError`。本例音频固定 0.25 秒，不会触发。正确做法是先把短音频补边到至少一帧。
- `apply_filterbank` 把内层循环压成了一个带 `if` 过滤的生成器表达式：`sum(w * frame[k] for k, w in enumerate(f) if w)`，含义完全相同——跳过权重为 0 的 bin，对剩余 bin 做加权和。本质仍是 `spec @ fbᵀ`。

### 3.3 `featurize`：一条完整的 MFCC 管线

```python
def featurize(signal, sr, n_mfcc=13, n_mels=40, frame_len=256, hop=128):
    mag = stft_mag(signal, frame_len, hop)
    fb = mel_filterbank(n_mels, frame_len, sr)
    mels = apply_filterbank(mag, fb)
    lm = log_transform(mels)
    return [dct_ii(f, n_mfcc) for f in lm]
```

- 输入：长度 2000 的波形（8 kHz × 0.25 s）。输出：14 帧 × 13 维 MFCC（`1 + (2000 − 256) // 128 = 14`）。
- 参数是缩小版：讲义 Step 1 用的是 `frame_len=400, hop=160`（16 kHz 下的 25/10 ms），这里用 8 kHz 下的 256/128（32/16 ms），让纯 Python 的 `O(N²)` DFT 能在几秒内处理完 68 段音频。
- ⚠️ **每次调用都重新构造 filterbank**：68 段音频就构造了 68 次一模一样的矩阵。生产代码会把 filterbank 预先算好缓存起来（`torchaudio.transforms.MelSpectrogram` 在 `__init__` 里构造一次）。这里为了让 `featurize` 成为"自包含"的纯函数而牺牲了效率。

### 3.4 `summarize`：变长序列 → 定长向量

```python
def summarize(frames):
    n = len(frames[0])
    mean = [sum(f[i] for f in frames) / len(frames) for i in range(n)]
    var = [sum((f[i] - mean[i]) ** 2 for f in frames) / len(frames) for i in range(n)]
    return mean + var
```

- 对每一维 MFCC，在时间轴上求均值（这段声音"平均"的频谱包络）和方差（随时间的波动程度），拼起来得到 `13 + 13 = 26` 维。
- `mean + var` 是**列表拼接**，不是逐元素相加——初学者极易误读。
- 讲义："Simple but strong"——这种"统计池化"思想后来演化成说话人识别里 x-vector / ECAPA 的 statistics pooling 层（第 06 节）。
- ⚠️ 刻意的简化：
  - 池化对帧的顺序不敏感，`summarize(frames) == summarize(frames[::-1])`，时间结构全部丢失。
  - 方差除以 `len(frames)`（总体方差），而非 `n − 1`。
  - 没有做特征标准化：均值和方差两部分的数值尺度不同，余弦相似度会更偏向数值大的维度。

### 3.5 `cosine` 与 `knn`

```python
def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-12
    nb = math.sqrt(sum(x * x for x in b)) or 1e-12
    return dot / (na * nb)


def knn(q, bank, labels, k=3):
    idx = sorted(range(len(bank)), key=lambda i: -cosine(q, bank[i]))[:k]
    votes = Counter(labels[i] for i in idx)
    return votes.most_common(1)[0][0]
```

- `x or 1e-12`：如果模长是 `0.0`（假值），就用 `1e-12` 代替，防止零向量除零；此时点积也为 0，余弦返回 0。
- `sorted(..., key=lambda i: -cosine(...))`：按相似度**降序**排列下标（取负号实现降序），切片取前 `k` 个——这是"top-K 最近邻"。
- `Counter(...).most_common(1)[0][0]`：`most_common(1)` 返回 `[(标签, 票数)]`，`[0][0]` 取出标签。
- **平票行为**：`Counter` 按首次出现顺序记录，`most_common` 在票数相同时保持插入顺序；因为 `idx` 已按相似度排序，所以 1:1:1 平票时返回**最近的那个邻居**的标签——结果是确定的。
- 讲义 Step 3 默认 `k=5`，代码用 `k=3`：每类只有 12 个训练样本，`k=3` 足够。
- ⚠️ 每次查询都对整个 bank 排序，`O(n log n)`；数据量大时应先归一化向量，再用 ANN 索引。

### 3.6 `main()`：建数据集、分类、混淆矩阵

```python
    random.seed(42)
    sr = 8000
    duration = 0.25
    classes = {"low": 200, "mid_low": 400, "mid_high": 800, "high": 1600}
    per_class_train = 12
    per_class_test = 5
```

- `random.seed(42)` 固定噪声序列，结果可复现。
- 4 类 × (12 训练 + 5 测试) = 48 + 20 = 68 段音频，测试集与训练集**分别**生成（不同的噪声实现），没有数据泄漏。
- 字典 `classes` 在 Python 3.7+ 保持插入顺序，所以混淆矩阵的行列顺序就是 `low, mid_low, mid_high, high`。

```python
    confusion = {c: Counter() for c in classes}
    for feat, gold in zip(X_test, y_test):
        pred = knn(feat, X_train, y_train, k=3)
        confusion[gold][pred] += 1
```

- 混淆矩阵用"字典套 `Counter`"实现：`confusion[真实][预测]`。`Counter` 对不存在的键返回 0，所以不用初始化每个格子。
- 对角线 = 预测正确，非对角线 = 哪两类容易混淆。在真实任务里，从混淆矩阵能直接看出"钻孔声总被认成手提钻"之类的系统性错误，比单一准确率有用得多。

```python
    header = "  " + " ".join(f"{c[:8]:>10}" for c in classes)
    print(header)
    for gold in classes:
        row = f"  {gold[:8]:>8}"
        for pred in classes:
            row += f" {confusion[gold][pred]:>10}"
        print(row)
```

- ⚠️ 排版小 bug：表头没有给行标签那一列留出 8 个字符的位置，导致表头整体比数据列**左移约 9 个字符**（看运行结果，`low` 表头落在了行标签上方）。修复：`header = "  " + " " * 8 + "".join(f" {c[:8]:>10}" for c in classes)`。
- `c[:8]` 截断过长的类名，`:>10` 右对齐占 10 位。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 合成纯音数据集 | 无需下载、可复现、几秒跑完 | 太简单，100% 准确率不说明问题；真实基线用 ESC-50 / Speech Commands |
| 复制上一节的特征代码 | 单文件自包含 | 代码重复；生产用 `torchaudio` / `librosa`，并缓存 filterbank |
| mean + var 统计池化 | 最简单的变长 → 定长方案 | 丢失时序；CNN/Transformer 或注意力池化可保留 |
| 不做特征标准化 | 保持代码简短 | 维度尺度差异影响余弦；生产中常对训练集统计量做 z-score（需实验验证） |
| 余弦 + 多数投票 k-NN | 无训练、无超参（除 k） | 查询 `O(n)`、对特征尺度敏感；大规模用 ANN 索引或换成线性分类器 |
| 平票取最近邻 | 依赖 `Counter` 的插入顺序，确定性 | 隐式规则不直观；可改为距离加权投票 |
| 字典套 `Counter` 的混淆矩阵 | 稀疏、无需初始化 | 生产用 `sklearn.metrics.confusion_matrix` + `classification_report` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `random.seed` / `random.gauss` | `random.seed(42)`、`random.gauss(0, sigma)` | 固定随机种子；生成高斯随机数 |
| 列表拼接 `+` | `return mean + var` | 两个列表首尾相连，不是逐元素相加 |
| 带条件的生成器表达式 | `sum(w * frame[k] for k, w in enumerate(f) if w)` | `if` 过滤掉权重为 0 的项 |
| `x or default` | `math.sqrt(...) or 1e-12` | `x` 为假值（0、空）时取 `default`，常用来兜底 |
| `sorted` + `key` + `lambda` + 切片 | `sorted(range(len(bank)), key=lambda i: -cosine(q, bank[i]))[:k]` | 按相似度降序排列下标，取前 k |
| `collections.Counter` | `Counter(labels[i] for i in idx)`、`votes.most_common(1)[0][0]` | 计数器；`most_common(n)` 返回频次最高的 n 个 `(元素, 次数)` |
| 字典推导式 | `{c: Counter() for c in classes}` | 一行构造"每个类别一个计数器" |
| 字典遍历 | `for label, freq in classes.items()`、`for gold in classes` | `.items()` 同时拿键值；直接遍历字典得到键 |
| `_` 占位变量 | `for _ in range(per_class_train)` | 不需要循环变量时用 `_` |
| `zip` 并行遍历 | `for feat, gold in zip(X_test, y_test)` | 特征与标签一一配对 |
| 多变量赋值 | `X_train, y_train = [], []` | 同时初始化两个列表 |
| `+=` 计数 | `confusion[gold][pred] += 1` | `Counter` 中不存在的键默认为 0 |
| f-string 对齐与截断 | `f"{c[:8]:>10}"`、`f"{acc:.3f}"` | `:>10` 右对齐宽 10；`:.3f` 三位小数 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 6 秒）：

```text
=== Build synthetic 4-class dataset (pure tones + noise) ===
  train: 48  test: 20
  feature dim: 26  (mean+var of 13 MFCC)

=== k-NN classify (k=3) ===
  test accuracy: 1.000 (20/20)

=== Confusion matrix (rows=gold, cols=predicted) ===
         low    mid_low   mid_high       high
       low          5          0          0          0
   mid_low          0          5          0          0
  mid_high          0          0          5          0
      high          0          0          0          5

takeaways:
  - k-NN on mean+var MFCC pool is a surprisingly strong baseline
  - real pipelines use BEATs / AST fine-tune + SpecAugment + mixup
```

逐段解读：

- **数据集**：4 类 × 12 = 48 条训练、4 类 × 5 = 20 条测试；特征 26 维。
- **准确率 1.000**：四个频率相隔一个八度，信噪比高，任何合理的特征都能完美分开。这个结果**不能**说明 k-NN 在真实数据上也这么好——它只证明管线是通的。
- **混淆矩阵**：完全对角。注意表头的排版错位（见 3.6）：数字列是对的，只是表头整体左移了。
- **耗时约 6 秒**：几乎全部花在纯 Python 的 `O(N²)` DFT 上（68 段 × 14 帧 × 每帧约 3.3 万次乘加，再乘以 cos/sin 调用）。换成 `numpy.fft.rfft` 会快上百倍。
- **想让它"难"一点**：把类别改成 400/430/460/490 Hz（相差 30 Hz，约一个 bin 宽）后实测：`sigma=0.05` 时仍是 100%，`sigma=0.5` 时降到 60%（20 条测试样本，波动较大）——噪声一大，相邻频率的 mel 能量分布就分不清了。

---

## 7. 动手改一改

1. **修排版**：按 3.6 的方法修正混淆矩阵表头，确认列对齐。
2. **加难度**：把 `classes` 改成相差 30 Hz 的四个频率，并把 `add_noise` 的 `sigma` 调到 0.3、0.5，观察准确率和混淆矩阵的变化——哪些类最容易混淆？为什么是相邻的频率？
3. **讲义练习 2**：把 `summarize` 扩展为 mean、var、skew、kurtosis 四阶矩（注意方差为 0 时偏度/峰度的除零问题），对比是否优于 mean + var。
4. **缓存 filterbank**：把 `mel_filterbank` 提到 `featurize` 之外只算一次，用 `time.perf_counter()` 测量节省了多少时间；再把 `dft_mag` 换成 `numpy.fft.rfft`，对比速度。
5. **时序信息实验**：构造上行扫频（200→1600 Hz）和下行扫频（1600→200 Hz）两个类别（注意使用正确的 chirp 相位公式 `f0·t + ½·k·t²`），看 mean + var 池化 + k-NN 能否区分；再加入"前半段均值 + 后半段均值"这样的粗粒度时序特征，看是否改善。
6. **换评估指标**：用 `sklearn.metrics.classification_report` 输出 per-class precision / recall / F1（环境中已安装 scikit-learn）。

---

## 8. 常见坑

- **把合成数据的 100% 当真**：玩具数据集只能验证代码正确性，不能代表模型能力；基线一定要在真实数据集上评估。
- **`mean + var` 误读为相加**：Python 列表的 `+` 是拼接，结果是 26 维而不是 13 维。
- **短音频崩溃**：`frame_signal` 对长度不足一帧的音频返回一个短帧，`stft_mag` 会越界；上游要补边或过滤。
- **特征尺度不一致**：不同维度数值范围不同时，余弦/欧氏距离会被大数值维度主导；是否标准化、如何标准化要用验证集实验决定。
- **平票的隐式规则**：k 是类别数的约数或类别很多时容易平票，结果依赖 `Counter` 的插入顺序；最好显式处理。
- **评估集泄漏**：真实数据中，同一段原始录音切出的片段不能同时出现在训练集和测试集，否则准确率虚高。本例的训练/测试是独立生成的，不存在这个问题。
