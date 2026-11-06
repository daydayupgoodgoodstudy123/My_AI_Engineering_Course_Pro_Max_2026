# 测验 · Kubernetes 上的 GPU Autoscaling：Karpenter、KAI Scheduler 与成组调度（GPU Autoscaling on Kubernetes — Karpenter, KAI Scheduler, Gang Scheduling）

> **阶段 17 · 基础设施与生产 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 说明：中文讲义为机器翻译，Karpenter 被译成"卡彭特"、gang scheduling 被译成"帮派日程安排"、HPA 被译成"香港邮政局"等，请以英文版为准。本节代码的实际运行结果与讲义结论**相反**（见 Q9），这是本测验的重点之一。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 三层 autoscaling | 节点供给（Karpenter）、成组/拓扑调度（KAI Scheduler）、应用层副本伸缩（NVIDIA Dynamo Planner、llm-d Workload Variant Autoscaler） |
| 2 | Karpenter vs Cluster Autoscaler | Karpenter 监听 Pending pod、按 `NodePool` 约束直接选实例类型，GPU 节点约 45–60s；Cluster Autoscaler 基于节点组扩容，约 90–120s |
| 3 | 合并（consolidation）陷阱 | 默认 `consolidationPolicy: WhenEmptyOrUnderutilized` 会终止正在推理的 GPU 节点、换更便宜的实例，导致请求被驱逐 + 70B 权重重新加载；GPU 池用 `WhenEmpty` + `consolidateAfter: 1h` |
| 4 | Gang scheduling | 多 GPU 任务"要么全部启动，要么都不启动"，避免"8 卡只拿到 7 卡、7 卡空等烧钱"的部分分配陷阱 |
| 5 | Topology awareness | 知道哪些 GPU 共享 NVLink、同机架、有 InfiniBand；tensor-parallel 工作负载必须留在一个 NVLink 域内 |
| 6 | Hierarchical queues | 多团队共享 GPU 池时的优先级、配额与抢占规则 |
| 7 | `DCGM_FI_DEV_GPU_UTIL` 陷阱 | 它是 duty cycle（采样时刻 GPU 是否在干活），100% 既可能是 10 个并发也可能是 100 个，不能反映积压量 |
| 8 | 显存信号也不行 | vLLM 按 `--gpu-memory-utilization` 预分配 KV cache，1 个请求时显存也在 90% 左右，基于显存的 HPA 永远不会缩容 |
| 9 | 正确的信号 | 队列深度（等待 prefill 的请求数）、KV cache 利用率（已分配给活跃序列的 block 比例）、每副本 P99 TTFT、goodput |
| 10 | P/D 分离与冷启动 | prefill pod 按队列深度、decode pod 按 KV 压力分别伸缩，不要用一个 HPA 管两者；从零冷启动 = 节点 45–60s + 模型加载 + 引擎初始化，约 2–5 分钟，SLO 关键路径要留 warm pool |

### 核心技能（能动手做到）

- [ ] 画出三层 autoscaling 架构，并说出每层的工具和它解决的失败模式
- [ ] 写出 GPU 推理池安全的 Karpenter `NodePool`（capacity-type、taint、`WhenEmpty` + `consolidateAfter: 1h`）
- [ ] 解释为什么 duty cycle 与显存都不是 LLM serving 的好伸缩信号，并给出替代信号
- [ ] 读懂本节模拟器的离散时间循环，能指出它的建模假设（每 tick 每副本只服务 1 个请求、95s 冷启动、30s 超时）
- [ ] 用插桩/修改代码的方法解释"为什么模拟结果与讲义结论相反"
- [ ] 为 P/D 分离部署分别选择 prefill 与 decode 的伸缩信号

---

## 二、基础自测（选择题）

**Q1.** 讲义把 GPU autoscaling 拆成三层。下列"层—工具"对应**正确**的是：

- A. 节点供给：KAI Scheduler；成组调度：Karpenter；副本伸缩：Cluster Autoscaler
- B. 节点供给：HPA；成组调度：kube-scheduler；副本伸缩：Karpenter
- C. 节点供给：Karpenter；成组/拓扑调度：KAI Scheduler；副本伸缩：Dynamo Planner / llm-d WVA
- D. 三层都由 Karpenter 完成

