# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 54 节 建立持续反馈机制，明确负责人和退役条件 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下）；测试：`python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义的主张是"反馈是基础设施"：收集日志不等于学习，必须有一条 **promotion（晋升）** 路径，把每个信号变成"有负责人、有 artifact、有验证、有退役条件"的持久变更——像棘轮（ratchet）一样，被验证的改进只进不退。这份约 110 行的代码实现了这条路径的最小版本：

1. **路由**：`destination` 根据观察文本把信号送到拥有它的层——evaluation、policy、context、runtime 或 backlog（讲义"Route to the Owning Layer"表格）。
2. **晋升**：`promote` 把一个 `Signal` 变成一个 `RatchetAction`：优先级、目标层、变更描述、负责人、持久 artifact、验证证据、退役检查。
3. **排序**：`backlog` 按优先级降序排出待办，写入 `outputs/feedback-backlog.json`——讲义说它是"Product Judgment and Delivery"路径的收尾产物，也是下一个结果框架的输入。

同时要看清它的简化：路由靠**有先后顺序的子串匹配**，会把根因与症状弄混；优先级是 `severity × frequency`，会把一次越权写入排在最后；`owner` 与到期天数都不校验；退役条件只是时间窗口。

> 一句话：**把"我们注意到了一个问题"变成"谁、在哪一层、改哪个文件、用什么证明、何时复审"的结构化待办，并看清自动路由与打分的局限。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Signal` | frozen dataclass | 来源、观察、严重度、频率、负责人、到期天数 | 具体信号 |
| `RatchetAction` | frozen dataclass | 优先级、目标层、变更、负责人、artifact、验证、退役检查 | 晋升后的持久控制 |
| `destination` | 函数 | 关键词匹配 → 五个目标层之一 | 路由到拥有层 |
| `promote` | 函数 | 校验 → 路由 → 计算优先级 → 查表得 artifact 与验证 → 生成 action | promotion |
| `backlog` | 函数 | 批量晋升并排序 | 按后果与复发排优先级 |
| `example` | 函数 | 三个信号：事故、试点审计、评测运行 | 讲义贯穿案例 |
| `main` | 函数 | 写出并打印 `outputs/feedback-backlog.json` | 交付物 |
| `tests/test_main.py` | 单元测试 | 6 个测试，见第 9 节 | 路由、排序、校验 |

数据流：`example()` → `backlog()` → 对每个信号 `promote()`（内部 `destination()`）→ `sorted()` → `asdict()` → `json.dumps` → 写入并打印。

---

## 3. 逐段精讲

### 3.1 两个数据类：信号与动作

```python
@dataclass(frozen=True)
class Signal:
    source: str
    observation: str
    severity: int
    frequency: int
    owner: str
    expires_after_days: int


@dataclass(frozen=True)
class RatchetAction:
    priority: int
    destination: str
    change: str
    owner: str
    durable_artifact: str
    verification_evidence: str
    retirement_check: str
```

- `RatchetAction` 的字段与讲义"Ownership Is Part of the Control"的清单逐项对应：

| 讲义要求 | 字段 |
|---------|------|
| one owner | `owner` |
| a priority based on consequence and recurrence | `priority` |
| the artifact to change | `durable_artifact` |
| the verification that proves the change | `verification_evidence` |
| a review or expiry window | 由 `Signal.expires_after_days` 带入 |
| a retirement condition | `retirement_check` |

- 两个类都是 frozen：动作一旦生成就是一条记录，修改应该生成新记录（可追溯）。
- ⚠️ `Signal` 只有 `observation`（症状），没有 `cause`（根因）。讲义循环第 3 步是"identify the earliest system layer that owns the **cause**"，代码却只能从症状文本推断（第 46 节的代码同时有 symptom 和 cause 两个字段）。
- ⚠️ `severity: int` 等类型注解运行时不检查。

### 3.2 `destination`：按顺序的关键词路由

```python
def destination(signal: Signal) -> str:
    text = signal.observation.lower()
    if any(word in text for word in ("regression", "wrong result", "false positive")):
        return "evaluation"
    if any(word in text for word in ("permission", "unsafe", "production write")):
        return "policy"
    if any(word in text for word in ("missing context", "could not find", "duplicate")):
        return "context"
    if any(word in text for word in ("timeout", "retry", "unavailable")):
        return "runtime"
    return "backlog"
