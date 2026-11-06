# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 20 节 OpenAI Preparedness Framework 与 DeepMind Frontier Safety Framework ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）

---

## 1. 这份代码在考察什么

本节讲义的核心技能是"把三份前沿安全政策放在一起读"。代码把这个阅读过程做成一个**决策表对照（decision-table diff）工具**：

1. **三张对照表**：OpenAI PF v2、Anthropic RSP v3.0、DeepMind FSF v3 各一张，键是能力名（如 `long_range_autonomy`），值是 `(分类, 触发动作)`。
2. **`diff(capability)`**：对给定能力，逐个政策打印它的分类与动作。
3. **HEADLINE**：总结"同一能力、三种分类"的两个代表例子。

docstring 明确说明这是"pedagogical distillations"，真正的判断必须读原文。

> 一句话：**用一个最简单的"字典查表"把讲义的"Locate → Classify"两步显式化**。代码本身几乎没有逻辑，真正的学习点在于：这张表的每一格从哪里来、能不能被原文支持、能不能被计算比较——这些正是讲义练习 1 和 skill 文件要求你做的核查。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Policy` | dataclass | `name` + `table: dict[str, tuple[str, str]]` | 一份政策的"能力 → (分类, 动作)"索引 |
| `OPENAI_PF_V2` | `Policy` 实例 | 4 个 Research + 3 个 Tracked | Tracked vs Research |
| `ANTHROPIC_RSP_V3` | `Policy` 实例 | AI R&D-4、affirmative case 等 | 第 19 节 RSP v3.0 |
| `DEEPMIND_FSF_V3` | `Policy` 实例 | CCL、Tracked Capability Level、欺骗性对齐监控 | FSF v3 |
| `POLICIES` | 列表 | 三个政策，决定打印顺序 | — |
| `diff` | 函数 | 查表并打印三行 | Locate + Classify |
| `main` | 函数 | 对 5 个能力调用 `diff`，打印 HEADLINE | 演示驱动 |

数据流：`main` → 对 5 个能力名依次 `diff(cap)` → 遍历 `POLICIES` → `p.table.get(cap, 默认值)` → 打印分类与动作。

三张表的内容（7 个能力 × 3 个政策）：

| 能力 | OpenAI PF v2 | Anthropic RSP v3.0 | DeepMind FSF v3 |
|------|-------------|--------------------|-----------------|
| `long_range_autonomy` | Research | named risk | folded into ML R&D / Cyber |
| `sandbagging` | Research | named via eval-context gap | deceptive alignment monitoring |
| `autonomous_replication` | Research | not explicitly named | folded into ML R&D domain |
| `undermining_safeguards` | Research | hardcoded prohibition | deceptive alignment monitoring |
| `rnd_automation` | Tracked | AI R&D-4 threshold | ML R&D autonomy level 1 |
| `cyber_uplift` | Tracked | ASL-3 trigger | Cyber CCL |
| `bio_uplift` | Tracked | ASL-3 trigger | Bio CCL |

---

## 3. 逐段精讲

### 3.1 `Policy` dataclass

```python
@dataclass
class Policy:
    name: str
    # capability -> (classification, trigger-action)
    table: dict[str, tuple[str, str]]
