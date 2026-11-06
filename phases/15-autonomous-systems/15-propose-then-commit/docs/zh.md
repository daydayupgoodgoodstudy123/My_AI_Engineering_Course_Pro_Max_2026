<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="human-in-the-loop-propose-then-commit"></a>

# Human-in-the-Loop：先提出方案，再 Commit

> 2026年关于HITL的共识是具体的。 agent 用户点击“批准” 。 这是提议commit:拟议行动将持续到一个耐久的仓库,并有一个 idempotency 键; 表面上显示为有意审查者, data lineage,允许被触碰,爆炸半径和 rollback 计划; 仅在确认后实施; 执行后核实以确认实际发生了副作用。 LangGraph的 `interrupt()` 加PostgreSQL 检查,微软 Agent Framework's `RequestInfoEvent`和云花的 `waitForApproval()` 全部执行相同的形状。 弹簧故障模式是橡胶标记的核准 : “ 验证” 。 不经审查点击。 记录下来的缓解是使用明确的核对表进行挑战和回应 。

**类型:** 学习
**语言:** Python (斯迪利布,提议 - 然后...commit 状态机器 idempotency)
**先修要求:** 阶段15 · 12 (Durable execution15阶段 14(铁丝网)
**时间:** ~60分钟

<a id="the-problem"></a>

## 问题

一个 agent 采取一项行动。 用户必须决定: 是否批准。 如果决定是即时的, 它可能不是一次审查。 如果决定是结构化的, 它会缓慢但可信。 工程问题是如何对阻力最小的路径进行结构化审查 。

2023年的 HITL 模式是同步的 prompt: "Agent 想要用身体 Y 发送电子邮件给 X , 批准吗? 用户点击“ 核准 ” 。 每个人都觉得系统是安全的。 实际上, 这个表面被大量橡皮标印: 用户快速批准, 批准预测很少, 当用户批准时 agent 错误的是,审计线索显示,用户无法回忆到很长的核准历史。

2026年的模式,然后...commit - 将 HITL 移动到耐久基底, 附加结构化元数据, 并且需要正值 commit. 每一个管理好的 agent SDK 船舶版本 : LangGraph `interrupt()`微软 Agent Framework `RequestInfoEvent`云雾 `waitForApproval()`. 该 API 名称不同; 形状没有。

<a id="the-concept"></a>

## 概念

<a id="the-propose-then-commit-state-machine"></a>

### 提议...commit 状态机器

1. **Propose.** Agent 生成一个拟议动作。 持续到一个耐久仓库( PostgreSQL, Rediis, 耐久对象) 。 包括:
   - 意图(为何 agent 这样做)
   - data lineage (是什么来源导致提出这项建议)
   - 被触动的权限( 范围/ 文件/ 终点)
   - 爆炸半径( 最坏的情况)
   - rollback 计划(如果已承诺,我们如何解除)
   - idempotency 键(每个建议独有;重新提交返回相同的记录)
2. **Surface.** 审阅者看到提案中包含所有元数据。 agent ))审查本身)。
3. **Commit.** 肯定的承认 行动开始
4. **Verify.** 执行后, 副作用会读取并确认。 如果校验步骤失败, 系统将处于已知的坏状态, 并会发生警告 。

<a id="the-idempotency-key"></a>

### 该 idempotency key

没有 idempotency 键,在瞬时性故障后重试可双重执行一个已核准的动作。具体示例:用户批准“从 A 向 B 转移100美元”。网络 blips。工作流回溯。用户只核准一次,但传输执行两次。 idempotency 键将批准与单一、独特的副作用联系起来;第二次执行是无操作。

都一样 idempotency 样式和 AWS APIs 使用。 重新使用它 agent 微软中明确认可 Agent 框架文件。

<a id="durability-why-approvals-outlast-processes"></a>

### 易腐性:为什么批准超过最后程序

批准候机室是一块州 agent 不存在。 工作流程被暂停( Lesson 12) 。 当批准到达时, 工作流程会从那个位置恢复 。 这就是为什么 LangGraph pairs `interrupt()` 且不只是在模拟状态下, 两天后批准工作仍保持完整。

<a id="rubber-stamp-approvals-and-the-challenge-and-response-mitigation"></a>

### 橡胶印章批准和减少挑战和应对

HITL (“ 验证” / “ 拒绝” 按钮) 默认的 UI 生成快速批准, 没有真正审查 。 文件化的缓解: 需要先对特定问题做出肯定回答后才能启用 。 具体形状 :

