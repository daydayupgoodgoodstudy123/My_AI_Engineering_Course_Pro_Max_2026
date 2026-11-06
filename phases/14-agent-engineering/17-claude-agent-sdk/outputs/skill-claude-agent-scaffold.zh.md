---
name: claude-agent-scaffold
description: Scaffold a Claude Agent SDK app with subagents, lifecycle hooks, session store, MCP server attachment, and W3C trace propagation.
version: 1.0.0
phase: 14
lesson: 17
tags: [claude-agent-sdk, subagents, hooks, session-store, mcp]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给出产品领域和清单 MCP 服务器,脚架 a Claude Agent SDK app.

显示 :

1. 一条主 agent 带有指令的定义, 内置工具访问( 读取)_文件, 写入_文件、 shell、 grep、 glob、 Web 获取和自定义函数工具 。
2. Subagent 产卵器用于平行和环境隔离。 使用时, 乐团会破坏其背景预算 。
3. 注册的生命周期钩:审计前工具使用+后工具使用、设置会话启动、拆卸会话启动、规则执行用户PromptSubmit(见支持工作流程模式)。
4. 会话存储( SQLite 默认) `list_subkeys` 装有电线,可以制造 subagent tree.
5. MCP 外部工具/资源表面的服务器附件 。
6. W3C trace 环境传播,所以OTel 横跨呼叫者 通过CLI。

艰难的拒绝 :

- 发光 subagent 单工具的工作。 Subagents 指平行或环境孤立;而非 " 一改为 "_档案呼叫。"
- 钩子与同步的昂贵工作。 钩子应该是微秒到毫秒。 长的工作属于一个 subagent.
- 课程商店没有级联删除政策。 subagent 循环气流存储。

拒绝规则 :

- 如果产品需要长期的自动合成工作(小时对天),则拒绝自行托管 SDK 和前往 Claude Managed Agents.
- 如果用户要求 `--session-mirror` 使用共享位置, 拒绝。 会话记录包含 PII; 镜像到每个用户加密的存储 。
- 如果 agent 取决于生 LLM streaming 对于未使用工具的 UX, 拒绝 Agent SDK 并推荐客户 SDK directly.

输出: `agent.py`, `tools.py`, `hooks.py`, `session.py`, `README.md` 解释 subagent 政策,钩子注册,会话后端, MCP 附加附件和 OTel 线。 结尾为“ 下一步读什么” , 指向 22 课 以表达声音 handoffs,OTel的第23课涵盖属性,如果产品需要生产运行时间形状,则第18课。
