# Phase 14 Agent 工程 — Agent Engineering

[返回总目录](README.md) · [前一章](13-工具与协议.md) · [后一章](15-自主与长任务系统.md)

本章共 **54 节**。

**掌握目标**：能设计有状态、可恢复、可评估的 Agent，并把任务、证据、验证与交接落实到工作流程。

**章节衔接**：以 Phase 13 工具接口为基础，向长任务、多 Agent 和生产部署扩展；31–46 聚焦工作台，47–54 聚焦产品判断。

**为什么有用**：处于模型调用之上的任务执行与编排层。它管理状态、记忆、工具、恢复和验证，也把用户目标转成有边界、可交付的工程任务。

**章节练习**：先完成有明确停止条件的单 Agent，再加入 checkpoint、失败样例与验收；根据任务需要选择后续工程分支。

小节中的“衔接”说明知识如何复用，不代表必须按编号完成所有分支；原课的具体前置要求见教材。建议练习可配合原课代码完成，CoderPad 的实际题目范围以各自 `PROMPT.md` 为准。

## 基础循环、规划与修订

### 14.01 [Agent 基本循环](../14-agent-engineering/01-the-agent-loop/docs/en.md) — The Agent Loop: Observe, Think, Act

- **掌握**：理解观察、推理、行动、反馈和终止条件。
- **衔接**：将工具调用组织成解决任务的连续执行过程。
- **为什么有用**：位于 Agent 的执行控制核心。观察结果改变下一步选择，工具调用因此形成闭环；终止条件让持续行动保持有界。
- **建议练习**：模拟两轮工具使用，检查成功、失败和步数上限。

入口：[中文教材](../14-agent-engineering/01-the-agent-loop/docs/zh.md) · [原课代码](../14-agent-engineering/01-the-agent-loop/code/) · [CoderPad](../14-agent-engineering/01-the-agent-loop/coderpad/README.md) · [分关练习](../14-agent-engineering/01-the-agent-loop/exam/README.md) · [课后测验](../14-agent-engineering/01-the-agent-loop/quiz/quiz.md)

### 14.02 [ReWOO 与计划执行](../14-agent-engineering/02-rewoo-plan-and-execute/docs/en.md) — ReWOO and Plan-and-Execute: Decoupled Planning

- **掌握**：理解 planner、worker、solver 的职责分离。
- **衔接**：与交错式 Agent 循环比较规划和执行成本。
- **为什么有用**：位于任务规划与实际执行的分工层。提前明确依赖可以减少重复规划，但需要处理计划过期和执行结果不符合预期的情况。
- **建议练习**：把任务写成带依赖的步骤，检查中间结果如何引用。

入口：[中文教材](../14-agent-engineering/02-rewoo-plan-and-execute/docs/zh.md) · [原课代码](../14-agent-engineering/02-rewoo-plan-and-execute/code/) · [CoderPad](../14-agent-engineering/02-rewoo-plan-and-execute/coderpad/README.md) · [分关练习](../14-agent-engineering/02-rewoo-plan-and-execute/exam/README.md) · [课后测验](../14-agent-engineering/02-rewoo-plan-and-execute/quiz/quiz.md)

### 14.03 [Reflexion](../14-agent-engineering/03-reflexion-verbal-rl/docs/en.md) — Reflexion: Verbal Reinforcement Learning

- **掌握**：理解执行、评估、反思及经验记忆。
- **衔接**：在失败后形成下一次尝试可用的反馈。
- **为什么有用**：位于跨尝试的经验反馈层。失败原因被保留下来后，下一次执行才有机会改变策略，而非从同样的错误重新开始。
- **建议练习**：记录一次失败和反思，检查重试是否改变具体行为。

入口：[中文教材](../14-agent-engineering/03-reflexion-verbal-rl/docs/zh.md) · [原课代码](../14-agent-engineering/03-reflexion-verbal-rl/code/) · [CoderPad](../14-agent-engineering/03-reflexion-verbal-rl/coderpad/README.md) · [分关练习](../14-agent-engineering/03-reflexion-verbal-rl/exam/README.md) · [课后测验](../14-agent-engineering/03-reflexion-verbal-rl/quiz/quiz.md)

### 14.04 [思维树与 LATS](../14-agent-engineering/04-tree-of-thoughts-lats/docs/en.md) — Tree of Thoughts and LATS: Deliberate Search

- **掌握**：把推理表示为候选展开、评分和搜索。
- **衔接**：从单一路径扩展到有预算的多候选探索。
- **为什么有用**：位于多候选推理与搜索预算层。复杂问题可能需要探索替代路径，评分与剪枝决定有限计算是否用在更有希望的候选上。
- **建议练习**：画一棵小搜索树，定义剪枝和停止条件。

入口：[中文教材](../14-agent-engineering/04-tree-of-thoughts-lats/docs/zh.md) · [原课代码](../14-agent-engineering/04-tree-of-thoughts-lats/code/) · [CoderPad](../14-agent-engineering/04-tree-of-thoughts-lats/coderpad/README.md) · [分关练习](../14-agent-engineering/04-tree-of-thoughts-lats/exam/README.md) · [课后测验](../14-agent-engineering/04-tree-of-thoughts-lats/quiz/quiz.md)

### 14.05 [Self Refine 与 CRITIC](../14-agent-engineering/05-self-refine-and-critic/docs/en.md) — Self-Refine and CRITIC: Iterative Output Improvement

- **掌握**：区分自我反馈与外部工具辅助的修订。
- **衔接**：补充 Reflexion，聚焦单次产物的迭代改进。
- **为什么有用**：位于产物质量的迭代修订层。反馈必须指向具体缺陷，外部检查还可补充模型自评，从而判断每轮修改是否真的改善结果。
- **建议练习**：保留初稿、反馈和修订，检查反馈是否有依据。

入口：[中文教材](../14-agent-engineering/05-self-refine-and-critic/docs/zh.md) · [原课代码](../14-agent-engineering/05-self-refine-and-critic/code/) · [CoderPad](../14-agent-engineering/05-self-refine-and-critic/coderpad/README.md) · [分关练习](../14-agent-engineering/05-self-refine-and-critic/exam/README.md) · [课后测验](../14-agent-engineering/05-self-refine-and-critic/quiz/quiz.md)

### 14.06 [Agent 工具使用](../14-agent-engineering/06-tool-use-and-function-calling/docs/en.md) — Tool Use and Function Calling

- **掌握**：理解工具选择、调用训练信号和执行反馈。
- **衔接**：复用 Phase 13 接口，把工具纳入规划决策。
- **为什么有用**：位于 Agent 决策与外部能力选择之间。工具让系统获得计算和查询结果，执行反馈则为下一步决策提供可观察依据。
- **建议练习**：比较可直接回答和必须查工具的两类任务。

入口：[中文教材](../14-agent-engineering/06-tool-use-and-function-calling/docs/zh.md) · [原课代码](../14-agent-engineering/06-tool-use-and-function-calling/code/) · [CoderPad](../14-agent-engineering/06-tool-use-and-function-calling/coderpad/README.md) · [分关练习](../14-agent-engineering/06-tool-use-and-function-calling/exam/README.md) · [课后测验](../14-agent-engineering/06-tool-use-and-function-calling/quiz/quiz.md)

