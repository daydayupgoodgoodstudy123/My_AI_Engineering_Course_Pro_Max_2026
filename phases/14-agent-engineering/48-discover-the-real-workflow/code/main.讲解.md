# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 48 节 发现人们实际执行的工作流 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在小节目录下 `python3 code/main.py`；测试 `python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义要求把"当前工作流"建模成**带证据的有序动作**，区分直接观察与自述/推断，并找出摩擦、交接、权限和隐藏状态。这份约 70 行的代码实现了其中最核心的一块——**证据审计**：

1. **每一步都要有证据**：`WorkflowStep.evidence` 是一个 `Evidence` 元组，没有证据的步骤会被报出来。
2. **证据有强弱**：`Evidence.direct` 标记它是不是直接证据，`confidence` 记录置信度（必须在 0–1 之间）。
3. **顺序要可信**：步骤编号必须是从 1 开始、按出现顺序连续的整数。
4. **把证据强度变成一个数**：`direct_evidence_ratio` 让"有多少是观察到的、有多少是听说的"一目了然（讲义 quiz："It keeps the strength of evidence visible"）。
5. **把摩擦点单独抽出来**：`friction_points` 是下一节"假设地图"的原材料。

> 一句话：**给工作流的每一步挂上证据，并用审计把"有多少是真正看到的"算出来**。但它把讲义的四级证据阶梯压成了一个布尔值，比例按证据条数而非步骤计算，"有一条直接证据就算 grounded"——这些简化会让置信度膨胀，恰好是讲义警告的问题。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Evidence` | frozen dataclass | 来源、观察内容、是否直接、置信度 | 证据阶梯（简化为二元） |
| `WorkflowStep` | frozen dataclass | 顺序、执行者、动作、证据元组、摩擦 | 工作流步骤（八字段中的四个） |
| `audit` | 函数 | 顺序检查、证据存在性、置信度范围、直接证据比例、摩擦点 | 证据审计 |
| `example` | 函数 | 值班工程师 → 查仪表盘 → 事故指挥官批准 | 讲义事故场景 |
| `main` | 函数 | 写 `outputs/workflow-evidence.json` 并打印 | 留存产物 |
| `tests/test_main.py` | 单元测试 | 6 个测试（见第 9 节） | 可执行验证 |

数据流：`example()` → `audit()` → `asdict` 每个步骤 → `json.dumps` → `outputs/workflow-evidence.json`。

---

## 3. 逐段精讲

### 3.1 两个数据类：证据与步骤

```python
@dataclass(frozen=True)
class Evidence:
    source: str
    observation: str
    direct: bool
    confidence: float


@dataclass(frozen=True)
class WorkflowStep:
    order: int
    actor: str
    action: str
    evidence: tuple[Evidence, ...]
    friction: str = ""
```

- `Evidence.source` 记录"从哪里看到的"（录屏编号、事故编号、runbook），`observation` 记录"看到了什么"。来源与观察分开存，是为了**可追溯**：日后有人质疑，可以回到原始材料（讲义延伸阅读 Gotel & Finkelstein 讨论的正是需求与来源的可追溯性）。
- `direct: bool` 把讲义的四级阶梯（直接行为 / 工件 / 自述 / 推断）压成两类。⚠️ 这样无法区分"工件"与"推断"，也无法区分"自述"与"推断"。
- `evidence: tuple[Evidence, ...]`：用**元组**而非列表，是因为 frozen dataclass 应当整体不可变；`tuple[X, ...]` 表示"任意长度、元素都是 X 的元组"。
- `friction` 有默认值 `""`，没有摩擦的步骤可以省略。
- 对照讲义的八个字段：Actor ✓（`actor`）、Action ✓、Friction ✓、Evidence ✓；**Trigger、Input、Output、Authority ✗**。示例第 3 步的"事故指挥官批准"体现了 authority，但只是写在 action 文本里，没有结构化字段。

### 3.2 `audit`：四项检查

```python
def audit(steps: list[WorkflowStep]) -> dict:
    orders = [step.order for step in steps]
    issues: list[str] = []
    if orders != list(range(1, len(steps) + 1)):
        issues.append("workflow order must be contiguous from one")
    for step in steps:
        if not step.evidence:
            issues.append(f"step {step.order} has no evidence")
        for item in step.evidence:
            if not 0 <= item.confidence <= 1:
                issues.append(f"step {step.order} has confidence outside zero to one")
