# 代码讲解 · debug_neural_nets.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 13 节 调试神经网络 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python debug_neural_nets.py`（无命令行参数，数据随机生成，CPU 几秒即可跑完） ｜ **依赖**：`torch`；标准库 `math`、`copy`

---

## 1. 这份代码在考察什么

前面几节都在教"怎么让网络跑起来"，这一节教"网络跑起来了但结果不对时怎么办"。代码是一个小型**诊断工具箱**，外加一组**故意写坏的网络**来演示每个工具能看到什么：

1. **用 hook 观察网络内部**：不改模型代码，借 PyTorch 的 forward/backward hook 记录每层的激活值和梯度统计量。
2. **把经验规则写成自动检查**：loss 是否 NaN、是否在下降、是否振荡；激活是否死亡、爆炸、塌缩；梯度是否消失、爆炸。
3. **三个经典调试技巧的实现**：overfit-one-batch、学习率查找器（LR finder）、数值梯度检查。
4. **对照实验**：学习率过大、死 ReLU、漏掉 `zero_grad`、健康网络，看诊断报告有什么不同。
5. **认识工具的局限**：有些 bug 用这些统计量是看不出来的（本文件的 BUG 3 就是例子）。

> 一句话：**神经网络的 bug 不会报错，所以你要自己造"报错"**——把内部状态量化出来，用阈值和对照实验把"感觉不对"变成"哪一层、哪个指标不对"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------------|
| `NetworkDebugger` | 类 | 给模型挂 hook，记录激活/梯度统计和 loss 历史，生成诊断报告 | 激活统计、梯度流 |
| `._register_hooks` | 方法 | 对 Linear/Conv2d/ReLU/LeakyReLU 挂 forward hook 和 full backward hook | PyTorch hooks |
| `._make_activation_hook` / `._make_gradient_hook` | 工厂方法 | 返回绑定了层名的 hook 闭包 | 闭包 |
| `.check_loss_health` | 方法 | 判断 NAN_OR_INF / NOT_DECREASING / OSCILLATING / HEALTHY | loss 曲线诊断 |
| `.check_activations` / `.check_gradients` | 方法 | 用阈值判断死亡、爆炸、塌缩、消失 | 健康指标表 |
| `.print_report` / `.remove_hooks` | 方法 | 打印报告；卸载 hook | — |
| `overfit_one_batch` | 函数 | 在 8 个样本上训练 200 步，loss < 0.1 判定 PASS | Overfit-one-batch |
| `find_learning_rate` | 函数 | 指数扫描学习率，发散即停，恢复权重，给出建议值 | LR finder |
| `_flat_to_multi_index` | 辅助函数 | 扁平下标 → 多维下标 | `unravel_index` |
| `gradient_check` | 函数 | float64 下用中心差分对比解析梯度 | 梯度检查 |
| `demo_broken_networks` | 函数 | 3 个坏网络 + 1 个好网络 + 3 个工具演示 | 对照实验 |

数据流：`demo_broken_networks` 生成随机数据 → 每个场景新建模型并用 `NetworkDebugger` 包装 → 训练时每次 forward/backward 自动触发 hook 更新统计量，循环中调用 `record_loss` → 训练结束 `print_report()` 汇总三类检查 → `remove_hooks()` 清理。之后依次调用三个独立工具函数。

---

## 3. 逐段精讲

### 3.1 注册 hook：不改模型代码就能"看进去"

```python
class NetworkDebugger:
    def __init__(self, model):
        self.model = model
        self.activation_stats = {}
        self.gradient_stats = {}
        self.loss_history = []
        self.hooks = []
        self._register_hooks()

    def _register_hooks(self):
        for name, module in self.model.named_modules():
            if isinstance(module, (nn.Linear, nn.Conv2d, nn.ReLU, nn.LeakyReLU)):
                hook = module.register_forward_hook(self._make_activation_hook(name))
                self.hooks.append(hook)
                hook = module.register_full_backward_hook(self._make_gradient_hook(name))
                self.hooks.append(hook)
```

