# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 05 节 迁移学习与微调（Transfer Learning & Fine-Tuning） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数；有 CUDA 时自动用 GPU） ｜ **依赖**：`numpy`、`torch`、`torchvision`；首次运行时 `ResNet18_Weights.IMAGENET1K_V1` 需要**联网下载**预训练权重（约几十 MB，缓存到本地后可离线使用）

---

## 1. 这份代码在考察什么

1. **复用预训练 backbone**：加载 torchvision 的 ImageNet 预训练 ResNet-18，替换分类头 `fc`。
2. **两种迁移方案的对照**：特征提取（冻结 backbone、只训 head）vs 微调（全部可训练、分层学习率）。
3. **分层学习率**：用优化器参数组给 stem / layer1–4 / fc 设置几何递增的学习率。
4. **BatchNorm 的处理**：`freeze_bn_stats` 演示如何让 BN 在训练中保持 eval 模式。
5. **参数可训练性的检查**：打印可训练参数量，确认"冻结"真的生效。

> 一句话：**迁移学习的代码量很小，坑却很多**——冻结什么、用多大学习率、BN 怎么办，这份代码把这三件事都摆到了明面上。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `synthetic_dataset` | 函数 | 生成每类有特定颜色/频率模式的合成图像（默认 224，`main` 用 96） | 离线可复现的数据 |
| `ArrayDataset` | `Dataset` 子类 | 用 **ImageNet** 的 mean/std 标准化，HWC→CHW | 预训练模型的输入约定 |
| `make_feature_extractor` | 函数 | 预训练 ResNet-18，全部冻结，换新 `fc` | 特征提取 / linear probe |
| `make_fine_tune` | 函数 | 预训练 ResNet-18，换新 `fc`，全部可训练 | 端到端微调 |
| `discriminative_param_groups` | 函数 | 按参数名前缀分 6 组，学习率 `base_lr · 0.3^k` | 分层学习率 |
| `freeze_bn_stats` | 函数 | 把所有 BN 切到 eval 模式，并冻结其 γ/β | BN 统计量冻结 |
| `train_and_eval` | 函数 | 构建优化器与调度器，训练若干 epoch 并在验证集上评估 | 微调训练循环 |
| `trainable_param_count` | 函数 | 统计 `requires_grad=True` 的参数个数 | 冻结检查 |
| `main` | 函数 | 依次跑特征提取和分层学习率微调，打印对比 | — |

数据流：`synthetic_dataset(40/类, 96×96)` → 9:1 切分 → `ArrayDataset` + `DataLoader` → 两个模型分别进入 `train_and_eval` → 打印两者最后一个 epoch 的验证准确率。

---

## 3. 逐段精讲

### 3.1 数据：合成图像 + ImageNet 标准化

```python
def synthetic_dataset(num_per_class=100, num_classes=10, size=224, seed=0):
    rng = np.random.default_rng(seed)
    X = np.empty((num_per_class * num_classes, size, size, 3), dtype=np.float32)
    Y = np.empty(num_per_class * num_classes, dtype=np.int64)
    k = 0
    for c in range(num_classes):
        # ... 与第 04 节相同的"颜色中心 + 频率"模式，噪声 σ=0.05
            X[k] = np.clip(img, 0, 1).astype(np.float32)
            Y[k] = c
            k += 1
    idx = rng.permutation(len(X))
    return X[idx], Y[idx]
```

- 与第 04 节不同，这里**预分配**了 `np.empty` 数组再按下标 `k` 填充，而不是 `append` 到列表最后 `np.stack`——图像尺寸变大（默认 224×224）时，预分配能避免一次额外的大内存拷贝。
- 标签直接用 `np.int64`，对应 PyTorch 交叉熵要求的 `long` 类型。
- 最后同样用 `permutation` 打乱，否则按类别排列的数据切分后验证集会全是最后一类。
- `main` 中用 `num_per_class=40, size=96`：一共 400 张、96×96，让 CPU 也能在合理时间内跑完 ResNet-18。

