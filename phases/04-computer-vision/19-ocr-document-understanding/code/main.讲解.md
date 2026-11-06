# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 19 节 OCR 和文档理解 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，全程 CPU） ｜ **依赖**：`numpy`、`torch`（`torch.nn`、`torch.nn.functional`）；无需联网、无需预训练权重

---

## 1. 这份代码在考察什么

这是经典 OCR 流水线里"识别"这一环的最小可运行版本：**CRNN + CTC**。它想让你亲手摸清：

1. **CRNN 的形状魔法**：CNN 如何把一张"高 32 × 宽 80"的文本行图变成长度为 20 的特征序列，宽度为什么就是时间轴。
2. **CTC 损失怎么调用**：`(T, N, C)` 的 log 概率布局、拼接式 targets、`input_lengths` / `target_lengths`、blank 下标、`zero_infinity`。
3. **贪心 CTC 解码**：逐帧 argmax → 合并相邻重复 → 删除 blank。
4. **合成数据的端到端冒烟测试**：从"渲染图像"到"训练"再到"解码对比"走通一遍。
5. **（隐藏考点）数据可学性**：本文件的合成数据把所有字母数字都画成同一个黑块，导致任务从信息论上就"不可学"——这是一个非常值得在面试里讲的调试教训（见 3.5 节）。

> 一句话：**CRNN 负责"把图变成序列"，CTC 负责"在没有对齐标注的情况下训练这个序列"**；读懂这 110 行，PaddleOCR 识别模型的骨架就清楚了。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `VOCAB` | 模块级常量 | `"_"`（blank，下标 0）+ 10 个数字 + 26 个小写字母，共 37 项 | 词表、blank |
| `ctc_loss(...)` | 函数 | 包一层 `F.ctc_loss`，固定 `reduction="mean"`、`zero_infinity=True` | CTC 损失 |
| `greedy_ctc_decode(log_probs, blank=0)` | 函数 | argmax → 合并重复 → 删 blank，返回下标列表 | 贪心 CTC 解码 |
| `TinyCRNN` | `nn.Module` 类 | 4 段 Conv-BN-ReLU-Pool + 双向 LSTM + 线性头 | CRNN |
| `synthetic_line(text)` | 函数 | 用 NumPy 画一行"字符块"图像 | 合成 OCR 数据 |
| `build_batch(strings, max_len)` | 函数 | 拼 batch 图像、拼接式 targets、目标长度 | CTC 的输入格式 |
| `decode_to_str(ids)` | 函数 | 下标列表 → 字符串 | 解码后处理 |
| `main()` | 演示入口 | 训练 200 步，测试 3 个字符串并逐个比对 | 端到端冒烟测试 |

数据流：`build_batch` → 图像 `(N,1,32,80)` → `TinyCRNN` → `log_probs (20, N, 37)` → 训练时进 `ctc_loss`，推理时进 `greedy_ctc_decode` → `decode_to_str`。

---

## 3. 逐段精讲

### 3.1 词表与 CTC 损失封装

```python
VOCAB = ["_"] + list("0123456789abcdefghijklmnopqrstuvwxyz")


def ctc_loss(log_probs, targets, input_lengths, target_lengths, blank=0):
    return F.ctc_loss(log_probs, targets, input_lengths, target_lengths,
                      blank=blank, reduction="mean", zero_infinity=True)
```

- `list("0123…z")` 把字符串拆成单字符列表，前面拼上 `"_"` 作为 blank。**blank 放在下标 0** 是 PyTorch `F.ctc_loss` 的默认约定（`blank=0`），代码里也一路显式传 `blank=0`。
- `F.ctc_loss` 的四个张量参数：
  - `log_probs`：`(T, N, C)`，**时间维在最前**，且必须是 `log_softmax` 之后的值；
  - `targets`：这里用的是**拼接式 1 维格式**——把 batch 里所有目标下标首尾相接成一个长向量（`build_batch` 里用 `extend` 拼出来），配合 `target_lengths` 切分；PyTorch 也接受 `(N, S)` 的填充格式；
  - `input_lengths`：每个样本实际使用的时间步数；
  - `target_lengths`：每个样本的目标长度。
