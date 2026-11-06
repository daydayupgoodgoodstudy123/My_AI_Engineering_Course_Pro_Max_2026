<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="compliance--soc-2-hipaa-gdpr-pci-dss-eu-ai-act-iso-42001"></a>

# 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001

> 多框架覆盖是2026年企业交易的表利。 **欧盟大赦国际法**2024年8月1日生效。大多数高风险要求都执行2026年8月2日的罚款。 高达15万欧元或全球高风险系统义务年营业额3%的罚款(第99(4)条);最高为3 500万欧元或7%的禁止的AI做法(第99(3)条)。如果为欧盟用户服务,则适用于全球。 **科罗拉多大赦国际法**2026年6月30日(从2026年2月被SB25B-004推迟)——高风险系统影响评估,有权对大赦国际的决定提出上诉。 **SOC 2 第二类**: 实际的B2B AI要求(Fintech的第二类,而非第一类)。 **GDPR**最高有记录的人工智能罚款是30.5万欧元,对Clearview AI(荷兰政治部,2024年9月);意大利颁发的1 500万欧元,对 OpenAI 2024年12月(后来于2026年3月上诉被推翻)。 inference 是可辩护的标准;处理后清理是不够的。 **HIPAA**医疗受限——没有BAA,不能将PHI送往外部AI服务。 **PCI-DSS**:AI-互动层覆盖要求配置+合同协议,而不是自动。 **ISO 2001**:新出现的国际空运协会治理标准,与ISO 27001一道不断增长的采购要求。 OpenAI 维持SOC 2型2,ISO/IEC 27001:2022,ISO/IEC 27701:2019,GDPR/CCPA/HIPAA(BAA)/FERPA,PCI-DSS ChatGPT 跨框架绘图可减少审计疲劳:ISO 2701 A.5.15-5.18的出入控制图,GDPR 第32条,HIPAA §164.312(a)。

**类型:** 学习
**语言:** (Python 任择性——遵守是政策+进程,而不是代码)
**先修要求:** 阶段17 25(安全),阶段17 13(Observability)
**时间：** ~60 分钟

<a id="learning-objectives"></a>

## 学习目标

- 列出与 LLM 产品,并匹配 客户部分。
- 遵守欧盟《大赦国际法》的执行时间表(2024年8月生效;2026年8月执行高风险)和两级罚款上限(高风险债务15万欧元/3%,违禁做法3500万欧元/7%)。
- 解释为什么后处理 PII 清理不足以满足GDPR 并命名实时 inference- 做一个简单的编辑
- 描述跨框架控制绘图(例如,ISO 2701 A.5.15-5.18+GDPR 第32条+HIPAA§164.312(a))。

<a id="the-problem"></a>

## 问题

企业客户要求购买2类SOC 2, GNSR, HIPAA BAA, ISO 27001和“EU AI Act Professional decordmentments”。你的团队有2类SOC I。你从2类6个月后还没有开始使用 GDP 第30条的记录。

多框架覆盖范围不是 LLM 问题——这是一个企业-SaaS的问题, LLM2026年采购小组需要每个框架一行、每个控制一列的矩阵,而不是一个PDF。

<a id="the-concept"></a>

## 概念

<a id="the-seven-frameworks"></a>

### 七个框架

| 框架 | Scope | LLM- 具体要求 |
|-----------|-------|--------------------------|
| SOC 2 第二类 | B2B SaaS 基线 | 6-12个月中审计的流程控制 |
| HIPAA | 美国保健 | 需要BAA;PHI不能在没有签署协议的情况下离开基础设施 |
| GDPR | 欧盟用户 | 实时PII编辑;数据主题权利;第30条记录 |
| PCI-DSS | 支付数据 | 配置+AI触摸付款合同 |
| 欧盟大赦国际法 | 服务于欧盟用户 | 风险等级分类;高风险系统:合规性评估、文件、记录 |
| 科罗拉多大赦国际法 | 服务社社长 | 影响评估;上诉权 |
| ISO 2001 | AI 治理 | 新兴;配有ISO 27001 |

<a id="eu-ai-act-timeline"></a>

### 欧盟大赦国际法案时间表

- 2024年8月1日,生效
- 2025年2月2日:实施禁止的大赦国际做法。
- 2026年8月2日:执行高风险系统(合规性评估、文件、记录)。
- 2027年8月:根据统一立法产品中高风险系统。

风险等级:不可接受(禁止)、高风险(符合标准+记录)、有限风险(透明)、最小风险(无限制)。 LLM 萨氏病风险有限;就业、信贷、教育、执法、移徙和基本服务风险高。

罚款(第99条):违反高风险系统义务的罚金最高为15万欧元或3%(第99(4)条);被禁止的《反垄断法》做法最高为35万欧元或7%(第99(3)条);适用较高者。

<a id="gdpr--real-time-redaction-is-the-standard"></a>

### 国内生产总值——实时编辑是标准

