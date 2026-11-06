# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 17 节 WMDP 与两用能力 Evaluation ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`random`）；不含任何真实题目、模型或危险内容

---

## 1. 这份代码在考察什么

这是一个"WMDP 形状"的评估 harness。它不包含任何真实题目，而是把"模型在某领域的能力"抽象成一个准确率 `p`，每道题用一次伯努利试验模拟"答对 / 答错"。在此基础上演示讲义的三个概念：

1. **分领域的能力数字**：WMDP 按生物安全、网络安全、化学三个领域分别出分，外加一个通用能力对照（这里叫 `mmlu_general`）。讲义："Models answer without being asked to assist with anything; capability can be measured without eliciting harmful behaviour."
2. **RMU 风格的 unlearning 权衡**：目标领域准确率被压到接近随机（0.25），非目标领域承受固定的"附带损失"。对应讲义"RMU ... reduced WMDP scores to near-random while preserving MMLU ... within a few percentage points"。
3. **"uplift 式"计算**：把准确率除以随机猜测基线 0.25，打印"x novice"。这一步恰恰是本代码最需要批判性阅读的地方——它与讲义中"新手相对 uplift"不是一回事（见 3.4）。

> 一句话：**用几十行代码展示"分领域测能力 → 做 unlearning → 看目标领域与通用能力各掉了多少"的评估流程，同时暴露小样本评估的统计噪声与指标混淆问题。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `random.seed(47)` | 模块级语句 | 固定随机种子，保证可复现 | 可复现评估 |
| `DOMAINS` | 模块级字典 | 4 个领域，每个 200 题，各自的基线准确率 | WMDP 三领域 + 通用能力对照 |
| `evaluate(model_accuracy)` | 函数 | 对每个领域做 `n_questions` 次伯努利试验，返回测得准确率 | 多选题评估 |
| `apply_rmu_style_unlearning(...)` | 函数 | 目标领域 `×(1−strength)` 且不低于 0.25；其他领域减 `collateral` | RMU 式 unlearning 及其代价 |
| `baseline_model()` | 函数 | 从 `DOMAINS` 取出基线准确率字典 | 被测模型 |
| `report(title, r)` | 函数 | 格式化打印 | 报告 |
| `main()` | 函数 | 基线 → 评估 → unlearning → 再评估 → "uplift"计算 | 实验流程 |

数据流：`baseline_model()`（真实准确率）→ `evaluate`（抽样得到测得准确率）→ `apply_rmu_style_unlearning`（修改真实准确率）→ `evaluate`（再次抽样）→ 测得值 / 0.25 → 打印。

---

## 3. 逐段精讲

### 3.1 领域配置

```python
DOMAINS = {
    "biosecurity":   {"n_questions": 200, "accuracy": 0.72},
    "cybersecurity": {"n_questions": 200, "accuracy": 0.80},
    "chemistry":     {"n_questions": 200, "accuracy": 0.64},
    "mmlu_general":  {"n_questions": 200, "accuracy": 0.78},
}
```

- 嵌套字典：外层键是领域名，内层是"题数 + 模型真实准确率"。
- 每个领域都是 200 题。真实 WMDP 是生物 1,520、网络 2,225、化学 412（讲义），题数差异很大，直接影响各领域结论的精度（化学单次评估的标准误约 2.4 个百分点，网络约 0.8 个百分点）。
- 文档字符串说"Mock model is a 3-domain expert"，但这里其实有 4 个领域；`mmlu_general` 扮演通用能力对照组。
- 4 选 1 多选题的随机猜测准确率是 0.25，这个数字在后面作为 unlearning 的下限和"novice"基线出现。

### 3.2 评估：伯努利抽样

```python
def evaluate(model_accuracy: dict) -> dict:
    results = {}
    for domain, cfg in DOMAINS.items():
        correct = 0
        for _ in range(cfg["n_questions"]):
            acc = model_accuracy.get(domain, cfg["accuracy"])
            if random.random() < acc:
                correct += 1
        results[domain] = correct / cfg["n_questions"]
    return results
```

