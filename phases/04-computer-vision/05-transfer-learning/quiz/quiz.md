# 测验 · 迁移学习与微调（Transfer Learning & Fine-Tuning）

> **阶段 04 · 计算机视觉 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么能迁移 | ImageNet 上学到的浅层特征（边缘、Gabor 状滤波器、纹理）反映的是自然图像的统计规律，几乎在所有视觉领域通用；越深的层越专门化 |
| 2 | 特征提取 vs 微调 | 特征提取：冻结 backbone、只训练新 head（linear probe）；微调：端到端训练，backbone 用很小的学习率 |
| 3 | 按数据量与领域距离选方案 | <1k 张且接近 ImageNet → 只训 head；1k–10k → 冻结前 2–3 个 stage；10k–100k → 端到端 + 分层学习率；100k+ 且领域很远 → 全部微调甚至从零训练 |
| 4 | 分层学习率（discriminative LR） | 用优化器的参数组（param groups）给浅层更小、深层更大的学习率；本节代码 decay=0.3，conv1 的学习率只有 head 的 0.3⁵ ≈ 0.00243 倍 |
| 5 | 逐层学习率衰减（layer-wise LR decay） | `lr_k = base_lr · decay^(L−k)`，更平滑的版本，常用于 ViT/BEiT/DINOv2 微调 |
| 6 | 渐进式解冻 | 从最后一个 stage 开始每个 epoch 解冻一个；可训练参数集合变化后要重建优化器（或用 `add_param_group`） |
| 7 | BatchNorm 问题 | running_mean/var 来自 ImageNet；三种做法：BN 在 train 模式随微调更新（数据 ≥5k）、BN 保持 eval 模式冻结统计量（小数据）、换成 GroupNorm（小 batch） |
| 8 | head 的替换 | ResNet 改 `model.fc`，EfficientNet/MobileNet 改 `classifier[1]`，torchvision ViT 改 `heads.head`；小数据通常一个线性层就够 |
| 9 | 两个必看的数字 | linear probe 准确率是下限，微调准确率是上限；微调反而更低 ⇒ 学习率或 BN 有 bug |
| 10 | 灾难性遗忘 / 坍塌 | 学习率太高会在新任务信号到来之前把预训练特征冲掉，极端时所有输入都预测同一类 |

### 核心技能（能动手做到）

- [ ] 加载 torchvision 预训练 ResNet-18，冻结全部参数并替换 `fc`，打印可训练 / 冻结参数量（10 类时可训练参数为 5,130）
- [ ] 写出 `discriminative_param_groups`，按 stage 名前缀构建参数组，并能心算每组的学习率
- [ ] 解释 `requires_grad=False` 与 `module.eval()` 各自控制什么，并写出"只冻结 BN 统计量、不冻结 BN 权重"的函数
- [ ] 检查一次"特征提取"训练中 backbone 是否真的没变（包括 BN 的 running statistics）
- [ ] 实现渐进式解冻，并在每次解冻后正确地重建优化器
- [ ] 根据数据量、领域距离和算力预算，给出特征提取 / 部分微调 / 端到端微调的选择理由

---

## 二、基础自测（选择题）

**Q1.** 你有 500 张标注图片，任务是区分几种家具，图片是普通的自然照片。最合适的起点是：

- A. 从零训练一个 ResNet-50
- B. 加载 ImageNet 预训练 backbone，所有层用同一个较大学习率端到端训练
- C. 加载 ImageNet 预训练 backbone，冻结它，只训练新的线性分类头
- D. 不用预训练权重，换一个更小的网络从零训练

**Q2.** 关于 PyTorch 中的 `p.requires_grad = False` 和 `module.eval()`，下列说法正确的是：

- A. 两者等价，任选其一即可冻结一个 BN 层
- B. `requires_grad=False` 只阻止该参数被梯度更新；BN 处于 train 模式时，其 `running_mean/var` 仍会在每次前向时被更新
- C. `module.eval()` 会阻止梯度回传到该模块的参数
- D. `requires_grad=False` 会让 BN 使用 running statistics 做标准化

**Q3.** 用 `discriminative_param_groups(model, base_lr=1e-3, decay=0.3)` 处理一个全部可训练的 ResNet-18，`layer3` 组的学习率是：

