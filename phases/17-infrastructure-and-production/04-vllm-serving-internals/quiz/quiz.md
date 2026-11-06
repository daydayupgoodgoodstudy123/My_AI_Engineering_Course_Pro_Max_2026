# 测验 · 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill（Serving Engine Internals — PagedAttention, Continuous Batching, Chunked Prefill）

> **阶段 17 · 基础设施与生产 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义为机器翻译（PagedAttention 被译成"打印的注意""页面搜索"等），请以英文版为准。本节代码的 STATIC 模式吞吐量反而最高，与讲义结论相反，原因是成本模型不一致（见 Q9），这是本测验的重点。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 静态批处理的三重浪费 | 按窗口内最长 prompt 填充 prefill、按最长输出填充 decode、整批等最慢的序列 |
| 2 | KV cache 大小公式 | 每序列 `num_layers × 2 × num_kv_heads × head_dim × seq_len × bytes`；GQA 模型要用 KV 头数 |
| 3 | 连续预留的浪费 | 按 8192 上限预留而平均只用 1500 token，浪费约 82%；讲义称经典连续分配的碎片浪费为 60–80% |
| 4 | PagedAttention | 像 OS 虚拟内存：KV 按固定大小 block（默认 16 token）分配，每个序列一张 block table 把逻辑位置映射到物理 block；碎片 < 4%；它是 vLLM 唯一的分配器，没有开关 |
| 5 | `--gpu-memory-utilization` | 默认 0.9，加载权重与激活后预留给 KV block 的 HBM 比例 |
| 6 | Continuous batching | 调度器**每个 decode 迭代**运行一次：移除已完成序列 → 在 KV block 够用时接纳新序列 → 对 `RUNNING` 里的所有序列做一次融合前向 |
| 7 | Chunked prefill | 把长 prompt 切成约 512 token 的块，与 decode 交错执行；保护的是 **P99 ITL / TTFT 尾部**，不是平均吞吐；讲义：P99 ITL 约 50ms → 15ms |
| 8 | 三者相互依赖 | PagedAttention 提供细粒度 KV 资源，continuous batching 依赖它做无重排接纳，chunked prefill 只是同一个 `RUNNING` 列表上的又一条调度策略 |
| 9 | 讲义中的基准数字 | Llama 3.3 70B FP8、H100 SXM5、128 并发：三者全开 2,200–2,400 tok/s；默认 vLLM（无 chunked prefill）约 1,800；朴素 PyTorch 循环约 600 |
| 10 | 兼容性矩阵 | 开启所有优化前按具体版本核对；v0.18.0 矩阵标注 speculative decoding 与 chunked prefill、prefix caching 兼容；已知不兼容：pipeline parallelism（至 v0.15.0）、draft-model 投机（至 v0.10.0） |

### 核心技能（能动手做到）

- [ ] 按公式手算任意模型（含 GQA）的每 token / 每序列 KV cache，并算出连续预留与分页分配的浪费比例
- [ ] 画出 continuous batching 一次迭代的三步，并能用伪代码写出调度循环
- [ ] 解释为什么长 prompt 的 prefill 会让其他用户的 ITL 出现尖峰，以及 chunked prefill 如何削平它
- [ ] 读懂本节玩具调度器，指出 STATIC 与 CONTINUOUS 成本模型的不一致，并修正后重新比较
- [ ] 为调度器加上每步 token 预算（`max_num_batched_tokens`）
- [ ] 根据 TTFT、ITL、吞吐、并发四个指标判断瓶颈在 KV、批处理还是 prefill 切分

---

## 二、基础自测（选择题）

**Q1.** 讲义认为经典静态批处理（static batching）的问题**不包括**哪一项？

- A. 把每个请求的 prompt 填充到窗口内最长的 prompt
- B. 每个请求都必须单独加载一份模型权重
- C. 把每个 decode 填充到最长的预期输出
- D. 整批要等最慢的序列结束，快请求只能空等

**Q2.** PagedAttention 把 KV cache 碎片从 60–80% 降到 4% 以下，核心机制是：

