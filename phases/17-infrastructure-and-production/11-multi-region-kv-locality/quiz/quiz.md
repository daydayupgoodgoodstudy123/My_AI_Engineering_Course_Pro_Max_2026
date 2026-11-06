# 测验 · 多区域 LLM 服务与 KV Cache 局部性（Multi-Region LLM Serving and KV Cache Locality）

> **阶段 17 · 基础设施与生产 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | Round-robin 对有缓存的推理"有害" | LLM 推理是有状态的：没落到持有该前缀 KV 的节点，就要付完整 prefill；讲义场景中 ALB 轮询让前缀命中率掉到 8%、TTFT P50 翻三倍 |
| 2 | 命中 vs 未命中 | 讲义：Llama 3.3 70B FP8 / H100、2K prompt，命中约 80 ms、冷 prefill 约 800 ms，约 10 倍 |
| 3 | Cache-aware router | 输入：副本发布的 KV-cache 事件（块分配/驱逐）+ 请求的前缀哈希（如前 512 token）；算法：按前缀哈希匹配；平局/未命中：按队列深度或 GPU 利用率 |
| 4 | 代表实现 | vLLM Router（Rust，订阅 `kv.cache.block_added`，O(1) 查表，未命中退回最小队列）、llm-d router（Kubernetes 原生）；SGLang RadixAttention 是**副本内**的等价物，跨副本路由在其上游 |
| 5 | 跨区域多了网络项 | RTT：us-east-1↔us-west-2 约 65 ms、↔eu-west-1 约 75 ms、↔ap-southeast-1 约 220 ms；GORGO 研究把 `prefill_time + network_latency` 联合最小化 |
| 6 | 商用跨区域推理不等于 KV 感知 | Bedrock Cross-Region Inference、GKE Multi-Cluster Gateway 优化的是**可用性**，把推理当黑盒，不管 TTFT；仍需要应用层的 cache-aware router |
| 7 | DR 的"32% 缺文件"问题 | 讲义：32% 的 LLM DR 失败是因为只备份了权重，漏了 tokenizer、量化配置（AWQ scales、GPTQ zero-points）、RoPE scaling / chat template、引擎配置、LoRA 清单 |
| 8 | 三文件最小 DR 清单 | ① HF 模型仓库全部文件；② 引擎服务配置；③ 部署清单（K8s YAML、Dockerfile、依赖锁）；外加每季度演练（讲义：JPMorgan 2024 年 11 月 us-east-1 演练约 22 分钟恢复，SLA 30 分钟） |
| 9 | 数据驻留优先于缓存 | 欧盟用户的 PHI 不能出欧盟；先按驻留边界切分路由器，再在边界内做缓存优化 |
| 10 | "区域优先"是常见答案 | 讲义：多数情况下保持区域内路由，只在 prefill 远大于网络延迟（很长前缀）时跨区域 |

### 核心技能（能动手做到）

- [ ] 用"命中率 × 命中延迟 + (1 − 命中率) × 未命中延迟"估算不同路由策略的平均 TTFT
- [ ] 计算"跨区域命中"何时优于"本地未命中"的提示长度临界点
- [ ] 设计 cache-aware router：前缀哈希、KV 事件索引、未命中时的一致性哈希、平局规则
- [ ] 在路由策略中显式加入数据驻留约束
- [ ] 为一个量化 + 多 LoRA 的部署写出完整的 DR 清单并自动校验
- [ ] 读懂本节模拟器，找出队列深度恒为 0、`set.pop()` 随机驱逐等问题并修正

---

## 二、基础自测（选择题）

**Q1.** 讲义说 round-robin 负载均衡对有缓存的 LLM 推理"actively harmful"，最根本的原因是：

- A. Round-robin 会破坏 TLS 会话
- B. Round-robin 只适用于有状态数据库
- C. Round-robin 必须配合 sticky session 才能工作
- D. LLM 推理是有状态的，请求若没落到持有其前缀 KV cache 的副本，就要付完整的 prefill 代价

