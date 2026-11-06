# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 10 节 视频生成 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数，约 4 秒） ｜ **依赖**：仅 Python 标准库（`math`、`random`）

---

## 1. 这份代码在考察什么

视频生成与图像生成最大的区别是**时间一致性**。这份代码用一个 6 帧的一维"视频"来演示：

1. **"视频 = 一串相关的帧"**：每段视频是一条带随机起点、随机斜率的平滑轨迹，帧与帧之间高度相关。
2. **patchify + 位置编码**：每帧当作一个 patch，附上帧序号的正弦编码，再展平成一个长向量——Sora 式"时空 patch 序列"的极简版。
3. **联合去噪**：一个网络**同时**预测所有帧的噪声，帧之间通过网络共享信息，所以采样出的视频是连贯的。
4. **闪烁基线**：把每帧独立采样的结果和联合采样对比，用"帧间差（frame-to-frame delta）"量化闪烁。

> 一句话：**视频扩散 = 把所有帧放进同一个去噪器里一起去噪**。帧间耦合是消除闪烁的关键；真实系统里负责耦合的是时空注意力，这里是一个全连接层。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sin_embed(t, dim)` | 函数 | 正弦/余弦编码（既用于帧位置，也用于扩散时间步） | 位置编码 / 时间步 embedding |
| `T_FRAMES = 6`、`POS_DIM = 4` | 常量 | 每段视频的帧数、帧位置编码维度 | 视频长度、位置编码维度 |
| `make_video(rng)` | 函数 | 生成 `base + slope·t + 小噪声` 的 6 帧轨迹 | 训练数据（带运动的视频） |
| `patchify_with_pos(video)` | 函数 | 每帧 → `[帧值] + 位置编码`（5 维） | 时空 patch + 位置编码 |
| `flatten(patches)` | 函数 | 6 个 5 维 patch 展平成 30 维 | 把 patch 序列送进网络 |
| `init_net` / `forward` / `backward` / `apply` | 函数 | `38 → 48 → 48 → 6` 的 tanh MLP，手写反传与 SGD | 去噪器（真实系统中是时空 DiT） |
| `make_schedule(T)` | 函数 | 线性 β 调度 | DDPM 前向过程 |
| `train_joint(...)` | 函数 | 对整段视频加噪、联合预测 6 帧噪声 | 视频扩散训练 |
| `sample_joint(...)` | 函数 | 6 帧一起从噪声反向采样 | 视频扩散采样 |
| `independent_per_frame(T_frames, rng)` | 函数 | 每帧 `N(0,1) + 0.3·t` 独立生成 | 闪烁基线（见 3.6 的评审） |
| `frame_deltas(video)` | 函数 | 相邻帧差的绝对值 | 闪烁/平滑度指标 |
| `main()` | 函数 | 训练 3000 步 → 联合采样 5 段 → 基线 5 段 → 比较平均 delta | 实验编排 |

数据流：`make_video → 加噪 → patchify_with_pos → flatten → forward（+ 时间步编码）→ 预测 6 帧噪声 → backward`；采样时 6 帧同时从 `N(0,1)` 出发，每步都整体经过 `patchify → flatten → forward`。

---

## 3. 逐段精讲

### 3.1 数据：带运动的"视频"

```python
def make_video(rng):
    """1-D 'video': smooth trajectory of T_FRAMES values."""
    base = rng.gauss(0, 1)
    slope = rng.gauss(0, 0.3)
    return [base + slope * t + rng.gauss(0, 0.05) for t in range(T_FRAMES)]
```

- `base` 是"场景内容"（第 0 帧的位置），`slope` 是"运动"（每帧的位移），`N(0, 0.05)` 是很小的逐帧噪声。
- 帧间相关性很强：相邻帧的差约为 `slope`，平均绝对值约 `0.3·√(2/π) ≈ 0.24`。我们在临时副本里对 2000 段真实数据统计，平均帧间差为 **0.245**。
- ⚠️ 与讲义 Step 1 的写法不同：讲义里是 8 帧、固定斜率 0.3、噪声 0.1；代码是 6 帧、随机斜率、噪声 0.05。以代码为准。

### 3.2 patchify + 位置编码

```python
def patchify_with_pos(video):
    """Each 'patch' here is one frame value + its time position embedding."""
    out = []
    for t in range(T_FRAMES):
        pe = sin_embed(t, POS_DIM)
        out.append([video[t]] + pe)
    return out  # list of (1 + POS_DIM) vectors


