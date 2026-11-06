# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 45 节 Gradient Clipping（梯度裁剪）与 Mixed Precision（混合精度） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下）；测试：`python3 -m unittest discover tests -v` 或 `python3 -m pytest -q tests` ｜ **依赖**：`torch`（第三方，CPU 即可）；其余为标准库（`csv`、`math`、`dataclasses`、`pathlib`、`typing`）
>
> 本讲解同时覆盖 `tests/__init__.py`（空文件，0 字节）与 `tests/test_amp.py`（见第 9 节）。

---

## 1. 这份代码在考察什么

上一节的 AdamW + 调度假设"梯度是正常的"。这份代码给训练步加上两条安全带：

1. **全局 L2 范数裁剪**：所有参数梯度拼成一个向量求范数，超过阈值就整体等比缩小，并同时返回裁剪前、后的范数。
2. **混合精度训练步**：`torch.amp.autocast` 做低精度前向，`GradScaler` 负责 loss scaling，二者按"scale → backward → unscale → 检测 → 裁剪 → step → update"的顺序接线。
3. **非有限值检测与跳过**：loss 非有限时不做反向；梯度非有限时不做优化器更新；两者都写入带原因的 `SkipLog`。
4. **可观测性**：每步记录 `lr`、裁剪前后范数、loss、是否跳过、跳过原因和缩放因子；滚动跳过率作为告警依据。

> 一句话：**裁剪限制"坏 batch"一步能走多远，loss scaling 让 FP16 的梯度既不下溢也不悄悄变成 NaN，而日志让这两件事可被看见**。

需要先说明一个关键事实：在 CPU 上（也就是本 demo 实际运行的环境），`GradScaler` 被**主动禁用**，缩放因子恒为 1.0；autocast 默认用 BF16。因此 demo 演示了"裁剪 + 跳过"的接线，但看不到缩放因子的动态（第 6 节会给出手动启用后的实测结果）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `StepLog` | dataclass | 一行日志，8 个字段，`to_csv_row()` 输出规范 CSV 行 | 固定日志模式 |
| `SkipLog` | dataclass | 被跳过步的独立记录 | 告警与取证 |
| `has_non_finite_grad` | 函数 | 扫描梯度中是否有 NaN/Inf | 非有限检测 |
| `compute_global_l2_norm` | 函数 | 拼接梯度的 L2 范数（不修改梯度） | 全局范数 |
| `clip_global_l2_norm` | 函数 | 超阈值时原地缩放梯度，返回 `(pre, post)` | 梯度裁剪 |
| `AmpTrainState` | 类 | 持有模型、AdamW、GradScaler、autocast 配置；`step()` 是完整的安全训练步 | AMP 训练步 |
| `rolling_skip_rate` | 函数 | 每一步的滚动跳过率 | 跳过率告警 |
| `write_step_log_csv` | 函数 | 写规范 CSV | 持久记录 |
| `build_toy_model` | 函数 | 16→32→4 的 MLP 与固定 batch（与第 44 节相同） | 演示数据 |
| `inject_inf_into_first_grad` | 函数 | 测试用：把第一个参数的梯度全部写成 +Inf | 故障注入 |
| `run_demo` | 函数 | 训练 20 步，第 5 步注入 Inf，打印 STEP/SKIP 日志 | 演示 |

数据流（单步）：`zero_grad` → autocast 前向 → loss 有限性检查（失败 → `_record_skip`）→ `scaler.scale(loss).backward()` →（可选）注入故障 → `scaler.unscale_` → 梯度有限性检查（失败 → `update()` + 记录跳过）→ `clip_global_l2_norm` → `scaler.step` → `scaler.update` → 记录 `StepLog`。

---

## 3. 逐段精讲

### 3.1 常量与两种日志记录

