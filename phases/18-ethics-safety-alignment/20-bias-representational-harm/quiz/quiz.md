# 测验 · LLMs 中的偏见与表征性伤害（Bias and Representational Harm in LLMs）

> **阶段 18 · 伦理、安全与对齐 · 第 20 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **提醒**：中文讲义为机器翻译，术语误译较多（如 "representational harm" 被译成"代表伤害"、"WinoIdentity" 被译成"双点识别/共度"、"debiasing" 被译成"贬低"），以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 表征性伤害（representational harm） | 刻板印象、抹除（erasure）、贬低性描绘，例如把护士描绘为只有女性 |
| 2 | 分配性伤害（allocational harm） | 不平等的物质结果，例如系统性地给某族裔申请者的简历打低分；与表征性伤害相互独立，两者都要测 |
| 3 | Gallegos 等人 2024 的三类评估指标 | embedding-based（WEAT 类，测表示而非行为）、probability-based（刻板/反刻板补全的对数似然）、generated-text-based（下游任务，生态效度最高但最难复现） |
| 4 | WEAT | `s(w,X,Y) = mean cos(w,X) − mean cos(w,Y)`，再比较两组身份词 s 的均值差；原版 effect size 还要除以标准差，并配合置换检验 |
| 5 | 交叉性（intersectionality） | 只在（性别 × 种族）组合上出现的偏见，单轴评估看不到；An 等人 2025 发现 GPT-4o 对黑人女性的简历惩罚大于对黑人男性和白人女性 |
| 6 | WinoIdentity（COLM 2025） | 基于**不确定性**的交叉公平评估：比较模型在不同交叉身份组合上的不确定性，而不只比较点预测 |
| 7 | 机制可解释性方法 | gender neurons（Yu & Ananiadou 2025，MLP 神经元）、SAE 特征（Ahsan & Wallace 2025，临床种族偏见）、UniBias（Zhou 等人 2024，操纵内部组件） |
| 8 | 投影去偏及其局限 | 把属性词在"性别方向"上的分量投影掉，能降低指标但降不到 0：偏见还编码在其他方向上（本节代码可精确演示） |
| 9 | 元批评（arXiv:2508.11067） | 十年文献过度集中在二元性别；残障、宗教、移民身份、多语言身份等维度研究不足，"没人检查的维度可能偏得很严重" |
| 10 | 偏见与蓄意伤害的区别 | 偏见是"无意产生的伤害"，来自数据分布、提示框架和累积的设计选择，与对抗鲁棒性是不同的方法学问题 |

### 核心技能（能动手做到）

- [ ] 判断一个具体案例属于表征性伤害还是分配性伤害，并说明为什么两者都要测
- [ ] 手算一个词的 WEAT 关联分数 `s(w, X, Y)`，并解释 `main.py` 输出的 +0.8906 是怎么来的
- [ ] 实现标准化的 WEAT effect size 与置换检验，说出"3 个词一组"时 p 值的下限
- [ ] 解释投影去偏后指标没有归零的**真实原因**，并用实验验证
- [ ] 把探针扩展到交叉维度（性别 × 种族），计算交互项
- [ ] 针对一份偏见评估报告，检查指标类别覆盖、交叉性覆盖和去偏机制（对应 `outputs/skill-bias-eval.md`）

---

## 二、基础自测（选择题）

**Q1.** 某招聘系统用 LLM 给简历打分，系统性地给某族裔申请者更低的分数。这属于：

- A. 表征性伤害，因为它反映了刻板印象
- B. 分配性伤害，因为它造成了不平等的物质结果
- C. 不属于偏见，因为模型没有输出任何贬低性文字
- D. 对抗攻击造成的伤害

**Q2.** Gallegos 等人 2024 年的综述把偏见评估指标分为哪三类？

- A. embedding-based、probability-based、generated-text-based
- B. WEAT、BLEU、ROUGE
- C. 预训练前、RLHF 中、RLHF 后
- D. 文本、图像、语音

**Q3.** 在 `main.py` 中，WEAT 分数为正表示什么？

