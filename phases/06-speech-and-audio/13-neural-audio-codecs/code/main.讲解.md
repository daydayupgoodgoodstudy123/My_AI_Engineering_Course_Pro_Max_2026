# 代码讲解 · main.py

> **所属小节**：阶段 06 · 语音与音频 · 第 13 节 神经音频编解码器 — EnCodec、SNAC、Mimi、DAC 和语义声学分离 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`），不需要 NumPy / PyTorch / encodec

---

## 1. 这份代码在考察什么

真实的 EnCodec、Mimi 有几千万参数，跑一次要装 PyTorch、下载权重。这份脚本把所有这些都拿掉，只保留神经 codec 里**最核心的那一个数学机制——残差量化（RVQ）**，让你用几十行纯 Python 看清楚：

1. **码本是怎么"学"出来的**：用一维 k-means 把一堆实数聚成 8 个中心，中心就是码字。
2. **残差级联**：第一级量化后剩下的误差交给第二级再量化，如此反复——这就是 "Residual" 的含义。
3. **解码就是求和**：每一级选出的码字相加，就是重建结果。
4. **码本数 ↔ 误差 ↔ 码率** 的三角关系：多一级码本，码率线性增加，误差却按数量级下降。
5. **把 toy 结果映射回真实世界**：后半段打印四大 codec 的帧率/质量对比和 Mimi 的语义/声学分工，把代码和讲义的概念连接起来。

> 一句话：**RVQ 就是"先粗后细、层层修补残差"的 k-means 级联**——看懂这份代码，就看懂了所有现代音频 codec 的离散化瓶颈。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `generate_signal(n, seed)` | 函数 | 生成 "正弦 + 高斯噪声" 的一维玩具信号 | 编码器输出（这里用原始样本代替） |
| `learn_codebook(values, size, iterations, seed)` | 函数 | 一维 k-means，返回排好序的 `size` 个中心 | 码本训练 |
| `quantize_with_codebook(values, codebook)` | 函数 | 每个值找最近码字，返回索引和残差 | 最近邻量化 |
| `rvq_encode(values, codebook_size, n_codebooks)` | 函数 | 逐级学码本 + 量化残差，返回所有索引和码本 | RVQ 编码 |
| `rvq_decode(all_indices, codebooks, length)` | 函数 | 把各级码字逐元素相加 | RVQ 解码 |
| `mse(a, b)` | 函数 | 均方误差 | 重建质量 |
| `main()` | 演示入口 | Step 1 生成信号；Step 2 扫描码本数；Step 3/4 打印 codec 对比与语义/声学分工 | — |

数据流：`generate_signal → rvq_encode（内部循环调用 learn_codebook + quantize_with_codebook）→ rvq_decode → mse`。Step 3、Step 4 只是打印硬编码的表格和说明文字，不做计算。

---

## 3. 逐段精讲

### 3.1 玩具信号：正弦 + 噪声

```python
def generate_signal(n=1000, seed=0):
    rng = random.Random(seed)
    return [math.sin(2 * math.pi * i / 100) + 0.3 * rng.gauss(0, 1.0) for i in range(n)]
```

- 周期为 100 个样本的正弦波，叠加标准差 0.3 的高斯噪声，取值大致在 [-1.7, 1.9]。
- `random.Random(seed)` 创建一个**独立的随机数生成器实例**，而不是用全局 `random.seed()`。好处是：不会影响程序里其他地方的随机状态，每个函数的随机性彼此隔离、可复现。
- ⚠️ 简化：真实 codec 量化的是**编码器输出的向量**（比如每帧 128 维），这里直接量化一维原始样本，所以严格说是"残差**标量**量化"。讲义 Exercises 第 1 题也称之为 "toy scalar + residual quantizer"。思想完全相同，只是把"向量最近邻"退化成了"数轴上找最近点"。

### 3.2 学码本：一维 k-means

```python
def learn_codebook(values, size, iterations=20, seed=0):
    rng = random.Random(seed)
    if not values:
        return [0.0] * size
    lo, hi = min(values), max(values)
    centroids = [lo + (hi - lo) * rng.random() for _ in range(size)]
    for _ in range(iterations):
        buckets = [[] for _ in range(size)]
        for v in values:
            idx = min(range(size), key=lambda i: abs(centroids[i] - v))
            buckets[idx].append(v)
        for i in range(size):
            if buckets[i]:
                centroids[i] = sum(buckets[i]) / len(buckets[i])
    return sorted(centroids)
