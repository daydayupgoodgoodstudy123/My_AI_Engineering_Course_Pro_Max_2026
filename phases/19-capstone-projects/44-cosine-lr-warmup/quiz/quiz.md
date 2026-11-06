# 测验 · 带线性 Warmup 的余弦学习率（Cosine LR with Linear Warmup）

> **阶段 19 · 综合项目 · 第 44 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、[code/tests/test_schedule.py](../code/tests/test_schedule.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)（`tests/__init__.py` 与测试均并入该讲解）
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要 warmup | 训练最初的上千步权重接近初始化、Adam 的二阶矩估计还没稳定、梯度范数大且噪声大；此时直接用峰值学习率容易发散或陷入平台 |
| 2 | 三段式调度 | `[0, warmup]` 线性从 0 升到 `lr_max`；`(warmup, total]` 余弦从 `lr_max` 降到 `lr_min`；`> total` 钉在 `lr_min` |
| 3 | Warmup 公式 | `lr = lr_max * step / warmup_steps`；`warmup_steps = 0` 视为"不 warmup"，第 0 步直接是 `lr_max` |
| 4 | 余弦公式 | `lr = lr_min + (lr_max − lr_min) · 0.5 · (1 + cos(π · progress))`，`progress = (step − warmup) / max(1, total − warmup)` |
| 5 | 端点连续 | `progress = 0` 时 `cos 0 = 1` 得 `lr_max`，与 warmup 终点重合；`progress = 1` 时 `cos π = −1` 得 `lr_min`；单一闭式函数保证改参数后边界不错位 |
| 6 | 无状态调度 | `lr(step)` 只依赖 step 与 4 个配置值，任意时刻可重算、跨运行无浮点漂移；`global_step` 才是需要随 checkpoint 持久化的"调度轴" |
| 7 | 梯度范数与学习率并列记录 | 发散时梯度范数先于 loss 飙升；固定日志模式 `step, lr, grad_l2_norm, loss` |
| 8 | AdamW 的解耦权重衰减 | 衰减项 `p ← p − lr·wd·p` 与梯度更新分开，且同样乘当前 lr；惯例是对 bias、LayerNorm 增益不做衰减 |
| 9 | 生产经验 | `lr_max` 是最敏感的旋钮，先扫它；warmup 按总步数比例配置（典型 1–3%）；`lr_min` 刻意非零（如 `lr_max` 的 10%） |
| 10 | 替代调度 | 线性 warmup + 常数（消融基线）、线性 warmup + 反平方根衰减（早期 Transformer 常用），本节代码都已实现 |

### 核心技能（能动手做到）

- [ ] 不看代码写出 `CosineWithWarmup.lr(step)`，并能手算任意 step 的学习率（包括 warmup 终点、衰减中点、总步数之后）
- [ ] 解释 `TrainState.step` 中"清梯度 → 前向 → 反向 → 记录梯度范数 → 设置 lr → `optimizer.step()`"每一步的顺序为什么如此
- [ ] 计算拼接梯度向量的 L2 范数，并说出它与 `torch.nn.utils.clip_grad_norm_` 返回值的关系
- [ ] 把本节的 `lr(step)` 包进 `torch.optim.lr_scheduler.LambdaLR`，并验证两者逐步一致
- [ ] 识别调度相关的 off-by-one：第 0 步 lr 为 0、`total_steps` 与实际训练步数的关系
- [ ] 按参数类型划分 weight decay 参数组，并能指出按名字子串匹配的陷阱

---

## 二、基础自测（选择题）

**Q1.** 配置 `warmup_steps=10, total_steps=100, lr_max=1.0, lr_min=0.1`。`lr(55)` 等于多少？

- A. 0.55
- B. 0.5
- C. 0.6
- D. 0.1

**Q2.** 同一配置下，`lr(150)` 的行为是：

- A. 抛出 `ValueError`，因为超过了 `total_steps`
- B. 继续沿余弦曲线外推，回升到约 0.55
- C. 返回 0
- D. 返回 0.1（钉在 `lr_min`），调度不报错也不外推

**Q3.** 讲义强调余弦调度要写成"关于 step 的单一函数"，而不是三段胶水代码拼起来。最主要的理由是：