- `named_modules()` 递归遍历所有子模块（包括根模块自己，名字是空字符串 `""`）。对 `nn.Sequential`，子模块名就是下标 `"0"`、`"1"`…根模块是 `Sequential`，不在过滤列表里，所以被跳过。
- **forward hook**：每次该模块 forward 结束后被调用，参数是 `(module, input, output)`。
- **full backward hook**：每次计算出该模块的梯度后被调用，参数是 `(module, grad_input, grad_output)`。
- `register_*_hook` 返回一个**句柄**（handle），保存在 `self.hooks` 里，之后 `handle.remove()` 就能卸载。不卸载的话，hook 会一直挂在模型上，拖慢之后的训练。
- 只挂在 Linear/Conv/ReLU 上：这些是"层输出"最有诊断价值的位置。注意 `nn.Tanh`、`nn.Sigmoid`、`nn.GELU` 不在列表里，用这些激活的网络需要自行补充。

### 3.2 为什么要用"工厂函数"生成 hook

```python
    def _make_activation_hook(self, name):
        def hook(module, input, output):
            with torch.no_grad():
                out = output.detach().float()
                self.activation_stats[name] = {
                    "mean": out.mean().item(),
                    "std": out.std().item(),
                    "fraction_zero": (out == 0).float().mean().item(),
                    "min": out.min().item(),
                    "max": out.max().item(),
                }
        return hook
```

- **闭包**：内层的 `hook` 记住了外层传入的 `name`。每次调用 `_make_activation_hook(name)` 都会生成一个绑定了不同层名的新函数。
- 为什么不在 `for` 循环里直接 `def hook(...)` 并引用循环变量 `name`？因为 Python 闭包是**晚绑定**的：所有 hook 都会在被调用时才去查 `name`，那时循环早已结束，所有 hook 看到的都是最后一个层名。用工厂函数是规避这个坑的标准做法。
- `output.detach().float()`：`detach` 断开计算图，统计操作不会进入 autograd；`.float()` 保证在 fp16/bf16 训练时统计量也用 float32 计算，避免溢出或精度不够。外层再包一个 `torch.no_grad()` 是双保险。
- 记录的 5 个指标对应讲义的"健康指标表"：均值、标准差判断饱和/爆炸；`fraction_zero` 判断死亡；`min/max` 看极值。
- ⚠️ 每个 `.item()` 都会把数值从 GPU 拷回 CPU 并**强制同步**，每一层、每一步做 5 次，在大模型上会明显拖慢训练。讲义 Ship It 建议"每 N 步记录一次"，正是这个原因。
- ⚠️ 字典每次被**覆盖**，只保留最后一次 forward 的统计量，没有历史曲线。想看趋势，需要改成追加到列表里。

### 3.3 梯度 hook：看的是"激活梯度"，不是参数梯度

```python
    def _make_gradient_hook(self, name):
        def hook(module, grad_input, grad_output):
            if grad_output[0] is not None:
                with torch.no_grad():
                    grad = grad_output[0].detach().float()
                    self.gradient_stats[name] = {
                        "mean": grad.mean().item(),
                        "std": grad.std().item(),
                        "abs_mean": grad.abs().mean().item(),
                        "max": grad.abs().max().item(),
                    }
        return hook
```

- `grad_output` 是一个元组，`grad_output[0]` 是 loss 对该模块**输出**的梯度 `∂L/∂output`。它衡量"误差信号传到这一层时还有多强"，是观察梯度流的直接指标。
- ⚠️ **它不是参数梯度 `param.grad`**。两者的关键区别：激活梯度每次 backward 都重新计算，不会累加；参数梯度会累加（直到 `zero_grad`）。所以这个调试器**看不到"漏掉 zero_grad"这类 bug**（见 3.11 的 BUG 3）。
- `abs_mean`（绝对值的均值）比 `mean` 更适合衡量梯度大小：梯度有正有负，直接求均值会互相抵消。
- **顺序的隐含假设**：backward hook 按**反向传播的顺序**触发，即从输出层到输入层。所以 `gradient_stats` 字典的插入顺序是 `"4" → "3" → … → "0"`，与 `activation_stats` 的顺序正好相反。`check_gradients` 中的"first"其实是**最靠近输出**的层、"last"是**最靠近输入**的层——命名有些误导，但逻辑是对的。
- 如果第一层的输入 `x` 不需要梯度，PyTorch 仍会调用这个 hook，只是 `grad_input` 为 `None`；代码只用 `grad_output`，所以不受影响。

### 3.4 `check_loss_health`：把 loss 曲线变成标签

