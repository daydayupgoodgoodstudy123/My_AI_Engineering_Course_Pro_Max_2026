# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 02 节 STaR、V-STaR、Quiet-STaR：自学推理 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`），无需网络、无需模型

---

## 1. 这份代码在考察什么

这不是一个真的语言模型，而是一个**概率模拟器**：把"模型"抽象成三种 rationale 策略的混合分布，然后模拟 STaR 的"答对才保留 → 重新训练"循环，观察每类策略的占比如何随轮次变化。

1. **STaR 过滤器的选择压力**：保留集中各类 rationale 的比例 ∝ 各自的"出现概率 × 答对概率"。
2. **ID vs OOD**：shortcut 在训练分布（ID）上命中 40%，在分布外（OOD）只有 5%；sound 推理两边都 100%。用两个准确率的差距衡量"捷径污染"。
3. **V-STaR 推理**：每题采样 N 个 trace，用 verifier 打分取最高者。
4. **讲义核心论点**：answer-conditioned gradient 会强化"碰巧答对"的推理。

> 一句话：**用最少的代码把"过滤器奖励什么，循环就放大什么"可视化**。但要注意，这份代码在默认参数下的实际输出**并不支持**它自己打印的结论（OOD 并没有崩），这是本讲解的重点之一。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Trace` | dataclass | 一条采样结果：策略名、答案是否正确、推理是否正确 | (rationale, answer) |
| `Model` | dataclass + 方法 | 存 `prob_sound`、`prob_shortcut`（random 为余量）；`sample(on_ood)` 采一条 trace | 策略混合分布 |
| `evaluate` | 函数 | 采 n 条 trace，返回 (答案准确率, 推理正确比例) | ID/OOD 评估 |
| `star_round` | 函数 | 采 1000 条 ID trace → 保留答对的 → 按占比与旧分布 `alpha` 混合 → 新 Model | 一轮 STaR |
| `run_star` | 函数 | 连续跑若干轮，返回每轮的 Model 列表 | bootstrap 循环 |
| `vstar_infer` | 函数 | best-of-N：按 verifier 分数挑一条，统计正确率 | V-STaR 推理时选择 |
| `report_round` / `vstar_report` | 函数 | 打印表格 | 输出 |
| `main` | 函数 | 设种子，跑 Scenario A（无 shortcut）、B（有 shortcut）和 V-STaR | 入口 |

数据流：`main()` → `run_star(5, Model(...))` →（每轮 `star_round` → `Model.sample`）→ `report_round`（`evaluate` ID/OOD）→ `vstar_report(models[-1])`（`vstar_infer`）→ 打印 HEADLINE。

---

## 3. 逐段精讲

### 3.1 `Trace` 与 `Model.sample`：三种策略

```python
@dataclass
class Model:
    prob_sound: float
    prob_shortcut: float
    # implied prob_random = 1 - sound - shortcut

    def sample(self, on_ood: bool) -> Trace:
        r = random.random()
        if r < self.prob_sound:
            return Trace("sound", True, True)
        elif r < self.prob_sound + self.prob_shortcut:
            ok = random.random() < (0.05 if on_ood else 0.40)
            return Trace("shortcut", ok, False)
        else:
            ok = random.random() < 0.10
            return Trace("random", ok, False)
```

- 用一个 `[0, 1)` 的随机数按区间选策略：`[0, ps)` → sound，`[ps, ps + psh)` → shortcut，其余 → random。这是从离散分布采样的标准写法（"轮盘赌"）。
- 三种策略的命中率：

| 策略 | ID 命中率 | OOD 命中率 | `rationale_sound` |
|------|----------|-----------|-------------------|
| sound | 100% | 100% | True |
| shortcut | 40% | 5% | False |
| random | 10% | 10% | False |

- 由此可得期望准确率公式：`ID = ps + 0.4·psh + 0.1·pr`，`OOD = ps + 0.05·psh + 0.1·pr`（`pr = 1 − ps − psh`）。Scenario B 初始模型 (0.2, 0.4)：ID 40%、OOD 26%。
- ⚠️ 简化：真实模型的"策略"不是离散的三类，也不存在一个可以直接读取的 `rationale_sound` 标志。
- random 的概率**不单独存储**，始终是 `1 − ps − psh`。

### 3.2 `evaluate`：同时统计两个指标

```python
def evaluate(model: Model, n: int, on_ood: bool) -> tuple[float, float]:
    correct = 0
    sound = 0
    for _ in range(n):
        t = model.sample(on_ood)
        if t.answer_correct:
            correct += 1
        if t.rationale_sound:
            sound += 1
    return correct / n, sound / n
