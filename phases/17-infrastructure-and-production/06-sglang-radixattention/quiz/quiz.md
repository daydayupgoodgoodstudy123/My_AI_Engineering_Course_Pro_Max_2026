# 测验 · 前缀缓存服务：RadixAttention 与 KV 复用（Prefix-Cache Serving — RadixAttention and KV Reuse）

> **阶段 17 · 基础设施与生产 · 第 06 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义为机器翻译，请以英文版为准。本节代码中 FCFS 与 CACHE_AWARE 在 RAG 工作负载上的命中率**完全相同**（69.1%），并没有达到代码自己声称的"超过 80%"，原因见 Q9、Q10。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 问题 | 5,000 个 RAG 请求共享 2,000 token 的 system prompt 时，经典 serving 会把这段前缀 prefill 5,000 次 |
| 2 | Radix tree 作为 KV 索引 | 压缩 trie：每个节点拥有一段 token 及其 KV block；新请求从根往下走，匹配到的节点直接复用 KV，prefill 成本只与"新后缀"成正比 |
| 3 | 前缀缓存命中率 | 由复用 KV 提供的 prompt token 占比（"你的 prompt 有多少是免费的"） |
| 4 | Cache-aware 调度 | 深度优先派发：优先调度与当前常驻分支共享前缀的请求，让热分支留在 HBM；FCFS 可能在下一个长前缀请求到来前把热分支驱逐 |
| 5 | 分支级 LRU | 按 radix 形状驱逐：从最久未用的叶子开始整段驱逐，而不是零散地驱逐 block |
| 6 | Prompt 顺序是缓存键 | 固定顺序：不变内容（system、tools、schemas）在前 → 检索上下文 → 对话历史 → 用户问题；不要把动态内容插进前缀 |
| 7 | 讲义基准数字 | Llama 3.1 8B、H100、ShareGPT 1K prompt：SGLang 约 16,200 tok/s vs vLLM 约 12,500（约 29%）；前缀密集 RAG 最高 6.4x；语音克隆命中率 86.4%；客户命中率 50–99%；2026 年部署于 40 万+ GPU |
| 8 | 真实案例 | 把动态内容移出可缓存前缀，一个部署的命中率从 7% 升到 74% |
| 9 | 赢与输 | 赢：RAG、agent（固定 tool schema）、长 system prompt 对话、固定前导的语音/视觉；输：无共享前缀的单次生成、每个请求都在前缀中插入独特内容 |
| 10 | 与 vLLM 的关系 | vLLM 也有 `--enable-prefix-caching` 和缓存感知路由（Rust 实现的 vLLM Router），差距缩小但未消失；前缀复用主导的负载默认选 SGLang |

### 核心技能（能动手做到）

- [ ] 画出给定一组 prompt 的 radix tree，算出每个节点的 KV block 数和新请求需要新 prefill 的 block 数
- [ ] 计算一个工作负载在理想缓存下的最大命中率，以及 KV 预算不足时的实际命中率
- [ ] 估算常驻一段 system prompt 的 HBM 开销（按模型的层数、KV 头数、head_dim）
- [ ] 读懂本节玩具 `RadixCache` 的 walk / insert / evict，并指出"驱逐当前路径上的祖先节点"等问题
- [ ] 解释为什么本节的 CACHE_AWARE 排序在 RAG 负载上与 FCFS 完全等价，并写出真正按分支分组的调度
- [ ] 审计一个 prompt 模板的顺序，给出能提升命中率的改写

---

## 二、基础自测（选择题）

**Q1.** SGLang 的 KV 复用由什么数据结构支撑？

- A. Radix tree（压缩 trie），每个节点拥有一段 token 及其对应的 KV block
- B. 哈希表，以完整 prompt 的哈希为键
- C. 平衡二叉搜索树，按请求到达时间排序
- D. 布隆过滤器，用来判断 prompt 是否见过

**Q2.** 讲义的 radix tree 示例中，新请求 = system（2,000 token）+ doc A（500 token）+ 一个约 60 token 的新问题（4 个 block）。讲义称无树时需要 160 个 block、有树时只需新分配 4 个，节省约 40 倍。按 16 token/block 严格计算，system 与 doc A 应分别占多少个 block？

- A. 124 和 31，与讲义一致
- B. 2000 和 500
- C. 125 和 32（讲义的 124、31 少算了向上取整的 1 个 block）
- D. 128 和 32

