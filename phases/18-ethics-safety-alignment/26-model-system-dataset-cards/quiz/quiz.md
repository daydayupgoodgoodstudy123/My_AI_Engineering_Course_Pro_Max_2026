# 测验 · 模型卡、系统卡与数据集卡（Model, System, and Dataset Cards）

> **阶段 18 · 伦理、安全与对齐 · 第 26 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三种范围的文档 | Model Card 记录**模型**，Datasheet / Data Card 记录**数据**，System Card 记录**整个部署系统**（模型 + 安全栈 + 部署环境） |
| 2 | Model Card（Mitchell 等，2019） | 模型的"营养标签"，9 个标准节：Model Details、Intended Use、Factors、Metrics、Evaluation Data、Training Data、Quantitative Analyses（按因素分组）、Ethical Considerations、Caveats and Recommendations |
| 3 | 采纳问题 | 讲义：Oreamuno 等 2023 审计 Hugging Face 模型卡，只有 **0.3%** 记录了伦理考量——"最常被跳过的字段" |
| 4 | Datasheets for Datasets（Gebru 等） | 类比电子元件数据手册：Motivation、Composition、Collection Process、Labeling、Uses、Distribution、Maintenance；讲义：CACM 2021 发表，arXiv 2018 |
| 5 | Datasheet 是上游 | 讲义："the model card depends on the datasheet being accurate"——模型卡的结论强度不会超过它所依赖的数据文档 |
| 6 | Data Cards（Pushkarna 等，Google 2022） | 模块化、分层：telescopic（给非专家的概览）/ periscopic（给 ML 从业者）/ microscopic（给审计者的特征级细节）；作为"boundary object"服务不同读者 |
| 7 | System Card | 端到端：安全能力、prompt injection 防护、数据外泄检测、与人类价值观的对齐、事故响应；讲义引 Sidhpurwala 2024、Meta 系统级透明度工作与 "Blueprints of Trust"（arXiv:2509.20394） |
| 8 | 2024–2025 进展 | CardGen（LLM 自动生成模型卡）、Liang 等 2024（模型卡详细度与最高 29% 的下载量提升相关）、Laminator（TEE / 密码学的可验证证明）、Jouneaux 2025（碳、水、能耗等可持续性字段） |
| 9 | 监管工件 | 讲义：GPAI Code of Practice 的 Transparency 章把模型文档作为合规工件（第 24 节） |
| 10 | 自报 vs 可验证 | skill 文件：没有密码学证明或第三方验证的结论一律标为"self-report"；"bias-tested"必须配分组指标 |

### 核心技能（能动手做到）

- [ ] 默写 Mitchell 模型卡与 Gebru datasheet 的标准节，并指出给定卡片缺了哪些
- [ ] 写一个脚本解析 Markdown 卡片的二级标题，按 skill 文件的规则自动审计"缺节 / 占位内容"
- [ ] 按 datasheet 的描述真正生成数据、训练模型，用分组指标（准确率、选择率、TPR、FPR）填写 Quantitative Analyses，并给出置信区间
- [ ] 发现模型卡与 datasheet、系统卡之间的不一致
- [ ] 设计一个携带"评测结果可验证证明"的模型卡字段，并说明验证方要检查什么
- [ ] 为一个真实的 LLM 应用写 System Card，并判断哪一节对第三方审计价值最高

---

## 二、基础自测（选择题）

**Q1.** 下列哪一组**全部**属于 Mitchell 等（2019）原始模型卡的标准节？

- A. Motivation、Composition、Collection Process
- B. Security Capabilities、Incident Response、Prompt-injection protection
- C. Telescopic、Periscopic、Microscopic
- D. Intended Use、Factors、Quantitative Analyses、Ethical Considerations

**Q2.** 讲义引用 Oreamuno 等（2023）对 Hugging Face 模型卡的审计，记录了伦理考量（Ethical Considerations）的比例约为：

- A. 29%
- B. 0.3%
- C. 3%
- D. 50%

