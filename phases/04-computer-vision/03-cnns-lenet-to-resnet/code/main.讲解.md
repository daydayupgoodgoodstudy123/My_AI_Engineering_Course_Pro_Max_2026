# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 03 节 CNNs — LeNet 到 ResNet ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：`torch`（只用到 `torch`、`torch.nn`、`torch.nn.functional`；不需要 torchvision、不下载数据、CPU 即可）

---

## 1. 这份代码在考察什么

1. **用三个时代的代表网络串起 CNN 演进史**：LeNet-5（1998）→ VGG 风格（2014）→ ResNet（2015），每个都在 40 行以内。
2. **PyTorch 模块化写法**：`nn.Module` 的 `__init__` 声明层、`forward` 描述数据流；用 `nn.Sequential` 和"工厂方法" `_make_group` 组装重复结构。
3. **残差块的正确实现**：shortcut 在什么条件下必须是投影（1×1 conv + BN），`bias=False` 与 BN 的配合，ReLU 在相加之后。
4. **参数量意识**：打印每个模型的总参数量 / 可训练参数量，以及 TinyResNet 各组的参数分布——学会"看到结构就能估算参数"。
5. **与输入尺寸解耦的分类头**：LeNet 用写死尺寸的 `Linear(16*5*5, 120)`，后两者用 `AdaptiveAvgPool2d(1)`。

> 一句话：**每个经典网络 = "卷积–非线性–下采样"配方 + 一个新想法**；这份代码让你亲手把这些想法拼起来，并量化它们的参数代价。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `LeNet5` | `nn.Module` 子类 | 2 个卷积–池化块 + 3 层全连接，tanh 激活 | LeNet 模板 |
| `VGGBlock` | `nn.Module` 子类 | 两个 3×3 卷积（+BN+ReLU）+ 2×2 最大池化 | 3×3 堆叠 |
| `MiniVGG` | `nn.Module` 子类 | 3 个 VGGBlock + 自适应池化分类头 | VGG 风格网络 |
| `BasicBlock` | `nn.Module` 子类 | conv-BN-ReLU-conv-BN-加 shortcut-ReLU | 残差块 |
| `TinyResNet` | `nn.Module` 子类 | stem + 4 组 × 2 个 BasicBlock + head | ResNet-18 的缩小版 |
| `summary` | 函数 | 推理模式前向一次，打印输入/输出形状、参数量 | 模型检查 |
| `per_group_params` | 函数 | 统计每个直接子模块的参数量 | 参数分布 |
| `main` | 函数 | 依次汇总三个模型，并打印 TinyResNet 的分组参数 | — |

数据流：`main` 对每个模型构造一个随机输入（LeNet 是 1 通道 32×32，另外两个是 3 通道 32×32），调用 `summary`；最后对一个新的 `TinyResNet` 调用 `per_group_params`。

---

## 3. 逐段精讲

### 3.1 `LeNet5`：所有 CNN 的模板

```python
class LeNet5(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 6, kernel_size=5)
        self.conv2 = nn.Conv2d(6, 16, kernel_size=5)
        self.pool = nn.AvgPool2d(2)
        self.fc1 = nn.Linear(16 * 5 * 5, 120)
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, num_classes)

    def forward(self, x):
        x = self.pool(torch.tanh(self.conv1(x)))
        x = self.pool(torch.tanh(self.conv2(x)))
        x = torch.flatten(x, 1)
        x = torch.tanh(self.fc1(x))
        x = torch.tanh(self.fc2(x))
        return self.fc3(x)
```

形状推导（输入 `(N, 1, 32, 32)`）：