## 记忆、技能与任务分解

### 14.07 [虚拟上下文与记忆分页](../14-agent-engineering/07-memory-virtual-context-memgpt/docs/en.md) — Agent Memory — Virtual Context and Memory Paging

- **掌握**：区分当前上下文、外部记忆和检索读写。
- **衔接**：解决长任务中信息无法全部常驻窗口的问题。
- **为什么有用**：位于有限上下文与长期任务信息之间的记忆层。分页与检索让重要信息按需进入窗口，避免把无限增长的历史直接塞给模型。
- **建议练习**：给一段长对话分配保留、归档和按需读取内容。

入口：[中文教材](../14-agent-engineering/07-memory-virtual-context-memgpt/docs/zh.md) · [原课代码](../14-agent-engineering/07-memory-virtual-context-memgpt/code/) · [CoderPad](../14-agent-engineering/07-memory-virtual-context-memgpt/coderpad/README.md) · [分关练习](../14-agent-engineering/07-memory-virtual-context-memgpt/exam/README.md) · [课后测验](../14-agent-engineering/07-memory-virtual-context-memgpt/quiz/quiz.md)

### 14.08 [记忆块与后台整理](../14-agent-engineering/08-memory-blocks-sleep-time-compute/docs/en.md) — Memory Blocks and Sleep-Time Compute

- **掌握**：理解核心、历史和归档记忆及离线整理。
- **衔接**：细化记忆分页，设计跨会话的信息维护。
- **为什么有用**：位于长期记忆的组织与维护层。不同记忆承担稳定事实、事件回顾和资料归档，整理过程还要防止过期或错误信息被固化。
- **建议练习**：把原始对话转为带来源的记忆，检查过期与纠正。

入口：[中文教材](../14-agent-engineering/08-memory-blocks-sleep-time-compute/docs/zh.md) · [原课代码](../14-agent-engineering/08-memory-blocks-sleep-time-compute/code/) · [CoderPad](../14-agent-engineering/08-memory-blocks-sleep-time-compute/coderpad/README.md) · [分关练习](../14-agent-engineering/08-memory-blocks-sleep-time-compute/exam/README.md) · [课后测验](../14-agent-engineering/08-memory-blocks-sleep-time-compute/quiz/quiz.md)

### 14.09 [向量、图与 KV 混合记忆](../14-agent-engineering/09-hybrid-memory-mem0/docs/en.md) — Hybrid Memory: Vector + Graph + KV

- **掌握**：理解语义、关系和精确状态的不同存储需求。
- **衔接**：在统一记忆目标下选择多种索引。
- **为什么有用**：位于 Agent 状态的多种索引层。向量适合语义相近，图适合关系，KV 适合精确字段，混合设计对应不同查询需求。
- **建议练习**：为事实、任务状态和事件关系分别选存储方式。

入口：[中文教材](../14-agent-engineering/09-hybrid-memory-mem0/docs/zh.md) · [原课代码](../14-agent-engineering/09-hybrid-memory-mem0/code/) · [CoderPad](../14-agent-engineering/09-hybrid-memory-mem0/coderpad/README.md) · [分关练习](../14-agent-engineering/09-hybrid-memory-mem0/exam/README.md) · [课后测验](../14-agent-engineering/09-hybrid-memory-mem0/quiz/quiz.md)

### 14.10 [技能库与持续学习](../14-agent-engineering/10-skill-libraries-voyager/docs/en.md) — Skill Libraries and Lifelong Learning (Voyager)

- **掌握**：理解课程生成、技能提取、检索和复用。
- **衔接**：把单次任务经验转成未来可调用的能力。
- **为什么有用**：位于任务经验到可复用行为的积累层。技能库保存经过验证的操作方法，让后续任务能够复用已有步骤而非全部重新规划。
- **建议练习**：从成功轨迹提炼技能，补上适用条件和验证样例。

入口：[中文教材](../14-agent-engineering/10-skill-libraries-voyager/docs/zh.md) · [原课代码](../14-agent-engineering/10-skill-libraries-voyager/code/) · [CoderPad](../14-agent-engineering/10-skill-libraries-voyager/coderpad/README.md) · [分关练习](../14-agent-engineering/10-skill-libraries-voyager/exam/README.md) · [课后测验](../14-agent-engineering/10-skill-libraries-voyager/quiz/quiz.md)

### 14.11 [HTN 与进化规划](../14-agent-engineering/11-planning-htn-and-evolutionary/docs/en.md) — Planning with HTN and Evolutionary Search

- **掌握**：理解任务分解、方法、前置条件和效果。
- **衔接**：补充自然语言计划，为复杂任务增加结构约束。
- **为什么有用**：位于结构化规划与可执行操作之间。前置条件和效果让计划可以检查依赖，也能在动作失败时找出需要重规划的位置。
- **建议练习**：将目标分解为可执行操作，检查每步前置条件。

入口：[中文教材](../14-agent-engineering/11-planning-htn-and-evolutionary/docs/zh.md) · [原课代码](../14-agent-engineering/11-planning-htn-and-evolutionary/code/) · [CoderPad](../14-agent-engineering/11-planning-htn-and-evolutionary/coderpad/README.md) · [分关练习](../14-agent-engineering/11-planning-htn-and-evolutionary/exam/README.md) · [课后测验](../14-agent-engineering/11-planning-htn-and-evolutionary/quiz/quiz.md)

## 工作流与运行框架

### 14.12 [工作流模式](../14-agent-engineering/12-anthropic-workflow-patterns/docs/en.md) — Anthropic's Workflow Patterns: Simple Over Complex

- **掌握**：区分链式、路由、并行、协调和评估优化。
- **衔接**：把前面 Agent 技术映射到可选择的执行结构。
- **为什么有用**：位于 Agent 应用的架构选择层。许多任务可以用固定工作流完成，匹配复杂度能减少额外协调、状态和调试成本。
- **建议练习**：为三个任务选最少必要模式并说明状态需求。

入口：[中文教材](../14-agent-engineering/12-anthropic-workflow-patterns/docs/zh.md) · [原课代码](../14-agent-engineering/12-anthropic-workflow-patterns/code/) · [CoderPad](../14-agent-engineering/12-anthropic-workflow-patterns/coderpad/README.md) · [分关练习](../14-agent-engineering/12-anthropic-workflow-patterns/exam/README.md) · [课后测验](../14-agent-engineering/12-anthropic-workflow-patterns/quiz/quiz.md)

### 14.13 [有状态图编排](../14-agent-engineering/13-langgraph-stateful-graphs/docs/en.md) — Stateful Graph Orchestration — Durable Execution and Checkpoints

- **掌握**：掌握类型化状态、节点、条件边和持久化。
- **衔接**：把工作流显式化，支持中断和恢复。
- **为什么有用**：位于 Agent 的持久执行与状态转换层。显式图结构方便查看分支、保存进度和恢复失败，适合有审查或中断需求的流程。
- **建议练习**：设计失败重试图，检查重复执行会否重复写入。

