# 参考答案讲解：mcpgateway（13/17）

计时结束后再看。参考实现在同目录的 `mcpgateway/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修转发与限流

**现象**：解锁后第一个错误是 502，`data` 里写着后端回了 -32001 Unauthenticated。网关自己并没有拒绝谁，是 reports 后端不认识它收到的 token。

**顺着往上找**：后端收到的 `Authorization` 是 `Bearer tok-alice`，也就是 alice 给网关的 token。`_backend_request` 先放路由头和网关的凭证，最后又摊开了 `**request.headers`，调用方的头把网关的凭证盖掉了，顺带还把 `Mcp-Session-Id`、`Cookie` 和调用方的 `Mcp-Name` 一起带了过去。修法是后端的头只由网关自己生成：路由头加 `_credential` 给的 token。课里：Never pass the outer gateway token to a backend。

**第二个 502**：这次写的是 `Backend returned a result the gateway cannot relay`，resultType 是 task。reports 后端只在请求声明了 Tasks 扩展时才返回 task，而这个网关的 `mediates` 里只有 elicitation。后端为什么会看到 Tasks？因为 `params.setdefault("_meta", ...)` 什么都没做：调用方的 params 里本来就有 `_meta`，于是后端拿到的是 alice 的客户端原样的 `_meta`。改成直接赋值 `params["_meta"] = request_meta(GATEWAY_INFO, request.capabilities)`。`capabilities` 是 `mediated()` 算出来的交集：网关能端到端中介、调用方也声明了的能力，值用网关自己的。这一关想练的是：报错的位置（结果检查）离根因（构造请求）隔着一次后端调用。

**第三处**：`_admit` 一进来就按 `Mcp-Name` 路由头扣了限流，然后才校验。三条畸形请求各花掉一次额度，合法调用直接 429。把扣额度挪到策略允许之后：

```python
outcome = "allow" if decision.allowed else "deny"
if decision.allowed and not self._spend(principal, public):
    outcome = "rate_limit"
self._audit_decision(request, decision, outcome)
```

放在校验之后、策略之前也不行：bob 被拒绝的 `notes.create` 第二次会变成 429。也不能等后端回答以后再检查，那样第 4 次调用已经转发出去了。

**第四处**：`RateLimiter.allow` 每次都用列表推导重建窗口，窗口里有 n 次调用时每次是 O(n)。改成每个 key 一个 deque，从队头弹出过期的时间戳，摊还 O(1)：

```python
calls = self._calls.setdefault(key, deque())
while calls and calls[0] <= now - self.window_s:
    calls.popleft()
