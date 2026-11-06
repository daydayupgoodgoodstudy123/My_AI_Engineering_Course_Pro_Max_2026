# 代码讲解 · gpu_check.py

> **所属小节**：阶段 00 · 环境搭建与工具 · 第 03 节 GPU 设置和云 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python gpu_check.py`（无命令行参数） ｜ **依赖**：标准库 `time` + `torch`（PyTorch）。没装 torch 也能运行，只会打印安装提示；要看到基准测试部分需要 NVIDIA GPU + CUDA 版 PyTorch

---

## 1. 这份代码在考察什么

这是一个 50 行的"GPU 体检脚本"，把讲义中的三段代码（检测 GPU、CPU vs GPU 基准、显存估算）串成一次运行：

1. **检测链路**：PyTorch 有没有装 → CUDA 能不能用 → 是哪块卡、多少显存、什么计算能力。
2. **GPU 的异步执行模型**：为什么计时必须配合 `torch.cuda.synchronize()`。
3. **CPU vs GPU 的数量级差距**：同样的 4000×4000 矩阵乘，亲眼看到加速比。
4. **显存决定模型规模**：用"fp16 每参数 2 字节"的法则，从显存反推能放下多大的模型。
5. **优雅降级**：没有 torch、没有 GPU 都不报错，而是告诉你"没关系，用 Colab"。

> 一句话：**先确认"我手上到底有什么算力"，再谈训练什么模型。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `import time` | 模块导入 | 计时 | 基准测试 |
| `check_gpu()` 第 1 段 | 函数内 `try/except ImportError` | 检查 PyTorch 是否安装 | 依赖检测、优雅降级 |
| `check_gpu()` 第 2 段 | `if not torch.cuda.is_available()` | 无 CUDA 时提示并提前返回 | CUDA 可用性 |
| `check_gpu()` 第 3 段 | 属性查询 | 打印 CUDA 版本、GPU 名称、显存、计算能力 | 设备属性 |
| `check_gpu()` 第 4 段 | 计时代码 | CPU 与 GPU 各做一次 4000×4000 矩阵乘并比较 | 并行计算、异步执行 |
| `check_gpu()` 第 5 段 | 算术 | 显存 / 2 字节 → 可容纳参数量 | fp16 经验法则 |
| `if __name__ == "__main__":` | 入口 | 直接运行时调用 `check_gpu()` | — |

整个脚本只有一个函数，自上而下顺序执行，遇到"条件不满足"就打印提示并 `return`——这是典型的**卫语句（guard clause）**结构。

---

## 3. 逐段精讲

### 3.1 在函数内部导入 torch：没装也不崩

```python
import time


def check_gpu():
    try:
        import torch
    except ImportError:
        print("PyTorch not installed. Run: pip install torch")
        return
