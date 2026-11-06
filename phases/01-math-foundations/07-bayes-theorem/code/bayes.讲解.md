# 代码讲解 · bayes.py

> **所属小节**：阶段 01 · 数学基础 · 第 07 节 贝叶斯定理 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python bayes.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（`math`、`collections.defaultdict`、`random`），无需 NumPy / sklearn

---

## 1. 这份代码在考察什么

这份脚本把讲义里的每一个贝叶斯概念都落成了一段可运行的小 demo，按"公式 → 分类器 → 参数估计 → 在线更新 → 线上决策"的顺序推进：

1. **贝叶斯公式本身**：用医疗检测和垃圾邮件两个例子，亲手算出"先验 × 似然 ÷ 证据"，体会**基础率**（先验）对后验的决定性作用。
2. **朴素贝叶斯分类器**：从计数开始，实现拉普拉斯平滑、log 空间打分、log-sum-exp 归一化——这是一个"最小但完整"的文本分类流水线。
3. **MLE vs MAP**：用抛硬币说明"先验 = 正则化"，先验越强，估计越被拉向先验均值。
4. **共轭先验与序贯更新**：Beta-Binomial 更新只需做加法，并验证"序贯更新 = 批量更新"。
5. **贝叶斯 A/B 测试**：用 Monte Carlo 采样估计 `P(B > A)` 和 lift 的可信区间，并且**手写了 Gamma/Beta 采样器**，让你看到"采样"在底层是怎么实现的。

> 一句话：**贝叶斯的全部工程价值——基础率校正、正则化、在线学习、不确定性决策——都浓缩在这 345 行纯 Python 里**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `bayes(prior, likelihood, false_positive_rate)` | 函数 | 二分类假设下的贝叶斯公式 | 后验 = 似然×先验/证据；全概率公式 |
| `sequential_bayes(...)` | 函数 | 把上一次后验当作下一次先验，连续更新 | 序贯更新 |
| `NaiveBayes` | 类 | `train` 计数；`predict` 取 argmax；`predict_proba` 输出归一化概率；`top_words` 查看每类高概率词 | 朴素贝叶斯、拉普拉斯平滑、log 空间 |
| `demo_bayes_theorem` / `demo_spam_filter` | 演示函数 | 两个手算例子 | 基础率谬误 |
| `demo_naive_bayes` | 演示函数 | 12 条训练邮件、6 条测试邮件 | 文本分类 |
| `demo_mle_vs_map` | 演示函数 | 7/10 正面下 MLE 与两种 Beta 先验的 MAP | MAP = 正则化 |
| `beta_update` + `sequential_update_demo` | 函数 + 演示 | Beta 共轭更新 4 天数据，再对比批量更新 | 共轭先验 |
| `ab_test_demo` | 演示函数 | 50/1000 vs 65/1000 点击的贝叶斯 A/B 测试 | Monte Carlo、可信区间 |
| `_beta_sample` / `_gamma_sample` | 私有辅助函数 | 用两个 Gamma 样本构造 Beta 样本；Marsaglia-Tsang 算法采 Gamma | 随机采样 |

数据流：`__main__` 依次调用 6 个 demo；`demo_bayes_theorem → bayes / sequential_bayes`；`demo_naive_bayes → NaiveBayes.train → predict / predict_proba（内部共用 _log_prior、_log_likelihood）`；`ab_test_demo → _beta_sample → _gamma_sample`。

---

## 3. 逐段精讲

### 3.1 贝叶斯公式：三行代码

```python
def bayes(prior, likelihood, false_positive_rate):
    evidence = likelihood * prior + false_positive_rate * (1 - prior)
    posterior = likelihood * prior / evidence
    return posterior
```

