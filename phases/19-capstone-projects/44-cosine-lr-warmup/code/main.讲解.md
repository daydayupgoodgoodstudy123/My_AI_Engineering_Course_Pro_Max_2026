# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 44 节 带线性 Warmup 的余弦学习率 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（在 `code/` 目录下）；测试：`python3 -m unittest discover tests -v` 或 `python3 -m pytest -q tests` ｜ **依赖**：`torch`（第三方，CPU 即可）；其余均为标准库（`csv`、`dataclasses`、`math`、`pathlib`、`typing`）
>
> 本讲解同时覆盖 `tests/__init__.py`（空文件，0 字节）与 `tests/test_schedule.py`（见第 9 节）。

---

## 1. 这份代码在考察什么

这份代码把"学习率调度"做成一个**可测试的、无状态的纯函数**，并把它接进一个最小的 AdamW 训练步：

1. **三段式调度的闭式实现**：线性 warmup → 余弦衰减 → 钉在 `lr_min`，以及两个端点（`warmup_steps`、`total_steps`）的精确连续。
2. **边界与校验**：负 step、`warmup_steps = 0`、`warmup >= total`、`lr_min > lr_max` 等配置错误在构造时就拒绝。
3. **训练健康度的可观测性**：每步同时记录 `lr` 和梯度 L2 范数，日志模式固定为 `step, lr, grad_l2_norm, loss`。
4. **可审阅的产物**：文本图（不依赖 matplotlib）与 CSV。
5. **对照基线**：线性 warmup + 常数、线性 warmup + 反平方根衰减，以及梯度范数平滑用的 EWMA、weight decay 参数分组。

> 一句话：**学习率是 step 的函数，step 是唯一需要持久化的状态**——把调度写成一个闭式函数并在每个边界上测试，就能消灭"六小时后才暴露的 off-by-one"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CosineWithWarmup` | dataclass | `lr(step)` 闭式计算三段式学习率；`points()` 列出 `[0, total]` 的所有值 | warmup + cosine + floor |
| `StepLog` | dataclass | 一行训练日志，`to_csv_row()` 以 10 位小数输出 | 固定日志模式 |
| `gradient_l2_norm` | 函数 | 所有参数梯度拼接后的 L2 范数 | 梯度范数 |
| `TrainState` | 类 | 持有模型、AdamW、调度、loss 和 `global_step`；`step()` 跑一次完整训练步 | 调度轴 / 训练步 |
| `plot_schedule_ascii` | 函数 | 把调度画成字符图 | 可视化自检 |
| `write_schedule_csv` / `write_step_log_csv` | 函数 | 写 CSV（调度表 / 训练日志） | 持久记录 |
| `LinearWarmupConstant` | dataclass | warmup 后保持 `lr_max` | 消融基线 |
| `InverseSqrtWarmup` | dataclass | warmup 后 `lr_max·sqrt(w/step)` | 经典 Transformer 调度 |
| `EWMA` | dataclass | 指数滑动平均，用于平滑梯度范数 | 监控平滑 |
| `StepLogSummary` / `summarize_step_log` | dataclass / 函数 | 把日志压缩成峰值、终值、loss 变化 | 审阅摘要 |
| `split_decay_groups` | 函数 | 把参数分成衰减组与不衰减组 | AdamW 参数分组 |
| `build_toy_model` / `run_demo` | 函数 | 16→32→4 的小 MLP，固定 batch 训练 20 步并打印 | 演示 |

数据流：`run_demo` → `build_toy_model`（固定种子 7）→ 构造 `CosineWithWarmup(4, 20, 1e-2, 1e-4)` → `TrainState` → 循环 20 次 `state.step()`（前向 → 反向 → 梯度范数 → `lr(global_step)` → `AdamW.step`）→ 打印每步日志 → `plot_schedule_ascii` → `summarize_step_log`。

---

## 3. 逐段精讲

### 3.1 导入与 torch 依赖检查

```python
from __future__ import annotations
...
try:
    import torch
    from torch import nn
except ImportError as exc:
    raise SystemExit(
        "torch is required for this lesson. Install with: pip install torch"
    ) from exc