| 步骤 | 输出形状 | 参数量 |
|------|---------|--------|
| conv1 5×5（无 padding） | `(N, 6, 28, 28)` | `1·6·25 + 6 = 156` |
| tanh + 平均池化 2×2 | `(N, 6, 14, 14)` | 0 |
| conv2 5×5 | `(N, 16, 10, 10)` | `6·16·25 + 16 = 2,416` |
| tanh + 平均池化 | `(N, 16, 5, 5)` | 0 |
| flatten | `(N, 400)` | 0 |
| fc1 → fc2 → fc3 | `(N, 120)` → `(N, 84)` → `(N, 10)` | 48,120 + 10,164 + 850 |

- `super().__init__()` 必须最先调用：它初始化 `nn.Module` 内部用来登记子模块和参数的字典，之后 `self.conv1 = ...` 这样的赋值才会被自动注册为子模块。
- `self.pool` 只定义一次、使用两次：池化没有参数，复用没有问题。（有参数的层如果复用，就会共享权重。）
- `torch.flatten(x, 1)` 从第 1 维开始展平，保留 batch 维。
- 最后一层**不加激活**，直接输出 logits，交给下游的 `nn.CrossEntropyLoss`（它内部包含 log-softmax）。讲义说这是对原论文"Gaussian connections"输出层唯一的现代化改动。
- ⚠️ `fc1` 的输入维度 `16 * 5 * 5` 把输入分辨率写死为 32×32：喂 28×28 的 MNIST 会在 fc1 处报形状不匹配（见测验 Q9）。

### 3.2 `VGGBlock` 与 `MiniVGG`：一种块，重复堆叠

```python
class VGGBlock(nn.Module):
    def __init__(self, in_c, out_c):
        super().__init__()
        self.conv1 = nn.Conv2d(in_c, out_c, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(out_c)
        self.conv2 = nn.Conv2d(out_c, out_c, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(out_c)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        return self.pool(x)
```

```python
        self.stack = nn.Sequential(
            VGGBlock(3, 32),
            VGGBlock(32, 64),
            VGGBlock(64, 128),
        )
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(128, num_classes),
        )
```

- `padding=1` 的 3×3 卷积保持空间尺寸，下采样完全交给 `MaxPool2d(2)`：32 → 16 → 8 → 4；通道 3 → 32 → 64 → 128。"空间减半、通道加倍"是贯穿 VGG 和 ResNet 的规律。
- 用了 BN（原版 VGG 没有 BN，这是现代化改动）。⚠️ 这里卷积保留了默认的 `bias=True`，后面紧跟 BN 时这个 bias 是冗余的（BN 会减掉均值）。功能正确，只是多了少量参数——可以和 `BasicBlock` 的 `bias=False` 对照。
- `F.relu`（函数式）与 `nn.ReLU()`（模块式）效果相同；无参数的操作写成函数式更简洁。
- **分类头**：`AdaptiveAvgPool2d(1)` 把任意 `H×W` 的特征图平均成 `1×1`（即全局平均池化），`Flatten` 得到 `(N, 128)`，再接一个线性层。这让网络对输入分辨率不敏感，也避免了 VGG-16 那种上亿参数的全连接头。
- 参数量约 28.9 万（讲义说 "~290k"）：三个块分别约 1.0 万、5.6 万、22.2 万，加上头部 1,290。

### 3.3 `BasicBlock`：残差块的标准写法

```python
class BasicBlock(nn.Module):
    def __init__(self, in_c, out_c, stride=1):
        super().__init__()
        self.conv1 = nn.Conv2d(in_c, out_c, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_c)
        self.conv2 = nn.Conv2d(out_c, out_c, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(out_c)
        if stride != 1 or in_c != out_c:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_c, out_c, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(out_c),
            )
        else:
            self.shortcut = nn.Identity()

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out = out + self.shortcut(x)
        return F.relu(out)
```

逐点拆解：

