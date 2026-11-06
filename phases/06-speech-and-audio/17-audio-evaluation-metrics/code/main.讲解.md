# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 17 节 音频 Evaluation — WER、MOS、UTMOS、MMAU、FAD 和开放排行榜 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`re`），不需要 jiwer / speechbrain / frechet_audio_distance

---

## 1. 这份代码在考察什么

讲义 Build It 部分调用的是现成库（`jiwer`、`speechbrain`、`frechet_audio_distance`）。这份脚本把其中最核心的几个指标**从零手写**一遍，让你知道这些库内部到底算了什么：

1. **WER / CER**：本质是编辑距离（Levenshtein）除以参考长度；以及"先规范化再打分"有多重要。
2. **EER**：说话人验证中扫描阈值、找 FAR = FRR 的点。
3. **SECS**：两个说话人 embedding 的余弦相似度。
4. **FAD 形式的分布距离**：两组 embedding 的"均值差 + 方差差"。
5. **MMAU 式准确率**：多选题的正确率，以及与随机基线（4 选 1 = 25%）的比较。
6. **排行榜速查**：打印讲义中各任务的 2026 年参考数字。

> 一句话：**指标就是几行算术，难的是"算对"**——规范化规则、分数方向、样本量、参考集，每一项没处理好都会让数字失真。这份代码里就能找到好几个现成的例子。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `_edit_distance(a_tokens, b_tokens)` | 函数 | 动态规划求最小编辑次数 | Levenshtein 距离，WER/CER 的核心 |
| `normalize(text)` | 函数 | 小写、删除非字母数字、合并空白 | 文本规范化 |
| `wer(ref, hyp)` | 函数 | 规范化 → 按空格分词 → 编辑距离 / 参考词数 | Word Error Rate |
| `cer(ref, hyp)` | 函数 | 原始字符串 → 字符列表 → 编辑距离 / 参考字符数 | Character Error Rate |
| `eer_from_scores(same, diff)` | 函数 | 阈值扫描，返回 (EER, 阈值) | 说话人验证 EER |
| `cosine(a, b)` | 函数 | 余弦相似度（含零向量保护） | SECS |
| `embedding_fad_like(real, fake)` | 函数 | 对角高斯近似下的 Fréchet 距离（再开根号） | FAD |
| `mmau_accuracy(predictions, golds)` | 函数 | 逐题比较，求正确率 | MMAU / MMAU-Pro |
| `main()` | 演示入口 | 依次演示 6 个部分并打印 | — |

各函数彼此独立；`wer`、`cer` 共用 `_edit_distance`，`wer` 还依赖 `normalize`。`main()` 中所有随机数据都来自同一个 `rng = random.Random(0)`，因此结果完全可复现。

---

## 3. 逐段精讲

### 3.1 编辑距离：WER/CER 的发动机

```python
def _edit_distance(a_tokens, b_tokens):
    dp = [[0] * (len(b_tokens) + 1) for _ in range(len(a_tokens) + 1)]
    for i in range(len(a_tokens) + 1):
        dp[i][0] = i
    for j in range(len(b_tokens) + 1):
        dp[0][j] = j
    for i in range(1, len(a_tokens) + 1):
        for j in range(1, len(b_tokens) + 1):
            cost = 0 if a_tokens[i - 1] == b_tokens[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[len(a_tokens)][len(b_tokens)]
```

- `dp[i][j]` = 把参考的前 i 个 token 变成识别结果的前 j 个 token 所需的最少操作数。
- **边界**：`dp[i][0] = i`（参考有 i 个、识别为空 → 删除 i 次）；`dp[0][j] = j`（参考为空 → 插入 j 次）。
- **转移**的三种选择正好对应 WER 公式里的 D、I、S：

| 转移 | 含义 | WER 中的错误类型 |
|------|------|----------------|
| `dp[i-1][j] + 1` | 参考第 i 个词没被识别出来 | 删除 D |
| `dp[i][j-1] + 1` | 识别结果多出第 j 个词 | 插入 I |
| `dp[i-1][j-1] + cost` | 对齐两个词，不同则替换 | 替换 S（相同则 0 代价） |