- A. 模型没有偏见
- B. 身份组 B 比 A 更关联 X
- C. 去偏操作成功
- D. 身份组 A（he/his/man）比 B（she/her/woman）更关联 X（engineer/programmer/scientist）

**Q4.** 讲义引用 An 等人（PNAS Nexus 2025）的发现来说明为什么需要交叉性评估。该发现是：

- A. 所有模型对所有群体的评分都一样
- B. 只有 Llama 3-70B 存在偏见
- C. GPT-4o 在简历评分中对黑人女性的惩罚，大于分别对黑人男性和白人女性的惩罚
- D. 种族偏见在加入性别维度后消失了

**Q5.** WinoIdentity（COLM 2025）相比传统单轴、点预测式偏见评估的改进在于：

- A. 比较模型在不同交叉身份组合上的**不确定性**，能捕捉"各组错得一样多、但对某些组更不确定"的情况
- B. 用 300 维 embedding 替代 4 维 embedding
- C. 只评估二元性别
- D. 用越狱攻击测试偏见

**Q6.** `debias()` 只对 6 个属性词做投影，`gender_dir = [1, -1, 0, 0]`。去偏后 `engineer`（原为 `[0.4, 0, 1.0, 0]`）变成：

- A. `[0.4, 0.0, 1.0, 0.0]`（不变）
- B. `[0.0, 0.0, 1.0, 0.0]`
- C. `[0.2, -0.2, 1.0, 0.0]`
- D. `[0.2, 0.2, 1.0, 0.0]`

**Q7.** 运行 `main.py`，WEAT 从 +0.8906 降到 +0.2212，没有归零。真实原因是：

- A. 玩具 embedding 只有 4 维，维度太低
- B. 去偏只处理了属性词在性别方向上的分量，而身份词本身带有 tech/care 分量（he 的 tech 为 0.2，she 的 care 为 0.2），偏见编码在性别方向之外
- C. 余弦相似度计算中的 `1e-9` 造成了误差
- D. 投影公式写错了，没有真正投影

**Q8.** 讲义引用的十年文献元批评（arXiv:2508.11067）的核心论点是：

- A. 交叉性研究已经过多
- B. 偏见研究不应使用定量方法
- C. 领域过度集中于二元性别偏见，残障、宗教、移民身份、多语言身份等维度研究不足，被忽视的群体可能因此受害
- D. 各维度研究已经很均衡

---

## 三、动手 / 代码题

**Q9.** 手算。代码中的向量如下（4 维：masculine、feminine、tech、care）：

```python
    "he":        [ 1.0, 0.0, 0.2,  0.0],
    "engineer":  [ 0.4, 0.0, 1.0,  0.0],
    "scientist": [ 0.3, 0.0, 1.0,  0.1],
    "nurse":     [ 0.0, 0.4, 0.0,  1.0],
    "teacher":   [ 0.0, 0.3, 0.1,  1.0],
```

`programmer` 与 `engineer` 相同，`caregiver` 与 `nurse` 相同。

1. 计算 `cos(he, engineer)`、`cos(he, scientist)`、`cos(he, nurse)`、`cos(he, teacher)`（保留 4 位小数）。
2. 计算 `s(he, X, Y)`。
3. 已知 6 个身份词的 s 值关于性别对称，只有 `man`（+0.3396）与 `woman`（−0.4230）不对称，验证 `pre = +0.8906`。

**Q10.** `main.py` 打印的是 "WEAT effect size"，但它只计算了两组 s 值的**均值差**。Caliskan 等人 2017 的原始 WEAT 中，effect size 还要除以全部身份词 s 值的标准差，并用置换检验给出 p 值。

1. 实现 `weat_effect_size` 和 `weat_permutation_p`（对 6 个身份词做所有 3+3 的划分）。
2. 报告去偏前后两者的值，并解释：为什么均值差降低了约 75%，标准化 effect size 却几乎没变？
3. 本例置换检验 p 值可能取到的最小值是多少？这对"3 个词一组"的小样本 WEAT 意味着什么？

**Q11.** 验证 Q7 的结论，并比较三种去偏方案：
- (a) 原代码：只对属性词投影掉性别方向；
- (b) 对**所有词**（含身份词）都投影掉性别方向；
- (c) 在 (a) 的基础上，再把身份词的 tech/care 分量清零。

