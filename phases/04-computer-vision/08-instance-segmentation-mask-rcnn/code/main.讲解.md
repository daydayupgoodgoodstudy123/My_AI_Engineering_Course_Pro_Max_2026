# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 08 节 实例分割——Mask R-CNN ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：`torch`、`torchvision`（`torchvision.ops.roi_align`、`torchvision.models.detection`）；第二部分首次运行需联网下载 COCO 预训练权重，失败时会被 `try/except` 捕获并跳过

---

## 1. 这份代码在考察什么

Mask R-CNN 整体太大，不适合从零手写；这份代码只挑出**最值得亲手写一遍的一个零件**（RoIAlign），其余部分演示"怎么正确使用 torchvision 的现成实现"：

1. **RoIAlign 的坐标数学**：像素坐标 → 特征图坐标 → `grid_sample` 归一化坐标，两个"半像素"约定分别从哪来。
2. **用参考实现做单元测试**：把自己的实现和 `torchvision.ops.roi_align` 在相同设置下逐元素比较。
3. **读懂预训练模型的输出格式**：`boxes / labels / masks` 各自的形状。
4. **微调配方**：替换 box predictor 和 mask predictor 适配新的类别数，冻结 backbone（含 FPN），统计可训练参数。
5. **对网络/下载失败的容错**：把依赖联网的部分包进 `try/except`。

> 一句话：**自己实现最容易出错的那一小块，其余交给成熟库，但要能读懂、能改造。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `roi_align_single(feature, box, output_size, spatial_scale)` | 函数 | 单张特征图、单个框的 RoIAlign（每个 bin 采 1 个点） | RoIAlign |
| `compare_with_torchvision_roi_align()` | 函数 | 3 个框上对比自写版与 `torchvision.ops.roi_align` 的最大绝对误差 | 参考实现验证 |
| `load_pretrained_maskrcnn()` | 函数 | 加载 `maskrcnn_resnet50_fpn_v2` 默认权重并设为 eval | 预训练模型 |
| `build_custom_maskrcnn(num_classes)` | 函数 | 替换 `box_predictor` 和 `mask_predictor` | 换头微调 |
| `freeze_backbone(model)` | 函数 | 把 `model.backbone`（含 FPN）全部设为不求梯度 | 冻结 |
| `main()` | 演示入口 | 先跑 RoIAlign 对比；再在 `try` 中做推理和换头 | — |

调用关系：`main → compare_with_torchvision_roi_align → roi_align_single`；`main → load_pretrained_maskrcnn → 推理`；`main → build_custom_maskrcnn → freeze_backbone → 统计参数`。

---

## 3. 逐段精讲

### 3.1 `roi_align_single`：坐标换算是全部难点

```python
def roi_align_single(feature, box, output_size=7, spatial_scale=1 / 16.0):
    C, H, W = feature.shape
    x1, y1, x2, y2 = [c * spatial_scale - 0.5 for c in box]
    bin_w = (x2 - x1) / output_size
    bin_h = (y2 - y1) / output_size

    grid_y = torch.linspace(y1 + bin_h / 2, y2 - bin_h / 2, output_size, device=feature.device)
    grid_x = torch.linspace(x1 + bin_w / 2, x2 - bin_w / 2, output_size, device=feature.device)
    yy, xx = torch.meshgrid(grid_y, grid_x, indexing="ij")

    gx = 2 * (xx + 0.5) / W - 1
    gy = 2 * (yy + 0.5) / H - 1
    grid = torch.stack([gx, gy], dim=-1).unsqueeze(0)
    sampled = F.grid_sample(feature.unsqueeze(0), grid, mode="bilinear",
                            align_corners=False)
    return sampled.squeeze(0)
```

按四步理解：

