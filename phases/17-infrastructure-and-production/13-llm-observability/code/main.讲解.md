# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 13 节 LLM Observability 技术栈选型 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数，约 1 秒） ｜ **依赖**：仅标准库（`dataclasses`、`random`），无需网络或 API key

---

## 1. 这份代码在考察什么

讲义的主体是"选工具"，代码则聚焦其中一个可以量化的问题：**trace 太多存不起，怎么采样、采样后省多少钱、丢掉了什么**。

1. **采样策略**：全量、均匀随机 10%、"5% 成功 + 100% 错误"、再加"100% 高成本"、1% 加错误加高成本。
2. **保留量与存储量**：1M trace/天 × 每条 4,500 字节 → 每天多少 GB。
3. **三种计费口径**：整体式平台（Datadog 类，按 GB 摄入）、Arize AX 零拷贝（声称便宜 100 倍）、自己放 S3。

它对应讲义的 "Sampling — you can't keep everything" 与 "Arize AX — the scale play" 两节。工具选型本身（Langfuse / LangSmith / Helicone…）在代码里没有体现，由配套 skill 文件承担。

> 一句话：**用一个可复现的蒙特卡洛模拟说明"按规则采样"能在保住错误与高成本信号的同时砍掉九成以上的账单**——同时也暴露出成本常量与结论之间的口径矛盾。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `BYTES_PER_TRACE` 等 4 个常量 | 模块级常量 | trace 大小与三种单价 | 成本模型 |
| `Strategy` | `@dataclass` | 采样率 + 是否强制保留错误 / 高成本 | 采样规则 |
| `STRATEGIES` | 列表常量 | 5 种策略 | 讲义的采样建议 |
| `simulate_day()` | 函数 | 逐条模拟 1M 条 trace，决定保留与否，汇总 GB 与月成本 | tail sampling |
| `report()` | 函数 | 把一行结果格式化打印 | — |
| `main()` | 函数 | 遍历策略、打印表格与结论 | — |

数据流：`STRATEGIES` → `simulate_day(s)`（固定种子生成错误 / 高成本 / 采样随机数 → 计数 → 换算 GB → 三种月成本）→ `report(row)` → 结尾三行结论。

同目录还有一个 `main.ts`（TypeScript 版，不在本批讲解范围），除了同样的模拟器外，还实现了一个最小的 OpenTelemetry 形状的 GenAI tracer（使用 `gen_ai.system`、`gen_ai.usage.input_tokens` 等属性名）和一个"错误 + 高成本（总 token > 8000）+ 5% 成功"的采样 exporter，可作为本文件的补充阅读。

---

## 3. 逐段精讲

### 3.1 成本常量

```python
BYTES_PER_TRACE = 4_500            # prompt + response + metadata
COST_PER_GB_MONTH = 0.023          # S3 standard
OBSERVABILITY_INGEST_PER_GB = 0.50 # e.g. Datadog-class
ARIZE_AX_PER_GB = 0.005            # zero-copy claim
```

- 数字中的下划线 `4_500` 只是为了易读，等于 4500。
- 4,500 字节约等于一次单轮问答的 prompt + 回复 + 元数据。多步 Agent trace（工具调用、检索片段、长上下文）通常大得多，这个假设会让成本被严重低估（见 3.5）。
- `OBSERVABILITY_INGEST_PER_GB / ARIZE_AX_PER_GB = 100`，就是把讲义里 Arize "claims ~100x cheaper" 直接写成了常量。它是厂商声称，不是推导出来的。
- 注意 `ARIZE_AX_PER_GB`（0.005）比 S3 存储单价（0.023）还低。零拷贝的含义是"数据放在你自己的 S3，Arize 直接读"，所以 S3 费用并没有消失，完整成本应是两者之和。代码把它们并列为三选一，容易误导。

### 3.2 `Strategy` 与五种策略

