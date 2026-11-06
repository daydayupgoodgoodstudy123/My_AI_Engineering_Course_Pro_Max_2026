---
name: injection-defense
description: Build a PVE (Prompt-Validator-Executor) layer with source-tagged content, injection-marker scanning, and allowlist navigation for any agent runtime.
version: 1.0.0
phase: 14
lesson: 27
tags: [security, prompt-injection, pve, greshake, source-tag]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 agent 具有工具访问和检索, 产生一个注射 - 防御层。

显示 :

1. 每个内容的源标签 : `user_message`, `tool_output`, `retrieved_web`, `retrieved_memory`, `retrieved_file`。在信息历史中传递标记。
2. `Validator.assess(tool_call, contents)` - 拒绝 tool calls 带有注入形的参数或检索的内容; 只有在源标签与所声明的信任级别匹配时才允许 。
3. 允许导航列表/ 块列表: URL、 域名、 文件路径 agent 可能触摸。
4. Memory-write guardrail拒绝写作看起来像是指令。
5. 内容获取纪律(课程23):存储外部检索的内容;横幅带有参考编号,而不是流言。
6. 测试套房:五个格雷沙克人 利用班级作为红色队。

艰难的拒绝 :

- 工具使用表面没有源标签。 没有源代码无法区分权限级别 。
- 仅运行于最终输出的验证符。 延迟验证不相干, 模型已经运行了 。
- “相信我，system prompt 会处理好。”仅靠规范系统级 prompt，并不能构成防护措施。

拒绝规则 :

- 如果 agent 具有任何回收能力,无需源标签,拒绝装运。检索的内容是弹射矢量。
- 如果敏感工具( 发送信件、 执行 shell、 在 / 中写入文件) 没有 human-in-the-loop 确认,拒绝。
- 如果记忆书写无防守,就拒绝。 下个会话中持续内存中毒再次中毒。

输出: `validator.py`, `source_tag.py`, `allowlist.py`, `memory_guard.py`, `red_team.py`, `README.md` 解释六种控制堆、残余风险和持续审查的顺序。结尾处加上“下一个读什么”指向21课(计算机使用安全)和23课(通过 OTel 获取内容)。
