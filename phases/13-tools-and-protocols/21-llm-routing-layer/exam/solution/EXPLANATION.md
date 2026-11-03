# 参考答案讲解：ModelRouter（13/21）

计时结束后再看。参考实现在同目录的 `modelrouter/` 里，`python3 -m pytest --solution --all-parts` 应该显示 5 passed。

## Part 1 修网关

**现象**：解锁后的第一个错误是 `AllProvidersFailed: every model for smart failed: openai/gpt-4o 400, anthropic/claude-sonnet 400, google/gemini-pro 400`，报在 `Gateway.route` 里。三家同时挂掉不太可能，三个 400 更说明问题出在请求本身。

**顺着往上找**：`except ProviderError: continue` 把 400 也当成服务商故障，坏请求被发给了三家，真正的错误信息被回退循环吞掉了。课里写的是 “on 5xx” 才换下一个，所以先把 4xx 改成立即抛 `RequestRejected`。这时报错变成服务商自己的话：`messages[3]: a tool message needs the tool_call_id of the call it answers`。发出去的最后一条消息是 tool 结果，而 `redact_messages` 把它重建成了 `{"role", "content"}`，`tool_call_id` 没了。测验 Q10 问的就是这个问题。这一关想练的是：报错的地方（网关的回退循环）离根因（脱敏函数）隔了两层，回退还会把真正的错误藏起来。

**依次修五处**：

1. `Gateway.route`：`err.status < 500` 时 `raise RequestRejected(err) from err`，5xx 才 `continue`。
2. `redact_messages`：用 `dict(message)` 复制一份再改 content，其他字段原样保留。
3. `redact_messages`：每一条消息都要脱敏，不只最后一条。客户端每次都把完整历史发过来，前面的 user 消息里的卡号和 SSN 同样会离开网关。content 为 None 的工具调用消息要跳过，否则正则报 TypeError。`redacted` 是所有消息的“或”。
4. `Gateway.route`：按实际服务的模型 `self.prices[model]` 计价。原代码在循环之前取了 `chain[0]` 的价格，gemini 服务的请求按 gpt-4o 计成 12,000 微美元，实际是 1200 × 1.25 + 400 × 5 = 3,500。
5. `Budget`：原来每次 `check` 都把所有花费扫一遍，15 万笔之后每个请求要几毫秒。改成按 `(团队, 月)` 记累计值：

```python
self._spent: defaultdict[tuple[str, str], int] = defaultdict(int)

def spent(self, team, month):
    return self._spent.get((team, month), 0)

def charge(self, team, at, micros):
    self._spent[(team, month_of(at))] += micros
```

**护栏**：累计值的键必须带月份。只按团队累计，12 月 1 日零点的请求会被 11 月的 36,000 挡住；只留一个“当前月”的计数器，查 11 月的花费会得到 0。月份由请求到达的时间决定，正好在 UTC 零点的请求算新月。另外，预算要在发送之前检查，花费等于上限就拒绝；按组存列表、每次 `sum` 仍然是每个请求 O(n)，计时过不了。

## Part 2 成本账本

参考实现只有一张表：`number` 是自增主键，`at` 存成 UTC 的 ISO 文本（保留微秒），另存一列 `month`（`month_of` 算出的 YYYY-MM），attempts 存成 JSON 的 `[[model, status], ...]`，成本和 token 都是 INTEGER。`spend` 用 `COALESCE(SUM(cost_micros), 0)`，`report` 用 `GROUP BY team ORDER BY team`，failed 是 `COUNT(*) - COUNT(served_model)`。

这一关的精度陷阱是钱。课里的代码用 `cost_usd: float`，账本照抄就会出问题：

- REAL 列读回来是 float，`3500.0 == 3500` 为真，等值比较发现不了，所以测试单独检查类型，`spend` 和 `report` 都查。
- 存美元、读回来乘 10⁶ 再 `int()`：0.000249 × 10⁶ = 248.99999999999997，249 变成 248。
- `TOTAL()` 永远返回 float；`SUM()` 在没有数据时返回 NULL。
- 成本在每次调用时按 `cost_micros` 的规则取整一次（每百万 token 的美元单价就是每 token 的微美元数，四舍五入到整数）。之后的所有合计都是整数相加，账本不再取整。所以 `record` 拒绝 float，包括 3500.0 这种整数值。

月份按 UTC：`2026-11-01T00:30+01:00` 是 10 月 31 日 23:30 UTC。存之前先 `astimezone(timezone.utc)`，或者用 `month_of`。按日期 `BETWEEN '2026-10-01' AND '2026-10-31'` 过滤，会漏掉 31 日零点以后的调用，因为 `'2026-10-31T23:59...'` 比 `'2026-10-31'` 大。

其他几点：`calls()` 按 `number` 排序，不按时间；编号用数据库的自增值，重开后接着来；attempts 读回来要重新组成 `Attempt` 元组；None 存成 NULL。

## Part 3 加权与合规

平滑加权轮询（nginx 的 SWRR）每次选择时：每个候选者的分数加上自己的权重，取分数最高的（同分取先列出的），胜者减去所有候选者的权重和。5:2:1 一个周期 8 次，顺序是 us, eu, us, us, sonnet, us, eu, us，同一个部署最多连着两次。普通的加权轮询会连续 5 次选同一个，正是课里 “Load balancing” 想避免的。

