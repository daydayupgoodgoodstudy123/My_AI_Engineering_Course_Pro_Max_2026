---
name: a2a-agent-spec
description: Produce the Agent Card and skills schema for an agent that should be callable over A2A.
version: 1.0.0
phase: 13
lesson: 18
tags: [a2a, agent-card, task-lifecycle, delegation]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 agent其能力和预期的合作者, A2A Agent 贺卡和技能定义。

显示 :

1. Agent Card. `name`, `description`, `url`, `version`, `schemaVersion`, `capabilities` (streaming,推动通知) `skills[]`.
2. 技能清单。 `id`, `name`, `description`, `inputModes`, `outputModes`。在描述中使用“ X. 不使用 Y” 模式。
3. 任务状态计划。 对于每种技能,预期的状态过渡和投入_需要路径。
4. 签名计划。 是否通过 AP2 签署卡片( 建议外部使用) agents).
5. Transport. JSON-RPC over HTTP (默认)或 GRPC。 注意与 v1.0 的后向兼容 。

艰难的拒绝 :
- 任意 Agent 没有稳定的 URL 的卡片。 打破发现 。
- 任何技能, 没有声明输入和输出模式。 呼叫者无法解释兼容性 。
- 任何外传的 agent 没有AP2签名计划。 身份矢量

拒绝规则 :
- 如果 agent使用大小写为单 tool call,拒绝脚架 A2A; 建议 MCP.
- 如果 agent 暴露内部内容,但不应该(tool call traces, chain-of-thought拒绝和授权不透明。
- 如果 agent needs A2A 说明AP2与核心分开 A2A.

产出:一页 Agent Card JSON,为每次行动、州过渡计划、签署和运输选择制定技能计划。 agent promises.
