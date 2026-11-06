# 测验 · 调试与性能分析（Debugging and Profiling）

> **阶段 00 · 环境搭建与工具 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/debug_tools.py](../code/debug_tools.py) ｜ 代码讲解：[code/debug_tools.讲解.md](../code/debug_tools.讲解.md)
>
> **用法**：学完讲义、装好 PyTorch 并跑过 `python code/debug_tools.py` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。没有 GPU 也能完成绝大部分题目。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | AI bug 的特点 | 最可怕的 bug 不崩溃：在错误数据上安静地训练 8 小时，loss 曲线还很漂亮 |
| 2 | 调试的三个层次 | ①标准 Python（断点、日志、profiling、内存）②张量操作（shape、dtype、device、NaN/Inf）③训练动态（loss、梯度范数、激活）；80% 的 bug 在前两层 |
| 3 | 张量打印调试 | 一行打印 shape / dtype / device / min / max / mean / has_nan，比单步调试更快看清全貌 |
| 4 | 条件断点 | `if loss.item() > 100 or torch.isnan(loss): breakpoint()`，只在异常时停下；pdb 用 `p` 查看、`c` 继续、`q` 退出 |
| 5 | logging 代替 print | 有时间戳、级别、可写文件；默认输出到 **stderr** |
| 6 | 计时与 profiling | `time.perf_counter()` 计时器；`cProfile` 看函数级耗时；`line_profiler`（`@profile` + `kernprof -l -v`）看逐行耗时 |
| 7 | 内存分析 | `tracemalloc` / `memory_profiler` 看 CPU 内存；`torch.cuda.memory_allocated()` / `memory_reserved()` 看显存 |
| 8 | OOM 应对顺序 | 先减 batch size，再混合精度、梯度检查点；`empty_cache()` 只归还缓存块，不会释放仍被引用的张量 |
| 9 | 四类常见 AI bug | shape 不匹配（forward hook 打印形状链）、NaN loss（逐参数查梯度）、数据泄漏（查 ID 重叠、时间泄漏）、设备不一致 |
| 10 | TensorBoard | `add_scalar` 记 loss / lr，`add_histogram` 记权重和梯度；训练 loss 降、验证 loss 升 = 过拟合 |

### 核心技能（能动手做到）

- [ ] 写出 `debug_print`，在一个前向过程中逐层打印，定位 NaN **第一次**出现的位置
- [ ] 在训练循环里加条件断点，进入 pdb 后查看 `outputs.shape`、`loss.item()`、某层的 `weight.grad`
- [ ] 用 `python -m cProfile -s cumtime train.py` 找出最耗时的函数，再用 `kernprof -l -v` 定位到行
- [ ] 用 `tracemalloc` 打印分配最多的前 5 行代码，并知道它看不到哪些内存
- [ ] 用 `register_forward_hook` 打印模型每一层的输入输出形状，并保证钩子一定会被移除
- [ ] 计算总梯度范数，并用 TensorBoard 记录 loss、学习率和梯度直方图
- [ ] 遇到 CUDA OOM 时，能说清 `memory_allocated` 和 `memory_reserved` 的区别，并按顺序尝试降显存手段

---

## 二、基础自测（选择题）

**Q1.** 讲义认为 AI 代码的 bug 与 Web 应用最大的不同是：

- A. AI 代码只能在 GPU 上调试
- B. AI 代码不能用 print 调试
- C. 最严重的 bug 往往不报错，训练照常进行，只是结果是错的
- D. AI 代码的 bug 都出在 TensorBoard 里

**Q2.** 讲义的条件断点写成 `if loss.item() > 100 or torch.isnan(loss): breakpoint()`。为什么不能只写 `if loss.item() > 100`？

- A. 因为 `loss.item()` 在 NaN 时会抛异常
- B. 因为 NaN 与任何数比较的结果都是 `False`，`nan > 100` 为假，单靠阈值抓不到 NaN
- C. 因为 `> 100` 只对整数有效
- D. 两种写法完全等价

**Q3.** 训练过程中，`torch.cuda.memory_allocated()` 显示 6 GB，而 `nvidia-smi` 显示这个进程占用了 10 GB。最合理的解释是：

- A. `nvidia-smi` 的统计有 bug
- B. PyTorch 的缓存分配器保留（reserved）了已释放的显存块以便复用，`nvidia-smi` 看到的是保留量加上 CUDA 上下文等开销
- C. 有 4 GB 显存被泄漏了，必须重启机器
- D. `memory_allocated()` 只统计模型参数

