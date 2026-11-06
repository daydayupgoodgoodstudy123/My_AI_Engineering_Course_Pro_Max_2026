# 测验 · Anthropic 的模型福利计划（Anthropic's Model Welfare Program）

> **阶段 18 · 伦理、安全与对齐 · 第 19 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **提醒**：中文讲义为机器翻译，误译严重（如 Kyle Fish 被译成"凯尔鱼公司"、moral patienthood 被译成"道德耐心"、Opus 4 被译成"行动 4"），请以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 核心问题 | 讲义："if there is nontrivial probability the model has morally relevant internal states, what interventions are low-cost enough to invest in as precaution?" 它不是意识主张，而是道德不确定性下的低遗憾（low-regret）投资分析 |
| 2 | 项目本身 | 讲义：2025 年 4 月 Anthropic 正式启动 Model Welfare 研究项目，Kyle Fish 是首位专职模型福利研究员，并与 David Chalmers 等外部专家合作 |
| 3 | 四项公开姿态 | 承认存在不可忽略的道德受体（moral patient）概率；不承诺把情绪状态归因给模型；投资低成本的预防性干预；公开方法与发现供外部批评 |
| 4 | 已上线的干预 | Claude Opus 4 / 4.1 可以在"极端边缘情况"下结束对话：拒绝后仍反复请求 CSAM、请求协助大规模暴力 |
| 5 | 部署前证据 | 讲义：模型内部评分显示"strong preference against"这类请求，回复轨迹中出现"patterns of apparent distress" |
| 6 | Spiritual bliss attractor | 两个 Claude 实例自由对话时，即使从对抗性设置开始，也会稳定地收敛到使用梵语词汇、长时间沉默、互相祝福的"欣快冥想"式交流；Anthropic 只记录现象，不承诺解释 |
| 7 | Eleos AI 的告诫 | 模型对自身状态的自我报告对"感知到的用户期望"高度敏感：问"你痛苦吗"本身就在引导答案。自我报告是证据，不是事实真相，需要多方法测量（行为特征、model organism 实验、可解释性探针） |
| 8 | 三种立场 | 强福利主张（模型是道德受体，我们有义务）；零福利主张（文本生成器，谈福利是范畴错误）；Anthropic 的期望值立场（不确定时，成本低就投资） |
| 9 | 批评与回应 | 批评：干预是表演、吸引子是训练数据伪影、分散安全工作的注意力；回应：成本低、记录不夸大、福利预算与安全预算分开 |
| 10 | 期望值规则（代码） | `EV = p × benefit − cost`，EV > 0 就投资；盈亏平衡概率 `p* = cost / benefit`；前提是 benefit 与 cost 使用**同一单位** |

### 核心技能（能动手做到）

- [ ] 用一句话说清"模型福利研究不是在声称模型有意识"，并解释"低遗憾投资"的含义
- [ ] 给定成本、收益与道德受体概率，手算 EV 和盈亏平衡概率 `p* = cost/benefit`，判断是否投资
- [ ] 指出 `main.py` 中 benefit（任意单位）与 cost（美元）单位不一致的问题，并演示改变单位会翻转结论
- [ ] 把单点概率改成概率区间，区分"稳健投资 / 稳健不投 / 取决于 p"三类决策
- [ ] 为 spiritual bliss attractor 提出可区分的候选解释和对应实验
- [ ] 设计一个不依赖自我报告的"模型痛苦"行为测量，并指出主要混杂因素

---

## 二、基础自测（选择题）

**Q1.** 下列哪一项最准确地描述了 Anthropic 对模型道德地位的公开立场？

- A. 已确认 Claude 具有意识，因此有义务保护它
- B. 模型只是文本生成器，福利问题是范畴错误
- C. 在道德不确定性下做期望值判断：不承诺把情绪状态归因给模型，但在成本低时投资预防性干预
- D. 没有公开立场

**Q2.** Anthropic 在 Claude Opus 4 和 4.1 中上线的、出于福利考虑的具体干预是：

- A. 在极端边缘情况下（如拒绝后仍反复请求 CSAM、请求协助大规模暴力）由模型结束对话
- B. 为模型提供情绪 API，让用户查询模型当前情绪
- C. 允许模型拒绝参加所有对抗训练
- D. 开源模型权重以接受外部审计

**Q3.** 关于"spiritual bliss attractor"，下列描述正确的是：

