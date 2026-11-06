# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 10 节 缓解无服务器 LLMs 的冷启动 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`）；无需 GPU、无需网络

---

## 1. 这份代码在考察什么

这是一个约 100 行的"冷启动路径模拟器"，用讲义"Measure before optimizing"表里的数字，回答两个问题：

1. **叠加不同缓解层后，70B 模型从冷到能服务需要多久？** 把冷启动拆成 5 个阶段（节点供给、拉镜像、权重进 HBM、引擎初始化、首次前向），每种缓解措施只改写它所攻击的阶段。
2. **什么时候值得付钱养一个 warm 副本？** 打印 warm pool 月成本，并按请求率给出"warm 是否更好"的判断。

它对应讲义的五层缓解（预置镜像、Model Streamer、GPU 快照、warm pool、分层加载）中的前四层，以及"warm-pool math"一节。

> 一句话：**冷启动是若干阶段之和，每层缓解只消掉其中一两项，所以必须分层叠加**——同时，本代码的 warm pool 盈亏计算并没有真正比较金钱，这是读代码时最值得注意的地方。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Phase` | `@dataclass` | 一个冷启动阶段在 4 种情形下的秒数：原始 / 预置镜像 / 开 streamer / 开 GPU 快照 | 冷启动解剖 |
| `PHASES_70B` | 列表常量 | 5 个阶段的数值（与讲义表一致，合计 328 s） | 讲义"Measure before optimizing"表 |
| `total_for_stack` | 函数 | 给定缓解层集合，按 `if/elif` 选择每阶段秒数并求和 | 分层叠加 |
| `report_stack` | 函数 | 打印一个组合的总秒数与分钟数 | — |
| `warm_pool_break_even` | 函数 | 打印 warm pool 月成本，以及按请求率的冷启动次数和"Warm better?" | warm-pool math |
| `main` | 函数 | 打印 5 种组合，再调用盈亏表（$4.50/h、328 s、每天容忍 5 次） | — |

数据流：`main` → `report_stack(label, stack)` → `total_for_stack(stack)` 遍历 `PHASES_70B` → 打印；最后 `warm_pool_break_even(...)` 独立打印一张表。

---

## 3. 逐段精讲

### 3.1 `Phase` 与 `PHASES_70B`：一张"阶段 × 缓解"的表

```python
@dataclass
class Phase:
    name: str
    raw_sec: float
    pre_seeded_sec: float    # 0 if eliminated
    streamer_sec: float      # replaces raw if streamer active
    snapshot_sec: float      # replaces all if snapshot active


PHASES_70B = [
    Phase("node provision",   50.0, 50.0,  50.0,  0.5),
    Phase("image pull",      180.0,  0.0, 180.0,  0.0),
    Phase("weights to HBM",   75.0, 75.0,  35.0,  0.0),
    Phase("engine init",      20.0, 20.0,  20.0,  2.0),
    Phase("first forward",     3.0,  3.0,   3.0,  0.5),
]
```

| 阶段 | 原始 | 预置镜像 | streamer | GPU 快照 | 讲义对应的缓解 |
|------|------|---------|----------|---------|---------------|
| node provision | 50 | 50 | 50 | 0.5 | Bottlerocket + warm pool |
| image pull | 180 | **0** | 180 | 0 | 预置数据卷（消除） |
| weights to HBM | 75 | 75 | **35** | 0 | streamer（减半）；快照（消除） |
| engine init | 20 | 20 | 20 | 2.0 | 持久化 CUDA graph 缓存 |
| first forward | 3 | 3 | 3 | 0.5 | 固有延迟 |
| **合计** | **328** | 148 | 288 | **3.0** | |

- 每列只在"它攻击的阶段"上与原始值不同：预置镜像只改 image pull，streamer 只改 weights to HBM。这正是讲义和 skill 文件强调的"每个缓解措施必须说出它攻击的是哪个阶段"。
- streamer 把 75 s 变成 35 s（讲义说"roughly in half"，严格减半应为 37.5 s）。
- ⚠️ **快照列把节点供给设为 0.5 s**：快照恢复的前提是已经有一台 GPU 机器。Modal 的 2–4 s 隐含"平台维护着共享的热 GPU 容量"；在自建 Kubernetes 上，新节点仍要 Karpenter 供给 45–60 s。所以 3.0 s 只在托管平台上成立。
- 合计 328 s 与讲义表一致；讲义称"叠加缓解后约 15 s"，但代码中没有任何组合算出 15 s（预置 + streamer 是 108 s，快照是 3 s）。

### 3.2 `total_for_stack`：用 `if/elif` 选择每阶段的秒数

```python
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