- A. 把 KV cache 压缩成 FP4
- B. 把 KV cache 卸载到 CPU 内存
- C. 为每个请求预留最大长度的连续空间
- D. 以固定大小 block（默认 16 token）分配 KV，每个序列用 block table 把逻辑位置映射到物理 block，按需增加 block、完成后归还

**Q3.** vLLM V1 调度器中 continuous batching 的关键不变量是：

- A. 调度器每个 decode 迭代运行一次，而不是每个请求运行一次
- B. 调度器每 10ms 运行一次，凑满一个窗口再执行
- C. 每个 batch 必须填充到固定大小
- D. 新请求只有在当前 batch 全部完成后才能加入

**Q4.** chunked prefill 主要保护的是哪个指标？

- A. 平均吞吐量（tok/s）
- B. 模型加载时间
- C. 混合负载下的 P99 ITL（以及 TTFT 尾部）
- D. KV cache 的碎片率

**Q5.** Llama 3.3 70B 有 80 层、64 个查询头、**8 个 KV 头**（GQA）、head_dim 128。按 BF16 计算，8192 token 的单序列 KV cache 约为：

- A. 0.34 GB
- B. 1.25 GB
- C. 21.5 GB
- D. 2.68 GB

**Q6.** 运行本节 `code/main.py`，四种模式的吞吐量排序是：

- A. STATIC（4055）> CONTINUOUS（886）≈ CONTINUOUS + CHUNKED（885）> NAIVE（768）
- B. CONTINUOUS + CHUNKED > CONTINUOUS > STATIC > NAIVE
- C. NAIVE > STATIC > CONTINUOUS > CONTINUOUS + CHUNKED
- D. 四者完全相同

**Q7.** 本节代码中，开启 chunked prefill 后 CONTINUOUS 的变化是：

- A. 吞吐提升约 3 倍，P99 ITL 不变
- B. 吞吐和 P99 ITL 都不变
- C. 吞吐几乎不变（886 → 885），P99 ITL 从 219.3ms 降到 66.1ms
- D. P99 ITL 变大，因为 prefill 被拆成了更多次

**Q8.** 关于 `--gpu-memory-utilization`，说法正确的是：

- A. 它是开启 PagedAttention 的开关，设为 0 就关闭分页
- B. 默认 0.9，表示加载权重和激活后可用于 KV block 的 HBM 比例上限
- C. 它控制 chunked prefill 的块大小
- D. 它表示 GPU 的 duty cycle 目标，适合作为 HPA 信号

---

## 三、动手 / 代码题

**Q9.** 讲义说"`CONTINUOUS + CHUNKED` 应该在混合流量上占优"，代码末尾也说"STATIC 与 CONTINUOUS 的差距就是 vLLM 存在的理由"。但实际输出是：

```text
NAIVE                         throughput=   768 tok/s   mean_TTFT=5870.5 ms   P99_ITL=  0.7 ms
STATIC (batch=16, padded)     throughput=  4055 tok/s   mean_TTFT= 691.3 ms   P99_ITL=  0.7 ms
CONTINUOUS (no chunk)         throughput=   886 tok/s   mean_TTFT=4671.6 ms   P99_ITL=219.3 ms
CONTINUOUS + CHUNKED          throughput=   885 tok/s   mean_TTFT=4591.5 ms   P99_ITL= 66.1 ms
```

对比两段成本代码，找出至少三处让 STATIC "作弊"的不一致：

```python
# simulate_static
        now += pad_prompt * PREFILL_LATENCY_PER_TOKEN + BATCH_OVERHEAD
        ...
            now += FORWARD_LATENCY_PER_TOKEN * len(window) / 16 + BATCH_OVERHEAD

# simulate_continuous
        dt = (prefill_work * PREFILL_LATENCY_PER_TOKEN
              + batch_tokens * FORWARD_LATENCY_PER_TOKEN
              + BATCH_OVERHEAD)
```

**Q10.** 阅读 `simulate_continuous` 开头：

