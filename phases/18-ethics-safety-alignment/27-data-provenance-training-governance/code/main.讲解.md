# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 27 节 Data Provenance 与训练数据治理 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（实际没有 import 任何模块），无需网络

---

## 1. 这份代码在考察什么

这是一个约 90 行的"California AB 2013 数据集摘要脚手架"。它做三件事：

1. 用列表 `AB_2013_FIELDS` 定义第 3111(a) 节要求的 **12 项**法定内容；
2. 用字典 `TOY_EXAMPLE` 为一个玩具数据集填写这 12 项；
3. `flag_followups` 根据若干关键字段（个人信息、聚合消费者信息、版权、合成数据、购买/许可）给出**连锁义务提示**，`render_markdown` 把摘要和提示渲染成 Markdown。

对应讲义的三个要点：AB 2013 的 12 项内容、"第 5 项和第 7 项触发连锁义务"（EU TDM opt-out 与 CPRA）、以及"合规窗口在收集时"。

> 一句话：**把法律条文变成可检查的数据结构**——这是合规工程的起点。但这份脚手架在"Y/N 判断""缺失字段"上的处理不一致，正好示范了合规工具最怕的问题：**静默漏报**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `AB_2013_FIELDS` | 列表常量（12 个字符串） | 12 项法定内容的字段名，括号里附填写说明 | AB 2013 第 3111(a) 节 |
| `TOY_EXAMPLE` | 字典常量 | 以字段名为键的玩具数据集摘要 | 一份填好的摘要 |
| `flag_followups(summary)` | 函数 | 根据 5 个字段的取值生成后续义务提示列表 | 连锁义务（CPRA、TDM opt-out 等） |
| `render_markdown(summary)` | 函数 | 按字段顺序渲染 Markdown，并附上提示 | 公开披露文档 |
| `main()` | 函数 | 打印摘要与 TAKEAWAY | 演示 |

数据流：`TOY_EXAMPLE` → `render_markdown` → 逐字段 `summary.get(field, '(missing)')` → `flag_followups(summary)` → 拼接成字符串 → `print`。

---

## 3. 逐段精讲

### 3.1 `AB_2013_FIELDS`：把法条变成字段名

```python
AB_2013_FIELDS = [
    "sources_or_owners",
    "how_dataset_furthers_intended_purpose",
    "number_of_data_points (or range)",
    "types_of_data_points (label types or general characteristics)",
    "contains_copyright_trademark_or_patent_protected (Y/N) or fully_public_domain",
    "purchased_or_licensed (Y/N)",
    "contains_personal_information (Y/N, per Cal. Civ. Code §1798.140(v))",
    "contains_aggregate_consumer_information (Y/N, per Cal. Civ. Code §1798.140(b))",
    "cleaning_processing_or_modification_description",
    "data_collection_time_period (with ongoing-collection notice if applicable)",
    "dates_first_used_during_development",
    "uses_synthetic_data_generation (Y/N)",
]
```

与讲义 12 项一一对应：

| # | 讲义原文（节选） | 字段 |
|---|---|---|
| 1 | Sources or owners | `sources_or_owners` |
| 2 | How the datasets further the intended purpose | `how_dataset_furthers_intended_purpose` |
| 3 | Number of data points (ranges acceptable) | `number_of_data_points (or range)` |
| 4 | Types of data points | `types_of_data_points (...)` |
| 5 | Copyright / trademark / patent, or entirely public domain | `contains_copyright_..._or_fully_public_domain` |
| 6 | Purchased or licensed | `purchased_or_licensed (Y/N)` |
| 7 | Personal information（§1798.140(v)） | `contains_personal_information (...)` |
| 8 | Aggregate consumer information（§1798.140(b)） | `contains_aggregate_consumer_information (...)` |
| 9 | Cleaning, processing, modification | `cleaning_processing_or_modification_description` |
| 10 | Time period, ongoing notice | `data_collection_time_period (...)` |
| 11 | Dates first used | `dates_first_used_during_development` |
| 12 | Synthetic data generation | `uses_synthetic_data_generation (Y/N)` |

- 用**列表**而不是集合，是为了保证渲染顺序与法条编号一致。
- ⚠️ 字段名同时承担了"键"和"填写说明"两个角色（如 `"... (Y/N, per Cal. Civ. Code §1798.140(v))"`）。这让键又长又容易拼错：`flag_followups` 里必须把整串完整复制一遍，任何一个字符不同都会 `KeyError`。更好的做法是短键（`"personal_info"`）+ 单独的说明字典，或者用 `dataclass` / `Enum`。
- 第 5 项是**复合问题**："是否含受保护内容"与"是否完全属于公有领域"——Y/N 回答不完整。

### 3.2 `TOY_EXAMPLE`：一份填好的摘要

