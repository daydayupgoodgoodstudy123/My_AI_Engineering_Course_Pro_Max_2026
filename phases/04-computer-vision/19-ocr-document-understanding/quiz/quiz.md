# 测验 · OCR 和文档理解（OCR & Document Understanding）

> **阶段 04 · 计算机视觉 · 第 19 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过（或读懂）代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三个能力层次 | OCR（像素→文字）、版面解析（文字→区域：标题/正文/表格）、文档理解（区域→结构化字段，如 `invoice_total = 42.50`） |
| 2 | 经典流水线 | 文本检测（DB / EAST / CRAFT）→ 裁剪 → 识别（CRNN + CTC）→ 阅读顺序重建；各阶段误差会累积 |
| 3 | CRNN | CNN 把固定高度的文本行图压成"宽度方向的特征序列"，BiLSTM 建模上下文，线性头输出每个时间步的字符分布 |
| 4 | CTC 损失 | 不需要逐字符对齐标注；对所有"合并重复 + 删除 blank 后等于目标文本"的对齐路径求概率和 |
| 5 | blank 的作用 | 既表示"此处无字符"，又能把相邻的相同字符隔开（`l _ l` → "ll"，而 `l l` → "l"） |
| 6 | 贪心解码 vs beam search | 贪心：逐帧 argmax 再合并去 blank；beam search 在低置信输入上更好，干净文本上差距通常 <1% CER |
| 7 | 端到端模型 | Donut（ViT 编码器 + 文本解码器，直接输出 JSON）、TrOCR、Qwen-VL-OCR / InternVL；省去多阶段误差累积，但更吃数据和算力 |
| 8 | 版面解析与 KV 抽取 | LayoutLMv3、DocLayNet 给区域打标签；表单用 Key-Value 抽取模型（图像 + 文字 + 位置 → 字段） |
| 9 | 评测指标 | CER / WER = 编辑距离 / 参考长度；结构化字段用 F1；端到端文档解析用 JSON 的归一化树编辑距离 |

### 核心技能（能动手做到）

- [ ] 手写贪心 CTC 解码（合并重复、删除 blank），并能手工解码一串帧级 argmax 序列
- [ ] 给定输入尺寸，逐层推出 `TinyCRNN` 的特征图形状和 CTC 时间步数 T，并说明 T 与目标长度的约束
- [ ] 正确调用 `F.ctc_loss`：`log_probs` 的 `(T, N, C)` 布局、拼接式 targets、`input_lengths` / `target_lengths`、`blank`、`zero_infinity`
- [ ] 用动态规划实现 Levenshtein 编辑距离，并计算 CER / WER
- [ ] 能诊断合成数据本身的缺陷（如本节所有字符渲染成同一个色块），并改造数据生成器让任务"可学"
- [ ] 能根据文档类型、语言、是否需要结构化字段，在 Tesseract / PaddleOCR / Donut / VLM-OCR 之间做选型

---

## 二、基础自测（选择题）

**Q1.** 某团队说："我们 OCR 的 CER 只有 1%，但发票金额字段抽取还是经常出错。"按讲义的三层划分，问题最可能出在哪一层？

- A. OCR 层，CER 1% 说明识别不行
- B. 版面解析 / 文档理解层：字符认对了，但没有正确判断"哪个数字是总金额"
- C. 图像采集层，必须换更高分辨率的扫描仪
- D. CTC 损失设计错误

**Q2.** 为什么 OCR 识别模型通常用 CTC 而不是逐时间步的交叉熵？

- A. PyTorch 只支持 CTC
- B. 模型输出的是定长特征序列（每个时间步一个分布），而目标文本是变长的、且没有"每个字符落在哪几帧"的对齐标注；CTC 对所有合法对齐求和，只需要（图像, 文本）对就能训练
- C. 交叉熵在长序列上会数值溢出
- D. CTC 的计算速度比交叉熵快

**Q3.** 以 `_` 表示 blank，下列哪个帧级输出经过"先合并相邻重复、再删除 blank"后得到 `hello`？

- A. `h _ e _ l l _ o`
- B. `h h e e l l o o`
- C. `h h e _ l _ l o`
- D. `h _ e l l l o _`

