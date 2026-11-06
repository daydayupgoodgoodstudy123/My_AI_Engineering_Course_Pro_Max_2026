# 测验 · 缓解无服务器 LLMs 的冷启动（Cold Start Mitigation for Serverless LLMs）

> **阶段 17 · 基础设施与生产 · 第 10 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 冷启动的解剖 | 节点供给（Karpenter 45–60 s）+ 拉镜像（30 GB，120–300 s）+ 权重进 HBM（45–120 s）+ 引擎初始化（CUDA graph、KV 池、tokenizer，10–30 s）；讲义合计 220–510 s，约 3–8 分钟 |
| 2 | 冷启动 = 故障 | SLA 是 2 s 时，几分钟的冷启动不是"预热"，而是一次 outage |
| 3 | L1 预置节点镜像 | AWS Bottlerocket 双卷架构：数据卷快照里预拉好镜像，`EC2NodeClass` 引用快照 ID；消除拉镜像，大模型每次省 2–4 分钟 |
| 4 | L2 模型流式加载 | NVIDIA Run:ai Model Streamer（vLLM 原生集成）：逐层把权重流入 GPU，I/O 与计算准备重叠，权重加载约快 2 倍 |
| 5 | L3 GPU 显存快照 | Modal 在首次加载后对 GPU 状态（权重、CUDA graph、KV 区域）做 checkpoint，重启时直接反序列化进 HBM，约快 10 倍；**快照与 GPU 拓扑绑定**，换 SKU 要重做 |
| 6 | L4 warm pool | `min_workers=1`：永远留一个副本，代价是 24×7 的 GPU 费用；讲义：70B+ 模型 TTFT P99 < 60 s 时 warm pool 成为必选 |
| 7 | L5 分层加载 | ServerlessLLM：NVMe → DRAM → HBM 的存储层级，权重预放 DRAM、按需进 HBM；论文报告冷加载延迟降低 10–200 倍 |
| 8 | 附加：live migration | 节点被驱逐时，把**输入 token（KB 级）**迁到已加载模型的目标节点并在那里重算 KV，而不是传输 GB 级的 KV cache |
| 9 | warm pool 的分层策略 | 高价值交互路径 `min_workers=1–2`；后台批处理接受 scale-to-zero；高级租户独享 `min_workers` |
| 10 | 先测量再优化 | 讲义的 70B 示例：50 + 180 + 75 + 20 + 3 = 328 s，叠加缓解后约 15 s（约 22 倍）；参考数字：Modal 2–4 s，Baseten 默认 5–10 s、预热后亚秒级 |

### 核心技能（能动手做到）

- [ ] 把一次冷启动拆成 5 个阶段并估算每个阶段的秒数（例如按存储带宽算权重加载时间）
- [ ] 说出每一层缓解措施具体消除或缩短的是哪个阶段
- [ ] 计算 warm pool 的月成本，并建立"冷启动损失 vs warm pool 成本"的盈亏平衡模型
- [ ] 为给定 SLA 选择"层数最少"的缓解组合，并识别"在该平台上数学上不可能"的 SLA
- [ ] 解释 live migration 为什么迁移 token 而不迁移 KV cache，并给出数量级
- [ ] 指出本节代码 `warm_pool_break_even` 的建模问题并重写

---

## 二、基础自测（选择题）

**Q1.** 讲义"Measure before optimizing"表中 70B 模型冷启动的各阶段为：节点 50 s、拉镜像 180 s、权重进 HBM 75 s、引擎初始化 20 s、首次前向 3 s。总时长和讲义声称的缓解后倍数分别是：

- A. 308 s，约 10 倍
- B. 328 s，约 109 倍
- C. 328 s，约 22 倍（缓解后约 15 s）
- D. 510 s，约 22 倍

**Q2.** Bottlerocket 预置数据卷快照主要消除的是哪个阶段？

- A. 拉取包含权重的容器镜像（示例中的 180 s）
- B. 节点供给
- C. CUDA graph 捕获
- D. 首次前向计算

**Q3.** NVIDIA Run:ai Model Streamer 加速冷启动的机制是：

- A. 把权重量化为 INT4，文件变小
- B. 把 KV cache 预先计算好存在 S3
- C. 跳过 CUDA graph 初始化
- D. 不等整个文件加载完，逐层把权重流入 GPU，让 I/O 与计算准备重叠，权重加载时间约减半

