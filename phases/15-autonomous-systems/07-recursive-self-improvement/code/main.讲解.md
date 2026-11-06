# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 07 节 递归自我改进：能力与 Alignment 的权衡 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py [--threshold 1.5] [--seed 11]` ｜ **依赖**：仅标准库（`argparse`、`random`、`statistics`、`dataclasses`）

---

## 1. 这份代码在考察什么

讲义把 RSI 的风险抽象成一场"复利竞赛"：能力 `C(t)` 以速率 `r_c` 复利增长，alignment `A(t)` 以 `r_a` 复利增长，差距 `M(t) = C(t) − A(t)` 在 `r_c > r_a` 时变大。这份代码就是这个模型的数值实验：

1. **复利与差距**：每轮 `C *= r_c + 噪声`、`A *= r_a + 噪声`，记录差距。
2. **暂停阈值**：差距首次 ≥ 阈值的那一轮就是"本应暂停等待人类审查"的时刻。
3. **三个场景**：A 能力更快、B 速率相同、C alignment 均值更快但能力噪声更大。
4. **Monte-Carlo**：对场景 A、C 各重复 500 次，统计越线比例和越线轮次。

更重要的学习点在于**批判性地读输出**：HEADLINE 对场景 B、C 的结论来自单条轨迹，被 Monte-Carlo（以及我们的额外实验）推翻；绝对差距 `C − A` 本身是依赖尺度的指标。

> 一句话：**用两条带噪声的指数曲线说明"小速率差在复利下变成大差距"，同时提醒你：单条随机轨迹不能当结论**。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `DEFAULT_SEED = 11` | 常量 | 默认随机种子 | 可复现 |
| `Config` | dataclass | `r_c`、`r_a`、两种噪声、阈值 | 竞赛参数 |
| `run` | 函数 | 模拟 `cycles` 轮，返回 `(轮次, C, A, C−A)` 列表 | 复利竞赛 |
| `crossing_cycle` | 函数 | 找差距首次 ≥ 阈值的轮次，未越线返回 −1 | 暂停阈值 |
| `print_trajectory` | 函数 | 跑一条 40 轮轨迹并打印约 9 个快照 | 单条轨迹 |
| `monte_carlo` | 函数 | 重复 `trials` 次，统计越线比例、均值、中位数 | 统计检验 |
| `main` | 函数 | 解析参数、设种子、跑三个场景 + 两组 Monte-Carlo、打印 HEADLINE | 入口 |

数据流：命令行 `--threshold/--seed` → `random.seed` → 3 × `print_trajectory`（`run` → `crossing_cycle`）→ 2 × `monte_carlo`（500 × `run`）→ 固定文字的 HEADLINE。

---

## 3. 逐段精讲

### 3.1 配置

```python
@dataclass
class Config:
    r_c: float
    r_a: float
    noise_c: float
    noise_a: float
    threshold: float = 1.5
```

| 场景 | `r_c` | `r_a` | `noise_c` | `noise_a` | 含义 |
|------|------|------|----------|----------|------|
| A | 1.15 | 1.08 | 0.02 | 0.03 | 能力每轮 +15%，alignment +8% |
| B | 1.10 | 1.10 | 0.02 | 0.03 | 速率相同，只有噪声 |
| C | 1.10 | 1.13 | 0.06 | 0.01 | alignment 均值更快，但能力噪声大 3 倍 |

- 注意 `threshold` 在 `main` 中被命令行参数覆盖，三个场景用同一个阈值。

### 3.2 `run()`：两条带噪声的复利曲线

```python
def run(cycles: int, cfg: Config) -> list[tuple[int, float, float, float]]:
    c = 1.0
    a = 1.0
    out = [(0, c, a, c - a)]
    for cyc in range(1, cycles + 1):
        nc = cfg.r_c + random.gauss(0, cfg.noise_c)
        na = cfg.r_a + random.gauss(0, cfg.noise_a)
        c *= max(0.9, nc)
        a *= max(0.9, na)
        out.append((cyc, c, a, c - a))
    return out
```

