# 代码讲解 · notebook_tips.py

> **所属小节**：阶段 00 · 环境搭建与工具 · 第 05 节 Jupyter 笔记本 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python notebook_tips.py`（无命令行参数；会在当前目录生成 `notebook_plot.png`）。也可以按讲义练习 3，把各函数粘贴进 Jupyter/Colab 的 cell 中运行 ｜ **依赖**：标准库 `time`、`sys`；第三方 `numpy`、`matplotlib`、`pandas`

---

## 1. 这份代码在考察什么

这是一个"**notebook 技巧的脚本版演示**"：在终端里用普通 Python 复刻讲义中 notebook 的几个核心场景，并通过对比让你理解 notebook 到底多做了什么。

1. **计时**：手动用 `time.perf_counter()` 做 `%timeit` / `%%time` 的事，顺便对比 Python 列表与 NumPy 向量化的速度。
2. **绘图**：在没有 notebook 内联显示的情况下，用 Agg 后端把图保存为 PNG——体会 `%matplotlib inline` 帮你省掉了什么。
3. **表格展示**：`df.to_string()` 的纯文本表格 vs notebook 里直接写 `df` 得到的 HTML 表格。
4. **内存意识**：大数组占多少内存，以及为什么 notebook 里内存会在 cell 之间不断累积。
5. **magic 命令速查**：把常用 magic 命令打印成一张小抄。

> 一句话：**先在脚本里看清"手动版"，才能真正理解 notebook 的便利从哪来、陷阱又在哪。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 文件头导入 + `matplotlib.use("Agg")` | 模块级代码 | 导入依赖，选择无界面绘图后端 | 脚本环境 vs notebook 环境 |
| `timing_comparison()` | 函数 | 计时列表推导与 NumPy 平方 100 万个数 | `%timeit`、向量化 |
| `inline_plotting()` | 函数 | 画"正弦 vs 加噪"折线图和噪声直方图，保存为 PNG | `%matplotlib inline`、富输出 |
| `dataframe_display()` | 函数 | 构造模型对比表，文本打印并找出最佳/最快模型 | DataFrame 富文本显示 |
| `memory_check()` | 函数 | 计算不同规模数组的内存占用 | 内存累积陷阱 |
| `magic_command_equivalents()` | 函数 | 打印 magic 命令小抄，并手动做一次微基准 | magic 命令 |
| `if __name__ == "__main__":` | 入口 | 依次调用以上 5 个函数 | — |

5 个函数彼此独立、没有共享状态，就像 notebook 里 5 个可以单独运行的 cell；入口按固定顺序调用它们——这恰好是 notebook "Restart & Run All" 想要保证的效果。

---

## 3. 逐段精讲

### 3.1 导入与 Agg 后端

```python
import time
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
```

- 导入按"标准库 → 第三方"分组，中间空一行，这是 PEP 8 推荐的风格。
- `matplotlib.use("Agg")`：选择 **Agg**（一个非交互式的光栅渲染后端），只在内存中画图并写入文件，不需要图形界面。脚本在终端、SSH、服务器或 CI 中运行时都不会尝试弹窗。
- 它写在 `import matplotlib.pyplot` **之前**，这是惯用且最稳妥的顺序：先定后端，再加载 pyplot。
- ⚠️ 在 notebook 里不需要（也不应该）这样写——notebook 使用内联后端，讲义用 `%matplotlib inline` 让图直接显示在 cell 下方。

### 3.2 `timing_comparison`：列表 vs NumPy

```python
def timing_comparison():
    print("=== Timing: List vs NumPy ===\n")

    size = 1_000_000

    start = time.perf_counter()
    python_list = [x ** 2 for x in range(size)]
    list_time = time.perf_counter() - start
    print(f"List comprehension: {list_time:.4f}s")

    start = time.perf_counter()
    numpy_array = np.arange(size) ** 2
    numpy_time = time.perf_counter() - start
    print(f"NumPy:              {numpy_time:.4f}s")
    print(f"Speedup:            {list_time / numpy_time:.1f}x")
