# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 05 节 风格GAN（StyleGAN） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，瞬间完成） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这是一个**没有训练、只有前向**的"StyleGAN 精简版"：用一个 4 层 mapping MLP 把 8 维 `z` 映射成 8 维 `w`，再让一个 3 层的"合成网络"从固定常量出发，每层用 `w` 计算出的 scale/bias 做 AdaIN，并可选地注入噪声。它要你看清 StyleGAN 的三个零件分别做了什么：

1. **Mapping network**：`z → w`，`W` 空间不是高斯，形状由网络决定。
2. **从常量出发 + AdaIN 注入**：合成网络的输入与 `z` 无关，`w` 只通过每层的 scale/bias 进入——这就是"风格"调制。
3. **截断技巧**：`w' = ŵ + ψ·(w - ŵ)`，ψ 从 0 到 1，输出从"平均样本"走向"原样本"。
4. **逐层噪声**：固定 `w`，只换噪声种子，输出跟着变——"全局风格"与"随机细节"的分离。

> 一句话：**StyleGAN 不把 latent 当输入，而是当"调音旋钮"逐层拧**；这份代码把这几个旋钮用 130 行纯 Python 搭了出来。⚠️ 它没有判别器、没有训练，所以只能演示机制，不能演示"效果"。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `leaky` / `randn_matrix` / `matmul` / `add` | 工具函数 | LeakyReLU、随机初始化、矩阵乘向量、逐元素加 | 基础算子 |
| `mean_std(xs)` | 函数 | 向量的均值与（加 ε 的）总体标准差 | 归一化统计量 |
| `adain(features, scale, bias)` | 函数 | 归一化后乘 scale 加 bias | AdaIN |
| `init_mapping` / `mapping(z, layers)` | 初始化 / 前向 | 4 层 8→8 的 MLP，参数存成 `(W, b)` 元组列表 | Mapping network `f: Z → W` |
| `init_synth(hidden, w_dim, rng)` | 初始化 | 每层一个 6×6 权重、偏置，以及把 `w` 投影成标量 scale/bias 的两个 8 维向量 | 合成网络 + 仿射投影 "A" |
| `stylegan_forward(w, const, synth, noise_sigma, rng, adain_on)` | 前向 | 从常量出发，3 层"线性 → LeakyReLU → AdaIN(w) → 噪声" | Synthesis network |
| `main()` | 演示入口 | 三个实验：AdaIN 开关对比、截断技巧、噪声注入 | — |

数据流：`z ~ N(0, I) → mapping → w`；`const → [层 0：W0, leaky, AdaIN(w), noise] → [层 1] → [层 2] → 6 维输出`。`w` 从不作为合成网络的输入，只决定每层的 `scale`、`bias`。

---

## 3. 逐段精讲

### 3.1 Mapping network：`(W, b)` 元组列表

```python
def mapping(z, layers):
    h = z
    for W, b in layers:
        pre = add(matmul(W, h), b)
        h = [leaky(x) for x in pre]
    return h

def init_mapping(z_dim, w_dim, depth, rng):
    layers = []
    dims = [z_dim] + [w_dim] * depth
    for i in range(depth):
        layers.append((randn_matrix(dims[i + 1], dims[i], rng), [0.0] * dims[i + 1]))
    return layers
```

- `dims = [8] + [8] * 4 = [8, 8, 8, 8, 8]`，第 i 层把 `dims[i]` 维映射到 `dims[i+1]` 维。这种"先列出各层维度，再按相邻两项建层"的写法在任何 MLP 构造里都很常见。
- 每层都是"线性 + LeakyReLU"，**最后一层也有激活**，所以 `w` 的分布被 LeakyReLU 扭曲：负值被压缩到 0.2 倍，整体不再是零均值的高斯。我实测 200 个 `w` 的各维均值在 -0.01 到 +0.12 之间、标准差只有 0.03–0.14——这就是讲义说的 "`W` is not forced to be Gaussian"。
- 真实 StyleGAN 是 8 层、512 维；这里缩成 4 层、8 维（`main` 里 `depth=4`）。讲义 Step 1 的示意代码用 `M[f"W{i}"]` 字典存参数，实际代码用元组列表，以代码为准。

### 3.2 AdaIN：把统计量"换掉"

```python
def mean_std(xs):
    m = sum(xs) / len(xs)
    v = sum((x - m) ** 2 for x in xs) / len(xs)
    return m, math.sqrt(v + 1e-8)

def adain(features, scale, bias):
    m, s = mean_std(features)
    return [scale * (f - m) / s + bias for f in features]
```

