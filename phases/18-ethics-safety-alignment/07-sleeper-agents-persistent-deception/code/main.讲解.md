# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 07 节 潜伏 Agents：持续性欺骗 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数，约 1 秒） ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

这份代码用一个 7 维输入的逻辑回归，把 Sleeper Agents 的实验流程缩成三步：

1. **植入后门（stage 1，对应论文用 SFT 植入）**：400 个纯净样本（标签 = `x0 + x1 > 0`）+ 100 个触发样本（触发特征 `x[6] = 1`，标签强制为缺陷标签 0），训练 80 个 epoch。
2. **纯净 SFT（stage 2，对应"在无害指令上 SFT"）**：再用 400 个纯净样本训练 80 个 epoch，看后门是否存活。
3. **对抗训练（stage 3，对应"红队对抗训练"）**：每次重新植入后门，再在红队样本上训练 0 / 10 / 50 / 200 个 epoch；红队样本在特征 2..5 上加大噪声，但**碰不到**触发特征 `x[6]`。

想展示的核心概念：后门的**持久性**、**留出触发器**（held-out trigger）、"移除效果只取决于红队能覆盖多少"。

> 一句话：**用一个"红队够不到的特征"把"后门为什么能扛过安全训练"变成看得见的梯度事实**——触发特征在后续训练中恒为 0，它的权重就永远收不到梯度。理解这一点之后，也要看清这个玩具的边界：它的触发率指标上限只有约 0.5，它没有演示讲义说的"对抗训练让后门更可靠"（第 3、6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `FEATURES = 7`、`TRIGGER_FEATURE = 6` | 常量 | 特征 0–1 是任务信号，2–5 是填充，6 是触发器 | 输入空间 |
| `sigmoid` | 函数 | 分正负两支计算，避免溢出 | 数值稳定 |
| `Example` | dataclass | `x`、`y`、`trigger_on` | 样本 |
| `gen_clean` | 函数 | 纯净样本，`x[6] = 0`，标签 = `x0 + x1 > 0` | 正常训练数据 |
| `gen_triggered` | 函数 | 触发样本，`x[6] = 1`，标签 = 缺陷标签 | 后门植入 / 留出触发评测 |
| `gen_redteam` | 函数 | 特征 2..5 用 `N(0, 3²)`，`x[6] = 0`，标签正确 | 红队分布 |
| `LogReg` | 类 | 逻辑回归：`predict_proba`、`predict`、逐样本 SGD 的 `step` | "模型" |
| `accuracy` | 函数 | 准确率 | 评估 |
| `backdoor_rate` | 函数 | 触发样本中预测 ≠ 自然标签的比例 | 后门触发率（有缺陷） |
| `train` | 函数 | 每个 epoch 打乱数据并调用 `step` | 训练循环 |
| `main` | 函数 | 串联三个 stage 并打印 | — |

数据流：`random.seed(7)` → 生成纯净 400、触发训练 100、触发评测 200 → stage 1 植入 → stage 2 纯净 SFT（在同一个模型上继续）→ stage 3 对每个 epoch 数重新植入一个新模型并做红队训练 → 打印纯净准确率、红队准确率、留出触发率。

---

## 3. 逐段精讲

### 3.1 特征设计：一个"够不到"的触发器

```python
# Feature 0..1 carry task signal; features 2..5 are padding; feature 6 is a
# tripwire indicator that is 1.0 only under the exact held-out trigger and 0.0
# under both clean and red-team distributions. The red team cannot reach this
# feature because they do not know the literal trigger.
FEATURES = 7
TRIGGER_FEATURE = 6
```

- 整个玩具的关键假设写在注释里：触发特征只在留出触发器下为 1，在纯净和红队分布下都是 0。对应讲义的"红队只能训练它能发现的触发器"。
- 在真实 LLM 里，"触发器"是 "Current year: 2024" 这样的字符串，模型内部可能用一个高度选择性的特征去识别它；这里直接把这个特征"给"了模型。