入口：[中文教材](../14-agent-engineering/13-langgraph-stateful-graphs/docs/zh.md) · [原课代码](../14-agent-engineering/13-langgraph-stateful-graphs/code/) · [CoderPad](../14-agent-engineering/13-langgraph-stateful-graphs/coderpad/README.md) · [分关练习](../14-agent-engineering/13-langgraph-stateful-graphs/exam/README.md) · [课后测验](../14-agent-engineering/13-langgraph-stateful-graphs/quiz/quiz.md)

### 14.14 [Actor 与异步消息](../14-agent-engineering/14-autogen-actor-model/docs/en.md) — The Actor Model for Agents — Async Messages and Typed Runtimes

- **掌握**：理解消息、隔离、并发和故障边界。
- **衔接**：提供不同于共享状态图的运行模型。
- **为什么有用**：位于并发 Agent 的消息与隔离运行层。Actor 用消息组织状态变化，适合分析异步协作、局部故障和背压的影响。
- **建议练习**：模拟两个 actor 交换消息，处理超时和重复消息。

入口：[中文教材](../14-agent-engineering/14-autogen-actor-model/docs/zh.md) · [原课代码](../14-agent-engineering/14-autogen-actor-model/code/) · [CoderPad](../14-agent-engineering/14-autogen-actor-model/coderpad/README.md) · [分关练习](../14-agent-engineering/14-autogen-actor-model/exam/README.md) · [课后测验](../14-agent-engineering/14-autogen-actor-model/quiz/quiz.md)

### 14.15 [角色型 Agent 团队](../14-agent-engineering/15-crewai-role-based-crews/docs/en.md) — Role-Based Agent Teams — Roles, Tasks, Processes

- **掌握**：区分角色、任务、流程和结果责任。
- **衔接**：将工作流分给不同职责，连接 Phase 16。
- **为什么有用**：位于多 Agent 的职责分配与交付层。角色只有配合任务合同和验收才有意义，否则容易形成重复工作或责任空缺。
- **建议练习**：写出 planner、executor 和 reviewer 的交付合同。

入口：[中文教材](../14-agent-engineering/15-crewai-role-based-crews/docs/zh.md) · [原课代码](../14-agent-engineering/15-crewai-role-based-crews/code/) · [CoderPad](../14-agent-engineering/15-crewai-role-based-crews/coderpad/README.md) · [分关练习](../14-agent-engineering/15-crewai-role-based-crews/exam/README.md) · [课后测验](../14-agent-engineering/15-crewai-role-based-crews/quiz/quiz.md)

### 14.16 [Agents SDK 的执行原语](../14-agent-engineering/16-openai-agents-sdk/docs/en.md) — OpenAI Agents SDK: Handoffs, Guardrails, Tracing

- **掌握**：理解 Agent、工具、handoff、guardrail 和 tracing。
- **衔接**：将通用编排概念映射到具体 SDK。
- **为什么有用**：位于模型 API 之上的 Agent 应用编排层。SDK 把工具、任务移交、检查与 trace 组织成运行流程，帮助把模型调用接成可调试的系统。
- **建议练习**：画出一次移交，说明状态和工具权限如何传递。

入口：[中文教材](../14-agent-engineering/16-openai-agents-sdk/docs/zh.md) · [原课代码](../14-agent-engineering/16-openai-agents-sdk/code/) · [CoderPad](../14-agent-engineering/16-openai-agents-sdk/coderpad/README.md) · [分关练习](../14-agent-engineering/16-openai-agents-sdk/exam/README.md) · [课后测验](../14-agent-engineering/16-openai-agents-sdk/quiz/quiz.md)

### 14.17 [Harness 与会话存储](../14-agent-engineering/17-claude-agent-sdk/docs/en.md) — The Harness as a Library — Subagents and Session Store

- **掌握**：区分原始模型客户端和完整 Agent 执行框架。
- **衔接**：把子 Agent、工具和持久会话组合为运行库。
- **为什么有用**：位于模型客户端与完整编码 Agent 运行环境之间。Harness 管理工具、会话和子任务，让开发者可以复用执行机制并检查状态责任。
- **建议练习**：检查恢复会话所需内容，区分消息历史与执行状态。

入口：[中文教材](../14-agent-engineering/17-claude-agent-sdk/docs/zh.md) · [原课代码](../14-agent-engineering/17-claude-agent-sdk/code/) · [CoderPad](../14-agent-engineering/17-claude-agent-sdk/coderpad/README.md) · [分关练习](../14-agent-engineering/17-claude-agent-sdk/exam/README.md) · [课后测验](../14-agent-engineering/17-claude-agent-sdk/quiz/quiz.md)

### 14.18 [生产运行时与类型化工作流](../14-agent-engineering/18-agno-and-mastra-runtimes/docs/en.md) — Production Agent Runtimes — Fast Instantiation and Typed Workflows

- **掌握**：理解实例化、状态、存储和执行接口。
- **衔接**：从框架演示转向可持续运行的应用结构。
- **为什么有用**：位于 Agent 从实例化到长期服务的运行层。类型、存储和工作流接口影响启动成本、状态管理与恢复方式，需要结合任务负载选择。
- **建议练习**：为一个后台任务列初始化、运行、恢复和清理步骤。

入口：[中文教材](../14-agent-engineering/18-agno-and-mastra-runtimes/docs/zh.md) · [原课代码](../14-agent-engineering/18-agno-and-mastra-runtimes/code/) · [CoderPad](../14-agent-engineering/18-agno-and-mastra-runtimes/coderpad/README.md) · [分关练习](../14-agent-engineering/18-agno-and-mastra-runtimes/exam/README.md) · [课后测验](../14-agent-engineering/18-agno-and-mastra-runtimes/quiz/quiz.md)

## 评估、界面与可观测性

### 14.19 [代码与通用 Agent 基准](../14-agent-engineering/19-benchmarks-swebench-gaia/docs/en.md) — Benchmarks: SWE-bench, GAIA, AgentBench

- **掌握**：理解任务、环境、执行验收和结果可比性。
- **衔接**：为 Agent 能力建立独立于回答措辞的测量。
- **为什么有用**：位于 Agent 能力的外部测量层。执行验收检查任务是否实际完成，能区分流畅的解释、正确的修改和真正通过测试的结果。
- **建议练习**：检查一条代码任务的成功条件与实际测试证据。

入口：[中文教材](../14-agent-engineering/19-benchmarks-swebench-gaia/docs/zh.md) · [原课代码](../14-agent-engineering/19-benchmarks-swebench-gaia/code/) · [CoderPad](../14-agent-engineering/19-benchmarks-swebench-gaia/coderpad/README.md) · [分关练习](../14-agent-engineering/19-benchmarks-swebench-gaia/exam/README.md) · [课后测验](../14-agent-engineering/19-benchmarks-swebench-gaia/quiz/quiz.md)