```

- `from __future__ import annotations`：让 `int | None`、`list[tuple[int, float]]` 这类注解在旧版本 Python 上也不会在定义时求值。
- 缺 torch 时用 `SystemExit` 给出清晰提示而不是一长串 traceback；`from exc` 保留原始异常链。
- 注意：调度函数本身只用到 `math`，真正依赖 torch 的只有 `TrainState`、`gradient_l2_norm` 等训练部分。

### 3.2 `CosineWithWarmup`：构造校验

```python
@dataclass
class CosineWithWarmup:
    warmup_steps: int
    total_steps: int
    lr_max: float
    lr_min: float = 0.0

    def __post_init__(self) -> None:
        if self.warmup_steps < 0:
            raise ValueError("warmup_steps must be non-negative")
        if self.total_steps <= 0:
            raise ValueError("total_steps must be positive")
        if self.warmup_steps >= self.total_steps:
            raise ValueError("warmup_steps must be less than total_steps")
        if self.lr_max <= 0:
            raise ValueError("lr_max must be positive")
        if self.lr_min < 0:
            raise ValueError("lr_min must be non-negative")
        if self.lr_min > self.lr_max:
            raise ValueError("lr_min must not exceed lr_max")
```

- `@dataclass` 自动生成 `__init__`，`__post_init__` 在其后运行，用于校验——**配置错误在构造时立刻失败**，而不是训练到一半才发现。
- `warmup_steps >= total_steps` 被拒绝，这保证了余弦段至少有 1 步（`decay_span >= 1`）。
- 只有 4 个字段，没有任何可变状态：这就是讲义说的"stateless"。

### 3.3 `lr(step)`：三段式闭式公式

```python
    def lr(self, step: int) -> float:
        if step < 0:
            raise ValueError(f"step must be non-negative, got {step}")
        if self.warmup_steps > 0 and step <= self.warmup_steps:
            return self.lr_max * (step / self.warmup_steps)
        if step >= self.total_steps:
            return self.lr_min
        decay_span = max(1, self.total_steps - self.warmup_steps)
        progress = (step - self.warmup_steps) / decay_span
        cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
        return self.lr_min + (self.lr_max - self.lr_min) * cosine
```

逐个分支：

| 条件 | 返回值 | 说明 |
|------|-------|------|
| `step < 0` | 抛 `ValueError` | 负 step 一定是调用方的 bug |
| `warmup > 0` 且 `step <= warmup` | `lr_max · step / warmup` | 线性 warmup；`step = 0` 精确为 0，`step = warmup` 精确为 `lr_max` |
| `step >= total` | `lr_min` | 地板；不报错、不外推 |
| 其余 | `lr_min + (lr_max − lr_min)·0.5·(1 + cos(π·progress))` | 余弦半周期 |

- **端点连续**：`step = warmup` 时 warmup 分支返回 `lr_max`；若落到余弦分支，`progress = 0`、`cos 0 = 1`，也得 `lr_max`。`step = total` 时余弦分支本应得 `cos π = −1` → `lr_min`，代码提前用地板分支返回同一个值，保证**精确相等**（测试用 `assertEqual(lr(101), 0.1)`）。
- **`warmup_steps = 0`**：第二个条件的 `warmup_steps > 0` 整体为假，直接进入余弦段，`lr(0) = lr_max`。如果写成 `step <= self.warmup_steps` 而不加 `> 0`，`step = 0` 会触发 `0 / 0`。
- **`max(1, ...)`** 是防御性写法：构造校验已经保证 `total − warmup >= 1`，这里不会真正起作用。
- 实际计算（`warmup=10, total=100, lr_max=1.0, lr_min=0.1`）：

| step | 0 | 5 | 10 | 11 | 32 | 55 | 78 | 100 | 150 |
|------|---|---|----|----|----|----|----|-----|-----|
| lr | 0.0 | 0.5 | 1.0 | 0.999726 | 0.873703 | 0.55 | 0.226297 | 0.1 | 0.1 |

  衰减段中点（step 55）恰为 `(lr_max + lr_min) / 2`；余弦在两端平缓、中间陡峭（11 与 10 只差 0.0003）。

```python
    def points(self, num_steps: int | None = None) -> list[tuple[int, float]]:
        upper = self.total_steps if num_steps is None else num_steps
        if upper <= 0:
            return []
        return [(step, self.lr(step)) for step in range(upper + 1)]
```

- 返回 `upper + 1` 个点（`[0, upper]` 闭区间）。一个小怪癖：`points(0)` 返回 `[]`，而不是 `[(0, lr(0))]`（已运行验证）。

### 3.4 `StepLog` 与梯度范数

```python
@dataclass
class StepLog:
    step: int
    lr: float
    grad_l2_norm: float
    loss: float

    def to_csv_row(self) -> list[str]:
        return [str(self.step), f"{self.lr:.10f}", f"{self.grad_l2_norm:.10f}", f"{self.loss:.10f}"]
