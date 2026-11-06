# 测验 · 选择足以改变决策的最小实现范围（Choose the Smallest Slice That Can Change the Decision）

> **阶段 14 · Agent 工程 · 第 50 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 小的价值在于能证明重要的事 | 讲义："A tiny build that cannot change the next decision is merely incomplete." |
| 2 | 用它证明的假设来定义切片 | 切片的身份不是"做了哪些功能"，而是"能证明哪些假设" |
| 3 | 纵向 = 端到端的证据 | 切片要穿过观察成效所需的最小真实工作流；可以在用户、数据、时长、能力上做窄，但**不能**通过去掉要检验的那个不确定性来做窄 |
| 4 | 先定义必须证明的集合 | 取最高风险的开放假设组成 required proof；只有**覆盖全部**的候选切片才有资格参与比较 |
| 5 | 资格门 > 算术 | 讲义："The eligibility gate matters more than the arithmetic."——分数再高、没覆盖必证项也要淘汰 |
| 6 | 五个比较维度 | 成效价值（越多越好）、减少的不确定性（越多越好）、投入（越少越好）、后果（越少越好）、可逆性（越高越好） |
| 7 | 五种假最小 | 只有 UI（去掉数据与运维不确定性）、只有基础设施（证明技术可行但没有用户价值）、只走 happy path（省略最危险的异常）、演示（有说服力但不可重复测量）、平台（一个工作流都没跑通就先造可复用机器） |
| 8 | 停止规则 | 实现前写好失败时怎么办：放弃成效、换目标用户/情境、换机制、收集更好证据、进一步收窄权限；"如果每个结果都导向'继续构建'，这个切片就不是实验" |
| 9 | 代码的打分 | `score = (价值 + 减少的不确定性) / (投入 + 后果 × (不可逆 2，可逆 0.5))`，保留 3 位小数；`choose` 先用子集判断过滤，再按 `(score, -effort, name)` 取最大 |
| 10 | 代码的局限 | 只校验 effort ≥ 1（负的后果会导致除零）；输出的 alternatives 不标注是否合格；平局时名字字母序**大**的胜出；没有停止规则字段；required proof 与第 49 节的假设地图没有连接 |

### 核心技能（能动手做到）

- [ ] 从假设地图中挑出最高风险的开放假设，写成 required proof 集合
- [ ] 为同一成效设计三个后果等级不同的候选切片，并判断每个是否覆盖必证项
- [ ] 手算 `score`，并解释可逆/不可逆对分数的 4 倍差异
- [ ] 识别计划中的五种"假最小"，说出它们各自绕过了哪个不确定性
- [ ] 为切片写出包含通过 / 失败 / 模糊三种结果的停止规则，确认不是"什么结果都继续做"
- [ ] 改进代码：严格输入校验、在输出中标注不合格原因、把第 49 节的输出接成第 50 节的输入

---

## 二、基础自测（选择题）

**Q1.** 按讲义，一个"小切片"有用的前提是：

- A. 它能改变一个重要的决策
- B. 它的代码量最少
- C. 它避开了真实的不确定性，所以风险低
- D. 它有精美的界面，便于演示

**Q2.** 示例中 "read-only incident replay"（价值 4、减少不确定性 5、投入 2、后果 1、可逆）的 `score` 是：

- A. 4.5
- B. 2.25
- C. 3.6
- D. 9.0

**Q3.** 在示例中加入一个更便宜的候选 `Slice("log grep script", 5, 5, 1, 1, True, ("service-identification",))`，它的分数是 6.667。`choose(..., {"service-identification", "operator-trust"})` 返回：

- A. "log grep script"，因为分数最高
- B. 抛出 `ValueError`
- C. "dashboard mockup"
- D. "read-only incident replay"

**Q4.** "在合成数据上做一个精美仪表盘"可以检验理解程度，却检验不了数据可行性。它属于哪一种"假最小"？

- A. Infrastructure-only minimum
- B. UI-only minimum
- C. Platform minimum
- D. Happy-path minimum

**Q5.** `choose(example(), set())`（必证集合为空）返回：