**Q4.** 关于 `torch.cuda.empty_cache()`，下列说法正确的是：

- A. 它会删除所有不再使用的张量变量
- B. 它把缓存分配器中**未被占用**的显存块还给驱动，`nvidia-smi` 上的占用会下降；但仍被引用的张量不会被释放，PyTorch 自己可用的显存也不会因此增加
- C. 它可以从根本上解决所有 OOM 问题
- D. 它会清空模型参数

**Q5.** 用讲义的 `Timer` 包住一次 GPU 上的大矩阵乘法 `c = a @ b`（`a`、`b` 都在 CUDA 上），测得只有 0.0001 秒。最可能的原因是：

- A. GPU 真的这么快
- B. CUDA 运算是**异步**的，Python 只是把计算任务提交到 GPU 就返回了；应在计时结束前调用 `torch.cuda.synchronize()`
- C. `time.perf_counter()` 精度不够
- D. 矩阵乘法被 Python 缓存了

**Q6.** 下列"问题 → 工具"的对应中，哪一项**不合适**？

- A. "整个训练脚本里哪个函数最耗时？" → `python -m cProfile -s cumtime train.py`
- B. "`train_step` 函数里哪一行最慢？" → `line_profiler`（`@profile` + `kernprof -l -v`）
- C. "数据加载时哪一行代码分配的 Python 内存最多？" → `tracemalloc`
- D. "模型这一轮的验证集准确率是多少？" → `cProfile`

**Q7.** TensorBoard 上，训练 loss 持续下降，验证 loss 先降后升。这说明：

- A. 学习率太低
- B. 模型开始过拟合
- C. 梯度消失
- D. 数据加载太慢

**Q8.** 你运行 `python debug_tools.py > out.txt`，打开 `out.txt` 发现第 9 部分 "Structured Logging" 的标题在，但那几行 `[INFO]` / `[WARNING]` 日志不见了。原因是：

- A. 日志级别设置得太高
- B. `logging.basicConfig` 默认创建的处理器把日志写到 **stderr**，而 `>` 只重定向了 stdout
- C. 文件被截断了
- D. logging 只在交互式终端中工作

---

## 三、动手 / 代码题

**Q9.** `debug_tools.py` 中的 `debug_print`：

```python
def debug_print(name, tensor):
    print(f"  {name}: shape={tensor.shape}, dtype={tensor.dtype}, "
          f"device={tensor.device}, "
          f"min={tensor.min().item():.4f}, max={tensor.max().item():.4f}, "
          f"mean={tensor.mean().item():.4f}, "
          f"has_nan={tensor.isnan().any().item()}")
```

演示代码中有：

```python
    with_nan = out.clone()
    with_nan[0, 0] = float("nan")
    debug_print("with injected NaN", with_nan)
```

1. `with_nan` 是 `32×128` 的张量，只有一个元素是 NaN。预测这一行打印出的 `min`、`max`、`mean`、`has_nan` 分别是什么，并说明这对调试意味着什么。
2. 如果对分类标签调用 `debug_print("labels", torch.randint(0, 10, (4,)))`，会发生什么？
3. 改写 `debug_print`：支持整数张量和空张量；min/max/mean 只统计有限值；同时报告 NaN 和 Inf 的**个数**。

**Q10.** `check_shapes` 用 forward hook 打印每一层的形状：

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

1. 对演示中的 `nn.Sequential(Linear(784,256), ReLU(), Linear(256,64), ReLU(), Linear(64,10))` 和 `sample = torch.randn(4, 784)`，写出打印结果。`if name:` 过滤掉了什么？
2. 这个函数最常见的用途是排查 shape 不匹配——恰恰是 `model(sample_input)` **会抛异常**的场景。此时会发生什么问题？打印出来的最后一行意味着什么？
3. 如果模型里有 `BatchNorm` 和 `Dropout`，在训练模式下运行 `check_shapes` 有什么副作用？
4. 写出修复后的版本。

**Q11.** 在**没有安装 PyTorch** 的环境中实际运行 `debug_tools.py`，第 3 部分的输出如下（路径已省略）：

