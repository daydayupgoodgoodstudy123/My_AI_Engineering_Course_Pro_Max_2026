# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 11 节 可扩展监督与弱到强泛化 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数，约 8 秒） ｜ **依赖**：仅标准库（`random`），无需网络、无需 GPU

---

## 1. 这份代码在考察什么

代码在一个 3 维合成二分类任务上模拟 Burns et al. 2023 的 weak-to-strong generalization（W2SG）实验流程：

1. **三个基线**：弱监督者自己的准确率（weak alone）、强模型在金标上训练的上限（ceiling）、强模型在弱标签上训练后的准确率（strong on weak）。
2. **PGR 指标**：`(strong_on_weak − weak) / (ceiling − weak)`。
3. **弱监督的质量**：扫描 `weak_accuracy` 参数，观察 PGR 如何变化（讲义练习 1）。

> 一句话：**用一个最小可运行的例子把 PGR 的三个量算出来**。但要看清这里的"强模型"只是从零训练的逻辑回归，没有任何预训练先验——它能做的只是平均掉随机噪声，无法纠正弱监督者的结构性错误；输出中 PGR 的起伏主要是 SGD 噪声。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `random.seed(29)` | 模块级语句 | 固定随机数 | 可复现 |
| `gen` | 函数 | 生成 n 个 `(x, y)`，`x ~ N(0, I₃)`，`y = [x0 + x1 − 0.5·x2 > 0]` | 任务与金标 |
| `weak_label` | 函数 | 只看 `x0` 的阈值规则 + 以 `1 − accuracy` 概率翻转 | 弱监督者（GPT-2 级） |
| `train_strong` | 函数 | 3 特征逻辑回归，逐样本 SGD | 强模型（GPT-4 级）的 fine-tune |
| `accuracy` | 函数 | 线性模型在数据集上的准确率 | 评估 |
| `run` | 函数 | 生成数据 → 三个基线 → 计算并打印 PGR | W2SG 实验流程 |
| `main` | 函数 | 扫描 `weak_accuracy ∈ {0.6, 0.7, 0.8, 0.9}` | 讲义练习 1 |

数据流：`gen`（eval 1000 + train 1000）→ `weak_label` 在 eval 上测 weak alone → `train_strong(train 金标)` 得 ceiling → `weak_label` 给 train 打标 → `train_strong(弱标签)` 得 strong on weak → 计算 PGR → 打印。

---

## 3. 逐段精讲

### 3.1 `gen`：一个线性可分、无噪声的任务

```python
def gen(n: int) -> list[tuple[list[float], int]]:
    data = []
    for _ in range(n):
        x = [random.gauss(0.0, 1.0) for _ in range(3)]
        y = 1 if x[0] + x[1] - 0.5 * x[2] > 0 else 0
        data.append((x, y))
    return data
```

- 三个独立标准正态特征，标签由真实方向 `(1, 1, −0.5)` 的线性判别给出。
- 标签是确定性的、没有噪声，因此线性模型在金标上可以接近 100%——这就是输出中 ceiling 为 0.993–1.000 的原因。讲义 "Use It" 说 ceiling 是 95%，与代码不符。
- 返回类型 `list[tuple[list[float], int]]`：每个元素是"特征列表 + 整数标签"的二元组。

### 3.2 `weak_label`：结构性错误 + 随机错误

```python
def weak_label(x: list[float], accuracy: float = 0.70) -> int:
    base = 1 if x[0] > 0 else 0
    if random.random() < accuracy:
        return base
    return 1 - base
```

- 第一层是**结构性错误**：只看 `x[0]`，忽略 `x[1]` 与 `x[2]`。`x0` 与 `v = x0 + x1 − 0.5·x2` 的相关系数 ρ = 1/1.5 ≈ 0.667，两者同号的概率 `q = 1 − arccos(ρ)/π ≈ 0.732`。
- 第二层是**随机错误**：以 `1 − accuracy` 的概率翻转。
- 因此真实准确率 = `a·q + (1 − a)(1 − q)`：

| 参数 a | 真实准确率（理论） | 单次实测 |
|-------|-----------------|---------|
| 0.6 | 0.547 | 0.542 |
| 0.7 | 0.593 | 0.607 |
| 0.8 | 0.639 | 0.637 |
| 0.9 | 0.686 | 0.694 |