- `reduction="mean"`：每个样本的损失先**除以自己的目标长度**，再对 batch 取平均。所以打印出来的损失是"每字符"量级的。
- `zero_infinity=True`：当某样本 T < 目标长度 + 相邻重复字符数时没有合法对齐，损失为 inf；这个开关把它和它的梯度置零，防止一个坏样本把整批变成 NaN。
- 讲义提到 `F.ctc_loss` 在可用时会走 cuDNN 的高效实现；本脚本在 CPU 上跑，用的是 PyTorch 自带的实现。

### 3.2 贪心 CTC 解码

```python
def greedy_ctc_decode(log_probs, blank=0):
    preds = log_probs.argmax(dim=-1).transpose(0, 1).cpu().tolist()
    out = []
    for seq in preds:
        decoded = []
        prev = None
        for idx in seq:
            if idx != prev and idx != blank:
                decoded.append(idx)
            prev = idx
        out.append(decoded)
    return out
```

- `argmax(dim=-1)`：每一帧取概率最大的字符 → `(T, N)`；`.transpose(0, 1)` → `(N, T)`，方便逐样本遍历；`.cpu().tolist()` 转成纯 Python 嵌套列表。
- 核心判断 `idx != prev and idx != blank` 一行同时完成两件事：
  - `idx != prev`：与上一帧相同就跳过 → **合并相邻重复**；
  - `idx != blank`：blank 不输出 → **删除 blank**。
- 精妙之处在 `prev = idx` **无条件更新**（包括 blank）：所以 `l _ l` 中第二个 `l` 的前一帧是 blank，不等于 `l`，会被保留——这就是 blank 能"隔开重复字符"的实现。
- `prev = None` 是哨兵值，保证第一帧的字符一定和"上一帧"不同。
- 讲义："The greedy decoder is simpler than a beam search and usually within 1% CER of it." ⚠️ 贪心解码求的是"最可能的**路径**"再化简，而不是"最可能的**文本**"（后者要对多条路径求和），beam search 更接近后者。

### 3.3 `TinyCRNN`：把图像变成序列

```python
class TinyCRNN(nn.Module):
    def __init__(self, vocab_size=len(VOCAB), hidden=128, feat=32):
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv2d(1, feat, 3, 1, 1), nn.BatchNorm2d(feat), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(feat, feat * 2, 3, 1, 1), nn.BatchNorm2d(feat * 2), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Conv2d(feat * 2, feat * 4, 3, 1, 1), nn.BatchNorm2d(feat * 4), nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 1)),
            nn.Conv2d(feat * 4, feat * 4, 3, 1, 1), nn.BatchNorm2d(feat * 4), nn.ReLU(inplace=True),
            nn.MaxPool2d((2, 1)),
        )
        self.rnn = nn.LSTM(feat * 4, hidden, bidirectional=True, batch_first=True)
        self.head = nn.Linear(hidden * 2, vocab_size)
```

逐层跟踪输入 `(N, 1, 32, 80)`：

| 层 | 输出形状 `(N, C, H, W)` | 说明 |
|----|------------------------|------|
| Conv 3×3 (pad 1) → BN → ReLU | `(N, 32, 32, 80)` | 卷积不改变尺寸 |
| `MaxPool2d(2)` | `(N, 32, 16, 40)` | 高宽都减半 |
| Conv → BN → ReLU | `(N, 64, 16, 40)` | |
| `MaxPool2d(2)` | `(N, 64, 8, 20)` | 高宽都减半 |
| Conv → BN → ReLU | `(N, 128, 8, 20)` | |
| `MaxPool2d((2, 1))` | `(N, 128, 4, 20)` | **只压高度，不压宽度** |
| Conv → BN → ReLU | `(N, 128, 4, 20)` | |
| `MaxPool2d((2, 1))` | `(N, 128, 2, 20)` | 只压高度 |

