# 面试官手册：ModelRouter（13/21）

候选人计时期间不要看。候选人手里只有 README、`modelrouter/` 和 `tests/`。

## 开场（2 分钟）

- 说明时长 60 分钟。请候选人一边做一边说出想法，可以随时提问，可以查官方文档。
- 目标是让测试原样通过，不追求全部做完。记录每关从解锁到变绿的时间，以及 pytest 跑了几次。
- 主持时不替候选人写代码。每关卡住约 5 分钟后，按下面的提示一次给一级。

## 澄清问题的标准答案

只在候选人问到时回答。用英文说。

| 关 | 可能的问题 | 回答 |
|---|---|---|
| 1 | 429 要不要换下一个模型？ | "The tests don't cover 429. The rule here is the lesson's: only a 5xx falls back. Tell me what you'd do with Retry-After." |
| 1 | system 和 tool 消息也要脱敏吗？ | "Yes. Every message's text, whatever its role." |
| 1 | tool_calls 里的 arguments 要脱敏吗？ | "Not in this exercise. Say where you'd add it." |
| 1 | 被拒绝的请求算钱吗？没人服务的请求呢？ | "Neither is charged. Only a served request costs anything." |
| 1 | 一个请求能把团队花费推过上限吗？ | "Yes. Check before sending, charge the full cost after. The next request is refused." |
| 1 | “月”怎么算？ | "A calendar month in UTC. month_of gives it." |
| 2 | 成本能存成美元吗？ | "Store whatever you like, as long as every cost and total comes back as whole micro-dollars, exactly." |
| 2 | 传进来 3500.0 这种整数值的 float 呢？ | "Reject it with TypeError. A float cost means someone did money in floats upstream." |
| 2 | calls() 按时间排还是按记录顺序？ | "Recorded order. Calls finish out of order." |
| 2 | 没有任何模型服务的调用算进 report 的 calls 吗？ | "Yes, it's a call. It is also the one that counts as failed." |
| 2 | 要不要建索引？ | "The tests don't need one. Tell me which you'd add." |
| 3 | 回退到下一个部署时，轮询要不要再走一步？ | "No. One plan per request, one step of the rotation." |
| 3 | weight 为 0 的部署怎么用？ | "Never first. Only as a fallback, in listed order." |
| 3 | 重试次数正好在计划用完时耗尽，报哪个错？ | "If no further try was needed, it's AllProvidersFailed. RetryBudgetExhausted means you wanted another try and couldn't make it." |
| 3 | region 是 None 时也有自己的轮询吗？ | "Yes. None is a region of its own." |
| 4 | 表头要在第一个事件之前就输出吗？ | "The header is the first thing yielded. Before or after pulling the first event, either is fine." |
| 4 | 结果的状态码有 4xx 吗？ | "No. Results are 200 or a 5xx here." |
| 4 | 探测请求一直没有结果怎么办？ | "The tests don't cover it. Tell me how you'd time it out." |
| 4 | 行尾用 \n 还是 \r\n？ | "Either. The test reads it with the csv module." |
| 5 | 直接传一个模型名可以吗？ | "Yes. A model stands for itself." |
| 5 | 内外两层 region 冲突，算错误吗？ | "No. That alias adds nothing. Its subtree is still checked for bad names and cycles." |
| 5 | max_depth 算不算模型那一层？ | "No, aliases only. The alias you expand is depth 1." |
| 5 | 环和深度超限同时出现，报哪个？ | "The tests don't pin it. I'd report the cycle as soon as you see it: it tells the operator more." |

## 每关：要看什么、提示、追问

### Part 1 修网关（目标 12 分钟）

一个测试里叠了 5 个缺陷和几个护栏：

