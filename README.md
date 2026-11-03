# AI Engineering Course — Phase 13

个人学习仓库，当前先同步 **Phase 13: Tools & Protocols 的 31 节课程**。保留原来的 `phases/13-tools-and-protocols/` 目录结构，方便后续逐步加入完整课程。

课程原始内容来自 [rohitg00/ai-engineering-from-scratch](https://github.com/rohitg00/ai-engineering-from-scratch)，上游快照为 `5b5ab48cd63d7ae5b4002985d9ac9de4ed86c2c0`。本副本同时保留本地已有的中文翻译、代码讲解、测验、CoderPad 和分关 exam。原作者版权及 MIT 许可见 [LICENSE](LICENSE)。

## 如何学习

1. 手机阅读下面的中文讲义或代码讲解，每次理解一个输入输出，再完成一道测验。
2. 使用电脑或 GitHub Codespaces 时，运行演示，然后在 `coderpad/starter/main.py` 完成一个小功能并测试。
3. 准备好完整练习时，再做 45 分钟 CoderPad 或各课 `exam/` 的分关练习；独立计时期间先关闭 `solution/` 和 `INTERVIEWER.md`。

`code/` 是课堂实现；`coderpad/` 是单文件练习；`exam/` 是多模块分关练习；`outputs/` 是课程提供的可复用材料。题目和协议限制采用课程快照与各题明确规定的合同。

中文讲义为本地翻译稿，读不通时请对照英文；代码讲解与测验可辅助理解。`verification.txt` 和 baseline 文件是历史记录，不代表你本次已经运行或通过测试。

## 快速开始

从本仓库根目录运行，要求 Python 3.10+：

```bash
python3 --version
python3 phases/13-tools-and-protocols/02-function-calling-deep-dive/code/main.py

cd phases/13-tools-and-protocols/02-function-calling-deep-dive/coderpad
python3 run_tests.py --list
python3 run_tests.py --core
```

CoderPad 只依赖标准库，不需要 API key。初始 TODO 使核心测试失败是正常起点；只修改 `starter/main.py`，以 `PROMPT.md` 为准确题目要求。

分关 exam 使用 pytest。另开终端，从仓库根目录运行：

```bash
python3 -m pip install pytest
cd phases/13-tools-and-protocols/02-function-calling-deep-dive/exam
python3 -m pytest
```

默认关卡被 skip 锁定，按该课 `exam/使用说明.md` 逐关解锁；`skipped` 不代表完成。TypeScript 示例及真实宿主实验另需 Node.js 或对应宿主，详见各课说明。

## Phase 13

[阶段中文说明](phases/13-tools-and-protocols/README.zh.md) · [阶段英文说明](phases/13-tools-and-protocols/README.md) · [CoderPad 总入口](phases/13-tools-and-protocols/CODERPAD.md) · [学习路线](ROADMAP.md)

| 课号 | 课程 | 学习材料 | 编码练习 |
| --- | --- | --- | --- |
| 01 | The Tool Interface — Why Agents Need Structured I/O | [中文](phases/13-tools-and-protocols/01-the-tool-interface/docs/zh.md) · [English](phases/13-tools-and-protocols/01-the-tool-interface/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/01-the-tool-interface/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/01-the-tool-interface/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/01-the-tool-interface/exam/README.md) |
| 02 | Function Calling Deep Dive — OpenAI, Anthropic, Gemini | [中文](phases/13-tools-and-protocols/02-function-calling-deep-dive/docs/zh.md) · [English](phases/13-tools-and-protocols/02-function-calling-deep-dive/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/02-function-calling-deep-dive/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/02-function-calling-deep-dive/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/02-function-calling-deep-dive/exam/README.md) |
| 03 | Parallel Tool Calls and Streaming with Tools | [中文](phases/13-tools-and-protocols/03-parallel-and-streaming-tool-calls/docs/zh.md) · [English](phases/13-tools-and-protocols/03-parallel-and-streaming-tool-calls/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/03-parallel-and-streaming-tool-calls/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/03-parallel-and-streaming-tool-calls/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/03-parallel-and-streaming-tool-calls/exam/README.md) |
| 04 | Structured Output — JSON Schema, Pydantic, Zod, Constrained Decoding | [中文](phases/13-tools-and-protocols/04-structured-output/docs/zh.md) · [English](phases/13-tools-and-protocols/04-structured-output/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/04-structured-output/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/04-structured-output/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/04-structured-output/exam/README.md) |
| 05 | Tool Schema Design — Naming, Descriptions, Parameter Constraints | [中文](phases/13-tools-and-protocols/05-tool-schema-design/docs/zh.md) · [English](phases/13-tools-and-protocols/05-tool-schema-design/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/05-tool-schema-design/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/05-tool-schema-design/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/05-tool-schema-design/exam/README.md) |
| 06 | MCP Fundamentals: Stateless Requests and JSON-RPC | [中文](phases/13-tools-and-protocols/06-mcp-fundamentals/docs/zh.md) · [English](phases/13-tools-and-protocols/06-mcp-fundamentals/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/06-mcp-fundamentals/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/06-mcp-fundamentals/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/06-mcp-fundamentals/exam/README.md) |
| 07 | Building an MCP Server: Stateless Python and TypeScript | [中文](phases/13-tools-and-protocols/07-building-an-mcp-server/docs/zh.md) · [English](phases/13-tools-and-protocols/07-building-an-mcp-server/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/07-building-an-mcp-server/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/07-building-an-mcp-server/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/07-building-an-mcp-server/exam/README.md) |
| 08 | Building an MCP Client: Discovery, Routing, and Dual-Era Fallback | [中文](phases/13-tools-and-protocols/08-building-an-mcp-client/docs/zh.md) · [English](phases/13-tools-and-protocols/08-building-an-mcp-client/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/08-building-an-mcp-client/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/08-building-an-mcp-client/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/08-building-an-mcp-client/exam/README.md) |
| 09 | MCP Transports: stdio and Stateless Streamable HTTP | [中文](phases/13-tools-and-protocols/09-mcp-transports/docs/zh.md) · [English](phases/13-tools-and-protocols/09-mcp-transports/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/09-mcp-transports/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/09-mcp-transports/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/09-mcp-transports/exam/README.md) |
| 10 | MCP Resources and Prompts: Addressable Context for Stateless Servers | [中文](phases/13-tools-and-protocols/10-mcp-resources-and-prompts/docs/zh.md) · [English](phases/13-tools-and-protocols/10-mcp-resources-and-prompts/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/10-mcp-resources-and-prompts/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/10-mcp-resources-and-prompts/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/10-mcp-resources-and-prompts/exam/README.md) |
| 11 | MCP Model Input: Sampling Migration and Stateless MRTR | [中文](phases/13-tools-and-protocols/11-mcp-sampling/docs/zh.md) · [English](phases/13-tools-and-protocols/11-mcp-sampling/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/11-mcp-sampling/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/11-mcp-sampling/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/11-mcp-sampling/exam/README.md) |
| 12 | Explicit Scope and Stateless Elicitation | [中文](phases/13-tools-and-protocols/12-mcp-roots-and-elicitation/docs/zh.md) · [English](phases/13-tools-and-protocols/12-mcp-roots-and-elicitation/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/12-mcp-roots-and-elicitation/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/12-mcp-roots-and-elicitation/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/12-mcp-roots-and-elicitation/exam/README.md) |
| 13 | MCP Tasks Extension: Durable Work on a Stateless Core | [中文](phases/13-tools-and-protocols/13-mcp-async-tasks/docs/zh.md) · [English](phases/13-tools-and-protocols/13-mcp-async-tasks/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/13-mcp-async-tasks/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/13-mcp-async-tasks/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/13-mcp-async-tasks/exam/README.md) |
| 14 | MCP Apps on the Stateless Protocol | [中文](phases/13-tools-and-protocols/14-mcp-apps/docs/zh.md) · [English](phases/13-tools-and-protocols/14-mcp-apps/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/14-mcp-apps/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/14-mcp-apps/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/14-mcp-apps/exam/README.md) |
| 15 | MCP Security: Poisoned Metadata, Routing, and MRTR State | [中文](phases/13-tools-and-protocols/15-mcp-security-tool-poisoning/docs/zh.md) · [English](phases/13-tools-and-protocols/15-mcp-security-tool-poisoning/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/15-mcp-security-tool-poisoning/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/15-mcp-security-tool-poisoning/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/15-mcp-security-tool-poisoning/exam/README.md) |
| 16 | MCP Authorization: CIMD, Issuer Binding, PKCE, and Step-Up | [中文](phases/13-tools-and-protocols/16-mcp-security-oauth-2-1/docs/zh.md) · [English](phases/13-tools-and-protocols/16-mcp-security-oauth-2-1/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/16-mcp-security-oauth-2-1/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/16-mcp-security-oauth-2-1/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/16-mcp-security-oauth-2-1/exam/README.md) |
| 17 | Stateless MCP Gateways and Registry Admission | [中文](phases/13-tools-and-protocols/17-mcp-gateways-and-registries/docs/zh.md) · [English](phases/13-tools-and-protocols/17-mcp-gateways-and-registries/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/17-mcp-gateways-and-registries/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/17-mcp-gateways-and-registries/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/17-mcp-gateways-and-registries/exam/README.md) |
| 18 | MCP Auth in Production: Issuer-Bound Enrollment and Tokens | [中文](phases/13-tools-and-protocols/18-mcp-auth-production/docs/zh.md) · [English](phases/13-tools-and-protocols/18-mcp-auth-production/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/18-mcp-auth-production/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/18-mcp-auth-production/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/18-mcp-auth-production/exam/README.md) |
| 19 | A2A — Agent-to-Agent Protocol | [中文](phases/13-tools-and-protocols/19-a2a-protocol/docs/zh.md) · [English](phases/13-tools-and-protocols/19-a2a-protocol/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/19-a2a-protocol/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/19-a2a-protocol/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/19-a2a-protocol/exam/README.md) |
| 20 | OpenTelemetry GenAI — Tracing Tool Calls End-to-End | [中文](phases/13-tools-and-protocols/20-opentelemetry-genai/docs/zh.md) · [English](phases/13-tools-and-protocols/20-opentelemetry-genai/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/20-opentelemetry-genai/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/20-opentelemetry-genai/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/20-opentelemetry-genai/exam/README.md) |
| 21 | LLM Routing Layer — LiteLLM, OpenRouter, Portkey | [中文](phases/13-tools-and-protocols/21-llm-routing-layer/docs/zh.md) · [English](phases/13-tools-and-protocols/21-llm-routing-layer/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/21-llm-routing-layer/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/21-llm-routing-layer/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/21-llm-routing-layer/exam/README.md) |
| 22 | Agent Skills: Portable Contract and Runtime Boundary | [中文](phases/13-tools-and-protocols/22-skills-and-agent-sdks/docs/zh.md) · [English](phases/13-tools-and-protocols/22-skills-and-agent-sdks/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/22-skills-and-agent-sdks/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/22-skills-and-agent-sdks/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/22-skills-and-agent-sdks/exam/README.md) |
| 23 | Capstone: Stateless Tool Ecosystem | [中文](phases/13-tools-and-protocols/23-capstone-tool-ecosystem/docs/zh.md) · [English](phases/13-tools-and-protocols/23-capstone-tool-ecosystem/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/23-capstone-tool-ecosystem/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/23-capstone-tool-ecosystem/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/23-capstone-tool-ecosystem/exam/README.md) |
| 24 | Skill Discovery and Progressive Disclosure | [中文](phases/13-tools-and-protocols/24-skill-discovery-and-progressive-disclosure/docs/zh.md) · [English](phases/13-tools-and-protocols/24-skill-discovery-and-progressive-disclosure/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/24-skill-discovery-and-progressive-disclosure/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/24-skill-discovery-and-progressive-disclosure/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/24-skill-discovery-and-progressive-disclosure/exam/README.md) |
| 25 | Skill Invocation and Routing | [中文](phases/13-tools-and-protocols/25-skill-invocation-and-routing/docs/zh.md) · [English](phases/13-tools-and-protocols/25-skill-invocation-and-routing/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/25-skill-invocation-and-routing/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/25-skill-invocation-and-routing/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/25-skill-invocation-and-routing/exam/README.md) |
| 26 | Skill Permissions, Sandboxes, and Trust | [中文](phases/13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/docs/zh.md) · [English](phases/13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/26-skill-permissions-sandboxes-and-trust/exam/README.md) |
| 27 | Skill Evals, Packaging, and Portability | [中文](phases/13-tools-and-protocols/27-skill-evals-packaging-and-portability/docs/zh.md) · [English](phases/13-tools-and-protocols/27-skill-evals-packaging-and-portability/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/27-skill-evals-packaging-and-portability/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/27-skill-evals-packaging-and-portability/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/27-skill-evals-packaging-and-portability/exam/README.md) |
| 28 | MCP Tool Contracts and Content | [中文](phases/13-tools-and-protocols/28-mcp-tool-contracts-and-content/docs/zh.md) · [English](phases/13-tools-and-protocols/28-mcp-tool-contracts-and-content/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/28-mcp-tool-contracts-and-content/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/28-mcp-tool-contracts-and-content/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/28-mcp-tool-contracts-and-content/exam/README.md) |
| 29 | MCP Reliability, Cancellation, and Flow Control | [中文](phases/13-tools-and-protocols/29-mcp-reliability-cancellation-and-flow-control/docs/zh.md) · [English](phases/13-tools-and-protocols/29-mcp-reliability-cancellation-and-flow-control/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/29-mcp-reliability-cancellation-and-flow-control/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/29-mcp-reliability-cancellation-and-flow-control/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/29-mcp-reliability-cancellation-and-flow-control/exam/README.md) |
| 30 | MCP Registry Supply Chain: Admission, Drift, and Rollback | [中文](phases/13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift/docs/zh.md) · [English](phases/13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/30-mcp-registry-supply-chain-and-drift/exam/README.md) |
| 31 | MCP Conformance Engineering: Versioning, Evidence, and Operations | [中文](phases/13-tools-and-protocols/31-mcp-conformance-versioning-and-operations/docs/zh.md) · [English](phases/13-tools-and-protocols/31-mcp-conformance-versioning-and-operations/docs/en.md) · [代码讲解](phases/13-tools-and-protocols/31-mcp-conformance-versioning-and-operations/code/main.讲解.md) | [CoderPad](phases/13-tools-and-protocols/31-mcp-conformance-versioning-and-operations/coderpad/README.md) · [Exam](phases/13-tools-and-protocols/31-mcp-conformance-versioning-and-operations/exam/README.md) |

## 本次同步范围

- 包含 Phase 13 的讲义、代码、图、测验、outputs、CoderPad、exam，以及原始备份和参考答案。
- 附带两条 Phase 13 学习路线和本阶段 CoderPad 生成器源码；保留第 23 课测试所需的三个仓库级辅助脚本。
- 本次未同步其他 Phase、PDF 导出、完整课程网站和自动导师 host skills。原讲义中的跨阶段选读链接需查看完整上游课程；`learn-mcp` / `learn-agent-skills` 的自动导师调用不随此副本提供。
- 原第 23 课代码讲解中提到“缺少根 scripts 导致测试导入失败”的历史说明不适用于本副本；所需辅助脚本已一并保留。

课程与练习文件按本地快照保留，未替学习者完成 TODO。后续加入完整课程时可以继续沿用当前目录布局。
