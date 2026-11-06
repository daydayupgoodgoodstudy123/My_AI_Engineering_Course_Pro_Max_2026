# 代码讲解 · stochastic.py

> **所属小节**：阶段 01 · 数学基础 · 第 22 节 随机过程 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python stochastic.py`（无命令行参数，不写文件，约 4 秒跑完） ｜ **依赖**：`numpy`

---

## 1. 这份代码在考察什么

这份文件约 280 行，把讲义的"四个基础随机过程 + 扩散模型前向过程"各实现成一个函数，再用 5 个演示**数值验证理论**：

1. **随机游走的 √n 规律**：1 万条轨迹的终点标准差是否等于 `√n`。
2. **马尔可夫链的平稳分布**：解析解（特征向量）与长程模拟的经验频率是否一致。
3. **Langevin 动力学 = 梯度下降 + 噪声**：能否从能量函数 `U(x)` 采样出 `exp(−U)` 分布。
4. **Metropolis-Hastings**：只知道未归一化的 log 密度，能否采样一个双峰分布；提议步长如何影响接受率。
5. **扩散模型前向过程**：信号如何随噪声表一步步退化。

> 一句话：**每个随机过程都是"一个更新公式 + 一个循环"**。这份代码让你看清这些公式，并亲手检验"理论分布"与"模拟统计量"是否吻合——也看到它们在哪里不吻合。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `random_walk_1d` / `random_walk_2d` | 函数 | 向量化地生成 1D / 2D 格点随机游走的位置序列 | 随机游走、√n 规律 |
| `MarkovChain` | 类 | 单步转移、长程模拟、平稳分布（特征向量法）、经验分布 | 马尔可夫链、平稳分布 |
| `langevin_dynamics` | 函数 | `x ← x − dt·∇U + √(2T·dt)·z` 的迭代 | Langevin 动力学 |
| `metropolis_hastings` | 函数 | 对称高斯提议 + 对数域接受/拒绝 | MCMC |
| `diffusion_forward` | 函数 | 线性噪声表下逐步加噪 | DDPM 前向过程 |
| `demo_random_walks` 等 5 个 | 演示函数 | 打印理论值与模拟值的对比 | — |

数据流非常扁平：每个演示调用一个核心函数，再用 NumPy 统计量（`mean`、`std`、`var`、`corrcoef`）与理论值对照。所有随机性都来自 `np.random.RandomState(seed)`，因此结果可复现。

---

## 3. 逐段精讲

### 3.1 随机游走：用 `cumsum` 代替循环

```python
def random_walk_1d(n_steps, seed=None):
    rng = np.random.RandomState(seed)
    steps = rng.choice([-1, 1], size=n_steps)
    positions = np.concatenate([[0], np.cumsum(steps)])
    return positions
```

- `rng.choice([-1, 1], size=n_steps)` 一次性抽出 n 个等概率的 ±1，对应讲义的"抛硬币"。
- `np.cumsum` 是累加和：第 i 个元素 = 前 i 步之和 = 第 i 步后的位置。这就是 `Sₙ = X₁ + … + Xₙ` 的**向量化**写法，循环在 NumPy 的 C 代码里完成，比逐步的 Python 循环快得多。
- `np.concatenate([[0], ...])` 在开头补上起点 0，所以返回 `n_steps + 1` 个位置。
- 每次调用都新建 `RandomState(seed)`，同一个 seed 一定得到同一条轨迹——演示里用 `seed=i` 生成 1 万条互不相同、但可复现的轨迹。

```python
def random_walk_2d(n_steps, seed=None):
    rng = np.random.RandomState(seed)
    directions = rng.choice(4, size=n_steps)
    dx = np.zeros(n_steps)
    dy = np.zeros(n_steps)
    dx[directions == 0] = 1
    dx[directions == 1] = -1
    dy[directions == 2] = 1
    dy[directions == 3] = -1
    x = np.concatenate([[0], np.cumsum(dx)])
    y = np.concatenate([[0], np.cumsum(dy)])
    return x, y
