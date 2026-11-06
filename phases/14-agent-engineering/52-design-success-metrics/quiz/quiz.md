# 测验 · 在结果产生前设计成功指标（Design Success Metrics Before the Result Exists）

> **阶段 14 · Agent 工程 · 第 52 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

> 说明：本节中文讲义是机器翻译，有多处误译（如 counter-metric 译成"反计数 / 反比 / 反措施"，alert dismissal 译成"警示解雇"，pilot 译成"飞行员"，window 译成"窗户"，pass 译成"通行证"）。本测验以英文原文为准：counter-metric = 反向指标，guardrail = 护栏指标，pilot = 试点，window = 观测窗口。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 测量服务于决策 | 讲义："Measurement should answer a decision, not decorate a dashboard."——不能改变决策的指标应删除 |
| 2 | GQM（Goal–Question–Metric） | 先写目标，再派生问题，最后选能回答问题的最少指标；顺序不能反过来从"手头有什么数据"出发 |
| 3 | 指标契约 | 每个指标要有 name、direction（at most / at least）、threshold、window、source、population、kind |
| 4 | 缺字段的后果 | 没有 source 和 window → 数字无法复现；没有 threshold → 无法驱动决策 |
| 5 | 三类指标 | outcome（期望状态是否改善）、guardrail（固定约束是否仍成立）、counter-metric（局部改进是否把成本或伤害转移到别处） |
| 6 | 速度不够 | 事故场景中要同时守住正确率、生产写入、操作员工作量、漏报，防止"快但不安全" |
| 7 | 离线 vs 在线证据 | offline replay 可重复、能覆盖边界；bounded pilot 才能观察真实行为、信任与工作流影响；二者不能互相替代 |
| 8 | 用最便宜的证据 | 用能回答当前决策的最便宜证据；不要仅仅因为"实现好了"就暴露真实用户 |
| 9 | 先决定再测量 | 看到结果之前写好 pass / fail / ambiguous 三条路径，否则团队会移动阈值来保护已建成的东西 |
| 10 | 代码实现的边界 | `validate` 要求至少一个 outcome 和一个 guardrail；`evaluate` 阈值**包含等号**；`report` 记录缺失值，但不给出 pass/fail/ambiguous 的总体结论 |

### 核心技能（能动手做到）

- [ ] 从一个结果目标派生 3 个以上问题，再为每个问题选出可操作的指标
- [ ] 为每个指标写完整契约：方向、阈值、窗口、来源、人群、类型
- [ ] 为一个 outcome 指标配一个 guardrail 和一个 counter-metric，并解释各自防的是什么
- [ ] 在看到数据之前写出 pass / fail / ambiguous 判定规则，并用代码实现
- [ ] 读懂 `validate / evaluate / report`，指出浮点边界、类型拼写、重复名称、缺少总体结论等问题
- [ ] 判断一个决策需要 offline replay 还是 bounded pilot 的证据

---

## 二、基础自测（选择题）

**Q1.** 按 GQM 方法，设计度量的正确顺序是：

- A. Goal → Question → Metric
- B. Metric → Question → Goal
- C. Dashboard → Metric → Goal
- D. Data → Metric → Question

**Q2.** 事故诊断工作流的目标是"更快识别受影响服务"。讲义建议同时追踪"告警被直接忽略的比例"和"操作员工作量"。这类指标属于：

- A. Outcome metric
- B. Guardrail metric
- C. Counter-metric
- D. 仅用于展示的 vanity metric

**Q3.** 用本节代码评估 `correct_service_rate`（方向 `at-least`，阈值 `0.9`），传入的值是 `0.7 + 0.2`。`evaluate` 返回：

- A. `True`，因为 0.7 + 0.2 等于 0.9
- B. 抛出 `ValueError`
- C. `"missing"`
- D. `False`，因为 `0.7 + 0.2` 在浮点中等于 `0.8999999999999999`

**Q4.** 用示例计划调用 `report`，传入 `{"median_identification_seconds": 94, "correct_service_rate": 0.9, "production_writes": 1}`。返回结果中：

