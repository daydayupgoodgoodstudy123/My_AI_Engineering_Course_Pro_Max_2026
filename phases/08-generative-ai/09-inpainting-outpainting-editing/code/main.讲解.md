# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 09 节 局部重绘（Inpainting）、扩图（Outpainting）与图像编辑 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 3 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

这份代码训练一个普通的（无条件）5 维 DDPM，然后**不改模型、只改采样过程**，就实现了 inpainting 和 outpainting。它要你搞懂：

1. **朴素 inpainting（mask 重注入）**：每个反向步之前，把"已知"维度替换成按当前噪声水平加噪的原值，只让模型生成"未知"维度。
2. **为什么补出来的内容会与上下文协调**：网络在训练中学到了维度之间的相关性（5 维同属一个簇），已知维度通过网络的**联合预测**影响未知维度。
3. **Outpainting 就是 mask 反过来的 inpainting**：同一个 `inpaint` 函数，换一个 mask 即可。
4. 这种做法**不需要重新训练**——它是 RePaint、SDEdit 这类"免训练编辑"方法的共同基础。

> 一句话：**inpainting = 在反向过程中，不断用"已知部分的正确加噪版本"覆盖已知区域，让模型只负责未知区域。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sin_embed` / `tanh` / `tanh_grad` / `matmul` / `add` / `randn_matrix` | 工具函数 | 时间步编码与纯列表的网络算子 | 与第 07 节相同 |
| `init_net` / `forward` / `backward` / `apply` | 函数 | `13 → 32 → 32 → 5` 的 tanh MLP，手写反传与 SGD | 噪声预测网络 ε_θ(x_t, t)（**没有**类别条件） |
| `make_schedule(T)` | 函数 | 线性 β 调度 | DDPM 前向过程 |
| `sample_data(rng, d=5)` | 函数 | 两簇 5 维数据：全部维度约为 −1 或约为 +1（std 0.2） | 具有强相关性的"图像" |
| `train(...)` | 函数 | 标准 DDPM 训练循环 | ε 预测 MSE |
| `sample_unconditional(...)` | 函数 | 标准 DDPM 反向采样 | 对照组（`main` 中没有调用） |
| `inpaint(net, ..., clean, mask, rng)` | 函数 | 带 mask 重注入的反向采样 | 朴素 inpainting / outpainting |
| `main()` | 函数 | 训练 5000 步 → 5 次 inpaint（补维度 3–4）→ 3 次 outpaint（补维度 0–1） | 实验编排 |

数据流：`train` 学会 5 维联合分布 → `inpaint` 从纯噪声出发，每步先覆盖已知维度、再做一次标准反向步 → 结束时把已知维度精确还原。

---

## 3. 逐段精讲

### 3.1 数据：强相关的两簇

```python
def sample_data(rng, d=5):
    cluster = rng.choice([0, 1])
    center = [-1.0 if cluster == 0 else 1.0] * d
    return [c + rng.gauss(0, 0.2) for c in center], cluster
```

- 每个样本的 5 个维度**要么都在 −1 附近，要么都在 +1 附近**。这就是玩具版的"图像统计规律"：已知一部分像素，就能推断其余像素大致是什么。
- `[... ] * d` 把单元素列表复制 d 次，得到 `[c, c, c, c, c]`（元素是 float，复制是安全的）。
- 讲义 Step 1 的写法 `[-1.0] * 5 if cluster == 0 else [1.0] * 5` 与此等价。

### 3.2 网络与训练：一个普通的无条件 DDPM

```python
def forward(x_t, t_emb, net):
    inp = list(x_t) + list(t_emb)
    # ... 两层 tanh 隐藏层
    return out, {"inp": inp, "h1": h1, "h2": h2}


def train(net, alpha_bars, T, steps, lr, t_dim, d, rng):
    for step in range(steps):
        x0, _ = sample_data(rng, d)
        t = rng.randrange(T)
        eps = [rng.gauss(0, 1) for _ in range(d)]
        a_bar = alpha_bars[t]
        x_t = [math.sqrt(a_bar) * x0[i] + math.sqrt(1 - a_bar) * eps[i] for i in range(d)]
        t_emb = sin_embed(t, T, t_dim)
        out, cache = forward(x_t, t_emb, net)
        grads = backward(eps, out, cache, net)
        apply(net, grads, lr)
