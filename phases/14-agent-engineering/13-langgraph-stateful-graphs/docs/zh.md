<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="stateful-graph-orchestration--durable-execution-and-checkpoints"></a>

# 有状态图 Orchestration：Durable Execution 与 Checkpoints

> Agent 是一个州级机器; 节点是函数; 边缘是过渡; 每个节点之后都设置了状态检查站。 上次成功时, 任何失败都会恢复 。 checkpoint. LangGraph 是这个低水平状态模型的 2026 参考值 orchestration.

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段14 · 01 (Agent Loop阶段14 · 12 (工作流程模式)
**时间:** ~75分钟

<a id="learning-objectives"></a>

## 学习目标

- Describe LangGraph核心模型: 带有打字状态、 函数节点、 有条件边缘和后节点的状态机器 checkpoints.
- 列出博士们突出显示的四种能力: durable execution, streaming, human-in-the-loop全面记忆
- 解释一下 orchestration topologies LangGraph 支持: 主管, 对等对等(swarm),等级(取消的子集)。
- 执行带有输入状态、 有条件边框和 a 的 stdrb 状态图 checkpoint循环

<a id="the-problem"></a>

## 问题

Agents 和工作流程都存在问题:当40步运行在38步失败时,您想要从38步恢复,而不是重新开始。二等国家模型让操作员在假设新运行的图书馆周围黑客重写。

LangGraph设计答案: 状态是头等键, 突变是明确的, 并且 checkpoints 在每个节点之后,都坚持下去。 `load_state(session_id)` call.

<a id="the-concept"></a>

## 概念

<a id="the-graph"></a>

### 图表

图形定义为:

- **国家类型。** 输入每个节点读取和变异的单词( 或 Pydantic 模型) 。
- **Nodes.** 纯函数 `(state) -> state_update`。更新在返回后将合并为州。
- **Edges.** 节点之间的有条件或直接过渡。
- **进进出出** `START` 和 `END` 哨兵节点标记边界。

示例:a agent 与 `classify`, `refund`, `bug`, `sales`, `done` 节点—— 路径流程作为图表 。

<a id="durable-execution"></a>

### Durable execution

每个节点返回后,运行时间将国家连成系列,并写给一个检查站(SQLite、Postgres、Redis、海关)。 `resume(session_id)` 并精确地从N+1级站站上接起。

该 LangGraph 医生们明确突出显示生产用户, 这一点很重要: Klarna, Uber, J. P. Morgan。 索赔不是图形形状, 而是图形形状加上检查站使得回收变得便宜。

<a id="streaming"></a>

### Streaming

每个节点都可产生部分输出。 图形流的每个节点- delta 事件会向调用器发送, 这样UIs 就会随着图形运行而更新 。

<a id="human-in-the-loop"></a>

### Human-in-the-loop

检查和修改节点之间的状态。 执行: 在关键节点前暂停, 向人表面状态、 接受修改、 恢复。 检查器让这一点容易, 因为状态已经序列化 。

<a id="memory"></a>

### 内存

短期(在跑步中——州里的对话历史)和长期(交叉运行——通过检查站坚持,加上一个单独的长期商店)。 LangGraph 通过工具与外部内存系统(Mem0,自定义)整合。

<a id="three-topologies"></a>

### 三个主题

1. **Supervisor.** 中央路由器 LLM 发送到专家 subagents. `create_supervisor()` 在 `langgraph-supervisor` (虽然 LangChain 2026年的队伍建议通过 tool calls )直接用于更多的上下文控制)。
2. **Swarm /对等的对等。** Agents 直接通过共享工具表面手动。 没有中心路由器 。
3. **Hierarchical.** 管理子监督的主管,作为嵌套子执行。

<a id="where-this-pattern-goes-wrong"></a>

### 哪里有这种模式

- **Checkpoints 太小了 , 有点小** 只有检查对话框才会转动工具状态, 记忆无法恢复。 完整状态必须序列化 。
- **非决定性节点。** 恢复假设节点输入产生相同的状态更新。 随机种子, 墙上时钟, 外部 APIs 一定要被俘虏
- **过度使用条件边缘。** 每个边缘都有条件的图表是无法解释的状态机器。 branches.

```figure
langgraph-state
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行一个标准状态图 :

- `State` 打印的剪贴板 `messages`, `step`, `route`, `output`, `human_approval`.
- `Node` 呼叫状态和回覆更新的指令。
- `StateGraph` - 节点+边缘+条件边+运行+恢复。
- `SQLiteCheckpointer` (模拟假)——在每个节点之后都按顺序排列; `load(session_id)` restores.
- 演示图: 分类 - > branch(退款/错误/销售) - > 人类大门 - > 发送。

运行：

```
python3 code/main.py
```

该 trace 显示人类大门的第一次运行失败, 坚持, 然后恢复产生最终输出 。

<a id="use-it"></a>

## 实际应用

- **LangGraph** 参考, 制作准备。 `create_react_agent`, `create_supervisor`,或建立自己的图表。
- **AutoGen v0. 4 自动 Gen** (教训14) actor 高货币假设情景的模型替代。
- **Claude Agent SDK** (教训17)——管理 harness 内置会话仓库 。
- **Custom** - 当你需要精确控制 州形状或检查器后端。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-state-graph.md` 生成 a LangGraph- 任何目标运行时的形状状态图,有检查并恢复电线。

<a id="exercises"></a>

## 练习

1. 添加条件边距 `classify` 以 `end` 当分类信任度低于阈值时。 继续运行于人组之后 `route` manually.
2. 将像SQLite一样的假冒换成真正的 SQLite 检查站。 测量每一步的序列式管理 。
3. 执行平行边缘: 两个节点同时运行, 由自定义的减少器合并。 无法改变状态在这里购买什么 ?
4. Read `langgraph-supervisor` 参考文献。 `create_supervisor`比较 trace shapes.
5. Add streaming:每个节点在运行时产生部分状态。在到达时打印三角洲。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| 状态图 | "Agent 做为国家机器 | 键入状态+节点+边缘+减少量 |
| Checkpointer | "坚持后端" | 在每个节点后进行序列状态; 允许恢复 |
| Reducer | "国家合并" | 将当前状态与节点更新合并的函数 |
| 条件边缘 | "Branch" | 由状态函数选择的边缘 |
| Subgraph | "净图" | 用于另一个图形中的节点的图形 |
| Durable execution | "从失败中恢复" | 以准确状态在最后一个成功节点重新开始 |
| Supervisor | "Router LLM" | 专家中央调度员 subagents |
| Swarm | "P2P agents" | Agents 通过共享工具手动; 没有中心路由器 |

<a id="further-reading"></a>

## 进一步阅读

- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) 参考文件
- [langgraph- 监督员参考](https://reference.langchain.com/python/langgraph/supervisor/) 主管模式 API
- [AutoGen v0.4, 微软研究](https://www.microsoft.com/en-us/research/articles/autogen-v0-4-reimagining-the-foundation-of-agentic-ai-for-scale-extensibility-and-robustness/) — actor- 模型替代
- [Claude Agent SDK overview](https://platform.claude.com/docs/en/agent-sdk/overview) 届会商店和 subagents
