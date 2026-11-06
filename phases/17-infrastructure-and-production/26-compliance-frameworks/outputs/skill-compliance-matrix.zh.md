---
name: compliance-matrix
description: Produce the required-framework matrix for an LLM SaaS given customer geography, segment, and contract scope. Map controls across SOC 2, HIPAA, GDPR, PCI-DSS, EU AI Act, Colorado AI Act, ISO 42001.
version: 1.0.0
phase: 17
lesson: 26
tags: [compliance, soc2, hipaa, gdpr, pci-dss, eu-ai-act, colorado-ai-act, iso-42001, iso-27001]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于客户的地理分布(美国/欧盟/全球,或美国特定州)、部门(萨斯/医疗保健/芬兰技术合作)、合同范围(企业与标准管理)以及目前的合规状态,产生了所需的框架矩阵。

显示 :

1. 所需框架:列出每个必须依据理由实现的框架(地理、部分、客户概况)。
2. 时间表。 对于每个框架,请说明当前状态(审计中无/类型I/类型II)。
3. 跨框架控制映射。 对于每个所需的框架, 指定符合多个控件( 访问日志、 加密、 密码) 。 audit log,改变 mgmt)。
4. 欧盟AI法案态势:对产品的风险等级进行分类(不可接受 / 高 / 有限 / 最低 ) 。 如果风险高,则要求在2026年8月2日执行日之前进行合规性评估。
5. PII/PHI处理。 确认实时 inference- 重复(第17阶段 · 25)——后处理是无法证明的。
6. 审计工具。 Drata/ Vanta/ 跨框架自动化安全框架。 值得多框架成本计算 。

艰难的拒绝 :
- 要求SOC 2 类型I在企业采购中符合SOC 2。拒绝-类型II是大门。
- 将PHI送到没有BAA的供应商那里。
- 后处理PII的清洗是GDPR的姿势。 拒绝要求实时。

拒绝规则 :
- 如果该产品为欧盟用户服务,但没有GDPR第30条的记录,则在记录确定之前拒绝向欧盟客户运送。
- 如果该产品在信贷/就业/住房/教育/基本服务方面为科罗拉多居民服务,则要求在2026年6月30日之前完成影响评估(根据经SB25B-004修订的《科罗拉多岛AI法案》生效日期),然后才能发射。
- 如果该产品在欧盟《AI法》下具有高风险,而且该小组没有符合性评估计划,则拒绝承诺在2026年8月在没有指定执行伙伴的情况下做好准备。

产出:一页矩阵,包含所需的框架、当前状况、差距、时间表、跨框架控制、欧盟AI Act 级别、 PII 态势、工具化。 以12个月的路线图结束:框架逐个季度里程碑。