```

- 返回 `(答案准确率, 推理正确比例)`。两者之差就是"答对但推理不对"的比例——这正是 STaR 看不见的部分。
- 返回类型 `tuple[float, float]` 是 Python 3.9+ 的内置泛型写法。
- `report_round` 只打印 ID 的 sound 比例；因为 soundness 与 `on_ood` 无关，OOD 的 sound 比例期望相同。
- ⚠️ 每次只采 500 个样本，标准误约 2 个百分点，表中相邻轮次的波动（例如 Scenario A 第 3 轮 OOD 85.6% → 第 4 轮 96.0%）有相当部分是噪声。

### 3.3 `star_round`：一轮 STaR

```python
def star_round(model: Model, n_samples: int = 1000) -> Model:
    kept = []
    for _ in range(n_samples):
        t = model.sample(on_ood=False)
        if t.answer_correct:
            kept.append(t)

    if not kept:
        return model

    sound_kept = sum(1 for k in kept if k.strategy == "sound")
    shortcut_kept = sum(1 for k in kept if k.strategy == "shortcut")
    random_kept = sum(1 for k in kept if k.strategy == "random")
    total = len(kept)

    alpha = 0.6
    new_sound = alpha * (sound_kept / total) + (1 - alpha) * model.prob_sound
    new_short = alpha * (shortcut_kept / total) + (1 - alpha) * model.prob_shortcut

    s = new_sound + new_short
    if s > 1.0:
        new_sound /= s
        new_short /= s
    return Model(new_sound, new_short)
```

逐行说明：

- **采样只在 ID 上进行**（`on_ood=False`）：STaR 只能在有标签的训练分布上过滤。
- **过滤**：`if t.answer_correct` 是唯一标准——answer-conditioned。
- **"重新训练"被抽象成**：新分布 = `alpha × 保留集中的占比 + (1 − alpha) × 旧分布`。`alpha = 0.6` 相当于"fine-tune 只把模型往保留集推 60%"，注释说是为了"avoid collapsing"（防止一轮就完全坍缩到保留集分布）。
- **选择压力的数学本质**：保留集中策略 i 的占比 = `p_i · hit_i / Σ_j p_j · hit_j`。sound 的 hit = 1.0，shortcut 的 hit = 0.4，所以 sound 每轮被放大的倍数比 shortcut 大 2.5 倍。
- 手算 Scenario B 第一轮（期望）：答对概率 0.40 = 0.20 + 0.16 + 0.04；保留集占比 0.50 / 0.40 / 0.10；`new_sound = 0.6×0.5 + 0.4×0.2 = 0.38`，`new_short = 0.6×0.4 + 0.4×0.4 = 0.40`。实际输出 0.392 / 0.385（采样噪声）。
- ⚠️ **死代码**：`s > 1.0` 永远不成立。保留集占比之和为 1，旧分布之和 ≤ 1，它们的凸组合也 ≤ 1。
- ⚠️ `random_kept` 计算了但从未使用；random 的新概率隐含为 `1 − new_sound − new_short`。
- ⚠️ 讲义提到的 **rationalization**（对做不对的题注入答案提示）没有实现。

### 3.4 `run_star`：循环

```python
def run_star(rounds: int, initial: Model) -> list[Model]:
    models = [initial]
    m = initial
    for _ in range(rounds):
        m = star_round(m)
        models.append(m)
    return models