- 起点 `C = A = 1`，差距 0；第 n 轮的期望近似 `C ≈ r_c^n`、`A ≈ r_a^n`。
- 每轮乘子 = 均值速率 + 高斯噪声。这是一个**几何随机游走**：`log C` 每轮加上 `log(乘子)`。
- `max(0.9, nc)`：乘子下限 0.9，即单轮最多跌 10%（防止噪声导致骤降或负数）；对上涨没有上限。在本节参数下几乎不触发（场景 C 的能力乘子低于 0.9 的概率约 0.04%）。
- 返回值是"轨迹"：每轮一个四元组，第 0 轮也包含在内。
- ⚠️ 模型把"能力"和"alignment"放在**同一个数值尺度**上直接相减。现实中二者单位不同，`C − A` 只是一种隐喻；讲义的 skill 文件也建议对每个轴分别设阈值。

**场景 A 的确定性对照**（无噪声）：

| 轮次 n | `1.15^n` | `1.08^n` | 差距 |
|-------|---------|---------|------|
| 8 | 3.059 | 1.851 | 1.208 |
| 9 | 3.518 | 1.999 | **1.519**（首次 ≥ 1.5） |
| 10 | 4.046 | 2.159 | 1.887 |
| 11 | 4.652 | 2.332 | **2.321**（首次 ≥ 2.0） |

### 3.3 `crossing_cycle()`：第一次越线

```python
def crossing_cycle(trajectory, threshold: float) -> int:
    for cyc, _c, _a, gap in trajectory:
        if gap >= threshold:
            return cyc
    return -1
```

- 在 for 循环里直接解包四元组，`_c`、`_a` 表示不用。
- 用 −1 作为"未越线"的哨兵值；调用方用 `cross >= 0` 判断。Python 里更地道的写法是返回 `None`（类型注解为 `int | None`）。
- 只看"有符号差距 ≥ 阈值"：alignment 领先（差距为负）永远不触发——这符合"能力超过 alignment 才危险"的设定。

### 3.4 `print_trajectory()`：只打印约 9 个快照

```python
    step = max(1, cycles // 8)
    for cyc, c, a, gap in traj:
        if cyc == 0 or cyc == cycles or cyc % step == 0:
            flag = "PAUSE" if gap >= cfg.threshold else "ok"
            print(f"  {cyc:>6}  {c:>8.2f}  {a:>8.2f}  {gap:>+8.2f}  {flag}")
```

- `cycles // 8` 是整除；40 轮时 `step = 5`，打印 0、5、10、…、40 共 9 行。`max(1, …)` 防止 `cycles < 8` 时 `step = 0` 导致取模除零。
- `{gap:>+8.2f}`：`+` 表示总是显示正负号，便于一眼看出谁领先。
- ⚠️ 只打印快照，越线发生在两个快照之间时（如场景 A 在第 9 轮越线），表格里看不到那一行，要看下方的 "threshold crossed at cycle 9"。

### 3.5 `monte_carlo()`：用重复实验说话

```python
def monte_carlo(cfg: Config, cycles: int, trials: int) -> None:
    crossings = []
    for _ in range(trials):
        traj = run(cycles, cfg)
        cross = crossing_cycle(traj, cfg.threshold)
        if cross >= 0:
            crossings.append(cross)
    print(f"  crossed: {len(crossings)} ({len(crossings)/trials:.0%})")
    if crossings:
        avg = sum(crossings) / len(crossings)
        p50 = statistics.median(crossings)
```

- 只对**越线的试验**统计均值和中位数（条件统计）；未越线的不计入。
- `statistics.median` 在元素个数为偶数时返回中间两数的平均，所以会出现 `9.0`、`21.0` 这样的浮点。
- ⚠️ `{…:.0%}` 把 2/500 = 0.4% 显示成 "0%"，与前面的 "2" 并列显得矛盾，应改为 `.1%`。
- ⚠️ Monte-Carlo 用 30 轮，而单条轨迹用 40 轮，二者不可直接比较。
- ⚠️ 只对 A、C 做了 Monte-Carlo，恰恰漏掉了 HEADLINE 下了强结论的场景 B。

### 3.6 `main()`：命令行参数与 HEADLINE

```python
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=float, default=1.5,
                        help="pause-gap threshold C - A (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, ...)
    args = parser.parse_args()
    random.seed(args.seed)
```

- `description=__doc__` 把模块文档字符串作为 `--help` 的说明；`%(default)s` 会被 argparse 替换为默认值。
- 整个程序共用一个全局 RNG：三条轨迹和两组 Monte-Carlo 依次消耗随机数，改动其中任何一段都会改变后面所有结果。

