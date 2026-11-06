# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 03 节 Kubernetes 上的 GPU Autoscaling：Karpenter、KAI Scheduler 与成组调度 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`random`），不需要 Kubernetes、GPU 或网络

---

## 1. 这份代码在考察什么

这是一个**离散时间（每 15 秒一个 tick）的 autoscaler 模拟器**，在同一份突发流量上比较三种副本伸缩策略：

1. `DUTY_CYCLE`：模仿 HPA 按 `DCGM_FI_DEV_GPU_UTIL` 伸缩（讲义所说的"坏默认"）。
2. `QUEUE_DEPTH`：按队列深度伸缩（讲义推荐的信号）。
3. `KAI_GANG`：名义上是"成组调度 + 拓扑感知"，实际上是阈值更低、步子更大的队列深度策略。

它想让你体会的讲义概念：

- 应用层伸缩信号的选择（duty cycle vs 队列深度）；
- 节点供给 + 模型加载的冷启动（`50 + 45 = 95` 秒）如何与请求超时（30 秒）赛跑；
- 丢弃请求数与空闲 GPU 时间之间的取舍。

> 一句话：**autoscaler 的好坏要同时看"丢了多少请求"和"浪费了多少 GPU"**。但请注意：这份代码的实际输出与讲义及代码自己的结论文字**相反**——DUTY_CYCLE 丢得最少。读懂"为什么"，比记住结论更有价值（见 3.5 与第 6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| 模块常量 | 常量 | 供给时间、加载时间、服务时间、副本上下限、tick、目标利用率 | 冷启动 / HPA 参数 |
| `Request` | `@dataclass` | 到达、开始、完成时间与是否被丢弃 | 请求生命周期 |
| `make_workload` | 函数 | 生成 1 小时的突发到达序列（静默—高峰—尾部） | 突发流量 |
| `simulate` | 函数 | 主循环：入队 → 新副本就绪 → 派发 → 策略决策 → 扩缩容 → 超时丢弃 | 三层中的"应用层"+ 节点冷启动 |
| `report` | 函数 | 打印一行结果 | 指标 |
| `main` | 函数 | 生成一次流量，三种策略各跑一遍（每次复制新的 `Request`） | 公平对比 |

数据流：`make_workload(seed=7)` → 为每种策略复制请求列表 → `simulate(strategy, reqs)` 每 15 秒推进一次 → 汇总 `dropped / completed / mean_wait / idle_gpu_min / peak_replicas` → `report`。

---

## 3. 逐段精讲

### 3.1 常量：模型的全部假设都在这里

```python
NODE_PROVISION_SEC = 50       # Karpenter ~45-60s
CLUSTER_AUTOSCALER_SEC = 110  # slower comparison
MODEL_LOAD_SEC = 45           # load 70B weights + engine init
REQUEST_PREFILL_SEC = 0.6
REQUEST_DECODE_SEC = 1.8
MIN_WARM_REPLICAS = 1
MAX_REPLICAS = 16
GPU_PER_REPLICA = 1
HPA_TICK_SEC = 15
TARGET_GPU_UTIL = 70          # duty-cycle target
```

- 每个新副本都要 `50 + 45 = 95` 秒才能接请求，即"每加一个副本都开一台新节点"。讲义的 2–5 分钟从零冷启动包含更大的模型加载，这里取了较乐观的值。
- 单个请求服务时间 2.4 秒（prefill 0.6 + decode 1.8），串行处理，没有 batching。
- ⚠️ `CLUSTER_AUTOSCALER_SEC` 和 `GPU_PER_REPLICA` **定义了但从未使用**：代码并没有比较 Karpenter 与 Cluster Autoscaler，也没有"一个副本需要多张 GPU"的概念，因此无法模拟讲义里的 7-of-8 部分分配陷阱。

### 3.2 `make_workload`：三段式突发流量

```python
def make_workload(duration_sec: int = 3600, seed: int = 7) -> list[Request]:
    rng = random.Random(seed)
    reqs = []
    for _ in range(int(duration_sec)):
        t = _
        if t < 600:
            rate = 0.5
        elif t < 1800:
            rate = 4.0
        else:
            rate = 1.2
        if rng.random() < rate / 10:
            reqs.append(Request(arrived_at=float(t)))
    return reqs
```

