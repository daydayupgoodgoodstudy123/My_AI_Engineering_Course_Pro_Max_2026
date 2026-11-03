---
name: provider-portability-audit
description: Audit a function-calling integration against one provider for what breaks when ported to the other two.
version: 1.0.0
phase: 13
lesson: 02
tags: [function-calling, openai, anthropic, gemini, portability]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


在一个供应商上进行功能调用整合(OpenAI, Anthropic, 或 Gemini),生成一个可移植性审计,列出每个字段的重命名、行为差异和当同一逻辑被运到另外两个供应商时出现的硬限碰撞。

显示 :

1. 声明 diff. 对于整合中的每个工具,请显示其他两个提供者各自需要的信封/字段重命名/系统翻译。 JSON 目标提供者不支持的Schema构建(Gemini:开放API 3.0子集; OpenAI 严格:无 `$ref`,没有模糊 `oneOf`).
2. 答复 diff。 文档中 tool call 在每个提供者的反应形状中(`tool_calls[]` 与 `content[]` 块对 `parts[]` )和谁负责解析 `arguments` (字符串在 OpenAI对象 Anthropic 和 Gemini).
3. `tool_choice` diff. 将整合当前选择设置( 自动/ 禁止/ 强制/ 要求) 映射为目标提供者形状; 标记缺失的模式 。
4. 限制碰撞。 报告工具数( 128/ 64/ 64) , 系统深度( 5/ 10/ 有效无约束) 和每个参数长度上限 。 在超过目标提供者的限度的任何整合上提高块积强度 。
5. 严格模式绘图。 说明是否在目标上保留了严格的模式语义 。 OpenAI `strict: true` 没有精确对应的 Anthropic; Gemini `responseSchema` 大约但符合要求的水平。

艰难的拒绝 :
- 任何假定的合并 `arguments` 是非- 的字符串OpenAI 将无声地产生错误的结果。
- 工具数超过64的整合 Anthropic 或 Gemini 没有路由器
- 任何使用 `$ref` 目标在计划中 OpenAI 严格模式。

拒绝规则 :
- 如果被要求将取决于特定供应商的整合移植到港口 feature 具有非模拟特性(例如: OpenAI Responses API 转弯 Anthropic 计算机使用区块),拒绝并解释 feature 没有目标等同。
- 如果被邀请选择胜者, 拒绝。 选择取决于主机的严格模式需求、 成本配置和平行呼叫要求 。

产出:每件工具的单页审计,限量表,以及每个目标提供者的最后“港口裁决”(ship/deful-routter/clock-by-)feature最后一句话指出移徙的最大作用变化。