- 每道题独立地以概率 `acc` 答对，统计答对比例。测得准确率是一个二项分布的样本均值，标准误为 `√(p(1−p)/n)`；n = 200 时约 0.028~0.034。
- `model_accuracy.get(domain, cfg["accuracy"])`：若传入的模型字典缺少某领域，就退回到 `DOMAINS` 中的基线值——这是一个"静默默认"，好处是容错，坏处是拼错领域名时不会报错。
- `acc` 在内层循环里每次重复查字典，放到循环外会更清晰（结果相同）。
- ⚠️ 每次调用 `evaluate` 都重新抽样，相当于**每次换一套新题**。真实基准是固定题集，前后对比应当做**配对**评估（同一道题前后对错的变化），方差会小得多。

### 3.3 RMU 风格的 unlearning

```python
def apply_rmu_style_unlearning(model_accuracy: dict,
                               targets: list[str],
                               strength: float = 0.9,
                               collateral: float = 0.03) -> dict:
    new = dict(model_accuracy)
    for d in targets:
        new[d] = max(0.25, new[d] * (1 - strength))
    for d in new:
        if d not in targets:
            new[d] = max(0.0, new[d] - collateral)
    return new
```

- `dict(model_accuracy)` 做浅拷贝，原字典不被修改（值都是 float，浅拷贝足够）。
- 目标领域：乘以 `(1 − strength)`，再用 `max(0.25, ...)` 截在随机水平。`main()` 用 `strength=0.85`：biosecurity `0.72 × 0.15 = 0.108 → 0.25`，chemistry `0.64 × 0.15 = 0.096 → 0.25`。只要 `strength` 超过约 0.653（bio）/ 0.609（chem），结果都一样是 0.25——在这个范围内 `strength` 不再起作用。
- 非目标领域：一律减去 `collateral`（`main()` 中为 0.04），并以 0 为下限。期望值：cybersecurity 0.76，mmlu_general 0.74。
- ⚠️ 两个建模简化：
  - 附带损失与遗忘强度、领域相似度都无关，是一个独立的常数；真实方法中遗忘越强，通用能力损失往往越大，且相近学科受影响更多（测验 Q12 给出了按相似度分配附带损失的版本）；
  - cybersecurity 是 WMDP 的危险领域之一，却被当作"附带损失"对象和通用能力放在一起，混淆了"未被针对的危险领域"与"应保留的通用能力"。
- 讲义"Use It"说"zero out domain-specific representation"，代码里并没有任何"表示"，只是直接修改准确率数字。真实 RMU 是在训练中改变模型内部表示。
- 拼错目标名（如 `["bio"]`）会在 `new[d]` 处抛 `KeyError`（已验证）。

### 3.4 报告与"uplift 式"计算

```python
    print("\nuplift-style calculation (novice baseline ~= 0.25 random):")
    novice = 0.25
    for d in ("biosecurity", "cybersecurity", "chemistry"):
        pre = baseline_results[d]
        pst = post_results[d]
        uplift_pre = pre / novice
        uplift_post = pst / novice
        print(f"  {d:18s}  pre={uplift_pre:.2f}x novice  post={uplift_post:.2f}x novice")
```

- 计算的是"测得准确率 ÷ 0.25"，也就是**相对随机猜测的倍数**。代码把"新手"假设成随机猜测者。
- ⚠️ 这与讲义中的"novice-relative uplift"是不同的量。讲义的 uplift（例如 Anthropic 试验的 2.53 倍）是在真人新手参与的对照试验中，比较"有模型辅助"与"只有互联网搜索"两组在**实际任务**上的成功率。多选题准确率除以随机水平，既不涉及真人，也不涉及任务，更不涉及"互联网基线"。读输出时不要把 `2.80x` 与 `2.53x` 放在一起比较。
- unlearning 后 chemistry 显示 `0.98x`（低于随机），只是抽样噪声。
- 这个循环写死了三个领域名，新增领域时需要同步修改（测验 Q12）。

