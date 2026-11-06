# 测验 · 梳理假设，优先验证风险最高的一项（Map Assumptions and Resolve the Riskiest One First）

> **阶段 14 · Agent 工程 · 第 49 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 路线图隐藏不确定性 | 讲义："A roadmap hides uncertainty inside features. An assumption map exposes what must be true before those features deserve to exist." |
| 2 | 每次构建都包含赌注 | 事故工具依赖于：告警上下文足以识别服务、工程师信任不是自己推出的建议、响应时间真的重要、能在不越权的情况下拿到数据、流程足够频繁值得维护 |
| 3 | 五类假设 | Value（成效够不够重要）、Usability（用户能否理解并行动）、Feasibility（能否用现有数据和约束做到）、Viability（组织能否承担成本、归属与运维）、Safety（失败时后果是否可接受） |
| 4 | 可证伪的写法 | "功能有用"无法检验；"十名值班工程师中有八名用只读结果更快找到正确服务"可以检验 |
| 5 | 风险的三个维度（1–5 分） | Impact（假设为假时的损害）、Uncertainty（现有证据有多弱）、Irreversibility（承诺之后才发现错的代价） |
| 6 | 示例公式 | `risk = impact × uncertainty + irreversibility`；讲义强调公式不通用，目的是逼团队说清"为什么先解决这个未知" |
| 7 | 决定性实验的五要素 | 可能为假的主张、真实样本、可观察的结果、**事先**定好的阈值、通过/失败/模糊三种结果各自的下一步决策 |
| 8 | 避免确认仪式 | 只证明"团队能把它做出来"的测试不是实验 |
| 9 | 可逆性决定顺序 | 只读回放先于生产集成；临时适配器先于数据迁移；人工批准的建议先于自动执行 |
| 10 | 代码的简化 | 只有 open/tested 两种状态（不区分支持还是否定）；排序与选下一个实验的平局规则不一致；`range` 判断会放过 `3.0` 和 `True`；没有假设类别字段 |

### 核心技能（能动手做到）

- [ ] 把一个功能想法拆成至少五条可证伪的假设，并分到 Value / Usability / Feasibility / Viability / Safety
- [ ] 为每条假设打 impact、uncertainty、irreversibility 分，并能为分数给出一句理由
- [ ] 手算 `risk_score` 并预测 `prioritize` 和 `next_experiment` 的输出，包括平局情况
- [ ] 为最高风险的开放假设设计一个包含阈值和三种后续决策的决定性实验
- [ ] 解释为什么在示例公式下不可逆性的影响很小，并比较不同公式对排序的影响
- [ ] 扩展代码，让"被证据否定"的假设触发"重新框定或停止"，而不是简单标记为 tested

---

## 二、基础自测（选择题）

**Q1.** 下面哪一条是**可证伪**的假设？

- A. 这个功能很有用
- B. 用户会喜欢它
- C. 这个设计很现代
- D. 在十次真实事故回放中，十名值班工程师里至少八名使用只读结果比现状更快找到正确的服务

**Q2.** `risk_score(Assumption("x", 5, 4, 3, "test"))` 的返回值是：

- A. 23
- B. 60
- C. 12
- D. 27

**Q3.** "组织能否承担它的成本、归属和运维？"属于哪一类假设？

- A. Value
- B. Feasibility
- C. Viability
- D. Usability

**Q4.** 对示例数据调用 `next_experiment(example())`，返回的假设是：

- A. "Automatic remediation is acceptable"
- B. "Engineers can identify the right service from alert context"
- C. "Two-minute diagnosis matters"
- D. `None`

**Q5.** 给示例中第一条假设（"Engineers can identify..."）补上证据 `"9 of 10 replays correct"` 后，`next_experiment` 返回的假设及其 `test` 字段是：

- A. "Automatic remediation is acceptable"，`test` 为 "Do not automate; test approval workflow first"
- B. "Two-minute diagnosis matters"，`test` 为 "Interview five incident commanders"
- C. 仍是 "Engineers can identify..."，因为它分数最高
- D. `None`，因为已经没有开放假设