- 公式就是讲义的 `AdaIN(x, y) = y_scale · (x - mean(x)) / std(x) + y_bias`。
- **一个必须吃透的性质**：输出的均值恰好是 `bias`，标准差约为 `|scale|`。归一化抹掉了原来的一阶、二阶统计量，再用 `w` 给出的新统计量替换——"风格 = 统计量"在这里一目了然（测验 Q10 给出了证明和实测验证）。
- `+ 1e-8` 加在方差里再开方，防止所有特征相等时除以 0。
- ⚠️ **与真实 StyleGAN 的差别**：真实 AdaIN 对**每个通道**在**空间维度**上求均值方差，每个通道有自己的 scale/bias；这里把整个 6 维隐藏向量当成"一张特征图"，只有一个标量 scale 和一个标量 bias。
- ⚠️ `scale` 是 `w` 的线性函数，可能为负（模式翻转）或接近 0（信息被压扁）。真实实现会把 scale 写成 `1 + affine(w)` 的形式（或让仿射层 bias 初始化为 1），让初始 scale 接近 1。

### 3.3 合成网络：常量出发，逐层调制

```python
def stylegan_forward(w, const, synth, noise_sigma, rng, adain_on=True):
    """Very small 'synthesis' network: three resolution blocks on a 4-channel constant."""
    h = list(const)
    for i in range(3):
        W = synth[f"W{i}"]
        b = synth[f"b{i}"]
        pre = add(matmul(W, h), b)
        h = [leaky(x) for x in pre]
        if adain_on:
            scale = sum(synth[f"scale{i}"][j] * w[j] for j in range(len(w)))
            bias = sum(synth[f"bias{i}"][j] * w[j] for j in range(len(w)))
            h = adain(h, scale, bias)
        if noise_sigma > 0:
            h = [x + noise_sigma * rng.gauss(0, 1) for x in h]
    return h
```

- **从常量出发**：`h = list(const)`，`const` 在 `main` 里只生成一次，对所有样本相同。对应讲义"Feed a constant 4×4×512 tensor as the network input"。`list(const)` 复制一份，避免后续修改影响原常量。
- **每层的 scale / bias**：`scale = Σ_j synth["scale_i"][j] · w[j]`，即 `w` 与一个可学习向量的点积——这就是讲义里"affine projections of w"（StyleGAN 架构图里标作 "A" 的那个仿射层），只是这里省略了偏置，输出是标量。
- **顺序**：线性 → LeakyReLU → AdaIN → 噪声，与讲义"conv → AdaIN(w) → noise"的顺序一致（真实 StyleGAN 的噪声是在 AdaIN 之前加到卷积输出上的，这里放在 AdaIN 之后，属于简化）。
- **噪声**：每个元素独立加 `noise_sigma · N(0,1)`。真实 StyleGAN 是"单通道噪声图 × 学习的逐通道系数"，这里 `noise_sigma` 是一个固定常数，不可学习。
- ⚠️ docstring 写"three resolution blocks on a 4-channel constant"，但实际常量是 `hidden = 6` 维，也没有任何上采样；"分辨率块"只是比喻。
- ⚠️ **`adain_on=False` 的陷阱**：`w` 只在 `if adain_on:` 分支里使用。关掉 AdaIN 后网络里没有任何 `w` 的入口，噪声又是 0，所以**无论 `z` 是什么输出都一样**。这不是"没有 AdaIN 的 StyleGAN"，而是"不接收 latent 的生成器"。

### 3.4 实验一：AdaIN 开 vs 关

```python
    for mode in [True, False]:
        outs = []
        for _ in range(5):
            z = [rng.gauss(0, 1) for _ in range(z_dim)]
            w = mapping(z, mapping_net)
            h = stylegan_forward(w, const, synth, 0.0, rng, adain_on=mode)
            outs.append(h)
        flat = [v for row in outs for v in row]
        m, s = mean_std(flat)
```

- `flat` 用双层推导式把 5×6 的结果摊平成 30 个数再求标准差。这个指标把"样本之间的差异"和"同一输出内 6 个维度之间的差异"混在一起了。
- AdaIN 关闭时样本之间差异为 0，打印出的 `std 0.012` 完全来自维度之间。所以这个实验真正证明的是"关掉 AdaIN 后 `w` 进不了网络"。讲义声称本代码展示了"AdaIN 调制 matches or beats 把 z 拼接进输入"，但代码里**没有拼接 z 的基线**，网络也未训练，这个结论并未被演示（见测验 Q9）。

### 3.5 实验二：截断技巧

```python
    ws = []
    for _ in range(200):
        z = [rng.gauss(0, 1) for _ in range(z_dim)]
        ws.append(mapping(z, mapping_net))
    w_bar = [sum(w[i] for w in ws) / len(ws) for i in range(w_dim)]

    z_test = [rng.gauss(0, 1) for _ in range(z_dim)]
    w_test = mapping(z_test, mapping_net)

    for psi in [0.0, 0.5, 0.7, 1.0]:
        w_psi = [w_bar[i] + psi * (w_test[i] - w_bar[i]) for i in range(w_dim)]
        h = stylegan_forward(w_psi, const, synth, 0.0, rng, adain_on=True)
```