- A. 抛出 `ValueError("no slice proves the required assumptions")`
- B. "dashboard mockup"，因为投入最小
- C. "read-only incident replay"
- D. "production auto-remediation"

**Q6.** 关于停止规则，讲义的判断标准是：

- A. 如果每一种结果都导向"继续构建"，这个切片就不是实验
- B. 停止规则只在试点失败后再补写
- C. 停止规则的唯一选项是放弃整个成效
- D. 只要切片足够小，就不需要停止规则

**Q7.** 示例中 "production auto-remediation"（价值 5、减少不确定性 4、投入 10、后果 5、不可逆）的 `score` 是：

- A. 0.9
- B. 0.6
- C. 0.72
- D. 0.45

**Q8.** 两个合格切片 `alpha` 和 `zeta` 的所有数值完全相同。`choose([alpha, zeta], ...)` 与 `choose([zeta, alpha], ...)` 分别返回：

- A. 都返回 `alpha`
- B. 都返回 `zeta`
- C. 都抛出异常，因为无法区分
- D. 各自返回列表中的第一个

---

## 三、动手 / 代码题

**Q9.**（手算与边界）`score` 的实现：

```python
def score(item: Slice) -> float:
    if item.effort < 1:
        raise ValueError("effort must be positive")
    risk_penalty = item.consequence * (2 if not item.reversible else 0.5)
    return round((item.outcome_value + item.uncertainty_reduced) / (item.effort + risk_penalty), 3)
```

1. 手算示例三个切片的分子、分母和分数。
2. 如果 "read-only incident replay" 改为不可逆、"production auto-remediation" 改为可逆，分数各是多少？可逆性对罚分的影响是几倍？
3. 找出一组能让 `score` 抛出 `ZeroDivisionError` 或返回负分的输入，并写出更严格的校验。

**Q10.**（输出会误导读者）`decision` 的 `alternatives` 列出了所有未被选中的切片及其分数，但没有标注它们是否合格。

1. 在示例中加入 Q3 的 "log grep script" 后，alternatives 里会出现哪些分数？读者可能得出什么错误结论？
2. 改写 `decision`：每个切片附带 `eligible` 和 `missing_proof`，并让合格的备选排在前面。

**Q11.**（讲义练习 4：停止规则）给切片决策增加停止规则：`stop_rule = {"pass": ..., "fail": ..., "ambiguous": ...}`。写一个 `check_stop_rule(rule) -> list[str]`：

- 三种结果都必须有非空决策；
- 如果三种结果都是"keep building"之类的继续构建，报 "every result leads to keep building; slice is not an experiment"。

并为 "read-only incident replay" 写一个合格的停止规则。

**Q12.**（把第 49 节接到第 50 节）讲义说："Take the highest-risk open assumptions and turn them into a required proof set." 第 49 节的 `outputs/assumption-map.json` 中，每行有 `statement`、`risk_score`、`status`。假设团队约定以下映射：

```python
PROOF_TAG = {
    "Engineers can identify the right service from alert context": "service-identification",
    "Automatic remediation is acceptable": "operator-trust",
    "Two-minute diagnosis matters": "outcome-value",
}
```

1. 写 `required_proof_from(assumption_map, min_risk=20)`：取 `status == "open"` 且 `risk_score >= min_risk` 的假设，映射成标签集合。
2. 用第 49 节的真实输出，分别在 `min_risk=20` 和 `min_risk=26` 时计算必证集合，并给出 `choose(example(), ...)` 的结果。
3. 如果把已检验的 "Two-minute diagnosis matters" 也放进必证集合，会发生什么？这说明了什么？

---

## 四、面试高频题

**Q13.**（基础必考）什么是"最小可检验切片"？它和"先做一个简化版功能"有什么区别？

**Q14.**（原理深挖）为什么讲义说"资格门比算术更重要"？如果只用加权分数排序会出什么问题？

**Q15.**（工程实践）评审一份"第一阶段计划"时，你如何识别讲义列出的五种"假最小"？

