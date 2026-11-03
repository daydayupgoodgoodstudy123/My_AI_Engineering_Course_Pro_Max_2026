# 测验 · LLM 路由层：LiteLLM、OpenRouter、Portkey（LLM Routing Layer — LiteLLM, OpenRouter, Portkey）

> **阶段 13 · 工具与协议 · 第 21 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 为什么需要路由层 | 成本（按任务选大/小模型）、故障转移、延迟 SLA、合规（区域）、实验（A/B）——每个集成都手写一遍太重复 |
| 2 | OpenAI 兼容代理 | 网关暴露 `/v1/chat/completions`，接收 OpenAI schema，内部转发到 Anthropic / Gemini / Ollama 等，客户端无感知 |
| 3 | 模型别名 | 代码里写 `smart` / `fast` 之类的逻辑名，网关映射到具体模型；换代时只改服务端映射 |
| 4 | Fallback chain | 别名 → 按优先级排列的具体模型列表；遇到 5xx 依次尝试，全部失败则拒绝；重试计入预算，避免级联放大成本 |
| 5 | 成本追踪 | 每次请求记录 provider、model、输入/输出 token，乘以每百万 token 单价，按用户/团队/项目聚合 |
| 6 | 缓存 | 讲义的语义缓存以 prompt embedding 为键，近似 prompt 共享缓存；练习 2 的 SHA-256 键只是精确匹配缓存 |
| 7 | 网关级 guardrail | 发送前 PII 脱敏、拒绝违规内容、输出过滤；讲义：Portkey、Kong 自带，LiteLLM 可选 |
| 8 | 按 key 限额 | 一个 API key 对应一个团队，按 key 设预算与限流，防止一个团队耗尽共享配额 |
| 9 | 三类网关 | LiteLLM：开源自托管，适合有 SRE、要数据主权；OpenRouter：托管 SaaS、额度计费，适合快速原型；Portkey：开源 + 托管，自带 guardrail 与合规能力 |
| 10 | 路由策略 | 静态优先级、负载均衡（轮询/加权）、成本感知、延迟感知、任务感知（prompt 分类器） |

### 核心技能（能动手做到）

- [ ] 根据 `PRICES` 和 token 数手算一次请求的成本，并与代码输出核对
- [ ] 跟踪 `route()` 在主模型故障时的 `attempts` 列表与最终选中的模型
- [ ] 指出本节 PII 正则能拦住什么、漏掉什么，并补充规则
- [ ] 实现一个以 SHA-256 为键的精确缓存，算出重复调用节省的成本
- [ ] 区分"可重试错误"和"不可重试错误"，为 fallback 加重试预算和熔断器
- [ ] 根据团队规模、合规、运维能力在 LiteLLM / OpenRouter / Portkey 之间做选择并说明理由

---

## 二、基础自测（选择题）

**Q1.** 应用代码调用 `smart` 而不是 `openai/gpt-4o`，最主要的好处是：

- A. 换模型（新一代发布、供应商故障、成本调整）时只改网关端映射，应用代码不用动
- B. 别名能让请求更快
- C. 别名让 token 计费变便宜
- D. 别名可以绕过供应商的速率限制

**Q2.** 本节场景 2 把 `openai/gpt-4o` 加入 `OUTAGE` 后调用 `route("smart", ...)`。输出的 `attempts` 和 `chosen` 是：

- A. `['openai/gpt-4o']`，`openai/gpt-4o`
- B. `['anthropic/claude-sonnet']`，`anthropic/claude-sonnet`
- C. `['openai/gpt-4o', 'anthropic/claude-sonnet']`，`anthropic/claude-sonnet`
- D. `['openai/gpt-4o', 'anthropic/claude-sonnet', 'google/gemini-pro']`，`google/gemini-pro`

**Q3.** 场景 1：消息 `"explain MCP"`（11 个字符），`provider_call` 计算 `prompt_tokens = len // 4`、`completion_tokens = max(20, len // 3)`，`openai/gpt-4o` 单价为每百万 token 输入 5.0、输出 15.0 美元。本次成本是：

- A. $0.000031
- B. $0.003100
- C. $0.000300
- D. $0.000310