```

- 字段顺序就是讲义要求的固定模式 `step, lr, grad_l2_norm, loss`；`.10f` 固定小数位，保证 CSV 可逐字节比对。

```python
def gradient_l2_norm(parameters: Iterable[torch.nn.Parameter]) -> float:
    squared_sum = 0.0
    for param in parameters:
        if param.grad is None:
            continue
        grad = param.grad.detach()
        squared_sum += float(grad.pow(2).sum().item())
    return math.sqrt(squared_sum)
```

- 数学上：`‖g‖₂ = sqrt(Σ_p Σ_i g_{p,i}²)`，即把所有参数的梯度拼成一个长向量再求范数。测试用 `[3, 0, 4]` 和 `[0, 0]` 验证得 5。
- `param.grad is None` 时跳过（未参与前向的参数、或 `zero_grad(set_to_none=True)` 后尚未反向的参数）。
- docstring 说这样写是为了不依赖某个 PyTorch 版本的 `torch.nn.utils.get_total_norm`；本环境 torch 2.14 已经提供该函数。
- 工程注意：每个参数一次 `.item()` 都会触发一次 GPU→CPU 同步，参数多时很慢；生产中用 `torch.nn.utils.clip_grad_norm_`（它返回裁剪前的总范数）或先在设备上 `torch.stack` 再一次性取值。

### 3.5 `TrainState`：把调度接进 AdamW

```python
class TrainState:
    def __init__(self, model, schedule, loss_fn, weight_decay=0.01,
                 betas=(0.9, 0.95), eps=1e-8) -> None:
        self.model = model
        self.schedule = schedule
        self.loss_fn = loss_fn
        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=schedule.lr(0), betas=betas, eps=eps,
            weight_decay=weight_decay,
        )
        self.global_step = 0
        self._log: list[StepLog] = []
```

- `lr=schedule.lr(0)`：优化器的初始 lr 就是调度的第 0 步值（这里是 0.0，AdamW 接受 0）。
- `betas=(0.9, 0.95)`：β₂ 取 0.95 而非 PyTorch 默认的 0.999，是大模型训练常见设置，二阶矩"记忆更短"。
- `global_step` 由 `TrainState` 拥有——讲义"The class owns the step counter so the schedule axis is the durable one"。第 47 节会把它写进 checkpoint。
- ⚠️ 所有参数用同一个 `weight_decay=0.01`，**包括 bias**；下面的 `split_decay_groups` 并没有被接入（见 3.9）。

```python
    def step(self, batch_inputs, batch_targets) -> StepLog:
        self.model.train()
        self.optimizer.zero_grad(set_to_none=True)
        predictions = self.model(batch_inputs)
        loss = self.loss_fn(predictions, batch_targets)
        loss.backward()
        grad_norm = gradient_l2_norm(self.model.parameters())
        rate = self.schedule.lr(self.global_step)
        self.set_lr(rate)
        self.optimizer.step()
        record = StepLog(step=self.global_step, lr=rate, grad_l2_norm=grad_norm,
                         loss=float(loss.detach().item()))
        self._log.append(record)
        self.global_step += 1
        return record
```

顺序解析：

1. `model.train()`：切到训练模式（对 Dropout、BatchNorm 有影响；本模型没有，但这是好习惯）。
2. `zero_grad(set_to_none=True)`：把 `.grad` 设为 `None` 而不是零张量，省内存，也让"未参与计算的参数"可区分。
3. 前向 → loss → `backward()`。
4. **先算梯度范数**，再改 lr、再 `optimizer.step()`：这样日志记录的是"本步更新所用的梯度"。
5. `rate = lr(global_step)`：**用 step 编号直接查表**，不是在上一步 lr 基础上乘衰减系数，因此不会积累浮点误差。
6. 记录 loss 时 `loss.detach().item()`：拿到 Python float，不持有计算图。
7. `global_step += 1` 在最后：第 k 次调用使用 `lr(k−1)`… 也就是第一次调用用 `lr(0)`。

```python
    def set_lr(self, lr: float) -> None:
        for group in self.optimizer.param_groups:
            group["lr"] = lr

    @property
    def log(self) -> list[StepLog]:
        return list(self._log)
