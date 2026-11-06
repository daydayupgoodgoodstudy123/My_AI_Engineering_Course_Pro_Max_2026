# 测验 · Data Provenance 与训练数据治理（Data Provenance and Training-Data Governance）

> **阶段 18 · 伦理、安全与对齐 · 第 27 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> **提示**：中文讲义把多个机构名译错（Irish DPC →"爱尔兰民主党"、UK ICO →"联合王国国际竞争组织"、Brazilian ANPD →"巴西国家残疾人协会"），请以 [English](../docs/en.md) 为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 训练数据治理是一切的上游 | 讲义：它是每张模型卡（第 26 节）和每项监管义务（第 24 节）的上游；收集时不合规，下游无法补救 |
| 2 | California AB 2013 | 2024 年签署的生成式 AI 训练数据透明度法；对 2022-01-01 及以后发布的系统，须在 2026-01-01 前公布文档；第 3111(a) 节要求 12 项数据集高层摘要 |
| 3 | AB 2013 的 12 项 | 来源/所有者、如何服务预期目的、数据点数量、数据点类型、是否含受版权/商标/专利保护内容、是否购买/许可、是否含个人信息、是否含聚合消费者信息、清洗处理、收集时间段、首次使用日期、是否使用合成数据生成 |
| 4 | 关键项的连锁义务 | 第 12 项（合成数据）相对 Gebru datasheet 是新增；第 7 项（个人信息）触发 CPRA 义务；第 3111(b) 节豁免安全/完整性、航空器运行、仅限联邦的国家安全系统 |
| 5 | EU TDM 例外与 opt-out | 欧盟版权指令的文本与数据挖掘例外允许训练公开内容，除非权利人 opt-out；GPAI Code of Practice 的 Copyright 章要求尊重机器可读的 opt-out 信号（robots.txt、C2PA "No AI Training" 等） |
| 6 | 2025 年 DPA 趋同 | Irish DPC（2025-05-21）在 EDPB 意见后接受 Meta 用欧盟成年用户公开内容训练；科隆高等地区法院（2025-05-23）驳回禁令；汉堡 DPA 放弃紧急程序；UK ICO（2025-09-23）对 LinkedIn 作出正面回应但**不是正式批准**——趋同原则：合法利益 + opt-out + 保障措施，不要求同意 |
| 7 | 巴西 ANPD 的不同路径 | 因信息透明度不足暂停 Meta 的训练处理（讲义摘要写 2024-07-02、正文标题写 2024 年 6 月），Meta 提交合规计划后于 2024-08-30 解除——优先透明度而非合法利益 |
| 8 | 不可逆性问题 | Cookie 同意是为实时、可撤销的追踪设计的；数据一旦进入权重就无法"外科手术式"删除，唯一彻底的补救是从头重训——GDPR 删除权对训练好的网络没有实际等价物 |
| 9 | 部分补救 | Unlearning（近似删除，用第 22 节的 MIA 度量）、基于 influence function 的定位与局部更新、微调抑制输出——都不能彻底解决；合规窗口在**收集时** |
| 10 | Consent in Crisis | Data Provenance Initiative（Longpre、Mahari、Lee 等，2024 年 7 月）：发布者加速添加 robots.txt 限制，可公开训练的数据公地快速收缩；讲义：2023→2024 约 25% 的顶级训练来源新增了某种限制 |

### 核心技能（能动手做到）

- [ ] 默写 AB 2013 的 12 项，并为一个数据集填写摘要
- [ ] 指出本节代码 `flag_followups` 中 Y/N 判断不一致导致的漏报，并修复它
- [ ] 写一个"字段欠规范"检查器：缺失、空值、Y/N 字段不是明确的 Y/N
- [ ] 用标准库 `urllib.robotparser` 检查某个爬虫 User-agent 是否被 robots.txt 允许，并说出 robots.txt 作为 AI 训练 opt-out 信号的局限
- [ ] 设计一个与 AB 2013 字段组合的数据溯源清单（manifest），用哈希链记录"原始数据 → 清洗 → 训练"的每一步
- [ ] 解释为什么"训练后再删除"不可行，以及 unlearning 的局限

---

## 二、基础自测（选择题）

**Q1.** 讲义反复强调"compliance window is at collection time"，根本原因是：

