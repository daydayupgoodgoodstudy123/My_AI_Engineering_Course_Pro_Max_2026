# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 04 节 服务引擎内部机制：PagedAttention、Continuous Batching 与 Chunked Prefill ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`collections.deque`、`random`、`statistics`），无需 GPU

---

## 1. 这份代码在考察什么

这是一个**虚拟时钟上的玩具 serving 调度器**，在同一份 60 个请求的工作负载上比较四种模式：

| 模式 | 对应讲义概念 |
|------|------------|
| `NAIVE` | 朴素 PyTorch 循环：一次一个请求，prefill 完再逐 token decode |
| `STATIC` | 经典静态批处理：16 个一组，填充到最长 prompt / 最长输出，整批等最慢者 |
| `CONTINUOUS` | 迭代级 continuous batching：每步移除已完成序列、在 KV block 够用时接纳新序列 |
| `CONTINUOUS + CHUNKED` | 再加 chunked prefill：每个请求每步最多 prefill 512 token，与 decode 交错 |

输出吞吐（tok/虚拟秒）、平均 TTFT、P99 ITL。讲义说的是"`CONTINUOUS + CHUNKED` 应该占优"。

> 一句话：**用一个可读的调度循环把 vLLM 的三个默认机制串起来**——尤其是看清 chunked prefill 如何削平 ITL 尖峰。但要注意：实际运行中 STATIC 吞吐最高（4055 vs 886 tok/s），原因是两种模式用了**不一致的成本模型**（见 3.5 与第 6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 成本常量 | 常量 | decode 每 token 0.5ms、prefill 每 token 0.04ms、每次前向 0.2ms 固定开销、块 512、block 16 token、KV 预算 1800 block | 虚拟 GPU 成本模型 |
| `Request` | `@dataclass` | 请求状态：已 prefill / 已生成 token 数、TTFT、ITL 样本；`in_prefill`、`done`、`blocks_needed()` | 序列状态 + KV block 需求 |
| `make_workload` | 函数 | 60 个请求，泊松到达约 40 req/s，prompt 取 {128, 256, 512, 2048, 8192}，输出 50–300 | 混合长度流量 |
| `report` | 函数 | 计算吞吐、平均 TTFT、P99 ITL 并打印 | 服务指标 |
| `simulate_naive` | 函数 | 串行处理 | 无批处理基线 |
| `simulate_static` | 函数 | 固定 16 个一组、填充 | 静态批处理 |
| `simulate_continuous` | 函数 | `WAITING` deque + `RUNNING` 列表的迭代级调度，可选 chunked | V1 调度器思路 |
| `main` | 函数 | 每种模式复制一份新请求后运行并报告 | 公平对比 |

数据流：`make_workload()` → 复制 4 份 → 各 `simulate_*` 推进虚拟时钟、填写每个请求的 `ttft / itl_samples / generated` → `report` 汇总。

---

## 3. 逐段精讲

### 3.1 成本常量：整个模拟的"物理定律"

```python
FORWARD_LATENCY_PER_TOKEN = 0.0005   # 0.5 ms per decode token in the batch
PREFILL_LATENCY_PER_TOKEN = 0.00004  # prefill ~12x cheaper per token than decode
BATCH_OVERHEAD = 0.0002              # fixed overhead per forward call
CHUNK_SIZE = 512
KV_BLOCK_SIZE = 16
KV_BLOCKS_AVAILABLE = 1800           # toy KV block budget
```

- prefill 每 token 比 decode 便宜 12.5 倍：体现"prefill 一次并行处理很多 token、算力利用率高"。8192 token 的 prefill 需要 `8192 × 0.04ms ≈ 0.33s`。
- decode 每个 token 0.5ms，**按 batch 中的 token 数线性增长**（在 CONTINUOUS 中）。这与真实 GPU 不符：decode 是 memory-bound，一步 decode 的主要成本是读一遍权重，batch 从 1 增到几十时单步耗时增长很慢——这正是批处理的收益来源。
- KV 预算 1800 block × 16 = 28,800 token。

### 3.2 `Request`：序列状态与 KV 需求

