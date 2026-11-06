# 测验 · 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001（Compliance — SOC 2, HIPAA, GDPR, PCI-DSS, EU AI Act, ISO 42001）

> **阶段 17 · 基础设施与生产 · 第 26 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **提醒**：本节中文讲义的机器翻译有多处数字/名称错误（如把 €15M 译成"15万欧元"、€30.5M 译成"30.5万欧元"、ISO 42001 译成"ISO 2001"），请以英文讲义为准。法规条款与日期以官方文本为准，本测验中的法规事实均转述自讲义，另有说明的除外。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 多框架覆盖是企业交易的入场券 | 采购方要的是"一行一个框架、一列一个控制项"的矩阵，而不是一份 PDF；这是企业 SaaS 问题，LLM 只是在其上叠加了特有要求 |
| 2 | 七个框架 | SOC 2 Type II（B2B 基线）、HIPAA（美国医疗）、GDPR（欧盟用户）、PCI-DSS（支付数据）、EU AI Act（服务欧盟用户）、Colorado AI Act（服务科罗拉多居民）、ISO 42001（AI 治理） |
| 3 | EU AI Act 时间线 | 2024-08-01 生效；2025-02-02 禁止性实践开始执行；2026-08-02 高风险系统义务执行（符合性评估、文档、日志）；2027-08 适用于受协调立法约束产品中的高风险系统 |
| 4 | EU AI Act 风险分级与罚款 | 不可接受（禁止）/ 高风险（符合性评估 + 日志）/ 有限风险（透明度）/ 最小风险；罚款：高风险义务最高 €15M 或全球年营业额 3%（Art. 99(4)），禁止性实践最高 €35M 或 7%（Art. 99(3)），取较高者 |
| 5 | GDPR：实时脱敏才站得住 | 事后清理不可辩护——模型已经看到了数据；推理层实时实体识别 + 一致性 tokenization，只存脱敏后的 prompt；讲义：Clearview AI 被荷兰 DPA 罚 €30.5M（2024-09），OpenAI 被意大利 Garante 罚 €15M（2024-12，讲义称 2026-03 上诉被推翻） |
| 6 | HIPAA：BAA 不是可选项 | 没有签署 Business Associate Agreement 就不能把 PHI 发给外部 AI 服务；讲义：Bedrock、Azure OpenAI、Vertex、OpenAI 直连 API、Anthropic 直连 API 都提供 BAA |
| 7 | SOC 2 Type I vs Type II | Type I：控制已设计并文档化（时间点）；Type II：控制在一段时间内（讲义：6–12 个月）有效运行；2026 年 B2B 采购默认要 Type II |
| 8 | 跨框架控制映射 | 一项控制同时满足多个框架，例如访问控制对应 ISO 27001 A.5.15–5.18、GDPR Art. 32、HIPAA §164.312(a)；Drata / Vanta / Secureframe 可自动化映射 |
| 9 | Colorado AI Act 与 ISO 42001 | Colorado：2026-06-30 生效（被 SB25B-004 从 2026 年 2 月推迟），要求高风险系统影响评估与申诉权；ISO 42001：2023 年底发布的 AI 管理体系标准，常与 ISO 27001 一起出现在采购要求中 |
| 10 | 本节代码的问题 | `CONTROL_MAP` 中若干条款映射值得商榷（如 secrets management → ISO 27001 A.8.19），`PROFILE_MAP` 给"EU · healthcare"列出了 "HIPAA (global)"，查询函数并不存在，结尾提示把高风险执行日期与禁止性实践的最高罚款放在一起 |

### 核心技能（能动手做到）

- [ ] 根据客户的地域与行业，列出必需的合规框架并说明理由
- [ ] 判断一个 LLM 产品在 EU AI Act 下属于哪个风险等级，以及高风险会带来什么额外义务
- [ ] 计算 EU AI Act 罚款上限（固定金额与营业额比例取较高者）
- [ ] 把一个技术控制项（访问控制、加密、审计日志）映射到多个框架的具体条款
- [ ] 读懂并扩展 `CONTROL_MAP` / `PROFILE_MAP`：实现查询函数、反向映射、按规则组合所需框架
- [ ] 为"误把 PHI 发给未签 BAA 的 provider"设计事件响应流程

---

## 二、基础自测（选择题）

**Q1.** 根据讲义，EU AI Act 中**高风险系统**的主要义务从哪一天开始执行？

