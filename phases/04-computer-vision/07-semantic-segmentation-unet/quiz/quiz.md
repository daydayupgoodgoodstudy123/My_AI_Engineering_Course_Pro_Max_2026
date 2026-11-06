# 测验 · 语义分割——U-Net（Semantic Segmentation — U-Net）

> **阶段 04 · 计算机视觉 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过（或读懂）代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 语义 / 实例 / 全景分割 | 语义：像素 → 类别（同类相邻目标糊成一团）；实例：像素 → 目标 id（只管前景 things）；全景：每个像素都有类别，每个 thing 还有 id |
| 2 | U-Net 形状 | 编码器 4 次下采样（分辨率 ÷2、通道 ×2），瓶颈在 H/16，解码器对称地 4 次上采样，最后 1×1 卷积输出 `num_classes` 通道 |
| 3 | Skip connection | 把同分辨率的编码器特征 **concat** 到解码器上，补回下采样丢掉的高频细节；没有它边界会糊 |
| 4 | 上采样两种做法 | 转置卷积可学习但 kernel 不能被 stride 整除时会出棋盘格伪影；双线性插值 + 3×3 卷积更平滑、参数更少，是现代默认 |
| 5 | 像素级交叉熵 | logits `(N,C,H,W)` + 整数标签 `(N,H,W)`，`F.cross_entropy` 原生支持，相当于在每个像素上做分类 |
| 6 | Dice loss 与组合损失 | `Dice = 2Σ(p·y) / (Σp + Σy)`，按比例计算，对类别不平衡不敏感；`L = CE + λ·Dice`（λ≈1）是医学/工业默认 |
| 7 | 评估指标 | 像素准确率在不平衡数据上失效；看逐类 IoU 和 mIoU；`Dice = 2·IoU/(1+IoU)`；Boundary F1 衡量边界精度 |
| 8 | 分辨率与显存 | 输入最好能被 16 整除；显存随 `H·W·C` 增长；大图用重叠切块（tiling）或空洞卷积（DeepLab） |

### 核心技能（能动手做到）

- [ ] 从零用 PyTorch 写出 `DoubleConv / Down / Up / UNet`，并能逐层写出 64×64 输入下 `x1…x5` 和输出的形状
- [ ] 手算一个 `DoubleConv(in_c, out_c)` 的参数量，并解释为什么卷积用 `bias=False`
- [ ] 实现 `dice_loss`（softmax + one-hot + `permute`）与 `combined_loss`，说清 `dims=(0,2,3)` 的含义
- [ ] 实现逐类 IoU，并能正确地在整个验证集上累计交集/并集求 mIoU（而不是按 batch 平均）
- [ ] 解释并验证 `Up` 中 `F.interpolate` 如何处理不能被 16 整除的输入尺寸
- [ ] 拿到一组逐类 IoU，能判断问题出在小目标召回、边界精度还是类别不平衡

---

## 二、基础自测（选择题）

**Q1.** 自动驾驶场景要求：天空、道路、植被等每个像素都要有类别，同时每一辆车、每一个行人还要区分出是"第几个"。这属于：

- A. 语义分割
- B. 实例分割
- C. 全景分割（panoptic）
- D. 目标检测

**Q2.** 本节代码中 `UNet(in_channels=3, num_classes=3, base=16)` 的第一个上采样块 `self.u1` 的输入通道数（拼接之后、送进 `DoubleConv` 之前）是：

- A. 256
- B. 384
- C. 128
- D. 512

**Q3.** 一个肿瘤分割任务中 99% 的像素是背景。只用交叉熵训练后像素准确率达到 99%，但肿瘤 mask 几乎全空。最合适的改进组合是：

- A. 增大学习率，继续训练
- B. 改用 `交叉熵 + Dice` 组合损失，并报告前景类的逐类 IoU / Dice
- C. 把评估指标换成 top-5 准确率
- D. 去掉 skip connection，减少过拟合

**Q4.** 某类别的 IoU 为 0.8，那么它的 Dice 系数约为：

- A. 0.64
- B. 0.80
- C. 0.889
- D. 0.90

**Q5.** 关于转置卷积产生棋盘格伪影，下列说法正确的是：

- A. 是 PyTorch 实现的 bug
- B. 当 kernel_size 不能被 stride 整除时（如 kernel 3、stride 2），输出像素收到的输入贡献次数不均匀，形成周期性图案
- C. 只要在转置卷积前加 BatchNorm 就能消除
- D. 是学习率太低导致的