**Q4.** 关于 Modal 式 GPU 显存快照，下列哪项是讲义强调的限制？

- A. 快照只能保存权重，不能保存 CUDA graph
- B. 快照与 GPU 拓扑绑定；若调度器把你迁到另一种 GPU SKU，需要重新做 checkpoint
- C. 快照恢复比冷启动更慢
- D. 快照只在 CPU 推理时可用

**Q5.** 一个节点被 spot 回收，正在进行的会话要迁移到另一个已加载模型的节点。讲义推荐迁移什么？

- A. 整个 KV cache（GB 级），避免重算
- B. 输入 token（KB 级），在目标节点重算 KV cache
- C. 模型权重
- D. 什么都不迁，让用户重新发起请求

**Q6.** 讲义"The Problem"中，5 个产品各保留 1 个 warm 副本，每月需要多少 GPU 小时（按 30 天）？

- A. 720
- B. 1,200
- C. 2,400
- D. 3,600

**Q7.** 本节代码中 `{"pre_seeded", "streamer"}` 组合的总冷启动为 108 s。剩下的时间里占比最大的两个阶段是：

- A. 节点供给（50 s）与权重进 HBM（35 s）
- B. 拉镜像（180 s）与引擎初始化（20 s）
- C. 引擎初始化（20 s）与首次前向（3 s）
- D. 权重进 HBM（75 s）与节点供给（50 s）

**Q8.** 关于本节代码的 `warm_pool_break_even`，下列说法正确的是：

- A. 它比较了 warm pool 的月成本与冷启动造成的金钱损失，给出了盈亏平衡请求率
- B. 它对每个请求率都用 `cold_seconds` 计算了冷启动期间受影响的请求数
- C. 它算出了 `warm_monthly` 和传入了 `cold_seconds`，但两者都没参与"Warm better?"的判断；冷启动次数直接取 `int(24 / rate)` 并截断到 [1, 20]，且第一行赋值是被立即覆盖的死代码
- D. 它正确地模拟了 Poisson 到达与空闲超时

---

## 三、动手 / 代码题

**Q9.** 阅读 `total_for_stack`：

```python
PHASES_70B = [
    Phase("node provision",   50.0, 50.0,  50.0,  0.5),
    Phase("image pull",      180.0,  0.0, 180.0,  0.0),
    Phase("weights to HBM",   75.0, 75.0,  35.0,  0.0),
    Phase("engine init",      20.0, 20.0,  20.0,  2.0),
    Phase("first forward",     3.0,  3.0,   3.0,  0.5),
]

def total_for_stack(stack: set[str]) -> float:
    seconds = 0.0
    for phase in PHASES_70B:
        if "gpu_snapshot" in stack:
            seconds += phase.snapshot_sec
        elif "streamer" in stack and "pre_seeded" in stack:
            used = phase.pre_seeded_sec
            if phase.name == "weights to HBM":
                used = phase.streamer_sec
            seconds += used
        elif "pre_seeded" in stack:
            seconds += phase.pre_seeded_sec
        elif "streamer" in stack:
            seconds += phase.streamer_sec if phase.name == "weights to HBM" else phase.raw_sec
        else:
            seconds += phase.raw_sec
    return seconds
```

1. `total_for_stack({"warm_pool"})` 返回多少？为什么？
2. `gpu_snapshot` 行把"node provision"设为 0.5 s。快照真的能消除节点供给吗？讲义的 Modal 2–4 s 隐含了什么前提？
3. 这种 `if/elif` 写法在增加第 5 种缓解（如 tiered loading）时会遇到什么问题？用"每层只覆盖它攻击的阶段"的数据驱动方式重写，并给出 `{"pre_seeded", "tiered"}` 的结果（假设 DRAM → HBM 需要 5 s）。

**Q10.** 讲义练习 1 要求计算"warm 副本比承担冷启动更便宜的盈亏平衡请求率"，但代码的 `warm_pool_break_even` 没有真正计算金钱。请重写一个模型：

- 请求按 Poisson 过程到达，速率 λ（次/小时）；副本空闲超过 `idle_timeout`（15 分钟）就缩到 0；
- 每次冷启动影响"触发它的请求 + 冷启动 328 s 内到达的请求"；
- 每个受影响请求的业务损失为 $0.50（假设值）；warm pool 成本 $4.50/h。