```python
@dataclass
class Strategy:
    name: str
    sample_rate: float
    keep_errors: bool
    keep_highcost: bool


STRATEGIES = [
    Strategy("100% retain",                1.00, True, True),
    Strategy("10% random sample",          0.10, False, False),
    Strategy("5% success + 100% errors",   0.05, True, False),
    Strategy("5% success + errors + $$$",  0.05, True, True),
    Strategy("1% aggregates only",         0.01, True, True),
]
```

- 一个策略 = 基础采样率 + 两个"强制保留"开关。第 4 个就是讲义推荐的规则："100% errors, 100% high-cost, 5% success"。
- 名字里的 "5% success" 其实是对**所有** trace 先做 5% 的随机保留，再把错误 / 高成本强制保留；效果上等价于"成功请求保留 5%"。
- 第 5 个叫 "1% aggregates only"，但它保留的是 1% 原始 trace + 全部错误 + 全部高成本，代码里也没有任何聚合计算。名字与行为不符。

### 3.3 `simulate_day()`：逐条决定保留

```python
def simulate_day(strategy: Strategy, traces_per_day: int = 1_000_000) -> dict:
    rng = random.Random(7)
    retained = 0
    lost = 0
    for i in range(traces_per_day):
        is_error = rng.random() < 0.02
        is_highcost = rng.random() < 0.01
        keep = rng.random() < strategy.sample_rate
        if strategy.keep_errors and is_error:
            keep = True
        if strategy.keep_highcost and is_highcost:
            keep = True
        if keep:
            retained += 1
        else:
            lost += 1
```

- `random.Random(7)` 创建一个**独立的**随机数生成器并固定种子。每个策略调用时都重新以 7 播种，而且每条 trace 都按相同顺序抽 3 个随机数，所以**所有策略面对的是完全相同的一批错误 / 高成本 trace**。这叫"公共随机数"（common random numbers），让策略之间的差异只来自规则本身。
- 错误率 2%、高成本 1%，彼此独立。
- 保留判断在"已知这条 trace 是否出错、是否高成本"之后才做——这在真实系统里对应 **tail sampling**（trace 结束后再决定）；head sampling（请求开始就决定）做不到"100% 保留错误"。
- 期望保留比例可以手算验证：
  - 10% 随机：0.10 → 100,078（实测）
  - 5% + 错误：`1 − 0.95 × 0.98 = 0.069` → 68,808
  - 5% + 错误 + 高成本：`1 − 0.95 × 0.98 × 0.99 ≈ 0.0783` → 78,255
  - 1% + 错误 + 高成本：`1 − 0.99 × 0.98 × 0.99 ≈ 0.0395` → 39,710
- 循环变量 `i` 没有被使用，惯例写法是 `for _ in range(...)`。
- docstring 说要报告 "what's lost under each"，但函数只统计了丢失**条数**，没有统计丢掉了多少错误 / 高成本 trace——而那才是评价采样策略的关键（测验 Q9 给出了改造方法和结果）。

### 3.4 换算 GB 与三种月成本

```python
    bytes_retained = retained * BYTES_PER_TRACE
    gb = bytes_retained / 1e9
    return {
        "name": strategy.name,
        "retained": retained,
        "lost": lost,
        "gb_per_day": gb,
        "s3_month": gb * 30 * COST_PER_GB_MONTH,
        "monolithic_month": gb * 30 * OBSERVABILITY_INGEST_PER_GB,
        "arize_month": gb * 30 * ARIZE_AX_PER_GB,
    }
```

- `/ 1e9` 用十进制 GB（10⁹ 字节），与云厂商计价口径一致。
- `gb * 30`：一个月的数据量。对 S3 而言，它等于"保留期 30 天时的稳态存储量"，乘以每 GB·月单价就是月存储费，在 30 天保留期下是合理的；保留期变成 90 天时应乘 90，代码没有把保留期作为参数。
- 对整体式平台，`gb * 30 * 0.50` 是按摄入量计的月费。
- 返回普通 `dict` 而不是 dataclass，`report()` 用键名取值。

### 3.5 `report()` 与 `main()`：打印与结论