- A. 2024 年 8 月 1 日
- B. 2025 年 2 月 2 日
- C. 2026 年 8 月 2 日
- D. 2027 年 8 月 2 日

**Q2.** 一家全球年营业额 €20 亿的公司违反了 EU AI Act 的**高风险系统义务**。按 Art. 99(4)，罚款上限是：

- A. €6,000 万（3% × €20 亿，高于 €15M）
- B. €1,500 万（固定金额）
- C. €1.4 亿（7% × €20 亿）
- D. €3,500 万

**Q3.** 讲义认为，对 GDPR 而言"在 LLM 返回后再清理 PII"不可辩护，主要因为：

- A. 事后清理太慢，会增加延迟
- B. GDPR 只允许使用正则，不允许 NER
- C. 事后清理会破坏一致性 tokenization
- D. 模型已经看到了数据——数据已经被发送和处理；应在推理前实时脱敏，只存储脱敏后的 prompt

**Q4.** 关于 SOC 2 Type I 与 Type II，正确的是：

- A. Type I 比 Type II 更严格
- B. Type I 证明控制已设计并文档化；Type II 证明控制在一段时间内（讲义：6–12 个月）有效运行，2026 年 B2B 采购默认要求 Type II
- C. 两者只是报告格式不同
- D. Type II 只适用于医疗行业

**Q5.** 一家美国医疗 SaaS 想把含 PHI 的病历摘要发给某 LLM API。讲义认为发送前**必须**具备的是：

- A. 与该 provider 签署的 Business Associate Agreement（BAA）
- B. ISO 42001 认证
- C. 该 provider 的 SOC 2 Type I 报告
- D. 用户在 UI 上点击"同意"

**Q6.** 在 EU AI Act 风险分级中，讲义认为大多数 B2B LLM SaaS 属于：

- A. 不可接受风险（被禁止）
- B. 高风险
- C. 不受该法约束
- D. 有限风险（主要是透明度义务）；涉及招聘、信贷、教育、执法、移民、基本服务时才进入高风险

**Q7.** 运行本节代码后统计 `CONTROL_MAP`：10 个控制项共 27 条映射。按框架统计，被最多控制项引用的框架是：

- A. ISO 27001（5 个控制项）
- B. HIPAA（6 个控制项）
- C. GDPR（4 个控制项）
- D. SOC 2（4 个控制项）

**Q8.** 代码结尾打印 "EU AI Act high-risk enforcement August 2, 2026. Fines up to €35M or 7% global annual turnover."。这两句放在一起的问题是：

- A. 日期写错了，应为 2025 年
- B. EU AI Act 没有罚款条款
- C. €35M / 7% 是**禁止性实践**的上限（Art. 99(3)），高风险义务的上限是 €15M / 3%（Art. 99(4)），并列容易让人误以为高风险违规适用 7%
- D. 罚款应按美元计算

---

## 三、动手 / 代码题

**Q9.** 代码 docstring 说"Given a control, print the frameworks it satisfies. Given a customer profile (geography + segment), print the required frameworks."，但 `main()` 只是把两个字典全部打印出来。请：

1. 写 `frameworks_for(control)`：大小写不敏感地查询，不存在时抛出带提示的 `KeyError`；
2. 写 `invert(CONTROL_MAP)`：得到"框架 → 控制项列表"的反向映射，并按控制项数量降序；
3. 说明反向映射对准备审计有什么用，以及运行后你发现了哪个框架**没有任何控制项**映射到它。

**Q10.** 逐条审视 `CONTROL_MAP`，指出至少四处映射可疑、遗漏或标签不准确的地方，并给出修改建议。（提示：ISO/IEC 27001:2022 附录 A 中 A.5.15–5.18 是访问控制、身份管理、鉴别信息、访问权限；A.8.11 是数据脱敏（data masking）；A.8.15 是日志；A.8.19 是运行系统上的软件安装；A.8.24 是密码技术的使用。PCI DSS v4.0 的 Req. 10 是"记录并监控对系统组件与持卡人数据的所有访问"。）

**Q11.** `PROFILE_MAP` 是一个以 `(geo, segment)` 为键的静态字典：

```python
    ("EU", "healthcare"):           ["GDPR", "SOC 2 Type II", "HIPAA (global)", "EU AI Act"],
    ("US-CO", "B2B SaaS"):          ["SOC 2 Type II", "Colorado AI Act", "ISO 27001"],
```

