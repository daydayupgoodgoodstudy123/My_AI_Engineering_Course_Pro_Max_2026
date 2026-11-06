# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 21 节 对 LLM Features 进行 A/B 测试：GrowthBook、Statsig 与凭感觉判断的问题 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`），无需网络

---

## 1. 这份代码在考察什么

代码围绕一个二元结果（例如"是否转化"）的 A/B 实验做两件事：

1. **固定样本量计算**：给定基线转化率 3% 和相对提升 2% / 5% / 10%，用双比例检验的功效公式算出所需样本量，再乘以 1.4 作为 LLM 非确定性缓冲（讲义："Multiply required sample size by ~1.3-1.5x"）。
2. **序贯检验模拟**：逐个用户随机分组、按概率转化，每来一个样本就计算一次 z 统计量，并与一个随 `log(n)` 增长的"always-valid"边界比较，越线即停止。分别模拟真实提升 5%、10%、50% 的情况。

对应讲义的样本量与功效、序贯检验（mSPRT / confidence sequences）、LLM 非确定性缓冲三个概念。

> 一句话：**用功效公式回答"要多少用户"，用逐样本的序贯模拟回答"能不能提前停"**。要注意：样本量是每组口径、模拟上限却是两组合计；docstring 说的 CUPED 并没有实现；序贯边界是启发式的，需要自己用 A/A 模拟验证。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `z_statistic(success_a, n_a, success_b, n_b)` | 函数 | 合并方差的双比例 z 统计量，带除零保护 | 假设检验 |
| `fixed_sample_size(p_baseline, lift, alpha, power)` | 函数 | 双比例检验的每组样本量 | 功效分析 |
| `simulate(p_a, p_b, seed, max_n)` | 函数 | 逐样本分组、转化、每步检查序贯边界 | 序贯检验 |
| `main()` | 函数 | 打印三个提升下的样本量与 ×1.4 缓冲；跑三次模拟 | 入口 |

数据流：`main()` → 对 `lift in (0.02, 0.05, 0.10)` 调 `fixed_sample_size` 并 ×1.4 → 三次 `simulate(0.03, p_b)`，内部每步调 `z_statistic` 与边界比较 → 打印最终样本数、观测转化率、停止位置。

---

## 3. 逐段精讲

### 3.1 双比例 z 统计量

```python
def z_statistic(success_a: int, n_a: int, success_b: int, n_b: int) -> float:
    p_a = success_a / n_a if n_a else 0
    p_b = success_b / n_b if n_b else 0
    p = (success_a + success_b) / (n_a + n_b) if (n_a + n_b) else 0
    se = math.sqrt(p * (1 - p) * (1 / n_a + 1 / n_b)) if n_a and n_b else 1
    return (p_b - p_a) / se if se > 0 else 0
```

- 公式：`z = (p̂_B − p̂_A) / √(p̂(1 − p̂)(1/n_A + 1/n_B))`，其中 `p̂` 是两组合并的转化率——这是原假设"两组相同"下的标准误。
- 每一行都用条件表达式防止除以 0：样本数为 0 时返回 0；合并转化率为 0（还没有任何转化）时 `se = 0`，返回 0。
- z > 0 表示 B 组更好；`simulate` 中用 `abs(z)` 做**双侧**检验。

### 3.2 固定样本量公式

```python
def fixed_sample_size(p_baseline: float, lift: float, alpha: float = 0.05, power: float = 0.80) -> int:
    p_treat = p_baseline * (1 + lift)
    z_alpha = 1.96
    z_beta = 0.84
    p_bar = (p_baseline + p_treat) / 2
    num = (z_alpha * math.sqrt(2 * p_bar * (1 - p_bar)) +
           z_beta * math.sqrt(p_baseline * (1 - p_baseline) + p_treat * (1 - p_treat))) ** 2
    den = (p_treat - p_baseline) ** 2
    return int(num / den)
```

