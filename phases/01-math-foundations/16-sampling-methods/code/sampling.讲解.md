# 代码讲解 · sampling.py

> **所属小节**：阶段 01 · 数学基础 · 第 16 节 Sampling 方法 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 sampling.py`（无命令行参数，约 3 秒；会在**当前目录**生成 `sampling_methods.png`） ｜ **依赖**：Python 标准库（`math`、`random`）；`matplotlib` 可选，只用于第 14 部分画图，没装时自动跳过

---

## 1. 这份代码在考察什么

讲义的主线是"所有采样方法都从一个均匀随机数出发"。这份代码只用 `random.random()`（以及少量 `random.gauss/uniform`），把 AI 中最常见的采样方法全部手写一遍：

1. **把均匀分布变成任意分布**：逆 CDF（指数分布）、Box-Muller（正态分布）、离散分布的累积和查找。
2. **采不到就"换个分布采"**：拒绝采样（要样本）与重要性采样（只要期望）的区别和代价。
3. **用随机数算积分**：蒙特卡洛估计 π 和定积分、分层采样降低方差。
4. **从只知道"形状"的分布采样**：Metropolis-Hastings 和 Gibbs 这两种 MCMC。
5. **LLM 解码的三个旋钮**：温度、top-k、top-p，以及完整的文本生成演示。
6. **让采样可微**：VAE 的重参数化技巧、Gumbel-Max / Gumbel-Softmax / straight-through。

> 一句话：**每一个生成式 AI 系统都是一个采样系统**——这份代码让你看清 `model.generate(temperature=0.7, top_p=0.9)` 和 `torch.randn_like(std)` 背后在做什么。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `sample_uniform` / `sample_exponential_inverse_cdf` / `verify_inverse_cdf` | 函数 | 均匀采样、逆 CDF 采样及验证 | 逆变换采样 |
| `normal_pdf` / `sample_normal_box_muller` | 函数 | 正态密度、Box-Muller 正态采样 | 基础分布 |
| `rejection_sample` / `rejection_sample_batch` / `truncated_normal_demo` | 函数 | 拒绝采样、批量统计接受率、截断正态示例 | 拒绝采样 |
| `importance_sampling_estimate` / `importance_sampling_demo` | 函数 | 普通与自归一化重要性采样 | 重要性采样 |
| `monte_carlo_pi` / `monte_carlo_integral` | 函数 | 估计 π 和定积分 | 蒙特卡洛 |
| `metropolis_hastings` / `metropolis_hastings_2d` / `bimodal_log_pdf` | 函数 | 1D/2D 随机游走 Metropolis，双峰目标 | MCMC |
| `gibbs_sampling_2d` | 函数 | 相关二维正态的 Gibbs 采样 | Gibbs |
| `softmax` / `sample_from_probs` | 函数 | 数值稳定的 softmax、离散分布采样 | 类别分布 |
| `temperature_*` / `top_k_*` / `top_p_*` | 函数（各有 `_sample` 与 `_distribution` 两版） | 解码策略：采一个 token / 返回过滤后的分布 | LLM 解码 |
| `reparam_sample` / `reparam_gradient` / `vae_forward_demo` | 函数 | 重参数化采样及其梯度 | VAE |
| `gumbel_sample` / `gumbel_max_sample` / `gumbel_softmax_sample` / `gumbel_softmax_straight_through` | 函数 | Gumbel 噪声与可微类别采样 | Gumbel-Softmax |
| `stratified_sample_1d` / `compare_sampling_variance` | 函数 | 分层采样及方差对比 | 方差缩减 |
| `text_generation_demo` | 函数 | 用不同解码方法生成"句子" | 解码策略对比 |
| `if __name__ == "__main__":` | 演示入口 | 13 个数值演示 + 第 14 部分 3×3 可视化 | — |

调用关系：几乎所有采样器都建立在 `random.random()` 之上；解码相关函数共享 `softmax` 和 `sample_from_probs`；`rejection_sample_batch` 调 `rejection_sample`；`vae_forward_demo` 调 `reparam_sample`；`gumbel_softmax_*` 调 `gumbel_sample` 和 `softmax`。

---

## 3. 逐段精讲

> 文件较大（约 25KB），下面聚焦核心算法；主程序中的打印与绘图只挑关键处说明。

### 3.1 逆 CDF 与 Box-Muller：从均匀分布出发

```python
def sample_exponential_inverse_cdf(lam):
    u = random.random()
    return -math.log(u) / lam