1. 写出每天冷启动次数与受影响请求数的公式，并计算 λ = 0.5、1、2、5、10、25、50 时的结果。
2. 冷启动次数为什么随 λ 先升后降？峰值出现在哪里？
3. 在这些假设下，每个受影响请求的损失至少要多大，warm pool 才在某个流量下划算？
4. 这个"纯成本"视角漏掉了什么？

**Q11.** 讲义练习 2 与练习 3：

1. 练习 3：Bottlerocket 预置后不再拉镜像，但权重仍要从快照支撑的 NVMe 读入 HBM。若 NVMe 读速 7 GB/s，70B 的 BF16 权重与 FP8 权重分别需要多久？沿用代码其它阶段的数值，整体冷启动是多少？
2. 练习 2：13B 模型、TTFT P99 SLA 3 s。给出"层数最少"的缓解组合并说明理由。

**Q12.** 讲义练习 5：为付费用户、试用用户、批处理三类流量设计分层 warm pool 策略，并给出月成本（GPU $4.50/h，按 30 天）。要求：付费交互路径 TTFT P99 ≤ 2 s；试用用户可以接受偶尔的冷启动但不超过 30 s；批处理允许 5–10 分钟冷启动。

---

## 四、面试高频题

**Q13.**（基础必考）一个 70B 模型从 0 扩到 1 副本要花几分钟，时间都花在哪里？每个阶段有什么对应的缓解手段？

**Q14.**（原理深挖）为什么 live migration 迁移输入 token 而不是 KV cache？请给出数量级估算，并说明在什么情况下"传 KV"反而是对的。

**Q15.**（工程实践）你负责一个 serverless LLM 平台，财务要求砍掉所有 warm pool，产品要求 TTFT P99 ≤ 2 s。你如何回应和取舍？

**Q16.**（场景设计）一个 70B 模型、流量高度突发（白天高峰、夜间接近 0），SLA 为 TTFT P99 ≤ 5 s。请设计完整的冷启动缓解方案。

**Q17.**（追问型）团队拒绝使用 GPU 快照，理由是"快照会泄露 PII"。你怎么看？（讲义练习 4）

---

## 五、参考答案与解析

### Q1 — 答案：C

`50 + 180 + 75 + 20 + 3 = 328 s`；讲义："Total with mitigations ~15s, 22x reduction"（`328 / 15 ≈ 21.9`）。A 少加了 20 s；B 的 109 倍是代码里 GPU 快照栈（3 s）的倍数（`328 / 3 ≈ 109`），不是讲义表中的数字；D 的 510 s 是讲义"The Problem"中区间的上限。

### Q2 — 答案：A

讲义："Snapshot the data volume with your container image pre-pulled ... New nodes boot with weights already on local NVMe — steps 2 and part of 3 vanish." 代码中 `pre_seeded_sec` 只把 "image pull" 设为 0。B 错，节点仍需供给（代码中仍是 50 s）；C、D 与镜像无关。

### Q3 — 答案：D

讲义："stream weights into GPU memory layer-by-layer and start processing as soon as the first transformer block is resident ... Cuts weight-load time roughly in half for large models by overlapping I/O with compute setup." 代码中权重进 HBM 从 75 s 变为 35 s。A 是量化（第 09 节）；B、C 都不是 streamer 的功能。

### Q4 — 答案：B

讲义："snapshots are per-GPU-topology, so if Karpenter migrates you to a different SKU, you re-checkpoint." skill 文件也把"忽略快照的 GPU 拓扑约束"列为 hard reject。A 错，快照包含"weights, CUDA graphs, KV cache region"；C 错，快照重启约快 10 倍；D 错，快照针对 GPU 状态。

### Q5 — 答案：B

讲义："Live migration moves the input tokens (kilobytes) to a destination that has the model loaded and recomputes KV cache on the destination. Recomputation is cheaper than transferring GB of KV cache over the network." A 是讲义明确否定的做法；C 目标节点已加载模型；D 是传统做法（冷启动另一个副本并排空队列）。

### Q6 — 答案：D

`5 × 24 × 30 = 3,600` GPU 小时/月——"whether or not a single user called"。A 是单个副本的 720 小时；B、C 无依据。按代码的 $4.50/h，单副本月成本 $3,240，5 个就是 $16,200。

