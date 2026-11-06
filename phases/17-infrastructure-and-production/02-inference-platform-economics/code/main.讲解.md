# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 02 节 Inference 平台经济性：Fireworks、Together、Baseten、Modal、Replicate、Anyscale ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

讲义的核心论点是："Fireworks 显示 $/M tokens，Baseten 显示 $/minute，Modal 显示 $/second，Replicate 显示 $/prediction——不建模工作量就没法正面比较。"这份代码就是一个最小的**成本归一化器**：

1. **三种计价函数**：per-token、per-minute（带预留分钟下限）、per-prediction，在同一个 `cost_per_day` 里实现。
2. **归一化**：把三种成本都折算为 `$/day` 和"有效 $/M tokens"，放进同一张表。
3. **盈亏平衡**：扫描利用率 5%–100%，看 per-token（Fireworks）与 per-minute（Baseten）在哪里交叉，对应讲义练习 1。
4. **冷启动**：列出各家冷启动秒数（只打印，不计成本）。

> 一句话：**价格页上的单价不能直接比，必须先乘上你的工作量模型**；而且同一份代码也暴露出：结论高度依赖"预留下限"和"满载吞吐"这两个假设。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Vendor` | `@dataclass` | 一个厂商的计价参数：三种单价（只填一种）、满载吞吐、冷启动、预留分钟下限 | 计价模型 |
| `VENDORS` | 列表常量 | 6 家厂商的"2026 近似"参数 | 市场格局 |
| `cost_per_day` | 函数 | 按厂商的计价方式计算每日成本 | 三种计价函数 |
| `effective_rate` | 函数 | 每日成本 ÷ 每日百万 token → 有效 $/M | 归一化 |
| `run_scenario` | 函数 | 打印一个工作量下 6 家的成本表 | 横向比较 |
| `utilization_breakeven` | 函数 | 扫描利用率，比较 Fireworks 与 Baseten | per-token vs per-minute 盈亏平衡 |
| `cold_start_penalty` | 函数 | 打印冷启动秒数 × 100 | serverless 隐性成本 |
| `main` | 函数 | 两个场景 + 盈亏平衡 + 冷启动 + 经验法则 | 入口 |

数据流：`VENDORS`（参数） → `cost_per_day(v, tokens, predictions)` → `effective_rate` → `run_scenario` / `utilization_breakeven` 打印表格。

---

## 3. 逐段精讲

### 3.1 `Vendor`：用"哪个字段非 None"表示计价方式

```python
@dataclass
class Vendor:
    name: str
    model: str
    per_mtok_output: float | None   # $/M output tokens (None if not the model)
    per_minute: float | None        # $/minute for dedicated GPU (None if serverless)
    per_prediction: float | None    # $/prediction (None if per-token)
    tokens_per_minute: int          # effective tokens when GPU is saturated
    cold_start_sec: float
    notes: str
    min_reserved_minutes_per_day: int = 0