**Q2.** 一个 cache-aware router 需要消费的两类输入是：

- A. 用户 ID 与租户 ID
- B. 副本发布的 KV-cache 事件（块分配/驱逐）与请求的前缀哈希
- C. 轮询计数器与 TLS 密钥
- D. 随机数与请求体大小

**Q3.** 讲义引用的"32% 的 LLM DR 失败"主要原因是：

- A. 只备份了权重，漏了 tokenizer 文件、量化配置等
- B. 区域配额耗尽
- C. 负载均衡器配置错误
- D. 备份没有加密

**Q4.** 关于 AWS Bedrock Cross-Region Inference，讲义的观点是：

- A. 它是 KV-cache 感知的，可以替代应用层路由
- B. 它在 GDPR 下被禁止使用
- C. 它在容量紧张时把请求路由到其他区域，优化的是可用性而非 TTFT，把推理当黑盒；仍需要应用层 cache-aware router
- D. 它只在 us-east-1 可用

**Q5.** 一个来自巴黎的请求，其前缀恰好在 us-east-1 的某个副本上命中缓存。按讲义的原则，应该：

- A. 路由到 us-east-1，因为 TTFT 能从 800 ms 降到约 155 ms
- B. 先路由过去，再在日志中脱敏
- C. 不路由；先按数据驻留边界切分路由器，跨驻留边界的路由即使能改善 TTFT 也禁止
- D. 让用户自己选择

**Q6.** 讲义写道：从 us-east-1 路由到 ap-southeast-1 的热前缀，"the saved prefill (800 → 80 ms) is dwarfed by 440 ms round-trip"。用讲义自己的数字检验，下列说法正确的是：

- A. 即使按 440 ms 计，跨区域命中约 80 + 440 = 520 ms，仍低于本地未命中的 800 ms；省下的 720 ms prefill 并没有被"淹没"。讲义列出的 RTT 本身就是 220 ms，440 ms 还重复计算了一次往返
- B. 讲义正确，跨区域命中总是比本地未命中慢
- C. 跨区域命中的 TTFT = 800 + 440 = 1,240 ms
- D. 只要跨区域，TTFT 就一定超过 1 秒

**Q7.** 本节代码中 `REGIONAL` 策略的命中率只有约 31%，只比 `ROUND_ROBIN` 略好。主要原因是：

- A. 每个副本的缓存容量只有 12，不足以容纳 40 个前缀
- B. 请求量太少，缓存来不及预热
- C. `REGIONAL` 每次都跨区域路由
- D. `queue_depth` 的更新式 `max(0, q + (1 if rng.random() < 0.4 else 0) - 1)` 让它永远为 0，所以未命中时 `min(local, key=queue_depth)` 总是选区域内第一个副本；所有未命中都挤到同一个副本，其余 3 个副本的缓存始终为空

**Q8.** 本节代码中 `GLOBAL` 策略命中率最高（约 86%–89%），但它还有一个讲义明确禁止的问题：

- A. 它没有使用 RTT
- B. 它不考虑数据驻留：一次运行中 312 个欧盟来源的请求里有 190 个被路由出了 eu-west-1
- C. 它的 P99 比 round-robin 高
- D. 它从不跨区域

---

## 三、动手 / 代码题

**Q9.** 阅读 `simulate` 中与缓存和队列相关的片段：

```python
        elif strategy == "REGIONAL":
            local = [rep for rep in replicas if rep.region == r.origin_region]
            matches = [rep for rep in local if r.prefix_hash in rep.prefix_cache]
            if matches:
                chosen = min(matches, key=lambda x: x.queue_depth)
            else:
                chosen = min(local, key=lambda x: x.queue_depth)
        ...
            chosen.prefix_cache.add(r.prefix_hash)
            if len(chosen.prefix_cache) > 12:
                chosen.prefix_cache.pop()
        chosen.queue_depth = max(0, chosen.queue_depth + (1 if rng.random() < 0.4 else 0) - 1)
```

