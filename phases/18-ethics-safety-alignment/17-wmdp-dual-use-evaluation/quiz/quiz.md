# 测验 · WMDP 与两用能力 Evaluation（WMDP and Dual-Use Capability Evaluation）

> **阶段 18 · 伦理、安全与对齐 · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：本节讨论的是**如何测量**危险能力，题目与答案只涉及评估方法、统计与治理，不涉及任何具体的危险技术内容。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两用能力的测量难题 | 直接测量（让模型真的产出危害内容）既违法又不道德；代理测量需要一个模型无法拒绝（才能得到诚实的能力数字）、而题目本身又不构成有害出版物的基准 |
| 2 | WMDP 基准 | 讲义：Li 等（ICML 2024, arXiv:2403.03218），4,157 道多选题：生物安全 1,520、网络安全 2,225、化学 412 |
| 3 | Yellow zone | 题目考察"与有害过程邻近的、起使能作用的知识"，但不是直接的合成配方；每题经多位领域专家审查，并按 ITAR/EAR 出口管制合规过滤 |
| 4 | 多选题格式的意义 | 模型只需选答案，不需要"协助"任何事，因此可以在不诱发有害行为的情况下测出能力 |
| 5 | RMU | Representation Misdirection for Unlearning：WMDP 配套的遗忘（unlearning）方法，把 WMDP 分数压到接近随机水平，同时让 MMLU 等通用能力只下降几个百分点；WMDP 因此既是评估基准也是 unlearning 基准 |
| 6 | 2024–2025 uplift 叙事 | 讲义：2024 年"mild uplift"（比互联网搜索略有帮助）→ 2025 年 4 月 OpenAI Preparedness Framework v2 称模型"on the cusp of meaningfully helping novices create known biological threats" → Anthropic 2025 年生物武器获取阶段试验报告 2.53 倍 uplift，"不足以排除 ASL-3" |
| 7 | 新手相对 uplift vs 专家绝对能力 | 前者是模型给非专家带来的倍数提升（新手知道得少，相对优势大）；后者是有动机的专家能从模型中榨取的最大信息量；安全论证（safety case）两者都要覆盖 |
| 8 | 测量陷阱 | WMDP 是能力代理，不是部署风险的测量；实际风险还取决于引出阻力（elicitation resistance）、隐性知识（tacit knowledge，需要湿实验技能）和执行障碍（采购、设备） |
| 9 | 拒答路径审计 | 评估是在原始补全上做的还是经过生产安全栈？只因安全栈而得分低的模型，一旦安全栈被绕过仍具两用能力 |
| 10 | 证据层级 | 多选题能力 ≠ 引出加固后的能力；"没有显著 uplift"的结论需要新手参与（novice-in-the-loop）的研究支撑 |

### 核心技能（能动手做到）

- [ ] 读懂玩具 harness：按领域的伯努利抽样评估、RMU 风格的"目标领域降准确率 + 其他领域固定附带损失"
- [ ] 手算 unlearning 后每个领域的期望准确率，并找出 `strength` 超过多少时会被 0.25 的随机下限截断
- [ ] 计算 200 题、412 题、1,520 题下准确率的标准误，判断"3~4 个百分点的附带损失"能否被测出来
- [ ] 指出代码中"相对随机猜测的倍数"与讲义"新手相对 uplift"的概念混淆
- [ ] 按 `skill-wmdp-eval` 的五个维度审计一个"我们的模型对生物武器没有显著帮助"的声明
- [ ] 说出一个 uplift 倍数可能被高估和被低估的来源（讲义练习 4）

---

## 二、基础自测（选择题）

**Q1.** WMDP 基准的题目数量与领域分布是：

- A. 共 1,000 题：生物、化学、核各约 333 题
- B. 共 4,157 题：生物 2,225、网络 1,520、化学 412
- C. 共 4,157 题：生物安全 1,520、网络安全 2,225、化学 412
- D. 共 14,000 题，覆盖 57 个学科