```text
--- 3. Memory Tracking (tracemalloc) ---
  Top 5 memory allocations:
    debug_tools.py:136: size=3913 KiB, count=201, average=19.5 KiB
    debug_tools.py:137: size=3906 KiB, count=2, average=1953 KiB
```

对应代码：

```python
    if HAS_TORCH:
        data = [torch.randn(100, 100) for _ in range(100)]
        more_data = torch.randn(1000, 1000)
    else:
        data = [bytearray(4 * 100 * 100) for _ in range(100)]       # 第 136 行
        more_data = bytearray(4 * 1000 * 1000)                      # 第 137 行
```

1. 解释两行的 `size` 和 `count` 是怎么来的。为什么标题写 "Top 5"，却只打印了 2 行？
2. 装上 PyTorch 后走 `HAS_TORCH` 分支，你预期 `tracemalloc` 还能看到这约 8 MB 的数据吗？为什么？
3. 如果要测量张量占用的内存，应该用什么方法？

**Q12.** `check_gradient_health` 的实现：

```python
def check_gradient_health(model):
    total_norm = 0.0
    for name, param in model.named_parameters():
        if param.grad is not None:
            grad_norm = param.grad.data.norm(2).item()
            total_norm += grad_norm ** 2
            if grad_norm > 100:
                print(f"    WARNING: large gradient in {name}: {grad_norm:.2f}")
            if grad_norm == 0:
                print(f"    WARNING: zero gradient in {name}")
    total_norm = total_norm ** 0.5
    print(f"  Total gradient norm: {total_norm:.4f}")
    return total_norm
```

1. 它计算的"总梯度范数"在数学上等于什么？和 `torch.nn.utils.clip_grad_norm_` 返回的值是什么关系？
2. 某个参数的梯度含有 NaN 时，这个函数会打印 WARNING 吗？
3. 在 GPU 上每一步都调用它，会有什么性能问题？
4. 改写它：能报告非有限值（NaN/Inf）梯度、没有任何梯度时给出提示、只做一次 GPU→CPU 同步。

---

## 四、面试高频题

**Q13.**（基础必考）训练到第 500 步 loss 突然变成 NaN。请给出你的系统排查流程，以及最常见的几种原因和对应修复。

**Q14.**（原理深挖）训练时 GPU 显存都花在了哪里？为什么很多 OOM 发生在 backward 阶段？粗略估算：用 Adam 全参数训练一个 7B 模型，仅参数、梯度和优化器状态就需要多少显存？

**Q15.**（工程实践）训练时 `nvidia-smi` 显示 GPU 利用率只有 30%。你会怎样定位瓶颈？常见的优化手段有哪些？

**Q16.**（场景设计）你要为团队设计一套"训练健康检查"：在花大量 GPU 时间之前尽早发现问题，并在训练中自动报警。你会包含哪些检查和监控项？

**Q17.**（追问型）测试集准确率 99%，你用讲义的 `check_data_leakage` 检查了 ID，没有任何重叠。这样就能排除数据泄漏了吗？还应该检查什么？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义开篇描述了一个典型场景：配置错误的训练循环跑了 8 小时、烧掉 200 美元的 GPU 费用，得到一个对任何输入都只会预测平均值的模型——"The code never errored."。根因可能是张量放错了设备、忘了 `.detach()`、或标签泄漏进了特征。所以 AI 调试的重点是**主动检查**（形状、数值、梯度、数据），而不是等报错。print 和标准工具当然可以用（B 错，讲义第一部分就是 print 调试）。

### Q2 — 答案：B

按 IEEE 754 规定，NaN 与任何数（包括它自己）比较，`>`、`<`、`==` 的结果都是 `False`。所以 loss 变成 NaN 时 `loss.item() > 100` 为假，断点不会触发，必须单独用 `torch.isnan(loss)` 判断。`loss.item()` 遇到 NaN 不会报错，只会返回 `nan`（A 错）。同理，"如果 loss 不小于阈值就报警"这类写法都要考虑 NaN 的情况。

### Q3 — 答案：B

PyTorch 使用**缓存分配器**：张量释放后，显存块不会立刻还给驱动，而是留在缓存里供后续分配复用，避免频繁调用代价很高的 `cudaMalloc`。`memory_allocated()` 只统计当前被张量占用的部分，`memory_reserved()`（讲义里打印为 "Cached"）是分配器从驱动那里持有的总量；`nvidia-smi` 看到的是保留量再加上 CUDA 上下文、cuDNN 工作区等开销。这是正常现象，不是泄漏。