```

- 网络输入是 `5 + 8 = 13` 维（`list(x_t) + list(t_emb)` 拼接），输出 5 维噪声预测。`list(...)` 包一层是为了兼容元组等任意序列。
- **训练时完全不知道 mask 的存在**：簇标签被 `x0, _` 丢弃，模型只学 5 维联合分布 `p(x)`。这正是讲义中"朴素方法"的前提——用一个普通的生成模型做 inpainting。
- 一个关键细节：网络是**联合**预测 5 维噪声的（全连接层把所有维度混在一起），所以它能学到"维度 3 的噪声应该参考维度 0–2 的取值"。这是后面 inpaint 能"协调上下文"的根本原因。
- `backward` / `apply` 与第 07 节完全相同（同样存在 `tanh_grad` 在列表推导中重复计算的小性能问题）。

### 3.3 核心：`inpaint`

```python
def inpaint(net, alphas, alpha_bars, T, t_dim, d, clean, mask, rng):
    """mask[i] == True means that dim is to be regenerated. Unmasked dims pinned to clean."""
    x = [rng.gauss(0, 1) for _ in range(d)]
    for t in range(T - 1, -1, -1):
        a_bar = alpha_bars[t]
        for i in range(d):
            if not mask[i]:
                x[i] = math.sqrt(a_bar) * clean[i] + math.sqrt(1 - a_bar) * rng.gauss(0, 1)
        t_emb = sin_embed(t, T, t_dim)
        eps_hat, _ = forward(x, t_emb, net)
        beta_t = 1 - alphas[t]
        mean = [(x[i] - beta_t / math.sqrt(1 - alpha_bars[t]) * eps_hat[i]) / math.sqrt(alphas[t])
                for i in range(d)]
        if t > 0:
            x = [mean[i] + math.sqrt(beta_t) * rng.gauss(0, 1) for i in range(d)]
        else:
            x = mean
    for i in range(d):
        if not mask[i]:
            x[i] = clean[i]
    return x
```

逐步拆解：

| 步骤 | 代码 | 作用 |
|------|------|------|
| ① 初始化 | `x = [rng.gauss(0, 1) ...]` | 所有维度从纯噪声开始 |
| ② 重注入 | `x[i] = √ᾱ_t·clean[i] + √(1−ᾱ_t)·ε`（仅 `mask[i] == False`） | 已知维度换成"原值在时刻 t 应有的样子"，与未知维度处在同一噪声水平 |
| ③ 联合预测 | `eps_hat = forward(x, t_emb)` | 网络看到全部 5 维，未知维度的噪声预测受已知维度影响 |
| ④ 反向一步 | `mean = ...`，`t > 0` 时加噪 | 标准 DDPM 后验均值 + `σ_t = √β_t` |
| ⑤ 最终还原 | `x[i] = clean[i]`（仅已知维度） | 保证已知区域与原图**逐值一致** |

为什么这样设计：
- **② 为什么要加噪而不是直接放干净值**：网络只在"所有维度处于同一噪声水平"的输入上训练过。一半干净、一半很吵的输入不在训练分布里，预测会失准（测验 Q9）。
- **② 为什么每步都用新的随机噪声**：这是 `q(x_t | x₀)` 的一次独立采样。⚠️ 这也是朴素方法的弱点：已知维度的噪声与上一步生成的轨迹无关，已知和未知两部分没有"一起演化"，在真实图像里就表现为**接缝**。RePaint 的跳回重采样、专用 9 通道模型，都是为了弥补这一点。
- **⑤ 为什么还要还原**：第 ④ 步也会改动已知维度，最终输出的已知维度只是"模型去噪的版本"，不一定等于原值。
- ⚠️ 与第 07 节相同，这里的 `T = 40` 沿用了为 `T = 1000` 设计的 β 区间，`ᾱ_T ≈ 0.667`。对已知维度影响不大（它们反正每步被覆盖），但未知维度从 `N(0,1)` 起步，与训练时 `t = 39` 的输入分布不一致。

### 3.4 `main`：inpaint 与 outpaint 只差一个 mask

```python
    for trial in range(5):
        clean, cluster = sample_data(rng, d)
        mask = [False, False, False, True, True]
        out = inpaint(net, alphas, alpha_bars, T, t_dim, d, clean, mask, rng)
        label = "neg cluster" if cluster == 0 else "pos cluster"
        print(f"  {label}: pinned={[f'{clean[i]:+.2f}' for i in range(3)]}  "
              f"filled={[f'{out[i]:+.2f}' for i in range(3, 5)]}")
    # ...
    for trial in range(3):
        clean, cluster = sample_data(rng, d)
        mask = [True, True, False, False, False]
        out = inpaint(net, alphas, alpha_bars, T, t_dim, d, clean, mask, rng)
