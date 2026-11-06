# 代码讲解 · debug_tools.py

> **所属小节**：阶段 00 · 环境搭建与工具 · 第 12 节 调试与性能分析 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python debug_tools.py`（无命令行参数） ｜ **依赖**：标准库 `sys`、`time`、`tracemalloc`、`logging`；可选 `torch`（未安装时只运行第 3、9 两个演示并以退出码 1 结束；有 CUDA 时额外运行 GPU 显存演示）

---

## 1. 这份代码在考察什么

这是一个"AI 调试工具箱"：把讲义里的调试函数整理成可以直接复制到自己项目里的工具，再用 10 个小演示逐一展示它们的输出。它要你掌握：

1. **张量级检查**：一行打印 shape / dtype / device / 数值范围 / 是否有 NaN；用 forward hook 打印整条形状链；检查设备是否一致。
2. **训练动态检查**：检测 NaN loss 并逐参数排查梯度；计算总梯度范数，发现梯度爆炸或消失。
3. **性能与内存**：用上下文管理器计时；用 `tracemalloc` 找出分配内存最多的代码行；查看 GPU 显存的已分配量和缓存量。
4. **工程习惯**：用 `logging` 替代 `print`；"条件断点"只在异常时停下；可选依赖缺失时优雅降级。

> 一句话：**AI 的 bug 多数不会报错，所以要主动"体检"**——这份代码就是一套体检仪器，测验里还会指出这些仪器本身的几处盲区。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `logging.basicConfig` + `logger` | 模块级配置 | 统一日志格式（时间、级别、消息） | 结构化日志 |
| `HAS_TORCH` | 标志变量 | 记录 PyTorch 是否可用 | 可选依赖 |
| `debug_print(name, tensor)` | 函数 | 打印张量的形状、类型、设备、min/max/mean、has_nan | 张量打印调试 |
| `Timer` | 类（上下文管理器） | `with Timer("x"):` 自动计时并打印 | 分段计时 |
| `check_shapes(model, sample_input)` | 函数 | 给每个子模块挂 forward hook，打印输入→输出形状 | 形状排查 |
| `detect_nan(model, loss, step)` | 函数 | loss 为 NaN 时逐参数检查梯度中的 NaN/Inf | NaN 排查 |
| `check_devices(model, *tensors)` | 函数 | 比较各张量与模型所在设备 | 设备一致性 |
| `check_gradient_health(model)` | 函数 | 计算总梯度范数，提示过大或为 0 的梯度 | 梯度健康 |
| `demo_*`（10 个） | 演示函数 | 分别演示以上工具以及显存、日志、条件断点 | — |
| `main()` + `sys.exit(main())` | 入口 | 按顺序运行演示，返回退出码 | 退出码约定 |

调用关系：`main()` 先检查 `HAS_TORCH`，没有 PyTorch 就只跑 `demo_memory_tracking` 和 `demo_logging`；否则依次运行全部 10 个演示，每个 `demo_*` 内部调用对应的工具函数。

---

## 3. 逐段精讲

### 3.1 开头：日志配置与"可选依赖"

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
```

- `basicConfig` 给**根日志器**配置一个输出处理器：级别 `INFO` 及以上才输出，格式里 `%(asctime)s` 是时间戳、`%(levelname)s` 是级别名。没有指定 `filename` / `handlers` 时，输出目标是 **stderr**——所以 `python debug_tools.py > out.txt` 抓不到日志（测验 Q8，已实测）。讲义第三部分的版本额外加了 `FileHandler("training.log")`，那才是"凌晨 3 点出错时有日志文件可查"的完整做法。
- `logging.getLogger(__name__)` 用模块名作为日志器名字，是标准写法：在大项目里可以按模块分别调整日志级别。
- `try/except ImportError` + 标志变量：PyTorch 是"可选依赖"，没有它脚本也不会在导入阶段崩溃，`main()` 会根据 `HAS_TORCH` 只运行不需要 torch 的演示。
- ⚠️ 在模块顶层调用 `basicConfig` 有副作用：别的程序 `import debug_tools` 时也会修改全局日志配置。作为脚本运行没问题；做成库时应把配置移到 `main()` 里。

