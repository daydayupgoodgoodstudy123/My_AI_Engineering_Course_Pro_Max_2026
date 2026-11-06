<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="action-budgets-iteration-caps-and-cost-governors"></a>

# 行动预算、迭代上限与成本控制

> 中等规模的电子商务 agent每月 LLM 成本从1200美元跳到4800美元,因为团队能够“跟踪订单”技能。这不是一个定价错误。 agent 发现新的循环 并一直花在其中。 Agent 治理工具包(2026年4月2日)将防范这一类的防罪编集成册:按要求 `max_tokens`,每个任务 token 美元预算,每日/月上限,迭代上限,分级模式路线, prompt 缓存、 上下文窗口、 HITL checkpoints 以昂贵的动作, 杀死开关 预算违约。 Anthropic的 Claude Code Agent SDK 金融速度限制——例如,10分钟内将存取量削减到 > 50美元——捕获环比月封更快。

**类型:** 学习
**语言:** Python (平整,分层成本管理模拟器)
**先修要求:** 阶段15 · 10(派遣模式),阶段15 · 12(Durable execution)
**时间:** ~60分钟

<a id="the-problem"></a>

## 问题

Autonomous agents 花真正的钱在每一关。聊天机的坏结果是一个坏的答复; agent失败模式的行业记录术语是"钱包的破旧" agent 不停地推理,不停地打电话,不停地计费, 没有什么能阻止它 因为没有设计。

固定不是一个数字。 它是一个不同时间尺度和颗粒的堆积限制: 每一个请求、 每个任务、 每小时、 每个月。 一个设计良好的堆叠在几分钟内会捕捉一个离家出走的环状, 几个小时内会缓慢泄漏, 一天内会释放坏消息。 当一个错误的堆叠在一小时内会保持预算水平 。 agent 长视距和自主。

这是工程课:数学是微不足道的, 学科是团队失败的地方。 下面的限制列表在微软中要么命名为 Agent 治理工具包或 Anthropic Claude Code Agent SDK docs.

<a id="the-concept"></a>

## 概念

<a id="the-cost-governor-stack"></a>

### 成本管理器堆

1. **`max_tokens` 请求。** 很简单,防止任何人发出无约束的完成信号
2. **Per-task token budget.** 整个运行,不超过N tokens顶部有困难
3. **每项任务的预算。** 与 tokens 但要用货币 `max_budget_usd` 在 Claude Code.
4. **Per-tool call cap.** 不超过N `WebFetch` 电话,N `shell_exec` 电话等等
5. **迭代上限( )`max_turns`).** Total agent loop 迭代; 防止无限的推理循环 。
6. **/每小时/每天/每月上限。** 滚动窗口,在不同时间段捕捉到泄漏
7. **财务速度限制。** 例如,“如果10分钟内花费超过50美元,切断通道。” 月度火灾前会发生环状燃烧。
8. **铁丝型路由** 默认为较小模式; 只有在分类者判断任务是否必要时,才会升级为较大模式。
9. **Prompt caching.** System prompt 储存在供应商缓存中的稳定的上下文; token 重新出售的费用接近零。
10. **上下文窗口。** 压缩/总结,使活动环境保持在阈值以下; token- 减价
11. **HITL checkpoints 代价高昂的行动。** 之前的行动已知昂贵(长) tool call大量下载, 昂贵的模型升级) 需要人脉冲。
12. **预算违约时就开枪** 会话在任何上限火灾时中止。 上限被记录; 需要另外一条可重新启用的路径 。

<a id="why-the-stack-not-one-cap"></a>

### 为什么堆叠,一个也没有

一个月一次的上限 就可以逃出 agent 只有在钱包离开后。 在会话级别上, 单个请求上限不会捕获任何信息。 不同的失败模式需要不同的时间尺度 :