```

- 三个单价字段**只应有一个非 None**，`cost_per_day` 按 `per_mtok_output → per_minute → per_prediction` 的顺序检查，第一个非 None 的生效。这是一种"隐式的 tagged union（带标签的联合类型）"，没有任何校验：如果两个字段都填了，只有前一个生效，不会报错。
- `tokens_per_minute` 的含义是"GPU **饱和**时的有效吞吐"，只在 per-minute 分支使用；对 Fireworks、Together、Replicate 来说是装饰性字段。
- `min_reserved_minutes_per_day` 带默认值 0，必须放在所有无默认值字段之后（dataclass 的规则）。Baseten、Anyscale 填 1440（全天预留），Modal 填 60（60 分钟 warm-pool 下限）。
- 注释 `(None if not the model)` 应为"不是该计价模型时为 None"，原文措辞有歧义。

### 3.2 `VENDORS`：参数决定结论

```python
VENDORS = [
    Vendor("Fireworks", "Llama 70B",        0.90, None, None,  900_000, 1.5, "..."),
    Vendor("Together",  "Llama 70B",        0.88, None, None,  850_000, 2.0, "..."),
    Vendor("Baseten",   "Custom Llama 70B", None, 0.55, None,  900_000, 5.0, "...", 1440),
    Vendor("Modal",     "Custom Llama 70B", None, 0.48, None,  800_000, 2.5, "...", 60),
    Vendor("Replicate", "Llama 70B",        None, None, 0.006, 750_000, 4.0, "..."),
    Vendor("Anyscale",  "Llama 70B RayTurbo", None, 0.60, None, 850_000, 3.0, "...", 1440),
]
```

把参数换算一下更直观：

| 厂商 | 计价 | 换算 | 满载有效单价 |
|------|------|------|------------|
| Fireworks | $0.90/M | — | $0.90/M |
| Together | $0.88/M | — | $0.88/M |
| Baseten | $0.55/min | $33/小时，全天 $792 | `0.55/900k×1e6 ≈ $0.611/M` |
| Modal | $0.48/min | $28.8/小时，下限 $28.8/天 | `$0.600/M` |
| Anyscale | $0.60/min | $36/小时，全天 $864 | `≈ $0.706/M` |
| Replicate | $0.006/次 | 200 token/次时 | `$30/M` |

- 这些数字是文件头说明的"2026 approximations"，不是真实报价；讲义里唯一给出的真实价格类数字是 Groq 在 Llama-70B 上约 $0.99/M（2025 年末）。
- 900k tok/min ≈ 15,000 tok/s，对单卡跑 70B 来说是非常乐观的聚合吞吐；吞吐假设越高，per-minute 越占便宜。
- 三家 per-minute 的满载单价都比 per-token 低，所以"利用率足够高时 per-minute 更便宜"在参数层面已经注定，问题只是阈值在哪。

### 3.3 `cost_per_day`：三种计价函数

```python
def cost_per_day(v: Vendor, tokens_per_day: int, predictions_per_day: int) -> float:
    if v.per_mtok_output is not None:
        return (tokens_per_day / 1e6) * v.per_mtok_output
    if v.per_minute is not None:
        saturated_minutes = tokens_per_day / v.tokens_per_minute
        minutes = max(saturated_minutes, v.min_reserved_minutes_per_day)
        return minutes * v.per_minute
    if v.per_prediction is not None:
        return predictions_per_day * v.per_prediction
    return 0.0
```

- **per-token**：线性，`token 数 / 1e6 × 单价`。没有空闲成本，也没有规模折扣。
- **per-minute**：先算"如果 GPU 一直满载，需要多少分钟"——`saturated_minutes`，再和预留下限取 `max`。这一行是整份代码最关键的假设：
  - 低流量时 `minutes = 预留下限`，成本是常数（Baseten 恒为 $792/天）；
  - 高流量时 `minutes = 满载分钟数`，成本随 token 线性增长，单价等于 `per_minute / tokens_per_minute`。
  - 它默认"流量可以被完美打包成满载时段"，现实中请求分散在 24 小时里，GPU 很难一直饱和。
- **per-prediction**：只看调用次数，与输出长度无关。
- docstring 说明了设计动机：早期版本在 `run_scenario` 里假设"完美缩容到零"、在盈亏平衡里假设"24h 预留"，现在用同一个下限字段统一口径。但 Modal 是 60 分钟、另两家是 1440 分钟，**厂商之间的口径仍不对称**，这让 Modal 在 Scenario B 显得比 per-token 还便宜（见第 6 节）。

### 3.4 `effective_rate`：归一化到 $/M tokens

```python
def effective_rate(v: Vendor, tokens_per_day: int, predictions_per_day: int) -> float:
    c = cost_per_day(v, tokens_per_day, predictions_per_day)
    return (c / (tokens_per_day / 1e6)) if tokens_per_day else 0
