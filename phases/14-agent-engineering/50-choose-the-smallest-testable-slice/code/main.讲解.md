# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 50 节 选择足以改变决策的最小实现范围 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：在小节目录下 `python3 code/main.py`；测试 `python3 -m unittest discover code/tests -v` ｜ **依赖**：仅标准库（`json`、`dataclasses`、`pathlib`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义的核心流程是：**先定义必须证明的集合（required proof）→ 用它作为资格门淘汰候选切片 → 只在合格切片中比较"证据 / 投入与风险"→ 选一个去构建**。这份约 75 行的代码完整实现了这条流程：

1. **切片的数据化**：`Slice` 记录讲义表格中的五个比较维度（成效价值、减少的不确定性、投入、后果、可逆性），以及它能证明的假设 `proves`。
2. **打分**：`score` = 收益 / （投入 + 风险罚分），不可逆的后果罚分是可逆的 4 倍。
3. **资格门 + 选择**：`choose` 先用集合子集判断过滤，再取分数最高者。
4. **决策记录**：`decision` 输出必证集合、选中的切片和全部备选，写入 `outputs/slice-decision.json`。

> 一句话：**先问"它能不能回答这次必须回答的问题"，再问"它是不是最便宜、最安全的那个"**。讲义说"资格门比算术更重要"，代码用一行 `required_proof <= set(item.proves)` 实现了它。同时要看清：输入校验不全（可除零）、输出不标注不合格原因、没有停止规则、必证集合是硬编码的。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Slice` | frozen dataclass | 名称、价值、减少的不确定性、投入、后果、是否可逆、能证明的假设 | 用证明的假设定义切片 |
| `score` | 函数 | `(价值 + 不确定性) / (投入 + 后果 × 系数)`，3 位小数 | 证据 / 投入与风险 |
| `choose` | 函数 | 资格门（子集判断）+ 取最大 `(score, -effort, name)` | 资格门 > 算术 |
| `decision` | 函数 | 组装必证集合、选中切片、备选列表 | 决策记录 |
| `example` | 函数 | 只读回放 / 生产自动修复 / 仪表盘原型 | 讲义三个例子 |
| `main` | 函数 | 写 `outputs/slice-decision.json` 并打印 | 留存产物 |
| `tests/test_main.py` | 单元测试 | 5 个测试（见第 9 节） | 可执行验证 |

数据流：`example()` + 硬编码的必证集合 `{"service-identification", "operator-trust"}` → `decision()`（内部 `choose()` → 过滤 → `score()` → `max`）→ `json.dumps` → `outputs/slice-decision.json`。

---

## 3. 逐段精讲

### 3.1 `Slice`：用它能证明的东西定义切片

```python
@dataclass(frozen=True)
class Slice:
    name: str
    outcome_value: int
    uncertainty_reduced: int
    effort: int
    consequence: int
    reversible: bool
    proves: tuple[str, ...]
```

| 字段 | 讲义维度 | 方向 |
|------|---------|------|
| `outcome_value` | Outcome value | 越多越好 |
| `uncertainty_reduced` | Uncertainty reduced | 越多越好 |
| `effort` | Effort | 越少越好 |
| `consequence` | Consequence | 越少越好 |
| `reversible` | Reversibility | 越高越好（代码中简化为布尔） |
| `proves` | 切片能证明的假设标签 | 用于资格门 |

- `proves` 用元组存，保证 frozen dataclass 整体不可变；使用时转成 `set` 做集合运算。
- ⚠️ 讲义的 Reversibility 是一个程度（"More is better"），代码压成了布尔值，只有"可逆 / 不可逆"两档。
- ⚠️ 没有停止规则字段，讲义 "Add a Stop Rule" 一节和练习 4 在代码中没有体现。

### 3.2 `score`：收益除以成本与风险

```python
def score(item: Slice) -> float:
    if item.effort < 1:
        raise ValueError("effort must be positive")
    risk_penalty = item.consequence * (2 if not item.reversible else 0.5)
    return round((item.outcome_value + item.uncertainty_reduced) / (item.effort + risk_penalty), 3)