```python
class ArrayDataset(Dataset):
    def __init__(self, X, Y):
        self.X = X
        self.Y = Y
        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __getitem__(self, i):
        img = (self.X[i] - self.mean) / self.std
        return torch.from_numpy(img).permute(2, 0, 1).float(), int(self.Y[i])
```

- **用 ImageNet 的 mean/std**：因为要复用 ImageNet 预训练权重，输入必须符合预训练时的分布（第 01 节的"预处理契约"）。对比第 04 节：从零训练时用的是数据集自己的统计量。规律是：**标准化统计量跟着权重走**。
- 在 HWC 上做标准化（`(H,W,3) - (3,)` 广播对齐通道轴），最后再 `permute` 成 CHW。
- ⚠️ 这里没有任何数据增强，也没有 resize（合成图已经是 96×96）。ResNet 的 `avgpool` 是自适应的，所以 96×96 输入同样能得到 512 维特征（stem 下采样 4 倍、后三组各 2 倍，最后的特征图是 3×3）。

### 3.2 两种模型构造方式

```python
def make_feature_extractor(num_classes=10):
    model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
    for p in model.parameters():
        p.requires_grad = False
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


def make_fine_tune(num_classes=10):
    model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    for p in model.parameters():
        p.requires_grad = True
    return model
```

- `weights=ResNet18_Weights.IMAGENET1K_V1` 是 torchvision 新版的权重枚举 API，明确指定用哪一套预训练权重。
- **顺序很关键**：特征提取模型是"先冻结全部，再替换 `fc`"。新建的 `nn.Linear` 默认 `requires_grad=True`，所以最终只有 `fc` 可训练（`512×10 + 10 = 5,130` 个参数）。如果顺序反过来（先换头再冻结），连新头也被冻结，模型什么都学不到。
- `model.fc.in_features` 读取原分类头的输入维度（ResNet-18 是 512），避免手写魔法数字。
- 微调模型最后把所有参数显式设为可训练（加载后默认就是 True，这里是为了表意清楚）。

### 3.3 分层学习率：参数组

```python
def discriminative_param_groups(model, base_lr=1e-3, decay=0.3):
    stages = [
        ["conv1", "bn1"],
        ["layer1"],
        ["layer2"],
        ["layer3"],
        ["layer4"],
        ["fc"],
    ]
    groups = []
    for i, names in enumerate(stages):
        lr = base_lr * (decay ** (len(stages) - 1 - i))
        params = [p for n, p in model.named_parameters()
                  if any(n.startswith(k) for k in names) and p.requires_grad]
        if params:
            groups.append({"params": params, "lr": lr, "name": "_".join(names)})
    return groups
```

- `model.named_parameters()` 产生 `(名字, 参数)` 对，名字形如 `conv1.weight`、`bn1.bias`、`layer2.0.conv1.weight`、`fc.weight`。用 `startswith` 按前缀归组：`"conv1"` 只匹配顶层 stem 卷积，因为嵌套层的名字都以 `layerX.` 开头。
- 学习率从 fc 的 `base_lr` 开始，每往前一组乘 0.3：fc 1e-3、layer4 3e-4、layer3 9e-5、layer2 2.7e-5、layer1 8.1e-6、stem 2.43e-6。讲义："Extreme sounding; empirically it works."
- `and p.requires_grad`：只收集可训练参数。对特征提取模型，只有 `fc` 一组能留下来。与讲义 Step 3 的版本相比，代码多了这个过滤条件——这使得同一个函数能同时用于冻结与不冻结的模型，但也带来一个后果：**之后再解冻的参数不会自动进入优化器**（见测验 Q11）。
- 参数组字典里的 `"name"` 是自定义键，PyTorch 优化器会原样保留在 `optimizer.param_groups` 中，方便日志打印。
- `"_".join(names)` 把 `["conv1", "bn1"]` 拼成 `"conv1_bn1"`。

### 3.4 `freeze_bn_stats`