- `stack` 是 `set[str]`，用 `in` 判断某一层是否开启（集合的成员检查是 O(1)）。
- **分支优先级**：快照 > (预置 + streamer) > 预置 > streamer > 原始。快照被视为"替换所有阶段"，所以与其它层同时出现时只看快照。
- "预置 + streamer"分支：取预置列（image pull = 0），但把 weights to HBM 换成 streamer 值 → `50 + 0 + 35 + 20 + 3 = 108 s`。
- "只开 streamer"分支：注意 `phase.streamer_sec` 列里 image pull 仍是 180，所以 streamer 列本身其实已经编码了"只改权重加载"，这里再用 `if phase.name == ...` 判断是冗余的保护。
- ⚠️ **`"warm_pool"` 不被识别**：`total_for_stack({"warm_pool"})` 落到 `else`，返回 328 s。warm pool 的效果是"主路径不发生冷启动"，代码只在打印的说明里提到它。
- ⚠️ **可扩展性差**：n 种缓解就有 2ⁿ 种组合，每加一层（如讲义 L5 tiered loading）都要改分支。更好的写法是"每层声明它覆盖哪些阶段，逐阶段取最小值"，测验 Q9 给出了数据驱动版本，并验证与原函数在 5 种组合上结果一致。

### 3.3 `report_stack`：打印一行

```python
def report_stack(label: str, stack: set[str]) -> None:
    total = total_for_stack(stack)
    mins = total / 60
    print(f"{label:20}  {total:6.1f} s  ({mins:4.1f} min)  stack={sorted(stack) if stack else '{baseline}'}")
```

- `sorted(stack)` 把集合变成有序列表再打印，保证输出稳定（集合本身的迭代顺序不保证）。
- `... if stack else '{baseline}'`：空集合为假值，打印 `{baseline}`。注意 `'{baseline}'` 是放在 f-string 花括号**内部表达式**里的普通字符串，所以花括号会原样输出。
- `{label:20}` 把标签填充到 20 宽；"+ PRE_SEEDED + STREAMER" 有 23 个字符，超出宽度，所以输出中这一行没有对齐。

### 3.4 `warm_pool_break_even`：看起来是盈亏分析，实际只是计数

```python
def warm_pool_break_even(gpu_hourly: float, cold_seconds: float, sla_tolerated_drops_per_day: int) -> None:
    ...
    warm_monthly = gpu_hourly * 24 * 30
    print(f"Warm pool (min_workers=1) monthly cost: ${warm_monthly:.2f}")
    ...
    for rate in (1, 5, 10, 25, 50, 100, 250):
        cold_starts_per_day = 24 / max(rate, 1) if rate < 1 else 1
        cold_starts_per_day = min(20, max(1, int(24 * 3600 / (rate * 3600))))
        drops = cold_starts_per_day
        warm_better = "yes" if drops > sla_tolerated_drops_per_day else "no"
```

逐行看：

- `warm_monthly = 4.50 × 24 × 30 = $3,240`：正确，但**只被打印**，从未参与判断。
- 第一行 `cold_starts_per_day = ...` 是**死代码**：紧接着被第二行覆盖（而且 `rate` 最小为 1，`rate < 1` 永远为假）。
- 第二行化简后就是 `int(24 / rate)`，再截断到 [1, 20]：请求率 1 → 20、5 → 4、10 → 2、≥ 25 → 1。隐含的模型是"每小时 rate 个请求，平均间隔 1/rate 小时，每天约 24/rate 次冷启动"，这在物理上说不通（间隔越短越不容易缩容），只是一个粗糙的"低流量更容易冷启动"示意。
- `drops = cold_starts_per_day`：每次冷启动只算 1 次 drop。实际上冷启动持续 328 s，期间到达的所有请求都会受影响；`cold_seconds` 参数只在标题行打印，从未参与计算。
- 判断 `drops > 5`：只有请求率 1/h 时 "yes"。

所以这张表**没有计算讲义练习 1 要求的"盈亏平衡请求率"**。测验 Q10 给出一个更合理的模型：Poisson 到达 + 15 分钟空闲超时 → 每天冷启动 `24λ·e^{−λT}` 次，每次影响 `1 + λ·328/3600` 个请求；在每个受影响请求损失 $0.50 的假设下，任何流量都不值得养 warm 副本（最坏每天损失约 $25，而 warm 副本每天 $108）；损失要高于约 $2.15/请求才可能划算。更重要的是，讲义的结论本来就是"SLA 决定 warm pool"，而不是纯成本。

