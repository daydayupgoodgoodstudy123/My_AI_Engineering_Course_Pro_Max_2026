<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="role-specialization--planner-critic-executor-verifier"></a>

# 角色专业化：规划者、Critic、执行者与验证者

> 最常见的多功能agent 2026年分解:一 agent 计划、执行、批评或核实。 MetaGPT(arXiv:2308.00352)将此正式化为SOP编码成角色 prompts 产品经理、建筑师、项目经理、工程师、质量保证工程师——以下 `Code = SOP(Team)`. 查塔德夫(arXiv:2307.7924) 链式设计师、程序员、审查员、测试员,通过带有“交流脱轨”的“聊天链”(Chat 链式)。agents 核查器带有载荷:Cemri等人(MAST,ARXiv:2503.13657)显示每个多维-agent 无法追踪到缺失或中断的验证。 PwC 报告了结构化验证循环在 7x 中增加的精度( 10% + 70%) CrewAI.

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段16 · 04(初级模型),阶段16 · 05(高级)
**时间:** ~60分钟

<a id="problem"></a>

## 问题

通用多功能agent 系统产生通用输出。 三个组聊天的编码员会写出三种普通代码的口味。 您可以添加更多 agents,添加更多回合,但仍未超过质量阈值。

修补不光 agents - 确实 *different* agents指定不同的角色。 critic 程序设计师没有工具。 给验证员一个客观的测试套件。 现在系统内部对有根的校正有分歧, 而不仅仅是平行的猜测 。

<a id="concept"></a>

## 概念

<a id="the-four-canonical-roles"></a>

### 四个金刚石角色

**Planner.** 读取目标, 生成一个步骤列表或规格。 工具: 知识检索、 文档、 输出: 结构化计划 。

**Executor.** 一次读取一个计划, 生成文物。 工具: 实际的工作工具( 代码编译器、 shell, ) API 输出: 文物 。

**Critic.** 根据计划者的意向阅读执行者的输出。工具:只读访问手工艺品,静态分析。输出:接受/拒绝带有理由。

**Verifier.** 读取工艺品并运行确定性检查。 工具: 测试运行者、 打字检查器、 系统验证器。 输出: 带证据的通过/ 失败 。

Critic 主观,有意见,经常 LLM验证是客观的,确定性的, 经常是代码的,它们不是同一个角色

<a id="metagpts-sop-pattern"></a>

### MetagPT 的 SOP 模式

MetGPT(arXiv:2308.00352)将SOP编码为软件工程标准操作程序 prompts:

- **产品管理器** 写PRD。
- **Architect** 制作系统设计。
- **项目管理员** 任务分开
- **Engineer** implements.
- **QA 工程师** 运行测试。

每个角色都有严格的输入/输出计划。 prompt 说起什么角色 *是* 和什么情况 *必须生产*. 该 `Code = SOP(Team)` 确定性标准业务程序 LLMs 进入一个可预测的管道。

<a id="chatdevs-communicative-dehallucination"></a>

### 查塔德夫的通讯解密

查塔德夫添加了密钥移动: 当执行者需要计划中没有的具体细节时, 它在继续前明确询问设计师。 这阻止了经典的操作 LLM 无法想象地发明细节

执行:作用 prompt 包括“当您需要特定信息时,您没有获得这些信息,在生成输出之前先询问相关角色的名称。”

<a id="why-verifier-matters-most"></a>

### 为什么核查者最重要

Cemri等人(MAST)追踪到1 642多个-agent 执行失败。 21.3%是核查缺陷——系统发送了一个无人检查的回答。 trace 回到“有一个检查 默默失败或从未运行过。”核查是负载作用。

报告的PwC(百分率)CrewAI 添加结构化的验证循环将精度从10%提高到70%。 7x从一个角色中得益。

<a id="critic-vs-verifier"></a>

### Critic vs 校验器

- 一个 critic 是一个 LLM 研究文物的质量,主观的,可以被貌似真实的流言所骗
- 验证器是一件在文物上运行的确定程序。 目标。 给人以通过/ 失败的证据 。

两者都用。 Critic 捕捉味道问题, 校验器无法表达。 验证器捕获错误 critic 看不到,因为他们只在运行时出现。

<a id="the-anti-pattern"></a>

### 反模式

