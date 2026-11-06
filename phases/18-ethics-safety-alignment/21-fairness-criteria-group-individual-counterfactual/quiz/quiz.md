# 测验 · 公平性标准：群体、个体与反事实（Fairness Criteria — Group, Individual, Counterfactual）

> **阶段 18 · 伦理、安全与对齐 · 第 21 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **符号约定**：讲义用 `Y` 表示**预测**、`Y*` 表示**真实标签**。本测验沿用这种写法，必要时写成 `Ŷ`（预测）与 `Y`（标签），会在题中说明。中文讲义是机器翻译（如把 "base rates" 译成"基本利率"、"Impossibility" 译成"不可想象性"），以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Demographic parity（人口统计均等） | `P(Ŷ=1 | A=a) = P(Ŷ=1 | A=a')`：各组通过率相同，不看真实标签 |
| 2 | Equalized odds（均等几率） | 在真实标签条件下预测分布相同：各组 TPR 相等**且** FPR 相等 |
| 3 | Conditional use accuracy equality | 在预测条件下真实标签分布相同：各组 PPV 相等**且** NPV 相等（预测值的"含金量"一样） |
| 4 | 不可能性定理 | Chouldechova、Kleinberg-Mullainathan-Raghavan 2017：基础率（base rate）不等时，三者不能同时满足（除非是完美分类器等退化情形） |
| 5 | Chouldechova 恒等式 | `FPR = p/(1−p) · (1−PPV)/PPV · TPR`。只要 p 不同，TPR、FPR 相同就必然导致 PPV 不同 |
| 6 | 个体公平（Dwork 2012） | `|f(x) − f(x')| ≤ L · d(x, x')`：相似的人得到相似的决定；难点在于相似度度量 d 是政策问题，不是统计问题 |
| 7 | 反事实公平（Kusner 2017） | 在人群的因果模型下，把个体的敏感属性反事实地改变后，决定不变；"只和 DAG 一样站得住" |
| 8 | CF 与准确率的权衡（讲义：NeurIPS 2024） | 存在固有权衡；模型无关的方法可以把"最优但不公平"的预测器转换成 CF 预测器，准确率损失有界，大小取决于最优预测器中敏感属性系数的大小 |
| 9 | 回溯反事实（arXiv:2401.13935） | 不去干预受保护属性，而是保持它不变、改变"初始条件"，来解释个体的结果 |
| 10 | 标准的选择是政策决定 | 三个家族在结构上不同；讲义（ICLR Blogposts 2024）：在明确的因果图下，某些群体公平度量蕴含反事实公平，表面上的对立部分源于因果模型不明确 |

### 核心技能（能动手做到）

- [ ] 从混淆矩阵手算各组的通过率、TPR、FPR、PPV、NPV，判断三个群体标准各自是否满足
- [ ] 用 Chouldechova 恒等式解释"为什么 base rate 不等时 EO 和 PPV 均等不能兼得"
- [ ] 读懂 `main.py` 的重加权，算出加权后的 base rate，并与 Kamiran-Calders reweighing 比较
- [ ] 核对代码 TAKEAWAY 的说法，区分哪些结论被运行结果支持、哪些不被支持
- [ ] 实现 Dwork 个体公平的 Lipschitz 违例计数（讲义练习 2）
- [ ] 为 `gen()` 画出因果 DAG，说出反事实公平在这个 DAG 下意味着什么

---

## 二、基础自测（选择题）

**Q1.** Equalized odds 要求各组之间：

- A. 通过率相等
- B. 真阳性率（TPR）和假阳性率（FPR）都相等
- C. 阳性预测值（PPV）和阴性预测值（NPV）都相等
- D. 准确率相等

**Q2.** Conditional use accuracy equality 在讲义中写作 `P(Y*=y | Y=y, A=a) = P(Y*=y | Y=y, A=a')`（Y 为预测，Y* 为真实标签）。它等价于各组之间：

- A. TPR 与 FPR 相等
- B. 通过率相等
- C. PPV 与 NPV 相等
- D. Lipschitz 常数相等

**Q3.** 关于 Chouldechova / KMR 2017 的不可能性结果，正确的是：

- A. 当各组 base rate 不等时，demographic parity、equalized odds、conditional use accuracy equality 不能同时满足（完美分类器等退化情形除外）
- B. 任何重加权都能同时满足三者
- C. 只要不把敏感属性作为特征输入，三者就能同时满足
- D. 只要 base rate 不等，任何单一标准都无法满足