**Q3.** 为什么讲义认为 FCFS 不适合前缀密集流量？

- A. FCFS 不支持 continuous batching
- B. FCFS 会让短请求饿死
- C. FCFS 无法使用 PagedAttention
- D. FCFS 只看到达顺序，可能先服务共享前缀很短的请求，并在下一个长前缀请求到来前把热分支驱逐出 HBM

**Q4.** 一个部署的命中率从 7% 升到 74%，讲义说只做了一件事：

- A. 把 GPU 换成 H200
- B. 把动态内容移出可缓存的前缀
- C. 把 KV block 从 16 token 改成 32 token
- D. 把 SGLang 换成 vLLM

**Q5.** 运行本节 `code/main.py`，RAG 工作负载（固定顺序）下 FCFS 与 CACHE_AWARE 的命中率分别是：

- A. 69.1% 与 85.0%
- B. 8.4% 与 26.5%
- C. 两者都是 69.1%
- D. 两者都是 96.0%

**Q6.** 本节代码 RAG 工作负载中，每个请求是 `[SYSTEM(2000), TOOLS(300), DOC_x(500), Q_i(60)]`，KV 预算 `KV_BUDGET_BLOCKS = 160`。一条完整路径需要多少 block？这意味着什么？

- A. 125 + 19 + 32 + 4 = 180 个 block，超过 160 的预算，缓存连一条完整路径都放不下
- B. 2860 个 block，远超预算
- C. 160 个 block，刚好放下一条路径
- D. 90 个 block，可以放下近两条路径

**Q7.** 下列哪个工作负载**最不可能**从 RadixAttention 获益？

- A. RAG：固定 system prompt + 固定检索前导 + 不同问题
- B. Agent：固定的 tool schema + 不同查询
- C. 带 2,000 token system prompt 的客服对话
- D. 没有 system prompt、每个请求都是独特代码片段的代码补全

**Q8.** 讲义推荐的 prompt 模板顺序是：

- A. 用户问题 → 检索上下文 → system → tools
- B. system → tools / schemas → 检索上下文 → 对话历史 → 用户问题
- C. 检索上下文 → system → 用户问题 → tools
- D. 顺序无所谓，radix tree 会自动识别人看来相同的内容

---

## 三、动手 / 代码题

**Q9.** 阅读 `RadixCache.insert` 与 `_evict_one`：

```python
    def insert(self, segments: list[str]) -> None:
        for i in range(1, len(segments) + 1):
            key = tuple(segments[:i])
            if key in self.nodes:
                continue
            blocks = (token_count(segments[i - 1]) + BLOCK_TOKENS - 1) // BLOCK_TOKENS
            while self.used + blocks > self.budget and self._evict_one():
                pass
            self.nodes[key] = [blocks, self.time]
            self.used += blocks

    def _evict_one(self) -> bool:
        leaves = [k for k in self.nodes if not any(
            other != k and other[: len(k)] == k for other in self.nodes)]
        if not leaves:
            return False
        victim = min(leaves, key=lambda k: self.nodes[k][1])
        self.used -= self.nodes.pop(victim)[0]
        return True
```

在空缓存上插入第一个请求 `["SYSTEM", "TOOLS", "DOC_3", "Q_13"]`，逐步写出 `used` 的变化和每次被驱逐的节点，并说明插入结束后缓存里剩下什么。这暴露了什么问题？

**Q10.** CACHE_AWARE 的排序函数：

```python
        def score(r: Request) -> int:
            return max(branch_count[tuple(r.segments[:i])] * sum(
                token_count(s) for s in r.segments[:i])
                for i in range(1, len(r.segments) + 1))
        order = sorted(requests, key=score, reverse=True)
```

1. 在 RAG 工作负载（80 个请求、4 个文档，文档出现次数分别为 27、20、18、15）中，每个请求的 score 是多少？为什么 CACHE_AWARE 的顺序与 FCFS 完全相同？
2. 写一个真正"按分支分组"的排序，并说明在 KV 预算为 180 或 200 block 时它能把命中率提升到多少（实际运行结果见答案）。
3. 这个 score 还有什么不现实之处？

**Q11.** 讲义练习 3：Llama 3.1 8B 有 32 层、8 个 KV 头、head_dim 128。按 BF16 计算：