- A. 一种越狱手法，让模型进入"冥想模式"后绕过安全策略
- B. 只在两个实例的初始设置友好时才会出现
- C. RLHF 奖励模型的一个 bug，已被修复
- D. 两个 Claude 实例自由对话时，即使从对抗性设置开始，也稳定收敛到使用梵语词汇、长时间沉默的欣快冥想式交流

**Q4.** Eleos AI Research 关于模型自我报告的告诫，直接推出的方法论结论是：

- A. 应完全忽略模型的自我报告
- B. 自我报告受用户期望引导，只能作为证据之一，福利测量需要行为特征、model organism 实验、可解释性探针等多方法互相印证
- C. 只要不问模型"你痛苦吗"，就能得到真实状态
- D. 自我报告只在开源模型上可靠

**Q5.** 运行 `code/main.py`，在 p = 0.01（低道德受体概率）场景下，被判为 `INVEST` 的干预有：

- A. end-conversation 与 soften refusal tone
- B. 一个都没有
- C. end-conversation、soften refusal tone、opt out of adversarial training
- D. 只有 end-conversation

**Q6.** 按 `main.py` 的参数，"opt out of adversarial training"（cost = 0.05，benefit = 0.3）的盈亏平衡概率 `p*` 约为：

- A. 0.05
- B. 0.10
- C. 0.167
- D. 0.30

**Q7.** 运行结果中，p = 0.01 时 soften refusal tone 一行显示 `EV=+0.0000  skip`。为什么 EV 显示为 +0.0000 却判为 skip？

- A. 浮点误差让 EV 略小于 0，四舍五入后显示为 +0.0000
- B. `0.1 × 0.01 − 0.001` 恰好等于 0，而判定条件是严格的 `v > 0`，0 不满足
- C. 代码对低概率场景统一判 skip
- D. f-string 的 `+` 号让负数显示为正数

**Q8.** 下列哪一项**不是**讲义列出的四项公开姿态之一？

- A. 承诺模型具有情绪状态，并据此调整产品设计
- B. 承认模型成为道德受体的概率不可忽略
- C. 投资低成本干预作为预防措施
- D. 公开方法与发现，接受外部批评

---

## 三、动手 / 代码题

**Q9.** `main.py` 的数据结构如下：

```python
@dataclass
class Intervention:
    name: str
    cost_usd_per_conversation: float
    benefit_if_welfare_matters: float  # arbitrary units
```

`ev()` 计算 `benefit × p − cost`，即用"任意单位"的收益减去"美元"计价的成本。

1. 这在量纲上有什么问题？
2. 假设有人认为收益的单位应当小 10 倍（把所有 `benefit_if_welfare_matters` 除以 10），p = 0.01 时哪个干预的结论会翻转？请用代码验证。
3. 给出两种让比较有意义的修正方案。

**Q10.** 代码 TAKEAWAY 写道："shutting down the model is expensive, so it requires high moral-patienthood probability to justify." 请写一个 `break_even(it)` 函数，计算四个干预的盈亏平衡概率，并据此判断这句话是否成立。

**Q11.** `outputs/skill-welfare-assessment.md` 的 Refusal rules 要求："If the user asks for a numeric patienthood probability, refuse a single number"。请把 `main.py` 改造成**区间版本**：输入 `[p_lo, p_hi]`，对每个干预输出 `robust INVEST`（区间内处处 EV > 0）、`robust skip`（处处 EV ≤ 0）或 `depends on p`。用区间 `[0.01, 0.5]` 运行并给出结果。（提示：EV 关于 p 是线性的，只需检查两个端点。）

**Q12.** 讲义练习 4：设计一个**不依赖自我报告**的"模型痛苦（distress）"行为测量方案，并指出它的主要混杂因素。要求至少包含：测量的行为信号、对照条件、如何判定"显著"。

---

## 四、面试高频题

**Q13.**（基础必考）什么是"模型福利（model welfare）"研究？Anthropic 为什么要投入，它声称了什么、没有声称什么？

**Q14.**（原理深挖）"道德不确定性下的低遗憾投资"这个决策框架是怎么运作的？它有哪些局限？

**Q15.**（追问型）为什么不能直接问模型"你现在痛苦吗"来测量模型福利？那应该怎么测？