```

- 指数分布 `F(x) = 1 − e^(−λx)`，反解得 `x = −ln(1−u)/λ`；因为 `1 − U` 与 U 同分布，直接写成 `−ln(u)/λ`。
- `verify_inverse_cdf` 采 10000 个样本，比较样本均值和理论均值 1/λ——"用统计量验证采样器"是测试随机代码的基本方法。
- ⚠️ `random.random()` 的取值范围是 `[0, 1)`，理论上可能返回 0.0，`math.log(0)` 会抛 `ValueError`。概率极小（约 2⁻⁵³），但同文件的 `gumbel_sample` 和 MH 都做了防御，这里没做。

```python
def sample_normal_box_muller(mu=0.0, sigma=1.0):
    u1 = random.random()
    u2 = random.random()
    z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
    return mu + sigma * z
```

- 正态分布的 CDF 没有闭式逆，所以用 Box-Muller：两个均匀数 → 一个标准正态数（另一个 `sin` 分量被丢弃，上一节 `statistics.py` 的版本则两个都用了）。
- `mu + sigma * z` 就是"标准正态 → 任意正态"的平移缩放，**和重参数化技巧完全是同一个式子**（见 3.9）。

### 3.2 拒绝采样：接受率与包络常数 M

```python
def rejection_sample(target_pdf, proposal_sample, proposal_pdf, M):
    attempts = 0
    while True:
        x = proposal_sample()
        u = random.random()
        attempts += 1
        if u < target_pdf(x) / (M * proposal_pdf(x)):
            return x, attempts
```

- 逐行对应讲义算法：从 q 采 x → 采 u → 若 `u < p(x)/(M·q(x))` 则接受，否则重来。`while True` + `return` 是"直到成功为止"的标准写法。
- 额外返回 `attempts`，让 `rejection_sample_batch` 统计接受率 `n / total_attempts`——把算法的"效率"也变成可观测的量。
- 采样器、密度都作为**函数参数**传入，同一个函数可以用于任何目标分布。

截断正态的例子：

```python
def truncated_normal_demo(mu, sigma, a, b, n=5000):
    norm_const = sum(
        normal_pdf(a + (b - a) * i / 1000, mu, sigma) * (b - a) / 1000
        for i in range(1001)
    )
    M_val = max(
        normal_pdf(x, mu, sigma) / (1.0 / (b - a))
        for x in [a + (b - a) * i / 200 for i in range(201)]
    )

    def target(x):
        if a <= x <= b:
            return normal_pdf(x, mu, sigma)
        return 0.0
    # ...
```

- 提议是区间上的均匀分布，`M` 取"目标/提议"在网格上的最大值。`target`、`proposal`、`proposal_pdf` 都是定义在函数内部的**闭包**，自动"记住"了外层的 `a, b, mu, sigma`。
- 实测接受率 0.6824，而 `1/M ≈ 0.836`。原因：`target` 用的是**没有按截断区间重新归一化**的正态密度，它在 [−1, 2] 上的总质量只有 `Z ≈ 0.8186`，一般公式是"接受率 = Z/M ≈ 0.684"。讲义的"接受率 = 1/M"默认 p 已归一化。
- ⚠️ `norm_const` 恰好就是这个 Z 的数值积分，但算完**没有被使用**，属于死代码。
- ⚠️ 网格上的最大值可能略低于真实最大值（x = 0 不在 201 点网格上），M 被轻微低估时，峰值附近 `p/(M·q) > 1` 的部分会被截断，带来微小偏差。稳妥做法是解析求最大值或乘一个安全系数。

### 3.3 重要性采样：一次循环得到两种估计

```python
def importance_sampling_estimate(f, target_pdf, proposal_pdf, proposal_sample, n):
    weighted_sum = 0.0
    weight_sum = 0.0
    for _ in range(n):
        x = proposal_sample()
        w = target_pdf(x) / proposal_pdf(x)
        weighted_sum += f(x) * w
        weight_sum += w
    unnormalized = weighted_sum / n
    self_normalized = weighted_sum / weight_sum
    return unnormalized, self_normalized
