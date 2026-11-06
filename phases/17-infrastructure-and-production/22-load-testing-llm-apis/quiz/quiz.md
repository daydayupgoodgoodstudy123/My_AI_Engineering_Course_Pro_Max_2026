# 测验 · 对 LLM APIs 进行负载测试：为什么 k6 与 Locust 会产生误导（Load Testing LLM APIs — Why k6 and Locust Lie）

> **阶段 17 · 基础设施与生产 · 第 22 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | LLM 负载测试为什么是独立学科 | 传统压测工具不是为 streaming 响应、可变输出长度、token 级指标和 GPU 饱和设计的；只看"一个 HTTP 连接成功了没有"会漏掉用户真正感受到的逐 token 延迟 |
| 2 | GIL trap（GIL 陷阱） | Locust 在客户端用 Python 做 tokenization，与请求生成争抢 GIL；高并发时 tokenization 积压被算进 inter-token latency，**瓶颈在压测客户端而不是服务端** |
| 3 | Prompt-uniformity trap（单一 prompt 陷阱） | 循环发送同一个 prompt，前缀缓存命中率趋近 100%、请求还可能被合并，吞吐与 TTFT 看起来极好，但只测到了 token 分布上的"一个点" |
| 4 | 真实的 prompt 分布 | 用 mean + stddev 采样输入长度（LLMPerf：`--mean-input-tokens 500 --stddev-input-tokens 150`），内容/前缀也要多样；数据来源是真实流量或公开分布（ShareGPT、HumanEval） |
| 5 | 四种负载模式 | Steady-state（基线回归）、Ramp（容量拐点、预热异常）、Spike（autoscaling 延迟、队列饱和、冷启动）、Soak（内存泄漏、连接池漂移、observability 溢出） |
| 6 | 2026 工具映射 | LLMPerf 做基准、GenAI-Perf 是 NVIDIA 参考实现、LLM-Locust 修复 GIL 陷阱、guidellm 做大规模合成、k6 v2026.1.0 + k6 Operator 1.0 GA（2025 年 9 月）做 CI 门禁、Vegeta 做恒定速率网关压测 |
| 7 | 指标口径差异 | GenAI-Perf 的 ITL **不含** TTFT（从第 2 个 token 起算），LLMPerf **包含** TTFT；同一服务器两个工具给出不同 TPOT，跨工具比较前必须对齐口径 |
| 8 | CI 中的 SLA 门禁 | 每个 PR 在基线 RPS 下跑 30–50 次迭代，门禁指标 P50/P95 TTFT、5xx < 5%、TPOT 低于阈值，违反即让构建失败 |
| 9 | 本节代码的结论与局限 | 统一 prompt：500 次里 499 次命中缓存、P99 = 80 ms；"真实"分布：421 次命中、P99 = 800 ms。但代码里 concurrency 参数不起作用、prompt 长度与 TPOT 都没被使用 |

### 核心技能（能动手做到）

- [ ] 说清 GIL 陷阱与单一 prompt 陷阱各自"在哪一侧撒谎"（客户端测量 vs 服务端缓存）以及对应的修复方法
- [ ] 为一个 LLM 服务设计四种负载模式，写出每种的目标 RPS、时长和要捕获的失败模式
- [ ] 用 mean + stddev（或真实流量回放）构造 prompt 分布，并检查前缀多样性
- [ ] 读懂并手算 `simulate()` 的缓存命中数、P50/P99 与均值，指出它为何与并发无关
- [ ] 写出一个 k6 CI 门禁脚本：100 并发、5 分钟、TTFT P95 < 800 ms、错误率 < 5%
- [ ] 解释 GenAI-Perf 与 LLMPerf 报告的 TPOT 为何不同，并能反推出 TTFT

---

## 二、基础自测（选择题）

