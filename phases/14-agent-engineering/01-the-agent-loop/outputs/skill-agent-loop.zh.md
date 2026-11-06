---
name: agent-loop
description: Write a correct, minimal ReAct agent loop in any target language/runtime with tools, stop condition, and turn budget.
version: 1.0.0
phase: 14
lesson: 01
tags: [react, agent-loop, tools, observability, stop-condition]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


设定目标运行时间( 时间) (E)Python async, Python 同步,节点, Rust 自动、 Go) 和工具列表( 名称、 输入模式、 可调用) , 产生 ReAct agent loop 第一次尝试时,这是对的。

显示 :

1. 带有 { user, 助手, 工具, final} 角色和目标提供者所期望的系统图的邮件缓冲类型( ) 。Anthropic `tool_use` / `tool_result` blocks, OpenAI 函数调用信件, 响应 API 逻辑频道) 。 绝不在提供者之间静悄悄地交换方案 。
2. 工具登记册, 名称 - > 可调用发送、 输入验证和输入结果。 必须捕获错误, 并将其转换为观察字符串, 从未被移动到循环中 。
3. 循环运行到: 明确 `finish` 动作,无 tool calls 最多转个圈,最多转一个圈 tokens, 或一个 guardrail 旅行,选一个主要站,其他是安全带
4. 预算转向任务类别——任务10,计算机使用200,深度研究400。
5. 一个 trace 记录所有的想法、动作、观察和停止理性。`invoke_agent`, `tool_call`当运行时间有一个 OTel 时 SDK present.

艰难的拒绝 :

- 环绕时没有转弯帽,这是可靠性问题,不是优化问题。
- 将工具错误转换为空观察。 模型必须看到失败文本才能校正 。
- 将检索的内容作为可信任的指示处理。 所有工具输出都是不可信的输入, 只有 user message 携带权限( 见 OpenAI 海关总署文件)。
- 混合提供者,没有计划翻译层。 Anthropic 和 OpenAI 具有不同的工具图案和信息形状。

拒绝规则 :

- 如果目标为“无框架,只按下,” , 拒绝并推荐至少输入信息模式; agent loops 用于不打字的 shell 粘结, 错误易变 。
- 如果用户要求“ 自动重试失败” tool call 拒绝。 重试必须经过模型 (% 1)CRITIC/自备,第05课或属于工具本身 idempotency contract.
- 如果工具列表中含有一个没有 human-in-the-loop 确认、拒绝和指向 09 (允许 + 沙箱) 课程。

输出: 每个语言目标一个文件加 a `README.md` 解释禁产条件的选择,转而说明预算理由,一个工作 trace 显示每步思维- 动作观察。 结尾处指向 02 (REWOO) planning如果任务长于一等,则为重复执行,或为重复执行,则为第3课(反省),或第27课(prompt injection如果工具触动了不可信的内容。