1. 让 2,000 token 的 system prompt 作为一个 radix 分支常驻 HBM 要多少显存？
2. 不做前缀复用时，16 条序列的 batch 各自保存这段 system prompt 要多少显存？

**Q12.** 讲义练习 2 说"随机打乱 `[system, tools, context]` 的顺序后命中率会崩溃"。代码的 scrambled 工作负载结果为 FCFS 8.4%、CACHE_AWARE 26.5%。但把 KV 预算扩大到 10,000 block 后（已实际运行），scrambled 的命中率是 **79.5%**，固定顺序是 **96.0%**。

1. 为什么无限缓存下打乱顺序仍有 79.5% 的命中率？
2. 那么本节代码在默认预算下"崩溃"到 8.4%，主要原因是顺序打乱还是预算太小？
3. 在真实系统中，什么样的"顺序问题"会让命中率真正接近 0？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 prefix caching / RadixAttention？它节省的是 prefill 还是 decode 的计算？命中率如何定义？

**Q14.**（原理深挖）为什么说 KV 复用"是调度问题而不只是 kernel 问题"？cache-aware 调度和分支级 LRU 各解决什么？

**Q15.**（工程实践）客户反馈前缀缓存命中率只有 8%（讲义练习 5）。请给出三个可能原因以及各自的诊断方法。

**Q16.**（场景设计）你要为一个多租户 RAG 平台选择 SGLang 还是 vLLM（带 `--enable-prefix-caching`），请给出决策流程和需要测量的数据。

**Q17.**（追问型）讲义说"前缀密集 RAG 最高 6.4x"。如果你的老板据此承诺"上 SGLang 就快 6 倍"，你会怎样回应？如何估算你自己工作负载的预期加速？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Tokens are indexed in a radix tree; each node owns KV blocks for the token sequence on its path from root." B 只能做"整个 prompt 完全相同"的缓存，无法复用部分前缀（vLLM 的 automatic prefix caching 是按 block 哈希的，但哈希的是"到该 block 为止的前缀"，与整 prompt 哈希不同）；C、D 都不能做最长前缀匹配。

### Q2 — 答案：C

`ceil(2000 / 16) = 125`，`ceil(500 / 16) = 32`（31.25 向上取整）。讲义写的 124 与 31 各少了 1 个 block（讲义中 520 token → 33 block、95 token → 6 block 则是正确向上取整的）。所以严格来说无树时是 `125 + 32 + 4 = 161` 个 block，节省约 40 倍的结论不变。B 混淆了 token 与 block；D 是按 2048/16 估算。

### Q3 — 答案：D

讲义："FCFS does the opposite — it serves whoever arrived first, potentially evicting the hot branch before the next long-prefix request hits." A、C 错：FCFS 是调度顺序，与 continuous batching、PagedAttention 正交（vLLM 默认就是 FCFS + 两者）。B 是 cache-aware 调度可能带来的问题（长期偏好热分支会让冷请求饿死），不是 FCFS 的问题。

### Q4 — 答案：B

讲义："moving dynamic content out of the cacheable prefix took one deployment from 7% to 74% cache hit rate in one change." 动态内容（时间戳、用户名、会话 ID 等）一旦出现在前缀前部，后面所有内容都无法共享。A、C 不改变前缀是否相同；D 与命中率无直接关系。

### Q5 — 答案：C

实际运行：`RAG workload | FCFS hit_rate= 69.1%`、`RAG workload | CACHE_AWARE hit_rate= 69.1%`，saved 都是 158,000 / 228,800 token。158,000 = 79 × 2,000，也就是**只有 SYSTEM 被复用了 79 次**，TOOLS、DOC 从未命中。代码的 KEY FINDING 说"固定顺序 + cache-aware 命中率超过 80%"，与输出不符。B 是 scrambled 工作负载的结果；D 是 KV 预算足够大时的理论最大值（见 Q10）。

### Q6 — 答案：A

`ceil(2000/16) = 125`，`ceil(300/16) = 19`，`ceil(500/16) = 32`，`ceil(60/16) = 4`，合计 180 > 160。注释说"small budget so eviction bites under FCFS"，但预算小到连一条完整路径都放不下，任何调度策略都只能保住 SYSTEM，这就是 FCFS 与 CACHE_AWARE 结果相同的根本原因之一。B 把 token 当成了 block。

### Q7 — 答案：D

