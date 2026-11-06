# 测验 · AI 网关：LiteLLM、Portkey、Kong AI Gateway、Bifrost（AI Gateways — LiteLLM, Portkey, Kong AI Gateway, Bifrost）

> **阶段 17 · 基础设施与生产 · 第 19 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py)（另有 TypeScript 版 [code/main.ts](../code/main.ts)，本测验以 Python 版为准） ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 网关的位置 | 位于应用与各模型提供商之间的一个进程，对外通常暴露一个 OpenAI 兼容 API，对内扇出到 OpenAI、Anthropic、自托管模型等 |
| 2 | 核心功能清单 | 讲义标题写"六个"，实际列了七项：provider routing、fallback、retries、rate limits、secret references、observability、guardrails |
| 3 | fallback 的可用性算术 | 若各提供商故障独立，链式 fallback 的失败率是各失败率的乘积：3% × 2% → 成功率 99.94%；再加 5% 的第三家 → 99.997% |
| 4 | LiteLLM | MIT 开源、Python、100+ 提供商；在 Kong 的基准里约 2000 RPS 崩溃（8 GB 内存、级联失败）；适合 Python 应用、< 500 RPS、开发/原型 |
| 5 | Portkey | 定位"控制面"：guardrails、PII 脱敏、越狱检测、审计；讲义：2026 年 3 月起 Apache 2.0 开源，额外时延 20–40 ms，生产档 $49/月 |
| 6 | Kong AI Gateway | 基于成熟的 Kong Gateway（Lua + OpenResty）；Kong 自己的基准：比 Portkey 快 228%、比 LiteLLM 快 859%；$100/模型/月，Plus 档最多 5 个 |
| 7 | Bifrost 与边缘网关 | Bifrost（Maxim AI）：可配置退避的自动重试，OpenAI 429 时回退到 Anthropic；Cloudflare / Vercel：托管、零运维、1–3 ms 开销，功能较基础 |
| 8 | 时延预算 | 网关开销直接加到 TTFT 上：Kong 3–8 ms、Cloudflare/Vercel 1–3 ms、LiteLLM 5–15 ms、Portkey 20–40 ms；TTFT P99 < 100 ms 只能选 Kong 或边缘网关 |
| 9 | 自托管 vs 托管 | 数据驻留（data residency）是决定因素：医疗、金融默认自托管；消费级产品默认托管；也可混合 |
| 10 | 限流语义 | token bucket 适合中等规模；多租户需要 sliding window + 突发额度 + 按租户分级；讲义：LiteLLM 用 token bucket、Kong 用 sliding window、Portkey 用分级 |

### 核心技能（能动手做到）

- [ ] 说出网关七项核心功能，并解释为什么不该在每个业务服务里各自实现
- [ ] 在"故障独立"假设下手算多级 fallback 的成功率与期望时延，并能说出这个假设何时不成立
- [ ] 根据 RPS、时延预算、合规（是否必须自托管）、guardrails 需求，在 LiteLLM / Portkey / Kong / Cloudflare 之间做选型
- [ ] 读懂 `simulate_fallback()`，指出它的"retries"其实不是重试，并补上带指数退避的同提供商重试
- [ ] 写出 token bucket 与 sliding window 两种限流器，并说明多租户场景下为什么倾向后者
- [ ] 识别厂商基准（Kong 自测）与独立结论的区别

---

## 二、基础自测（选择题）

**Q1.** 讲义对 AI 网关核心职责的描述是：

- A. 一个只负责缓存模型输出的 CDN
- B. 位于应用与模型提供商之间的进程，在一个 API 背后统一处理路由、fallback、重试、限流、密钥引用、可观测性和 guardrails
- C. 专门用来做模型微调的平台
- D. 一个把多个模型权重合并成一个的工具

**Q2.** 主提供商错误率 3%、备用提供商错误率 2%，假设二者故障相互独立。"主 → 备"两级 fallback 的成功率是：

- A. 95%
- B. 99.4%
- C. 99.997%
- D. 99.94%

**Q3.** 关于"Kong 比 Portkey 快 228%、比 LiteLLM 快 859%"这组数字，最准确的理解是：