```

- `1_000_000`：数字字面量中的下划线只为可读性，等于 `1000000`。
- `time.perf_counter()`：高精度、单调递增的计时器，专门用来测时间间隔（比 `time.time()` 更合适）。"结束时间 − 开始时间"就是 `%%time` 的手动版。
- 两种写法做同一件事——计算 0 到 999,999 每个数的平方：
  - 列表推导：Python 解释器逐个元素循环，每个 `x ** 2` 都要创建一个 Python 整数对象。
  - `np.arange(size) ** 2`：**向量化**，循环发生在 NumPy 的 C 代码里，作用于一整块连续内存。
- 打印时 `NumPy:` 后面补了空格，让三行冒号后的数值对齐。
- ⚠️ **刻意的简化**：每种方法只测**一次**。实测连续运行 4 次，`Speedup` 分别是 2.7x、3.7x、10.2x、3.5x，波动巨大；用 `timeit` 多轮重复取最好值后稳定在约 44–49x（见测验 Q9）。这正是 `%timeit` 要"运行很多次取统计"的原因。
- `python_list`、`numpy_array` 赋值后没有使用，只是为了让计算发生（也可以写成 `_ = ...`）。

### 3.3 `inline_plotting`：脚本里怎么"内联"画图

```python
def inline_plotting():
    print("\n=== Inline Plotting ===\n")

    np.random.seed(42)
    x = np.linspace(0, 10, 200)
    y_sin = np.sin(x)
    y_noisy = y_sin + np.random.normal(0, 0.2, 200)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].plot(x, y_sin, label="sin(x)")
    axes[0].plot(x, y_noisy, alpha=0.5, label="noisy")
    axes[0].set_title("Signal vs Noise")
    axes[0].legend()

    axes[1].hist(y_noisy - y_sin, bins=30, edgecolor="black")
    axes[1].set_title("Noise Distribution")

    plt.tight_layout()
    plt.savefig("notebook_plot.png", dpi=100)
```

- `np.random.seed(42)`：固定随机种子，每次生成的"噪声"都一样，结果可复现。（新代码更推荐 `rng = np.random.default_rng(42)` 的生成器写法，这里用的是传统全局接口。）
- `np.linspace(0, 10, 200)`：在 [0, 10] 上均匀取 200 个点（包含两端）。
- `np.random.normal(0, 0.2, 200)`：均值 0、标准差 0.2 的 200 个高斯噪声，与 `y_sin` 逐元素相加——又一次向量化运算。
- `plt.subplots(1, 2, figsize=(12, 4))`：一行两列的子图，返回画布 `fig` 和子图数组 `axes`。`figsize` 单位是英寸，配合 `dpi=100` 得到 1200×400 像素的图片。
- 左图：两条曲线，`alpha=0.5` 让噪声曲线半透明；`label` + `legend()` 生成图例。
- 右图：`y_noisy - y_sin` 恰好就是加入的噪声本身，直方图呈现近似钟形（高斯分布），中心在 0 附近。
- `tight_layout()` 自动调整子图间距，防止标题、刻度重叠。
- `savefig` 把图写到**当前工作目录**下的 `notebook_plot.png`。在 notebook 中，把最后一行换成 `plt.show()`，图就直接显示在 cell 下方——这就是脚本打印的提示 "In a notebook, plt.show() displays this inline." 的含义。

### 3.4 `dataframe_display`：文本表格 vs 富表格

```python
def dataframe_display():
    print("\n=== DataFrame Display ===\n")

    df = pd.DataFrame({
        "model": ["Linear Regression", "Random Forest", "Neural Network", "XGBoost"],
        "accuracy": [0.72, 0.89, 0.94, 0.91],
        "train_time_sec": [0.1, 2.3, 45.6, 8.2],
        "parameters": [102, 50_000, 1_200_000, 25_000],
    })

    print("In a notebook, just typing 'df' renders a rich HTML table:\n")
    print(df.to_string(index=False))

    print(f"\nBest model: {df.loc[df['accuracy'].idxmax(), 'model']}")
    print(f"Fastest model: {df.loc[df['train_time_sec'].idxmin(), 'model']}")