```

- PyTorch 优化器的 lr 存在每个 `param_group` 字典里，修改它即可在下一次 `step()` 生效——这就是所有 lr scheduler 的底层机制。
- ⚠️ `set_lr` 给所有组赋同一个**绝对值**，若有多个组且基础 lr 不同（如对 embedding 用更小 lr），这种写法会把差异抹掉；`LambdaLR` 的"乘数"语义更适合多组场景（测验 Q12）。
- `log` 属性返回副本，外部修改不会影响内部日志。

### 3.6 `plot_schedule_ascii`：文本图

```python
    step_axis = [int(round(i * total / max(1, width - 1))) for i in range(width)]
    rates = [schedule.lr(step) for step in step_axis]
    upper = max(rates)
    ...
    grid = [[" "] * width for _ in range(height)]
    for col, rate in enumerate(rates):
        row = int(round((height - 1) * (1.0 - rate / upper)))
        row = max(0, min(height - 1, row))
        grid[row][col] = "*"
```

- 横轴：`width` 列均匀采样 `[0, total]` 的 step（四舍五入为整数）。纵轴：按 `rate / upper` 映射到行，`row = 0` 是顶端（最大值），所以用 `1 − rate/upper`。
- `[[" "] * width for _ in range(height)]` 用推导式生成**互相独立**的行；若写成 `[[" "] * width] * height`，所有行会是同一个列表对象，改一处全变。
- 每列只放一个 `*`，是"采样点图"而非连线图；纵轴标签 `f"{label:8.6f}"` 保留 6 位小数。
- 输出共 `height + 2` 行（网格 + 坐标轴 + 端点标签），测试 `test_plot_has_correct_number_of_lines` 验证这一点。

### 3.7 CSV 输出

```python
def write_schedule_csv(schedule: CosineWithWarmup, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["step", "lr"])
        for step, rate in schedule.points():
            writer.writerow([step, f"{rate:.10f}"])
```

- `mkdir(parents=True, exist_ok=True)`：自动创建父目录，已存在不报错。
- `newline=""` 是 `csv` 模块的官方要求，防止 Windows 上出现空行。
- 调度 CSV 有 `total + 2` 行（表头 + `[0, total]`）。`write_step_log_csv` 同理，表头为固定模式。
- 注意：`run_demo` 并没有调用任何 CSV 函数，讲义"Production Patterns"里提到的 `outputs/lr_schedule.png` 或 CSV 也没有在 demo 中生成——它们只在测试中被验证。

### 3.8 替代调度与 EWMA

```python
@dataclass
class LinearWarmupConstant:
    def lr(self, step):
        ...
        if self.warmup_steps == 0:
            return self.lr_max
        if step >= self.warmup_steps:
            return self.lr_max
        return self.lr_max * (step / self.warmup_steps)

@dataclass
class InverseSqrtWarmup:
    def lr(self, step):
        ...
        if step <= self.warmup_steps:
            return self.lr_max * (step / self.warmup_steps)
        return self.lr_max * math.sqrt(self.warmup_steps / step)
```

- `LinearWarmupConstant`：消融用基线，回答"衰减到底带来多少收益"。
- `InverseSqrtWarmup`：在 `step = warmup` 处两段都等于 `lr_max`，连续；之后按 `1/√step` 衰减，**永不归零**也没有终点（不需要 `total_steps`），实际值：`warmup=4` 时 `lr(4, 9, 16, 100) = 1.0, 0.667, 0.5, 0.2`。要求 `warmup_steps > 0`，否则 `sqrt(0/step) = 0`，学习率永远为 0。
- 讲义练习 1 要求"添加反平方根变体"，代码其实已经实现了，练习可以改成"在 200 步玩具训练上比较两者最终 loss"。

```python
@dataclass
class EWMA:
    beta: float
    value: float = 0.0
    initialized: bool = False

    def update(self, sample: float) -> float:
        if not self.initialized:
            self.value = float(sample)
            self.initialized = True
            return self.value
        self.value = self.beta * self.value + (1.0 - self.beta) * float(sample)
        return self.value