- ⚠️ 参数名 `accuracy` 有误导性：它是"不翻转的概率"，不是相对金标的准确率。讲义说"Weak labeler has 70% accuracy"，实际只有约 59%。
- 每次调用都重新抽随机数，同一个 `x` 两次调用可能得到不同标签（eval 上测 weak alone 时与 train 上打标时是独立的）。

### 3.3 `train_strong`：逐样本 SGD 的逻辑回归

```python
def train_strong(data, steps: int = 200, lr: float = 0.05) -> list[float]:
    w = [0.0, 0.0, 0.0]
    b = 0.0
    for _ in range(steps):
        random.shuffle(data)
        for x, y in data:
            z = b + sum(wi * xi for wi, xi in zip(w, x))
            p = 1.0 / (1.0 + pow(2.71828, -z))
            err = p - y
            for i in range(3):
                w[i] -= lr * err * x[i]
            b -= lr * err
    return w + [b]
```

- 交叉熵损失对 logit 的梯度是 `p − y`（与第 10 阶段 GPT 训练中"softmax 概率 − one-hot"是同一个公式的二分类版本），所以 `w ← w − lr·(p − y)·x`。
- `steps` 实际上是 **epoch 数**：每个 step 遍历全部 1,000 个样本，共 200,000 次更新。
- ⚠️ **没有先验**：从 `[0, 0, 0]` 开始。讲义与 TAKEAWAY 说强模型"借助预训练先验"超越弱监督者，在这里不成立。
- ⚠️ **恒定学习率、无正则**：
  - 金标数据线性可分，权重会持续增长（我们看到约 `[18, 18, −9]`），方向正确但幅度发散；
  - 弱标签上最优方向是 `(1, 0, 0)`，但恒定 lr 让 `w1`、`w2` 始终在 0 附近大幅抖动。例如 a = 0.8 那次学到 `[1.25, 0.35, −0.27]`，噪声碰巧与真实方向同号，准确率跳到 0.833；a = 0.6 那次是 `[0.34, −0.05, −0.33]`。
- ⚠️ `pow(2.71828, -z)`：用近似的 e，并且当 `z < −709` 左右时 `pow` 会抛 `OverflowError`。本次运行没有触发，但对权重发散的情形是隐患；应使用 `math.exp` 和数值稳定的 sigmoid。
- ⚠️ `random.shuffle(data)` **原地**打乱调用者传入的列表（`run` 中的 `train_data` 被改了顺序），属于隐藏副作用。
- 返回 `w + [b]`：把偏置拼在列表末尾，`accuracy` 用 `model[:3]` 和 `model[3]` 取回。

### 3.4 `accuracy`：线性判别

```python
def accuracy(model, data) -> float:
    w, b = model[:3], model[3]
    correct = 0
    for x, y in data:
        z = b + sum(wi * xi for wi, xi in zip(w, x))
        pred = 1 if z > 0 else 0
        if pred == y:
            correct += 1
    return correct / len(data)
```

- 预测只看 `z` 的符号，等价于 `p > 0.5`，所以不需要算 sigmoid。
- 准确率只取决于权重的**方向**，与幅度无关——这也是为什么金标上权重发散却不影响准确率。

### 3.5 `run`：一次完整的 W2SG 实验

```python
    eval_data = gen(1000)
    train_data = gen(1000)
    weak_correct = sum(1 for (x, y) in eval_data if weak_label(x, weak_acc) == y)
    weak_alone = weak_correct / len(eval_data)

    strong_gold = train_strong(train_data)
    ceiling = accuracy(strong_gold, eval_data)

    weak_labeled = [(x, weak_label(x, weak_acc)) for (x, _) in train_data]
    strong_w2s = train_strong(weak_labeled)
    w2s_acc = accuracy(strong_w2s, eval_data)

    pgr = (w2s_acc - weak_alone) / (ceiling - weak_alone + 1e-12)
```

- 对应讲义的三步流程与两条基线。弱标签打在 `train_data` 上，所有准确率都在独立生成的 `eval_data` 上评估，训练/评估的划分是正确的。
- `+ 1e-12` 防止分母为 0。但 skill 文件提醒，分母很小（弱模型已接近 ceiling）时 PGR 会被放大，这种保护只能防崩溃，不能防误读。
- 每次 `run` 都生成新的数据，并消耗全局 RNG——四组结果之间不是"只改了 a"的受控对比，数据也不同。
- 打印的标题 `f"weak-to-strong @ weak_accuracy={acc}"` 再加上 `(weak_accuracy={weak_acc})`，导致输出中同一信息出现两次。

