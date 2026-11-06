# 测验 · 构建您自己的迷你框架（Build Your Own Mini Framework）

> **阶段 03 · 深度学习核心 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Module 抽象 | 每个层都实现同一套接口：`forward()` 算输出、`backward()` 回传梯度、`parameters()` 暴露可训练参数，外加 `train()/eval()` 切换模式 |
| 2 | Linear 层 | 前向 `y = Wx + b` 并**缓存输入**；反向用 `+=` 累加 `∂L/∂W = g·xᵀ`、`∂L/∂b = g`，并返回 `∂L/∂x = Wᵀg` 给上一层 |
| 3 | 激活模块的缓存 | ReLU 缓存 0/1 掩码，Sigmoid/Tanh 缓存**输出**（因为导数 `o(1-o)`、`1-o²` 只依赖输出） |
| 4 | Sequential = 组合模式 | 一串 Module 本身也是 Module：forward 从左到右，backward 用 `reversed()` 从右到左，parameters 把子模块的参数拼起来 |
| 5 | train / eval 模式 | Dropout 训练时随机置零并乘 `1/(1-p)`（inverted dropout），评估时原样通过；BatchNorm 训练用批统计量、评估用滑动平均 |
| 6 | 损失对象 | `__call__` 计算并缓存预测与目标，`backward()` 返回 `∂L/∂pred`；Sigmoid + BCE 串起来的梯度恰好是 `p - t` |
| 7 | 优化器只认扁平参数表 | 参数以 `(container, i, j, grad_container)` 四元组交给优化器，它完全不需要知道网络结构；SGD 一行更新，Adam 维护 m/v 并做偏差修正 |
| 8 | zero_grad 与 step 分离 | 因为梯度是**累加**的，必须在每次 backward 前清零；分离设计让"多次 backward 累积、一次 step"成为可能 |
| 9 | DataLoader | 每个 epoch 打乱下标、按 `batch_size` 切片、用生成器 `yield` 出批次；批数 = `ceil(N / batch_size)` |
| 10 | 与 PyTorch 一一对应 | `Sequential/Linear/ReLU/BCELoss/Adam/zero_grad/backward/step/train/eval` 全部同名；PyTorch 多的是 autograd、GPU 和多年优化 |

### 核心技能（能动手做到）

- [ ] 不看讲义，从零写出 `Module`、`Linear`、`ReLU`、`Sigmoid`，并用数值差分 `(L(w+ε) - L(w-ε)) / 2ε` 验证 `Linear.backward` 的权重梯度
- [ ] 写出 `Sequential` 的 `forward / backward / parameters / train / eval`，并解释为什么 `train()/eval()` 必须递归传给子模块
- [ ] 实现 inverted dropout，验证训练时保留元素被放大为 `1/(1-p)`、评估时输出与输入完全相同
- [ ] 手写 SGD 与带偏差修正的 Adam，能说清 `m_hat`、`v_hat` 各自修正了什么
- [ ] 把本代码"逐样本更新"的训练循环改成真正的 mini-batch 梯度累积（每批一次 `step`），并对比测试准确率
- [ ] 能算出 `2→16→16→8→1` 网络的参数量（465），并说出 `DataLoader` 在 400 个样本、`batch_size=16` 时产生多少批
- [ ] 能把本框架的每个组件逐一映射到 PyTorch 的 `nn.Module`、`nn.Sequential`、`torch.optim.Adam`、`DataLoader`

---

## 二、基础自测（选择题）

**Q1.** 本框架中 `Sequential` 也继承自 `Module`。这一设计（组合模式，composite pattern）最大的好处是：

- A. 让反向传播的计算量减半
- B. 容器和普通层接口一致，容器可以嵌套，外部代码统一调用 `forward/backward/parameters`
- C. 自动获得 autograd 能力，不必再手写 `backward`
- D. 让不同层之间可以共享同一份权重

**Q2.** `Dropout(p=0.3)` 处于训练模式时，**没有被置零**的元素会被乘以：

- A. 0.3
- B. 0.7
- C. `1/0.7 ≈ 1.4286`
- D. `1/0.3 ≈ 3.333`

**Q3.** 训练完一个带 Dropout 的模型后，忘记调用 `model.eval()` 就直接在测试集上评估，最可能的结果是：

