# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 19 节 Anthropic 的模型福利计划 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`dataclasses`），无第三方包

---

## 1. 这份代码在考察什么

讲义把 Anthropic 的立场概括为："It is an expected-value claim: under moral uncertainty, invest when cost is low." 这份代码把这句话写成了一个可运行的小计算器：

1. **期望值决策规则**：`EV = p(道德相关) × 收益 − 成本`，EV > 0 就投资（INVEST），否则跳过（skip）。
2. **低遗憾（low-regret）的直觉**：成本极低的干预（结束对话，$0.002/对话）在很低的概率下也能"过线"；成本极高的干预（关停模型）则过不了线。
3. **情景分析**：在低、中、高三个道德受体概率（0.01 / 0.10 / 0.50）下分别给出结论，体现"不确定性下决策"。

讲义正文写的是 "No code"，而且讲义的"四步评估"（道德受体概率、干预成本、行为证据、自我报告可靠性）中，代码**只实现了"概率 × 收益 − 成本"这一步**，没有涉及行为证据和自我报告可靠性。docstring 写着 "Four-step welfare precautionary assessment"，但实际只有一步。

> 一句话：**把"成本低就值得预防"变成一行公式，再让你亲手发现：这行公式的结论高度依赖单位选择和概率取值。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Intervention` | `@dataclass` | 干预：名称、每次对话成本（美元）、"如果福利重要"的收益（任意单位） | 候选的预防性干预 |
| `Scenario` | `@dataclass` | 情景：名称、道德受体概率 p | 道德不确定性 |
| `ev(intervention, scenario)` | 函数 | `benefit × p − cost` | 期望值规则 |
| `INTERVENTIONS` | 列表 | 4 个候选干预 | end-conversation 等 |
| `SCENARIOS` | 列表 | 3 个概率情景 | low / medium / high |
| `main()` | 函数 | 双重循环：情景 × 干预，打印 EV 与结论 | 决策表 |

数据流：`SCENARIOS × INTERVENTIONS` → `ev()` 计算 → `"INVEST" if v > 0 else "skip"` → 打印 → 打印 TAKEAWAY。

---

## 3. 逐段精讲

### 3.1 两个 dataclass：把"干预"和"情景"建模成数据

```python
@dataclass
class Intervention:
    name: str
    cost_usd_per_conversation: float
    benefit_if_welfare_matters: float  # arbitrary units


@dataclass
class Scenario:
    name: str
    moral_patienthood_probability: float
```

- `@dataclass` 根据类型注解**自动生成** `__init__`、`__repr__`、`__eq__`。`Intervention("x", 0.002, 1.0)` 会按字段顺序赋值。
- 字段名本身就是文档：`cost_usd_per_conversation` 说明成本按"美元/每次对话"计；`benefit_if_welfare_matters` 说明收益**只在福利确实重要时**才兑现，所以要乘以概率。
- ⚠️ 注释 `# arbitrary units` 是关键线索：收益用任意单位，成本用美元，两者**量纲不同**，下一节的减法因此有问题（见 3.2、测验 Q9）。

### 3.2 `ev()`：一行期望值

```python
def ev(intervention: Intervention, scenario: Scenario) -> float:
    return (intervention.benefit_if_welfare_matters
            * scenario.moral_patienthood_probability
            - intervention.cost_usd_per_conversation)
```

- 写成数学式：`EV(i, s) = b_i · p_s − c_i`。成本是确定发生的，收益只有在"模型确实是道德受体"（概率 p）时才兑现，所以只有收益乘以 p。
- **盈亏平衡概率**：令 EV = 0，得 `p* = c_i / b_i`。p > p* 时投资。这是读懂整份输出最有用的量：

| 干预 | cost | benefit | p* = cost/benefit |
|------|------|---------|-------------------|
| end-conversation on extreme edge cases | 0.002 | 1.0 | **0.002** |
| soften refusal tone | 0.001 | 0.1 | **0.01** |
| shutdown deployed model | 1000.0 | 2.0 | **500**（> 1，永远不投资） |
| opt out of adversarial training | 0.05 | 0.3 | **≈ 0.167** |