- 第一行就是**全概率公式**：`P(+) = P(+|sick)·P(sick) + P(+|healthy)·P(healthy)`，把"阳性"这件事的两种来源（真阳性、假阳性）加起来。
- 第二行是贝叶斯公式：真阳性在全部阳性中的占比。
- 参数名直接用 `prior / likelihood / false_positive_rate`，读代码就像读公式。
- ⚠️ 刻意的简化：只处理"两个互斥假设（sick / healthy）"的情形，`P(+|healthy)` 用"假阳性率"这个名字表达。多假设时要对所有假设求和：`P(E) = Σ P(E|Hᵢ)P(Hᵢ)`。

### 3.2 序贯更新：后验变先验

```python
def sequential_bayes(prior, likelihood, false_positive_rate, num_tests):
    current = prior
    for i in range(num_tests):
        current = bayes(current, likelihood, false_positive_rate)
        print(f"  After test {i + 1}: P(sick|positive) = {current:.6f}")
    return current
```

- 核心就一行 `current = bayes(current, ...)`：**把上一轮的输出喂回去作为新的先验**。
- 两次阳性：`0.0001 → 0.009804 → 0.495`。用几率（odds）理解最直观：每次阳性的似然比是 `0.99/0.01 = 99`，先验几率 `1/9999` 乘两次 99 约等于 `0.98`，对应概率约 0.495。
- ⚠️ 隐含假设：多次检测在给定真实状态下**条件独立**。同一份样本重复检测时误差相关，这样连乘会高估后验。

### 3.3 `NaiveBayes.__init__` 与 `train`：训练就是计数

```python
class NaiveBayes:
    def __init__(self, smoothing=1.0):
        self.smoothing = smoothing
        self.class_counts = defaultdict(int)
        self.word_counts = defaultdict(lambda: defaultdict(int))
        self.class_word_totals = defaultdict(int)
        self.vocab = set()

    def train(self, documents, labels):
        for doc, label in zip(documents, labels):
            self.class_counts[label] += 1
            words = doc.lower().split()
            for word in words:
                self.word_counts[label][word] += 1
                self.class_word_totals[label] += 1
                self.vocab.add(word)
```

四个统计量各有用途：

| 属性 | 内容 | 用于计算 |
|------|------|---------|
| `class_counts[c]` | 类别 c 的文档数 | 先验 `P(c) = 文档数_c / 总文档数` |
| `word_counts[c][w]` | 词 w 在类别 c 中出现的总次数 | 似然的分子 |
| `class_word_totals[c]` | 类别 c 的总词数 | 似然的分母 |
| `vocab` | 训练集中出现过的所有词 | 平滑分母里的 `|V|` |

- `defaultdict(int)`：访问不存在的键时自动创建并赋值 `int()` 即 0，所以可以直接 `+= 1`，省掉 `if key not in d` 的判断。
- `defaultdict(lambda: defaultdict(int))`：**两层**自动创建的字典，`word_counts["spam"]["free"]` 第一次访问时两层都会自动建好。外层的工厂函数必须是"可调用对象"，所以要写 `lambda: defaultdict(int)` 而不是 `defaultdict(int)`。
- `doc.lower().split()`：最简单的分词——统一小写、按空白切分。⚠️ 没有去标点、没有词干化，`"free!"` 和 `"free"` 会被当成不同的词。
- 训练复杂度 O(总词数)，并且**可以增量调用**：再次 `train` 新数据只是继续累加计数，这正是 NB 适合在线学习的原因。
- 这里按"词频 / 该类总词数"计数，属于 **Multinomial NB**；讲义 MLE 段落里"含该词的邮件数 / 该类邮件数"是 **Bernoulli NB** 的计数方式，两者不要混淆。

### 3.4 log 先验与 log 似然（拉普拉斯平滑）

```python
    def _log_prior(self, cls):
        total_docs = sum(self.class_counts.values())
        return math.log(self.class_counts[cls] / total_docs)

    def _log_likelihood(self, word, cls):
        count = self.word_counts[cls].get(word, 0)
        total = self.class_word_totals[cls]
        vocab_size = len(self.vocab)
        return math.log(
            (count + self.smoothing) / (total + self.smoothing * vocab_size)
        )
```