**Q6.** 本节代码里，`F.cross_entropy(logits, targets)` 中 `logits` 的形状是 `(N, C, H, W)`，`targets` 应该是：

- A. `(N, H, W, C)` 的 one-hot float 张量
- B. `(N, H, W)` 的 int64 类别下标
- C. `(N, 1, H, W)` 的 float 张量
- D. `(N, H*W)` 的 float 张量

**Q7.** 把一张 100×100 的图像喂给本节的 `UNet`，结果是：

- A. 在 `torch.cat` 处报尺寸不匹配错误
- B. 输出 96×96
- C. 输出 100×100，因为 `Up` 在拼接前用 `F.interpolate` 把上采样结果对齐到 skip 的尺寸
- D. 输出 112×112

**Q8.** `dice_loss` 里 `dims = (0, 2, 3)`，`inter = (probs * one_hot).sum(dim=dims)`。这意味着 Dice 是：

- A. 在每个像素上单独计算
- B. 对每张图、每个类别分别计算
- C. 对每个类别在**整个 batch 的所有像素**上汇总计算，再对类别取平均（macro Dice）
- D. 把所有类别和所有像素混在一起算一个总 Dice（micro Dice）

---

## 三、动手 / 代码题

**Q9.** `main()` 中 `model = UNet(in_channels=3, num_classes=3, base=16)`，输入 batch 形状 `(8, 3, 64, 64)`。

(a) 写出 `x1, x2, x3, x4, x5` 和最终输出的形状。
(b) 手算 `DoubleConv(3, 16)` 的可训练参数量。
(c) 为什么 `nn.Conv2d(..., bias=False)`？

**Q10.** 下面是 `main()` 中的验证逻辑。训练集 60 张图按 0.85 切分，验证集共 9 张，`batch_size=8`。已知验证集 9 张图的类别依次为 `[2, 1, 2, 1, 1, 1, 2, 1, 1]`（每张图只有一个形状）。请解释：为什么打印出来的"方块（类别 2）IoU"**永远不会超过约 0.5**，即使模型完美？并写一个正确的数据集级 IoU 计算函数。

```python
        iou_sum = torch.zeros(num_classes)
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                iou_sum += iou_per_class(model(x), y, num_classes).nan_to_num(0)
        iou_mean = (iou_sum / len(val_loader)).tolist()
```

**Q11.** 阅读 `dice_loss`：

```python
def dice_loss(logits, targets, num_classes, eps=1e-6):
    probs = F.softmax(logits, dim=1)
    one_hot = F.one_hot(targets, num_classes).permute(0, 3, 1, 2).float()
    dims = (0, 2, 3)
    inter = (probs * one_hot).sum(dim=dims)
    denom = probs.sum(dim=dims) + one_hot.sum(dim=dims)
    dice = (2 * inter + eps) / (denom + eps)
    return 1 - dice.mean()
```

(a) 为什么要 `.permute(0, 3, 1, 2)`？
(b) 如果某个 batch 里**完全没有**类别 2 的像素，类别 2 的 Dice 值大约是多少？这对总损失有什么影响？
(c) 给出一种修改方式。

**Q12.** 讲义 Step 6 说合成数据"在随机颜色背景上画形状，网络必须学形状而不是像素颜色"。但 `main.py` 的 `synthetic_segmentation` 用的是固定颜色：

```python
    circle_color = np.array([0.9, 0.1, 0.1], dtype=np.float32)
    square_color = np.array([0.1, 0.2, 0.9], dtype=np.float32)
    for i in range(num_samples):
        bg = np.array([0.3, 0.7, 0.3], dtype=np.float32)
```

(a) 写一个**不需要训练**的 baseline，证明这份数据只靠颜色就能分对。
(b) 怎样修改生成器，才能真正逼网络学习形状？

---

## 四、面试高频题

**Q13.**（基础必考）画出/描述 U-Net 的结构。skip connection 为什么必不可少？U-Net 用 concat 而 ResNet 用 add，有什么区别？

**Q14.**（原理深挖）Dice loss 和交叉熵各自的优缺点是什么？为什么工业界常用 `CE + Dice` 组合？还有哪些针对类别不平衡的分割损失？

**Q15.**（原理深挖）解释转置卷积的工作方式、输出尺寸公式，以及棋盘格伪影的成因与解决方法。

**Q16.**（工程实践）你要对 8000×8000 的遥感图做建筑物分割，单卡 24 GB 显存。训练和推理分别怎么做？有哪些坑？