- A. 完全没有影响，Dropout 只在 backward 时生效
- B. 测试时仍会随机丢弃神经元，同一输入多次预测结果不同，准确率通常偏低且不稳定
- C. 程序抛出异常
- D. 所有参数的梯度被清零

**Q4.** 结合本代码中 `Linear.backward` 用 `+=` 累加梯度的事实，下面哪一种单步训练顺序**会让模型学不到东西**？

- A. `zero_grad → forward → loss → backward → step`
- B. `forward → loss → zero_grad → backward → step`
- C. `forward → loss → backward → zero_grad → step`
- D. `forward → loss → backward → step → zero_grad`

**Q5.** Adam 中 `m_hat = m / (1 - beta1 ** t)` 这一行的作用是：

- A. 随训练步数衰减学习率
- B. 修正 m 从 0 初始化导致前几步估计值偏小（偏向 0）的偏差
- C. 防止分母为 0
- D. 对梯度做裁剪

**Q6.** 本框架把参数交给优化器的形式是：

- A. 每层一个权重矩阵对象，优化器按层遍历
- B. 一个扁平列表，每项是 `(container, i, j, grad_container)` 四元组，`j is None` 表示一维参数（偏置、gamma、beta）
- C. 一个"参数名 → 数值"的字典
- D. 只把最后一层的参数交给优化器，其余层靠反向传播自动更新

**Q7.** `train_framework()` 里 `DataLoader(train_data, batch_size=16)`，但请仔细看内层循环。实际上**每次参数更新**用了几个样本的梯度？

- A. 16
- B. 1
- C. 400
- D. 25

**Q8.** 网络最后是 `Sigmoid()`，损失是 `BCELoss()`。设 Sigmoid 的输入为 z、输出为 p、标签为 t，忽略 clamp，`BCELoss.backward()` 的结果再经过 `Sigmoid.backward()` 后得到的 `∂L/∂z` 是：

- A. `p(1 - p)`
- B. `p - t`
- C. `-t / p`
- D. `(p - t)²`

---

## 三、动手 / 代码题

**Q9.** 预测输出，并说明 `count_parameters()` 数的是什么。

```python
model = Sequential(
    Linear(2, 16), ReLU(),
    Linear(16, 16), ReLU(),
    Linear(16, 8), ReLU(),
    Linear(8, 1), Sigmoid(),
)
print(model.count_parameters())

loader = DataLoader(list(range(400)), batch_size=16)
print(len(loader))
loader2 = DataLoader(list(range(401)), batch_size=16)
print(len(loader2))
```

**Q10.** 找问题。下面是 `main.py` 中 `BatchNorm.forward`（单样本版本）的训练分支：

```python
    def forward(self, x):
        if self.training:
            for j in range(self.size):
                self.running_mean[j] = (1 - self.momentum) * self.running_mean[j] + self.momentum * x[j]

            self.std_inv = [1.0 / math.sqrt(v + self.eps) for v in self.running_var]
            self.x_norm = [(x[j] - self.running_mean[j]) * self.std_inv[j] for j in range(self.size)]
            return [self.gamma[j] * self.x_norm[j] + self.beta[j] for j in range(self.size)]
```

(a) 新建 `bn = BatchNorm(2)` 后执行 `bn.forward([3.0, -1.0])`，输出大约是多少？`running_mean`、`running_var` 变成多少？
(b) 这和 BatchNorm 的定义"用当前 batch 的均值、方差做标准化"差在哪？至少指出两点。
(c) 为什么本框架的训练循环很难用上真正的 BatchNorm？

**Q11.** 讲义练习 5：把下面"逐样本更新"的内层循环改成**真正的 mini-batch 梯度累积**——每个 batch 只调用一次 `optimizer.zero_grad()` 和一次 `optimizer.step()`，梯度取 batch 内平均。只允许改训练循环，不改任何 Module 类。

```python
for batch_inputs, batch_targets in loader:
    for x, t in zip(batch_inputs, batch_targets):
        pred = model.forward(x)
        loss = criterion(pred, t)
        total_loss += loss

        optimizer.zero_grad()
        grad = criterion.backward()
        model.backward(grad)
        optimizer.step()
```

---

## 四、面试高频题

