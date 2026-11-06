<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="rewoo-and-plan-and-execute-decoupled-planning"></a>

# ReWOO 与 Plan-and-Execute：解耦 Planning

> ReAct 在一个流中进行内断思考和动作。 REWO 将它们分开: 前面有一个大计划, 然后执行 。 tokens,+4%的精度在热锅QA上,您可以将规划器提炼成7B模型。规划和执行将其普遍化;计划与行动将其缩放到网络导航中。

**类型：** 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop)
**时间:** ~60分钟

<a id="learning-objectives"></a>

## 学习目标

- 解释为什么REWOO的规划者/ 工人/ 溶剂分割保存 tokens 并增强坚固度 ReAct断裂循环
- 实施一个计划DAG,一个有依赖性的定单执行员和一个构成工人产出的解决者——全部都是标准标准。
- 决定任务何时应该按照计划执行,然后执行,然后中断 ReAct,使用 2026 “ 5 个工作流程模式” 框架(Anthropic).
- 承认当需要计划与行动合成计划数据 来完成长视距网络或移动任务时

<a id="the-problem"></a>

## 问题

ReAct断裂思维-观察循环既简单又灵活,但每个 tool call 必须充分顾及前一情况,包括以前的所有想法。 Token 使用量随着深度而增长。 更糟的是: 当工具在中间环失效时, 模型必须从错误观察中重新生成整个计划 。

REWO(Xu等人,ArXiv:2305.18323, 2023年5月)注意到这一点,并下注:计划整个项目,平行地收集证据,最后作出回答。 LLM 呼叫计划,N tool calls 证据(可平行),1 LLM 解决的号召。 贸易的灵活性较小( 计划是静态的) , 效果更好 token 效率和更清晰的失败模式。

<a id="the-concept"></a>

## 概念

<a id="the-three-roles"></a>

### 三个角色

```
Planner:  user_question -> [plan_dag]
Workers:  [plan_dag]     -> [evidence]        (tool calls, possibly parallel)
Solver:   user_question, plan_dag, evidence -> final_answer
```

