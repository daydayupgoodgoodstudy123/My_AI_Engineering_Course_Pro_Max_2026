# 代码讲解 · main.py

> **所属小节**：阶段 03 · 深度学习核心 · 第 09 节 学习率调度和 Warmup（Learning Rate Schedules and Warmup） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 4 秒跑完） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这份代码把五种学习率调度写成五个纯函数，然后用同一个小网络比较它们：

1. **调度就是函数**：`lr = schedule(step, ...)`，输入当前步数，输出当前学习率；与优化器、模型完全解耦。
2. **五种形状**：常数、阶梯衰减、余弦退火、warmup + 余弦、1cycle，用文本条形图画出来（STEP 1）。
3. **学习率大小的影响**：从 1.0 到 0.0001 扫 6 个常数学习率（STEP 2）。
4. **调度之间的对比和 warmup 长度的影响**（STEP 3、STEP 4）。
5. **关键时间点的学习率**：0、T/4、T/2、3T/4、T 五个点上各调度的值（STEP 5）。

> 一句话：**学习率调度只是一个 `step → lr` 的小函数，但它要和训练步数、优化器、任务难度配合起来才有意义**。本次实际运行中，常数学习率反而得到了最低的训练 loss——读懂"为什么"比记住"现代默认用 warmup + cosine"更重要。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `constant_schedule` | 函数 | 恒定学习率 | 常数调度 |
| `step_decay_schedule` | 函数 | 每 `step_size` 步乘一次 `gamma` | 阶梯衰减 |
| `cosine_schedule` | 函数 | 从 `lr` 余弦衰减到 `lr_min` | 余弦退火 |
| `warmup_cosine_schedule` | 函数 | 线性 warmup 后余弦衰减 | 现代默认 |
| `one_cycle_schedule` | 函数 | 前半程线性上升、后半程线性下降 | 1cycle |
| `visualize_schedule` | 函数 | 采样 21 个点，打印文本条形图 | 可视化 |
| `sigmoid` / `relu` / `relu_deriv` / `make_circle_data` | 函数 | 激活函数与圆形数据集 | 与前几节相同 |
| `train_with_schedule` | 函数 | 2→8→1 网络、逐样本 SGD，每步向调度函数要学习率 | 被调度的训练过程 |
| `compare_schedules` | 函数 | 五种调度各训练 300 epoch，打印起点/中点/终点/最佳 loss | 调度对比 |
| `lr_sensitivity` | 函数 | 常数学习率扫 6 个值，各训练 100 epoch，给出状态判定 | 三种失败模式 |
| `warmup_impact` | 函数 | warmup 占比 0%–20%，各训练 300 epoch | warmup 长度 |
| `schedule_trajectory` | 函数 | 打印 4 种调度在 5 个关键点的学习率 | 调度形状对比 |
| `if __name__ == "__main__":` | 演示入口 | 依次运行 STEP 1–5 | — |

数据流：所有调度函数共享同一签名 `fn(step, lr=..., total_steps=..., **kwargs)`；`train_with_schedule` 只认识这个签名，所以任何新调度只要符合它就能直接插进来。

---

## 3. 逐段精讲

### 3.1 统一签名与 `**kwargs`

```python
def constant_schedule(step, lr=0.01, **kwargs):
    return lr


def step_decay_schedule(step, lr=0.1, step_size=100, gamma=0.1, **kwargs):
    return lr * (gamma ** (step // step_size))
```

- 每个调度函数都以 `step` 开头、带 `lr` 参数，并在末尾接一个 `**kwargs`。调用方 `train_with_schedule` 会统一传 `lr=base_lr, total_steps=total_steps`，再加上各调度自己的参数。`constant_schedule` 用不到 `total_steps`，但有了 `**kwargs`，多传的参数会被**静默吸收**而不报错。这是一种"鸭子类型"的统一接口。
- `step // step_size` 是**整除**：0–99 步为 0，100–199 步为 1……对应讲义公式里的 `floor(epoch / step_size)`。注意这里的单位是"步"，不是 epoch，`compare_schedules` 中 `step_size=15000` 就是 75 个 epoch（每 epoch 200 步）。
- ⚠️ `**kwargs` 的代价：参数名拼错（如 `warmup_step=100`）也不会报错，只会悄悄用默认值。

### 3.2 余弦退火

```python
def cosine_schedule(step, lr=0.01, total_steps=1000, lr_min=1e-5, **kwargs):
    if step >= total_steps:
        return lr_min
    return lr_min + 0.5 * (lr - lr_min) * (1 + math.cos(math.pi * step / total_steps))
```