**Q3.** Data Cards 的 telescopic / periscopic / microscopic 三层结构，目的是：

- A. 用不同"缩放级别"的细节服务不同读者（非专家、ML 从业者、审计者），同一份文档作为 boundary object 被各取所需
- B. 分别记录训练集、验证集、测试集
- C. 对应数据的三种隐私等级
- D. 让数据卡可以被望远镜式地自动压缩

**Q4.** System Card 覆盖、而 Model Card 通常不覆盖的内容是：

- A. 模型的参数量与架构
- B. 训练数据的收集过程
- C. 端到端系统：模型 + 安全栈 + 部署环境，包括 prompt injection 防护、数据外泄检测、事故响应
- D. 模型在各人口群体上的准确率

**Q5.** 讲义说"The datasheet is the upstream documentation"，这句话的含义是：

- A. datasheet 必须比模型卡写得更长
- B. 模型卡中关于训练数据、偏差、适用范围的结论依赖 datasheet 的准确性；数据文档错了，模型卡再完整也站不住
- C. datasheet 只在模型上线后才需要编写
- D. datasheet 由下游用户负责填写

**Q6.** Laminator（Duddu 等，2024）对模型文档的贡献是：

- A. 用 LLM 自动生成模型卡
- B. 统计模型卡与下载量的关系
- C. 增加碳排放与用水字段
- D. 借助硬件 TEE / 密码学签名，为卡片中的结论附上可验证的证明（proof-of-claim），而不只是声明

**Q7.** 对照 Mitchell 2019 的 9 个标准节，本节 `code/main.py` 生成的模型卡**缺少**哪一节？

- A. Evaluation Data
- B. Intended Use
- C. Ethical Considerations
- D. Caveats and Recommendations

**Q8.** 本节代码生成的三张卡片之间存在一处事实不一致，是哪一处？

- A. 模型卡说许可证是 MIT，datasheet 说是 Apache-2.0
- B. 系统卡说是生成式模型，模型卡说是分类器
- C. 模型卡的 Factors 列出了 gender 和 age bucket 两个敏感属性，但 datasheet 的 Composition 只有"1 binary sensitive attribute"，数据里根本没有年龄
- D. datasheet 说有 1,500 条样本，模型卡说有 15,000 条

---

## 三、动手 / 代码题

**Q9.** 把 `outputs/skill-card-audit.md` 的"Section coverage"规则写成代码：

1. 写 `sections(md)`：把 Markdown 卡片按 `## ` 二级标题拆成 `{节名: [内容行]}`；
2. 写 `audit(md, kind)`：对 `kind ∈ {"model", "datasheet", "system"}` 检查缺失的标准节，并把内容中含 `placeholder`、`N/A`、`no one`、`goes nowhere` 等字样的节标为"弱"；
3. 对本节三张卡片运行，报告结果。这种"按关键字判弱"的方法有什么局限？

**Q10.**（讲义练习 2）datasheet 声称数据是"1,500 synthetic examples … 2-d continuous, 1 binary sensitive attribute … labels derived from x[0] + x[1] > 0"，模型卡则报告"accuracy: 0.97 overall; demographic parity gap: +0.03; equalized odds TPR gap: -0.01"。

1. 按 datasheet 真的生成数据（`random.gauss`，敏感属性随机），用 1000 条训练逻辑回归、500 条测试，按两个群体分别计算准确率、选择率、TPR、FPR。你得到的数字和模型卡一致吗？
2. 每组约 250 个测试样本时，demographic parity 差值的 95% 置信区间半宽约为多少？"+0.03"这个数字能说明什么？
3. "equalized odds TPR gap"这个写法有什么问题？

**Q11.**（讲义练习 4）设计一个模型卡字段，携带"某项评测结果"的密码学证明：

1. 这条证明里至少要绑定哪些内容？
2. 用标准库写一个最小演示：对规范化 JSON 的声明做 MAC，并验证"篡改数值后验证失败"。说明演示与真实 TEE 方案（如 Laminator）的差距。
3. 验证方（verifier）需要检查哪些东西？

