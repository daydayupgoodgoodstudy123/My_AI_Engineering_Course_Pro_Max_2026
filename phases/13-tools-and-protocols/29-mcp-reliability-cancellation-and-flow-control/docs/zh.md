<!-- local-zh-machine-draft: English source is canonical; prose translated automatically, code/math preserved. -->

<a id="mcp-reliability-cancellation-and-flow-control"></a>

# MCP 可靠性、取消与流量控制

> 请求ID 将信件关联。 它不会使副作用安全, 阻止工人, 或者保护流不受慢速消费者的影响 。

**类型:** Build
**语言:** Python
**先修要求:** 第13阶段,第09和13段
**时间:** ~120分钟

<a id="learning-objectives"></a>

## 学习目标

- 执行正确取消标准流和流信号 HTTP.
- 解析完成和取消的比赛, 不在取消后发送信件 。
- 单独取消耐用请求 `tasks/cancel` semantics.
- 从副作用和清晰度构建重试决定 idempotency keys.
- 保存最终响应的同时, 绕过进度队列 。
- 通过连接、再伸展和急转直下 恢复流。

<a id="the-problem"></a>

## 问题

幸福的道路隐藏了最昂贵的分布系统错误。

客户端调用工具。 服务器开始工作。 进度到来。 代理缓冲流。 客户端到达超时并断开。 服务器稍晚完成一毫秒。 客户端重新输入新文件 JSON-RPC id 突变两次

每个部件都以本地为行为,系统在全球范围失灵。

MCP 定义消息和运输行为, 但您的应用程序仍然拥有 :

- 时间预算;
- business idempotency;
- 捆绑队列;
- 重试分类;
- 持久任务状态;
- 重新连接和重新拉伸政策 。

这一教训将这些决定发展成决定性的模拟器。
没有睡眠、套接字或随机故障。 您控制取消事件顺序
直接。 一个同步线测试迫使两个分类账客户端进行竞争
相同内容 idempotency key.

<a id="request-cancellation-is-transport-specific"></a>

## 请求取消是特定运输

每一次运输都具有同样的意图:客户不再需要飞行结果。电线信号不同。

<a id="stdio"></a>

### stdio