- 与讲义公式逐项对应：`step = 0` 时 `cos 0 = 1`，得 `lr`；`step = total_steps` 时 `cos π = -1`，得 `lr_min`。
- `1 + cos(...)` 的范围是 [0, 2]，乘 0.5 后是 [0, 1]，再线性映射到 `[lr_min, lr]`。
- **越界保护**：`step >= total_steps` 时直接返回 `lr_min`。如果没有这一行，超过总步数后 `cos` 会从 -1 回升，学习率会重新变大——这在"多训了几步"或"总步数算错"时是很隐蔽的 bug。

### 3.3 Warmup + Cosine

```python
def warmup_cosine_schedule(step, lr=0.01, total_steps=1000, warmup_steps=100, lr_min=1e-5, **kwargs):
    if total_steps <= warmup_steps:
        return lr * (step / max(warmup_steps, 1))
    if step < warmup_steps:
        return lr * step / warmup_steps
    progress = (step - warmup_steps) / (total_steps - warmup_steps)
    return lr_min + 0.5 * (lr - lr_min) * (1 + math.cos(math.pi * progress))
```

- **三个分支**：
  1. 退化情况：总步数不超过 warmup 步数，只做 warmup。`max(warmup_steps, 1)` 防止 `warmup_steps = 0` 时除以 0。
  2. warmup 段：`lr × step / warmup_steps`，从 **0** 线性升到接近 `lr`。
  3. 余弦段：`progress` 把剩余步数重新归一化到 [0, 1]，然后套余弦公式。
- **无缝衔接**：`step = warmup_steps` 时 `progress = 0`，余弦段返回恰好是 `lr`，与 warmup 段的终点连续。
- **为什么要重新归一化 progress**：如果直接用 `step / total_steps`，warmup 结束时余弦已经走了一段，峰值永远达不到 `lr`。
- ⚠️ `warmup_steps = 0` 时第二个分支被跳过（`step < 0` 不成立），直接进入余弦段，等价于纯 `cosine_schedule`——所以 STEP 4 中 0% warmup 的结果和 STEP 3 的 Cosine 完全相同（都是 0.008420）。
- ⚠️ 第 0 步学习率为 0，这一步的参数更新量为 0。
- ⚠️ 与 `cosine_schedule` 不同，这里没有 `step >= total_steps` 的保护，越界后学习率会重新上升。

### 3.4 1cycle

```python
def one_cycle_schedule(step, lr=0.01, total_steps=1000, **kwargs):
    mid = max(total_steps // 2, 1)
    if step < mid:
        return (lr / 25) + (lr - lr / 25) * step / mid
    else:
        progress = (step - mid) / max(total_steps - mid, 1)
        return lr * (1 - progress) + (lr / 10000) * progress
```

- 前半程：从 `lr/25` 线性升到 `lr`（`step = mid` 时到达）。后半程：从 `lr` 线性降到 `lr/10000`，与讲义的两个阶段一致。
- 两段都写成"起点 + (终点 − 起点) × 进度"的**线性插值**形式，第二段写成 `a·(1 − p) + b·p`，是同一件事的另一种写法。
- `max(..., 1)` 两处都是防除零。
- ⚠️ 简化：PyTorch 的 `OneCycleLR` 默认用余弦形状的升降（`anneal_strategy='cos'`）、上升段占 30%（`pct_start=0.3`），并且默认同时反向调节动量；这里是最朴素的"对半 + 线性"版本。

### 3.5 `visualize_schedule`：文本条形图

```python
def visualize_schedule(name, schedule_fn, total_steps=500, **kwargs):
    steps = list(range(0, total_steps, total_steps // 20))
    if total_steps - 1 not in steps:
        steps.append(total_steps - 1)

    lrs = [schedule_fn(s, total_steps=total_steps, **kwargs) for s in steps]
    max_lr = max(lrs) if max(lrs) > 0 else 1.0
    # ...
        bar_len = int(lr_val / max_lr * 40)
```

- 每隔 `500 // 20 = 25` 步采样一次，共 20 个点，再补上最后一步 499。
- `**kwargs` 在这里起"透传"作用：调用方传的 `lr=0.05, warmup_steps=50` 原样转交给调度函数。
- 条形长度按**本调度自己的最大值**归一化到 40 个字符，所以不同调度的条形不能直接比较绝对大小，只能看形状。
- `max(lrs) if max(lrs) > 0 else 1.0` 防止全 0 时除以 0。