### 3.2 `debug_print`：一行看清一个张量

```python
def debug_print(name, tensor):
    print(f"  {name}: shape={tensor.shape}, dtype={tensor.dtype}, "
          f"device={tensor.device}, "
          f"min={tensor.min().item():.4f}, max={tensor.max().item():.4f}, "
          f"mean={tensor.mean().item():.4f}, "
          f"has_nan={tensor.isnan().any().item()}")
```

- 讲义的观点："For tensor code, a targeted print statement beats stepping through a debugger"——单步调试一次只能看一个变量，而形状、类型、设备、数值范围往往要放在一起看才能发现问题（比如 `dtype=float64` 混进来了，或者某层输出的 `max` 突然变成 1e6）。
- 相邻的 f-string 字面量会被 Python **自动拼接**成一个字符串，所以可以把一行很长的格式串拆成多行书写。
- `.item()` 把只有一个元素的张量转成 Python 数字，才能用 `:.4f` 格式化。
- ⚠️ 盲区一：`min()` / `max()` / `mean()` 会**传播 NaN**——张量里只要有一个 NaN，这三项全部显示 `nan`，你看不到其余元素是否正常。
- ⚠️ 盲区二：整数张量调用 `mean()` 会抛 `RuntimeError`，空张量调用 `min()` 也会报错；只检查 NaN、不检查 Inf。测验 Q9 给出了改进版。
- ⚠️ 在 GPU 张量上，每个 `.item()` 都会触发一次 GPU→CPU 同步，调试时没问题，但不要留在正式训练的每一步里。

### 3.3 `Timer`：用上下文管理器计时

```python
class Timer:
    def __init__(self, name=""):
        self.name = name
        self.elapsed = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self.start
        print(f"  [{self.name}] {self.elapsed:.4f}s")
```

- 实现了 `__enter__` 和 `__exit__` 的类就是**上下文管理器**，可以用在 `with` 语句里：进入 `with` 块时调用 `__enter__` 记下开始时间，离开时（**包括块内抛出异常时**）调用 `__exit__` 计算耗时。
- `__exit__(self, *args)` 用 `*args` 一次接住 Python 传入的三个参数（异常类型、异常值、traceback）；它返回 `None`（假值），所以块内的异常会照常向外传播，计时器不会吞掉错误。
- `time.perf_counter()` 是专门用来测量时间间隔的高精度单调时钟，不受系统时间调整的影响，比 `time.time()` 更适合计时。
- 相比讲义版本，这里多了 `self.elapsed`，`with Timer(...) as t:` 之后可以通过 `t.elapsed` 读取耗时，便于程序化比较。
- ⚠️ 对 GPU 运算，CUDA 是异步执行的，必须在停表前调用 `torch.cuda.synchronize()`，否则只测到了"提交任务"的时间（测验 Q5）。
- ⚠️ `demo_timing` 中计时范围包含了 `torch.randn` 生成随机矩阵的时间，标签 "matrix multiply" 并不只代表矩阵乘法；也没有预热，第一次运行通常偏慢。

### 3.4 `check_shapes`：用 forward hook 打印形状链

```python
def check_shapes(model, sample_input):
    print(f"  Input: {sample_input.shape}")
    hooks = []

    def make_hook(name):
        def hook(module, inp, out):
            in_shape = inp[0].shape if isinstance(inp, tuple) else inp.shape
            out_shape = out.shape if hasattr(out, "shape") else type(out).__name__
            print(f"    {name}: {in_shape} -> {out_shape}")
        return hook

    for name, module in model.named_modules():
        if name:
            hooks.append(module.register_forward_hook(make_hook(name)))

    with torch.no_grad():
        model(sample_input)

    for h in hooks:
        h.remove()
```

