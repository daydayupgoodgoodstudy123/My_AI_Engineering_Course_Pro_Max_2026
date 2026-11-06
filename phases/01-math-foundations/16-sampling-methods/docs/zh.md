<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="sampling-methods"></a>

# Sampling 方法

> Sampling 是人工智能探索可能性空间的方式。

**类型：** 构建
**语言：** Python
**先决条件：** 第 1 阶段，第 06-07 课（概率、贝叶斯定理）
**时间：** ~120 分钟

<a id="learning-objectives"></a>

## 学习目标

- 仅使用统一随机数从头开始实现逆 CDF、拒绝和 importance sampling
- 为语言模型 token 生成构建 temperature、top-k 和 top-p（核心）sampling
- 解释重新参数化技巧以及为什么它通过 VAEs 中的 sampling 启用 backpropagation
- 运行 Metropolis-Hastings MCMC 从非标准化目标分布中进行采样

<a id="the-problem"></a>

## 问题

语言模型完成对 prompt 的处理并生成 50,000 个 logits 的向量。 vocabulary 中的每个 token 都有一个。现在它必须选择一个。如何？

如果它总是选择概率最高的 token，则每个响应都是相同的。确定性的。无聊的。如果它随机选择，输出就是乱码。答案介于这两个极端之间，并且由 sampling 控制。

Sampling 不限于文本生成。 Reinforcement learning 通过 sampling 轨迹估计 policy gradients。 VAEs 通过 sampling 从学习的分布中学习潜在表示并通过随机性进行反向传播。 Diffusion models 通过 sampling 噪声和迭代去噪生成图像。 Monte Carlo 方法估计没有封闭式解的积分。 MCMC 算法探索无法枚举的高维后验分布。

每个生成式人工智能系统都是一个 sampling 系统。 sampling策略决定了产出的质量、多样性、可控性。本课程从头开始构建每个主要的 sampling 方法，从统一随机数开始，到支持现代 LLMs 和生成模型的技术结束。

<a id="the-concept"></a>

## 概念

<a id="why-sampling-matters"></a>

### 为什么 Sampling 很重要

Sampling 在人工智能和机器学习领域扮演着四个基本角色：

**Generation.** 语言模型、diffusion models 和 GANs 均由 sampling 生成输出。 sampling算法直接控制创造力、连贯性和多样性。 Temperature、top-k和nucleus sampling是工程师每天转动的旋钮。

**Training.** Stochastic gradient descent 样本小批量。 Dropout 对神经元进行采样以使其失活。 Data augmentation 对随机变换进行采样。 Importance sampling 重新加权样本以减少 reinforcement learning 中的 gradient 方差（PPO，TRPO）。

**Estimation.** ML 中的许多量没有封闭式解。数据分布的预期损失、基于能量的模型的配分函数、贝叶斯 inference 中的证据。 Monte Carlo 估计通过对样本进行平均来近似所有这些。

**Exploration.** MCMC 算法探索贝叶斯 inference 中的后验分布。进化策略样本 parameter 扰动。 Thompson sampling 平衡了 bandits 的探索和利用。

核心挑战：您只能直接从简单分布（均匀分布、正态分布）中采样。对于其他一切，您需要一种方法将简单样本转换为目标分布中的样本。

<a id="uniform-random-sampling"></a>

### 统一随机 Sampling

每个 sampling 方法都从这里开始。均匀随机数生成器生成 [0, 1) 中的值，其中每个长度相等的子区间具有相等的概率。

```
U ~ Uniform(0, 1)

P(a <= U <= b) = b - a    for 0 <= a <= b <= 1

Properties:
  E[U] = 0.5
  Var(U) = 1/12
```

要从 n 个项目的离散集合中均匀采样，请生成 U 并返回下限 (n * U)。要从连续范围 [a、b] 进行采样，请计算 a + (b - a) * U。

关键见解：单个均匀随机数包含恰好适量的随机性，可以从任何分布中生成一个样本。诀窍是找到正确的转变。

<a id="inverse-cdf-method-inverse-transform-sampling"></a>

### 逆CDF法（逆变换Sampling）