### 3.6 `train_with_schedule`：每一步向调度要学习率

```python
def train_with_schedule(schedule_fn, schedule_name, data, epochs=300, base_lr=0.05, **kwargs):
    random.seed(0)
    hidden_size = 8
    total_steps = epochs * len(data)

    std = math.sqrt(2.0 / 2)
    w1 = [[random.gauss(0, std) for _ in range(2)] for _ in range(hidden_size)]
    # ...
    w2 = [random.gauss(0, std) for _ in range(hidden_size)]

    step = 0
    # ...
        for x, target in data:
            lr = schedule_fn(step, lr=base_lr, total_steps=total_steps, **kwargs)
            # ... 前向
            error = out - target
            d_out = error * out * (1 - out)

            for i in range(hidden_size):
                d_h = d_out * w2[i] * relu_deriv(z1[i])
                w2[i] -= lr * d_out * h[i]
                for j in range(2):
                    w1[i][j] -= lr * d_h * x[j]
                b1[i] -= lr * d_h
            b2 -= lr * d_out

            total_loss += (out - target) ** 2
            # ...
            step += 1
```

- **按步调度**：`total_steps = epochs × len(data)`，每个样本（每次参数更新）都调用一次调度函数，`step` 全局递增、跨 epoch 不清零。这和"每个 optimizer step 调一次 `scheduler.step()`"的工程实践一致。300 epoch × 200 样本 = 60,000 步。
- `random.seed(0)` 保证所有配置的初始权重相同，差异只来自调度。
- **初始化**：`std = √(2/2) = 1.0` 是第一层（fan_in = 2）的 Kaiming 初始化。⚠️ 第二层 `w2` 也用了同一个 std，而它的 fan_in 是 8，按 Kaiming 应为 `√(2/8) = 0.5`，这里是简化。
- **损失与梯度**：用的是 MSE `(out − target)²`，`d_out = error · out · (1 − out)` 是 MSE 经过 sigmoid 后对 z2 的导数（省略常数 2）。⚠️ 这个梯度被 `out·(1 − out)` 限制在约 ±0.148 以内，导致大学习率也很难让训练发散（见第 6 节 STEP 2）。
- **优化器是普通 SGD**：讲义解释 warmup 时说的是 Adam 的统计量问题，而这里没有任何优化器状态，所以 warmup 的作用在这个实验里体现不出来。
- ⚠️ `correct` 被统计了但从未使用（函数只返回 loss 列表），是遗留代码。`schedule_name` 参数也没有被用到。

### 3.7 `lr_sensitivity`：状态判定

```python
def lr_sensitivity(data):
    learning_rates = [1.0, 0.1, 0.05, 0.01, 0.001, 0.0001]
    # ...
    for lr in learning_rates:
        losses = train_with_schedule(constant_schedule, f"lr={lr}", data, epochs=100, base_lr=lr)
        start = losses[0]
        end = losses[-1]

        if math.isnan(end) or end > 1.0:
            status = "DIVERGED"
        elif end > start * 0.9:
            status = "BARELY MOVED"
        elif end < 0.15:
            status = "CONVERGED"
        else:
            status = "LEARNING"
```

- 判定顺序：NaN 或大于 1 → 发散；比起点只降了不到 10% → 几乎没动；低于 0.15 → 收敛；其余 → 还在学。
- `end_str = f"{end:.6f}" if not math.isnan(end) else "NaN"` 处理 NaN 的显示。
- ⚠️ 单样本 MSE `(out − target)²` 中 `out ∈ (0, 1)`、`target ∈ {0, 1}`，平均 loss 不可能超过 1，`end > 1.0` 永远不成立；而梯度有界，在这些学习率下权重也不会溢出成 NaN。所以 **"DIVERGED" 实际上是一个打印不出来的状态**。讲义版本中还有 `end > start`（loss 变大）这个条件，代码版本去掉了它。

### 3.8 `compare_schedules`、`warmup_impact`、`schedule_trajectory`

```python
    configs = [
        ("Constant", constant_schedule, {}),
        ("Step Decay", step_decay_schedule, {"step_size": 15000, "gamma": 0.1}),
        ("Cosine", cosine_schedule, {"lr_min": 1e-5}),
        ("Warmup+Cosine", warmup_cosine_schedule, {"warmup_steps": 3000, "lr_min": 1e-5}),
        ("1cycle", one_cycle_schedule, {}),
    ]
    # ...
    for name, schedule_fn, extra_kwargs in configs:
        losses = train_with_schedule(schedule_fn, name, data, epochs=300, base_lr=0.05, **extra_kwargs)
```

