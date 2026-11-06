# 测验 · 学习率调度和 Warmup（Learning Rate Schedules and Warmup）

> **阶段 03 · 深度学习核心 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 学习率是最重要的超参数 | 三种失败模式：太大 → 发散；太小 → 爬行；不衰减 → 在最小值附近震荡、下不去 |
| 2 | 最优学习率随训练变化 | 早期要大步覆盖地形，后期要小步收敛；调度（schedule）就是"训练步数 → 学习率"的函数 |
| 3 | 常数学习率 | `lr(t) = lr₀`；适合调试和小模型，长时间训练通常不是最优 |
| 4 | Step decay | `lr = lr₀ · γ^⌊epoch/step_size⌋`；ResNet 时代的经典（0.1 起，每 30 epoch ×0.1）；切换点需要按任务调，切换处可能出现 loss 突变 |
| 5 | Cosine annealing | `lr = lr_min + ½(lr_max − lr_min)(1 + cos(πt/T))`；开头和结尾下降平缓、中间最快；只需定 lr_max 和 lr_min |
| 6 | Warmup | 前 N 步从接近 0 线性升到 lr_max；讲义的解释是 Adam 等自适应优化器早期的统计量不可靠，大步更新容易走偏；通常占总步数 1–5% |
| 7 | Warmup + Cosine | 现代默认（Llama、GPT、PaLM 等）：先线性升温，再按 `progress = (t − warmup)/(T − warmup)` 做余弦衰减 |
| 8 | 1cycle | 前半程从 lr_max/25 升到 lr_max，后半程降到 lr_max/10000；高学习率阶段相当于正则化；必须预先知道总步数 |
| 9 | 工程用法 | PyTorch `torch.optim.lr_scheduler`（`StepLR`、`CosineAnnealingLR`、`OneCycleLR`、`LambdaLR`），HuggingFace `get_cosine_schedule_with_warmup`；`scheduler.step()` 放在 `optimizer.step()` 之后，步进单位要和 `T_max`/总步数一致 |

### 核心技能（能动手做到）

- [ ] 从零实现 constant、step decay、cosine、warmup+cosine、1cycle 五个调度函数，并手算它们在 `0、T/4、T/2、3T/4、T` 处的值
- [ ] 读懂 `main.py` 的五步输出，解释为什么在这个任务上常数学习率反而得到最低的训练 loss，以及为什么 warmup 长短几乎没有影响
- [ ] 指出 `lr_sensitivity` 在当前损失函数下几乎不可能打印 `DIVERGED` 的原因，并改造实验让"学习率过大发散"真正出现
- [ ] 用 PyTorch `LambdaLR` 写出与 `warmup_cosine_schedule` 等价的调度器，并按"每个 optimizer step 调一次"正确使用
- [ ] 实现 LR range test（学习率从 1e-7 指数增大到 1，记录 loss），据此选出峰值学习率
- [ ] 根据场景（从头预训练 / 微调 / 小算力快速训练 / 不知道总步数）选择调度方式和 warmup 比例

---

## 二、基础自测（选择题）

**Q1.** Cosine annealing，`lr_max = 0.05`、`lr_min ≈ 0`，总步数 T。在 `t = T/4` 时学习率约为：

- A. 0.0375（线性插值的结果）
- B. 约 0.0427
- C. 0.025
- D. 约 0.0073

**Q2.** Step decay：`lr₀ = 0.1`、`γ = 0.1`、`step_size = 30`（按 epoch）。第 65 个 epoch 的学习率是：

- A. 0.1
- B. 0.01
- C. 0.001
- D. 0.0001

**Q3.** 按照讲义的解释，在 Adam 类优化器上使用 warmup 的主要原因是：

- A. 增强正则化，减少过拟合
- B. 训练初期优化器的梯度统计量还不可靠，此时用大学习率容易迈出方向很差的大步
- C. 降低显存占用
- D. 让 weight decay 更快生效

**Q4.** 用本节代码的 `warmup_cosine_schedule(step, lr=0.05, total_steps=1000, warmup_steps=100, lr_min=1e-5)`，`step = 0` 和 `step = 100` 时的返回值分别是：

- A. 0.0005 和 0.05
- B. 0 和 0.05
- C. 0 和约 0.025
- D. 1e-5 和 0.05

**Q5.** 关于 1cycle 策略，下面哪一项是讲义指出的**主要代价**？

- A. 只能用于 SGD
- B. 必须预先知道总训练步数
- C. 训练速度比常数学习率慢
- D. 学习率永远不会超过初始值