```python
def freeze_bn_stats(model):
    for m in model.modules():
        if isinstance(m, (nn.BatchNorm1d, nn.BatchNorm2d, nn.BatchNorm3d)):
            m.eval()
            for p in m.parameters():
                p.requires_grad = False
    return model
```

- `model.modules()` **递归**遍历所有子模块（包括嵌套在 `layer1.0` 里的 BN）；`isinstance` 可以接收一个类型元组，一次匹配三种 BN。
- `m.eval()`：只把这个 BN 切到推理模式——用 running statistics 标准化，并且不再更新它们。
- ⚠️ **与讲义描述不一致**：讲义说这是"冻结 BN 运行统计量、但不冻结其权重"的函数，而代码还把 BN 的 γ、β 设成了 `requires_grad = False`，权重也一起冻结了（测验 Q9 给出了只冻结统计量的版本）。
- 必须在每个 epoch 的 `model.train()` **之后**调用，因为 `train()` 会递归地把所有子模块（包括 BN）切回训练模式。`train_and_eval` 中正是这样安排的。
- ⚠️ `main` 中两个实验都没有开启 `freeze_bn`，这个函数只是作为工具提供。

### 3.5 `train_and_eval`：微调训练循环

```python
def train_and_eval(model, train_loader, val_loader, device, epochs=2, base_lr=1e-3, freeze_bn=False):
    model = model.to(device)
    groups = discriminative_param_groups(model, base_lr=base_lr)
    if not groups:
        groups = [{"params": [p for p in model.parameters() if p.requires_grad], "lr": base_lr}]
    optimizer = SGD(groups, momentum=0.9, weight_decay=1e-4, nesterov=True)
    scheduler = CosineAnnealingLR(optimizer, T_max=max(epochs, 1))

    last_val = 0.0
    for epoch in range(epochs):
        model.train()
        if freeze_bn:
            freeze_bn_stats(model)
        # ... 标准训练步：前向 → label smoothing 交叉熵 → zero_grad → backward → step
        scheduler.step()

        model.eval()
        # ... 在 no_grad 下统计验证准确率
        last_val = va_correct / va_total
```

- **把参数组直接传给 `SGD`**：每组用自己的 `lr`；`momentum`、`weight_decay`、`nesterov` 作为所有组的默认值。
- **兜底分支** `if not groups:`：模型参数名不符合 ResNet 命名（例如换成别的网络）时，退化为"所有可训练参数一个组"。
- **`CosineAnnealingLR` 作用于每一组**：各组的学习率都按同一余弦曲线、从各自的初始值往下降，组间比例保持不变。`T_max=max(epochs, 1)` 防止 `epochs=0` 时传入 0。
- 训练步与第 04 节完全一致（`train()` → `zero_grad` → `backward` → `step`，`.item()` 累计指标），损失用 `label_smoothing=0.1`。
- 返回最后一个 epoch 的验证准确率，供 `main` 做对比。
- ⚠️ 特征提取实验中，`model.train()` 会让**冻结的** backbone 中的 BN 层进入训练模式，`running_mean/var` 会被合成数据更新。卷积权重确实没变，但严格来说这不是纯粹的 linear probe（测验 Q10）。若要严格冻结，对特征提取模型传 `freeze_bn=True` 即可。

### 3.6 `main`：两组实验

```python
    fe = make_feature_extractor()
    print(f"  trainable params: {trainable_param_count(fe):,}")
    acc_fe = train_and_eval(fe, train_loader, val_loader, device, epochs=2, base_lr=3e-2)

    ft = make_fine_tune()
    for g in discriminative_param_groups(ft, base_lr=1e-3):
        print(f"  group {g['name']:>10s}  lr={g['lr']:.2e}")
    acc_ft = train_and_eval(ft, train_loader, val_loader, device, epochs=2, base_lr=1e-3)

    print(f"\nsummary  feature-extract val={acc_fe:.3f}   fine-tune val={acc_ft:.3f}")
```

