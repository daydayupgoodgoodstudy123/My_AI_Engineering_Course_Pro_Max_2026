<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="role-based-agent-teams--roles-tasks-processes"></a>

# 基于角色的 Agent 团队：角色、任务与流程

> 四个原始的: Agent工作、船员、工序。两个顶级的形状:船员(自主、基于角色的合作)和流动(活动驱动、决定)。 CrewAI 2026年的参考执行, 其文档是直截了当的:“对于任何生产准备应用, 从流程开始 。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 12(工作流程模式),阶段14 14(Actor 模型)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- 名称 CrewAI四个原始的Agent,任务,船员,处理)和每个人自己的。
- 区分顺序、等级和计划中的共识进程;按工作量选一个。
- 区分(以自主角色为基础的)流动(活动驱动的)船员,并解释医生提出的生产建议。
- 使用 `@tool` 设计器和 `BaseTool` 子类; 原因 structured outputs 文本为空的文本。
- 说四 CrewAI 内存类型和每个回报。
- 执行三号标准agent 编剧(研究员、作家、编辑),编写简报。
- 点三 CrewAI 失败模式 : prompt- 烟雾,经理...LLM 税,易碎 handoffs.

<a id="the-problem"></a>

## 问题

团队采用多 -agent 框架撞上了相同的墙。 “ 自主合作” 在演示中听起来很棒。 然后客户会将错误归档, 你需要重新播放决定性。 或者财务会问 LLM或待命需要知道哪个 agent 凌晨3点停了下来

Free-form LLM完全的DAGs回答他们,但失去了探索的形态 一个集思广益 agent needs.

CrewAI分裂是诚实的。 团队为协作、 角色基础、 探索性工作。 流程为事件驱动、 代码所有、 可审计的生产。 相同的框架, 两个形状, 每个表面的选取 。

<a id="the-concept"></a>

## 概念

<a id="four-primitives"></a>

### 四个原始人

CrewAI表面很小,记住这个和那个 rest 是配置。

- **Agent.** `role + goal + backstory + tools + (optional) llm`。背面是包含负载的。它会塑造音调、判断力,当 agent 工具为函数 agent 可在下面拨打(更多)。
- **Task.** `description + expected_output + agent + (optional) context + (optional) output_pydantic`. 可重复使用的工作单位。 `expected_output` 是合约 `context` 列出产出通过时的上游任务。 `output_pydantic` 强制结构形状 。
- **Crew.** 集装箱 拥有 `agents`,将 `tasks`, 该 `process`,并且可选 `memory` + `verbose` + `manager_llm` settings.
- **Process.** 执行策略,顺序,等级,共识(计划),选择运行的形状。

Agents 无法直接看到对方。 agents。船员顺序任务。进程决定谁选择下一个任务。这就是整个心理模式。