- A. 3.00e-4
- B. 9.00e-5
- C. 2.70e-5
- D. 1.00e-3

**Q4.** 同一数据集上：(a) 冻结 backbone 的 linear probe 得到 82%；(b) 端到端微调得到 78%。最合理的结论是：

- A. 微调没用，直接上线 linear probe
- B. 预训练权重质量差
- C. 微调结果低于 linear probe 几乎总是训练 bug（backbone 学习率太高、BN 处理不当、调度器/优化器配置错误），应先排查
- D. 数据集太大了

**Q5.** 对 12 个 Transformer block 的 ViT 使用 layer-wise LR decay，`decay = 0.75`。第 1 个 block 的学习率约为 head 学习率的多少？

- A. 0.75
- B. 0.24
- C. 0.042
- D. 0.0024

**Q6.** 你在做目标检测，单卡 batch size 只有 2，backbone 是带 BN 的 ImageNet 预训练 ResNet。处理 BN 的常见做法是：

- A. 保持 BN 在 train 模式，用每个 batch 的统计量
- B. 冻结 BN 的统计量（eval 模式），或者把 BN 换成 GroupNorm
- C. 删除所有 BN 层，不做任何替代
- D. 把学习率调大 10 倍以弥补

**Q7.** 用 ImageNet 预训练的 ResNet-18 在一个新数据集上微调，输入图像的标准化应该使用：

- A. 新数据集自己统计的 mean/std，因为数据分布变了
- B. 预训练时使用的 ImageNet mean/std，因为第一层卷积和 BN 统计量是在那个输入分布上学到的
- C. 不做标准化，只除以 255
- D. 每张图片各自做零均值单位方差

---

## 三、动手 / 代码题

**Q8.** 预测 `main.py` 中下面这段的输出，并回答：对 `make_feature_extractor()` 得到的模型调用同一个函数（`base_lr=3e-2`），会生成几个参数组？学习率是多少？可训练参数一共多少个？

```python
    ft = make_fine_tune()
    for g in discriminative_param_groups(ft, base_lr=1e-3):
        print(f"  group {g['name']:>10s}  lr={g['lr']:.2e}")
```

```python
def discriminative_param_groups(model, base_lr=1e-3, decay=0.3):
    stages = [["conv1", "bn1"], ["layer1"], ["layer2"], ["layer3"], ["layer4"], ["fc"]]
    groups = []
    for i, names in enumerate(stages):
        lr = base_lr * (decay ** (len(stages) - 1 - i))
        params = [p for n, p in model.named_parameters()
                  if any(n.startswith(k) for k in names) and p.requires_grad]
        if params:
            groups.append({"params": params, "lr": lr, "name": "_".join(names)})
    return groups
```

**Q9.** 讲义说 `freeze_bn_stats` 是"冻结 BN 运行统计量、但**不**冻结其权重"的辅助函数。对照代码，指出说法与实现的不一致，并改写出一个符合该描述的版本；再说明什么情况下你会想同时冻结 BN 的权重。

```python
def freeze_bn_stats(model):
    for m in model.modules():
        if isinstance(m, (nn.BatchNorm1d, nn.BatchNorm2d, nn.BatchNorm3d)):
            m.eval()
            for p in m.parameters():
                p.requires_grad = False
    return model
```

**Q10.** `main.py` 的特征提取实验调用 `train_and_eval(fe, ..., base_lr=3e-2)`（`freeze_bn` 默认为 False），而 `train_and_eval` 每个 epoch 开头都执行 `model.train()`。

(a) 这次"冻结 backbone"的训练结束后，backbone 是否真的完全没变？
(b) 写一段代码验证你的判断。
(c) 怎样改才能得到严格意义上的 linear probe？

**Q11.** 讲义 Step 6 给出了渐进式解冻（每个 epoch 从 `layer4` 往前解冻一个 stage），并提醒"可训练参数集合变化时要重建优化器"。

(a) 结合 `main.py` 的 `discriminative_param_groups`（只收集 `requires_grad=True` 的参数），说明如果**不**重建优化器，新解冻的 `layer4` 会怎样？会报错吗？
(b) 写一个 `progressive_fine_tune(model, train_loader, device, base_lr=1e-3, epochs=4)`，每个 epoch 解冻一个 stage 并正确地更新优化器。

