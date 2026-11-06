# 测验 · 音频分类——从 MFCC 上的 k-NN 到 AST 和 BEATs（Audio Classification — From k-NN on MFCCs to AST and BEATs）

> **阶段 06 · 语音与音频 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 音频分类的范围 | 环境声事件、语音命令、语种识别、情感、场景，都是"一段音频 → 类别"；2026 年基线是 log-mel → CNN/Transformer → softmax |
| 2 | 真正的难点是数据 | 类别极度不平衡、领域偏移（干净 vs 嘈杂）、标签噪声；80% 的工作是数据整理、增强和评估，而不是换网络 |
| 3 | k-NN on MFCC | 每段音频的 MFCC 在时间上做 mean + var 池化 → 26 维定长向量，余弦相似度找 top-K，多数投票；无需 GPU |
| 4 | 2D CNN on log-mel | 把 `(T, n_mels)` 当图像，ResNet/VGG 式卷积，时间轴全局池化，softmax；仍是多数比赛的基线 |
| 5 | AST | 把 log-mel 切成 16×16 patch，加位置编码，送入 ViT；监督学习时代 AudioSet 的代表模型 |
| 6 | 自监督预训练（BEATs / WavLM） | 在海量无标注音频上预训练，下游只需 1–10% 的标注数据；2026 年非语音音频的默认起点 |
| 7 | Whisper encoder 作冻结骨干 | 丢掉 decoder，接线性分类头，在语种识别等任务上接近 SOTA，是"免费午餐"基线 |
| 8 | 不平衡的应对 | 训练时平衡采样（评估时不要）、Mixup（样本与标签同时线性插值）、SpecAugment（随机遮挡时间/频率带） |
| 9 | 评估指标 | 单标签互斥：top-1/top-5 准确率；多标签：mAP；严重不平衡：per-class recall + macro F1 |
| 10 | 决策规则 | 先用冻结的预训练骨干，而不是从零训练；标注少于约 1 万条时不要从零训练 |

### 核心技能（能动手做到）

- [ ] 用纯 Python 把一段音频变成 MFCC 帧序列，再用 mean + var 池化成 26 维定长向量
- [ ] 从零实现余弦相似度 k-NN 分类器，并能说清它在平票时的行为
- [ ] 跑通合成 4 类数据集的训练 / 测试，打印并读懂混淆矩阵（行 = 真实，列 = 预测）
- [ ] 手算一个小型 CNN 的参数量和输出形状，判断"3M 参数"之类的说法是否靠谱
- [ ] 为一个给定的音频分类任务选出架构、增强、类别平衡策略、损失与主指标
- [ ] 设计不泄漏的数据划分：说话人不相交、同一原始录音不跨 fold、流式数据按时间划分

---

## 二、基础自测（选择题）

**Q1.** 对 13 维 MFCC 的每一维在时间轴上取均值和方差并拼接，得到的定长向量维度是：

- A. 13
- B. 26
- C. 39
- D. 与音频时长成正比

**Q2.** AudioSet 这类"一段音频可以同时有多个标签"的任务，主评估指标应该是：

- A. top-1 准确率
- B. top-5 准确率
- C. mAP（mean average precision）
- D. 训练集上的 loss

**Q3.** 关于平衡采样（balanced sampling），下列做法正确的是：

- A. 训练和评估都按类别平衡采样，保证指标公平
- B. 只在训练时平衡采样，评估集保持真实分布
- C. 只在评估时平衡采样，训练集保持真实分布
- D. 平衡采样会引入偏差，任何时候都不应使用

**Q4.** Mixup 的正确描述是：

- A. 把两段音频首尾拼接，标签取并集
- B. `x = λ·x1 + (1−λ)·x2`，标签不变，仍用 x1 的标签
- C. `x = λ·x1 + (1−λ)·x2`，`y = λ·y1 + (1−λ)·y2`
- D. 随机把频谱图的某些频带置零

**Q5.** SpecAugment 的核心操作是：