```

- **顺序检查**：比较的是**列表**而不是集合。`[1, 2, 3]` 通过；`[2]`（不从 1 开始）、`[2, 1]`（倒序）、`[1, 3, 2]`（乱序）、`[1, 2, 3, 3]`（重复）都不通过。消息说 "contiguous"，实际检查的是"从 1 开始且按出现顺序递增 1"。
- **证据存在性**：空元组为假，报 "has no evidence"。
- **置信度范围**：链式比较 `0 <= x <= 1`。⚠️ 每条越界证据各报一次，同一步骤两条越界会产生**两条完全相同**的消息。`float('nan')` 也会被正确拒绝（任何与 NaN 的比较都为假）。
- ⚠️ `confidence` 只做范围检查，**不参与** status 判断：一条 `direct=True, confidence=0.01` 的证据照样让工作流 `grounded`。

```python
    direct = sum(item.direct for step in steps for item in step.evidence)
    total = sum(len(step.evidence) for step in steps)
    return {
        "status": "grounded" if not issues and direct > 0 else "needs-evidence",
        "issues": issues,
        "direct_evidence_ratio": round(direct / total, 2) if total else 0,
        "friction_points": [step.friction for step in steps if step.friction],
        "steps": [asdict(step) for step in steps],
    }
```

- `sum(item.direct for ...)`：布尔值是 `int` 的子类，`True` 当 1、`False` 当 0，求和即计数。双层 `for` 的生成器表达式等价于嵌套循环。
- **直接证据比例** = 直接证据条数 / 证据总条数。⚠️ 这是按**证据条数**而不是按**步骤**统计：一个步骤堆 5 条直接证据，就能把整体比例拉高，而其它步骤可能完全没有直接证据（测验 Q10：3 步中只有 1 步被观察证实，比例却是 0.71）。
- **status**：只要没有 issue 且**至少一条**直接证据就是 `grounded`。⚠️ 10 步里只有第 1 步被观察过也算 grounded（比例 0.1）。讲义要"把不确定的说法保持可见"，更合理的做法是列出 `ungrounded_steps`，全部步骤都有支撑才算 grounded（测验 Q9）。
- `if total else 0`：没有任何证据时避免除以零；⚠️ 返回整数 `0`，而正常情况下是浮点数（如 `0.0`、`0.67`），类型不一致。
- `friction_points` 用带条件的列表推导式过滤掉空字符串，顺序与步骤顺序一致。
- `asdict(step)` 会递归转换：`evidence` 元组里的每个 `Evidence` 也被转成 dict，元组变成 list，所以 JSON 里是数组。

### 3.3 示例与 `main`

```python
def example() -> list[WorkflowStep]:
    return [
        WorkflowStep(1, "on-call engineer", "opens the alert", (Evidence("screen recording 01", "alert lacks service owner", True, 0.95),), "owner lookup"),
        WorkflowStep(2, "on-call engineer", "searches dashboards", (Evidence("incident 184", "three dashboards opened", True, 0.9),), "context switching"),
        WorkflowStep(3, "incident commander", "approves mitigation", (Evidence("runbook", "production writes require approval", False, 0.8),)),
    ]