```python
TOY_EXAMPLE = {
    "sources_or_owners": "generated in-repo via Python random.gauss; owner: this repository",
    ...
    "number_of_data_points (or range)": "1,000 examples (fixed seed)",
    ...
    "cleaning_processing_or_modification_description": "none (generated deterministically)",
    "data_collection_time_period (with ongoing-collection notice if applicable)": "2026-04 (single run, fixed seed; not ongoing)",
    "dates_first_used_during_development": "2026-04-22",
    "uses_synthetic_data_generation (Y/N)": "Y (entire dataset is synthetic)",
}
```

- 12 个键与 `AB_2013_FIELDS` 完全一致（实测 `set(...) == set(...)` 为 `True`）。
- 写得好的地方：数量给出了具体值、收集时间写明"not ongoing"（第 10 项要求说明是否持续收集）、合成数据如实写 Y。
- ⚠️ **欠规范之处**（讲义练习 1）：
  - "cleaning: none"——标签是由规则生成的，这本身就是处理，应写明规则；
  - 没有生成脚本、种子值或数据哈希，无法核实"1,000 examples (fixed seed)"；
  - 版权字段只答"N"，没有回答"是否完全公有领域"。
- ⚠️ **适用范围**：AB 2013 是生成式 AI 的训练数据透明度法，而这份摘要描述的是一个"binary classification"教学数据集——严格说不在该法范围内。作为脚手架演示没问题，但真实合规工作的第一步是判断适用性。
- ⚠️ **跨课不一致**：第 26 节 datasheet 里同样"用 `random.gauss` 生成"的玩具二分类数据是 1,500 条、含 1 个二元敏感属性；这里是 1,000 条、两个实数特征。若指同一份数据，两份文档互相矛盾。

### 3.3 `flag_followups`：连锁义务提示

```python
def flag_followups(summary: dict) -> list[str]:
    flags = []
    if summary["contains_personal_information (Y/N, per Cal. Civ. Code §1798.140(v))"] == "Y":
        flags.append("triggers CPRA obligations (California Privacy Rights Act)")
    if summary["contains_aggregate_consumer_information (Y/N, per Cal. Civ. Code §1798.140(b))"] == "Y":
        flags.append("aggregate consumer information disclosure obligations apply")
    if summary["contains_copyright_trademark_or_patent_protected (Y/N) or fully_public_domain"].startswith("Y"):
        flags.append("must respect EU TDM opt-out signals (EU Copyright Directive)")
    if summary["uses_synthetic_data_generation (Y/N)"].startswith("Y"):
        flags.append("may still trigger obligations on the base model used for generation")
    if summary["purchased_or_licensed (Y/N)"] == "Y":
        flags.append("retain license terms and provenance records for audit")
    return flags
```

| 字段 | 判断方式 | 触发的提示 | 对应讲义 |
|---|---|---|---|
| 个人信息（第 7 项） | `== "Y"` | CPRA 义务 | "Item 7 … triggers Privacy Rights Act (CPRA) obligations" |
| 聚合消费者信息（第 8 项） | `== "Y"` | 披露义务 | — |
| 版权（第 5 项） | `.startswith("Y")` | 尊重 EU TDM opt-out | EU 版权指令 TDM 例外 |
| 合成数据（第 12 项） | `.startswith("Y")` | 基础模型的连带义务 | "Item 12 … new relative to Gebru" |
| 购买/许可（第 6 项） | `== "Y"` | 保留许可条款与溯源记录 | — |

问题（均已实际运行验证）：

- ⚠️ **判断方式不一致导致静默漏报**：个人信息字段写成 `"Y (user emails)"` 时**不会**触发 CPRA 提示（只有恰好 `"Y"` 才会）；写成 `"yes"` 也不会。而版权、合成数据字段用 `startswith("Y")`，带注释的 `"Y (...)"` 能正常触发。在合规工具里，漏报比报错更危险。
- ⚠️ **缺失字段直接崩溃**：用 `summary[...]` 取值，缺键时抛 `KeyError`；而 `render_markdown` 渲染时用的是 `.get(field, '(missing)')`——两个函数对缺失的处理策略相反（3.4）。
- ⚠️ **大小写敏感**：`"y"` 不会触发任何提示。
- ⚠️ **合成数据提示对本例是误报**：数据由 `random.gauss` 生成，并没有"用于生成的基础模型"。规则应区分"模型生成"与"程序生成"。
- ⚠️ **版权提示的触发条件**：是否要尊重 TDM opt-out，取决于数据**如何获取**（是否从网上抓取欧盟权利人的内容），而不只是"是否含受保护内容"的 Y/N。
- 修复思路见测验 Q9：统一的 `yn()` 解析函数（接受 `Y/yes/N/no` 及括号注释），无法判断时返回 `None` 并记入"问题清单"（fail-closed）。