### Q7 — 答案：A

`{"pre_seeded", "streamer"}` 分支：每个阶段取 `pre_seeded_sec`，"weights to HBM" 改取 `streamer_sec`。结果：50 + 0 + 35 + 20 + 3 = 108 s。最大的两项是节点供给 50 s 和权重加载 35 s。B 错，拉镜像已被消除；D 的 75 s 是未开 streamer 时的值。这也说明要再往下压，必须解决节点供给（warm 节点池 / 平台托管容量）和权重加载（快照 / 分层加载）。

### Q8 — 答案：C

代码：

```python
        cold_starts_per_day = 24 / max(rate, 1) if rate < 1 else 1        # 立即被覆盖
        cold_starts_per_day = min(20, max(1, int(24 * 3600 / (rate * 3600))))
        drops = cold_starts_per_day
        warm_better = "yes" if drops > sla_tolerated_drops_per_day else "no"
```

`warm_monthly` 只被打印，`cold_seconds` 只出现在标题行；判断只是"冷启动次数是否超过每天 5 次的容忍预算"。`int(24 * 3600 / (rate * 3600))` 化简就是 `int(24 / rate)`，每次冷启动只算 1 次"drop"，没有考虑冷启动 328 s 内到达的其它请求。A、B、D 描述的都是代码没有做的事（Q10 会补上）。

### Q9 — 参考答案

1. 返回 **328.0 s**（已实际运行验证）。`"warm_pool"` 不匹配任何分支，落到 `else: raw_sec`。代码只在注释和打印里提到 warm pool（"WARM_POOL avoids cold start entirely on the warm path"），并没有把它建模成栈的一部分——warm pool 不是"缩短冷启动"，而是"让主路径不发生冷启动"，所以应该单独处理（返回 0 或在报告中单列）。
2. 不能。快照恢复的前提是**已经有一台带 GPU 的机器**；在自建 Kubernetes 上，新节点仍需 Karpenter 供给 45–60 s。Modal 的 2–4 s 隐含"平台方维护了一个共享的热 GPU 容量池"，你的容器被调度到已有机器上，节点供给的成本由平台摊掉了。代码把 node provision 设为 0.5 s 等于默认了这一前提；在自建集群上，快照栈的真实下限更接近 `50 + 2 + 0.5 ≈ 53 s`（除非同时有 warm 节点池）。
3. `if/elif` 需要为每种组合写分支（n 层就有 2ⁿ 种组合），而且 `{"pre_seeded", "streamer", "gpu_snapshot"}` 之类的组合只能靠分支顺序隐式决定。数据驱动重写：

```python
OVERRIDES = {
    "pre_seeded": {"image pull": 0.0},
    "streamer":   {"weights to HBM": 35.0},
    "tiered":     {"weights to HBM": 5.0},     # DRAM -> HBM，假设值
}

def total_v2(stack):
    if "gpu_snapshot" in stack:
        return sum(p.snapshot_sec for p in PHASES_70B)
    t = {p.name: p.raw_sec for p in PHASES_70B}
    for layer in stack:
        for phase, sec in OVERRIDES.get(layer, {}).items():
            t[phase] = min(t[phase], sec)          # 多层攻击同一阶段时取最优
    return sum(t.values())
```

实际运行：对原有 5 种组合与 `total_for_stack` 结果完全一致（328 / 148 / 288 / 108 / 3）；`{"pre_seeded", "tiered"}` = 50 + 0 + 5 + 20 + 3 = **78 s**。注意 tiered loading 的前提是权重已经在 DRAM 里（即节点已经存在且预热过），否则 5 s 不成立。

### Q10 — 参考答案

1. 公式：
   - 每天到达数 `24λ`；
   - 一个请求到达时副本已缩容的概率 = 上一个请求间隔超过 `idle_timeout` 的概率 = `exp(−λ·T)`（Poisson 到达时间间隔服从指数分布）；
   - 每天冷启动次数 `= 24λ · exp(−λT)`；
   - 每次冷启动受影响请求数 `= 1 + λ · 328 / 3600`；
   - 每天损失 = 受影响请求数 × $0.50；warm pool 每天 `4.5 × 24 = $108`。