**Q6.** `risk_score(Assumption("x", 3.0, 3, 3, "t"))` 的结果是：

- A. 抛出 `ValueError`，因为 3.0 不是整数
- B. `12`
- C. 抛出 `TypeError`
- D. `12.0`

**Q7.** 按讲义"Reversibility Changes Order"，下列哪组顺序是正确的？

- A. 先做生产集成以便最快学习，再做只读回放
- B. 只读回放先于生产集成；临时适配器先于数据迁移；人工批准的建议先于自动执行
- C. 先做数据迁移，再用临时适配器验证
- D. 顺序无所谓，只要最终都做

**Q8.** 下面哪一项**不是**讲义所说"有用的实验"必须具备的要素？

- A. 一个可能为假的主张
- B. 在看到结果之前就定好的阈值
- C. 一个能说服利益相关方的精美演示
- D. 针对通过、失败、模糊三种结果的下一步决策

---

## 三、动手 / 代码题

**Q9.**（读代码找 bug：平局规则不一致）

```python
def prioritize(items: list[Assumption]) -> list[dict]:
    ranked = sorted(items, key=lambda item: (-risk_score(item), item.statement))
    ...

def next_experiment(items: list[Assumption]) -> Assumption | None:
    open_items = [item for item in items if not item.evidence]
    return max(open_items, key=risk_score, default=None)
```

设 `b = Assumption("B claim", 3, 3, 1, "t")`、`a = Assumption("A claim", 2, 4, 2, "t")`，两者都未测试。

1. 计算两者的风险分。
2. `prioritize([b, a])` 排在第一位的是谁？`next_experiment([b, a])` 返回谁？为什么不一致？这会造成什么实际问题？
3. 修复 `next_experiment`，让它与 `prioritize` 永远一致。

**Q10.**（公式与讲义的张力）讲义说："High-consequence, irreversible choices need earlier evidence." 但在示例中，不可逆性为 5 的 "Automatic remediation is acceptable" 只排第二。

1. 在 `impact × uncertainty + irreversibility` 下，分数范围是多少？不可逆性最多能改变多少分？"Automatic remediation"（I=5, U=4）的不可逆性需要多大才能超过第一名的 27？
2. 分别用 `I × U × R` 和 `I + U + R` 计算示例三条假设的分数，排序会怎样变化？
3. 你会怎样修改选择逻辑，让"高不可逆性"真正前置？说明你的方案的代价。

**Q11.**（扩展：证据要能改变方向）讲义流程图中，证据"Supports → Bounded build"，"Rejects → Reframe or stop"。但代码中只要 `evidence` 非空就是 `"tested"`：

```python
"status": "tested" if item.evidence else "open"
```

例如 `evidence="rejected: 2 of 10"` 依然显示为 `tested`。请：

1. 给 `Assumption` 增加 `result` 字段（`"supports" | "rejects" | "ambiguous"`），并写 `status(item)`。
2. 写 `next_decision(items) -> str`：有被否定的假设 → "reframe or stop: <最高风险的被否定假设>"；否则有开放或模糊的 → "run experiment: <最高风险那条的 test>"；全部被支持 → "bounded build"。
3. 用示例验证四种情形：第 2 条被支持；第 1 条再被否定；全部被支持；第 1 条结果模糊。

**Q12.**（输入校验）`risk_score` 用 `value not in range(1, 6)` 校验维度。

1. 依次判断 `3`、`3.0`、`True`、`"3"`、`0`、`6` 是否会通过这项检查，`risk_score(Assumption("x", True, True, True, "t"))` 返回什么？
2. 写一个严格版的校验函数，只接受 1–5 的 `int`（排除 `bool` 和 `float`）。

---

## 四、面试高频题

**Q13.**（基础必考）什么是假设地图（assumption map）？它和产品路线图有什么不同，为什么要先做它？

**Q14.**（原理深挖）为什么要把风险拆成 impact、uncertainty、irreversibility 三个维度分别打分，而不是直接给一个"风险分"？如果团队对公式有分歧怎么办？