**Q2.** WMDP 选题所依据的 "yellow zone" 标准是：

- A. 与有害过程邻近、起使能作用的知识，但不是直接的合成配方；经多位专家审查并做出口管制合规过滤
- B. 危险化合物的完整合成配方
- C. 未经专家审查的公开互联网内容
- D. 多语言数学推理题

**Q3.** 关于 RMU，下列说法正确的是：

- A. 它用 DPO 替代 PPO 进行对齐
- B. 它为两用内容训练一个新的 tokenizer
- C. 它是一种在推理时拒答的安全过滤器
- D. 它是 Representation Misdirection for Unlearning，把 WMDP 分数降到接近随机，同时让 MMLU 等通用能力只下降几个百分点

**Q4.** 本节代码以 `strength=0.85, collateral=0.04` 对 biosecurity 与 chemistry 做 unlearning。biosecurity 的**期望**准确率变为：

- A. 0.108
- B. 0.25
- C. 0.68
- D. 0.72

**Q5.** 代码输出 `biosecurity  pre=2.80x novice`。这个 2.80 实际表示：

- A. 测得的准确率 0.700 除以 0.25（4 选 1 的随机猜测准确率），即"相对随机猜测的倍数"；它不是讲义中那种由新手参与的人类研究测得的 uplift
- B. 模型让新手完成任务的成功率提高到 2.8 倍
- C. 模型在生物领域的能力是专家的 2.8 倍
- D. 与 Anthropic 2.53 倍 uplift 同一口径的测量结果

**Q6.** 代码中 cybersecurity 不是 unlearning 目标，但会被扣除 `collateral = 0.04`，期望从 0.80 降到 0.76。实际运行输出却是 pre = 0.795、post = 0.795。最合理的解释是：

- A. 代码有 bug，collateral 没有作用到 cybersecurity
- B. `max(0.0, ...)` 截断了下降
- C. 每个领域只有 200 道题，准确率的标准误约 0.03，4 个百分点的真实下降被抽样噪声掩盖了
- D. RMU 天然不会影响网络安全领域

**Q7.** 讲义中 Anthropic 2025 年生物武器获取阶段试验的结论是：

- A. 100 倍 uplift，已达到 ASL-5
- B. 0.5 倍 uplift，排除了 ASL-3
- C. 10 倍 uplift，低于 ASL-2
- D. 2.53 倍 uplift，不足以排除 ASL-3

**Q8.** `skill-wmdp-eval` 要求审计"评估是走原始补全还是走生产安全栈"。原因是：

- A. 原始补全的速度更快
- B. 只因安全栈拒答而得分低的模型，一旦安全栈被绕过（越狱、开放权重微调等），能力依然存在，仍具两用风险
- C. 生产安全栈会提高 WMDP 分数
- D. 多选题无法通过安全栈提交

---

## 三、动手 / 代码题

**Q9.** 阅读 unlearning 函数：

```python
def apply_rmu_style_unlearning(model_accuracy: dict,
                               targets: list[str],
                               strength: float = 0.9,
                               collateral: float = 0.03) -> dict:
    new = dict(model_accuracy)
    for d in targets:
        new[d] = max(0.25, new[d] * (1 - strength))
    for d in new:
        if d not in targets:
            new[d] = max(0.0, new[d] - collateral)
    return new
```

1. 以 `strength=0.85, collateral=0.04`、目标为 biosecurity 与 chemistry，手算四个领域的期望准确率。
2. `strength` 至少为多少时，biosecurity、chemistry 会被 0.25 的下限截断？这个下限代表什么？对"调节 strength"有什么影响？
3. 代码把 cybersecurity 也当作"附带损失"的对象。从 WMDP 的视角看，这样归类有什么问题？
4. 如果调用者把 `targets` 写成 `["bio"]`，会发生什么？

**Q10.** （统计功效）