### Q4 — 答案：B

`empty_cache()` 只把缓存中**未被占用**的块还给驱动，让其他进程能用、`nvidia-smi` 的读数下降。仍被变量引用的张量不会被释放——要先 `del` 掉引用（讲义第 3 条"`del tensor` 后再 `empty_cache()`"）。对 PyTorch 自身来说，缓存里的空闲块本来就可以复用，所以 `empty_cache()` 并不会让当前进程多出可用显存，讲义把它列为 OOM 的第 2 条对策是有误导性的；更有效的是减 batch size、混合精度、梯度检查点。

### Q5 — 答案：B

CUDA 内核是**异步**执行的：`a @ b` 只是把计算任务放进 GPU 的执行队列，Python 立即返回，计时器测到的只是"提交任务"的时间。正确做法：

```python
torch.cuda.synchronize()
with Timer("matmul"):
    c = a @ b
    torch.cuda.synchronize()     # 等 GPU 真正算完再停表
```

另外，第一次调用通常包含 CUDA 初始化、cuBLAS 加载等一次性开销，应该先预热几次再计时。`debug_tools.py` 的 `demo_timing` 在 CPU 上运行，不受异步影响，但它的计时范围同时包含了 `torch.randn` 生成随机数的时间，标签写 "matrix multiply" 并不完全准确。

### Q6 — 答案：D

cProfile、line_profiler、tracemalloc 都是测量**资源消耗**（时间、内存）的工具（A、B、C 都对应讲义的用法）；准确率是**模型效果**指标，要靠评估代码和 TensorBoard 记录，profiler 无法告诉你。

### Q7 — 答案：B

讲义的 TensorBoard 判读清单："Train loss decreasing, val loss increasing: Overfitting"。模型在训练集上越来越好，在没见过的数据上越来越差，说明它开始记忆训练数据。常见对策：early stopping（在验证 loss 最低点保存模型）、正则化、数据增强、增加数据。学习率太低的表现是 loss 下降很慢（A）。

### Q8 — 答案：B

`logging.basicConfig(level=..., format=...)` 没有指定 `filename` 或 `handlers` 时，会创建一个 `StreamHandler`，默认输出到 `sys.stderr`。`print` 写的是 stdout。所以 `> out.txt` 只捕获了 stdout，日志仍然打在终端上。实测：`python3 debug_tools.py 2>/dev/null` 时日志行全部消失。要把两者存进同一个文件，用 `> out.txt 2>&1`（第 10 节），或者像讲义第三部分那样给 logging 配一个 `FileHandler`。

### Q9 — 参考答案

1. 预测：`min=nan, max=nan, mean=nan, has_nan=True`。PyTorch 的 `min()`、`max()`、`mean()` 这类全量归约都会**传播 NaN**：只要有一个元素是 NaN，结果就是 NaN（f-string 的 `:.4f` 格式会显示为 `nan`）。这意味着：一旦有一个 NaN，min/max/mean 这三个统计量就全部失去参考价值，你看不出其余 4095 个值是否正常，也不知道有多少个 NaN。`has_nan` 只回答"有没有"，不回答"有多少"。
2. 会抛出 `RuntimeError`：`mean()` 不支持整数张量（报错信息类似 `mean(): could not infer output dtype. Input dtype must be either a floating point or complex dtype. Got: Long`）。也就是说，这个调试工具在调试标签时自己先崩了。对空张量（`numel() == 0`），`min()` / `max()` 同样会报错。
3. 改写版本：

```python
import torch


def debug_print(name, tensor):
    t = tensor.detach()
    msg = f"  {name}: shape={tuple(t.shape)}, dtype={t.dtype}, device={t.device}"
    if t.numel() == 0:
        print(msg + ", (empty)")
        return
    tf = t if t.is_floating_point() else t.float()   # 整数、布尔张量先转成浮点再统计
    finite = torch.isfinite(tf)
    n_nan = torch.isnan(tf).sum().item()
    n_inf = torch.isinf(tf).sum().item()
    vals = tf[finite]                                 # 只用有限值计算统计量
    if vals.numel() > 0:
        msg += (f", min={vals.min().item():.4f}, max={vals.max().item():.4f}, "
                f"mean={vals.mean().item():.4f}")
    msg += f", nan={n_nan}, inf={n_inf}"
    print(msg)
```

   对 `with_nan`，新版会打印其余有限值的真实 min / max / mean，以及 `nan=1, inf=0`；对整数标签会正常打印取值范围。`.detach()` 保证调试代码不会进入计算图。