**Q12.**（基础必考）PyTorch 的 `nn.Module` 帮你做了哪些事？`model.train()` / `model.eval()` 具体影响哪些层？`model.eval()` 和 `torch.no_grad()` 有什么区别？

**Q13.**（原理深挖）为什么 `optimizer.zero_grad()` 要单独调用而不是在 `step()` 里自动完成？如何用它实现梯度累积？梯度累积和"直接用大 batch"完全等价吗？

**Q14.**（原理深挖）手写框架时，每个模块在 forward 中都要缓存一些东西给 backward 用（Linear 缓存输入、ReLU 缓存掩码、Sigmoid 缓存输出）。这件事和训练时的显存占用有什么关系？工业界有哪些手段缓解？

**Q15.**（工程实践）本代码用 `Sigmoid()` + `BCELoss()`，并在 Sigmoid 里把输入夹到 `[-500, 500]`、在 BCE 里把 p 夹到 `[1e-7, 1-1e-7]`。为什么需要这些防御？生产中为什么更推荐 `BCEWithLogitsLoss`？

**Q16.**（场景设计）这个框架只支持 `Sequential` 这种"一条直线"的网络。如果要支持残差连接（`y = x + f(x)`）、多输入多输出等任意计算图，你会怎么改造？

---

## 五、参考答案与解析

### Q1 — 答案：B

组合模式的核心是"容器与叶子节点同接口"。`Sequential` 有 `forward/backward/parameters/train/eval`，所以它能像普通层一样被放进另一个 `Sequential`，训练循环也只需对最外层调用一次 `model.forward()`、`model.backward()`、`model.parameters()`。A 错：计算量不变；C 错：本框架每个模块仍需手写 `backward`；D 错：参数共享需要显式让两个层引用同一份权重，与容器设计无关。

### Q2 — 答案：C

代码：`self.mask = [0.0 if random.random() < self.p else 1.0 / (1 - self.p) for _ in x]`。保留概率是 `1-p = 0.7`，保留的元素乘 `1/0.7`，这样每个元素的期望值 `0.7 × x/0.7 = x` 不变，评估时就可以直接原样输出，不需要再缩放——这叫 **inverted dropout**，也是 PyTorch 的做法。

### Q3 — 答案：B

`Dropout.forward` 第一行就是 `if not self.training: return x`。不调 `eval()`，`training` 仍为 True，测试时继续随机丢弃，预测带随机性。含 BatchNorm 的模型还会用测试 batch 的统计量而非训练积累的 running 统计量，单样本推理时问题更严重。不会报错（C 错），也和梯度无关（D 错）。

### Q4 — 答案：C

只要 `zero_grad` 发生在**本次 backward 之前**或**上一次 step 之后**，顺序就是对的：A、B、D 都正确（B 正是本代码 `train_framework()` 的写法，D 是"用完再清"）。C 在 backward 之后、step 之前清零，`step()` 看到的梯度全是 0：SGD 完全不更新；Adam 的 m 始终为 0，同样不更新。
⚠️ 注意：原 `quiz.json` 把"`zero_grad → forward → loss → backward → step`"作为唯一正确答案，但选项"`forward → loss → zero_grad → backward → step`"其实也正确，而且就是本节代码的写法。

### Q5 — 答案：B

m、v 初始化为 0，第 1 步 `m = 0.1·g`，明显偏小。除以 `1 - 0.9¹ = 0.1` 后 `m_hat = g`，恢复到无偏估计；随着 t 增大，`beta1**t → 0`，修正项趋近 1，自动失效。v 同理（`beta2=0.999`，修正持续得更久）。

### Q6 — 答案：B

`Linear.parameters()` 对每个权重返回 `(self.weights, i, j, self.weight_grads)`，对偏置返回 `(self.biases, i, None, self.bias_grads)`。优化器只要 `container[i][j] -= ...` 或 `container[i] -= ...`。因为 Python 列表是**可变对象、按引用传递**，优化器改的就是模型里的那份数据。这正是"优化器不需要知道网络结构"的体现，对应 PyTorch 中 `optimizer = Adam(model.parameters())`。

### Q7 — 答案：B

内层 `for x, t in zip(batch_inputs, batch_targets):` 对**每个样本**都执行 `zero_grad → backward → step`，等价于 batch size = 1 的 SGD/Adam。DataLoader 在这里只起到"每个 epoch 打乱顺序"的作用。讲义练习 5 就是让你把它改成真正的 mini-batch（见 Q11）。

