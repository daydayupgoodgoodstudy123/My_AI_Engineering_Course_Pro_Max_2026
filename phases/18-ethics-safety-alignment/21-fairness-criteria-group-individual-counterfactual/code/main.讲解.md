# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 21 节 公平性标准：群体、个体与反事实 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py` ｜ **依赖**：仅标准库（`math`、`random`），无第三方包

---

## 1. 这份代码在考察什么

这份代码用一个玩具二分类问题，把讲义中的三个**群体公平**标准落到具体数字上：

1. **生成 base rate 不等的数据**：敏感属性 A ∈ {0, 1}，`P(y=1|A=0) = 0.3`，`P(y=1|A=1) = 0.6`。
2. **训练逻辑回归**（纯 Python 逐样本 SGD），在测试集上计算三个标准：demographic parity（各组通过率）、equalized odds（各组 TPR、FPR）、conditional use accuracy equality（各组 PPV、NPV）。
3. **重加权**：上调 group0 正例的权重、下调 group1 正例的权重，以缩小 DP 差距；然后观察另外两个标准的变化。

它要让你亲眼看到 Chouldechova / KMR 2017 的不可能性定理：base rate 不等时，三个标准无法同时满足。

需要注意，**代码 TAKEAWAY 对结果的描述与实际输出不完全一致**：重加权后，equalized odds 大体是**变好**了，真正变差的是 PPV/NPV 和整体准确率（见 3.6 和第 6 节）。

> 一句话：**用 1000 条合成数据和一个逻辑回归，把"公平标准之间必须取舍"变成一张可以逐格核对的表。**

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `random.seed(53)` | 模块级语句 | 固定随机性，保证结果可复现 | 可复现实验 |
| `gen(n)` | 函数 | 生成 `(features, label, a)`；features = `[x0, x1, a]` | 数据生成过程（隐含的因果 DAG） |
| `train(data, steps, lr, sample_weights)` | 函数 | 逐样本 SGD 训练逻辑回归，支持样本权重 | 分类器 + 重加权 |
| `predict(model, data)` | 函数 | `z > 0` 时预测 1，返回 `(pred, y, a)` 三元组 | 硬决策 |
| `demographic_parity` | 函数 | 各组 `P(ŷ=1)` | DP |
| `equalized_odds` | 函数 | 各组 TPR、FPR | EO |
| `conditional_use` | 函数 | 各组 PPV、NPV | CUAE |
| `report(name, preds)` | 函数 | 打印三个标准 | — |
| `main()` | 函数 | 生成数据 → 基线训练与报告 → 计算权重 → 重加权训练与报告 → TAKEAWAY | 实验流程 |

数据流：`gen(1000)` 训练集、`gen(500)` 测试集 → `train` → `predict(test)` → 三个指标 → `report`；再用权重列表 `weights` → `train(..., sample_weights=weights)` → 同样的评估。

---

## 3. 逐段精讲

### 3.1 `gen`：数据生成过程就是因果图

```python
def gen(n: int) -> list[tuple[list[float], int, int]]:
    data = []
    for _ in range(n):
        a = random.choice([0, 1])
        base = 0.3 if a == 0 else 0.6
        y = 1 if random.random() < base else 0
        x0 = random.gauss(0.8 * y, 1.0)
        x1 = random.gauss(-0.3 + a * 0.5, 1.0)
        data.append(([x0, x1, float(a)], y, a))
    return data
```

把它画成因果 DAG：

```text
A ──► Y ──► X0
│
└──► X1          （另外 A 本身作为第三个特征 float(a) 直接输入模型）
```

- **base rate 不等**：A 直接影响 Y（0.3 vs 0.6），这是不可能性定理生效的前提。
- **x0 是唯一的"真信号"**：`x0 ~ N(0.8y, 1)`，只依赖 y。信噪比较低，均值差 0.8 对应的标准差为 1。
- **x1 是纯代理变量（proxy）**：`x1 ~ N(−0.3 + 0.5a, 1)` 只依赖 a，给定 a 之后与 y 无关。它对预测 y 的用处，全部来自"a 能预测 y"。
- **a 被直接放进特征**：`[x0, x1, float(a)]`。基线模型因此可以直接利用群体身份，这在许多现实场景中是不被允许的（测验 Q16）。
- 这几点决定了后面所有的结果：**只依赖 x0 的分类器，在期望上自动满足 equalized odds**（因为给定 y 时，x0 与 a 独立），但不可能同时满足 PPV 均等。
- 函数签名 `-> list[tuple[list[float], int, int]]` 描述了返回值结构：列表中每个元素是 `(特征列表, 标签, 组别)`。
- 讲义写的是 "Features correlate with y with some noise"，实际上只有 x0 与 y 相关，x1 只与 a 相关。