```

- **分子**：成效价值 + 减少的不确定性，即"这个切片能带来多少价值和信息"。
- **分母**：投入 + 风险罚分。罚分 = 后果 × 系数，不可逆系数 2、可逆系数 0.5，相差 **4 倍**。这是讲义"Prefer reversible evidence over premature production commitment"的数值化。
- `effort < 1` 的检查是为了防止除以零——在 consequence 非负时，分母至少为 1。
- ⚠️ **只检查了 effort**：`consequence` 为负时分母可以为 0 或负数。`effort=1, consequence=-2, reversible=True` → 分母 `1 - 1 = 0` → `ZeroDivisionError`；`consequence=-3` 返回 `-4.0`（已实际运行验证）。`effort=1.5` 也能通过检查，尽管注解是 `int`。
- `round(..., 3)` 只用于展示，但 `choose` 也拿这个**已四舍五入**的值来比较，极接近的两个分数可能被视为相等，从而进入平局规则。
- 讲义："The lab's score is intentionally simple. The eligibility gate matters more than the arithmetic."——不要在这个公式上过度优化。

### 3.3 `choose`：资格门，然后才是分数

```python
def choose(items: list[Slice], required_proof: set[str]) -> Slice:
    candidates = [item for item in items if required_proof <= set(item.proves)]
    if not candidates:
        raise ValueError("no slice proves the required assumptions")
    return max(candidates, key=lambda item: (score(item), -item.effort, item.name))
```

- **资格门**：`required_proof <= set(item.proves)` 是集合的**子集**判断——必证集合中的每一项，切片都必须证明。这一行就是讲义流程图里的 "Covers all proof?"。
- **没有合格切片就报错**，而不是退而求其次选一个"最接近的"。这与讲义一致：不覆盖必证项的切片不能回答这次的问题，正确的反应是设计新切片。
- **比较键** `(score, -effort, name)`：先比分数；分数相同时 `-effort` 越大（投入越小）越好；再相同时比名字。
  - ⚠️ 用的是 `max`，所以名字**字母序靠后**的胜出（`"zeta"` 胜 `"alpha"`）。这是确定性的，但没有业务含义。
  - ⚠️ `required_proof` 为空集时，空集是任何集合的子集，资格门**静默失效**，退化为纯打分。生产中应把空必证集合当作错误。
- 讲义 Build It："Add a cheaper candidate that proves only one required assumption. It should remain ineligible even if its numerical score is high." 实测：只证明 `service-identification` 的 "log grep script" 得 6.667，仍被淘汰，选中的还是 replay。

### 3.4 `decision`：决策记录

```python
def decision(items: list[Slice], required_proof: set[str]) -> dict:
    selected = choose(items, required_proof)
    return {
        "required_proof": sorted(required_proof),
        "selected": {**asdict(selected), "score": score(selected)},
        "alternatives": [{**asdict(item), "score": score(item)} for item in items if item != selected],
    }
```

- `sorted(required_proof)`：集合无序，排序后转成列表，保证 JSON 输出稳定（集合本身也不能被 `json.dumps` 序列化）。
- `{**asdict(selected), "score": ...}`：展开字段后追加分数。
- ⚠️ **alternatives 不标注是否合格**：dashboard mockup（2.667）看起来像"接近的第二名"，实际上它缺 `service-identification`，根本没有资格。讲义说这个文件"记录了为什么这个切片是能改变决策的最小切片"，但"为什么其它的不行"没有被记录（测验 Q10 给出带 `eligible` 和 `missing_proof` 的改进版）。
- ⚠️ `item != selected` 是**值相等**比较（dataclass 自动生成 `__eq__`）：若列表里有两个字段完全相同的切片，它们会一起被排除。用 `item is not selected` 按对象身份比较更准确。

### 3.5 示例与 `main`

```python
def example() -> list[Slice]:
    return [
        Slice("read-only incident replay", 4, 5, 2, 1, True, ("service-identification", "operator-trust")),
        Slice("production auto-remediation", 5, 4, 10, 5, False, ("service-identification", "operator-trust")),
        Slice("dashboard mockup", 2, 2, 1, 1, True, ("operator-trust",)),
    ]