**Q4.** 讲义练习 2 让你用"prompt 的 SHA-256 作为查找键"实现缓存。它与讲义所说的 semantic caching 的关系是：

- A. 完全相同，SHA-256 就是一种 embedding
- B. SHA-256 只能命中**逐字节相同**的请求；语义缓存以 embedding 为键，近似的 prompt 也能共享结果
- C. SHA-256 缓存命中率一定高于语义缓存
- D. 语义缓存不需要任何相似度阈值

**Q5.** 一家受监管的公司要求：网关自带 PII 脱敏等 guardrail、需要完整的 OTel 可观测性、使用自己的供应商 key。按讲义的对比表，最贴合的是：

- A. OpenRouter
- B. Portkey
- C. 直接调用单一供应商 API，不用网关
- D. 任何网关都一样

**Q6.** 下列输入经过本节 `redact_pii` 后，哪一个**没有**被脱敏？

- A. `"contact me at SSN 123-45-6789 please"`
- B. `"card 4111111111111111 ok"`
- C. `"order 1234567890123456"`
- D. `"card 4111 1111 1111 1111"`

**Q7.** "用一个 prompt 分类器把 `code ...` 发给擅长编码的模型、把 `summarize ...` 发给更快的模型"属于讲义中的哪种路由策略？

- A. 任务感知（task-aware）
- B. 静态优先级（static priority）
- C. 负载均衡（load balancing）
- D. 延迟感知（latency-aware）

**Q8.** 讲义说 fallback 的"Retries count against a budget"，其主要目的是：

- A. 让第一个供应商永远不会被跳过
- B. 保证每个请求都尝试链上所有供应商
- C. 防止大面积故障时级联重试把成本和延迟放大
- D. 让缓存命中率更高

---

## 三、动手 / 代码题

**Q9.** 阅读 `route()` 中的这两行：

```python
    chain = ROUTES.get(alias, [alias])
    ...
            in_rate, out_rate = PRICES.get(model, (0, 0))
```

执行 `route("evil/free-model", [{"role": "user", "content": "x" * 4000}])`，写出 `chosen_model`、`attempts`、`input_tokens`、`output_tokens`、`cost_usd`。同样的消息走 `smart` 的成本是多少？这两行默认值组合起来造成了什么问题？怎么改？

**Q10.** 本节网关号称面向"tool-calling 工作负载"，但 `route()` 的脱敏循环是这样写的：

```python
    for m in messages:
        txt, r = redact_pii(m["content"])
        if r:
            inv.redacted = True
        new_msgs.append({"role": m["role"], "content": txt})
```

1. 对一条 `{"role": "assistant", "content": None, "tool_calls": [...]}` 消息会发生什么？对 `content` 为多模态列表（`[{"type": "text", "text": "hi"}]`）的消息呢？
2. 对 `{"role": "tool", "tool_call_id": "call_1", "content": "42"}`，转发给供应商的消息长什么样？这为什么会破坏 function calling？
3. 改写这段循环。

**Q11.** 完成讲义练习 2：实现一个 SHA-256 精确缓存 `cached_route(alias, messages)`。要求：缓存键包含 alias、**脱敏后**的完整 messages（以及采样参数）；命中时成本记为 0，`attempts` 记为 `["cache"]`；失败结果不缓存。对消息 `"explain MCP in one paragraph please"` 连续调用 10 次，算出有缓存和无缓存的总成本。

**Q12.** fallback 循环只写了 `except RuntimeError: continue`。

1. 如果供应商 SDK 抛的是 `TimeoutError` 会怎样？如果供应商返回的是 400（请求本身不合法），按讲义"on 5xx"的规则该不该换下一个供应商？
2. 一次主模型持续宕机期间，每个请求都会先打一次宕机的供应商。请加一个熔断器（连续失败 3 次后 30 秒内跳过该模型）和"最多尝试 2 个模型"的重试预算，写出代码，并说明 5 个连续请求一共会调用供应商几次。
3. 运行完 `demo()` 后，模块级 `OUTAGE` 里还剩什么？这说明了全局可变状态的什么问题？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 LLM 路由网关？它解决了哪些问题？OpenAI 兼容接口在其中起什么作用？