**Q12.**（讲义练习 1）找出本节三张卡片里"只有占位、缺乏证据"的条目，至少 5 条，并为每条写出"什么样的证据能让它变强"。

---

## 四、面试高频题

**Q13.**（基础必考）Model Card、Datasheet、Data Card、System Card 分别是什么？各自面向谁、解决什么问题？

**Q14.**（原理深挖）（讲义练习 3）为什么只有 0.3% 的 Hugging Face 模型卡写了伦理考量？请提出一个**结构性**的规范改动来提高采纳率，并说明它可能带来的副作用。

**Q15.**（工程实践）你的团队每两周发布一个新模型版本。如何保证模型卡、datasheet、系统卡与实际发布的模型保持同步、而不是写一次就过期？可以用 LLM 自动生成吗？

**Q16.**（场景设计）（讲义练习 5）为一个"能读邮件和内部文档、并渲染 Markdown 的企业 Copilot"写 System Card 的大纲。哪一节对第三方审计者价值最高？

**Q17.**（追问型）供应商的模型卡写着"bias-tested, fair across groups"。你会追问哪些问题？

---

## 五、参考答案与解析

### Q1 — 答案：D

Mitchell 2019 的 9 节为 Model Details、Intended Use、Factors、Metrics、Evaluation Data、Training Data、Quantitative Analyses、Ethical Considerations、Caveats and Recommendations。A 是 Gebru datasheet 的节；B 是 System Card 的节；C 是 Data Cards 的三个缩放层级。

### Q2 — 答案：B

讲义："Oreamuno et al. 2023 audit of Hugging Face model cards found only 0.3% document ethical considerations." A 的 29% 是 Liang 等 2024 报告的"模型卡详细度与下载量提升"的上限数字，容易混淆；C、D 无依据。

### Q3 — 答案：A

讲义："Telescopic. High-level summary for non-experts. Periscopic. Middle-level overview for ML practitioners. Microscopic. Detailed feature-level documentation for auditors. Boundary-object framing: different readers extract different information from the same document."B、C、D 都是望文生义。中文译文把三个词译成"星球、远洋、微科"，请以英文为准。

### Q4 — 答案：C

讲义："Scope: end-to-end AI system including model + safety stack + deployment context"，节包括 Security capabilities、Prompt-injection protection、Data-exfiltration detection、Alignment、Incident response。A、D 是模型卡内容（Model Details、Quantitative Analyses）；B 是 datasheet 的 Collection Process。

### Q5 — 答案：B

讲义："The datasheet is the upstream documentation; the model card depends on the datasheet being accurate."skill 文件的硬性拒绝项也写明"Any card citing a dataset without a datasheet or equivalent documentation"。A、C、D 都与"上游依赖"无关；C 恰好相反，datasheet 应在数据创建时就写。

### Q6 — 答案：D

讲义："Laminator (Duddu et al. 2024). Verifiable attestations via hardware TEE / cryptographic signatures — allows the model card to carry a proof-of-claim, not just a claim."A 是 CardGen（Liu 等 2024）；B 是 Liang 等 2024；C 是 Jouneaux 等 2025。

### Q7 — 答案：A

运行代码后解析二级标题，模型卡只有 8 节：Model Details、Intended Use、Factors、Metrics、Training Data、Quantitative Analysis、Ethical Considerations、Caveats and Recommendations——**没有 Evaluation Data**。这不是小问题：Quantitative Analysis 里的 0.97、+0.03、−0.01 没有说明是在什么数据上测的，读者无法判断它们是训练集、测试集还是编出来的数字（见 Q10）。

### Q8 — 答案：C

模型卡 Factors："Sensitive attributes: gender (binary in toy), age bucket"；datasheet Composition："Features: 2-d continuous, 1 binary sensitive attribute"。数据里只有一个二元敏感属性，"age bucket"无从而来。这正是 skill 第 3 节"Datasheet alignment"要抓的问题：模型卡的结论只能和 datasheet 一样强。A、B、D 在代码中都不存在（两张卡都说 1,500 条、都是分类器，datasheet 没写许可证）。

