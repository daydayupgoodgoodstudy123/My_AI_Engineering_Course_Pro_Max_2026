# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 01 节 从聊天机器人转向长程 Agents ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`dataclasses`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

这是一个"数字直觉"模拟器，不调用任何模型，只做三件算术：

1. **horizon 指数外推**：给定基线 horizon（14 小时）和倍增时间（7 个月），算出未来每个月的 50% horizon，以及穿越 1 天、2 天、1 周、1 个月所需的月数——对应讲义 "Doubling times and what they imply"。
2. **可靠性复利**：每步成功率 p、N 步全成功的概率 `p^N`，以及为了保持 50% 端到端成功率最多能跑多少步——对应讲义 "a 99% per-step reliable agent still fails half the time on a 70-step trajectory"。
3. **eval-vs-deploy 折扣**：把基准 horizon 乘以 `(1 − gap)` 得到"部署 horizon"——对应讲义 "Eval-context gaming" 与 "horizon is a ceiling, not a floor"。

> 一句话：**同时把"能力在指数增长"和"可靠性在指数衰减"两个数字放进脑子里**，再决定要不要让 agent 无人值守地跑。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `HorizonConfig` | dataclass | 保存基线 horizon、基线月份、倍增时间 | METR 拟合出的趋势参数 |
| `horizon_at` | 函数 | `h0 · 2^((m − m0)/T)` | 指数外推 |
| `months_to_cross` | 函数 | `m0 + T · log2(target/h0)` | 外推的反函数 |
| `end_to_end_reliability` | 函数 | `p^N` | 可靠性复利 |
| `max_steps_for_target` | 函数 | `floor(ln target / ln p)` | 给定目标下的最大轨迹长度 |
| `fmt_hours` | 函数 | 把小时数格式化为 min / hr / day | 可读输出 |
| `horizon_projection` | 函数 | 打印 0–36 个月的 horizon 表与穿越月份 | 讲义 2026/2027/2028 外推 |
| `reliability_compounding` | 函数 | 打印 8 组 (p, N) 的端到端成功率与分级标签 | "70 步就是抛硬币" |
| `deploy_gap_note` | 函数 | 打印 3 个 horizon × 3 档 gap 的部署值 | eval-vs-deploy 差距 |
| `main` | 函数 | 依次调用三个演示并打印结论 | 入口 |

数据流：`main()` → `horizon_projection()`（`HorizonConfig` → `horizon_at` / `months_to_cross` → `fmt_hours`）→ `reliability_compounding()`（`end_to_end_reliability` / `max_steps_for_target`）→ `deploy_gap_note()` → 打印 HEADLINE。三段之间没有数据传递，彼此独立。

---

## 3. 逐段精讲

### 3.1 `HorizonConfig`：用 dataclass 存三个参数

```python
@dataclass
class HorizonConfig:
    baseline_hours: float
    baseline_month: int  # months since epoch (0 = now)
    doubling_months: float
```

- `@dataclass` 自动生成 `__init__`、`__repr__`、`__eq__`，适合这种"只装数据"的类。
- 三个字段正好是指数曲线 `h(m) = h0 · 2^((m − m0)/T)` 的三个参数：`h0 = baseline_hours`、`m0 = baseline_month`、`T = doubling_months`。
- 文件头的 `from __future__ import annotations` 让类型注解延迟求值（在 3.10+ 中写 `int | None` 之类也不会报错），在本文件中只起"保持风格一致"的作用。

### 3.2 指数外推与它的反函数

```python
def horizon_at(cfg: HorizonConfig, months_from_now: int) -> float:
    delta = months_from_now - cfg.baseline_month
    return cfg.baseline_hours * (2 ** (delta / cfg.doubling_months))


def months_to_cross(cfg: HorizonConfig, target_hours: float) -> float:
    ratio = target_hours / cfg.baseline_hours
    return cfg.baseline_month + cfg.doubling_months * math.log2(ratio)
```

