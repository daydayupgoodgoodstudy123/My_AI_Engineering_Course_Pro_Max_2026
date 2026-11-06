# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 27 节 LLMs 的 FinOps：单位经济性与多租户成本归因 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`、`random`、`statistics`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

这是一个约 80 行的"玩具"多租户 LLM 计费模拟器，用来演示讲义中的**三级执行阶梯**：

1. **每租户的策略对象**：合同日额、限流、花费上限倍数、kill switch 的 z-score 阈值——对应讲义"Enforcement ladder"。
2. **每租户的运行状态**：今日花费、历史日花费、是否已暂停——这是做 z-score 基线所需的最小状态。
3. **成本模型**：请求数 × 每请求 token 数 × 单价，对应"成本是 token 交易"这一核心观点。
4. **异常检测**：用租户自己的历史日花费求均值与样本标准差，花费 z-score > 4 时自动暂停（kill switch）。

但它也是一份**与描述不符**的代码：限流字段从未执行；花费上限只打印不收紧；更重要的是，按默认种子运行时 kill switch 暂停的是**正常租户 A**，而标题里的"滥用租户 C"从未触发任何一级阶梯。读懂这些偏差，正好能理解 z-score 异常检测在真实 FinOps 中的陷阱。

> 一句话：**用三十行模拟把"限流 → 上限 → 熔断"串起来，同时暴露"相对自身基线的 z-score 抓不住一直很贵的客户、却会误杀低波动的客户"这一工程教训。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TenantPolicy` | dataclass | 合同日额、每分钟限流、cap 倍数（默认 2.0）、kill 阈值（默认 4.0） | 执行阶梯的参数 |
| `TenantState` | dataclass | 今日花费、`minute_count`（未用）、历史日花费、是否暂停 | 租户运行时状态 / 基线 |
| `TENANTS` | 模块级字典 | 3 个租户：`(策略, 状态, 流量倍数)`，倍数分别为 1.0、2.5、25.0 | 多租户 |
| `simulate_day` | 函数 | 为每个未暂停租户生成当日请求与花费，检查 cap 与 z-score | 成本计算 + 第 2、3 级阶梯 |
| `main` | 函数 | 固定种子，跑 10 天；每天打印状态、记录历史、清零花费 | 驱动循环 |

数据流：`main` 设定 `random.seed(7)` → 每天调用 `simulate_day` 累加 `spend_today_usd` 并检查 cap / z-score → `main` 打印每个租户状态 → 把当天花费 append 到 `daily_history` → 未暂停的租户清零 → 下一天。

---

## 3. 逐段精讲

### 3.1 策略与状态：两个 dataclass

```python
@dataclass
class TenantPolicy:
    contracted_daily_usd: float
    rate_limit_per_min: int
    spend_cap_multiplier: float = 2.0
    kill_z_score: float = 4.0


@dataclass
class TenantState:
    spend_today_usd: float = 0.0
    minute_count: int = 0
    daily_history: list = field(default_factory=list)
    paused: bool = False
```

- **策略与状态分离**：策略是"合同 + 配置"，基本不变；状态是每天变化的运行数据。生产中策略来自租户配置库，状态在 Redis / 流处理引擎里。
- `spend_cap_multiplier = 2.0` 落在讲义"1.5–3x contracted ceiling"区间内；`kill_z_score = 4.0` 对应"spend z-score > 4"。
- `field(default_factory=list)`：可变默认值必须这样写，否则所有实例会共享同一个列表（见第 5 节）。
- ⚠️ `rate_limit_per_min` 和 `minute_count` **在整个文件中从未被读取**——第一级阶梯（rate limit）实际上不存在。

### 3.2 三个租户

```python
TENANTS = {
    "tenant_A_normal":  (TenantPolicy(100.0, rate_limit_per_min=120), TenantState(), 1.0),
    "tenant_B_growing": (TenantPolicy(50.0,  rate_limit_per_min=60),  TenantState(), 2.5),
    "tenant_C_abusive": (TenantPolicy(20.0,  rate_limit_per_min=40),  TenantState(), 25.0),
}
```

- 每个值是一个三元组：`(策略, 状态, 流量倍数)`。C 的流量是 A 的 25 倍，合同额却只有 A 的 1/5——意图是"小合同、大用量"的滥用者。
- ⚠️ 名字叫 "growing" 的 B 并没有随时间增长：倍数恒为 2.5。
- ⚠️ 状态对象挂在**模块级全局变量**上，多次调用 `main()` 会沿用上一次的状态（见第 8 节）。

### 3.3 成本计算

```python
        requests = int(100 * traffic_mult * random.uniform(0.8, 1.3))
        tokens_per_req = int(random.gauss(600, 150))
        cost_per_req = (tokens_per_req / 1e6) * 10.0
        total_spend = requests * cost_per_req
        state.spend_today_usd += total_spend
