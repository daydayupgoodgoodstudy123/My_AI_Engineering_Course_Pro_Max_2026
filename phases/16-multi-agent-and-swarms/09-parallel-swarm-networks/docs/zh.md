<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="parallel--swarm--networked-architectures"></a>

# 并行、Swarm 与网络化架构

> 与主管对质:没有中央决定者。 Agents 阅读共享活动巴士, 以不同步的方式接下工作, 写回结果 。 LangGraph 明确支持 "Swarm 用于分散、 动态环境的架构。 矩阵( arXiv: 2511.21686) 代表着通过分布式队列传递的串联信件的控制和数据流, 以消除管弦乐瓶颈。 权衡是明确的: 确定性和可缩放性的可追踪性 。 Swarm 任务与许多独立的次级问题相适应;它不符合需要单一连贯计划的任务。

**类型:** 学习 + 构建
**语言:** Python (stdlib, `threading`, `queue`)
**先修要求:** 阶段16 -05(高级模式),阶段16 -04(初级模式)
**时间:** ~75分钟

<a id="problem"></a>

## 问题

监督员的比重是少数工人。 大约几百个呢? 监督员本身就成了瓶颈: 每一个决定谁做漏斗 通过一个 agent计划缓慢,整个系统就会停顿

Swarm 结构翻转设计。 工人不选择中央规划员发送工作, 而是选择一个共享队列。 “ 协调” 被烤进了事件总线的语义 。 没有管弦; 系统比例直到队列完成 。

<a id="concept"></a>

## 概念

<a id="the-shape"></a>

### 形状

```
                ┌──── shared queue ────┐
                │                      │
       ┌────────┼────────┐  ◄──────┬───┘
       ▼        ▼        ▼         │
     Worker  Worker  Worker   Worker
      A       B       C        D
       │        │        │         │
       └────────┴────────┴─────────┘
                 │
                 ▼
            results pool
```

没有指挥员。 每个工人重复: 拉出任务、进程、写结果( 以及可选的排队跟踪) 。

<a id="when-swarm-fits"></a>

### 当 swarm fits

- **许多独立的任务。** 剪切、转换、分类。任务不取决于彼此。
- **工作时间可变。** 如果有些任务需要100米,而另一些则需要10秒,a swarm 平衡自动负荷——快速工人拉下工作。主管必须预测时间长度。
- **超越决定性的极限** 你关心的是完成时间,而不是严格命令

<a id="when-swarm-fails"></a>

### 当 swarm fails

- **有序的工作流程。** 如果第3步需要第2步输出,a swarm 危险第3步在第二步完成前开火
- **全球计划任务。** 复杂的研究问题得益于规划者。 swarm 研究者提出独立的事实,而不是连贯的报告。
- **Debugging.** 没有中央日志和无同步工作,复制一个虫子费用昂贵。

<a id="matrix-arxiv251121686"></a>

### 矩阵(arXiv:2511.21686)

矩阵是2025年的论文 swarm 自动得出: 控制流和数据流都是分布式队列上的序列信息。 没有中央协调器。 错误容忍度来自信件的耐久性。 缩放性是信息经纪人的问题, 而不是系统的问题 。

贡献:一个方案模式,其中涉及多个agent 协调是"什么信息主题做这个 agent 订阅吗? 而不是"什么" agent 系统看起来就像酒吧/活动网格。

<a id="swarm-in-graph-frameworks"></a>

### Swarm 图表框中

LangGraph 2025年的医生明确描述 "Swarm 建筑"是多功能之一agent patterns: agents 是一个结点,但边缘会形成一个带周期的定向图形,任何节点都可以从池子里激活。工人可以按条件而不是根据主管任务从现有工作中挑选。

<a id="failure-mode-starvation-and-hot-spotting"></a>

### 失败模式:饥饿和热点

如果所有工人都拉了最快的任务,那么长期任务就永远得不到选择,直到他们是唯一剩下的。 典型的排队饥饿。

Mitigations:
- 明显老化的优先排队( 等待时间后增加优先排队) 。
- 工人专业:有些工人只承担“长期”任务。
- 后压: 限制队列中有多少任务快速输入 。

