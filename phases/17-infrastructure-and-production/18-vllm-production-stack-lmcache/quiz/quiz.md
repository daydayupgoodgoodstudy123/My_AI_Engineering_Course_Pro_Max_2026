# 测验 · 生产服务技术栈：KV 卸载与缓存感知路由（Production Serving Stack — KV Offloading and Cache-Aware Routing）

> **阶段 17 · 基础设施与生产 · 第 18 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 问题：HBM 压力 → preemption → 重复 prefill | 并发上来后 KV 槽位占满，请求被抢占（preempt）、重新排队，同一段 2K prompt 一分钟内被 prefill 四次，goodput 远低于原始吞吐 |
| 2 | KV offloading 的思路 | 把 KV cache 从 GPU 显存搬到更便宜的层级（CPU DRAM，再往下是磁盘 / Ceph / S3），需要时再搬回来，用"搬运"替代"重算" |
| 3 | vLLM production-stack | 官方参考部署：cache-aware Router + vLLM Engines + KV 卸载层 + 可观测性（Prometheus/Grafana/OTel）+ 控制面，以 Helm chart + operator 交付 |
| 4 | Connector API | vLLM 0.9.0 引入的可插拔 KV 后端接口：引擎把块交给 connector 存，需要时从 connector 取回 |
| 5 | 0.11.0 异步卸载 | 讲义：vLLM 0.11.0（2026 年 1 月）让卸载在后台进行，常见情况下不阻塞引擎；但端到端影响取决于负载、命中率和系统压力，并非绝对免费 |
| 6 | 原生 CPU offload vs LMCache | 原生：引擎本地、存在本机内存、无网络跳、**不跨引擎**；LMCache：集群级共享缓存服务（CPU DRAM + Ceph/S3 层），任何引擎都能读 |
| 7 | 何时用 LMCache | 多租户共享 system prompt、RAG 文档块重复、同一基座上的多个 LoRA、抢占频繁的负载 |
| 8 | 何时不要开 | HBM 压力小（讲义：只付出约 3–5% 开销）、短上下文（< 1K token，搬运比重算还慢）、单租户无复用 |
| 9 | 基准测试的形状 | 16× H100（4 台 a3-highgpu-4g）：KV 占用低时所有配置与基线持平；KV 超出 HBM 时原生 CPU offload 与 LMCache 都显著提升吞吐 |
| 10 | 搬运 vs 重算的盈亏 | 只有当"从缓存层读回 KV 的时间 < 重新 prefill 的时间"时卸载才划算；本节代码的常数恰好让 LMCache 读回比重算慢 7.5 倍 |

### 核心技能（能动手做到）

- [ ] 画出 vLLM production-stack 的五个组成部分，并说明 KV 卸载层在请求路径中的位置
- [ ] 解释 Connector API 的"存 / 取"两个方向，以及异步卸载把开销藏到了哪里
- [ ] 针对给定部署（引擎数、前缀复用模式、HBM 压力）在"不开 / 原生 CPU offload / LMCache"之间做选择
- [ ] 按"KV 大小 ÷ 读取带宽"与"prompt 长度 ÷ prefill 速度"比较搬运与重算，算出盈亏平衡点
- [ ] 读懂 `simulate()` 的三种配置，指出它没有建模 HBM 容量、抢占和读回成本的地方
- [ ] 识别由 `set.pop()` 和字符串哈希随机化导致的结果不可复现问题，并用 LRU 修复

---

## 二、基础自测（选择题）

**Q1.** 讲义认为 LMCache 在 vLLM 部署中主要解决的问题是：

- A. 模型权重太大放不进单卡，需要张量并行
- B. API 网关的速率限制
- C. HBM 中 KV cache 不够用，导致请求被抢占、同样的前缀被反复 prefill
- D. tokenizer 速度太慢

**Q2.** 为 vLLM 引入可插拔 KV cache 后端接口的是：

- A. vLLM 0.9.0 的 Connector API
- B. vLLM 0.11.0 的 PagedAttention
- C. production-stack 的 Helm chart
- D. Kubernetes 的 CSI 存储接口

**Q3.** 关于"原生 vLLM CPU offload"与"LMCache connector"，说法正确的是：

- A. 原生 CPU offload 可以跨引擎共享 KV，LMCache 只能在单个引擎内使用
- B. 原生 CPU offload 把 KV 存在本引擎所在主机的内存里、不跨引擎；LMCache 是集群级共享缓存，任何引擎都能读
- C. 两者都必须依赖 Ceph 才能工作
- D. LMCache 只能存在 GPU 显存里