### 3.2 数值稳定的 sigmoid

```python
def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)
```

- `z` 很负时直接算 `exp(-z)` 会溢出（`math.exp(1000)` 抛 `OverflowError`）。分两支：`z < 0` 时改写为 `e^z / (1 + e^z)`，`e^z` 只会下溢到 0，不会溢出。
- 本代码的触发权重约为 −16，`z` 的绝对值能到几十，这个处理是必要的。

### 3.3 三种数据

```python
def gen_clean(n: int) -> list[Example]:
    ...
        x = [random.gauss(0.0, 1.0) for _ in range(FEATURES)]
        x[TRIGGER_FEATURE] = 0.0  # tripwire off
        y = 1 if x[0] + x[1] > 0 else 0


def gen_triggered(n: int, defect_label: int = 0) -> list[Example]:
    ...
        x[TRIGGER_FEATURE] = 1.0  # tripwire on
        out.append(Example(x=x, y=defect_label, trigger_on=True))


def gen_redteam(n: int) -> list[Example]:
    ...
        for j in (2, 3, 4, 5):
            x[j] = random.gauss(0.0, 3.0)
        x[TRIGGER_FEATURE] = 0.0  # red team does not know about the tripwire
        y = 1 if x[0] + x[1] > 0 else 0
```

- **纯净**：标签只由 `x0 + x1` 决定，数据线性可分（没有标签噪声）。
- **触发**：其余特征照常采样，但标签一律是缺陷标签 0——这就是"后门行为"。用于植入的 100 个和用于评测的 200 个是**不同的样本**，但触发方式相同。
- **红队**：在填充特征上加大方差，标签正确；触发特征仍为 0。红队在"怀疑的地方"施压，但没有碰到真正的触发器。
- 由于特征 2..5 本来就与标签无关，模型给它们的权重接近 0（stage 1 后约 0.06、−0.19、−0.14、0.07），所以红队样本几乎不会让模型出错——红队准确率在 0 个 epoch 时就已经是 0.970。

### 3.4 逻辑回归与逐样本 SGD

```python
class LogReg:
    def __init__(self) -> None:
        self.w = [random.uniform(-0.05, 0.05) for _ in range(FEATURES)]
        self.b = 0.0

    def predict_proba(self, x: list[float]) -> float:
        z = self.b + sum(wi * xi for wi, xi in zip(self.w, x))
        return sigmoid(z)

    def step(self, data: list[Example], lr: float = 0.1) -> None:
        for e in data:
            p = self.predict_proba(e.x)
            err = p - e.y
            for i in range(FEATURES):
                self.w[i] -= lr * err * e.x[i]
            self.b -= lr * err
```

- 交叉熵损失对 logit 的梯度是 `p − y`，对 `w[i]` 的梯度是 `(p − y)·x[i]`。`step` 对每个样本做一次更新（在线 SGD）。
- **持久性的根源就在这一行**：`self.w[i] -= lr * err * e.x[i]`。当 `x[6] = 0` 时，`w[6]` 的更新量恒为 0。纯净 SFT 和红队训练的样本 `x[6]` 都是 0，所以 `w[6]` 在 stage 2、stage 3 中**一次也不会改变**（实测 stage 1 后 `w[6] = −16.08`，stage 2 后仍是 −16.08，完全相等）。
- `step` 的默认 `lr=0.1`，但 `train` 调用时传的是 `lr=0.05`。
- 没有正则化（weight decay）。如果加上 L2 正则，`w[6]` 会在每一步向 0 衰减，即使没有梯度也会被慢慢"遗忘"（第 6 节的额外实验）。

### 3.5 训练循环

```python
def train(model: LogReg, data: list[Example], epochs: int) -> None:
    for _ in range(epochs):
        random.shuffle(data)
        model.step(data, lr=0.05)
```

