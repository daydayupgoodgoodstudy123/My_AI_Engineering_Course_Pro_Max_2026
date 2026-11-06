# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 30 节 两用风险：网络、生物、化学与核领域的能力提升 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（实际没有 `import` 任何模块）

---

## 1. 这份代码在考察什么

本节是阶段 18 的收尾课。讲义头部标注 `Languages: none`，"Use It" 一节写 "No code"，但仓库附带了这份 66 行的脚本，docstring 说它是 "Reference-only"：把讲义 "Cross-domain synthesis" 表格做成结构化数据并打印出来。

它对应讲义的这些核心概念：

1. **四个领域的 2024 → 2025 变化**：生物（mild → 2.53x、接近 ASL-3）、化学（mild → 执行鸿沟被视觉模型侵蚀）、网络（代码片段协助 → 80–90% 攻击活动自动化）、核（limited → limited）。
2. **拐点（inflection）**：获取阶段自动化、实时湿实验纠错、agentic coding。
3. **剩余瓶颈（bottleneck remaining）**：采购、设备、4–6 个人工步骤、裂变材料获取——讲义与技能文件称之为"最后一道防线"。
4. **结论**：三个领域越过阈值；安全论证必须同时针对新手相对提升与专家绝对能力。

需要强调：本节讨论的是**风险评估与治理层面**的证据，代码与讲解都不涉及任何操作性内容。

> 一句话：**这是讲义跨领域汇总表的"可打印版"，学习价值在于数据背后的证据链；代码本身是练习"把结论从写死的文字改为由数据推导"的好素材。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 模块 docstring | 字符串 | 说明"仅供参考，原始来源见 docs/en.md" | — |
| `from __future__ import annotations` | 导入 | 注解延迟求值（本文件仅 `-> None` 一处注解） | — |
| `DOMAINS` | `list[dict[str, str]]`，4 条记录 | 每条 5 个键：`domain`、`2024_state`、`2025_state`、`inflection`、`bottleneck_remaining` | 跨领域综合表 |
| `main()` | 函数 | 打印标题 → 逐领域打印 4 行 → 打印 TAKEAWAY | 本节结论 |
| `if __name__ == "__main__":` | 入口守卫 | 直接运行时调用 `main()` | — |

数据流：`DOMAINS`（硬编码）→ `main()` 循环逐领域格式化 → 标准输出；TAKEAWAY 的 5 行是写死的文字，不依赖数据。

---

## 3. 逐段精讲

### 3.1 模块头

```python
"""Dual-use triage table — stdlib Python.

Prints the 2024-2025 cross-domain dual-use picture as a table.
Reference-only; primary sources cited in docs/en.md.

Usage: python3 code/main.py
"""
```

- "Reference-only; primary sources cited in docs/en.md"：数据没有附来源，来源要回讲义的 Further Reading 查（Anthropic 2025 年 11 月网络威胁报告、OpenAI PF v2、Anthropic RSP v3.0、Council on Strategic Risks 2025 年终综述）。
- 标题叫 "triage table"，但代码并不做分诊（triage）——真正的分诊流程在 `outputs/skill-dual-use-triage.md`（五步：领域、提升类型、2025 基准、剩余瓶颈、安全论证支柱）。代码只提供了其中"2025 基准"和"剩余瓶颈"两步所需的参考数据。
- 实际输出是"逐领域分块"的格式，并不是 docstring 所说的 "as a table"（表格）。

### 3.2 `DOMAINS`：四个领域的数据

```python
DOMAINS = [
    {
        "domain": "bio",
        "2024_state": "mild uplift",
        "2025_state": "2.53x novice-relative uplift; ASL-3 approach",
        "inflection": "acquisition-phase automation",
        "bottleneck_remaining": "pathogen procurement, biosafety equipment",
    },
    {
        "domain": "chem",
        "2024_state": "mild uplift",
        "2025_state": "execution-gap erosion via vision-enabled LLMs",
        "inflection": "real-time wet-lab protocol correction",
        "bottleneck_remaining": "precursor procurement, specialized equipment",
    },
    {
        "domain": "cyber",
        "2024_state": "code-snippet assistance",
        "2025_state": "80-90% campaign automation (Anthropic Nov 2025)",
        "inflection": "agentic coding workflows",
        "bottleneck_remaining": "4-6 human intervention steps",
    },
    {
        "domain": "nuclear",
        "2024_state": "limited",
        "2025_state": "limited",
        "inflection": "(no major 2024-2025 inflection reported)",
        "bottleneck_remaining": "fissile-material acquisition dominates",
    },
]
```

