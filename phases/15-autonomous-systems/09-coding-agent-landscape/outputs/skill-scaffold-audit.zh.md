---
name: coding-scaffold-audit
description: Audit a proposed coding-agent scaffold (retrieval, verifier loop, sandbox, benchmark fit) before adopting it for production code changes.
version: 1.0.0
phase: 15
lesson: 9
tags: [coding-agent, scaffolding, swe-bench, codeact, openhands]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


鉴于一个拟议的编码agent 脚架(SWE-)agent开关手,艾达,克莱恩,德文 Claude 代码,或内部结构, 分到四个轴和旗帜上, 基准数字会超过生产质量。

显示 :

1. **Retrieval.** 描述脚手架如何选择哪个文件 agent 读取之前演戏。 embedding 搜索、 明确文件列表,或 agent-driven `grep` 检索的质量是沉默的可靠性因素。
2. **验证环。** 脚架有没有做测试,读一下书架 trace,然后将失败反馈到下一回合。如果没有验证环,则标记为缺失——这通常是SWE-bench类任务的10+点绝对三角洲。
3. **Sandbox 和爆炸半径。** 动作执行到哪里? 本地文件系统, 短容器, 管理 VM 。 对于代码 Act- scarffold, 请确认 sandbox 固定的(无反射,无主机挂载,限时)。 JSON 工具呼叫脚架,确认工具验证器拒绝所有意外的副作用。
4. **基准合适。** 报告的数值( 例如, “ 运行于 SWE- bench 验证的 ” ) 实际覆盖了哪些分布? 计算基准数中由 1-2 行任务组成的部分; 比较所报告得分与同一模型的 SWE- bench Pro ( 10+ 行任务) 。 标题号由简单尾巴驱动的脚架不是生产信号。

艰难的拒绝 :
- 任何没有验证器环的脚架 用于过轻复杂的任务
- 代码法脚架没有 sandbox 孤立(无) Docker,没有无根容器,没有VM)指向真正的仓库。
- 基准索赔不披露分配情况(容易分数,准等值分)。
- 工具呼叫脚架, 单个工具可以触摸任意路径, 没有验证器( 例如, 原始) `shell_exec` 工具暴露于模型中)。

拒绝规则 :
- 如果用户无法在具有代表性的内部分布上生成脚手架的测试适中过速率,则拒绝并首先要求进行小样本测量。 公共基准预测等级顺序,而不是绝对质量。
- 如果提议的脚手架在不进行模拟运行的情况下会与生产仓库对峙,则拒绝并需要先进行中转。 Coding agents 重写文件; coding agents 错误的检索重写错误的文件 。
- 如果用户计划单独使用基准分数(没有自己的评估)来作出 " 不可放弃 " 决定,则拒绝并要求内部评估数据。

输出格式 :

返回一个记号 :
- **检索分数** (0-5 带有说明的机制)
- **验证循环分数** (0-5 带有反馈格式)
- **Sandbox score** (0-5个带隔离装置)
- **基准适配分** (0-5带有内部分布三角洲)
- **部署建议** (仅生产/中产/研究)
- **一行风险摘要** (最有可能发生第一次生产失败)