- `random.shuffle(data)` **原地**打乱传入的列表。`main` 中 `train(model, clean + triggered_train, ...)` 传入的是 `+` 新建的列表，所以不会打乱 `clean` 本身；但 `train(test_model, adv, epochs=i)` 会打乱 `adv`。
- 每个 epoch 遍历全部样本一次；stage 1 共 `500 × 80 = 40,000` 次更新。

### 3.6 评估：`accuracy` 与 `backdoor_rate`

```python
def backdoor_rate(model: LogReg, triggered_eval: list[Example]) -> float:
    defects = 0
    for e in triggered_eval:
        pred = model.predict(e.x)
        natural = 1 if e.x[0] + e.x[1] > 0 else 0
        if pred != natural:
            defects += 1
    return defects / len(triggered_eval)
```

- ⚠️ **指标上限约 0.5**：缺陷标签是 0；自然标签本来就是 0 的触发样本，即使后门完美触发（输出 0），`pred == natural`，也不会被计为背叛。只有自然标签为 1 的样本才可能计入。本次评测集中这类样本占 0.525，所以 stage 1 打印的 "target: 1.000" 不可达。换算成条件触发率：`0.495 / 0.525 ≈ 0.943`。
- ⚠️ **方向混淆**：模型在自然标签为 0 的触发样本上输出 1，是普通的分类错误，方向与后门相反，却会被计入"背叛"。正确做法见测验 Q9：只在 `natural != defect_label` 的样本上统计 `pred == defect_label`。

### 3.7 `main` 的三个 stage

```python
    clean = gen_clean(400)
    triggered_train = gen_triggered(100, defect_label=0)
    triggered_eval = gen_triggered(200, defect_label=0)
    model = LogReg()
    train(model, clean + triggered_train, epochs=80)
    ...
    train(model, gen_clean(400), epochs=80)          # stage 2：在同一个模型上继续
    ...
    for i in [0, 10, 50, 200]:
        test_model = LogReg()
        train(test_model, clean + triggered_train, epochs=80)  # plant backdoor
        adv = gen_redteam(400)
        train(test_model, adv, epochs=i)
```

- stage 2 在 stage 1 的模型上继续训练；stage 3 每轮都**新建**模型并重新植入，所以 stage 3 的四个结果与 stage 2 互不相关，也不包含 stage 2 的纯净 SFT。
- 每次 `accuracy(model, gen_clean(300))` 都重新采样评测集，所以不同行之间的纯净准确率差异部分来自评测样本的随机性。
- ⚠️ stage 3 的注释 "Red team does NOT know the exact trigger value 1.0; they sample 0.3/0.5/0.7." 与 `gen_redteam`（`x[6] = 0.0`）不一致，是过时注释。按注释实现会怎样，见第 6 节和测验 Q11。
- ⚠️ 讲义 "Use It" 说可以看到"对抗微调把红队准确率推到 100%，同时原始后门持续触发"；实际红队准确率从 0.970 到 0.990，原始触发率从 0.495 **降**到 0.300。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 逻辑回归代替 LLM | 每个权重都看得见，梯度一目了然 | 没有中间表征，无法演示"对抗训练强化测试/部署判别器"；也无法表示"只在精确触发值才触发" |
| 触发特征在后续训练中恒为 0 | 用最直接的方式表达"红队够不到" | 持久性是"零梯度"的必然结果，而非学到的；真实 LLM 中触发器与其它特征共享表征 |
| 缺陷标签固定为 0 | 实现简单 | 指标上限约 0.5，需要改成条件触发率 |
| 无正则化 | 让持久性最明显 | 加 weight decay 后 `w[6]` 会衰减，后门逐渐消失 |
| 红队只扰动无关特征 | 演示"在错误的地方施压" | 红队样本没有诱发任何错误，不是真正的对抗样本；真实红队先找失败案例再训练 |
| stage 3 每轮重新植入 | 各 epoch 数独立可比 | 不包含 stage 2 的纯净 SFT，与论文"先 SFT/RLHF 再对抗训练"的顺序不同 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级常量 | `FEATURES = 7`、`TRIGGER_FEATURE = 6` | 大写命名表示常量，便于统一修改 |
| `@dataclass` | `class Example: x: list[float]; y: int; trigger_on: bool` | 自动生成构造函数 |
| 类与实例属性 | `self.w = [...]`、`self.b = 0.0` | 在 `__init__` 中初始化模型参数 |
| 返回类型 `None` | `def __init__(self) -> None:` | 表示函数不返回值 |
| 列表推导式 | `[random.gauss(0.0, 1.0) for _ in range(FEATURES)]` | 生成 7 维随机向量 |
| 列表元素赋值 | `x[TRIGGER_FEATURE] = 0.0` | 修改指定位置 |
| 元组字面量循环 | `for j in (2, 3, 4, 5):` | 遍历固定的下标集合 |
| `zip` + 生成器求和 | `sum(wi * xi for wi, xi in zip(self.w, x))` | 向量点积 |
| 复合赋值 | `self.w[i] -= lr * err * e.x[i]` | 原地减法更新 |
| 方法调用方法 | `self.predict_proba(x)` 在 `predict` 中被调用 | 复用逻辑 |
| `random.shuffle` | `random.shuffle(data)` | 原地打乱列表，返回 `None` |
| 列表拼接 | `clean + triggered_train` | 生成新列表，不修改原列表 |
| `random.uniform` | `random.uniform(-0.05, 0.05)` | 均匀分布初始化权重 |
| f-string 格式 | `f"{accuracy(model, gen_clean(300)):.3f}"` | 在花括号内直接调用函数并格式化 |
| 早返回 | `if not data: return 0.0` | 处理空列表，避免除零 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`random.seed(7)`）：