**Q16.**（场景设计）为"值班工程师在两分钟内定位故障服务"这一成效，设计三个不同后果等级的切片，写出必证集合、你的选择和停止规则。

**Q17.**（追问型）延伸阅读提到 MVP 的定义很模糊。"能改变决策的最小切片"与常说的 MVP 有什么区别？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义开篇："Small is useful only when it proves something important. A tiny build that cannot change the next decision is merely incomplete." B 是常见误解，代码少不等于能产生决定性证据；C 恰好是讲义警告的做法——"It should not be narrow by removing the exact uncertainty you need to test"；D 是"演示最小"。

### Q2 — 答案：C

分子 `4 + 5 = 9`；可逆，罚分 `1 × 0.5 = 0.5`；分母 `2 + 0.5 = 2.5`；`9 / 2.5 = 3.6`（与输出文件一致）。A 是忽略罚分的 `9 / 2`；B 是同一切片改为不可逆时的分数（`9 / (2 + 2)`）；D 只是分子。

### Q3 — 答案：D

`choose` 先过滤：`required_proof <= set(item.proves)`。"log grep script" 只证明了 `service-identification`，缺 `operator-trust`，被淘汰；"dashboard mockup" 同样不合格。合格的只有 replay（3.6）和 auto-remediation（0.45），选 replay（已实际运行验证）。这正是讲义 Build It 的要求："Add a cheaper candidate that proves only one required assumption. It should remain ineligible even if its numerical score is high." A 忽略了资格门；B 只有在没有任何合格切片时才会发生；C 不合格。

### Q4 — 答案：B

讲义："A polished dashboard on synthetic data may test comprehension but not data feasibility"，对应 "The UI-only minimum: removes the data and operational uncertainty." A 是只证明技术可行而没有用户价值；C 是先造可复用机器；D 是省略最危险的异常。

### Q5 — 答案：C

空集是任何集合的子集（`set() <= set(x)` 恒为 True），所以三个切片都合格，按分数选出 replay（3.6）。A 不会发生；B 投入最小但分数 2.667 低于 3.6；D 分数最低。这暴露了一个隐患：忘记填必证集合时，资格门**静默失效**，退化为纯打分。生产中应把空的 required proof 视为错误。

### Q6 — 答案：A

讲义："If every result leads to 'keep building,' the slice is not an experiment." 停止规则要在实现**之前**写好（B 错），并且选项不止"放弃"——还可以换目标用户或情境、换机制、收集更好的证据、进一步收窄权限（C 错）。D 混淆了"小"与"可证伪"。

### Q7 — 答案：D

分子 `5 + 4 = 9`；不可逆，罚分 `5 × 2 = 10`；分母 `10 + 10 = 20`；`9 / 20 = 0.45`。A 是忽略罚分的 `9 / 10`；B 是罚分系数取 1 时的 `9 / 15`；C 是改为可逆时的 `9 / 12.5 = 0.72`。

### Q8 — 答案：B

`max` 的键是 `(score(item), -item.effort, item.name)`。前两项相同时比较 `name`，`"zeta" > "alpha"`，所以 `max` 选 `zeta`，与输入顺序无关（已实际运行验证）。平局规则是确定性的，但"字母序靠后的胜出"没有任何业务含义，可能与读者直觉相反；若想让字母序靠前者胜出，应改用 `min` 配合 `(-score, effort, name)`。第 49 节的 `next_experiment` 则是另一种平局行为（取输入顺序中的第一个），两节代码的平局规则互不一致。

### Q9 — 参考答案

1. 手算（与运行输出一致）：

| 切片 | 分子（价值 + 不确定性） | 罚分 | 分母 | score |
|------|------|------|------|------|
| read-only incident replay | 4 + 5 = 9 | 1 × 0.5 = 0.5 | 2.5 | 3.6 |
| production auto-remediation | 5 + 4 = 9 | 5 × 2 = 10 | 20 | 0.45 |
| dashboard mockup | 2 + 2 = 4 | 1 × 0.5 = 0.5 | 1.5 | 2.667 |