标准程序使用一个共享双向频道。 客户端发送通知 :

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/cancelled",
  "params": {
    "requestId": 41,
    "reason": "User closed the operation"
  }
}
```

通知是火和忘记。服务器发出否 JSON-RPC 回应它。

服务器应该停止工作, 释放资源, 并避免发送被取消请求的回复。 当请求未知、 已完成或无法安全停止时, 它可能会忽略取消 。

错误、 未知和已完成的取消通知被忽略。 将这些种族转换为新错误会引发更多种族 。

<a id="streamable-http"></a>

### Streamable HTTP

现代流 HTTP 给每个请求自己的 HTTP 响应或 SSE 响应流。 客户端关闭请求响应流后取消 。

不在 Post 状态 `notifications/cancelled` 普通的 HTTP 请求。 流关闭是取消信号 。

一旦服务器看到断开, 它就应该停止工作, 并且不能为此请求发送更多信息 。

<a id="server-sent-cancellation-is-narrow"></a>

### 服务器发送取消范围小

服务器不使用 `notifications/cancelled` 以取消任意客户端的通话。在标准程序上,服务器发送的取消被保留用于终止 `subscriptions/listen` 请求。 保持该路径与普通客户端请求取消分开 。

<a id="cancellation-is-a-race"></a>

## 取消是一个种族

两个事件的命令都有效

<a id="cancellation-wins"></a>

### 取消赢

```text
request starts
client sends cancellation signal
server marks request cancelled
worker reaches completion
server suppresses the response
```

<a id="completion-wins"></a>

### 补全赢

```text
request starts
worker commits the result
server sends the response
cancellation arrives late
server ignores the late notification
```

客户还必须忽略对已经放弃的请求的迟发反应。 网络延迟意味着任何一方都不能证明对方先观察到了什么事件。

```figure
mcp-reliability-race
```

课上 `RequestCoordinator` 储存一个终端状态。 `complete()` 返回取消后没有回复。延迟取消不能更改完整记录。

<a id="timeouts-need-two-clocks"></a>

## 超时需要两个钟

单凭一个无活动计时器是不够的。

使用两个限制 :

1. **闲置超时** 请求可产生任何有用的活动多长时间。
2. **最大超时** 要求开始时的绝对墙上预算。

进度可以重置闲置的时钟, 永远不能取消最长的截止时间 。

```text
start: 0 ms
progress: 400 ms
progress: 800 ms
progress: 1200 ms
idle timeout: 500 ms
maximum timeout: 2000 ms
```

请求在1500毫秒时仍然有效,因为最新进展只有300毫秒。 在2000毫秒时,即使1999毫秒时又出现了另一进展事件,但最高期限也取消了请求。

进度是可选的。 服务器可以接受进度 token 并且不发布更新。 不要改变一个 token 进入无限的超时

MCP 进度值必须增加。 完成或取消后通知停止。 限速进度使快速工人无法充斥运输 。

<a id="request-cancellation-is-not-taskscancel"></a>

## 请求取消不是 `tasks/cancel`

这些机制解决了不同的寿命期。

| Mechanism | 目标 | 信号 | 成功意味着什么 |
|-----------|--------|--------|--------------------|
| 标准版上的请求取消 | 一架在飞行中RPC | `notifications/cancelled` | 客户放弃请求; 如果实际操作, 服务器应该停止 |
| 请求取消于 HTTP | 一个飞行中反应流 | 关闭流 | 客户放弃请求; 如果实际操作, 服务器应该停止 |
| `tasks/cancel` | 一个持久任务 | Ordinary MCP request | 服务器确认取消意向 |

成功 `tasks/cancel` 结果不能证明工人停止了。任务可能仍然 `working` 直到工人 checkpoint 观察旗帜。 在此之前, 工程可能完成 。 checkpoint.

不要删除当 HTTP 连接关闭。 创建任务的原因是, 其生命周期比一个请求和一个连接有效。

<a id="a-new-json-rpc-id-is-not-idempotency"></a>

## A 新设 JSON-RPC 身份证不是 Idempotency

JSON-RPC 与要求和回应相关,它们不确定业务。

假设客户提出指控 `41`,然后重试 `42`。服务器看到两个不同的信息。没有应用程序密钥,它无法知道它们是一次检出。

一个 idempotency 关键字表示业务意图:

```json
{
  "name": "charge_account",
  "arguments": {
    "account": "acct-7",
    "cents": 1200,
    "idempotencyKey": "checkout-7"
  }
}
```

服务器仓库 :

- 钥匙;
- 操作参数的指纹;
- 承诺的结果。

相同的键和相同的参数返回存储的结果。 拒绝同样的带有不同参数的键。 这防止了意外的键再利用来改变不同的业务操作 。

<a id="the-ledger-boundary-must-be-atomic-and-durable"></a>

### 分类账的界限必须是原子的和持久的

这个序列不安全 :

```text
check key
run mutation
store result
```

两名工人都可以看到一个丢失的钥匙 两人都运行突变。
效果之后,但在商店重新试镜之前,也会产生同样的模糊性。

课程使用文件支持的 SQLite 分类账 。 `BEGIN IMMEDIATE` 连续
键盘检查、模拟业务效果、执行台和存储结果
一次交易,两个独立的账簿连接 以同一个键进行比赛
因此,观察一个承诺的结果和一个处决。
账簿上记录了

将每个返回值从存储的重现 JSON。打电话的人从未收到
分类账持有的可变对象, 因此无法更改返回的字典
损坏后重放结果 。

模拟器的商业效果是
同样的SQLite交易。 真实支付、 部署或外部 API 电话是
生产需要耐久的
共享数据库交易、交易发包或上游供应商
执行相同 idempotency 键。单靠锁程序不能保护
多个复制或恢复运行。

<a id="retry-matrix"></a>

### 重试矩阵

执行前分类。

| Class | 示例 | 重试规则 |
|------|---------|------------|
| Safe | 确定性读数无副作用 | 重试新 JSON-RPC 理解失败边界后的身份 |
| Conditional | 耐久性变异 idempotency key | 使用相同的键和相同参数重试 |
| Unsafe | 异变无业务重复 | 不自动重试; 先对齐 |

工具注释, 如 `readOnlyHint` 和 `idempotentHint` 仍然不可信提示。 应用程序合同和服务器执行决定重试安全性 。

<a id="backpressure-is-part-of-correctness"></a>

## Backpressure 是正确性的一部分

SSE 制作人能够比客户端、 代理或网络能消耗它更快地生成进步。 无约束的队列会将慢速转换为记忆耗尽 。

使用条框的队列并定义可以丢失的内容 。

进步是可替换的。 后一个进度值则取代较早的进度值 token决赛 JSON-RPC 反应不可替换 。

课程缓冲应用此政策 :

1. 相同项目的相邻进度 token.
2. 能力达到后,就放弃最古老的进展。
3. 将流标为需要权威的再伸缩。
4. 保留最后的回复
5. 拒绝保留最后答复的国家,需要放弃另一种最后答复。

这是有明确补偿的捆绑损失,沉默损失不是策略。

<a id="proxy-buffering"></a>

### 代理缓冲

服务器可以正确流出, 而反向代理在缓冲中保存事件 。

特殊保障体系回复,请发送:

```http
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