### Q9 — 参考答案

```python
import re

CANON = {
    "model": ["Model Details", "Intended Use", "Factors", "Metrics", "Evaluation Data",
              "Training Data", "Quantitative Analysis", "Ethical Considerations",
              "Caveats and Recommendations"],
    "datasheet": ["Motivation", "Composition", "Collection Process", "Labeling",
                  "Uses", "Distribution", "Maintenance"],
    "system": ["Security Capabilities", "Alignment", "Incident Response"],
}
PLACEHOLDER = re.compile(r"placeholder|N/A|no one|goes nowhere|TBD", re.I)

def sections(md: str) -> dict[str, list[str]]:
    out, cur = {}, None
    for line in md.splitlines():
        h = re.match(r"^## (.+)$", line)
        if h:
            cur = h.group(1).strip()
            out[cur] = []
        elif cur and line.strip():
            out[cur].append(line.strip())
    return out

def audit(md: str, kind: str):
    s = sections(md)
    missing = [c for c in CANON[kind] if c not in s]
    weak = [k for k, v in s.items() if any(PLACEHOLDER.search(x) for x in v)]
    return missing, weak
```

对本节三张卡片实际运行的结果：

| 卡片 | 缺失的标准节 | 被标为"弱"的节 |
|---|---|---|
| Model Card | `Evaluation Data` | `Ethical Considerations`（含 "placeholder"） |
| Datasheet | 无 | `Motivation`（"Funded by no one"） |
| System Card | 无 | `Security Capabilities`、`Incident Response`、`Regulatory Alignment`（含 "N/A" / "goes nowhere"） |

局限：
- **假阳性**：`Motivation` 被标弱只是因为"Funded by no one"命中了关键字，这其实是一条合理的事实陈述；`Prompt-injection: N/A (non-generative)` 对分类器也是合理的。
- **假阴性**：`Quantitative Analysis` 里的 0.97、+0.03 没有数据来源、没有样本量、没有置信区间，却不会被标弱——关键字规则看不出"数字是否有证据"。
- 节名必须完全匹配（"Quantitative Analysis" vs 原文 "Quantitative Analyses"、"Labeling" vs "Preprocessing/cleaning/labeling"），真实审计需要同义词表或人工复核。
- 所以 skill 文件把"Section coverage"只作为五项检查中的第一项，还要做分组、datasheet 对齐、可验证性、可持续性检查。

### Q10 — 参考答案

1. 我们按 datasheet 生成数据（`random.seed(26)`，`x0, x1 ~ N(0,1)`，敏感属性 `g ∈ {0,1}` 随机，`y = [x0 + x1 > 0]`），用纯 Python SGD 训练逻辑回归（50 轮，lr = 0.1），测试集 500 条的实际结果：

| 组 | n | 准确率 | 选择率 | TPR | FPR |
|---|---|---|---|---|---|
| 全体 | 500 | 1.000 | 0.522 | 1.000 | 0.000 |
| g = 0 | 250 | 1.000 | 0.500 | 1.000 | 0.000 |
| g = 1 | 250 | 1.000 | 0.544 | 1.000 | 0.000 |

   demographic parity 差值（g0 − g1）= −0.044，TPR 差 = 0，FPR 差 = 0。**与模型卡不一致**：标签是一条线性规则，逻辑回归可以完美拟合，准确率应接近 1.0 而不是 0.97；标签与群体无关，equalized odds 的差值应为 0。模型卡里的数字是**手写的占位值**，代码并没有生成数据、训练或评测任何东西——datasheet 写的"regenerated on every run from fixed seed"在代码里也不存在。