```python
@dataclass
class Request:
    req_id: int
    prompt_len: int
    output_len: int
    arrived_at: float
    prefilled: int = 0
    generated: int = 0
    ttft: float | None = None
    last_token_at: float | None = None
    itl_samples: list[float] = field(default_factory=list)

    @property
    def in_prefill(self) -> bool:
        return self.prefilled < self.prompt_len

    @property
    def done(self) -> bool:
        return self.generated >= self.output_len

    def blocks_needed(self) -> int:
        total = self.prompt_len + self.output_len
        return (total + KV_BLOCK_SIZE - 1) // KV_BLOCK_SIZE
```

- `prefilled` 记录已经算过 KV 的 prompt token 数，chunked prefill 时它会分多步增长；`in_prefill` 据此判断该序列本步做 prefill 还是 decode。
- `itl_samples` 用 `field(default_factory=list)`：可变默认值必须这样写，否则所有实例会共享同一个列表。
- `blocks_needed()` 是向上取整除法 `ceil(total / 16)`。⚠️ 它包含了 `output_len`——在准入时就按"真实输出长度"一次性预留全部 block。真实系统既不知道输出长度，PagedAttention 也是按需追加 block 的；这里更像"按实际长度的连续预留"。
- `ttft` 存的是**绝对时间**，`report` 中再减去 `arrived_at`。

### 3.3 `make_workload`：短长混合 + 突发到达

```python
    for i in range(n):
        now += rng.expovariate(40.0)   # ~40 req/s arrival
        prompt_len = rng.choice([128, 256, 512, 2048, 8192])
        out_len = rng.randint(50, 300)
```

- 指数分布的到达间隔 = 泊松过程，平均 25ms 一个请求。60 个请求在 0.01–1.31 秒内全部到达，整体上更像一个"突发"，系统大部分时间在消化积压。
- `seed=7` 时 prompt 分布为 128×11、256×14、512×10、2048×12、8192×13，总 prompt 141,184 token、总输出 9,419 token。8192 token 的长 prompt 占 13 个，是制造 ITL 尖峰的主角。

### 3.4 `report`：三个指标的算法

```python
    ttfts = [r.ttft - r.arrived_at for r in reqs if r.ttft is not None]
    itls = [dt for r in reqs for dt in r.itl_samples]
    total_out = sum(r.generated for r in reqs)
    throughput = total_out / sim_end if sim_end else 0
    mean_ttft = statistics.mean(ttfts) * 1000 if ttfts else 0
    p99_itl = sorted(itls)[int(0.99 * len(itls)) - 1] * 1000 if itls else 0
```

- 吞吐只算**输出 token**，分母是模拟结束时刻（包括第一个请求到达前的空闲）。
- `itls` 用双层推导式把所有请求的 ITL 样本展平。
- P99 用排序后取下标 `int(0.99n) − 1`，比"最近秩"定义（`ceil(0.99n) − 1`）偏前一两个位置。n = 9,419 时两者是相邻元素；在 CONTINUOUS（无 chunk）中这两个相邻值分别是 219.3ms 和 262.2ms，可见尾部分布非常陡，P99 的定义细节会影响报告值。生产中用 `statistics.quantiles` 或 NumPy 的 `percentile` 并注明插值方法。

### 3.5 `simulate_naive` 与 `simulate_static`

```python
def simulate_naive(reqs):
    for r in reqs:
        ...
        now += r.prompt_len * PREFILL_LATENCY_PER_TOKEN + BATCH_OVERHEAD
        ...
        for _ in range(r.output_len):
            now += FORWARD_LATENCY_PER_TOKEN + BATCH_OVERHEAD
```

NAIVE：每个输出 token 0.7ms，没有批处理也没有交错，所以 P99 ITL 只有 0.7ms，但后面的请求要等前面全部完成，平均 TTFT 5.87 秒。

```python
def simulate_static(reqs, batch=16):
    while i < len(reqs):
        window = reqs[i:i + batch]
        now = max(now, max(r.arrived_at for r in window))
        pad_prompt = max(r.prompt_len for r in window)
        pad_output = max(r.output_len for r in window)
        now += pad_prompt * PREFILL_LATENCY_PER_TOKEN + BATCH_OVERHEAD
        ...
        for _ in range(pad_output):
            now += FORWARD_LATENCY_PER_TOKEN * len(window) / 16 + BATCH_OVERHEAD
            for r in window:
                if r.generated < r.output_len:
                    r.generated += 1
```