2026年的流体 HTTP 说明建议 `X-Accel-Buffering: no` 如此兼容的代理立即发送事件。

静静长寿的流体,

```text
:
```

客户端忽略批注行。 中介人看到流量, 并不太可能关闭闲置的连接 。

保持保存不是进步。 不要仅仅因为运输批注到达而重置操作的语义空闲超时 。

<a id="reconnect-means-refetch"></a>

## 重新连接意味着再扩展

现代流 HTTP 不支持可恢复 SSE 过 `Last-Event-ID`.

过了 `subscriptions/listen` 流线滴数 :

1. 使用新打开的听请求 JSON-RPC id.
2. 恢复所需的订阅过滤器 。
3. 重新获取受影响的工具、资源、 prompts,或根据权威方法确定的任务。
4. 重复应用程序以稳定标识符表示 。
5. 不要因为不安全的突变反应丢失而重播它。

抽样回收计划明确规定 `sendLastEventId` 来列出可以重新获取的资源

<a id="prevent-a-reconnect-herd"></a>

### 防止重新连接群群

如果一万个客户一秒钟就重新连接 正在恢复的服务器又失败了

使用指数反转和Qitter 和 盖。 课目从客户端 id 和 尝试编号中计算决定性快速, 所以测试仍然可以复制 :

```text
attempt 0: up to 250 ms
attempt 1: up to 500 ms
attempt 2: up to 1000 ms
...
cap: 8000 ms
```

生产可以使用加密安全或运行时随机性。 变量是分布, 不是特定的公式 。

<a id="build-it"></a>

## 动手实现

`code/main.py` 建立五个小的可靠性组件。

<a id="requestcoordinator"></a>

### `RequestCoordinator`

- 启动飞行中请求,无所事事,最长期限;
- 发出单音进度通知;
- 生成正确的标准或 HTTP 取消信号;
- 忽略无效的取消通知;
- 明确取消和完成终点赛;
- 保留用于标准用户的服务器发送取消。

<a id="mutationledger"></a>

### `MutationLedger`

- 证明两个 JSON-RPC id 执行两次,无商业钥匙;
- 使用文件支持的 SQLite 交易进行密钥检查, 模拟效果,
  执行台和结果 commit;
- 重复匹配一个参数 idempotency 独立键
  分类账连接;