- 每一秒做一次伯努利试验，概率 `rate / 10`：静默期 0.05/s、高峰 0.4/s、尾部 0.12/s。每秒最多 1 个请求，到达时间都是整数秒。
- `seed=7` 时共 743 个请求：静默 34、高峰 496、尾部 213（插桩统计）。
- 用独立的 `random.Random(seed)` 实例而不是全局 `random.seed`，不会影响其他代码的随机状态。
- 小瑕疵：循环变量写成 `_`（约定表示"不用的变量"）却紧接着 `t = _` 使用它，直接写 `for t in range(...)` 更清晰。

### 3.3 `simulate` 的状态

```python
    replicas_ready = MIN_WARM_REPLICAS
    replicas_target = MIN_WARM_REPLICAS
    replica_available_at = {i: 0.0 for i in range(MIN_WARM_REPLICAS)}
    queue: list[Request] = []
    ...
    pending_replicas: list[tuple[float, int]] = []  # (ready_at, replica_id)
```

- `replica_available_at`：副本 id → "下一次空闲的时间"。它同时记录了就绪副本和**正在供给中的副本**（后者的值是 `ready_at`）。
- `replicas_target`：策略想要的副本数；`replicas_ready + len(pending_replicas)` 是已有 + 在路上的副本数。
- `queue` 是普通列表，`pop(0)` 是 O(n)，规模小无所谓；生产代码用 `collections.deque`。

### 3.4 主循环：每个 tick 的六个步骤

```python
    while now < sim_end:
        # ① 新到达的请求入队
        while cursor < len(reqs) and reqs[cursor].arrived_at <= now:
            queue.append(reqs[cursor]); cursor += 1
        # ② 到时间的 pending 副本变为就绪
        for ready_at, rid in list(pending_replicas):
            if ready_at <= now:
                replica_available_at[rid] = now
                replicas_ready += 1
                pending_replicas.remove((ready_at, rid))
        # ③ 每个空闲副本取一个请求；没请求就记 15 秒空闲
        free_replicas = [rid for rid, t in replica_available_at.items() if t <= now]
        for rid in free_replicas:
            if queue:
                r = queue.pop(0)
                r.started_at = now
                service_time = REQUEST_PREFILL_SEC + REQUEST_DECODE_SEC
                r.completed_at = now + service_time
                replica_available_at[rid] = r.completed_at
            else:
                idle_gpu_sec += HPA_TICK_SEC
```

（为讲解方便，上面把两行合成了一行，并加了编号注释。）

- ① 用游标 `cursor` 顺序扫描已排序的请求，避免每个 tick 全表扫描。
- ② `for ... in list(pending_replicas)`：遍历**副本**的同时从原列表 `remove`，必须先 `list(...)` 拷贝，否则会跳元素。
- ③ **关键简化**：一个副本每个 tick 只取 **1 个**请求。请求 2.4 秒就完成，但要等到下一个 tick 才能接下一个，所以单副本能力是 `1/15 ≈ 0.067` 请求/秒，而不是 `1/2.4 ≈ 0.417`。高峰期 0.4 请求/秒于是需要约 6 个副本。
- 空闲计时也是"整 tick"粒度：接了一个 2.4 秒请求的副本这个 tick 记为 0 空闲；完全没请求的记 15 秒。正在供给中的副本（同样要付钱）不计入空闲。
- 请求最早在到达后的下一个 tick 才被处理，纯量化等待平均约 7.0 秒（插桩计算），这就是 DUTY_CYCLE 的 `mean_wait = 7.5s` 几乎全是 tick 造成的原因。

