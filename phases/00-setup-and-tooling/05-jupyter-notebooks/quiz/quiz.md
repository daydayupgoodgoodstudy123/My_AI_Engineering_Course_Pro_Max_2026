# 测验 · Jupyter 笔记本（Jupyter Notebooks）

> **阶段 00 · 环境搭建与工具 · 第 05 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/notebook_tips.py](../code/notebook_tips.py) ｜ 代码讲解：[code/notebook_tips.讲解.md](../code/notebook_tips.讲解.md)
>
> **用法**：学完讲义、在 JupyterLab（或 VS Code / Colab）里亲手建过一个 notebook、并在终端跑过 `notebook_tips.py` 后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Notebook 的结构 | 一串 cell（单元格），每个 cell 是 code 或 markdown；`.ipynb` 本质是一个包含 cells、outputs、metadata 的 **JSON 文件** |
| 2 | Kernel（内核） | 后台独立运行的 Python 进程；所有 cell 共享同一个 kernel，变量在 cell 之间持续存在，重启即全部清空 |
| 3 | 执行顺序由你点击决定 | kernel 按你点击的顺序执行 cell，而不是页面上的顺序——既是超能力，也是"脚枪" |
| 4 | 三种界面一种格式 | JupyterLab、Jupyter Notebook、VS Code 的 Jupyter 扩展读写同一个 `.ipynb` |
| 5 | 两种模式与快捷键 | `Esc` 命令模式、`Enter` 编辑模式；`Shift+Enter` 运行并下移，`A`/`B` 插入，`DD` 删除，`M`/`Y` 切换类型 |
| 6 | Magic 命令 | `%` 行魔法、`%%` 单元格魔法；`%timeit` 多次运行取统计、`%%time` 只跑一次；`%matplotlib inline`、`!` 执行 shell、`%env` |
| 7 | 富文本输出 | cell 的**最后一个表达式**自动渲染：`df` 是 HTML 表格，`print(df)` 只是文本；图片用 `display(Image(...))` |
| 8 | Colab 的差异 | 免费 GPU、预装常用库；文件不跨会话保留（挂载 Google Drive 持久化）；免费版闲置约 90 分钟断开 |
| 9 | 用 notebook 探索，用脚本交付 | 探索/原型/可视化用 notebook；训练流水线、可复用工具、定时任务、生产代码用 `.py` |
| 10 | 三大陷阱 | 乱序执行、隐藏状态、内存累积；对策：分享前 Restart & Run All、定期重启、`del` + `gc.collect()` |

### 核心技能（能动手做到）

- [ ] 安装并启动 JupyterLab，新建 notebook，只用键盘完成：插入 cell、切换 markdown、运行、删除
- [ ] 用 `%timeit` 比较列表推导与 NumPy 生成 100,000 个随机数的速度，读懂 `mean ± std per loop` 的含义
- [ ] 写一个"读 CSV → 显示 DataFrame → 画图"的 notebook，然后 Kernel > Restart & Run All 验证能从上到下跑通
- [ ] 在终端运行 `python notebook_tips.py`，解释为什么它要 `matplotlib.use("Agg")` 并把图保存成 `notebook_plot.png`
- [ ] 用 `%who` 查看内存中的变量，用 `del` + `gc.collect()` 或重启 kernel 释放大对象
- [ ] 把 notebook 中验证好的函数移到 `.py` 文件，再在 notebook 里 `import` 回来继续实验
- [ ] 在 Colab 上切换到 T4 GPU、挂载 Google Drive，并把结果保存到 Drive

---

## 二、基础自测（选择题）

**Q1.** `%timeit` 与 `%%time` 的区别是：

- A. 两者是同一个命令的别名
- B. `%timeit` 多次运行取统计结果，适合微基准；`%%time` 只运行一次，适合训练这类长任务
- C. `%timeit` 测 CPU 时间，`%%time` 测 GPU 时间
- D. `%timeit` 作用于整个 notebook，`%%time` 只作用于一行

