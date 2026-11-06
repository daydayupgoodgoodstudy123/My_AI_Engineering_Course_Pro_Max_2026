# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 26 节 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（实际上没有任何 import，除了 `from __future__ import annotations`）

---

## 1. 这份代码在考察什么

讲义说本节的语言是"Python optional — compliance is policy + process, not code"。这份约 70 行的代码确实只是**把合规知识写成两张 Python 字典**并打印出来：

1. **`CONTROL_MAP`：一个控制项 → 多个框架条款**，对应讲义的"Cross-framework mapping"——一项访问控制策略可以同时满足 ISO 27001、GDPR、HIPAA、SOC 2 的要求，从而减少"审计疲劳"。
2. **`PROFILE_MAP`：客户画像（地域 + 行业）→ 必需框架**，对应讲义 skill 文件的"给定客户地域与行业，输出必需框架矩阵"。

价值在于"数据结构即文档"：把隐含在合规顾问脑子里的映射关系变成可以版本化、可以查询、可以审查的数据。代码本身没有逻辑，所以值得关注的是**数据是否正确**、**结构是否够用**：

- 若干条款映射值得商榷（例如 secrets management → ISO 27001 A.8.19）；
- "EU · healthcare" 写了 "HIPAA (global)"；
- docstring 说"给定控制项/客户画像输出结果"，但并没有查询函数；
- `PROFILE_MAP` 多次要求 ISO 42001，`CONTROL_MAP` 里却没有任何控制项映射到它；
- 结尾把"高风险执行日期"与禁止性实践的最高罚款 €35M / 7% 放在一起。

> 一句话：**把跨框架控制映射写成数据**——这是 Drata / Vanta 一类工具的核心思路；但映射数据本身必须经得起审计师逐条追问。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `CONTROL_MAP` | `dict[str, list[str]]` | 10 个控制项，共 27 条框架条款映射 | Cross-framework control mapping |
| `PROFILE_MAP` | `dict[tuple[str, str], list[str]]` | 7 个 `(地域, 行业)` 组合 → 必需框架列表 | 按客户画像选框架 |
| `main` | 函数 | 依次打印两张表与 EU AI Act 提示 | 演示入口 |

数据流：模块加载时两张字典就已构造好 → `main()` 遍历打印 → 结尾打印 EU AI Act 日期与罚款。没有输入、没有计算。

---

## 3. 逐段精讲

### 3.1 `CONTROL_MAP`：一个控制项，多个框架

```python
CONTROL_MAP = {
    "access logging": ["ISO 27001 A.5.15-5.18", "GDPR Art. 32", "HIPAA §164.312(a)", "SOC 2 CC6"],
    "change management": ["ISO 27001 A.8.32", "PCI DSS Req. 6", "HIPAA breach-notification", "SOC 2 CC8"],
    "encryption in transit": ["ISO 27001 A.8.24", "GDPR Art. 32", "HIPAA §164.312(e)", "PCI DSS Req. 4"],
    "secrets management": ["ISO 27001 A.8.19", "PCI DSS Req. 8", "SOC 2 CC6.1"],
    "PII redaction (inference-time)": ["GDPR Art. 25", "EU AI Act Art. 10", "HIPAA §164.514"],
    "audit log retention": ["SOC 2 CC7", "HIPAA §164.312(b)", "ISO 27001 A.8.15"],
    "conformity assessment": ["EU AI Act Art. 43 (high-risk)"],
    "impact assessment": ["Colorado AI Act SB24-205", "EU AI Act Art. 27"],
    "data subject rights": ["GDPR Ch. III", "CCPA"],
    "BAA signed": ["HIPAA §164.504(e)"],
}
```

- 前 4 行与讲义"Cross-framework mapping"表格基本一致，代码另外补了 SOC 2 与 PCI DSS 的条款；后 6 行是代码新增的 LLM 相关控制项。
- 每个值是"框架名 + 条款号"的字符串，例如 `"HIPAA §164.312(e)"`（传输安全）。用字符串而不是结构化对象，方便打印，但不方便按框架统计（测验 Q9 用前缀匹配做了反向映射）。
- 逐条理解（条款含义为通用理解，最终以标准原文和审计师意见为准）：