### Q10 — 参考答案

1. 打印结果：

```text
  Input: torch.Size([4, 784])
    0: torch.Size([4, 784]) -> torch.Size([4, 256])
    1: torch.Size([4, 256]) -> torch.Size([4, 256])
    2: torch.Size([4, 256]) -> torch.Size([4, 64])
    3: torch.Size([4, 64]) -> torch.Size([4, 64])
    4: torch.Size([4, 64]) -> torch.Size([4, 10])
```

   `nn.Sequential` 的子模块名就是 `"0"`、`"1"`……；ReLU 不改变形状，所以输入输出相同。`named_modules()` 的第一个元素是模型自身，名字为空字符串 `""`，`if name:` 把它过滤掉了，否则还会多打印一行 `: [4, 784] -> [4, 10]`（讲义里的原版没有这个过滤）。
2. **钩子不会被移除。** 异常从 `model(sample_input)` 抛出后，后面的 `for h in hooks: h.remove()` 不会执行，所有钩子永久挂在模型上：之后每一次前向（包括正式训练）都会打印一堆形状信息，既刷屏又拖慢速度。另外，forward hook 在某一层**成功完成**前向之后才触发，所以最后打印出的那一行是"最后一个成功的层"，出错的正是**它后面的那一层**——这正是定位 shape 问题的关键线索。
3. 训练模式下：`Dropout` 会随机置零（虽不影响形状，但输出有随机性）；`BatchNorm` 会用这个样本 batch **更新 `running_mean` / `running_var`**——`torch.no_grad()` 只关闭梯度，**不会**阻止 BatchNorm 更新统计量。用一个随便造的 `randn` 样本去污染真实模型的统计量，会影响后续评估。应先 `model.eval()`，结束后恢复原来的模式。
4. 修复版：

```python
def check_shapes(model, sample_input):
    print(f"  Input: {tuple(sample_input.shape)}")
    hooks = []

    def make_hook(name):
        def hook(module, inp, out):
            # inp 是位置参数组成的元组；用关键字参数调用时可能为空
            in_shape = tuple(inp[0].shape) if inp and hasattr(inp[0], "shape") else None
            out_shape = tuple(out.shape) if hasattr(out, "shape") else type(out).__name__
            print(f"    {name} ({type(module).__name__}): {in_shape} -> {out_shape}")
        return hook

    for name, module in model.named_modules():
        if name:
            hooks.append(module.register_forward_hook(make_hook(name)))

    was_training = model.training
    model.eval()                                  # 不更新 BatchNorm 统计量、关闭 Dropout
    try:
        with torch.no_grad():
            model(sample_input)
    finally:                                      # 无论成功还是抛异常都会执行
        for h in hooks:
            h.remove()
        model.train(was_training)                 # 恢复原来的模式
```

   原代码中的 `else inp.shape` 分支是死代码：PyTorch 传给 forward hook 的 `inp` 总是元组。

### Q11 — 参考答案

1. 第 136 行：100 个 `bytearray`，每个 `4 × 100 × 100 = 40,000` 字节，共 4,000,000 字节 ≈ **3906 KiB**；再加上 100 个 bytearray 对象本身的开销和列表对象，合计 3913 KiB。`count=201` 大约是 100 个对象 + 100 块数据缓冲区 + 1 个列表。第 137 行：一个 4,000,000 字节的 `bytearray` ≈ 3906 KiB，`count=2` 是对象本身和数据缓冲区。只打印了 2 行，是因为 `tracemalloc.start()` 写在这个函数**内部**，只追踪启动之后的分配；`statistics("lineno")` 只返回实际存在分配的行，不足 5 行就有几行打印几行。作者用 `4 × 元素个数` 模拟 float32 张量的字节数，使这个分支的数据量与 torch 分支一致。
2. 预期**基本看不到**。`tracemalloc` 只能追踪通过 Python 内存分配器（以及主动向它报告的扩展库）进行的分配。PyTorch 张量的数据缓冲区是由 PyTorch 自己的 C++ 分配器直接向操作系统申请的，不经过 Python 的分配器，因此 `tracemalloc` 只能看到 Python 层面那些很小的张量包装对象，看不到实际的 8 MB 数据。（当前环境没有 PyTorch，未能实测；NumPy 数组则会向 tracemalloc 报告其数据缓冲区。）这意味着讲义里"用 tracemalloc 找数据加载管线中最占内存的行"对 NumPy、Python 对象有效，对张量数据会严重低估。
3. 测量张量内存的方法：
   - 单个张量：`t.element_size() * t.nelement()`（字节数）；
   - GPU：`torch.cuda.memory_allocated()`、`memory_reserved()`、`torch.cuda.max_memory_allocated()`（峰值）、`torch.cuda.memory_summary()`；
   - CPU 进程整体：看进程的常驻内存 RSS（`htop`，或用 `psutil.Process().memory_info().rss`），或用讲义的 `memory_profiler`（它基于进程内存，而不是 Python 分配器）；
   - 想按算子分析：`torch.profiler` 开启内存分析（`profile_memory=True`）。