def flatten(patches):
    return [v for patch in patches for v in patch]
```

- 每帧变成 `[帧值, sin(t), cos(t), sin(t·1e-4), cos(t·1e-4)]`，6 帧展平成 30 维，再在 `forward` 里拼上 8 维扩散时间步编码，网络输入共 **38 维**。
- `flatten` 是一个**双层推导式**：`for patch in patches` 在外，`for v in patch` 在内，顺序与嵌套 for 循环一致。
- 对应真实系统：3D VAE 输出 `[T_latent, H_latent, W_latent, C_latent]`，切成 `[t_p, h_p, w_p]` 的块，每块加 3D 位置编码后排成序列。这里 `t_p = 1`，空间维只有 1 个"像素"。
- ⚠️ **在这个 MLP 里，位置编码几乎不起作用**：它对每个样本都是同样的常数，且每帧在展平向量中的槽位是固定的，网络已经从"哪个输入槽"知道是第几帧了。位置编码真正必不可少的是 transformer：自注意力是置换等变的，不加位置编码就不知道 token 的时空坐标（测验 Q9）。讲义说"temporal coherence emerges ... when adjacent-frame patches share a denoiser and position embeddings"，在本代码中起作用的其实是前一半——**共享的联合去噪器**。

### 3.3 去噪网络：全连接 = 最粗暴的"全时空注意力"

```python
def forward(x, t_emb, net):
    inp = list(x) + list(t_emb)
    pre1 = add(matmul(net["W1"], inp), net["b1"])
    h1 = tanh(pre1)
    pre2 = add(matmul(net["W2"], h1), net["b2"])
    h2 = tanh(pre2)
    out = add(matmul(net["W3"], h2), net["b3"])
    return out, {"inp": inp, "h1": h1, "h2": h2}
```

- 第一层 `W1`（48×38）让每个隐藏单元都能看到**所有帧**，相当于"每一帧都能和其他所有帧交互"——功能上类似完整的时空注意力，只是参数与序列长度绑定、不能处理变长视频。
- 输出层 `W3`（6×48）一次给出 6 帧的噪声预测。
- 讲义 Build It 开头说代码"denoise the whole sequence with a transformer-style attention over patches"，⚠️ 但实际代码**没有注意力**，是 MLP（讲义 Step 3 的描述"concatenates all frame values + their position embeddings and predicts the noise for all frames jointly"与代码一致）。
- `backward` / `apply` 与第 07 节相同，不再赘述。

### 3.4 联合训练：`train_joint`

```python
def train_joint(net, alpha_bars, T, t_dim, steps, lr, rng):
    """Joint sampling: denoiser sees all frames + their time positions simultaneously."""
    for step in range(steps):
        video = make_video(rng)
        t = rng.randrange(T)
        eps = [rng.gauss(0, 1) for _ in range(T_FRAMES)]
        a_bar = alpha_bars[t]
        noisy = [math.sqrt(a_bar) * video[i] + math.sqrt(1 - a_bar) * eps[i]
                 for i in range(T_FRAMES)]
        patches = patchify_with_pos(noisy)
        x_flat = flatten(patches)
        t_emb = sin_embed(t, t_dim)
        out, cache = forward(x_flat, t_emb, net)
        grads = backward(eps, out, cache, net)
        apply(net, grads, lr)
```

- **整段视频共用一个扩散时间步 `t`**，每帧有独立的噪声 `eps[i]`。这与真实视频扩散一致：整个时空潜变量处在同一噪声水平。
- 注意两种"时间"的区别：帧序号（0–5，视频里的时间）由 `patchify_with_pos` 编码；扩散时间步 `t`（0–39，加噪程度）由 `sin_embed(t, t_dim)` 编码。面试时别把它们混为一谈。
- 损失与第 06 节完全一致：预测噪声的 MSE（讲义："Same diffusion loss as Lesson 06"）。

### 3.5 联合采样：`sample_joint`

```python
def sample_joint(net, alphas, alpha_bars, T, t_dim, rng):
    x = [rng.gauss(0, 1) for _ in range(T_FRAMES)]
    for t in range(T - 1, -1, -1):
        patches = patchify_with_pos(x)
        x_flat = flatten(patches)
        t_emb = sin_embed(t, t_dim)
        eps_hat, _ = forward(x_flat, t_emb, net)
        beta_t = 1 - alphas[t]
        new_x = [(x[i] - beta_t / math.sqrt(1 - alpha_bars[t]) * eps_hat[i]) / math.sqrt(alphas[t])
                 for i in range(T_FRAMES)]
        if t > 0:
            x = [new_x[i] + math.sqrt(beta_t) * rng.gauss(0, 1) for i in range(T_FRAMES)]
        else:
            x = new_x
    return x
