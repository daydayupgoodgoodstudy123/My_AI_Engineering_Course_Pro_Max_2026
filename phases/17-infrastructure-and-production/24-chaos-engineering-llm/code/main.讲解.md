# 代码讲解 · main.py

> **所属小节**：阶段 17 · 基础设施与生产 · 第 24 节 LLM 生产环境中的混沌工程 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`），不会真的注入任何故障

---

## 1. 这份代码在考察什么

这是一个约 70 行的"混沌实验 runner"，模拟讲义中的**安全面（safety plane）**：给定三个 LLM 相关的实验（杀 decode 副本、provider 429、畸形 prompt 卡死 tokenizer），计算每个实验的 burn rate，判断安全门是否会中止它。

它对应讲义的三个概念：

1. **错误预算与 burn rate**：99.9% SLO → 0.1% 错误预算；实验引发的错误率相对"预期"高出多少倍。
2. **爆炸半径（blast radius）**：实验影响的流量/副本比例。
3. **安全门**：高 burn + 大爆炸半径 → ABORTED。

但它有两处与讲义不一致的地方，这是最值得学的部分：

- burn rate 的分母是"预期基线错误率 0.05%"，而不是错误预算 0.1%，算出来的倍数是标准 burn rate 的 2 倍；
- 中止条件是 `burn > 2 **and** blast > 20%`，讲义的门槛只看 burn（"pause experiment if daily error-budget burn exceeds 2x expected"），于是 burn 80 倍的畸形 prompt 实验照样"COMPLETED"。

> 一句话：**用三行实验数据演示"burn rate × 爆炸半径"的安全门**——同时提醒你，门控公式写错一个分母、多写一个 `and`，安全面就形同虚设。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `ERROR_BUDGET_PER_DAY = 0.001` | 常量 | 99.9% SLO 的错误预算；**只被打印，不参与计算** | Error budget |
| `EXPECTED_ERROR_RATE = 0.0005` | 常量 | 平时的基线错误率，被代码当作 burn rate 的分母 | 稳态基线 |
| `Experiment` | dataclass | 名称、时长（分钟）、引发的错误率、爆炸半径 | 实验定义（控制面） |
| `EXPERIMENTS` | 列表 | 三个实验：pod kill、provider 429、malformed prompt | LLM 专属实验 |
| `run_experiment` | 函数 | 计算 burn rate，按"burn > 2 且 blast > 20%"判定是否中止 | 安全面 |
| `main` | 函数 | 打印参数与结果表 | 可观测面（简化） |

数据流：`EXPERIMENTS` 中每个 `Experiment` → `run_experiment` → 结果字典 → 格式化打印。

---

## 3. 逐段精讲

### 3.1 常量：SLO、错误预算与基线

```python
ERROR_BUDGET_PER_DAY = 0.001   # 99.9% SLO
EXPECTED_ERROR_RATE = 0.0005
```

- 99.9% 的 SLO 意味着 0.1% 的请求允许失败，这就是 error budget（`1 − SLO`）。变量名里的 "PER_DAY" 指的是"按天评估的窗口"，它本身是一个比例而不是"每天多少次"。
- `EXPECTED_ERROR_RATE = 0.05%` 表示服务平时只用掉一半预算——这是健康服务的常态。
- ⚠️ `ERROR_BUDGET_PER_DAY` 只在 `main` 里打印，从未参与任何计算。

### 3.2 `Experiment` 与三个实验

```python
@dataclass
class Experiment:
    name: str
    duration_min: int
    induced_error_rate: float
    blast_radius_pct: float


EXPERIMENTS = [
    Experiment("pod kill (1 decode replica)",     5, 0.002, 0.05),
    Experiment("provider 429 fallback",           5, 0.015, 0.30),
    Experiment("malformed prompt tokenizer stall",3, 0.040, 0.10),
]
```

| 实验 | 时长 | 引发错误率 | 爆炸半径 | 对应讲义 |
|------|------|-----------|---------|---------|
| pod kill | 5 分钟 | 0.2% | 5% | "First experiment: pod-kill one decode replica" |
| provider 429 | 5 分钟 | 1.5% | 30% | "inject one provider 429 for 5 minutes" |
| malformed prompt | 3 分钟 | 4.0% | 10% | 五个 LLM 实验之 4：tokenizer bomb |

- 三个数字都是作者设定的假设值，不是测量结果。
- ⚠️ `induced_error_rate` 的口径没有说明：是爆炸半径**内**的错误率，还是全服务的错误率？两种解释算出的 burn rate 相差一个"爆炸半径"倍数（测验 Q10 对两种口径都做了计算）。
- skill 文件要求爆炸半径 "< 30% of fleet"，provider 429 恰好是 30%，严格来说在设计阶段就该被拒绝。

### 3.3 `run_experiment`：安全门

```python
def run_experiment(e: Experiment) -> dict:
    burn_rate = e.induced_error_rate / max(EXPECTED_ERROR_RATE, 0.0001)
    paused = burn_rate > 2.0 and e.blast_radius_pct > 0.2
    return {
        "experiment": e.name,
        "duration": e.duration_min,
        "error_rate": e.induced_error_rate,
        "burn_rate_x": burn_rate,
        "blast_radius": e.blast_radius_pct,
        "paused_by_safety_plane": paused,
        "status": "ABORTED (burn-rate guard)" if paused else "COMPLETED",
    }
