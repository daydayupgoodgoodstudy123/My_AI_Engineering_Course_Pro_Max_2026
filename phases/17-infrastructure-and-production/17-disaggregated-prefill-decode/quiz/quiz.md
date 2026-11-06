# 测验 · Prefill 与 Decode 分离：NVIDIA Dynamo 与 llm-d（Disaggregated Prefill/Decode — NVIDIA Dynamo and llm-d）

> **阶段 17 · 基础设施与生产 · 第 17 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两阶段瓶颈不同 | prefill 一次前向处理整段 prompt，矩阵乘法主导，是 compute-bound；decode 每步只出一个 token、却要把全部权重读一遍，是 memory-bandwidth-bound |
| 2 | 同机部署（colocated）的浪费 | 同一组 GPU 既跑 prefill 又跑 decode，只能按两者的"最坏情况"过量配置；讲义估计 20–40% 的 GPU 时间花在了"错的资源"上 |
| 3 | 分离式架构（disaggregated serving） | Router → Prefill pool（算力型）→ 通过 NIXL 传 KV cache → Decode pool（显存型）→ 流式返回 token |
| 4 | NIXL | NVIDIA 的节点间 KV 传输层：有 RDMA/InfiniBand 就走 RDMA，否则退回 TCP；传输时延是真实成本（"transfer tax"） |
| 5 | 何时不该分离 | 讲义：prompt < 512 token 且输出 < 200 token、集群 < 4 张 GPU、没有 RDMA、团队运维不了两个池子 |
| 6 | NVIDIA Dynamo | "stack-above" 编排层，架在 vLLM / SGLang / TRT-LLM 之上；Planner Profiler 测量负载，SLA Planner 自动调 prefill:decode 比例；Rust 内核 + Python 扩展 |
| 7 | llm-d | Red Hat + AWS 的 Kubernetes 原生方案：prefill / decode / router 是独立 Service，各自 HPA（prefill 看队列深度、decode 看 KV 利用率），`packDomain: rack` 把同一组 prefill+decode 打包到同一机架 |
| 8 | 与 cache-aware 路由叠加 | 路由器先找"已持有该前缀 KV"的 decode 节点，命中就跳过 prefill；未命中才走 prefill → decode，两种优化相互放大 |
| 9 | 数字要带出处 | 讲义：6x（DeepSeek-R1 / GB200 NVL72 + Dynamo，NVIDIA 2025-06）有一手来源；"30x"只是社区汇总；50x 来自产品页；$2M → 省 $600–800K 是内部综合估算 |
| 10 | 本节代码的结论有问题 | 模拟器里分离式在**所有** 8 个 case 都胜出，且越长的 prompt 反而让分离式越吃亏——与打印的 "Read:" 结论方向相反（见第三部分） |

### 核心技能（能动手做到）

- [ ] 用一句话说清 prefill 为什么是 compute-bound、decode 为什么是 memory-bound，并能推出"同机部署会浪费哪种资源"
- [ ] 画出分离式架构图（router、prefill pool、NIXL、decode pool），说明每个箭头上传的是什么
- [ ] 按 `KV 字节/token × prompt 长度 ÷ 带宽` 手算一次 KV 传输时延，并对照 SLA 判断是否可接受
- [ ] 读懂 `ms_colocated` / `ms_disaggregated`，推出两者的盈亏平衡条件（prompt/output 比值）
- [ ] 按"层数 × KV 头数 × head_dim × 2 × 字节数"算出 70B 模型每 token 的 KV 大小，并发现代码常数的简化
- [ ] 针对给定集群和团队情况，在 Dynamo 与 llm-d 之间做出有理由的选择
- [ ] 识别讲义里哪些数字有一手来源、哪些只是方向性说法

---

## 二、基础自测（选择题）

**Q1.** 讲义认为 prefill 与 decode 应该放到不同 GPU 池的根本原因是：

- A. prefill 是 compute-bound（矩阵乘法吞吐），decode 是 memory-bound（HBM 带宽），放在一起总有一种资源被浪费
- B. prefill 和 decode 使用不同的模型权重，必须分开加载
- C. decode 需要的网络带宽比 prefill 大得多
- D. prefill 只能在 FP8 下运行，decode 只能在 FP16 下运行

