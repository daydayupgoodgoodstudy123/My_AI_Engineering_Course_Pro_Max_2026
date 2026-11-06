# 代码讲解 · pytorch_intro.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 11 节 PyTorch 简介 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python pytorch_intro.py`（无命令行参数；首次运行会联网下载约 11 MB 的 MNIST 到 `./mnist_data/`，结束时在当前目录写出 `mnist_mlp.pt`） ｜ **依赖**：`torch`；标准库 `struct`、`gzip`、`urllib.request`、`os`、`time`；有 CUDA 时自动用 GPU

---

## 1. 这份代码在考察什么

上一节你用纯 Python 手写了一个框架；这一节用 PyTorch 把**同一套思路**重新做一遍，任务换成真实数据集 MNIST（手写数字 10 分类）。它要你掌握：

1. **张量与设备**：数据从原始字节变成 `float32` 张量，模型和数据都要 `.to(device)`。
2. **nn.Module 的工业版**：子模块自动注册、`named_parameters()` 自动命名、`.to(device)` 递归搬运，不再需要手写 `parameters()`。
3. **autograd 取代手写 backward**：一句 `loss.backward()` 替代了第 10 节每层的 `backward()`。
4. **标准训练/评估循环**：`zero_grad → forward → loss → backward → step`，评估时 `model.eval()` + `torch.no_grad()`。
5. **对照实验思维**：Adam vs SGD+Momentum vs BatchNorm vs 余弦学习率，同一数据、同一框架，只改一个变量。
6. **模型持久化**：`state_dict` 的保存与加载，并验证加载后的准确率。

> 一句话：**概念和第 10 节一一对应，变的只是"引擎"**——C++/CUDA kernel、自动微分和十年的工程积累。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------------|
| `MNIST_BASE_URL`、`MNIST_FILES` | 模块级常量 | 数据源地址和 4 个文件名 | 原始数据 |
| `download_mnist` | 函数 | 文件不存在才下载 | 数据缓存 |
| `load_images` / `load_labels` | 函数 | 解析 IDX 二进制格式 → 张量 | 张量、dtype |
| `MNISTModel` | `nn.Module` | 784→256→128→10，ReLU + Dropout(0.2) | MLP、正则化 |
| `MNISTModelWithBatchNorm` | `nn.Module` | 同结构，Linear 后接 BatchNorm1d，无 Dropout | 批归一化 |
| `train_one_epoch` | 函数 | 一个 epoch 的训练，返回平均 loss 和准确率 | 五行训练循环 |
| `evaluate` | 函数 | `eval()` + `no_grad()` 下评估 | 推理模式 |
| `load_data` / `create_loaders` | 函数 | 下载 + 解析；包成 `TensorDataset` 和 `DataLoader` | 数据管线 |
| `run_experiment` | 函数 | 通用实验驱动：打印信息、训练若干 epoch、计时 | 实验框架 |
| `experiment_adam/sgd/batchnorm/sgd_cosine` | 函数 | 四组对照实验 | 优化器、BN、LR 调度 |
| `show_model_info` | 函数 | 逐个打印参数名、形状、数量 | `named_parameters` |
| `demo_tensor_basics` / `demo_autograd` | 函数 | 张量属性/变形演示；autograd 与手动梯度下降演示 | Tensor、autograd |
| `if __name__ == "__main__":` | 入口 | 依次跑演示、加载数据、4 个实验、保存与加载 | — |

调用关系：入口 → `demo_*` → `load_data()` → `create_loaders()` → `show_model_info()` ×2 → 4 个 `experiment_*`（前三个都走 `run_experiment`，它内部循环调用 `train_one_epoch` 和 `evaluate`）→ 重新训练一个模型 → `torch.save` → 新模型 `load_state_dict` → `evaluate`。

---

## 3. 逐段精讲

### 3.1 下载与解析 MNIST：从字节到张量

```python
def download_mnist(path="./mnist_data"):
    os.makedirs(path, exist_ok=True)
    for f in MNIST_FILES:
        filepath = os.path.join(path, f)
        if not os.path.exists(filepath):
            print(f"  Downloading {f}...")
            urllib.request.urlretrieve(MNIST_BASE_URL + f, filepath)
```

