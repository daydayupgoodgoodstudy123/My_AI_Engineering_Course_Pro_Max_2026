# 测验 · Gradient Clipping（梯度裁剪）与 Mixed Precision（混合精度）（Gradient Clipping and Mixed Precision）

> **阶段 19 · 综合项目 · 第 45 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)、[code/tests/test_amp.py](../code/tests/test_amp.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)（`tests/__init__.py` 与测试均并入该讲解）
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么要裁剪 | 单个坏 batch 能让梯度范数暴涨几个数量级（讲义例子：4,200，是此前峰值的 20 倍），一步更新就能毁掉之前的训练成果 |
| 2 | 全局 L2 范数裁剪 | 把所有参数梯度拼成一个向量求 L2 范数 `‖g‖`；若 `‖g‖ > max_norm`，全部梯度乘以 `max_norm/‖g‖`，**方向不变、只缩长度**；LLM 训练的常用默认值 `max_norm = 1.0` |
| 3 | 记录裁剪前后两个范数 | 只看裁剪后的范数永远 ≤ `max_norm`，看不出"每一步都在裁剪"这种异常；裁剪前范数才是训练健康信号 |
| 4 | autocast | `torch.amp.autocast(device_type, dtype)` 只让矩阵乘等"适合低精度"的算子用 FP16/BF16，`mse_loss` 等对精度敏感的算子仍用 FP32 |
| 5 | FP16 与 BF16 | FP16 最大值 65,504、指数范围窄，容易上溢/下溢；BF16 指数位与 FP32 相同（最大约 3.39e38），但尾数只有 7 位、精度低；BF16 一般不需要 loss scaling |
| 6 | GradScaler | 反向前把 loss 乘以缩放因子（默认初值 65,536），优化器 step 前再除回去；发现 Inf/NaN 就跳过本步并把因子减半，连续 2,000 步干净则翻倍 |
| 7 | 正确的调用顺序 | `scaler.scale(loss).backward()` → `scaler.unscale_(optimizer)` → `clip_grad_norm_` → `scaler.step(optimizer)` → `scaler.update()`；先 unscale 再裁剪，阈值才作用在真实梯度上 |
| 8 | 两处非有限值检测 | 反向前检查 loss（`torch.isfinite`），unscale 后检查梯度；任一失败都跳过本步并记录原因 |
| 9 | 跳过率是告警而非日志 | 偶尔跳过是健康的；讲义建议 1,000 步滚动跳过率超过 5% 就告警 |
| 10 | 固定 CSV 模式 | `step, lr, grad_l2_pre_clip, grad_l2_post_clip, loss, skipped, skip_reason, scaler_scale` 放在一行，避免多文件对不齐 |

### 核心技能（能动手做到）

- [ ] 手写全局 L2 范数与原地裁剪，并能手算 `[6, 8]` 在 `max_norm=1` 下裁剪后的值
- [ ] 正确写出 autocast + GradScaler + 梯度裁剪的五步顺序，并解释每一步颠倒后会出什么问题
- [ ] 在 CPU 上打开 `GradScaler` 观察缩放因子在跳过步后减半，读懂日志中"跳过步记录的是更新前的 scale"
- [ ] 区分 FP16 与 BF16 的数值范围，判断某个 loss/梯度规模在哪种精度下会溢出
- [ ] 识别"传入生成器导致只算范数不裁剪"这类 API 陷阱
- [ ] 计算滚动跳过率，并设计一个基于它的告警/中止策略

---

## 二、基础自测（选择题）

**Q1.** 使用 `GradScaler` 和梯度裁剪时，下列哪个顺序是正确的？

- A. `scaler.scale(loss).backward()` → `clip_grad_norm_` → `scaler.unscale_(opt)` → `scaler.step(opt)` → `scaler.update()`
- B. `loss.backward()` → `scaler.unscale_(opt)` → `clip_grad_norm_` → `scaler.step(opt)`
- C. `scaler.scale(loss).backward()` → `scaler.step(opt)` → `clip_grad_norm_` → `scaler.update()`
- D. `scaler.scale(loss).backward()` → `scaler.unscale_(opt)` → `clip_grad_norm_` → `scaler.step(opt)` → `scaler.update()`

**Q2.** 一个参数的梯度为 `[6.0, 8.0]`，`max_norm = 1.0`。调用本节 `clip_global_l2_norm` 后：

