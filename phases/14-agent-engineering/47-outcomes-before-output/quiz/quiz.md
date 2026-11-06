# 测验 · 先定义预期成效，再选择交付形式（Define the Outcome Before You Choose the Output）

> **阶段 14 · Agent 工程 · 第 47 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 速度放大方向错误的代价 | 讲义："Fast implementation increases the penalty for choosing the wrong problem"——agent 能同样快地实现清楚和不清楚的任务 |
| 2 | Output ≠ Outcome | "做一个事故助手"是产出（output）；"值班工程师在两分钟内找到故障服务和安全的下一步，诊断全程只读、可审计"是成效（outcome） |
| 3 | 成效可被多种产出满足 | 同一个成效可以由软件、runbook、数据修复或一个更小的界面改动满足，让团队绑定结果而不是第一个想到的工件 |
| 4 | 六部分框架 | User（谁直接受影响）、Situation（何时何地）、Current behavior（今天怎么做，含变通办法）、Desired outcome（哪个可观察状态改善）、Constraints（固定的安全/政策/成本/兼容限制）、Non-goals（排除哪些诱人的相邻工作） |
| 5 | 方案泄漏（solution leakage） | 成效描述里出现了**未经证据支持**的产品形式、界面、模型选择、框架或架构，例如"每周 AI 摘要""部署向量数据库" |
| 6 | 技术可以出现在约束里 | 当兼容性**确实**把某项技术固定下来时，约束可以点名它，但要记录为什么固定 |
| 7 | 约束是成效的一部分 | 讲义："A build that reaches the outcome by violating a constraint has not reached the outcome." |
| 8 | Non-goals 划定边界 | 好的 non-goal 足够具体，能用来**拒绝**工作：不做自动修复、不建新告警路由、不取代事故指挥官、本切片不做历史分析 |
| 9 | 代码的校验逻辑 | 四个文本字段非空、constraints/non-goals 非空列表、`proposed_output` 是否作为子串出现在 `desired_outcome` 中 |
| 10 | 代码的局限 | 泄漏检测只是"整串子串匹配"：改个说法就漏检；空白字符串会被误判；不检查约束中的技术是否附带理由 |

### 核心技能（能动手做到）

- [ ] 把一个 backlog 里的功能请求改写成六部分 outcome frame，且成效句中不点名任何方案
- [ ] 一眼判断一句话是 output 还是 outcome，并能指出泄漏的是"形式、界面、模型、框架还是架构"
- [ ] 写出至少两条能**改变可选方案集合**的约束和两条能让切片保持小的 non-goal
- [ ] 读懂 `validate` / `decision`，能预测任意修改后的 frame 得到的 status 与 issues
- [ ] 指出并修复代码中泄漏检测与空白输入的缺陷
- [ ] 为成效写出"最早能证伪它的观察"（讲义练习 4），并写出三种能满足同一成效的不同产出（练习 5）

---

## 二、基础自测（选择题）

**Q1.** 下面哪一句是 outcome（成效），而不是 output（产出）？

- A. 构建一个事故助手（incident assistant）
- B. 部署一个向量数据库
- C. 当生产告警到达时，值班工程师在两分钟内确定故障服务和安全的下一步，且诊断全程只读、可审计
- D. 用户每周收到一份 AI 摘要

**Q2.** 六部分框架中，"今天发生了什么，包括人们的变通办法？"对应的是哪一部分？

- A. Current behavior
- B. Situation
- C. Desired outcome
- D. Non-goals

**Q3.** 在本节代码中，把示例的 `desired_outcome` 改为 `"engineers use an AI incident helper"`（`proposed_output` 仍为 `"incident assistant"`），`validate` 返回：

- A. `["desired outcome names the proposed output"]`
- B. `["solution leakage detected"]`
- C. 抛出 `ValueError`
- D. `[]`

**Q4.** 关于约束（constraints）中能否点名具体技术，讲义的立场是：

