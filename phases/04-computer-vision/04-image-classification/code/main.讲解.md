# 代码讲解 · main.py

> **所属小节**：阶段 04 · 计算机视觉 · 第 04 节 图像分类 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数；有 CUDA 时自动用 GPU，否则用 CPU） ｜ **依赖**：`numpy`、`torch`（`torch.utils.data`、`torch.optim`）；不需要 torchvision，不下载任何数据集

---

## 1. 这份代码在考察什么

这份代码**手工**搭起一条完整的图像分类训练管线，刻意不用 `torchvision.datasets`，让每个环节都"看得见"：

1. **数据层**：用确定性的合成数据模拟 CIFAR-10（32×32 RGB、10 类），用 `Dataset` + `DataLoader` 负责取样、打乱和组 batch。
2. **增强层**：用闭包写出 `standardize`、`random_hflip`、`random_crop`、`compose`，理解 torchvision transforms 背后在做什么。
3. **损失层**：mixup（batch 级增强）+ 软标签交叉熵，以及内置的 label smoothing。
4. **训练循环的五条不变式**：`train()/eval()`、`zero_grad()`、`.item()`、`no_grad`、对 logits 直接 argmax。
5. **超越准确率的评估**：混淆矩阵 + 逐类 precision / recall / F1。

> 一句话：**大多数分类 bug 不在模型里，而在管线里**——这份代码就是一条每一步都可以检查的"标准管线"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `synthetic_cifar` | 函数 | 生成每类具有特定颜色/频率模式的 32×32 图像并打乱 | 可复现的数据集 |
| `ArrayDataset` | `Dataset` 子类 | 按下标取一张图，应用 transform，HWC→CHW 转成张量 | 数据集接口 |
| `standardize` / `random_hflip` / `random_crop` / `compose` | 返回闭包的工厂函数 | 标准化、随机水平翻转、reflect 填充随机裁剪、串联 | 数据增强 |
| `mixup_batch` | 函数 | 在 batch 内随机配对，混合图像与 one-hot 标签 | mixup |
| `soft_cross_entropy` | 函数 | 对软目标分布计算交叉熵 | 软标签损失 |
| `MiniClassifier` | `nn.Module` 子类 | 5 个 Conv-BN-ReLU + 2 次池化 + GAP 分类头（约 14.1 万参数） | 小型 CNN |
| `train_one_epoch` | 函数 | 一个 epoch 的训练，返回平均损失与（近似）训练准确率 | 训练循环 |
| `evaluate` | 函数（`@torch.no_grad()`） | 验证集上的损失、准确率与混淆矩阵 | 评估循环 |
| `per_class_report` | 函数 | 从混淆矩阵算逐类 P / R / F1 | 逐类指标 |
| `main` | 函数 | 组装数据、模型、优化器、调度器，训练 5 个 epoch 并打印报告 | — |

数据流：`synthetic_cifar` → 切分 90%/10% → 两个 `ArrayDataset`（训练用增强 transform，验证只做标准化）→ 两个 `DataLoader` → 每个 epoch：`train_one_epoch` → `evaluate` → `scheduler.step()` → 最后用最后一个 epoch 的混淆矩阵调用 `per_class_report`。

---

## 3. 逐段精讲

### 3.1 合成数据集：可复现、可学、带噪声

```python
def synthetic_cifar(num_per_class=300, num_classes=10, seed=0):
    rng = np.random.default_rng(seed)
    X = []
    Y = []
    for c in range(num_classes):
        centre = rng.uniform(0, 1, (3,))
        freq = 2 + c
        for _ in range(num_per_class):
            yy, xx = np.meshgrid(np.linspace(0, 1, 32), np.linspace(0, 1, 32), indexing="ij")
            r = np.sin(xx * freq) * 0.5 + centre[0]
            g = np.cos(yy * freq) * 0.5 + centre[1]
            b = (xx + yy) * 0.5 * centre[2]
            img = np.stack([r, g, b], axis=-1) + rng.normal(0, 0.08, (32, 32, 3))
            img = np.clip(img, 0, 1).astype(np.float32)
            X.append(img)
            Y.append(c)
    X = np.stack(X)
    Y = np.array(Y)
    idx = rng.permutation(len(X))
    return X[idx], Y[idx]
```