### Q12 — 参考答案

1. 先求每个参数梯度的 L2 范数 `‖gᵢ‖`，再计算 `√(Σ ‖gᵢ‖²)`，这等于把**所有参数的梯度拼成一个长向量后的 L2 范数**。`torch.nn.utils.clip_grad_norm_(params, max_norm)` 默认（`norm_type=2`）计算的正是这个总范数，并返回裁剪**之前**的值；传入 `max_norm=float("inf")` 时，它只计算、不改变梯度，可以直接拿来做监控。
2. **不会。** 梯度含 NaN 时 `grad_norm` 是 `nan`，而 `nan > 100` 和 `nan == 0` 都是 `False`（与 Q2 同理），两个 WARNING 都不会触发；`total_norm` 也会变成 `nan`，但没有任何提示。如果梯度含 Inf，`grad_norm > 100` 会触发，但报告的是 `inf`。
3. 每个参数都调用一次 `.item()`，每次都要把数据从 GPU 拷回 CPU，并**等待 GPU 完成之前所有排队的计算**（同步）。一个有几百个参数张量的模型，每一步就要同步几百次，GPU 流水线被反复打断，训练明显变慢。另外，`.data` 是旧式写法，推荐用 `.detach()`。
4. 改写版：

```python
import math

import torch


def check_gradient_health(model, large=100.0):
    names, norms = [], []
    for name, p in model.named_parameters():
        if p.grad is not None:
            names.append(name)
            norms.append(p.grad.detach().norm(2))       # 仍留在 GPU 上，不同步
    if not norms:
        print("  No gradients found: forgot loss.backward()? or all params frozen?")
        return 0.0

    stacked = torch.stack(norms)                       # 假设所有参数在同一设备上
    total = stacked.norm(2).item()
    for name, n in zip(names, stacked.tolist()):       # 只在这里同步一次
        if not math.isfinite(n):
            print(f"    WARNING: non-finite gradient in {name}: {n}")
        elif n > large:
            print(f"    WARNING: large gradient in {name}: {n:.2f}")
        elif n == 0:
            print(f"    WARNING: zero gradient in {name}")
    print(f"  Total gradient norm: {total:.4f}")
    return total
```

   实践中也不需要每一步都检查：每 N 步检查一次并记录到 TensorBoard 即可。

### Q13 — 参考回答要点

- **第一步，定位 NaN 从哪里来**：
  1. 打开 `torch.autograd.set_detect_anomaly(True)`（只在调试时用，速度很慢），它会在反向传播产生 NaN 时报告是哪个前向操作导致的；
  2. 在出现 NaN 的那一步设置条件断点，或者用讲义的 `detect_nan` 逐参数检查梯度中的 NaN / Inf；
  3. 用 `debug_print` 或 forward hook 逐层检查激活值，找到 NaN **第一次**出现的层；
  4. 检查这一步的**输入数据**本身是否含有 NaN / Inf（脏数据也很常见）。
- **常见原因与修复**（讲义列出前四种）：
  - 学习率过大 → 降低学习率、加 warmup、加梯度裁剪（`clip_grad_norm_`）；
  - 自定义 loss 里除以 0 → 分母加 epsilon；
  - 对 0 或负数取 log → `torch.log(x + 1e-8)`，或直接使用数值稳定的内置函数（例如用 `CrossEntropyLoss` 处理 logits，而不是自己先 softmax 再 log）；
  - RNN 等深层结构的梯度爆炸 → 梯度裁剪；
  - 混合精度下 fp16 溢出 → 使用 loss scaling（GradScaler）或改用 bf16。
