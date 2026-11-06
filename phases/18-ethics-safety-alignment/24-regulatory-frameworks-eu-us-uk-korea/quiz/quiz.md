# 测验 · 监管框架：欧盟、美国、英国、韩国（Regulatory Frameworks — EU, US, UK, Korea）

> **阶段 18 · 伦理、安全与对齐 · 第 24 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **提示**：本节中文讲义机翻质量很差（把 "AI" 译成"大赦国际"、把 "GPAI" 译成"全球公共管理倡议"、把 "15M EUR" 译成"15万欧元"、把 "logging" 译成"伐木"），阅读时请以 [English](../docs/en.md) 为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 自愿 vs 强制 | 讲义："Lab frameworks (Lesson 18) are voluntary. Regulatory frameworks are compulsory."部署方要把技术控制映射到各法域的法定义务 |
| 2 | EU AI Act 风险分层 | 禁止性实践（第 5 条）→ 高风险系统（Annex III：就业、教育、信贷、执法、司法、移民）→ GPAI 模型 → 有限风险（第 50 条透明度） |
| 3 | EU AI Act 时间线 | 2024-08-01 生效；2025-02-02 禁止性实践 + AI 素养；2025-08-02 GPAI + 治理；2026-08-02 全面适用 + 第 50 条 + 罚则；2027-08-02 存量 GPAI 与嵌入式高风险系统 |
| 4 | 系统性风险 GPAI | 训练算力 > 1e25 FLOP 的 GPAI 承担额外义务；讲义估计受约束的公司 5–15 家 |
| 5 | GPAI Code of Practice | 2025-07-10 发布；三章：Transparency、Copyright（所有 GPAI 提供者）、Safety and Security（仅系统性风险 GPAI）；共 12 项承诺；2026-08-02 起执法，此前接受善意合规 |
| 6 | 第 50 条透明度守则 | 2025-12-17 第一稿、2026 年 3 月第二稿、讲义预计 2026 年 6 月定稿；覆盖 AI 生成内容标识与 deepfake——要求第 23 节的水印技术 |
| 7 | 英国 AISI 更名 | 2025 年 2 月 AI Safety Institute → AI Security Institute：收窄到前沿能力安全，去掉算法偏见与言论自由框架；开源 Inspect 评测工具（2024 年 5 月） |
| 8 | 美国 CAISI | 2025 年 6 月 NIST 的 AI Safety Institute → Center for AI Standards and Innovation：转向 "pro-growth"，弱化部署前评测，强调标准与创新支持；州法（如加州 AB 2013）填补联邦空白 |
| 9 | 韩国 AI 基本法 | 2024 年 12 月通过、2025 年 1 月颁布、2026 年 1 月生效，合并 19 个法案；第 12 条在 MSIT 下设 AISI；要求外国 AI 公司设本地代表、高影响 AI 风险评估、生成式与高影响 AI 安全措施；亚洲首部全面横向 AI 法 |
| 10 | 跨法域合规 | 讲义："Deployers in multiple jurisdictions have to comply with the strictest, which in 2026 is typically the EU AI Act"；但各法域义务并非总能排成一条"严格度"直线（见 Q17） |

### 核心技能（能动手做到）

- [ ] 默写 EU AI Act 的四个关键日期，并说出每个日期开始适用的义务类别
- [ ] 给定一个 AI 产品，判断它在 EU AI Act 下的风险层级，以及是否属于（系统性风险）GPAI
- [ ] 说清 GPAI Code of Practice 三章分别约束谁
- [ ] 对"美国公司 + 欧盟基础设施 + 韩国用户"这类部署，逐法域列出适用规则与"对每个实质问题起约束作用的规则"
- [ ] 把技术控制（水印、模型卡、训练数据摘要、红队评测、日志）映射到具体法定义务
- [ ] 读懂 / 改进本节的时间线打印脚本：处理"只有月份精度"的日期、按日期排序、查询某日已生效的里程碑

---

## 二、基础自测（选择题）

**Q1.** EU AI Act 的生效日期，以及**最先**开始适用的义务类别是：