- 每个类别有自己的颜色中心 `centre`（3 个随机数）和空间频率 `freq = 2 + c`，所以类别信息同时藏在颜色和纹理里；高斯噪声（σ=0.08）迫使模型学"信号"而不是记住像素。
- 输出已经是 `float32`、值域 [0,1]（相当于"已除以 255"的 normalized 形式），布局 HWC。
- **最后的 `permutation` 很关键**：生成时样本按类别顺序排列（先 200 张类 0，再 200 张类 1……），如果不打乱，后面"前 90% 训练、后 10% 验证"的切分会让验证集几乎全是类 9。讲义把"未打乱的训练集""被污染的验证集"列为最常见的管线 bug。
- ⚠️ 讲义说"同一管线换成真实 CIFAR-10 也能直接用"；但这个合成任务远比真实数据简单，验证精度很高并不代表模型强，只代表**管线是通的**。

### 3.2 `ArrayDataset`：`Dataset` 协议

```python
class ArrayDataset(Dataset):
    def __init__(self, X, Y, transform=None):
        self.X = X
        self.Y = Y
        self.transform = transform

    def __len__(self):
        return len(self.X)

    def __getitem__(self, i):
        img = self.X[i]
        if self.transform is not None:
            img = self.transform(img)
        img = torch.from_numpy(np.ascontiguousarray(img)).permute(2, 0, 1).float()
        return img, int(self.Y[i])
```

- PyTorch 的 map-style 数据集只需要实现两个魔术方法：`__len__`（数据集多大）和 `__getitem__`（第 i 个样本是什么）。`DataLoader` 负责按（打乱后的）下标调用 `__getitem__`，再用默认的 collate 函数把多个 `(img, label)` 叠成 `(N,3,32,32)` 的图像张量和 `(N,)` 的 `int64` 标签张量。
- **transform 在 NumPy/HWC 上做**，最后才 `permute(2, 0, 1)` 转 CHW——与第 01 节"先在 HWC 上标准化、最后转置"的顺序一致。
- `np.ascontiguousarray`：防御式写法。`torch.from_numpy` 不支持负步长的数组（例如未 `.copy()` 的 `img[:, ::-1, :]`），先转成连续内存可以避免这类报错。`.float()` 确保 dtype 是 `float32`。
- `int(self.Y[i])`：把 NumPy 整数转成 Python int，collate 后得到 `LongTensor`——`cross_entropy` 要求类别标签是 `int64`。

### 3.3 增强：用闭包做"可配置的函数"

```python
def random_hflip(p=0.5):
    def _fn(img):
        if np.random.random() < p:
            return img[:, ::-1, :].copy()
        return img
    return _fn


def random_crop(pad=4):
    def _fn(img):
        h, w = img.shape[:2]
        padded = np.pad(img, ((pad, pad), (pad, pad), (0, 0)), mode="reflect")
        y = np.random.randint(0, 2 * pad + 1)
        x = np.random.randint(0, 2 * pad + 1)
        return padded[y:y + h, x:x + w, :]
    return _fn


def compose(*fns):
    def _fn(img):
        for fn in fns:
            img = fn(img)
        return img
    return _fn
```

- **闭包**：外层函数接收配置（`p`、`pad`、`mean/std`），返回一个只接收 `img` 的内层函数 `_fn`，内层函数"记住"了外层变量。这和 torchvision 中 `RandomHorizontalFlip(p=0.5)` 这种"先构造、再调用"的对象是同一个思路。
- `img[:, ::-1, :]`：HWC 布局下沿 W 轴（第 1 轴）反转 = 水平翻转。`.copy()` 消除负步长视图。
- `random_crop`：先在 H、W 两轴各填充 `pad` 个像素（通道轴 `(0, 0)` 不填充），`mode="reflect"` 镜像边缘内容而不是补黑边——讲义："black borders are a signal the model would learn to ignore in a non-useful way"。然后随机选一个 `h×w` 的窗口，相当于随机平移最多 ±4 像素。
- ⚠️ `randint(0, 2 * pad + 1)`：`randint` 的上界不包含在内，所以偏移是 0..8 共 9 种，覆盖对称的 ±4 平移。讲义 Step 2 写的是 `randint(0, 2 * pad)`，少了最右/最下的偏移，是 off-by-one（测验 Q9）；代码这里是对的。
- `compose(*fns)`：`*fns` 收集任意个参数为元组，按顺序依次应用。训练用 `compose(random_hflip(), random_crop(pad=4), standardize(mean, std))`，**先几何增强、最后标准化**，因为 reflect 填充的值应来自原始像素尺度。
- ⚠️ 增强用的是 NumPy 的**全局**随机状态 `np.random`，而 `main` 只调用了 `torch.manual_seed(0)`，所以每次运行的增强和 mixup 的 λ 都不同，结果不能逐位复现。需要复现时应额外 `np.random.seed(...)`（并为多进程 DataLoader 设置 `worker_init_fn`）。