```python
    def check_loss_health(self):
        if len(self.loss_history) < 2:
            return "NOT_ENOUGH_DATA"
        recent = self.loss_history[-10:]
        if any(math.isnan(v) or math.isinf(v) for v in recent):
            return "NAN_OR_INF"
        if len(self.loss_history) >= 20:
            first_half = sum(self.loss_history[:10]) / 10
            second_half = sum(self.loss_history[-10:]) / 10
            if second_half >= first_half * 0.99:
                return "NOT_DECREASING"
        if len(recent) >= 5:
            diffs = [recent[i + 1] - recent[i] for i in range(len(recent) - 1)]
            if max(diffs) - min(diffs) > 2 * abs(sum(diffs) / len(diffs) + 1e-10):
                return "OSCILLATING"
        return "HEALTHY"
```

三条规则按优先级依次判断：

| 规则 | 判断方法 | 含义 |
|------|---------|------|
| `NAN_OR_INF` | 最近 10 个 loss 中有 NaN/Inf | 训练已经"死了" |
| `NOT_DECREASING` | 至少 20 个点时，最后 10 个的平均 ≥ 最前 10 个平均的 99% | 整体几乎没有下降 |
| `OSCILLATING` | 最近 10 个点的相邻差值，其"极差"大于"平均差值"绝对值的 2 倍 | 每步变化忽大忽小，不是平稳下降 |

- 前两条很稳健。第三条是一个**启发式**规则，有明显的局限：
  - ⚠️ 当训练**已经收敛**时，相邻差值都接近 0、平均差值也接近 0，任何一点微小的噪声都会让极差超过 `2 × |平均|`，于是一个健康收敛的模型也会被判为 `OSCILLATING`；
  - 下降速度逐渐变慢（曲线前陡后缓）时，同样可能被误判。
- `+ 1e-10` 是代码相对讲义版本的修补，避免平均差值恰好为 0 时右侧为 0。
- `math.isnan(v) or math.isinf(v)` 也可以写成 `not math.isfinite(v)`。

### 3.5 `check_activations` 与 `check_gradients`：阈值规则

```python
    def check_activations(self):
        issues = []
        for name, stats in self.activation_stats.items():
            if stats["fraction_zero"] > 0.5:
                issues.append(f"DEAD_NEURONS: {name} has {stats['fraction_zero']:.0%} zero activations")
            if abs(stats["mean"]) > 10:
                issues.append(f"EXPLODING_ACTIVATIONS: {name} mean={stats['mean']:.2f}")
            if stats["std"] < 1e-6:
                issues.append(f"COLLAPSED_ACTIVATIONS: {name} std={stats['std']:.2e}")
        return issues if issues else ["HEALTHY"]
```

| 标签 | 阈值 | 典型原因 |
|------|------|---------|
| `DEAD_NEURONS` | 零比例 > 50% | ReLU 输入大多为负：初始化/偏置不当、学习率过大 |
| `EXPLODING_ACTIVATIONS` | \|均值\| > 10 | 权重过大、缺少归一化 |
| `COLLAPSED_ACTIVATIONS` | 标准差 < 1e-6 | 所有样本输出相同：神经元全死、对称性没打破 |
| `VANISHING_GRADIENT` | 梯度绝对值均值 < 1e-7 | 前面某处梯度被截断（死 ReLU、饱和激活） |
| `EXPLODING_GRADIENT` | 梯度绝对值均值 > 100 | 学习率过大、深层网络无归一化 |
| `GRADIENT_RATIO` | 输出侧/输入侧梯度幅度 > 100 | 梯度在传向输入的过程中大幅衰减 |

- ⚠️ **`DEAD_NEURONS` 的指标有概念偏差**：ReLU 对大约一半的输入输出 0 是正常的稀疏性，而"死亡神经元"指的是对**所有**输入都输出 0 的神经元。按元素统计零比例会把两者混在一起：健康网络的 ReLU 层零比例经常在 50% 上下波动，很容易被误报。更准确的写法是按神经元统计：`(out == 0).all(dim=0).float().mean()`（对 batch 维取"全为 0"）。
- 对 Linear 层，零比例几乎总是 0，所以这条规则实际上只对 ReLU 层起作用。
- 所有阈值（0.5、10、1e-6、1e-7、100）都是经验值，与模型规模、数据尺度有关，生产中应该根据自己模型正常时的统计量来设定基线。
- `return issues if issues else ["HEALTHY"]`：空列表在布尔上下文中为 False，这是 Python 中判断"列表是否为空"的惯用写法。

### 3.6 `overfit_one_batch`：最重要的一个测试