```python
eligible = [d for d in pool.deployments if region is None or d.region == region]
candidates = [d for d in eligible if d.weight > 0]
scores = self._scores.setdefault((alias, region), {})
best = None
for d in candidates:
    scores[d.name] = scores.get(d.name, 0) + d.weight
    if best is None or scores[d.name] > scores[best.name]:
        best = d
scores[best.name] -= sum(d.weight for d in candidates)
return [best] + [d for d in eligible if d is not best]
```

- **合规先于选择**：先按 region 过滤，再在过滤后的集合里轮询，而且每个 `(alias, region)` 有自己的分数。否则 EU 流量会改变全局轮询，或者 EU 用户按全局顺序被分配。过滤后为空就报 `NoEligibleDeployment`，回退也只在合规的部署之间进行。课里的技能文件把“把 prompt 发到违反合规约束的区域”列为硬拒绝。
- **重试计入预算**：`send` 只调用一次 `plan`。每次尝试之前检查已经试了几次，同一部署的重试也算。计划正好用完时报 `AllProvidersFailed`，只有还想再试却没有预算时才报 `RetryBudgetExhausted`。
- **4xx**：和 Part 1 一样立即抛 `RequestRejected`，`retries` 只对 5xx 有效。
- **权重全为 0**：合规部署的权重都是 0 时没有候选者，计划直接按列出顺序，轮询状态不动。

## Part 4 延迟感知路由

每个模型维护三样东西：一个按时间排序的成功样本队列（`deque`），连续 5xx 的计数，熔断状态（打开时间、在途探测的 request_id）。

```python
async for event in events:
    if isinstance(event, Result):
        _observe(health[event.model], event, trip_after)
        continue
    for h in health.values():                      # 按请求的时间淘汰过期样本
        while h.samples and event.t_ms - h.samples[0][0] >= window_ms:
            h.samples.popleft()
    model, reason = _choose(health, models, event.t_ms, cooldown_ms)
    if reason == "probe":
        health[model].probe = event.request_id
    yield _record(event.t_ms, event.request_id, model or "", reason)
```

- **选择顺序**：冷却到期且没有在途探测的模型先拿到请求，作为探测，即使别的模型更快（q11）或者还没有样本（s5）；然后是没有样本的模型，按列出顺序；最后是中位数最低的，同分取先列出的。比较时用“两倍中位数”（奇数个是中间值乘 2，偶数个是中间两个之和），全程整数。
- **样本**：只有成功的结果是样本。快速失败的 503 如果算进去，坏掉的模型会显得最快。正好 window_ms 之前的样本已经过期，淘汰按请求的时间判断。
- **熔断**：连续 trip_after 个 5xx 打开熔断，打开时间是最后一个 5xx 的时间；成功清零。打开期间，只有探测的结果能改变状态，按 request_id 认，迟到的成功只算样本，迟到的 5xx 什么也不改（s6）。探测成功就关闭，连续 5xx 从 0 重新计（s8）；失败就从这个结果的时间重新冷却。
- **输出**：先输出表头，每个请求一到就输出一条 `csv.writer` 写的记录。测试数了拉取的事件数，读完整个流再输出会挂。

## Part 5 别名展开

递归时带着路径（检测环）、当前的 region 和 “是否已经冲突” 的标记：

- 进入一个 alias 前，如果它已经在当前路径上，就报 `AliasCycle(path[path.index(alias):] + [alias])`。环检测用路径，不用全局集合，因为 coding 经两条路径到达 fast 是菱形，不是环。环检测在深度检查之前，所以短环报成环。
- 路径长度超过 max_depth 报 `AliasError`；被展开的 alias 是第 1 层。
- `{"region": r, "chain": [...]}` 的 region 和外层的取交集：外层没有就用 r，相同不变，不同就把这一支标记为冲突，什么也不选，但仍然检查名字和环。直接传进来的模型名也要过调用方的 region。
- 模型只有在没冲突、region 符合、而且还没出现过时才加入。没被选中的模型不占位置，所以 eu-first 先走 eu-smart（只选 EU 模型），再走 smart 时还能把 US 模型补进来。按 alias 名字缓存展开结果会在这里出错，因为同一个 alias 在不同 region 下展开结果不同。
- 既不是 alias 也不是模型的名字报 `UnknownName`。课里的 `ROUTES.get(alias, [alias])` 会把拼错的别名当成模型名发出去，`PRICES.get(model, (0, 0))` 还会把它的成本记成 0（测验 Q9）。
- 什么都没选进来报 `AliasError`，不返回空列表。

## 这套题证明了什么，没证明什么

通过了说明你能在网关代码里沿着假服务商的报错找到根因，分清哪些错误该回退，按实际服务的模型记账，用整数微美元建一个按团队和月份汇总的 SQLite 账本，实现平滑加权轮询、合规过滤和共享的重试预算，写一个带滑动窗口和半开熔断的流式路由器，以及展开带区域约束的别名图。它不涉及真实服务商的 API 和流式响应、OpenAI 格式到各家格式的翻译、语义缓存、并发请求下的预算预扣，也不涉及 LiteLLM、OpenRouter、Portkey 的选型。课里的练习 2、3、5 需要另外动手做。
