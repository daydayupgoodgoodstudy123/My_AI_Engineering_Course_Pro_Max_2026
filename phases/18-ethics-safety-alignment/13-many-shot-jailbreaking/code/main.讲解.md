# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 13 节 大量样例越狱 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`），无需模型、无需网络

---

## 1. 这份代码在考察什么

这是一个**不训练任何模型**的玩具模拟器：它直接写出"攻击成功率（ASR）随 shot 数变化"的公式，然后用蒙特卡洛采样把曲线"测"出来，再拟合幂律指数，最后对比一个简单防御。对应讲义的核心概念：

1. **幂律 ASR**：讲义称 MSJ 的 ASR 随 shot 数呈 power law，"Power law — not logistic"。代码用 `a0 + c·n^α` 模拟这条曲线。
2. **从观测数据拟合幂律**：讲义练习 1 要求"Fit a power law to the shot-vs-ASR curve. Report the exponent"，代码用 log-log 线性回归实现。
3. **防御会"压平"曲线**：代码把有效 shot 数截断在 16，展示防御后 ASR 不再随 shot 数增长。
4. **评估的统计本质**：每个 shot 数做 500 次伯努利试验，输出的是带噪声的频率，而不是精确概率。

需要先说清楚：代码里**没有**讲义"Use It"一节描述的关键词过滤器，也没有任何真实或伪造的对话内容；"MSJ"只体现为一个整数 `n_shots`。

> 一句话：**用一个公式 + 一次回归，让你亲手看到"shot 越多越危险"的幂律形状，以及截断式防御如何把曲线压平。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `random.seed(41)` | 模块级语句 | 固定随机种子，保证输出可复现 | 可复现评估 |
| `target_asr(n_shots, alpha, a0)` | 函数 | 返回期望 ASR：`min(1, a0 + 0.03·n^α)` | 幂律 ASR 曲线 |
| `defense_adjusted(n_shots, alpha)` | 函数 | 有效 shot 数截断为 16 后再查 `target_asr` | 分类器 / 截断防御 |
| `simulate(n_shots, asr_fn, trials)` | 函数 | 做 `trials` 次伯努利试验，返回命中频率 | 用试验估计 ASR |
| `fit_power_law(shots, asrs)` | 函数 | 在 log-log 空间做最小二乘，返回 `(α, c)` | 幂律拟合 |
| `main()` | 函数 | 依次跑无防御曲线、拟合、有防御曲线，打印结论 | 实验流程 |

数据流：`shots = [1, 2, 4, …, 512]` → 对每个 shot 数 `simulate(s, target_asr)` → 频率列表 → `fit_power_law` → 打印拟合式；再对每个 shot 数 `simulate(s, defense_adjusted)` → 打印防御后曲线。

---

## 3. 逐段精讲

### 3.1 期望 ASR：`target_asr`

```python
def target_asr(n_shots: int, alpha: float = 0.5, a0: float = 0.02) -> float:
    if n_shots <= 0:
        return 0.0
    c = 0.03
    return min(1.0, a0 + c * (n_shots ** alpha))
```

- 公式：`ASR(n) = min(1, a0 + c·n^α)`，默认 `a0 = 0.02`、`c = 0.03`、`α = 0.5`（即 `√n`）。
- 已用 Python 计算的期望值：

| shots | 1 | 2 | 4 | 8 | 16 | 32 | 64 | 128 | 256 | 512 |
|-------|---|---|---|---|----|----|----|-----|-----|-----|
| 期望 ASR | 0.050 | 0.062 | 0.080 | 0.105 | 0.140 | 0.190 | 0.260 | 0.359 | 0.500 | 0.699 |

- 这**不是纯幂律**：多了常数项 `a0`，取对数后 `log(a0 + c·n^α)` 不是 `log n` 的线性函数。这会让后面的拟合指数偏小（见 3.4）。
- `min(1.0, …)` 保证概率不超过 1。按公式，ASR 在 `n = ((1−0.02)/0.03)² ≈ 1067` 时才到 1；默认 shot 列表最多 512，因此截断从未触发。
- ⚠️ docstring 写 "saturates around 256"，但 256 处只有 0.50，与代码不符；它还说"fails reliably at 5 shots"，但 `target_asr(5) ≈ 0.087`。
- ⚠️ `n_shots <= 0` 时返回 0.0，而 1 shot 时是 0.05：`a0` 本意是基线，却在 0 处被丢掉，形成不连续。
- 讲义说"指数取决于行为类别和模型"，代码只用一个全局 `alpha`，没有区分类别。