- A. 来自 Kong 自己发布的基准（在相同 12 CPU 条件下），属于厂商基准，选型时应在自己的负载上复测
- B. 来自独立第三方审计机构的认证结果
- C. 说明 LiteLLM 在任何 RPS 下都不可用
- D. 指的是模型推理速度，而不是网关本身的开销

**Q4.** 你的 SLA 是 TTFT P99 < 100 ms。按讲义的时延预算，哪组网关能留在预算内？

- A. 只有 Portkey
- B. LiteLLM 与 Portkey
- C. Kong（约 3–8 ms）或 Cloudflare/Vercel 边缘网关（约 1–3 ms）
- D. 任意网关都可以，网关开销可以忽略

**Q5.** 运行 `code/main.py`，四个网关的 `mean_latency` 分别是 193、213、188、185 ms，而 success、retries、fallbacks 完全相同。原因是：

- A. 每个网关都用同一个种子 `seed=7`，错误注入序列完全相同，网关之间唯一的差别是一个固定的开销常数（10 / 30 / 5 / 2 ms）
- B. 不同网关选择了不同的提供商顺序
- C. Portkey 的 guardrails 拦截了更多请求
- D. Kong 的限流让一部分请求被拒绝

**Q6.** 在 `code/main.py` 的输出里，`retries` 与 `fallbacks` 两列都是 34。这说明：

- A. 每个请求都被同一提供商重试了 34 次
- B. 代码实现了指数退避，34 是退避次数
- C. 代码里没有"对同一提供商重试"，`retries` 实际统计的是"某个提供商调用失败"的次数，每次失败都直接转到下一家
- D. 34 个请求最终失败

**Q7.** 讲义认为决定"自托管还是托管网关"的强制因素（forcing function）是：

- A. 团队偏好的编程语言
- B. 数据驻留（data residency）要求
- C. 提供商数量
- D. 网关的 GitHub star 数

**Q8.** 一个多租户 SaaS 需要按免费 / 试用 / 付费三档做公平限流，并允许付费用户短时突发。按讲义，更合适的方案是：

- A. 全局一个 token bucket，所有租户共享
- B. 不做限流，交给模型提供商的 429
- C. 每个请求固定 sleep 100 ms
- D. sliding window + 突发额度 + 按租户分级

---

## 三、动手 / 代码题

**Q9.** 代码的提供商链与错误注入：

```python
PROVIDERS = [
    Provider("OpenAI",       180, 0.03, 0),
    Provider("Anthropic",    220, 0.02, 0),
    Provider("Self-hosted",  100, 0.05, 0),
]

def call_provider(p: Provider, rng: random.Random) -> tuple[bool, float]:
    if rng.random() < p.error_rate:
        return False, p.base_latency_ms * 0.3  # half-done before error
    return True, p.base_latency_ms
```

1. 写出（不含网关开销的）期望时延公式并算出数值，与运行结果（Kong 188 ms − 5 ms 开销）对比。
2. 三级链的理论成功率是多少？为什么 1000 次模拟里看到的是 100.0%？
3. 讲义练习 1：若三家提供商错误率都是 5%，三级链的成功率、"至少发生一次 fallback"的比例、"走到第三家"的比例分别是多少？

**Q10.** 代码只有"失败就换下一家"，没有讲义所说的"Retries — exponential backoff, bounded attempts"。请写一个函数 `call_with_retry(p, rng, max_attempts=3, base_ms=50)`：对同一提供商最多尝试 `max_attempts` 次，第 k 次失败后等待 `base_ms × 2^(k-1)`（加随机抖动），返回 `(ok, 总耗时 ms, 尝试次数)`；并说明什么类型的错误应该重试、什么类型应该立即 fallback。

**Q11.** 仔细阅读 `main.py`，找出至少 5 处问题（死代码、注释与代码不符、统计口径、输出格式、建模假设）。

**Q12.** 讲义练习 5 要求为多租户设计限流。请用标准库实现一个 `TokenBucket(rate_per_ms, burst)` 和一个 `SlidingWindowLog(limit, window_ms)`，各自提供 `allow(now_ms) -> bool`，并用一组时间戳说明二者行为的差别。

---

## 四、面试高频题

**Q13.**（基础必考）为什么需要 AI 网关？如果不用网关，直接在每个服务里调用各家 SDK，会有什么问题？

**Q14.**（原理深挖）fallback 链的可用性真的是"各失败率相乘"吗？什么情况下这个计算会严重高估可用性？fallback 又会带来哪些新问题？