```

这是标准的 Lloyd 算法（k-means）：

| 步骤 | 代码 | 含义 |
|------|------|------|
| 初始化 | `lo + (hi - lo) * rng.random()` | 在数据范围内均匀随机撒 `size` 个中心 |
| 分配（E 步） | `min(range(size), key=lambda i: abs(...))` | 每个值归入最近的中心 |
| 更新（M 步） | `sum(buckets[i]) / len(buckets[i])` | 中心移到所属值的均值处 |
| 重复 | `for _ in range(iterations)` | 固定迭代 20 次，不检查收敛 |

设计要点：

- `buckets = [[] for _ in range(size)]` 必须用推导式创建**互相独立**的空列表。如果写成 `[[]] * size`，8 个元素会指向**同一个**列表对象，往一个桶里加值等于往所有桶里加——这是 Python 新手的经典坑。
- `if buckets[i]:` 跳过空桶：没有任何值被分配到的中心保持原位（否则会除以 0）。⚠️ 这其实就是真实 VQ 训练里的**"死码字 / 码本坍塌（dead codes）"**问题的缩影——那些码字永远不被使用，白白浪费比特。生产中会把死码字重新初始化到随机样本上，DAC 则用 L2 归一化码本等手段提升码本利用率。
- `return sorted(centroids)`：排序后索引有了"大小顺序"（索引 0 是最小值），方便人读，对量化结果没有影响。
- ⚠️ 复杂度：每轮要做 `len(values) × size` 次距离计算，总共 `O(iterations · N · K)`。一维情况下其实可以排序后二分查找，但为了与"向量最近邻"的通用写法保持一致，这里用了暴力搜索。

### 3.3 最近邻量化：输出"索引 + 残差"

```python
def quantize_with_codebook(values, codebook):
    indices = []
    residuals = []
    for v in values:
        idx = min(range(len(codebook)), key=lambda i: abs(codebook[i] - v))
        indices.append(idx)
        residuals.append(v - codebook[idx])
    return indices, residuals
```

- **索引 `idx`** 就是要传输/交给语言模型的离散 token；码本大小为 8 时，每个索引只需 3 bit。
- **残差 `v - codebook[idx]`** 是这一级"没能表达的部分"，会成为下一级的输入。
- `min(range(n), key=...)` 是 Python 求 argmin 的惯用写法：在下标集合里找使 `key` 最小的那个下标。

### 3.4 RVQ 编码：一级一级吃掉残差

```python
def rvq_encode(values, codebook_size=8, n_codebooks=4):
    residuals = list(values)
    codebooks = []
    all_indices = []
    for cb_i in range(n_codebooks):
        cb = learn_codebook(residuals, codebook_size, seed=cb_i)
        codebooks.append(cb)
        indices, residuals = quantize_with_codebook(residuals, cb)
        all_indices.append(indices)
    return all_indices, codebooks
```

这是整个文件的核心，对应讲义 "The core trick: Residual Vector Quantization"：

```text
第 0 级：学码本 C0 ← 原信号      ；量化 → 索引 I0，残差 r1 = x - C0[I0]
第 1 级：学码本 C1 ← r1          ；量化 → 索引 I1，残差 r2 = r1 - C1[I1]
第 2 级：学码本 C2 ← r2          ；……
```

- `residuals = list(values)` 先复制一份，避免改动调用方的列表。
- `indices, residuals = quantize_with_codebook(residuals, cb)`：**用同一个变量名接住新残差**，下一轮循环就自动在更小的残差上学码本——一行代码体现了"残差"二字。
- 每一级的码本都在**上一级残差的分布**上学习，所以码字的尺度逐级缩小。实测第 0 级码字约在 [-1.14, 1.47]，第 1 级缩到约 [-0.44, 0.41]。
- `seed=cb_i` 让每级初始化不同但可复现。
- 返回值 `all_indices` 是 `n_codebooks × N` 的二维列表，相当于真实 codec 里形状为 `(n_codebooks, n_frames)` 的 `codes` 张量（讲义 Step 1 中 EnCodec 输出 `(1, n_codebooks, n_frames)`）。
- ⚠️ 简化 1：码本是在**要压缩的同一段信号**上现学的（相当于"训练集 = 测试集"）。真实 codec 的码本在海量数据上训练好后固定不变，编码新音频时只做量化，不再学习。这也是本例在 8 级之后 MSE 显示为 `0.000000` 的原因之一——过拟合到了这 1000 个点。
- ⚠️ 简化 2：真实 codec 的编码器、量化器、解码器是**端到端联合训练**的（量化步骤用 straight-through 估计器传梯度），这里只有量化器，且是贪心地逐级独立学习。

### 3.5 RVQ 解码：码字相加

```python
def rvq_decode(all_indices, codebooks, length):
    out = [0.0] * length
    for indices, cb in zip(all_indices, codebooks):
        for i, idx in enumerate(indices):
            out[i] += cb[idx]
    return out
