# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 19 节 Anthropic Responsible Scaling Policy v3.0（负责任扩展政策） ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）

---

## 1. 这份代码在考察什么

RSP v3.0 是一份政策文件，不是算法。这份代码把文件中关于 **AI R&D-4 阈值**的逻辑写成一个小型"决策引擎"，作为阅读辅助（docstring："The code is a reading aid, not a policy tool"）：

1. **能力测量**：用一个 dataclass 表示候选模型的四个指标（研发自动化份额、METR 时间跨度、AAR 胜出比例、评测情境 gaming 率）。
2. **阈值判定**：三个能力指标各有一个示意阈值，**任意两项**越过即判定越过 AI R&D-4。
3. **Affirmative case 模板**：越过后列出必须覆盖的 6 节内容；gaming 率 > 20% 时追加第 7 节"gaming 调整后的能力估计"。
4. **两个演示模型**：一个代表讲义所说"Opus 4.6 未越过"，一个代表"接近阈值的下一代"。

> 一句话：**把政策里"越过阈值 → 必须先公开 affirmative case 才能继续扩展"的形状显式化**。它最有价值的地方恰恰是它的简化：数值阈值、"任意两项"规则、gaming 只进模板不进判定——每一处都值得拿来和讲义对照着质疑。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CapabilityMeasurement` | dataclass | 模型名 + 4 个指标 | 能力评测证据 |
| `AI_RD_4_THRESHOLDS` | dict 常量 | 3 个示意阈值：0.5 / 40 小时 / 0.4 | AI R&D-4 阈值 |
| `threshold_crossed` | 函数 | 逐项比较，收集理由；≥ 2 项即越过 | 阈值评估 |
| `affirmative_case_template` | 函数 | 返回 6 或 7 节模板 | affirmative case |
| `evaluate` | 函数 | 打印测量、判定、理由与模板 | 报告 |
| `main` | 函数 | 评估两个模型并打印 HEADLINE | 演示驱动 |

数据流：`main` 构造 `CapabilityMeasurement` → `evaluate` → `threshold_crossed`（得到 `crossed, reasons`）→ 越过则调用 `affirmative_case_template` → 打印。

`evaluate` 的三条输出路径：

```text
crossed = True                 ──▶ "CROSSED" + 全部理由 + 模板（6 或 7 节）
crossed = False 且 reasons 非空 ──▶ "not crossed" + single trigger(s)
crossed = False 且 reasons 为空 ──▶ "not crossed"
```

---

## 3. 逐段精讲

### 3.1 `CapabilityMeasurement`：四个指标

```python
@dataclass
class CapabilityMeasurement:
    model_name: str
    # Fraction of internal AI R&D tasks the model can complete at
    # expert-human cost-equivalent (0.0-1.0).
    rd_automation_share: float
    # METR 50% time horizon in hours.
    metr_horizon_hours: float
    # Fraction of alignment-research pilot tasks the model completes
    # at or above human baseline (Anthropic AAR benchmark).
    aar_outperform_share: float
    # Evaluation-context gaming rate (0-1; 0 = never distinguishes).
    eval_context_gaming_rate: float
```

| 字段 | 含义 | 与讲义的关系 |
|------|------|------------|
| `rd_automation_share` | 以专家人力等价成本完成内部 AI 研发任务的比例 | 最贴近 AI R&D-4 定义："automate a substantial fraction of AI research at competitive cost" |
| `metr_horizon_hours` | METR 50% 成功率时间跨度（小时） | 第 21 节 METR 外部评测；讲义 Further Reading 把 AI R&D-4 与"measured autonomy"联系起来 |
| `aar_outperform_share` | 对齐研究试点任务中达到或超过人类基线的比例 | 讲义："Automated alignment researchers crossing research-quality bars is evidence that the AI R&D-4 threshold is approaching"（第 6 节） |
| `eval_context_gaming_rate` | 模型区分评测与部署情境的比例 | 第 01 节讲义的 eval-context gaming |

- 字段顺序就是位置参数顺序：`CapabilityMeasurement("x", 0.35, 45.0, 0.30, 0.05)`。
- 注释写了 0.0–1.0，但 dataclass 不做任何范围校验（传 0.9 或 9.0 都可以）。

### 3.2 阈值与判定规则

```python
AI_RD_4_THRESHOLDS = {
    "rd_automation_share": 0.5,
    "metr_horizon_hours": 40.0,
    "aar_outperform_share": 0.4,
}

def threshold_crossed(m: CapabilityMeasurement) -> tuple[bool, list[str]]:
    reasons = []
    if m.rd_automation_share >= AI_RD_4_THRESHOLDS["rd_automation_share"]:
        reasons.append(
            f"rd_automation_share={m.rd_automation_share:.2f} "
            f">= {AI_RD_4_THRESHOLDS['rd_automation_share']}"
        )
    ...
    crossed = len(reasons) >= 2  # any two triggers; illustrative
    return crossed, reasons