```python
DEFAULT_MAX_NORM = 1.0
DEFAULT_DEVICE = "cpu"
NORM_TYPE = 2.0

@dataclass
class StepLog:
    step: int
    lr: float
    grad_l2_pre_clip: float
    grad_l2_post_clip: float
    loss: float
    skipped: bool
    skip_reason: str
    scaler_scale: float

    def to_csv_row(self) -> list[str]:
        return [str(self.step), f"{self.lr:.10f}", f"{self.grad_l2_pre_clip:.10f}",
                f"{self.grad_l2_post_clip:.10f}", f"{self.loss:.10f}",
                "1" if self.skipped else "0", self.skip_reason, f"{self.scaler_scale:.6f}"]
```

- 字段顺序与讲义规定的 CSV 模式一一对应：`step, lr, grad_l2_pre_clip, grad_l2_post_clip, loss, skipped, skip_reason, scaler_scale`。
- 布尔值写成 `"1"/"0"` 而不是 `"True"/"False"`，方便 pandas/SQL 直接求和算跳过率。
- `f"{float('inf'):.10f}"` 会输出 `inf`，所以跳过行在 CSV 中是合法的字符串。
- `NORM_TYPE = 2.0` 定义了但**没有被使用**（手写范数固定是 L2）。
- `SkipLog` 是跳过步的"窄表"：告警系统只关心步号、原因、范数、loss、缩放因子。

### 3.2 非有限检测与全局范数

```python
def has_non_finite_grad(parameters) -> bool:
    for param in parameters:
        if param.grad is None:
            continue
        grad = param.grad.detach()
        if not torch.isfinite(grad).all().item():
            return True
    return False
```

- `torch.isfinite` 对 NaN、+Inf、−Inf 都返回 False；`.all()` 归约成一个布尔张量，`.item()` 转成 Python bool。
- 找到第一个就提前返回（短路）。
- 工程注意：每个参数一次 `.item()` 在 GPU 上意味着一次同步；生产中 `GradScaler` 内部用 `found_inf` 张量在设备上累计，不需要逐参数同步。

```python
def compute_global_l2_norm(parameters) -> float:
    squared_sum = 0.0
    for param in parameters:
        if param.grad is None:
            continue
        grad = param.grad.detach()
        squared_sum += float(grad.pow(2).sum().item())
    return math.sqrt(squared_sum)
```

- `‖g‖ = sqrt(Σ_p ‖g_p‖²)`，与第 44 节 `gradient_l2_norm` 完全相同。累加用 Python float（双精度），所以数值与 `clip_grad_norm_`（float32 张量）在第 7 位小数后略有差别。
- 若某个梯度含 Inf，平方和为 Inf，`math.sqrt(inf) = inf`；含 NaN 则结果为 NaN。

### 3.3 `clip_global_l2_norm`：原地裁剪

```python
def clip_global_l2_norm(parameters: list[torch.nn.Parameter], max_norm: float) -> tuple[float, float]:
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

- **三种情况**：非有限 → 原样返回（不裁剪，让调用方决定跳过）；未超阈值 → 不动；超阈值 → 所有梯度乘同一个系数 `max_norm/‖g‖`，方向不变、范数变成 `max_norm`。
- `+ 1e-12` 防止除零（实际上 `pre_clip > max_norm > 0` 时不可能为 0，属于防御写法）。
- `param.grad.detach().mul_(scale)`：`detach()` 返回共享存储的视图，`mul_` 原地修改，所以真正改到了 `.grad`。
- 示例：`[6, 8]` → 范数 10 → 系数约 0.1 → `[0.6, 0.8]`，返回 `(10.0, 1.0)`。
- ⚠️ **生成器陷阱**：参数被遍历两次（一次求范数、一次缩放）。若传入 `model.parameters()` 生成器，第一次就耗尽，第二次循环不执行，**梯度没有被裁剪但函数仍返回 `(pre, max_norm)`**。已实测：传生成器时裁剪后实际范数仍为 1.0080，传列表时为 0.1000。`AmpTrainState` 调用处用 `list(...)` 规避了这一点（测验 Q9）。
- ⚠️ 返回的 `post_clip` 是"声明值"`max_norm`，不是重新测得的值。
- ⚠️ 讲义与 docstring 都称它是"`torch.nn.utils.clip_grad_norm_` 的包装"，但代码**并未调用** `clip_grad_norm_`，而是手写了等价逻辑（`clip_grad_norm_` 用 `max_norm/(total+1e-6)` 并在 float32 上计算，测验 Q12）。

### 3.4 `AmpTrainState.__init__`：GradScaler 与 autocast 精度

```python
        if device_type not in ("cpu", "cuda"):
            raise ValueError(...)
        self.optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
        scaler_enabled = device_type == "cuda"
        self.scaler = torch.amp.GradScaler(device_type, enabled=scaler_enabled)
        if amp_dtype is None:
            amp_dtype = torch.bfloat16 if device_type == "cpu" else torch.float16
        self.amp_dtype = amp_dtype
        self.global_step = 0
        self._log: list[StepLog] = []
        self._skip_log: list[SkipLog] = []
        self._loss_fn = nn.functional.mse_loss