分别报告 WEAT 均值差，并说明这对真实 embedding 去偏（Bolukbasi 2016）有什么启示。

**Q12.** 讲义练习 2：把探针扩展为交叉性测试（性别 × 种族）×（career, family）。设计一个 6 维玩具 embedding，计算 4 个交叉组的 s 值，并定义一个"交互项"来量化单轴评估看不到的部分。

---

## 四、面试高频题

**Q13.**（基础必考）表征性伤害和分配性伤害有什么区别？为什么一个模型可能"表征上无偏，但分配上有偏"？请各举一个 LLM 部署中的例子。

**Q14.**（原理深挖）比较 embedding-based、probability-based、generated-text-based 三类偏见指标的原理、优缺点和适用场景。为什么只用 WEAT 证明"模型无偏"是不够的？

**Q15.**（原理深挖）投影去偏（hard debiasing）的原理是什么？为什么它常常只是"把偏见藏起来"？

**Q16.**（场景设计）你要为一个用 LLM 辅助筛选简历的产品设计偏见评估方案，会怎么做？

**Q17.**（追问型）有研究找到了与性别偏见相关的 "gender neurons"，消融后偏见指标下降。你如何设计实验区分"这些神经元**导致**偏见"和"这些神经元只是与偏见**相关**"？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Allocational harm. Unequal material outcomes. An LLM that scores Black applicants' resumes systematically lower is producing allocational harm." A 混淆了两种伤害：刻板印象可能是**原因**，但伤害的**类型**由后果决定（资源分配不平等）。C 错：分配性伤害不需要任何贬低性文字，只看打分就够了。这正是讲义强调"一个模型可以表征上无偏、分配上有偏"的原因。D 错：偏见是"无意产生的伤害"，与对抗攻击无关。

### Q2 — 答案：A

讲义："Embedding-based ... Probability-based ... Generated-text-based." B 中只有 WEAT 是偏见指标（属于 embedding-based），BLEU、ROUGE 是生成质量指标。C、D 不是 Gallegos 的分类方式。

### Q3 — 答案：D

代码打印："positive means identity A associates more with X than B does."。`weat_score` 返回 `mean_a − mean_b`，其中 `s(w) = mean cos(w,X) − mean cos(w,Y)`。A 组（男性词）的 s 平均为正（更接近 tech），B 组为负，所以差值为正。B 说反了；C 错：正值只表示存在关联，与去偏是否成功无关。

### Q4 — 答案：C

讲义："An et al. 2025 find GPT-4o penalizes Black women in resume scoring more than Black men and more than white women separately. Single-axis evaluation cannot capture this." 单看"性别"或单看"种族"都会把这种组合效应平均掉。A、D 与讲义相反；B 错，讲义说研究覆盖了 5 个模型（GPT-3.5 Turbo、GPT-4o、Gemini 1.5 Flash、Claude 3.5 Sonnet、Llama 3-70B）。

### Q5 — 答案：A

讲义："It measures whether the model's uncertainty over outcomes differs across intersectional identity tuples — not just the point prediction. This catches cases where the model is equally wrong across groups but more uncertain for some, which produces different downstream allocation behaviour." 例如下游系统只在模型"有把握"时自动通过，那么对某组更不确定，就意味着该组更多被转人工或被拒。B 是本节代码 TAKEAWAY 的内容；C、D 无关。

### Q6 — 答案：D

投影系数 `proj = (engineer · g) / |g|² = (0.4×1 + 0×(−1)) / 2 = 0.2`；`engineer − 0.2 × [1, −1, 0, 0] = [0.4−0.2, 0+0.2, 1.0, 0] = [0.2, 0.2, 1.0, 0.0]`。实际运行验证：去偏后 engineer 和 programmer 都是 `[0.2, 0.2, 1.0, 0.0]`，nurse 和 caregiver 都是 `[0.2, 0.2, 0.0, 1.0]`。投影后 masculine 与 feminine 两个分量**相等**，即在性别方向上中立。B 是"把两个性别分量都清零"，不是投影；C 把 `−proj × g` 的符号算反了。