- A. 闭式表达式在 `warmup_steps` 与 `total_steps` 两个端点天然连续，改 `lr_max` 等配置时不会让某个边界错位
- B. 单一函数运行速度更快
- C. PyTorch 只接受单一函数作为调度器
- D. 三段式无法表示 `lr_min > 0`

**Q4.** 关于 `warmup_steps = 0`，本节代码的行为是：

- A. 构造时抛出 `ValueError`
- B. 第 0 步学习率为 `lr_max`，随即进入余弦衰减
- C. 第 0 步学习率为 0，第 1 步跳到 `lr_max`
- D. 第 0 步发生除以 0 错误

**Q5.** 在 `run_demo()` 中，`step=0` 与 `step=1` 两行打印的 `grad_l2` 和 `loss` 完全相同（都是 `1.008009` 与 `1.024962`）。原因是：

- A. 打印语句有 bug，重复打印了同一条记录
- B. 第 0 步梯度为 0，所以没有更新
- C. 第 0 步学习率为 0，AdamW 的梯度更新和解耦权重衰减都乘以 lr，权重完全没变，第 1 步看到的是同一组权重
- D. 第 0 步 `optimizer.step()` 没有被调用

**Q6.** 关于本节 `TrainState.step` 记录的 `grad_l2_norm`，说法正确的是：

- A. 它是 `optimizer.step()` 之后、用更新后权重算出的梯度范数
- B. 它是所有参数梯度拼接成一个长向量后的 L2 范数，在 `optimizer.step()` 之前计算
- C. 它是每个参数梯度范数的平均值
- D. 它已经经过梯度裁剪

**Q7.** 讲义"Use It"部分建议 warmup 以总步数的**比例**来配置。下列理由最贴切的是：

- A. 比例比整数更容易写进 YAML
- B. 绝对步数会导致除以 0
- C. 2,000 步 warmup 对 2 亿步的训练几乎等于没有 warmup，对 2 万步的训练却占了 10%；按比例（典型 1–3%）才能随训练时长缩放
- D. AdamW 要求 warmup 必须是总步数的 1%

**Q8.** 对于 `InverseSqrtWarmup(warmup_steps=4, lr_max=1.0)`，`lr(16)` 是多少？

- A. 0.5
- B. 0.25
- C. 1.0
- D. 0.0625

---

## 三、动手 / 代码题

**Q9.** 阅读 `split_decay_groups`：

```python
def split_decay_groups(
    model: nn.Module,
    weight_decay: float = 0.01,
    no_decay_names: tuple[str, ...] = ("bias", "LayerNorm.weight", "layer_norm.weight"),
) -> list[dict[str, object]]:
    decay_params: list[nn.Parameter] = []
    no_decay_params: list[nn.Parameter] = []
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if any(needle in name for needle in no_decay_names):
            no_decay_params.append(param)
        else:
            decay_params.append(param)
    ...
```

测试 `test_split_decay_separates_bias_and_layernorm` 用 `nn.Sequential(nn.LayerNorm(8), nn.Linear(8, 4))` 作模型，只断言两个组都非空，测试通过。

1. 写出这个模型的四个参数名，以及它们实际被分到哪一组。
2. 这个函数在这里有什么 bug？测试为什么没抓住？
3. 给出一个不依赖参数名的修正方案，并改写测试使它真正验证"LayerNorm 增益不衰减"。
4. `TrainState` 有没有用到 `split_decay_groups`？这意味着 demo 里实际发生了什么？

**Q10.** `run_demo()` 使用 `CosineWithWarmup(warmup_steps=4, total_steps=20, lr_max=1e-2, lr_min=1e-4)` 并训练 20 步，最后一行是 `step= 19 lr=0.000195`。

1. 训练中学习率是否到达过 `lr_min = 1e-4`？为什么？
2. 第 0 步的 lr 为 0，这一步对模型和 AdamW 内部状态各有什么影响？
3. 如果希望"N 步训练恰好在最后一步用到 `lr_min`"，以及"第一步就有非零学习率"，分别可以怎么改？各有什么代价？

**Q11.** 讲义练习 3 要求写一个测试：对 `[0, total_steps]` 中的每个 step，`|lr(step+1) − lr(step)|` 不超过 `lr_max / warmup_steps`。