1. `redact_messages` 只处理最后一条消息，而且把它重建成只有 role 和 content 的 dict。测试的第一个请求是工具执行完之后的那一轮，最后一条是 tool 消息，`tool_call_id` 被丢掉，假 API 回 400。
2. `Gateway.route` 的 `except ProviderError: continue` 对任何状态码都回退。于是这个 400 被依次发给三家，每家都回 400，客户端看到的是 `AllProvidersFailed: ... openai/gpt-4o 400, anthropic/claude-sonnet 400, google/gemini-pro 400`。报错在 gateway.py，根因在 guard.py，中间隔着一层假的服务商和一层回退循环。这一关想练的是：报错的位置往往不是出 bug 的位置，而回退会把真正的错误藏起来。
3. 修好字段以后，前面那条 user 消息里的卡号和 SSN 原样发了出去：只脱敏最后一条。断言是 "PII never leaves the gateway, in any message"。
4. `price = self.prices[chain[0]]` 在循环之前就定了单价。gpt-4o 503、sonnet 502、gemini 服务的请求按 gpt-4o 的价格算成 12,000 微美元，应该是 3,500。
5. `Budget.spent` 每次检查都把这个团队的全部历史扫一遍。15 万笔花费之后，200 个请求要 0.7 到 1.8 秒，限值 0.02 秒（修好的版本约 1 毫秒）。

护栏：
- 改成脱敏所有消息时，assistant 的工具调用消息 content 是 None，直接交给正则会报 `TypeError: expected string or bytes-like object`。
- `redacted` 要反映所有消息：第二个请求的 SSN 在第一条，最后一条没有 PII。
- 4xx 的判断写成 `== 400` 会挂在 422 上（AllProvidersFailed）；5xx 写成 `== 503` 会挂在 502 上（RequestRejected）。直接 `raise` 原来的 ProviderError 也不行，docstring 要的是 RequestRejected。
- 预算检查要在发送之前："a team at its cap is refused before anything is sent"。花费等于上限也要拒绝。
- 防过度修复：改成累计值以后，键必须带月份。只按团队累计，12 月 1 日零点的请求会被 11 月的花费挡住（BudgetExceeded）；只保留“当前月”一个计数器，12 月的请求进来后，11 月的花费查不到了（"last month's spend stays with last month"）。
- 按 (团队, 月) 分组存列表、每次再 `sum`，仍然是每个请求 O(n)，约 60 毫秒，过不了。把计算挪到 `charge` 里每次重算，填充 15 万笔花费的那段循环会触发 "a charge costs the same however much the team has already spent"。

看什么：是不是先读 traceback，再去看假服务商到底返回了什么；会不会打印发出去的消息；每改一处就重跑。

提示：
- H1："What did the first provider actually say?"
- H2："Print the messages the fake received. What is missing from the last one?"
- H3：直接指出 `redact_messages` 的最后一行和 `except` 分支。

追问：
- "Should a 429 fall back, retry the same provider, or neither?"（测验 Q14：429 尊重 Retry-After，同一家带退避重试；本题不涉及）
- "Two gateway replicas serve the same team. Where does the budget counter live?"（共享存储、原子加；测验 Q15）
- "The cost is known only after the reply. How do you stop concurrent requests from overshooting the cap?"（按 max_tokens 预扣，完成后结算）
- "Would you redact in place?"（不：调用方可能重试或记录原文；复制一份）
- "What does this regex miss?"（测验 Q6：带空格的卡号；需要更多规则或 ML）

### Part 2 成本账本（目标 11 分钟）

坑：
- 钱不能用浮点：REAL 列读回来是 float（"costs come back as whole micro-dollars"）；存美元再用 `int()` 换回来，249 会变成 248；`TOTAL()` 返回 float；不加 `COALESCE` 的 `SUM()` 在没有数据时返回 NULL。report 里用 `TOTAL()` 汇总时 `1270.0 == 1270`，等值比较发现不了，测试单独检查类型（"report totals are whole numbers too"）。
- 成本的类型检查写成 `isinstance(cost, int)` 会放过 `True`，测试不区分，可以拿来追问。
- 月份按 UTC：`2026-11-01T00:30+01:00` 属于 10 月，`2026-11-30T20:00-05:00` 属于 12 月。直接对带偏移的时间 `strftime("%Y-%m")` 会分错月；`BETWEEN '2026-10-01' AND '2026-10-31'` 会漏掉 10 月 31 日零点以后的调用。
- `calls()` 按记录顺序返回。记录顺序和时间顺序不同：第 5 条（12 月 1 日 01:00 UTC）比第 6 条（11 月 30 日 23:59 UTC）先记。team 和 month 两个条件同时给出时取交集。
- 编号在重开后接着来。用内存计数器会从 1 重新开始。
- attempts 是按顺序的 `Attempt` 元组。JSON 读回来的是 list，和 tuple 不相等；排序后存也不对。
- 没有模型服务时 `served_model` 是 None，不是字符串 "None"。failed 是“没有模型服务”，不是“成本为 0”：gpt-4o-mini 一个输入 token 是 0.15 微美元，按四舍五入收 0。
- report 按团队名排序，calls 数所有调用。
- 成本必须是 int：3500.0 也要报 TypeError。
- 时间要保留到微秒：测试里有 23:59:59.999999 和 .000250。

