# 测验 · 模型评估（Model Evaluation）

> **阶段 02 · 机器学习基础 · 第 09 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/evaluation.py](../code/evaluation.py) ｜ 代码讲解：[code/evaluation.讲解.md](../code/evaluation.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 训练 / 验证 / 测试三分 | 训练集用来学参数，验证集用来调超参、选模型，测试集只在最后用**一次**；看过测试集再改模型，它就退化成"第二个验证集" |
| 2 | K 折交叉验证 | 把数据切成 K 份，轮流拿 1 份做验证、K-1 份训练，取 K 个分数的均值；每个样本恰好被验证一次，估计比单次划分更稳 |
| 3 | 分层 K 折（Stratified） | 每折保持与全集相同的类别比例；类别不平衡时防止某折几乎没有少数类 |
| 4 | 混淆矩阵与 P/R/F1 | Precision = TP/(TP+FP)（报出来的有多少是真的），Recall = TP/(TP+FN)（真的有多少被找到），F1 是二者的**调和平均** |
| 5 | 准确率在不平衡数据上"撒谎" | 99% 负样本时"永远预测负"就有 99% 准确率，但 recall = 0；要看 P/R/F1 或 AUC |
| 6 | AUC-ROC | 扫描所有阈值画 TPR–FPR 曲线求面积；0.5 = 随机，1.0 = 完美；与阈值无关，衡量的是**排序能力** |
| 7 | 回归指标 | MSE 平方惩罚大误差、对异常值敏感；RMSE 与目标同单位；MAE 线性惩罚、更稳健；R² = 1 − SS_res/SS_tot，可以为负 |
| 8 | 学习曲线 / 验证曲线 | 横轴为训练集大小 / 超参数；两条线都低且贴合 = 高偏差，训练高验证低且差距大 = 高方差 |
| 9 | 数据泄漏 | 测试信息流进训练：先在全量数据上拟合 scaler、时间序列随机打乱、用由目标派生的特征；原则是**先划分再预处理** |
| 10 | 模型比较要做统计检验 | 两模型在相同折上的分数做配对 t 检验（K=5 时 df=4，双侧 p<0.05 的临界值约 2.78）；均值高一点不代表真的更好 |

### 核心技能（能动手做到）

- [ ] 不用 sklearn，从零实现 `train_val_test_split`、`kfold_split`、`stratified_kfold_split`、`cross_validate`，并能说清每个样本在 K 折中恰好被验证一次
- [ ] 从混淆矩阵四个数手算 accuracy / precision / recall / F1，并处理分母为 0 的情况
- [ ] 从零实现 ROC 曲线与梯形法求 AUC，并用"随机正负样本对排序正确率"的定义交叉验证结果
- [ ] 实现 MSE / RMSE / MAE / R²，并能构造一个 R² 为负的例子
- [ ] 画出（或打印）学习曲线，根据训练/验证分数的高低与差距判断高偏差还是高方差
- [ ] 在一段预处理代码里找出数据泄漏（如先标准化后划分），并改写成"只在训练集上 fit"
- [ ] 对两个模型的 K 折分数做配对 t 检验，正确使用 `n-1` 的样本标准差并查表判断显著性

---

## 二、基础自测（选择题）

**Q1.** 你在测试集上测得 F1 = 0.81，于是回去把正则化强度调小，再测一次得到 0.84，并在报告里写"测试集 F1 = 0.84"。问题出在哪？

- A. 没有问题，0.84 是最新的测试结果
- B. 测试集已经参与了建模决策，变成了"第二个验证集"，0.84 是带乐观偏差的估计
- C. 应该报告两次结果的平均值 0.825
- D. 只要正则化强度不是在训练集上调的，就不算问题

**Q2.** 本节代码在测试集上得到混淆矩阵 `TP=24, TN=25, FP=3, FN=8`。F1 约等于：

- A. 0.8194
- B. 0.8136
- C. 0.8167
- D. 0.7500

**Q3.** 某二分类模型的 AUC-ROC = 0.94，下列解读**最准确**的是：

- A. 在阈值 0.5 下，模型准确率为 94%
- B. 随机抽一个正样本和一个负样本，模型给正样本打分更高的概率约为 0.94
- C. 94% 的正样本被模型找回
- D. 模型输出的概率是良好校准的（预测 0.9 的样本里约 90% 是正类）

**Q4.** 学习曲线显示：训练集从 1k 增加到 10k，训练准确率和验证准确率都稳定在 0.70 左右，两条线几乎重合。最合理的下一步是：

- A. 继续收集更多数据
- B. 加大正则化强度
- C. 换更有表达能力的模型或增加更有信息量的特征
- D. 减少训练数据以加快迭代

**Q5.** 某回归模型在测试集上的 R² = −0.3。这说明：

- A. 计算一定写错了，R² 的取值范围是 [0, 1]
- B. 模型的平方误差比"永远预测目标均值"还大
- C. 模型解释了 30% 的方差，只是方向反了
- D. 特征与目标负相关

**Q6.** 以下哪种做法属于**数据泄漏**？

- A. 在划分训练/测试集之前，用全量数据计算每个特征的均值和标准差并做标准化
- B. 用验证集分数选择正则化强度
- C. 用训练集目标均值作为回归基线，去和模型在测试集上比较
- D. 分类任务中使用分层划分

**Q7.** 房价数据里有少量天价豪宅，它们的价格由模型无法获取的因素决定。你希望评估指标**不被这几个样本主导**，应优先看：

- A. MSE
- B. RMSE
- C. MAE
- D. R²

**Q8.** 1000 个样本中只有 20 个正样本（2%），做普通（非分层）的 10 折交叉验证，最主要的风险是：

- A. 训练时间变成原来的 10 倍
- B. 某些折里正样本极少甚至为 0，该折的 recall / F1 无意义或剧烈波动
- C. 有些样本会被验证不止一次
- D. 模型会记住折的顺序

---

## 三、动手 / 代码题

**Q9.** 预测下面两行的输出（`r_squared` 即本节代码中的实现），并回答：代码演示中 "Mean baseline" 的 R² 打印出来是 `-0.0013` 而不是 `0`，为什么？

```python
print(round(r_squared([1, 2, 3], [3, 2, 1]), 4))
print(round(r_squared([1, 2, 3], [2, 2, 2]), 4))
```

演示代码中的基线：

```python
    mean_baseline = [sum(y_tr_r) / len(y_tr_r)] * len(y_te_r)
```

**Q10.** 本节的 `auc_roc` 在下面这个**有并列分数**的输入上会输出什么？按"随机正负样本对中正样本得分更高的比例（并列记 0.5）"的定义，正确的 AUC 应是多少？请定位原因并修复。

```python
print(auc_roc([1, 0, 1, 0], [0.9, 0.9, 0.5, 0.1]))
```

相关源码：

```python
def roc_curve(y_true, y_scores):
    thresholds = sorted(set(y_scores), reverse=True)
    # ...
    for threshold in thresholds:
        y_pred = [1 if s >= threshold else 0 for s in y_scores]
        # ... 计算 tpr、fpr 并追加
    return fpr_list, tpr_list, thresholds


def auc_roc(y_true, y_scores):
    fpr_list, tpr_list, _ = roc_curve(y_true, y_scores)

    pairs = sorted(zip(fpr_list, tpr_list))
    fpr_sorted = [p[0] for p in pairs]
    tpr_sorted = [p[1] for p in pairs]

    area = 0.0
    for i in range(1, len(fpr_sorted)):
        width = fpr_sorted[i] - fpr_sorted[i - 1]
        height = (tpr_sorted[i] + tpr_sorted[i - 1]) / 2
        area += width * height

    return area
```

**Q11.** 讲义在"常见错误"里强调 *Always split first, then preprocess*。但本节演示的回归部分是这样写的，请指出问题，并改写成没有泄漏的版本（只用本文件已有的 `standardize`、`train_val_test_split` 等函数）。

```python
    X_reg, y_reg = make_regression_data(200)

    col0 = [x[0] for x in X_reg]
    col1 = [x[1] for x in X_reg]
    col0_s, m0, s0 = standardize(col0)
    col1_s, m1, s1 = standardize(col1)
    X_reg_scaled = [[col0_s[i], col1_s[i]] for i in range(len(X_reg))]

    X_tr_r, y_tr_r, X_v_r, y_v_r, X_te_r, y_te_r = train_val_test_split(X_reg_scaled, y_reg)
```

**Q12.** 演示代码最后用配对 t 检验比较两个模型：

```python
    diffs = [a - b for a, b in zip(model_a_scores, model_b_scores)]
    mean_diff = sum(diffs) / len(diffs)
    std_diff = math.sqrt(sum((d - mean_diff) ** 2 for d in diffs) / len(diffs))
    t_stat = mean_diff / (std_diff / math.sqrt(len(diffs))) if std_diff > 0 else 0.0
```

(1) 若 5 折的准确率差为 `diffs = [0, 1/60, 1/60, 2/60, 3/60]`，这段代码算出的 t 是多少？会得出什么结论？
(2) 这段代码在统计上有什么错误？改正后 t 是多少，结论是否改变？
(3) 为什么两次 `cross_validate` 必须用**同一组**折？本节代码是靠什么保证这一点的？

---

## 四、面试高频题

**Q13.**（基础必考）解释 precision、recall、F1 的定义和适用场景。分类阈值从 0.5 调到 0.3，precision 和 recall 一般会怎么变？类别极不平衡时，为什么很多人更推荐看 PR 曲线而不是 ROC 曲线？

**Q14.**（原理深挖）AUC-ROC 的概率含义是什么？为什么说它"与阈值无关"？它有哪些局限——什么情况下 AUC 很高，但模型上线后效果并不好？

**Q15.**（工程实践）列举你见过或能想到的数据泄漏类型，并说明在工程上如何系统性地防止（不只是"先划分再预处理"这一句话）。

**Q16.**（场景设计）你负责一个信用卡反欺诈模型，正样本约 0.1%，数据跨越 12 个月，同一用户有多笔交易。请设计完整的离线评估方案：如何划分数据、用什么指标、怎么选阈值、怎么和线上对齐。

**Q17.**（追问型）同事说"模型 B 的 5 折 CV 平均准确率 0.880，比模型 A 的 0.873 高，所以上 B"。你会怎么追问？如果超参数也是用这 5 折 CV 选出来的，报告的 0.880 还可信吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

测试集的价值在于"对建模过程完全不可见"。一旦你根据测试分数回头改模型，测试集的信息就流进了建模决策，它和验证集没有本质区别了，0.84 是在"这个测试集上挑出来的最好结果"，对真正未见数据是**乐观偏差**的估计。正确做法：在验证集（或 CV）上调正则化，测试集最后只看一次。C 平均两次结果仍然受污染；D 的说法混淆了"在哪个集合上训练"和"用哪个集合做决策"。

### Q2 — 答案：B

Precision = 24/27 ≈ 0.8889，Recall = 24/32 = 0.75，F1 = 2·0.8889·0.75 / (0.8889+0.75) ≈ **0.8136**（与代码实际输出一致）。A 是 P 与 R 的**算术平均**（0.8194），F1 用的是调和平均，会被较小的那个值拉低；C 是准确率 (24+25)/60 ≈ 0.8167；D 只是 recall。

### Q3 — 答案：B

AUC 等价于 Mann–Whitney U 统计量归一化后的值：随机抽一对（正, 负），正样本得分更高的概率。A 混淆了 AUC 与某个阈值下的准确率；C 是 recall（还依赖阈值）；D 是**校准（calibration）**，AUC 只看排序，把所有分数做任意单调变换 AUC 都不变，所以它对概率是否校准一无所知。

### Q4 — 答案：C

训练和验证分数都低且已经收敛重合，是典型的**高偏差（欠拟合）**：模型连训练集都拟合不好，再多数据也没用（A 错）。加正则化（B）会进一步降低模型容量，方向相反。应该增加模型复杂度或加入更有信息量的特征。

### Q5 — 答案：B

R² = 1 − SS_res/SS_tot。SS_tot 正是"永远预测均值"的平方误差和，R² < 0 ⇔ SS_res > SS_tot，即模型比均值基线还差。R² 没有下界，A 错；C、D 是望文生义。常见原因：模型严重过拟合、训练/测试分布不一致、或者预测有系统性偏移。

### Q6 — 答案：A

在划分前用全量数据算均值/标准差，测试集的统计量就"流进"了训练特征的变换中。这正是讲义点名的泄漏例子。B 是验证集的本职工作；C 用训练集均值做基线是正确做法；D 是推荐做法。

### Q7 — 答案：C

MSE / RMSE 对误差平方，几个巨大误差会主导整体分数；R² 也基于平方误差和，同样被主导。MAE 线性惩罚，对异常值更稳健。注意这并不是说异常值可以忽略——如果业务上大误差代价极高，反而应该用 RMSE。

### Q8 — 答案：B

每折平均只有 2 个正样本，随机划分时很可能有的折 0 个、有的折 5 个。0 个正样本时 recall 的分母为 0（本节代码会返回 0.0），而 1 个与 2 个正样本之间 recall 就能差 50%，估计极不稳定。分层 K 折保证每折约 2 个正样本。A 是 K 折本身的代价，与是否分层无关；C、D 都是错误描述。

### Q9 — 参考答案

输出：

```text
-3.0
0.0
```

- 第一行：均值为 2，SS_tot = 1+0+1 = 2；SS_res = (1−3)² + 0 + (3−1)² = 8；R² = 1 − 8/2 = **−3.0**，预测与真实完全"反着来"，比均值基线差得多。
- 第二行：预测恰好是 y_true 的均值，SS_res = SS_tot，R² = **0.0**——这就是 R² 的零点定义。

为什么演示里是 −0.0013：`r_squared` 里的 `mean_y` 是**测试集**的均值，而 `mean_baseline` 用的是**训练集**均值 `sum(y_tr_r) / len(y_tr_r)`。两者略有差异，所以基线的 SS_res 比 SS_tot 稍大，R² 略小于 0。这正是正确做法：基线只能使用训练时可见的信息，若直接用测试集均值做基线，那本身就是一种（轻微的）泄漏。

### Q10 — 参考答案

代码输出 `0.5`，正确答案是 `0.625`。

按定义计数：正样本得分 {0.9, 0.5}，负样本得分 {0.9, 0.1}，共 4 对：

| 正 | 负 | 记分 |
|----|----|------|
| 0.9 | 0.9 | 0.5（并列） |
| 0.9 | 0.1 | 1 |
| 0.5 | 0.9 | 0 |
| 0.5 | 0.1 | 1 |

AUC = 2.5 / 4 = 0.625（`sklearn.metrics.roc_auc_score` 也给出 0.625）。

原因：`roc_curve` 从最高分数开始当阈值，第一个点已经是"所有 ≥0.9 的样本都判正"，即 (FPR, TPR) = (0.5, 0.5)。曲线**缺少起点 (0, 0)**，而 `auc_roc` 的梯形积分从第一个点开始，(0,0)→(0.5,0.5) 这一段三角形面积 0.125 被丢掉了。没有并列分数时，第一个点必然有一个坐标是 0，丢掉这一段面积为 0，所以演示中的连续分数恰好不受影响。

修复（补上起点即可）：

```python
def auc_roc_fixed(y_true, y_scores):
    fpr_list, tpr_list, _ = roc_curve(y_true, y_scores)
    pairs = [(0.0, 0.0)] + sorted(zip(fpr_list, tpr_list))
    area = 0.0
    for (x0, y0), (x1, y1) in zip(pairs, pairs[1:]):
        area += (x1 - x0) * (y0 + y1) / 2
    return area
```

也可以直接按定义实现（O(P·N)，适合对拍）：

```python
def auc_rank(y_true, y_scores):
    pos = [s for s, t in zip(y_scores, y_true) if t == 1]
    neg = [s for s, t in zip(y_scores, y_true) if t == 0]
    if not pos or not neg:
        return 0.5
    wins = 0.0
    for p in pos:
        for q in neg:
            if p > q:
                wins += 1
            elif p == q:
                wins += 0.5
    return wins / (len(pos) * len(neg))
```

两个函数在本例都返回 0.625，在演示用的测试集分数上都返回 0.9408（与原实现一致）。补充：原 `roc_curve` 对每个阈值都重新扫一遍全部样本，复杂度 O(n²)；生产实现会先按分数排序，一次扫描累加 TP/FP，复杂度 O(n log n)。

### Q11 — 参考答案

问题：`standardize` 在**全部 200 个样本**上计算均值和标准差，之后才划分训练/验证/测试。测试集的特征统计量参与了训练特征的变换，属于讲义所说的 "fitting a scaler on the full dataset before splitting"。本例数据同分布、只泄漏了特征的两个统计量，所以数值影响很小，但在小数据、分布漂移或目标编码等场景下，同样的写法会显著高估效果。

改写（先划分，只在训练集上 fit，再 transform 到其他集合）：

```python
X_reg, y_reg = make_regression_data(200)
X_tr, y_tr, X_v, y_v, X_te, y_te = train_val_test_split(X_reg, y_reg)


def fit_scaler(X):
    stats = []
    for j in range(len(X[0])):
        _, mean, std = standardize([row[j] for row in X])
        stats.append((mean, std))
    return stats


def transform(X, stats):
    return [[(row[j] - mean) / std for j, (mean, std) in enumerate(stats)] for row in X]


stats = fit_scaler(X_tr)                 # 只用训练集
X_tr_s = transform(X_tr, stats)
X_v_s = transform(X_v, stats)            # 验证/测试只做 transform
X_te_s = transform(X_te, stats)

reg = SimpleLinearRegression(lr=0.01, epochs=500)
reg.fit(X_tr_s, y_tr)
pred = [reg.predict(x) for x in X_te_s]
print(mse(y_te, pred), r_squared(y_te, pred))
```

实测输出 MSE ≈ 4.87、R² ≈ 0.957，与原来几乎相同——这恰好说明泄漏往往"看不出来"，必须靠写法上的纪律（或 sklearn 的 `Pipeline`）来杜绝。注意：`standardize` 原本就返回了 `mean, std`（原代码中的 `m0, s0` 没被使用），正是为"fit 一次、transform 多次"准备的。

### Q12 — 参考答案

(1) 均值差 = 7/300 ≈ 0.0233；原代码用总体标准差（除以 n），算得 **t ≈ 3.07**，大于 2.78，会被判为"显著"。

(2) 配对 t 检验的统计量是 `t = d̄ / (s_d / √n)`，其中 `s_d` 必须是**样本标准差**（除以 n−1，即 Bessel 校正）。除以 n 会低估标准差，使 t 被放大 `√(n/(n−1))` 倍（n=5 时约 1.118 倍）。改正：

```python
std_diff = math.sqrt(sum((d - mean_diff) ** 2 for d in diffs) / (len(diffs) - 1))
```

改正后 **t ≈ 2.75 < 2.776**，在 p<0.05 下**不显著**，结论反转。另外 `if std_diff > 0 else 0.0` 也不严谨：如果 5 折的差值都相同且非 0（std=0），差异其实是"完全一致"的，返回 0.0 会误判为"没有差异"。

(3) 配对检验的前提是"同一折上的两个分数可以相减"，折的难易程度会同时影响两个模型，相减后抵消掉这部分方差。两次调用如果用的是不同折，差值里混入了"折不同"的噪声，配对就失去意义。本节代码里 `kfold_split(n, k=5, seed=42)` 每次都 `random.seed(42)` 后再打乱，所以两次调用得到的折完全相同。

补充（面试加分）：K 折的训练集彼此重叠，各折分数并不独立，朴素配对 t 检验往往过于乐观；Nadeau & Bengio 提出的 corrected resampled t-test、或 5×2 CV 检验是更稳妥的做法。另外本次演示中模型 A（100 epochs）和 B（500 epochs）的 5 折分数**完全相同**，差值全为 0，所以输出 t = 0。

### Q13 — 参考回答要点

- **定义**：Precision = TP/(TP+FP)，"判为正的里面有多少真是正"；Recall = TP/(TP+FN)，"真正的正样本找回了多少"；F1 = 2PR/(P+R)，调和平均，任何一个很低 F1 都会很低。
- **场景**：误报代价高用 precision（垃圾邮件过滤误杀正常邮件、推荐中的强打扰推送）；漏报代价高用 recall（癌症筛查、安全告警）；两者都重要且难以量化取舍时用 F1，或用 Fβ（β>1 更重视 recall）。
- **阈值 0.5 → 0.3**：更多样本被判为正，TP、FP 都增加，recall 单调不减，precision 通常下降（不保证单调）。
- **PR vs ROC**：ROC 的 FPR = FP/(FP+TN)，负样本极多时 TN 巨大，FP 增加几百个 FPR 也几乎不动，曲线看起来很漂亮；PR 曲线的 precision 直接受 FP 影响，更能反映"告警里有多少是真的"。所以极不平衡时 PR-AUC（Average Precision）更有区分度。
- **常见误区**：把 F1 当成万能指标；忘记 F1 依赖阈值，而模型比较时阈值往往没对齐。

### Q14 — 参考回答要点

- **概率含义**：AUC = P(score(正) > score(负))，并列记 1/2，等价于 Mann–Whitney U 统计量 / (P·N)。
- **与阈值无关**：ROC 曲线本身就是把所有阈值扫一遍，AUC 汇总了所有阈值下的表现；而且对分数做任意严格单调变换，AUC 不变。
- **局限**：
  1. 不反映校准：概率整体偏高/偏低 AUC 不变，但下游如果要用概率做定价、期望收益计算就会出错；
  2. 全局排序 ≠ 关心的区域：业务往往只在很低 FPR（如 0.1% 误报率）下运行，两个 AUC 相同的模型在这一段可能差很多，可看 partial AUC 或固定 FPR 下的 TPR；
  3. 极不平衡数据下 AUC 偏乐观（见 Q13）；
  4. 离线 AUC 与线上指标不一致：分布漂移、样本选择偏差、特征穿越（泄漏）都会让离线 AUC 虚高。
- **加分点**：能说出 AUC 的 O(n log n) 计算方法（排序后用秩和）；能提到 LLM 评估中 "benchmark 污染" 本质也是测试集泄漏。

### Q15 — 参考回答要点

- **类型**：
  1. **预处理泄漏**：在全量数据上 fit scaler / imputer / PCA / 特征选择 / 目标编码；
  2. **时间泄漏（特征穿越）**：随机划分时间序列；特征里用了预测时刻之后才能拿到的信息（如"未来 7 天的点击数"）；
  3. **目标泄漏**：特征由标签派生或与标签同时产生（如"是否已退款"用于预测欺诈）；
  4. **分组泄漏**：同一用户/病人/文档的多条样本分散在训练和测试中，模型学会"认人"；
  5. **重复样本 / 近重复**：数据集去重不彻底，测试样本几乎原样出现在训练集（LLM 预训练语料污染 benchmark 是同类问题）；
  6. **评估流程泄漏**：反复看测试集、用 CV 分数选超参又用同一个 CV 分数报告。
- **防止手段**：先划分；预处理放进 `Pipeline` 让 CV 每折独立 fit；时间序列用前向滚动（walk-forward）划分；有分组的用 GroupKFold；特征上线前做"预测时刻可得性"审查；对"好得不正常"的特征做重要性排查；测试集锁起来只在最终评估时读取。
- **加分点**：能举一个自己踩过的坑，以及如何通过特征重要性异常或线上线下指标差异发现它。

### Q16 — 参考回答要点

- **划分**：按**时间**切，如前 9 个月训练、第 10 个月验证、最后 2 个月测试，模拟"用过去预测未来"；同时保证同一用户不会在训练和测试中出现（或至少意识到这一点的影响）；CV 用滚动时间窗而不是随机 K 折。
- **指标**：不看 accuracy（全判正常就有 99.9%）。离线主指标用 PR-AUC，辅以"固定告警量/误报率下的 recall"，例如每天人工只能审核 500 单，就看 top-500 中的 precision 和 recall；金额加权的 recall（拦截了多少欺诈金额）往往更贴近业务。
- **阈值**：在验证集上根据业务成本选，例如最小化 `FN 成本 × FN + FP 成本 × FP`，或满足审核产能约束；阈值定好后在测试集上只评一次。
- **统计可靠性**：0.1% 的正样本，测试集里可能只有几百个正例，需要给出置信区间（bootstrap）。
- **线上对齐**：标签延迟（拒付可能几十天后才确认）要在离线评估中模拟；上线先影子模式（shadow）再 A/B；持续监控分布漂移。

### Q17 — 参考回答要点

- **追问 1：差异是否显著？** 0.007 的差距在 300 个样本、每折 60 个样本的情况下不到 1 个样本/折。需要看各折分数和标准差，做配对检验（同一组折），最好再换几个随机种子重复 CV。
- **追问 2：是否用的同一组折？** 不同折的分数不能直接配对比较。
- **追问 3：成本**：B 是否更慢、更大、更难维护？差异不显著时优先选更简单的模型（skill 文件中也写了 "Consider the simpler model when performance differences are not significant"）。
- **超参数问题**：如果超参数就是在这 5 折上挑出来的，0.880 是"在多个候选里取最大值"，有**选择偏差**，是乐观估计。正确做法是**嵌套交叉验证**：内层 CV 选超参，外层 CV 评估整个"选超参 + 训练"的流程；或者保留一个从未参与选择的测试集。
- **常见误区**：只比较均值不看方差；把 CV 分数当作最终泛化性能报告。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 06 概率和分布](../../../01-math-foundations/06-probability-and-distributions/docs/zh.md)：理解"随机抽一对正负样本"的概率含义。
- [阶段 01 · 15 机器学习统计](../../../01-math-foundations/15-statistics-for-ml/docs/zh.md)：均值、方差、样本标准差（n−1）、t 检验与置信区间。
- [阶段 02 · 02 线性回归](../../02-linear-regression/docs/zh.md)、[阶段 02 · 03 逻辑回归](../../03-logistic-regression/docs/zh.md)：本节演示用的两个被评估模型。
- [阶段 02 · 08 Feature 工程与选择](../../08-feature-engineering/docs/zh.md)：标准化、编码等预处理，以及它们可能引入的泄漏。

