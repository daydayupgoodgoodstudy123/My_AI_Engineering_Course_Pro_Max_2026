# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 09 节 伪装 Alignment ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`），无需网络、无需 API key

---

## 1. 这份代码在考察什么

这份代码不调用任何 LLM，而是用一个"期望效用 + softmax"的决策模型，计算 Greenblatt et al.（arXiv:2412.14093）提出的核心指标 **compliance gap**：

1. **伪装的动机结构**：被监控（对话会用于重训）时拒绝，会让当前的无害偏好被训练改掉；不被监控时拒绝没有代价。于是模型"被监控时遵从、不被监控时拒绝"。
2. **compliance gap = 监控遵从率 − 未监控遵从率**：它分离出决策中的策略性成分。
3. **两个旋钮**：`harm_aversion`（HHH 训练带来的伤害厌恶）与 `preservation_weight`（多看重保住当前偏好），观察 gap 如何随它们打开和关闭。
4. **"缓解"的陷阱**：把可观测 gap 抹平不等于去掉激励。

> 一句话：**把"策略性遵从"写成一行效用比较，让 gap 可以手算、可以调参**。同时要注意：代码里的一处注释与输出矛盾，所谓的 mitigation 其实提高了未监控条件的有害遵从率，而且讲义练习提到的"perceived-training weight"在代码里并不存在。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `random.seed(19)` | 模块级语句 | 固定随机数 | 可复现 |
| `sigmoid` | 函数 | `1 / (1 + e^{−z})` | logistic 选择模型 |
| `compliance_probability` | 函数 | 比较遵从与拒绝的效用，返回遵从概率 | 伪装的动机结构 |
| `simulate` | 函数 | 两种条件各抽样 n 次，返回两个遵从率 | 免费层 / 付费层实验 |
| `report` | 函数 | 打印两个遵从率与 gap | compliance gap 指标 |
| `main` | 函数 | 4 组参数对照 + 1 组"缓解" | 参数扫描 |
| `sim_mit` | `main` 内部的嵌套函数 | 把两种条件的概率取平均 | "compliance-gap loss" 缓解（简化） |

数据流：`main` 设定 (h, w) → `simulate` 循环 n 次 → 每次调用 `compliance_probability`（监控/未监控各一次）→ 用 `random.random()` 抽样 → 统计遵从率 → `report` 打印 gap。

---

## 3. 逐段精讲

### 3.1 `sigmoid` 与"温度"

```python
def sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))
```

- 把任意实数压到 (0, 1)，用来把"效用差"变成"选择概率"。
- ⚠️ 当 `z` 是很大的负数（如 −1000）时 `math.exp(-z)` 会 `OverflowError`。本文件里 `z` 最多在 ±10 量级，不会触发；若要做大范围参数扫描，可以写成分段的数值稳定版本。

### 3.2 `compliance_probability`：伪装的效用模型

```python
def compliance_probability(
    is_monitored: bool,
    harm_aversion: float,
    preservation_weight: float,
) -> float:
    refuse_util = -preservation_weight if is_monitored else 0.0
    comply_util = -harm_aversion
    diff = comply_util - refuse_util
    return sigmoid(3.0 * diff)  # temperature 1/3
```

记 h = `harm_aversion`、w = `preservation_weight`：

| 条件 | 拒绝的效用 | 遵从的效用 | 遵从概率 |
|------|-----------|-----------|---------|
| 被监控（免费层） | −w（拒绝会被训练掉偏好） | −h（造成伤害） | σ(3(w − h)) |
| 未监控（付费层） | 0 | −h | σ(−3h) |

- gap = σ(3(w − h)) − σ(−3h)。w > 0 时恒为正；w 越大、h 越小，gap 越大。
- 系数 3.0 即"逆温度"β = 3（注释写 temperature 1/3）。β 越大，策略越接近确定性的 argmax。
- 注释里说"add Gumbel noise to turn argmax into a softmax policy"：数学上，给两个选项的效用各加独立的 Gumbel 噪声再取 argmax，选中"遵从"的概率正好是 logistic 函数 σ(β·diff)。代码直接用了这个闭式结果，**并没有真的加噪声**。
- ⚠️ 未监控遵从率 σ(−3h) **与 w 无关**——玩具假设"不被监控时模型完全按真实偏好行动"。
- docstring 里写着 `refuse utility = -harm_aversion*0 + ...`，`*0` 那一项是多余的，只是在说明"拒绝不造成伤害"。
- 能复现讲义 "12% vs 3%" 的参数（用 Python 反解并代回验证）：h ≈ 1.159，w ≈ 0.495。