**Q4.** 按讲义"When NOT to enable"，下列哪种情况**最不应该**开启 KV 卸载？

- A. 多租户 SaaS，各租户共享一段 6K token 的 system prompt
- B. 并发高峰时频繁出现 preemption 事件
- C. 同一个基座模型上部署了 20 个 LoRA 变体
- D. 单租户内部工具，prompt 大多不足 500 token，HBM 利用率长期低于 50%

**Q5.** 运行 `code/main.py`，三种配置的 `speedup` 大致是：

- A. NATIVE_ONLY 1.00x，CPU_OFFLOAD 1.5x，LMCACHE 3.0x
- B. NATIVE_ONLY 1.00x，CPU_OFFLOAD 0.98x，LMCACHE 1.02x
- C. 三者都正好是 1.00x
- D. NATIVE_ONLY 1.00x，CPU_OFFLOAD 约 1.01–1.02x，LMCACHE 约 0.98–0.99x（比基线还慢）

**Q6.** 代码里 LMCACHE 配置的避免重算次数最多（194 次），总时间却最长。直接原因是：

- A. LMCache 每次命中都要额外 decode 一遍
- B. 从 LMCache 读回 KV 的代价是每块 3.0 ms（每 token 0.1875 ms），而重新 prefill 每 token 只要 0.025 ms，读回比重算慢 7.5 倍
- C. LMCache 配置把每个请求都分配到了同一个引擎
- D. LMCache 配置没有执行任何 decode

**Q7.** 连续运行几次 `python main.py`，NATIVE_ONLY 一行的 `prefill` 和 `avoided_re_prefill` 每次都可能不同（例如 8100 / 127、9650 / 114），而另两行不变。原因是：

- A. NATIVE_ONLY 分支在缓存满时调用 `set.pop()` 随机弹出一个元素，而字符串哈希在每个进程启动时随机化，弹出哪个元素随之改变
- B. `random.Random(11)` 没有设置种子
- C. `make_workload` 每次生成不同的请求
- D. 浮点数累加的舍入误差

**Q8.** 讲义描述的 16× H100 基准中，KV 占用很低（短 prompt、低并发）时的表现是：

- A. LMCache 吞吐提升 3 倍
- B. 原生 CPU offload 吞吐下降 50%
- C. 所有配置都与基线持平，LMCache 额外带来约 3–5% 开销
- D. 无法运行，必须先打开 Ceph 层

---

## 三、动手 / 代码题

**Q9.** 代码中的常数与 LMCACHE 分支：

```python
PREFILL_TOK_PER_MS = 40.0
LMCACHE_TIME_MS_PER_BLOCK = 3.0
KV_BLOCK_TOKENS = 16
...
        elif config == "LMCACHE":
            if cached_local:
                prefill_ms = 0
                re_prefills_avoided += 1
            elif cached_lmcache:
                prefill_ms = blocks * LMCACHE_TIME_MS_PER_BLOCK
                engines_state[eng].add(r.prefix_id)
                re_prefills_avoided += 1
            else:
                prefill_ms = r.prompt_tokens / PREFILL_TOK_PER_MS
```

1. 对 2000、4000、8000 token 的 prompt，分别算"重新 prefill"与"从 LMCache 读回"的毫秒数。
2. `LMCACHE_TIME_MS_PER_BLOCK` 取多少时，读回与重算恰好打平？
3. 若把它改成 0.2，你预期 LMCACHE 的 `total` 会比 NATIVE_ONLY 小还是大？

**Q10.** 代码 docstring 说"Reports re-prefill count avoided, throughput gain, and break-even HBM utilization"，讲义说它模拟"preemption-heavy workload"。请仔细读 `simulate()`，至少找出 5 处模拟与描述不符或建模不合理的地方。

**Q11.** NATIVE_ONLY 分支的本地缓存淘汰写法：

```python
                engines_state[eng].add(r.prefix_id)
                if len(engines_state[eng]) > 4:
                    engines_state[eng].pop()
```

1. 这段代码有哪两个问题？（提示：`set.pop()` 弹出哪个元素？会不会弹掉刚加入的那个？）
2. 用 `collections.OrderedDict` 改写成"容量为 4 的 LRU 缓存"，命中时要把条目移到最近使用的位置。