**Q4.** Dwork 等人 2012 的个体公平 `|f(x) − f(x')| ≤ L · d(x, x')`，在实践中最核心的难点是：

- A. Lipschitz 常数 L 无法计算
- B. 需要因果 DAG
- C. 只适用于线性模型
- D. 任务相关的相似度度量 d 必须事先定义，而这是一个政策问题，不是统计问题

**Q5.** 关于 Kusner 等人 2017 的反事实公平，正确的是：

- A. 只需要群体层面的统计量
- B. 等价于 demographic parity
- C. 不需要任何因果假设
- D. 需要人群的因果模型（DAG），其结论只和这个 DAG 一样站得住

**Q6.** `main.py` 运行结果如下（seed 53）。哪项说法**被这次运行结果支持**？

```text
baseline:      DP 0.171/0.600  TPR 0.383/0.709  FPR 0.100/0.431  PPV 0.561/0.718  NPV 0.814/0.558
DP-reweighted: DP 0.292/0.304  TPR 0.617/0.386  FPR 0.183/0.176  PPV 0.529/0.772  NPV 0.865/0.464
```

- A. 重加权降低了 DP 差距，代价是 equalized odds 显著变差
- B. DP 差距从 0.429 降到 0.012；FPR 差距从 0.331 缩小到约 0.007；但 PPV 差距从 0.157 扩大到 0.244，NPV 差距从 0.256 扩大到 0.401
- C. 基线分类器满足 equalized odds
- D. 重加权后三个标准同时满足

**Q7.** 某组的 base rate 为 p = 0.25，分类器在该组的 PPV = 0.561、TPR = 0.383。根据 Chouldechova 恒等式 `FPR = p/(1−p) · (1−PPV)/PPV · TPR`，该组的 FPR 约为：

- A. 0.100
- B. 0.183
- C. 0.250
- D. 0.431

**Q8.** 回溯反事实（backtracking counterfactuals，arXiv:2401.13935）与传统（干预式）反事实的区别是：

- A. 它不需要任何因果模型
- B. 它证明了不可能性定理是错的
- C. 它不干预受保护属性，而是保持该属性不变、改变初始条件，去解释个体实际得到的结果
- D. 它把 embedding 偏见指标替换为概率指标

---

## 三、动手 / 代码题

**Q9.** 阅读 `main.py` 的重加权：

```python
    for x, y, a in train_data:
        if a == 0 and y == 1:
            weights.append(2.0)
        elif a == 1 and y == 1:
            weights.append(0.5)
        else:
            weights.append(1.0)
```

训练集中 group0 有 498 人，其中 141 个正例；group1 有 502 人，其中 305 个正例。

1. 计算两组原始 base rate 与**加权后** base rate，并解释为什么这组手工权重能让 DP 差距几乎消失。
2. Kamiran-Calders reweighing 的权重是 `w(a, y) = P(a)·P(y) / P(a, y)`。算出 4 个权重，并与代码的手工权重比较。
3. 为什么说代码的权重是"针对这份数据调出来的"？换一个随机种子会怎样？

**Q10.** 代码 TAKEAWAY 说："DP-targeted reweighting reduces the DP gap at the cost of equalized odds and conditional use accuracy."

1. 用 Q6 的数据分别算出 EO 的最大差距（max(|ΔTPR|, |ΔFPR|)）和 CUAE 的最大差距（max(|ΔPPV|, |ΔNPV|)），重加权前后各是多少？
2. 观察重加权后模型的权重 `[w_x0, w_x1, w_a, b] = [0.746, −0.063, −0.045, −0.644]`（基线为 `[0.891, −0.303, 1.347, −1.374]`），结合 `gen()` 的数据生成过程，解释为什么 EO **反而**大体改善了。
3. 重加权后 TPR 差距仍有 −0.231，这是系统性的还是噪声？给出理由。
4. 这句 TAKEAWAY 应该怎么改？

**Q11.** 讲义练习 2：在非敏感特征 (x0, x1) 上用 L2 距离实现 Dwork 个体公平检查，L = 1，统计测试集 500 人中所有 124,750 对的违例数。分别用"概率输出 f(x) = σ(z)"和"硬决策 1[z>0]"两种 f，对基线和重加权模型计算。再统计"只翻转输入特征 a、保持 x0/x1 不变"时决策改变的人数。解释结果。