**Q2.** 在 Dynamo 的分离式架构里，KV cache 从 prefill pool 传到 decode pool 用的是：

- A. 经由共享 NFS 文件系统落盘再读取
- B. gRPC 双向流
- C. NIXL：有 RDMA/InfiniBand 时走 RDMA，否则退回 TCP
- D. 普通 HTTP POST

**Q3.** 按讲义"When NOT to disaggregate"一节，下列哪种情形**最不适合**做 prefill/decode 分离？

- A. RAG 服务，P99 前缀 8K token，输出 300 token
- B. GB300 NVL72 上的 MoE 模型推理
- C. 多租户服务，共享长 system prompt，且有 RDMA 网络
- D. 一个只有 2 张 GPU 的小集群，请求大多是 300 token prompt、100 token 输出

**Q4.** 关于 NVIDIA Dynamo 与 llm-d，说法正确的是：

- A. Dynamo 只能运行在 AMD GPU 上，llm-d 只能运行在 NVIDIA GPU 上
- B. Dynamo 是架在 vLLM/SGLang/TRT-LLM 之上的编排层；llm-d 是 Kubernetes 原生方案，把 prefill/decode/router 做成独立 Service 并分别扩缩容
- C. 两者都只是推理引擎，需要再配一个 Dynamo 才能工作
- D. llm-d 用 Planner Profiler 自动调 prefill:decode 比例，Dynamo 没有这个能力

**Q5.** 按本节 `code/main.py` 的常数（`KV_BYTES_PER_TOKEN_70B_FP8 = 125_000`，`NIXL_RDMA_GB_S = 100`），一个 4096 token 的 prompt，其 KV 经 RDMA 传输需要多少毫秒？

- A. 0.512 ms
- B. 51.2 ms
- C. 5.12 ms
- D. 512 ms

**Q6.** 运行 `code/main.py`，最后一列 `Winner` 的实际结果是：

- A. 8 个 case 全部是 `disaggregated`，连 prompt 256 / output 100 也是
- B. prompt ≤ 512 时是 `colocated`，更长时是 `disaggregated`
- C. prompt ≤ 2048 时是 `colocated`，更长时是 `disaggregated`
- D. 8 个 case 全部是 `colocated`

**Q7.** llm-d 为 prefill 与 decode 两类 Service 分别配置 HPA。讲义给出的扩缩容信号是：

- A. 两者都看 GPU 利用率
- B. prefill 看 KV 利用率，decode 看队列深度
- C. 两者都看请求 QPS
- D. prefill 看队列深度，decode 看 KV 利用率

**Q8.** 关于讲义里的吞吐数字，哪种引用方式最符合讲义自己的说明？

- A. "Dynamo 让任何模型吞吐提高 30 倍"，这是 NVIDIA 官方数字
- B. "DeepSeek-R1 在 GB200 NVL72 + Dynamo 的中等时延区间约 6x（NVIDIA 2025-06）；'30x' 是社区汇总、没有单一一手来源，只能当方向性说法"
- C. "$2M 推理开销节省 $600–800K"是某个公开发表的单一客户案例
- D. "GB300 + Dynamo 比 Hopper 快 50 倍"适用于所有 dense 模型

---

## 三、动手 / 代码题

**Q9.** 本节代码的两个核心函数：

```python
def ms_colocated(prompt: int, output: int) -> float:
    prefill_ms = prompt / PREFILL_TOK_PER_MS
    decode_ms = output / DECODE_TOK_PER_MS_COLOCATED
    return prefill_ms + decode_ms


def ms_disaggregated(prompt: int, output: int, use_rdma: bool = True) -> float:
    prefill_ms = prompt / PREFILL_TOK_PER_MS
    kv_bytes = prompt * KV_BYTES_PER_TOKEN_70B_FP8
    transport = NIXL_RDMA_GB_S if use_rdma else NIXL_TCP_GB_S
    transfer_ms = (kv_bytes / 1e9) / transport * 1000
    decode_ms = output / DECODE_TOK_PER_MS_DECODE_GPU
    return prefill_ms + transfer_ms + decode_ms
```

