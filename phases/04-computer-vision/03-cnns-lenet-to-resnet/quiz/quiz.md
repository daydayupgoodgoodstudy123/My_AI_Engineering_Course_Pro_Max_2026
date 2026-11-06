# 测验 · CNNs — LeNet 到 ResNet（CNNs — LeNet to ResNet）

> **阶段 04 · 计算机视觉 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | LeNet-5（1998） | 卷积 + 池化交替、最后接全连接分类头；约 6 万参数，定义了所有 CNN 的基本模板 |
| 2 | AlexNet（2012） | ReLU 代替 tanh（不饱和、收敛快约 6 倍）、Dropout 正则化、更深更宽（约 6000 万参数、双 GPU） |
| 3 | VGG（2014） | 只用 3×3 卷积并加深；两个 3×3 = 一个 5×5 的感受野但参数更少（18C² vs 25C²）、多一个非线性；VGG-16 约 1.38 亿参数 |
| 4 | Inception（2014） | 同一层并行 1×1 / 3×3 / 5×5 / 池化分支再沿通道拼接；分支内用 1×1 卷积做 bottleneck 控制参数量 |
| 5 | 退化问题（degradation） | 普通网络超过约 20 层后，**训练误差**和测试误差都变大——不是过拟合，而是优化困难 |
| 6 | 残差连接 | `y = F(x) + x`，块只需把 F 推向 0 就能实现恒等映射；梯度多了一条恒等通路 |
| 7 | BasicBlock 与 Bottleneck | BasicBlock：两个 3×3（ResNet-18/34）；Bottleneck：1×1 降维 → 3×3 → 1×1 升维（ResNet-50/101/152），高通道数时更省 |
| 8 | 投影 shortcut | stride≠1 或通道数变化时，shortcut 改为 1×1 卷积（带 stride）+ BN 以匹配形状 |
| 9 | Conv + BN 的约定 | 卷积后紧跟 BN 时设 `bias=False`，BN 的 β 已经承担偏置的作用 |
| 10 | backbone / stem / head | stem 把 3 通道变成基础宽度；backbone 产出特征图；head = 自适应池化 + flatten + 线性层 |

### 核心技能（能动手做到）

- [ ] 用 PyTorch 在 40 行内写出 LeNet-5、VGGBlock、BasicBlock，并能逐层说出每个张量的形状
- [ ] 手算 LeNet-5 的参数量（61,706），并指出参数主要集中在哪一层
- [ ] 手算 TinyResNet 各组参数量，说明为什么参数集中在最后一组（layer4 约占 75%）
- [ ] 正确实现 shortcut 的判断条件 `stride != 1 or in_c != out_c`，并能举出只判断 stride 时会崩溃的配置
- [ ] 实现 Bottleneck 块，并定量比较它与 BasicBlock 在 256 通道时的参数量
- [ ] 能讲清 `AdaptiveAvgPool2d(1)` 为什么让网络与输入分辨率解耦，而 LeNet 的 `Linear(16*5*5, 120)` 把输入尺寸写死了

---

## 二、基础自测（选择题）

**Q1.** 下列哪一项**不是**讲义中列出的 AlexNet（2012）的关键改进？

- A. 用 ReLU 代替 tanh
- B. 在全连接分类头中使用 Dropout
- C. 更深更宽的网络，并拆分到两块 GPU 上训练
- D. 用恒等 skip connection 训练上百层网络

**Q2.** Inception 模块在 3×3 和 5×5 分支之前先放一个 1×1 卷积，主要目的是：

- A. 增大感受野
- B. 先压缩通道数（bottleneck），大幅降低后续大卷积核的参数量和计算量
- C. 代替池化做下采样
- D. 实现平移不变性

**Q3.** He 等人发现：56 层普通网络的**训练误差**比 20 层普通网络还高。这说明：

- A. 56 层网络过拟合了
- B. 训练数据不够
- C. 这是优化困难（退化问题），更深的网络连训练集都拟合不好
- D. 应该把学习率调大

**Q4.** 对残差块 `y = F(x) + x`，反向传播时损失对 `x` 的梯度为：