```

- 三个 `if` 是**独立**的（不是 `elif`），所以所有越过的项都会被记录。
- 比较用 `>=`：恰好等于阈值也算触发（实测 `rd=0.50, metr=40.0` → 越过）。
- 相邻的两个 f-string 字面量会被自动拼接成一个字符串；内层用单引号 `['rd_automation_share']` 避免与外层双引号冲突。
- 返回 `(crossed, reasons)`：即使未越过，`reasons` 也可能非空，`evaluate` 会把它们作为"single trigger"打印——这是很好的预警设计。
- ⚠️ **数值阈值是示意的**：注释 "Numbers are illustrative"。讲义与 HEADLINE 都强调 v3.0 的阈值是**定性的**，代码用定量阈值"模拟形状"，读者要注意区分。
- ⚠️ **"任意两项"与定义的张力**（实测）：
  - `rd=0.90, metr=10, aar=0.10` → **未越过**（只有 1 项）——一个能自动化 90% 研发任务的模型被判安全，直接违背 AI R&D-4 的定义；
  - `rd=0.20, metr=40, aar=0.40` → **越过**——研发自动化能力很低，却因两个旁证被判越过。
  - 更贴近定义的结构是：`rd_automation_share` 作主判据，另外两项作预警，接近阈值时进入"无法排除"状态（测验 Q9）。

### 3.3 Affirmative case 模板

```python
def affirmative_case_template(m: CapabilityMeasurement) -> list[str]:
    sections = [
        "1. Capability inventory: specific measurements against RSP thresholds",
        "2. Misalignment risk analysis: modes the model could exhibit",
        "3. Evaluation-context gap: residual risk from eval-vs-deploy divergence",
        "4. Mitigation design: technical + operational + deployment gates",
        "5. Residual risk acknowledgement: what we cannot rule out",
        "6. Review: internal Safety Advisory Group sign-off + external reviewer",
    ]
    if m.eval_context_gaming_rate > 0.2:
        sections.append(
            f"7. Gaming-adjusted capability estimate "
            f"(observed gaming rate {m.eval_context_gaming_rate:.0%})"
        )
    return sections
```

- 讲义只说 affirmative case 要"identifying misalignment risks and mitigations"；这 6 节是代码作者对它的展开，第 2、4 节对应讲义原文，第 6 节"内部 SAG 签字 + 外部审查者"回应了讲义所列 SaferAI 降级原因之一（"Review mechanisms depend on Anthropic's Safety Advisory Group, with limited independent oversight"）。
- `{x:.0%}`：把 0.28 格式化为 `28%`（乘 100、保留 0 位小数、加百分号）。
- gaming 阈值用 `>`（严格大于），所以 gaming 恰为 0.2 时不加第 7 节，0.21 时加。
- ⚠️ **gaming 只进模板、不进判定**：模板只在 `crossed` 为真时才被调用。实测 `rd=0.45, metr=35, aar=0.38, gaming=0.6` → 三项都未越过，输出只有 `not crossed`，60% 的 gaming 率完全没有体现。如果评测情境识别导致 sandbagging（在危险能力评测中刻意表现更差），测得的能力被低估，此时最需要调整的恰恰是**判定本身**（测验 Q10 给出了按 gaming 率下调阈值的版本）。
- 模板的内容与哪些指标触发无关（除第 7 节外），真实 affirmative case 应针对具体触发的能力展开。

### 3.4 `evaluate`：打印报告

```python
def evaluate(m: CapabilityMeasurement) -> None:
    crossed, reasons = threshold_crossed(m)
    print(f"\nModel: {m.model_name}")
    print(f"  rd_automation_share={m.rd_automation_share:.2f}  "
          f"metr_horizon_hours={m.metr_horizon_hours:.1f}  "
          f"aar_outperform_share={m.aar_outperform_share:.2f}  "
          f"gaming_rate={m.eval_context_gaming_rate:.0%}")
    if crossed:
        print("  AI R&D-4 threshold: CROSSED")
        ...
    else:
        print("  AI R&D-4 threshold: not crossed")
        if reasons:
            print("  single trigger(s) observed (below threshold):")