```

- **GradScaler 只在 CUDA 上启用**。`enabled=False` 时：`scale(loss)` 原样返回、`unscale_`/`update` 是空操作、`step(opt)` 直接调 `opt.step()`、`get_scale()` 返回 1.0。讲义称 CPU 上的 GradScaler 是"stub"，更准确的说法是"被代码禁用"——本环境（torch 2.14）中 `GradScaler("cpu", enabled=True)` 完全可用（第 6 节实测）。
- **autocast 精度**：CPU 默认 BF16、CUDA 默认 FP16。讲义正文多处写"FP16"，但 CPU demo 实际跑的是 BF16。
- 只校验 `device_type` 字符串，**不会**把模型和数据搬到对应设备；用 `"cuda"` 时调用方要自己 `.to("cuda")`。
- AdamW 使用默认 `betas=(0.9, 0.999)`，与第 44 节的 `(0.9, 0.95)` 不同；也**没有接入第 44 节的调度**，lr 恒为 `1e-2`（`set_lr` 方法提供了接口但 demo 未用）。
- 默认 loss 是 `mse_loss`，可用 `set_loss_fn` 替换（测试用它制造非有限 loss）。

### 3.5 `step()` 前半段：autocast 前向与 loss 检查

```python
        self.model.train()
        self.optimizer.zero_grad(set_to_none=True)

        with torch.amp.autocast(device_type=self.device_type, dtype=self.amp_dtype):
            predictions = self.model(inputs)
            loss = self._loss_fn(predictions, targets)

        if not torch.isfinite(loss).all().item():
            return self._record_skip(
                loss_value=float(loss.detach().cpu().item()),
                reason="non_finite_loss",
                pre_clip=0.0,
                update_scaler=False,
            )
```

- autocast 是**按算子选择精度**：已实测 BF16 autocast 下 `model(x)` 输出 `torch.bfloat16`，`mse_loss` 输出 `torch.float32`（loss 类算子在 autocast 的 FP32 名单里）。权重本身仍是 FP32。
- 同一 toy 模型、同一 batch，FP32 下初始 loss 为 `1.0249619`（第 44 节输出 1.024962），BF16 autocast 下为 `1.024904`——差异就是 BF16 只有 7 位尾数带来的舍入误差。
- loss 非有限时直接跳过：没有 `backward`，也**不调用** `scaler.update()`。原因（代码注释）：本步没有 `scale().backward()`/`unscale_`，`update()` 找不到 inf 检查记录，启用状态下会断言失败。这与讲义"`scaler.update()` runs every step, even on skip"不完全一致，讲义的原则只适用于梯度非有限的路径。
- `pre_clip=0.0`：没有反向就没有梯度，范数记为 0（而梯度非有限路径记为 inf），两种跳过在 CSV 中可以靠 `skip_reason` 区分。

### 3.6 `step()` 中段：scale、backward、unscale、梯度检查

```python
        self.scaler.scale(loss).backward()
        if gradient_corruptor is not None:
            gradient_corruptor(self.model)
        self.scaler.unscale_(self.optimizer)

        if has_non_finite_grad(self.model.parameters()):
            scale_before = float(self.scaler.get_scale())
            self.scaler.update()
            record = StepLog(step=self.global_step, lr=self._current_lr(),
                             grad_l2_pre_clip=float("inf"), grad_l2_post_clip=float("inf"),
                             loss=float(loss.detach().item()), skipped=True,
                             skip_reason="non_finite_grad", scaler_scale=scale_before)
            self._log.append(record)
            self._skip_log.append(SkipLog(...))
            self.global_step += 1
            return record
