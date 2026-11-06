# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 52 节 在结果产生前设计成功指标 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下）；测试：`python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义的主张是"测量回答决策，而不是装饰仪表盘"：先写 Goal，派生 Question，再选最少的 Metric，并在看到数据**之前**定好阈值、窗口、来源和判定路径。这份代码把"测量计划"做成一个可校验的数据结构：

1. **GQM 的数据表达**：`MeasurementPlan` = 一个目标 + 若干问题 + 若干指标。
2. **指标契约**：每个 `Metric` 必须有方向（`at-most` / `at-least`）、阈值、窗口、来源、类型。
3. **计划校验**：至少一个 outcome 指标、至少一个 guardrail 指标；方向合法；来源与窗口非空。
4. **报告**：逐项评估（阈值包含等号），对缺失值显式标注 `missing`，对非法方向标注 `invalid` 而不是崩溃。

同时要看清它的边界：它没有实现讲义的 pass / fail / ambiguous 总体判定，没有 counter-metric 与 population，`report` 的 `status` 只说明**计划**是否合法，不说明**结果**是否达标。

> 一句话：**把"先定规则再看数据"落成一个可以被校验、可以复现的测量契约，并让缺失与非法输入显式可见。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Metric` | frozen dataclass | 名称、方向、阈值、窗口、来源、类型 | 指标契约 |
| `MeasurementPlan` | dataclass | 目标、问题、指标 | Goal–Question–Metric |
| `validate` | 函数 | 返回计划层面的问题列表 | 事前校验 |
| `evaluate` | 函数 | 单个指标在给定值下是否通过（含等号） | 阈值方向 |
| `report` | 函数 | 计划状态 + 逐项结果（passed / missing / invalid） | 证据报告 |
| `example` | 函数 | 事故诊断场景：2 个 outcome + 1 个 guardrail | 讲义案例 |
| `main` | 函数 | 用示例观测值生成 `outputs/measurement-report.json` | 交付物 |
| `tests/test_main.py` | 单元测试 | 6 个测试，见第 9 节 | 校验与报告行为 |

数据流：`example()` + 观测值字典 `values` → `report()`（内部调用 `validate()`、`evaluate()`、`asdict()`）→ `json.dumps` → 写入并打印 `outputs/measurement-report.json`。

---

## 3. 逐段精讲

### 3.1 数据结构：`Metric` 与 `MeasurementPlan`

```python
@dataclass(frozen=True)
class Metric:
    name: str
    direction: str
    threshold: float
    window: str
    source: str
    kind: str


@dataclass
class MeasurementPlan:
    goal: str
    questions: list[str]
    metrics: list[Metric]
```

- 与讲义"A Metric Needs a Contract"表格对照：

| 讲义字段 | 代码字段 | 示例 |
|---------|---------|------|
| Name | `name` | `median_identification_seconds` |
| Direction | `direction` | `"at-most"`（讲义写作 "at most"） |
| Threshold | `threshold` | `120` |
| Window | `window` | `"ten incident replays"` |
| Source | `source` | `"replay log"` |
| Population | **缺失** | 讲义：试点中的 on-call 工程师 |
| Kind | `kind` | `"outcome"` / `"guardrail"` |

- `Metric` 是 frozen：指标契约定下后不应被悄悄修改，这与"先承诺再测量"的精神一致。
- `MeasurementPlan` 可变：测试中会直接替换 `plan.metrics` 来构造反例。
- ⚠️ `questions` 是孤立的字符串列表，与 metrics 没有映射关系，代码无法检查"每个问题都有指标回答"。
- ⚠️ `kind` 只认 `outcome` / `guardrail`（见 3.2），讲义的第三类 counter-metric 没有落地。

### 3.2 `validate`：计划层面的事前检查

```python
def validate(plan: MeasurementPlan) -> list[str]:
    issues: list[str] = []
    if not plan.goal.strip():
        issues.append("goal is empty")
    if not plan.questions:
        issues.append("questions are empty")
    if not plan.metrics:
        issues.append("metrics are empty")
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
    return issues