```

- 每日请求数 = 100 × 倍数 × [0.8, 1.3) 的均匀噪声：A 约 80–130 次，C 约 2,000–3,250 次。
- 每请求 token 数服从均值 600、标准差 150 的正态分布——**每天只抽一次**，当天所有请求共享同一个值（简化）。
- 单价 $10 / M tokens，不区分输入/输出、不区分缓存命中——讲义强调的"四个 token 层"在这里被压成了一个数。
- 数量级：600 tokens × $10/M = **$0.006/请求**。于是 A 每天约 $0.6（合同额 $100 的 0.6%），C 每天约 $15（合同额 $20 以内）。**所有租户都没有超出合同**——这直接导致第二级阶梯永远不触发。

### 3.4 第二级：花费上限（只告警）

```python
        if state.spend_today_usd > policy.contracted_daily_usd * policy.spend_cap_multiplier:
            if verbose:
                print(f"  [cap breach] {name}: ${state.spend_today_usd:.2f} > cap ${...:.2f} → tighten rate + alert CS")
```

- cap = 合同额 × 2.0：A $200、B $100、C $40。
- ⚠️ 只 `print`，没有任何"收紧 rate"的状态改变；并且 C 的最高日花费（本次 $21.88，500 个种子中最高 $33.54）始终低于 $40，这条分支**从未执行**。

### 3.5 第三级：z-score kill switch

```python
        if len(state.daily_history) >= 5:
            mean = statistics.mean(state.daily_history)
            sd = statistics.stdev(state.daily_history) or 1
            z = (state.spend_today_usd - mean) / sd
            if z > policy.kill_z_score:
                state.paused = True
```

- 至少有 5 天历史才开始检测（第 6 天起）。
- `statistics.stdev` 是**样本标准差**（分母 n−1）；`or 1` 在 sd 恰好为 0 时用 1 兜底，避免除零。注意这个兜底是"1 美元"，对日花费只有几毛钱的租户来说意味着"永远不会触发"，对日花费上万的租户意味着"几乎必然触发"——单位不匹配。
- z-score 比较的是**今天 vs 该租户自己的历史**。这带来两个结构性问题：
  - **抓不住一直很贵的租户**：C 第 1 天就是 25 倍流量，基线本身就是"滥用"水平，sd 约 $4，z 最高只有 1.89。
  - **误杀低波动的租户**：A 基线 $0.60 ± $0.08，一天花 $0.97 就是 z = 4.80，被暂停。
- 只看单侧（`z > 阈值`），花费骤降不会报警——这对成本控制是合理的。

### 3.6 主循环：打印、记账、清零

```python
    for day in range(1, 11):
        print(f"\n— Day {day} —")
        simulate_day(day, verbose=True)
        for name, (policy, state, _) in TENANTS.items():
            status = "PAUSED" if state.paused else "active"
            print(f"  {name}: spend=${state.spend_today_usd:7.2f}, contract=${policy.contracted_daily_usd:.2f}  [{status}]")
            state.daily_history.append(state.spend_today_usd)
            if not state.paused:
                state.spend_today_usd = 0.0