累积分布函数 (CDF) 将值映射到概率：

```
F(x) = P(X <= x)

Properties:
  F is non-decreasing
  F(-inf) = 0
  F(+inf) = 1
  F maps the real line to [0, 1]
```

逆 CDF 将概率映射回值。如果 U ~ Uniform(0, 1)，则 X = F_inverse(U) 遵循目标分布。

```
Algorithm:
  1. Generate u ~ Uniform(0, 1)
  2. Return F_inverse(u)

Why it works:
  P(X <= x) = P(F_inverse(U) <= x) = P(U <= F(x)) = F(x)
```

**指数分布示例：**

```
PDF: f(x) = lambda * exp(-lambda * x),   x >= 0
CDF: F(x) = 1 - exp(-lambda * x)

Solve F(x) = u for x:
  u = 1 - exp(-lambda * x)
  exp(-lambda * x) = 1 - u
  x = -ln(1 - u) / lambda

Since (1 - U) and U have the same distribution:
  x = -ln(u) / lambda
```

当您可以以封闭形式写下 F_inverse 时，这将非常有效。对于正态分布，不存在封闭形式的逆 CDF，因此我们使用其他方法（Box-Muller 或数值近似）。

**离散版本：** 对于离散分布，将CDF构建为累积和，生成U，并找到累积和超过U的第一个索引。这就是第06课中`sample_categorical`的工作原理。

<a id="rejection-sampling"></a>

### 拒绝 Sampling

当您无法反转 CDF 但可以将目标 PDF 评估为常数时，拒绝 sampling 有效。

```
Target distribution: p(x)  (can evaluate, possibly unnormalized)
Proposal distribution: q(x)  (can sample from)
Bound: M such that p(x) <= M * q(x) for all x

Algorithm:
  1. Sample x ~ q(x)
  2. Sample u ~ Uniform(0, 1)
  3. If u < p(x) / (M * q(x)), accept x
  4. Otherwise, reject and go to step 1

Acceptance rate = 1/M
```

约束M越紧，接受率越高。在低维度 (1-3) 中，拒绝 sampling 效果很好。在高维度中，接受率呈指数下降，因为大多数提案量都被拒绝。这就是拒绝的维度诅咒sampling。

**E示例：来自截断法线的 sampling。** 在截断范围内使用统一建议。包络 M 是该范围内正常 PDF 的最大值。

**示例：sampling 来自半圆。** 在边界矩形中均匀提出。如果该点落在半圆内，则接受。这就是 Monte Carlo 计算 pi 的方式：接受率等于面积比 pi/4。

<a id="importance-sampling"></a>

### Importance Sampling

有时您不需要目标分布 p(x) 中的样本。您需要估计 p(x) 下的期望，并且您有来自不同分布 q(x) 的样本。

```
Goal: estimate E_p[f(x)] = integral of f(x) * p(x) dx

Rewrite:
  E_p[f(x)] = integral of f(x) * (p(x)/q(x)) * q(x) dx
            = E_q[f(x) * w(x)]

where w(x) = p(x) / q(x)  are the importance weights.

Estimator:
  E_p[f(x)] ~ (1/N) * sum(f(x_i) * w(x_i))    where x_i ~ q(x)
```