- **forward hook**：`register_forward_hook(fn)` 让 PyTorch 在该模块每次前向**完成后**调用 `fn(module, inputs, output)`。不需要修改模型代码，就能"窃听"每一层的输入输出。它返回一个句柄，调用 `h.remove()` 才能卸载。
- **为什么要 `make_hook(name)` 这个工厂函数**：如果直接在 `for` 循环里定义 `hook` 并引用循环变量 `name`，所有钩子会在**执行时**才去读取 `name`，那时循环早已结束，每个钩子都会打印最后一个名字（闭包的"延迟绑定"陷阱）。把 `name` 作为参数传给外层函数，每个钩子就各自"记住"了自己的名字。
- `named_modules()` 会递归列出所有子模块，第一个是模型本身，名字为 `""`，`if name:` 将其跳过。
- `type(out).__name__`：当某层输出的不是张量（例如返回元组或字典）时，打印类型名而不是报错。
- `with torch.no_grad()`：只是看形状，不需要构建计算图，省内存也更快。
- ⚠️ 没有 `try/finally`：如果前向抛出形状错误——这恰好是这个函数最常用的场景——`h.remove()` 不会执行，钩子永久留在模型上。
- ⚠️ 没有切换到 `model.eval()`：训练模式下 BatchNorm 仍会用这个随机样本更新 running 统计量（`no_grad` 不会阻止这一点），Dropout 也会生效。
- ⚠️ `else inp.shape` 是死代码：PyTorch 传给 forward hook 的 `inp` 总是元组。测验 Q10 给出了修复版。

### 3.5 `detect_nan` 与 `check_devices`

```python
def detect_nan(model, loss, step):
    if torch.isnan(loss):
        print(f"  NaN loss detected at step {step}")
        for name, param in model.named_parameters():
            if param.grad is not None:
                if torch.isnan(param.grad).any():
                    print(f"    NaN gradient in {name}")
                if torch.isinf(param.grad).any():
                    print(f"    Inf gradient in {name}")
        return True
    return False
```

- 思路是"先确认 loss 坏了，再逐个参数找梯度从哪里开始坏的"：`named_parameters()` 给出每个参数的名字（如 `0.weight`、`2.bias`），可以直接定位到层。
- `param.grad is not None` 的检查很必要：冻结的参数、或还没执行过 `backward()` 的参数，`.grad` 是 `None`。
- `if torch.isnan(loss):` 能这样写，是因为 `loss` 是只有一个元素的张量，Python 会自动把它转成布尔值。
- ⚠️ 只在 loss 为 NaN 时检查；loss 为 Inf 或梯度先变成 Inf 时不会进入分支。通常应该用 `not torch.isfinite(loss)` 一次覆盖两种情况。

```python
def check_devices(model, *tensors):
    model_device = next(model.parameters()).device
    print(f"  Model device: {model_device}")
    for i, t in enumerate(tensors):
        status = "OK" if t.device == model_device else "MISMATCH"
        print(f"    Tensor {i}: {t.device} [{status}]")
```

- `*tensors` 收集任意数量的位置参数，调用时可以写 `check_devices(model, x, y, mask)`。
- `next(model.parameters())` 只取**第一个参数**的设备作为"模型设备"。
- ⚠️ 没有参数的模型会抛 `StopIteration`；模型被拆分到多张卡上时，只看第一个参数也不够。
- 讲义特别提醒：设备不一致**有时不会报错**，而是让某个张量一直留在 CPU 上，训练"只是变慢"——这正是这个函数存在的意义。

### 3.6 `check_gradient_health`：总梯度范数

```python
    for name, param in model.named_parameters():
        if param.grad is not None:
            grad_norm = param.grad.data.norm(2).item()
            total_norm += grad_norm ** 2
            if grad_norm > 100:
                print(f"    WARNING: large gradient in {name}: {grad_norm:.2f}")
            if grad_norm == 0:
                print(f"    WARNING: zero gradient in {name}")
    total_norm = total_norm ** 0.5
```

