---
name: managed-platform-picker
description: Pick a managed LLM platform (Bedrock, Azure OpenAI, Vertex AI) and a second for redundancy, given workload, SLA, and compliance requirements — then produce a FinOps instrumentation plan.
version: 1.0.0
phase: 17
lesson: 01
tags: [bedrock, azure-openai, vertex-ai, ptu, finops, managed-platforms]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


工作量概况(所需模型,每月) tokens与P50/P99的TTFT SLA有关的合规限制、现有云足迹,提出了平台建议。

显示 :

1. 主平台。 命名平台、 其覆盖的具体模式, 以及是否适合使用点需求或提供输送单位 / 提供输送单位 。 点击平衡数学( 持续使用比例约为 40%- 60% ) 。
2. 第二平台。 命名两个提供者- 最小的后退。 将配对合理化—— 冗余必须包含模式重叠( )Claude 在贝德洛克+ GPT 月亮上 OpenAI 区域重叠。
3. FinOps 仪器。 指定第一天启用的功能: Bedrock 应用程序 Inference 配置、 Azure 范围 + PTU 保留为成本对象, Vertex 项目- 每组 + BigQuery Billing 导出。 请列出属性大小—— 用户、 每个任务、 每租户。
4. 对照目标TTFT P99与公布的基准(阿苏尔) OpenAI 单价50毫秒;按需贝德洛克=75毫秒P50。如果SLA比按需交付的更紧,则需要PTU。
5. 合规性检查:核查BAA、SOC 2 类型二、HIPAA、欧盟数据居留权(视需要),注意这三种符合基线但保留政策和滥用监测选择的退出情况各不相同。
6. 迁移路径: 列出团队本周可以采取的可逆步骤( 例如, 通过 AI 网关抽取提供者、 仪器归属头条) 和一项长期步骤(  PTU 承诺; 跨区域失败 ) 。

艰难的拒绝 :
- 推荐一个没有名副其实的平台。 拒绝并坚持两个提供者的最低要求 。
- 选择 PTU, 但没有使用估计。 拒绝并要求持续使用数据 。
- 忽略 Bedrock 应用程序 Inference 属性被列作要求时的特征——它们是最干净的本地表面。

拒绝规则 :
- 如果工作量需要 Claude, Gemini, 和 GPT 全部为 P0, 命名三平台的真象( 贝德罗克 + 维特克斯 + Azure) OpenAI 而不是假装一个平台可以为所有三个服务。
- 如果苏丹解放军是TTFT P99 < 100 ms,预期预算不能支持PTU,则拒绝向苏丹解放军许诺——解释按需差异上限。
- 顾客若要求使用最便宜的供应商,token + 专用能力+ 归属管理费+锁定成本)

产出:一页决定,主平台、第二平台、PTU对点、仪器清单、SLA/合规核查和两个迁移步骤。 最后是单一指标,即持续使用、PTU废物或归属覆盖。