- **下采样放在第一个卷积**：`conv1` 带 `stride`，`conv2` 固定 stride 1。这样一个块最多下采样一次。
- **`bias=False`**：卷积后紧跟 BN，BN 的减均值会抵消常数偏置，β 已经提供偏移，所以卷积不需要 bias。
- **shortcut 的条件 `stride != 1 or in_c != out_c`**：两者任一成立，`x` 与主分支的形状就不同，必须用 1×1 卷积（带相同 stride）+ BN 投影。只判断 stride 是经典 bug，在 TinyResNet 这种"通道变化总伴随 stride 2"的配置下还会被掩盖（测验 Q10）。
- **`nn.Identity()`**：什么都不做的模块，原样返回输入。用它而不是在 `forward` 里写 `if`，可以让 `forward` 统一成一行 `out + self.shortcut(x)`。
- **激活顺序**：主分支最后一个 BN 之后**不加 ReLU**，先与 shortcut 相加，再整体 ReLU。即 conv-BN-ReLU-conv-BN-**add**-ReLU（讲义 Key Terms）。如果在相加前就 ReLU，主分支只能输出非负的修正量，残差只能"往上加"。
- `out = out + self.shortcut(x)` 用的是**非原地**加法，新建张量，不会破坏 autograd 需要保存的中间值。

### 3.4 `TinyResNet`：stem + 4 组 + head

```python
        self.stem = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
        )
        self.layer1 = self._make_group(32, 32, num_blocks=2, stride=1)
        self.layer2 = self._make_group(32, 64, num_blocks=2, stride=2)
        self.layer3 = self._make_group(64, 128, num_blocks=2, stride=2)
        self.layer4 = self._make_group(128, 256, num_blocks=2, stride=2)
        # ...

    def _make_group(self, in_c, out_c, num_blocks, stride):
        blocks = [BasicBlock(in_c, out_c, stride=stride)]
        for _ in range(num_blocks - 1):
            blocks.append(BasicBlock(out_c, out_c, stride=1))
        return nn.Sequential(*blocks)
```

- **stem**：CIFAR 尺寸（32×32）的图像很小，用 3×3 stride 1 的 stem，不下采样；ImageNet 版 ResNet 则用 7×7 stride 2 + 最大池化（讲义 Key Terms "Stem"）。
- `nn.ReLU(inplace=True)`：直接在输入张量上改写，省一份显存。这里安全，因为 BN 的输出在 ReLU 之后不再被别处使用。
- **`_make_group` 工厂方法**：每组第一个块负责变通道/下采样，其余块是 `out_c→out_c, stride=1`。`nn.Sequential(*blocks)` 用 `*` 把列表解包成多个位置参数。方法名前的下划线表示"内部使用"。
- 形状（输入 32×32）：stem `32×32×32` → layer1 `32×32×32` → layer2 `64×16×16` → layer3 `128×8×8` → layer4 `256×4×4` → head `(N, 10)`。
- 每组 2 个块、共 4 组，与 ResNet-18 的 `[2, 2, 2, 2]` 结构相同，只是通道减半（32/64/128/256 vs 64/128/256/512）、stem 更小。

### 3.5 `summary` 与 `per_group_params`

```python
def summary(name, net, x):
    net.eval()
    with torch.no_grad():
        y = net(x)
    params = sum(p.numel() for p in net.parameters())
    trainable = sum(p.numel() for p in net.parameters() if p.requires_grad)
    print(f"{name:12s}  input {tuple(x.shape)} -> output {tuple(y.shape)}   "
          f"params {params:>10,}   trainable {trainable:>10,}")


def per_group_params(net):
    return {name: sum(p.numel() for p in mod.parameters()) for name, mod in net.named_children()}
```