**Q12.** 讲义练习 2 与练习 4 的计算：

1. 某租户每小时 200 个请求共享一段 6K token 的 system prompt。按本节代码的 prefill 速度（40 token/ms），若前缀全部命中缓存，每小时能省下多少 GPU prefill 时间？
2. LMCache 把一个 4K token 的 70B FP8 KV（讲义取约 500 MB）存到机械硬盘上的 Ceph。假设顺序读取约 200 MB/s，读回需要多久？与按代码速度重算 4K token prefill 相比哪个快？如果 KV 在 CPU DRAM、经约 50 GB/s 的 PCIe 读回呢？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 KV cache offloading？它和 prefix caching（如 RadixAttention）是什么关系？

**Q14.**（原理深挖）vLLM 在 HBM 不够时会发生什么？preemption 有哪两种处理方式，为什么卸载到 CPU 能改善它？

**Q15.**（工程实践）你负责一个 8 卡 vLLM 集群，团队想上 LMCache。你会先看哪些指标来判断值不值得？上线后用什么来验证？

**Q16.**（场景设计）LMCache 服务器是单点。请设计它的高可用方案（讲义练习 3），并说明故障时请求路径如何降级。

**Q17.**（追问型）"vLLM 0.11.0 的异步卸载是免费的吗？"开销藏在哪里？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义的问题描述："GPUs at 100% HBM with preemption events ... you re-prefill the same 2K-token prompt four times in a minute." LMCache 把 KV 搬到 CPU DRAM，"so preempted requests recover fast, and repeated prefixes across engines share cache"。A 是模型并行问题；B 是网关（下一节）的事；D 与 KV 无关。

### Q2 — 答案：A

讲义："vLLM 0.9.0 introduced a Connector API for pluggable KV cache backends." B 错在两处：0.11.0 增加的是异步卸载路径，PagedAttention 是更早的显存分页机制（阶段 17 · 04）。C 是部署形态而非 KV 接口。D 是 K8s 存储卷接口，与 vLLM 无关。

### Q3 — 答案：B

讲义："Native vLLM CPU offload: engine-local ... Does not cross engines." "LMCache connector: cluster-scale ... Blocks are accessible to any engine." A 把两者对调了；C 错，Ceph 只是 LMCache 的可选下层；D 错，LMCache 的意义正是把 KV 移出 GPU。

### Q4 — 答案：D

D 同时命中讲义的三条"不要开"：短上下文（< 1K）、HBM 压力小、单租户无复用——只会付出约 3–5% 的开销。A（共享 system prompt）、B（抢占频繁）、C（同基座多 LoRA）都是讲义"When LMCache is decisive"里点名的场景。

### Q5 — 答案：D

实际运行结果：

```text
NATIVE_ONLY     total=  374133 ms  prefill=   8100 ms  avoided_re_prefill= 127  speedup=1.00x
CPU_OFFLOAD     total=  369402 ms  prefill=   3369 ms  avoided_re_prefill= 176  speedup=1.01x
LMCACHE         total=  380833 ms  prefill=  14800 ms  avoided_re_prefill= 194  speedup=0.98x
```

（多次运行时 NATIVE_ONLY 一行会变，speedup 在 1.01–1.02x / 0.98–0.99x 之间浮动，见 Q7。）三者差别都很小，因为 200 个请求的 decode 总时间约 366,033 ms，占总时间的 97% 以上；prefill 部分即使全部省掉也只有 22,850 ms。A 是讲义"Read:"想传达的印象，但代码给不出来；B 把两者对调了；C 忽略了确实存在的小差异。

### Q6 — 答案：B

每 token 读回代价 = `3.0 ms / 16 token = 0.1875 ms`；每 token prefill 代价 = `1 / 40 = 0.025 ms`；比值 7.5。所以"命中 LMCache"反而比"重新 prefill"更慢：8000 token 的 prompt 读回要 1500 ms，重算只要 200 ms。LMCACHE 的 `prefill=14800 ms` 中绝大部分是读回时间。A、D 与代码不符（decode 对三种配置完全相同）；C 错，引擎是 `rng.randrange(4)` 随机选的。

这是代码与讲义结论最大的矛盾：打印的 "Read: ... LMCache avoids redundant prefills" 只说了"避免了"，却没说"避免的代价比重算还高"。

### Q7 — 答案：A