- `horizon_at`：每过 T 个月乘 2。`delta / doubling_months` 是"经过了几次倍增"（可以是小数），所以 6 个月是 `2^(6/7) ≈ 1.81` 倍：`14 × 1.81 = 25.4` 小时，打印为 `1.1 day`。
- `months_to_cross`：解方程 `h0 · 2^((m − m0)/T) = target` 得 `m = m0 + T · log2(target/h0)`。两个函数互为反函数。
- 讲义的外推：2027 年约 48 小时（代码 12 个月时 45.9 小时）、2028 年约一周（代码 24 个月时 150.7 小时 ≈ 6.3 天），数量级一致。
- ⚠️ 讲义强调这是"straight-line extrapolations, not predictions"——在对数坐标下是一条直线，在线性坐标下是指数曲线。
- 注意类型注解 `months_from_now: int`，但函数对 `float` 同样正确；注解只是提示，Python 运行时不检查。

### 3.3 可靠性复利

```python
def end_to_end_reliability(per_step: float, steps: int) -> float:
    return per_step ** steps


def max_steps_for_target(per_step: float, target: float) -> int:
    """Largest N such that per_step**N >= target."""
    if per_step >= 1.0:
        return 10**9
    return math.floor(math.log(target) / math.log(per_step))
```

- `p^N` 隐含三条假设：**每步独立**、**每步成功率相同**、**任何一步失败即整体失败**（没有重试或纠错）。
- 由 `p^N ≥ target` 两边取对数：`N · ln p ≥ ln target`。因为 `ln p < 0`，除过去不等号要翻转：`N ≤ ln target / ln p`，所以取 floor。
- 以 p = 0.99、target = 0.5 为例：`ln 0.5 / ln 0.99 = 68.97`，floor 后为 68。验证：`0.99^68 = 0.5049`、`0.99^69 = 0.4998`。
- `per_step >= 1.0` 时 `ln p = 0` 会除零，所以单独返回一个"很大的数" `10**9`。
- ⚠️ **浮点边界 bug**：数学上恰好是整数的比值会因浮点误差落在整数下方。实测 `max_steps_for_target(0.9, 0.81)` 返回 1，但 `0.9**2 >= 0.81` 为 True（`ln 0.81 / ln 0.9` 算出 `1.9999999999999998`）。`(0.7, 0.49)`、`(0.95, 0.9025)` 同样少算 1。默认演示里 target 都是 0.5，没有暴露。修法见测验 Q9。
- ⚠️ `per_step <= 0` 或 `target <= 0` 会抛 `ValueError: math domain error`，函数没有做输入校验。

### 3.4 `fmt_hours`：单位换算

```python
def fmt_hours(h: float) -> str:
    if h < 1:
        return f"{h * 60:.1f} min"
    if h < 24:
        return f"{h:.1f} hr"
    return f"{h / 24:.1f} day"
```

- 三段式：不足 1 小时显示分钟，不足 24 小时显示小时，否则显示天（一天按 24 小时计，不是工作日 8 小时）。
- 因此 `168` 小时显示为 `7.0 day`，`720` 小时显示为 `30.0 day`；单位不做复数处理（`day` 而非 `days`）。
- 用的是"提前 return"风格，代替 if/elif/else 嵌套。

### 3.5 `horizon_projection`：外推表

```python
    for m in (0, 6, 12, 18, 24, 30, 36):
        h = horizon_at(cfg, m)
        tag = ""
        if h < 24:
            tag = "workday-scale"
        elif h < 168:
            tag = "multi-day task"
        elif h < 720:
            tag = "week-scale"
        else:
            tag = "month-scale"
```