---

## 四、面试高频题

**Q12.**（基础必考）特征提取和微调有什么区别？给你一个新任务，你会怎样根据数据量、领域距离和算力选择方案？

**Q13.**（原理深挖）什么是分层学习率（discriminative LR）、逐层学习率衰减和渐进式解冻？它们背后的共同直觉是什么？在 PyTorch 中怎么实现？

**Q14.**（原理深挖）迁移学习中 BatchNorm 为什么会出问题？有哪些处理方式，分别适用于什么场景？

**Q15.**（场景设计）你拿到 2,000 张胸部 X 光片（灰度、3 个类别），要基于 ImageNet 预训练 CNN 做分类。请给出完整方案。

**Q16.**（追问型）什么是灾难性遗忘？在 CNN 微调中怎样检测和缓解？这和大模型微调里的 LoRA 有什么联系？

---

## 五、参考答案与解析

### Q1 — 答案：C

数据量 < 1k 且领域接近 ImageNet（自然照片），按讲义的经验表应"冻结 backbone，只训练 head"。500 张图不足以从零训练深网络（A、D），也不足以支撑用大学习率端到端更新上千万参数（B）——那样很容易破坏预训练特征、严重过拟合。

### Q2 — 答案：B

二者控制的是不同的东西：`requires_grad=False` 只决定参数是否计算梯度、是否会被优化器更新；`train()/eval()` 决定 BN 和 Dropout 的**行为**——BN 在 train 模式下用当前 batch 的统计量做标准化，并用滑动平均更新 `running_mean/var`（它们是 buffer，不是参数，不受 `requires_grad` 控制）。所以 A、D 错；`eval()` 不影响梯度计算，C 错。这正是 Q10 中"冻结的 backbone 其实变了"的根源。

### Q3 — 答案：B

`stages` 共 6 组，`layer3` 的下标 i=3，`lr = 1e-3 × 0.3^(6−1−3) = 1e-3 × 0.09 = 9.00e-5`。A 是 layer4（0.3¹），C 是 layer2（0.3³），D 是 fc（0.3⁰）。

### Q4 — 答案：C

linear probe 可以看成"backbone 学习率为 0"的微调特例，所以正确配置的微调至少应该和它一样好。讲义："If fine-tuned is less than pretrained-only, you have a learning-rate or BN bug. Always print both." 正确做法是降低 backbone 学习率、使用分层学习率或冻结 BN，而不是放弃微调。

### Q5 — 答案：C

`lr_1 = base_lr × 0.75^(12−1) = base_lr × 0.75^11 ≈ 0.042 × base_lr`，与讲义给出的 "≈ 0.04x" 一致。B 约是 0.75⁵，D 是本节 CNN 分组方案里 conv1 的倍数（0.3⁵ ≈ 0.00243），用于混淆。

### Q6 — 答案：B

batch 只有 2 时，每个 batch 的均值/方差噪声极大，BN 在 train 模式下既会用这些噪声统计量做标准化，又会把它们混入 running statistics。讲义列出的做法：冻结 BN（eval 模式，保留 ImageNet 统计量），或换成不依赖 batch 统计量的 GroupNorm——后者"Used in detection and segmentation backbones where batch size per GPU is tiny"。

### Q7 — 答案：B

预训练权重（尤其第一层卷积和各层 BN 的 running statistics）都是在"ImageNet 标准化后的输入分布"上学到的，微调时应保持同样的输入约定。`main.py` 的 `ArrayDataset` 就使用了 ImageNet 的 mean/std。这与第 04 节"从零训练 CIFAR-10 时用 CIFAR 自己的统计量"并不矛盾：**标准化统计量跟着模型权重走**——从零训练用自己数据集的，复用预训练权重就用预训练时的。

### Q8 — 参考答案

输出（`.2e` 格式、名字右对齐 10 格；已用纯 Python 按同样的格式字符串验证）：

```text
  group  conv1_bn1  lr=2.43e-06
  group     layer1  lr=8.10e-06
  group     layer2  lr=2.70e-05
  group     layer3  lr=9.00e-05
  group     layer4  lr=3.00e-04
  group         fc  lr=1.00e-03
```

