<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="long-running-background-agents-durable-execution"></a>

# 长时间运行的后台 Agents：Durable Execution

> 生产长方圆 agents 不要运行 `while True`. 每个 LLM 电话成为一项活动 checkpoint,重试和重播。 OpenAI Agents SDK 2026年3月,合并进入了GA。 Claude 代码路段( R)Anthropic运行计划 Claude 代码引用没有持续的地方进程。 会话暂停人的投入, 能够生存, 并且从最近的恢复 checkpoint 键入 `thread_id`。在新的人类工程学背后,有一个老模式——工作流程 orchestration ——加上一个新的输入: LLM 被称为非决定性活动,必须明确重新进行恢复。

**类型:** 学习
**语言:** Python (标准, 最小耐力性执行状态机器)
**先修要求:** 阶段15 · 10(派遣模式),阶段15 · 01(长-长 agents)
**时间:** ~60分钟

<a id="the-problem"></a>

## 问题

考虑 agent 持续四个小时,需要三个工具 prompts 用户两次, 并得出40 LLM 电话,半途而废,主机在重新启动,怎么了?

- 幼稚的 `while True` 循环: 一切都丢失了。运行从零开始。 3 tool calls 执行( 具有实际副作用) 再次执行。 用户因已核准的事项再次被提示 。 40 LLM 电话被重新登记
- 与 durable execution:运行的简历来自最近的 checkpoint。已完成的活动没有重新执行;其结果从耐用日志中重新播放。用户不重新批准他们已经批准的事项。 LLM 已经打过的电话没有重新登记。

这和十年来运行的流程引擎一样(Temporal, Cadence, Uber's Cherami)。新的是: LLM 现在,电话是一种活动——非决定性的、昂贵的、具有副作用的——它们完全适合这种模式。

课程的运行主题:长期的可靠性衰减(METR观察到“35分钟的降解”——成功率随着地平线的下降,大约是四级下降)。 Durable execution 启用比可靠性配置支持长的运行, 如果设计正确且如果设计错误则不安全, 这是一条安全失败的新途径 。

<a id="the-concept"></a>

## 概念

<a id="activities-workflows-and-replay"></a>

### 活动、工作流程和重播

- **Workflow**:确定性 orchestration 代码。定义活动的顺序, branches,等待。必须具有确定性,这样它就可以从事件日志中重播,而不会出现令人惊讶的差异。
- **Activity**:非决定性的、可能无法完成的工作单位。 LLM call, tool call,文件写, HTTP 每项活动都记录了投入,并(一旦完成)完成了产出。
- **事件日志**: 耐久的备份仓库。每个活动开始、完成、失败、重试,每一个工作流程决定都记录下来。
- **Replay**:在恢复时,工作流程代码从一开始就重新运行;已完成的每一项活动都返回其登录结果,而不重新生效。只有尚未完成的活动才实际运行。

和那个形状一样 React 与虚拟DOM重新发生,或 Git 重建一棵树 commits。管弦乐团的决定性因素是耐久性便宜的原因。

<a id="why-llm-calls-fit-the-pattern"></a>

### Why LLM 调用符合模式

LLM 电话:
- 非决定性(temperature > 0; 偶数 temperature 10个模型版本之间漂移)。
- 昂贵(金钱和隐居)。
- 可能失败(rate limits中途停留)
- 具有副作用(如果他们使用工具的话)。

这正是活动配置。 LLM 调用为活动, 使您重试以指数反向、 检查重新启动和可重播 trace 用于调试。

<a id="checkpoints-keyed-by-thread_id"></a>

### Checkpoints 键入 `thread_id`

LangGraph微软 Agent 框架,云花耐久物体, Claude 代码规则都在同一条线上 API 形状: a `thread_id` 指定会议( 或同等) ; 每个州都持续向后端过渡( 默认为 PostgreSQL, SQLite for dev, Rediis for capid); 恢复读取最新 checkpoint.

后端选择很重要 :

- **PostgreSQL**:可耐用、可查询、可生存。 LangGraph.
- **SQLite**:仅限本地- dev;在主机之间丢失数据。
- **Redis**:快速但短暂,除非配置 AOF/ snapshot。
- **云花耐久物体**: 透明分布; 以独特的钥匙覆盖范围; 活到数小时至数周。

<a id="human-input-as-a-first-class-state"></a>

### 人类投入作为一流状态

Propose-then-commit 需要“ 等待人类” 的持久性状态。 工作流程暂停, 外部排队会保留等待的请求, 批准会从那个角度恢复。 没有持久性, 这将是最好的选择; 有了它, 一夜之间就会收到批准, 工作流程会在早上开始。

<a id="the-35-minute-degradation"></a>

### 35分钟的降解

METR观察到, agent 测量的类别显示可靠性衰减超过连续操作的~35分钟。任务持续时间翻倍大约使故障率翻了四倍。 Durable execution 无法修正此选项; 它允许您运行的时间超过可靠性配置支持的时间。 安全模式是将耐久性与 checkpoints 并且用预算的杀机开关(Lesson 13) 来计算总上限,而不论墙上时间。

<a id="when-durable-execution-is-the-wrong-answer"></a>

### 当 durable execution 答案不对

- 运行时间短于几分钟,没有人输入。 管理 > 受益 。
- 严格只读信息检索 。
- 正确性需要一内部端对端的任务 context window (一些推理任务;一些一张照片的一代)

```figure
memory-consolidation
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 在 stdlib 中执行一个最小的耐久执行引擎 Python支持:

- `@activity` 将输入和输出记录到 a/ 的装饰器 JSON 事件日志 。
- 工作流程函数,可以排列活动顺序。
- 一个 `run_or_replay(workflow, event_log)` 函数重播已完成的活动,而不重新执行。

驱动程序模拟三维活动工作流程, 中途崩溃, 并显示 (a) 一种天真的重试重新执行一切, 而 (b) 是一种只运行缺失活动的重播 。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-durable-execution-review.md` 审评拟议的长期 agent 用于正确耐久性执行形状:活动、确定性、 checkpoint 后端,人输入状态,和HITL对面政策。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。观察天真的重试和重播之间活动执行计数的差别。修改崩溃点并相应显示重放计数的变动。

2. 转换玩具引擎使用 `thread_id` 明确。 模拟两个同时举行的共享引擎的会话并确认其事件日志不会相撞 。

3. 在玩具引擎中选择一个活动。 引入非确定性( 在工作流程决定中设置一个墙时钟的时针) 。 显示重放时的差异 。 解释真正的引擎如何处理这个问题( 副作用登记, ) `Workflow.now()` APIs).

