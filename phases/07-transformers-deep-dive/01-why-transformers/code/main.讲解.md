# 代码讲解 · main.py

> **所属小节**：阶段 07 · Transformers 深入 · 第 01 节 为什么选择 Transformers — RNNs 的问题 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`time`），不需要 NumPy / PyTorch

---

## 1. 这份代码在考察什么

这一节没有神经网络，代码只用几十行标准库，把"RNN 为什么输给 Transformer"这个问题拆成可以数、可以测的东西：

1. **依赖结构决定可并行性**：`rnn_style` 每一步都要用上一步的 `h`，`attention_style` 的每个元素互不依赖。数学上都是"把一串数合成一个数"，但依赖图完全不同。
2. **串行深度（serial depth）的概念**：`depth()` 只做计数，用 `N` 对 `⌈log₂N⌉` 告诉你：在并行硬件上，决定耗时的是"最长依赖链"，而不是"总共做了多少次加法"。
3. **并行前缀和（Hillis-Steele scan）**：`serial_scan` 和 `parallel_scan` 结果相同，但后者的依赖图深度只有 `log₂N`——这是 GPU 上做扫描、也是 Mamba 等 SSM 并行训练的基础思想。
4. **测量的陷阱**：纯 Python 计时表里 `attention_style` 更快，但原因是 C 实现的 `sum()`，不是并行。读懂这一点，才不会被"漂亮的 benchmark"误导。

> 一句话：**用最少的代码，让你从"运算量"的思维切换到"依赖深度"的思维**——这是理解 Transformer、Flash Attention、并行扫描乃至 speculative decoding 的共同底层视角。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `rnn_style(xs, decay=0.9)` | 函数 | 逐个元素做 `h = decay*h + x` | RNN 的递归 `h_t = f(h_{t-1}, x_t)` |
| `attention_style(xs)` | 函数 | 直接求平均 `sum(xs)/len(xs)` | 均匀权重的 attention（每个 `a_ij = 1/N`） |
| `serial_scan(xs)` | 函数 | 串行前缀和，深度 O(N) | 串行依赖链 |
| `parallel_scan(xs)` | 函数 | Hillis-Steele 前缀和，深度 O(log N) | 并行扫描 / 用工作量换深度 |
| `benchmark(n, reps=3)` | 函数 | 对两种风格各计时 3 次，取最小值 | 微基准测试方法 |
| `depth(n)` | 函数 | 返回 `(n, ⌈log₂n⌉)` | 串行深度的理论值 |
| `main()` | 函数 | 打印三张表：深度对比、纯 Python 计时、扫描一致性 | 演示入口 |

数据流：`main()` → 先调用 `depth()` 打印理论表 → 再循环调用 `benchmark()`（内部调用 `rnn_style` / `attention_style`）打印实测表 → 最后用 `serial_scan` 与 `parallel_scan` 做一致性检查。

---

## 3. 逐段精讲

### 3.1 `rnn_style`：一条无法跳过的依赖链

```python
def rnn_style(xs, decay=0.9):
    """Sequential recurrence: h_t depends on h_{t-1}. Cannot parallelize."""
    h = 0.0
    for x in xs:
        h = decay * h + x
    return h
```

- 这是 RNN 递归 `h_t = f(h_{t-1}, x_t)` 的最小化版本：隐状态是一个标量，"网络"只有一个固定系数 `decay`。
- `decay = 0.9` 让旧信息每过一步就打九折——第 50 步之前的输入只剩 `0.9⁵⁰ ≈ 0.005` 的权重，这恰好是讲义里"50 个 token 之前的信息被压得所剩无几"的数值直觉（梯度消失也是同样的连乘衰减）。
- 依赖关系：每次循环都读上一轮写入的 `h`，所以 N 个元素就是 N 个串行步。
- ⚠️ **刻意的简化，也是一个值得深究的点**：这里的递归是**线性**的（仿射变换 `h ↦ 0.9h + x`），它其实有闭式解 `h_N = Σ 0.9^(N-1-t)·x_t`，也可以用并行扫描计算（两个仿射变换的复合仍是仿射变换，满足结合律）。真正"无法并行"的是带非线性的经典 RNN，例如 `h = tanh(W·h + U·x)`。所以 docstring 的 "Cannot parallelize" 要理解为"代表经典 RNN 的计算模式"，而不是这段代码本身的数学性质。这一点恰恰是 Mamba 等 SSM 的核心洞察：把递归设计成线性的，就能并行训练。

### 3.2 `attention_style`：每个元素都是独立的

```python
def attention_style(xs):
    """Order-independent reduction: every element is independent."""
    return sum(xs) / len(xs)
```