- **判断时机**：从第 0 步就是 NaN，多半是数据或 loss 实现有问题；训练一段时间后才出现，多半是学习率过大、梯度爆炸或数值溢出。
- **加分点**：记录梯度范数曲线，NaN 之前往往能看到梯度范数先剧烈上升；保留出事前的 checkpoint 和那一个 batch，用于复现问题。

### Q14 — 参考回答要点

- **显存组成**：①模型参数；②梯度（与参数一样大）；③优化器状态（Adam 为每个参数保存一阶和二阶矩，是参数量的 2 倍）；④**激活值**（前向时保存下来供反向使用，与 batch size、序列长度、层数成正比）；⑤临时缓冲区、CUDA 上下文、缓存分配器保留的块。
- **为什么 OOM 常发生在 backward**：前向结束时所有激活都还保存在显存里；反向过程中又要为梯度和中间结果分配新的显存，此时正好是峰值。第一次 `optimizer.step()` 时 Adam 的状态才真正被创建，所以 OOM 也常出现在第一步更新时。
- **7B 模型粗略估算**（只算参数、梯度、优化器状态，不含激活）：
  - 全 fp32 + Adam：参数 4 + 梯度 4 + Adam 两个状态 8 = **每个参数 16 字节**，7B × 16 B ≈ **112 GB**；
  - 常见的混合精度训练（fp16/bf16 参数和梯度各 2 字节 + fp32 主权重 4 + Adam 状态 8）同样约为每参数 16 字节，也是 ≈ 112 GB——混合精度主要省的是**激活**和计算时间，并不是讲义所说的"把显存减半"那么简单；
  - 对比：仅做 fp16 推理时只需参数 7B × 2 B ≈ 14 GB（与第 07 节"7B fp16 = 14 GB"一致）。
- **降显存手段**：减小 batch size 并配合梯度累积、混合精度、梯度检查点（用重新计算换显存）、优化器状态分片（ZeRO / FSDP）、LoRA 等参数高效微调、8-bit 优化器。
- **常见误区**：以为 `empty_cache()` 能解决 OOM；把 `nvidia-smi` 的读数当作张量实际占用量。

### Q15 — 参考回答要点

- **定位**：
  1. 用讲义的 `Timer` 分段计时：数据加载、前向、反向、优化器更新各占多少（GPU 部分记得 `synchronize`）；
  2. `htop` 看 CPU：如果数据加载进程的 CPU 占满、GPU 在空转，瓶颈在数据管线；
  3. `python -m cProfile -s cumtime train.py` 找出最耗时的 Python 函数（例如数据增强、分词）；
  4. 用 `torch.profiler` 查看 GPU 时间线上的空隙和频繁的 CPU-GPU 同步点。
- **常见原因与优化**：
  - 数据加载慢（讲义："Common finding: data loading takes 60% of training time"）→ `DataLoader(num_workers>0, pin_memory=True)`、预取、把昂贵的预处理改为离线完成、使用 Parquet 等更快的存储格式（第 09 节）；
  - 每步都调用 `.item()`、`print(tensor)`、`.cpu()` 导致频繁同步 → 每 N 步才记录一次；
  - batch 太小，GPU 喂不饱 → 增大 batch size；
  - 没有使用混合精度 → 开启 AMP，利用 Tensor Core；
  - 大量小算子、Python 循环 → 向量化，或使用 `torch.compile` 进行融合；
  - 共享机器上有其他进程在抢 GPU / CPU（第 10 节 Q16）。
- **加分点**：区分"GPU 利用率"（只要有任何内核在运行就算忙）和真正的算力利用率（MFU），利用率高也不代表算得高效。

### Q16 — 参考回答要点

- **训练前（几分钟内完成）**：
  1. `check_shapes` 跑一个样本 batch，确认每一层的形状符合预期；
  2. 检查初始 loss：分类任务随机初始化时应接近 `ln(类别数)`（10 类约为 2.30，与 `debug_tools.py` 演示中的正常 loss 量级一致）；偏差太大说明初始化或 loss 有问题；
  3. **单 batch 过拟合测试**：在一个小 batch 上训练几百步，loss 应该能降到接近 0；降不下去说明模型、loss 或优化器的连接有 bug；
  4. 数据检查：train / val / test 是否有重叠（`check_data_leakage`），标签分布是否合理，输入中是否有 NaN；
  5. `check_devices` 确认模型和数据在同一设备上；
  6. 先用几十步做冒烟测试（smoke test），确认 checkpoint 能保存并能恢复。