这在 reinforcement learning 中至关重要。在PPO（近端策略优化）中，您在旧策略pi_old下收集轨迹，但想要优化新策略pi_new。 weight 的重要性为 pi_new(a|s) / pi_old(a|s）。 PPO 剪辑这些 weights 以防止新策略与旧策略偏离太远。

importance sampling 估计器的方差取决于 q 与 p 的相似程度。如果 q 与 p 相差很大，则少数样本会获得巨大的 weights 并主导估计。自归一化 importance sampling 除以 weights 的总和来减少这个问题：

```
E_p[f(x)] ~ sum(w_i * f(x_i)) / sum(w_i)
```

<a id="monte-carlo-estimation"></a>

### Monte Carlo 预估

Monte Carlo 估计通过平均随机样本来近似积分。大数定律保证收敛。

```
Goal: estimate I = integral of g(x) dx over domain D

Method:
  1. Sample x_1, ..., x_N uniformly from D
  2. I ~ (Volume of D / N) * sum(g(x_i))

Error: O(1 / sqrt(N))   regardless of dimension
```

错误率与维度无关。这就是为什么 Monte Carlo 方法在不可能进行基于网格的集成的高维度中占主导地位。

**E估计圆周率：**

```
Sample (x, y) uniformly from [-1, 1] x [-1, 1]
Count how many fall inside the unit circle: x^2 + y^2 <= 1
pi ~ 4 * (count inside) / (total count)
```

**E预估预期：**

```
E[f(X)] ~ (1/N) * sum(f(x_i))    where x_i ~ p(x)

The sample mean converges to the true expectation.
Variance of the estimator = Var(f(X)) / N
```

<a id="markov-chain-monte-carlo-mcmc-metropolis-hastings"></a>

### 马尔可夫链 Monte Carlo (MCMC): Metropolis-Hastings

MCMC构造一个马尔可夫链，其平稳分布是目标分布p(x)。经过足够多的步骤后，链中的样本（大约）是来自 p(x) 的样本。

```
Target: p(x)  (known up to a normalizing constant)
Proposal: q(x'|x)  (how to propose the next state given the current state)

Metropolis-Hastings algorithm:
  1. Start at some x_0
  2. For t = 1, 2, ..., T:
     a. Propose x' ~ q(x'|x_t)
     b. Compute acceptance ratio:
        alpha = [p(x') * q(x_t|x')] / [p(x_t) * q(x'|x_t)]
     c. Accept with probability min(1, alpha):
        - If u < alpha (u ~ Uniform(0,1)): x_{t+1} = x'
        - Otherwise: x_{t+1} = x_t
  3. Discard first B samples (burn-in)
  4. Return remaining samples
```

对于对称提议 (q(x'|x) = q(x|x'))，该比率简化为 p(x')/p(x)。这是原始的 Metropolis 算法。

**为什么有效。** 接受规则确保了详细的平衡：位于 x 并移动到 x' 的概率等于位于 x' 并移动到 x 的概率。详细的平衡意味着 p(x) 是链的平稳分布。

**实际考虑：**
- 老化：在链达到平衡之前丢弃早期样本
- 细化：保留每个第 k 个样本以减少自相关
- 提案规模：太小，链动缓慢（接受度高，探索慢）；太大，大多数提案被拒绝（接受度低，卡在原地）
- 高维高斯提案的最佳接受率约为 0.234

<a id="gibbs-sampling"></a>

### 吉布斯 Sampling

Gibbs sampling 是多元分布的 MCMC 的特例。它不是一次性建议在所有维度上采取行动，而是根据其条件分布一次更新一个变量。

```
Target: p(x_1, x_2, ..., x_d)

Algorithm:
  For each iteration t:
    Sample x_1^{t+1} ~ p(x_1 | x_2^t, x_3^t, ..., x_d^t)
    Sample x_2^{t+1} ~ p(x_2 | x_1^{t+1}, x_3^t, ..., x_d^t)
    ...
    Sample x_d^{t+1} ~ p(x_d | x_1^{t+1}, x_2^{t+1}, ..., x_{d-1}^{t+1})
```

Gibbs sampling 要求您可以从每个条件分布 p(x_i | x_{-i})。这对于许多模型来说都很简单：
- 贝叶斯网络：条件遵循图结构
- 高斯混合：条件是高斯的
- 伊辛模型：每个自旋的条件仅取决于其邻居

接受率始终为 1（每个提案都被接受），因为精确条件中的 sampling 自动满足详细余额。

**Limitation.** 当变量高度相关时，Gibbs sampling 混合缓慢，因为一次更新一个变量无法在分布中进行较大的对角线移动。

<a id="temperature-sampling-used-in-llms"></a>

### Temperature Sampling（用于LLMs）

语言模型为 vocabulary 中的每个 token 输出 logits z_1, ..., z_V。 Softmax 将这些转换为概率。 Temperature 在 softmax 之前重新缩放 logits：

```
p_i = exp(z_i / T) / sum(exp(z_j / T))

T = 1.0: standard softmax (original distribution)
T -> 0:  argmax (deterministic, always picks highest logit)
T -> inf: uniform (all tokens equally likely)
T < 1.0: sharpens the distribution (more confident, less diverse)
T > 1.0: flattens the distribution (less confident, more diverse)
```

**为什么有效。** 将 logits 除以 T < 1 会放大 logits 之间的差异。如果z_1 = 2且z_2 = 1，则除以T = 0.5得到z_1/T = 4且z_2/T = 2，使得间隙更大。在softmax之后，最高logit的token获得了更大的份额。

**实践中：**
- T = 0.0：贪婪解码，最适合事实问答
- T = 0.3-0.7：稍有创意，有利于代码生成
- T = 0.7-1.0：平衡，适合一般对话
- T = 1.0-1.5：创意写作、头脑风暴
- T > 1.5：越来越随机，很少有用

Temperature 不会改变 tokens 是可能的。它改变分配给每个 token 的概率质量。

<a id="top-k-sampling"></a>

### Top-k Sampling

Top-k sampling 将候选集限制为具有最高概率的 k 个 tokens，然后重新规范化并从该限制集中进行采样。

```
Algorithm:
  1. Compute softmax probabilities for all V tokens
  2. Sort tokens by probability (descending)
  3. Keep only the top k tokens
  4. Renormalize: p_i' = p_i / sum(p_j for j in top-k)
  5. Sample from the renormalized distribution

k = 1:  greedy decoding
k = V:  no filtering (standard sampling)
k = 40: typical setting, removes long tail of unlikely tokens
```

Top-k 防止模型选择存在于 vocabulary 分布长尾中的极不可能的 tokens（拼写错误、废话）。问题：无论上下文如何，k 都是固定的。当模型有信心时（一个 token 有 95% 的概率），k = 40 仍然允许 39 个替代方案。当模型不确定时（概率分散在 1000 个 tokens 中），k = 40 会切断看似合理的选项。

<a id="top-p-nucleus-sampling"></a>

### Top-p（核心）Sampling

top -p sampling 动态调整候选集大小。它没有保留固定数量的tokens，而是保留累积概率超过p的tokens的最小集合。

```
Algorithm:
  1. Compute softmax probabilities for all V tokens
  2. Sort tokens by probability (descending)
  3. Find smallest k such that sum of top-k probabilities >= p
  4. Keep only those k tokens
  5. Renormalize and sample

p = 0.9:  keeps tokens covering 90% of probability mass
p = 1.0:  no filtering
p = 0.1:  very restrictive, nearly greedy
```

当模型有信心时，nucleus sampling 保留少量 tokens（可能是 2-3 个）。当模型不确定时，它会保留很多（也许 200 个）。这种自适应行为就是为什么 nucleus sampling 通常会生成比 top-k 更好的文本。

**常用组合：**
- Temperature 0.7 + top-p 0.9：良好的通用设置
- Temperature 0.0（贪婪）：最适合确定性任务
- Temperature 1.0 + top-k 50：Fan 等人。 (2018)原纸设定

Top-k 和 top-p 可以组合。首先应用 top-k，然后在剩余的集合上应用 top-p。

<a id="reparameterization-trick-used-in-vaes"></a>

### 重新参数化技巧（用于VAEs）

变分自动编码器 (VAEs) 通过将输入编码到 latent space 中的分布、从该分布中提取 sampling 并解码样本来进行学习。问题：您无法通过 sampling 操作进行反向传播。

```
Standard sampling (not differentiable):
  z ~ N(mu, sigma^2)

  The randomness blocks gradient flow.
  d/d_mu [sample from N(mu, sigma^2)] = ???
```

重新参数化技巧将随机性与 parameters 分开：

```
Reparameterized sampling:
  epsilon ~ N(0, 1)          (fixed random noise, no parameters)
  z = mu + sigma * epsilon   (deterministic function of parameters)

  Now z is a deterministic, differentiable function of mu and sigma.
  d(z)/d(mu) = 1
  d(z)/d(sigma) = epsilon

  Gradients flow through mu and sigma.
```

这是有效的，因为 N(mu, sigma^2) 与 mu + sigma * N(0, 1) 具有相同的分布。关键见解：将随机性移至 parameter 无源 (epsilon)，然后将样本表示为 parameters 的可微变换。

**在VAE训练循环中：**
1. Encoder 为每个输入输出 mu 和 log(sigma^2)
2. 样本 epsilon ~ N(0, 1)
3. 计算 z = mu + sigma * epsilon
4. 解码 z 以重建输入
5. 通过步骤 4、3、2、1 进行反向传播（可能是因为步骤 3 是可微分的）

如果没有重新参数化技巧，VAEs 无法使用标准 backpropagation 进行训练。这一单一见解使 VAEs 变得实用。

<a id="gumbel-softmax-differentiable-categorical-sampling"></a>

### Gumbel-Softmax（可微分类 Sampling）

重新参数化技巧适用于连续分布（高斯）。对于离散分类分布，我们需要一种不同的方法。 Gumbel-Softmax 提供了分类 sampling 的可微近似。

**Gumbel-Max 技巧（不可微分）：**

```
To sample from a categorical distribution with log-probabilities log(p_1), ..., log(p_k):
  1. Sample g_i ~ Gumbel(0, 1) for each category
     (g = -log(-log(u)), where u ~ Uniform(0, 1))
  2. Return argmax(log(p_i) + g_i)

This produces exact categorical samples.
```

**Gumbel-Softmax（可微近似）：**

```
Replace the hard argmax with a soft softmax:
  y_i = exp((log(p_i) + g_i) / tau) / sum(exp((log(p_j) + g_j) / tau))

tau (temperature) controls the approximation:
  tau -> 0:  approaches a one-hot vector (hard categorical)
  tau -> inf: approaches uniform (1/k, 1/k, ..., 1/k)
  tau = 1.0: soft approximation
```

Gumbel-Softmax 产生离散样本的连续松弛。输出是概率向量（软独热）而不是硬独热。 Gradients 流经softmax。在训练 forward pass 期间，您可以使用“直通”估计器：对 forward pass 使用硬 argmax，对 backward pass 使用软 Gumbel-Softmax gradients。

**应用：**
- VAEs 中的离散潜变量
- 神经架构搜索（选择离散操作）
- 硬 attention 机制
- Reinforcement learning 带离散动作

<a id="stratified-sampling"></a>

### 分层Sampling

标准 Monte Carlo sampling 可能会偶然在样本空间中留下间隙。分层 sampling 通过将空间划分为分层和 sampling 来强制均匀覆盖。

```
Standard Monte Carlo:
  Sample N points uniformly from [0, 1]
  Some regions may have clusters, others gaps

Stratified sampling:
  Divide [0, 1] into N equal strata: [0, 1/N), [1/N, 2/N), ..., [(N-1)/N, 1)
  Sample one point uniformly within each stratum
  x_i = (i + u_i) / N   where u_i ~ Uniform(0, 1),  i = 0, ..., N-1
```

与标准 Monte Carlo 相比，分层 sampling 始终具有较低或相等的方差：

```
Var(stratified) <= Var(standard Monte Carlo)

The improvement is largest when f(x) varies smoothly.
For piecewise-constant functions, stratified sampling is exact.
```

**应用：**
- 数值积分（准Monte Carlo）
- 训练数据分割（确保每个折叠中的类别平衡）
- Importance sampling 分层（结合两种技术）
- NeRF（神经辐射场）沿相机光线使用分层 sampling

<a id="connection-to-diffusion-models"></a>

### 连接到 Diffusion Models

Diffusion models 通过 sampling 进程生成图像。前向过程通过 T 个步骤向图像添加高斯噪声，直到变成纯噪声。逆向过程学习去噪，逐步恢复原始图像。

```
Forward process (known):
  x_t = sqrt(alpha_t) * x_{t-1} + sqrt(1 - alpha_t) * epsilon
  where epsilon ~ N(0, I)

  After T steps: x_T ~ N(0, I)  (pure noise)

Reverse process (learned):
  x_{t-1} = (1/sqrt(alpha_t)) * (x_t - (1 - alpha_t)/sqrt(1 - alpha_bar_t) * epsilon_theta(x_t, t)) + sigma_t * z
  where z ~ N(0, I)

  Each denoising step is a sampling step.
```

与本课方法的联系：
- 每个去噪步骤都使用重新参数化技巧（采样噪声，应用确定性变换）
- 噪声表 {alpha_t} 控制 temperature 退火的一种形式
- 训练使用 Monte Carlo 估计来近似 ELBO（证据下界）
- diffusion models中的祖传sampling是一条马尔可夫链（每一步仅取决于当前状态）

整个图像生成过程是迭代的 sampling：从噪声开始，在每一步中，根据学习的去噪模型采样噪声稍低的版本。

```figure
monte-carlo-pi
```

<a id="build-it"></a>

## 动手实现

<a id="step-1-uniform-and-inverse-cdf-sampling"></a>

### 步骤1：均匀和逆CDF sampling

```python
import math
import random

def sample_uniform(a, b):
    return a + (b - a) * random.random()

def sample_exponential_inverse_cdf(lam):
    u = random.random()
    return -math.log(u) / lam
```

生成 10,000 个指数样本并验证平均值为 1/lambda。

<a id="step-2-rejection-sampling"></a>

### 第2步：拒绝sampling

```python
def rejection_sample(target_pdf, proposal_sample, proposal_pdf, M):
    while True:
        x = proposal_sample()
        u = random.random()
        if u < target_pdf(x) / (M * proposal_pdf(x)):
            return x
```

使用拒绝 sampling 从截断正态分布中绘制。通过对样本进行直方图验证形状。

<a id="step-3-importance-sampling"></a>

### 步骤3：Importance sampling

```python
def importance_sampling_estimate(f, target_pdf, proposal_pdf, proposal_sample, n):
    total = 0
    for _ in range(n):
        x = proposal_sample()
        w = target_pdf(x) / proposal_pdf(x)
        total += f(x) * w
    return total / n
```

使用统一提案在正态分布下估计 E[X^2]。与已知答案 (mu^2 + sigma^2) 进行比较。

<a id="step-4-monte-carlo-estimation-of-pi"></a>

### 步骤4：Monte Carlo pi的估计

```python
def monte_carlo_pi(n):
    inside = 0
    for _ in range(n):
        x = random.uniform(-1, 1)
        y = random.uniform(-1, 1)
        if x*x + y*y <= 1:
            inside += 1
    return 4 * inside / n
```

<a id="step-5-metropolis-hastings-mcmc"></a>

### 第 5 步：大都会-黑斯廷斯 MCMC

```python
def metropolis_hastings(target_log_pdf, proposal_sample, proposal_log_pdf, x0, n_samples, burn_in):
    samples = []
    x = x0
    for i in range(n_samples + burn_in):
        x_new = proposal_sample(x)
        log_alpha = (target_log_pdf(x_new) + proposal_log_pdf(x, x_new)
                     - target_log_pdf(x) - proposal_log_pdf(x_new, x))
        if math.log(random.random()) < log_alpha:
            x = x_new
        if i >= burn_in:
            samples.append(x)
    return samples
```

来自双峰分布（两个高斯分布的混合）的样本。可视化链条的轨迹。

<a id="step-6-gibbs-sampling"></a>

### 步骤 6：吉布斯 sampling

```python
def gibbs_sampling_2d(conditional_x_given_y, conditional_y_given_x, x0, y0, n_samples, burn_in):
    x, y = x0, y0
    samples = []
    for i in range(n_samples + burn_in):
        x = conditional_x_given_y(y)
        y = conditional_y_given_x(x)
        if i >= burn_in:
            samples.append((x, y))
    return samples
```

<a id="step-7-temperature-sampling"></a>

### 步骤7：Temperature sampling

```python
def softmax(logits):
    max_l = max(logits)
    exps = [math.exp(z - max_l) for z in logits]
    total = sum(exps)
    return [e / total for e in exps]

def temperature_sample(logits, temperature):
    scaled = [z / temperature for z in logits]
    probs = softmax(scaled)
    return sample_from_probs(probs)
```

显示 temperature 如何更改一组 token logits 的输出分布。

<a id="step-8-top-k-and-top-p-sampling"></a>

### 步骤8：Top-k和top-p sampling

```python
def top_k_sample(logits, k):
    indexed = sorted(enumerate(logits), key=lambda x: -x[1])
    top = indexed[:k]
    top_logits = [l for _, l in top]
    probs = softmax(top_logits)
    idx = sample_from_probs(probs)
    return top[idx][0]

def top_p_sample(logits, p):
    probs = softmax(logits)
    indexed = sorted(enumerate(probs), key=lambda x: -x[1])
    cumsum = 0
    selected = []
    for token_idx, prob in indexed:
        cumsum += prob
        selected.append((token_idx, prob))
        if cumsum >= p:
            break
    sel_probs = [pr for _, pr in selected]
    total = sum(sel_probs)
    sel_probs = [pr / total for pr in sel_probs]
    idx = sample_from_probs(sel_probs)
    return selected[idx][0]
```

<a id="step-9-reparameterization-trick"></a>

### 步骤 9：重新参数化技巧

```python
def reparam_sample(mu, sigma):
    epsilon = random.gauss(0, 1)
    return mu + sigma * epsilon

def reparam_gradient(mu, sigma, epsilon):
    dz_dmu = 1.0
    dz_dsigma = epsilon
    return dz_dmu, dz_dsigma
```

证明 gradients 流经重新参数化的样本，但不直接流经 sampling。

<a id="step-10-gumbel-softmax"></a>

### 步骤10：Gumbel-Softmax

```python
def gumbel_sample():
    u = random.random()
    return -math.log(-math.log(u))

def gumbel_softmax(logits, temperature):
    gumbels = [math.log(p) + gumbel_sample() for p in logits]
    return softmax([g / temperature for g in gumbels])
```

展示减少 temperature 如何使输出接近 one-hot 向量。

所有可视化的完整实现都在 `code/sampling.py` 中。

<a id="use-it"></a>

## 实际应用

对于 NumPy 和 SciPy，生产版本：

```python
import numpy as np

rng = np.random.default_rng(42)

exponential_samples = rng.exponential(scale=2.0, size=10000)
print(f"Exponential mean: {exponential_samples.mean():.4f} (expected 2.0)")

from scipy import stats
normal = stats.norm(loc=0, scale=1)
print(f"CDF at 1.96: {normal.cdf(1.96):.4f}")
print(f"Inverse CDF at 0.975: {normal.ppf(0.975):.4f}")

logits = np.array([2.0, 1.0, 0.5, 0.1, -1.0])
temperature = 0.7
scaled = logits / temperature
probs = np.exp(scaled - scaled.max()) / np.exp(scaled - scaled.max()).sum()
token = rng.choice(len(logits), p=probs)
print(f"Sampled token index: {token}")
```

对于大规模 MCMC，请使用专用库：
- PyMC：使用 NUTS（自适应 HMC）的完整贝叶斯建模
- 主持人：合奏 MCMC 采样器
- NumPyro/JAX：GPU-加速MCMC

您从头开始构建了这些。现在你知道图书馆的电话正在做什么了。

<a id="exercises"></a>

## 练习

1. 为柯西分布实现逆 CDF sampling。 CDF 为 F(x) = 0.5 + arctan(x)/pi。生成 10,000 个样本并根据真实 PDF 绘制直方图。请注意重尾（远离中心的极值）。

2. 使用拒绝 sampling 使用 Uniform(0, 1) 提议从 Beta(2, 5) 分布生成样本。根据真实的 Beta PDF 绘制已接受的样本。理论接受率是多少？

3. 使用 Monte Carlo 和 1,000、10,000 和 100,000 个样本估计 sin(x) 从 0 到 pi 的积分。比较每个级别的误差。验证误差是否为 O(1/sqrt(N))。

4. 实现 Metropolis-Hastings，从与 exp(-(x^2 * y^2 + x^2 + y^2 - 8*x - 8*y) / 2) 成比例的 2D 分布 p(x, y) 进行采样。绘制样本和链轨迹。尝试不同的提案标准差。

5. 构建完整的文本生成演示：给定 10 个单词的 vocabulary 和 logits，使用 (a) 贪婪、(b) temperature=0.7、(c) top-k=3、(d) top-p=0.9 生成 20 个 tokens 的序列。比较 5 次运行的输出多样性。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|----------------------|
| Sampling | “绘制随机值” | 根据概率分布生成值。所有生成式人工智能背后的机制 |
| 均匀分布 | “一切可能性均等” | [a、b] 中的每个值都具有相等的概率密度 1/(b-a)。所有 sampling 方法的起点 |
| 逆累积分布函数 | 《概率变换》 | F_inverse(U) 将均匀样本转换为具有已知 CDF 的任意分布的样本。准确高效 |
| 拒绝 sampling | “提议并接受/拒绝” | 从简单的提案生成，以与目标/提案比率成比例的概率接受。准确但浪费样品 |
| Importance sampling | “重新称重样品” | 通过对每个样本进行 p(x)/q(x) 加权，使用 q(x) 中的样本估计 p(x) 下的期望。 RL 中 PPO 的核心 |
| Monte Carlo | “平均随机样本” | 近似积分作为样本平均值。无论尺寸如何，误差为 O(1/sqrt(N)) |
| MCMC | “收敛的随机游走” | 构造一个以平稳分布为目标的马尔可夫链。 Metropolis-Hastings 是基础算法 |
| 大都会-黑斯廷斯 | “接受上坡，有时下坡” | 根据密度比提出移动建议并接受。详细的平衡确保收敛到目标分布 |
| 吉布斯 sampling | “一次一个变量” | 根据条件分布更新每个变量，保持其他变量固定。 100% 录取率 |
| Temperature | “信心旋钮” | 在 softmax 之前将 logits 除以 T。 T<1 锐化（更加自信），T>1 扁平化（更加多样化） |
| Top-k sampling | “保持 k 最好” | 将除 k 个最高概率 tokens 之外的所有内容归零，重新归一化，采样。固定候选集大小 |
| Nucleus sampling（顶部-p） | “保留可能的” | 保留tokens的累积概率超过p的最小集合。自适应候选集大小 |
| 重新参数化技巧 | “把随机性移到外面” | 写出 z = mu + sigma * epsilon，其中 epsilon ~ N(0,1)。使 sampling 可微分。 VAE 培训必备 |
| Gumbel-Softmax | “软分类 sampling” | 使用 Gumbel 噪声对分类 sampling 的可微近似 + softmax 和 temperature |
| 分层sampling | “强制覆盖” | 将样本空间划分为多个层，从每个层中采样。方差始终低于朴素 Monte Carlo |
| 老化 | “预热期” | 在链达到其固定分布之前丢弃初始 MCMC 样本 |
| 详细余额 | “可逆性条件” | p(x) * T(x->y) = p(y) * T(y->x)。 p 是马尔可夫链平稳分布的充分条件 |
| 扩散 sampling | “迭代去噪” | 通过从噪声开始并应用学习的去噪步骤来生成数据。每一步都是一个有条件的 sampling 操作 |

<a id="further-reading"></a>

## 进一步阅读

- [Holbrook (2023)：Metropolis-Hastings 算法](https://arxiv.org/abs/2304.07010) - MCMC 基础的详细教程
- [Jang, Gu, Poole (2017)：使用 Gumbel-Softmax](https://arxiv.org/abs/1611.01144) 进行分类重新参数化 - 原始 Gumbel-Softmax 论文
- [Holtzman 等人。 (2020): 神经文本退化的奇怪案例](https://arxiv.org/abs/1904.09751) - 核 (top-p) sampling 论文
- [Kingma & Welling (2014)：自动编码变分贝叶斯](https://arxiv.org/abs/1312.6114) - VAE 论文介绍了重新参数化技巧
- [Ho, Jain, Abbeel (2020)：去噪扩散概率模型](https://arxiv.org/abs/2006.11239) - DDPM 将 sampling 连接到图像生成