- `exist_ok=True`：目录已存在时不报错。`if not os.path.exists(...)` 让下载**幂等**——第二次运行直接用缓存。
- 讲义强调"不用 `torchvision.datasets`，自己解析原始数据"，目的是让你看清楚数据集到底是什么格式。
- ⚠️ 简化：没有校验文件完整性（如 MD5）。下载中断留下半个文件时，下次运行会跳过下载、解析时出错，需要手动删除。

```python
def load_images(filepath):
    with gzip.open(filepath, "rb") as f:
        magic, num, rows, cols = struct.unpack(">IIII", f.read(16))
        data = f.read()
        images = torch.frombuffer(bytearray(data), dtype=torch.uint8)
        images = images.reshape(num, rows * cols).float() / 255.0
    return images
```

- **IDX 格式**：图像文件头 16 字节 = 4 个大端（big-endian）无符号 32 位整数：magic、数量、行数、列数；之后是逐像素的 `uint8`。标签文件头 8 字节（magic、数量），之后每字节一个标签。
- `struct.unpack(">IIII", ...)`：`>` 表示大端，`I` 表示 4 字节无符号整数。读错字节序会得到一个巨大的错误数字。
- `torch.frombuffer(bytearray(data), dtype=torch.uint8)`：直接把字节缓冲区解释成张量，不经过 Python 列表，非常快。用 `bytearray` 而不是 `bytes`，是因为 `frombuffer` 与缓冲区**共享内存**，`bytes` 是只读的，PyTorch 会对不可写的缓冲区发出警告。
- `.reshape(num, rows * cols)`：把每张 28×28 图展平成 784 维向量，因为 MLP 的输入是一维特征。
- `.float() / 255.0`：`uint8` 转 `float32` 并归一化到 [0, 1]。神经网络对输入尺度很敏感，0–255 的原始值会让初始激活和梯度过大。
- 内存：60000 × 784 × 4 字节 ≈ 188 MB，整个训练集一次性放进内存。MNIST 没问题，ImageNet 这种规模就必须用按需读取的 `Dataset`。

```python
def load_labels(filepath):
    with gzip.open(filepath, "rb") as f:
        magic, num = struct.unpack(">II", f.read(8))
        data = f.read()
        labels = torch.frombuffer(bytearray(data), dtype=torch.uint8).long()
    return labels
```

- `.long()` 转成 `int64`：`nn.CrossEntropyLoss` 要求类别下标是 `int64`（`torch.long`）。用 `uint8` 或 `float` 都会报错。
- ⚠️ 两个函数都读出了 `magic` 但没有检查（图像应为 2051，标签应为 2049）。生产代码应校验，以便尽早发现文件传错。

### 3.2 两个模型：只差 Dropout 和 BatchNorm

```python
class MNISTModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(784, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 10),
        )

    def forward(self, x):
        return self.net(x)
```

- `super().__init__()` **必须最先调用**：`nn.Module.__init__` 会建立 `_parameters`、`_modules` 等内部字典。之后 `self.net = ...` 这一赋值被 `nn.Module.__setattr__` 拦截，自动登记为子模块——这就是"自动注册"。顺序反了会报 `cannot assign module before Module.__init__() call`。
- 只需要写 `forward`，不需要写 `backward`：autograd 会在前向时记录计算图。
- 调用时写 `model(images)` 而不是 `model.forward(images)`：`__call__` 会在调用 `forward` 前后执行 hooks，直接调用 `forward` 会绕过它们。
- 最后一层输出 **10 个 logits**，没有 softmax——`CrossEntropyLoss` 内部会做 `log_softmax`。
- 参数量：`784·256+256 + 256·128+128 + 128·10+10 = 235,146`。

```python
class MNISTModelWithBatchNorm(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(784, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Linear(128, 10),
        )
```

- 按讲义练习 1 的做法：**Linear → BatchNorm → ReLU**（BN 放在激活之前），并去掉 Dropout，以便单独观察 BN 的效果。
- `BatchNorm1d(256)` 对形状 `[batch, 256]` 的输入逐特征标准化，可训练参数是 γ、β 各 256 个；`running_mean/var` 是 buffer，不计入 `parameters()`。总参数 235,914。
- 与第 10 节的简化版不同，这里的 BN 是真正的批归一化：PyTorch 的层天然以 `[batch, features]` 为输入，训练时用批统计量、评估时用 running 统计量，反向传播由 autograd 完整推导。
- ⚠️ 在 Linear 后面紧跟 BN 时，Linear 的 bias 其实是冗余的（会被 BN 减均值抵消）。常见写法是 `nn.Linear(784, 256, bias=False)`，这里为了简洁没有这么做。

