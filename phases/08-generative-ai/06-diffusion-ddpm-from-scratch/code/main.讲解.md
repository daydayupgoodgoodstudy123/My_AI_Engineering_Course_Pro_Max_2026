# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 06 节 Diffusion Models — 从头开始的 DDPM ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 2–3 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

一个完整的、纯 Python 的一维 DDPM：数据是 `0.5·N(-2, 0.4²) + 0.5·N(2, 0.4²)`，去噪网络是"`[x_t ‖ 正弦时间嵌入]` → 24 → 24 → 1"的两层 tanh MLP，手写反向传播，训练 4000 步后用 40 步反向链采 500 个样本并画直方图。它要你亲手走一遍：

1. **调度**：β、α、ᾱ 三个数组怎么来，`ᾱ_t` 为什么让"一步加噪"成为可能。
2. **训练 = 一行损失**：随机 t、闭式加噪、回归噪声 `(ε̂ - ε)²`——没有判别器、没有 KL。
3. **时间条件**：网络通过正弦嵌入知道当前在第几步。
4. **反向采样**：讲义里那条"丑陋但只是代数"的更新式，以及最后一步为什么不加噪。
5. **一个值得警惕的细节**：T=40 却沿用了为 T=1000 设计的 β 区间，前向过程并没有把数据变成纯噪声（见 3.4 节）。

> 一句话：**扩散模型 = 学会"在每个噪声水平下把噪声猜出来"，然后从噪声出发一步步减回去**。同样的循环，换成 U-Net/DiT 和图像 latent，就是 Stable Diffusion。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sin_embed(t, T, dim=8)` | 函数 | 时间步 → 8 维 `[sin, cos, sin, cos, ...]` | 正弦时间嵌入 |
| `tanh` / `tanh_grad` / `matmul` / `add` / `randn_matrix` | 工具函数 | 激活、导数、线性代数、初始化 | 基础算子 |
| `init_net` / `forward(x_t, t_embed, net)` | 网络 | 9 → 24 → 24 → 1，返回 `ε̂` 和缓存 | 噪声预测器 `ε_θ(x_t, t)` |
| `backward(target_eps, eps_hat, cache, net)` | 反向 | MSE 对三层参数的梯度 | 反向传播 |
| `apply_update(net, grads, lr)` | 优化器 | SGD（batch=1，不做平均） | 梯度下降 |
| `make_schedule(T)` | 函数 | 线性 β → α → 累乘 ᾱ | 噪声调度 |
| `sample_data(rng)` | 数据 | 两峰混合中采一个数 | `p_data` |
| `train(...)` | 训练循环 | 采 `x₀`、随机 t、闭式加噪、回归噪声 | `L_simple` |
| `sample(...)` | 采样 | 从 `N(0,1)` 出发跑 T 步反向链 | 反向过程 `p_θ` |
| `histogram(...)` / `main()` | 可视化 / 入口 | 字符画直方图、统计两峰样本数 | — |

数据流：**训练**：`x₀ → (t, ε) → x_t → [x_t ‖ emb(t)] → MLP → ε̂ → (ε̂-ε)² → backward → SGD`；**采样**：`x_T ~ N(0,1) → for t = T-1..0: ε̂ = MLP(x_t, t) → x_{t-1} = 均值 + 噪声`。

---

## 3. 逐段精讲

### 3.1 正弦时间嵌入

```python
def sin_embed(t, T, dim=8):
    """Sinusoidal timestep embedding."""
    out = []
    half = dim // 2
    for i in range(half):
        freq = 1.0 / (10000 ** (i / max(half - 1, 1)))
        out.append(math.sin(t * freq))
        out.append(math.cos(t * freq))
    return out[:dim]