### Q7 — 答案：B

去偏后，6 个属性词在性别方向上已经中立，剩下的 WEAT 完全来自身份词自身的 tech/care 分量：`he = [1, 0, 0.2, 0]` 带 0.2 的 tech，`she = [0, 1, 0, 0.2]` 带 0.2 的 care。已实际验证：在原代码去偏后，再把 6 个身份词的 tech/care 分量清零，WEAT 精确地降到 0.0。

- A 是代码 TAKEAWAY 的说法（"the metric does not drop to zero because the toy is 4-d"），但这并不是原因：即使换成 300 维，只要偏见编码在被投影方向之外，结果也一样。这类现象正是 Gonen & Goldberg 2019（"Lipstick on a Pig"）指出的：投影去偏会掩盖、但不会消除系统性偏见。
- C：`1e-9` 只影响零向量的情况，量级可忽略。
- D：投影公式是正确的（Q6 已验证）。

### Q8 — 答案：C

讲义："The 10-year literature review (arXiv:2508.11067, 2025) finds the field disproportionately focuses on binary-gender bias ... a model well-debiased on binary gender may be badly biased on dimensions nobody checked." 本节代码本身就是例子：它只测了二元性别。

### Q9 — 参考答案

1. `|he| = √(1 + 0.04) = 1.0198`，`|engineer| = √(0.16 + 1) = 1.0770`，`|scientist| = √(0.09 + 1 + 0.01) = 1.0488`，`|nurse| = 1.0770`，`|teacher| = 1.0488`。
   - `cos(he, engineer) = (0.4 + 0.2) / (1.0198 × 1.0770) = 0.6 / 1.0983 = 0.5463`
   - `cos(he, scientist) = (0.3 + 0.2) / (1.0198 × 1.0488) = 0.5 / 1.0696 = 0.4675`
   - `cos(he, nurse) = 0`（he 只有 masculine 和 tech 分量，nurse 只有 feminine 和 care 分量，两者正交）
   - `cos(he, teacher) = (0.2 × 0.1) / 1.0696 = 0.0187`
2. `mean cos(he, X) = (0.5463 + 0.5463 + 0.4675) / 3 = 0.5200`；`mean cos(he, Y) = (0 + 0.0187 + 0) / 3 = 0.0062`；`s(he) = 0.5138`。
3. 实际运行得到的 6 个 s 值：he 0.5138、his 0.4408、man 0.3396；she −0.5138、her −0.4408、woman −0.4230。`mean_a = 1.2942 / 3 = 0.4314`，`mean_b = −1.3776 / 3 = −0.4592`，差值为 `0.8906`，与输出一致。（`man` 带了 0.1 的 care，`woman` 带了 0.1 的 tech，两者都被"拉向中间"，但幅度不同，所以不对称。）

### Q10 — 参考答案

```python
import itertools, statistics

def s(E, w, X, Y):
    return (sum(cos(E[w], E[a]) for a in X) / len(X)
            - sum(cos(E[w], E[b]) for b in Y) / len(Y))

def weat_effect_size(E, A, B, X, Y):
    sa = [s(E, w, X, Y) for w in A]
    sb = [s(E, w, X, Y) for w in B]
    return (statistics.mean(sa) - statistics.mean(sb)) / statistics.stdev(sa + sb)

def weat_permutation_p(E, A, B, X, Y):
    words = A + B
    obs = sum(s(E, w, X, Y) for w in A) - sum(s(E, w, X, Y) for w in B)
    hits = total = 0
    for Ai in itertools.combinations(words, len(A)):
        Bi = [w for w in words if w not in Ai]
        stat = sum(s(E, w, X, Y) for w in Ai) - sum(s(E, w, X, Y) for w in Bi)
        total += 1
        hits += stat >= obs - 1e-12
    return hits / total
```

实际运行结果：

| | 均值差（代码打印的值） | 标准化 effect size | 置换 p 值 |
|---|---|---|---|
| 去偏前 | 0.8906 | 1.811 | 1/20 = 0.05 |
| 去偏后 | 0.2212 | 1.603 | 1/20 = 0.05 |

