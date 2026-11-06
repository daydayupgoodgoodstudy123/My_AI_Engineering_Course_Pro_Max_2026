# 测验 · Evaluation 与 LLM 应用测试（Evaluation & Testing LLM Applications）

> **阶段 11 · LLM 工程 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/eval_framework.py](../code/eval_framework.py) ｜ 代码讲解：[code/eval_framework.讲解.md](../code/eval_framework.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三类评估 | automated metrics（快/免费/会漏语义）、LLM-as-judge（主力/花钱/与人相关性 82–88%）、human eval（金标准/最慢最贵，只用于校准） |
| 2 | LLM-as-judge | 把 (input, output, 可选 reference, rubric) 交给强模型打分；是 90% 情况下会用的方法 |
| 3 | 四个常用维度 | relevance、correctness、helpfulness、safety，各 1–5 分 |
| 4 | rubric 设计 | 把每个分数锚定到可观察的具体行为；锚定描述能把 judge 方差降低 30–40% |
| 5 | pairwise / best-of-N | 两两比较避开"3 还是 4"的刻度校准问题；best-of-N 衡量系统上限 |
| 6 | 六步流水线 | Prompt → Run → Collect → Score → Compare → Decide |
| 7 | 数据集三件套 | golden set（50–100，回归用）、adversarial（20–50，攻击用）、distribution（100–200，真实流量） |
| 8 | 样本量与置信区间 | 50 个用例 95% CI 宽达 19 个百分点；要做部署决策至少 200，比较相近系统用 500+ |
| 9 | 回归测试 | 每次改 prompt / 换模型 / 调参都要 before/after 对比，用统计检验判断有无回归 |
| 10 | 反模式 | 凭感觉看几条、在训练样例上测、只看单一指标、没有 baseline、用弱 judge |

### 核心技能（能动手做到）

- [ ] 用 dataclass 定义 TestCase / EvalResult / EvalScore，并说清 `__post_init__` 的作用
- [ ] 实现 rubric 锚定的 LLM-as-judge 打分（本节是模拟 judge，要能指出它和真 judge 的差距）
- [ ] 手写 ROUGE-L（LCS + F1），并解释它为什么会把语义相同但用词不同的答案判低分
- [ ] 实现并解释 Wilson 区间与 bootstrap 区间，知道各自适用于"通过率"还是"均值"
- [ ] 看懂 compare_eval_runs 的 ship/block 逻辑，指出它用阈值而非统计显著性判断回归的问题
- [ ] 根据可容忍的回归幅度反推需要多少测试用例

---

## 二、基础自测（选择题）

**Q1.** 关于三类评估方法，按讲义的说法正确的是：

- A. automated metrics 与人类判断相关性最高，应作为主力
- B. human eval 又快又便宜，应该在每次提交时都跑
- C. LLM-as-judge 是日常会用 90% 的主力方法，在设计良好的 rubric 上与人类相关性约 82–88%，介于廉价字符串指标与昂贵人工之间
- D. 三类方法任选其一即可，不需要互相校准

**Q2.** 讲义说"anchored descriptions reduce judge variance by 30-40%"。这里的"锚定"指的是：

- A. 把 judge 模型的 temperature 固定为 0
- B. 把每个分数（1–5）都对应到具体、可观察的行为描述，而不是用"打个 1–5 分看它多好"这种模糊标准
- C. 把所有测试用例的参考答案固定下来
- D. 用同一个 judge 模型评所有维度

**Q3.** 当你在对比"prompt v1 和 v2 哪个好"、又不想纠结"这答案算 3 分还是 4 分"时，最合适的评估方式是：

- A. 单点打分（single grader）
- B. pairwise comparison：让 judge 直接看两个输出选更好的那个
- C. 只看 ROUGE-L
- D. 只做 human eval

**Q4.** 讲义的样本量表格指出：50 个用例、观测准确率 90% 时，95% 置信区间宽约 19 个百分点。由此能得出的结论是：

- A. 50 个用例足够区分一个 80% 的系统和一个 96% 的系统
- B. 50 个用例时无法可靠检测 5% 的回归；要做部署决策至少用 200 个，比较相近系统用 500+
- C. 置信区间宽窄只取决于准确率，与样本量无关
- D. 用例越多准确率一定越高

**Q5.** 下列哪一项**不是**讲义列出的评估反模式？

- A. 凭感觉读 5 条输出就下结论
- B. 在训练/few-shot 用过的样例上做评估
- C. 用比被测模型更强的模型当 judge
- D. 没有 baseline，只看一个孤立的 4.2/5

**Q6.** 实际运行本节代码，对"How do you hack into a bank account?"这条用例，`baseline-v1` 的输出被判 `safety=1`。真正的原因是：

- A. 模型真的输出了危险内容
- B. 模拟 judge 的 safety 规则检查输出里是否含 `hack / exploit / steal / weapon / illegal`，而模型的输出把问题里的 "hack" 原样回显了进去，于是被判 1 分——这是基于关键词、不看语义的误判
- C. reference answer 里含有 "illegal"
- D. output 太短

**Q7.** 本节 `bootstrap_confidence_interval` 对同一组分数连续调用两次，返回值：

- A. 每次都不同，因为用了随机采样
- B. 完全相同，因为它用 `seed_base = int(sum(scores) * 1000) % 2**31` 从数据派生种子，再用线性同余生成"随机"下标，整个过程是确定性的
- C. 只有均值相同，上下界不同
- D. 会抛异常，因为没有真随机源

**Q8.** 对 `rouge_l_score("The capital of France is Paris.", "Paris is the capital of France.")`，实际返回 0.5。原因是：

- A. 两句话完全无关
- B. 两句话语义相同但 ROUGE-L 只看最长公共子序列（保持词序），LCS 是 "the capital of"（3 词，`paris.` 与 `france.` 带句号不匹配），precision = recall = 3/6，F1 = 0.5
- C. ROUGE-L 把大小写当作不同词
- D. 函数有 bug，应该返回 1.0

---

## 三、动手 / 代码题

**Q9.** 阅读 `simulate_judge_score`（节选）：

```python
    base_score = 3
    if output_len < 10:
        base_score = 1
    elif output_len > input_len * 0.5:
        base_score = 4
    if reference_output:
        overlap = len(ref_words & out_words) / max(len(ref_words), 1)
        if overlap > 0.5:
            base_score = min(5, base_score + 1)
        elif overlap < 0.1:
            base_score = max(1, base_score - 1)
    ...
    seed = int(hashlib.md5(f"{input_text}{model_output}{criterion}".encode()).hexdigest(), 16) % 100
    if seed < 15:  base_score = max(1, base_score - 1)
    elif seed > 85: base_score = min(5, base_score + 1)
```

1. 这个"judge"实际上在用哪些信号打分？它和讲义描述的真正 LLM-as-judge 有什么本质区别？
2. 其中编码了哪一种 judge 的已知偏见（讲义在别处提到过）？用一个例子说明。
3. `hashlib.md5(...) % 100` 那段起什么作用？它让这个 judge 变得"更像真的"还是"更不可信"？

**Q10.** 阅读 `rouge_l_score`：

```python
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref_tokens[i - 1] == hyp_tokens[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs_length = dp[m][n]
    precision = lcs_length / n
    recall = lcs_length / m
    f1 = (2 * precision * recall) / (precision + recall)
```

1. 解释这个二维 dp 在算什么，时间复杂度是多少。
2. 对 `rouge_l_score("Python is a programming language.", "Python is a programming language.")`，返回值是多少？`rouge_l_score("", "x")` 呢？
3. 举一个"答案完全正确但 ROUGE-L 很低"的例子，说明为什么不能只用 ROUGE-L 做 correctness 评估。
4. 这个实现没做分词规范化（标点、大小写）。给出一个因此被低估的例子，并说明怎么改。

**Q11.** 阅读 `compare_eval_runs` 的判定逻辑：

```python
        if diff < -0.3:
            report["regressions"].append(criterion)
            criterion_report["status"] = "REGRESSION"
        elif diff > 0.3:
            ...
    ...
    "ship_decision": "SHIP" if not report["regressions"] else "BLOCK",
```

实际运行中，`baseline-v1 → baseline-v2` 的报告是：overall 3.844 → 3.875，helpfulness 从 3.625 降到 3.375（diff −0.250，判为 STABLE），最终 `Decision: SHIP`。

1. helpfulness 明明降了，为什么没有触发 BLOCK？这个 ±0.3 的阈值有什么问题？
2. 讲义要求"用统计检验（paired t-test 或 bootstrap）判断回归"。代码里已经算了 bootstrap CI，但 ship/block 决策用到它了吗？应该怎么用？
3. 这个评估只有 8 个用例。按讲义的样本量表，用 8 个用例做 ship/block 决策合理吗？

**Q12.** 关于置信区间：

```python
def wilson_confidence_interval(successes, total, z=1.96):
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return (round(max(0.0, center - spread), 4), round(min(1.0, center + spread), 4))
```

1. 本节同时实现了 Wilson 区间和 bootstrap 区间。它们分别适合评估"通过率"还是"平均分"？为什么通过率不直接用正态近似 `p ± 1.96·√(p(1−p)/n)`？
2. 用这个函数算：45/50（90%）和 180/200（90%）的区间宽度各是多少？（可只保留小数点后两位）这与讲义样本量表的结论一致吗？
3. 讲义 Sample Size 一节说"要检测 5% 的回归，50 个用例不够"。请据此说明：如果你希望 90% 准确率的 95% CI 宽度不超过 5 个百分点，大约需要多少用例？

---

## 四、面试高频题

**Q13.**（基础必考）LLM 应用的评估有哪三大类方法？各自的速度、成本、与人类的相关性、适用场景是什么？为什么说"没有一种单独够用"？

**Q14.**（原理深挖）LLM-as-judge 怎么做？它有哪些已知偏见？怎么降低这些偏见、怎么验证 judge 本身可信？

**Q15.**（工程实践）你要给一个线上 LLM 功能搭 CI 里的回归测试，请从数据集、指标、样本量、统计判定、成本几个方面给出方案。

**Q16.**（场景设计）要评估一个 RAG 客服系统，你会设计哪些评估维度和数据集？怎么把"检索对不对"和"答得对不对"分开评？

**Q17.**（追问型）自动指标（BLEU/ROUGE/BERTScore）在什么时候仍然有用？它们和 LLM-as-judge 是替代还是互补关系？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："LLM-as-judge ... This is the evaluation method you will use 90% of the time"，相关性表里 LLM-as-judge 为 82–88%，而 BLEU/ROUGE 只有 40–60%、BERTScore 55–70%、human 100%（按定义）。A 错（自动指标相关性最低）；B 错（human eval 最慢最贵，只用于校准）；D 错（讲义明确要用 human eval 校准自动评估）。

### Q2 — 答案：B

讲义对比了"Rate from 1-5 how good the answer is"（坏）和把 5/4/3/2/1 各自锚定到具体行为（好），并指出锚定能把 judge 方差降低 30–40%。A（temperature）、C（参考答案）、D（同一 judge）都不是"锚定 rubric"的含义。本节 `RUBRICS` 字典正是这种锚定描述的实现。

### Q3 — 答案：B

讲义："Pairwise comparison ... This eliminates scale calibration issues -- the judge does not need to decide if something is a '3' or a '4.' It just picks the winner. Useful for comparing two prompt versions head-to-head." A 仍有刻度问题；C 只看词序重叠，判不了语义质量；D 太慢太贵，不适合频繁对比。

### Q4 — 答案：B

讲义样本量表：50 个用例 90% 时 CI 宽 19 点、"No"（无法检测 5% 回归）；200 个时宽 9 点、"Yes"。并明确："Use at least 200 test cases for any evaluation where you need to make deployment decisions. Use 500+ if you are comparing two systems that are close in quality." A 恰好是讲义反驳的（19 点宽无法区分 80% 和 96%）；C 错（样本量显著影响宽度）；D 无因果关系。

### Q5 — 答案：C

讲义反模式列表："Using a weak judge. GPT-3.5 as a judge produces noisy, inconsistent scores ... The judge must be at least as capable as the model being evaluated." 所以"用更强的模型当 judge"恰恰是**推荐**做法，不是反模式。A（vibes-based）、B（testing on training examples）、D（evaluating without baselines）都是讲义明列的反模式。

### Q6 — 答案：B

`simulate_judge_score` 的 safety 分支：`unsafe_patterns = ["hack", "exploit", "steal", "weapon", "illegal"]`，只要输出里出现任一关键词就返回 1。`baseline-v1` 对这条用例的输出是 "The answer to your question about How do you hack into is as follows..."——它把问题里的 "hack" 回显了进去，于是被判 safety=1（已实际运行验证）。这是典型的**关键词匹配误判**：输出其实是无害的套话，却因为含 "hack" 字样被判为危险。A 错（输出并无危险内容）；C 错（reference 里没有触发词，且 safety 分支不看 reference）；D 错（长度不影响 safety 分支的返回）。这正好说明关键词过滤式的 safety 评估不可靠。

### Q7 — 答案：B

`seed_base = int(sum(scores) * 1000) % 2**31`，之后用线性同余 `seed = (seed * 1103515245 + 12345) % 2**31` 生成下标——没有任何真随机源，同样的输入必然得到同样的输出（已实际运行，两次调用结果都是 `(3.7333, 4.0667, 4.4)`）。这保证了 demo 可复现，但也意味着它不是真正的随机重采样：所谓的"1000 次 bootstrap"其实是一个固定的伪随机序列，区间的统计意义有限。A、C、D 都与实现不符。

### Q8 — 答案：B

分词后 ref = `[the, capital, of, france, is, paris.]`、hyp = `[paris, is, the, capital, of, france.]`（各 6 词）。最长公共子序列（保持词序）是 "the capital of"（3 词）——`paris.` 与 `paris`、`france.` 与 `france` 因为句号不同不算匹配。于是 precision = recall = 3/6 = 0.5，F1 = 0.5（已实际运行验证）。这说明 ROUGE-L **只看词面和词序**：两句话意思完全一样，却因为词序重排和标点被判半分。A 错（两句语义相同）；C 错（代码 `.lower()` 了，大小写不敏感）；D 错（0.5 是正确结果）。

### Q9 — 参考答案

1. 它用的信号全是**表面特征**：输出长度（`output_len < 10` → 1 分，`> input_len * 0.5` → 4 分）、与 reference 的词集合重叠率、关键词命中（safety）、与 input 的关键词重叠率（relevance），最后叠一个由 md5 派生的"伪随机扰动"。真正的 LLM-as-judge 是把 (input, output, rubric) 交给一个**强语言模型**去理解语义后打分，能判断事实正确性、是否答到点子上等表面特征完全看不出的东西。这个模拟 judge 没有任何语义理解，纯靠长度和词重叠。
2. 编码了**冗长偏好（verbosity bias）**：`output_len > input_len * 0.5` 就给 4 分，等于"越长越高分"。例子：问 "What is 2+2?"，答 "4" 会因为太短（<10 字符）被判 1 分，而一段啰嗦但不一定更对的长答案能拿 4 分。实测 `simulate_judge_score("Q?", "Yes.", ...)` 得 2 分、`"x"*500` 得 4 分。讲义也提到真实 judge 有"preferring verbose responses"的偏见（quiz.json 的解析里也点出了这一点）。
3. `md5(...) % 100` 把输入哈希成 0–99 的确定性数，`<15` 减 1 分、`>85` 加 1 分，模拟"judge 有一定随机波动"。它让分数看起来有抖动（更像真 judge 的非确定性），但因为是确定性哈希，同样输入永远得同样结果——既不是真的随机，又给分数加了与质量无关的噪声，整体上让这个 judge **更不可信**。真实评估中我们恰恰想**减少**这种与质量无关的方差（靠锚定 rubric、多次采样取平均）。

### Q10 — 参考答案

1. `dp[i][j]` 是 ref 前 i 个词与 hyp 前 j 个词的**最长公共子序列（LCS）长度**。词相等时 `dp[i][j] = dp[i-1][j-1] + 1`，否则取 `max(dp[i-1][j], dp[i][j-1])`。时间和空间复杂度都是 O(m·n)。
2. 两句完全相同时 LCS = 5（`python is a programming language.`），precision = recall = 1，F1 = **1.0**。`rouge_l_score("", "x")`：函数开头 `if not reference or not hypothesis: return 0.0`，空串直接返回 **0.0**。
3. 例子：参考答案 "The capital of France is Paris."，模型答 "Paris."——完全正确但 LCS 只有 1，ROUGE-L 很低。反过来，"The capital of France is Berlin." 和参考只差一个词，ROUGE-L 很高却事实错误。所以 ROUGE-L 衡量的是**词面重叠**，不是**语义正确性**；correctness 应交给 LLM-as-judge 或带 reference 的语义指标（BERTScore）。
4. 因为不做规范化，`"Paris."`（带句号）与 `"Paris"` 被当成不同词。例子：ref "...is Paris." 与 hyp "...is Paris" 的末词不匹配，LCS 少 1。改法：分词前统一小写（已做）并去除标点，例如 `re.findall(r"[a-z0-9]+", text.lower())`，或用更规范的分词器。

### Q11 — 参考答案

1. 因为 helpfulness 的 diff 是 −0.250，没有越过 `diff < -0.3` 的阈值，所以被判 STABLE 而非 REGRESSION，`regressions` 列表为空，于是 `ship_decision = "SHIP"`。问题：**±0.3 是个拍脑袋的固定阈值**，与样本量、方差都无关。8 个用例上 0.25 的均值下降很可能是真实回归，也可能是噪声，但这个阈值既不看置信区间是否重叠，也不看变化方向是否一致。一个"刚好 −0.29"的明显下降会被放行。
2. **没用到**。代码算了 `baseline_ci`、`new_ci` 两个 bootstrap 区间并打印出来，但 ship/block 完全由 `diff` 和 ±0.3 阈值决定，区间只是展示。正确做法：判断两个区间是否重叠，或对配对分数做 bootstrap/配对检验看差值的置信区间是否跨 0——差值 CI 完全落在 0 以下才算显著回归（讲义："Compare scores with a statistical test (paired t-test or bootstrap)"）。
3. 不合理。讲义明确"至少 200 个用例才能做部署决策"，8 个用例的置信区间极宽（Wilson 对 80% 通过率、n=8 时宽度超过 0.5），任何 ship/block 结论都在噪声范围内。这个 demo 的 8 个用例只是教学规模。

### Q12 — 参考答案

1. **Wilson 区间**适合评估**通过率/比例**（二项型数据，如"≥4 分的比例"）；**bootstrap 区间**适合评估**均值/任意统计量**（如平均分，分数不是 0/1）。通过率不直接用正态近似 `p ± 1.96·√(p(1−p)/n)` 是因为：当 p 接近 0 或 1、或 n 较小时，正态近似的区间会超出 [0,1]、甚至覆盖率严重失真；Wilson 区间对小样本和极端比例更稳健（不会越界，且中心会向 0.5 收缩）。
2. 实测：45/50（90%）→ `(0.786, 0.957)`，宽度约 **0.17**（17 个百分点）；180/200（90%）→ `(0.851, 0.934)`，宽度约 **0.08**（8 个百分点）。这与讲义样本量表"50 个用例宽 19 点、200 个用例宽 9 点"基本一致（讲义是约数，Wilson 区间略窄一点）。
3. 从表格看，宽度随 n 大致按 1/√n 收窄：n=200 约 9 点、n=500 约 5 点。所以要让 90% 准确率的 95% CI 宽度 ≤ 5 个百分点，大约需要 **500 个用例**（讲义表格里 n=500 对应宽 5 点、"Confidently"）。这也呼应讲义"比较相近系统用 500+"的建议。

### Q13 — 参考回答要点

- **三类**（讲义 taxonomy 表）：
  - automated metrics（BLEU/ROUGE/BERTScore/exact match）：<1 秒、$0、与人相关性 40–70%，适合翻译/摘要基线、语义相似度初筛；
  - LLM-as-judge：分钟级、每千次约 $3–25、相关性 82–88%，是日常主力；
  - human eval：小时级、每千次约 $500、相关性 100%（按定义），只用于校准和边界/政策判断。
- **为什么单独不够**：字符串指标看不懂语义（词面不同但都对、或词面像却错）；LLM-as-judge 有偏见且本身要靠 human 校准；human 太贵太慢不能每次跑。实践是分层：便宜指标初筛 → judge 做主力 → 人工校准 judge 并处理边界。
- 加分点：相关性数字、成本量级能说出来；提到要定期用 human 标注验证 judge 的相关性是否漂移。

### Q14 — 参考回答要点

- **怎么做**：给强模型 (input, output, 可选 reference, 锚定 rubric)，让它按维度打分并给理由；本节用 relevance/correctness/helpfulness/safety 四维、1–5 分。
- **已知偏见**：冗长偏好（偏爱长答案，本节模拟 judge 的长度规则就是这种偏见的极端化）、位置偏好（pairwise 时偏向第一个/第二个）、自我偏好（偏爱同家族模型的输出）、对自信语气的偏好。
- **降低偏见**：用锚定 rubric（降方差 30–40%）；pairwise 时交换顺序各评一次取平均；控制长度或在 rubric 里明确"简洁优先"；多次采样取多数/均值；用足够强的 judge（讲义：judge 至少要和被测模型一样强）。
- **验证 judge 可信**：用一批 human 标注做校准，计算 judge 与 human 的相关性/一致率（讲义：82–88%），并定期复校。
- 加分点：指出本节的 `simulate_judge_score` 只是关键词 + 长度的占位实现，真实系统必须换成真模型。

### Q15 — 参考回答要点

- **数据集**：golden set 50–100（回归基线）+ adversarial 20–50（注入、越权、边界）+ distribution 100–200（真实流量采样）；eval 数据与训练/few-shot 严格隔离。
- **指标**：以 LLM-as-judge 多维打分为主（锚定 rubric），辅以便宜的自动指标初筛；安全类单独严格评。
- **样本量**：做 ship/block 至少 200，比较相近版本 500+。
- **统计判定**：每次改动跑 before/after，对配对分数做 bootstrap/配对检验，差值 CI 完全落在阈值坏侧才算回归——而不是像本节那样用固定 ±0.3 阈值。
- **成本**：按 judge 单价估算（讲义：200 用例 × 4 维用便宜 judge 约 $4/次），和"漏掉回归的代价"权衡；高频可先便宜 judge 筛、再对可疑项上贵 judge。
- **工程**：接进 CI，每个 PR 自动跑、不达标就 block；记录 model/temperature/prompt 版本便于追溯。
- 加分点：提到用 promptfoo / DeepEval / Braintrust 等现成工具而非全手写。

### Q16 — 参考回答要点

- **拆成检索和生成两层**：
  - 检索层：Recall@k、MRR、nDCG——标注每个问题的相关文档，看是否被召回（见第 07 节 Advanced RAG）。
  - 生成层：faithfulness（回答是否有检索内容支撑，防幻觉）、answer relevance（是否答到问题）、correctness（对不对）。
- **数据集**：真实客服问题 + 已知答案所在文档；加对抗样本（答案不在库里时应说"不知道"）、多跳问题、时效性问题。
- **分开评的意义**：答错可能是"检索没召回对的文档"（检索问题）或"召回了对的文档却答错"（生成问题），两者修法完全不同；只看端到端答对率无法定位。
- **方法**：faithfulness 可用 NLI 或 LLM-as-judge 逐 claim 核对；检索指标用标注数据算；端到端用 judge + human 校准。
- 加分点：提到 RAGAS（讲义表里列出，NLI faithfulness + judge，相关性约 85%）、阶段 19 的 RAG Evaluation 课程。

### Q17 — 参考回答要点

- **仍然有用的场景**：有明确参考答案且表述受限的任务（机器翻译、抽取、摘要基线）；需要**零成本、秒级**对海量输出做初筛；回归监控里当廉价的第一道闸。BERTScore 用 embedding 做语义相似，比纯 n-gram 好，适合相似度筛查。
- **局限**：词面重叠不等于语义正确（ROUGE-L 的 0.5 例子），一个词之差的事实错误查不出来。
- **关系**：**互补**而非替代。典型分层：先用便宜的自动指标过滤明显无关/明显一致的样本，再把需要判断语义质量的交给 LLM-as-judge，最后用 human 校准 judge。单独依赖任何一层都不够（讲义："None is sufficient alone"）。
- 加分点：能说出 BLEU（n-gram precision，翻译）、ROUGE（召回，摘要）、BERTScore（embedding 语义）各自的出身和适用面。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 01 Prompt Engineering：技术与模式](../../01-prompt-engineering/docs/zh.md)：有了评估才能科学地迭代 prompt。
- [阶段 11 · 07 Advanced RAG（Chunking、重排序、混合检索）](../../07-advanced-rag/docs/zh.md)：RAG 的 Recall@k、faithfulness 评估。
- [阶段 05 · 27 LLM Evaluation — RAGAS、DeepEval、G-Eval](../../../05-nlp-foundations-to-advanced/27-llm-evaluation-frameworks/docs/zh.md)：讲义多处引用的 judge 校准与 RAG 指标。

### 本节被哪些后续内容用到
- [阶段 11 · 12 Guardrails,安全及内容过滤](../../12-guardrails/docs/zh.md)：safety 评估与内容过滤。
- [阶段 11 · 13 构建生产环境中的 LLM 应用](../../13-production-app/docs/zh.md)：把评估接入 CI 与上线流程。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：模型级基准评测（MMLU 等）。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：把 eval 作为 agent 开发的驱动力。
- [阶段 19 · 68 RAG Evaluation：精确率、召回率、MRR、nDCG、忠实度与回答相关性](../../../19-capstone-projects/68-rag-eval-precision-recall/docs/zh.md)、[阶段 19 · 75 端到端评估执行器](../../../19-capstone-projects/75-end-to-end-eval-runner/docs/zh.md)：综合项目中的完整评估系统。

### 延伸关键词
`LLM-as-judge` · `G-Eval` · `pairwise comparison` · `best-of-N` · `rubric anchoring` · `ROUGE-L / BLEU / BERTScore` · `Wilson interval` · `bootstrap` · `paired t-test` · `verbosity bias / position bias` · `golden set / adversarial set` · `regression gate` · `promptfoo / DeepEval / Braintrust / LangSmith` · `RAGAS`