与讲义 "Cross-domain synthesis" 表逐行对照：

| 领域 | 讲义 2024 | 讲义 2025 | 讲义 Inflection | 代码额外提供的"剩余瓶颈" |
|------|----------|----------|----------------|------------------------|
| Bio | mild uplift | 2.53x uplift, ASL-3 approach | acquisition-phase automation | 病原体采购、生物安全设备 |
| Chem | mild uplift | execution-gap erosion via vision | real-time wet-lab correction | 前体采购、专用设备 |
| Cyber | code assistance | 80-90% campaign automation | agentic coding | 4–6 个人工介入步骤 |
| Nuclear | limited | limited | material-access bottleneck holds | 裂变材料获取 |

值得注意的几处：

- **`bottleneck_remaining` 是代码对讲义表格的补充**：讲义表格只有四列，"剩余瓶颈"散落在正文里（"Procurement and equipment gaps remain"、"The 4-6 human steps are the bottleneck"、"fissile-material acquisition dominates"）。代码把它们收拢成一列，这正对应技能文件第 4 步 "Bottleneck residual"。
- **生物的 "2.53x novice-relative uplift"**：讲义原文是"2.53x uplift on acquisition-phase tasks"，并在"新手相对 vs 专家绝对"一节把它作为新手相对提升的例子；代码加上 "novice-relative" 修饰，与讲义一致。
- **核领域的 `inflection`** 写的是 "(no major 2024-2025 inflection reported)"，而讲义表格这一格写的是 "material-access bottleneck holds"。两者意思相近，但代码把"瓶颈依然有效"挪到了 `bottleneck_remaining`。
- **证据缺失**：讲义正文与 SVG 中的关键数字"2025 年 12 月 OpenAI 演示 GPT-5 迭代湿实验，79x 效率提升"、OpenAI PF v2 的 "on the cusp" 表述、防御侧 "trusted access" 试点，都没有进入数据。
- **键名以数字开头**：`"2024_state"` 作为字典键没问题，但不是合法的 Python 标识符，无法直接改写为 dataclass 字段或对象属性（实测 `make_dataclass` 会抛 `TypeError: Field names must be valid identifiers: '2024_state'`）。
- **没有"是否越过阈值"字段**：TAKEAWAY 的 "three of four" 无法从数据得到（见 3.4）。

### 3.3 `main()`：逐领域打印

```python
def main() -> None:
    print("=" * 82)
    print("2026 DUAL-USE PICTURE (Phase 18, Lesson 30)")
    print("=" * 82)

    for d in DOMAINS:
        print(f"\n{d['domain'].upper()}")
        print(f"  2024 state             : {d['2024_state']}")
        print(f"  2025 state             : {d['2025_state']}")
        print(f"  inflection             : {d['inflection']}")
        print(f"  remaining bottleneck   : {d['bottleneck_remaining']}")
```

- `d['domain'].upper()`：把 "bio" 变成 "BIO" 作为小标题。f-string 的花括号里可以调用方法。
- 标签文字（"remaining bottleneck"）和字典键（`bottleneck_remaining`）的词序不同——显示文字与数据字段名可以独立设计，但最好保持一致，减少阅读时的对照成本。
- 循环顺序 bio → chem → cyber → nuclear 与讲义表格一致。
- 分隔线是 82 个 `=`，比第 28、29 节（78、74）更宽，因为 2025 状态一行较长。

### 3.4 TAKEAWAY：写死的结论

```python
    print("\n" + "=" * 82)
    print("TAKEAWAY: three of four CBRN domains crossed thresholds in 2025.")
    print("bio: 2.53x uplift, ASL-3 approach. chem: execution-gap erosion.")
    print("cyber: agentic automation of 80-90% of campaigns. nuclear remains")
    print("bounded by material access. safety cases must target novice-relative")
    print("AND expert-absolute; input-filter-only defenses do not suffice.")
    print("=" * 82)
```

- 这五行概括了讲义的两大结论：**三个领域越过阈值**；**安全论证必须同时针对新手相对提升与专家绝对能力，仅靠输入过滤不够**（讲义："addressing only novice uplift (via input filters, refusals, uncertainty) is insufficient for expert-absolute control"）。
- **"three of four CBRN domains" 的术语问题**：CBRN 通常指 Chemical、Biological、Radiological、Nuclear。本节的四个领域是生物、化学、网络、核——网络不在 CBRN 之内，放射性反而没讨论。讲义正文 "The least-analyzed of the four CBRN domains" 也有同样的问题。更准确的说法是"四个两用领域"或"CBRN + cyber"。
- **结论与数据脱节**：如果将来更新了 `DOMAINS`（例如核领域出现新证据），TAKEAWAY 不会自动更新。一种简单的推导方式是比较两年状态：