- 总范数 `√(Σ‖gᵢ‖²)` 等于把所有梯度拼成一个长向量后的 L2 范数，与 `torch.nn.utils.clip_grad_norm_` 使用的定义相同，可以直接用来决定梯度裁剪阈值。
- 讲义"Use It"一节要求在训练中记录梯度范数：它突然飙升通常预示 loss 即将变成 NaN；长期接近 0 则说明梯度消失或者某处被意外 `detach()` 了。
- `grad_norm == 0` 精确等于 0，常见原因是这一层的输出没有参与 loss 的计算（例如被 `detach()` 截断，或是某个分支没有被用到）。
- ⚠️ 梯度含 NaN 时，`nan > 100` 和 `nan == 0` 都是 `False`，**不会有任何警告**。
- ⚠️ 每个参数调用一次 `.item()`，在 GPU 上会造成大量同步。`.data` 是旧式写法，推荐 `.detach()`。改进版见测验 Q12。

### 3.7 十个演示里值得注意的细节

```python
def demo_memory_tracking():
    print("\n--- 3. Memory Tracking (tracemalloc) ---")
    tracemalloc.start()

    if HAS_TORCH:
        data = [torch.randn(100, 100) for _ in range(100)]
        more_data = torch.randn(1000, 1000)
    else:
        data = [bytearray(4 * 100 * 100) for _ in range(100)]
        more_data = bytearray(4 * 1000 * 1000)

    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics("lineno")
```

- `tracemalloc.start()` 之后的内存分配才会被记录；`take_snapshot()` 拍下当前仍存活的分配，`statistics("lineno")` 按"代码行"汇总并从大到小排序。
- 无 torch 分支用 `bytearray(4 × 元素个数)` 模拟 float32 张量的字节数，让两条分支的数据量一致：每条分支大约 4 MB + 4 MB。
- 列表推导里的 `_` 是"我不需要这个循环变量"的惯用写法。
- 最后 `del data, more_data` 和 `tracemalloc.stop()`：释放演示数据并停止追踪（追踪本身有性能开销）。
- ⚠️ `tracemalloc` 只能看到经过 Python 内存分配器（或主动向它报告）的分配。PyTorch 张量的数据缓冲区由 PyTorch 的 C++ 分配器直接申请，因此在 `HAS_TORCH` 分支里，预期 `tracemalloc` 只能看到很小的 Python 包装对象，看不到那约 8 MB 的数据（当前环境没有 torch，未实测）。所以本演示真正"演示成功"的是无 torch 的分支。

```python
    large_tensor = torch.randn(10000, 10000, device="cuda")
    # ...
    del large_tensor
    torch.cuda.empty_cache()
    print(f"  After cleanup:")
    print(f"    Allocated: {torch.cuda.memory_allocated() / 1e6:.1f} MB")
```

- `10000 × 10000 × 4 字节 = 400 MB`，所以分配后 `Allocated` 会增加约 400 MB。
- ⚠️ `del` 之后 `memory_allocated()` 就已经回落了，这与 `empty_cache()` 无关；`empty_cache()` 影响的是 `memory_reserved()`（Cached），而清理后的部分没有打印它，所以这个演示其实看不出 `empty_cache()` 的作用。改成同时打印 `memory_reserved()` 就能看到"del 之后 reserved 不变、empty_cache 之后 reserved 下降"的完整过程。

其余演示：

- `demo_print_debugging`：`x` 为 `randn(32, 784)`，`w` 为 `randn(784, 128)`，`out = x @ w` 的每个元素是 784 个乘积之和，标准差约 `√784 = 28`，所以 min/max 会比输入大一个数量级——这本身就是一个"未做初始化缩放会导致激活变大"的小例子（对比阶段 03 的权重初始化）。
- `demo_nan_detection`：先跑一次正常的前向和反向，`detect_nan` 返回 `False`；再用 `torch.tensor(float("nan"))` 伪造一个 NaN loss。因为梯度来自正常的那一步，所以只会打印 "NaN loss detected"，不会出现 NaN 梯度的提示。
- `demo_device_checking`：只有在 CUDA 可用时才演示设备不一致的情况。注意 `model.cuda()` 是**原地**移动并返回模型本身，所以执行后 `model` 和 `model_gpu` 是同一个对象。
- `demo_conditional_breakpoint`：只**打印**用法，而不是真的调用 `breakpoint()`，否则脚本会停下来等待输入。顺带一提：设置环境变量 `PYTHONBREAKPOINT=0` 可以让代码中所有 `breakpoint()` 失效，方便在正式运行时关掉调试断点。