```python
def overfit_one_batch(model, x_batch, y_batch, criterion, lr=0.01, steps=200):
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()
    # ...
    for step in range(steps):
        optimizer.zero_grad()
        output = model(x_batch)
        loss = criterion(output, y_batch)
        loss.backward()
        optimizer.step()

        if step % 50 == 0 or step == steps - 1:
            with torch.no_grad():
                if output.shape[-1] == 1:
                    preds = (output > 0).float().squeeze()
                else:
                    preds = output.argmax(dim=1)
                targets = y_batch if y_batch.dim() == 1 else y_batch.squeeze()
                acc = (preds == targets).float().mean().item()
            # 打印 step、loss、accuracy

    final_loss = loss.item()
    if final_loss > 0.1:
        # FAIL
        return False
    return True
```

- 思路：在一个很小的 batch 上反复训练，正常的模型和训练循环**一定**能把 loss 压到接近 0。做不到就说明前向、损失、反向、优化器、数据对齐之中至少有一处坏了。
- 用 Adam、lr=0.01：比常规的 1e-3 大，目的是"尽快记住"，不需要考虑泛化。
- 兼容两种输出：输出最后一维为 1 时视为二分类单 logit，用 `> 0` 判定（对应 sigmoid 输出 > 0.5）；否则用 `argmax` 取类别。
- 准确率用的是 `optimizer.step()` **之前**的 `output`，所以是"这一步更新前"的准确率；`final_loss` 同理是最后一步更新前的 loss。
- 阈值 0.1 是经验值。对一个 8 样本的二分类问题，正常情况下 200 步后 loss 会远小于这个值。
- ⚠️ 这个测试**不检查**泛化能力，也抓不到所有 bug。比如漏掉 `zero_grad` 反而可能让它收敛得更快。

### 3.7 `find_learning_rate`：指数扫描 + 提前停止 + 恢复权重

```python
    original_state = copy.deepcopy(model.state_dict())
    optimizer = torch.optim.SGD(model.parameters(), lr=start_lr)
    lr_mult = (end_lr / start_lr) ** (1 / steps)
    # ...
    for step in range(steps):
        optimizer.zero_grad()
        output = model(x_data)
        loss = criterion(output, y_data)

        if math.isnan(loss.item()) or loss.item() > best_loss * 10:
            break

        best_loss = min(best_loss, loss.item())
        results.append((current_lr, loss.item()))

        loss.backward()
        optimizer.step()

        current_lr *= lr_mult
        for param_group in optimizer.param_groups:
            param_group["lr"] = current_lr

    model.load_state_dict(original_state)
    # ...
    min_loss_idx = min(range(len(results)), key=lambda i: results[i][1])
    suggested_lr = results[max(0, min_loss_idx - 10)][0]
```

- **指数增长**：每步乘以 `lr_mult = (10/1e-7)^(1/100) ≈ 1.2023`，在对数坐标上均匀覆盖 8 个数量级。
- ⚠️ 100 步只做了 99 次乘法，所以最后一步的学习率约 **8.32** 而不是 `end_lr=10`；若要正好到达终点，指数应为 `1/(steps-1)`。
- **提前停止**：loss 为 NaN 或超过历史最低值的 10 倍时停止——再往后的学习率已经没有参考价值。
- **修改学习率**：通过 `optimizer.param_groups` 逐组设置，这也是所有 `lr_scheduler` 的底层机制。
- **恢复权重**：扫描过程会用很大的学习率训练模型，必须恢复。`deepcopy` 是必需的，因为 `state_dict()` 中的张量与模型参数**共享内存**，浅拷贝会随训练一起改变。
- **建议值**：loss 最小处往前退 10 步，即学习率除以 `1.2023¹⁰ ≈ 6.3`。⚠️ 这和讲义的文字描述不完全一致——讲义正文说"比 loss 下降最快处小约 10 倍"，Key Terms 又说"loss 发散之前"。三种都是常见经验，但标准不同。
- ⚠️ 每一步都在**同一批数据**上训练，后面的 loss 小一部分是因为"训练了更多步"，会让最小点偏向大学习率。实用的 LR finder 每步用新的 batch，并对 loss 做指数平滑。
- `min(range(len(results)), key=lambda i: results[i][1])`：用 `key` 参数找"loss 最小的下标"，等价于 argmin。

### 3.8 `gradient_check`：float64 下的中心差分

