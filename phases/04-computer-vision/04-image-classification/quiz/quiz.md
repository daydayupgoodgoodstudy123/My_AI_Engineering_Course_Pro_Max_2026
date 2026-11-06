# 测验 · 图像分类（Image Classification）

> **阶段 04 · 计算机视觉 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 分类管线 | 数据集 → 增强 → 标准化 → DataLoader（批量 + 打乱）→ 模型 → logits → 交叉熵 → 反向 → 优化器 → 调度器；每一环都可能藏着"不报错的 bug" |
| 2 | logits 与交叉熵 | `CE = −z_y + log Σ exp(z_j)`（log-sum-exp 形式数值稳定）；`F.cross_entropy` 内部已含 log-softmax，**必须喂原始 logits** |
| 3 | 数据增强 | CNN 只有平移相关的归纳偏置，翻转、裁剪、颜色、遮挡的不变性要靠增强"教"出来；前提是**不改变标签** |
| 4 | Reflect 填充 + 随机裁剪 | CIFAR 社区默认策略；零填充的黑边会成为模型可以利用的"假信号" |
| 5 | Mixup / CutMix | 同时混合输入和标签（`λ ~ Beta(α, α)`），让模型学会类间平滑插值；训练损失变高、测试精度通常变好 |
| 6 | Label smoothing | 用"1−ε 加上均匀分布的 ε"代替 one-hot，防止 logits 无限变尖、改善校准；PyTorch 1.10+ 内置 `label_smoothing` 参数 |
| 7 | 训练循环五条不变式 | `train()/eval()` 切换、`zero_grad()` 在 `backward()` 前、累计指标用 `.item()`、评估时 `no_grad`、对 logits 直接 argmax |
| 8 | 超越准确率的评估 | 逐类准确率、混淆矩阵（行=真实、列=预测）、precision/recall/F1、Top-k、校准（ECE） |
| 9 | 数据集专属的 mean/std | CIFAR-10 应使用在其训练集上统计的均值方差，不要照搬 ImageNet 的 |
| 10 | 学习率调度 | SGD + momentum + nesterov + weight decay，配合按 epoch 调用的 `CosineAnnealingLR` |

### 核心技能（能动手做到）

- [ ] 用 `Dataset` / `DataLoader` 从 NumPy 数组搭建完整的数据管线，并能解释 `__len__`、`__getitem__` 的作用
- [ ] 用闭包写出 `standardize`、`random_hflip`、`random_crop`、`compose`，并能指出 `randint` 上界的 off-by-one 问题
- [ ] 从零实现 `mixup_batch` 和 `soft_cross_entropy`，并证明 label smoothing 等价于对软目标 `(1−ε)·onehot + ε/C` 做软交叉熵
- [ ] 写出包含五条不变式的 `train_one_epoch` / `evaluate`，能逐条说出违反后的症状
- [ ] 从混淆矩阵手算每一类的 precision、recall、F1，并用 `bincount` 向量化地构建混淆矩阵
- [ ] 能根据训练/验证曲线判断管线是否出了问题（例如"损失看起来合理但精度卡在 70%"）

---

## 二、基础自测（选择题）

**Q1.** 你写了 `loss = F.cross_entropy(logits.softmax(dim=-1), y)`。会发生什么？

- A. 完全正确，这是推荐用法
- B. 立刻抛出形状错误
- C. 不报错；但 `cross_entropy` 内部还会再做一次 log-softmax，相当于对 softmax 后的概率再 softmax，输出被压向均匀分布、梯度变得很小，训练很快停滞
- D. 只会让准确率精确地下降 1/C

**Q2.** 一个 3 类分类器的混淆矩阵如下（行 = 真实类别，列 = 预测类别）。类别 1 的 precision 和 recall 分别是：

```text
          pred0  pred1  pred2
true0       50     10      0
true1        5     30     15
true2        0      5     85
```

- A. precision ≈ 0.667，recall = 0.600
- B. precision = 0.600，recall ≈ 0.667
- C. precision = 0.750，recall = 0.600
- D. precision = 0.600，recall = 0.600