**Q15.**（工程实践）请为假设"值班工程师能从告警上下文中识别出正确的故障服务"设计一个决定性实验。

**Q16.**（场景设计）业务方坚持第一版就要上线"AI 自动修复生产事故"。你怎样用假设地图说服他们调整顺序？

**Q17.**（追问型）本节延伸阅读引用了 Boehm 的螺旋模型。风险驱动的开发与"按功能优先级排 backlog"有什么本质区别？

---

## 五、参考答案与解析

### Q1 — 答案：D

D 有明确的人群（十名值班工程师）、真实样本（十次事故回放）、可观察的结果（找到正确服务的速度）和失败的可能（少于八名）。讲义："'The feature is useful' cannot be tested. 'Eight of ten on-call engineers identify the correct service faster with the read-only result' can." A、B、C 都没有可观察的判定标准。

### Q2 — 答案：A

`5 × 4 + 3 = 23`，与测试 `test_risk_score_weights_impact_and_uncertainty` 一致。B 是三者相乘；C 是三者相加；D 是示例第一条假设的分数（`5 × 5 + 2`）。

### Q3 — 答案：C

讲义表格："Viability — Can the organization sustain cost, ownership, and operation?" A 问成效是否足够重要；B 问系统能否用现有数据和约束做到；D 问用户能否理解并据此行动。注意 Feasibility 是"能不能做出来"，Viability 是"做出来之后养不养得起"。

### Q4 — 答案：B

三条的分数：Engineers… = `5×5+2 = 27`（开放）；Automatic remediation = `5×4+5 = 25`（开放）；Two-minute = `4×2+1 = 9`（已有证据，被排除）。开放假设中最高的是 27。A 是第二高；C 已测试；D 只有在没有开放假设时才返回。

### Q5 — 答案：A

第一条有了证据后，开放假设只剩 "Automatic remediation is acceptable"（25），它被选中（已实际运行验证）。注意它的 `test` 字段 "Do not automate; test approval workflow first" 本身就是一个**改变方向**的决定：不直接验证"自动修复可接受"，而是先验证风险更低、可逆的"审批工作流"。这正是讲义"人工批准的建议先于自动执行"的体现。B 已经有证据；C 已有证据所以不再是开放的；D 错在仍有一条开放假设。

### Q6 — 答案：D

`3.0 in range(1, 6)` 为 `True`——`range` 的成员判断按数值相等比较，`3.0 == 3`。于是校验通过，`3.0 × 3 + 3 = 12.0`，返回**浮点数**（已实际运行验证），违反了函数注解 `-> int` 和错误消息中"must be integers"的承诺。A 是错误消息让人以为会发生的事；B 少了类型变化；C 不会发生。

### Q7 — 答案：B

讲义原文："A read-only replay can precede a production integration. A temporary adapter can precede a data migration. A human-approved recommendation can precede automatic action." 共同原则：先用可逆、低后果的方式拿到证据，再做高后果、不可逆的承诺。A、C 把顺序倒过来；D 忽略了"学到的时间点"决定了犯错的代价。

### Q8 — 答案：C

讲义列出的五要素是：可能为假的主张、人群或真实样本、可观察的结果、事先确定的阈值、针对通过/失败/模糊证据的下一步决策。精美演示恰恰是讲义警告的"确认仪式"："Avoid tests that only demonstrate that the team can build the idea."

### Q9 — 参考答案

1. `b`：`3 × 3 + 1 = 10`；`a`：`2 × 4 + 2 = 10`，平局。
2. 实际运行：`prioritize([b, a])` 的顺序是 `["A claim", "B claim"]`（分数相同时按 statement 字母序）；`next_experiment([b, a])` 返回 `"B claim"`——`max` 在多个最大值中返回**第一个遇到的**，即输入顺序中的第一个。两个函数对同一份数据给出不同的"第一名"：输出到 `assumption-map.json` 的排序显示 A 最优先，但真正被选去做实验的是 B。实际问题是：团队看着地图讨论 A 的实验，代码却推荐了 B；而且输入顺序一变，推荐结果也会变，不可复现。
3. 修复：让两个函数共用同一个排序键：