1. 指出 "HIPAA (global)" 的问题。
2. 查询 `("EU", "fintech")` 会得到什么？一个同时服务美国、欧盟、科罗拉多的医疗客户又该怎么查？
3. 改写为"基线 + 地域规则 + 行业规则"的组合函数，并给出 `required(["EU"], ["fintech"])` 与 `required(["US", "EU", "US-CO"], ["healthcare"])` 的输出。

**Q12.**（讲义练习 5）把 25 节 audit log 的字段（timestamp、user、tenant、model、prompt_hash、response_hash、input/output_tokens、cost_usd、guardrail_trips）映射到至少三个框架的控制要求，并说明每个字段支撑哪项审计证据；再指出要满足这些框架，audit log 还缺什么。

---

## 四、面试高频题

**Q13.**（基础必考）一个 LLM SaaS 要进入企业市场，通常需要哪些合规框架？分别由什么因素触发？

**Q14.**（原理深挖）（讲义练习 2）解释 EU AI Act 的风险分级。请对三个假设产品分级：①面向开发者的代码补全助手；②为企业 HR 筛选简历并打分的系统；③电商客服聊天机器人。被划为高风险后要做什么？

**Q15.**（工程实践）（讲义练习 1）首个企业客户要求 SOC 2 Type II、HIPAA BAA 和"EU AI Act 合规声明"，你目前只有 SOC 2 Type I。拿下这单的最小可行合规方案是什么？

**Q16.**（场景设计）（讲义练习 3）你发现团队误把一批含 PHI 的请求发给了一个没有签 BAA 的 LLM provider。请给出事件响应步骤。

**Q17.**（追问型）（讲义练习 4）对一家中型 AI 供应商来说，ISO 42001 在 2026 年是"必需品"吗？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义时间线："August 1, 2024: in force. February 2, 2025: prohibited-AI practices enforced. August 2, 2026: high-risk systems enforced. August 2027: high-risk systems in products under harmonized legislation." A 是生效日；B 是禁止性实践执行日；D 对应受协调立法约束的产品中的高风险系统。补充：讲义未提到 2025 年 8 月起适用的通用目的 AI 模型（GPAI）义务；此外 2025 年末欧盟层面曾提出推迟部分高风险义务的提案，实际执行日期请以官方公报的最新版本为准。

### Q2 — 答案：A

Art. 99(4)："up to €15M or 3% global annual turnover... whichever higher applies"。`3% × €20 亿 = €6,000 万 > €1,500 万`，取 €6,000 万。实际计算：营业额 €1 亿时 3% 只有 €300 万，取 €15M；营业额 €5 亿时 3% 正好 €15M。

- B：只看固定金额，忽略了"取较高者"。
- C、D：是禁止性实践（Art. 99(3)）的比例和固定金额。
- 加分点：对中小企业（含初创），Art. 99(6) 规定取两者中**较低**者，讲义未提及。

### Q3 — 答案：D

讲义："Post-processing cleanup (redact PII after the LLM sees it) is not a defensible posture — the model already saw the data." 处理已经发生，数据已离开你的控制边界。正确做法：推理前实体识别 → 一致性 tokenization → 只存脱敏后的 prompt，原文仅在用户明确同意时保存。A 不是核心理由（实时脱敏反而增加延迟）；B 无此规定；C 与合规判断无关。

### Q4 — 答案：B

讲义："Type I: controls designed and documented. Type II: controls operate effectively over 6-12 months... Type I is a starter; Type II is the gate." skill 文件把"拿 Type I 宣称 SOC 2 compliant 去应对企业采购"列为 hard reject。实践中 Type II 的观察期也有短至 3 个月的情况，但讲义口径是 6–12 个月。A 说反了；C 忽略了"时间段内有效运行"这一本质差异；D 错，SOC 2 是通用 B2B 基线。

### Q5 — 答案：A

讲义："You cannot send PHI to external AI services without a signed Business Associate Agreement... Confirm before sending PHI." skill 文件："Sending PHI to a provider without BAA. Refuse — HIPAA violation." B、C 是有价值的证明材料，但不能替代 BAA；D 的用户同意不能免除 covered entity 与 business associate 之间的合同义务。

### Q6 — 答案：D