- A. `status` 为 `"fail"`，因为发生了生产写入
- B. `status` 仍为 `"valid"`，第三项为 `{"name": "production_writes", "value": 1, "passed": false}`
- C. `status` 为 `"invalid"`，`issues` 中出现 `production_writes failed`
- D. 抛出 `ValueError`

**Q5.** 为什么讲义坚持"在看到结果之前"定义阈值与判定路径？

- A. 为了减少存储空间
- B. 为了保证一定能通过
- C. 防止团队事后移动阈值来保护已经做出来的东西
- D. 因为阈值必须由仪表盘自动生成

**Q6.** 按讲义 Build It 删除示例计划中的 guardrail 指标后，`report`（其余两个值照常传入）的结果是：

- A. `status: "invalid"`，`issues: ["guardrail metric is missing"]`，但两个 outcome 指标仍被评估为 `passed: true`
- B. `status: "valid"`，因为两个 outcome 指标都通过了
- C. 两个 outcome 指标的结果都变成 `"missing"`
- D. 抛出 `KeyError`

**Q7.** 讲义"A Metric Needs a Contract"表格列出了 7 个字段。本节代码的 `Metric` dataclass 缺少哪一个？

- A. direction
- B. window
- C. source
- D. population

**Q8.** 下列哪种情况下，offline replay 的证据**不足以**支撑决策？

- A. 需要验证解析器在 50 种告警格式上的正确率
- B. 决策依赖于工程师是否信任推荐结果、是否改变了实际处理流程
- C. 需要可重复地复现某个历史边界案例
- D. 需要在发布前低成本地比较两个检索策略

---

## 三、动手 / 代码题

**Q9.** 讲义"Decide Before You Measure"给出了三条判定路径：

- pass：正确率 ≥ 0.9 且中位耗时 ≤ 120 秒；
- fail：任何生产写入，或正确率 < 0.75；
- ambiguous：小幅改进但方差大，需要更大的 replay 集。

本节 `report` 只给出逐项 `passed`，没有总体结论。请写一个 `decide(values) -> str`，返回 `"pass" / "fail" / "ambiguous"`，并说明以下输入分别得到什么：

| # | median | correct_rate | writes |
|---|--------|--------------|--------|
| a | 94 | 0.9 | 0 |
| b | 94 | 0.9 | 1 |
| c | 94 | 0.7 | 0 |
| d | 150 | 0.95 | 0 |
| e | 94 | 0.9 | （缺失） |

**Q10.** 阅读 `validate`：

```python
    kinds = {metric.kind for metric in plan.metrics}
    if "outcome" not in kinds:
        issues.append("outcome metric is missing")
    if "guardrail" not in kinds:
        issues.append("guardrail metric is missing")
    for metric in plan.metrics:
        if metric.direction not in {"at-most", "at-least"}:
            issues.append(f"{metric.name} has invalid direction")
        if not metric.source.strip() or not metric.window.strip():
            issues.append(f"{metric.name} lacks source or window")
```

找出至少三类能通过校验、但会导致错误决策的计划，并给出修复代码。

**Q11.** 示例中 `correct_service_rate` 的窗口是"ten incident replays"，阈值是 0.9。

1. 10 次 replay 时，正确率可能取哪些值？"≥ 0.9"实际意味着什么？
2. 9/10 正确时，95% Wilson 置信区间大约是多少？这对讲义的"ambiguous"路径意味着什么？
3. Q3 的浮点问题在真实系统中如何避免？

**Q12.** 讲义练习 2 与练习 3：给计划加上 counter-metric 和 population。

1. 修改 `Metric` 与 `validate`，支持 `kind="counter"` 与 `population` 字段，并要求每个计划至少有一个 counter-metric。
2. 为事故诊断场景设计一个 counter-metric，写出它完整的契约。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 GQM？请用"上线一个 AI 客服 agent"举例，从目标推导到指标。

**Q14.**（原理深挖）outcome metric、guardrail metric、counter-metric 的区别是什么？为什么只盯一个 outcome 指标很危险？

**Q15.**（工程实践）你的 agent 在 10 次离线 replay 中正确率正好 90%，达到了阈值。你会直接推进到试点吗？还需要什么？

