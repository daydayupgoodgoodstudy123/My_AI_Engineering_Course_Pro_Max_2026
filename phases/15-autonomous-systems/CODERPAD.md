# 15-autonomous-systems：CoderPad 练习

本章 22 个项目已按第 13 章试点形式提供练习：45 分钟建议上限、Python 3.10+ 标准库、离线执行。
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
| 01 | [The Shift from Chatbots to Long-Horizon Agents](01-long-horizon-agents/coderpad/README.md) | 成本预算治理 | 合法状态转换 |
| 02 | [STaR, V-STaR, Quiet-STaR — Self-Taught Reasoning](02-star-family-reasoning/coderpad/README.md) | 折扣回报 | 声明与证据绑定 |
| 03 | [AlphaEvolve — Evolutionary Coding Agents](03-alphaevolve-evolutionary-coding/coderpad/README.md) | 多目标候选筛选 | 证据分层 Gate |
| 04 | [Darwin Godel Machine — Open-Ended Self-Modifying Agents](04-darwin-godel-machine/coderpad/README.md) | 探索与利用调度 | 内容指纹与漂移 |
| 05 | [AI Scientist v2 — Workshop-Level Autonomous Research](05-ai-scientist-v2/coderpad/README.md) | 依赖计划拓扑排序 | 声明与证据绑定 |
| 06 | [Automated Alignment Research (Anthropic AAR)](06-automated-alignment-research/coderpad/README.md) | 证据分层 Gate | 评估锚点漂移 |
| 07 | [Recursive Self-Improvement — Capability vs Alignment](07-recursive-self-improvement/coderpad/README.md) | 评估锚点漂移 | 证据分层 Gate |
| 08 | [Bounded Self-Improvement Designs](08-bounded-self-improvement/coderpad/README.md) | 成本预算治理 | 风险登记与排序 |
| 09 | [The Autonomous Coding Agent Landscape (2026)](09-coding-agent-landscape/coderpad/README.md) | 角色与工具选择 | 配置合同校验 |
| 10 | [Permission Modes for Autonomous Agents](10-claude-code-permission-modes/coderpad/README.md) | 独立权限与批准 | 精确命令策略 |
| 11 | [Browser Agents and Long-Horizon Web Tasks](11-browser-agents/coderpad/README.md) | 独立权限与批准 | 词法路径包含边界 |
| 12 | [Long-Running Background Agents: Durable Execution](12-durable-execution/coderpad/README.md) | 幂等请求账本 | 可验证任务交接 |
| 13 | [Action Budgets, Iteration Caps, and Cost Governors](13-cost-governors/coderpad/README.md) | 成本预算治理 | Token 成本计费 |
| 14 | [Kill Switches, Circuit Breakers, and Canary Tokens](14-kill-switches-canaries/coderpad/README.md) | 灰度发布判定 | 证据分层 Gate |
| 15 | [Human-in-the-Loop: Propose-Then-Commit](15-propose-then-commit/coderpad/README.md) | 证据分层 Gate | Git 变更分类 |
| 16 | [Checkpoints and Rollback](16-checkpoints-rollback/coderpad/README.md) | 内容指纹与漂移 | 评估锚点漂移 |
| 17 | [Constitutional AI and Rule Overrides](17-constitutional-ai/coderpad/README.md) | 分类信号合并 | 声明与证据绑定 |
| 18 | [Llama Guard and Input/Output Classification](18-llama-guard/coderpad/README.md) | 分类信号合并 | Expected Calibration Error |
| 19 | [Anthropic Responsible Scaling Policy v3.0](19-anthropic-rsp/coderpad/README.md) | 风险登记与排序 | 证据分层 Gate |
| 20 | [OpenAI Preparedness Framework and DeepMind Frontier Safety Framework](20-openai-preparedness-deepmind-fsf/coderpad/README.md) | 证据分层 Gate | 风险登记与排序 |
| 21 | [METR Time Horizons and External Capability Evaluation](21-metr-external-evaluation/coderpad/README.md) | Expected Calibration Error | 分类混淆矩阵指标 |
| 22 | [CAIS, CAISI, and Societal-Scale Risk](22-cais-caisi-societal-risk/coderpad/README.md) | 风险登记与排序 | 分组选择率差异 |

全课程入口：[CODERPAD_INDEX.md](../../CODERPAD_INDEX.md)。维护方式：[生成器说明](../../scripts/coderpad_curriculum/README.md)。