**Q1.** 用 stock Locust 压测一个流式 LLM 端点，并发从 50 加到 500 后，报告的 inter-token latency 翻了 3 倍，但服务端 vLLM 的指标几乎不变。最可能的原因是：

- A. 客户端 tokenization 在 Python GIL 下与请求生成争抢，积压时间被计入了 ITL，瓶颈在压测客户端
- B. 服务端 GPU 已经饱和，只是服务端指标采样太慢
- C. Locust 不支持 HTTP/2，导致连接被拒绝
- D. 并发越高，前缀缓存命中越多，逐 token 延迟必然变长

**Q2.** 一个压测脚本循环 10,000 次发送同一个 2,000 token 的 prompt，结果吞吐极高、TTFT 极低。讲义认为这组数字不可信，主要因为：

- A. 2,000 token 的 prompt 太长，会被服务端截断
- B. 循环次数太少，统计不显著
- C. 每次都是相同前缀，前缀缓存命中率接近 100%（还可能触发请求合并），只测到了 token 分布上的一个点
- D. 同一 prompt 会导致输出长度变长，拉低吞吐

**Q3.** 某服务稳态 30 分钟一切正常，但上线一周后每天凌晨都会 OOM 重启一次。下列哪种负载模式最有可能在上线前发现它？

- A. Ramp：15 分钟内从 0 线性升到目标 RPS
- B. Spike：突然 3–10 倍 RPS 持续 2 分钟
- C. Steady-state：恒定 RPS 30–60 分钟
- D. Soak：稳态持续 4–8 小时

**Q4.** 讲义中 Spike（突发）模式主要用来捕获哪类问题？

- A. 内存泄漏与连接池漂移
- B. autoscaling 延迟、队列饱和与冷启动影响
- C. 基线性能回归
- D. 不同工具的指标口径差异

**Q5.** 同一台服务器、同一批请求，GenAI-Perf 报告 TPOT = 6 ms，LLMPerf 报告 TPOT = 11 ms。最合理的解释是：

- A. GenAI-Perf 的 ITL 从第 2 个 token 起算、不含 TTFT；LLMPerf 把 TTFT 也平摊进了每个 token
- B. LLMPerf 使用 Rust tokenizer，计数更准确
- C. GenAI-Perf 只统计 cache 命中的请求
- D. 两个工具的并发设置一定不同，否则数字会一样

**Q6.** 运行本节 `main.py`，UNIFORM 工作负载在三种并发下 TTFT_P99 都是 80 ms。原因是：

- A. 代码把 P99 写成了 P50
- B. 统一 prompt 使用了更短的 2,000 token，prefill 更快
- C. 并发太低，服务端还没饱和
- D. 500 个请求只有第 1 个未命中缓存（0.2%），不到 1%，P99 的位置（第 495 个样本）仍是命中值

**Q7.** 本节代码中三组并发（10、50、200）的输出完全相同。根本原因是：

- A. `random.Random(seed)` 固定了种子，所以任何参数都不会影响结果
- B. 并发只用于把请求切成批，但缓存在批内逐个更新，同一批里后到的请求能"看到"前面请求刚写入的缓存；`unique_prefixes` 算出来后也没被使用
- C. 并发越大，P99 的下标计算越不准
- D. `make_uniform_workload` 的参数固定为 500

**Q8.** 讲义推荐用 k6（v2026.1.0）+ k6 Operator 做 CI/CD 门禁。关于 k6 Operator，正确的是：

- A. 它是 Locust 的扩展，用于修复 GIL 陷阱
- B. 它通过 `TestRun` / `PrivateLoadZone` 等 CRD 在 Kubernetes 上原生地做分布式压测，1.0 版于 2025 年 9 月 GA
- C. 它只能在单机上运行，不支持分布式
- D. 它是 NVIDIA 的参考压测实现

---

## 三、动手 / 代码题

**Q9.** 阅读 `simulate()` 并手算（不运行代码）：