```python
    while waiting or running:
        if waiting and running and now < waiting[0].arrived_at and not running:
            now = waiting[0].arrived_at
        while waiting and waiting[0].arrived_at <= now:
            r = waiting[0]
            if blocks_used + r.blocks_needed() > KV_BLOCKS_AVAILABLE:
                break
            blocks_used += r.blocks_needed()
            running.append(waiting.popleft())
```

1. 第一个 `if` 什么时候为真？
2. `blocks_needed()` 预留的是什么？这更像 PagedAttention 还是经典连续分配？真实 vLLM 怎么做？
3. KV 预算 1800 个 block（每 block 16 token）最多能同时容纳几个"8192 prompt + 300 输出"的请求？插桩显示 RUNNING 最多 16 个、准入被 KV 预算拦截近千次，这说明什么？

**Q11.**（讲义练习 4）1,000 个请求的输出长度服从均值 1,500、标准差 600 的正态分布（截断为 ≥1）。分别计算：（a）每个请求按 8192 上限连续预留，（b）PagedAttention 16-token block 时的 KV 浪费比例。

**Q12.**（讲义练习 2）给玩具调度器加上 `max_num_batched_tokens`（每次前向最多处理多少 token，包括 decode 的 1 token 和 prefill 块）。写出核心修改，并说明它与本代码"每个请求各自最多取 512"的 chunking 有何不同。

---

## 四、面试高频题

**Q13.**（基础必考）解释 PagedAttention、continuous batching、chunked prefill 分别解决什么问题，以及三者为什么"互相依赖"。

**Q14.**（原理深挖）为什么 prefill 是 compute-bound、decode 是 memory-bound？这对 batch 调度意味着什么？为什么 chunked prefill 能降低 P99 ITL，却不能单独提升吞吐？

**Q15.**（工程实践）线上 vLLM 服务报告：P99 ITL 偶发 300ms 尖峰、TTFT 均值正常、WAITING 队列不长。你会怀疑哪个默认机制出了问题？怎样调参并验证？

**Q16.**（场景设计）你要在一台 H100 上为 Llama 3.3 70B FP8 服务长文档问答（prompt 平均 16k token）和聊天（prompt 平均 500 token）两类流量，SLO 是聊天 P99 ITL < 30ms。说明你的调度配置与容量估算思路。

**Q17.**（追问型）KV cache 满了以后 vLLM 会怎样？抢占（preemption）有哪几种方式？为什么"提前知道输出长度"在真实系统里不成立？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："static batching — pads every request to the longest prompt in the window, pads every decode to the longest expected output, and stalls the whole batch on the slowest sequence." A、C、D 都是原文列出的问题。B 是捏造的：一个 serving 进程只加载一份权重，batch 内所有请求共享它，这正是批处理能提升效率的原因。

### Q2 — 答案：D

讲义："It is allocated in fixed-size blocks (default 16 tokens). Each sequence has a block table that maps its logical token positions to physical block IDs." 浪费只发生在每个序列最后一个未填满的 block（平均约 8 个 token）。A 是 KV 量化，B 是 KV 卸载（阶段 17 · 18 的 LMCache 方向），都不是 PagedAttention 本身；C 恰好是 PagedAttention 要取代的经典做法。

### Q3 — 答案：A

讲义："The key invariant: the scheduler runs once per decode iteration, not once per request." B 是讲义所说旧的 "dynamic batching"（等窗口凑满）；C、D 是静态批处理的特征。

### Q4 — 答案：C

讲义学习目标："name which latency metric it protects (hint: it is TTFT tail, not mean throughput)"；正文："P99 ITL under mixed load drops from ~50 ms to ~15 ms"。本节代码也印证：开启 chunking 后吞吐几乎不变，P99 ITL 从 219.3ms 降到 66.1ms。A 正是讲义特意排除的答案；D 是 PagedAttention 的作用。

### Q5 — 答案：D