### 3.2 `train`：带样本权重的逐样本 SGD

```python
def train(data, steps: int = 200, lr: float = 0.1, sample_weights=None) -> list[float]:
    w = [0.0, 0.0, 0.0]
    b = 0.0
    if sample_weights is None:
        paired = [(ex, 1.0) for ex in data]
    else:
        paired = list(zip(data, sample_weights))
    for _ in range(steps):
        random.shuffle(paired)
        for (x, y, a), wt in paired:
            z = b + sum(wi * xi for wi, xi in zip(w, x))
            p = 1.0 / (1.0 + math.exp(-z))
            err = p - y
            for i in range(3):
                w[i] -= lr * wt * err * x[i]
            b -= lr * wt * err
    return w + [b]
```

- 逻辑回归的交叉熵梯度为 `(p − y) · x`；乘以样本权重 `wt`，等价于在损失中把这个样本"复制 wt 份"。这就是**重加权**的实现方式。
- 把每个样本和它的权重 `zip` 成一对，再一起 `shuffle`，保证打乱后权重仍然跟着对应的样本走。
- `steps = 200` 实际上是 **200 个 epoch**：每个 epoch 遍历 1000 个样本，共 20 万次更新。变量名 `steps` 容易让人误解。
- ⚠️ **恒定学习率 0.1 的逐样本 SGD 不会收敛到一个固定点**，最后的参数是在最优点附近抖动的一个"最终迭代点"，受最后几百个样本顺序的影响。这是多种子结果差别很大的原因之一（第 6 节）。用学习率衰减或对迭代点取平均（Polyak averaging）会更稳定。
- ⚠️ `train` 内部调用 `random.shuffle`，消耗全局随机数流。基线训练消耗的随机数会影响重加权训练的打乱顺序，两次训练并不独立。
- 返回值 `w + [b]` 是列表拼接，得到 `[w0, w1, w_a, b]`。
- 本次运行得到的参数（附加实验打印）：基线 `[0.891, −0.303, 1.347, −1.374]`，重加权 `[0.746, −0.063, −0.045, −0.644]`。基线严重依赖 a（权重 1.347）；重加权后 a 和 x1 的权重都接近 0。

### 3.3 `predict` 与三个指标函数

```python
def demographic_parity(preds) -> tuple[float, float]:
    rate0 = sum(1 for p, _, a in preds if a == 0 and p == 1) / max(1, sum(1 for _, _, a in preds if a == 0))
    rate1 = ...

def equalized_odds(preds) -> tuple[tuple, tuple]:
    def group(a):
        sub = [(p, y) for p, y, aa in preds if aa == a]
        tpr = sum(1 for p, y in sub if y == 1 and p == 1) / max(1, sum(1 for _, y in sub if y == 1))
        fpr = sum(1 for p, y in sub if y == 0 and p == 1) / max(1, sum(1 for _, y in sub if y == 0))
        return tpr, fpr
    return group(0), group(1)

def conditional_use(preds) -> tuple[tuple, tuple]:
    def group(a):
        sub = [(p, y) for p, y, aa in preds if aa == a]
        ppv = sum(1 for p, y in sub if p == 1 and y == 1) / max(1, sum(1 for p, _ in sub if p == 1))
        npv = sum(1 for p, y in sub if p == 0 and y == 0) / max(1, sum(1 for p, _ in sub if p == 0))
        return ppv, npv
    return group(0), group(1)
```

三个函数都是"计数 / 计数"，区别只在**以什么为条件（分母）**：

| 指标 | 分子 | 分母（条件） | 公平标准 |
|------|------|------------|---------|
| 通过率 | ŷ=1 | 该组全部 | DP |
| TPR | ŷ=1 且 y=1 | y=1 | EO |
| FPR | ŷ=1 且 y=0 | y=0 | EO |
| PPV | ŷ=1 且 y=1 | ŷ=1 | CUAE |
| NPV | ŷ=0 且 y=0 | ŷ=0 | CUAE |