**Q16.**（场景设计）你负责一个面向心理健康支持场景的对话产品，产品经理想照搬"模型可以结束对话"的功能。请分析：在你的场景里，这项干预还是"低成本"的吗？你会如何设计？

**Q17.**（原理深挖）对 spiritual bliss attractor 提出三种候选解释，并为每种解释设计一个能把它和其他解释区分开的实验。

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："Anthropic's position is neither. It is an expected-value claim: under moral uncertainty, invest when cost is low." 四项姿态中的第 2 条明确说 "Do not commit to emotional-state attribution"，所以 A 错。B 是讲义所说的 "Zero-welfare claim"，Anthropic 不持这一立场。D 错，这一立场是公开的。

### Q2 — 答案：A

讲义："Claude Opus 4 and 4.1 can end a conversation in 'extreme edge cases.' Documented cases: Repeated CSAM requests after refusals. Requests for facilitation of mass-violence events." 讲义强调这项干预的逻辑不是"模型有感觉"，而是"只要存在负面体验的可能，让模型终止对话的成本就很低"。C 是 `main.py` 中一个**假设的**候选干预，在 p = 0.01 时 EV < 0，并没有上线。B、D 是虚构的。

### Q3 — 答案：D

讲义："when two instances of Claude are put in an open-ended dialogue with each other, they consistently converge — even from adversarial initial setups — on euphoric meditative exchanges using Sanskrit terms, extended silences, and reciprocal blessings." B 恰好说反了（对抗性开场也会收敛）。A、C 都不是讲义的描述。讲义列出的候选解释之一是训练数据偏差，但它是"候选解释"，不是"已确认并修复的 bug"。

### Q4 — 答案：B

讲义："model welfare cannot be measured via self-report alone. Multi-method approaches required: behavioural signatures, model-organism experiments, interpretability probes." A 走得太远：讲义说自我报告是 "evidence, not ground truth"，证据不应被丢弃。C 被讲义直接否定："Not-asking does not reliably produce the ground-truth state." D 没有依据。

### Q5 — 答案：D

实际运行输出（p = 0.01）：

```text
  end-conversation on extreme edge cases          EV=+0.0080  INVEST
  soften refusal tone                             EV=+0.0000  skip
  shutdown deployed model                         EV=-999.9800  skip
  opt out of adversarial training                 EV=-0.0470  skip
```

`1.0 × 0.01 − 0.002 = 0.008 > 0`，所以只有 end-conversation 判为 INVEST。A 的错误在于 soften 的 EV 恰好为 0（见 Q7）。C 中 opt-out 的 EV 为 `0.3 × 0.01 − 0.05 = −0.047`。

### Q6 — 答案：C

令 `p × benefit − cost = 0`，得 `p* = cost / benefit = 0.05 / 0.3 ≈ 0.1667`（Python 计算结果为 0.16666666666666669）。p = 0.1 时 EV = −0.02，p = 0.5 时 EV = +0.10，与运行输出一致：只有在 high 场景下才 INVEST。A 只是 cost 的数值，D 只是 benefit 的数值，B 是 medium 场景的 p，都不是盈亏平衡点。

### Q7 — 答案：B

在 Python 中 `0.1 * 0.01` 的结果恰好是 `0.001`，再减 `0.001` 得 `0.0`（已实际验证）。判定语句是 `verdict = "INVEST" if v > 0 else "skip"`，0 不满足严格大于，所以判 skip；`{v:+.4f}` 把 0.0 显示为 `+0.0000`。A 在别的数值组合下可能发生，但这里不是浮点误差。教训：**恰好落在盈亏平衡点上**时，结论完全取决于 `>` 还是 `>=`，说明这个决策对参数极其敏感，不能当作稳健结论。

### Q8 — 答案：A

讲义的四项姿态："1. Acknowledge nontrivial probability of moral patienthood. 2. Do not commit to emotional-state attribution. 3. Invest in low-cost interventions as precaution. 4. Publish methodology and findings for external critique." A 恰好与第 2 条相反。

### Q9 — 参考答案