```

- 与 Transformer 位置编码同源：一组几何级数分布的频率 `1, 10000^{-1/3}, 10000^{-2/3}, 10000^{-1}`（`half = 4` 时），每个频率贡献一对 `sin`、`cos`。
- `max(half - 1, 1)` 防止 `dim = 2` 时 `half - 1 = 0` 导致除以 0。`out[:dim]` 在 `dim` 为奇数时截断多出来的一项。
- 参数 `T` 没有被使用（函数签名里保留了它，但计算与 T 无关）。
- ⚠️ 频率是为"上万个位置"设计的，而这里 t 只有 0–39：最低频 `1e-4` 那一对在整个范围内几乎恒为 `(0, 1)`，第三对也只变化很小（`t·0.00215 ≤ 0.084`）。真正区分时间步的主要是前两对。我打印过 `t=39` 的嵌入：`[0.964, 0.267, 0.971, -0.237, 0.084, 0.996, 0.004, 1.0]`，后两对几乎是常数。对小 T 的任务，可以把 `10000` 换成更小的基数。
- 讲义说"Our toy code uses sinusoidal → concat. Production U-Nets use FiLM"：这里嵌入直接拼接到输入（见 3.2），生产中嵌入先过 MLP，再在每个 block 用 FiLM / AdaLN 调制特征。

### 3.2 去噪网络：输入拼接时间嵌入

```python
def forward(x_t, t_embed, net):
    inp = x_t + t_embed
    pre1 = add(matmul(net["W1"], inp), net["b1"])
    h1 = tanh(pre1)
    pre2 = add(matmul(net["W2"], h1), net["b2"])
    h2 = tanh(pre2)
    eps_hat = add(matmul(net["W3"], h2), net["b3"])
    return eps_hat, {"inp": inp, "h1": h1, "h2": h2, "pre1": pre1, "pre2": pre2}
```

- `x_t + t_embed` 是**列表拼接**：`[x_t]`（1 维）接上 8 维嵌入，共 9 维，所以 `init_net` 里 `W1` 的列数是 `x_dim + t_dim`。
- 两层 tanh 隐藏层（24 单元），输出层线性——预测的噪声是任意实数。
- 返回的 `cache` 字典保存反向传播需要的中间量（`pre1`、`pre2` 其实没被 `backward` 用到，因为 tanh 的导数用输出 `h` 计算）。
- 这就是讲义的 `ε_θ(x_t, t)`：同一套权重服务所有 40 个噪声水平，t 只通过嵌入告诉网络"现在噪声有多大"。

### 3.3 反向传播与 SGD

```python
    d_out = [2 * (a - b) for a, b in zip(eps_hat, target_eps)]
    for i in range(len(d_out)):
        grads["b3"][i] += d_out[i]
        for j in range(len(cache["h2"])):
            grads["W3"][i][j] += d_out[i] * cache["h2"][j]
    d_h2 = [sum(net["W3"][i][j] * d_out[i] for i in range(len(d_out)))
            for j in range(len(cache["h2"]))]
    d_pre2 = [d_h2[j] * tanh_grad(cache["h2"])[j] for j in range(len(cache["h2"]))]
    # ... 同样的模式重复到第一层
```

- `d_out = 2(ε̂ - ε)`：MSE 对输出的导数。之后每层都是"偏置梯度 = 上游梯度、权重梯度 = 外积、输入梯度 = Wᵀ·上游梯度、过 tanh 乘 `1 - h²`"的标准套路（与本阶段 VAE、GAN 两节一致）。
- ⚠️ **性能小坑**：`tanh_grad(cache["h2"])[j]` 写在推导式内部，每个 `j` 都把整个 24 维向量的导数重算一遍再取一个，`O(H²)` 而非 `O(H)`。应在推导式外先算 `g2 = tanh_grad(cache["h2"])`。
- `apply_update` 直接 `v -= lr * grad`，没有除以 batch 大小——因为每步只用 1 个样本。

### 3.4 调度：线性 β → α → 累乘 ᾱ

```python
def make_schedule(T):
    betas = [1e-4 + (0.02 - 1e-4) * t / (T - 1) for t in range(T)]
    alphas = [1 - b for b in betas]
    alpha_bars, cum = [], 1.0
    for a in alphas:
        cum *= a
        alpha_bars.append(cum)
    return betas, alphas, alpha_bars