```

| 步骤 | 证据 | 代码 `direct` | 按讲义阶梯 | 讲义"四样东西" |
|------|------|--------------|-----------|---------------|
| 1 打开告警 | 录屏 01 | True | 直接行为 | Friction：查 owner；Hidden state：告警里没有 owner，信息在别处 |
| 2 搜仪表盘 | incident 184（三个仪表盘被打开） | True | 若是事故系统的事件记录则为直接，若是事故报告则为工件 | Friction：上下文切换 |
| 3 批准缓解措施 | runbook | False | **工件**（讲义明确列出 runbook） | Authority：事故指挥官；**Handoff**：执行者从工程师变为指挥官 |

- ⚠️ 单元素元组必须写成 `(x,)`，末尾的逗号不能省，否则括号只是分组，`evidence` 会变成一个 `Evidence` 对象而不是元组。
- ⚠️ 讲义说 "Only the first two prove current behavior directly"，按字面 runbook 应计为直接证据，比例应为 1.0。代码标 `False` 也有道理：runbook 写的是**规定**（"写生产需要批准"），不能证明人们**实际**都这样做。这个分歧本身就说明：二元字段不足以表达讲义的证据阶梯。
- 步骤 2→3 是一次 handoff（actor 从 on-call engineer 变为 incident commander），代码没有显式标出；讲义说 AI 功能常在这里失败。
- `main` 与其它小节相同，写入 `<小节>/outputs/workflow-evidence.json` 后打印。⚠️ 每次运行覆盖该文件（内容不变）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 证据挂在每个步骤上 | 可追溯：每个说法都能回到来源 | 无 |
| `direct: bool` | 最简单的强弱区分 | 丢失四级阶梯；用 `kind` 枚举（direct/artifact/reported/inference）更忠实于讲义 |
| 按证据条数算比例 | 实现简单 | 会被"同一步骤堆证据"拉高；应按步骤统计并列出未被证实的步骤 |
| 一条直接证据即 grounded | 演示 status 概念 | 严重高估；应要求每步都有直接/工件证据 |
| 顺序必须 1..n 且按序 | 防止步骤错位、遗漏 | 无法表达异常分支和流程变体（讲义 Build It 与练习 4）；可加 `branch_from` 字段或多个 workflow |
| 只建模 actor/action/friction | 代码短小 | 缺 trigger/input/output/authority/hidden state，讲义的八字段表无法完整落地 |
| 置信度只做范围检查 | 保证数据合法 | 不参与判断；可设阈值，低置信度证据不计入 grounded |
| frozen dataclass + tuple | 证据记录不可变 | 修改需重建对象 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class Evidence`、`class WorkflowStep` | 自动生成构造器等方法，实例不可修改 |
| 变长元组类型注解 | `tuple[Evidence, ...]` | `...` 表示任意多个同类型元素；`tuple[int, str]` 则表示恰好两个元素 |
| 单元素元组 | `(Evidence(...),)` | 末尾逗号决定它是元组 |
| 字段默认值 | `friction: str = ""` | 有默认值的字段必须放在最后 |
| 列表推导式 | `[step.order for step in steps]` | 从对象列表中取一个属性 |
| 带条件的列表推导式 | `[step.friction for step in steps if step.friction]` | 过滤掉空字符串 |
| 双层生成器表达式 | `sum(item.direct for step in steps for item in step.evidence)` | 等价于嵌套 for；外层在前、内层在后 |
| 布尔值参与求和 | `sum(...)` 中的 `item.direct` | `bool` 是 `int` 的子类，`True == 1` |
| 列表相等比较 | `orders != list(range(1, len(steps) + 1))` | 逐元素且按顺序比较；`range(1, n+1)` 是 1..n |
| 链式比较 | `0 <= item.confidence <= 1` | 等价于 `0 <= c and c <= 1` |
| 条件表达式 | `round(direct / total, 2) if total else 0` | 防止除零 |
| `round(x, 2)` | `round(2/3, 2)` → `0.67` | 保留两位小数（银行家舍入，`round(0.125, 2)` 为 `0.12`） |
| f-string | `f"step {step.order} has no evidence"` | 字符串插值 |
| `dataclasses.asdict` | `asdict(step)` | 递归转 dict，嵌套的元组变为列表 |
| 类型注解 | `def audit(steps: list[WorkflowStep]) -> dict` | 说明参数与返回类型 |
| `pathlib` / `json` / `__main__` | `main()` | 与其它小节相同 |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，在小节目录副本中执行，输出与仓库内 `outputs/workflow-evidence.json` 逐字节相同），截取前半部分：

```text
{
  "status": "grounded",
  "issues": [],
  "direct_evidence_ratio": 0.67,
  "friction_points": [
    "owner lookup",
    "context switching"
  ],
  "steps": [
    {
      "order": 1,
      "actor": "on-call engineer",
      "action": "opens the alert",
      "evidence": [
        {
          "source": "screen recording 01",
          "observation": "alert lacks service owner",
          "direct": true,
          "confidence": 0.95
        }
      ],
      "friction": "owner lookup"
    },
    ...
    {
      "order": 3,
      "actor": "incident commander",
      "action": "approves mitigation",
      "evidence": [ { "source": "runbook", ..., "direct": false, "confidence": 0.8 } ],
      "friction": ""
    }
  ]
}
```

逐项解读：