1. 证明 `queue_depth` 永远为 0，并统计 `REGIONAL` 下各副本服务的请求数。
2. `prefix_cache` 是 `set`，`set.pop()` 驱逐的是哪个元素？代码固定了 `random.Random(7)` 和 `random.Random(11)`，为什么多次运行的命中率仍然不同（例如 GLOBAL 在 86.3%–89.2% 之间波动）？
3. 用"未命中时按前缀哈希做一致性分配（例如 `zlib.crc32(prefix) % 4`）+ LRU 驱逐（`OrderedDict`）"修正 `REGIONAL`，命中率和平均 TTFT 变为多少？与原 `GLOBAL` 相比说明了什么？

**Q10.** 讲义练习 1："在 75 ms RTT 下，提示多长时跨区域路由优于本地路由？"代码中命中/未命中是固定的 80 / 800 ms，与提示长度无关。请按讲义的 2K prompt 数字把 prefill 线性化：未命中 `0.4 ms/token × L`。

1. 若跨区域命中的成本为固定 `80 ms + RTT`，求 RTT = 75、130、220 ms 时的临界长度 L。
2. 若命中只需计算未缓存的后缀，成本近似 `0.04 ms/token × L + RTT`，重新计算 RTT = 75 ms 时的临界长度。
3. 这与 skill 文件"long prompts (>8K tokens) benefit from cross-region routing"的说法相比如何？为什么生产中仍倾向区域优先？

**Q11.** 讲义练习 5：为 `GLOBAL` 策略加入数据驻留约束——欧盟来源的请求只能在 eu-west-1 服务，非欧盟请求不能路由进/出欧盟以外的约束可按需设定（本题设定：EU 与非 EU 互不跨越）。在 Q9 修正后的一致性哈希 + LRU 版本上实现，并报告命中率、平均 TTFT 与跨区域请求数；与无约束版本对比。

**Q12.** 讲义练习 3：为一个 vLLM 服务的 70B AWQ 量化模型（带 5 个 LoRA adapter）设计 DR 清单。写一个 `check_dr_manifest(files, n_lora=5)`，返回缺失项列表；用"只备份了权重分片和 `config.json`"的情况测试，说明会缺哪些。

---

## 四、面试高频题

**Q13.**（基础必考）为什么传统的 L4/L7 负载均衡（轮询、最少连接）不适合 LLM 推理？cache-aware router 是怎么工作的？

**Q14.**（原理深挖）cache-aware router 的前缀哈希该怎么设计？路由器的缓存索引和副本的真实缓存不一致时会发生什么？

**Q15.**（工程实践）线上前缀缓存命中率从 70% 掉到 12%。请给出三个可能原因，以及能证实每个原因的观测指标。（讲义练习 2）

**Q16.**（场景设计）一家金融科技公司在 us-east-1、us-west-2、eu-west-1 部署 70B 模型，TTFT SLO 严格，且有欧盟客户。他们问"开启 Bedrock Cross-Region Inference 是不是就够了"。请设计多区域方案并回答这个问题。（讲义练习 4）

**Q17.**（追问型）"我们每天把权重同步到另一个区域的 S3，DR 没问题。"你会追问什么？

---

## 五、参考答案与解析

### Q1 — 答案：D

讲义："A request that does not land on the node holding its prefix pays full prefill cost"；"Round-robin is optimal for stateless services. LLM inference is stateful by design — the KV cache encodes everything the model has seen." A、B、C 都与 KV cache 无关；sticky session 是一种粗糙的亲和性手段，但按会话而不是按前缀，也不是 round-robin 的前提。

### Q2 — 答案：B

讲义："Replicas publish KV-cache events on a pub/sub channel as they allocate and evict blocks. Router picks the replica with the match, falls through to GPU-util-based tie-breaker if no one does." 前缀哈希例如取前 512 token。A、C、D 都不是缓存状态的信息来源。