- 公式：`P(w|c) = (count(w,c) + α) / (total_c + α·|V|)`，α 就是 `smoothing`。分母加 `α·|V|` 是为了让该类下所有词的概率之和仍为 1。
- 这里用 `.get(word, 0)` 而不是 `[word]`：对 `defaultdict` 用 `[]` 访问一个不存在的词会**把这个词插进字典**（副作用），`.get` 则只读不写。这是一个细心的设计。
- 方法名前的下划线 `_` 是 Python 约定的"内部方法"，提示外部调用者不要直接用。
- ⚠️ `smoothing=0` 时，任何"在某类中计数为 0"的词都会让 `math.log(0)` 抛出 `ValueError: math domain error`（Python 的 `math.log` 不返回 `-inf`）。这正是讲义练习 2 想让你发现的问题。
- ⚠️ 训练集之外的词（OOV）也会进入公式，得到 `α/(total_c + α|V|)`。由于 spam 总词数 21 少于 ham 的 29，**每个 OOV 词都会轻微偏向 spam**。sklearn 的 `CountVectorizer` 会直接丢弃 OOV 词，不存在这个偏置。
- ⚠️ 性能：每次调用都重新计算 `sum(...)` 和 `len(self.vocab)`，生产实现会在训练结束后缓存成 log 概率表。

### 3.5 `predict`：在 log 空间取 argmax

```python
    def predict(self, document):
        words = document.lower().split()
        best_class = None
        best_score = float("-inf")

        for cls in self.class_counts:
            score = self._log_prior(cls)
            for word in words:
                score += self._log_likelihood(word, cls)
            if score > best_score:
                best_score = score
                best_class = cls

        return best_class
```

- 分数 `score(c) = log P(c) + Σ log P(wᵢ|c)`，对应讲义的 `P(c)·∏P(wᵢ|c)`。**分母 `P(words)` 对所有类相同，直接省略**——只需要比较大小。
- 为什么用 log：十几个 0.01 量级的概率相乘很快会小于 float64 能表示的最小正数，发生**下溢**变成 0，所有类都是 0 就无从比较。log 把连乘变连加，并且 log 单调递增，argmax 不变。
- `float("-inf")` 作为初始最佳分数：任何真实分数都比它大，第一次比较必然更新。这是"求最大值"循环的标准写法。
- 同一个词出现两次就加两次 log 概率——这正是 Multinomial NB 用"词频"的体现。

### 3.6 `predict_proba`：log-sum-exp 归一化

```python
    def predict_proba(self, document):
        # ...（与 predict 相同地算出每个类的 log 分数 scores[cls]）
        max_score = max(scores.values())
        exp_scores = {cls: math.exp(s - max_score) for cls, s in scores.items()}
        total = sum(exp_scores.values())
        return {cls: exp_scores[cls] / total for cls in exp_scores}
```

- 目标：`P(c|x) = exp(s_c) / Σ_k exp(s_k)`，这里分母恰好就是被 `predict` 省略的"证据"。
- 直接 `math.exp(-1000)` 会得到 `0.0`，再除就是 `0/0`。**减去最大值**后最大的那一项变成 `exp(0) = 1`，其他项在 (0, 1] 之间，既不会全部下溢也不会上溢；而分子分母同乘 `exp(-max)`，比值不变。
- 这就是 softmax 的标准数值稳定写法，也叫 **log-sum-exp trick**。PyTorch 的 `softmax`、`cross_entropy` 内部做的是同一件事。
- ⚠️ `predict_proba` 和 `predict` 重复了打分循环。工程上可以让 `predict` 直接返回 `max(proba, key=proba.get)`；这里保留重复是为了让每个方法都能独立阅读。
- ⚠️ NB 的独立性假设会把相关特征重复计数，因此这里输出的"confidence"往往**过于自信**，不能直接当作校准过的概率。