```python
    for i in range(0, len(reqs), concurrency):
        batch = reqs[i:i + concurrency]
        unique_prefixes = len({r.prefix_hash for r in batch})
        for r in batch:
            hit = r.prefix_hash in cache
            ttft = PREFIX_CACHE_HIT_TTFT_MS if hit else PREFIX_CACHE_MISS_TTFT_MS
            if not hit:
                cache.add(r.prefix_hash)
            ttft_samples.append(ttft)
    ttft_samples.sort()
    p50 = ttft_samples[len(ttft_samples) // 2]
    p99 = ttft_samples[int(len(ttft_samples) * 0.99) - 1]
```

已知 REALISTIC 工作负载 500 个请求，从 80 个前缀中随机抽取，实际出现了 **79** 种不同前缀。

1. cache_hits、mean、P50、P99 各是多少？
2. 如果把前缀池扩大，让 500 个请求里实际出现 313 种不同前缀，P50 会变成多少？
3. 这说明"真实分布"这个工作负载本身还有什么不够真实的地方？

**Q10.** 改造 `simulate()`，让 concurrency 真正起作用：同一批（同时在途）的请求彼此看不到对方写入的缓存——批次结束后才把这批的新前缀写入缓存。写出代码，并说明 UNIFORM 在并发 10 / 50 / 200 下 cache_hits 分别变成多少、为什么随并发下降。

**Q11.** 讲义"实际应用"一节说 `code/main.py`"measures effective TPOT"。请通读代码，回答：

1. 哪些常量/字段被定义了却从未参与计算？
2. 代码实际测到了 TPOT 吗？TTFT 与 prompt 长度有关吗？
3. 如果要让 TTFT 反映 prompt 长度与缓存命中，给出一个合理的 TTFT 模型（写成函数）。

**Q12.**（讲义练习 2）写一个 k6 CI 门禁脚本：对流式 chat completions 端点施加 100 并发、持续 5 分钟，门禁为 TTFT P95 < 800 ms、请求失败率 < 5%。说明你用 k6 的哪个计时字段近似 TTFT，以及这个近似在什么情况下不成立。

---

## 四、面试高频题

**Q13.**（基础必考）为什么说"k6 和 Locust 会撒谎"？分别说说 LLM 负载测试里最常见的两个陷阱、它们在哪一侧造成偏差、以及如何修复。

**Q14.**（原理深挖）TTFT、TPOT、ITL、E2E 分别测什么？为什么不同压测工具对同一服务报告不同的 TPOT？客户端测量本身还会引入哪些误差？

**Q15.**（工程实践）给一个 70B 模型的聊天 API（SLA：TTFT P95 < 800 ms、TPOT P95 < 30 ms、5xx < 1%）设计完整的负载测试方案：工具、prompt 分布、四种模式的参数、CI 门禁。

**Q16.**（场景设计）（讲义练习 3）Soak 测试显示进程内存每小时增长 50 MB。说出三个可能原因，以及分别用什么手段区分它们。

**Q17.**（追问型）（讲义练习 4）Spike 测试从 10 RPS 突增到 100 RPS，集群已经部署了 Karpenter + vLLM production-stack。你预计恢复需要多久？时间都花在哪里？怎样缩短？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Reported inter-token latency includes client-side tokenization backlog. You think the server is slow; it's the test harness." 服务端指标不变而客户端测量恶化，正是"测量工具自己成了瓶颈"的信号。修复：换 LLM-Locust（把 tokenization 移到独立进程），或换编译型语言的 harness（k6、使用 tokenizers.rs 的 LLMPerf）。

- B：服务端指标几乎不变，与"GPU 饱和"矛盾。
- C：与 HTTP 版本无关，且连接被拒会表现为错误率而不是 ITL 变长。
- D：缓存命中只影响 prefill（TTFT），且命中越多应该越快。

### Q2 — 答案：C