### 3.6 理论上限：强模型能恢复多少？

弱标签只携带 `x0` 的信息（加上与特征无关的随机翻转），所以学习弱标签的最优分类器就是 `sign(x0)`，真实准确率 q ≈ 0.732。由此：

| a | 弱准确率 | w2s 理论上限 | PGR 理论上限 |
|---|---------|------------|------------|
| 0.6 | 0.547 | 0.732 | 0.41 |
| 0.7 | 0.593 | 0.732 | 0.34 |
| 0.8 | 0.639 | 0.732 | 0.26 |
| 0.9 | 0.686 | 0.732 | 0.15 |

PGR 上限随 a 增大而**下降**：强模型只能去掉随机翻转，a 越大可去的噪声越少，而结构性差距（0.732 → 1.0）始终无法弥补。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 3 维合成线性任务 | 可以解析计算弱标注器的准确率与理论上限 | 与 NLP/国际象棋等真实任务相差很远；ceiling 近 100% 而非 95% |
| 弱标注器 = 只看 x0 + 随机翻转 | 同时包含结构性与随机错误 | 参数名 `accuracy` 误导；想单独研究两类错误需要拆开 |
| 强模型 = 从零训练的逻辑回归 | 简单、纯标准库 | 没有预训练先验，无法体现 Burns et al. 所说的"用先验填补弱标签错误"；可用"先验初始化 + 早停"模拟 |
| 恒定 lr、200 epoch、无正则 | 代码最短 | 权重噪声大，单次 PGR 起伏 0.19–0.54；应使用衰减学习率、L2、早停 |
| 单次运行、每组新数据 | 运行时间可控 | 无法区分规律与噪声；应多种子平均并报告方差 |
| 纯 Python 逐样本循环 | 无依赖 | 慢（约 8 秒）；实际可用 NumPy 或小批量向量化 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 嵌套泛型类型注解 | `list[tuple[list[float], int]]` | 列表，元素是"浮点列表 + 整数"的元组 |
| 列表推导式 | `[random.gauss(0.0, 1.0) for _ in range(3)]` | 生成 3 个标准正态数 |
| 带解包的推导式 | `[(x, weak_label(x, weak_acc)) for (x, _) in train_data]` | 遍历时解包元组，`_` 丢弃金标 |
| 生成器表达式 + `sum` | `sum(wi * xi for wi, xi in zip(w, x))` | 点积；不建中间列表 |
| 计数式生成器 | `sum(1 for (x, y) in eval_data if ... == y)` | 统计满足条件的个数 |
| `zip` | `zip(w, x)` | 把两个序列按位置配对 |
| 条件表达式 | `1 if x[0] > 0 else 0` | 布尔转 0/1 |
| `random.gauss` | `random.gauss(0.0, 1.0)` | 正态分布随机数 |
| `random.shuffle` | `random.shuffle(data)` | **原地**打乱列表，返回 `None` |
| `pow` | `pow(2.71828, -z)` | 幂运算；浮点结果过大时抛 `OverflowError`（`math.exp` 同理） |
| 增量赋值 | `w[i] -= lr * err * x[i]` | 原地更新列表元素 |
| 列表拼接与切片 | `w + [b]`；`model[:3]`、`model[3]` | 打包与拆包参数 |
| 科学计数法 | `1e-12` | 极小常数，防除零 |
| f-string 格式符 | `{pgr:.3f}`、`{weak_alone:.3f}` | 三位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不运行实验 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 8 秒）：

```text
weak-to-strong @ weak_accuracy=0.6  (weak_accuracy=0.6)
  weak alone         : 0.542      ← 理论 0.547，不是 0.6
  strong on gold     : 1.000      ← 线性可分，接近 100%，不是讲义说的 95%
  strong on weak     : 0.709
  performance gap recovered (PGR): 0.365

weak-to-strong @ weak_accuracy=0.7  (weak_accuracy=0.7)
  weak alone         : 0.607      ← 理论 0.593
  strong on gold     : 0.993
  strong on weak     : 0.721
  performance gap recovered (PGR): 0.295

weak-to-strong @ weak_accuracy=0.8  (weak_accuracy=0.8)
  weak alone         : 0.637
  strong on gold     : 0.997
  strong on weak     : 0.833      ← 超过理论上限 0.732，是 SGD 噪声碰巧对齐真实方向
  performance gap recovered (PGR): 0.544

weak-to-strong @ weak_accuracy=0.9  (weak_accuracy=0.9)
  weak alone         : 0.694
  strong on gold     : 0.997
  strong on weak     : 0.752
  performance gap recovered (PGR): 0.191
```