```

- `v ← β·v + (1−β)·x`。用第一个样本初始化，而不是像 Adam 那样从 0 开始再做偏差修正——两种做法都能避免"开头被拉向 0"。`beta=0.9` 时输入 `1, 2, 3, 4` 得到 `1.0, 1.1, 1.29, 1.561`（已计算）。
- 用途：原始梯度范数噪声大，平滑后再设告警阈值更可靠。demo 未使用。

### 3.9 摘要与 weight decay 分组

```python
def summarize_step_log(log):
    rows = list(log)
    if not rows:
        raise ValueError("step log is empty")
    return StepLogSummary(steps=len(rows), lr_peak=max(row.lr for row in rows), ...,
                          loss_delta=rows[-1].loss - rows[0].loss)
```

- 用生成器表达式求最大值；`list(log)` 先物化，因为 `log` 可能是只能遍历一次的迭代器。

```python
def split_decay_groups(model, weight_decay=0.01,
                       no_decay_names=("bias", "LayerNorm.weight", "layer_norm.weight")):
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        if any(needle in name for needle in no_decay_names):
            no_decay_params.append(param)
        else:
            decay_params.append(param)
```

- 目的：bias 和 LayerNorm 增益不做 weight decay，只衰减权重矩阵。
- ⚠️ **按名字子串匹配有 bug**：已实际运行 `nn.Sequential(nn.LayerNorm(8), nn.Linear(8, 4))`，参数名是 `0.weight, 0.bias, 1.weight, 1.bias`，结果 LayerNorm 增益 `0.weight` 被分进了**衰减组**。只有当模块属性名恰好叫 `LayerNorm`/`layer_norm`（如部分 Hugging Face 模型）时才生效。更稳妥的写法是 `p.ndim < 2` 不衰减（测验 Q9）。
- ⚠️ 该函数**没有被 `TrainState` 使用**，demo 中所有参数都在衰减。

### 3.10 `build_toy_model` 与 `run_demo`

```python
def build_toy_model(in_dim=16, out_dim=4, seed=7):
    torch.manual_seed(seed)
    model = nn.Sequential(nn.Linear(in_dim, 32), nn.GELU(), nn.Linear(32, out_dim))
    inputs = torch.randn(8, in_dim)
    targets = torch.randn(8, out_dim)
    return model, inputs, targets
```

- 参数量：`16×32 + 32 + 32×4 + 4 = 676`。固定 batch `(8, 16) → (8, 4)`，目标是随机数，MSE 回归——模型在"背"这 8 个样本，所以 loss 会稳定下降。
- `torch.manual_seed(7)` 让初始化和数据可复现。

```python
    schedule = CosineWithWarmup(warmup_steps=4, total_steps=20, lr_max=1e-2, lr_min=1e-4)
    state = TrainState(model=model, schedule=schedule, loss_fn=nn.functional.mse_loss)
    for _ in range(20):
        record = state.step(inputs, targets)
        print(f"step={record.step:>3} lr={record.lr:.6f} ...")