- A. `∂L/∂x = ∂L/∂y · ∂F/∂x`
- B. `∂L/∂x = ∂L/∂y · (∂F/∂x + I)`
- C. `∂L/∂x = ∂L/∂y`
- D. `∂L/∂x = ∂L/∂y · ∂F/∂x · I`

**Q5.** 一个 BasicBlock 的输入是 `(N, 64, 32, 32)`，参数为 `in_c=64, out_c=128, stride=2`。它的 shortcut 应该是：

- A. `nn.Identity()`，形状由主分支负责
- B. `nn.MaxPool2d(2)`
- C. `1×1 Conv(64→128, stride=2) + BN`，输出 `(N, 128, 16, 16)` 与主分支相加
- D. `3×3 Conv(64→128, stride=1) + BN`

**Q6.** `BasicBlock` 中所有卷积都写了 `bias=False`，原因是：

- A. 有 bias 的卷积无法在 GPU 上运行
- B. 紧跟其后的 BatchNorm 会减去均值（bias 被抵消），再用自己的可学习偏置 β 重新加上偏移，卷积的 bias 是冗余参数
- C. 为了让网络输出非负
- D. 残差连接要求卷积必须是线性无偏的

**Q7.** ResNet-18（约 1170 万参数）与 VGG-16（约 1.38 亿参数）的 ImageNet top-1 准确率接近（69.8% vs 71.6%）。VGG-16 参数多出来的部分**主要**在：

- A. 13 个 3×3 卷积层
- B. BatchNorm 层
- C. 最后的三层全连接（第一层的输入就是 7×7×512=25,088 维），合计约 1.24 亿参数
- D. 输入的 stem 层

---

## 三、动手 / 代码题

**Q8.** 不运行代码，手算 `LeNet5` 每一层的参数量和总参数量，并回答：参数最多的是哪一层，占比多少？

```python
self.conv1 = nn.Conv2d(1, 6, kernel_size=5)
self.conv2 = nn.Conv2d(6, 16, kernel_size=5)
self.pool = nn.AvgPool2d(2)
self.fc1 = nn.Linear(16 * 5 * 5, 120)
self.fc2 = nn.Linear(120, 84)
self.fc3 = nn.Linear(84, num_classes)
```

**Q9.** MNIST 原始图片是 28×28。分别预测下面两次调用的结果（输出形状或报错），并解释差异：

```python
LeNet5()(torch.randn(1, 1, 28, 28))
TinyResNet()(torch.randn(1, 3, 64, 64))
```

**Q10.** 有人把 `BasicBlock` 的 shortcut 判断写成了只看 stride：

```python
        if stride != 1:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_c, out_c, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_c),
            )
        else:
            self.shortcut = nn.Identity()
```

(a) 用这个有 bug 的块构建 `TinyResNet` 并前向传播，会报错吗？为什么？
(b) 给出一个会触发报错的 `_make_group` 调用，并说明报错发生在哪一行。
(c) 这个例子说明了测试上的什么问题？

**Q11.** 按讲义练习 2，实现一个 Bottleneck 块（1×1 降维 → 3×3 → 1×1 升维，扩张系数 4，带 shortcut），并手算：输入 256 通道、中间宽度 64、stride 1 时，它的卷积参数量与一个 256→256 的 BasicBlock 的卷积参数量各是多少？

---

## 四、面试高频题

**Q12.**（基础必考）ResNet 为什么有效？残差连接到底解决了什么问题？

**Q13.**（原理深挖）BatchNorm 在 CNN 中做了什么？训练和推理时有什么区别？为什么 Conv 后面接 BN 可以不要 bias？

**Q14.**（原理深挖）Bottleneck 块的设计思路是什么？为什么 ResNet-50 用 Bottleneck，而 ResNet-18/34 用 BasicBlock？

**Q15.**（场景设计）你要为一个工厂缺陷检测项目选 CNN backbone：约 5,000 张标注图、6 个类别、要部署在一台没有 GPU 的工控机上。你会怎么选、怎么验证？