讲义："Most B2B LLM SaaS is limited-risk; high-risk kicks in for employment, credit, education, law enforcement, migration, essential services." A 是社会评分等被禁止的用途；B 只在特定用途下成立；C 错，讲义："Applies globally if serving EU users."

### Q7 — 答案：B

用反向映射实际统计（见 Q9）：HIPAA 6、ISO 27001 5、GDPR 4、SOC 2 4、PCI DSS 3、EU AI Act 3、Colorado AI Act 1、CCPA 1。HIPAA 最多是因为代码给几乎每个控制项都挂上了一个 HIPAA 条款，其中"change management → HIPAA breach-notification"并不贴切（见 Q10）。这也提醒我们：映射数量多不代表覆盖好，条款对应关系要经得起审计师追问。

### Q8 — 答案：C

讲义明确区分两档：Art. 99(4) 高风险义务 €15M / 3%；Art. 99(3) 禁止性实践 €35M / 7%。代码把"高风险执行日期"与"€35M / 7%"写在相邻两行，容易误导。A 错，2026-08-02 正是讲义给出的高风险执行日；B、D 显然错误。

### Q9 — 参考答案

```python
from collections import defaultdict

FRAMEWORK_PREFIXES = ["ISO 27001", "GDPR", "HIPAA", "SOC 2", "PCI DSS",
                      "EU AI Act", "Colorado AI Act", "CCPA"]

def framework_of(ref: str) -> str:
    for p in FRAMEWORK_PREFIXES:
        if ref.startswith(p):
            return p
    return ref

def frameworks_for(control: str) -> list[str]:
    key = control.strip().lower()
    for c, refs in CONTROL_MAP.items():
        if c.lower() == key:
            return refs
    raise KeyError(f"unknown control: {control!r}; known: {list(CONTROL_MAP)}")

def invert(cmap: dict) -> dict:
    inv = defaultdict(list)
    for control, refs in cmap.items():
        for r in refs:
            inv[framework_of(r)].append(control)
    return dict(sorted(inv.items(), key=lambda kv: -len(kv[1])))
```

实际运行：

- `frameworks_for("Secrets Management")` → `['ISO 27001 A.8.19', 'PCI DSS Req. 8', 'SOC 2 CC6.1']`；`frameworks_for("backup")` → `KeyError: "unknown control: 'backup'; ..."`。
- `invert(CONTROL_MAP)`：HIPAA 6、ISO 27001 5、GDPR 4、SOC 2 4、PCI DSS 3、EU AI Act 3、Colorado AI Act 1、CCPA 1。

用途：审计是**按框架**进行的。准备 HIPAA 审计时，你需要的是"HIPAA 的每一条要求由哪些控制项满足、证据在哪里"，反向映射正好给出这张表，也能暴露"某框架只被一两个控制项覆盖"的薄弱点。

发现：`PROFILE_MAP` 里多次要求 **ISO 42001**，但 `CONTROL_MAP` 中没有任何控制项映射到 ISO 42001（例如 AI 风险评估、数据质量、透明度、人类监督——讲义列出的 ISO 42001 关注点）。这意味着按这张表准备，ISO 42001 是完全空白的。

### Q10 — 参考答案

| 问题 | 说明 | 建议 |
|------|------|------|
| "access logging" 的标签与条款不符 | A.5.15–5.18 与 HIPAA §164.312(a) 都是**访问控制**，不是"日志"。讲义正文说"One access control policy satisfies multiple framework controls"，但表格标签写成了 Access logging | 拆成两项："access control"（A.5.15–5.18、GDPR Art. 32、HIPAA §164.312(a)、SOC 2 CC6）与"logging"（A.8.15、HIPAA §164.312(b)、PCI DSS Req. 10） |
| secrets management → ISO 27001 A.8.19 | A.8.19 是"运行系统上的软件安装"，与密钥管理关系不大 | 改为 A.5.17（鉴别信息）与 A.8.24（密码技术的使用，含密钥管理） |
| change management → "HIPAA breach-notification" | 违规通知规则规定的是泄露后的通知义务，并不是变更管理控制（讲义表格写作"HIPAA breach-notification scope"，同样值得商榷） | 删除，或改为 HIPAA 安全规则中的评估要求，并注明是间接支撑 |
| 审计日志缺 PCI DSS 与 EU AI Act | PCI DSS Req. 10 要求记录并监控所有访问，v4.0 的 10.5.1 要求审计日志至少保留 12 个月、最近 3 个月可立即分析；EU AI Act 对高风险系统有自动记录（record-keeping，Art. 12）要求 | 在 "audit log retention" 中加入 PCI DSS Req. 10 与 EU AI Act Art. 12 |
| PII redaction 缺 ISO 27001 A.8.11 | ISO 27001:2022 新增了 A.8.11 数据脱敏（data masking），正好对应推理层脱敏 | 加入 A.8.11；同时考虑 GDPR Art. 5(1)(c) 数据最小化 |
| PII redaction → EU AI Act Art. 10 | Art. 10 讲的是高风险系统的数据与数据治理（主要针对训练、验证、测试数据），与推理时脱敏的关联较弱 | 注明是"间接相关"，不要作为主要依据 |
| 缺 GDPR Art. 30 | 讲义问题部分专门提到 "GDPR Article 30 records"（处理活动记录），skill 文件也把缺少 Art. 30 记录列为拒绝向欧盟客户发货的条件 | 新增控制项 "records of processing" → GDPR Art. 30 |