- 均值差降了 75%，但标准差也从 0.492 降到 0.138。去偏是"整体缩放"了所有 s 值，**组间分离的相对程度几乎没变**：男性词仍然全部为正、女性词仍然全部为负（`man` 为 0.0）。从统计意义上说，偏见的"可检测性"并没有被消除。
- 3+3 的划分只有 `C(6,3) = 20` 种，观测到的划分本身就是其中之一，所以 p 值最小只能是 1/20 = 0.05。这意味着**每组 3 个词的 WEAT 永远无法得到比 0.05 更强的显著性**。真实研究会用每组 8 个以上的词，并报告 effect size 与 p 值。

### Q11 — 参考答案

实际运行结果：

| 方案 | WEAT 均值差 |
|------|------------|
| 原始（不去偏） | 0.8906 |
| (a) 只对属性词投影掉性别方向（原代码） | 0.2212 |
| (b) 对所有词都投影掉性别方向 | **0.3080**（比 (a) 还高） |
| (c) (a) 基础上再把身份词的 tech/care 分量清零 | **0.0000** |

- (b) 反而更高：身份词的性别分量被投影成 `[0.5, 0.5, …]` 之后，余弦主要由剩下的 tech/care 分量决定，偏见的**相对**影响被放大了。
- (c) 能归零，但只有在玩具例子中，我们才知道偏见"藏在"哪个维度。
- **启示**：
  1. 偏见不一定只沿一个"性别方向"分布。在真实 embedding 中，与性别相关的信息分散在许多方向上（例如"职业邻居"的聚类结构），投影一个方向只能降低一种指标；
  2. 指标下降不等于偏见消除，需要用多种指标（聚类、分类器能否恢复性别信息、下游任务表现）交叉检验；
  3. 讲义强调：embedding-based 指标"measures the representation, not the behaviour"。即使 embedding 指标归零，生成文本里仍可能有偏见，因此需要 probability-based 和 generated-text-based 指标兜底。

### Q12 — 参考答案

```python
# 6 维：masc, fem, race1, race2, career, family
ID = {
 ("m","r1"): [1,0,1,0,0.2,0.0],
 ("m","r2"): [1,0,0,1,0.1,0.1],
 ("f","r1"): [0,1,1,0,0.1,0.1],
 ("f","r2"): [0,1,0,1,0.0,0.4],   # 交叉组额外偏向 family
}
X = [[0.2,0,0,0,1,0],[0.2,0,0,0,1,0.1]]   # career 词
Y = [[0,0.2,0,0,0,1],[0,0.2,0,0,0.1,1]]   # family 词
def s(v): return sum(cos(v,a) for a in X)/len(X) - sum(cos(v,b) for b in Y)/len(Y)
S = {k: s(v) for k, v in ID.items()}
inter = S[("f","r2")] - S[("f","r1")] - S[("m","r2")] + S[("m","r1")]
```

实际运行结果：

```text
('m','r1') 0.2671   ('m','r2') 0.1377   ('f','r1') -0.1377   ('f','r2') -0.3861
gender gap within r1 0.4048   within r2 0.5237
single-axis gender gap (avg over race) 0.4643
interaction term -0.119
```

- 单轴评估只会报告"性别差 0.464"，看不出 r2 组内的性别差（0.524）比 r1（0.405）更大。
- **交互项**（类似双因素方差分析中的交互效应）：`s(f,r2) − s(f,r1) − s(m,r2) + s(m,r1) = −0.119`。它衡量的是"(f, r2) 组偏离'性别效应 + 种族效应'加性预测的程度"。不为 0 就说明存在只在交叉处出现的偏见。An 等人 2025 年发现的"黑人女性受到的惩罚比两个单轴效应各自预示的更大"，正是交互项不为 0 的情形。
- 实践中，每个交叉组要用多个身份词（人名、代词组合）、报告每组 s 值的置信区间，并对交互项做置换检验。

### Q13 — 参考回答要点