**Q2.** 为什么讲义说 `DCGM_FI_DEV_GPU_UTIL` 不适合作为 vLLM 的 HPA 信号？

- A. 它是 duty cycle：只反映采样时 GPU 是否在工作，100% 可能对应 10 个并发也可能对应 100 个，无法反映积压
- B. 它只在 AMD GPU 上可用
- C. 它统计的是显存占用，vLLM 预分配后一直是 90%
- D. 它的采样周期是 1 小时，太慢

**Q3.** Karpenter 默认的 `WhenEmptyOrUnderutilized` 为什么对推理 GPU 池危险？

- A. 它会让节点永远不缩容，浪费钱
- B. 它会关闭 gang scheduling
- C. 它会把 GPU 节点换成 CPU 节点
- D. 它会终止仍在运行推理的 GPU 节点以迁移到更便宜的实例，驱逐进行中的请求并重新加载模型权重

**Q4.** 一个 70B 模型需要 8 张 GPU（跨 2 个节点）。集群有 7 张空闲 GPU，Cluster Autoscaler 为缺的 1 张新开节点，7 张卡空等 4 分钟。能**直接**避免这种情况的机制是：

- A. 把 HPA 的目标利用率调到 50%
- B. KAI Scheduler 的 gang scheduling（全有或全无）
- C. 增大 `--gpu-memory-utilization`
- D. 把 `consolidateAfter` 改成 10 分钟

**Q5.** 在 P/D 分离（disaggregated prefill/decode）部署中，讲义推荐的伸缩信号是：

- A. prefill pod 按队列深度、decode pod 按 KV cache 压力，各自独立的 per-role HPA
- B. 两类 pod 共用一个基于 `DCGM_FI_DEV_GPU_UTIL` 的 HPA
- C. prefill 按显存、decode 按 CPU
- D. 两类 pod 都按 P99 TTFT 用同一个 HPA

**Q6.** 运行本节 `code/main.py`（`seed=7`，743 个请求），三种策略的丢弃请求数分别是：

- A. DUTY_CYCLE 64、QUEUE_DEPTH 1、KAI_GANG 61
- B. DUTY_CYCLE 61、QUEUE_DEPTH 64、KAI_GANG 1
- C. 三者都是 0
- D. DUTY_CYCLE 1、QUEUE_DEPTH 64、KAI_GANG 61

**Q7.** 本节模拟器里 `KAI_GANG` 策略与 `QUEUE_DEPTH` 的**真实区别**是：

- A. KAI_GANG 真正模拟了 8 卡成组分配与 NVLink 拓扑
- B. 只是扩容阈值更低（队列 > 3 而非 > 5）、每次至少加 2 个副本；没有任何成组或拓扑逻辑
- C. KAI_GANG 使用 Cluster Autoscaler 的 110 秒供给时间
- D. KAI_GANG 每个副本占 8 张 GPU

**Q8.** 关于基于显存的 HPA，下列说法正确的是：

- A. 显存是最准确的 LLM 负载信号，应优先使用
- B. 显存只在 decode 阶段变化，适合 decode pod
- C. vLLM 按 `--gpu-memory-utilization` 预分配 KV cache，1 个请求时显存也接近 90%，这种 HPA 永远不会缩容
- D. 显存信号只有在开启 gang scheduling 后才有效

---

## 三、动手 / 代码题

**Q9.** 讲义练习 1 问"突发负载下 duty-cycle HPA 比 queue-depth HPA 多丢多少请求"，代码末尾也打印"DUTY_CYCLE drops requests because…"。但实际输出是：

```text
DUTY_CYCLE      reqs= 743  done= 742  dropped=  1  mean_wait=  7.5s  idle_gpu= 266.2min  peak=16
QUEUE_DEPTH     reqs= 743  done= 679  dropped= 64  mean_wait= 18.2s  idle_gpu=  49.5min  peak=16
KAI_GANG        reqs= 743  done= 682  dropped= 61  mean_wait= 15.4s  idle_gpu= 120.0min  peak=16
```

阅读下面的代码，解释为什么 DUTY_CYCLE 反而几乎不丢请求，以及它付出了什么代价：

