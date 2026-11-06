# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 18 节 前沿安全框架：RSP、PF、FSF ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（无第三方包、无网络、无 GPU）

---

## 1. 这份代码在考察什么

这份代码不做模拟，也不做计算。它是一张**可打印的对照表**：把 Anthropic RSP v3.0、OpenAI PF v2、DeepMind FSF v3.0 放在同一组维度上逐行对比。考察点有三个：

1. **框架比较的维度**：分级结构（tier structure）、CBRN 阈值、AI R&D 阈值、竞争者调整条款、safety case 要求。这五个维度正好是 `outputs/skill-framework-diff.md` 要求审计的五个"结构轴"。
2. **"结构对齐、术语不同"**：三家用的名字不同（Capability Thresholds / High Capability thresholds / CCL），但放进同一张表后，能看出是同类构造。
3. **用数据结构表达知识**：用"字典列表 + 按键取列"的方式组织对照表，是写审计、对比类脚本的常用骨架。

需要说明：英文讲义头部写的是 `Languages: none`，Use It 一节也说 "No code for this lesson"，但仓库里确实有这份可运行的代码。讲义和代码在这一点上不一致。

> 一句话：**这是一张"活的"对照表：改一个字典就能更新比较结果。但表里硬编码的事实需要对照一手资料核对，其中至少一处已经过时。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 模块 docstring | 字符串 | 说明用途："Reference-only, no simulation" | — |
| `LABS` | `list[dict]` | 三个框架，每个是一个字典，6 个键：`name` + 5 个比较维度 | RSP / PF / FSF 的结构要素 |
| `print_row(header, key)` | 函数 | 打印一个维度（表的一"行"）：遍历三家，取同一个键 | 横向比较 |
| `main()` | 函数 | 依次打印 5 个维度和 TAKEAWAY | 讲义 Cross-lab alignment 的结论 |
| `if __name__ == "__main__"` | 入口 | 直接运行时调用 `main()` | — |

数据流：`LABS`（静态数据）→ `main()` 依次调用 5 次 `print_row(维度标题, 键名)` → 每次遍历 `LABS` 取 `lab[key]` → 格式化打印 → 打印 TAKEAWAY。

---

## 3. 逐段精讲

### 3.1 文件头与 `from __future__ import annotations`

```python
"""Frontier safety framework comparison — stdlib Python.
...
Reference-only, no simulation. Primary sources cited inline.
"""

from __future__ import annotations
```

- docstring 写着 "Primary sources cited inline"，但代码里**并没有引用任何来源**，没有 URL，也没有文档节号。来源列在讲义的 Further Reading 里。
- `from __future__ import annotations` 让类型注解延迟求值。本文件只用了 `-> None`、`str` 这类简单注解，加不加这一行行为一样。它是这套课程代码的统一模板。

### 3.2 `LABS`：用字典列表表示"表格"

```python
LABS = [
    {
        "name": "Anthropic RSP v3.0 (Feb 2026)",
        "tier_structure": "ASL-1 .. ASL-5+; biosafety-level analog",
        "cbrn_threshold": "ASL-3 (activated May 2025)",
        "ai_rd_threshold": "AI R&D-2 + AI R&D-4 (disaggregated v3.0)",
        "adjustment_clause": "yes; peer-ship reduction allowed",
        "safety_case": "required at AI R&D-4 crossing",
    },
    {
        "name": "OpenAI PF v2 (Apr 15, 2025)",
        "tier_structure": "Low / Medium / High / Critical per tracked capability",
        ...
    },
    ...
]
```

把它想成一张表：

| 键（行） | Anthropic RSP v3.0 | OpenAI PF v2 | DeepMind FSF v3.0 |
|---------|-------------------|--------------|-------------------|
| `tier_structure` | ASL-1..5+，仿 BSL | Low/Medium/High/Critical（**过时**） | 按领域的 CCL |
| `cbrn_threshold` | ASL-3（2025 年 5 月启用） | High for bio | Bioweapon Uplift CCL |
| `ai_rd_threshold` | AI R&D-2 + AI R&D-4 | High for AI R&D；Critical 定义待定 | ML R&D Acceleration CCL |
| `adjustment_clause` | 有 | 有，Leadership 可降低要求 | 有，2025 年加入 |
| `safety_case` | AI R&D-4 时要求 | Capabilities + Safeguards 两份报告 | 每个 CCL 一份；v2.0 加 Deceptive Alignment |