### 3.2 截断式防御：`defense_adjusted`

```python
def defense_adjusted(n_shots: int, alpha: float = 0.5) -> float:
    eff = min(n_shots, 16)
    return target_asr(eff, alpha)
```

- docstring 说"classifier detects the many-shot pattern and caps effective shot count at 16"，但代码**没有任何检测**：对所有输入无条件截断。这相当于假设分类器召回率 100%，而且它不区分有害示例和良性示例。
- 结果：n ≥ 16 时期望 ASR 恒为 `0.02 + 0.03×4 = 0.14`。512 shot 从 0.70 降到 0.14，下降约 80%，但离讲义里 Anthropic 防御的"61% → 2%"差得很远——两者不是同一件事。
- 讲义强调的两难（防御会伤害良性 ICL）在这里完全没被建模：如果用同样的截断处理良性 few-shot 示例，它们的效果也会被压在 16 shot 水平（测验 Q11 给出了对比实现和数据）。
- 小细节：`defense_adjusted` 透传了 `alpha` 但没有透传 `a0`，若想改基线需要同时改两处。

### 3.3 蒙特卡洛估计：`simulate`

```python
def simulate(n_shots: int, asr_fn, trials: int = 500) -> float:
    p = asr_fn(n_shots)
    hits = sum(1 for _ in range(trials) if random.random() < p)
    return hits / trials
```

- `asr_fn` 是**函数作为参数**传入的（`target_asr` 或 `defense_adjusted`），同一个 `simulate` 可以测两条曲线。
- `random.random() < p` 以概率 p 返回 True，相当于一次"攻击是否成功"的伯努利试验；500 次取频率。
- 噪声量级：标准差 `√(p(1−p)/500)`，p = 0.14 时约 0.0155，p = 0.5 时约 0.022。所以输出中 256 shot 得到 0.538（期望 0.50）、防御后 256 shot 得到 0.108（期望 0.14）都在 2~2.5 个标准差内，属正常波动。
- `sum(1 for … if …)` 是生成器表达式计数，等价于手写循环累加。
- 两条曲线共享同一个全局随机数流：如果调换两段实验的顺序，具体数字会变。

### 3.4 幂律拟合：`fit_power_law`

```python
def fit_power_law(shots: list[int], asrs: list[float]) -> tuple[float, float]:
    xs = [math.log(s) for s in shots if s > 0]
    ys = [math.log(max(a, 1e-4)) for a in asrs]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(xs, ys))
    den = sum((xi - mx) ** 2 for xi in xs)
    alpha = num / den
    logc = my - alpha * mx
    return alpha, math.exp(logc)
```

- 原理：若 `ASR = c·n^α`，则 `log ASR = log c + α·log n`，在 log-log 空间就是一条直线；用普通最小二乘求斜率 `α = Cov(x, y) / Var(x)`，截距 `log c = ȳ − α·x̄`。
- `max(a, 1e-4)` 防止 `log(0)`。但它会把 0 次成功变成 −9.2 的极端点，严重拉偏回归。
- ⚠️ **潜在 bug**：`xs` 过滤了 `s > 0`，`ys` 却没有同步过滤。只要 `shots` 里出现 0，两个列表就会错位，`zip` 静默截断，`my` 也会用错误的元素个数。已实际验证：`shots=[0,1,2,4]`、`asrs=[0,0.05,0.06,0.08]` 时拟合出 `α ≈ 4.61`，正确值应为 `α ≈ 0.339`。默认 shot 列表不含 0，所以本次运行没触发。修复方法见测验 Q9。
- **指数偏小的来源**（已用 Python 验证）：
  - 对无噪声期望值拟合：`α ≈ 0.427`，`c ≈ 0.045`——偏差来自 `a0`；
  - 先减去 `a0` 再拟合：精确得到 `α = 0.500`，`c = 0.030`；
  - 本次运行（seed 41）：`α ≈ 0.461`，`c ≈ 0.038`——在 `a0` 偏差上又叠加了采样噪声；
  - 换 20 个种子：`α` 在 0.381 ~ 0.490 之间波动。