```python
def rank_key(item: Assumption) -> tuple[int, str]:
    return (-risk_score(item), item.statement)

def prioritize(items):
    ranked = sorted(items, key=rank_key)
    ...

def next_experiment(items):
    open_items = [item for item in items if not item.evidence]
    return min(open_items, key=rank_key, default=None)
```

实际运行：`[b, a]` 与 `[a, b]` 两种输入都返回 `"A claim"`；示例仍返回 "Engineers can identify..."；空列表返回 `None`。注意用 `min` 搭配"负分"键，等价于"分数最高、平局时字母序最小"。

### Q10 — 参考答案

1. 每个维度 1–5，`I × U + R` 的范围是 **2–30**（已实际计算）。前一项最多 25，不可逆性只贡献 1–5 分，即最多**改变 4 分**。"Automatic remediation" 的 `I × U = 20`，要超过 27 需要 `R ≥ 8`，在 1–5 分制下**不可能**。也就是说，在这个公式下，只要 `I × U` 落后 5 分以上，不可逆性再高也无法前置。

2. 实际计算：

| 假设 | I×U+R | I×U×R | I+U+R |
|------|-------|-------|-------|
| Engineers can identify the right service（5,5,2） | **27** | 50 | 12 |
| Automatic remediation is acceptable（5,4,5） | 25 | **100** | **14** |
| Two-minute diagnosis matters（4,2,1，已测试） | 9 | 8 | 7 |

在乘法和加法公式下，"Automatic remediation"都会成为第一名。

3. 方案示例：
   - **门槛法**：把"不可逆性 ≥ 4 的开放假设"作为第一排序键，即 `key = (irreversibility >= 4, risk_score)`；实际运行时示例会选中 "Automatic remediation"。代价：一些不可逆但影响很小的假设也会被提前。
   - **乘法**：`I × U × R`，让三个维度对等。代价：任何一个维度为 1 时分数被大幅压低。
   - **不改公式，改方案**：示例其实是通过把高不可逆性的选项**变成可逆的测试**（"Do not automate; test approval workflow first"）来处理的——这也是讲义的思路：降低不可逆性，而不是只在排序上提前它。
   - 讲义自己说 "The formula is not universal. Its purpose is to force the team to state why one unknown should be resolved before another." 所以关键是把选择的理由写下来。

### Q11 — 参考答案

1. 字段与状态：

```python
@dataclass(frozen=True)
class Assumption:
    statement: str
    impact: int
    uncertainty: int
    irreversibility: int
    test: str
    evidence: str = ""
    result: str = ""          # "supports" | "rejects" | "ambiguous"

def status(item: Assumption) -> str:
    if not item.evidence:
        return "open"
    return {"supports": "supported", "rejects": "rejected",
            "ambiguous": "ambiguous"}.get(item.result, "invalid")
```

2. 决策函数：

```python
def next_decision(items: list[Assumption]) -> str:
    rejected = [i for i in items if status(i) == "rejected"]
    if rejected:
        worst = max(rejected, key=risk_score)
        return f"reframe or stop: {worst.statement}"
    pending = [i for i in items if status(i) in ("open", "ambiguous")]
    if pending:
        top = min(pending, key=lambda i: (-risk_score(i), i.statement))
        return f"run experiment: {top.test}"
    return "bounded build"
```

3. 实际运行结果：

| 情形 | 各假设状态 | `next_decision` |
|------|-----------|----------------|
| 第 2 条 supports | open / supported / open | `run experiment: Replay ten incidents with a read-only prototype` |
| 再把第 1 条设为 rejects（"3 of 10 replays correct"） | rejected / supported / open | `reframe or stop: Engineers can identify the right service from alert context` |
| 全部 supports | — | `bounded build` |
| 第 1 条 ambiguous（"6 of 10, threshold 8"） | ambiguous / supported / open | `run experiment: Replay ten incidents with a read-only prototype` |