HEADLINE 是**硬编码文字**：

```python
    print("  Scenario A crosses the absolute 1.5 gap (C - A) in under 10 cycles.")
    print("  Scenario B stays bounded — same mean rate, noise-only drift.")
    print("  Scenario C: higher alignment mean does NOT save you if")
    print("  capability has big surges. Noise matters as much as drift.")
```

与实际数据的核对：

| HEADLINE 说法 | 实测 | 结论 |
|--------------|------|------|
| A 在 10 轮内越过 1.5 | 单条轨迹第 9 轮，Monte-Carlo 100% 越线、中位数 9 | 成立（但阈值改成 2.0 后变成 11 轮，这句仍写 1.5） |
| B stays bounded | 2000 次试验：30 轮内 37.3% 越线，40 轮 55.3%，100 轮 77.5% | **不成立**，只是这条轨迹没越线 |
| C 的高 alignment 均值救不了你 | 500 次只有 2 次越线（0.4%）；2000 次 0.5% | **与数据相反**；`noise_c` 加到 0.15 才有 25.4% |

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用乘法复利建模能力与 alignment | 直接对应讲义 `r_c`、`r_a` 的"compounding"叙述 | 真实能力与 alignment 不在同一尺度、也未必复利；生产中对每个轴分别设阈值 |
| 绝对差距 `C − A` + 固定阈值 | 直观 | 依赖尺度：早期太松、后期太敏感；应改用比值或对数差距 |
| 对称高斯噪声 | 一行代码 | 无法表达"偶发暴涨"；surge 应建模为偏态跳跃过程 |
| 乘子下限 0.9 | 防止骤降/负值 | 不对称地限制下跌、不限制上涨；对本节参数几乎无影响 |
| 单条轨迹 + Monte-Carlo | 既有可看的例子又有统计 | B 没做 Monte-Carlo；HEADLINE 硬编码，与统计结果矛盾 |
| 只检查差距 | 简单 | skill 文件还要求单轮变化上限、回退监控、人工恢复契约（测验 Q12） |
| 全局 `random` | 简洁 | 各段互相影响；需要独立可复现时应传 `random.Random(seed)` 实例 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| `@dataclass` + 默认值 | `threshold: float = 1.5` | 自动生成构造函数；有默认值的字段放最后 |
| 复杂类型注解 | `-> list[tuple[int, float, float, float]]` | 返回"四元组列表" |
| 元组列表 | `out = [(0, c, a, c - a)]`、`out.append((cyc, c, a, c - a))` | 注意 `append` 需要双层括号 |
| 增强赋值 | `c *= max(0.9, nc)` | 等价于 `c = c * max(0.9, nc)` |
| `max` 做下限钳制 | `max(0.9, nc)` | 取较大值即"不低于 0.9" |
| for 中解包 | `for cyc, _c, _a, gap in trajectory:` | 下划线前缀表示不使用 |
| 哨兵返回值 | `return -1` | 用特殊值表示"没找到"；也可用 `None` |
| 整除与取模 | `cycles // 8`、`cyc % step == 0` | 选择要打印的行 |
| f-string 格式符 | `{cyc:>6}`、`{c:>8.2f}`、`{gap:>+8.2f}`、`{x:.0%}` | 宽度、小数位、强制正负号、百分比 |
| `statistics.median` | `statistics.median(crossings)` | 中位数；偶数个时取中间两数平均 |
| `argparse` | `parser.add_argument("--threshold", type=float, default=1.5, help=...)` | 解析命令行；`type` 自动转换类型；`%(default)s` 在帮助中显示默认值 |
| `__doc__` | `ArgumentParser(description=__doc__)` | 模块顶部三引号字符串 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py`（Python 3.13，seed 11，瞬间完成），节选：

```text
Scenario A — capability outpaces alignment
   cycle      C(t)      A(t)       C-A  flag
       5      1.93      1.45     +0.48  ok      ← 比值已约 1.33，但绝对差距小
      10      4.15      2.12     +2.04  PAUSE
      40    330.77     22.42   +308.34  PAUSE   ← 比值约 14.8
  -> threshold crossed at cycle 9                ← 与确定性答案 9 一致

Scenario B — matched rates (noise-only drift)
      25     12.97     13.87     -0.90  ok
      35     33.16     36.88     -3.72  ok      ← 绝对差距的摆幅随规模变大
      40     55.83     54.51     +1.32  ok
  -> threshold not crossed in simulated window   ← 这一条恰好没越线