`80 层 × 2（K、V）× 8 KV 头 × 128 × 2 字节 = 327,680 字节/token`，× 8192 = 2,684,354,560 字节 ≈ **2.68 GB**（2.5 GiB）。讲义写的是"roughly 1.25 GB per sequence in BF16"，大约是正确值的一半，可能漏掉了 K/V 的 2 倍，或对应的是 FP8 KV cache——这是讲义的一处数值问题。C（21.5 GB）是错用 64 个查询头计算的结果（高估 8 倍），A 是 1500 token 而非 8192 token 的量级（`327,680 × 1,024 ≈ 0.34 GB`，对应约 1k token）。讲义"82% 浪费"的结论不受影响：`1 − 1500/8192 ≈ 81.7%`。

### Q6 — 答案：A

实际运行结果如题干 Q9 所示：STATIC 4055 tok/s 遥遥领先，CONTINUOUS 886、CONTINUOUS + CHUNKED 885、NAIVE 768。B 是讲义期望的结果，但代码的成本模型给了 STATIC 不公平的折扣（见 Q9）。

### Q7 — 答案：C

chunking 不改变总工作量（每个 prompt token 仍要 prefill 一次，每个输出 token 仍要 decode 一次），所以吞吐几乎不变；它改变的是工作在时间上的分布：每个迭代里一个请求最多 prefill 512 token，decode 序列不会被一次 8192 token 的 prefill 卡住 0.33 秒。D 错：拆分会多几次 `BATCH_OVERHEAD`（0.2ms），但远小于被消除的尖峰。

### Q8 — 答案：B

讲义："You do not enable PagedAttention with a flag — it is the only allocator vLLM ships. The knob is `--gpu-memory-utilization` (default 0.9)…" A 错，PagedAttention 没有开关；C 错，chunk 大小由 `--max-num-batched-tokens` 等参数控制；D 混淆了阶段 17 · 03 的 DCGM duty cycle 与显存比例。skill 还规定：该值低于 0.7 时应先提高它，再调其他调度参数。

### Q9 — 参考答案

1. **STATIC 的 prefill 只按一个 prompt 计费**：`pad_prompt * PREFILL_LATENCY_PER_TOKEN`，16 个请求填充到同一长度后，实际要计算 `16 × pad_prompt` 个 token，代码只收了 1/16。CONTINUOUS 的 `prefill_work` 却把每个 prompt 的每个 token 都计入。仅这一项：60 个请求的真实 prompt 共 141,184 token，CONTINUOUS 要花约 5.6 秒做 prefill；STATIC 4 个批次合计只收约 1.3 秒。
2. **STATIC 的 decode 有 1/16 的批处理折扣**：`FORWARD_LATENCY_PER_TOKEN * len(window) / 16`，16 个序列一步 decode 只要 `0.5 + 0.2 = 0.7ms`；CONTINUOUS 是 `batch_tokens × 0.5ms`，16 个序列要 8.2ms——continuous 模式里**批处理完全没有摊薄效果**，这与"decode 是 memory-bound、一次读权重服务整个 batch"的事实相反。
3. **STATIC 不受 KV 预算约束**：CONTINUOUS 受 `KV_BLOCKS_AVAILABLE = 1800` 限制，而 STATIC 每批按填充后长度需要 8,496、8,480、8,464、6,372 个 block，远超 1800。STATIC 在一个"放不下"的显存里运行。
4. （次要）STATIC 的填充浪费在代码里完全没有代价：按填充计算，4 个批次共占 508,416 个 token 槽位，真实只有 150,603 个，**70.4% 是填充**——这恰恰是讲义说的"为从不使用的 padding 付费"。

修正验证（已实际运行）：只把 STATIC 的 prefill 改为 `pad_prompt × len(window)`，STATIC 吞吐降到 456 tok/s、平均 TTFT 12.2 秒；prefill 和 decode 都改成与 CONTINUOUS 相同的线性成本，STATIC 为 329 tok/s、TTFT 15.2 秒——此时 CONTINUOUS（886）明显领先，与讲义结论一致。反过来，若给 CONTINUOUS 的 decode 也加上同样的 `/16` 摊薄，CONTINUOUS 吞吐升到约 1,510 tok/s、TTFT 约 2.8 秒，chunked 版 P99 ITL 61.8ms（无 chunk 267.5ms）。结论：**玩具模拟的对比结果完全由成本模型决定**，两种模式必须用同一套成本函数。