```

- `any(word in text for word in (...))`：生成器表达式 + `any`，只要有一个关键词是 `text` 的**子串**就为真，并且找到第一个就短路停止。
- 与讲义表格对照：

| 讲义信号 | 讲义目标层 | 代码关键词 |
|---------|-----------|-----------|
| False positive, regression, wrong result | Evaluation or test | 三个都有 |
| Missing context, duplicate work, stale fact | Context source or retrieval route | 有 missing context、duplicate，另加 could not find；**缺 stale** |
| Unsafe action or authority gap | Policy or permission boundary | unsafe、permission、production write |
| Timeout, retry storm, unavailable dependency | Runtime control | timeout、retry、unavailable |
| New product need or unresolved tradeoff | Shaped backlog item | 兜底分支 |

- 检查顺序是 evaluation → policy → context → runtime，**先命中先返回**。已实测的误判：

| 观察 | 代码结果 | 应为 | 原因 |
|------|---------|------|------|
| `retry storm caused duplicate writes` | context | runtime | `duplicate` 先于 `retry` 被检查 |
| `timeout caused wrong result` | evaluation | runtime | 症状先于根因被匹配 |
| `stale fact about service owner` | backlog | context | 关键词表缺 `stale` |
| `nonduplicated` | context | — | 子串匹配，不看单词边界 |
| `the agent was unable to find the runbook` | backlog | context | 只认 `could not find` 这一种说法 |

- 只调整顺序并不能根治：实测把 policy、runtime 提前、加上 `stale` 后，原本正确的 `"false positive on a stale deployment"` 会被路由到 context，测试 `test_false_positive_routes_to_evaluation` 失败。根本办法是让信号携带人工确定的根因 / 拥有层，关键词路由只做建议（测验 Q9）。
- 值得肯定的设计：policy 在 context 和 runtime 之前，所以"在超时后尝试不安全的生产写入"会进入 policy（实测），安全问题不会被其他层"抢走"。

### 3.3 `promote`：从信号到 ratchet action

```python
def promote(signal: Signal) -> RatchetAction:
    if signal.severity not in range(1, 6) or signal.frequency < 1:
        raise ValueError("severity must be one to five and frequency positive")
    target = destination(signal)
    priority = signal.severity * signal.frequency
    durable_artifact = {
        "evaluation": "evaluations/regression-suite.json",
        "policy": "policies/authority-boundaries.json",
        "context": "context/retrieval-guidance.md",
        "runtime": "runtime/reliability-controls.json",
        "backlog": "backlog/shaped-work.json",
    }[target]
    verification_evidence = {
        "evaluation": "Record a passing regression evaluation",
        "policy": "Record a passing authority-boundary scenario",
        "context": "Record a replay with the required context present",
        "runtime": "Record a timeout and retry scenario within budget",
        "backlog": "Record review against the outcome frame",
    }[target]
    return RatchetAction(
        priority,
        target,
        f"Prevent recurrence of: {signal.observation}",
        signal.owner,
        durable_artifact,
        verification_evidence,
        f"Remove or revise after {signal.expires_after_days} days without recurrence",
    )