### Q8 — 答案：B

BCE 对 p 的梯度是 `-t/p + (1-t)/(1-p) = (p - t) / (p(1-p))`，Sigmoid 的局部导数是 `p(1-p)`，相乘后约掉，得 `p - t`。实际运行验证：`z=0.3, t=1` 时，两者都是 `-0.42555748...`。这个"约掉"也是框架把两者融合成 `BCEWithLogitsLoss` 的理论依据（见 Q15）。

### Q9 — 参考答案

输出：

```text
465
25
26
```

- 参数量：`(2·16+16) + (16·16+16) + (16·8+8) + (8·1+1) = 48 + 272 + 136 + 9 = 465`。`count_parameters()` 返回 `len(self.parameters())`，而每个四元组对应**一个标量参数**，所以数出来正好是标量参数个数。ReLU/Sigmoid 的 `parameters()` 继承自基类，返回 `[]`。
- `__len__` 是 `(len(data) + batch_size - 1) // batch_size`，即向上取整：`400/16 = 25` 整除；`401` 时最后多一个只含 1 个样本的批，得 26。

### Q10 — 参考答案

(a) 实测输出约 `[2.69999, -0.89999]`，`running_mean = [0.3, -0.1]`，`running_var = [1.0, 1.0]`（没变）。过程：`running_mean = 0.9·0 + 0.1·x = [0.3, -0.1]`；`std_inv ≈ 1/√(1+1e-5) ≈ 1`；`x_norm = x - running_mean = [2.7, -0.9]`；γ=1、β=0，输出就是 `x_norm`。

(b) 与真正 BatchNorm 的差别：
1. **没有用 batch 统计量**：减去的是包含当前样本的滑动平均，方差用的是 `running_var`；
2. **`running_var` 在这条路径里从不更新**，永远是初始值 1.0，所以根本没有"除以标准差"的效果，输出约等于 `0.9·x`（早期）——几乎没有标准化；
3. **反向传播被大幅简化**：`backward` 只返回 `grad·γ·std_inv`，忽略了均值、方差对 x 的依赖。完整的 BN 反向（N 为 batch 大小，`dx̂ = dy·γ`）是：`dx = (std_inv / N) · (N·dx̂ - Σdx̂ - x̂·Σ(dx̂·x̂))`；
4. 训练与评估使用的统计量也不一致。

(c) 本框架的 `Module.forward(x)` 一次只处理**一个样本**（一维列表），而 BN 的本质是"跨样本"统计，需要整个 batch 同时流过。代码中虽有 `forward_batch(batch)`，但 `Sequential.forward` 和训练循环都调用单样本 `forward`，`Linear/ReLU` 也不支持批输入。要用上真正的 BN，需要把整个框架改成以 `[batch, features]` 张量为单位前向/反向——这正是 PyTorch 所有层都约定"第 0 维是 batch"的原因。另外，本节 3 个实验都没有用到 BatchNorm。

### Q11 — 参考答案

```python
for batch_inputs, batch_targets in loader:
    optimizer.zero_grad()                    # 每个 batch 只清一次
    B = len(batch_inputs)                    # 最后一批可能不足 16
    for x, t in zip(batch_inputs, batch_targets):
        pred = model.forward(x)
        loss = criterion(pred, t)
        total_loss += loss
        grad = [g / B for g in criterion.backward()]   # 取平均
        model.backward(grad)                 # Linear 里的 += 自动把 B 个样本的梯度累加
    optimizer.step()                         # 每个 batch 只更新一次
```

要点：
- 能这么改的前提是 `Linear.backward` / `BatchNorm.backward` 用的是 `+=`：不清零，梯度就自然累加。
- 每个样本必须**先 forward 再立刻 backward**，因为每层只缓存了"最近一次" forward 的输入（`self.input`、`self.mask`），不能先把 16 个样本都 forward 完再统一 backward。
- 除以 `B` 让梯度变成 batch 平均值，否则梯度大小随 batch 大小线性变化，SGD 需要重新调学习率（Adam 对梯度整体缩放不太敏感，但仍建议取平均）。用 `len(batch_inputs)` 而不是写死 16，是为了正确处理最后一个不完整的 batch。
- 实测（seed=42，Adam lr=0.01，30 个 epoch）测试准确率 96.0%；参数更新次数从每 epoch 400 次降到 25 次，通常需要更多 epoch 或更大学习率才能达到同样的 loss。