```

- 对每一级，把该级每个位置选中的码字 `cb[idx]` 累加到输出上。对应讲义："At inference time, the decoder sums all chosen codes per frame to reconstruct."
- `[0.0] * length` 创建全零列表（元素是不可变的 float，这里用 `*` 是安全的，和 3.2 中列表的列表不同）。
- 因为解码是**纯加法**，你可以只传入前 k 级的索引和码本做"低码率解码"——这就是 RVQ 码率可伸缩的来源，也是测验 Q10 码本消融实验的做法。
- ⚠️ 真实 codec 中，码字相加得到的是**潜向量**，还要再送进一个神经网络解码器（卷积 + Transformer 等）才能变回波形；这里由于量化的就是样本本身，相加后直接就是重建信号。

### 3.6 Step 2：扫描码本数，观察误差与码率

```python
    for n_cb in [1, 2, 4, 8, 12]:
        indices, codebooks = rvq_encode(sig, codebook_size=8, n_codebooks=n_cb)
        recon = rvq_decode(indices, codebooks, length=len(sig))
        err = mse(sig, recon)
        bits_per_frame = n_cb * 3
        bitrate = bits_per_frame * 50
        print(f"  | {n_cb:>11} | {bits_per_frame:>10} | {err:.6f}   | {bitrate:>5} bps       |")
```

- `bits_per_frame = n_cb * 3`：`3 = log2(8)`，每个码本索引 3 bit。
- `bitrate = bits_per_frame * 50`：假设每秒 50 帧，算出一个"如果这是真实 codec"的码率，便于和讲义里的 kbps 数字建立直觉。
- ⚠️ `3` 是硬编码的：如果把 `codebook_size` 改成 16 或 1024，这一列不会跟着变，会输出错误的码率。更稳妥的写法是 `math.ceil(math.log2(codebook_size))`（测验 Q9 就考这个）。
- 每次循环都**从头重新训练**全部码本（而不是在 4 级的基础上再加 4 级）。由于种子按级号固定，前 k 级的结果其实是一样的，只是多花了些时间。

### 3.7 Step 3 / Step 4：把 toy 映射回真实 codec

```python
    rows = [
        ("EnCodec-24k", "75 Hz",   "3.2 PESQ", "general audio, MusicGen"),
        ("DAC-44.1k",   "86 Hz",   "3.5 PESQ", "highest fidelity"),
        ("SNAC-24k",    "~12 Hz",  "3.3 PESQ", "multi-scale, AR-LM"),
        ("Mimi",        "12.5 Hz", "3.1 PESQ", "semantic+acoustic, Moshi"),
    ]
    print("  | codec        | frame rate | quality    | use case                 |")
    for name, fr, q, u in rows:
        print(f"  | {name:<12} | {fr:<10} | {q:<10} | {u:<24} |")