```

- `betas` 从 `1e-4` 线性增到 `0.02`（`t = T-1` 时恰好 0.02）；`alphas = 1 - β`；`alpha_bars` 是前缀累乘 `ᾱ_t = ∏_{s≤t} α_s`。用一个运行中的 `cum` 变量累乘，是计算前缀积的标准 `O(T)` 写法（等价于 `itertools.accumulate(alphas, operator.mul)`）。
- 有了 `ᾱ_t`，就能一步写出 `x_t = √ᾱ_t·x₀ + √(1-ᾱ_t)·ε`（讲义的闭式解）。
- ⚠️ **这里有一个与讲义不一致的地方**：`1e-4 → 0.02` 这个区间是 DDPM 为 **T = 1000** 设计的，那时 `ᾱ_T ≈ 4e-5`，`x_T` 确实约等于 `N(0, 1)`。代码在 **T = 40** 时照搬了它：`Σβ ≈ 0.40`，我实测 `ᾱ_T = 0.667`，`√ᾱ_T = 0.817`——加完 40 步噪声后，数据还保留着 82% 的幅度，噪声标准差只有 0.58。但 `sample()` 仍然从 `N(0, 1)` 出发，**训练时网络在 t=39 见过的输入**（中心 ±1.63 的两峰）与**采样时的起点**（以 0 为中心的单峰）对不上。模型最终仍能生成两个峰，但位置和宽度都有偏差（见第 6 节）。测验 Q9 详细分析了它的后果和修法。

### 3.5 训练循环：一行损失

```python
def train(net, alpha_bars, T, steps, lr, t_dim, rng):
    for step in range(steps):
        x0 = sample_data(rng)
        t = rng.randrange(T)
        a_bar = alpha_bars[t]
        eps = rng.gauss(0, 1)
        x_t = math.sqrt(a_bar) * x0 + math.sqrt(1 - a_bar) * eps
        t_emb = sin_embed(t, T, t_dim)
        eps_hat, cache = forward([x_t], t_emb, net)
        grads = backward([eps], eps_hat, cache, net)
        apply_update(net, grads, lr)
        if (step + 1) % 500 == 0:
            loss = (eps_hat[0] - eps) ** 2
            print(f"step {step+1:5d}: loss {loss:.4f}")
```

逐行对照讲义的 `L_simple = E_{x₀, t, ε}[||ε - ε_θ(√ᾱ_t·x₀ + √(1-ᾱ_t)·ε, t)||²]`：

| 代码 | 公式中的部分 |
|------|------------|
| `x0 = sample_data(rng)` | `x₀ ~ p_data` |
| `t = rng.randrange(T)` | `t ~ Uniform{0..T-1}` |
| `eps = rng.gauss(0, 1)` | `ε ~ N(0, 1)` |
| `x_t = sqrt(a_bar)*x0 + sqrt(1-a_bar)*eps` | 闭式加噪 |
| `forward([x_t], t_emb, net)` | `ε_θ(x_t, t)` |
| `backward([eps], ...)` | 对 `(ε̂ - ε)²` 求梯度 |

- 注意 `eps` 既是加噪用的噪声，也是回归的**标签**——这是一个"自监督"任务：标签是我们自己造出来的，所以永远不缺。
- 每步只有 1 个样本、1 个随机 t，梯度方差很大；生产中 batch 里每个样本各自随机 t。
- ⚠️ 打印的是**当前这一个样本**的平方误差，随 t 的不同天然在 0.02–2 之间跳动，不能当作收敛曲线看（见第 6 节）。

### 3.6 反向采样：从噪声往回走

```python
def sample(net, alphas, alpha_bars, T, t_dim, rng):
    x = rng.gauss(0, 1)
    for t in range(T - 1, -1, -1):
        t_emb = sin_embed(t, T, t_dim)
        eps_hat, _ = forward([x], t_emb, net)
        beta_t = 1 - alphas[t]
        mean = (x - beta_t / math.sqrt(1 - alpha_bars[t]) * eps_hat[0]) / math.sqrt(alphas[t])
        if t > 0:
            x = mean + math.sqrt(beta_t) * rng.gauss(0, 1)
        else:
            x = mean
    return x
```

- 这正是讲义的 `x_{t-1} = (1/√α_t)·(x_t - β_t/√(1-ᾱ_t)·ε_θ) + σ_t·z`，取 `σ_t = √β_t`。
- `range(T - 1, -1, -1)` 从 39 倒数到 0（终点 -1 不含）。
- **均值项的直觉**：`x_t - β_t/√(1-ᾱ_t)·ε̂` 是"减去这一步该去掉的那一小份噪声"，再除以 `√α_t` 补偿前向时的缩放。
- **最后一步不加噪声**：`t = 0` 时直接取均值。如果最后还加 `√β_0·z`，就等于在最终样本上再撒一层噪声，没有后续步骤能把它去掉。
- 每一步都要调用一次网络——T 步就是 T 次前向，这就是讲义说的"diffusion inference is a step-count problem"。生产中会用 DDIM / DPM-Solver 只在少数时间步上调用网络（测验 Q10 实现了一个 DDIM 版本）。

### 3.7 `main`：配置与评估

```python
    rng = random.Random(13)
    T, t_dim, hidden = 40, 8, 24
    _, alphas, alpha_bars = make_schedule(T)
    net = init_net(1, t_dim, hidden, rng)
    train(net, alpha_bars, T, steps=4000, lr=0.01, t_dim=t_dim, rng=rng)
    samples = [sample(net, alphas, alpha_bars, T, t_dim, rng) for _ in range(500)]
    print(histogram(samples))
    m = sum(samples) / len(samples)
    pos = sum(1 for s in samples if s > 0)
    print(f"mean {m:+.3f}, modeA(<0)={500-pos}, modeB(>0)={pos}")
