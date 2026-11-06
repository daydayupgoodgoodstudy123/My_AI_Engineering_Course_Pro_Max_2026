---
name: terminal-coding-agent
description: Build and evaluate a terminal-native coding agent against SWE-bench Pro with bounded cost, sandboxed tools, and full 2026 hook surface.
version: 1.0.0
phase: 19
lesson: 01
tags: [capstone, coding-agent, claude-code, swe-bench, mcp, hooks, sandbox]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


设计一个目标存储库和一项自然语言任务, harness 计划,执行 sandbox,然后打开 pull request。 匹配或打败迷你丝丝丝...agent 基准,30个任务SWE-Bench Pro子集,但每个任务预算5美元。

构建计划 :

1. 站起来 包和墨水 提示 harness 带一个计划板,工具呼叫流,和活的 token/美元预算。
2. 定义 6 个工具( 读取)_文件, 编辑_文件, 复位, 树_sitter_符号,运行_shell, git结束 Model Context Protocol 流式HTTP。 每个呼叫最多返回 4k tokens.
3. 运行每个 tool call E2B或Dontona内部的 sandbox 在一个新鲜的 `git worktree add` branch。不要触摸主机文件系统。
4. 电线 全部八次 2026 钩子事件: 会话启动、会话使用、预用工具、后方工具使用、用户程序提交、通知、停止、预处理。 船舶至少四个用户使用的钩子( 破坏性指令保护, 以及 token 会计,OTel 覆盖排放, trace ) 包抄作者。
5. 执行三个预算:50个轮转,200k tokens5美元 150公里的预火力 总结老轮转
6. Emit OpenTelephysics 与GenAI语义协议的连接, 与自办的兰福斯相隔。
7. 成功的时候,推 branch 并打开一个公关与计划 trace 包在身体里。
8. 以迷你丝丝为评价对象agent 30个问题 Python 子集和记录通行证@ 1, 转 tokens和美元每项任务。

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | SWE - Bench 方案通行证@ 1 | 30个任务子集和迷你丝agent baseline |
| 20 | 结构清晰度 | 计划/行动/观测分离、钩子表面、工具图案可读性 |
| 20 | 安全 | Sandbox 逃避红色队+破坏性指挥警卫的审计 |
| 20 | Observability | 100% tool calls spanned, token 每一转折的会计核算 |
| 15 | 开发者 UX | 冷启动于 2 下, 崩溃恢复, Ctrl- C 取消语义 |

艰难的拒绝 :

- Harness 炮弹飞向 git 而不是在主机文件系统中 sandbox.
- 任意 agent 可以在外写 worktree 或没有明确允许列表钩的曲线外部 URL 。
- 所报告的没有匹配基线的Eval数字也涉及30个问题。
- 表 1. 依据 `git reset --hard` 转接之间; SWE-bench Pro 是 pass@ 1 。

拒绝规则 :

- 拒绝直接按任何配置向主键 。 branches 仅.
- 拒绝禁用破坏命令的守卫。 这是非常困难的要求 。
- 拒绝在没有预算上限的情况下运行。 无限期运行会污染对评估的比较 。

输出: 包含 harness,一个固定的30个任务 SWE-bench Pro eval harness 和匹配的迷你丝we --agent 基线运行, 一个 Open 遥测 trace 归档至少5个完整运行,并写入命名任务 harness 解决基准不为或相反。结尾时在您所观察到的三种失败模式上有一个区域,钩子会改变每个模式。