- 拒绝用不同论据重复使用的密钥;
- 将防御性副本归还,并保存在重新开放的每个地点的已承诺的记录。

<a id="durabletaskservice"></a>

### `DurableTaskService`

- 确认取消请求;
- 保留任务 `working` 直到工人 checkpoint;
- 说明为什么承认不是最后地位。

<a id="boundedssebuffer"></a>

### `BoundedSseBuffer`

- 压力下凝聚或降低进展;
- 需要具有权威性的检索记录;
- 永不放弃最后的回答

<a id="recovery-helpers"></a>

### 康复帮助者

- 返回安全代理 SSE 信头并保持保留评论;
- 创建一个连接和再牵线计划;
- 分散回旋带 以确定性指数反转和紧张。

<a id="use-it"></a>

## 实际应用

从仓库根 :

```bash
cd phases/13-tools-and-protocols/29-mcp-reliability-cancellation-and-flow-control/code
python3 main.py
python3 -m unittest discover tests -v
```

演示在中央两边运行, 执行交易
临时文件支持的分类账中被复制的突变, 超载了被绑定的
进度缓冲,并显示一个持久的任务,从确认的取消
改为工人观察的取消。

<a id="interactive-lab"></a>

## 交互式实验

运行四个事件, 不添加睡眠 。

1. 启动请求 `A`取消,然后打电话 `complete()`.
2. 启动请求 `B`,完成它,然后发送取消。
3. 启动请求 `C`,在每一个空闲的最后期限之前发布进度,然后跨过最大期限。
4. 启动请求 `D` 流经可移动 HTTP 并关闭其响应流。

每种情景的记录:

- 最终请求状态;
- 是否存在最后答复;
- 电线上发出的取消信号;
- 客户端应该忽略的哪个事件 。

换个衣服 `D` 。 操作相同, 但取消信号必须更改 。

<a id="practice-lab"></a>

## 练习实验

添加a `reserve_inventory` 突变到 `MutationLedger`.

Requirements:

1. 密钥将SKU、数量、租户和操作名称捆绑在一起。
2. 重试同一键, 并用相同的参数返回第一个保留 。
3. 重试数量更改后, 无法再次保留 。
4. 关键可以调和已经执行但已失去反应的处决。
5. 结果没有记录任何秘密或付款数据。
6. 当客户端没有提供密钥时, 自动重试会被禁用 。
7. 在决定下一步行动之前添加模拟订阅滴出并重新拉动库存记录 。
8. 在屏障启动两个分类账连接并提交相同的密钥
   同时,有人提出保留。
9. 静音返回的第一个保留对象。重放键并证明
   存储结果没有改变 。
10. 关闭并重开分类账文件, 然后按键对保留进行对账 。

保持实验室的诚实:如果库存 住在另一服务,解释一下
服务接受相同 idempotency 键或交易发件箱
连接当地 commit 遥控效果

<a id="shipped-artifact"></a>

## 交付成果

`outputs/skill-mcp-reliability-reviewer.md` 是一个平坦的可靠性审查技巧。 MCP 运行、 传输、 超时策略、 重试行为、 队列策略和回收计划。 它返回一个种族表、 重试分类, idempotency 边界、流动控制检查和故障装置。

<a id="verify-it"></a>

## 验证

当这些说法属实时,这一教训就已经讲完了:

- 平方公尺取消发送 `notifications/cancelled` 并且没有得到任何回应。
- Streamable HTTP 取消关闭请求流,不发送取消 POST 。
- 取消在完成前停止最后回应。
- 完全取消后保留了答复,忽略了推迟取消。
- 进步可以重新设定闲置的超时, 但永远无法最大超时 。
- 一个新的 JSON-RPC 光凭ID就能再次执行突变
- One idempotency 键和相同的参数在同时执行时执行
  双连赛