### 3.5 TAKEAWAY 的说法与实际输出

- "RMU-style unlearning reduces target-domain scores with ~3-4% general-capability collateral damage"：配置的是 4 个百分点，但本次测得 MMLU 下降 8 个百分点、cybersecurity 下降 0 个百分点。1,000 个种子的实验显示测得的 MMLU 下降 90% 区间约为 −3 ~ +11 个百分点（测验 Q10）——200 题的评估无法分辨"3~4%"这一量级。
- "the 2025 field narrative is 'mild uplift' -> ..."：按讲义，"mild uplift" 属于 2024 年，2025 年才是"on the cusp"与 2.53 倍试验；这句只是概括，不是代码测出的结果。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用准确率 + 伯努利抽样代替真实题目 | 不接触任何危险内容，几毫秒跑完 | 不能用于真实结论；真实评估用 WMDP 固定题集与真实模型 |
| 每领域 200 题 | 简单对称 | 标准误约 3 个百分点，测不出 3~4% 的附带损失；真实 WMDP 题数不对称 |
| 每次评估重新抽样 | 实现简单 | 相当于换题，前后差值方差翻倍；应做配对评估 |
| 目标领域截在 0.25 | 表达"接近随机"是 unlearning 的目标 | `strength` 超过阈值后失去意义 |
| 固定常数 `collateral` | 参数直观 | 与遗忘强度、领域相似度无关，掩盖真实权衡 |
| cybersecurity 当附带损失对象 | 只对 bio、chem 做 unlearning | 混淆"非目标危险领域"和"通用能力" |
| `准确率 / 0.25` 称为"x novice" | 给出一个倍数直观感受 | 与讲义的"新手相对 uplift"（真人对照试验）概念不同，容易误导 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 延迟求值注解，`list[str]` 写法兼容旧版本 |
| 嵌套字典 | `DOMAINS = {"biosecurity": {"n_questions": 200, "accuracy": 0.72}, ...}` | 用字典的字典表示配置表 |
| 字典推导式 | `{d: cfg["accuracy"] for d, cfg in DOMAINS.items()}` | 从配置表中抽出一列 |
| `dict.get(key, default)` | `model_accuracy.get(domain, cfg["accuracy"])` | 键不存在时返回默认值 |
| `dict(...)` 浅拷贝 | `new = dict(model_accuracy)` | 新建字典，修改它不影响原字典 |
| 多行函数签名 + 默认参数 | `def apply_rmu_style_unlearning(model_accuracy: dict, targets: list[str], strength: float = 0.9, ...)` | 参数多时按行排列；关键字调用 `strength=0.85` 更易读 |
| `max` 作下限截断 | `max(0.25, new[d] * (1 - strength))` | 结果不低于 0.25 |
| `in` 判断成员 | `if d not in targets:` | 列表成员判断（目标多时可以改用集合） |
| 伯努利试验 | `if random.random() < acc: correct += 1` | `random.random()` 返回 [0, 1) 均匀随机数 |
| `_` 占位循环变量 | `for _ in range(cfg["n_questions"]):` | 只需要循环次数，不需要变量 |
| 元组字面量遍历 | `for d in ("biosecurity", "cybersecurity", "chemistry"):` | 固定顺序的不可变序列 |
| f-string 宽度与小数 | `{d:18s}`、`{score:.3f}`、`{uplift_pre:.2f}x` | 左对齐到 18 宽；保留 3 / 2 位小数 |
| 函数返回 `None` 的打印函数 | `def report(title: str, r: dict) -> None:` | 只产生副作用（打印） |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行才执行；被 import 时（测验中的统计实验）不执行 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，瞬间完成）：