- A. 对波形做变速和变调
- B. 在频谱图上随机遮挡若干时间段和频率带
- C. 在波形上叠加背景噪声
- D. 把多个模型的预测做平均

**Q6.** 关于 AST（Audio Spectrogram Transformer），下列说法**错误**的是：

- A. 把 log-mel 当作图像切成 patch（如 16×16）
- B. 给 patch 加位置编码后送入 ViT
- C. 它直接以原始波形样本作为 token，不需要 mel 特征
- D. 是 2021 年前后监督学习方式下 AudioSet 的代表模型

**Q7.** 你有 5 万条带标签的环境声片段，要做 30 类分类。按讲义的决策表，最合适的起点是：

- A. 从零训练一个大型 Transformer
- B. 微调 BEATs 或 AST
- C. 只用 MFCC 均值的 k-NN，不再尝试其他模型
- D. 用 Whisper 的 decoder 直接生成类别名

**Q8.** mean + var 池化相对于保留完整帧序列，最本质的信息损失是：

- A. 丢失了频率信息
- B. 丢失了帧的时间顺序：把所有帧倒序排列，池化结果完全不变
- C. 丢失了幅度信息
- D. 没有信息损失，均值和方差是充分统计量

---

## 三、动手 / 代码题

**Q9.** 阅读 `summarize`：

```python
def summarize(frames):
    n = len(frames[0])
    mean = [sum(f[i] for f in frames) / len(frames) for i in range(n)]
    var = [sum((f[i] - mean[i]) ** 2 for f in frames) / len(frames) for i in range(n)]
    return mean + var
```

(a) 手算 `summarize([[1, 2], [3, 6]])` 的输出。
(b) 设 `fr = [[1, 2], [3, 6], [5, 1]]`，`summarize(fr) == summarize(fr[::-1])` 的结果是什么？这说明了什么？举一个本节合成数据集之外、这种池化会失败的音频例子。
(c) 这里的方差是总体方差还是样本方差？对 k-NN 有影响吗？

**Q10.** 阅读 `cosine` 和 `knn`：

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

(a) `... or 1e-12` 在什么情况下生效？此时 `cosine` 返回什么？
(b) 4 个类别、`k=3`，如果 3 个近邻标签各不相同（1:1:1 平票），`knn` 返回哪个？结果是确定的吗？预测下面代码的输出：

```python
bank = [[1, 0], [0, 1], [1, 1], [-1, 0]]
labels = ["x", "y", "z", "w"]
print(knn([1, 0.1], bank, labels, k=3))
```

(c) 每次查询都对整个 bank 排序，时间复杂度是多少？bank 有 100 万条时怎么办？

**Q11.** 运行 `main.py`，混淆矩阵打印成这样：

```text
         low    mid_low   mid_high       high
       low          5          0          0          0
   mid_low          0          5          0          0
```

对照打印代码找出排版问题的原因，并修复：

```python
    header = "  " + " ".join(f"{c[:8]:>10}" for c in classes)
    print(header)
    for gold in classes:
        row = f"  {gold[:8]:>8}"
        for pred in classes:
            row += f" {confusion[gold][pred]:>10}"
        print(row)
```

**Q12.** 讲义 Step 4 给出 `AudioCNN`，并称其"3M parameters"：

```python
class AudioCNN(nn.Module):
    def __init__(self, n_mels=80, n_classes=50):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.head = nn.Linear(128, n_classes)

    def forward(self, x):  # x: (B, 1, T, n_mels)
        return self.head(self.body(x).flatten(1))
```

(a) 手算总参数量（含 bias），与"3M"对比。
(b) 输入 `(8, 1, 1000, 80)` 时，`self.body(x)` 和最终输出的形状各是什么？
(c) 为什么这个模型能接受任意长度 `T` 的输入？构造函数里的 `n_mels` 参数起作用了吗？

---

## 四、面试高频题

**Q13.**（基础必考）梳理音频分类模型从 MFCC + k-NN 到 CNN、AST、BEATs 的演进。面对一个新任务，你怎么选起点？