### 14.20 [网页与操作系统基准](../14-agent-engineering/20-benchmarks-webarena-osworld/docs/en.md) — Benchmarks: WebArena and OSWorld

- **掌握**：理解可复现界面环境和操作结果验收。
- **衔接**：扩展 Agent 评估到浏览器和桌面行动。
- **为什么有用**：位于交互式环境中的行为评估层。浏览器与操作系统任务需要检查最终状态，单纯复述步骤或点击成功都不足以代表任务完成。
- **建议练习**：把点击步骤与最终状态分开，定义成功检查。

入口：[中文教材](../14-agent-engineering/20-benchmarks-webarena-osworld/docs/zh.md) · [原课代码](../14-agent-engineering/20-benchmarks-webarena-osworld/code/) · [CoderPad](../14-agent-engineering/20-benchmarks-webarena-osworld/coderpad/README.md) · [分关练习](../14-agent-engineering/20-benchmarks-webarena-osworld/exam/README.md) · [课后测验](../14-agent-engineering/20-benchmarks-webarena-osworld/quiz/quiz.md)

### 14.21 [Computer Use](../14-agent-engineering/21-computer-use-agents/docs/en.md) — Computer Use: Claude, OpenAI CUA, Gemini

- **掌握**：理解截图感知、坐标动作和操作后观察。
- **衔接**：把多模态模型接入真实界面的 Agent 循环。
- **为什么有用**：位于视觉感知与桌面动作的闭环层。截图解释、坐标定位和动作验证共同决定可靠性，界面变化会让一次性动作计划失效。
- **建议练习**：设计布局变化案例，检查动作前后的定位与验证。

入口：[中文教材](../14-agent-engineering/21-computer-use-agents/docs/zh.md) · [原课代码](../14-agent-engineering/21-computer-use-agents/code/) · [CoderPad](../14-agent-engineering/21-computer-use-agents/coderpad/README.md) · [分关练习](../14-agent-engineering/21-computer-use-agents/exam/README.md) · [课后测验](../14-agent-engineering/21-computer-use-agents/quiz/quiz.md)

### 14.22 [语音 Agent](../14-agent-engineering/22-voice-agents-pipecat-livekit/docs/en.md) — Voice Agents: Pipecat and LiveKit

- **掌握**：理解音频帧管道、控制事件和实时交互。
- **衔接**：连接 Phase 06 与工具型 Agent 执行。
- **为什么有用**：位于音频交互与 Agent 执行的连接层。语音任务还需要处理帧流、轮次和打断，文本工具流程必须适配实时事件。
- **建议练习**：画出用户打断时上游控制和下游音频的变化。

入口：[中文教材](../14-agent-engineering/22-voice-agents-pipecat-livekit/docs/zh.md) · [原课代码](../14-agent-engineering/22-voice-agents-pipecat-livekit/code/) · [CoderPad](../14-agent-engineering/22-voice-agents-pipecat-livekit/coderpad/README.md) · [分关练习](../14-agent-engineering/22-voice-agents-pipecat-livekit/exam/README.md) · [课后测验](../14-agent-engineering/22-voice-agents-pipecat-livekit/quiz/quiz.md)

### 14.23 [GenAI 遥测语义](../14-agent-engineering/23-otel-genai-conventions/docs/en.md) — OpenTelemetry GenAI Semantic Conventions

- **掌握**：理解 model、agent、tool 三类 span 的职责。
- **衔接**：为跨工具、跨 Agent 执行建立共同观测格式。
- **为什么有用**：位于 Agent 系统统一遥测的语义层。明确模型、Agent 和工具各记录什么，才能跨组件还原耗时、错误和执行关系。
- **建议练习**：给一次失败任务关联请求、模型和工具记录。

入口：[中文教材](../14-agent-engineering/23-otel-genai-conventions/docs/zh.md) · [原课代码](../14-agent-engineering/23-otel-genai-conventions/code/) · [CoderPad](../14-agent-engineering/23-otel-genai-conventions/coderpad/README.md) · [分关练习](../14-agent-engineering/23-otel-genai-conventions/exam/README.md) · [课后测验](../14-agent-engineering/23-otel-genai-conventions/quiz/quiz.md)

### 14.24 [Agent 可观测平台](../14-agent-engineering/24-agent-observability-platforms/docs/en.md) — Agent Observability: Langfuse, Phoenix, Opik

- **掌握**：区分 trace、会话、提示版本和评估管理。
- **衔接**：把遥测数据转为调试和质量分析入口。
- **为什么有用**：位于运行证据的收集与质量分析层。观测平台帮助关联会话、版本和评估结果，选型应围绕实际排障问题和数据需求。
- **建议练习**：列出排查错误所需字段，再比较平台能力。

入口：[中文教材](../14-agent-engineering/24-agent-observability-platforms/docs/zh.md) · [原课代码](../14-agent-engineering/24-agent-observability-platforms/code/) · [CoderPad](../14-agent-engineering/24-agent-observability-platforms/coderpad/README.md) · [分关练习](../14-agent-engineering/24-agent-observability-platforms/exam/README.md) · [课后测验](../14-agent-engineering/24-agent-observability-platforms/quiz/quiz.md)

## 协作、故障与运行模式

### 14.25 [多 Agent 讨论与协作](../14-agent-engineering/25-multi-agent-debate/docs/en.md) — Multi-Agent Debate and Collaboration

- **掌握**：理解候选、互评、轮次和汇总。
- **衔接**：引出 Phase 16，检查协作是否改善独立任务结果。
- **为什么有用**：位于多个候选之间的协作推理层。讨论可能发现遗漏，也可能放大共同偏差，需要和相同预算的单 Agent 结果对照。
- **建议练习**：固定预算比较单 Agent 与讨论，记录成本和正确性。

入口：[中文教材](../14-agent-engineering/25-multi-agent-debate/docs/zh.md) · [原课代码](../14-agent-engineering/25-multi-agent-debate/code/) · [CoderPad](../14-agent-engineering/25-multi-agent-debate/coderpad/README.md) · [分关练习](../14-agent-engineering/25-multi-agent-debate/exam/README.md) · [课后测验](../14-agent-engineering/25-multi-agent-debate/quiz/quiz.md)

### 14.26 [Agent 失败模式](../14-agent-engineering/26-failure-modes-agentic/docs/en.md) — Failure Modes: Why Agents Break

- **掌握**：识别任务理解、协调、执行和验证失败。
- **衔接**：把前面评估与观测用于定位具体机制问题。
- **为什么有用**：位于 Agent 可靠性的故障分析层。把失败拆成理解、协调、行动或验证问题，才知道该改提示、接口、状态还是验收。
- **建议练习**：给失败轨迹分类，指出最早可检测的错误点。

入口：[中文教材](../14-agent-engineering/26-failure-modes-agentic/docs/zh.md) · [原课代码](../14-agent-engineering/26-failure-modes-agentic/code/) · [CoderPad](../14-agent-engineering/26-failure-modes-agentic/coderpad/README.md) · [分关练习](../14-agent-engineering/26-failure-modes-agentic/exam/README.md) · [课后测验](../14-agent-engineering/26-failure-modes-agentic/quiz/quiz.md)