**Q6.** 你训练 10 个 epoch，每个 epoch 100 个 iteration，设置了 `CosineAnnealingLR(optimizer, T_max=1000)`，但**在每个 epoch 结束时**才调用一次 `scheduler.step()`。训练结束时学习率大约是：

- A. 接近 `eta_min`，衰减完成
- B. 初始值的约 50%
- C. 仍约为初始值（只走完了余弦曲线的 1%）
- D. 0

**Q7.** 用 SGD 训练 ImageNet，把 batch size 从 256 增大到 2048（8 倍）。按 Goyal 等（2017）的经验做法，学习率应该：

- A. 保持不变
- B. 乘以 8（线性缩放规则），并配合 warmup
- C. 除以 8
- D. 乘以 8，同时去掉 warmup

---

## 三、动手 / 代码题

**Q8.** `main.py` STEP 5 打印（`total_steps = 100 × 200 = 20000`，warmup 为 5% 即 1000 步）：

```text
  Schedule                 Step 0   Step T/4   Step T/2  Step 3T/4     Step T
  Constant               0.050000   0.050000   0.050000   0.050000   0.050000
  Cosine                 0.050000   0.042679   0.025005   0.007331   0.000010
  Warmup+Cosine          0.000000   0.044730   0.027069   0.008076   0.000010
  1cycle                 0.002000   0.026000   0.050000   0.025003   0.000010
```

(a) 手算验证 Warmup+Cosine 在 `T/4`（第 5000 步）的 0.044730；(b) 为什么它在 `T/2` 比纯 Cosine 高？(c) 1cycle 在 `3T/4` 为什么是 0.025003 而不是 0.025？(d) Warmup+Cosine 在第 0 步学习率为 0，对训练意味着什么？

**Q9.** STEP 2 的实际输出：

```text
        LR   Start Loss     End Loss          Status
    1.0000     0.229053     0.031786       CONVERGED
    0.1000     0.395736     0.009589       CONVERGED
    0.0500     0.422651     0.014495       CONVERGED
    0.0100     0.465033     0.041905       CONVERGED
    0.0010     0.481675     0.307537        LEARNING
    0.0001     0.483407     0.444479    BARELY MOVED
```

讲义说"lr=0.1 时 3 步就发散"，这里 lr=1.0 都收敛了。(a) 结合 `train_with_schedule` 的损失和梯度写法解释原因；(b) 看下面的状态判定逻辑，这段代码有没有可能打印 `DIVERGED`？

```python
        if math.isnan(end) or end > 1.0:
            status = "DIVERGED"
        elif end > start * 0.9:
            status = "BARELY MOVED"
```

**Q10.** STEP 3 与 STEP 4 的实际输出：

```text
Schedule               Start Loss     Mid Loss     End Loss    Best Loss
Constant                 0.422651     0.009973     0.005437     0.005437
Step Decay               0.422651     0.014659     0.014512     0.014512
Cosine                   0.422651     0.011089     0.008420     0.008420
Warmup+Cosine            0.480849     0.011341     0.008381     0.008381
1cycle                   0.479481     0.017522     0.008183     0.008183

  Warmup %   Warmup Steps     End Loss    Best Loss
        0%              0     0.008420     0.008420
        1%            600     0.008807     0.008807
        5%           3000     0.008381     0.008381
       10%           6000     0.008381     0.008381
       20%         12000     0.008359     0.008359
```

(a) 为什么常数学习率的最终 loss 最低、Step Decay 最差？(b) 为什么 warmup 从 0% 到 20% 几乎没有影响？(c) 设计一个能体现"调度和 warmup 价值"的改进实验。

**Q11.** 用 PyTorch 的 `LambdaLR` 写一个与 `warmup_cosine_schedule` 等价的调度器（支持 `lr_min`），并写出正确的训练循环调用位置。

---

## 四、面试高频题

**Q12.**（基础必考）什么是 learning rate warmup？为什么 Transformer / 大 batch 训练几乎都要用？warmup 一般设多长？

**Q13.**（原理深挖）为什么训练后期要降低学习率？cosine 衰减相比 step decay 有什么好处？

**Q14.**（工程实践）你要用 AdamW 微调一个开源 LLM，预算是 3 个 epoch。请给出学习率和调度的具体配置，以及实现时容易踩的坑。

**Q15.**（场景设计）一个长时间的预训练任务在第 10,000 步左右 loss 突然飙升。你怎么判断这和学习率调度有关？可以怎么处理？