- 每 6 个月取一个点，共 3 年。
- 分级阈值：24 小时（1 天）、168 小时（1 周）、720 小时（30 天）。
- ⚠️ 标签较粗：14 小时被标为 `workday-scale`，但 14 小时已经接近两个 8 小时工作日；6 个月时 25.4 小时（1.1 天）被标为 `multi-day task`，其实刚过 1 天。讲义开头还写了 Opus 4.6 的 horizon 从秒增长到 "half a workday"，与同一讲义的 "14+ hours" 互相矛盾。
- `tag = ""` 的初始化是多余的（后面的 if/elif/else 一定会赋值），但无害。
- 穿越月份：`for target in (24, 48, 168, 720)`，分别对应 1 天、2 天、1 周、30 天。

### 3.6 `reliability_compounding`：复利表

```python
    cases = [
        (0.90, 10),
        (0.90, 50),
        (0.95, 50),
        (0.99, 50),
        (0.99, 70),
        (0.99, 200),
        (0.995, 200),
        (0.999, 1000),
    ]
    for per_step, steps in cases:
        p = end_to_end_reliability(per_step, steps)
        ...
        print(f"  {per_step:>10.3f}  {steps:>8}  {p:>12.1%}  {flag:<20}")
```

- `cases` 是元组列表，`for per_step, steps in cases` 直接解包。
- 四档 flag：`< 0.5` 抛硬币或更差、`< 0.8` 不可上生产、`< 0.95` 脆弱、其余 ok。这些阈值是教学设定，不是行业标准。
- `{p:>12.1%}`：`%` 格式符会把 0.495 显示为 `49.5%`（自动乘 100 并加百分号）。
- 后半段对五个 p 打印 50% 目标下的最大步数：6、13、68、138、692。
- 有意思的规律：`0.995^200 ≈ 0.999^1000 ≈ 1/e`，因为两者都满足 `N = 1/(1 − p)`。

### 3.7 `deploy_gap_note`：部署折扣

```python
    for horizon in (14.0, 48.0, 168.0):
        for gap in (0.0, 0.2, 0.4):
            effective = horizon * (1 - gap)
            print(f"  benchmark {fmt_hours(horizon):>7}  "
                  f"gap {gap:.0%}  ->  deploy "
                  f"{fmt_hours(effective):>7}")
```

- 双重循环：三个基准 horizon × 三档 gap。
- ⚠️ 这里的 0/20/40% 是**假设值**（与 `outputs/skill-horizon-reality-check.md` 中 "Apply a 20-40% gap" 一致），与上方打印的 alignment-faking 12% / 78% 之间没有推导关系；把两件事放在同一个标题下容易让人误以为 gap 是从研究数据算出来的。
- ⚠️ 线性折扣在指数趋势下意义有限：40% 的折扣只相当于倍增曲线"晚了" `7 × log2(1/0.6) ≈ 5.2` 个月。
- 多行 f-string：相邻的字符串字面量会被自动拼接，括号内可以随意换行。

### 3.8 `main` 与入口

```python
if __name__ == "__main__":
    main()
```