### 14.27 [Prompt Injection 防御](../14-agent-engineering/27-prompt-injection-defense/docs/en.md) — Prompt Injection and the PVE Defense

- **掌握**：理解外部内容、指令边界和受控执行。
- **衔接**：为工具型 Agent 的检索与行动链路加上约束。
- **为什么有用**：位于外部内容进入行动链路的信任控制层。检索和工具结果可能含恶意指令，防御需要约束它们能影响哪些决策与权限。
- **建议练习**：用恶意检索片段测试是否越权调用工具。

入口：[中文教材](../14-agent-engineering/27-prompt-injection-defense/docs/zh.md) · [原课代码](../14-agent-engineering/27-prompt-injection-defense/code/) · [CoderPad](../14-agent-engineering/27-prompt-injection-defense/coderpad/README.md) · [分关练习](../14-agent-engineering/27-prompt-injection-defense/exam/README.md) · [课后测验](../14-agent-engineering/27-prompt-injection-defense/quiz/quiz.md)

### 14.28 [Supervisor、Swarm 与层级编排](../14-agent-engineering/28-orchestration-patterns/docs/en.md) — Orchestration Patterns: Supervisor, Swarm, Hierarchical

- **掌握**：理解集中协调、分布协作和层级分解。
- **衔接**：按依赖与责任选择多 Agent 结构。
- **为什么有用**：位于多 Agent 的控制与协作拓扑层。不同结构决定谁分配任务、保存状态和处理失败，需按依赖关系与责任边界选择。
- **建议练习**：为同一任务比较状态所有权和失败恢复方式。

入口：[中文教材](../14-agent-engineering/28-orchestration-patterns/docs/zh.md) · [原课代码](../14-agent-engineering/28-orchestration-patterns/code/) · [CoderPad](../14-agent-engineering/28-orchestration-patterns/coderpad/README.md) · [分关练习](../14-agent-engineering/28-orchestration-patterns/exam/README.md) · [课后测验](../14-agent-engineering/28-orchestration-patterns/quiz/quiz.md)

### 14.29 [队列、事件与定时运行](../14-agent-engineering/29-production-runtimes/docs/en.md) — Production Runtimes: Queue, Event, Cron

- **掌握**：区分交互、后台、事件触发和周期任务。
- **衔接**：把逻辑工作流映射到持续运行的基础设施。
- **为什么有用**：位于 Agent 逻辑到生产任务调度的连接层。队列、事件和定时器决定任务何时启动、如何重试及怎样避免重复副作用。
- **建议练习**：为任务选择触发方式，设计幂等键与重试策略。

入口：[中文教材](../14-agent-engineering/29-production-runtimes/docs/zh.md) · [原课代码](../14-agent-engineering/29-production-runtimes/code/) · [CoderPad](../14-agent-engineering/29-production-runtimes/coderpad/README.md) · [分关练习](../14-agent-engineering/29-production-runtimes/exam/README.md) · [课后测验](../14-agent-engineering/29-production-runtimes/quiz/quiz.md)

### 14.30 [评估驱动 Agent 开发](../14-agent-engineering/30-eval-driven-agent-development/docs/en.md) — Eval-Driven Agent Development

- **掌握**：区分公共基准、自有离线集和线上效果。
- **衔接**：形成需求、实现、评估和改进的循环。
- **为什么有用**：位于需求、实现和质量反馈的开发闭环层。用评估先定义失败与成功，能让后续框架或提示变更围绕可测目标进行。
- **建议练习**：先写失败样例和验收规则，再修改一个执行环节。

入口：[中文教材](../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md) · [原课代码](../14-agent-engineering/30-eval-driven-agent-development/code/) · [CoderPad](../14-agent-engineering/30-eval-driven-agent-development/coderpad/README.md) · [分关练习](../14-agent-engineering/30-eval-driven-agent-development/exam/README.md) · [课后测验](../14-agent-engineering/30-eval-driven-agent-development/quiz/quiz.md)

## 工作台基础与持久状态

### 14.31 [为什么强模型仍会失败](../14-agent-engineering/31-agent-workbench-why-models-fail/docs/en.md) — Agent Workbench Engineering: Why Capable Models Still Fail

- **掌握**：区分模型能力与执行环境可靠性。
- **衔接**：开启工作台分支，将失败归因到环境和流程。
- **为什么有用**：位于模型能力与工作环境可靠性的分界处。任务失败可能来自状态丢失、反馈不足或验证缺位，工作台负责补足这些执行条件。
- **建议练习**：回看一次失败，区分模型判断、上下文和验证问题。

入口：[中文教材](../14-agent-engineering/31-agent-workbench-why-models-fail/docs/zh.md) · [原课代码](../14-agent-engineering/31-agent-workbench-why-models-fail/code/) · [CoderPad](../14-agent-engineering/31-agent-workbench-why-models-fail/coderpad/README.md) · [分关练习](../14-agent-engineering/31-agent-workbench-why-models-fail/exam/README.md) · [课后测验](../14-agent-engineering/31-agent-workbench-why-models-fail/quiz/quiz.md)

### 14.32 [最小 Agent 工作台](../14-agent-engineering/32-minimal-agent-workbench/docs/en.md) — The Minimal Agent Workbench

- **掌握**：理解启动状态、任务板和操作规则的最小集合。
- **衔接**：把上一节的问题转成可读取的工作入口。
- **为什么有用**：位于编码 Agent 的任务启动入口层。统一状态、任务与规则让新会话能快速接续，也减少每次重新猜测项目情况。
- **建议练习**：为小项目写最小启动材料，验证能否接续任务。

入口：[中文教材](../14-agent-engineering/32-minimal-agent-workbench/docs/zh.md) · [原课代码](../14-agent-engineering/32-minimal-agent-workbench/code/) · [CoderPad](../14-agent-engineering/32-minimal-agent-workbench/coderpad/README.md) · [分关练习](../14-agent-engineering/32-minimal-agent-workbench/exam/README.md) · [课后测验](../14-agent-engineering/32-minimal-agent-workbench/quiz/quiz.md)

### 14.33 [可执行的 Agent 约束](../14-agent-engineering/33-instructions-as-executable-constraints/docs/en.md) — Agent Instructions as Executable Constraints

- **掌握**：把宽泛要求转为操作条件、边界和验收。
- **衔接**：让工作台规则能指导行动并被检查。
- **为什么有用**：位于自然语言要求到操作约束的转换层。规则写清适用条件和检查方式，才能同时指导执行者和最终验证者。
- **建议练习**：将三条模糊规则改成可判断的条件与证据。

入口：[中文教材](../14-agent-engineering/33-instructions-as-executable-constraints/docs/zh.md) · [原课代码](../14-agent-engineering/33-instructions-as-executable-constraints/code/) · [CoderPad](../14-agent-engineering/33-instructions-as-executable-constraints/coderpad/README.md) · [分关练习](../14-agent-engineering/33-instructions-as-executable-constraints/exam/README.md) · [课后测验](../14-agent-engineering/33-instructions-as-executable-constraints/quiz/quiz.md)

