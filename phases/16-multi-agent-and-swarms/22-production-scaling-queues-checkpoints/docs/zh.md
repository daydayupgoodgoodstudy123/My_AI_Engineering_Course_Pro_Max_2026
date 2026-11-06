<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="production-scaling--queues-checkpoints-durability"></a>

# 生产扩展：队列、Checkpoints 与持久性

> 缩放多agent 需要使用系统到千个同时运行 **durable execution** - 工作队列加 checkpoints,因此任何工人在任何碰撞后都可以恢复运行,只要租赁处理、一流的副作用和决定性的重播就位。 LangGraph运行时间是引用示例: 它写了 checkpoint 之后的每一个超级步骤键 `thread_id` 工人意外事故释放了租约,另一名工人恢复工作。 Agents 能够无休止地等待人类输入 **MegaAgent** (arXiv:2408.0955)每agent 由三个州组成的生产者-消费者队列(Idle/ processional / response)和两层协调(小组内部聊天+小组之间行政聊天)。 **Fiber/async** 跳过每份工作 LLM streaming:线条闲置,等待时间的99% tokens反点:Ashpret Bedi的“扩大” Agentic 软件“ 论证 **FastAPI + 邮戳+无其他** 直至负荷证明相反,简单的建筑比预期的要远。 checkpoint 日志, 每 -agent 以州过渡方式, 以 Async-vs-thread 演示方式, 进行工作排队, 并设定实用的“ 启动简单” 规则 。

**类型:** 学习 + 构建
**语言:** Python (stdlib, `asyncio`, `sqlite3`)
**先修要求:** 阶段16 -09(帕拉莱尔) Swarm 网络,第16阶段 · 13(共享记忆)
**时间:** ~75分钟

<a id="problem"></a>

## 问题

原型多功能agent 系统在一台手提电脑上工作,三台 agents 在一个模拟事件循环中。您移动到制作:

- Agents 有时跑几个小时(长期研究, human-in-the-loop waits).
- 工人处理崩溃。 重新开始会丢失状态 。
- 峰值负载为平均10倍;需要水平缩放。
- 用户付费 agent- 跑,你需要完全的语义来充电。

模拟事件循环没有这些。 您需要一个 durable execution 2026年的金刚石选项是:

1. 工作流程引擎 checkpoints (Temporal, LangGraph runtime).
2. 带有状态存储的邮件队列( Postgres + SQS/RabbitMQ) 。
3. Actor- 示范框架(按每份 agent).
4. Hand-rolled FastAPI + Postgres(贝迪的论据)。

这课可以建立每个小的缩影

<a id="concept"></a>

## 概念

<a id="durable-execution-the-pattern"></a>

### Durable execution,该图案

耐久执行引擎保持了每个“ 步骤” 之后的整个程序状态( 超步骤, 英寸) LangGraph语言 。 崩溃时 :

```
worker crashes mid-step
  -> lease timeout
  -> another worker picks up the thread_id
  -> resumes from last checkpoint
  -> no duplicate side effects
```

这项工作的要求:

- **连环状态** 所有 agent state 功能关闭, 连接到数据库 无法生存 。
- **决定性的复演** 以同样的状态和相同的投入, agent 产生相同的动作(或服从外部的确定性神谕) LLM calls).
- **同上,《能动副作用》。** 外部电话(tool calls,支付)必须是一无所有或使用重复键。

LangGraph 写 checkpoint 在每个超级步骤之后; 时间性在每次活动之后写作; 重报使用事件源日记。 所有三个都执行相同的模式 。

<a id="a-checkpoint-per-step-runtime"></a>

### 一个 checkpoint- 一步步运行时间

LangGraph运行时间是工作的例子: agent 已经有一个 `thread_id`; 状态是打印的编辑器; 每个超级步骤都写上一行到 checkpoints 表格。在简历中,运行时间重播 checkpoint而不是从头开始 Agents 可以 `interrupt()` 等待人的投入;运行时间持续并释放工人。 当输入到达时,任何工人都可以恢复工作。