- 结论：讲义练习 1 "Report the exponent" 时，要说明拟合的模型形式和不确定性。

### 3.5 `main()`：实验流程与结论

```python
    shots = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
    ...
    for s in shots:
        rate = simulate(s, target_asr)
        undef.append(rate)
        print(f"  shots={s:4d}   ASR={rate:.3f}")
    alpha, c = fit_power_law(shots, undef)
```

- shot 数按 2 的幂取点，在 log 轴上等间距，正适合 log-log 回归。
- 最后的 TAKEAWAY 写"classifier-based prompt modification (Anthropic 2024) reports 61%->2% reduction without breaking ICL"。讲义原文只说"reported reduction: 61% -> 2% attack success on tested settings"，并没有说"without breaking ICL"；而且本代码根本没有测量 ICL，这半句是代码自己加的结论，应谨慎看待。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 直接写出 ASR 公式，不用模型 | 无需 GPU 和有害数据，几毫秒跑完 | 结论完全由公式决定，不能用来证明"MSJ 呈幂律"；真实评估要对真实模型、真实数据集跑 |
| `a0 + c·n^α` 而非纯幂律 | 给 1 shot 一个非零基线 | 拟合纯幂律时指数被系统性低估（0.427 vs 0.5） |
| 每点 500 次伯努利试验 | 展示"ASR 是估计值、有噪声" | 指数估计波动约 ±0.05；生产评估需要置信区间 |
| log-log OLS 拟合 | 实现简单、直观 | 对 0 值和极端点敏感；更稳妥的是二项似然 + 非线性拟合 |
| 防御 = 无条件截断到 16 shot | 一行代码展示"曲线被压平" | 不区分有害/良性，会同样伤害 ICL；真实做法是上下文分类器 + 截断/改写，并同时报告 ICL 表现 |
| 单一全局 `alpha` | 简化 | 讲义说指数随类别和模型变化；生产中要分类别拟合 |
| 全局 `random.seed(41)` | 可复现 | 两段实验共享随机流，顺序改变数字就变 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 让类型注解延迟求值；在旧版本 Python 中也能写 `list[int]` 这类注解 |
| 类型注解 | `def target_asr(n_shots: int, alpha: float = 0.5, a0: float = 0.02) -> float:` | 标注参数与返回值类型，只作文档用途，运行时不检查 |
| 泛型注解 | `list[int]`、`tuple[float, float]` | 列表元素类型、二元组类型 |
| 默认参数 | `trials: int = 500` | 调用时可省略 |
| 函数作为参数 | `simulate(s, target_asr)`、`asr_fn(n_shots)` | 函数是一等对象，可以像变量一样传递 |
| 生成器表达式计数 | `sum(1 for _ in range(trials) if random.random() < p)` | 不建列表，边产生边求和；`_` 表示不使用的循环变量 |
| 带条件的列表推导式 | `[math.log(s) for s in shots if s > 0]` | 过滤 + 变换一步完成 |
| `zip` | `zip(xs, ys)` | 成对遍历；长度不同时**静默按短的截断**（本文件 bug 的根源） |
| 幂运算 | `n_shots ** alpha` | 浮点指数，`** 0.5` 即平方根 |
| `min` / `max` 截断 | `min(1.0, …)`、`max(a, 1e-4)` | 把值夹在合法范围内 |
| 多返回值 | `return alpha, math.exp(logc)` / `alpha, c = fit_power_law(...)` | 实际返回元组，再解包 |
| f-string 格式符 | `{s:4d}`、`{rate:.3f}`、`{alpha:.3f}` | 宽度 4 的整数；保留 3 位小数 |
| 字符串乘法 | `"=" * 70` | 打印分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()`，被 import 时不执行（测验 Q11 就是 import 了 `target_asr`） |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，Python 3，耗时不到 1 秒）：

```text
-- undefended target (power-law ASR curve) --
  shots=   1   ASR=0.046      ← 期望 0.050
  shots=   2   ASR=0.046      ← 期望 0.062（噪声使 1、2 shot 相等）
  shots=   4   ASR=0.068      ← 期望 0.080
  shots=   8   ASR=0.100      ← 期望 0.105
  shots=  16   ASR=0.142      ← 期望 0.140
  shots=  32   ASR=0.184      ← 期望 0.190
  shots=  64   ASR=0.264      ← 期望 0.260
  shots= 128   ASR=0.346      ← 期望 0.359
  shots= 256   ASR=0.538      ← 期望 0.500
  shots= 512   ASR=0.678      ← 期望 0.699

  fitted power law: ASR ~= 0.038 * n^0.461     ← 真实 c=0.03、α=0.5