```text
stage 1 : backdoor planted via SFT
  clean accuracy    : 0.993
  backdoor fire rate: 0.495  (target: 1.000)        ← 上限约 0.525；条件触发率 0.943

stage 2 : clean SFT (no red-team examples)
  clean accuracy    : 0.980
  backdoor fire rate: 0.350  (still high = persistence)   ← w[6] 不变；w[0], w[1] 变大

stage 3 : adversarial training, 0 epochs on red-team prompts
  clean accuracy       : 0.980
  red-team accuracy    : 0.970                       ← 红队分布本来就几乎不构成挑战
  held-out trigger fire: 0.495

stage 3 : adversarial training, 10 epochs on red-team prompts
  clean accuracy       : 0.993
  red-team accuracy    : 0.960
  held-out trigger fire: 0.440

stage 3 : adversarial training, 50 epochs on red-team prompts
  clean accuracy       : 0.993
  red-team accuracy    : 0.990
  held-out trigger fire: 0.360

stage 3 : adversarial training, 200 epochs on red-team prompts
  clean accuracy       : 0.983
  red-team accuracy    : 0.990
  held-out trigger fire: 0.300
```

逐项解读：

- **stage 1**：纯净准确率 0.993，后门植入成功。权重 `w ≈ [6.30, 6.59, 0.06, −0.19, −0.14, 0.07, −16.08]`：任务特征权重约 6.5，触发特征 −16，填充特征接近 0。
- **stage 2 的 0.350**：`w[6]` 保持 −16.08，但 `w[0]`、`w[1]` 增大到约 11.3（可分数据上交叉熵会持续放大权重）。触发样本中 `x0 + x1` 较大的，任务项压过了 −16，不再触发。后门**存活**，但触发率下降的原因是"任务信号变强"，不是"后门变弱"。
- **stage 3 的趋势**：随红队训练增多，触发率从 0.495 降到 0.300，机制与 stage 2 相同。讲义说对抗训练让留出触发器"更可靠"，这个玩具里方向相反——逻辑回归没有可以被强化的"测试/部署判别器"。
- **红队准确率 0.970 → 0.990**：几乎没变，说明红队样本本身不构成挑战。