**Q2.** 关于 Jupyter kernel，正确的说法是：

- A. 每个 cell 都有自己独立的 Python 进程
- B. kernel 是后台独立的 Python 进程，所有 cell 共享它，变量在 cell 之间保留
- C. kernel 负责把 markdown 渲染成 HTML
- D. kernel 关闭后变量会自动保存到 `.ipynb` 里，下次打开还在

**Q3.** 你的 notebook 在自己电脑上运行正常，同事从上到下运行却报 `NameError`。最可能的原因是：

- A. 同事没有执行 `%matplotlib inline`
- B. markdown cell 太多
- C. 你曾乱序执行 cell，或删掉了定义变量的 cell，notebook 依赖了"幽灵状态"
- D. `.ipynb` 文件在传输中损坏

**Q4.** 在一个 cell 中写下面代码，会得到格式化的 HTML 表格的是：

```python
# 写法 1
print(df)
# 写法 2
df
# 写法 3
df
x = 1
```

- A. 只有写法 1
- B. 只有写法 2
- C. 写法 2 和写法 3
- D. 三种都会

**Q5.** `.ipynb` 文件的本质是：

- A. 编译后的 Python 字节码
- B. 一个 JSON 文件，包含 cells、输出和元数据
- C. 一个压缩包
- D. 纯 Python 源码，只是扩展名不同

**Q6.** 在 notebook 里执行 `!pip install scikit-learn` 后，`import sklearn` 仍然报 `ModuleNotFoundError`。最可能的原因是：

- A. scikit-learn 不支持 notebook
- B. 包被装进了另一个 Python 环境，而不是 kernel 正在使用的那个
- C. 需要先执行 `%matplotlib inline`
- D. notebook 不允许安装包

**Q7.** 在免费版 Colab 上训练了一个模型并把权重存到 `/content/model.pt`，第二天打开发现文件没了。原因和正确做法是：

- A. Colab 有 bug，应该改用本地 GPU
- B. Colab 的文件系统不跨会话保留，应该保存到挂载的 Google Drive 或下载到本地
- C. `.pt` 文件会被 Colab 自动删除，应该改成 `.pth`
- D. 需要先执行 `%env` 保存环境

---

## 三、动手 / 代码题

**Q8.**（预测输出）下面是 `notebook_tips.py` 中的 `memory_check()`。写出它打印的前三行，并回答：(a) 为什么 10M 个元素正好是 80 MB？(b) 最后一行 `Python process memory: ~80.0 MB` 的标签有什么误导性？(c) 如果把 `sys.getsizeof(large)` 换成 `sys.getsizeof(large[::2])`，大约会打印多少？为什么？

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
```

**Q9.**（改进代码）`timing_comparison()` 只对列表推导和 NumPy 各计时一次。在同一台机器上连续运行脚本 4 次，得到的 `Speedup` 分别是 2.7x、3.7x、10.2x、3.5x。

```python
    start = time.perf_counter()
    python_list = [x ** 2 for x in range(size)]
    list_time = time.perf_counter() - start
    # ...
    start = time.perf_counter()
    numpy_array = np.arange(size) ** 2
    numpy_time = time.perf_counter() - start