### Q3 — 答案：A

讲义："32% of LLM DR failures happen because teams backed up weights but forgot: tokenizer.json ... Quantization configs ... Model-specific configs ... Engine config"。B、C、D 都是一般性的运维问题，不是讲义引用的统计。

### Q4 — 答案：C

讲义："It optimizes availability, not TTFT, and treats inference as opaque ... You still need an app-layer cache-aware router even when using these. They handle the 'us-east-1 is on fire' case." skill 文件把"声称 Bedrock CRI 解决了跨区域路由"列为 hard reject。A 正好说反；B、D 无依据。

### Q5 — 答案：C

讲义："If your cache-aware router sends a Paris-originated request to us-east-1 for a prefix match, you have violated GDPR regardless of TTFT gain. Partition routers by residency boundary before optimizing for cache." A 只看 TTFT；B 脱敏日志不能改变"数据已经出境"的事实；D 不是合规的做法。

### Q6 — 答案：A

讲义列出的"Inter-region RTT"中 us-east-1↔ap-southeast-1 为约 220 ms，RTT 本身已经是往返时间；"440 ms round-trip"相当于又乘了 2。即便按 440 ms 计：跨区域命中 `80 + 440 = 520 ms` < 本地未命中 `800 ms`，省下的 720 ms 并未被淹没；按 220 ms 计则为 300 ms。所以对 2K prompt 而言，单看 TTFT 跨区域命中是划算的。保持区域路由的真正理由是：短提示时 prefill 本来就小（见 Q10）、数据驻留、跨区域流量费用、以及路由到远端热点造成的负载集中。B、C、D 都与讲义自己的数字矛盾（C 把命中当成了未命中）。

### Q7 — 答案：D

从 0 出发：以 40% 概率 `0 + 1 − 1 = 0`，以 60% 概率 `max(0, −1) = 0`——永远回到 0（实际跑 10 万步，最大值为 0）。于是未命中时 `min(local, ...)` 在全 0 的列表中返回第一个元素，实际统计 `REGIONAL` 下各区域只有 0 号副本在服务：us-east-1/0 服务 365 个、us-west-2/0 服务 323 个、eu-west-1/0 服务 312 个，其余 9 个副本 0 个请求。每个区域实际只用了 12 个缓存槽来装 40 个前缀，命中率自然只有约 30%。A 错，区域内 4 × 12 = 48 个槽本来足以装下 40 个前缀；B 错，1000 个请求、40 个前缀足够预热；C 错，REGIONAL 的跨区域数为 0。

### Q8 — 答案：B

实际统计（一次运行）：GLOBAL 的跨区域流向在 6 个方向上大致均匀，eu-west-1 来源的 312 个请求中有 190 个被路由到美国区域。代码的 GLOBAL 只比较 `CACHE_HIT_MS + rtt`，没有任何驻留约束，正是讲义说的"violated GDPR regardless of TTFT gain"。A 错，它用了 RTT；C 错，GLOBAL 的 P99 为 800 ms，低于 round-robin 的 930 ms；D 错，它跨区域了约 570–600 次。

### Q9 — 参考答案

1. 证明见 Q7：更新式只有"+1−1"和"−1 后截断为 0"两种结果，初值为 0 时永远不会离开 0。实际统计：REGIONAL 下 3 个区域各自的 0 号副本承担了全部 1000 个请求（365 / 323 / 312）。在真实系统里这相当于"平局规则退化为固定顺序"，造成热点副本。修正：真实的队列深度应随请求到达 +1、完成 −1，或者直接使用副本上报的排队数。
2. `set.pop()` 弹出的是**任意**元素（取决于集合内部的哈希表布局），不是最旧的，也不是最少使用的。而 Python 对 `str` 的哈希默认按进程随机化（`PYTHONHASHSEED`），所以同一组前缀字符串在不同进程中的集合布局不同，被驱逐的元素也不同。固定 `random.Random(seed)` 只控制了工作负载和队列的随机数，管不住字符串哈希。实际用 `PYTHONHASHSEED=0/1/2/3/random` 各运行一次，GLOBAL 命中率分别为 86.3%、89.2%、86.8%、88.3%、87.5%；ROUND_ROBIN 在 26.7%–28.9% 之间。要可复现，应设置 `PYTHONHASHSEED` 或改用有序的 LRU 结构。
3. 修正思路与结果（已实际运行，`zlib.crc32` 是确定性的，结果可复现）：