```python
import math
def cold_model(rate_per_hr, cold_s=328, idle_timeout_h=0.25, value_per_drop=0.5, gpu_hourly=4.5):
    arrivals_day = 24 * rate_per_hr
    p_cold = math.exp(-rate_per_hr * idle_timeout_h)
    cold_per_day = arrivals_day * p_cold
    hit_per_cold = 1 + rate_per_hr * cold_s / 3600
    drops_day = cold_per_day * hit_per_cold
    return cold_per_day, drops_day, drops_day * value_per_drop, gpu_hourly * 24
```

实际运行结果：

| λ（次/h） | 冷启动/天 | 受影响请求/天 | 损失 $/天 | warm $/天 |
|----------|----------|-------------|----------|----------|
| 0.5 | 10.59 | 11.07 | 5.54 | 108 |
| 1 | 18.69 | 20.39 | 10.20 | 108 |
| 2 | 29.11 | 34.42 | 17.21 | 108 |
| 5 | 34.38 | 50.04 | 25.02 | 108 |
| 10 | 19.70 | 37.65 | 18.82 | 108 |
| 25 | 1.16 | 3.80 | 1.90 | 108 |
| 50 | 0.00 | 0.02 | 0.01 | 108 |

2. 低流量时请求少，冷启动次数随 λ 增长；高流量时副本几乎不会空闲 15 分钟，冷启动概率 `exp(−λT)` 迅速趋近 0。冷启动次数 `24λe^{−λT}` 在 `λ = 1/T = 4 次/小时` 时最大；受影响请求数的峰值约在 λ ≈ 5.3 次/小时，约 50 个/天。
3. 最坏情况每天约 50 个受影响请求，`108 / 50.1 ≈ $2.15`。只有每个受影响请求的业务损失超过约 $2.15，warm pool 才可能在纯成本上划算；按 $0.50 计，任何流量下都不划算。
4. 漏掉的东西：
   - **SLA / 体验约束**：讲义的视角是"SLA 决定 warm pool"——付费交互路径只要有一次 5 分钟的冷启动就违约，这不是用平均成本能衡量的（讲义："TTFT P99 < 60s on a 70B+ model" 时 warm pool 必选）；
   - 流量并非 Poisson：早高峰的集中爬坡会让多个副本同时冷启动；
   - 用户流失、品牌损失等难以量化的成本；
   - 缓解层（预置镜像、快照）能把 328 s 缩短，从而改变 `hit_per_cold`，应与 warm pool 联合优化。

### Q11 — 参考答案

1. 70B BF16 权重 140 GB：`140 / 7 = 20 s`；FP8 权重 70 GB：`10 s`。沿用代码其它阶段（节点 50 s、无拉镜像、引擎 20 s、首次前向 3 s）：BF16 `50 + 0 + 20 + 20 + 3 = 93 s`，FP8 `83 s`（实际计算）。比代码里 `pre_seeded` 栈的 148 s（权重 75 s）快，说明代码的 75 s 对应的是更慢的存储（约 1.9 GB/s）。节点供给 50 s 成为最大头——这也是为什么"预置镜像"之后下一步是 warm 节点池或快照。
2. 3 s 的 TTFT P99 意味着**主路径上不能发生任何冷启动**：即使 GPU 快照也要 2–4 s（Modal 公布的下限），再加上真实请求的 prefill、排队，P99 无法稳定 ≤ 3 s。最少层数方案：**warm pool（`min_workers ≥ 1`）**，单层即可满足主路径；扩容时的新副本建议配合 GPU 快照（或预置镜像 + streamer）缩短扩容窗口，并使用"新请求先路由到已有 warm 副本"的尾部策略（skill 文件第 5 项）。13B 的 GPU 单价较低，讲义说 warm pool 的算术"brutal on small models"，但 SLA 优先于成本。

### Q12 — 参考答案

示例方案（数值为示意，需按真实流量校准）：

| 层级 | 策略 | warm 副本 | 月成本 |
|------|------|----------|--------|
| 付费交互 | `min_workers = 2`（一个应对日常、一个应对单副本故障/滚动更新），突发扩容走快照 | 2 | `2 × 4.5 × 720 = $6,480` |
| 试用用户 | `min_workers = 0`，GPU 快照或预置镜像 + streamer + 分层加载，把冷启动压到 ≤ 30 s；高峰期白天保持 1 个副本（例如 12 h/天） | 0–1 | `4.5 × 12 × 30 = $1,620` |
| 批处理 | scale-to-zero，冷启动 5–10 分钟可接受；集中调度、批量启动 | 0 | 按用量付费 |