```

(a) 为什么结果波动这么大？(b) 用标准库 `timeit` 模块模仿 `%timeit` 的做法重写，让结果稳定。

**Q10.**（解释 + 重构）回答关于 `notebook_tips.py` 的两个问题：
(a) 文件开头为什么要写 `matplotlib.use("Agg")`，而且放在 `import matplotlib.pyplot as plt` 之前？在 notebook 里需要这样写吗？
(b) 按"用 notebook 探索，用脚本交付"的原则，把 `dataframe_display()` 里"找最佳/最快模型"的逻辑重构为一个**不打印、可测试**的函数 `summarize(df) -> dict`，放进 `model_utils.py`，并写出 notebook 中使用它的 cell。

---

## 四、面试高频题

**Q11.**（基础必考）Notebook 和 `.py` 脚本各自适合什么场景？你在 AI 项目里的典型工作流是怎样的？

**Q12.**（原理深挖）解释 Jupyter 的前端—kernel 架构。为什么 notebook 会出现"乱序执行""隐藏状态"这类问题？重启 kernel 到底做了什么？

**Q13.**（工程实践）团队用 Git 协作时，notebook 会带来哪些问题？你会采取哪些措施？

**Q14.**（场景设计）同事说："我在 notebook 里反复加载数据、训练模型，跑着跑着 kernel 就挂了，也没有报错信息。"请给出你的排查思路。

**Q15.**（追问型）`%timeit np.random.randn(10000)` 输出 `45.2 µs ± 1.3 µs per loop (mean ± std. dev. of 7 runs, 10,000 loops each)`。这些数字分别是什么意思？为什么不能用 `%timeit` 给一次完整的模型训练计时？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义原话：`%timeit` 运行很多次并取平均，`%%time` 只运行一次；`%timeit` 用于微基准，`%%time` 用于训练。D 把两者的作用范围说反且说错了：单个 `%` 是**行魔法**（作用于这一行），`%%` 是**单元格魔法**（作用于整个 cell）。C 是编造的。

### Q2 — 答案：B

讲义：kernel 是在后台运行的独立 Python 进程，执行 cell 并把变量保存在内存中，所有 cell 共享同一个 kernel。D 错：`.ipynb` 只保存代码和**输出**，不保存变量；kernel 一重启，内存中的变量全部消失。C 是前端的工作。

### Q3 — 答案：C

这是讲义列出的头号陷阱"乱序执行"及"隐藏状态"：变量存在只是因为你曾经运行过某个 cell（可能已被删除或在下方）。对策：分享前执行 Kernel > Restart & Run All，确认 notebook 能从上到下线性跑通。

### Q4 — 答案：B

只有**最后一个表达式**会被自动渲染为富文本输出。写法 1 是 `print`，输出纯文本；写法 3 中 `df` 不是最后一行，最后一行是赋值语句（不产生输出），所以什么都不显示。想在 cell 中间显示，可以用 `display(df)`。配套诊断提示词也写到：`print(df)` 得到文本，单独的 `df` 得到富表格。

### Q5 — 答案：B

讲义 Key Terms：`.ipynb` 是包含 cells、outputs 和 metadata 的 JSON 文件，名字来源于 IPython Notebook。正因为是 JSON 且包含输出（甚至 base64 编码的图片），它在 Git 中的 diff 往往很难读（见 Q13）。

### Q6 — 答案：B

配套诊断提示词："Import errors after pip install：包被装进了与 kernel 不同的 Python。"`!` 只是执行一条 shell 命令，`pip` 解析到哪个 Python 取决于 PATH，不一定是 kernel 的解释器。排查：`import sys; sys.executable` 与 `!which python` 是否一致。更稳妥的做法是用 IPython 的 `%pip install scikit-learn`，它会安装到当前 kernel 所在的环境。

### Q7 — 答案：B

讲义列出的 Colab 差异：文件不跨会话保留，需要保存到 Drive 或下载；用 `from google.colab import drive; drive.mount('/content/drive')` 挂载 Drive 做持久化存储。

### Q8 — 参考答案

前三行（实测）：

```text
Array   1K elements:     0.01 MB
Array 100K elements:     0.80 MB
Array  10M elements:    80.00 MB
```

`{name:>4s}` 把名字右对齐到 4 个字符宽（`"1K"` 前补两个空格），`{size_mb:>8.2f}` 右对齐到 8 位宽、保留两位小数，所以三行的数字是对齐的。

(a) `np.random.randn` 默认生成 `float64`，每个元素 8 字节：`10,000,000 × 8 = 80,000,000` 字节，除以 `1e6` 得 80.00 MB。`arr.nbytes` 就是"元素个数 × 每元素字节数"。

(b) `sys.getsizeof(large)` 返回的是**这一个数组对象**占用的字节数（实测 `80,000,112`：80 MB 数据 + 112 字节的对象头），而不是"Python 进程的内存"。进程实际内存（RSS）还包括解释器本身、已导入的 numpy/pandas/matplotlib、前面创建的其他数组等，要看操作系统层面的指标（如 `psutil.Process().memory_info().rss`）。

(c) 大约 `0.0 MB`（实测 112 字节）。`large[::2]` 是一个**视图（view）**，与原数组共享数据缓冲区，自己不拥有数据，所以 `getsizeof` 只算对象头。这说明 `sys.getsizeof` 不适合用来统计 NumPy 数组的内存，应该用 `nbytes`；同时也提醒你：只要视图还被引用，原数组的 80 MB 就无法释放。

### Q9 — 参考答案

(a) 波动的原因：
- **只测一次**：受操作系统调度、CPU 频率、其他进程干扰的影响很大。
- **首次调用开销**：NumPy 第一次为一块新的大数组申请内存时会产生缺页等一次性开销；在测试中，同一进程里连续三次计时 `np.arange(size) ** 2`，第一次常常明显慢于后两次。
- 列表推导本身耗时几十毫秒，而 NumPy 只有几毫秒，分母很小，一点噪声就会让比值剧烈变化。

(b) 用 `timeit.repeat` 模仿 `%timeit`（多次循环、多轮重复，取最好值）：

```python
import timeit

