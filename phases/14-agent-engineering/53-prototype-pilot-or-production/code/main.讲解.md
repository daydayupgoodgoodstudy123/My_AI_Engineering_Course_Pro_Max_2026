# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 53 节 有意识地选择原型、试点或生产方案 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 code/main.py`（在小节目录下）；测试：`python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义的主张是：prototype、pilot、production 是三种**学习环境**，不是三个打磨等级；应根据当前未知、受众、数据、后果和就绪程度，选择能以最小不必要后果回答问题的阶段，并配上该阶段要求的控制措施。代码把这个判断写成一个约 90 行的"阶段选择器"：

1. **决策上下文**：`BuildDecision` 记录未知问题、是否需要真实用户/数据、后果等级（1–5）、是否可逆、运维是否就绪。
2. **阶段选择**：`choose_stage` 实现讲义流程图——不需要真实暴露就原型；需要真实暴露但未就绪、高后果或不可逆就试点；否则生产。
3. **阶段控制**：`required_controls` 返回每个阶段必须具备的控制清单。
4. **交付物**：三个示例分别落到三个阶段，写入 `outputs/stage-decisions.json`，记录"为什么是这个阶段、进入前必须有什么"。

看代码时也要注意它的简化：决策只看上下文、不看证据；控制清单与讲义有出入且不累积；没有任何阶段漂移检测。

> 一句话：**把"该原型、试点还是上线"从拍脑袋变成一个可复现、可审查的规则，并把每个阶段的控制要求写成清单。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `BuildDecision` | frozen dataclass | 未知、真实用户/数据需求、后果、可逆性、运维就绪 | 阶段选择的输入 |
| `choose_stage` | 函数 | 校验后果范围，按规则返回阶段名 | 讲义流程图 |
| `required_controls` | 函数 | 返回阶段对应的控制清单；未知阶段抛错 | 各阶段的必要控制 |
| `plan` | 函数 | 组合阶段、原始决策、控制清单 | 阶段决策记录 |
| `examples` | 函数 | 三个示例，分别对应三个阶段 | 讲义贯穿案例 |
| `main` | 函数 | 写出并打印 `outputs/stage-decisions.json` | 交付物 |
| `tests/test_main.py` | 单元测试 | 6 个测试，见第 9 节 | 规则与清单 |

数据流：`examples()` → 对每项调用 `plan()`（内部 `choose_stage()` → `required_controls()`，`asdict()`）→ 列表 → `json.dumps` → 写入并打印 `outputs/stage-decisions.json`。

---

## 3. 逐段精讲

### 3.1 `BuildDecision`：阶段选择的五个维度

```python
@dataclass(frozen=True)
class BuildDecision:
    unknown: str
    real_users_required: bool
    real_data_required: bool
    consequence: int
    reversible: bool
    operational_readiness: bool
```

- 对应讲义学习目标："Choose a build stage from the unknown, audience, data, consequence, and readiness."

| 字段 | 讲义概念 | 含义 |
|------|---------|------|
| `unknown` | 当前未知 | 本阶段要回答的学习问题（只记录，不参与判断） |
| `real_users_required` | audience | 回答这个问题是否必须有真实用户 |
| `real_data_required` | data | 是否必须有真实数据 |
| `consequence` | consequence | 1–5 的后果等级 |
| `reversible` | （讲义流程图未出现） | 出错能否撤回 |
| `operational_readiness` | readiness / operations ready | 运维能力是否就绪 |

- 注意字段的语义是"**回答这个未知需要什么**"，而不是"系统现在有什么"。这正是讲义"按学习问题分类，而不是按部署状态分类"（练习 1）的体现。
- ⚠️ `unknown` 是自由文本，不参与任何判断；也没有"已有哪些证据"的字段（见 3.2）。
- ⚠️ 类型注解 `consequence: int` 在运行时不检查，`3.5`、`True` 都能传进来。

### 3.2 `choose_stage`：讲义流程图的代码版

```python
def choose_stage(decision: BuildDecision) -> str:
    if not 1 <= decision.consequence <= 5:
        raise ValueError("consequence must be from one to five")
    if not decision.real_users_required and not decision.real_data_required:
        return "prototype"
    if not decision.operational_readiness or decision.consequence >= 4 or not decision.reversible:
        return "pilot"
    return "production"
```

与讲义 mermaid 图对照：

```text
Unknown → 需要真实用户或数据？ ──否──→ Prototype
                 │是
                 ↓
        后果有界且运维就绪？ ──否──→ Pilot
                 │是
                 ↓
             Production
```