你系统中的每一个角色都是 LLM 并且每个角色的输出都是“看起来不错。”经典MAST 失败模式。至少添加一个通过代码而不是密码决定的过错验证器。 LLM.

<a id="framework-mappings"></a>

### 框架绘图

- **CrewAI** — `Agent(role, goal, backstory)` 教科书专业的表面。
- **LangGraph** - 结点可以专门化 prompts;边缘强制输油管。
- **AutoGen** 角色特定人物 名字在"CroupChat"里
- **OpenAI Agents SDK** — handoff 角色专业化工具之间的 Agents.

```figure
swarm-roles
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 实施一个四功能管道, 建立一个简单的 Python function:

- **Planner** 产生一个规格。
- **Executor** 生成代码字符串 。
- **Critic** (LLM- 标出明显的问题。
- **Verifier** 在 a 中运行生成的代码 sandbox (`exec`) 与试验案例相对应。

演示运行两次:一次执行器生成正确的代码( )critic + 校验双关,执行器一旦生成非规格代码(critic 检查者会发现,

Run:

```
python3 code/main.py
```

<a id="use-it"></a>

## 实际应用

`outputs/skill-role-designer.md` 需要任务并生成角色名册( 3-5 个角色)、 输入/ 输出每个角色的图案, 以及校验器检查。 在编程前先使用此选项 agents 进入一个框架。

<a id="ship-it"></a>

## 交付成果

Checklist:

- **至少有一个确定性核查员** 从来没有全部...LLM.
- **明确I/O每个角色的方略。** 计划者返回一个图例,而不是说明;执行者读取的是这个图案。
- **沟通脱节** 执行者必须询问计划者信息丢失时; 永远不要发明它 。
- **Critic/验证者订购。** Run critic 第一次(低劣、渔获设计问题),第二次核查(慢、渔获虫)。
- **循环预算。** Max 2 critic- 执行者修正回合,然后升级为人类。

<a id="exercises"></a>

## 练习

1. Run `code/main.py` 观察验证员如何捕捉到窃听器 critic 错误。 添加静态分析检查( 计算出 `return`测试失败了会有什么发现?
2. 添加一个第五角色:将用户的愿望转换为计划者准备的“需求分析员 ” 。 什么样的沟通性失常要求应该流到它头上?
3. 读取 MetagPT 第3节 (")Agents列出MetaGPT的5个角色的每个输入/输出计划。
4. 读查塔德夫的聊天链图(arXiv:2307.7924,图3)。 确定交流脱轨会打破一个无穷无尽的循环。
5. PwC的准确度增长来自核查循环。 假设三个任务,其中添加一个验证器是无益的 — — 无法确定是否正确或者费用太高。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 角色专业化 | "Different agents,不同的工作" | Distinct system prompts 专为规划者/执行者/critic/验证作用。 |
| SOP 模式 | "标准操作程序编码" | MetGPT的架构:每个角色严格的I/O计划将一个团队变成管道。 |
| 交流性脱轨 | "先问再发明" | 查塔德夫模式: 当缺少细节而不是编造细节时, 执行者会询问计划者 。 |
| Critic | "LLM reviewer" | 主观的,有意见的审查员, 品味问题, 可能被貌似可信的流言所骗 |
| 验证者 | 彻底检查 | 基于代码的通行证/ 失败。 测试运行器、 打字器、 系统验证器。 不能被骗取 。 |
| 核查缺口 | "没有人检查" | MAST系统有21.3%的故障。 回答发送时没有检查, 检查结果会捕捉到错误 。 |
| 版本循环 | "Critic 把它送回去" | Critic 拒绝会触发执行者通过反馈重新运行。需要预算 。 |
| All-LLM anti-pattern | "看起来不错" | 每一个角色 LLM无法确定性检查,典型的MAST失败 |

<a id="further-reading"></a>

## 进一步阅读

- [Hong等人——MetGPT:Meta方案,多功能-Agent Collaboration](https://arxiv.org/abs/2308.00352) - 标准操作程序prompt 参考文件
- [简等人——通讯 Agents 软件开发(ChatDev)](https://arxiv.org/abs/2307.07924) 聊天链+交流脱轨
- [Cemri等人——为什么要做多Agent LLM 系统失效?](https://arxiv.org/abs/2503.13657) 最大技术统计分类;核查缺口占失败的21.3%
- [CrewAI 医生 Agent roles](https://docs.crewai.com/en/introduction) 生产角色说明表面
