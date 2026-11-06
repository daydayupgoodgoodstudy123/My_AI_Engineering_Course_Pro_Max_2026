---
name: tool-registry
description: Build a production tool catalog and registry with JSON Schema validation, parallel dispatch, and observability.
version: 1.0.0
phase: 14
lesson: 06
tags: [function-calling, tools, schema, validation, bfcl, parallel-tools]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给任务域制作一个工具目录, agent 可在 BFCL V4 轴上方可靠使用(agentic,多转,活,不活, hallucination).

显示 :

1. 工具定义。 对于每个工具 : `name` (snake_case), `description` (告诉模型何时使用,何时不使用) JSON 输入有打字属性、所需字段、酌情括号、数字最小/最大、每个工具超时、每个工具的方块 sandbox 政策(fs表面、网络、内存上限)。
2. 描述质量检查。 运行每个描述 。 “ 这是否告诉模型何时选择此工具 ” ? 如果两个工具有重叠描述, 拒绝和重写 。
3. 平行发送计划。 对于每一项现实的任务, 请确定 tool calls 独立(可平行),且必须相继。
4. 校验政策。 测试、 强制规则( 例如“ 接受字符串 ” , 拒绝浮动字符串 ” ) 、 要求的实地强制 。 每个失败都返回结构化的观察字符串, 永远不要转到循环中 。
5. Observability。每个工具都发出一个开放的遥测 GenAI `tool_call` 带有属性的横线 `gen_ai.tool.name`, `gen_ai.tool.call.id`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result` (参考,而不是内联,当内容政策需要时)。

艰难的拒绝 :

- 常规 shell/ command- exec 工具。 拒绝并打破特定的动词 (`git_status`, `fs_read`, `npm_test`).
- 缺少的圈套 parameter 具有一套封闭的值。 环境验证是最便宜的捕捉漂移的方法 。
- 两种不同工具的描述相同。 模型无法在它们之间做出可靠的选择 。
- `description` 中仅指定工具名称(“添加两个数字 ” )。 包括何时选择它替代 。
- 没有超时,每个 tool call 一定有天花板的 绝对有

拒绝规则 :

- 如果工具列表超过 30 个工具, 单 agent,拒绝和建议 subagent delegation (第17条)。
- 如果任何工具在没有确认门的情况下进行破坏行动,则拒绝并指向09课(许可、沙箱)。
- 如果任务为计算机使用(单击、键入、截图),则拒绝并指向21课——这是一个带有视觉动作的单独工具形状。

产出:a JSON 工具目录已准备粘贴 Anthropic / OpenAI / Gemini SDK 电话、调度图、审定政策文件和登记册应经过的BFCL型小型电子交易。

最后是“下一个读什么”的提示: 课程 09 (沙发), 课程 23 (OTel GenAI 跨越) , 或课程 30 (Eval-hind) 。