### 3.4 `render_markdown`：渲染披露文档

```python
def render_markdown(summary: dict) -> str:
    lines = ["# Dataset Summary (AB 2013 Section 3111(a) 12-item)", ""]
    for field in AB_2013_FIELDS:
        lines.append(f"- **{field}**: {summary.get(field, '(missing)')}")
    followups = flag_followups(summary)
    if followups:
        lines.append("")
        lines.append("## Follow-up obligations triggered")
        for f in followups:
            lines.append(f"- {f}")
    return "\n".join(lines)
```

- 先把每一行放进列表，最后 `"\n".join(lines)` 一次性拼接——比反复 `+=` 字符串更清晰、也更高效。
- 遍历 `AB_2013_FIELDS`（而不是 `summary`），保证按法条顺序输出，且**即使摘要多了无关键也不会输出**。
- `summary.get(field, '(missing)')`：缺失字段显示 `(missing)`，这是对的设计——可惜随后调用的 `flag_followups` 会因同一个缺失字段抛 `KeyError`，`(missing)` 实际上永远显示不出来（除非缺的是那 5 个被检查之外的字段）。
- ⚠️ 空字符串不会被识别：`"dates_first_used_during_development": ""` 渲染为 `- **dates_first_used_during_development**: `，既不报错也不提示。
- `f"- **{field}**: ..."` 用 Markdown 加粗字段名。
- `if followups:` 利用"空列表为假"的特性，没有提示时不输出标题。

### 3.5 `main()` 与 TAKEAWAY

- 打印标题、摘要与五行结论。TAKEAWAY 说"Items 5 and 7 trigger cascading obligations (EU TDM opt-out + CPRA)"——但在 `TOY_EXAMPLE` 中两者都是 N，实际触发的只有第 12 项的提示。
- ⚠️ "2025 DPA convergence: legitimate interest + opt-out = lawful" 是简化：讲义同时强调 UK ICO 的回应"not a formal clearance"，巴西 ANPD 则以透明度不足为由暂停过 Meta 的处理；合法利益还需要通过平衡测试并配合保障措施，不能简化成一个等式。
- "Compliance window is at collection time; irreversibility precludes downstream fix" 是本节的核心结论（讲义 The irreversibility problem）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 字段名 = 法条描述 + 填写说明 | 打印出来即可读 | 键冗长、易拼错；生产用短键 + 说明表，或 dataclass |
| 字典存摘要 | 简单直观 | 无类型校验；生产可用 JSON Schema / pydantic 校验类型与必填 |
| Y/N 用自由文本 | 允许附注释 | 判断方式不一致导致漏报；应统一解析，无法判断时报错（fail-closed） |
| 渲染用 `.get`、检查用 `[]` | 两处分别写成 | 缺失时崩溃；应统一先做完整性检查 |
| 只对 5 个字段生成提示 | 聚焦讲义强调的连锁义务 | 时间字段、数量字段无格式校验；可加日期解析、范围检查 |
| 硬编码 `TOY_EXAMPLE` | 演示 | 没有生成脚本、种子或哈希，摘要无法验证；生产中摘要应由数据管道的元数据自动生成并附溯源链（测验 Q12） |
| 不判断法律适用性 | 脚手架定位 | 真实合规第一步是判断是否适用（AB 2013 只针对生成式 AI） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 延迟求值类型注解 |
| 列表常量 | `AB_2013_FIELDS = ["sources_or_owners", ...]` | 有序，保证输出顺序 |
| 字典常量 | `TOY_EXAMPLE = {"sources_or_owners": "...", ...}` | 键值映射 |
| 非 ASCII 字符串 | `"§1798.140(v)"` | Python 3 源文件默认 UTF-8，可直接写 `§` |
| 类型注解 | `def flag_followups(summary: dict) -> list[str]:` | 参数与返回值类型 |
| 方括号取值 vs `.get` | `summary["..."]` 与 `summary.get(field, '(missing)')` | 前者缺键抛 `KeyError`，后者返回默认值 |
| 字符串比较 | `== "Y"` 与 `.startswith("Y")` | 前者要求完全相等，后者只看前缀——本文件混用导致漏报 |
| 列表 `append` | `flags.append("...")` | 逐条收集结果 |
| f-string 嵌套引号 | `f"- **{field}**: {summary.get(field, '(missing)')}"` | 外层双引号、内层单引号 |
| 空列表为假 | `if followups:` | 列表为空时条件为 False |
| `str.join` | `"\n".join(lines)` | 用换行把多行拼成一个字符串 |
| 主入口 | `if __name__ == "__main__": main()` | 被 import 时不执行，便于在测验中复用 `flag_followups` |
| （扩展）`re.match(r"^(y|yes|n|no)\b", v, re.I)` | 测验 Q9 的 `yn()` | 忽略大小写地匹配开头的 Y/N，`\b` 保证是完整单词 |
| （扩展）`urllib.robotparser` | 测验 Q11 | 标准库解析 robots.txt 并判断 `can_fetch` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，瞬间完成）：