讲义："Server sees the same prefix every time — prefix cache hits approach 100%, throughput looks great." 问题部分还提到 request-coalescing（请求合并）：500 个相同请求看起来像 500 路并发 decode，实际只处理了一路。

- A：截断与否取决于上下文窗口，2,000 token 远未超限。
- B：10,000 次的样本量足够，问题是偏差（bias）而非方差。
- D：相同 prompt 不会系统性地让输出变长。

### Q3 — 答案：D

讲义："Soak — steady-state for 4-8 hours. Catches: memory leaks, connection-pool drift, observability overflow." 每天一次的 OOM 是典型的慢泄漏，30 分钟的稳态（C）、15 分钟的 Ramp（A）、2 分钟的 Spike（B）时长都不够把它暴露出来。

### Q4 — 答案：B

讲义："Spike — sudden 3-10x RPS for 2 min then back. Catches: autoscaling latency, queue saturation, cold-start impact." A 是 Soak 的目标，C 是 Steady-state 的目标，D 与负载模式无关（是工具口径问题）。

### Q5 — 答案：A

17 · 08 节讲义的例子：TTFT 500 ms、100 个输出 token、decode 共 700 ms 时，GenAI-Perf 报 `700/99 = 7.07 ms`，LLMPerf 报 `(500+700)/100 = 12.00 ms`。

反推本题：设输出 100 个 token，GenAI-Perf 的 6 ms 意味着 decode ≈ `6 × 99 = 594 ms`；LLMPerf 的 11 ms 意味着 `TTFT + 594 = 1,100 ms`，即 TTFT ≈ 506 ms。两个数字都"正确"，只是口径不同。

- B：tokenizer 实现影响计数速度，不会造成近 2 倍差距。
- C、D：都是臆测，题目已说明"同一批请求"。

注意：中文讲义练习 5 把 LLMPerf 的数字误译成 "TPOT=1100ms"，英文原文是 11ms。

### Q6 — 答案：D

UNIFORM 只有一个前缀 `single_prefix`，第 1 个请求 miss（800 ms），后 499 个全部命中（80 ms）。排序后只有下标 499 是 800。P99 取下标 `int(500×0.99)−1 = 494`，仍是 80。均值 `(499×80 + 800)/500 = 81.44 ≈ 81 ms`，与输出一致。

- A：代码中 P50 用 `len//2`、P99 用 `int(n*0.99)-1`，并没有写错。
- B：反而 UNIFORM 的 prompt（2,000）比 REALISTIC 的均值（约 504）长得多；何况代码根本没用 `prompt_tokens`。
- C：代码里没有"服务端饱和"的建模。

### Q7 — 答案：B

`simulate` 先按 `concurrency` 切批，但批内仍是**逐个**判断 `hit` 并立即 `cache.add`，等价于完全串行处理。批大小怎么变，每个前缀都恰好只 miss 一次，所以三组结果一字不差。`unique_prefixes` 算出后没有任何地方使用，`BATCH_EFFICIENCY_SHARED_PREFIX` 也没被使用。

- A：种子固定只保证同一参数下可复现，若并发参与计算，不同并发的结果依然会不同（见 Q10）。
- C：P99 下标只与 n 有关，与并发无关。
- D：n 固定为 500 与"并发不影响结果"无关。

### Q8 — 答案：B

讲义："k6 Operator uses TestRun / PrivateLoadZone CRDs for Kubernetes-native distributed testing"，"k6 Operator 1.0 GA (Sept 2025)"，"Best for CI/CD gates and SLA testing"。A 描述的是 LLM-Locust；C 与"distributed"矛盾；D 描述的是 GenAI-Perf。

### Q9 — 参考答案

