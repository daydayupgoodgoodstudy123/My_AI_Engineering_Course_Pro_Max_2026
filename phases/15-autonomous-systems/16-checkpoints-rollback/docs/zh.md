<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="checkpoints-and-rollback"></a>

# Checkpoints（检查点）与 Rollback（回滚）

> 每一个图状状态的转变都持续。 当工人崩溃时,其租约到期,而另一个工人最晚会来接 checkpoint。 云层中持久的物体保持数小时或数周的状态。 提议- 即commit (第15条) 定义 rollback 行动后核查结束循环。 欧盟《大赦国际法》第14条规定,对高风险系统必须进行有效的人力监督。 checkpoints 必须是可查询的, rollbacks 必须排练,审计线索必须能够幸存。 严重故障模式: 没有 idempotency 键和先决条件检查, 过瞬时故障后重试可以双倍执行已经批准的动作。 操作后验证是它所抓住的 。

**类型:** 学习
**语言:** Python (stdlib, checkpoint 和 rollback 状态机器)
**先修要求:** 阶段15 · 12 (Durable execution15(提出时-commit)
**时间:** ~60分钟

<a id="the-problem"></a>

## 问题

Durable execution (教训12) 坠毁 agent 还可以再现,然后...commit (教训15) 使得一个已核准的行动可以审计。 此课程也与它们相联: 当被批准的行动执行部分、 崩溃和恢复时会发生什么 ? rollback 跑步,反向哪个州?

真正的系统 将这个连接起来不同:

- **LangGraph** checkpoints 每一个图形状态转换到 PostgreSQL。 在工人崩溃时, 租赁解除和另一个工人最晚恢复 checkpoint工作流暂停 `interrupt()`也让它继续存在
- **云花耐久物体** 保持每小时或每星期的状态。 与已核准动作的存储点一起使用计算 。
- **Microsoft Agent Framework** exposes `Checkpoint` 工作流程中的原始元素 API; 重放加 idempotency 覆盖重试。

在所有情况下,实际有效的组合是: idempotency 键(防止双重执行)+先决条件检查(状态仍然是我们批准的对照)+行动后核查(实际发生了副作用)+ rollback 被证实失败

<a id="the-concept"></a>

## 概念

<a id="every-transition-persists"></a>

### 每一个过渡都持续

图形状态转换是将工作流程从一个指定状态移动到另一个状态的任何步骤。 仅在特定情况下才持续执行 。 commit 点; 生产实施会持续到每个过渡阶段。 相对于可靠性收益而言,成本( 少数额外写作) 很小( 重放任何地方的土地, 租赁回收是准确的 ) 。

<a id="lease-recovery"></a>

### 收回租赁费

当工人崩溃时,工作流程不会丢失;租赁(该工人正在运行的短期索赔)只是过期了。 checkpoint 租赁机制是让生产系统在不损失飞行工作的情况下进行滚动部署。

<a id="idempotency-plus-preconditions"></a>

### Idempotency 附加先决条件

Idempotency 仅靠单是是不够的。 考虑: 工作流程被批准“ 当余额 > 1 000 时, 将100美元从 A 转到 B 。 ” 工作流程被投入, 中执行时崩溃, 并恢复 。 如果只有此选项的话 idempotency 键被检查,执行恢复后,传输运行一次(正确)。但考虑到在崩溃和恢复之间,A的余额会通过不同的工作流程下降到500美元。 idempotency 检查仍然通过; 先决条件没有。 没有先决条件检查, 我们就会发一笔透支 。

由此采取的每一项行动都需要:

- **Idempotency key**:防止双向执行。
- **先决条件检查**:确认国家仍然符合批准的内容。

<a id="post-action-verification"></a>

### 行动后核查

“ 返回的200” 工具不是验证。 真正的验证会重新读取目标状态并确认实际发生了副作用 。 模式 :

- 数据库更新 : `UPDATE ... RETURNING *` 然后声明返回的行匹配预想状态 。
- 电子邮件发送: 检查提交后信件编号的已发文件夹 。
- 文件写入: 读取文件并进行杂交 。
- API 电话: 后续行动 `GET` 目标资源。

如果校验失败, 工作流程将处于已知的坏状态 。 Rollback engages.

<a id="rollback-plans"></a>

### Rollback plans

之后的每件事commit (教训15)携带 rollback 计划。 类型 :

- **In-band rollback**: 直接倒转副作用(`DELETE` 之后 `INSERT`, `Send-correction-email` ) 发函后)。
- **补偿交易**:一个能够抵消原始(标准 SAGA 模式)的新动作。
- **Out-of-band rollback**:提醒人,暂停工作流程,让坏状况调查。