- `lift` 是**相对**提升：3% × 1.05 = 3.15%，绝对差只有 0.15 个百分点。分母是差值的平方，所以提升减半，样本量约翻 4 倍：10% → 53,150，5% → 207,702，2% → 1,279,744。
- 结果是**每组**样本量（这是该公式的标准含义），输出文字没有注明。
- ⚠️ `alpha` 和 `power` 是参数，却没有被使用：`z_alpha = 1.96`、`z_beta = 0.84` 写死了，调用 `fixed_sample_size(0.03, 0.05, power=0.9)` 不会有任何变化。应改为 `NormalDist().inv_cdf(1 - alpha/2)` 和 `NormalDist().inv_cdf(power)`。
- ⚠️ `int()` 向下截断；样本量应向上取整。用精确分位数并 `ceil` 后，5% 提升为每组 207,938（差约 0.1%）。

### 3.3 序贯模拟：逐样本分组与转化

```python
def simulate(p_a: float, p_b: float, seed: int = 7, max_n: int = 300_000) -> dict:
    rng = random.Random(seed)
    success_a = success_b = 0
    n_a = n_b = 0
    sequential_stopped_at = None
    for _ in range(max_n):
        group = rng.random() < 0.5
        if group:
            n_b += 1
            if rng.random() < p_b:
                success_b += 1
        else:
            n_a += 1
            if rng.random() < p_a:
                success_a += 1
```

- 每个样本先抛一次硬币决定组别（独立伯努利分配，不是严格 50/50），再按该组转化率抛一次决定是否转化。
- `success_a = success_b = 0` 是链式赋值，两个变量都绑定到 0（整数不可变，安全）。
- ⚠️ `max_n = 300_000` 是**两组合计**的上限，每组约 15 万——而 5% 提升的固定检验需要每组 207,702，所以那次模拟注定功效不足。

### 3.4 序贯边界

```python
        if n_a > 100 and n_b > 100 and sequential_stopped_at is None:
            z = z_statistic(success_a, n_a, success_b, n_b)
            # Always-valid z-boundary (mSPRT-style): grows with log(n) so Type-I stays bounded.
            # threshold(n) ≈ sqrt(2 * log(1/alpha) + log(n)) for alpha=0.05.
            n_total = n_a + n_b
            threshold = math.sqrt(2 * math.log(1 / 0.05) + math.log(n_total))
            if abs(z) > threshold:
                sequential_stopped_at = n_total
                break
```

- 每组都超过 100 个样本后，**每来一个样本就检查一次**——这是最极端的"持续偷看"。
- 边界 `√(2 ln 20 + ln n)`：n = 202 时 3.36，n = 2,774 时 3.73，n = 300,000 时 4.31。它随 `ln n` 缓慢增长，用来抵消"看得越多、越容易碰巧越线"的效应。
- 这个形式与"迭代对数律"/混合似然比边界的思想相近，但代码没有给出推导，它是一个**启发式**边界，不是 mSPRT 的标准公式。我们用 A/A 模拟验证了它（第 6 节）：第一类错误约 0.3%，确实在 5% 以内，但相当保守。
- `sequential_stopped_at is None` 的判断在 `break` 存在时是多余的（一旦赋值就立即跳出循环），保留它无害。
- `alpha = 0.05` 写死在表达式里，没有参数化。

### 3.5 返回值与 `main()`

```python
    return {
        "n_a": n_a,
        "n_b": n_b,
        "p_a_observed": success_a / n_a if n_a else 0.0,
        "p_b_observed": success_b / n_b if n_b else 0.0,
        "sequential_stop_at": sequential_stopped_at,
    }
```

```python
    baseline = 0.03
    for lift in (0.02, 0.05, 0.10):
        required = fixed_sample_size(baseline, lift)
        adjusted = int(required * 1.4)  # LLM non-determinism buffer
        ...
    result = simulate(0.03, 0.0315)
    ...
    result = simulate(0.03, 0.033)
    ...
    result = simulate(0.03, 0.045)
```