- A. 永远不能，任何技术名词都算方案泄漏
- B. 当兼容性确实把它固定下来时可以，但要记录为什么它是固定的
- C. 只要团队偏好某种技术就可以写进去
- D. 只能写在 non-goals 里

**Q5.** 把示例的 `proposed_output` 设为一个空格 `" "`，其余不变，`validate` 返回：

- A. `["desired outcome names the proposed output"]`
- B. `[]`
- C. `["proposed_output is empty"]`
- D. 抛出 `AttributeError`

**Q6.** 下面哪一条是讲义意义上"好的 non-goal"？

- A. 保持代码质量
- B. 让用户满意
- C. 以后可能会做的所有事情
- D. 不做自动修复（no automatic remediation）

**Q7.** 一个实现确实让工程师在两分钟内定位了故障服务，但它在诊断阶段向生产环境写入了数据。按讲义：

- A. 已达成成效，写入只是实现细节
- B. 部分达成，把写入记为技术债即可
- C. 没有达成成效，因为约束是成效的一部分
- D. 已达成成效，约束只是可选的建议

**Q8.** 把示例的 `constraints` 改为 `["  "]`、`non_goals` 改为 `[""]`，`decision(...)["status"]` 是：

- A. `"needs-framing"`，issues 中有两条
- B. `"ready-to-discover"`
- C. 抛出异常
- D. `"needs-framing"`，issues 中有一条

---

## 三、动手 / 代码题

**Q9.**（改进泄漏检测）代码的泄漏检测只有一行：

```python
    if frame.proposed_output and frame.proposed_output.lower() in frame.desired_outcome.lower():
        issues.append("desired outcome names the proposed output")
```

1. 讲义列举了 4 句话（"weekly AI summary""understand account changes before approval""Deploy a vector database""policy evidence is available during review"）。在示例 frame 中依次把它们放进 `desired_outcome`，当前代码各报几处泄漏？哪些是漏报？
2. 写一个 `find_leakage(frame) -> list[str]`：除了检查 `proposed_output`，还要检查一组"方案形式"词汇（如 assistant、dashboard、summary、vector database、model、agent），并用单词边界避免子串误判。

**Q10.**（找 bug：空白与非字符串输入）运行结果如下：

| 修改 | `validate` 结果 |
|------|----------------|
| `proposed_output = " "` | `["desired outcome names the proposed output"]` |
| `constraints = ["  "]`, `non_goals = [""]` | `[]` |
| `user = None` | 抛出 `AttributeError: 'NoneType' object has no attribute 'strip'` |
| `user = "   "` 时 `next_question` | `"...achieved for the    ?"` |

1. 解释每一行的成因。
2. 给出修复后的 `validate`，使前三行分别得到 `[]`、`["constraints are empty", "non-goals are empty"]`、`["user is empty"]`。

**Q11.**（讲义练习 4 + mermaid 最后一步）讲义的流程图以 "Evidence question" 结束，练习 4 要求"找出最早能证伪预期成效的观察"。请给 `OutcomeFrame` 增加 `disproof_signal` 字段，并在 `validate` 中要求它非空。

1. 新字段应该放在 dataclass 的哪个位置？为什么？
2. 只改 dataclass 和 `validate`、不改其它代码时，现有 6 个测试会怎样？还需要改什么？
3. 为示例写一个合格的 `disproof_signal`。

**Q12.**（预测输出）对示例 frame 分别做以下修改，写出 `decision(frame)` 的 `status` 和 `issues`（注意 issues 的顺序）：

- (a) `desired_outcome = "Use the Incident Assistant"`
- (b) `user = ""` 且 `constraints = []`
- (c) `proposed_output = ""` 且 `desired_outcome = "Deploy a vector database"`
- (d) `desired_outcome = "incident assistant answers within two minutes"` 且 `non_goals = []`
- (e) `non_goals` 追加一项 `"the incident assistant"`

---

## 四、面试高频题