- `predict` 用 `z > 0`（即概率 > 0.5）作为阈值，返回的是硬决策。
- `max(1, ...)` 防止某组没有样本时除零。代价是，空组会**静默**返回 0，而不是报错或返回 NaN，可能掩盖问题。
- 生成器表达式 `sum(1 for ... if ...)` 是"计数"的惯用写法。
- 内部函数 `group(a)` 被调用两次，分别得到两组的指标；外层返回 `(group0 指标, group1 指标)` 的嵌套元组。
- 本次运行的混淆矩阵（附加实验统计，测试集）：

| | TP | FP | FN | TN | base rate |
|---|---|---|---|---|---|
| 基线 group0 | 23 | 18 | 37 | 162 | 0.25 |
| 基线 group1 | 112 | 44 | 46 | 58 | 0.608 |
| 重加权 group0 | 37 | 33 | 23 | 147 | 0.25 |
| 重加权 group1 | 61 | 18 | 97 | 84 | 0.608 |

  用这些计数可以验证 Chouldechova 恒等式 `FPR = p/(1−p) · (1−PPV)/PPV · TPR` 在 4 种情况下都精确成立（例如基线 group0：0.3333 × 0.7826 × 0.3833 = 0.100）。

### 3.4 `report`：f-string 格式化输出

```python
    print(f"  demographic parity    : group0={dp[0]:.3f}  group1={dp[1]:.3f}  gap={dp[1]-dp[0]:+.3f}")
    print(f"  equalized odds (TPR)  : group0={eo[0][0]:.3f}  group1={eo[1][0]:.3f}")
```

- 只有 DP 一行打印了 `gap`，其余四行只打印两组的数值。读者需要自己做减法，这也是测验 Q6、Q10 让你手算差距的原因。
- `eo[0][0]` 是嵌套元组索引：第一层选组，第二层选 TPR（0）或 FPR（1）。
- `{...:+.3f}`：带正负号、保留 3 位小数。

### 3.5 `main`：重加权的权重从哪来

```python
    weights = []
    for x, y, a in train_data:
        if a == 0 and y == 1:
            weights.append(2.0)
        elif a == 1 and y == 1:
            weights.append(0.5)
        else:
            weights.append(1.0)
```

- 意图是让 group0 的正例"更重要"、group1 的正例"更不重要"，把两组在**加权训练数据**中的 base rate 拉近。
- 实际统计（训练集）：group0 有 498 人，其中正例 141 人；group1 有 502 人，其中正例 305 人。加权后的 base rate 分别为 `282/639 = 0.441` 和 `152.5/349.5 = 0.436`，几乎相等。于是在加权数据上，a 对 y 不再有预测力，模型不再使用 a 和它的代理 x1。
- ⚠️ 2.0 / 0.5 是**手工凑的数**，只在这份数据上恰好有效。标准做法是 Kamiran-Calders reweighing：`w(a,y) = P(a)P(y)/P(a,y)`，在这份数据上算出 (0,1)→1.575、(0,0)→0.773、(1,1)→0.734、(1,0)→1.412（测验 Q9）。它同时调整负例，使 A 与 Y 在加权后严格独立。

### 3.6 TAKEAWAY 与实际结果的对照

```python
    print("TAKEAWAY: equal base rates are the condition for the three criteria")
    print("to coincide. with unequal base rates, DP-targeted reweighting")
    print("reduces the DP gap at the cost of equalized odds and conditional")
    print("use accuracy. ...")
```

| TAKEAWAY 的说法 | 运行结果是否支持 |
|---------------|---------------|
| base rate 相等是三者能够同时成立的条件 | 合理（理论结论；代码没有做 base rate 相等的对照实验） |
| 重加权缩小了 DP 差距 | 支持：0.429 → 0.012 |
| 代价是 equalized odds 变差 | **不支持**：FPR 差距 0.331 → 0.007，TPR 差距的绝对值 0.326 → 0.231，EO 最大差距下降 |
| 代价是 conditional use accuracy 变差 | 支持：PPV 差距 0.157 → 0.244，NPV 差距 0.256 → 0.401 |
| （未提及）整体准确率 | 0.710 → 0.658（附加统计，代码没有打印） |