1. 79 种前缀各 miss 一次，其余命中：
   - cache_hits = `500 − 79 = 421`；
   - mean = `(421×80 + 79×800)/500 = (33,680 + 63,200)/500 = 193.76 ≈ 194 ms`；
   - 排序后下标 0–420 为 80，421–499 为 800；P50 下标 250 → **80 ms**；P99 下标 494 → **800 ms**。
   - 与实际运行输出 `REALISTIC 500 80ms 800ms 194ms 421` 完全一致。
2. 313 种前缀 → hits = 187，下标 187 起就是 800，P50（下标 250）变为 **800 ms**。实际改造运行（前缀池 500、seed=7）的结果为 `p50=800, p99=800, mean=530.72, cache_hits=187`。前缀池 300 时出现 246 种前缀，hits = 254，P50 仍是 80，均值 434.24——P50 在 "hits 是否超过 250" 这条线上发生跳变。
3. 不够真实之处：
   - **前缀高度重复**：80 个前缀服务 500 个请求，命中率 84%，"真实"工作负载依然非常缓存友好，P50 仍是 80 ms；真实流量的前缀多样性要靠真实数据确定；
   - **缓存无限大、永不淘汰**：真实的 KV/前缀缓存有容量上限，会 LRU 淘汰；
   - **TTFT 只有两个取值**：与 prompt 长度、排队无关（见 Q11）；
   - **没有并发竞争**（见 Q10）。
   结论：代码只是在演示"缓存命中率决定数字"这个机制，并不能给出真实容量上限。

### Q10 — 参考答案

```python
def simulate_concurrent(reqs, concurrency):
    cache, ttft_samples = set(), []
    for i in range(0, len(reqs), concurrency):
        batch = reqs[i:i + concurrency]
        new_prefixes = set()
        for r in batch:
            hit = r.prefix_hash in cache          # 只看"批开始前"已存在的缓存
            ttft_samples.append(
                PREFIX_CACHE_HIT_TTFT_MS if hit else PREFIX_CACHE_MISS_TTFT_MS)
            new_prefixes.add(r.prefix_hash)
        cache |= new_prefixes                     # 整批完成后才写入缓存
    ttft_samples.sort()
    n = len(ttft_samples)
    return {"p50": ttft_samples[n // 2],
            "p99": ttft_samples[int(n * 0.99) - 1],
            "mean": statistics.mean(ttft_samples),
            "cache_hits": sum(t == PREFIX_CACHE_HIT_TTFT_MS for t in ttft_samples)}
```

实际运行结果：

| 并发 | UNIFORM hits / mean | REALISTIC hits / mean |
|------|---------------------|-----------------------|
| 10 | 490 / 94.4 ms | 417 / 199.52 ms |
| 50 | 450 / 152 ms | 392 / 235.52 ms |
| 200 | 300 / 368 ms | 285 / 389.6 ms |

UNIFORM 的第一批 `concurrency` 个请求全部 miss（缓存还没建立），所以 hits = `500 − concurrency`。并发越高，"冷缓存"阶段同时在途的请求越多。这对应真实系统里的现象：同时到达的相同前缀不一定能共享缓存——除非服务端做了请求合并或在 prefill 期间就能共享前缀（SGLang 的 RadixAttention 正是为此设计，见 17 · 06）。这个模型仍然简化（批同步、无排队），但至少让 concurrency 参与了计算。

### Q11 — 参考答案

1. 未使用的有：`TPOT_MS = 15`、`BATCH_EFFICIENCY_SHARED_PREFIX = 0.8`、`Request.prompt_tokens`、`simulate` 内的局部变量 `unique_prefixes`。
2. 没有测到 TPOT：输出只有 TTFT 的 P50/P99/mean。TTFT 只取决于是否命中缓存（80 或 800 ms），与 prompt 长度无关——UNIFORM 的 2,000 token 与 REALISTIC 的平均约 504 token（实际统计：均值 503.9、标准差 170.9、最小 50、最大 1008）对结果毫无影响。讲义说代码"measures effective TPOT"与实际不符。
3. 一个合理的模型（prefill 时间与**未命中缓存的 token 数**成正比）：

