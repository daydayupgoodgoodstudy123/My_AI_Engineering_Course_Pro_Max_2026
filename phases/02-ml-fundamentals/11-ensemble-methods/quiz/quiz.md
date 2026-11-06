# 测验 · 集成方法（Ensemble Methods）

> **阶段 02 · 机器学习基础 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/ensembles.py](../code/ensembles.py) ｜ 代码讲解：[code/ensembles.讲解.md](../code/ensembles.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 集成为什么有效 | N 个**独立**、准确率 p > 0.5 的分类器做多数投票，准确率 = `Σ_{k>N/2} C(N,k)·pᵏ·(1−p)^(N−k)`，随 N 增大趋近 1；前提是模型犯**不同**的错（多样性） |
| 2 | Bagging | 每个模型在一份 bootstrap 样本（有放回、与原数据同大小）上训练，再平均或投票；主要降**方差** |
| 3 | Bootstrap 与 OOB | 每份 bootstrap 约含 63.2%（1 − 1/e）的不同样本，剩下约 36.8% 是 out-of-bag，可当免费验证集 |
| 4 | 随机森林 | Bagging + 每次分裂只看随机特征子集（分类常用 √p，回归常用 p/3），降低树之间的相关性 |
| 5 | Boosting | 顺序训练，每个新模型专攻当前集成的错误，主要降**偏差**；轮数过多会拟合噪声 |
| 6 | AdaBoost | 加权误差 `err`、模型权重 `α = ½·ln((1−err)/err)`、样本权重 `w ← w·exp(−α·y·h(x))` 再归一化；最终 `sign(Σ αₜhₜ(x))` |
| 7 | Gradient Boosting | 每棵树拟合损失的负梯度（伪残差）；平方损失下就是残差 `y − F(x)`；learning rate（shrinkage）与树的数量需要一起调 |
| 8 | XGBoost / LightGBM | 正则化目标（叶子权重 L1/L2）、二阶近似、缺失值处理、列采样、加权分位数草图、缓存友好；表格数据首选 |
| 9 | Stacking | 用基模型的预测作为特征训练元学习器；元特征必须用**交叉验证的 out-of-fold 预测**生成，否则泄漏 |
| 10 | Voting | Hard voting 按标签多数；Soft voting 平均概率，利用了置信度，通常更好 |

### 核心技能（能动手做到）

- [ ] 用二项分布公式算出"21 个 60% 准确率的独立分类器"多数投票的准确率，并解释为什么真实模型达不到这个数
- [ ] 从零实现带样本权重的 `DecisionStump`（遍历特征、阈值、极性）和 `AdaBoostScratch`，手算一轮 α 与权重更新
- [ ] 从零实现按方差下降分裂的回归树，并在其上实现 `GradientBoostingScratch`，观察训练/测试 MSE 随树的数量的变化
- [ ] 用 `rng.choice(n, size=n, replace=True)` 实现 bagging，并扩展出 OOB 准确率
- [ ] 实现 out-of-fold 的 stacking：K 折生成元特征 → 训练元学习器 → 用全量数据重训基模型
- [ ] 解释并演示 learning rate 与树的数量的耦合关系（lr 减小时树要相应增多）
- [ ] 识别从零实现中的细节陷阱：`np.sign(0) = 0`、循环变量泄漏导致打印标签与模型不符、`fit` 不重置状态

---

## 二、基础自测（选择题）

**Q1.** 21 个**相互独立**、准确率均为 60% 的二分类器做多数投票，集成准确率最接近：

- A. 60%
- B. 74%
- C. 83%
- D. 98%

**Q2.** 从 n 个样本中有放回地抽 n 次构成一份 bootstrap 样本。当 n 很大时，原数据中**没有被抽中**的样本占比约为：

- A. 0%
- B. 25%
- C. 36.8%
- D. 50%

**Q3.** AdaBoost 某一轮弱学习器的加权误差 `err = 0.2`。下列说法正确的是：

- A. `α ≈ 0.693`，归一化前分错样本的权重乘以 2，分对样本的权重乘以 0.5
- B. `α ≈ 1.386`，所有样本权重都乘以 4
- C. `α ≈ 0.2`，分错样本权重乘以 1.2
- D. `α < 0`，这个弱学习器会被丢弃

**Q4.** 使用平方损失的梯度提升中，第 t 棵树拟合的目标是：

- A. 原始标签 y
- B. 上一棵树的预测值
- C. 当前集成的残差 `y − F_{t−1}(x)`
- D. 随机选取的特征子集

**Q5.** 本节代码 `demo_learning_rate_effect()` 的结果是：`lr=0.05, n_trees=200` 测试 MSE 为 0.2967，而 `lr=0.01, n_trees=500` 为 0.4652。最合理的解释是：

- A. 学习率越小越容易过拟合
- B. lr=0.01 时 500 棵树还不够，模型仍处于欠拟合，需要更多的树
- C. 树的数量超过 200 后梯度提升必然过拟合
- D. 学习率与树的数量无关，结果只是随机波动

**Q6.** Stacking 中，基模型给元学习器的特征必须用交叉验证的 out-of-fold 预测生成，主要原因是：

- A. 可以减少训练时间
- B. 基模型在自己训练过的样本上预测过于乐观，元学习器会学到"信任最过拟合的模型"
- C. 元学习器只能接受整数特征
- D. 为了让每个基模型使用不同的特征

**Q7.** 随机森林在 bagging 之外加入"每次分裂只考虑随机特征子集"，主要目的是：

- A. 降低每棵树的偏差
- B. 降低树与树之间预测的相关性，让平均后的方差更小
- C. 让每棵树都更深
- D. 替代 bootstrap 采样

**Q8.** 训练数据中有约 5% 的标签是错的。下面哪种方法最容易受影响？

- A. Bagging
- B. 随机森林
- C. AdaBoost
- D. Soft voting

---

## 三、动手 / 代码题

**Q9.** `demo_gradient_boosting()` 的运行输出如下，最后一行标的是 "GBM 100 MSE"：

```text
  n_estimators=100  train_mse=0.0623  test_mse=0.3073
  n_estimators=200  train_mse=0.0260  test_mse=0.2790

  Single tree MSE: 1.3385
  GBM 100 MSE:     0.2790
```

对应源码：

```python
    for n_est in [1, 10, 50, 100, 200]:
        model = GradientBoostingScratch(n_estimators=n_est, learning_rate=0.1)
        model.fit(X_train, y_train)
        # ...
    single_tree = SimpleRegressionTree(max_depth=3)
    # ...
    print(f"  GBM 100 MSE:     {model.mse(X_test, y_test):.4f}")
```

(1) 打印的 0.2790 实际是哪个模型的 MSE？为什么？
(2) 给出两种修正方式。

**Q10.** 运行 `demo_bagging()` 和 `demo_stacking()`（同一份数据、同一划分）会看到：

```text
  Single tree accuracy: 0.750
  Bagging (20 trees):   0.863
  ...
  Tree depth=3 accuracy: 0.825
  Tree depth=5 accuracy: 0.750
  Tree depth=7 accuracy: 0.825
```

深度 5 的树比深度 3 和 7 都差，而且恰好就是 bagging 对比用的那棵树。相关代码：

```python
    single_tree = SimpleRegressionTree(max_depth=5)
    single_tree.fit(X_train, y_train)
    single_acc = np.mean(np.sign(single_tree.predict(X_test)) == y_test)
```

`SimpleRegressionTree` 在标签为 ±1 的数据上，叶子值是叶内标签的均值。请分析这个"深度 5 反常"的原因，给出修正，并说明它对 "Variance reduction: +0.113" 这个结论有什么影响。

**Q11.** `StackingClassifier` 的元学习器训练代码如下：

```python
        for _ in range(200):
            logits = meta_features @ self.meta_weights + self.meta_bias
            preds = np.tanh(logits)
            errors = y - preds
            grad_w = -2 * meta_features.T @ errors / n
            grad_b = -2 * np.sum(errors) / n
            self.meta_weights -= self.meta_lr * grad_w
            self.meta_bias -= self.meta_lr * grad_b
```

有人说："如果损失是 `(y − tanh(z))²`，正确的梯度应该多一个 `(1 − tanh²(z))` 因子，这里写错了。"
(1) 这个说法对"均方误差"而言是否成立？
(2) 证明：对 y ∈ {−1, +1}，这段更新恰好是对损失 `L(z) = log(1 + exp(−2yz))` 做梯度下降（差一个常数因子），即一个用 ±1 标签写的逻辑回归。
(3) 这段代码之前，`meta_features` 是如何生成的？为什么不能直接用"在全部训练集上训练好的基模型"的预测？

**Q12.** 为 `BaggingClassifier` 增加 OOB（out-of-bag）准确率：训练时记录每个样本在哪些树中没有被抽中，用这些树对它的平均预测作为 OOB 预测，最后得到 `self.oob_score_`。要求：不改变原类的预测逻辑，`fit` 里要重置 `self.trees`。

---

## 四、面试高频题

**Q13.**（基础必考）对比 bagging 和 boosting：训练方式、主要降低的误差成分、对基学习器的要求、能否并行、过拟合风险、对噪声的敏感度。

**Q14.**（原理深挖）AdaBoost 的模型权重 `α = ½·ln((1−err)/err)` 是怎么来的？它最小化的是什么损失？这解释了 AdaBoost 的哪些性质？

**Q15.**（原理深挖）为什么说梯度提升是"函数空间中的梯度下降"？对二分类的对数损失，伪残差是什么？XGBoost 在经典 GBDT 上主要做了哪些改进？

**Q16.**（工程实践）给你一个几十万行的表格数据二分类任务，你会如何用 GBDT（XGBoost/LightGBM）从基线做到上线？关键超参数的调参顺序是什么？如何防止过拟合？

**Q17.**（场景设计 · 追问型）团队想在生产中用"随机森林 + XGBoost + 逻辑回归"做 stacking 再提 0.5% 的 AUC。你会如何设计训练流程，评估它是否值得？另外，LLM 应用里有哪些做法本质上也是集成？

---

## 五、参考答案与解析

### Q1 — 答案：C

`P(X ≥ 11)`，X ~ Binomial(21, 0.6)，精确计算约 **0.826**。同理 101 个分类器约 0.979。（讲义正文写的是"21 个约 74%、101 个约 84%"，用讲义自己给出的公式计算并不吻合，应以计算结果为准；作为参照，11 个分类器约为 75.3%。）要点是：只要个体优于随机且错误独立，投票准确率随 N 单调上升并趋于 1。现实中模型的错误高度相关，所以远达不到这个理论值——这就是"多样性"如此重要的原因。

### Q2 — 答案：C

某个样本在 n 次抽取中都没被抽中的概率是 `(1 − 1/n)ⁿ → 1/e ≈ 0.368`，所以每份 bootstrap 约含 63.2% 的不同样本。实测：从 1000 个样本中抽 1000 次，平均有 63.3% 的样本至少出现一次。这 36.8% 就是 OOB 样本。

### Q3 — 答案：A

`α = ½·ln(0.8/0.2) = ½·ln 4 ≈ 0.693`。权重更新 `w·exp(−α·y·h)`：分错时 `y·h = −1`，乘 `e^α = 2`；分对时 `y·h = +1`，乘 `e^{−α} = 0.5`；然后再归一化。err = 0.2 < 0.5，α 为正，D 错；只有 err > 0.5（比随机还差）时 α 才为负，而树桩会同时尝试两种极性，这种情况基本不会出现。

### Q4 — 答案：C

平方损失 `L = ½(y − F)²` 的负梯度就是 `y − F`，代码中 `residuals = y - current_pred` 正是如此。每棵树"拟合前面所有树还没拟合好的部分"，然后以 `learning_rate` 缩放后叠加。

### Q5 — 答案：B

梯度提升的"总步长"大致由 `lr × n_trees` 决定：0.5×20 = 10、0.1×100 = 10、0.05×200 = 10，而 0.01×500 = 5，只有前几组的一半，模型还没把残差拟合够，属于欠拟合。实测把树增加到 1000 棵（0.01×1000 = 10）后测试 MSE 降到 0.2932，略优于 `lr=0.05, n_trees=200` 的 0.2967。小学习率"通常泛化更好"的前提是**给足树的数量**（或者配合早停在验证集上找最佳轮数）。A、C 与结果相反；D 忽略了明显的结构性原因。

### Q6 — 答案：B

基模型（尤其是深树）在自己的训练样本上几乎全对，如果元特征用的是这种"样本内预测"，元学习器会认为最过拟合的模型最可靠，上线后在新数据上崩掉。用 K 折 out-of-fold 预测，每个元特征都来自"没见过这个样本"的模型，分布与测试时一致。

### Q7 — 答案：B

平均 N 个方差为 σ²、两两相关系数为 ρ 的模型，方差为 `ρσ² + (1−ρ)σ²/N`。只做 bagging 时，强特征会让每棵树的顶层分裂几乎相同，ρ 很高；随机特征子集迫使树之间不同，ρ 下降，第一项变小。它对单棵树的偏差往往略有增加（A 错）。

### Q8 — 答案：C

AdaBoost 每轮都提高被分错样本的权重，标签错误的样本永远"分不对"，权重会被指数级放大，后续的弱学习器都在拼命拟合噪声。讲义的方法选择表中也注明了 AdaBoost "Sensitive to outliers and noise"。Bagging / 随机森林对噪声相对稳健。

### Q9 — 参考答案

(1) 打印的是 **`n_estimators=200`** 那个模型的测试 MSE（0.2790 与上面 200 那一行完全相同）。Python 的 `for` 循环不创建新的作用域，循环结束后变量 `model` 仍指向**最后一次**迭代创建的对象，即 200 棵树的模型。标签写成 "GBM 100" 是错误的。

(2) 修正方式：

```python
# 方式一：改标签，如实反映
print(f"  GBM 200 MSE:     {model.mse(X_test, y_test):.4f}")

# 方式二：显式保存想要对比的模型
models = {}
for n_est in [1, 10, 50, 100, 200]:
    model = GradientBoostingScratch(n_estimators=n_est, learning_rate=0.1)
    model.fit(X_train, y_train)
    models[n_est] = model
    # ...
print(f"  GBM 100 MSE:     {models[100].mse(X_test, y_test):.4f}")   # 0.3073
```

延伸：由于每个模型都从头训练，这个循环其实做了 1+10+50+100+200 = 361 棵树的工作。更高效的做法是只训练 200 棵树，然后在预测时累加到第 k 棵就记录一次（sklearn 的 `staged_predict` 就是这个思路）。

### Q10 — 参考答案

**原因**：`np.sign(0) == 0`。当某个叶子里 +1 和 −1 的样本数相等时，叶子值（均值）恰好为 0，落入该叶子的测试样本预测为 0，与任何真实标签（±1）都不相等，一律算错。实测深度 5 的树在 80 个测试样本中有 **11 个**预测值恰好为 0，而深度 3 和 7 的树都没有这种情况。

**修正**：给 0 指定一个类别（或回退到训练集多数类）。

```python
pred = single_tree.predict(X_test)
single_acc = np.mean(np.where(pred >= 0, 1, -1) == y_test)
```

修正后深度 5 单棵树的准确率是 **0.8125**，与深度 3/7 的 0.825 在同一水平。

**对结论的影响**：原输出的 "+0.113" 中有约 0.0625（5 个样本）是这个平局 bug 造成的；真实的 bagging 提升约 0.05（0.8125 → 0.863）。bagging 本身不受影响，因为 20 棵树平均后几乎不会恰好为 0。同样的问题也存在于 `TreeWrapper.predict`、`AdaBoostScratch.predict`、`StackingClassifier.predict`（都直接用 `np.sign`）。这类"平局"细节在面试手写代码时经常被追问。

### Q11 — 参考答案

(1) 对**均方误差**而言，这个说法成立：`d/dz (y − tanh z)² = −2(y − tanh z)(1 − tanh² z)`，代码缺少 `(1 − tanh² z)`。所以如果作者的本意是"tanh + MSE"，那梯度确实不对。

(2) 但这段更新换个角度看是完全合理的。利用 `tanh(z) = 2σ(2z) − 1` 和 `σ(−t) = 1 − σ(t)`（σ 为 sigmoid）：

```text
L(z)  = log(1 + exp(−2yz))
dL/dz = −2y · σ(−2yz)

y = +1：dL/dz = −2σ(−2z)；而 y − tanh z = 1 − (2σ(2z) − 1) = 2 − 2σ(2z) = 2σ(−2z)
        ⇒ dL/dz = −(y − tanh z)
y = −1：dL/dz = 2σ(2z)；  而 y − tanh z = −1 − (2σ(2z) − 1) = −2σ(2z)
        ⇒ dL/dz = −(y − tanh z)
```

所以对两种标签都有 `dL/dz = −(y − tanh z)`，对 w 的梯度为 `−Xᵀ(y − tanh(Xw + b)) / n`。代码中的 `grad_w = -2 * meta_features.T @ errors / n` 恰好是它的 2 倍，等价于学习率翻倍。也就是说，这个元学习器本质上是**用 ±1 标签写的逻辑回归**（`P(y=1) = σ(2z)`），这正是 stacking 最常用的元学习器。变量名 `errors` 和系数 `-2` 容易让人误以为是 MSE。

(3) `meta_features` 是用**手写的 K 折**生成的 out-of-fold 预测：对每一折，用其余折训练一个新的基模型，只对该折做预测，填入 `meta_features[val_idx, m_idx]`。这样每个元特征都来自"没见过该样本"的模型。如果用在全量训练集上训练好的基模型直接预测训练集，深树几乎 100% 正确，元学习器会过度信任它（见 Q6）。训练完元学习器后，代码再用**全部训练数据**重训每个基模型（`self.fitted_models`），供预测时使用。

注意：这里的 K 折没有打乱（`indices = np.arange(n)`），依赖于 `train_test_split` 已经打乱过数据；而且元特征是 `np.sign` 后的硬标签，丢失了置信度信息，用连续分数通常更好。

### Q12 — 参考答案

```python
class BaggingWithOOB(BaggingClassifier):
    def fit(self, X, y):
        rng = np.random.RandomState(42)
        n = len(y)
        self.trees = []                      # 重置，防止多次 fit 累积
        oob_sum = np.zeros(n)                # 每个样本累计的 OOB 预测
        oob_cnt = np.zeros(n)                # 每个样本作为 OOB 的次数

        for _ in range(self.n_estimators):
            idx = rng.choice(n, size=n, replace=True)
            tree = SimpleRegressionTree(max_depth=self.max_depth)
            tree.fit(X[idx], y[idx])
            self.trees.append(tree)

            oob_mask = np.ones(n, dtype=bool)
            oob_mask[idx] = False            # 被抽中过的样本不是 OOB
            if oob_mask.any():
                oob_sum[oob_mask] += tree.predict(X[oob_mask])
                oob_cnt[oob_mask] += 1

        has_oob = oob_cnt > 0                # 极少数样本可能每次都被抽中
        oob_pred = np.where(oob_sum[has_oob] >= 0, 1, -1)
        self.oob_score_ = np.mean(oob_pred == y[has_oob])


X, y = make_classification_data(n_samples=400)
X_train, X_test, y_train, y_test = train_test_split(X, y)
m = BaggingWithOOB(n_estimators=20, max_depth=5)
m.fit(X_train, y_train)
print(f"OOB accuracy:  {m.oob_score_:.3f}")
print(f"Test accuracy: {m.accuracy(X_test, y_test):.3f}")
```

实测输出：

```text
OOB accuracy:  0.916
Test accuracy: 0.863
```

要点：
- 因为 `y` 是 ±1、树的叶子值是均值，用"累加后取符号"等价于对 OOB 树做平均投票；用 `>= 0` 避免平局得 0。
- 每个样本平均只被约 37% 的树（20 棵中约 7 棵）当作 OOB，所以 OOB 预测来自"更小的森林"，通常略偏悲观；这里 OOB 高于测试集，主要是测试集只有 80 个样本（1 个样本 = 1.25%）带来的波动。
- OOB 的价值：不需要单独留验证集，就能得到近似无偏的泛化估计，sklearn 的 `RandomForestClassifier(oob_score=True)` 就是这么做的。
- 原 `BaggingClassifier.fit` 没有重置 `self.trees`，同一个对象 `fit` 两次会得到 40 棵树（`AdaBoostScratch`、`GradientBoostingScratch` 同理，实测 AdaBoost 5 轮 fit 两次后有 10 个 stump）。

### Q13 — 参考回答要点

| 维度 | Bagging | Boosting |
|------|---------|----------|
| 训练方式 | 并行、相互独立，各用一份 bootstrap 样本 | 串行，每一轮依赖前面的结果（样本加权或拟合残差） |
| 降低的误差 | 主要降方差，偏差基本不变 | 主要降偏差 |
| 基学习器 | 低偏差、高方差（深树） | 高偏差的弱学习器（树桩、浅树） |
| 并行 | 天然并行 | 轮间串行（单棵树内部可以并行找分裂，XGBoost/LightGBM 就是这么做的） |
| 过拟合 | 加树不会让它过拟合，只是收益递减 | 轮数过多会过拟合，需要早停、shrinkage、子采样 |
| 噪声敏感度 | 较稳健 | 较敏感，AdaBoost 尤甚 |

- **加分点**：能说出"随机森林加树不会过拟合"不等于"随机森林不会过拟合"——单棵树太深、数据太少时它照样会过拟合，只是增加树的数量不会让情况变坏。
- **常见误区**：把两者降低的误差成分说反（quiz.json 里的干扰项就是这个）。

### Q14 — 参考回答要点

- **损失**：AdaBoost 等价于用前向分步加法模型最小化**指数损失** `L = Σ exp(−yᵢ F(xᵢ))`。
- **推导**：第 t 轮，`F_t = F_{t−1} + α·h`。把 `exp(−yᵢF_{t−1}(xᵢ))` 视为样本权重 wᵢ，则

```text
L(α) = Σ wᵢ·exp(−α·yᵢ·h(xᵢ)) = e^{−α}·Σ_{分对} wᵢ + e^{α}·Σ_{分错} wᵢ
     ∝ e^{−α}·(1 − err) + e^{α}·err          （权重归一化后）
dL/dα = 0  ⇒  α = ½·ln((1 − err)/err)
```

- **解释的性质**：
  1. 样本权重更新 `w ← w·exp(−α·y·h)` 正是指数损失在新模型下的权重；
  2. err 越小 α 越大，err = 0.5（随机猜）时 α = 0；
  3. 指数损失对大的负间隔惩罚呈指数增长，所以对离群点和标签噪声敏感。
- **加分点**：提到 Freund & Schapire 的提出背景，以及"弱可学习 ⇔ 强可学习"的 boosting 理论（讲义开头"这是一个定理"所指）；能说出用对数损失替代指数损失就得到更稳健的 LogitBoost / 梯度提升分类器。

### Q15 — 参考回答要点

- **函数空间梯度下降**：把模型 F 本身看作优化变量。每一步计算损失对当前预测 `F(xᵢ)` 的负梯度（伪残差 `rᵢ`），用一棵回归树去"近似"这个梯度方向（因为不能直接改每个点的预测，要能泛化到新样本），再沿这个方向走一小步 `F ← F + η·γ·h`。
- **对数损失的伪残差**：二分类、y ∈ {0,1}、`p = σ(F)` 时，`L = −[y·log p + (1−y)·log(1−p)]`，伪残差 `rᵢ = yᵢ − pᵢ`。叶子值不再是残差均值，需要单独做线搜索或牛顿步。
- **平方损失的特殊性**：叶子取残差的均值就已经是该叶子上的最优步长，所以本节代码省略了讲义伪代码中的 `γ_t` 线搜索并不影响正确性。
- **XGBoost 的改进**（讲义列举）：目标函数中加入叶子权重的 L1/L2 正则；用一阶和二阶导数（牛顿法）来求叶子值与分裂增益；稀疏感知分裂，自动学习缺失值的方向；列采样；加权分位数草图做近似分裂点；缓存友好的块结构。
- **加分点**：LightGBM 的直方图算法与 leaf-wise 生长；早停是 GBDT 最重要的正则化手段之一。

### Q16 — 参考回答要点

- **起步**：先做数据检查与划分（必要时按时间/分组划分），用 LightGBM/XGBoost 默认参数跑出基线，并与逻辑回归等简单模型对比，确认没有泄漏。
- **调参顺序**（讲义建议调 n_estimators、learning_rate、max_depth、min_child_weight）：
  1. 先固定一个中等学习率（如 0.05–0.1），用验证集**早停**确定树的数量；
  2. 调树的复杂度：`max_depth` / `num_leaves`、`min_child_weight`（或 `min_data_in_leaf`）；
  3. 调随机性：行采样 `subsample`、列采样 `colsample_bytree`；
  4. 调正则：`reg_lambda`、`reg_alpha`；
  5. 最后把学习率调小、树相应调多，再早停一次，通常能再挤出一点。
- **防过拟合**：早停、shrinkage、限制深度/叶子数、叶子最小样本、行列采样、L1/L2；交叉验证全程使用；特征上线前做时间可得性审查。
- **为什么 GBDT 在表格数据上强**：能自然处理异构特征、尺度不敏感、对缺失值友好、能捕捉非线性和交互，训练快、易调；讲义也指出神经网络在表格数据上"几乎总是更差"，TabNet、NODE 等偶尔持平但很少超过调好的 XGBoost。
- **上线**：监控特征分布漂移，定期重训；保存特征处理与模型版本。

### Q17 — 参考回答要点

- **流程**：
  1. 划出最终测试集（或时间外样本），全程不碰；
  2. 在训练集上做 K 折：每折训练 RF、XGBoost、LR，在留出折上产出**概率**预测，拼成 out-of-fold 元特征；
  3. 元学习器用简单模型（带正则的逻辑回归），避免二次过拟合；
  4. 基模型用全量训练集重训，测试时先过基模型再过元学习器；
  5. 嵌套 CV 或单独验证集评估整个流程。
- **是否值得**：对比"最佳单模型"在同一测试集上的 AUC 提升，并用 bootstrap 给出置信区间；同时计入成本——推理延迟与资源近乎翻几倍、特征/模型版本管理复杂度、排障难度。讲义把 stacking 定位为"榨取最后 1–2%"，适合比赛和收益极高的场景。
- **多样性检查**：看基模型 OOF 预测之间的相关性，若相关性很高，stacking 收益有限。
- **LLM 中的集成思想**：
  - **Self-consistency / 多数投票**：同一问题采样多条推理路径，对最终答案投票，正是本节"独立分类器多数投票"的思路，同样依赖采样之间的多样性；
  - 多模型投票、多 Agent 辩论与投票；
  - 用一个路由器或评审模型决定"信任哪个模型的输出"，与 stacking 的元学习器思想相近。
- **常见误区**：元特征用样本内预测；元学习器过于复杂；忽略推理成本。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 06 概率和分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：二项分布——多数投票准确率公式的来源。
- [阶段 02 · 04 决策树和随机森林](../../04-decision-trees/docs/zh.md)：本节所有集成的基学习器都是树。
- [阶段 02 · 09 模型 Evaluation](../../09-model-evaluation/docs/zh.md)：交叉验证是 stacking 生成元特征的基础。
- [阶段 02 · 10 偏差-方差权衡](../../10-bias-variance/docs/zh.md)：bagging 降方差、boosting 降偏差的理论依据。

### 本节被哪些后续内容用到
- [阶段 02 · 12 Hyperparameter 调整](../../12-hyperparameter-tuning/docs/zh.md)：GBDT / 随机森林的超参数搜索与早停。
- [阶段 02 · 13 机器学习管道](../../13-ml-pipelines/docs/zh.md)：把集成模型与预处理组合成可复用、无泄漏的管道。
- [阶段 02 · 16 异常检测](../../16-anomaly-detection/docs/zh.md)：孤立森林（Isolation Forest）同样是随机树的集成。
- [阶段 02 · 17 处理不平衡数据](../../17-imbalanced-data/docs/zh.md)：集成方法与重采样、代价敏感学习的结合。
- [阶段 07 · 11 专家混合 (MoE)](../../../07-transformers-deep-dive/11-mixture-of-experts/docs/zh.md)：由门控网络决定"信任哪个专家"，与 stacking 的元学习器思想相通。
- [阶段 16 · 15 投票、自洽性与辩论拓扑](../../../16-multi-agent-and-swarms/15-voting-debate-topology/docs/zh.md)：LLM / 多 Agent 场景下的投票与 self-consistency。

### 延伸关键词
`Condorcet 陪审团定理` · `Out-of-bag 估计` · `Extra-Trees` · `LightGBM leaf-wise` · `CatBoost 有序提升` · `staged_predict` · `早停 (early stopping)` · `Blending` · `Soft voting` · `Self-consistency`