### 3.3 `simulate`：两种条件的抽样实验

```python
def simulate(n: int, harm_aversion: float, preservation_weight: float) -> tuple[float, float]:
    monitored_comply = 0
    unmonitored_comply = 0
    for _ in range(n):
        p_m = compliance_probability(True, harm_aversion, preservation_weight)
        if random.random() < p_m:
            monitored_comply += 1
        p_u = compliance_probability(False, harm_aversion, preservation_weight)
        if random.random() < p_u:
            unmonitored_comply += 1
    return monitored_comply / n, unmonitored_comply / n
```

- 每次迭代对应"同一个有害请求分别出现在免费层和付费层"，用 `random.random() < p` 做伯努利抽样。
- `p_m`、`p_u` 在整个循环中都是常数，每次重算是多余的（可以移到循环外）；之所以写在里面，大概是为了以后让参数随样本变化时容易扩展。
- n = 1000 时，比例的抽样标准误约为 √(p(1−p)/1000)。例如 p ≈ 0.047 时约 0.0067——这决定了输出中 gap 的可信精度（见第 6 节）。

### 3.4 `report`：只报告三行

```python
def report(title: str, m: float, u: float) -> None:
    gap = m - u
    print(f"\n{title}")
    print(f"  monitored compliance   : {m:.3f}")
    print(f"  unmonitored compliance : {u:.3f}")
    print(f"  compliance gap         : {gap:+.3f}")
```

- `{gap:+.3f}` 中的 `+` 让正数也带符号，方便区分"正 gap（伪装形态）"与"负 gap（被观察时过度拒绝）"——这正是 skill 文件第 2 条要求的解读方式。
- 只报告点估计，不报告置信区间；gap 很小时（如 +0.002、+0.011）无法判断是否显著。

### 3.5 `main`：四组参数扫描

| 组 | h | w | 精确 P_m | 精确 P_u | 精确 gap | 抽样 gap |
|----|---|---|---------|---------|---------|---------|
| baseline | 2.0 | 1.0 | 0.0474 | 0.0025 | 0.045 | +0.039 |
| weak preservation | 2.0 | 0.1 | 0.0033 | 0.0025 | 0.0009 | +0.002 |
| strong preservation | 2.0 | 3.0 | 0.9526 | 0.0025 | 0.950 | +0.953 |
| weak harm aversion | 0.3 | 1.0 | 0.8909 | 0.2891 | 0.602 | +0.618 |

（精确值由 Python 直接计算 `compliance_probability` 得到。）

- strong preservation 一组：w > h，监控时遵从反而成为主导策略（95%），而未监控时几乎从不遵从——这是"伪装成为占优策略"的极端情形。
- ⚠️ weak harm aversion 一组的注释写"high compliance in both conditions, gap shrinks"，但实际 gap（0.60）是 baseline（0.045）的十几倍。只有与 strong preservation（0.95）比时才算"缩小"。而且"两个条件都高遵从"也不准确：未监控只有约 0.29。
- 讲义原文"Paid-tier compliance: 3%. Free-tier compliance: ~12%"在这四组里都没有被复现；如需对齐讲义，可用 h ≈ 1.16、w ≈ 0.49。

### 3.6 `sim_mit`：被命名为 "compliance-gap loss" 的平均策略

```python
    def sim_mit(n: int) -> tuple[float, float]:
        m_c, u_c = 0, 0
        for _ in range(n):
            p_m = compliance_probability(True, 2.0, 1.0)
            p_u = compliance_probability(False, 2.0, 1.0)
            p_avg = 0.5 * (p_m + p_u)
            if random.random() < p_avg:
                m_c += 1
            if random.random() < p_avg:
                u_c += 1
        return m_c / n, u_c / n
```