- A. 返回 `(10.0, 1.0)`，梯度变为约 `[0.6, 0.8]`，方向不变
- B. 返回 `(10.0, 10.0)`，梯度不变
- C. 返回 `(10.0, 1.0)`，梯度变为 `[1.0, 1.0]`
- D. 返回 `(1.0, 1.0)`，梯度变为 `[0.6, 0.8]`

**Q3.** 运行 `run_demo()`，每一行的 `scale=` 都是 `1.0`，包括第 5 步的 SKIP 之后。原因是：

- A. 缩放因子每 2,000 步才变化一次，20 步内看不到变化
- B. `scaler.update()` 在跳过路径上没有被调用
- C. `AmpTrainState` 只在 `device_type == "cuda"` 时启用 GradScaler，CPU 上 `enabled=False`，缩放因子恒为 1.0
- D. CPU 不支持浮点 Inf，所以不会真正跳过

**Q4.** 关于 FP16 与 BF16，说法正确的是：

- A. BF16 的尾数位比 FP16 多，所以精度更高
- B. BF16 与 FP32 的指数位相同，数值范围约到 3.39e38；FP16 最大只有 65,504，因此 FP16 训练通常需要 loss scaling
- C. 两者数值范围相同，只是存储格式不同
- D. BF16 必须配合 GradScaler 才能训练

**Q5.** demo 中第 5 步被跳过（`loss=0.448445`），第 6 步的 loss 同样是 `0.448445`。这说明：

- A. 跳过步没有调用 `optimizer.step()`，权重没有变化，第 6 步在相同权重和相同 batch 上计算出相同的 loss
- B. loss 打印有缓存，没有重新计算
- C. 第 6 步也被跳过了
- D. GradScaler 把第 5 步的梯度延迟到第 6 步再应用

**Q6.** 在 `AmpTrainState.step` 中，当 loss 本身非有限（`non_finite_loss`）时，代码**不**调用 `scaler.update()`。原因是：

- A. 为了让缩放因子保持不变，方便调试
- B. 讲义要求跳过时不更新缩放因子
- C. CPU 上 `update()` 会抛异常
- D. 这一步没有执行 `scaler.scale(loss).backward()` 和 `unscale_`，没有记录任何 inf 检查，此时调用 `update()` 违反 GradScaler 要求的调用顺序（启用时会断言失败）

**Q7.** `torch.amp.GradScaler` 的默认参数（已在本环境读取）是：

- A. 初始缩放 1.0，每步翻倍
- B. 初始缩放 65,536，遇到 Inf/NaN 乘 0.5，连续 2,000 步无溢出乘 2.0
- C. 初始缩放 2^18，遇到 Inf/NaN 归零
- D. 初始缩放 65,504，遇到 Inf/NaN 减 1

**Q8.** 20 步日志中只有第 5 步被跳过。`rolling_skip_rate(log, window=10)` 在第 5 步和第 9 步的值分别是多少？

- A. 0.1 和 0.1
- B. 1.0 和 0.1
- C. 约 0.1667 和 0.1
- D. 0.05 和 0.05

---

## 三、动手 / 代码题

**Q9.** 阅读 `clip_global_l2_norm`：

```python
def compute_global_l2_norm(parameters):
    squared_sum = 0.0
    for param in parameters:
        if param.grad is None:
            continue
        squared_sum += float(param.grad.detach().pow(2).sum().item())
    return math.sqrt(squared_sum)


def clip_global_l2_norm(parameters: list[torch.nn.Parameter], max_norm: float):
    if max_norm <= 0:
        raise ValueError("max_norm must be positive")
    pre_clip = compute_global_l2_norm(parameters)
    if not math.isfinite(pre_clip):
        return pre_clip, pre_clip
    if pre_clip <= max_norm:
        return pre_clip, pre_clip
    scale = max_norm / (pre_clip + 1e-12)
    for param in parameters:
        if param.grad is not None:
            param.grad.detach().mul_(scale)
    return pre_clip, max_norm
```

1. 如果调用方写成 `clip_global_l2_norm(model.parameters(), 0.1)`（传入生成器而不是列表），会发生什么？返回值会"说谎"吗？
2. `AmpTrainState.step` 为什么写成 `clip_global_l2_norm(list(self.model.parameters()), self.max_norm)`？
3. 如何修改函数，使它对任何可迭代对象都安全？