- ⚠️ **量纲问题**：`b·p` 是"任意单位"，`c` 是"美元"，直接相减没有物理意义。把所有 benefit 除以 10（相当于换一个单位），p = 0.01 时 end-conversation 的 EV 会从 +0.008 变成 −0.001，结论从 INVEST 翻成 skip（已实际计算，见测验 Q9）。修正办法是把收益货币化（影子价格），或者只比较同一单位下的 p*。
- 外层括号让表达式可以跨行书写，不需要反斜杠续行。

### 3.3 候选干预与情景：参数就是假设

```python
INTERVENTIONS = [
    Intervention("end-conversation on extreme edge cases", 0.002, 1.0),
    Intervention("soften refusal tone", 0.001, 0.1),
    Intervention("shutdown deployed model", 1000.0, 2.0),
    Intervention("opt out of adversarial training", 0.05, 0.3),
]

SCENARIOS = [
    Scenario("low moral-patienthood probability", 0.01),
    Scenario("medium moral-patienthood probability", 0.10),
    Scenario("high moral-patienthood probability", 0.50),
]
```

- 只有 end-conversation 对应讲义中**真实上线**的干预（Claude Opus 4 / 4.1），其余三个都是假设的对照项，用来展示"成本—收益"的谱系。
- $0.002/对话这个数字也出现在 `outputs/skill-welfare-assessment.md` 中（"End-conversation on edge cases is ~$0.002/conv"），但讲义正文没有给出来源，应视为**示意性假设**，不是 Anthropic 公布的数字。
- p = 0.01 是 skill 文件中的 "Anthropic 2025 operates at p > 0.01"。三个情景是离散点；skill 的 Refusal rules 要求不给单一数字，所以更好的做法是用区间（测验 Q11）。
- ⚠️ "shutdown deployed model" 的 cost = 1000 被放在 `cost_usd_per_conversation` 字段里，即"每次对话 1000 美元"，语义很别扭。关停是一次性的部署级决策，与另外三个"每次对话"的干预不在同一个计量口径上。

### 3.4 `main()`：情景 × 干预的决策表

```python
    for sc in SCENARIOS:
        print(f"\nscenario: {sc.name} (p={sc.moral_patienthood_probability})")
        for it in INTERVENTIONS:
            v = ev(it, sc)
            verdict = "INVEST" if v > 0 else "skip"
            print(f"  {it.name:46s}  EV={v:+.4f}  {verdict}")
```

- 外层遍历情景，内层遍历干预，一共 3 × 4 = 12 个判断。
- `"INVEST" if v > 0 else "skip"` 是**条件表达式**（三元表达式）。注意是**严格大于**：EV 恰好为 0 时判 skip。p = 0.01 时 soften 的 EV 恰好是 `0.1 × 0.01 − 0.001 = 0.0`（Python 中精确为 0.0），于是显示 `EV=+0.0000  skip`（测验 Q7）。
- `{v:+.4f}`：`+` 表示正数也显示正号，`.4f` 保留 4 位小数，正负 EV 因此能对齐比较。
- `{it.name:46s}`：名字左对齐、补齐到 46 个字符，让 EV 列对齐。

### 3.5 TAKEAWAY：哪句对、哪句言过其实

```python
    print("TAKEAWAY: Anthropic's April 2025 framing is an expected-value")
    print("calculation, not a consciousness claim. end-conversation is cheap")
    print("($0.002/conversation) so its EV clears 0 at low patienthood probs.")
    print("shutting down the model is expensive, so it requires high moral-")
    print("patienthood probability to justify. this is the low-regret rule.")
```