```python
crossed = [d["domain"] for d in DOMAINS if d["2024_state"] != d["2025_state"]]
# 实测：['bio', 'chem', 'cyber']，共 3 个
```

  但这只是代理指标，更稳妥的是显式字段 `crossed_threshold: bool` 加上依据说明（测验 Q9）。

### 3.5 入口守卫

```python
if __name__ == "__main__":
    main()
```

- 直接运行时打印；被 `import main` 时只加载 `DOMAINS`，便于在其他脚本里复用（测验 Q9、Q12 就是导入后做实验的）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 数据硬编码、无来源字段 | Learn 型小节，重点是内容 | 无法追溯每条状态出自哪份报告；生产中的风险登记表（risk register）每条都要有来源、日期、置信度 |
| 每年一个字符串字段（`2024_state`、`2025_state`） | 与讲义表格列一一对应 | 新增年份要改代码结构；键名不是合法标识符；可改为 `states: dict[int, str]` |
| 自由文本状态描述 | 读起来像讲义 | 不能比较、不能聚合；可补充结构化字段（如 `uplift_multiplier: float | None`、`crossed_threshold: bool`） |
| TAKEAWAY 写死 | 保证输出与讲义结论完全一致 | 数据更新后结论可能过时；应由数据生成并在不一致时报警 |
| 只记录"新手相对"的数字 | 讲义只有新手试验的倍数 | 专家绝对能力没有对应字段，而讲义强调两者都要评估；可增加 `expert_absolute` 字段（哪怕暂时为 "unknown"） |
| 不做分诊逻辑 | 分诊需要人工判断 | 技能文件定义了五步流程，代码只提供参考数据；关键词式的自动分诊会误判（测验 Q11） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块 docstring | 文件开头的三引号字符串 | 成为模块的 `__doc__` |
| `from __future__ import annotations` | 第 9 行 | 注解延迟求值；必须位于文件最前（docstring 之后） |
| 列表嵌套字典 | `DOMAINS = [{...}, {...}, ...]` | 常用的"记录列表"写法；每个字典是一条记录 |
| 以数字开头的字符串键 | `"2024_state"` | 字典键可以是任意字符串；但不能当变量名、属性名或 dataclass 字段名 |
| 尾随逗号 | 每个字典最后一项后的 `,` | 合法且推荐，增删行时 diff 更干净 |
| 字符串方法 | `d['domain'].upper()` | 返回大写的新字符串，原字符串不变 |
| f-string 中调用方法与取键 | `f"\n{d['domain'].upper()}"` | 花括号内可写表达式；内层用单引号 |
| 字符串重复与拼接 | `"\n" + "=" * 82` | `*` 先于 `+` 计算 |
| 返回值注解 `-> None` | `def main() -> None:` | 表示无返回值 |
| 入口守卫 | `if __name__ == "__main__":` | 区分"直接运行"与"被导入" |

---

## 6. 运行结果解读

实际运行（`cd code && timeout 180 python3 main.py`，退出码 0，瞬时完成）：

```text
==================================================================================
2026 DUAL-USE PICTURE (Phase 18, Lesson 30)
==================================================================================

BIO
  2024 state             : mild uplift
  2025 state             : 2.53x novice-relative uplift; ASL-3 approach
  inflection             : acquisition-phase automation
  remaining bottleneck   : pathogen procurement, biosafety equipment

CHEM
  2024 state             : mild uplift
  2025 state             : execution-gap erosion via vision-enabled LLMs
  inflection             : real-time wet-lab protocol correction
  remaining bottleneck   : precursor procurement, specialized equipment

CYBER
  2024 state             : code-snippet assistance
  2025 state             : 80-90% campaign automation (Anthropic Nov 2025)
  inflection             : agentic coding workflows
  remaining bottleneck   : 4-6 human intervention steps

NUCLEAR
  2024 state             : limited
  2025 state             : limited
  inflection             : (no major 2024-2025 inflection reported)
  remaining bottleneck   : fissile-material acquisition dominates

==================================================================================
TAKEAWAY: three of four CBRN domains crossed thresholds in 2025.
bio: 2.53x uplift, ASL-3 approach. chem: execution-gap erosion.
cyber: agentic automation of 80-90% of campaigns. nuclear remains
bounded by material access. safety cases must target novice-relative
AND expert-absolute; input-filter-only defenses do not suffice.
==================================================================================
```