### 3.3 `train_one_epoch`：五行核心 + 统计

```python
def train_one_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss = 0
    correct = 0
    total = 0
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        correct += predicted.eq(labels).sum().item()
        total += labels.size(0)
    return total_loss / total, correct / total
```

| 行 | 作用 | 第 10 节对应 |
|----|------|-------------|
| `model.train()` | 打开 Dropout、BN 用批统计量 | `model.train()` |
| `.to(device)` | 数据搬到模型所在设备 | 无（只有 CPU） |
| `optimizer.zero_grad()` | 清空上一步的 `.grad` | `optimizer.zero_grad()` |
| `outputs = model(images)` | 前向，同时构建计算图 | `model.forward(x)` |
| `loss = criterion(...)` | 标量 loss | `criterion(pred, t)` |
| `loss.backward()` | autograd 自动求所有参数的梯度 | `criterion.backward()` + `model.backward(grad)` |
| `optimizer.step()` | 用梯度更新参数 | `optimizer.step()` |

- `model.train()` 放在函数开头，是因为上一个 epoch 结束时 `evaluate()` 把模型切到了 eval 模式。少了这一行，从第 2 个 epoch 起 Dropout 就会被关掉。
- 这里一次处理**一整个 batch**（`[64, 784]`），而第 10 节是逐样本。这是速度差距的第一个来源（向量化），第二个来源是 C++/CUDA kernel。
- `loss.item()`：把单元素张量转为 Python float。如果写成 `total_loss += loss`，每个 loss 都挂着整张计算图，一个 epoch 的图都无法释放，显存会持续增长。
- `* images.size(0)`：`CrossEntropyLoss` 默认返回批内平均。60000 = 937×64 + 32，最后一批只有 32 个样本，乘以批大小再除以总数，得到精确的逐样本平均。
- `outputs.max(1)` 返回 `(最大值, 最大值下标)`，下标就是预测类别；用 `_` 丢弃最大值。等价写法：`outputs.argmax(1)`。
- `predicted.eq(labels)` 得到布尔张量，`.sum().item()` 数出预测正确的个数。
- 注意：这里的训练准确率是"边训练边统计"的，且处于 train 模式（Dropout 开启），通常会**低于**同一时刻在训练集上用 eval 模式测得的准确率。

### 3.4 `evaluate`：`eval()` 与 `no_grad()` 缺一不可

```python
def evaluate(model, loader, criterion, device):
    model.eval()
    # ...
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            # 统计同上
```

- `model.eval()`：Dropout 变恒等，BN 用 running 统计量——保证同一输入的输出是确定的。
- `torch.no_grad()`：不构建计算图，节省显存、加快速度。讲义：*Without it, PyTorch builds a computational graph you never use.*
- 两者管的是不同的事，评估时都要用。PyTorch 还提供 `torch.inference_mode()`，限制更多、速度更快。

### 3.5 数据管线：`TensorDataset` + `DataLoader`

```python
def create_loaders(train_images, train_labels, test_images, test_labels, batch_size=64):
    train_dataset = torch.utils.data.TensorDataset(train_images, train_labels)
    test_dataset = torch.utils.data.TensorDataset(test_images, test_labels)
    train_loader = torch.utils.data.DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True
    )
    test_loader = torch.utils.data.DataLoader(
        test_dataset, batch_size=256, shuffle=False
    )
    return train_loader, test_loader
```

- `TensorDataset` 把多个第 0 维长度相同的张量"绑在一起"，`dataset[i]` 返回 `(images[i], labels[i])`。它就是一个现成的 `Dataset`（实现了 `__len__` 和 `__getitem__`）。
- 训练集 `shuffle=True`：每个 epoch 打乱顺序，避免模型学到数据的排列规律；测试集 `shuffle=False`：顺序无关，固定顺序便于复现和对比。
- 测试 batch 用 256：评估不需要反向、不存激活，显存占用小，可以用更大的 batch 提速。
- 批数：训练 `ceil(60000/64) = 938`，测试 `ceil(10000/256) = 40`。
- ⚠️ 没有设置 `num_workers`（默认 0，在主进程加载）。数据已经全在内存里，所以影响不大；如果是从磁盘读图片，讲义提到 `num_workers=4` 往往能让速度翻倍。

### 3.6 `run_experiment` 与四组对照实验