**Q15.**（工程实践）你的团队目前用 LiteLLM，流量 300 RPS，预计 6 个月后到 3000 RPS。你会怎么规划？

**Q16.**（场景设计）一家医疗客户要求：自托管、PII 脱敏、完整审计、TTFT P99 < 300 ms、约 800 RPS。请给出网关方案。

**Q17.**（追问型）"Portkey 每个请求多 20–40 ms，所以它不能用于生产"——你同意吗？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："A gateway sits between your apps and model providers. Core features are provider routing, fallback, retries, rate limiting, secret references, observability, guardrails." 它通常对外暴露一个 OpenAI 兼容 API。A 是缓存层（阶段 17 · 14）；C、D 与网关无关。

### Q2 — 答案：D

两级都失败的概率 = `0.03 × 0.02 = 0.0006`，成功率 = `1 − 0.0006 = 99.94%`，与代码末尾的 Notes 一致。A 是把两个错误率相加后取补；B 少了一个 9；C 是三级链（再乘 0.05）的结果。前提是**故障独立**——见 Q14。

### Q3 — 答案：A

讲义："Kong's own benchmark on 12-CPU equivalent: 228% faster than Portkey, 859% faster than LiteLLM"，"Kong AI Gateway Benchmark" 链接到 Kong 自己的博客。这是厂商基准，结论可以作为参考，但测试负载、配置与你的场景未必一致。B 错：不是独立审计；C 过度推广：讲义推荐 LiteLLM 用于 < 500 RPS；D 错：比较的是网关本身的吞吐/开销。

### Q4 — 答案：C

讲义："For TTFT P99 < 100 ms SLA, Kong or Cloudflare. For P99 < 500 ms, any." Portkey 20–40 ms 会吃掉预算的 20–40%，skill 文件把"TTFT P99 < 100 ms 用 Portkey"列为硬拒绝；LiteLLM 5–15 ms 在讲义中也不在推荐之列。D 错：网关开销直接叠加在 TTFT 上。

### Q5 — 答案：A

`simulate_fallback(gw)` 的默认 `seed=7`，四次调用产生完全相同的随机序列；每个请求的提供商路径完全一样，只是起点加了 `GATEWAY_OVERHEAD[gateway]`。所以 `mean_latency = 约 183 ms + 开销`：193 = 183 + 10，213 = 183 + 30，188 = 183 + 5，185 = 183 + 2。B 错：`PROVIDERS` 顺序固定；C、D 错：代码没有 guardrails 和限流。这也说明此模拟**不能**区分不同网关在可靠性上的差别。

### Q6 — 答案：C

```python
        for attempt, p in enumerate(PROVIDERS):
            ok, ms = call_provider(p, rng)
            req_latency += ms
            if attempt > 0:
                fallback_hits += 1
            if ok:
                ...
                break
            retries += 1
```

每次失败 `retries += 1`，然后循环进入下一家提供商，此时 `attempt > 0`，`fallback_hits += 1`。因此只要失败不发生在最后一家，两者总是相等。1000 次中：967 次首家成功，32 次第一家失败、第二家成功，1 次前两家都失败、第三家成功；`32 + 2 = 34`。A、B 与代码不符；D 错：成功率 100%，没有请求最终失败。

### Q7 — 答案：B

讲义："Data residency is the forcing function. Healthcare and finance default self-host ... Consumer products default managed." 其余选项都不是讲义提出的决策依据。

### Q8 — 答案：D

讲义："Simple token-bucket works up to moderate scale. Multi-tenant requires sliding-window + burst allowance + per-tenant tiering." A 的全局共享桶会让一个吵闹租户耗尽所有人的额度；B 把限流责任推给提供商，既不公平也无法分级；C 不是限流，只是人为增加时延。

### Q9 — 参考答案

1. 期望时延（不含网关开销）：

   `E = 0.97 × 180 + 0.03 × [54 + 0.98 × 220 + 0.02 × (66 + 0.95 × 100 + 0.05 × 30)]`

   其中 54、66、30 是三家失败时的"半途时延"（`× 0.3`）。计算结果约 **182.79 ms**（已用 Python 计算）。运行结果：Kong 188 ms − 5 ms = 183 ms，与理论值吻合。