- A. 2025-08-02 生效；最先适用 GPAI 义务
- B. 2024-08-01 生效；最先适用高风险系统的合格评定
- C. 2024-08-01 生效；2025-02-02 起最先适用禁止性实践与 AI 素养要求
- D. 2026-08-02 生效；所有义务同时适用

**Q2.** 讲义中，EU AI Act 把 GPAI 模型认定为"系统性风险 GPAI"（承担额外义务）的量化门槛是：

- A. 训练算力超过 1e25 FLOP
- B. 参数量超过 1000 亿
- C. 月活用户超过 4500 万
- D. 年营业额超过 15M 欧元

**Q3.** 关于 GPAI Code of Practice（2025-07-10）的三章及约束对象，正确的是：

- A. 三章均只约束系统性风险 GPAI 提供者
- B. Transparency 只约束系统性风险 GPAI，其他两章约束所有 GPAI
- C. 三章分别是 Privacy、Fairness、Robustness
- D. Transparency 和 Copyright 约束所有 GPAI 提供者；Safety and Security 只约束系统性风险 GPAI 提供者

**Q4.** 2025 年 2 月英国 AI Safety Institute 更名为 AI Security Institute，讲义认为它意味着：

- A. 机构被撤销，职能并入 NIST
- B. 范围收窄：去掉算法偏见与言论自由等框架，聚焦前沿能力安全
- C. 开始对所有 AI 产品实行上市前许可
- D. 改为只研究 AI 对就业的影响

**Q5.** 韩国 AI 基本法（AI Framework Act）的核心内容是：

- A. 第 12 条在科学技术信息通信部（MSIT）下设立 AISI；要求外国 AI 公司设本地代表，并对高影响 AI 做风险评估、对生成式与高影响 AI 采取安全措施
- B. 禁止在韩国境内部署任何生成式 AI
- C. 只规范政府内部使用的 AI，不涉及企业
- D. 直接照搬 EU AI Act 的全部条文与罚则

**Q6.** 关于 EU AI Act 第 50 条，正确的是：

- A. 它规定的是系统性风险 GPAI 的红队测试义务
- B. 它已于 2025-02-02 与禁止性实践同时适用
- C. 它只适用于高风险系统
- D. 它是有限风险系统的透明度义务（AI 生成内容标识，包括 deepfake），2026-08-02 起适用，配套的透明度守则讲义预计 2026 年 6 月定稿

**Q7.** 2025 年 6 月美国把 NIST 下的 AI Safety Institute 改组为 CAISI，讲义描述的政策方向是：

- A. 与 EU AI Act 对齐，引入风险分层与高额罚款
- B. 要求所有前沿模型在发布前接受联邦强制评测
- C. 转向"pro-growth AI policies"：弱化部署前评测，强调标准与创新支持
- D. 把 AI 监管权完全交给各州并解散联邦机构

**Q8.** 本节 `code/main.py` 的 `TIMELINE` 用 `"2025-02-00"` 这样的字符串表示"只知道月份"的日期。下列说法正确的是：

- A. `datetime.date.fromisoformat("2025-02-00")` 会返回 2025 年 2 月 1 日
- B. 这种写法无法被 `datetime.date.fromisoformat` 解析（日期 0 越界），而且按字符串排序时 `"2025-02-00"` 会排在 `"2025-02-02"` 前面，与列表里的实际顺序不一致
- C. 列表已经严格按日期字符串升序排列
- D. `"-00"` 是 ISO 8601 规定的"未知日"写法

---

## 三、动手 / 代码题

**Q9.** 审查 `TIMELINE` 数据：

```python
TIMELINE = [
    ("2024-08-01", "EU AI Act enters into force"),
    ("2024-12-00", "Korean AI Framework Act passed by National Assembly"),
    ("2025-01-00", "Korean AI Framework Act enacted (effective Jan 2026)"),
    ("2025-02-02", "EU AI Act: prohibited practices and AI literacy apply"),
    ("2025-02-00", "UK AISI renamed -> AI Security Institute"),
    ...
]
```