2. 每组约 250 个样本、选择率约 0.5 时，差值的标准误 `√(0.25/250 + 0.25/250) ≈ 0.045`，95% 置信区间半宽约 **±0.088**。所以"+0.03"与 0 在统计上无法区分（我们实测的 −0.044 也只是抽样噪声：这里标签规则与群体完全无关，选择率差异来自两组基础正例比例的随机波动）。没有样本量和置信区间的分组差值，既不能证明"公平"，也不能证明"不公平"。

3. Equalized odds 要求**TPR 和 FPR**在各组都相等；只报告 TPR 差值，实际上检验的是较弱的 equal opportunity（第 21 节）。应同时报告 TPR 差、FPR 差，并写明符号约定（"group0 − group1"）。

### Q11 — 参考答案

1. **必须绑定的内容**：模型权重的哈希、评测数据集的哈希（或版本 ID）、评测代码的版本（commit）、指标名、分组、数值、样本量、时间戳，以及签名者身份/TEE 度量值（measurement）。缺少任何一项，攻击者都可以"拿对的签名配错的模型或数据"。
2. 最小演示（已实际运行：未篡改时 `True`，把 `value` 从 0.97 改成 0.99 后 `False`）：

```python
import hashlib, hmac, json

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

KEY = b"demo-key-inside-enclave"   # 演示用对称密钥；真实方案用 TEE 内的非对称私钥
claim = {
    "model_sha256": sha256_hex(b"<weights bytes>"),
    "eval_data_sha256": sha256_hex(b"<eval set bytes>"),
    "eval_code_commit": "abc1234",
    "metric": "accuracy", "group": "all", "value": 0.97, "n": 500,
}

def canon(c):                       # 规范化序列化：键排序、无多余空格
    return json.dumps(c, sort_keys=True, separators=(",", ":")).encode()

att = {"claim": claim, "sig": hmac.new(KEY, canon(claim), hashlib.sha256).hexdigest()}

def verify(att, key=KEY):
    expect = hmac.new(key, canon(att["claim"]), hashlib.sha256).hexdigest()
    return hmac.compare_digest(att["sig"], expect)
```

   与真实方案的差距：HMAC 是**对称**的，验证方必须拿到同一把密钥，也就能伪造签名；真实方案用 TEE 内生成、不可导出的私钥签名，验证方只持有公钥和硬件厂商的证书链。另外，演示只证明"声明没被改过"，不证明"评测确实在这些权重和数据上跑过"——后者靠 TEE 的远程证明（attestation）：证明某段**特定代码**在**可信硬件**里执行并产生了这个结果。
3. **验证方要检查**：签名有效且证书链可信；TEE 度量值对应公开、已审计的评测代码；自己手上模型文件的哈希与声明一致；评测数据哈希对应公开或托管的数据集；声明未过期、未被吊销。skill 文件："Unverified claims are labelled self-report."

### Q12 — 参考答案

| 卡片 / 条目 | 现状 | 增强所需证据 |
|---|---|---|
| Model Card / Quantitative Analysis | 三个数字，无数据来源、无样本量、无置信区间 | 指明评测集（补上 Evaluation Data 节）；每组 n、点估计与置信区间；可复现脚本链接 |
| Model Card / Ethical Considerations | "Bias metrics are placeholder" | 列出已知风险（gender 仅为二元的局限、合成数据不代表真实人群）、受影响群体、缓解措施 |
| Model Card / Factors | 列了 age bucket，数据里没有 | 与 datasheet 对齐；说明为何选择这些因素、哪些因素没评测 |
| Datasheet / Maintenance | "regenerated on every run from fixed seed"，代码中并无生成器 | 提供生成脚本、种子、数据哈希；维护者与更新策略 |
| Datasheet / Labeling | "no annotation error" | 对程序化标签这句成立，但应说明标签规则与真实任务的差距 |
| System Card / Security Capabilities | "Data-exfiltration detection: basic egress rate limit" | 速率限制不是外泄检测；应写明检测什么（如 DLP 规则）、测试方法与结果 |
| System Card / Incident Response | "escalation goes nowhere" | 联系人、响应时限、事故分级、历史事故记录 |
| 全部 | 无可持续性、无可验证证明 | skill 第 4、5 节：训练能耗/碳排放；关键评测结果附签名证明（Q11） |