讲义"Loses"一节："Single-shot generation with unique prompts (code completion, open-ended chat without system prompt)." 没有共享前缀，radix tree 无可复用，性能回到 vLLM 水平。A、B、C 都在讲义"Wins"列表中。

### Q8 — 答案：B

讲义："Put everything immutable (system, tools, schemas) first. Put retrieval context next. Put user question last." skill 给出的规范顺序是 system → tools/schemas → retrieval context → conversation history → user input。D 是讲义特意批驳的误解："What looks like a shared prefix to a human is two distinct sequences to the radix tree."

### Q9 — 参考答案

逐步（block 数：SYSTEM 125、TOOLS 19、DOC 32、Q 4；已实际插桩验证）：

1. 插入 `(SYSTEM,)`：`used = 125`。
2. 插入 `(SYSTEM, TOOLS)`：`125 + 19 = 144 ≤ 160`，`used = 144`。
3. 插入 `(…, DOC_3)`：`144 + 32 = 176 > 160`，需要驱逐。此时唯一的叶子是 `(SYSTEM, TOOLS)`——**它正是当前要插入节点的父节点**——被驱逐，`used = 125`；再插入 DOC，`used = 157`。
4. 插入 `(…, Q_13)`：`157 + 4 = 161 > 160`，唯一叶子是刚插入的 `(…, DOC_3)`，被驱逐，`used = 125`；插入 Q，`used = 129`。

结束后缓存里只有 `(SYSTEM,)` 和 `(SYSTEM, TOOLS, DOC_3, Q_13)`。后者是**孤儿节点**：它的父节点已不存在，`walk` 在 TOOLS 处就会停止，永远走不到它，但它仍占着 4 个 block，直到下次被当作 LRU 叶子驱逐。

暴露的问题：

- 驱逐时没有保护"当前正在插入/使用的路径"。真实的 SGLang 对正在被运行中请求使用的节点做引用计数，引用计数为 0 的节点才可被驱逐。
- 叶子判断用 `other[:len(k)] == k` 是"任意后代"判断，`(SYSTEM,)` 因为有孤儿后代而永远不被视为叶子——这里碰巧保住了 SYSTEM。
- `_evict_one` 每次都扫描所有节点对，复杂度 O(n²)，真实实现靠树结构和优先队列维护叶子。

### Q10 — 参考答案

1. RAG 负载中所有请求都以 `SYSTEM, TOOLS` 开头，深度 2 的 `branch_count = 80`，`80 × 2300 = 184,000`；深度 3 最多 `27 × 2800 = 75,600`；深度 1 为 `80 × 2000 = 160,000`。所以**每个请求的 score 都是 184,000**（已实际验证：只有一个不同的值）。`sorted` 是稳定排序，分数全相同时保持原顺序，于是 CACHE_AWARE 的处理顺序与 FCFS 一字不差。score 取的是"最热的那一层"，而所有请求在最热层上都一样，它不能区分不同文档分支。
2. 真正的分支分组：按共享路径排序，让同一文档的请求连续出现：

   ```python
   order = sorted(requests, key=lambda r: tuple(r.segments[:-1]))   # 按除问题外的前缀分组
   ```

   实际运行（FCFS 顺序 vs 按文档分组）：

   | KV 预算（block） | FCFS | 按分支分组 |
   |-----------------|------|-----------|
   | 160（默认） | 69.1% | 69.1% |
   | 180 | 82.5% | **96.0%** |
   | 200 | 82.5% | **96.0%** |
   | 250 | 89.3% | **96.0%** |

   96.0% 正是理论上限：`(79 × 2300 + 76 × 500) / 228,800`（SYSTEM+TOOLS 除首个请求外全部命中，每个文档只有首次 miss，问题永不命中）。默认预算 160 下任何顺序都无济于事，因为一条路径就要 180 个 block。
3. 不现实之处：它是**离线**排序，事先看到了全部 80 个请求并统计了全局分支计数；真实调度器是在线的，只能看到当前等待队列，还要考虑到达时间、公平性和饥饿（热分支一直优先，冷分支请求可能等很久）。SGLang 的做法是在等待队列中按"与缓存的最长前缀匹配长度"排序（longest-prefix-match first），这是在线可实现的近似深度优先。

### Q11 — 参考答案

每 token KV = `32 层 × 2（K、V）× 8 KV 头 × 128 × 2 字节 = 131,072 字节 = 128 KiB`。