```python
def gradient_check(model, x, y, criterion, eps=1e-4):
    model.train()
    x_double = x.double()
    y_double = y.double()
    model_double = model.double()
    # ...
    for name, param in model_double.named_parameters():
        # ...
        model_double.zero_grad()
        output = model_double(x_double)
        loss = criterion(output, y_double)
        loss.backward()
        analytical_grad = param.grad.clone()

        num_checks = min(5, param.numel())
        for i in range(num_checks):
            idx = _flat_to_multi_index(i, param.shape)
            original = param.data[idx].item()

            param.data[idx] = original + eps
            with torch.no_grad():
                loss_plus = criterion(model_double(x_double), y_double).item()

            param.data[idx] = original - eps
            with torch.no_grad():
                loss_minus = criterion(model_double(x_double), y_double).item()

            param.data[idx] = original

            numerical = (loss_plus - loss_minus) / (2 * eps)
            analytical = analytical_grad[idx].item()

            denom = max(abs(numerical), abs(analytical), 1e-8)
            rel_diff = abs(numerical - analytical) / denom
            # ...
    model.float()
```

- **为什么用 float64**：中心差分要计算两个非常接近的 loss 之差，float32 只有约 7 位有效数字，差值会被舍入误差淹没。`model.double()` 是**原地**把所有参数转成 float64，并返回模型本身（所以 `model_double` 和 `model` 是同一个对象），结束时 `model.float()` 再转回来。
- **中心差分**：`(L(w+ε) - L(w-ε)) / 2ε`，截断误差 `O(ε²)`，比单侧差分准一个数量级。`eps=1e-4` 在 float64 下是截断误差和舍入误差之间的合理折中。
- **相对误差**：`|n - a| / max(|n|, |a|, 1e-8)`，消除不同参数梯度量级的差异；`1e-8` 防止两者都接近 0 时除以 0。判定标准与讲义一致：`< 1e-5` OK、`< 1e-3` WARN、否则 FAIL。
- `param.data[idx] = ...`：通过 `.data` 绕过 autograd 直接修改参数值，并在算完后**恢复原值**。
- `analytical_grad = param.grad.clone()`：`clone` 保存一份副本，避免后续操作影响它。
- ⚠️ 只检查每个参数**前 5 个**元素，不是随机抽样。对大矩阵覆盖面很小，但作为演示足够。
- ⚠️ `y.double()` 只适用于回归类目标。分类任务的 `CrossEntropyLoss` 需要 `int64` 标签，转成 double 会报错。讲义 Step 5 的版本正是用 `CrossEntropyLoss` + 类别标签调用它，直接运行会出错；代码版的演示改成了 Tanh + MSE。
- ⚠️ 开头调用的是 `model.train()`。如果模型含 Dropout，每次 forward 的随机掩码不同，数值梯度会完全不可信。做梯度检查时应关掉随机性（例如 `model.eval()`，或确保没有 Dropout）。

```python
def _flat_to_multi_index(flat_idx, shape):
    multi_idx = []
    remaining = flat_idx
    for dim in reversed(shape):
        multi_idx.insert(0, remaining % dim)
        remaining //= dim
    return tuple(multi_idx)
```

- 把行优先的扁平下标转成多维下标：从最后一维开始，取余得到该维下标，整除后继续处理前一维。例：`(7, (4, 3)) → (2, 1)`。等价于 `np.unravel_index` / `torch.unravel_index`。
- 返回 `tuple` 是因为 PyTorch 的多维索引 `param.data[(2, 1)]` 需要元组。

### 3.9 `demo_broken_networks`：数据与四个场景

```python
    torch.manual_seed(42)
    x = torch.randn(64, 10)
    y = (x[:, 0] > 0).long()
    criterion = nn.CrossEntropyLoss()
```

- 数据：64 个 10 维随机样本，标签只取决于**第一维的正负**——一个线性可分的简单问题，正常网络应该很快学会。简单的数据让"学不会"只可能是 bug 造成的。
- `torch.manual_seed(42)` 固定随机种子，保证每次运行的数据和初始化一致，诊断结果可复现。

四个训练场景对比：

| 场景 | 模型 | 优化器 | 刻意制造的问题 | 设计意图 |
|------|------|--------|---------------|---------|
| BUG 1 | 10→32→2 | SGD lr=10，20 步 | 学习率高出正常值约 100–1000 倍 | 看 loss 剧烈波动/飙升、ReLU 大量死亡 |
| BUG 2 | 10→32→32→2 | Adam lr=1e-3，50 步 | 所有权重填 −1、偏置填 −5 | 看死 ReLU、塌缩、梯度消失 |
| BUG 3 | 10→32→2 | SGD lr=0.01，50 步 | 循环中没有 `zero_grad()` | 看梯度累加 |
| HEALTHY | 10→32→2 | Adam lr=1e-3，50 步 | 无 | 作为对照基线 |

