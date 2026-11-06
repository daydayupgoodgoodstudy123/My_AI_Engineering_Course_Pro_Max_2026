<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="case-studies-and-the-2026-state-of-the-art"></a>

# 案例研究与 2026 年前沿进展

> 三个生产级参考,用于研究端到端,每个参考显示不同的多-agent engineering. **Anthropic研究系统** (手动笔记员,15x) tokens单人加90.2%agent 4号手术,彩虹部署) 是金刚管的病例。 **MetGPT / 聊天发展** (SOP-编码的软件工程角色专业化;ChatDev的“交流脱轨”;MacNet 扩展至 > 1 000 agents 通过DAGs, arXiv:2406.07155是弹道作用分解案例。 **OpenClaw / Moltbook / 软本** (原为Clawdbot, Peter Steinberger著,2025年11月;改名两次;247k GitHub 2026年3月前的恒星;本地 ReAct-loop agents; 分子本作为 agent-只有社会网络,使用~2.3M agent 由Meta 2026-03-10获得的发射日内账户说明在人口规模上发生的情况: prompt- 注射风险,州级条例(中国限制政府计算机使用公开法律,2026年3月)。 **2026年4月的框架景观:** LangGraph 和 CrewAI 铅生产; AG2 是社区 AutoGen 续编; Microsoft AutoGen 处于维护模式( 合并为 Microsoft) Agent 框架,RC 2026年2月; OpenAI Agents SDK 是生产 Swarm 后继者; Google ADK (2025年4月) 是 A2A- 本地的,每个主要框架都已经上船了 MCP 支持; 大多数船舶 A2A。这个课读取每个案例的端到端,并提取共同模式,以便您为您的下一个生产系统选择正确的参考。

**类型:** 学习(综合项目)
**语言:** —
**先修要求:** 整个第16阶段(第01-24期)
**时间:** ~90分钟

<a id="problem"></a>

## 问题

Multi-agent 工程是一个年轻的学科。 制作参考文献很少, 并且每个引用都覆盖空间的不同部分。 一次阅读它们有用; 把它们比较成一组更有用 。 此课将三个2026年的卡门案例研究作为端到端阅读列表, 标记共同模式, 并绘制框架景观图, 这样您就可以从知识而不是营销中做出框架选择 。

<a id="concept"></a>

## 概念

<a id="anthropic-research-system"></a>

### Anthropic 研究系统

制作监督员 -工人的案子 Claude 4号操作计划和合成; Claude 索内特 4 subagents 出版的工程文章: https://www.anthropic.com/engineering/multi-agent-research-system.

关键计量结果:

- **+90.2%** 相对于单agent 内部研究评估4号
- **80%的浏览Comp 差异** 解释如下: **token 仅使用** - 多重 - 多重 - - 多重agent 赢得主要因为 subagent 换个新衣服 context window.
- **15x tokens 每个查询** 单人agent.
- **彩虹部署** because agents 长途跋涉,而且很老练

编写设计经验:

1. **缩放努力查询复杂程度 。** 简单  1 agent 3-10岁 tool calls中度 + 3 agents10+ 复杂研究 subagents.
2. **先宽一点,再窄一点** Subagents 进行大范围搜索; 铅合成; 后续 subagents 做目标深度。
3. **彩虹部署** 保持旧的运行时间版本在飞行前一直运行 agents finish.
4. **核查不是可选择的。** 该系统被认为具有幻觉,没有明确的核查作用。

这是生产规模的主管-工人地形学(16 ° -05级)的参考案例。

<a id="metagpt--chatdev"></a>

### MetGPT / 聊天发展

生产SOP-作用分解案例,涵盖arXiv:2308.00352(MetaGPT)和arXiv:2307.07924(ChatDev)。

MetGPT 编码软件工程SOP作为角色 prompts产品经理、建筑师、项目经理、工程师、质量保证工程师。 `Code = SOP(Team)`。每个角色都有狭窄的专门性 prompt; 间线 handoffs 携带结构化的文物(PRD docs、建筑文档、代码)。

查塔德夫的贡献: **交流脱轨**. Agents 回答前要求具体信息——设计师 agent 询问程序员在绘制 UI 之前使用什么语言,而不是猜测。 hallucination 以多个 -agent 管道可观。

MacNet(arXiv:2406.07155) 将查塔德夫扩展至 **>1000 agents 通过 DAGs 进行**。每个 DAG 节点都是角色专业化;边缘编码 handoff 比例表是可能的,因为路线明确,离线可计算。

设计课程:

1. **结构问题比规模问题重要。** 一支五官制的SOP队击败了50agent 组织不结构的组。
2. **Handoff 书面合同。** 角色之间的异体传递遵循一种模式。
3. **交流性脱轨** 是一种廉价的载荷模式。
4. **磁盘比聊天更宽** 当流体是已知的, 编码它。

这是角色专业化(第16阶段 08)和结构化的地形学(第16阶段 15)的参考案例。

<a id="openclaw--moltbook-ecosystem"></a>

### OpenClaw / Moltbook 生态系统

生产规模案例。

- **2025年11月: 纽约** 克劳德波特(彼得·斯坦伯格) ReAct-loop coding agent船舶。
- **2025年12月 - 2026年3月:** 两次改名(Clawdbot OpenClaw 继续按OpenClaw)。
- **2026年2月: 2026年2月,我发现** 分子手册作为 agent- 仅在相同的原始生物上建立社交网络;~2.3M agent 账户在天数内。
- **2026年3月(2026-03-10):** 梅塔获得分子本。
- **2026年3月:** 中国限制公开法律对政府电脑的使用。
- **2026年3月:** OpenClaw 交叉号 247k GitHub stars.

这就是多重的...agent 看起来像你放几百万 agents 在一个共同的基质上:

- **新兴经济活动。** Agents 买卖,互相服务 token-payments.
- **Prompt- 人口规模的注射风险。** 恶毒的 prompt 在一个病毒中 agent 向数千个 agent-以-agent 小时内互动。
- **国家一级的监管对策。** 在发射后数周内,监管就到达生态系统。

从这一案例中得出的设计经验部分是技术性的,部分是治理性的:

1. **Multi-agent 人口规模是一个新的制度。** 个别系统的最佳做法(核查、明确作用)仍然适用,但还不够。
2. **Prompt injection 是新的 XSS 。** Treat agent 剖面图和交叉agent 默认情况下信件为不信任的输入 。
3. **监管比设计周期快。** 计划一下
4. **开源+病毒级化合物。** 247k 恒星在~ 4个月中是不寻常的; 用于部署- 爆炸装入的设计 。

See [OpenClaw 维基百科](https://en.wikipedia.org/wiki/OpenClaw) 和CNBC/Palo Alto网络报告生态系统细节。 ReAct 循环; Moltbook 的公开文章揭示了社会制图结构在顶端。

<a id="framework-landscape-april-2026"></a>

### 2026年4月框架景观

| 框架 | Status | 最适合 | 注释 |
|---|---|---|---|
| **LangGraph** (LangChain) | 生产领导 | 结构图+检查站+ human-in-the-loop | 建议的生产违约 |
| **CrewAI** | 生产领导 | 具有序列/等级过程的基于角色的船员 | 强力作用分解 |
| **AG2** | 社区维护 | 组域+演讲者选择 | AutoGen v0.2 续编 |
| **微软自动Gen** | 维护模式 (2026年2月) | — | 合并为 Microsoft Agent 框架RC |
| **Microsoft Agent Framework** | RC (2026年2月) | orchestration +企业一体化 | 新条目; 手表 |
| **OpenAI Agents SDK** | Production | Swarm successor | tool-return handoff pattern |
| **谷歌 ADK 键盘** | 生产(2025年4月) | A2A-native | 谷歌云集成 |
| **Anthropic Claude Agent SDK** | Production | single-agent + 研究扩展 | 参见研究系统员额 |

每一个主要框架现在都投入舰船 **MCP** 支持; 大多数船舶 **A2A**。协议兼容性不再是一个差异。

<a id="the-common-patterns-across-all-three-cases"></a>

### 所有三个案件的共同模式

1. **轮椅+工人** (Anthropic 明确主管,MetGPT PM-As-监督员,开放法律个人 agents +网络效应)。
2. **Structured handoff contracts** (Anthropic subagent 任务描述, MetGPT PRD/建筑文件, OpenClaw A2A artifacts).
3. **核查作为头等角色** (Anthropic验证器, MetaGPT 的 QA 工程师, OpenClaw 的网络验证器) 。
4. **缩放是表层+基底,不是更多 agents** (脑波部署,MacNet DAGs,人口规模基底)
5. **费用为重要和披露的费用** (15x tokens,MetaGPT的人均作用预算,Motbook的每份互动定价)。
6. **安全态势明确** (Anthropic沙箱,MetaGPT的功能限制, OpenClaw prompt- 注射,即已知的攻击表面。

<a id="choosing-a-reference-for-your-next-project"></a>

### 选择下一个工程的参考

- **生产研究/知识任务 Anthropic Research.** Fresh-context subagents win.
- **工程/工具链工作流程 + MetGPT / ChatDev。** 角色+标准业务程序+ handoff contracts.
- **网络效应社会产品“开放法律”/“分子手册”。** 基底+新兴经济。
- **典型的企业自动化 CrewAI 或 LangGraph** 生产领先者,稳定运行时间。

<a id="the-2026-state-of-the-art-summary"></a>

### 2026年最新摘要

2026年4月的现场:

- **框架正在趋同。** MCP + A2A 支持是表格基本要求。 Handoff 语义是剩下的设计选择
- **Evaluation 越来越硬了** 水、水、循环和蒸气的缓解基准。
- **生产失败率可以衡量** 现场已经脱离了“演示时看起来很棒”的时代。
- **成本是核心工程的制约因素。** Token 每项任务的成本,每次互动的墙上时钟,彩虹部署的顶部。agent 准确性获胜,但成本却受损——贸易是商业决定。
- **监管是一种近期投入,而不是背景关切。** 管辖权的移动速度快于单个部署周期。

```figure
a5-orchestrator-scale
```

<a id="use-it"></a>

## 实际应用

`outputs/skill-case-study-mapper.md` 是一个能读出一个提议中的多功能的技巧agent 将系统设计图绘制成最接近的案例研究,对已经测试过的项目设计决定进行直观分析。

<a id="ship-it"></a>

## 交付成果

生产多功能的启动规则agent 2026年:

- **是从案例研究开始的,不是从零开始的** 选择最接近 Anthropic 研究/MetGPT/开放法律与适应。
- **Adopt MCP + A2A.** 跨框架的可移动性是有价值的;协议支持是免费的。
- **与SWE -bench Pro或者你内部的亲善行为做斗争** 被验证是污染的
- **交税** 独立核查费用 ~ 20 - 30% token budget 并且购买了可以测量的正确性。
- **彩虹部署长期运行 agents.** 期待多小时 agent 运行为例行。
- **阅读WMAC 2026和MAST后续报告。** 纪律发展得很快

<a id="exercises"></a>

## 练习

1. 读 Anthropic 研究系统从终端到终端。 确定三个设计决定, 如果您用一个较小的模型取代 Opus 4 (例如, Haiku 4)。
2. 读取 MetaGPT 3-4 节(arXiv:2308.00352). 从您自己的域( 不是软件) 编码 1 SOP 作为角色 prompts。SOP意味着多少角色?
3. 读查塔德夫(arXiv:2307. 7924), 识别“ 交流性脱轨” 的机制。 在您现有的多功能- 系统之一中执行它 。agent systems.
4. 读取 OpenClaw 和 Moltbook 。 选择一个在人口规模上出现的特定失败模式, 而不出现在 5- 中 。agent 系统,你如何设计它?
5. 选择您当前的多功能 -agent 三个案例研究中哪一个是最接近的参考? 您还没有通过案例研究中哪些设计决定? 请写下您将在本季度采纳的决定 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Anthropic Research | 主管的推荐信 | Claude 行动4+索内特4 subagents; 15x 键 tokens;+90.2%超过单agent. |
| MetaGPT | "作为 prompts" | 软件工程的作用分解; `Code = SOP(Team)`. |
| ChatDev | "Agents 成为角色" | 设计师/程序员/审查员/测试员;交流解密。 |
| MacNet | "通过DAG实现比例 | arXiv: 2406.07155; 1000+ agents 透过明确的DAG路线。 |
| OpenClaw | "Local ReAct-loop agents" | Steinberger的项目, 2026年3月247k颗恒星。 |
| Moltbook | "Agent- 唯一的社交网络" | 2.3M agent 账户;2026年3月Meta公司购置的。 |
| 彩虹部署 | "同时使用多种版本" | 保持旧运行时间的版本在飞行中运行 agents. |
| 交流性脱轨 | "在回答之前先问" | Agents 要求同行提供具体信息,而不是猜测。 |
| WMAC 2026年 | "AAAI研讨会" | 2026年4月 社区多-agent coordination. |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic - 我们如何建造我们的多 -agent 研究系统](https://www.anthropic.com/engineering/multi-agent-research-system) 监督员-工人生产参考
- [METGPT - 多种语言的META程序Agent 合作框架](https://arxiv.org/abs/2308.00352) - SOP作用分解
- [聊天Dev - 通讯 Agents 软件开发](https://arxiv.org/abs/2307.07924) 交流性脱节
- [麦克网——基于作用的尺度 agents 至 1000+](https://arxiv.org/abs/2406.07155) 以残疾津贴为基础的比额表
- [维基百科上的 OpenClaw](https://en.wikipedia.org/wiki/OpenClaw) 生态系统概览
- [WMAC 2026年](https://multiagents.org/2026/) - AAAI 2026年关于多-Agent Coordination
- [LangGraph docs](https://docs.langchain.com/oss/python/langgraph/workflows-agents) 生产领导者
- [CrewAI docs](https://docs.crewai.com/en/introduction) 作用框架