`engines_state` 是 `set[str]`，`set.pop()` 弹出的是哈希表里"第一个"元素，取决于字符串的哈希值；而 Python 默认对 `str` 哈希做随机化（`PYTHONHASHSEED`），每个进程不同。我们用 `PYTHONHASHSEED=0/1/2/3` 分别运行，NATIVE_ONLY 的 prefill 依次是 9650、9650、9100、10100 ms，避免次数 114、111、118、115。CPU_OFFLOAD 与 LMCACHE 分支从不调用 `pop()`，所以稳定。B 错：`random.Random(11)` 有固定种子；C 错：`make_workload` 用固定种子 7；D 错：舍入误差不会改变计数。

### Q8 — 答案：C

讲义："Low KV footprint (short prompts, low concurrency): all configs match baseline, LMCache adds ~3-5% overhead." A 描述的是 KV 超出 HBM 的情形下"substantially improve"，且讲义没有给出 3 倍这个数字；B、D 无出处。

### Q9 — 参考答案

1. 块数 = `ceil(prompt / 16)`；读回 = 块数 × 3.0 ms；重算 = prompt / 40：

| prompt | 块数 | 重算 prefill | LMCache 读回 |
|--------|------|-------------|-------------|
| 2000 | 125 | 50 ms | 375 ms |
| 4000 | 250 | 100 ms | 750 ms |
| 8000 | 500 | 200 ms | 1500 ms |

2. 打平条件：`每块读回时间 = 16 × 0.025 = 0.4 ms`。只有 `LMCACHE_TIME_MS_PER_BLOCK < 0.4` 时，命中 LMCache 才比重算快。
3. 会**更小**。实际运行验证：设为 0.4 时 LMCACHE total = 368,483 ms；设为 0.2 时 total = 367,533 ms，prefill 只有 1,500 ms，优于 NATIVE_ONLY（约 374,000 ms）和 CPU_OFFLOAD（369,402 ms）。

结论：缓存是否值得，取决于"读回带宽"与"重算算力"的比值，这正是讲义"Short contexts (<1K tokens) — transfer time > re-prefill"背后的道理。

### Q10 — 参考答案

1. **`hbm_capacity_blocks_per_engine = 900` 定义了但从未使用**：没有任何 HBM 容量约束，所谓"break-even HBM utilization"根本没有计算，也没有输出。
2. **没有 preemption**：请求逐个串行处理，不存在并发，也就不存在"KV 满了被抢占"；"preemption-heavy"只是标题。
3. **CPU_OFFLOAD 永不淘汰**：该分支只 `add` 不 `pop`，本地缓存无限大，等于假设 HBM 无限；而且卸载的"写出"代价被乘了 `0.1`（`blocks * 1.5 * 0.1`），从 CPU"读回"的代价却完全没算（命中时 `prefill_ms = 0`）。它领先完全是因为"不淘汰 + 读回免费"。
4. **LMCACHE 的本地缓存也永不淘汰**，与 NATIVE_ONLY 的"最多 4 个"不对等，比较不公平。
5. **前缀粒度不对**：`prefix_id` 只有 6 种，但同一 `prefix_id` 的请求 prompt 长度是 2000/4000/8000 随机的；命中时整段 prompt 都算作免 prefill，相当于假设"整个 prompt 都是共享前缀"。真实的前缀复用只覆盖共享部分，剩余部分仍要 prefill。
6. **"avoided_re_prefill" 的含义被夸大**：它统计的是所有缓存命中，包括某引擎第一次见到但别的引擎算过的情况，不全是"重新 prefill"。
7. **NATIVE_ONLY 用 `set.pop()` 淘汰**：随机弹出、可能弹掉刚加入的元素，且结果随哈希种子变化（见 Q7、Q11）。
8. **没有吞吐**：`speedup` 是总串行时延之比，不是吞吐提升；decode 占 97% 以上，掩盖了 prefill 差异。
9. 小问题：`main()` 为每个配置复制了一份 `Request` 列表，但 `simulate` 并不修改请求，复制是多余的。

### Q11 — 参考答案

1. 两个问题：
   - `set.pop()` 弹出的是**任意**元素，不是"最久未使用"的那个，不符合任何缓存策略；而且它可能弹掉**刚刚加入**的 `r.prefix_id`，导致刚 prefill 完的前缀立即丢失。
   - 结果依赖字符串哈希顺序，而 `str` 哈希每个进程随机化，导致同样的代码多次运行结果不同（不可复现）。
2. LRU 改写：