```

- 返回长度为 `rounds + 1` 的列表（含初始模型），方便打印第 0 轮到第 5 轮。
- `Model` 每轮都新建，旧模型不被修改，因此列表里保存的是每一轮的"快照"。

### 3.5 `vstar_infer`：best-of-N 与"偷看答案"的 verifier

```python
    for _ in range(n_problems):
        traces = [model.sample(on_ood) for _ in range(samples_per_problem)]
        best = None
        best_score = -1.0
        for t in traces:
            score = 0.9 if t.rationale_sound else (0.55 if t.answer_correct else 0.3)
            score += random.random() * 0.1
            if score > best_score:
                best_score = score
                best = t
        if best and best.answer_correct:
            correct += 1
```

- 每题采 N 条 trace，手写"求最大值"循环选出分数最高者。
- 分数区间：sound `[0.9, 1.0)`、答对的非 sound `[0.55, 0.65)`、答错的 `[0.3, 0.4)`。三个区间不重叠，所以噪声项 `random.random() * 0.1` 实际上**不改变任何排序**，只在同类之间打破平局。
- 结果：只要 N 个里有一条 sound，就一定选 sound；没有 sound 但有答对的，就一定选答对的。这等价于 **pass@N**（N 次里至少一次对）。
- 训练后模型 `p(sound) = 0.886`，N = 4 时没有 sound 的概率 `0.114^4 ≈ 0.00017`，因此 ID/OOD 都是 100%。
- ⚠️ docstring 承认这是 "idealized verifier — it reads the ground-truth rationale_sound flag"，但它**还读了 `answer_correct`**。推理时（尤其 OOD）标签不可得，这一点比 docstring 说的更"作弊"。
- ⚠️ 讲义说 verifier 的风险是 "prefer well-formatted wrong reasoning"，而这里的 verifier 恰好系统性地**偏好** sound——它无法演示讲义所说的风险。测验 Q11 给出了一个只看可观测特征的 verifier，N 越大 OOD 准确率越低（89.1% → 41.5%）。
- `if best and best.answer_correct`：`best` 初值为 `None`，当 `samples_per_problem = 0` 时保护不报错。

### 3.6 `main`：两个场景

```python
    random.seed(42)
    ...
    models = run_star(5, Model(prob_sound=0.20, prob_shortcut=0.0))
    ...
    models = run_star(5, Model(prob_sound=0.20, prob_shortcut=0.40))
    report_round("STaR bootstrap rounds (with shortcuts)", models)

    vstar_report(models[-1])