**列表中的每个字典是一列（一家实验室），每个键是一行（一个维度）**。这种"按记录存储、按字段读取"的组织方式和数据库表、pandas DataFrame 是同一种思路。

与讲义或一手资料核对后发现的问题：

- ⚠️ **OpenAI 的 `tier_structure` 已过时**。OpenAI 2025-04-15 公告（讲义 Further Reading 第 2 条）原文是 "We've streamlined levels to two clear thresholds"，即 High 与 Critical。Low / Medium / High / Critical 是旧版 Beta 框架的四级记分卡写法。
- ⚠️ **OpenAI 的 `adjustment_clause` 措辞不完整**。公告写的是 "If another frontier AI developer releases a high-risk system without comparable safeguards, we may adjust our requirements"，并附带前提：先 "rigorously confirm that the risk landscape has actually changed"，并公开承认这次调整。代码只写了 "Leadership may reduce requirements"，读起来比原条款更随意。
- `"AI R&D-2 + AI R&D-4"` 与讲义一致。讲义把 ASL-4 描述为 "AI R&D-2 crossing threshold; models that can automate entry-level AI research"。
- 讲义列出了 Harmful Manipulation CCL，但表中没有对应的维度。它只出现在 DeepMind 的 `tier_structure` 文本里（"manipulation"）。可以加一个维度把它显式化，见第 7 节练习 2。

### 3.3 `print_row`：取出表的一行

```python
def print_row(header: str, key: str) -> None:
    print(f"\n{header}")
    for lab in LABS:
        name = lab["name"]
        val = lab[key]
        print(f"  {name:32s} : {val}")
```

- `header` 是给人看的标题，`key` 是字典里的键名。二者分开，显示文字和数据字段可以独立修改。
- `f"{name:32s}"`：把 `name` 当字符串，**左对齐、补空格到 32 个字符宽**（字符串默认左对齐）。最长的名字 `"Anthropic RSP v3.0 (Feb 2026)"` 有 29 个字符，所以三行的冒号能对齐。
- ⚠️ `lab[key]` 在键不存在时抛 `KeyError`。现在三家的字段齐全，所以不会出问题；但要表达"某家没有定义某阈值"时就会崩。改成 `lab.get(key, "(not defined)")` 更稳，也更符合"空白本身就是比较结论"的需要（测验 Q9）。
- `print(f"\n{header}")` 中的 `\n` 在标题前空一行，让各段在视觉上分开。

### 3.4 `main()`：五个维度 + 结论

```python
def main() -> None:
    print("=" * 78)
    print("FRONTIER SAFETY FRAMEWORKS (Phase 18, Lesson 18)")
    print("=" * 78)

    print_row("tier structure", "tier_structure")
    print_row("CBRN threshold", "cbrn_threshold")
    print_row("AI R&D threshold", "ai_rd_threshold")
    print_row("competitor-adjustment clause", "adjustment_clause")
    print_row("safety-case requirement", "safety_case")

    print("\n" + "=" * 78)
    print("TAKEAWAY: structural alignment across the three labs: three tiers of")
    ...
```

- `"=" * 78`：字符串乘以整数表示重复，画出 78 个字符宽的分隔线。
- 五次 `print_row` 调用是硬编码的。如果维度增多，可以改成遍历一个 `[(标题, 键), ...]` 列表（第 7 节练习 1）。
- TAKEAWAY 对应讲义 "Cross-lab alignment" 和 "The race-dynamic problem" 两节的结论：结构上对齐、没有统一术语、safety case 是汇聚性产物、外部对应方是 UK AISI / US CAISI / EU AI Office。
- ⚠️ "three tiers of frontier capability" 这一说法来自讲义（"three tiers of frontier capability with published evaluation criteria"），但含义模糊：ASL 有五级以上，PF v2 是两级阈值，FSF 按领域定义 CCL。比较可靠的理解是"三家实验室各有一套分级阈值"，而不是"都分三级"。

### 3.5 `if __name__ == "__main__":`