```python
def ttft_ms(prompt_tokens, cached_tokens, queue_ms=0.0,
            base_ms=30.0, prefill_ms_per_token=0.35):
    uncached = max(0, prompt_tokens - cached_tokens)
    return queue_ms + base_ms + uncached * prefill_ms_per_token
```

其中 `cached_tokens` 来自前缀缓存命中的长度（命中整个系统提示时可能是几百 token），`queue_ms` 来自排队模型。再用 `E2E = TTFT + TPOT × output_tokens` 计算端到端延迟。系数需要用真实 benchmark 标定，这里只是示意。

### Q12 — 参考答案

```javascript
import http from 'k6/http';
import { check } from 'k6';
import { Trend } from 'k6/metrics';

const ttft = new Trend('ttft', true);          // true = 按时间单位显示

export const options = {
  scenarios: {
    gate: { executor: 'constant-vus', vus: 100, duration: '5m' },
  },
  thresholds: {
    ttft: ['p(95)<800'],                       // TTFT P95 < 800 ms
    http_req_failed: ['rate<0.05'],            // 失败率 < 5%
  },
};

const prompts = JSON.parse(open('./prompts.json'));   // 来自真实流量的采样，禁止单一 prompt

export default function () {
  const p = prompts[Math.floor(Math.random() * prompts.length)];
  const res = http.post(`${__ENV.BASE_URL}/v1/chat/completions`, JSON.stringify({
    model: __ENV.MODEL, stream: true, max_tokens: 256,
    messages: [{ role: 'user', content: p }],
  }), { headers: { 'Content-Type': 'application/json' }, timeout: '60s' });
  ttft.add(res.timings.waiting);               // TTFB 近似 TTFT
  check(res, { 'status 200': (r) => r.status === 200 });
}
```

要点：

- `res.timings.waiting` 是从发出请求到收到第一个字节（TTFB）的时间。若服务端收到请求后先排队、prefill，然后立刻以 SSE 推送第一个 token，TTFB ≈ TTFT。
- **不成立的情况**：网关/代理缓冲了整个响应（如 Nginx 未关闭 `proxy_buffering`）；服务端先发送 HTTP 头或空的 keep-alive 事件再推 token；第一个 SSE 事件只有 role 没有内容。这时需要真正逐块解析流的客户端（讲义："k6 v2026.1.0 streaming-aware metrics"，或 LLMPerf/GenAI-Perf）。
- 门禁要稳定：讲义 skill 文件要求"3-run stability"，建议同一 PR 跑 3 次全部通过才算绿。
- 加分点：`constant-vus` 是**闭环**模型（每个 VU 等响应回来才发下一个），服务变慢时实际 RPS 会自动下降，掩盖排队问题；想测"固定到达率"应改用 `constant-arrival-rate` executor。

### Q13 — 参考回答要点

- **为什么是独立学科**：LLM 响应是流式的、输出长度可变、核心指标是 token 级的（TTFT、TPOT），瓶颈在 GPU 和 KV cache；通用压测只看 HTTP 请求成功率和整体耗时。
- **GIL 陷阱（客户端侧偏差）**：Locust 在 Python 里做 tokenization 来计算逐 token 指标，高并发下与请求生成争抢 GIL，积压被算进 ITL。修复：LLM-Locust（多进程 tokenization）、k6 / LLMPerf（编译语言或 Rust tokenizer）。自检方法：压测机 CPU 是否打满、服务端指标是否同步恶化。
- **单一 prompt 陷阱（服务端缓存侧偏差）**：同一前缀命中前缀缓存、请求合并，吞吐和 TTFT 被严重高估。修复：从分布采样（LLMPerf 的 mean/stddev），或回放真实流量；内容和前缀都要多样。
- 加分点：讲义开头的故事——500 并发的 k6 测试通过，生产中 200 个真实用户就把服务打垮、P99 TTFT 爆炸，就是这两个陷阱叠加的结果。
- 常见误区：只把 prompt **长度**随机化，内容仍是同一个模板 + 同一个系统提示，前缀缓存依然几乎全中。