### Q10 — 参考答案

1. 永远不会为真：条件同时要求 `running` 为真和 `not running` 为真，是死代码。真正处理"没有运行中的请求时快进到下一个到达时间"的是后面的 `if not running: ... now = waiting[0].arrived_at; continue`。
2. `blocks_needed()` = `ceil((prompt_len + output_len) / 16)`，在**准入时一次性预留整个生命周期**的 block，且预先知道输出长度。这更接近"按实际长度预留的连续分配"，而不是 PagedAttention。真实 vLLM 只在准入时为 prompt 分配 block，decode 过程中每满 16 个 token 再追加一个 block；block 不够时抢占（preempt）部分序列。真实系统也无法提前知道输出长度（取决于 EOS）。
3. 一个这样的请求需要 `ceil(8492 / 16) = 531` 个 block，`1800 // 531 = 3`，最多同时 3 个。插桩：RUNNING 最多 16 个序列（短请求多时），准入因 KV 不足被拦截 987 次（chunked 版 1049 次），`blocks_used` 峰值 1796/1800。说明玩具模型是 **KV 受限**的：长 prompt 一来，大量请求只能在 WAITING 里排队，这也是 CONTINUOUS 平均 TTFT 高达 4.6 秒的主要原因之一。真实系统中这正是 `--gpu-memory-utilization`、KV 量化、prefix caching 发挥作用的地方。

### Q11 — 参考答案

用 `random.Random(0)` 生成 1,000 个 `max(1, int(gauss(1500, 600)))` 样本（实际均值 1,510.5）计算：

- （a）连续预留：总槽位 `1000 × 8192`，浪费 `1 − 实际用量 / 总槽位 ≈ 81.6%`。与讲义"平均 1500 token 时浪费约 82%"一致。
- （b）PagedAttention：每个请求分配 `ceil(x / 16) × 16` 个槽位，只有最后一个 block 有空位，平均约 7.5 token，浪费 ≈ **0.5%**。

讲义说生产负荷下碎片 < 4%，额外来源包括：prompt 部分同样有尾 block、block 表与元数据开销、为未来增长预留的 block、并发序列数变化导致的瞬时空闲。

```python
import math, random
rng = random.Random(0)
xs = [max(1, int(rng.gauss(1500, 600))) for _ in range(1000)]
used = sum(xs)
print(1 - used / (1000 * 8192))                                # ≈ 0.816
print(1 - used / sum(math.ceil(x / 16) * 16 for x in xs))      # ≈ 0.005
```

### Q12 — 参考答案

核心修改：在每个迭代里维护一个共享预算，先给所有 decode 序列各 1 token，剩余预算按 FCFS 分给 prefill 中的请求：

```python
MAX_NUM_BATCHED_TOKENS = 2048

        budget = MAX_NUM_BATCHED_TOKENS
        decoded = [r for r in running if not r.in_prefill]
        batch_tokens = min(len(decoded), budget)       # decode 优先，每个 1 token
        decoded = decoded[:batch_tokens]
        budget -= batch_tokens
        prefill_work = 0
        for r in running:
            if r.in_prefill and budget > 0:
                take = min(r.prompt_len - r.prefilled, budget, CHUNK_SIZE if chunked else budget)
                r.prefilled += take
                prefill_work += take
                budget -= take
                if r.prefilled >= r.prompt_len:
                    r.ttft = now + prefill_work * PREFILL_LATENCY_PER_TOKEN
```

已实际运行验证（chunked=True）：预算 512 → P99 ITL 26.7ms、吞吐 884 tok/s；预算 2048 → 66.6ms；预算 8192 → 66.1ms（与原版相同）。chunked=False 时预算 2048 → 87.2ms、8192 → 262.2ms。全局预算越小，ITL 尾部越低，而吞吐几乎不变（平均 TTFT 从约 4.59 秒略升到 4.71 秒）。