1. 推导"分离式比同机部署更慢"的条件，写成 `prompt / output > 某个常数` 的形式，分别给出 RDMA 与 TCP 下的常数。
2. 代码最后打印 "disaggregation wins at longer prompts ... TCP transport raises the break-even"。根据你的推导，这句话的方向对吗？
3. 举一个让 TCP 分离式输给同机部署的具体 `(prompt, output)`，并给出三者的毫秒数。

**Q10.** 观察代码中的常数 `DECODE_TOK_PER_MS_COLOCATED = 0.10`、`DECODE_TOK_PER_MS_DECODE_GPU = 0.18`（注释："memory-optimized pool (H200-like)"）。

1. 如果 decode pool 用的也是同样的 H100（即两个 decode 速度都取 0.10），`(4096, 500)` 这一行的 colocated 与 disagg RDMA 分别是多少？谁赢？
2. 这说明模拟器里"分离式胜出"实际来自什么？它漏掉了分离式在真实系统中最主要的收益来源是什么？
3. `Winner` 一列是怎么算的？TCP 列参与比较了吗？请把它改成"三选一"并输出最快的方案名。

**Q11.** KV cache 大小计算。Llama 3.x 70B 的结构是 80 层、64 个查询头、**8 个 KV 头**（GQA）、head_dim = 128。

1. 算出 FP8（1 字节）与 FP16（2 字节）下每 token 的 KV 字节数，与代码中的 `125_000` 对比。
2. 4096 token 的 KV 在 FP8 下有多大？按 100 GB/s 与 10 GB/s 各需多少毫秒？
3. 讲义练习 4 说"4K prefill ≈ 500 MB，RDMA 5 ms、TCP 50 ms"，而概念部分又说 NIXL 传 4K-token KV "typically 20–80 ms"。这两种说法如何调和？

**Q12.** 讲义"Use It"一节说 `main.py` 会"Reports throughput, cost per request, and the prompt-length crossover"。

1. 实际代码报告了这三项中的哪几项？
2. 设计一个最小改动：给每个方案加上"每请求 GPU 成本"。提示：同机方案占用 1 张 GPU 的全部时间；分离式方案 prefill 阶段占 prefill GPU、decode 阶段占 decode GPU，且 H200 类 GPU 单价更高。写出函数签名与公式即可。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 prefill/decode 分离（disaggregated serving）？为什么要这样做？它的代价是什么？

**Q14.**（原理深挖）同一张 GPU 上同时跑 prefill 和 decode，除了"资源类型不匹配"之外，还会对 TTFT 和 TPOT 造成什么干扰？分离式和 chunked prefill 分别怎么缓解？

**Q15.**（工程实践）你在评估是否给一个 70B 模型服务上分离式架构，你会收集哪些数据、算哪些数、用什么门槛做决定？

**Q16.**（场景设计）为一个 RAG 服务设计 prefill pool 与 decode pool：P99 前缀 8K token、输出约 300 token，集群有 InfiniBand。说明池子配比怎么定、路由怎么做、上线后看什么指标。

**Q17.**（追问型）面试官说："NVIDIA 说 Dynamo 能带来 30 倍吞吐，我们为什么不直接上？"你怎么回答？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Prefill is compute-bound; decode is memory-bound. Running both on the same GPU wastes one resource." prefill 一次前向处理整段 prompt，主要是大矩阵乘法，吃算力（讲义给的量级：H100 FP8 约 2000 TFLOPS）；decode 每步只出一个 token，却要读一遍全部权重和 KV，吃显存带宽（HBM3 约 3 TB/s）。

- B 错：两个阶段用的是同一套权重，分离式只是把它们放到不同 GPU 上各加载一份。
- C 错：真正需要网络带宽的是两池之间的 KV 传输，而不是 decode 本身。
- D 错：精度与阶段无关，两池都可以用 FP8。

### Q2 — 答案：C