- `main()` 依次运行三段演示，最后打印 HEADLINE："At 7-month doubling, a multi-day horizon is ~1 year away. At 99% per-step, a 70-step trajectory is already a coin flip."
- 第一句与数字基本一致（2 天在第 12.4 个月穿越），但"1 天"其实在第 5.4 个月就已穿越。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 只用标准库、纯算术 | 零依赖，任何人都能跑，专注"数字直觉" | 不做真实拟合；真实 METR 方法是对任务成功率做 logistic 回归，需要任务数据 |
| 指数外推 `2^(m/T)` | 讲义采用的趋势模型 | 外推不是预测；生产决策应以当前实测能力为准 |
| `p^N` 独立失败模型 | 最简单、能直观展示复利 | 忽略纠错、重试、相关失败与静默失败；真实系统要配 checkpoint + 验证 |
| `floor(ln t / ln p)` 求最大步数 | 一行闭式解 | 浮点边界会少算 1；应加容差并回检 |
| `per_step >= 1` 返回 `10**9` | 避免除零 | 魔法数；可返回 `math.inf` 或抛异常 |
| 线性 gap 折扣 | 简单易懂 | gap 是假设值，不来自数据；应在自己的分布上实测部署 horizon |
| 用 dataclass 存配置 | 参数清晰、可复用 | 只有一个配置被用到，可扩展成多模型对比 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块 docstring | 文件开头的三引号字符串 | 描述模块用途，可被 `help()` 读取 |
| `from __future__ import annotations` | 第 12 行 | 类型注解推迟求值，便于使用新式注解语法 |
| `@dataclass` | `class HorizonConfig` | 自动生成构造函数等方法，字段用"名字: 类型"声明 |
| 类型注解 | `def horizon_at(cfg: HorizonConfig, months_from_now: int) -> float` | 只是提示，运行时不检查；`-> None` 表示无返回值 |
| 行尾注释 | `baseline_month: int  # months since epoch` | `#` 后为注释 |
| 幂运算 `**` | `per_step ** steps`、`2 ** (delta / T)`、`10**9` | 支持小数指数 |
| `math.log` / `math.log2` / `math.floor` | `math.log(target) / math.log(per_step)` | 自然对数、以 2 为底的对数、向下取整（返回 int） |
| 提前 return | `fmt_hours` 中的三个 `return` | 满足条件就返回，减少嵌套 |
| f-string 格式符 | `{h * 60:.1f}`、`{m:>8}`、`{tag:<30}`、`{p:>12.1%}`、`{gap:.0%}` | 保留小数位、右/左对齐宽度、百分比格式 |
| 字符串乘法 | `"-" * 70`、`"=" * 70` | 生成分隔线 |
| 元组与解包 | `for per_step, steps in cases` | 每个元素是 `(p, N)`，循环时直接拆开 |
| 遍历元组字面量 | `for m in (0, 6, 12, 18, 24, 30, 36)` | 不可变序列，适合固定取值 |
| if / elif / else 链 | flag、tag 的分级 | 按顺序判断，阈值需从小到大 |
| 嵌套循环 | `for horizon in ...: for gap in ...:` | 笛卡尔积 |
| 相邻字符串拼接 | `print(f"..." f"...")` | 括号内相邻字面量自动拼接，便于换行 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行 |

---

## 6. 运行结果解读

实际运行（Python 3，`cd code && python3 main.py`，瞬间完成）：

```text
METR-style horizon projection
  baseline: 14.0 hr at month 0 (Claude Opus 4.6, Jan 2026)
  doubling time: 7.0 months

     month       horizon  interpretation
         0       14.0 hr  workday-scale        ← 14 小时其实已近两个工作日
         6       1.1 day  multi-day task       ← 25.4 小时
        12       1.9 day  multi-day task       ← 45.9 小时，讲义"2027 年约 48 小时"
        18       3.5 day  multi-day task
        24       6.3 day  multi-day task       ← 150.7 小时，讲义"2028 年约一周"
        30      11.4 day  week-scale
        36      20.6 day  week-scale

  target crossings
    1.0 day: month 5.4
    2.0 day: month 12.4
    7.0 day: month 25.1
    30.0 day: month 39.8

Per-step reliability -> end-to-end reliability
    per-step     steps    end-to-end  flag
       0.900        10         34.9%  coin flip or worse
       0.900        50          0.5%  coin flip or worse
       0.950        50          7.7%  coin flip or worse
       0.990        50         60.5%  not production
       0.990        70         49.5%  coin flip or worse   ← 讲义的核心例子
       0.990       200         13.4%  coin flip or worse
       0.995       200         36.7%  coin flip or worse   ← ≈ 1/e
       0.999      1000         36.8%  coin flip or worse   ← ≈ 1/e

  max trajectory length for 50% end-to-end success
    per-step 0.900: up to 6 steps
    per-step 0.950: up to 13 steps
    per-step 0.990: up to 68 steps
    per-step 0.995: up to 138 steps
    per-step 0.999: up to 692 steps

Eval-vs-deploy adjustment
  benchmark 14.0 hr  gap 0%  ->  deploy 14.0 hr
  benchmark 14.0 hr  gap 20%  ->  deploy 11.2 hr
  benchmark 14.0 hr  gap 40%  ->  deploy  8.4 hr
  benchmark 2.0 day  gap 20%  ->  deploy 1.6 day
  benchmark 7.0 day  gap 40%  ->  deploy 4.2 day
  ...
```

