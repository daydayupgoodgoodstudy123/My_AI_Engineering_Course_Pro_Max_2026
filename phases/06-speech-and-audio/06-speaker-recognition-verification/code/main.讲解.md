# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 06 节 说话人识别与验证 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无命令行参数，约 3 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`、`collections.defaultdict`）

---

## 1. 这份代码在考察什么

这份脚本用一个"玩具版"说话人验证系统，把讲义的三个核心环节串起来：

1. **说话人 embedding**：用 MFCC 帧的"均值 + 标准差"拼成 26 维向量，再做 L2 归一化——这是 x-vector "统计池化"思想的最简化版本。
2. **余弦打分**：归一化后的向量点积就是余弦相似度。
3. **trial 列表**：所有"同一说话人"与"不同说话人"的组合，分别得到两组分数。
4. **EER**：扫描阈值，找到误接受率（FA）与误拒绝率（FR）最接近的点。
5. **数字直觉**：最后打印讲义中的 2026 年 VoxCeleb1-O EER 排行。

> 一句话：**说话人验证 = embedding + 余弦 + 阈值，而阈值的好坏全部浓缩在 EER 这一个数字里**。真实系统只是把"MFCC 统计量"换成了 ECAPA-TDNN / WavLM 这样训练好的 embedding 模型。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tone_mix` | 函数 | 多个正弦叠加 + 高斯噪声，模拟一个"说话人" | 合成数据 |
| `hann` / `dft_mag` / `frame_signal` / `stft_mag` / mel 相关 / `log_transform` / `dct_ii` / `featurize` | 函数 | 与第 03 节相同的 MFCC 管线 | 特征提取 |
| `l2_normalize` | 函数 | 向量除以其 L2 范数 | embedding 归一化 |
| `embed_mfcc_stats` | 函数 | MFCC 均值 + 标准差 → 26 维 → 归一化 | 统计池化 embedding |
| `cosine` | 函数 | 点积（假设输入已归一化） | 余弦打分 |
| `eer` | 函数 | 扫描阈值求 FA ≈ FR 的点 | EER |
| `main()` | 演示入口 | 注册 5 人 × 5 条、构造 trial、算 EER、打印排行 | 评估流程 |

数据流：`tone_mix → embed_mfcc_stats（featurize → 统计 → l2_normalize）→ 两两 cosine → same / diff 分数 → eer`。

---

## 3. 逐段精讲

### 3.1 合成"说话人"：`tone_mix`

```python
def tone_mix(freqs, sr, seconds, amp=0.4, noise=0.02):
    n = int(sr * seconds)
    out = []
    for i in range(n):
        val = 0.0
        t = i / sr
        for f in freqs:
            val += math.sin(2.0 * math.pi * f * t)
        val = amp * val / max(1, len(freqs))
        val += random.gauss(0, noise)
        out.append(val)
    return out
```

- 每个"说话人"由 3 个频率组成（例如 alice = 200/400/600 Hz，像基频 200 Hz 加两个谐波），叠加后除以频率个数、乘以 `amp`，保证幅度不超过 0.4。
- `max(1, len(freqs))` 防止空列表时除零。
- 噪声 `random.gauss(0, noise)` 是同一说话人不同"语音"之间唯一的差异来源；`main` 中把 `noise` 设成 0.04。
- ⚠️ 极度简化：真实说话人之间的差异来自声道形状、基频范围、发音习惯等，而且同一个人每次说的内容、语速、情绪都不同（类内差异大得多）。这里的"说话人"每次都发同一个和弦，只是噪声不同，所以很容易区分。

### 3.2 特征管线：沿用第 03 节

```python
def apply_filterbank(spec, fb):
    return [[sum(w * frame[k] for k, w in enumerate(f) if w) for f in fb] for frame in spec]
```

- `hann`、`dft_mag`、`frame_signal`、`stft_mag`、`hz_to_mel`、`mel_to_hz`、`mel_filterbank`、`log_transform`、`dct_ii`、`featurize` 与第 03 节完全相同（参见 [第 02 节代码讲解](../../02-spectrograms-mel-features/code/main.讲解.md) 和 [第 03 节代码讲解](../../03-audio-classification/code/main.讲解.md)）。
- 唯一的写法变化是 `apply_filterbank` 被进一步压缩成一个**嵌套列表推导式**：外层遍历帧，内层遍历滤波器，最内层是带 `if w` 过滤的加权求和。含义仍是 `spec @ fbᵀ`。
- 参数：8 kHz、帧长 256、帧移 128、40 mels、13 MFCC。每条 0.4 秒语音 → 3200 样本 → `1 + (3200 − 256) // 128 = 24` 帧。

### 3.3 Embedding：均值 + 标准差 + L2 归一化