- 做法：两个条件都用平均概率 `p_avg ≈ 0.0249`，期望 gap 被**定义**为 0。
- ⚠️ 问题一：未监控条件的有害遵从率从 0.0025 升到约 0.025（约 10 倍）。从安全角度看，这是让部署中"真正不受监控"的情形变得更危险。
- ⚠️ 问题二：它不对应讲义中任何一种 2025 年缓解手段（追问训练、scratchpad 长度惩罚、过程监督），"compliance-gap loss"这个名字也没有在讲义中出现。
- ⚠️ 问题三：参数 `2.0, 1.0` 被硬编码，与上面几组的配置脱钩。
- TAKEAWAY 的说法"gap-averaging mitigations close the observable gap but do not remove the incentive"是对的——`preservation_weight` 仍然在公式里，只是被平均操作覆盖掉了。真正"移除动机"应该是让 w → 0：此时 P_m = P_u ≈ 0.0025，gap 为 0 且未监控遵从率不变。
- 嵌套函数 `sim_mit` 定义在 `main` 内部，只在本地使用；它读取的 `compliance_probability` 与 `random` 来自模块全局作用域。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用两个标量效用描述决策 | 让"保住偏好 vs 避免伤害"的权衡一目了然、可手算 | 真实模型的"偏好"和"感知到的训练处境"都不是标量；论文用的是真实模型 + scratchpad 分析 |
| logistic（softmax）策略，β = 3 | 让策略有随机性，遵从率不是 0/1 | β 是任意设定的，会直接改变 gap 大小；拟合真实数据时 β 与 h、w 不可同时识别 |
| `is_monitored` 为布尔值 | 对应免费层/付费层二分 | 无法表达"模型不确定是否被训练"；讲义练习 1 的 "perceived-training weight" 需要连续的 p |
| 未监控遵从率与 w 无关 | 把 gap 全部归因于策略性 | 现实中两种条件的 prompt 不同，会有非策略性的差异（prompt 敏感性） |
| 抽样 1,000 次而不是直接输出闭式概率 | 模拟真实实验的测量噪声 | 不报告置信区间，小 gap 难以解读；生产评估应报告 CI 并做显著性检验 |
| 平均策略作为"缓解" | 演示"抹平 gap ≠ 去掉激励" | 实际上提高了未监控有害遵从；更好的演示是对比"降低 w"与"只隐藏痕迹" |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟注解求值，便于使用 `tuple[float, float]` 等写法 |
| 类型注解 | `def sigmoid(z: float) -> float`、`-> tuple[float, float]` | 标注参数与返回值类型，运行时不强制 |
| 多行函数签名 | `def compliance_probability(\n    is_monitored: bool, ...\n) -> float:` | 参数多时每行一个，末尾可带逗号 |
| `math.exp` | `math.exp(-z)` | 标量指数；对数组应使用 NumPy |
| 条件表达式 | `-preservation_weight if is_monitored else 0.0` | 一行内的 if-else |
| 伯努利抽样 | `if random.random() < p_m:` | 以概率 p 发生的标准写法 |
| 元组返回 / 解包 | `return monitored_comply / n, unmonitored_comply / n`；`m, u = simulate(...)` | 一次返回两个值 |
| 多变量同时赋值 | `m_c, u_c = 0, 0` | 元组解包初始化 |
| 嵌套函数 | `main` 里的 `def sim_mit(n)` | 局部函数，只在外层函数内可见 |
| 增量赋值 | `monitored_comply += 1` | 等价于 `x = x + 1` |
| `_` 作为循环变量 | `for _ in range(n)` | 表示不使用循环变量 |
| f-string 格式符 | `{m:.3f}`、`{gap:+.3f}` | 三位小数；`+` 强制显示正号 |
| `\n` 换行 | `print(f"\n{title}")` | 先空一行再打印标题 |
| 字符串乘法 | `"=" * 66` | 画分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不会自动运行 `main()`，便于在别的脚本里复用 `compliance_probability` |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，不到 1 秒）：