> **对照** CrewAI 0.86 (2026-05)。 更新版本可以重命名或合并进程类型; 检查 [CrewAI 处理文件](https://docs.crewai.com/concepts/processes) 之后再依赖特定的形状

<a id="sequential-vs-hierarchical-vs-consensus"></a>

### 顺序与等级对共识

- **Sequential.** 任务按声明顺序运行。 `context` 以 N+1. 任务为单位, 成本最低。 最可预测的是, 在定单时使用 。
- **Hierarchical.** 经理 Agent (separate LLM 专家之间的路线。 CrewAI 要么从你那产卵经理 `manager_llm` 配置或默认。 管理器每回合选择下一项任务, 可以拒绝或更改路径。 当您有四个或四个以上专家并命令时使用, 真正取决于先前的输出 。
- **Consensus.** 计划,目前尚未在公众中实施 API。文档为未来的投票程序保留了名称。今天不要依赖它。

等级制增加一个回合 LLM 在每个专家的电话上都叫(经理) Token 费用可以乘五步跑程三倍,只有在需要路由时才能支付。

<a id="crews-vs-flows"></a>

### 船员对流动

这是2026年医生的领头

- **Crew.** LLM框架选择运行时的形状。 有利于: 研究、 集思广益、 初稿、 路径的任何地方都是答案的一部分。 很难重放。 很难测试。 低价到原型 。
- **Flow.** 由事件驱动的图表 `@start` 标记条目。 `@listen(topic)` 代表一个步骤,当另一步发出这个主题时,它会燃烧。 Python 生产,可观察,可测试,确定性。

2026年的医生生产建议: 以流动开始。 Fold Crews in `Crew.kickoff()` 自动时, 流动步骤会给您打电话。 流动会给您提供审计线索, 船员会给你探索机会。 Compe, 不要选择 。

<a id="tool-integration"></a>

### 工具集成

给一个 Agent 工具,选最简单的

1. **`@tool` decorator.** 纯函数成为工具。签名是图案; 文档是描述 LLM 看吧,对一次性帮手来说最好

   ```python
   from crewai.tools import tool

   @tool("Search the web")
   def search(query: str) -> str:
       """Return top results for the query."""
       return run_search(query)
   ```

2. **`BaseTool` subclass.** 基于类的工具, 具有明确的参数图案、 async 支持、 restrary 。 当工具有状态( 客户端、 缓存) 或需要结构化的参数时使用 。

   ```python
   from crewai.tools import BaseTool
   from pydantic import BaseModel

   class SearchArgs(BaseModel):
       query: str
       limit: int = 10

   class SearchTool(BaseTool):
       name = "web_search"
       description = "Search the web and return top results."
       args_schema = SearchArgs

       def _run(self, query: str, limit: int = 10) -> str:
           return self.client.search(query, limit=limit)
   ```

3. **内置工具包。** CrewAI 船舶第一当事方适配器: `SerperDevTool`, `FileReadTool`, `DirectoryReadTool`, `CodeInterpreterTool`, `RagTool`, `WebsiteSearchTool`连接一个输入

Structured outputs 使用 Pydantic 。 过 `output_pydantic=MyModel` 任务上的 CrewAI 验证 LLM 反制模型,强迫或重试 `expected_output` 字符串。 文本输出对草稿来说是好的; structured outputs 下游的流能消耗多少

<a id="memory-hooks"></a>

### 内存钩

CrewAI 将四个内存类型从盒子中卸下。它们组成:一个船员可以同时启用所有四个。

> **对照** CrewAI 0.86 (2026-05年). 最近通过统一 `Memory` 系统包扎这四个仓库。下面的概念模型仍然可以保存,但公共阶级表面可能崩溃成单一 `Memory` 更新版本中的条目点; 检查 [CrewAI 内存文档](https://docs.crewai.com/concepts/memory) 当前 API.

- **Short-term.** 单程内交谈缓冲,最后擦干净
- **Long-term.** 贯穿运行。 存储在矢量 DB (默认情况下的色调可互换) 。 与当前任务相似 。
- **Entity.** 实体事实。 “X客户在企业计划中。” 由实体而不是相似实体来决定。 生存者横跨各个角落。
- **Contextual.** 同步时间检索。 此时拉动相关的内存 Agent 需要它,而不是预先装货。

启用于船员 `memory=True` 或按类型配置。 embeddings 您配置的提供者( 默认为 OpenAI,可转换到本地。记忆是其中之一 CrewAI 其保持较薄的框架;纯度 LangGraph 需要你亲自给每个女人打个电话

<a id="when-role-based-teams-fit"></a>

### 适合角色小组

- 三到六岁 agents 起草、审查、审查、 planning集思广益
- 运行于 LLM下一步的判断是价值的一部分( 等级 ) 。
- 哪里的团队更快乐 `role + goal + backstory` 而不是读取图形定义。

<a id="when-they-do-not"></a>

### 当他们不

- 严格订购的确定性 DAG 。 LangGraph (教训13) 图形形状是右抽象; CrewAI角色框架是摩擦
- 二级延迟预算。 等级性增加往返旅行。 甚至序列序列化 prompts 包括备份和先前输出。
- Single-agent loops跳过框架; a agent loop (教训1)加上工具登记册较短。

课程17(Agent 框架权衡)在矩阵中对此做了规定。 CrewAI 坐在"协作角色"的角落

<a id="dependency-shape"></a>

### 依赖形状

独立 LangChain. Python 3.10至3.13. 用途 `uv`。星数:见 [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) AWS Bedrock集成记录;供应商基准报告,与 LangGraph 质量评估工作量,但方法(数据集、硬件、 evaluation 标准)不公布,因此将框架供应商数字视为仅指向性数字。

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **Prompt-从后院吹来的** 每一页2000字的背书 agent 和一个五...agent 组员在第一个任务之前烧掉上下文预算 tool call。将后台保留在200个字以下。重新使用词组 agents;不重复五次家用风格。
- **Manager-LLM token tax.** 等级进程添加一个管理器 LLM 在每个专家来之前先打个电话 五个任务组6人 LLM 调用不使用五通, 管理器调用带有全部任务列表和先前输出。 切换为顺序, 除非路由取决于输出 。
- **Brittle handoffs.** 任务 N `expected_output` 是一个“大纲”。任务N+1读为 `context` 并尝试分析三节。 LLM 下游生产了4种。 Agent 自动调试 `output_pydantic` ,所以任务 N+1 读取已输入的对象,而不是免费文本。
- **Crew-as-prod.** 自由式船员在没有流动包装的情况下被运到生产场。 输出变异性很大; 无法重播; 待命不能对好操作进行错误操作。 以流动包扎 。

```figure
ae-crew-vs-flow
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行两个形状的标准版本加上一个三agent crew.

Shape:

- `Agent`, `Task` 匹配数据类 CrewAI表面的
- `SequentialCrew.kickoff(inputs)` 以声明顺序运行任务, 将输出线串为 `context`.
- `HierarchicalCrew.kickoff(topic)` 添加一个管理器 Agent 选下一位专家,每回合,停在"完成"。
- `Flow` 与 `@start` 和 `@listen(topic)` 装饰师,一个小事件循环, trace.
- `tool(name)` 装饰镜像 CrewAI的 `@tool` shape.
- `Memory` 与 `short_term`, `long_term`, `entity` 仓库; 模拟相似性用途 numpy.
- Mock LLM 响应是硬编码字符串, 键离角色加输入前缀。 没有网络。 确定性 。

混凝土演示:研究员、作家、编辑团队制作关于 " 的简介agent 工程 2026 ” 。 研究人员拉动( 沉没) 来源。 Writer 起草。 编辑器收紧。 同样的船员通过流动运行来显示确定性形状 。

运行：

```bash
python3 code/main.py
```

Trace 连续机组人员通过 `context`,有经理选手的分级人员(研究人员、作家、编辑、然后是“完成”), 运行相同的三步, 并有明确的话题(`researched`, `drafted`, `edited`), tool calls 已经通过 `@tool`长期记忆在两个开关之间存活下来

船员 trace 流体; 经理原则上可以重新排序。 trace 已经固定了,这个选择就是教训

<a id="use-it"></a>

## 实际应用

- **CrewAI Flow** 即使流动是需要 `Crew.kickoff()`。流程给出了审计界限。
- **CrewAI 船员( 顺序)** 特别是第一稿和审查循环。
- **CrewAI 船员( 等级)** 当路由取决于输出时, 你拥有4个或更多专家。
- **LangGraph** 明确的国家机器,耐久的恢复,严格订单。
- **AutoGen v0. 4 自动 Gen** (第14条) actor- 典型的货币和错觉隔离。
- **OpenAI Agents SDK** (第16段) OpenAI- 第一批产品 handoffs 和 guardrails.
- **Claude Agent SDK** (第17段) Claude- 第一批产品 subagents 和会话存储。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-crew-or-flow.md` 选择 船员对流动 任务, 并用脚架来设置最小的操作。 手持手腕的人拒绝使用无背部、 无直截了当的外在主题, 与三个专家相比, 等级 。

<a id="pitfalls"></a>

## 陷阱

- **背面的味道。** 它决定输出。 测试三个变量 agent; 差异是真实的。 选择一个, 冻结它 。
- **Skipping `expected_output`.** 没有每件任务的合同,下游的任务就能够接收到 LLM 编译。 船员运行; 审计失败 。
- **记忆永远在** 长期的写作每运行一次。 矢量 DB 增长。 检索会变得吵闹。 范围会写给事实持续的任务 。
- **Manager prompt drift.** 等级管理器 prompt 如果路由变怪, 把它丢到动词模式中读取 。
- **工具副作用在船员。** 船员可以比预期的多拨数。 POST, DELETE, 支付属于流动步骤, 绝不是船员工具 。

<a id="exercises"></a>

## 练习

1. 将序列组转换为流动。 计算可变性下降的触摸点。 注意可读性下降的位置 。
2. 给船员添加实体记忆:客户的实际情况始终存在, 校验检索会拉动正确的实体 。
3. 执行一个等级化程序, 管理者拒绝前往编辑处, 直到作者输出至少三段 。 Trace 重试
4. 电线a `BaseTool` 用于网络搜索的子类。比较 trace 形状与 `@tool` 装饰版本 。
5. Add `output_pydantic=Brief` 编辑器任务 `Brief` 具有 `title`, `summary`, `sections`。使写入任务输出格式错误 JSON 一次; 核实 CrewAI重试行为 trace.
6. Read CrewAI医生介绍的,把玩具移到真实的 `crewai` API。标准版本跳过什么保证?
7. 电线代理Ops或Langfuse(Lesson 24) 进行真正的运行。 traces 你错过了Stdlib版本吗?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Agent | "Persona" | 角色+目标+背书+工具 |
| 任务 | "单位工作" | 说明+预期产出+受让人+可选 structured output |
| Crew | "Agent team" | 集装箱 Agents +任务+进程 |
| 工艺流程 | 执行战略 | 顺序/等级/共识(计划) |
| Flow | "决定性的工作流程" | 事件驱动、代码所有、可测试 |
| Backstory | "Persona prompt" | 音调和判断力的形状 Agent |
| `@tool` | "功能工具" | 将函数转换为工具的装饰符 Agent 可以调用 |
| `BaseTool` | "类工具" | 基于类的工具, 带有 args 方案、 restries、 async 支持 |
| 实体内存 | "实体事实" | 内存范围为客户/账户/发行 |
| 长期内存 | "龙卷风记忆" | 矢量支持的内存,在开球之间存活 |
| 上下文内存 | "即时检索" | 记忆拉动在那一刻 Agent 需要它吗? |
| Manager LLM | "Router agent" | Extra LLM 选择下一个任务的等级进程 |
| `expected_output` | "任务合同" | 字串,它告诉 Agent (和审计)什么形状返回 |

<a id="further-reading"></a>

## 进一步阅读

- [CrewAI 介绍](https://docs.crewai.com/en/introduction):概念和建议的生产路径
- [CrewAI 流程指南](https://docs.crewai.com/en/concepts/flows):事件驱动形状, `@start`, `@listen`
- [CrewAI 工具参考](https://docs.crewai.com/en/concepts/tools): `@tool`, `BaseTool`内置工具包
- [CrewAI memory](https://docs.crewai.com/en/concepts/memory):短期、长期、实体、背景
- [Anthropic建设有效 Agents](https://www.anthropic.com/research/building-effective-agents):当多功能-agent 帮助,当它不帮助
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview):国家机器的替代