```python
        if strategy == "DUTY_CYCLE":
            pending_ids = {rid for _, rid in pending_replicas}
            busy = sum(1 for rid, t in replica_available_at.items()
                       if t > now and rid not in pending_ids)
            util = busy / max(replicas_ready, 1) * 100
            if util > TARGET_GPU_UTIL and replicas_target < MAX_REPLICAS:
                replicas_target += 1
            elif util < 20 and replicas_target > MIN_WARM_REPLICAS:
                replicas_target -= 1
        elif strategy == "QUEUE_DEPTH":
            qd = len(queue)
            if qd > 5 and replicas_target < MAX_REPLICAS:
                replicas_target = min(MAX_REPLICAS, replicas_target + max(1, qd // 5))
            elif qd == 0 and replicas_target > MIN_WARM_REPLICAS:
                replicas_target = max(MIN_WARM_REPLICAS, replicas_target - 1)
```

**Q10.** 把 `util` 改成"真正的 duty cycle"——每个副本在 15 秒 tick 内实际忙碌的时间比例：

```python
util = busy * min(REQUEST_PREFILL_SEC + REQUEST_DECODE_SEC, HPA_TICK_SEC) / HPA_TICK_SEC / max(replicas_ready, 1) * 100
```

1. 这个 util 的最大值是多少？
2. 预测 DUTY_CYCLE 会怎样表现，丢弃多少请求？（实际运行结果见答案）
3. 这说明讲义所说的哪种失败模式？

**Q11.** 模拟器中每个空闲副本在每个 15 秒 tick 内只从队列取 **1 个**请求（服务时间 2.4 秒）。

1. 一个副本的理论服务能力与模拟中的实际服务能力分别是多少请求/秒？
2. 高峰期（600–1800 秒）到达率是多少？按模拟的服务能力需要几个副本？
3. 这个简化对三种策略的结论有什么影响？

**Q12.** 给 `QUEUE_DEPTH` 加一个缩容稳定窗口（连续 N 个 tick 队列为空才缩容 1 个副本），结果如下（已实际运行）：

| 稳定窗口 N | dropped | idle_gpu_min |
|-----------|---------|--------------|
| 原版（N=1） | 64 | 49.5 |
| 2 | 70 | 84.75 |
| 4 | 42 | 121.5 |
| 8 | 35 | 154.5 |

1. 解释为什么 N 增大时丢弃减少、空闲 GPU 时间增加。
2. N=2 时丢弃反而略增（64 → 70），说明了什么？
3. 写出你会在生产中给队列深度 autoscaler 加的另外两个保护措施。

---

## 四、面试高频题

**Q13.**（基础必考）在 Kubernetes 上做 LLM 推理的 GPU 自动伸缩，为什么不能"直接开 HPA"？请按三层说明需要哪些组件、各自解决什么问题。

**Q14.**（原理深挖）为什么 GPU 利用率（duty cycle）和显存占用都不是 LLM serving 的好伸缩信号？队列深度、KV cache 利用率、P99 TTFT、goodput 各自适合什么场景？

**Q15.**（工程实践）请为在 H100 SXM5 上服务 Llama 3.3 70B FP8 的集群设计一个 Karpenter NodePool（讲义练习 2），说明每个关键字段的选择理由。

**Q16.**（场景设计）团队报告："GPU 明明有空闲，但 pod 一直 Pending。"你会如何诊断是 Karpenter、kube-scheduler 还是 KAI Scheduler 的问题？看哪些指标和事件？

**Q17.**（追问型）凌晨 2 点来了一个 1M token 的长 prompt，集群里没有热副本。从请求到首 token 要经过哪些阶段？你如何在成本和 SLO 之间取舍 warm pool 的大小？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义的"When to use what"表：增删节点用 Karpenter；调度多 GPU 任务、抢占低优先级用 KAI Scheduler；增删副本用 Dynamo Planner / llm-d WVA（或基于队列深度的自定义 HPA）；选 GPU 类型用 Karpenter NodePool。A 把前两层颠倒，且 Cluster Autoscaler 是节点层工具；B 中 HPA 是副本层、Karpenter 是节点层；D 错，Karpenter 不做 gang scheduling 也不伸缩副本。