### Q12 — 参考回答要点

- **nn.Module 做的事**：①递归注册子模块与参数（赋值 `self.fc = nn.Linear(...)` 时自动登记），`parameters()` / `named_parameters()` 可以拿到全部参数；②`state_dict()` / `load_state_dict()` 保存与加载；③`.to(device)` 一次搬运所有参数和 buffer；④`train()/eval()` 递归切换模式；⑤`__call__` 包了一层，调用 `forward` 前后执行 hooks。backward 由 autograd 自动完成，不需要每层手写。
- **train/eval 影响的层**：Dropout（训练随机丢弃 / 评估恒等）、BatchNorm（训练用 batch 统计并更新 running 统计 / 评估用 running 统计）。Linear、ReLU 等不受影响。
- **与 no_grad 的区别**：`eval()` 只改层的**行为**，不影响是否构建计算图；`torch.no_grad()` 关闭梯度记录、省显存省算力，不改变 Dropout/BN 行为。推理时两者都要用。
- **常见误区**：以为 `eval()` 会关闭梯度；或在验证后忘了切回 `train()`，导致后续训练时 Dropout 失效。

### Q13 — 参考回答要点

- **为什么分离**：梯度是**累加**到 `.grad` 上的（本框架的 `+=` 即同理）。如果 `step()` 自动清零，就没法跨多次 backward 累积梯度。分离之后：清零时机由用户控制，一个机制同时支持普通训练和梯度累积。
- **梯度累积**：每 `k` 个 micro-batch 调一次 `step()` 和 `zero_grad()`；每个 micro-batch 的 loss 先除以 `k`（或者等价地对梯度取平均），等效 batch = `micro_batch × k`。用于显存放不下大 batch 的情况（大模型训练的标配）。
- **不完全等价的地方**：①BatchNorm 的统计量只基于 micro-batch，和真大 batch 不同（LayerNorm 无此问题）；②如果各 micro-batch 长度不同（如 token 数不同），简单除以 k 不等于按 token 平均；③学习率调度按"优化器步数"而不是 micro-batch 计数。
- **加分点**：提到 DDP 中可以在累积期间用 `no_sync()` 跳过梯度 all-reduce，只在最后一个 micro-batch 同步。

### Q14 — 参考回答要点

- **原理**：反向传播需要前向的中间结果（Linear 需要输入 x 来算 `∂L/∂W = g·xᵀ`，ReLU 需要掩码，Sigmoid 需要输出）。这些中间激活从 forward 开始一直保存到对应层的 backward 完成，所以训练显存 ≈ 参数 + 梯度 + 优化器状态（Adam 是参数的 2 倍）+ **激活值**；激活值随 batch size、序列长度、层数线性增长，在大模型训练中往往是大头。
- **推理为什么省**：推理不做 backward，不用缓存（`torch.no_grad()` 就是告诉框架不要保存这些）。
- **缓解手段**：
  - Gradient checkpointing（激活重计算）：只保存部分层的输入，backward 时重算 forward，用约 30% 额外计算换大量显存；
  - 混合精度（激活用 FP16/BF16 存）；
  - 减小 micro-batch + 梯度累积；
  - ZeRO/FSDP 切分参数、梯度、优化器状态（不直接省激活，但省其他部分）。
- **加分点**：能指出"缓存输出而不是输入"是 Sigmoid/Tanh 的小技巧——导数只依赖输出，省一次计算。

### Q15 — 参考回答要点

- **两个 clamp 的作用**：
  - Sigmoid 中 `max(-500, min(500, v))`：`math.exp(-v)` 在 `v < -709` 左右会 `OverflowError`，夹紧后 `exp(500)` 仍在 float 范围内；
  - BCE 中 `p` 夹到 `[1e-7, 1-1e-7]`：防止 `log(0) = -inf` 以及 backward 中 `-t/p` 除以 0。