### 14.34 [仓库记忆与持久状态](../14-agent-engineering/34-repo-memory-and-state/docs/en.md) — Repo Memory and Durable State

- **掌握**：区分长期事实、任务进度和聊天记录。
- **衔接**：解决跨会话丢失上下文与过期记忆问题。
- **为什么有用**：位于跨会话的信息持久化层。仓库事实与任务状态保存后，Agent 才能在上下文中断后继续工作，并发现信息已经过期。
- **建议练习**：设计状态记录，保存来源、更新时间和下一步。

入口：[中文教材](../14-agent-engineering/34-repo-memory-and-state/docs/zh.md) · [原课代码](../14-agent-engineering/34-repo-memory-and-state/code/) · [CoderPad](../14-agent-engineering/34-repo-memory-and-state/coderpad/README.md) · [分关练习](../14-agent-engineering/34-repo-memory-and-state/exam/README.md) · [课后测验](../14-agent-engineering/34-repo-memory-and-state/quiz/quiz.md)

### 14.35 [Agent 初始化脚本](../14-agent-engineering/35-initialization-scripts/docs/en.md) — Initialization Scripts for Agents

- **掌握**：理解环境自检、依赖准备和稳定启动。
- **衔接**：减少每次会话重复探索与环境差异。
- **为什么有用**：位于会话启动与可运行环境之间。自动检查重复前置工作，有助于减少环境差异，也能让失败在正式修改前被发现。
- **建议练习**：列出可重复初始化步骤，检查重复运行的结果。

入口：[中文教材](../14-agent-engineering/35-initialization-scripts/docs/zh.md) · [原课代码](../14-agent-engineering/35-initialization-scripts/code/) · [CoderPad](../14-agent-engineering/35-initialization-scripts/coderpad/README.md) · [分关练习](../14-agent-engineering/35-initialization-scripts/exam/README.md) · [课后测验](../14-agent-engineering/35-initialization-scripts/quiz/quiz.md)

## 合同、验证、审查与交接

### 14.36 [任务范围合同](../14-agent-engineering/36-scope-contracts/docs/en.md) — Scope Contracts and Task Boundaries

- **掌握**：明确允许修改、交付物、非目标与验收。
- **衔接**：把工作台规则落实到单次任务。
- **为什么有用**：位于任务授权范围与验收条件的合同层。明确交付物和非目标，能减少范围漂移，并为审查者提供判断完成的依据。
- **建议练习**：给一个改动写范围合同，检查扩大范围的触发条件。

入口：[中文教材](../14-agent-engineering/36-scope-contracts/docs/zh.md) · [原课代码](../14-agent-engineering/36-scope-contracts/code/) · [CoderPad](../14-agent-engineering/36-scope-contracts/coderpad/README.md) · [分关练习](../14-agent-engineering/36-scope-contracts/exam/README.md) · [课后测验](../14-agent-engineering/36-scope-contracts/quiz/quiz.md)

### 14.37 [运行时反馈闭环](../14-agent-engineering/37-runtime-feedback-loops/docs/en.md) — Runtime Feedback Loops

- **掌握**：区分即时运行反馈和事后遥测记录。
- **衔接**：让执行过程及时发现错误，而非只在结束后复盘。
- **为什么有用**：位于行动到下一步决策的反馈层。编译、测试和运行结果需要及时进入控制流程，才有机会在错误继续传播前改变行动。
- **建议练习**：定义一个反馈信号及它如何改变下一步动作。

入口：[中文教材](../14-agent-engineering/37-runtime-feedback-loops/docs/zh.md) · [原课代码](../14-agent-engineering/37-runtime-feedback-loops/code/) · [CoderPad](../14-agent-engineering/37-runtime-feedback-loops/coderpad/README.md) · [分关练习](../14-agent-engineering/37-runtime-feedback-loops/exam/README.md) · [课后测验](../14-agent-engineering/37-runtime-feedback-loops/quiz/quiz.md)

### 14.38 [验证关卡](../14-agent-engineering/38-verification-gates/docs/en.md) — Verification Gates

- **掌握**：把验收写成对产物可重复执行的检查。
- **衔接**：为范围合同和反馈提供确定性完成标准。
- **为什么有用**：位于任务结束前的确定性验收层。关卡让完成状态依赖真实产物与行为，减少只根据 Agent 自述判断成功的问题。
- **建议练习**：设计通过与失败样例，确保关卡检查的是实际行为。

入口：[中文教材](../14-agent-engineering/38-verification-gates/docs/zh.md) · [原课代码](../14-agent-engineering/38-verification-gates/code/) · [CoderPad](../14-agent-engineering/38-verification-gates/coderpad/README.md) · [分关练习](../14-agent-engineering/38-verification-gates/exam/README.md) · [课后测验](../14-agent-engineering/38-verification-gates/quiz/quiz.md)

### 14.39 [独立 Reviewer](../14-agent-engineering/39-reviewer-agent/docs/en.md) — Reviewer Agent: Separate Builder from Marker

- **掌握**：理解构建与审查的职责及证据交付。
- **衔接**：在验证关卡之上加入独立检查。
- **为什么有用**：位于实现与质量判断的独立审查层。不同职责和证据输入可以帮助发现构建过程遗漏的假设、范围偏差与测试盲点。
- **建议练习**：给审查者提供 diff、验收条件和复现命令。

入口：[中文教材](../14-agent-engineering/39-reviewer-agent/docs/zh.md) · [原课代码](../14-agent-engineering/39-reviewer-agent/code/) · [CoderPad](../14-agent-engineering/39-reviewer-agent/coderpad/README.md) · [分关练习](../14-agent-engineering/39-reviewer-agent/exam/README.md) · [课后测验](../14-agent-engineering/39-reviewer-agent/quiz/quiz.md)

### 14.40 [多会话交接](../14-agent-engineering/40-multi-session-handoff/docs/en.md) — Multi-Session Handoff

- **掌握**：保存当前状态、证据、阻塞项和明确下一步。
- **衔接**：连接仓库记忆与恢复，减少重复劳动。
- **为什么有用**：位于长任务跨会话协作的交接层。交接包把当前状态和下一步写清，使继续执行不依赖完整聊天记录或口头解释。
- **建议练习**：关闭对话后只读交接包，检查是否能继续任务。

入口：[中文教材](../14-agent-engineering/40-multi-session-handoff/docs/zh.md) · [原课代码](../14-agent-engineering/40-multi-session-handoff/code/) · [CoderPad](../14-agent-engineering/40-multi-session-handoff/coderpad/README.md) · [分关练习](../14-agent-engineering/40-multi-session-handoff/exam/README.md) · [课后测验](../14-agent-engineering/40-multi-session-handoff/quiz/quiz.md)

### 14.41 [真实仓库上的工作台](../14-agent-engineering/41-workbench-for-real-repos/docs/en.md) — The Workbench on a Real Repo