```

- 这部分**没有计算**，只是把讲义两张表（帧率表、PESQ 表）的关键数字打印出来。
- `for name, fr, q, u in rows:` 把每个四元组解包成四个变量。
- `{name:<12}` 左对齐占 12 个字符，用来打印对齐的表格。
- ⚠️ 标题写着 "speech @ 6 kbps"，但对照讲义的质量表，SNAC 的 3.3 PESQ 对应 3 kbps、Mimi 的 3.1 PESQ 对应 4.4 kbps，只有 EnCodec 和 DAC 是 6 kbps。读表时要注意它们并不是严格同码率比较。
- Step 4 打印的是 Mimi 的分工：码本 0 由 WavLM 蒸馏、负责内容；码本 1–7 是声学残差、负责音色/说话人/噪声；LM 先生成码本 0，再条件生成 1–7。最后的 takeaways 中 "12.5 Hz Mimi × 8 codebooks = 1000 tokens per 10 s clip" 就是 `10 × 12.5 × 8`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 一维标量代替高维向量 | 距离就是 `abs`，最近邻一目了然 | 真实 codec 在 64–512 维潜空间做向量量化 |
| 在待压缩信号上现学码本 | 不需要额外训练数据，演示自包含 | 码本应在大规模数据上训练后冻结；否则就是过拟合 |
| 逐级贪心学码本 | 直观体现"残差"概念 | 真实系统端到端训练，用 straight-through 估计器、commitment loss、EMA 更新码本 |
| 空桶中心保持不动 | 避免除零，代码最短 | 会产生死码字；生产中常重置死码字或做码本归一化 |
| 固定 20 次迭代 | 简单、可预测的运行时间 | 应检查中心移动量是否小于阈值以提前停止 |
| 硬编码 `3` bit 与 50 fps | 打印出贴近真实世界的码率 | 应从 `codebook_size` 与真实帧率计算 |
| `random.Random(seed)` 独立实例 | 结果可复现，不污染全局随机状态 | —— 这是值得照搬的好习惯 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块文档字符串 | 文件开头的 `"""Residual Vector Quantization ..."""` | 写在模块第一行的字符串，`help(main)` 时可见 |
| 默认参数 | `def rvq_encode(values, codebook_size=8, n_codebooks=4)` | 调用时可省略；可用关键字传参 `n_codebooks=n_cb` |
| 列表推导式 | `[math.sin(...) + 0.3 * rng.gauss(0, 1.0) for i in range(n)]` | 一行生成列表 |
| 列表的列表 | `[[] for _ in range(size)]` | 每次循环新建空列表；**不要**写 `[[]] * size`（会共享同一对象） |
| `_` 占位变量 | `for _ in range(iterations)` | 表示"这个循环变量用不到" |
| `lambda` + `min(key=...)` | `min(range(size), key=lambda i: abs(centroids[i] - v))` | 求 argmin：在下标里找让 key 最小的那个 |
| 多返回值 / 元组解包 | `indices, residuals = quantize_with_codebook(...)` | 函数 `return a, b` 实际返回元组，左边一次接住 |
| `zip` | `for indices, cb in zip(all_indices, codebooks)` | 按位置配对多个序列 |
| `enumerate` | `for i, idx in enumerate(indices)` | 同时拿到下标和元素 |
| 增量赋值 | `out[i] += cb[idx]` | 等价于 `out[i] = out[i] + cb[idx]` |
| 真值判断 | `if not values:`、`if buckets[i]:` | 空列表为假，非空为真 |
| `random.Random(seed)` | `rng = random.Random(seed)` | 独立的随机数生成器实例；`rng.random()` 返回 [0,1)，`rng.gauss(μ, σ)` 返回正态样本 |
| f-string 格式符 | `{n_cb:>11}`、`{err:.6f}`、`{name:<12}`、`{min(sig):.2f}` | `>` 右对齐、`<` 左对齐、数字为宽度；`.6f` 保留 6 位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()`，被导入时不执行 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（不到 1 秒）的关键输出：

```text
=== Step 1: generate signal ===
  length: 1000   range: [-1.67, 1.88]   mean: 0.005

=== Step 2: RVQ reconstruction error vs codebook count ===
  codebook_size = 8   values per codebook
  | # codebooks | bits/frame | MSE        | bitrate @ 50 fps |
  |           1 |          3 | 0.013647   |   150 bps       |
  |           2 |          6 | 0.000521   |   300 bps       |
  |           4 |         12 | 0.000001   |   600 bps       |
  |           8 |         24 | 0.000000   |  1200 bps       |
  |          12 |         36 | 0.000000   |  1800 bps       |
```

逐行解读：