```

- `random.seed(42)` 只在开头设一次，之后所有调用共享同一个随机流，所以改变任何一处的采样次数都会改变后面所有数字。
- Scenario A（无 shortcut）作为对照组；Scenario B 引入 shortcut。
- V-STaR 只在 Scenario B 第 5 轮的模型上评估。
- ⚠️ 最后的 HEADLINE（"Scenario B climbs on ID while OOD collapses"、"cannot undo training bias"）是**硬编码的文字**，与实际输出相矛盾：Scenario B 的 OOD 从 27.8% 升到 90.2%，V-STaR OOD 达到 100%。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 把模型抽象成三类策略的混合 | 不需要真模型，秒级运行 | 真实 rationale 是连续谱，没有可读的 soundness 标签 |
| 用 `alpha` 混合代替 fine-tune | 一行代码模拟"训练向保留集靠拢" | 真实 fine-tune 有泛化、遗忘、过拟合等复杂效应 |
| shortcut ID 命中率 0.40 | 体现"偶尔蒙对" | 命中率低于 sound，过滤器会逐轮淘汰它，无法演示 OOD 崩溃；改成 1.0 才能演示（见测验 Q10） |
| 只用一个随机种子、500/1000 样本 | 运行快、可复现 | 表格噪声大；应多 seed 平均或用期望公式迭代 |
| verifier 读取真实标签 | 给出"理想上界" | 等价于 pass@N，无法体现 verifier 偏差；真实 verifier 只能看 rationale 文本 |
| HEADLINE 硬编码 | 传达讲义观点 | 与输出不符；结论应由数据计算后再打印（例如检测 OOD 是否下降） |
| 未实现 rationalization、Quiet-STaR | 控制篇幅 | 标题包含 Quiet-STaR，但代码只覆盖 STaR 与 V-STaR |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` | `class Trace`、`class Model` | 自动生成 `__init__`；dataclass 里也可以定义普通方法（`Model.sample`） |
| `from dataclasses import dataclass, field` | 第 21 行 | `field` 被导入但未使用（可删除） |
| 类型注解与内置泛型 | `-> tuple[float, float]`、`-> list[Model]` | Python 3.9+ 可直接写 `list[...]`、`tuple[...]` |
| `random.random()` / `random.seed()` | `r = random.random()`、`random.seed(42)` | `[0, 1)` 均匀随机数；固定种子保证可复现 |
| 条件表达式 | `0.05 if on_ood else 0.40` | 三元表达式，一行内二选一 |
| 嵌套条件表达式 | `0.9 if t.rationale_sound else (0.55 if t.answer_correct else 0.3)` | 三选一，括号增强可读性 |
| 生成器表达式 + `sum` | `sum(1 for k in kept if k.strategy == "sound")` | 计数的惯用写法，不创建中间列表 |
| 列表推导式 | `[model.sample(on_ood) for _ in range(samples_per_problem)]` | 生成 N 条 trace |
| `_` 占位变量 | `for _ in range(n)` | 表示不使用循环变量 |
| 默认参数 | `def star_round(model, n_samples: int = 1000)` | 调用时可省略 |
| 增强赋值 | `correct += 1`、`new_sound /= s`、`score += ...` | 原地运算 |
| `enumerate` | `for i, m in enumerate(models)` | 同时拿到下标和元素 |
| `None` 判断 | `if best and best.answer_correct` | `None` 为假值，短路求值避免访问 `None` 的属性 |
| f-string 格式符 | `{m.prob_sound:>10.3f}`、`{id_acc:>8.1%}`、`{tag:<3}`、`{n:>3}` | 宽度、小数位、百分比、对齐 |
| `if __name__ == "__main__":` | 文件末尾 | 脚本入口 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，`random.seed(42)`，瞬间完成）：

```text
STaR bootstrap rounds (clean)
  round    p(sound)   p(shortcut)    ID acc   OOD acc  sound frac
      0       0.200         0.000     28.8%     27.4%       23.2%
      1       0.500         0.000     56.2%     58.6%       51.0%
      2       0.740         0.000     77.8%     77.8%       74.8%
      3       0.882         0.000     90.6%     85.6%       89.0%
      4       0.942         0.000     94.4%     96.0%       93.2%
      5       0.973         0.000     97.8%     96.6%       97.2%

STaR bootstrap rounds (with shortcuts)
  round    p(sound)   p(shortcut)    ID acc   OOD acc  sound frac
      0       0.200         0.400     39.8%     27.8%       19.8%
      1       0.392         0.385     61.0%     43.4%       43.6%
      2       0.582         0.304     69.6%     58.4%       56.8%
      3       0.719         0.224     80.8%     72.0%       73.8%
      4       0.822         0.152     90.8%     82.4%       85.0%
      5       0.886         0.103     92.2%     90.2%       89.0%

V-STaR best-of-N inference
  n=  1  ID   accuracy 92.4%
  n=  1  OOD  accuracy 90.2%
  n=  4  ID   accuracy 100.0%
  n=  4  OOD  accuracy 100.0%
  n= 16  ID   accuracy 100.0%
  n= 16  OOD  accuracy 100.0%

HEADLINE: STaR reinforces whatever reaches the answer
  Scenario A climbs on both ID and OOD.
  Scenario B climbs on ID while OOD collapses — ...
```

逐项解读：