**Q4.** 本节 `TinyCRNN` 的输入是 `(N, 1, 32, 80)`（高 32、宽 80）。经过 CNN 后，送入 CTC 的时间步数 T 是多少？

- A. 80
- B. 40
- C. 20
- D. 5

**Q5.** 关于 `F.ctc_loss(..., zero_infinity=True)`，下列说法正确的是：

- A. 它会把所有损失截断到 0 以上
- B. 当某个样本不存在合法对齐（例如 T 小于"目标长度 + 相邻重复字符数"）时，该样本损失为无穷大；`zero_infinity=True` 把这种损失和对应梯度置 0，避免整个 batch 出现 inf/NaN
- C. 它把 blank 的概率强制设为 0
- D. 它让损失按目标长度归一化

**Q6.** 参考文本 `hello`，模型输出 `helo`，CER 是：

- A. 0%
- B. 20%
- C. 25%
- D. 80%

**Q7.** 关于 Donut 这类端到端文档模型与"检测 + 识别 + 版面"流水线的对比，讲义的观点是：

- A. 端到端模型在所有场景都更好，流水线已经过时
- B. 端到端模型直接从图像输出文本或 JSON，避免了多阶段误差累积，但需要更多数据和算力；PaddleOCR 这类经典流水线仍是开源主力
- C. Donut 内部仍然调用了一个 OCR 引擎
- D. 流水线模型不需要任何标注数据

---

## 三、动手 / 代码题

**Q8.** 阅读 `TinyCRNN.forward`：

```python
    def forward(self, x):
        f = self.cnn(x)
        f = f.mean(dim=2).transpose(1, 2)
        h, _ = self.rnn(f)
        return F.log_softmax(self.head(h).transpose(0, 1), dim=-1)
```

已知 `feat=32, hidden=128`，词表大小 `len(VOCAB) = 37`，输入 `x` 形状为 `(8, 1, 32, 80)`。

1. 写出 `self.cnn(x)`、`f.mean(dim=2).transpose(1, 2)`、`h`、最终返回值的形状。
2. CNN 结束时特征图的高度是多少？`f.mean(dim=2)` 这一步在做什么？
3. 为什么最后要 `.transpose(0, 1)`？

**Q9.**（找 bug）`main()` 训练 200 步后，对 `["abc7", "xy45", "abc2"]` 做测试。数据生成函数如下：

```python
def synthetic_line(text, height=32, char_width=16):
    W = char_width * max(1, len(text))
    img = np.ones((height, W), dtype=np.float32)
    for i, c in enumerate(text):
        x = i * char_width
        shade = 0.0 if c.isalnum() else 0.5
        img[6:height - 6, x + 2:x + char_width - 2] = shade
    return img
```

1. 不运行代码，你能断定三个测试样本的预测结果之间有什么关系？最多能有几个 `ok`？
2. 这对训练损失意味着什么？讲义说"损失应从约 3 降到约 0.2"，在本代码的数据上可能吗？请给出一个损失下界的估算思路。
3. 修改 `synthetic_line`，让每个字符有可区分的"字形"。

**Q10.** 用本节的 `VOCAB = ["_"] + list("0123456789abcdefghijklmnopqrstuvwxyz")`（blank 下标为 0）：

1. 手工用 `greedy_ctc_decode` 的规则解码两条帧级 argmax 序列：`[18, 18, 0, 15, 22, 22, 0, 22, 25, 25, 0]` 和 `[18, 15, 22, 22, 22, 25]`，再用 `decode_to_str` 转成字符串。
2. 写一个函数 `cer(ref: str, hyp: str) -> float`，用 Levenshtein 编辑距离计算字符错误率。

---

## 四、面试高频题

**Q11.**（基础必考）请解释 CTC：它解决了什么问题？blank 有什么作用？损失是怎么高效计算的？它有什么建模假设和局限？

**Q12.**（原理深挖）CRNN 为什么要把图像高度压到 1、保留宽度作为时间轴？时间步数 T、字符宽度和目标长度之间有什么约束？中文等大字符集场景下 CRNN + CTC 会遇到什么问题？

**Q13.**（场景设计）设计一个"发票/收据结构化抽取"系统，输出 `{商家, 日期, 明细, 总金额}`。你会选流水线方案还是端到端方案？如何评测、如何上线？