```

- 6 帧**同步**去噪，每一步网络都能看到所有帧的当前状态，所以帧 3 的去噪方向会参考帧 2 和帧 4。这就是"coupled denoising"。
- 每帧注入的随机噪声 `rng.gauss` 仍然相互独立，但网络会在后续步骤中把它们"协调"掉。
- ⚠️ `T = 40` 沿用为 T=1000 设计的 β 区间，`ᾱ_T ≈ 0.667`，与前几节存在同样的终端 SNR 问题。

### 3.6 闪烁基线与评估

```python
def independent_per_frame(T_frames, rng):
    """Baseline: sample each frame independently from a random walk."""
    return [rng.gauss(0, 1) + 0.3 * t for t in range(T_frames)]


def frame_deltas(video):
    return [abs(video[i + 1] - video[i]) for i in range(len(video) - 1)]
```

- `frame_deltas` 计算 5 个相邻帧差的绝对值；平均值越大，"闪烁"越严重。
- ⚠️ **基线并不公平**：
  - 它不是从数据分布中采样的——写死了 `+0.3·t` 的趋势（数据中 `slope` 的均值是 0），每帧加独立的 `N(0,1)`；
  - docstring 说 "random walk"，但随机游走是噪声累加，这里各帧噪声独立、不累加；
  - 它没有经过任何模型。
  更公平的对照是"每帧都服从真实的单帧边缘分布、帧间独立"（测验 Q11）。好在结论是稳健的：我们用公平基线统计，平均 delta 为 1.484，仍远大于联合采样。
- ⚠️ `main` 只比较 5 段（25 个 delta），统计波动很大（见第 6 节）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 一维、6 帧的"视频" | 纯 Python 几秒跑完，平滑度一眼可见 | 没有空间维度，无法体现分解注意力 |
| 每帧一个 patch（`t_p = 1`） | 最简单的 patchify | 真实系统用 3D VAE + `[t_p, h_p, w_p]` 的 3D patch |
| 全连接 MLP 作去噪器 | 实现简单，天然让所有帧交互 | 输入长度写死；真实系统用时空 DiT，靠注意力 + 3D 位置编码处理变长序列 |
| 附加帧位置编码 | 形式上对齐 DiT | 在 MLP 中是常数输入，几乎没有作用 |
| 手写的独立噪声基线 | 直观演示闪烁 | 分布与数据不一致；应使用真实边缘分布做对照 |
| 只用 5 段比较 | 输出简短 | 统计不可靠；应该用数百段并报告方差 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `T_FRAMES = 6`、`POS_DIM = 4` | 全大写表示常量，被多个函数共享 |
| 文档字符串 | `"""1-D 'video': smooth trajectory of T_FRAMES values."""` | 说明函数用途 |
| 列表拼接 | `[video[t]] + pe`、`list(x) + list(t_emb)` | 把帧值和位置编码拼成一个 patch |
| 双层列表推导（展平） | `[v for patch in patches for v in patch]` | 先遍历外层再遍历内层，等价于嵌套 for 循环 |
| 列表推导 | `[abs(video[i + 1] - video[i]) for i in range(len(video) - 1)]` | 相邻差分 |
| `list.extend` | `joint_deltas.extend(deltas)` | 把一个列表的元素逐个追加（`append` 会把整个列表当一个元素） |
| `str.join` + 生成器 | `" ".join(f"{v:+.2f}" for v in clip)` | 把格式化后的数字用空格连接成一行 |
| f-string 格式符 | `f"{v:+.2f}"`、`f"{avg_joint:.2f}"` | 带正负号 / 保留 2 位小数 |
| 下划线丢弃 | `eps_hat, _ = forward(...)` | 不用的返回值 |
| 关键字参数 | `train_joint(net, alpha_bars, T, t_dim, steps=3000, lr=0.01, rng=rng)` | 参数多时更清晰 |
| `range` 倒序 | `range(T - 1, -1, -1)` | 反向采样 |
| `random.Random(seed)` | `rng = random.Random(21)` | 可复现的独立随机源 |

---

## 6. 运行结果解读

实际运行输出：

```text
=== training joint video DDPM: 6 frames per clip ===