### Q2 — 答案：A

讲义："`DCGM_FI_DEV_GPU_UTIL` is a duty-cycle metric — it measures whether the GPU was doing work at each sampling interval. 100% utilization could mean 10 concurrent requests or 100." C 描述的是显存信号的问题（另一个陷阱）；B、D 是捏造的。补充：Kubernetes HPA 的副本公式是 `desired = ceil(current × 当前指标 / 目标指标)`，指标被封顶在 100% 时，每轮最多只能扩 `100/70 ≈ 1.43` 倍，且无法知道"还差多少"，这才是"盲目伸缩"的本质。讲义"The Problem"里写"HPA 从不扩容，因为它认为已经满了"，表述不够严谨——指标高于目标时 HPA 会扩容，问题在于信号饱和、无法反映积压规模。

### Q3 — 答案：D

讲义："It will terminate a running GPU node to migrate pods to a cheaper right-sized instance. For inference workloads that means evicting running requests and reloading a 70B model on the new node." A 恰好相反（这个策略是更积极地合并）；B、C 与合并策略无关。

### Q4 — 答案：B

这是讲义"The Problem"第三个场景，即"7-of-8 部分分配陷阱"。gang scheduling 让 8 个 pod 原子性地一起调度，资源不足时全部推迟，而不是先启动 7 个空等。A 是副本层参数；C 是 vLLM 显存参数；D 是节点合并参数，都不涉及多 pod 原子调度。

### Q5 — 答案：A

讲义："prefill pods scale on queue depth, decode pods scale on KV cache pressure. llm-d exposes these as separate `Services` with per-role HPA. Do not try to put a single HPA in front of both." prefill 是算力密集、按积压的 prompt 数决定；decode 是显存/带宽密集，KV cache 占满就无法接纳新序列。

### Q6 — 答案：D

实际运行（`make_workload(seed=7)`）：DUTY_CYCLE 丢 1、QUEUE_DEPTH 丢 64、KAI_GANG 丢 61。A 是把讲义的叙事套到了数字上——讲义和代码末尾的"Read"文字都暗示 DUTY_CYCLE 丢得最多，但实际结果正好相反（原因见 Q9）。换不同种子（1、2、3、11）结论一致：DUTY_CYCLE 丢 2–30 个，QUEUE_DEPTH 丢 75–105 个，DUTY_CYCLE 的空闲 GPU 时间始终约 260–280 分钟。

### Q7 — 答案：B

```python
        elif strategy == "KAI_GANG":
            qd = len(queue)
            if qd > 3 and replicas_target < MAX_REPLICAS:
                replicas_target = min(MAX_REPLICAS, replicas_target + max(2, qd // 3))
```

除了阈值与步长，它与 QUEUE_DEPTH 完全相同。`GPU_PER_REPLICA = 1` 和 `CLUSTER_AUTOSCALER_SEC = 110` 两个常量定义了但**从未使用**，所以 C、D 都不成立；代码里没有任何"多 pod 原子调度"或拓扑判断，A 错。KAI_GANG 丢弃更少（61 vs 64）只是因为它扩得更激进，与 gang scheduling 无关。

### Q8 — 答案：C

讲义："vLLM and similar engines pre-allocate KV cache memory (up to `--gpu-memory-utilization`). Memory usage stays near 90% even at one request. Memory-based HPA never scales down." skill 也把"按 GPU 显存伸缩"列为拒绝项。B 错：预分配后显存占用几乎恒定，并不随 decode 变化；真正随负载变化的是 KV **block** 的分配比例（KV cache 利用率），而不是显存占用。

### Q9 — 参考答案