**Q10.** 讲义练习 1 说"把一个 batch 的 target 乘以 1e8，验证跳过路径会被触发"；练习 2 说"切换到 BF16 后，同一个 demo 的跳过率应降为 0"。

1. 在默认配置（CPU、BF16 autocast）下执行 `state.step(x, y * 1e8)`，你预期是 SKIP 还是 STEP？loss 是否有限？
2. 改成 `amp_dtype=torch.float16` 再执行一次呢？
3. demo 中第 5 步的 SKIP 在 BF16 下会消失吗？请据此评价练习 2 的说法。

**Q11.** 在 CPU 上手动打开 GradScaler：

```python
model, x, y = build_toy_model()
st = AmpTrainState(model, lr=1e-2, max_norm=1.0, device_type="cpu")
st.scaler = torch.amp.GradScaler("cpu", enabled=True)
for i in range(8):
    corrupt = inject_inf_into_first_grad if i in (3, 5) else None
    r = st.step(x, y, gradient_corruptor=corrupt)
    print(r.step, r.skipped, r.scaler_scale)
```

写出 8 行输出中 `skipped` 和 `scaler_scale` 两列，并解释：为什么第 3 步（SKIP）记录的 scale 仍是 65,536，而第 4 步才变成 32,768？这种记录方式和正常步有什么不一致？

**Q12.** 讲义说 `clip_global_l2_norm` 是"a wrapper around `torch.nn.utils.clip_grad_norm_`"，代码的 docstring 也这么写。

1. 实际代码调用了 `clip_grad_norm_` 吗？
2. 用 `clip_grad_norm_` 重写这个函数，保持 `(pre_clip, post_clip)` 的返回约定。
3. 在 toy 模型上对 `max_norm=0.1` 分别用两种实现裁剪，裁剪后的实际范数会有什么微小差别？原因是什么？

---

## 四、面试高频题

**Q13.**（基础必考）什么是梯度裁剪？按全局范数裁剪和按值裁剪（clip by value）有什么区别？LLM 训练为什么通常选全局范数 1.0？

**Q14.**（原理深挖）混合精度训练为什么需要 loss scaling？动态 loss scaling 是怎么工作的？为什么 BF16 一般不需要它？

**Q15.**（工程实践）请写出 PyTorch 中 AMP + 梯度裁剪的标准训练步，并说明：为什么必须先 `unscale_` 再裁剪？跳过步为什么也要调用 `scaler.update()`？

**Q16.**（场景设计）一次 FP16 训练中，你发现 `scaler_scale` 在 2^10 到 2^16 之间反复振荡，跳过率 8%。你会如何诊断和处理？

**Q17.**（追问型）如果日志显示几乎每一步都在裁剪（`pre_clip` 长期远大于 `max_norm`），这意味着什么？在 Adam 优化器下，"每步都裁剪"和"从不裁剪"的效果差别大吗？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："The right order is: `scaler.scale(loss).backward()`, then `scaler.unscale_(optimizer)`, then `clip_grad_norm_`, then `scaler.step(optimizer)`, then `scaler.update()`. Any other order produces a silently broken loop." A 在缩放后的梯度上裁剪，阈值实际被放大了 scale 倍（scale = 65,536 时等于没裁剪）；B 没有 `scaler.scale`，unscale 会把梯度错误地再除一次 scale，且漏了 `update()`；C 先 step 后裁剪，裁剪对本步更新毫无作用。

### Q2 — 答案：A

`‖[6, 8]‖ = 10 > 1`，缩放系数 `1/(10 + 1e-12) ≈ 0.1`，梯度变为约 `[0.6, 0.8]`，范数 1、方向不变；函数返回 `(pre_clip, max_norm) = (10.0, 1.0)`（测试 `test_clip_scales_gradients_above_max_norm` 验证）。B 是未超阈值时的行为；C 是逐元素截断（clip by value 的思路），改变了方向；D 把 pre_clip 写错了。

### Q3 — 答案：C