**BUG 2 的机制**（可以完全推算出来）：
- 第一层每个神经元的输出都是 `-Σxᵢ - 5`，32 个神经元完全相同；只有 `Σxᵢ < -5`（约 5.7% 的样本）时才为正，所以第一个 ReLU 约 94% 输出为 0。
- 第二层输出 `-(32 个非负数之和) - 5` 恒为负，第二个 ReLU **100%** 输出为 0。
- 最后一层输出恒等于偏置 `[-5, -5]`，loss = ln 2 ≈ 0.6931；由于前面的梯度全被 ReLU 截断，只有最后一层的偏置能更新，loss 几乎不动。

**BUG 3 的机制**：漏掉 `zero_grad` 后，第 t 步用的是前 t 次梯度之和，相当于动量系数为 1 的动量法。

之后三个工具演示：
- overfit-one-batch：用前 8 个样本、默认 Adam lr=0.01 训练 200 步；
- LR finder：用全部 64 个样本扫描；
- 梯度检查：换成 `torch.manual_seed(123)` 生成的 4×3 输入、Tanh 激活、MSE 损失——光滑函数让有限差分结果干净，不会被 ReLU 的拐点干扰。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 hook 而不是改模型代码 | 对任意模型即插即用，诊断与业务代码解耦 | 记得 `remove_hooks()`；hook 中的 `.item()` 会强制同步，生产中每 N 步采样一次 |
| 梯度 hook 统计激活梯度 `grad_output` | 直接反映误差信号在每层的强度（梯度流） | 看不到参数梯度的累加；应同时记录 `param.grad` 的范数 |
| 统计量只保留最新一次 | 实现简单 | 没有趋势；生产中写入 W&B / TensorBoard 形成曲线 |
| 固定阈值规则 | 简单直观，与讲义表格一一对应 | 阈值依赖模型和数据尺度；更好的做法是与健康基线比较 |
| `DEAD_NEURONS` 按元素零比例判断 | 计算简单 | 与"死亡神经元"的定义不符，易误报；应按神经元统计"整批全 0" |
| `OSCILLATING` 用差值极差判断 | 不需要额外超参数 | 已收敛的曲线容易误报 |
| LR finder 在同一批数据上扫描 | 演示简单、可复现 | 最小点偏向大学习率；实际应每步换 batch 并平滑 loss |
| 梯度检查用 float64、只查前 5 个元素 | 数值可靠、速度快 | 覆盖面小；生产中可用 `torch.autograd.gradcheck` |
| 梯度检查演示用 Tanh + MSE | 光滑、无拐点、target 可直接转 double | 函数不支持分类标签；讲义版用 CrossEntropy 的调用会报错 |
| 刻意用简单的线性可分数据 | "学不会"只能归因于 bug | 无法演示过拟合、数据泄漏等需要真实数据的问题 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类与 `__init__` | `class NetworkDebugger: def __init__(self, model)` | 构造时就完成 hook 注册 |
| 以下划线开头的方法名 | `_register_hooks`、`_make_activation_hook`、`_flat_to_multi_index` | 约定俗成表示"内部使用"，外部不应直接调用 |
| `isinstance` 配元组 | `isinstance(module, (nn.Linear, nn.Conv2d, nn.ReLU, nn.LeakyReLU))` | 属于其中任意一种类型就返回 True |
| 嵌套函数与闭包 | `_make_activation_hook` 里的 `def hook(...)` 记住了 `name` | 工厂函数为每层生成独立的 hook，避免循环变量晚绑定 |
| 函数作为返回值 | `return hook` | 把函数当作对象传给 `register_forward_hook` |
| 字典字面量 | `{"mean": ..., "std": ..., ...}` | 一次记录多个统计量 |
| `dict.items()` | `for name, stats in self.activation_stats.items()` | 同时遍历键和值；字典保持插入顺序（Python 3.7+） |
| 列表切片 | `self.loss_history[-10:]`、`[:10]`、`[-5:]` | 负数下标从末尾数；取最近/最早的若干项 |
| 列表推导 | `[recent[i + 1] - recent[i] for i in range(len(recent) - 1)]` | 一行算出相邻差值 |
| `any()` + 生成器表达式 | `any(math.isnan(v) or math.isinf(v) for v in recent)` | 只要有一个为真就返回 True，并且会短路 |
| 条件表达式 | `issues if issues else ["HEALTHY"]`；`y_batch if y_batch.dim() == 1 else y_batch.squeeze()` | 空列表为假，非空为真 |
| `lambda` 作为 `key` | `min(range(len(results)), key=lambda i: results[i][1])` | 按自定义规则取最小值，相当于 argmin |
| `float("inf")` | `best_loss = float("inf")` | 正无穷，作为"历史最小值"的初始值 |
| `math.isnan` / `math.isinf` | `check_loss_health`、`find_learning_rate` | 判断浮点数是否为 NaN / 无穷大 |
| `copy.deepcopy` | `copy.deepcopy(model.state_dict())` | 递归复制，得到与原对象完全独立的副本 |
| `reversed` / `list.insert(0, x)` | `_flat_to_multi_index` | 逆序遍历；在列表头部插入 |
| `%` 与 `//=` | `remaining % dim`、`remaining //= dim` | 取余；整除并赋值 |
| 元组 | `return tuple(multi_idx)`；`results.append((current_lr, loss.item()))` | 不可变序列，可作多维下标，也可打包两个值 |
| `max` 多参数 | `max(abs(numerical), abs(analytical), 1e-8)` | 取多个数中的最大值，这里用来给分母设下限 |
| `list.clear()` | `self.hooks.clear()` | 原地清空列表 |
| 默认参数 / 关键字参数 | `def overfit_one_batch(..., lr=0.01, steps=200)` | 调用时可省略或按名字覆盖 |
| `with torch.no_grad()` | hook 内部、梯度检查中 | 上下文管理器：块内不构建计算图 |
| f-string 格式符 | `:.0%`、`:.1%`、`:.2e`、`:.0e`、`:.4f`、`:3d` | 百分比（0/1 位小数）、科学计数法、定点小数、宽度 3 的整数 |
| f-string 嵌套 | `f"  Last 5 losses: {[f'{v:.4f}' for v in self.loss_history[-5:]]}"` | 花括号内又写了一个带 f-string 的列表推导，内外引号要不同 |
| 相邻字符串自动拼接 | `f"\n  FAIL: ... " f"Model or training loop is broken."` | 括号内相邻的字符串字面量会自动连接 |