```python
def run_experiment(name, model, train_loader, test_loader, optimizer, device, epochs=10):
    # ...
    num_params = sum(p.numel() for p in model.parameters())
    print(f"  Parameters: {num_params:,}")
    print(f"  Optimizer:  {optimizer.__class__.__name__}")
    # ...
    criterion = nn.CrossEntropyLoss()
    start_time = time.time()

    for epoch in range(epochs):
        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, device)
        test_loss, test_acc = evaluate(model, test_loader, criterion, device)
        # 打印一行
    elapsed = time.time() - start_time
```

- `sum(p.numel() for p in model.parameters())`：统计参数总数的标准写法，`numel()` 是元素个数。
- `optimizer.__class__.__name__`：取对象的类名字符串（`"Adam"`、`"SGD"`），用于打印。
- 四组实验：

| 实验 | 模型 | 优化器 | 想观察什么 |
|------|------|--------|-----------|
| 1 | Dropout 版 | `Adam(lr=1e-3)` | 默认首选的基线 |
| 2 | Dropout 版 | `SGD(lr=0.01, momentum=0.9)` | 讲义练习 5：SGD+动量与 Adam 的收敛差异 |
| 3 | BatchNorm 版 | `Adam(lr=1e-3)` | 讲义练习 1：BN 能否更快到 98%+ |
| 4 | Dropout 版 | `SGD(lr=0.05, momentum=0.9)` + `CosineAnnealingLR` | 讲义练习 5 后半：调度能否让 SGD 追上 Adam |

- 每个实验都**新建模型和优化器**，互不干扰；共用同一组 DataLoader。
- ⚠️ 全文件没有调用 `torch.manual_seed(...)`，初始权重和打乱顺序每次运行都不同，各实验之间也不是同一个初始化。几个百分点以内的差距不能当成结论，要多跑几个种子。
- ⚠️ 小瑕疵：`run_experiment` 中如果 `epochs=0`，最后的 `test_acc` 未定义会报错；`experiment_sgd_cosine` 预先写了 `test_acc = 0`，前者没有。

### 3.7 余弦学习率：`get_last_lr()` 放在 `step()` 之前

```python
def experiment_sgd_cosine(train_loader, test_loader, device, epochs=10):
    model = MNISTModel().to(device)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.05, momentum=0.9)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    # ...
    for epoch in range(epochs):
        train_loss, train_acc = train_one_epoch(model, train_loader, criterion, optimizer, device)
        test_loss, test_acc = evaluate(model, test_loader, criterion, device)
        current_lr = scheduler.get_last_lr()[0]
        # 打印含 LR 的一行
        scheduler.step()
```

- 余弦退火：`lr_e = 0.05 × (1 + cos(π·e/10)) / 2`，从 0.05 平滑降到接近 0。10 个 epoch 实际使用的学习率依次为 `0.050000, 0.048776, 0.045225, 0.039695, 0.032725, 0.025000, 0.017275, 0.010305, 0.004775, 0.001224`。
- 初始 lr 用 0.05（比实验 2 的 0.01 大）：后期会衰减，所以前期可以更激进。
- `scheduler.step()` 每个 epoch 末尾调用一次（这里 `T_max` 以 epoch 为单位）。`get_last_lr()` 在 `step()` 之前读取，打印的正是本 epoch 用过的学习率。
- `get_last_lr()` 返回列表，因为优化器可以有多个 `param_groups`，每组的学习率可以不同（例如微调时骨干网络用小学习率、分类头用大学习率）。
- 这个实验没有复用 `run_experiment`，因为要在每个 epoch 之间插入 `scheduler.step()` 并打印 LR。更好的设计是给 `run_experiment` 加一个可选的 `scheduler` 参数。

### 3.8 `show_model_info`：参数是怎么被命名的

```python
def show_model_info(model, name="Model"):
    # ...
    for pname, param in model.named_parameters():
        print(f"    {pname:30s} {str(list(param.shape)):15s} ({param.numel():,} params)")
        total += param.numel()
```

- `named_parameters()` 递归遍历子模块，产生 `(名字, 参数)` 对。名字由属性路径拼成：`self.net` 的第 0 个子模块的 `weight` → `net.0.weight`。
- 对 Dropout 版，输出的是 `net.0.*`、`net.3.*`、`net.6.*`（下标 1、2、4、5 是 ReLU 和 Dropout，没有参数）；BN 版多出 `net.1.*`、`net.4.*`。
- 这些名字正是 `state_dict()` 的键。加载权重时"键不匹配"（如多了 `module.` 前缀）就是因为模型结构或包装方式不同。
- `str(list(param.shape))`：`param.shape` 是 `torch.Size`，转成列表再转字符串，才能用 `:15s` 对齐。