```

- inpainting：固定维度 0–2，生成 3–4（"补洞"）。
- outpainting：固定维度 2–4，生成 0–1（"往外扩"）。在一维序列上，"洞在中间/末尾"和"在开头扩展"对算法来说**完全一样**——讲义说 outpainting 是"mask inverted"、"Identical training objective"，正是这个意思。
- f-string 里嵌套了列表推导：`[f'{clean[i]:+.2f}' for i in range(3)]` 先把每个数格式化成字符串，再把整个列表打印出来，所以输出里能看到引号。
- `sample_unconditional` 定义了但 `main` 没有调用；它是很好的对照组（测验 Q10 的 k = 5 等价于它）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用无条件模型 + 采样时 mask 重注入 | 无需重训，演示"免训练编辑"的核心 | 接缝/不协调；生产用 9 通道专用模型（SD-Inpaint、Flux-Fill） |
| 每步对已知维度重新独立加噪 | 严格符合 `q(x_t|x₀)` | 已知与未知的轨迹不连贯；RePaint 用跳回重采样改善 |
| 5 维全相关的两簇数据 | 一眼能看出"补得对不对"（看符号） | 真实图像的相关性是局部、多尺度的 |
| 最后硬还原已知维度 | 保证未遮挡区域逐值一致 | 真实图像中还要处理 VAE 编解码带来的色偏（mask 外贴回原图） |
| 只打印少量样本 | 输出简短 | 不足以下结论；应统计大量样本的一致率（测验 Q10） |
| `T = 40` 沿用 T=1000 的 β | 与前几节一致、跑得快 | 终端 SNR 不为 0 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 布尔列表作 mask | `mask = [False, False, False, True, True]` | 用 `True/False` 标记每一维是否需要重绘 |
| `not` 取反 | `if not mask[i]:` | 未被遮挡（已知）的维度 |
| 列表复制 | `[-1.0 if cluster == 0 else 1.0] * d` | 单元素列表重复 d 次 |
| 条件表达式 | `"neg cluster" if cluster == 0 else "pos cluster"` | 三元表达式 |
| `list()` 转换 + 拼接 | `list(x_t) + list(t_emb)` | 统一成列表后拼接 |
| 列表推导 | `[math.sqrt(a_bar) * x0[i] + ... for i in range(d)]` | 逐维计算前向加噪 |
| 下划线丢弃返回值 | `x0, _ = sample_data(rng, d)`、`eps_hat, _ = forward(...)` | 不需要的返回值用 `_` 接收 |
| 关键字参数 | `train(net, alpha_bars, T, steps=5000, lr=0.01, t_dim=t_dim, d=d, rng=rng)` | 参数多时按名字传，避免顺序出错 |
| 文档字符串 | `"""mask[i] == True means ..."""` | 说明 mask 的语义约定 |
| 嵌套 f-string | `f"pinned={[f'{clean[i]:+.2f}' for i in range(3)]}"` | 外层双引号、内层单引号；`+.2f` 带符号保留 2 位 |
| f-string 跨行拼接 | `print(f"..." f"...")` | 相邻字符串字面量会自动连接 |
| `range` 倒序 | `range(T - 1, -1, -1)` | 从 T−1 到 0 |
| `dict.items()` / `isinstance` | `apply` 与 `backward` 中 | 统一遍历矩阵和向量参数 |

---

## 6. 运行结果解读

实际运行输出：

```text
=== training 5-D DDPM on two-cluster mixture ===