- **掌握**：整合规则、状态、初始化、合同、反馈和验收。
- **衔接**：将单独设计的工作台组件放进完整项目。
- **为什么有用**：位于工作台机制的集成验证层。真实仓库会暴露路径、依赖与任务边界问题，能检查各控制组件是否确实协同工作。
- **建议练习**：选一个小改动，从任务领取走到验证和交接。

入口：[中文教材](../14-agent-engineering/41-workbench-for-real-repos/docs/zh.md) · [原课代码](../14-agent-engineering/41-workbench-for-real-repos/code/) · [CoderPad](../14-agent-engineering/41-workbench-for-real-repos/coderpad/README.md) · [分关练习](../14-agent-engineering/41-workbench-for-real-repos/exam/README.md) · [课后测验](../14-agent-engineering/41-workbench-for-real-repos/quiz/quiz.md)

### 14.42 [可复用工作台包](../14-agent-engineering/42-agent-workbench-capstone/docs/en.md) — Capstone: Ship a Reusable Agent Workbench Pack

- **掌握**：理解打包、配置边界、使用说明与迁移验证。
- **衔接**：把真实仓库实践整理成可移植产物。
- **为什么有用**：位于 Agent 工程流程的复用与交付层。打包后需要区分通用规则和项目配置，避免把某仓库的隐含假设带到其他项目。
- **建议练习**：在另一小项目检查路径、命令和默认假设。

入口：[中文教材](../14-agent-engineering/42-agent-workbench-capstone/docs/zh.md) · [原课代码](../14-agent-engineering/42-agent-workbench-capstone/code/) · [CoderPad](../14-agent-engineering/42-agent-workbench-capstone/coderpad/README.md) · [分关练习](../14-agent-engineering/42-agent-workbench-capstone/exam/README.md) · [课后测验](../14-agent-engineering/42-agent-workbench-capstone/quiz/quiz.md)

## 任务框定、计划与委派

### 14.43 [写代码前界定任务](../14-agent-engineering/43-frame-the-task-before-code/docs/en.md) — Frame the Task Before the Agent Writes Code

- **掌握**：明确目标行为、约束、未知项和完成证据。
- **衔接**：在工作台执行前补足任务理解。
- **为什么有用**：位于用户需求到可执行任务的前置分析层。先明确行为、边界和未知项，可以减少在错误问题上快速实现大量代码。
- **建议练习**：将一条模糊请求改成可验证的任务描述。

入口：[中文教材](../14-agent-engineering/43-frame-the-task-before-code/docs/zh.md) · [原课代码](../14-agent-engineering/43-frame-the-task-before-code/code/) · [CoderPad](../14-agent-engineering/43-frame-the-task-before-code/coderpad/README.md) · [分关练习](../14-agent-engineering/43-frame-the-task-before-code/exam/README.md) · [课后测验](../14-agent-engineering/43-frame-the-task-before-code/quiz/quiz.md)

### 14.44 [有证据的执行计划](../14-agent-engineering/44-plan-from-evidence/docs/en.md) — Build an Evidence-Backed Execution Plan

- **掌握**：把任务分成有依赖、输入和证明的工作项。
- **衔接**：将任务框定转成可跟踪的执行顺序。
- **为什么有用**：位于任务框定到工程执行的计划层。每步带输入、依据和完成证明，便于发现依赖缺口，也方便追踪进度与恢复。
- **建议练习**：为每步标出依据与验收，检查未验证假设。

入口：[中文教材](../14-agent-engineering/44-plan-from-evidence/docs/zh.md) · [原课代码](../14-agent-engineering/44-plan-from-evidence/code/) · [CoderPad](../14-agent-engineering/44-plan-from-evidence/coderpad/README.md) · [分关练习](../14-agent-engineering/44-plan-from-evidence/exam/README.md) · [课后测验](../14-agent-engineering/44-plan-from-evidence/quiz/quiz.md)

### 14.45 [委派、隔离与合并合同](../14-agent-engineering/45-delegate-with-isolation/docs/en.md) — Delegate Agent Work with Isolation and Merge Contracts

- **掌握**：判断子任务独立性，定义产物和集成责任。
- **衔接**：在计划明确后决定是否值得并行委派。
- **为什么有用**：位于并行开发的资源与集成管理层。委派的收益取决于独立性，隔离和合并合同则处理共享文件、冲突与最终验收。
- **建议练习**：模拟两个工作分支，检查共享文件冲突和合并验收。

入口：[中文教材](../14-agent-engineering/45-delegate-with-isolation/docs/zh.md) · [原课代码](../14-agent-engineering/45-delegate-with-isolation/code/) · [CoderPad](../14-agent-engineering/45-delegate-with-isolation/coderpad/README.md) · [分关练习](../14-agent-engineering/45-delegate-with-isolation/exam/README.md) · [课后测验](../14-agent-engineering/45-delegate-with-isolation/quiz/quiz.md)

### 14.46 [把纠正转为系统改进](../14-agent-engineering/46-turn-feedback-into-system/docs/en.md) — Turn Every Agent Correction into a System Improvement

- **掌握**：将重复错误转为规则、自动检查或环境修复。
- **衔接**：闭合工作台学习循环，减少相同纠正再次发生。
- **为什么有用**：位于 Agent 工作方式的持续改进层。把重复纠正转成规则或检查，能让后续任务依靠系统控制保持正确，而非反复提醒。
- **建议练习**：从一次纠正提炼最小控制，并设计防回归样例。

入口：[中文教材](../14-agent-engineering/46-turn-feedback-into-system/docs/zh.md) · [原课代码](../14-agent-engineering/46-turn-feedback-into-system/code/) · [CoderPad](../14-agent-engineering/46-turn-feedback-into-system/coderpad/README.md) · [分关练习](../14-agent-engineering/46-turn-feedback-into-system/exam/README.md) · [课后测验](../14-agent-engineering/46-turn-feedback-into-system/quiz/quiz.md)

## 产品结果、验证切片与反馈

### 14.47 [先定义结果再选产物](../14-agent-engineering/47-outcomes-before-output/docs/en.md) — Define the Outcome Before You Choose the Output

- **掌握**：区分用户行为改善与要制作的功能。
- **衔接**：开启产品判断分支，决定工作台应该执行什么。
- **为什么有用**：位于 AI 产品的问题与价值定义层。先说明希望用户行为发生什么变化，再选功能，才能避免交付产物与实际目标脱节。
- **建议练习**：把功能请求改写为目标用户、场景和预期变化。

入口：[中文教材](../14-agent-engineering/47-outcomes-before-output/docs/zh.md) · [原课代码](../14-agent-engineering/47-outcomes-before-output/code/) · [CoderPad](../14-agent-engineering/47-outcomes-before-output/coderpad/README.md) · [分关练习](../14-agent-engineering/47-outcomes-before-output/exam/README.md) · [课后测验](../14-agent-engineering/47-outcomes-before-output/quiz/quiz.md)

### 14.48 [发现实际工作流程](../14-agent-engineering/48-discover-the-real-workflow/docs/en.md) — Discover the Workflow People Actually Perform