说明：上述条款含义为我们对标准的理解，最终映射应由合规团队或审计师确认；讲义与代码中的映射也需要同样的复核。

### Q11 — 参考答案

1. **"HIPAA (global)" 的问题**：HIPAA 是美国联邦法律，约束美国的 covered entities 及其 business associates，不存在"global"版本。纯欧盟医疗客户需要的是 GDPR 对健康数据（特殊类别个人数据）的更严格要求，以及可能的成员国医疗数据规定；只有当它处理美国患者的 PHI 或为美国 covered entity 服务时 HIPAA 才适用。代码这样写会让人误以为欧盟医疗客户也要签 BAA。
2. `PROFILE_MAP[("EU", "fintech")]` 会抛出 `KeyError`（用 `.get` 则得到 `None`，实测返回 "MISSING"）；多地域客户在静态字典中根本无法表达，只能人为挑一个最接近的键。
3. 组合函数（已运行验证）：

```python
BASELINE = ["SOC 2 Type II", "ISO 27001"]
GEO_RULES = {"EU": ["GDPR", "EU AI Act"], "US-CO": ["Colorado AI Act"],
             "US": [], "Global": ["GDPR", "EU AI Act"]}
SEGMENT_RULES = {"B2B SaaS": [], "healthcare": ["HIPAA (US PHI only)"],
                 "fintech": ["PCI-DSS"], "enterprise": ["ISO 27001"]}

def required(geos, segments):
    out = list(BASELINE)
    for g in geos:
        out += GEO_RULES.get(g, [])
    for s in segments:
        out += SEGMENT_RULES.get(s, [])
    return list(dict.fromkeys(out))          # 去重并保持顺序
```

输出：

- `required(["EU"], ["fintech"])` → `['SOC 2 Type II', 'ISO 27001', 'GDPR', 'EU AI Act', 'PCI-DSS']`
- `required(["US", "EU", "US-CO"], ["healthcare"])` → `['SOC 2 Type II', 'ISO 27001', 'GDPR', 'EU AI Act', 'Colorado AI Act', 'HIPAA (US PHI only)']`

进一步改进：EU AI Act 的义务取决于**风险等级**而不只是地域，应增加 `risk_tier` 参数；Colorado AI Act 只在"做出重大决策"的高风险系统（信贷、就业、住房、教育、基本服务等）上有实质义务；"enterprise"作为规模而不是行业，应单独作为一个维度（是否要求 ISO 42001 等）。

### Q12 — 参考答案

| 字段 | 支撑的审计证据 | 对应控制要求（示例） |
|------|--------------|-------------------|
| timestamp | 事件发生时间，可重建时间线 | ISO 27001 A.8.15（日志）、A.8.17（时钟同步）；PCI DSS Req. 10 |
| user / tenant | 谁在何时访问了什么（问责） | HIPAA §164.312(b) 审计控制；SOC 2 CC6 / CC7；GDPR Art. 32 |
| model（含版本） | 变更追溯：哪个版本产生了这个输出 | SOC 2 CC8（变更管理）；EU AI Act Art. 12（高风险系统的记录保存） |
| prompt_hash / response_hash | 证明内容未被篡改、且日志不含原始 PII | GDPR Art. 25 / Art. 5(1)(c)（设计保护与数据最小化）；ISO 27001 A.8.11 |
| input/output_tokens、cost_usd | 用量与计费核对、异常用量检测 | SOC 2 CC7（监控）；也用于 27 节的成本归因 |
| guardrail_trips | 安全控制确实在运行的证据 | SOC 2 CC7；EU AI Act 中高风险系统的风险管理与人类监督证据 |