- 复杂度 `O(m·n)` 时间、`O(m·n)` 空间。只需要距离时可以只保留两行，把空间降到 `O(n)`。
- 函数名前的下划线 `_edit_distance` 是 Python 的约定：表示"模块内部使用"，不打算给外部直接调用。
- ⚠️ 只返回总编辑次数，不回溯出 S/D/I 各是多少。`jiwer` 等库会回溯对齐路径，分别报告替换、删除、插入数，便于分析错误类型。

### 3.2 规范化 + WER

```python
def normalize(text):
    import re
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def wer(ref, hyp):
    r, h = normalize(ref).split(), normalize(hyp).split()
    return _edit_distance(r, h) / max(1, len(r))
```

- 三步规范化：①全部小写；②正则 `[^a-z0-9\s]` 匹配"不是小写字母、数字、空白"的字符并删除（即去标点）；③把连续空白合并为一个空格并去掉首尾空格。
- `wer` 把规范化后的字符串按空白 `split()` 成词列表，再算编辑距离除以参考词数。`max(1, len(r))` 防止参考为空时除以 0。
- 对应讲义"Normalize before scoring. Lowercase, punctuation-strip, number-expand."——但这里**只做了前两项**：
  - ⚠️ **没有数字展开**：`"5"` 和 `"five"` 被算成一次替换（第 6 节的第 4 对例子 WER = 0.2）。
  - ⚠️ **缩写只删撇号、不展开**：`"what's"` 变成 `"whats"`，与 `"what is"` 对不上，产生 1 个替换 + 1 个插入（WER = 0.5）。
  - ⚠️ 正则只保留 `a-z`，任何非英文字母（中文、带重音的法语字母如 é）都会被**直接删掉**，这个规范化只适用于英文。
- `import re` 写在函数内部：每次调用都会执行 import 语句（模块有缓存，开销很小），但更规范的做法是放到文件顶部。

### 3.3 CER：与 WER 规范化不一致

```python
def cer(ref, hyp):
    return _edit_distance(list(ref), list(hyp)) / max(1, len(ref))
```

- `list("abc")` → `['a', 'b', 'c']`，把字符串拆成字符列表，复用同一个编辑距离函数——空格和标点也算字符。
- ⚠️ **没有调用 `normalize`**：`wer("Play jazz", "play jazz")` 为 0，`cer` 却是 1/9 ≈ 0.111（大小写被算作替换）。同一份报告里的 WER 与 CER 用不同的规范化，会产生令人困惑的结果。修复方法是先 `normalize` 再拆字符（测验 Q10）。
- CER 在中文、粤语等"词边界有歧义"的语言上是主指标（讲义）。中文的规范化规则不同于英文（全半角、繁简、标点），需要另写。

### 3.4 EER：说话人验证的阈值扫描

```python
def eer_from_scores(same, diff):
    thresholds = sorted(set(same + diff))
    best = (1.0, 0.0, 0.0, 0.0)
    for t in thresholds:
        far = sum(1 for s in diff if s >= t) / max(1, len(diff))
        frr = sum(1 for s in same if s < t) / max(1, len(same))
        if abs(far - frr) < best[0]:
            best = (abs(far - frr), t, far, frr)
    gap, t, far, frr = best
    return (far + frr) / 2, t
```

- **约定**：`same` 是"同一说话人"试验对的分数（余弦相似度），`diff` 是"不同说话人"的分数；**分数越高越像同一人**，`score ≥ t` 判为接受。
- `far`（误接受率）= 不同人却被接受的比例；`frr`（误拒绝率）= 同一人却被拒绝的比例。方向与约定一致，这个实现是对的（对比第 16 节代码中方向不一致的 bug）。
- 候选阈值取所有出现过的分数，`O(T·N)` 的暴力扫描。数据量大时应先排序再一次扫描（`O(N log N)`）。
- 返回 `(far + frr) / 2`：离散样本上 FAR 与 FRR 很少恰好相等，取最接近点的平均值是常见近似。
- ⚠️ 参数顺序非常关键：若误写成 `eer_from_scores(diff, same)`，实测会返回约 99.9%，而且不会报错（测验 Q12）。
- 与讲义 Step 5 的 `eer()` 逻辑相同，只是多返回了阈值。

### 3.5 SECS：余弦相似度

```python
def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-12
    nb = math.sqrt(sum(x * x for x in b)) or 1e-12
    return dot / (na * nb)

    # ... main() 中：
    ref_emb = [rng.gauss(0, 0.1) for _ in range(192)]
    clone_emb = [ref_emb[i] + rng.gauss(0, 0.1) for i in range(192)]
```