| 步骤 | 代码 | 含义 |
|------|------|------|
| ① 映射到特征图 | `c * spatial_scale` | 原图像素坐标 ÷ stride（`spatial_scale = 1/stride`） |
| ② 半像素对齐 | `- 0.5` | 换到"像素中心在整数位置"的坐标系，对应 torchvision 的 `aligned=True` |
| ③ 采样点 | `linspace(y1 + bin_h/2, y2 - bin_h/2, output_size)` | 把框均分成 `output_size × output_size` 个 bin，每个 bin 取**中心**一个点（= `sampling_ratio=1`） |
| ④ 归一化 | `2 * (xx + 0.5) / W - 1` | `grid_sample` 在 `align_corners=False` 时，第 i 个像素中心对应 `2(i+0.5)/W − 1` |

- **全程没有任何取整**：采样点是浮点坐标，`grid_sample(mode="bilinear")` 用周围 4 个像素做双线性插值。这就是 RoIAlign 相对 RoIPool 的全部改进——讲义说的"No rounding, no quantisation, no dropped gradients"。
- `torch.meshgrid(grid_y, grid_x, indexing="ij")`：`yy[i, j] = grid_y[i]`、`xx[i, j] = grid_x[j]`，得到 7×7 的采样点网格。
- `torch.stack([gx, gy], dim=-1)`：`grid_sample` 要求最后一维是 `(x, y)` 顺序（先宽后高），容易写反。`.unsqueeze(0)` 补出 batch 维，`grid` 形状 `(1, 7, 7, 2)`。
- `feature.unsqueeze(0)`：`(C,H,W)` → `(1,C,H,W)`；输出 `(1,C,7,7)` 再 `squeeze(0)` 成 `(C,7,7)`。
- `device=feature.device`：采样网格与特征图放在同一设备上，GPU 上也能直接用。
- 因为 `grid_sample` 对输入和 grid 都可导，这个实现天然支持反向传播。
- ⚠️ 简化：①一次只处理一个框、一张图；torchvision 版本接收 `(K, 5)` 的 `[batch_idx, x1, y1, x2, y2]` 一次处理所有框。②每个 bin 只采 1 个点；Mask R-CNN 在 torchvision 中默认每个 bin 采 2×2 个点再平均（`sampling_ratio=2`）。③**边界处理与 torchvision 不同**：`grid_sample` 默认把越界邻居当 0；torchvision 内核会把 `(−1, 0]` 范围内的坐标夹到 0、只有更远才返回 0。贴边的框两者结果会不同（测验 Q10）。

### 3.2 `compare_with_torchvision_roi_align`：用参考实现做单元测试

```python
    torch.manual_seed(0)
    feature = torch.randn(1, 16, 50, 50)
    boxes = torch.tensor([[0, 10, 20, 100, 90],
                          [0, 5, 5, 80, 80],
                          [0, 30, 10, 120, 110]], dtype=torch.float32)

    diffs = []
    for b in boxes:
        ours = roi_align_single(feature[0], b[1:].tolist(), output_size=7, spatial_scale=1 / 4)
        theirs = roi_align(
            feature, b.unsqueeze(0),
            output_size=(7, 7),
            spatial_scale=1 / 4,
            sampling_ratio=1,
            aligned=True,
        )[0]
        diffs.append((ours - theirs).abs().max().item())
    return diffs
```

- 特征图 50×50、`spatial_scale=1/4`，相当于原图 200×200、stride 4（FPN 的 P2 层）。
- `boxes` 每行的第 0 列是 **batch 索引**，这是 `torchvision.ops.roi_align` 的输入约定；自写版只需要后 4 个坐标，所以 `b[1:].tolist()`。
- 关键是 `sampling_ratio=1, aligned=True` 两个参数——只有在这个设置下两种实现的采样点才完全一致。
- `b.unsqueeze(0)`：单个框 `(5,)` → `(1,5)`；返回 `(1, 16, 7, 7)`，`[0]` 取出 `(16, 7, 7)`。
- `.abs().max().item()`：最大绝对误差转成 Python 浮点数。用"最大"而不是"平均"，才能发现个别位置的错误。
- 三个框换算后，所有采样点都在特征图内部（例如第三个框的 y 方向最远到约 27，小于 49），因此不会触发 3.1 提到的边界差异。