- `net.eval()`：切换到推理模式——BN 使用 running statistics 而非当前 batch 的统计量，Dropout 关闭。batch size 为 1 时这一步尤其重要。
- `with torch.no_grad():`：前向时不构建计算图，省内存、省时间。注意 `eval()` 和 `no_grad()` 是两件独立的事：前者改变层的行为，后者关闭梯度记录。
- `p.numel()` 返回张量的元素个数；用生成器表达式求和得到参数总数。`trainable` 只统计 `requires_grad=True` 的参数——这里两者相等，但在迁移学习冻结 backbone 后（讲义 Use It 部分），二者就会不同，这个打印格式正是为下一节准备的。
- ⚠️ BN 的 `running_mean` / `running_var` 是 **buffer**，不在 `parameters()` 里，不计入参数量。
- `named_children()` 只遍历**直接**子模块（stem、layer1…layer4、head），而 `mod.parameters()` 会递归统计子模块内部所有参数。字典推导式一行完成。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| LeNet 保留 tanh + 平均池化 | 忠实还原 1998 年的设计，便于对比 | 现代网络用 ReLU + 最大池化或 stride 卷积 |
| LeNet 头部写死 `16*5*5` | 与原论文一致 | 输入尺寸不能变；现代做法用自适应池化 |
| VGG/ResNet 用 `AdaptiveAvgPool2d(1)` 头 | 与分辨率解耦，参数极少 | 丢失空间信息；检测/分割任务需要别的 head |
| VGGBlock 中卷积保留 bias | 代码简洁，与讲义一致 | 与 BN 搭配时冗余；更规范的写法是 `bias=False` |
| shortcut 条件同时判断 stride 和通道 | 任何形状变化都投影 | 投影带来额外参数；也有用"池化 + 补零通道"的无参数 shortcut（ResNet 论文的选项 A） |
| `_make_group` 工厂方法 | 结构规则化，改深度只需改 `num_blocks` | — |
| `summary` 中 `eval()` + `no_grad()` | 推理语义正确、开销小 | 训练时要记得切回 `train()` |
| 随机输入、不训练 | 本节只关心形状和参数量 | 讲义给出的 CIFAR-10 准确率（约 60%/89%/93%）需要真实训练才能得到 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import ... as ...` | `import torch.nn as nn`、`import torch.nn.functional as F` | 给模块起短别名，是 PyTorch 社区惯例 |
| 类继承 | `class LeNet5(nn.Module):` | 继承 `nn.Module` 获得参数注册、`.eval()`、`.parameters()` 等能力 |
| `super().__init__()` | 每个 `__init__` 第一行 | 调用父类构造函数；漏掉它，给 `self` 赋值子模块时会报错 |
| 默认参数 | `def __init__(self, num_classes=10)`、`stride=1` | 调用时可省略 |
| 关键字参数 | `nn.Conv2d(in_c, out_c, kernel_size=3, stride=stride, padding=1, bias=False)` | 按名字传参，可读性好、不怕顺序错 |
| `__call__` 与 `forward` | `net(x)` 实际调用 `forward(x)` | `nn.Module.__call__` 会做钩子等额外处理后再调 `forward`，所以应写 `net(x)` 而非 `net.forward(x)` |
| `_` 占位变量 | `for _ in range(num_blocks - 1):` | 不需要循环变量时的惯用写法 |
| 下划线前缀方法 | `def _make_group(...)` | 约定为"内部方法"，不是语言层面的私有 |
| `*` 解包 | `nn.Sequential(*blocks)` | 把列表展开成多个位置参数 |
| `with` 上下文管理器 | `with torch.no_grad():` | 进入时关闭梯度记录，退出时自动恢复 |
| 生成器表达式 + 条件 | `sum(p.numel() for p in net.parameters() if p.requires_grad)` | 边遍历边过滤边求和，不建中间列表 |
| 字典推导式 | `{name: ... for name, mod in net.named_children()}` | 一行构造字典 |
| f-string 格式符 | `f"{name:12s}"`、`f"{params:>10,}"`、`f"{name:8s}"` | `12s` 字符串左对齐占 12 格；`>10,` 右对齐占 10 格并加千分位逗号 |
| 相邻字符串拼接 | `print(f"..." f"...")` | 括号内相邻的字符串字面量自动拼接，便于换行 |
| `tuple()` 转换 | `tuple(x.shape)` | 把 `torch.Size` 转成普通元组打印 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 以下输出根据代码中的层定义逐层计算参数量，并按 `summary` / `per_group_params` 的格式字符串推得：

```text
LeNet5        input (1, 1, 32, 32) -> output (1, 10)   params     61,706   trainable     61,706
MiniVGG       input (1, 3, 32, 32) -> output (1, 10)   params    289,194   trainable    289,194
TinyResNet    input (1, 3, 32, 32) -> output (1, 10)   params  2,797,610   trainable  2,797,610