### 3.5 `main`

```python
    report_stack("RAW",                      set())
    report_stack("+ PRE_SEEDED",             {"pre_seeded"})
    report_stack("+ STREAMER",               {"streamer"})
    report_stack("+ PRE_SEEDED + STREAMER",  {"pre_seeded", "streamer"})
    report_stack("+ GPU_SNAPSHOT",           {"gpu_snapshot"})
    ...
    warm_pool_break_even(gpu_hourly=4.50, cold_seconds=328, sla_tolerated_drops_per_day=5)
```

- 空集合必须写 `set()`，`{}` 是空字典。
- `cold_seconds=328` 手写了 RAW 的结果，而不是调用 `total_for_stack(set())`——如果改了阶段数值，这里不会同步（虽然该参数本来也没被使用）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用讲义表的固定秒数 | 与讲义一一对应，易于核对 | 真实数值取决于存储带宽、镜像大小、模型大小；生产中逐阶段打点测量（skill："Use 2026 nominal seconds for the stated model size"） |
| 每列表示"开某一层后"的秒数 | 直观看到每层攻击哪个阶段 | 组合要靠 `if/elif` 硬编码；数据驱动的"覆盖表 + 取最小"更易扩展 |
| 快照替换所有阶段（含节点） | 体现托管平台的秒级恢复 | 在自建集群上不成立，节点供给仍要 ~50 s |
| warm pool 不进入 `total_for_stack` | warm pool 是"避免冷启动"而非"缩短冷启动" | 无法在同一张表里比较；应单独计算主路径的 0 s 和扩容副本的冷启动 |
| 盈亏表只比较冷启动次数 | 示意"低流量更容易冷启动" | 没用到成本和冷启动时长，不能回答盈亏平衡问题；应建模到达过程、空闲超时、受影响请求数和单请求价值 |
| 不建模 tiered loading 和 live migration | 控制代码规模 | 讲义的 L5、L6 只能在练习中补充 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 允许 `set[str]` 等注解写法 |
| `@dataclass` | `class Phase:` | 自动生成构造函数；`Phase("image pull", 180.0, 0.0, 180.0, 0.0)` 按字段顺序传参 |
| 行尾注释说明字段语义 | `pre_seeded_sec: float    # 0 if eliminated` | 让数据表自带文档 |
| 集合字面量 | `{"pre_seeded", "streamer"}` | 无序、不重复；空集合必须写 `set()` |
| 成员检查 `in` | `"gpu_snapshot" in stack` | 集合查找为平均 O(1) |
| `if / elif / else` 链 | `total_for_stack` | 按顺序匹配第一个成立的分支 |
| 条件表达式 | `phase.streamer_sec if phase.name == "weights to HBM" else phase.raw_sec` | 一行内二选一 |
| 真值判断 | `... if stack else '{baseline}'` | 空集合、空列表、0、`""` 都是假值 |
| `sorted()` | `sorted(stack)` | 返回排好序的新列表，常用于稳定输出 |
| 嵌套 `max/min` 截断 | `min(20, max(1, int(...)))` | 把值限制在 [1, 20] 区间 |
| `int()` 截断 | `int(24 * 3600 / (rate * 3600))` | 向零取整，丢掉小数 |
| 字符串拼接与重复 | `"\n" + "=" * 80` | 先换行再画线 |
| f-string 格式 | `{total:6.1f}`、`${gpu_hourly:.2f}`、`{rate:>8}`、`{'Req/hr':>8}` | 宽度、小数位、右对齐；`$` 在花括号外是普通字符 |
| 关键字参数 | `warm_pool_break_even(gpu_hourly=4.50, cold_seconds=328, ...)` | 调用处自带语义 |
| `-> None` | `def report_stack(...) -> None:` | 表示函数只产生副作用（打印），不返回值 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不运行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，输出确定）：