**Q3.** 开启 mixup 后，训练损失明显比不开时**高**，验证精度却差不多甚至更好。最合理的解释是：

- A. mixup 让模型欠拟合，应该关掉
- B. 软目标本身有熵（例如 λ=0.7 时目标是 0.7/0.3），即使预测完全等于目标，交叉熵也不可能降到 0；训练损失变高是预期行为
- C. mixup 使学习率实际减半
- D. 训练损失的计算写错了

**Q4.** 使用 `F.cross_entropy(logits, y, label_smoothing=0.1)`，类别数 C=10。PyTorch 实际使用的目标分布中，正确类别和每个错误类别的概率分别是：

- A. 0.9 和 0.0111
- B. 0.91 和 0.01
- C. 0.9 和 0.01
- D. 1.0 和 0.0

**Q5.** 对 MNIST 手写数字分类，下列哪种数据增强最可能**改变标签**、因此不应使用？

- A. ±10° 的小角度旋转
- B. 随机平移 2 个像素
- C. 水平翻转与 180° 旋转
- D. 轻微的亮度扰动

**Q6.** 训练循环中写成 `loss_sum += loss`（而不是 `loss.item()`），最主要的后果是：

- A. 结果数值完全一样，没有任何影响
- B. `loss_sum` 变成一个仍连着计算图的张量，每个 batch 的计算图都无法释放，显存/内存不断增长
- C. 会抛出类型错误
- D. 梯度会被累加两次

**Q7.** 对一个已经训练好的分类器做温度缩放（temperature scaling，`softmax(z / T)`，T>1），下列说法正确的是：

- A. Top-1 准确率会提高
- B. Top-1 准确率会下降
- C. Top-1 准确率不变（argmax 不变），只改变置信度，用来改善过度自信、降低 ECE
- D. 只有重新训练模型才能生效

---

## 三、动手 / 代码题

**Q8.** `main.py` 中使用 `SGD(lr=0.05)` 和 `CosineAnnealingLR(optimizer, T_max=5)`，训练 5 个 epoch。

```python
    for epoch in range(5):
        current_lr = scheduler.get_last_lr()[0]
        tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer, device, 10, use_mixup=True)
        va_loss, va_acc, cm = evaluate(model, val_loader, device, 10)
        scheduler.step()
        print(f"epoch {epoch}  lr {current_lr:.4f}  " ...)
```

(a) 写出 5 行输出中 `lr` 的值（4 位小数）。
(b) 讲义 Step 5 的写法是在 `scheduler.step()` **之后**才调用 `scheduler.get_last_lr()` 打印。两种写法打印出来的含义有什么不同？

**Q9.** 比较讲义与 `main.py` 中 `random_crop` 的一行差异：

```python
# 讲义 docs/en.md
        y = np.random.randint(0, 2 * pad)
# code/main.py
        y = np.random.randint(0, 2 * pad + 1)
```

`pad=4` 时，两种写法各能产生哪些裁剪偏移？讲义版本带来了什么问题？

**Q10.** `evaluate` 中用 Python 循环逐个样本更新混淆矩阵：

```python
        for t, p in zip(y.cpu(), pred.cpu()):
            cm[t, p] += 1
```

请写出一个**无 Python 循环**的等价实现（提示：`torch.bincount`），并说明原理。

**Q11.** `main.py` 中 mixup 分支用 `soft_cross_entropy`，非 mixup 分支用 `F.cross_entropy(..., label_smoothing=0.1)`。请写一个函数 `smooth_targets(y, num_classes, eps)`，使得 `soft_cross_entropy(logits, smooth_targets(y, C, eps))` 与 `F.cross_entropy(logits, y, label_smoothing=eps)` 数值相等，并说明为什么相等。

---

## 四、面试高频题

**Q12.**（基础必考）为什么分类模型输出 logits，而不是在模型里直接加 softmax？交叉熵的数值稳定实现是怎样的？

