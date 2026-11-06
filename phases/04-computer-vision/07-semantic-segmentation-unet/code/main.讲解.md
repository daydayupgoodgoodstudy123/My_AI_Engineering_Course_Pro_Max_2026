# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 07 节 语义分割——U-Net ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数；有 GPU 自动用 `cuda`，否则 CPU） ｜ **依赖**：`numpy`、`torch`（`torch.nn`、`torch.nn.functional`、`torch.utils.data`、`torch.optim`）；无需联网、无需预训练权重

---

## 1. 这份代码在考察什么

这是一个**端到端可训练**的最小语义分割项目：自己造数据、自己搭 U-Net、自己写损失和指标，在 CPU 上几十秒就能跑完 8 个 epoch。

1. **U-Net 的积木**：`DoubleConv`（两次 3×3 卷积 + BN + ReLU）、`Down`（池化 + DoubleConv）、`Up`（上采样 + 拼接 skip + DoubleConv）如何拼成 U 形网络。
2. **skip connection 的实现细节**：拼接前如何处理尺寸不一致、为什么只比较空间维。
3. **分割损失**：像素级交叉熵 + 多类 Dice 的组合损失，以及 one-hot 与 `permute` 的维度处理。
4. **分割指标**：逐类 IoU 的计算，以及"缺席类别"的处理（这里藏着一个会让结果偏低的坑）。
5. **完整训练流程**：`Dataset / DataLoader`、`train()/eval()` 切换、`no_grad`、优化器三连。

> 一句话：**分割 = 每个像素做分类**；U-Net 用"编码器拿上下文 + skip 送细节"让这件事做得又准又清晰。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DoubleConv` | `nn.Module` | 两次 `Conv3×3 → BN → ReLU`，空间尺寸不变 | U-Net 的基本块 |
| `Down` | `nn.Module` | `MaxPool2d(2)` + `DoubleConv`，分辨率减半 | 编码器（收缩路径） |
| `Up` | `nn.Module` | 双线性上采样 ×2 → 对齐尺寸 → 与 skip concat → `DoubleConv` | 解码器（扩张路径）+ skip |
| `UNet` | `nn.Module` | `inc + 4×Down + 4×Up + 1×1 outc` | 完整 U-Net |
| `dice_loss` | 函数 | 多类 soft Dice（按类在 batch 上汇总后求平均） | Dice loss |
| `combined_loss` | 函数 | `CE + λ·Dice`，并返回两个分量 | 组合损失 |
| `iou_per_class` | 函数（`@torch.no_grad()`） | 对 argmax 预测逐类算 IoU，缺席类返回 nan | IoU / mIoU |
| `synthetic_segmentation` | 函数 | 生成"绿色背景上一个红圆或蓝方"的图像与 mask | 合成数据 |
| `SegDataset` | `Dataset` | HWC → CHW 张量，mask 转 long | 数据管道 |
| `main()` | 演示入口 | 60 张图 85/15 切分，训练 8 个 epoch，每轮打印 loss 和逐类 IoU | 训练循环 |

数据流：`synthetic_segmentation → SegDataset → DataLoader → UNet → logits (N,3,64,64)`；训练时 `combined_loss(logits, y)` 反向传播，验证时 `iou_per_class(logits, y)`。

---

## 3. 逐段精讲

### 3.1 `DoubleConv`：最常用的积木

```python
class DoubleConv(nn.Module):
    def __init__(self, in_c, out_c):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_c, out_c, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_c),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_c, out_c, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_c),
            nn.ReLU(inplace=True),
        )