- 配置表是 `(名字, 函数, 额外参数字典)` 的三元组，用 `**extra_kwargs` 把字典**解包**成关键字参数传下去。
- Step Decay 每 15,000 步（75 个 epoch）乘 0.1，60,000 步内降 3 次：0.05 → 0.005 → 0.0005 → 0.00005。
- Warmup+Cosine 的 3000 步 = 总步数的 5%，在讲义建议的 1–5% 范围内。
- 打印"Mid Loss"取的是第 150 个 epoch，"Best Loss"是所有 epoch 中的最小值。

```python
def warmup_impact(data):
    warmup_fractions = [0.0, 0.01, 0.05, 0.10, 0.20]
    total_steps = 300 * len(data)
    # ...
        warmup_steps = int(total_steps * frac)
```

- 用比例算 warmup 步数，`int()` 向下取整。

```python
def schedule_trajectory(data):
    total_steps = 100 * len(data)
    # ...
        for s in [0, total_steps // 4, total_steps // 2, 3 * total_steps // 4, total_steps - 1]:
            vals.append(fn(s, total_steps=total_steps, **kw))
```

- 只调用调度函数、不训练，`data` 参数只用于计算总步数。最后一个点取 `total_steps − 1`，即最后一次实际使用的学习率。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 调度写成无状态纯函数 `f(step)` | 容易测试、画图、复用；与优化器解耦 | PyTorch 调度器是有状态对象（内部维护步数），断点续训要保存 `state_dict` |
| 统一签名 + `**kwargs` | 训练函数可以接任意调度 | 参数名拼错会被静默吞掉 |
| 按步（per-step）调度 | 与 LLM 训练实践一致，曲线更平滑 | 需要正确计算总步数；CNN 经典配方多按 epoch 调度 |
| warmup 从 0 开始 | 公式最简单 | 第 0 步的更新被浪费；有的实现从 `lr/warmup_steps` 起步 |
| 1cycle 用对半 + 线性 | 一眼能看懂"先升后降" | PyTorch 默认 30% 上升 + 余弦形状 + 动量反向调节 |
| 用普通 SGD + MSE | 延续前几节的代码，便于对照 | warmup 的价值（稳定 Adam）体现不出来；MSE + sigmoid 梯度有界，发散演示失效 |
| 只比较训练 loss | 实现简单 | 看不到调度对泛化的影响；生产中看验证集 |
| 每个配置只跑一个种子 | 运行快 | 0.008 与 0.0084 这种差距不能作为结论 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def cosine_schedule(step, lr=0.01, total_steps=1000, lr_min=1e-5, ...)` | 不传则用默认值 |
| `**kwargs` 收集多余参数 | `def constant_schedule(step, lr=0.01, **kwargs)` | 把未声明的关键字参数收进一个字典，起"吸收"作用 |
| `**dict` 解包传参 | `train_with_schedule(..., **extra_kwargs)`、`fn(s, total_steps=total_steps, **kw)` | 把字典展开成关键字参数，起"透传"作用 |
| 函数作为参数 | `schedule_fn(step, lr=base_lr, ...)` | 调度函数作为参数传入训练函数 |
| 整除 `//` | `step // step_size`、`total_steps // 20`、`len(losses) // 2` | 向下取整的除法 |
| 幂运算 | `gamma ** (step // step_size)` | γ 的 n 次方 |
| `math.cos` / `math.pi` | `math.cos(math.pi * progress)` | 余弦函数与 π |
| `max(x, 1)` 防除零 | `max(warmup_steps, 1)`、`max(total_steps - mid, 1)` | 让分母至少为 1 |
| `in` / `not in` | `if total_steps - 1 not in steps:` | 判断元素是否在列表中 |
| `range` 带步长 | `range(0, total_steps, total_steps // 20)` | 起点、终点（不含）、步长 |
| 列表推导式 | `[schedule_fn(s, total_steps=total_steps, **kwargs) for s in steps]` | 批量计算 |
| 条件表达式 | `max(lrs) if max(lrs) > 0 else 1.0`、`f"{end:.6f}" if not math.isnan(end) else "NaN"` | 一行 if/else |
| `math.isnan` | `math.isnan(end)` | 判断是否为 NaN（`NaN == NaN` 为 False，不能用 `==`） |
| `zip` | `for s, lr_val in zip(steps, lrs):` | 两个列表配对遍历 |
| 三元组解包 | `for name, schedule_fn, extra_kwargs in configs:` | 配置表的每一项拆成三个变量 |
| `min()` | `best = min(losses)` | 求最小值 |
| f-string 格式符 | `f"{name:<20}"`、`f"{losses[0]:>12.6f}"`、`f"{frac*100:>9.0f}%"`、`f"{warmup_steps:>14d}"` | 左/右对齐、宽度、小数位 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行实验 |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py`，约 4 秒完成。

**STEP 1：五种调度的形状（总步数 500，峰值 0.05）**

节选关键行：

```text
Step Decay:
  Step  100: lr=0.050000 ########################################
  Step  125: lr=0.025000 ####################
  Step  250: lr=0.012500 ##########
  Step  375: lr=0.006250 #####

