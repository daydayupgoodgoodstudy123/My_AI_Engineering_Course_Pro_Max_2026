<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="production-agent-runtimes--fast-instantiation-and-typed-workflows"></a>

# 生产级 Agent 运行时：快速实例化与类型化工作流

> 生产 agent 运行时间优化了忽略的原型框架:即时成本、输入工作流程表面和备供使用的后端。 2026年配对: Agno ()Python) 瞄准微秒 agent 即决和无国籍 FastAPI backends. Mastra ships agents工具、工作流程、统一模式路径和在 Vercel AI 上的综合存储 SDK substrate.

**类型：** 了解
**语言:** Python, TypeScript
**先修要求:** 阶段14 · 01 (Agent Loop阶段14 13 (LangGraph)
**时间:** ~45分钟

<a id="learning-objectives"></a>

## 学习目标

- 确定Agno的业绩目标,以及它们的重要性。
- 名称 Mastra三个原始人 Agents、工具、工作流程——以及支持的服务器适配器。
- 解释为何无国籍问题届会范围 FastAPI 后端是推荐的 Agno 生产路径 。
- 选择 Agno 与s Mastra 给定的堆叠( F)Python- 第一次对决 TypeScript-first).

<a id="the-problem"></a>

## 问题

LangGraph自动Gen, CrewAI 团队想要的只是 agent loop快速,在我的运行时间"达到阿格诺(Agno) (Agno)Python) 或 Mastra (TypeScript两者都以原始原型的原始产品进行原始加工,使其更符合周围的堆叠。

<a id="the-concept"></a>

## 概念

<a id="agno"></a>

### Agno

- Python 运行时间,前费数据
- "没有图表,链条,或混乱的模式——只是纯净的 python."
- 其文件的绩效目标:~2微秒 agent 即时, ~ 3. 75 KiB 内存 agent,~23 个模型提供者。
- 生产路径:无国籍会议范围 FastAPI 后端。 每个请求都开始新 agent;会话状态 生活在 DB 中。
- 本地多式联运(文字、图像、音频、视频、文件)和 agentic RAG.

速度目标很重要 当你有成千上万的短命 agents 每秒( 聊天 fant- in, ) evaluation 管道)当它们重要程度较低时 agent 运行10分钟。

<a id="mastra"></a>

### Mastra

- TypeScript,以Vercel AI为基础 SDK.
- 三个原始的: **Agents**, **Tools** (Zod-typed), **Workflows**.
- Unified Model Router - 94个供应商的3 300个+型号(2026年3月)。
- 复合存储:内存、工作流程、 observability 选择不同的后端; 点击House 推荐 observability 缩放时。
- 阿帕奇2.0 与 `ee/` 来源许可的企业许可证目录。
- Express、 Hono、 Fastify、Koa的服务器适配器; 头等舱下流和天体整合。
- Ships Mastra 工作室(当地主机: 4111)用于调试。
- 22k+ GitHub 300公里+每周 npm 下载时间为1.0(Jan 2026)。

<a id="positioning"></a>

### Positioning

也不是想成为 LangGraph他们就以下几个方面展开竞争:

- **语言适合。** 阿格诺为 Python- 第一队; Mastra 用于 TypeScript-first.
- **运行时间的人类工程学。** Agno = 近零高空; Mastra = 与Vercel生态系统结合。
- **Observability.** 两者都与Langfuse/Phoenix/Opik合并(列松24),但 Mastra 工作室是第一党。

<a id="when-to-pick-each"></a>

### 什么时候选一个

- **Agno** — Python 后端, 许多短命 agents,强的渗透要求, FastAPI shop.
- **Mastra** — TypeScript 后端, 下js/ Vercel 部署, 统一的多供应商模式路径, Zod 类型工具 。
- **LangGraph** (教训13)——当耐久状态和清晰的图表推理比原始速度更重要时。
- **OpenAI / Claude Agent SDK** - 需要供应商的产物形状时(16-17页)。

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **Perf-for-perf's-sake.** 选阿格诺是因为当工作量慢一点时,"2微秒"听起来不错 agent 要求时请打个电话 管理费不是瓶颈
- **生态系统锁定。** Mastra维瑟尔的组合是加在维瑟尔,再减到别处。
- **企业执照混乱** Mastra的 `ee/` 目录是源代码, 不是 Apache 2. 0。 如果您是的话, 请阅读许可 。 planning 叉子

```figure
wb-runtime-spawn
```

<a id="build-it"></a>

## 动手实现

这一教训主要是比较性的,没有单一的代码工艺品能对两者都起到司法作用。 `code/main.py` 单枪匹马的玩具: agent, 流出, 持续会话" 流执行两次( 一旦 Agno 形状, 一次) Mastra-shaped).

运行：

```
python3 code/main.py
```

两个结构不同但功能等同的 traces.

<a id="use-it"></a>

## 实际应用

- **Agno** — Python 需要速度和 FastAPI shape.
- **Mastra** — TypeScript 后端, 有许多原始的提供者和工作流程 。
- 双方的船首选方 observability 钩子,都和兰福斯混在一起

<a id="ship-it"></a>

## 交付成果

`outputs/skill-runtime-picker.md` 选阿格诺 Mastra, LangGraph,或提供者 SDK 以堆叠、潜伏预算 和操作形状为基础

<a id="exercises"></a>

## 练习

1. 读读阿格诺的医生。 ReAct 环(Lesson 0.1)到阿格诺,什么消失了?
2. Read Mastra博士, 左转相同的循环到 Mastra。工具键入方面有什么变化(Zod对空)?
3. 基准:计量 agent 堆叠上的即时悬浮物, Agno的2微秒对您的工作量很重要吗?
4. 设计一个迁移:如果你一直在运行 CrewAI 在 Python如果你搬到阿格诺,会有什么坏处?
5. Read Mastra的 `ee/` 许可证条款。什么限制会影响开放源码叉?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Agno | "Fast Python agents" | 无国籍会议范围 agent runtime |
| Mastra | "TypeScript agents 阿尔法尔 SDK" | Agents + 工具+工作流程+ Model Router |
| Unified Model Router | "多供应商访问" | 94个供应商3 300多个模型的单一客户 |
| 复合储存 | "多面后端" | Memory/workflows/observability 每一个都到不同的商店 |
| Mastra Studio | 本地调试器 | 本地主机: 4111 用于检查的 UI agents |
| Source-available | "不是OSS" (没有SS) | 许可证允许从源头阅读,但限制商业用途 |

<a id="further-reading"></a>

## 进一步阅读

- [Agno Agent 框架文件](https://www.agno.com/agent-framework) 实绩指标, FastAPI integration
- [Mastra docs](https://mastra.ai/docs) 原始设备,服务器适配器, Model Router
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) —— 现状的备选办法
- [彗星奥皮克](https://www.comet.com/site/products/opik/) — observability 比较 Mastra integrations