- **Step 1**：1000 个样本，范围约 [-1.67, 1.88]（正弦幅度 1 加噪声），均值接近 0。信号方差约 0.60。
- **1 个码本**：只有 8 个"台阶"，MSE ≈ 0.0136，已经把方差 0.60 降低了约 44 倍——第一级码本拿走了绝大部分能量。
- **2 个码本**：MSE ≈ 5.2e-4，又降了约 26 倍。
- **4 个码本**：MSE ≈ 1e-6（额外实验测得第 3 级为 2.55e-5、第 4 级为 1.07e-6），每加一级误差大约缩小 20 多倍。
- **8、12 个码本**：MSE 小到 6 位小数显示为 0。8 级 × 3 bit = 24 bit，相当于 `8^8 ≈ 1677 万`个可区分的取值，去表示 1000 个点绰绰有余（也有"在同一信号上学码本"的过拟合因素）。
- **规律**：码率**线性**增长（150 → 300 → 600 → 1200 bps），误差却按**数量级**下降，而且很快饱和。这告诉我们两件事：①少量码本就能覆盖大部分信息，后面的码本是精修；②码本加到一定数量后收益几乎为零，却会让 LM 序列线性变长——这就是讲义 Pitfalls 中"停在 8–12 个码本"的原因。

```text
=== Step 3: 2026 codec comparison (speech @ 6 kbps) ===
  | EnCodec-24k  | 75 Hz      | 3.2 PESQ   | general audio, MusicGen  |
  | DAC-44.1k    | 86 Hz      | 3.5 PESQ   | highest fidelity         |
  | SNAC-24k     | ~12 Hz     | 3.3 PESQ   | multi-scale, AR-LM       |
  | Mimi         | 12.5 Hz    | 3.1 PESQ   | semantic+acoustic, Moshi |
```

- 这几行是硬编码的讲义数字：DAC 保真度最高但帧率也最高（86 Hz，序列最长）；Mimi PESQ 最低，却因 12.5 Hz 的低帧率和语义码本成为流式对话的首选——**"重建最好"和"最适合做 LM"是两回事**。
- Step 4 和 takeaways 只是文字说明，最后一行 `1000 tokens per 10 s clip` 可以自己用 `10 × 12.5 × 8` 验算。

---

## 7. 动手改一改

1. **修掉硬编码**：把 `bits_per_frame = n_cb * 3` 改成用 `math.log2(codebook_size)` 计算，再把 `codebook_size` 改成 4、16 各跑一次，观察"同码率下小码本多级 vs 大码本少级"的误差差异。
2. **码本消融**：用 4 级 RVQ 编码后，分别只解码 `ind[1:]`（去掉第 0 级）和 `ind[:3]`（去掉最后一级），比较 MSE（参考结果：约 0.586 vs 2.55e-5）。
3. **同比特对比**：比较"一个 64 码字码本"和"2 级 × 8 码字 RVQ"的 MSE（参考：约 3.30e-4 vs 5.21e-4），想一想为什么单码本更准，但真实 codec 仍选 RVQ。
4. **训练/测试分离**：用 `generate_signal(seed=0)` 学码本、用 `generate_signal(seed=1)` 只做量化（不重新学码本），观察 8 级时 MSE 是否还会是 0。需要你把 `rvq_encode` 拆成"训练码本"和"用已有码本编码"两个函数。
5. **死码字统计**：在 `learn_codebook` 里统计最后一轮有多少个空桶；把 `codebook_size` 调到 64、256 看看死码字比例如何变化，并实现"把空桶中心重置为一个随机样本"的修复。
6. **升到二维**：把信号改成 `(sin, cos)` 二维点序列，把 `abs` 换成欧氏距离，实现真正的"向量"RVQ。

---

## 8. 常见坑

- **`[[]] * size` 共享引用**：创建桶时若这样写，所有桶是同一个列表，k-means 会完全错乱。本文件用推导式规避了。
- **硬编码比特数**：改了 `codebook_size` 却忘了改 `* 3`，打印的码率就是错的，而且不会报错。
- **把"MSE = 0"当成好模型**：码本在同一信号上学出来，8 级之后的"完美重建"很大程度是过拟合；评估 codec 必须用没见过的音频。
- **误以为码本越多越好**：误差的下降很快饱和，而 LM 要预测的 token 数与码本数成正比。
- **忽略空桶**：真实训练中码本利用率低（大量死码字）会让有效词表远小于名义大小，白白浪费比特。
- **把 toy 码率当真**：50 fps 是假设值，这个一维信号并没有"帧"的物理意义；真实码率要用 codec 的真实帧率与码本大小计算。