**Q14.**（工程实践）你负责的 OCR 服务上线后，用户投诉"扫描件里的表格识别顺序全乱了"，而单行识别准确率很高。你怎么定位和解决？

**Q15.**（追问型）现在很多团队直接用 VLM（如 Qwen-VL-OCR）做 OCR。相比 CRNN + CTC，VLM-OCR 有什么新的风险？你会怎么在生产中控制这些风险？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义把能力分三层：OCR（像素→文字）、版面解析（分区域）、文档理解（抽字段）。CER 1% 说明字符基本都认对了，问题在于"这一页有十几个数字，哪个是 total"——需要版面信息（位置、相邻的 "Total" 标签）和语义理解。讲义原话："the gap between 'I want text from an image' and 'I need the total amount from this receipt' is bigger than most teams realise." A 混淆了层次；C、D 没有依据。

### Q2 — 答案：B

识别网络在宽度方向输出 T 个分布，目标文本长度 L ≤ T 且不知道每个字符对应哪些帧。逐帧交叉熵需要帧级标签（对齐），人工标注极其昂贵。CTC 把"所有能化简为目标文本的对齐路径"的概率加起来作为似然，因此只需要（图像, 文本）对。D 不是原因，CTC 的前向-后向计算反而比交叉熵复杂。

### Q3 — 答案：C

逐项化简：

- A：`h _ e _ l l _ o` → 合并重复 `h _ e _ l _ o` → 去 blank `helo`；
- B：`h h e e l l o o` → `h e l o` → `helo`；
- C：`h h e _ l _ l o` → 合并 `h e _ l _ l o` → 去 blank `hello` ✔；
- D：`h _ e l l l o _` → `h _ e l o _` → `helo`。

关键：两个 l 之间**必须有 blank 隔开**，否则会被"合并重复"吃掉。这正是 blank 存在的第二个理由。

### Q4 — 答案：C

四个 `MaxPool`：`MaxPool2d(2)`、`MaxPool2d(2)`、`MaxPool2d((2, 1))`、`MaxPool2d((2, 1))`。宽度只在前两次被减半：80 → 40 → 20，后两次 `(2, 1)` 只压高度不压宽度。所以 T = 20，每个时间步对应原图 4 像素宽；一个字符宽 16 像素，约占 4 个时间步。只压高度、尽量保留宽度，就是为了给 CTC 留足时间步。

### Q5 — 答案：B

CTC 要求 T ≥ L + 相邻重复字符数（每对相邻相同字符之间至少要插一个 blank）。不满足时没有任何合法路径，似然为 0，损失为 `+inf`，一个 inf 就会把整个 batch 的平均损失和梯度污染成 inf/NaN。`zero_infinity=True` 是一个"安全阀"，把这类样本的损失和梯度置零。D 描述的是 `reduction="mean"` 的行为（先除以目标长度，再对 batch 求平均），不是 `zero_infinity`。

### Q6 — 答案：B

`helo` 相对 `hello` 只缺一个 `l`，编辑距离 = 1；CER = 编辑距离 / 参考长度 = 1 / 5 = 20%。注意分母是**参考文本**长度，所以 CER 可以超过 100%（预测里有大量插入时）。

### Q7 — 答案：B

讲义："End-to-end models need more data and compute but skip the error accumulation of multi-stage pipelines."同时说 PaddleOCR 仍是 "the open-source workhorse"。A 过于绝对；C 错，Donut 恰恰是 "OCR-free"，没有检测器和识别器；D 错，流水线的每个模块都需要训练数据。

### Q8 — 参考答案

1. 形状（N = 8）：
   - `self.cnn(x)`：通道 1→32→64→128→128；高度 32→16→8→4→2；宽度 80→40→20→20→20。输出 `(8, 128, 2, 20)`。
   - `f.mean(dim=2)` → `(8, 128, 20)`；`.transpose(1, 2)` → `(8, 20, 128)`，即 `(batch, 时间, 特征)`，符合 `batch_first=True` 的 LSTM 输入。
   - `h`：双向 LSTM，每个方向 128 维拼接 → `(8, 20, 256)`。
   - `self.head(h)` → `(8, 20, 37)`；`.transpose(0, 1)` → `(20, 8, 37)`；`log_softmax(dim=-1)` 形状不变。