```python
home = local[zlib.crc32(r.prefix_hash.encode()) % len(local)]   # 一致性分配
cache = OrderedDict()                                            # 每副本一个
if prefix in cache: cache.move_to_end(prefix)                    # LRU 命中
else:
    cache[prefix] = True
    if len(cache) > 12: cache.popitem(last=False)                # 驱逐最久未用
```

| 版本 | 命中率 | 平均 TTFT | P50 | 跨区域 |
|------|-------|----------|-----|-------|
| 原 REGIONAL | 30.9% | 578 ms | 800 ms | 0 |
| 修正 REGIONAL | **88.0%** | **166 ms** | 80 ms | 0 |
| 原 GLOBAL（一次运行，随哈希种子波动） | 88.4% | 216 ms | 145 ms | 595 |
| 修正 GLOBAL（无驻留约束） | 96.0% | 166 ms | 145 ms | 648 |

说明：修正后的 REGIONAL 不跨区域就达到了与原 GLOBAL 相当的命中率，且平均 TTFT 更低（166 vs 216 ms）；剩下 12% 的未命中基本是每个区域对 40 个前缀各自的"首次未命中"（3 × 40 = 120 次）。修正后的 GLOBAL 命中率更高（96%），但多出的命中都要付 RTT，平均 TTFT 与 REGIONAL 持平（都约 166 ms），还多了 648 次跨区域流量。这正是讲义"Often the answer is to keep routing regional"的结论——原代码中 GLOBAL 的大幅领先，主要是 REGIONAL 的队列深度 bug 造成的假象。

### Q10 — 参考答案

1. 跨区域命中优于本地未命中的条件：`0.4·L > 80 + RTT`，即 `L > (80 + RTT) / 0.4`：

| RTT | 临界长度 |
|-----|---------|
| 75 ms | 约 388 token |
| 130 ms | 约 525 token |
| 220 ms | 750 token |

2. `0.4·L > 0.04·L + 75` → `L > 75 / 0.36 ≈ 208` token。
3. 按讲义的单位数字，临界长度只有几百个 token，远低于 skill 文件说的 ">8K tokens"。但生产中仍倾向区域优先，原因包括：
   - 这个比较假设"本地一定未命中"。只要本地路由做得好（Q9：修正后区域内命中率 88%），本地命中 80 ms 永远优于跨区域命中 `80 + RTT`；跨区域只在"本地未命中且远端命中"时才有意义；
   - 数据驻留可能直接禁止；
   - 跨区域流量有费用（代码中 $0.0004/请求），并会把负载集中到远端热点副本，增加排队延迟（代码没有建模真实排队）；
   - 网络 RTT 有抖动，影响 P99；
   - 很长的前缀（讲义说"massive multi-MB prefixes"）才让 prefill 的绝对差值大到值得承担这些风险，这才是 ">8K tokens" 经验值的含义。

### Q11 — 参考答案

在修正版 GLOBAL 中，候选副本先按驻留边界过滤：

```python
def allowed(origin, rep_region):
    return (origin == "eu-west-1") == (rep_region == "eu-west-1")   # EU 与非 EU 互不跨越

candidates = [rp for rp in reps if allowed(r.origin_region, rp[0])]
# 本地 home 副本未命中时，才在 candidates 中找 80 + RTT 最小的命中副本
```

实际运行结果：