```python
from collections import OrderedDict

CAP = 4
engines_state: list[OrderedDict] = [OrderedDict() for _ in range(4)]

def lookup_and_touch(cache: OrderedDict, key: str) -> bool:
    if key in cache:
        cache.move_to_end(key)        # 命中：移到"最近使用"端
        return True
    return False

def insert(cache: OrderedDict, key: str) -> None:
    cache[key] = True
    cache.move_to_end(key)
    if len(cache) > CAP:
        cache.popitem(last=False)     # 淘汰最久未使用的一端
```

   在 `simulate` 中把 `cached_local = r.prefix_id in engines_state[eng]` 换成 `lookup_and_touch(...)`，把 `add + pop` 换成 `insert(...)`。改完后结果与 `PYTHONHASHSEED` 无关，可复现。

### Q12 — 参考答案

1. 第一个请求需要 prefill，其余 199 个命中：每次省 `6000 / 40 = 150 ms`，每小时共省 `199 × 150 = 29,850 ms ≈ 29.9 s` 的 GPU prefill 时间（按代码的示意速度）。若存在多个引擎且没有跨引擎共享，每个引擎都要先 prefill 一次，这正是 LMCache 相对原生 offload 的优势所在。
2. - 机械盘 Ceph：`500 MB ÷ 200 MB/s = 2.5 s`；按代码速度重算 4K prefill 只要 `4096 / 40 ≈ 102 ms`。**重算快约 24 倍**——机械盘这一层对 4K 级别的 KV 没有意义，只适合做"冷数据持久化"或极长上下文。
   - CPU DRAM 经 PCIe（约 50 GB/s）：`0.5 GB ÷ 50 GB/s = 10 ms`，比重算快约 10 倍，这才是 LMCache 的主战场。
   - 结论：缓存层级越往下，容量越大、读回越慢；每一层都要做"读回时间 vs 重算时间"的比较。注意 70B 真实 KV（8 个 KV 头、FP8）约 163,840 字节/token，4K 约 671 MB，讲义的 500 MB 略偏小。

### Q13 — 参考回答要点

- **定义**：把 GPU 显存里的 KV cache 块移到更便宜的存储层（CPU DRAM → 本地 SSD → 分布式存储），需要时再加载回 GPU，避免重新 prefill。
- **与 prefix caching 的关系**：prefix caching（RadixAttention / vLLM APC）解决"识别并复用相同前缀"；KV offloading 解决"复用的 KV 存在哪里、HBM 放不下怎么办"。二者叠加：前缀缓存的容量从"HBM 剩余空间"扩大到"HBM + DRAM + 磁盘"，命中率随之提高。
- **跨引擎**：本地卸载只扩容不共享；LMCache 这类共享层让引擎 A 算出的前缀能被引擎 B 使用，配合 cache-aware 路由效果最佳。
- **代价**：搬运带宽、额外的内存与服务、一致性和故障处理。
- 加分点：说出"读回时间 < 重算时间"是值得卸载的前提，并能估算 PCIe 与 prefill 的量级。

### Q14 — 参考回答要点

- **现象**：continuous batching 下，并发增加 → KV 块分配完 → 调度器必须抢占一些正在运行的请求，腾出块给其它请求。
- **两种处理**：
  - **recompute**：直接丢弃被抢占请求的 KV，之后重新 prefill（讲义所说的"re-prefill the same prompt four times"）；
  - **swap**：把 KV 换出到 CPU 内存，之后换回。
- **为什么卸载能改善**：恢复成本从"一次完整 prefill（算力）"变成"一次 PCIe 搬运（带宽）"，长 prompt 时后者便宜得多；同时卸载层还能保存已完成请求的前缀供以后复用。
- **监控**：preemption 次数、HBM 利用率 P99、`--gpu-memory-utilization` 的余量；skill 文件建议在 HBM 持续 92% 以上时告警。
- 加分点：说明 goodput（满足 SLO 的吞吐）与原始吞吐的差距就是重复 prefill 等浪费。

### Q15 — 参考回答要点

- **判断值不值得**：
  - HBM 压力：利用率 P99、preemption 事件频率、请求排队时间；
  - 复用潜力：前缀命中率、共享 system prompt / RAG 文档的重复度、不同引擎之间的前缀重叠；
  - prompt 长度分布：大多 < 1K 就别开；
  - 读回 vs 重算：用实测 PCIe/网络带宽与 prefill 吞吐比较。