追问：
- "Prices change on the 15th. What does the ledger keep so last week's totals don't move?"（存当时收的钱，或者存价目表版本）
- "The provider invoices from summed tokens. Why can its total differ from yours?"（每次调用单独取整，汇总时不再取整）
- "Which index makes spend(team, month) cheap?"（(team, month)）
- "Two gateway processes write the same file?"（WAL、busy_timeout，或者单写进程）

### Part 3 加权与合规（目标 12 分钟）

坑：
- 平滑加权轮询（SWRR）：5:2:1 的首选顺序是 us, eu, us, us, sonnet, us, eu, us。普通的加权轮询会连续 5 次选 us；`random.choices` 不确定；第 4 步 us 和 sonnet 同分，取先列出的；胜者减去的是候选者权重之和，不是自己的权重，也不是池里所有部署的权重和（后者在 EU 的第 4 个计划上露出来）。
- 分数要跨请求保留在 Router 里；每个计划都从零开始算，就永远只选权重最大的那个。
- 计划的其余部分按列出顺序，不按权重排：第一个计划是 us, sonnet-eu, gpt-4o-eu, gemini-us。
- EU：先过滤再选；EU 有自己的轮询状态，EU 流量不能改变全局轮询；回退时也不能出 EU；一个合规部署都没有时报 NoEligibleDeployment，不返回空计划。
- 预算按尝试次数算，同一部署的重试也算。每次尝试之前检查；计划正好在预算耗尽时走完，报 AllProvidersFailed，不是 RetryBudgetExhausted。预算属于单个请求：把计数器放在 Router 上跨请求累加，第二个请求就会报 RetryBudgetExhausted。
- 合规部署的权重全是 0 时，计划就是列出顺序。SWRR 循环里一个候选者都没有，不特判会在 `best.name` 上报 AttributeError；报 NoEligibleDeployment 也不对，这些部署是合规的。
- 4xx 立即报 RequestRejected，即使这个部署还有 retries 也不重试。
- 每个请求只走一步轮询：`send` 里只调用一次 `plan`。

追问：
- "Each replica runs its own rotation. Does 5:2:1 still hold across the fleet?"（每个副本内精确，整体近似，不需要共享状态）
- "Retry budget per request, or one budget shared by all requests, as a ratio of retries to requests?"（共享的比例能防住大面积故障时的重试风暴）
- "An EU user asks for an alias with only US deployments. What should the client see?"（明确的错误，不能悄悄发到 US）

### Part 4 延迟感知路由（目标 15 分钟）

三段事件流，每个路由决定一行 CSV，测试逐行比较并给出这一行考的规则。