- **为什么后两次池化是 `(2, 1)`**：宽度就是 CTC 的时间轴，再压就只剩 10 帧甚至 5 帧，一个字符（16 像素宽）只能分到 1 帧左右，遇到相邻重复字符时连插 blank 的位置都没有。所以经典 CRNN 都是"高度狠压、宽度少压"。
- `Conv2d(1, feat, 3, 1, 1)` 的位置参数依次是 `in_channels, out_channels, kernel_size, stride, padding`。
- `BatchNorm2d`：稳定训练；⚠️ 这意味着推理前**必须 `model.eval()`**，否则 BN 会用当前 batch 的统计量。
- `ReLU(inplace=True)`：原地修改，省一点内存。
- `nn.LSTM(128, 128, bidirectional=True, batch_first=True)`：输入每帧 128 维，每个方向隐状态 128 维，双向拼接后 256 维，所以线性头是 `Linear(256, 37)`。`batch_first=True` 表示输入布局为 `(N, T, C)`。
- 默认参数 `vocab_size=len(VOCAB)` 在**函数定义时**求值（= 37），这在这里没问题，但要知道这个时机（见第 5 节）。
- 参数量（确定值，按层公式计算）：CNN 240,960 + LSTM 264,192 + 线性头 9,509 = **514,661**。BN 的 running mean/var 是 buffer，不计入 `parameters()`。

### 3.4 `forward`：从特征图到 `(T, N, C)`

```python
    def forward(self, x):
        f = self.cnn(x)
        f = f.mean(dim=2).transpose(1, 2)
        h, _ = self.rnn(f)
        return F.log_softmax(self.head(h).transpose(0, 1), dim=-1)
```

- `self.cnn(x)` → `(N, 128, 2, 20)`。⚠️ 注意高度是 **2 而不是 1**（32 / 2⁴ = 2）；讲义说 "the CNN max-pools height to 1" 并不准确，真正把高度压没的是下一行的 `mean(dim=2)`。
- `f.mean(dim=2)` → `(N, 128, 20)`：在高度方向取平均，每一列变成一个 128 维向量；`.transpose(1, 2)` → `(N, 20, 128)`，成为 LSTM 需要的 `(batch, 时间, 特征)`。
- `h, _ = self.rnn(f)`：LSTM 返回 `(输出序列, (h_n, c_n))`，这里只要每一帧的输出 `h (N, 20, 256)`，最终状态丢弃。双向 LSTM 让每一帧都能看到整行的左右上下文。
- `self.head(h)` → `(N, 20, 37)`，`.transpose(0, 1)` → `(20, N, 37)`，满足 CTC 要求的时间维在前；`log_softmax(dim=-1)` 在词表维度上归一化成 log 概率。
- 用 `log_softmax` 而不是先 `softmax` 再 `log`：数值更稳定，且 CTC 内部全在 log 空间做 logsumexp。

### 3.5 合成数据：渲染与打包（以及一个致命缺陷）

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

- 白底（1.0），每个字符占 16 像素宽的格子，在格子中间画一个 20×12 的块：字母数字为黑色 0.0，其他字符为灰色 0.5。`max(1, len(text))` 防止空串得到宽度 0 的图。
- ⚠️ **致命缺陷**：所有字母和数字画出来是**完全相同的黑块**。图像里唯一的信息是"有几个字符"（以及标点的位置）。`"abc7"`、`"xy45"`、`"abc2"` 三张图逐像素相等（我用 NumPy 单独抽出这两个函数验证过：`np.array_equal` 为 `True`）。后果：
  - 模型从信息论上**不可能**区分同长度的字符串，`main()` 里三个测试样本的预测**必然完全相同**，最多 1 个 `ok`；
  - 训练集 20 个字符串里有 19 个长度为 4、图像相同但标签不同，损失有下界（约 `ln 19 / 4 ≈ 0.74`，CTC 的帧间独立假设会让实际值更高），讲义所说"降到约 0.2"在这份数据上做不到。
  - 修复思路：给每个字符一个可区分的字形（例如以字符编码为种子的随机二值图案，或用 PIL 按真实字体渲染），见测验 Q9。

