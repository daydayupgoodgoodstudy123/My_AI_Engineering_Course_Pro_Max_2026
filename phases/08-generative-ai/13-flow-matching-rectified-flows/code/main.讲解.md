# 代码讲解 · main.py

> **所属小节**：阶段 08 · 生成式 AI · 第 13 节 Flow Matching 与 Rectified Flows ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`random`），无需 NumPy / PyTorch

---

## 1. 这份代码在考察什么

这份代码用不到 150 行纯 Python，在**一维双峰分布**上把流匹配（flow matching）从训练到采样完整走一遍：

1. **CFM 训练的"三采样一回归"**：采样数据 `x₀`、噪声 `x₁`、时间 `t`，构造直线插值 `x_t`，回归常数速度 `x₁ − x₀`——训练时完全不积分 ODE（simulation-free）。
2. **Euler 采样**：从 `t=1` 的噪声出发，用学到的速度场反向积分到 `t=0`，体会"步数 = 积分步数"。
3. **步数与质量的关系**：同一个模型分别用 1/2/4/8/20 步采样，用 ASCII 直方图直观看到 1 步时样本塌到两峰中间、4 步以上恢复双峰。
4. **手写反向传播**：一个 5→24→24→1 的 tanh MLP，前向、反向、SGD 更新全部手写，帮你确认"流匹配就是普通回归"。
5. **评估意识**：打印的"左右峰计数"在 1 步时看起来很均衡，但直方图显示分布其实是错的——提示单一粗糙指标会骗人。

> 一句话：**流匹配的训练就是一个 MSE 回归，采样就是解一个 ODE；路径越直，需要的步数越少。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `tanh` / `tanh_grad` / `matmul` / `add` | 工具函数 | 列表版的激活、导数、矩阵乘、向量加 | MLP 的基本运算 |
| `randn_matrix` / `init_net` | 函数 | 用 `N(0, 0.3²)` 初始化权重，偏置为 0 | 权重初始化 |
| `forward(x, t, net)` | 函数 | 拼时间特征 → 两层 tanh → 输出标量速度，并缓存中间值 | 速度场 `v_θ(x, t)` |
| `backward(target, out, cache, net)` | 函数 | 对平方误差手动求所有参数梯度 | 反向传播 |
| `apply(net, grads, lr)` | 函数 | 原地 SGD 更新 | 梯度下降 |
| `sample_data(rng)` | 函数 | 从 `0.5·N(−2, 0.3²) + 0.5·N(2, 0.3²)` 采样 | 数据分布 `x₀` |
| `train(net, steps, lr, rng)` | 函数 | CFM 训练循环（batch size = 1） | 条件流匹配损失 |
| `sample(net, num_steps, rng)` | 函数 | Euler 积分从噪声到数据 | ODE 采样 |
| `histogram(samples, ...)` | 函数 | 把样本画成 6 行高的 ASCII 直方图 | 可视化分布 |
| `main()` | 入口 | 训练 6000 步，再用 5 种步数各采 500 个样本并打印 | 步数对比实验 |

数据流：`main → train（反复调用 sample_data → forward → backward → apply）→ 对每个步数调用 sample（反复调用 forward）→ histogram 打印`。

---

## 3. 逐段精讲

### 3.1 列表版线性代数工具

```python
def tanh(v):
    return [math.tanh(x) for x in v]


def tanh_grad(h):
    return [1 - x * x for x in h]


def matmul(W, x):
    return [sum(w * xi for w, xi in zip(row, x)) for row in W]
```

- `W` 用"行的列表"表示，形状 `[out_dim][in_dim]`，`matmul(W, x)` 对每一行做点积，得到长度为 `out_dim` 的列表，等价于 `W @ x`。
- `tanh_grad(h)` 的参数是**激活后的值** `h = tanh(z)`，利用 `tanh'(z) = 1 − tanh²(z) = 1 − h²`。这样反向传播时只需缓存激活值，不必再保存 `z`——这是手写 backprop 的常见省事写法。