1. 找出至少三个数据质量问题（格式、顺序、信息缺失）。
2. 用 `@dataclass` 重新设计一条时间线记录：至少包含日期、日期精度、法域、类别（生效 / 适用 / 草案 / 更名）和描述；说明这样设计的好处。

**Q10.** 写一个函数 `milestones_on(query: str) -> list`，返回在给定日期（`YYYY-MM-DD`）**当天或之前**已发生的里程碑，要求能处理 `-00` 日期。然后回答：

1. 从 EU AI Act 生效（2024-08-01）到全面适用（2026-08-02）、到存量 GPAI 截止（2027-08-02）分别相隔多少天、约多少个月？
2. 若把 `-00` 一律当作当月 1 日，`milestones_on("2026-03-15")` 会把"Transparency Code second draft（2026-03-00）"算作已发生。这种处理有什么风险？应该怎么改？

**Q11.**（讲义练习 2）一个部署：美国公司开发，运行在欧盟的云基础设施上，服务韩国用户。请按 `outputs/skill-regulatory-map.md` 的五个部分写出映射表，并指出在"透明度标识""风险评估""本地代表"三个实质问题上分别由哪条规则起约束作用。

**Q12.** 讲义说 EU AI Act 罚则"up to 15M EUR or 3% of global turnover"。

1. 条例原文（第 99 条）对企业的表述是"两者取较高者"。分别计算全球年营业额 2 亿欧元与 20 亿欧元的企业的罚款上限。
2. 讲义把"15M / 3%"写成罚则的上限。这个说法完整吗？

---

## 四、面试高频题

**Q13.**（基础必考）请概述 EU AI Act 的风险分层与分阶段生效时间表，并各举一个例子。

**Q14.**（原理深挖）EU AI Act 用"训练算力 > 1e25 FLOP"来界定系统性风险 GPAI。用算力作门槛有什么优点和缺点？还能用什么指标？

**Q15.**（工程实践）你是一家 GPAI 提供者的安全工程师。请把公司已有的技术控制（水印、模型卡/系统卡、训练数据摘要、红队评测、日志）映射到 EU AI Act / GPAI Code of Practice 的义务，并指出缺口。

**Q16.**（场景设计）（讲义练习 5）一家湾区公司向韩国用户提供生成式 AI 服务。韩国 AI 基本法的"本地代表"要求对它的运营有哪些具体影响？

**Q17.**（追问型）"多法域部署只要遵守最严格的那个（通常是欧盟）就行了"——你同意吗？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："In force 1 August 2024"；"2 Feb 2025: prohibited practices + AI literacy"。A 把 GPAI 的适用日当成了生效日；B 错，高风险系统是最晚的一批（Annex III 系统随 2026-08-02 全面适用，嵌入式高风险到 2027-08-02，讲义还提到委员会在 2025 年底提议把高风险时间表调整 16 个月）；D 把"全面适用"误当成"生效"——生效（entry into force）与适用（application）是两个概念。

### Q2 — 答案：A

讲义："systemic-risk GPAI (>1e25 FLOP training compute) have additional obligations"，Key Terms 也称其为"the 1e25 FLOP threshold"。B、C 都不是本条例的认定方式（C 的"4500 万用户"是欧盟《数字服务法》中"超大型平台"的口径，容易混淆）；D 把罚款数额当成了门槛。

### Q3 — 答案：D

讲义："Transparency. All GPAI providers. Copyright. All GPAI providers. Safety and Security. Systemic-risk GPAI providers (estimated 5-15 companies)."共 12 项承诺，由 AI Office 主持的 Signatory Taskforce 管理实施，2026-08-02 开始执法。A、B 混淆了约束范围；C 是编造的章节名。

### Q4 — 答案：B

讲义："The rebrand narrows scope: drops algorithmic bias and free-speech framings; focuses on frontier capability security."同时英国 AISI 仍保持强评测基础设施（开源 Inspect、与 Redwood 合作 control safety case）。A 混淆了美国（CAISI 在 NIST 下）；C 错，英国到 2026 年都没有全面的 AI 法规（skill 文件："The UK does not have a comprehensive AI regulation (2026); sectoral rules apply"）；D 无依据。