```

| 切片 | 讲义对应 | 合格？ | 分子 | 分母 | score |
|------|---------|-------|------|------|-------|
| read-only incident replay | "tests service identification and operator trust" | 是 | 9 | 2 + 0.5 = 2.5 | **3.6** |
| production auto-remediation | "tests everything at once with unacceptable consequence" | 是 | 9 | 10 + 10 = 20 | 0.45 |
| dashboard mockup | "may test comprehension but not data feasibility"（UI-only 假最小） | 否，缺 service-identification | 4 | 1 + 0.5 = 1.5 | 2.667 |

- 三个切片恰好对应讲义"Vertical Means Evidence End to End"一节的三个例子。
- 必证集合 `{"service-identification", "operator-trust"}` 在 `main` 里**硬编码**。讲义说它应来自第 49 节最高风险的开放假设；代码没有读取 `assumption-map.json`（连接方法见测验 Q12）。
- `main` 写入 `<小节>/outputs/slice-decision.json`。⚠️ 每次运行会覆盖该文件（内容不变）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 资格门放在打分之前 | 非补偿性约束：便宜不能弥补"答不了问题" | 必证集合为空时静默失效；应校验非空 |
| 无合格切片直接抛错 | 迫使团队设计新切片，而不是凑合 | 调用方需处理异常 |
| 收益 / 成本比 | 直观的"每单位投入与风险能换多少证据" | 主观打分，公式不通用；讲义明确说它"intentionally simple" |
| 不可逆罚分 ×2、可逆 ×0.5 | 让可逆证据明显占优 | 系数随意；可逆性只有两档 |
| 只校验 effort ≥ 1 | 防止最常见的除零 | 负的后果仍可除零或得负分；应校验所有维度 |
| 平局 `(-effort, name)` 取 max | 确定性 | 名字靠后的胜出，无业务含义 |
| alternatives 不标资格 | 代码短 | 读者会误读分数；应附 `eligible`、`missing_proof` |
| 必证集合硬编码 | 本节独立可运行 | 与第 49 节断开；应从假设地图生成 |
| 无停止规则 | 代码短 | 讲义要求实现前写好失败时怎么办；可加 `stop_rule` 字段并校验 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass(frozen=True)` | `class Slice` | 不可变记录；自动生成 `__eq__`（按值比较）和 `__hash__` |
| 变长元组注解与单元素元组 | `proves: tuple[str, ...]`、`("operator-trust",)` | 末尾逗号让括号成为元组 |
| 集合子集运算 | `required_proof <= set(item.proves)` | `a <= b` 表示 a 是 b 的子集；空集是任何集合的子集 |
| 集合差 | `required_proof - set(item.proves)`（测验改进版） | 得到缺失的必证项 |
| `set()` 转换 | `set(item.proves)` | 元组转集合以做集合运算 |
| 条件表达式 | `2 if not item.reversible else 0.5` | 一行 if/else |
| `round(x, 3)` | `round(9 / 1.5, 3)` → `2.667` | 保留 3 位小数 |
| `raise ValueError` | 投入 < 1、无合格切片 | 用异常表达"无法给出合法结果" |
| `max` + 元组键 | `key=lambda item: (score(item), -item.effort, item.name)` | 按元组逐项比较；负号把"越小越好"转成"越大越好" |
| 字典解包 | `{**asdict(selected), "score": score(selected)}` | 展开并追加键 |
| 带条件的列表推导式 | `[... for item in items if item != selected]` | 过滤掉选中的切片 |
| `!=` 与 `is not` | `item != selected` | 前者比较值（dataclass 字段全等即相等），后者比较对象身份 |
| `sorted(set)` | `sorted(required_proof)` | 集合无序且不能直接 JSON 序列化，排序后得到列表 |
| `pathlib` / `json` / `__main__` | `main()` | 与其它小节相同 |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，在小节目录副本中执行，输出与仓库内 `outputs/slice-decision.json` 逐字节相同）：

```text
{
  "required_proof": [
    "operator-trust",
    "service-identification"
  ],
  "selected": {
    "name": "read-only incident replay",
    "outcome_value": 4,
    "uncertainty_reduced": 5,
    "effort": 2,
    "consequence": 1,
    "reversible": true,
    "proves": [
      "service-identification",
      "operator-trust"
    ],
    "score": 3.6
  },
  "alternatives": [
    {
      "name": "production auto-remediation",
      ...
      "reversible": false,
      "score": 0.45
    },
    {
      "name": "dashboard mockup",
      ...
      "proves": [
        "operator-trust"
      ],
      "score": 2.667
    }
  ]
}
```

逐项解读：