讲义："NIXL is NVIDIA's inter-node transport. Uses RDMA/InfiniBand when available, TCP fallback otherwise." A/B/D 都不是讲义所述，且落盘或 HTTP 的时延远高于 RDMA，不适合在每个请求的关键路径上搬几百 MB 的 KV。

### Q3 — 答案：D

讲义列出的四种"不该分离"：短 prompt 短输出、集群 < 4 张 GPU、团队运维不了两个池子、没有 RDMA。D 同时命中"集群 < 4 GPU"和"prompt < 512、输出 < 200"两条。

- A 是讲义点名的受益场景（"prefill-heavy workloads (RAG with 8K+ prefixes) benefit more"）。
- B：讲义说 MoE on Blackwell "is where the real numbers are"，分离是"double win"。
- C：共享前缀 + RDMA，正好与 cache-aware 路由叠加。

### Q4 — 答案：B

讲义：Dynamo "Sits above vLLM, SGLang, TRT-LLM as an orchestrator"；llm-d "Prefill / decode / router as independent Kubernetes Services"，"Per-role HPA"。

- A 是编造的硬件绑定。
- C 错：Dynamo 本身就是编排层，llm-d 本身就是完整方案。
- D 把归属说反了：Planner Profiler / SLA Planner 是 Dynamo 的组件。

### Q5 — 答案：C

`4096 × 125,000 = 512,000,000 字节 = 0.512 GB`；`0.512 GB ÷ 100 GB/s = 0.00512 s = 5.12 ms`。这与讲义练习 4 的"RDMA 5 ms"一致。B（51.2 ms）是 TCP 10 GB/s 时的结果；A 少算了一个数量级；D 是把 MB 数当成了毫秒数。

### Q6 — 答案：A

实际运行结果（见代码讲解第 6 节）：8 行全部 `disaggregated`。例如 `256/100`：colocated 1006.4 ms，disagg RDMA 562.3 ms。原因是 decode pool 的速度被设定为 0.18 tok/ms，比同机的 0.10 快 80%，而 decode 时间在总时间中占绝对大头；KV 传输只有 0.32 ms（RDMA）或 3.2 ms（TCP），根本抵消不了。

这与讲义"短 prompt 不值得分离"的结论**矛盾**：模拟器从未出现 crossover。B、C 是讲义叙述"应该"出现的结果，但代码实际给不出来；D 恰好相反。

### Q7 — 答案：D

讲义："Per-role HPA with queue depth (prefill) / KV utilization (decode) signals." 道理：prefill 是算力型，排队的 prompt 越多说明算力不够；decode 是显存型，KV 槽位占满就会开始抢占/排队。B 把二者对调了；A、C 无法区分两类负载的瓶颈。

### Q8 — 答案：B

讲义反复强调："we have not found a single primary source stating exactly 30x, so treat it as a directional claim"；6x 有 NVIDIA 开发者博客（2025-06）出处。

- A 把"方向性说法"当成官方数字，且"任何模型"是过度推广。
- C 错：讲义明说"$2M→$600-800K figure is an internal composite, not a single published case study"。
- D 错：50x 是 MoE 吞吐、对比 Hopper，来自未注明日期的产品页，不能推广到 dense 模型。

### Q9 — 参考答案

1. **推导**：两式相减，prefill 项相同而抵消：

   `disagg − colo = prompt × t_xfer − output × (1/0.10 − 1/0.18)`

   其中 `1/0.10 − 1/0.18 = 10 − 5.556 = 4.444 ms/输出 token`；
   每个 prompt token 的传输时间 `t_xfer = 125,000 B ÷ 带宽`：RDMA 为 `0.00125 ms`，TCP 为 `0.0125 ms`。

   分离式更慢 ⇔ `prompt / output > 4.444 / t_xfer`：
   - RDMA：`prompt / output > 3,556`
   - TCP：`prompt / output > 356`

2. **方向反了**。在这个模型里，prompt 越长，传输税越大，分离式越**吃亏**；让分离式获利的是"输出长"（decode 越多，快 decode pool 的优势越大）。"TCP 抬高 break-even"在方向上也应理解为：TCP 让分离式在更**小**的 prompt/output 比值下就开始输。讲义所说"短 prompt 不值得分离"在真实系统里成立，是因为真实收益来自消除干扰、按瓶颈配比池子，而这些都没有被模拟。

