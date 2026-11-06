<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="anthropics-workflow-patterns-simple-over-complex"></a>

# Anthropic 的工作流模式：优先采用简单方案

> 施伦茨和张Anthropic, 2024年12月 将工作流程(预定义路径)与 agents (动态工具使用) 。 五个工作流程模式覆盖大多数情况。 以直接 API 电话。 agents 只有当无法预测步骤时。

**类型：** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 名称 Anthropic五个工作流程模式 : prompt 链条、路线、平行、管弦乐手、评价员optimizer.
- 解释一下 agent- 工作流量的区别和每个工程成本。
- 指定何时选择一个工作流 agent 也反之亦然。
- 执行所有五个模式的脚本 LLM.

<a id="the-problem"></a>

## 问题

团队达到多 -agent 用于解决需要单功能呼叫的问题的框架。 成本是真实的: 框架添加了模糊的层 prompts, 隐藏控制流程, 并邀请过早的复杂。 史伦茨和张的2024年12月的岗位是行业最引人注意的退步: 开始简单, 只有在它挣钱时才增加复杂性 。

<a id="the-concept"></a>

## 概念

<a id="workflows-vs-agents"></a>

### 工作流程与 agents

- **Workflow.** LLMs 和通过预定义的代码路径操作的工具。 工程师拥有此图 。
- **Agent.** LLMs 动态引导自己的工具并自制步骤。该模型拥有图表。

工作流更便宜,更快,更容易调试 Agents 解开没有定论的问题,但使失败模式更难解释。

<a id="the-augmented-llm"></a>

### 扩大 LLM

为所有五种模式奠定基础:一 LLM 具有三种功能——搜索(检索)、工具(行动)、内存(持久性)。 API 电话可以用这个

<a id="the-five-patterns"></a>

### 五个模式

1. **Prompt chaining.** 呼叫1的输出是调用 2 输入。 当任务有干净线性分解时使用。 选项程序在两个步骤之间的关卡 。

2. **Routing.** 分类器 LLM 选择下游 LLM 或用于引用的工具。当输入的绝对不同需要不同的操作时使用(第一级支持与退款对错误与销售)。

3. **Parallelization.** 运行 N LLM 同时调用,总结果。 两种形状: 分割( 不同的块) 和投票( 相同) prompt,N 运行,多数/合成)。

4. **Orchestrator-workers.** 乐团 LLM 动态决定哪些工人(以及 LLMs运行和合成输出。 agent loops 但管弦乐队不会无止境地循环

5. **Evaluator-optimizer.** One LLM 提议一个答案,另一个 LLM 进行切换,直到评价员通过。这是自我检索(Lesson 05)的通用版本。

<a id="where-workflows-beat-agents"></a>

### 工作流程跳过的地方 agents

- **任务可以预测** 如果你能列举一下台阶,你应该。
- **费用高昂的任务。** 工作流程已受约束的职档计数; agents 能够螺旋。
- **遵守规定的任务。** 审计员想读一下图表,而不是从轨迹推断出来。

<a id="where-agents-beat-workflows"></a>

### Where agents 跳过工作流程

- **不限成员名额的研究。** 下一步取决于最后一步返回了多少。
- **变长任务。** 职档计数未知的时数。
- **新颖域 。** 当你还不知道正确的工作流程——先探索,然后编纂。

<a id="the-context-engineering-companion"></a>

### 环境工程伙伴

"Effective context engineering 大赦国际 agents" (Anthropic 2025年)正式确定了相邻的学科:200k窗口是预算,而不是容器。在压缩时,包括何时让上下文增长。 context compression (本课程中第14期第06期,重编之前)。

```figure
workflow-chain
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行所有五个工作流程模式 `ScriptedLLM`:

- `prompt_chain(input, steps)` - 顺序。
- `route(input, classifier, handlers)` 分类+发送。
- `parallel_vote(prompt, n, aggregator)` -N跑步,总和。
- `orchestrator_workers(task, workers)` 管弦乐队选工人
- `evaluator_optimizer(task, proposer, evaluator, max_iter)` - 绕到过去

运行：

```
python3 code/main.py
```

每一个图案都印有 trace。每个模式的总代码线为~10-15;框架的成本以千计。

<a id="use-it"></a>

## 实际应用

- Direct API 需要完成大部分任务。
- 只有当模式真正需要持久状态时,框架才适用(第2条)。LangGraph), actor- 模型货币(AutoGen v0.4),或角色诱惑(Stemple)CrewAI).
- 伸手争取 Claude Agent SDK 当你想要 Claude Code harness 形状没有重建它。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-workflow-picker.md` 选择特定任务描述的正确模式,包括决定理由和 agent 如果工作流程不足。

<a id="exercises"></a>

## 练习

1. 执行带有信任阈值的路线。 低于阈值 - > 升级为人类。 一级支持使用案例的阈值土地在哪里?
2. 添加超时到 `parallel_vote`. . 万一有人打电话来,会怎么样?
3. Turn `evaluator_optimizer` 成为土匪: 保持上2级输出横跨迭代, 这样一个晚好结果就不会被一个晚坏的结果覆盖。
4. Combine prompt 以路径链链:路由器选择三条链中的一个。 token 成本与单一的一大prompt alternative.
5. 选一个你的作品 features。绘制工作流程图,计算步骤。 agent 在这儿真的好点了吗?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Workflow | "预定义的流程" | 工程师拥有的图表 LLM 和 tool calls |
| Agent | “自主 AI” | 模型所有图;动态工具方向 |
| Augmented LLM | "LLM 带工具的" | LLM +搜索+工具+内存;原子单元 |
| Prompt chaining | 连续电话 | 调用 N 是调用 N+1 的输入 |
| Routing | "分类器发送" | 选择哪个链/ 模式处理输入 |
| Parallelization | 滚蛋 | 并行电话;按分节或表决方式汇总 |
| Orchestrator-workers | "Dispatcher agent" | Orchestrator LLM 选取专家 LLMs dynamically |
| Evaluator-optimizer | "建议人+法官" | 循环到评价员通过; 自译自审 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic建设有效 Agents (第2024号决定)](https://www.anthropic.com/research/building-effective-agents) 五个工作流程模式
- [Anthropic有效 context engineering 大赦国际 agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 同伴纪律
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) ——当有价图表得到其成本时
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) 管弦乐队工人模式,已生产