**Q14.**（原理深挖）单标签多分类、多标签分类、严重不平衡分类分别该用什么损失和指标？为什么多标签任务不能只报 top-1 准确率？

**Q15.**（工程实践）AudioSet 的标签呈极长尾分布。训练时你会用哪些手段应对类别不平衡和标签噪声？每种手段的风险是什么？

**Q16.**（场景设计）为智能音箱设计一个"玻璃破碎 / 婴儿哭声"检测器：只有约 500 条标注片段，要求在端侧实时运行。请给出数据、模型、增强、评估、部署的完整方案。

**Q17.**（追问型）你的音频分类模型离线准确率 97%，上线后效果明显变差。从数据划分和评估的角度，最可能是哪些问题？

---

## 五、参考答案与解析

### Q1 — 答案：B

`summarize` 返回 `mean + var`（Python 列表拼接），13 + 13 = 26。代码运行时打印 `feature dim: 26 (mean+var of 13 MFCC)`。C 的 39 是 MFCC + Δ + ΔΔ 的常见维度；D 错在池化的目的就是把变长序列压成定长向量。

### Q2 — 答案：C

多标签任务里每个类别是独立的二分类，需要对每个类别在所有阈值上计算 average precision 再求平均（mAP）。top-1 只看"分数最高的那个类别对不对"，无法衡量其余同时存在的标签；技能文件 `skill-classifier-designer` 明确要求"拒绝只用 top-1 评估多标签任务"。

### Q3 — 答案：B

讲义原文："Balanced sampling during training (not in evaluation)"。训练时平衡采样让尾部类别得到足够的梯度；评估时必须保持真实分布，否则指标会高估模型在真实场景的表现。若需要关注尾部类别，评估时看 per-class recall / macro F1，而不是改变测试分布。

### Q4 — 答案：C

讲义 Key Terms：`x = λ·x1 + (1-λ)·x2; y = λ·y1 + (1-λ)·y2`。标签也要按同一个 λ 插值（软标签），否则模型会被要求把"混合后的声音"判成单一类别。A 是另一种增强（拼接）；D 是 SpecAugment。

### Q5 — 答案：B

SpecAugment = 在频谱图上随机置零若干时间段（time mask）和频率带（freq mask），迫使模型不依赖某一段局部信息。讲义称其"Simple; critical"。A、C 是波形级增强；D 是集成。

### Q6 — 答案：C

AST 的输入是 log-mel 频谱图，不是原始波形——A、B、D 都是讲义描述。直接从波形学习表示的是 wav2vec 2.0 / WavLM 一类自监督模型（WavLM 在讲义中与 BEATs 并列为自监督起点）。

### Q7 — 答案：B

讲义 Use It 表：中等规模（1K–100K）→ BEATs 或 AST 微调。A 对应 >100K 且有充足算力时才考虑；C 是 <1000 条时的基线，有 5 万条数据还停留在 k-NN 浪费了数据；D 不合理——讲义说的是用 Whisper 的 **encoder** 加线性头。

### Q8 — 答案：B

均值和方差对帧的排列顺序不变（permutation-invariant），所以"先高后低"和"先低后高"的声音得到相同的特征。合成数据集里每类都是稳态纯音，所以这不是问题；但对时间结构重要的声音（如上扬 vs 下降的音调、"开门" vs "关门"的先后顺序）就会失效。A、C 错：MFCC 本身就编码了频谱和能量；D 错：均值和方差只对高斯分布是充分统计量，音频特征远非如此。

### Q9 — 参考答案

(a) 两帧：第 0 维 `[1, 3]`，均值 2，方差 `((1−2)² + (3−2)²)/2 = 1`；第 1 维 `[2, 6]`，均值 4，方差 `((2−4)² + (6−4)²)/2 = 4`。输出 `[2.0, 4.0, 1.0, 4.0]`（实测一致）——前一半是均值，后一半是方差。

(b) 结果是 `True`。求和与顺序无关，所以 mean + var 池化**完全丢失时间顺序**。失败例子：一段从 200 Hz 扫到 1600 Hz 的上行扫频与一段 1600 → 200 Hz 的下行扫频，逐帧的频谱集合几乎相同、只是顺序相反，池化后几乎一样；"门铃叮-咚" vs "咚-叮"同理。CNN 的时间卷积、Transformer 的位置编码，就是为了保留这类时序信息。