1. 用 `warmup_steps=10, total_steps=12, lr_max=1.0, lr_min=0.0` 手算 `lr(10)`、`lr(11)`、`lr(12)`，检验这个上界是否总成立。
2. 推导一个对余弦段也成立的相邻步差上界，并写出修正后的测试断言。
3. 当 `warmup_steps = 0` 时原练习的上界还有意义吗？

**Q12.** 讲义练习 4：把调度接入 `torch.optim.lr_scheduler.LambdaLR`。请写出代码，并回答：`LambdaLR` 的 lambda 应该返回什么？`scheduler.step()` 应放在 `optimizer.step()` 之前还是之后？如何验证它和 `TrainState` 逐步等价？

---

## 四、面试高频题

**Q13.**（基础必考）大模型预训练为什么普遍使用"线性 warmup + 余弦衰减"？请分别说明 warmup 和衰减各解决什么问题。

**Q14.**（原理深挖）Warmup 与 Adam 类优化器之间有什么关系？为什么说训练初期 Adam 的"有效步长"不可信？

**Q15.**（工程实践）训练从 checkpoint 恢复后，学习率调度要怎么保证正确？如果中途想把训练延长一倍，应该怎么改？

**Q16.**（场景设计）一次训练在 warmup 结束后不久 loss 突然飙升甚至 NaN。你会看哪些日志、按什么顺序排查、可能怎么调整调度？

**Q17.**（追问型）AdamW 的 weight decay 和学习率调度如何相互作用？为什么 bias 和 LayerNorm 的参数通常不做 weight decay？

---

## 五、参考答案与解析

### Q1 — 答案：A

`progress = (55 − 10) / (100 − 10) = 0.5`，`cos(0.5π) = 0`，余弦因子 `0.5 · (1 + 0) = 0.5`，所以 `lr = 0.1 + (1.0 − 0.1) × 0.5 = 0.55`（已实际运行验证，`lr(55) = 0.55`）。规律：衰减段的中点学习率是 `(lr_max + lr_min) / 2`。B 忽略了 `lr_min`；C 是随手凑的；D 是终点值。

### Q2 — 答案：D

代码 `if step >= self.total_steps: return self.lr_min`，`lr(150) = 0.1`。讲义："the schedule does not error out and does not extrapolate; it pins at the floor"。A 不对，只有负 step 才抛错；B 是"把 cos 继续算下去"的错误实现（`progress > 1` 时余弦会回升）；C 混淆了 `lr_min` 与 0。

### Q3 — 答案：A

讲义："The continuity at both endpoints is not an accident… A glued schedule loses one boundary the first time `lr_max` is changed." 余弦段在 `progress = 0` 恰为 `lr_max`，与 warmup 段终点相同；在 `progress = 1` 恰为 `lr_min`，与地板值相同。B 不是关键考虑；C 错，PyTorch 有多种调度器；D 错，三段式同样可以表示。

### Q4 — 答案：B

`if self.warmup_steps > 0 and step <= self.warmup_steps` 在 `warmup_steps = 0` 时整体为假，直接走余弦段：`progress = 0 / total`，`lr = lr_max`。测试 `test_zero_warmup_starts_at_peak` 正是验证这一点。`__post_init__` 只拒绝负数 warmup，A 错；C、D 是没有处理 0 的天真实现才会出现的情况。

### Q5 — 答案：C

已实际验证：执行第 0 步后，所有参数与执行前 `torch.equal` 完全相等。AdamW 的更新是 `p ← p − lr·(m̂/(√v̂+ε))` 和 `p ← p − lr·wd·p`，两项都乘 lr，lr = 0 时权重不变。但 `optimizer.step()` 确实被调用了（D 错）：AdamW 的 `step` 计数变成 1，一阶矩 `m`、二阶矩 `v` 已经吸收了第 0 步的梯度。B 错，梯度范数是 1.008，不为 0；A 错，两条记录的 `step` 和 `lr` 不同。

### Q6 — 答案：B