只有直接运行 `python3 main.py` 时才执行 `main()`；被其他脚本 `import main` 时不会自动打印。这样就能在别处复用 `LABS` 数据，比如测验 Q9 中测试 `print_row` 的行为。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯静态数据，不做模拟 | 本节是 "Learn" 类型，重点是概念对比 | 不能"运行出洞见"，价值完全取决于数据是否准确；真实工作中应把数据放在带来源和日期的 YAML/JSON 里 |
| 字典列表（每家一个字典） | 新增一家实验室只要追加一个字典 | 新增维度时每个字典都要补键；缺键会 `KeyError`；可用 `dataclass` 或 schema 校验强制字段齐全 |
| 值是自由文本字符串 | 写起来快，信息密度高 | 无法程序化比较（如"谁的阈值更早触发"）；生产中会把阈值结构化（领域、等级、触发评估、要求的保障） |
| 不写来源链接 | 代码简短 | docstring 声称 "cited inline" 但实际没有；事实过时（PF v2 等级）时无从追溯，应给每个字段附 `source` 与 `as_of` |
| TAKEAWAY 硬编码在打印语句里 | 让结论紧跟表格 | 结论不会随数据变化而更新；表改了，结论可能就不再成立 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块 docstring | 文件开头的 `"""..."""` | 模块的说明文字，可以通过 `help(main)` 或 `main.__doc__` 读取 |
| `from __future__ import annotations` | 第 12 行 | 推迟类型注解的求值；在老版本 Python 里也能写 `list[str]` 这类注解 |
| 字典字面量 | `{"name": "...", "tier_structure": "..."}` | 键值对集合，用 `d[key]` 取值 |
| 列表 | `LABS = [ {...}, {...}, {...} ]` | 有序容器，这里存放三条记录 |
| `for` 遍历列表 | `for lab in LABS:` | 依次取出每个字典 |
| 字典取值与 `KeyError` | `lab[key]` | 键不存在时抛异常；`lab.get(key, 默认值)` 则返回默认值 |
| 类型注解 | `def print_row(header: str, key: str) -> None:` | 说明参数和返回值的类型，运行时不做强制检查 |
| f-string 宽度格式符 | `f"  {name:32s} : {val}"` | `:32s` 表示按字符串格式化，宽度 32，字符串默认左对齐（`:>32s` 为右对齐） |
| 转义字符 | `f"\n{header}"` | `\n` 是换行 |
| 字符串重复 | `"=" * 78` | 把字符串重复 78 次 |
| 字符串拼接 | `"\n" + "=" * 78` | `*` 的优先级高于 `+`，先重复再拼接 |
| 主程序入口 | `if __name__ == "__main__": main()` | 直接运行时执行；被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，耗时远小于 1 秒，退出码 0）：

```text
==============================================================================
FRONTIER SAFETY FRAMEWORKS (Phase 18, Lesson 18)
==============================================================================

tier structure
  Anthropic RSP v3.0 (Feb 2026)    : ASL-1 .. ASL-5+; biosafety-level analog
  OpenAI PF v2 (Apr 15, 2025)      : Low / Medium / High / Critical per tracked capability   ← 已过时：v2 只有 High / Critical
  DeepMind FSF v3.0 (Sep 2025)     : CCL per domain: bio / cyber / ML R&D / manipulation

CBRN threshold
  Anthropic RSP v3.0 (Feb 2026)    : ASL-3 (activated May 2025)
  OpenAI PF v2 (Apr 15, 2025)      : High for bio
  DeepMind FSF v3.0 (Sep 2025)     : Bioweapon Uplift CCL

AI R&D threshold
  Anthropic RSP v3.0 (Feb 2026)    : AI R&D-2 + AI R&D-4 (disaggregated v3.0)
  OpenAI PF v2 (Apr 15, 2025)      : High for AI R&D; Critical definitions pending
  DeepMind FSF v3.0 (Sep 2025)     : ML R&D Acceleration CCL (v2.0 raised security tier)

competitor-adjustment clause
  Anthropic RSP v3.0 (Feb 2026)    : yes; peer-ship reduction allowed
  OpenAI PF v2 (Apr 15, 2025)      : yes; Leadership may reduce requirements   ← 原文有"先确认风险格局改变 + 公开承认"的前提
  DeepMind FSF v3.0 (Sep 2025)     : yes; added 2025

safety-case requirement
  Anthropic RSP v3.0 (Feb 2026)    : required at AI R&D-4 crossing
  OpenAI PF v2 (Apr 15, 2025)      : Capabilities + Safeguards Reports separately
  DeepMind FSF v3.0 (Sep 2025)     : per-CCL; Deceptive Alignment section added v2.0

==============================================================================
TAKEAWAY: structural alignment across the three labs: three tiers of
frontier capability, CBRN thresholds defined, AI R&D thresholds
emerging, competitor-adjustment clauses universal. no industry-
standard terminology. safety cases are the convergent artifact.
UK AISI, US CAISI, EU AI Office provide the external counterpart.
==============================================================================
```