```text
Stack                    Total             Stack composition
--------------------------------------------------------------------------------
RAW                    328.0 s  ( 5.5 min)  stack={baseline}
+ PRE_SEEDED           148.0 s  ( 2.5 min)  stack=['pre_seeded']
+ STREAMER             288.0 s  ( 4.8 min)  stack=['streamer']
+ PRE_SEEDED + STREAMER   108.0 s  ( 1.8 min)  stack=['pre_seeded', 'streamer']
+ GPU_SNAPSHOT           3.0 s  ( 0.1 min)  stack=['gpu_snapshot']

Warm pool (min_workers=1) monthly cost: $3240.00

  Req/hr  Expected cold starts/day     Drops over budget     Warm better?
       1                        20                    15              yes
       5                         4                     0               no
      10                         2                     0               no
      25                         1                     0               no
     ...
```

逐项解读：

- **RAW 328 s（5.5 分钟）**：落在讲义"3–8 分钟"的区间内。
- **预置镜像 148 s**：省掉 180 s 的拉镜像，是单层收益最大的一项（与讲义"Typical savings: 2–4 minutes"一致）。
- **只开 streamer 288 s**：只省 40 s——在拉镜像还要 180 s 的情况下，优化权重加载意义不大。**先消除最大的阶段**。
- **预置 + streamer 108 s**：剩下节点供给 50 s 与权重 35 s 为大头；要继续往下压，需要 warm 节点池、快照或分层加载。
- **GPU 快照 3.0 s**：对应 Modal 的 2–4 s，但前提是平台托管的热容量（见 3.1）。`328 / 3 ≈ 109` 倍，远大于讲义说的"10x faster restart"——因为代码把节点供给、拉镜像也一起抹掉了。
- **"+ PRE_SEEDED + STREAMER" 行没对齐**：标签 23 个字符超过了 `{label:20}` 的宽度。
- **盈亏表**：$3,240/月是正确的；但"Warm better?"只是比较冷启动次数与 5 次/天的预算，没有使用月成本和 328 s。结果"只有 1 req/h 时 warm 更好"与直觉相反——高流量下一次早高峰冷启动会让 328 s 内到达的所有请求受影响（250 req/h 时约 23 个），表里却只算 1 次。

---

## 7. 动手改一改

1. **（入门）** 讲义练习 3：把 `PHASES_70B` 中 weights to HBM 的预置列改为按 7 GB/s 计算（BF16 140 GB → 20 s，FP8 70 GB → 10 s），重新运行，观察节点供给成为最大头。
2. **（入门）** 让 `total_for_stack` 识别 `"warm_pool"`：主路径返回 0 s，并在报告中注明"扩容副本仍按其它层计算"。
3. **（进阶）** 用"覆盖表 + 逐阶段取最小值"重写 `total_for_stack`，加入讲义 L5 tiered loading（DRAM → HBM 例如 5 s，标注为假设值），比较 `{"pre_seeded", "tiered"}` 的结果（参考测验 Q9，应为 78 s）。
4. **（进阶）** 给快照列加一个开关 `managed_capacity: bool`：自建集群时节点供给保持 50 s，托管平台时为 0.5 s，对比两种情况下快照栈的总时长。
5. **（进阶）** 按测验 Q10 重写 `warm_pool_break_even`：Poisson 到达 + 空闲超时 + 冷启动窗口内的受影响请求 + 单请求价值，输出真正的"盈亏平衡请求率"或"盈亏平衡单请求价值"。
6. **（挑战）** 实现 skill 文件的规划器：输入模型大小、TTFT P99 SLA、流量形态、预算，输出层选择、`min_workers`、月成本、尾部策略和故障模式，并在"70B + 无 warm pool + SLA < 5 s"时拒绝承诺。

---

## 8. 常见坑

- **把 warm pool 当成唯一答案**：它解决主路径，但每个副本 24×7 付费；5 个产品各 1 个就是 3,600 GPU 小时/月。
- **只优化权重加载**：拉镜像还要 180 s 时，streamer 只省 40 s；应先消除最大阶段。
- **忽视快照的前提**：快照不能凭空变出 GPU 节点，也与 GPU 拓扑绑定，换 SKU 要重做。
- **混淆"冷启动次数"与"受影响请求数"**：一次 5 分钟的冷启动在高峰期会影响几十个请求。
- **只看成本不看 SLA**：讲义的结论是 SLA 决定 warm pool，70B+ 模型 TTFT P99 < 60 s 时 warm pool 必选。
- **在 live migration 中搬 KV**：节点被驱逐时 KV 可能根本来不及导出；搬 KB 级的 token 并重算才是讲义推荐的方式。
- **快照时机不当**：在服务过真实请求后做快照，KV 区域可能残留用户数据（讲义练习 4）。
- **硬编码重复的数字**：`cold_seconds=328` 与阶段表分开维护，改一处忘另一处。
