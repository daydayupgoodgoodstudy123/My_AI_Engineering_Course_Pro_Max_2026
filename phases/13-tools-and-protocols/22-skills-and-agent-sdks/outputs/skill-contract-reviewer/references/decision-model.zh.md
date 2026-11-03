<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="primitive-decision-model"></a>

# 原始决定模式

由责任选择,不止一个原始的是正确的

| 需要 | Primitive | Boundary |
|---|---|---|
| 一次性指令 | Prompt | 存在当前互动 |
| 全仓库的默认值 | AGENTS.md | 在存储器范围中工作时适用 |
| 可重复使用的任务方法 | Agent Skill | 装载任务的程序知识 |
| 外部操作或数据 | MCP tool | 显示有输入合同的可调用能力 |
| 对运行时事件的反应 | Hook | 在主机定义的生命周期点运行 |
| 决定性转变 | 普通代码 | 生成可重复输出, 不使用模型判断 |
| 孤立或平行的上下文 | Subagent | 将一项捆绑的任务单独列为一项任务 context window |

远程服务查询的发布-审查方法可同时使用 Agent Skill 和一个 MCP 工具。仓库测试协议可以添加 AGENTS.md. 工具后的审计可能会添加钩子。稳定的解析属于普通代码。 subagent.