```python
def build_batch(strings, max_len=None):
    H = 32
    max_len = max_len or max(len(s) for s in strings)
    W = 16 * max_len
    imgs = np.ones((len(strings), 1, H, W), dtype=np.float32)
    targets = []
    target_lengths = []
    for i, s in enumerate(strings):
        line = synthetic_line(s)
        imgs[i, 0, :, :line.shape[1]] = line
        ids = [VOCAB.index(c) for c in s]
        targets.extend(ids)
        target_lengths.append(len(ids))
    return torch.from_numpy(imgs), torch.tensor(targets, dtype=torch.long), torch.tensor(target_lengths, dtype=torch.long)
```

- `max_len = max_len or max(...)`：没传就用本 batch 最长串。`main()` 固定传 `max_len=5`，保证训练和测试的图像宽度都是 80、T 都是 20（训练集里有一个 5 字符的 `"xy910"`）。
- 较短的串只填左边 `line.shape[1]` 列，右边保持白色——相当于右侧 padding，模型应该在这些帧输出 blank。
- `targets.extend(ids)` 而不是 `append`：把下标"摊平"接到末尾，构成拼接式 1 维 targets；`target_lengths` 负责记录每段多长。
- `VOCAB.index(c)` 是 O(|V|) 的线性查找，词表 37 项无所谓；大词表应预建 `dict`。⚠️ 遇到词表外字符（如大写字母、空格）会抛 `ValueError`。
- `torch.from_numpy(imgs)` 与 NumPy 数组共享内存（零拷贝）；`torch.tensor(..., dtype=torch.long)` 从列表新建整型张量，CTC 要求 targets 和长度是整数。

### 3.6 训练循环

```python
    train_strings = [f"abc{d}" for d in range(10)] + [f"xy{d}{d+1}" for d in range(10)]
    for step in range(200):
        idx = np.random.choice(len(train_strings), 8)
        strings = [train_strings[i] for i in idx]
        imgs, targets, target_lens = build_batch(strings, max_len=5)
        log_probs = model(imgs)
        input_lens = torch.full((imgs.size(0),), log_probs.size(0), dtype=torch.long)
        loss = ctc_loss(log_probs, targets, input_lens, target_lens, blank=0)
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 40 == 0:
            print(f"step {step:3d}  loss {loss.item():.3f}")
```

- 训练集：`abc0`…`abc9` 和 `xy01`、`xy12`…`xy89`、`xy910`（注意最后一个是 5 个字符）。相邻字符都不重复，所以 T = 20 远大于 CTC 的最低要求。
- `np.random.choice(20, 8)` 默认**有放回**地抽 8 个下标。⚠️ 它用的是 NumPy 的全局随机数，而代码只设置了 `torch.manual_seed(0)`，所以每次运行抽到的 batch 不同、日志数值也不可复现；要复现需加 `np.random.seed(...)`。
- `input_lens` 用 `torch.full` 把每个样本的输入长度都设为 T = 20：所有图都 padding 到同宽，直接用满长度。
- 每 40 步打印一次：step 0、40、80、120、160，共 5 行。

### 3.7 推理与比对

```python
    model.eval()
    test_strings = ["abc7", "xy45", "abc2"]
    imgs, _, _ = build_batch(test_strings, max_len=5)
    with torch.no_grad():
        log_probs = model(imgs)
    preds = [decode_to_str(ids) for ids in greedy_ctc_decode(log_probs)]
    for target, pred in zip(test_strings, preds):
        match = "ok" if target == pred else "diff"
        print(f"  target {target!r:10s} -> pred {pred!r:10s}  {match}")
```