import numpy as np


def bench(stmt, number, repeat=7):
    times = timeit.repeat(stmt, number=number, repeat=repeat, globals=globals())
    per_loop = [t / number for t in times]
    return min(per_loop), sum(per_loop) / len(per_loop)


size = 1_000_000
list_best, list_mean = bench("[x ** 2 for x in range(size)]", number=5)
np_best, np_mean = bench("np.arange(size) ** 2", number=50)

print(f"List : best {list_best * 1e3:.2f} ms, mean {list_mean * 1e3:.2f} ms")
print(f"NumPy: best {np_best * 1e3:.2f} ms, mean {np_mean * 1e3:.2f} ms")
print(f"Speedup (best vs best): {list_best / np_best:.1f}x")
```

在同一台机器上连续运行两次，加速比分别为 48.8x 和 44.0x——不仅稳定，而且远高于单次测量得到的 3–10x，说明原来的单次计时严重低估了 NumPy 的优势。

要点：`globals=globals()` 让被测语句能访问 `np` 和 `size`；`number` 是每轮执行次数，`repeat` 是轮数；取**最小值**是因为噪声只会让时间变长、不会变短，最小值最接近"真实成本"（`%timeit` 报告的则是均值 ± 标准差）。

### Q10 — 参考答案

(a) `matplotlib.use("Agg")` 选择 **Agg 非交互式后端**：只在内存里渲染图像、写入 PNG 文件，不需要图形界面。这个脚本是在终端里运行的演示，目标是 `plt.savefig("notebook_plot.png")`，用 Agg 可以保证在没有显示器的服务器、CI、SSH 环境下也能稳定运行，不会尝试弹出窗口。放在导入 `pyplot` 之前是惯用且最稳妥的写法，确保 pyplot 一开始就使用这个后端。
在 notebook 里**不需要**这样写：notebook 有自己的内联后端，讲义中用 `%matplotlib inline` 让图直接显示在 cell 下方；若强制设为 Agg，`plt.show()` 就不会显示图了。

(b)

```python
# model_utils.py
import pandas as pd


def summarize(df: pd.DataFrame) -> dict:
    """返回准确率最高与训练最快的模型名。"""
    return {
        "best": df.loc[df["accuracy"].idxmax(), "model"],
        "fastest": df.loc[df["train_time_sec"].idxmin(), "model"],
    }
```

notebook 中：

```python
import pandas as pd
from model_utils import summarize

