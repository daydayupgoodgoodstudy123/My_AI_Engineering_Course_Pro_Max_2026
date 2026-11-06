<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="supervisor--orchestrator-worker-pattern"></a>

# 监督者与编排者—工作者模式

> 一条线索 agent 计划与代表; 专业工作者在平行环境下执行并报告。 这是后面的模式 Anthropic研究系统(A)Claude 4号行动队领先,4号索内特领先 subagents),以90.2%的单位计量,高于单agent 内部研究评估4号 Anthropic工程文章中说浏览Comp 80%的差异 由 token 仅使用——多agent 赢得主要因为 subagent 换个新衣服 context window。这一课程从原始人那里建立主管模式,并涵盖2026年的工程经验,即生产部署。

**类型:** 学习 + 构建
**语言:** Python (stdlib, `threading`)
**先修要求:** 阶段16 -04(初级模型)
**时间：** ~75分钟

<a id="problem"></a>

## 问题

研究是典型的任务 单agent 系统失败。 您询问“ 多重中哪些变化 :agent 系统在2023年和2026年之间?" agent 依次读取五篇论文, 以文字填充一半的上下文, 然后将所有文字一起解释。 当它达到第五篇时, 它忘记了第一篇论文。 它不能平行化 。

上司模式解决这个问题: agent 计划搜索,将每个子问题 交给一个工人,并合成。token 窗口中有一个狭义的问题。 领导者从不看到原始文件, 仅看到工人摘要 。

Anthropic研究系统报告内部研究评估与单一Opus 4. 同一文章指出,浏览Comp的80%差异是由于 *token 仅使用*新的环境 subagent 它们是主要机制。

<a id="concept"></a>

## 概念

<a id="the-pattern"></a>

### 模式

```
                 ┌──────────────┐
                 │   Lead       │  plans, decomposes,
                 │  (Opus 4)    │  synthesizes
                 └──┬────┬───┬──┘
                    │    │   │
            ┌───────┘    │   └───────┐
            ▼            ▼           ▼
      ┌─────────┐  ┌─────────┐  ┌─────────┐
      │ Worker1 │  │ Worker2 │  │ Worker3 │
      │(Sonnet) │  │(Sonnet) │  │(Sonnet) │
      └─────────┘  └─────────┘  └─────────┘
         fresh       fresh        fresh
         context     context      context
```

铅从不读原材料。工人在铅合成之前,不会看到对方的工作。 handoff 和一个狭窄的文物。

<a id="why-it-wins"></a>

### 为何赢

三个机制:

1. **新建上下文 subagent.** 探索“FIPA-ACL遗产”的工人不携带40k tokens 铅花费 planning。它有一个200公里的窗口 一个问题。
2. **专业 prompt.** 领先者 prompt 是一个“分解和合成”而不是“研究”。 prompt 范围狭窄: "找到X中的变化。" prompts 产生重点突出的产出。
3. **Parallelism.** 工人同时跑动, 长钟时间差不多 `max(worker_times) + plan + synthesis`, 不 `sum(worker_times)`.

<a id="engineering-lessons-anthropic-2025"></a>

### 工程课程(Anthropic 2025)

该 Anthropic 文章列出了一些与2026年相关的生产经验:

- **缩放努力查询复杂程度 。** 简单查询: 1 agent, 3-10 tool calls复杂查询:10+ agents。领导者必须估算这个,而不是打电话的人。
- **宽一点再窄一点** 将问题分为广泛的分问题,然后在回答需要深度时,每个分问题产生更多的工人。
- **彩虹部署。** Agents 传统蓝色绿色行不通 Anthropic 使用彩虹: 渐进 rollout 旧版的版本,而旧版的版本。
- **Token 使用率居主导地位。** Multi-agent 是 ~ 15x 的 tokens 单agent。只有在任务值证明成本合理时才运行。

<a id="the-graph-native-turn"></a>

### 图形本地转

LangGraph 最初发运a `langgraph-supervisor` 高级图书馆 `create_supervisor` 2025年,帮助者 LangChain 将建议直接通过工具呼叫方式实施主管模式,因为 tool calls 给予更多的控制权 *上级看到了什么* (context engineering图书馆仍在运作;医生们现在建议使用工具呼叫表。

<a id="the-failure-modes"></a>

### 失败模式

- **铅会幻觉** 如果铅产生不会分解真实问题的子问题,工人对错误的目标进行精确的研究。
- **工人过度爆炸。** 没有明确的范围界限,工人就超越了他们指定的次级问题,污染了综合步骤。
- **综合冲突。** 两位工人又回到了矛盾的事实。 领导者必须重新询问(加上一轮)或者明确指出分歧。 沉默地选择一方是最糟糕的失败:用户从来不知道发生了分歧。

<a id="when-supervisor-is-wrong"></a>

### 当主管错了

- **顺序任务。** 如果第二步实际上需要第一步的产出,平行主义就一文不值。CrewAI Sequential, LangGraph 线性图)。
- **简单的查询** Single-agent 使用铅的“规模努力”来进行产卵工人。
- **严格地确定** 主管用途 LLM-selected delegation。如果审计/重播比适应性重要,静态图更好。