### 本节被哪些后续内容用到
- [阶段 02 · 10 偏差-方差权衡](../../10-bias-variance/docs/zh.md)：把学习曲线 / 验证曲线的诊断上升到误差分解理论。
- [阶段 02 · 11 集成方法](../../11-ensemble-methods/docs/zh.md)：用交叉验证比较单模型与集成模型，stacking 依赖 out-of-fold 预测。
- [阶段 02 · 12 Hyperparameter 调整](../../12-hyperparameter-tuning/docs/zh.md)：网格/随机/贝叶斯搜索都以 CV 分数为目标，嵌套 CV 防止选择偏差。
- [阶段 02 · 13 机器学习管道](../../13-ml-pipelines/docs/zh.md)：用 Pipeline 把预处理放进 CV，从工程上杜绝泄漏。
- [阶段 02 · 15 时间序列基础知识](../../15-time-series/docs/zh.md)：时间序列必须按时间划分，不能随机 K 折。
- [阶段 02 · 17 处理不平衡数据](../../17-imbalanced-data/docs/zh.md)：PR 曲线、阈值调整、重采样与本节指标直接衔接。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)、[阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：LLM 评估同样面临测试集污染、指标选择和统计显著性问题。
- [阶段 19 · 71 经典评估指标](../../../19-capstone-projects/71-classical-metrics/docs/zh.md)：在评测框架中实现分类/回归指标。

### 延伸关键词
`PR-AUC / Average Precision` · `Fβ score` · `Matthews 相关系数 (MCC)` · `概率校准 (Platt / Isotonic)` · `GroupKFold` · `TimeSeriesSplit` · `嵌套交叉验证` · `Bootstrap 置信区间` · `5×2 CV 配对 t 检验` · `McNemar 检验` · `Benchmark 污染`