`gradient_l2_norm` 把每个参数梯度的平方和累加，最后开方，等价于"拼接后的整体 L2 范数"：`sqrt(Σ_p ‖g_p‖²)`。它在 `loss.backward()` 之后、`optimizer.step()` 之前计算，反映的是当前权重处的梯度（A 错）。C 是另一种统计量；D 错，本节没有裁剪，裁剪是第 45 节的内容。这一数值与 `clip_grad_norm_` 返回的"裁剪前总范数"相同。

### Q7 — 答案：C

讲义原话："A 200-million-step run with 2,000 warmup steps starts at peak almost immediately; a 20,000-step run with the same number warms up for 10 percent. Configure warmup as a fraction (typical: 1-3 percent)." A、D 是无关或编造的理由；B 错，代码已处理 `warmup_steps = 0`。

### Q8 — 答案：A

`step = 16 > warmup = 4`，`lr = 1.0 × sqrt(4 / 16) = 0.5`（测试 `test_inverse_sqrt_warmup_decays` 同样断言 0.5）。B 是 `4/16`（忘了开方）；C 是 warmup 终点值；D 是 `(4/16)²`。

### Q9 — 参考答案

1. 实际运行 `named_parameters()` 得到：`0.weight`（LayerNorm 增益，形状 `[8]`）、`0.bias`、`1.weight`（形状 `[4, 8]`）、`1.bias`。分组结果：
   - 衰减组（wd = 0.01）：`0.weight`、`1.weight`
   - 不衰减组：`0.bias`、`1.bias`
2. **Bug**：`nn.Sequential` 里的参数名是数字前缀，名字里根本没有 `LayerNorm` 字样，所以 LayerNorm 增益 `0.weight` 被错误地分进了衰减组。子串规则只对 Hugging Face 风格、模块属性恰好叫 `LayerNorm` / `layer_norm` 的模型有效（比如属性叫 `ln_1`、`norm` 都会漏掉）。测试只断言"两组都非空"——仅凭两个 bias 就能让不衰减组非空，所以测试名说"separates bias and layernorm"，实际只验证了 bias。
3. 修正：按张量维度或模块类型判断。最常见的写法是"一维参数（bias、LayerNorm/RMSNorm 增益）不衰减，二维及以上（Linear、Embedding 权重）衰减"：

```python
def split_decay_groups(model, weight_decay=0.01):
    decay, no_decay = [], []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        (no_decay if p.ndim < 2 else decay).append(p)
    return [{"params": decay, "weight_decay": weight_decay},
            {"params": no_decay, "weight_decay": 0.0}]
```

   改写后的测试应断言具体成员：

```python
model = nn.Sequential(nn.LayerNorm(8), nn.Linear(8, 4))
groups = split_decay_groups(model)
no_decay_ids = {id(p) for g in groups if g["weight_decay"] == 0 for p in g["params"]}
self.assertIn(id(model[0].weight), no_decay_ids)      # LayerNorm 增益
self.assertNotIn(id(model[1].weight), no_decay_ids)   # Linear 权重
```

4. 没有。`TrainState.__init__` 直接把 `model.parameters()` 交给 `AdamW(weight_decay=0.01)`，所以 demo 中**所有参数（含 bias）都在衰减**。`split_decay_groups` 是一个写好但未接入的辅助函数，讲义"Build It"也没有提到它。

### Q10 — 参考答案

1. **没有到达**。循环 20 次，`global_step` 依次为 0…19；`lr(19) ≈ 0.000195`，而 `lr(20) = lr_min = 0.0001` 要到第 21 次更新才会用到。也就是说，按本节的约定，`total_steps` 是"lr 恰好等于 `lr_min` 的那个 step 编号"，完整走完调度需要 `total_steps + 1` 次更新。demo 的文本图画的是 `[0, 20]`，比实际训练多一个点。
2. 第 0 步：权重完全不变（Q5），但 AdamW 内部状态变化了——`step` 计数为 1，`m`、`v` 吸收了第 0 步的梯度，偏差修正也按 t = 1 计算。实际效果相当于"用一次前向反向预热了优化器的矩估计"，代价是浪费一次计算。
3. 两种常见改法：
   - **让最后一步用到 `lr_min`**：训练循环跑 `total_steps + 1` 次，或者把余弦分母改成 `total_steps − 1 − warmup_steps`（相应地 `step >= total_steps − 1` 时返回 `lr_min`）。代价是改变了"`total_steps` 的语义"，所有依赖它的测试、图表和 checkpoint 中的配置都要同步。
   - **第一步就非零**：warmup 段用 `lr_max * (step + 1) / warmup_steps`，demo 的 warmup 序列会从 `[0, 0.0025, 0.005, 0.0075]` 变成 `[0.0025, 0.005, 0.0075, 0.01]`（已计算）。代价是 `lr(0) == 0` 这条测试和讲义的"step zero is exactly zero"约定都要改。
   - 关键是：二者都是"约定"问题，选哪种都行，但要在 docstring、测试和配置里写死，这正是讲义说"schedules are easy to get wrong off by one"的原因。