```

- 条件表达式防止 `tokens_per_day = 0` 时除零；此时返回整数 `0` 而非 `0.0`，类型注解写的是 `float`，属于小瑕疵（Python 中 `int` 能当 `float` 用，不影响打印）。
- 对 per-minute 厂商，有效单价 = 预留成本被摊到实际 token 上，流量越低越贵——这就是 skill 中"低于 100k token/天拒绝推荐 per-minute"的数学依据。

### 3.5 `run_scenario`：横向比较表

```python
    header = f"{'Vendor':12}  {'Model':22}  {'$/day':>8}  {'$/M tok':>10}  Notes"
    print(header)
    print("-" * len(header))
    for v in VENDORS:
        cost = cost_per_day(v, tokens_per_day, predictions_per_day)
        rate = effective_rate(v, tokens_per_day, predictions_per_day)
        print(f"{v.name:12}  {v.model:22}  ${cost:7.2f}  ${rate:9.2f}  {v.notes}")
```

- 两个场景的 `tokens_per_day / predictions_per_day` 都是 200，即隐含"每次请求 200 个输出 token"。这个比例决定了 Replicate 的有效单价（$30/M）。
- `"-" * len(header)`：分隔线长度自动等于表头长度。

### 3.6 `utilization_breakeven`：利用率扫描

```python
    fw = VENDORS[0]
    bt = VENDORS[2]
    for util_pct in (5, 10, 15, 20, 25, 30, 35, 40, 50, 75, 100):
        tokens_per_day = int(bt.tokens_per_minute * 60 * 24 * util_pct / 100)
        fw_cost = cost_per_day(fw, tokens_per_day, 0)
        bt_cost = cost_per_day(bt, tokens_per_day, 0)
        winner = "Baseten" if bt_cost < fw_cost else "Fireworks"
```

- 利用率以 **Baseten 的满载吞吐**为基准：u% 意味着每天 `900k × 1440 × u%` 个 token。
- 用 `VENDORS[0]`、`VENDORS[2]` 按下标取厂商，列表顺序一改就会取错；更稳妥的是按名字查找（`next(v for v in VENDORS if v.name == "Baseten")`）。
- 扫描点在 50% 和 75% 之间跳了一大步，而真实交叉点（约 67.9%）恰在这段里，所以表格看不出精确阈值。解析解是 `u* = per_minute / (tokens_per_minute × per_mtok / 1e6) = 0.55 / 0.81 ≈ 0.679`。
- 平局时（`bt_cost == fw_cost`）判为 Fireworks。

### 3.7 `cold_start_penalty` 与 `main`

```python
    for v in VENDORS:
        impact_sec = v.cold_start_sec * 100
        print(f"{v.name:12}  {v.cold_start_sec:>8.1f} s   +{impact_sec:.0f} seconds/day of extra latency")