- `model.eval()`：BN 改用训练中累计的滑动均值/方差。忘记这一步，推理结果会随 batch 组成变化。
- `with torch.no_grad()`：推理不建计算图。
- 三个测试串都在训练集里出现过，这只是"冒烟测试"，不是泛化测试。而由于 3.5 节的缺陷，三行的 `pred` 一定相同。
- `{target!r:10s}`：先 `repr()` 加上引号，再左对齐填充到 10 个字符宽，让输出列对齐。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 后两次池化 `(2, 1)` | 保住宽度方向的时间步，给 CTC 足够的帧 | 生产中按字符宽度和最长文本设计下采样倍数 |
| 高度池化到 2 再 `mean` | 简单地把二维特征压成序列 | 也可展平高度维（`C×H'`）再接线性层，保留更多竖向信息 |
| BiLSTM | 每帧获得整行上下文 | 现代实现常用 Transformer 编码器或纯卷积序列模型 |
| 拼接式 targets | 不需要 padding，`F.ctc_loss` 原生支持 | 需同步维护 `target_lengths` |
| `zero_infinity=True` | 防止个别不可对齐样本让训练 NaN | 会"静默"跳过坏样本，应统计并清洗这类数据 |
| 贪心解码 | 简单快速，干净文本上与 beam search 差距小 | 噪声输入或需要语言模型时用 beam search（+LM） |
| 色块代替字形的合成数据 | 代码极短，不依赖字体文件 | 任务不可学；真实合成数据需要字体渲染 + 噪声/模糊/旋转增强 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表拼接 + `list(str)` | `["_"] + list("0123…z")` | `list` 把字符串拆成字符列表 |
| 默认参数在定义时求值 | `def __init__(self, vocab_size=len(VOCAB), ...)` | `len(VOCAB)` 在 `class` 定义执行时就算好了；之后再改 `VOCAB` 不会影响默认值 |
| `or` 提供默认值 | `max_len = max_len or max(len(s) for s in strings)` | `None`（以及 0）为假时取右边；注意 0 也会被替换 |
| 条件表达式 | `shade = 0.0 if c.isalnum() else 0.5`、`"ok" if target == pred else "diff"` | 一行 if-else |
| `str.isalnum()` | `c.isalnum()` | 是否为字母或数字 |
| `enumerate` | `for i, c in enumerate(text)` | 同时拿到下标和元素 |
| `append` vs `extend` | `targets.extend(ids)`、`target_lengths.append(len(ids))` | `extend` 把列表元素逐个加入；`append` 把整个对象作为一个元素加入 |
| `None` 哨兵 | `prev = None` | 表示"还没有上一帧" |
| 元组解包与 `_` | `h, _ = self.rnn(f)`、`imgs, _, _ = build_batch(...)` | 丢弃不需要的返回值 |
| 列表推导 / 生成器表达式 | `[VOCAB.index(c) for c in s]`、`"".join(VOCAB[i] for i in ids)` | `join` 直接接收生成器，拼接字符串 |
| `with` 上下文管理器 | `with torch.no_grad():` | 进入时关闭梯度记录，退出时自动恢复 |
| f-string 格式符 | `{sum(...):,}`、`{step:3d}`、`{loss.item():.3f}`、`{target!r:10s}` | `:,` 千分位；`!r` 先取 `repr`；`:10s` 填充到宽度 10 |
| NumPy 切片赋值 | `img[6:height - 6, x + 2:x + char_width - 2] = shade` | 二维切片一次性给矩形区域赋值（广播标量） |
| `np.random.choice` | `np.random.choice(len(train_strings), 8)` | 从 `range(20)` 中有放回抽 8 个 |
| NumPy ↔ PyTorch | `torch.from_numpy(imgs)`、`.cpu().tolist()` | 零拷贝转张量；张量转 Python 列表 |
| 一行多语句 | `opt.zero_grad(); loss.backward(); opt.step()` | 分号分隔，等价于三行 |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 数据生成部分只依赖 NumPy，我已单独抽出 `synthetic_line` / 打包逻辑在临时目录运行，确认三张测试图像逐像素相同、图像形状为 `(3, 1, 32, 80)`；CTC 的数值用 NumPy 写的前向算法核对。根据代码可以推出的输出如下：

