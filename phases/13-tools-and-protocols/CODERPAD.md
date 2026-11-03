# Phase 13：CoderPad 面试试点

31 个小项目，每个项目的 `coderpad/` 与 `assets/`、`code/`、`docs/`、`notebook/` 同级。
每套 45 分钟，Python 3.10+ 标准库，离线 fake；不需要 API key 或安装包。
原创练习仅参考本地 Edison mock exams 的组织形式，不声称是真题或官方招聘标准。
课程相关协议格式使用本地课程快照和题目明确列出的简化合同，未对外部最新版本作认证。

## 现在开始

```bash
cd phases/13-tools-and-protocols/01-the-tool-interface/coderpad
python3 run_tests.py --list
python3 run_tests.py --core
```

从仓库根目录执行上面的 cd；其他位置可直接在对应 coderpad 目录打开终端。
先读该套 README 和英文 PROMPT，再开自己的 45 分钟计时器，只修改 starter/main.py。
初始失败是 TODO 的正常起点。参考答案在 solution/，计时后再打开。
所有测试均存本地，没有真正隐藏的评分服务器或强制倒计时。

## 建议练习顺序

- **第一轮打基础**：01 → 02 → 04 → 05 → 07。03 的流式与并发可在这之后做。
- **MCP 边界**：06 → 07 → 08 → 09 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 18 → 17。
- **工程组合**：19 → 20 → 21，再进入 23 综合题。
- **Skills 专项**：22 → 24 → 25 → 26 → 27。
- **进阶专项**：28 → 29 → 30 → 31；23 可最后重做综合复盘。

时间与难度尚未经真实候选人校准。核心 case 数不是难度分数，各套通过率不能直接横向比较。
建议每次只做一套，保留计时成绩与复盘成绩；需要陪练时可说：
“按第 02 套的 coderpad/INTERVIEWER.md 开始模拟面试，一次只问一个问题。”

## 全部题目

| 课号 | 面试题 | 建议难度 |
| --- | --- | --- |
| 01 | [有边界的工具执行器](01-the-tool-interface/coderpad/README.md) | 基础 |
| 02 | [统一不同模型的工具调用](02-function-calling-deep-dive/coderpad/README.md) | 基础到中等 |
| 03 | [重组交错的工具流](03-parallel-and-streaming-tool-calls/coderpad/README.md) | 中等 |
| 04 | [结构化提取的错误分层](04-structured-output/coderpad/README.md) | 基础 |
| 05 | [工具合同静态检查](05-tool-schema-design/coderpad/README.md) | 基础 |
| 06 | [独立 RPC 请求校验](06-mcp-fundamentals/coderpad/README.md) | 基础到中等 |
| 07 | [笔记工具服务](07-building-an-mcp-server/coderpad/README.md) | 基础到中等 |
| 08 | [合并与路由远端工具](08-building-an-mcp-client/coderpad/README.md) | 中等 |
| 09 | [传输层路由一致性](09-mcp-transports/coderpad/README.md) | 中等 |
| 10 | [资源、提示模板与私有缓存](10-mcp-resources-and-prompts/coderpad/README.md) | 基础 |
| 11 | [续传状态绑定与防篡改](11-mcp-sampling/coderpad/README.md) | 中等 |
| 12 | [路径边界与一次确认](12-mcp-roots-and-elicitation/coderpad/README.md) | 中等 |
| 13 | [持久化任务状态机](13-mcp-async-tasks/coderpad/README.md) | 中等 |
| 14 | [内嵌 App 消息边界](14-mcp-apps/coderpad/README.md) | 中等 |
| 15 | [工具描述漂移检测](15-mcp-security-tool-poisoning/coderpad/README.md) | 中等 |
| 16 | [授权凭证绑定](16-mcp-security-oauth-2-1/coderpad/README.md) | 中等 |
| 17 | [带策略的工具网关](17-mcp-gateways-and-registries/coderpad/README.md) | 中等 |
| 18 | [Token 缓存隔离与轮换](18-mcp-auth-production/coderpad/README.md) | 中等 |
| 19 | [Agent 任务生命周期](19-a2a-protocol/coderpad/README.md) | 中等 |
| 20 | [脱敏 Trace 与耗时统计](20-opentelemetry-genai/coderpad/README.md) | 基础到中等 |
| 21 | [有限回退的模型路由](21-llm-routing-layer/coderpad/README.md) | 中等 |
| 22 | [校验 Skill 包的基础合同](22-skills-and-agent-sdks/coderpad/README.md) | 基础到中等 |
| 23 | [有上限的工具生态编排](23-capstone-tool-ecosystem/coderpad/README.md) | 进阶 |
| 24 | [渐进加载与目录预算](24-skill-discovery-and-progressive-disclosure/coderpad/README.md) | 中等 |
| 25 | [Skill 显式调用与路由弃权](25-skill-invocation-and-routing/coderpad/README.md) | 中等 |
| 26 | [执行前权限策略](26-skill-permissions-sandboxes-and-trust/coderpad/README.md) | 中等 |
| 27 | [评估指标与发布门槛](27-skill-evals-packaging-and-portability/coderpad/README.md) | 中等 |
| 28 | [工具结果与内容合同](28-mcp-tool-contracts-and-content/coderpad/README.md) | 中等 |
| 29 | [保留最终结果的有界流控](29-mcp-reliability-cancellation-and-flow-control/coderpad/README.md) | 中等 |
| 30 | [准入 Pin 与回滚历史](30-mcp-registry-supply-chain-and-drift/coderpad/README.md) | 中等到进阶 |
| 31 | [完整证据驱动的发布检查](31-mcp-conformance-versioning-and-operations/coderpad/README.md) | 中等到进阶 |

## 目录内材料

- README.md / PROMPT.md：中文上手与英文输入输出合同。
- starter/main.py：学员 TODO；tests/：可见行为测试，可以额外添加自己的测试文件。
- run_tests.py：收集、过滤、核心/加分和独立参考实现选择。
- INTERVIEWER.md：澄清、分级提示、追问和原创人工评分标准。
- REVIEW_TEMPLATE.md：计时结果、卡点、提示次数与复盘结果分开记录。
- solution/：参考代码与中文解释；verification.txt / starter_baseline.txt：实跑证据。

包内 `python3 run_tests.py --solution` 不修改 starter。重复练习先另存自己的答案。
维护源文件和安全生成方式见 [生成器说明](../../scripts/coderpad_phase13/README.md)。