3. 例：`(4096, 1)`（已实际运行）：colocated 112.4 ms，disagg RDMA 113.08 ms，disagg TCP 159.16 ms——两种分离式都输了。再如 `(2048, 1)`：colocated 61.2，RDMA 59.32，TCP 82.36——只有 TCP 输。也就是说只有在"长 prompt、几乎没有输出"（如打分、分类、embedding 类请求）时才会出现 crossover。

### Q10 — 参考答案

1. 两个 decode 速度都取 0.10 时：colocated 仍是 `102.4 + 5000 = 5102.4 ms`；disagg RDMA 为 `102.4 + 5.12 + 5000 = 5107.52 ms`。**同机部署赢**，而且对任何输入都赢——分离式只多出了一段传输时间。
2. 模拟器里"分离式胜出"完全来自**换了更快的 decode 硬件**（0.18 vs 0.10），而不是来自"分离"这一架构本身——这等价于把硬件升级的收益记到了分离式头上。它漏掉了真实系统中分离式的主要收益来源：
   - 消除 prefill 与 decode 在同一批次里的**相互干扰**（长 prompt 的 prefill 会卡住正在 decode 的请求，拉高 ITL/TPOT）；
   - 两个池子**独立按瓶颈配比和扩缩容**（讲义的"right-sizing each pool"），从而提高 goodput；
   - 并发与批处理效率：代码只算单个请求的串行时延，没有队列、没有 batch、没有 GPU 数量。
3. `winner = "colocated" if colo < rdma else "disaggregated"`——只比较了 colocated 与 RDMA，**TCP 列只打印、不参与判定**。三选一可以写成：

```python
options = {"colocated": colo, "disagg-RDMA": rdma, "disagg-TCP": tcp}
winner = min(options, key=options.get)
```

### Q11 — 参考答案

1. 每 token KV = `2（K、V）× 80 层 × 8 个 KV 头 × 128 维 × 字节数`：
   - FP8：`163,840` 字节/token；
   - FP16：`327,680` 字节/token。
   代码的 `125,000` 比真实 FP8 值低约 24%（是一个"示意常数"）。注意这里用的是 **KV 头数 8** 而不是查询头数 64；若误用 64 会高估 8 倍（1,310,720 字节/token）。
2. 4096 token × 163,840 = `671,088,640` 字节 ≈ **671 MB**（代码常数给出 512 MB）。100 GB/s：约 **6.7 ms**；10 GB/s：约 **67 ms**。
3. 练习 4 是"纯带宽"估算：数据量 ÷ 链路带宽。概念部分的 20–80 ms 是"typically"的实际端到端时延，包含了 KV 块的收集/打包、注册内存、跨节点协议开销、与 decode 侧的调度对齐，以及链路达不到满带宽等因素；而且 TCP 在真实网络里往往远达不到 10 GB/s（80 Gbps）。两种说法量级上可以并存，但讲义没有说明二者的差别，读者容易混淆。做 SLA 评估时应以**实测的 KV 传输 P99** 为准（这也是本节 skill 文件最后指定的唯一验证指标）。

### Q12 — 参考答案

1. 只报告了**每请求时延**（colocated / RDMA / TCP 三列）和一个 `Winner`。没有吞吐，没有成本，也没有真正的 crossover（见 Q6、Q9）。讲义描述与代码不符。
2. 一个最小设计：

```python
GPU_PRICE_PER_HOUR = {"H100": 2.5, "H200": 3.5}   # 示意价格

def cost_colocated(prompt, output, price=GPU_PRICE_PER_HOUR["H100"]):
    return ms_colocated(prompt, output) / 3_600_000 * price

def cost_disaggregated(prompt, output, use_rdma=True,
                       p_price=GPU_PRICE_PER_HOUR["H100"],
                       d_price=GPU_PRICE_PER_HOUR["H200"]):
    prefill_ms = prompt / PREFILL_TOK_PER_MS
    total_ms = ms_disaggregated(prompt, output, use_rdma)
    decode_side_ms = total_ms - prefill_ms          # 传输 + decode 期间占用 decode GPU
    return (prefill_ms * p_price + decode_side_ms * d_price) / 3_600_000
```

   更真实的做法是引入**批大小**：decode 时 GPU 同时服务 B 个请求，单请求成本要除以 B；而 decode 的 B 受 KV 显存限制（这正是 H200 显存大的价值所在）。这样才能体现讲义"按瓶颈选硬件"的论点。

