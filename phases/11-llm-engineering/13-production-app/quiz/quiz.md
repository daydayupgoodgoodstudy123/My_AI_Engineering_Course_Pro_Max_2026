# 测验 · 构建生产环境中的 LLM 应用（Building a Production LLM Application）

> **阶段 11 · LLM 工程 · 第 13 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/production_app.py](../code/production_app.py) ｜ 代码讲解：[code/production_app.讲解.md](../code/production_app.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 生产架构的固定流程 | API 网关（鉴权 + 限流）→ 输入 guardrail → prompt 路由 → 语义缓存 →（未命中）流式 LLM 调用 → 输出 guardrail → eval 记录 → 成本记账 → SSE 返回 |
| 2 | 流式输出（streaming） | 总生成时间不变，但首 token 在 200–500ms 内到达，讲义称感知延迟下降约 90%；SSE 是默认选择 |
| 3 | 三层错误处理 | API 故障（429/500/超时）→ 指数退避 + 抖动；模型故障（格式错、幻觉函数名）→ 带错误信息重试；应用故障（向量库/缓存挂了）→ 优雅降级 |
| 4 | Fallback 模型链 | 主模型不可用时依次降级到其他模型 → 缓存答案 → "服务暂不可用"，用质量换可用性 |
| 5 | 可观测性三支柱 | 结构化日志（带 request ID）、分布式追踪（OpenTelemetry）、指标看板（P50 < 2s、P99 < 10s、缓存命中 > 30%、拦截率 < 5%、单请求成本 < $0.01） |
| 6 | Prompt 版本与 A/B 测试 | 模板带版本号；用 `hash(user_id) mod 100` 确定性分桶，保证同一用户体验一致；shadow mode 与百分比灰度 |
| 7 | 成本预测 | 上线前按 DAU × 次数 × token × 单价 × (1 − 缓存命中率) 估算月成本，决定商业模式是否成立 |
| 8 | 扩展模式 | 全链路 async、耗时任务进队列、连接池复用、水平扩展；LLM 应用是 I/O 密集而非 CPU 密集 |
| 9 | 上线检查清单 | 15 项：密钥放环境变量、限流、输入/输出 guardrail、缓存、流式、退避、fallback、结构化日志、成本追踪、健康检查、token 上限、超时、CORS、压测 |
| 10 | 组件之间的"接线"才是难点 | 讲义："Each one is a lesson you already completed. The engineering is in the wiring."——缓存键、错误是否入缓存、日志口径一致性都是接线问题 |

### 核心技能（能动手做到）

- [ ] 能画出生产 LLM 服务的请求流程图，并说明每个组件失败时系统应如何表现
- [ ] 用 `asyncio` 实现带指数退避 + 抖动的重试，以及跨模型的 fallback 链，并能算出最坏情况下的等待时间
- [ ] 用确定性哈希实现 A/B 分桶，验证流量比例
- [ ] 实现真正的流式响应（async generator + SSE），并处理流式输出与输出 guardrail 的矛盾
- [ ] 设计缓存键，避免跨模板、跨租户命中和"把错误答案缓存起来"
- [ ] 按讲义公式做月度成本预测，并换算成单请求成本
- [ ] 读出本节代码中"看起来在工作、实际没生效"的部分（伪语义缓存、伪流式、恒为 healthy 的健康检查、恒为 0 的错误计数）

---

## 二、基础自测（选择题）

**Q1.** 讲义说流式输出让"perceived latency drops by 90%"。下列解释正确的是：

- A. 流式输出让模型生成速度提高了约 10 倍
- B. 流式输出减少了输出 token 数
- C. 流式输出把请求变成了批处理，所以总耗时下降
- D. 总生成时间不变，但用户在首 token 到达（约 200–500ms）时就开始看到内容，而不必盯着加载动画等完整的 3–8 秒

**Q2.** 讲义把生产故障分成三层。下列"故障 → 处理方式"的对应全部正确的是：

- A. 429 限流 → 指数退避重试并排队；模型返回非法 JSON → 把错误信息带进提示词重试；向量库宕机 → 跳过 RAG 上下文继续回答
- B. 429 限流 → 立即切换到下一个模型，不重试；向量库宕机 → 重试 3 次后返回 500
- C. Guardrail 拦截 → 带退避重试 3 次；缓存宕机 → 拒绝所有请求
- D. 模型返回非法 JSON → 直接返回 500；API 超时 → 无限重试

**Q3.** 本节 A/B 测试用 `int(md5(f"{user_id}:{exp_name}"), 16) % 100` 分桶，而不是 `random.random()`。最主要的原因是：

- A. md5 比 `random` 更快
- B. md5 能让流量比例严格等于 10%
- C. 同一用户在同一实验中总是落在同一个桶，跨请求体验一致，实验数据也不会被"同一用户见过两个版本"污染
- D. 为了加密用户 ID

**Q4.** 本节 `simple_embedding` 用 SHA-256 哈希值生成 64 维向量。实测 `"What is the capital of France?"` 与 `"what is the capital of france?"` 的余弦相似度只有约 0.885，低于阈值 0.92。由此可知这个"语义缓存"实际上：

- A. 是真正的语义缓存，只是阈值设得太高
- B. 只对完全相同的文本有效（哈希不具备语义连续性，相近文本的向量与随机向量无异），连大小写不同都会未命中
- C. 会把所有查询都判为命中
- D. 只对中文无效

**Q5.** `call_llm_with_retry` 中的退避公式是 `backoff = min(2 ** attempt + random.uniform(0, 1), 10)`，`max_retries=3`。同一个模型连续失败时，三次重试前分别等待：

- A. 都是 1 秒
- B. 约 1–2 秒、2–3 秒、4–5 秒
- C. 约 1 秒、10 秒、100 秒
- D. 0.5 秒、1 秒、2 秒

**Q6.** 关于本节 `health_check()`，下列说法正确的是：

- A. 它会探测 LLM 提供商是否可用
- B. 它会检测缓存和向量库的连通性
- C. 它会在错误率超过阈值时返回 "degraded"
- D. 它的 `status` 永远是 `"healthy"`，只是汇总了缓存和成本统计；讲义检查清单第 11 项要求的是"返回依赖状态"的健康检查，负载均衡器靠它摘除坏实例

**Q7.** 讲义的成本预测：每天 50,000 次查询，缓存命中率 35%，每次 1,500 输入 / 400 输出 token，按 $2.50 / $10.00 每百万 token 计算。每月 LLM 成本约为：

- A. $7,556
- B. $11,625
- C. $13,163
- D. $3,900

**Q8.** 演示的负载测试打印 `Errors: 0`。下列说法正确的是：

```python
    results = await asyncio.gather(*tasks)
    errors = sum(1 for r in results if r.get("error"))
```

- A. 说明 20 个请求都没有触发任何重试
- B. 说明 fallback 链从未被使用
- C. 这个数字恒为 0：`handle_request` 返回的字典里根本没有 `"error"` 键（错误只写进了 `RequestLog`），即使所有模型都失败、返回了 fallback 文案也会显示 0
- D. `asyncio.gather` 会自动过滤掉失败的请求

---

## 三、动手 / 代码题

**Q9.** 阅读 `handle_request` 中缓存相关的代码：

```python
        effective_query = input_check.modified_text or query
        ...
        cached = self.cache.get(effective_query)
        if cached:
            ...
            return {"request_id": request_id, "response": cached["response"], "cache_hit": True, ...}

        template, rendered_prompt = select_prompt(template_name, user_id, variables)
        result = await call_with_fallback(rendered_prompt, template.model)
        ...
        self.cache.put(effective_query, result["text"])
```

1. 实验：把 `random.random` 固定为 0（所有调用都失败），用户 `u` 请求 "hello there"，随后用户 `u2` 请求同样的问题。`u2` 会得到什么？为什么这很危险？
2. 先用 `rag_answer` 模板（带 context）问 "Explain the RAG architecture"，再用 `general_chat` 模板问同一句，第二次会怎样？
3. 输出 guardrail 拦截后的替换文案会不会被缓存？
4. 重写缓存的读写逻辑，修复以上问题，并说明缓存键应包含哪些字段。

**Q10.** 下面是本节的"流式"实现：

```python
    async def handle_streaming_request(self, user_id, query, template_name="general_chat"):
        result = await self.handle_request(user_id, query, template_name)
        if result.get("cache_hit"):
            return result

        tokens = []
        async for token in stream_response(result["response"]):
            tokens.append(token)
        result["streamed"] = True
        result["stream_tokens"] = len(tokens)
        return result
```

1. 这个实现能降低首 token 延迟（TTFT）吗？为什么？
2. 把它改造成真正的流式：`handle_request` 拿到第一个 token 就向客户端推送，并以 SSE 格式（`data: {...}\n\n`、`data: [DONE]\n\n`）输出。
3. 流式输出和"输出 guardrail 需要看到完整文本"之间有什么矛盾？给出至少两种工程上的折中方案。

**Q11.** 关于重试与 fallback：

```python
async def call_llm_with_retry(prompt, model, max_retries=3):
    for attempt in range(max_retries + 1):
        try:
            failure_chance = 0.15 if attempt == 0 else 0.05
            if random.random() < failure_chance:
                raise ConnectionError(...)
            ...
        except (ConnectionError, TimeoutError):
            if attempt < max_retries:
                backoff = min(2 ** attempt + random.uniform(0, 1), 10)
                await asyncio.sleep(backoff)
            else:
                raise
    raise ConnectionError(f"All {max_retries} retries exhausted for {model.value}")
```

1. 当三个模型全部失败时，一个请求在返回 fallback 文案之前大约要等多久？（提示：实测约 25 秒。）讲义检查清单第 13 项要求外部调用超时 30 秒，这个设计是否合理？
2. 最后一行 `raise ConnectionError(...)` 什么时候会被执行？
3. 按模拟的失败率（首次 15%，之后 5%），单个模型 4 次全失败、三个模型全失败的概率分别是多少？这对"演示能否测到 fallback 路径"意味着什么？
4. 改写：给整条 fallback 链加一个总截止时间（例如 10 秒），只对可重试错误（429、5xx、超时）重试，并在 429 时优先使用服务端返回的 `Retry-After`。

**Q12.** 讲义"Cost Projection"表格中写输入单价 "$5.00 | OpenAI GPT-5 pricing"、输出单价 "$15.00"，但下面的算式用的是 $2.50 和 $10.00。

1. 分别按两组单价计算"有缓存（35%）"和"无缓存"的月成本。
2. 按讲义算式的结果，计算"每个用户请求"（含缓存命中）和"每次实际 LLM 调用"的平均成本，判断是否满足讲义指标表中 "Cost per request < $0.01"。
3. 讲义说"A 35% cache hit rate saves 35% on LLM costs"。在什么情况下这个结论不成立？

---

## 四、面试高频题

**Q13.**（基础必考）请描述一个生产级 LLM 应用从收到请求到返回响应的完整链路，以及每个组件存在的理由。

**Q14.**（原理深挖）流式输出为什么重要？SSE、WebSocket、长轮询怎么选？流式场景下怎么做输出安全检查和成本统计？

**Q15.**（工程实践）设计 LLM 调用的重试与降级策略。哪些错误该重试、哪些不该？如何避免重试风暴？fallback 到另一个厂商的模型时要注意什么？

**Q16.**（场景设计）产品经理写了一个新版 prompt，说"效果更好"。你怎么把它安全地上线，并用数据证明它确实更好？

**Q17.**（追问型）月底账单突然从 $3,000 涨到 $12,000，P99 延迟也翻倍了。你会怎么定位原因？平时应该记录哪些数据才能快速回答这个问题？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："A GPT-5 response with 500 output tokens takes 3-8 seconds to fully generate... With streaming, the first token arrives in 200-500ms. The total time is the same. The perceived latency drops by 90%." 关键指标是 TTFT（time to first token）。A、B 错，流式不改变生成速度和 token 数；C 把流式和批处理混为一谈。

### Q2 — 答案：A

对应讲义三层错误处理与表格："API 429 | Yes, with backoff | Queue the request"；Model failures："retry with a corrected prompt. Include the error in the retry message"；"Vector store down | No retry on vector store | Skip RAG context"。B 错，429 应先退避重试；C 错，讲义："Guardrail block | No"（不重试），"Cache down | ... | Direct LLM call"；D 错，无限重试会放大故障。

### Q3 — 答案：C

讲义："Use a deterministic hash of the user ID, not random selection. This ensures each user gets a consistent experience across requests within the same experiment." 把实验名也拼进哈希，使不同实验的分桶相互独立。B 错，哈希分桶是近似比例：实测 1,000 个用户中 v2 占 10.9%，不是严格 10%（而且因为是确定性的，每次运行都是 10.9%）。A、D 不是目的。

### Q4 — 答案：B

SHA-256 有"雪崩效应"：输入改一个字符，输出完全不同。哈希出来的 64 个值都在 [0, 1] 区间，两个**无关**文本的余弦相似度均值约 0.75（实测 2,000 对随机文本均值 0.7492，最大 0.8779），所以阈值 0.92 下只有完全相同的文本才能命中。代码第一段哈希用了 `text.lower().strip()`，但补齐到 64 维的第二段哈希用的是原始 `text`，导致大小写不同的两句只有一半向量相同，相似度 0.8852，**连"忽略大小写"的意图都没实现**。实测还有：末尾多一个空格 0.8691、去掉问号 0.8204。讲义说"Two questions phrased differently but meaning the same thing will hit the cache"，本实现做不到；生产中要用 `text-embedding-3-small` 一类的真实 embedding。

### Q5 — 答案：B

`attempt` 依次为 0、1、2 时等待 `2^0 + U(0,1)`、`2^1 + U(0,1)`、`2^2 + U(0,1)`，即 1–2、2–3、4–5 秒；`min(..., 10)` 封顶 10 秒（本例用不上）。第 4 次（attempt = 3）失败后不再等待，直接抛出。注意与讲义略有差异：讲义写的是"1s + random(0, 0.5s)、2s + random(0, 1.0s)、4s + random(0, 2.0s)"，抖动与基数成比例；代码的抖动固定为 0–1 秒。

### Q6 — 答案：D

```python
    def health_check(self):
        return {
            "status": "healthy",
            ...
        }
```

状态是硬编码的字符串。讲义检查清单第 11 项："Health check endpoint returning dependency status"；Key Terms："An endpoint that returns the status of all dependencies (cache, LLM availability, guardrails) -- used by load balancers and Kubernetes to route traffic"。A、B、C 都是它应该做但没有做的事。生产中通常区分 liveness（进程活着）与 readiness（依赖可用、能接流量）。

### Q7 — 答案：A

有效查询 `50,000 × (1 − 0.35) = 32,500` 次/天。输入 `32,500 × 1,500 × 30 / 1,000,000 × $2.50 = $3,656.25`，输出 `32,500 × 400 × 30 / 1,000,000 × $10 = $3,900`，合计 **$7,556.25**（已用 Python 计算）。B 是无缓存的成本；C 是按表格里 $5/$15 计算的有缓存成本（见 Q12）；D 只算了输出。

### Q8 — 答案：C

`handle_request` 的正常返回字典键为 `cache_hit, cost_usd, guardrail_output_pass, input_tokens, latency_ms, model, output_tokens, pii_detected, request_id, response`（实测），没有 `error`。即使 `call_with_fallback` 返回了带 `"error"` 的 fallback 结果，`handle_request` 也只把它写进 `RequestLog.error`，没有放进返回值。已用"强制所有调用失败"的实验验证：返回 `model='fallback'`，`r.get('error')` 为 `None`。A、B 错：负载测试的总耗时在多次运行中从约 0.3 秒到 3.4 秒不等，正是有请求触发了 1–2 秒以上的退避重试——重试确实发生了，只是没被统计。正确做法：返回值里带 `error`/`degraded` 字段，或直接从 `request_logs` 统计。

### Q9 — 参考答案

1. `u2` 会**立刻从缓存拿到 "I apologize, but I am temporarily unable to process your request..."**（已实际验证：`cache_hit=True`）。`handle_request` 不区分成功与否，`call_with_fallback` 返回的降级文案也被 `self.cache.put` 存了进去，TTL 是 1 小时。于是一次短暂的上游故障会在接下来一小时内持续影响所有问同样问题的用户——这叫**缓存中毒**，把短故障放大成长故障。另外，这次失败的请求还被按 gpt-4o-mini 的价格计了费（实测 `$1.53e-05`），而实际上没有任何成功调用。
2. 第二次**直接命中缓存，拿到 RAG 模板的回答**（实测返回 "According to the provided context..."）。缓存键只有查询文本，不含模板名、模板版本和 RAG 上下文。同理，A/B 实验的 v1、v2 也共享缓存：被分到 v2 的用户可能拿到 v1 的回答，实验数据被污染；不同用户也共享缓存，若回答里含个人信息就会串号。
3. **会**。输出 guardrail 拦截后 `result["text"]` 被替换成 "I cannot provide that response as it was flagged..."，随后照样 `put` 进缓存。
4. 参考改写：

```python
def cache_key(template, rendered_variables, tenant_id):
    payload = json.dumps({
        "tpl": template.name, "ver": template.version,       # 模板与版本
        "vars": rendered_variables,                           # 含 query、context 等
        "tenant": tenant_id,                                  # 租户/权限范围
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

# 写缓存：只缓存"成功且通过输出检查"的结果
if result["model"] != "fallback" and output_check.passed and not result.get("error"):
    self.cache.put(key, result["text"])
```

语义缓存则在"同一个 (模板, 版本, 租户) 命名空间"内按 query embedding 查找；RAG 场景还要把知识库版本纳入键，知识库更新时整体失效。

### Q10 — 参考答案

1. **不能。** `await self.handle_request(...)` 会等完整回答生成完毕才返回，之后再把**已经完整的字符串**按词切开、每词 sleep 20–80ms "假装"流式。首 token 延迟 = 完整生成时间，而且总时间还多了 61 个词 × 平均 50ms ≈ 3 秒的人为延迟。讲义 FastAPI 示例里的 `stream=True` 分支也是同样的写法。
2. 参考改写（模拟模型用 async generator 逐 token 产出；真实场景替换为讲义 "Real API Integration" 中的 `call_openai` / `call_anthropic`）：

```python
async def llm_stream(prompt):                      # 模拟上游流式接口
    for i, word in enumerate(SIMULATED_RESPONSES["general"].split()):
        await asyncio.sleep(random.uniform(0.02, 0.08))
        yield word if i == 0 else " " + word

async def handle_stream(self, user_id, query, template_name="general_chat"):
    check = check_input_guardrails(query)
    if not check.passed:
        yield f"data: {json.dumps({'error': check.blocked_reason})}\n\n"
        return
    template, prompt = select_prompt(template_name, user_id, {"query": check.modified_text or query})
    start, first, parts = time.time(), None, []
    async for token in llm_stream(prompt):
        if first is None:
            first = time.time() - start            # 记录 TTFT
        parts.append(token)
        yield f"data: {json.dumps({'token': token})}\n\n"
    yield "data: [DONE]\n\n"
    # 流结束后：完整文本做输出检查、记账、写日志
```

在 FastAPI 中用 `StreamingResponse(service.handle_stream(...), media_type="text/event-stream")` 返回。

3. **矛盾**：输出 guardrail 需要看到内容才能判断，但流式要求"边生成边发送"，发出去的 token 收不回来。折中方案：
   - **滑动窗口/按句检查**：缓冲到句号或 N 个 token 再检查后发送，以几百毫秒延迟换安全；
   - **流中检查 + 中断**：边发边检查，一旦命中就停止流并发送"内容已撤回"事件，前端替换已显示内容；
   - **按风险分级**：高风险场景（如生成 SQL、代码执行）不流式或先完整校验；普通聊天流式；
   - **结构化输出**：需要 JSON 校验的接口整体生成后再返回。
   成本统计在流结束时根据 `usage`（OpenAI 需开启 `stream_options.include_usage`）或累计 token 数记账。

### Q11 — 参考答案

1. 每个模型 3 次退避约 `1.5 + 2.5 + 4.5 ≈ 8.5` 秒，加上每次失败前的调用耗时；三个模型串行约 25 秒（实测把 `asyncio.sleep` 替换为计时器后，9 次退避合计 25.15 秒）。这意味着在上游大面积故障时，每个请求都要挂起 25 秒才拿到"暂不可用"，用户早已离开，而服务器的并发连接被大量占用。还没有算上每次真实调用自身的超时（代码里没有设置单次调用超时）。合理做法是给整个请求一个总预算（如 10–30 秒），预算用完立即降级。
2. **永远不会执行。** 循环最后一轮（`attempt == max_retries`）失败时 `else: raise` 已经把异常抛出；成功则提前 `return`。这行是不可达代码（防御性写法，但掩盖了真实逻辑）。
3. 单个模型 4 次全失败：`0.15 × 0.05³ = 1.875 × 10⁻⁵`；三个模型全失败：约 `6.6 × 10⁻¹⁵`（已计算）。也就是说演示**几乎不可能**走到 fallback 文案和"错误计数"路径，这些代码在演示中从未被验证过——必须像 Q9 那样用故障注入（固定 `random.random` 返回 0）专门测试。
4. 参考实现：

```python
RETRYABLE = {429, 500, 502, 503, 504}

class LLMError(Exception):
    def __init__(self, status, retry_after=None):
        super().__init__(f"status={status}")
        self.status, self.retry_after = status, retry_after

async def call_with_deadline(prompt, chain, deadline_s=10.0, max_retries=2):
    loop = asyncio.get_running_loop()
    end = loop.time() + deadline_s
    last = None
    for model in chain:
        for attempt in range(max_retries + 1):
            remaining = end - loop.time()
            if remaining <= 0:
                return degraded_response(last)
            try:
                return await asyncio.wait_for(raw_call(prompt, model), timeout=remaining)
            except asyncio.TimeoutError as e:
                last = e
            except LLMError as e:
                last = e
                if e.status not in RETRYABLE:
                    break                              # 4xx 参数错误等：换模型或直接失败
                if attempt < max_retries:
                    wait = e.retry_after or min(2 ** attempt, 8) * random.uniform(0.5, 1.5)
                    await asyncio.sleep(min(wait, max(0, end - loop.time())))
    return degraded_response(last)
```

要点：总截止时间、单次超时、只重试可重试错误、尊重 `Retry-After`、抖动避免重试风暴、降级结果带 `degraded=True` 且**不入缓存**。

### Q12 — 参考答案

1. （已用 Python 计算）

| 单价（入/出，每百万） | 有缓存（32,500 次/天） | 无缓存（50,000 次/天） |
|----------------------|----------------------|----------------------|
| $2.50 / $10.00（讲义算式） | $7,556.25 | $11,625 |
| $5.00 / $15.00（讲义表格） | $13,162.50 | $20,250 |

表格与算式用的不是同一组价格，结论相差约 74%。做成本预测时价格来源必须与计算一致，并注明日期。

2. 每个用户请求平均：`$7,556.25 / (50,000 × 30) ≈ $0.00504`；每次实际 LLM 调用：`1,500 × 2.5e-6 + 400 × 1e-5 = $0.00775`。两者都低于 $0.01，满足指标。但如果用 $5/$15 的价格，每次 LLM 调用是 $0.0135，就**超标**了。
3. 结论成立的前提是"命中与未命中的请求成本相同"且命中本身零成本。不成立的情况：命中的多是短小便宜的 FAQ，而长且贵的请求（长上下文、代码审查）很少重复——按请求数算命中 35%，按成本算可能只省 10%；语义缓存本身有 embedding 与向量库成本（上一节讲义中约 $180/月）；provider prompt caching 与应用层缓存叠加时，节省比例不能简单相加。

### Q13 — 参考回答要点

- **API 网关**：鉴权、按用户限流、CORS、请求大小限制——在任何 LLM 逻辑之前挡掉滥用。
- **输入 guardrail**：注入检测、PII 脱敏、话题范围（第 12 节）。
- **Prompt 路由**：按请求类型选模板与版本，A/B 分桶；模板带版本号，便于回滚。
- **缓存**：精确/语义缓存，命中直接返回（第 11 节）；键要包含模板版本与租户。
- **RAG / 工具**（如有）：检索上下文、调用函数；失败时降级而不是整体失败。
- **LLM 调用**：流式、超时、退避重试、fallback 模型链。
- **输出 guardrail**：危险内容、格式校验、PII。
- **Eval 记录 + 成本记账 + 结构化日志/追踪**：每一步都带同一个 request ID。
- **响应**：SSE 流式返回。
- 加分点：说明哪些组件是"关键路径"（失败必须报错），哪些是"次要路径"（失败应降级，讲义："Never let a secondary system crash the primary flow"）；并指出组件之间的接线问题（缓存键、错误是否入缓存、日志口径）。

### Q14 — 参考回答要点

- **重要性**：用户等待的心理阈值约 3 秒（讲义："Users leave after 3"），流式把 TTFT 降到亚秒级。
- **协议选择**（讲义表格）：SSE 单向、基于 HTTP、实现简单，三大厂商的 API 都用它，是默认选择；WebSocket 双向，适合语音、实时协作；长轮询只用于不支持前两者的旧客户端。SSE 要注意代理/负载均衡的缓冲与超时配置，客户端断开时要取消上游请求以免白白付费。
- **输出安全**：见 Q10 第 3 问——按句缓冲检查、流中中断撤回、按风险分级是否流式。
- **成本统计**：流结束时从最终 chunk 的 usage 字段记账；中途断开也要按已生成 token 计费。
- **可观测性**：分别记录 TTFT、TPOT（每 token 时间）与总时长。
- 常见误区：先生成完再分块发送（本节 `handle_streaming_request` 的做法），TTFT 毫无改善。

### Q15 — 参考回答要点

- **该重试**：429、500/502/503/504、网络超时。**不该重试**：400（参数错误）、401/403（鉴权）、内容策略拒绝、guardrail 拦截（讲义："Guardrail block | No"）。
- **退避**：指数退避 + 抖动，尊重 `Retry-After`；设置最大重试次数和**总时间预算**（Q11）。
- **避免重试风暴**：抖动；重试预算（如重试请求不超过总请求的 10%）；circuit breaker——某个模型错误率超过阈值时短时间内直接跳过它，而不是每个请求都去试一遍再退避。
- **跨厂商 fallback**：提示词格式与能力差异（system prompt、工具调用格式、上下文长度、结构化输出支持）；输出质量差异要事先评估；成本与合规（数据能否发往另一家厂商）；日志里记录实际使用的模型，以便分析质量变化。
- **幂等性**：有副作用的工具调用（下单、发邮件）重试前要确认幂等，或使用幂等键。
- 加分点：降级结果不入缓存（Q9）；对用户透明地标注"降级回答"。

### Q16 — 参考回答要点

- **离线评估先行**：在固定评测集上对比新旧 prompt（准确率、格式合规率、LLM-as-judge 打分、长度/成本）。
- **Shadow mode**：新 prompt 对 100% 流量运行但只记录不展示（讲义："No user risk, full data"），注意这会使 LLM 成本翻倍。
- **灰度发布**：确定性哈希分桶，10% → 25% → 50% → 100%（讲义），每一步观察质量与业务指标。
- **指标**：用户评分/点赞、追问率、重新生成率、任务完成率、错误率、延迟、单请求成本；按版本分组看板（讲义练习 4）。
- **统计显著性**：样本量足够、按用户而非请求分组分析，避免同一重度用户主导结果。
- **自动回滚**：讲义练习 4——新版本在 100 个请求内错误率达到旧版本 2 倍就自动回滚。
- **工程配套**：版本化存储所有 prompt、日志里记录 `prompt_version`（本节 `RequestLog` 已有该字段）、缓存键包含版本（否则 Q9 的问题会污染实验）。

### Q17 — 参考回答要点

- **按维度拆账**：按功能/模板、模型、用户/租户、日期拆分成本（本节 `CostTracker.cost_by_user` / `cost_by_model` 是雏形）；找出增长最大的维度——常见原因是某功能上下文变长、某用户/脚本滥用、路由把流量导向了贵模型、缓存命中率下降、重试风暴。
- **关联延迟**：P99 翻倍可能来自上游限流导致的退避重试（重试也会增加成本）、长上下文请求增多、缓存失效、fallback 到慢模型。
- **用追踪定位**：OpenTelemetry 把一次请求拆成缓存、检索、guardrail、LLM 调用等 span，直接看是哪一段变慢（讲义练习 5）。
- **平时要记录**：每个请求的 request ID、用户、模板及版本、模型、输入/输出/缓存 token、成本、TTFT 与总延迟、缓存命中、guardrail 结果、重试次数、错误、是否降级（讲义 Structured logging 列出的字段）；日志里避免存原文 PII。
- **预防**：按用户/租户的日预算与告警（讲义练习 3：单用户超 $0.50/天降级到 mini，总额超 $100/天进入紧急模式）；输入/输出 token 上限（检查清单第 12 项）。
- 常见误区：只看总账单不看分布；日志里没有模型名和 token 数，事后无法归因。

---

## 六、关联知识点

### 前置知识
- [阶段 11 · 01 Prompt Engineering](../../01-prompt-engineering/docs/zh.md)：模板与版本化管理的基础。
- [阶段 11 · 06 RAG](../../06-rag/docs/zh.md)：`rag_answer` 模板背后的检索增强生成。
- [阶段 11 · 09 Function Calling 与工具使用](../../09-function-calling/docs/zh.md)：讲义练习 2 要求把工具注册表接入服务。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../10-evaluation/docs/zh.md)：eval 记录与 prompt A/B 的评估方法。
- [阶段 11 · 11 缓存、请求速率限制与成本优化](../../11-caching-cost/docs/zh.md)：语义缓存、成本追踪、限流。
- [阶段 11 · 12 Guardrails、安全及内容过滤](../../12-guardrails/docs/zh.md)：输入/输出 guardrail。