```

- `kernel=3, padding=1`：输出尺寸 = 输入尺寸（`H + 2·1 − 3 + 1 = H`）。U-Net 原论文用无 padding 卷积，输出会缩小、skip 要裁剪；加 padding 是现在的通用简化。
- 第一个卷积改变通道数，第二个保持通道数。
- `bias=False`：BN 会减掉 batch 均值，卷积偏置会被抵消，BN 的 β 已经承担了偏置的角色。
- `nn.ReLU(inplace=True)`：直接在输入张量上改写，省一份激活显存；因为前面是 BN 的输出，不会破坏需要保留的张量。
- `nn.Sequential`：按顺序串起来，`forward` 只需 `return self.net(x)`。
- 参数量公式：`9·in_c·out_c + 9·out_c² + 4·out_c`（两个 BN 各有 γ、β）。

### 3.2 `Down` 与 `Up`：下采样与带 skip 的上采样

```python
class Down(nn.Module):
    def __init__(self, in_c, out_c):
        super().__init__()
        self.net = nn.Sequential(nn.MaxPool2d(2), DoubleConv(in_c, out_c))


class Up(nn.Module):
    def __init__(self, in_c, out_c):
        super().__init__()
        self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False)
        self.conv = DoubleConv(in_c, out_c)

    def forward(self, x, skip):
        x = self.up(x)
        if x.shape[-2:] != skip.shape[-2:]:
            x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        x = torch.cat([skip, x], dim=1)
        return self.conv(x)
```

- `Down`：`MaxPool2d(2)` 分辨率减半（奇数尺寸向下取整），`DoubleConv` 把通道翻倍。
- `Up` 选择**双线性插值 + 卷积**而不是转置卷积：没有可学习参数的上采样不会产生棋盘格伪影，讲义称之为"现代默认"。上采样本身不改变通道数，通道的减少发生在随后的 `DoubleConv` 里。
- **尺寸对齐**：输入不能被 16 整除时（如 100×100：100→50→25→12→6），上采样 12→24 与 skip 的 25 对不上，`F.interpolate(size=skip.shape[-2:])` 把它拉成 25×25。
- **为什么只比较 `shape[-2:]`**：`shape` 是 `(N, C, H, W)`，`[-2:]` 只取 `(H, W)`。如果比较完整 shape，通道数不同也会触发插值——而通道数不同说明网络搭错了，应该在 `torch.cat` 或卷积处**大声报错**，而不是被插值悄悄掩盖。
- `torch.cat([skip, x], dim=1)`：在通道维拼接，所以 `Up` 的 `in_c` 必须写成"skip 通道 + 上采样通道"。

### 3.3 `UNet`：把积木拼成 U 形

```python
class UNet(nn.Module):
    def __init__(self, in_channels=3, num_classes=3, base=32):
        super().__init__()
        self.inc = DoubleConv(in_channels, base)
        self.d1 = Down(base, base * 2)
        self.d2 = Down(base * 2, base * 4)
        self.d3 = Down(base * 4, base * 8)
        self.d4 = Down(base * 8, base * 16)
        self.u1 = Up(base * 16 + base * 8, base * 8)
        self.u2 = Up(base * 8 + base * 4, base * 4)
        self.u3 = Up(base * 4 + base * 2, base * 2)
        self.u4 = Up(base * 2 + base, base)
        self.outc = nn.Conv2d(base, num_classes, 1)

    def forward(self, x):
        x1 = self.inc(x)
        x2 = self.d1(x1)
        x3 = self.d2(x2)
        x4 = self.d3(x3)
        x5 = self.d4(x4)
        x = self.u1(x5, x4)
        x = self.u2(x, x3)
        x = self.u3(x, x2)
        x = self.u4(x, x1)
        return self.outc(x)