**Q16.**（追问型）1cycle、warmup + cosine、step decay 分别适合什么场景？如果你**不知道**总训练步数（例如数据持续流入、想随时停止），该怎么设计调度？

---

## 五、参考答案与解析

### Q1 — 答案：B

`lr = ½ × 0.05 × (1 + cos(π/4)) = 0.025 × 1.7071 ≈ 0.0427`。代码 STEP 5 中 Cosine 在 `T/4` 的值 0.042679 正是这个数（`lr_min = 1e-5` 影响极小）。余弦曲线开头平缓：走完 1/4 的步数，学习率只降了约 15%，而线性衰减会降 25%（A）。C 是 `T/2` 的值，D 是 `3T/4` 的值。

### Q2 — 答案：C

`⌊65/30⌋ = 2`，`0.1 × 0.1² = 0.001`。第 0–29 epoch 为 0.1，30–59 为 0.01，60–89 为 0.001。

### Q3 — 答案：B

讲义的解释：Adam 维护的梯度均值和方差估计从 0 开始，最初几步依据的统计量很不可靠，如果此时学习率很大，模型会迈出"又大又歪"的步子；warmup 先用很小的学习率，等统计量稳定后再升到峰值。A、C、D 都不是 warmup 的目的。补充：warmup 对 SGD 的大 batch 训练同样有用（Q7），本节代码用的是 SGD + 小数据，所以 warmup 几乎没有效果（Q10）。

### Q4 — 答案：B

`step < warmup_steps` 时返回 `lr * step / warmup_steps`，`step = 0` 时为 0。`step = 100` 时进入余弦分支，`progress = 0`，`lr_min + ½(lr − lr_min)(1 + cos 0) = lr = 0.05`，与 warmup 结束时无缝衔接。A 是"从 lr/warmup_steps 开始"那种变体（讲义也提到过这种写法），但本节代码从 0 开始。

### Q5 — 答案：B

1cycle 的上升和下降阶段都按总步数划分（代码中 `mid = total_steps // 2`），所以必须事先确定总步数。它并不限于 SGD（A 错）；讲义认为在固定算力预算下它往往比 cosine 更快（C 错）；它的峰值就是 lr_max，起点是 lr_max/25（D 错）。

### Q6 — 答案：C

`T_max` 的单位是"调用 `scheduler.step()` 的次数"。每个 epoch 才调一次，10 个 epoch 只走了 10 步，位置是 `10/1000 = 1%`，学习率系数 `½(1 + cos(π × 0.01)) ≈ 0.99975`，基本没衰减。要么改成每个 iteration 调一次，要么把 `T_max` 设为 epoch 数 10。这是线上非常常见的隐蔽 bug：代码能跑，只是调度形同虚设。

### Q7 — 答案：B

Goyal 等提出线性缩放规则：batch 扩大 k 倍，学习率也乘 k；但训练刚开始时直接用大学习率不稳定，所以要配合 warmup（论文中是前 5 个 epoch 逐渐升到目标值）。讲义也提醒"增大 batch size 时，warmup 长度需要随之调整"。D 去掉 warmup 正是大 batch 训练早期崩溃的原因。

### Q8 — 参考答案

(a) `progress = (5000 − 1000)/(20000 − 1000) = 4000/19000 ≈ 0.2105`；`cos(π × 0.2105) ≈ 0.7891`；`lr = 1e-5 + ½ × (0.05 − 1e-5) × 1.7891 ≈ 0.04473`。

(b) 余弦段从第 1000 步才开始，`T/2` 时 `progress = 9000/19000 ≈ 0.474`，还没走到余弦曲线的一半，所以比纯 Cosine（正好一半，0.025005）略高。warmup 把整条衰减曲线向后推了。

(c) 代码中后半段是线性插值 `lr·(1 − progress) + (lr/10000)·progress`，终点是 `lr/10000 = 5e-6` 而不是 0。`3T/4` 时 `progress = 0.5`：`0.05 × 0.5 + 0.000005 × 0.5 = 0.0250025`，打印为 0.025003。

(d) 第 0 步的参数更新量为 0，相当于白算了一次前向和反向（只有统计 loss 的作用），之后学习率才从 `0.05/1000` 开始线性增大。实践中有的实现从 `lr/warmup_steps` 开始（讲义提到的写法），或用 `(step + 1)/warmup_steps`，避免浪费第一步。

### Q9 — 参考答案