**Q16.**（追问型）"没有 ResNet 就没有 GPT"——残差连接在 Transformer 里是什么样的？Post-LN 和 Pre-LN 有什么区别？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义列出的 AlexNet 三个改变是：ReLU（A）、Dropout（B）、更深更宽并在两块 GPU 上训练（C）。恒等 skip connection 是 2015 年 ResNet 的贡献。讲义还特别指出：双 GPU 拆分只是**硬件妥协**，不是架构洞见，真正留下来的是 ReLU、Dropout 和"深度+宽度"。

### Q2 — 答案：B

5×5 卷积的参数量是 `25·C_in·C_out`，如果输入有 256 通道，直接做会非常贵。先用 1×1 卷积把通道压到比如 64，再做 5×5，参数和计算量都大幅下降——讲义原话"Inception v1 used 1x1 convolutions inside each branch as a bottleneck to keep parameter counts sane"。1×1 卷积不改变感受野（A 错），也不下采样（C 错）。

### Q3 — 答案：C

过拟合的特征是"训练误差低、测试误差高"；这里是**训练误差**本身更高，所以不是过拟合（A 错）。更深的网络理论上至少能做到和浅网络一样好（多出来的层学恒等映射即可），实际却做不到，说明优化器找不到好的解——这就是退化问题。数据量不变时浅网络训练得更好，B 错；调学习率不能根本解决，D 错。

### Q4 — 答案：B

链式法则：`y = F(x) + x`，`∂y/∂x = ∂F/∂x + I`，所以 `∂L/∂x = ∂L/∂y · (∂F/∂x + I)`。即使 `∂F/∂x` 很小，梯度仍能通过恒等项 `I` **原封不动地**传回前面的层——这就是常说的"梯度高速公路"。A 是普通网络的情形；C 只在 F 的梯度为 0 时成立。

### Q5 — 答案：C

主分支第一个卷积 stride=2，输出 `(N,128,16,16)`；输入 x 是 `(N,64,32,32)`，通道和空间都不匹配，不能直接相加。`1×1 Conv(stride=2)` 同时完成"通道 64→128"和"空间 32→16"，再接 BN 与主分支的尺度对齐。这正是 `main.py` 中 `if stride != 1 or in_c != out_c:` 分支的内容。

### Q6 — 答案：B

BN 先计算 `(z − μ)/σ`：卷积输出 `z = Wx + b` 中的常数 `b` 会被减均值完全抵消，然后 BN 再乘以 γ、加上 β。因此卷积的 bias 对输出没有任何作用，只是浪费参数（讲义："BN's beta parameter already handles the bias"）。注意 `MiniVGG` 的 `VGGBlock` 中卷积**保留**了默认的 `bias=True`，后面也接了 BN——功能上没错，只是多了一些冗余参数。

### Q7 — 答案：C

VGG-16 的三层全连接：`25088×4096 + 4096` ≈ 1.03 亿，`4096×4096 + 4096` ≈ 1,678 万，`4096×1000 + 1000` ≈ 410 万，合计约 **1.24 亿**，占总参数的约 90%。ResNet 用"全局平均池化 + 一个线性层"作为分类头，几乎不占参数。所以讲义里"残差连接带来 12 倍参数效率"这句话需要补充：参数量差距的**主要来源是分类头的设计**，残差连接的主要贡献是让网络可以训练得更深。原 quiz.json 的解析也指出了这一点。

### Q8 — 参考答案

| 层 | 计算 | 参数量 |
|----|------|--------|
| conv1 | `1×6×5×5 + 6` | 156 |
| conv2 | `6×16×5×5 + 16` | 2,416 |
| fc1 | `400×120 + 120` | 48,120 |
| fc2 | `120×84 + 84` | 10,164 |
| fc3 | `84×10 + 10` | 850 |
| 池化 | 无参数 | 0 |
| **合计** | | **61,706** |

与讲义给出的 `params: 61,706` 一致。参数最多的是 **fc1**（48,120，约占 78%）。两个卷积层合计只有 2,572 个参数——再次印证"卷积省参数、全连接吃参数"，这也是 VGG 参数量爆炸、而 ResNet 用全局平均池化替代大全连接层的原因。