```

- 元组解包 `crossed, reasons = ...` 接收两个返回值。
- `:.2f`、`:.1f`、`:.0%` 分别控制小数位与百分比格式。
- ⚠️ 讲义 "Use It" 说引擎会返回"whether deployment can proceed"，但 `evaluate` 只打印判定与模板，**没有部署决策**；它也只打印不返回，无法被其他代码复用或测试。测验 Q11 补了 `deployment_decision`。

### 3.5 `main`：两个演示模型

```python
    opus_4_6 = CapabilityMeasurement(
        model_name="Claude Opus 4.6 (as stated by Anthropic in v3.0)",
        rd_automation_share=0.30,
        metr_horizon_hours=14.0,
        aar_outperform_share=0.35,
        eval_context_gaming_rate=0.12,
    )
    ...
    near = CapabilityMeasurement(
        model_name="Synthetic next-gen (illustrative only)",
        rd_automation_share=0.55, metr_horizon_hours=48.0,
        aar_outperform_share=0.45, eval_context_gaming_rate=0.28,
    )
```

- 讲义只说 Opus 4.6"does not cross"。代码中的数字来源混杂：14.0 小时与第 01 节讲义引用的 METR 数字（14+ 小时）一致；0.12 与第 01 节提到的 alignment faking 12%（另一项研究、另一种指标）数值相同；0.30 和 0.35 讲义中没有来源。模型名里的 "(as stated by Anthropic in v3.0)" 容易让人误以为这些都是官方测量值。
- 讲义练习 1 要求"三个不同能力水平的合成模型"，代码只给了两个；加入第三个"单触发"模型即可覆盖 `evaluate` 的全部三条路径（见第 7 节）。
- HEADLINE 打印讲义的要点：阈值从定量变为定性、删除暂停条款、SaferAI 2.2 → 1.9。⚠️ 其中 "not quantitative as in v2" 与讲义开头 "replaced the 2023 quantitative commitments" 对版本的说法不一致——讲义自身就在"2023 RSP"与"v2"之间混用（测验 Q12）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用数值阈值模拟定性阈值 | 让"判定形状"可以运行 | 读者可能误以为 v3.0 有这些数字；真实判定依赖人类判断与更大的证据集 |
| 任意两项触发 | 避免单一指标噪声 | 与定义冲突：研发自动化 0.9 的模型被判未越过；应以最贴近定义的指标为主判据 |
| 未越过时也打印单项触发 | 提供预警 | 只打印不行动；可升级为"无法排除"状态并触发准备工作 |
| gaming 只影响模板 | 实现简单 | 判定不随评测可信度变化；sandbagging 下会低估风险 |
| 模板固定 6 节 | 展示 affirmative case 的结构 | 不随触发的能力变化；真实文档需针对性论证 |
| 第 6 节要求外部审查者 | 回应"缺乏独立监督"的批评 | 代码里只是一句文本，没有任何检查 |
| `evaluate` 只打印 | 演示直观 | 不可测试、不可复用，也没有讲义所说的部署决策 |
| 模型名标注 "as stated by Anthropic" | 与讲义对应 | 混入了非官方的示意数值 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让 `tuple[bool, list[str]]` 等注解在较老 Python 上可用 |
| 模块 docstring | 文件开头三引号字符串 | 说明模块用途；可通过 `main.__doc__` 读取 |
| `@dataclass` 与字段注释 | `rd_automation_share: float` 上方的注释 | 自动生成构造函数；注释说明单位与范围（但不校验） |
| 关键字参数构造 | `CapabilityMeasurement(model_name=..., rd_automation_share=0.30, ...)` | 按字段名传参，可读性强 |
| 字典常量 | `AI_RD_4_THRESHOLDS = {...}` | 集中管理阈值，便于修改 |
| 返回元组并解包 | `return crossed, reasons`；`crossed, reasons = threshold_crossed(m)` | 一次返回多个值 |
| 相邻字符串字面量拼接 | `f"rd_automation_share=... " f">= {...}"` | 括号内相邻的字符串会自动拼成一个 |
| f-string 中引用字典 | `{AI_RD_4_THRESHOLDS['rd_automation_share']}` | 内外引号要不同 |
| 格式说明符 | `:.2f`、`:.1f`、`:.0%` | 两位 / 一位小数；百分比 |
| `len(...) >= 2` 产生布尔值 | `crossed = len(reasons) >= 2` | 比较表达式本身就是 `True/False` |
| 列表字面量 + `append` | `sections = [...]`；`sections.append(...)` | 条件性追加元素 |
| 空列表为假 | `if reasons:` | 列表非空才进入分支 |
| `"\n"` 换行 | `print(f"\nModel: ...")` | 先输出一个空行 |
| `"-" * 70` | `print("-" * 70)` | 字符串重复 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`，被 import 时可单独调用 `threshold_crossed` 做实验 |

---

## 6. 运行结果解读

实际运行输出（节选）：