(a) 发散不了的原因在损失和梯度的形式：

```python
            error = out - target
            d_out = error * out * (1 - out)
```

这是 **MSE + sigmoid 输出**。`|d_out|` 有上界：target=0 时为 `out²(1 − out)`，在 `out = 2/3` 处取最大值 `4/27 ≈ 0.148`；target=1 时对称。而且输出越饱和，`out·(1 − out)` 越小，梯度自动变小——相当于自带"梯度裁剪"。再加上 ReLU 的死神经元会停止更新，即使 lr=1.0，单步的更新量也有限，网络不会数值爆炸。讲义"lr=0.1 三步发散"描述的是一般情况（例如无界损失、无饱和的输出），这个玩具设置恰好不满足。

(b) 实际上几乎不可能。每个样本的 MSE 是 `(out − target)²`，`out ∈ (0, 1)`、`target ∈ {0, 1}`，单样本 loss 不超过 1，平均值 `end` 也不会超过 1，`end > 1.0` 永远为假；`math.isnan(end)` 要求权重先溢出成 inf/NaN，而前面分析过梯度有界，在这些学习率下不会发生。讲义版本里还有 `end > start` 这个条件（loss 变大就算发散），代码版本把它删掉了，于是一个 loss 越训越大的运行最多只会被标成 "BARELY MOVED"。

改造思路：把损失换成交叉熵（梯度 `out − target` 不再被 `out(1 − out)` 压小）并去掉 sigmoid 的输入裁剪保护，或者换成线性回归 `(w·x − y)²` 这种无界损失；判定条件恢复 `end > start`。

### Q10 — 参考答案

(a) 这个任务的训练 loss 还在持续下降，lr=0.05 的逐样本 SGD 并没有进入"在最小值附近震荡"的阶段，所以**任何衰减都会减慢进展**：

- Constant 全程保持 0.05，下降最多（0.005437）。
- Step Decay（`step_size = 15000`，总步数 60000）在训练 1/4 处就把学习率降到 0.005，再到 0.0005、0.00005，后 3/4 的训练几乎停滞，mid 和 end loss 都停在约 0.0145。
- Cosine 类前期学习率接近峰值，后期迅速变小，最终 loss 介于两者之间。
- 另外，这里只看了**训练** loss。调度的价值更多体现在最终的泛化和稳定性上，训练 loss 最低不等于模型最好。

(b) warmup 的动机是稳定 Adam 早期不可靠的统计量，或者大 batch/大学习率下的早期不稳定。本代码用的是**普通 SGD**、batch size 为 1、峰值学习率只有 0.05，训练初期本来就不会不稳定，所以 warmup 长短只是让前几个 epoch 学得慢一点，对最终 loss 几乎没有影响（0.0084 左右）。

(c) 改进方案：

- 把峰值学习率提高到常数调度会明显震荡的程度（例如 0.5 或 1.0，并改用交叉熵），再比较 Constant 与 Cosine；
- 换用 Adam/AdamW 和更深的网络，观察有无 warmup 时前几百步的 loss 曲线；
- 划分训练/测试集，比较测试 loss/准确率；
- 每个配置多跑几个随机种子，报告均值和方差。

### Q11 — 参考答案

`LambdaLR` 的 lambda 返回的是**乘在初始学习率上的系数**，所以要把 `lr_min` 换算成比例：

```python
import math
from torch.optim.lr_scheduler import LambdaLR

def make_warmup_cosine_lambda(total_steps, warmup_steps, base_lr, lr_min=0.0):
    floor = lr_min / base_lr
    def lr_lambda(step):
        if step < warmup_steps:
            return step / max(1, warmup_steps)
        progress = min(1.0, (step - warmup_steps) / max(1, total_steps - warmup_steps))
        return floor + 0.5 * (1 - floor) * (1 + math.cos(math.pi * progress))
    return lr_lambda

optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)
scheduler = LambdaLR(optimizer, make_warmup_cosine_lambda(total_steps, warmup_steps, 3e-4, 3e-5))

for step in range(total_steps):
    optimizer.zero_grad()
    loss = compute_loss(model, next(batches))
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    scheduler.step()          # 每个 optimizer step 之后调用一次
```

要点：