推导要点：
- 付费层由 SLA 驱动，2 s 的 P99 不能容忍任何冷启动，所以必须有 warm 副本；用 2 个而不是 1 个，是因为单副本在重启、升级、故障时会立刻暴露冷启动（skill 文件第 6 项"failure mode"）。
- 试用层由"≤ 30 s"驱动：按代码数字，预置镜像 + streamer 仍需 108 s，不够；需要快照（自建集群需配合 warm 节点池）或分层加载。skill 文件："If budget forbids warm pool but SLA requires sub-30s cold start, name the platform-specific fix (Modal GPU snapshots, Baseten pre-warming)."
- 合计固定成本约 $8,100/月；对比 3 个层全部 `min_workers = 1` 的 $9,720，以及付费层冷启动违约的代价。

### Q13 — 参考回答要点

- **阶段与数量级**（讲义 70B 示例）：节点供给 50 s、拉镜像 180 s、权重进 HBM 75 s、引擎初始化 20 s、首次前向 3 s，合计 328 s。
- **逐阶段缓解**：
  - 节点供给 → warm 节点池 / warm pool / 平台托管容量；
  - 拉镜像 → 预置节点镜像（Bottlerocket 数据卷快照，GCP 自定义镜像，Azure 磁盘快照）；
  - 权重加载 → Model Streamer（约 2 倍）、分层加载（ServerlessLLM，10–200 倍）、GPU 快照（直接消除）；更小的量化权重也更快（第 09 节）；
  - 引擎初始化 → 持久化 CUDA graph 缓存、GPU 快照；
  - 首次前向 → 固有延迟。
- **组合**：讲义称叠加后约 15 s（22 倍）；单一工具无法覆盖所有阶段，必须分层叠加。
- 加分点：强调"先测量"——不同集群的瓶颈不同（例如存储带宽决定权重加载时间）。

### Q14 — 参考回答要点

- **数量级**：Llama 3 70B 每 token KV = `80 层 × 2 × 8 KV 头 × 128 × 2 B = 327,680 B`，8k 上下文约 **2.68 GB**；而 8k 个 token ID 按 4 字节存只有 **32 KB**，差约 8 万倍。
- **传输 vs 重算**：2.68 GB 在 25 Gbps 网络上约 0.86 s，在 100 Gbps 上约 0.21 s；而在已加载模型的目标节点上重算就是一次 prefill（讲义第 08 节：70B FP8 在 H100 上 32k prompt 约 800 ms，8k 的量级约为其 1/4 或更少）。在普通数据中心网络上，重算通常不慢于传输，而且不占用网络带宽。
- **更关键的原因**：live migration 发生在节点被驱逐、排空时——源节点可能马上消失，KV 根本来不及或无法完整导出；而输入 token 很小，可以保存在路由层/网关，任何时候都能重放。
- **什么时候传 KV 是对的**：prefill/decode 分离（第 17 节）——prefill 节点刚算完 KV，通过 NVLink / InfiniBand（RDMA）高速传给 decode 节点；长上下文时重算代价远高于高速互联的传输代价；以及跨请求的 KV 复用（第 18 节的 KV 卸载）。
- 讲义："Applicable to disaggregated deployments."

### Q15 — 参考回答要点

- **先量化矛盾**：2 s 的 P99 意味着主路径不能有冷启动；即使 GPU 快照也要 2–4 s。没有 warm pool 时，这个 SLA 在数学上无法保证（skill 文件的拒绝规则："If SLA is TTFT P99 < 5s on a fresh 70B cold start with no warm pool, refuse"）。
- **给财务的选项**：
  - 只为高价值交互路径保留 warm pool，批处理和低价值路径 scale-to-zero（分层策略，见 Q12）；
  - 用快照/预置镜像缩短扩容窗口，让 warm 副本数可以更少（例如峰值靠快速扩容、只保留 1 个基线副本）；
  - 按时段调整 `min_workers`（夜间降到 0 或 1）；
  - 计算违约成本（流失、SLA 赔付）与 warm pool 月成本（单 70B 副本约 $3,240）对比。
- **给产品的选项**：若坚持零 warm pool，就必须放宽 SLA（例如首请求允许 30 s，或用 UI 提示"正在唤醒"）。
- 要点：这不是技术能单方面解决的问题，而是 SLA × 成本的显式取舍，要把数字摆出来。