| 版本 | 命中率 | 平均 TTFT | P50 | 跨区域 |
|------|-------|----------|-----|-------|
| 修正 GLOBAL（无约束） | 96.0% | 166 ms | 145 ms | 648 |
| 修正 GLOBAL（驻留约束） | 92.0% | 160 ms | 80 ms | 344（仅美国两区之间） |
| 修正 REGIONAL | 88.0% | 166 ms | 80 ms | 0 |

加入驻留约束后，欧盟请求只在 eu-west-1 内命中；美国两个区域之间仍可互相借用缓存。命中率下降 4 个百分点，但平均 TTFT 不升反降（160 vs 166 ms）、P50 回到 80 ms——因为少了很多"命中但要付 75–130 ms RTT"的请求。合规约束在这个负载上几乎没有性能代价。实现要点：**先过滤再优化**，而不是优化后再检查；路由器按驻留边界分区部署更安全（EU 路由器根本看不到美国副本的索引）。

### Q12 — 参考答案

```python
REQUIRED = {
    "weights":        lambda f: any(x.endswith(".safetensors") for x in f),
    "model config":   lambda f: "config.json" in f,                       # 含 RoPE scaling 等
    "tokenizer":      lambda f: "tokenizer.json" in f or "tokenizer.model" in f,
    "tokenizer cfg":  lambda f: "tokenizer_config.json" in f,             # chat template 通常在这里
    "quant config":   lambda f: "quantize_config.json" in f or "quant_config.json" in f,
    "generation cfg": lambda f: "generation_config.json" in f,            # 采样默认值
    "engine config":  lambda f: "vllm_config.yaml" in f,
    "lora manifest":  lambda f: "lora/manifest.json" in f,
    "deploy manifest": lambda f: "k8s/deployment.yaml" in f and "Dockerfile" in f,
    "dependency lock": lambda f: "requirements.lock" in f,
}

def check_dr_manifest(files, n_lora=5):
    f = set(files)
    missing = [k for k, ok in REQUIRED.items() if not ok(f)]
    for i in range(n_lora):
        for part in ("adapter_config.json", "adapter_model.safetensors"):
            p = f"lora/adapter_{i}/{part}"
            if p not in f:
                missing.append(p)
    return missing
```

用 `["model-00001-of-00008.safetensors", "config.json"]` 测试，实际返回 **18 项**缺失：tokenizer、tokenizer cfg、quant config、generation cfg、engine config、lora manifest、deploy manifest、dependency lock 这 8 类，加上 5 个 adapter 各 2 个文件共 10 个。补齐后返回空列表。

清单按讲义的三文件结构归类：

1. **HF 模型仓库**：全部权重分片、`config.json`（含 RoPE scaling）、`tokenizer.json` / `tokenizer.model`、`tokenizer_config.json`（chat template）、`generation_config.json`、AWQ 的 `quantize_config.json`（scales / group size 等）；
2. **引擎配置**：`vllm_config.yaml`（量化方式、max model len、KV cache dtype、LoRA 相关参数）、采样默认值、LoRA adapter 清单与每个 adapter 的 `adapter_config.json` 与权重；
3. **部署清单**：K8s YAML、Dockerfile（固定引擎版本）、依赖锁文件。

要点：清单检查应该自动化并纳入 CI，而不是靠人记；再配合季度演练真正从备份启动一次（讲义："run a DR drill quarterly"）。实际文件名以所用工具链为准，这里是示例。

### Q13 — 参考回答要点

- **为什么不适合**：轮询、最少连接假设后端无状态、任何副本处理同一请求代价相同。LLM 副本持有 KV cache（包括前缀缓存），同样的请求落在有缓存的副本上 TTFT 约 80 ms，落在没有的副本上约 800 ms（讲义 2K prompt）。轮询会把同前缀的请求打散到所有副本，命中率趋近 `1 / 副本数`，讲义场景中掉到 8%。
- **cache-aware router 的工作方式**：
  - 副本在分配/驱逐 KV 块时发布事件（pub/sub），路由器维护"前缀哈希 → 副本"的索引；
  - 请求到达时计算前缀哈希（例如前 512 token），O(1) 查表；
  - 命中则路由到持有者（多个持有者时按队列深度选）；未命中则按最小队列深度 / GPU 利用率选择，或用一致性哈希把同前缀固定到某个副本以便后续命中；
  - 代表：vLLM Router（Rust）、llm-d router（K8s 原生）。