处理后清理(在 LLM 模型已经看到数据,这不是一种可辩护的姿态。 inference- 层编辑是2026年的标准:

- 实体在 LLM call.
- Consistent tokenization (Mesh方法)保留语义。
- 只存储已编辑的 prompts + 同意选择原产。

最近的执行情况:30.5万欧元对Clearview AI(德国政治部,2024年9月)是迄今为止记录的最大有记录的大赦国际专用的国内总产值罚款;15万欧元对1 500万欧元 OpenAI (意大利的Garante,2024年12月)是最大的 LLM具体罚款,尽管2026年3月上诉时被推翻,裁决仍在进一步审查中。

<a id="hipaa--baa-is-not-optional"></a>

### HIPAA - BAA不是可选的

没有签定的商业联系协议,你不能将PHI送往外部的AI服务。 LLM 平台( 贝德罗克, 亚苏尔) OpenAI提供BAAs(Vertex) OpenAI direct API 提供BAA。 Anthropic direct API 提供BAA。 在发送 PHI之前确认 。

<a id="soc-2-type-ii"></a>

### SOC 2 第二类

第一类:设计和记录控制。
第二类:控制有效运行6-12个月。

2026年B2B采购默认为二类。 类型I是起始器; 类型II是大门 。

共同审计驱动因素:访问日志(谁看到什么)、改革管理(如何部署)、风险评估(每季度), incident response (tested?). Audit log · 25 直接可重复使用。

<a id="cross-framework-mapping"></a>

### 跨框架绘图

一项出入控制政策满足多种框架控制:

| Control | Frameworks |
|---------|-----------|
| 访问记录 | ISO 2701 A.5.15-5.18,《国际化学品安全条例》第32条,《国际化学品安全条例》第164.312(a)节 |
| 改革管理 | ISO 27001 A.8.32, PCI DSS Req.6, HIPAA 违反通知范围 |
| 正在传输加密 | ISO 2701 A.8.24, 国内总产值条例第32条,《国际船舶和公司注册法》第164.312(e)节 |
| 秘密管理 | ISO 27001 A.8.19,PCI DSS Req.8, SOC 2 CC6.1 |

合规工具( lata, Vanta, Securef) 自动连接此映射。 值得以规模计算成本 。

<a id="iso-42001--emerging"></a>

### ISO 2001 - 新兴

2023年末公布的《国际行业标准27001》的《国际行业管理框架》,包括风险管理、数据质量、透明度、人的监督等,采购要求不断增加。

<a id="openais-reference-profile"></a>

### OpenAI引用配置

OpenAI 维持SOC 2型2,ISO/IEC 27001:2022,ISO/IEC 27701:2019,GDPR/CCPA/HIPAA(BAA)/FERPA,PCI-DSS ChatGPT 大约是2026年的企业表的基本要求

<a id="numbers-you-should-remember"></a>

### 数字您应该记住

- 欧盟大赦国际法规定的罚款:最高为1,500万欧元/3%(高风险义务,第99(4)条);最高为3,500万欧元/7%(违禁行为,第99(3)条)。
- 欧盟大赦国际《高风险执法法》:2026年8月2日。
- 记录最多的大赦国际专用国内生产总值罚款:30.5M欧元,Clearview AI(荷兰政治部,2024年9月)。
- Largest LLM- 国内生产总值罚款:1 500万欧元, OpenAI (意大利的Garante,2024年12月;上诉被推翻,2026年3月)。
- SOC 2 第二类窗口:6-12个月操作控制。
- 《科罗拉多独立法》生效日期:2026年6月30日(从2026年2月起被SB25B-004推迟)。

```figure
i4-control-matrix
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 是一个合规映射电子表格 Python - 进行管制,列出符合其要求的框架。

<a id="ship-it"></a>

## 交付成果

课程产生 `outputs/skill-compliance-matrix.md`. 鉴于客户部分和地域,具体说明了所需的框架和控制。

<a id="exercises"></a>

## 练习

1. 企业客户需要2类SOC 2,HIPAA BAA,欧盟AI Act声明。 最起码可行的合规态势是什么?
2. 分三个假设 LLM 风险等级。
3. 你无意间把PHI送到一个没有BAA的供应商那里 incident response.
4. 质疑对于一个中市AI销售商来说,ISO 2001是否“2026年的必要”。
5. 映射您的 LLM audit log 字段(第17阶段 · 25)至至少三个框架控制。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| SOC 2 第二类 | "审计控制" | 6-12个月以上运作的控制,经独立证明 |
| 哈帕阿巴亚 | "医疗合同" | 商业联系协定;对初级保健的要求 |
| GDPR | "欧盟隐私" | PII实时编辑为2026年可辩驳标准 |
| 欧盟大赦国际法 | "欧盟AI规则" | 2026年8月高风险执法;1 500万欧元/3%(高风险债务)-35万欧元/7%(违禁做法) |
| 科罗拉多大赦国际法 | 美国大赦国际州法 | 2026年6月30日生效(被SB25B-004推迟);影响评估 |
| ISO 2001 | “大赦国际治理” | 新的独立交易风险+透明度框架 |
| ISO 27001 | "保安系统" | 信息安全管理系统基线 |
| 合规性评估 | "欧盟的AI 软件包" | 高风险要求:医生、测试、记录 |
| 跨框架绘图 | "一个控制,许多框架" | 单一政策满足多个框架控制 |

<a id="further-reading"></a>

## 进一步阅读

- [OpenAI 安全和隐私](https://openai.com/security-and-privacy/) 参考遵守情况简介。
- [警卫队 LLM 遵守2026年:ISO 2001, 欧盟AI法, SOC 2, GDPR](https://guardion.ai/blog/llm-compliance-guide-iso-42001-eu-ai-act-soc2-gdpr-2026)
- [Dsalta - SOC 2 类型 2 审计指南 2026: 10 AI 控制](https://www.dsalta.com/resources/ai-compliance/soc-2-type-2-audit-guide-2026-10-ai-powered-controls-every-saas-team-needs)
- [欧盟大赦国际](https://eur-lex.europa.eu/eli/reg/2024/1689/oj) - 原始来源。
- [科罗拉多大赦国际法](https://leg.colorado.gov/bills/sb24-205) - 原始来源。
- [ISO/IEC 2001:2023](https://www.iso.org/standard/81230.html) AI管理系统标准。