1. **这里的 "util" 并不是 duty cycle**：`busy` 统计的是"本 tick 刚刚接到请求的副本数"（它们的 `available_at = now + 2.4 > now`）。只要本 tick 队列里的请求数 ≥ 就绪副本数，`util` 就是 100%。它实际上是"有没有积压"的一个粗信号。
2. **低流量期就会扩容**：静默期（0–600s，到达率 0.05/s，每 tick 约 0.75 个请求）只有 1 个副本时，只要来 1 个请求，`util = 1/1 = 100% > 70%`，立刻 +1。插桩显示，t=585s（高峰开始前）DUTY_CYCLE 已有 5 个就绪 + 4 个在供给中的副本，目标 9 个；而 QUEUE_DEPTH 和 KAI_GANG 都只有 1 个。
3. **缩容迟钝（滞回）**：只有 `util < 20%` 才缩容。5 个副本中有 1 个接到请求就是 20%，不满足 `< 20`。这相当于一个很宽的滞回区间，副本数"只升不降"。
4. **QUEUE_DEPTH 反而抖动**：队列每个 tick 都会被清空到 0 就立刻缩容 1 个（无稳定窗口），扩容又要 `qd > 5` 才触发，且新副本要 `50 + 45 = 95` 秒才就绪，而请求 30 秒就超时——于是"缩容 → 积压 → 扩容来不及 → 丢弃"反复发生。插桩：t=630s 时 QUEUE_DEPTH 只有 1 个就绪副本、5 个在供给中、队列 16；高峰期平均就绪副本 7.19，DUTY_CYCLE 为 13.8。
5. **代价**：DUTY_CYCLE 空闲 GPU 266.2 分钟，是 QUEUE_DEPTH（49.5）的 5.4 倍。它以过度供给换来了低丢弃。

结论：这个模拟器里的结果由**阈值、步长、滞回和稳定窗口**决定，而不是由"信号本身对不对"决定。代码末尾的"Read"文字与实际输出矛盾，讲义练习 1 的问题前提也不成立。

### Q10 — 参考答案

1. 每个副本每 tick 最多服务 1 个请求、忙 2.4 秒，最大 util = `2.4 / 15 = 16%`。
2. 16% 永远到不了 70% 的扩容阈值，且始终 < 20%，所以副本数一直停在 `MIN_WARM_REPLICAS = 1`。实际运行：`dropped = 511`（743 个中丢 68.8%），`peak_replicas = 1`，`idle_gpu_min = 3.0`。
3. 这正是讲义要说的"信号在撒谎"：duty cycle 的数值与真实积压无关。讲义的例子是信号**饱和在 100%**、看不出差多少；这里是 GPU 每次只忙一小段、信号**低估**负载。两者本质相同——duty cycle 只看"GPU 在不在忙"，不看"有多少请求在等"。

### Q11 — 参考答案

1. 理论上一个副本串行处理，`1 / 2.4 ≈ 0.417` 请求/秒（一个 tick 能处理约 6 个）；模拟中每 tick 只取 1 个，即 `1 / 15 ≈ 0.067` 请求/秒，低估了约 6 倍。真实 vLLM 还有 continuous batching，一个副本能同时服务几十个序列，差距更大。
2. 高峰期 `rate = 4.0`，每秒以 `4.0 / 10 = 0.4` 的概率产生 1 个请求，即 0.4 请求/秒、每 tick 6 个。按模拟能力需要约 6 个副本，按理论串行能力只需 1 个。实际生成的工作负载：静默期 34 个、高峰期 496 个、尾部 213 个，共 743 个。
3. 影响：副本"不够用"被放大了，所有策略都扩到了上限 16（peak=16）；丢弃数主要取决于"扩容时机 vs 95 秒冷启动 vs 30 秒超时"。若改成每个副本在一个 tick 内连续处理队列直到 tick 结束（已实际验证），DUTY_CYCLE 丢 0、QUEUE_DEPTH 丢 32、KAI_GANG 丢 23，峰值副本 DUTY_CYCLE 降到 10——数字整体变化很大，说明玩具模拟的定量结论不能直接搬到生产。

### Q12 — 参考答案