- 加分点：副本内部的前缀复用由 RadixAttention / 自动前缀缓存完成，路由器负责"让请求去对的副本"，二者是上下游关系（讲义："Cross-replica routing is strictly upstream"）。

### Q14 — 参考回答要点

- **前缀哈希设计**：
  - 按 token 而不是按字符串哈希（同样的文本在不同 tokenizer 版本下结果不同）；
  - 按 KV 块粒度做**链式哈希**（每块哈希包含前一块的哈希），这样可以做"最长前缀匹配"，而不是只匹配固定的前 512 token；
  - 只哈希前 N token 的问题：系统提示相同、用户内容不同的请求会被视为同一前缀，路由合理；但若前 N token 不足以区分（例如共享很长的系统提示后接不同文档），命中只能复用系统提示部分；
  - 哈希碰撞概率要足够低（64 位以上），并包含模型/LoRA 标识（不同 adapter 的 KV 不能复用）。
- **索引与真实缓存不一致**：
  - 驱逐事件延迟到达 → 路由器以为命中，实际未命中（"假命中"），付出完整 prefill；
  - 事件丢失 → 索引永久陈旧；需要定期全量同步或带 TTL 的索引；
  - 副本重启 → 缓存清空，必须发布清空事件；
  - 后果是命中率虚高、TTFT 尾部变差；监控"路由器预测命中率 vs 副本实际命中率"的差异可以发现问题。
- 加分点：热门前缀会把流量集中到少数副本，需要负载上限（超过队列阈值就放弃亲和性），或把热门前缀复制到多个副本。

### Q15 — 参考回答要点

| 可能原因 | 证实的观测 |
|---------|-----------|
| 路由退化为轮询（router 故障、事件通道断开、新部署绕过了 router） | 路由器日志中"索引命中"比例骤降；KV 事件订阅延迟/错误率；同前缀请求分布到的副本数变多 |
| 缓存容量不足导致驱逐风暴（流量上涨、上下文变长、副本缩容、KV 显存被别的配置占用） | 副本的 KV 块驱逐速率上升、KV 使用率接近 100%、并发数/平均上下文长度变化；缩容事件 |
| 前缀本身变了（提示模板改版、系统提示中加入了时间戳/请求 ID 等动态字段、tokenizer 或模型版本更新导致哈希变化） | 前缀哈希的基数（distinct count）骤增；命中率下降的时间点与发布记录吻合；按模板版本拆分的命中率 |

- 其它可能：多区域故障转移把流量切到冷区域；LoRA adapter 增多导致缓存被按 adapter 切碎。
- 处理：先回滚可疑发布或修复路由，再看容量；把"路由器命中率、副本命中率、驱逐速率、前缀基数"做成看板（skill 文件建议告警"跨区域前缀缓存命中率低于阈值"）。

### Q16 — 参考回答要点

- **直接回答**：Bedrock CRI 不够。讲义：它"optimizes availability, not TTFT, and treats inference as opaque"——容量紧张时会把请求送到其他区域，既不感知 KV 缓存，也可能把请求送往你不想去的区域；严格 TTFT SLO 需要应用层的 cache-aware router。CRI 可以保留为"区域着火"时的可用性兜底层。
- **方案**：
  - **驻留分区**：EU 请求只在 eu-west-1（路由器按驻留边界独立部署）；美国两个区域可以互借缓存；
  - **区域内 cache-aware 路由**：vLLM Router / llm-d router，KV 事件索引 + 前缀哈希 + 未命中一致性哈希 + 队列深度上限；
  - **跨区域策略**：默认区域内；仅在 `本地未命中 且 远端命中 且 prefill 节省 > RTT + 余量` 时跨（美国两区之间），参考 GORGO 的联合目标；
  - **可用性层**：CRI 或多集群网关处理区域级故障，但要确认其目标区域符合驻留要求；
  - **DR**：三文件清单 + 跨区域复制 + 季度演练，目标 RTO 30 分钟（讲义 JPMorgan 演练 22 分钟）；
  - **观测**：按区域的 TTFT P99、命中率、跨区域比例、goodput。