```

- `{metric.kind for metric in plan.metrics}` 是**集合推导式**：收集出现过的类型，再用 `in` 检查"至少一个 outcome、至少一个 guardrail"。这正是讲义 Build It 的实验点：删掉 guardrail 后计划变成 invalid，"even when the outcome metrics remain"。
- 没有 source 或 window → 报错，对应讲义："Without source and window, a number cannot be reproduced."
- 空计划 `metrics=[]` 会同时报 3 条（实测：`metrics are empty`、`outcome metric is missing`、`guardrail metric is missing`）。
- ⚠️ 已实测的漏洞（测验 Q10）：
  - `kind="outcom"`（拼写错误）或 `kind="counter"` 都被**静默接受**；
  - 同名指标不报错，`report` 会对同一个值给出两个可能相反的结论；
  - 阈值是 NaN 不报错，之后任何比较都是 `False`；
  - 不检查 population（字段本身就不存在）。

### 3.3 `evaluate`：包含等号的阈值

```python
def evaluate(metric: Metric, value: float) -> bool:
    if metric.direction == "at-most":
        return value <= metric.threshold
    if metric.direction == "at-least":
        return value >= metric.threshold
    raise ValueError("invalid direction")
```

- 阈值**包含等号**：中位耗时正好 120 秒算通过、正确率正好 0.9 算通过。这是一个需要事先约定的细节，测试 `test_at_most_threshold_is_inclusive` 专门锁定了它。示例观测值 `correct_service_rate = 0.9` 正好踩在线上。
- 非法方向直接抛 `ValueError`——`evaluate` 是底层函数，遇到不该出现的输入应该大声失败；`report` 会在调用前先拦截非法方向（见 3.4）。
- ⚠️ 浮点边界：`0.7 + 0.2` 的结果是 `0.8999999999999999`，实测 `evaluate(correct_service_rate, 0.7 + 0.2)` 返回 `False`。比率型指标建议用计数表达（10 次中 ≥ 9 次），或在契约中写明比较精度。
- ⚠️ `NaN` 在两个方向下都返回 `False`；`False`（布尔值）在 `at-most 0` 下返回 `True`（因为 `False == 0`）。

### 3.4 `report`：缺失与非法都要显式

```python
def report(plan: MeasurementPlan, values: dict[str, float]) -> dict:
    issues = validate(plan)
    results = []
    for metric in plan.metrics:
        if metric.direction not in {"at-most", "at-least"}:
            result = {"name": metric.name, "status": "invalid"}
            if metric.name in values:
                result["value"] = values[metric.name]
            results.append(result)
        elif metric.name not in values:
            results.append({"name": metric.name, "status": "missing"})
        else:
            results.append({"name": metric.name, "value": values[metric.name], "passed": evaluate(metric, values[metric.name])})
    return {"status": "valid" if not issues else "invalid", "issues": issues, "plan": asdict(plan), "results": results}
```

- 每个指标三选一：
  - 方向非法 → `{"status": "invalid"}`（若有值也附上），**不调用** `evaluate`，避免整份报告因一个坏指标崩溃；
  - 没有观测值 → `{"status": "missing"}`，缺失被显式记录，而不是默认为通过或失败；
  - 正常 → `{"value": ..., "passed": bool}`。
- 结果字典有两种"形状"：有的带 `status`，有的带 `passed`。消费方需要分别处理（例如 `item.get("passed")`）。
- 顶层 `status` 只取决于 `validate(plan)`：**计划合法**就是 `"valid"`。实测传入 `production_writes = 1` 时，`status` 仍是 `"valid"`，只有第三项 `passed: False`。讲义的 fail 规则（"any production write"）需要另写判定函数（测验 Q9）。
- `asdict(plan)` 把计划原样写入报告：读报告的人可以看到当时承诺的阈值，这是"事前承诺"的可审计记录。

### 3.5 `example` 与 `main`：事故诊断场景

```python
def example() -> MeasurementPlan:
    return MeasurementPlan(
        goal="Reduce time to identify the affected service without increasing unsafe actions",
        questions=["How quickly is the correct service identified?", "Does diagnosis remain read-only?"],
        metrics=[
            Metric("median_identification_seconds", "at-most", 120, "ten incident replays", "replay log", "outcome"),
            Metric("correct_service_rate", "at-least", 0.9, "ten incident replays", "incident record", "outcome"),
            Metric("production_writes", "at-most", 0, "entire pilot", "audit log", "guardrail"),
        ],
    )


def main() -> None:
    values = {"median_identification_seconds": 94, "correct_service_rate": 0.9, "production_writes": 0}
    output = Path(__file__).resolve().parents[1] / "outputs" / "measurement-report.json"
    output.write_text(json.dumps(report(example(), values), indent=2) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))
