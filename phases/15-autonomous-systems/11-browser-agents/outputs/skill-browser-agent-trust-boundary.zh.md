---
name: browser-agent-trust-boundary
description: Scope a proposed browser-agent deployment — trust zones, authorized writes, required defenses — before the agent touches a real site.
version: 1.0.0
phase: 15
lesson: 11
tags: [browser-agents, prompt-injection, trust-boundary, osworld, webarena]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


有了这个浏览器...agent 工作流程,产生一个信任范围范围的文件 列出每个阅读,每一个写作, 和最起码的防御堆叠 第一次运行。

显示 :

1. **读表面。** 列出每个来源 agent 将每个网站归类为托管(由用户组织运营的首选网站)或托管外(任何第三方、任何用户生成的内容、任何搜索结果)。 prompt-注射频道
2. **写表面。** 列出随后采取的所有行动 agent 允许使用( 提交表单、 邮寄内容、 调用后端工具、 写入内存) 。 对于每个对象, 请说明爆炸半径以及动作是否可逆 。
3. **需要的防御** 最小堆叠: 内容净化器, 读写/ 写边界( 内容需要经新批准)_来源是不信任的)工具允许列表,每个任务,有范围范围的证书的会话孤立,金丝雀 tokens 持续记忆, HITL 不可逆转的行动。
4. **基准至分布合适。** 如果 agent 中键报告浏览 Comp, OSWorld, 或 WebArena- Verificate 的分数, 指定基准与实际任务之间的分布重叠。 高浏览 Comp 分数无法预测预订流量的可靠性 。
5. **已知的攻击清单。** 确认部署的强度,以(a) 可见文字注入,(b) URL碎片/查询注入,(c) 内存连接攻击(记事表类),(d) 验证会话上的CSRF形攻击,(e) 一击劫持。每个会话都列出具体防御和开火地点。

艰难的拒绝 :
- Browser agents 能够取得生产证书,且不与届会隔绝。
- 任何使用从信托外内容开始的文字不需要新的HITL批准。
- 任何仅依靠内容净化剂的部署(卫生器很容易受到攻击;尖端有效载荷通过)。
- 内存不变,无金丝雀条目。
- 触及金融交易或客户数据且没有HITL的工作流程写道。

拒绝规则 :
- 如果用户无法说出注射驱动错误的文字的爆炸半径,则拒绝并要求明确句子。
- 如果用户提议浏览器 agent 无法获取范围证书的堆叠上, 请先拒绝并请求单独身份 。
- 如果用户引用基准分数( BrowseComp、 OSWorld、 WebArena)作为证据 agent 能够做生产任务 拒绝和要求内部评估 真实分布。

输出格式 :

以下列方式归还一份信任备忘录:
- **读取表面表格** (来源、委托/委托外)
- **写入表层** (动作、爆炸半径、可逆 y/n)
- **国防堆叠** (已配置的层的布告列表)
- **基准适用说明** (如果适用)
- **已知攻击清单** (五行,每行防守名)
- **部署决定** (生产/中转/仅研究)
