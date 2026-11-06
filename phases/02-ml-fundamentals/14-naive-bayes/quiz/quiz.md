# 测验 · 朴素贝叶斯（Naive Bayes）

> **阶段 02 · 机器学习基础 · 第 14 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/naive_bayes.py](../code/naive_bayes.py) ｜ 代码讲解：[code/naive_bayes.讲解.md](../code/naive_bayes.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 贝叶斯公式用于分类 | `P(类\|特征) ∝ P(特征\|类)·P(类)`；分母 `P(特征)` 对所有类相同，比较时可以忽略 |
| 2 | 朴素（条件独立）假设 | 给定类别后各特征相互独立：`P(w₁…wₙ\|c) = Π P(wᵢ\|c)`，把不可估计的联合分布拆成 n 个只需计数的一维分布 |
| 3 | 为什么"错的假设"也好用 | 分类只需要排序正确而非概率准确；强假设带来高偏差、低方差；相关特征的重复计数往往同时作用于正确类别 |
| 4 | 三种变体 | Multinomial（词频/计数，长文本）、Bernoulli（出现与否，短文本，会惩罚"缺席"）、Gaussian（连续特征，每类每特征一个均值和方差） |
| 5 | Laplace 平滑 | `(count + α) / (total + α·V)`，避免一个没见过的词让整类概率归零；等价于对词分布加对称 Dirichlet 先验；α 是要调的超参数 |
| 6 | 对数空间计算 | 连乘许多小于 1 的数会下溢为 0；取对数后变成求和，预测就是 `X @ log θᵀ + log prior`，一次矩阵乘法 |
| 7 | 生成式 vs 判别式 | NB 建模 `P(X\|Y)` 和 `P(Y)`（生成式）；逻辑回归直接建模 `P(Y\|X)`（判别式）；小数据 NB 占优，大数据 LR 反超 |
| 8 | 概率校准差 | NB 的概率往往过于极端（接近 0/1），需要可靠概率时用 `CalibratedClassifierCV`（sigmoid / isotonic）校准 |
| 9 | 失败场景 | XOR 式的特征交互、强相关且证据方向相反的特征、超大训练集；表格数据少量强相关特征时优先考虑 LR 或树模型 |

### 核心技能（能动手做到）

- [ ] 手算讲义中的 spam 例子：带 α=1 平滑的条件概率、两个类别的对数得分，并判断胜者
- [ ] 不用 sklearn 从零实现 `MultinomialNB`（fit 计数 + 平滑 + 取对数；predict 一次矩阵乘法），并验证与 `sklearn.naive_bayes.MultinomialNB` 的 `feature_log_prob_` 完全一致
- [ ] 从零实现 `GaussianNB`：每类每特征估计均值和方差，在对数空间计算高斯对数似然并加上 log 先验
- [ ] 实现数值稳定的 `predict_proba`：先减去每行最大值再 `exp` 和归一化（log-sum-exp 技巧）
- [ ] 在 MultinomialNB 基础上扩展出 `BernoulliNB`，正确处理"词缺席"的 `log(1−p)` 项
- [ ] 根据特征类型（计数 / 二值 / 连续）选择 NB 变体，并说清 MultinomialNB 为什么不能吃负数特征
- [ ] 用混淆矩阵手算每类 precision / recall / F1，并解释为什么垃圾邮件过滤不能只看 accuracy

---

## 二、基础自测（选择题）

**Q1.** 朴素贝叶斯的"朴素"假设，准确地说是：

- A. 所有特征彼此无条件独立
- B. 在给定类别的条件下，各特征相互独立
- C. 每个类别的先验概率相等
- D. 每个特征都服从正态分布

**Q2.** 讲义例子中，spam 类里 "free" 出现 80 次，spam 类总词数 150，词表大小 3。使用 α=1 的 Laplace 平滑，`P(free | spam)` 等于：

- A. `80 / 150`
- B. `81 / 151`
- C. `81 / 153`
- D. `81 / 450`

**Q3.** 用 **Multinomial** NB 对一封邮件打分时，邮件里**没有出现**词 "meeting"。这个词对 spam 和 not-spam 两个类别的对数得分有什么影响？

- A. 对两个类别都没有影响，因为它贡献 `0 · log P(meeting|c) = 0`
- B. 会降低 spam 的得分，因为 spam 里 "meeting" 很少见
- C. 会降低 not-spam 的得分，因为 not-spam 里 "meeting" 很常见，缺席是反面证据
- D. 会让两个类别的得分都变成负无穷

**Q4.** 下列"数据类型—NB 变体"的搭配中，**最不合适**的是：

- A. 新闻长文的词频向量 → MultinomialNB
- B. 短信是否包含某些词的 0/1 向量 → BernoulliNB
- C. 传感器测得的温度、振动幅度等连续值 → GaussianNB
- D. 标准化（均值 0、方差 1）后的连续特征 → MultinomialNB

**Q5.** 训练完成后，MultinomialNB 对一批样本做预测时，计算的本质是：

- A. 计算测试样本到每个训练样本的距离
- B. 一次矩阵乘法再加偏置：`X @ feature_log_prob_.T + class_log_prior_`
- C. 若干轮梯度下降，直到损失收敛
- D. 沿着一棵树从根节点走到叶子

**Q6.** 关于朴素贝叶斯与逻辑回归，下列说法**正确**的是：

- A. 两者都是判别式模型，只是损失函数不同
- B. 训练样本很少时 NB 往往更好，因为强假设带来高偏差、低方差；样本充足时 LR 通常反超
- C. NB 的概率输出比 LR 校准得更好，因此适合直接用来设阈值
- D. NB 能自动学习特征之间的相关性，LR 不能

**Q7.** 下列哪种情形下，朴素贝叶斯最可能**彻底失效**（不只是概率不准，而是排序错误）？

- A. 词表有 5 万个词、每个词单独都只提供很弱证据的文本分类
- B. 类别由两个二值特征的异或（XOR）决定，单看任一特征都与类别无关
- C. 训练集只有 100 条样本
- D. "machine" 和 "learning" 总是一起出现，并且都指向 tech 类

---

## 三、动手 / 代码题

**Q8.**（预测输出）用本节代码中的 `MultinomialNB` 复现讲义的 spam 例子：两封 spam、三封 not-spam，按类别加总后的词频正好是讲义里的 `[80, 60, 10]` 和 `[5, 10, 100]`。写出三个 `print` 的输出（保留 2 位小数即可），并说明 `predict_log_proba` 的两列分别对应哪个类别。

```python
X = np.array([[40, 30, 5], [40, 30, 5],             # spam (标签 1)
              [5, 0, 0], [0, 10, 0], [0, 0, 100]],  # not-spam (标签 0)
             dtype=float)
y = np.array([1, 1, 0, 0, 0])
m = MultinomialNB(alpha=1.0).fit(X, y)
q = np.array([[2, 1, 0]], dtype=float)              # free×2, money×1, meeting×0
print(m.predict_log_proba(q))
print(m.predict_proba(q))
print(m.predict(q))
```

**Q9.**（找 bug）有人觉得平滑会"歪曲数据"，把 α 设成了 0：

```python
X = np.array([[3, 0], [0, 2]], dtype=float)
y = np.array([0, 1])
m0 = MultinomialNB(alpha=0.0).fit(X, y)
q = np.array([[1.0, 0.0]])          # 只含第 0 个词
print(m0.predict_log_proba(q))
print(m0.predict_proba(q))
```

(a) 写出 `feature_log_prob_` 和两个 `print` 的结果。
(b) 查询样本**根本不含**第 1 个词，为什么类别 0 的得分还是坏掉了？
(c) 这时 `m0.predict(q)` 返回什么？为什么说"即使碰巧预测对了，也是错的"？

**Q10.**（解释写法）`predict_proba` 中有这样两行：

```python
        log_proba = self.predict_log_proba(X)
        log_proba -= log_proba.max(axis=1, keepdims=True)
        proba = np.exp(log_proba)
        proba /= proba.sum(axis=1, keepdims=True)
```

(a) 去掉第二行，对于对数得分 `[[-1200.0, -1210.0]]` 会得到什么？保留第二行又会得到什么？
(b) 为什么减去最大值不会改变最终概率？
(c) `keepdims=True` 去掉会怎样？

**Q11.**（扩展实现）参照本节 `MultinomialNB` 的结构，实现 `BernoulliNB(alpha=1.0)`：
- `fit` 时先把特征二值化（`X > 0`），按讲义公式 `P(wᵢ|c) = (含该词的文档数 + α) / (该类文档数 + 2α)` 估计；
- `predict_log_proba` 要同时计入"出现"的 `log p` 和"缺席"的 `log(1−p)`，并且仍然写成矩阵乘法形式；
- 用 `make_text_data` 的数据与 `sklearn.naive_bayes.BernoulliNB` 对比，验证 `feature_log_prob_` 一致。

---

## 四、面试高频题

**Q12.**（基础必考）讲一下朴素贝叶斯的原理。"条件独立"假设在文本里显然不成立，为什么它在文本分类上依然是强基线？

**Q13.**（原理深挖）朴素贝叶斯和逻辑回归都是线性分类器吗？二者的本质区别是什么？各自适合什么数据规模？

**Q14.**（原理深挖）Laplace 平滑解决什么问题？它有什么贝叶斯解释？α 太大、太小分别会怎样，怎么选？

**Q15.**（场景设计）让你用朴素贝叶斯做一个线上垃圾邮件过滤器。从特征、变体选择、类别不平衡、阈值与概率、评估指标到上线后的维护，你会怎么设计？

**Q16.**（追问型）你在特征里加入了大量彼此高度相关的特征（比如同一个词的多种拼写、n-gram 与其组成单词同时存在），NB 的效果反而变差了。为什么？NB 还有哪些典型的失败场景，怎么应对？

---

## 五、参考答案与解析

### Q1 — 答案：B

朴素假设是**条件**独立：`P(w₁, w₂ | c) = P(w₁|c)·P(w₂|c)`。A 是常见误解——无条件独立是更强、也更不合理的假设（"free" 和 "money" 在整个语料里显然相关，部分原因正是它们都和 spam 相关；给定类别后这种相关会减弱，但通常也不会消失）。C、D 分别是"先验相等"和 GaussianNB 的分布假设，不是"朴素"的含义。

### Q2 — 答案：C

`(count + α) / (total + α·V) = (80 + 1) / (150 + 1×3) = 81/153 ≈ 0.529`。分母要加 `α·V` 而不是 `α`，这样平滑后所有词的概率之和仍然为 1。D 把三个词的平滑量错算成了 `150×3`。

### Q3 — 答案：A

Multinomial NB 的对数似然是 `Σ xᵢ·log P(wᵢ|c)`，"meeting" 的计数 `xᵢ = 0`，贡献为 0，对所有类别都一样。C 描述的是 **Bernoulli NB** 的行为：它对每个词都计入"出现"的 `log p` 或"缺席"的 `log(1−p)`，缺席本身也是证据。D 只有在 `log P = −∞`（α=0 且该词在某类中从未出现）时才会出问题，而且结果不是 −∞ 而是 NaN（见 Q9）。

### Q4 — 答案：D

标准化后的特征有负数，而 MultinomialNB 把特征当成"计数"，要求非负——本节代码在 `fit` 开头就会 `raise ValueError("MultinomialNB requires non-negative feature values")`。即使平移成正数（`demo_comparison` 的 Task 2），效果也很差（实测 0.678，而 GaussianNB 为 0.989），因为"计数的相对比例"这个模型假设与连续测量值不符。A、B、C 正是讲义 "When to Use Each Variant" 表中的推荐搭配。

### Q5 — 答案：B

代码 `predict_log_proba` 就是 `X @ self.feature_log_prob_.T + self.class_log_prior_`：`(n×d) @ (d×k) + (k,)`，复杂度 O(n·d·k)。这和一层线性模型的计算完全相同，所以 NB 预测极快。A 是 KNN，C 是逻辑回归训练，D 是决策树。

### Q6 — 答案：B

讲义的对比表："Small data: Better (strong prior helps)；Large data: Worse"。A 错：NB 是生成式模型。C 恰好说反了：NB 概率校准差，LR 更好。D 也说反了：NB 假设独立、无法建模相关性，LR 能通过权重分配处理相关特征。

### Q7 — 答案：B

XOR 情形下每个特征单独与类别无关，`P(x₁|c)` 和 `P(x₂|c)` 对两类都一样，NB 只会把它们逐个相乘，永远看不到"组合"信息，结果和瞎猜差不多。A 恰好是 NB 最擅长的场景；C 是 NB 的优势区间；D 是讲义说的"相关特征重复计数，但重复计给了正确的类"，通常不影响排序。

### Q8 — 参考答案

```
[[-8.84 -3.11]]
[[0.   1.  ]]        # 精确值约为 [[0.0032 0.9968]]
[1]
```

- `classes_ = np.unique(y) = [0, 1]`，所以第 0 列是 not-spam、第 1 列是 spam。列的顺序由**排序后的标签**决定，而不是由样本出现的顺序决定。
- 先验：spam = 2/5 = 0.4，not-spam = 3/5 = 0.6，与讲义一致。平滑后的 θ 也正好是讲义的 81/153、61/153、11/153 和 6/118、11/118、101/118。
- spam 得分：`log 0.4 + 2·log(81/153) + log(61/153) ≈ −0.916 − 1.272 − 0.920 = −3.108`；not-spam：`log 0.6 + 2·log(6/118) + log(11/118) ≈ −8.842`。讲义写的 −3.109 / −8.838 是用四舍五入后的概率算的，差异只是舍入误差。
- `predict_proba`：差值约 5.73，`1 / (1 + e^{−5.73}) ≈ 0.9968`。注意这里的"概率"是在两类之间归一化的后验，不是讲义里那个未归一化的 `log P(spam | email)`。

### Q9 — 参考答案

(a) α=0 时：类别 0 的 θ = `[3/3, 0/3] = [1, 0]`，类别 1 的 θ = `[0, 1]`，于是

```
feature_log_prob_ = [[  0., -inf],
                     [-inf,   0.]]
predict_log_proba(q) → [[ nan, -inf]]
predict_proba(q)     → [[nan, nan]]
```

（`fit` 时 `np.log(0)` 还会给出 `RuntimeWarning: divide by zero`。）

(b) 矩阵乘法会把**所有词**都算进去，包括计数为 0 的词：类别 0 的得分 = `1·0 + 0·(−inf)`。在 IEEE 754 浮点里 `0 × (−inf) = NaN`，NaN 会污染整个求和。所以零概率不仅会在"出现了没见过的词"时把整类得分变成 −∞，在矩阵乘法实现中，**哪怕只是词表里存在某个零概率词，也会让该类所有样本的得分变成 NaN**。

(c) `np.argmax([nan, -inf])` 返回 0——NumPy 的 argmax 遇到 NaN 时返回第一个 NaN 的位置。这里碰巧"预测对了"，但它依赖的是 NaN 的传播规则而不是证据，换一个样本照样返回 0。修复：α 必须 > 0，最好在 `fit` 中检查 `alpha <= 0` 并直接报错。sklearn 也有同样的陷阱：当前版本 `MultinomialNB` 默认 `force_alpha=True`，`alpha=0` 会被原样使用，同样得到 NaN；只有设置 `force_alpha=False` 时才会把过小的 α 截断成 `1e-10` 并给出警告（在本环境 sklearn 1.9 中实测）。

### Q10 — 参考答案

(a) 去掉第二行：`np.exp(-1200)` 和 `np.exp(-1210)` 都下溢成 0，`0/0 = nan`，结果是 `[[nan, nan]]`。保留第二行：先变成 `[0, −10]`，`exp` 后为 `[1, 4.54e−5]`，归一化后约为 `[0.99995, 4.54e−5]`。

(b) softmax 对平移不变：`exp(aᵢ − m) / Σ exp(aⱼ − m) = e^{−m}·exp(aᵢ) / (e^{−m}·Σ exp(aⱼ))`，`e^{−m}` 分子分母约掉。减去最大值后最大项变成 `exp(0) = 1`，分母至少为 1，永远不会出现 0/0；最大项也不会上溢。这就是 **log-sum-exp 技巧**。文本里几百个词的对数似然相加，得分到几百、几千都很常见，所以这一步不是可有可无的。

(c) `log_proba.max(axis=1)` 的形状是 `(n,)`，与 `(n, k)` 相减时会按**最后一维**对齐广播：n = 1 时碰巧正确；n ≠ k 且 n > 1 时直接报形状错误；n == k 时最糟——不报错但减错了数（第 j 列减去的是第 j 个样本的最大值）。下一行的 `proba.sum(axis=1)` 同理。`keepdims=True` 让形状保持 `(n, 1)`，按行广播才正确。

### Q11 — 参考答案

```python
class BernoulliNB:
    def __init__(self, alpha=1.0):
        self.alpha = alpha

    def fit(self, X, y):
        Xb = (X > 0).astype(float)                       # 二值化：出现 / 缺席
        self.classes_ = np.unique(y)
        k, d = len(self.classes_), X.shape[1]
        self.class_log_prior_ = np.zeros(k)
        self.feature_log_prob_ = np.zeros((k, d))        # log p
        self.feature_log_neg_prob_ = np.zeros((k, d))    # log (1 - p)
        for i, c in enumerate(self.classes_):
            Xc = Xb[y == c]
            n_c = Xc.shape[0]
            self.class_log_prior_[i] = np.log(n_c / X.shape[0])
            p = (Xc.sum(axis=0) + self.alpha) / (n_c + 2 * self.alpha)
            self.feature_log_prob_[i] = np.log(p)
            self.feature_log_neg_prob_[i] = np.log(1 - p)
        return self

    def predict_log_proba(self, X):
        Xb = (X > 0).astype(float)
        # Σ [x·log p + (1−x)·log(1−p)] = x·(log p − log(1−p)) + Σ log(1−p)
        return (Xb @ (self.feature_log_prob_ - self.feature_log_neg_prob_).T
                + self.feature_log_neg_prob_.sum(axis=1)
                + self.class_log_prior_)

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_log_proba(X), axis=1)]

    def score(self, X, y):
        return np.mean(self.predict(X) == y)
```

验证（实际运行）：

```python
from sklearn.naive_bayes import BernoulliNB as SkB
Xt, yt = make_text_data(1200, 200, 42)
Xtr, Xte, ytr, yte = train_test_split(Xt, yt, 0.25, 42)
b = BernoulliNB(1.0).fit(Xtr, ytr)
sb = SkB(alpha=1.0, binarize=0.0).fit(Xtr, ytr)
np.allclose(b.feature_log_prob_, sb.feature_log_prob_)   # True
(b.predict(Xte) == sb.predict(Xte)).all()                # True
```

要点：
- 分母是"该类**文档数** + 2α"（二值变量只有两个取值），而 Multinomial 是"该类**总词数** + α·V"。
- 关键的代数变形：`x·log p + (1−x)·log(1−p) = x·(log p − log(1−p)) + log(1−p)`，于是缺席项可以预先求和成每个类别的常数，预测仍然只要一次矩阵乘法。
- 正因为多了 `Σ log(1−p)` 这一项，Bernoulli 会把"高频词没出现"当成反面证据，这是它在短文本上有时更好的原因。
- sklearn 的 `BernoulliNB` 默认 `binarize=0.0`，即同样按 `X > 0` 二值化。

### Q12 — 参考回答要点

- **原理**：由贝叶斯公式 `P(c|x) ∝ P(c)·P(x|c)`，加上条件独立假设 `P(x|c) = Π P(xᵢ|c)`，每个 `P(xᵢ|c)` 只需要计数（或估计均值方差）就能得到。训练只扫一遍数据，预测在对数空间里是一次矩阵乘法。
- **为什么好用**：
  1. **只要排序对**：分类取 argmax，概率被扭曲成 0.99999 也没关系，只要赢家没变；
  2. **高偏差、低方差**：独立假设是很强的先验，参数少、估计稳定，样本少、维度高时不容易过拟合，这正是文本分类的典型处境（几万维、样本有限）；
  3. **误差常常同向**：相关的词往往一起指向正确类别，重复计数放大的是正确的证据；
  4. **快**：可以训练上百万文档、快速迭代特征。
- **加分点**：能说出它的代价——概率校准差、特征交互完全学不到；能提到 TF-IDF + MultinomialNB 是小数据文本分类的强基线；能引用 Ng & Jordan（2001）关于生成式与判别式模型的比较。

### Q13 — 参考回答要点

- **都是线性的（Multinomial / Bernoulli 情况下）**：Multinomial NB 二分类的判别函数是 `(log θ₁ − log θ₀)·x + (log π₁ − log π₀)`，对 x 是线性的，形式和 LR 的 `w·x + b` 一模一样。Gaussian NB 在各类共享方差时边界也是线性的，各类方差不同时则是二次边界。
- **本质区别在于参数怎么来**：
  - NB（生成式）：建模 `P(x|y)` 和 `P(y)`，参数由计数/闭式公式得到，相当于"每个特征独立地"决定权重；
  - LR（判别式）：直接最大化条件似然 `P(y|x)`，权重通过迭代优化**联合**确定，能自动处理特征间的相关性（相关特征会分摊权重）。
- **数据规模**：Ng & Jordan（2001）的经典结论是，生成式的 NB 用更少的样本就能逼近它自己的渐近误差，而判别式的 LR 渐近误差更低、但需要更多样本才能达到。所以经验法则是"小数据先上 NB，数据多了、NB 进入平台期再换 LR"。
- **其他维度**：NB 训练是单遍计数、可以增量更新（新数据来了直接加计数）；LR 的概率校准更好。
- **常见误区**：说"NB 是非线性模型"或"LR 一定比 NB 好"。

### Q14 — 参考回答要点

- **问题**：某个词在某类训练数据里从未出现，最大似然估计给出 `P = 0`，一乘就让整个类别概率归零（对数下为 −∞），其他证据再强也没用。矩阵乘法实现中甚至会产生 NaN（见 Q9）。
- **做法**：`P(wᵢ|c) = (count + α) / (total + α·V)`，每个词都"预先看到" α 次。
- **贝叶斯解释**：给每个类的词分布加一个对称 Dirichlet(α) 先验，平滑后的估计就是后验均值；α=1 对应均匀先验（add-one）。α 可以理解成"伪计数"，表示你对"所有词等概率"这个先验的信心。
- **α 的影响**：α 太小 → 几乎不平滑，稀有词的概率估计方差大、容易被偶然出现带偏；α 太大 → 分布被拉向均匀，所有词的区分度都被抹平，欠拟合（讲义练习 1 要求观察这一点）。
- **怎么选**：作为超参数用交叉验证搜索（常在 0.01–10 的对数网格上）；数据越少、未登录词越多，越倾向大一些的 α；配合 TF-IDF 时常用较小的 α（讲义示例用 0.1）。
- **加分点**：提到 Lidstone 平滑（α 取任意正数的推广）；提到语言模型里也有同样的平滑问题。

### Q15 — 参考回答要点

1. **特征**：分词 → 词袋/TF-IDF；邮件标题、发件人域名、链接数量等也可以做成计数或二值特征；可以加入 n-gram。
2. **变体**：长邮件正文用 MultinomialNB（或 TF-IDF + MultinomialNB）；短文本（短信、标题）可以试 BernoulliNB（`CountVectorizer(binary=True)`）。用 sklearn `Pipeline` 把向量化和模型包在一起，避免训练/服务不一致。
3. **类别不平衡与先验**：如果训练数据里 spam 占比和线上不同，先验 `P(c)` 会偏；可以通过 `class_prior` 手动设定，或在决策阈值上补偿。
4. **阈值与概率**：误杀正常邮件的代价远高于漏掉一封垃圾邮件，所以不用 argmax，而是在"P(spam) > 阈值"上决策；NB 概率极端且校准差，要先用 `CalibratedClassifierCV`（sigmoid 或 isotonic）校准，再在验证集上按业务目标（例如"误杀率 < 0.1%"）选阈值。
5. **评估**：不能只看 accuracy（99% 都是正常邮件时全猜"正常"也有 99%）；看 spam 类的 precision / recall / F1、PR 曲线，并单独盯住"正常邮件被误杀"的比例。
6. **上线后**：垃圾邮件是对抗性的，分布持续漂移（新词、变形拼写），需要定期重训；NB 训练只是计数，可以做增量更新；未登录词靠平滑兜底；监控每日拦截率和用户的"不是垃圾邮件"反馈。
- **加分点**：提到 NB 作为第一道快速过滤，后面再接更复杂的模型（级联）。

### Q16 — 参考回答要点

- **原因：重复计数**。NB 把每个特征都当成独立证据。如果"同一信息"被 5 个高度相关的特征重复表达，它的对数似然就被加了 5 次，等价于把这条证据的权重放大了 5 倍。当所有相关特征都指向正确类别时问题不大（讲义的 "machine/learning" 例子）；但当被放大的证据**压过了其他更可靠的证据**，或者讲义所说的"相关特征给出相反证据"时，排序就会出错。这些概率也会因此变得更加极端。LR 则会在相关特征之间分摊权重，不会重复计数。
- **典型失败场景**（讲义 "When Naive Bayes Fails"）：
  1. 强特征交互 / XOR：单个特征无信息，只有组合才有信息；
  2. 高度相关但证据方向相反的特征；
  3. 训练数据非常多：独立假设的偏差成为瓶颈，判别式模型反超。
- **应对**：去重和合并冗余特征（如拼写归一化、只保留 n-gram 或单词之一）、做特征选择；需要交互时手工构造组合特征；数据充足时换 LR / 线性 SVM / 树模型；需要概率时做校准。
- **加分点**：能提到 Rennie 等人（2003）针对 NB 文本分类的改进思路（讲义延伸阅读），或者 Complement NB 用于类别不平衡的文本数据。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 07 贝叶斯定理](../../../01-math-foundations/07-bayes-theorem/docs/zh.md)：先验、似然、后验，以及朴素贝叶斯的数学起点。
- [阶段 01 · 06 概率与分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：多项分布、伯努利分布、高斯分布。
- [阶段 01 · 13 数值稳定性](../../../01-math-foundations/13-numerical-stability/docs/zh.md)：下溢、log-sum-exp 技巧。
- [阶段 02 · 03 逻辑回归](../../03-logistic-regression/docs/zh.md)：本节反复对比的判别式模型。
- [阶段 02 · 10 偏差-方差权衡](../../10-bias-variance/docs/zh.md)：解释"错误假设反而好用"的理论框架。

### 本节被哪些后续内容用到
- [阶段 02 · 09 模型 Evaluation](../../09-model-evaluation/docs/zh.md)：混淆矩阵、precision / recall / F1（本节代码最后一个演示）。
- [阶段 02 · 16 异常检测](../../16-anomaly-detection/docs/zh.md)：同样用"每个特征一个高斯分布"刻画正常数据，低密度即异常。
- [阶段 02 · 17 处理不平衡数据](../../17-imbalanced-data/docs/zh.md)：先验偏移、阈值调整与概率校准。
- [阶段 05 · 02 词袋、TF-IDF 与文本表示](../../../05-nlp-foundations-to-advanced/02-bag-of-words-tfidf/docs/zh.md)：MultinomialNB 的输入特征从哪里来。
- [阶段 05 · 05 情感分析](../../../05-nlp-foundations-to-advanced/05-sentiment-analysis/docs/zh.md)：用朴素贝叶斯做情感分类的实战。

### 延伸关键词
`Complement NB` · `Dirichlet 先验 / 伪计数` · `log-sum-exp` · `生成式 vs 判别式 (Ng & Jordan)` · `Platt scaling / isotonic 回归` · `CountVectorizer(binary=True)` · `TF-IDF` · `增量学习 partial_fit` · `高斯判别分析 (GDA/QDA)`