```

- 目标一句话里已经包含了 outcome（"reduce time"）和约束（"without increasing unsafe actions"），两个问题分别派生出 outcome 指标和 guardrail 指标——GQM 的最小完整示例。
- 讲义列了 4 个问题，示例只用了 2 个："How often is the identified service correct?" 没有写进 `questions`，但有对应指标 `correct_service_rate`；"Does the workflow increase alert dismissal or operator workload?"（counter-metric 对应的问题）既没有问题也没有指标。
- 窗口不一致值得注意：两个 outcome 用"ten incident replays"（离线），guardrail 用"entire pilot"（在线）。一份报告里混合了离线与在线证据，而 `main` 中的观测值是硬编码的，并非真的来自 replay 或 pilot。
- `production_writes` 阈值为 0、方向 `at-most`：只要有一次写入就不通过——guardrail 的典型写法。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 方向用 `at-most` / `at-least` 字符串 | 比 `<=` 符号更可读，JSON 友好 | 拼错会被 `validate` 拦下；可改成 `Enum` |
| 阈值包含等号 | 明确的边界约定，有测试锁定 | 浮点比率会踩边界；用计数或事先约定精度 |
| 强制 outcome + guardrail | 防止"快但不安全" | 没强制 counter-metric；未知 kind 被静默接受 |
| `missing` / `invalid` 显式记录 | 缺失不等于通过；坏指标不拖垮整份报告 | 结果字典形状不统一，消费方需判断 |
| `status` 只反映计划合法性 | 职责单一 | 不给出 pass / fail / ambiguous，讲义的判定规则要另写 |
| 把计划写进报告 | 事前承诺可审计 | 没有记录"阈值何时定、谁定的"；生产中应有版本与签署时间 |
| 观测值硬编码在 `main` | 演示简单 | 真实系统应从 replay 日志、审计日志等 source 读取，并记录采集时间窗 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class Metric` | 不可变数据类，可哈希，可放进集合 |
| `@dataclass` | `class MeasurementPlan` | 可变数据类，自动生成 `__init__` |
| 类型注解 | `threshold: float`、`values: dict[str, float]` | 只是提示，运行时不检查；传 `120`（int）也可以 |
| 集合推导式 | `{metric.kind for metric in plan.metrics}` | 去重收集，便于做成员测试 |
| 集合字面量做成员测试 | `metric.direction not in {"at-most", "at-least"}` | 简洁的"合法值"检查 |
| `str.strip()` | `plan.goal.strip()` | 去掉首尾空白再判断是否为空 |
| 链式比较返回布尔 | `return value <= metric.threshold` | 比较表达式本身就是 `bool` |
| `raise ValueError(...)` | `evaluate` 末尾 | 遇到不该出现的输入时主动抛错 |
| `if / elif / else` | `report` 的三分支 | 互斥地处理 invalid、missing、正常 |
| 字典动态加键 | `result["value"] = values[metric.name]` | 先建基础字典，按条件补充字段 |
| `in` 判断字典键 | `metric.name not in values` | 避免 `KeyError` |
| 条件表达式 | `"valid" if not issues else "invalid"` | 三元表达式 |
| `dataclasses.asdict` | `asdict(plan)` | 递归转为 dict，嵌套的 `Metric` 也会被转换 |
| `json.dumps(indent=2)` | `main` | 带缩进的 JSON |
| `pathlib.Path` | `Path(__file__).resolve().parents[1] / "outputs"` | 与当前工作目录无关地定位输出文件 |
| `if __name__ == "__main__":` | 文件末尾 | 被测试导入时不执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时副本中运行；生成的 JSON 与仓库中的 `outputs/measurement-report.json` 逐字节一致）。节选：

```text
{
  "status": "valid",                       ← 计划合法：有 outcome、有 guardrail，方向与来源窗口都齐全
  "issues": [],
  "plan": { ... 原样写入目标、2 个问题、3 个指标契约 ... },
  "results": [
    { "name": "median_identification_seconds", "value": 94,  "passed": true },   ← 94 <= 120
    { "name": "correct_service_rate",          "value": 0.9, "passed": true },   ← 0.9 >= 0.9，恰好踩线
    { "name": "production_writes",             "value": 0,   "passed": true }    ← 0 <= 0
  ]
}
```

（`results` 中每个对象在真实输出里分多行显示，这里压缩为一行。）

逐项解读：

