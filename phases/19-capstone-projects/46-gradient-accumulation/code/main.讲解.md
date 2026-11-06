# 代码讲解 · main.py

> **所属小节**：阶段 19 · 综合项目 · 第 46 节 Gradient Accumulation ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py [--micro-batch 4] [--accum-grid 1,2,4,8,16] [--num-steps 25] [--seed 0] [--lr 0.05] [--no-write]`（在 `code/` 目录下）；测试：`python3 -m pytest -q test_main.py` 或 `python3 -m unittest test_main -v` ｜ **依赖**：`torch`（第三方，CPU 即可）；其余为标准库（`argparse`、`json`、`math`、`time`、`dataclasses`、`pathlib`、`typing`）
>
> **注意**：不加 `--no-write` 时脚本会**覆盖**仓库中的 `outputs/accum-curve.json`。本讲解的运行结果均使用 `--no-write` 得到。

---

## 1. 这份代码在考察什么

这份代码用一个三层 MLP 和随机合成数据，把"梯度累积"拆成三件可验证的事：

1. **等价性证明**（`equivalence_check`）：同一初始化的两个模型，一个对 16 个样本做一次反向，另一个把 16 个样本切成 4 份、每份 loss 除以 4 后累积反向。比较两者的梯度和 SGD 更新后的参数，最大差应小于 1e-4。
2. **sync-on-last-step 模式**（`train_one_optimizer_step` + `no_sync_context`）：除最后一个 micro-batch 外都进入"不同步"上下文，用计数器验证每个有效步只同步一次。单进程中上下文是空操作，但调用位置与真实 DDP 完全一致。
3. **吞吐曲线**（`sweep_effective_batches`）：固定 micro-batch，扫描 `accum_steps`，记录样本/秒、每步中位耗时、同步次数和平均 loss，写成 JSON。

> 一句话：**`backward()` 是累加的，所以把 loss 除以 N、攒够 N 次再 step，就等于一次大 batch——但要记住"除以 N"和"只 step 一次"这两件事**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `HERE` / `OUT_DIR` / `LOG_PATH` | 模块常量 | 输出文件路径 `../outputs/accum-curve.json` | 产物位置 |
| `StepResult` | dataclass | 单步结果（定义了但**未被使用**） | — |
| `CurvePoint` | dataclass | 扫描曲线上的一个点 | 吞吐记录 |
| `seed_everything` | 函数 | `torch.manual_seed` | 可复现 |
| `synthetic_batch` | 函数 | 随机输入 + 随机整数标签 | 合成数据 |
| `make_model` | 函数 | `Linear-GELU-Linear-GELU-Linear` | 演示模型 |
| `global_grad_norm` | 函数 | 全局梯度 L2 范数 | 监控 |
| `zero_grads` | 函数 | 原地把梯度清零 | 窗口开始 |
| `loss_scaled_for_accum` | 函数 | `loss_fn(...) / accum_steps` | loss 缩放 |
| `train_one_optimizer_step` | 函数 | 一个有效步：清零 → N 次前向/缩放反向 → 一次 step | 累积循环 |
| `_NoSyncCtx` / `no_sync_context` | 类 / 函数 | DDP `no_sync()` 的单进程替身 | sync-on-last |
| `run_config` | 函数 | 一个 `(effective_batch, accum)` 配置训练 `num_steps` 步并汇总 | 单点测量 |
| `sweep_effective_batches` | 函数 | 遍历 accum 网格 | 吞吐曲线 |
| `equivalence_check` | 函数 | 全 batch vs 累积，返回梯度/参数最大差 | 等价性证明 |
| `write_curve` | 函数 | 写带 schema 的 JSON | 产物 |
| `parse_args` / `main` | 函数 | 命令行入口 | — |

数据流：`main` → `equivalence_check`（打印并断言 < 1e-4）→ `sweep_effective_batches` →（每个 accum）`run_config` →（每步）`synthetic_batch` × accum → `train_one_optimizer_step` → 汇总为 `CurvePoint` → 打印表格 →（可选）`write_curve`。

---

## 3. 逐段精讲

### 3.1 路径常量与两个 dataclass

```python
HERE = Path(__file__).parent
OUT_DIR = HERE.parent / "outputs"
LOG_PATH = OUT_DIR / "accum-curve.json"