`scaler_enabled = device_type == "cuda"`，CPU 上 `GradScaler(..., enabled=False)`：`scale()` 原样返回 loss、`unscale_` 和 `update()` 都是空操作、`get_scale()` 恒返回 1.0。讲义说 CPU 上 GradScaler 是"stub"，实际是代码主动禁用。A 混淆了"增长间隔"——减半是立即发生的，若启用则跳过后下一步就会变成 32,768（见 Q11）。B 错，非有限梯度路径调用了 `update()`。D 错，CPU 完全支持 Inf。

### Q4 — 答案：B

本环境实测：`torch.finfo(torch.float16).max = 65504`、`torch.finfo(torch.bfloat16).max ≈ 3.39e38`；`torch.tensor(70000.).half()` 得到 `inf`，`torch.tensor(1e-8).half()` 下溢为 0，而 BF16 仍能表示 `1.0012e-08`。代价是精度：BF16 的 eps 为 0.0078，FP16 为 0.00098。A 说反了；C 错；D 错，讲义："BF16 has a wider exponent range than FP16 and rarely needs loss scaling"。

### Q5 — 答案：A

跳过路径在 `has_non_finite_grad` 为真时直接返回，不调用 `scaler.step(optimizer)`，所以权重和 AdamW 的矩估计都不变；第 6 步在同一 batch 上前向，loss 必然相同。注意第 5 步打印的 loss 是**前向时**算出来的 0.448445（梯度是被人为注入的 Inf，loss 本身正常）。D 错，GradScaler 不会延迟应用梯度，被跳过的梯度直接丢弃。

### Q6 — 答案：D

代码注释原文："we never called `scaler.scale(loss).backward()` for this step, so calling update() here would violate GradScaler's required call ordering."——`update()` 依赖 `unscale_`（或 `step`）记录的 `found_inf`，没有记录时启用状态下会断言失败（已实测：已有过正常迭代时报 `AssertionError: No inf checks were recorded prior to update.`；全新 scaler 上直接 `update()` 则报 `Attempted update but _scale is None`）。这与讲义"`scaler.update()` runs every step, even on skip"的说法不完全一致：讲义的原则只适用于"梯度非有限"的跳过路径。A、B 不是原因；C 错，CPU 上禁用时 `update()` 是空操作，不会抛异常。

### Q7 — 答案：B

本环境读取 `torch.amp.GradScaler("cpu")` 的内部字段：`_init_scale = 65536.0`（2^16）、`_growth_factor = 2.0`、`_backoff_factor = 0.5`、`_growth_interval = 2000`。D 的 65,504 是 FP16 最大值，不要与 65,536 混淆。讲义说健康运行中缩放因子会"climbing in powers of two until it saturates near 2^17 or 2^18"，这里的增长需要连续 2,000 个干净步才发生一次。

### Q8 — 答案：C

已实际计算。第 5 步时窗口内有 6 条记录（0–5），其中 1 条跳过：`1/6 ≈ 0.1667`；第 9 步窗口内 10 条（0–9）：`1/10 = 0.1`；第 15 步窗口变成 6–15，跳过的第 5 步滑出，降为 0。A 忽略了窗口未满时分母是实际条数；B 是只看当前步；D 是全局跳过率 1/20。

### Q9 — 参考答案

1. **会"说谎"**。`model.parameters()` 是生成器，`compute_global_l2_norm` 遍历一次就耗尽了；后面的 `for param in parameters` 一次都不执行，梯度**没有被裁剪**，但函数仍返回 `(pre_clip, max_norm)`。已实际运行：传入生成器时返回 `(1.0080, 0.1)`，而裁剪后实际范数仍是 `1.0080`；传入列表时实际范数变为 `0.1000`。
2. 正是为了规避上面的问题——类型注解写的是 `list[torch.nn.Parameter]`，`AmpTrainState` 在调用前用 `list(...)` 物化了。但类型注解在运行时不强制，测试也没覆盖生成器输入。
3. 在函数开头物化，并顺便让 `post_clip` 成为实测值而不是"声明值"：

```python
def clip_global_l2_norm(parameters, max_norm):
    if max_norm <= 0:
        raise ValueError("max_norm must be positive")
    params = [p for p in parameters if p.grad is not None]   # 物化一次
    pre_clip = compute_global_l2_norm(params)
    if not math.isfinite(pre_clip) or pre_clip <= max_norm:
        return pre_clip, pre_clip
    scale = max_norm / (pre_clip + 1e-12)
    for p in params:
        p.grad.detach().mul_(scale)
    return pre_clip, compute_global_l2_norm(params)          # 实测裁剪后的范数
```

   顺带一提：`torch.nn.utils.clip_grad_norm_` 自己也会先把参数物化成列表，所以它对生成器是安全的。