```

`main()` 中 `base=16`、输入 `(8, 3, 64, 64)` 时的形状：

| 编码器 | 形状 | 解码器 | 形状 |
|--------|------|--------|------|
| `x1` | `(8, 16, 64, 64)` | `u1(x5, x4)` | `(8, 128, 8, 8)` |
| `x2` | `(8, 32, 32, 32)` | `u2(·, x3)` | `(8, 64, 16, 16)` |
| `x3` | `(8, 64, 16, 16)` | `u3(·, x2)` | `(8, 32, 32, 32)` |
| `x4` | `(8, 128, 8, 8)` | `u4(·, x1)` | `(8, 16, 64, 64)` |
| `x5`（瓶颈） | `(8, 256, 4, 4)` | `outc` | `(8, 3, 64, 64)` |

- 编码器的 `x1…x4` 都被保存在局部变量里，等解码器"按相反顺序"取用——这就是 skip connection 在代码里的样子：**没有任何特殊模块，只是把变量传过去**。
- `outc` 是 1×1 卷积：在每个像素上做一次 `base → num_classes` 的线性分类，输出 logits（未经 softmax）。
- `base` 控制网络宽度：讲义用 `base=32`（约 785 万参数），`main()` 用 `base=16`（1,964,131 个参数），宽度减半参数约变为 1/4。
- ⚠️ 讲义说 `base=32` 时"About 7.7M parameters"，按公式精确计算是 7,849,634（约 7.85M），量级一致。

### 3.4 `dice_loss` 与 `combined_loss`

```python
def dice_loss(logits, targets, num_classes, eps=1e-6):
    probs = F.softmax(logits, dim=1)
    one_hot = F.one_hot(targets, num_classes).permute(0, 3, 1, 2).float()
    dims = (0, 2, 3)
    inter = (probs * one_hot).sum(dim=dims)
    denom = probs.sum(dim=dims) + one_hot.sum(dim=dims)
    dice = (2 * inter + eps) / (denom + eps)
    return 1 - dice.mean()


def combined_loss(logits, targets, num_classes, lam=1.0):
    ce = F.cross_entropy(logits, targets)
    dc = dice_loss(logits, targets, num_classes)
    return ce + lam * dc, {"ce": ce.detach().item(), "dice": dc.detach().item()}
```

- `F.softmax(logits, dim=1)`：在**类别维**上归一化，每个像素的 3 个概率和为 1。用概率而不是 argmax，是为了让 Dice 可导（"soft Dice"）。
- `F.one_hot(targets, num_classes)`：`(N,H,W)` → `(N,H,W,C)`，新维度加在最后；`permute(0,3,1,2)` 变成 `(N,C,H,W)` 与 `probs` 对齐；`.float()` 因为 one-hot 是整型。
- `dims=(0,2,3)`：在 batch 和空间维上求和，得到每个类别一个 Dice（长度 C 的向量），再 `.mean()` 对类别求平均（macro Dice）。背景类也包含在内。
- 公式就是讲义的 `Dice = 2Σ(p·y) / (Σp + Σy)`，`eps` 加在分子分母上防止 0/0。
- `F.cross_entropy(logits, targets)`：直接接受 `(N,C,H,W)` 的 logits 和 `(N,H,W)` 的 long 标签，内部自带 log-softmax，不需要 reshape。
- 返回值是 `(总损失, 分量字典)`：`.detach().item()` 把分量转成 Python 浮点数，用于日志，不会持有计算图。
- ⚠️ 坑：如果某个 batch 完全没有某一类，该类 `inter = 0`，但 `Σp` 远大于 `eps`，Dice ≈ 0，这一类会给损失贡献约 `1/C` 的"常量"。`main()` 训练集最后一个 batch 只有 3 张图且都是圆（类别 1），方块类就会出现这种情况。常见修法：只对出现的类取平均，或把 `eps` 换成较大的平滑项（测验 Q11）。

### 3.5 `iou_per_class`：逐类 IoU

```python
@torch.no_grad()
def iou_per_class(logits, targets, num_classes):
    preds = logits.argmax(dim=1)
    ious = torch.zeros(num_classes)
    for c in range(num_classes):
        pred_c = (preds == c)
        true_c = (targets == c)
        inter = (pred_c & true_c).sum().float()
        union = (pred_c | true_c).sum().float()
        ious[c] = (inter / union) if float(union) > 0 else float("nan")
    return ious