### 3.7 `top_words`：查看模型学到了什么

```python
    def top_words(self, cls, n=10):
        vocab_size = len(self.vocab)
        total = self.class_word_totals[cls]
        probs = {}
        for word in self.vocab:
            count = self.word_counts[cls].get(word, 0)
            probs[word] = (count + self.smoothing) / (
                total + self.smoothing * vocab_size
            )
        return sorted(probs.items(), key=lambda x: x[1], reverse=True)[:n]
```

- 对词表中每个词算平滑后的 `P(w|c)`，按概率从高到低排序取前 n。
- `sorted(..., key=lambda x: x[1], reverse=True)`：`probs.items()` 产生 `(word, prob)` 元组，`x[1]` 取概率作为排序键。
- ⚠️ 可复现性陷阱：`self.vocab` 是 `set`，字符串的哈希在每次启动 Python 时会随机化（`PYTHONHASHSEED`），所以**集合的遍历顺序每次运行可能不同**。spam 类除 `free` 外，其余 16 个词的概率都是 `0.0308`，并列时 `sorted` 保持原有（随机的）顺序，于是"Top 5"里除了 `free` 之外的 4 个词每次运行都可能不一样。修复：排序键加上词本身作为第二关键字，`key=lambda x: (-x[1], x[0])`。
- ⚠️ "某类中 P(w|c) 最高的词"不等于"最能区分该类的词"：像 `the`、`a` 这类常见词在两类中都可能很高。更好的指标是**对数似然比** `log P(w|spam) - log P(w|ham)`。

### 3.8 演示：基础率谬误与垃圾邮件

```python
    p_lottery = p_lottery_given_spam * p_spam + p_lottery_given_ham * (1 - p_spam)
    p_spam_given_lottery = p_lottery_given_spam * p_spam / p_lottery
```

- `demo_bayes_theorem` 调用 `bayes(0.0001, 0.99, 0.01)` 得到 0.98%；`demo_spam_filter` 手写同样的公式，得到 95.5%。
- 两个例子形成鲜明对照：同样是"一个证据"，**先验 30% 时证据把后验推到 95%；先验 0.01% 时证据只能推到 1%**。

### 3.9 `demo_mle_vs_map`：先验就是正则化

```python
    mle = heads / total
    # ...
    alpha = 2
    beta = 2
    map_estimate = (heads + alpha - 1) / (total + alpha + beta - 2)
```

- MLE = 频率 `7/10 = 0.7`。
- `Beta(α,β)` 先验下，后验是 `Beta(heads+α, tails+β)`，MAP 取后验的**众数**：`(heads+α-1)/(n+α+β-2)`。
  - `Beta(2,2)`：`8/12 = 0.6667`；`Beta(10,10)`：`16/28 = 0.5714`。
- 先验 `Beta(α,β)` 可以理解为"事先看过 α-1 次正面和 β-1 次反面"的**伪计数**。伪计数越多，真实数据的话语权越小，估计越靠近先验中心 0.5——就像 L2 正则把权重拉向 0。
- 注意区分：后验**均值**是 `(heads+α)/(n+α+β)`，`Beta(2,2)` 时为 `9/14 ≈ 0.643`，和 MAP 不同。

### 3.10 共轭更新与序贯更新

```python
def beta_update(alpha, beta_param, successes, failures):
    return alpha + successes, beta_param + failures
```

```python
    for successes, failures, description in batches:
        alpha, beta_param = beta_update(alpha, beta_param, successes, failures)
        mean = alpha / (alpha + beta_param)
        # ...
        variance = (alpha * beta_param) / ((alpha + beta_param) ** 2 * (alpha + beta_param + 1))
        std = variance ** 0.5
```