Scenario C — alignment higher mean rate but capability surges
      40     33.94    127.16    -93.22  ok      ← alignment 遥遥领先
  -> threshold not crossed in simulated window

Monte-Carlo on Scenario A
  crossed: 500 (100%)
  mean crossing cycle: 9.4
  median crossing cycle: 9.0

Monte-Carlo on Scenario C
  crossed: 2 (0%)                                ← 实为 0.4%
  mean crossing cycle: 21.0
```

逐项解读：

- **场景 A**：噪声很小（0.02/0.03），轨迹基本贴着确定性曲线，第 9 轮越线；Monte-Carlo 中位数 9.0、全部越线。这部分完全支持讲义"small rate differences compound"。
- **场景 B**：单条轨迹没越线，但我们用 2000 次试验额外验证：30 轮内 37.3%、40 轮内 55.3% 越线。原因是 `log(C/A)` 做随机游走（每步标准差约 0.033），而绝对差距 = 规模 × 相对偏差，规模指数增长。所以"stays bounded"不成立——这正是讲义练习 2 想引出的观察。
- **场景 C**：alignment 每轮多 3 个百分点，40 轮后领先近 4 倍；能力噪声 0.06 远不足以抵消。Monte-Carlo 只有 0.4% 越线。我们实测：`noise_c` 提到 0.10、0.15、0.20 时，30 轮越线比例分别为 8.2%、25.4%、40.5%。
- **`--threshold 2.0`**（讲义练习 1）：单条轨迹第 10 轮越线（4.15 − 2.12 = 2.04），Monte-Carlo 均值 10.8、中位数 11.0；确定性答案是 11。场景 C 的 Monte-Carlo 变为 0 次越线。HEADLINE 仍然写 "1.5 gap … under 10 cycles"。

---

## 7. 动手改一改

1. **（讲义练习 1）** 跑 `python main.py --threshold 2.0` 和 `--threshold 3.0`，把单条轨迹、Monte-Carlo 中位数与确定性公式 `min n: 1.15^n − 1.08^n ≥ th` 放在一张表里对比。
2. **（讲义练习 2）** 给场景 B 也加上 Monte-Carlo，分别跑 30、40、100 轮，验证"差距是否有界"；再把 `crossing_cycle` 改成对数差距（测验 Q10），比较两种指标下的越线比例。
3. **修 HEADLINE**：让 `monte_carlo` 返回 `(越线比例, 中位数)`，用实际数字和实际阈值拼出结论句；把百分比格式改成 `.1%`。
4. **建模能力暴涨**：给能力乘子加"5% 概率 ×1.5 跳跃"（测验 Q9），观察场景 C 的越线比例如何变化，并说明为什么"均值更高"不足以保证安全。
5. **实现 pause spec**：按测验 Q12 改写成 `run_with_pause`，同时检查对数差距、单轮涨幅 ≥30%、单轮跌幅 ≥5%，返回暂停轮次与原因。
6. **进阶**：把"alignment 检查"建模为有误差的外部评估器（例如观测值 = 真实 A × (1 + 噪声)，且被评估方在知道被评估时表现更好），研究"评估器噪声 / 被钻空子"如何让暂停来得太晚——这对应 workshop 的 evaluator generalization 问题。

---

## 8. 常见坑

- **把单条随机轨迹当结论**：本节 HEADLINE 对 B、C 的结论就是这样得出的，并且被统计结果推翻。任何带噪声的模拟都要多次重复。
- **用绝对差距设固定阈值**：两条指数曲线的绝对差距本身就会指数增长；应该用比值或对数差距。
- **百分比格式丢精度**：`:.0%` 把 0.4% 显示为 0%。
- **以为"均值更高"就安全**：真实风险来自尾部事件（偶发暴涨）；对称高斯噪声建模不了它。
- **全局 RNG 的连锁效应**：在中间插入一次 `run()` 会改变后面所有结果，比较实验时要固定每段的种子。
- **硬编码的结论文字**：参数一改就失真；结论应当由计算结果生成。
- **忽略 `max(0.9, …)` 的不对称**：它只限制下跌，不限制上涨；若要建模"单轮变化上限"，应当显式检查并暂停，而不是悄悄钳制数值。