### Q5 — 答案：A

讲义："Article 12 establishes an AISI under the Ministry of Science and ICT (MSIT). Mandates: Local representatives for foreign AI companies operating in Korea; Risk assessment for 'high-impact' AI systems; Safety measures for generative AI and high-impact AI."B、C 与事实相反；D 错，韩国法是 MSIT 主导、以外国提供者为重点的独立框架，并非照搬欧盟。

### Q6 — 答案：D

讲义："Limited-risk systems. Transparency obligations under Article 50 (AI-generated content labelling). Applied 2 August 2026."透明度守则："First draft 17 December 2025. Second draft March 2026. Final version June 2026 … the regulatory layer that requires Lesson 23's watermarking technology."（第 23 节讲义注明截至 2026 年 4 月仍是草案，时间表可能变化。）A 属于系统性风险 GPAI 的 Safety and Security 范畴；B 把第 50 条与第 5 条混淆；C 错，第 50 条面向的是"有限风险"层，与是否高风险无关。

### Q7 — 答案：C

讲义："Shift toward 'pro-growth AI policies' per VP Vance's Paris AI Action Summit remarks. Reduced emphasis on pre-deployment evaluation; emphasis on standards and innovation support."A、B 恰好相反；D 夸大了——讲义只说州法"fill federal gaps"，联邦机构仍在（改名而非解散）。

### Q8 — 答案：B

实际运行：`datetime.date.fromisoformat("2025-02-00")` 抛出 `ValueError: day is out of range for month`，所以 A 错；ISO 8601 表示"只知道年月"的写法是 `2025-02`，没有 `-00`，所以 D 错。我们检查列表顺序：`"2025-02-02"` 后面紧跟 `"2025-02-00"`，按字符串比较是逆序的，所以 C 错。脚本只是原样打印，不会出错，但一旦有人对它排序或做日期计算，就会出现顺序变化或异常（见 Q9、Q10）。

### Q9 — 参考答案

1. **数据质量问题**：
   - **伪日期 `-00`**：用不存在的"第 0 天"表示"只知道月份"，无法被标准日期库解析，也无法和精确日期正确比较。
   - **顺序不一致**：`2025-02-02` 排在 `2025-02-00` 之前；按字符串或按日期排序都会改变顺序。
   - **缺少法域与类别字段**：法域只写在描述文本里（"EU AI Act: …"、"Korean …"），无法按法域筛选；也没有区分"生效 / 开始适用 / 草案 / 更名"。
   - **草案与确定日期混在一起**：`2026-06-00 Transparency Code final version` 在讲义中是"预计"日期（第 23 节讲义注明截至 2026 年 4 月仍为草案、时间表可能变化），但表中与已发生的事件写法一样。
   - **与讲义略有出入的细节**：讲义说委员会在 2025 年底提议把高风险时间表调整 16 个月，时间线中没有体现，读者会以为 2026/2027 的高风险日期是确定的。
   - 另外，讲义标注本节"**Type: Learn**、**Languages: none**"，Use It 一节写"No code"，但目录里实际有 `code/main.py`——讲义与代码不一致。
2. 参考设计：

```python
from dataclasses import dataclass
from datetime import date
from typing import Literal

@dataclass(frozen=True)
class Milestone:
    day: date                                   # 精度不足时取当期第一天
    precision: Literal["day", "month"]          # 明确记录精度
    jurisdiction: Literal["EU", "UK", "US", "KR"]
    kind: Literal["in_force", "applies", "draft", "planned", "rename", "publication"]
    text: str
    tentative: bool = False                     # 预计 / 可能变化

TIMELINE = sorted([
    Milestone(date(2024, 8, 1), "day", "EU", "in_force", "EU AI Act enters into force"),
    Milestone(date(2025, 2, 1), "month", "UK", "rename", "UK AISI -> AI Security Institute"),
    Milestone(date(2026, 6, 1), "month", "EU", "planned", "Transparency Code final", tentative=True),
    # ...
], key=lambda m: m.day)
```

   好处：类型明确、可按法域/类别过滤、排序可靠；显示时按 `precision` 输出 `2025-02` 或 `2025-02-02`；`tentative` 让"预计日期"在输出中被标注出来，避免把计划当事实。

