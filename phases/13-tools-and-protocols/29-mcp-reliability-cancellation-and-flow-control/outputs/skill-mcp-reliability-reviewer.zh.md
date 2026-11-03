---
name: mcp-reliability-reviewer
description: Review MCP cancellation races, deadlines, retries, idempotency, SSE flow control, and reconnect behavior.
version: 1.0.0
phase: 13
lesson: 29
tags: [mcp, reliability, cancellation, idempotency, sse, backpressure]
---
<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->


审查一 MCP 从请求开始到故障恢复操作。

如有这种信息,请询问:

1. 运输:平坦或可流 HTTP.
2. 语义和副作用
3. 闲暇和绝对最高超时
4. Progress-token 行为和 rate limits.
5. 重试政策和业务 idempotency storage.
6. SSE 缓冲、 代理、 保存和重新连接设置 。
7. 持久任务行为,如果操作使用任务扩展。

编写以下各节。

<a id="cancellation-wire"></a>

## 取消线

- 斯迪奥,请求客户同意 `notifications/cancelled` 通知提及主动请求的代号。
- 用于可移动 HTTP,要求关闭该请求的响应流。拒绝普通的 POST 取消 。
- 需要否 JSON-RPC 对取消通知的答复。
- 保留服务器-已发 `notifications/cancelled` 用于标准 `subscriptions/listen` teardown.
- 说明取消未知、格式错误、晚或不可能取消时会发生什么。

<a id="race-table"></a>

## 比赛桌

给以下各方面带来决定性结果:

| 事件顺序 | 服务器终端状态 | 最后答复 | 客户行为 |
|------------|-----------------------|----------------|-----------------|
| 取消后完成 | Cancelled | Suppressed | 继续恢复 |
| 完成后取消 | Completed | Preserved | 忽略延迟取消 |
| 超时后延迟回复 | 依赖运输的取消 | 被观察到的顺序忽略或压缩 | 在不安全重试前调和 |
| 进展中断开 | 取消飞行请求 | 无可回收流 | 重新连接和再牵引 |

<a id="deadline-policy"></a>

## 期限政策

需要空闲超时和绝对最大超时。 进步只有在有效、 单调和有节率限制的情况下才能重新设定闲置时间。 保持评论不算作语义进步。 最大超时从不重设 。

<a id="retry-classification"></a>

## 重试分类

每次操作返回一个类 :

- `SAFE`:申请合同证明没有副作用。
- `CONDITIONAL`:突变有一个耐久性 idempotency 键,用相同的参数重新使用。
- `UNSAFE`:突变缺乏权威的重复。

永远不要吃新的 JSON-RPC id, 工具注释, 或运输重新连接为商业 idempotency.

对于有条件的重试, 需要存储参数指纹和已执行结果。 拒绝一个用更改参数重新使用的密钥 。

关键索赔、参数需要一个原子、耐久分类账界限
指纹、商业效果记录和承诺结果。
字典或锁定不耐用,且不协调复制。 接受
共享数据库交易、交易发包或上游供应商
执行相同的键。 效果所在的国家实际上位于边界内 。

返回已执行结果的防御副本。 永远不要暴露可变物体
由分类账持有。 以同时的同一密钥固定键来证明两个属性,
重新开张的固定装置 和变异的别具固定装置

<a id="flow-control"></a>

## 流动控制

- 设定明确的每流或每个客户的能力。
- 煤炭可替代的进展。
- 马克放弃进步,因为需要权威的重新伸展。
- 保留最终 JSON-RPC responses.
- Set `Content-Type: text/event-stream`, `Cache-Control: no-cache`, 和 `X-Accel-Buffering: no` 给SSE的
- 定义保持连续和运行进度分开。
- 拒绝无约束队列 。

<a id="reconnect-plan"></a>

## 重连计划

- 使用新ID 打开新请求 。
- 恢复订阅过滤器 。
- 不使用 `Last-Event-ID` 用于 MCP 2026-07-28.
- 重新获取受影响的资源,清单, prompts,或任务。
- 不要自动重播不安全的突变 。
- 使用带 Q 的 峰值指数后退 。

<a id="durable-tasks"></a>

## 持久任务

当任务存在时, 保留 `tasks/cancel` 完全确认仅证明取消意向被接受。 投放或倾听直到持久任务到达终点状态。

<a id="required-fixtures"></a>

## 所需装置

至少返回这些可执行的情景 :

1. 完成前取消标准;
2. 取消前完成标准;
3. HTTP 完成前关闭流;
4. 重新设定闲置超时,而最大超时仍会着火;
5. 复制突变与两个 JSON-RPC ids and no IDs 和无 idempotency key;
6. 重复突变,使用一个关键和相同的参数;
7. 键重用,参数改变;
8. 消费者慢于进度缓冲;
9. 流线下降,然后是新的订阅和权威性的再取;
10. `tasks/cancel` 之后,工人被推迟取消。
11. 两个独立的分类账连接在一个关键和相同的论点上进行竞争;
12. 呼叫者变异了返回的结果,然后从耐久记录中进行干净重播。

重新尝试政策时拒绝做出为生产准备的判决
超时尝试,账簿是本地的,外部效果就在这里
返回了没有发件箱或上游钥匙的被主张的原子边界外
记录别名可变存储,或未指定队列容量。