Cosine Annealing:
  Step    0: lr=0.050000 ########################################
  Step  125: lr=0.042679 ##################################
  Step  250: lr=0.025005 ####################
  Step  375: lr=0.007331 #####
  Step  499: lr=0.000010

Warmup + Cosine:
  Step    0: lr=0.000000
  Step   25: lr=0.025000 ####################
  Step   50: lr=0.050000 ########################################
  Step  275: lr=0.025005 ####################
  Step  499: lr=0.000011

1cycle:
  Step    0: lr=0.002000 #
  Step  250: lr=0.050000 ########################################
  Step  475: lr=0.005004 ####
  Step  499: lr=0.000205
```

- **Step Decay**（这里用 `step_size=125, gamma=0.5`）：每 125 步减半，呈阶梯状。
- **Cosine**：前 125 步只降了约 15%，中段下降最快，末尾平缓地落到 1e-5。
- **Warmup + Cosine**：前 50 步线性升温，第 50 步到达峰值；余弦的"中点"（0.025）推迟到了第 275 步。
- **1cycle**：从 `0.05/25 = 0.002` 升到第 250 步的 0.05，再线性降。最后一个采样点 499 的值是 0.000205，因为它离终点（第 500 步）还差一步，线性下降段每步约降 0.0002。

**STEP 2：学习率敏感性（常数调度，100 epoch）**

```text
        LR   Start Loss     End Loss          Status
    1.0000     0.229053     0.031786       CONVERGED
    0.1000     0.395736     0.009589       CONVERGED
    0.0500     0.422651     0.014495       CONVERGED
    0.0100     0.465033     0.041905       CONVERGED
    0.0010     0.481675     0.307537        LEARNING
    0.0001     0.483407     0.444479    BARELY MOVED
```

- **太小的学习率**确实"爬行"：0.0001 训练 100 epoch 只降了约 8%，0.001 还在学。
- **太大的学习率没有发散**：lr=1.0 也收敛了，只是最终 loss（0.0318）不如 0.1（0.0096）。原因是 MSE + sigmoid 的梯度被 `out·(1 − out)` 压在约 ±0.148 以内，输出越饱和梯度越小，相当于自带梯度裁剪。讲义"lr=0.1 三步发散"在这个设置下无法复现。
- 最佳点在 0.1 附近：过大（1.0）和过小（0.01 及以下）都更差，呈现典型的 U 形。
- Start Loss 随学习率变化，是因为第一个 epoch 内已经在更新，学习率越大第一个 epoch 的平均 loss 越低。

**STEP 3：调度对比（峰值 0.05，300 epoch）**

```text
Schedule               Start Loss     Mid Loss     End Loss    Best Loss
Constant                 0.422651     0.009973     0.005437     0.005437
Step Decay               0.422651     0.014659     0.014512     0.014512
Cosine                   0.422651     0.011089     0.008420     0.008420
Warmup+Cosine            0.480849     0.011341     0.008381     0.008381
1cycle                   0.479481     0.017522     0.008183     0.008183
```

- **Constant 最好**：在这个任务上，0.05 的逐样本 SGD 一直在稳步下降，还没到需要靠衰减"收尾"的阶段，任何衰减都会拖慢进度。
- **Step Decay 最差**：第 75 个 epoch 就降到 0.005，之后进展缓慢；mid（0.0147）到 end（0.0145）几乎没变。
- **Warmup+Cosine 和 1cycle 的起始 loss 更高**（0.48 vs 0.42）：第一个 epoch 学习率很小，学得慢。到最后三种余弦/1cycle 类调度的 loss 都在 0.008 左右。
- **End Loss = Best Loss**：所有配置的 loss 都是单调下降到最后，没有出现"后期变差"，说明这里并不存在讲义描述的"常数学习率在最小值附近震荡"现象。
- 结论：调度的优势依赖于问题本身。这个实验只能说明各调度的**行为**，不能用来证明"warmup + cosine 优于常数学习率"。

**STEP 4：warmup 长度的影响**

```text
  Warmup %   Warmup Steps     End Loss    Best Loss
        0%              0     0.008420     0.008420
        1%            600     0.008807     0.008807
        5%           3000     0.008381     0.008381
       10%           6000     0.008381     0.008381
       20%          12000     0.008359     0.008359