### Q9 — 参考答案

1. `LeNet5()(torch.randn(1, 1, 28, 28))` **报错**。形状推导：28 →（5×5 卷积）24 →（池化）12 →（5×5 卷积）8 →（池化）4，flatten 后是 `16×4×4 = 256` 维，而 `fc1` 期望 400 维，`F.linear` 会抛出类似 `RuntimeError: mat1 and mat2 shapes cannot be multiplied (1x256 and 400x120)` 的错误。修法：把 MNIST 图像四周各填充 2 个像素到 32×32（LeNet 原论文的做法），或者给 `conv1` 加 `padding=2`。
2. `TinyResNet()(torch.randn(1, 3, 64, 64))` **正常运行**，输出 `(1, 10)`。形状：stem 后 `(1,32,64,64)` → layer1 `(1,32,64,64)` → layer2 `(1,64,32,32)` → layer3 `(1,128,16,16)` → layer4 `(1,256,8,8)` → `AdaptiveAvgPool2d(1)` → `(1,256,1,1)` → flatten → `(1,256)` → `(1,10)`。

差异的根源：LeNet 的分类头是 `Linear(16*5*5, 120)`，把"最后一张特征图必须是 5×5"写死在了参数形状里；TinyResNet / MiniVGG 用 `AdaptiveAvgPool2d(1)`，无论特征图多大都池化成 1×1，分类头只依赖通道数。这也是现代 backbone 可以直接在不同分辨率上微调的原因。

### Q10 — 参考答案

(a) **不会报错。** TinyResNet 中每次通道数变化（32→64、64→128、128→256）都恰好发生在 stride=2 的组首块，此时 bug 版本也会创建投影 shortcut；其余块都是 `in_c == out_c` 且 stride=1，恒等 shortcut 本来就正确。bug 被这组特定配置"掩盖"了。

(b) 例如把 layer1 改成 `self._make_group(32, 64, num_blocks=2, stride=1)`：第一个块 `in_c=32, out_c=64, stride=1`，shortcut 是 `nn.Identity()`。前向时主分支输出 `(N,64,H,W)`、shortcut 输出 `(N,32,H,W)`，在 `out = out + self.shortcut(x)` 这一行抛出 `RuntimeError`（通道维 64 与 32 无法广播）。真实例子：ResNet-50 的 layer1 第一个 Bottleneck 是 64→256 通道、stride=1，正是需要"只因通道变化"而投影的情况。

(c) 测试只覆盖了"恰好不会触发 bug"的配置。像 `BasicBlock` 这样的通用组件应当单独做**参数化测试**：遍历 `(in_c == out_c?, stride ∈ {1, 2})` 的四种组合，检查前向输出形状。本节 outputs 中的 residual-block-reviewer 把"shortcut 形状对齐"列为第一项检查，理由就是它是"最常见的崩溃原因"。

### Q11 — 参考答案

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, in_c, mid_c, stride=1):
        super().__init__()
        out_c = mid_c * self.expansion
        self.conv1 = nn.Conv2d(in_c, mid_c, kernel_size=1, bias=False)          # 1x1 降维
        self.bn1 = nn.BatchNorm2d(mid_c)
        self.conv2 = nn.Conv2d(mid_c, mid_c, kernel_size=3, stride=stride,
                               padding=1, bias=False)                           # 3x3（在窄通道上）
        self.bn2 = nn.BatchNorm2d(mid_c)
        self.conv3 = nn.Conv2d(mid_c, out_c, kernel_size=1, bias=False)         # 1x1 升维
        self.bn3 = nn.BatchNorm2d(out_c)
        if stride != 1 or in_c != out_c:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_c, out_c, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_c),
            )
        else:
            self.shortcut = nn.Identity()

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = F.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))
        return F.relu(out + self.shortcut(x))


if __name__ == "__main__":
    blk = Bottleneck(256, 64)
    print(blk(torch.randn(2, 256, 16, 16)).shape)   # torch.Size([2, 256, 16, 16])