**Q14.**（原理深挖）设计一个可靠的 fallback 机制：哪些错误该重试、该换供应商还是同供应商重试、如何避免重试风暴？fallback 到另一个模型会带来哪些"非故障"风险？

**Q15.**（工程实践）讲义练习 4：为每个团队设计月度预算。按请求还是按时间窗口执行？请求开始时还不知道输出 token 数，如何预扣？并发请求如何避免超支？

**Q16.**（场景设计）你们有一个面向欧盟用户的客服 agent（需要合规、低延迟），还有一个内部离线批量摘要任务（成本敏感）。请设计别名、fallback chain、guardrail 和网关选型。

**Q17.**（追问型）网关层的语义缓存能省 30%–60% 的成本（讲义数据），为什么很多团队仍然不敢在 agent 场景下打开它？什么时候缓存是安全的？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义 "Model aliases"："When a provider ships a new generation, you change the alias server-side; your code does not touch a thing." 别名本身不改变速度（B）或价格（C）；也不能绕过速率限制（D）——限流反而常常按 key/别名配置在网关上。

### Q2 — 答案：C

`ROUTES["smart"] = ["openai/gpt-4o", "anthropic/claude-sonnet", "google/gemini-pro"]`。循环先把 `openai/gpt-4o` 加入 `attempts`，调用抛 `RuntimeError("simulated 5xx ...")`，被 `except` 捕获后 `continue`；再尝试 `anthropic/claude-sonnet` 成功并立即 `return`，所以 `gemini-pro` 不会被尝试。实际输出：

```text
  chosen  : anthropic/claude-sonnet
  attempts: ['openai/gpt-4o', 'anthropic/claude-sonnet']
  cost    : $0.000309
```

B 漏掉了失败的那次尝试（`attempts` 会记录所有尝试过的模型）；D 是两个都宕机时才会出现的情况。

### Q3 — 答案：D

`prompt_tokens = 11 // 4 = 2`，`completion_tokens = max(20, 11 // 3) = max(20, 3) = 20`。成本 = `(2 × 5.0 + 20 × 15.0) / 1,000,000 = 310 / 1,000,000 = $0.000310`，与实际输出 `cost    : $0.000310` 一致。A 小了 10 倍；B 大了 10 倍（单位换算出错）；C 只算了输出部分（`20 × 15 = 300`）。可以看到输出 token 单价是输入的 3 倍，短 prompt 的成本几乎全部来自输出。

### Q4 — 答案：B

讲义："Keys are embedding-based; near-identical prompts share a cache slot." SHA-256 是密码学哈希，输入改一个字符结果就完全不同，所以只能做精确匹配。A 错：哈希不保留语义相似性。C 错：精确缓存的命中率不会高于（同阈值下的）语义缓存。D 错：语义缓存必须设相似度阈值，阈值太松会把不同问题的答案返回给用户（见 Q17）。

### Q5 — 答案：B

讲义对比表：Portkey "Open source (Mar 2026) + managed"、"Billing: Your own keys"、"Observability: Full OTel + PII redaction"、"Best for: Production with compliance"；正文："Portkey wins when you need guardrails and compliance out of the box." A：OpenRouter 用 OpenRouter 额度计费、可观测性是 dashboard，适合快速原型。C：直接调用失去 fallback 与集中 guardrail。D 显然不对。LiteLLM 也可以满足（自建 guardrail），但讲义说它"leaves them optional"，需要自己投入运维。

### Q6 — 答案：D

已实测：

| 输入 | 结果 |
|------|------|
| `"contact me at SSN 123-45-6789 please"` | `SSN [REDACTED]`（SSN 正则） |
| `"card 4111111111111111 ok"` | `[REDACTED]`（16 位连续数字） |
| `"order 1234567890123456"` | `[REDACTED]`——**误伤**：订单号也是 16 位数字 |
| `"card 4111 1111 1111 1111"` | **未脱敏**——卡号带空格就漏掉 |

另外 `"ssn 123456789"`（无横线）、邮箱、电话也都不会被处理。正则脱敏要在漏报与误报之间取舍，生产通常用"正则 + Luhn 校验 + ML 实体识别"组合。