2. replay 改为不可逆：`9 / (2 + 2) = 2.25`；auto-remediation 改为可逆：`9 / (10 + 2.5) = 0.72`（已实际运行验证）。同一后果下，不可逆的罚分是可逆的 `2 / 0.5 = 4` 倍。即便 auto-remediation 变成可逆，它也会因为投入 10 而远低于 replay——说明它的问题不只是风险，还有成本。

3. 边界输入（已实际运行验证）：
   - `effort=1, consequence=-2, reversible=True`：分母 `1 + (-2 × 0.5) = 0` → `ZeroDivisionError`；
   - `effort=1, consequence=-3, reversible=True`：分母 `-0.5`，得到 `-4.0`；
   - `effort=1.5` 能通过 `effort < 1` 的检查，尽管注解是 `int`。

   严格校验：

```python
def score(item: Slice) -> float:
    if type(item.effort) is not int or item.effort < 1:
        raise ValueError("effort must be a positive integer")
    for name in ("outcome_value", "uncertainty_reduced", "consequence"):
        value = getattr(item, name)
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    risk_penalty = item.consequence * (2 if not item.reversible else 0.5)
    return round((item.outcome_value + item.uncertainty_reduced) / (item.effort + risk_penalty), 3)
```

校验后示例三个分数不变；负的后果和非整数投入都会抛出 `ValueError`。由于 effort ≥ 1 且罚分 ≥ 0，分母恒 ≥ 1，除零不再可能。

### Q10 — 参考答案

1. 加入 "log grep script" 后，alternatives 中依次出现 auto-remediation（0.45）、log grep script（**6.667**）、dashboard mockup（2.667）。读者看到一个比被选方案（3.6）高得多的分数，会以为"选错了"或"打分有 bug"；看到 mockup 的 2.667，会以为它是"接近的第二选择"。其实这两个都**不合格**，分数根本不可比——资格门的结论没有写进输出，讲义"Keep `outputs/slice-decision.json`. It records why this slice is the smallest one that can change the decision"的"为什么"就丢了。

2. 参考实现：

```python
def decision(items: list[Slice], required_proof: set[str]) -> dict:
    selected = choose(items, required_proof)

    def row(item: Slice) -> dict:
        missing = sorted(required_proof - set(item.proves))
        return {**asdict(item), "score": score(item),
                "eligible": not missing, "missing_proof": missing}

    return {
        "required_proof": sorted(required_proof),
        "selected": row(selected),
        "alternatives": sorted(
            (row(i) for i in items if i is not selected),
            key=lambda r: (not r["eligible"], -r["score"]),
        ),
    }
```

实际运行（示例 + log grep script）：

| 备选 | score | eligible | missing_proof |
|------|-------|----------|---------------|
| production auto-remediation | 0.45 | True | `[]` |
| log grep script | 6.667 | False | `["operator-trust"]` |
| dashboard mockup | 2.667 | False | `["service-identification"]` |

另外把 `item != selected` 改成 `item is not selected`：原代码用值相等比较，若列表中有两个完全相同的切片，它们会被一起排除出 alternatives。

### Q11 — 参考答案

```python
KEEP_BUILDING = {"keep building", "continue", "build more"}

def check_stop_rule(rule: dict[str, str]) -> list[str]:
    issues: list[str] = []
    for outcome in ("pass", "fail", "ambiguous"):
        if not rule.get(outcome, "").strip():
            issues.append(f"stop rule has no {outcome} decision")
    if rule and all(rule.get(k, "").strip().lower() in KEEP_BUILDING
                    for k in ("pass", "fail", "ambiguous")):
        issues.append("every result leads to keep building; slice is not an experiment")
    return issues
```

replay 的合格停止规则（实际运行返回 `[]`）：

```python
{
    "pass": "build the bounded read-only assistant for one team",
    "fail": "stop: alert context cannot identify services; reframe outcome",
    "ambiguous": "collect ten more incidents with deployment records",
}
```