```

- `scaler.scale(loss)` 返回 `loss × S`；`backward()` 后每个 `.grad` 都是真实梯度的 S 倍。
- `gradient_corruptor` 是**测试钩子**：在 backward 之后、unscale 之前注入故障，模拟 FP16 反向溢出。生产调用方传 `None`。
- `scaler.unscale_(optimizer)`：把该优化器管理的所有梯度原地除以 S，同时检查 inf 并把结果记到 `found_inf`。**必须在裁剪之前**，否则阈值作用在放大了 S 倍的梯度上。
- 检测到非有限梯度：调用 `scaler.update()` 让缩放因子减半（启用时），**不调用** `scaler.step()`，所以权重与 AdamW 状态都不变。
- ⚠️ 日志记录的是 `scale_before`（更新前的值），而正常步记录的是 `update()` 之后的值，三条路径的记录口径不统一（测验 Q11）。
- 范数直接记 `inf`，没有区分 NaN 与 Inf。

### 3.7 `step()` 后半段：裁剪、step、update

```python
        pre_clip, post_clip = clip_global_l2_norm(list(self.model.parameters()), self.max_norm)

        self.scaler.step(self.optimizer)
        self.scaler.update()
        record = StepLog(..., grad_l2_pre_clip=pre_clip, grad_l2_post_clip=post_clip,
                         skipped=False, skip_reason="",
                         scaler_scale=float(self.scaler.get_scale()))
```

- 顺序正是讲义要求的：unscale 之后裁剪 → `scaler.step` → `scaler.update`。
- `scaler.step(opt)` 在启用时会再查一次 `found_inf`，有 inf 就跳过 `opt.step()`；本代码已经提前处理了非有限情况，所以这里一定会执行更新。
- `list(self.model.parameters())` 物化参数列表，避免 3.3 中的生成器陷阱。
- 记录的 `lr` 来自 `param_groups[0]["lr"]`，即优化器实际使用的值。

### 3.8 `_record_skip` 与只读属性

```python
    def _record_skip(self, loss_value, reason, pre_clip, update_scaler=True) -> StepLog:
        record = StepLog(..., skipped=True, skip_reason=reason,
                         scaler_scale=float(self.scaler.get_scale()))
        self._log.append(record)
        self._skip_log.append(SkipLog(...))
        self.global_step += 1
        if update_scaler:
            self.scaler.update()
        return record
```

- 通用的"记录跳过"辅助函数；目前只被非有限 loss 路径调用，且总是传 `update_scaler=False`，所以 `update_scaler=True` 分支在代码中从未执行。非有限梯度路径没有复用它，而是内联了一份几乎相同的代码。
- 跳过也让 `global_step` 加 1：步号是"尝试次数"而不是"成功更新次数"。如果接入第 44 节的调度，跳过步也会推进学习率——这是一个需要明确的约定。
- `log`、`skip_log` 用 `@property` 返回副本；`skip_count` 是跳过列表的长度。

### 3.9 滚动跳过率与 CSV

```python
def rolling_skip_rate(log, window: int = 1000) -> list[float]:
    if window <= 0:
        raise ValueError("window must be positive")
    rows = list(log)
    rates: list[float] = []
    skipped: list[int] = []
    for row in rows:
        skipped.append(1 if row.skipped else 0)
        if len(skipped) > window:
            skipped = skipped[-window:]
        rates.append(sum(skipped) / len(skipped))
    return rates