- 特征提取用较大的 `base_lr=3e-2`（只训练一个线性层，可以激进一些）；微调用 `base_lr=1e-3`（fc 拿 1e-3，backbone 更小）。
- 各训练 2 个 epoch：360 张训练图、batch 16，每个 epoch 23 步。
- ⚠️ 两组实验的 head 学习率相差 30 倍、训练步数很少，所以最后的 summary 不是严格的对照实验——如果看到微调准确率低于特征提取，先别急着下结论：讲义说"微调低于 linear probe ⇒ 学习率或 BN 有 bug"，在这里更可能的原因是**微调的 head 学习率太小、训练太短**。想做公平对比，应让两者的 head 学习率相同、训练足够多的 epoch。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 合成数据 + 96×96 | 数据离线可得、CPU 可跑 | 合成任务太简单，体现不出预训练特征的真正价值；真实项目用领域数据并 resize 到 224 |
| ImageNet mean/std | 与预训练权重的输入约定一致 | — |
| 先冻结再换头 | 保证新头可训练 | 顺序写反会导致整个模型不可训练 |
| 按名字前缀分组 | 简单、对 torchvision ResNet 有效 | 与具体网络的命名强耦合；通用做法是按模块层级或用 timm 提供的分组工具 |
| 参数组只收集可训练参数 | 同一函数兼容冻结/不冻结的模型 | 后续解冻的参数不会自动进入优化器，需重建或 `add_param_group` |
| `freeze_bn_stats` 同时冻结 γ/β | 小数据下最保守 | 与讲义描述不符；更灵活的做法是用参数控制是否冻结仿射参数 |
| 特征提取也走 `model.train()` | 复用同一个训练函数 | BN 统计量被更新，不是严格的 linear probe；可预先缓存特征再训练线性层，又快又准确 |
| 只训练 2 个 epoch | 演示用，节省时间 | 结论不稳定；真实对比需要更多 epoch 和多次随机种子 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `np.empty` 预分配 | `X = np.empty((N, size, size, 3), dtype=np.float32)` | 先分配好内存（内容未初始化），再逐个填充 |
| 计数器变量 | `k = 0 ... X[k] = ...; k += 1` | 在嵌套循环中维护全局下标 |
| 类属性初始化 | `self.mean = np.array([...])` | 在 `__init__` 中准备好常量，`__getitem__` 中重复使用 |
| 属性赋值替换子模块 | `model.fc = nn.Linear(model.fc.in_features, num_classes)` | 给 `nn.Module` 的属性赋新模块，会自动替换并注册 |
| 嵌套列表 | `stages = [["conv1", "bn1"], ["layer1"], ...]` | 每组是一个名字列表 |
| `enumerate` | `for i, names in enumerate(stages):` | 同时得到下标和元素 |
| 幂运算 | `decay ** (len(stages) - 1 - i)` | 计算几何递减的系数 |
| 带条件的列表推导 | `[p for n, p in model.named_parameters() if any(...) and p.requires_grad]` | 遍历 + 过滤，一行完成 |
| `any()` + 生成器 | `any(n.startswith(k) for k in names)` | 只要有一个前缀匹配就为 True |
| `str.startswith` / `str.join` | `n.startswith(k)`、`"_".join(names)` | 前缀判断；用分隔符拼接字符串 |
| 字典字面量 | `{"params": params, "lr": lr, "name": ...}` | 优化器参数组的格式 |
| `isinstance` 与类型元组 | `isinstance(m, (nn.BatchNorm1d, nn.BatchNorm2d, nn.BatchNorm3d))` | 一次判断多种类型 |
| `if not groups:` | 空列表为假 | Python 的"真值测试"：空容器视为 False |
| `max()` 防御 | `T_max=max(epochs, 1)` | 保证参数至少为 1 |
| 关键字参数默认值 | `def train_and_eval(..., epochs=2, base_lr=1e-3, freeze_bn=False)` | 调用时可以只覆盖需要的参数 |
| f-string 格式符 | `f"{n:,}"`、`f"{g['name']:>10s}"`、`f"{g['lr']:.2e}"` | 千分位逗号；右对齐 10 格；科学计数法 2 位小数 |
| f-string 中的引号 | `f"  group {g['name']:>10s}"` | 外层用双引号时，内部字典键用单引号 |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch` 和 `torchvision`；另外加载 `IMAGENET1K_V1` 预训练权重首次需要联网）。** 根据代码可以确定的部分如下，训练指标取决于随机性和硬件，这里不编造具体数值：

```text
device: cpu