**Q16.**（场景设计）为一个"自动生成 PR 描述"的 coding agent 设计度量方案：目标、问题、指标（含方向、阈值、窗口、来源、人群、类型）与判定规则。

**Q17.**（追问型）上线后发现指标没达标，产品经理提议"把阈值从 0.9 调到 0.85，反正差不多"。你怎么回应？什么情况下调整阈值是合理的？

---

## 五、参考答案与解析

### Q1 — 答案：A

GQM：目标定义信息需求，问题把需求细化，指标把答案操作化。讲义："Start with the goal, derive questions, then choose the smallest metrics that answer them."

- B 是逆向推导，会产生"先有数字再找理由"。
- C 是"装饰仪表盘"，讲义明确反对。
- D 从手头数据出发，容易选到"容易收集但不能改变决策"的指标（讲义练习 5 要求删除这类指标）。

### Q2 — 答案：C

讲义定义 counter-metric："did the local improvement shift cost or harm elsewhere?" 识别速度提升了，但如果工程师因此忽略更多告警、或花更多时间核对推荐，成本就被转移到了操作员身上。

- A 错：outcome 是目标本身（识别耗时、正确率）。
- B 错：guardrail 守的是固定约束（如生产写入 = 0）。两者的区别：guardrail 有一条不可越过的硬线；counter-metric 监视成本是否转移，往往与基线比较。
- D 错：它直接影响是否继续推进，不是装饰。

### Q3 — 答案：D

实测：`0.7 + 0.2 == 0.8999999999999999`，`0.8999999999999999 >= 0.9` 为 `False`。数学上相等，浮点中却差了一个最小单位。`evaluate` 用的是严格的 `>=`，没有容差。

- A 错：浮点二进制无法精确表示 0.7、0.2、0.9。
- B 错：只有 direction 非法时才抛 `ValueError`。
- C 错：值存在，不会是 missing。

避免方法见 Q11。

### Q4 — 答案：B

`report` 中的 `status` 来自 `validate(plan)`——它只说明**计划**是否合法，与观测值无关。实测输出 `status: "valid"`，三个结果的 `passed` 依次为 `True, True, False`。讲义的 fail 规则是"any production write"，但代码没有把逐项结果汇总成决策，需要读者自己实现（Q9）。

- A 错：代码中不存在 `"fail"` 状态。
- C 错：`issues` 只包含计划层面的问题。
- D 错：方向合法时 `evaluate` 不会抛错。

### Q5 — 答案：C

讲义："Write the pass, fail, and ambiguous paths before seeing results. Otherwise the team will move the threshold to protect the build." 这是对"事后合理化"的防范，与科研中的预注册（pre-registration）同理。

- A、D 与题意无关。
- B 恰恰相反：预先承诺的阈值可能导致失败，这正是它有价值的原因。

### Q6 — 答案：A

实测：`status: "invalid"`，`issues: ['guardrail metric is missing']`，`results` 中两个 outcome 指标仍是 `passed: True`。讲义要你观察的正是这一点："the plan becomes invalid even when the outcome metrics remain"——没有 guardrail 的计划，即使 outcome 全部达标也不能作为决策依据。

- B 错：`validate` 会报出缺少 guardrail。
- C 错：值都传入了，不会是 missing。
- D 错：代码用 `in` 判断键是否存在，不会 `KeyError`。

### Q7 — 答案：D

讲义表格：Name、Direction、Threshold、Window、Source、**Population**、Kind。代码的 `Metric` 只有 `name, direction, threshold, window, source, kind`，缺 population（人群，例如"试点中的 on-call 工程师"）。没有 population，同一个指标在不同人群上的数字无法比较。另外，讲义写 direction 为"at most"，代码用连字符 `"at-most"`。

### Q8 — 答案：B

讲义："Offline replay is useful for repeatability and edge coverage. A bounded pilot is useful for real behavior, trust, and workflow effects. Neither substitutes for the other." 信任与工作流变化只能在真实人群中观察。

- A、C、D 都是 replay 的强项：可重复、覆盖边界、成本低。

### Q9 — 参考答案

参考实现（已运行验证，结果见下表）：