```

- 每步一个值：最近 `min(已有步数, window)` 步中跳过的比例。窗口未满时分母是实际条数。
- 实测（20 步、只有第 5 步跳过、`window=10`）：第 0–4 步 0.0，第 5 步 `1/6 ≈ 0.1667`，第 6–8 步 `1/7, 1/8, 1/9`，第 9–14 步 0.1，第 15 步起回到 0.0。
- 复杂度 O(n·window)：每步都切片、求和。生产中用 `collections.deque(maxlen=window)` 加一个运行中的计数即可 O(1)。
- 讲义说"would page on a rate above 5 percent"，代码只提供计算，没有告警或中止逻辑（讲义练习 4）。
- `write_step_log_csv` 与第 44 节同构：`mkdir(parents=True, exist_ok=True)`、`newline=""`、先写表头。讲义练习 5 提到"每行后 flush 以便 Ctrl-C 后文件完整"，当前实现是一次性写完，没有逐行 flush。demo 也没有调用它。

### 3.10 故障注入与 demo

```python
def inject_inf_into_first_grad(model: nn.Module) -> None:
    for param in model.parameters():
        if param.grad is not None:
            param.grad.data[...] = float("inf")
            return

def run_demo() -> int:
    model, inputs, targets = build_toy_model()
    state = AmpTrainState(model=model, lr=1e-2, max_norm=1.0, device_type="cpu")
    for index in range(20):
        corruptor = None
        if index == 5:
            corruptor = inject_inf_into_first_grad
        record = state.step(inputs, targets, gradient_corruptor=corruptor)
        marker = "SKIP" if record.skipped else "STEP"
        print(f"{marker} step={record.step:>3} lr={record.lr:.6f} "
              f"pre_clip={record.grad_l2_pre_clip:>10.6f} ...")
    print(f"skip_count={state.skip_count} "
          f"final_skip_rate={rolling_skip_rate(state.log, window=10)[-1]:.4f}")