```

- 文件顶部只导入标准库 `time`；`torch` 放在函数里、用 `try/except ImportError` 包住。这样即使环境里没有 PyTorch，脚本也能运行并给出明确提示，而不是抛出一长串 `ModuleNotFoundError` 栈信息（`ModuleNotFoundError` 是 `ImportError` 的子类，同样会被捕获）。
- 函数里的 `return` 不带值，等价于返回 `None`，用来**提前结束**。
- ⚠️ 提示语是 `pip install torch`。结合第 01 节：在课程推荐的环境里应该是激活虚拟环境后 `uv pip install ...`，而 NVIDIA 机器要带上对应的 CUDA 索引地址，Mac 用默认版本。

### 3.2 CUDA 可用性检查：卫语句提前返回

```python
    print("=== GPU Check ===\n")
    print(f"PyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    if not torch.cuda.is_available():
        print("\nNo GPU detected. That's fine for most lessons.")
        print("For GPU-heavy lessons, use Google Colab (free).")
        return
```

- 先打印 PyTorch 版本——排查问题时第一个要知道的信息。
- `torch.cuda.is_available()` 为 False 的常见原因：没有 NVIDIA 卡、驱动有问题、装的是 CPU 版 PyTorch、或者在 Mac 上。
- 提示语与讲义一致："大多数课程不需要 GPU，GPU 重的课程用 Colab"。
- ⚠️ **刻意的简化（也是局限）**：脚本只认 CUDA。Apple Silicon 上即使 `torch.backends.mps.is_available()` 为 True，也会打印 "No GPU detected"。第 01 节的 `verify.py` 则会检测 MPS——两者对照着看，就知道一个完整的检测应该怎么写（见第 7 部分练习）。

### 3.3 设备属性：显存与计算能力

```python
    print(f"CUDA version: {torch.version.cuda}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")

    props = torch.cuda.get_device_properties(0)
    print(f"Memory: {props.total_memory / 1e9:.1f} GB")
    print(f"Compute capability: {props.major}.{props.minor}")
```

- `torch.version.cuda`：**这个 PyTorch 是针对哪个 CUDA 版本编译的**（例如 cu124 的 wheel 对应 `12.4`），不是驱动版本，也不是 `nvidia-smi` 右上角显示的那个数字。
- 参数 `0` 表示第 0 块 GPU。多卡机器上编号从 0 开始；脚本只看第一块。
- `get_device_properties(0)` 返回一个属性对象，存进 `props` 复用，避免重复查询。
- `total_memory` 单位是**字节**，除以 `1e9` 得到十进制 GB。⚠️ 显卡容量常按 GiB（`1024³`）标称，所以"24 GB"的卡这里可能显示 `25.x GB` 左右，这不是 bug。
- **计算能力（compute capability）**`major.minor` 是 NVIDIA 给每一代 GPU 架构的编号，决定支持哪些硬件特性（例如某些低精度格式、某些优化 kernel）。很多库会要求最低计算能力，所以把它打印出来便于对照。

### 3.4 CPU 基准：先测 CPU

```python
    print("\n=== CPU vs GPU Benchmark ===\n")
    size = 4000

    a = torch.randn(size, size)
    b = torch.randn(size, size)

    start = time.time()
    _ = a @ b
    cpu_time = time.time() - start
    print(f"CPU matrix multiply ({size}x{size}): {cpu_time:.3f}s")
```

- `torch.randn(size, size)` 生成标准正态分布的随机矩阵，默认在 CPU 上、dtype 为 float32。
- `@` 是矩阵乘法运算符。4000×4000 的矩阵乘大约需要 `2 × 4000³ ≈ 1.28 × 10¹¹` 次浮点运算（乘和加各算一次），足够体现差距。
- `_ = a @ b`：用 `_` 接收结果，表示"这个值我不关心，只是为了让计算发生"。
- 讲义里的版本用 `size = 5000`，脚本用 4000，运行更快一些。

### 3.5 GPU 基准：两次 synchronize 的意义

```python
    a_gpu = a.to("cuda")
    b_gpu = b.to("cuda")
    torch.cuda.synchronize()

    start = time.time()
    _ = a_gpu @ b_gpu
    torch.cuda.synchronize()
    gpu_time = time.time() - start
    print(f"GPU matrix multiply ({size}x{size}): {gpu_time:.3f}s")
    print(f"Speedup: {cpu_time / gpu_time:.0f}x")
```

这是全文件最重要的一段：

- `.to("cuda")` 把张量从 CPU 内存拷贝到显存，返回一个**新**张量（原来的 `a` 仍在 CPU 上）。拷贝放在计时之外，所以这里比较的是**纯计算速度**。
- **CUDA 是异步的**：`a_gpu @ b_gpu` 只是把 kernel 放进 GPU 的任务队列，Python 几乎立即返回。
  - 计时前的 `synchronize()`：等之前所有 GPU 工作做完，计时起点干净。
  - 计时后的 `synchronize()`：等矩阵乘真正算完再停表。少了它，`gpu_time` 只是"提交任务"的时间，加速比会被夸大得离谱。
- `{cpu_time / gpu_time:.0f}x`：`.0f` 取整显示，例如 `45x`。
- ⚠️ **刻意的简化**：
  - **没有预热（warm-up）**：首次 GPU 调用包含 cuBLAS 初始化、显存分配等一次性开销，会让 GPU 显得比实际慢；CPU 首次调用也可能有线程池启动等开销。
  - **只测一次**：受系统抖动影响大。
  - **用 `time.time()`**：墙上时钟可能被系统校时调整，测时间间隔更推荐 `time.perf_counter()`。
  - 所以这里的 "Speedup" 只适合看**数量级**，严谨的做法见测验 Q10。

### 3.6 显存 → 最大模型规模估算

```python
    vram_gb = props.total_memory / 1e9
    params_fp16 = vram_gb * 1e9 / 2
    params_billions = params_fp16 / 1e9
    print(f"\nEstimated max model size (fp16): ~{params_billions:.0f}B parameters")
```

- 三步换算写得很"啰嗦"，是为了让每个量的单位一目了然：
  1. `vram_gb`：显存（GB）；
  2. `params_fp16`：显存字节数 ÷ 每参数 2 字节 = 可容纳的参数个数；
  3. `params_billions`：换算成"十亿（B）"。
  数学上就等于 `vram_gb / 2`。
- 例：16 GB → ~8B；24 GB → ~12B（按十进制 GB 计）。
- ⚠️ 这是**只算权重**的上界。真实推理还要 KV cache、激活和框架开销；训练还要梯度和优化器状态（Adam 混合精度训练常按约 16 字节/参数估算），能训练的模型远小于这个数字。

### 3.7 入口

```python
if __name__ == "__main__":
    check_gpu()
```

- 直接运行时执行检查；被其他文件 `import gpu_check` 时不会自动运行，可以单独调用 `check_gpu()`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 函数内 `import torch` + `except ImportError` | 没装 torch 也能给出友好提示 | 生产代码一般在顶部导入，依赖由锁文件保证 |
| 卫语句逐级 `return` | 结构扁平，读起来像检查清单 | 函数里打印和逻辑混在一起，不便测试；可拆成"检测函数返回数据 + 打印函数" |
| 只检测 CUDA | 讲义聚焦 NVIDIA 与云 GPU | 漏掉 Apple MPS；完整检测应依次判断 CUDA → MPS → CPU |
| 拷贝放在计时外 | 只比较计算速度 | 真实训练中数据传输可能是瓶颈，需要单独评估 |
| 两次 `synchronize` | 异步执行下计时才准确 | 也可以用 `torch.cuda.Event(enable_timing=True)` 在 GPU 时间线上计时 |
| 单次计时、无预热、`time.time()` | 代码最短，展示数量级 | 正式基准要预热、多次重复、用 `perf_counter` 或 profiler |
| 固定 `size = 4000` | 足够大以体现差距，又不会太慢 | 可做成命令行参数，测不同规模下的加速比曲线 |
| fp16 = 2 字节/参数 | 简单好记的经验法则 | 只算权重；训练/长上下文推理需另算 |
| `1e9` 作为 GB | 计算简单 | 与 GiB 存在约 7% 差异 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `def` 定义函数 | `def check_gpu():` | 无参数函数，把整个流程封装起来 |
| 函数内导入 | `try: import torch` | 只有执行到这里才导入，常用于可选依赖 |
| `try / except` | `except ImportError:` | 捕获"模块导不进来"；`ModuleNotFoundError` 是它的子类 |
| 不带值的 `return` | `return` | 提前结束函数，返回 `None` |
| `if not ...` | `if not torch.cuda.is_available():` | 对布尔值取反 |
| f-string | `f"PyTorch version: {torch.__version__}"` | 字符串里直接嵌入表达式 |
| f-string 格式符 `.1f` / `.3f` / `.0f` | `{props.total_memory / 1e9:.1f}`、`{cpu_time:.3f}s`、`{cpu_time / gpu_time:.0f}x` | 保留 1 / 3 / 0 位小数（`.0f` 会四舍五入取整） |
| 字符串中的 `\n` | `"=== GPU Check ===\n"` | 换行符，制造空行分隔各段输出 |
| 科学计数法字面量 | `1e9` | 等于 `1000000000.0`（float） |
| `@` 运算符 | `a @ b` | 矩阵乘法，PyTorch 张量实现了 `__matmul__` |
| 下划线变量 `_` | `_ = a @ b` | 约定俗成表示"不使用的值" |
| 属性访问 | `props.major`、`props.minor`、`props.total_memory` | 读取对象属性 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 |

---

## 6. 运行结果解读

**实际运行**（在临时副本中，本机未安装 PyTorch；尝试安装 CPU 版 PyTorch 时下载源被网络策略拦截，因此只能实测第一种分支）：

```text
PyTorch not installed. Run: pip install torch
```

- 走的是 3.1 节的 `except ImportError` 分支，退出码为 0（脚本把"没装 torch"视为正常提示，而不是错误）。

**未实际运行的分支（原因：本机无 PyTorch、无 NVIDIA GPU），根据代码预期如下：**

装了 PyTorch 但没有 CUDA（如普通笔记本或 Mac）：

```text
=== GPU Check ===

PyTorch version: <你的版本>
CUDA available: False

No GPU detected. That's fine for most lessons.
For GPU-heavy lessons, use Google Colab (free).
```

有 NVIDIA GPU（如 Colab T4）时，输出结构如下（具体数值取决于硬件，这里用占位符表示）：

```text
=== GPU Check ===

PyTorch version: <版本>
CUDA available: True
CUDA version: <PyTorch 编译所用的 CUDA 版本，如 12.4>
GPU: <显卡型号>
Memory: <显存> GB
Compute capability: <major>.<minor>

=== CPU vs GPU Benchmark ===

CPU matrix multiply (4000x4000): <秒数>s
GPU matrix multiply (4000x4000): <秒数>s
Speedup: <倍数>x

Estimated max model size (fp16): ~<显存/2>B parameters
```

读输出时注意：
- `Speedup` 一般是几十倍以上的量级，但因为没有预热，GPU 时间里含有首次调用的初始化开销，**多跑几次结果会有差异**，第一次往往偏慢。
- `Memory` 显示的是十进制 GB，会比显卡标称的 GiB 数字略大。
- 最后一行是"只装权重"的上限，不代表能训练这么大的模型。

---

## 7. 动手改一改

1. **支持 Apple MPS**：在 CUDA 判断之后加一段 `elif torch.backends.mps.is_available():`，打印 "Apple MPS available"，并用 `"mps"` 设备跑同样的基准（同步用 `torch.mps.synchronize()`）。
2. **加预热和多次重复**：先跑 3 次不计时，再跑 10 次取平均，对比改动前后的 `Speedup`。
3. **换成 `time.perf_counter()`**，并思考它与 `time.time()` 的区别。
4. **用 fp16 再测一次**：`a_gpu.half() @ b_gpu.half()`，观察有 Tensor Core 的卡上速度变化（注意 CPU 上 fp16 矩阵乘可能很慢或不受支持，只在 GPU 上比较）。
5. **多卡信息**：用 `torch.cuda.device_count()` 遍历所有 GPU，逐个打印名称和显存。
6. **更真实的显存估算**：给估算函数加一个 `bytes_per_param` 参数，分别打印 fp32（4）、fp16（2）、int8（1）、int4（0.5）以及"Adam 训练约 16 字节/参数"下的最大参数量。

---

## 8. 常见坑

- **忘记 `synchronize`**：GPU 时间被严重低估，得到上万倍的"加速"。
- **不预热就下结论**：第一次调用包含初始化开销，GPU 看起来比实际慢；多跑几次才稳定。
- **把 `torch.version.cuda` 当成驱动版本**：它是 PyTorch 编译时用的 CUDA 版本；驱动支持的最高版本要看 `nvidia-smi`。
- **在 Mac 上看到 "No GPU detected" 就以为没有加速**：本脚本不检测 MPS，用 `torch.backends.mps.is_available()` 自己确认。
- **用权重估算去判断能否训练**：训练还需要梯度、优化器状态和激活，显存需求是推理的数倍。
- **装成了 CPU 版 PyTorch**：在 NVIDIA 机器上显示 `CUDA available: False`，再用 `python -c "import torch; print(torch.version.cuda)"` 检查，若输出 `None`，多半是安装时没有指定 CUDA 版本的下载地址（见第 01 节）。