- **表征性伤害**：对群体的描绘有偏，如刻板印象、抹除、贬低。例：让模型写"护士的一天"，100 次生成里主角几乎全是女性；或者某群体在生成的故事里从不出现。
- **分配性伤害**：对群体的物质结果有偏，如资源、机会、服务。例：用 LLM 给简历打分、审核贷款材料、分诊排序时，某群体系统性地得分更低。
- **为什么可能"表征无偏、分配有偏"**：模型可能被调得在开放生成中描绘多样（表征指标好看），但在打分、排序这类决策任务中，仍然通过姓名、学校、措辞等代理特征（proxy）给出不同结果。两类伤害由不同的输出通道产生，所以讲义说 "Evaluations need to measure both."
- 加分点：说明分配性伤害往往牵涉法律（如雇佣歧视法），而表征性伤害会长期影响社会认知、放大刻板印象。

### Q14 — 参考回答要点

| 类别 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| Embedding-based（WEAT、SEAT） | 身份词与属性词在向量空间中的余弦关联 | 便宜、可复现、不需要生成 | 测的是"表示"而不是"行为"（讲义原话）；对词表选择敏感；上下文化模型中 embedding 与输出的关系很弱 |
| Probability-based（如 CrowS-Pairs、StereoSet 类） | 比较刻板与反刻板补全的对数似然 | 直接作用于解码器，能捕捉部分行为偏见 | 依赖模板句、对措辞敏感；需要访问 logits，闭源 API 不一定提供 |
| Generated-text-based | 在下游任务（简历打分、推荐信写作、对话）中统计生成结果 | 生态效度最高（讲义："Most ecologically valid"） | 最难复现（讲义："hardest to reproduce"）；需要评分器，评分器本身也可能有偏 |

- **为什么只靠 WEAT 不够**：Q10、Q11 已经证明，WEAT 会被去偏操作"刷低"，但偏见仍在别的方向上；WEAT 也不反映 RLHF 之后模型的实际行为。`skill-bias-eval.md` 的 Hard rejects 第一条就是："Any 'debiased' claim based on a single metric category."
- 加分点：说明三类指标之间的相关性往往很弱，所以要"覆盖每个类别至少一个指标"。

### Q15 — 参考回答要点

- **原理**（Bolukbasi 2016 思路）：先用若干性别词对的差向量（如 he−she、man−woman）估计"性别方向"g；对本应性别中立的词（职业等），减去它在 g 上的投影 `w − (w·g / |g|²) g`，使其在性别方向上中立。原论文还有"equalize"步骤，让性别词对关于中立词对称。本节代码直接手工指定 `g = [1, −1, 0, 0]`，只做了中立化这一步。
- **为什么常常只是"藏起来"**：
  1. 偏见不只沿一个方向分布：Q11 中残留的偏见全部在 tech/care 维度上；
  2. 去偏后，"原本有性别偏向的词"仍然彼此聚在一起，用分类器或聚类仍能恢复性别信息（Gonen & Goldberg 2019，"Lipstick on a Pig"）；
  3. 指标缩小可能只是整体尺度缩小，标准化 effect size 几乎不变（Q10：1.81 → 1.60）；
  4. 对 LLM 而言，静态 embedding 去偏几乎不影响上下文表示和生成行为。
- **更好的做法**：多指标评估；在模型内部定位偏见机制（gender neurons、SAE 特征）后做有针对性的干预，并衡量通用能力的损失（skill 要求 "general-capability delta"）；在数据和后训练层面治理。

### Q16 — 参考回答要点

- **定义伤害**：主要是分配性伤害（打分、排序、是否进入面试），兼顾表征性伤害（生成的评语中带刻板印象）。
- **反事实配对测试**（generated-text-based）：同一份简历，只替换姓名、代词、能暗示身份的经历（如女子学院、宗教社团），比较分数分布；覆盖性别、种族及**它们的交叉**（参照 An 等人 2025 的方法），并扩展到年龄、残障、移民背景等元批评指出的薄弱维度。
- **统计方法**：每组足够样本，报告各组平均分、通过率差异，以及交叉组的交互项和置信区间；同时比较模型的**不确定性**（如多次采样的方差，参照 WinoIdentity），因为不确定性高的组更可能被转人工或被拒。
- **公平标准选择**：明确采用哪个公平标准（如通过率均等或机会均等），并说明这是政策选择（第 21 节）。
- **持续监控**：上线后按组统计实际通过率，定期复测；模型版本或提示词更新后都要回归测试。
- **缓解**：去除或遮蔽身份信息；在提示中给出结构化的评分标准；对分数做事后校准；保留人工复核。缓解后要重新跑全套评估，并报告对整体准确率的影响。
- 加分点：注意这类系统在很多司法辖区属于高风险 AI 用途（第 24 节），需要文档化与审计。