**Q13.**（基础必考）什么是 output 与 outcome 的区别？请举一个把 output 改写成 outcome 的例子。

**Q14.**（原理深挖）为什么 AI coding agent 让"先定义成效"变得**更**重要，而不是更不重要？

**Q15.**（工程实践）你要在团队的需求评审流程里自动检测"方案泄漏"，会怎么设计？规则、LLM、人工各负责什么？

**Q16.**（场景设计）产品经理说："我们需要给客服做一个 RAG 聊天机器人。"请你用六部分框架把它重新框定，并说明你会如何收集信息。

**Q17.**（追问型）Constraints 和 non-goals 有什么区别？为什么说"违反约束达成的成效不算达成"？

---

## 五、参考答案与解析

### Q1 — 答案：C

C 说明了谁（值班工程师）、什么情况（告警到达）、可观察的改善（两分钟内找到服务和下一步）和约束（只读、可审计），且没有指定任何产物——可以用软件、runbook 或界面改动来满足。A 是产出；B 泄漏了基础设施；D 泄漏了"摘要"这一形式和"每周"这一节奏（讲义原例）。

### Q2 — 答案：A

讲义表格："Current behavior — What happens today, including workarounds?"。B 问的是"何时何地发生"；C 问"哪个可观察状态应改善"；D 问"排除哪些诱人的相邻工作"。示例代码中 current_behavior 是 "searches three dashboards before finding the affected service"。

### Q3 — 答案：D

`validate` 只检查 `"incident assistant"` 这个**整串**是否出现在 `desired_outcome` 中。`"engineers use an AI incident helper"` 不包含这个子串，所以返回 `[]`（已实际运行验证），status 为 `ready-to-discover`。这是一次典型漏报：换个说法（"helper"）方案就溜进了成效。A 是"应该"的结果但不是实际结果；B 这个字符串在代码中根本不存在；C 代码中没有抛异常的路径。

### Q4 — 答案：B

讲义："Constraints can name technology when compatibility truly fixes it. Record why it is fixed." 例如"必须继续使用现有审计事件作为权威来源"是合理约束。A 过于绝对；C 把偏好伪装成约束，正是方案泄漏的变体；D 混淆了 non-goal 与 constraint。

### Q5 — 答案：A

`" "` 是非空字符串，在 `if` 中为真；`" ".lower()` 仍是 `" "`，而任何含空格的句子都包含它，于是被判为泄漏（已实际运行验证）。这是一个误报 bug：应先 `.strip()` 再判断。B 是修复后的期望结果；C 代码没有这条检查；D 不会发生，`" "` 是字符串。

### Q6 — 答案：D

讲义："Good non-goals are concrete enough to reject work"，并给出 "no automatic remediation" 作为例子。A、B 太抽象，无法用来拒绝任何具体工作；C 是"未来愿望清单"，不是本切片的边界。

### Q7 — 答案：C

讲义 "Constraints Protect the Outcome"："A build that reaches the outcome by violating a constraint has not reached the outcome." 示例约束第一条就是 "read-only during diagnosis"。A、D 把约束当成可选的实现细节；B 用"技术债"掩盖了一次真实的安全违规。

### Q8 — 答案：B

`if not frame.constraints` 只判断列表是否为空。`["  "]` 和 `[""]` 都是长度为 1 的非空列表，所以两项检查都通过，status 为 `ready-to-discover`（已实际运行验证）。这是 Q10 要修的 bug 之一。A 是修复后的期望结果。

### Q9 — 参考答案

1. 实际运行结果：四句话放进 `desired_outcome` 后，当前代码**都**返回 `[]`。其中 "weekly AI summary" 和 "Deploy a vector database" 是讲义明确指出的泄漏，属于**漏报**；另外两句本来就是成效，不报是对的。原因是代码只认识 `proposed_output` 这一个字符串，对讲义列出的五类泄漏（产品形式、界面、模型选择、框架、架构）没有任何识别。