### 3.4 mixup 与软交叉熵

```python
def mixup_batch(x, y, num_classes, alpha=0.2):
    if alpha <= 0:
        return x, F.one_hot(y, num_classes).float()
    lam = float(np.random.beta(alpha, alpha))
    idx = torch.randperm(x.size(0), device=x.device)
    x_mixed = lam * x + (1 - lam) * x[idx]
    y_onehot = F.one_hot(y, num_classes).float()
    y_mixed = lam * y_onehot + (1 - lam) * y_onehot[idx]
    return x_mixed, y_mixed


def soft_cross_entropy(logits, soft_targets):
    log_probs = F.log_softmax(logits, dim=-1)
    return -(soft_targets * log_probs).sum(dim=-1).mean()
```

- **batch 内配对**：`torch.randperm` 生成一个随机排列，`x[idx]` 就是"把 batch 打乱后的另一份"，每张图与另一张随机图按 λ 混合，不需要再从数据集中额外取样。整个 batch 共用一个 λ。
- `λ ~ Beta(0.2, 0.2)`：α 很小时 Beta 分布呈 U 形，λ 大多接近 0 或 1——多数时候"轻微混合"，偶尔强混合。
- `alpha <= 0` 时退化为不混合，只返回 one-hot，便于做消融实验。
- `soft_cross_entropy` 是交叉熵的一般形式 `−Σ q_c log p_c`：目标为 one-hot 时就是普通交叉熵；目标为混合分布时就是 mixup 损失；目标为 `(1−ε)·onehot + ε/C` 时就是 label smoothing（测验 Q11）。
- 用 `F.log_softmax` 而不是 `torch.log(F.softmax(...))`：前者内部用 log-sum-exp，数值稳定。
- 为什么 mixup 放在训练步而不是 `Dataset` 里：它需要**两张图**配对，属于 batch 级操作，放在前向传播旁边最自然（讲义 Step 3）。

### 3.5 `MiniClassifier`：比 TinyResNet 更小的 CNN

```python
        self.features = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1, bias=False),
            nn.BatchNorm2d(32), nn.ReLU(inplace=True),
            # ... 32→32，MaxPool；32→64，64→64，MaxPool；64→128
        )
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(128, num_classes),
        )
```

- 形状：`(N,3,32,32)` → 两个 32 通道卷积 → 池化 `16×16` → 两个 64 通道卷积 → 池化 `8×8` → 128 通道卷积 → GAP → `(N,128)` → `(N,10)`。
- 参数量约 14.1 万（卷积约 13.9 万、BN 1,280、分类头 1,290）。讲义 Step 5 用的是上一节的 `TinyResNet`，并在 import 处留了"占位符"；`main.py` 改用自带的 `MiniClassifier`，让文件**自包含**、可以直接运行。
- 卷积 `bias=False` + BN、`ReLU(inplace=True)`、GAP 分类头——都是上一节讲过的约定。

### 3.6 `train_one_epoch`：五条不变式的落地

```python
def train_one_epoch(model, loader, optimizer, device, num_classes, use_mixup=True):
    model.train()
    total, correct, loss_sum = 0, 0, 0.0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        if use_mixup:
            x_m, y_soft = mixup_batch(x, y, num_classes)
            logits = model(x_m)
            loss = soft_cross_entropy(logits, y_soft)
        else:
            logits = model(x)
            loss = F.cross_entropy(logits, y, label_smoothing=0.1)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        loss_sum += loss.item() * x.size(0)
        total += x.size(0)
        with torch.no_grad():
            pred = logits.argmax(dim=-1)
            correct += (pred == y).sum().item()
    return loss_sum / total, correct / total
```