规划者生成一个 DAG。 每个节点都指定工具、 其参数, 以及它依赖于哪个早期节点( 引用如 `#E1`, `#E2`工人按地形顺序执行节点,溶剂将所有东西都缝在一起。

<a id="why-5x-fewer-tokens"></a>

### 为什么少5x tokens

ReAct grows prompt 线性长度,以步数。 prompt 包括思想1+行动1+观察1+思想2+行动2+观察2等等。 prompt.

REWO 支付一个计划者 prompt (大),N小工人 prompts (每张 tool call,没有链条),和一个求解器 prompt。在热锅QA上,纸张测量量为~5x tokens 并评分+4绝对精确度。

<a id="why-it-is-more-robust"></a>

### 为何更强健

如果工人3失败 ReAct,循环必须解析中流错误。在REWOO中,工人 3 返回一个错误字符串;解决问题者会从原始计划中看到它,并可以优雅地降低。失败的本地化是每个节点,而不是一步步。

<a id="planner-distillation"></a>

### 规划师蒸馏

论文的第二个结果: 因为规划者看不到观测结果, 您可以微调一位175B老师对规划者输出的 7B 模型。 小模型处理 planning; 大模型不需要 inference. 这是现在的标准——许多2026年的生产 agents 使用一个小计划员和一个大执行员,或者相反。

<a id="plan-and-execute-2023"></a>

### 计划与执行(2023年)

该 LangChain 团队的2023年8月通用后 ReWOO , 变成一个模式名称: 计划与执行。 前端规划员发布一个步骤列表, 执行者运行每个步骤, 选项重规划者可以在观察结果后修改 。 这更接近于此 。 ReAct 重排轨道(重新规划者将观测结果带回 planning),但保留 token savings.

<a id="plan-and-act-erdogan-et-al-arxiv250309572-icml-2025"></a>

### 计划与行动(埃尔多甘等人,ArXiv:2503.09572,ICML 2025)

计划与行动将模式缩放为长方位网络和移动 agents。关键贡献是合成计划数据:标签的轨道生成器生成了明确计划的训练数据。用于微调在WebArena(WebArena)等任务上工作30-50步的规划模型,该模型将使用一个单项任务 ReAct 轨道失去一致性。

<a id="when-to-pick-which"></a>

### 什么时候选择哪个

| 图案 | 当 |
|---------|------|
| ReAct | 短期任务、未知环境、需要被动处理例外 |
| ReWOO | 结构化任务,有已知工具 token- 敏感、可平行的证据 |
| Plan-and-Execute | 和ReWOO一样,但经过部分执行后进行重新规划 |
| Plan-and-Act | 长方位( > 30级),网络/移动/计算机使用 |
| 思想树 | 搜索值得支付( Lesson 04)。 |

Anthropic 在 2024 年 12 月的建议是：从最简单的方案开始。如果任务只需要一次 tool call 加上一段总结，就不要构建 ReWOO。如果任务是一项需要 40 步的研究工作，就不要仅使用 ReAct。

```figure
rewoo-plan
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行玩具雷WOO:

- `Planner` 一种编程政策,它从一个 prompt.
- `Worker` - 发送每个节点 tool call 通过登记处。
- `Solver` 文字的构成读取证据并产生最后答案。
- 依赖性决议——参考文献 `#E1` 改为较早的工人产出。

演示回答“法国首都的人口是多少,四百万?” 使用两步计划:(1) 查查首都,(2) 查查人口,然后解决。

运行：

```
python3 code/main.py
```

该 trace 显示完整计划,然后是工人结果,然后是求解者构成。比较 token 计数 (我们打印粗略字符计数) 至 a ReAct那种脱产的跑步 REWO在这种结构化的任务上获胜

<a id="use-it"></a>

## 实际应用

LangGraph 计划与执行作为食谱(`create_react_agent` 用于 ReAct,为计划执行定制图形。 CrewAI流直接编码模式: 您定义了前面的任务, 而流程 DAG 执行这些任务。 计划与行动合成数据方法仍然主要是研究; 运行时间模式( 明确计划 DAG) 正在生产中的船舶 LangGraph 和 CrewAI Flows.

<a id="ship-it"></a>

## 交付成果

`outputs/skill-rewoo-planner.md` 给用户请求生成 ReWOO 计划 DAG, 给其工具目录。 它在将数据传递给执行者之前验证该计划( 循环、 解决了所有引用、 每个工具都存在) 。

<a id="exercises"></a>

## 练习

1. 将工人执行独立计划节点的平行操作。 它用两个平行组的6节 DAG买什么?
2. 如果工人返回错误, 添加一个重规划节点, 开火。 给再规划操作组织最小的更改是什么 ?
3. Replace `Planner` 使用小模型( 7B 类)并保留 `Solver` 比较端对端质量——分割在哪里失败?
4. 阅读再生组织关于计划蒸馏的论文第4节。从概念上重现175B - > 7B的结果:您需要哪些训练数据,以及如何得分计划质量?
5. 将玩具移植到计划与行动轨道形状:计划是一个序列,而不是一个DAG。什么权衡会改变?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| ReWOO | "无观察的回响" | 计划,然后平行地收集证据,然后解决——在 planning prompt |
| Plan-and-Execute | "LangChain计划执行模式 | 执行后,有可选重规划节点的 reWOO |
| Plan-and-Act | 规模计划执行 | 与长方位任务综合计划训练数据分开的明细规划者/执行者 |
| 证据参考 | "#E1,#E2,..." | 发送时用先前的工人输出替换计划节点占位符 |
| 规划师蒸馏 | "小计划者,大执行者" | 精细调整一个小模型 traces 老师的 |
| Token efficiency | 往返旅行 | 减少5x tokens 在热锅QA 与s ReAct 中写着 |
| DAG 执行器 | "心理调度员" | 运行有依赖性的计划节点; 在每个级别平行 |

<a id="further-reading"></a>

## 进一步阅读

- [Xu等人,REWO:与观察脱钩(arXiv:2305.18323)](https://arxiv.org/abs/2305.18323) - 银色纸
- [Erdogan等人,《计划与行动》(arXiv:2503.09572)](https://arxiv.org/abs/2503.09572) 配有合成计划的按比例规划者-执行者
- [LangGraph 计划与执行导师](https://docs.langchain.com/oss/python/langgraph/overview) 框架办法
- [Anthropic建设有效 Agents](https://www.anthropic.com/research/building-effective-agents) - 选择最简单的模式
