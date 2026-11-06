# 测验 · 调试神经网络（Debugging Neural Networks）

> **阶段 03 · 深度学习核心 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/debug_neural_nets.py](../code/debug_neural_nets.py) ｜ 代码讲解：[code/debug_neural_nets.讲解.md](../code/debug_neural_nets.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 静默 bug（silent bug） | 神经网络出错时通常不崩溃、不报错，只是结果悄悄变差；一个漏掉的 `zero_grad()`、一个错位的维度就足够 |
| 2 | 系统化排查顺序 | 从简单开始、一次只加一个复杂度：先查学习率 → 再查梯度（全 0 / NaN）→ 再查数据管道 → 最后查架构 |
| 3 | loss 不下降 | 学习率过大（振荡/NaN）或过小（几乎不动）、dead ReLU、梯度消失（sigmoid/tanh 深层网络）、梯度爆炸 |
| 4 | loss 下降但模型差 | 过拟合（train/val 差距拉大）、数据泄漏（先打乱/标准化再划分、跨集合重复样本）、标签错误 |
| 5 | NaN / Inf | 几步后才 NaN 多半是学习率太高；一开始就 NaN 多半是 `log(0)`、除以 0、`exp` 溢出（用 eps 和 log-sum-exp 防御） |
| 6 | 梯度检查 | 中心差分 `(L(w+ε) - L(w-ε)) / 2ε` 与反向传播结果对比，相对误差 `< 1e-5` 正确、`> 1e-3` 几乎肯定有 bug；用 float64 计算 |
| 7 | 激活统计与梯度流 | 用 forward/backward hook 记录每层输出的均值、标准差、零比例，以及每层的梯度幅度；前层梯度比后层小 100 倍以上 → 梯度消失 |
| 8 | Overfit-one-batch | 拿 8–32 个样本反复训练 100+ 步，loss 应接近 0、准确率 100%；做不到就说明模型或训练循环有根本问题，不要开始完整训练 |
| 9 | LR finder | 学习率从 1e-7 指数增长到很大，记录 loss，在 loss 开始发散之前选一个较小的学习率 |
| 10 | loss 初值的含义 | 均匀预测时交叉熵 = `ln(类别数)`：2 类 0.693、10 类 2.303；loss 卡在这个值说明模型什么也没学到 |

### 核心技能（能动手做到）

- [ ] 用 `register_forward_hook` 和 `register_full_backward_hook` 写一个记录每层激活/梯度统计量的调试器，并能用 `hook.remove()` 干净地卸载
- [ ] 写出 overfit-one-batch 测试，能说出它能抓到哪些 bug、抓不到哪些 bug
- [ ] 用 float64 实现中心差分梯度检查，能解释为什么选 `eps=1e-4`、为什么用相对误差、为什么光滑的 Tanh + MSE 比 ReLU + 交叉熵更适合做检查
- [ ] 实现 LR finder：指数增长学习率、loss 发散时提前停止、结束后恢复原始权重
- [ ] 看到 loss 卡在 0.693（2 类）或 2.303（10 类）时，能立刻判断"模型在输出均匀分布"并给出下一步排查方向
- [ ] 故意制造"学习率过大、死 ReLU、漏 `zero_grad`"三种 bug，并能说清楚调试器对每一种能看到什么、看不到什么

---

## 二、基础自测（选择题）

**Q1.** 一个 10 分类模型用交叉熵训练，loss 从第 1 步到第 1000 步一直停在 2.30 附近。最可能的情况和第一步该做什么是：

- A. 学习率太高，应立刻把学习率降低 10 倍
- B. 模型在输出近似均匀分布（`ln 10 ≈ 2.303`），什么也没学到；先检查数据管道、标签与输入是否对齐，并跑 overfit-one-batch
- C. 模型过拟合，应加 Dropout
- D. 梯度爆炸，应加梯度裁剪

**Q2.** 关于数值梯度检查，下列说法**错误**的是：

- A. 用中心差分 `(L(w+ε) - L(w-ε)) / 2ε`，截断误差是 `O(ε²)`，比单侧差分的 `O(ε)` 更准
- B. 应该用 float64 计算，否则 `L(w+ε) - L(w-ε)` 会被 float32 的舍入误差淹没
- C. ε 越小越好，取 `1e-12` 能得到最精确的数值梯度
- D. 用相对误差而不是绝对误差，因为不同参数的梯度量级相差很大

**Q3.** overfit-one-batch 测试**不能**帮你发现下面哪一个问题？

- A. 损失函数写错
- B. 优化器没有连接到模型参数（例如传错了 `parameters()`）
- C. 模型在新数据上泛化差
- D. 数据和标签错位

**Q4.** 本节 `NetworkDebugger.check_activations()` 中，只要某个 ReLU 层输出里 0 的比例 `> 0.5` 就报告 `DEAD_NEURONS`。关于这个指标，最准确的说法是：

- A. 它准确等价于"超过一半的神经元已经死亡"
- B. 健康的 ReLU 层本来就会对大约一半的输入输出 0；"死亡神经元"是指对**所有**输入都输出 0 的神经元。这个指标把"稀疏"和"死亡"混在一起，健康网络也可能被误报
- C. 它只对 Linear 层有意义
- D. ReLU 输出为 0 的比例永远不会超过 0.5

**Q5.** 训练第 1 步 loss 就是 `nan`，和训练正常进行了 200 步后才突然变成 `nan`，最可能的原因分别是：

- A. 两者都是学习率太高
- B. 前者多为 `log(0)`、除以 0、或输入数据本身含 NaN/Inf；后者多为学习率过高或梯度爆炸导致权重逐渐发散
- C. 前者是过拟合，后者是欠拟合
- D. 前者是 batch 太大，后者是 batch 太小

**Q6.** 本节调试器用 `module.register_full_backward_hook(hook)` 记录梯度，hook 的签名是 `hook(module, grad_input, grad_output)`。代码中统计的 `grad_output[0]` 是：

- A. 该模块**参数**（weight、bias）的梯度
- B. loss 对该模块**输出**的梯度 `∂L/∂output`
- C. loss 对该模块**输入**的梯度 `∂L/∂input`
- D. loss 的数值

**Q7.** 下列做法中，哪一个**会造成数据泄漏**？

- A. 先划分 train/test，再用训练集的均值和标准差去标准化训练集和测试集
- B. 先用整个数据集的均值和标准差做标准化，再划分 train/test
- C. 训练时用数据增强，测试时不用
- D. 用验证集做早停

**Q8.** 模型训练正常，但每次评估测试集准确率都不一样（同一个模型、同一份测试数据），最先应该怀疑：

- A. 测试集太小
- B. 评估时没有调用 `model.eval()`，Dropout 仍在随机丢弃、BatchNorm 仍在用 batch 统计量
- C. 学习率太大
- D. 优化器选错了

---

## 三、动手 / 代码题

**Q9.** 分析代码中的 BUG 2（"Dead ReLUs from bad initialization"）：

```python
    model2 = nn.Sequential(
        nn.Linear(10, 32),
        nn.ReLU(),
        nn.Linear(32, 32),
        nn.ReLU(),
        nn.Linear(32, 2),
    )
    with torch.no_grad():
        for m in model2.modules():
            if isinstance(m, nn.Linear):
                m.weight.fill_(-1.0)
                m.bias.fill_(-5.0)
```

输入 `x = torch.randn(64, 10)`，标签 `y = (x[:, 0] > 0).long()`，优化器 `Adam(lr=1e-3)` 训练 50 步。

(a) 第 1 步的 loss 是多少？为什么能精确算出来？
(b) 第一个 ReLU（模块名 `"1"`）大约有多少比例的输出为 0？第二个 ReLU（`"3"`）呢？
(c) 为什么 Adam 也救不回来？哪些参数在 50 步里完全没有变化？
(d) 调试报告里 loss 健康状态最可能是什么？

**Q10.** 分析 BUG 3（"Missing zero_grad"）：

```python
    optimizer3 = torch.optim.SGD(model3.parameters(), lr=0.01)
    for step in range(50):
        out = model3(x)
        loss = criterion(out, y)
        debugger3.record_loss(loss.item())
        loss.backward()
        optimizer3.step()
```

(a) 漏掉 `zero_grad()` 后，第 t 步实际用于更新的"梯度"是什么？它在数学上相当于哪种优化器的极端情况？
(b) `NetworkDebugger` 的梯度统计能发现这个 bug 吗？为什么？在这个 50 步的短实验里，loss 曲线可能是什么样子？
(c) 写一个函数 `param_grad_norms(model)`，返回 `{参数名: 梯度 L2 范数}`，并说明在训练循环中怎样用它发现"梯度在累加"。

**Q11.** 阅读 `find_learning_rate` 的关键部分：

```python
def find_learning_rate(
    model, x_data, y_data, criterion, start_lr=1e-7, end_lr=10, steps=100
):
    original_state = copy.deepcopy(model.state_dict())
    optimizer = torch.optim.SGD(model.parameters(), lr=start_lr)
    lr_mult = (end_lr / start_lr) ** (1 / steps)
    # ...
    for step in range(steps):
        # ... forward, 发散检查, 记录 (current_lr, loss), backward, step
        current_lr *= lr_mult
        for param_group in optimizer.param_groups:
            param_group["lr"] = current_lr

    model.load_state_dict(original_state)
    # ...
    min_loss_idx = min(range(len(results)), key=lambda i: results[i][1])
    suggested_lr = results[max(0, min_loss_idx - 10)][0]
```

(a) `lr_mult` 约等于多少？如果 100 步都没有提前停止，记录到的最后一个学习率是多少？是 `end_lr=10` 吗？
(b) `suggested_lr` 比"loss 最小处的学习率"小多少倍？
(c) 为什么必须 `deepcopy` 保存并在最后 `load_state_dict` 恢复？
(d) 这个实现每一步都在**同一批数据**上训练。这会让"loss 最小点"偏向哪一端？

**Q12.** 关于 `gradient_check`：

```python
def _flat_to_multi_index(flat_idx, shape):
    multi_idx = []
    remaining = flat_idx
    for dim in reversed(shape):
        multi_idx.insert(0, remaining % dim)
        remaining //= dim
    return tuple(multi_idx)
```

(a) `_flat_to_multi_index(7, (4, 3))` 返回什么？它等价于 NumPy/PyTorch 里的哪个函数？
(b) 演示中 `model_grad = nn.Sequential(nn.Linear(3, 4), nn.Tanh(), nn.Linear(4, 1))`，每个参数最多检查 5 个元素。程序最后打印 `Checked N parameters`，N 是多少？
(c) 讲义版的演示是 `gradient_check(model_grad, x[:4], y[:4], criterion)`，其中 `criterion = nn.CrossEntropyLoss()`、`y` 是类别下标。代码版改成了 Tanh + MSE。讲义版直接运行会出什么问题？为什么光滑激活更适合做梯度检查？

---

## 四、面试高频题

**Q13.**（场景设计）你接手一个训练任务，跑了 10 个 epoch，loss 几乎没有下降。请描述你的排查流程。

**Q14.**（原理深挖）什么是梯度消失和梯度爆炸？产生的根本原因是什么？有哪些解决手段？训练中怎么监控？

**Q15.**（工程实践）大模型训练到第 3 万步时 loss 突然变成 NaN。你会怎么定位和处理？

**Q16.**（基础必考）如何从 train/val 的 loss 曲线判断过拟合、欠拟合和数据泄漏？分别怎么处理？

**Q17.**（追问型）为什么 overfit-one-batch 是"最重要的调试技巧"？测试通过能说明什么、不能说明什么？如果测试失败，你会按什么顺序排查？

---

## 五、参考答案与解析

### Q1 — 答案：B

模型对 10 个类都输出相同概率 0.1 时，交叉熵 = `-ln 0.1 = ln 10 ≈ 2.303`。讲义"Master Debugging Table"第一行：*Loss stuck at -log(1/num_classes) → Model predicting uniform distribution → Check data pipeline, verify labels match inputs*。常见原因：标签被打乱、输入全 0 或未归一化、梯度没有流到参数（被 detach 或 `.item()` 截断）、学习率过小。A 错：学习率太高通常表现为振荡或 NaN，而不是稳稳地停在 ln 10。

### Q2 — 答案：C

ε 太小时，`L(w+ε)` 与 `L(w-ε)` 几乎相等，相减会产生严重的**相消误差**（catastrophic cancellation），再除以很小的 `2ε` 会把舍入误差放大。float64 下 ε 一般取 `1e-4` 到 `1e-6`，本节代码用 `1e-4`。A、B、D 都正确：中心差分误差 `O(ε²)`；float32 只有约 7 位有效数字，不足以做检查（代码中 `model.double()` 就是为此）；相对误差 `|a-n| / max(|a|, |n|, 1e-8)` 消除了量级差异。

### Q3 — 答案：C

overfit-one-batch 只验证"模型**能不能**拟合数据"，即损失函数、反向传播、优化器连接、数据-标签对齐、模型容量是否基本正常（讲义列出的就是 A、B、D 和"架构太小"）。泛化能力要看验证集，单个 batch 拟合到 100% 恰恰是在"故意过拟合"，与泛化无关。

### Q4 — 答案：B

ReLU 的输入大致以 0 为中心时，约一半输出为 0 是**正常的稀疏性**。死亡神经元的定义（讲义 Key Terms）是"输入**永远**为负，于是输出恒为 0、梯度恒为 0"。按元素统计零比例会把两者混为一谈：健康网络的零比例常在 50% 上下波动，容易被误报；更准确的指标是"对整个 batch 都输出 0 的神经元比例"：`(out == 0).all(dim=0).float().mean()`。讲义正文"If >50% are dead"说的是神经元，代码实现的却是元素比例，两者不一致。

### Q5 — 答案：B

第 1 步就 NaN 说明问题在"静态"环节：数据本身有 NaN/Inf、`log(0)`、除以 0（例如自己实现的 BN 没加 eps）、`exp` 溢出（softmax 没减最大值）。正常训练一段后才 NaN，说明是"动态"累积出来的：学习率过高、梯度爆炸使权重越来越大，最终溢出（讲义：*Loss NaN after a few steps → Learning rate too high → Reduce LR by 10x*）。

### Q6 — 答案：B

`grad_output` 是 loss 对模块**输出**的梯度，`grad_input` 是对模块**输入**的梯度，二者都是**激活值的梯度**，不是参数梯度。参数梯度要看 `param.grad`。这个区别很关键：参数梯度会因为漏掉 `zero_grad` 而累加，激活梯度每次 backward 都重新计算、不会累加——这正是 Q10 的伏笔。

### Q7 — 答案：B

用全量数据的统计量做预处理，测试集的信息就"漏"进了训练过程。讲义原话：*Fix: split first, preprocess second, check for duplicates.* A 是正确做法；C、D 都是标准做法（早停用的是验证集，不是测试集）。

### Q8 — 答案：B

讲义"Common PyTorch Bugs"表：*Forgetting `model.eval()` at test time → Dropout and batch norm behave differently, test accuracy varies between runs*。修复：`model.eval()` + `torch.no_grad()`。

### Q9 — 参考答案

(a) **0.6931（= ln 2）**。权重全 −1、偏置全 −5 时，第二个 ReLU 的输出恒为 0（见 b），最后一层的输出就是偏置 `[-5, -5]`，两类概率都是 0.5，交叉熵 = ln 2，与样本无关。

(b) 第一层每个神经元的输出都是 `-Σxᵢ - 5`（32 个神经元**完全相同**——这也是一个"对称性没有被打破"的问题）。`Σxᵢ ~ N(0, 10)`，只有 `Σxᵢ < -5` 时才为正，概率约 `Φ(-5/√10) = Φ(-1.58) ≈ 5.7%`，所以 `"1"` 的零比例约 **94%**（64 个样本中约 60 个）。第二层输出 `= -Σ(32 个 ≥0 的值) - 5 < 0` 恒成立，所以 `"3"` 的零比例为 **100%**，标准差为 0，会同时触发 `DEAD_NEURONS` 和 `COLLAPSED_ACTIVATIONS`。

(c) 反向传播时，第二个 ReLU 的输入全为负，局部导数全为 0，于是前两层 Linear 的 weight、bias 梯度**精确为 0**。最后一层 weight 的梯度 `= gᵀ·h₂ = 0`（因为 h₂ 全 0）。Adam 的更新是 `lr · m̂ / (√v̂ + eps)`，梯度恒为 0 时 m、v 都是 0，更新量也是 0——自适应优化器不会凭空创造梯度。50 步里只有**最后一层的 bias** 在变，模型能学到的只是类别先验。另外，`"3"` 处的梯度 `∂L/∂h₂ = g·W₃` 也约为 0：最后一层权重全是 −1，而每个样本的 `g₀ + g₁ = (p₀ + p₁) - 1 = 0`，所以调试器会在 `"3"`、`"2"`、`"1"`、`"0"` 上报告 `VANISHING_GRADIENT`。

(d) 最可能是 **`NOT_DECREASING`**：loss 始终约 0.693，后 10 步平均 ≥ 前 10 步平均的 0.99 倍。（未实际运行 PyTorch，以上用 NumPy 按相同结构复刻推演：多个随机种子下 loss 都停在 0.6927–0.6931。）修复：用默认的 Kaiming 初始化、偏置初始化为 0（或很小的正数），或改用 LeakyReLU。

### Q10 — 参考答案

(a) 第 t 步的 `.grad` 是 `g₁ + g₂ + … + gₜ`，即**所有历史梯度之和**。这相当于动量系数 β = 1（永不衰减）的 heavy-ball 动量，等效步长随步数线性增长。

(b) **很可能发现不了**。`NetworkDebugger` 的 backward hook 统计的是 `grad_output`（激活值的梯度），它每次 backward 都重新计算，不会累加；被累加的是 `param.grad`，调试器没有监控它。更反直觉的是：在只有 50 步、lr=0.01 的短实验里，"梯度越积越大"像是带了一个很强的动量，loss 往往**比正确实现下降得更快**，健康检查可能直接报告 `HEALTHY`（NumPy 复刻推演中 5 个种子均如此：50 步后 loss 降到 0.05–0.19，而正确的 Adam 版本约 0.5）。问题会在更长的训练里暴露：等效步长持续增大，最终振荡或发散。这说明**有些 bug 只能靠代码审查或监控参数梯度来发现**。

(c)

```python
def param_grad_norms(model):
    return {
        name: p.grad.norm().item()
        for name, p in model.named_parameters()
        if p.grad is not None
    }
```

用法：在 `loss.backward()` 之后、`optimizer.step()` 之前调用并记录。正常训练中，参数梯度范数应在一个范围内波动、通常随 loss 下降而减小；漏掉 `zero_grad` 时，梯度范数会**随步数单调、近似线性地增长**。更直接的检查：在 `loss.backward()` **之前**断言 `all(p.grad is None or p.grad.abs().sum() == 0 for p in model.parameters())`。讲义的 W&B 示例中用 `clip_grad_norm_(model.parameters(), float("inf"))` 记录总梯度范数，也是同样的思路。

### Q11 — 参考答案

(a) `lr_mult = (10 / 1e-7)^(1/100) = 10^0.08 ≈ 1.2023`。第 i 步记录的学习率是 `1e-7 × 1.2023ⁱ`，最后一步 i = 99，约 **8.32**，而不是 10——因为 100 步只做了 99 次乘法。要让最后一步正好到 `end_lr`，指数应为 `1 / (steps - 1)`。打印的 "Swept ... to 8e+00" 正体现了这一点。

(b) 往前退 10 步，学习率除以 `1.2023¹⁰ = 10^0.8 ≈ 6.3` 倍。注意这与讲义的描述并不一致：讲义正文说"比 loss 下降**最快**处小约 10 倍"，Key Terms 又说"loss 发散**之前**的学习率"，代码实现的是"loss **最小**处往前退 10 步"。三种规则都是常见经验，但应当统一。

(c) LR finder 在扫描过程中真的在训练模型，后期学习率很大，权重会被破坏。保存初始权重并恢复，才能保证后续正式训练从原来的初始化开始。`deepcopy` 是必须的：`state_dict()` 返回的张量与模型参数**共享内存**，不深拷贝的话，"保存的状态"会随训练一起被修改。

(d) 偏向**大学习率**一端。因为每一步都在同一批数据上继续训练，后面的 loss 小，部分是因为"已经训练了更多步"，而不完全是因为学习率更合适。对于本节这种很容易的二分类问题，loss 可能一直降到扫描末尾才达到最小（NumPy 推演中最小点出现在 lr ≈ 7–8，建议值约 1.1–1.3）。实际使用时应该每一步换一个新的 batch，并对 loss 做平滑。

### Q12 — 参考答案

(a) 返回 `(2, 1)`。过程：从最后一维开始，`7 % 3 = 1`、`7 // 3 = 2`；`2 % 4 = 2`。它把行优先（C order）的扁平下标转换成多维下标，等价于 `np.unravel_index(7, (4, 3))`（PyTorch 中有 `torch.unravel_index`）。代码只检查**前** `min(5, numel)` 个元素，对 `(4, 3)` 的权重就是 `(0,0) (0,1) (0,2) (1,0) (1,1)`。

(b) 参数依次为 `0.weight [4,3]`（12 个元素，查 5 个）、`0.bias [4]`（查 4 个）、`2.weight [1,4]`（查 4 个）、`2.bias [1]`（查 1 个），共 **14** 个，打印 `Checked 14 parameters`。（Tanh 没有参数，所以没有 `1.*`。）

(c) 讲义版在 `gradient_check` 里执行 `y_double = y.double()`，把类别下标变成了浮点数。`CrossEntropyLoss` 只有在 target 与输入形状相同（`[4, 2]`）时才把浮点 target 当作"类别概率"；这里 target 是 `[4]`，会走"类别下标"的路径，而类别下标必须是 `int64`，于是抛出 RuntimeError（dtype 不匹配，期望 Long 却收到 Double）。代码版改用 MSE + 浮点 target，绕开了这个问题。至于光滑激活：ReLU 在 0 处不可导，如果某个预激活值离 0 小于 ε，`w±ε` 会让它跨过拐点，数值梯度与解析梯度就会不一致，造成**假阳性**的 MISMATCH。Tanh 处处光滑，差分结果干净，这正是代码注释 "smooth model + MSE loss for clean finite differences" 的含义。

### Q13 — 参考回答要点

按"由便宜到昂贵、由常见到少见"的顺序：
1. **看 loss 的数值**：是否等于 `ln(类别数)`（模型输出均匀分布）？是否为 NaN？是振荡还是平坦？
2. **检查数据**：随机打印几个样本和标签，确认对齐；检查输入是否归一化、有没有 NaN；检查标签分布。
3. **跑 overfit-one-batch**：8–32 个样本训练 100–200 步。如果失败，问题在模型/损失/优化器/训练循环本身，不用再看大数据集。
4. **检查学习率**：在跨 10 倍的 3 个学习率（如 1e-2、1e-3、1e-4）上各跑一小段，或用 LR finder。
5. **检查梯度**：每层参数梯度的范数是否为 0（dead ReLU、被 `detach`、`requires_grad=False`、优化器没拿到参数）、是否极小（梯度消失）、是否 NaN/Inf。
6. **检查激活**：每层输出的均值、标准差、零比例；是否饱和（sigmoid/tanh 输出接近 ±1）、塌缩（std≈0）、爆炸。
7. **检查代码细节**：`zero_grad` 的位置、`model.train()/eval()`、损失函数的输入（logits vs 概率）、标签 dtype、张量形状是否意外广播。
8. 以上都正常后，再考虑模型容量（欠拟合）和架构问题。
- **加分点**：强调"一次只改一个变量"，并且先在小规模、快反馈的实验上定位问题。

### Q14 — 参考回答要点

- **定义**：反向传播时梯度逐层相乘，若每层的雅可比"缩放因子"持续小于 1，梯度指数级衰减（消失），前几层几乎不更新；持续大于 1 则指数级增长（爆炸），导致权重更新过大、loss 变成 NaN。
- **根本原因**：①激活函数导数小（sigmoid 导数最大只有 0.25，tanh 在饱和区接近 0）；②权重初始化尺度不合适（方差过大或过小）；③网络很深或像 RNN 那样沿时间步重复乘同一个矩阵。
- **解决**：
  - 激活：ReLU/GELU 替代 sigmoid/tanh；
  - 初始化：Xavier（tanh）/ Kaiming（ReLU）；
  - 归一化：BatchNorm、LayerNorm；
  - 结构：残差连接（梯度有一条"直通"路径）、LSTM/GRU 的门控；
  - 爆炸专用：梯度裁剪 `clip_grad_norm_`、降低学习率、warmup。
- **监控**：每层参数梯度范数（或激活梯度幅度）的曲线；本节调试器检查"首层/末层梯度幅度比 > 100"；W&B/TensorBoard 记录梯度直方图。
- **常见误区**：以为用了 ReLU 就不会有问题——ReLU 有 dead neuron 问题，很深的纯 ReLU 网络没有归一化和残差同样难训练。

### Q15 — 参考回答要点

1. **先止损**：从最近的 checkpoint 恢复；记录出问题的 step、batch 内容、学习率。
2. **定位来源**：
   - 回放出问题的那个 batch：检查数据是否有 NaN/Inf、异常长的样本、全是 padding 的样本；
   - 开启 `torch.autograd.detect_anomaly()`（讲义 Use It 部分），找到第一个产生 NaN 的反向算子（很慢，只在复现时开）；
   - 用 forward hook 检查每层输出，定位第一个出现 Inf/NaN 的层（本节 `NetworkDebugger` 的思路）；
   - 查看 NaN 之前的梯度范数和 loss 曲线：是否有 loss spike、梯度范数在突然增大。
3. **常见原因与对策**：
   - 学习率过高 / warmup 不足 → 降低学习率、加长 warmup；
   - 梯度爆炸 → 梯度裁剪（如全局范数 1.0）；
   - fp16 溢出 → 换用 bf16，或检查 `GradScaler` 是否正常工作；
   - 数值不稳定的算子 → softmax 减最大值、log 加 eps、除法加 eps；
   - 坏数据 → 过滤。
4. **预防**：自动告警（讲义 Ship It：NaN loss、dead neurons > 80%、梯度爆炸），定期保存 checkpoint，跳过 loss 异常大的 batch。
- **加分点**：大模型训练中常见的 loss spike 往往与特定数据和优化器状态有关，常用做法是回滚到 spike 之前的 checkpoint 并跳过对应的数据段。

### Q16 — 参考回答要点

| 现象 | 判断 | 处理 |
|------|------|------|
| train loss 持续下降，val loss 先降后升，差距越来越大 | 过拟合 | 更多数据、数据增强、Dropout、weight decay、早停、减小模型 |
| train 和 val loss 都高且接近，准确率都低 | 欠拟合 | 更大的模型、更多特征、训练更久、降低正则化、检查学习率 |
| val/test 准确率高得可疑，甚至超过 train，或明显高于业界水平 | 数据泄漏 | 先划分再预处理、检查跨集合重复样本、检查特征里是否含有标签信息（如"未来"信息） |
| train ≈ val ≈ 随机水平 | 什么都没学到 | 跑 overfit-one-batch，查数据管道（Q1、Q13） |
| val loss 从一开始就不动，train loss 在降 | 训练/验证分布不一致或预处理不一致，或严重过拟合 | 对比两个集合的预处理流程和数据分布 |

- **加分点**：提到标签噪声（讲义引用 Northcutt et al. 2021：主流基准测试集中存在相当比例的错误标签），可以用 confident learning 找出可疑标签；也可以提到 Dropout 会让训练 loss 在 train 模式下统计时偏高，比较曲线时要注意。

### Q17 — 参考回答要点

- **为什么有效**：Zhang et al. (2017) 证明，足够大的神经网络甚至能记住**随机标签**。所以一个正常的模型 + 正常的训练循环，没有任何理由记不住 8 个样本。做不到就说明管道本身有问题。它只需几十秒，却能在花几个小时完整训练之前拦下大部分低级 bug。
- **通过说明**：前向、损失、反向、优化器连接、数据-标签对齐（至少在这个 batch 上）、模型容量下限都基本正常。
- **通过不说明**：模型能泛化；学习率对完整数据集合适；没有数据泄漏；数据增强、BatchNorm 在大 batch 上的行为正确；完整数据集上没有别的数据问题（例如只有部分 shard 标签错位）。另外，"漏掉 `zero_grad`"这类 bug 在这个测试里甚至可能让 loss 降得更快（见 Q10），所以测试通过也不能代替代码审查。
- **失败后的排查顺序**：①确认 loss 在动（如果完全不动：检查 `optimizer` 是否拿到了 `model.parameters()`、是否有 `requires_grad=False` 或 `.detach()`）；②确认数据和标签对齐、标签 dtype 和取值范围正确；③确认损失函数的输入（logits vs 概率）；④对自定义层做梯度检查；⑤换几个学习率；⑥暂时去掉 Dropout、数据增强和正则化（它们会妨碍"记住"）；⑦增大模型容量。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 03 Backpropagation 从头开始](../../03-backpropagation/docs/zh.md)：梯度检查验证的就是反向传播的正确性。
- [阶段 03 · 04 Activation Functions](../../04-activation-functions/docs/zh.md)：dead ReLU、sigmoid 饱和与梯度消失。
- [阶段 03 · 05 Loss Functions](../../05-loss-functions/docs/zh.md)：交叉熵、`ln(C)` 基线、log(0) 问题。
- [阶段 03 · 08 Weight 初始化和训练稳定性](../../08-weight-initialization/docs/zh.md)：BUG 2 的根源与 Kaiming 初始化。
- [阶段 03 · 09 Learning Rate Schedules](../../09-learning-rate-schedules/docs/zh.md)：学习率过大/过小、warmup。
- [阶段 03 · 11 PyTorch 简介](../../11-intro-to-pytorch/docs/zh.md)：hooks、`model.eval()`、`zero_grad` 等 API。

### 本节被哪些后续内容用到
- [阶段 03 · 10 构建您自己的迷你框架](../../10-mini-framework/docs/zh.md)：讲义练习 5 要用梯度检查定位那里故意引入的 backward bug。
- [阶段 00 · 12 调试与性能分析](../../../00-setup-and-tooling/12-debugging-and-profiling/docs/zh.md)：通用的调试与 profiling 工具。
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：NaN/Inf 的根源、log-sum-exp、相消误差。
- [阶段 02 · 10 偏差-方差](../../../02-ml-fundamentals/10-bias-variance/docs/zh.md)：过拟合与欠拟合的理论框架。
- [阶段 02 · 09 模型评估](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：正确划分数据、避免泄漏。
- [阶段 19 · 45 梯度裁剪与 AMP](../../../19-capstone-projects/45-gradient-clipping-amp/docs/zh.md)：梯度爆炸与 fp16 溢出的工程化处理。

### 延伸关键词
`silent bug` · `overfit one batch` · `gradient check / finite differences` · `forward hook / full backward hook` · `dead ReLU` · `vanishing / exploding gradients` · `clip_grad_norm_` · `LR range test` · `detect_anomaly` · `data leakage` · `confident learning` · `loss spike`