### 3.5 三种策略：决定结论的不是"信号"，而是阈值与滞回

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
```

- `busy` 是"本 tick 刚接到请求的就绪副本数"（它们的空闲时间是 `now + 2.4 > now`），所以 `util` = 本 tick 接单副本的比例。只要队列 ≥ 副本数，`util = 100%`。**这不是 duty cycle**——真正的 duty cycle 应是忙碌时间占比，每个副本最多 `2.4 / 15 = 16%`。
- 扩容：`util > 70%` 时 +1。只有 1 个副本时，来 1 个请求就是 100%，所以**静默期就在不断扩容**。
- 缩容：只有 `util < 20%` 才 −1。5 个副本中 1 个接单 = 20%，不满足，副本"只升不降"。这个 20%–70% 的滞回区间等于一个很宽的稳定窗口。

```python
        elif strategy == "QUEUE_DEPTH":
            qd = len(queue)
            if qd > 5 and replicas_target < MAX_REPLICAS:
                replicas_target = min(MAX_REPLICAS, replicas_target + max(1, qd // 5))
            elif qd == 0 and replicas_target > MIN_WARM_REPLICAS:
                replicas_target = max(MIN_WARM_REPLICAS, replicas_target - 1)
        elif strategy == "KAI_GANG":
            qd = len(queue)
            if qd > 3 and replicas_target < MAX_REPLICAS:
                replicas_target = min(MAX_REPLICAS, replicas_target + max(2, qd // 3))
            elif qd == 0 and replicas_target > MIN_WARM_REPLICAS:
                replicas_target = max(MIN_WARM_REPLICAS, replicas_target - 1)
```

- `qd` 是派发**之后**剩下的队列长度。只要本 tick 副本够用，队列就是 0，立刻缩容——**没有任何稳定窗口**，流量稍有起伏就来回抖动。
- 扩容要 `qd > 5` 才触发，而新副本 95 秒后才就绪、请求 30 秒就超时，扩容永远"慢半拍"。
- 扩容步长与积压成比例（`qd // 5`），这一点比 DUTY_CYCLE 的 +1 合理，也是讲义"队列深度能反映积压规模"的体现。
- `KAI_GANG` 与 `QUEUE_DEPTH` 只差阈值（3 vs 5）和最小步长（2 vs 1），**没有任何成组调度或拓扑逻辑**。名字与内容不符。

### 3.6 执行扩缩容与超时丢弃

```python
        while replicas_ready + len(pending_replicas) < replicas_target:
            ready_at = now + NODE_PROVISION_SEC + MODEL_LOAD_SEC
            pending_replicas.append((ready_at, next_replica_id))
            replica_available_at[next_replica_id] = ready_at
            next_replica_id += 1
        peak_replicas = max(peak_replicas, replicas_ready + len(pending_replicas))
        if replicas_ready > replicas_target:
            idle = [rid for rid, t in replica_available_at.items() if t <= now]
            if idle:
                replica_available_at.pop(idle[0])
                replicas_ready -= 1

        for r in queue[:]:
            if now - r.arrived_at > 30:  # SLA timeout
                r.dropped = True
                queue.remove(r)
```

- 扩容：缺多少补多少，每个新副本 95 秒后就绪。`peak_replicas` 统计的是"就绪 + 在路上"的最大值，三种策略都到了上限 16。
- 缩容：每个 tick 最多移除 **1 个空闲**副本；正在服务的副本不会被移除（对应讲义"不要驱逐正在运行的任务"）。已经在供给中的副本即使目标下降也**不会被取消**，就绪后再慢慢缩掉。
- 超时：在队列里等待超过 30 秒就丢弃。`for r in queue[:]` 遍历切片拷贝，才能在循环里安全 `remove`。因为检查发生在 tick 末尾，实际容忍时间是 30–45 秒。

### 3.7 汇总指标

```python
    started = [r for r in reqs if r.started_at is not None]
    mean_wait = (
        sum(r.started_at - r.arrived_at for r in started) / len(started)
        if started else 0.0
    )
```

- `mean_wait` 只统计**被处理过**的请求，被丢弃的请求（等得最久的那些）不计入，存在幸存者偏差；更好的做法是报告包含丢弃请求的 P99 等待时间。
- `idle_gpu_min` 是空闲 GPU 秒数 / 60；`completed + dropped` 可能小于 `total`（模拟结束时仍在队列里的请求，seed=7 时三种策略都正好相加为 743）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 15 秒离散 tick | 与 HPA 同步周期类似、代码简单 | 量化等待约 7 秒；每副本每 tick 只服务 1 个请求，能力低估约 6 倍；生产评估用事件驱动模拟或真实压测 |
| 串行服务、无 batching | 易懂 | 真实引擎有 continuous batching，一个副本同时服务几十个序列（阶段 17 · 04） |
| 每个新副本 = 新节点 + 加载 | 突出冷启动 | 节点上可能已有空闲 GPU；权重缓存可缩短加载 |
| DUTY_CYCLE 用"接单副本比例" | 简化 | 实际不是 duty cycle；真正 duty cycle（忙碌时间占比）在本模型中封顶 16%，副本永远不扩，丢 511 个请求 |
| 队列策略无稳定窗口 | 代码短 | 抖动严重；生产 HPA 用 `behavior.scaleDown.stabilizationWindowSeconds` 做"快扩慢缩" |
| KAI_GANG 只是更激进的队列策略 | 演示"更积极扩容" | 无法体现 gang/拓扑；要模拟需要"副本需 N 张 GPU、节点有 8 张卡、部分分配时空等"的资源模型 |
| 单个种子、单次运行 | 输出确定 | 结论对种子和参数敏感，应多种子取均值与置信区间 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 默认值 | `started_at: float \| None = None` | 自动生成构造函数；可选字段给默认值 |
| `float \| None` | `Request.started_at` | 联合类型注解（配合 `from __future__ import annotations`） |
| 局部随机数生成器 | `rng = random.Random(seed)`、`rng.random()` | 独立随机流，结果可复现且不污染全局 |
| 字典推导式 | `{i: 0.0 for i in range(MIN_WARM_REPLICAS)}` | 一行构造字典 |
| 集合推导式 | `{rid for _, rid in pending_replicas}` | 元组解包 + 去重；`in` 查找 O(1) |
| 生成器表达式求和 | `sum(1 for rid, t in ... if t > now ...)` | 计数满足条件的元素，不建中间列表 |
| `sorted(..., key=lambda)` | `sorted(reqs, key=lambda r: r.arrived_at)` | 按属性排序，返回新列表 |
| 遍历时修改的安全写法 | `for ... in list(pending_replicas)`、`for r in queue[:]` | 先复制再遍历，才能在循环里 `remove` |
| `list.pop(0)` / `dict.pop(key)` | `queue.pop(0)`、`replica_available_at.pop(idle[0])` | 取出并删除；`list.pop(0)` 是 O(n) |
| `max(1, qd // 5)` | 扩容步长 | `//` 整除；`max` 保证至少 1 |
| 条件表达式 | `... / len(started) if started else 0.0` | 避免除零 |
| 类型注解的局部变量 | `queue: list[Request] = []` | 只是提示，不做运行时检查 |
| f-string 宽度与精度 | `{row['total']:4}`、`{row['mean_wait_s']:5.1f}`、`{row['strategy']:14}` | 固定宽度对齐；数字默认右对齐、字符串默认左对齐 |
| `if __name__ == "__main__":` | 文件末尾 | 允许被 import 复用（本讲解的插桩实验就是 import 后改写 `simulate`） |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，不到 1 秒）：

```text
Strategy        reqs       done  dropped  mean_wait  idle_gpu   peak
--------------------------------------------------------------------
DUTY_CYCLE      reqs= 743  done= 742  dropped=  1  mean_wait=  7.5s  idle_gpu= 266.2min  peak=16
QUEUE_DEPTH     reqs= 743  done= 679  dropped= 64  mean_wait= 18.2s  idle_gpu=  49.5min  peak=16
KAI_GANG        reqs= 743  done= 682  dropped= 61  mean_wait= 15.4s  idle_gpu= 120.0min  peak=16

Read: DUTY_CYCLE drops requests because DCGM_FI_DEV_GPU_UTIL
is a duty-cycle metric. QUEUE_DEPTH reacts to the actual backlog.
KAI_GANG scales more aggressively and avoids partial-alloc stalls.
```

**结论文字与数据矛盾**：DUTY_CYCLE 只丢 1 个，QUEUE_DEPTH 丢 64 个。为解释原因，我们在 `simulate` 里每个 tick 记录了（就绪副本、供给中副本、目标、队列长度）：

| 时刻 | DUTY_CYCLE | QUEUE_DEPTH | KAI_GANG |
|------|-----------|-------------|----------|
| t=585（高峰前） | 就绪 5、在途 4、目标 9 | 就绪 1、在途 0 | 就绪 1、在途 0 |
| t=630 | 就绪 8、队列 0 | 就绪 1、在途 5、队列 16 | 就绪 1、在途 9、队列 16 |
| 高峰期平均就绪副本 | 13.8 | 7.19 | 7.31 |
| 丢弃分布（静默/高峰/尾部） | 1 / 0 / 0 | 1 / 38 / 25 | 1 / 39 / 21 |

逐项解读：

- **DUTY_CYCLE 靠"误打误撞的预热"取胜**：静默期 1 个副本接 1 个请求就是 100% 利用率，触发扩容；缩容门槛 `< 20%` 又很难满足。高峰来临前它已有 9 个副本在位或在路上，所以几乎不丢请求。代价是空闲 GPU 266.2 分钟，是 QUEUE_DEPTH 的 5.4 倍。
- **QUEUE_DEPTH 输在"缩得太快、扩得太晚"**：队列一清空就缩容，积压超过 5 才扩容，扩容后 95 秒才就绪，而请求 30 秒就超时。尾部阶段（0.12 请求/秒，约需 2 个副本）队列常驻 3–4 个、不到扩容阈值，于是持续有请求超时，丢了 25 个。
- **KAI_GANG 比 QUEUE_DEPTH 稍好**只因更激进（阈值 3、至少 +2），空闲时间也因此翻倍多（120 分钟）。
- **mean_wait 7.5 秒**中约 7.0 秒是 15 秒 tick 的量化等待，不是排队。
- **换种子结论不变**：种子 1/2/3/11 下 DUTY_CYCLE 丢 30/10/15/2，QUEUE_DEPTH 丢 105/83/75/85。

两个对照实验（都已实际运行）进一步说明问题出在建模而不是信号：

- 把 `util` 改成真正的 duty cycle（忙碌时间占比，最大 16%）：DUTY_CYCLE 永不扩容，`dropped=511`、`peak=1`——这才是讲义所说"信号在撒谎"的样子。
- 给 QUEUE_DEPTH 加缩容稳定窗口（连续 4 个空 tick 才缩 1 个）：丢弃 64 → 42，空闲 49.5 → 121.5 分钟；窗口为 8 时丢弃 35、空闲 154.5 分钟。

---

## 7. 动手改一改

1. **修正结论文字**：根据实际输出改写 `main` 末尾的 "Read" 说明，写清"本模拟中 DUTY_CYCLE 以 5 倍空闲 GPU 为代价换取低丢弃"。
2. **真正的 duty cycle**：按忙碌秒数 / tick 秒数计算 `util`（见测验 Q10），观察它为何永不扩容；再把 `TARGET_GPU_UTIL` 调到 10，看看是否"修好"了——并思考为什么这种调参在生产中不可靠。
3. **快扩慢缩**：给两种队列策略加缩容稳定窗口（连续 N 个 tick 队列为空才缩容），扫描 N=1…10，画出"丢弃数 vs 空闲 GPU 分钟"的折线，找出你愿意接受的折中点。
4. **去掉服务能力的 tick 限制**：让副本在一个 tick 内连续处理队列直到 tick 结束（参考实现下 DUTY_CYCLE/QUEUE_DEPTH/KAI_GANG 分别丢 0/32/23），比较结论变化。
5. **真的模拟 gang scheduling**：引入"节点 8 张 GPU、每个副本需要 `GPU_PER_REPLICA=8` 张且必须同节点"的资源模型，对比"部分分配后空等"与"全有或全无"两种调度在空闲 GPU 分钟上的差异，实现讲义的 7-of-8 场景。
6. **用上 `CLUSTER_AUTOSCALER_SEC`**：增加一个参数选择节点供给器，比较 50 秒与 110 秒供给时间下 QUEUE_DEPTH 的丢弃数。

---

## 8. 常见坑

- **相信代码打印的"Read"结论而不看数据**：本文件就是反例，结论文字与输出矛盾。
- **把"接单副本比例"当成 duty cycle**：二者含义不同；真实 DCGM 指标是采样窗口内 GPU 是否在执行 kernel。
- **没有缩容稳定窗口**：队列一空就缩，下一波流量来时冷启动 95 秒远长于 30 秒超时，必然丢请求。
- **只看丢弃数不看成本**：DUTY_CYCLE 丢得少是因为一直多开副本；评估 autoscaler 必须同时看空闲 GPU 时间（或成本）。
- **名字与实现不符**：`KAI_GANG` 并没有成组调度；不要据此得出"gang scheduling 能减少丢弃"的结论——gang 解决的是多 GPU 任务部分分配的浪费，不是单卡副本的扩容速度。
- **单个种子下结论**：流量是随机的，至少换几个种子，或用固定的真实流量回放。
- **遍历列表时直接删除元素**：代码用 `list(...)`、`[:]` 复制后再遍历，自己改代码时别漏掉。