```

- 普通估计 `(1/N)Σ f·w`：无偏，但需要 p、q 都是归一化密度。
- 自归一化估计 `Σ f·w / Σ w`：分母也是随机的，所以有偏但相合；好处是 p 只需知道到常数倍，而且当权重整体偏大或偏小时会自动抵消，通常更稳定。
- 演示：目标 `N(2, 1)`，提议 `Uniform(−3, 7)`（覆盖 μ ± 5σ），估计 `E[X²] = μ² + σ² = 5`。两种估计分别得到 4.9921 和 5.0120。
- ⚠️ 提议是有界区间，区间外 `proposal_pdf = 0`，但区间外永远采不到样本，所以不会除以 0；代价是区间外的那部分目标质量（这里约 6×10⁻⁷）被忽略。重要性采样要求 **q 在 p 非零处也非零**，否则估计有偏。

### 3.4 蒙特卡洛：估计 π 和积分

```python
def monte_carlo_integral(f, a, b, n):
    total = 0.0
    for _ in range(n):
        x = sample_uniform(a, b)
        total += f(x)
    return (b - a) * total / n
```

- `∫f dx ≈ (b − a) · mean(f(xᵢ))`，即"区间长度 × 平均高度"。`monte_carlo_pi` 则是"落在单位圆内的比例 × 正方形面积 4"。
- 误差 `O(1/√N)`，与维度无关。但单次运行的误差是随机的：真实输出中 N = 10000 的误差（0.0086）比 N = 1000（0.0060）还大——要验证收敛速度必须重复多次求 RMSE（测验 Q12）。

### 3.5 Metropolis-Hastings：对数空间里的接受判断

```python
def metropolis_hastings(target_log_pdf, x0, n_samples, burn_in, proposal_std=1.0):
    samples = []
    x = x0
    accepted = 0
    total = n_samples + burn_in

    for i in range(total):
        x_new = x + random.gauss(0, proposal_std)
        log_alpha = target_log_pdf(x_new) - target_log_pdf(x)

        if math.log(random.random() + 1e-300) < log_alpha:
            x = x_new
            if i >= burn_in:
                accepted += 1

        if i >= burn_in:
            samples.append(x)

    acceptance_rate = accepted / n_samples
    return samples, acceptance_rate