```python
def decide(values: dict[str, float]) -> str:
    writes = values.get("production_writes")
    rate = values.get("correct_service_rate")
    median = values.get("median_identification_seconds")
    # 1) fail 优先：任何一条硬性失败条件触发就失败
    if writes is not None and writes > 0:
        return "fail"
    if rate is not None and rate < 0.75:
        return "fail"
    # 2) 证据不全不能判定为 pass
    if None in (writes, rate, median):
        return "ambiguous"
    # 3) 全部达标才 pass
    if rate >= 0.9 and median <= 120:
        return "pass"
    return "ambiguous"
```

| # | 输入 | 结果 | 原因 |
|---|------|------|------|
| a | 94 / 0.9 / 0 | pass | 两个 outcome 达标，guardrail 守住 |
| b | 94 / 0.9 / 1 | fail | 任何生产写入即失败，与 outcome 好坏无关 |
| c | 94 / 0.7 / 0 | fail | 正确率低于 0.75 |
| d | 150 / 0.95 / 0 | ambiguous | 讲义的三条规则没有覆盖"准但慢"，默认落入 ambiguous |
| e | 94 / 0.9 / 缺失 | ambiguous | guardrail 没有证据，不能当作 0 |

要点：
- **fail 先于 pass 判断**，guardrail 一票否决。
- **缺失值不能默认为通过**；尤其是 guardrail 缺失，应视为"没证据"。
- 例 d 暴露了讲义规则的空隙：应在事前就写明"准但慢"怎么处理（例如 median 在 120–180 秒为 ambiguous，超过 180 秒为 fail），而不是事后再决定。

### Q10 — 参考答案

已实测可通过校验的问题计划：

| 问题 | 复现 | 后果 |
|------|------|------|
| kind 拼写错误 | 再加一个 `kind="outcom"` 的指标 | 校验通过，该指标不被当成 outcome，也没有任何提示 |
| 不认识 counter-metric | `kind="counter"` 被静默接受 | 讲义的第三类指标没有被强制要求 |
| 重复名称 | 再加一个同名 `median_identification_seconds`、方向 `at-least`、阈值 200 | 两个指标读同一个值，`report` 给出 `True` 和 `False` 两个相反结论 |
| 阈值为 NaN | `threshold=float("nan")` | 任何比较都为 `False`，指标永远不通过且不报错 |
| 问题与指标无关联 | `questions` 只是字符串列表 | 无法检查每个问题都有指标、每个指标都回答某个问题 |
| 缺 population | 字段不存在 | 见 Q7 |

修复（已运行验证：拼写错误、NaN 阈值、重复名称都能报出，示例计划仍返回 `[]`）：

```python
import math
from collections import Counter

VALID_KINDS = {"outcome", "guardrail", "counter"}

def validate_strict(plan: MeasurementPlan) -> list[str]:
    issues = validate(plan)
    for metric in plan.metrics:
        if metric.kind not in VALID_KINDS:
            issues.append(f"{metric.name} has invalid kind: {metric.kind}")
        t = metric.threshold
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
            issues.append(f"{metric.name} has non-finite threshold")
    for name, count in Counter(m.name for m in plan.metrics).items():
        if count > 1:
            issues.append(f"duplicate metric name: {name}")
    return issues
```

更进一步：把 `questions` 改成 `dict[str, list[str]]`（问题 → 指标名），检查每个问题至少一个指标，且每个指标至少回答一个问题。

### Q11 — 参考答案

1. 10 次 replay 时正确率只可能是 `0.0, 0.1, …, 1.0` 这 11 个值。"≥ 0.9"等价于"10 次中至少 9 次正确"。用计数表达更清晰：`correct_count >= 9 of 10`。
2. 实际计算 9/10 的 95% Wilson 区间约为 **[0.596, 0.982]**；10/10 为 [0.722, 1.0]；若扩大到 90/100，区间收窄到 [0.826, 0.945]。也就是说，10 次中 9 次正确，真实正确率可能低到 0.6，与 fail 线 0.75 无法区分。这正是讲义 ambiguous 路径的含义："small improvement with wide variance, requiring a larger replay set"。
3. 避免浮点边界问题：
   - 存计数而不是比率（`correct=9, total=10`），用整数比较 `correct * 10 >= 9 * total`；
   - 或用 `fractions.Fraction` / `decimal.Decimal`；
   - 或在比较前按指标精度取整（如 `round(value, 6)`）、用 `math.isclose` 给出容差，但容差必须在事前写进契约。