=== inpainting: pin dims 0-2, regenerate dims 3-4 ===
  pos cluster: pinned=['+1.17', '+1.20', '+1.23']  filled=['+0.26', '+0.90']
  neg cluster: pinned=['-0.97', '-0.71', '-0.71']  filled=['-0.81', '-1.19']
  pos cluster: pinned=['+0.84', '+0.95', '+1.14']  filled=['+0.74', '+0.94']
  neg cluster: pinned=['-1.14', '-1.03', '-0.58']  filled=['-1.12', '-1.12']
  neg cluster: pinned=['-1.22', '-1.18', '-1.02']  filled=['-0.80', '-0.79']

=== outpainting (mask dims 0-1, pin 2-4) ===
  pinned tail=[-0.98, -0.93, -0.73]  filled head=[-0.94, -0.68]
  pinned tail=[-0.65, -0.80, -1.08]  filled head=[-1.67, -0.62]
  pinned tail=[-1.12, -1.28, -0.92]  filled head=[-1.60, -0.95]

takeaway: the filled dims match the cluster sign of the pinned dims.
          that is why inpainting looks coherent with the surroundings.
```

- 训练阶段没有进度输出，所以第一行标题下面是空的。
- **inpainting 5 次全部同号**：已知维度为正，补出来的也是正；为负，补出来的也为负。说明已知信息确实通过网络传到了未知维度。
- **质量并不完美**：第一行补出了 `+0.26`，离 +1 很远（真实数据 std 只有 0.2）；outpaint 中出现 `-1.67`、`-1.60`，也明显超出簇的正常范围。这是朴素方法 + 小网络 + 调度不匹配的综合结果，对应真实图像中"内容大体对，但细节/边界不自然"。
- 8 个样本只能说明"看起来对"。我们在临时副本中做了统计（测验 Q10）：遮挡 1/2/3/4/5 维时，符号一致率分别为 0.960 / 0.980 / 0.920 / 0.740 / 0.452——上下文越少越差，全部遮挡时退化为约 50% 的随机水平（等同于无条件生成）。

---

## 7. 动手改一改

1. **调用对照组**：在 `main` 末尾用 `sample_unconditional` 采 200 个样本，统计"五维同号"的比例，与 inpaint 的结果对比。
2. **遮挡比例扫描**（讲义练习 1）：遮挡最后 k 维（k = 1…5），各跑 200 次，统计符号一致率与到簇中心的 MSE（参考答案见测验 Q10）。
3. **去掉加噪**：把重注入改成 `x[i] = clean[i]`（不加噪），重新统计一致率和补全值的分布，体会"噪声水平不一致"的危害。
4. **实现 SDEdit**：写一个从 `t0` 开始反向的函数，用一个正负混杂的源样本测试不同 `t0`（测验 Q11）。
5. **实现 RePaint**（讲义练习 2）：每到 `t % 10 == 0` 时，用 `x ← √(1−β)·x + √β·ε` 逐步加噪跳回 5 步，再重新去噪（每个跳点只跳一次）。我们在临时副本中试过，遮挡 4/5 维时一致率从约 0.71 升到约 0.77（单次运行，有随机波动），可以自己多跑几次、换种子验证。
6. **修调度**：把 β 上限改为 0.2，观察补全值是否更集中在 ±1 附近。

---

## 8. 常见坑

- **重注入时忘了加噪**：直接放干净值会让输入偏离训练分布。
- **用错时间步的 ᾱ**：重注入必须用**当前**时刻 t 的 `ᾱ_t`，与随后 `forward` 用的 `t_emb` 对应。
- **忘了最后还原已知区域**：输出的已知区域会被模型"轻微改写"，违背 inpainting "保持外部像素不变"的承诺。
- **mask 语义搞反**：本文件约定 `True` = 要重绘；有些库约定白色（1）= 重绘、黑色（0）= 保留，也有反过来的，接入前要确认。
- **只看几个样本下结论**：8 行输出全部同号，不代表一致率是 100%；生成模型的评估一定要统计。
- **以为朴素方法等于专用模型**：玩具数据上朴素方法够用，但讲义明确说真实图像要用 9 通道模型，因为纹理连贯性要求更高。