2. 理论成功率 = `1 − 0.03 × 0.02 × 0.05 = 1 − 0.00003 = 99.997%`，即每 10 万个请求约 3 个失败。1000 次模拟中期望失败数只有 0.03 次，看到 0 次失败、显示为 100.0% 很正常。把 `n` 调到 100,000 时，实际运行得到 success = 99.998%（2 次失败）。小样本无法验证"几个 9"的可用性，这也是生产中要长期统计 SLO 的原因。

3. 三家都是 5%：
   - 成功率 = `1 − 0.05³ = 99.9875%`；
   - 至少一次 fallback 的比例 = 第一家失败的概率 = **5%**；
   - 走到第三家的比例 = `0.05² = 0.25%`。

### Q10 — 参考答案

```python
import random

def call_with_retry(p, rng: random.Random, max_attempts: int = 3, base_ms: float = 50):
    total = 0.0
    for k in range(1, max_attempts + 1):
        ok, ms = call_provider(p, rng)
        total += ms
        if ok:
            return True, total, k
        if k < max_attempts:
            backoff = base_ms * 2 ** (k - 1)
            total += backoff * rng.uniform(0.5, 1.5)    # 抖动，避免重试风暴同步
    return False, total, max_attempts
```

在 `simulate_fallback` 中把 `call_provider(p, rng)` 换成 `call_with_retry(p, rng)`，就得到"每家先重试、再 fallback"的两层策略。

应该区分错误类型：

| 错误 | 处理 |
|------|------|
| 429（限流） | 对同一家退避重试，若带 `Retry-After` 就按它等；持续 429 再 fallback（Bifrost 的"OpenAI 429 → Anthropic"） |
| 5xx / 连接超时 | 有限次重试，然后 fallback |
| 4xx 参数错误、认证失败、内容过长 | **不重试**、不 fallback（换一家也会错），直接返回给调用方 |
| 内容安全拒绝 / 质量失败 | 视业务决定是否 fallback 到另一个模型 |

还要设置**总时延预算**：重试 + fallback 的累计时间超过 TTFT 预算时应直接失败，而不是继续尝试。

### Q11 — 参考答案

1. **`retries` 名不副实**：没有对同一提供商重试，`retries` 与 `fallbacks` 统计的几乎是同一件事（见 Q6）。讲义的 "Retries — exponential backoff" 没有实现。
2. **注释与代码不符**：`# half-done before error`，但乘数是 `0.3` 而不是 `0.5`。
3. **死代码**：`Provider.overhead_ms` 字段全部为 0 且从未使用；`from dataclasses import field` 中的 `field` 未使用；`done = True` 赋值后从未读取。
4. **所有网关用同一种子**：网关之间只差一个常数开销，模拟无法体现讲义所说的可靠性差别（例如 LiteLLM 在 2000 RPS 的级联失败）；也没有负载、RPS 或内存的概念。
5. **输出格式错位**：表头写 `Success  mean latency  retries  fallbacks`，每行又带 `success=`、`mean_latency=` 等标签，表头与列不对齐。
6. **只报告均值**：讲义强调 TTFT P99，代码只算平均时延；fallback 请求的尾部时延（例如 54 + 220 = 274 ms）被平均值掩盖。
7. **故障独立假设**：每次调用独立按概率失败，没有"提供商整段时间宕机"或"429 突发"的相关性。
8. **fallback 顺序未考虑时延**：自托管最快（100 ms）却排在最后；讲义练习 1 指定的顺序是 OpenAI → Anthropic → self-hosted，可以讨论是否应按"成本/时延/质量"重排。
9. 讲义 "Use It" 说报告 "retry rate, and fallback hit rate"，代码输出的是计数而非比例。

### Q12 — 参考答案

```python
from collections import deque

class TokenBucket:
    def __init__(self, rate_per_ms: float, burst: int):
        self.rate, self.capacity = rate_per_ms, burst
        self.tokens, self.last = float(burst), 0
    def allow(self, now_ms: int, cost: float = 1.0) -> bool:
        self.tokens = min(self.capacity, self.tokens + (now_ms - self.last) * self.rate)
        self.last = now_ms
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

class SlidingWindowLog:
    def __init__(self, limit: int, window_ms: int):
        self.limit, self.window, self.events = limit, window_ms, deque()
    def allow(self, now_ms: int) -> bool:
        while self.events and self.events[0] <= now_ms - self.window:
            self.events.popleft()
        if len(self.events) < self.limit:
            self.events.append(now_ms)
            return True
        return False
```