```

- `_, alphas, alpha_bars = make_schedule(T)`：用 `_` 丢弃不需要的 `betas`（采样时用 `1 - alphas[t]` 重新算 β）。
- 评估只统计了总体均值和正负两侧的样本数。和 GAN 那一节一样，这种"按符号数模式"的指标看不出峰的位置偏差和峰之间的伪样本——建议补上每个峰的均值/标准差和低密度区占比。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 一维两峰数据 | 能打印直方图，秒级跑完 | 真实任务在图像 latent 上，用 U-Net / DiT |
| T = 40（而非 1000） | 采样 40 次前向，纯 Python 也能接受 | 照搬 T=1000 的 β 区间导致 `ᾱ_T ≈ 0.67`，前向终点不是纯噪声；生产中训练用 T≈1000，推理靠采样器跳步 |
| 线性 β 调度 | DDPM 默认，最容易理解 | cosine 调度同等算力 FID 更好（讲义 Pitfalls） |
| 正弦嵌入直接拼接 | 最简单的时间条件 | 生产用嵌入 → MLP → FiLM / AdaLN；小 T 时高位频率几乎无用 |
| ε-prediction | DDPM 标准，损失最简单 | 极端 t 下信噪比差，v-prediction 更稳 |
| `σ_t = √β_t`，最后一步不加噪 | DDPM 的标准选择之一 | 也可以用后验方差或学习方差（Improved DDPM） |
| batch=1 的 SGD | 代码最短 | 梯度方差大；生产用大 batch + Adam/AdamW + EMA 权重 |
| 手写反向传播 | 看清每个梯度 | 有 `O(H²)` 的小性能坑；生产用 autograd |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 整除与 `max` 防零 | `half = dim // 2`；`max(half - 1, 1)` | 向下取整；给分母一个下限 |
| 幂运算 | `10000 ** (i / max(half - 1, 1))` | 浮点指数，生成几何级数频率 |
| 切片截断 | `return out[:dim]` | 只保留前 `dim` 个元素 |
| 列表拼接 | `inp = x_t + t_embed`、`forward([x_t], ...)` | `[x_t]` 先把标量包成列表再拼接 |
| 字典字面量作缓存 | `{"inp": inp, "h1": h1, ...}` | 前向把中间量按名字存起来供反向使用 |
| 字典推导式 | `grads = {k: None for k in net}` | 建与参数同结构的梯度字典 |
| 多变量同行初始化 | `alpha_bars, cum = [], 1.0` | 元组解包同时初始化两个变量 |
| 前缀累乘 | `for a in alphas: cum *= a; alpha_bars.append(cum)` | 运行累积量；也可用 `itertools.accumulate` |
| 条件表达式 | `rng.gauss(-2.0, 0.4) if rng.random() < 0.5 else rng.gauss(2.0, 0.4)` | 一行实现"先抽成分再采样" |
| 倒序 `range` | `range(T - 1, -1, -1)` | 从 T-1 递减到 0 |
| `_` 丢弃返回值 | `eps_hat, _ = forward(...)`；`_, alphas, alpha_bars = make_schedule(T)` | 不需要的值用 `_` 接收 |
| 关键字参数 | `train(net, alpha_bars, T, steps=4000, lr=0.01, t_dim=t_dim, rng=rng)` | 调用处自带说明 |
| `or` 默认值 | `peak = max(counts) or 1` | 全 0 时避免阈值为 0 |
| f-string 格式符 | `f"{step+1:5d}"`、`f"{loss:.4f}"`、`f"{m:+.3f}"` | 宽度 5 整数；4 位小数；带符号 3 位小数 |

---

## 6. 运行结果解读

实际运行（Python 3.13，耗时约 2.5 秒）的输出：

```text
=== training DDPM on two-mode 1-D mixture ===
step   500: loss 0.2163
step  1000: loss 1.5629
step  1500: loss 2.0959
step  2000: loss 0.2167
step  2500: loss 0.0435
step  3000: loss 0.0241
step  3500: loss 0.2062
step  4000: loss 0.0538

=== sampling ===
                    #         
                    #         
       #           ##         
       ##          ###        
       ###        ####        
      ####        ####        
      #####      ######       
     ######      ######       
------------------------------
mean -0.107, modeA(<0)=229, modeB(>0)=271
```