- 用纯 Python 对比验证：`0.05 × lr_lambda(s)` 与 `warmup_cosine_schedule(s, lr=0.05, total_steps=20000, warmup_steps=1000, lr_min=1e-5)` 在全部 20000 步上的最大差异约为 7e-18（浮点误差）。
- `min(1.0, …)` 让超过总步数后停在 `lr_min`，与代码中 `cosine_schedule` 的 `step >= total_steps` 保护一致。
- `scheduler.step()` 必须在 `optimizer.step()` 之后（上一节的训练循环顺序）。
- 用了梯度累积时，`total_steps` 和 `scheduler.step()` 都按**参数更新次数**计，而不是按 micro-batch 计。
- HuggingFace 的 `get_cosine_schedule_with_warmup` 是同样的思路（默认衰减到 0）。

### Q12 — 参考回答要点

- 定义：训练前 N 步把学习率从接近 0 线性升到峰值，然后再进入主调度（通常是 cosine）。
- 为什么需要：
  - 自适应优化器：Adam 的一阶/二阶矩估计在早期样本太少、不可靠，大学习率下更新方向和尺度都可能失真（讲义解释）；
  - 训练初期模型输出、梯度尺度变化剧烈（尤其是深层 Transformer、刚初始化的残差流），小步更安全；
  - 大 batch：按线性缩放规则放大学习率后，开头直接用大学习率容易崩溃，需要 warmup 过渡（Goyal 等）。
- 长度：讲义建议 1–5% 的总步数（Use It 部分建议 3–5%）；BERT 用了 10,000 步；Llama 2 用 2,000 步；Llama 3 405B 用了 8,000 步。
- 加分点：能指出 warmup 太短会早期发散/loss spike，太长则浪费算力；能说出 RAdam 等工作试图从优化器层面替代 warmup。
- 常见误区：以为 warmup 只对 Adam 有意义（大 batch SGD 同样需要）；把 warmup 步数按 epoch 设置却按 iteration 步进。

### Q13 — 参考回答要点

- 为什么后期要降：mini-batch 梯度有噪声，学习率固定时参数会在最小值附近以"学习率 × 梯度噪声"的幅度来回跳动，下不到更低的地方（讲义："oscillates around a minimum it can never reach"）。逐步降低学习率可以缩小这个震荡范围，让模型收敛到更精确的位置。
- Cosine 相比 step decay：
  - 平滑，没有突变点，不会在切换处出现 loss 跳变；
  - 不需要调"在哪几个 epoch 降"这种依赖数据集的超参，只要 lr_max、lr_min（和总步数）；
  - 形状上前期下降慢、中期快、后期又慢，讲义的解释是大部分学习发生在训练中段，此时需要较大的步子。
- Step decay 的优势：简单、可解释，CNN 时代有大量现成配方（ResNet-50：0.1，每 30 epoch ×0.1）。
- 加分点：提到 SGDR（带重启的余弦）、线性衰减（BERT 使用）；能说清 lr_min 一般取峰值的 1/10 左右（讲义决策图中 `lr_min = lr_max / 10`，Llama 2 也是衰减到峰值的 10%）。

### Q14 — 参考回答要点

- 典型配置（讲义经验值）：AdamW，`lr = 2e-5`（范围 1e-5～5e-5），`weight_decay = 0.01`；warmup 占总步数 3–5%；之后 cosine 衰减（或 linear 衰减）。
- 总步数要算对：`total_steps = epochs × ⌈样本数 / (batch_size × 梯度累积步数 × GPU 数)⌉`，即**优化器更新次数**。
- 工程细节：
  - 每个 optimizer step 调一次 `scheduler.step()`，放在 `optimizer.step()` 之后；
  - 断点续训要同时保存/恢复 optimizer、scheduler 的 `state_dict`，否则恢复后学习率会从头开始 warmup；
  - 多个参数组（例如 LoRA 参数与分类头用不同学习率）时，`LambdaLR` 的系数作用于每组各自的初始学习率；
  - 打印/记录每步的学习率，确认曲线符合预期。
- 加分点：提到可以先用较小数据跑 LR range test 或几组学习率（1e-5、2e-5、5e-5）做小规模扫描；微调学习率过大会导致"灾难性遗忘"。
- 常见误区：直接沿用预训练的峰值学习率（如 3e-4）做全参数微调；`T_max` 按 epoch 设置却按 iteration 步进（Q6）。

### Q15 — 参考回答要点