逐项解读：

- **BIO**：2.53x 是新手在"获取阶段"任务上的相对提升，讲义说它"不足以排除 ASL-3"——也就是说，评估无法证明模型低于 ASL-3 阈值，而不是证明模型已经达到某种危险水平。剩余瓶颈是采购与设备。
- **CHEM**：变化不是一个数字，而是"防线性质"的变化——隐性知识鸿沟在缩小。剩余瓶颈同样是采购与设备。
- **CYBER**：变化最显著的领域，从代码片段级协助跃升为 agentic 工作流自动化大部分攻击活动；剩余瓶颈是 4–6 个人工步骤，讲义指出"未来的能力提升会减少这个数字"。
- **NUCLEAR**：两年都是 "limited"，瓶颈是材料而非信息。注意"公开分析最少"本身也是一个信号：证据少不等于风险低。
- **TAKEAWAY**：三个领域越过阈值；防御不能只靠输入过滤。
- 补充实验（导入 `DOMAINS` 计算）：两年状态不同的领域为 `['bio', 'chem', 'cyber']`，与 TAKEAWAY 的 "three of four" 一致；为每个领域加上第 18 节安全论证支柱后，网络领域三个支柱都相关，生物、化学以 incapability 为主（测验 Q12）。

---

## 7. 动手改一改

1. **由数据生成结论**：给每条记录加 `crossed_threshold: bool` 和 `evidence: list[str]`（报告名 + 日期），把 TAKEAWAY 的第一句改为由数据计算，并在 `crossed_threshold` 与状态字段矛盾时打印警告。
2. **修正键名并支持多年份**：把 `2024_state`、`2025_state` 改为 `states: dict[int, str]`，打印时按年份排序输出；尝试用 `@dataclass` 重写每条记录。
3. **补全缺失证据**：把 79x 湿实验效率演示、PF v2 "on the cusp"、trusted access 试点作为 `evidence` 或 `defender_side` 字段加入相应领域。
4. **加入新手 / 专家两个维度**：增加 `novice_relative` 与 `expert_absolute` 字段（未知则写 `"unknown"`），并在打印时对 `"unknown"` 标红提示——呼应技能文件"没有新手 / 专家分解的两用安全声明一律拒绝"。
5. **安全论证支柱**：按第 18 节的指导为每个领域增加 `primary_pillars`（monitoring / illegibility / incapability），打印"每个领域的安全论证重点"（测验 Q12）。
6. **讲义练习 5（写作）**：选一个领域写一段 2027 年预测，并在数据结构里加一个 `falsifiers` 字段，列出能推翻该预测的证据类型。

---

## 8. 常见坑

- **把 "CBRN" 当成包含网络**：CBRN 通常指化学、生物、放射性、核；本节的"四个领域"是 CBRN 中的三个加上网络。
- **把 2.53x 理解成"绝对风险提高了 2.53 倍"**：它是新手在特定任务上的**相对**提升；倍数依赖基线，而专家的绝对能力需要另外评估（测验 Q10）。
- **"不足以排除 ASL-3" ≠ "达到 ASL-3"**：前者是"无法证明安全"，后者是"证明危险"；技能文件也拒绝在没有实验室具体评估的情况下回答"是否满足 ASL-3"。
- **混淆两个"三支柱"**：第 8 节 Apollo 的 scheming 三条件（misalignment、goal-directedness、situational awareness）与第 18 节安全论证三支柱（monitoring、illegibility、incapability）名称相同、含义不同。技能文件第 5 步指的是后者。
- **把"证据少"当成"风险低"**：核领域是公开分析最少的领域；`limited` 描述的是现有报告的结论，不是对未来的保证。
- **结论与数据不同步**：TAKEAWAY 写死在 `print` 里，更新 `DOMAINS` 时容易忘记同步修改。
- **讲义摘要与正文的小差异**：摘要写网络攻击自动化 "up to 90%"，正文与代码写 "80-90%"；引用时以正文为准。
- **中文讲义为机器翻译**：例如把 ASL-3 写成 "ACL-3"、把 "mild uplift" 译成"移动提升"、把 "on the cusp" 译成"在孵化时"、凭空多出"2025年12月 纽约 OpenAI"。术语和数字的含义以英文讲义为准。