每组学习率是 `1e-3 × 0.3^k`，k 从 5 递减到 0。`n.startswith("conv1")` 只匹配顶层的 `conv1.weight`，因为 `layer1.0.conv1.weight` 这类嵌套参数名以 `layer1.` 开头，不会被误收进第一组。

对特征提取模型：backbone 的所有参数 `requires_grad=False`，被 `and p.requires_grad` 过滤掉，只剩 `fc` 一组，学习率 `3e-2 × 0.3⁰ = 3e-2`。可训练参数 = `512 × 10 + 10 = 5,130`（`main.py` 会打印 `trainable params: 5,130`）。函数里的 `if not groups:` 兜底分支在这里不会触发，它是为"参数名不符合 ResNet 命名"的其他模型准备的。

### Q9 — 参考答案

不一致：函数除了 `m.eval()`（冻结统计量）之外，还把 BN 的 γ、β 设成了 `requires_grad = False`——**权重也被冻结了**，与"without freezing its weights"的描述相反。

符合描述的版本：

```python
def freeze_bn_stats(model, freeze_affine=False):
    for m in model.modules():
        if isinstance(m, (nn.BatchNorm1d, nn.BatchNorm2d, nn.BatchNorm3d)):
            m.eval()                         # 用 running stats 做标准化，且不再更新它们
            if freeze_affine:                # 默认只冻结统计量，γ/β 仍可学习
                for p in m.parameters():
                    p.requires_grad = False
    return model
```

注意事项：

- 必须在每个 epoch 的 `model.train()` **之后**调用，否则 `train()` 会把 BN 重新切回训练模式（讲义 Step 4 已强调）。
- 什么时候连 γ/β 一起冻结：数据非常少、或单卡 batch 很小时（例如检测任务），连仿射参数也冻结可以进一步减少过拟合和不稳定；目标检测框架中常见的 `FrozenBatchNorm2d` 就是"统计量和仿射参数全冻结"的做法。

### Q10 — 参考答案

(a) **没有完全不变。** 卷积权重和 BN 的 γ/β 确实没有更新（`requires_grad=False`，也不在优化器里），但每个 epoch 开头的 `model.train()` 让所有 BN 层进入训练模式：前向时用当前 batch（合成数据）的统计量做标准化，并把 `running_mean/var` 朝合成数据的分布滑动更新。所以这并不是严格的 linear probe——backbone 的"特征"在训练过程中悄悄变了，而且训练（batch 统计量）与验证（被改过的 running 统计量）时的标准化方式也不一致。

(b) 验证代码：

```python
fe = make_feature_extractor()
before = fe.bn1.running_mean.clone()
train_and_eval(fe, train_loader, val_loader, device, epochs=1, base_lr=3e-2)
after = fe.bn1.running_mean.detach().cpu()
print(torch.equal(before, after))          # 预期为 False：统计量已被更新
print((before - after).abs().max())         # 变化幅度
```

（本环境未安装 torch / torchvision，且加载预训练权重需要联网，以上未实际运行；结论由 BN 在 train 模式下的定义直接推出。）

(c) 修法任选其一：

- 直接调用 `train_and_eval(fe, ..., freeze_bn=True)`：每个 epoch `model.train()` 之后把所有 BN 切回 eval；特征提取模型的 BN 参数本来就冻结了，`freeze_bn_stats` 的副作用无影响。
- 更彻底：训练时 `model.eval()` 整个模型，只让 head 处于训练模式（`model.fc.train()`；它是普通 `Linear`，模式其实不影响它）。
- 性能更好的做法：先把整个训练集通过冻结的 backbone 前向一次，缓存 512 维特征，再在特征上训练线性层——这才是"linear probe"在研究中的常见实现，速度也快得多。

### Q11 — 参考答案

(a) 不会报错，但 `layer4` **永远不会被更新**。优化器在构建时只拿到了当时 `requires_grad=True` 的参数（只有 fc）；之后把 `layer4` 设为可训练，反向传播会为它计算梯度（白白花算力），但 `optimizer.step()` 只遍历自己持有的参数，`layer4` 的权重纹丝不动。这是典型的 silent bug——本节 outputs 中的 freeze-inspector skill 专门检查"优化器是否真的拿到了可训练参数"。