1. 2,000 token：`131,072 × 2,000 ≈ 262 MB`（250 MiB）。
2. 16 条序列各存一份：`262 MB × 16 ≈ 4.19 GB`，复用后只需 262 MB，省下约 3.9 GB——在 80GB 的 H100 上，8B 模型权重约 16GB（BF16），这几 GB 足够再放下几十条中等长度序列的 KV。

注意：若错用 32 个查询头计算会高估 4 倍。

### Q12 — 参考答案

1. 打乱只是在 `[SYSTEM, TOOLS, DOC]` 的 6 种排列之间随机选（实际分布 18/16/13/12/11/10）。同一种排列的请求之间仍然共享前缀；例如以 SYSTEM 开头的 25 个请求仍共享那 2,000 token。缓存足够大时，每种排列的前缀只在第一次出现时 miss，所以仍有 79.5%。
2. 主要是预算太小。默认 160 block 连一条路径都放不下，固定顺序时还能靠"SYSTEM 永远在第一位"保住 2,000 token 的复用；打乱后第一段只有约 1/3 的概率是 SYSTEM，连这点复用也保不住，于是跌到 8.4%。CACHE_AWARE 在打乱时有效（26.5%），是因为不同排列的 score 不同，排序恰好把相同首段的请求聚在了一起。
3. 真正让命中率接近 0 的是**前缀最前面出现每个请求都不同的内容**：时间戳、请求 ID、用户名、随机 few-shot 抽样、把用户问题放在 system prompt 之前等。只要第一个 token 不同，后面的一切都无法共享。讲义 7% → 74% 的案例就是这种情况。

### Q13 — 参考回答要点

- **定义**：把已经算过的 prompt 前缀的 KV cache 保留下来，后续请求如果以相同的 token 序列开头，就直接复用这些 KV，不再 prefill。SGLang 用 radix tree 组织这些 KV（RadixAttention），vLLM 用基于 block 哈希的 automatic prefix caching。
- **节省什么**：主要是 **prefill** 计算（以及 TTFT）；decode 每步仍要读取完整的 KV（包括复用的前缀部分），所以 decode 成本不变。复用还节省 KV 显存，可以容纳更多并发序列，间接提升吞吐。
- **命中率**：由复用 KV 提供的 prompt token 数 / prompt 总 token 数。讲义：客户命中率 50–99%，取决于 prompt 纪律。
- 加分点：讲义数据——ShareGPT 1K prompt 上 SGLang 比 vLLM 快约 29%；前缀密集 RAG 最高 6.4x；同时指出这些数字依赖工作负载形状。

### Q14 — 参考回答要点

- **kernel 层面**：让注意力 kernel 能读取共享的 KV block（借助 PagedAttention 的 block table，多个序列指向同一批物理 block）。这一步不难。
- **调度层面**：缓存容量有限，若调度顺序与前缀结构无关，热分支会被频繁驱逐又重建（cache thrash），复用率很低。讲义："reuse only pays if the scheduler keeps the hot branch resident."
- **cache-aware 调度**：优先调度与常驻分支共享前缀的请求（深度优先遍历），让同一分支的请求集中处理，减少驱逐。
- **分支级 LRU**：按 radix 形状从最久未用的叶子开始驱逐，保证剩下的总是"从根出发的完整前缀"；按 block 级 LRU 可能把一个前缀中间的 block 驱逐掉，导致后面的 block 虽在显存里却无法被匹配（本节代码中出现的"孤儿节点"就是这种浪费）。
- **还要保护正在使用的节点**：被运行中请求引用的节点不可驱逐（引用计数）。
- 风险：长期偏好热分支会让冷请求饥饿，需要老化（aging）或配额。

### Q15 — 参考回答要点

1. **动态内容在前缀前部**（时间戳、请求 ID、用户信息放进 system prompt）：抓取一批真实 prompt，计算两两最长公共前缀长度的分布；看第一个分叉点出现在第几个 token。
2. **模板顺序不一致**（不同客户端或代码路径拼接顺序不同，或 tools 列表顺序随机、JSON 键顺序不稳定）：对 prompt 做"规范化前后"的对比，统计前缀的不同版本数；检查 tool schema 序列化是否稳定排序。
3. **缓存容量不足或驱逐过快**（KV 预算小、并发高、长尾多租户）：看缓存驱逐率、常驻分支数、按租户的命中率；用影子流量逐步加大缓存预算，观察命中率曲线是否随预算明显上升。
- 其他可能：多副本之间没有缓存感知路由，相同前缀的请求被分散到不同副本（阶段 17 · 18）；tokenizer 差异（同一文本因前导空格不同被切成不同 token）。
- 加分点：skill 的建议——在代理层做模板规范化（无法控制客户端模板时）。

