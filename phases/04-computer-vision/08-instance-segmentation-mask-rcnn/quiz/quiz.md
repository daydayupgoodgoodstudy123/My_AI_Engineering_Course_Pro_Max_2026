# 测验 · 实例分割——Mask R-CNN（Instance Segmentation — Mask R-CNN）

> **阶段 04 · 计算机视觉 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过（或读懂）代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 实例分割 = 检测 + mask | 语义分割每类一张 mask；实例分割每个目标一张 mask，同类目标也要分开，用于计数、跟踪、逐个测量 |
| 2 | 五大组件 | ResNet backbone（stride 4/8/16/32）→ FPN → RPN → RoIAlign → box head + mask head |
| 3 | FPN | 自顶向下 + 横向连接，让每一层都有语义丰富的特征；按 proposal 大小选层（小目标用高分辨率层） |
| 4 | RPN | 每个位置放 K 个 anchor，预测"有没有物体"和框偏移，取 top ~1000、IoU 0.7 做 NMS，交给后面的 head |
| 5 | RoIPool → RoIAlign | RoIPool 把坐标取整，误差可达一个特征图像素（stride 32 时就是 32 个原图像素）；RoIAlign 在浮点坐标上双线性采样，不做任何取整 |
| 6 | Mask head | 对每个 proposal：RoIAlign 特征 → 4 个 3×3 conv → 2× 反卷积 → 1×1 conv，输出 `num_classes` 张 28×28 mask，只取预测类别那一张（与分类解耦） |
| 7 | 损失 | `L_rpn_cls + L_rpn_box + L_box_cls + L_box_reg + L_mask`；分类是 C+1 类 CE，框回归是 smooth L1，mask 是逐像素 BCE |
| 8 | torchvision 输出与类别编号 | 每图一个 dict：`boxes / labels / scores / masks(N,1,H,W)`；类别 0 是背景，`num_classes` 要包含背景 |
| 9 | 小数据微调配方 | 复用 backbone/FPN/RPN，替换 box predictor 与 mask predictor，冻结 backbone（含 FPN） |

### 核心技能（能动手做到）

- [ ] 用 `F.grid_sample` 从零实现 `roi_align_single`，并能逐步写出"像素坐标 → 特征图坐标 → `[-1,1]` 归一化坐标"的换算
- [ ] 用 `torchvision.ops.roi_align(..., sampling_ratio=1, aligned=True)` 验证自己的实现，并解释什么情况下两者会出现差异
- [ ] 加载 `maskrcnn_resnet50_fpn_v2`，正确读取输出 dict，把 `masks` 用 0.5 阈值二值化成 `(N, H, W)`
- [ ] 为 K 个前景类的数据集替换 `FastRCNNPredictor` 与 `MaskRCNNPredictor`（`num_classes = K + 1`）
- [ ] 冻结 `model.backbone` 后统计各子模块的可训练参数量
- [ ] 写出训练模式下 `loss_dict = model(images, targets)` 的训练步，并说出 targets 中每个字段的格式

---

## 二、基础自测（选择题）

**Q1.** 在显微镜图像中需要统计细胞个数并测量**每个**细胞的面积，细胞经常互相贴在一起。最合适的任务形式是：

- A. 图像分类
- B. 语义分割
- C. 实例分割
- D. 只做目标检测

**Q2.** 在 stride=16 的特征图上用 RoIPool 裁剪 proposal，仅"框坐标取整"这一步引入的原图偏移最多约为：

- A. 0.5 像素
- B. 1 像素
- C. 16 像素
- D. 32 像素

**Q3.** Mask R-CNN 的 mask head 为每个 proposal 输出 `num_classes` 张 28×28 的 mask，推理时只读预测类别对应的那一张。这样设计的主要原因是：

- A. 单通道放不下二值 mask
- B. 把"形状预测"和"分类"解耦：每个类别独立学自己的二值 mask（逐像素 sigmoid），各类别之间不在像素上竞争
- C. 为了让 mask head 参数更少
- D. 为了让反向传播能计算 softmax

