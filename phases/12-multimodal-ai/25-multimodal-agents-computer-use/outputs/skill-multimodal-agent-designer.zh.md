---
name: multimodal-agent-designer
description: Design a multimodal agent (computer-use, GUI grounding, web or mobile) with action schema, memory strategy, and benchmark evaluation plan.
version: 1.0.0
phase: 12
lesson: 25
tags: [multimodal-agents, computer-use, gui-grounding, visualwebarena, agentvista]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


以计算机使用产品规格(域、动作集、 evaluation 目标),设计 agent loop记忆策略 grounding 模式,以及 evaluation.

显示 :

1. 行动计划 JSON 定义支持的动作(单击、键入、滚动、拖动、选择、导航、完成,加上任何视觉工具)。
2. 输入模式。 仅屏幕截图、 无障碍树或混合。 浏览器的混合默认值; 仅桌面抓图, 没有访问钩 。
3. 模型选取。 Quen2.5- VL- 72B( 开关) , Claude 计算机使用(闭机、强型)4.7 GPT-5(封闭,更强),以基准和成本说明理由。
4. 记忆战略。 每5个步骤的简链 + 最后2个截图即时直播; 仅对非常长的工作流程进行日志 。
5. 错误回收。 动作失败时, 通过元素重新定位_语义暗示; 重试最多2次; 返回到重新规划 。
6. Evaluation 计划。 grounding,“视觉网”为端到端,“AgentVista”为硬性多步工作流程。预期得分等级。

艰难的拒绝 :
- 使用自由文本动作输出。 总是 JSON- 结构上有明确的计划
- 要求开口7B型号与Vista特工的边界匹配 差距是10 -20点
- 依靠协调的内存在截图上。 坐标在抓取之间漂移 。

拒绝规则 :
- 如果产品需要 > 50 步流程, 拒绝单agent loop 并推荐等级规划器+执行器分割。
- 如果产品在没有无障碍钩的规范平台上工作,则只使用标语截图的可靠性限制,并提出严格的核查。
- 如果任务类别是在经过培训的外部分发(专门的工业软件),则拒绝现成的销售并提出 fine-tuning 显示在域图中。

产出:一页 agent 设计包含动作图、输入模式、模型选取、内存、恢复, evaluation以arXiv 2401.10935(见Click)、2401.13649(VitualWebArena)、2602.23166(AgencyVista)结束。