**Q12.** 讲义练习 3/5：为 `gen()` 画出因果 DAG：

```python
        a = random.choice([0, 1])
        base = 0.3 if a == 0 else 0.6
        y = 1 if random.random() < base else 0
        x0 = random.gauss(0.8 * y, 1.0)
        x1 = random.gauss(-0.3 + a * 0.5, 1.0)
        data.append(([x0, x1, float(a)], y, a))
```

1. 写出 A、Y、X0、X1 之间的边。哪些观测特征是 A 的后代？
2. Kusner 等人指出：只用 A 的**非后代**做预测的预测器是反事实公平的。在这个 DAG 下，这意味着什么？
3. Q11 中"只翻转输入特征 a"算不算一次合法的反事实？如果不算，正确的反事实应当如何构造？

---

## 四、面试高频题

**Q13.**（基础必考）请解释 demographic parity、equalized odds、predictive parity（PPV 均等）的定义，并说明为什么 base rate 不等时它们不能同时满足。

**Q14.**（原理深挖）个体公平和反事实公平分别要求什么？它们各自最脆弱的假设是什么？

**Q15.**（场景设计）你负责一个贷款审批模型，不同群体的历史违约率不同。业务方问"我们的模型公平吗？"，你怎么回答、怎么选标准？

**Q16.**（追问型）"我们没有把性别和种族作为特征，所以模型是公平的。"这句话对吗？请结合本节代码说明。