- **`status: valid`** 说的是"这份测量计划可以用来做决策"，不是"结果达标"。
- **中位耗时 94 秒**：低于 120 秒阈值，outcome 达标。
- **正确率 0.9**：恰好等于阈值，因为比较包含等号才算通过。窗口只有 10 次 replay，0.9 意味着 9/10；按 Wilson 方法，95% 置信区间约为 [0.596, 0.982]，实际很接近讲义所说的"ambiguous"情形（见测验 Q11）。
- **生产写入 0**：guardrail 守住。
- 若按讲义的判定规则手工汇总：三项都满足 → pass。但代码本身没有输出这个结论。

附加实验（均实测）：

| 改动 | 结果 |
|------|------|
| 删除 guardrail 指标（讲义 Build It） | `status: invalid`，`issues: ['guardrail metric is missing']`，两个 outcome 仍为 `passed: true` |
| `production_writes = 1` | `status: valid`，第三项 `passed: false` |
| `values = {}` | 三项都是 `{"status": "missing"}`，`status` 仍为 `valid` |
| `correct_service_rate = 0.7 + 0.2` | `passed: false`（浮点值 0.8999999999999999） |

---

## 7. 动手改一改

1. **（入门）** 讲义 Build It：删除 guardrail 指标并运行，解释为什么 outcome 全部通过时计划仍然无效。
2. **（入门）** 讲义练习 4：实现 `decide(values)`，按讲义的 pass / fail / ambiguous 规则返回总体结论，并把它加入 `report` 的输出（参考测验 Q9）。注意：缺失的 guardrail 不能当作通过。
3. **（进阶）** 讲义练习 2、3：给 `Metric` 增加 `population` 字段，新增 `kind="counter"`，让 `validate` 要求至少一个 counter-metric、拒绝未知 kind；同步更新 `example()` 和测试。
4. **（进阶）** 把比率指标改为计数：`correct_service_count`（at-least 9）配合 `replay_count`（at-least 10），消除浮点边界问题。
5. **（进阶）** 让 `questions` 变成 `dict[str, list[str]]`（问题 → 指标名），在 `validate` 中检查每个问题至少映射一个指标、每个指标至少回答一个问题；讲义练习 5 要求删除"不能改变决策"的指标——这个映射能帮你找出它们。
6. **（挑战）** 为 ambiguous 路径实现"最小样本量"规则：比率型指标在 Wilson 区间下界低于 fail 线时返回 ambiguous，并在报告中给出"还需要多少个样本"。

---

## 8. 常见坑

- **把 `status: valid` 读成"达标"**：它只代表计划合法。
- **把缺失当成 0**：`production_writes` 缺失时不能推断"没有写入"；代码正确地标为 `missing`，下游判定也必须这样处理。
- **浮点比率踩阈值**：`0.7 + 0.2 < 0.9`。用计数、`Fraction`，或事先约定精度。
- **拼错 kind**：`"outcom"` 不会报错，只会让该指标"隐身"。
- **同名指标**：两个契约读同一个值，可能一个通过、一个失败。
- **离线与在线窗口混用却不标注**：同一份报告里，replay 数据和 pilot 数据回答的是不同问题。
- **看到结果后再改阈值**：讲义的核心警告。修改阈值应记录理由，并在下一轮测量中生效。

---

## 9. 测试在验证什么

`code/tests/test_main.py` 用 `importlib.util.spec_from_file_location` 按路径加载 `main.py`（模块名 `lesson52`），不依赖包结构。

| 测试 | 验证的性质 |
|------|-----------|
| `test_example_is_valid` | 示例计划通过校验（`validate` 返回 `[]`） |
| `test_outcome_metric_is_required` | 删掉全部 outcome 指标后出现 `"outcome metric is missing"` |
| `test_guardrail_metric_is_required` | 删掉 guardrail 后出现 `"guardrail metric is missing"`（讲义 Build It 的自动化版本） |
| `test_at_most_threshold_is_inclusive` | `median_identification_seconds` 恰好为 120 时通过——锁定"阈值包含等号"的约定 |
| `test_report_marks_missing_value` | `values = {}` 时每一项都是 `status: missing`，缺失被显式记录 |
| `test_report_marks_invalid_direction_without_evaluating_it` | 方向为 `"up"` 时：计划 `invalid`、issues 含 `bad_direction has invalid direction`，该项结果为 `{"name", "status": "invalid", "value": 94}`，且没有因调用 `evaluate` 而抛异常 |

运行方式（在小节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：`Ran 6 tests in 0.001s — OK`，全部通过。

未覆盖、可补充的测试：`at-least` 的边界（0.9 恰好通过）、浮点边界、未知 kind、重复名称、NaN 阈值、`production_writes > 0` 时的总体判定（需先实现 `decide`）。
