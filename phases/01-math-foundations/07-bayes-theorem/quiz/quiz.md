# 测验 · 贝叶斯定理（Bayes' Theorem）

> **阶段 01 · 数学基础 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/bayes.py](../code/bayes.py) ｜ 代码讲解：[code/bayes.讲解.md](../code/bayes.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 贝叶斯定理 | 由 `P(A∩B) = P(A|B)P(B) = P(B|A)P(A)` 直接推出 `P(A|B) = P(B|A)·P(A) / P(B)` |
| 2 | 四个组成部分 | 后验 posterior = 似然 likelihood × 先验 prior ÷ 证据 evidence；证据用全概率公式展开 `P(B) = P(B|A)P(A) + P(B|¬A)P(¬A)` |
| 3 | 基础率谬误（base rate fallacy） | 患病率 1/10000、准确率 99% 的检测，阳性后真患病概率只有约 0.98%——先验很小时，假阳性占多数 |
| 4 | 朴素贝叶斯（Naive Bayes） | 假设特征在**给定类别时条件独立**，`score(c) = P(c)·∏P(xᵢ|c)`；分母对所有类相同，可以省略 |
| 5 | 拉普拉斯平滑与对数空间 | `(count + α) / (total + α·|V|)` 防止零概率"一票否决"；连乘改成 log 求和防止浮点下溢 |
| 6 | MLE vs MAP | MLE 最大化 `P(data|θ)`；MAP 最大化 `P(data|θ)·P(θ)`；高斯先验 ⇔ L2 正则，拉普拉斯先验 ⇔ L1 正则 |
| 7 | 共轭先验 Beta-Binomial | 先验 `Beta(a,b)` + s 次成功 f 次失败 → 后验 `Beta(a+s, b+f)`；均值 `a/(a+b)`，`a+b` 越大越"自信" |
| 8 | 序贯更新 | 今天的后验就是明天的先验；序贯更新与一次性批量更新结果完全相同 |
| 9 | 贝叶斯 A/B 测试 | 两组各自得到 Beta 后验，用 Monte Carlo 采样估计 `P(B > A)`，再按阈值（如 0.95）决策 |

### 核心技能（能动手做到）

- [ ] 给定患病率、灵敏度、假阳性率，手算 `P(sick|positive)`，并能算出连续两次阳性后的后验（约 0.495）
- [ ] 不用 sklearn，从零实现带拉普拉斯平滑、在 log 空间打分的 `NaiveBayes`，并在 12 条样例邮件上跑通预测
- [ ] 用"减去最大值再 exp"的技巧把 log 分数安全地转成归一化概率（`predict_proba`）
- [ ] 能写出 Beta(α,β) 先验下的 MAP 公式 `(h+α-1)/(n+α+β-2)`，并解释为什么先验越强估计越靠近 0.5
- [ ] 用 Beta-Binomial 共轭更新实现序贯更新，并验证"序贯 = 批量"
- [ ] 用 Monte Carlo 采样（`random.betavariate` 或 `numpy.random.Generator.beta`）计算 A/B 测试的 `P(B > A)` 与 lift 的可信区间

---

## 二、基础自测（选择题）

**Q1.** 某疾病患病率为 1%，检测灵敏度 99%，假阳性率 1%。一个人检测阳性，他真正患病的概率约为：

- A. 99%
- B. 50%
- C. 9.9%
- D. 1%

**Q2.** 在垃圾邮件例子中，"已知是垃圾邮件，邮件里出现 lottery 的概率 = 0.05"这个量，在贝叶斯公式中叫做：

- A. 先验（prior）
- B. 后验（posterior）
- C. 似然（likelihood）
- D. 证据（evidence）

**Q3.** 朴素贝叶斯中"朴素"的独立性假设，准确表述是：

- A. 所有特征彼此完全独立（边缘独立）
- B. 给定类别后，各特征相互条件独立
- C. 类别与特征相互独立
- D. 训练样本之间相互独立

**Q4.** 拉普拉斯平滑公式 `P(w|c) = (count(w,c) + 1) / (total_c + |V|)` 中，分母要加上词表大小 `|V|`，原因是：

- A. 让高频词的概率变得更大
- B. 保证该类下所有词的概率之和仍为 1
- C. 让不同类别的概率可以直接相加
- D. 为了让未登录词（OOV）的概率为 0

**Q5.** 抛硬币 10 次得到 7 次正面，使用 `Beta(2,2)` 先验。偏置参数的 **MAP 估计**是：

- A. 0.700
- B. 0.667
- C. 0.643
- D. 0.500

**Q6.** 关于先验与正则化的对应关系，正确的是：

- A. 高斯先验 ⇔ L1 正则；拉普拉斯先验 ⇔ L2 正则
- B. 高斯先验 ⇔ L2 正则；拉普拉斯先验 ⇔ L1 正则
- C. 均匀先验 ⇔ L2 正则
- D. 先验只影响后验方差，与正则化无关

**Q7.** 从 `Beta(1,1)` 出发，第一天观察到 7 正 3 反，第二天观察到 5 正 5 反（以第一天后验作为第二天先验）。下列说法正确的是：

- A. 最终后验为 `Beta(12, 8)`，均值 0.600
- B. 最终后验为 `Beta(13, 9)`，均值约 0.591；若一次性用 12 正 8 反更新，结果相同
- C. 最终后验为 `Beta(13, 9)`，但一次性批量更新会得到不同结果
- D. 第二天应重新从 `Beta(1,1)` 出发，否则会重复计算先验

---

## 三、动手 / 代码题

**Q8.** 阅读 `bayes.py` 中的函数，写出下面代码的输出，并说明为什么第二次阳性后概率会从不到 1% 跳到约 50%。如果再做第三次检测（仍为阳性），结果大约是多少？

```python
def bayes(prior, likelihood, false_positive_rate):
    evidence = likelihood * prior + false_positive_rate * (1 - prior)
    posterior = likelihood * prior / evidence
    return posterior


def sequential_bayes(prior, likelihood, false_positive_rate, num_tests):
    current = prior
    for i in range(num_tests):
        current = bayes(current, likelihood, false_positive_rate)
        print(f"  After test {i + 1}: P(sick|positive) = {current:.6f}")
    return current

sequential_bayes(0.0001, 0.99, 0.01, 2)
```

**Q9.**（找 bug）讲义练习 2 问"smoothing=0 时会怎样"。用 `NaiveBayes(smoothing=0.0)` 在本节 12 条训练邮件上训练后调用 `predict("free meeting")`，会发生什么？指出出错的代码行，并给出至少两种修复思路。

```python
    def _log_likelihood(self, word, cls):
        count = self.word_counts[cls].get(word, 0)
        total = self.class_word_totals[cls]
        vocab_size = len(self.vocab)
        return math.log(
            (count + self.smoothing) / (total + self.smoothing * vocab_size)
        )
```

**Q10.**（解释现象）运行 `bayes.py`，`'meeting rescheduled to friday'` 被判为 ham，但置信度只有 `0.638`，而 `'please review the attached report'` 有 `0.983`。已知训练集中 spam 类共 21 个词、ham 类共 29 个词、词表大小 44，`meeting` 只在 ham 中出现 1 次，`rescheduled / to / friday` 都不在词表中。请定量解释为什么置信度这么低，并说明 sklearn 的 `CountVectorizer + MultinomialNB` 在这一点上的行为有何不同。

**Q11.**（扩展）`ab_test_demo` 手写了 Marsaglia-Tsang Gamma 采样器来生成 Beta 样本。请用标准库 `random.betavariate` 重写一个函数 `p_b_beats_a(a_clicks, a_views, b_clicks, b_views, n=100000, seed=42)`，返回 `P(B > A)`，并说明在 `50/1000` vs `65/1000` 的数据上大约会得到多少、应当做什么决策。

---

## 四、面试高频题

**Q12.**（基础必考）请写出贝叶斯定理并解释每一项。一个欺诈检测模型"召回率 99%、误报率 1%"，但线上欺诈率只有 0.1%，被模型标记为欺诈的交易里真正是欺诈的比例大约多少？这对阈值设定和评估指标选择有什么启示？

**Q13.**（原理深挖）MLE 和 MAP 有什么区别？请推导"对线性回归的权重加高斯先验，MAP 就等价于 L2 正则（岭回归）"。数据量趋于无穷时两者是什么关系？

**Q14.**（原理深挖）朴素贝叶斯的条件独立假设在文本中明显不成立，为什么它仍然好用？它输出的概率可以直接当置信度用吗？它和逻辑回归是什么关系？

**Q15.**（工程实践）对比频率学派 A/B 测试和贝叶斯 A/B 测试。"贝叶斯 A/B 测试可以随时偷看结果而不会膨胀误报率"这个说法你怎么看？在推荐/LLM 功能实验里，贝叶斯思想还能怎么用（例如 Thompson sampling）？

**Q16.**（追问型）实现朴素贝叶斯时为什么要在 log 空间计算？已经得到每个类的 log 分数后，如何安全地还原出归一化概率？如果直接 `math.exp(score)` 会出现什么问题？

---

## 五、参考答案与解析

### Q1 — 答案：B

`P(+) = 0.99×0.01 + 0.01×0.99 = 0.0099 + 0.0099 = 0.0198`，`P(sick|+) = 0.0099 / 0.0198 = 0.5`。真阳性与假阳性数量恰好相等。和讲义里患病率 1/10000（后验约 0.98%）对比：**同一个检测，先验从 0.01% 变成 1%，后验从约 1% 变成 50%**——先验对结果影响巨大。A 是"把 `P(+|sick)` 当成 `P(sick|+)`"的经典错误；C、D 是数量级上的误算。

### Q2 — 答案：C

`P("lottery"|spam)` 是"假设成立时观测到证据的概率"，即似然。先验是 `P(spam)=0.3`，后验是 `P(spam|"lottery")≈0.955`，证据是 `P("lottery")=0.0157`。

### Q3 — 答案：B

朴素贝叶斯假设 `P(x₁,…,xₙ|c) = ∏ P(xᵢ|c)`，是**以类别为条件**的独立，而不是边缘独立（A）。"New" 和 "York" 在所有文本中显然相关，NB 只要求"在同一类别内部"把它们当作独立，这仍然是错误假设，但比边缘独立弱得多。C 说类别与特征独立，那分类器就毫无意义；D 是训练数据的 i.i.d. 假设，与"朴素"无关。

### Q4 — 答案：B

分子给词表中**每个词**都加了 1，共加了 `|V|` 个 1；分母同样加 `|V|`，才能保证 `Σ_w P(w|c) = (total_c + |V|) / (total_c + |V|) = 1`。代码中一般化为 `total + smoothing * vocab_size`。D 正好相反——平滑的目的就是让未见过的词概率**不为 0**。

### Q5 — 答案：B

`Beta(2,2)` 先验 + 7 正 3 反 → 后验 `Beta(9,5)`。MAP 是后验的**众数（mode）**：`(h+α-1)/(n+α+β-2) = (7+1)/(10+2) = 8/12 ≈ 0.667`，与代码 `demo_mle_vs_map` 的输出一致。A 是 MLE（7/10）；C 是后验**均值** `9/14 ≈ 0.643`，这是常见混淆点——MAP 取的是峰值，不是均值；D 是先验均值。

### Q6 — 答案：B

`-log N(w; 0, σ²) = w²/(2σ²) + const` → L2 惩罚；`-log Laplace(w; 0, b) = |w|/b + const` → L1 惩罚。所以"每加一个正则项，都是在对参数做贝叶斯先验声明"。均匀先验（C）对应的是无正则的 MLE。

### Q7 — 答案：B

`Beta(1+7, 1+3) = Beta(8,4)`，再 `Beta(8+5, 4+5) = Beta(13,9)`，均值 `13/22 ≈ 0.591`。共轭更新只是把计数相加，加法满足交换律和结合律，所以**顺序无关、序贯 = 批量**（代码 `sequential_update_demo` 最后打印 `Sequential and batch give the same result: True`）。A 忘了加上先验的伪计数 1；D 恰恰违背了"后验即新先验"的序贯思想——重新从 `Beta(1,1)` 出发会丢掉第一天的信息。

### Q8 — 参考答案

输出：

```
  After test 1: P(sick|positive) = 0.009804
  After test 2: P(sick|positive) = 0.495000
```

- 第一次：`0.99×0.0001 / (0.99×0.0001 + 0.01×0.9999) ≈ 0.0098`。
- 第二次把 `0.009804` 当作新的先验：`0.99×0.009804 / (0.99×0.009804 + 0.01×0.990196) ≈ 0.495`。
- 直觉：每次阳性的**似然比**是 `0.99/0.01 = 99`。用几率（odds）看：先验几率 `1/9999`，乘 99 得 `≈0.0099`（后验约 0.98%），再乘 99 得 `≈0.98`（后验约 0.495）。第三次再乘 99 得 `≈97`，对应概率 `97/98 ≈ 0.9898`（实际运行 `sequential_bayes(..., 3)` 输出 `0.989800`）。
- 前提：两次检测在给定真实状态下**条件独立**（讲义 Exercise 1 的"independent tests"）。如果是同一台机器、同一份样本重复测，误差高度相关，这样连乘会严重高估后验。

### Q9 — 参考答案

会抛出 `ValueError: math domain error`。类别按 `class_counts` 的插入顺序遍历，先算 `spam`：`"meeting"` 在 spam 中计数为 0，`(0 + 0) / (21 + 0) = 0`，而 `math.log(0)` 在 Python 中直接抛 `ValueError`（不是返回 `-inf`）。出错行是 `_log_likelihood` 里的 `return math.log(...)`。

修复思路：

1. **保持 `smoothing > 0`**（这正是拉普拉斯平滑存在的意义）。也可以用更小的 α（如 0.1，称为 Lidstone 平滑）。
2. **对零概率返回 `-inf`**：`p = ...; return math.log(p) if p > 0 else float("-inf")`。但这样任意一个零计数词都会让该类分数变成 `-inf`，"一票否决"问题依然存在。
3. **忽略训练词表外的词**（sklearn 的做法），只对 `word in self.vocab` 的词累加分数——但这只能解决"完全没见过"的词，"在 ham 见过、在 spam 没见过"的词在 α=0 时仍会得到 0 概率。

所以根本办法仍是平滑。

### Q10 — 参考答案

逐项比较 ham 与 spam 的分数比（似然比）：

| 项 | spam | ham | ham/spam |
|----|------|-----|----------|
| 先验 | 5/12 | 7/12 | 1.40 |
| `meeting` | (0+1)/(21+44)=1/65 | (1+1)/(29+44)=2/73 | ≈1.78 |
| 每个未登录词 ×3 | 1/65 | 1/73 | 65/73 ≈ 0.89，三次 ≈ 0.71 |

总比值 `≈ 1.40 × 1.78 × 0.71 ≈ 1.76`，所以 `P(ham) ≈ 1.76 / 2.76 ≈ 0.638`，与运行结果一致。

关键原因：**未登录词的平滑概率是 `α/(total_c + α|V|)`，只取决于该类的总词数**。spam 类总词数更少（21 < 29），所以每个没见过的词都会"偏向 spam" 约 12%。测试句里有 3 个未登录词，把 `meeting` 带来的 ham 证据抵消掉了一大半。

sklearn 的 `CountVectorizer.transform` 只保留 `fit` 时的词表，**训练时没见过的词直接被丢弃**，不参与打分，因此不会产生这种系统性偏置。从零实现时可以在 `predict` 里加一行 `if word not in self.vocab: continue` 达到同样效果。

### Q11 — 参考答案

```python
import random


def p_b_beats_a(a_clicks, a_views, b_clicks, b_views, n=100000, seed=42):
    rng = random.Random(seed)                      # 独立的随机数生成器，不污染全局状态
    a_alpha, a_beta = 1 + a_clicks, 1 + (a_views - a_clicks)   # Beta(1,1) 先验 + 数据
    b_alpha, b_beta = 1 + b_clicks, 1 + (b_views - b_clicks)
    wins = 0
    for _ in range(n):
        if rng.betavariate(b_alpha, b_beta) > rng.betavariate(a_alpha, a_beta):
            wins += 1
    return wins / n


print(p_b_beats_a(50, 1000, 65, 1000))   # 实测约 0.925
```

- 结果约 0.92–0.93（`bayes.py` 自带采样器输出 `0.9227`，用 NumPy `rng.beta` 采样也约 0.924），说明"B 更好的概率约 92%"。
- 决策：按代码中的规则，`0.05 < 0.92 < 0.95`，属于 **Keep collecting data（继续收集数据）**。注意讲义中"97% chance B is better"只是举例措辞，并不是这组数据的计算结果。
- 生产中可用 NumPy 向量化：`rng = np.random.default_rng(42); (rng.beta(66, 936, n) > rng.beta(51, 951, n)).mean()`，速度快几十倍。

### Q12 — 参考回答要点

- 定义：`P(H|E) = P(E|H)·P(H) / P(E)`，后验 = 似然 × 先验 / 证据；证据用全概率公式展开。
- 计算：`P(flag) = 0.99×0.001 + 0.01×0.999 ≈ 0.00099 + 0.00999 = 0.01098`，`P(fraud|flag) ≈ 0.00099/0.01098 ≈ 9%`。**被标记的交易里约 91% 是误报**。
- 启示：
  - 模型输出的分数要结合**线上基础率**解读；训练集若做过过采样，线上概率需要做先验校正（prior shift correction）。
  - 极不平衡场景下 accuracy 无意义，要看 precision / recall / PR-AUC；误报率 1% 乘以海量负样本，绝对数量依然巨大。
  - 阈值应由业务代价决定：人工复核成本 vs 漏判损失。也可以设计**两阶段**流程（粗筛 + 复核），相当于讲义里的"确认检测"。
- 加分点：用"似然比 × 先验几率 = 后验几率"的 odds 形式快速心算；指出这与 RAG/安全分类器的误拦截问题是同一回事。

### Q13 — 参考回答要点

- 定义：MLE `θ* = argmax P(D|θ)`；MAP `θ* = argmax P(D|θ)·P(θ)`（证据 `P(D)` 与 θ 无关，可忽略）。
- 推导（线性回归）：设 `y = wᵀx + ε, ε ~ N(0, σ²)`，先验 `w ~ N(0, τ²I)`。
  - `-log P(D|w) = (1/(2σ²))·Σ(yᵢ - wᵀxᵢ)² + const`
  - `-log P(w) = (1/(2τ²))·‖w‖² + const`
  - 两者相加最小化，等价于 `Σ(yᵢ - wᵀxᵢ)² + λ‖w‖²`，其中 `λ = σ²/τ²`。先验越窄（τ 越小），λ 越大，正则越强。
- 数据量趋于无穷：似然项随 n 线性增长，先验项不变，**先验的影响被数据淹没，MAP → MLE**。小数据时差异最大——这正是"先验即正则、防止过拟合"。
- 常见误区：MAP 仍然是**点估计**，并不给出不确定性；完整的贝叶斯推断要保留整个后验分布。另外 MAP 依赖参数化方式（换元后众数会变），而后验均值/分布不会有这个问题。

### Q14 — 参考回答要点

- 为什么好用：
  - 分类只需要**排序正确**（argmax），不需要概率校准；独立性假设带来的误差常常在各类之间"同向"出现，不影响排序。
  - 参数极少（每类每词一个概率），**高偏差、低方差**，小数据下不易过拟合；训练只是计数，O(数据量)，可增量更新。
- 概率不能直接当置信度：相关特征被重复计数（"New" 和 "York" 被当成两条独立证据），导致 log 分数被放大，输出概率**系统性地过于极端**（接近 0 或 1）。需要时可用 Platt scaling / isotonic regression 做校准。本节代码 `predict_proba` 输出的 0.99 级别"置信度"也应这么看待。
- 与逻辑回归：二者构成一对**生成式/判别式**模型。多项式 NB 的后验对数几率是特征计数的线性函数，形式上与逻辑回归相同；区别是 NB 通过建模 `P(x|c)` 计数得到参数，LR 直接最大化 `P(c|x)`。经典结论（Ng & Jordan）：NB 收敛更快、适合小样本，LR 渐近误差更低、数据多时更好。
- 加分点：提到 Bernoulli NB（看词是否出现）与 Multinomial NB（看词频）的区别——讲义 MLE 段落按"含有该词的邮件数/邮件总数"计数是 Bernoulli 视角，而代码与平滑公式按"词频/该类总词数"计数是 Multinomial 视角。

### Q15 — 参考回答要点

- 频率学派：设原假设 A=B，算 p 值，`p < 0.05` 拒绝原假设；需要预先确定样本量，**中途多次偷看并在显著时停止会膨胀第一类错误**。
- 贝叶斯：每组 `Beta(1+clicks, 1+non-clicks)` 后验，Monte Carlo 估计 `P(B>A)` 与 lift 的可信区间；输出是直接可解释的"B 更好的概率"；可以融入历史实验的先验（例如转化率通常在 3%–8%）。
- 关于"随时偷看"：讲义在表格里加了限定条件（"given a well-chosen prior and correctly specified model"）。更严谨的说法是：贝叶斯后验本身在任意时刻都是有效的信念陈述，不依赖停止规则；但如果你用"`P(B>A) > 0.95` 就停"这种规则并且关心**频率意义上的误报率**，频繁查看依然会提高误判次数。工程上常配合最小样本量、最小实验时长、期望损失（expected loss）阈值等护栏。
- 延伸应用：
  - **Thompson sampling**：每次从各臂的 Beta 后验各采一个样本，选最大的那个臂投放——自然平衡探索与利用，常用于多臂老虎机、推荐冷启动、prompt/模型版本的在线流量分配。
  - LLM 功能实验中，成功率类指标（点赞率、任务完成率）都可以直接套 Beta-Binomial。
- 常见误区：把 p 值解释成"A=B 的概率"；把 `P(B>A)=0.92` 理解成"B 比 A 好 92%"（那是 lift，不是概率）。

### Q16 — 参考回答要点

- 原因：几十个词的概率都在 0.01 量级，连乘后很快小于 float64 的最小正数（约 `1e-308`），**下溢为 0**，所有类别分数都变成 0，无法比较。`log` 把连乘变成连加，且 log 单调递增，argmax 不变。
- 还原概率：`P(c|x) = exp(sᶜ) / Σ exp(sᵏ)`。直接算 `exp(-1000)` 会得到 0.0，导致 `0/0`。做法是先减去最大值：`exp(sᶜ - m) / Σ exp(sᵏ - m)`，其中 `m = max sᵏ`，数学上分子分母同乘 `exp(-m)`，结果不变，但最大项变为 `exp(0)=1`，不会全部下溢；这就是代码中 `predict_proba` 的写法，也是 softmax 的标准数值稳定实现（log-sum-exp trick）。
- 示例：分数 `{spam: -1000, ham: -1002}`，直接 exp 全为 0；减最大值后得到 `{spam: 0.881, ham: 0.119}`。
- 加分点：`scipy.special.logsumexp`、`torch.logsumexp` 都内置了这个技巧；交叉熵损失通常直接接收 logits，就是为了在内部用同样的方式保证数值稳定。

---

## 六、关联知识点

### 前置知识
- [阶段 01 · 06 概率和分布](../../06-probability-and-distributions/docs/zh.md)：条件概率、全概率公式、Bernoulli/Binomial 分布，是本节推导贝叶斯公式的起点。
- 对数运算：`log(ab) = log a + log b`，理解 log 空间计算与 log-sum-exp。

### 本节被哪些后续内容用到
- [阶段 01 · 09 信息论](../../09-information-theory/docs/zh.md)：交叉熵、KL 散度与"最大似然 = 最小化交叉熵"直接相连。
- [阶段 01 · 13 数值稳定性](../../13-numerical-stability/docs/zh.md)：log 空间计算、log-sum-exp 的系统讲解。
- [阶段 01 · 15 机器学习统计](../../15-statistics-for-ml/docs/zh.md)：假设检验、置信区间，与本节的可信区间、贝叶斯 A/B 测试对照。
- [阶段 01 · 16 Sampling 方法](../../16-sampling-methods/docs/zh.md)：Monte Carlo、MCMC——没有共轭先验时如何近似后验。
- [阶段 02 · 14 朴素贝叶斯](../../../02-ml-fundamentals/14-naive-bayes/docs/zh.md)：Gaussian / Multinomial / Bernoulli NB 的完整展开。
- [阶段 02 · 17 不平衡数据](../../../02-ml-fundamentals/17-imbalanced-data/docs/zh.md)：基础率问题在分类评估与阈值设定中的体现。
- [阶段 03 · 07 正则化](../../../03-deep-learning-core/07-regularization/docs/zh.md)：L1/L2 正则——即本节"先验即正则"的工程形态。
- [阶段 08 · 02 自编码器与 VAE](../../../08-generative-ai/02-autoencoders-vae/docs/zh.md)：变分推断用优化来近似后验，ELBO 由贝叶斯公式推出。
- [阶段 17 · 21 LLM 功能的 A/B 测试](../../../17-infrastructure-and-production/21-ab-testing-llm-features/docs/zh.md)：本节贝叶斯 A/B 测试在生产环境中的落地。

### 延伸关键词
`共轭先验 (Conjugate Prior)` · `Dirichlet-Multinomial` · `Thompson Sampling` · `MCMC` · `变分推断 (Variational Inference)` · `贝叶斯因子 (Bayes Factor)` · `BIC` · `概率校准 (Calibration)` · `log-sum-exp` · `生成式 vs 判别式模型`