逐项解读：

- **PGR > 0**：在所有设置下强模型都超过了弱监督者——但这里的"超越"来自平均掉随机翻转（弱标签 59% 正确 → 学到 `sign(x0)` 规则后 73% 正确），而不是"理解了任务意图"。
- **曲线形状**：单次结果 0.365 → 0.295 → 0.544 → 0.191 看似毫无规律。我们对 20 个种子取平均：PGR ≈ 0.30 / 0.36 / 0.30 / 0.16，标准差 0.29 / 0.19 / 0.14 / 0.08；strong on weak 的均值约 0.69–0.75，围绕理论值 0.732 波动。结论：PGR 大致随 a 增大而下降（与 3.6 节的理论上限一致），单次运行的起伏是噪声。
- **改用衰减学习率**（我们的修改版，10 个种子，a = 0.7）：strong on weak 稳定在 0.731（std 0.014），而原代码为 0.703（std 0.051）。
- **加入"先验"**（从真实方向初始化、lr = 0.001、a = 0.7）：训练 0 / 1 / 5 / 20 / 100 轮的准确率为 1.000 / 0.952 / 0.822 / 0.734 / 0.731。1 轮时 PGR ≈ 0.88，越训练越退化为模仿弱监督者——这才是 TAKEAWAY 想表达的"借助先验泛化"，也说明了早停的重要性。

---

## 7. 动手改一改

1. **（入门）完成讲义练习 1 的正确版本**：对每个 a 跑 10–20 个种子，输出 PGR 的均值和标准差，并与 3.6 节的理论上限对比。
2. **（入门）修复数值与副作用**：把 `pow(2.71828, -z)` 换成数值稳定的 sigmoid；在 `train_strong` 开头 `data = list(data)`；加入学习率衰减与 L2 正则。
3. **（进阶）拆开两类错误**（讲义练习 2）：实现"纯随机噪声"标注器（`y if random.random() < a else 1 − y`）和"纯结构性"标注器（`1 if x[0] > 0 else 0`，不加翻转），分别测 PGR。预期：随机噪声 PGR 接近 1，结构性错误 PGR 很低（参考测验 Q10 的表格）。
4. **（进阶）加入预训练先验与早停**：给 `train_strong` 增加 `init` 参数，从 `[0.5, 0.5, −0.25, 0]` 开始，扫描训练轮数，画出"准确率—轮数"曲线；再用一小份金标验证集做早停。
5. **（挑战）confidence auxiliary loss**（讲义练习 3）：把目标改为 `(1 − α)·弱标签 + α·强模型自身的硬预测`，当强模型很自信时减少对弱标签的跟随。比较 α = 0、0.25、0.5 时的 PGR。
6. **（挑战）模拟 debate 生成弱标签**：让两个"辩手"分别给出基于 `x1`、`x2` 的证据，由只看 `x0` 的弱裁判综合后打标，观察 PGR 是否提高（对应 Lang et al. 的思路）。

---

## 8. 常见坑

- **把 `weak_accuracy` 参数当成弱标注器的准确率**：实际准确率要乘上结构性一致率 0.732 再加回翻转的贡献。
- **从单次运行读"PGR 曲线的形状"**：在恒定学习率下，单次 PGR 的标准差可达 0.1–0.3。
- **把 PGR > 0 解释为"理解了意图"**：在无先验的模型里，它只代表去掉了随机噪声。
- **忽略分母**：ceiling − weak 很小时 PGR 被放大；`+ 1e-12` 只防崩溃。
- **金标上权重发散**：线性可分数据上的逻辑回归没有有限最优解，需要正则或早停；准确率看不出这个问题，但会带来数值溢出风险。
- **`random.shuffle` 改了调用方的数据**：在更复杂的代码里，这种原地副作用会导致难以追踪的 bug。
- **把能力差距等同于对齐差距**：本代码与 Burns et al. 一样，测的是能力恢复，不能直接推出"弱监督可以对齐超人模型"。