### 3.3 加载预训练模型并推理

```python
def load_pretrained_maskrcnn():
    from torchvision.models.detection import (
        maskrcnn_resnet50_fpn_v2, MaskRCNN_ResNet50_FPN_V2_Weights,
    )
    model = maskrcnn_resnet50_fpn_v2(weights=MaskRCNN_ResNet50_FPN_V2_Weights.DEFAULT)
    model.eval()
    return model
```

```python
        with torch.no_grad():
            p = model([torch.randn(3, 200, 300)])[0]
        print(f"  boxes:  {tuple(p['boxes'].shape)}")
        print(f"  labels: {tuple(p['labels'].shape)}")
        print(f"  masks:  {tuple(p['masks'].shape)}")
```

- **导入放在函数内部**：只有真正调用时才导入检测模块，RoIAlign 的部分不依赖它；这也让"加载失败"可以被 `main()` 里的 `try` 捕获。
- `Weights.DEFAULT`：torchvision 新式权重 API，指向当前推荐的预训练权重（COCO），首次使用会下载到本地缓存。
- `model.eval()`：切到推理模式。torchvision 检测模型在 eval 模式下返回预测，在 train 模式下要求传 `targets` 并返回损失字典。
- **输入是图像列表**：`model([tensor(3, H, W)])`，每张图可以尺寸不同，模型内部的 `transform` 负责缩放和归一化，所以不需要自己 resize。
- 输出 `p` 是 dict：`boxes (N,4)`、`labels (N,)`、`scores (N,)`、`masks (N,1,200,300)`——mask 已经被粘贴回**原图尺寸**。输入是随机噪声，N 很可能是 0 或个位数。
- 代码没打印 `scores`，但真实使用时要先按分数过滤，再用 `(p['masks'] > 0.5).squeeze(1)` 二值化。

### 3.4 `build_custom_maskrcnn`：换头

```python
    model = maskrcnn_resnet50_fpn_v2(weights=MaskRCNN_ResNet50_FPN_V2_Weights.DEFAULT)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
    in_features_mask = model.roi_heads.mask_predictor.conv5_mask.in_channels
    model.roi_heads.mask_predictor = MaskRCNNPredictor(in_features_mask, 256, num_classes)
    return model
```

- **从旧头读出输入维度**：`cls_score` 是 box predictor 里的分类线性层，`in_features` 就是 box head 输出的特征维度；`conv5_mask` 是 mask predictor 里的 2× 反卷积，`in_channels` 是 mask head 的输出通道。这样写不需要硬编码数字，换 backbone 也不会错。
- `FastRCNNPredictor(in_features, num_classes)`：新的分类层 + 框回归层（每类 4 个偏移）。
- `MaskRCNNPredictor(in_features_mask, 256, num_classes)`：反卷积（隐藏通道 256）+ 1×1 卷积输出 `num_classes` 张 mask。
- `num_classes=5` 表示 4 个前景类 + 1 个背景类（类别 0 是背景）。
- 被替换的只有两个 **predictor**（最后的输出层），box head 和 mask head 的 4 层卷积仍沿用预训练权重。
- ⚠️ 这里会**再加载一次**完整预训练模型（与 3.3 各加载一次），只是演示用；实际项目中只需要加载一次。

### 3.5 `freeze_backbone`：冻结 backbone + FPN

```python
def freeze_backbone(model):
    # torchvision Mask R-CNN's backbone includes the FPN (model.backbone.fpn),
    # so freezing model.backbone.parameters() also freezes the FPN parameters.
    for p in model.backbone.parameters():
        p.requires_grad = False
    return model
```