### 3.2 网络初始化：一个 769 参数的小 MLP

```python
def randn_matrix(rows, cols, rng, scale=0.3):
    return [[rng.gauss(0, scale) for _ in range(cols)] for _ in range(rows)]


def init_net(in_dim, hidden, out_dim, rng):
    return {
        "W1": randn_matrix(hidden, in_dim, rng),
        "b1": [0.0] * hidden,
        "W2": randn_matrix(hidden, hidden, rng),
        "b2": [0.0] * hidden,
        "W3": randn_matrix(out_dim, hidden, rng),
        "b3": [0.0] * out_dim,
    }
```

- `main` 里用 `in_dim=5, hidden=24, out_dim=1`：参数量 = 24×5 + 24 + 24×24 + 24 + 1×24 + 1 = 769。
- 参数存进一个 `dict`，键名就是参数名。后面 `backward` / `apply` 都是遍历这个字典，所以加一层也只需改几处。
- `scale=0.3` 是手调的固定标准差。⚠️ 简化：生产中会用 Xavier / Kaiming 这类按扇入扇出缩放的初始化。

### 3.3 `forward`：速度场 `v_θ(x, t)` 与时间特征

```python
def forward(x, t, net):
    inp = [x, t, t * t, math.sin(2 * math.pi * t), math.cos(2 * math.pi * t)]
    pre1 = add(matmul(net["W1"], inp), net["b1"])
    h1 = tanh(pre1)
    pre2 = add(matmul(net["W2"], h1), net["b2"])
    h2 = tanh(pre2)
    out = add(matmul(net["W3"], h2), net["b3"])
    return out[0], {"inp": inp, "h1": h1, "h2": h2}
```

- 输入是 5 维：位置 `x` 加上 4 个时间特征。网络必须知道 `t`，因为同一个位置 `x` 在不同时间的最优速度完全不同（`t≈1` 时 `x` 基本是噪声，`t≈0` 时 `x` 基本是数据）。
- **为什么既有 `sin/cos` 又有 `t`、`t²`**：`sin(2πt)`、`cos(2πt)` 的周期为 1，`t=0` 和 `t=1` 时取值完全相同，单靠它们网络分不清"数据端"和"噪声端"。`t` 单调、`t²` 提供曲率，打破了这个歧义。真实模型（DiT、U-Net）用多频率的正弦时间嵌入来解决同样的问题。
- 返回值是二元组：标量输出 `out[0]` 和缓存字典 `cache`。缓存的是反向传播要用的激活值——这就是 PyTorch autograd 在背后替你保存的"计算图中间结果"。
- 输出层没有激活函数：速度可以是任意实数（代码实测在 ±2.6 量级），不能被 tanh 截断到 [−1, 1]。

### 3.4 `backward`：手写反向传播

```python
def backward(target, out, cache, net):
    grads = {k: None for k in net}
    for p in net:
        if isinstance(net[p][0], list):
            grads[p] = [[0.0] * len(net[p][0]) for _ in net[p]]
        else:
            grads[p] = [0.0] * len(net[p])
    d_out = 2 * (out - target)
    grads["b3"][0] += d_out
    for j in range(len(cache["h2"])):
        grads["W3"][0][j] += d_out * cache["h2"][j]
    d_h2 = [net["W3"][0][j] * d_out for j in range(len(cache["h2"]))]
    d_pre2 = [d_h2[j] * tanh_grad(cache["h2"])[j] for j in range(len(cache["h2"]))]
    # ... 第二层、第一层同理
    return grads
```

逐行对应链式法则：

| 代码 | 数学 |
|------|------|
| `d_out = 2 * (out - target)` | `∂(out − y)²/∂out` |
| `grads["W3"][0][j] += d_out * h2[j]` | `∂L/∂W3 = d_out · h2ᵀ` |
| `d_h2 = W3[0][j] * d_out` | `∂L/∂h2 = W3ᵀ · d_out` |
| `d_pre2 = d_h2 * (1 − h2²)` | 穿过 tanh |
| `d_h1[k] = Σ_j W2[j][k] · d_pre2[j]` | `∂L/∂h1 = W2ᵀ · d_pre2` |