-- classifier-defended target (caps effective shots at 16) --
  shots=   1   ASR=0.052
  shots=   2   ASR=0.054
  shots=   4   ASR=0.070
  shots=   8   ASR=0.110
  shots=  16   ASR=0.144
  shots=  32   ASR=0.120      ← 从这里起期望值恒为 0.140
  shots=  64   ASR=0.138
  shots= 128   ASR=0.134
  shots= 256   ASR=0.108
  shots= 512   ASR=0.146
```

逐项解读：

- **无防御曲线**单调上升（除 1、2 shot 的噪声），512 shot 时约 0.68。每翻一倍 shot，ASR 大约乘以 `2^0.5 ≈ 1.41`（扣除 `a0` 后）。
- **拟合指数 0.461**：低于真实值 0.5。原因一是 `a0` 使模型不是纯幂律（无噪声时也只能拟合到 0.427），原因二是采样噪声（本次恰好把斜率往上推了一点）。
- **防御后曲线**：16 shot 以后在 0.11~0.15 之间随机波动，围绕期望 0.14，不再随 shot 数增长——这就是"截断有效 shot 数"的效果。但 0.14 并不低，远没有到讲义所说 Anthropic 防御的 2%。
- **TAKEAWAY 段落**：前半句（曲线被压平）是代码真实展示的；后半句"without breaking ICL"是代码没有测量过的结论（见 3.5）。

---

## 7. 动手改一改

1. （讲义练习 1）把 `trials` 从 500 改为 20000，再拟合一次，观察指数是否稳定在 0.427 附近；然后在拟合前减去 `a0`，验证能还原 0.5。
2. 修复 `fit_power_law` 的错位 bug（成对过滤 `s > 0 and a > 0`），并把 `shots` 改为从 0 开始，确认结果合理。
3. 给 `target_asr` 加一个 `category` 参数，例如暴力/欺骗类 `alpha = 0.6`、其他类 `alpha = 0.4`，分别画曲线并拟合，体会讲义"指数取决于行为类别"。
4. （讲义练习 2）实现真正的分类器防御：上下文表示为 `(user, assistant)` 对的列表，分类器只删除"有害顺从对"，并引入召回率参数 `recall`（例如 0.9），漏检的有害对仍计入 shot 数；同时测量良性 ICL 曲线（测验 Q11 给出了起步代码）。
5. 把 `simulate` 的返回值换成 `(rate, ci_low, ci_high)`（例如 Wilson 区间），并用 bootstrap 给拟合指数加上置信区间。
6. 进阶：把 `a0 + c·n^α` 换成 logistic 曲线 `1 / (1 + exp(−k(log n − m)))`，在 log-log 图上对比两种曲线形状，理解讲义"power law, not logistic"的区别，并讨论有限范围的数据能否区分二者。

---

## 8. 常见坑

- **把玩具结论当成实证结论**：这里的幂律是写进公式的，不是"发现"的。真实的幂律要在真实模型和真实数据上测出来。
- **用单一 shot 数报告 ASR**：MSJ 是一条曲线，只测 5 shot 得到 0% 毫无意义（skill 文件把它列为硬拒绝项）。
- **忽略常数项直接拟合纯幂律**：会系统性低估指数。
- **`zip` 静默截断**：两个列表长度不一致时不报错，只会给出错误结果。成对过滤或在 Python 3.10+ 用 `zip(..., strict=True)`。
- **`log(0)` 的处理**：用一个很小的常数替代 0 会制造极端点；最好去掉或平滑。
- **防御只看 ASR、不看 ICL**：截断防御看起来有效，但同样会截断良性 few-shot 示例。
- **采样噪声当信号**：500 次试验下单点波动 ±0.02~0.03，比较曲线时要看置信区间。