**Q17.**（工程实践）在一个实际项目中，你会如何把公平性评估和缓解接入模型开发流程？有哪些类别的缓解方法？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Equalized odds. P(Y=1 | Y*=y, A=a) = P(Y=1 | Y*=y, A=a'). Equal TPR and FPR across groups." 以真实标签为条件：y=1 时得 TPR，y=0 时得 FPR，两者都要相等。A 是 demographic parity；C 是 conditional use accuracy equality；D 不在讲义的三个标准中，而且准确率相等并不蕴含任何一个标准。

### Q2 — 答案：C

以预测为条件：Ŷ=1 时 `P(Y=1 | Ŷ=1)` 是 PPV，Ŷ=0 时 `P(Y=0 | Ŷ=0)` 是 NPV。Key Terms："equal PPV/NPV"。A 把条件方向弄反了，这是最容易混淆的一点：**EO 以真实标签为条件，CUAE 以预测为条件**。

### Q3 — 答案：A

讲义："these three cannot be satisfied simultaneously under unequal base rates." 更细的说法是两两冲突：EO 与 PPV 均等不能兼得（Chouldechova，见 Q7 的恒等式），DP 与 EO 不能兼得（除非 TPR = FPR，即分类器与标签无关）。B、C 错：重加权和"不用敏感属性"都改变不了数学约束。D 说过了头：任何**单一**标准都可以满足（本节代码的重加权就近似满足了 DP）。

### Q4 — 答案：D

讲义："Requires defining d. Policy question, not statistical." 例如"两个申请人相似"是看收入、学历，还是还要看邮编？这本身就是价值判断。A 错：对给定的 f 和 d，L 可以估计或设定。B 是反事实公平的要求。C 错：Lipschitz 条件适用于任何映射。

### Q5 — 答案：D

讲义："Requires a causal DAG. The DAG is a modeling choice. Counterfactual fairness is only as justified as the DAG." A、C 正好相反；B 错：反事实公平是个体层面的因果概念，与 DP 不等价（讲义提到在特定因果图下某些群体度量可以蕴含 CF，但这不是一般性的等价关系）。

### Q6 — 答案：B

逐项计算（group1 − group0）：

| 指标 | 基线差距 | 重加权后差距 |
|------|---------|------------|
| 通过率（DP） | +0.429 | +0.012 |
| TPR | +0.326 | −0.231 |
| FPR | +0.331 | −0.007 |
| PPV | +0.157 | +0.244 |
| NPV | −0.256 | −0.401 |

- A 不被支持：EO 的两个分量中，FPR 差距几乎消失，TPR 差距的绝对值也从 0.326 降到 0.231。EO 整体是**变好**的（见 Q10）。
- C 错：基线的 TPR 差距和 FPR 差距都超过 0.3，严重违反 EO。这也说明"基线分类器三个标准**全都不满足**"，而不只是"三个标准相互冲突"。
- D 错：PPV、NPV 差距反而扩大了。

### Q7 — 答案：A

`0.25 / 0.75 × (1 − 0.561) / 0.561 × 0.383 = 0.3333 × 0.7825 × 0.383 ≈ 0.100`。这正是基线 group0 的实际 FPR（0.100）。该恒等式只由混淆矩阵的定义推出，对任何分类器都**精确成立**（已在本次运行的 4 个"组 × 模型"组合上逐一验证）。B（0.183）是重加权后 group0 的 FPR，D（0.431）是基线 group1 的 FPR。

由恒等式可以看出不可能性：若两组 TPR、FPR 都相等（满足 EO），则 `(1−PPV)/PPV = FPR/TPR × (1−p)/p`。p 不同，PPV 必然不同。

### Q8 — 答案：C

论文摘要：不去想象"换一个受保护特征"，而是"imagine different initial conditions while keeping that characteristic fixed"。讲义的表述是："instead of intervening on the attribute, ask what combination of the individual's actual features would have produced the counterfactual outcome"，并把它的意义归结为规避法律上的反对。原论文摘要更强调的是"人口属性干预在形式框架中难以良好定义"，法律只是动机之一。A 错：回溯反事实同样需要因果模型；B、D 无关。

### Q9 — 参考答案

1. **base rate**（已用代码统计验证）：
   - group0：原始 `141/498 = 0.283`；加权后 `141×2 / (141×2 + 357×1) = 282/639 = 0.441`
   - group1：原始 `305/502 = 0.608`；加权后 `305×0.5 / (305×0.5 + 197×1) = 152.5/349.5 = 0.436`

   加权后两组的 base rate 几乎相等（0.441 vs 0.436）。在加权数据上，A 与 Y 近似独立，于是模型从"a 能预测 y"这件事里学不到东西：a 的权重从 1.347 降到 −0.045，代理特征 x1 的权重从 −0.303 降到 −0.063。模型的决策几乎只依赖 x0，各组的通过率也就趋于一致。

2. **Kamiran-Calders 权重**（n = 1000，其中 A=0 有 498 人、A=1 有 502 人；Y=1 有 446 人、Y=0 有 554 人）：

   | (a, y) | 计数 | `P(a)P(y)/P(a,y)` | 代码手工权重 |
   |--------|------|------------------|------------|
   | (0, 1) | 141 | 498×446/(1000×141) = **1.575** | 2.0 |
   | (0, 0) | 357 | 498×554/(1000×357) = **0.773** | 1.0 |
   | (1, 1) | 305 | 502×446/(1000×305) = **0.734** | 0.5 |
   | (1, 0) | 197 | 502×554/(1000×197) = **1.412** | 1.0 |

   KC 权重**同时**调整正例和负例，使加权后的 A 与 Y 严格独立；代码只调正例，靠"凑"使两组 base rate 接近。用 KC 权重实际重训（seed 53）：DP 差距 −0.021，TPR 差距 −0.225，FPR 差距 −0.060，PPV 差距 +0.303，NPV 差距 −0.387，准确率 0.652，与手工权重的效果相近。

3. 手工权重 2.0 / 0.5 恰好让这份数据的加权 base rate 接近（0.441 vs 0.436），这是数据相关的"凑数"。在其他种子上（实际运行了 seed 0–4），重加权后的 DP 差距分别为 −0.020、−0.052、−0.248、+0.138、−0.009，seed 2 过度矫正，seed 3 矫正不足。应当从数据中计算权重（KC），而不是写死。

### Q10 — 参考答案

1. 最大差距：

   | | EO 最大差距 | CUAE 最大差距 | 整体准确率 |
   |---|---|---|---|
   | 基线 | max(0.326, 0.331) = **0.331** | max(0.157, 0.256) = **0.256** | 0.710 |
   | 重加权 | max(0.231, 0.007) = **0.231** | max(0.244, 0.401) = **0.401** | 0.658 |

   EO 变好，CUAE 变差，准确率下降 5.2 个百分点。

2. **为什么 EO 改善**：在 `gen()` 中，`x0 ~ N(0.8y, 1)` **只依赖 y**；`x1` 只依赖 a。重加权后模型几乎不用 a 和 x1，决策近似为 `1[0.746·x0 − 0.644 > 0]`。在给定 y 的条件下，x0 的分布与 a 无关，所以 TPR、FPR 在期望上对两组相同，EO 近似满足。再由 Chouldechova 恒等式，base rate 不同（测试集中 0.25 vs 0.608），PPV、NPV 就必然分化，这正是 CUAE 变差的原因。这才是"Chouldechova 定理的缩影"：**满足（近似的）EO，就付出 predictive parity 的代价**。

3. **−0.231 主要是噪声**：测试集 group0 只有 60 个正例，group1 有 158 个，TPR 差距的标准误约为 √(0.5·0.5/60 + 0.5·0.5/158) ≈ 0.075。按重加权模型的权重解析计算（z 在 y=1 条件下服从正态分布，均值为 −0.028 − 0.077a，标准差为 0.749），两组的期望 TPR 分别约为 0.485 和 0.444，差距只有约 −0.04。观测值偏离约 2.5 个标准误，主要来自测试样本的随机性，以及 SGD 最终迭代点的噪声。多种子运行时，这个差距在 −0.456 到 +0.083 之间波动，符号都不稳定。

4. **改写建议**："With unequal base rates, DP-targeted reweighting closes the DP gap; on this data it also roughly equalizes odds (the model stops using a), but conditional use accuracy (PPV/NPV) diverges and overall accuracy drops. No classifier can satisfy all three when base rates differ." 同时应报告多种子均值与置信区间，而不是单次运行的结果。

### Q11 — 参考答案

```python
import math
def prob(mod, x):
    z = mod[3] + sum(w * v for w, v in zip(mod[:3], x))
    return 1 / (1 + math.exp(-z))

def lipschitz_violations(mod, data, L=1.0, hard=False):
    f = [prob(mod, x) for x, _, _ in data]
    if hard:
        f = [1.0 if p > 0.5 else 0.0 for p in f]
    v = 0
    for i in range(len(data)):
        for j in range(i + 1, len(data)):
            xi, xj = data[i][0], data[j][0]
            d = math.hypot(xi[0] - xj[0], xi[1] - xj[1])   # 只用非敏感特征 x0, x1
            if abs(f[i] - f[j]) > L * d + 1e-12:
                v += 1
    return v
```

实际运行结果（seed 53 的测试集，124,750 对）：

| 模型 | 概率输出违例数 | 硬决策违例数 | 只翻转 a 后决策改变的人数 |
|------|--------------|------------|----------------------|
| 基线 | 1,264 | 9,051（7.3%） | **230 / 500** |
| 重加权 | 2 | 4,075（3.3%） | 12 / 500 |

解释：
- 基线直接把 a 作为特征（权重 1.347）。两个非敏感特征几乎相同、但 a 不同的人，概率输出会相差很多，而 d ≈ 0，于是违例。重加权后 a 的权重接近 0，违例几乎消失。
- 对于概率输出 σ(w·x + b)，它对非敏感特征的 Lipschitz 常数不超过 `|(w0, w1)| / 4`（sigmoid 导数最大为 1/4）。基线约为 0.94/4 ≈ 0.23 < 1，所以违例**全部**来自 a 的跳变；重加权后仅剩的 2 对，也来自 a 的权重 −0.045 造成的微小跳变。
- 硬决策是不连续函数：决策边界附近距离很近的两个人可能一个通过、一个不通过，所以只要 L 有限，就**一定**会有违例。这说明个体公平更适合用于连续分数，或者需要随机化的决策。
- "只翻转 a"时基线有 46% 的人决策改变，这是一个强烈的"直接歧视"信号。但它并不是严格意义上的反事实（见 Q12）。

### Q12 — 参考答案

1. **DAG**：`A → Y`（base rate 依赖 a）、`Y → X0`、`A → X1`；此外 A 本身作为第三个特征直接输入模型。观测特征 X0（通过 Y）和 X1 **都是 A 的后代**。
2. Kusner 的结论"只用 A 的非后代"在这里意味着：**没有任何对预测 Y 有用的观测特征可用**，X0 有用，但它是 A 的后代。反事实公平的预测器只能依赖从模型推断出的外生噪声（例如 `x1 − 0.5a` 是 X1 的噪声项，但与 Y 无关），或者只能是常数。这暴露出 CF 的一个核心张力：如果 A → Y 这条边本身是"真实的"（例如历史不公造成的基础率差异），CF 就会要求模型放弃所有经由这条路径的信息。是否接受这条路径是**政策选择**（讲义："Choosing a standard is a policy decision"）。
3. 不算。合法的反事实要经过三步（abduction → action → prediction）：先推断个体的外生噪声 U（例如 `U1 = x1 − (−0.3 + 0.5a)`），再把 A 设为 a'，然后按结构方程重新生成所有后代：`x1' = −0.3 + 0.5a' + U1`；Y 和 X0 也要按 Y 的噪声重新生成（例如 y 由 `U_y < base(a)` 决定，翻转 a 可能改变 y，进而改变 x0）。"只翻转输入特征 a"忽略了 X1 和 X0 也会随之改变，测到的只是模型对 a 这一列的直接依赖（直接效应），不是 Kusner 意义上的总效应。

### Q13 — 参考回答要点

- **定义**（Ŷ 为预测，Y 为标签）：
  - DP：`P(Ŷ=1|A=a)` 各组相等；
  - EO：`P(Ŷ=1|Y=y, A=a)` 各组相等，即 TPR、FPR 均等；
  - Predictive parity（CUAE 的一半）：`P(Y=1|Ŷ=1, A=a)` 各组相等，即 PPV 均等。
- **为什么不能兼得**：
  - EO vs PPV：恒等式 `FPR = p/(1−p) · (1−PPV)/PPV · TPR`。若各组 TPR、FPR 都相同而 p 不同，PPV 必然不同；唯一的例外是完美分类器（FPR = 0）等退化情形。
  - DP vs EO：通过率 `= p·TPR + (1−p)·FPR`。p 不同而 TPR、FPR 相同，通过率就不同；要让 DP 也成立，只能 TPR = FPR，即分类器与标签无关、毫无用处。
- 加分点：能举出 COMPAS 再犯预测的争议。ProPublica 指出 FPR 不等，开发方回应 PPV（校准）相等，两边都"对"，因为两组 base rate 不同。这正是 Chouldechova 论文的背景。

### Q14 — 参考回答要点

- **个体公平**（Dwork 2012）：相似的人得到相似的决定，形式化为 Lipschitz 条件。
  - 最脆弱的假设：**相似度度量 d**。d 里包含什么特征、权重多大，决定了一切；如果 d 本身编码了历史偏见（例如把邮编当作"相似"的依据），满足个体公平也毫无意义。讲义："Policy question, not statistical."
  - 实践难点：硬决策不连续，决策边界附近必然违例（Q11）。
- **反事实公平**（Kusner 2017）：在因果模型中改变个体的敏感属性，决定不变。
  - 最脆弱的假设：**因果 DAG** 与结构方程，包括外生噪声的分布。讲义："only as justified as the DAG"。
  - 概念难点：对种族、性别这类属性做"干预"是否有意义（回溯反事实正是为此提出的）；如果 A 影响了几乎所有特征，CF 可能要求放弃大量有用信息（Q12）；讲义还提到 NeurIPS 2024 关于 CF 与准确率存在固有权衡的结论。
- **与群体公平的关系**：讲义（ICLR Blogposts 2024）指出，在明确的因果图下，某些群体度量蕴含 CF，三个家族是同一因果结构的不同侧面；但这并不能消除不可能性定理。

### Q15 — 参考回答要点

- **先拒绝二元回答**：`skill-fairness-criterion.md` 的 Refusal rules："If the user asks whether a model is 'fair,' refuse the binary claim; fairness is criterion-relative."
- **审计 base rate**：各群体历史违约率不同，不可能性定理适用，必须选择优先满足哪个标准。
- **按价值目标选标准**：
  - 强调"同样会还款的人，被批准的机会相同"→ equalized odds 或 equal opportunity（TPR 均等）；
  - 强调"批准的含金量相同、风险定价一致"→ predictive parity / 校准（贷方关心的风险一致性）；
  - 强调"各群体获得贷款的比例相同"（例如出于纠正历史不公的政策目标）→ demographic parity，但要接受准确率损失和更高的个体违约风险。
- **因果层面**：画出 DAG，判断哪些路径是"合法"的（如收入 → 还款能力），哪些是"不合法"的（如邮编作为种族代理）；考虑反事实公平或路径特定公平。
- **报告**：给出所选标准下的差距与置信区间、对其他标准的影响、准确率代价，并明确写出"这是一个政策选择"。
- 加分点：提到合规约束，例如信贷领域的反歧视法规可能限制直接使用受保护属性，这会影响能采用的缓解方法（第 24 节）。

### Q16 — 参考回答要点

- **不对**。这叫"fairness through unawareness"（无意识公平），通常不够：
  1. **代理变量**：在 `gen()` 中，x1 的均值随 a 变化（`−0.3 + 0.5a`），就是 a 的代理。去掉 a 后，模型仍可以通过 x1 间接利用群体信息。现实中的邮编、姓名、毕业院校、消费习惯都可能是代理。
  2. **标签本身有群体差异**：即使模型完全不知道 A，只要 base rate 不同，预测就会在群体间产生不同的通过率与 PPV（Q13）。在本节数据中，只用 x0 的分类器可以近似满足 EO，但 DP 和 PPV 均等仍然不满足。
  3. **妨碍审计与纠偏**：不收集敏感属性，就无法测量群体差距，也无法做 KC 重加权这类需要知道 A 的缓解。
- **反过来**：本节代码基线**直接把 a 作为特征**（权重 1.347），"只翻转 a"就让 46% 的决策改变（Q11），属于直接依赖受保护属性，在很多场景下本身就不合规。
- 加分点：区分"训练和推理时不使用 A"与"评估时使用 A"。后者通常是必要的。

### Q17 — 参考回答要点

- **流程**：
  1. 在需求阶段确定受保护属性、要采用的公平标准和可接受差距（政策决定，需要业务、法务、伦理多方参与）；
  2. 数据阶段：审计各组的样本量与 base rate，检查代理变量，记录到数据集卡（第 26 节）；
  3. 训练与评估阶段：在每次评估中按组报告混淆矩阵派生的指标，**附置信区间，并做多种子或 bootstrap**（本节代码的单次运行结论不稳，Q10）；
  4. 发布门禁：差距超过阈值就阻断发布；
  5. 上线后：监控各组的实际结果，注意分布漂移和反馈回路（被拒的人没有后续标签，即 selective labels 问题）。
- **缓解方法三类**：
  - 预处理：重加权（Kamiran-Calders）、重采样、学习去除群体信息的表示；
  - 训练中：带公平约束或正则的优化（如约束 TPR 差距）、对抗去偏；
  - 后处理：按组设定阈值（例如 Hardt 等人的 equalized odds 后处理），或者对分数做校准。
- **权衡**：每种缓解都要报告对整体准确率和**其他**公平标准的影响（本节中 DP 变好、PPV 变差）。
- 常见误区：只看一个指标、只跑一次、只在训练集上评估。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 20 LLMs 中的偏见与表征性伤害](../../20-bias-representational-harm/docs/zh.md)：上一节测量偏见，本节定义测量应服务的公平标准；分配性伤害正是本节标准的作用对象。
- [阶段 02 · 03 逻辑回归](../../../02-ml-fundamentals/03-logistic-regression/docs/zh.md)：`main.py` 的分类器就是逐样本 SGD 训练的逻辑回归。
- [阶段 02 · 09 模型 Evaluation](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：混淆矩阵、TPR/FPR/PPV/NPV 的定义。
- [阶段 02 · 17 处理不平衡数据](../../../02-ml-fundamentals/17-imbalanced-data/docs/zh.md)：样本重加权的通用技巧。
- [阶段 01 · 07 贝叶斯定理](../../../01-math-foundations/07-bayes-theorem/docs/zh.md)：PPV 与 base rate 的关系（Chouldechova 恒等式本质上是贝叶斯公式）。
- [阶段 01 · 21 机器学习的图论](../../../01-math-foundations/21-graph-theory/docs/zh.md)：DAG 的基本概念。

### 本节被哪些后续内容用到
- [阶段 18 · 22 面向 LLMs 的差分隐私](../../22-differential-privacy-for-llms/docs/zh.md)：同属"用户侧伤害"层；隐私与公平之间也存在权衡（DP 噪声对少数群体的影响更大）。
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：高风险 AI 系统的公平与非歧视要求。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../26-model-system-dataset-cards/docs/zh.md)：按组报告性能指标是模型卡的标准内容。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../../17-infrastructure-and-production/26-compliance-frameworks/docs/zh.md)：把公平性审计纳入生产合规流程。

### 延伸关键词
`demographic parity` · `equalized odds / equal opportunity` · `predictive parity / calibration` · `Chouldechova impossibility` · `base rate` · `COMPAS` · `fairness through unawareness` · `proxy variable` · `Kamiran-Calders reweighing` · `post-processing thresholds (Hardt 2016)` · `Lipschitz individual fairness` · `counterfactual fairness` · `abduction-action-prediction` · `backtracking counterfactuals` · `path-specific fairness`