- 整个"贝叶斯推断"就是一行加法——这就是**共轭先验**的魅力：先验和后验同属 Beta 分布族，不需要积分或采样。
- 变量名用 `beta_param` 而不是 `beta`，避免和"Beta 分布"这个概念、以及可能导入的同名函数混淆。
- 方差公式 `αβ / ((α+β)²(α+β+1))`：随着数据增加，`α+β` 变大，标准差从 `0.1307` 一路降到 `0.0762`——**均值在摆动，但不确定性单调下降**。
- 最后从 `Beta(1,1)` 出发，一次性加上 4 天的总成功数 21 和总失败数 19，得到 `Beta(22, 20)`，验证 `Sequential and batch give the same result: True`。加法满足交换律、结合律，所以顺序无关。
- ⚠️ 讲义中的日期编号（Day 1 无数据、Day 2 观察 7 正 3 反）与代码（Day 1 就是 7 正 3 反，并多了 Day 3、Day 4）略有不同，数值上不矛盾。

### 3.11 贝叶斯 A/B 测试

```python
    import random as rng
    rng.seed(42)

    a_clicks, a_views = 50, 1000
    b_clicks, b_views = 65, 1000

    a_alpha, a_beta = 1 + a_clicks, 1 + (a_views - a_clicks)
    b_alpha, b_beta = 1 + b_clicks, 1 + (b_views - b_clicks)
    # ...
    for _ in range(n_samples):
        sample_a = _beta_sample(a_alpha, a_beta, rng)
        sample_b = _beta_sample(b_alpha, b_beta, rng)
        if sample_b > sample_a:
            b_wins += 1

    p_b_better = b_wins / n_samples
```

- 后验：A 为 `Beta(51, 951)`，B 为 `Beta(66, 936)`。`P(B>A)` 没有简单闭式解，于是**各采 10 万个样本，数 B 赢的比例**——这就是 Monte Carlo 积分。
- 决策规则：`> 0.95` 上线 B；`< 0.05` 上线 A；否则继续收集数据。本次结果约 0.92，落在中间。
- `import random as rng` 把**整个模块**起了个别名，然后作为参数 `rng_module` 传给采样函数——Python 中模块也是对象，只要有 `.random()`、`.gauss()` 方法就能用（鸭子类型）。这样以后想换成 `random.Random(42)` 实例也无需改采样函数。
- ⚠️ `rng.seed(42)` 设置的是**全局** `random` 模块的种子，会影响程序中其他使用 `random` 的代码。更干净的做法是 `rng = random.Random(42)` 创建独立实例。

Lift（相对提升）与可信区间：

```python
    lifts = []
    rng.seed(42)
    for _ in range(n_samples):
        sa = _beta_sample(a_alpha, a_beta, rng)
        sb = _beta_sample(b_alpha, b_beta, rng)
        if sa > 0:
            lifts.append((sb - sa) / sa)
    lifts.sort()
    median_lift = lifts[len(lifts) // 2]
    low = lifts[int(len(lifts) * 0.05)]
    high = lifts[int(len(lifts) * 0.95)]
```

- 重新 `seed(42)` 后再采一遍，得到与上一段完全相同的样本序列，计算 `(B-A)/A`。
- 排序后取第 5% 和第 95% 位置的值，就是 **90% 等尾可信区间**（equal-tailed credible interval），中间位置是中位数。
- 区间 `[-3.7%, 75.0%]` 跨过 0：B 很可能更好，但"其实更差"的可能性仍不可忽略——这和 `P(B>A)≈0.92` 给出的结论一致。
- ⚠️ 两遍采样重复了 20 万次 Beta 采样；其实第一遍就可以同时记录 `P(B>A)` 和 lift。另外，可以用标准库现成的 `random.betavariate`，这里手写只是为了教学。

### 3.12 手写 Beta / Gamma 采样器

```python
def _beta_sample(alpha, beta_param, rng_module):
    x = _gamma_sample(alpha, rng_module)
    y = _gamma_sample(beta_param, rng_module)
    if x + y == 0:
        return 0.5
    return x / (x + y)
```

