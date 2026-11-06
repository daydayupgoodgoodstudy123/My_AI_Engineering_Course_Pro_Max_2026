# 测验 · PyTorch 简介（Introduction to PyTorch）

> **阶段 03 · 深度学习核心 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/pytorch_intro.py](../code/pytorch_intro.py) ｜ 代码讲解：[code/pytorch_intro.讲解.md](../code/pytorch_intro.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Eager execution（即时执行） | `y = model(x)` 立刻算出结果，print、pdb、if/else 都能直接用；这是 PyTorch 胜过 TF 1.x 静态图的关键 |
| 2 | Tensor 三属性 | shape、dtype、device；参与同一运算的张量必须在同一 device，否则报 `Expected all tensors to be on the same device` |
| 3 | 变形操作 | `view` 只改元数据、要求内存连续；`reshape` 总能成功（必要时会复制）；`permute` 换维度顺序；`unsqueeze/squeeze` 增删大小为 1 的维 |
| 4 | Autograd | 前向时把运算记录成有向无环图（tape），`.backward()` 逆序回放；只有 `requires_grad=True` 的**叶子张量**会把梯度存到 `.grad`，且默认**累加** |
| 5 | nn.Module | 在 `__init__` 里赋值子模块/参数即自动注册；提供 `parameters()`、`named_parameters()`、`.to(device)`、`state_dict()`、`train()/eval()` |
| 6 | 损失函数的输入 | `CrossEntropyLoss` 内部 = `LogSoftmax + NLLLoss`，必须喂 **logits**；二分类用 `BCEWithLogitsLoss` |
| 7 | 五行训练循环 | `zero_grad → model(x) → criterion → backward → step`；评估时 `model.eval()` + `torch.no_grad()` |
| 8 | Dataset / DataLoader | Dataset 实现 `__len__` 和 `__getitem__`；DataLoader 负责批处理、打乱、`num_workers` 多进程加载 |
| 9 | 模型保存 | 保存 `state_dict()`（参数名 → 张量的有序字典）而不是整个对象；加载用 `load_state_dict(torch.load(..., weights_only=True))` |
| 10 | 学习率调度与混合精度 | `CosineAnnealingLR` 每个 epoch `scheduler.step()` 一次；AMP 用 `autocast` 低精度前向 + `GradScaler` 缩放 loss 防止梯度下溢 |

### 核心技能（能动手做到）

- [ ] 从零写出 `train_one_epoch` 和 `evaluate`，正确处理 `.to(device)`、`model.train()/eval()`、`torch.no_grad()`，并按样本数加权统计平均 loss
- [ ] 用 `gzip + struct` 解析 MNIST 原始 IDX 文件为 `float32` 图像张量 `[N, 784]`（归一化到 0–1）和 `int64` 标签张量
- [ ] 手算 `784→256→128→10` MLP 的参数量（235,146），并用 `named_parameters()` 打印每个参数的名字和形状来核对
- [ ] 不用 optimizer，只用 autograd 写一个梯度下降循环（`torch.no_grad()` 内原地更新 + `grad.zero_()`），并解释每一行为什么必要
- [ ] 保存 `state_dict` 后在新模型里加载，验证测试准确率与保存前一致
- [ ] 给 SGD 接上 `CosineAnnealingLR`，能说出 `T_max=10` 时每个 epoch 实际使用的学习率
- [ ] 能把第 10 节手写框架的每个组件对应到 PyTorch API，并说清 PyTorch 多做了什么（autograd、C++/CUDA kernel、设备管理、序列化）

---

## 二、基础自测（选择题）

**Q1.** `nn.BatchNorm1d(256)` 有多少个**可训练参数**（即出现在 `model.parameters()` 中的元素个数）？

- A. 256
- B. 512
- C. 1024（γ、β、running_mean、running_var 各 256）
- D. 0，BatchNorm 没有可训练参数

**Q2.** 本节 `MNISTModel` 的最后一层是 `nn.Linear(128, 10)`，没有 softmax，损失是 `nn.CrossEntropyLoss()`。如果有人"好心"在最后加一个 `nn.Softmax(dim=1)`，会发生什么？

- A. 直接报错，维度不匹配
- B. 能正常训练，但相当于做了两次 softmax，梯度被压扁，收敛变慢、效果变差，而且不会有任何报错
- C. 准确率会提高，因为输出变成了概率
- D. 和不加完全等价

**Q3.** 设 `x = torch.randn(2, 3, 4)`，下面哪一行会**抛出 RuntimeError**？

- A. `x.view(2, 12)`
- B. `x.reshape(6, 4)`
- C. `x.permute(2, 0, 1).view(24)`
- D. `x.unsqueeze(0)`

**Q4.** 执行下面的代码之后，哪个说法正确？

```python
x = torch.tensor([1.0, 2.0, 3.0], requires_grad=True)
y = x ** 2 + 3 * x
z = y.sum()
z.backward()
```

- A. `x.grad` 和 `y.grad` 都是 `[5., 7., 9.]`
- B. `x.grad` 是 `[5., 7., 9.]`；`y` 是非叶子张量，`y.grad` 为 `None`（除非事先调用 `y.retain_grad()`）
- C. `x.grad` 是 `[2., 4., 6.]`
- D. `x.grad` 为 `None`，因为还没有调用 `optimizer.step()`

**Q5.** 关于 `model.eval()` 和 `torch.no_grad()`，正确的是：

- A. `model.eval()` 会关闭梯度计算，所以有了它就不需要 `torch.no_grad()`
- B. `model.eval()` 切换 Dropout/BatchNorm 的行为；`torch.no_grad()` 停止构建计算图、节省显存和计算；评估时两者都应该使用
- C. `torch.no_grad()` 会把 Dropout 关掉
- D. 两者完全等价，用哪个都行

**Q6.** `train_one_epoch` 里写的是 `total_loss += loss.item() * images.size(0)`，最后返回 `total_loss / total`。乘以 `images.size(0)` 的主要原因是：

- A. 放大梯度，加速训练
- B. `CrossEntropyLoss` 默认 `reduction='mean'` 返回的是批内平均；60000 不能被 64 整除，最后一批只有 32 个样本，按样本数加权才能得到精确的全数据平均 loss
- C. 把张量转换成 Python float
- D. 防止 loss 变成负数

**Q7.** `experiment_sgd_cosine` 中：初始 `lr=0.05`，`CosineAnnealingLR(optimizer, T_max=10)`，每个 epoch 结束调用一次 `scheduler.step()`。**第 6 个 epoch**（从 1 开始数）训练时使用的学习率是：

- A. 0.05
- B. 0.025
- C. 0.0125
- D. 0.0

**Q8.** 用 float16 做混合精度训练时需要 `GradScaler`，它解决的核心问题是：

- A. float16 计算太慢
- B. 很小的梯度在 float16 下会下溢成 0；先把 loss 乘一个大系数再反向，`step` 前再除回去，并在出现 inf/NaN 时跳过这一步、自动调小系数
- C. 让模型权重以 float16 保存，节省硬盘
- D. 自动调节学习率

---

## 三、动手 / 代码题

**Q9.** 阅读 `demo_autograd()` 的后半段：

```python
    w = torch.randn(3, requires_grad=True)
    for step in range(3):
        loss = (w ** 2).sum()
        loss.backward()
        print(f"\n  Step {step}: loss={loss.item():.4f}, grad={w.grad.tolist()}")
        with torch.no_grad():
            w -= 0.1 * w.grad
        w.grad.zero_()
```

(a) 不管 `w` 的初值是多少，相邻两步的 `loss` 之比是多少？`grad` 之比是多少？
(b) 如果去掉 `with torch.no_grad():`，直接写 `w -= 0.1 * w.grad`，会发生什么？
(c) 如果删掉 `w.grad.zero_()`，假设某一维初值 `w₀ = 1.0`，三步打印出的 grad 分别是多少？

**Q10.** 预测 `show_model_info(MNISTModelWithBatchNorm(), ...)` 打印出的参数名、形状和总数，并解释为什么参数名里没有 `net.2`、`net.5`。

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

**Q11.** 找 bug。下面是一位同学改写的训练/评估代码，至少有 5 处问题，请逐一指出并修正。

```python
model = MNISTModel()
model.to("cuda")
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
criterion = nn.CrossEntropyLoss()

for epoch in range(10):
    total_loss = 0
    for images, labels in train_loader:
        outputs = torch.softmax(model(images), dim=1)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss

    correct = 0
    for images, labels in test_loader:
        images, labels = images.cuda(), labels.cuda()
        outputs = model(images)
        correct += (outputs.argmax(1) == labels).sum().item()
```

**Q12.** 讲义练习 2：实现一个学习率查找器（LR finder）`lr_finder(model, loader, criterion, device, start_lr=1e-7, end_lr=1.0, num_iters=100)`。要求学习率按指数从 `start_lr` 增长到 `end_lr`，每个 iteration 训练一个 batch，记录 `(lr, loss)`，loss 超过历史最小值 4 倍时提前停止，返回两个列表。

---

## 四、面试高频题

**Q13.**（基础必考）讲讲 PyTorch autograd 的原理：计算图是什么时候建的？叶子张量和非叶子张量有什么区别？为什么梯度默认累加？`detach()`、`torch.no_grad()`、`requires_grad_(False)` 各用在什么场景？

**Q14.**（基础必考）为什么 `nn.CrossEntropyLoss` 要求输入 logits 而不是 softmax 概率？如果模型输出已经是概率，应该怎么算损失？

**Q15.**（工程实践）你用 PyTorch 在单卡上训练，发现 GPU 利用率只有 30%。你会怎么排查和优化？

**Q16.**（原理深挖）混合精度训练中 float16 和 bfloat16 有什么区别？为什么 fp16 需要 `GradScaler` 而 bf16 通常不需要？"master weights" 是什么？

**Q17.**（追问型）为什么推荐保存 `state_dict` 而不是 `torch.save(model)`？`weights_only=True`、`map_location` 是做什么的？如果要支持"断点续训"，checkpoint 里还需要保存哪些东西？

---

## 五、参考答案与解析

### Q1 — 答案：B

可训练参数只有 γ（`weight`）和 β（`bias`），各 256 个，共 512——讲义表格里写的也是 `2 * features`。`running_mean`、`running_var`（以及 `num_batches_tracked`）是 **buffer**：会随 `.to(device)` 移动、会出现在 `state_dict()` 里，但不在 `parameters()` 里，优化器不会更新它们。所以 C 混淆了 parameter 和 buffer。

### Q2 — 答案：B

`CrossEntropyLoss` 内部会再做一次 `log_softmax`。输入已经是 0–1 的概率时，各类别之间的差距被压得很小，再做一次 softmax 后分布接近均匀，梯度很小且失真。代码不会报错，只会"悄悄地"训练得很差——讲义原话：*produces wrong gradients silently*。推理时如果需要概率，再在模型外面单独 `softmax` 即可。

### Q3 — 答案：C

`permute` 只改步长（stride），不移动数据，结果是**非连续**张量；`view` 要求内存连续，因此报错（提示使用 `.reshape(...)`）。修正：`x.permute(2, 0, 1).contiguous().view(24)` 或直接 `reshape(24)`（必要时会复制数据）。A 中 `x` 是新建的连续张量，可以 `view`；B 的 `reshape` 总能成功；D 得到形状 `(1, 2, 3, 4)`。

### Q4 — 答案：B

`dz/dx = 2x + 3 = [5, 7, 9]`，和本节代码 `demo_autograd()` 的打印一致。autograd 第一条规则：只有 `requires_grad=True` 的**叶子张量**才把梯度存到 `.grad`；`y` 是运算产生的中间结果，默认不保留梯度（访问时 `y.grad` 为 `None` 并有警告），需要的话先调用 `y.retain_grad()`。D 错：`.backward()` 本身就计算并写入梯度，与 optimizer 无关。

### Q5 — 答案：B

两者管的是不同的事情：`eval()` 改变**层的行为**（Dropout 不再丢弃，BN 使用 running 统计量）；`no_grad()` 改变 **autograd 的行为**（不记录计算图，省显存、提速）。本节 `evaluate()` 两个都用了。只用 `no_grad` 不用 `eval`：Dropout 仍在随机丢弃；只用 `eval` 不用 `no_grad`：结果正确，但白白建了计算图、浪费显存。

### Q6 — 答案：B

`loss.item()` 是这一批的平均 loss。`60000 = 937 × 64 + 32`，共 938 批，最后一批只有 32 个样本。直接对 938 个批平均值再取平均，会让最后这一小批的权重偏大。乘以批大小得到"这一批的 loss 总和"，最后除以样本总数，就是精确的逐样本平均。另外 `.item()` 把标量张量转成 Python float，不再引用计算图，避免显存泄漏（这是 C 的部分含义，但不是乘 `size(0)` 的原因）。

### Q7 — 答案：B

`CosineAnnealingLR`（`eta_min=0`）：`lr_e = 0.05 × (1 + cos(π·e/10)) / 2`，e 是已经调用 `scheduler.step()` 的次数。第 6 个 epoch 开始前已经 step 了 5 次，`cos(π/2) = 0`，lr = 0.025。10 个 epoch 依次为 `0.050000, 0.048776, 0.045225, 0.039695, 0.032725, 0.025000, 0.017275, 0.010305, 0.004775, 0.001224`。代码在 `scheduler.step()` **之前**调用 `get_last_lr()`，打印的正是本 epoch 实际使用的学习率。

### Q8 — 答案：B

float16 能表示的最小正规数约 `6e-5`（次正规数最小约 `6e-8`），很多梯度比这还小，会直接变成 0。`GradScaler` 先 `scaler.scale(loss)`（乘一个大系数，如 65536）再 backward，`scaler.step(optimizer)` 内部先除回去（unscale），如果发现 inf/NaN 就跳过这一步，`scaler.update()` 动态调整系数。D 错，它不改学习率。

### Q9 — 参考答案

(a) `grad = 2w`，更新 `w ← w - 0.1·2w = 0.8w`。所以 grad 每步变为 **0.8 倍**，loss = `Σw²` 每步变为 **0.64 倍**。例如若某步 loss=2.0000，下一步就是 1.2800。

(b) `w` 是 `requires_grad=True` 的叶子张量，在 autograd 记录下对它做原地修改会报错：`RuntimeError: a leaf Variable that requires grad is being used in an in-place operation.`。参数更新本身不应该被记录进计算图，所以放在 `torch.no_grad()` 里（`optimizer.step()` 内部也是这么做的）。

(c) 梯度会累加：
- Step 0：grad = `2·1.0 = 2.0`，更新后 w = `1.0 - 0.1·2.0 = 0.8`
- Step 1：grad = `2.0 + 2·0.8 = 3.6`，更新后 w = `0.8 - 0.36 = 0.44`
- Step 2：grad = `3.6 + 2·0.44 = 4.48`

梯度越积越大，相当于在用一个"动量没有衰减"的错误更新，这就是忘记 `zero_grad()` 的典型症状。`w.grad.zero_()` 末尾的下划线表示**原地操作**，是 PyTorch 的命名约定。

### Q10 — 参考答案

```text
    net.0.weight                   [256, 784]      (200,704 params)
    net.0.bias                     [256]           (256 params)
    net.1.weight                   [256]           (256 params)
    net.1.bias                     [256]           (256 params)
    net.3.weight                   [128, 256]      (32,768 params)
    net.3.bias                     [128]           (128 params)
    net.4.weight                   [128]           (128 params)
    net.4.bias                     [128]           (128 params)
    net.6.weight                   [10, 128]       (1,280 params)
    net.6.bias                     [10]            (10 params)
    Total: 235,914 parameters
```

- 名字由"属性名 + Sequential 中的下标 + 参数名"拼成：`self.net` → `net`，第 0 个子模块 → `net.0`。
- 下标 2、5 是 `nn.ReLU()`，没有参数，所以不出现。（Dropout 版模型中 `net.1/net.2/net.4/net.5` 是 ReLU 和 Dropout，同样不出现，总数 235,146。）
- `nn.Linear(784, 256).weight` 的形状是 `[out, in] = [256, 784]`，前向计算 `y = x @ Wᵀ + b`。
- BN 的 `weight/bias` 就是 γ/β；总数比 Dropout 版多 `2·256 + 2·128 = 768`，即 235,914。

### Q11 — 参考答案

问题清单：
1. **训练数据没搬到 GPU**：模型在 cuda，`images/labels` 在 cpu → `Expected all tensors to be on the same device`。加 `images, labels = images.to(device), labels.to(device)`。
2. **CrossEntropyLoss 前做了 softmax**：应直接传 logits（见 Q2）。
3. **没有 `optimizer.zero_grad()`**：梯度跨 batch 累加（见 Q9c）。
4. **`total_loss += loss` 累加的是张量**：每个 loss 都挂着计算图，整个 epoch 的图都无法释放，显存持续增长。应写 `loss.item()`。
5. **评估时没有 `model.eval()`**：Dropout 仍在随机丢弃。
6. **评估时没有 `torch.no_grad()`**：白白构建计算图，浪费显存。
7. **评估完没有切回 `model.train()`**：下一个 epoch 的 Dropout 会一直关闭（本节代码在 `train_one_epoch` 开头调用 `model.train()`，就是为了避免这一点）。
8. （小问题）`model.to("cuda")` 写死设备，没有 GPU 的机器会报错；用 `torch.device("cuda" if torch.cuda.is_available() else "cpu")`。

修正版：

```python
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = MNISTModel().to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
criterion = nn.CrossEntropyLoss()

for epoch in range(10):
    model.train()
    total_loss = 0.0
    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(images)                  # logits
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * images.size(0)

    model.eval()
    correct = 0
    with torch.no_grad():
        for images, labels in test_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            correct += (outputs.argmax(1) == labels).sum().item()
```

### Q12 — 参考答案

```python
def lr_finder(model, loader, criterion, device,
              start_lr=1e-7, end_lr=1.0, num_iters=100):
    optimizer = torch.optim.SGD(model.parameters(), lr=start_lr)
    gamma = (end_lr / start_lr) ** (1 / (num_iters - 1))   # 每步乘的系数
    lrs, losses = [], []
    best = float("inf")
    model.train()
    data_iter = iter(loader)
    for i in range(num_iters):
        try:
            images, labels = next(data_iter)
        except StopIteration:                               # 数据用完就重新开始
            data_iter = iter(loader)
            images, labels = next(data_iter)
        images, labels = images.to(device), labels.to(device)

        lr = start_lr * gamma ** i
        for group in optimizer.param_groups:               # 手动设置学习率
            group["lr"] = lr

        optimizer.zero_grad()
        loss = criterion(model(images), labels)
        loss.backward()
        optimizer.step()

        lrs.append(lr)
        losses.append(loss.item())
        best = min(best, loss.item())
        if loss.item() > 4 * best:                          # loss 爆炸，停止
            break
    return lrs, losses
```

要点：
- 指数增长：`lr_i = start_lr · gammaⁱ`，`gamma = (end/start)^(1/(n-1))`，保证第 0 步是 `start_lr`、最后一步是 `end_lr`。画图时 x 轴用对数刻度。
- 修改学习率要通过 `optimizer.param_groups`，这也是所有 `lr_scheduler` 的底层机制。
- 选择规则（讲义）：选在 loss 开始上升**之前**的位置；常见经验是取 loss 下降最陡处，或最小 loss 对应 lr 的约 1/10。
- ⚠️ LR finder 会改动模型权重，正式训练前要重新初始化模型（或事先 `copy.deepcopy(model.state_dict())` 备份再恢复）。

### Q13 — 参考回答要点

- **何时建图**：动态图（define-by-run）。每执行一个涉及 `requires_grad=True` 张量的运算，就创建一个节点（结果张量的 `grad_fn`），记录输入和反向函数。每次 forward 都重新建图，所以控制流（if/for）可以随数据变化。
- **backward**：从标量 loss 出发，按拓扑逆序调用各节点的反向函数，用链式法则把梯度传到叶子张量；默认 backward 完就释放图（再次 backward 需要 `retain_graph=True`）。
- **叶子 vs 非叶子**：用户直接创建的张量（如参数）是叶子，梯度存在 `.grad`；中间结果默认不保存梯度，需要 `retain_grad()`。
- **为什么累加**：①同一参数在图中被多次使用时，梯度本来就要求和（如共享权重、RNN）；②支持梯度累积。代价是必须手动 `zero_grad()`（PyTorch 2.x 默认 `set_to_none=True`，直接把 `.grad` 设为 None，省一次内存写）。
- **三者区别**：`detach()` 返回一个与原张量共享数据、但脱离计算图的新张量（如 RL 中的 target、GAN 中截断梯度）；`torch.no_grad()` 是上下文管理器，块内所有运算都不记录图（推理、参数更新）；`requires_grad_(False)` 冻结某个参数（微调时冻结骨干网络）。
- **常见误区**：认为 `model.eval()` 会关梯度；在 `no_grad` 里计算的 loss 调用 `backward` 时报错找不到 `grad_fn`。

### Q14 — 参考回答要点

- **数值稳定**：先 softmax 再取 log，当某个 logit 很大时 `exp` 溢出，很小的概率 `log` 后变成 `-inf`。`CrossEntropyLoss` 内部用 `log_softmax`，基于 log-sum-exp 技巧：`log_softmax(z)ᵢ = zᵢ - max(z) - log Σ exp(zⱼ - max(z))`，全程不会溢出。
- **梯度简洁**：对 logits 的梯度就是 `softmax(z) - onehot(y)`，数值稳定且不会因为 softmax 饱和而消失。
- **已经是概率怎么办**：用 `torch.log(probs.clamp_min(1e-8))` 再接 `nn.NLLLoss`；或者更好地，修改模型，去掉最后的 softmax。
- **加分点**：`CrossEntropyLoss` 还支持 `label_smoothing`、`ignore_index`（如忽略 padding token）、`weight`（类别不平衡）；标签可以是类别下标（int64），新版本也支持概率分布形式的软标签。

### Q15 — 参考回答要点

先定位瓶颈，再对症下药：
1. **数据加载是瓶颈**（最常见）：用 profiler 或简单计时看 `next(loader)` 的耗时。优化：`num_workers > 0`（讲义：4 个 worker 在磁盘密集型任务上可让速度翻倍）、`pin_memory=True` 配合 `.to(device, non_blocking=True)`、把解码/增强挪到 GPU 或提前预处理。
2. **batch 太小**：GPU kernel 启动开销占比高。在显存允许内增大 batch，必要时调学习率。
3. **频繁 CPU-GPU 同步**：每步都 `loss.item()`、`print`、`.cpu()` 会强制同步。改为每 N 步记录一次。
4. **没开混合精度**：`autocast` + bf16/fp16 能用上 Tensor Core（讲义：A100 上约 2 倍）。
5. **Python 开销 / 小算子太多**：`torch.compile` 融合算子；`channels_last` 内存布局（CNN）。
6. **工具**：`torch.profiler`、`nvidia-smi dmon`、Nsight Systems。
- **常见误区**：一上来就换模型或加卡，而没有先确认瓶颈在哪。

### Q16 — 参考回答要点

- **格式区别**：fp16 = 1 符号 + 5 指数 + 10 尾数，范围小（最大约 65504），精度约 3.3 位十进制；bf16 = 1 + 8 + 7，**指数位与 fp32 相同**，范围与 fp32 一样，但精度更低（约 2–3 位）。讲义表格：bf16 "Same range as float32, less precision"，是 LLM 训练的主流。
- **为什么 fp16 要 scaler**：范围窄，小梯度下溢为 0、大激活值溢出为 inf；loss scaling 把梯度整体平移到 fp16 能表示的区间。bf16 范围和 fp32 一样，基本不会下溢，所以通常不需要。
- **Master weights**：优化器维护一份 fp32 的权重和优化器状态，前向/反向用低精度副本计算；更新时把梯度加到 fp32 权重上。否则 `w + lr·g` 中的小更新量在 fp16 里会被舍入掉（"更新消失"）。PyTorch 的 `autocast` 方式是：参数本身保持 fp32，进入 autocast 区域时按算子自动转换为低精度计算。
- **加分点**：autocast 会让 softmax、layernorm、loss 等对精度敏感的算子保持 fp32；FP8 训练（H100）是同一思路的延伸。

### Q17 — 参考回答要点

- **state_dict vs 整个模型**：`torch.save(model)` 用 pickle 序列化整个对象，加载时需要**相同的类定义和模块路径**，代码重构（改类名、挪文件）后就无法加载；`state_dict` 只是"参数名 → 张量"的有序字典，与代码结构解耦，可移植（讲义原话：*State dicts are portable*）。
- **`weights_only=True`**：只允许反序列化张量和基础类型，拒绝执行任意 pickle 代码。加载来路不明的 checkpoint 时可以防止远程代码执行攻击（新版 PyTorch 已将其设为默认值）。
- **`map_location`**：把张量加载到指定设备。例如在 GPU 上保存、在只有 CPU 的机器上加载时必须指定，否则会尝试放回 cuda 而报错。本节代码用了 `map_location=device`。
- **断点续训需要保存**：模型 `state_dict`、**优化器 `state_dict`**（Adam 的 m、v 和步数）、**学习率调度器状态**、当前 epoch / global step、`GradScaler` 状态（如用 AMP）、随机数生成器状态（Python、NumPy、torch、cuda），以及最佳指标等。只存模型权重，恢复后 Adam 的动量从 0 重新开始，loss 曲线会出现明显的跳变。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 10 构建您自己的迷你框架](../../10-mini-framework/docs/zh.md)：本节的每个 PyTorch API 都能在那里找到手写版本。
- [阶段 01 · 12 张量运算](../../../01-math-foundations/12-tensor-operations/docs/zh.md)：shape、广播、reshape/permute 的数学含义。
- [阶段 01 · 05 链式法则与自动微分](../../../01-math-foundations/05-chain-rule-and-autodiff/docs/zh.md)：autograd 的理论基础。
- [阶段 03 · 09 Learning Rate Schedules](../../09-learning-rate-schedules/docs/zh.md)：余弦退火的原理。

