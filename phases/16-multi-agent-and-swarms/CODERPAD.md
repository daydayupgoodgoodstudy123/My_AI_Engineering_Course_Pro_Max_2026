# 16-multi-agent-and-swarms：CoderPad 练习

本章 25 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [Why Multi-Agent?](01-why-multi-agent/coderpad/README.md) | 并行加速上限 | Token 成本计费 |
| 02 | [Heritage of FIPA-ACL and Speech Acts](02-fipa-acl-heritage/coderpad/README.md) | JSON-RPC 请求包 | 配置合同校验 |
| 03 | [Communication Protocols](03-communication-protocols/coderpad/README.md) | JSON-RPC 请求包 | 幂等请求账本 |
| 04 | [The Multi-Agent Primitive Model](04-primitive-model/coderpad/README.md) | 合法状态转换 | 角色与工具选择 |
| 05 | [Supervisor / Orchestrator-Worker Pattern](05-supervisor-orchestrator-pattern/coderpad/README.md) | 依赖计划拓扑排序 | 优先级任务调度 |
| 06 | [Hierarchical Architecture and Its Failure Mode](06-hierarchical-architecture/coderpad/README.md) | 依赖计划拓扑排序 | 可验证任务交接 |
| 07 | [Society of Mind and Multi-Agent Debate](07-society-of-mind-debate/coderpad/README.md) | Quorum 与重复选票 | 声明与证据绑定 |
| 08 | [Role Specialization — Planner, Critic, Executor, Verifier](08-role-specialization/coderpad/README.md) | 角色与工具选择 | 独立权限与批准 |
| 09 | [Parallel / Swarm / Networked Architectures](09-parallel-swarm-networks/coderpad/README.md) | 均衡参数分片 | 集体归约 |
| 10 | [Group Chat and Speaker Selection](10-group-chat-speaker-selection/coderpad/README.md) | 优先级任务调度 | 角色与工具选择 |
| 11 | [Handoffs and Routines — Stateless Orchestration](11-handoffs-and-routines/coderpad/README.md) | 可验证任务交接 | 合法状态转换 |
| 12 | [A2A — The Agent-to-Agent Protocol](12-a2a-protocol/coderpad/README.md) | 合法状态转换 | JSON-RPC 请求包 |
| 13 | [Shared Memory and Blackboard Patterns](13-shared-memory-blackboard/coderpad/README.md) | 有界记忆保留 | TTL 缓存回放 |
| 14 | [Consensus and Byzantine Fault Tolerance for Agents](14-consensus-and-bft/coderpad/README.md) | Quorum 与重复选票 | 分类混淆矩阵指标 |
| 15 | [Voting, Self-Consistency, and Debate Topology](15-voting-debate-topology/coderpad/README.md) | 集成投票与并列 | Quorum 与重复选票 |
| 16 | [Negotiation and Bargaining](16-negotiation-bargaining/coderpad/README.md) | 多目标候选筛选 | 成本预算治理 |
| 17 | [Generative Agents and Emergent Simulation](17-generative-agents-simulation/coderpad/README.md) | 马尔可夫状态分布 | 角色与工具选择 |
| 18 | [Theory of Mind and Emergent Coordination](18-theory-of-mind-coordination/coderpad/README.md) | 贝叶斯更新 | 角色与工具选择 |
| 19 | [Swarm Optimization for LLMs (PSO, ACO)](19-swarm-optimization-pso-aco/coderpad/README.md) | 稀疏路由 Top-K | 多目标候选筛选 |
| 20 | [MARL — MADDPG, QMIX, MAPPO](20-marl-maddpg-qmix-mappo/coderpad/README.md) | Q-learning 更新 | Quorum 与重复选票 |
| 21 | [Agent Economies, Token Incentives, Reputation](21-agent-economies/coderpad/README.md) | 成本预算治理 | 幂等请求账本 |
| 22 | [Production Scaling — Queues, Checkpoints, Durability](22-production-scaling-queues-checkpoints/coderpad/README.md) | 优先级任务调度 | 幂等请求账本 |
| 23 | [Failure Modes — MAST, Groupthink, Monoculture, Cascading Errors](23-failure-modes-mast-groupthink/coderpad/README.md) | 评估锚点漂移 | Quorum 与重复选票 |
| 24 | [Evaluation and Coordination Benchmarks](24-evaluation-coordination-benchmarks/coderpad/README.md) | 分类混淆矩阵指标 | 分位数与 Goodput |
| 25 | [Case Studies and the 2026 State of the Art](25-case-studies-2026-sota/coderpad/README.md) | 声明与证据绑定 | 风险登记与排序 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