```text
params: 514,661
step   0  loss ?.???
step  40  loss ?.???
step  80  loss ?.???
step 120  loss ?.???
step 160  loss ?.???
  target 'abc7'     -> pred <P>  ...
  target 'xy45'     -> pred <P>  ...
  target 'abc2'     -> pred <P>  ...
```

- `params: 514,661` 是由层结构决定的确定值（CNN 240,960 + LSTM 264,192 + 线性头 9,509）。
- **step 0 的损失**：随机初始化时输出接近均匀分布。若每帧都是 `1/37`，用 CTC 前向算法算出长度 4 目标在 T = 20 下的负对数似然约 58.7，除以目标长度后约 **14.7**；5 字符的 `"xy910"` 约 11.4。所以第一行损失应在 10 以上的量级（讲义说"从约 3 开始"，与 `reduction="mean"` 下的这个量级不符）。
- **后续损失**：CTC 模型通常很快学会"大部分帧输出 blank"，损失迅速下降；但由于所有同长度字符串的图像相同，损失会停在一个明显大于 0 的平台（理论下界约 0.74，实际更高），不会到 0.2。因为 `np.random.choice` 未设种子，每次运行的数值也会不同。
- **测试三行**：三个 `pred` 必然是**同一个字符串** `<P>`，因此至少两行是 `diff`。模型最可能学到的是各位置最常见的字符（如 `a`、`b`、`c` 开头，第 4 位是某个数字），但具体是什么需实际运行确认。看到这个结果不要以为是模型或训练出了问题——是数据本身没有可学的信号。

---

## 7. 动手改一改

1. **修复数据**：按测验 Q9 的思路给每个字符一个固定的随机字形，重新训练，观察损失能否降到 0.2 附近、三个测试串能否全部 `ok`。
2. **可复现性**：在 `main()` 开头加 `np.random.seed(0)`，连续运行两次，确认日志完全一致。
3. **时间步消融**：把第二个 `MaxPool2d(2)` 改成 `MaxPool2d((2, 1))`（T 变为 40）或把第三个改成 `MaxPool2d(2)`（T 变为 10），比较收敛速度；思考 T = 5 时会发生什么（提示：`zero_infinity`）。
4. **实现 CER 评测**：写 `levenshtein` 和 `cer`，在修复后的数据上用 100 个随机 5 位数字串作为测试集，报告 CER（讲义练习 1）。
5. **Beam search**：参考 `outputs/skill-ctc-decoder.md` 实现 beam_width = 5 的前缀 beam search，比较与贪心解码的 CER 差异（讲义练习 2）。
6. **换掉 BiLSTM**：用 `nn.TransformerEncoder`（加位置编码）替换 LSTM，对比参数量与效果。

---

## 8. 常见坑

- **`log_probs` 布局写错**：`F.ctc_loss` 要 `(T, N, C)`，传成 `(N, T, C)` 不一定报错，但训练出来全是垃圾。
- **传了 softmax 概率而不是 log 概率**：`F.ctc_loss` 期望 `log_softmax` 的输出。
- **T 太短**：下采样过多，T < 目标长度 + 相邻重复数，损失为 inf；开了 `zero_infinity` 会被静默置 0，看起来"损失很低"其实是样本被丢了。
- **推理忘了 `model.eval()`**：BN 用当前 batch 统计量，单张图推理结果飘忽。
- **blank 下标不一致**：训练用 `blank=0`，解码却把 0 当普通字符，或词表第 0 位放了真实字符。
- **合成数据没有信号**：就像本文件的色块渲染——先可视化几张样本、确认"人眼能区分"，再开始训练。