### 本节被哪些后续内容用到
- [阶段 03 · 12 JAX 简介](../../12-intro-to-jax/docs/zh.md)：与 PyTorch 对照的函数式框架。
- [阶段 03 · 13 调试神经网络](../../13-debugging-neural-networks/docs/zh.md)：在 PyTorch 训练中定位 loss 不降、NaN、梯度消失等问题。
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：log-sum-exp、fp16 下溢，对应 Q14、Q16。
- [阶段 04 · 03 CNN：从 LeNet 到 ResNet](../../../04-computer-vision/03-cnns-lenet-to-resnet/docs/zh.md)：用 PyTorch 搭建卷积网络。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：同样的五行训练循环，放大到语言模型。
- [阶段 19 · 45 梯度裁剪与 AMP](../../../19-capstone-projects/45-gradient-clipping-amp/docs/zh.md)：`autocast` 与 `GradScaler` 的工程化实践。
- [阶段 19 · 47 Checkpoint 保存与恢复](../../../19-capstone-projects/47-checkpoint-save-resume/docs/zh.md)：Q17 断点续训的完整实现。

### 延伸关键词
`define-by-run` · `grad_fn` · `retain_graph` · `contiguous / stride` · `buffer vs parameter` · `pin_memory` · `torch.compile` · `bf16 / fp16 / FP8` · `GradScaler` · `weights_only` · `lr_scheduler` · `TensorDataset`