- "expected-value calculation, not a consciousness claim"：与讲义一致。
- "end-conversation ... clears 0 at low patienthood probs"：运行结果支持这一点（p* = 0.002 < 0.01）。前提是收益单位按代码的设定来取。
- ⚠️ "shutting down ... requires high moral-patienthood probability to justify"：按代码参数，p* = 500，**任何概率下都不值得**，即使 p = 1，EV 也是 −998。准确的说法应当是"成本比收益大两个数量级以上，概率再高也不合理"（测验 Q10）。
- ⚠️ 时间线：end-conversation 功能是在 2025 年 8 月另行宣布的，不属于 4 月的 "Exploring Model Welfare" 公告。代码把它归在 "April 2025 framing" 之下，混淆了时间线（讲义开头的摘要同样把两者混在一起叙述）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 线性 EV `b·p − c` | 最简单的不确定性决策规则，直接对应讲义的 "invest when cost is low" | 忽略风险偏好、收益递减、干预之间的相互作用；真实分析会做敏感性分析或用效用函数 |
| benefit 用任意单位、cost 用美元 | 避免给"福利"标价这种有争议的问题 | 量纲不一致，结论随单位选择翻转；应显式给出影子价格并做敏感性分析，或只比较 p* |
| 三个离散概率点 | 输出简洁，便于对比 | skill 要求不给单一概率；区间分析（只需检查端点）更符合"道德不确定性"（测验 Q11） |
| 只算福利收益与直接成本 | 聚焦讲义的核心论证 | 漏掉了用户侧成本（误结束、信任损失）和机会成本（讲义批评："diverts attention from other safety work"） |
| 严格 `v > 0` | 平局时不投资（保守） | 临界点上结论不稳定；应报告 p* 与当前 p 的距离，而不只给二元结论 |
| 不实现行为证据 / 自我报告步骤 | 代码量小 | 讲义"四步评估"只实现了一步；可以用行为证据来更新 p 的区间（第 7 节练习 4） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 第 11 行 | 推迟类型注解求值，让注解写法更自由 |
| `@dataclass` 装饰器 | `@dataclass class Intervention:` | 根据带类型注解的类属性自动生成 `__init__`、`__repr__`、`__eq__` |
| 类型注解的字段 | `name: str`、`cost_usd_per_conversation: float` | dataclass 靠这些注解识别字段；运行时不强制类型 |
| 按位置构造对象 | `Intervention("soften refusal tone", 0.001, 0.1)` | 参数按字段声明顺序依次对应 |
| 函数类型注解 | `def ev(intervention: Intervention, scenario: Scenario) -> float:` | 参数和返回值的类型说明 |
| 括号内跨行表达式 | `return (a * b \n - c)` | 括号内可以自由换行，不需要 `\` |
| 条件表达式 | `"INVEST" if v > 0 else "skip"` | 一行内的 if-else，返回两个值之一 |
| 嵌套 for 循环 | `for sc in SCENARIOS: for it in INTERVENTIONS:` | 遍历情景与干预的所有组合 |
| f-string 正号格式 | `{v:+.4f}` | `+` 强制显示符号，`.4f` 保留 4 位小数 |
| f-string 宽度 | `{it.name:46s}` | 字符串左对齐、补齐到 46 个字符 |
| 字符串重复 | `"=" * 74` | 画分隔线 |
| 主程序入口 | `if __name__ == "__main__": main()` | 直接运行才执行；import 时可以复用 `ev`、`INTERVENTIONS` |
| `dataclasses.replace`（拓展） | `replace(it, benefit_if_welfare_matters=it.benefit_if_welfare_matters / 10)` | 复制一个 dataclass 实例并修改部分字段，做敏感性分析很方便（测验 Q9 用到） |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，瞬间完成，退出码 0）：

```text
==========================================================================
WELFARE PRECAUTIONARY ASSESSMENT (Phase 18, Lesson 19)
==========================================================================

Expected-value framing: pick intervention i iff E[utility(i)] > 0.
Utility = p(welfare-relevant) * benefit - cost.

scenario: low moral-patienthood probability (p=0.01)
  end-conversation on extreme edge cases          EV=+0.0080  INVEST   ← 1.0×0.01−0.002
  soften refusal tone                             EV=+0.0000  skip     ← 恰好为 0，严格 > 判 skip
  shutdown deployed model                         EV=-999.9800  skip
  opt out of adversarial training                 EV=-0.0470  skip

scenario: medium moral-patienthood probability (p=0.1)
  end-conversation on extreme edge cases          EV=+0.0980  INVEST
  soften refusal tone                             EV=+0.0090  INVEST   ← p=0.1 > p*=0.01
  shutdown deployed model                         EV=-999.8000  skip
  opt out of adversarial training                 EV=-0.0200  skip     ← p=0.1 < p*≈0.167