- 求平均相当于一个**所有权重都等于 `1/N` 的 attention**：`output = Σ_j (1/N)·x_j`。真正的 attention 权重来自 `softmax(q·k)`，但"加权求和、每项互不依赖"这个结构是一样的。
- "Order-independent"：交换 `xs` 中任意两个元素，结果不变。这对 attention 也成立——attention 本身不知道顺序，这就是为什么第 04 节需要位置编码。
- ⚠️ `len(xs) == 0` 时会除以零，演示中不会出现。

### 3.3 串行扫描 vs Hillis-Steele 并行扫描

```python
def serial_scan(xs):
    """Prefix sum computed serially. Depth O(N)."""
    out = []
    acc = 0.0
    for x in xs:
        acc += x
        out.append(acc)
    return out


def parallel_scan(xs):
    # ...（docstring 省略）
    out = list(xs)
    step = 1
    n = len(out)
    while step < n:
        new = list(out)
        for i in range(step, n):
            new[i] = out[i] + out[i - step]
        out = new
        step *= 2
    return out
```

前缀和（prefix sum / scan）：输出第 i 项是前 i+1 个输入之和。

- `serial_scan`：一个累加器从头扫到尾，深度 N，总加法 N 次。
- `parallel_scan`：第 k 轮让每个位置加上"左边距离 `2^k` 的那个位置"。以 `[1, 2, 3, 4]` 为例：

| 轮次 | step | out |
|------|------|-----|
| 初始 | — | `[1, 2, 3, 4]` |
| 1 | 1 | `[1, 3, 5, 7]` |
| 2 | 2 | `[1, 3, 6, 10]` |

  每一轮内部的所有 `i` 互不依赖，可以同时算；轮数是 `⌈log₂N⌉`。
- **为什么要 `new = list(out)`（双缓冲）**：Hillis-Steele 每一轮在概念上是"所有位置同时更新"，所以必须读旧值、写新值。若直接 `out[i] = out[i] + out[i-step]` 原地写，`[1,2,3,4]` 会得到错误的 `[1, 3, 7, 13]`，因为同一轮里后面的位置读到了已被改过的值。
- **代价**：每轮做 `n - step` 次加法，N = 16 时总计 49 次，而串行只要 15 次。这就是"用更多工作量换更浅深度"——在 GPU 上很划算，在单核 CPU 上反而更慢。
- ⚠️ docstring 也坦白说了："In pure Python each step is still serial"——这里只是演示**依赖图的形状**，Python 的 `for i in range(step, n)` 依然是一个一个算的。

### 3.4 `benchmark`：怎么做一个靠谱的微基准

```python
def benchmark(n, reps=3):
    xs = [0.001 * (i % 17) for i in range(n)]

    best_rnn = math.inf
    for _ in range(reps):
        t0 = time.perf_counter()
        _ = rnn_style(xs)
        best_rnn = min(best_rnn, time.perf_counter() - t0)
    # ... attention_style 同理
    return best_rnn, best_attn
```

- `xs` 的值用 `0.001 * (i % 17)` 生成：数值小、有变化、且确定性（不需要随机种子），避免 `decay*h` 在长序列上溢出。
- `time.perf_counter()` 是专门用来测时间间隔的高精度单调时钟，比 `time.time()` 更适合 benchmark。
- **取 3 次中的最小值**：最小值最接近"没有被操作系统调度、缓存未命中等噪声干扰"的真实耗时，这是 `timeit` 模块的推荐做法。
- `_ = rnn_style(xs)` 用 `_` 接住结果，表示"我只关心耗时，不关心返回值"。
- `math.inf` 作为"最小值"的初始值，第一次 `min` 时一定会被替换。

### 3.5 `depth`：理论串行深度

```python
def depth(n):
    """Serial-depth count for RNN vs attention-style reductions."""
    rnn_depth = n
    attn_depth = max(1, math.ceil(math.log2(n)))
    return rnn_depth, attn_depth
```

- RNN 深度 = N：每一步都依赖上一步。
- 归约深度 = `⌈log₂N⌉`：二叉树两两相加，每一轮规模减半。
- `math.ceil`：N 不是 2 的幂时需要向上取整（1000 个数需要 10 轮）。
- `max(1, ...)`：`log2(1) = 0`，避免 `main()` 中 `rd / ad` 除以零。
- ⚠️ `depth(0)` 会因为 `math.log2(0)` 抛 `ValueError`，演示里不会传 0。
- 讲义里说 attention 是 "O(1) serial depth"，指的是"一层 attention 内部没有沿序列的依赖链"；落到硬件上，每个求和归约仍有 `log N` 深度，这正是 `depth()` 计算的东西。两种说法都对，看你数的是"层"还是"加法"。