- **运行循环** (agent 被速度限制所困在5秒重试中。
- **慢慢漏水** (agent 执行~ 2x 每件任务预期的工作): 被每日上限捕获 。
- **错误的释放** (新版本使用 5x) tokens:每周/每月上限。
- **合法激增** (实际需求,不是虫子):按小时/日上限和清晰的日志捕获。

<a id="a-harness-budget-surface"></a>

### 一个 harness 预算面

该 Claude Code Agent SDK 曝光( 公共文件) :

- `max_turns` - 循环帽
- `max_budget_usd` 美元上限;会话因违反而中止。
- `allowed_tools` / `disallowed_tools` - 工具许可清单和拒绝名单。
- 用于定制成本会计的工具之前的钩点。

与许可模式梯子合并( Lesson 10) `autoMode` 无 `max_budget_usd` 不受管治的自治 Anthropic 明确框框自动模式需要预算控制;分类器对齐进行成本计算。

<a id="eu-ai-act-owasp-agentic-top-10"></a>

### 欧盟大赦国际法,OWASP Agentic 10大类

Microsoft's Agent 治理工具包涵盖《世界可持续发展伙伴关系》 Agentic 欧盟的《工业法》前十大和欧盟《工业法》第14条(人的监督)要求。 对于欧盟的生产,伐木和上限执行不是可选择的。

<a id="the-observed-1200--4800-case"></a>

### 观察到的1 200美元 4 800美元

微软文件的真实案例:电子商务 agent 其月成本在新工具添加后增加了三倍。 agent 以在每次会话中进行民意测验。 没有循环检测。 没有每个工具的上限。 没有一周以上增长的警告。 修正是每工具的上限加上每日增长的提示。 这是一个模板: 每个新工具表面都是一个新的潜在循环; 每个新工具都需要自己的上限和自己的提醒 。

```figure
cost-governor-stack
```

<a id="use-it"></a>

## 实际应用

`code/main.py` 模拟 agent 运行时和运行时都有一个多层的成本管理器堆。 agent 在某些转弯后漂移到一个投票圈;在速度窗口内,层叠的堆叠会将其捕获,而一个月一次的盖子在几天后才会起火。

<a id="ship-it"></a>

## 交付成果

`outputs/skill-agent-budget-audit.md` 审计a agent 部署的成本管理器堆和标记缺失层。

<a id="exercises"></a>

## 练习

1. Run `code/main.py`。在投票圈轨道的迭代上限之前确认速度限制火灾。现在禁用速度限制并测量 agent 循环帽抓住它之前的"溢出"

2. 为浏览器设计一个每个工具盖 agent 哪个工具需要最紧的帽子?

3. 读取微软 Agent 治理工具包文件。 列出工具箱的每个顶号名称。 将每个标记都映射到一个失败模式( 运行循环、 缓慢泄漏、 错误释放、 激增) 。

4. 买一晚上的无人看守, 来完成现实的任务( 例如“ 在回购中处理50个问题 ” )。 `max_budget_usd` 点数为 2x 。 说明 2x 的理由 。

5. Claude Code's `max_budget_usd` 以会话总成本点火。 设计一个补充速度限制, 您可以在外部执行。 什么触发了截断, 以及什么可以重新实现?

<a id="key-terms"></a>

## 关键术语

| 术语 | 人们怎么说 | 它实际上意味着什么 |
|---|---|---|
| 拒绝钱包 | 跑车帐单 | Agent loop 创造没有上限的支出以阻止它 |
| max_tokens | "请求上限" | 单项完成的大小上限 |
| max_turns | 试管 | 上限 agent loop 会话中的重迭 |
| max_budget_usd | "大开关" | 会话成本上限;违反时中止 |
| 速度限制 | 帽子,帽子,我给你 | 限制每个短窗口的支出(例如50美元/10分钟) |
| 铁丝路由 | "小模特先来" | 廉价模式默认; 只有在分类者授权时才会升级 |
| Prompt caching | "Cached system prompt" | 提供者侧缓存减少重新发送 token 成本接近零 |
| HITL checkpoint | "Human approval gate" | 需要人手才能进行昂贵的行动 |

<a id="further-reading"></a>

## 进一步阅读

- [Anthropic Claude Code Agent SDK — agent loop 和预算](https://code.claude.com/docs/en/agent-sdk/agent-loop) — `max_turns`, `max_budget_usd`,工具允许列表。
- [Microsoft Agent 框架 - human-in-the-loop 和治理](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop) 费用-管理者 checkpoints.
- [Anthropic — Claude Managed Agents overview](https://platform.claude.com/docs/en/managed-agents/overview) 供应商-方费用控制。
- [Anthropic — Prompt 缓存( C)Claude API docs)](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) 缓冲力
- [Anthropic 计量 agent 实际的自主权](https://www.anthropic.com/research/measuring-agent-autonomy) 长方位的成本简介 agents.