### Q10 — 参考答案

已实际运行（同一 toy 模型，第一步）：

1. **BF16（默认）：STEP，不跳过**。loss ≈ `9.79e15`（MSE 在 autocast 下以 FP32 计算，远小于 FP32 上限），反向梯度在 BF16 下也不溢出，`pre_clip ≈ 9.67e7`，被裁剪到 `post_clip = 1.0`。也就是说，这种"损失尖峰"在默认配置下是由**梯度裁剪**兜住的，而不是跳过路径。
2. **FP16：SKIP，原因 `non_finite_grad`**。loss 仍是有限的 FP32 值，但反向传播中 FP16 中间梯度超过 65,504 溢出为 Inf，unscale 后被检测到而跳过。
3. **不会消失**。demo 的第 5 步是 `inject_inf_into_first_grad` 人为写入的 Inf，与精度无关，换成 BF16 照样跳过。何况 CPU 上默认已经是 BF16（`amp_dtype` 为 None 时 CPU 选 `torch.bfloat16`），所谓"添加 `--bf16` 模式"在 CPU 上没有可比较的对象。练习 2 的合理版本是：在 FP16 与 BF16 下分别跑"target 乘 1e8"的真实尖峰，比较跳过率——FP16 会跳过、BF16 不会。

### Q11 — 参考答案

实际运行输出（`step skipped scale`）：

```text
0 False 65536.0
1 False 65536.0
2 False 65536.0
3 True  65536.0
4 False 32768.0
5 True  32768.0
6 False 16384.0
7 False 16384.0
```

- 第 3 步注入 Inf → `unscale_` 记录 found_inf → `has_non_finite_grad` 为真 → 代码先 `scale_before = get_scale()`（65,536）再调用 `update()`（减半为 32,768），**日志写的是更新前的值**。第 4 步是正常步，日志写的是 `update()` 之后的值（仍为 32,768，因为一次干净步不足以翻倍）。
- 第 5 步再次减半，第 6 步看到 16,384。2,000 步的增长间隔意味着 8 步内不会翻倍。
- **不一致**：跳过步记录"更新前"、正常步记录"更新后"、非有限 loss 路径记录"未更新"。在 CSV 里读 `scaler_scale` 时，跳过行与下一行之间的减半看起来像是"下一步才减半"。建议统一记录 `update()` 之后的值，或者同时记录 `scale_before` 与 `scale_after` 两列。
- 另外，loss 列也印证了跳过不更新权重：第 3、4 步 loss 都是 0.626274，第 5、6 步都是 0.530047。

### Q12 — 参考答案

1. **没有**。函数手动计算范数并 `mul_`，只是行为上模仿 `clip_grad_norm_`。讲义"Build It"和 docstring 的描述与实现不符。
2. 重写：

```python
def clip_global_l2_norm(parameters, max_norm):
    if max_norm <= 0:
        raise ValueError("max_norm must be positive")
    params = list(parameters)
    pre = float(torch.nn.utils.clip_grad_norm_(params, max_norm, norm_type=2.0))
    if not math.isfinite(pre) or pre <= max_norm:
        return pre, pre
    return pre, compute_global_l2_norm(params)
```

   注意 `clip_grad_norm_` 遇到非有限范数时默认（`error_if_nonfinite=False`）仍会把梯度乘以 `max_norm/(inf+1e-6) = 0`，已实测：梯度 `[1, inf, 2]` 被改写成 `[0, nan, 0]`、返回值为 `inf`。所以本节"先检测非有限再裁剪"的顺序依然必要。
3. 已实际运行（`max_norm=0.1`）：手写版裁剪后范数 `0.10000000005`，`clip_grad_norm_` 版 `0.09999992`，后者返回的总范数 `1.0080090761`（float32 张量）、手写版 `1.0080091253`（Python float64 累加）。差异来自：`clip_grad_norm_` 的系数是 `max_norm / (total_norm + 1e-6)`，而手写版的 eps 是 `1e-12`；以及前者在 float32 上计算范数。实际训练中这种差别可以忽略，但写测试时用 `assertAlmostEqual(..., places=6)` 而不是精确相等。