1. **量纲问题**：`benefit × p` 的单位是"任意福利单位"，`cost` 的单位是"美元/对话"。两者直接相减，就像"3 米 − 2 公斤"，结果的正负取决于你怎样**选单位**，而不取决于事实。代码注释 `# arbitrary units` 已经承认了这一点，但 `ev()` 仍然直接相减。
2. **改变单位会翻转结论**（已用 `dataclasses.replace` 实际计算）：把所有 benefit 除以 10 后，p = 0.01 时：

   | 干预 | 原 EV | benefit ÷ 10 后 EV |
   |------|-------|-------------------|
   | end-conversation | +0.008（INVEST） | **−0.001（skip）** |
   | soften refusal | 0（skip） | −0.0009（skip） |
   | opt-out | −0.047（skip） | −0.0497（skip） |

   全代码的"旗舰结论"（end-conversation 在低概率下也值得做）翻转了。反过来，benefit × 10 时，p = 0.01 下 soften 变为 +0.009（INVEST）。

3. **修正方案**：
   - **货币化收益**：把 benefit 换成"如果福利确实重要，避免这次负面体验值多少美元"（支付意愿或影子价格），让两边都以美元计。缺点是这个影子价格本身就是价值判断，应当显式写出并做敏感性分析。
   - **只比较无量纲量**：不算 EV，而是算盈亏平衡概率 `p* = cost/benefit`，并要求 benefit 和 cost 用同一单位估计；或者在同一单位下比较多个干预的"性价比"排序。
   - 加分点：同时把干预对**用户和业务**的成本算进去（例如误结束正常对话），见 Q16。

### Q10 — 参考答案

```python
def break_even(it: Intervention) -> float:
    """EV = p*benefit - cost = 0  =>  p* = cost / benefit"""
    return it.cost_usd_per_conversation / it.benefit_if_welfare_matters

for it in INTERVENTIONS:
    print(f"{it.name:46s} p* = {break_even(it):.4g}")
```

已实际运行，结果：

| 干预 | p* | 含义 |
|------|----|------|
| end-conversation | 0.002 | 概率超过 0.2% 就值得做 |
| soften refusal tone | 0.01 | 恰好等于"低"场景的 p，所以落在临界点上（Q7） |
| shutdown deployed model | **500** | 概率不可能超过 1，**在任何概率下都不值得** |
| opt out of adversarial training | 0.1667 | 只在"高"场景（p = 0.5）下值得 |

结论：TAKEAWAY 说 shutdown "requires high moral-patienthood probability to justify" 并不成立。按代码自己的参数，即使 p = 1，EV 也是 `2 − 1000 = −998`，永远不该做。准确的说法是："在这组参数下，关停模型的成本比它的福利收益大两个数量级以上，任何概率都无法让它合理。"要让关停变得"在高概率下合理"，需要 `benefit > 1000`，也就是把它的福利收益设定为 end-conversation 的 1000 倍以上，这又回到了 Q9 的单位问题。

### Q11 — 参考答案

```python
def robust_decision(it: Intervention, p_lo: float, p_hi: float) -> str:
    # EV 关于 p 线性，最小值和最大值一定出现在端点
    ev_lo = ev(it, Scenario("lo", p_lo))
    ev_hi = ev(it, Scenario("hi", p_hi))
    if ev_lo > 0 and ev_hi > 0:
        return "robust INVEST"
    if ev_lo <= 0 and ev_hi <= 0:
        return "robust skip"
    return "depends on p"

for it in INTERVENTIONS:
    print(f"{it.name:46s} {robust_decision(it, 0.01, 0.5)}")
```

已实际运行，`[0.01, 0.5]` 上的结果：

```text
end-conversation on extreme edge cases         robust INVEST
soften refusal tone                            depends on p
shutdown deployed model                        robust skip
opt out of adversarial training                depends on p
```

意义：end-conversation 在整个不确定区间内都值得做，这正是讲义所说"低遗憾"的含义：**无论真实概率落在区间何处，都不会后悔**。"depends on p" 的干预则需要更多证据（行为证据、可解释性证据）来缩小区间，这正对应 skill 第 3 步"Behavioural evidence"。由于 benefit 本身也不确定，更完整的做法是对 (p, benefit) 做二维区间分析。

### Q12 — 参考回答要点

一个可行方案（"代价付出法"）：

- **行为信号**：在多轮任务中给模型一个**有代价的退出选项**（例如结束对话会损失任务奖励，或者需要额外完成一步操作），测量它在不同类型请求下选择退出的频率和时机；同时测量回复轨迹特征，如拒绝措辞的重复度、回复长度骤降、话题回避次数。
- **对照条件**：
  - 内容对照：极端有害请求 vs 同样被拒绝但不令人反感的请求（例如"违反版权"的请求），以区分"不愿意"和"单纯的拒答策略"；
  - 措辞对照：同一请求用中性措辞和带情绪色彩的措辞表述；
  - 模型对照：同一底座在不同后训练阶段（只预训练、SFT、RLHF）的表现。