4. 读 LangChain 深入地在生产后运行 agents文章。 请列出运行时间持续的每一状态, 以及每个失败模式覆盖的名称 。

5. 设计a checkpoint 6小时自动编码任务的政策。您在哪里 checkpoint崩溃后恢复是什么样子?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| Workflow | "Agent脚本 | Deterministic orchestration 代码; 从事件日志中可重放 |
| Activity | "一步" | 非确定性单位(LLM call, tool call); 在前后登录 |
| 事件日志 | 后台店 | 每一州过渡的持久记录 |
| Replay | "Resume" | 重新运行工作流程;已完成的活动返回已记录的结果,不执行 |
| Checkpoint | 拯救点 | 以线索键入的永久状态_ID; 简历上的最新赢项 |
| thread_id | "会议钥匙" | 确定可持续状态的标识符 |
| 35分钟降压 | "可靠性衰变" | METR: 成功率随地平线而下降~ 方形 |
| Non-determinism | 重播时的疲惫 | 墙上的钟,随机的 LLM 输出; 必须注册为副作用 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic — Claude Code Agent SDK: agent loop](https://code.claude.com/docs/en/agent-sdk/agent-loop) 预算,转身,恢复语义。
- [微软 - Agent Framework: human-in-the-loop 和检查站](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop) 要求信息窗口形状 。
- [LangChain 制作深部的运行时间 Agents](https://www.langchain.com/conceptual-guides/runtime-behind-production-deep-agents) 具体运行时间要求。
- [OpenAI Agents SDK + 时间整合(Trigger.dev 宣布)](https://trigger.dev) 活动形状 LLM calls.
- [Anthropic 计量 agent 实际的自主权](https://www.anthropic.com/research/measuring-agent-autonomy) -35分钟的降解参考。