### Q14 — 参考回答要点

- **定义**（见 17 · 08）：TTFT = 排队 + prefill + 网络，到第一个 token；TPOT / ITL = decode 阶段相邻 token 的间隔；E2E = TTFT + TPOT × 输出 token 数 + 网络。
- **工具差异**：GenAI-Perf 的 ITL 从第 2 个 token 起算、不含 TTFT；LLMPerf 包含 TTFT（`(TTFT + decode)/N`）。长 prompt、短输出时差异最大。跨工具比较前必须声明口径，skill 文件把"不对齐口径就比较跨工具数字"列为 hard reject。
- **客户端测量误差**：
  - 压测机资源不足（GIL、CPU、网卡），测到的是客户端积压；
  - token 计数方式不同（客户端重新 tokenize vs 用服务端返回的 usage），SSE 一个事件可能包含多个 token；
  - 网关/代理缓冲把流"攒成一块"，ITL 失真；
  - 闭环压测的 coordinated omission（协调遗漏）：服务变慢时客户端少发请求，尾延迟被低估。
- **报告方式**：P50/P90/P99，不只看均值；把 goodput（同时满足所有 SLO 的请求比例）作为最终判断依据。

### Q15 — 参考回答要点

- **工具**：基准运行用 LLMPerf；PR 门禁用 k6（编译语言、无 GIL，k6 Operator 做分布式）；若团队已用 Locust，必须加 LLM-Locust 扩展。
- **prompt 分布**：从生产日志统计输入 token 的 mean/stddev（例如 500 ± 150），并按真实比例混合不同系统提示与多轮对话前缀；没有数据时用 ShareGPT 并在报告中写明假设。输出长度也要按分布设置 `max_tokens`。
- **四种模式**（数值示例，需按目标容量调整）：
  - Steady：目标 RPS 的 70%，45 分钟 → 基线回归；
  - Ramp：0 → 150% 目标 RPS，15 分钟 → 找出 TTFT P95 越过 800 ms 的拐点；
  - Spike：基线 → 5 倍，持续 2 分钟再回落 → 观察排队、autoscaler 反应时间、冷启动、5xx；
  - Soak：目标 RPS 的 70%，6 小时 → 内存、连接池、日志/trace 量。
- **CI 门禁**：每个 PR 3–5 分钟、30–50 次迭代；TTFT P95 < 800 ms、TPOT P95 < 30 ms、5xx < 1%；连续 3 次运行都通过才绿。Soak 不进 PR，放夜间任务（skill 文件："If CI gate budget is < 60s per PR, refuse full soak"）。
- **口径**：固定使用一个工具的 TPOT 定义并写进报告。
- 加分点：压测环境的前缀缓存状态要明确（冷启动后先预热还是不预热），并记录模型版本、引擎参数（batch size、chunked prefill）以便复现。

### Q16 — 参考回答要点

三个常见原因与区分手段：

1. **应用层对象泄漏**（会话历史、prompt 模板缓存、无界的 dict/list）：用 Python `tracemalloc` 或 `memray` 在不同时间点做快照对比，看增长集中在哪一行分配。
2. **连接池/客户端漂移**（HTTP 连接未释放、SSE 流未关闭、每请求新建 client）：监控打开的 socket/fd 数量（`ls /proc/<pid>/fd | wc -l`）、连接池指标；如果 fd 数与内存同步增长，基本可以确定。
3. **Observability 溢出**（trace/span 在内存中排队导出失败、日志缓冲、metrics 标签基数爆炸）：查看 OTel exporter 队列长度、丢弃计数、Prometheus 时间序列数量；临时关闭 tracing 后增长是否消失。