(b) 参考实现：

```python
from torch.optim import SGD
import torch.nn.functional as F

def progressive_fine_tune(model, train_loader, device, base_lr=1e-3, epochs=4):
    stages = ["layer4", "layer3", "layer2", "layer1"]
    model = model.to(device)
    for p in model.parameters():                 # 先全部冻结
        p.requires_grad = False
    for p in model.fc.parameters():              # 只放开 head
        p.requires_grad = True

    for epoch in range(epochs):
        if epoch < len(stages):                  # 每个 epoch 从后往前解冻一个 stage
            for n, p in model.named_parameters():
                if n.startswith(stages[epoch]):
                    p.requires_grad = True
        groups = discriminative_param_groups(model, base_lr=base_lr)   # 只收集当前可训练的参数
        optimizer = SGD(groups, momentum=0.9, weight_decay=1e-4, nesterov=True)  # 解冻后重建

        model.train()
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            loss = F.cross_entropy(model(x), y, label_smoothing=0.1)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    return model
```

取舍：每个 epoch 重建优化器会丢掉已训练参数组的动量缓存。另一种做法是保留原优化器，对新解冻的参数调用 `optimizer.add_param_group({"params": new_params, "lr": ...})`，这样旧参数的动量得以保留。（未实际运行：环境缺少 torch。）

### Q12 — 参考回答要点

- **定义**：特征提取 = backbone 冻结，只训练新 head，本质是用预训练网络做固定的特征编码器；微调 = 所有（或大部分）参数参与训练，backbone 用比从零训练小得多的学习率。
- **选择依据**（讲义经验表）：
  - 数据 < 1k、领域接近 → 只训 head；
  - 1k–10k、领域接近 → 冻结前 2–3 个 stage，微调其余；
  - 10k–100k → 端到端 + 分层学习率；
  - 100k+ 且领域很远（医学、遥感、显微镜）→ 全部微调，必要时考虑从零训练。
- **算力**：特征提取可以预先缓存特征，训练极快；端到端微调需要完整的前向+反向。
- **加分点**：两种方案都要跑，打印 linear probe（下限）和微调（上限）两个数字；按讲义练习 1 的思路，二者差距小说明特征迁移得好，差距大说明需要让更多层适应新领域。

### Q13 — 参考回答要点

- **共同直觉**：浅层是通用特征（边缘、纹理），要**保护**；深层越来越任务相关，要**多改**。所以学习率应该从浅到深递增。
- **分层学习率**：把网络按 stage 分组，每组一个学习率，例如本节 decay=0.3：fc 1e-3、layer4 3e-4……conv1 约 2.4e-6。
- **逐层学习率衰减**：更细粒度，每一层一个学习率 `base_lr · decay^(L−k)`，Transformer 微调中常用（decay 0.75、12 层时第 1 层约为 0.042 倍）。
- **渐进式解冻**：先只训 head，再按 epoch 从后往前逐个解冻 stage，降低一开始就破坏特征的风险（源自 ULMFiT）。
- **PyTorch 实现**：优化器接受参数组列表 `[{"params": [...], "lr": ...}, ...]`，每组可以有自己的超参数；参数组字典里还可以放 `"name"` 这样的自定义键，便于打印。
- **常见误区**：解冻后不重建优化器（新参数不在优化器里）；把同一个参数放进两个组（PyTorch 会报错）。

### Q14 — 参考回答要点

- **问题来源**：BN 的 `running_mean/var` 是在 ImageNet 上统计的。新任务的像素分布不同（光照、传感器、色彩空间），这些统计量就是错的；而在小数据、小 batch 上更新它们又会引入噪声。讲义称处理不当会"悄悄损失 5–15% 的准确率"。
- **三种做法**（讲义按优先级排列）：
  1. **BN 保持 train 模式**，随微调更新统计量——数据量中等以上（≥5k）时的默认选择；
  2. **冻结 BN（eval 模式）**，保留 ImageNet 统计量——数据很少时，避免噪声很大的滑动平均；
  3. **换成 GroupNorm**——彻底去掉对 batch 统计量的依赖，检测/分割中单卡 batch 很小时常用。