- `or 1e-12`：模长为 0（假值）时用一个极小数代替，避免除零。
- **192 维**是 ECAPA-TDNN 说话人 embedding 的常见维度（讲义 Step 3 用的 `speechbrain/spkrec-ecapa-voxceleb`）。
- 模拟方式：克隆 embedding = 参考 embedding + 同等强度的噪声（标准差都是 0.1）。理论上余弦约为 `σ_s / √(σ_s² + σ_n²) = 1/√2 ≈ 0.707`，实测 0.644（有限样本的随机波动）。低于讲义说的 0.75"可辨认"线——这个"克隆"不合格。

### 3.6 FAD 形式的距离

```python
def embedding_fad_like(real_embeds, fake_embeds):
    def mean_var(embs):
        n = len(embs[0])
        mean = [sum(e[i] for e in embs) / len(embs) for i in range(n)]
        var = [sum((e[i] - mean[i]) ** 2 for e in embs) / len(embs) for i in range(n)]
        return mean, var
    mu_r, v_r = mean_var(real_embeds)
    mu_f, v_f = mean_var(fake_embeds)
    mean_dist = sum((a - b) ** 2 for a, b in zip(mu_r, mu_f))
    var_dist = sum((math.sqrt(a) - math.sqrt(b)) ** 2 for a, b in zip(v_r, v_f))
    return math.sqrt(mean_dist + var_dist)
```

- **嵌套函数** `mean_var`：只在外层函数内部使用的小工具，定义在里面可以避免污染模块命名空间。
- 按维度求均值和（总体）方差：`embs` 是"样本 × 维度"的二维列表，`e[i] for e in embs` 取出所有样本的第 i 维。
- 真正的 FAD：`‖μ_r − μ_g‖² + Tr(Σ_r + Σ_g − 2(Σ_r Σ_g)^½)`，Σ 是全协方差矩阵。若假设协方差是**对角阵**，迹项化简为 `Σᵢ (σ_r,i − σ_g,i)²`，正是 `var_dist`。所以这个函数 = 对角近似的 Fréchet 距离。
- ⚠️ 与通常报告的 FAD 有两处不同：①对角近似，忽略维度间相关；②最后又**开了一次根号**（FAD/FID 一般报告的是不开根号的平方形式）。本例开根号前为 3.057，开根号后为 1.748。
- ⚠️ 打印时拿 `MusicGen-small on MusicCaps: 4.5` 作对照没有可比性：真实 FAD 用 VGGish 128 维 embedding、特定参考集，这里是 32 维随机高斯。
- ⚠️ **小样本偏差**：额外实验用两组**同分布**样本（各 50 个、32 维）计算，距离约 1.36，并不是 0；样本增至 500 个时约 0.44。也就是说，本例真假之间的 1.748 里有相当一部分只是估计噪声——这正是讲义说"FAD depends on reference set"之外的另一个坑。

### 3.7 MMAU 式准确率与基准速查表

```python
def mmau_accuracy(predictions, golds):
    correct = sum(1 for p, g in zip(predictions, golds) if p == g)
    return correct / max(1, len(predictions))
```

- 逐题比较预测与标准答案。10 道题对了 7 道 → 0.700，远高于 4 选 1 的随机基线 0.250。
- ⚠️ 只报一个总体准确率。讲义的铁律之一是"Per-category for MMAU"：MMAU-Pro 分 speech / sound / music / multi-audio 四类，multi-audio 上各模型只有约 22%（低于随机），总体数字会把它掩盖。改进方法是给每道题加类别标签，用字典按类别汇总。
- `zip` 遇到长度不同的列表会静默截断，若预测数少于题目数，分母却用 `len(predictions)`，准确率会被高估；更稳妥的是检查长度相等，或以 `len(golds)` 为分母。

速查表部分：

```python
    rows = [
        ("Open ASR Leaderboard",  "LibriSpeech + multilingual", "Parakeet-TDT 6.05%, Whisper-LV3-turbo 1.58%"),
        # ...
        ("ASVspoof 5",            "anti-spoofing EER",           "SOTA ~7.23% on in-the-wild"),
    ]
```