No-op rollback (“ 我们无法撤销此选项 ” ) 必须写入提案。 行动没有 rollback 需要更强的 HITL 时间 commit 时间(第15条挑战与回应)。

<a id="eu-ai-act-article-14-operational-reading"></a>

### 《欧盟大赦国际法》第14条操作读法

第十四条要求对高风险系统进行“有效的人的监督”。

- Checkpoints 由审计员查询。
- Rollbacks 进行排练(至少一次试验到最后)。
- 审计线索在部署中得以维持(见A/C.5/49/70,第1段)。checkpoint 后端不是短时间)
- 验证失败时会提醒,而不是静悄悄地登录。

中途崩溃的工作流程commit,并完成副作用,而没有校验+ rollback 路径无法经受第十四条的考验。

<a id="the-sharp-failure-mode-the-double-execute"></a>

### 锐性失败模式: 双向执行

最常见的制作事件在这个空间:

1. 核准的行动, idempotency 键 K。
2. Commit 开始,执行,返回200。
3. 工作流量在维持“承诺”状态之前就崩溃了。
4. 工作流量恢复; 查看“ 核准但未执行”; 重新执行 。
5. 副作用两次开火

减轻:在处决前坚持“飞行中”的意图, idempotency 键,然后在操作后验证成功后才标记“ 承诺 ” 。 如果动作火灾和状态写作失败, 您知道验证和( 如果必要)再射击。 如果状态写入成功且操作失败, 您会通过恢复路径来核实并精确地射击一次 。

```figure
checkpoint-replay
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 执行一个已检查的工作流程 idempotency、先决条件、核实和 rollback。驱动程序模拟四种情景:干净运行,崩溃后重试(idempotency 测试失败(未开关的流程中断)rollback fires).

<a id="ship-it"></a>

## 交付成果

`outputs/skill-rollback-rehearsal.md` 设计a rollback- 拟议的工作流程的排练测试和审计 checkpoint 用于审计拖累性后端。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。验证四个假设。对于坠机期间 --commit 情况,确认动作火 准确的一 跨重覆。

2. 修改“ 先标记, 然后做 ” 模式, 这样状态会写出动作后发生的火灾。 重运行崩溃的情景。 测量有多少重复动作 。

3. 设计a rollback 计划特定生产行动(例如“加入黑频道”)。分类为带内、补偿或带外。说明选择的理由。

4. 选择一个您知道的工作流程。 确定每个状态过渡。 标记每个状态的周期需要持久性( 永久/ 不持续) 。 计算您目前没有持续的工作 。

5. Rehearsed-rollback 测试:设计一个端到端的测试,运行一个真正的工作流程,崩溃它,并证实 rollback 路径火灾。测试证实什么?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| Checkpoint | 拯救点 | 每个图状状态的过渡 都持续到耐久商店 |
| Lease | “工人索赔” | 工人执行跑步的短期索赔;坠机时失效 |
| Precondition | 国家大门 | 声称国家仍然符合批准的行动 |
| 行动后核实 | 重新读取检查 | 确认目标系统中实际发生的副作用 |
| In-band rollback | "直接解脱" | 反转反转操作的副效果 |
| 补偿交易 | "SAGA 解码" | 一种能抵消原始 |
| Mark-as-done-first | "状态写作命令" | 在返回之前,坚持已承诺的地位 commit |
| 第14条 | "欧盟AI 人类监督" | 操作: 可查询 checkpoints排练 rollbacks可审计跟踪 |

<a id="further-reading"></a>

## 进一步阅读

- [Microsoft Agent 框架——检查和高级信息技术](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop) — checkpoint 原始的和租赁回收。
- [Cloudflare Agents - 人进入循环](https://developers.cloudflare.com/agents/concepts/human-in-the-loop/) - 耐久物体作为国家基质。
- [欧盟大赦国际法——第14条:人的监督](https://artificialintelligenceact.eu/article/14/) 管理基线。
- [Anthropic 计量 agent 实际的自主权](https://www.anthropic.com/research/measuring-agent-autonomy) 长视距工作流程的可靠性框架。
- [Anthropic — Claude Code Agent SDK: agent loop](https://code.claude.com/docs/en/agent-sdk/agent-loop) 工作流量形状 Claude 密码路由