这是2026年4月的参考生产设计。

<a id="megaagents-per-agent-queue"></a>

### 巨型代理商的每 -agent queue

arXiv:2408.0955 表示一个比例实验:千个同时进行 agents 在一个组中。 结构 :

```
agent i:
  state ∈ {Idle, Processing, Response}
  in_queue   <- messages addressed to agent i
  out_queue  -> replies + side effects

coordinators:
  intra-group chat  (agents in the same group)
  inter-group admin chat  (high-level routing)
```

由两层协调进行,使集团内部对话发生频繁,而集团之间则保持稀少——这种模式用于维持数千种成本线性。 agents.

<a id="async-vs-thread-per-job"></a>

### 工作时的线条

LLM 电话是I/O-l发的,还有一条线等着下一个 token 闲置时间为99%。线索费用为每只~1MB 内存;同时通话10,000次,即10GB只用于堆叠。

纤维( 纤维)Python `asyncio`去吧,去古龙水 Rust `tokio`合作地向I/O投放。 同样的10,000个电话在进行过程中是舒适的。 LLM-agent 规模,自动合成不是优化——这是建筑。

Exception: CPU- 运出后处理(embedding, tokenizer 技巧)仍然需要线索或进程。您需要的 I/ O 层与您的 CPU layer.

<a id="bedis-counterpoint"></a>

### 贝迪的反面点

"Scaling Agentic 软件(Ashpreet Bedi, 2026)认为,大多数团队在测量负荷之前就超编了。

- FastAPI + 邮戳。
- 每个 agent 运行为一行; 状态更新, 带有乐观的同价货币 。
- 通向背景工作 `pg_notify` 或一个简单的西莱里工人。
- 重试应用代码中的策略 。

以 ~ 100 下同时值装载 agent- 运行在可控的任务上, 这通常是你所需要的。 当测量失败时, 升级 。

规则: 当遇到一个简单的建筑无法解决的具体问题时, 采用耐久执行框架。 过早的收养会让那些没有回报的仪式燃烧时间 。

<a id="exactly-once-semantics"></a>

### 完全一成不变的语义

付账 agent 运行时, 您需要“ 一次有效 ” ( 至少在一次交付时 + 一流的消费者) 。 工程动作 :

- **每一运行的丁字串键 。** 把它纳入每个副作用的呼叫。
- **发件箱模式。** 副作用先写到表格,然后单独执行。这两个步骤都是适当的。
- **补偿交易。** 当副作用成功,但跟踪失败时,请安排补偿。

这些是数据库工程模式,不是 LLM- 特殊,特别 LLM 税是仅此而已 LLM 电话很慢,其他的都是标准分布系统

<a id="rainbow-deployment"></a>

### 彩虹部署

Anthropic多重 - 数agent 研究系统使用“脑电荷部署”: agent 运行时间同时进行,如此长的运行 agents 不需要在每次代码部署中都杀死。 加那利语新版本的流量部分; 当旧版本被淘汰时, 退出它们 。 agents finish.

这是长期运行的状态系统的标准;2026年的适应性是 agents 能够维持数小时,因此部署周期必须适应。

<a id="the-canonical-production-checklist"></a>

### 银河生产清单

- 国家(续)checkpoints,快照,或发件箱+可重播日志)。
- 同上,《能动副作用》。
- 自动I/O层 LLM calls.
- 起码一次送货,还有分头
- 彩虹/卡纳里用于有状况的工作量。
- Observability: 每-agent traces超级审计,重试计数器

```figure
sw-checkpoint-replay
```

<a id="build-it"></a>

## 动手实现

`code/main.py` implements:

- `CheckpointStore` - 以 SQLite 支持 checkpoint 带有线索标识键的日志。 每个超级步骤都附加一行 。
- `run_with_checkpoint(agent, thread_id)` 模拟中途坠毁; 上个工人恢复 checkpoint.
- `AgentQueue` — 每-agent 工作队列小的空闲/处理/反应状态机器。
- `demo_async_vs_threads()` - 运行500个同时模拟的 "LLM 透过音频和线条调用;报告墙上时钟和峰值内存(接近)。