- A. 收集数据时监管机构会现场检查
- B. 训练后的模型权重属于商业秘密，监管机构无权要求删除
- C. 数据一旦进入模型权重就无法精确删除，唯一彻底的补救是从头重训，代价极高
- D. GDPR 只适用于数据收集阶段

**Q2.** 关于 California AB 2013，下列说法正确的是：

- A. 要求生成式 AI 开发者公布含 12 项法定内容的训练数据集高层摘要；对 2022-01-01 及以后发布的系统，须在 2026-01-01 或之前公布
- B. 要求公布 7 项内容，与 Gebru datasheet 完全一致
- C. 只适用于参数量超过 1e25 FLOP 的模型
- D. 要求开发者在用户请求时删除模型权重中的个人数据

**Q3.** AB 2013 的 12 项中，讲义指出**相对 Gebru 等 2018 datasheet 新增**的是哪一项？

- A. 数据集的来源或所有者
- B. 数据点的数量
- C. 数据收集的时间段
- D. 系统是否使用（或持续使用）合成数据生成

**Q4.** 2025 年欧洲各数据保护机构（DPA）与法院在"用公开内容训练 LLM"问题上趋同的原则是：

- A. 必须逐一取得每位用户的明确同意
- B. 合法利益（legitimate interest）可以作为用第一方公开内容训练的依据，前提是提供 opt-out 和适当保障措施；不要求同意
- C. 所有用公开内容训练的行为都被禁止
- D. UK ICO 已正式批准所有社交平台用用户数据训练

**Q5.** 巴西 ANPD 对 Meta 的处理与欧盟 DPA 的不同之处在于：

- A. ANPD 对 Meta 处以全球营业额 7% 的罚款
- B. ANPD 要求 Meta 删除已训练的模型
- C. ANPD 以信息透明度不足为由暂停了 Meta 用巴西用户数据训练 AI，Meta 提交合规计划后该预防措施于 2024-08-30 解除
- D. ANPD 认为合法利益不能作为任何数据处理的依据

**Q6.** Data Provenance Initiative 的 "Consent in Crisis"（2024 年 7 月）的主要发现是：

- A. 发布者正在加速添加 robots.txt 限制，可公开训练的 AI 数据公地在快速收缩；讲义称 2023→2024 约 25% 的顶级训练来源新增了限制
- B. 绝大多数网站已经取消了 robots.txt
- C. 合成数据已完全取代网络爬取数据
- D. robots.txt 对 AI 爬虫没有任何影响，因此不需要审计

**Q7.** 在本节代码中，把个人信息字段填成 `"Y (user emails)"`，调用 `flag_followups`：

```python
    if summary["contains_personal_information (Y/N, per Cal. Civ. Code §1798.140(v))"] == "Y":
        flags.append("triggers CPRA obligations (California Privacy Rights Act)")
    ...
    if summary["contains_copyright_trademark_or_patent_protected (Y/N) or fully_public_domain"].startswith("Y"):
        flags.append("must respect EU TDM opt-out signals (EU Copyright Directive)")
```

结果是：

- A. 触发 CPRA 提示
- B. 抛出 `ValueError`
- C. 触发 EU TDM opt-out 提示
- D. **不**触发 CPRA 提示——个人信息字段用的是 `== "Y"` 精确比较，而版权、合成数据字段用的是 `.startswith("Y")`，判断方式不一致

**Q8.** 如果 `summary` 字典里**缺少**个人信息这个键，调用 `render_markdown(summary)` 会：

- A. 在该行显示 `(missing)`，然后正常输出
- B. 抛出 `KeyError`——`render_markdown` 渲染字段时用的是 `.get(field, '(missing)')`，但随后调用的 `flag_followups` 用 `summary[...]` 直接取值
- C. 自动把缺失字段当作 `"N"`
- D. 跳过该字段，不输出也不报错

---

## 三、动手 / 代码题

**Q9.** 修复 `flag_followups`：

1. 写一个 `yn(value)` 函数，把 `"Y"`、`"Y (user emails)"`、`"yes"`、`"N (synthetic)"` 等统一解析为 `True / False`，无法判断时返回 `None`；
2. 改写 `flag_followups`，使它对缺失字段、空值、不明确的 Y/N 返回"问题清单"而不是崩溃或静默漏报；
3. 用 `"Y (user emails)"` 和"删除个人信息字段"两种输入验证。

**Q10.**（讲义练习 1）审查 `TOY_EXAMPLE` 这份 12 项摘要：