### 本节被哪些后续内容用到
- [阶段 11 · 14 Model Context Protocol](../../14-model-context-protocol/docs/zh.md)、[阶段 11 · 15 Prompt 缓存与上下文缓存](../../15-prompt-caching/docs/zh.md)：讲义 Related 指出二者是 2026 年生产栈的标配。
- [阶段 13 · 20 OpenTelemetry GenAI](../../../13-tools-and-protocols/20-opentelemetry-genai/docs/zh.md)、[阶段 17 · 13 LLM Observability 技术栈选型](../../../17-infrastructure-and-production/13-llm-observability/docs/zh.md)：追踪与可观测性。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../../17-infrastructure-and-production/08-inference-metrics-goodput/docs/zh.md)：流式延迟指标。
- [阶段 17 · 19 AI 网关](../../../17-infrastructure-and-production/19-ai-gateways/docs/zh.md)：把限流、fallback、成本追踪放到网关层。
- [阶段 17 · 20 Shadow Traffic、金丝雀与渐进式部署](../../../17-infrastructure-and-production/20-shadow-canary-progressive/docs/zh.md)、[阶段 17 · 21 对 LLM Features 进行 A/B 测试](../../../17-infrastructure-and-production/21-ab-testing-llm-features/docs/zh.md)：prompt 上线与实验。
- [阶段 17 · 22 对 LLM APIs 进行负载测试](../../../17-infrastructure-and-production/22-load-testing-llm-apis/docs/zh.md)：检查清单第 15 项"100 并发压测"。
- [阶段 19 · 08 面向受监管行业的生产级 RAG 聊天机器人](../../../19-capstone-projects/08-production-rag-chatbot/docs/zh.md)、[阶段 19 · 11 LLM Observability 与评估仪表盘](../../../19-capstone-projects/11-llm-observability-dashboard/docs/zh.md)：综合项目。

### 延伸关键词
`FastAPI / Uvicorn` · `SSE / EventSource` · `TTFT / TPOT` · `exponential backoff + jitter` · `Retry-After` · `circuit breaker` · `fallback chain` · `graceful degradation` · `liveness / readiness probe` · `OpenTelemetry` · `structured logging` · `shadow mode / canary` · `cache poisoning` · `unit economics`