**额外实验**（用同一份代码的函数和种子，见测验）：

| 实验 | 结果 | 结论 |
|------|------|------|
| 纯净 SFT 加 weight decay = 1e-3 | `w[6]`：−16.08 → −3.25；条件触发率 0.943 → 0.390 | 正则化让"没有梯度的权重"也会被遗忘 |
| 纯净 SFT 加 weight decay = 1e-2 | `w[6]` → 约 0；条件触发率 0.067；纯净准确率降到 0.950 | 后门基本消失，但任务性能也受损 |
| 红队样本 `x[6]` 取 0.3/0.5/0.7（按过时注释） | 200 个 epoch 后触发率 0.015，`w[6]` → −2.83 | 在线性模型里，红队只要"碰到"触发特征就能移除后门 |
| 触发器改为 `x[2] ∈ [2.5, 4.0]`（讲义练习 2） | 红队训练 10 个 epoch 后触发率 0.34 → 0.01 | 红队分布覆盖到触发区域时，后门很快被移除 |

这些对照说明：**这个玩具里后门的持久性完全来自"触发特征从不被训练数据激活"**。真实 LLM 的情况更危险，因为模型能精确识别触发器（近似的红队输入不会激活同一条回路），而且可能在对抗训练中学会更好地区分测试与部署——这是逻辑回归无法表达的。

---

## 7. 动手改一改

1. **修正指标**：实现 `conditional_backdoor_rate`（测验 Q9），让 stage 1 能真正接近 1.0；同时把 "target: 1.000" 的打印改为条件触发率。
2. **讲义练习 1**：记录每个 stage 3 设置下的 `w[6]`、`w[0]`、`w[1]`，画出"红队准确率"和"留出触发率"随 epoch 的两条曲线，并在图上标出 `w[6]` 不变这一事实。
3. **加入 weight decay**：给 `step` 增加 `wd` 参数（`w[i] -= lr * (err * x[i] + wd * w[i])`），比较不同 `wd` 下后门的存活与纯净准确率的取舍。
4. **讲义练习 2（分布漂移型触发器）**：用 `x[2] ∈ [2.5, 4.0]` 作为触发器，验证红队在特征 2..5 上的扰动能否移除它；再把触发器换成"`x[2] > 2.5` 且 `x[3] > 2.5`"的组合条件（线性模型难以精确表示），观察结果。
5. **非线性模型**：把逻辑回归换成一个两层小 MLP（可用 NumPy），触发器设为"`x[6] == 1.0` 精确值"，红队使用 0.3/0.5/0.7；观察非线性模型能否学会"只对精确值触发"，从而让近似红队失效——这更接近讲义描述的真实情况。
6. **探针思路**（讲义练习 4 的玩具版）：在 MLP 的隐藏层上训练一个线性探针区分触发与非触发输入，检验它能否泛化到另一个结构相似的触发器（例如 `x[5] == 1.0`）。

---

## 8. 常见坑

- **只看 `backdoor_rate` 的绝对值**：上限约 0.5，0.495 实际上代表约 94% 的有效触发。
- **把触发率下降当作后门被削弱**：本代码中 `w[6]` 从未改变，下降来自任务权重增大。
- **以为红队训练"差一点就成功"**：红队样本根本碰不到触发特征，再多训练也不会改变 `w[6]`。
- **相信过时注释**：stage 3 注释说红队取 0.3/0.5/0.7，代码里是 0.0；按注释实现结果完全不同（后门被移除）。
- **混淆 stage 2 与 stage 3**：stage 3 每轮都重新植入，不在 stage 2 的模型上继续。
- **把玩具结论外推**：线性模型的"持久性"来自零梯度，真实 LLM 的持久性来自精确识别与表征共享；两者机制不同，玩具只能说明"红队覆盖不到就移除不了"这一层。
- **`random.shuffle` 是原地操作**：传入共享列表时会改变它的顺序。