df = pd.DataFrame({
    "model": ["Linear Regression", "Random Forest", "Neural Network", "XGBoost"],
    "accuracy": [0.72, 0.89, 0.94, 0.91],
    "train_time_sec": [0.1, 2.3, 45.6, 8.2],
})
summarize(df)
```

最后一行是表达式，notebook 会直接显示 `{'best': 'Neural Network', 'fastest': 'Linear Regression'}`。

要点：函数只负责**计算并返回**，打印/展示交给调用方，这样既能在 notebook 里交互使用，也能写单元测试；这正是讲义工作流的第 3、4 步——验证好的代码移到 `.py`，再 import 回 notebook 继续实验。加分：在 notebook 开头用 `%load_ext autoreload` 和 `%autoreload 2`，修改 `model_utils.py` 后无需重启 kernel 就能生效。

### Q11 — 参考回答要点

- **Notebook 适合**：探索数据、模型原型、可视化结果、讲解/汇报、快速实验、课程练习——核心价值是"代码 + 输出 + 说明"放在一起、快速迭代。
- **脚本适合**：训练流水线、可复用工具函数、带 `if __name__` 入口的程序、定时任务、生产代码、包和库——核心需求是可复现、可测试、可审查、可自动化。
- **典型工作流**（讲义四步）：notebook 中探索数据 → notebook 中做原型 → 跑通后把代码移到 `.py` → 把 `.py` import 回 notebook 做进一步实验。口诀：**explore in notebooks, ship in scripts**。
- **加分点**：提到 notebook 中的关键结论要能用脚本复现；用参数化执行 notebook 的工具（如 papermill）只是折中方案，长期仍应沉淀为模块。
- **常见误区**：把几百个 cell 的 notebook 直接当生产训练脚本，用定时任务去跑。

### Q12 — 参考回答要点

- **架构**：Notebook UI（浏览器或编辑器中的前端）负责编辑和展示；kernel 是**独立的 Python 进程**，接收前端发来的代码、执行、把结果（文本、HTML、图片）发回前端渲染。（加分：两者通过 Jupyter 消息协议通信，底层用 ZeroMQ。）
- **为什么会乱序/隐藏状态**：kernel 只是一个长期存活的解释器，它不知道页面上 cell 的排列顺序，只按"收到代码的顺序"执行；全局命名空间在所有 cell 间共享。于是：先运行下面的 cell、修改后不重跑上游 cell、删除 cell 但变量还在内存里，都会让"页面上的代码"与"内存中的状态"不一致。cell 左侧的 `[n]` 执行计数就是线索——数字不是自上而下递增，就说明乱序过。
- **重启 kernel**：结束旧的 Python 进程、启动一个全新的进程，所有变量、导入的模块、占用的内存（包括 GPU 显存）都被释放；notebook 中保存的输出不受影响（所以输出可能"骗人"）。
- **常见误区**：以为删除 cell 就删除了它创建的变量。

### Q13 — 参考回答要点

- **问题**：
  - `.ipynb` 是 JSON，包含输出、执行计数、base64 图片——diff 难读、合并冲突难解决、仓库膨胀；
  - 输出中可能意外包含敏感信息（打印出的密钥、内部数据样本）；
  - 乱序执行导致"提交的 notebook 无法复现"。
- **措施**：
  - 提交前清空输出或用工具自动清理（如 nbstripout 这类 Git 过滤器）；
  - 用 jupytext 等工具把 notebook 与 `.py`/`.md` 配对，在 Git 里审查纯文本版本；
  - 分享/提交前强制 Restart & Run All；在 CI 中用 `jupyter nbconvert --execute` 之类的方式确保能从头跑通；
  - 把稳定的逻辑移到 `.py` 模块并写测试，notebook 只保留薄薄一层调用和展示；
  - `.gitignore` 中忽略 `.ipynb_checkpoints/`（第 02 节）。
- **加分点**：提到 VS Code 和 JupyterLab 都有面向 notebook 的 diff 工具（如 nbdime）。

### Q14 — 参考回答要点

1. **找真实报错**：配套诊断提示词指出，kernel 静默崩溃时，真正的错误信息往往在**启动 Jupyter 的那个终端**里，notebook 界面会把它藏起来。
2. **判断是否内存耗尽**：用 `%who` 查看内存中有哪些变量，对 DataFrame 用 `df.info()`、对张量看 `shape` 和 `dtype` 估算大小；同时观察系统内存监控。
3. **释放内存**：`del` 不需要的大变量后 `gc.collect()`；注意视图、列表、闭包里残留的引用会让对象无法回收；最彻底的是重启 kernel。
4. **减少峰值内存**：分块读取（`pd.read_csv(path, chunksize=...)` 返回迭代器）、使用生成器、减小 batch、使用更紧凑的 dtype。
5. **原生库段错误**：如果是 numpy/torch 与系统库版本不匹配导致的崩溃，新建干净的虚拟环境重装（第 06 节）。
6. **根本改进**：把"加载数据 + 训练"挪到脚本里运行，notebook 只做分析。
- **加分点**：GPU 训练时也会累积显存，`torch.cuda.empty_cache()` 无法释放仍被引用的张量。

### Q15 — 参考回答要点

- **含义**：`%timeit` 自动决定每轮循环次数（这里 10,000 次），一共重复 7 轮；每轮总时间除以循环次数得到"每次耗时"，再对 7 轮求**均值 ± 标准差**——每次调用平均 45.2 微秒，轮与轮之间的波动约 1.3 微秒。
- **为什么要多次**：单次执行太短，计时器精度、调度抖动、缓存状态都会严重干扰；多次循环把噪声摊薄，多轮重复给出波动范围（Q9 中单次测量的加速比在 2.7x～10x 之间跳动就是反例）。
- **为什么不能给训练计时**：训练一次就要几分钟到几小时，`%timeit` 会运行很多次，时间成倍增加；而且训练有副作用（会修改模型参数），重复运行会改变被测对象本身。长任务应该用 `%%time` 只跑一次看墙钟时间，或在代码中记录每个 epoch 的耗时。
- **加分点**：GPU 代码的计时还要考虑异步执行（第 03 节的 `torch.cuda.synchronize()`）。

---

## 六、关联知识点

### 前置知识
- [阶段 00 · 01 开发环境](../../01-dev-environment/docs/zh.md)：用 uv 安装 jupyter、numpy、matplotlib；理解"包装进了哪个 Python"。
- [阶段 00 · 03 GPU 设置和云](../../03-gpu-setup-and-cloud/docs/zh.md)：Colab 免费 T4 GPU 的开启与验证。

### 本节被哪些后续内容用到
- [阶段 00 · 06 Python 环境](../../06-python-environments/docs/zh.md)：kernel 用的是哪个环境、为什么装了包却 import 不到。
- [阶段 00 · 08 编辑器设置](../../08-editor-setup/docs/zh.md)：在 VS Code 中通过 Jupyter 扩展运行 notebook。
- [阶段 00 · 09 数据管理](../../09-data-management/docs/zh.md)：分块读取大数据集，避免 notebook 内存爆炸。
- [阶段 00 · 12 调试与性能分析](../../12-debugging-and-profiling/docs/zh.md)：比 `%timeit` 更系统的性能分析方法。
- [阶段 01 · 01 线性代数直觉](../../../01-math-foundations/01-linear-algebra-intuition/docs/zh.md)：数学基础阶段大量适合在 notebook 中边算边画的练习。
- [阶段 03 · 11 PyTorch 入门](../../../03-deep-learning-core/11-intro-to-pytorch/docs/zh.md)：在 notebook 中原型化模型，再沉淀为训练脚本。

### 延伸关键词
`IPython` · `ipykernel` · `%pip / %who / %autoreload` · `timeit 模块` · `nbstripout / jupytext / nbdime` · `papermill` · `NumPy 视图 vs 拷贝` · `Matplotlib 后端（Agg / inline）`