实际运行验证：

- `TokenBucket(0.002, 5)`（每秒补 2 个、最多攒 5 个），时间戳 `[0,0,0,0,0,0,500,1000,1000]` → `[T,T,T,T,T,F,T,T,F]`：开头可以一次性突发 5 个，之后按速率放行。
- `SlidingWindowLog(3, 1000)`（任意 1 秒内最多 3 个），时间戳 `[0,100,200,300,1000,1050,1100,1200]` → `[T,T,T,F,T,F,T,T]`：严格保证"任意 1000 ms 窗口不超过 3 个"。

区别：token bucket 允许攒额度后突发，实现 O(1)；sliding window 对任意窗口精确，更公平，但要保存事件（或用"滑动窗口计数器"近似）。多租户时为每个 `(tenant, tier)` 维护一个限流器，按档位设置 `limit` 与突发额度；分布式部署要把状态放在 Redis 等共享存储里。还应按 **token 数**（而不仅是请求数）计费式限流，因为 LLM 请求的成本差异很大。

注意：时间用整数毫秒。若用浮点秒，`1.2 - 1.0` 会得到 `0.19999999999999996`，窗口边界判断会出错。

### Q13 — 参考回答要点

- **没有网关时的问题**：每个服务都耦合每家 SDK（错误模型、限流语义、认证方式各不相同）；密钥散落在各服务配置里；fallback、重试逻辑重复实现且不一致；没有统一的成本归因与可观测性；无法统一执行 PII 脱敏与审计；切换提供商要改所有服务。
- **网关的价值**：一个（通常 OpenAI 兼容的）API；集中路由、fallback、重试、按租户/密钥/模型限流；运行时从 vault 拉取密钥；统一 OTel GenAI 追踪与成本归因（阶段 17 · 13）；guardrails。
- **代价**：多一跳时延（1–40 ms）；网关本身成为关键依赖，需要高可用；有扩展上限（LiteLLM 约 2000 RPS）。
- 加分点：说明网关、可观测性、模型路由在生产中是"同一层"（讲义：17 · 13 + 16 + 19），可以一个工具覆盖或分工组合。

### Q14 — 参考回答要点

- **相乘的前提是独立**。以下情况会严重高估可用性：
  - 同一区域的网络或 DNS 故障，所有出站请求一起失败；
  - 网关自身故障（它是所有 fallback 的共同路径）；
  - 备用提供商在主提供商宕机时被大量流量涌入，触发 429（相关性故障）；
  - 多家提供商依赖同一云厂商或同一上游。
- **fallback 带来的新问题**：
  - 尾部时延：失败的半途时间 + 备用提供商时延（代码中 54 + 220 = 274 ms，远高于均值）；
  - 输出质量与格式不一致（不同模型的风格、JSON 遵循度、tool calling 行为不同）；
  - 成本变化（备用模型可能更贵）；
  - 提示词需要按模型适配；
  - 重试风暴：没有退避和抖动时会放大故障。
- **工程做法**：断路器（连续失败后暂时跳过该提供商）、带抖动的指数退避、总时延预算、对备用路径做定期合成探测、按错误类型区分是否 fallback。
- 加分点：能用"99.94% 还是 99.997%"说明"多一级 fallback 的边际收益"，并指出 1000 次模拟无法验证这种级别的可用性。

### Q15 — 参考回答要点

- **现状判断**：300 RPS 在 LiteLLM 的舒适区（讲义：< 500 RPS）；3000 RPS 超过了 Kong 基准中约 2000 RPS 的崩溃点。skill 文件："scale ambiguity is large ... require the migration plan before committing to LiteLLM"。
- **规划**：
  1. 现在就在自己的流量形态下压测 LiteLLM，找到真实的拐点（不要只信厂商基准）；
  2. 选定目标网关（> 1000 RPS 讲义推荐 Kong；需要 guardrails 可以 Kong + Portkey 分工）；
  3. 保持 OpenAI 兼容接口，让业务代码不感知网关替换；
  4. 灰度迁移：1% 流量走新网关，比较时延 P99、错误率、成本归因是否一致（阶段 17 · 20 的 canary 方法），逐步放量；
  5. 准备快速回滚开关。