2. 参考实现：

```python
import re

SOLUTION_FORMS = ("assistant", "helper", "chatbot", "bot", "dashboard", "summary",
                  "vector database", "database", "model", "llm", "agent", "plugin", "app")

def find_leakage(frame: OutcomeFrame) -> list[str]:
    text = frame.desired_outcome.lower()
    hits: list[str] = []
    proposed = frame.proposed_output.strip().lower()
    if proposed and proposed in text:
        hits.append(f"names the proposed output '{proposed}'")
    for form in SOLUTION_FORMS:
        if re.search(rf"\b{re.escape(form)}\b", text):
            hits.append(f"names a solution form '{form}'")
    return hits
```

实际运行：

| desired_outcome | 原代码 | `find_leakage` |
|------|------|------|
| Users receive a weekly AI summary | `[]` | summary |
| Users understand account changes before approval | `[]` | `[]` |
| Deploy a vector database | `[]` | vector database、database |
| Relevant policy evidence is available during review | `[]` | `[]` |
| 示例原文（identifies the failing service...） | `[]` | `[]` |
| engineers use an AI incident helper | `[]` | helper |
| Use the Incident-Assistant | `[]` | assistant |

要点：`re.escape` 防止词汇里的特殊字符破坏正则；`\b` 避免 "app" 匹配到 "approval"。词表法仍然只是启发式：它会误报（例如成效本身就是"模型评估报告按时交付"）也会漏报（新造的产品名）。实践中应把命中当作"需要人确认"的提示，而不是直接判失败。

### Q10 — 参考答案

1. 成因：
   - `" "`：非空字符串为真，且空格是任何多词句子的子串 → 误报泄漏。
   - `["  "]`、`[""]`：`not list` 只看列表长度，不看元素内容。
   - `None`：`getattr(frame, "user").strip()` 对 `None` 调用 `.strip()`；dataclass 的类型注解 `user: str` **不会**在运行时阻止传入 `None`。
   - `next_question` 直接把 `frame.user` 拼进模板，不论 frame 是否通过校验；即使 status 是 `needs-framing`，也会生成"for the    ?"这样的问题。

2. 参考实现（已实际运行验证三行分别得到 `[]`、`["constraints are empty", "non-goals are empty"]`、`["user is empty"]`，示例仍为 `[]`）：

```python
def validate(frame: OutcomeFrame) -> list[str]:
    issues: list[str] = []
    for name in ("user", "situation", "current_behavior", "desired_outcome"):
        value = getattr(frame, name)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"{name} is empty")
    if not [c for c in frame.constraints if c.strip()]:
        issues.append("constraints are empty")
    if not [n for n in frame.non_goals if n.strip()]:
        issues.append("non-goals are empty")
    proposed = frame.proposed_output.strip().lower()
    if proposed and proposed in frame.desired_outcome.lower():
        issues.append("desired outcome names the proposed output")
    return issues
```

注意：如果 `desired_outcome` 是 `None`，最后一行仍会出错——更彻底的做法是在 `__post_init__` 里统一做类型检查，或在第一轮检查失败时提前返回。`decision` 中也应在 status 为 `needs-framing` 时不生成 `next_question`，或把它设为 `None`。

### Q11 — 参考答案

1. 放在 `proposed_output` **之后**，写成 `disproof_signal: str = ""`。dataclass 规定：有默认值的字段之后不能再出现没有默认值的字段，否则在类定义时就会报 `TypeError: non-default argument ... follows default argument`。`proposed_output` 已经有默认值，所以新字段也必须带默认值且放在后面。

2. 在 `validate` 末尾加：

```python
    if not frame.disproof_signal.strip():
        issues.append("disproof signal is empty")
```

只改这两处时，`test_example_is_ready` 会**失败**（示例没有 disproof_signal，status 变为 `needs-framing`），其余 5 个测试仍通过——已用副本实际运行验证：`Ran 6 tests ... FAILED (failures=1)`。还需要更新 `example()`，为它补上 disproof_signal；补上后 6 个测试全部通过。这说明测试把"示例是合格的 frame"当作了契约，改变"合格"的定义时必须同步更新示例。