```

- `param.grad.data[...] = float("inf")`：`[...]`（Ellipsis）表示"所有元素"，原地填充；`.data` 绕过 autograd 记录。第一个参数是第一层 `Linear` 的权重 `(32, 16)`，512 个元素全部变成 Inf。
- `record.skip_reason or '-'`：空字符串为假，于是打印 `-`。
- 讲义说 demo 训练"a small `nn.Linear` model"，实际是 `Linear → GELU → Linear` 的两层 MLP。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 全局 L2 范数裁剪 | 保持梯度方向，只限制步长 | 需要遍历所有参数；分布式下要跨卡归约（第 48 节） |
| 同时记录 pre/post 范数 | 识别"每步都在裁剪"的异常 | `post_clip` 是声明值而非实测值 |
| 手写裁剪而非调用 `clip_grad_norm_` | 逻辑透明 | 与讲义描述不符；有生成器陷阱；生产直接用 `clip_grad_norm_`（多张量 foreach 实现更快） |
| CPU 上禁用 GradScaler、默认 BF16 | BF16 范围大，不需要 loss scaling；CI 只有 CPU | demo 看不到缩放因子的动态；可在 CPU 上手动启用来演示 |
| 反向前检查 loss | 一次归约的开销，省掉整个无用的反向 | loss 有限但梯度溢出的情况仍需第二道检查 |
| 显式 `has_non_finite_grad` 而不只依赖 `scaler.step` | 能写出带原因的跳过日志；CPU 禁用 scaler 时 `scaler.step` 不会帮你跳过 | 逐参数 `.item()` 同步，GPU 上较慢 |
| 非有限 loss 路径不调用 `update()` | 遵守 GradScaler 调用顺序 | 与讲义"每步都 update"原则存在表述差异 |
| 跳过步也推进 `global_step` | 步号与日志行一一对应 | 若接入调度，跳过会消耗调度进度 |
| `gradient_corruptor` 测试钩子 | 无需真实溢出就能稳定复现跳过路径 | 钩子进入了生产 API 的签名 |
| 滚动跳过率用列表切片 | 简单 | O(n·window)；用 deque + 计数器 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，可写 `torch.dtype \| None` |
| 模块级常量 | `DEFAULT_MAX_NORM = 1.0` | 全大写表示常量（约定，不强制） |
| `@dataclass` | `StepLog`、`SkipLog` | 自动生成构造函数等；`asdict`、`field` 被导入但未使用 |
| 条件表达式 | `"1" if self.skipped else "0"` | 一行 if/else |
| `or` 取默认值 | `record.skip_reason or '-'` | 左侧为假（空字符串）时取右侧 |
| 类型注解 `tuple[float, float]`、`Callable[[nn.Module], None] \| None` | `clip_global_l2_norm`、`step` 签名 | 描述返回元组、可调用对象或 None |
| 元组返回与解包 | `pre_clip, post_clip = clip_global_l2_norm(...)` | 一次返回多个值 |
| `float("inf")` / `math.isfinite` | 跳过记录、裁剪函数 | Python 中表示与判断无穷大 |
| `with` 上下文管理器 | `with torch.amp.autocast(...):` | 进入时开启低精度，退出时恢复 |
| `@property` | `log`、`skip_log`、`skip_count` | 只读属性，返回副本防止外部修改 |
| 下划线私有约定 | `_record_skip`、`_current_lr`、`_loss_fn` | 内部使用 |
| 关键字参数与默认值 | `update_scaler: bool = True` | 调用时可按名传参 |
| 高阶函数 / 回调 | `gradient_corruptor(self.model)` | 函数作为参数传入 |
| `lambda` | 测试中 `lambda preds, tgts: preds.sum() * float("inf")` | 匿名函数 |
| Ellipsis 索引 | `param.grad.data[...] = float("inf")` | 选取全部元素原地赋值 |
| 原地运算 `mul_` | `param.grad.detach().mul_(scale)` | PyTorch 中下划线结尾的方法会修改张量本身 |
| 列表切片 | `skipped = skipped[-window:]` | 保留最后 `window` 个元素 |
| f-string 宽度与精度 | `{record.grad_l2_pre_clip:>10.6f}`、`{record.scaler_scale:.1f}` | 右对齐宽 10、6 位小数；`inf` 也能按宽度输出 |
| `sys.exit(run_demo())` + `if __name__ == "__main__":` | 文件末尾 | 脚本入口，返回值作退出码 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，torch 2.14 CPU，约 2.5 秒）：

```text
STEP step=  0 lr=0.010000 pre_clip=  1.007523 post_clip=  1.000000 loss=1.024904 scale=1.0 reason=-
STEP step=  1 lr=0.010000 pre_clip=  0.858376 post_clip=  0.858376 loss=0.871224 scale=1.0 reason=-
STEP step=  2 lr=0.010000 pre_clip=  0.747091 post_clip=  0.747091 loss=0.739348 scale=1.0 reason=-
STEP step=  3 lr=0.010000 pre_clip=  0.663516 post_clip=  0.663516 loss=0.626274 scale=1.0 reason=-
STEP step=  4 lr=0.010000 pre_clip=  0.597836 post_clip=  0.597836 loss=0.530047 scale=1.0 reason=-
SKIP step=  5 lr=0.010000 pre_clip=       inf post_clip=       inf loss=0.448445 scale=1.0 reason=non_finite_grad
STEP step=  6 lr=0.010000 pre_clip=  0.552096 post_clip=  0.552096 loss=0.448445 scale=1.0 reason=-
STEP step=  7 lr=0.010000 pre_clip=  0.529829 post_clip=  0.529829 loss=0.379962 scale=1.0 reason=-
...
STEP step= 19 lr=0.010000 pre_clip=  0.331493 post_clip=  0.331493 loss=0.058069 scale=1.0 reason=-