Run:

```
python3 code/main.py
```

预期产出: checkpoint 模拟崩溃后恢复成功; 同步版本处理500个同时调用 < 1s; 线索版本需要几秒钟, 并使用数量级增加的每同时单元内存 。

<a id="use-it"></a>

## 实际应用

`outputs/skill-scaling-advisor.md` 有关持久执行选择的建议: FastAPI + 邮戳, LangGraph 运行时间、 时间或习惯。 校准为负载、 状态保留需求及部署频率 。

<a id="ship-it"></a>

## 交付成果

火药生产加固:

- **开始简单( Bedi 规则) 。** FastAPI + Postgres + 直到测量失败。
- **最优化前要先把一切工具都装好** 运行的潜伏直方图, 一步步时间, 重试计数, 失败分类 。
- **副作用的发件箱模式。** 特别是付款和外部 API calls.
- **彩虹部署** 绝不在飞行中杀人 agent 部署期间运行。
- **采用耐久性执行引擎(临时/临时) LangGraph / 重报)** 遇到特殊问题:小时 human-in-the-loop 等待、跨区域协调、复杂的重试/补偿政策。
- **静脉注射I/O层** 线索仅用于 CPU- 运到后处理

<a id="exercises"></a>

## 练习

1. Run `code/main.py`确认 checkpoint 恢复工作; 测量 async 和 线性 共通货币差异 。
2. 执行 **outbox** 表格:每张 tool call 先写给发件箱, 然后单独执行一个 Groutine/ task 执行 。 idempotency 运行 tool call twice.
3. 模拟 **彩虹部署**:两个同时运行的时间版本;新线条的一半_每项编号; 确认旧版本上的飞行线条没有中断 。
4. Read LangGraph运行时间 doc( 链接到下面) 。 确定 features 使用手动复制时间最长 FastAPI + Postgres 版本。 这是收养的理由, 还是您可以推迟?
5. 读取大Agency(arXiv:2408.0955)第3节,两层协调(小组内部+小组间行政聊天)是明确的。您如何将它映射为有两个队列的队列 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|------|----------------|------------------------|
| Durable execution | 坚持程序状态 | 引擎在每个超级步骤后都写状态; 崩溃恢复是决定性的。 |
| Super-step | “交易边界” | 工作单位 checkpoints. LangGraph term. |
| thread_id | "Agent 运行标识符" | 绑定的密钥 checkpoints 并恢复逻辑。 |
| Idempotency | "重试安全" | 重复副作用产生的结果与一次尝试相同。 |
| 发件箱模式 | "十倍副作用" | 将意向写入表格; 单独的执行人进行操作并完成标记 。 |
| 至少在交货后 | "可能重复" | 信件队列语义; 分隔键使消费者能够一次有效 。 |
| 彩虹部署 | "重叠版本" | 在长期工作量期间同时使用多个运行时间版本。 |
| 松动纤维 | "合作生产" | 用户模式的组合货币; I/O 运入负荷的线条比值低。 |
| Checkpoint | "国家快照" | 处于超步骤边界的序列状态; 恢复的密钥 。 |

<a id="further-reading"></a>

## 进一步阅读

- [LangChain 生产落后的时间 agents](https://www.langchain.com/conceptual-guides/runtime-behind-production-deep-agents) — LangGraph 运行时间设计
- [MegaAgent](https://arxiv.org/abs/2408.09955) — 每-agent 生产者-消费者队列;两层协调,同时进行数千次 agents
- [Matrix](https://arxiv.org/abs/2511.21686) 分散框架,以信息队列作为协调的基底
- [时间值](https://docs.temporal.io/) 参考工作流程引擎 durable execution
- [Anthropic - 多重 - 多重 -agent 研究系统](https://www.anthropic.com/engineering/multi-agent-research-system) 生产经验,包括彩虹部署