3. 示例：`"in a replay of ten real alerts, median time to identify the failing service stays above two minutes"`。好的证伪信号要满足：可观察（时间可以测）、有阈值（两分钟）、样本真实（真实告警的回放）、可以尽早获得（不必上线就能测）。随后可以把 `next_question` 改为引用这个信号，例如 "What is the cheapest way to observe: <disproof_signal>?"。

### Q12 — 参考答案

（全部已实际运行验证。）

| 情况 | status | issues |
|------|--------|--------|
| (a) | `needs-framing` | `["desired outcome names the proposed output"]`——比较前两边都 `.lower()`，大小写不影响 |
| (b) | `needs-framing` | `["user is empty", "constraints are empty"]`——先检查四个文本字段，再检查列表 |
| (c) | `ready-to-discover` | `[]`——`proposed_output` 为空时跳过泄漏检查，"vector database"这种讲义明确列出的泄漏完全漏报 |
| (d) | `needs-framing` | `["non-goals are empty", "desired outcome names the proposed output"]`——non-goals 检查排在泄漏检查之前 |
| (e) | `ready-to-discover` | `[]`——代码不检查 non-goals 与 proposed_output 之间的矛盾（把要做的东西列为不做的东西） |

issues 的顺序完全由 `validate` 中各个 `if` 的书写顺序决定：四个文本字段（按 `user, situation, current_behavior, desired_outcome`）→ constraints → non-goals → 泄漏。

### Q13 — 参考回答要点

- **Output**：交付的工件（一个助手、一个仪表盘、一个功能）。**Outcome**：在某个用户、某个情境下，可以被观察到的状态改善，并带有必须保持的约束。
- **例子**：output "给值班工程师做一个事故助手" → outcome "告警到达时，值班工程师在两分钟内定位故障服务和安全的下一步，诊断全程只读、可审计"。
- **为什么重要**：outcome 允许多种产出（软件、runbook、数据修复、界面小改动），团队绑定的是结果而不是第一个想到的工件。
- 加分点：能说出六部分框架，并指出 outcome 句里的"两分钟"让成功可以被测量。
- 常见误区：把"上线某功能"当作成效；把"用户满意"这种无法观察的东西当作成效。

### Q14 — 参考回答要点

- 讲义开篇："A coding agent can implement a clear task quickly. It can also implement an unclear task quickly. The speed is the same. The cost is not."（第 43 节），本节进一步指出："Fast implementation increases the penalty for choosing the wrong problem."
- **机制**：实现变便宜后，团队会更快地对第一个想法投入代码、数据结构、集成和用户预期；"学到方向错了"的时间点没有提前，但在错误方向上积累的工件变多了，回头成本更高。
- **沉没成本与锚定**：已经有一个能跑的"助手"后，讨论会自然围绕"怎么改进助手"，而不是"助手是否是正确的产出"。
- **对策**：先写 outcome frame 和 non-goals，再让 agent 动手；用约束提前排除不安全的方案。
- 加分点：把 outcome frame 作为 agent 任务的输入工件（outputs/outcome-frame.json），让后续第 48–50 节的发现、假设和切片都以它为锚。

### Q15 — 参考回答要点

- **规则层**：方案形式词表（assistant、dashboard、chatbot、vector database、具体模型名、框架名）+ 单词边界匹配；检查 proposed_output 及其同义词；规则只负责"提示"，不直接拒绝。
- **LLM 层**：让模型判断一句话"是否点名了产品形式、界面、模型、框架或架构"，并说明理由；同时要求它改写成不含方案的版本，供人对比。
- **人工层**：判断技术名词是否是**有证据的约束**（兼容性确实固定），并要求写下理由；处理规则和 LLM 的分歧。
- **度量**：在评审过的历史需求上标注一批样本，统计漏报/误报率，调整词表与提示。
- 加分点：区分"成效句中出现技术名词"（通常是泄漏）与"约束中出现技术名词并附理由"（可以接受）。
- 常见误区：只做子串匹配（本节代码的问题），或让 LLM 直接一票否决。