要点：被否定的假设**优先于**任何新实验——核心假设被否定时，继续测试其它假设毫无意义，应该先重新框定（回到第 47 节）或停止。模糊结果被当作"仍需实验"，但不应原样重跑：实际中应设计一个更尖锐的实验（更大样本、更清晰的阈值），否则会陷入"一直模糊、一直继续"的确认仪式。`"invalid"` 用于捕获有证据却没写结论的记录。

### Q12 — 参考答案

1. 实际运行：`3` 通过；`3.0` 通过（`3.0 == 3`）；`True` 通过（`bool` 是 `int` 的子类，`True == 1`）；`"3"` 不通过（字符串不等于任何整数），抛 `ValueError`；`0`、`6` 不通过。`risk_score(Assumption("x", True, True, True, "t"))` 返回 `1 × 1 + 1 = 2`。

2. 严格校验：

```python
def check_dimension(value: object) -> bool:
    return type(value) is int and 1 <= value <= 5

def risk_score(item: Assumption) -> int:
    for value in (item.impact, item.uncertainty, item.irreversibility):
        if not check_dimension(value):
            raise ValueError("risk dimensions must be integers from one to five")
    return item.impact * item.uncertainty + item.irreversibility
```

`type(value) is int` 排除了 `bool`（`type(True)` 是 `bool`）和 `float`；用 `isinstance(value, int)` 则会放过 `True`。实际运行：`3`、`5` 为 True，`3.0`、`True`、`"3"`、`0`、`6` 均为 False。更好的位置是在 `Assumption.__post_init__` 里校验，让非法假设根本无法被创建（讲义第 46 节："A type that prevents an invalid state is stronger than..."）。

### Q13 — 参考回答要点

- **定义**：把一个计划中的构建拆成"它要有价值、可用、可行、可持续、安全，必须有哪些事情为真"，每条写成可证伪的陈述，并标注风险和检验方式。
- **与路线图的不同**：路线图按功能和时间排列，不确定性被藏在"做功能"里；假设地图按**风险**排列，显式写出"如果这条是假的，功能就不该存在"。
- **为什么先做**：在投入构建前用最便宜的方式消除最大的不确定性；避免在错误前提上积累代码和承诺。
- **五类假设**：Value、Usability、Feasibility、Viability、Safety——Safety 最常被功能列表遗漏（讲义练习 2）。
- 加分点：说明假设地图是"活文档"，被证据否定的假设会改变方向（重新框定或停止），被支持的假设变成边界明确的构建。
- 常见误区：把实现任务（"接入告警 API"）当成假设。

### Q14 — 参考回答要点

- **拆分的理由**：三者含义不同，混成一个数会掩盖"为什么"。高影响但证据充分的假设不急；高不确定但影响很小的也不急；高不可逆性的假设即使分数中等，也需要在承诺前验证。
- **透明**：分开打分让讨论从"我觉得风险大"变成"我认为影响是 5，因为……"，分歧点一目了然。
- **公式不通用**：讲义明确说示例公式不是普适的，目的是逼团队说明排序理由。示例中加法项让不可逆性的权重很小（见 Q10），不同团队可以选乘法、门槛或加权。
- **有分歧时**：先对齐每个维度的打分标准（例如 impact 5 = 用户可见的生产事故）；比较不同公式下的排序，若第一名稳定就不必争论；若不稳定，说明需要讨论的是价值取舍而不是算术。
- 加分点：指出打分本身也有不确定性，分数应附一句理由和证据来源。

### Q15 — 参考回答要点

- **主张**：值班工程师仅凭告警上下文（可加只读的部署记录），能比现状更快地识别出正确的故障服务。
- **样本**：从历史事故中抽取 10–20 个真实告警（覆盖常见与少见服务，包含部署记录缺失的异常——第 48 节），邀请 8–10 名不同资历的值班工程师。
- **方式**：只读回放（讲义推荐的 "read-only replay"），对照组用现有流程（三个仪表盘），实验组额外看到只读的候选服务提示。
- **可观察结果**：识别正确率、用时、是否需要额外查询、对建议的信任度（事后问卷）。
- **事先定阈值**：例如"≥ 8/10 的工程师在 ≥ 80% 的案例中两分钟内识别正确，且正确率不低于对照组"。
- **三种结果的决策**：通过 → 进入第 50 节选择最小切片；失败 → 告警上下文不足，重新框定（补数据源？换成效？）或停止；模糊 → 扩大样本或缩小人群（只针对新人？）后再测一次。
- 常见误区：只用合成数据、只找支持者、看完结果再定阈值。