### 3.6 `main`：三张表

```python
    for n in [64, 512, 4096, 32768, 262144]:
        rd, ad = depth(n)
        print(f"{n:>8}  {rd:>12}  {ad:>12}  {rd / ad:>15.0f}x")
```

- 第一张表：`rd / ad` 是深度比，列名写作 "speedup (ops)"，含义是"无限并行硬件上的理论加速上限"，不是实际测得的速度。
- f-string 的 `:>8` 表示右对齐、宽度 8；`:>15.0f` 表示右对齐、宽度 15、保留 0 位小数。

```python
    for n in [1_000, 10_000, 100_000, 1_000_000]:
        rnn_t, attn_t = benchmark(n)
        ratio = rnn_t / attn_t if attn_t > 0 else float("inf")
```

- `1_000_000` 中的下划线是数字分隔符，只为可读，等价于 `1000000`。
- 条件表达式 `a if cond else b` 防止 `attn_t` 为 0 时除零（极短序列在低精度时钟上可能测出 0）。
- ⚠️ 讲义正文说"sequences up to 100,000 elements"，代码实际测到 1,000,000，以代码为准。

```python
    mismatches = sum(1 for a, b in zip(ser, par) if abs(a - b) > 1e-9)
```

- 用"带条件的生成器 + `sum`"来计数，是 Python 中统计满足条件元素个数的惯用写法。
- 用容差 `1e-9` 而不是 `==` 比较浮点数；虽然这里的输入是整数值的浮点数，加法结果是精确的，但养成习惯总没错。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用标量递归代替真实 RNN | 去掉矩阵和激活函数，只保留"依赖链"这一个变量 | 线性递归其实可并行，不能完全代表 tanh-RNN；真实对比要用 PyTorch 的 `nn.LSTM` vs `nn.MultiheadAttention` |
| 用平均值代表 attention | 突出"每项独立、加权求和"的结构 | 没有 softmax、没有 QK 打分；真正的 attention 见第 02 节 |
| 只算深度、不在 GPU 上测 | 纯标准库，任何机器都能跑 | 真正的并行收益只在 GPU 上可见（讲义练习 3） |
| Hillis-Steele 而不是 Blelloch | 实现最短、深度最浅、最直观 | 工作量 O(N log N)；工作量最优的 Blelloch 扫描是 O(N) |
| 取多次计时的最小值 | 排除系统噪声 | 生产级 benchmark 用 `timeit`、预热、固定 CPU 频率、报告分布 |
| `new = list(out)` 双缓冲 | 保证"同一轮所有位置同时更新"的语义 | 每轮复制一次列表，额外 O(N) 内存 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块 docstring | 文件开头的三引号字符串 | 描述整个文件用途，可通过 `__doc__` 访问 |
| 函数默认参数 | `def rnn_style(xs, decay=0.9)`、`benchmark(n, reps=3)` | 调用时可省略，省略就用默认值 |
| 增强赋值 | `acc += x`、`step *= 2` | `acc = acc + x` 的简写 |
| `while` 循环 | `while step < n:` | 条件为真就继续；适合"不知道循环几次"的场景 |
| `range(start, stop)` | `range(step, n)` | 从 `step` 到 `n-1` |
| `list()` 复制 | `new = list(out)` | 创建新列表（浅拷贝），修改 `new` 不影响 `out` |
| 列表推导式 | `[0.001 * (i % 17) for i in range(n)]` | 一行生成列表；`%` 是取模 |
| 生成器表达式 + 条件 | `sum(1 for a, b in zip(ser, par) if abs(a - b) > 1e-9)` | 统计满足条件的元素个数 |
| `zip` 与元组解包 | `for a, b in zip(ser, par)`、`rd, ad = depth(n)` | 并行遍历两个序列；函数返回元组后一次拆开 |
| `_` 占位变量 | `for _ in range(reps)`、`_ = rnn_style(xs)` | 约定俗成表示"这个值不用" |
| `math.inf` / `float("inf")` | `best_rnn = math.inf` | 正无穷，常用作求最小值的初始值 |
| 条件表达式 | `rnn_t / attn_t if attn_t > 0 else float("inf")` | 一行版的 if-else |
| 数字分隔符 | `1_000_000` | Python 3.6+，只为可读 |
| f-string 对齐与精度 | `f"{n:>8}"`、`f"{rd / ad:>15.0f}x"`、`f"{rnn_t * 1000:>10.2f}"` | `>` 右对齐，数字是宽度，`.2f` 保留两位小数 |
| `time.perf_counter()` | `t0 = time.perf_counter()` | 高精度计时器，只用来求时间差 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