逐段解读：

- **训练日志**：每行只是第 500k 步那**一个**样本的平方误差，所以在 0.02 和 2.1 之间乱跳；1000、1500 步的大值不代表发散，只是恰好抽到了难预测的样本 / 时间步。要判断收敛，需要看滑动平均或固定验证集上分 t 统计的平均损失。
- **直方图**：30 个格子覆盖 `[-5, 5)`，每格宽约 0.33。底行左边一簇 `#` 落在约 -3.3 ~ -1.3，最高点在 -2.5 附近；右边一簇落在约 +0.7 ~ +2.7，最高点在 +1.7 ~ +2.0 之间。两个峰都出现了，中间有明显的低谷——讲义的 takeaway "reproduces both modes" 在定性上成立。
- **样本数平衡**：229 vs 271，两个模式都被覆盖，没有模式崩溃——这是扩散相对 GAN 的典型优势。
- **定量看还有偏差**：我用同一个训练好的模型、独立随机数再采 1000 个样本，测得负峰均值 -2.19（标准差 0.61），正峰均值 +1.68（标准差 0.54），6.8% 的样本落在 `|x| < 1`（真实数据约 0.6%，两峰标准差 0.4）。正峰偏向中间、两峰都偏宽，与 3.4 节的"起点错位"一致：采样从 `N(0, 1)` 出发，比训练时 t=39 的真实输入分布更靠中间。
- **讲义练习 1 的参考**：把 T 改成 10 后（`ᾱ_T ≈ 0.90`，错位更严重），我实测两峰均值缩到约 ±1.17，42% 的样本落在 `|x| < 1`，两峰结构基本被压扁。

---

## 7. 动手改一改

1. **打印 `ᾱ_T`**：在 `main` 里加 `print(alpha_bars[-1])`，分别试 `T = 10, 40, 100, 1000`，体会"Σβ 决定总噪声量"。
2. **修正调度**：让 β 随 T 缩放（例如上界改成 `min(0.02 * 1000 / T, 0.2)`）或实现 cosine 调度（注意把 β 截断在一个不太大的值以内，例如 0.3；截断在 0.999 时最后一步会把误差放大约 31 倍），使 `ᾱ_T` 接近 0；再加大 `hidden` 和训练步数，比较两峰的均值和标准差。
3. **更好的监控**：把训练日志改成最近 500 步的平均损失；采样后报告每个峰的均值、标准差和 `|x| < 1` 的比例。
4. **修掉 `O(H²)`**：把 `tanh_grad(...)` 移到推导式外面，用 `zip` 逐元素相乘，确认结果不变。
5. **DDIM 采样器**：实现 `predict_x0` 和确定性 DDIM（`x_{t'} = √ᾱ_{t'}·x̂₀ + √(1-ᾱ_{t'})·ε̂`），对比 40 / 10 / 5 步的样本统计（参考：三者几乎相同，体现"同一模型、步数大减"）。
6. **进阶：v-prediction 或 CFG**（讲义练习 2、3）：把网络的回归目标换成 `v = √ᾱ·ε - √(1-ᾱ)·x₀` 并重新推导采样步；或给数据加类别标签，训练时 10% 概率丢掉条件，采样时用 `ε = (1+w)·ε_cond - w·ε_uncond`，统计不同 `w` 下的"条件模式命中率"。

---

## 8. 常见坑

- **闭式加噪忘了开方**：必须是 `√ᾱ_t·x₀ + √(1-ᾱ_t)·ε`，写成 `ᾱ_t·x₀ + (1-ᾱ_t)·ε` 是最常见的 bug。
- **调度与 T 不匹配**：少步数时照搬 T=1000 的 β，前向终点不是纯噪声，采样起点错位（本文件就是这种情况）。
- **β 太大**：反向一步除以 `√α_t`，β 接近 1 会把误差放大几十倍、样本发散。
- **最后一步加了噪声**：`t = 0` 时应直接输出均值。
- **时间索引错位**：训练用 `t ∈ [0, T-1]`，采样也必须从 `T-1` 倒数到 0，且 `sin_embed`、`alphas[t]`、`alpha_bars[t]` 使用同一个 t。
- **把单样本损失当收敛曲线**：扩散损失随 t 差异极大，必须平均或分桶看。