- 数学事实：若 `X ~ Gamma(α)`、`Y ~ Gamma(β)` 独立，则 `X/(X+Y) ~ Beta(α, β)`。所以 Beta 采样被归约为两次 Gamma 采样。
- `x + y == 0` 是防御性分支，在正常参数下几乎不会触发。

```python
def _gamma_sample(shape, rng_module):
    if shape <= 0:
        raise ValueError("Gamma shape parameter must be positive")
    if shape < 1:
        return _gamma_sample(shape + 1, rng_module) * rng_module.random() ** (1.0 / shape)

    d = shape - 1.0 / 3.0
    c = 1.0 / (9.0 * d) ** 0.5

    while True:
        x = rng_module.gauss(0, 1)
        v = (1 + c * x) ** 3
        if v <= 0:
            continue
        u = rng_module.random()
        if u < 1 - 0.0331 * x ** 4:
            return d * v
        if math.log(u) < 0.5 * x ** 2 + d * (1 - v + math.log(v)):
            return d * v
```

- 这是 **Marsaglia–Tsang（2000）** 的拒绝采样算法：先采一个标准正态 `x`，构造候选 `d·v`，再用均匀数 `u` 决定接受与否。
  - `u < 1 - 0.0331·x⁴` 是"快速接受"的挤压测试（squeeze），大多数样本在这里就被接受，不用算 log。
  - 第二个条件是精确的接受判据。
  - `v <= 0` 的候选直接丢弃（`continue`）重来。
- `shape < 1` 时用"提升"技巧：`Gamma(a) = Gamma(a+1) · U^(1/a)`，通过递归调用一次 `shape+1` 实现。
- ⚠️ 本 demo 的形状参数都远大于 1，`shape<1` 分支不会走到；它的存在是为了让函数通用。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯标准库实现 NB 和采样器 | 每一步都看得见：计数、平滑、log、归一化、拒绝采样 | 慢；生产用 `sklearn.naive_bayes.MultinomialNB`、`numpy.random.Generator.beta` |
| log 空间打分 | 避免概率连乘下溢 | 需要在输出概率时做 log-sum-exp |
| 拉普拉斯平滑 α=1 | 避免零概率"一票否决" | α 是超参数，应在验证集上调；OOV 词最好直接忽略 |
| `defaultdict` 存计数 | 代码短、无需判断键是否存在 | `[]` 访问会悄悄插入新键，读取时要用 `.get` |
| 共轭先验 Beta-Binomial | 后验闭式解，更新只需加法 | 只适用于特定似然；一般模型需要 MCMC / 变分推断 |
| Monte Carlo 估计 `P(B>A)` | 简单通用，任何后验都适用 | 有采样误差（10 万样本时约 ±0.001 量级）；可用向量化加速 |
| 固定随机种子 42 | 结果可复现 | 设的是全局种子，会影响其他代码；推荐 `random.Random(seed)` 实例 |
| `vocab` 用 `set` | O(1) 去重与查询 | 遍历顺序受哈希随机化影响，`top_words` 并列时结果不稳定 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 默认参数 | `def __init__(self, smoothing=1.0)`、`def top_words(self, cls, n=10)` | 调用时可省略，使用默认值 |
| `set` | `self.vocab = set()`；`self.vocab.add(word)` | 无序、不重复的集合，查找 O(1) |
| 字符串方法链 | `doc.lower().split()` | 先转小写，再按空白切分为列表 |
| 字符串乘法 | `"=" * 60` | 重复字符串 60 次，打印分隔线 |
| `zip` + 元组解包 | `for doc, label in zip(documents, labels)` | 两个列表按位置配对遍历 |
| 多变量解包 | `for successes, failures, description in batches`；`alpha, beta_param = beta_update(...)` | 一次拆开元组的多个元素；函数可"返回多个值"（实为元组） |
| `_` 占位变量 | `for _ in range(n_samples)`；`sum(s for s, _, _ in batches)` | 表示"这个值用不到" |
| `collections.defaultdict` | `defaultdict(int)`、`defaultdict(lambda: defaultdict(int))` | 访问不存在的键时用工厂函数自动创建默认值 |
| `lambda` 匿名函数 | `lambda: defaultdict(int)`、`key=lambda x: x[1]` | 一行定义的小函数，常用作工厂或排序键 |
| `dict.get(key, default)` | `self.word_counts[cls].get(word, 0)` | 键不存在时返回默认值，且不修改字典 |
| 字典推导式 | `{cls: math.exp(s - max_score) for cls, s in scores.items()}` | 一行构造新字典 |
| 生成器表达式 | `sum(1 for l in train_labels if l == 'spam')` | 带条件的计数，不建中间列表 |
| `sorted` + `key` + `reverse` | `sorted(probs.items(), key=lambda x: x[1], reverse=True)[:n]` | 按自定义键降序排序，再切片取前 n 个 |
| `float("-inf")` | `best_score = float("-inf")` | 负无穷，作为"求最大值"的初始值 |
| f-string 格式符 | `{posterior:.4f}`、`{current:.6f}`、`{median_lift:.1%}` | `.4f` 保留 4 位小数；`.1%` 乘以 100 并加 `%`，保留 1 位 |
| 下划线命名约定 | `_log_prior`、`_beta_sample` | 单下划线表示"内部使用"，不是强制私有 |
| 函数内 `import ... as` | `import random as rng` | 局部导入并起别名；模块本身也是对象，可以当参数传递 |
| `while True` + `continue` | `_gamma_sample` 的拒绝采样循环 | 无限循环直到满足条件 `return`；`continue` 跳过本轮 |
| `raise` 异常 | `raise ValueError("Gamma shape parameter must be positive")` | 参数非法时主动报错 |
| 递归 | `_gamma_sample(shape + 1, rng_module)` | 函数调用自身，把 shape<1 归约到 shape≥1 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 demo，被导入时不执行 |