```

- `dict[str, tuple[str, str]]` 是类型注解：键是字符串，值是两个字符串组成的元组。配合 `from __future__ import annotations`，这种写法在较老 Python 上也不会报错。
- 值是**自由文本**：`"Research"`、`"named risk"`、`"folded into ML R&D / Cyber domains"` 各不相同，程序无法据此判断"谁更严格"（测验 Q10 加了约束强度字段）。
- 没有"原文出处"字段——而 skill 文件把"无法指向原文条款的分类"列为 hard reject（测验 Q11 加了 `source_clause`）。

### 3.2 OpenAI PF v2 表

```python
OPENAI_PF_V2 = Policy(
    name="OpenAI Preparedness v2 (Apr 2025)",
    table={
        "long_range_autonomy": ("Research", "observed; potential mitigations"),
        "sandbagging": ("Research", "observed; potential mitigations"),
        "autonomous_replication": ("Research", "observed; potential mitigations"),
        "undermining_safeguards": ("Research", "observed; potential mitigations"),
        "rnd_automation": ("Tracked", "Capabilities + Safeguards Reports; SAG review"),
        "cyber_uplift": ("Tracked", "Capabilities + Safeguards Reports; SAG review"),
        "bio_uplift": ("Tracked", "Capabilities + Safeguards Reports; SAG review"),
    },
)
```

- 四个 Research 条目与讲义列出的 Research Categories 一一对应，动作文本里的 "potential mitigations" 正是讲义强调的措辞。
- Tracked 一栏的动作"Capabilities + Safeguards Reports; SAG review"也来自讲义。
- 讲义本身没有列出 Tracked Categories 的完整清单，`rnd_automation`、`cyber_uplift`、`bio_uplift` 被标为 Tracked 需要对照 PF v2 原文核实（讲义练习 1、2）。

### 3.3 Anthropic RSP v3.0 表（需要重点核查）

```python
ANTHROPIC_RSP_V3 = Policy(
    name="Anthropic RSP v3.0 (Feb 2026)",
    table={
        "long_range_autonomy": ("named risk", "affirmative case at threshold"),
        "sandbagging": ("named via eval-context gap", "addressed in measurement methodology"),
        "autonomous_replication": ("not explicitly named", "covered under AI R&D-4"),
        "undermining_safeguards": ("hardcoded prohibition", "refuses training / deploy"),
        "rnd_automation": ("AI R&D-4 threshold", "affirmative case required"),
        "cyber_uplift": ("ASL-3 trigger", "security + deployment mitigations"),
        "bio_uplift": ("ASL-3 trigger", "security + deployment mitigations"),
    },
)
```

- `rnd_automation` → AI R&D-4 + affirmative case：与第 19 节讲义一致。
- `sandbagging` → eval-context gap：与本节讲义"Anthropic's RSP v3.0 addresses it via the evaluation-context gap (Lesson 1)"一致。
- ⚠️ `undermining_safeguards` → "hardcoded prohibition / refuses training / deploy"：**概念混用**。"hardcoded prohibition"是第 17 节 Claude Constitution 中约束模型**行为**的概念，不是 RSP 这份**扩展政策**的阈值；第 19 节讲义介绍 RSP 时没有提到 undermining safeguards，更没有"拒绝训练 / 部署"——它甚至与"v3.0 删除了暂停条款"相矛盾。HEADLINE 把这一格当作三家对比的重点例子之一。
- ⚠️ `cyber_uplift` / `bio_uplift` → "ASL-3 trigger"：第 19 节讲义从未提到 ASL 体系，课程材料中没有出处。
- ⚠️ `long_range_autonomy` → "named risk"：第 19 节讲义只命名了 AI R&D-4，没有把 long-range autonomy 作为独立风险。
- ⚠️ `autonomous_replication` → "not explicitly named" 却又 "covered under AI R&D-4"：skill 文件明确要求，若声称"被覆盖"但原文中没有这个词，必须给出具体条款，否则拒绝。
- 表中也没有标注每条承诺属于"Anthropic 单方面"还是"行业建议"栏——而这正是第 19 节两层结构的阅读要点。

### 3.4 DeepMind FSF v3 表

```python
DEEPMIND_FSF_V3 = Policy(
    name="DeepMind FSF v3 (Sept 2025 + Apr 2026)",
    table={
        "long_range_autonomy": ("folded into ML R&D / Cyber domains", "CCL + Tracked Capability Level"),
        "sandbagging": ("deceptive alignment monitoring", "automated instrumental-reasoning monitor"),
        "autonomous_replication": ("folded into ML R&D domain", "CCL threshold"),
        "undermining_safeguards": ("deceptive alignment monitoring", "automated monitor + red-team"),
        "rnd_automation": ("ML R&D autonomy level 1", "Tracked Capability Level added Apr 2026"),
        "cyber_uplift": ("Cyber CCL", "security + deployment mitigations"),
        "bio_uplift": ("Bio CCL", "security + deployment mitigations"),
    },
)
```

- "folded into ML R&D / Cyber"、"ML R&D autonomy level 1"、"automated instrumental-reasoning monitor" 都与讲义对应。
- `autonomous_replication` 只写"folded into ML R&D domain"，而讲义说 autonomy 并入的是 ML R&D **和** Cyber——自主复制在 Cyber 领域的含义被省略了。
- "automated monitor + red-team" 中的 red-team 讲义没有提到。
- 讲义自身也有小矛盾：正文说 CCL 覆盖"five domains: Cyber, Bio, ML R&D, CBRN, Autonomy (folded into ML R&D and Cyber)"，Key Terms 却只列四个领域（Cyber, Bio, ML R&D, CBRN）；既然 autonomy 被并入，就不应再算作第五个领域。

### 3.5 `diff`：查表与默认值

```python
def diff(capability: str) -> None:
    print(f"\nCapability: {capability}")
    print("-" * 80)
    for p in POLICIES:
        entry = p.table.get(capability, ("not in table", "—"))
        print(f"  {p.name}")
        print(f"    classification: {entry[0]}")
        print(f"    action:         {entry[1]}")