```

- `max(EXPECTED_ERROR_RATE, 0.0001)`：防御性写法，防止基线被配置成 0 时除以零（下限 0.01%）。
- **burn rate 的计算**：

| 实验 | 代码 burn（÷0.0005） | 标准 burn（÷0.001） | 按爆炸半径折算后标准 burn |
|------|--------------------|-------------------|------------------------|
| pod kill | 4.0x | 2.0x | 0.1x |
| provider 429 | 30.0x | 15.0x | 4.5x |
| malformed prompt | 80.0x | 40.0x | 4.0x |

- ⚠️ **分母问题**：SRE 中 burn rate 的标准定义是 `实际错误率 / (1 − SLO)`，即除以错误预算。代码除以"预期基线"，得到的是"比平时糟糕多少倍"的异常倍数。讲义说的是"error-budget burn exceeds 2x expected"，"expected"可以理解为"预期的预算消耗速度"（即 burn = 1），按此理解分母应是错误预算。
- ⚠️ **`and` 问题**：`paused = burn_rate > 2.0 and e.blast_radius_pct > 0.2`。讲义的 burn-rate 门不附加爆炸半径条件；爆炸半径应作为**另一道独立的门**（skill："blast-radius (< 30% of fleet)"），二者是"或"的关系——任何一个越界都应停止。
- ⚠️ **没有时间维度**：`duration_min` 只用于展示。真实安全面在实验**进行中**持续评估滑动窗口内的 burn，一旦超限立刻中止并撤销注入；本代码是事后给出"会不会被中止"的结论。

### 3.4 `main`：打印结果表

```python
    print(f"SLO error budget: {ERROR_BUDGET_PER_DAY*100:.2f}%/day")
    print(f"Expected baseline error rate: {EXPECTED_ERROR_RATE*100:.3f}%")
    print(f"Burn-rate gate: > 2.0x expected AND blast radius > 20%\n")

    header = f"{'Experiment':38}  {'mins':>4}  {'err %':>6}  {'burn×':>6}  {'blast':>6}  Status"
    ...
        print(f"{r['experiment']:38}  {r['duration']:>4}  "
              f"{r['error_rate']*100:>5.2f}%  "
              f"{r['burn_rate_x']:>5.1f}x  "
              f"{r['blast_radius']*100:>5.0f}%  "
              f"{r['status']}")
```

- 比例乘以 100 后用 `%` 显示：`0.015 * 100` → `1.50%`。
- 相邻的 f-string 字面量会被自动拼接成一个字符串（隐式字符串拼接），所以一个 `print` 可以跨多行书写。
- 第三行的 `f"Burn-rate gate: ..."` 里没有任何占位符，`f` 前缀是多余的（无害）。
- 结尾的提示 "small-blast-radius experiments run to completion even at high burn rate" 把代码的行为当作设计意图陈述了出来——这正是与讲义冲突的地方：按讲义，高 burn 就应暂停，与爆炸半径无关。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 实验参数写死 | 无需真实集群即可演示安全门 | 真实错误率要在实验中测量；用 LitmusChaos / Chaos Mesh / AWS FIS 注入 |
| burn 以基线为分母 | 直观表达"比平时糟多少倍" | 与标准 burn rate 不一致，数值翻倍；应以错误预算为分母 |
| `burn > 2 and blast > 20%` | 想表达"小范围实验可以容忍" | 高 burn 的小范围实验不会被中止，违背讲义；应把两个门分开，任一越界即停 |
| 事后判定 | 代码最简 | 真实安全面实时评估滑动窗口并自动撤销注入 |
| 错误率口径未说明 | 省略 | 报告必须写明错误率是爆炸半径内还是全服务 |
| 不考虑时长与预算消耗 | 简化 | 应同时报告"本次实验消耗了多少预算"，与当月剩余预算比较 |
| 无 trace-ID、无抑制窗口 | 只在结尾提示语中提到 | skill 文件把"无 trace-ID 标签的实验"列为 hard reject |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 推迟类型注解求值 |
| `@dataclass` | `class Experiment:` | 自动生成构造函数；`Experiment("pod kill", 5, 0.002, 0.05)` 按字段顺序传参 |
| 模块级常量 | `ERROR_BUDGET_PER_DAY = 0.001` | 全大写命名表示常量（约定，Python 不强制） |
| 列表字面量里构造对象 | `EXPERIMENTS = [Experiment(...), ...]` | 模块加载时就创建好实验列表 |
| `max()` 防除零 | `max(EXPECTED_ERROR_RATE, 0.0001)` | 给分母设下限 |
| 布尔表达式 | `burn_rate > 2.0 and e.blast_radius_pct > 0.2` | `and` 两边都为真才为真；本例的逻辑缺陷就在这里 |
| 条件表达式 | `"ABORTED ..." if paused else "COMPLETED"` | 三元表达式 |
| 返回字典 | `return {"experiment": e.name, ...}` | 用字典打包多项结果 |
| f-string 格式符 | `{x*100:.2f}`、`{r['burn_rate_x']:>5.1f}x`、`{'Experiment':38}` | 小数位、右对齐宽度、字符串默认左对齐 |
| f-string 内表达式 | `{ERROR_BUDGET_PER_DAY*100:.2f}` | 花括号内可以写任意表达式 |
| 隐式字符串拼接 | `print(f"..." f"..." f"...")` | 相邻字符串字面量自动连接，便于跨行 |
| f-string 中取字典值 | `{r['experiment']:38}` | 外层双引号、内层单引号避免冲突 |
| 字符串乘法 | `"=" * 90`、`"-" * len(header)` | 画分隔线 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时执行 `main()` |

---

## 6. 运行结果解读

实际运行 `python3 main.py` 的完整表格：

```text
SLO error budget: 0.10%/day
Expected baseline error rate: 0.050%
Burn-rate gate: > 2.0x expected AND blast radius > 20%