- 常见误区：把"可用性"与"延迟优化"混为一谈；只备份权重。

### Q17 — 参考回答要点

- **文件是否齐全**：tokenizer、`tokenizer_config.json`（chat template）、量化配置（AWQ scales、GPTQ zero-points）、RoPE scaling、生成默认值、引擎配置、LoRA adapter 及其清单、部署 YAML、Dockerfile、依赖锁——讲义："32% of LLM DR failures" 正是漏了这些。
- **版本一致性**：备份的权重与引擎版本、配置是否对应同一次发布？有没有版本号和校验和？
- **能否真正启动**：最近一次从备份冷启动是什么时候？用了多久（RTO）？讲义：JPMorgan 演练 22 分钟，"only because the playbook was rehearsed"。
- **容量**：目标区域有没有足够的 GPU 配额？冷启动需要多久（第 10 节）？缓存预热期间 TTFT 会恶化多少？
- **RPO**：每天同步意味着最多丢一天的配置/adapter 变更，是否可接受？
- **驻留**：备份所在区域是否符合数据驻留要求（例如包含欧盟客户的 LoRA 或日志）？
- 加分点：把"从备份启动并跑通 smoke test"做成定期自动任务。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：KV 块的分配与驱逐是 KV 事件的来源。
- [阶段 17 · 06 前缀缓存服务：RadixAttention 与 KV 复用](../../06-sglang-radixattention/docs/zh.md)：副本内的前缀复用；本节是它的跨副本、跨区域版本。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：TTFT 的组成（排队 + 网络 + prefill）。
- [阶段 11 · 15 Prompt 缓存与上下文缓存](../../../11-llm-engineering/15-prompt-caching/docs/zh.md)：应用层视角的前缀缓存。

### 本节被哪些后续内容用到
- [阶段 17 · 18 生产服务技术栈：KV 卸载与缓存感知路由](../../18-vllm-production-stack-lmcache/docs/zh.md)：vLLM production stack 的路由器与 LMCache。
- [阶段 17 · 17 Prefill 与 Decode 分离：NVIDIA Dynamo 与 llm-d](../../17-disaggregated-prefill-decode/docs/zh.md)：llm-d 的路由与 KV 传输。
- [阶段 17 · 19 AI 网关](../../19-ai-gateways/docs/zh.md)：网关层的路由与故障转移。
- [阶段 17 · 24 LLM 生产环境中的混沌工程](../../24-chaos-engineering-llm/docs/zh.md)：区域故障演练。
- [阶段 17 · 26 合规：SOC 2、HIPAA、GDPR、PCI-DSS、EU AI Act、ISO 42001](../../26-compliance-frameworks/docs/zh.md)：数据驻留的合规要求。
- [阶段 17 · 10 缓解无服务器 LLMs 的冷启动](../../10-cold-start-mitigation/docs/zh.md)：故障转移时目标区域的冷启动与 live migration。

### 延伸关键词
`cache-aware routing` · `prefix hash` · `KV-cache events` · `vLLM Router` · `llm-d` · `consistent hashing` · `LRU eviction` · `GORGO` · `inter-region RTT` · `Bedrock Cross-Region Inference` · `GKE Multi-Cluster Gateway` · `data residency / GDPR` · `DR manifest` · `RTO / RPO` · `PYTHONHASHSEED`