**Q4.** 你的数据集有 4 个前景类（猫、狗、鸟、马），用 `FastRCNNPredictor(in_features, num_classes)` 替换分类头时，`num_classes` 应该是：

- A. 4
- B. 5
- C. 91
- D. 3

**Q5.** 一个 20×20 像素的小目标 proposal，FPN 通常会把它分配到哪一层去做 RoIAlign？

- A. P5（stride 32），因为语义最强
- B. P2（stride 4）这类高分辨率浅层，因为在 stride 32 上它连一个格子都占不满
- C. 随机选一层
- D. 四层都取再平均

**Q6.** 关于 torchvision 的 Mask R-CNN，下列说法正确的是：

- A. 无论训练还是推理，`model(images)` 都返回预测结果列表
- B. 训练模式下 `model(images, targets)` 返回损失字典，推理模式下返回每张图一个预测 dict 的列表
- C. 训练模式下只返回一个总损失标量
- D. 推理模式下必须传入 targets

**Q7.** `maskrcnn_resnet50_fpn_v2` 推理输出的 `p['masks']` 是：

- A. 每个实例 28×28 的 logits，需要自己上采样
- B. `(N, 1, H, W)`、与原图同尺寸、取值 [0,1] 的概率图，常用 `> 0.5` 得到二值 mask
- C. `(H, W)` 的整数实例 id 图
- D. `(N, 28, 28)` 的布尔张量

**Q8.** 在一个 500 张图的数据集上微调 Mask R-CNN，训练损失持续下降、验证 mAP 却早早停滞。讲义推荐首先尝试：

- A. 继续加 epoch
- B. 提高学习率
- C. 冻结 backbone 和 FPN，只训练 RPN 和两个 head
- D. 换成 U-Net

---

## 三、动手 / 代码题

**Q9.** 阅读 `roi_align_single`：

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

特征图 `(16, 50, 50)`，box = `(10, 20, 100, 90)`，`spatial_scale = 1/4`，`output_size = 7`。

(a) 计算 `x1, y1, x2, y2`、`bin_w`、`bin_h`，以及左上角第一个采样点的特征图坐标 `(x, y)` 和对应的归一化坐标 `(gx, gy)`。
(b) `- 0.5` 和 `gx = 2 * (xx + 0.5) / W - 1` 里的 `+ 0.5` 分别在做什么？
(c) 返回张量的形状是什么？

**Q10.** 讲义说在 `sampling_ratio=1, aligned=True` 下，本实现与 `torchvision.ops.roi_align` 误差在 `1e-5` 以内。`main()` 里的三个框都满足。但如果把框换成 `(0, 0, 20, 20)`（`spatial_scale=1/4`），两者会出现明显差异。请算出第一个采样点的 x 坐标，解释差异来源，并说明为什么讲义练习 1 中"100 个随机框"的验证可能会失败。

**Q11.** `freeze_backbone(custom)` 之后，写一个函数 `trainable_by_module(model)`，返回 `{子模块名: 可训练参数量}`，用来确认 backbone（含 FPN）确实被冻结、RPN 和 ROI heads 仍可训练。torchvision 的 Mask R-CNN 顶层有哪几个子模块？

---

## 四、面试高频题

**Q12.**（基础必考）讲一下 Mask R-CNN 的完整前向流程。它相对 Faster R-CNN 改了哪两处？

**Q13.**（原理深挖）RoIAlign 相比 RoIPool 解决了什么问题？为什么这个改进对 mask 的提升比对框更明显？`sampling_ratio` 是什么？

**Q14.**（原理深挖）Mask R-CNN 的 mask 分支为什么用"每类一张 mask + 逐像素 sigmoid/BCE"，而不是"一张 mask + 跨类 softmax"？28×28 的分辨率会带来什么限制，有哪些改进方向？

**Q15.**（工程实践）给你 300 张标注了实例 mask 的工业零件图（3 类），要求两周内上线。请描述你用 torchvision Mask R-CNN 微调的完整方案：数据格式、模型改造、训练策略、评估。