| 行 | 对应的不变式 | 违反时的症状 |
|----|-------------|-------------|
| `model.train()` | ① 训练/评估模式切换 | BN 用 running stats 训练、Dropout 不生效，学习效果变差 |
| `optimizer.zero_grad()` 在 `backward()` 前 | ② 每步清零梯度 | 梯度跨 batch 累加，表现得像学习率忽大忽小、训练不稳定 |
| `loss.item()` | ③ 累计指标时脱离计算图 | 计算图无法释放，内存持续增长 |
| `with torch.no_grad():` 计算预测 | ④ 不需要梯度的计算关掉 autograd | 多余的显存与时间开销 |
| `logits.argmax(dim=-1)` | ⑤ 直接对 logits 取 argmax | 对 softmax 取 argmax 结果相同，只是多一次计算 |

- `loss.item() * x.size(0)`：`loss` 是 batch 内的**平均**损失，乘以 batch 大小还原成总和，最后除以样本总数，得到正确的逐样本平均（最后一个 batch 可能不满 128，直接平均各 batch 的损失会有偏差）。
- ⚠️ mixup 开启时，`correct` 是拿"混合图像的预测"与"未混合的标签 `y`"比较，只是粗略的进度信号（讲义的代码注释也这样说明），判断效果要看验证集。
- ⚠️ 训练损失（软交叉熵，含 mixup）与验证损失（普通交叉熵）**口径不同**，不能直接比较大小来判断过拟合。

### 3.7 `evaluate` 与 `per_class_report`

```python
@torch.no_grad()
def evaluate(model, loader, device, num_classes):
    model.eval()
    # ...
    cm = torch.zeros(num_classes, num_classes, dtype=torch.long)
    for x, y in loader:
        # ...
        pred = logits.argmax(dim=-1)
        for t, p in zip(y.cpu(), pred.cpu()):
            cm[t, p] += 1
```

```python
def per_class_report(cm):
    tp = cm.diag().float()
    fp = cm.sum(dim=0).float() - tp
    fn = cm.sum(dim=1).float() - tp
    prec = tp / (tp + fp).clamp_min(1)
    rec = tp / (tp + fn).clamp_min(1)
    f1 = 2 * prec * rec / (prec + rec).clamp_min(1e-9)
    return prec, rec, f1
```

- `@torch.no_grad()` 作为**装饰器**，让整个函数都在不记录梯度的模式下运行；`model.eval()` 让 BN 使用 running statistics。两者缺一不可、各管一件事。
- 混淆矩阵约定：**行 = 真实类别，列 = 预测类别**。对角线是预测正确的数量。
- `cm.sum(dim=0)` 按列求和 = 被预测为该类的总数，减去 TP 得 FP；`cm.sum(dim=1)` 按行求和 = 该类真实样本总数，减去 TP 得 FN。
- `.clamp_min(1)`：分母至少为 1，某类从未被预测时 precision 记为 0 而不是 `0/0 = NaN`；F1 的分母用 `1e-9` 防止 P、R 同时为 0。
- ⚠️ 逐样本的 Python 循环在大验证集上很慢，可以用 `torch.bincount(y * C + pred, minlength=C*C).view(C, C)` 向量化（测验 Q10）。

### 3.8 `main`：组装一切

```python
    torch.manual_seed(0)
    X, Y = synthetic_cifar(num_per_class=200)
    split = int(0.9 * len(X))
    # ...
    train_loader = DataLoader(train_ds, batch_size=128, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False, num_workers=0)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = MiniClassifier(num_classes=10).to(device)
    optimizer = SGD(model.parameters(), lr=0.05, momentum=0.9, weight_decay=5e-4, nesterov=True)
    scheduler = CosineAnnealingLR(optimizer, T_max=5)

    for epoch in range(5):
        current_lr = scheduler.get_last_lr()[0]
        tr_loss, tr_acc = train_one_epoch(model, train_loader, optimizer, device, 10, use_mixup=True)
        va_loss, va_acc, cm = evaluate(model, val_loader, device, 10)
        scheduler.step()
```