其他候选：引擎侧 KV/前缀缓存配置为不设上限（CPU offload 层持续增长）、分配器碎片（glibc malloc，可对比 `jemalloc`）。方法论：先确认增长发生在哪个进程（网关、应用、推理引擎），再按"对象 → 连接 → 观测管道"逐层排除；用 Soak 复现并在修复后再跑一次验证斜率归零。

### Q17 — 参考回答要点

- **要分情况**：
  - 已有副本有余量：vLLM 的 continuous batching 直接吸收，TTFT 因排队上升，几秒到几十秒内恢复；
  - 需要新副本、节点池里有空闲 GPU：只需拉起 Pod + 加载权重 + 引擎初始化；
  - 需要新节点：17 · 03 讲义："Karpenter's 45-60 second warm-up plus a 20GB model load plus engine init means a from-zero request takes 2-5 minutes"；17 · 10 讲义给出 70B 原始冷启动 3–8 分钟。
- **时间分解**：autoscaler 检测（指标采集周期 + 稳定窗口）→ 调度/Karpenter 起节点（45–60 s）→ 拉镜像 → 加载权重 → 引擎初始化（CUDA graph、KV cache 预分配）→ 路由器把新副本纳入（production-stack 的路由）。
- **缩短方法**：基于队列深度/KV 利用率而不是 GPU duty cycle 扩缩容；warm pool（`min_workers=1`）；预置节点镜像、模型流式加载、GPU 快照；路由层的 prefix-aware / KV 感知路由让已有副本承接更多流量。
- **验证方式**：Spike 测试里同时记录"开始突增 → 新副本 ready → P95 TTFT 回到 SLO"的三个时间点，区分 autoscaling 延迟与冷启动开销。
- 常见误区：给出一个"30 秒"之类的固定数字而不分情况；以为 Spike 只测服务端，忽略压测客户端自身能否瞬时提升 10 倍发压能力。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：本节所有门禁指标的精确定义，以及 GenAI-Perf / LLMPerf 的口径差异。
- [阶段 17 · 03 Kubernetes 上的 GPU Autoscaling：Karpenter、KAI Scheduler 与成组调度](../../03-gpu-autoscaling-kubernetes/docs/zh.md)：Spike 测试要验证的对象。
- [阶段 17 · 06 前缀缓存服务：RadixAttention 与 KV 复用](../../06-sglang-radixattention/docs/zh.md)：单一 prompt 陷阱之所以"有效"，正是因为前缀缓存。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：并发请求在引擎内如何批处理。

### 本节被哪些后续内容用到
- [阶段 17 · 10 缓解无服务器 LLMs 的冷启动](../../10-cold-start-mitigation/docs/zh.md)：Spike 测试暴露的冷启动问题如何缓解。
- [阶段 17 · 18 生产服务技术栈：KV 卸载与缓存感知路由](../../18-vllm-production-stack-lmcache/docs/zh.md)：讲义练习 4 的部署前提。
- [阶段 17 · 20 面向 LLMs 的 Shadow Traffic、金丝雀 Rollout 与渐进式部署](../../20-shadow-canary-progressive/docs/zh.md)：上线前压测之后，用真实流量做渐进验证。
- [阶段 17 · 24 LLM 生产环境中的混沌工程](../../24-chaos-engineering-llm/docs/zh.md)：在负载之上注入故障。
- [阶段 17 · 27 LLMs 的 FinOps：单位经济性与多租户成本归因](../../27-finops-llms/docs/zh.md)：压测得到的容量直接决定单位成本。

### 延伸关键词
`LLMPerf` · `GenAI-Perf` · `LLM-Locust` · `guidellm` · `k6 Operator / TestRun CRD` · `Vegeta` · `GIL` · `prefix cache hit rate` · `request coalescing` · `open-loop vs closed-loop` · `coordinated omission` · `constant-arrival-rate` · `soak test` · `goodput`