- "你知道这触及到什么资源吗? [ ]"
- "你是否确认爆炸半径是可以接受的? [ ]"
- "你有 rollback 如果失败了怎么办? [ ]"

官僚主义不是为了自身的利益,而是强迫功能。 无法在框中勾选的审评员要么要求澄清( 降级) , 要么要求降低( 安全默认) 。 Anthropic agent- 安全研究明确引用清单驱动的HITL作为橡胶印章批准模式的缓解措施。

<a id="what-counts-as-consequential"></a>

### 何为后果

不是每件事都需要提出...commit2026年指南:

- **相应行动** (总是高端信息) 不可逆的写作、金融交易、外向通信、生产数据库变化、破坏性的文件系统操作。
- **可逆动作** (有时是 HITL): 编辑本地文件, 中继- env 更改, 可逆性写法清晰 rollback.
- **阅读和检查** (从未 HITL ): 读取文件, 列出资源, 调用只读 API.

<a id="post-action-verification"></a>

### 行动后核查

"该 commit Ran" 和“ 副作用发生” 不一样。 网络分割和种族条件可以产生一个在后端不持续的情况下认为它成功的工作流程。 校验步骤会在目标资源被重新读取之后 commit 用于确认。这是与数据库交易相同的模式 `RETURNING` 或AWS 系统 `GetObject` 之后 `PutObject`.

<a id="eu-ai-act-article-14"></a>

### 《欧盟大赦国际法》第14条

第14条规定对欧盟的高风险人工智能系统进行有效的人力监督。 “有效”不是装饰性的。监管语言具体排除了橡胶印章模式。commit 与挑战与回应是 微软第14条的检查中幸存的形状 Agent 治理工具包合规文件。

```figure
mx-propose-then-commit
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 执行一个提议 - 然后commit 状态机器在 stdlib Python。 耐久商店是 JSON file. Idempotency 键是(线索)的散列_ID, 动作_驱动程序模拟三个实例: 清洁的核准流程、 短暂故障后重试( 不得双重执行) 以及橡胶标记默认值相对于挑战与响应流量 。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-hitl-design.md` 审查拟议的高级信息技术水平工作流程,以便提出 -- --commit 形状和标记缺失元数据, idempotency、核查或挑战与反应层。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`确认经核准的提案的重试使用耐久记录,而不重新执行。 idempotency 键,以包含一个时间戳并显示重复执行。

2. 将建议记录扩展为 `rollback` 字段。模拟校验步骤失败的执行。显示 rollback 自动射击

3. 读取 Microsoft Agent Framework's `RequestInfoEvent` 查找一个元数据字段 API 包括玩具引擎丢失。添加它并解释它能保护什么。

4. 设计一个特定行动的挑战和回应清单( 比如“ 贴到公共推特账户 ” ) 。 评审者必须回答三个问题吗? 为什么要回答这三个问题?

5. 选一个同步的"证明"? prompt 足够( 不需要耐久的商店) 。 请解释原因, 并列出您接受的风险类别 。

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| Propose-then-commit | "两阶段批准" | 坚持的建议+积极 commit + 校验 |
| Idempotency key | "Retry-safe token" | 每个提案的独特性; 第二次不执行 |
| Data lineage | "从哪来的" | 导致提出提案的具体来源内容 |
| 爆炸半径 | "最烂的箱子" | 行动发生错误时的效力范围 |
| Rubber-stamp | "尽快批准" | 未经真正审查而点击“ 证明” |
| Challenge-and-response | 强制检查 | 审评员必须肯定地承认具体问题 |
| RequestInfoEvent | "MS Agent 原始框架 | 具有结构化元数据的持久 HITL 请求 |
| `interrupt()` / `waitForApproval()` | 原始的森林 | LangGraph / 同一形状的云花等量 |

<a id="further-reading"></a>

## 进一步阅读

- [Microsoft Agent 框架——人环绕](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop) — `RequestInfoEvent`长期批准
- [Cloudflare Agents - 人进入循环](https://developers.cloudflare.com/agents/concepts/human-in-the-loop/) — `waitForApproval()` 和持久物。
- [Anthropic 计量 agent 实际的自主权](https://www.anthropic.com/research/measuring-agent-autonomy) - 高光学水平作为长视距风险的缓解措施。
- [欧盟大赦国际法——第14条:人的监督](https://artificialintelligenceact.eu/article/14/) - 高风险系统的监管基线。
- [Anthropic — Claude《宪法》(2026年1月)](https://www.anthropic.com/news/claudes-constitution) - 围绕监督制定宪法。