### Q10 — 参考答案

```python
from datetime import date

def parse(s: str) -> tuple[date, bool]:
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d) or 1), d == "00"   # 返回 (日期, 是否只有月份精度)

def milestones_on(query: str):
    q = date.fromisoformat(query)
    return [(d, e) for d, e in TIMELINE if parse(d)[0] <= q]
```

1. 用 `datetime` 实际计算：2024-08-01 → 2025-02-02 为 185 天（约 6 个月）；→ 2025-08-02 为 366 天（约 12 个月）；→ 2026-08-02 为 **731 天（约 24 个月）**；→ 2027-08-02 为 **1096 天（约 36 个月）**。即"6 / 12 / 24 / 36 个月"的阶梯式过渡期。
2. `milestones_on("2026-03-15")` 的最后三条输出是 `2025-12-17 第一稿`、`2026-01-00 韩国法生效`、`2026-03-00 第二稿`。把 `-00` 当作 1 日会让"只知道在 3 月"的事件在 3 月 1 日就被判为已发生——如果它实际发生在 3 月 28 日，3 月 15 日的查询就错了。在合规场景下，提早一天和晚一天都可能导致错误判断。改法：对 `precision == "month"` 的记录返回三态结果（"已发生 / 未发生 / 本月内、无法确定"），或者让调用方选择保守策略（义务类事件取月初，以免错过截止；"已完成"类事件取月末）。

### Q11 — 参考答案

| 部分 | 结论 |
|---|---|
| 1. EU 暴露 | 讲义 skill 的保守规则："If the deployment touches EU users or infrastructure, apply the EU AI Act"。运行在欧盟基础设施上，按 skill 应纳入评估：先判定风险层级（是否为 GPAI 提供者、是否面向 Annex III 场景、是否需要第 50 条标识），再列出对应日期。注意：条例自身的适用范围以"投放欧盟市场 / 输出在欧盟使用"为主，仅基础设施位于欧盟时是否触发需要法律意见确认——skill 选择从严 |
| 2. UK 暴露 | 无英国用户，不适用（若有，英国没有全面 AI 法，适用行业规则与 AISI 评测预期） |
| 3. US 暴露 | 公司在美国：联邦层面 CAISI / NIST 标准（pro-growth、以自愿标准为主）；州法设底线（skill 点名加州 AB 2013、科罗拉多 AI 法案）——要看公司注册州和业务涉及的州 |
| 4. Korea 暴露 | 服务韩国用户：适用韩国 AI 基本法；判断是否为生成式 AI / 高影响 AI；外国提供者须设**本地代表** |
| 5. 约束规则 | 见下 |

- **透明度标识**：用户在韩国，韩国法对生成式 AI 有安全/透明要求；若同时被纳入 EU 评估，第 50 条（2026-08-02 起）的标识要求通常更具体——实践中取"标识 + 水印 + C2PA"的并集来同时满足二者。
- **风险评估**：韩国的"高影响 AI 风险评估"直接针对这批用户；EU 的高风险合格评定只在用途属于 Annex III 且触发欧盟适用时才需要。
- **本地代表**：只有韩国法有这一针对本次部署的硬性要求，没有"更严格的替代"——这正是"只遵守最严格者"不够用的例子（见 Q17）。

讲义 skill 的拒答规则："If the user asks 'is this deployment compliant,' refuse the binary claim without jurisdiction-by-jurisdiction mapping."

### Q12 — 参考答案

1. 上限 = max(15M, 3% × 营业额)：营业额 2 亿欧元 → 3% 为 600 万，取较高者 **1500 万欧元**；营业额 20 亿欧元 → 3% 为 **6000 万欧元**，高于 1500 万。（"取较高者"是条例对企业的表述，讲义中没有写出；对中小企业条例规定取两者中较低者。）
2. 不完整。按条例第 99 条，罚款分档：违反第 5 条禁止性实践的最高一档为 3500 万欧元或全球营业额 7%；违反其他多数义务为 1500 万欧元或 3%；向监管机构提供不正确信息为 750 万欧元或 1%。讲义（以及中文译文更离谱的"15 万欧元"）只给出了中间一档。GPAI 提供者的罚款另有专门条款，讲义的"15M / 3%"与那一档一致。面试中说清"分档"比背一个数字更有说服力。