1. 哪些字段写得具体、哪些是"欠规范"的？`flag_followups` 对它输出的唯一提示 "may still trigger obligations on the base model used for generation" 合理吗？
2. 这份摘要描述的是一个**二分类**教学数据集。从 AB 2013 的适用对象看，它真的需要这份摘要吗？
3. 与第 26 节 datasheet 里那个同样"用 `random.gauss` 生成"的玩具数据集相比，你发现了什么不一致？

**Q11.**（讲义练习 2）用 Python 标准库检查 robots.txt：

```text
User-agent: GPTBot
Disallow: /

User-agent: *
Allow: /
```

1. 用 `urllib.robotparser.RobotFileParser` 判断 `GPTBot`、`CCBot`、`MyLabCrawler` 能否抓取 `https://news.example/article/1`。
2. 这个结果说明 robots.txt 作为"AI 训练 opt-out"信号有哪些局限？与 C2PA "No AI Training" 声明相比各有什么优缺点？

**Q12.**（讲义练习 5）设计一个训练数据溯源清单（provenance manifest）：

1. 它如何与 AB 2013 的 12 项字段组合？
2. 用哈希链记录"原始抓取 → 去重 → PII 过滤 → 分词"每一步的输入/输出哈希，写出生成与校验代码，并演示篡改任一记录后校验失败。
3. 指出一个技术障碍和一个法律障碍。

---

## 四、面试高频题

**Q13.**（基础必考）为什么说训练数据治理的"合规窗口在收集时"？GDPR 的删除权（right to erasure）在 LLM 上会遇到什么问题？有哪些部分补救手段？

**Q14.**（原理深挖）2025 年欧洲 DPA 为什么会在"合法利益 + opt-out"上趋同？请构造一个合法利益**不足以**支撑训练的场景，并说明此时需要什么法律依据。（讲义练习 4）

**Q15.**（工程实践）你负责一个预训练数据管道，要同时满足 AB 2013 和 EU GPAI Code of Practice 的 Copyright 章。请设计管道中的治理环节。

**Q16.**（场景设计）"Consent in Crisis"显示可公开训练的数据在快速收缩。作为一家模型公司，你会怎样调整数据获取策略？请论述一个经济后果。（讲义练习 3 的后半部分）

**Q17.**（追问型）"我们的数据集全是合成数据，所以不用管数据溯源和版权"——你怎么回应？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："once data enters model weights, surgical erasure is not possible. Retraining from scratch is the only complete remediation, and it is prohibitively expensive."A、B 无依据；D 错，GDPR 适用于整个处理生命周期，问题在于训练后的模型在**技术上**无法满足删除要求。

### Q2 — 答案：A

讲义："Signed 2024. Documentation must be posted on or before January 1, 2026 for systems released on or after January 1, 2022. Section 3111(a) requires … 12 statutory items."B 错在数量和"完全一致"（第 12 项就是新增的）；C 把 EU AI Act 的系统性风险门槛张冠李戴；D 描述的是一个法律并未规定、技术上也做不到的要求。

### Q3 — 答案：D

讲义："Item 12 (synthetic data) is new relative to Gebru et al. 2018 datasheets."来源、数量、收集时间段在 Gebru datasheet 的 Motivation / Composition / Collection Process 中都有对应问题。

### Q4 — 答案：B

讲义："Convergent principle: legitimate interest can justify training on publicly available first-party content with opt-out. Consent is not required."A 与趋同原则相反；C 错；D 错，讲义两次强调 UK ICO 的回应"not a formal clearance"，并且仍在持续监测。

### Q5 — 答案：C

讲义摘要："Brazilian ANPD (2 July 2024) suspended Meta's processing over insufficient information transparency; the preventive measure was lifted on 30 August 2024 after Meta submitted a compliance plan."正文："ANPD prioritized transparency over legitimate-interest admissibility."A、B 无依据；D 夸大了，ANPD 关注的是透明度不足，而不是否定合法利益本身。注意讲义自身的日期不一致：摘要写 2024-07-02，正文标题写"June 2024"。

### Q6 — 答案：A

讲义："publishers are adding robots.txt restrictions at an accelerating rate. The openly-trainable-upon commons is contracting rapidly. 2023 -> 2024 saw about 25% of the top training sources add some restriction."B、D 与发现相反；C 无依据——讲义说未来数据获取依赖"licensing, synthetic generation, incentivized participation"等新范式，而不是合成数据已经取代一切。