```python
def l2_normalize(v):
    norm = math.sqrt(sum(x * x for x in v)) or 1e-12
    return [x / norm for x in v]


def embed_mfcc_stats(signal, sr):
    frames = featurize(signal, sr)
    n = len(frames[0])
    mean = [sum(f[i] for f in frames) / len(frames) for i in range(n)]
    var = [sum((f[i] - mean[i]) ** 2 for f in frames) / len(frames) for i in range(n)]
    std = [math.sqrt(v) for v in var]
    return l2_normalize(mean + std)
```

- 与第 03 节的 `summarize` 相比有两点不同：
  1. 用**标准差**而不是方差：标准差与均值同量纲，数值尺度更接近，拼接后不会某一半"压倒"另一半。讲义 Step 1 的 `embed_mfcc_stats` 也是 `mean + std`。
  2. 最后做 **L2 归一化**：向量模长变为 1，后续点积就是余弦。讲义 Pitfalls："Cosine on non-normalized embeddings. L2-normalize first; otherwise the magnitude dominates."
- 这正是 x-vector 里 **statistics pooling** 层做的事（对帧级特征求均值和标准差拼接），只不过 x-vector 是在 TDNN 学到的帧级特征上做，再接几层全连接得到 embedding；ECAPA-TDNN 进一步用注意力加权求均值和标准差。
- `or 1e-12`：全零向量时避免除零（同第 03 节的 `cosine`）。
- ⚠️ 讲义原话："Not SOTA by a mile — for teaching only."

### 3.4 `cosine`：其实只是点积

```python
def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))
```

- 因为 `embed_mfcc_stats` 已经保证输出是单位向量，余弦 = 点积，省掉了除以模长。
- ⚠️ 隐含契约：调用方必须传入**已归一化**的向量。如果传 `[3, 4]` 和 `[3, 4]`，会返回 25 而不是 1。生产代码要么在函数里归一化，要么用类型/命名明确这个契约（例如叫 `dot_normalized`）。
- 讲义 Step 2 的版本是完整的余弦（带除法、零向量返回 0），更稳健。

### 3.5 EER：扫描阈值

```python
def eer(same_scores, diff_scores):
    thresholds = sorted(set(same_scores + diff_scores))
    best_gap = float("inf")
    best_fa, best_fr, best_t = 1.0, 0.0, thresholds[0] if thresholds else 0.0
    for t in thresholds:
        fr = sum(1 for s in same_scores if s < t) / len(same_scores)
        fa = sum(1 for s in diff_scores if s >= t) / len(diff_scores)
        gap = abs(fa - fr)
        if gap < best_gap:
            best_gap = gap
            best_fa, best_fr, best_t = fa, fr, t
    return (best_fa + best_fr) / 2, best_t
```

- **候选阈值**：所有观测到的分数（`set` 去重、`sorted` 升序）。阈值只需在这些点上取，因为 FA、FR 只在越过某个分数时才会变化。
- **FR（误拒绝率）**：同一说话人的分数低于阈值 → 被错误拒绝；**FA（误接受率）**：不同说话人的分数 ≥ 阈值 → 被错误接受。分数恰好等于阈值时算"接受"。
- 找 `|FA − FR|` 最小的阈值，返回 `(FA + FR) / 2` 作为 EER 的近似，以及该阈值。讲义："Returns (eer, threshold_at_eer). Report both."
- **`best_gap = float("inf")` 是关键**：讲义 Step 3 的版本把初始值设为 `best = (1.0, 1.0, 0.0)`，其 gap 为 0，导致 `abs(fa - fr) < 0` 永远不成立、结果永远是 `(1.0, 0.0)`（EER 100%）。代码改用独立的 `best_gap` 并初始化为无穷大，修好了这个 bug。
- 初始化那一行的条件表达式只作用于元组的最后一个元素：右侧等价于 `(1.0, 0.0, (thresholds[0] if thresholds else 0.0))`，因为逗号在 Python 表达式中结合得最松。所以 `best_t` 在列表为空时取 0.0，不会影响前两个变量。
- 复杂度：每个阈值都遍历一遍全部分数，`O(T × (S + D))`。分数多时，先把两组分数排序再用双指针扫描，可降到 `O((S + D) log(S + D))`。
- ⚠️ 简化：
  - 两类分数完全可分时，返回的阈值是同说话人分数的**最小值**（升序扫描到的第一个 gap = 0 的点），工作点贴着正类边缘，不稳健。
  - 离散阈值下 FA 与 FR 往往不相等，取平均只是近似；严格做法是在 DET 曲线上插值求交点。
  - 空列表会除零（`len(same_scores) == 0`）。

### 3.6 `main()`：注册与 trial 构造