区别：本代码的 chunking 是**每个请求**最多取 512，若同时有 10 个请求在 prefill，一个迭代仍可能做 5,120 个 prefill token，decode 的 ITL 仍会被拉长；`max_num_batched_tokens` 是**每次前向的全局上限**，直接限制了一个迭代的最大耗时，从而给 ITL 一个确定的上界。取值的思路（讲义提示）：它取决于 KV block 大小和空闲 block 数，以及你愿意让一个迭代最多花多长时间（ITL 目标），而不是原始 HBM 容量；值太小则 prefill 很慢、TTFT 变差，太大则 ITL 尖峰回来。

### Q13 — 参考回答要点

- **PagedAttention**：解决 KV cache 内存碎片和过度预留。固定大小 block + block table，按需分配，碎片从 60–80% 降到 < 4%，同样显存能放下更多并发序列。
- **Continuous batching**：解决静态批处理的"填充 + 等最慢"。每个 decode 迭代都可以移除完成的序列、接纳新序列，batch 始终满载真实工作。
- **Chunked prefill**：解决长 prompt 的 prefill 独占一次前向、导致其他序列 decode 停顿。把 prefill 切成块与 decode 交错，保护 P99 ITL。
- **相互依赖**：continuous batching 需要细粒度的 KV 资源才能随时接纳新序列而不重排内存（PagedAttention 提供）；chunked prefill 是同一个调度循环在 `RUNNING` 列表上的又一个决策。调度器优化的是"在 KV block 预算下的 goodput"。
- 加分点：说出讲义数字——三者全开 2,200–2,400 tok/s vs 默认约 1,800 vs 朴素约 600（Llama 3.3 70B FP8、H100、128 并发）。

### Q14 — 参考回答要点

- **prefill**：一次处理几百到几万个 token，矩阵乘法规模大，算术强度高，GPU 算力是瓶颈。
- **decode**：每个序列每步只算 1 个 token，但要读一遍全部权重和该序列的 KV cache，算术强度低，显存带宽是瓶颈。因此把多个序列放进同一个 decode 步，读一次权重服务多个 token，几乎"免费"——这就是批处理的收益来源（本节代码的 CONTINUOUS 恰恰没有建模这一点）。
- **调度含义**：decode 应尽量大 batch；prefill 与 decode 混在一个前向里时，大块 prefill 会显著拉长这一步的时间，所有 decode 序列都被拖慢。
- **chunked prefill 与吞吐**：总计算量不变（每个 prompt token 仍算一次），所以单独看不提升吞吐；它降低的是单步最大耗时，即 ITL 尾部。实践中的吞吐收益来自：prefill 块可以"填满"decode 步中没用满的算力（decode 是 memory-bound，算力有富余），让 GPU 同时干两种活；以及因为 ITL 可控，可以放心提高并发而不违反 SLO（goodput 提升）。
- 常见误区：认为 chunking"让 prefill 更快"——单个长 prompt 的 TTFT 反而可能略增。

### Q15 — 参考回答要点

- **怀疑**：chunked prefill 未开启或块太大（`--max-num-batched-tokens` 过大），偶发的长 prompt 在一步里做完整个 prefill，造成 ITL 尖峰；WAITING 不长、TTFT 均值正常说明不是 KV 饥饿或准入问题。
- **验证**：把 ITL 尖峰的时间戳与长 prompt 请求的到达时间对齐；看每步 batched tokens 的分布。
- **调参**：开启 chunked prefill，逐步降低 `--max-num-batched-tokens`（如 8192 → 2048 → 512），观察 P99 ITL 与 TTFT 的权衡；同时检查与投机解码等特性的兼容性（skill 的 hard reject：开启 chunked prefill 前要检查 speculative config）。
- **备选**：长 prompt 很多时考虑 P/D 分离（阶段 17 · 17），把 prefill 移到专门的实例。
- 加分点：给出"what to measure next"——P99 ITL、每步 batched token 数、长 prompt 比例。