```

- `rng.choice(4, ...)` 从 `{0,1,2,3}` 中抽方向；然后用**布尔掩码**一次性把"向右/左/上/下"翻译成 dx、dy。每一步只有一个坐标变化。
- 2D 中到原点的均方根距离仍是 `√n`（每步恰好移动 1 个单位）。实测 2000 条 1000 步的轨迹，均方根距离约 31.1，与 `√1000 ≈ 31.6` 吻合。⚠️ 演示中并没有调用 `random_walk_2d`，它是留给你做练习的。

### 3.2 `MarkovChain`：模拟与经验分布

```python
class MarkovChain:
    def __init__(self, transition_matrix, state_names=None):
        self.P = np.array(transition_matrix, dtype=float)
        self.n_states = len(self.P)
        self.state_names = state_names or [str(i) for i in range(self.n_states)]

    def step(self, current_state, rng=None):
        if rng is None:
            rng = np.random.RandomState()
        probs = self.P[current_state]
        return rng.choice(self.n_states, p=probs)

    def simulate(self, start_state, n_steps, seed=None):
        rng = np.random.RandomState(seed)
        states = [start_state]
        current = start_state
        for _ in range(n_steps):
            current = self.step(current, rng)
            states.append(current)
        return states
```

- `np.array(..., dtype=float)` 把嵌套列表转成浮点矩阵；`len(self.P)` 是行数，即状态数。
- `state_names or [...]`：`None` 为假值，所以没传名字时自动用 `"0"`、`"1"`…——这是 Python 常见的"默认值"写法。⚠️ 如果传入空列表 `[]` 也会被替换，一般无妨。
- `step` 的核心是 `rng.choice(n, p=probs)`：按当前状态那一**行**的概率抽下一个状态。这正是马尔可夫性的体现——只看 `current_state`，不看历史。
- `simulate` 把同一个 `rng` 传给每次 `step`，整条轨迹只用一个随机数流，保证可复现；如果 `step` 每次新建无种子的 `RandomState()`，结果就不可复现了。
- ⚠️ 没有校验 P 的每行和是否为 1；行和不为 1 时，`rng.choice` 会抛出 `ValueError: probabilities do not sum to 1`。

```python
    def empirical_distribution(self, states):
        counts = np.zeros(self.n_states)
        for s in states:
            counts[s] += 1
        return counts / len(states)
```

统计每个状态出现的频率（包括起始状态）。等价的一行写法是 `np.bincount(states, minlength=self.n_states) / len(states)`。

### 3.3 `stationary_distribution`：左特征向量

```python
    def stationary_distribution(self):
        eigenvalues, eigenvectors = np.linalg.eig(self.P.T)
        idx = np.argmin(np.abs(eigenvalues - 1.0))
        stationary = np.real(eigenvectors[:, idx])
        if stationary.sum() < 0:
            stationary = -stationary
        stationary = np.clip(stationary, 0, None)
        total = stationary.sum()
        if total > 0:
            stationary = stationary / total
        return stationary
```

| 步骤 | 为什么 |
|------|-------|
| `eig(self.P.T)` | `πP = π` 是**左**特征向量；转置后变成 `Pᵀ` 的右特征向量。P 不对称，所以只能用 `eig`，不能用 `eigh` |
| `argmin(|λ − 1|)` | 数值特征值可能是 `0.9999999999999998`，不能用 `== 1` 判断 |
| `np.real(...)` | 非对称矩阵的 `eig` 返回复数数组，去掉 `+0j` |
| 符号翻转 | 特征向量只确定到一个倍数，可能整体为负 |
| `np.clip(..., 0, None)` | 把 `−1e-17` 这样的浮点噪声截为 0，保证是合法概率 |
| 除以 `total` | 特征向量默认单位长度（L2 范数为 1），概率分布需要和为 1（L1） |

与讲义 Build It 版本（最后 `np.abs(...)`）相比，这里先翻转符号再 clip，更稳妥。⚠️ 对可约链（特征值 1 有多个），这里只会返回其中一个平稳分布。

### 3.4 `langevin_dynamics`：带校准噪声的梯度下降

```python
def langevin_dynamics(grad_U, x0, dt, temperature, n_steps, seed=None):
    rng = np.random.RandomState(seed)
    x = np.array(x0, dtype=float)
    trajectory = [x.copy()]
    for _ in range(n_steps):
        noise = rng.randn(*x.shape)
        x = x - dt * grad_U(x) + np.sqrt(2 * temperature * dt) * noise
        trajectory.append(x.copy())
    return np.array(trajectory)