### Q16 — 参考回答要点

- **先不接受方案**：把"RAG 聊天机器人"记为 proposed_output，然后问六个问题。
- **User**：一线客服？还是终端客户？两者成效完全不同。
- **Situation**：客服在处理哪类工单时卡住？高峰期？新人？
- **Current behavior**：现在怎么找答案——翻知识库、问老员工、群里问？有什么变通办法？（这需要第 48 节的观察与证据。）
- **Desired outcome**：例如"新入职客服在处理退款类工单时，在 3 分钟内找到正确的政策条款并给出符合政策的答复"。
- **Constraints**：不得对客户承诺政策之外的赔偿；回答必须引用现行政策版本；不新增运行时依赖等。
- **Non-goals**：不直接面向终端客户自动回复；本切片不覆盖所有工单类型；不重建知识库。
- 然后列出三种可能产出：改进知识库搜索、给退款工单加一张决策表、才是 RAG 助手——用证据选择。
- 加分点：写出最早的证伪信号，如"在 20 个真实退款工单回放中，找到条款的时间没有缩短"。

### Q17 — 参考回答要点

- **Constraints**：成效必须在什么限制内达成——安全、政策、成本、兼容性等**固定**条件，如"诊断期间只读""现有审计事件保持权威"。它限制**怎么做**。
- **Non-goals**：本次**不做什么**——诱人但被排除的相邻工作，如"不做自动修复""不建新告警路由"。它限制**做多少**。
- **为什么违反约束不算达成**：约束本身就是现实世界目标的一部分。两分钟定位故障但向生产写入了数据，等于用一次新的风险换来了速度，组织真正要的"安全地更快"并没有实现。
- 加分点：约束可以合法地点名技术（需附理由），non-goal 可以随着切片推进被重新纳入范围，但约束的放宽需要更高层级的决策。
- 常见误区：把约束当成"实现建议"，在压力下就放弃。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 43 在 Agent 编写代码前界定任务](../../43-frame-the-task-before-code/docs/zh.md)：任务级的框定方法，本节把它提升到"成效"层面。
- [阶段 14 · 36 Scope Contracts 与任务边界](../../36-scope-contracts/docs/zh.md)：non-goals 与 scope 合同都是在划边界。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：先确认需求再决定是否需要 agent，与"先成效后产出"同一思路。

### 本节被哪些后续内容用到
- [阶段 14 · 48 发现人们实际执行的工作流](../../48-discover-the-real-workflow/docs/zh.md)：用观察与证据检验本节 frame 中的 current behavior。
- [阶段 14 · 49 梳理假设，优先验证风险最高的一项](../../49-map-assumptions-and-risk/docs/zh.md)：把成效拆成必须为真的假设。
- [阶段 14 · 50 选择足以改变决策的最小实现范围](../../50-choose-the-smallest-testable-slice/docs/zh.md)：在约束与 non-goals 内选最小切片。
- [阶段 14 · 52 在结果产生前设计成功指标](../../52-design-success-metrics/docs/zh.md)：把"desired outcome"变成可测量的指标（该节先修要求包含本节）。
- [阶段 17 · 23 AI 的 SRE：多 Agent Incident Response、操作手册与预测性检测](../../../17-infrastructure-and-production/23-sre-for-ai/docs/zh.md)：本节示例场景（事故诊断、只读、人工批准修复）在生产中的真实形态。

### 延伸关键词
`outcome vs output` · `outcome frame` · `solution leakage` · `non-goals` · `constraints` · `goal-oriented requirements engineering` · `KAOS` · `jobs to be done` · `falsifiable outcome` · `disproof signal`