@dataclass
class CurvePoint:
    effective_batch: int
    accum_steps: int
    micro_batch: int
    avg_loss: float
    samples_per_sec: float
    median_step_ms: float
    sync_calls: int
    steps: int
```

- `Path(__file__).parent` 定位到 `code/`，所以无论从哪个目录运行，输出都写到小节的 `outputs/` 下。
- `CurvePoint` 是 JSON 的一行，字段名就是讲义列出的指标；`asdict` 把它转成字典。
- `StepResult` 定义了 9 个字段，但整个文件没有用到它（讲义 skill 文件说"Emit a small JSON record per effective step"，代码只输出了按配置汇总的点）。

### 3.2 合成数据与模型

```python
def synthetic_batch(batch_size, in_dim, out_dim, gen):
    x = torch.randn(batch_size, in_dim, generator=gen)
    target = torch.randint(low=0, high=out_dim, size=(batch_size,), generator=gen)
    return x, target

def make_model(in_dim, hidden, out_dim):
    return nn.Sequential(nn.Linear(in_dim, hidden), nn.GELU(),
                         nn.Linear(hidden, hidden), nn.GELU(),
                         nn.Linear(hidden, out_dim))
```

- 用独立的 `torch.Generator` 生成数据，使数据流不受模型初始化消耗的全局随机数影响。
- ⚠️ 标签与输入**完全无关**，模型无规律可学。交叉熵会停在 `ln(out_dim)` 附近：扫描用 `out_dim=16`，`ln 16 ≈ 2.7726`，实测各配置 2.776–2.780。所以 `avg_loss` 只能证明"代码在跑"，不能比较配置优劣。
- 扫描模型参数量：`64·128+128 + 128·128+128 + 128·16+16 = 26,896`；等价性检查模型（32→48→48→8）为 4,328。
- 模型里没有 BatchNorm，这是"累积严格等价"的前提之一（BatchNorm 的统计量依赖 micro-batch）。

### 3.3 梯度范数与清零

```python
def global_grad_norm(model):
    total = 0.0
    for p in model.parameters():
        if p.grad is None:
            continue
        total += float(p.grad.detach().pow(2).sum().item())
    return math.sqrt(total)

def zero_grads(model):
    for p in model.parameters():
        if p.grad is not None:
            p.grad.detach_()
            p.grad.zero_()
```

- `global_grad_norm` 与第 44、45 节相同；在 `train_one_optimizer_step` 中算出后返回，但 `run_config` 用 `_grad_norm` 接住后**丢弃**了。
- `zero_grads` 等价于 `optimizer.zero_grad(set_to_none=False)`：`detach_()` 把梯度从可能存在的计算图上摘下（`create_graph=True` 时梯度本身有 grad_fn），`zero_()` 原地清零，保留张量对象以复用内存。现代 PyTorch 默认 `set_to_none=True`，更省内存。
- **清零的时机**是窗口开始，而不是每个 micro-batch 之后——这正是累积能发生的原因。

### 3.4 loss 缩放与一个有效步

```python
def loss_scaled_for_accum(logits, target, accum_steps, loss_fn):
    raw = loss_fn(logits, target)
    return raw / accum_steps
```

- 设全 batch 有 B 个样本、切成 N 份、每份 `m = B/N` 个。`CrossEntropyLoss` 默认 mean：每份 loss 是 `(1/m)Σℓᵢ`，除以 N 后是 `(1/B)Σℓᵢ`（对该份样本求和）。N 份的梯度相加，正好是 `(1/B)Σ_{全部} ∇ℓᵢ`，即全 batch mean loss 的梯度。
- 前提：**各份大小相同**。`run_config` 和 `equivalence_check` 都用 `assert ... % accum_steps == 0` 保证整除。若切分不等（如 10 + 6），每个样本的权重变成 `1/(N·m_k)`，已实测梯度最大差 0.037（测验 Q5）。

```python
def train_one_optimizer_step(model, optimizer, micro_batches, loss_fn, *,
                             no_sync_until_last, sync_counter):
    accum_steps = len(micro_batches)
    zero_grads(model)
    total = 0.0
    for i, (x, y) in enumerate(micro_batches):
        is_last = i == accum_steps - 1
        if no_sync_until_last and not is_last:
            with no_sync_context(model):
                logits = model(x)
                loss = loss_scaled_for_accum(logits, y, accum_steps, loss_fn)
                loss.backward()
        else:
            logits = model(x)
            loss = loss_scaled_for_accum(logits, y, accum_steps, loss_fn)
            loss.backward()
            sync_counter[0] += 1
        total += float(loss.detach().item()) * accum_steps
    grad_norm = global_grad_norm(model)
    optimizer.step()
    return total / accum_steps, grad_norm