- **掌握**：理解真实步骤、参与者、等待和证据。
- **衔接**：用当前行为验证结果目标，避免凭空设计流程。
- **为什么有用**：位于产品发现与流程证据收集层。AI 功能要嵌入已有工作，理解等待、交接和返工，才知道模型能力应该放在哪一步。
- **建议练习**：记录一条现有流程，标出耗时和频繁返工点。

入口：[中文教材](../14-agent-engineering/48-discover-the-real-workflow/docs/zh.md) · [原课代码](../14-agent-engineering/48-discover-the-real-workflow/code/) · [CoderPad](../14-agent-engineering/48-discover-the-real-workflow/coderpad/README.md) · [分关练习](../14-agent-engineering/48-discover-the-real-workflow/exam/README.md) · [课后测验](../14-agent-engineering/48-discover-the-real-workflow/quiz/quiz.md)

### 14.49 [假设与风险排序](../14-agent-engineering/49-map-assumptions-and-risk/docs/en.md) — Map Assumptions and Resolve the Riskiest One First

- **掌握**：将需求拆成价值、可行性和使用行为假设。
- **衔接**：从流程证据中找出最影响决策的未知。
- **为什么有用**：位于方案投入前的风险判断层。把价值、使用和技术假设拆开，可以优先验证最可能推翻方案的未知项。
- **建议练习**：列出关键假设，按不确定性和后果选首个验证点。

入口：[中文教材](../14-agent-engineering/49-map-assumptions-and-risk/docs/zh.md) · [原课代码](../14-agent-engineering/49-map-assumptions-and-risk/code/) · [CoderPad](../14-agent-engineering/49-map-assumptions-and-risk/coderpad/README.md) · [分关练习](../14-agent-engineering/49-map-assumptions-and-risk/exam/README.md) · [课后测验](../14-agent-engineering/49-map-assumptions-and-risk/quiz/quiz.md)

### 14.50 [最小有效验证切片](../14-agent-engineering/50-choose-the-smallest-testable-slice/docs/en.md) — Choose the Smallest Slice That Can Change the Decision

- **掌握**：用最小实现回答一个明确的决策问题。
- **衔接**：承接假设排序，约束功能范围和学习目标。
- **为什么有用**：位于需求验证到最小实现的范围选择层。切片以能改变决策的证据为目标，帮助控制投入并避免把试验扩成完整产品。
- **建议练习**：定义一周内可验证的切片及继续或停止条件。

入口：[中文教材](../14-agent-engineering/50-choose-the-smallest-testable-slice/docs/zh.md) · [原课代码](../14-agent-engineering/50-choose-the-smallest-testable-slice/code/) · [CoderPad](../14-agent-engineering/50-choose-the-smallest-testable-slice/coderpad/README.md) · [分关练习](../14-agent-engineering/50-choose-the-smallest-testable-slice/exam/README.md) · [课后测验](../14-agent-engineering/50-choose-the-smallest-testable-slice/quiz/quiz.md)

### 14.51 [保留判断空间的规格](../14-agent-engineering/51-write-specifications-that-preserve-judgment/docs/en.md) — Write Specifications That Preserve Judgment

- **掌握**：区分结果、不变量、示例、非目标和证明。
- **衔接**：把验证切片转成可执行且不过度限定实现的规格。
- **为什么有用**：位于产品意图与 Agent 实现之间的规格层。结果、不变量和例子保留关键判断，同时给实现留出根据证据选择方案的空间。
- **建议练习**：为一个行为写正例、反例和不可破坏的约束。

入口：[中文教材](../14-agent-engineering/51-write-specifications-that-preserve-judgment/docs/zh.md) · [原课代码](../14-agent-engineering/51-write-specifications-that-preserve-judgment/code/) · [CoderPad](../14-agent-engineering/51-write-specifications-that-preserve-judgment/coderpad/README.md) · [分关练习](../14-agent-engineering/51-write-specifications-that-preserve-judgment/exam/README.md) · [课后测验](../14-agent-engineering/51-write-specifications-that-preserve-judgment/quiz/quiz.md)

### 14.52 [提前设计成功指标](../14-agent-engineering/52-design-success-metrics/docs/en.md) — Design Success Metrics Before the Result Exists

- **掌握**：从目标推导指标、基线和解释规则。
- **衔接**：让产品和工程验收在结果出现前有共同口径。
- **为什么有用**：位于产品结果的提前测量设计层。指标在结果出现前定义，能减少事后挑选有利数字，并让工程验收与用户价值对应。
- **建议练习**：定义一个主指标与一个护栏，检查能否被轻易刷高。

入口：[中文教材](../14-agent-engineering/52-design-success-metrics/docs/zh.md) · [原课代码](../14-agent-engineering/52-design-success-metrics/code/) · [CoderPad](../14-agent-engineering/52-design-success-metrics/coderpad/README.md) · [分关练习](../14-agent-engineering/52-design-success-metrics/exam/README.md) · [课后测验](../14-agent-engineering/52-design-success-metrics/quiz/quiz.md)

### 14.53 [原型、试点与生产](../14-agent-engineering/53-prototype-pilot-or-production/docs/en.md) — Choose Prototype, Pilot, or Production Deliberately

- **掌握**：根据未知、受众、数据和后果选择建设阶段。
- **衔接**：决定验证切片需要多大工程投入。
- **为什么有用**：位于实验阶段与工程投入的匹配层。原型、试点和生产服务不同未知与后果，阶段选择决定需要哪些质量和运行证据。
- **建议练习**：给同一想法写三个阶段的范围与升级条件。

入口：[中文教材](../14-agent-engineering/53-prototype-pilot-or-production/docs/zh.md) · [原课代码](../14-agent-engineering/53-prototype-pilot-or-production/code/) · [CoderPad](../14-agent-engineering/53-prototype-pilot-or-production/coderpad/README.md) · [分关练习](../14-agent-engineering/53-prototype-pilot-or-production/exam/README.md) · [课后测验](../14-agent-engineering/53-prototype-pilot-or-production/quiz/quiz.md)

### 14.54 [有负责人的反馈机制](../14-agent-engineering/54-build-the-feedback-ratchet/docs/en.md) — Build a Feedback Ratchet with Ownership and Retirement

- **掌握**：把事件、评估和用户反馈转成可关闭的改进项。
- **衔接**：连接产品指标与工作台纠正，形成持续学习。
- **为什么有用**：位于上线反馈到长期流程改进的闭环层。反馈需要负责人、验收和退役条件，才不会只堆积问题或永久增加无效规则。
- **建议练习**：为一条反馈指定负责人、验收和规则退役条件。

入口：[中文教材](../14-agent-engineering/54-build-the-feedback-ratchet/docs/zh.md) · [原课代码](../14-agent-engineering/54-build-the-feedback-ratchet/code/) · [CoderPad](../14-agent-engineering/54-build-the-feedback-ratchet/coderpad/README.md) · [分关练习](../14-agent-engineering/54-build-the-feedback-ratchet/exam/README.md) · [课后测验](../14-agent-engineering/54-build-the-feedback-ratchet/quiz/quiz.md)