**Q16.**（场景设计）同样是实例分割，什么时候选 Mask R-CNN，什么时候选 YOLO 系分割模型、Mask2Former 或 SAM 系模型？请从精度、速度、数据量、开放类别几个角度对比。

---

## 五、参考答案与解析

### Q1 — 答案：C

需要"逐个"计数和测面积，而且细胞相互贴着：语义分割会把相邻细胞合成一块（只知道"这些像素是细胞"），检测只给框、算不了真实面积。实例分割给每个细胞一张独立的 mask，正是讲义所说的"每块砖、每个细胞"的测量场景。

### Q2 — 答案：C

坐标先除以 stride 映射到特征图，再取整。取整误差最多接近 1 个特征图像素，乘回 stride 就是约 16 个原图像素。讲义原话：误差可达"a full feature-map pixel"，在 stride 32 时是灾难性的。而且 RoIPool 还会在划分网格时对每个格子边界再取整一次，误差会叠加。

### Q3 — 答案：B

每个类别一张独立的二值 mask，用逐像素 sigmoid + BCE 训练，且只在 GT 类别那一张上计算损失；推理时由分类分支决定读哪一张。这样 mask 分支只需要回答"这是不是该类目标的一部分"，不用在像素级再做一次多类竞争——这就是讲义说的"decouples mask prediction from classification"。A、D 都是伪理由；C 恰好相反，每类一张会**增加**输出通道。

### Q4 — 答案：B

torchvision 检测模型把类别 0 留给背景，分类头做的是 C+1 类 softmax，所以 4 个前景类需要 `num_classes = 5`，讲义 Step 5 和本节代码 `build_custom_maskrcnn(num_classes=5)` 正是这个设定。C 是 COCO 预训练权重的类别数（含背景与占位）。

### Q5 — 答案：B

20×20 的目标在 stride 32 的 P5 上还不到一个格子，几乎没有空间信息。FPN 按 proposal 尺寸把小目标路由到高分辨率的浅层（P2/P3）、大目标路由到 P4/P5，让感受野与目标大小匹配。FPN 的自顶向下路径保证了浅层也有足够的语义，这正是它比"只用 P5"或"只用 P2"都好的原因。

### Q6 — 答案：B

讲义 Use It 部分：模型根据 `model.training` 决定行为——训练时 `model(images, targets)` 返回损失字典（可以直接 `sum(loss_dict.values())` 后反传），推理时 `model(images)` 返回 `list[dict]`。注意 torchvision 实际返回的损失有 5 项：`loss_classifier`、`loss_box_reg`、`loss_mask`、`loss_objectness`、`loss_rpn_box_reg`，与讲义公式里的 5 项一一对应。

### Q7 — 答案：B

torchvision 已经在内部把 28×28 的 mask 按框的位置和大小粘贴（paste）回原图尺寸，输出 `(N, 1, H, W)` 的 [0,1] 概率。用法：`(p['masks'] > 0.5).squeeze(1)` 得到 `(N, H, W)` 的布尔 mask。A 描述的是 mask head 的内部输出；C 是全景/实例 id 图的另一种表示，torchvision 不这样返回。

### Q8 — 答案：C

小数据集没有足够信号去更新几千万个 backbone 参数，容易过拟合。冻结预训练的 backbone 和 FPN，只训练 RPN 与两个 head，是讲义 Step 6 的标准做法（"On 500-image datasets this is the difference between convergence and overfitting"）。

### Q9 — 参考答案

(a) 计算（`spatial_scale = 0.25`）：
- `x1 = 10·0.25 − 0.5 = 2.0`，`y1 = 20·0.25 − 0.5 = 4.5`，`x2 = 100·0.25 − 0.5 = 24.5`，`y2 = 90·0.25 − 0.5 = 22.0`
- `bin_w = (24.5 − 2.0)/7 ≈ 3.214`，`bin_h = (22.0 − 4.5)/7 = 2.5`
- 第一个采样点在第一个 bin 的中心：`x = 2.0 + 3.214/2 ≈ 3.607`，`y = 4.5 + 2.5/2 = 5.75`（最后一个是 `(22.893, 20.75)`）
- 归一化：`gx = 2·(3.607 + 0.5)/50 − 1 ≈ −0.836`，`gy = 2·(5.75 + 0.5)/50 − 1 = −0.75`