### Q13 — 参考回答要点

- **定义**：反向之后、优化器更新之前，限制梯度的大小，防止单步更新过大。讲义例子：某个 batch 梯度范数 4,200，是平时峰值的 20 倍，不裁剪会"reset every learning the model had done in the previous hour"。
- **按全局范数**：把所有参数梯度视为一个向量，超阈值时统一按比例缩小，**保持梯度方向**，只限制步长。本节 `clip_global_l2_norm` 和 `torch.nn.utils.clip_grad_norm_` 都是这种。
- **按值裁剪**：每个分量独立截断到 `[-c, c]`，会改变方向，对大模型很少用。
- **按参数裁剪**（per-parameter norm）：每个张量各自裁剪，会改变层与层之间的相对比例。
- **为什么 1.0**：讲义："`max_norm = 1.0` is the modern default for language-model training"，需在小模型上扫一遍；阈值越大越能从"真正难的 batch"中学习，越小越能限制最坏情况但 loss 曲线更噪。
- 加分点：一定要同时记录裁剪前范数；Pascanu 等人关于 RNN 训练困难的论文是梯度裁剪的经典参考。

### Q14 — 参考回答要点

- **问题**：FP16 指数范围窄（最大 65,504，最小正规数约 6.1e-5）。反向传播中很多梯度非常小，会下溢成 0；偶尔也会上溢成 Inf。
- **loss scaling**：反向前把 loss 乘以一个大数 S，由链式法则所有梯度都放大 S 倍，把小梯度"抬"进 FP16 可表示范围；更新前再除以 S 还原。（Micikevicius 等人的 Mixed Precision Training 论文提出。）
- **动态缩放**：S 太大会上溢，太小会下溢，所以自动调节——出现 Inf/NaN 就跳过本步并 `S × 0.5`；连续 `growth_interval`（默认 2,000）步无溢出就 `S × 2`。默认初值 65,536。
- **BF16 为何不需要**：BF16 有 8 位指数，与 FP32 相同的范围，小梯度不会下溢、大梯度不容易上溢；代价是只有 7 位尾数，精度低，但训练对此相对鲁棒。本节在 CPU 上默认用 BF16 并禁用 GradScaler 正是这个道理。
- 加分点：autocast 不是把所有东西都转低精度——矩阵乘用低精度，loss、softmax、归一化等仍用 FP32（本节实测：BF16 autocast 下 Linear 输出为 `bfloat16`，`mse_loss` 输出为 `float32`）；主权重始终保存在 FP32。

### Q15 — 参考回答要点

```python
optimizer.zero_grad(set_to_none=True)
with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
    loss = loss_fn(model(x), y)
if not torch.isfinite(loss):
    skip(); continue                        # 不进 backward
scaler.scale(loss).backward()
scaler.unscale_(optimizer)                  # 梯度回到真实尺度
grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
scaler.step(optimizer)                      # 内部发现 inf 会自动跳过
scaler.update()                             # 每次 backward 后都要调用
```

- **先 unscale 再裁剪**：未 unscale 时梯度是真实值的 S 倍（如 65,536 倍），用 1.0 作阈值等于把所有梯度都压成极小的范数，或者反过来让阈值失去意义；而且 S 在变化，阈值语义也跟着变。
- **跳过步也要 `update()`**：减半缩放因子就发生在 `update()` 里。讲义："Forgetting `update()` on the skip path is the bug that produces 'the scaling factor never changed.'" 本节代码在梯度非有限路径上调用了它。
- **例外**：loss 本身非有限时还没 `backward`/`unscale_`，此时调用 `update()` 会违反调用顺序，本节选择不调用（见 Q6）。
- 加分点：`scaler.step` 自己就会在发现 inf 时跳过 `optimizer.step()`；本节额外用 `has_non_finite_grad` 显式判断，是为了记录跳过原因与日志。

### Q16 — 参考回答要点

- **现象含义**：讲义："A misbehaving run shows the factor oscillating between high and low values, which is the signal that the model's gradients are sometimes in range and sometimes not." 8% 已超过讲义建议的 5% 告警线。
- **诊断**：
  1. 看 `skip_reason` 分布：是 `non_finite_loss`（前向溢出）还是 `non_finite_grad`（反向溢出）。
  2. 看裁剪前梯度范数：是否在跳过前后飙升，是否与特定 batch 相关（数据问题）。
  3. 看学习率：振荡是否从 warmup 结束、lr 达峰值时开始（第 44 节）。
  4. 定位溢出的层：对激活/梯度加 hook，找最先出现 Inf 的模块（常见于注意力 logits、未归一化的大激活）。