```

逐行要点：

- `accum_steps = len(micro_batches)`：累积步数由传入的列表长度决定，不需要额外参数。
- `*` 之后的参数是**仅限关键字参数**，调用时必须写 `no_sync_until_last=True`，避免布尔位置参数的歧义。
- 非最后的 micro-batch 在 `no_sync_context` 内完成**前向和反向**——这与 DDP 的要求一致（`no_sync` 必须包住前向，否则仍会同步）。
- `sync_counter` 是一个单元素列表 `[0]`：Python 的整数不可变，用列表包一层才能在函数内修改并让调用方看到（"可变容器当引用"）。只在会同步的分支 `+= 1`，所以每个有效步恰好加 1。
- `total += loss.item() * accum_steps`：把缩放后的 loss 乘回去得到原始 loss；最后除以 `accum_steps` 得到**窗口内原始 loss 的平均**。docstring 说返回"total_unscaled_loss"，实际是平均值。
- 每次 `.item()` 都是一次同步点；在 GPU 上更好的做法是把 loss 累加成张量，窗口结束再 `.item()` 一次。
- `optimizer.step()` 只调用一次：优化器状态、步数计数都按有效步推进（已用 AdamW 实测：3 个有效步 × 4 个 micro-batch 后 `state["step"] = 3`）。
- 没有梯度裁剪、没有 AMP、没有学习率调度——组合方式见测验 Q11。

### 3.5 `no_sync_context`：DDP 的替身

```python
class _NoSyncCtx:
    def __init__(self, model):
        self.model = model
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False

def no_sync_context(model):
    """Stand-in for DDP no_sync. ..."""
    return _NoSyncCtx(model)