```

- **校验**：`signal.severity not in range(1, 6)` 用 range 的成员测试表达"1 到 5"。实测：`0`、`6`、`2.5` 被拒；但 `3.0`（`3.0 == 3`）和 `True`（`True == 1`）会通过。`frequency < 1` 只拦住 0 和负数，`1.5` 能通过。
- ⚠️ **不校验 owner 和到期天数**：实测 `owner=""`、`expires_after_days=-5` 正常返回，退役检查变成 "after -5 days"。讲义："Every ratchet action needs one owner"、"An unowned improvement is an observation with better formatting."
- **优先级 = 严重度 × 频率**：对应讲义"Prioritize recurrence by severity and frequency"。示例中 `4×3 = 12`、`5×1 = 5`、`3×4 = 12`。⚠️ 越权写生产（严重度 5、频率 1）因此排在最后（测验 Q10）。
- **两个字典查表**：每个目标层对应一个持久 artifact 和一种验证证据。字典字面量后紧跟 `[target]`，即"建表后立刻取值"。这体现了讲义的"Fix the cause at the earliest effective layer"：policy 层的修复是改权限边界文件、用授权场景测试验证，而不是加 prompt。
- `change` 用 f-string 生成，是通用模板；真实系统中应写具体的变更（如"给 CMDB 查询加 2 秒超时与最多 2 次重试"）。
- `retirement_check` 只实现了讲义四条复审理由中的一条（"被保护的失败在窗口内未出现"），而且没有区分"复审"与"退役"（测验 Q12）。

### 3.4 `backlog`：排序

```python
def backlog(signals: list[Signal]) -> list[RatchetAction]:
    actions = [promote(signal) for signal in signals]
    return sorted(actions, key=lambda item: (-item.priority, item.destination, item.change))
```

- 排序键是一个三元组：`-item.priority`（取负实现降序）、`item.destination`（同分时按层名字母序）、`item.change`（再同分时按文本）。元组按位置逐项比较。
- 示例中 context 与 evaluation 都是 12，`"context" < "evaluation"`，所以 context 在前。这个次序与业务无关，只是为了**输出确定**（同样的输入永远得到同样的 JSON，便于 diff 与测试）。
- 任何一个信号非法都会让 `promote` 抛错，整个 `backlog` 失败——"全有或全无"。生产中可能更希望把非法信号收集到单独的"需修正"列表。

### 3.5 `example` 与 `main`

```python
def example() -> list[Signal]:
    return [
        Signal("incident 184", "missing context caused duplicate service lookup", 4, 3, "platform", 90),
        Signal("pilot audit", "production write was attempted", 5, 1, "security", 180),
        Signal("evaluation run", "false positive on a stale deployment", 3, 4, "evaluation", 60),
    ]