- 整批等到最后一个请求到达才开始（`max(arrived_at)`），整批的 TTFT 相同，decode 步数 = 批内最长输出。这些都正确体现了"填充 + 等最慢"。
- ⚠️ **成本模型给了 STATIC 两个 1/16 折扣**：
  1. prefill 只按 `pad_prompt` 收费，而实际要算 `16 × pad_prompt` 个（填充后的）token；
  2. decode 每步 `0.5ms × 16 / 16 + 0.2ms = 0.7ms` 服务 16 个序列，而 CONTINUOUS 每步按 `batch_tokens × 0.5ms` 计费、没有摊薄。
- ⚠️ STATIC 完全不检查 KV 预算：4 个批次按填充长度分别需要 8,496、8,480、8,464、6,372 个 block，远超 `KV_BLOCKS_AVAILABLE = 1800`。
- 按填充计算，4 个批次共占 508,416 个 token 槽位，真实只有 150,603 个，70.4% 是填充——但这些填充在成本里几乎没有体现。

### 3.6 `simulate_continuous`：迭代级调度循环

**准入**：

```python
    waiting = deque(sorted(reqs, key=lambda r: r.arrived_at))
    running: list[Request] = []
    blocks_used = 0
    while waiting or running:
        if waiting and running and now < waiting[0].arrived_at and not running:
            now = waiting[0].arrived_at
        while waiting and waiting[0].arrived_at <= now:
            r = waiting[0]
            if blocks_used + r.blocks_needed() > KV_BLOCKS_AVAILABLE:
                break
            blocks_used += r.blocks_needed()
            running.append(waiting.popleft())
        if not running:
            if not waiting:
                break
            now = waiting[0].arrived_at
            continue
```

- `WAITING` 用 `deque`，`popleft()` 是 O(1)。准入是严格 FCFS：队首放不下就 `break`，后面的短请求也不能插队（head-of-line blocking），vLLM 默认策略同样是 FCFS。
- ⚠️ 第一个 `if` 的条件同时要求 `running` 和 `not running`，**永远为假**，是死代码；"空闲时快进到下一个到达"实际由后面的 `if not running` 完成。
- 插桩统计：RUNNING 最多 16 个序列，准入因 KV 不足被拦截 987 次（chunked 版 1,049 次），`blocks_used` 峰值 1,796/1,800。一个"8192 + 300"的请求要 531 个 block，最多同时容纳 3 个。玩具模型是**KV 受限**的。

**组 batch 与计费**：

```python
        for r in running:
            if r.in_prefill:
                remaining = r.prompt_len - r.prefilled
                take = min(CHUNK_SIZE if chunked else remaining, remaining)
                r.prefilled += take
                prefill_work += take
                if r.prefilled >= r.prompt_len:
                    r.ttft = now + prefill_work * PREFILL_LATENCY_PER_TOKEN
            else:
                decoded.append(r)
                batch_tokens += 1

        dt = (prefill_work * PREFILL_LATENCY_PER_TOKEN
              + batch_tokens * FORWARD_LATENCY_PER_TOKEN
              + BATCH_OVERHEAD)
        now += dt
```

- 同一步里，prefill 中的序列各贡献一块 prompt（chunked 时最多 512），decode 中的序列各贡献 1 个 token，合成"一次融合前向"，耗时为各部分之和。这就是讲义伪代码 `run_forward(batch)` 的实现。
- 不开 chunk 时，一个新到的 8192 token 请求会让这一步多出 0.33 秒，本步所有 decode 序列的 ITL 都被拉长——P99 ITL 219.3ms 的来源。开 chunk 后每个请求每步最多 512 token（约 20ms），尖峰被削平到 66.1ms。
- ⚠️ chunk 上限是**每个请求**的，而不是每步的全局 token 预算；同时有多个请求在 prefill 时，一步仍可能做数千个 prefill token。真实 vLLM 用 `max_num_batched_tokens` 做全局预算（讲义练习 2，测验 Q12）。
- TTFT 记为"本步中到该请求为止的累计 prefill 时间"，没有计入本步的 decode 和固定开销，略有低估；而且 prefill 完成后的第一个输出 token 要到下一步才产生，与 vLLM"prefill 的最后一步同时产出第一个 token"的语义略有差异。

**记录 ITL 与释放**：