- 记录能维持下去,重播可回回回一份防守副本。
- 变异返回的结果不能改变存储的结果 。
- 封闭缓冲装置保持在能力范围内,并保留最后反应。
- 重新连接使用新请求, 不发送 `Last-Event-ID`,并重新计时 影响状态。
- `tasks/cancel` 承认使工作非终止,直到工人遵守。

<a id="production-failure-modes"></a>

## 生产失败模式

| Failure | 可见症状 | 正确回应 |
|---------|--------------------|------------------|
| HTTP 客户端 PST 取消通知 | 服务器和客户对请求寿命有异议 | 关闭请求的 SSE 响应流 |
| 服务器在被接受取消后响应 | 客户收到无法使用的晚结果 | 停止工作, 当取消获胜时停止继续发送消息 |
| 进度每过一个截止时间重排 | 洪哥的活活是一辈子 | 保持单独的绝对最大超时 |
| 新的 RPC 代号作为重复处理 | 两次充电、部署或删除 | 添加一个耐久应用程序 idempotency key |
| 密钥检查和效果是分开的 | 同时工作的工人都看到一个缺失的钥匙 | Commit 关键索赔、效果记录和结果原子 |
| 复制品使用的模拟分类账 | 重新开始,否则其他工人会忘记之前 commits | 使用共享耐久储存或上游 idempotency |
| 直接返回存储的变异结果 | 调用者变异 腐蚀了以后重播 | 将承诺的结果序列化,并归还防御性副本 |
| 键被更改参数重新使用 | 其中一个关键别名是两个业务意图 | 保存和比较参数指纹 |
| 无约束的进度队列 | 内存随着消费者的缓慢而上升 | 结合内可替代的进展的折叠和下降 |
| 最终反应在压力下下降 | 客户无法知道请求结果 | 储备能力或驱逐进展,从来就没有最后反应 |
| 代理缓冲 | 进展在瞬间或超时后到达 | 禁用缓冲并配置兼容的代理超时 |
| `Last-Event-ID` assumed | 客户端从服务器不支持的状态恢复 | 重新连接新请求并重新拉伸 |
| 每个客户都马上重新连接 | 恢复又造成停电 | 使用带 Qitter 的上限指数后退 |
| 工作日作为最后取消处理 | 工人在UI说停止后继续跑 | 将任务拖到终端状态 |

<a id="capstone-connection"></a>

## 与综合项目的联系

工具生态系统的综合项目应把可靠性视为可执行的证据,而不是建筑图中的一段。

需要这些艺术品:

- 每批运输单一份取消的种族记录;
- 重试每个暴露突变的表格;
- 一个 idempotency- 关键记录和不匹配固定;
- 并行的同钥匙记录、重新检查和突变性检查;
- 封闭缓冲超载结果;
- 反向代理 SSE 信头和闲置政策;
- 重新连接计划,其中列出权威的再牵引方法;
- 持久任务取消 trace 当综合项目使用任务。

本地程序中的绿色要求只能证明是幸福的道路。 当响应丢失、取消晚期、消费者迟缓和重新连接牛群时,综合项目就已经可以生产了,结果也具有决定性。

<a id="key-terms"></a>

## 关键术语

| 术语 | 含义 |
|------|---------|
| 请求取消 | 放弃一架在飞行中 MCP request |
| 取消种族 | 终端完成和取消事件之间的竞争 |
| 空闲超时 | 自上次有用的请求活动以来的限制 |
| 最大超时 | 请求开始时的绝对限制,不受进展的影响 |
| Idempotency key | 重复一个业务意图的应用识别符 |
| 原子分类账 | 永久边界 commits 关键索赔、效果记录和结果 |
| Backpressure | 生产者比消费者快时实行控制 |
| 进步联合 | 以新的权威性价值取代旧的进展 |
| Refetch | 流差后再次读取当前状态 |
| Jitter | 故意使时间变异 |

<a id="further-reading"></a>

## 进一步阅读

- [MCP Cancellation](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/cancellation)
- [MCP Progress](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/progress)
- [MCP Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)
- [MCP 任务扩展](https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks)