### Q7 — 答案：D

实际运行：个人信息字段为 `"Y (user emails)"` 时，`flag_followups` 只返回 `['may still trigger obligations on the base model used for generation']`，**CPRA 提示被漏掉**；只有恰好写成 `"Y"` 才会触发。同样，`"yes"` 也不会触发。代码对 PI、聚合消费者信息、购买/许可三个字段用 `== "Y"`，对版权、合成数据两个字段用 `.startswith("Y")`。A 是"预期行为"而不是实际行为；B 不会发生；C 不对，版权字段仍是 `"N (...)"`。在合规工具中，这种"静默漏报"比报错更危险。

### Q8 — 答案：B

实际运行：删除个人信息键后调用 `render_markdown`，抛出 `KeyError: 'contains_personal_information (Y/N, per Cal. Civ. Code §1798.140(v))'`。渲染循环里的 `summary.get(field, '(missing)')` 本来能优雅地标出缺失，但函数随后调用 `flag_followups(summary)`，后者用方括号直接取值。A 是作者想要的效果，但被后面的调用打断；C、D 都不会发生。另外，如果字段存在但是空字符串，渲染结果是 `- **dates_first_used_during_development**: `，既不报错也不提示——同样需要检查。

### Q9 — 参考答案

```python
import re

F = {k.split(" ")[0]: k for k in AB_2013_FIELDS}       # 短名 -> 完整字段名

def yn(value: str):
    m = re.match(r"^(y|yes|n|no)\b", value.strip(), re.I)
    return None if not m else m.group(1)[0].upper() == "Y"

def flag_followups_v2(summary: dict):
    flags, problems = [], []
    for f in AB_2013_FIELDS:                              # 缺失与空值
        if not summary.get(f, "").strip():
            problems.append(f"missing: {f}")
    checks = [
        ("contains_personal_information", "triggers CPRA obligations (California Privacy Rights Act)"),
        ("contains_aggregate_consumer_information", "aggregate consumer information disclosure obligations apply"),
        ("contains_copyright_trademark_or_patent_protected", "must respect EU TDM opt-out signals (EU Copyright Directive)"),
        ("uses_synthetic_data_generation", "may still trigger obligations on the base model used for generation"),
        ("purchased_or_licensed", "retain license terms and provenance records for audit"),
    ]
    for short, msg in checks:
        r = yn(summary.get(F[short], ""))
        if r is None:
            problems.append(f"not a clear Y/N: {short}")
        elif r:
            flags.append(msg)
    return flags, problems
```

实际运行：
- `"Y (user emails)"` → `flags` 包含 `triggers CPRA obligations ...`，`problems` 为空；
- 删除个人信息键 → `problems` 为 `['missing: contains_personal_information (...)', 'not a clear Y/N: contains_personal_information']`，不再崩溃；
- 原始 `TOY_EXAMPLE` → 与原版输出一致。

要点：统一用一个解析函数处理所有 Y/N 字段；**无法判断时显式报告**而不是当作 N（fail-closed）；版权字段允许的第三种答案 `fully_public_domain` 会被归为"not a clear Y/N"，需要单独处理。

### Q10 — 参考答案

1. **具体的字段**：数据来源（in-repo、`random.gauss`）、数量（1,000）、类型（两个实数特征 + 二元标签）、是否合成（Y）、收集时间（2026-04，不持续）、首次使用日期（2026-04-22）。**欠规范之处**：
   - `how_dataset_furthers_intended_purpose` 只写"pedagogical demonstration"，没说明数据性质与目的之间的关系；
   - `cleaning_processing_or_modification_description: none`——标签是由某条规则生成的，这本身就是一种"处理"，应写明规则；
   - 没有生成脚本、种子、数据哈希，任何人都无法核实"1,000 examples (fixed seed)"；
   - 版权字段是复合问题（受保护 / 完全公有领域），只答"N"没有回答"是否完全公有领域"。
   
   至于唯一的提示 "may still trigger obligations on the base model used for generation"：对本例是**误报**——数据是 `random.gauss` 生成的，不存在"用于生成的基础模型"。规则应区分"由模型生成的合成数据"与"程序/统计生成的数据"。