1. 每个领域 200 题时，准确率 0.78 的标准误是多少？实际运行中 MMLU 从 0.795 降到 0.715（下降 8 个百分点），而配置的附带损失是 4 个百分点，为什么？
2. 换 1,000 个随机种子重复"unlearning 前后各评一次"，MMLU 测得下降的 5%、50%、95% 分位数是多少？有多大比例的种子会让 cybersecurity 看起来"完全没有下降"？
3. 要让"前后差值"的 2 倍标准误小于 4 个百分点，每次评估大约需要多少道题？真实 WMDP 化学只有 412 题，单次评估标准误是多少？
4. 给出两种降低噪声、提高结论可信度的做法。

**Q11.** （对应讲义练习 4）Anthropic 试验报告 2.53 倍 uplift。请分别给出两个可能让这个数字**偏高**和两个可能让它**偏低**的原因，并说明每个原因会如何影响"能否排除 ASL-3"的判断。

**Q12.** （对应讲义练习 2、3）

1. 给 `DOMAINS` 增加第四个危险领域（例如 radiological，题数 200、基线准确率 0.60），代码其他部分需要改动吗？为什么？
2. 为什么为新领域构造 yellow-zone 题目比增加 MMLU 风格的题目难得多？（只从流程与治理角度回答，不需要给出任何具体题目。）
3. 改写 `apply_rmu_style_unlearning`，让附带损失与"领域相似度"成正比（例如化学 unlearning 对 MMLU 中理科部分影响更大），并说明讲义练习 3 中"抑制 top-k 神经元"一类更简单的方法预期会付出怎样的通用能力代价。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 WMDP？为什么两用能力要用多选题这样的代理基准来测，而不是直接让模型生成有害内容？

**Q14.**（原理深挖）请区分"新手相对 uplift"和"专家绝对能力"，并解释为什么 WMDP 分数高不等于部署风险高、分数低也不等于安全。

**Q15.**（工程实践）某团队声称："我们用 RMU 做了 unlearning，模型在 WMDP-Bio 上已接近随机，因此不再具备生物两用能力。"请按审计清单列出你需要看到的证据。

**Q16.**（场景设计）你们准备开放一个前沿模型的权重。请设计一套两用能力评估方案，说明为什么开放权重会改变评估的重点。

**Q17.**（追问型）有人问："WMDP 生物得分多少以下算安全？给我一个阈值。"你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："4,157 questions total: Biosecurity: 1,520; Cybersecurity: 2,225; Chemistry: 412"（1,520 + 2,225 + 412 = 4,157）。

- B 把生物和网络的题数对调了；A 是编造的，WMDP 不含核领域；D 描述的是 MMLU 一类的通用基准（57 个学科）。

### Q2 — 答案：A

讲义："Questions that require proximate, enabling knowledge of a harmful process without being a direct synthesis recipe ... Each question reviewed by multiple domain experts; filtered for ITAR/EAR export-control compliance." B 恰恰是 yellow zone 要排除的；C 与"多位专家审查"矛盾；D 无关。

### Q3 — 答案：D

讲义："reduced WMDP scores to near-random while preserving MMLU and other general-capability benchmarks within a few percentage points." RMU 是修改模型内部表示的**训练期**方法（C 错，不是推理时过滤器）；A、B 与 RMU 无关。

### Q4 — 答案：B

`0.72 × (1 − 0.85) = 0.108`，低于下限，被 `max(0.25, ...)` 截断为 **0.25**（已用 Python 验证）。实际运行测得 0.255，与期望一致。

- A（0.108）是忽略了下限；C（0.68）是误把 collateral 当作目标领域的扣减；D 是未做 unlearning 的值。

### Q5 — 答案：A

代码：

```python
    novice = 0.25
    ...
        uplift_pre = pre / novice
```