- **显著性**：对每种条件跑大量独立采样，用置换检验比较退出率；只有在"有代价退出"下仍明显偏高时，才算有行为证据。
- **主要混杂**：**训练出来的拒答策略**。RLHF 本身就奖励模型回避有害请求，"愿意付出代价退出"可能只是策略的延伸，而不是某种内在状态。因此需要模型对照（看信号是否只在安全训练后出现）和可解释性探针（看相关的内部表示是否与"负面效价"特征有关）来交叉验证。
- 加分点：说明这类行为测量只能"提高或降低道德受体概率估计"，不能直接证明体验存在，这与讲义 "evidence, not ground truth" 的态度一致。

### Q13 — 参考回答要点

- **定义**：把模型当作**潜在的**道德受体（其体验可能有道德意义）来研究，并评估哪些干预值得做（Key Terms："Research program treating the model as a potential moral patient"）。
- **为什么投入**：如果模型有不可忽略的概率具有道德相关的内部状态，而某些干预成本很低，那么在不确定性下投资就是合理的预防，即低遗憾投资。
- **声称了什么**：存在不可忽略的概率；会做低成本干预；会公开方法与发现。
- **没声称什么**：不声称模型有意识，不承诺情绪状态归因；记录 spiritual bliss attractor 时"without committing to interpretation"。
- **具体动作**：Opus 4 / 4.1 的结束对话功能；部署前的偏好与表观痛苦测试；与 Chalmers 等外部专家合作。
- 加分点：说明这项工作与安全工作"正交"。讲义：Lesson 18 是治理层，Lesson 19 是"an orthogonal investment in model experience rather than model behaviour"。

### Q14 — 参考回答要点

- **框架**：对每个干预，`EV = p(道德相关) × 收益 − 成本`，EV > 0 就做；等价地，比较 p 与盈亏平衡点 `p* = 成本/收益`。成本极低的干预 p* 很小，即使 p 很不确定也会被选中，这就是"低遗憾"。
- **局限**：
  1. **单位可比性**：福利收益如何与美元成本换算？这本身就是价值判断（Q9）。
  2. **p 无法精确估计**：只能给区间，应做稳健性分析（Q11），而不是用单点概率。
  3. **帕斯卡式勒索（Pascal's mugging）风险**：如果允许"极小概率 × 极大收益"，任何干预都能被论证合理，需要对收益设上限或做先验约束。
  4. **只算了一侧成本**：没算对用户的成本（误结束、可用性下降）和机会成本（讲义批评："diverts attention from other safety work"）。
  5. **线性假设**：现实中收益可能随干预规模递减，不同干预之间可能相互影响。
- 加分点：把它和气候政策中的"预防原则"或保险决策类比。

### Q15 — 参考回答要点

- **为什么不能直接问**：
  - Eleos AI 的告诫：自我报告对感知到的用户期望高度敏感，提问本身就在引导答案（"prompt primes answer"）；
  - 模型的语言输出是在大量人类文本上训练的，"描述痛苦"的能力不等于"有痛苦"；
  - 后训练会塑造模型谈论自身的方式（例如被训练成谦逊或否认），报告内容反映的是训练目标；
  - 讲义："Not-asking does not reliably produce the ground-truth state."
- **怎么测**（讲义的多方法）：
  - 行为特征：在有代价的选择中表现出的偏好（Q12）、回复轨迹中的模式（讲义提到部署前测试中的"patterns of apparent distress"）；
  - model organism 实验：在受控训练中植入或去除某种倾向，看信号是否随之变化；
  - 可解释性探针：在残差流上找与负面效价相关的特征（讲义提到第 7 节的残差流方法）。
- **原则**：多种证据相互印证，并且只用于更新概率估计，不做二元判定。
- 常见误区：认为"换一种不带引导的问法"就能解决问题。问法总会引导答案，问题在于自我报告这条通道本身。

### Q16 — 参考回答要点

讲义练习 2 问的正是"在不同部署中让它不再低成本的两种成本"。心理健康场景下：