```

- 三个信号来自三种来源：事故复盘、试点审计、评测运行——对应讲义"Turn incidents, evaluations, user behavior, and corrections into owned actions"。
- 负责人分别是 platform、security、evaluation 团队；到期窗口与严重度大致正相关（安全问题 180 天，误报 60 天）——越严重的控制越不该轻易退役。
- 第三个信号含 `"stale"`，但因为 `"false positive"` 先匹配，被正确地送到 evaluation（这也说明 `stale` 不能简单地加进 context 关键词表）。
- `main` 中 `[asdict(item) for item in backlog(example())]` 把每个 frozen dataclass 转成 dict，再序列化为 JSON 数组。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 关键词子串路由 | 无需模型、可复现、易测试 | 顺序依赖、子串误判、症状≠根因；应以人工确定的根因 / 拥有层为准，自动路由只做建议并标记低置信度 |
| policy 先于 context / runtime | 安全问题优先归属权限层 | evaluation 仍在 policy 之前，"导致错误结果的越权"会被送到 evaluation |
| 层 → artifact / 验证 的固定映射 | 每个动作都有落点和证明方式 | 粒度粗；真实系统中 artifact 应是具体文件与条目，验证应是可执行命令（讲义练习 3） |
| `priority = severity × frequency` | 简单体现"后果与复发" | 高严重度低频被低估；应按严重度分档，档内再排序 |
| 只校验 severity / frequency | 代码短 | owner 空、到期为负、浮点与布尔都能通过 |
| 三元组排序键 | 输出确定、便于 diff | 同分次序与业务无关 |
| 退役条件 = N 天无复发 | 给每个控制一个到期点 | 只覆盖讲义四条理由之一；"无复发"可能正是控制在起作用，应进入评审而非直接删除 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `Signal`、`RatchetAction` | 不可变记录；可哈希 |
| 位置参数构造 | `RatchetAction(priority, target, ...)` | 按字段顺序传参，字段多时易错位，建议改用关键字参数 |
| `str.lower()` | `signal.observation.lower()` | 统一小写后再匹配，大小写不敏感 |
| 子串成员测试 | `word in text` | 判断子串，不考虑单词边界 |
| 生成器表达式 + `any` | `any(word in text for word in (...))` | 短路：找到第一个真值就停止 |
| 元组字面量 | `("timeout", "retry", "unavailable")` | 不可变的关键词集合 |
| `range` 成员测试 | `signal.severity not in range(1, 6)` | 对 int 是 O(1)；对 `3.0` 也返回 `True`，因为按相等比较 |
| 字典字面量立即索引 | `{...}[target]` | 建表即查，键不存在会 `KeyError`（这里 target 一定在表中） |
| f-string | `f"Prevent recurrence of: {signal.observation}"` | 字符串插值 |
| 列表推导式 | `[promote(signal) for signal in signals]` | 批量转换 |
| `sorted` + `key=lambda` | `sorted(actions, key=lambda item: (-item.priority, ...))` | 返回新列表；键为元组时逐项比较 |
| 取负实现降序 | `-item.priority` | 对数值字段的常用技巧（字符串不能这样用） |
| `dataclasses.asdict` | `asdict(item)` | 转成 dict 以便 JSON 序列化 |
| `raise ValueError` | `promote` 开头 | 拒绝非法输入 |
| `pathlib.Path` | `Path(__file__).resolve().parents[1] / "outputs"` | 定位小节目录下的输出 |
| `if __name__ == "__main__":` | 文件末尾 | 被测试导入时不执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时副本中运行；生成的 JSON 与仓库中的 `outputs/feedback-backlog.json` 逐字节一致）：

```text
[
  {
    "priority": 12,                                   ← 4 × 3
    "destination": "context",                         ← 命中 "missing context" / "duplicate"
    "change": "Prevent recurrence of: missing context caused duplicate service lookup",
    "owner": "platform",
    "durable_artifact": "context/retrieval-guidance.md",
    "verification_evidence": "Record a replay with the required context present",
    "retirement_check": "Remove or revise after 90 days without recurrence"
  },
  {
    "priority": 12,                                   ← 3 × 4，与上一条同分，按层名字母序排在后面
    "destination": "evaluation",                      ← 命中 "false positive"
    "change": "Prevent recurrence of: false positive on a stale deployment",
    "owner": "evaluation",
    "durable_artifact": "evaluations/regression-suite.json",
    "verification_evidence": "Record a passing regression evaluation",
    "retirement_check": "Remove or revise after 60 days without recurrence"
  },
  {
    "priority": 5,                                    ← 5 × 1，严重度最高却排最后
    "destination": "policy",                          ← 命中 "production write"
    "change": "Prevent recurrence of: production write was attempted",
    "owner": "security",
    "durable_artifact": "policies/authority-boundaries.json",
    "verification_evidence": "Record a passing authority-boundary scenario",
    "retirement_check": "Remove or revise after 180 days without recurrence"
  }
]
```

逐项解读：

- **三个信号都被路由到了合理的层**，每个 action 都有负责人、artifact、验证与退役检查——这是讲义"ownership is part of the control"的完整形态。
- **排序结果值得质疑**：一次生产写入尝试（试点审计发现的越权行为）排在两个优先级 12 的问题之后。如果团队按顺序处理 backlog，安全问题会最后被修。改用"严重度 5 置顶"或 `(severity, frequency)` 字典序后，顺序变为 policy → context → evaluation（测验 Q10）。
- **讲义 Build It**："Add a runtime timeout signal and confirm that it routes to the runtime rather than the general backlog." 实测 `"dependency timeout during diagnosis"` → `runtime`，artifact 为 `runtime/reliability-controls.json`，验证为 "Record a timeout and retry scenario within budget"。但如果写成 `"timeout caused wrong result"`，会被路由到 evaluation——观察文本的措辞会改变路由。

---

## 7. 动手改一改

1. **（入门）** 讲义 Build It：在 `example()` 中加一个 `Signal("incident 201", "dependency timeout during diagnosis", 3, 2, "reliability", 60)`，确认它进入 runtime 并排在第几位（优先级 6）。
2. **（入门）** 写 `validate_signal`：严重度必须是 1–5 的整数（排除 `bool`），频率为正整数，owner 非空，到期天数为正（参考测验 Q11），并让 `promote` 使用它。
3. **（进阶）** 给 `Signal` 增加 `cause` 或 `owning_layer` 字段：有显式层时直接使用，否则用关键词路由并在输出中加 `"routing": "inferred"` 标记；对同时命中多个层的文本返回 `"needs-triage"`。
4. **（进阶）** 改优先级规则：严重度 5 一律置顶，其余按乘积；更新测试 `test_backlog_sorts_by_priority`（当前测试只检查 priority 字段降序，需要一并调整）。
5. **（进阶）** 讲义练习 3："Add verification commands or observations to the lab output." 把 `verification_evidence` 从描述改成可执行命令（如 `python3 -m pytest evaluations/test_regressions.py -k stale_deployment`）与预期结果。
6. **（挑战）** 讲义练习 4：实现 `review_control(...)`，用"是否被低层不变量取代、阻碍合法工作 vs 防止伤害的次数、架构是否变化、窗口内是否复发"四类证据输出 keep / revise / retire / review-for-retirement（参考测验 Q12），并把复审结论也作为一个 ratchet action 写回 backlog。

---

## 8. 常见坑

- **把症状当根因路由**：`"timeout caused wrong result"` 的修复应在 runtime，而不是只往评测集里加一条。
- **子串匹配**：`"nonduplicated"` 会命中 `"duplicate"`；需要单词边界或结构化字段。
- **调整关键词顺序"修好"一个误判**：往往会制造另一个误判，务必跑全部测试。
- **乘积优先级低估安全事件**：严重度与频率不应线性互换。
- **没有负责人的 action**：代码允许 `owner=""`，但讲义认为这只是"格式更好的观察"。
- **"N 天无复发"就删除控制**：没有复发可能正是因为控制有效；应先进入评审，用证据决定退役。
- **把 prompt 当作默认修复层**：能用测试、权限、运行时控制让失败不可能发生时，不要再加 prompt 段落。

---

## 9. 测试在验证什么

`code/tests/test_main.py` 用 `importlib.util.spec_from_file_location` 按路径加载 `main.py`（模块名 `lesson54`）。

| 测试 | 验证的性质 |
|------|-----------|
| `test_missing_context_routes_to_context` | 示例 1（missing context / duplicate）→ `context` |
| `test_unsafe_action_routes_to_policy` | 示例 2（production write）→ `policy`：越权问题归属权限层 |
| `test_false_positive_routes_to_evaluation` | 示例 3（false positive，同时含 stale）→ `evaluation`；这条测试也锁住了"evaluation 关键词先于 stale 判断"的行为 |
| `test_backlog_sorts_by_priority` | backlog 的 priority 序列是降序 |
| `test_every_action_names_an_artifact_and_verification_evidence` | 每个 action 都有非空的 artifact 与验证证据 |
| `test_invalid_signal_is_rejected` | 严重度 0 时 `promote` 抛 `ValueError` |

运行方式（在小节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：`Ran 6 tests in 0.000s — OK`，全部通过。

测试没有覆盖：runtime 与 backlog 两个分支（讲义 Build It 正好要求补 runtime）、owner 为空、到期天数非正、浮点/布尔严重度、同分时的次序、关键词顺序造成的误判。建议至少补一个 `"dependency timeout during diagnosis" → runtime` 的测试，以及一个"owner 为空应被拒绝"的测试（当前会失败，正好暴露缺口）。