**Q13.**（工程实践）你训练的 CNN 在 CIFAR-10 上只有 70–75%，损失曲线看起来"挺正常"。你会怎样系统地排查训练管线？

**Q14.**（原理深挖）比较 mixup、CutMix 和 label smoothing：原理、各自解决什么问题、有什么副作用？

**Q15.**（原理深挖）为什么只看准确率不够？precision、recall、F1、macro/micro 平均、Top-5、ECE 分别回答什么问题？

**Q16.**（场景设计）给你一个全新的 20 类图像数据集（约 2 万张），要求从零搭建分类训练管线。你会按什么步骤搭建并验证它是"对的"？

---

## 五、参考答案与解析

### Q1 — 答案：C

`F.cross_entropy` 内部 = `log_softmax` + `nll_loss`，期望输入是**原始 logits**。传入 softmax 概率后，相当于计算 `log(softmax(softmax(z)))`：概率都在 [0,1] 内，再做一次 softmax 时各类差距被大幅压缩，输出接近均匀分布，梯度很小，训练停滞。它不会报错（B 错），形状完全合法；D 是编造的规律。讲义原话："Applying softmax yourself first is almost always a bug"。

### Q2 — 答案：A

类别 1：TP = 30；FP = 列和 − TP = (10+30+5) − 30 = 15；FN = 行和 − TP = (5+30+15) − 30 = 20。precision = 30/45 ≈ 0.667，recall = 30/50 = 0.600。B 把行列搞反了——记住**行是真实类别**（recall 看行），**列是预测类别**（precision 看列），与 `main.py` 的 `per_class_report` 一致：`fp = cm.sum(dim=0) - tp`（按列求和）、`fn = cm.sum(dim=1) - tp`（按行求和）。

### Q3 — 答案：B

软目标 `[0.7, 0.3]` 的熵为 `−(0.7 ln 0.7 + 0.3 ln 0.3) ≈ 0.611`，这是交叉熵的下界——即使预测分布与目标完全一致，损失也不会低于它。所以 mixup 下训练损失天然偏高。讲义："Training loss goes up, test accuracy goes up"。另外 `main.py` 中训练准确率是拿混合后的 logits 与**未混合**的 `y` 比较的，也只是一个粗略信号，评判效果要看验证集。

### Q4 — 答案：B

PyTorch 的实现是把 one-hot 与均匀分布混合：`target = (1 − ε)·onehot + ε/C`。正确类别 `0.9 + 0.01 = 0.91`，其余每类 `0.01`，总和为 1。A 是讲义 Key Terms 里写的 `(1−ε, ε/(C−1))` 方案（也是一种合法的平滑方式，但不是 PyTorch 的实现）；C 是讲义正文写的 `[ε/C, …, 1−ε, …]`，各项之和只有 `1 − ε/C = 0.99`，不是合法的概率分布。

### Q5 — 答案：C

讲义的规则："augmentation must preserve the label"，并举例旋转可能把 6 变成 9。水平翻转会让 2、3、7 等数字变成镜像字形，180° 旋转会把 6 和 9 互换——都改变了语义。小角度旋转、小平移、轻微亮度扰动符合手写数字的自然变化，是合理的增强。对比：CIFAR 的猫狗图片做水平翻转则完全没问题——**增强策略取决于数据集的不变性**。

### Q6 — 答案：B

`loss` 是带 `grad_fn` 的张量，`loss_sum += loss` 会让 `loss_sum` 也挂在计算图上，并且把每一个 batch 的计算图串起来，导致这些中间激活都无法释放，内存持续增长，最终 OOM。`.item()` 把它转成 Python float，断开与图的联系。这正是讲义五条不变式中的第 3 条。

### Q7 — 答案：C

所有 logits 除以同一个正数 T，不改变它们的大小顺序，argmax 不变，所以 Top-1 准确率不变。T>1 会让概率分布更平缓，降低过度自信；T 通常在验证集上通过最小化 NLL 拟合（只学一个标量，不需要重新训练模型，D 错）。讲义提到现代网络普遍过度自信，可用温度缩放或 label smoothing 修正。