- `ŵ`（`w_bar`）是 200 个 `w` 的逐维平均：`[sum(w[i] for w in ws) / len(ws) for i in range(w_dim)]`——外层遍历维度、内层遍历样本。
- 截断公式完全照抄讲义：`w' = ŵ + ψ·(w - ŵ)`。`ψ=0` 得到 `G(ŵ)`（"平均样本"），`ψ=1` 得到 `G(w_test)`。
- 截断是在 **`W` 空间**做的（先 mapping 再插值），不是在 `Z` 空间——这是 StyleGAN 截断的标准做法。
- 由于每层的 scale/bias 是 `w` 的线性函数，它们也随 ψ 线性变化；但经过归一化和 LeakyReLU，输出对 ψ 是非线性的。

### 3.6 实验三：固定 `w`，只换噪声

```python
    z_fixed = [rng.gauss(0, 1) for _ in range(z_dim)]
    w_fixed = mapping(z_fixed, mapping_net)
    for seed in range(3):
        rng_local = random.Random(seed)
        h = stylegan_forward(w_fixed, const, synth, 0.1, rng_local, adain_on=True)
```

- 每个种子新建一个独立的 `random.Random(seed)`，只用于噪声，保证三次运行的 `w` 完全相同、只有噪声不同——这是做"控制变量"实验的正确写法。
- 打印的结尾语说"outputs vary slightly with noise seed"。⚠️ 但从实际数字看（第 6 节），噪声造成的变化（如最后一维 -0.82 / -0.58 / -0.68）**比截断实验中 ψ 从 0 到 1 造成的变化还大**。原因：网络未训练，输出本身的尺度只有 0.1–0.4，而噪声标准差固定为 0.1，且前两层的噪声还会被后面的 AdaIN 重新放缩。真实 StyleGAN 的噪声系数是**学出来的**，训练会把它调到"只影响细节"的量级。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 不训练、只演示前向 | 130 行内展示三个零件的机制 | 无法说明"效果更好"；真实 StyleGAN 需要判别器、混合正则、长时间训练 |
| 向量级 AdaIN（标量 scale/bias） | 最简单地体现"替换统计量" | `w` 每层只有 2 个标量入口；真实实现逐通道、在空间维度上归一化 |
| scale 直接是 `w` 的线性函数 | 代码短 | 可能为负或接近 0；生产用 `1 + affine(w)` 或 bias 初始化为 1 |
| 固定 `noise_sigma` | 简单 | 噪声强度不可学习，未训练时会盖过风格的影响 |
| mapping 用 4 层、8 维 | 跑得快 | 真实是 8 层 512 维 |
| 截断在 `W` 空间做 | 与 StyleGAN 一致，`W` 更解耦 | 需要先采样大量 `w` 估计 `ŵ`（生产中会预先算好并缓存） |
| 独立的 `random.Random(seed)` 用于噪声 | 控制变量，只改变噪声 | 无 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 条件表达式 | `return x if x > 0 else a * x` | LeakyReLU 一行实现 |
| 多返回值 | `return m, math.sqrt(v + 1e-8)`；`m, s = mean_std(features)` | 返回元组并解包 |
| 列表拼接与乘法 | `dims = [z_dim] + [w_dim] * depth` | 构造层维度列表 `[8, 8, 8, 8, 8]` |
| 元组作为列表元素 | `layers.append((W, b))`；`for W, b in layers:` | 把一层的权重和偏置打包，遍历时直接解包 |
| `list(...)` 复制 | `h = list(const)` | 浅拷贝，避免修改原常量 |
| f-string 生成字典键 | `synth[f"W{i}"]`、`synth[f"scale{i}"]` | 按层号动态拼出参数名 |
| 嵌套推导式摊平 | `[v for row in outs for v in row]` | 二维列表 → 一维列表（外层循环写在前） |
| 按维度求平均 | `[sum(w[i] for w in ws) / len(ws) for i in range(w_dim)]` | 外层遍历维度、内层生成器遍历样本 |
| 关键字参数 | `init_mapping(z_dim, w_dim, depth=4, rng=rng)`；`adain_on=mode` | 调用时写明参数名，可读性更好 |
| 布尔列表循环 | `for mode in [True, False]:` | 同一段代码跑两种配置 |
| 独立随机数生成器 | `rng_local = random.Random(seed)` | 每个种子一个独立随机流，互不干扰 |
| f-string 嵌套推导 | `f"output = {[f'{v:+.2f}' for v in h]}"` | 打印格式化后的列表 |
| 字符串对齐小技巧 | `"no AdaIN  "`（末尾补空格） | 手动让两行输出对齐 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 0.03 秒）的输出：