```

- `@torch.no_grad()` 是**装饰器**：整个函数内部不建计算图，省显存也更快——指标不需要梯度。
- `argmax(dim=1)`：每个像素取概率最大的类，得到 `(N,H,W)` 的硬预测。
- `&`、`|` 是布尔张量的逐元素与/或，求和就是像素个数。
- 某类既没出现也没被预测时 `union = 0`，返回 `nan`——这是讲义强调的"缺席类不能当 0 参与平均"。
- ⚠️ `ious` 建在 CPU 上，而在 GPU 上训练时 `inter / union` 是 GPU 上的 0 维张量；赋值时需要一次跨设备拷贝（并伴随同步）。更清晰的写法是 `ious[c] = (inter / union).item()`，或者把 `ious` 建在 `logits.device` 上。

### 3.6 合成数据：`synthetic_segmentation` 与 `SegDataset`

```python
    yy, xx = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    circle_color = np.array([0.9, 0.1, 0.1], dtype=np.float32)
    square_color = np.array([0.1, 0.2, 0.9], dtype=np.float32)
    for i in range(num_samples):
        bg = np.array([0.3, 0.7, 0.3], dtype=np.float32)
        images[i] = bg
        cls = int(rng.integers(1, 3))
        cx, cy = int(rng.integers(14, size - 14)), int(rng.integers(14, size - 14))
        r = int(rng.integers(8, 14))
        if cls == 1:
            mask = (xx - cx) ** 2 + (yy - cy) ** 2 < r ** 2
            images[i][mask] = circle_color
        else:
            mask = (np.abs(xx - cx) < r) & (np.abs(yy - cy) < r)
            images[i][mask] = square_color
        masks[i][mask] = cls
        images[i] += rng.normal(0, 0.02, images[i].shape)
        images[i] = np.clip(images[i], 0, 1)
```

- `np.meshgrid(..., indexing="ij")` 生成每个像素的行坐标 `yy` 和列坐标 `xx`；圆用"到圆心距离² < r²"，方块用"x、y 方向偏移都 < r"，两者都是**向量化的布尔 mask**，一行画完一个形状。
- 讲义版本把 meshgrid 放在循环里，代码把它提到循环外——网格只依赖 `size`，只算一次即可。
- `images[i][mask] = color`：布尔索引赋值，把 mask 为 True 的像素整体设成某种颜色（广播到 3 个通道）。
- 加 0.02 的高斯噪声再 `clip` 回 [0,1]。
- 统计：每张图恰好一个形状，前景像素平均约占 9.3%（4.7%–15.3%），存在一定的类别不平衡。
- ⚠️ **与讲义不一致**：讲义 Step 6 用随机背景色、随机形状色、每图 1–3 个形状，目的是"逼网络学形状而不是颜色"；而这里圆永远是红色、方永远是蓝色、背景永远是绿色。一个"红通道 > 0.6 → 圆、蓝通道 > 0.6 → 方"的阈值规则在这份数据上三类 IoU 全是 1.0（已用 NumPy 验证）。所以这个 demo 只能证明管道跑通，不能证明网络学会了形状（测验 Q12）。

```python
class SegDataset(Dataset):
    def __getitem__(self, i):
        img = torch.from_numpy(self.images[i]).permute(2, 0, 1).float()
        mask = torch.from_numpy(self.masks[i]).long()
        return img, mask
```

- 实现 `__len__` 和 `__getitem__` 两个魔术方法，就能被 `DataLoader` 自动分批、打乱。
- NumPy 图像是 `HWC`，PyTorch 卷积要 `CHW`，所以 `permute(2,0,1)`；mask 必须是 `long` 才能给 `cross_entropy` 和 `one_hot` 用。
- `torch.from_numpy` 与原数组共享内存，不拷贝。

### 3.7 `main()`：训练与验证循环

```python
    for epoch in range(8):
        model.train()
        loss_sum, total = 0.0, 0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            logits = model(x)
            loss, _ = combined_loss(logits, y, num_classes)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            loss_sum += loss.detach().item() * x.size(0)
            total += x.size(0)

        model.eval()
        iou_sum = torch.zeros(num_classes)
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                iou_sum += iou_per_class(model(x), y, num_classes).nan_to_num(0)
        iou_mean = (iou_sum / len(val_loader)).tolist()