| 控制项 | 映射 | 评价 |
|-------|------|------|
| access logging | ISO A.5.15–5.18、GDPR Art. 32、HIPAA §164.312(a)、SOC 2 CC6 | 这些条款都是**访问控制**，标签写成 "logging" 不准确；讲义正文说的是"one access control policy" |
| change management | ISO A.8.32、PCI DSS Req. 6、"HIPAA breach-notification"、SOC 2 CC8 | A.8.32 与 CC8 正是变更管理；违规通知规则与变更管理并不对应（讲义表格同样如此） |
| encryption in transit | ISO A.8.24、GDPR Art. 32、HIPAA §164.312(e)、PCI DSS Req. 4 | 对应合理 |
| secrets management | ISO A.8.19、PCI DSS Req. 8、SOC 2 CC6.1 | A.8.19 是"运行系统上的软件安装"，更贴切的是 A.5.17（鉴别信息）与 A.8.24（密码技术/密钥管理） |
| PII redaction | GDPR Art. 25、EU AI Act Art. 10、HIPAA §164.514 | Art. 25（设计和默认的数据保护）、§164.514（去标识化）合理；Art. 10 针对高风险系统的数据治理，关联偏弱；缺 ISO A.8.11（数据脱敏） |
| audit log retention | SOC 2 CC7、HIPAA §164.312(b)、ISO A.8.15 | 合理；缺 PCI DSS Req. 10 与 EU AI Act 的记录保存要求 |
| conformity assessment | EU AI Act Art. 43 | 合理，只适用于高风险系统 |
| impact assessment | Colorado SB24-205、EU AI Act Art. 27 | Art. 27 是部署者的基本权利影响评估，合理 |
| data subject rights | GDPR Ch. III、CCPA | 合理 |
| BAA signed | HIPAA §164.504(e) | 合理（business associate 合同要求） |

- 还缺讲义特别提到的 **GDPR Art. 30 处理活动记录**，以及任何映射到 **ISO 42001** 的控制项。

### 3.2 `PROFILE_MAP`：用元组作字典键

```python
PROFILE_MAP = {
    ("US", "B2B SaaS"):             ["SOC 2 Type II", "ISO 27001", "ISO 42001"],
    ("US", "healthcare"):           ["SOC 2 Type II", "HIPAA", "ISO 27001"],
    ("US", "fintech"):              ["SOC 2 Type II", "PCI-DSS", "ISO 27001"],
    ("EU", "B2B SaaS"):             ["GDPR", "SOC 2 Type II", "ISO 27001", "EU AI Act"],
    ("EU", "healthcare"):           ["GDPR", "SOC 2 Type II", "HIPAA (global)", "EU AI Act"],
    ("Global", "enterprise"):       ["SOC 2 Type II", "ISO 27001", "ISO 42001", "GDPR", "HIPAA", "EU AI Act"],
    ("US-CO", "B2B SaaS"):          ["SOC 2 Type II", "Colorado AI Act", "ISO 27001"],
}
```

- 元组是不可变、可哈希的，所以能作字典键；`("US", "healthcare")` 一次表达两个维度。
- 冒号后的空格对齐只是排版，Python 不在意。
- ⚠️ **"HIPAA (global)"**：HIPAA 是美国法律，只约束处理美国 PHI 的主体，没有全球版本。欧盟医疗客户真正需要的是 GDPR 对健康数据（特殊类别数据）的更严格要求。
- ⚠️ **覆盖不全**：`("EU", "fintech")` 不存在，直接索引会 `KeyError`；同时服务多个地域的客户无法表达；"enterprise" 其实是规模而不是行业，却与 "B2B SaaS"、"healthcare" 混在一个维度。
- ⚠️ **"Global · enterprise"** 没有 PCI-DSS 和 Colorado AI Act，"US · fintech" 没有 Colorado AI Act（而 Colorado 法案恰好覆盖信贷类决策）。
- ⚠️ **EU AI Act 不分等级**：欧盟画像都直接写 "EU AI Act"，但义务取决于风险等级（讲义：大多数 B2B LLM SaaS 是有限风险，只有透明度义务）。
- 更好的结构是"基线 + 地域规则 + 行业规则 + 风险等级"的组合函数（测验 Q11 给出了实现与运行结果）。