**Q17.**（场景设计）工业缺陷分割：缺陷只占 0.5% 的像素。你的模型 mIoU = 0.74，但缺陷类 IoU 只有 0.21。你如何定位问题、如何改进？

---

## 五、参考答案与解析

### Q1 — 答案：C

既要给 stuff（天空、道路）打语义标签，又要给 things（车、人）分实例 id，正是全景分割的定义。A 会把相邻的车糊成一块；B 只处理前景实例，不管天空和道路；D 只输出框，不给像素级轮廓。

### Q2 — 答案：B

`self.u1 = Up(base * 16 + base * 8, base * 8)`，`base=16` 时输入通道为 `256 + 128 = 384`：`x5`（瓶颈，256 通道）上采样后通道数不变，与 skip `x4`（128 通道）在通道维 concat。A 只算了瓶颈；C 只算了 skip；D 是把两者都当成 256。

### Q3 — 答案：B

99% 准确率只说明模型学会了"全部预测背景"。Dice 按比例衡量前景重叠，背景像素再多也"稀释"不了它；CE 提供早期稳定梯度，Dice 在后期专注于形状匹配。评估也必须换成前景类的逐类 IoU / Dice。A 只会让模型更快收敛到"全背景"；C 是分类指标；D 会让边界更差，与不平衡无关。

### Q4 — 答案：C

`Dice = 2·IoU / (1 + IoU) = 1.6 / 1.8 ≈ 0.889`。两者单调相关，Dice 总是 ≥ IoU（在 0 和 1 处相等），所以医学界习惯报 Dice、驾驶界习惯报 IoU 时，数值不能直接比较。A 是 `0.8²`，是常见的误算。

### Q5 — 答案：B

转置卷积相当于"把每个输入像素乘以 kernel 后贴到输出上，stride 决定贴的间隔"。kernel 3、stride 2 时，有的输出位置被两个 kernel 覆盖，有的只被一个覆盖，贡献次数呈周期性不均，就出现棋盘格。解决：用能被 stride 整除的 kernel（如 kernel 4、stride 2），或改用"双线性上采样 + 3×3 卷积"（本节代码的做法）。C、D 都不针对成因。

### Q6 — 答案：B

`F.cross_entropy` 对 `(N,C,H,W)` 的 logits 原生支持形状为 `(N,H,W)`、dtype 为 `long` 的类别下标，代码里 `SegDataset.__getitem__` 正是用 `.long()` 生成标签。A 的维度顺序和类型都不对；C 多了一个通道维（二分类时用 BCE 才会这样）；D 把空间维展平了，不需要。

### Q7 — 答案：C

MaxPool 向下取整：100 → 50 → 25 → 12 → 6。解码时 6 → 12（与 `x4` 的 12 一致）；12 → 24，但 skip `x3` 是 25，尺寸不等，于是 `F.interpolate(x, size=skip.shape[-2:])` 把它拉到 25；25 → 50、50 → 100 都对得上。最终输出 100×100。讲义特意强调只比较 `shape[-2:]`：通道数不等应该大声报错，而不是被插值掩盖。

### Q8 — 答案：C

`probs` 和 `one_hot` 形状都是 `(N, C, H, W)`，在第 0（batch）、2、3（空间）维上求和后得到长度为 C 的向量——每个类别一个 Dice，再 `dice.mean()` 对类别平均，也就是讲义说的 macro Dice。它是 batch 级而非逐图的：一个 batch 内大目标会"淹没"同类的小目标。

### Q9 — 参考答案

(a) 形状（`base=16`）：

| 张量 | 形状 |
|------|------|
| 输入 | `(8, 3, 64, 64)` |
| `x1 = inc(x)` | `(8, 16, 64, 64)` |
| `x2 = d1(x1)` | `(8, 32, 32, 32)` |
| `x3 = d2(x2)` | `(8, 64, 16, 16)` |
| `x4 = d3(x3)` | `(8, 128, 8, 8)` |
| `x5 = d4(x4)` | `(8, 256, 4, 4)` |
| `u1` → `u2` → `u3` → `u4` | `(8,128,8,8)` → `(8,64,16,16)` → `(8,32,32,32)` → `(8,16,64,64)` |
| `outc` 输出 | `(8, 3, 64, 64)` |