```

- `grad_U` 是**函数参数**（高阶函数）：调用者传入能量函数的梯度，同一个采样器可以用于任何分布。
- `rng.randn(*x.shape)`：`*` 把形状元组解包成位置参数，生成与 x 同形状的标准正态噪声——对标量、向量、高维数组都适用。
- 两项分工：`− dt·∇U` 把粒子推向低能量区（梯度下降）；`√(2T·dt)·z` 是随机扰动。注意**系数是 √dt 而不是 dt**：噪声的**方差**正比于 dt，这是布朗运动 `B(t+dt) = B(t) + √dt·z` 的直接推论。系数 2 保证平稳分布恰好是 `exp(−U/T)`。
- `x.copy()`：轨迹里存副本。当前写法中 `x = x - ...` 每次都会创建新数组，不拷贝也不会出错；但如果以后改成 `x -= ...` 这种原地更新，不拷贝会让轨迹里所有元素都指向同一个数组。这是一种防御式写法。
- ⚠️ 这是**未经校正的 Langevin 算法（ULA）**，离散化本身带来 O(dt) 的偏差：对高斯目标 `N(μ, σ²)`，离散链的平稳方差是 `σ²·2/(2 − dt/σ²)`，而不是 σ²。演示中 `σ² = 2, dt = 0.1` 时理论值为 2.051。消除偏差可以加一个 MH 接受步骤（MALA），或者减小 dt。

### 3.5 `metropolis_hastings`：对数域的接受/拒绝

```python
def metropolis_hastings(target_log_prob, proposal_std, x0, n_samples, seed=None):
    if n_samples < 1:
        raise ValueError("n_samples must be at least 1")
    rng = np.random.RandomState(seed)
    x = np.array(x0, dtype=float)
    samples = [x.copy()]
    accepted = 0
    for _ in range(n_samples - 1):
        x_proposed = x + rng.randn(*x.shape) * proposal_std
        log_ratio = target_log_prob(x_proposed) - target_log_prob(x)
        if np.log(rng.rand()) < log_ratio:
            x = x_proposed
            accepted += 1
        samples.append(x.copy())
    acceptance_rate = accepted / (n_samples - 1)
    return np.array(samples), acceptance_rate