### Q13 — 参考回答要点

- **定义**：把推理的两个阶段放到不同的 GPU 池——prefill pool 只负责处理 prompt、生成 KV cache；decode pool 接收 KV 后逐 token 生成。中间用高带宽互连（NIXL：RDMA/InfiniBand，退回 TCP）传 KV。
- **为什么**：
  - 瓶颈不同：prefill compute-bound，decode memory-bandwidth-bound；同机部署只能双向过量配置（讲义：20–40% GPU 时间被浪费）。
  - 可以为两池选不同硬件（prefill 用算力型，decode 用大显存/高带宽型或更激进的量化）、不同并行策略、独立扩缩容。
  - 消除两阶段在同一批次里的互相干扰，TTFT 与 TPOT 可以分别优化。
- **代价**：
  - KV 传输税（4K token 70B 量级几毫秒到几十毫秒）；
  - 两个池子的运维复杂度（配比、扩缩容、拓扑）；
  - 依赖 RDMA 和机架拓扑；短请求反而更慢。
- 加分点：说出 Dynamo（stack-above）与 llm-d（K8s 原生）两条落地路线；提到配比应由测量决定（Dynamo Planner Profiler / SLA Planner）。

### Q14 — 参考回答要点

- **干扰**：continuous batching 下，一个长 prompt 的 prefill 进入批次，会让这一步的耗时暴涨，正在 decode 的其它请求这一步也得等——表现为 ITL/TPOT 尖刺；反过来，大量 decode 请求占着 KV 槽位，新的 prefill 要排队，TTFT 上升。
- **chunked prefill**（阶段 17 · 04）：把长 prompt 切成小块，与 decode 交错执行，限制单步耗时，缓解 decode 被卡住；但两阶段仍共享同一 GPU 的算力与显存，只是"平滑"而非"隔离"。
- **分离式**：物理隔离，prefill 再长也不影响 decode pool 的 TPOT；代价是 KV 传输和两池运维。
- 加分点：指出这正是本节模拟器没有建模的部分——它只算单请求串行时延，没有批次和干扰；指标上应同时看 TTFT P99 与 TPOT P99（阶段 17 · 08 的 goodput 概念）。

### Q15 — 参考回答要点

- **负载画像**：prompt 长度和输出长度的分布（P50/P99）、并发、前缀复用率。讲义门槛：prompt > 512 且输出 > 200 才考虑。
- **当前效率**：同机部署下的 GPU 利用率、TTFT/TPOT P99、因 prefill 干扰导致的 TPOT 尖刺频率、goodput。
- **传输成本**：按"层数 × KV 头 × head_dim × 2 × 字节数 × prompt P99"算 KV 大小，再除以实测链路带宽；与 TTFT SLA 预算对比（是否吃掉过多预算）。
- **集群与团队**：GPU 数量是否 ≥ 4，是否有 RDMA/IB，能否做到同机架打包；团队能否运维两池（否则倾向 Dynamo 这类托管编排）。
- **收益估算**：用 profiler 求两池配比，估算在同等 P99 SLA 下需要的 GPU 数；讲义锚点为同等 SLA 下省 30–40%（内部综合数，只作量级参考）。
- **决策与验证**：小流量灰度（见阶段 17 · 20），以 KV 传输 P99 和 TPOT P99 为门禁。
- 常见误区：用模拟器或厂商峰值数字直接下结论；忘了 GQA，用查询头数算 KV。

### Q16 — 参考回答要点