### 3.9 `demo_tensor_basics` 与 `demo_autograd`

```python
    x = torch.randn(3, 4)
    print(f"    shape={x.shape}, dtype={x.dtype}, device={x.device}")
    x_int = x.to(torch.int8)
    y = x.view(2, 6)
    z = x.unsqueeze(0)
```

- 一个张量的三个核心属性：`torch.Size([3, 4])`、`torch.float32`、`cpu`。
- `.to(torch.int8)`：浮点转整数**向零截断**，`randn` 的值大多落在 (-3, 3)，转换后基本是 -2～2 的小整数。这正是"量化"会丢信息的直观例子。
- `view(2, 6)`：元素总数 12 不变，只改元数据，不复制数据；`unsqueeze(0)` 在最前面加一维，得到 `[1, 3, 4]`——常用于给单个样本加上 batch 维。

```python
    x = torch.tensor([1.0, 2.0, 3.0], requires_grad=True)
    y = x ** 2 + 3 * x
    z = y.sum()
    z.backward()
    # dz/dx = 2x + 3 = [5.0, 7.0, 9.0]

    w = torch.randn(3, requires_grad=True)
    for step in range(3):
        loss = (w ** 2).sum()
        loss.backward()
        # 打印 loss 和 grad
        with torch.no_grad():
            w -= 0.1 * w.grad
        w.grad.zero_()
```

- 第一段：`z = Σ(xᵢ² + 3xᵢ) = 4 + 10 + 18 = 32`，梯度 `2x + 3 = [5, 7, 9]`。`backward()` 要求输出是**标量**，所以先 `sum()`。
- 第二段是"不用 optimizer 的手写梯度下降"，揭示了 `optimizer.step()` 和 `zero_grad()` 内部在做什么：
  - `with torch.no_grad()`：参数更新不应被记录进计算图；而且对 `requires_grad=True` 的叶子张量做原地修改，不在 `no_grad` 里会直接报错。
  - `w.grad.zero_()`：梯度默认累加，必须手动清零；末尾的 `_` 是 PyTorch 对**原地操作**的命名约定。
  - 每步 `w ← 0.8w`，所以 loss 每步乘 0.64、grad 每步乘 0.8。

### 3.10 入口：保存、加载、验证

```python
    best_model = MNISTModel().to(device)
    optimizer = torch.optim.Adam(best_model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss()
    for epoch in range(10):
        train_one_epoch(best_model, train_loader, criterion, optimizer, device)

    torch.save(best_model.state_dict(), "mnist_mlp.pt")

    loaded_model = MNISTModel().to(device)
    loaded_model.load_state_dict(
        torch.load("mnist_mlp.pt", map_location=device, weights_only=True)
    )
    _, loaded_acc = evaluate(loaded_model, test_loader, criterion, device)
```

