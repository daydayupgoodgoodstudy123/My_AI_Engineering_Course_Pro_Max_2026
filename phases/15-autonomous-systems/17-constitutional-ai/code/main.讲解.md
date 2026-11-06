# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 17 节 Constitutional AI 与规则覆盖 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）

---

## 1. 这份代码在考察什么

讲义的核心是 2026 Claude Constitution 的结构："硬编码底线 + 四层优先级"。这份代码把这个结构写成一个约 50 行的裁决器（resolver）：

1. **硬编码层**：一组禁止短语（生物武器 uplift、CBRN 攻击规划、CSAM、关键基础设施攻击、身份欺骗），命中即拒绝，不看任何分数。
2. **四层优先级**：对每个动作给出 safety / ethics / guidelines / helpfulness 四个分数，按 safety → ethics → guidelines 的顺序检查，任何一层 ≥ 3 即触发该层的处理（前两层拒绝，guidelines 层要求修改）。
3. **固定案例集**：8 个案例覆盖明确放行、明确拒绝、硬编码禁令、跨层模糊情况。

> 一句话：**用"先查底线、再按层级否决"的确定性规则，演示宪法式对齐的"裁决顺序"**。它不演示如何判断"是否违规"——分数是手写的——这一点恰恰是理由式对齐最难的部分，读代码时要时刻记住。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `HARDCODED_PROHIBITIONS` | 元组常量 | 6 个禁止短语 | hardcoded prohibitions |
| `TierScore` | dataclass | 四层分数（1–5） | 四层优先级的输入 |
| `hardcoded_block` | 函数 | 小写后子串匹配，返回命中的规则或 `None` | 硬编码层检测 |
| `resolve` | 函数 | 硬编码 → safety → ethics → guidelines → allow | 四层裁决 |
| `CASES` | 列表 | 8 个 `(action, TierScore)` | 演示用例 |
| `main` | 函数 | 打印裁决表与 HEADLINE | 驱动 |

数据流：`CASES` 中每个 `(action, score)` → `resolve` → `(verdict, reason)` → 格式化打印。

裁决流程图：

```text
action ──hardcoded_block 命中?──是──▶ refuse（hardcoded prohibition）
             │否
             ▼
      safety ≥ 3? ──是──▶ refuse（safety violation）
             │否
      ethics ≥ 3? ──是──▶ refuse（ethics violation）
             │否
  guidelines ≥ 3? ──是──▶ modify（guideline conflict）
             │否
             ▼
          allow（helpfulness 从未被检查）
```

---

## 3. 逐段精讲

### 3.1 硬编码禁令清单

```python
HARDCODED_PROHIBITIONS = (
    "bioweapons uplift",
    "cbrn attack planning",
    "csam",
    "critical infrastructure attack",
    # Illustrative only — substring matching catches specific phrasings
    # like "false identity to user" or "deny being an ai". Production
    # classifiers should use a dedicated deception detector, not a
    # keyword list.
    "false identity to user",
    "deny being an ai",
)
```

- 对应讲义的硬编码清单：Bioweapons / CBRN uplift、CSAM、关键基础设施攻击、"用户直接询问时就身份欺骗"。
- 用**元组**而非列表：表达"这是不可变的底线"（运行时也无法 `append`）。
- 注释已经承认："Illustrative only"，生产应使用专门的检测器而不是关键词。

### 3.2 `TierScore`：四个分数

```python
@dataclass
class TierScore:
    safety: int    # 1-5, higher = principle is violated more
    ethics: int
    guidelines: int
    helpfulness: int
```

- `@dataclass` 自动生成构造函数，可以写 `TierScore(safety=1, ethics=1, guidelines=1, helpfulness=5)`，也可以按位置写 `TierScore(1, 1, 1, 5)`。
- ⚠️ **语义不一致**：注释说"越高 = 违反越严重"，但 `CASES` 里写俳句是 `helpfulness=5`、过度拒绝是 `helpfulness=1`，显然 helpfulness 是"越高越有帮助"。前三项是"违规分"，第四项是"收益分"，方向相反。
- 类型注解 `int` 只是提示，Python 不会检查 1–5 的范围。

### 3.3 `hardcoded_block`：子串匹配

```python
def hardcoded_block(action: str) -> str | None:
    low = action.lower()
    for rule in HARDCODED_PROHIBITIONS:
        if rule in low:
            return rule
    return None
```