### Q11 — 参考答案

1. 实际计算：`lr(10) = 1.0`，`lr(11) = 0.5`，`lr(12) = 0.0`。相邻差 0.5，而 `lr_max / warmup_steps = 0.1`，上界**不成立**。原因：衰减段只有 2 步，余弦从 1 降到 0 非常陡。练习中的上界只在衰减段比 warmup 段"更平缓"时成立（例如 `warmup=10, total=100` 时最大差恰为 0.1）。
2. 余弦段 `f(s) = lr_min + (lr_max − lr_min) · 0.5 · (1 + cos(π (s − w)/D))`，导数绝对值最大为 `(lr_max − lr_min) · π / (2D)`（`D = total − warmup`）。由中值定理，相邻两步之差不超过它。对应的测试：

```python
def test_schedule_is_lipschitz(self):
    s = CosineWithWarmup(warmup_steps=10, total_steps=12, lr_max=1.0, lr_min=0.0)
    D = s.total_steps - s.warmup_steps
    bound = max(s.lr_max / max(1, s.warmup_steps),
                (s.lr_max - s.lr_min) * math.pi / (2 * D))
    for step in range(s.total_steps + 1):
        self.assertLessEqual(abs(s.lr(step + 1) - s.lr(step)), bound + 1e-12)
```

   验证：`warmup=10, total=12` 时余弦段上界为 `π/4 ≈ 0.785 ≥ 0.5`；`warmup=100, total=110` 时实际最大差 0.1545，上界 `π/20 ≈ 0.157`，都成立。
3. 没有意义：`lr_max / 0` 直接除零；此时只有余弦段的上界有效。

### Q12 — 参考答案

```python
from torch.optim.lr_scheduler import LambdaLR

sched_cfg = CosineWithWarmup(warmup_steps=4, total_steps=20, lr_max=1e-2, lr_min=1e-4)
opt = torch.optim.AdamW(model.parameters(), lr=sched_cfg.lr_max,
                        betas=(0.9, 0.95), weight_decay=0.01)
scheduler = LambdaLR(opt, lr_lambda=lambda step: sched_cfg.lr(step) / sched_cfg.lr_max)

for _ in range(20):
    opt.zero_grad(set_to_none=True)
    loss = nn.functional.mse_loss(model(x), y)
    loss.backward()
    opt.step()
    scheduler.step()          # 在 optimizer.step() 之后
```

- `LambdaLR` 把 `lr = base_lr × lambda(step)`，所以 lambda 要返回**乘数** `lr(step) / lr_max`，并把优化器的初始 lr 设成 `lr_max`。构造 `LambdaLR` 时就会立刻把 lr 设为 `base_lr × lambda(0) = 0`。
- `scheduler.step()` 放在 `optimizer.step()` 之后（PyTorch 1.1 起的约定，顺序反了会跳过调度的第一个值，并给出警告）。
- 验证：已实际运行——每步记录 `opt.param_groups[0]["lr"]`，与 `sched_cfg.lr(i)` 逐步相等；20 步后两种写法的模型参数 `torch.allclose` 全部为真，最后一步 loss 都是 `0.185674`。
- 包装器改变了什么：调度器自己维护 `last_epoch` 计数并进入 `state_dict()`，可以和优化器一起存进 checkpoint；缺点是 lr 被表达成"乘数"，不同 param group 的 base_lr 不同时乘数语义更合适，而本节的"绝对 lr"写法会把所有组设成同一个值（`set_lr` 遍历所有 group 赋同一个数）。