Experiment                              mins   err %   burn×   blast  Status
----------------------------------------------------------------------------
pod kill (1 decode replica)                5   0.20%    4.0x      5%  COMPLETED
provider 429 fallback                      5   1.50%   30.0x     30%  ABORTED (burn-rate guard)
malformed prompt tokenizer stall           3   4.00%   80.0x     10%  COMPLETED
```

逐项解读：

- **pod kill**：代码 burn 4.0x（标准 2.0x），爆炸半径 5% → COMPLETED。按标准定义它恰好落在 2x 的边界上，不满足"> 2"，完成是合理的。
- **provider 429**：30x、爆炸半径 30% → ABORTED。这是讲义练习 1 的"代码答案"：它同时满足高 burn 与大爆炸半径。同时它也违反了 skill 文件"爆炸半径 < 30%"的上限。
- **malformed prompt**：80x（标准 40x），爆炸半径 10% → **COMPLETED**。这是本代码最值得警惕的结果：按讲义，burn 远超 2x 就应暂停；代码因为 `and` 条件放行了它。
- **修正后的对照**（测验 Q11 的 `run_experiment_v2`，按"错误率 × 爆炸半径"折算后除以错误预算，已实际运行）：pod kill 0.1x COMPLETED（消耗当日预算 0.035%）；provider 429 4.5x，因爆炸半径与 burn 双重原因 ABORTED（1.562%）；malformed prompt 4.0x ABORTED（0.833%）。

---

## 7. 动手改一改

1. 把 burn rate 的分母改成 `ERROR_BUDGET_PER_DAY`，重新运行，对比三个实验的倍数（应正好减半）。
2. 把 `and` 改成两道独立的门：`blast >= 0.30` 在实验开始前拒绝，`burn > 2.0` 在运行中中止；给结果加一个 `reasons` 列表。
3. 增加"本次实验消耗当日错误预算的比例"：`effective_rate × duration_min / (budget × 1440)`，并设置单次实验不得超过 5% 的上限。
4. 把实验改成按分钟推进的时间序列：每分钟错误率从 0 逐步升到 `induced_error_rate`，用最近 2 分钟的滑动窗口计算 burn，超过 2x 时记录"在第几分钟中止"。
5. 加入讲义中另外两个 LLM 实验："memory overload"与"KV eviction storm"，为它们设定合理的参数与成功标准。
6. 进阶：模拟"自然故障与实验重叠"——随机在某一分钟加入不带实验标签的错误，用"带标签错误占比"判断中止原因是混沌还是自然（对应讲义练习 3）。

---

## 8. 常见坑

- **burn rate 分母用错**：用基线错误率而不是错误预算，数值被放大，阈值也就失去了与 SLO 的对应关系。
- **用 `and` 合并独立的安全条件**：任何一道门越界都应停止；用 `and` 会让"高 burn + 小范围"或"低 burn + 大范围"都被放行。
- **错误率口径不清**：不说明是爆炸半径内还是全服务，同一组数据会得到相差数倍的结论。
- **安全门只做事后判断**：真正的保护来自实时中止与自动撤销注入。
- **只看 5xx**：LLM 服务的故障也表现为 TTFT 飙升、回答质量下降、流式中断，安全面应同时监控这些 SLI。
- **把提示语当作规范**：代码结尾说"小爆炸半径实验即使高 burn 也会跑完"，这是实现的副作用，不是讲义推荐的做法。