还缺什么：

- **不可变与完整性**：哈希链或 WORM 存储（25 节测验 Q11），否则审计师无法相信日志未被修改；
- **保留期策略**：讲义给出 SOC 2 1 年、HIPAA 6 年；PCI DSS 要求至少 12 个月（最近 3 个月可立即查询）；
- **访问日志的访问日志**：谁查看过 audit log 本身；
- **请求结果与错误码**、来源 IP / 客户端标识、数据处理地域（GDPR 跨境传输）；
- **数据主体请求的处理记录**（GDPR 第三章）；
- 25 节代码的 `input_tokens` 是单词数、`model` 不含版本，这些都需要修正才能作为证据。

### Q13 — 参考回答要点

- **基线**：SOC 2 Type II（几乎所有 B2B 采购的门槛）+ ISO 27001（国际客户、尤其欧洲常要求）。
- **按地域触发**：服务欧盟用户 → GDPR + EU AI Act（按风险等级定义务）；服务科罗拉多居民且做"重大决策" → Colorado AI Act；加州用户 → CCPA。
- **按行业/数据触发**：美国医疗 PHI → HIPAA（BAA）；支付卡数据 → PCI-DSS（讲义：AI 交互层的覆盖需要配置 + 合同约定，不是自动获得）；教育数据 → FERPA（讲义 OpenAI 合规清单中出现）。
- **AI 治理**：ISO 42001 作为新兴采购要求，与 ISO 27001 配套。
- **参考画像**：讲义列出 OpenAI 的合规清单（SOC 2 Type 2、ISO/IEC 27001:2022、ISO/IEC 27701:2019、GDPR/CCPA/HIPAA(BAA)/FERPA、ChatGPT 支付组件的 PCI-DSS），大致等于 2026 年企业市场的"入场券"。
- **方法论**：用跨框架控制映射减少重复审计，用 Drata / Vanta / Secureframe 自动收集证据。

### Q14 — 参考回答要点

- **四级**：不可接受风险（禁止，如社会评分）、高风险（符合性评估、文档、日志等）、有限风险（透明度义务，例如告知用户正在与 AI 交互）、最小风险（无额外约束）。
- **分级**（需按具体用途与法规附件逐项确认）：
  1. 代码补全助手：一般为最小/有限风险，主要是透明度与通用义务；
  2. HR 简历筛选打分：属于讲义列出的"employment"领域，通常落入**高风险**；
  3. 电商客服机器人：有限风险，需要告知用户其在与 AI 交互；若它做出影响基本服务获取的决定，需要重新评估。
- **高风险带来的变化**：符合性评估（Art. 43）、技术文档、自动日志记录、风险管理体系、数据治理、人类监督、准确性与鲁棒性要求；作为部署者在某些场景下还需做基本权利影响评估（Art. 27）。skill 文件要求：若为高风险且没有符合性评估计划，不要承诺 2026 年 8 月就绪。
- 加分点：分级取决于**用途**而不是模型本身；同一个 LLM 在不同产品中可能落入不同等级。

### Q15 — 参考回答要点

- **SOC 2**：如实说明当前是 Type I，并给出 Type II 观察期已开始的证明和预计报告日期（讲义：Type II 需要 6–12 个月运行证据）；提供桥接函（bridge letter）、渗透测试报告与安全白皮书作为过渡材料。不能把 Type I 说成"SOC 2 compliant"（skill hard reject）。
- **HIPAA BAA**：与客户签 BAA 之前，先确认你调用的每一个 LLM provider 都已与你签 BAA（讲义：主流云平台和 OpenAI、Anthropic 直连 API 都提供）；落实推理层 PHI 脱敏、加密传输、访问控制与审计日志（25 节）。
- **EU AI Act 声明**：完成产品的风险等级判定并书面说明依据；若为有限风险，说明透明度措施；若可能是高风险，给出符合性评估路线图。
- **GDPR 基础**：处理活动记录（Art. 30）、DPA（数据处理协议）、子处理者清单、数据驻留说明。
- **工具**：接入 Drata / Vanta 一类平台，持续收集证据，避免每个框架单独准备。
- 原则：能证明的就证明，不能证明的给出带日期的计划，绝不夸大。