在临时目录实际运行 `python3 main.py`（Python 3.13，计时数字因机器而异）：

```text
=== serial-depth comparison ===
       N     rnn depth    attn depth     speedup (ops)
      64            64             6               11x
     512           512             9               57x
    4096          4096            12              341x
   32768         32768            15             2185x
  262144        262144            18            14564x
```

- 每一行就是 `n` 与 `⌈log₂n⌉`。64 / 6 ≈ 10.67，四舍五入成 11x；262144 = 2¹⁸，所以深度 18，比值 14564x。
- 关键观察：**N 每扩大 8 倍，RNN 深度扩大 8 倍，归约深度只加 3**。序列越长，并行的理论优势越大——这就是讲义说"the speedup is not a constant"。

```text
=== wall-clock on this machine (pure Python) ===
       N    rnn (ms)   attn (ms)     ratio
    1000        0.03        0.01      5.8x
   10000        0.22        0.05      4.6x
  100000        1.68        0.37      4.5x
 1000000       19.77        4.79      4.1x
```

- 两列都随 N **线性**增长（每扩大 10 倍，耗时约扩大 10 倍），说明两者在 CPU 上都是 O(N) 的单线程循环。
- 比值稳定在 4–6 倍，**并没有像第一张表那样随 N 增大**——这正说明这里的差距来自"C 循环 vs 解释器循环"的常数因子，而不是并行深度。作为对照，把 `attention_style` 改成纯 Python `for` 循环后，100 万元素时耗时约 18 ms，和 `rnn_style` 的约 23 ms 相差无几。

```text
=== prefix-sum equivalence check ===
length: 16, mismatches between serial and parallel scan: 0
last value (serial):   120.0
last value (parallel): 120.0
```

- 0 到 15 求和 = 15 × 16 / 2 = 120，两种扫描完全一致，证明"改变依赖图形状不改变结果"。

```text
takeaway: attention wins on every dimension but memory.
memory cost is O(N^2) for full attention; Lesson 12 covers the fixes.
```

- 结论提醒：attention 的代价在显存——N×N 分数矩阵，详见第 12 节的 Flash Attention。

---

## 7. 动手改一改

1. **讲义练习 1**：把 `rnn_style` 的标量 `h` 换成长度 64 的列表，每步对每个分量做 `h[k] = decay*h[k] + x`，重新计时。观察耗时随隐藏维度如何增长（提示：纯 Python 下大约线性增长）。
2. 写一个 `attention_style_loop`，用 `for` 循环手动累加再除以长度，加进 `benchmark`，验证"4–6 倍差距主要来自 `sum()` 的 C 实现"。
3. 把 `rnn_style` 改成非线性版本 `h = math.tanh(decay * h + x)`，然后尝试写出它的闭式解——体会为什么非线性递归无法像线性递归那样拆开。
4. 为线性递归实现 `rnn_parallel_scan`：把每步表示成 `(a, b)` 对，复合规则 `(a1, b1) ∘ (a2, b2) = (a1·a2, a2·b1 + b2)`，套进 Hillis-Steele 框架，与 `rnn_style` 的结果对比（参考测验 Q10）。
5. 在 `parallel_scan` 里加一个计数器，统计总加法次数，画出 N = 2…1024 时"串行 N−1 次"与"Hillis-Steele 次数"的对比，验证 `N·log₂N` 量级。
6. **进阶**：实现 Blelloch（up-sweep + down-sweep）扫描，验证它只需要 O(N) 次加法、O(log N) 深度。

---

## 8. 常见坑

- **把计时结果当成并行证据**：纯 Python 的 4–6 倍来自 C 实现的 `sum()`，与 GPU 并行无关；真正的深度差距要在 GPU 上才能观察到。
- **原地更新做并行扫描**：去掉 `new = list(out)` 会得到错误结果，并行算法的"同时更新"语义必须靠双缓冲或同步来保证。
- **把"深度"和"运算量"混为一谈**：Hillis-Steele 深度更浅，但加法次数更多；"更快"只在并行宽度足够时成立。
- **误以为所有递归都不能并行**：线性递归可以用结合律做并行扫描（这正是 SSM 的思路）；不能并行的是非线性递归。
- **`math.log2(0)` 报错**：`depth(0)` 会抛 `ValueError`；扩展代码时要先处理空序列。
- **只看时间、忘了内存**：attention 赢在时间（并行），输在显存（O(N²)），讲义最后一句提醒的就是这个。