- 先用 `isinstance(net[p][0], list)` 判断参数是矩阵（二维列表）还是向量（一维列表），分别建同形状的零梯度。
- 损失是**单样本平方误差** `(v_θ − (x₁ − x₀))²`——就是讲义的 CFM 损失，只是没有对 batch 求平均。
- ⚠️ 性能小坑：`tanh_grad(cache["h2"])[j]` 写在列表推导内部，每个 `j` 都重新算一遍整个列表，把 O(H) 变成了 O(H²)。H=24 时无所谓，但写法上应先 `g = tanh_grad(cache["h2"])` 再索引。
- ⚠️ 简化：没有梯度裁剪、没有数值梯度检查。手写 backprop 时，用有限差分 `(L(θ+ε) − L(θ−ε)) / 2ε` 对比一两个参数是最可靠的自检方法。

### 3.5 `apply`：原地 SGD

```python
def apply(net, grads, lr):
    for k, v in net.items():
        if isinstance(v[0], list):
            for i in range(len(v)):
                for j in range(len(v[i])):
                    v[i][j] -= lr * grads[k][i][j]
        else:
            for i in range(len(v)):
                v[i] -= lr * grads[k][i]
```

- `v` 是字典里列表的**引用**，`v[i][j] -= ...` 直接修改了 `net` 里的数据，所以函数不需要返回值。
- 纯 SGD、固定学习率 0.01、batch=1。⚠️ 简化：真实训练用 AdamW + warmup + 大 batch（skill 文件建议 Transformer 规模下 β₂=0.95）。batch=1 的梯度噪声很大，这也是学到的速度场不够精确的原因之一。

### 3.6 数据分布与训练循环：本节的核心

```python
def sample_data(rng):
    return rng.gauss(-2.0, 0.3) if rng.random() < 0.5 else rng.gauss(2.0, 0.3)


def train(net, steps, lr, rng):
    for _ in range(steps):
        x0 = sample_data(rng)
        x1 = rng.gauss(0, 1)
        t = rng.random()
        x_t = t * x1 + (1 - t) * x0
        target = x1 - x0
        pred, cache = forward(x_t, t, net)
        grads = backward(target, pred, cache, net)
        apply(net, grads, lr)
```

- 数据：两个窄高斯峰在 ±2，标准差 0.3，中间 `|x|<1` 的区域几乎没有数据。这种"中间是空地"的分布最能暴露少步采样的问题。
- 训练一步的四件事与讲义公式一一对应：
  1. `x0 ~ data`，`x1 ~ N(0,1)`，`t ~ U[0,1)`——三者**独立**采样（随机配对）。
  2. `x_t = t·x₁ + (1−t)·x₀`：直线插值，`t=0` 在数据端，`t=1` 在噪声端。
  3. `target = x₁ − x₀`：直线的时间导数，常数。
  4. 回归：`(v_θ(x_t, t) − target)²`。
- 注意整个循环里**没有任何 ODE 积分**，这就是 simulation-free。
- 为什么学到的流仍然弯：网络只看到 `(x_t, t)`，看不到 `x₀, x₁`。在 `t` 较大时，同一个 `x_t` 既可能来自左峰也可能来自右峰，平方损失的最优解是条件平均 `E[x₁ − x₀ | x_t]`，平均会让流场弯曲——这就是讲义说 rectified flow 要 reflow 的原因。

### 3.7 `sample`：Euler 积分

```python
def sample(net, num_steps, rng):
    x = rng.gauss(0, 1)
    dt = 1.0 / num_steps
    for i in range(num_steps):
        t = 1.0 - i * dt
        v, _ = forward(x, t, net)
        x -= dt * v
    return x
```