- 停止时 `n_a`、`n_b` 是"停止那一刻"的样本数；未停止时是跑满 `max_n` 后的样本数。
- 三次模拟都用默认种子 7，**每个设定只跑一次**——单次结果只是一条样本路径，不能代表功效或平均停止时间；需要多种子重复才能得到"停止概率"和"平均样本量"。
- `0.0315`、`0.033`、`0.045` 分别对应 5%、10%、50% 的相对提升。
- ⚠️ docstring 写着 "Illustrates CUPED-style variance reduction"，但文件中没有任何 CUPED 代码；讲义练习 5 涉及 CUPED，需要自己实现（见测验 Q10）。
- 也没有 SRM 检查、多重比较校正——讲义中的这些概念都只在文字里出现。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 二元结果 + 双比例 z 检验 | 最常见、最易懂 | LLM 实验常用连续或比值指标（每请求成本、对话长度），需要 t 检验 / delta method |
| 写死 1.96 / 0.84 | 简单 | `alpha`、`power` 参数失效；应使用 `NormalDist().inv_cdf` |
| ×1.4 非确定性缓冲 | 对应讲义 1.3–1.5 倍的经验值 | 经验系数；更严谨的做法是用历史数据估计组内相关或方差膨胀因子 |
| 每个样本都检查一次 | 演示 always-valid 的极端情况 | 生产中按批或按时间检查即可；边界需有理论保证 |
| 启发式 `√(2 ln(1/α) + ln n)` 边界 | 形式简单，随 n 增长 | 未经推导、非常保守；生产用 mSPRT / confidence sequences 的标准实现（GrowthBook、Statsig 已内置） |
| 每个设定只模拟一次 | 运行快 | 无法给出功效与停止时间的分布；应多种子重复 |
| 独立伯努利分流 | 简单 | 不会出现 SRM，掩盖了讲义强调的分流 bug 问题 |
| 不实现 CUPED / SRM / 多重比较 | 代码短 | 讲义的三个核心概念没有代码对应，需要读者补齐 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 条件表达式防除零 | `success_a / n_a if n_a else 0` | `n_a` 为 0 时布尔值为假，走 `else` 分支 |
| `and` 组合条件 | `if n_a and n_b else 1` | 两者都非 0 才计算 |
| 链式赋值 | `success_a = success_b = 0` | 两个名字绑定同一个值；对不可变的整数安全，对列表则会共享同一对象 |
| 数字下划线 | `300_000` | 等于 300000 |
| `math` 模块 | `math.sqrt`、`math.log` | `math.log` 默认是自然对数 |
| 幂运算 `**` | `(...) ** 2` | 平方 |
| 跨行表达式 | `num = (z_alpha * ... +\n z_beta * ...) ** 2` | 括号内可以自由换行，不需要反斜杠 |
| `None` 作哨兵值 | `sequential_stopped_at = None`、`is None` | 表示"还没有停止"；判断用 `is None` 而不是 `== None` |
| `break` | 越过边界后跳出 `for` 循环 | 循环提前结束 |
| 布尔值作分组 | `group = rng.random() < 0.5` | 比较表达式本身就是 `True` / `False` |
| f-string 格式符 | `{baseline*100:.0f}%`、`{result['p_a_observed']*100:.3f}%` | 花括号内可做乘法；`.0f` 不保留小数，`.3f` 保留 3 位 |
| 打印 `None` | `sequential stop at n={result['sequential_stop_at']}` | f-string 会把 `None` 显示为 `None` |
| 类型注解与默认参数 | `def simulate(p_a: float, p_b: float, seed: int = 7, max_n: int = 300_000) -> dict:` | 注解只是提示；默认参数可省略 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.25 秒，结果可复现）：

```text
Baseline 3%, lift +2%:
  fixed sample size (traditional, 80% power, α=0.05): 1279744
  LLM-adjusted (×1.4 for non-determinism): 1791641

Baseline 3%, lift +5%:
  fixed sample size (traditional, 80% power, α=0.05): 207702
  LLM-adjusted (×1.4 for non-determinism): 290782

Baseline 3%, lift +10%:
  fixed sample size (traditional, 80% power, α=0.05): 53150
  LLM-adjusted (×1.4 for non-determinism): 74410

Simulation — actual lift 5% (p_a=0.03, p_b=0.0315):
  final n: A=150026, B=149974
  observed: p_a=2.941%, p_b=3.100%
  sequential stop at n=None

Simulation — actual lift 10% (p_a=0.03, p_b=0.033):
  final n: A=79762, B=79969
  observed: p_a=2.950%, p_b=3.320%
  sequential stop at n=159731

Simulation — actual lift 50% (p_a=0.03, p_b=0.045) — strong signal:
  final n: A=1357, B=1417
  observed: p_a=2.284%, p_b=4.940%
  sequential stop at n=2774
```