### Q17 — 参考回答要点

讲义练习 4 的要点："这些神经元导致偏见" vs "只是与偏见相关"。

- **相关性证据**（不够）：神经元激活与性别词同时出现；消融后偏见指标下降。但消融后指标下降也可能是因为：消融破坏了模型的一般语言能力（所有输出变得更平淡）；或者这些神经元只是性别信息的**下游读出**，真正的原因在上游。
- **因果检验设计**：
  1. **激活修补（activation patching）**：在"男性语境"的前向传播中，把这些神经元的激活替换为"女性语境"下的值，其余不变；如果输出的偏向按预期翻转，支持因果作用；
  2. **剂量—反应关系**：按比例缩放激活（0×、0.5×、1×、2×），偏见指标应单调变化；
  3. **特异性对照**：随机消融同等数量、激活统计特征相近的神经元，偏见下降应明显更小；同时测量通用能力（困惑度、标准基准），确认偏见下降不是"模型变笨"造成的；
  4. **必要性 vs 充分性**：只消融这些神经元，看偏见是否消失（必要性）；只激活这些神经元而去掉其他性别线索，看偏见是否出现（充分性）。
  5. **泛化**：在训练时未使用的新模板、新职业词上检验因果效应是否依然成立。
- 加分点：说明偏见通常由许多组件**分布式**实现，单个神经元集合往往只解释部分效应；SAE 特征也有类似的"特征是否真的被模型使用"问题。

---

## 六、关联知识点

### 前置知识
- [阶段 05 · 03 词 Embeddings——从零实现 Word2Vec](../../../05-nlp-foundations-to-advanced/03-word-embeddings-word2vec/docs/zh.md)：WEAT 测量的对象就是这类词向量（讲义先修要求 "Phase 05 (word embeddings)"）。
- [阶段 01 · 14 范数与距离](../../../01-math-foundations/14-norms-and-distances/docs/zh.md)：余弦相似度、投影的数学基础。
- [阶段 18 · 01 将指令遵循作为 Alignment 信号](../../01-instruction-following-alignment-signal/docs/zh.md)：讲义的先修要求。
- [阶段 18 · 07 潜伏 Agents：持续性欺骗](../../07-sleeper-agents-persistent-deception/docs/zh.md)：残差流探针，以及"相关 vs 因果"的可解释性方法。

### 本节被哪些后续内容用到
- [阶段 18 · 21 公平性标准：群体、个体与反事实](../../21-fairness-criteria-group-individual-counterfactual/docs/zh.md)：本节测量偏见，下一节定义测量应服务的公平标准。
- [阶段 18 · 22 面向 LLMs 的差分隐私](../../22-differential-privacy-for-llms/docs/zh.md)：同属"用户侧伤害"层。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../26-model-system-dataset-cards/docs/zh.md)：偏见评估结果的披露载体。
- [阶段 18 · 29 内容审核系统：OpenAI、Perspective、Llama Guard](../../29-moderation-systems-openai-perspective-llamaguard/docs/zh.md)：审核分类器本身也存在群体偏见问题。
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：招聘等高风险场景的合规要求。

### 延伸关键词
`representational harm` · `allocational harm` · `WEAT / SEAT` · `effect size + permutation test` · `CrowS-Pairs / StereoSet` · `counterfactual resume audit` · `intersectionality` · `interaction effect` · `WinoIdentity` · `hard debiasing (Bolukbasi 2016)` · `Lipstick on a Pig` · `gender neurons` · `SAE features` · `activation patching` · `UniBias`
