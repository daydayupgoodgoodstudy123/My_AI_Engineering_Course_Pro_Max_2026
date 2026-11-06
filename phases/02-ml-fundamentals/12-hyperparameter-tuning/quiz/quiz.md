# 测验 · 超参数调整（Hyperparameter Tuning）

> **阶段 02 · 机器学习基础 · 第 12 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/tuning.py](../code/tuning.py) ｜ 代码讲解：[code/tuning.讲解.md](../code/tuning.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 参数 vs 超参数 | 参数在训练中学出来（权重、分裂阈值）；超参数在训练前设定，控制"怎么学"（学习率、树深、正则强度） |
| 2 | Grid Search | 穷举所有组合，成本随超参数个数**指数增长**（6 个超参 × 5 个取值 = 15,625 次）；重要维度上只得到很少的不同取值 |
| 3 | Random Search | 从分布中采样；有效维度低时（通常只有 1–2 个超参真正重要），同样预算下在重要维度上覆盖更密（Bergstra & Bengio, 2012） |
| 4 | 采样尺度 | 学习率、正则强度用 **log-uniform**：0.001→0.01 与 0.1→1.0 同样重要；线性采样会把预算浪费在大值一端 |
| 5 | Bayesian Optimization | 代理模型（通常是高斯过程，给出预测均值 + 不确定性）+ 采集函数（EI / UCB / PI）决定下一个评估点，在利用与探索之间权衡 |
| 6 | 早停与剪枝 | Patience 早停、Median pruning、Hyperband（先给大量配置小预算，逐轮淘汰并给幸存者加预算） |
| 7 | 超参数重要性 | 学习率几乎总是最重要；迭代次数用早停决定而不是去搜；先调重要的，其余保持默认 |
| 8 | 交互作用 | Boosting 中学习率与树的数量强相关：学习率小就需要更多树，必须一起调 |
| 9 | 验证集过拟合与嵌套 CV | 试验成千上万次等于在验证集上训练；嵌套 CV 内层选超参、外层评估整个调参流程 |
| 10 | 常见错误 | 预处理泄漏（不放进 Pipeline）、搜索范围太窄（最优值落在边界）、忽略交互、不用早停 |

### 核心技能（能动手做到）

- [ ] 用 `itertools.product` + `dict(zip(keys, combo))` 实现网格搜索，并能算出任意网格的评估次数
- [ ] 实现支持 `int` / `float` / `log_float` / 类别列表的采样器，并用模拟验证 log-uniform 下各数量级的采样概率
- [ ] 读懂并能复现 GP 后验均值/方差的 Cholesky 解法，以及 EI 公式 `(μ − y*)·Φ(z) + σ·φ(z)`
- [ ] 用"截至当前的最优值"（best-so-far）曲线比较不同搜索方法的收敛速度
- [ ] 从零实现 successive halving（Hyperband 的基本单元），并算出它相对全预算的计算量
- [ ] 识别"最优超参数落在搜索边界"并据此扩大搜索范围
- [ ] 写出嵌套交叉验证的流程，说明外层分数估计的是什么

---

## 二、基础自测（选择题）

**Q1.** 2 个超参数、预算 9 次评估。若只有学习率真正影响结果，网格搜索（3×3）与随机搜索分别能尝试多少个**不同的学习率**？

- A. 9 和 9
- B. 3 和 9
- C. 3 和 3
- D. 9 和 3

**Q2.** 学习率在 `[0.001, 1.0]` 上做 **log-uniform** 采样，采到 `< 0.01` 的概率约为：

- A. 0.9%
- B. 10%
- C. 33%
- D. 50%

**Q3.** 讲义说"60 次随机试验有 95% 的概率找到接近最优的点"。这句话背后的计算 `1 − 0.95⁶⁰ ≈ 0.954`，最准确的含义是：

- A. 60 次后，最佳结果的分数一定在最优分数的 95% 以上
- B. 只要有一个"占搜索空间体积 5% 的最优区域"，60 次独立均匀采样中至少有一次落入该区域的概率约为 95%
- C. 60 次随机搜索一定优于 60 次网格搜索
- D. 随机搜索 60 次后会收敛到全局最优

**Q4.** 当前最优观测值 `y* = −0.5`（越大越好）。候选 A：GP 预测 `μ = −0.5, σ = 0.3`；候选 B：`μ = −0.45, σ = 0.01`。按 EI（Expected Improvement）应选：

- A. B，因为它的预测均值更高
- B. A，因为它的不确定性大，期望提升更大
- C. 两者 EI 相同
- D. 都不选，EI 均为 0

**Q5.** 81 个配置做 successive halving（η = 3）：先各训练 1 个 epoch，保留前 1/3 并把预算乘 3，直到只剩 1 个配置（最后一个配置训练满 81 个 epoch）。总共消耗的 epoch 数约为：

- A. 81
- B. 405
- C. 1,215
- D. 6,561

**Q6.** 嵌套交叉验证中，外层折上的分数估计的是：

- A. 某一组固定超参数的泛化性能
- B. "在内层用 CV 选超参数 + 用选出的超参训练"这一整个流程的泛化性能
- C. 内层 CV 中最好那一组超参数的验证分数
- D. 训练集上的拟合程度

**Q7.** 本节代码 `demo_grid_search()` 的最优结果是 `{'n_estimators': 100, 'learning_rate': 0.3, 'max_depth': 2}`，网格为 `n_estimators ∈ {20, 50, 100}`、`learning_rate ∈ {0.01, 0.05, 0.1, 0.3}`、`max_depth ∈ {2, 3, 5}`。最应该做的下一步是：

- A. 直接采用这组超参数上线
- B. 缩小网格，在这组值附近做更细的搜索
- C. 三个最优值都落在网格边界上，应扩大搜索范围（更多树、更大的学习率、更浅的树）后再搜
- D. 换用更复杂的模型

---

## 三、动手 / 代码题

**Q8.** 阅读 `sample_param`：

```python
def sample_param(spec, rng):
    if isinstance(spec, list):
        return rng.choice(spec)
    name, low, high = spec[0], spec[1], spec[2]
    if name == "int":
        return rng.randint(low, high + 1)
    if name == "float":
        return rng.uniform(low, high)
    if name == "log_float":
        return np.exp(rng.uniform(np.log(low), np.log(high)))
    return low
```

(1) 对代码中实际使用的 `("log_float", 0.005, 0.5)`，采到 `learning_rate < 0.05` 的理论概率是多少？如果改成 `("float", 0.005, 0.5)` 呢？写一段代码用 10 万次采样验证。
(2) `"int"` 分支为什么是 `high + 1`？
(3) 对类别列表，`rng.choice(spec)` 返回值的类型可能与列表元素的原始类型不同，这在什么情况下会出问题？

**Q9.** `SimpleBayesianOptimizer` 用下面的函数近似标准正态 CDF：

```python
    @staticmethod
    def _norm_cdf(x):
        return 0.5 * (1 + np.vectorize(lambda v: np.tanh(v * 0.7978845608))(x))
```

(1) `0.7978845608` 是什么数？这个近似在哪里误差最大，大约多大？
(2) `np.vectorize` 在这里有必要吗？
(3) 用标准库 `math.erf` 写一个精确版本（要求支持 NumPy 数组输入）。

**Q10.** `demo_random_search()` 依次以 `n_iter = 10, 25, 50, 100` 调用 `random_search`（种子都是 42），之后又以 `n_iter=100` 再调用一次来打印最优参数。

(1) 为什么输出的 `best_mse` 随预算**单调不增**？各次调用之间是什么关系？
(2) 这段演示一共训练了多少个模型？有多少是重复计算？
(3) 利用文件中已有的 `convergence_curve`，改写成只跑一次 100 次搜索就能打印 4 个预算下的结果。

**Q11.**（讲义练习 2 的核心）实现 `successive_halving(configs, evaluate, min_budget=1, eta=3)`：每轮用当前预算评估所有幸存配置，保留前 `1/eta`，预算乘以 `eta`，直到只剩一个配置；返回最优配置、它的分数和总消耗预算。用 81 个 log-uniform 采样的学习率和一个合成的"带学习曲线"的目标函数测试，并与全预算方案对比计算量。

---

## 四、面试高频题

**Q12.**（基础必考）比较 Grid Search、Random Search、Bayesian Optimization 的原理、优缺点和适用场景。为什么说"随机搜索通常优于网格搜索"？

**Q13.**（原理深挖）讲一讲基于高斯过程的贝叶斯优化：代理模型给出了什么？核函数和长度尺度起什么作用？EI 的公式是什么，为什么它能自动平衡探索与利用？它有哪些局限，Optuna 默认用的又是什么？

**Q14.**（工程实践）你跑了 500 次超参数试验，最好的验证集分数比默认参数高了 2%。你会如何确认这个提升是真的？如何向别人报告最终性能？

**Q15.**（场景设计 · 结合深度学习 / 大模型）你要为一个 Transformer 模型（或一次 LLM 微调）调超参数，单次训练要几个小时，GPU 预算有限。请给出调参策略：先调什么、如何设置搜索空间、如何节省算力。

**Q16.**（追问型）讲义中给出了下面的 Optuna 剪枝示例，并称"通常能节省 40–60% 的计算"。这段代码真的能剪掉试验吗？如果不能，应该怎么改？

```python
    model = GradientBoostingRegressor(**params)
    scores = cross_val_score(model, X_train, y_train, cv=3,
                             scoring="neg_mean_squared_error")
    mean_score = -scores.mean()

    trial.report(mean_score, step=0)
    if trial.should_prune():
        raise optuna.TrialPruned()

    return mean_score

pruner = optuna.pruners.MedianPruner(n_startup_trials=10, n_warmup_steps=5)
```

---

## 五、参考答案与解析

### Q1 — 答案：B

3×3 网格里学习率只有 3 个不同取值，每个重复 3 次（只变化了不重要的那个超参数），等于浪费了 6 次评估；随机搜索每次都采一个新的学习率，9 次就有 9 个不同取值。这正是讲义中"低有效维度"论证的核心。

### Q2 — 答案：C

log-uniform 意味着 `log10(lr)` 在 `[−3, 0]` 上均匀分布，`lr < 0.01` 对应 `log10(lr) < −2`，概率 = 1/3。若在 `[0.001, 1.0]` 上线性均匀采样，概率只有 `(0.01 − 0.001)/(1 − 0.001) ≈ 0.9%`（A），几乎所有样本都落在 0.1–1.0 这个数量级。

### Q3 — 答案：B

计算的含义是：每次均匀采样落入"最优 5% 区域"的概率是 0.05，60 次都落不进去的概率是 `0.95⁶⁰ ≈ 0.046`，所以至少一次落入的概率约为 95.4%。这里的"5%"是**搜索空间体积的比例**（分位数意义上的前 5%），不是"分数与最优值相差 5% 以内"——讲义的措辞 "within 5% of the optimum" 容易被误读成 A。该结论也不保证优于网格搜索（C）或收敛到全局最优（D）。

### Q4 — 答案：B

EI = `(μ − y*)·Φ(z) + σ·φ(z)`，`z = (μ − y*)/σ`。

- A：`z = 0`，EI = `0.3 × φ(0) ≈ 0.3 × 0.399 ≈ 0.120`
- B：`z = 5`，EI ≈ `0.05 × Φ(5) + 0.01 × φ(5) ≈ 0.050`

用本节代码的 `_expected_improvement` 实测分别为 0.1197 和 0.0500。A 的均值并不比当前最优更好，但不确定性大，"可能好很多"的那部分期望超过了 B 的"确定只好一点点"。这就是 EI 自动带来的**探索**。

### Q5 — 答案：B

各轮：81 个 × 1 + 27 个 × 3 + 9 个 × 9 + 3 个 × 27 + 1 个 × 81 = 81 × 5 = **405** 个 epoch。全预算方案是 81 × 81 = 6,561 个 epoch（D），约为 16 倍。讲义描述的"81 个配置、每次保留 1/3、预算乘 3"严格说是 successive halving；Hyperband 在此基础上用多个不同"起始配置数 / 起始预算"组合的 bracket 来对冲"早期表现不代表最终表现"的风险。

### Q6 — 答案：B

每个外层折都独立地在其余数据上做一次完整的内层调参，选出的超参数可能各不相同。所以外层分数评估的不是"某一组超参数"，而是"这套调参流程"的泛化能力，这正是我们最终部署时会用到的东西。C 是有选择偏差的乐观估计。

### Q7 — 答案：C

三个最优值都在网格边界：`n_estimators=100` 是最大值、`learning_rate=0.3` 是最大值、`max_depth=2` 是最小值。讲义"常见错误"明确指出：最优值落在边界说明真正的最优可能在范围之外。B 在边界附近缩小范围恰好方向相反；A、D 都跳过了这个明显的信号。另外注意 `n_estimators` 与 `learning_rate` 同时取到上限，说明在当前范围内模型"训练量"整体不足，这也是学习率与树的数量相互作用的体现。

### Q8 — 参考答案

(1) log-uniform：`P = (ln 0.05 − ln 0.005) / (ln 0.5 − ln 0.005) = ln 10 / ln 100 = 0.5`。线性均匀：`(0.05 − 0.005) / (0.5 − 0.005) ≈ 0.091`。

```python
import numpy as np

rng = np.random.RandomState(0)
s_log = np.array([sample_param(("log_float", 0.005, 0.5), rng) for _ in range(100000)])
s_lin = np.array([sample_param(("float", 0.005, 0.5), rng) for _ in range(100000)])
print(np.mean(s_log < 0.05), np.mean(s_lin < 0.05))
```

实测约 `0.5006` 与 `0.0898`。也就是说线性采样时，100 次试验里只有约 9 次会落在 0.005–0.05 这一整个数量级里。

(2) `RandomState.randint(low, high)` 的上界是**开区间**（与 Python `range` 一致），写 `high + 1` 才能采到 `high`。例如 `("int", 2, 8)` 才能包含深度 8。

(3) `rng.choice` 会先把列表转成 NumPy 数组再取样，返回的是 `numpy.int64`、`numpy.str_` 等 NumPy 标量（实测对 `[1, 2]` 返回 `numpy.int64`）。在本文件中 `spec.index(v)` 依然能找到（因为值相等），但如果把它传给对类型有严格检查的库（例如要求原生 `int` 的参数校验），或用 `json.dumps` 记录试验参数，就可能报错。稳妥的写法是 `spec[rng.randint(len(spec))]`。

### Q9 — 参考答案

(1) `0.7978845608 ≈ √(2/π)`。`Φ(x) ≈ 0.5·(1 + tanh(√(2/π)·x))` 是一个简单的 tanh 近似（GELU 的 tanh 近似公式里还多一个 `0.044715·x³` 修正项，这里省略了）。实测在 `[−6, 6]` 上与精确值的最大绝对误差约 **0.0177**，出现在 `|x| ≈ 1.73` 附近；例如 `Φ(1) = 0.8413`，近似值为 0.8314。对"挑 EI 最大的候选点"来说，这个误差一般不会改变排序太多，但作为数学函数并不精确。

(2) 没必要。`np.tanh` 本身就是逐元素的 ufunc，直接 `np.tanh(x * 0.7978845608)` 即可。`np.vectorize` 本质上是 Python 循环，对 500 个候选点每次都要逐个调用 lambda，反而更慢。

(3) 精确版本：

```python
import math
import numpy as np

_erf = np.vectorize(math.erf)          # math.erf 只接受标量，这里 vectorize 才是必要的


def norm_cdf(x):
    x = np.asarray(x, dtype=float)
    return 0.5 * (1.0 + _erf(x / math.sqrt(2.0)))


print(norm_cdf([1.0, 2.0]))            # [0.84134475 0.97724987]
```

如果环境里有 SciPy，直接用 `scipy.stats.norm.cdf` / `scipy.special.erf` 更快。

### Q10 — 参考答案

(1) 每次调用都新建 `np.random.RandomState(42)`，按相同顺序采样，而 `GBMForTuning.fit` 内部也固定了种子，训练是确定性的。所以 `n_iter=25` 的前 10 次试验与 `n_iter=10` 完全相同，以此类推——各次调用的历史是**前缀关系**，较大预算的最优值只可能更好或相同。

(2) 共训练 10 + 25 + 50 + 100 + 100 = **285** 个模型，其中只有 100 个是"新的"，其余 185 次都是重复计算（包括最后那次完全重复的 100 次搜索）。实测 `n_iter=100` 这一次就耗时约 375 秒（平均每个模型约 3.7 秒），重复的 185 次相当于白白多花了约 11 分钟。

(3) 改写：

```python
best_params, best_score, history = random_search(
    param_distributions, X_tr, y_tr, X_val, y_val, n_iter=100
)
curve = convergence_curve(history)          # curve[i] = 前 i+1 次中的最优 neg_mse
for n_iter in [10, 25, 50, 100]:
    print(f"  n_iter={n_iter:>3d}  best_mse={-curve[n_iter - 1]:.4f}")
```

结果与原来 4 次单独调用完全相同，计算量从 285 次降到 100 次（这里没有打印各预算的耗时，若需要可在 `random_search` 内记录每次试验的时间戳）。

### Q11 — 参考答案

```python
import numpy as np


def successive_halving(configs, evaluate, min_budget=1, eta=3):
    """configs: 候选超参列表；evaluate(config, budget) -> 分数（越大越好）。"""
    budget = min_budget
    total_cost = 0
    survivors = list(configs)
    while True:
        scores = [evaluate(c, budget) for c in survivors]
        total_cost += budget * len(survivors)
        if len(survivors) == 1:
            return survivors[0], scores[0], total_cost
        order = np.argsort(scores)[::-1]                     # 分数从高到低
        n_keep = max(1, len(survivors) // eta)
        survivors = [survivors[i] for i in order[:n_keep]]
        budget *= eta


# 一个"带学习曲线"的合成目标：真实质量 q 由 lr 决定，预算越大越接近 q
def evaluate(config, budget):
    q = -(np.log10(config["learning_rate"]) + 1.5) ** 2      # lr ≈ 0.03 最好
    return q * (1 - np.exp(-budget / 10)) - np.exp(-budget / 10)


rng = np.random.RandomState(42)
configs = [{"learning_rate": sample_param(("log_float", 1e-4, 1.0), rng)} for _ in range(81)]
best, score, cost = successive_halving(configs, evaluate, min_budget=1, eta=3)
print(f"best lr = {best['learning_rate']:.4f}, score = {score:.4f}")
print(f"successive halving cost = {cost} epochs, full budget = {81 * 81} epochs")
```

实测输出：

```text
best lr = 0.0280, score = -0.0031
successive halving cost = 405 epochs, full budget = 6561 epochs
```

要点：
- 以约 1/16 的计算量找到了接近最优（0.0316）的学习率。
- 这个合成目标中所有配置的学习曲线形状相同、不交叉，所以"早期排名 = 最终排名"，successive halving 不会误杀。真实训练里，学习率小的配置往往起步慢、后劲足，早期就被淘汰——这正是 Hyperband 要用多个 bracket（有的 bracket 起始预算更大、配置更少）来对冲的原因。
- 在 GBM 上，"预算"可以是树的数量；在神经网络上是 epoch 或训练步数。

### Q12 — 参考回答要点

| 方法 | 原理 | 优点 | 缺点 | 适用 |
|------|------|------|------|------|
| Grid | 穷举离散组合 | 简单、可复现、易并行 | 指数爆炸；重要维度覆盖稀疏 | 1–2 个超参（如 SVM 的 C、gamma，讲义建议对数尺度网格） |
| Random | 从分布独立采样 | 易并行；重要维度覆盖密；可随时停止 | 不利用历史结果 | 默认首选，粗搜 |
| Bayesian | 代理模型 + 采集函数顺序决策 | 样本效率高，适合昂贵评估 | 顺序性强、难大规模并行；高维/类别/条件空间较难 | 单次评估很贵、预算有限的精搜 |

- **随机优于网格的原因**：有效维度低。若 6 个超参中只有 1–2 个重要，网格把大量预算花在了不重要维度的组合上，重要维度上只有少数几个不同取值；随机搜索每次试验都给每个维度一个新值。
- **加分点**：讲义推荐的实用流程——默认值 → 20–50 次粗粒度随机搜索（配早停）→ 分析结果收窄范围 → 50–100 次贝叶斯或聚焦随机搜索 → 用最佳超参在全部训练数据上重训。
- **常见误区**：认为贝叶斯优化一定更好；它的优势在于"每次评估都很贵"的场景，评估很便宜时随机搜索 + 大量并行往往更划算。

### Q13 — 参考回答要点

- **代理模型**：高斯过程把目标函数视为随机函数，在已观测点 `(xᵢ, yᵢ)` 的条件下，对任意新点给出后验**均值 μ(x)**（最可能的分数）和**方差 σ²(x)**（有多不确定）。本节代码用 Cholesky 分解求解：`μ = K*·K⁻¹·y`，`σ² = 1 − diag(K*·K⁻¹·K*ᵀ)`；在已观测点处方差趋近噪声项（代码中加了 `1e-4` 的抖动），远离观测点时方差趋近先验值 1。
- **核函数与长度尺度**：RBF 核 `exp(−‖x − x′‖² / (2ℓ²))` 表达"相近的超参数分数相近"；ℓ 小则函数被认为变化剧烈、不确定性在观测点之间迅速回升；ℓ 大则更平滑。代码固定 `ℓ = 0.3`，并先把每个超参数**归一化到 [0, 1]**（log 型先取对数），让各维度的"距离"可比。正式实现会通过最大化边际似然来学习 ℓ 和信号方差。
- **EI**：`EI(x) = E[max(f(x) − y*, 0)] = (μ − y*)·Φ(z) + σ·φ(z)`，`z = (μ − y*)/σ`。第一项奖励"均值高"（利用），第二项奖励"不确定性大"（探索），一个公式自动权衡（Q4 的例子）。
- **局限**：GP 推断代价随观测数立方增长（Cholesky 是 O(n³)），高维（几十维以上）效果下降，类别/条件型超参数难以建模，天然是顺序的。本节代码还用 500 个随机候选点近似"最大化采集函数"，没有用梯度优化。
- **Optuna**：默认采样器是 TPE（Tree-structured Parzen Estimator），它分别对"好的试验"和"差的试验"的超参数分布建模，选择两者比值大的点；对类别和条件空间更友好，也更容易并行。
- **加分点**：能指出本节代码未对 y 做标准化（只减了均值），而核的先验方差固定为 1，当分数的尺度远小于或远大于 1 时，探索与利用的平衡会失真。

### Q14 — 参考回答要点

- **怀疑选择偏差**：500 次试验中取最大值，本身就是有偏的乐观估计；即使所有配置真实水平一样，验证集噪声也会让最大值比平均值高。
- **确认方法**：
  1. 用一个从未参与调参的**测试集**（或新时间段的数据）评估最佳配置与默认配置；
  2. 或做**嵌套交叉验证**，外层分数才是调参流程的无偏估计；
  3. 对最佳配置和默认配置在相同折上做配对比较、多换几个随机种子，看提升是否稳定、是否超出噪声水平；
  4. 检查最佳配置是否落在搜索边界、是否对某个超参数异常敏感。
- **报告方式**：报告测试集（或外层 CV）的分数及其置信区间/标准差，同时报告默认参数基线、搜索空间、试验次数与预算；不要把调参过程中的最佳验证分数当最终结果。
- **常见误区**：只报告最佳验证分数；在测试集上反复比较多个"最佳配置"后挑一个。

### Q15 — 参考回答要点

- **先调学习率**：讲义强调学习率几乎总是最重要的超参数。先固定其他超参数为常用默认值，在**对数尺度**上扫学习率（例如跨 2–3 个数量级），用短训练（少量步数）观察 loss 曲线，排除发散和明显过慢的区间。
- **调度器**：Transformer 通常用 warmup + 衰减（讲义表格中的 "Warmup + decay"），先把调度方式定下来，再调峰值学习率。
- **重要性排序**：学习率 → 权重衰减等正则 → batch size（在合理范围内重要性较低，讲义也这样归类）→ 其他结构类超参尽量用默认值。LLM 微调中还要加上训练轮数（配合早停或按验证集选 checkpoint）以及 LoRA 的秩等。
- **节省算力**：
  1. 小规模代理实验：更少的数据/步数、较小的模型上先粗搜，再把范围迁移到全量训练（注意：最优值不一定能直接迁移，最后要在目标规模上小范围确认）；
  2. 剪枝 / Hyperband / ASHA 一类方法，早期淘汰明显差的配置；
  3. 随机搜索并行跑多组，再用贝叶斯优化在收窄后的空间里精搜。
- **验证**：选出的配置用独立验证集或多种子复现，避免把一次幸运的 run 当成结论。
- **常见误区**：在线性尺度上搜学习率；只训练很少的步数就下结论，而有的配置（小学习率）起步慢后劲足。

### Q16 — 参考回答要点

- **不能剪枝**：
  1. `MedianPruner(n_warmup_steps=5)` 表示在试验汇报的步数达到 5 之前不做剪枝判断，而代码只在 `step=0` 汇报一次，所以 `should_prune()` 永远返回 False；
  2. 即使去掉 `n_warmup_steps`，汇报发生在 `cross_val_score` **已经全部跑完之后**，此时剪不剪都已经花掉了全部算力，没有任何节省。
  因此"节省 40–60% 算力"的说法在这段示例里不成立。
- **正确的做法**：在训练过程中**多次**汇报中间结果。
  - 按折汇报：手动循环 K 折，每完成一折就 `trial.report(当前平均分, step=fold)` 并检查 `should_prune()`，差的配置在第 1、2 折后就停止；
  - 按迭代汇报：对 GBM 用 `staged_predict` 或分阶段训练，每增加若干棵树在验证集上汇报一次；神经网络则每个 epoch 汇报一次；
  - `n_warmup_steps` 要小于实际汇报的步数，`n_startup_trials` 保证有足够的完整试验作为中位数参照。
- **加分点**：能说清剪枝的前提是"中间结果能预示最终结果"，以及剪枝和 Hyperband 本质上都是在做"早期淘汰"。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 06 概率和分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：正态分布的 CDF/PDF，log-uniform 分布。
- [阶段 01 · 08 优化](../../../01-math-foundations/08-optimization/docs/zh.md)：学习率在梯度下降中的作用。
- [阶段 02 · 09 模型 Evaluation](../../09-model-evaluation/docs/zh.md)：验证集、交叉验证与嵌套 CV。
- [阶段 02 · 10 偏差-方差权衡](../../10-bias-variance/docs/zh.md)：验证曲线——超参数如何在偏差与方差之间移动模型。
- [阶段 02 · 11 集成方法](../../11-ensemble-methods/docs/zh.md)：本节被调参的模型就是梯度提升，学习率与树的数量的耦合在那一节已出现。

### 本节被哪些后续内容用到
- [阶段 02 · 13 机器学习管道](../../13-ml-pipelines/docs/zh.md)：把预处理放进 Pipeline，再整体调参，杜绝泄漏。
- [阶段 03 · 06 Optimizers](../../../03-deep-learning-core/06-optimizers/docs/zh.md)：优化器自带的超参数（动量、β、权重衰减）。
- [阶段 03 · 07 正则化](../../../03-deep-learning-core/07-regularization/docs/zh.md)：Dropout、权重衰减、早停等正则化超参数。
- [阶段 03 · 09 Learning Rate Schedules 和 Warmup](../../../03-deep-learning-core/09-learning-rate-schedules/docs/zh.md)：本节学习率调度表的完整展开。
- [阶段 11 · 08 Fine-Tuning 与 LoRA & QLoRA](../../../11-llm-engineering/08-fine-tuning-lora/docs/zh.md)：LLM 微调中的学习率、秩、轮数等超参数选择。
- [阶段 19 · 44 带线性 Warmup 的余弦学习率](../../../19-capstone-projects/44-cosine-lr-warmup/docs/zh.md)：动手实现 Transformer 训练常用的学习率调度。

### 延伸关键词
`Successive Halving` · `ASHA` · `BOHB` · `TPE` · `Upper Confidence Bound` · `GP 边际似然` · `Cholesky 分解` · `Population Based Training` · `LR Range Test` · `嵌套交叉验证`