```

时间戳是按时间追加的，所以过期的一定在队头。本机 12,001 次调用从 1 秒左右降到 2 毫秒左右。

**护栏**：窗口按 (principal, issuer, resource, 工具, 成本类别) 分开，为了提速合成一个全局窗口、或者像本课代码那样只按 principal，都会挂；另一个 issuer 下的同名 alice 是另一个人。语义是滑动窗口：一次放行的调用在 t + window_s 时不再计数，被拒绝的调用不计数，时间来自网关的时钟。换成本课 `TokenBucket` 那样的令牌桶（容量 3，每 60 秒补满），30 秒后已经补出 1.5 个令牌，会放进一次调用，和这里的窗口语义不同。

## Part 2 单条审计证据与脱敏

`AuditLog.record` 已给出，先调用候选人的 `redact(event)`，再把结果交给正确的 `JsonlAuditSink`。sink 负责编号、追加、flush、读取和关闭；它接收的只能是已经投影脱敏的事件。

```python
return self.append(redact(event))
```

这里的投影只看一条已经组装好的应用审计事件，不查其他行。MRTR、task、outer error、authorization deny 四类夹具分别要求留下 round、状态摘要、task_id、结构化拒绝信息和 decision/reason；每条还保留 descriptor pin 版本以及原样的 request/result metadata。`mrtr_round`、`descriptor_pin`、`request_meta`、`result_meta` 是应用审计字段；metadata 的值来自协议里的 protocolVersion/clientInfo/serverInfo，没有定义新的 MCP 属性。Part 5 才负责跨事件连接。

`redact` 先 deepcopy，所以调用方的 dict 不受影响；`headers` 变成排好序的头名列表；`arguments` 和 `inputResponses` 递归穿过 dict 和 list，键名小写以后在 SECRET_KEYS 里的，值整个换成 `"[redacted]"`，值是 dict 或 list 也一样，不再往里走。别的字段原样保留，网关自己记的 `error.code` 不能被当成 OAuth 授权码抹掉。

容易漏的几点：

- **给定 sink 的追加和 flush 护栏**：`"w"` 会清掉别的副本写的行；不 flush 的话，`record` 返回以后磁盘上还没有这一行。
- **先脱敏再写**：秘密只要写到磁盘上一次就算泄漏了，事后删不干净。
- **只按 `\n` 切行**：`json.dumps` 默认把 U+2028 转义，所以自己写的行没问题；但别的副本可能用 `ensure_ascii=False` 写，原样的 U+2028 会被 `splitlines()` 当成换行。
- **seq**：是事件在文件里的位置，打开时接着已有的事件往下编。Part 5 靠它在时间相同时定顺序。
- **原样往返**：JSON 本身能区分 7 和 "7"，能准确还原 `0.1 + 0.2`；只要不自作主张地规范化或四舍五入，就能逐条一致。

## Part 3 运行时策略

`decide` 先问策略服务。拿到了，就记成 last-known（连同拿到它的时间），按规则评估，路径是 `live`：

```python
checks = (
    ("admission", ctx.admitted),
    ("role", bool(roles & policy.tool_roles.get(ctx.tool, frozenset()))),
    ("pin", ctx.pinned),
    ("tenant", ctx.target_tenant is None or ctx.target_tenant == ctx.tenant),
    ("health", ctx.healthy),
    ("quarantine", not (ctx.operation == "write" and ctx.backend in policy.quarantined)),
)
```

`roles` 来自策略的 `roles[(issuer, principal)]`，没有就是空集。token 里的角色是签发时的状态，课里那句 A Registry record can remain active while a user's role is revoked 说的就是这种情况：注册表和 token 都还说可以，运行时策略说不行。

数据分级只在这里起作用：服务在线时，敏感数据照常按上面的规则判定。拿不到策略（PolicyUnavailable）时，只有同时满足四条的调用可以用 last-known 策略：读、公开数据、工具在 last-known 策略的 `stale_reads` 里、距离拿到它不到 ttl。规则照样全套执行，路径记 `last_known`，版本记那一版。其余一律失败关闭，路径 `fail_closed`，没有版本。ttl 从最后一次成功的 fetch 算起，不管那次的结果是允许还是拒绝；失败的 fetch 不刷新它。

没有任何缓存。撤销角色、隔离后端这些变化，下一次调用就生效。最后一段把引擎装进网关，验证 MRTR 的第二轮会被重新授权：角色撤销后重试被 403 拒绝，而且没有转发。

## Part 4 SSE 透传与任务路由

`relay` 逐条读后端的消息，只认两种：

```python
if message.get("id") == hop.backend_id and ("result" in message or "error" in message):
    ...  # 换成客户端的 id；result 用 gateway_result；task 先记路由
    yield _event(reply)
    return
if (message.get("method") == "notifications/progress" and "id" not in message
        and params.get("progressToken") == hop.backend_id and hop.progress_token is not None):
    yield _event({**message, "params": {**params, "progressToken": hop.progress_token}})