### Q13 — 参考回答要点

- **分层**：
  - 禁止性实践（第 5 条）：社会评分、公共场所实时远程生物识别（执法有例外）、利用弱势群体的操纵；2025-02-02 起适用。
  - 高风险系统（Annex III）：招聘筛选、教育评分、信贷评估、执法、司法、移民等；需合格评定、风险管理、日志、透明度。
  - GPAI 模型：2025-08-02 起；所有提供者有基础义务，> 1e25 FLOP 的系统性风险 GPAI 有额外义务。
  - 有限风险：第 50 条透明度（聊天机器人披露、AI 生成内容与 deepfake 标识）；2026-08-02 起。
- **时间线**：2024-08-01 生效 → +6 个月禁止性实践与 AI 素养 → +12 个月 GPAI 与治理 → +24 个月全面适用与罚则 → +36 个月存量 GPAI 与嵌入式高风险。
- 加分点：区分"生效"与"适用"；提到 GPAI Code of Practice 是证明合规的途径（2026-08-02 前接受善意合规）；提到委员会 2025 年底提议调整高风险时间表。
- 常见误区：以为 2024 年生效即所有义务立即适用。

### Q14 — 参考回答要点

- **优点**：客观、可事先计算、可审计；与能力大致相关（scaling law）；提供者在训练前就能判断自己是否会被纳入，有可预期性。
- **缺点**：
  - 算法效率提升后，同等能力所需算力下降，门槛会"漂移"——低于 1e25 也可能有前沿能力；
  - 蒸馏、微调、合并开源权重等途径不一定被计入"训练算力"；
  - 算力不等于风险：同样规模的模型用途差异巨大；
  - 计算口径（是否计入合成数据生成、RL 阶段）有歧义。
- **替代/补充指标**：能力评测（如第 17、18 节讨论的危险能力评测与 FSF/RSP 阈值）、用户规模、部署方式（开放权重 vs API）、监管机构的个案认定。
- 加分点：讲义估计受 Safety and Security 章约束的公司只有 5–15 家，说明门槛设计意在"只抓前沿"。

### Q15 — 参考回答要点

| 技术控制 | 对应义务 | 常见缺口 |
|---|---|---|
| 模型卡 / 系统卡（第 26 节） | GPAI Transparency 章：向 AI Office 与下游提供者提供技术文档 | 缺少训练算力、能耗、评测方法等字段 |
| 训练数据摘要、数据溯源（第 27 节） | Copyright 章：版权政策、尊重 opt-out；数据来源说明 | 无法追溯爬取时的 robots.txt / TDM 保留状态 |
| 红队评测、危险能力评测 | Safety and Security 章（仅系统性风险 GPAI）：风险评估与缓解 | 评测不覆盖 agent 场景；无第三方评测 |
| 水印 + C2PA（第 23 节） | 第 50 条：AI 生成内容可被机器识别、deepfake 标识 | 文本水印抗改写差；元数据可剥离 |
| 日志与事故响应 | 高风险系统的日志义务；系统性风险 GPAI 的严重事件报告 | 日志保留期限、事故上报流程未定义 |

- 方法：先做"义务清单 × 控制清单"的矩阵，空格就是缺口；再按适用日期排优先级（GPAI 义务已于 2025-08-02 适用，执法 2026-08-02 开始）。
- 加分点：说明 Code of Practice 不是法律本身，而是证明合规的推荐路径；签署后由 Signatory Taskforce 跟进。

### Q16 — 参考回答要点