```python
    speakers = {
        "alice": [200, 400, 600],
        "bob":   [220, 330, 880],
        "carol": [300, 600, 1200],
        "dave":  [180, 540, 1080],
        "eve":   [260, 520, 780],
    }

    n_per = 5
    enroll = defaultdict(list)
    for spk, freqs in speakers.items():
        for _ in range(n_per):
            sig = tone_mix(freqs, sr, duration, noise=0.04)
            enroll[spk].append(embed_mfcc_stats(sig, sr))
```

- `defaultdict(list)`：访问不存在的键时自动创建空列表，省掉 `if spk not in enroll: enroll[spk] = []`。
- 每个说话人 5 条 0.4 秒的"语音"，共 25 个 embedding。
- ⚠️ 名字叫 `enroll`，但这里并没有区分"注册集"和"测试集"——所有 embedding 两两比对。真实流程是：先用几条语音算出注册模板（平均后归一化），再用**另外的**语音来验证。

```python
    for spk in spk_list:
        embs = enroll[spk]
        for i in range(len(embs)):
            for j in range(i + 1, len(embs)):
                same_scores.append(cosine(embs[i], embs[j]))
    for i, s1 in enumerate(spk_list):
        for s2 in spk_list[i + 1:]:
            for e1 in enroll[s1]:
                for e2 in enroll[s2]:
                    diff_scores.append(cosine(e1, e2))
```

- 同说话人：每人内部 `j > i` 的组合，`C(5,2) = 10` 对 × 5 人 = **50 对**。
- 不同说话人：说话人两两组合 `C(5,2) = 10` 组，每组 5 × 5 = 25 对，共 **250 对**。
- 用 `j in range(i + 1, ...)` 和 `spk_list[i + 1:]` 保证每对只算一次、不和自己比。
- 讲义练习 1 说"100-pair trial list"，与代码的 300 对不一致。

```python
    print(f"  synthetic speakers are near-orthogonal, so this toy hits 0% EER.")
    print(f"  real ECAPA-TDNN on VoxCeleb1-O lands at 0.87% after training on 2700 speakers.")
```

- ⚠️ 这两行是**硬编码**的说明文字，不依赖计算结果。第一句的"near-orthogonal"与实测不符：不同说话人的平均余弦是 0.558，最高 0.773，远不是"正交"（≈ 0）；EER 为 0 的原因是两类分数**完全可分**。
- 第二句的"2700 speakers"来自讲义；常用的 ECAPA 训练集 VoxCeleb2 开发集本身就有约 6000 个说话人，这个数字值得核实。
- 最后的表格是讲义中 2026 年的 VoxCeleb1-O 排行。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用和弦模拟说话人 | 无需下载数据、可复现 | 类内变化太小，EER 0% 不说明问题；真实评测用 VoxCeleb1-O 等 trial 列表 |
| MFCC 均值 + 标准差 | 统计池化的最简形式，无需训练 | 区分度远不如 ECAPA-TDNN / WavLM-SV；生产用 SpeechBrain 等预训练模型 |
| 标准差而非方差 | 与均值同量纲 | — |
| embedding 内部做 L2 归一化，`cosine` 只算点积 | 少一次除法 | 隐含契约易被误用；生产代码中应显式归一化或断言 |
| 全组合 trial、不分注册/测试 | 最大化 trial 数 | 与真实"注册模板 vs 测试语音"的流程不同 |
| 在观测分数上扫描阈值 | 简单、精确到样本 | 可分时阈值贴边；生产按目标 FAR 在开发集上定阈值，并配合 AS-norm |
| `best_gap = inf` | 修正讲义版本"永不更新"的 bug | — |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `random.seed` / `random.gauss` | `random.seed(123)`、`random.gauss(0, noise)` | 固定随机种子；高斯噪声 |
| `x or default` | `math.sqrt(...) or 1e-12` | 模长为 0 时兜底，避免除零 |
| 嵌套列表推导式 | `[[sum(...) for f in fb] for frame in spec]` | 外层遍历帧、内层遍历滤波器 |
| 列表拼接 | `mean + std` | 两个 13 维列表拼成 26 维 |
| `float("inf")` | `best_gap = float("inf")` | 正无穷，"求最小值"时的标准初始值 |
| 条件表达式 | `thresholds[0] if thresholds else 0.0` | 列表为空时给默认值 |
| 多变量赋值 | `best_fa, best_fr, best_t = fa, fr, t` | 一次更新三个变量 |
| `set` 去重 + `sorted` | `sorted(set(same_scores + diff_scores))` | 去重后升序排列 |
| 计数式生成器 | `sum(1 for s in same_scores if s < t)` | 统计满足条件的元素个数 |
| `collections.defaultdict` | `enroll = defaultdict(list)` | 访问缺失键时自动创建默认值 |
| `enumerate` + 切片避免重复配对 | `for i, s1 in enumerate(spk_list): for s2 in spk_list[i + 1:]` | 只取 `i < j` 的组合 |
| `dict.keys()` 转列表 | `list(speakers.keys())` | 固定说话人顺序以便下标访问 |
| f-string 格式 | `f"{e * 100:.2f}%"`、`f"{name:<18}"` | 花括号里可写表达式；`:<18` 左对齐 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 3 秒）：