```

整个循环包在 `try/finally` 里，finally 关掉 `messages`。客户端断开时，`aclose()` 在 yield 处抛出 GeneratorExit，finally 跟着关掉后端的流，这就是取消后端请求；响应发完 return 时也会走到这里。

要点：

- **只认两种消息**：别的通知、别的 token 的进度、后端在流上发来的请求（比如 `sampling/createMessage`，现代版本本来就不允许）都丢掉。判断有没有进度 token 要写 `is not None`，0 是合法的 token，也是合法的 id。
- **两个映射**：网关给后端的进度 token 就是后端请求 id，所以 `gw-3` 在进度里要换成客户端的 token `p-7`，在响应里要换成客户端的 id 7。两件事分开做，按字段改，不做字符串替换。
- **原样透传**：除了 id 和 `_meta`，result 一个字段都不动。input_required 的 `inputRequests` 和 `requestState` 都在里面，后端在下一轮用 HMAC 验证 `requestState`，改一个字节就过不去。
- **先记路由再发 taskId**：`tasks.record` 在 `yield` 之前。客户端拿到 taskId 时，路由已经可查；之后客户端断开也不影响。课里：The task must already be durably readable before that result is sent。
- **TaskRoutes**：taskId 到 (owner, backend) 的映射，owner 是 (issuer, principal)。别人的任务和不存在的任务抛同一个 TaskNotFound，网关回同一个 -32602。

网关这边（已给出）在 `open_stream` 里把后端请求 id 作为进度 token 放进后端的 `_meta`，在 `_tap` 里像 JSON 路径一样检查并审计后端的响应。

## Part 5 审计决策链重建

按 (ts, seq) 排好序以后一遍扫过去，用三张表：

- `requests`：身份 (issuer, principal, trace_id, request_id) 到这个请求的节点。result 按身份找到自己的 decision，挂在下面；找不到就是孤儿叶子。
- `states`：(issuer, principal, state_out) 到产生这个状态的请求节点。重试的 decision 用 `state_in` 查这张表，挂在那一轮下面。
- `tasks`：(issuer, principal, taskId) 到返回这个任务的请求节点，只由 result 是 "task" 的结果写入。任务请求用自己的 taskId 查。

既没有 `state_in`、也不是任务方法的请求，是一次新调用的开头；有链接却查不到的，连同它下面的东西都是孤儿。被策略拒绝的请求不会有 result，但它照样是调用的一部分，按同样的规则挂进树里。因为按 (ts, seq) 的顺序处理，子节点追加的顺序就是排好的顺序，查表时也只会查到更早的事件。

为什么要这么多键：请求 id 是客户端起的，不同客户端、同一客户端的不同运行都会重复（测试里 alice 的第二个 agent、在 alice 的 trace 里被调用的 bob 的服务都用了 1），必须带上 trace、principal 和 issuer（另一个 IdP 下也可能有一个 alice）；MRTR 重试是新 id，网关又读不懂 `requestState`，只能靠它的摘要连接，而且不看 trace，重试可能来自新的 trace；任务轮询可以在很久以后、从另一个 trace 发来，只有 taskId 把它和原来的调用连在一起。同一个 trace 下的两个独立调用各是一棵树。

## 这套题证明了什么，没证明什么

通过了说明你能在网关代码里顺着 502 找到转发请求的根因，知道网关是后端的客户端、凭证按 issuer 和 resource 绑定，能把限流放在校验和授权之后并写出摊还 O(1) 的滑动窗口，能写一个写入前脱敏、可以多副本追加的 JSONL 审计日志，能写出带失败路径和 last-known ttl 的运行时策略，能写一个只改 id 和进度 token、先记任务路由再发 taskId、断开就取消后端的 SSE 中继，并能用多种关联键把扁平的审计事件拼回调用树。它不涉及真实的 HTTP 适配器（第 09 课）、OAuth 的 token 交换和受众校验（第 16、18 课）、命名空间合并、描述符 pin 和注册表准入（第 08、15、30 课），也没有测多副本共享限流窗口、日志防篡改和 `subscriptions/listen`。这些需要另外动手。