### 3.8 `main()` 与退出码

```python
def main():
    # ...
    if not HAS_TORCH:
        print("\nPyTorch not installed. Install with:")
        print("  uv pip install torch")
        print("\nRunning non-PyTorch demos only...\n")
        demo_memory_tracking()
        demo_logging()
        return 1
    # ...
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- `main()` 返回整数，`sys.exit(main())` 把它作为进程的**退出码**：0 表示全部成功，1 表示环境不完整。这样 shell 脚本或 CI 可以用 `$?` 判断结果——即使脚本"跑完了"部分演示，缺少 torch 时仍然报告失败，提醒你环境没装好。
- 没有 torch 时仍然运行这两个演示，是"优雅降级"：能做的先做，而不是直接退出。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 `print` 打印张量统计 | 一眼看全形状、类型、设备、数值 | 调试完要删掉；长期监控应改为 logging 或 TensorBoard |
| `Timer` 做成上下文管理器 | `with` 写法简洁，异常时也能停表 | GPU 计时需 `synchronize`；严肃的基准测试要预热并多次重复 |
| forward hook 查形状 | 不改模型代码即可观察每一层 | 应 `try/finally` 移除钩子并切到 `eval()` 模式 |
| 只在 NaN loss 时才查梯度 | 平时零开销 | 漏掉 Inf；生产中会定期记录梯度范数，而不是等出事 |
| 每个参数单独 `.item()` | 代码直观 | GPU 上同步开销大；应批量计算后一次性取回 |
| PyTorch 作为可选依赖 | 没装 torch 也能体验部分功能 | 演示覆盖面有限 |
| 日志用 `basicConfig` 输出到 stderr | 一行配置、开箱即用 | 应加 `FileHandler` 写文件；做成库时不要在导入时修改全局配置 |
| 用 `bytearray` 模拟张量的内存 | 无 torch 时也能演示 tracemalloc | 恰好掩盖了"tracemalloc 看不到张量数据"这一盲区 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `try / except ImportError` + 标志变量 | `HAS_TORCH = True / False` | 处理可选依赖，导入失败不崩溃 |
| 相邻字符串自动拼接 | `debug_print` 中多行 f-string | 括号内相邻的字符串字面量会合并成一个 |
| f-string 格式符 | `{x:.4f}`、`{n / 1e6:.1f}` | `.4f` 保留 4 位小数；大括号里可以写表达式 |
| 浮点特殊值 | `float("nan")` | 构造 NaN；NaN 与任何数比较都为 `False` |
| 幂运算 | `grad_norm ** 2`、`total_norm ** 0.5` | 平方与开平方 |
| `class` 与实例属性 | `Timer.__init__` 中 `self.elapsed = 0.0` | 在构造函数里初始化属性 |
| 上下文管理器协议 | `__enter__` / `__exit__`，`with Timer("..."):` | 进入和离开 `with` 块时自动执行，异常时也会调用 `__exit__` |
| `*args` | `def __exit__(self, *args)`、`def check_devices(model, *tensors)` | 收集任意数量的位置参数，得到一个元组 |
| 嵌套函数与闭包 | `make_hook(name)` 返回内部的 `hook` | 内层函数"记住"外层函数的变量，避免循环变量的延迟绑定问题 |
| `enumerate` | `for i, t in enumerate(tensors)` | 同时取得下标和元素 |
| 条件表达式 | `"OK" if t.device == model_device else "MISMATCH"` | 一行写出二选一 |
| `hasattr` / `isinstance` / `type(...).__name__` | `check_shapes` 中的 hook | 运行时检查对象能力和类型，取类型名 |
| `next(iterator)` | `next(model.parameters())` | 取生成器的第一个元素；为空时抛 `StopIteration` |
| 列表推导与 `_` | `[torch.randn(100, 100) for _ in range(100)]` | `_` 表示不使用的循环变量 |
| `del` | `del data, more_data` | 删除名字绑定，引用计数归零后对象被回收 |
| `with torch.no_grad():` | `check_shapes` 中 | 上下文管理器的实际应用：临时关闭梯度记录 |
| `logging` | `basicConfig(...)`、`logger.info(...)`、`logger.warning(...)` | 按级别输出带时间戳的日志 |
| 提前 `return` | `main()` 中无 torch 时 `return 1` | 卫语句，避免深层嵌套 |
| `sys.exit(main())` + `if __name__ == "__main__":` | 文件末尾 | 把函数返回值作为进程退出码；仅在直接运行时执行 |

---

## 6. 运行结果解读

在临时副本中实际运行了一次。**当前环境没有安装 PyTorch**，所以只执行了无 torch 的分支：

```text
============================================================
  AI Debugging and Profiling Toolkit
  Phase 0, Lesson 12