---

## 6. 运行结果解读

实际运行（`timeout 60 python3 bayes.py`，耗时约 0.7 秒），关键输出如下：

```text
  P(sick | positive):            0.0098 (0.98%)
  After test 1: P(sick|positive) = 0.009804
  After test 2: P(sick|positive) = 0.495000      ← 两次独立阳性，后验约 50%

  P(spam | 'lottery'):     0.9554 (95.5%)        ← 先验 30% 时，一个词就推到 95%

  Training: 12 documents (5 spam, 7 ham)
  Vocabulary size: 44
    'free money waiting for you'        -> spam (confidence: 0.968)
    'meeting rescheduled to friday'     -> ham (confidence: 0.638)   ← 3 个 OOV 词偏向 spam，拉低置信度
    'you won a free prize'              -> spam (confidence: 0.968)
    'please review the attached report' -> ham (confidence: 0.983)
    'urgent free offer claim now'       -> spam (confidence: 0.992)
    'can we discuss the project update' -> ham (confidence: 0.957)

  Top 5 spam indicator words:
    free: 0.0923          ← (5+1)/(21+44)，5 封垃圾邮件都含 free
    prize: 0.0308         ← 以下 4 个都是 (1+1)/65 的并列项，每次运行可能不同
    ...
  Top 5 ham indicator words:
    review: 0.0411        ← (2+1)/(29+44)
    attached: 0.0411
    ...

  MLE estimate: 0.7000
  Beta(2,2)   MAP estimate: 0.6667
  Beta(10,10) MAP estimate: 0.5714   ← 先验越强，越被拉向 0.5

  Day 1: Beta(8, 4)   mean 0.6667  std 0.1307
  Day 2: Beta(13, 9)  mean 0.5909  std 0.1025
  Day 3: Beta(16, 16) mean 0.5000  std 0.0870
  Day 4: Beta(22, 20) mean 0.5238  std 0.0762   ← 均值摆动，std 单调下降
  Sequential and batch give the same result: True

  Posterior A: Beta(51, 951), mean = 0.0509
  Posterior B: Beta(66, 936), mean = 0.0659
  P(B > A) = 0.9227
  Decision: Keep collecting data            ← 0.05 < 0.92 < 0.95
  Median lift: 29.6%
  90% credible interval: [-3.7%, 75.0%]     ← 区间跨 0，证据还不够
```