- **负载特征**：8K 前缀、300 输出，是典型的 prefill-heavy 场景，讲义认为这类负载受益最大。
- **配比**：先用 profiler 测单卡 prefill 吞吐（token/s）与 decode 在目标 TPOT 下能承载的并发数，再按 `所需 prefill GPU = 到达率 × 平均 prompt token ÷ 单卡 prefill 吞吐`、`所需 decode GPU = 并发请求数 ÷ 单卡可承载并发` 计算；skill 文件给的经验起点是 RAG-heavy 约 2 prefill : 1 decode，然后由 SLA Planner 或 HPA 动态调整。
- **KV 传输**：8K × 163,840 B ≈ 1.34 GB/请求（FP8）；IB 100 GB/s 下约 13 ms，可接受；必须把 prefill 与 decode 打包在同一机架（llm-d 的 `packDomain: rack`）。
- **路由**：cache-aware 路由在前（阶段 17 · 11）——RAG 的文档块和 system prompt 经常重复，命中前缀可以直接跳过 prefill，与分离式叠加。
- **指标**：TTFT P99（含传输）、TPOT P99、KV 传输 P99、两池各自利用率与队列深度、前缀命中率、单位请求成本。
- 加分点：考虑 KV 卸载层（下一节的 LMCache）承接传输后未被用到的 KV。

### Q17 — 参考回答要点

- **先核实出处**：讲义明确写"30x"没有单一一手来源，是社区对"全栈 Blackwell + Dynamo + DeepSeek-R1"报告的汇总；NVIDIA 博客有据可查的是 DeepSeek-R1 在 GB200 NVL72 上中等时延区间约 6x；50x 是产品页上 GB300 vs Hopper 的 MoE 吞吐。
- **条件不可迁移**：这些数字叠加了新硬件（Blackwell）、MoE 模型、特定时延区间和全栈优化，不能直接套到"我们的 dense 70B + H100"上。
- **我们自己的条件**：prompt/输出长度分布是否过门槛、有没有 RDMA、GPU 数量、团队运维能力。
- **怎么做决定**：在自己的负载上做 A/B 压测或 shadow，对比同等 P99 SLA 下的 GPU 数与成本；数字要定期复核（讲义："Benchmark numbers drift ... Re-check before quoting"）。
- 加分点：指出连本课程自带的模拟器都存在"把硬件升级算作分离收益"的问题，说明任何"倍数"都要拆解来源。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：理解同机部署时 prefill 与 decode 如何共享批次并互相干扰。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：分离式要优化的正是这些指标。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 的大小与生成方式。
- [阶段 10 · 12 Inference Optimization](../../../10-llms-from-scratch/12-inference-optimization/docs/zh.md)：prefill/decode 两阶段的算力与带宽分析。
- [阶段 07 · 11 专家混合 (MoE)](../../../07-transformers-deep-dive/11-mixture-of-experts/docs/zh.md)：讲义说 MoE 是分离式收益最大的场景。

### 本节被哪些后续内容用到
- [阶段 17 · 11 多区域 LLM 服务与 KV Cache 局部性](../../11-multi-region-kv-locality/docs/zh.md)：cache-aware 路由与分离式叠加。
- [阶段 17 · 18 生产服务技术栈：KV 卸载与缓存感知路由](../../18-vllm-production-stack-lmcache/docs/zh.md)：传输后的 KV 落入 LMCache 供后续复用。
- [阶段 17 · 03 Kubernetes 上的 GPU Autoscaling](../../03-gpu-autoscaling-kubernetes/docs/zh.md)：llm-d 按角色扩缩容依赖的 K8s 调度基础。
- [阶段 17 · 28 自托管服务选型：让引擎匹配硬件与规模](../../28-self-hosted-serving-selection/docs/zh.md)：何时值得引入分离式这类复杂架构。
- [阶段 17 · 27 LLMs 的 FinOps](../../27-finops-llms/docs/zh.md)：分离式的节省最终要落到单位经济性上。

### 延伸关键词
`disaggregated serving` · `NIXL` · `RDMA / InfiniBand` · `NVIDIA Dynamo` · `llm-d` · `SLA Planner` · `chunked prefill` · `prefill-decode interference` · `GQA` · `KV transfer tax` · `packDomain: rack` · `goodput` · `DistServe / Splitwise`