2. 高度是 **2**（32 / 2⁴ = 2），并没有被池化到 1。`f.mean(dim=2)` 对剩下的高度方向取平均，把每一列压成一个 128 维向量——这一步才真正把二维特征图变成一维序列。（讲义里"the CNN max-pools height to 1"的说法不够准确，严格说是池化到 2 再平均。）
3. `F.ctc_loss` 要求 `log_probs` 的布局是 `(T, N, C)`——时间维在最前，这是 PyTorch CTC 接口的约定；`greedy_ctc_decode` 也按这个布局写，内部再 `transpose(0, 1)` 回 `(N, T)` 逐样本处理。

### Q9 — 参考答案

1. **三个预测一定完全相同，最多只有 1 个 `ok`。** `shade = 0.0 if c.isalnum() else 0.5`：所有字母和数字都被画成**同一个黑色矩形**，图像里只有"有几个字符"的信息。三个测试串长度都是 4，经 `build_batch(..., max_len=5)` 后都是"4 个黑块 + 右侧 16 像素白边"，像素逐一相等（可以用 `np.array_equal` 验证）。`model.eval()` 后 BatchNorm 使用滑动统计量，网络是确定性函数，相同输入必然得到相同输出。`"abc7"` 和 `"abc2"` 不可能同时正确，`"xy45"` 也不可能与它们同时正确。
2. **损失不可能降到 0.2。** 训练集 20 个字符串中有 19 个长度为 4，它们的图像完全相同，却对应 19 个不同标签。对同一个输入，任何模型的期望负对数似然都 ≥ 标签分布的熵 `ln 19 ≈ 2.94`；`reduction="mean"` 会再除以目标长度 4，所以这部分样本的损失下界约 `2.94 / 4 ≈ 0.74`。而且 CTC 假设各帧条件独立，无法表达"首字母是 a 时第二个字母一定是 b"这种相关性，实际平台期还会更高。模型能学到的只是"长度"和各位置字符的边缘分布（以及唯一的 5 字符串 `"xy910"`）。
3. 一种改法：给每个字符一个固定的随机二值"字形"，同字符外观一致、不同字符可区分：

```python
import numpy as np

_GLYPH_CACHE = {}


def glyph(c, h=20, w=12):
    if c not in _GLYPH_CACHE:
        g = np.random.default_rng(ord(c)).random((h, w)) > 0.5   # 用字符编码作种子，保证可复现
        _GLYPH_CACHE[c] = np.where(g, 0.0, 1.0).astype(np.float32)
    return _GLYPH_CACHE[c]


def synthetic_line(text, height=32, char_width=16):
    W = char_width * max(1, len(text))
    img = np.ones((height, W), dtype=np.float32)
    for i, c in enumerate(text):
        x = i * char_width
        img[6:height - 6, x + 2:x + char_width - 2] = glyph(c)   # 20×12 的字形块
    return img
```

更真实的做法是用 PIL 的 `ImageDraw.text` 配合多种字体渲染，再加噪声、模糊、旋转（讲义："A real OCR dataset adds fonts, noise, rotation, blur, and colour"）。教训：**先确认数据里有可学的信号**，再去调模型。

### Q10 — 参考答案

1. 下标对照：`h=18, e=15, l=22, o=25`，`0` 是 blank。
   - `[18, 18, 0, 15, 22, 22, 0, 22, 25, 25, 0]`：合并重复 → `18, 0, 15, 22, 0, 22, 25, 0` → 删 blank → `18, 15, 22, 22, 25` → `"hello"`。
   - `[18, 15, 22, 22, 22, 25]`：三个连续 22 没有 blank 隔开，合并成一个 → `18, 15, 22, 25` → `"helo"`。
   - 注意 `greedy_ctc_decode` 的实现方式：`prev` 无论当前是不是 blank 都会更新，所以"blank 之后再出现同一字符"会被当成新字符保留——这正是合并规则要求的行为。

2. 参考实现：

```python
def levenshtein(a, b):
    prev = list(range(len(b) + 1))                 # 空串 → b[:j] 需要 j 次插入
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cur[j] = min(prev[j] + 1,              # 删除
                         cur[j - 1] + 1,           # 插入
                         prev[j - 1] + (ca != cb)) # 替换（相同则 0）
        prev = cur
    return prev[-1]


def cer(ref: str, hyp: str) -> float:
    if not ref:
        return float(len(hyp) > 0)
    return levenshtein(ref, hyp) / len(ref)


print(cer("hello", "helo"))   # 0.2
print(cer("abc7", "abc2"))    # 0.25
```