```python
        for r in decoded:
            prev = r.last_token_at or r.ttft or now
            r.generated += 1
            r.itl_samples.append(now - prev)
            r.last_token_at = now
            if r.ttft is None:
                r.ttft = now

        finished = [r for r in running if r.done]
        for r in finished:
            blocks_used -= r.blocks_needed()
            running.remove(r)
```

- `a or b or c`：返回第一个"真值"。第一个输出 token 的 ITL 以 `ttft` 为起点。
- 完成的序列立刻归还 block，下一步就能接纳新序列——这就是 continuous batching 相对 STATIC 的核心优势（STATIC 中快请求的"槽位"要空等到整批结束）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 虚拟时钟 + 线性成本 | 无需 GPU、结果确定 | 成本模型决定一切；STATIC 与 CONTINUOUS 用了不同的模型，结论被扭曲。应使用同一个"单步耗时 = f(prefill token, decode 序列数)"函数，并让 decode 呈 memory-bound 形状 |
| 准入时按 prompt+output 一次性预留 block | 不必实现抢占 | 依赖提前知道输出长度；vLLM 按需追加 block，不足时抢占（recompute 或 swap） |
| 每请求 512 的 chunk 上限 | 实现简单 | 没有全局 token 预算；vLLM 用 `max_num_batched_tokens` |
| 严格 FCFS | 公平、与 vLLM 默认一致 | 长请求造成队首阻塞；可按优先级或 SLO 分队列 |
| STATIC 忽略 KV 预算 | 代码短 | 实际上放不下；对比不公平 |
| 60 个请求在 1.3 秒内到齐 | 制造积压 | 更像离线批处理；continuous batching 的"随时接纳"在稳态流式到达时优势更明显 |
| 下标法 P99 | 简单 | 小样本或陡尾时与标准分位数定义有差异 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + `field(default_factory=list)` | `itl_samples: list[float] = field(default_factory=list)` | 每个实例一个独立的新列表；直接写 `= []` 会报错（dataclass 禁止可变默认值） |
| `@property` | `def in_prefill(self) -> bool` | 把方法当属性用：`r.in_prefill` 不加括号 |
| 向上取整整除 | `(total + KV_BLOCK_SIZE - 1) // KV_BLOCK_SIZE` | 不用 `math.ceil` 的整数写法 |
| `collections.deque` | `waiting.popleft()` | 两端 O(1) 出入队，适合 FIFO 队列 |
| `rng.expovariate(40.0)` | 到达间隔 | 指数分布，均值 1/40 秒 |
| `rng.choice` / `rng.randint` | prompt 长度、输出长度 | 从列表中随机取一个 / 闭区间整数 |
| 嵌套推导式 | `[dt for r in reqs for dt in r.itl_samples]` | 展平二维结构；顺序同两层 for 循环 |
| `statistics.mean` | `statistics.mean(ttfts)` | 标准库求均值 |
| 布尔求和 | `sum(r.done for r in reqs)` | `True` 当 1、`False` 当 0 |
| `or` 链式取默认值 | `r.last_token_at or r.ttft or now` | 返回第一个真值；注意 `0.0` 也是假值 |
| 切片 | `reqs[i:i + batch]` | 超出范围自动截断，最后一批只有 12 个 |
| 列表复制构造 | `[Request(r.req_id, ...) for r in base]` | 每种模式用全新的请求对象，避免状态互相污染 |
| f-string 格式 | `{label:28}`、`{throughput:6.0f}`、`{p99_itl:5.1f}` | 宽度与小数位 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不运行 `main()`（本讲解的插桩实验依赖这一点） |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 1 秒）：

```text
NAIVE                         throughput=   768 tok/s   mean_TTFT=5870.5 ms   P99_ITL=  0.7 ms   finished=60/60
STATIC (batch=16, padded)     throughput=  4055 tok/s   mean_TTFT= 691.3 ms   P99_ITL=  0.7 ms   finished=60/60
CONTINUOUS (no chunk)         throughput=   886 tok/s   mean_TTFT=4671.6 ms   P99_ITL=219.3 ms   finished=60/60
CONTINUOUS + CHUNKED          throughput=   885 tok/s   mean_TTFT=4591.5 ms   P99_ITL= 66.1 ms   finished=60/60

Read the CONTINUOUS+CHUNKED row. That is what vLLM ships as default.
The gap between STATIC and CONTINUOUS is the whole reason vLLM exists.
```