(b) 两个 0.5 是两种不同的"半像素约定"：
- `c * spatial_scale - 0.5`：对应 torchvision 的 `aligned=True`。把"像素格子的左上角坐标"换成"像素中心坐标"体系——特征图第 i 个像素的中心在连续坐标 `i` 处，而框坐标是连续的边界坐标，所以要整体平移半个像素。不减 0.5 会让采样整体偏移半个特征图像素。
- `2 * (xx + 0.5) / W - 1`：`grid_sample` 在 `align_corners=False` 时，`-1` 和 `+1` 表示整张图最左/最右像素的**外边缘**，第 i 个像素中心对应 `2(i + 0.5)/W − 1`。这一步把"像素中心坐标 `xx`"换成 grid_sample 要求的归一化坐标。
- linspace 的 `bin/2` 偏移让每个采样点落在 bin 中心，等价于 `sampling_ratio=1`（每个 bin 采 1 个点）。

(c) `grid` 形状 `(1, 7, 7, 2)`，`grid_sample` 输出 `(1, 16, 7, 7)`，`squeeze(0)` 后是 `(16, 7, 7)`，即 `(C, output_size, output_size)`。

### Q10 — 参考答案

`(0,0,20,20)` 缩放后 `x1 = 0·0.25 − 0.5 = −0.5`，`x2 = 5 − 0.5 = 4.5`，`bin_w = 5/7 ≈ 0.714`，第一个采样点 `x = −0.5 + 0.357 ≈ −0.143`，落在特征图左边界之外（-1 到 0 之间），y 方向同理。

差异来源是**越界处理方式不同**：
- `F.grid_sample` 默认 `padding_mode="zeros"`：对 `x = −0.143` 做双线性插值时，用到索引 −1 和 0 两个邻居，越界的 −1 被当成 0，所以结果约为 `0.857 × f[0]`（被"拉暗"）。
- torchvision 的 RoIAlign 内核：坐标在 `(−1, 0]` 时先**夹到 0**，直接取 `f[0]`；只有小于 −1 或大于边长时才返回 0。

因此靠近图像边缘的框，两种实现会给出明显不同的值。讲义练习 1 的"100 个随机框"如果有框贴近边界，`max|diff|` 就不会在 `1e-5` 以内。要完全对齐，需要在采样前手动复现 torchvision 的规则（`(−1, 0]` 夹到 0、超出 `[−1, H]` 置 0）；`padding_mode="border"` 只能对齐 `(−1, 0)` 这一段，对更远的越界点（torchvision 返回 0）反而不一致。`main()` 里三个框的采样点都在特征图内部，所以不会触发这个问题。

### Q11 — 参考答案

```python
def trainable_by_module(model):
    stats = {}
    for name, module in model.named_children():
        stats[name] = sum(p.numel() for p in module.parameters() if p.requires_grad)
    return stats

custom = freeze_backbone(build_custom_maskrcnn(num_classes=5))
print(trainable_by_module(custom))
# 预期：{'transform': 0, 'backbone': 0, 'rpn': >0, 'roi_heads': >0}
```

torchvision 的 `MaskRCNN`（继承自 `GeneralizedRCNN`）顶层有四个子模块：
- `transform`：`GeneralizedRCNNTransform`，负责缩放和归一化，没有可训练参数；
- `backbone`：ResNet 主体（`backbone.body`）+ FPN（`backbone.fpn`），冻结后应为 0；
- `rpn`：RPN head（objectness + 框回归），仍可训练；
- `roi_heads`：box head、`box_predictor`、mask head、`mask_predictor`，仍可训练，其中两个 predictor 是新换上的、随机初始化的。

要点：①冻结是通过 `requires_grad = False` 实现的，优化器最好只接收 `filter(lambda p: p.requires_grad, model.parameters())`；②代码注释强调了 FPN 在 `model.backbone` 里，所以冻结 backbone 就同时冻结了 FPN；③BatchNorm 的 running stats 是 buffer，不受 `requires_grad` 控制。