- 保存 `state_dict()`（参数名 → 张量的有序字典），而不是整个模型对象：pickle 整个对象依赖类定义和模块路径，代码一重构就加载不了。
- 加载时先**新建同结构的模型**，再 `load_state_dict`。键名或形状对不上会直接报错，这是一种安全检查。
- `map_location=device`：在 GPU 上保存、在 CPU 上加载时必须指定，否则会尝试把张量放回不存在的 cuda 设备。
- `weights_only=True`：只反序列化张量等安全类型，防止恶意 checkpoint 通过 pickle 执行任意代码。
- `evaluate` 内部会调用 `loaded_model.eval()`，所以加载后不需要额外切换模式（但单独做推理时一定记得 `model.eval()`）。
- ⚠️ 设计上的浪费：`best_model` 用和实验 1 完全相同的配置**从头再训练 10 个 epoch**，只是为了演示保存。更高效的做法是让 `experiment_adam` 返回模型，直接保存它。
- ⚠️ `mnist_mlp.pt` 写在当前工作目录，`./mnist_data` 也是相对路径——在哪个目录运行，文件就落在哪里。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手动解析 IDX，不用 `torchvision.datasets` | 看清数据格式，不依赖额外库 | 需要自己处理字节序、校验；生产中用成熟的数据集库 |
| 全部数据一次性加载为张量 | MNIST 只有约 188 MB，最简单、最快 | 大数据集要用自定义 `Dataset` 按需读取 + `num_workers` |
| 最后一层输出 logits，用 `CrossEntropyLoss` | 数值稳定，梯度简洁 | 推理需要概率时再单独 softmax |
| `train_one_epoch` 开头调 `model.train()` | 防止被上一次 `evaluate` 留在 eval 模式 | 无代价，强烈推荐的习惯 |
| `loss.item() * batch_size` 统计 | 精确的逐样本平均，且不持有计算图 | `.item()` 会触发 GPU 同步，大规模训练中改为每 N 步记录一次 |
| 每个实验新建模型和优化器 | 实验互相独立 | 没有固定随机种子，不同实验的初始化不同 |
| 余弦实验单独写循环 | 需要插入 `scheduler.step()` | 代码重复；可给 `run_experiment` 加 `scheduler` 参数 |
| 保存 `state_dict` + `weights_only=True` | 可移植、安全 | 断点续训还需保存优化器、调度器、epoch、随机状态 |
| 重新训练一个模型用于保存 | 演示保存/加载流程 | 多花一倍训练时间；应直接保存实验中得到的模型 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `import ... as ...` | `import torch.nn as nn` | 给模块起别名，PyTorch 社区的通用约定 |
| 模块级常量（全大写） | `MNIST_BASE_URL`、`MNIST_FILES` | 约定俗成表示"不应被修改" |
| 默认参数 | `def download_mnist(path="./mnist_data")` | 不传参数时使用默认值 |
| `os.makedirs(..., exist_ok=True)` | `download_mnist` | 递归建目录，已存在不报错 |
| `os.path.join` / `os.path.exists` | `os.path.join(path, f)` | 跨平台拼接路径、判断文件是否存在 |
| `with` 上下文管理器 | `with gzip.open(filepath, "rb") as f:` | 离开代码块时自动关闭文件，即使出了异常 |
| `with` 用于切换状态 | `with torch.no_grad():` | 进入时关闭梯度记录，离开时恢复 |
| `struct.unpack` | `struct.unpack(">IIII", f.read(16))` | 按格式字符串解析二进制：`>` 大端，`I` 4 字节无符号整数 |
| `bytes` vs `bytearray` | `bytearray(data)` | 前者不可变，后者可变；`frombuffer` 需要可写缓冲区 |
| 元组解包 | `magic, num, rows, cols = ...`；`train_loss, train_acc = train_one_epoch(...)` | 函数返回多个值时一次接收 |
| `_` 占位变量 | `_, predicted = outputs.max(1)` | 表示"这个值我不需要" |
| 类继承 + `super().__init__()` | `class MNISTModel(nn.Module)` | 必须先调用父类构造函数，`nn.Module` 才能注册子模块 |
| 生成器表达式 | `sum(p.numel() for p in model.parameters())` | 不建中间列表，直接求和 |
| 增量赋值 / 原地运算 | `w -= 0.1 * w.grad`；`total += ...` | 对张量是原地修改；对 int 是重新绑定 |
| 方法名末尾下划线 | `w.grad.zero_()` | PyTorch 约定：带 `_` 的方法原地修改张量 |
| `__class__.__name__` | `optimizer.__class__.__name__` | 取对象所属类的名字 |
| f-string 表达式与格式符 | `f"{'='*60}"`、`f"{num_params:,}"`、`f"{epoch+1:2d}"`、`f"{pname:30s}"`、`f"{elapsed/epochs:.1f}"`、`f"{current_lr:.6f}"` | 花括号里可以写表达式；`,` 千分位；`2d` 宽 2 的整数；`30s` 宽 30 的字符串；`.1f` 1 位小数 |
| 相邻字符串自动拼接 | `print(f"  Epoch ..." f"Train Loss: ..." ...)` | 括号内相邻的字符串字面量会自动连成一个，方便换行书写 |
| `time.time()` | `start_time = time.time()` | 当前时间戳（秒），相减得到耗时 |
| 条件表达式 | `torch.device("cuda" if torch.cuda.is_available() else "cpu")` | 一行内的 if/else |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行，被 import 时不执行 |

---

## 6. 运行结果解读

> **未实际运行**（原因：当前环境未安装 `torch`，且脚本需要联网下载 MNIST）。以下是根据代码与讲义推断的预期输出。