```

- 提议是以当前点为中心的高斯随机游走，**对称**（`q(x'|x) = q(x|x')`），Hastings 修正项约掉，只剩 `p(x')/p(x)`——这其实是原始的 Metropolis 算法。讲义 Build It 中的通用版本多了 `proposal_log_pdf` 两项。
- 全程使用**对数密度**：`log u < log p(x') − log p(x)`。密度值可能小到下溢，对数相减既稳定又省掉了除法；`+ 1e-300` 防止 `log(0)`。
- 被拒绝时 `x` 保持不变，但**仍然把当前 x 记入样本**——这一点很关键，重复的样本正是 MCMC 正确性的一部分；只记录被接受的点会让分布出错。
- 前 `burn_in` 步既不记录样本也不计入接受率。
- 双峰目标 `bimodal_log_pdf` 是 `0.4·N(−3,1) + 0.6·N(3,1)`，真实均值 0.6、标准差约 3.10。步长 0.5 时接受率 0.84 但均值偏到 0.97（跨峰太少），步长 3.0 时接受率 0.44 而均值 0.67——**高接受率不等于好的混合**。
- `metropolis_hastings_2d` 从远离中心的 (5, 5) 出发，用来展示 burn-in 的作用：丢弃前 2000 步后，均值回到 (0.05, 0.03) 附近。

### 3.6 Gibbs 采样：轮流从条件分布采样

```python
def gibbs_sampling_2d(rho, n_samples, burn_in):
    x, y = 0.0, 0.0
    samples = []

    for i in range(n_samples + burn_in):
        x = random.gauss(rho * y, math.sqrt(1 - rho ** 2))
        y = random.gauss(rho * x, math.sqrt(1 - rho ** 2))
        if i >= burn_in:
            samples.append((x, y))

    return samples
```

- 目标是相关系数为 ρ 的标准二维正态。它的条件分布有闭式：`x | y ~ N(ρy, 1 − ρ²)`，`y | x ~ N(ρx, 1 − ρ²)`。
- 注意更新 y 时用的是**刚更新过的** x——这就是讲义公式里 `x₁^{t+1}`、`x₂^{t+1}` 的上标含义。
- 没有接受/拒绝步骤：从精确条件分布采样自动满足细致平衡，接受率恒为 1。
- ρ 越接近 1，条件方差 `1 − ρ²` 越小，每一步只能挪一点点，混合越慢（讲义"Limitation"）。
- 主程序中打印的 "empirical correlation" 实际算的是 `E[xy] − E[x]E[y]`（协方差）；因为两个边缘分布的方差都是 1，协方差 ≈ 相关系数，所以数值上可以这样用。

### 3.7 softmax 与离散采样：所有解码策略的底座

```python
def softmax(logits):
    max_l = max(logits)
    exps = [math.exp(z - max_l) for z in logits]
    total = sum(exps)
    return [e / total for e in exps]


def sample_from_probs(probs):
    r = random.random()
    cumsum = 0.0
    for i, p in enumerate(probs):
        cumsum += p
        if r <= cumsum:
            return i
    return len(probs) - 1
```

- softmax 先减去最大值：数学上结果不变，但避免了 `exp(1000)` 溢出（第 13 节数值稳定性的经典技巧）。温度很低时 `z/T` 会很大，这一步尤其重要。
- `sample_from_probs` 是**离散版的逆 CDF**：累加概率，找到第一个累计和超过 r 的位置。复杂度 O(V)。
- 最后的 `return len(probs) - 1` 是防御：浮点累加可能让总和是 0.9999999999，而 r 恰好落在缝隙里。
- ⚠️ 用 `r <= cumsum` 时，如果开头几个 token 的概率恰好为 0 且 r 恰好等于 0.0，会选中概率为 0 的 token；改成 `r < cumsum` 更严谨（发生概率极低）。

### 3.8 温度、top-k、top-p：采样版与分布版

```python
def temperature_sample(logits, temperature):
    if temperature <= 0:
        return logits.index(max(logits))
    scaled = [z / temperature for z in logits]
    probs = softmax(scaled)
    return sample_from_probs(probs)
```

- `temperature <= 0` 特殊处理为贪心（argmax），否则会除以 0。这与 API 中"temperature=0 表示贪心"的约定一致。

```python
def top_k_sample(logits, k):
    indexed = sorted(enumerate(logits), key=lambda x: -x[1])
    top = indexed[:k]
    top_logits = [l for _, l in top]
    probs = softmax(top_logits)
    idx = sample_from_probs(probs)
    return top[idx][0]
```

- 按 logit 从大到小排序后取前 k 个，**只对这 k 个 logit 做 softmax**。这与"先对全部做 softmax、再把前 k 个概率重新归一化"（`top_k_distribution` 的写法）数学上完全等价，因为 softmax 的分母会在重新归一化时约掉。
- `top[idx][0]` 把"在 top-k 子集中的位置"映射回"词表中的原始下标"——这是很容易写错的一步。
- 完整排序是 O(V log V)；生产中用部分排序（如 `torch.topk`）。

```python
def top_p_sample(logits, p):
    probs = softmax(logits)
    indexed = sorted(enumerate(probs), key=lambda x: -x[1])
    cumsum = 0.0
    selected = []
    for token_idx, prob in indexed:
        cumsum += prob
        selected.append((token_idx, prob))
        if cumsum >= p:
            break
    # ... 重新归一化后采样，再映射回原始下标
```

- 先 `append` 再判断 `cumsum >= p`，保证**跨过阈值的那个 token 也被保留**，得到"累计概率 ≥ p 的最小集合"。如果先判断再 append，就会少一个 token，p 很小时甚至得到空集合。
- 每种方法都有 `_sample`（采一个下标）和 `_distribution`（返回过滤后的完整分布）两个版本：前者用于生成，后者是**确定性**的，便于打印、画图和写单元测试。
- 演示中 `p=0.50` 只保留 1 个 token（0.5889 一个就够了），`p=0.95` 保留 4 个：候选数随分布形状变化，这就是 nucleus 采样"自适应"的含义。

### 3.9 重参数化技巧：用链式法则穿过采样

```python
def reparam_sample(mu, sigma):
    epsilon = random.gauss(0, 1)
    z = mu + sigma * epsilon
    return z, epsilon


def vae_forward_demo(mu, log_var):
    sigma = math.exp(0.5 * log_var)
    z, epsilon = reparam_sample(mu, sigma)

    dz_dmu = 1.0
    dz_dsigma = epsilon
    dsigma_dlogvar = 0.5 * sigma

    dz_dmu_total = dz_dmu
    dz_dlogvar = dz_dsigma * dsigma_dlogvar

    return z, epsilon, dz_dmu_total, dz_dlogvar
```

- 把随机性全部放进 ε，z 就成了 μ、σ 的确定函数：`∂z/∂μ = 1`，`∂z/∂σ = ε`。
- VAE 编码器输出的是 `log_var`（保证 σ = exp(½·log_var) > 0，且数值稳定），所以还要多乘一层 `∂σ/∂log_var = ½σ`——这就是**链式法则**。
- 返回 ε 很重要：反向传播时需要用到这次前向抽到的同一个 ε。
- 这里的导数是手写的，没有自动微分；在 PyTorch 中，同样的事情就是 `z = mu + torch.exp(0.5 * log_var) * torch.randn_like(mu)`，梯度会自动流回 `mu` 和 `log_var`。
- ⚠️ `reparam_gradient(epsilon)` 定义了但主程序没有调用（`vae_forward_demo` 里重新写了一遍）。
- ⚠️ 演示只抽了 5 次，`Mean of z samples: 2.9195 (expected ~2.0)` 看起来偏差不小，但 σ ≈ 1.28，5 个样本均值的标准误约 0.57，偏差在 2 个标准误以内；紧接着的 10000 次对比（均值 1.99、标准差 1.28）才是可靠的验证。

### 3.10 Gumbel-Max 与 Gumbel-Softmax

```python
def gumbel_sample():
    u = random.random()
    while u == 0:
        u = random.random()
    return -math.log(-math.log(u))


def gumbel_max_sample(log_probs):
    gumbels = [lp + gumbel_sample() for lp in log_probs]
    return gumbels.index(max(gumbels))


def gumbel_softmax_sample(log_probs, temperature):
    gumbels = [lp + gumbel_sample() for lp in log_probs]
    scaled = [g / temperature for g in gumbels]
    return softmax(scaled)
```

- `−log(−log u)` 就是 Gumbel(0,1) 分布的逆 CDF 采样（又是逆 CDF！）。`while u == 0` 防止 `log(0)`。
- **Gumbel-Max**：给每个对数概率加独立 Gumbel 噪声后取 argmax，得到的就是**精确**的类别样本。演示中 10000 次的频率与真实概率误差都在 0.006 以内。
- **Gumbel-Softmax**：把不可微的 argmax 换成带温度 τ 的 softmax。τ = 0.1 时输出几乎是 one-hot，τ = 5 时接近均匀。
- 输入参数叫 `log_probs`，传入的应该是对数概率（或 logits，二者只差一个常数，加到所有分量上不影响 argmax/softmax）。⚠️ 讲义 Build It 第 10 步的示例函数写成 `gumbel_softmax(logits, temperature)`，里面却又对 `logits` 取了一次 `math.log`——对真正的 logits 这样做是错的（logits 可以为负，会直接报错）；本代码文件的写法是正确的。
- `gumbel_softmax_straight_through` 返回 `(hard, soft)`：前向用 hard one-hot，反向用 soft 的梯度。这里只是把两个向量都算出来示意，真正的"前向用 A、反向用 B"需要自动微分框架（常见写法是 `hard - soft.detach() + soft`）。

### 3.11 分层采样与方差对比

```python
def stratified_sample_1d(n):
    samples = []
    for i in range(n):
        u = random.random()
        samples.append((i + u) / n)
    return samples
```

- 把 [0, 1) 等分为 n 层，第 i 层内取 `(i + u)/n`，保证每层恰好一个点，不会出现"扎堆"和"空洞"。
- `compare_sampling_variance` 对 `sin(πx)` 各做 200 次估计，比较两种方法估计值的方差。结果显示比值从 N=10 的 20 倍增长到 N=100 的 2671 倍：普通 MC 方差按 `1/N` 下降，分层采样对光滑函数约按 `1/N³` 下降。

### 3.12 文本生成演示：`**kwargs` 分派

```python
def text_generation_demo(vocab, logits, length, method, **kwargs):
    tokens = []
    for _ in range(length):
        if method == "greedy":
            idx = logits.index(max(logits))
        elif method == "temperature":
            idx = temperature_sample(logits, kwargs.get("temperature", 1.0))
        elif method == "top_k":
            idx = top_k_sample(logits, kwargs.get("k", 5))
        elif method == "top_p":
            idx = top_p_sample(logits, kwargs.get("p", 0.9))
        else:
            idx = sample_from_probs(softmax(logits))
        tokens.append(vocab[idx])
    return " ".join(tokens)
```

- 用字符串 `method` 选择策略，`**kwargs` 接收各策略自己的参数，`kwargs.get(..., 默认值)` 取值。调用处用 `**params` 把字典展开成关键字参数。
- ⚠️ 这是一个**简化**：每一步都用同一组固定 logits，下一个 token 不依赖前文，所以生成的只是"独立同分布的词序列"，而不是真正的自回归生成。真实 LLM 每一步都要把已生成的 token 喂回模型、得到新的 logits。
- 主程序用 `len(set(sequences))` 统计 3 次运行中不同序列的个数：贪心永远 1/3，其余方法 3/3。

### 3.13 可视化：可选依赖的写法

```python
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        # ... 3×3 子图：指数分布、截断正态、MC 求 π、MCMC 双峰、Gibbs、温度、top-k vs top-p、Gumbel-Softmax、分层采样
        plt.savefig("sampling_methods.png", dpi=150)
    except ImportError:
        print("  matplotlib not available, skipping visualization.")
```

- 把可选依赖的 `import` 放在 `try` 里，没装 matplotlib 也能跑完前 13 部分。
- `matplotlib.use("Agg")` 选择无界面的后端，在服务器 / 无显示器环境里也能保存图片。
- 图片保存到**当前工作目录**，所以最好在代码副本或单独的输出目录中运行，避免把生成文件混进源码目录。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用 `random.random()` 搭建一切 | 展示"均匀分布是所有采样的起点" | 慢；生产用 `numpy.random.Generator`、`torch.distributions` |
| 模块级 `random.seed(42)` | 结果可复现 | 各演示共享随机流，改一处影响后续全部结果；生产中每个组件用独立的随机数生成器 |
| 拒绝采样返回尝试次数 | 让接受率可观测 | 多一个返回值 |
| MCMC 在对数空间计算 | 防止密度下溢，数值稳定 | 需要提供对数密度 |
| 随机游走 Metropolis（对称提议） | 最简单，省掉 Hastings 修正 | 高维、多峰时混合慢；生产用 HMC/NUTS（PyMC、NumPyro） |
| 每种解码策略都有 `_sample` 与 `_distribution` 两版 | 分布版确定、可测试、可画图 | 少量重复代码 |
| 完整排序实现 top-k / top-p | 简单直观 | O(V log V)；生产用部分排序并在 GPU 上批量执行 |
| 重参数化的导数手写 | 看清链式法则 | 生产中交给自动微分 |
| 文本生成使用固定 logits | 聚焦采样策略本身 | 不是真正的自回归生成 |
| matplotlib 作为可选依赖 | 核心逻辑零依赖 | 图片写到当前目录 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def sample_normal_box_muller(mu=0.0, sigma=1.0)`、`proposal_std=1.0` | 不传时使用默认值 |
| 列表推导式 | `[math.exp(z - max_l) for z in logits]` | 一行生成新列表 |
| 生成器表达式 | `sum(normal_pdf(...) * (b - a) / 1000 for i in range(1001))`、`max(... for x in [...])` | 直接喂给 `sum/max`，不建中间列表 |
| `while True` + `return` | `rejection_sample` | "直到满足条件为止"的循环 |
| 返回元组与解包 | `return x, attempts`；`x, attempts = rejection_sample(...)`；`x, y = x_new, y_new` | 一次返回/赋值多个值 |
| 函数作为参数 | `rejection_sample(target_pdf, proposal_sample, proposal_pdf, M)` | 算法与具体分布解耦 |
| 嵌套函数 / 闭包 | `truncated_normal_demo` 内的 `target`、`proposal`；主程序里的 `gaussian_2d_log_pdf`、`test_fn` | 内部函数能读取外层变量（如 `a, b`） |
| `sorted` + `enumerate` + `lambda` | `sorted(enumerate(logits), key=lambda x: -x[1])` | 按值降序排序并保留原下标 |
| `list.index` + `max` | `logits.index(max(logits))` | 取 argmax（并列时取第一个） |
| 用 `_` 忽略元素 | `[l for _, l in top]` | 解包时丢弃不需要的部分 |
| `**kwargs` 与 `dict.get` | `def text_generation_demo(..., **kwargs)`、`kwargs.get("k", 5)` | 收集任意关键字参数，带默认值取用 |
| 字典展开调用 | `text_generation_demo(..., method=method_name, **params)` | 把字典展开成关键字参数 |
| `if/elif/else` 分派 | `if method == "greedy": ... elif ...` | 按字符串选择分支 |
| 条件表达式 | `std_var / strat_var if strat_var > 0 else float('inf')` | 一行 if/else，避免除以 0 |
| `set` 去重计数 | `len(set(sequences))` | 统计不同元素个数 |
| 字符串方法 | `" ".join(tokens)`、`', '.join(formatted)` | 用分隔符拼接字符串列表 |
| f-string 格式符 | `f"{n:>7d}"`、`f"{p:.4f}"`、`f"T={temp:.1f}"` | 右对齐宽度 7 的整数；4 位小数 |
| 嵌套 f-string | `f"[{', '.join(f'{p:.4f}' for p in empirical)}]"` | 外层双引号、内层单引号，里面还能放生成器 |
| `random` 模块 | `random.random()`、`random.uniform(-1, 1)`、`random.gauss(0, 1)`、`random.seed(42)` | `[0,1)` 均匀数、区间均匀数、正态数、固定种子 |
| `try` / `except ImportError` | 可视化部分 | 可选依赖缺失时优雅降级 |
| 块内 `import` | `import matplotlib` 写在 `try` 里 | 只在需要时导入 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行演示 |

---

## 6. 运行结果解读

已在临时目录实际运行（Python 3.13 + matplotlib 3.11，约 2.5 秒，生成了 `sampling_methods.png`）。关键输出：

```text
  Exponential(lambda=0.5): empirical mean=1.9887, theoretical=2.0000   ← 逆 CDF 正确
  Truncated N(0,1) on [-1, 2]: mean=0.2266, acceptance rate=0.6824     ← 理论均值约 0.230，接受率 = Z/M ≈ 0.684
    Unnormalized IS: 4.9921
    Self-normalized IS: 5.0120          ← 理论值 5 = μ² + σ²
    N= 100000: pi ~ 3.141240, error=0.000353
    N=  10000: estimate=1.991409, error=0.008591   ← 比 N=1000 的误差还大：单次运行有随机性
```

```text
    proposal_std=0.5: mean=0.9712, std=3.0384, acceptance=0.8448   ← 接受率高，但跨峰少，均值偏
    proposal_std=3.0: mean=0.6730, std=3.0971, acceptance=0.4401   ← 最接近真实值 0.6 / 3.10
    mean_x=0.0468, mean_y=0.0250, acceptance=0.5617               ← 从 (5,5) 出发，burn-in 后回到原点附近
  rho=0.9: empirical correlation=0.9038                            ← Gibbs 恢复了设定的相关性
```

```text
  T=0.1: [1.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000]   ← 几乎是贪心
  T=1.0: [0.5889, 0.2166, 0.1314, 0.0483, 0.0108, 0.0040]   ← 原始 softmax
  T=3.0: [0.3115, 0.2232, 0.1889, 0.1354, 0.0821, 0.0588]   ← 接近均匀
  k=3: [0.6285, 0.2312, 0.1402, 0.0000, 0.0000, 0.0000]     ← 前 3 个重新归一化
  p=0.50: [1.0000, ...] (1 tokens)
  p=0.90: [0.6285, 0.2312, 0.1402, 0.0000, ...] (3 tokens) ← 恰好与 top-3 相同
  p=0.95: [0.5977, 0.2199, 0.1334, 0.0491, 0.0000, 0.0000] (4 tokens)
```

```text
    Trial 1: z=2.5542, eps=0.4316, dz/dmu=1.0000, dz/dlog_var=0.2771   ← 0.5 × 1.284 × 0.4316 ≈ 0.277
    Direct:  mean=1.9914, std=1.2824
    Reparam: mean=1.9922, std=1.2772    ← 两种方式得到同一个分布 N(2, e^0.5)，σ = e^0.25 ≈ 1.284
    Empirical: [0.5014, 0.2948, 0.1558, 0.0480]   ← Gumbel-Max 与真实概率一致
    tau=0.1: [1.0000, 0.0000, 0.0000, 0.0000] -> cat
    tau=5.0: [0.3563, 0.2260, 0.2231, 0.1946] -> cat   ← τ 大时接近均匀
```

```text
    N= 10: standard_var=0.00986030, stratified_var=0.00048323, ratio=20.41x
    N=100: standard_var=0.00098553, stratified_var=0.00000037, ratio=2671.44x
  greedy:      Unique sequences: 1/3
  top_k(k=3):  Run 1: the the cat cat the the cat cat   ← 只会出现 the / cat / sat
  top_p(p=0.8):  Unique sequences: 3/3
```

普通 MC 在 N = 10 时方差 0.00986，正好约等于 `Var(sin πx)/N = 0.0947/10`，与理论吻合。

---

## 7. 动手改一改

1. 实现 Cauchy 分布的逆 CDF 采样 `x = tan(π(u − 0.5))`，观察样本均值随 N 增大是否收敛（提示：不会，Cauchy 没有均值，这也是 CLT 失效的例子）——讲义练习 1。
2. 用 `Uniform(0,1)` 作提议，对 Beta(2, 5) 做拒绝采样，计算理论接受率（M 取 Beta(2,5) 密度在众数 0.2 处的值 ≈ 2.458，接受率 ≈ 0.407）并与实测对比——讲义练习 2。
3. 在 `importance_sampling_estimate` 中增加有效样本量 `ESS = (Σw)²/Σw²` 的输出；把提议改成 `Uniform(−20, 30)`，观察 ESS 和估计值的变化。
4. 给 `metropolis_hastings` 增加一个参数，返回整条链（包括 burn-in），用 matplotlib 画出不同 `proposal_std` 下的 trace plot，直观看到"困在一个峰里"。
5. 实现 `filtered_distribution(logits, temperature, top_k, top_p)`，把三种策略组合起来（测验 Q11），并给它写几条断言式单元测试。
6. 把 `text_generation_demo` 改成"真正的"自回归：用一个二元组表 `next_logits[prev_token]` 决定下一步的 logits，比较不同解码策略生成句子的流畅度。

---

## 8. 常见坑

- **温度为 0 时除以 0**：必须像 `temperature_sample` 一样单独处理为贪心。
- **top-k / top-p 下标映射错误**：在排序后的子集里采样得到的是子集位置，必须映射回词表原始下标（`top[idx][0]`、`selected[idx][0]`）。
- **top-p 漏掉跨阈值的 token**：先判断再追加会少一个 token，p 小时甚至得到空集合。
- **MCMC 只记录被接受的样本**：被拒绝时也要重复记录当前状态，否则分布是错的；另外不要忘记 burn-in。
- **用接受率判断 MCMC 好坏**：接受率高可能只是步子太小；多峰分布要看 trace plot 或多条链。
- **对 logits 再取一次 log**：Gumbel 技巧的输入是对数概率或 logits，不要再 `math.log`（讲义 Build It 第 10 步的示例代码就有这个问题）。
- **在源码目录里直接运行**：脚本会在当前目录写入约 600KB 的 `sampling_methods.png`。