```

- 用"列名 → 列表"的字典构造 DataFrame，每个列表是一列。
- `df.to_string(index=False)`：把整张表转成纯文本，并去掉左侧的行号索引。在 notebook 里，如果 `df` 是 cell 的**最后一个表达式**，它会被渲染成带样式的 HTML 表格；而 `print(df)` 永远只是文本。
- `df['accuracy'].idxmax()` 返回准确率最大值所在的**行标签**（这里是 2），再用 `df.loc[行标签, 'model']` 取出模型名。`idxmin()` 同理。这是 pandas 里"按某列找最优行"的惯用写法。
- f-string 外层双引号、内层列名单引号，避免引号冲突。
- ⚠️ 这里把"计算"和"打印"混在一起，便于演示；按"脚本交付"的原则，应该拆出一个只返回结果的函数（见测验 Q10）。

### 3.5 `memory_check`：内存意识

```python
def memory_check():
    print("\n=== Memory Usage ===\n")

    small = np.random.randn(1000)
    medium = np.random.randn(100_000)
    large = np.random.randn(10_000_000)

    for name, arr in [("1K", small), ("100K", medium), ("10M", large)]:
        size_mb = arr.nbytes / 1e6
        print(f"Array {name:>4s} elements: {size_mb:>8.2f} MB")

    print(f"\nPython process memory: ~{sys.getsizeof(large) / 1e6:.1f} MB for the large array")
    print("In notebooks, memory accumulates across cells. Restart the kernel to free it.")
```

- `np.random.randn` 默认 `float64`，每个元素 8 字节，所以 `nbytes` = 元素数 × 8：1K → 0.008 MB（显示为 `0.01`），100K → 0.80 MB，10M → 80.00 MB。
- `for name, arr in [(...), (...)]`：遍历元组列表并**解包**成两个变量。
- 格式符：`{name:>4s}` 字符串右对齐到 4 宽；`{size_mb:>8.2f}` 浮点数右对齐到 8 宽、两位小数——三行数字整齐对齐。
- ⚠️ **标签有误导性**：`sys.getsizeof(large)` 是"这个数组对象"的大小（实测 80,000,112 字节 = 数据 + 112 字节对象头），并不是"Python 进程内存"。进程总内存要用操作系统指标（如 `psutil`）来看。而且对一个**视图**（如 `large[::2]`）调用 `getsizeof` 只会得到 112 字节，因为视图不拥有数据。统计 NumPy 内存应该用 `nbytes`。
- 这一段的核心启示：在脚本里，函数返回后 `large` 就失去引用、可以被回收；但在 notebook 里，cell 中定义的变量是**全局变量**，会一直留在 kernel 中，反复加载数据就会不断累积——讲义"内存泄漏"陷阱的根源。

### 3.6 `magic_command_equivalents`：小抄 + 手动微基准

```python
def magic_command_equivalents():
    print("\n=== Magic Command Equivalents ===\n")
    print("In a notebook, you would use magic commands:")
    print("  %timeit np.random.randn(10000)    -> micro-benchmark")
    print("  %%time long_operation()            -> wall clock time")
    # ... %matplotlib inline / !pip install / %env VAR
    print()

    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        np.random.randn(10000)
    elapsed = time.perf_counter() - start
    per_call = elapsed / iterations * 1e6

    print(f"Manual timing (like %%timeit): np.random.randn(10000)")
    print(f"  {per_call:.1f} us per call ({iterations} iterations)")
```

- 前半段只是打印字符串小抄。普通字符串里的 `%` 没有特殊含义，原样输出。
- ⚠️ 小抄里 `%%time long_operation()` 是压缩成一行的写法。在 notebook 中，`%%time` 作为单元格魔法应该**单独占第一行**、要计时的代码写在下面（讲义里的示例就是这样）；只给一行代码计时用行魔法 `%time long_operation()`。
- 后半段是 `%timeit` 的手动版：循环 1000 次，总时间除以次数得到单次耗时，`× 1e6` 把秒换成微秒（`us` 即 µs）。`for _ in range(...)` 中的 `_` 表示不使用循环变量。
- 最后一个 `print` 用了 f-string，但里面的 `%%timeit` 不是占位符，会原样输出 `%%timeit`（IPython 中 `%%timeit` 是 `%timeit` 的单元格版本）。
- 与真正的 `%timeit` 相比，这里只有一轮、没有标准差，也没有自动决定循环次数。

### 3.7 入口

```python
if __name__ == "__main__":
    print("Notebook Tips - Key Patterns\n")
    print("Run these in a Jupyter notebook to see rich output.\n")

    timing_comparison()
    inline_plotting()
    dataframe_display()
    memory_check()
    magic_command_equivalents()