(b) `DoubleConv(in_c, out_c)` 参数 = 第一个 conv `9·in_c·out_c` + 第二个 conv `9·out_c²` + 两个 BN 各 `2·out_c`（γ、β）。代入 `(3,16)`：`432 + 2304 + 64 = 2800`。按同样公式把 9 个块加上 `outc`（`16·3 + 3 = 51`）求和，整网为 **1,964,131**，这就是 `main()` 第一行打印的 `params:`。（running_mean/var 是 buffer，不算参数。）

(c) 卷积后紧跟 BatchNorm，BN 会先减去 batch 均值——卷积的偏置是一个常数，会被这一步完全抵消；BN 自己的 β 承担了偏置的作用。加 bias 只会浪费参数。

### Q10 — 参考答案

**原因**：9 张验证图被切成两个 batch：第一个 8 张（两类都有），第二个只有 1 张，类别是 1（圆）。第二个 batch 中没有方块：若模型没有预测出方块，`union = 0` → `nan` → `nan_to_num(0)` 变成 0；若误预测出方块，`inter = 0`，IoU 也是 0。最后 `iou_sum / len(val_loader)` 除以 2，所以方块 IoU ≤ `(1 + 0) / 2 = 0.5`。这是"按 batch 平均 IoU + 把缺席类别当 0"的双重偏差，讲义 Step 7 也提醒了这一点。

**正确做法**：在整个数据集上累计每类的交集与并集，最后再相除。

```python
@torch.no_grad()
def evaluate_iou(model, loader, num_classes, device):
    model.eval()
    inter = torch.zeros(num_classes)
    union = torch.zeros(num_classes)
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        preds = model(x).argmax(dim=1)
        for c in range(num_classes):
            p, t = preds == c, y == c
            inter[c] += (p & t).sum().item()
            union[c] += (p | t).sum().item()
    iou = inter / union              # 某类在整个数据集都没出现过且没被预测 → 0/0 = nan
    return iou, torch.nanmean(iou)   # mIoU 忽略 nan 类
```

要点：①交集/并集是可加的，IoU 不是；②真正缺席的类用 `nan` 标记并在 mIoU 中跳过，而不是当 0；③工业代码通常累计一个 `C×C` 混淆矩阵，一次得到 IoU、Dice、像素准确率。

### Q11 — 参考答案

(a) `F.one_hot` 会在**最后**新增一维，`(N,H,W)` 变成 `(N,H,W,C)`；而 `probs` 是 `(N,C,H,W)`。`permute(0,3,1,2)` 把类别维挪到第 1 维，两者才能逐元素相乘。`.float()` 是因为 one-hot 结果是整型。

(b) 类别 2 缺席时 `one_hot` 那一通道全 0，`inter = 0`；但 softmax 永远不会输出精确的 0，`probs.sum()` 在 `N·H·W` 个像素上累加后是一个明显大于 `eps` 的数。所以 `dice ≈ eps / Σp ≈ 0`，该类对 `1 − dice.mean()` 贡献约 `1/C`（3 类时约 0.333）。用 NumPy 模拟一个 2×64×64、概率均匀 1/3 的 batch，缺席类的 Dice 精确到 4 位就是 `0.0`。影响：①损失里多了一块"只要还有一点概率就不能消掉"的常量，梯度不断把该类概率往 0 压；②不同 batch 的损失大小随"缺了几类"跳变，loss 曲线难读。

(c) 常见改法任选其一：
- 只对 batch 中**出现过**的类取平均：`present = one_hot.sum(dim=dims) > 0`，返回 `1 - dice[present].mean()`；
- 用较大的平滑项（如 `smooth = 1.0`）同时加在分子分母上，使"预测也几乎为 0"时 Dice 接近 1；
- 不把背景类算进 Dice（很多医学分割只对前景算 Dice）。

### Q12 — 参考答案

(a) 一个不用训练的颜色阈值 baseline：

```python
def color_baseline(images):                  # images: (N, H, W, 3)
    pred = np.zeros(images.shape[:3], dtype=np.int64)
    pred[images[..., 0] > 0.6] = 1           # 红通道高 → 圆
    pred[images[..., 2] > 0.6] = 2           # 蓝通道高 → 方
    return pred
```

在 `synthetic_segmentation(num_samples=60, size=64)` 上，三类 IoU 都是 **1.0**（已用 NumPy 实际运行验证）。说明这份数据可以完全不看形状：圆永远是红色、方永远是蓝色、背景永远是绿色，噪声只有 0.02。U-Net 很快拿到高 IoU，并不能证明它学会了"形状"——这是典型的 **shortcut learning（捷径学习）**。