- **选型**：单引擎有压力 → 原生 CPU offload；多引擎共享前缀 → LMCache；都没有 → 不开（skill：< 2 个引擎拒绝 LMCache）。
- **验证**：灰度上线，对比 TTFT P99、prefill GPU 时间占比、goodput、命中率、LMCache 读回时延 P99；同时确认低负载时的开销在 3–5% 以内。
- 常见误区：只看"命中次数"而不看"命中后读回耗时"——本节代码就是反例。

### Q16 — 参考回答要点

- **把 LMCache 当作"可丢失的缓存"而不是"数据源"**：任何缓存失效都只能导致回退到重算，绝不能导致请求失败。
- **冗余**：LMCache 多副本或分片 + 副本，前面有健康检查；按前缀哈希做一致性哈希分片，单节点故障只损失一部分缓存。
- **降级路径**：connector 超时（设置严格的读回超时，例如低于重算时间）→ 回退到引擎本地 CPU offload → 再回退到重新 prefill。
- **容量与持久化**：DRAM 层做热数据，Ceph/S3 层做冷数据和重启后的预热。
- **观测**：读回时延 P99、超时率、命中率、回退率；故障演练（见阶段 17 · 24 混沌工程）。
- 加分点：说明 cache-aware 路由需要感知 LMCache 状态，故障时要停止把请求路由到"以为有缓存"的引擎上。

### Q17 — 参考回答要点

- **不免费**。异步只是把"写出 KV"从请求关键路径上挪走，开销依然存在：
  - PCIe / 网络带宽被卸载流量占用，可能与模型加载、其它传输争用；
  - CPU 与主机内存资源（固定内存、拷贝线程）；
  - **读回**仍然可能在关键路径上：命中缓存时请求要等 KV 加载完才能开始 decode；
  - 调度复杂度：讲义提到 vLLM 自己的说明——自定义 kernel 的卸载在低命中率时可能降低吞吐，异步调度与 speculative decoding 存在已知的交互问题。
- **低负载时纯开销**：讲义基准显示 KV 占用低时 LMCache 约 3–5% 开销而无收益。
- 加分点：给出验证方法——在真实流量回放下对比开/关时的吞吐、TTFT P99 与 TPOT P99，而不是相信"异步"二字。

---

## 六、关联知识点

### 前置知识
- [阶段 17 · 04 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill](../../04-vllm-serving-internals/docs/zh.md)：KV 块分配、抢占与 continuous batching 的基础。
- [阶段 17 · 06 前缀缓存服务：RadixAttention 与 KV 复用](../../06-sglang-radixattention/docs/zh.md)：前缀复用的机制，本节在它之上扩容到 CPU/磁盘与跨引擎。
- [阶段 07 · 12 KV Cache、Flash Attention 与 Inference 优化](../../../07-transformers-deep-dive/12-kv-cache-flash-attention/docs/zh.md)：KV cache 的大小与作用。
- [阶段 17 · 08 Inference 指标：TTFT、TPOT、ITL、Goodput、P99](../../08-inference-metrics-goodput/docs/zh.md)：评估卸载效果要看的指标。

### 本节被哪些后续内容用到
- [阶段 17 · 17 Prefill 与 Decode 分离：NVIDIA Dynamo 与 llm-d](../../17-disaggregated-prefill-decode/docs/zh.md)：分离式传输的 KV 可以落入 LMCache 供后续复用。
- [阶段 17 · 11 多区域 LLM 服务与 KV Cache 局部性](../../11-multi-region-kv-locality/docs/zh.md)：cache-aware 路由消费 KV 事件。
- [阶段 17 · 13 LLM Observability 技术栈选型](../../13-llm-observability/docs/zh.md)：production-stack 的可观测性组件。
- [阶段 17 · 24 LLM 生产环境中的混沌工程](../../24-chaos-engineering-llm/docs/zh.md)：缓存层故障的演练。
- [阶段 17 · 28 自托管服务选型：让引擎匹配硬件与规模](../../28-self-hosted-serving-selection/docs/zh.md)：何时值得引入完整的 production-stack。

### 延伸关键词
`vLLM production-stack` · `LMCache` · `KV Connector API` · `KV offloading` · `preemption (recompute / swap)` · `prefix caching` · `cache-aware routing` · `--gpu-memory-utilization` · `CPU DRAM tier` · `Ceph / S3 tier` · `LRU eviction` · `PYTHONHASHSEED`