### Q12 — 参考回答要点

- **前向流程**：①图像经 `transform` 缩放/归一化；②ResNet backbone 输出 stride 4/8/16/32 的多层特征；③FPN 自顶向下 + 横向连接，得到 P2–P5（以及额外的池化层）；④RPN 在各层的每个位置对 K 个 anchor 预测 objectness 和框偏移，取 top-K、IoU 0.7 NMS，得到约 1000 个 proposal；⑤按 proposal 大小选 FPN 层，RoIAlign 抽出 7×7（box 分支）和 14×14（mask 分支）特征；⑥box head 做 C+1 类分类和框精修，NMS 后得到最终检测；⑦mask head 对检测框输出 28×28×C 的 mask，取预测类别那一张，再粘贴回原图尺寸。
- **相对 Faster R-CNN 的两处改动**：①新增并行的 mask 分支（一个小 FCN）；②用 RoIAlign 替换 RoIPool。
- **损失**：`L_rpn_cls + L_rpn_box + L_box_cls + L_box_reg + L_mask`，mask 损失只在正样本 RoI 的 GT 类别通道上算。
- **加分点**：指出训练时 mask 分支只对正样本 RoI 计算；推理时 mask 分支用的是 box head 精修后的框，而不是原始 proposal。

### Q13 — 参考回答要点

- **问题**：RoIPool 两次量化——框坐标映射到特征图后取整、划分 bin 时每个 bin 边界再取整，再在 bin 内取最大值。每次取整误差可达一个特征图像素，stride 16/32 时相当于原图十几到几十个像素的错位。
- **RoIAlign**：保持浮点坐标，每个 bin 内取若干规则采样点做**双线性插值**，再平均（或取最大），全程不取整，梯度也能平滑地传回特征图。
- **为什么对 mask 更关键**：框分类对几个像素的偏移不敏感；mask 需要逐像素对齐，特征错位直接变成边界错位。讲义提到 RoIAlign 让 COCO mask AP 提升约 3–4 个点。
- **sampling_ratio**：每个 bin 在每个方向上采样点的个数。`sampling_ratio=1` 就是每个 bin 只采中心一个点（本节实现与之对齐）；torchvision 中 `≤0` 表示自适应（按 bin 大小取 ceil）；Mask R-CNN 的 `MultiScaleRoIAlign` 默认用 2。
- **加分点**：知道 `aligned=True` 的半像素偏移（Q9b），以及边界处的插值规则（Q10）。

### Q14 — 参考回答要点

- **为什么每类一张 + sigmoid**：softmax 会让不同类别在每个像素上竞争，mask 分支被迫同时做分类；而分类已经由 box 分支完成。每类独立的二值 mask + BCE 让 mask 分支只学"形状"，和分类解耦。Mask R-CNN 原论文的消融实验也表明解耦的 sigmoid 方案明显优于 softmax 方案。
- **28×28 的限制**：对大目标，28×28 的 mask 被放大到几百像素后边界会锯齿、发糊，细长结构（电线、手指）容易断；mask AP 在高 IoU 阈值（如 AP@0.75）上受限。
- **改进**：①提高 mask 分辨率（讲义练习 3：56×56，代价是显存和计算）；②PointRend 等方法只在不确定的边界点上做细化；③Mask2Former 这类基于 query 的方法直接在高分辨率特征上预测整图 mask。
- **常见误区**：以为 mask head 输出的就是最终 mask——实际还要按框粘贴并阈值化。

### Q15 — 参考回答要点