[feature extraction] freeze backbone, train head only
  trainable params: 5,130
  epoch 0  train <loss>/<acc>  val <acc>
  epoch 1  train <loss>/<acc>  val <acc>

[fine-tune] discriminative LR across stages
  group  conv1_bn1  lr=2.43e-06
  group     layer1  lr=8.10e-06
  group     layer2  lr=2.70e-05
  group     layer3  lr=9.00e-05
  group     layer4  lr=3.00e-04
  group         fc  lr=1.00e-03
  epoch 0  train <loss>/<acc>  val <acc>
  epoch 1  train <loss>/<acc>  val <acc>

summary  feature-extract val=<acc_fe>   fine-tune val=<acc_ft>
```

解读：

- **`trainable params: 5,130`**：只有新的 `fc`（512×10 权重 + 10 偏置）可训练，其余约 1,118 万个 backbone 参数全部冻结。这是"冻结是否生效"最直接的证据。
- **参数组学习率**：严格按 `1e-3 × 0.3^k` 计算，6 组跨越近 3 个数量级——stem 的学习率只有 head 的约 0.24%。
- **训练损失**：使用了 `label_smoothing=0.1`，10 类时损失的理论下界不是 0，而是平滑目标分布的熵（约 0.5）。
- **两组验证准确率**：合成任务的类别区分主要靠颜色和频率，冻结的 ImageNet 特征 + 线性头通常就能学得不错。由于两组实验 head 学习率不同、只训 2 个 epoch（见 3.6），比较结果时要谨慎；如果要严格遵循讲义"始终打印下限和上限"的做法，应统一 head 学习率并多训练几轮。

---

## 7. 动手改一改

1. （易）在特征提取实验前后各保存一次 `fe.bn1.running_mean`，验证它是否被改变；再传入 `freeze_bn=True` 重跑，确认不再改变（测验 Q10）。
2. （易）把 `make_feature_extractor` 中"冻结"和"换头"两步的顺序对调，打印 `trainable params`，观察结果并解释。
3. （中）修改 `freeze_bn_stats`，增加 `freeze_affine=False` 参数，使默认行为与讲义描述一致（只冻结统计量）。
4. （中）让两组实验的 head 学习率相同（例如都用 1e-2）、各训练 5 个 epoch，重新比较 linear probe 与微调（讲义练习 1）。
5. （中）故意把 backbone 学习率设为 1e-1（例如 `decay=1.0, base_lr=1e-1`），观察训练损失是否爆炸；再换回分层学习率恢复训练（讲义练习 2）。
6. （难）实现渐进式解冻：每个 epoch 解冻一个 stage，并用 `optimizer.add_param_group` 把新解冻的参数加入优化器（测验 Q11）。

---

## 8. 常见坑

- **先换头再冻结**：新头也被冻结，`trainable params` 变成 0，模型完全不学习。
- **以为 `requires_grad=False` 能冻结 BN**：running statistics 是 buffer，只受 `train()/eval()` 控制。
- **`freeze_bn_stats` 调用时机不对**：在 `model.train()` 之前调用会被立刻覆盖。
- **解冻后不更新优化器**：新解冻的参数有梯度却从不更新，而且不报错。
- **用新数据集的统计量做标准化**：复用预训练权重时应使用预训练时的 mean/std。
- **head 学习率不一致就比较两种方案**：得出"微调不如特征提取"的错误结论。