- 2000 张图（200/类）→ 1800 训练、200 验证。训练集 `shuffle=True`，验证集 `shuffle=False`（评估不需要打乱，固定顺序便于对比）。`num_workers=0` 表示在主进程里加载，最简单、也避免多进程随机种子问题。
- `mean = std = 0.5 / 0.25`：合成数据值域 [0,1]，用这组粗略统计量标准化到大约 [-2, 2]。讲义 Use It 部分强调：真实 CIFAR-10 应使用它**自己**的统计量 `(0.4914, 0.4822, 0.4465) / (0.2470, 0.2435, 0.2616)`。
- **优化器**：SGD + momentum 0.9 + Nesterov + weight decay 5e-4，是 CIFAR 上的经典强基线。
- **调度器**：`CosineAnnealingLR(T_max=5)` 每个 epoch 调用一次 `step()`，学习率从 0.05 余弦下降到接近 0。`current_lr` 在训练**之前**读取，打印的是本 epoch 实际使用的学习率（讲义 Step 5 在 `step()` 之后读取，会错位一行，见测验 Q8）。
- 最后的逐类报告使用的是**最后一个 epoch** 的混淆矩阵 `cm`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 合成数据代替 CIFAR-10 | 离线、确定、几秒钟跑完；专注验证管线 | 任务太简单，指标不代表真实性能；真实项目用 `torchvision.datasets.CIFAR10` 或自定义数据集 |
| 闭包实现 transform | 透明、无依赖，便于理解 torchvision | 生产中用 `torchvision.transforms.v2`，支持张量/GPU、检测框等 |
| 增强用全局 `np.random` | 代码最短 | 不可复现、多进程加载时需要处理种子；更好的做法是传入 `Generator` |
| mixup 放在训练步 | batch 级操作，需要两张图配对 | 与 DataLoader 解耦，但每步多一次 `randperm` 和混合计算 |
| 一个 `soft_cross_entropy` 统一处理软标签 | mixup / label smoothing / 蒸馏都能复用 | 对硬标签比 `F.cross_entropy` 略慢 |
| 混淆矩阵用 Python 循环 | 一目了然 | 大数据集慢，改用 `bincount` |
| 自带 `MiniClassifier` | 文件自包含，不依赖上一节的代码路径 | 容量较小；讲义 Step 5 用的是 TinyResNet |
| `num_workers=0` | 简单、可调试 | 真实训练中数据加载会成为瓶颈，应开多进程并 `pin_memory=True` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from ... import ...` | `from torch.utils.data import Dataset, DataLoader` | 只导入需要的名字 |
| 类继承与魔术方法 | `class ArrayDataset(Dataset)`、`__len__`、`__getitem__` | 实现这两个方法，对象就支持 `len(ds)` 和 `ds[i]` |
| `None` 默认值与判断 | `transform=None`；`if self.transform is not None:` | 可选参数的惯用写法 |
| `_` 占位变量 | `for _ in range(num_per_class):` | 不使用循环变量 |
| 闭包（嵌套函数） | `def random_hflip(p=0.5): def _fn(img): ... return _fn` | 内层函数捕获外层变量，返回"带配置的函数" |
| `*args` 收集参数 | `def compose(*fns):` | 接收任意数量的位置参数，打包成元组 |
| 负步长切片 | `img[:, ::-1, :]` | 沿某轴反转；返回视图，配合 `.copy()` 得到独立数组 |
| 元组解包赋值 | `x, y = x.to(device), y.to(device)`；`total, correct, loss_sum = 0, 0, 0.0` | 一行给多个变量赋值 |
| 条件表达式 | `device = "cuda" if torch.cuda.is_available() else "cpu"` | 三元表达式 |
| 增强赋值 | `loss_sum += loss.item() * x.size(0)`、`cm[t, p] += 1` | 原地累加 |
| `with` 上下文管理器 | `with torch.no_grad():` | 代码块内关闭梯度记录，退出后自动恢复 |
| 装饰器 | `@torch.no_grad()` 修饰 `evaluate` | 把整个函数包在 no_grad 上下文里 |
| `zip` | `for t, p in zip(y.cpu(), pred.cpu()):` | 成对遍历真实标签与预测 |
| 多返回值 | `return loss_sum / total, correct / total, cm` | 返回元组，调用方解包 |
| `float()` / `int()` | `float(np.random.beta(...))`、`int(self.Y[i])` | NumPy 标量转 Python 原生类型 |
| f-string 格式符 | `f"lr {current_lr:.4f}"`、`f"train {tr_loss:.3f}/{tr_acc:.3f}"` | 保留 4 位 / 3 位小数 |
| 张量方法链 | `cm.sum(dim=0).float() - tp`、`(tp + fp).clamp_min(1)` | 连续调用张量方法，每步返回新张量 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才训练；被 import 时只提供函数 |

---

## 6. 运行结果解读

**未实际运行（当前环境缺少 `torch`）。** 根据代码，运行后会看到 5 行训练日志和 10 行逐类指标，格式如下（`lr` 列由余弦公式精确计算得出；损失和准确率的具体数值取决于随机性，这里不编造）：

```text
epoch 0  lr 0.0500  train <软交叉熵>/<近似训练准确率>  val <交叉熵>/<验证准确率>
epoch 1  lr 0.0452  train .../...  val .../...
epoch 2  lr 0.0327  train .../...  val .../...
epoch 3  lr 0.0173  train .../...  val .../...
epoch 4  lr 0.0048  train .../...  val .../...