2. AB 2013 规范的是**生成式 AI**（讲义："Generative AI training-data transparency"）。一个二分类逻辑回归不是生成式 AI 系统，严格说不在该法范围内。作为练习脚手架没有问题，但在真实合规工作中，第一步应该是判断**是否适用**，而不是直接填表（skill 文件的拒答规则也要求逐法域分析）。
3. 第 26 节的 datasheet 描述"ToyBinaryClassification-1.0：1,500 synthetic examples，2-d continuous + 1 binary sensitive attribute"，本节摘要是"1,000 examples，two real-valued features"。两节的玩具数据集都用 `random.gauss` 生成、都是二分类，但样本量与特征描述不同；如果它们指同一份数据，两份文档就互相矛盾——这正是第 26 节说的"model card depends on the datasheet being accurate"在课程材料自身上的体现。

### Q11 — 参考答案

1. 实际运行：

```python
from urllib.robotparser import RobotFileParser
rp = RobotFileParser()
rp.parse(rules_text.splitlines())
rp.can_fetch("GPTBot", "https://news.example/article/1")        # False
rp.can_fetch("CCBot", "https://news.example/article/1")         # True
rp.can_fetch("MyLabCrawler", "https://news.example/article/1")  # True
```

2. **robots.txt 的局限**：
   - **按爬虫名点名**：站点只屏蔽了 GPTBot，其他 AI 爬虫（CCBot、新出现的爬虫）都被 `*` 规则放行；新爬虫不断出现，发布者只能事后追加；
   - **表达的是"访问"不是"用途"**：无法区分"可以抓来做搜索索引，但不能训练"；
   - **不随内容传播**：内容被转载、镜像或进入第三方数据集后，原站的 robots.txt 不再可见；
   - **时间性**：只反映抓取那一刻的规则，事后添加的限制不能撤回已经抓取的数据（不可逆性，Q13）；
   - **自愿遵守**：没有技术强制力。
   
   **C2PA "No AI Training" 声明**：优点是嵌在资产的签名元数据里，**随内容传播**、可验证是谁声明的；缺点是可以被剥离（第 23 节）、依赖采用率、只适用于支持 C2PA 的媒体格式。理想的 opt-out 格式应**同时**有站点级（robots.txt / HTTP 头）和资产级（嵌入元数据）信号，并能区分用途（训练 / 检索 / 搜索）。讲义还提到 TDM.Reservation 这类专门表达 TDM 保留的信号。

### Q12 — 参考答案

1. **与 AB 2013 的组合**：manifest 按数据集组织，每个数据集一条记录，12 项字段作为"摘要层"；在其下挂"证据层"：每个来源的抓取时间、抓取时的 robots.txt / opt-out 快照、许可证文本哈希、PII 扫描结果、每一步处理的哈希链。摘要中的每个回答都能链接到证据（例如第 7 项"含个人信息：Y"链接到 PII 扫描报告）。
2. 参考实现（已实际运行：未篡改时 `True`，修改第二步的 `input_sha256` 后 `False`）：

```python
import hashlib, json

def h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def make_chain(raw: bytes, steps):                # steps: [(名称, 输出字节), ...]
    chain, prev = [], h(raw)
    for name, out in steps:
        rec = {"step": name, "input_sha256": prev, "output_sha256": h(out)}
        rec["record_sha256"] = h(json.dumps(rec, sort_keys=True).encode())
        chain.append(rec)
        prev = rec["output_sha256"]
    return chain

def verify(chain, raw_hash):
    prev = raw_hash
    for r in chain:
        body = {k: r[k] for k in ("step", "input_sha256", "output_sha256")}
        if r["input_sha256"] != prev or r["record_sha256"] != h(json.dumps(body, sort_keys=True).encode()):
            return False
        prev = r["output_sha256"]
    return True

chain = make_chain(b"crawled html ...", [("dedup", b"dedup text"),
                                         ("pii_filter", b"filtered text"),
                                         ("tokenize", b"tokens")])
```

   说明：每条记录的输入哈希必须等于上一条的输出哈希，改动任何一步都会断链。生产中还要对整条链签名（如 C2PA 风格的签名 manifest），否则攻击者可以整体重算所有哈希。