- **status = grounded，issues 为空**：顺序 `[1, 2, 3]` 合法，每步都有证据，置信度都在范围内，且有直接证据。
- **direct_evidence_ratio = 0.67**：3 条证据中 2 条直接（录屏、incident 184）。按讲义"工件也能直接证明当前行为"的口径，runbook 也算，比例应为 1.0；按"runbook 只是规定"的口径，第 3 步其实没有被观察证实——代码没有把这一点暴露出来，因为 status 只需要至少一条直接证据。
- **friction_points**：`owner lookup`（告警里没有服务 owner，只能另查——同时也是一个隐藏状态的信号）和 `context switching`（三个仪表盘之间切换）。这两项会成为下一节假设地图中"告警上下文是否足以识别服务"这条高风险假设的来源。
- **steps 中 `friction: ""`**：第 3 步没有记录摩擦，但它是一次 handoff 加一个权限边界，讲义认为这里最容易出问题，值得补充观察。
- **讲义 Build It（部署记录缺失的异常路径）**：直接追加 order=3 的步骤会得到 `"workflow order must be contiguous from one"`（已实际运行验证），说明当前模型无法表达分支；扩展方案见测验 Q11。

---

## 7. 动手改一改

1. **讲义 Build It**：给 `WorkflowStep` 加 `branch_from: int | None = None`，添加一条"部署记录缺失 → 在团队聊天里问谁发了版"的异常步骤，让主路径的顺序检查保持不变（参考测验 Q11）。
2. **四级证据**：把 `direct: bool` 换成 `kind`（direct / artifact / reported / inference），按步骤输出 `ungrounded_steps` 和 `grounded_step_ratio`（参考测验 Q9）。
3. **讲义练习 3**：加 `authority: str` 字段，以及一条 "mitigation fails → roll back" 的失败恢复步骤；让 `audit` 列出所有 authority 边界（相邻步骤 authority 不同的位置）。
4. **讲义练习 4**：建模两个流程变体（先查部署记录 vs 先看仪表盘），写一个 `compare_variants(a, b)` 输出两者在哪一步开始分叉，而不是把它们合并。
5. 去重 issue：让越界置信度的消息带上证据序号（如 `step 1 evidence 2 has confidence -1 outside [0, 1]`），并修正空输入时比例返回整数 `0` 的问题。
6. 进阶：把 `confidence` 纳入 status——直接证据的置信度低于 0.5 时不计入，并写测试验证。

---

## 8. 常见坑

- **把访谈结论当事实**：自述是第三级证据，要标注；人们描述的"应该怎么做"常常不是"实际怎么做"。
- **只画 happy path**：异常和 handoff 是 AI 功能最常失败的地方。
- **把变体平均掉**：两种流程可能都合理，平均出来的流程没人在用。
- **用证据条数衡量覆盖率**：重复证据会掩盖没被观察的步骤。
- **单元素元组少写逗号**：`(Evidence(...))` 不是元组。
- **以为 `0 <= x <= 1` 能挡住所有异常值**：它挡得住 NaN 和越界，但挡不住类型错误（比如字符串会在比较时抛 `TypeError`）。
- **把顺序检查理解成集合检查**：`[1, 3, 2]` 也会被拒绝，消息里的 "contiguous" 容易误导。

---

## 9. 测试在验证什么

`code/tests/test_main.py` 用 `importlib.util.spec_from_file_location` 按文件路径加载 `main.py`（模块名 `lesson48`）。

| 测试 | 验证的性质 |
|------|-----------|
| `test_example_is_grounded` | 示例工作流的 status 为 `grounded` |
| `test_missing_step_evidence_is_reported` | 证据为空元组的步骤会报 `"step 1 has no evidence"` |
| `test_non_contiguous_order_is_rejected` | 只有一个 order=2 的步骤（不从 1 开始）会被拒绝 |
| `test_reversed_contiguous_order_is_rejected` | `[2, 1]` 这种"集合连续但顺序颠倒"的情况也会被拒绝——说明检查的是序列而不是集合 |
| `test_confidence_range_is_checked` | `confidence=1.2` 会报越界 |
| `test_friction_points_are_extracted` | 摩擦点按步骤顺序抽取，且跳过空字符串 |

运行方式（在小节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：

```text
Ran 6 tests in 0.000s

OK
```

测试**没有覆盖**的地方：

- `direct_evidence_ratio` 的数值（包括无证据时返回整数 `0`）；
- "只有一条直接证据也算 grounded"的边界——测验 Q4 的 10 步工作流；
- 重复的 order（`[1, 2, 2]`）和重复的越界消息；
- 异常分支与流程变体（讲义 Build It 与练习 4 的目标）。