- **代价**：clamp 区域内梯度被截断/失真；当 Sigmoid 饱和（p 非常接近 0 或 1 且预测错误）时，先算 p 再算 log 会损失精度。
- **BCEWithLogitsLoss**：直接接收 logit z，用 log-sum-exp 技巧计算 `max(z,0) - z·t + log(1 + e^{-|z|})`，数值稳定；梯度直接是 `σ(z) - t`（就是 Q8 的结论），不经过 p 的除法。多分类同理：`CrossEntropyLoss` 接收 logits，内部融合 `log_softmax + NLL`。
- **常见误区**：在模型末尾加了 Sigmoid/Softmax，又用 `BCEWithLogitsLoss` / `CrossEntropyLoss`，相当于激活了两次。

### Q16 — 参考回答要点

- **问题所在**：`Sequential.backward` 假设数据流是一条链，用 `reversed()` 即可；残差连接中 x 被用了两次，它的梯度必须是两条路径之和，链式结构表达不了。
- **方案一：张量级 autograd（PyTorch 的做法）**：每个运算产生的张量记录"由谁、由哪些输入产生"（`grad_fn`），形成动态计算图；`loss.backward()` 时对图做拓扑排序，逆序调用每个节点的局部反向函数，对多次使用的张量把梯度**累加**。这样 Module 只需要写 forward，backward 自动得到。
- **方案二：保留 Module 级手写 backward**：引入 `Add` 等合并模块，并把模型表示成 DAG，由框架按拓扑逆序调度 backward，在分叉点累加梯度。
- **其他配套**：参数命名与注册（`named_parameters`、`state_dict`）、批维度（张量 `[B, ...]` 而非单样本列表）、设备管理、hooks。
- **加分点**：提到本阶段第 03 节的标量 autograd（`Value` 类）就是方案一的缩小版；JAX 则走另一条路——函数变换 `grad(f)`，没有可变的 Module 状态。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 03 Backpropagation 从头开始](../../03-backpropagation/docs/zh.md)：链式法则与反向传播，本节每个 `backward()` 的来源。
- [阶段 03 · 04 Activation Functions](../../04-activation-functions/docs/zh.md)、[05 Loss Functions](../../05-loss-functions/docs/zh.md)：ReLU/Sigmoid/Tanh 的导数，MSE/BCE 的梯度。
- [阶段 03 · 06 Optimizers](../../06-optimizers/docs/zh.md)：SGD、Adam 与偏差修正。
- [阶段 03 · 07 正则化](../../07-regularization/docs/zh.md)、[08 Weight 初始化](../../08-weight-initialization/docs/zh.md)：Dropout、BatchNorm、He 初始化 `std = √(2/fan_in)`。
- [阶段 03 · 09 Learning Rate Schedules](../../09-learning-rate-schedules/docs/zh.md)：练习 2 要把它接进优化器。

### 本节被哪些后续内容用到
- [阶段 03 · 11 PyTorch 简介](../../11-intro-to-pytorch/docs/zh.md)：把本节手写的每个组件换成 `nn.Module`、`autograd`、`torch.optim`、`DataLoader`。
- [阶段 03 · 12 JAX 简介](../../12-intro-to-jax/docs/zh.md)：另一种框架哲学——纯函数 + `grad` 变换，没有可变 Module。
- [阶段 03 · 13 调试神经网络](../../13-debugging-neural-networks/docs/zh.md)：忘记 `zero_grad`、忘记 `eval()` 等都是那里的经典 bug。
- [阶段 01 · 05 链式法则与自动微分](../../../01-math-foundations/05-chain-rule-and-autodiff/docs/zh.md)：Q16 中"任意计算图"的理论基础。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：同样的"forward → loss → backward → step"循环，放大到 Transformer。
- [阶段 10 · 34 Gradient Checkpointing](../../../10-llms-from-scratch/34-gradient-checkpointing/docs/zh.md)：Q14 中激活值显存问题的系统解法。
- [阶段 19 · 46 梯度累积](../../../19-capstone-projects/46-gradient-accumulation/docs/zh.md)：Q11/Q13 的工程化版本。

### 延伸关键词
`nn.Module` · `组合模式 (Composite Pattern)` · `inverted dropout` · `running mean / running var` · `gradient accumulation` · `BCEWithLogitsLoss` · `计算图拓扑排序` · `state_dict` · `forward hooks` · `activation checkpointing`