### Q7 — 答案：A

讲义 "Routing strategies"："Task-aware. Prompt classifier routes coding to one model, summarization to another." 这也正是讲义练习 3。B 是"按列表顺序、出错再换"；C 是轮询或加权分流；D 是"选最近 N 分钟最快的模型"。

### Q8 — 答案：C

讲义："Gateways define this in a config. Retries count against a budget so fallback cascades do not explode cost." 大面积故障时，若每个请求都把链上所有供应商试一遍（甚至每个还重试多次），成本和延迟会成倍放大，还可能把压力转嫁到备用供应商导致连锁故障。A、B 与"预算"的含义相反；D 无关。本节代码没有实现重试预算（见 Q12）。

### Q9 — 参考答案

实测结果：

```text
chosen_model = "evil/free-model"
attempts     = ["evil/free-model"]
input_tokens = 1000,  output_tokens = 1333
cost_usd     = 0.0
```

同样的消息走 `smart`（`openai/gpt-4o`）：`(1000 × 5 + 1333 × 15) / 10⁶ = $0.024995`。

问题：`ROUTES.get(alias, [alias])` 把**任意未知别名当作具体模型名**放行，`PRICES.get(model, (0, 0))` 又把**未知模型的价格当 0**。两者叠加：

- 成本追踪与团队预算可以被一个拼错或伪造的模型名绕过（花了钱，账上却是 $0）；
- 单元素的 fallback chain 违反了技能文件的硬拒绝项"Any fallback chain with only one provider"；
- 调用方可以直达网关没有批准过的模型，别名层的治理形同虚设。

改法（fail closed）：

```python
def resolve_chain(alias: str) -> list[str]:
    chain = ROUTES.get(alias)
    if chain is None:
        raise ValueError(f"unknown model alias {alias!r}")
    return chain

def price_of(model: str) -> tuple[float, float]:
    try:
        return PRICES[model]
    except KeyError:
        raise RuntimeError(f"no price configured for {model}; refusing to route") from None
```

并在启动时校验：`ROUTES` 中出现的每个模型都必须在 `PRICES` 中有价格。

### Q10 — 参考答案

1. 实测：`content=None` 时 `pat.search(None)` 抛 `TypeError: expected string or bytes-like object, got 'NoneType'`；`content` 为列表时同样抛 `TypeError`（`got 'list'`）。在 OpenAI 格式中，带 `tool_calls` 的 assistant 消息 `content` 经常为 `null`，多模态消息的 `content` 是 part 列表——这两种都是 tool-calling 对话的常见形状，网关会直接崩溃。
2. 实测转发内容为 `[{'role': 'assistant', 'content': ''}, {'role': 'tool', 'content': '42'}]`：`tool_calls` 和 `tool_call_id` 被**丢弃**了。供应商无法把工具结果对应回之前的调用，通常会直接报错（tool 消息缺少 id），或模型看不到自己发起过工具调用——function calling 的多轮协议被破坏。
3. 改写：保留所有字段，只对文本内容做脱敏，并按内容类型分支处理：

```python
def redact_message(msg: dict) -> tuple[dict, bool]:
    out = dict(msg)                      # 浅拷贝，保留 tool_calls / tool_call_id / name 等
    content = msg.get("content")
    hit = False
    if isinstance(content, str):
        out["content"], hit = redact_pii(content)
    elif isinstance(content, list):      # 多模态 part 列表
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text, h = redact_pii(part.get("text", ""))
                parts.append({**part, "text": text})
                hit = hit or h
            else:
                parts.append(part)
        out["content"] = parts
    # content 为 None：原样保留
    # 工具调用参数里也可能有 PII：对 tool_calls[*].function.arguments 同样处理（此处从略）
    return out, hit
```

要点：网关是"透明代理"，除了明确要改写的字段，其余必须原样透传；脱敏也要覆盖工具调用参数和工具结果。

### Q11 — 参考答案