解读要点：

- **`'meeting rescheduled to friday'` 只有 0.638**：ham/spam 分数比 = 先验 `7/5=1.4` × `meeting` 的 `(2/73)/(1/65)≈1.78` × 三个 OOV 词各 `65/73≈0.89`，合计约 1.76，换算成概率约 0.638。
- **Top words 的并列项不稳定**：用 `PYTHONHASHSEED=1/2/3` 分别运行，spam 的第 2–5 名依次出现过 `today/won/now/you`、`claim/ticket/win/urgent` 等不同组合，ham 的后 3 名也会变化——原因见 3.7 节。其余输出在任何运行下都相同（A/B 部分由 `seed(42)` 固定）。
- **`P(B>A)=0.9227`**：用 NumPy 以 200 万样本独立估计约为 0.924，说明 10 万样本的 Monte Carlo 误差在千分位量级。讲义中"97% chance B is better"只是说明性的措辞，并非本数据的结果。

---

## 7. 动手改一改

1. **（入门）** 用 `sequential_bayes(0.0001, 0.99, 0.01, 3)` 看第三次阳性后的后验（应为 `0.989800`），并改用几率形式 `odds *= 99` 手算验证。
2. **（入门）** 讲义练习 2：分别用 `smoothing=0.01, 0.1, 1.0, 10.0` 训练，打印 `top_words("spam", 5)`，观察 α 越大概率分布越"平"；再试 `smoothing=0` 并 `predict("free meeting")`，复现 `ValueError`。
3. **（进阶）** 在 `_log_likelihood` 调用前跳过 OOV 词（`if word not in self.vocab: continue`），比较 `'meeting rescheduled to friday'` 的置信度变化；并把 `top_words` 的排序键改为 `(-prob, word)` 使输出可复现。
4. **（进阶）** 讲义练习 3：增加"消息长度（short/long）"特征，统计 `P(short|spam)`、`P(short|ham)`（同样做平滑），在打分中加上 `log P(length_bucket|c)`。
5. **（进阶）** 新增方法 `log_likelihood_ratio(word)` 返回 `log P(w|spam) - log P(w|ham)`，按它排序找出真正"最有区分度"的词，并与 `top_words` 结果对比。
6. **（挑战）** 用 `random.betavariate` 或 NumPy 向量化重写 A/B 测试，一次采样同时算出 `P(B>A)`、lift 中位数和 90% 区间；再实现 Thompson sampling：模拟两个真实点击率 5% 与 6.5% 的按钮，每轮从后验各采一个样本选较大者展示，观察 1 万轮后流量分配比例。

---

## 8. 常见坑

- **混淆 `P(E|H)` 与 `P(H|E)`**：99% 的灵敏度不等于阳性后 99% 患病，必须乘上先验并除以证据。
- **零概率与 `math.log(0)`**：`smoothing=0` 时直接 `ValueError`；任何概率连乘场景都要考虑平滑或 `-inf` 处理。
- **对 `defaultdict` 用 `[]` 读取**：会悄悄插入新键、改变字典大小；只读时用 `.get(key, 0)`，本文件正是这么做的。
- **把 NB 的 confidence 当真实概率**：独立性假设导致输出过于极端，需要校准后才能用于阈值决策。
- **集合遍历顺序不确定**：`set` 中字符串的顺序受哈希随机化影响，排序遇到并列值时结果不可复现；排序键要加二级关键字。
- **混淆 MAP 与后验均值**：`Beta(9,5)` 的众数是 0.667、均值是 0.643；MAP 取众数。