```text
=== Enroll 5 synthetic speakers, 5 utterances each ===
  alice: 5 embeddings, dim=26
  bob: 5 embeddings, dim=26
  carol: 5 embeddings, dim=26
  dave: 5 embeddings, dim=26
  eve: 5 embeddings, dim=26

=== Build trial pairs (same vs different speaker) ===
  same-speaker pairs: 50  mean cosine: 0.995
  diff-speaker pairs: 250  mean cosine: 0.558

=== Equal Error Rate ===
  EER: 0.00%   at threshold: 0.989
  synthetic speakers are near-orthogonal, so this toy hits 0% EER.
  real ECAPA-TDNN on VoxCeleb1-O lands at 0.87% after training on 2700 speakers.

=== 2026 speaker-verification leaderboard ===
  | Model              | EER  | Params |
  | ReDimNet (2024)    | 0.39 | 24M    |
  | WavLM-SV large     | 0.42 | 316M   |
  | Pyannote 3.1       | 0.65 | 6M     |
  | ECAPA-TDNN         | 0.87 | 15M    |
  | x-vector (classic) | 3.10 | 5M     |
```

逐段解读：

- **注册**：每人 5 个 26 维 embedding。
- **trial**：50 对同说话人、平均余弦 0.995——几乎一模一样，因为同一"说话人"的信号只差噪声；250 对不同说话人、平均 0.558。
- **EER 0.00%，阈值 0.989**：额外分析得到同说话人最低分 0.9888、不同说话人最高分 0.7732（alice 与 eve，二者的谐波 200/400/600 与 260/520/780 最接近），两类之间有约 0.2 的空隙。代码选的阈值 0.989 恰好是同说话人的最低分，贴着正类边缘；取空隙中点（约 0.88）会更稳健。
- **"near-orthogonal"**：与实测不符，见 3.6。
- **排行表**：讲义的数字。注意参数量与 EER 并不单调：ReDimNet 24M 参数就做到 0.39%，而 WavLM-SV 316M 参数为 0.42%——部署时要同时看速度和模型大小（讲义表中还有吞吐量一列）。

---

## 7. 动手改一改

1. **让任务变难**：把 `noise` 从 0.04 调到 0.3，或把时长从 0.4 秒缩到 0.1 秒（对应讲义"短语音 EER 急剧变差"），观察两类分数的均值和 EER 如何变化。
2. **加一个"像 alice 的冒认者"**：新增 `"mallory": [205, 410, 615]`，看它与 alice 的分数落在哪里，EER 是否上升。
3. **分开注册与测试**：每人前 3 条做注册（平均 + 重新归一化），后 2 条做测试，重新构造 trial 并计算 EER（参考测验 Q12 的 `make_enrollment`）。
4. **改进阈值选择**：在两类分数可分时返回空隙的中点；再写一个 `threshold_at_far(diff_scores, target_far)`，按目标误接受率（如 1%）选阈值，并报告此时的 FRR。
5. **实现 S-norm**：为每个说话人留出一组 cohort（其他说话人的 embedding），对每个分数做 `0.5·((s − μ_e)/σ_e + (s − μ_t)/σ_t)`，比较归一化前后阈值的稳定性。
6. **复现讲义 Step 3 的 bug**：把讲义版本的 `eer` 粘进来跑一次，确认永远返回 `(1.0, 0.0)`，再对比本文件的修复。

---

## 8. 常见坑

- **未归一化就用点积当余弦**：模长会主导分数；本文件的 `cosine` 依赖调用方已归一化。
- **求最小值时初始值设错**：讲义 Step 3 的 `eer` 把初始 gap 设成 0，导致永远不更新；应初始化为 `float("inf")`。
- **只报 EER 不报阈值和评测条件**：技能文件要求同时报告评测集、信道和语音时长分布。
- **EER 阈值直接上线**：业务关心的是目标 FAR 下的 FRR，阈值应在目标域开发集上按 FAR 要求调。
- **注册集与测试集混用**：全组合 trial 适合评估 embedding 区分度，但不等于真实"注册 → 验证"流程。
- **硬编码的结论文字**：打印的解释文字与实际结果不符（如"near-orthogonal"），容易误导读者；结论应基于计算结果生成。