```python
import hashlib, json

CACHE: dict[str, Invocation] = {}

def cache_key(alias: str, messages: list[dict], params: dict | None = None) -> str:
    blob = json.dumps({"alias": alias, "messages": messages, "params": params or {}},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()

def cached_route(alias, messages, params=None):
    redacted = [{**m, "content": redact_pii(m["content"])[0]} for m in messages]
    key = cache_key(alias, redacted, params)
    if key in CACHE:
        hit = CACHE[key]
        inv = Invocation(alias=alias, chosen_model=hit.chosen_model, response=hit.response,
                         redacted=hit.redacted)          # tokens 与 cost 保持默认 0
        inv.attempts.append("cache")
        return inv
    inv = route(alias, messages)
    if inv.error is None:                                 # 失败不缓存
        CACHE[key] = inv
    return inv
```

已实际运行：`"explain MCP in one paragraph please"` 长 35 字符 → 输入 8、输出 20 token → 单次 `(8 × 5 + 20 × 15) / 10⁶ = $0.00034`。10 次调用：有缓存 **$0.00034**（只有第一次真正调用），无缓存 **$0.0034**，节省 90%。

设计要点：
- 键里要有 alias（不同模型的答案不能混用）、完整对话（不是只有最后一条）、采样参数（temperature 不同结果不同）；
- 用**脱敏后**的内容算键，否则缓存里会以 PII 为索引；
- 多租户场景键里还要加租户 id，避免跨租户泄露；
- temperature > 0 的请求是否缓存是产品决策：缓存会让"随机"回答变成确定的。

### Q12 — 参考答案

1. 已实测：`TimeoutError` 不是 `RuntimeError` 的子类，会直接从 `route()` 抛出，后续供应商一个都不会尝试，请求失败——而超时恰恰是最需要 fallback 的情况之一。反过来，400（请求格式错误、超长、内容违规）是**调用方**的问题，换供应商通常同样失败，还会白白消耗配额；讲义写的是"on 5xx"才 fallback。实践中通常把 429、500、502、503、504 和超时、连接错误视为可重试，4xx（除 429）不重试。

2. 参考实现（已运行验证）：

```python
class ProviderError(Exception):
    def __init__(self, status, msg=""):
        super().__init__(msg)
        self.status = status

RETRYABLE = {429, 500, 502, 503, 504}

class Breaker:
    def __init__(self, threshold=3, cooldown=30.0):
        self.threshold, self.cooldown = threshold, cooldown
        self.fails, self.open_until = {}, {}
    def allow(self, model, now):
        return now >= self.open_until.get(model, 0.0)
    def record(self, model, ok, now):
        if ok:
            self.fails[model] = 0
            return
        self.fails[model] = self.fails.get(model, 0) + 1
        if self.fails[model] >= self.threshold:
            self.open_until[model] = now + self.cooldown

def route2(alias, messages, breaker, max_attempts=2, now=None):
    now = time.monotonic() if now is None else now
    chain = ROUTES.get(alias)
    if chain is None:
        raise ValueError(f"unknown alias {alias!r}")
    attempts, errors = [], []
    for model in chain:
        if len(attempts) >= max_attempts:            # 重试预算
            break
        if not breaker.allow(model, now):            # 熔断中：跳过，不计入尝试
            errors.append((model, "circuit open"))
            continue
        attempts.append(model)
        try:
            resp = call_provider(model, messages)
        except ProviderError as e:
            breaker.record(model, False, now)
            errors.append((model, e.status))
            if e.status not in RETRYABLE:            # 4xx：不换供应商
                break
            continue
        except TimeoutError:
            breaker.record(model, False, now)
            errors.append((model, "timeout"))
            continue
        breaker.record(model, True, now)
        return model, attempts, errors
    return None, attempts, errors
```

让 `openai/gpt-4o` 持续返回 503，连续 5 个请求（时间相隔 1 秒）：前 3 个请求各调用 2 次（gpt-4o 失败 + sonnet 成功），第 3 次失败后熔断打开；第 4、5 个请求直接跳过 gpt-4o，只调用 sonnet 1 次。总计 `3 × 2 + 2 × 1 = 8` 次供应商调用（实测 8），没有熔断时是 10 次。`errors` 也记录了每次失败的原因——原代码 `except RuntimeError as e: continue` 把原因丢掉了。