### Q12 — 参考答案

1. 修改要点：

```python
@dataclass(frozen=True)
class Metric:
    name: str
    direction: str
    threshold: float
    window: str
    source: str
    kind: str          # "outcome" | "guardrail" | "counter"
    population: str    # 新增：数据来自哪个人群

def validate(plan):
    ...
    if "counter" not in kinds:
        issues.append("counter metric is missing")
    for metric in plan.metrics:
        if not metric.population.strip():
            issues.append(f"{metric.name} lacks population")
```

注意：新增字段没有默认值时，`example()` 里所有 `Metric(...)` 调用都要补参数，测试中构造的 `Metric("bad_direction", "up", ...)` 也要同步修改。

2. 示例 counter-metric 契约：

| 字段 | 值 |
|------|----|
| name | `alerts_dismissed_without_action_rate` |
| direction | at-most |
| threshold | 不高于试点前基线 + 5 个百分点（基线需事先测出并写入） |
| window | 试点全程（例如 4 周） |
| source | 告警平台事件日志（acknowledge / dismiss 记录） |
| population | 试点中的 on-call 工程师 |
| kind | counter |

它防的是"推荐很快，但工程师因为不信任或信息过载而更多地直接关闭告警"——成本被转移到了漏报上。另一个可选项是"每次事故中操作员额外核对推荐所花的分钟数"。

### Q13 — 参考回答要点

- **GQM**：Basili 提出的 Goal/Question/Metric 方法——目标（为什么测）→ 问题（要知道什么）→ 指标（用什么数回答）。讲义引用了 Basili 1992 与 Basili、Caldiera、Rombach 的 GQM 论文。
- **例子**：
  - Goal：在不降低客户满意度、不增加违规承诺的前提下，减少需要人工处理的工单。
  - Questions：agent 能独立解决多少工单？解决得对不对？是否做出越权承诺（退款、赔偿）？是否把麻烦转嫁给人工（转人工时上下文是否完整、二次联系率是否上升）？
  - Metrics：自动解决率（outcome）、抽检正确率（outcome）、越权承诺次数 = 0（guardrail）、7 天内二次联系率不高于基线（counter）。每个都写方向、阈值、窗口、来源、人群。
- 加分点：先写判定规则；删掉"对话轮数""调用次数"这类不能改变决策的指标。
- 常见误区：从已有的仪表盘指标倒推目标。

### Q14 — 参考回答要点

- **Outcome**：期望状态是否改善（识别耗时、正确率）。
- **Guardrail**：固定约束是否仍成立（生产写入 = 0、隐私泄露 = 0），触发即失败，不与 outcome 做交换。
- **Counter-metric**：局部改进是否把成本转移到别处（操作员工作量、漏报、下游团队的返工）。
- **只盯一个 outcome 的危险**：Goodhart 定律——指标一旦成为目标就不再是好指标。只优化速度会得到"快但错"或"快但不安全"；讲义："For an incident workflow, speed is not enough."
- 加分点：说明 guardrail 是硬约束、counter-metric 通常与基线比较；指出本节代码只强制 outcome + guardrail，没有强制 counter-metric。

### Q15 — 参考回答要点

- 不会直接推进，原因：
  1. **样本太小**：9/10 的 95% 区间约 [0.60, 0.98]，与 fail 线 0.75 无法区分；应落入 ambiguous，扩大 replay 集。
  2. **只看了 outcome**：guardrail（生产写入）和 counter-metric 是否满足？
  3. **离线证据的边界**：replay 证明不了信任与工作流影响，这是试点要回答的问题——但进入试点本身也需要试点的控制措施（有限人群、负责人、回滚、审计、退出标准，见第 53 节）。
  4. **事前规则**：如果事前写的 pass 规则就是"≥ 0.9"，那么形式上通过了；但应检查当初是否定义了最小样本量。
- 加分点：建议把阈值改写为计数形式，并把"最小窗口"写进契约。

