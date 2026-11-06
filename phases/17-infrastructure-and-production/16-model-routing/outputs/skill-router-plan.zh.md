---
name: router-plan
description: Design an LLM model-routing plan — pick pattern (pre-route, cascade, ensemble), signals (task, length, embedding, confidence), and online quality gates.
version: 1.0.0
phase: 17
lesson: 16
tags: [routing, cascade, model-cascade, routellm, notdiamond, cost-reduction]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于工作量的组合(任务分类抽样),质量底线、延缓度和目前的月支出,产生了一个路线规划。

显示 :

1. 模式: 路径前( 最快捷、 取决于分类者)、 级联( 最佳质量底线) 或组合( 仅标本 A/ B) 。 以质量容忍度+ 延迟度预算为根据。
2. 信号。从任务分类中提取, prompt length, embedding 国家(通常为2-3)和组成规则相结合。
3. 便宜/ 边框。 列出具体模型。 例如 : Claude 海库3.5+ GPT-5. 以成本曲线+能力说明理由。
4. 预期节省。 计算混合成本, 按建议拆分; 状态: 预计每月美元对当前美元 。
5. 在线质量门。 指定现场交通法官: 每条路线由边疆法官评估5%的样本; 如果 {% 质量 > 2% 的警告。 跟踪升级率; 如果每月攀升 > 10 点, 提醒 。
6. Rollout。阴影(路由但忽略;离线比较),10%的金丝雀,按用户-合口键,在通过门上延伸。

艰难的拒绝 :
- 拒绝 — 漂移是1号的失败。
- 仅使用任务分类作为信号。 拒绝 - 忽略任务内的困难 。
- 将符合边境条件的任务(代码、数学、多步)变成便宜而没有级联的后退。 拒绝 — — 质量底线会破裂。

拒绝规则 :
- 如果质量容忍度被说成是"零回归" 拒绝前期,建议升级率高的级联
- 如果便宜的模型不是...Anthropic/non-OpenAI/ 具有拒绝模式(例如,未经审查的型号) agent 工具使用),拒绝对,它会断开 tool calls silently.
- 如果路线是向另一家廉价供应商(跨供应商级联),则需要AI网关层(17 · 19阶段)统一 APIs.

产出:一页计划命名模式、信号、模型配对、预期节余、在线门户、 rollout 以单一指标结束:滚动7天的升幅;变化时的漂移触发率 > 10个百分点。