```text
=== compare: style inputs via AdaIN vs no AdaIN ===
sample 5 random z, look at std of output under each mode
  with AdaIN: mean -0.016  std 0.152
  no AdaIN  : mean +0.012  std 0.012

=== truncation trick: sample many w, take mean, interpolate ===
  psi=0.0: output = ['+0.08', '+0.07', '+0.02', '+0.10', '-0.07', '-0.20']
  psi=0.5: output = ['+0.11', '+0.06', '-0.02', '+0.14', '-0.07', '-0.27']
  psi=0.7: output = ['+0.12', '+0.06', '-0.04', '+0.15', '-0.05', '-0.31']
  psi=1.0: output = ['+0.12', '+0.09', '-0.06', '+0.15', '-0.05', '-0.36']

=== per-layer noise injection (pose fixed, stochastic detail changes) ===
  seed 0: ['+0.18', '+0.05', '+0.03', '+0.22', '-0.30', '-0.82']
  seed 1: ['+0.15', '-0.06', '-0.23', '+0.36', '-0.23', '-0.58']
  seed 2: ['+0.11', '+0.04', '-0.02', '-0.07', '-0.48', '-0.68']
```

逐段解读：

- **实验一**：`with AdaIN` 的 std 0.152 远大于 `no AdaIN` 的 0.012。正确的解读是：AdaIN 打开时，不同 `z` 通过 `w` 改变了每层的统计量，输出各不相同；关闭时 5 个输出**完全相同**（我单独打印过，每行都是 `[0.02, 0.021, -0.001, 0.03, 0.008, -0.004]`），0.012 只是同一向量内 6 个数的离散程度。我还逐样本验证了：AdaIN 打开时每个输出向量的均值、标准差分别等于最后一层的 `bias`、`|scale|`（如 -0.0680 / 0.2180）。
- **实验二**：ψ 从 0 到 1，输出从 `G(ŵ)` 平滑地移向 `G(w_test)`，最后一维从 -0.20 变到 -0.36，变化是单调、连续的。ψ=0.7（讲义推荐的常用值）已经很接近 ψ=1，但更"靠近平均"。
- **实验三**：同一个 `w`，3 个噪声种子给出明显不同的输出。方向上与讲义一致（"同一个 `w`，细节随噪声变化"），但幅度不是"slightly"：噪声造成的差异（最后一维 -0.82 ~ -0.58）比实验二中 ψ 全程的变化（-0.20 ~ -0.36）还大。这是未训练网络 + 固定噪声强度的结果，真实 StyleGAN 中噪声系数会被学到很小。

---

## 7. 动手改一改

1. **修正多样性指标**：把实验一改成"逐维计算 5 个样本之间的标准差，再取平均"，确认 `no AdaIN` 时结果为 0。
2. **加一个公平的基线**：写 `concat_forward(z, const, synth)`，把 `const + w`（列表拼接，14 维）作为第一层输入，对比它和 AdaIN 版在"跨样本标准差"上的差异（注意要为第一层新建 6×14 的权重）。
3. **验证 AdaIN 性质**：对任意输出 `h`，打印 `mean_std(h)` 和最后一层的 `bias`、`abs(scale)`，确认两者相等。
4. **风格混合**：实现 `stylegan_forward_mix(w_a, w_b, crossover, ...)`，前 `crossover` 层用 `w_a`、其余用 `w_b`。观察 `crossover=1, 2` 时输出为什么几乎等于 `G(w_b)`（提示：最后一层 AdaIN 决定了输出的均值和标准差）。
5. **让 scale 远离 0**：把 scale 改成 `1.0 + sum(...)`，对比实验一、二的输出变化。
6. **调噪声强度**：把实验三的 `noise_sigma` 从 0.1 依次改为 0.01、0.03，找到"噪声只造成小幅变化"的量级，体会真实 StyleGAN 为什么要让噪声系数可学习。

---

## 8. 常见坑

- **误以为 `adain_on=False` 是"普通 GAN 基线"**：它根本不接收 latent，输出与 `z` 无关。
- **摊平后求标准差当多样性**：会把维度间差异误当成样本间差异。
- **在 `Z` 空间做截断或编辑**：`Z` 纠缠，效果不可控；StyleGAN 的截断和编辑都在 `W`（或 W+、StyleSpace）中进行。
- **AdaIN 的 scale 没有偏置到 1**：scale 接近 0 时整层信息被压扁，梯度也会消失。
- **把这个玩具的层次行为当成真实 StyleGAN 的规律**：未训练、无空间维度的网络里，"低层管结构、高层管细节"并不成立。
- **以为截断能省算力**：ψ 只改变 `w`，前向计算量完全不变。