- 硬编码的参考数字，不参与计算。`{name:<24}` 等是左对齐宽度，超长字符串（如 `Artificial Analysis Speech`、`LibriSpeech + multilingual`）会把列撑宽，导致个别行错位。
- ⚠️ 阅读这张表时注意：第一行两个 WER 数字的口径看起来并不一致（6.05% 与 1.58% 很可能来自不同的测试集），不能据此直接比较两个模型；最后一行把讲义中 "ASVspoof 5 上约 7.23%" 写成了 "on in-the-wild"，而讲义对野外数据的说法是"预期 5–10%"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手写 DP 编辑距离 | 看清 S/D/I 从哪来 | 不回溯对齐路径；生产用 `jiwer`，可分别报告 S/D/I |
| 简单正则规范化 | 短小易懂 | 缺数字/缩写展开、只支持英文；生产用 Whisper normalizer 并在报告中写明规则 |
| CER 不规范化 | 演示字符级编辑距离 | 与 WER 口径不一致；应共用同一规范化 |
| 暴力阈值扫描求 EER | 直接对应定义 | `O(T·N)`；大数据先排序再单次扫描，或用 ROC 插值 |
| 用随机高斯模拟 embedding | 不需要真实模型 | 只能演示公式；真实 SECS 用 ECAPA，真实 FAD 用 VGGish |
| 对角近似 + 开根号的 FAD | 免去矩阵平方根 | 与真实 FAD 不可比；生产用全协方差（`scipy.linalg.sqrtm`）或现成库 |
| 只报总体准确率 | 代码最短 | 违反"按类别报告"的铁律 |
| 所有随机数来自同一个 `rng` | 完全可复现 | 前面任何一步多取或少取一个随机数，后面所有结果都会变 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 下划线前缀命名 | `_edit_distance` | 约定为"内部函数"，`from main import *` 不会导入它 |
| 二维列表初始化 | `[[0] * (len(b) + 1) for _ in range(len(a) + 1)]` | 外层必须用推导式，否则各行会共享同一列表 |
| `min` 多参数 | `min(dp[i-1][j] + 1, dp[i][j-1] + 1, dp[i-1][j-1] + cost)` | 取三者最小值 |
| 条件表达式 | `cost = 0 if a_tokens[i - 1] == b_tokens[j - 1] else 1` | 一行二选一 |
| 正则 `re.sub` | `re.sub(r"[^a-z0-9\s]", "", text)` | `r""` 原始字符串；`[^...]` 取反字符集；`\s+` 匹配一个或多个空白 |
| 方法链 | `re.sub(...).strip()`、`normalize(ref).split()` | 上一步的返回值直接调用下一个方法 |
| 函数内 `import` | `normalize` 里的 `import re` | 合法；模块会被缓存，但通常放文件顶部 |
| `list(str)` | `list(ref)` | 把字符串拆成字符列表 |
| `or` 提供默认值 | `math.sqrt(...) or 1e-12` | 左边为 0 时取右边，防除零 |
| 嵌套函数 | `embedding_fad_like` 里的 `def mean_var(embs)` | 只在外层函数内可见 |
| 嵌套推导式 | `[[rng.gauss(0, 1.0) for _ in range(32)] for _ in range(50)]` | 生成 50 × 32 的二维列表 |
| 计数惯用法 | `sum(1 for p, g in zip(predictions, golds) if p == g)` | 统计满足条件的个数 |
| 元组解包 | `gap, t, far, frr = best`；`eer, t = eer_from_scores(...)` | 一次接住多个返回值 |
| `!r` 转换 | `f"  ref: {ref!r}"` | 用 `repr()` 显示字符串，会带引号；含单引号时自动改用双引号 |
| f-string 格式符 | `{wer(ref, hyp):.3f}`、`{eer * 100:.2f}`、`{name:<24}` | 小数位数与对齐宽度；花括号里可调用函数 |
| `random.Random(seed)` | `rng = random.Random(0)` | 独立、可复现的随机数生成器 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（约 0.04 秒）的输出：