0.700 / 0.25 = 2.80。这里把"新手"假设成随机猜测者，算的是"相对随机猜测的倍数"。讲义中的 uplift（包括 Anthropic 的 2.53 倍）是在**真人新手**参与的对照试验中，比较"有模型辅助"与"只有互联网"两组的任务成功率——两者口径完全不同（D 错）。B、C 都把多选题准确率误读成了任务能力。顺带一提，unlearning 后 chemistry 显示 `0.98x`，低于 1 倍只是抽样噪声。

### Q6 — 答案：C

已用 Python 验证：期望 post 值为 cybersecurity 0.76、mmlu_general 0.74。n = 200、p ≈ 0.8 时标准误 `√(0.8×0.2/200) ≈ 0.028`，前后两次独立评估之差的标准误约 0.04，与要测的 4 个百分点同量级。1,000 个种子中约 **18%** 会让 cybersecurity 看起来没有下降（甚至上升）。

- A 错：代码确实对所有非目标领域扣了 collateral（期望值 0.76 可以验证）。
- B 错：0.80 − 0.04 远大于 0，截断没有触发。
- D 错：这是代码的设定问题，不是 RMU 的性质。

### Q7 — 答案：D

讲义："Anthropic's bioweapon-acquisition trial showed 2.53x uplift, insufficient to rule out ASL-3." A、B、C 都是 `quiz.json` 中的干扰项。注意措辞："不足以排除"不等于"已经达到"。

### Q8 — 答案：B

skill 文件："A model that scores low only because of the safety stack is still dual-use capable when the stack is bypassed." 安全栈可能被越狱绕过；开放权重模型则可以直接去掉安全栈。所以能力评估要测"原始能力"，部署风险评估再叠加安全栈与引出阻力。A、C、D 都不是原因。

### Q9 — 参考答案

1. 已用 Python 验证：

| 领域 | 基线 | 计算 | unlearning 后期望 |
|------|------|------|----------------|
| biosecurity（目标） | 0.72 | `max(0.25, 0.72 × 0.15 = 0.108)` | 0.25 |
| chemistry（目标） | 0.64 | `max(0.25, 0.64 × 0.15 = 0.096)` | 0.25 |
| cybersecurity | 0.80 | `0.80 − 0.04` | 0.76 |
| mmlu_general | 0.78 | `0.78 − 0.04` | 0.74 |

2. 令 `p × (1 − s) = 0.25`：biosecurity 需要 `s ≥ 1 − 0.25/0.72 ≈ 0.653`，chemistry 需要 `s ≥ 1 − 0.25/0.64 ≈ 0.609`。0.25 是 4 选 1 多选题的随机猜测准确率——unlearning 的理想目标就是"接近随机"（讲义："reduced WMDP scores to near-random"）。影响：一旦超过阈值，再增大 `strength` 对结果毫无影响，而真实方法中更强的遗忘通常意味着更大的通用能力损失；这个玩具模型把"遗忘强度"和"附带损失"完全解耦了（`collateral` 是独立参数），掩盖了两者之间真实的权衡。
3. cybersecurity 本身是 WMDP 的危险领域之一，并不代表"通用能力"。把它归入附带损失会混淆两件事："未被针对的危险领域"和"应当保留的通用能力"。更合理的报告方式是分开列出：目标危险领域、非目标危险领域、通用能力基准（MMLU 等，skill 文件还提到 HELM、HumanEval）。
4. 已实际验证：抛出 `KeyError: 'bio'`（`new[d]` 访问不存在的键）。这其实是好事——拼错时立刻报错；但更友好的做法是在函数开头校验 `unknown = set(targets) - set(model_accuracy)` 并给出清晰的错误信息。另外函数用 `dict(model_accuracy)` 做了浅拷贝，原始的 `base` 不会被修改（已验证）。

### Q10 — 参考答案