### 3.3 `main`：打印两张表

```python
    for control, frameworks in CONTROL_MAP.items():
        print(f"\n{control}")
        for f in frameworks:
            print(f"  → {f}")
    ...
    for (geo, segment), frameworks in PROFILE_MAP.items():
        print(f"\n{geo} · {segment}")
        for f in frameworks:
            print(f"  · {f}")
```

- `for (geo, segment), frameworks in PROFILE_MAP.items()`：`items()` 产出 `((geo, segment), list)`，循环变量直接写成嵌套形式就能一次解包键里的元组。
- 字典按插入顺序遍历（Python 3.7+ 保证），输出顺序与源码一致。
- 字符串中直接使用 `→`、`·`、`§`、`€` 等非 ASCII 字符：Python 3 源文件默认 UTF-8，无需声明编码；终端编码不是 UTF-8 时才可能乱码。

```python
    print("\nNote: EU AI Act high-risk enforcement August 2, 2026.")
    print("Fines up to €35M or 7% global annual turnover.")
```

- ⚠️ 这两行相邻，容易让人理解为"高风险违规罚 €35M / 7%"。按讲义：高风险义务是 Art. 99(4) 的 **€15M / 3%**；€35M / 7% 是 Art. 99(3) 的**禁止性实践**上限；均取较高者（讲义未提及：对中小企业取较低者）。
- 实际计算：营业额 €20 亿的公司违反高风险义务，上限为 `max(€15M, 3% × €20 亿) = €6,000 万`；违反禁止性实践为 `max(€35M, 7% × €20 亿) = €1.4 亿`。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用字典存映射 | 零依赖、一目了然，可以放进 git 做版本管理与评审 | 无法表达条款的版本（ISO 27001:2013 vs 2022）、证据位置、负责人；生产用合规平台（Drata、Vanta、Secureframe）或结构化 YAML/数据库 |
| 条款写成字符串 | 便于打印 | 不能按框架聚合与校验；应拆成 `{framework, clause, description}` |
| 画像用 `(geo, segment)` 静态键 | 演示"不同客户要不同框架" | 组合爆炸、无法表达多地域、缺风险等级；改为规则组合函数 |
| 只打印不查询 | 代码最短 | docstring 承诺的查询能力没有实现；加 `frameworks_for()`、`required()` 与反向映射 |
| 映射由作者手写 | 教学用 | 存在误映射；每条映射都应注明依据并由合规负责人复核 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 本文件没有类型注解，这一行实际上不起作用，属于模板习惯 |
| 字典字面量 | `CONTROL_MAP = {"access logging": [...], ...}` | 键为字符串、值为列表 |
| 元组作字典键 | `("US", "healthcare"): [...]` | 元组不可变、可哈希，可作键；列表不行 |
| 多行字面量与尾随逗号 | 每行末尾的 `,` | 尾随逗号让新增一行时 diff 更干净 |
| `dict.items()` | `for control, frameworks in CONTROL_MAP.items()` | 同时遍历键和值 |
| 嵌套解包 | `for (geo, segment), frameworks in PROFILE_MAP.items()` | 一次拆开 `((geo, segment), list)` |
| f-string | `f"\n{geo} · {segment}"` | 字符串插值，`\n` 为换行 |
| 字符串拼接与乘法 | `"\n" + "=" * 80` | 先算乘法再拼接 |
| 非 ASCII 字符 | `"→"`、`"§164.312(a)"`、`"€35M"` | Python 3 源码默认 UTF-8 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时只加载两张表 |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（节选）：