**确定性的部分**（与随机数无关，或可以精确推出）：

```text
  torch.randn(3, 4):
    shape=torch.Size([3, 4]), dtype=torch.float32, device=cpu
  .to(torch.int8):
    dtype=torch.int8
  .view(2, 6):
    shape=torch.Size([2, 6])
  .unsqueeze(0):
    shape=torch.Size([1, 3, 4])

  x = [1.0, 2.0, 3.0]
  y = x^2 + 3x
  z = sum(y) = 32.0
  dz/dx = 2x + 3 = [5.0, 7.0, 9.0]

  Train: 60,000 images
  Test:  10,000 images
  Image shape: 784 features (28x28 flattened)
  Classes: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

    Total: 235,146 parameters        ← Dropout 版
    Total: 235,914 parameters        ← BatchNorm 版（多 768 个 γ/β）
```

- `demo_autograd` 的三步手动梯度下降：`w` 随机，但相邻两步 loss 之比恒为 0.64、grad 之比恒为 0.8。
- 余弦实验每行末尾的 `LR:` 依次是 `0.050000 → 0.048776 → … → 0.001224`（见 3.7）。

**随机的部分**（每次运行不同）：

- 讲义给出的参考：Adam + Dropout 训练 10 个 epoch，测试准确率约 **97.8%**；CPU 上约 30 秒，GPU 约 5 秒（同结构在第 10 节的纯 Python 框架上约 45 分钟）。
- 讲义练习 1 的预期：BatchNorm 版应能在更少的 epoch 内达到 98% 以上。
- 训练准确率在前几个 epoch 可能**低于**测试准确率：训练统计时 Dropout 开启，且是整个 epoch 的平均值（包含早期较差的模型）；测试时 Dropout 关闭，用的是 epoch 结束时的模型。这不是 bug。
- 最后一行 `Loaded model test accuracy` 应与重新训练的 `best_model` 的测试准确率完全相同——加载的是同一份权重，而 `evaluate` 处于 eval 模式，结果是确定的。

---

## 7. 动手改一改

1. **固定随机种子**：在入口处加 `torch.manual_seed(0)`，连续运行两次，确认实验 1 的每个 epoch 数字完全一致（CPU 上）；然后换 3 个不同的种子，看实验之间的差距是否稳定。
2. **复用实验模型**：让 `experiment_adam` 同时返回 `model`，直接保存它，删掉最后"重新训练 10 个 epoch"的代码，对比总运行时间。
3. **给 `run_experiment` 加 `scheduler=None` 参数**：有调度器时每个 epoch 末尾 `scheduler.step()` 并打印 LR，从而把 `experiment_sgd_cosine` 合并进去。
4. **自定义 Dataset（讲义练习 4）**：写一个 `MNISTDataset(Dataset)`，在 `__getitem__` 里才做 `/255.0` 和 reshape，用 `DataLoader(..., num_workers=2)` 加载，对比速度。
5. **混合精度（讲义练习 3，需 GPU）**：在 `train_one_epoch` 中加入 `torch.amp.autocast(device_type="cuda")` 和 `GradScaler`，测量每秒处理的样本数。
6. **LR finder（讲义练习 2）**：学习率从 `1e-7` 指数增长到 `1.0`，记录每个 batch 的 loss，选出 loss 开始上升之前的学习率，再用它重新训练（参考测验 Q12）。

---

## 8. 常见坑

- **设备不一致**：模型 `.to("cuda")` 了，数据没搬 → `Expected all tensors to be on the same device`。每个 batch 都要 `.to(device)`。
- **标签 dtype 错误**：`CrossEntropyLoss` 的类别标签必须是 `int64`；本文件用 `.long()` 转换。用 `uint8` 或 `float` 会报错。
- **在 `CrossEntropyLoss` 前加 softmax**：不报错，但训练效果明显变差。
- **`total_loss += loss`（没写 `.item()`）**：整个 epoch 的计算图都无法释放，显存持续增长。
- **评估后忘记切回 `train()`**：本文件在 `train_one_epoch` 开头调用 `model.train()` 规避了这个问题；自己写循环时容易漏。
- **加载权重时 `map_location` 缺失**：GPU 上保存的 checkpoint 在 CPU 机器上加载会报 CUDA 相关错误。
- **对非连续张量用 `view`**：`permute`/`transpose` 之后直接 `view` 会报错，改用 `reshape` 或先 `.contiguous()`。