1. 稳定窗口让 autoscaler 在流量短暂回落时不立刻缩容，减少"刚缩完又要扩"的抖动；新副本 95 秒冷启动远长于 30 秒超时，任何一次错误的缩容都可能导致丢弃。代价是低谷期多保留了副本，空闲时间上升（49.5 → 154.5 分钟）。
2. 说明系统行为对参数**非单调、离散敏感**：15 秒的 tick、整数阈值和随机到达叠加后，小改动可能让扩缩容时序刚好错开高峰。评估 autoscaler 需要多个随机种子和多种流量形状，而不是一次运行。
3. 生产中常见的保护（任选两项并说明）：
   - 扩容快、缩容慢的非对称策略（Kubernetes HPA 的 `behavior.scaleDown.stabilizationWindowSeconds`）；
   - 按"队列深度 / 每副本目标并发"成比例扩容，而不是固定 +1；
   - 最小 warm 副本数按 SLO 设定（讲义："Keep a warm pool for SLO-critical paths"）；
   - 预测式扩容（按历史时段提前扩，如早高峰）；
   - 冷启动期间的 admission control / 排队 + 降级（返回 429 或路由到托管 API）。

### Q13 — 参考回答要点

- **节点层（Karpenter）**：Pending pod 触发直接按 NodePool 约束开 GPU 节点，约 45–60s（Cluster Autoscaler 约 90–120s）；GPU 池要用 `WhenEmpty` + `consolidateAfter: 1h`，避免合并时驱逐正在推理的节点。
- **调度层（KAI Scheduler）**：作为二级调度器与 kube-scheduler 并存，提供 gang scheduling（防部分分配）、拓扑感知（TP 留在同一 NVLink 域）、层级队列（多团队配额与抢占）。
- **应用层（Dynamo Planner / llm-d WVA / 自定义 HPA）**：按队列深度、KV cache 利用率、P99 TTFT、goodput 伸缩副本，不用 `DCGM_FI_DEV_GPU_UTIL`。
- 三层的联动：应用层增加副本 → pod Pending → KAI 判断能否整组调度 → 资源不足时 Karpenter 开节点。
- 加分点：说出每层对应的失败模式（HPA 信号失真、2 a.m. 长 prompt 等节点超时、7-of-8 部分分配），并提到冷启动期间需要 warm pool。

### Q14 — 参考回答要点

- **duty cycle**：只表示采样时 GPU 是否在执行 kernel，饱和于 100%，不能区分 10 个和 100 个并发；在小 batch/短请求下又可能低估负载（Q10 的 16% 上限）。
- **显存**：推理引擎预分配 KV cache，显存几乎恒定在 `--gpu-memory-utilization` 附近，永远触发不了缩容。
- **队列深度**：直接反映积压，适合 prefill 侧和整体扩容判断；需配合"每副本目标并发"做比例换算。
- **KV cache 利用率**：已分配给活跃序列的 block 比例，接近满时无法接纳新序列，适合 decode 侧。
- **P99 TTFT**：直接对应 SLA，但它是滞后指标，适合作为告警和兜底触发器。
- **goodput**：同时满足所有 SLO 的请求速率，最贴近业务价值，常用于评估而非实时伸缩。
- 常见误区：把 DCGM 的 SM 活跃度等更细指标当成万能信号——它们仍然不反映排队请求数。

### Q15 — 参考回答要点

参考 YAML（Karpenter v1 API，AWS 为例；p5.48xlarge 是 8×H100 实例）：

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: gpu-h100-inference
spec:
  template:
    metadata:
      labels:
        workload: llm-inference          # 供 KAI Scheduler / nodeSelector 选择
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]          # 在线推理不用 spot，避免被回收
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["p5.48xlarge"]
      taints:
        - key: nvidia.com/gpu
          value: "true"
          effect: NoSchedule             # 非 GPU 工作负载无法调度上来
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: gpu-al2023
  disruption:
    consolidationPolicy: WhenEmpty       # 不驱逐正在运行的推理
    consolidateAfter: 1h
  limits:
    nvidia.com/gpu: 64                   # 成本上限