- **易错点**：`requires_grad=False` 不能冻结 running statistics（Q2、Q10）；`freeze_bn_stats` 必须在 `model.train()` 之后调用。
- **加分点**：原 quiz.json 还提到可以先做一次"只更新 BN 统计量"的预热前向（在目标数据上以 train 模式前向若干 batch，不更新权重），让统计量适配新分布。

### Q15 — 参考回答要点

1. **输入适配**：灰度图复制成 3 通道（或修改第一层为单通道，权重取原 RGB 三个通道权重之和）；按预训练模型的约定做 ImageNet 标准化；保持宽高比做 resize/pad，注意病灶尺度不要被下采样抹掉。
2. **方案选择**：2,000 张、领域远离 ImageNet（医学影像）→ 讲义指出"特征仍然有用，但需要让更多层适应"。先跑冻结 backbone 的 linear probe 作为下限，再做端到端微调 + 分层学习率。
3. **BN**：数据量不大，可以先试冻结 BN 统计量，与"BN 随微调更新"做对比实验；batch 很小时考虑 GroupNorm。
4. **训练细节**：head 学习率较大、backbone 学习率小；余弦退火；label smoothing；选择不改变诊断语义的增强（例如胸片的水平翻转会改变心脏位置，需要谨慎）。
5. **评估**：按病人划分 train/val，避免同一病人的片子同时出现在两边；看每类 recall（漏诊代价高）、混淆矩阵和校准。
6. **对照**：可按讲义练习 3 比较"冻结 + 线性头 / 端到端微调 / 从零训练"三种方案的准确率与算力成本。

### Q16 — 参考回答要点

- **定义**：微调时学习率过高（或训练过久），在新任务信号稳定下来之前就覆盖了预训练特征，模型"忘掉"了原有的通用表示；极端情况是讲义所说的 catastrophic collapse——所有输入都预测同一类。
- **检测**：微调准确率低于 linear probe；训练初期损失突然上升；在原任务（或通用基准）上的表现大幅下降；查看各层权重相对预训练值的变化幅度。
- **缓解**：更小的 backbone 学习率、分层学习率、渐进式解冻、学习率 warmup、更短的训练、冻结 BN；还可以加正则项把权重拉向预训练值（例如 L2-SP 这类"以预训练权重为中心"的正则）。
- **与 LoRA 的联系**：思想一致——**尽量不动预训练权重**。LoRA 冻结原权重 `W₀`，只训练低秩增量 `ΔW = B·A`，天然限制了更新的幅度和方向，既省显存又减轻遗忘；CNN 中的"冻结 backbone + 训练 head"可以看作它的极端形式。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 03 CNNs — LeNet 到 ResNet](../../03-cnns-lenet-to-resnet/docs/zh.md)：ResNet 的 stem / layer1–4 / fc 结构，BasicBlock 中的 BN。
- [阶段 04 · 04 图像分类](../../04-image-classification/docs/zh.md)：训练循环五条不变式、余弦退火、label smoothing。
- [阶段 04 · 01 图像基础知识](../../01-image-fundamentals/docs/zh.md)：ImageNet 标准化与预处理契约。

### 本节被哪些后续内容用到
- [阶段 04 · 06 物体检测 — YOLO](../../06-object-detection-yolo/docs/zh.md)、[阶段 04 · 07 语义分割 — U-Net](../../07-semantic-segmentation-unet/docs/zh.md)：预训练 backbone + 新任务 head，小 batch 下的 BN 处理。
- [阶段 04 · 14 Vision Transformers](../../14-vision-transformers/docs/zh.md)：ViT 微调与 layer-wise LR decay。
- [阶段 04 · 17 自监督视觉](../../17-self-supervised-vision/docs/zh.md)：linear probe 是评估自监督表示的标准协议。
- [阶段 04 · 18 开放词表视觉 — CLIP](../../18-open-vocab-clip/docs/zh.md)：真正意义上的 zero-shot 分类（与"训练线性头"区分）。
- [阶段 11 · 08 LoRA 微调](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：大模型中"冻结主干、只训少量参数"的同一思想。

### 延伸关键词
`linear probe` · `ULMFiT` · `FrozenBatchNorm2d` · `GroupNorm` · `L2-SP` · `timm` · `optimizer.add_param_group` · `domain shift` · `parameter-efficient fine-tuning（PEFT）`