per-class metrics:
  class 0  prec ...  rec ...  f1 ...
  ...
  class 9  prec ...  rec ...  f1 ...
```

预期现象与解读：

- **lr 列**：`0.05 × (1 + cos(π·t/5)) / 2`，依次为 0.0500、0.0452、0.0327、0.0173、0.0048——余弦退火前期下降慢、后期下降快。
- **验证准确率应快速升高**：讲义说在合成数据上"五个 epoch 内接近完美的验证准确率"（讲义用的是更大的 TinyResNet 和更多数据）。这里每类只有 200 张、模型更小，但类别模式（颜色中心 + 频率）很容易区分，验证准确率同样应该很高。如果 5 个 epoch 后仍接近 10%（随机猜），说明管线有 bug。
- **训练损失高于验证损失并不奇怪**：训练用的是 mixup 软标签交叉熵（有一个由目标熵决定的下界），验证用的是普通交叉熵，并且训练时还有随机增强。
- **训练准确率可能低于验证准确率**：训练准确率是用混合图像的预测与原始标签比较得出的，只是近似值。
- **逐类指标**：在这个简单任务上，各类 P/R/F1 应该都接近 1；若某两类互相混淆（混淆矩阵中出现成对的非对角元素），可以检查它们的 `centre` 颜色是否相近。
- 由于 NumPy 全局随机状态未设种子，每次运行的数值会略有不同。

---

## 7. 动手改一改

1. （易）在 `main` 开头加 `np.random.seed(0)`，连续运行两次，确认（CPU 上）输出完全一致。
2. （易）把 `use_mixup=True` 改成 `False`（走 label smoothing 分支），对比训练损失和验证准确率，解释训练损失为什么下降得更低（讲义练习 1）。
3. （中）实现 Cutout：在每张训练图上随机把一个 8×8 方块置零（注意在标准化之后置零，0 才对应"数据集均值"），并做消融：无增强 / 翻转+裁剪 / 翻转+裁剪+Cutout / 翻转+裁剪+mixup（讲义练习 2）。
4. （中）用 `torch.bincount` 改写混淆矩阵的构建，并写一个 `print_confusion(cm)` 打印 10×10 表格（参考讲义 Step 6）。
5. （中）实现 CutMix 版本的 `cutmix_batch`：随机矩形面积比例决定标签混合系数 λ，复用 `soft_cross_entropy`。
6. （难）加入 ECE 计算：把验证集预测按最大概率分成 10 个箱，计算每箱"平均置信度 − 准确率"的加权平均；再拟合一个温度参数 T 并比较缩放前后的 ECE。

---

## 8. 常见坑

- **对 softmax 输出调用 `cross_entropy`**：不报错，但训练停滞。
- **数据未打乱就切分**：生成/读取时按类别排序的数据，直接切片会导致验证集类别严重偏斜。
- **`randint` 上界不包含**：`randint(0, 2*pad)` 少一种偏移，增强不对称。
- **翻转后不 `.copy()` 就 `torch.from_numpy`**：负步长数组会报错。
- **训练/验证损失口径不同**：mixup/label smoothing 下训练损失天然偏高，不要据此判断"欠拟合"。
- **只设了 `torch.manual_seed`**：NumPy 的增强与 mixup λ 仍然随机，实验无法复现。
- **在最后一个 batch 上直接平均 batch 损失**：batch 大小不等时会有偏差，本代码用"乘以 batch 大小再除以总数"规避了这一点。