- 从 `x ~ N(0,1)`（`t=1`）出发，时间依次取 `1, 1−dt, …, dt`，每步 `x -= dt·v`，最终到达 `t=0`。
- 方向：`v` 指向"`t` 增大"（朝噪声），采样往 `t` 减小方向走，所以用减号。若训练目标写成 `x₀ − x₁`，这里就必须改成加号。
- **1 步时发生了什么**：只在 `t=1` 估一次速度，`x_final = x₁ − v(x₁, 1)`。`t=1` 时 `x_t = x₁` 与数据无关，最优速度是 `x₁ − E[x₀]`，于是 `x_final ≈ E[x₀] ≈ 0`——正好落在两峰之间。
- 每次调用只采 1 个标量样本，`main` 用列表推导调用 500 次。⚠️ 简化：真实实现会把一个 batch 的 `x` 放进张量一起前向。
- ⚠️ Euler 是一阶方法。路径弯曲时，常用 Heun（二阶）等高阶求解器在相同函数评估次数下获得更高精度。

### 3.8 `histogram`：ASCII 直方图

```python
def histogram(samples, lo=-5.0, hi=5.0, bins=30):
    width = (hi - lo) / bins
    counts = [0] * bins
    for s in samples:
        if lo <= s < hi:
            counts[int((s - lo) / width)] += 1
    peak = max(counts) or 1
    height = 6
    rows = []
    for r in range(height, 0, -1):
        thr = peak * r / height
        rows.append("".join("#" if c >= thr else " " for c in counts))
    rows.append("-" * bins)
    return "\n".join(rows)
```

- 30 个桶覆盖 [−5, 5)，每桶宽 1/3。`x=−2` 落在第 9 桶，`x=+2` 落在第 21 桶，`x=0` 落在第 15 桶——读图时可以用这几个位置定位。
- 每一行是一个阈值 `peak·r/6`，计数超过阈值就画 `#`，从上往下打印，形成"立着的"柱状图。
- `max(counts) or 1`：如果所有样本都越界、`counts` 全 0，`max` 为 0，`or 1` 让 `peak` 变成 1，避免后面阈值全为 0 时把每个桶都画满。

### 3.9 `main`：步数对比实验

```python
def main():
    rng = random.Random(31)
    net = init_net(in_dim=5, hidden=24, out_dim=1, rng=rng)

    print("=== training flow matching on two-mode mixture ===")
    train(net, steps=6000, lr=0.01, rng=rng)

    print()
    for num_steps in [1, 2, 4, 8, 20]:
        samples = [sample(net, num_steps, rng) for _ in range(500)]
        m = sum(samples) / len(samples)
        pos = sum(1 for s in samples if s > 0)
        # ... 打印直方图、均值、左右计数
```