---

## 6. 运行结果解读

> **未实际运行**（原因：当前环境未安装 `torch`）。下面分两部分说明：可以从代码精确推出的输出，以及用 NumPy 按相同结构、相同超参数复刻后得到的**定性**预期（NumPy 的随机初始化与 PyTorch 不同，具体数值不会一致）。

**可以精确推出的部分**：

```text
OVERFIT ONE BATCH TEST
Batch size: 8, Steps: 200
  Step   0 | ...
  Step  50 | ...
  Step 100 | ...
  Step 150 | ...
  Step 199 | ...               ← 第 0/50/100/150/199 步各打印一行

LEARNING RATE FINDER
  Swept 100 steps from 1e-07 to 8e+00     ← 若未提前停止：最后的 lr 约 8.32，不是 10

GRADIENT CHECK (smooth model + MSE loss for clean finite differences)
  0.weight: max_rel_diff=... [OK]
  0.bias: max_rel_diff=... [OK]
  2.weight: max_rel_diff=... [OK]
  2.bias: max_rel_diff=... [OK]

  Checked 14 parameters                   ← 5 + 4 + 4 + 1
  PASS: Gradients match (rel_diff < 1e-5) ← float64 + 光滑函数，预期通过
```

**各场景的预期诊断**：

| 场景 | Loss health | 激活诊断 | 梯度诊断 | 解读 |
|------|-------------|---------|---------|------|
| BUG 1（lr=10） | 多半是 `NOT_DECREASING` 或 `OSCILLATING`；20 步内不一定出现 NaN | 第一个 ReLU（`"1"`）零比例很高（复刻中 83%–97%），报 `DEAD_NEURONS` | 取决于具体数值 | 巨大的更新把大部分 ReLU 推进了负区；loss 可能飙到成千上万，也可能卡在一个值不动。两种都是"学习率过大"的典型症状 |
| BUG 2（坏初始化） | `NOT_DECREASING`，loss 始终约 0.6931 | `"1"` 约 94% 为 0、`"3"` 100% 为 0（同时 `COLLAPSED_ACTIVATIONS`） | `"3"`、`"2"`、`"1"`、`"0"` 报 `VANISHING_GRADIENT` | 完全符合 3.9 的推算；0.6931 = ln 2 正是讲义诊断表中"loss 卡在 −log(1/类别数)" |
| BUG 3（漏 zero_grad） | 很可能是 `HEALTHY` | 很可能无异常 | 很可能无异常 | 这是本文件最值得深思的结果：梯度 hook 看的是不会累加的激活梯度；而在 50 步的短实验里，累加的梯度相当于强动量，loss 反而下降得**更快**（复刻中 50 步后 loss 降到 0.05–0.19，健康的 Adam 版本约 0.5）。调试器"看不见"这个 bug |
| HEALTHY | `HEALTHY` | 第一个 ReLU 零比例约 50%（复刻中 49%–52%），**有可能被误报**为 `DEAD_NEURONS` | 正常 | 说明按元素零比例判断死神经元的指标不可靠 |