逐项解读：

- **NAIVE**：768 tok/s，平均 TTFT 5.9 秒（排队），ITL 恒为 0.7ms（没有别人打扰）。
- **STATIC 4055 tok/s 是成本模型的产物**：prefill 和 decode 都享受了 1/16 折扣，又不受 KV 预算约束。修正为与 CONTINUOUS 相同的线性成本后（已实际运行），STATIC 降到 **329 tok/s、平均 TTFT 15.2 秒**；只修正 prefill 计费时为 456 tok/s。修正后 CONTINUOUS（886）才明显领先，与讲义一致。
- **CONTINUOUS 只比 NAIVE 高 15%**：因为 decode 成本按 batch 线性增长、批处理没有收益；它的优势只来自"prefill 与 decode 交错"和"完成即释放"。若给 CONTINUOUS 的 decode 也加上 `/16` 摊薄（已实际运行），吞吐升到约 **1,510 tok/s**，平均 TTFT 降到约 2.8 秒。
- **chunked prefill 的效果被正确体现**：吞吐几乎不变（886 → 885），P99 ITL 从 219.3ms 降到 66.1ms（约 3.3 倍）。这与讲义"P99 ITL 约 50ms → 15ms""chunking 不单独提升吞吐"的形状一致。两者 ITL 中位数都是 4.2ms，差异只在尾部（无 chunk 最大 745ms，有 chunk 最大 115ms）。
- **TTFT 很高**：60 个请求 1.3 秒内到齐，而 KV 预算最多同时放 3 个长请求，大量请求在 WAITING 中排队。

---

## 7. 动手改一改

1. **统一成本模型**（最重要）：写一个 `step_cost(prefill_tokens, decode_seqs)` 函数，例如 `prefill_tokens × 0.04ms + (0.5ms + decode_seqs × 0.02ms if decode_seqs else 0) + 0.2ms`，让三种批处理模式都用它；STATIC 的 prefill 按 `16 × pad_prompt` 计。重新比较四种模式（讲义练习 1）。
2. **全局 token 预算**（讲义练习 2）：加 `MAX_NUM_BATCHED_TOKENS`，decode 优先、剩余预算分给 prefill，扫描 512/2048/8192 并画出 P99 ITL 与平均 TTFT 的折线（参考实现见测验 Q12）。
3. **按需分配 + 抢占**：准入只分配 prompt 的 block，decode 每满 16 个 token 追加 1 个；block 不够时抢占最新加入的序列（释放其 block、`prefilled = 0` 放回 WAITING 队首），统计抢占次数。
4. **碎片计算**（讲义练习 4）：生成 1,000 个输出长度 ~N(1500, 600)，比较 8192 连续预留（约 81.6% 浪费）与 16-token block（约 0.5%）的浪费。
5. **稳态流量**：把到达率改成 5 req/s、请求数改成 600，观察 CONTINUOUS 与 STATIC 的 TTFT 差距如何变化（STATIC 要等凑满 16 个才开始）。
6. **修正 P99 与死代码**：用 `statistics.quantiles(itls, n=100)[98]` 计算 P99；删掉永远为假的 `if`。

---

## 8. 常见坑

- **两种模式用不同的成本函数**：任何"A 比 B 快"的模拟结论都先检查是不是同一个成本模型；本文件的 STATIC 就因此"赢"了。
- **让 decode 成本随 batch 线性增长**：这抹掉了批处理的全部意义；decode 是 memory-bound，单步耗时对 batch 大小不敏感（直到算力或 KV 带宽打满）。
- **以为 chunked prefill 能提高吞吐**：它保护的是 ITL 尾部；吞吐收益来自更高的可用并发（goodput），而不是更少的计算。
- **只做每请求的 chunk 上限**：多个请求同时 prefill 时一步仍可能很长，需要全局 token 预算。
- **准入时假设已知输出长度**：真实系统只知道 `max_tokens`；按上限预留就退回了经典连续分配的浪费。
- **忽略 KV 预算**：STATIC 的填充批次在真实显存里根本放不下。
- **用 64 个查询头算 Llama 3 系列的 KV cache**：GQA 模型应使用 KV 头数（8 个），否则高估 8 倍。
- **可变默认参数**：dataclass 中的列表字段必须用 `field(default_factory=list)`。