skip_count=1 final_skip_rate=0.0000
```

逐项解读：

- **第 0 步发生了裁剪**：`1.007523 → 1.000000`，这是 20 步中唯一一次裁剪。与第 44 节相比，同一模型第 0 步的范数是 1.008009（FP32），这里 1.007523（BF16 autocast），loss 1.024904 vs 1.024962——差异来自 BF16 舍入。
- **lr 恒为 0.01**：本节没有接入第 44 节的调度，第一步就用峰值 lr（所以 loss 下降比第 44 节快：20 步后 0.058 vs 0.186）。
- **第 5 步 SKIP**：注入的 Inf 被 `has_non_finite_grad` 抓到；loss 列 `0.448445` 是正常前向的结果。
- **第 6 步 loss 与第 5 步相同**：跳过步没有更新权重，相同权重 + 相同 batch → 相同 loss。这也是检验"跳过是否真的跳过"的最简单方法。
- **scale 恒为 1.0**：CPU 上 GradScaler 被禁用。
- **`final_skip_rate=0.0000`**：窗口为 10，最后 10 步（10–19）没有跳过；全局跳过率是 1/20 = 5%。

**补充实验：在 CPU 上手动启用 GradScaler**（`st.scaler = torch.amp.GradScaler("cpu", enabled=True)`，第 3、5 步注入 Inf）：

```text
step skipped scale     loss
0    False   65536.0   1.024904
1    False   65536.0   0.871224
2    False   65536.0   0.739348
3    True    65536.0   0.626274   ← 记录的是 update() 之前的值
4    False   32768.0   0.626274   ← 减半在这里才"看得见"；loss 与上一步相同
5    True    32768.0   0.530047
6    False   16384.0   0.530047
7    False   16384.0   0.448445
```

- 初始缩放 65,536（2^16）；每次跳过减半；增长需要连续 2,000 个干净步，所以 8 步内不会翻倍。
- loss 列与禁用时完全一致：GradScaler 的放大与缩小是精确的 2 的幂，unscale 后梯度不变（只要不溢出）。

**补充实验：讲义练习 1（target × 1e8）**：

- 默认 BF16：**不跳过**，loss ≈ 9.79e15（有限），`pre_clip ≈ 9.67e7` 被裁到 1.0——由裁剪兜底。
- `amp_dtype=torch.float16`：**跳过**，原因 `non_finite_grad`——FP16 反向溢出。
- 这正好说明讲义练习 2 的直觉（"BF16 很少需要 loss scaling"）：同一个尖峰，FP16 溢出、BF16 不溢出。

测试运行结果见第 9 节（17 个测试全部通过）。

---

## 7. 动手改一改

1. **修生成器陷阱**：在 `clip_global_l2_norm` 开头物化参数，并让 `post_clip` 返回实测值；补一个"传入 `model.parameters()` 也能裁剪"的测试。
2. **统一 scale 记录口径**：给 `StepLog` 增加 `scaler_scale_before` 列，所有路径都记录 `update()` 前后两个值；在 CPU 上启用 GradScaler 复现第 6 节的表格。
3. **接入第 44 节的调度**：每步 `state.set_lr(schedule.lr(state.global_step))`，并思考跳过步要不要推进调度（推进 = 按尝试次数，不推进 = 按有效更新次数）。
4. **讲义练习 1、2 的正确版本**：分别在 BF16 与 FP16 下对第 8 步使用 `targets * 1e8`，比较两种精度的跳过次数与裁剪前范数。
5. **讲义练习 4**：用 `collections.deque(maxlen=window)` 重写 `rolling_skip_rate` 为 O(1) 的在线版本，并加一个"连续 100 步超过阈值就 `raise RuntimeError`"的保护。
6. **讲义练习 5**：训练循环中逐行写 CSV，每行后 `fh.flush()`；用 `KeyboardInterrupt` 模拟中断，确认文件最后一行完整。

---

## 8. 常见坑

- **在 unscale 之前裁剪**：阈值作用在放大了 S 倍的梯度上，S = 65,536 时等于把所有梯度压得极小或者让阈值失效。
- **跳过路径忘了 `scaler.update()`**：缩放因子永远不减半，下一步继续溢出，形成"连续跳过"。
- **在没有 backward/unscale 的步调用 `update()`**：违反调用顺序会断言失败（本节非有限 loss 路径因此不调用）。
- **把生成器传给需要遍历两次的函数**：`model.parameters()` 只能遍历一次。
- **只记录裁剪后的范数**：永远 ≤ `max_norm`，看不出问题。
- **以为 autocast 会把一切转成低精度**：loss、归一化等仍是 FP32；也不要手动 `.half()` 整个模型去"代替" autocast。
- **以为 CPU demo 演示了 loss scaling**：CPU 上 GradScaler 被禁用，scale 恒为 1.0。
- **把 65,536 和 65,504 搞混**：前者是 GradScaler 默认初始缩放（2^16），后者是 FP16 的最大有限值。
- **跳过率只看全局平均**：长训练中局部爆发的跳过会被平均掉，必须看滚动窗口。

---

## 9. 测试在验证什么

`tests/__init__.py` 是 0 字节的空文件，作用是把 `tests/` 标记为包，便于 `unittest discover` 与 pytest 导入；`test_amp.py` 用 `sys.path.insert(0, str(HERE.parent))` 把 `code/` 加入路径后 `from main import ...`。辅助函数 `_make_param_with_grad(values)` 构造一个梯度为指定值的参数。

运行方式（均已实际运行）：

```bash
cd code && python3 -m unittest discover tests -v   # Ran 17 tests ... OK
cd code && python3 -m pytest -q tests              # 17 passed
```

| 测试类 | 测试 | 验证的性质 |
|-------|------|----------|
| `GlobalNormTests` | `test_global_l2_norm_matches_known_value` | `[3, 0, 4]` 的范数为 5 |
| | `test_global_l2_norm_spans_multiple_params` | `[3, 0]` 与 `[4]` 跨参数拼接后范数为 5——证明是"全局"而非逐参数 |
| | `test_global_l2_norm_handles_none_grad` | `grad is None` 被跳过，结果 0 |
| `ClipTests` | `test_clip_no_op_when_under_max_norm` | `[0.3, 0.4]`（范数 0.5）在阈值 1 下不变，返回 `(0.5, 0.5)`——讲义练习 3 要求的测试其实已经存在 |
| | `test_clip_scales_gradients_above_max_norm` | `[6, 8]` → 返回 `(10, 1)`，且**实测**裁剪后梯度范数为 1 |
| | `test_clip_rejects_non_positive_max_norm` | `max_norm=0` 抛错 |
| `NonFiniteTests` | 三个测试 | Inf、NaN 都能被检出；正常梯度返回 False |
| `AmpTrainStateTests` | `test_step_clips_high_norm_gradient` | `max_norm=0.001` 时第一步 `pre > post` 且 `post ≈ 0.001` |
| | `test_step_skips_on_injected_inf` | 注入 Inf 后 `skipped=True`、原因 `non_finite_grad`、`skip_count == 1` |
| | `test_step_skips_on_non_finite_loss` | 用 `preds.sum() * inf` 作 loss，原因 `non_finite_loss` |
| | `test_state_rejects_invalid_device` | `device_type="mars"` 抛错 |
| | `test_state_rejects_non_positive_max_norm` | `max_norm=0` 抛错 |
| `RollingSkipRateTests` | `test_rolling_skip_rate_window_is_respected` | `[T, T, F, F, F]`、窗口 2：首两步 1.0，末步 0.0 |
| | `test_rolling_skip_rate_rejects_zero_window` | 窗口 0 抛错 |
| `CsvTests` | `test_write_step_log_csv_columns` | 表头是 8 列规范模式；`skipped` 列写成 `"0"` |

值得注意的测试缺口：

- 没有任何测试启用 GradScaler，因此"跳过后缩放因子减半""正常步可能翻倍"这条讲义的核心机制**在测试中从未被验证**。
- 没有测试跳过步确实没有修改权重（可以比较 step 前后的参数快照）。
- 没有测试 `clip_global_l2_norm` 接收生成器的情形（会静默失效）。
- `test_step_skips_on_non_finite_loss` 只检查返回值，没有检查此时 `scaler.update()` 未被调用、`global_step` 推进等副作用。
