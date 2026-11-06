<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="group-chat-and-speaker-selection"></a>

# 群聊与发言者选择

> Shared-conversation orchestration 调出 N agents 在一个对话框中;选择函数(LLM,圆形或习惯)选择下一个发言的人。这是新兴多型的原型agent 对话 - agents 不知道他们的作用 在静态图,他们只是 react 共享集合。 AutoGen Gen GroupChat 和 AG2 GroupChat 是引用执行: AutoGen v0. 2 的组语义保存在 AG2 叉子里; AutoGen v0. 4 重写为事件驱动 actor 模型。 Microsoft 在2026年2月将自动Gen 引入维护模式, 并将其与语义内核合并为 Microsoft Agent 框架(RC 2026年2月)。 原始的集团在AG2和微软中都生存下来。 Agent 框架——学习一次,到处使用。

**类型:** 学习 + 构建
**语言:** Python (stdlib)
**先修要求:** 阶段16 -04(初级模型)
**时间:** ~60分钟

<a id="problem"></a>

## 问题

静态图(LangGraph当工作流程为人所知时,这是件好事。真正的对话不是静态的:有时代码员会询问审查者,有时是研究人员,有时是作家。 handoff 产生边缘爆炸。 *agents 与共享池子发生反应*,一些功能决定谁 下一个交谈。

这正是AutoGen Chat集团的工作。

<a id="concept"></a>

## 概念

<a id="the-shape"></a>

### 形状

```
              ┌─── shared pool ────┐
              │   m1  m2  m3  ...  │
              └─────────┬──────────┘
                        │ (everyone reads all)
      ┌───────┬─────────┼─────────┬───────┐
      ▼       ▼         ▼         ▼       ▼
    Agent A  Agent B  Agent C  Agent D  Selector
                                           │
                                           ▼
                                  "next speaker = C"
```

每个 agent 查看每个消息。 在每个转弯处都会引用选择函数来选择下一个发言的人 。

<a id="the-three-selector-flavors"></a>

### 三种选调

**Round-robin.** 固定周期。 确定性。 在 N 中直线缩放, 但忽略了上下文, 代码员即使话题是法律审查, 也会得到转折 。

**LLM-selected.** 呼叫一个 LLM ,然后返回下一个最佳的发言者。 LLM 电话,自动Gen的默认

**Custom.** 一个 Python 函数的逻辑值。 LLM- 以备用规则选择(例如,“总是在代码员之后让验证人转弯”)。

<a id="the-conversableagent-api"></a>

### 易言的代理 API

```
agent = ConversableAgent(
    name="coder",
    system_message="You write Python.",
    llm_config={...},
)
chat = GroupChat(agents=[coder, reviewer, tester], messages=[])
manager = GroupChatManager(groupchat=chat, llm_config={...})
```

`GroupChatManager` 持有选择器。 agent 完成一个转折, 管理器会调用选择器, 返回下一个 agent循环持续到 termination condition.

<a id="termination"></a>

### Termination

三种常见模式:

- **马克思子弹** 完全转弯的硬帽
- **"TERMINATE" token.** Agents 能够发送一个寄件信息; 管理器在出现时停止 。
- **目标检查。** 轻量级验证器每转一次 就会停止聊天

<a id="lineage-forks-and-mergers"></a>

### 线条:叉子和合并

2025年初,微软围绕一个事件驱动的版本开始对AutoGen(v0.4)进行主要改写 actor 模式。 社区被AutoGen v0. 2的 GroupChat 语义作为 AG2 保存 API 早期收养者已经融合了

2026年2月,微软宣布AutoGen将使用维护模式,由事件驱动 actor 模式合并为 **Microsoft Agent Framework** (RC 2026年2月, 现在与语义核心部分合并) GroupChat 概念在两个轨道上都存在; 执行细节不同。 AG2 是 v0. 2 兼容代码的首选上游 。

<a id="when-groupchat-fits"></a>

### 当组热合时

- **刚开始的谈话** 你不会想预接下一位演讲者的
- **角色混合任务。** 代码员问研究员, 搜索员问档案员, 归档员问密码员回来。 流程不是 DAG 。
- **探讨解决问题的办法。** 想想"脑风暴会议",而不是"集合线"

<a id="when-it-fails"></a>

### 失败时

- **严格地确定** 该 LLM 选择器可能不一致。 prompt,不同的运行,不同的下个扬声器。
- **血吸力级联** Agents 顺从那些最自信的人prompt explicitly.
- **上下文浮肿。** 每个 agent 读取每个信息; 在 10 个之后, 上下文会变得巨大。 使用预测( 课程 15) 到范围视图 。
- **热扬声器** One agent 选择者偏好其专业,所以主导了对话。 feature.

<a id="group-chat-vs-supervisor"></a>

### 组聊天对管理器

相同的原始,不同的默认值:

- 主管:一 agent 选择者是"问计划者该怎么做"
- 分组聊天:全部 agents 是一个对等点;选择器是共享池上的函数。

使用4个原始的 04 课。 LLM-selected orchestration 和全池共享状态。

```figure
swarm-speaker
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行一个组的“从头开始” 。 agents 转环和转环(编码、审查、管理) LLM- 选择的变体,和终止 `TERMINATE` token.

演示打印了谈话记录 加上选手的决定 trace 两种变体都一样。

Run:

```
python3 code/main.py
```

<a id="use-it"></a>

## 实际应用

`outputs/skill-groupchat-selector.md` 配置给定任务组域选择器——圆形对齐 LLM- 选择与自定义,以及选择输入(最近的信息, agent 特殊性, 转数) 。

<a id="ship-it"></a>

## 交付成果

Checklist:

- **马克思圆帽。** 总是,10 -20 对于典型的任务。
- **议长平衡度。** 音轨旋转 agent; 当不平衡超过阈值时提醒 。
- **Termination token.** `TERMINATE` 或专用验证器 agent.
- **投影或范围内存。** ~ 10 条信息后, 考虑给每个 agent 仅用于防止上下文浮肿的范围视图。
- **选择记录 。** 用于 LLM- 选择变量, 记录选择方输入和选择。 否则无法调试 。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。比较圆环对圆环的谈话 LLM- 选的 agent 每一个下面都占优势?
2. 添加“ 最大语句 ”agent规则在选择者中 它对笔录有什么影响?
3. 执行一个达到目标的终止: 当审查者返回“ 批准” 时停止。 它在圆顶前多久触发一次 ?
4. 阅读 AutoGen 稳定版文档中的 GroupChat 说明（ https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/group-chat.html ），指出 `GroupChatManager` 默认使用哪种选择器。
5. 读取 AG2 回收( A)https://github.com/ag2ai/ag2) 并将其 v0. 2 GroupChat 与 v. 4 事件驱动版本进行比较。 v. 4 添加了什么具体属性( 吞吐、 过错容忍、 可调制) ?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| GroupChat | "Agents 在一个聊天室里 | 共享信件库 + 选择器功能。 AutoGen / AG2 原始功能。 |
| 选择演讲人 | "谁说下一个" | 选择下一个函数 agent圆柱形, LLM- 选择,或习惯。 |
| GroupChatManager | 主办人 | 自动 Gen 组件, 拥有选择器并旋转旋转 。 |
| ConversableAgent | "基地" agent" | 自动Gen 基级; a agent 它可以发送和接收信息。 |
| Termination token | "停止"这个词 | 哨兵字符串( 通常) `TERMINATE`结束谈话 |
| 热扬声器 | "One agent dominates" | 选择者不断选择失败模式 agent. |
| 上下文浮点数 | "无敌的猪" | 每个 agent 读取先前的每一个信息; 上下文随转动而增长。 |
| 投影 | "扫荡的风景" | 将特定角色观点纳入共享池,以防止上下文浮肿。 |

<a id="further-reading"></a>

## 进一步阅读

- [自动 Gen 组聊天文档](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/group-chat.html) 参考执行情况
- [AG2 回收](https://github.com/ag2ai/ag2) 社区AutoGen v0.2 续延
- [Microsoft Agent 框架文件](https://learn.microsoft.com/en-us/agent-framework/) 合并后的继任者RC 2026年2月
- [AutoGen v0.4 发布便条](https://microsoft.github.io/autogen/stable/) 活动驱动 actor 模式重写细节