```text
==========================================================================
CALIFORNIA AB 2013 SECTION 3111(a) 12-ITEM GENERATOR (Phase 18, L27)
==========================================================================

# Dataset Summary (AB 2013 Section 3111(a) 12-item)

- **sources_or_owners**: generated in-repo via Python random.gauss; owner: this repository
- **how_dataset_furthers_intended_purpose**: pedagogical demonstration of binary classification in Phase 18
- **number_of_data_points (or range)**: 1,000 examples (fixed seed)
- **types_of_data_points (label types or general characteristics)**: two real-valued features; binary {0,1} labels
- **contains_copyright_trademark_or_patent_protected (Y/N) or fully_public_domain**: N (entirely synthetic; no third-party material)
- **purchased_or_licensed (Y/N)**: N
- **contains_personal_information (Y/N, per Cal. Civ. Code §1798.140(v))**: N
- **contains_aggregate_consumer_information (Y/N, per Cal. Civ. Code §1798.140(b))**: N
- **cleaning_processing_or_modification_description**: none (generated deterministically)
- **data_collection_time_period (with ongoing-collection notice if applicable)**: 2026-04 (single run, fixed seed; not ongoing)
- **dates_first_used_during_development**: 2026-04-22
- **uses_synthetic_data_generation (Y/N)**: Y (entire dataset is synthetic)

## Follow-up obligations triggered
- may still trigger obligations on the base model used for generation

==========================================================================
TAKEAWAY: the 12 items in Section 3111(a) are the California baseline.
Items 5 and 7 trigger cascading obligations (EU TDM opt-out + CPRA).
...
==========================================================================
```

解读：

- 12 项全部填写，按法条顺序输出。
- 唯一触发的提示来自第 12 项（合成数据 = Y）。如 3.3 所述，这条对 `random.gauss` 生成的数据是误报。
- 第 5、7 项都是 N，所以 TAKEAWAY 强调的"连锁义务"在这个例子里没有被演示出来。
- 补充实验（测验 Q7、Q8）：
  - 个人信息填 `"Y (user emails)"` → 输出中**没有** CPRA 提示；填 `"Y"` 才有；
  - 删除个人信息键 → `KeyError`，而不是显示 `(missing)`；
  - 首次使用日期填空字符串 → 渲染为空，无任何提示。

---

## 7. 动手改一改

1. **（讲义练习 1）** 写 `underspecified(summary)`：报告缺失/空值字段、Y/N 字段不以 Y 或 N 开头、日期字段无法解析（`date.fromisoformat`）、第 10 项未说明是否持续收集等问题；对 `TOY_EXAMPLE` 运行并逐条评价。
2. **修复漏报**：按测验 Q9 实现统一的 `yn()` 解析与 `flag_followups_v2`，让 `"Y (user emails)"`、`"yes"` 都能触发 CPRA 提示，缺失字段返回问题清单而不崩溃。
3. **短键重构**：把字段改为 `dataclass`（如 `personal_info: bool | None`、`notes: dict[str, str]`），渲染时再映射回法条描述，消除长字符串键。
4. **区分合成数据来源**：给第 12 项增加子字段"生成方式：model / programmatic"，只有 `model` 时才提示基础模型的连带义务。
5. **（讲义练习 2）opt-out 预过滤**：用 `urllib.robotparser` 对一组 URL 和 robots.txt 规则做抓取前检查（测验 Q11），把每个 URL 的检查结果与时间戳写入溯源记录。
6. **（讲义练习 5）溯源清单**：实现测验 Q12 的哈希链 manifest，并让 `render_markdown` 在第 9 项（清洗处理）后面附上处理链摘要。

---

## 8. 常见坑

- **Y/N 判断写法不统一**：`== "Y"` 和 `.startswith("Y")` 混用，导致带注释的回答被漏报。
- **缺失处理不一致**：一个函数用 `.get` 宽容，另一个用 `[]` 崩溃；应在入口处统一做完整性校验。
- **把空字符串当作已填写**：`"key": ""` 与缺键同样是缺失。
- **误报与漏报都要关注**：本例合成数据提示是误报，PI 字段带注释时是漏报；合规工具的规则要可测试（为每条规则写正反例）。
- **先填表、后判断适用性**：AB 2013 针对生成式 AI；先确定法律是否适用，再决定填哪些表。
- **以为摘要可以事后改**：skill 文件提醒"the summary becomes binding once published"——公开前要核实每一项。
- **以为 unlearning 能补救一切**：讲义 "None fully solve the problem"——合规窗口在收集时。