(b) 改法：背景色和形状颜色都随机采样，让颜色与类别无关：

```python
    for i in range(num_samples):
        images[i] = rng.uniform(0, 1, (3,)).astype(np.float32)        # 随机背景
        # ... 选 cls、cx、cy、r、mask 同原代码 ...
        images[i][mask] = rng.uniform(0, 1, (3,)).astype(np.float32)  # 随机前景色
```

还可以按讲义版本在一张图里画 1–3 个形状。改完后再跑 (a) 的颜色 baseline，IoU 应该明显下降，而 U-Net 仍能学好——这才证明网络学的是形状。

### Q13 — 参考回答要点

- **结构**：编码器（收缩路径）由"两个 3×3 conv + BN + ReLU"与 2×2 MaxPool 交替组成，每级分辨率减半、通道翻倍；瓶颈在 H/16；解码器（扩张路径）每级上采样 ×2、与同分辨率的编码器特征 concat、再做两个 3×3 conv；最后 1×1 conv 映射到类别数。整体是 U 形。
- **为什么需要 skip**：下采样换来了大感受野和语义（"这是什么场景"），却丢掉了像素级位置；解码器只从 H/16 的瓶颈出发无法恢复锐利边缘。skip 把编码器在下采样**之前**算好的高分辨率、低语义特征直接送过去，让每一级输出同时拥有上下文和细节。
- **concat vs add**：concat 保留两路特征的全部通道，由后续卷积自己学怎么融合，代价是通道数变大（`base*16 + base*8`）；add 要求通道一致，信息被直接叠加，参数和显存更省，ResNet 的目的是让梯度易于传播（恒等映射），而 U-Net 的目的是把不同层级的信息**并列**交给解码器。FCN 用的就是 add 式融合。
- **加分点**：U-Net 原论文用无 padding 卷积，输出比输入小、需要裁剪 skip（本节代码用 `padding=1` 规避了）；U-Net 结构后来成为 diffusion 去噪网络的骨架（见第 10、11 节）。

### Q14 — 参考回答要点

- **交叉熵**：逐像素独立的分类损失，梯度平滑稳定、早期训练友好；但每个像素权重相同，前景极少时总损失被背景主导。
- **Dice**：直接优化预测与真值的重叠比例，背景像素再多也不影响前景那一项，天然抗不平衡；缺点是梯度在预测很差或目标很小时可能不稳定、震荡，且对"类别缺席"的处理需要小心（见 Q11）。
- **组合**：`CE + λ·Dice`（λ≈1）——CE 负责早期稳定收敛，Dice 负责后期把形状对齐，讲义称之为医学影像的默认配置。
- **其他选项**：带类别权重的 CE、Focal loss（压低易分像素的权重）、Tversky loss（分别加权 FP/FN，适合更在乎召回的场景）、Lovász-Softmax（直接优化 IoU 的凸替代）、Boundary loss（关注边界）。
- **常见误区**：认为"用了 Dice 就不用看指标分布"——依然要报逐类 IoU，并检查小目标召回。

### Q15 — 参考回答要点

- **工作方式**：可以理解为普通卷积的"转置"（反向传播时卷积对输入的梯度就是转置卷积）：每个输入像素乘以整个 kernel，按 stride 间隔"贴"到输出上，重叠处相加。它是**可学习**的上采样。
- **输出尺寸**（dilation=1）：`H_out = (H_in − 1)·stride − 2·padding + kernel_size + output_padding`。例如 kernel 2、stride 2、padding 0：`H_out = 2·H_in`；kernel 4、stride 2、padding 1 也得到 `2·H_in`。
- **棋盘格成因**：kernel 不能被 stride 整除时，输出位置被覆盖的次数不均匀，形成周期性亮暗；即使整除，学到的 kernel 在不同相位上不一致也可能出现纹理。
- **解决**：①kernel 取 stride 的整数倍；②"最近邻/双线性上采样 + 普通卷积"（本节代码 `Up` 的做法）；③PixelShuffle（sub-pixel conv）配合合适初始化。
- **取舍**：转置卷积参数更多、表达力更强；插值 + 卷积更平滑、更省参数，讲义建议第一个 U-Net 用后者。

### Q16 — 参考回答要点