(c) 除以 `len(frames)`，是**总体方差**（有偏估计）；样本方差应除以 `n − 1`。由于每段音频的帧数相同（都是 14 帧），两者只差一个常数因子 `14/13`，对所有样本同比例缩放方差这 13 维，会轻微改变余弦相似度中均值与方差两部分的相对权重，但不改变"哪类更像"的大体结论。

### Q10 — 参考答案

(a) 当向量全为 0 时，`math.sqrt(0) == 0.0` 为假值，`or` 返回 `1e-12`，避免除零。此时 `dot = 0`，`cosine` 返回 `0.0`（实测 `cosine([0, 0], [1, 1]) == 0.0`），即"零向量与任何向量都不相似"。

(b) 返回**最相近的那个邻居的标签**，结果是确定的。原因：`idx` 已按相似度从高到低排序，`Counter` 按首次出现的顺序记录元素，`most_common` 在计数相同时保持插入顺序。示例中 `[1, 0.1]` 与 `[1,0]`、`[1,1]`、`[0,1]` 的余弦约为 0.995、0.77、0.10，top-3 标签为 `x, z, y`，各 1 票，返回 `x`。实测输出 `x`。生产中更稳妥的做法是距离加权投票，或用奇数 k 且 k 不是类别数的倍数。

(c) 每次查询算 `n` 次余弦（`O(n·d)`）再排序（`O(n log n)`）。可以改用 `heapq.nlargest(k, ...)` 降到 `O(n log k)`；bank 到百万级时，先把向量归一化，用向量数据库或 ANN 索引（如 FAISS 的 HNSW / IVF）做近似最近邻检索。

### Q11 — 参考答案

原因：表头只有 `"  "` 前缀，**没有为行标签那一列留位置**；而每行先打印了 `2 + 8 = 10` 个字符宽的行标签，再加空格和 10 宽的数字。于是表头的第一列 `low` 落在了行标签的位置上，整个表头比数据列左移了约 9 个字符。

修复——给表头补上与行标签同宽的空白，并让列分隔方式一致：

```python
    header = "  " + " " * 8 + "".join(f" {c[:8]:>10}" for c in classes)
    print(header)
    for gold in classes:
        row = f"  {gold[:8]:>8}"
        for pred in classes:
            row += f" {confusion[gold][pred]:>10}"
        print(row)
```

修复后：

```text
                  low    mid_low   mid_high       high
       low          5          0          0          0
  mid_high          0          0          5          0
```

要点：`f"{x:>10}"` 是右对齐、宽度 10；对齐类 bug 只要逐字符数清每段宽度即可定位。

### Q12 — 参考答案

(a) 卷积参数 = `out × in × k × k + out`（bias）：

| 层 | 计算 | 参数 |
|----|------|------|
| Conv2d(1, 32, 3) | 32×1×9 + 32 | 320 |
| Conv2d(32, 64, 3) | 64×32×9 + 64 | 18,496 |
| Conv2d(64, 128, 3) | 128×64×9 + 128 | 73,856 |
| Linear(128, 50) | 128×50 + 50 | 6,450 |
| 合计 | | **99,122 ≈ 0.1M** |

ReLU、MaxPool、AdaptiveAvgPool 没有参数。所以讲义中的"3M parameters"与代码不符，实际约 0.1M，相差约 30 倍。面试中能当场算出参数量是基本功。

(b) `(8,1,1000,80)` → 第一次 MaxPool 后 `(8,32,500,40)` → 第二次后 `(8,64,250,20)` → 第三层卷积 `(8,128,250,20)` → `AdaptiveAvgPool2d(1)` 后 `(8,128,1,1)`；`flatten(1)` 得 `(8,128)`；`head` 输出 `(8,50)` 的 logits。