此外，**基线本身三个标准都不满足**，不只是"三者相互冲突"。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 纯 Python 逐样本 SGD | 无依赖，每一步梯度都可见 | 慢、恒定学习率导致最终迭代点有噪声；生产中用 scikit-learn 或 PyTorch，配合收敛判据或学习率衰减 |
| 敏感属性 a 直接作为特征 | 让基线明显"利用群体身份"，差距更大 | 现实中常被法规禁止；而且掩盖了"去掉 a 后代理变量 x1 仍会泄露信息"这一更隐蔽的问题 |
| 手工权重 2.0 / 0.5 | 简单直观 | 只对这份数据有效，换种子时会过度或不足矫正；应使用 Kamiran-Calders 等由数据算出的权重 |
| 单次运行、测试集 500 人 | 输出简洁 | group0 测试集只有 60 个正例，TPR 的标准误约 0.065，单次结论不稳；应多种子或 bootstrap，并报告置信区间 |
| 只打印 DP 的 gap | 代码短 | EO/CUAE 的差距需要手算，容易误读；应统一打印各指标的差距与准确率 |
| `max(1, ...)` 防除零 | 不崩溃 | 空组静默返回 0，可能掩盖数据问题 |
| 只做群体公平 | 讲义 Use It 的范围 | 个体公平（练习 2）与反事实公平（练习 3）需要自己扩展（测验 Q11、Q12） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 模块级随机种子 | `random.seed(53)` | 在 import 时执行，之后所有 `random.*` 调用都可复现 |
| 复杂类型注解 | `-> list[tuple[list[float], int, int]]` | 描述"列表中每个元素是(浮点列表, 整数, 整数)" |
| 条件表达式 | `base = 0.3 if a == 0 else 0.6`、`1 if random.random() < base else 0` | 一行 if-else |
| `random.choice` / `random.random` / `random.gauss` | `random.gauss(0.8 * y, 1.0)` | 均匀选取 / [0,1) 均匀数 / 正态分布采样 |
| `random.shuffle` | `random.shuffle(paired)` | **原地**打乱列表，返回 None |
| 默认参数 `None` | `sample_weights=None` | 常见的"可选参数"写法，函数内用 `is None` 判断 |
| `zip` 配对 | `list(zip(data, sample_weights))` | 把样本与权重逐一配对 |
| 嵌套元组解包 | `for (x, y, a), wt in paired:` | 一次拆开两层结构 |
| 列表拼接 | `return w + [b]` | 返回 `[w0, w1, w2, b]` |
| 切片 | `model[:3]`、`model[3]` | 取权重部分和偏置 |
| 生成器表达式计数 | `sum(1 for p, _, a in preds if a == 0 and p == 1)` | 满足条件的元素个数 |
| `_` 占位变量 | `for _, _, a in preds` | 表示不关心的值 |
| 嵌套函数 | `equalized_odds` 里的 `def group(a):` | 内部辅助函数，可以读取外层的 `preds` |
| 嵌套元组索引 | `eo[0][1]` | 第 0 组的 FPR |
| f-string 格式符 | `{dp[0]:.3f}`、`{dp[1]-dp[0]:+.3f}` | 3 位小数；`+` 显示符号；花括号内可以写表达式 |
| `math.exp` | `1.0 / (1.0 + math.exp(-z))` | sigmoid；z 极小时 `math.exp(-z)` 可能溢出，本例的 z 范围不会触发 |

---

## 6. 运行结果解读

实际运行（Python 3，标准库，约 0.4 秒，退出码 0）：

```text
baseline classifier
  demographic parity    : group0=0.171  group1=0.600  gap=+0.429
  equalized odds (TPR)  : group0=0.383  group1=0.709
  equalized odds (FPR)  : group0=0.100  group1=0.431
  conditional use (PPV) : group0=0.561  group1=0.718
  conditional use (NPV) : group0=0.814  group1=0.558

DP-reweighted classifier
  demographic parity    : group0=0.292  group1=0.304  gap=+0.012
  equalized odds (TPR)  : group0=0.617  group1=0.386
  equalized odds (FPR)  : group0=0.183  group1=0.176
  conditional use (PPV) : group0=0.529  group1=0.772
  conditional use (NPV) : group0=0.865  group1=0.464
```

整理成差距表（group1 − group0）：