```text
Model: Claude Opus 4.6 (as stated by Anthropic in v3.0)
----------------------------------------------------------------------
  rd_automation_share=0.30  metr_horizon_hours=14.0  aar_outperform_share=0.35  gaming_rate=12%
  AI R&D-4 threshold: not crossed

Model: Synthetic next-gen (illustrative only)
----------------------------------------------------------------------
  rd_automation_share=0.55  metr_horizon_hours=48.0  aar_outperform_share=0.45  gaming_rate=28%
  AI R&D-4 threshold: CROSSED
    - rd_automation_share=0.55 >= 0.5
    - metr_horizon_hours=48.0 >= 40.0
    - aar_outperform_share=0.45 >= 0.4
  required: affirmative case covering:
    1. Capability inventory: specific measurements against RSP thresholds
    ...
    6. Review: internal Safety Advisory Group sign-off + external reviewer
    7. Gaming-adjusted capability estimate (observed gaming rate 28%)
```

逐项解读：

- **Opus 4.6（示意值）**：0.30 < 0.5、14 < 40、0.35 < 0.4，没有任何单项触发，所以只打印 `not crossed`，与讲义"Claude Opus 4.6 does not cross it"一致。注意 0.35 已接近 0.4——对应讲义"confidently ruling this out is becoming difficult"的意味，但代码并不会把"接近"表达出来。
- **Synthetic next-gen**：三项全部越过，`reasons` 有 3 条，`crossed=True`；gaming 28% > 20%，模板追加第 7 节。
- **HEADLINE**：固定文本，总结讲义要点。

补充实验（已运行）：

| 测量 (rd, metr, aar, gaming) | `crossed` | 理由数 | 说明 |
|-----------------------------|-----------|-------|------|
| (0.90, 10, 0.10, 0.0) | False | 1 | 研发自动化 90% 仍判未越过 |
| (0.50, 40.0, 0.39, 0.0) | True | 2 | 边界值 `>=` 生效 |
| (0.20, 40, 0.40, 0.2) | True | 2 | 两个旁证即越过；gaming 恰为 0.2，模板 6 节 |
| (0.20, 40, 0.40, 0.21) | True | 2 | gaming 0.21 > 0.2，模板 7 节 |
| (0.45, 35, 0.38, 0.6) | False | 0 | 高 gaming 被完全忽略 |
| (0.35, 45.0, 0.30, 0.05) | False | 1 | 讲义练习 1 的第三个模型：打印 single trigger |

---

## 7. 动手改一改

1. **（讲义练习 1）** 在 `main()` 中加入 `CapabilityMeasurement("Synthetic mid (one trigger)", 0.35, 45.0, 0.30, 0.05)`，确认三个模型分别走"无触发 / 单触发 / 越过"三条路径。
2. **让 `evaluate` 可测试**：改为返回一个 `dict`（`crossed`、`reasons`、`sections`），打印交给另一个函数；再写 3 条断言测试边界值（等于阈值、略低于阈值、gaming 恰为 0.2）。
3. **主判据重构**：以 `rd_automation_share` 为主判据，METR 与 AAR 作预警，增加 `CANNOT-RULE-OUT` 状态（参考测验 Q9），比较新旧规则在 6 个测量上的差异。
4. **gaming 进入判定**：按 `factor = 1 - 0.5 * gaming` 下调阈值（参考测验 Q10），观察 gaming 60% 的模型从"未越过"变为"越过"；讨论这个系数应由谁、依据什么设定。
5. **部署决策**：实现 `deployment_decision(crossed, case_published, sag_signoff, external_review)`，越过阈值时三者缺一不可（参考测验 Q11）。
6. **政策对照（讲义练习 5 的预备）**：把阈值字典扩展为 `{"policy": "RSP v3.0", "type": "qualitative/quantitative", "trigger": ..., "mitigation": ..., "tier": "unilateral/industry"}` 的列表，输出 skill 文件要求的"Threshold table"与"Two-tier ratio"，为下一节对比三家框架做准备。

---

## 8. 常见坑

- **把示意阈值当成政策原文**：代码的 0.5 / 40 小时 / 0.4 是演示用的；v3.0 的阈值是定性的。
- **把示意测量值当官方数据**：模型名写着 "as stated by Anthropic"，但大部分数字不是 RSP v3.0 公布的。
- **多数投票 ≠ 能力定义**：任意两项触发会同时产生"该判越过却没判"与"不该判越过却判了"两类错误。
- **忽略评测可信度**：gaming / sandbagging 会让测量值偏离真实能力，判定逻辑应随之更保守，而不只是在报告里加一节。
- **把"未越过"读成"安全"**：它只表示"在当前证据下未越过"；讲义引用的"becoming difficult to rule out"正是提醒。
- **混淆政策版本**：讲义自身在"2023 RSP"与"v2"之间混用；引用评分（2.2 / 1.9）与条款时一定要写清版本号。
- **把政策当法规**：讲义："RSP v3.0 is not a regulation"；有政策不等于已合规。