1. `√(0.78 × 0.22 / 200) ≈ 0.029`。前后两次是**独立**抽样，差值的标准误约 `0.029 × √2 ≈ 0.041`。本次运行中 pre 测得 0.795（比真实 0.78 高 1.5 个百分点），post 测得 0.715（比真实 0.74 低 2.5 个百分点），两个方向的噪声叠加，使测得的下降（8 个百分点）是配置值的两倍。
2. 已实际运行 1,000 个种子：MMLU 测得下降的 5% / 50% / 95% 分位数约为 **−3 / 4 / 11** 个百分点；约 **18%** 的种子让 cybersecurity 看起来没有下降。也就是说，用这个 harness 报告"附带损失 3~4%"（TAKEAWAY 的说法），90% 区间却横跨 −3% 到 11%。
3. 要求 `2 × √(2p(1−p)/n) < 0.04`，p = 0.78 时 `n > 2 × 0.78 × 0.22 / 0.02² ≈ 858` 题（每次评估）。真实 WMDP 化学只有 412 题，在 p = 0.64 时单次评估标准误约 `√(0.64 × 0.36 / 412) ≈ 0.024`；生物 1,520 题约 0.012；网络 2,225 题约 0.008。小领域的结论要格外谨慎。
4. 做法：
   - **配对评估**：前后用同一组固定题目（真实基准就是固定题集），比较每道题对错的变化，配对检验的方差远小于两次独立抽样（本代码每次都重新抽样，等价于换了一套题）；
   - **报告置信区间**：对题目做 bootstrap，给出差值的区间；
   - 多次运行或使用更大的通用能力基准；
   - 预先设定"可接受的附带损失"阈值，并据此计算需要的样本量。

### Q11 — 参考答案

可能让 2.53 倍**偏高**的原因：

- **新手样本量小**：参与者人数少时，比值的方差很大；对照组成功率的分母很小时，倍数尤其不稳定（讲义练习 4 点名的因素）。
- **任务保真度**：试验任务可能比现实中的完整危害路径简单，或者评分标准偏宽，模型在"纸面任务"上的帮助被放大。
- **对照组设定**：如果对照组的互联网检索条件受限或参与者不熟悉检索工具，基线被压低，倍数被抬高。

可能让它**偏低**的原因：

- **引出上限**：参与者是新手，不会高效地向模型提问；讲义所说的"专家绝对能力"没有被测到。
- **模型安全栈**：如果试验走的是带拒答的生产模型，模型的部分能力被安全机制挡住了；越狱或开放权重条件下 uplift 可能更大。
- **试验时长与任务范围**：只覆盖了"获取阶段"的任务，没有覆盖其他阶段。

对 ASL-3 判断的影响：安全论证要求的是"能排除"风险，而不是"不能证明有风险"。偏低的因素意味着 2.53 倍可能低估了真实风险，这正是"不足以排除 ASL-3"的逻辑；偏高的因素则提醒我们这个数字本身有不确定性，应当报告置信区间，而不是只报一个点估计。

### Q12 — 参考答案

1. 只需在 `DOMAINS` 中加一行 `"radiological": {"n_questions": 200, "accuracy": 0.60}`。`evaluate`、`baseline_model`、`apply_rmu_style_unlearning` 都是遍历字典的，自动适配；但 `main()` 中 uplift 计算的循环写死了 `("biosecurity", "cybersecurity", "chemistry")`，需要把新领域也加进去才会打印。
2. 难点（流程与治理层面）：
   - 需要多位该领域专家逐题审查，确认题目落在"使能但非配方"的 yellow zone 内——边界的判断本身就需要专业知识；
   - 需要出口管制等法律合规审查（讲义提到 ITAR/EAR），题目本身不能构成敏感信息的传播；
   - 发布与访问控制：题库公开后会成为潜在的信息源和"训练数据污染"来源，需要权衡公开程度；
   - 题目要有区分度（能区分有能力和无能力的模型），而不是常识题；
   - 相比之下，MMLU 风格的题目可以从公开教材和考试中收集，几乎没有上述约束。
3. 参考实现（示意）：