- overfit-one-batch：复刻中 50 步后 loss 已降到 1e-3 量级，准确率 100%，最终远小于 0.1，预期打印 `PASS`。
- LR finder：这个问题很简单，复刻中 loss 一直降到扫描末尾附近才最小（lr ≈ 7–8），建议值约 1.1–1.3。这个建议值对 SGD 来说偏大，正是"在同一批数据上扫描会让最小点偏向大学习率"的体现。

---

## 7. 动手改一改

1. **修正死神经元指标**：在 activation hook 中增加 `"dead_fraction": (out == 0).all(dim=0).float().mean().item()`（只对 2D 输出），并让 `check_activations` 改用它判断。对比 HEALTHY 场景下两个指标的差别。
2. **让调试器发现 BUG 3**：在 `NetworkDebugger` 中增加 `record_param_grads()`，在每次 `loss.backward()` 后记录 `{name: p.grad.norm().item()}`；如果梯度范数随步数近似线性增长就报告 `GRADIENT_ACCUMULATING`。再把 BUG 3 的训练延长到 500 步，观察 loss 何时开始振荡。
3. **梯度爆炸检测（讲义练习 1）**：搭一个 20 层、无归一化的 MLP，用较大的初始化，让调试器检测梯度超过阈值时自动建议一个 `clip_grad_norm_` 的值（例如取最近若干步梯度范数的中位数）。
4. **修正 LR finder**：改成每一步换一个随机 batch，对 loss 做指数滑动平均（如 β=0.98），并把 `lr_mult` 的指数改为 `1/(steps-1)`；输出 CSV 供画图（讲义练习 3）。
5. **用梯度检查找 bug（讲义练习 5）**：把第 10 节 `Linear.backward` 中的 `self.weights[i][j]` 换成 `self.weights[j][i]`（方阵时不会越界），用纯 Python 版本的中心差分找出是哪个参数的梯度错了。
6. **对比内置工具**：用 `torch.autograd.gradcheck` 检查同一个 Tanh 模型，再在 BUG 1 中开启 `torch.autograd.detect_anomaly()`，看看它在什么情况下会报错。

---

## 8. 常见坑

- **hook 挂上不卸**：每次实验都新建 debugger 却不调用 `remove_hooks()`，hook 会越积越多，既慢又会让统计量互相覆盖。
- **在循环里直接定义 hook 引用循环变量**：闭包晚绑定，所有 hook 都会记成最后一个层名。用工厂函数或默认参数 `def hook(m, i, o, name=name)` 绑定。
- **把激活梯度当成参数梯度**：`grad_output` 不会累加，`param.grad` 会；监控"梯度累加"类问题必须看后者。
- **梯度检查用 float32 或 ε 太小**：舍入误差和相消误差会让结果毫无意义；用 float64，ε 取 `1e-4`～`1e-6`。
- **梯度检查时模型有 Dropout 或用了 ReLU 拐点附近的值**：随机性或不可导点会造成假阳性的 MISMATCH。
- **LR finder 结束后忘记恢复权重**：后续训练从一个被大学习率"破坏"过的模型开始；保存时还必须 `deepcopy`。
- **把一次诊断报告当结论**：本文件的阈值是经验值，同一份代码在健康网络上也可能报出 `DEAD_NEURONS` 或 `OSCILLATING`；要和健康基线对比着看。