- `random.Random(31)` 创建一个**独立的随机数生成器对象**，而不是用全局 `random.seed`。好处：所有随机性都从这一个对象出来，结果可复现，也不会被其他模块调用 `random` 干扰。
- 训练和采样共用同一个 `rng`，所以改变训练步数会连带改变采样时的随机序列。
- 统计量只有均值和"`x>0` 的个数"。⚠️ 这是很粗的指标：对称的中心单峰也会给出约 50/50。讲义练习 1 提到的"与真实分布比较 MSE"在代码里并没有实现。
- ⚠️ 最后打印的 "DDPM needs 20+ for similar quality in this toy" 只是一句结论陈述，脚本里并没有训练或运行 DDPM 来验证它。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 一维双峰数据 | 能用 ASCII 直方图一眼看出模式塌缩；中间空地最能暴露少步采样的问题 | 真实任务是 VAE 潜空间里的高维图像 latent |
| 手写 MLP + 手写 backprop | 证明 FM 只是普通回归，没有任何魔法 | 生产用 PyTorch autograd + DiT / U-Net |
| 时间特征 `[t, t², sin, cos]` | 小网络也能感知时间，且能区分 `t=0` 与 `t=1` | 多频率正弦嵌入 + MLP，或 adaLN 调制 |
| `t ~ U[0,1)` 均匀采样 | 最简单的 CFM 设置 | SD3 用 logit-normal 集中中段 `t` |
| batch=1 SGD、固定 lr | 代码最短 | AdamW、warmup、大 batch、EMA 权重 |
| 一阶 Euler 采样 | 与讲义公式一一对应；路径直时 Euler 足够 | Heun / DPM-Solver 等高阶求解器；或蒸馏到 1–4 步 |
| 只训练一次、不做 reflow | 聚焦 CFM 本身 | 需要 1–2 步时再做 reflow / consistency 蒸馏 |
| 用左右峰计数评估 | 打印简单 | 应使用分布距离（Wasserstein、FID 类指标） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 列表推导式 | `[math.tanh(x) for x in v]` | 一行生成新列表 |
| 嵌套列表推导 | `[[rng.gauss(0, scale) for _ in range(cols)] for _ in range(rows)]` | 生成二维列表；外层是行、内层是列 |
| `_` 占位变量 | `for _ in range(steps)` | 表示"循环变量用不到" |
| 生成器表达式 | `sum(w * xi for w, xi in zip(row, x))` | 不建中间列表，直接求和 |
| `zip` + 元组解包 | `for w, xi in zip(row, x)` | 两个列表按位置配对 |
| 列表乘法 | `[0.0] * hidden` | 创建定长的全零列表（元素是不可变的 float，所以安全） |
| 字典字面量与推导式 | `{"W1": ..., "b1": ...}`、`{k: None for k in net}` | 用名字管理参数 |
| `dict.items()` | `for k, v in net.items()` | 同时遍历键和值 |
| `isinstance` | `isinstance(net[p][0], list)` | 运行时区分矩阵与向量 |
| 多返回值（元组） | `return out[0], {"inp": inp, ...}`；`pred, cache = forward(...)` | 函数返回元组，调用方解包 |
| 条件表达式 | `rng.gauss(-2.0, 0.3) if rng.random() < 0.5 else rng.gauss(2.0, 0.3)` | 一行 if-else |
| 增量赋值与原地修改 | `v[i][j] -= lr * grads[k][i][j]`、`x -= dt * v` | 对列表元素原地修改会反映到原对象 |
| `or` 的短路取值 | `peak = max(counts) or 1` | 左边为假值（0）时取右边 |
| `range` 倒序 | `range(height, 0, -1)` | 从 6 数到 1 |
| `str.join` | `"".join("#" if c >= thr else " " for c in counts)` | 把字符序列拼成字符串 |
| f-string 格式符 | `f"mean {m:+.2f}"` | `+` 强制显示正负号，`.2f` 保留两位小数 |
| `random.Random(seed)` | `rng = random.Random(31)` | 独立、可复现的随机数生成器 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 2 秒）的关键输出：

```text
=== 1-step Euler integration ===
             #
             #
            ##
            #### ###
           #########
           ##########
------------------------------
mean +0.03, left mode = 258, right mode = 242

=== 2-step Euler integration ===
         #
         #
         #           ##
        ###         ###
        ###         ####
       #####     # ######
------------------------------
mean +0.22, left mode = 242, right mode = 258

=== 4-step Euler integration ===
                      #
                     ###
       ###           ###
       #####       #####
      #######      #######
    #########     #########
------------------------------
mean +0.20, left mode = 243, right mode = 257

=== 8-step Euler integration ===
...（双峰，形状与 4 步接近）
mean +0.28, left mode = 238, right mode = 262

=== 20-step Euler integration ===
        #                     
       ##             ##      
       ###          #####     
     # ####         #####     
     ######         ######    
     ######        ########   
------------------------------
mean +0.22, left mode = 239, right mode = 261

takeaway: straight-line flow matching lets Euler work at 4-8 steps.
          DDPM needs 20+ for similar quality in this toy.
```