- **required_proof** 按字母序排列；它就是第 49 节两条最高风险的开放假设对应的标签（"能识别服务"27 分、"自动修复可接受"25 分 → 通过"先测审批流"落到 operator-trust）。
- **selected = read-only incident replay，score 3.6**：合格的两个切片中，它的投入（2 vs 10）和风险罚分（0.5 vs 10）都远低于自动修复，而收益分子相同（都是 9）。
- **production auto-remediation 0.45**：它能证明同样的东西，但"tests everything at once with unacceptable consequence"。即使把它改为可逆，分数也只有 0.72，投入过高同样是问题。
- **dashboard mockup 2.667**：分数排第二，但它**不合格**——只证明 operator-trust。输出里看不出这一点，这是本节代码最值得改进的地方。
- **讲义 Build It 验证**：加入只证明一项、分数 6.667 的 "log grep script" 后，仍选中 replay（已实际运行验证）。

---

## 7. 动手改一改

1. **讲义 Build It**：加入 "log grep script"（5, 5, 1, 1, True, 只证明 service-identification），确认它不被选中；再把 required proof 改为只有 `{"service-identification"}`，观察它会不会胜出、为什么。
2. **输出资格信息**：让 `decision` 为每个切片附上 `eligible` 和 `missing_proof`，合格备选排前面（参考测验 Q10）。
3. **严格校验**：所有数值维度必须是整数，effort ≥ 1，consequence ≥ 0；必证集合不能为空（参考测验 Q9）。
4. **讲义练习 4**：加 `stop_rule` 字段（pass / fail / ambiguous），拒绝"所有结果都继续构建"的切片（参考测验 Q11）。
5. **连接第 49 节**：读 `../49-map-assumptions-and-risk/outputs/assumption-map.json`，用一张"假设 → 证明标签"映射表生成必证集合（参考测验 Q12）。
6. **讲义练习 1、3**：为同一成效设计三个不同后果等级的切片；再从 replay 中去掉一项**不影响必证项**的能力（例如把回放数从 10 降到 6，effort 由 2 降为 1），确认它仍然合格且分数上升；作为对照，去掉操作员信任问卷（`proves` 只剩 service-identification）后它会失去资格。

---

## 8. 常见坑

- **先打分后过滤**：便宜的假最小会在分数上胜出；资格门必须在前。
- **必证集合为空**：空集是任何集合的子集，所有切片都"合格"，资格门形同虚设。
- **用去掉不确定性的方式让切片变小**：UI-only、happy-path 都属于这种。
- **只校验部分输入**：effort 有检查、consequence 没有，负值就能制造除零。
- **把四舍五入后的分数用于比较**：展示用的精度不该影响决策。
- **以为 `!=` 比较的是"是不是同一个对象"**：dataclass 的 `__eq__` 比较字段值。
- **没有停止规则就开工**：结果出来后才决定"怎么解释"，任何结果都会被解读成"继续"。

---

## 9. 测试在验证什么

`code/tests/test_main.py` 用 `importlib.util.spec_from_file_location` 按文件路径加载 `main.py`（模块名 `lesson50`）。

| 测试 | 验证的性质 |
|------|-----------|
| `test_read_only_replay_wins` | 示例 + 两项必证时选中只读回放 |
| `test_slice_must_cover_required_proof` | 必证 `{"billing"}` 无人覆盖时抛出消息含 "no slice" 的 `ValueError`——资格门不会退而求其次 |
| `test_zero_effort_is_invalid` | 投入为 0 时 `score` 抛 `ValueError` |
| `test_irreversible_consequence_reduces_score` | 其余相同时，不可逆切片的分数低于可逆切片（(5+5)/(2+2)=2.5 > (5+5)/(2+8)=1.0） |
| `test_decision_records_alternatives` | 必证只有 `operator-trust` 时三个切片都合格，选中一个，alternatives 有 2 个 |

运行方式（在小节目录下）：

```bash
python3 -m unittest discover code/tests -v
```

实际运行结果：

```text
Ran 5 tests in 0.000s

OK
```

测试**没有覆盖**的地方：

- 讲义 Build It 的核心场景："高分但只证明一项"的切片必须保持不合格——当前测试只验证了"无人合格时报错"；
- 负的 consequence 导致的除零或负分；
- 空必证集合让资格门失效；
- 平局时的选择结果；
- alternatives 中不合格切片的标注（当前代码也没有这个功能）。