```

- 0% 与 STEP 3 的 Cosine 完全相同（0.008420），印证了 `warmup_steps = 0` 时等价于纯余弦。
- 所有结果都在 0.0084–0.0088 之间，差异可以忽略。warmup 要解决的是 Adam 统计量不可靠、大 batch/大学习率下的早期不稳定，而这里是普通 SGD、batch=1、峰值只有 0.05，训练初期本来就稳定。
- 5% 和 10% 的结果在 6 位小数上完全一样，是巧合级别的接近，不要过度解读。

**STEP 5：关键时间点的学习率（总步数 20,000）**

```text
  Schedule                 Step 0   Step T/4   Step T/2  Step 3T/4     Step T
  Constant               0.050000   0.050000   0.050000   0.050000   0.050000
  Cosine                 0.050000   0.042679   0.025005   0.007331   0.000010
  Warmup+Cosine          0.000000   0.044730   0.027069   0.008076   0.000010
  1cycle                 0.002000   0.026000   0.050000   0.025003   0.000010
```

- Cosine 在 T/4 只降到 85%，在 3T/4 已降到 15%——"两头慢、中间快"。
- Warmup+Cosine（5% warmup）整体比 Cosine 晚一点：T/2 时 0.027 > 0.025。
- 1cycle 在 T/2 才到峰值，后半程线性下降；3T/4 是 0.025003 而不是 0.025，因为终点是 `lr/10000` 而不是 0。
- 四种调度的"末尾学习率"都很小（Constant 除外），这正是调度的核心目的：训练末期用小步收敛。

---

## 7. 动手改一改

1. **让发散出现**：把 `d_out = error * out * (1 - out)` 改成交叉熵的梯度 `d_out = error`，并在 `lr_sensitivity` 的判定中加回 `end > start`，重新扫学习率，看哪个值开始发散。
2. **让调度体现价值**：把 `base_lr` 提高到 0.5（配合第 1 题的交叉熵），比较 Constant 与 Cosine 的最终 loss，观察常数学习率是否开始在后期震荡。
3. **指数衰减**（讲义练习 1）：实现 `lr · gamma^step`，`gamma = 0.999`，注意按步衰减时 60,000 步后学习率会小到可以忽略，思考 gamma 该怎么按总步数设置。
4. **SGDR**（讲义练习 4）：实现带重启的余弦，每 `T_0` 步重置到 `lr`，画出形状并和单周期余弦对比。
5. **LR range test**（讲义练习 2）：学习率从 1e-7 按指数增长到 1，每步记录 loss，找出 loss 开始上升前的学习率。
6. **补上越界保护**：给 `warmup_cosine_schedule` 加上 `if step >= total_steps: return lr_min`，并写一个小测试检查 `step = total_steps + 100` 时的返回值。

---

## 8. 常见坑

- **步进单位不一致**：`total_steps` 按 iteration 算，却每个 epoch 才调用一次调度（或反过来），调度形同虚设。
- **总步数算错**：用了梯度累积、多卡时，`total_steps` 应该是**参数更新次数**；算多了学习率降不下来，算少了后期变成 `lr_min` 甚至越界回升。
- **越界后学习率回升**：余弦公式在 `step > total_steps` 时会重新变大，需要像 `cosine_schedule` 那样做保护。
- **warmup 从 0 开始浪费一步**：第 0 步更新量为 0；影响很小，但要知道它的存在。
- **`**kwargs` 吞掉拼错的参数**：`warmup_step=3000` 不会报错，只会用默认值 100，结果完全不同。
- **用玩具实验下大结论**：本节 STEP 3 中常数学习率最好，并不意味着大模型训练可以不用调度；反过来，大模型的默认配置也不一定适合你的小任务。