```

- ⚠️ 训练 20 次，step 编号 0…19，`lr(20) = lr_min` 从未被用到（最后一步 lr = 0.000195）。这是"`total_steps` 指的是哪一步"的约定问题，测验 Q10 有详细讨论。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 调度写成无状态闭式函数 | 任意 step 可重算、恢复训练只需 `global_step`、无浮点漂移 | 与框架的 `LRScheduler` 对象不直接兼容；可用 `LambdaLR` 包装 |
| 三段在一个函数里、端点精确连续 | 改 `lr_max` 等配置不会让某段错位 | 需要穷举边界测试（本节已做） |
| `step > total` 钉在 `lr_min` | 训练循环多跑几步也处于"有文档的状态" | 掩盖了"循环与调度长度不一致"的配置错误；讲义建议同时打警告日志，但代码没有打 |
| `lr(0) = 0` | 约定清晰、测试好写 | 第 0 步只更新 Adam 矩估计、不动权重；可改为 `(step+1)/warmup` |
| `lr_min` 非零（demo 中 `1e-4`） | 长尾阶段仍在学习 | 需要按 `lr_max` 的比例设置，讲义建议约 10%（demo 只有 1%） |
| 梯度范数逐参数 `.item()` | 不依赖特定 torch 版本 | GPU 上每参数同步一次；生产用 `clip_grad_norm_` 的返回值 |
| 所有 param group 设同一绝对 lr | 简单 | 多组不同 lr 时会被抹平；用乘数语义 |
| 文本图 + CSV | CI 中无需图形库、可 diff | 不如 PNG 直观；讲义练习 5 讨论两者作为 CI 默认值的取舍 |
| 按名字划分 no-decay 组 | 对 HF 命名的模型直接可用 | 对 `nn.Sequential` 等会漏掉 LayerNorm；用 `p.ndim < 2` 更通用 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，`int \| None` 等新语法可在旧版本使用 |
| `try / except ImportError ... raise ... from exc` | 导入 torch | 捕获缺包并抛出更友好的错误，保留异常链 |
| `@dataclass` 与默认值 | `lr_min: float = 0.0` | 自动生成 `__init__`/`__repr__`/`__eq__`；有默认值的字段必须排在无默认值字段之后 |
| `__post_init__` | `CosineWithWarmup.__post_init__` | dataclass 构造完成后自动调用，常用于校验 |
| 类型注解 | `def lr(self, step: int) -> float`、`Callable[[Tensor, Tensor], Tensor]` | 只是提示，运行时不强制 |
| `X \| None` 联合类型 | `num_steps: int \| None = None` | 等价于 `Optional[int]` |
| `@property` | `def log(self) -> list[StepLog]` | 像属性一样访问方法：`state.log` |
| 私有约定 | `self._log` | 下划线开头表示"内部使用" |
| f-string 格式符 | `{record.step:>3}`、`{rate:.6f}`、`{label:8.6f}`、`{x:.10f}` | 右对齐宽 3；6 位小数；宽 8 含 6 位小数 |
| 列表推导式 | `[(step, self.lr(step)) for step in range(upper + 1)]` | 一行生成列表 |
| 嵌套推导式生成二维网格 | `[[" "] * width for _ in range(height)]` | 每行是独立列表；`[[...]] * n` 会共享同一行 |
| 生成器表达式 | `max(row.lr for row in rows)`、`any(needle in name for needle in ...)` | 不建中间列表，惰性求值 |
| `enumerate` | `for col, rate in enumerate(rates)` | 同时拿下标和值 |
| `with` 上下文管理器 | `with path.open("w", ...) as fh:` | 自动关闭文件 |
| `pathlib.Path` | `path.parent.mkdir(parents=True, exist_ok=True)` | 面向对象的路径操作 |
| 链式比较 | `if not 0 < self.beta < 1:` | 等价于 `0 < beta and beta < 1` |
| 数字下划线 | `self.schedule.lr(10_000)`（测试中） | 提高可读性，等于 10000 |
| `sys.exit(run_demo())` + `if __name__ == "__main__":` | 文件末尾 | 作为脚本运行时执行 demo，并把返回值作为进程退出码；被 import 时不执行 |
| torch：`zero_grad(set_to_none=True)`、`.detach()`、`.item()` | `TrainState.step` | 清梯度为 None；切断计算图；取 Python 标量 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，torch 2.14 CPU，耗时约 6 秒，主要是导入 torch）：

```text
step=  0 lr=0.000000 grad_l2=1.008009 loss=1.024962   ← lr=0，权重不变
step=  1 lr=0.002500 grad_l2=1.008009 loss=1.024962   ← 与上一行完全相同
step=  2 lr=0.005000 grad_l2=0.967476 loss=0.984344
step=  3 lr=0.007500 grad_l2=0.893771 loss=0.907511
step=  4 lr=0.010000 grad_l2=0.800174 loss=0.802678   ← warmup 终点 = lr_max
step=  5 lr=0.009905 grad_l2=0.701427 loss=0.680955   ← 余弦开头很平
...
step= 12 lr=0.005050 grad_l2=0.541742 loss=0.273171   ← 衰减中点 = (1e-2 + 1e-4)/2
...
step= 19 lr=0.000195 grad_l2=0.458796 loss=0.185674   ← 未到 lr_min=1e-4

learning rate schedule:
0.010000 |        ******
0.008889 |              ****
0.007778 |      **          **
...
0.000000 | *                                  *****
          +----------------------------------------
           step 0                           step 20