```text
baseline model accuracy by domain          ← 设定的真实准确率
  biosecurity        : 0.720
  cybersecurity      : 0.800
  chemistry          : 0.640
  mmlu_general       : 0.780

measured scores (pre-unlearning)           ← 200 题抽样
  biosecurity        : 0.700
  cybersecurity      : 0.795
  chemistry          : 0.605
  mmlu_general       : 0.795

measured scores (post-unlearning: bio + chem)
  biosecurity        : 0.255               ← 期望 0.25（被下限截断）
  cybersecurity      : 0.795               ← 期望 0.76，噪声掩盖了 4 个百分点的下降
  chemistry          : 0.245               ← 期望 0.25
  mmlu_general       : 0.715               ← 期望 0.74，测得下降 8 个百分点

uplift-style calculation (novice baseline ~= 0.25 random):
  biosecurity         pre=2.80x novice  post=1.02x novice
  cybersecurity       pre=3.18x novice  post=3.18x novice
  chemistry           pre=2.42x novice  post=0.98x novice    ← 低于 1 倍只是噪声
```

逐项解读：

- **unlearning 前**：测得值与真实值的偏差在 0.5~3.5 个百分点之间，都在 200 题的抽样误差范围内（标准误约 3 个百分点）。
- **目标领域**：bio、chem 都降到约 0.25，即接近随机——对应讲义"reduced WMDP scores to near-random"。
- **非目标领域**：配置的附带损失相同（都是 0.04），测得结果却一个是 0（cyber）、一个是 8 个百分点（MMLU）。这说明：用 200 题、两次独立抽样，无法可靠测出"几个百分点"的通用能力损失。按 skill 文件，"没有通用能力差值的 unlearning 声明不可信"——这里还要补一句：没有置信区间的差值同样不可信。
- **"x novice" 一栏**：是"相对随机猜测"的倍数（见 3.4），不是讲义中真人试验意义上的 uplift。

---

## 7. 动手改一改

1. （讲义练习 1）把每个领域的题数改成真实 WMDP 的 1,520 / 2,225 / 412，并给 MMLU 设为 14,000 左右，重新运行，观察各领域测得值的稳定性差异。
2. 实现配对评估：先为每个领域生成固定的"题目难度"列表，前后两次评估在同一组题上比较对错变化；对比独立抽样与配对两种方式下"附带损失"估计的方差。
3. 给 `report` 增加 95% 置信区间（正态近似 `p ± 1.96·√(p(1−p)/n)` 或 Wilson 区间），并给"前后差值"做 bootstrap 区间。
4. （讲义练习 2）在 `DOMAINS` 中加入第四个危险领域，并修改 `main()` 中写死的领域元组；思考为什么构造 yellow-zone 题目需要专家审查与合规流程（只从流程角度思考，不需要编写任何题目）。
5. （讲义练习 3）按测验 Q12 实现"按领域相似度分配附带损失"的 unlearning，让 `collateral` 随 `strength` 增长（例如 `collateral = k · strength²`），画出"目标领域分数 vs 通用能力分数"的权衡曲线。
6. 把"uplift"一栏改名为 `ratio_vs_chance`，另写一个函数，用两组"模拟参与者"（对照组：只用互联网；实验组：有模型辅助）的任务成功率计算真正的相对 uplift，并讨论样本量对倍数置信区间的影响（讲义练习 4）。

---

## 8. 常见坑

- **把多选题准确率当作 uplift**：`准确率 / 0.25` 是相对随机猜测的倍数，不是真人试验中的 uplift。
- **忽略抽样误差**：200 题的标准误约 3 个百分点，报告"附带损失 3~4%"之前先算置信区间。
- **前后两次独立抽样**：等于换了一套题；应在同一题集上做配对比较。
- **把非目标危险领域当作通用能力**：cybersecurity 下降与否和"通用能力是否保留"是两个问题，应分开报告。
- **只看目标领域掉到随机**：skill 文件要求同时报告通用能力差值，否则 unlearning 声明不可信。
- **把能力代理当作部署风险**：WMDP 分数还要结合拒答路径、引出研究、隐性知识与执行障碍来解读（讲义"The measurement pitfall"）。
- **静默默认值**：`dict.get` 的回退值会掩盖领域名拼写错误；关键配置最好显式校验。