```text
COMPLIANCE CONTROL MAP — one control, many frameworks

access logging
  → ISO 27001 A.5.15-5.18
  → GDPR Art. 32
  → HIPAA §164.312(a)
  → SOC 2 CC6
……（共 10 个控制项）

CUSTOMER PROFILE MAP — required frameworks per geography + segment

EU · healthcare
  · GDPR
  · SOC 2 Type II
  · HIPAA (global)          ← HIPAA 并无全球版本
  · EU AI Act
……（共 7 个画像）

Note: EU AI Act high-risk enforcement August 2, 2026.
Fines up to €35M or 7% global annual turnover.   ← 这是禁止性实践的上限，高风险义务是 €15M / 3%
```

逐项解读：

- **控制项统计**：10 个控制项、27 条映射。按框架反向统计（测验 Q9 的 `invert`，已实际运行）：HIPAA 6、ISO 27001 5、GDPR 4、SOC 2 4、PCI DSS 3、EU AI Act 3、Colorado AI Act 1、CCPA 1。HIPAA 最多，部分原因是存在"change management → breach-notification"这种牵强的映射。
- **单项多框架**："access logging"和"encryption in transit"各对应 4 个框架——这正是讲义说的"一次实现、多处得分"，也是合规自动化工具的价值所在。
- **ISO 42001 的空白**：它在 `PROFILE_MAP` 中出现了 2 次（US · B2B SaaS、Global · enterprise），但没有任何控制项映射到它。
- **画像查询**：`("EU", "fintech")` 不在表中，多地域客户无从查询，说明静态表只能作为示例。

---

## 7. 动手改一改

1. 实现 `frameworks_for(control)`（大小写不敏感，未知控制项给出提示）与 `invert(CONTROL_MAP)`（框架 → 控制项），并按控制项数量降序打印（测验 Q9）。
2. 按测验 Q10 修正映射：拆分 access control 与 logging、把 secrets management 改到 A.5.17 / A.8.24、为 PII redaction 加 A.8.11、为审计日志加 PCI DSS Req. 10、新增 GDPR Art. 30 控制项。每条映射加一个 `source` 字段注明依据。
3. 为 ISO 42001 增加至少三个控制项（如"AI 风险评估"、"模型/数据文档"、"人类监督流程"），使它不再是空白。
4. 把 `PROFILE_MAP` 改成规则组合函数 `required(geos, segments, risk_tier)`，EU AI Act 按风险等级输出不同义务（测验 Q11）。
5. 写一个 `fine_cap(turnover_eur, kind, sme=False)`：`kind` 为 `"prohibited"` 或 `"high_risk"`，普通企业取较高者、中小企业取较低者，用 €1 亿、€5 亿、€20 亿验证。
6. 进阶：把映射导出成"行 = 框架条款、列 = 控制项"的矩阵（讲义说采购方想要的就是这种矩阵），并标出每个控制项的证据来源（例如 25 节的 audit log 字段）。

---

## 8. 常见坑

- **标签与条款不符**：把访问控制条款挂在"access logging"下，审计时会被问"日志在哪一条"。
- **映射越多越好的错觉**：牵强的映射在审计中站不住，还会掩盖真正的空白（如 ISO 42001、GDPR Art. 30）。
- **把美国法规当全球法规**：HIPAA、CCPA、Colorado AI Act 都有明确的适用范围。
- **EU AI Act 不分风险等级**：不同等级的义务差别巨大，笼统写"需要 EU AI Act"无法指导工作。
- **混淆罚款档位**：€35M / 7%（禁止性实践）与 €15M / 3%（高风险义务）不能混用；中小企业取较低者。
- **只信中文机翻**：本节中文讲义把 €15M 译成"15万欧元"、€30.5M 译成"30.5万欧元"、ISO 42001 译成"ISO 2001"，数字与名称请以英文原文为准。
- **以为合规是代码问题**：讲义开宗明义"compliance is policy + process, not code"；代码只能帮助整理与查询，证据收集、流程执行与外部审计才是主体。