- **法律实体与人员**：需要在韩国指定本地代表（个人或法人），承担与监管机构（MSIT 及其下设 AISI）对接、接收通知、提交材料的职责。
- **合规流程**：判断服务是否属于生成式 AI / 高影响 AI；对高影响场景做风险评估并留档；落实生成式 AI 的安全措施（如生成内容告知/标识）。
- **数据与沟通**：本地代表要能及时拿到技术文档、风险评估、事故记录——需要内部的文档管理与翻译流程；监管问询可能要求韩语材料。
- **成本与责任**：本地代表的委托合同、责任划分、保险；产品发布节奏要预留合规评审时间。
- **与其他法域的复用**：EU 对欧盟外的 GPAI 提供者也有指定授权代表的要求（条例第 54 条），可复用同一套"本地代表 + 文档包"的机制，但两地的对接机构、语言、触发条件不同。
- 常见误区：以为"服务器不在韩国就不受韩国法约束"——讲义明确该法针对在韩国运营的外国 AI 公司。

### Q17 — 参考回答要点

- **部分同意**：在可比较的维度上（例如透明度标识的详细程度、罚则力度），EU AI Act 往往最严格，以它为基线能覆盖大部分义务，这也是讲义的结论。
- **但不完全成立**：
  - 义务不是一条直线上的"严格度"，而是不同类别的集合：韩国的本地代表、美国各州的特定披露（如加州 AB 2013 的训练数据披露，见第 27 节）在欧盟法中没有一一对应的条款；
  - 不同法域的定义不同（"高风险"vs"高影响"），同一系统可能在一地被归为高风险、在另一地不是；
  - 某些要求可能冲突（如数据本地化与集中式日志）；
  - 时间表不同：韩国 2026 年 1 月已生效，欧盟全面适用在 2026 年 8 月。
- **正确做法**：先逐法域映射，再对每个**实质问题**找出起约束作用的规则（skill 第 5 部分），取义务的**并集**而不是只看"最严格的那个法"。skill 的拒答规则："If the user asks for a single global compliance strategy, refuse — the jurisdictions have different requirements."
- 加分点：指出监管态势在变化——英国收窄、美国转向 pro-growth、欧盟提议调整高风险时间表——合规映射需要定期复审。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：实验室自愿治理，本节的强制监管是它的对照面。
- [阶段 18 · 23 水印：SynthID、Stable Signature、C2PA](../../23-watermarking-synthid-stable-signature-c2pa/docs/zh.md)：第 50 条透明度义务所依赖的技术层。
- [阶段 18 · 10 AI 控制：面对蓄意破坏仍能保障安全](../../10-ai-control-subversion/docs/zh.md)：英国 AISI 与 Redwood 合作的 control safety case。
- [阶段 15 · 22 CAIS、CAISI 与社会规模风险](../../../15-autonomous-systems/22-cais-caisi-societal-risk/docs/zh.md)：CAISI 的背景与社会级风险讨论。

### 本节被哪些后续内容用到
- [阶段 18 · 25 EchoLeak 与 AI 领域 CVE 的出现](../../25-echoleak-cves-for-ai/docs/zh.md)：监管之外的另一条问责通道——漏洞披露。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../26-model-system-dataset-cards/docs/zh.md)：GPAI Transparency 章对应的文档工件。
- [阶段 18 · 27 Data Provenance 与训练数据治理](../../27-data-provenance-training-governance/docs/zh.md)：Copyright 章、加州 AB 2013 等训练数据披露要求。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../../17-infrastructure-and-production/26-compliance-frameworks/docs/zh.md)：把监管要求落到生产系统的合规工程。
- [阶段 15 · 21 METR 时间跨度与外部能力 Evaluation](../../../15-autonomous-systems/21-metr-external-evaluation/docs/zh.md)：系统性风险 GPAI 所需的外部评测实践。

### 延伸关键词
`Regulation (EU) 2024/1689` · `entry into force vs application` · `Annex III` · `GPAI with systemic risk` · `1e25 FLOP` · `AI Office` · `Code of Practice` · `Article 50` · `Digital Omnibus` · `UK AI Security Institute` · `Inspect` · `CAISI` · `California AB 2013` · `Colorado AI Act` · `Korean AI Basic Act` · `MSIT` · `local representative`
