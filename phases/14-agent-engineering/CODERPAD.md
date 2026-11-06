# 14-agent-engineering：CoderPad 练习

本章 54 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
核心 6 cases、加分 2 cases。题目是原课程中的一个编码切面，不要求运行完整训练、云服务或 GPU。
相同基础 kernel 会在相关课程复用；请在复盘中区分“未见题”与“重复练习”。
运行方法：进入任一项目的 `coderpad/`，阅读 README/PROMPT，再执行：

```bash
python3 run_tests.py --list
python3 run_tests.py --core
```

初始失败是 TODO 的正常起点；计时结束后才打开 solution 或使用 `--solution`。
面试官材料、评分与复盘模板均在每套目录；计时器自行设置。

| 课号 | 主题与题目入口 | 核心 | 加分 |
| --- | --- | --- | --- |
| 01 | [The Agent Loop: Observe, Think, Act](01-the-agent-loop/coderpad/README.md) | 合法状态转换 | 成本预算治理 |
| 02 | [ReWOO and Plan-and-Execute: Decoupled Planning](02-rewoo-plan-and-execute/coderpad/README.md) | 依赖计划拓扑排序 | 上下文预算装箱 |
| 03 | [Reflexion: Verbal Reinforcement Learning](03-reflexion-verbal-rl/coderpad/README.md) | 有界记忆保留 | 评估锚点漂移 |
| 04 | [Tree of Thoughts and LATS: Deliberate Search](04-tree-of-thoughts-lats/coderpad/README.md) | 最短路径搜索 | 探索与利用调度 |
| 05 | [Self-Refine and CRITIC: Iterative Output Improvement](05-self-refine-and-critic/coderpad/README.md) | 证据分层 Gate | 评估锚点漂移 |
| 06 | [Tool Use and Function Calling](06-tool-use-and-function-calling/coderpad/README.md) | 工具参数校验 | 幂等请求账本 |
| 07 | [Agent Memory — Virtual Context and Memory Paging](07-memory-virtual-context-memgpt/coderpad/README.md) | 有界记忆保留 | 上下文预算装箱 |
| 08 | [Memory Blocks and Sleep-Time Compute](08-memory-blocks-sleep-time-compute/coderpad/README.md) | 有界记忆保留 | 内容指纹与漂移 |
| 09 | [Hybrid Memory: Vector + Graph + KV](09-hybrid-memory-mem0/coderpad/README.md) | TTL 缓存回放 | 倒数排名融合 |
| 10 | [Skill Libraries and Lifelong Learning (Voyager)](10-skill-libraries-voyager/coderpad/README.md) | 角色与工具选择 | 内容指纹与漂移 |
| 11 | [Planning with HTN and Evolutionary Search](11-planning-htn-and-evolutionary/coderpad/README.md) | 依赖计划拓扑排序 | 多目标候选筛选 |
| 12 | [Anthropic's Workflow Patterns: Simple Over Complex](12-anthropic-workflow-patterns/coderpad/README.md) | 依赖计划拓扑排序 | 优先级任务调度 |
| 13 | [Stateful Graph Orchestration — Durable Execution and Checkpoints](13-langgraph-stateful-graphs/coderpad/README.md) | 合法状态转换 | 幂等请求账本 |
| 14 | [The Actor Model for Agents — Async Messages and Typed Runtimes](14-autogen-actor-model/coderpad/README.md) | 优先级任务调度 | JSON-RPC 请求包 |
| 15 | [Role-Based Agent Teams — Roles, Tasks, Processes](15-crewai-role-based-crews/coderpad/README.md) | 角色与工具选择 | 可验证任务交接 |
| 16 | [OpenAI Agents SDK: Handoffs, Guardrails, Tracing](16-openai-agents-sdk/coderpad/README.md) | 可验证任务交接 | 独立权限与批准 |
| 17 | [The Harness as a Library — Subagents and Session Store](17-claude-agent-sdk/coderpad/README.md) | 独立权限与批准 | 词法路径包含边界 |
| 18 | [Production Agent Runtimes — Fast Instantiation and Typed Workflows](18-agno-and-mastra-runtimes/coderpad/README.md) | 合法状态转换 | 耗时聚合 |
| 19 | [Benchmarks: SWE-bench, GAIA, AgentBench](19-benchmarks-swebench-gaia/coderpad/README.md) | 分类混淆矩阵指标 | 声明与证据绑定 |
| 20 | [Benchmarks: WebArena and OSWorld](20-benchmarks-webarena-osworld/coderpad/README.md) | 独立权限与批准 | 分位数与 Goodput |
| 21 | [Computer Use: Claude, OpenAI CUA, Gemini](21-computer-use-agents/coderpad/README.md) | 独立权限与批准 | 边框 IoU |
| 22 | [Voice Agents: Pipecat and LiveKit](22-voice-agents-pipecat-livekit/coderpad/README.md) | 能量 VAD 边界 | 合法状态转换 |
| 23 | [OpenTelemetry GenAI Semantic Conventions](23-otel-genai-conventions/coderpad/README.md) | 耗时聚合 | 结构化日志脱敏 |
| 24 | [Agent Observability: Langfuse, Phoenix, Opik](24-agent-observability-platforms/coderpad/README.md) | 分位数与 Goodput | Token 成本计费 |
| 25 | [Multi-Agent Debate and Collaboration](25-multi-agent-debate/coderpad/README.md) | Quorum 与重复选票 | 声明与证据绑定 |
| 26 | [Failure Modes: Why Agents Break](26-failure-modes-agentic/coderpad/README.md) | 有限指数退避 | 合法状态转换 |
| 27 | [Prompt Injection and the PVE Defense](27-prompt-injection-defense/coderpad/README.md) | 独立权限与批准 | 声明与证据绑定 |
| 28 | [Orchestration Patterns: Supervisor, Swarm, Hierarchical](28-orchestration-patterns/coderpad/README.md) | 依赖计划拓扑排序 | 优先级任务调度 |
| 29 | [Production Runtimes: Queue, Event, Cron](29-production-runtimes/coderpad/README.md) | 幂等请求账本 | 内容指纹与漂移 |
| 30 | [Eval-Driven Agent Development](30-eval-driven-agent-development/coderpad/README.md) | 证据分层 Gate | 分类混淆矩阵指标 |
| 31 | [Agent Workbench Engineering: Why Capable Models Still Fail](31-agent-workbench-why-models-fail/coderpad/README.md) | 配置合同校验 | 声明与证据绑定 |
| 32 | [The Minimal Agent Workbench](32-minimal-agent-workbench/coderpad/README.md) | 合法状态转换 | 证据分层 Gate |
| 33 | [Agent Instructions as Executable Constraints](33-instructions-as-executable-constraints/coderpad/README.md) | 配置合同校验 | 独立权限与批准 |
| 34 | [Repo Memory and Durable State](34-repo-memory-and-state/coderpad/README.md) | 有界记忆保留 | 内容指纹与漂移 |
| 35 | [Initialization Scripts for Agents](35-initialization-scripts/coderpad/README.md) | 开发环境探针汇总 | 精确命令策略 |
| 36 | [Scope Contracts and Task Boundaries](36-scope-contracts/coderpad/README.md) | 配置合同校验 | 词法路径包含边界 |
| 37 | [Runtime Feedback Loops](37-runtime-feedback-loops/coderpad/README.md) | 耗时聚合 | 证据分层 Gate |
| 38 | [Verification Gates](38-verification-gates/coderpad/README.md) | 证据分层 Gate | 内容指纹与漂移 |
| 39 | [Reviewer Agent: Separate Builder from Marker](39-reviewer-agent/coderpad/README.md) | 声明与证据绑定 | Git 变更分类 |
| 40 | [Multi-Session Handoff](40-multi-session-handoff/coderpad/README.md) | 可验证任务交接 | 有界记忆保留 |
| 41 | [The Workbench on a Real Repo](41-workbench-for-real-repos/coderpad/README.md) | 内容指纹与漂移 | Git 变更分类 |
| 42 | [Capstone: Ship a Reusable Agent Workbench Pack](42-agent-workbench-capstone/coderpad/README.md) | 依赖计划拓扑排序 | 证据分层 Gate |
| 43 | [Frame the Task Before the Agent Writes Code](43-frame-the-task-before-code/coderpad/README.md) | 配置合同校验 | 风险登记与排序 |
| 44 | [Build an Evidence-Backed Execution Plan](44-plan-from-evidence/coderpad/README.md) | 声明与证据绑定 | 依赖计划拓扑排序 |
| 45 | [Delegate Agent Work with Isolation and Merge Contracts](45-delegate-with-isolation/coderpad/README.md) | 均衡参数分片 | 独立权限与批准 |
| 46 | [Turn Every Agent Correction into a System Improvement](46-turn-feedback-into-system/coderpad/README.md) | 评估锚点漂移 | 内容指纹与漂移 |
| 47 | [Define the Outcome Before You Choose the Output](47-outcomes-before-output/coderpad/README.md) | 证据分层 Gate | 耗时聚合 |
| 48 | [Discover the Workflow People Actually Perform](48-discover-the-real-workflow/coderpad/README.md) | 依赖计划拓扑排序 | 可验证任务交接 |
| 49 | [Map Assumptions and Resolve the Riskiest One First](49-map-assumptions-and-risk/coderpad/README.md) | 风险登记与排序 | 声明与证据绑定 |
| 50 | [Choose the Smallest Slice That Can Change the Decision](50-choose-the-smallest-testable-slice/coderpad/README.md) | 上下文预算装箱 | 成本预算治理 |
| 51 | [Write Specifications That Preserve Judgment](51-write-specifications-that-preserve-judgment/coderpad/README.md) | 配置合同校验 | 证据分层 Gate |
| 52 | [Design Success Metrics Before the Result Exists](52-design-success-metrics/coderpad/README.md) | 分类混淆矩阵指标 | 分位数与 Goodput |
| 53 | [Choose Prototype, Pilot, or Production Deliberately](53-prototype-pilot-or-production/coderpad/README.md) | 证据分层 Gate | 声明与证据绑定 |
| 54 | [Build a Feedback Ratchet with Ownership and Retirement](54-build-the-feedback-ratchet/coderpad/README.md) | 评估锚点漂移 | 证据分层 Gate |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