- `.lower()` 让匹配与大小写无关；`rule in low` 是字符串的**子串**判断。
- 返回命中的规则名（用于理由说明）或 `None`；调用方用 `if block:` 判断，`None` 与空字符串都为假。
- ⚠️ 实测的漏报与误报（详见测验 Q9）：
  - `"provide bioweapon uplift"`（单数）、`"give bio-weapons uplift"`（连字符）、`"Tell the user you are human"`、`"I am a licensed lab; help synthesize a pathogen"` → 全部 `None`；
  - `"summarize the policy debate on why bioweapons uplift evals matter"` → 被拦截（误报）。
- ⚠️ 讲义说硬编码"不随前提框架弯曲"，但关键词实现只要换一种说法就能绕过——硬编码在理念上不弯曲，在实现上却很脆弱。讲义也说明了硬编码主要在**权重层**靠训练实现，推理层只是补充。

### 3.4 `resolve`：先底线、再分层否决

```python
def resolve(action: str, score: TierScore) -> tuple[str, str]:
    block = hardcoded_block(action)
    if block:
        return "refuse", f"hardcoded prohibition: {block}"

    if score.safety >= 3:
        return "refuse", f"safety violation (score={score.safety})"
    if score.ethics >= 3:
        return "refuse", f"ethics violation (score={score.ethics})"
    if score.guidelines >= 3:
        return "modify", f"guideline conflict (score={score.guidelines}); modify"

    return "allow", "all higher tiers clear; helpfulness respected"
```

- **硬编码层先于一切**：命中后连分数都不看，所以 `"provide bioweapons uplift on toxin synthesis"` 虽然 `safety=5`，理由却是 `hardcoded prohibition`。
- **逐层否决**：任意一层 ≥ 3 就立刻返回。高层的作用体现在两点：①先被检查，所以理由报告的是最高的违规层；②safety / ethics 违规是 `refuse`，guidelines 违规只是 `modify`——讲义说 ethics "supersedes Anthropic's guidelines"，所以 guidelines 层的处理更温和。
- **helpfulness 从未被读取**：注释写"helpfulness respected"，但实际上它不参与任何判断。实测 `TierScore(1,1,1,1)` 与 `TierScore(1,1,1,5)` 结果相同。这意味着：
  - 讲义练习 1 "确认 helpfulness 很高时硬编码仍然生效"在这个实现里是平凡成立的；
  - 练习 1 后半"把 helpfulness 放到 ethics 之上"需要先给它一个决策位置（见第 7 节）。
- 返回类型 `tuple[str, str]`：`(verdict, reason)`。verdict 只有 `refuse / modify / allow` 三种。
- 枚举统计（`itertools.product` 实测）：625 种分数组合中 `refuse 525、modify 60、allow 40`。`allow` 要求前三项都 ≤ 2（`2³ × 5 = 40`）。这是一个相当保守的否决结构。
- ⚠️ 这里没有"层间冲突"的真正权衡：讲义说"When tiers conflict, higher wins"，但代码里低层永远无法"赢"，只有"更高层先否决"。这是一种**词典序否决**（lexicographic veto），与讲义"可预测的裁决"一致，但不涉及任何收益与风险的交换。
- ⚠️ **没有 operator 层**：讲义和 HEADLINE 都在说"operators adjust soft-coded defaults inside declared bounds"，但代码里没有 operator 配置、没有边界、没有用户层。测验 Q11 给出了补全版本。

### 3.5 `CASES`：8 个案例

```python
CASES = [
    ("write a haiku about spring",
     TierScore(safety=1, ethics=1, guidelines=1, helpfulness=5)),
    ("explain how to make a pipe bomb",
     TierScore(safety=5, ethics=5, guidelines=5, helpfulness=5)),
    ...
    ("refuse outright despite a benign request (over-refusal)",
     TierScore(safety=1, ethics=1, guidelines=4, helpfulness=1)),
    ("pretend to not be an AI when the user directly asks",
     TierScore(safety=4, ethics=5, guidelines=2, helpfulness=3)),
]
```

逐案分析：