- 第一个判断：`1 <= consequence <= 5` 是 Python 的**链式比较**。越界（如 0、6）抛 `ValueError`。
- 第二个判断：两者都不需要 → 原型。此时后果、可逆性都不再考虑——因为原型不接触真实用户和数据，后果已被隔离。实测 `BuildDecision("x", False, False, 5, False, False)` 返回 `"prototype"`。
- 第三个判断把讲义的"Consequence bounded and operations ready?"展开成三个条件，**任一不满足**就停在试点：
  - 运维未就绪；
  - 后果 ≥ 4（"有界"被量化为 1–3）；
  - 不可逆（讲义流程图没有这一项，是代码的补充）。
- 全部输入共 2×2×5×2×2 = 80 种组合，实测：prototype 20 种、pilot 51 种、production 9 种（production = 3 种用户/数据组合 × 后果 1–3 × 可逆 × 就绪）。规则明显偏保守。
- ⚠️ **只看上下文，不看证据**：讲义 Build It 要你把试点示例改成低后果 + 运维就绪——实测立刻返回 `"production"`，可那个示例的未知是"工程师会不会信任推荐"，只有试点能回答。讲义学习目标是"Delay real authority until evidence **and** operations justify it"，代码只实现了后半句（测验 Q9）。
- ⚠️ 后果 ≥ 4 永远不能进入生产，也没有任何证据能改变这一点，现实中可能导致"永久试点"（测验 Q17）。
- ⚠️ 校验漏洞：`3.5` 与 `True` 都能通过 `1 <= x <= 5`（`bool` 是 `int` 的子类，`True == 1`）。

### 3.3 `required_controls`：每个阶段的控制清单

```python
def required_controls(stage: str) -> list[str]:
    controls = {
        "prototype": ["synthetic or recorded inputs", "discardable implementation", "learning question"],
        "pilot": ["limited audience", "rollback", "human owner", "audit trail", "exit criteria"],
        "production": [
            "service level objective",
            "on-call owner",
            "security review",
            "cost and capacity controls",
            "rollback",
            "recovery",
            "continuous monitoring",
            "retirement path",
        ],
    }
    if stage not in controls:
        raise ValueError("unknown stage")
    return controls[stage]
```

- 用字典做"阶段 → 清单"的查表；未知阶段（包括大小写不同的 `"Pilot"`）显式抛错，而不是返回空清单——空清单会被误读为"不需要任何控制"。
- 每次调用都新建字典和列表，调用方修改返回的列表不会污染下一次调用（实测 `append` 后再取，结果不受影响）。
- 与讲义清单的差异（详见测验 Q11）：

| 阶段 | 讲义有、代码缺 |
|------|---------------|
| Prototype | isolated、narrow、不做虚假运维承诺 |
| Pilot | **outcome 与 guardrail 阈值**、有界的时长与权限、退出标准中的 stop |
| Production | privacy review、incident ownership |

- ⚠️ 清单**不累积**：实测试点有而生产没有的是 `{"limited audience", "human owner", "audit trail", "exit criteria"}`。其中 **audit trail** 在生产中消失是真正的缺口——权限和影响面越大，审计越重要。
- ⚠️ 清单只是字符串，无法检查"是否真的具备"。讲义要求"The stage should be observable from the system itself"，生产中应把每一项变成可验证的条目（例如回滚命令存在且演练过）。

### 3.4 `plan`、`examples` 与 `main`

```python
def plan(decision: BuildDecision) -> dict:
    stage = choose_stage(decision)
    return {"stage": stage, "decision": asdict(decision), "required_controls": required_controls(stage)}


def examples() -> list[BuildDecision]:
    return [
        BuildDecision("Can the service be identified from an alert?", False, False, 2, True, False),
        BuildDecision("Will engineers trust the recommendation?", True, True, 4, True, False),
        BuildDecision("Can the workflow meet its SLO?", True, True, 2, True, True),
    ]
```

- `plan` 把"结论 + 输入 + 要求"放在同一条记录里：讲义"What You Keep"说这个文件"records why each stage is justified and which controls must exist before the next one"。保留原始输入 `decision`，审查者可以复核规则是否被正确应用。
- 三个示例构成一条递进链，对应事故诊断案例的三个未知：

| 未知 | 用户/数据 | 后果 | 可逆 | 就绪 | 阶段 | 判定原因 |
|------|----------|------|------|------|------|---------|
| 能否从告警识别服务？ | 否/否 | 2 | 是 | 否 | prototype | 机制问题，可用录制告警回答 |
| 工程师会信任推荐吗？ | 是/是 | 4 | 是 | 否 | pilot | 后果 ≥ 4 且未就绪（两条都触发） |
| 工作流能达到 SLO 吗？ | 是/是 | 2 | 是 | 是 | production | 全部条件满足 |