```figure
supervisor-hierarchy
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 使用 `threading`。铅分解了子问题,工人同时处理每个子问题,铅合成。 LLMs 工人们的脚本是用来模拟取回和总结的。

关键结构 :

- `Lead.plan(query)` 将查询分为三个子问题。
- `Worker.run(sub_q)` 返回假摘要(可能是任何工具使用) agent 生产中)。
- `Lead.run(query)` 吸引工人加入并合成

Run:

```
python3 code/main.py
```

输出显示计划, 平行工人 traces 并加上开始/ 结束的时间戳和最后的合成。 您可以看到墙上时钟的赢家: 3个0. 3秒的工人在~ 0. 35秒内运行, 不是 0. 9秒 。

<a id="use-it"></a>

## 实际应用

`outputs/skill-supervisor-designer.md` 使用用户查询并制作一个主管- 模式设计: 铅 system prompt, 工人角色, 子问题分解规则, 以及合成模板。 在建立新研究模式之前先使用此模板 agent system.

<a id="ship-it"></a>

## 交付成果

部署上司模式前的检查列表 :

- **模特儿配对** 引领推理模型(Opus类, `o3` 工人采用较快、较便宜的模式(Sonnet, `o4-mini`).
- **工人超时** 超过中位运行时间的工人会被杀;铅的再生或没有铅的再生。
- **Token 每一个工人的上限。** 硬限值(如预期合成输入量10x)阻止了离家出走的工人打乱预算。
- **Observability.** Trace 领头计划,每个工人 tool calls,以及合成。这是任何热量后调试的基础。
- **Rainbow rollout.** 古老的长跑 agents 需要渐进版本转换,而不是热交换。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`,然后修改铅,让5个工人而不是3个工人生产。观察墙上时钟的效果。
2. 执行工人超时:杀死超过0.5秒的工人,并让铅合成其余结果。 observability 你需要知道一个工人被切开吗?
3. 给领导者的合成添加冲突检测步骤:如果两个工人返回自相矛盾的答案,牵头者会注意到分歧而不是选择一个。 LLM?
4. Read Anthropic研究系统工程员额。列出该玩具演示在生产过程中需要采用的三种做法。
5. Compare LangGraph的 `create_supervisor` 相对于新的工具调用建议。 这给了您更好的控制 主管所看到的? 为什么 Anthropic 是否只明确通过次回答,而不是将原始工人背景合成?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Supervisor | "Lead agent" | 乐团 agent 计划,代表,和合成。 |
| Worker | "Subagent" | 重点 agent 主管援引的狭义范围及其自己的 context window. |
| Orchestrator-worker | "超级巨型" | 相同的东西,不同的名字 2026年的文学作品使用两种 |
| 新的上下文 | 清干净的窗口 | 工人的背景是从 system prompt 而不是领导者的历史 |
| 彩虹部署 | "Gradual rollout" | 长期状态 agents 需要改版排水和替换,而不是蓝色绿色。 |
| Token dominance | "内容是变量" | 80%的研究与研究差异来自总数 tokens 使用, 不是模式选择, 按 Anthropic. |
| 缩放努力 | "Match agent 算作复杂" | 铅估算查询困难,产生1对10加工人。 |
| 综合冲突 | 工人意见不一致 | 两名工人又回到了相互矛盾的事实;铅必须出现分歧,而不是默默地挑出一个。 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic 工程——我们如何建造我们的多功能...agent 研究系统](https://www.anthropic.com/engineering/multi-agent-research-system) 监督员生产参考图案
- [LangGraph 工作流程和 agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents) ——现在推荐表格是工具调用主管
- [LangGraph 主管参考](https://reference.langchain.com/python/langgraph-supervisor) 遗留的助手,仍在2026年的生产中使用
- [OpenAI 烹饪手册——管弦乐 Agents:常规和 Handoffs](https://developers.openai.com/cookbook/examples/orchestrating_agents) — handoff- 基地主管变体
