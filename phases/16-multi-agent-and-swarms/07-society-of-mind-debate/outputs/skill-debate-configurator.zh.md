---
name: debate-configurator
description: Configure a multi-agent debate for a given task, estimating quality gain and token cost before running.
version: 1.0.0
phase: 16
lesson: 07
tags: [multi-agent, debate, society-of-mind, consensus]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


问题或任务,请制作一个辩论配置,准备在任何 agent 框架(LangGraph, AutoGen, 自定义环) 。

显示 :

1. **任务匹配检查。** 辩论有助于推理、事实性和分解;它无助于已经具有决定性(理性、代码汇编)或纯粹具有遗传性(创作)的任务。
2. **Agent count.** 3、4或5. 默认3; 只有当成本不敏感和任务需要更多不同的观点时,才算4+。
3. **数数** 2或3. 默认3;很少。
4. **Heterogeneity.** 同一基本模式(简单、便宜、关联性强的错误)或混合家庭(Llama + Claude + GPT; 装饰; 更昂贵,需要路由层)
5. **角色分配** 对称( 全部 agents 具有相同作用)与一对一(一) agent 反竞争是针对相残级联的廉价保险。
6. **集合法。** 多数票(分辨答案)、加权平均数(数字),或 LLM- 法官综合(无限期)。
7. **费用估计数。** N agents ×R 子弹x中位数 tokens 以当前供应商定价的美元估计数表示。

艰难的拒绝 :

- 超过 5 个的配置 agents 或超过三轮,但无具体费用说明。
- 仅对称辩论,讨论已知的恋情风险。
- 使用辩论来进行具有确定性核查(复杂、测试、精确数学)的任务——由核查者来操作。

拒绝规则 :

- 如果任务简单, 简单的事实查询, 拒绝并推荐检索 - 增强单 -agent.
- 如果任务具有特质(写一首诗),则拒绝——辩论会将产出拖向平均值。
- 如果用户没有设置 token5 -15x 单人费用agent.

输出: 一页配置摘要。 从任务匹配检查开始, 结束总成本估算 。