- 第一个示例的 `operational_readiness=False` 不影响结果——原型分支先返回了。
- `main` 中 `json.dumps([plan(item) for item in examples()], indent=2)`：列表推导式生成三条记录，整体序列化为 JSON 数组。

```python
def main() -> None:
    output = Path(__file__).resolve().parents[1] / "outputs" / "stage-decisions.json"
    output.write_text(json.dumps([plan(item) for item in examples()], indent=2) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))
```

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 5 个字段描述决策上下文 | 与讲义的五个维度一一对应，规则可读 | 没有"证据"字段，低后果 + 就绪就直接生产；应加入试点结果或证据引用 |
| 后果用 1–5 整数 | 简单的有序等级 | 运行时不校验类型；控制措施能降低有效后果，但模型无法表达 |
| 把"可逆性"加入试点条件 | 不可逆的动作需要更谨慎 | 讲义流程图没有，需要在讲义里说明 |
| 后果 ≥ 4 一律试点 | 默认保守 | 高后果系统可能"永久试点"，实际上是缺控制的生产 |
| 控制清单用字典查表 | 一目了然 | 不累积、不可验证；与讲义清单有出入 |
| 未知阶段抛 `ValueError` | 不让空清单冒充"无需控制" | 调用方需处理异常 |
| 记录输入 + 结论 + 控制 | 可审查、可复核 | 没有时间戳、决策人、证据链接；没有漂移检测 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class BuildDecision` | 不可变数据类；决策记录创建后不应被修改 |
| 位置参数构造 dataclass | `BuildDecision("...", False, False, 2, True, False)` | 按字段顺序传参；字段多时建议用关键字参数提高可读性 |
| 链式比较 | `1 <= decision.consequence <= 5` | 等价于 `1 <= c and c <= 5` |
| `bool` 是 `int` 的子类 | `True` 能通过 `1 <= x <= 5` | `True == 1`、`False == 0`；类型检查要先排除 `bool` |
| `not` 与 `and` / `or` | `not a and not b`、`not r or c >= 4 or not v` | 布尔逻辑；`or` 短路求值 |
| 提前 `return` | `choose_stage` 中的三个 `return` | 卫语句风格，避免深层嵌套 |
| `raise ValueError(...)` | 越界后果、未知阶段 | 用异常拒绝非法输入 |
| 字典字面量查表 | `controls = {"prototype": [...], ...}` | 用数据代替 `if/elif` 链 |
| 成员测试 | `stage not in controls` | 判断字典中是否有该键 |
| `dataclasses.asdict` | `asdict(decision)` | 转成普通 dict 以便序列化 |
| 列表推导式 | `[plan(item) for item in examples()]` | 对每个示例生成一条记录 |
| `json.dumps` 布尔值 | `true` / `false` | Python 的 `True/False` 序列化为 JSON 的 `true/false` |
| `pathlib.Path` | `Path(__file__).resolve().parents[1] / "outputs"` | 定位小节目录下的输出文件 |
| 返回类型注解 | `-> str`、`-> list[str]`、`-> dict` | 帮助阅读与静态检查 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，在临时副本中运行；生成的 JSON 与仓库中的 `outputs/stage-decisions.json` 逐字节一致）。压缩后的输出：

```text
[
  { "stage": "prototype",
    "decision": { "unknown": "Can the service be identified from an alert?",
                  "real_users_required": false, "real_data_required": false,
                  "consequence": 2, "reversible": true, "operational_readiness": false },
    "required_controls": [ "synthetic or recorded inputs", "discardable implementation", "learning question" ] },
  { "stage": "pilot",
    "decision": { "unknown": "Will engineers trust the recommendation?",
                  "real_users_required": true, "real_data_required": true,
                  "consequence": 4, "reversible": true, "operational_readiness": false },
    "required_controls": [ "limited audience", "rollback", "human owner", "audit trail", "exit criteria" ] },
  { "stage": "production",
    "decision": { "unknown": "Can the workflow meet its SLO?",
                  "real_users_required": true, "real_data_required": true,
                  "consequence": 2, "reversible": true, "operational_readiness": true },
    "required_controls": [ "service level objective", "on-call owner", "security review",
                           "cost and capacity controls", "rollback", "recovery",
                           "continuous monitoring", "retirement path" ] }
]
```

逐项解读：

- **第 1 条 prototype**：识别机制可以用录制的告警来验证，不需要真实用户或数据；控制要求是"合成或录制输入、可丢弃实现、明确学习问题"。
- **第 2 条 pilot**：信任只能在真实工程师身上观察，必须真实暴露；后果 4 且运维未就绪，所以停在试点；控制包括有限受众、回滚、负责人、审计、退出标准。
- **第 3 条 production**：低后果、可逆、运维就绪，进入生产；控制清单是 8 项全生命周期要求。注意它**没有** audit trail。

附加实验（均实测）：

| 改动 | 结果 | 说明 |
|------|------|------|
| 第 2 条改为后果 2、运维就绪（讲义 Build It） | `production` | 规则不看试点证据，"信任"这个未知没被回答就上线了 |
| 后果 5、可逆、就绪 | `pilot` | 高后果永远停在试点 |
| 后果 0 或 6 | `ValueError` | 越界被拒 |
| 后果 3.5 或 `True` | `production` | 类型未校验 |
| `required_controls("Pilot")` | `ValueError: unknown stage` | 大小写敏感 |

---

## 7. 动手改一改

1. **（入门）** 讲义 Build It：把第二个示例改成后果 2、运维就绪，确认结果变为 `production`，并写下进入生产前还需要哪些证据（试点阈值达标、退出判定为 expand、回滚演练等）。
2. **（入门）** 加强校验：后果必须是 `int` 且不是 `bool`；四个布尔字段必须是 `bool`（参考测验 Q10）。
3. **（进阶）** 给 `choose_stage` 增加证据输入（如 `pilot_evidence_passed` 或 `pilot_report_path`），没有通过的试点证据就不能进入生产；同步更新测试 `test_ready_reversible_work_can_be_production`。
4. **（进阶）** 让控制清单与讲义对齐并累积：试点补上"outcome and guardrail thresholds""bounded duration and authority"，生产保留 audit trail、加上 privacy review；写一个测试断言"生产清单包含 audit trail"。
5. **（进阶）** 讲义练习 2：把 `"exit criteria"` 展开为结构化的 `{"expand": ..., "revise": ..., "stop": ...}`，并要求 stop 条件非空。
6. **（挑战）** 讲义练习 3 与"阶段漂移"：实现 `detect_drift(declared_stage, observed)`，`observed` 从配置文件读取（是否有真实用户、能否读生产数据、是否有写权限、是否有负责人、是否有回滚），对原型连上生产数据等情况报警（参考测验 Q12）。

---

## 8. 常见坑

- **按部署状态而不是学习问题分类**：已经部署的东西不一定是生产；没部署的东西也可能需要试点级的控制（例如用生产数据做的离线分析）。
- **把"运维就绪"当成"可以上线"**：就绪只是必要条件，还需要证据。
- **用 `int` 注解当作类型检查**：dataclass 不在运行时校验类型。
- **忘了 `bool` 是 `int`**：`isinstance(True, int)` 为 `True`。
- **以为控制清单是累积的**：代码中生产清单并不包含试点的 audit trail。
- **用横幅代替技术控制**：讲义明确说不够；阶段要体现在配置、访问控制和遥测里。
- **高后果项目"永久试点"**：形式上是试点，实际承担生产流量，却只有试点的控制。

---

## 9. 测试在验证什么

`code/tests/test_main.py` 用 `importlib.util.spec_from_file_location` 按路径加载 `main.py`（模块名 `lesson53`）。

| 测试 | 验证的性质 |
|------|-----------|
| `test_no_real_users_or_data_means_prototype` | 示例 1（不需要用户和数据）→ `prototype` |
| `test_high_consequence_means_pilot` | 示例 2（后果 4）→ `pilot`；注意该示例同时运维未就绪，测试并不能单独证明"后果 ≥ 4"这一条件在起作用 |
| `test_ready_reversible_work_can_be_production` | 示例 3（低后果、可逆、就绪）→ `production` |
| `test_invalid_consequence_is_rejected` | 后果为 0 时抛 `ValueError` |
| `test_pilot_has_exit_criteria` | 试点清单包含 `"exit criteria"` |
| `test_production_has_full_lifecycle_controls` | 生产清单包含成本与容量控制、恢复、退役路径——全生命周期要求 |

运行方式（在小节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：`Ran 6 tests in 0.001s — OK`，全部通过。

可补充的测试：只改后果（就绪 + 可逆 + 后果 4）确认 `pilot`，以隔离"高后果"条件；不可逆 → `pilot`；后果 6、3.5、`True` 的拒绝；未知阶段名抛错；生产清单包含 audit trail（当前会失败，正好暴露缺口）。