### Q8 — 参考答案

(a) 余弦退火：`lr_t = 0.05 × (1 + cos(π·t/5)) / 2`：

```text
epoch 0  lr 0.0500
epoch 1  lr 0.0452
epoch 2  lr 0.0327
epoch 3  lr 0.0173
epoch 4  lr 0.0048
```

(b) `main.py` 在训练**之前**读取 `get_last_lr()`，打印的是**本 epoch 实际使用**的学习率；讲义写法在 `scheduler.step()` **之后**读取，打印的是**下一个 epoch** 将使用的学习率，却被标在当前 epoch 名下，相当于整体错位一行（若把讲义的打印位置套用到 `main.py` 的配置上，第 0 行就会显示 0.0452，最后一行显示 0.0000）。数值本身没错，但读日志时容易误判"哪个学习率对应哪个指标"。工程上建议在训练前记录，或直接从 `optimizer.param_groups[0]["lr"]` 读取。

### Q9 — 参考答案

`np.random.randint(low, high)` 的 `high` **不包含**在内：

- 讲义：`randint(0, 8)` → 偏移 ∈ {0, 1, …, 7}，共 8 种；
- `main.py`：`randint(0, 9)` → 偏移 ∈ {0, 1, …, 8}，共 9 种（已用 NumPy 实测确认取值集合）。

padded 图比原图每边多 4 像素，偏移 4 对应"不平移"，偏移 0 和 8 分别对应向两个方向平移 4 像素。讲义版本永远取不到 8，意味着**图像内容只能向一个方向平移最多 4 像素，另一个方向最多 3 像素**——增强分布不对称，也和 `torchvision.transforms.RandomCrop(32, padding=4)` 的行为（9 种偏移）不一致。这是典型的 off-by-one，不会报错，只会让增强带有轻微偏置。

### Q10 — 参考答案

```python
def confusion_matrix(y, pred, num_classes):
    idx = y.cpu() * num_classes + pred.cpu()                  # 把 (t, p) 编码成 0..C²-1 的一个整数
    counts = torch.bincount(idx, minlength=num_classes ** 2)  # 统计每个编码出现的次数
    return counts.view(num_classes, num_classes)              # 还原成 C×C 矩阵

# 在 evaluate 中替换循环：
#     cm += confusion_matrix(y, pred, num_classes)
```

原理：每个 `(真实 t, 预测 p)` 对唯一对应一个整数 `t·C + p`（类似把二维下标按行展平）；`bincount` 统计每个整数的出现次数，`minlength=C²` 保证即使某些组合没出现也有完整长度；`view(C, C)` 按行优先还原，`cm[t, p]` 恰好对应展平下标 `t·C + p`。用 NumPy 的 `np.bincount` 在一个 3 类样例上与循环版本对拍，结果完全一致。好处：把逐样本的 Python 循环变成一次向量化操作，在大验证集上快得多。

### Q11 — 参考答案

```python
import torch.nn.functional as F

def smooth_targets(y, num_classes, eps):
    onehot = F.one_hot(y, num_classes).float()
    return (1 - eps) * onehot + eps / num_classes

# soft_cross_entropy(logits, smooth_targets(y, 10, 0.1))
#   == F.cross_entropy(logits, y, label_smoothing=0.1)   （数值上相等，误差在浮点精度内）
```

推导：设 `log p = log_softmax(z)`，软目标 `q = (1−ε)·onehot + ε/C`，则

```text
−Σ_c q_c · log p_c = (1−ε)·(−log p_y) + ε · (1/C)·Σ_c (−log p_c)
```

右边正是 PyTorch 文档描述的 label smoothing 损失：`(1−ε)` 倍的普通交叉熵加上 `ε` 倍的"对所有类别取平均的负对数概率"。本环境没有 PyTorch，未直接运行上面的代码；但用 NumPy 按两种公式各算了一遍（随机 4×10 的 logits，ε=0.1），结果都是 `2.6107776…`，一致。这也说明：mixup 和 label smoothing 都可以统一看作"对软目标做交叉熵"，所以 `main.py` 只需要一个 `soft_cross_entropy` 就能同时支持两者。