### Q13 — 参考回答要点

- **Model Card**（Mitchell 2019）：面向模型使用者和评估者；说明模型做什么、适用/不适用场景、按因素分组的性能、伦理考量与局限。
- **Datasheet**（Gebru，arXiv 2018 / CACM 2021）：面向数据使用者；以问答形式记录数据集的动机、组成、收集、标注、用途、分发、维护——讲义："upstream documentation"。
- **Data Card**（Pushkarna，Google 2022）：同样记录数据，但强调分层（telescopic / periscopic / microscopic）与模块化，让非专家、从业者、审计者都能取到需要的层级。
- **System Card**：面向部署方、审计者、监管者；记录整个系统——安全栈、prompt injection 与外泄防护、对齐、事故响应、监管对齐。同一个模型在不同系统中风险完全不同，所以需要这一层。
- 加分点：说明这是"范围逐步扩大"的演进（模型 → 数据 → 系统），以及 GPAI Code of Practice 把模型文档变成合规工件（第 24 节）。

### Q14 — 参考回答要点

- **原因**：伦理考量没有标准答案、难以量化；写了可能带来法律或声誉风险；模板里它是自由文本，最容易被跳过；没有平台层面的强制或激励；作者往往没有相关专业背景。
- **结构性改动示例**：
  - 把自由文本改成**结构化问卷**（"模型是否涉及人群决策？哪些群体可能受影响？做过哪些分组评测？"），每题必答，允许回答"未评估"——"未评估"本身就是有用信息；
  - 平台把该字段设为**发布必填**，或在搜索结果中对缺失卡片降权；
  - 与 Quantitative Analyses 联动：列出 Factors 就必须给出对应分组指标。
- **副作用**：可能出现"勾选式合规"——大量模板化、无信息量的回答；必填门槛可能让小作者放弃发布；结构化问卷难以覆盖所有领域。缓解：抽样人工审核、对高下载量模型提高要求。
- 加分点：讲义提到 Liang 等 2024 发现详细模型卡与最高 29% 的下载量提升相关——采纳压力正从合规转向市场。

### Q15 — 参考回答要点

- **docs-as-code**：卡片源文件与模型代码放在同一仓库，用模板 + 数据填充（评测结果由评测流水线写入 JSON，再渲染进卡片），而不是手工复制数字。
- **CI 门禁**：发布流水线里跑 Q9 那样的审计脚本——缺节、占位内容、模型哈希与卡片不一致时阻止发布；skill 的硬性拒绝项（无伦理考量、无 datasheet、"bias-tested"无分组指标）可以直接变成检查规则。
- **版本绑定**：卡片里写模型版本与权重哈希、评测数据版本；关键结果附签名证明（Q11）。
- **变更记录**：每次发布记录与上版的差异（性能、已知问题、安全栈变化）。
- **LLM 自动生成**：可以用 CardGen 类方法生成**草稿**（讲义：它在标准字段上报告了比很多人工卡片更高的客观性），但 skill 文件要求"refuse unless a CardGen-style system with human review is used"——必须人工复核，尤其是伦理考量和局限，因为 LLM 可能编造没有评测过的数字。
- 加分点：对 System Card 设定定期复审（安全栈、事故响应联系人会变化）。

### Q16 — 参考回答要点

- **大纲**：
  1. 部署范围与用户（企业员工、可访问的数据源：邮箱、文档库）；
  2. 组件清单（基础模型及其模型卡链接、检索系统、工具、渲染器）；
  3. Security Capabilities：retrieval / scope / output 三边界控制（第 25 节 EchoLeak）、Markdown 渲染的域名白名单、DLP；
  4. Prompt-injection protection：评测方法、攻击语料、攻击成功率与版本；
  5. Data-exfiltration detection：检测规则、告警流程、已知绕过；
  6. Alignment：拒答策略、敏感操作的人工确认；
  7. Incident Response：联系人、响应时限、漏洞披露渠道、历史 CVE；
  8. Regulatory Alignment：适用法域与义务（第 24 节）；
  9. 可持续性与可验证证明。