```

- 数据：60 张图，`split = int(0.85 * 60) = 51`，训练 51 张（`batch_size=8` → 7 个 batch，最后一个 3 张），验证 9 张（2 个 batch：8 张 + 1 张）。
- `model.train()` / `model.eval()`：切换 BatchNorm 的行为（训练用 batch 统计量并更新 running stats；验证用 running stats）。忘记切换是分割模型"训练好、验证差"的常见原因。
- 优化器三连：`zero_grad → backward → step`。
- `loss.detach().item() * x.size(0)`：按样本数加权累计，最后除以 `total`，得到真正的样本平均损失（最后一个 batch 只有 3 张，不能简单对 batch 取平均）。
- `loss, _ = combined_loss(...)`：用 `_` 丢弃不需要的分量字典。
- ⚠️ **指标偏差**：验证集的第二个 batch 只有 1 张圆形图。方块类在这个 batch 里 IoU 要么是 nan（被 `nan_to_num(0)` 变成 0），要么是 0；再除以 `len(val_loader)=2`，打印出来的方块 IoU **最多约 0.5**，即使模型完美。讲义 Step 7 也提醒过应改为按存在性掩码 + `nanmean`，更稳妥的做法是在整个验证集上累计交集与并集再相除（测验 Q10）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 双线性上采样 + DoubleConv | 无棋盘格伪影、参数少，讲义推荐的第一个 U-Net 做法 | 转置卷积表达力更强；生产中两者都常见 |
| `padding=1` 保持尺寸 | 不用裁剪 skip，输入输出同尺寸 | 原论文无 padding + 裁剪；边缘像素上下文稍差 |
| 只比较 `shape[-2:]` 再插值 | 兼容不能被 16 整除的输入，同时让通道错误大声暴露 | 插值会让 skip 与上采样特征有轻微错位 |
| `CE + Dice`（λ=1） | CE 稳定、Dice 抗不平衡 | 缺席类 Dice 需要特殊处理；可换 Focal/Tversky |
| 合成数据（固定颜色） | 秒级生成、无需下载 | 颜色就是捷径，不能验证"学形状"；应随机化颜色 |
| `base=16`、8 个 epoch | CPU 上也能很快跑完 | 真实任务用 `base=64` 或预训练编码器（`smp.Unet`） |
| 按 batch 平均 IoU 并把 nan 当 0 | 代码最短 | 结果有偏；应在数据集级别累计交并或用混淆矩阵 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 多重赋值 | `loss_sum, total = 0.0, 0`；`x, y = x.to(device), y.to(device)` | 一行给多个变量赋值 |
| 用 `_` 丢弃返回值 | `loss, _ = combined_loss(...)` | 约定俗成表示"这个值不用" |
| 条件表达式 | `"cuda" if torch.cuda.is_available() else "cpu"` | `a if 条件 else b` |
| 列表推导 + f-string 格式符 | `[f'{v:.2f}' for v in iou_mean]` | 每个数保留 2 位小数，得到字符串列表 |
| f-string 千分位 | `f"params: {sum(...):,}"` | `:,` 用逗号分隔千位，如 `1,964,131` |
| 生成器表达式 | `sum(p.numel() for p in model.parameters())` | 不建中间列表，直接累加 |
| 类继承 + `super()` | `class UNet(nn.Module)`、`super().__init__()` | 继承 PyTorch 模块，必须先初始化父类 |
| 魔术方法 | `SegDataset.__len__`、`__getitem__` | 让对象支持 `len()` 和 `ds[i]`，`DataLoader` 依赖它们 |
| 装饰器 | `@torch.no_grad()` | 给整个函数关闭梯度计算 |
| 上下文管理器 | `with torch.no_grad():` | 只在代码块内关闭梯度，退出自动恢复 |
| 元组切片 | `x.shape[-2:]` | 取最后两个维度 `(H, W)` |
| NumPy 布尔索引 | `images[i][mask] = circle_color` | 只对 mask 为 True 的像素赋值 |
| `np.meshgrid(indexing="ij")` | `yy, xx = np.meshgrid(...)` | 生成像素坐标网格；`"ij"` 表示第一个输出沿行变化 |
| 链式方法调用 | `torch.from_numpy(...).permute(2, 0, 1).float()` | 每个方法返回新张量，可连续调用 |
| `if __name__ == "__main__":` | 文件末尾 | 只有直接运行时才执行 `main()` |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 数据生成部分只依赖 NumPy，已单独抽取运行验证（类别分布、前景比例、颜色 baseline IoU = 1.0）；下面是根据代码推出的预期输出格式与趋势：

```text
params: 1,964,131
epoch 0  train_loss 1.xxx  iou ['0.xx', '0.xx', '0.xx']
epoch 1  train_loss ...    iou [...]
...
epoch 7  train_loss 0.xxx  iou ['0.9x', '0.xx', '≤0.5']
```

逐行解读：

- `params: 1,964,131`：`base=16`、3 类输出的 U-Net 参数量，由 `9·in·out + 9·out² + 4·out` 对 9 个块求和再加 `outc` 的 51 个参数得到，是确定值。
- `train_loss`：初始化时 softmax 接近均匀，CE ≈ `ln 3 ≈ 1.10`；Dice 方面背景约占 90% 像素，背景 Dice ≈ 0.49、两个前景类 ≈ 0.09，Dice loss ≈ 0.78，因此**第一步**的总损失约 1.9。epoch 0 打印的是整轮平均值，会低于它，之后逐轮下降。具体数值依赖随机初始化和 `shuffle=True` 的顺序。
- `iou` 三个数依次是背景、圆、方块：
  - 背景占绝大多数像素，IoU 最先升到 0.9 以上；
  - 圆形在两个验证 batch 里都出现，IoU 能正常反映质量；
  - 方块只出现在第一个 batch，按 3.7 节分析，打印值**最多约 0.5**——看到"方块 IoU 卡在 0.45 上不去"不是模型问题，而是指标代码问题。
- 由于数据可以靠颜色区分，模型通常几个 epoch 就能学好；这说明管道正确，但不说明模型学会了形状。

---

## 7. 动手改一改

1. 把验证 IoU 改成"整个验证集累计交集/并集再相除"，对比修改前后方块类的数值。
2. 把 `synthetic_segmentation` 改成随机背景色 + 随机形状色（参考讲义 Step 6），再跑一次，观察收敛是否变慢、最终 IoU 是否下降。
3. 写一个 `UpTransposed`：用 `nn.ConvTranspose2d(in_c_up, in_c_up, kernel_size=3, stride=2, padding=1, output_padding=1)` 替换双线性上采样，训练后可视化输出，找棋盘格伪影（讲义练习 2）。
4. 在 `dice_loss` 里加一个 `present = one_hot.sum(dim=dims) > 0` 掩码，只对出现过的类取平均。
5. 实现二分类版 `bce_dice_loss`（前景约占 5%），对比只用 BCE 的收敛速度（讲义练习 1）。
6. 用 100×100 的随机输入跑一次 `UNet`，打印每层形状，确认 `Up` 里的插值分支被触发。

---

## 8. 常见坑

- **标签 dtype 错误**：mask 不是 `long` 时，`F.cross_entropy` 和 `F.one_hot` 都会报错。
- **one-hot 维度顺序**：`F.one_hot` 把类别维放在最后，忘了 `permute` 就会和 `(N,C,H,W)` 的概率错位相乘（若 H、W 恰好等于 C 还不会报错）。
- **忘记 `model.eval()`**：BN 在验证时仍用 batch 统计量，batch 很小时（如验证集最后只剩 1 张）结果会剧烈抖动。
- **按 batch 平均 IoU、把缺席类当 0**：本文件就有这个问题，指标被系统性压低。
- **合成数据的捷径**：颜色和类别一一对应，网络不学形状也能满分。
- **输入尺寸不是 16 的倍数**：本实现靠插值兜底，但 skip 与上采样特征会有亚像素错位；生产中通常把输入 pad 到 16 的倍数。