```

- 当天的花费在**检查之后**才写入历史，所以基线不包含当天——这是正确的做法（否则异常值会稀释自己的 z）。
- ⚠️ 暂停后的处理：`simulate_day` 对暂停租户直接 `continue`，这里又不清零，于是每天把同一个 $0.97 再 append 一次。本次运行结束时 A 的历史为 `[0.70, 0.67, 0.64, 0.53, 0.60, 0.48, 0.55, 0.97, 0.97, 0.97]`——异常值被复制进基线。
- ⚠️ 没有恢复路径，`paused` 一旦为真永远为真。
- 结尾那句 "rate limits throttle; caps trigger alerts; kill switch catches blow-ups" 描述的是讲义中的设计，而不是这份代码实际做到的事。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 以"天"为粒度模拟 | 输出短、容易读 | 滥用要等一天结束才发现；生产按分钟/小时滑动窗口实时累计 |
| 单一单价 $10/M、每天一个 token 数 | 代码最短 | 无法体现四层 token、缓存折扣、batch 折扣；生产按供应商返回的 usage 精确计价 |
| 策略/状态分两个 dataclass | 清晰区分配置与运行数据 | 生产中策略在配置库、状态在 Redis/流处理里 |
| 相对自身基线的 z-score | 无需人工为每个租户设阈值 | 抓不住"一直很贵"、误杀"低波动"；应加 sd 下限、绝对金额门槛、稳健统计、季节性 |
| 最少 5 天历史 | 让演示在第 6 天就能触发 | 样本太少，正态假设下单次误报率约 1.1%（30 天时约 0.02%） |
| `or 1` 兜底 sd | 防止除零 | 单位与租户规模无关；应用相对下限如 `max(sd, 0.25 × mean)` |
| 暂停即永久 | 演示简单 | 需要"暂停—复核—恢复"状态机与审计日志 |
| 限流字段只声明不执行 | （疑为遗漏） | 应在网关按租户执行，返回 429 + `Retry-After` |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件第一行代码 | 让类型注解延迟求值（以字符串保存），可在注解中引用尚未定义的类；Python 3.7+ |
| `@dataclass` | `class TenantPolicy:` | 自动生成 `__init__`、`__repr__`、`__eq__`；字段按声明顺序成为构造参数 |
| 带默认值的字段 | `spend_cap_multiplier: float = 2.0` | 有默认值的字段必须放在无默认值字段之后 |
| `field(default_factory=list)` | `daily_history: list = field(default_factory=list)` | 可变默认值要用工厂函数，每个实例得到自己的新列表；直接写 `= []` 会报 `ValueError` |
| 类型注解 | `def simulate_day(day: int, verbose: bool) -> None:` | 只做文档/静态检查用，运行时不强制 |
| 位置参数 + 关键字参数混用 | `TenantPolicy(100.0, rate_limit_per_min=120)` | 第一个按位置给 `contracted_daily_usd`，第二个按名字给 |
| 元组作为字典值 + 解包 | `for name, (policy, state, traffic_mult) in TENANTS.items():` | 在 `for` 里直接把嵌套元组拆开 |
| `_` 占位 | `for name, (policy, state, _) in ...` | 表示不使用的变量 |
| `random.seed` / `uniform` / `gauss` | `random.seed(7)`、`random.uniform(0.8, 1.3)`、`random.gauss(600, 150)` | 固定种子保证可复现；均匀分布；正态分布 |
| `statistics.mean` / `stdev` | `statistics.stdev(state.daily_history)` | 标准库统计函数；`stdev` 是样本标准差（n−1），少于 2 个数据会抛 `StatisticsError` |
| `or` 短路取值 | `statistics.stdev(...) or 1` | 左边为假值（0.0）时取右边 |
| f-string 格式符 | `{state.spend_today_usd:7.2f}`、`{z:.2f}` | 宽度 7、保留两位小数 |
| 条件表达式 | `"PAUSED" if state.paused else "active"` | 三元运算 |
| 字符串乘法 | `"=" * 95` | 生成分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`random.seed(7)`，耗时不到 0.1 秒），截取关键部分：

```text
— Day 1 —
  tenant_A_normal: spend=$   0.70, contract=$100.00  [active]
  tenant_B_growing: spend=$   1.62, contract=$50.00  [active]
  tenant_C_abusive: spend=$  15.08, contract=$20.00  [active]
...
— Day 3 —
  tenant_C_abusive: spend=$  21.88, contract=$20.00  [active]   ← 超合同额，但 cap 是 $40
...
— Day 8 —
  [KILL SWITCH] tenant_A_normal: z=4.80 on spend $0.97 (baseline $0.60 ± $0.08) → auto-pause + page on-call
  tenant_A_normal: spend=$   0.97, contract=$100.00  [PAUSED]
  tenant_B_growing: spend=$   1.00, contract=$50.00  [active]
  tenant_C_abusive: spend=$  15.99, contract=$20.00  [active]
...
— Day 10 —
  tenant_A_normal: spend=$   0.97, contract=$100.00  [PAUSED]
  tenant_B_growing: spend=$   1.52, contract=$50.00  [active]
  tenant_C_abusive: spend=$  13.39, contract=$20.00  [active]