逐项解读：

- **样本量（每组）**：讲义练习 1 的答案是每组 207,702，加缓冲后 290,782，两组合计约 58 万用户。用精确分位数并向上取整为 207,938。
- **5% 提升没有停止**：跑满 300,000 个样本（每组约 15 万，低于固定检验所需的每组 207,702）。观测差异方向正确（2.941% vs 3.100%），但此时边界约为 4.31，越不过去——这不是"没有效果"，而是"功效不足"。
- **10% 提升在 n = 159,731 停止**：此时阈值约 4.24。固定检验每组只需 53,150（合计 106,300），这次序贯检验反而用了更多样本——边界保守的代价。
- **50% 提升在 n = 2,774 停止**：阈值约 3.73。观测提升 `4.940 / 2.284 − 1 ≈ 116%`，远大于真实的 50%，且 A 组观测值 2.284% 明显低于真实 3%：这是提前停止导致的**效应高估**（赢家诅咒），报告效应大小时要注意。
- **分流**：最终 `A=150026, B=149974`，卡方 SRM 检验 χ² ≈ 0.009、p ≈ 0.92，正常（独立伯努利分流本就不会出现 SRM）。
- **边界的第一类错误**（我们额外做的 A/A 验证）：用 numpy 跑 300 次 A/A（p = 3%、每次 60,000 样本、与代码相同的"每组 > 100 后每步检查"规则）：
  - 代码的序贯边界：约 **0.3%** 的模拟误报；
  - 每步都用 1.96：约 **51%**——这就是"偷看"的危害；
  - 只在最后看一次 1.96：**5%**，与名义值一致。
  说明代码边界确实控制住了第一类错误，但比 5% 保守得多。

---

## 7. 动手改一改

1. **修复参数**：用 `statistics.NormalDist().inv_cdf` 让 `alpha`、`power` 真正生效，并用 `math.ceil` 向上取整；打印时注明 "per arm"。比较 power = 0.8 与 0.9 的样本量。
2. **A/A 验证**：写一个循环，用 200 个种子运行 `simulate(0.03, 0.03, seed=s, max_n=50_000)`，统计停止比例（第一类错误）；再把阈值换成 1.96 重跑，观察偷看问题。
3. **功效与停止时间分布**：对 `p_b = 0.033` 用 100 个种子运行，统计停止比例与停止时样本数的中位数，与固定检验的 106,300 对比。
4. **实现 CUPED**：为每个用户生成实验前指标 `x`（与转化倾向相关），实现 `cuped_adjust`（见测验 Q10），比较调整前后均值差的标准误，验证方差缩减约为 `1 − ρ²`。
5. **SRM 检查**：在 `simulate` 返回前调用 `srm_check(n_a, n_b)`（见测验 Q12）；再故意把分流改成 `rng.random() < 0.47`，确认检查能报警。
6. **多重比较**：同时模拟 20 个无效实验，比较不校正、Bonferroni（α/20）与 Benjamini-Hochberg 下的"显著"数量。

---

## 8. 常见坑

- **把每组样本量当成总样本量**：代码的 `fixed_sample_size` 是每组，而 `simulate` 的 `max_n` 是总量；混用会导致实验功效不足。
- **参数不生效**：函数签名里有 `alpha`、`power`，但写死了分位数——读代码时要确认参数真的被用到了。
- **偷看固定样本检验**：每天看一次、显著就停，假阳性率会远超 5%；要么用序贯方法，要么预先确定样本量只看一次。
- **用一次模拟下结论**：单条随机路径不能代表功效；统计性质要靠多次重复估计。
- **报告提前停止时的点估计**：序贯检验早停时效应被高估，应报告置信区间或校正后的估计。
- **相信 docstring**：本文件 docstring 提到的 CUPED 并不存在；讲义提到的 SRM、多重比较也没有实现。
- **忽视 LLM 非确定性**：同样的提示词输出不同，实际方差比 IID 假设更大；×1.3–1.5 是经验缓冲，不是精确修正。