```

- **提议**：`x + N(0, proposal_std²)`，对称提议，所以 Hastings 修正项 `Q(x|x')/Q(x'|x) = 1`，只剩 `p(x')/p(x)`。
- **对数域**：`log_ratio = log p(x') − log p(x)`，归一化常数在减法中约掉；用 `log(u) < log_ratio`（u ~ U(0,1)）代替 `u < p(x')/p(x)`，避免小概率相除时下溢、`exp` 上溢。当 `log_ratio ≥ 0` 时 `log(u) < 0 ≤ log_ratio` 恒成立，等于自动实现了 `min(1, ·)`。
- **拒绝时也要记录**：被拒绝时 x 不变，但仍然 `append` 一次当前值。重复的样本是 MH 正确性的一部分（它们代表"在高概率区停留更久"），不能删掉。
- ⚠️ 两个小问题：
  1. `n_samples=1` 能通过 `< 1` 的检查，循环不执行，最后 `0 / 0` 抛出 `ZeroDivisionError`（已实测）。应改为 `n_samples < 2`，或在 `n_samples == 1` 时返回 `nan`。
  2. `target_log_prob(x)` 在 x 没变时被重复计算。缓存当前点的 log 密度可以把目标函数的调用次数减半，结果完全不变（测验 Q10 给出了改写版并验证过）。

### 3.6 `diffusion_forward`：DDPM 前向加噪

```python
def diffusion_forward(signal, n_steps, beta_start=0.0001, beta_end=0.02, seed=None):
    rng = np.random.RandomState(seed)
    betas = np.linspace(beta_start, beta_end, n_steps)
    trajectory = [signal.copy()]
    x = signal.copy()
    for t in range(n_steps):
        noise = rng.randn(*x.shape)
        x = np.sqrt(1 - betas[t]) * x + np.sqrt(betas[t]) * noise
        trajectory.append(x.copy())
    return np.array(trajectory), betas
```

- `np.linspace` 生成线性噪声表，默认值 `1e-4 → 0.02` 与 DDPM 论文一致（论文用 T = 1000 步）。
- 更新式 `xₜ = √(1−βₜ)·xₜ₋₁ + √βₜ·ε`：先把旧信号**缩小**，再加噪声。两个系数的平方和为 1，所以如果 `xₜ₋₁` 方差为 1，`xₜ` 方差仍为 1——这叫**方差保持（variance preserving）**。如果不缩小直接加噪声，方差会一路增大。
- 多步合起来有闭式：`xₜ = √ᾱₜ·x₀ + √(1−ᾱₜ)·ε`，`ᾱₜ = Π(1−β_s)`。这里逐步模拟是为了展示"马尔可夫链"本身；真正训练时直接用闭式一步得到 `xₜ`。
- 输入 `signal` 必须是 NumPy 数组：循环里的 `rng.randn(*x.shape)` 用到了 `.shape` 属性，Python 列表没有它，会抛 `AttributeError`。

### 3.7 五个演示的设计要点

**`demo_random_walks`**：先打印 5 条轨迹的终点和极值，直观感受"公平却越走越远"；再跑 1 万条，比较 `finals.std()` 与 `√1000`。注意它验证的是**标准差**（均方根距离）`√n`，而平均绝对距离 `E|Sₙ|` 约为 `0.8·√n`。

**`demo_markov_chain`**：
- 解析解 `[0.5455, 0.1818, 0.2727]`（精确值 `6/11, 2/11, 3/11`）与 10 万步经验频率对比。
- "Convergence check" 从 Rainy 出发、对每个长度都用 `seed=42`，所以四次模拟其实是**同一条轨迹的不同长度前缀**——观察的是"运行平均"随长度收敛的过程。蒙特卡洛误差大致按 `1/√n` 下降，但会有波动（1000 步 0.0100、10000 步 0.0104）。
- `" -> ".join(names[s] for s in short[:15])` 把状态序列拼成可读的天气链。

**`demo_langevin`**：

```python
    target_mean = 3.0
    target_var = 2.0

    def grad_U(x):
        return (x - target_mean) / target_var
```

- 在函数内部定义 `grad_U`（**嵌套函数 / 闭包**），它"捕获"了外层的 `target_mean` 和 `target_var`。`U(x) = (x−3)²/(2·2)`，所以 `exp(−U) ∝ N(3, 2)`。
- 跑 5 万步，丢掉前 5000 步作为 burn-in（`trajectory[5000:, 0]`），统计均值和方差。

**`demo_metropolis_hastings`**：

```python
    def bimodal_log_prob(x):
        v = np.asarray(x).ravel()[0]
        log_p1 = -0.5 * (v - 3) ** 2
        log_p2 = -0.5 * (v + 3) ** 2
        return np.logaddexp(log_p1, log_p2) - np.log(2)
```

- 目标是 `0.5·N(−3,1) + 0.5·N(3,1)`（省略了公共常数 `1/√(2π)`，MH 不需要它）。
- `np.logaddexp(a, b) = log(eᵃ + eᵇ)`，数值稳定地把两个分量的 log 密度"加"起来，这就是 log-sum-exp 技巧。
- `np.asarray(x).ravel()[0]`：把形状为 `(1,)` 的数组取成标量，使函数同时兼容标量和数组输入。
- 之后用 5 种 `proposal_std` 对比接受率，说明"步长小 → 接受率高但走不动；步长大 → 拒绝多"。

**`demo_diffusion`**：对 `sin(t) + 0.5·sin(3t)` 加噪 100 步，在 0/10/25/50/75/100 步打印均值、标准差、SNR 和与原信号的相关系数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 随机游走用 `cumsum` 向量化 | 一行实现 `Sₙ`，快 | 无 |
| 每个函数自建 `RandomState(seed)` | 结果可复现，演示可对照 | 新代码推荐 `np.random.default_rng(seed)`（Generator API） |
| 马尔可夫链逐步 `rng.choice` | 与"按行采样下一状态"的定义一一对应 | Python 循环慢；大规模可用预先生成的均匀随机数 + 累积概率表 |
| 平稳分布用 `eig(Pᵀ)` | 直接对应"左特征向量"的定义 | 大规模稀疏链用幂迭代或稀疏求解器 |
| Langevin 不做 MH 校正 | 代码最短，突出"梯度 + 噪声" | 有 O(dt) 偏差；需要精确采样时用 MALA / HMC |
| MH 在对数域比较 | 避免下溢 / 上溢 | 无；但应缓存当前点的 log 密度 |
| MH 用固定步长的高斯提议 | 最简单，便于观察步长的影响 | 多峰或高维时效率低；实践中用自适应步长、HMC/NUTS、并行回火 |
| 扩散前向逐步模拟 | 展示"马尔可夫链"本身 | 训练时用闭式 `√ᾱₜx₀ + √(1−ᾱₜ)ε` 一步采样 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 `None` | `def random_walk_1d(n_steps, seed=None)` | 不传就是"不固定种子" |
| `is None` 判断 | `if rng is None:` | 判断 None 用 `is`，不用 `==` |
| `or` 提供默认值 | `state_names or [str(i) for i in ...]` | 左边为假值（None、空列表）时取右边 |
| 类与方法 | `class MarkovChain:`、`def step(self, ...)` | 用 `self.P` 在方法间共享转移矩阵 |
| 列表推导式 | `[str(i) for i in range(self.n_states)]` | 一行生成列表 |
| `for _ in range(...)` | `for _ in range(n_steps):` | 不需要循环变量时用 `_` |
| 函数作为参数 | `langevin_dynamics(grad_U=grad_U, ...)` | 高阶函数：把函数当作值传递 |
| 嵌套函数 / 闭包 | `def grad_U(x): return (x - target_mean) / target_var` | 内层函数可以读取外层函数的局部变量 |
| 关键字参数调用 | `metropolis_hastings(target_log_prob=..., proposal_std=2.0, ...)` | 按名字传参，可读性高 |
| `*` 解包 | `rng.randn(*x.shape)` | 把元组 `(1,)` 展开成位置参数 |
| 返回元组 | `return x, y`；`samples, acc_rate = metropolis_hastings(...)` | 一次返回 / 接收多个值 |
| `raise ValueError` | `raise ValueError("n_samples must be at least 1")` | 主动报错 |
| 生成器表达式 + `join` | `" -> ".join(names[s] for s in short[:15])` | 把多个字符串用分隔符拼接 |
| f-string 格式符 | `{walk[-1]:+4d}`、`{acc_rate:.2%}`、`{length:>7d}`、`{std:5.1f}`、`{'Step':>6s}` | `+` 总显示符号；`%` 按百分比显示；`>` 右对齐 |
| `float('inf')` | `snr = float('inf')` | 正无穷（无噪声时 SNR 无穷大） |
| `RandomState` | `rng.choice([-1, 1], size=n)`、`rng.choice(n, p=probs)`、`rng.randn(...)`、`rng.rand()` | 抽样（可指定概率）、标准正态、[0,1) 均匀 |
| NumPy 构造 | `np.zeros(n)`、`np.linspace(a, b, n)`、`np.array(x0, dtype=float)` | 全 0、等差数列、类型转换 |
| `np.cumsum` / `np.concatenate` | `np.concatenate([[0], np.cumsum(steps)])` | 累加和；拼接数组 |
| 布尔掩码 | `dx[directions == 0] = 1`、`samples_flat[samples_flat < 0]` | 按条件赋值 / 筛选 |
| 二维切片 | `eigenvectors[:, idx]`、`trajectory[5000:, 0]` | 取某列；取第 5000 行之后的第 0 列 |
| 线性代数与数值函数 | `np.linalg.eig`、`np.argmin`、`np.real`、`np.clip(x, 0, None)` | 一般矩阵特征分解、最小值下标、取实部、截断（`None` 表示无上限） |
| 稳定的对数运算 | `np.log`、`np.logaddexp`、`np.log10` | log-sum-exp；分贝换算 |
| 统计方法 | `.mean()`、`.std()`、`.var()`、`.max()`、`.min()`、`np.corrcoef(a, b)[0, 1]` | 数组统计量；相关系数矩阵的非对角元 |
| `.copy()` | `trajectory = [x.copy()]` | 存副本，防止之后的原地修改影响历史记录 |
| `np.asarray(x).ravel()[0]` | `bimodal_log_prob` 中 | 转数组 → 拉平 → 取第一个元素 |

---

## 6. 运行结果解读

实际运行（临时副本中执行 `python3 stochastic.py`，NumPy 2.5，耗时约 4 秒）的关键输出：

```text
  Walk 2: final position =  -44, max =  +16, min =  -46
  Walk 4: final position =  -48, max =   +3, min =  -68
Theory: E[position] = 0, std(position) = sqrt(1000) = 31.6
10000 walks: mean = 0.02, std = 31.63 (expected 31.62)
```

- 单条轨迹可以偏离很远（Walk 4 一度到 −68，超过 2 倍标准差），但 1 万条的均值约为 0、标准差 31.63——√n 规律被精确验证。

```text
Stationary distribution (analytical):
  Sunny: 0.5455
  Rainy: 0.1818
  Cloudy: 0.2727
Empirical distribution (100000 steps, start=Sunny):
  Sunny: 0.5469 ...
Convergence check:
      100 steps: max error = 0.0531
     1000 steps: max error = 0.0100
    10000 steps: max error = 0.0104
   100000 steps: max error = 0.0022
```

- 解析解与 10 万步的经验频率相差不到 0.003。
- 误差总体下降，但 1000 → 10000 步时并没有变小：这是蒙特卡洛误差的随机波动，它只是**大致**按 `1/√n` 下降，而且相邻状态高度相关，有效样本数比步数少。

```text
Target: mean = 3.0, variance = 2.0
Sampled (45001 samples after 5000 burn-in):
  Mean:     2.9904 (expected 3.0)
  Variance: 2.0888 (expected 2.0)
```

- 均值很准。方差偏大，其中一部分是**系统偏差**：dt = 0.1 时离散链的理论平稳方差为 2.051（见 3.4）；其余是有限样本误差。把 dt 改成 0.5，实测方差约 2.31，理论值 2.29，偏差更明显。

```text
Acceptance rate: 53.26%
Sample std:  3.1545
Left mode (x < 0):  mean = -2.9863, count = 44795
Right mode (x >= 0): mean = 2.9985, count = 45205
Fraction in each mode: 49.77% / 50.23% (expected ~50/50)
```

- 理论标准差 `√(1 + 3²) = √10 ≈ 3.162`，实测 3.155；两个峰各约一半，均值约 ±3——双峰被正确采到。

```text
  std =   0.1: acceptance rate = 96.89%
  std =   2.0: acceptance rate = 54.51%
  std =  20.0: acceptance rate = 12.56%
```

- 接受率随步长单调下降，但**接受率高不代表采样好**：额外统计发现，`std = 0.1` 时 10000 个样本中 99.7% 都停留在右峰，几乎没有跨过 x = 0；`std = 5.0` 时跨峰 1277 次。

```text
  Step |     Mean |      Std |   SNR (dB) |  Correlation
     0 |   0.0000 |   0.7886 |        inf |       1.0000
    50 |  -0.0273 |   0.8481 |       0.29 |       0.5688
   100 |   0.0913 |   0.9782 |      -2.64 |       0.2891

At step 100: nearly pure noise (correlation near 0)
```

- 标准差从 0.79 逐渐趋近 1——方差保持的前向过程会把任何输入推向 `N(0, 1)`。
- 但最后一行的结论与数据不符：第 100 步的相关系数仍有 0.29。原因是这个噪声表的 `ᾱ₁₀₀ = Π(1−βₜ) ≈ 0.075`，信号还保留了 `√0.075 ≈ 0.27` 倍的幅度。DDPM 的设置（1000 步，β 从 1e-4 到 0.02）下 `ᾱ_T ≈ 4×10⁻⁵`，那才是真正接近纯噪声。
- SNR 的计算把 `x − signal` 都当成噪声，而 `xₜ` 中的信号已被缩小到 `√ᾱₜ` 倍，这部分缩水也算进了噪声，所以 SNR 只是粗略指标。

---

## 7. 动手改一改

1. **√n 的两种含义**：在 1 万条 1000 步的游走上同时计算 `np.sqrt((finals**2).mean())` 与 `np.abs(finals).mean()`，验证前者 ≈ `√n`、后者 ≈ `√(2n/π)`（实测约 31.6 和 25.1）。
2. **赌徒破产**：从 k = 3 出发、在 0 和 10 处吸收，模拟 2 万次，验证到达 10 的概率 ≈ 0.3（实测 0.302）。
3. **谱间隙与混合**：对天气链求 `np.linalg.eigvals(P)`（结果为 1、0.362、0.138），再从 Sunny 出发做幂迭代，打印每一步与平稳分布的总变差距离，观察它是否按 `0.362ᵗ` 的速度衰减。
4. **修复并加速 MH**：处理 `n_samples=1`；缓存 `log_p_x`；再加一个"跨峰次数"统计，把 5 种 `proposal_std` 的接受率和跨峰次数放进同一张表。
5. **MALA**：把 Langevin 的一步当作提议，加上 MH 接受步骤（注意提议不对称，需要 Hastings 修正项）。在 dt = 0.5 时对比 ULA 与 MALA 的样本方差。
6. **扩散闭式采样**：写 `q_sample(x0, t, betas, rng)` 直接返回 `√ᾱₜ·x₀ + √(1−ᾱₜ)·ε`，与 `diffusion_forward` 逐步模拟的统计量对比；再调整 `beta_end` 或 `n_steps`，让第 T 步的相关系数降到 0.05 以下。

---

## 8. 常见坑

- **把 √n 当成"平均距离"**：√n 是均方根距离，平均绝对距离约为 `0.8·√n`。
- **左右特征向量搞反**：平稳分布是 `Pᵀ` 的特征向量；对 P 本身求，得到的永远是全 1 向量。转移矩阵不对称，不能用 `eigh`。
- **只看接受率调 MCMC**：接受率高可能意味着链几乎没动；要结合跨峰次数、自相关、多链诊断。
- **在概率域相乘相除**：高维时密度会下溢为 0；一律在对数域计算，并用 `logaddexp` 合并混合分量。
- **噪声系数写错**：Langevin 的噪声是 `√(2T·dt)·z`，不是 `2T·dt·z`；扩散前向要先把信号乘以 `√(1−β)`，否则方差会一路增大。
- **以为"跑了 T 步就是纯噪声"**：是否接近纯噪声取决于 `ᾱ_T`，而不是步数本身。