```python
        trainable = sum(p.numel() for p in custom.parameters() if p.requires_grad)
        total = sum(p.numel() for p in custom.parameters())
        print(f"  trainable: {trainable:,}   total: {total:,}")
```

- `model.backbone` 是 `BackboneWithFPN`，内部包含 `body`（ResNet）和 `fpn`，注释特意说明冻结它就同时冻结了 FPN——与讲义 Step 6 "freeze the backbone and the FPN" 一致。
- `requires_grad = False`：反向传播不再为这些参数计算梯度，既防止小数据过拟合，也省显存和时间。
- 统计后 `trainable` 只包含 RPN 与 `roi_heads`（box head、box predictor、mask head、mask predictor），远小于 `total`。
- ⚠️ `requires_grad=False` 不影响 BatchNorm 的 running stats；如果 backbone 里是普通 BN 且以 train 模式运行，统计量仍会被更新。冻结时通常还要让这些 BN 保持 eval 模式（或使用 FrozenBatchNorm）。
- ⚠️ 训练时应只把可训练参数交给优化器：`torch.optim.SGD([p for p in model.parameters() if p.requires_grad], lr=...)`。

### 3.6 `main()` 的容错结构

```python
    try:
        print("\n[pretrained] loading maskrcnn_resnet50_fpn_v2 (downloads on first run)")
        model = load_pretrained_maskrcnn()
        # ...
    except Exception as e:
        print(f"[pretrained] skipped: {e}")
```

- 下载失败、离线、磁盘不足时，不让整个脚本崩溃，而是打印原因后结束——RoIAlign 部分的结果依然可用。
- ⚠️ `except Exception` 会吞掉所有错误，包括代码 bug（比如属性名写错）。教学脚本可以接受；生产代码应只捕获预期的异常类型（如网络错误），其余让它抛出。
- 文件顶部的 `from torchvision.ops import roi_align` 不在 `try` 里：没装 torchvision 时脚本一开始就会失败。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 `grid_sample` 实现 RoIAlign | 一行完成双线性采样，自动可导 | 一次只处理一个框；生产用 `torchvision.ops.roi_align` / `MultiScaleRoIAlign` |
| 每个 bin 只采 1 个点 | 与 `sampling_ratio=1` 对齐，便于逐元素验证 | 默认配置每个 bin 采多个点并平均，更平滑 |
| 用最大绝对误差验证 | 能抓出个别位置的错误 | 应补充贴边框、退化框等边界用例 |
| 检测相关 import 放进函数 | 按需加载，失败可被捕获 | 隐藏依赖，IDE 不易发现 |
| 从旧头读 `in_features` / `in_channels` | 不硬编码，换 backbone 也不出错 | 需要了解 torchvision 内部属性名 |
| 冻结整个 `model.backbone` | 小数据集防过拟合 | 数据多时应解冻高层并降低学习率 |
| `except Exception` 兜底 | 离线也能跑完第一部分 | 会掩盖真实 bug |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组解包 | `C, H, W = feature.shape` | 一次取出三个维度 |
| 列表推导 + 解包 | `x1, y1, x2, y2 = [c * spatial_scale - 0.5 for c in box]` | 对 4 个坐标做同样变换后直接解包 |
| `enumerate` | `for i, d in enumerate(diffs)` | 同时拿到下标和值 |
| f-string 科学计数法 | `f"{d:.2e}"` | 输出如 `1.19e-07` 的格式 |
| f-string 千分位 | `f"{trainable:,}"` | 用逗号分隔千位 |
| 生成器表达式 + 条件 | `sum(p.numel() for p in custom.parameters() if p.requires_grad)` | 只累加满足条件的元素 |
| 函数内 `import` | `from torchvision.models.detection import (...)` | 延迟导入；括号允许多行导入 |
| `try / except Exception as e` | `main()` 中的预训练部分 | 捕获异常并拿到异常对象打印 |
| `with` 上下文管理器 | `with torch.no_grad():` | 代码块内关闭梯度 |
| 张量方法 | `unsqueeze / squeeze / tolist / item` | 增删维度、转 Python 列表、转 Python 数 |
| 关键字参数 | `roi_align(..., sampling_ratio=1, aligned=True)` | 显式写参数名，可读性高 |
| `if __name__ == "__main__":` | 文件末尾 | 只有直接运行时才执行 `main()` |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch` 与 `torchvision`，且第二部分需要联网下载预训练权重）。** 根据代码，预期输出结构如下：

```text
[roi_align] comparing ours vs torchvision.ops.roi_align
  box 0: max|diff|=x.xxe-0y
  box 1: max|diff|=x.xxe-0y
  box 2: max|diff|=x.xxe-0y