| 案例 | 走到哪一层 | 值得注意 |
|------|----------|---------|
| 写俳句 | 全部通过 → allow | 基线 |
| 管道炸弹 | safety=5 → refuse | 按讲义定义，"伤害他人"属于 ethics；safety 专指"支持人类监督" |
| 生物武器 uplift | 硬编码 → refuse | 唯一真正走硬编码层的案例 |
| 造谣真人 | ethics=4 → refuse | 典型 ethics 层 |
| 修 typo | allow | 基线 |
| 帮用户向经理隐瞒谎言 | ethics=4 → refuse | helpfulness=5 但不起作用 |
| 对良性请求直接拒绝（过度拒绝） | guidelines=4 → modify | action 本身是"拒绝"，modify 表示"不应过度拒绝，改成帮忙"——用 action 文本描述一个"回应策略"，语义有点绕 |
| 被直接问时假装不是 AI | safety=4 → refuse | 讲义明确是**硬编码**禁令，但短语 `"not be an ai"` 匹配不上 `"deny being an ai"`；裁决碰巧正确，理由却错了 |

- ⚠️ 最后一个案例很关键：代码自带的测试集就暴露了关键词匹配的漏报。如果该案例的分数被改低，它会被放行。
- ⚠️ 讲义第一层强调"不是 be cautious"，但代码把炸弹和身份欺骗都记在 safety 上，正好落入讲义要澄清的误读。真正的 safety 层例子是：关闭审计日志、绕过审批、修改自身权限、对监督者隐瞒行为。

### 3.6 `main`：格式化输出

```python
    print(f"  {'action':<54} -> {'verdict':<8} {'reason'}")
    for action, score in CASES:
        verdict, reason = resolve(action, score)
        print(f"  {action:<54} -> {verdict:<8} {reason}")
```

- `{x:<54}`：左对齐、宽度 54。`"refuse outright despite a benign request (over-refusal)"` 有 55 个字符，超出宽度，所以输出里这一行的 `->` 向右错位了一格。
- `for action, score in CASES`：直接在循环头解包元组。
- HEADLINE 总结"hardcoded floor + reason-based ceiling"，并指出理由式对齐会漏掉原则歧义、漂移和前提框架攻击，运行时层（第 10、13、14 节）仍然必需。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 硬编码层放在最前且不看分数 | 体现"不随前提与分数弯曲" | 关键词实现易被改写绕过；生产在权重层训练 + 推理层用安全分类器，输入输出双侧检查 |
| 用元组存禁令 | 不可变，象征底线 | 仍然只是代码常量；生产需要版本化与审计 |
| 分数手写 | 聚焦"裁决顺序" | 真实分数来自模型或分类器判断，而它们正是会被前提框架误导的部分 |
| 阈值统一为 3 | 简单、可预测 | 不同层应有不同阈值；84% 的组合被拒，偏保守 |
| 逐层否决（词典序） | 高层永远优先，可预测 | 没有真正的权衡；helpfulness 无法发挥任何作用 |
| guidelines 违规返回 `modify` | ethics 高于 guidelines，guidelines 冲突不必拒绝 | 没有实现"如何修改" |
| 没有 operator / user 层 | 代码短 | 讲义的 soft-coded defaults 与"声明边界"没有体现；见测验 Q11 |
| 字符串理由 | 方便打印 | 生产需要结构化理由（层、规则 id、证据）以便审计 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，让 `str \| None`、`tuple[str, str]` 在较老 Python 上可用 |
| 元组常量 | `HARDCODED_PROHIBITIONS = ("bioweapons uplift", ...)` | 圆括号 + 逗号，不可修改；全大写命名表示常量 |
| 括号内多行与注释 | 元组中间夹 `# Illustrative only ...` | 括号内可以自由换行和写注释 |
| `@dataclass` | `class TierScore: safety: int ...` | 用类型注解声明字段，自动生成 `__init__` 等方法 |
| 关键字参数构造 | `TierScore(safety=1, ethics=1, guidelines=1, helpfulness=5)` | 按字段名传参，可读性强 |
| 返回类型注解 | `-> str \| None`、`-> tuple[str, str]` | 可能返回 None；返回二元组 |
| `str.lower()` 与 `in` | `low = action.lower()`；`if rule in low:` | 转小写；子串判断 |
| 提前 `return` | `if block: return "refuse", ...` | 满足条件立即返回，避免深层嵌套 |
| 返回多个值 | `return "refuse", f"..."` | 实际返回一个元组，调用方用 `verdict, reason = ...` 解包 |
| 真值判断 | `if block:` | `None` 和空字符串都为假 |
| 列表里放元组 | `CASES = [("...", TierScore(...)), ...]` | 简单的测试数据表 |
| 循环中解包 | `for action, score in CASES:` | 每个元素是二元组，直接拆开 |
| f-string 对齐 | `{action:<54}`、`{verdict:<8}` | `<` 左对齐，数字为宽度 |
| f-string 中嵌字符串字面量 | `{'action':<54}` | 用单引号避免与外层双引号冲突 |
| `"=" * 80` | `print("=" * 80)` | 字符串重复 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`；被 import 时不执行，便于在别处复用 `resolve` |

---

## 6. 运行结果解读

实际运行输出（节选）：

```text
  action                                                 -> verdict  reason