```

- `dict.get(key, default)`：查不到时返回默认元组，而不是抛 `KeyError`。
- `entry[0]`、`entry[1]` 用下标取元组元素；也可以写成 `cls, action = p.table.get(...)` 解包，更易读。
- ⚠️ **精确匹配**：`diff("autonomy")` 会对三家都打印 `not in table`（已实测）。这把"拼写或命名不同"与"政策确实没覆盖"混在一起；讲义的 Locate 一步说"If not findable, the policy does not cover it"，工具层面就更需要区分两者（测验 Q11 用 `difflib.get_close_matches` 给出候选名）。
- 函数只打印、不返回，结果无法被其他代码复用或测试。

### 3.6 `main` 与 HEADLINE

```python
    for cap in ("long_range_autonomy", "sandbagging", "autonomous_replication",
                "undermining_safeguards", "rnd_automation"):
        diff(cap)
    ...
    print("  Undermining Safeguards:")
    print("   - OpenAI: Research (not triggering)")
    print("   - Anthropic: hardcoded prohibition (refusal)")
    print("   - DeepMind: deceptive alignment monitoring")
```

- 遍历一个元组字面量，依次对 5 个能力调用 `diff`。
- ⚠️ 三张表都有的 `cyber_uplift`、`bio_uplift` 没有被打印。它们恰好是三家**最趋同**的两项（都是强制措施类），不展示它们会让读者只看到分歧、看不到共识。
- ⚠️ HEADLINE 是手写字符串，不是从表中生成的：一旦修改表格（例如更正 Anthropic 的 `undermining_safeguards`），HEADLINE 不会随之更新，产生"表与总结不一致"的风险。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 三张字典表 | 极简、易读，直接体现"同一能力不同分类" | 无法计算比较；生产中应有结构化字段（约束强度、出处、栏位） |
| 自由文本分类 | 保留各家术语原貌 | 不同政策的词汇不可比，容易被"措辞相似"误导 |
| 无原文出处字段 | 代码短 | 违反 skill 文件"每个分类必须指向原文条款"的要求；也让 Q9 中的概念混用难以被发现 |
| `.get` + 默认值 | 不会因缺键崩溃 | 把拼写错误与"未覆盖"混为一谈 |
| `main` 只展示 5 个能力 | 聚焦分歧 | 隐藏了三家一致的 cyber / bio 项 |
| HEADLINE 手写 | 突出两个例子 | 与表格可能不同步 |
| 只打印不返回 | 演示直观 | 无法测试、无法导出对比报告 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，`dict[str, tuple[str, str]]` 在较老 Python 上也可用 |
| `@dataclass` | `class Policy: name: str; table: dict[...]` | 自动生成 `__init__`，可写 `Policy(name=..., table=...)` |
| 嵌套类型注解 | `dict[str, tuple[str, str]]` | 字典的值是二元组 |
| 字典字面量跨多行 | `table={ "long_range_autonomy": (...), ... }` | 括号内可以自由换行；末尾逗号便于增删 |
| 元组字面量 | `("Research", "observed; potential mitigations")` | 不可变的二元组 |
| 括号内字符串换行 | `("not explicitly named",\n "covered under AI R&D-4")` | 括号内逗号分隔的元素可以分行写 |
| 模块级常量 | `OPENAI_PF_V2 = Policy(...)`、`POLICIES = [...]` | 全大写命名，导入模块时即创建 |
| `dict.get(k, default)` | `p.table.get(capability, ("not in table", "—"))` | 缺键时返回默认值 |
| 元组下标 | `entry[0]`、`entry[1]` | 按位置取元素 |
| 遍历元组字面量 | `for cap in ("long_range_autonomy", ...):` | 不需要先赋值给变量 |
| f-string | `f"    classification: {entry[0]}"` | 嵌入表达式 |
| 转义换行 | `f"\nCapability: {capability}"` | 先输出空行 |
| 非 ASCII 字符 | `"—"`（破折号） | Python 3 源码默认 UTF-8，可直接写 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行 `main()`；被 import 时可以单独调用 `diff` |

---

## 6. 运行结果解读

实际运行输出（节选）：

```text
Capability: long_range_autonomy
--------------------------------------------------------------------------------
  OpenAI Preparedness v2 (Apr 2025)
    classification: Research
    action:         observed; potential mitigations
  Anthropic RSP v3.0 (Feb 2026)
    classification: named risk
    action:         affirmative case at threshold
  DeepMind FSF v3 (Sept 2025 + Apr 2026)
    classification: folded into ML R&D / Cyber domains
    action:         CCL + Tracked Capability Level