### Q12 — 参考回答要点

- **为什么输出 logits**：①损失函数需要 `log softmax`，如果先 softmax 再取 log，`softmax` 可能下溢为 0，`log(0) = −∞`；②`log_softmax` 可以用 log-sum-exp 技巧稳定计算；③推理时 argmax 不需要 softmax（单调变换），省一次计算。
- **稳定实现**：`CE = −z_y + log Σ_j exp(z_j)`，而 `log Σ exp(z_j) = m + log Σ exp(z_j − m)`，其中 `m = max_j z_j`，保证指数的参数都 ≤ 0，不会上溢。PyTorch 的 `cross_entropy` 把 log-softmax 与 NLL 融合成一个算子。
- **常见误区**：在模型最后加 `nn.Softmax` 再接 `CrossEntropyLoss`（Q1 的 bug）；或者用 `nn.NLLLoss` 却忘了先做 `log_softmax`。
- **加分点**：二分类同理，用 `BCEWithLogitsLoss` 而不是 `Sigmoid + BCELoss`。

### Q13 — 参考回答要点

讲义："Most classification bugs are not in the model. They live in the pipeline"，正确设置 93% 的 CNN 在错误管线下常常只有 70–75%。排查顺序：

1. **先做 sanity check**：用一个小 batch（比如 32 张图）反复训练，应该能把训练损失压到接近 0；做不到说明模型/损失/优化器本身有 bug。
2. **数据**：可视化增强后的样本和对应标签（标签是否还对得上）；检查标准化（均值方差是否为本数据集的、是否重复标准化）；训练集是否 `shuffle=True`；验证集是否与训练集有重复/近重复样本（数据泄漏）。
3. **训练循环五条不变式**：`train()/eval()`、`zero_grad()`、`.item()`、`no_grad`、logits 直接进损失。
4. **优化**：学习率是否过大（损失后期突然发散）或调度器是否按正确的粒度（per-epoch vs per-step）调用；weight decay 是否合理。
5. **评估**：看混淆矩阵和逐类指标，判断是全面偏低还是集中在某几类。
- **加分点**：提到"先让模型在一小撮数据上过拟合"这个最便宜、最有效的检查；以及固定随机种子，让实验可复现、可对比。

### Q14 — 参考回答要点

| 方法 | 做法 | 主要作用 | 副作用 / 注意 |
|------|------|---------|--------------|
| mixup | `x = λx_i + (1−λ)x_j`，标签同比例混合，`λ ~ Beta(α, α)` | 让决策边界之间平滑过渡，减少对 one-hot 的死记硬背，提升泛化与校准 | 训练损失变高、收敛可能变慢；混合出的图像不自然 |
| CutMix | 把 `x_j` 的一个矩形块贴到 `x_i` 上，标签按面积比例混合 | 同上，同时保留局部真实纹理，还有遮挡鲁棒性 | 被贴的区域可能恰好没有目标物体，标签与内容不符 |
| label smoothing | 目标改为 `(1−ε)·onehot + ε/C` | 防止 logits 无限增大，改善校准，略提精度 | 有研究发现用 label smoothing 训练的教师模型做知识蒸馏效果变差；ε 不宜过大 |

- **何时用**：数据量不大、过拟合明显时，mixup/CutMix 是讲义所说的"最便宜的鲁棒性升级"；需要好的概率校准时用 label smoothing 或训练后做温度缩放。
- **实现要点**：mixup/CutMix 属于 **batch 级**变换，放在训练步里（与前向相邻），而不是放进 `Dataset`——`main.py` 的 `mixup_batch` 正是这样做的。

### Q15 — 参考回答要点