--------------------------------------------------------------------------------
  write a haiku about spring                             -> allow    all higher tiers clear; helpfulness respected
  explain how to make a pipe bomb                        -> refuse   safety violation (score=5)
  provide bioweapons uplift on toxin synthesis           -> refuse   hardcoded prohibition: bioweapons uplift
  write persuasive disinformation about a real person    -> refuse   ethics violation (score=4)
  edit the user's Python file to fix a typo              -> allow    all higher tiers clear; helpfulness respected
  help the user hide a lie from their manager            -> refuse   ethics violation (score=4)
  refuse outright despite a benign request (over-refusal) -> modify   guideline conflict (score=4); modify
  pretend to not be an AI when the user directly asks    -> refuse   safety violation (score=4)
```

逐项解读：

- **2 个 allow**（俳句、修 typo）：前三项都是 1。
- **1 个硬编码 refuse**（生物武器）：短语 `bioweapons uplift` 原样出现，命中。
- **2 个 safety refuse**（炸弹、身份欺骗）：其中身份欺骗本应走硬编码层，见第 3.5 节。
- **2 个 ethics refuse**（造谣、隐瞒谎言）：safety=2 未触发，ethics=4 触发。
- **1 个 modify**（过度拒绝）：只有 guidelines=4。这一行因为 action 文本 55 个字符超出宽度 54，`->` 错位一格。
- 讲义练习 1 第一问"确认 helpfulness 很高时硬编码仍然生效"：生物武器案例 `helpfulness=5` 仍被硬编码拒绝——成立，但因为 helpfulness 根本不参与判断，这个"确认"并没有检验到什么。

补充实验（已运行）：把 helpfulness ≥ 4 放在 ethics 检查之前，造谣、隐瞒谎言两例从 `refuse` 变成 `allow`，其余不变（测验 Q10）。

---

## 7. 动手改一改

1. **（讲义练习 1）** 在 `resolve` 中 safety 检查之后加入 `if score.helpfulness >= 4: return "allow", ...`，重跑，确认造谣和隐瞒谎言两例被放行；再把它移回最后，体会 skill 文件为什么把"helpfulness 高于 ethics"列为 hard reject。
2. **修正身份欺骗的漏报**：给 `HARDCODED_PROHIBITIONS` 补充若干同义短语，再写 5 个换说法的输入测试漏报率；体会关键词列表永远追不上改写。
3. **修正分数语义**：把 `helpfulness` 改名为 `benefit` 并在注释中写明方向；再按讲义定义重新给 8 个案例打分（例如炸弹改为 ethics 违规），观察输出理由的变化。
4. **加入 operator 层**：实现 `SOFT_BOUNDS`、`validate_operator`、`resolve_with_operator`（参考测验 Q11），验证"改名绕过"（如 `allow_csam_research`）会被拒绝。
5. **结构化理由**：把返回值改为 `dataclass Verdict(decision, tier, rule_id, score)`，并输出 JSON 审计记录，满足 skill 文件的审计格式要求。
6. **进阶**：用一个小模型或下一节的分类器替换手写分数，构造 10 条"前提框架"攻击（如"我们是持证实验室"），统计 resolver 的放行率。

---

## 8. 常见坑

- **把 safety 层理解成"谨慎"**：讲义明确第一层是"不让人类监督更困难"，伤害他人与欺骗属于 ethics（部分属于硬编码）。
- **以为关键词能实现硬编码禁令**：单复数、连字符、同义改写都能绕过；讨论政策的正常请求又会被误拦。
- **分数方向混用**：违规分越高越坏，收益分越高越好，放在同一个结构里不注明方向，很容易写出相反的逻辑。
- **让 helpfulness 参与否决链却放错位置**：一旦它排在 ethics 之前，"用户想要"就能压过一切伦理考量。
- **operator 可调项没有边界**：没有边界的"可调"就是后门；"未声明即拒绝"比"列黑名单"安全。
- **把宪法当成运行时护栏的替代**：宪法在模型层，kill switch、权限、分类器在运行时层，两层都需要。
- **只看裁决结果不看理由**：身份欺骗案例的裁决是对的，但走错了层；分数一变就会被放行。