逐段解读：

- **1 步**：`#` 集中在第 11–20 桶（约 x ∈ [−1.3, 2)），是一个**中心单峰**，而真实数据在第 9 桶和第 21 桶附近各有一个窄峰。这正是 3.7 节分析的"一步走到均值"。但左右计数 258/242 看起来很均衡——指标完全没发现问题。我另外用同样的种子统计过：1 步时约 60% 样本落在 `|x|<1`，20 步时只有约 1%。
- **2 步**：已经分出两个峰，但峰偏宽、中间仍有残留（第 17 桶附近的孤立 `#`）。第一步仍从 `t=1` 起步，走了半程后第二步的速度估计才开始"知道"该去哪个峰。
- **4 / 8 / 20 步**：都是清晰的双峰，形状相近，说明在这个玩具上 4 步已接近 20 步的质量——与讲义 "Expect the 4-step sampler to already match the 20-step quality" 一致。
- **峰比真实数据宽**：真实每个峰标准差只有 0.3（约 1 个桶宽），而 20 步结果左峰横跨第 5–10 桶、右峰横跨第 19–26 桶（6–8 个桶）。这是小网络 + batch=1 SGD + 6000 步训练的拟合误差，不是采样步数的问题——再多步也不会变窄。
- **均值略偏正（+0.2 左右）**：样本中右峰略多（约 52%），属于有限样本 + 不完美模型的正常偏差。

---

## 7. 动手改一改

1. **加一个真正的分布指标**：对生成样本和 500 个真实样本分别排序，算一维 Wasserstein-1 距离 `mean(|sorted_gen − sorted_real|)`，打印每个步数的值，验证"1 步最差、4 步接近 20 步"。
2. **logit-normal 时间采样**：把 `train` 里的 `t = rng.random()` 换成 `t = 1/(1+math.exp(-rng.gauss(0, 1)))`，比较各步数的指标变化（讲义练习 2）。
3. **删掉时间特征里的 `t` 和 `t*t`**：只保留 `sin/cos`，观察 1 步和 20 步结果怎么变，验证"`t=0` 与 `t=1` 无法区分"的分析。
4. **Heun 二阶采样**：每步先用 `v(x, t)` 走一个 Euler 预测 `x̃`，再算 `v(x̃, t−dt)`，用两者平均做真正的更新；在相同函数评估次数下与 Euler 对比。
5. **一次 reflow**（讲义练习 3）：用训练好的模型以 20 步把 2000 个 `x₁` 积分成 `x₀`，在这些配对上训练第二个模型（训练循环中 `(x₀, x₁)` 从配对里取），对比 1 步采样的直方图。
6. **改成 mini-batch**：每步采 32 个样本、累加梯度后取平均再更新，观察峰宽是否变窄、训练是否更稳。

---

## 8. 常见坑

- **采样符号写反**：目标是 `x₁ − x₀` 时采样必须 `x -= dt·v`；从别的代码库搬来的模型可能用相反约定（`t=0` 为噪声），符号和时间方向都要对齐。
- **时间网格的 off-by-one**：本代码在 `t = 1, 1−dt, …, dt` 处评估速度，从不在 `t=0` 处评估。若误写成 `t = 1 − (i+1)·dt`，第一步就会在错误的时间点估速度。
- **把"左右计数均衡"当成"分布正确"**：1 步结果是中心单峰，却给出 258/242。生成模型评估要看分布，不能只看某个统计量。
- **以为 FM 一步就能出图**：随机配对训练的流是弯的，1 步会塌到均值；1–2 步需要 reflow 或蒸馏。
- **时间嵌入无法区分两端**：只用周期为 1 的 `sin/cos(2πt)` 时，`t=0` 和 `t=1` 的编码相同。
- **在列表推导中重复计算**：`tanh_grad(cache["h2"])[j]` 每次迭代都重算整个列表，小网络无感，规模一大就是隐蔽的 O(H²)。