- **数据**：每张图构造 `target = {"boxes": (n,4) float xyxy, "labels": (n,) int64（1..3）, "masks": (n,H,W) uint8/bool}`；框可以由 mask 的最小外接矩形生成，保证一致。增强（翻转、缩放、颜色）必须对图像、框、mask 同步变换。按 8:1:1 划分，验证集要覆盖所有类别与尺寸。
- **模型**：`maskrcnn_resnet50_fpn_v2` 预训练权重；替换 `FastRCNNPredictor(in_features, 4)` 和 `MaskRCNNPredictor(in_channels, 256, 4)`（3 类 + 背景）；冻结 `model.backbone`（含 FPN）。
- **训练**：优化器只传可训练参数，SGD/AdamW 小学习率 + warmup；batch 小时注意 BN；先训练 head，若验证集还有提升空间再解冻 backbone 高层、降低学习率继续训练。训练步就是讲义的 `loss_dict = model(images, targets)` + 求和反传，同时记录 5 项损失看哪一项卡住。
- **评估**：用 `pycocotools` 同时算 box mAP 与 mask mAP@0.5:0.95——讲义强调两个都要看：box 好 mask 差 → mask head/分辨率是瓶颈；box 就差 → 检测部分是瓶颈。部署前另外选置信度阈值和 mask 阈值（默认 0.5）。
- **加分点**：用一个固定的小样本先过拟合检查管道；可视化预测与 GT 叠加图排查标注问题。

### Q16 — 参考回答要点

- **Mask R-CNN**：两阶段、生态成熟、小到中等数据集微调稳定，torchvision/Detectron2 开箱即用；缺点是速度一般、mask 分辨率 28×28 限制边界质量。适合离线或中等实时性要求、类别固定、数据有限的场景。
- **YOLO 系分割**：单阶段、速度快，适合实时与边缘部署（见第 15 节）；通常在高 IoU 阈值的 mask 质量上不如两阶段/query 方法。
- **Mask2Former / OneFormer**：基于 query 的统一分割架构，一套模型做语义、实例、全景，精度高；训练成本和数据需求更高（第 07 节提到它们）。
- **SAM 系**：可提示分割，SAM 3 支持文本提示，适合开放类别、零样本或交互式标注；推理成本高，类别语义要靠提示或外部检测器（第 24 节）。
- **选型思路**：先定实时性与硬件约束，再看类别是否固定、标注量多少、边界精度要求多高；工程上常见"SAM 辅助标注 → 训练一个轻量专用模型上线"的组合。

---

## 六、关联知识点

### 前置知识
- [阶段 04 · 06 物体检测——从头开始的 YOLO](../../06-object-detection-yolo/docs/zh.md)：anchor、IoU、NMS、检测损失；RPN 就是一个两类的 YOLO 式头。
- [阶段 04 · 07 语义分割——U-Net](../../07-semantic-segmentation-unet/docs/zh.md)：逐像素分类、mask 与 FCN 式的 mask head。
- [阶段 04 · 05 Transfer Learning & Fine-Tuning](../../05-transfer-learning/docs/zh.md)：冻结 backbone、替换 head 的微调套路。
- [阶段 04 · 03 CNNs — LeNet 到 ResNet](../../03-cnns-lenet-to-resnet/docs/zh.md)：ResNet backbone 与多尺度特征。

### 本节被哪些后续内容用到
- [阶段 04 · 16 构建完整的视觉流程](../../16-vision-pipeline-capstone/docs/zh.md)：把 Mask R-CNN 或 YOLO 作为检测器接入端到端服务。
- [阶段 04 · 24 SAM 3 与开放词表分割](../../24-sam3-open-vocab-segmentation/docs/zh.md)：以本节为前置，从固定类别实例分割走向文本提示的开放词表分割。
- [阶段 04 · 27 多目标跟踪与视频记忆](../../27-multi-object-tracking/docs/zh.md)：以本节为前置，逐帧检测/分割 + 跨帧关联。
- [阶段 04 · 15 实时视觉——边缘部署](../../15-real-time-edge/docs/zh.md)：两阶段与单阶段模型在延迟上的取舍。

### 延伸关键词
`Faster R-CNN` · `FPN 层级分配` · `MultiScaleRoIAlign` · `PointRend` · `Cascade Mask R-CNN` · `YOLACT 原型 mask` · `Mask2Former` · `Detectron2` · `pycocotools segm mAP` · `Keypoint R-CNN`