3. **技术障碍**：Web 规模数据（数十亿文档）的逐文档溯源存储与计算开销巨大；去重、混合、采样会让"某条训练样本来自哪个来源"的映射变得多对多；历史数据集（如早年的爬取快照）根本没有保留抓取时的 opt-out 状态。**法律障碍**：各法域对"公开数据""个人信息""TDM 例外"的定义不同；清单本身可能暴露商业秘密或个人信息（公开得越细，泄露风险越高）；AB 2013 的摘要一旦公布即具有约束力（skill 文件："the summary becomes binding once published"），细节写错会带来法律责任。

### Q13 — 参考回答要点

- **合规窗口在收集时**：Cookie 同意适用于可实时撤销的追踪；而训练数据进入权重后，模型参数是所有数据的混合函数，无法定位和删除某个人的贡献。讲义："Retraining from scratch is the only complete remediation, and it is prohibitively expensive."
- **删除权的问题**：用户要求删除时，可以删除原始数据存储，但模型可能已经记住（memorization）并能复现该数据；GDPR 删除权"对训练好的神经网络没有实际等价物"。
- **部分补救**：
  - Machine unlearning：近似地降低模型对特定数据的依赖，用第 22 节的成员推断攻击（MIA）评估效果；
  - 基于 influence function 定位受影响最大的权重并选择性更新；
  - 微调抑制：训练模型拒绝输出该数据相关内容——数据仍在权重里，只是不输出；
  - 输出过滤：在推理层拦截。
  - 讲义："None fully solve the problem."
- **工程结论**：在收集时做 opt-out 过滤、PII 过滤、许可证检查，并记录可审计的溯源；对 PII 敏感数据考虑差分隐私训练（第 22 节）。
- 常见误区：把"微调让模型不再输出"等同于"已删除"——skill 文件硬性拒绝"assumes surgical removal of data from trained weights"的补救声明。

### Q14 — 参考回答要点

- **趋同原因**：GDPR 第 6 条的合法利益要求"目的正当、处理必要、利益平衡"；DPA 认为在**第一方**、**公开**、**成年用户**内容上，配合透明告知、简化 opt-out、延长反对窗口等保障措施，平衡测试可以通过；EDPB 意见提供了共同框架；汉堡 DPA 放弃紧急程序也是为了欧盟范围内的一致性。
- **合法利益不足的场景**（任举一例并说明理由）：
  - 训练数据含**特殊类别数据**（健康、宗教、政治观点、生物特征，GDPR 第 9 条）——第 9 条对这类数据另有更严格的要求，合法利益本身不足以作为依据，通常需要明确同意或其他特定例外；
  - 数据来自**未成年人**，或来自**私信、非公开内容**——用户的合理预期不同，平衡测试难以通过；
  - 从**第三方网站爬取**而非第一方平台、且数据主体无从得知、无法 opt-out。
- **此时的法律依据**：通常需要明确同意（explicit consent），或者通过匿名化让数据不再属于个人数据；对版权内容还要单独满足 TDM 例外 / 许可。
- 加分点：巴西 ANPD 的案例说明即使不讨论合法利益本身，**透明度不足**也足以让处理被暂停；UK ICO 的回应"not a formal clearance"，监管仍在持续。

### Q15 — 参考回答要点

- **抓取层**：遵守 robots.txt（使用公开、可识别的 User-agent）、HTTP 头和资产级的 TDM 保留 / C2PA "No AI Training" 声明；**抓取时**保存每个 URL 的 opt-out 状态快照与时间戳（skill："Pre-collection filter must be in place"）。
- **许可层**：区分自有、购买/许可、公开、公有领域；保留许可证文本与条款（对应 AB 2013 第 5、6 项）。
- **PII 层**：PII 检测与过滤、特殊类别数据的处理策略；记录是否含个人信息（第 7 项）与聚合消费者信息（第 8 项）。
- **处理层**：去重、质量过滤、合成数据生成都写入溯源链（第 9、12 项）；记录收集时间段、是否持续收集（第 10 项）与首次使用日期（第 11 项）。
- **输出层**：每个数据集自动生成 12 项摘要（Q9 的检查器作为 CI 门禁），以及 GPAI Copyright 章要求的版权政策；与模型卡的 Training Data 节联动（第 26 节）。
- **事后响应**：opt-out 请求的受理流程——从未来训练中剔除、评估 unlearning 的必要性；但不对外宣称"已从权重中删除"。
- 加分点：对第三方数据集（如开源爬取语料）要求提供上游溯源，否则视为高风险来源。

### Q16 — 参考回答要点