三种结果都是 "keep building" 时返回 `["every result leads to keep building; slice is not an experiment"]`；只写了 pass 时返回缺少 fail 与 ambiguous 两条问题。讲义列出的失败去向——放弃成效、换用户或情境、换机制、收集更好证据、进一步收窄权限——都可以作为 fail/ambiguous 的合法决策。关键词黑名单只是最低限度的检查；真正的判断是"不同结果是否会导向**不同**的行动"，可以进一步要求 pass 与 fail 的决策文本不同。

### Q12 — 参考答案

1. 实现：

```python
def required_proof_from(assumption_map: list[dict], min_risk: int = 20) -> set[str]:
    return {
        PROOF_TAG[row["statement"]]
        for row in assumption_map
        if row["status"] == "open" and row["risk_score"] >= min_risk
    }
```

2. 用第 49 节真实的 `assumption-map.json`（已实际运行验证）：
   - `min_risk=20`：两条开放假设（27、25）都入选，必证集合为 `{"operator-trust", "service-identification"}`，正好是本节 `main` 里硬编码的集合，`choose` 选 "read-only incident replay"；
   - `min_risk=26`：只剩 27 分那条，集合为 `{"service-identification"}`，仍选 replay（dashboard mockup 因只证明 operator-trust 而不合格）。

3. 集合变为 `{"operator-trust", "outcome-value", "service-identification"}`，没有任何切片证明 `outcome-value`，`choose` 抛出 `ValueError("no slice proves the required assumptions")`。这说明：已有证据支持的假设不该再进入必证集合，否则会无端淘汰所有候选；反过来，若一条高风险假设确实没有切片能证明，正确的反应是**设计新的切片**，而不是放宽资格门。另外，`PROOF_TAG` 本身是团队的约定（把"自动修复可接受"的检验落到"操作员信任审批流"），这一映射应写进决策记录，因为它决定了切片的资格。

### Q13 — 参考回答要点

- **定义**：用它能证明的假设来定义的切片——覆盖最高风险的开放假设、穿过观察成效所需的最小真实工作流、产出能改变下一个决策的证据。
- **与"简化版功能"的区别**：简化版功能按功能做减法，常常恰好把最难、最不确定的部分（真实数据、异常、权限）减掉了；最小可检验切片按**证据**做减法：可以在用户数、数据量、时长、能力上做窄，但必须保留要检验的不确定性。
- **例子**：只读回放 10 个真实事故（窄在只读、只回放、只 10 个），却完整检验了"能否识别服务"和"操作员是否信任"。
- 加分点：配套"必证集合 + 资格门 + 停止规则"；切片的产出是证据，可能导致停止。
- 常见误区：把"第一版"当作最小切片，结果是一个什么都证明不了的半成品。

### Q14 — 参考回答要点

- **资格门的作用**：确保候选切片能回答**这次**需要回答的问题。不覆盖必证项的切片，分数再高也只是"便宜地回答了另一个问题"。
- **只用加权分数的问题**：加权分数会让"便宜、低风险"的切片自然胜出，而这些切片往往正是通过去掉不确定性才变得便宜的（UI-only、happy-path）。本节示例中只证明一项的 log grep script 得 6.667，远高于 replay 的 3.6。
- **补偿性陷阱**：加权和允许一个维度的高分补偿另一个维度的缺失，但"缺少关键证据"不应被"便宜"补偿——这是非补偿性的约束。
- **讲义原话**："The lab's score is intentionally simple. The eligibility gate matters more than the arithmetic."
- 加分点：类比多目标决策中的"先满足约束、再在可行域内优化"；指出忘记填必证集合时资格门会静默失效（Q5）。

### Q15 — 参考回答要点

- **UI-only**：问"数据从哪来？是真实数据还是合成数据？运维流程是否参与？"——只用 mock 数据的，数据可行性未被检验。
- **Infrastructure-only**：问"哪个真实用户在什么情境下会用到它？成效如何被观察？"——只有管道和服务、没有用户的，价值未被检验。
- **Happy-path**：问"最危险的异常是什么？切片里有没有它？"（如部署记录缺失、权限不足，见第 48 节）。
- **Demo**：问"结果能否重复测量？阈值是什么？"——只有一次精心准备的演示的，不是实验。
- **Platform**：问"有没有一个工作流已经证明需要它？"——先建通用框架、插件系统、多租户的，属于过早抽象。
- **通用检查**：把计划对照必证集合逐项打勾；要求附停止规则；看是否存在"无论结果如何都继续"的倾向。
- 加分点：讲义练习 5——找出一个应等到切片之后再做的可复用平台组件。