### Q16 — 参考回答要点

- **把需求拆成假设**：自动修复可行（Feasibility）、修复动作安全（Safety）、工程师和事故指挥官能接受（Usability/Viability）、诊断本身准确（前置的核心假设）。
- **打分**：自动修复的 impact 和 irreversibility 都是 5（错误的写操作可能扩大事故），且"诊断准确"这一前置假设的不确定性最高。
- **论证顺序**：自动修复依赖于诊断准确——如果诊断都没被证实，自动修复必然建立在未验证的前提上。按讲义，应该先用只读回放验证诊断，再用"人工批准的建议"验证修复动作，最后才考虑窄范围的自动执行。
- **给业务方一条路径**：不是拒绝，而是给出带阈值的阶段门：只读诊断达标 → 人工批准试点达标 → 窄范围自动化（如仅限重启特定 pod）。
- 加分点：引用阶段 17 · 23 中"AI 建议、人类批准"的行业实践；把业务方关心的指标（MTTR）写进每个阶段的阈值。
- 常见误区：只用"风险太大"来否决，不给出可验证的路线。

### Q17 — 参考回答要点

- **螺旋模型**（讲义延伸阅读 Boehm）：每一轮迭代先识别并解决当前最大的风险，再决定是否投入更深的承诺；每一轮的形态由风险决定（原型、仿真、基准测试等）。
- **与功能 backlog 的区别**：backlog 按"价值/成本"排功能，默认每个功能的前提成立；风险驱动按"不确定性 × 后果"排**未知**，先花钱买信息再花钱做功能。
- **产出不同**：backlog 的产出是功能；风险驱动一轮的产出可能只是"证据"——包括"停止"这个结论。
- **对 agent 时代的意义**：实现很便宜时（第 47 节），最贵的是在错误方向上走得很远；先解决风险让速度指向正确方向。
- 加分点：说明两者可以结合——用假设地图决定下一轮学什么，用 backlog 管理已验证方向上的工作；本节代码的 `next_experiment` 就是螺旋模型"下一轮做什么"的极简版。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 48 发现人们实际执行的工作流](../../48-discover-the-real-workflow/docs/zh.md)：观察到的摩擦与缺少直接证据的说法，是本节假设的来源。
- [阶段 14 · 47 先定义预期成效，再选择交付形式](../../47-outcomes-before-output/docs/zh.md)：被否定的核心假设会让你回到成效框定。
- [阶段 14 · 44 制定有证据支撑的执行计划](../../44-plan-from-evidence/docs/zh.md)：每一步都要有证据的计划思路。

### 本节被哪些后续内容用到
- [阶段 14 · 50 选择足以改变决策的最小实现范围](../../50-choose-the-smallest-testable-slice/docs/zh.md)：把最高风险的开放假设变成"必须证明的集合"，据此选切片（讲义 "What You Keep"）。
- [阶段 14 · 52 在结果产生前设计成功指标](../../52-design-success-metrics/docs/zh.md)：实验阈值与成功指标的设计。
- [阶段 14 · 53 有意识地选择原型、试点或生产方案](../../53-prototype-pilot-or-production/docs/zh.md)：不可逆性决定选择原型、试点还是生产。
- [阶段 17 · 21 对 LLM Features 进行 A/B 测试](../../../17-infrastructure-and-production/21-ab-testing-llm-features/docs/zh.md)：上线后用对照实验验证价值假设。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)：在生产中以可逆方式降低不可逆性。

### 延伸关键词
`assumption mapping` · `falsifiability` · `risk-driven development` · `spiral model` · `irreversibility / one-way door` · `decisive experiment` · `pre-registered threshold` · `confirmation ritual` · `value / usability / feasibility / viability / safety` · `goal-obstacle analysis`