============================================================

PyTorch not installed. Install with:
  uv pip install torch

Running non-PyTorch demos only...


--- 3. Memory Tracking (tracemalloc) ---
  Top 5 memory allocations:
    /tmp/run_xxxx/debug_tools.py:136: size=3913 KiB, count=201, average=19.5 KiB
    /tmp/run_xxxx/debug_tools.py:137: size=3906 KiB, count=2, average=1953 KiB

--- 9. Structured Logging ---
2026-10-11 18:23:59,311 [INFO] Training started: lr=0.001, batch_size=32, epochs=10
2026-10-11 18:23:59,311 [INFO] Step 100: loss=2.3026, accuracy=0.10
2026-10-11 18:23:59,311 [WARNING] Loss spike detected: 15.7 at step 450
2026-10-11 18:23:59,311 [INFO] Step 1000: loss=0.4512, accuracy=0.87
2026-10-11 18:23:59,311 [INFO] Training complete: best_loss=0.3201
exit=1
```

逐行解读：

- `:136 size=3913 KiB, count=201`：100 个 `bytearray(40000)`，数据共 4,000,000 字节 ≈ 3906 KiB，加上 100 个对象和列表的开销，合计 3913 KiB。
- `:137 size=3906 KiB, count=2`：一个 4,000,000 字节的 `bytearray`，2 次分配分别是对象和数据缓冲区。
- 标题写 "Top 5"，实际只有 2 行：`tracemalloc` 在函数内部才启动，期间只有这两行代码分配了内存。
- 日志行带有时间戳和 `[INFO]` / `[WARNING]` 级别，这是 `basicConfig` 中 format 的效果。
- `exit=1`：缺少 torch，`main()` 返回 1。
- 额外验证：执行 `python3 debug_tools.py 2>/dev/null` 时，5 行日志全部消失——证明 logging 默认写入的是 stderr。

**未实际运行 PyTorch 部分（原因：环境中没有安装 torch）**。在装有 PyTorch 的纯 CPU 机器上，根据代码预期会看到：

| 演示 | 预期输出要点 |
|------|------------|
| 1. Print Debugging | `input batch: shape=torch.Size([32, 784]) ... has_nan=False`，min/max 大约在 ±4 到 ±5；`after matmul` 的形状是 `[32, 128]`，数值范围扩大到大约 ±100 量级（标准差约 28）；`with injected NaN` 显示 `min=nan, max=nan, mean=nan, has_nan=True` |
| 2. Timing | 两行 `[matrix multiply ...] x.xxxxs`，5000×5000 明显更慢：矩阵乘法计算量按 n³ 增长，理论上约为 1000×1000 的 125 倍，实际倍数还受多线程 BLAS 效率和随机数生成时间（按 n² 增长）影响；具体数值取决于 CPU |
| 3. tracemalloc | 预期只能看到较小的 Python 对象开销，看不到约 8 MB 的张量数据（原因见 3.7 节） |
| 4. Shape Checking | `0: [4, 784] -> [4, 256]`、`1: [4, 256] -> [4, 256]`、`2: [4, 256] -> [4, 64]`、`3: [4, 64] -> [4, 64]`、`4: [4, 64] -> [4, 10]` |
| 5. NaN Detection | `Normal loss` 约为 2.3（随机初始化时接近 ln 10 ≈ 2.30）、`NaN detected: False`；随后 `Simulated NaN loss: nan`、`NaN loss detected at step 99`、`NaN detected: True` |
| 6. Device Checking | `Model device: cpu`，两个张量都是 `cpu [OK]`；没有 GPU 时不演示设备不一致 |
| 7. Gradient Health | 一行 `Total gradient norm: x.xxxx`，通常没有 WARNING |
| 8. GPU Memory | 没有 GPU 时打印 "No GPU available. Skipping GPU memory demo." 和三行说明 |
| 9. Logging | 同上面实测的 5 行日志 |
| 10. Breakpoint | 打印条件断点模板和 pdb 常用命令 |

最后打印 "All demos complete."，退出码为 0。

---

## 7. 动手改一改

1. 按测验 Q9 改写 `debug_print`：支持整数张量和空张量，只对有限值统计 min/max/mean，并报告 NaN 和 Inf 的个数。用 `with_nan` 和 `torch.randint(0, 10, (4,))` 验证。
2. 讲义练习 1：在演示模型的前向中人为制造 NaN（例如自定义一个模块执行 `x / 0` 再乘 0），观察 `detect_nan` 能否发现；再把 `detect_nan` 的判断改为 `not torch.isfinite(loss)`，覆盖 Inf 的情况。
3. 给 `check_shapes` 加上 `try/finally` 和 `eval()` / 恢复模式；然后故意把第二个 `Linear(256, 64)` 改成 `Linear(128, 64)`，观察打印的最后一行停在哪一层。
4. 给 `Timer` 增加一个参数 `cuda_sync=False`，为 `True` 时在开始和结束时调用 `torch.cuda.synchronize()`；在 GPU 上对比加与不加的计时结果。
5. 在 `demo_gpu_memory` 中每一步都同时打印 `memory_allocated()` 和 `memory_reserved()`，观察 `del` 和 `empty_cache()` 分别影响哪一个数字。
6. 写一个 20 步的小训练循环，用讲义第八部分的 `SummaryWriter` 记录 loss、学习率和 `check_gradient_health` 返回的总梯度范数，启动 `tensorboard --logdir=runs` 查看曲线。

---

## 8. 常见坑

- **NaN 的比较永远是 `False`**：`nan > 100`、`nan == 0` 都不成立，任何基于阈值的检查都要单独处理 NaN（`torch.isnan` / `torch.isfinite` / `math.isfinite`）。
- **GPU 计时不同步**：CUDA 是异步的，不调用 `torch.cuda.synchronize()` 测到的只是任务提交时间。
- **钩子忘记移除**：forward hook 一旦注册就一直存在，务必用 `try/finally` 保证 `remove()`。
- **`no_grad()` 不等于 `eval()`**：前者只关闭梯度记录，BatchNorm 和 Dropout 的行为由后者控制。
- **日志去了 stderr**：只用 `>` 重定向会丢失 logging 输出，需要 `2>&1` 或配置 `FileHandler`。
- **`tracemalloc` 看不到张量数据**：它适合分析 Python 对象和 NumPy 数组；张量要看 `memory_allocated` 或进程的 RSS。
- **`line_profiler` 的 `@profile` 不需要 import**：它由 `kernprof` 在运行时注入；直接用 `python train.py` 运行带 `@profile` 的代码会报 `NameError: name 'profile' is not defined`。