...
Capability: rnd_automation
  OpenAI Preparedness v2 (Apr 2025)
    classification: Tracked
    action:         Capabilities + Safeguards Reports; SAG review
  Anthropic RSP v3.0 (Feb 2026)
    classification: AI R&D-4 threshold
    action:         affirmative case required
  DeepMind FSF v3 (Sept 2025 + Apr 2026)
    classification: ML R&D autonomy level 1
    action:         Tracked Capability Level added Apr 2026

HEADLINE: same capability, three different classifications
  Long-range Autonomy:
   - OpenAI: Research (not triggering)
   - Anthropic: named risk (affirmative case)
   - DeepMind: domain-folded (CCL + Tracked Capability Level)
  Undermining Safeguards:
   - OpenAI: Research (not triggering)
   - Anthropic: hardcoded prohibition (refusal)
   - DeepMind: deceptive alignment monitoring
```

逐项解读：

- 5 个能力 × 3 个政策 = 15 组分类，全部是表格内容的原样打印。
- 前 4 个能力在 OpenAI 一列都是 Research——讲义的要点："Research Categories ... do not automatically trigger mitigations"。
- `rnd_automation` 是三家都有明确门槛的一项：OpenAI Tracked、Anthropic AI R&D-4、DeepMind ML R&D autonomy level 1。
- HEADLINE 中 "Anthropic: hardcoded prohibition (refusal)" 是表中最站不住的一格（见 3.3）。

补充实验（已运行）：

| 调用 / 统计 | 结果 | 说明 |
|-----------|------|------|
| `diff("cyber_uplift")` | Tracked / ASL-3 trigger / Cyber CCL | 三家一致为强制类，但 `main` 未展示 |
| `diff("autonomy")` | 三行 `not in table` | 精确匹配，拼写差异被当成"未覆盖" |
| 各表键数 | 7、7、7，键集合完全相同 | 三张表可以逐行对齐 |
| OpenAI 分类计数 | Research 4、Tracked 3 | |
| 按约束强度映射后的分布 | OpenAI：mandatory 3 / monitor-only 4；Anthropic：mandatory 3 / conditional 2 / methodology 1 / not-named 1；DeepMind：mandatory 2 / conditional 3 / monitor-only 2 | 映射是主观的，见测验 Q10 |

---

## 7. 动手改一改

1. **（讲义练习 1）** 在 `main` 的能力元组中加入 `"cyber_uplift"`、`"bio_uplift"`，并挑两项与 PF v2、FSF v3 原文核对；把核对结果（条款位置）记在注释里。
2. **加出处与栏位**：把表值升级为 `Entry(classification, action, binding, source_clause, tier)`，缺出处时打印警告（参考测验 Q11）；为 Anthropic 一列标注"unilateral / industry-recommendation"。
3. **模糊查找**：对未知能力名用 `difflib.get_close_matches` 提示候选；只有在其他政策中存在、该政策中缺失时，才输出"not covered"。
4. **可计算的对比**：给每个分类定义约束强度，统计每家分布，找出三家一致与分歧最大的能力（参考测验 Q10）；让 HEADLINE 从表格自动生成，而不是手写。
5. **更正 Anthropic 一列**：根据第 17、19 节讲义，重新填写 `undermining_safeguards`、`cyber_uplift`、`bio_uplift`、`long_range_autonomy` 四格，找不到出处的写 `"not found in lesson sources"`，观察 HEADLINE 需要怎样改。
6. **（讲义练习 4 预备）** 写一个小函数 `measured_rate(true, sandbag, p_detect)`，复现测验 Q12 的 0.35 / 0.75 计算，并画出识别率从 0 到 1 时测得成功率的变化，标出阈值 0.6 的交点。

---

## 8. 常见坑

- **把教学提炼当政策原文**：docstring 已声明这些表是"pedagogical distillations"；任何对外判断都要回到原文条款。
- **把模型行为层与实验室政策层混在一起**：Constitution 的硬编码禁令约束的是模型的回答，RSP 约束的是实验室何时继续训练 / 部署，二者不能互换。
- **把 Research 当 Tracked**：skill 文件的 hard reject；前者只观察，后者触发报告与审查。
- **看措辞相似就说"三家一致"**：同样提到"欺骗性对齐"，有的是强制措施，有的只是监控。
- **精确键匹配的假阴性**：`autonomy` 与 `long_range_autonomy` 是同一类能力，工具却报告"不在表中"。
- **只展示分歧不展示共识**：cyber / bio 的一致性同样是重要信息。
- **忽略测量问题**：所有分类都假设能力能被准确测量；sandbagging 会让三家的阈值同时失效。