### Q16 — 参考回答要点

- **判断可行性**：70B + 突发 + 5 s，scale-to-zero 无法保证（skill："If the operator asks for scale-to-zero with bursty traffic and a 70B model, refuse to promise SLA"）。
- **方案**：
  - 白天 `min_workers ≥ 1–2`，夜间可降到 1（不建议 0）；
  - 节点镜像预置（消除拉镜像）+ Model Streamer / 分层加载（缩短权重加载）；在支持的平台上用 GPU 快照，把扩容副本的就绪时间压到秒级；
  - 预测性扩容：早高峰前按历史曲线提前扩容；
  - 尾部策略：新副本就绪前，请求排队到已有 warm 副本（"route first request to any warm replica within 10s"）；
  - 故障恢复：节点驱逐时用 live migration 迁移 token，避免会话中断。
- **观测**：按 skill 文件，告警指标为"最近滚动一小时的 P99 冷启动时长"；同时跟踪 TTFT P99 与 goodput（第 08 节）。
- **成本**：列出 warm 副本月成本与扩容频次，定期复核。

### Q17 — 参考回答要点

- **风险是真实的**：GPU 快照包含 HBM 中的状态——讲义写明包括"KV cache region"；如果在服务过真实请求之后才做快照，KV 区域、CPU 内存中的缓冲（如请求日志、tokenizer 缓存）可能残留用户数据，快照被复用到其他租户或泄露时就构成 PII 风险。
- **但风险可控**：
  - 只在**加载完权重、尚未接收任何用户请求**时做快照（"clean" 快照），KV 区域为空；
  - 快照加密存储，按租户/命名空间隔离，不跨租户复用；
  - 使用短生命周期（ephemeral）快照，定期轮换；
  - 审计快照的创建与访问，纳入合规流程（第 25、26 节）。
- **结论**：不应因噎废食；用"快照时机 + 加密 + 隔离 + 审计"把风险降到与普通镜像同级，同时换来 10 倍的重启速度。
- 常见误区：一概而论地说"快照安全"或"快照一定泄露"——关键在快照时机和隔离边界。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 02 Inference 平台经济性](../../02-inference-platform-economics/docs/zh.md)：Modal、Baseten 等 serverless 平台的计费模式。
- [阶段 17 · 03 Kubernetes 上的 GPU Autoscaling：Karpenter、KAI Scheduler 与成组调度](../../03-gpu-autoscaling-kubernetes/docs/zh.md)：节点供给与扩缩容机制。
- [阶段 17 · 04 服务引擎内部机制](../../04-vllm-serving-internals/docs/zh.md)：引擎初始化时 KV 池与 CUDA graph 的作用。
- [阶段 17 · 09 生产环境中的 Quantization](../../09-production-quantization/docs/zh.md)：权重越小，加载越快。

### 本节被哪些后续内容用到
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：冷启动直接体现在 TTFT 的尾部。
- [阶段 17 · 11 多区域 LLM 服务与 KV Cache 局部性](../../11-multi-region-kv-locality/docs/zh.md)：跨区域故障转移同样面临"传 KV 还是重算"。
- [阶段 17 · 17 Prefill 与 Decode 分离：NVIDIA Dynamo 与 llm-d](../../17-disaggregated-prefill-decode/docs/zh.md)：live migration 与 KV 传输的适用场景。
- [阶段 17 · 24 LLM 生产环境中的混沌工程](../../24-chaos-engineering-llm/docs/zh.md)：主动演练节点驱逐与冷启动。
- [阶段 17 · 25 安全：密钥、API 密钥轮换、Audit Logs 与 Guardrails](../../25-security-secrets-audit/docs/zh.md)：快照的加密与审计。
- [阶段 17 · 27 LLMs 的 FinOps](../../27-finops-llms/docs/zh.md)：warm pool 的成本归因。

### 延伸关键词
`cold start` · `scale-to-zero` · `min_workers` · `warm pool` · `Karpenter` · `Bottlerocket` · `EC2NodeClass` · `Run:ai Model Streamer` · `GPU memory snapshot` · `CUDA graph cache` · `ServerlessLLM` · `tiered loading` · `live migration` · `spot eviction` · `Poisson arrivals`