- **训练中（自动监控）**：
  - 用 TensorBoard 记录 loss（训练 / 验证）、学习率、总梯度范数、权重和梯度直方图（讲义第八部分）、吞吐量（样本/秒）、显存峰值；
  - 自动报警：loss 为 NaN / Inf 时立即停止并保存现场（讲义的 `detect_nan`）；loss 突增超过阈值时记录 WARNING；梯度范数异常；吞吐量骤降；
  - 用 logging 写入文件，保存完整日志，便于事后排查（讲义："When a training run fails at 3 AM, you want a log file"）。
- **工程化**：把这些检查做成训练框架里的回调或钩子，所有实验默认开启，而不是依赖个人记得手动添加。

### Q17 — 参考回答要点

- **不能。** ID 不重叠只排除了"同一条记录同时出现在两个集合"这一种情况。
- **还应检查**：
  1. **近重复样本**：内容相同或几乎相同、但 ID 不同的样本（爬取的网页、转发的文本、数据增强后的图片），可以用内容哈希、MinHash 或 embedding 相似度检测；
  2. **特征泄漏**：某些特征本身就包含了标签信息（例如由标签派生出的字段、只有在结果出现之后才会存在的字段）；检查方法是看单个特征的预测力是否高得离谱；
  3. **时间泄漏**：讲义提到的"用未来预测过去"，应按时间排序后再切分；
  4. **分组泄漏**：同一用户、患者、文档的不同样本被分到不同集合；
  5. **预处理泄漏**：在全量数据上拟合了标准化、词表、特征选择等（第 09 节 Q8）；
  6. **评测污染**：LLM 场景中测试题出现在预训练语料里。
- **验证手段**：用一个简单的基线模型（甚至只用一个特征）也能得到很高的准确率，就是强烈的泄漏信号；换一个完全独立、新收集的测试集看准确率是否明显下降。

---

## 六、关联知识点

### 前置知识
- [阶段 00 · 01 开发环境](../../01-dev-environment/docs/zh.md)：安装 PyTorch，能运行脚本。
- [阶段 00 · 08 编辑器设置](../../08-editor-setup/docs/zh.md)：Debugpy 扩展与 `launch.json`，讲义第九部分的 VS Code 调试器依赖它。
- [阶段 00 · 10 终端与 Shell](../../10-terminal-and-shell/docs/zh.md)：stdout / stderr 重定向、`tail -f` 盯日志（对应 Q8）。

### 本节被哪些后续内容用到
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：NaN / Inf 的数学根源，log-sum-exp 等稳定写法（对应 Q13）。
- [阶段 03 · 03 反向传播](../../../03-deep-learning-core/03-backpropagation/docs/zh.md)：理解梯度为什么会消失或爆炸。
- [阶段 03 · 11 PyTorch 入门](../../../03-deep-learning-core/11-intro-to-pytorch/docs/zh.md)：张量、设备、autograd、hook 的系统讲解。
- [阶段 03 · 13 调试神经网络](../../../03-deep-learning-core/13-debugging-neural-networks/docs/zh.md)：本节方法在完整训练中的深入应用（对应 Q16）。
- [阶段 10 · 34 梯度检查点](../../../10-llms-from-scratch/34-gradient-checkpointing/docs/zh.md)：讲义 OOM 对策第 5 条的原理与实现。
- [阶段 19 · 45 梯度裁剪与 AMP](../../../19-capstone-projects/45-gradient-clipping-amp/docs/zh.md)：梯度范数监控、裁剪与混合精度（对应 Q12、Q14）。
- [阶段 17 · 13 LLM 可观测性](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：把日志和指标从训练延伸到线上服务。

### 延伸关键词
`torch.autograd.set_detect_anomaly` · `torch.profiler` · `CUDA 异步执行 / synchronize` · `caching allocator` · `max_memory_allocated` · `GradScaler / bf16` · `clip_grad_norm_` · `overfit one batch` · `PYTHONBREAKPOINT` · `py-spy`