### Q16 — 参考回答要点

- **先测量**：抽样真实流量，计算可共享前缀长度、重复率和预期命中率（skill："Recommending SGLang without measuring actual prefix sharing in traffic. Refuse."）。
- **审计模板**：按规范顺序重排，移出动态内容，再测一次预期命中率。
- **决策阈值（skill）**：预期命中率 > 40% 且非单次生成 → SGLang；< 30% → vLLM + `--enable-prefix-caching` 更简单；30–40% → 在样本上两者都跑一遍。
- **多租户**：每个租户的 system prompt 不同，分支数多；需要按租户分配缓存预算，防止大租户的热分支挤掉小租户（skill 提示 tree-branch eviction 会饿死小租户）。
- **上线**：48 小时影子基准，记录命中率、TTFT、吞吐，修正模板问题后再基准，达标后上线。
- **多副本**：配合缓存感知路由，让共享前缀的请求落到同一副本。

### Q17 — 参考回答要点

- **回应**：6.4x 是"相同 system + 相同文档、只有问题不同"的前缀密集 RAG 上的上限数字（讲义原话 "up to 6.4x"），skill 明确禁止脱离工作负载形状引用它；通用 ShareGPT 风格流量上讲义给出的优势约 29%。
- **估算方法**：
  - 测量 prompt 长度分布、可复用前缀比例 h（命中率）、输出长度；
  - prefill 节省 ≈ h × prefill 时间；若 prefill 占端到端时间的比例为 f，则端到端加速的粗略上限约为 `1 / (1 − f·h)`；
  - 输出长、decode 主导的负载，前缀缓存对总吞吐帮助有限（decode 成本不变），但 KV 显存的节省可以提高并发；
  - 最后用影子流量实测命中率与吞吐，而不是只靠公式。
- 加分点：指出命中率还依赖 prompt 模板纪律和缓存容量，本节代码就显示了预算不足时 cache-aware 调度毫无作用。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：KV block 与调度器的基础，RadixAttention 构建在分页 KV 之上。
- [阶段 11 · 06 RAG（检索增强生成）](../../../11-llm-engineering/06-rag/docs/zh.md)：本节最典型的前缀密集工作负载（讲义前置写作 "Phase 14 (Agentic RAG)"）。
- [阶段 11 · 15 Prompt 缓存与上下文缓存](../../../11-llm-engineering/15-prompt-caching/docs/zh.md)：API 层面的 prompt 缓存与本节引擎层面的前缀复用是同一思想。

### 本节被哪些后续内容用到
- [阶段 17 · 11 多区域 LLM 服务与 KV Cache 局部性](../../11-multi-region-kv-locality/docs/zh.md)：把前缀缓存扩展到多区域路由。
- [阶段 17 · 14 Prompt 缓存与语义缓存的经济性](../../14-prompt-semantic-caching/docs/zh.md)：命中率如何转化为成本。
- [阶段 17 · 18 生产服务技术栈：KV 卸载与缓存感知路由](../../18-vllm-production-stack-lmcache/docs/zh.md)：多副本之间的缓存感知路由与 KV 卸载。
- [阶段 17 · 28 自托管服务选型：让引擎匹配硬件与规模](../../28-self-hosted-serving-selection/docs/zh.md)：SGLang 与 vLLM 等引擎的选型。
- [阶段 17 · 05 生产环境中的 EAGLE-3 Speculative Decoding](../../05-eagle3-speculative-decoding/docs/zh.md)：讲义提到 SGLang 把 EAGLE-3 作为前缀密集负载的推荐草稿路径。

### 延伸关键词
`RadixAttention` · `radix tree / compact trie` · `prefix caching` · `automatic prefix caching (vLLM)` · `cache-aware scheduling` · `longest-prefix-match` · `branch-level LRU` · `reference counting` · `cache hit rate` · `prompt template ordering` · `cache-aware routing` · `SGLang`