```

- 冷启动只被打印，不进入 `cost_per_day`。讲义把冷启动当作 serverless 的隐性成本，但这里没把它换算成钱或 SLA 违约。
- 有点反直觉：Baseten/Anyscale 被建模为 24h 预留，理论上根本不会冷启动，却列出了最大的冷启动秒数。

`main` 最后打印的经验法则是"~60-70%"，与讲义正文和 skill 文件中的"~30%"**不一致**。代码的数字与它自己的参数一致；讲义的 30% 是另一组价格/吞吐下的结论。详见测验 Q10。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 一个 dataclass 装三种计价 | 代码短、一张表能比完 | 没有校验"只能填一种"；生产会用不同的类或枚举 + 校验 |
| per-minute 用 `max(满载分钟, 预留下限)` | 同时覆盖"预留"与"按需"两种情形 | 假设流量能完美打包成满载时段；现实需按小时级流量曲线 + 实测 batch 吞吐模拟 |
| 只算输出 token | 简化 | 真实账单区分输入/输出 token，输入通常更便宜但量更大 |
| 固定 200 token/请求 | 让 per-prediction 可比 | 应使用真实请求长度分布 |
| 冷启动只打印 | 讲清"有这个成本"即可 | 生产会把冷启动转成 P99 TTFT 与 SLA 违约率，再决定预热策略 |
| 利用率扫描点离散 | 输出简洁 | 应二分或解析求精确交叉点 |
| 硬编码"2026 近似"价格 | 无需网络 | 价格频繁变化（讲义提到 Fireworks 2026-05-01 涨价），应从配置或价格 API 读取 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，使 `float \| None` 在旧版本 Python 中也能写在注解里 |
| `@dataclass` | `class Vendor:` | 自动生成 `__init__`、`__repr__`、`__eq__`；字段即构造参数 |
| 联合类型注解 | `per_minute: float \| None` | 值可以是 float 或 None（Python 3.10+ 语法） |
| 字段默认值顺序 | `min_reserved_minutes_per_day: int = 0` 放最后 | dataclass 中有默认值的字段必须在无默认值字段之后 |
| 位置参数构造 | `Vendor("Fireworks", "Llama 70B", 0.90, None, ...)` | 按字段顺序传参；可读性差，生产代码建议关键字参数 |
| 数字下划线 | `900_000`、`2_000_000` | 只为可读，等于 900000 |
| `is not None` 判断 | `if v.per_minute is not None:` | 区分"值为 0"与"没有值"，不能写成 `if v.per_minute:` |
| 条件表达式 | `(c / ...) if tokens_per_day else 0` | 一行 if/else，避免除零 |
| 内置 `max` | `max(saturated_minutes, v.min_reserved_minutes_per_day)` | 取下限 |
| f-string 宽度/对齐 | `{v.name:12}`、`{'$/day':>8}`、`{cost:7.2f}`、`{util_pct:>7}` | 左对齐（字符串默认）、右对齐、总宽 7 保留 2 位小数 |
| f-string 内表达式 | `{tokens_per_day/1e6:.1f}`、`{bt.tokens_per_minute/1e3:.0f}k` | 花括号内可以写任意表达式 |
| 字符串乘法 | `"=" * 80`、`"-" * len(header)` | 重复字符串生成分隔线 |
| 元组字面量循环 | `for util_pct in (5, 10, 15, ...)` | 直接迭代常量元组 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不执行 `main()`，便于在别的脚本里复用 `cost_per_day` |

---

## 6. 运行结果解读

实际运行（Python 3，耗时不到 1 秒）：

```text
Scenario A — startup-scale LLM product
Workload: 2.0M output tokens/day  |  10000 predictions/day
Fireworks     Llama 70B               $   1.80  $     0.90
Together      Llama 70B               $   1.76  $     0.88
Baseten       Custom Llama 70B        $ 792.00  $   396.00   ← 1440 分钟预留，实际只需 2.2 分钟
Modal         Custom Llama 70B        $  28.80  $    14.40   ← 60 分钟下限，实际只需 2.5 分钟
Replicate     Llama 70B               $  60.00  $    30.00   ← 10000 × $0.006
Anyscale      Llama 70B RayTurbo      $ 864.00  $   432.00

Scenario B — high-volume production
Workload: 100.0M output tokens/day  |  500000 predictions/day
Fireworks     Llama 70B               $  90.00  $     0.90
Together      Llama 70B               $  88.00  $     0.88
Baseten       Custom Llama 70B        $ 792.00  $     7.92   ← 仍在预留下限内（满载只需 111 分钟）
Modal         Custom Llama 70B        $  60.00  $     0.60   ← 125 分钟 > 60 下限，按满载单价计
Replicate     Llama 70B               $3000.00  $    30.00
Anyscale      Llama 70B RayTurbo      $ 864.00  $     8.64

PER-TOKEN vs PER-MINUTE BREAK-EVEN — Fireworks (per-token) vs Baseten (per-min)
  Util %   Fireworks $/day   Baseten $/day  Winner
      5%  $          58.32  $       792.00  Fireworks
     30%  $         349.92  $       792.00  Fireworks   ← 讲义说的 30% 这里仍是 Fireworks 胜
     50%  $         583.20  $       792.00  Fireworks
     75%  $         874.80  $       792.00  Baseten
    100%  $        1166.40  $       792.00  Baseten