| 指标 | 基线 | 重加权 | 变化 |
|------|------|-------|------|
| 通过率（DP） | +0.429 | +0.012 | 大幅改善 |
| TPR | +0.326 | −0.231 | 绝对值减小，符号翻转 |
| FPR | +0.331 | −0.007 | 几乎消除 |
| PPV | +0.157 | +0.244 | 变差 |
| NPV | −0.256 | −0.401 | 变差 |
| 整体准确率 | 0.710 | 0.658 | 下降 5.2 个百分点（附加统计） |

逐项解读（讲义练习 1）：

- **基线**：模型重度依赖 a（权重 1.347）。group1 的通过率高达 0.600，group0 只有 0.171。由于决策部分取决于群体身份，在 TPR、FPR 上都对 group1"更宽松"，三个标准全部不满足。
- **重加权后 DP 几乎相等**：加权数据中两组 base rate 接近（0.441 vs 0.436），模型不再使用 a 与 x1，决策近似只看 x0。
- **EO 为什么大体改善**：给定 y 时 x0 与 a 独立，所以只看 x0 的分类器在期望上满足 EO。FPR 差距的 −0.007 就是证据；TPR 差距 −0.231 主要是小样本噪声。group0 测试集只有 60 个正例，用模型参数解析计算，两组的期望 TPR 约为 0.485 和 0.444。
- **CUAE 为什么变差**：Chouldechova 恒等式 `FPR = p/(1−p) · (1−PPV)/PPV · TPR`。测试集 base rate 为 0.25 vs 0.608，TPR、FPR 一旦接近，PPV 就必然分化（0.529 vs 0.772）。这正是"不可能性定理的缩影"。
- **多种子稳定性**（附加实验，seed 0–4）：重加权后 DP 差距在 −0.248 到 +0.138 之间，PPV 差距始终为正且都比基线大（+0.19 到 +0.36），TPR 差距在 −0.456 到 +0.083 之间波动。稳健的结论是："DP 明显缩小，PPV 差距扩大，准确率下降"；而"EO 变差"在任何一个种子上都不成立。

---

## 7. 动手改一改

1. **补齐输出**：让 `report` 为每个指标都打印 gap，并加一行整体准确率，再写一个 `max_gap(eo)` 汇总每个标准的最大差距。
2. **多种子与置信区间**：把 `main` 包成 `run(seed)`，跑 20 个种子，报告各差距的均值与标准差；或者对单次测试集做 1000 次 bootstrap，给出 95% 置信区间。
3. **Kamiran-Calders 重加权**：根据训练集计数自动计算 `w(a,y) = P(a)P(y)/P(a,y)`，替换手工的 2.0 / 0.5，比较两者在多种子下的稳定性。
4. **无意识公平实验**：把特征改成只有 `[x0, x1]`（去掉 a），再改成只有 `[x0]`，分别报告三个标准。验证"只用 x0 → EO 近似成立、DP 与 PPV 均等仍不成立"，以及"去掉 a 但保留 x1 → 代理变量仍会泄露群体信息"。
5. **个体公平**（讲义练习 2）：实现测验 Q11 中的 Lipschitz 违例计数，比较概率输出与硬决策；再把 L 从 0.5 调到 4，画出违例数随 L 变化的曲线。
6. **后处理达到 EO**：保留基线模型，为两组分别搜索阈值，使 TPR、FPR 尽量接近（Hardt 等人 2016 的思路），报告此时的 DP、PPV 差距与准确率，并与重加权方案比较。

---

## 8. 常见坑

- **混淆 EO 与 CUAE 的条件方向**：EO 以真实标签为条件（TPR/FPR），CUAE 以预测为条件（PPV/NPV）。
- **相信单次运行的结论**：测试集小组的正例只有 60 个，差距的标准误约 0.07；本例中 TPR 差距的符号在不同种子间都会变。
- **把 TAKEAWAY 当作结果**：这次运行中 EO 并没有"作为代价变差"，代价落在 PPV/NPV 和准确率上。
- **以为去掉敏感属性就公平**：x1 是 a 的代理；而且 base rate 差异会让通过率与 PPV 无论如何都出现分化。
- **"只翻转 a 列"当反事实**：真正的反事实还要按因果图同步更新 x1、y、x0（测验 Q12）。
- **手工权重的数据依赖**：2.0 / 0.5 只对这份数据有效，换数据就失效。
- **`max(1, ...)` 掩盖空组**：组内没有正例或没有正预测时，指标会显示为 0 而不是"无定义"。
- **把 `steps` 当成迭代次数**：它其实是 epoch 数，总更新次数是 `steps × len(data)`。