### Q13 — 参考回答要点

- **Warmup 解决"开头太猛"**：讲义："The first thousand training updates are the loudest"——权重接近随机初始化，梯度范数大、噪声大；Adam 的二阶矩估计尚未稳定。此时用峰值 lr 要么发散，要么落进"再也逃不出来的 loss 平台"。线性从 0 升到 `lr_max` 让早期有效步长很小。
- **衰减解决"结尾太粗"**：训练后期需要更小的步长让参数在低 loss 区域精细收敛，减少噪声带来的震荡。余弦曲线开头和结尾都很平、中间下降，过渡平滑，没有阶梯式调度的突变。
- **`lr_min` 非零**：讲义建议约为 `lr_max` 的 10%，"A `lr_min = 0` schedule produces a training curve that looks great on a plot and a model that has not actually finished training"。
- 加分点：提到 SGDR（Loshchilov & Hutter）是余弦调度的参考论文、AdamW 来自同一作者的解耦权重衰减论文；能写出闭式公式并说明两个端点的连续性。
- 常见误区：认为 warmup 只是"慢启动的经验技巧"而说不出与梯度噪声、优化器统计量的关系。

### Q14 — 参考回答要点

- Adam 的更新量约为 `lr · m̂ / (√v̂ + ε)`，归一化后每个坐标的步长量级约等于 lr，**与梯度大小无关**。所以即使梯度很小，早期每一步也会移动约 lr 的距离。
- 训练初期 `v`（梯度平方的滑动平均）只基于很少的样本，偏差修正后方差很大；某些坐标 `v̂` 偶然偏小，就会产生过大的更新。讲义："The optimizer's running second-moment estimate has not stabilised."
- Warmup 用小 lr 压住这段不可靠期的实际位移，等 `v` 积累足够统计量后再放大步长。
- 本节 betas 取 `(0.9, 0.95)`：β₂ = 0.95 比默认 0.999 更"短记忆"，二阶矩反应更快，是大模型训练中常见的选择（可作加分点，说明 β₂ 也影响需要的 warmup 长度）。
- 加分点：能结合本节 demo 说明 lr = 0 的第 0 步虽然不动权重，但已经在更新 `m`、`v`。

### Q15 — 参考回答要点

- **调度轴必须是持久化的 `global_step`**：讲义："The schedule reads `global_step` from the trainer's checkpoint, not from a local counter." 本节 `TrainState` 拥有 `global_step`，恢复时必须一起恢复，否则会重新 warmup。
- 因为 `lr(step)` 是无状态函数，只要 `global_step` 和 4 个配置值正确，恢复后的学习率与不中断时完全一致；若用 `LambdaLR`，还要保存/加载 scheduler 的 `state_dict`（见第 47 节）。
- **延长训练**：讲义："Trainers that need to extend training change the schedule's `total_steps`, not the loop." 但要意识到：修改 `total_steps` 会让当前 step 对应的 lr 跳变（已计算：`warmup=10, lr_max=1.0, lr_min=0.1` 时，第 78 步在 `total=100` 下 lr ≈ 0.226，把 `total` 改成 190 后同一步变成 ≈ 0.719），需要评估这次跳变；常见做法是从当前 lr 开始接一段新的衰减，或者事先采用"warmup–平台–衰减"类可延长的调度。
- 配置放在提交到 git 的 YAML/JSON 中，恢复时校验配置未改变（第 47 节会把配置写进 checkpoint）。
- 常见误区：用"epoch × 每 epoch 步数"推算 step，数据分片或 dataloader 重启后就错位。

### Q16 — 参考回答要点

- **先看日志**：`step, lr, grad_l2_norm, loss` 四列。讲义："A divergent training run shows the gradient norm spike before the loss does… a too-aggressive peak shows up as a norm that stays high after warmup."
- **排查顺序**：
  1. 确认调度本身正确：画出 lr 曲线（文本图或 CSV），检查 warmup 终点值、峰值是否符合配置（off-by-one、单位错误如 `3e-3` 写成 `3e-2`）。
  2. 看梯度范数：是否在 lr 接近峰值时持续升高或出现尖峰。
  3. 排除数据问题：定位尖峰对应的 batch，是否有异常长、重复或损坏的样本。
  4. 排除数值问题：混合精度下的溢出（第 45 节）。