(c) `AdaptiveAvgPool2d(1)` 无论输入的空间尺寸多大，都输出 1×1，所以 `T`（以及 `n_mels`）可以变化，全连接层的输入始终是 128 维。构造函数里的 `n_mels` 参数**没有被使用**——它只是文档性质的提示。

### Q13 — 参考回答要点

- **演进**：
  - MFCC + k-NN（1990s）：手工特征 + 最近邻，小而干净的数据集上意外地强，无需 GPU；
  - 2D CNN on log-mel（2015–2019）：把频谱当图像，时间轴全局池化；
  - AST（2021–2024）：log-mel 切 patch + ViT，监督学习下的 AudioSet 代表；
  - BEATs / WavLM（2024–2026）：海量无标注音频自监督预训练，下游只需少量标注；
  - Whisper encoder 冻结 + 线性头：语种识别、简单事件分类上的"免费午餐"。
- **选起点**（讲义 Use It 表）：<1000 条 → k-NN-MFCC 基线 + 增强；1K–100K → BEATs/AST 微调；>100K → 从零训练或微调 Whisper encoder；端侧实时 → 40 维 MFCC 小 CNN + int8 量化；语种识别 → MMS-LID 等现成基线。
- **核心原则**："start with a frozen backbone, not a fresh model"。
- **加分点**：先做最便宜的基线（k-NN）确定"下限"，再上预训练模型；强调数据（不平衡、领域偏移、标签噪声）才是主要矛盾。

### Q14 — 参考回答要点

| 任务类型 | 输出层 + 损失 | 主指标 |
|---------|--------------|-------|
| 单标签互斥（Speech Commands） | softmax + 交叉熵 | top-1 / top-5 准确率 |
| 多标签（AudioSet） | 每类 sigmoid + BCE | mAP |
| 严重不平衡 | CE/BCE + 类别权重或 focal loss | per-class recall + macro F1 |

- 多标签不能只报 top-1：一段音频可能同时有"说话 + 音乐 + 汽车"，top-1 只检验其中一个，其他标签预测得再差也看不出来；而且多标签的阈值选择本身是问题，mAP 对所有阈值求平均，与阈值无关。
- 不平衡时准确率会被头部类别主导：99% 的样本是"背景"时，全预测"背景"也有 99% 准确率。macro F1 对每个类别等权平均，per-class recall 能看出哪些尾部类别被"放弃"了。
- 加分点：mAP 是"按类别平均"，与 micro 平均不同；上线时还要按业务选阈值（如对玻璃破碎要求高召回）。

### Q15 — 参考回答要点

- **平衡采样**：按类别（或标签频率倒数）重采样，尾部类别出现得更频繁。风险：尾部样本被反复看到、容易过拟合；只能用于训练。
- **Mixup**：样本和标签同时插值，平滑决策边界，对标签噪声也有一定鲁棒性。风险：λ 分布（Beta(α, α)）需要调；对需要精确时间定位的任务可能有害。
- **SpecAugment**：遮挡时间/频率带，防止依赖局部线索。风险：遮挡太多会删掉短促事件的全部证据。
- **类别权重 / focal loss**（技能文件提到）：放大尾部类别或难样本的损失。风险：权重过大使训练不稳定，噪声标签被放大。
- **标签噪声**：AudioSet 是弱标签（只标注片段级，不标注时间位置），可用更稳健的损失、知识蒸馏/伪标签清洗、人工复核尾部类别。
- **评估**：保持测试集真实分布，报告 mAP 和尾部类别的指标。
- 加分点：说出讲义观点"80% 的问题是整理、增强、评估，而不是换 CNN 还是 Transformer"。

### Q16 — 参考回答要点