summary: steps=20 lr_peak=0.010000 grad_l2_peak=1.008009 loss_delta=-0.839288
```

逐项解读：

- **前两行一模一样**：第 0 步 lr = 0，AdamW 的梯度更新和解耦权重衰减都乘 lr，所以权重不变（已用参数快照验证 `torch.equal` 全真）；第 1 步面对的是同一组权重、同一个 batch，梯度与 loss 自然相同。但 AdamW 的 `state["step"]` 已经是 1，矩估计吸收了第 0 步的梯度。
- **warmup 阶段**：lr 按 `0.0025` 等差增长，正好是 `1e-2 / 4`。
- **衰减中点**：step 12 的 `progress = (12 − 4)/16 = 0.5`，lr = 0.00505，即 `(lr_max + lr_min)/2`。
- **梯度范数**：从 1.008 一路降到 0.459。在固定 batch 上拟合，梯度随 loss 下降而变小；step 9–11 有小幅回升（0.537 → 0.545），说明在峰值 lr 附近参数仍在较大幅度移动。没有尖峰，训练健康。
- **loss**：1.025 → 0.186，`loss_delta = −0.839`。后期 lr 很小，loss 每步只降约 0.003–0.005，体现了余弦尾部的"精调"。
- **文本图**：最底一行左边的 `*` 是 step 0（lr = 0），右侧一串 `*****` 是接近 `lr_min` 的尾部——由于纵轴从 0 到 0.01 只有 10 行，`1e-4` 与 0 落在同一行，图上看不出 `lr_min` 非零。顶部 `******` 是峰值附近；由于每列只放一个点，warmup 段呈"阶梯"状。
- **summary**：`grad_l2_peak` 出现在第 0 步，这对随机初始化的模型是正常的；若峰值出现在 warmup 结束之后，就是讲义所说"peak 太激进"的信号。

测试运行结果见第 9 节（27 个测试全部通过）。

---

## 7. 动手改一改

1. **调度表打印**：在 `run_demo` 末尾调用 `write_schedule_csv(schedule, Path("outputs/lr_schedule.csv"))` 和 `write_step_log_csv(state.log, ...)`，用 `wc -l` 确认行数分别为 `total + 2` 与 `21`。
2. **修 off-by-one**：把 demo 改成训练 `total_steps + 1` 步，确认最后一行 lr 为 `0.000100`；再尝试把 warmup 改为 `(step + 1) / warmup_steps`，看哪些测试会失败、为什么。
3. **修 `split_decay_groups`**：改为 `p.ndim < 2` 不衰减，并把它接入 `TrainState`（`torch.optim.AdamW(split_decay_groups(model, weight_decay), ...)`），同时改写测试使其断言 LayerNorm 增益在不衰减组（测验 Q9）。
4. **讲义练习 1**：用 `InverseSqrtWarmup(4, 1e-2)` 与 `LinearWarmupConstant(4, 1e-2)` 替换调度（`TrainState` 只调用 `schedule.lr`，鸭子类型即可），在 200 步上比较最终 loss。
5. **讲义练习 3**：写"连续性"测试，但用测验 Q11 推导的 `max(lr_max/warmup, (lr_max−lr_min)·π/(2D))` 作为上界，并用 `warmup=10, total=12` 证明原上界会失败。
6. **讲义练习 2（进阶）**：实现 warm restart——在 `total/2` 处再做一次短 warmup，用 `EWMA(beta=0.9)` 平滑梯度范数并打印，观察重启时梯度范数与 loss 的反应。

---

## 8. 常见坑

- **把 `total_steps` 当成"训练循环次数"**：本节约定下 `lr(total_steps) = lr_min`，需要 `total_steps + 1` 次更新才走完调度；demo 就没有走完。
- **`warmup_steps = 0` 时除零**：天真的 `lr_max * step / warmup_steps` 会在 0 处崩溃，本节用 `warmup_steps > 0 and ...` 规避。
- **余弦段 `progress > 1` 继续计算**：`cos` 会回升，学习率"反弹"。必须有地板分支。
- **用"上一步 lr × 系数"递推**：长时间训练会积累浮点误差，恢复训练也难以对齐；用 `lr(step)` 直接计算。
- **恢复训练时 step 从 0 开始**：会重新 warmup；`global_step` 必须进 checkpoint（第 47 节）。
- **`scheduler.step()` 放在 `optimizer.step()` 之前**：用 PyTorch 调度器时会跳过第一个 lr 值（会出警告）。
- **以为 weight decay 只作用于权重矩阵**：`TrainState` 对所有参数一视同仁；`split_decay_groups` 的名字匹配在 `nn.Sequential` 上漏掉 LayerNorm。
- **梯度范数在裁剪之后再记录**：会看不到真正的尖峰。本节在 `optimizer.step()` 前、无裁剪时记录；加了裁剪（第 45 节）后应记录裁剪前的范数。
- **文本图里看不出 `lr_min`**：纵轴分辨率不足时小值会和 0 重合，判断地板值请看 CSV。

---

## 9. 测试在验证什么

`tests/__init__.py` 是一个 0 字节的空文件，作用只是把 `tests/` 标记为 Python 包，使 `unittest discover` 与 pytest 能以包的方式导入测试模块。`test_schedule.py` 开头用 `sys.path.insert(0, str(HERE.parent))` 把 `code/` 加入搜索路径，从而 `from main import ...`。

运行方式（均已实际运行）：

```bash
cd code && python3 -m unittest discover tests -v   # Ran 27 tests ... OK
cd code && python3 -m pytest -q tests              # 27 passed
python3 -m unittest discover code/tests            # 从小节根目录运行也可以，27 个 OK
```

| 测试类 | 测试 | 验证的性质 |
|-------|------|----------|
| `ScheduleBoundaryTests`（`warmup=10, total=100, lr_max=1.0, lr_min=0.1`） | `test_step_zero_is_exactly_zero` | `lr(0) == 0.0`（精确相等） |
| | `test_warmup_endpoint_is_exactly_lr_max` | `lr(10) ≈ 1.0`（10 位小数） |
| | `test_total_endpoint_is_exactly_lr_min` | `lr(100) ≈ 0.1` |
| | `test_past_total_pins_at_lr_min` | `lr(101)`、`lr(10_000)` 精确等于 0.1 |
| | `test_negative_step_raises` | `lr(-1)` 抛 `ValueError` |
| `ScheduleShapeTests` | `test_warmup_is_linear` | `step ∈ [0, 10)` 时 `lr = step/10` |
| | `test_decay_is_monotonic_non_increasing` | 11…100 步单调不增（容差 1e-12） |
| | `test_zero_warmup_starts_at_peak` | `warmup=0` 时 `lr(0) = lr_max` |
| `ScheduleValidationTests` | 三个测试 | `warmup > total`、`lr_max = 0`、`lr_min > lr_max` 在构造时抛错 |
| `GradientNormTests` | `test_gradient_norm_matches_known_value` | `[3,0,4]` 与 `[0,0]` 拼接后范数为 5（勾股数） |
| | `test_gradient_norm_ignores_none_grads` | `grad is None` 的参数被跳过，结果 0 |
| `TrainStateTests` | `test_train_state_drives_optimizer_with_schedule` | 10 步中第 0 条记录 lr 为 0、第 4 条为 `lr_max`、最后一条等于 `lr(9)`——证明 `TrainState` 确实按 `global_step` 查调度 |
| | `test_loss_decreases_across_steps` | 32 步后 loss 低于第一步（端到端冒烟测试） |
| `PlotAndCsvTests` | `test_plot_has_correct_number_of_lines` | 文本图行数为 `height + 2` |
| | `test_plot_rejects_tiny_dimensions` | `width=2` 抛错 |
| | `test_write_schedule_csv_round_trip` | 表头为 `["step","lr"]`，首行 step 0、末行 step 10 |
| | `test_write_step_log_csv_records_all_columns` | 表头为固定模式，2 条日志 + 表头共 3 行 |
| `AlternativeScheduleTests` | `test_linear_warmup_constant_holds_at_peak` | `lr(0)=0`、`lr(5)=1`、`lr(100)=1` |
| | `test_inverse_sqrt_warmup_decays` | `lr(4)=1.0`、`lr(16)=0.5` |
| `EWMATests` | 三个测试 | 第一个样本直接通过；常数流收敛到该常数；`beta` 为 0 或 1 时拒绝 |
| `SummaryAndGroupTests` | `test_summary_extracts_peaks_and_delta` | 峰值、步数、`loss_delta = −1.5` |
| | `test_summary_rejects_empty_log` | 空日志抛错 |
| | `test_split_decay_separates_bias_and_layernorm` | 只断言两组都非空 |

值得注意的测试缺口：

- `test_split_decay_separates_bias_and_layernorm` **名不副实**：两个 bias 已足以让不衰减组非空，LayerNorm 增益实际被分进了衰减组，测试却通过（见 3.9 与测验 Q9）。
- 没有测试余弦段中间某点的具体数值（如 `lr(55) = 0.55`），只测了单调性；若有人把 `0.5 * (1 + cos)` 写错成 `cos` 的其他变形但仍单调，边界测试可能抓不住中段错误。
- 没有测试"demo 的训练步数是否走完调度"，也没有讲义练习 3 的连续性测试。