### Q16 — 参考回答要点

1. **止损**：立即停止向该 provider 发送数据（切换路由或关闭功能）；保留相关日志与请求证据。
2. **评估范围**：哪些请求、多少患者、哪些 PHI 字段、时间范围；利用 audit log（25 节）定位。
3. **联系 provider**：要求删除数据、确认数据保留与训练使用政策，并取得书面确认；评估能否补签 BAA（补签不能追溯消除已经发生的违规）。
4. **法律与合规评估**：由隐私官/法务按 HIPAA 违规通知规则进行风险评估，判断是否构成需通知的泄露，以及通知对象（受影响个人、监管机构、媒体，取决于规模）与时限。
5. **通知客户**：若你是客户的 business associate，按 BAA 约定的时限通知 covered entity。
6. **根因与整改**：为什么 PHI 没有被推理层脱敏？为什么路由允许调用未签 BAA 的 provider？在网关增加"含 PHI 的租户只能路由到已签 BAA 的 provider"的强制策略。
7. **复盘与证据**：记录全过程，作为 SOC 2 事件响应控制的证据。
- 常见误区：私下删除日志"当作没发生"——这会把一次合规事故变成更严重的问题。

### Q17 — 参考回答要点

- **支持"必需"的理由**：讲义称其为"growing procurement requirement alongside ISO 27001"；它提供了 AI 风险管理、数据质量、透明度、人类监督的体系化框架，能直接支撑 EU AI Act 的部分义务（风险管理、文档、人类监督），也能回答企业客户问卷中的 AI 治理问题。
- **反对的理由**：认证成本与人力投入不小；2026 年多数采购仍以 SOC 2 Type II 与 ISO 27001 为硬门槛，ISO 42001 多为加分项；中型供应商若尚未拿到 Type II，优先级应排在后面。
- **判断依据**：目标客户（受监管行业、欧盟大型企业更可能要求）、产品是否涉及高风险用途、是否已有 ISO 27001（已有则复用管理体系，边际成本更低）。
- **合理结论**：先拿 SOC 2 Type II + ISO 27001；按 ISO 42001 的要求建立 AI 治理流程（风险登记、模型卡、评估记录），在客户开始提出要求或进入高风险领域时再正式认证。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../25-security-secrets-audit/docs/zh.md)：推理层脱敏与 audit log 是多个框架的共同控制项。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../13-llm-observability/docs/zh.md)：日志与追踪是审计证据的来源。
- [阶段 17 · 01 托管 LLM 平台：Bedrock、Vertex AI、Azure OpenAI](../../01-managed-llm-platforms/docs/zh.md)：托管平台的 BAA、数据驻留与合规认证。
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../../18-ethics-safety-alignment/24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：EU AI Act 等法规的更完整介绍。

### 本节被哪些后续内容用到
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../27-finops-llms/docs/zh.md)：合规工具与审计成本也是单位经济的一部分。
- [阶段 17 · 28 自托管服务选型：让引擎匹配硬件与规模](../../28-self-hosted-serving-selection/docs/zh.md)：当 BAA 或数据驻留无法满足时，自托管成为选项。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../../18-ethics-safety-alignment/26-model-system-dataset-cards/docs/zh.md)：高风险系统技术文档的组成部分。
- [阶段 18 · 27 Data Provenance 与训练数据治理](../../../18-ethics-safety-alignment/27-data-provenance-training-governance/docs/zh.md)：EU AI Act 数据治理要求的落地。
- [阶段 19 · 08 面向受监管行业的生产级 RAG 聊天机器人](../../../19-capstone-projects/08-production-rag-chatbot/docs/zh.md)：在综合项目中落实合规要求。

### 延伸关键词
`SOC 2 Type II` · `Trust Services Criteria (CC6/CC7/CC8)` · `ISO/IEC 27001:2022 Annex A` · `ISO/IEC 42001` · `ISO/IEC 27701` · `HIPAA BAA` · `PHI` · `GDPR Art. 25 / 30 / 32` · `DPA / sub-processor` · `EU AI Act risk tiers` · `conformity assessment` · `Art. 99 fines` · `Colorado AI Act SB24-205` · `PCI DSS v4.0 Req. 10` · `control mapping` · `Drata / Vanta / Secureframe`