3. 实测：`demo()` 结束后 `OUTAGE == {'openai/gpt-4o-mini', 'anthropic/claude-haiku'}`——场景 4 没有 `OUTAGE.clear()`。如果同一进程中再调用 `route("fast", ...)`（例如在测试里先 import 再跑 demo），会莫名其妙地全部失败。模块级可变全局状态让函数行为依赖调用历史，应当把故障注入、熔断状态等放进显式传入的对象中（如 `Gateway` 实例），每个测试新建一个。

### Q13 — 参考回答要点

- **定义**：位于应用与多个 LLM 供应商之间的一层代理，对外提供统一 API，对内转发到不同供应商。
- **解决的问题**（讲义五个场景）：成本（按任务选模型）、故障转移（某供应商故障自动切换，无需重新部署）、延迟（按 SLA 选模型）、合规（按区域路由）、实验（A/B 分桶）。
- **附加能力**：模型别名、fallback chain、缓存、guardrail（PII 脱敏、内容策略、输出过滤）、按 key 限额与预算、成本追踪、可观测性。
- **OpenAI 兼容接口的作用**：讲义 "Everyone speaks OpenAI-shape"——应用和现成 SDK 无需改动即可接入，网关负责把 OpenAI schema 翻译成各供应商的格式（消息、工具调用、流式事件）。
- 加分点：翻译层是最容易出 bug 的地方——工具调用格式、system prompt 位置、流式事件、stop reason 在各家并不相同（本节 Q10 就是一个"翻译时丢字段"的例子）。

### Q14 — 参考回答要点

- **错误分类**：429 / 5xx / 超时 / 连接错误可重试；4xx（除 429）不重试也不换供应商；内容策略拒绝要区分"该供应商的策略"还是"请求本身违规"。
- **同供应商重试 vs 换供应商**：瞬时错误（单次 502）先在同供应商带抖动的指数退避重试 1 次；持续故障（熔断打开、区域性故障）直接换供应商。429 要尊重 `Retry-After`。
- **避免重试风暴**：总重试预算（每请求最多 N 次、全局重试比例上限）、熔断器、退避加抖动、超时预算（整个请求的截止时间向下传递）。
- **"非故障"风险**：
  - 行为差异：不同模型对同一 prompt 和工具 schema 的遵循程度不同，tool calling 格式、structured output 支持可能不一致；
  - 成本差异：备用模型可能更贵（本节 sonnet 输入单价低于 gpt-4o，但未必总是如此）；
  - 合规：备用供应商/区域可能不满足数据驻留要求——技能文件硬拒绝"sends prompts to a region violating the compliance constraint"；
  - 上下文窗口：备用模型窗口更小会直接失败。
- **观测**：技能文件建议部署后首先告警的指标是 fallback 使用率。

### Q15 — 参考回答要点

- **粒度**：
  - 按请求：每个请求前检查剩余额度，简单但并发下会超支；
  - 按时间窗口：如每分钟/每小时的消费速率限制，平滑但对月度上限不精确；
  - 常见组合：月度硬上限 + 短窗口速率限制。
- **预扣（reservation）**：请求开始时按"输入 token × 输入单价 + max_tokens × 输出单价"预扣最大可能成本，完成后按实际 usage 结算、退回差额；没有 `max_tokens` 的请求由网关强制设置上限。
- **并发安全**：额度扣减用原子操作（如 Redis `INCRBYFLOAT` + Lua 脚本、数据库条件更新），多副本网关共享同一个计数器。
- **到达上限后的行为**：拒绝（返回明确错误码）、降级到便宜别名、或仅允许关键流量；提前在 80%/90% 时告警。
- **计价可信**：价格表集中维护、未知模型拒绝路由（见 Q9），缓存命中计 0 成本但要单独统计。
- 讲义："Per-key budgets prevent one team from consuming the shared quota."

### Q16 — 参考回答要点