```

- 每个函数相当于一个 cell，入口按固定顺序"Run All"。讲义练习 3 建议把它们粘贴到 Colab 中运行，对比脚本输出与 notebook 富输出的差异。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用脚本"模拟" notebook 功能 | 对比之下看清 notebook 的便利来自哪里 | 富输出（HTML 表格、内联图）只能用文字描述 |
| `matplotlib.use("Agg")` + `savefig` | 无界面环境也能稳定运行 | 在 notebook 中要去掉，改用 `%matplotlib inline` + `plt.show()` |
| 每个功能一个独立函数 | 像独立 cell，可单独调用，互不干扰 | 函数既算又打印，不便测试；生产中分离计算与展示 |
| 单次 `perf_counter` 计时 | 代码最短，演示 `%%time` 原理 | 结果波动大；微基准应用 `timeit` / `%timeit` 多次重复 |
| `np.random.seed(42)` | 图形可复现 | 全局随机状态；新代码用 `default_rng` |
| `sys.getsizeof` 估内存 | 一行代码就能演示 | 不是进程内存，对视图不准；用 `nbytes` 或 `psutil` |
| 图片写到当前目录 | 简单 | 在源码目录运行会留下产物文件；可输出到临时/输出目录 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 导入别名 | `import numpy as np`、`import pandas as pd` | 社区约定的简称 |
| 数字下划线分隔 | `1_000_000`、`50_000` | 只为可读性，值不变 |
| 幂运算 | `x ** 2`、`np.arange(size) ** 2` | 对数组是逐元素运算（向量化） |
| 列表推导式 | `[x ** 2 for x in range(size)]` | 一行生成列表 |
| `range` | `range(size)` | 惰性生成 0..size-1 的整数序列 |
| 元组解包 | `fig, axes = plt.subplots(...)`；`for name, arr in [...]` | 一次给多个变量赋值 |
| 下标访问 | `axes[0]`、`axes[1]` | 取第几个子图 |
| 关键字参数 | `figsize=(12, 4)`、`alpha=0.5`、`bins=30`、`index=False` | 按名字传参，常带默认值 |
| 字典构造 DataFrame | `pd.DataFrame({"model": [...], ...})` | 键是列名，值是列数据 |
| 方法链 | `df['accuracy'].idxmax()` | 取列后直接调用方法 |
| f-string 格式符 | `{list_time:.4f}`、`{name:>4s}`、`{size_mb:>8.2f}`、`{per_call:.1f}` | `.4f` 四位小数；`>4` 右对齐宽 4；`s` 字符串；`f` 浮点 |
| f-string 中的引号 | `f"...{df.loc[df['accuracy'].idxmax(), 'model']}"` | 外双内单，避免冲突 |
| 字符串中的 `\n` | `"\n=== Inline Plotting ===\n"` | 换行，制造空行 |
| `_` 占位变量 | `for _ in range(iterations):` | 不需要的循环变量 |
| 科学计数法 | `1e6` | `1000000.0` |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行，被导入时不执行 |

---

## 6. 运行结果解读

在临时副本中实际运行（numpy 2.5.3、matplotlib 3.11.2、pandas 3.0.5，Python 3.13）：

```text
Notebook Tips - Key Patterns

Run these in a Jupyter notebook to see rich output.

=== Timing: List vs NumPy ===

List comprehension: 0.2101s
NumPy:              0.0779s
Speedup:            2.7x
```

- 这次 NumPy 只快了 2.7 倍，看起来不太对劲。再连续跑 3 次，加速比分别是 3.7x、10.2x、3.5x。原因是**单次计时**受首次内存分配、系统调度等噪声影响很大；用 `timeit` 多轮重复取最好值，稳定在约 44–49 倍。这一行输出本身就是"为什么需要 `%timeit`"的最佳教材。你机器上的具体数字会不同。

```text
=== Inline Plotting ===