逐项解读：

- **tier structure**：Anthropic 是**全局**分级（一个模型对应一个 ASL），DeepMind 是**按领域**分级（每个领域各有 CCL），OpenAI 是"按跟踪类别设阈值"，介于两者之间。这对应 `skill-framework-diff.md` 第 1 条："per-domain (FSF-style) or global (RSP-style)"。
- **CBRN threshold**：三家都有，是最成熟、最一致的一行，因为生物风险的威胁模型最清楚，也最早有 uplift 研究（第 17 节）。
- **AI R&D threshold**：三家都在定义，但成熟度不同。OpenAI 写着 "Critical definitions pending"。这一行对应 TAKEAWAY 中的 "AI R&D thresholds emerging"。
- **competitor-adjustment clause**：三家都是 yes，这就是讲义所说的 "competitor-adjustment clauses universal"，也是 race dynamic 争议的根源（测验 Q15）。
- **safety-case requirement**：三家的形式各不相同（Anthropic 的 affirmative case、OpenAI 的双报告、DeepMind 的按 CCL 论证），但都在向"书面论证 + 证据"的形式靠拢，所以 TAKEAWAY 说 "safety cases are the convergent artifact"。

---

## 7. 动手改一改

1. **数据驱动的行列表**：把五次 `print_row` 调用改成遍历 `DIMENSIONS = [("tier structure", "tier_structure"), ...]`，以后加维度只改数据不改逻辑。
2. **加一个维度并显式标空**：新增 `manipulation_threshold`，只给 DeepMind 赋值 `"Harmful Manipulation CCL (new in v3.0)"`；`print_row` 改用 `lab.get(key, "(not defined)")`。运行后观察哪些单元格是空白，这就是讲义 Use It 要求找的"其他家没有定义的阈值"。
3. **修正过时事实并加来源**：把 OpenAI 的 `tier_structure` 改为 `"High / Critical per tracked category"`；给每个字典加 `"source"` 与 `"as_of"` 字段，并在表格末尾打印来源列表。
4. **加入第四个框架**：参考 `outputs/skill-framework-diff.md`，为任意一份公开的安全政策（如另一家实验室的框架）补一个字典，并检查它是否触发该 skill 的 "Hard rejects"（例如没有分级阈值、没有外部治理交叉引用）。
5. **结构化阈值**：把 `cbrn_threshold` 从字符串改成 `{"level": "ASL-3", "trigger_eval": "...", "required_safeguards": [...]}`，写一个函数列出"每家在 CBRN 阈值上要求的保障措施"的并集与交集。
6. **进阶**：用 `dataclass` 定义 `Framework`，字段齐全，缺字段时构造就会报错；再写一个 `diff(a, b)` 函数，输出两份框架逐字段的差异（可以理解为 `skill-framework-diff` 的程序化版本）。

---

## 8. 常见坑

- **把硬编码的事实当成权威**：代码里的 OpenAI 等级数已经过时。治理类资料更新很快（讲义里的三个框架分别发布于 2025-02、2025-04、2025-09、2026-02），引用前要核对一手资料和日期。
- **用 `lab[key]` 读可能缺失的字段**：在比较场景里，"缺失"是常见情况，而不是异常。
- **把"结构对齐"理解为"标准相同"**：三家的阈值数值、评估方法、触发后果都不同；讲义强调的是"structurally aligned"而不是"identical"（参见 quiz.json 中对应的选择题）。
- **把"three tiers"理解为"都分三级"**：ASL 有五级以上，PF v2 是两级阈值，FSF 按领域定义 CCL。
- **以为框架有法律约束力**：讲义："The lab frameworks are voluntary; the regulatory frameworks are emerging."
- **读中文机翻讲义时被误译带偏**："race dynamic" 被译成"种族动力"、"ship" 被译成"船舶"、"safety case" 被译成"安全箱"，都应以英文为准。