```

- `capacity-type`：在线推理用 on-demand 或预留；离线批处理可用 spot。
- `WhenEmpty + 1h`：只合并真正空了一小时的节点，避免抖动和驱逐。
- taint + 推理 pod 的 toleration：防止 CPU 服务占用昂贵的 GPU 节点。
- 70B FP8 权重约 70GB，单卡 80GB 放得下但留给 KV cache 的空间很少，通常 TP=2 或 TP=4，需要 gang + 同 NVLink 域调度。
- 加分点：设置 `limits` 防止失控扩容；为模型权重准备节点本地缓存或镜像预拉取以缩短冷启动。

### Q16 — 参考回答要点

- **先看 pod 事件**：`kubectl describe pod` 的 `FailedScheduling` 原因——`Insufficient nvidia.com/gpu`、`node(s) had untolerated taint`、`didn't match node affinity`、拓扑约束不满足等。
- **kube-scheduler/KAI 问题**：资源"总量够但分散"（7 张空闲卡分布在 3 个节点上，但 pod 要求同节点或同 NVLink 域）；gang 组内成员不够被整体推迟；队列配额已满或优先级不够。看 KAI 的 PodGroup 状态、队列配额使用率、gang 推迟次数（skill 建议的 dashboard 指标"gang-scheduling deferral count"）。
- **Karpenter 问题**：没有匹配的 NodePool（instance-type/zone 不符）、达到 `limits`、云厂商容量不足（ICE）。看 Karpenter 日志与 NodeClaim 事件、"node provision wait time"。
- **其他**：device plugin 未上报 GPU、节点 NotReady、taint/toleration 不匹配。
- 结论：先区分"调度不上（scheduler 层）"还是"没有节点（provisioner 层）"，再看配额与拓扑。

### Q17 — 参考回答要点

- **阶段**：请求到达 → 应用层 autoscaler 发现队列 → 新副本 Pending → Karpenter 开节点（约 45–60s）→ 拉镜像 + 加载权重（讲义举例 20GB 模型）+ 引擎初始化 → 1M token 的 prefill 本身也很长。讲义估算从零开始需要 2–5 分钟，远超常见的请求超时。
- **取舍**：
  - SLO 关键路径保留 `min_workers=1` 或更多 warm 副本，成本是为空闲付费；
  - 非关键路径允许缩容到零，配合排队与"预计等待时间"提示；
  - 预测式预热（已知流量高峰前扩容）；
  - 冷启动加速：权重本地缓存、快照/checkpoint 恢复（讲义提到 Modal 风格的 checkpointing）；
  - 兜底：冷启动期间把请求路由到托管 API（阶段 17 · 02 的平台）。
- 加分点：用"冷启动时长 × 冷启动次数 × 每次失败的业务损失"与"warm 副本每小时成本"做定量比较。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 02 Inference 平台经济性：Fireworks、Together、Baseten、Modal、Replicate、Anyscale](../../02-inference-platform-economics/docs/zh.md)：自建集群前先算清托管与自建的成本。
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：KV cache 预分配与 block 利用率的来源。
- [阶段 00 · 07 用于 AI 的 Docker](../../../00-setup-and-tooling/07-docker-for-ai/docs/zh.md)：容器化是上 Kubernetes 的前提。

### 本节被哪些后续内容用到
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：伸缩信号与 SLO 指标的精确定义。
- [阶段 17 · 10 缓解无服务器 LLMs 的冷启动](../../10-cold-start-mitigation/docs/zh.md)：warm pool、权重缓存与快照。
- [阶段 17 · 17 Prefill 与 Decode 分离：NVIDIA Dynamo 与 llm-d](../../17-disaggregated-prefill-decode/docs/zh.md)：per-role 伸缩的具体架构。
- [阶段 17 · 18 生产服务技术栈：KV 卸载与缓存感知路由](../../18-vllm-production-stack-lmcache/docs/zh.md)：多副本之间的路由与 KV 复用。
- [阶段 17 · 22 对 LLM APIs 进行负载测试](../../22-load-testing-llm-apis/docs/zh.md)：用真实流量形状验证 autoscaler。
- [阶段 17 · 24 LLM 生产环境中的混沌工程](../../24-chaos-engineering-llm/docs/zh.md)：主动验证节点被回收、合并时的行为。

### 延伸关键词
`Karpenter NodePool` · `consolidationPolicy` · `Cluster Autoscaler` · `KAI Scheduler` · `gang scheduling / PodGroup` · `topology-aware scheduling` · `NVLink domain` · `DCGM_FI_DEV_GPU_UTIL` · `HPA behavior / stabilizationWindowSeconds` · `KEDA` · `queue depth` · `KV cache utilization` · `goodput` · `warm pool`