```text
=== WER + CER ===
  ref: 'turn on the kitchen lights'
  hyp: 'turn off the kitchen lights'
    WER = 0.200   CER = 0.077
  ref: "what's the weather today"
  hyp: 'what is the weather today'
    WER = 0.500   CER = 0.083
  ref: 'play jazz'
  hyp: 'play jazz'
    WER = 0.000   CER = 0.000
  ref: 'set a 5 minute timer'
  hyp: 'set a five minute timer'
    WER = 0.200   CER = 0.200

=== EER (toy speaker verification) ===
  same mean cos: 0.795
  diff mean cos: 0.203
  EER = 0.10%   at threshold 0.661

=== SECS (toy voice-cloning similarity) ===
  SECS = 0.644   (target: &gt; 0.75 for recognizable clone)

=== FAD-shaped embedding distance ===
  FAD-like = 1.748   (MusicGen-small on MusicCaps: 4.5)

=== MMAU-Pro-style multiple-choice accuracy ===
  accuracy = 0.700  (random on 4-way: 0.250)
```

逐条解读：

- **on → off**：WER 1/5 = 0.2（一个词替换）；CER 2/26 ≈ 0.077（`n→f` 替换 + 插入一个 `f`），这是**真实错误**，而且是会让灯"开"变"关"的严重错误——WER 0.2 看起来不高，语义却完全相反。指标之外还要看错误类型。
- **what's → what is**：WER 高达 0.5，CER 只有 0.083——**这不是识别错误**，是规范化缺少缩写展开造成的假错误。ref 那一行用双引号显示，是 `!r` 发现字符串里含单引号后自动选择的。
- **play jazz**：完全正确，两者都是 0。
- **5 → five**：WER、CER 都是 0.2，同样是格式差异而非识别错误（缺数字展开）。四句里有两句的"错误"是规范化不完整造成的，这正是讲义把"Normalize before scoring"列为第一条铁律的原因。
- **EER = 0.10%**：同人分数均值 0.795、异人 0.203，分得很开；额外检查发现同人最低 0.661、异人最高 0.736，有少量重叠，在阈值 0.661 处 FRR = 0、FAR = 1/500，平均后约 0.1%。可以对照讲义：ECAPA 在 VoxCeleb1-O 上约 0.87%。
- **SECS = 0.644**：低于 0.75 的"可辨认"线（理论期望约 0.707，见 3.5）。`&gt;` 是 HTML 实体，本意是 `>`，属于源码中的小瑕疵。
- **FAD-like = 1.748**：开根号后的对角近似值；同分布对照约 1.36，说明大部分是小样本估计噪声；与 4.5 的对比没有意义（见 3.6）。
- **accuracy = 0.700**：7/10，远高于随机 0.25；但没有按类别拆分。

后面的排行榜速查表是硬编码文本，注意 3.7 提到的口径问题；takeaways 四条对应讲义 Use It 部分的三条铁律。

---

## 7. 动手改一改

1. **补全规范化**：在 `normalize` 中加入缩写展开（先于删标点）和数字展开，确认第 2、4 对的 WER 变成 0，而第 1 对仍是 0.2。
2. **统一 CER**：让 `cer` 先调用 `normalize`，验证 `cer("Play jazz", "play jazz")` 变为 0。
3. **回溯 S/D/I**：从 `dp` 表右下角回溯，分别统计替换、删除、插入的个数，打印每一对的 `S/D/I`。
4. **语料级 WER**：写 `corpus_wer(pairs)`，把所有句子的编辑次数相加再除以总参考词数，与"逐句 WER 的平均"比较差异。
5. **FAD 偏差实验**：用同分布的两组 embedding，样本数分别取 20、50、200、1000，画出距离随样本数的变化；再去掉最后的 `math.sqrt`，对比数值。
6. **按类别报告 MMAU**：给 10 道题加上 `speech/sound/music/multi-audio` 标签，输出每个类别的准确率。

---

## 8. 常见坑

- **规范化不完整**：缩写、数字、大小写差异被当作识别错误，WER 被虚高（本文件的第 2、4 对例子）。
- **WER 与 CER 口径不一致**：一个规范化、一个不规范化，报告里的两个数字互相矛盾。
- **逐句 WER 取平均**：短句的 WER 波动极大（可以 > 1），语料级 WER 应汇总编辑次数后再除以总词数。
- **EER 参数顺序 / 分数方向写反**：结果从 0.1% 变成 99.9%，不报错。
- **拿玩具 FAD 和论文 FAD 比较**：embedding 模型、维度、参考集、样本量、是否开根号都不同。
- **只报一个总数**：MMAU 不分类别、延迟不报分位数、WER 不分切片，都会掩盖最关键的失败模式。