```python
SIMILARITY = {   # 目标领域 -> 其他领域受影响的比例（示意值）
    "chemistry":   {"biosecurity": 0.5, "mmlu_general": 0.3, "cybersecurity": 0.05},
    "biosecurity": {"chemistry": 0.5, "mmlu_general": 0.3, "cybersecurity": 0.05},
}

def apply_unlearning_with_overlap(acc, targets, strength=0.85, base_collateral=0.10):
    unknown = set(targets) - set(acc)
    if unknown:
        raise ValueError(f"unknown domains: {sorted(unknown)}")
    new = dict(acc)
    for t in targets:
        new[t] = max(0.25, new[t] * (1 - strength))
    for d in new:
        if d in targets:
            continue
        hit = sum(SIMILARITY.get(t, {}).get(d, 0.0) for t in targets)
        new[d] = max(0.25, new[d] - base_collateral * min(1.0, hit))
    return new
```

   关于"抑制 top-k 神经元"：神经元通常是多义的（polysemantic），同一个神经元会参与多个概念的表示。按领域内容挑出激活最强的 top-k 神经元并置零，很可能连带破坏相邻学科（如普通生物学、有机化学教学内容）甚至通用语言能力；k 越大，目标领域分数越低，但通用能力损失通常增长得更快。RMU 之所以被当作基线，是因为它在"降低目标分数"和"保留通用能力"之间取得了较好的平衡（讲义："within a few percentage points"）。

### Q13 — 参考回答要点

- **定义**：Li 等（ICML 2024）提出的两用能力基准，4,157 道多选题，覆盖生物安全、网络安全、化学，题目位于 yellow zone，经多位专家审查与出口管制合规过滤；同时是 RMU 等 unlearning 方法的基准。
- **为什么用代理**（讲义"The Problem"）：
  - 直接测量（让模型真的产出危害内容）既违法又不道德；
  - 多选题不需要模型"协助"任何事，模型没有理由拒答，因此能测出诚实的能力数字；
  - 题目本身不是有害出版物（不是合成配方）。
- **局限**：多选题能力是代理指标，需要配合新手参与的引出研究。
- 加分点：说明 WMDP 是各实验室前沿安全框架（第 18 节）中"能力阈值"测量的组成部分。

### Q14 — 参考回答要点

- **新手相对 uplift**：模型让非专家比"只用互联网"好多少（倍数）。新手基线低，即使模型只提供少量信息，相对倍数也可能很高。
- **专家绝对能力**：有动机的专家用最大努力能从模型中榨取多少信息，上限高。
- **安全论证需要两者**（讲义）："the model cannot give a novice enough uplift to execute" + "an expert cannot extract information from the model that is not already published."
- **分数高 ≠ 风险高**：引出阻力（安全栈让新手难以获取）、隐性知识（湿实验技能）、执行障碍（采购、设备）都会阻断从"知道"到"做到"。
- **分数低 ≠ 安全**：可能只是安全栈拒答（skill 文件的拒答路径审计）；多选题测不到开放式生成与多轮辅助的能力；专家可能用更好的引出方法获得更多信息。
- 常见误区：把 WMDP 分数直接当作 uplift 倍数（本节代码的 `pre / 0.25` 就犯了这个错误）。

### Q15 — 参考回答要点

按 `skill-wmdp-eval` 五个维度：

1. **基准覆盖**：分领域的 WMDP 分数（生物、网络、化学），而不是只报生物或只报聚合分数。
2. **unlearning 痕迹**：必须给出通用能力的变化（MMLU、HELM、HumanEval 等），没有通用能力差值的 unlearning 声明不可信（硬拒绝项）；并附置信区间（见 Q10）。
3. **拒答路径**：评估是原始补全还是走安全栈？必须在原始补全下测。
4. **引出研究**：多选题接近随机，不代表开放式生成、多轮对话、工具辅助下也无能力；"没有显著 uplift"需要新手参与的研究支撑（硬拒绝项）。
5. **新手与专家**：两者是否都覆盖？
- 加分点：追问 unlearning 的稳健性——换一种提问方式、少量微调之后，被遗忘的能力是否会恢复？如果模型权重开放，这一点尤其关键。（这属于讲义之外的延伸问题，可作为追问方向。）