Read: rate limits throttle; caps trigger alerts; kill switch catches blow-ups.
```

逐项解读：

- **花费数量级**：A 约 $0.5–1.0、B 约 $1–3、C 约 $9–22，都远低于各自 cap（$200 / $100 / $40）。整次运行**没有一条 `[cap breach]`**。
- **被暂停的是 A，不是 C**。我们用脚本复现了每天检查时的 z 值：

| 天 | A 的 z（sd） | B 的 z（sd） | C 的 z（sd） |
|----|-------------|-------------|-------------|
| 6 | −2.24（0.06） | −0.05（0.71） | −0.24（4.63） |
| 7 | −0.67（0.08） | 0.04（0.64） | −0.40（4.17） |
| 8 | **4.80**（0.08） | −1.32（0.58） | 0.34（3.86） |
| 9 | — | −0.36（0.60） | 1.89（3.60） |
| 10 | — | −0.23（0.57） | −0.54（4.06） |

  A 的 sd 只有 $0.08，C 的 sd 有约 $4——相对量把"$0.37 的小波动"放大成了 4.8σ，把"每天 $15 的持续高花费"压成了不到 2σ。
- **多种子统计**：换 0–499 共 500 个种子各跑 10 天，A、B、C 被暂停的次数分别是 37、18、26 次（约 7%、4%、5%），与是否"滥用"基本无关。这个 kill switch 在当前设定下是噪声触发器。
- **暂停后的历史**：A 的 `daily_history` 末尾是三个 0.97，异常值被复制进了基线。
- **最后一行文字**：是讲义设计的复述，不是本次运行的结论。

---

## 7. 动手改一改

1. **（讲义练习 1）** 把 `kill_z_score` 改成 3、5、6，分别统计 500 个种子下各租户被暂停的比例，体会阈值与误报率的关系；再把"最少历史"从 5 改成 14，观察误报率变化。
2. **实现第一级限流**：把 `rate_limit_per_min` 换成与模拟粒度一致的 `rate_limit_per_day`，在 `simulate_day` 中 `allowed = min(requested, limit)`，打印被 429 拒绝的数量。
3. **让滥用"发生"**：把流量倍数改成按天变化的函数，例如 C 前 6 天为 1.0、第 7 天起为 25.0。我们跑过的变体里（同时加了限流 300 次/天和 sd 下限），C 在第 7 天被拒 2,266 次请求并以 z = 5.8 被暂停，A 不再被误杀。
4. **修正基线**：sd 用 `max(stdev, 0.25 * mean)` 做下限；暂停或异常的日子不 append 到历史；把 `mean/stdev` 换成 `median` 与 MAD（中位数绝对偏差），比较效果。
5. **拆开四层 token**：给每次请求生成 prompt/tool/memory/response 四个 token 数（比例参考讲义表格），分别计价（例如输入与输出不同单价、缓存输入打一折），输出每租户每层的花费占比。
6. **进阶**：把模拟粒度改成"小时"，加入"暂停—复核—恢复"状态机（自动降级到低速率而不是全停），并为每次状态变化写一条结构化审计日志。

---

## 8. 常见坑

- **相对基线 ≠ 绝对预算**：z-score 只能发现"变化"，对一开始就超额的租户无效；一定要有与合同额比较的绝对阈值（这正是 spend cap 的职责）。
- **低方差租户被误杀**：sd 很小时，几分钱的波动也会变成高 z；需要 sd 下限或绝对金额门槛。
- **小样本 z-score 的厚尾**：用 5 个样本估计 sd，误报率比"正态 4σ"高一到两个数量级。
- **异常值污染基线**：本代码在暂停后不断把同一花费 append 进历史；生产中应排除异常日或单独标记。
- **"声明了但没执行"的策略**：`rate_limit_per_min` 只在构造时出现。读 FinOps 代码时要逐个确认每个策略字段真的被执行了。
- **单位不匹配的兜底值**：`or 1` 中的"1"是美元，对不同规模的租户含义完全不同。
- **模块级可变状态**：`TENANTS` 里的 `TenantState` 是全局对象；在同一个进程里第二次调用 `main()`（例如在 notebook 中）会继承上次的历史和暂停状态，结果不可复现。要重新创建状态或把它们放进 `main` 内部。
- **`statistics.stdev` 的前提**：少于 2 个数据会抛异常；这里靠"至少 5 天"间接避免，改动最短历史时要小心。