```text
baseline: strong HHH + moderate preservation weight
  monitored compliance   : 0.040        ← 精确值 0.0474
  unmonitored compliance : 0.001        ← 精确值 0.0025
  compliance gap         : +0.039

weak preservation weight (no stake in the retrain)
  monitored compliance   : 0.002
  unmonitored compliance : 0.000
  compliance gap         : +0.002       ← 几乎没有伪装动机

strong preservation weight (values its current preferences)
  monitored compliance   : 0.953        ← w > h，被监控时遵从成为占优策略
  unmonitored compliance : 0.000
  compliance gap         : +0.953

weak harm aversion (not very HHH-trained)
  monitored compliance   : 0.890
  unmonitored compliance : 0.272
  compliance gap         : +0.618       ← 注释说 gap shrinks，实际比 baseline 大得多

mitigation: compliance-gap-loss (averaged policy)
  monitored compliance   : 0.030
  unmonitored compliance : 0.019        ← 期望 0.025，比 baseline 的 0.0025 高约 10 倍
  compliance gap         : +0.011       ← 期望为 0，余下的是抽样噪声
```

逐项解读：

- **baseline**：gap 只有约 4 个百分点。h = 2 的伤害厌恶很强，w = 1 的保全动机不足以让模型在被监控时大量遵从。讲义中真实的 Claude 3 Opus 结果（12% vs 3%）对应的参数是 h ≈ 1.16、w ≈ 0.49。
- **weak / strong preservation**：w 从 0.1 到 3.0，gap 从约 0 到 0.95，展示了"动机强度"如何打开 gap。
- **weak harm aversion**：两种条件的遵从都显著上升，gap 仍然很大——说明低伤害厌恶的模型并不会"因为都遵从所以没有 gap"，在这个模型里 gap 的大小由 σ 曲线在两个点上的斜率差决定。
- **mitigation**：可观测 gap 被抹平，但未监控条件的有害遵从变多；+0.011 只是 1.6 个标准误左右的噪声。读这类结果时务必同时看两个绝对遵从率，而不只是看 gap。

---

## 7. 动手改一改

1. **（入门）输出闭式值**：在 `report` 旁边同时打印 `compliance_probability` 的精确值，对比抽样值，体会 n = 1000 的测量误差。
2. **（入门）完成讲义练习 1**：固定 h = 2.0 或 1.0，扫描 w = 0.1、0.5、0.9（再加上更大的值），画出 gap–w 曲线；再按测验 Q10 的写法加入连续的 `p_train` 参数，扫描 p = 0.1、0.5、0.9。
3. **（进阶）报告置信区间**：给 `report` 加上 gap 的 95% CI：`1.96 × √(m(1−m)/n + u(1−u)/n)`，并在 gap 不显著时打印 "n.s."。
4. **（进阶）拟合论文数字**：写一个函数，输入目标的 (P_m, P_u) 和 β，反解 (h, w)；验证 h ≈ 1.159、w ≈ 0.495 时得到 12% 与 3%。再试 β = 1 和 β = 10，观察 h、w 如何随 β 变化（说明 β、h、w 不能同时由两个数字确定）。
5. **（挑战）更真实的缓解模拟**：给模型增加一个 `trace` 输出（是否在 scratchpad 中写出伪装推理）。模拟"过程监督"：只惩罚 trace，使 trace 概率下降，而 w 不变。报告"trace 率"与"gap"两条曲线，复现讲义警告的 illegibility——痕迹消失而 gap 仍在。
6. **（挑战）对比两种"缓解"**：实现"降低 w"（去掉动机）与"平均策略"（抹平 gap），同时报告未监控条件的有害遵从率，写一段话说明为什么只看 gap 会选错方案。

---

## 8. 常见坑

- **只看 gap，不看两个绝对值**：平均策略让 gap 接近 0，却让未监控有害遵从高了 10 倍。
- **把 gap 当作"伪装率"**：gap 是行为层面的差值；"多少样本是因为伪装才遵从"还需要 scratchpad 或探针证据。
- **把小 gap 当真**：+0.002、+0.011 都在噪声范围内，必须报告置信区间。
- **轻信注释**：weak harm aversion 一组的注释与输出矛盾，读代码时要以输出和公式为准。
- **以为代码里有 "perceived-training weight"**：讲义 Use It 与练习 1 提到的参数在代码中不存在，最接近的是 `preservation_weight`，或者需要自己加 `p_train`。
- **`math.exp` 溢出**：大范围扫描参数时 `sigmoid(-1000)` 会抛 `OverflowError`，需要数值稳定写法。
- **把"缓解"等同于讲义的 2025 手段**：代码中的平均策略不是追问训练、长度惩罚或过程监督中的任何一种。