- **别名**：`eu_chat_fast`（客服，低延迟）、`batch_summarize_cheap`（离线摘要）。
- **fallback chain**：
  - `eu_chat_fast`：只包含部署在欧盟区域的模型端点，至少两个不同供应商（技能文件：单一供应商的链违背初衷）；按延迟感知排序；整体超时短（如首 token 2 秒内）。
  - `batch_summarize_cheap`：成本感知，优先最便宜的小模型，失败再换另一个便宜模型；允许更长超时、可排队、可用批处理接口。
- **guardrail**：客服流量直接处理用户输入，必须有输入 PII 脱敏与输出过滤（技能文件："Any guardrail-less setup if the workload processes user input directly"）；批量任务视数据来源决定。
- **缓存**：客服场景的 FAQ 类问题可用精确/语义缓存（需租户隔离）；批量任务的重复文档用精确缓存。
- **预算与告警**：两个别名分属不同 key / 团队，各自预算；告警 fallback 使用率、p95 延迟、单位成本。
- **网关选型**（按讲义）：需要开箱即用的 guardrail 与合规 → Portkey；有 SRE、要求数据主权和完全自托管 → LiteLLM；OpenRouter 作为托管额度计费的方案，需要额外确认其路由的区域能否满足欧盟数据驻留要求。

### Q17 — 参考回答要点

- **为什么不敢开**：
  - 正确性：近似 prompt 不等于同一个问题（"转账给张三 100 元"与"转账给张三 1000 元"的 embedding 可能非常接近），阈值稍松就会返回错误答案；
  - agent 上下文依赖：同一句"继续"在不同对话历史下含义完全不同，只对最后一条消息做缓存键会出错；
  - 工具调用与副作用：缓存一个"决定调用某工具"的回复，会让 agent 在状态已改变的情况下重复执行旧决定；
  - 时效性：涉及实时数据的回答会过期；
  - 隐私与多租户：一个租户的回答被另一个租户命中就是数据泄露；
  - 随机性：temperature > 0 的请求被缓存后变成确定输出。
- **何时安全**：确定性任务（temperature = 0）、无副作用、无个性化、无时效性的请求，如 FAQ、固定文档摘要、embedding 计算；键包含完整上下文 + 模型 + 参数 + 租户；设置 TTL；对语义缓存设严格阈值并抽样评估误命中率。
- 加分点：精确缓存（SHA-256）几乎没有正确性风险，可以先上；语义缓存要有离线评估集，度量"误命中率"而不只是"命中率"。

---

## 六、关联知识点

### 前置知识
- [阶段 13 · 02 深入理解 Function Calling：OpenAI、Anthropic、Gemini](../../02-function-calling-deep-dive/docs/zh.md)：网关要在各家 function calling 格式之间翻译。
- [阶段 13 · 17 Stateless MCP 网关与注册表准入](../../17-mcp-gateways-and-registries/docs/zh.md)：讲义提到 MCP 网关与 LLM 路由网关有时会合并成一个服务。
- [阶段 13 · 11 MCP 模型输入：Sampling 迁移与无状态 MRTR](../../11-mcp-sampling/docs/zh.md)：sampling 请求的 `modelPreferences` 也可以经路由网关翻译到具体后端。
- [阶段 11 · 11 缓存与成本](../../../11-llm-engineering/11-caching-cost/docs/zh.md)：缓存与成本控制的基础。

### 本节被哪些后续内容用到
- [阶段 17 · 19 AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost](../../../17-infrastructure-and-production/19-ai-gateways/docs/zh.md)：生产视角下的网关对比。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../../17-infrastructure-and-production/16-model-routing/docs/zh.md)：成本感知与任务感知路由的深入。
- [阶段 17 · 14 Prompt 缓存与语义缓存的经济性](../../../17-infrastructure-and-production/14-prompt-semantic-caching/docs/zh.md)：语义缓存的收益与风险。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../../17-infrastructure-and-production/27-finops-llms/docs/zh.md)：按团队的成本归因与预算。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：agent 层面的预算控制。

### 延伸关键词
`LiteLLM` · `OpenRouter` · `Portkey` · `OpenAI-compatible proxy` · `model alias` · `fallback chain` · `retry budget` · `circuit breaker` · `exponential backoff + jitter` · `semantic cache` · `PII redaction` · `per-key budget` · `cost attribution` · `data residency`