### Q16 — 参考回答要点

- **容量估算**：70B FP8 权重约 70GB，H100 80GB 显存在 `--gpu-memory-utilization 0.9` 下留给 KV 的空间只有几 GB；按 BF16 KV 每 token 约 320KB（GQA 8 KV 头），16k token 的长文档单序列约 5.4GB，单卡可能只能放下 1–2 个长请求。必须考虑 FP8 KV cache、TP=2 或拆分部署。
- **调度配置**：开启 chunked prefill，用较小的 `max_num_batched_tokens` 给每步耗时设上界，保证聊天的 ITL；按 FCFS 但给聊天更高优先级（或按 SLO 分队列）。
- **架构选项**：两类流量分到不同副本池（长文档池 + 聊天池），或使用 P/D 分离让长 prefill 不与聊天 decode 争抢；聊天 system prompt 可用 prefix caching（阶段 17 · 06）。
- **验证**：用混合流量压测，分流量类别统计 P99 ITL、TTFT 与 goodput。
- 常见误区：只看总吞吐 tok/s，不分流量类别看尾延迟。

### Q17 — 参考回答要点

- **KV 满了**：新请求留在 WAITING 队列；若运行中的序列需要新 block 而没有空闲 block，调度器会抢占部分序列（通常是最新加入、优先级低的）。
- **抢占方式**：recompute（丢弃其 KV block，之后重新 prefill，计算换内存）与 swap（把 KV block 换出到 CPU 内存，之后再换回，带宽换计算）。
- **不知道输出长度**：生成何时遇到 EOS 由模型决定，只有 `max_tokens` 上限是已知的；按上限预留就退化成经典连续分配的浪费，所以 PagedAttention 才按需追加 block。本节代码的 `blocks_needed()` 用了真实输出长度做一次性预留，是一个"开了天眼"的简化。
- 加分点：抢占会造成 TTFT/ITL 抖动，监控 block 分配率和抢占次数（skill 的"block allocation rate"）；降低抢占的方法有提高 `--gpu-memory-utilization`、KV 量化、限制最大并发序列数。

---

## 六、关联知识点

### 前置知识
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 的原理与显存公式。
- [阶段 10 · 12 Inference Optimization](../../../10-llms-from-scratch/12-inference-optimization/docs/zh.md)：prefill/decode 两阶段与批处理的基础。
- [阶段 17 · 01 托管 LLM 平台：Bedrock、Vertex AI、Azure OpenAI](../../01-managed-llm-platforms/docs/zh.md)：讲义列出的前置节（讲义写作 "Model Serving"）。

### 本节被哪些后续内容用到
- [阶段 17 · 05 生产环境中的 EAGLE-3 Speculative Decoding](../../05-eagle3-speculative-decoding/docs/zh.md)：在同一调度器上叠加投机解码，需核对兼容性。
- [阶段 17 · 06 前缀缓存服务：RadixAttention 与 KV 复用](../../06-sglang-radixattention/docs/zh.md)：在分页 KV 之上做跨请求复用。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：本节指标的精确定义与测量。
- [阶段 17 · 17 Prefill 与 Decode 分离：NVIDIA Dynamo 与 llm-d](../../17-disaggregated-prefill-decode/docs/zh.md)：把 prefill 与 decode 拆到不同实例。
- [阶段 17 · 18 生产服务技术栈：KV 卸载与缓存感知路由](../../18-vllm-production-stack-lmcache/docs/zh.md)：KV block 卸载到 CPU/存储。
- [阶段 17 · 28 自托管服务选型：让引擎匹配硬件与规模](../../28-self-hosted-serving-selection/docs/zh.md)：vLLM 与其他引擎的选型。

### 延伸关键词
`PagedAttention` · `block table` · `KV block size` · `continuous batching / iteration-level scheduling` · `V1 scheduler` · `chunked prefill` · `max_num_batched_tokens` · `gpu_memory_utilization` · `preemption (recompute / swap)` · `GQA` · `TTFT / ITL / goodput` · `compute-bound vs memory-bound`