坑：
- 5xx 不是延迟样本：r04 时 sonnet 只有一个 503，仍然是 unmeasured。
- 没有样本的模型优先，按列出顺序；结果回来之前一直是 unmeasured（r02）。
- 中位数：偶数个取中间两个的平均。取上中位（`values[n // 2]`）在 r16 选错，取下中位在 q4 选错；用平均值在 q6 选错（4000 毫秒的离群值）；用最小值、最大值、最后一个样本也不对。
- 熔断：连续 3 个 5xx 打开，中间一次成功要清零（r11）；在第 3 个 5xx 的时间打开，冷却从这里算（r17 还关着，r18 正好到期）；打开期间的迟到成功不关闭熔断（r15）；冷却结束后只放一个探测（r19、q12）；探测失败从探测结果的时间重新冷却（r20）；探测成功才关闭（r24、q10）；探测优先于更快的模型（q11），也优先于没有样本的模型（s5）。
- 探测按 request_id 认：第三段流里 s3 是熔断前发给 gpt-4o 的请求，它的 502 在探测 s5 在途时才回来，既不结束探测，也不重新计时（s6）。只看“这个模型来了结果”就结束探测，s6 会被当成新的探测。探测成功关闭熔断以后，连续 5xx 从 0 重新计：打开熔断时没把计数清零，s7 的一个 503 就会把熔断重新打开（s8，trip_after=2）。
- 窗口：正好 window_ms 之前的样本已经过期（r22）；过期按请求的时间判断，不能等这个模型有新结果才淘汰。
- 所有熔断都打开时输出空模型和 unavailable（q8）；平局取先列出的（q3，按名字排序会选 anthropic）；trip_after 是参数（q7）。
- 格式：第一条是表头，每个 chunk 恰好一条 CSV 记录，带行尾。
- 每个请求一到就输出：测试数被拉取了几个事件，拿到第一个决定时只能拉了 1 个。写成普通函数时，测试报 `'async for' requires an object with __aiter__ method, got coroutine`。

追问：
- "Ten requests arrive before any result. They all go to the first model. Is that what you want?"（探索阶段；按在途请求数或 least-busy）
- "Median over a minute, EWMA, or p95?"（中位数抗离群值；SLA 看尾延迟）
- "For a chat UI, which latency do you measure?"（课里的场景：首 token 时间）
- "How would latency routing combine with Part 3's weights and EU filter?"（先合规过滤，再在剩下的里按延迟或权重选）

### Part 5 别名展开（目标 10 分钟）

坑：
- 未知名字要报 UnknownName。课里的 `ROUTES.get(alias, [alias])` 会把它当成模型发出去，再加上 `PRICES.get(model, (0, 0))`，这个调用还不要钱（测验 Q9）。直接传模型名是合法的，返回它自己。
- 同一个 alias 经两条路径到达不是环（coding 两次到 fast）；只用一个 visited 集合会误报。环的路径从重复的那个 alias 开始：`["a", "b", "c", "a"]`，不是从根开始。不做环检测、靠深度上限兜底，会报成深度错误。
- 深度：被展开的 alias 是第 1 层，正好 max_depth 层可以，多一层报错。
- 去重保留第一次出现的位置。被区域排除的模型不占位置，后面的路径还能加进来（eu-first）；按 alias 名字缓存展开结果、不区分 region，也会在这里挂。
- region 沿整条路径向下传，内层只能收窄不能放宽（eu-batch 里 us-batch 什么也不加）；调用方的 region 也一样，直接传进来的模型名也要服从它（`expand("openai/gpt-4o", region="eu")` 报 AliasError）；alias 的 region 和外层相同不算冲突（eu-smart 在 region="eu" 下照常展开）；冲突的子树仍然要检查名字和环。
- 环和深度超限同时出现时先报哪个，测试不区分，参考实现先查环。
- 什么都没选进来时报 AliasError，不返回空列表。

追问：
- "Expand per request, or once when the config loads?"（加载时按 (alias, region) 展开并缓存，配置变化时失效）
- "An alias points at a model that has no price. When do you find out?"（加载时就拒绝，见测验 Q9）
- "How would an operator see why a model is in a chain?"（记录展开路径）

## 记录与评分（原创练习，不是公司标准）

| 维度 | 分值 | 看什么 |
|---|---|---|
| 推进 | 40 | 每关 8 分，通过即得 |
| 调试方法 | 20 | 读 traceback、看假服务商收到了什么、一次只改一处、用 `-x -k` |
| 代码质量 | 15 | 修根因不凑测试；没有残留的死代码；命名清楚 |
| 沟通 | 15 | 先复述需求再动手；主动问澄清问题；说出取舍 |
| 生产意识 | 10 | 追问里答出并发、预扣、价目表版本、重试风暴、数据驻留 |

每一项都写下具体观察到的证据，没观察到的写“未观察”。提示次数和每关用时单独记录。