1. **数据**：500 条正样本远远不够覆盖真实环境——补充大量负样本（电视声、厨房声、说话声，尤其是"像玻璃破碎"的难负例：碗碟碰撞、钥匙）；用公开数据集作为背景噪声；按录音来源划分 train/test，防止同一录音的片段跨集合。
2. **模型**：讲义的端侧推荐——40 维 MFCC + 小 CNN，int8 量化（KWS 风格）。更好的做法是先用 BEATs 等预训练模型在服务器上训练"教师"，再蒸馏到小 CNN；不要在 <1 万条标注上从零训练大模型（技能文件规则）。
3. **增强**：SpecAugment、Mixup、按多种信噪比混入背景噪声、混入不同房间的混响、增益随机化。
4. **评估**：这是严重不平衡的检测问题——看 per-class recall、precision、每小时误报次数，而不是准确率；在真实家居环境录音上做测试。
5. **部署**：流式滑窗推理（如 1 秒窗口、0.5 秒步长），连续多帧触发才报警以降低误报；监控线上误报率，收集难例回流。
- 加分点：明确业务权衡——玻璃破碎漏报代价高（召回优先），婴儿哭声误报会让用户关掉功能（需要控制误报）。

### Q17 — 参考回答要点

- **数据泄漏**：同一段原始录音被切成多个片段，分别落入训练集和测试集，模型"记住了录音条件"而非声音类别。ESC-50 提供预先划分好的 5 个 fold 就是为了避免这一点；涉及说话人的任务必须**说话人不相交**划分；流式/时间序列数据要**按时间**划分（技能文件第 5 条）。
- **领域偏移**：训练数据干净，线上嘈杂；麦克风、采样率、编解码不同（回顾第 01、02 节的采样率和特征一致性）。
- **评估集分布不真实**：在平衡后的测试集上评估，高估了真实分布下的表现；或线上类别先验不同（大量"其他"声音）。
- **阈值与指标不匹配**：离线用 argmax 准确率，线上需要固定阈值，precision/recall 完全不同。
- **特征管线不一致**：训练与服务的 mel 数、归一化、补边不同（第 02 节的"静默 bug"）。
- 加分点：给出排查顺序——先复现线上输入，在同一管线上离线评估；再分桶看误差（按设备、环境、类别），定位是数据、特征还是模型的问题。

---

## 六、关联知识点

### 前置知识
- [阶段 06 · 02 频谱图、Mel 刻度与音频 Features](../../02-spectrograms-mel-features/docs/zh.md)：本节的 `featurize` 就是上一节的 STFT → mel → log → DCT 管线。
- [阶段 02 · 06 k-NN 与距离](../../../02-ml-fundamentals/06-knn-and-distances/docs/zh.md)：k-NN 的原理、k 的选择与距离度量。
- [阶段 04 · 03 CNN：从 LeNet 到 ResNet](../../../04-computer-vision/03-cnns-lenet-to-resnet/docs/zh.md)：把 log-mel 当图像用 CNN 分类。
- [阶段 04 · 14 Vision Transformers](../../../04-computer-vision/14-vision-transformers/docs/zh.md)：AST 就是 ViT 用在频谱图上。

### 本节被哪些后续内容用到
- [阶段 06 · 06 说话人识别与验证](../../06-speaker-recognition-verification/docs/zh.md)：同样是"变长音频 → 定长 embedding"，但用 ECAPA 和统计池化。
- [阶段 06 · 14 语音活动检测与对话轮次交接](../../14-voice-activity-detection-turn-taking/docs/zh.md)：VAD 本质是逐帧的"语音 / 非语音"二分类。
- [阶段 06 · 16 语音反欺骗和音频水印](../../16-anti-spoofing-audio-watermarking/docs/zh.md)：反欺骗是"真人 / 合成"二分类，严重依赖本节的评估方法。
- [阶段 06 · 17 音频 Evaluation](../../17-audio-evaluation-metrics/docs/zh.md)：音频任务指标的系统总结。
- [阶段 02 · 17 不平衡数据](../../../02-ml-fundamentals/17-imbalanced-data/docs/zh.md)：重采样、类别权重、focal loss 的通用方法。
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：precision/recall、F1、AP 的定义。

### 延伸关键词
`PANNs` · `HTS-AT` · `Audio-MAE` · `EAT` · `HEAR benchmark` · `弱标签 / 多示例学习` · `focal loss` · `知识蒸馏` · `int8 量化` · `声音事件检测 (SED)`