- **期间的缓冲**：LiteLLM 可以水平扩展多个实例并在前面加负载均衡，但讲义提到内存约 8 GB 与级联失败，需要设置保护性限流。
- 常见误区：等到出事故再迁移；迁移时一并更换提供商和提示词，导致问题无法定位。

### Q16 — 参考回答要点

- **硬约束**：自托管 → 排除 Cloudflare/Vercel（skill 文件：受监管的本地部署客户拒绝 Cloudflare）。
- **候选**：Portkey OSS（guardrails、PII 脱敏、越狱检测、审计内建）或 Kong（规模与时延优势，guardrails 需插件或外挂）。
- **时延预算**：TTFT P99 < 300 ms，Portkey 20–40 ms 可接受，但要扣掉模型本身的 TTFT；800 RPS 超过 LiteLLM 舒适区，不选 LiteLLM。
- **推荐方案之一**：Portkey OSS 作为控制面（PII 脱敏、审计日志写入不可篡改存储），若后续 RPS 继续上升，再在前面加 Kong 负责大流量路由与限流——讲义提到 2026 年常见做法是"Portkey（guardrails）+ Kong（规模）"分工。
- **其他配置**：密钥从 vault 运行时拉取；fallback 链只包含满足合规的提供商（可能只有自托管 + 签了 BAA 的云端模型）；审计日志包含租户、模型、提示词哈希、脱敏结果；OTel 追踪接入（阶段 17 · 13）；按租户限流。
- 加分点：指出 PII 脱敏（正则 + NER）本身会增加时延，需要计入预算；审计与合规框架见阶段 17 · 25、26。

### Q17 — 参考回答要点

- **不同意这种绝对化的说法**，要看 SLA 与功能需求：
  - TTFT P99 < 100 ms 的场景：确实不合适（skill 硬拒绝）；
  - TTFT P99 < 500 ms 的常见对话场景：讲义 "For P99 < 500 ms, any"，20–40 ms 可以接受；
  - 受监管行业：Portkey 内建的 guardrails、PII 脱敏、审计可能是刚需，自己实现同样会有时延。
- **量化**：模型 TTFT 往往是几百毫秒，20–40 ms 的占比要放在总预算里看；同时要测 P99 而非均值。
- **折中**：把 guardrails 放在需要的租户/路由上，其余流量走更轻的路径；或 Kong 做数据面、Portkey 做部分控制面。
- 加分点：指出讲义里的开销数字也需要在自己的部署中复测。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 01 托管 LLM 平台：Bedrock、Vertex AI、Azure OpenAI](../../01-managed-llm-platforms/docs/zh.md)：网关背后对接的各类提供商。
- [阶段 17 · 16 将模型路由作为降低成本的基本手段](../../16-model-routing/docs/zh.md)：网关里的"provider routing"与成本路由是一回事。
- [阶段 13 · 21 LLM 路由层：LiteLLM、OpenRouter、Portkey](../../../13-tools-and-protocols/21-llm-routing-layer/docs/zh.md)：从工具与协议视角介绍同一批产品。
- [阶段 11 · 11 缓存、请求速率限制与成本优化](../../../11-llm-engineering/11-caching-cost/docs/zh.md)：限流与成本控制的应用层基础。

### 本节被哪些后续内容用到
- [阶段 17 · 13 LLM Observability 技术栈选型](../../13-llm-observability/docs/zh.md)：网关是 OTel GenAI 追踪和成本归因的天然采集点。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../20-shadow-canary-progressive/docs/zh.md)：在网关层做流量切分与灰度迁移。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../25-security-secrets-audit/docs/zh.md)：密钥引用、审计日志的深入内容。
- [阶段 11 · 12 Guardrails，安全及内容过滤](../../../11-llm-engineering/12-guardrails/docs/zh.md)：网关里 guardrails 的具体实现。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../27-finops-llms/docs/zh.md)：网关的按租户成本归因。

### 延伸关键词
`AI gateway` · `OpenAI-compatible API` · `fallback chain` · `exponential backoff + jitter` · `circuit breaker` · `Retry-After` · `token bucket` · `sliding window` · `per-tenant rate limit` · `PII redaction` · `audit trail` · `data residency` · `vendor benchmark`