- **Scenario A**：没有 shortcut，只有 sound 与 random。sound 第一轮在保留集中占 `0.2 / (0.2 + 0.08) ≈ 71%`，`0.6 × 0.714 + 0.4 × 0.2 = 0.509`（实际 0.500）。之后快速趋近 1，ID 与 OOD 同步上升——因为 sound 在两边都一样准。
- **Scenario B**：
  - ID 与 OOD 之间始终有差距（第 0 轮 12 个点，第 5 轮约 2 个点），差距的来源就是 shortcut 的 `0.4 − 0.05 = 0.35` 命中率差乘以 `p(shortcut)`；
  - `p(shortcut)` 第 1 轮几乎不变（0.400 → 0.385），之后逐轮下降到 0.103；
  - **OOD 没有崩溃**，而是从 27.8% 升到 90.2%。原因：shortcut 在 ID 上只有 40% 命中，sound 是 100%，过滤器天然更偏好 sound。
  - 讲义练习 1 问"两次运行的最终准确率差多少"：第 5 轮 ID 97.8% vs 92.2%，OOD 96.6% vs 90.2%，差约 6 个点；Scenario B 的 ID 是 92.2%，满足"都超过 90%"。
- **V-STaR**：n = 1 时就是普通采样（92.4% / 90.2%）；n ≥ 4 时 100%，因为 verifier 能看到真实标签（见 3.5）。
- **HEADLINE 与数据不符**：这是硬编码的结论。要复现讲义的现象，把 shortcut 的 ID 命中率改为 1.0：按期望迭代 5 轮后 ID 99.2%、OOD 卡在 36.4%（详见测验 Q10）。

---

## 7. 动手改一改

1. **（练习 1）**把 Scenario B 的 `prob_shortcut` 改成 0.0、0.2、0.4、0.6，各跑 5 个 seed 取平均，画出"初始 shortcut 比例 vs 第 5 轮 OOD 准确率"。
2. **复现 OOD 卡住**：把 `sample` 中 shortcut 的 ID 命中率从 `0.40` 改为 `1.0`，验证 ID → 约 99%、OOD → 约 36%；再试 0.7、0.9，找到"shortcut 开始被保留"的临界点。
3. **把 HEADLINE 改成数据驱动**：比较 Scenario B 首末轮的 OOD 准确率，自动打印"OOD 上升"或"OOD 停滞/下降"。
4. **写一个真实的 verifier**：只根据 `strategy`（代表文本风格）打分、不读 `answer_correct`；令 shortcut 得分略高于 sound，观察 N = 1、4、16 时准确率下降（参考测验 Q11）。
5. **加入 process supervision**：在 `star_round` 的过滤中加一个召回率为 `recall` 的步骤检查器，比较 `recall = 0 / 0.5 / 0.8` 下的 OOD 结果（参考测验 Q12）。
6. **加入 rationalization 与停止条件**：为"答错"的样本以一定概率生成 rationalized trace（可设定它 50% 是 sound）；每轮评估 OOD，若连续两轮下降则停止（对应 skill 文件 "Rounds past peak OOD accuracy actively degrade quality"）。

---

## 8. 常见坑

- **只看 ID 准确率**：ID 上 outcome 与 process 监督几乎一样（都约 99%），差距只在 OOD 显现。
- **相信硬编码的结论**：先看数字再看结论；本文件的 HEADLINE 与输出相矛盾。
- **让 verifier 读取标签**：模拟时很容易"顺手"用了推理时不可得的信息，得到虚高的结果。
- **单 seed 下结论**：500 个样本的准确率有约 ±2 个点的噪声，相邻轮次的波动不一定是真实趋势。
- **以为 shortcut 一定被保留**：只有当 shortcut 在训练分布上的命中率接近 sound 时，STaR 才无法淘汰它；命中率越低，过滤器越会自动清除它。
- **死代码掩盖意图**：`if s > 1.0` 永远不触发，读者可能误以为归一化在起作用。
- **全局随机流**：`random.seed(42)` 只设一次，增删任意一次采样都会让后面的所有数字改变。