```

（本环境未安装 PyTorch，以上代码未实际运行；形状与参数量按公式推导。）

参数量（只算卷积权重，`bias=False`）：

| 结构 | 计算 | 卷积参数 |
|------|------|---------|
| Bottleneck(256, 64) | `256×64×1 + 64×64×9 + 64×256×1 = 16,384 + 36,864 + 16,384` | **69,632** |
| BasicBlock(256, 256) | `2 × 256×256×9` | **1,179,648** |

Bottleneck 的卷积参数约为 BasicBlock 的 1/17。原因：昂贵的 3×3 卷积只在 64 通道上做，两端的 1×1 卷积负责升降维。注意 ResNet-50 layer1 的第一个块是 `Bottleneck(64, 64)`：输入 64、输出 256、stride=1，需要投影 shortcut——这就是 Q10 中"只看 stride"会出错的真实场景。

### Q12 — 参考回答要点

- **问题**：退化问题——普通网络加深到一定程度后，训练误差反而上升。这不是过拟合，而是优化困难。
- **核心机制**：
  1. **恒等映射变得容易**：普通层要学恒等映射很难，残差块只需把 `F(x)` 推向 0，于是"多加一层至少不会更差"，优化器可以让每个块"略微有用"；
  2. **梯度通路**：`∂L/∂x = ∂L/∂y·(∂F/∂x + I)`，梯度可以经由恒等项直接传到浅层；
  3. **学残差更容易**：如果最优映射接近恒等，学"与恒等的差"比从零学整个映射更容易。
- **常见误区**：直接说"ResNet 解决了梯度消失"不够准确。ResNet 原论文认为其普通网络已经用了 BN，前向信号和反向梯度的范数都正常，退化"不太可能是梯度消失造成的"；讲义里"梯度逐层连乘变小"的解释是一种直观说法，面试时最好把"退化/优化困难"与"梯度消失"区分开讲。
- **加分点**：提到 Pre-activation ResNet（v2）把 BN-ReLU 移到卷积前、让 shortcut 成为"纯恒等"路径，进一步改善了超深网络的训练；以及残差结构让损失曲面更平滑的相关研究。

### Q13 — 参考回答要点

- **做什么**：对每个通道，用当前 mini-batch 在 `(N, H, W)` 上的均值、方差做标准化，再用可学习的 γ（缩放）、β（偏移）恢复表达能力。
- **作用**：让每层输入的分布更稳定，可以用更大的学习率、对初始化不那么敏感，还有轻微的正则化效果。
- **训练 vs 推理**：训练时用当前 batch 的统计量，并用滑动平均更新 `running_mean / running_var`；推理（`model.eval()`）时用这些滑动平均值，输出与 batch 内其他样本无关。`main.py` 的 `summary` 先调用 `net.eval()` 再用 `torch.no_grad()` 前向，就是为了得到确定的推理行为、不更新统计量。
- **为什么可以不要 bias**：BN 减均值会抵消卷积的常数偏置，β 已经提供偏置（见 Q6）。
- **常见误区**：忘记 `model.eval()`，batch size 为 1 时用单样本统计量做标准化，结果飘忽不定；`running_mean` 是 buffer，不在 `parameters()` 里，所以 `sum(p.numel() for p in net.parameters())` 不会计入它们。

### Q14 — 参考回答要点

- **设计**：1×1 卷积把通道从 4m 降到 m → 在 m 通道上做 3×3 → 1×1 升回 4m，再加 shortcut。3×3 卷积的成本与通道数的平方成正比，在窄通道上做可以大幅省参数和计算（Q11：256 通道时卷积参数约为 BasicBlock 的 1/17）。
- **为什么 ResNet-50 用 Bottleneck**：深层网络的通道数很大（最后一组到 2048），用 BasicBlock 的成本无法接受；Bottleneck 让 ResNet-50 能做到 50 层，而计算量与 ResNet-34 同一量级。
- **为什么 ResNet-18/34 用 BasicBlock**：通道数较小（最大 512），BasicBlock 结构简单、计算密度高，在 GPU 上效率更好。
- **加分点**：Bottleneck 中两端的 1×1 卷积就是"逐像素的全连接层"；后续 ResNeXt 把中间的 3×3 换成分组卷积，MobileNetV2 则反过来做"先升维再降维"的倒残差（inverted residual）。

### Q15 — 参考回答要点

- **起点**：数据量小（5,000 张）、类别少，**不要从零训练大网络**，优先用 ImageNet 预训练的小型 backbone 做迁移学习（ResNet-18 或面向移动端的 MobileNet 类网络）。讲义提醒"不要一上来就用最大的模型——MNIST 不需要 ResNet"。
- **CPU 部署约束**：关注参数量与 FLOPs、实际延迟；ResNet-18 约 1170 万参数，CPU 上通常可接受；更紧的预算选 depthwise separable 结构的网络，并考虑降低输入分辨率、量化。
- **验证流程**：先用冻结 backbone + 线性头做基线；再解冻最后一两组微调；用混淆矩阵检查哪些缺陷类别容易混淆；在目标工控机上实测端到端延迟（含预处理）。
- **加分点**：缺陷往往很小，需要关注输入分辨率与感受野——下采样过多会把微小缺陷"平均掉"；类别不均衡时要用合适的评估指标（如每类召回率）而非只看准确率。

### Q16 — 参考回答要点

- **Transformer 中的残差**：每个子层（自注意力、前馈网络）都包在残差里：`x + Sublayer(...)`，与 ResNet 的 `F(x) + x` 完全同构。讲义原话："Every transformer ... has the exact same skip connection in every block."
- **Post-LN**（原始 Transformer）：`y = LN(x + F(x))`，LayerNorm 在残差相加之后，恒等通路上也要经过 LN；深层时训练不稳定，通常需要学习率 warmup。
- **Pre-LN**（GPT-2 及之后的多数 LLM）：`y = x + F(LN(x))`，恒等通路上没有任何变换，梯度可以直通，训练更稳定——思想上和 Pre-activation ResNet 一致。
- **加分点**：指出 CNN 中用 BatchNorm，而 Transformer 中用 LayerNorm（序列长度不定、batch 统计量不稳定）；残差连接也是模型可以"层剪枝 / 提前退出"的结构基础。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 02 从零实现卷积](../../02-convolutions-from-scratch/docs/zh.md)：输出尺寸公式、参数量、感受野、3×3 堆叠。
- [阶段 03 · 11 PyTorch 入门](../../../03-deep-learning-core/11-intro-to-pytorch/docs/zh.md)：`nn.Module`、`nn.Sequential`、`parameters()`。
- [阶段 03 · 04 激活函数](../../../03-deep-learning-core/04-activation-functions/docs/zh.md)：tanh 饱和与 ReLU。
- [阶段 03 · 07 正则化](../../../03-deep-learning-core/07-regularization/docs/zh.md)：Dropout、BatchNorm 的正则化效果。

### 本节被哪些后续内容用到
- [阶段 04 · 04 图像分类](../../04-image-classification/docs/zh.md)：在 CIFAR-10 上训练本节的网络，完整训练管线。
- [阶段 04 · 05 迁移学习与微调](../../05-transfer-learning/docs/zh.md)：冻结 backbone、替换 head 的完整做法。
- [阶段 04 · 06 物体检测 — YOLO](../../06-object-detection-yolo/docs/zh.md)、[阶段 04 · 07 语义分割 — U-Net](../../07-semantic-segmentation-unet/docs/zh.md)：backbone + 任务 head 的结构。
- [阶段 04 · 14 Vision Transformers](../../14-vision-transformers/docs/zh.md)：ViT 与 CNN 的归纳偏置对比，残差结构同样存在。
- [阶段 07 · 05 完整 Transformer](../../../07-transformers-deep-dive/05-full-transformer/docs/zh.md)：每个子层外的残差连接与 LayerNorm（Q16）。

### 延伸关键词
`Pre-activation ResNet` · `ResNeXt / 分组卷积` · `SE-Net` · `MobileNetV2 倒残差` · `DenseNet` · `ConvNeXt` · `全局平均池化（GAP）` · `Kaiming 初始化` · `zero-init residual`