只保留两行 DP，空间 O(|b|)、时间 O(|a|·|b|)。WER 只需把字符串先 `split()` 成词列表再算同样的距离。

### Q11 — 参考回答要点

- **问题**：序列识别中输入（T 帧特征）与输出（L 个字符）长度不同且没有对齐标注。
- **做法**：词表加一个 blank；定义化简映射 B（合并相邻重复 → 删除 blank）；似然 `P(y|x) = Σ_{π: B(π)=y} Π_t p(π_t | x)`。
- **blank 的作用**：①表示"这一帧没有字符"（字符之间的空隙、字符的过渡帧）；②隔开相邻相同字符，使 "ll" 可以被表示。
- **高效计算**：路径数随 T 指数增长，不能枚举。用前向-后向动态规划：把目标扩展为 `_ y1 _ y2 _ … yL _`（长度 2L+1），在这个扩展序列上递推 α，复杂度 O(T·L)。PyTorch 的 `F.ctc_loss` 有现成实现（GPU 上可用 cuDNN）。
- **假设与局限**：①**帧间条件独立**——给定输入，各帧输出相互独立，没有显式语言模型，需要时在解码阶段外挂 LM（beam search + LM）；②要求 T ≥ L + 重复数，单调对齐，不适合需要重排序的任务；③输出峰值化（spiky），大多数帧输出 blank。
- **加分点**：CTC 同样是语音识别（ASR）的经典损失；端到端的 attention 解码器（TrOCR、Donut）不需要 CTC，但可能出现漏字、重复等对齐错误，所以也有 CTC + attention 联合训练的做法。

### Q12 — 参考回答要点

- **为什么压高度、保留宽度**：横排文本行的阅读方向是水平的，宽度天然对应"时间"。高度方向只需要汇总成"这一列是什么笔画"的特征；宽度方向尽量少下采样，以便有足够的时间步。本节代码前两次池化 2×2，后两次只压高度 `(2, 1)`，32 像素高的行最后剩 2，再在高度上取平均。
- **约束**：T = W / 宽度下采样倍数（本节 80 / 4 = 20）。需要 T ≥ L + 相邻重复数；实践中每个字符最好对应 ≥ 2–4 帧，字符太窄（或下采样太多）会导致 CTC 无解或识别吃字。输入通常缩放到固定高度、按比例保持宽度，宽度可变。
- **BiLSTM 的作用**：单个时间步的感受野有限，双向 LSTM 让每一帧看到左右上下文（如判断 "rn" 还是 "m"）。现代实现常换成 Transformer 编码器。
- **大字符集问题**：中文常用字 6000+，输出层 softmax 变大、长尾字样本少、易混字多；解决方案包括大规模合成数据（多字体渲染）、字典/语言模型约束解码、按频率平衡采样。竖排文本还需要先判断方向并旋转。
- **常见误区**：认为"高度一定被池化到 1"——很多实现（包括本节）是池化到小高度后再平均或展平。

### Q13 — 参考回答要点

- **需求拆解**：OCR 准确 + 字段定位 + 语义归类 + 明细行的表格结构 + 规范化（日期格式、金额小数点）。
- **方案对比**：
  - 流水线：PaddleOCR 检测识别 → 版面/KV 模型（LayoutLMv3 一类）→ 规则后处理。可解释、每段可单独调优，但误差累积，新版式要改规则。
  - 端到端：微调 Donut 或 VLM，直接输出 JSON。讲义观点：版式重复的收据/发票/表单适合微调 Donut；任意文档或需要推理的场景以 VLM 为当前默认。
  - 实务：先用 PaddleOCR + 简单规则做基线，再用几百到几千张标注样本微调端到端模型对比。
- **评测**：字段级 F1（字段名和值都对才算对）、金额做精确匹配；明细行用行级匹配 F1；整体可用 JSON 的归一化树编辑距离；CER 只作为诊断指标。
- **上线**：置信度阈值 + 人工复核队列；业务规则校验（明细之和 = 总额、日期合法）；记录纠错数据回流训练；版式漂移监控。
- **加分点**：金额这类"错一位就出事"的字段，用两套系统交叉校验（端到端结果与 OCR 文本里能否找到同一字符串）。