- **为什么不能直接喂**：U-Net 的激活显存约随 `H·W·C` 增长，讲义指出 1024×1024 输入在 1024 通道瓶颈下前向就要占用 GB 级显存；8000×8000 是其 60 倍以上的像素量。
- **训练**：随机裁剪 512×512（或 1024）的 patch 训练；保证 patch 中前景比例（可做前景过采样）；可开混合精度（AMP）和 gradient checkpointing 换显存；必要时减小 `base` 通道数。
- **推理**：滑动窗口**重叠切块**（如 512 窗口、128 重叠），只取每块中心区域或用高斯/线性权重融合重叠部分，避免拼接缝——块边缘的像素缺少上下文，预测最差；整张图拼回后再做后处理（形态学、连通域、矢量化）。
- **结构选择**：讲义提到第二种方案：用空洞卷积替代下采样的 DeepLab 系，保持较高分辨率的同时扩大感受野。
- **坑**：切块尺寸要能被 16 整除；训练/推理的归一化与分辨率（GSD）要一致；建筑物跨块时实例会被切断，需要在全图层面做后处理。

### Q17 — 参考回答要点

- **先拆指标**：mIoU 0.74 被背景等大类"抬高"了，讲义原话"Mean IoU hides a class at 15% when nine others are at 85%"。只看缺陷类：IoU 0.21 的构成是什么——画出缺陷类的 precision/recall（像素级）、按缺陷大小分桶的召回、以及边界误差（Boundary F1）。
- **三种典型病因（对应讲义的诊断目标）**：
  - 小目标召回差：小缺陷在 H/16 的瓶颈上几乎消失 → 提高输入分辨率或切块、保留更浅层的 skip、对小缺陷过采样；
  - 边界不准：大体位置对但轮廓偏 → 关注 Boundary F1，加边界损失，检查上采样方式和标注一致性；
  - 类别不平衡：模型偏向背景 → `CE + Dice`、类别加权 CE、Focal/Tversky，采样时保证每个 batch 含缺陷。
- **数据侧**：检查标注质量（缺陷边界是否一致、是否有漏标），做 copy-paste 缺陷增强。
- **评估侧**：按整个验证集累计交并（而不是按 batch 平均），缺陷类单独报告；业务上往往更关心"有没有漏检某个缺陷"，可以补充按连通域计的召回。
- **加分点**：能说出 `Dice = 2·IoU/(1+IoU)` 用于和医学/质检团队对齐数字。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 02 从零实现卷积](../../02-convolutions-from-scratch/docs/zh.md)：卷积、padding、stride、池化的形状计算。
- [阶段 04 · 03 CNNs — LeNet 到 ResNet](../../03-cnns-lenet-to-resnet/docs/zh.md)：编码器就是一个分类 CNN 的特征提取部分。
- [阶段 04 · 04 图像分类](../../04-image-classification/docs/zh.md)：分割 = 在每个像素上做分类。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：交叉熵、focal loss。
- [阶段 03 · 07 正则化](../../../03-deep-learning-core/07-regularization/docs/zh.md)：BatchNorm 的原理（解释 `bias=False`）。

### 本节被哪些后续内容用到
- [阶段 04 · 08 实例分割——Mask R-CNN](../../08-instance-segmentation-mask-rcnn/docs/zh.md)：从"每像素一个类别"走向"每个目标一张 mask"。
- [阶段 04 · 10 图像生成 — Diffusion Models](../../10-image-generation-diffusion/docs/zh.md)：去噪网络就是带时间条件的 U-Net。
- [阶段 04 · 11 Stable Diffusion](../../11-stable-diffusion/docs/zh.md)：在 latent 空间里跑的 U-Net + cross-attention。
- [阶段 04 · 21 关键点检测和姿势估计](../../21-keypoint-pose/docs/zh.md)：用 U-Net 式网络输出 K 个关键点热力图。
- [阶段 04 · 24 SAM 3 与开放词表分割](../../24-sam3-open-vocab-segmentation/docs/zh.md)：以本节为前置的可提示分割。
- [阶段 04 · 26 单目深度和几何估计](../../26-monocular-depth/docs/zh.md)：同属稠密预测，以本节为前置。
- [阶段 08 · 04 Conditional GANs & Pix2Pix](../../../08-generative-ai/04-conditional-gans-pix2pix/docs/zh.md)：Pix2Pix 的生成器就是 U-Net。

### 延伸关键词
`FCN` · `DeepLabV3+ / 空洞卷积 / ASPP` · `SegFormer` · `Mask2Former / OneFormer` · `Tversky / Lovász-Softmax` · `Boundary F1` · `混淆矩阵求 mIoU` · `滑窗切块推理` · `shortcut learning` · `segmentation_models_pytorch`
