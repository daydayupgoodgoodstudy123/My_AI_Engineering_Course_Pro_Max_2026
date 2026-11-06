---
name: multi-agent-team
description: Build a multi-agent software team with architect, parallel coders, reviewer, and tester; measure against SWE-bench Pro and produce a handoff post-mortem.
version: 1.0.0
phase: 19
lesson: 10
tags: [capstone, multi-agent, swe-bench, langgraph, a2a, worktree, roles]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


给定 GitHub 发布 URL 和平行级别, 部署一个多agent 软件团队,制作一个合并准备的PR。 handoff- 直方图失效

构建计划 :

1. 任务板: 文件支持 (或 Redis) JSONL 存储已输入的信件。 信件类型: 计划_请求, 子任务, diff_准备就绪, 复议_需要、审查_反馈、核准、测试_需要,测试_通过测试_失败, 重计划_needed.
2. 建筑师(Opus 4.7):读一读问题,写出计划,发出一个带有明确界面的子任务控制表(文件被触动、公共功能、测试冲击)。
3. N编码器(Sonnet 4.7):每个编号都要求一个子任务,产生一个新的 `git worktree add` + 代顿纳a sandbox独立执行
4. 合并协调员:三向合并; LLM- 调解解决冲突,但只在文件一级重叠。
5. 审阅员 (GPT-5.4:读合并 diff; 无法批准它所写的 diff; 发布已核准或审查_反馈发送到相关编码器。
6. 测试器 (Gemini 2.5 Pro:在清洁的试验室内运行试验套房 sandbox; 发布测试_通过或测试_与文物失败。
7. Handoff 计算:每个交叉功能信息都变成带有有效载荷大小和型号的兰弗斯区域。计算 token 增益=总计_符号/单_agent_baseline_tokens.
8. 输入明显的错误探测器( 运行量的10%) 来测量审查者错误批准率 。
9. 运行50个 SWE-bench Pro 问题; 发布通行证@ 1, 墙上时钟对单agent 基准,每功用 token breakdown, handoff- 直方图失效

评估标题:

| Weight | 标准 | Measurement |
|:-:|---|---|
| 25 | SWE - Bench 方案通行证@ 1 | 50 号分机通行证@ 1 |
| 20 | 平行加速 | 单向钟点对单向agent baseline |
| 20 | 审查质量 | 注射式错误检测的误准率 |
| 20 | Token efficiency | Total tokens 解决的问题和单agent |
| 15 | 协调工程 | 合并解决冲突, handoff- 直方图失效 |

艰难的拒绝 :

- 能够批准它所编写或提议的审查员。
- 连一个没有匹配的报告...agent 运行基准。agent 一定要赢 *每美元*,不只是通过@ 1。
- 将信件改为自由格式字符串而不是键入的任务栏 A2A messages.
- 合并那些默默地放下冲突diffs而不是重新规划的协调员。

拒绝规则 :

- 拒绝运行,不设定每个角色的预算上限(第1条)token +美元)的汇率。
- 拒绝打开其测试器未在清洁状态中验证的公关 sandbox.
- 拒绝一次对8级以上的编码员进行比对。 协调管理比这要多。

输出:包含任务委员会+角色工人的回购,50个问题 SWE-bench Pro 运行日志,匹配的单agent 运行基线, 带有角色标记的 Langfuse 仪表板, 以及每个功能 token 解剖,注射式窃听器检测报告, 和验尸后命名三 handoffs 和消息系统或 prompt 改变,降低每一个。