=== 5 clips, joint sampling (coherent) ===
  clip 0: -1.50 -1.30 +0.35 +0.51 +1.62 +2.46
  clip 1: +0.72 +0.01 -0.49 -1.06 -1.65 -2.46
  clip 2: -0.81 -0.70 +0.07 +0.28 +1.39 +1.53
  clip 3: -1.16 -0.88 +0.10 +0.18 +0.80 +1.38
  clip 4: -1.06 -0.57 +0.05 -0.70 +0.34 -0.06

=== 5 clips, independent per-frame (flicker baseline) ===
  clip 0: -1.67 +1.68 +1.93 -0.02 +0.51 +1.58
  clip 1: -0.02 -1.06 +1.39 +1.26 +1.84 +1.48
  clip 2: +2.08 +0.36 +0.52 -1.30 +2.85 +1.26
  clip 3: +0.49 -0.39 +0.34 +1.54 +2.40 +1.76
  clip 4: +1.15 +0.56 -0.12 +2.16 +1.94 +0.53

avg frame-to-frame delta: joint=0.61  independent=1.23
joint sampling produces smoother motion (smaller deltas).
```

逐段解读：

- **joint 的 5 段**大多呈单调趋势（clip 1 一路下降，clip 2、3 一路上升），这就是"运动"。但它们并不完美：clip 0 从 −1.30 跳到 +0.35，斜率明显大于训练数据（`slope` 的标准差只有 0.3）；clip 4 来回摆动。小网络 + 简化调度学到的运动比真实数据"抖"。
- **independent 的 5 段**正负乱跳（clip 0：−1.67 → +1.68 → +1.93 → −0.02），这就是闪烁。
- **平均 delta**：joint 0.61 vs independent 1.23，联合采样平滑约一倍。
- 这个数字本身不可靠：只有 25 个 delta。我们在临时副本中用更大样本复算：真实数据 0.245、joint 模型（300 段）0.359、代码基线（2000 段）1.163、公平基线（2000 段）1.484。**结论成立，但 joint 与真实数据之间仍有差距**。
- 训练阶段没有输出，所以第一个标题下面是空行。

---

## 7. 动手改一改

1. **讲义练习 1**：把两种采样各跑 300 段，报告帧间差的均值和方差；再加上"真实数据"和"公平基线"两组对照（测验 Q11）。
2. **讲义练习 2：首帧条件**：仿照第 09 节的 inpaint，每步把第 0 帧替换成固定值的加噪版本（测验 Q10 有参考代码），观察固定值随帧数衰减的现象，并思考为什么生产 I2V 要在训练时就加入首帧条件。
3. **验证位置编码的作用**：把 `patchify_with_pos` 里的 `pe` 换成全 0，重新训练，比较平均 delta。预期几乎没有变化——体会 MLP 与 transformer 对位置信息需求的不同。
4. **打乱帧顺序**：训练时随机打乱 6 帧的顺序（位置编码跟着帧走），MLP 是否还能学到运动？这时位置编码是否开始有用？
5. **加长视频**：把 `T_FRAMES` 改成 12，看看输入维度怎样变化、网络能否保持平滑；体会"MLP 的输入长度写死"的局限，以及真实系统为什么要用滑动窗口。
6. **修调度**：把 β 上限改为 0.2，观察 joint 采样的平均 delta 是否更接近真实数据的 0.245。

---

## 8. 常见坑

- **混淆"帧序号"与"扩散时间步"**：前者是视频里的时间（0–5），后者是加噪程度（0–39），两者用不同的编码分别输入。
- **以为位置编码在任何网络里都必要**：在固定长度的 MLP 里，位置已经由输入槽位隐式给出；transformer 才必须显式加位置编码。
- **基线不公平**：拿一个与数据分布不一致的手写噪声做对照，会夸大模型的优势。
- **样本太少就下结论**：5 段视频得到的平均值波动很大（0.61 vs 大样本的 0.36）。
- **`extend` 与 `append` 混用**：`joint_deltas.append(deltas)` 会得到"列表的列表"，`sum` 时直接报错。
- **以为帧间差越小越好**：delta 为 0 意味着视频是静止的。好的模型应该让 delta 的分布接近真实数据，而不是一味地小。