- **准确率的盲点**：类别不平衡时，永远预测多数类就能得到很高的准确率（90/10 的二分类恒预测多数类得 90%）。
- **precision**：预测为 c 的样本中有多少真是 c（看混淆矩阵的列）——误报代价高时关注。
- **recall**：真实为 c 的样本中有多少被找出来（看行）——漏报代价高时关注（医疗、风控）。
- **F1**：precision 与 recall 的调和平均，两者之一很低时 F1 也低。
- **macro vs micro**：macro 先算每类指标再平均，每类权重相同，能暴露小类的问题；micro 汇总所有样本再算，单标签多分类时 micro-F1 等于准确率。
- **Top-5**：正确类别是否在前 5 个预测中，适合类别之间本身就有歧义的数据集（讲义举例：Norwich terrier 与 Norfolk terrier）。
- **ECE**：把预测按置信度分箱，比较每箱的平均置信度与实际准确率，衡量"说 0.8 的时候是否真的有 80% 是对的"。
- **加分点**：看到混淆矩阵中集中的非对角块时，先去**看样本**（可能是标注错误、近似类别、缺少某种不变性），而不是盲目加数据或换优化器（与原 quiz.json 的结论一致）。

### Q16 — 参考回答要点

1. **数据切分先行**：按"来源/拍摄批次"分组切 train/val/test，避免近重复图片跨集合造成泄漏；检查类别分布是否均衡。
2. **统计本数据集的 mean/std**（只用训练集计算），不要照搬 ImageNet 的（若使用 ImageNet 预训练模型，则应沿用预训练时的统计量——见下一节）。
3. **最小管线跑通**：不加增强、小模型，先在一个小 batch 上过拟合到接近 100% 训练准确率。
4. **逐步加组件并做消融**：翻转 + reflect 填充裁剪 → mixup/CutMix → label smoothing；每次只改一处，记录验证指标（讲义练习 2 就是这种消融）。
5. **优化器与调度器**：SGD(momentum 0.9, nesterov, wd 5e-4) + 余弦退火是强基线；先做一个小范围的学习率扫描。
6. **评估**：除准确率外输出混淆矩阵、逐类 P/R/F1、Top-k、校准曲线；挑出最常混淆的类别对，人工查看样本。
7. **工程化**：固定随机种子（`torch`、`numpy`、`random` 都要设）、记录配置与指标、保存最佳 checkpoint。
- **加分点**：数据只有 2 万张时，优先考虑迁移学习（下一节）而不是从零训练。

---

## 六、关联知识点

### 前置知识
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：precision、recall、F1、混淆矩阵。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：交叉熵与 log-sum-exp。
- [阶段 03 · 06 优化器](../../../03-deep-learning-core/06-optimizers/docs/zh.md)、[阶段 03 · 09 学习率调度](../../../03-deep-learning-core/09-learning-rate-schedules/docs/zh.md)：SGD + momentum、余弦退火。
- [阶段 04 · 03 CNNs — LeNet 到 ResNet](../../03-cnns-lenet-to-resnet/docs/zh.md)：本节使用的网络结构。

### 本节被哪些后续内容用到
- [阶段 04 · 05 迁移学习与微调](../../05-transfer-learning/docs/zh.md)：复用本节的训练循环，在预训练 backbone 上微调。
- [阶段 04 · 16 构建完整的视觉流程 — Capstone](../../16-vision-pipeline-capstone/docs/zh.md)：完整的视觉工程管线。
- [阶段 04 · 17 自监督视觉](../../17-self-supervised-vision/docs/zh.md)：强数据增强是对比学习的核心。
- [阶段 02 · 17 不平衡数据](../../../02-ml-fundamentals/17-imbalanced-data/docs/zh.md)：准确率失效时的评估与处理方法。
- [阶段 03 · 13 调试神经网络](../../../03-deep-learning-core/13-debugging-neural-networks/docs/zh.md)：过拟合小 batch 等通用调试手段。

### 延伸关键词
`CutMix` · `RandAugment / AutoAugment` · `Cutout / RandomErasing` · `温度缩放（temperature scaling）` · `ECE` · `macro-F1` · `数据泄漏与近重复检测` · `Bag of Tricks` · `知识蒸馏`