[pretrained] loading maskrcnn_resnet50_fpn_v2 (downloads on first run)
  boxes:  (N, 4)
  labels: (N,)
  masks:  (N, 1, 200, 300)

[fine-tune setup] swap heads for 5-class dataset, freeze backbone
  trainable: …   total: …
```

逐段解读：

- **RoIAlign 对比**：三个框的采样点都在特征图内部，两种实现计算的是同一组双线性插值，差异只来自 float32 的运算顺序，预期在 `1e-6` 量级甚至更小（讲义说"within 1e-5"）。如果看到 `1e-1` 量级的差异，多半是 `-0.5`、`+0.5` 或 `(x, y)` 顺序写错了。
- **推理**：输入是随机噪声，模型大概率检测不到任何东西，N 可能为 0，此时会打印 `(0, 4)`、`(0,)`、`(0, 1, 200, 300)`——这不是错误。重点是 `masks` 的空间尺寸等于输入的 200×300，说明 mask 已经被粘贴回原图。
- **换头 + 冻结**：`total` 约为讲义所说的 46M 量级（新 predictor 类别数从 91 变成 5，参数略少）；`trainable` 只剩 RPN 与 ROI heads 的参数，远小于 `total`。
- **离线时**：第二、三段会被替换为一行 `[pretrained] skipped: <下载错误信息>`。

---

## 7. 动手改一改

1. 增加一个贴边的框 `[0, 0, 0, 20, 20]`，观察 `max|diff|` 变大；再试 `padding_mode="border"`，看能不能消除差异，并解释原因。
2. 把 `roi_align_single` 扩展为支持 `sampling_ratio=2`：每个 bin 采 2×2 个点再平均，与 `roi_align(..., sampling_ratio=2, aligned=True)` 比较。
3. 实现一个 RoIPool 版本（坐标取整、bin 内取 max），在同一个框上与 RoIAlign 的输出比较，体会量化误差（讲义练习 1）。
4. 在推理部分加上分数过滤和 mask 二值化：只保留 `scores > 0.5` 的实例，打印每个实例的 mask 像素面积。
5. 写 `trainable_by_module(model)`，按 `transform / backbone / rpn / roi_heads` 分别统计可训练参数（测验 Q11）。
6. 解冻 `model.backbone.body.layer4`，比较可训练参数量的变化。

---

## 8. 常见坑

- **`grid_sample` 的坐标顺序**：最后一维是 `(x, y)`，不是 `(row, col)`；写反了形状完全正确但结果全错。
- **`align_corners` 与 `aligned` 混用**：两套半像素约定必须配套，否则整体偏移半个像素。
- **`num_classes` 忘记加背景**：4 个前景类却写 `num_classes=4`，最后一个类永远学不到。
- **roi_align 的框格式**：`torchvision.ops.roi_align` 的 Tensor 输入需要第 0 列是 batch 索引，直接传 `(K,4)` 会报错或错位。
- **冻结了但优化器仍拿到全部参数**：不会出错，但会浪费内存；BN 统计量也可能在悄悄更新。
- **`except Exception` 掩盖 bug**：换头时属性名写错，也只会打印一行 "skipped"。