1. **对齐时间轴**：把学习率曲线、loss 曲线、梯度范数曲线画在同一张图上。第 10,000 步处在哪个阶段？如果 warmup 恰好在这附近结束、学习率刚到峰值，就高度可疑。
2. **看梯度范数**：飙升前梯度范数是否先出现尖峰？如果 loss 和梯度同时飙升，往往是学习率相对当前曲率过大。
3. **排除数据问题**：查看对应 batch 是否有异常样本；如果换掉数据后 spike 消失，就不是调度的问题。
4. **处理方式**：
   - 回滚到 spike 之前的 checkpoint，降低峰值学习率或延长 warmup 后继续；
   - 加/收紧梯度裁剪（`max_norm = 1.0`）；
   - 降低 Adam 的 β2（如 0.95），让二阶矩跟上梯度变化（上一节）；
   - 跳过引发问题的数据 batch。
5. 讲义提醒：当训练在第 10,000 步出问题时，你需要能判断是调度问题还是别的问题——关键就是把学习率当作一条需要监控的曲线，而不是一个配置项。
- 加分点：说出大模型训练中"spike → 回滚 → 跳过数据/降学习率"是常规操作。

### Q16 — 参考回答要点

| 调度 | 适合场景 | 依据 |
|------|---------|------|
| Warmup + Cosine | 长时间、大算力训练，Transformer/LLM 预训练和微调 | 讲义决策图："Large (days/weeks)"；Llama、GPT 的默认 |
| 1cycle | 小算力、几小时内的快速训练，需要先做 LR range test 找 lr_max | 讲义："Small (hours)，fastest convergence" |
| Cosine | 中等预算的安全默认值 | 讲义决策图 |
| Step decay | 沿用 CNN 经典配方（ResNet） | 有成熟的里程碑设置 |

- 不知道总步数时：讲义的建议是"常数学习率 + 手动衰减"（观察到验证 loss 平台期时手动降）。其他做法：
  - 基于指标的自动衰减（PyTorch 的 `ReduceLROnPlateau`，即讲义练习 5 的"schedule surgeon"思路）；
  - SGDR（带重启的余弦），每个周期都是完整的余弦，可以在任何周期末尾停止；
  - Warmup-Stable-Decay（WSD）：warmup 后长时间保持常数学习率，决定停止时再做一段短的衰减，适合持续训练。
- 加分点：说明 1cycle 和 cosine 都依赖总步数，提前停止时学习率还没降下来，模型通常不是最优状态。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 06 优化器](../../06-optimizers/docs/zh.md)：Adam 的偏差修正和二阶矩，是理解 warmup 动机的基础；训练循环中 `scheduler.step()` 的位置。
- [阶段 03 · 08 Weight 初始化和训练稳定性](../../08-weight-initialization/docs/zh.md)：初始化和 warmup 共同决定训练初期是否稳定；本节网络沿用了 Kaiming 初始化。
- [阶段 01 · 08 优化](../../../01-math-foundations/08-optimization/docs/zh.md)：梯度下降步长与收敛、发散的关系。
- [阶段 02 · 12 超参数调优](../../../02-ml-fundamentals/12-hyperparameter-tuning/docs/zh.md)：学习率搜索的方法论。

### 本节被哪些后续内容用到
- [阶段 03 · 10 构建您自己的迷你框架](../../10-mini-framework/docs/zh.md)：把调度器作为框架组件。
- [阶段 03 · 11 PyTorch 简介](../../11-intro-to-pytorch/docs/zh.md)：`torch.optim.lr_scheduler` 的使用。
- [阶段 03 · 13 调试神经网络](../../13-debugging-neural-networks/docs/zh.md)：学习率过大/过小导致的训练失败如何定位。
- [阶段 10 · 04 预训练 mini-GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：在语言模型预训练中使用 warmup。
- [阶段 10 · 06 指令微调 SFT](../../../10-llms-from-scratch/06-instruction-tuning-sft/docs/zh.md)：微调阶段的学习率选择。
- [阶段 19 · 44 Cosine LR + Warmup](../../../19-capstone-projects/44-cosine-lr-warmup/docs/zh.md)：本节调度在完整训练项目中的实现。
- [阶段 19 · 46 梯度累积](../../../19-capstone-projects/46-gradient-accumulation/docs/zh.md) 与 [阶段 19 · 47 检查点保存与恢复](../../../19-capstone-projects/47-checkpoint-save-resume/docs/zh.md)：调度器步数计算与状态恢复。

### 延伸关键词
`LR range test` · `SGDR（warm restarts）` · `ReduceLROnPlateau` · `线性缩放规则` · `Warmup-Stable-Decay (WSD)` · `inverse square root 调度` · `RAdam` · `Super-Convergence` · `OneCycleLR（div_factor / final_div_factor / pct_start）`