- **处理**：
  - 若硬件支持，换 BF16（最直接）；
  - 降低 `lr_max` 或延长 warmup；
  - 对溢出的算子强制 FP32（例如注意力 softmax 前的 logits）；
  - 调整 GradScaler 的 `growth_interval`，减少"增长—溢出—减半"的循环；
  - 清洗导致尖峰的数据。
- 常见误区：只看 loss 曲线——跳过步不更新权重，loss 曲线可能"看起来还行"，但实际有效训练步大大减少。

### Q17 — 参考回答要点

- **含义**：`max_norm` 相对模型当前的梯度尺度设得太小，裁剪从"异常保护"变成了"常态缩放"。讲义提到同时记录裁剪前后范数正是为了做"we are clipping at every step"的诊断。
- **对 SGD**：每步裁剪相当于有效学习率被降低（且随梯度大小变化），会明显影响训练。
- **对 Adam**：Adam 的更新约为 `m̂ / √v̂`，对梯度整体乘一个**常数**是近似不变的（分子分母同比例缩放，只受 ε 影响）。所以如果每步都被裁到差不多的比例，效果接近"没裁剪"；裁剪真正起作用的是"某一步梯度相对历史突然变大"的情形——它阻止尖峰梯度污染 `m`、`v` 和本步更新。
- 但"每步都裁剪"在 Adam 下仍会改变不同步之间的相对权重（大梯度步被压低），使 `m` 的方向偏向小梯度步。
- **做法**：检查 `pre_clip` 的分布（中位数、p99），把阈值设在正常范围之上、尖峰之下；同时排查是否学习率过高或初始化不当导致梯度长期偏大。
- 加分点：能说出本节 demo 只有第 0 步发生了裁剪（1.0075 → 1.0），之后梯度范数都低于 1.0，属于"健康的偶发裁剪"。

---

## 六、关联知识点

### 前置知识
- [阶段 19 · 44 带线性 Warmup 的余弦学习率](../../44-cosine-lr-warmup/docs/zh.md)：本节在其 AdamW 训练步与梯度范数日志之上加入裁剪与混合精度。
- [阶段 19 · 36 训练循环与 Evaluation](../../36-training-loop-eval/docs/zh.md)：基础训练循环。
- [阶段 03 · 06 Optimizers](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：理解 Adam 对梯度尺度的不变性。
- [阶段 03 · 08 Weight 初始化和训练稳定性](../../../03-deep-learning-core/08-weight-initialization/docs/zh.md)：梯度爆炸/消失的成因。
- [阶段 01 · 14 范数与距离](../../../01-math-foundations/14-norms-and-distances/docs/zh.md)：L2 范数的定义。

### 本节被哪些后续内容用到
- [阶段 19 · 46 Gradient Accumulation](../../46-gradient-accumulation/docs/zh.md)：累积后对总梯度做一次裁剪，与 GradScaler 共同使用。
- [阶段 19 · 47 Checkpoint 保存与恢复](../../47-checkpoint-save-resume/docs/zh.md)：GradScaler 的状态也需要写进 checkpoint。
- [阶段 19 · 48 从零实现分布式数据并行与 FSDP](../../48-distributed-fsdp-ddp/docs/zh.md)：分布式下全局范数要跨卡归约后再裁剪。
- [阶段 10 · 11 Quantization：让模型装得下](../../../10-llms-from-scratch/11-quantization/docs/zh.md)：FP16/BF16/INT8 等数值格式的进一步讨论。
- [阶段 03 · 13 调试神经网络](../../../03-deep-learning-core/13-debugging-neural-networks/docs/zh.md)：用梯度范数与 NaN 检测定位训练问题。

### 延伸关键词
`clip_grad_norm_` · `clip_grad_value_` · `global gradient norm` · `torch.amp.autocast` · `GradScaler` · `dynamic loss scaling` · `FP16 / BF16 / FP8` · `found_inf` · `skip rate` · `master weights` · `overflow / underflow`