<a id="the-content-based-routing-link"></a>

### 基于内容的路径链接

Swarm 配对自然带有基于内容的路径( Lesson 22) 。 与通用队列不同, 每个信件类型有一个队列。 专业工人只订阅其类型。 这是以千位 agents.

```figure
sw-work-stealing
```

<a id="build-it"></a>

## 动手实现

`code/main.py` 执行a swarm 4个工人线从一个共享的 `queue.Queue`。任务有可变的长度(有些是快速的,有些是慢的)。

- **序列基线 :** 一名工人连续处理所有任务。
- **固定任务:** 每项任务事先指定给特定工人(监督型)。
- **Swarm:** 工人从一个共同的队列中拉出来。

Swarm 余额自动负荷; 固定任务让快速工人在指派任务缓慢时闲置。

Run:

```
python3 code/main.py
```

输出显示每个工人的任务计数( )swarm 分配不均,但最优)和墙上时钟。

<a id="use-it"></a>

## 实际应用

`outputs/skill-swarm-fit.md` 评估任务是否应该使用 swarm 输入:任务独立、期限差异、订购要求、调试性需求。

<a id="ship-it"></a>

## 交付成果

Checklist:

- **排队排队时老了** 防止长途饥荒
- **Worker idempotency.** 如果工人在中途坠毁,任务可能会被多次拖动。工人必须有能力。
- **长队列** 使用 Kafka、 Redis 流或数据库支持的队列来制作 。 `queue.Queue` 仅仅是记忆中的。
- **Observability 每项任务。** 每一个任务都有 trace ID; 每个工人日志都以它开始/结束 。
- **Back-pressure.** 如果排队的速度比工人排的快 就会让制片人慢下来

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。多快是 swarm 相对于依次的可变期限工作量?比固定任务快多少?
2. 添加优先队列变量( 使用) `queue.PriorityQueue`))通过任务“重要性”字段指定优先级。观察低优先级任务是否在连续负荷下断绝。
3. 执行热点检测器: 当任何工人处理比最慢的工人多3x的任务时, 记录。 这表示任务期限分布是什么 ?
4. 阅读矩阵文件(arXiv:2511.21686)摘要和第三节。 确定一个特定的权衡矩阵接受(可扩增),一个放弃(可追踪性、确定性)。
5. 转换 swarm 演示以使用 `queue.Queue` 任务_使用特定类型。 当任务不一时,什么路线规则才有意义?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Swarm architecture | "Decentralized agents" | 工人从共同队列中拉出来;没有中央指挥员。 |
| 事件总线 | "Agents 订阅主题" | 信息经纪人,按类型或内容将任务传递给工人。 |
| Starvation | "任务从不运行" | 低优先的任务从未被挑选,因为高优先的工作不断到来。 |
| Hot-spotting | "一个工人淹死" | 将一个工人承担大部分任务的地方加载不平衡。 |
| Back-pressure | 慢点,慢点 | 信号在上游的装置 停止生产 当排队填满。 |
| 同上,有能力工人 | "安全重开" | 两次处理的任务产生相同的结果。 需要的是工人可能中途坠毁。 |
| 耐久队列 | 幸存者坠毁 | 以磁盘或复制存储为后盾的队列; 工人崩溃时任务不会丢失 。 |
| 矩阵框架 | 传递完整信息 swarm" | 数据和控制流程都是分布式队列上的序列信息。 |

<a id="further-reading"></a>

## 进一步阅读

- [LangGraph 工作流程和 agents — Swarm Architecture](https://docs.langchain.com/oss/python/langgraph/workflows-agents) - 明确 swarm support
- [矩阵——多功能分散框架Agent Systems](https://arxiv.org/abs/2511.21686) 完整信息传递 swarm
- [Anthropic 工程——为什么主管不 swarm 研究组](https://www.anthropic.com/engineering/multi-agent-research-system) -为什么一个具体的生产系统明确选择监督员而不是 swarm
- [AutoGen v0. 4 自动 Gen actor- 模范医生](https://microsoft.github.io/autogen/stable/) 活动驱动 actor 重写, 靠近 swarm 大于 v0. 2 的群件附件