COLD START PENALTY — bursty workload
Fireworks          1.5 s   +150 seconds/day of extra latency
Baseten            5.0 s   +500 seconds/day of extra latency
...
Rule of thumb: under reserved-minute billing, per-minute (Baseten, Modal) beats per-token
once GPU saturation stays above ~60-70% utilization; below that, per-token wins.
```

逐项解读：

- **Scenario A**：per-token 两家每天不到 $2，per-minute 两家（Baseten、Anyscale）因全天预留贵了约 440–480 倍。对小流量创业公司，结论非常明确：用 per-token serverless。
- **Scenario B**：100M token/天对 900k tok/min 的卡来说也只是约 7.7% 的利用率（`100M / 1,296M`），所以 Baseten、Anyscale 仍不划算。Modal 之所以最便宜，是因为它只有 60 分钟下限、其余时间被假设为"完美缩容到零 + 满载打包"，这是对 Modal 有利的口径差异，而不是 Modal 真的在任何流量下都比 per-token 便宜。
- **Replicate**：两场景都是 $30/M，与流量无关；它的弱点完全来自"每次只输出 200 token 却按次收 $0.006"。
- **盈亏平衡**：精确扫描得 67% 时 Fireworks $781.49 < $792，68% 时 $793.15 > $792，交叉点约 67.9%，与代码结尾的"~60-70%"一致，与讲义"~30%"不一致。
- **冷启动**：只是常数 × 100，作为提示信息看即可。

---

## 7. 动手改一改

1. **精确盈亏平衡**（讲义练习 1）：写一个函数用解析式 `u* = per_minute / (tokens_per_minute × per_mtok / 1e6)` 输出任意 per-token/per-minute 组合的交叉点；再把扫描点改成 `range(5, 101, 1)` 验证。
2. **batch tier**（讲义练习 3）：给 `Vendor` 增加 `batch_discount: float = 0.0` 字段，`run_scenario` 增加参数 `batch_share`，计算 40% 流量走 5 折后的混合单价（Fireworks 应为 $0.72/M）。
3. **输入 token**：增加 `per_mtok_input` 字段与 `input_tokens_per_day` 参数，观察长 prompt（如 RAG）场景下排名是否变化。
4. **按小时流量曲线计费**：用 24 个元素的列表表示每小时 token 量，per-minute 厂商按"每小时需要的 GPU 数 = ceil(该小时 token / 满载每小时 token)"计费，替换"完美打包"的假设，比较与原结果的差异。
5. **冷启动入账**：假设每次冷启动导致 x% 用户放弃、每个用户价值 $y，把 `cold_start_penalty` 改成真正的"每日损失"并加入总成本；再模拟 `min_workers=1` 预热带来的额外预留费用。
6. **按名字取厂商**：把 `VENDORS[0]`、`VENDORS[2]` 改成按名字查找的字典 `{v.name: v for v in VENDORS}`，并在 `Vendor.__post_init__` 中校验"三种单价恰好只有一个非 None"。

---

## 8. 常见坑

- **直接比较 $/min 和 $/M tokens**：必须先套进工作量模型折算；这也是 skill 的第一条 hard reject。
- **把"30%"当常数**：盈亏平衡点完全由 `p_m / (r × p_t)` 决定，换价格、换引擎吞吐就会变；本代码参数下是 68%。
- **忽略预留下限**：per-minute 平台在低流量时的有效单价可能是 per-token 的几百倍（Scenario A 的 $396/M）。
- **相信"满载吞吐"**：`tokens_per_minute` 是 GPU 饱和时的数字，低并发时实际吞吐远低于它；用它算出的 per-minute 有效单价偏乐观。
- **厂商之间口径不一致**：Modal 60 分钟下限 vs Baseten 1440 分钟下限，会让比较结果偏向前者。
- **per-prediction 不看输出长度**：Replicate 的有效单价随每次输出 token 数反比变化，平均 6.7k token 以上时反而比 Fireworks 便宜。
- **按下标取元素**：`VENDORS[2]` 在列表重排后会悄悄取错厂商。