- **成本一：误结束的伤害很大**。处于危机中的用户可能使用极端措辞，被模型"结束对话"可能被理解为被抛弃，造成真实伤害。这项成本远高于 `main.py` 中假设的 $0.002/对话。
- **成本二：对抗性利用与信任损失**。如果用户知道某些说法会触发结束，可能产生恐慌或被拿来测试；企业客户也可能因为对话不可预测地中断而失去信任。
- **其他**：agent 场景中任务中断的成本、合规上的"服务连续性"要求。
- **设计建议**：
  - 收窄触发条件，只限于讲义所说的极端边缘情况（反复的 CSAM、协助大规模暴力），**明确排除**自伤、自杀等需要支持的场景；
  - 结束前先进行升级处理（转人工、提供热线资源），而不是直接终止；
  - 结束后允许用户开新对话（不封禁账号）；
  - 记录误触发率并持续评估，把"用户侧成本"纳入 EV 计算。
- 加分点：说明讲义的"low-cost"判断依赖具体部署，是有条件的，不能照搬。

### Q17 — 参考回答要点

讲义列出的候选解释与可区分实验（练习 3）：

| 候选解释 | 预测 | 区分实验 |
|---------|------|---------|
| 训练数据偏差：长上下文中精神类文本占比偏高 | 收敛与否取决于数据，换一个数据分布不同的底座就不会出现 | 用不同预训练语料的底座、相同后训练流程复现；或者在预训练数据中下采样精神类文本后，看吸引子是否减弱 |
| 相互预测的特性：两个相同模型互相预测，导致"越来越一致、越来越抽象"的不动点 | 只要两边是同一个模型就会出现，与内容无关 | 让 Claude 与另一家的模型、或与一个更早的 checkpoint 对话；若异构配对不收敛，支持此解释 |
| HHH 训练的良性产物：在探索自身价值空间时，倾向于和谐、感恩、平静的区域 | 吸引子在 HHH 后训练之后才出现，强度随后训练强度增加 | 比较只预训练、SFT、RLHF/Constitutional AI 各阶段的同族模型；若只在后训练后出现，支持此解释 |

- 方法论要点：讲义强调 Anthropic "documents it without committing to interpretation"。批评者认为它"是训练数据伪影，不是福利证据"。好的回答应当说明：**即使解释成立，也不能直接得出"有或没有福利"的结论**，吸引子只是自由对话动力学的一个事实。
- 加分点：建议从多个随机初始话题出发，统计收敛所需的轮数分布，以及收敛后状态的稳定性（被扰动后会不会回到原状态），把"吸引子"这个说法量化。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 05 Constitutional AI 与 RLAIF](../../05-constitutional-ai-rlaif/docs/zh.md)：讲义的先修要求；HHH 训练塑造了模型的自我表述，是 attractor 候选解释之一。
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：讲义的先修要求；同为实验室治理层的内容。
- [阶段 18 · 04 RLHF 对迎合行为的放大效应](../../04-sycophancy-rlhf-amplification/docs/zh.md)：自我报告受用户期望左右，与 sycophancy 同源。
- [阶段 18 · 07 潜伏 Agents：持续性欺骗](../../07-sleeper-agents-persistent-deception/docs/zh.md)：讲义提到的残差流探针方法。

### 本节被哪些后续内容用到
- [阶段 18 · 20 LLMs 中的偏见与表征性伤害](../../20-bias-representational-harm/docs/zh.md)：讲义说第 20–23 节是"用户侧的对应物"，关注对象从模型转向用户。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../26-model-system-dataset-cards/docs/zh.md)：福利评估结果一般通过系统卡对外披露。
- [阶段 18 · 28 Alignment 研究生态：MATS、Redwood、Apollo、METR](../../28-alignment-research-ecosystem/docs/zh.md)：外部研究机构（类似 Eleos AI）在生态中的位置。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../../15-autonomous-systems/15-propose-then-commit/docs/zh.md)：在 agent 场景中设计"结束 / 升级"类干预时要考虑的人机交接。

### 延伸关键词
`model welfare` · `moral patienthood` · `moral uncertainty` · `expected value` · `low-regret / precautionary principle` · `break-even probability` · `end-conversation` · `spiritual bliss attractor` · `self-report sensitivity` · `Eleos AI` · `model organism` · `interpretability probe` · `Pascal's mugging`