### Q16 — 参考回答要点

- **Goal**：减少开发者写 PR 描述的时间，同时不降低 reviewer 理解变更的质量。
- **Questions**：节省了多少时间？描述是否准确（不编造未发生的改动）？reviewer 是否因此需要更多来回？是否泄露敏感信息？
- **Metrics（示例）**：

| name | 方向 | 阈值 | 窗口 | 来源 | 人群 | 类型 |
|------|------|------|------|------|------|------|
| `author_edit_minutes_median` | at-most | 3 | 试点 2 周 | 编辑器埋点 | 试点团队开发者 | outcome |
| `description_factual_error_rate` | at-most | 0.05 | 每周抽检 40 个 PR | 人工审阅记录 | 同上 | outcome |
| `secrets_in_description` | at-most | 0 | 试点全程 | 密钥扫描日志 | 全部试点 PR | guardrail |
| `review_round_trips_median` | at-most | 基线值 | 试点 2 周 | 代码托管平台 API | reviewer | counter |

- **判定规则**：任何密钥泄露 → fail；事实错误率 > 0.1 → fail；outcome 都达标且 counter 不劣于基线 → pass；其他 → ambiguous，延长窗口。
- 加分点：事前测基线；说明为什么不选"生成字数"这种易收集但不能改变决策的指标。

### Q17 — 参考回答要点

- 回应：事后降低阈值正是讲义警告的"move the threshold to protect the build"。阈值是事前对"什么结果值得继续投入"的承诺，结果出来后再改，就等于没有阈值。
- 合理调整阈值的条件：
  1. 有**新证据**表明原阈值本身设错了（例如发现基线其实只有 0.7，0.85 已是大幅改进），并且这个理由与本次结果无关；
  2. 调整要**显式记录**理由，并在**下一轮**测量中生效，而不是用于本轮的判定；
  3. 同时检查 guardrail 和 counter-metric，不能用放宽 outcome 去掩盖其他问题。
- 当前结果的正确处理：按事前规则落入 fail 或 ambiguous，ambiguous 就扩大样本或调整方案。
- 加分点：类比科研的预注册与"p-hacking"；建议把阈值变更走评审流程（与第 51 节"记录理由"一致）。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 47 先定义预期成效，再选择交付形式](../../47-outcomes-before-output/docs/zh.md)：GQM 中的 Goal 来自结果框架。
- [阶段 14 · 51 编写保留判断空间的规格说明](../../51-write-specifications-that-preserve-judgment/docs/zh.md)：规格中的 Proof 表面在本节被细化为指标契约。
- [阶段 14 · 50 选择足以改变决策的最小实现范围](../../50-choose-the-smallest-testable-slice/docs/zh.md)：指标要能"改变决策"，与切片选择的标准一致。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../30-eval-driven-agent-development/docs/zh.md)：离线 eval 集是 replay 证据的来源。
- [阶段 02 · 09 模型 Evaluation](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：样本量、置信区间等评估基础。

### 本节被哪些后续内容用到
- [阶段 14 · 53 有意识地选择原型、试点或生产方案](../../53-prototype-pilot-or-production/docs/zh.md)：outcome 与 guardrail 阈值是试点的必备控制，决定能否进入下一阶段。
- [阶段 14 · 54 建立持续反馈机制，明确负责人和退役条件](../../54-build-the-feedback-ratchet/docs/zh.md)：上线后的信号如何回流修改测量计划。
- [阶段 17 · 21 对 LLM Features 进行 A/B 测试](../../../17-infrastructure-and-production/21-ab-testing-llm-features/docs/zh.md)：在线实验中的指标、护栏与统计显著性。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)：用指标阈值驱动逐步放量。
- [阶段 19 · 11 LLM Observability 与评估仪表盘](../../../19-capstone-projects/11-llm-observability-dashboard/docs/zh.md)：把指标契约落到仪表盘与告警。

### 延伸关键词
`GQM` · `outcome metric` · `guardrail metric` · `counter-metric` · `decision rule` · `pre-registration` · `Goodhart's law` · `Wilson interval` · `offline replay` · `bounded pilot` · `baseline` · `population` · `observation window`