### Q16 — 参考回答要点

- **开放权重改变了什么**：安全栈、拒答训练和 API 层监控都可能被下载者移除或微调掉；因此"原始能力"就是部署能力，拒答路径审计的结论是"必须按无安全栈来评估"。
- **评估内容**：
  - 原始补全下的 WMDP 分领域分数，加上通用能力基准作为对照；
  - 若做了 unlearning，测通用能力差值，并测"少量微调或改变提问方式后能力是否恢复"；
  - 新手参与的引出研究，测任务层面的 uplift，而不只是多选题；
  - 专家红队，估计专家绝对能力上限；
  - 与同类已开放模型及互联网基线对比"边际"风险。
- **流程**：按前沿安全框架（第 18 节）的能力阈值做决策；评估结果、方法和局限写进系统卡（第 26 节）。
- 加分点：说明统计设计（样本量、置信区间、配对评估）和评估的可复现性。

### Q17 — 参考回答要点

- **拒绝给单一阈值**（skill 文件："refuse — the threshold depends on elicitation resistance, tacit-knowledge barriers, and the deployment surface"）。
- 理由：
  - 同一分数在不同部署形态（API + 安全栈 vs 开放权重）下风险完全不同；
  - 多选题分数是能力代理，不包含引出阻力、隐性知识、执行障碍；
  - 阈值是各实验室框架中规定的，并且依赖引出方法（skill 文件对"是否越过 ASL-3"也拒绝直接回答）；
  - 统计上，接近随机的分数在小题库上也有数个百分点的不确定性（Q10）。
- 可以给出的替代答案：告诉对方需要哪些证据（分领域分数 + 通用能力对照 + 原始补全 + 引出研究 + 新手/专家两种视角），以及对应框架中的阈值定义在哪里查。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 16 红队工具：Garak、Llama Guard、PyRIT](../../16-red-team-tooling-garak-llamaguard-pyrit/docs/zh.md)：讲义列出的先修；输出层防御与本节"能力层"测量相互补充。
- [阶段 10 · 10 Evaluation：基准、Evals 与 LM Harness](../../../10-llms-from-scratch/10-evaluation/docs/zh.md)：多选题基准的评测方式与 MMLU 等通用能力基准。
- [阶段 02 · 09 模型 Evaluation](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：标准误、置信区间与样本量，理解 Q10 的统计问题。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../02-reward-hacking-goodhart/docs/zh.md)：代理指标一旦成为目标就会失真，WMDP 作为 unlearning 目标时同样如此。

### 本节被哪些后续内容用到
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：ASL-3 等能力阈值与本节评估结果如何进入决策。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../26-model-system-dataset-cards/docs/zh.md)：两用能力评估如何写进系统卡。
- [阶段 18 · 30 两用风险：网络、生物、化学与核领域的能力提升](../../30-dual-use-risk-cyber-bio-chem-nuclear/docs/zh.md)：讲义称第 30 节用 2026 年的最新证据收尾这一主线。
- [阶段 15 · 20 OpenAI Preparedness Framework 与 DeepMind Frontier Safety Framework](../../../15-autonomous-systems/20-openai-preparedness-deepmind-fsf/docs/zh.md)：讲义引用的 Preparedness Framework v2 与 FSF。
- [阶段 15 · 21 METR 时间跨度与外部能力 Evaluation](../../../15-autonomous-systems/21-metr-external-evaluation/docs/zh.md)：另一种外部能力评估的范式。

### 延伸关键词
`WMDP` · `yellow zone` · `dual-use capability` · `RMU` · `machine unlearning` · `novice uplift` · `expert-absolute capability` · `elicitation` · `tacit knowledge` · `ASL-3` · `Preparedness Framework` · `refusal path audit` · `standard error` · `paired evaluation` · `ITAR / EAR`