Saved plot to notebook_plot.png
In a notebook, plt.show() displays this inline.
```

- 当前目录多了一个 `notebook_plot.png`（1200×400 像素）：左边是蓝色平滑正弦曲线与半透明橙色带噪曲线，右边是噪声的直方图，大致呈以 0 为中心的钟形，范围约 ±0.5。

```text
=== DataFrame Display ===

In a notebook, just typing 'df' renders a rich HTML table:

            model  accuracy  train_time_sec  parameters
Linear Regression      0.72             0.1         102
    Random Forest      0.89             2.3       50000
   Neural Network      0.94            45.6     1200000
          XGBoost      0.91             8.2       25000

Best model: Neural Network
Fastest model: Linear Regression
```

- `index=False` 去掉了行号；文本表格按列右对齐。注意 `50_000` 打印成 `50000`——下划线只存在于源码里。
- 准确率最高 0.94 → Neural Network；训练最快 0.1 秒 → Linear Regression。

```text
=== Memory Usage ===

Array   1K elements:     0.01 MB
Array 100K elements:     0.80 MB
Array  10M elements:    80.00 MB

Python process memory: ~80.0 MB for the large array
In notebooks, memory accumulates across cells. Restart the kernel to free it.
```

- 数字正好是"元素数 × 8 字节"。`~80.0 MB` 实际是这个数组对象的大小，不是整个进程的内存（见 3.5）。

```text
=== Magic Command Equivalents ===

In a notebook, you would use magic commands:
  %timeit np.random.randn(10000)    -> micro-benchmark
  %%time long_operation()            -> wall clock time
  %matplotlib inline                 -> show plots in cells
  !pip install package               -> install from notebook
  %env VAR                           -> check env variable

Manual timing (like %%timeit): np.random.randn(10000)
  150.2 us per call (1000 iterations)
```

- 生成 10,000 个正态随机数每次约 150 微秒（多次运行在 149–152 µs 之间，比 3.2 节的单次计时稳定得多，因为这里平均了 1000 次）。讲义中 `%timeit` 示例给出的是 `45.2 us`，不同机器差异很正常。

---

## 7. 动手改一改

1. **搬进 notebook**：把 5 个函数分别粘贴到 5 个 cell，删掉 `matplotlib.use("Agg")`，在绘图 cell 末尾改用 `plt.show()`，在表格 cell 末尾直接写 `df`，对比显示效果。
2. **用真正的 magic**：在 notebook 中用 `%timeit [x ** 2 for x in range(1_000_000)]` 和 `%timeit np.arange(1_000_000) ** 2` 替代 `timing_comparison`，看加速比是否稳定。
3. **制造"隐藏状态"**：在 notebook 中先运行 `lr = 0.01`，在下一个 cell 使用 `lr`，然后删除第一个 cell，再 Restart & Run All，观察 `NameError`。
4. **观察内存累积**：在 notebook 中多次运行创建 `large` 的 cell，用 `%who` 查看变量，用 `del large` + `gc.collect()` 释放；再试试先创建 `v = large[::2]` 再 `del large`，思考内存为什么没被释放。
5. **修正内存标签**：把最后一行改为打印 `large.nbytes`，并用 `psutil.Process().memory_info().rss`（需要安装 psutil）打印真实的进程内存，对比两者。
6. **加命令行参数**：用 `argparse` 加 `--size` 和 `--out` 参数，分别控制计时规模和图片输出路径。

---

## 8. 常见坑

- **单次计时下结论**：本脚本的加速比在 2.7x～10x 之间跳动；微基准一定要多次重复（`%timeit` / `timeit`）。
- **在 notebook 里保留 `matplotlib.use("Agg")`**：图不会内联显示；notebook 用 `%matplotlib inline`。
- **`print(df)` 期待漂亮表格**：只有 cell 最后一个表达式（或 `display(df)`）才会渲染 HTML 表格。
- **把 `sys.getsizeof` 当成内存统计工具**：对 NumPy 数组用 `nbytes`，对进程用操作系统指标；视图的 `getsizeof` 只有对象头。
- **在源码目录直接运行**：会在当前目录生成 `notebook_plot.png`，不想要的话在其他目录运行或修改输出路径。
- **`%%time` 后面直接跟代码**：单元格魔法应独占 cell 第一行，单行计时用 `%time`。