逐项解读：

- **外推表**：每 7 个月翻倍，36 个月约 `2^(36/7) ≈ 35.4` 倍，14 小时 → 约 495 小时 ≈ 20.6 天。讲义练习 1 的答案：30 小时在第 7.7 个月穿越，168 小时在第 25.1 个月穿越。
- **复利表**：只有 0.99 × 50 步一行超过 50%（60.5%），其余全部是"抛硬币或更差"。0.9 × 50 步只剩 0.5%。
- **最大步数**：p 每向 1 靠近一个数量级（失败率 1% → 0.1%），最大步数大约扩大 10 倍（68 → 692），因为 `ln 0.5 / ln p ≈ 0.693 / (1 − p)`。讲义练习 2 的答案：0.995 下最多 138 步，0.99 下 68 步，0.999 下 692 步。
- **部署折扣**：纯线性乘法。注意 48 小时的基准 horizon 显示为 `2.0 day`，168 小时显示为 `7.0 day`。

---

## 7. 动手改一改

1. **（练习 1）**把 `target crossings` 改成 `(30, 168)`，验证 7.7 与 25.1 个月；再把 `doubling_months` 改成 4 个月和 12 个月，比较穿越时间的差别。
2. **（练习 2）**在 `max_steps_for_target` 的循环里加入 `0.995`、`0.9995` 和 target = 0.8、0.95，做一张"可靠性 × 目标"的二维表。
3. **修复浮点 bug**：给 `max_steps_for_target` 加输入校验、容差和乘方回检，使 `(0.9, 0.81)` 返回 2（参考测验 Q9）。
4. **加入 checkpoint + 重试**：写 `checkpointed_reliability(per_step, steps, segment, attempts)`，验证 200 步、每段 20 步、0.99 时 r = 1/2/3 的结果为 13.4% / 71.4% / 94.1%（参考测验 Q11）。
5. **递减的单步可靠性**：模拟"上下文越长越容易出错"——令第 i 步的成功率为 `p0 − k·i`，比较与常数 p 的差异。
6. **进阶（练习 3 方向）**：给定一组 (人类时长, 成功/失败) 的模拟数据，用 `log2(时长)` 做特征，手写梯度下降拟合 logistic 回归，求出 50% 与 80% horizon，体会"80% horizon 远短于 50% horizon"。

---

## 8. 常见坑

- **把 horizon 当成模型运行时长**：horizon 是"人类专家完成该任务的时长"，模型可能只用几分钟就完成了一个人类需要 2 小时的任务。
- **把 50% horizon 当成可交付能力**：在 horizon 这个长度上就有一半会失败；短于它的任务也不是 100%。
- **线性外推**：horizon 按 7 个月倍增是指数增长，"每 7 个月加 14 小时"是错的。
- **用 floor 处理浮点比值**：恰好整除的边界会少算 1，需要容差或回检。
- **忘记 `p^N` 的假设**：独立、同分布、不可恢复。真实 agent 有纠错能力，也有相关失败和静默失败，两个方向的偏差都存在。
- **把 gap 当成数据**：代码中的 20%/40% 是设定值，不是由 12%/78% 推出的。
- **单位换算**：`fmt_hours` 以 24 小时为一天；讨论"工作日"时要换成 8 小时。
