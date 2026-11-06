# 测验 · 处理不平衡数据（Handling Imbalanced Data）

> **阶段 02 · 机器学习基础 · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/imbalanced.py](../code/imbalanced.py) ｜ 代码讲解：[code/imbalanced.讲解.md](../code/imbalanced.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | accuracy 陷阱 | 正例只占 1% 时，"全部预测为负"就有 99% accuracy，却一个正例都抓不到 |
| 2 | Precision / Recall / F1 / Fβ | 精确率看"报出来的有多少是真的"，召回率看"真的有多少被抓到"；F1 是调和平均，β>1 偏重召回（如 F2 用于反欺诈） |
| 3 | AUPRC 与 MCC | 随机分类器的 AUPRC = 正例比例（不是 0.5），提升更显眼；MCC ∈ [-1, 1]，只有两类都做好才会高 |
| 4 | 随机过采样 / 欠采样 | 过采样复制少数类 → 重复点易过拟合；欠采样丢弃多数类 → 信息损失、方差变大 |
| 5 | SMOTE | 在少数类样本与其 k 个少数类近邻之间线性插值：`new = x + t·(neighbor − x)`，t ~ U(0,1) |
| 6 | class weights | 不改数据、改损失：`w_c = n_samples / (n_classes · n_c)`，期望意义上等价于过采样 |
| 7 | 阈值调优 | 0.5 只是默认值；在**验证集**上扫阈值、选使目标指标最大的那个，绝不能在测试集上调 |
| 8 | 代价敏感学习 | 用代价矩阵（如 C_FN=100、C_FP=1）显式表达"哪种错误更贵"，优化总代价而非错误个数 |
| 9 | 防泄漏原则 | 重采样只作用于训练集（CV 时只作用于每折的训练部分），评估永远在原始分布上进行 |

### 核心技能（能动手做到）

- [ ] 从混淆矩阵四个数手算 accuracy、precision、recall、F1、MCC，并解释"全预测为负"时各指标的取值
- [ ] 不用 imbalanced-learn，从零实现 SMOTE（k 近邻 + 线性插值），并说清它和随机复制的区别
- [ ] 实现 `compute_class_weights`，手算 950/50 数据集的两类权重（0.526 与 10.0）并验证"每类总权重相等"
- [ ] 把类权重接入逻辑回归的梯度（`error * weights`），并用加权交叉熵验证两个模型各自优化的目标不同
- [ ] 在独立验证集上用 for 循环扫阈值，选出 F1 最优阈值，再到测试集上评估
- [ ] 从零实现 AUPRC（average precision），并验证随机打分时它约等于正例比例
- [ ] 用 sklearn + imblearn 的 `Pipeline([("smote", SMOTE()), ("model", ...)])` 写出不泄漏的重采样流程

---

## 二、基础自测（选择题）

**Q1.** 测试集有 1000 个样本：990 个负例、10 个正例。一个模型对所有样本都预测"负"。它的 accuracy、recall、MCC（分母为 0 时按惯例记为 0）分别是：

- A. 99%、0、0
- B. 99%、0、0.99
- C. 1%、1、0
- D. 99%、未定义、1

**Q2.** 某数据集正例比例为 2%。一个完全随机打分的分类器，ROC-AUC 和 AUPRC 的期望值大约是：

- A. 0.5 和 0.5
- B. 0.02 和 0.02
- C. 0.5 和 0.02
- D. 0.98 和 0.5

**Q3.** 用 SMOTE 生成合成样本：少数类样本 `x = (1.0, 2.0)`，选中的近邻 `neighbor = (1.5, 2.5)`，随机数 `t = 0.4`。新样本是：

- A. `(1.25, 2.25)`
- B. `(1.3, 2.3)`
- C. `(1.2, 2.2)`
- D. `(0.8, 1.8)`

**Q4.** 关于三种重采样策略，下列说法**正确**的是：

- A. 随机欠采样不会丢失任何信息，因此在小数据集上是首选
- B. 随机过采样会让模型反复看到完全相同的点，有过拟合风险
- C. SMOTE 会参考多数类的分布，因此不会在决策边界附近产生噪声样本
- D. 少数类只有 1 个样本时，SMOTE 依然可以正常生成合成样本

**Q5.** 训练集有 950 个负例、50 个正例，按 `n_samples / (n_classes · n_c)` 计算类权重。正例权重是负例权重的多少倍？

- A. 10 倍
- B. 19 倍
- C. 20 倍
- D. 9.5 倍

**Q6.** 关于 SMOTE 应该在流程的哪一步使用，正确的做法是：

- A. 在全量数据上先做 SMOTE，再划分训练/测试集，这样测试集也是平衡的
- B. 先划分数据，只对训练集（交叉验证时只对每一折的训练部分）做 SMOTE，验证/测试集保持原始分布
- C. 对训练集和测试集分别做 SMOTE，让两者都平衡，评估更公平
- D. 先对训练集整体做 SMOTE，再在它上面做 5 折交叉验证；合成样本不是原始样本，不算泄漏

**Q7.** 一个**概率校准良好**的反欺诈模型，代价矩阵为：漏报（FN）代价 100，误报（FP）代价 1，判对代价 0。为使期望代价最小，判为"欺诈"的概率阈值应约为：

- A. 0.5
- B. 0.99
- C. 0.1
- D. 0.0099（约 1/101）

---

## 三、动手 / 代码题

**Q8.** 下面是本节代码中的两个函数（原样摘录）。

```python
def confusion_matrix_values(y_true, y_pred):
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    return tp, tn, fp, fn


def compute_metrics(y_true, y_pred):
    tp, tn, fp, fn = confusion_matrix_values(y_true, y_pred)
    accuracy = (tp + tn) / (tp + tn + fp + fn)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    denom = np.sqrt(float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)))
    mcc = (tp * tn - fp * fn) / denom if denom > 0 else 0.0
    # ...
```

(a) 对 `y_true = np.array([1,1,0,0,0,0,0,0,0,0])`、`y_pred = np.array([1,0,1,0,0,0,0,0,0,0])`，写出五个指标的值。
(b) 讲义 Step 6 的版本没有 `int(...)` 这一层包装。在一个有几百万条交易的数据集上，去掉 `int(...)` 会出什么问题？

**Q9.**（找 bug）本节的 `find_optimal_threshold` 核心逻辑如下（原样摘录）：

```python
def find_optimal_threshold(y_true, y_probs, metric="f1"):
    best_threshold = 0.5
    best_score = -1.0

    for threshold in np.arange(0.05, 0.96, 0.01):
        y_pred = (y_probs >= threshold).astype(int)
        tp = np.sum((y_pred == 1) & (y_true == 1))
        fp = np.sum((y_pred == 1) & (y_true == 0))
        fn = np.sum((y_pred == 0) & (y_true == 1))

        if metric == "f1":
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            score = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        elif metric == "recall":
            score = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        elif metric == "precision":
            score = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        else:
            score = 0.0

        if score > best_score:
            best_score = score
            best_threshold = threshold

    return best_threshold, best_score
```

(a) 同事想按 F2 选阈值，调用了 `find_optimal_threshold(y_val, probs_val, metric="f2")`，会得到什么返回值？为什么这很危险？
(b) 用 `metric="recall"` 调用时，返回的阈值几乎总是 0.05，为什么？
(c) 改写这个函数：支持 `metric="fbeta"`（带参数 `beta`），未知 metric 直接抛 `ValueError`。

**Q10.** 讲义强调 AUPRC，但代码里没有实现它。请用 NumPy 从零写 `average_precision(y_true, scores)`（AP，即按"每个正例所在名次的 precision"求平均，是 AUPRC 的常用估计），并：
(a) 验证 `y_true=[1,0,1,0]`、`scores=[0.9,0.8,0.7,0.6]` 时 AP = 0.8333；
(b) 验证随机打分时 AP ≈ 正例比例。

---

## 四、面试高频题

**Q11.**（基础必考）为什么在不平衡数据上 accuracy 不可靠？你会用哪些指标替代？ROC-AUC 和 PR-AUC 各在什么情况下用？

**Q12.**（原理深挖）讲一下 SMOTE 的原理。它相比随机过采样好在哪里？有哪些已知缺陷，业界有哪些改进变体？

**Q13.**（原理深挖）class weight 和过采样是什么关系？用了类权重或重采样之后，模型输出的概率还能直接当"真实概率"用吗？如果不能，怎么修正？

**Q14.**（场景设计）设计一个信用卡反欺诈模型：欺诈率约 0.1%，每天千万级交易，漏掉一笔欺诈的损失远大于一次误报。请从数据划分、训练策略、阈值选择、评估和上线监控几方面说说你的方案。

**Q15.**（追问型）本节代码里，对类加权模型做阈值调优，选出的最优阈值是 0.67——比 0.5 还**高**。可讲义说"不平衡时最优阈值通常更低"。这矛盾吗？另外，为什么阈值必须在验证集上调，而不能在测试集上调？

---

## 五、参考答案与解析

### Q1 — 答案：A

- accuracy = (0 + 990) / 1000 = 99%。
- recall = TP / (TP + FN) = 0 / 10 = 0。
- MCC 的分母 `√((TP+FP)(TP+FN)(TN+FP)(TN+FN))` 中 `TP+FP = 0`，分母为 0，按惯例（本节代码 `if denom > 0 else 0.0`）记为 0。

B 错在 MCC 不可能高——它只有在两类都预测好时才高；C 把 accuracy 算反了；D 中 recall 是有定义的（分母 TP+FN = 10 ≠ 0），没有定义的是 precision（0/0）。这道题的要点：**accuracy 说 99%，recall / F1 / MCC 全是 0，后者才说了实话。**

### Q2 — 答案：C

随机打分时，正负样本的分数分布相同，ROC 曲线是对角线，AUC = 0.5，**与类别比例无关**；而 PR 曲线上，不管阈值取多少，被判为正的样本里正例比例都约等于总体正例率，所以 AUPRC ≈ 0.02。正因为 AUPRC 的基线随不平衡程度变化，在 2% 正例的场景里从 0.02 提到 0.4 是巨大的进步，而 ROC-AUC 从 0.5 到 0.9 可能被海量 TN"注水"。

### Q3 — 答案：C

`new = x + t·(neighbor − x) = (1.0, 2.0) + 0.4 × (0.5, 0.5) = (1.2, 2.2)`，与讲义里的示意图一致。A 是 t=0.5 的中点；B 是 t=0.6 的结果（把 t 和 1−t 弄反了）；D 是往反方向外推（`x − t·(neighbor − x)`），SMOTE 只在两点之间的线段上插值，不外推。

### Q4 — 答案：B

- A 错：欠采样恰恰是**扔掉**多数类数据，信息损失、方差变大，小数据集上应避免。
- B 对：随机过采样是有放回地复制少数类样本，模型反复看到完全相同的点，会"记住"它们。
- C 错：讲义明确指出 SMOTE 的缺点是"不考虑多数类分布、可能在决策边界附近产生噪声样本"——它只在少数类内部找近邻，完全看不到多数类。Borderline-SMOTE 等变体才会参考多数类。
- D 错：至少需要 2 个少数类样本才能找近邻。本节代码里 `k = min(k, n_samples - 1)`，若 k < 1 会 `raise ValueError("SMOTE requires at least 2 minority samples")`。

### Q5 — 答案：B

- 负例：`1000 / (2 × 950) ≈ 0.526`；正例：`1000 / (2 × 50) = 10.0`。
- 比值 `10.0 / 0.526 = 950 / 50 = 19`，即"类权重之比 = 类别样本数之反比"。
- C（20 倍）是把 `1000 / 50` 当成了比值；A 是只看了正例权重。
- 一个好记的性质：两类各自的**总权重**都是 `n / 2 = 500`（0.526 × 950 ≈ 50 × 10），相当于让两类在损失里"说话分量相等"。

### Q6 — 答案：B

重采样是一种"训练技巧"，不是数据本身的属性，所以只能用在训练数据上：

- A：先 SMOTE 再划分，合成点由全体少数类（包括后来进入测试集的点）插值得到，测试集信息泄漏进训练集；而且测试集分布被人为改变，指标不再反映线上真实情况。
- C：测试集被平衡后，precision 等指标会被严重高估（线上正例率才 0.1%，测试集却是 50%）。
- D：一个合成点由某个原始样本插值而来，CV 切分后，"孪生兄弟"可能分到验证折，造成泄漏、CV 分数虚高。正确做法是用 `imblearn.pipeline.Pipeline` 把 SMOTE 放进流水线，让它在每一折里只对训练部分生效。

### Q7 — 答案：D

对一个样本，若预测为正，期望代价 = `(1 − p) · C_FP`；若预测为负，期望代价 = `p · C_FN`。当 `p · C_FN > (1 − p) · C_FP` 时应该判正，解得：

```
p > C_FP / (C_FP + C_FN) = 1 / (1 + 100) ≈ 0.0099
```

也就是说，只要有约 1% 的欺诈概率就值得拦截。前提是**概率校准良好**——如果模型是用重采样/类权重训练的，输出的概率已被扭曲（见 Q13），这个公式就不能直接套。A 是默认阈值，与代价无关；B 方向反了；C 没有依据。

### Q8 — 参考答案

**(a)** 逐个样本数：下标 0 → TP，下标 1 → FN，下标 2 → FP，其余 7 个 → TN。所以 `tp=1, tn=7, fp=1, fn=1`：

| 指标 | 计算 | 值 |
|------|------|----|
| accuracy | (1+7)/10 | 0.8 |
| precision | 1/(1+1) | 0.5 |
| recall | 1/(1+1) | 0.5 |
| f1 | 2·0.5·0.5/(0.5+0.5) | 0.5 |
| mcc | (1·7 − 1·1)/√(2·2·8·8) = 6/16 | 0.375 |

实际运行 `print(compute_metrics(...))` 得到：

```
{'accuracy': 0.8, 'precision': 0.5, 'recall': 0.5, 'f1': 0.5, 'mcc': np.float64(0.375)}
```

注意 `mcc` 显示为 `np.float64(0.375)`：因为 `denom` 来自 `np.sqrt`，是 NumPy 标量；NumPy 2.x 打印字典时会显示类型。数值上与 0.375 完全相等。

**(b)** `np.sum(...)` 返回的是 `numpy.int64`。MCC 分母是**四个计数的乘积**，在大数据集上很容易超过 int64 上限（约 9.2×10¹⁸）。例如 TN+FP、TN+FN 都是 10⁷ 量级，TP+FP、TP+FN 是 10⁴ 量级，乘积就是 10²² 量级。int64 乘法溢出时 NumPy 只给一个 `RuntimeWarning`，结果"绕回"成负数，`np.sqrt` 得到 `nan`，MCC 就变成 `nan`。用 `int(...)` 转成 Python 原生 int（任意精度）后，乘积不会溢出，再 `float(...)` 交给 `np.sqrt` 即可。这是代码文件比讲义片段更健壮的一处细节。

### Q9 — 参考答案

**(a)** `"f2"` 不属于三个已知分支，走进 `else: score = 0.0`。每个阈值得分都是 0.0，而初始 `best_score = -1.0`，所以第一个阈值 0.05 就被记为最优，之后 `0.0 > 0.0` 不成立，不再更新。返回 `(0.05, 0.0)`（实际运行验证过）。危险在于：**函数静默返回了一个合法的阈值**，不报错。0.05 这样极低的阈值会把大量样本判为正例，上线后误报暴增，而调用者可能根本没注意到 score 是 0。

**(b)** 阈值越低，被判为正的样本越多，TP 只增不减，recall 单调不减。扫描从 0.05 开始，0.05 处 recall 已经最大（通常为 1.0），后面的阈值只能"持平"，而更新条件是严格的 `>`，所以停在 0.05。单独优化 recall（或 precision）总会得到退化解，这就是为什么要用 F1 / Fβ 或"在 precision ≥ X 的约束下最大化 recall"这类组合目标。

**(c)** 参考实现：

```python
import numpy as np


def find_optimal_threshold_v2(y_true, y_probs, metric="f1", beta=1.0):
    if metric not in ("f1", "fbeta", "recall", "precision"):
        raise ValueError(f"unknown metric: {metric!r}")
    if metric == "f1":
        beta = 1.0
    best_threshold, best_score = 0.5, -1.0
    for threshold in np.arange(0.05, 0.96, 0.01):
        y_pred = (y_probs >= threshold).astype(int)
        tp = np.sum((y_pred == 1) & (y_true == 1))
        fp = np.sum((y_pred == 1) & (y_true == 0))
        fn = np.sum((y_pred == 0) & (y_true == 1))
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        if metric in ("f1", "fbeta"):
            b2 = beta ** 2
            denom = b2 * prec + rec
            score = (1 + b2) * prec * rec / denom if denom > 0 else 0.0
        elif metric == "recall":
            score = rec
        else:
            score = prec
        if score > best_score:
            best_score, best_threshold = score, threshold
    return float(best_threshold), float(best_score)
```

要点：①**快速失败**（fail fast）：参数非法立即抛异常，比静默返回默认值安全得多；②Fβ 公式 `(1+β²)·P·R / (β²·P + R)`，β=1 时退化为 F1；③在本节数据上（前 600 条训练、600–800 条做验证），`metric="f1"` 和 `metric="fbeta", beta=2.0` 都返回阈值约 0.67、得分 1.0（验证集只有约 10 个正例，很容易"满分"——这也提醒我们小验证集上选出的阈值方差很大）。

### Q10 — 参考答案

```python
import numpy as np


def average_precision(y_true, scores):
    order = np.argsort(-np.asarray(scores), kind="mergesort")  # 按分数从高到低
    y = np.asarray(y_true)[order]
    n_pos = y.sum()
    if n_pos == 0:
        return 0.0
    tp_cum = np.cumsum(y)                                  # 前 k 名里的正例数
    precision_at_k = tp_cum / np.arange(1, len(y) + 1)     # 前 k 名的 precision
    return float(np.sum(precision_at_k * y) / n_pos)       # 只在正例所在名次取平均


print(average_precision(np.array([1, 0, 1, 0]), np.array([0.9, 0.8, 0.7, 0.6])))

rng = np.random.RandomState(0)
y = (rng.rand(100000) < 0.05).astype(int)
print(round(average_precision(y, rng.rand(100000)), 4), y.mean())
```

实际输出：

```
0.8333333333333333
0.0503 0.04964
```

- (a)：排序后标签为 `[1,0,1,0]`，两个正例分别在第 1、3 名，对应 precision 为 1/1 和 2/3，平均 = (1 + 0.667)/2 = 0.8333。
- (b)：随机打分时 AP ≈ 0.050，与正例率 0.0496 几乎相等，印证了讲义"随机分类器的 AUPRC 等于正例比例"。
- 加分：把它用在本节模型上，测试集 AP 为：无处理模型 0.9706、类加权模型 0.9768，与 `sklearn.metrics.average_precision_score` 完全一致。两者几乎一样——因为类权重主要改变截距（相当于移动阈值），对样本的**排序**影响很小，而 AP 只看排序。（本实现未处理分数并列的情况，sklearn 会把并列分数作为一个阈值点处理。）

### Q11 — 参考回答要点

- **为什么 accuracy 不可靠**：它把"判对一个负例"和"抓到一个正例"同等计分。正例 1% 时，全判负就是 99%。模型在最小化总错误数时，"永远猜多数类"恰好是一个很强的局部最优。
- **替代指标**：
  - Precision（误报多不多）、Recall（漏报多不多），二者此消彼长；
  - F1：调和平均，P、R 有一个很低就会被拉低；Fβ：β>1 偏重召回（反欺诈、疾病筛查常用 F2），β<1 偏重精确（垃圾邮件、推荐常用 F0.5）；
  - AUPRC：与阈值无关的排序质量，基线 = 正例率；
  - MCC：用到混淆矩阵全部四格，只有两类都好才高，适合跨数据集比较。
- **ROC-AUC vs PR-AUC**：ROC 的横轴 FPR = FP/(FP+TN)，负例极多时，几百个 FP 也只让 FPR 动一点点，曲线显得很好看；PR 曲线的 precision 直接受 FP 绝对数影响，更能反映"实际报警里有多少是真的"。正例稀少、关心正例时首选 PR-AUC；类别较均衡或两类同等重要时 ROC-AUC 也可以。
- **加分点**：报告指标时附上"全预测多数类"基线；业务上常用 `Precision@K` / `Recall@固定 FPR` 这类与运营容量挂钩的指标。
- **常见误区**：认为 ROC-AUC 0.95 就"很好"——在 0.1% 正例下，它对应的 precision 可能只有个位数百分比。

### Q12 — 参考回答要点

- **原理**：对少数类样本 x，在**少数类内部**找 k 个最近邻（常用 k=5），随机选一个近邻 x_nn，在两点连线上取一点：`x_new = x + t·(x_nn − x)`，`t ~ U(0,1)`。重复直到达到目标数量。本节代码就是"k-NN + 线性插值"两步，没有任何魔法。
- **相比随机过采样的优势**：生成的是"新点"而非复制，让决策区域更平滑地向少数类扩展，降低对个别点的过拟合。
- **缺陷**：
  1. 不看多数类：少数类点如果深入多数类区域（噪声/离群点），插值会把噪声放大，在边界附近产生"越界"样本；
  2. 依赖距离度量：高维稀疏特征下近邻不可靠；需要先做特征缩放；
  3. 类别特征不能直接插值（0.4 个"北京"没有意义）；
  4. 需要至少 2 个少数类样本；少数类内部若是多个分散的小簇，跨簇插值会生成不存在的样本。
- **改进变体**：Borderline-SMOTE（只对靠近边界、近邻中含多数类的少数类点插值，本节练习 1）、ADASYN（按学习难度自适应分配合成数量）、SMOTE + Tomek links / ENN（合成后再清洗边界噪声）、SMOTE-NC（处理混合类别特征）。
- **常见误区**：在划分数据前做 SMOTE（泄漏）；对深度学习的图像/文本直接做 SMOTE（像素/token 空间的线性插值通常不是合理样本，深度学习里更常用数据增强、类权重或 focal loss）。

### Q13 — 参考回答要点

- **关系**：对样本 i 的损失乘以权重 w_i，在期望意义上等价于"把这个样本复制 w_i 份"。本节代码的运行结果也印证了这一点：随机过采样与类权重两个模型在测试集上的混淆矩阵完全相同（TP=14, FN=0, FP=8, TN=178）。类权重的优势是不增加数据量、没有重复点。
- **概率会被扭曲**：无论是正例加权（权重比 r = w_pos / w_neg）还是负例下采样（保留比例 s，相当于 r = 1/s），模型学到的都是"正例被放大了 r 倍"的世界，输出概率 q 的 odds 约为真实 odds 的 r 倍：`q/(1−q) ≈ r · p/(1−p)`。
- **修正（prior correction）**：反解得到

  ```
  p = q / (q + r · (1 − q))
  ```

  负例下采样场景下即 `p = q / (q + (1 − q) / s)`，这是广告 CTR 预估中负采样后的经典校准公式。也可以在原始分布的验证集上做 Platt scaling 或 isotonic regression。
- **什么时候必须校准**：要把概率用于期望代价决策（Q7 的公式）、出价、风险定价，或多个模型的分数要融合时。只做排序（AUPRC/AUC）或只用一个调好的阈值时可以不校准——校准不改变排序。
- **加分点**：指出"重采样/加权本质上是在移动决策阈值"，所以先试"不重采样 + 阈值调优"常常就够了；本节代码里"无处理"模型把阈值从 0.5 降到 0.3，测试集 F1 就从 0.783 升到 0.88。

### Q14 — 参考回答要点

1. **数据划分**：按**时间**切分（用过去训练、未来验证/测试），避免未来信息泄漏；如果要随机切则必须分层（stratified）。欺诈有"同一卡/同一商户"聚集性，最好按用户/卡号分组切分。
2. **训练策略**：
   - 千万级数据中正例约 1 万/天，量是够的 → 优先**负例下采样**（如保留 1%–10% 负例）加速训练，或直接用 class weight；SMOTE 在这种规模和高维混合特征下性价比不高；
   - 模型常用 GBDT（如 XGBoost/LightGBM，带 `scale_pos_weight`）或深度模型 + 加权交叉熵 / focal loss；
   - 下采样后用 `p = q / (q + (1−q)/s)` 把概率校准回真实分布。
3. **阈值选择**：显式写出代价矩阵（漏报损失 = 平均欺诈金额，误报损失 = 人工审核成本 + 用户体验损失），在验证集上找总代价最小的阈值；同时受"审核团队每天能处理多少单"的容量约束（Precision@K）。可以分级：高分直接拦截、中分人工审核/二次验证、低分放行。
4. **评估**：离线看 AUPRC、Recall@固定 FPR、按金额加权的召回率，以及代价曲线；与"全判正常"和规则系统基线对比；按商户/地区/金额分桶看。
5. **上线与监控**：影子模式/灰度上线；监控分数分布漂移、报警率、正例率变化（prior shift 会让阈值失效）；欺诈标签有延迟（拒付可能几周后才确认），需要延迟标签回流与定期重训；警惕对抗性漂移（欺诈者会适应模型）。
- **加分点**：提到"标签延迟"和"对抗漂移"这两个反欺诈特有的问题；提到成本曲线比单一 F1 更贴近业务。

### Q15 — 参考回答要点

- **不矛盾**："最优阈值更低"说的是**普通训练**的模型：它的概率被大量负例往下压，正例常常只拿到 0.1~0.3 的分数，所以要把阈值降下来（本节代码中，无处理模型阈值降到 0.3 时 F1 从 0.783 升到 0.88）。而本节第 7 步调阈值的对象是**类加权模型**——类权重已经把正例的分数整体往上推了（等价于把阈值预先下移了一大截），推过了头，导致误报偏多（阈值 0.5 时 FP=8）。这时最优阈值往回调到 0.67，误报降到 1 个，F1 从 0.778 升到 0.929。结论：**最优阈值取决于模型的训练方式和概率刻度，没有通用值，只能在验证集上搜。**
- **为什么不能在测试集上调**：阈值也是一个超参数。在测试集上选阈值相当于"看着答案选最优"，测试集分数就不再是对未见数据的无偏估计，会系统性偏高。正确做法：训练集训练 → 验证集选阈值 → 测试集只评估一次。本节代码就是从训练集再切出 25% 作验证集来调阈值。
- **追问细节**：代码是在"前 75% 训练集上训练的模型"上调阈值，却把阈值用到"全部训练集上训练的模型"（`probs_cw`）上。这是一个近似——两个模型系数非常接近（本例中权重约为 `[1.07, 1.09]` 与 `[1.08, 1.10]`），所以可以迁移；严格的做法是用同一个模型，或用交叉验证的 out-of-fold 预测来选阈值。
- **加分点**：验证集只有约 10 个正例时，选出的阈值方差很大（本例验证 F1 直接是 1.0），工程上可以用多折 OOF 预测、或在阈值—指标曲线上选一段稳定平台的中点；上线后正例率变化（prior shift）时阈值需要重新校准。

---

## 六、关联知识点

### 前置知识
- [阶段 02 · 03 逻辑回归](../../03-logistic-regression/docs/zh.md)：sigmoid、交叉熵与梯度下降，本节的加权逻辑回归直接在它上面改。
- [阶段 02 · 06 K-最近邻和距离](../../06-knn-and-distances/docs/zh.md)：SMOTE 的第一步就是在少数类内部做 k-NN。
- [阶段 02 · 09 模型评估](../../09-model-evaluation/docs/zh.md)：混淆矩阵、precision/recall/F1、ROC、分层 K 折。
- [阶段 01 · 15 机器学习统计学](../../../01-math-foundations/15-statistics-for-ml/docs/zh.md)：分布、期望，理解"类权重在期望上等价于过采样"。

### 本节被哪些后续内容用到
- [阶段 02 · 13 机器学习管道](../../13-ml-pipelines/docs/zh.md)：把 SMOTE 放进 Pipeline、在每一折内拟合，避免数据泄漏。
- [阶段 02 · 16 异常检测](../../16-anomaly-detection/docs/zh.md)：极端不平衡（0.1%）时，问题往往转化为异常检测，同样用 AUPRC、Precision@k 评估。
- [阶段 02 · 11 集成方法](../../11-ensemble-methods/docs/zh.md)：本节练习 4 的 balanced bagging 建立在 bagging 之上。
- [阶段 02 · 12 超参数调优](../../12-hyperparameter-tuning/docs/zh.md)：调决策阈值与调超参数遵循同一套纪律——在验证集（或交叉验证）上搜索，测试集只用一次。
- [阶段 03 · 05 损失函数](../../../03-deep-learning-core/05-loss-functions/docs/zh.md)：深度学习中的加权交叉熵与 focal loss，是类权重思想的延续。
- [阶段 04 · 06 目标检测 YOLO](../../../04-computer-vision/06-object-detection-yolo/docs/zh.md)：检测中前景/背景极度不平衡，用 focal loss 处理。
- [阶段 18 · 21 公平性准则](../../../18-ethics-safety-alignment/21-fairness-criteria-group-individual-counterfactual/docs/zh.md)：equalized odds 要求各群体的 TPR/FPR 相等，"拆开看每个群体/类别的 recall，而不是只看总体 accuracy"的思路与本节一脉相承。

### 延伸关键词
`Borderline-SMOTE` · `ADASYN` · `SMOTE-Tomek / SMOTE-ENN` · `SMOTE-NC` · `Balanced Bagging / EasyEnsemble` · `Focal Loss` · `scale_pos_weight` · `Prior correction（先验校正）` · `Platt scaling / Isotonic regression` · `Cost curve（代价曲线）` · `Precision@K` · `Prior shift / Label shift`