```python
def report(row: dict) -> None:
    print(f"{row['name']:30}  retained={row['retained']:7}  "
          f"lost={row['lost']:7}  {row['gb_per_day']:6.2f} GB/day  "
          f"mono=${row['monolithic_month']:8.2f}  "
          f"arize=${row['arize_month']:6.2f}  "
          f"s3=${row['s3_month']:5.2f}")
```

- 相邻的 f-string 字面量会被 Python 自动拼接成一个字符串，所以可以分多行书写。
- 在 f-string 里取字典值要用另一种引号：外层双引号、内层 `row['name']` 单引号（Python 3.12 之前不能在 f-string 内重复使用同种引号）。
- `$` 在 f-string 里只是普通字符，后面紧跟格式化的金额。

`main()` 最后打印三句结论。**第一句与表格数字矛盾**："100% retention on Datadog-class costs hundreds of $/day"，而表格里全量保留的 mono 成本是 $67.50/月，约 $2.25/天。要达到 $300/天，按 $0.50/GB 需要每天 600 GB，即每条 trace 约 600 KB。讲义"超过 1M 请求/天时全量保留比 LLM 调用还贵"的论断，用代码自己的参数也推不出来。第二句"cuts 90% of bill"成立（`5.28 / 67.50 ≈ 7.8%`，减少约 92%）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 逐条蒙特卡洛模拟 | 直观，和"每条 trace 决定去留"的真实流程同构 | 期望值其实可以直接用公式算；1M 次循环约 1 秒，规模再大要换成解析式或向量化 |
| 每个策略重设同一种子 | 公共随机数，策略间可公平对比 | 只代表一次抽样；严肃评估应跑多个种子看方差 |
| 在已知结果后决定保留 | 对应讲义的规则（100% 错误） | 生产中需要 tail sampling（如 OTel Collector 的 tail sampling 处理器），要缓冲整条 trace |
| 固定每条 4.5 KB | 简单 | Agent trace 大小差异巨大；应按实际分布或分位数建模 |
| 单一 GB 单价 | 便于比较 | 真实平台常按 span、索引、保留期计费；应把报价拆成单位成本 |
| Arize 与 S3 并列三选一 | 展示"100 倍"声称 | 零拷贝仍需自付存储与查询；应比较 `S3 + Arize` 与整体式平台 |
| 只报告条数 | 代码短 | 看不出丢了多少错误 / 高成本；应增加 `lost_errors`、`lost_highcost` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 数字分隔符 | `4_500`、`1_000_000` | 下划线只为易读，不影响数值 |
| 行尾注释 | `# S3 standard` | `#` 之后到行尾都是注释 |
| `@dataclass` | `class Strategy` | 自动生成 `__init__` 等方法 |
| 默认参数 | `traces_per_day: int = 1_000_000` | 调用时可省略 |
| 独立随机数生成器 | `rng = random.Random(7)`、`rng.random()` | 不影响全局 `random` 状态；`random()` 返回 [0, 1) 均匀分布 |
| 比较得布尔值 | `is_error = rng.random() < 0.02` | 以 2% 概率为 `True`，即伯努利抽样 |
| 增强赋值 | `retained += 1` | 等价于 `retained = retained + 1` |
| 科学计数法 | `/ 1e9` | `1e9` 是浮点数 10⁹ |
| 字典字面量 | `return {"name": ..., "gb_per_day": gb}` | 返回多个具名结果 |
| f-string 宽度与精度 | `{row['retained']:7}`、`{row['gb_per_day']:6.2f}` | 宽度 7；宽度 6、两位小数 |
| 相邻字符串自动拼接 | `print(f"..." f"..." f"...")` | 跨行书写长字符串 |
| 入口保护 | `if __name__ == "__main__":` | 直接运行才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，约 0.9 秒）：