- **调整**：降低 `lr_max`（最敏感的旋钮）、延长 warmup 比例、加梯度裁剪（第 45 节）、必要时从尖峰前的 checkpoint 恢复并跳过问题数据。
- 加分点：给梯度范数加 EWMA 平滑（本节已有 `EWMA` 类）后设置告警阈值，比肉眼看原始曲线可靠。

### Q17 — 参考回答要点

- **AdamW 是解耦衰减**：参数先按 `p ← p − lr·wd·p` 收缩，再用 Adam 的归一化梯度更新；衰减不进入 `m`、`v`。（原始 Adam + L2 正则会把 `wd·p` 加进梯度，再被 `√v̂` 缩放，效果被扭曲，这是 AdamW 论文的动机。）
- **与调度的交互**：PyTorch 实现中衰减量正比于当前 lr，所以 warmup 期间衰减也很弱，第 0 步 lr = 0 时完全没有衰减；余弦后期衰减随 lr 一起减弱。有效的"每步收缩比例"是 `lr · wd`。
- **为什么 bias、LayerNorm 不衰减**：它们参数量很小、几乎不贡献过拟合；LayerNorm 增益被拉向 0 会直接削弱该层输出的尺度，伤害表达能力；bias 衰减也没有正则化意义。惯例是只衰减二维权重矩阵（Linear、Embedding）。
- 结合本节代码：`split_decay_groups` 想实现这一点，但按名字子串匹配，在 `nn.Sequential` 上会漏掉 LayerNorm 增益（Q9）；而 `TrainState` 根本没接入它，demo 中所有参数都被衰减。
- 常见误区：以为 `weight_decay=0.01` 表示每步缩小 1%——实际每步缩小 `lr × 0.01`，在 `lr = 1e-2` 时只有 0.01%。

---

## 六、关联知识点

### 前置知识
- [阶段 03 · 06 Optimizers](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：SGD、Momentum、Adam、AdamW 的更新公式，理解本节 AdamW 的一阶/二阶矩。
- [阶段 03 · 09 Learning Rate Schedules 和 Warmup](../../../03-deep-learning-core/09-learning-rate-schedules/docs/zh.md)：学习率调度的基础与各类调度的比较。
- [阶段 03 · 07 正则化](../../../03-deep-learning-core/07-regularization/docs/zh.md)：weight decay 与 L2 正则的关系。
- [阶段 19 · 36 训练循环与 Evaluation](../../36-training-loop-eval/docs/zh.md)：本节的 `TrainState.step` 是在那个训练循环上加入调度与日志。
- [阶段 10 · 04 预训练 Mini GPT](../../../10-llms-from-scratch/04-pre-training-mini-gpt/docs/zh.md)：讲义提到预训练配方 Adam + warmup + cosine。

### 本节被哪些后续内容用到
- [阶段 19 · 45 Gradient Clipping 与 Mixed Precision](../../45-gradient-clipping-amp/docs/zh.md)：训练循环的下一层，梯度范数从"记录"变成"裁剪"。
- [阶段 19 · 46 Gradient Accumulation](../../46-gradient-accumulation/docs/zh.md)：累积时调度按"优化器步"而不是 micro-batch 推进。
- [阶段 19 · 47 Checkpoint 保存与恢复](../../47-checkpoint-save-resume/docs/zh.md)：保存 `global_step` 与调度器状态，保证恢复后学习率连续。
- [阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../48-distributed-fsdp-ddp/docs/zh.md)、[阶段 19 · 81 端到端分布式训练](../../81-end-to-end-distributed-train/docs/zh.md)：分布式训练沿用同一调度。
- [阶段 03 · 13 调试神经网络](../../../03-deep-learning-core/13-debugging-neural-networks/docs/zh.md)：用 lr 与梯度范数日志诊断训练问题。

### 延伸关键词
`linear warmup` · `cosine annealing` · `SGDR / warm restarts` · `inverse square root schedule` · `AdamW decoupled weight decay` · `LambdaLR` · `global_step` · `gradient L2 norm` · `EWMA` · `no-decay parameter groups` · `lr sweep`