- **对第三方审计价值最高的一节**：通常是 **Security Capabilities + Prompt-injection 评测结果**——它直接对应这类系统最主要、已被生产 CVE 证实的风险（EchoLeak），并且可以被独立复测；附上可复现的攻击语料与结果，审计者能验证而不只是阅读声明。
- 常见误区：只写基础模型的能力，不写部署层的防护——那是 Model Card，不是 System Card。

### Q17 — 参考回答要点

- **在哪些群体上测的**：Factors 是什么？是否包括与本业务相关的群体？交叉群体？
- **用什么指标**：demographic parity、equalized odds（TPR 与 FPR 都要）、校准？不同指标可能互相冲突（第 21 节）。
- **数据与样本量**：评测数据是什么、每组多少样本、置信区间多宽？（Q10：每组 250 个样本时 ±0.09 的区间）
- **阈值与结论**：差值多大算"公平"？谁定的？
- **复现与验证**：能否提供评测脚本与数据哈希？是否有第三方或密码学证明？否则按 skill 规则标为 self-report。
- **与 datasheet 的一致性**：训练数据是否包含这些属性？是否存在代理变量？
- **适用范围**：在我的部署场景（不同人群分布、不同阈值）下结论是否仍成立？
- skill 硬性拒绝项："Any card claiming 'bias-tested' without disaggregated metric reporting."

---

## 六、关联知识点

### 前置知识
- [阶段 18 · 20 LLMs 中的偏见与表征性伤害](../../20-bias-representational-harm/docs/zh.md)：模型卡 Factors 与伦理考量要回答的伤害类型（讲义练习 2 指向这里）。
- [阶段 18 · 21 公平性标准：群体、个体与反事实](../../21-fairness-criteria-group-individual-counterfactual/docs/zh.md)：demographic parity、equalized odds 等分组指标的定义。
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：实验室安全政策对文档的要求（讲义先修）。
- [阶段 18 · 24 监管框架：欧盟、美国、英国、韩国](../../24-regulatory-frameworks-eu-us-uk-korea/docs/zh.md)：GPAI Code of Practice 的 Transparency 章（讲义先修）。
- [阶段 02 · 09 模型 Evaluation](../../../02-ml-fundamentals/09-model-evaluation/docs/zh.md)：评测集划分与指标置信区间。

### 本节被哪些后续内容用到
- [阶段 18 · 27 Data Provenance 与训练数据治理](../../27-data-provenance-training-governance/docs/zh.md)：datasheet 的上游——数据从哪里来、许可证是什么。
- [阶段 18 · 28 Alignment 研究生态：MATS、Redwood、Apollo、METR](../../28-alignment-research-ecosystem/docs/zh.md)：卡片中引用的外部评测来自这些机构。
- [阶段 18 · 25 EchoLeak 与 AI 领域 CVE 的出现](../../25-echoleak-cves-for-ai/docs/zh.md)：System Card 中 prompt injection 与外泄防护要应对的真实漏洞。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../../17-infrastructure-and-production/26-compliance-frameworks/docs/zh.md)：把卡片纳入合规证据链。
- [阶段 19 · 07 端到端 Fine-Tuning 流程——从数据、SFT、DPO 到模型服务](../../../19-capstone-projects/07-end-to-end-fine-tuning-pipeline/docs/zh.md)：在完整流水线中自动产出模型卡。

### 延伸关键词
`Model Cards for Model Reporting` · `Datasheets for Datasets` · `Data Cards Playbook` · `boundary object` · `disaggregated evaluation` · `equal opportunity vs equalized odds` · `self-report vs attestation` · `TEE remote attestation` · `CardGen` · `Laminator` · `sustainability reporting` · `docs-as-code` · `GPAI Model Documentation`