### Q14 — 参考回答要点

- **定位**：单行准确说明检测和识别没问题，问题在**版面解析 / 阅读顺序**。用可视化把检测框和输出顺序画出来确认。
- **原因**：朴素的"从上到下、从左到右"排序在多栏、表格、合并单元格、页眉页脚混排时会把不同列的行交错拼接（讲义：阅读顺序对拉丁文简单，对混合版式并不简单）。
- **解决**：
  1. 先跑版面检测（LayoutLMv3、在 DocLayNet 上训练的检测器）区分 Title / Paragraph / Table / Figure / Footnote，再"按区域顺序遍历、区域内排序后拼接"；
  2. 表格单独走表格结构识别（行列、单元格），输出 HTML/Markdown/CSV 而不是纯文本；
  3. 复杂版面考虑 Donut 或 VLM 直接输出结构化结果。
- **评测**：为阅读顺序和表格结构单独建测试集与指标，不要只看 CER。

### Q15 — 参考回答要点

- **新风险**：
  - **幻觉**：VLM 是生成式解码，看不清时会"脑补"出看起来合理的文字（例如补全金额、改写人名），而 CTC 模型通常只会输出错字或漏字，错误更"诚实"；
  - 输出不可控：格式漂移、自动"纠正"原文错别字、翻译或总结原文；
  - 成本与延迟高，长文档受上下文长度限制；
  - 缺少逐字符置信度和精确位置（取决于模型是否支持 grounding）。
- **控制手段**：约束输出格式（JSON schema / 受限解码）；要求同时输出坐标，并与传统 OCR 的结果交叉验证；对关键字段做业务规则校验；低置信或不一致时转人工；保留传统 OCR 作为兜底与比对基线；建立覆盖模糊、遮挡、手写的回归测试集。
- **加分点**：指出评测要包含"图里没有该字段"的负样本——检验模型是否会编造。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 06 物体检测——从头开始的 YOLO](../../06-object-detection-yolo/docs/zh.md)：文本检测本质上是检测问题（框/四边形）。
- [阶段 04 · 02 从零实现卷积](../../02-convolutions-from-scratch/docs/zh.md)：CRNN 的 CNN 部分、池化对特征图尺寸的影响。
- [阶段 05 · 08 用于文本的 CNN 和 RNN](../../../05-nlp-foundations-to-advanced/08-cnns-rnns-for-text/docs/zh.md)：LSTM / 双向 RNN。
- [阶段 07 · 02 从零实现 self-attention](../../../07-transformers-deep-dive/02-self-attention-from-scratch/docs/zh.md)：TrOCR、Donut 的 Transformer 解码器。

### 本节被哪些后续内容用到
- [阶段 06 · 04 语音识别 ASR](../../../06-speech-and-audio/04-speech-recognition-asr/docs/zh.md)：CTC 在语音识别中的同款用法。
- [阶段 04 · 25 Vision-Language Models](../../25-vision-language-models/docs/zh.md)：VLM-OCR 背后的 ViT-MLP-LLM 结构。
- [阶段 12 · 22 文档与图表理解](../../../12-multimodal-ai/22-document-diagram-understanding/docs/zh.md)：多模态模型做文档理解的进阶。
- [阶段 12 · 23 ColPali 视觉原生 RAG](../../../12-multimodal-ai/23-colpali-vision-native-rag/docs/zh.md)：跳过 OCR、直接对页面图像做检索。
- [阶段 11 · 03 结构化输出](../../../11-llm-engineering/03-structured-outputs/docs/zh.md)：让 VLM 稳定输出 JSON 字段。
- [阶段 19 · 04 多模态文档问答](../../../19-capstone-projects/04-multimodal-document-qa/docs/zh.md)：综合项目中的文档解析环节。

### 延伸关键词
`DBNet / EAST / CRAFT` · `CRNN` · `CTC forward-backward` · `CTC beam search + LM` · `TrOCR` · `Donut` · `LayoutLMv3` · `DocLayNet` · `PaddleOCR / EasyOCR / Tesseract` · `CER / WER` · `tree edit distance` · `table structure recognition`