```

- 一个什么也不做的上下文管理器：`__enter__` 返回自身，`__exit__` 返回 `False`（不吞异常）。标准库里等价的是 `contextlib.nullcontext()`。
- 真实 DDP 中应替换为 `model.no_sync()`：它让本次反向不触发梯度 all-reduce，梯度只在本地累积；窗口最后一次反向时 DDP 把累积好的梯度一次归约。讲义练习 4 要求接入真实 DDP 并验证同步次数减少 N−1。
- 为什么"跳过同步"仍然正确：all-reduce 是线性运算（求平均），`avg(g₁) + avg(g₂) = avg(g₁ + g₂)`，先在本地累加再归约一次，与每次都归约再累加结果相同，但通信从 N 次降为 1 次。

### 3.6 `run_config`：单个配置的测量

```python
    assert effective_batch % accum_steps == 0, "effective_batch must divide by accum_steps"
    micro_batch = effective_batch // accum_steps
    seed_everything(seed)
    gen = torch.Generator()
    gen.manual_seed(seed)
    model = make_model(in_dim, hidden, out_dim)
    optimizer = torch.optim.SGD(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()
    ...
    for step in range(num_steps):
        t0 = time.perf_counter()
        micro_batches = [synthetic_batch(micro_batch, in_dim, out_dim, gen) for _ in range(accum_steps)]
        avg_loss, _grad_norm = train_one_optimizer_step(model, optimizer, micro_batches, loss_fn,
                                                        no_sync_until_last=True, sync_counter=sync_counter)
        wall_ms = (time.perf_counter() - t0) * 1000.0
        ...
    total_wall = time.perf_counter() - wall_start
    sps = total_samples / max(total_wall, 1e-6)
    step_times_ms.sort()
    median_ms = step_times_ms[len(step_times_ms) // 2]
```

- 用 `assert` 做参数校验：注意 `python -O` 会移除所有 assert，生产代码应改为 `raise ValueError`。测试 `test_effective_batch_must_divide_accum` 正是依赖 `AssertionError`。
- 每个配置都用同一个种子重新初始化模型，配置之间互不影响。
- 优化器是**无动量的 SGD**——没有任何优化器状态，讲义所说"optimizer state advances once per effective step"在这里无从体现（讲义练习 3 要求换成 AdamW 验证）。
- ⚠️ 计时区间包含数据生成（`synthetic_batch`），这部分开销与 accum 成正比，被算进了"训练吞吐"。
- `time.perf_counter()` 是单调高精度计时器，适合测量耗时（不要用 `time.time()`）。
- 中位数取 `sorted[len // 2]`：长度为偶数时取的是上中位数，对 25 步（奇数）是精确中位数。
- `max(total_wall, 1e-6)` 防止除零。
- 所有配置使用同一个 `lr`，没有按有效 batch 缩放学习率（讲义"Use It"提到大有效 batch 需要缩放 lr 和 warmup）。

### 3.7 `equivalence_check`：等价性证明

```python
    seed_everything(seed)
    gen_a = torch.Generator(); gen_a.manual_seed(seed)
    x, y = synthetic_batch(big_batch, in_dim, out_dim, gen_a)

    seed_everything(seed)
    model_full = make_model(in_dim, hidden, out_dim)
    ...
    loss_full = loss_fn(model_full(x), y)
    loss_full.backward()
    full_grads = [p.grad.detach().clone() for p in model_full.parameters()]
    opt_full.step()
    full_params_after = [p.detach().clone() for p in model_full.parameters()]

    seed_everything(seed)
    model_accum = make_model(in_dim, hidden, out_dim)
    ...
    chunks_x = list(torch.split(x, micro, dim=0))
    chunks_y = list(torch.split(y, micro, dim=0))
    for cx, cy in zip(chunks_x, chunks_y):
        scaled = loss_fn(model_accum(cx), cy) / accum_steps
        scaled.backward()
    accum_grads = [p.grad.detach().clone() for p in model_accum.parameters()]
    accum_params_before = [p.detach().clone() for p in model_accum.parameters()]
    opt_accum.step()
```

- **两次 `seed_everything(seed)` 再建模型**，保证两个模型的初始权重逐位相同（`params_init_match` 用 `torch.equal` 验证）。
- `torch.split(x, micro, dim=0)` 把 `(16, 32)` 切成 4 个 `(4, 32)` 的视图（不复制数据）。
- `.detach().clone()`：先断开计算图再复制，得到独立的快照，后续 `step()` 修改参数不会影响快照。
- 比较的是**逐元素最大绝对差**：`(a - b).abs().max()`。
- 一个小瑕疵：`accum_params_before` 是在累积反向**之后**才拍的快照，而 `full_params_before` 在反向之后、step 之前——两者都在 step 之前，所以比较仍然有效（反向不改参数）。
- 讲义练习 5 要求比较 2×8 与 4×4 的切分：已实测差异同样是 7.45e-9 量级，不需要放宽容差；只有不等分时才会出现大的差异。

### 3.8 输出与入口

```python
def write_curve(points, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": "accum-curve.v1", "points": [asdict(p) for p in points]}
    path.write_text(json.dumps(payload, indent=2) + "\n")
```

- 带版本号的 `schema` 字段，下游读取时可以校验格式。
- `Path.write_text` 一次写完整个文件（非原子写入；第 47 节会讲临时文件 + `os.replace` 的原子写法）。

```python
def main() -> int:
    args = parse_args()
    accum_grid = [int(s) for s in args.accum_grid.split(",") if s.strip()]
    eq = equivalence_check()
    print(json.dumps(eq, indent=2))
    assert eq["max_grad_diff"] < 1e-4, ...
    assert eq["max_param_diff"] < 1e-4, ...
    points = sweep_effective_batches(...)
    header = f"{'eff_batch':>10}  {'accum':>5}  ..."
    ...
    if not args.no_write:
        write_curve(points, LOG_PATH)

if __name__ == "__main__":
    raise SystemExit(main())
```

- `--accum-grid` 以逗号分隔字符串传入，推导式中 `if s.strip()` 过滤空项（允许 `"1,2,"` 这种写法）。
- `--no-write` 是 `store_true` 开关：出现即为 True。
- `f"{'eff_batch':>10}"`：对字符串常量也可以用格式符右对齐，表头与数据列宽一致。
- `raise SystemExit(main())` 与 `sys.exit(main())` 等价，不需要 `import sys`。
- ⚠️ 仓库中的 `outputs/accum-curve.json` 只有 3 个点、每点 8 步，是用 `--accum-grid 1,2,4 --num-steps 8` 生成的（已用 `--no-write` 复现出相同的 loss 列 `2.7746/2.7787/2.7735`），与默认参数的输出不一致；讲义没有说明。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| loss 除以 `accum_steps` 而不是梯度除以 N | 一次除法、在反向前完成，与 AMP 的 loss scaling 自然兼容 | 只在等大 micro-batch + mean 归约时严格等价；变长 token 要按总 token 数归一化 |
| 窗口开始时清零、末尾 step 一次 | 让 `backward()` 的累加语义直接实现累积 | 中途 step 或清零都会悄悄破坏结果 |
| `no_sync_context` 空实现 | 单进程可跑、调用位置与 DDP 相同 | 演示不出通信节省；生产用 `model.no_sync()` |
| 可变列表当计数器 | 无需类或全局变量就能在函数间累加 | 可读性一般；生产中用指标对象 |
| 合成随机数据 + 随机标签 | 无需下载数据、完全可复现 | loss 无意义，只能验证机制不能验证效果 |
| 无动量 SGD | 等价性检查中"参数差 = lr × 梯度差"，结论直观 | 体现不出优化器状态按有效步推进；练习 3 换 AdamW |
| 计时包含数据生成 | 实现简单 | 吞吐数字偏低且随 accum 变化；应只计训练部分或预生成数据 |
| `assert` 做参数校验 | 简短 | `python -O` 下失效；用 `ValueError` |
| 默认写 `outputs/` | 产物可被 notebook 复用 | 每次运行都会改动仓库文件；需要 `--no-write` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值 |
| `Path(__file__).parent` 与 `/` 拼接 | `HERE.parent / "outputs"` | `pathlib` 用 `/` 运算符拼路径 |
| `@dataclass` + `asdict` | `asdict(p) for p in points` | dataclass 转字典，便于 JSON 序列化 |
| 类型注解 `List[...]`、`tuple[torch.Tensor, torch.Tensor]` | 函数签名 | `typing.List` 与内置 `list[...]` 两种写法混用，效果相同 |
| 仅限关键字参数 `*` | `def train_one_optimizer_step(..., *, no_sync_until_last, sync_counter)` | `*` 之后的参数必须按名字传 |
| 可变对象当"引用" | `sync_counter = [0]`、`sync_counter[0] += 1` | 在函数内修改列表元素，调用方可见 |
| 上下文管理器协议 | `_NoSyncCtx.__enter__` / `__exit__` | 自定义 `with` 语句的进入与退出行为；`__exit__` 返回 False 表示不吞异常 |
| `enumerate` + 元组解包 | `for i, (x, y) in enumerate(micro_batches)` | 同时拿下标与成对元素 |
| 列表推导式 | `[synthetic_batch(...) for _ in range(accum_steps)]` | `_` 表示不用的循环变量 |
| 带条件的推导式 | `[int(s) for s in args.accum_grid.split(",") if s.strip()]` | 过滤空字符串 |
| `zip` | `for a, b in zip(full_grads, accum_grads)` | 并行遍历两个序列 |
| 一行多语句 `;` | `gen_a = torch.Generator(); gen_a.manual_seed(seed)` | 合法但不推荐 |
| `assert cond, msg` | `assert effective_batch % accum_steps == 0, "..."` | 条件为假时抛 `AssertionError`；`-O` 下被移除 |
| `all(...)` 与生成器 | `all(torch.equal(a, b) for a, b in zip(...))` | 全部为真才返回 True，遇假短路 |
| `argparse` | `p.add_argument("--no-write", action="store_true")` | 命令行解析；`--accum-grid` 自动变成 `args.accum_grid` |
| f-string 对齐 | `f"{p.samples_per_sec:>10.1f}"`、`f"{'eff_batch':>10}"` | 右对齐宽 10、1 位小数 |
| `time.perf_counter()` | `t0 = time.perf_counter()` | 单调高精度计时 |
| `json.dumps(..., indent=2)` | 打印等价性结果 | 美化输出 |
| `raise SystemExit(main())` | 文件末尾 | 以 `main()` 的返回值作为退出码 |
| torch：`torch.split`、`.detach().clone()`、`torch.equal` | `equivalence_check` | 切分视图；独立快照；逐位比较 |

---

## 6. 运行结果解读

实际运行（`python3 main.py --no-write`，torch 2.14 CPU，约 3 秒）：

```text
equivalence check (full batch vs accumulated)
{
  "max_grad_diff": 7.450580596923828e-09,
  "max_param_diff": 7.450580596923828e-09,
  "params_init_match": true
}
equivalence holds. running sweep...
 eff_batch  accum  micro         sps   median_ms   syncs      loss
         4      1      4      5876.3        0.59      25    2.7768
         8      2      4      8057.4        0.92      25    2.7799
        16      4      4     10321.1        1.46      25    2.7798
        32      8      4     11975.6        2.65      25    2.7760
        64     16      4     12230.4        4.81      25    2.7762
```

逐项解读：

- **`max_grad_diff = 7.45e-9`**：约等于 `2^-27`，是 float32 在梯度量级（本例全 batch 梯度范数约 0.30）上的舍入误差——来自求和顺序不同（一次 16 项求和 vs 4 次 4 项求和再相加）。远小于 1e-4 阈值。
- **`max_param_diff = 7.45e-9`**：SGD 一步 `p -= 0.1 × g`，参数差 ≈ `0.1 × 梯度差`，再叠加一次舍入，所以同一量级。
- **`params_init_match: true`**：两个模型初始化逐位相同，排除了"差异来自初始化"的可能。
- **`syncs` 恒为 25**：每个有效步同步一次，与 accum 无关。在真实 DDP 中，若不用 `no_sync`，同步次数会是 `25 × accum`（accum=16 时 400 次）。
- **`median_ms` 近似线性增长**：0.59 → 0.92 → 1.46 → 2.65 → 4.81 ms，每多一个 micro-batch 约增加 0.27 ms，外加约 0.3 ms 的固定开销（清零、范数、`step()`）。
- **`sps` 先升后平**：5876 → 12230，从 accum 8 到 16 只增加约 2%。固定开销被摊薄之后，吞吐受单个 micro-batch 前向反向的计算速度约束。这正是讲义所说的"diminishing return"。第一个配置还承担了 PyTorch 首次运行的预热开销，数值偏低。CPU 上这些数字每次运行都有波动。
- **`loss` 都约 2.777**：标签随机，交叉熵停在 `ln 16 = 2.7726` 附近，各配置之间的差异是噪声。

与仓库中 `outputs/accum-curve.json` 的对比：该文件只有 accum = 1, 2, 4 三个点、`steps = 8`。用 `--accum-grid 1,2,4 --num-steps 8 --no-write` 复现得到 loss `2.7746 / 2.7787 / 2.7735`，与文件中的 `avg_loss` 一致；样本/秒随机器不同而不同（文件中约 10.6k–12.7k，本机这次为 2.9k–8.6k，短运行受预热影响更大）。

测试运行结果见第 9 节（6 个测试全部通过）。

---

## 7. 动手改一改

1. **讲义练习 2**：加一个 `divide: bool` 参数，比较不除以 N 时 SGD 与 AdamW 的参数差（测验 Q9 实测：SGD 约 0.0215，AdamW 约 7.8e-4），思考为什么 Adam 对这个 bug 不敏感却仍然必须修。
2. **讲义练习 3**：把 `run_config` 的优化器换成 `torch.optim.AdamW`，在每个有效步后打印 `optimizer.state[p]["step"]`，确认它等于有效步数。
3. **讲义练习 5 扩展**：让 `equivalence_check` 支持传入任意切分列表（如 `[10, 6]`），观察不等分时的差异，再改用 `reduction="sum"` 并除以总样本数修正它。
4. **修计时**：把数据生成移到 `t0` 之前，并把 loss 累加改为张量累加、窗口末尾 `.item()` 一次，重新扫描，比较吞吐曲线的形状变化。
5. **组合第 44、45 节**：在 `train_one_optimizer_step` 末尾加上全局范数裁剪和调度，按测验 Q11 的顺序接入 GradScaler（CPU 上可用 `enabled=True` 测试）。
6. **讲义练习 4（进阶）**：用 `torch.distributed` 的 gloo 后端起 2 个 CPU 进程，把模型包成 `DistributedDataParallel`，让 `no_sync_context` 返回 `model.no_sync()`；用 DDP 的通信 hook 统计 all-reduce 次数，确认每个有效步只有 1 次。

---

## 8. 常见坑

- **忘记除以 `accum_steps`**：SGD 下步长放大 N 倍；Adam 下看似无事，但梯度范数、裁剪、FP16 溢出都会出问题。
- **每个 micro-batch 后 `zero_grad()`**：累积被清掉，等于只用最后一个 micro-batch 训练。
- **每个 micro-batch 后 `optimizer.step()`**：变成 N 次小 batch 更新，优化器状态与调度以 N 倍速度推进。
- **micro-batch 不等大 / 按 token 平均**：除以 N 不再等价；用 sum 归约除以窗口总量。
- **DDP 中只把 backward 包进 `no_sync`**：前向在外面时仍会同步；前向和反向都要在上下文内。
- **在窗口中途 `scaler.unscale_` 或裁剪**：`unscale_` 每次 `update()` 之间只能调一次；裁剪应作用于整个窗口的累积梯度。
- **调度按 micro-batch 推进**：学习率以 N 倍速度衰减，提前"烧完"。
- **用 BatchNorm 还期待严格等价**：统计量按 micro-batch 计算。
- **直接运行脚本覆盖了仓库产物**：演示时加 `--no-write`。
- **用随机标签的 loss 比较配置**：本节的 `avg_loss` 不含任何信号。

---

## 9. 测试在验证什么

`test_main.py` 用 `sys.path.insert(0, str(HERE))` 把 `code/` 加入路径后 `import main as accum`。测试不会写仓库中的 `outputs/`（`write_curve` 写到临时目录）。

运行方式（均已实际运行）：

```bash
cd code && python3 -m pytest -q test_main.py      # 6 passed
cd code && python3 -m unittest test_main -v       # Ran 6 tests ... OK
```

| 测试类 | 测试 | 验证的性质 |
|-------|------|----------|
| `EquivalenceTests` | `test_full_batch_matches_accumulated` | `equivalence_check()` 的梯度差、参数差都 < 1e-4，且两模型初始化逐位相同——本节核心命题 |
| | `test_loss_scaled_for_accum_divides` | logits `[2.0, 0.5, -1.0]`、标签 0：缩放后的 loss 等于原始 loss / 4（6 位小数） |
| `SweepTests` | `test_sweep_returns_one_point_per_accum` | `accum_grid=[1,2,4]`、micro=2 时返回 3 个点，有效 batch 为 `[2, 4, 8]`，吞吐、步数、耗时都为正 |
| | `test_sync_calls_equal_step_count` | `accum=1` 与 `accum=4` 下 `sync_calls == steps == 7`——sync-on-last-step 每个有效步只同步一次 |
| `CurveOutputTests` | `test_write_curve_round_trip` | 写 JSON 再读回：`schema == "accum-curve.v1"`、点数为 2、含 `samples_per_sec` 字段 |
| | `test_effective_batch_must_divide_accum` | `effective_batch=5, accum=2` 触发 `AssertionError` |

值得注意的测试缺口：

- 没有测试优化器状态按有效步推进（SGD 无状态，练习 3 的 AdamW 版本未覆盖）。
- 没有"不等分切分不等价"的反例测试，也没有"忘记除以 N"的负面测试。
- `test_effective_batch_must_divide_accum` 依赖 `assert`，在 `python -O` 下会失败（断言被移除，不再抛错）。
- 没有测试 `main()` 的 `--no-write` 行为，也没有防止测试意外写入仓库产物的保护。