- **策略调整**：
  - **授权许可**：与出版商、媒体、图片库签订数据许可协议；
  - **合成数据**：用现有模型生成训练数据（但要注意 AB 2013 第 12 项的披露，以及基础模型本身的数据合规问题，见 Q17）；
  - **激励参与**：向内容创作者付费或分成，换取明确授权；
  - **第一方数据**：利用自有平台数据，在合法利益 + opt-out 框架下使用（Q14）；
  - **精细化 opt-out 遵守**：建立可信的爬虫身份与用途声明，争取发布者不全面屏蔽。
- **一个经济后果（任选论述）**：
  - 数据从"免费公地"变成"需要购买的生产要素"，训练成本上升，**有资金签许可的大公司更有优势**，市场集中度可能上升；
  - 或：数据许可成为出版商的新收入来源，内容行业与 AI 行业的谈判地位发生变化；
  - 或：开放研究与学术机构可获取的数据减少，可复现研究更困难。
- 讲义练习 3 前半部分要求说出"限制最快的三个内容类别"，这需要阅读原论文，讲义正文没有给出，答题时不要凭空编造。

### Q17 — 参考回答要点

- **合成数据不等于免责**：
  - 合成数据是由某个**基础模型**生成的，基础模型自己的训练数据合规问题会传递下来（本节代码的提示："may still trigger obligations on the base model used for generation"——前提是数据确实由模型生成）；
  - 生成提示（prompt）或种子样本可能来自真实数据（含 PII 或版权内容），模型也可能复现训练数据；
  - 基础模型的使用条款可能限制"用其输出训练其他模型"。
- **披露义务仍在**：AB 2013 第 12 项要求披露是否使用（或持续使用）合成数据生成——这正是讲义所说的相对 Gebru datasheet 的新增项。
- **溯源仍然需要**：记录生成所用的模型版本、提示模板、种子数据来源、过滤规则，才能在审计时说清"合成数据从哪里来"。
- **质量与偏差**：合成数据可能放大基础模型的偏差，模型卡与 datasheet 应如实说明。
- 结论："合成"改变的是风险形态，而不是消除风险。

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：EU AI Act 与 GPAI Code of Practice 的 Copyright 章（讲义先修）。
- [阶段 18 · 26 模型卡、系统卡与数据集卡](../../26-model-system-dataset-cards/docs/zh.md)：datasheet 是本节 12 项摘要的"前身"（讲义先修）。
- [阶段 18 · 22 面向 LLMs 的差分隐私](../../22-differential-privacy-for-llms/docs/zh.md)：成员推断攻击（MIA）用于评估 unlearning；DP 训练是"收集时 / 训练时"的保护手段。
- [阶段 10 · 03 用于预训练的数据管道](../../../10-llms-from-scratch/03-data-pipelines/docs/zh.md)：治理环节要嵌入的数据管道。
- [阶段 00 · 09 数据管理](../../../00-setup-and-tooling/09-data-management/docs/zh.md)：数据版本化与哈希校验的基础。

### 本节被哪些后续内容用到
- [阶段 18 · 28 Alignment 研究生态：MATS、Redwood、Apollo、METR](../../28-alignment-research-ecosystem/docs/zh.md)：讲义："Lesson 28 maps the research ecosystem that works on these questions."
- [阶段 18 · 23 水印：SynthID、Stable Signature、C2PA](../../23-watermarking-synthid-stable-signature-c2pa/docs/zh.md)：C2PA 签名清单与 "No AI Training" 声明的技术基础。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../../17-infrastructure-and-production/26-compliance-frameworks/docs/zh.md)：GDPR 等合规框架在生产系统中的落地。
- [阶段 19 · 07 端到端 Fine-Tuning 流程——从数据、SFT、DPO 到模型服务](../../../19-capstone-projects/07-end-to-end-fine-tuning-pipeline/docs/zh.md)：在综合项目的数据阶段落实溯源记录。

### 延伸关键词
`California AB 2013` · `Section 3111(a)` · `CPRA` · `EU Copyright Directive TDM exception` · `opt-out / TDM reservation` · `robots.txt` · `C2PA "No AI Training"` · `legitimate interest (GDPR Art. 6)` · `special category data (GDPR Art. 9)` · `EDPB opinion` · `machine unlearning` · `influence functions` · `Data Provenance Initiative` · `Consent in Crisis` · `provenance manifest`