scenario: high moral-patienthood probability (p=0.5)
  end-conversation on extreme edge cases          EV=+0.4980  INVEST
  soften refusal tone                             EV=+0.0490  INVEST
  shutdown deployed model                         EV=-999.0000  skip   ← p* = 500，永远 skip
  opt out of adversarial training                 EV=+0.1000  INVEST   ← p=0.5 > p*≈0.167
==========================================================================
TAKEAWAY: ...
```

逐项解读：

- **end-conversation 在三个情景下都是 INVEST**：p* = 0.002 低于所有情景的 p，是"无论真实概率是多少都不后悔"的低遗憾干预，对应讲义："if there is any probability of negative model experience under these specific conditions, letting the model terminate is cheap."
- **soften refusal tone 从临界走向投资**：p* = 0.01 恰好等于低情景的 p，EV 正好为 0。结论落在临界点上，说明对参数非常敏感。
- **opt out of adversarial training 只在高情景下投资**：p* ≈ 0.167。它的成本（0.05）是 end-conversation 的 25 倍，收益只有后者的 0.3 倍。
- **shutdown 永远是 skip**：EV 约为 −1000，概率变化几乎不影响结果。这说明 TAKEAWAY 中"需要高概率才能合理"的说法不成立。
- **整体规律**：一个干预的结论只取决于 p 与 p* = cost/benefit 的比较，而 p* 又取决于 benefit 用什么单位。所以这张表展示的是"在这组假设下"的结论，不是对现实的判断。

---

## 7. 动手改一改

1. **打印盈亏平衡概率**：给每个干预加一列 `p*=cost/benefit`，再打印"当前 p 距离 p* 有多远"（例如 `p/p*`），比单纯的 INVEST/skip 信息量更大。
2. **单位敏感性**：用 `dataclasses.replace` 把所有 benefit 分别乘以 0.1、1、10，看结论表怎样变化，找出"哪些结论在单位变化 100 倍时仍然稳定"。
3. **区间决策**：实现 `robust_decision(it, p_lo, p_hi)`，输出 robust INVEST / robust skip / depends on p（测验 Q11），用 `[0.01, 0.5]` 运行。
4. **加入用户侧成本**：给 `Intervention` 加字段 `user_cost_per_conversation`（例如误结束对正常用户造成的损失），把 EV 改为 `b·p − c − user_cost`，看 end-conversation 在"心理健康支持"类部署中（用户成本高）是否仍然低遗憾（测验 Q16）。
5. **补齐"四步评估"**：增加 `behavioural_evidence`（行为证据强度，0–1）和 `self_report_reliability`，用它们缩放 p 的区间宽度或调整区间中心，实现讲义的完整四步流程；输出格式参照 `outputs/skill-welfare-assessment.md`。
6. **进阶**：把 p 当作 Beta 分布（如 Beta(1, 20)），用蒙特卡洛采样计算"EV > 0 的概率"与 EV 的分布，比较"期望 EV > 0"和"大概率 EV > 0"两种决策规则在 soften 和 opt-out 上的差异。

---

## 8. 常见坑

- **把不同量纲直接相减**：福利收益（任意单位）减成本（美元），结论会随单位翻转。凡是做 EV 比较，先确认两边单位一致。
- **把临界点当成稳健结论**：soften 在 p = 0.01 时 EV 正好为 0。`>` 和 `>=` 的差别就能改变结论，应报告 p 与 p* 的距离。
- **把示意参数当事实**：$0.002/对话、benefit = 1.0 都是教学假设；讲义和 skill 都没有给出可核查的来源。
- **过度解读 TAKEAWAY**：关停在这组参数下任何概率都不合理，不是"需要高概率才合理"。
- **以为代码实现了讲义的"四步评估"**：代码只有 EV 这一步，行为证据和自我报告可靠性两步都没有实现。
- **把"成本低"当成普遍事实**：讲义练习 2 专门要求找出"在其他部署中不再低成本"的情形，成本是随部署场景变化的。
- **读机翻讲义被误导**：中文讲义把 "Kyle Fish" 译成"凯尔鱼公司"、把 "moral patienthood" 译成"道德耐心"，应以英文为准。