```text
OBSERVABILITY SAMPLING — 1M traces/day, 2026 price approximations
100% retain                     retained=1000000  lost=      0    4.50 GB/day  mono=$   67.50  arize=$  0.68  s3=$ 3.10
10% random sample               retained= 100078  lost= 899922    0.45 GB/day  mono=$    6.76  arize=$  0.07  s3=$ 0.31
5% success + 100% errors        retained=  68808  lost= 931192    0.31 GB/day  mono=$    4.64  arize=$  0.05  s3=$ 0.21
5% success + errors + $$$       retained=  78255  lost= 921745    0.35 GB/day  mono=$    5.28  arize=$  0.05  s3=$ 0.24
1% aggregates only              retained=  39710  lost= 960290    0.18 GB/day  mono=$    2.68  arize=$  0.03  s3=$ 0.12

Read: 100% retention on Datadog-class costs hundreds of $/day.
5% success + 100% errors + high-cost keeps signal, cuts 90% of bill.
Arize AX zero-copy pattern wins at scale when you already have a data lake.
```

逐项解读：

- **保留条数**与 3.3 节的期望公式吻合，说明模拟正确。
- **GB/天**：全量 4.5 GB，讲义推荐策略 0.35 GB。
- **mono 一列**：全量也只有 $67.50/月。结论第一句的"hundreds of $/day"与此相差两个数量级，属于代码常量与结论不一致（见 3.5）。
- **arize 一列**：恰好是 mono 的 1/100，因为单价就是这样设定的。
- **丢了什么**（表中看不到，用同一种子补算得到）：这一天共有 19,956 条错误、10,159 条高成本。10% 随机采样丢了 18,005 条错误（约 90%）和 9,166 条高成本；"5% + 错误"不丢错误，但丢了 9,447 条高成本；后两种策略两类都不丢。所以真正"保住信号"的是第 4、5 种，而第 5 种更便宜一半。

---

## 7. 动手改一改

1. **统计丢失的信号**：给 `simulate_day` 增加 `lost_errors`、`lost_highcost` 两个计数并打印（参考测验 Q9），验证 10% 随机采样丢掉约 90% 的错误。
2. **参数化保留期**：给 `simulate_day` 增加 `retention_days` 参数，S3 成本改为 `gb * retention_days * COST_PER_GB_MONTH`，比较 14 / 30 / 90 天。
3. **修正 Arize 成本**：新增一列 `arize_total = arize_month + s3_month`，重新比较三种方案。
4. **trace 大小分布**：把固定的 4,500 字节换成对数正态分布（如中位数 5 KB、长尾到 500 KB），看全量保留成本如何变化，以及每条多大时才会到"hundreds of $/day"。
5. **完成讲义练习 2**：把 `traces_per_day` 改为 5M，计算代码口径下的月成本，再与 $150K 的报价对比，反推出隐含的每 GB 单价。
6. **进阶**：参考同目录 `main.ts`，用 Python 写一个最小 tracer：每次调用生成带 GenAI 约定属性的 span 字典，并实现"错误 + 总 token > 8000 + 5% 成功"的采样 exporter。

---

## 8. 常见坑

- **用均匀随机采样代替规则采样**：会按比例丢掉错误 trace，排查问题时恰好没有数据。
- **在采样后的数据上算错误率**：保留规则偏向错误，采样后数据里的错误占比会被严重高估（"5% + 错误"策略下约 29% vs 真实 2%）；聚合指标要在采样前计算，或按采样率加权。
- **head sampling 实现"100% 保留错误"**：请求开始时还不知道会不会出错，做不到；需要 tail sampling。
- **把厂商声称写成常量后当作结论**：`0.50 / 0.005 = 100` 只是重复了"100 倍"的说法，不是验证。
- **以为零拷贝不需要存储费**：数据在你自己的 S3 上，存储与查询费用照付。
- **按单一 GB 单价估算整体式平台**：真实报价可能按 span、索引、主机计费，必须把报价拆成单位成本再比较。
- **策略名与行为不符**："1% aggregates only" 实际保留原始 trace 并且没有聚合，读代码时以逻辑为准，不以名字为准。