### Q16 — 参考回答要点

- **必证集合**（来自第 49 节最高风险的开放假设）：`service-identification`（告警上下文足以识别服务）、`operator-trust`（工程师愿意依据非自己推出的建议行动，且审批流可接受）。
- **三个切片**：
  - 低后果：只读回放 10–20 个真实历史事故，工程师在回放中使用候选服务提示（覆盖两项，可逆，后果低）；
  - 中后果：在一个团队的真实值班中提供只读建议，所有动作仍由人执行（覆盖两项，可逆，后果中等，投入更高）；
  - 高后果：生产环境自动修复（覆盖两项，但不可逆、后果高、投入大）。
- **选择**：低后果的回放——资格相同，后果和投入最低，得分最高（与示例一致）。
- **停止规则**：通过（≥ 8/10 工程师在两分钟内识别正确且愿意采纳）→ 进入中后果试点；失败 → 告警上下文不足，回到第 47 节重新框定（补数据源或换成效）；模糊 → 补充部署记录缺失类的事故再测一次，样本加倍。
- 加分点：说明为什么不选"仪表盘原型"（只证明 operator-trust，缺 service-identification）；把"人工批准的建议先于自动执行"写成阶段门。

### Q17 — 参考回答要点

- **MVP 的模糊性**（讲义延伸阅读 Lenarduzzi & Taibi 的系统性映射研究）："minimum"和"viable"在实践中被理解成很多不同的东西：最少功能、最早可卖、最快可演示、可学习的实验……
- **本节的定义更窄、更可检验**："最小"相对于**必证集合**来衡量——能覆盖全部必证项的切片中最便宜、后果最小、最可逆的那个；"可行"由停止规则定义——它必须能改变决策。
- **产出不同**：很多 MVP 的目标是"上线"；本节切片的目标是"证据"，结论可以是停止。
- **防假最小**：本节显式列出 UI-only、infrastructure-only、happy-path、demo、platform 五种伪装成 MVP 的切片。
- 加分点：与第 53 节呼应——原型、试点、生产是不同的学习环境，不是打磨程度的不同等级。
- 常见误区：把 MVP 当成"功能少一点的正式版"。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 49 梳理假设，优先验证风险最高的一项](../../49-map-assumptions-and-risk/docs/zh.md)：本节的必证集合来自那里的最高风险开放假设。
- [阶段 14 · 48 发现人们实际执行的工作流](../../48-discover-the-real-workflow/docs/zh.md)：识别 happy-path 假最小需要知道真实的异常与交接。
- [阶段 14 · 47 先定义预期成效，再选择交付形式](../../47-outcomes-before-output/docs/zh.md)：切片失败时回到成效重新框定。

### 本节被哪些后续内容用到
- [阶段 14 · 51 编写保留判断空间的规格说明](../../51-write-specifications-that-preserve-judgment/docs/zh.md)：为选中的切片写规格（该节先修要求为本节）。
- [阶段 14 · 52 在结果产生前设计成功指标](../../52-design-success-metrics/docs/zh.md)：把停止规则中的阈值变成成功指标。
- [阶段 14 · 53 有意识地选择原型、试点或生产方案](../../53-prototype-pilot-or-production/docs/zh.md)：切片的后果等级对应原型、试点、生产三种学习环境。
- [阶段 14 · 54 建立持续反馈机制，明确负责人和退役条件](../../54-build-the-feedback-ratchet/docs/zh.md)：切片交付后的学习闭环。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)：生产中保持可逆性的发布手段。

### 延伸关键词
`vertical slice` · `walking skeleton` · `required proof set` · `eligibility gate` · `non-compensatory decision` · `false minimum` · `stop rule / kill criteria` · `MVP ambiguity` · `spiral model` · `reversibility`