TinyResNet parameters by group:
  stem             928
  layer1        37,120
  layer2       131,712
  layer3       525,568
  layer4     2,099,712
  head           2,570
```

解读：

- **输出形状**都是 `(1, 10)`：三个模型都是 10 类分类器。
- **LeNet5 = 61,706**：与讲义 Step 1 给出的数字一致；其中 fc1 就占 48,120（约 78%）。
- **MiniVGG ≈ 28.9 万**：讲义说 "~290k"。
- **TinyResNet ≈ 280 万**：讲义说 "Roughly 2.8M"。三个模型的参数量跨度约 45 倍（讲义称"三个数量级"，实际约为一个半到两个数量级）。
- **params = trainable**：没有冻结任何参数。下一节迁移学习中冻结 backbone 后，`trainable` 会远小于 `params`。
- **分组参数**：layer4 一组就有约 210 万，占总量约 75%。原因：3×3 卷积参数 ∝ `C_in·C_out`，通道每翻一倍参数翻四倍。卷积权重合计约 279 万，BN 参数（γ、β）只有 4,800 个，分类头 2,570 个——这回答了讲义练习 1 "参数主要花在哪里"：**几乎全在卷积，而且集中在最深的一组**。
- stem 只有 928 个参数：`3×32×9 = 864` 加 BN 的 64。

---

## 7. 动手改一改

1. （易）把 `LeNet5` 的 `conv1` 改成 `nn.Conv2d(1, 6, kernel_size=5, padding=2)`，让它接受 28×28 的 MNIST 输入；推导新的参数量是否变化。
2. （易）把 `VGGBlock` 中的卷积改成 `bias=False`，计算 MiniVGG 参数量减少多少（提示：每个卷积少 `out_c` 个）。
3. （中）写一个参数化测试：对 `BasicBlock` 遍历 `(in_c, out_c, stride)` ∈ `{(32,32,1), (32,64,1), (32,32,2), (32,64,2)}`，断言输出形状正确；再把 shortcut 条件改成只看 stride，确认测试能抓到 bug。
4. （中）实现 Bottleneck 块（1×1 → 3×3 → 1×1，扩张系数 4），搭一个 ResNet-50 风格的 CIFAR 网络，与 TinyResNet 比较参数量（讲义练习 2）。
5. （中）把 `BasicBlock` 改成 pre-activation 版本（BN-ReLU-conv-BN-ReLU-conv-add，相加后不再 ReLU），比较两种版本在同样输入下的输出分布（均值、是否有负值）。
6. （难）去掉 skip connection，分别堆 34 个块的普通网络与 ResNet，在 CIFAR-10 上各训练 10 个 epoch，画训练损失曲线，复现 He 等人 Figure 1 的退化现象（讲义练习 3）。

---

## 8. 常见坑

- **shortcut 条件只看 stride**：通道变化但 stride=1 时形状不匹配；在某些配置下 bug 被掩盖。
- **相加前就做 ReLU**：主分支只能输出非负修正，偏离标准 BasicBlock 的设计。
- **忘记 `model.eval()`**：BN 用当前 batch 统计量，batch 很小时输出不稳定，评测结果偏差大。
- **把 `parameters()` 当成全部状态**：BN 的 running statistics 是 buffer，保存/加载模型要用 `state_dict()`。
- **全连接头写死输入尺寸**：换分辨率就报错；需要灵活性时用自适应池化。
- **`inplace=True` 用在还会被复用的张量上**：会破坏 autograd 需要的值，报 "modified by an inplace operation" 错误。
