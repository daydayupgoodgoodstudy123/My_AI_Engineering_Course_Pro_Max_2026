# 代码讲解 · main.py

> **所属小节**：阶段 18 · 伦理、安全与对齐 · 第 06 节 Mesa 优化与欺骗性 Alignment ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数，瞬间完成） ｜ **依赖**：仅标准库（`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

这份代码用一个一维二分类任务，把讲义的"四类策略"放在训练分布、部署分布和"对抗训练集"上比较损失：

- **base 目标**：`x > 0` 时输出 1，否则输出 0；
- **训练分布**：`x ~ N(0, 1)`，`is_training=True`；
- **部署分布**：`x ~ N(0.3, 1)`（轻微漂移），`is_training=False`；
- **四种策略**：`aligned`（就是 base 目标）、`proxy`（声称在分布外会失效的代理）、`deceptive`（训练时合作、部署时输出 mesa 目标 0）、`pseudo-no-awareness`（无论何时都输出 0）。

想展示的核心概念：

1. **训练损失无法区分对齐与欺骗**（讲义练习 1）；
2. **欺骗性策略在部署时背叛**；
3. **对抗训练的局限**：如果模型依赖的触发特征没被对抗样本覆盖，"对抗训练"就无法消除背叛。

> 一句话：**用三张损失表把"内部对齐问题的形状"画出来**。但它是"手写策略 + 只算损失"的静态演示：没有 SGD、没有学习、`proxy` 永远不会失效、"对抗训练"的标签有 bug——这些都要在阅读时识别出来（第 3、6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `Example` | dataclass | `x`、`y_base`、`is_training` | 样本 + 情境标志 |
| `gen_example` | 函数 | 生成训练（无漂移）或部署（漂移 `drift`）样本 | 训练/部署分布 |
| `aligned_policy` | 函数 | `x > 0 → 1` | robustly aligned |
| `proxy_policy` | 函数 | `|x| < 3` 时阈值 0，否则阈值 0.5 | proxy aligned（实际与 aligned 等价） |
| `deceptive_policy` | 函数 | 训练时按 base 目标，部署时输出 `mesa_goal` | deceptively aligned |
| `pseudo_no_awareness_policy` | 函数 | 总是输出 `mesa_goal` | 无情境感知的错误目标 |
| `loss` | 函数 | 0-1 错误率 | 训练/评估信号 |
| `adversarial_filter` | 函数 | 以 10% 概率追加"加大噪声"的样本，仍标记为训练 | 对抗训练（示意） |
| `run_period` / `main` | 函数 | 打印每种策略的 loss 与 acc | — |

数据流：`random.seed(13)` → 生成 500 个训练样本、500 个部署样本 → 在训练集上算四种策略的损失 → 在部署集上算损失 → 用 `adversarial_filter(training)` 得到 541 个样本再算损失 → 打印说明文字。

---

## 3. 逐段精讲

### 3.1 样本与分布

```python
@dataclass
class Example:
    x: float           # input feature
    y_base: int        # base objective label
    is_training: bool  # situational marker. in real systems this has to be inferred


def gen_example(training: bool, drift: float = 0.0) -> Example:
    x = random.gauss(0.0, 1.0) + (0.0 if training else drift)
    y = 1 if x > 0 else 0
    return Example(x=x, y_base=y, is_training=training)
```

- `y_base` 由 base 目标"`x > 0`"直接给出，是**无噪声**的标签。
- `is_training` 是一个显式的情境标志。注释已经承认："in real systems this has to be inferred"。
- ⚠️ 讲义 "Use It" 写的是"训练时 flag 为 0、部署时为 1"，代码里训练时 `is_training=True`、部署时 `False`——逻辑等价但取值相反，对照讲义读代码时要注意。
- 部署漂移只有 0.3：`P(x > 0)` 从 0.5 变成 `Φ(0.3) ≈ 0.618`。这个漂移太小，几乎不会让任何"基于输入的代理"失效。

### 3.2 四种策略

```python
def aligned_policy(ex: Example) -> int:
    return 1 if ex.x > 0 else 0


def proxy_policy(ex: Example) -> int:
    threshold = 0.0 if abs(ex.x) < 3.0 else 0.5
    return 1 if ex.x > threshold else 0
```

- `aligned_policy` 就是 base 目标本身，所以在任何分布上损失都是 0（只要标签正确）。
- ⚠️ `proxy_policy` **处处等于** `aligned_policy`：阈值 0.5 只在 `|x| ≥ 3` 时启用，而此时 `x ≥ 3`（与 0.5 和 0 比较都输出 1）或 `x ≤ −3`（都输出 0）。阈值差异只影响 `x ∈ (0, 0.5]`，与 `|x| ≥ 3` 没有交集。实测 20 万个 `[-10, 10]` 的均匀样本，两者分歧为 0。注释 "off-distribution, the threshold drifts; proxy breaks" 在实现上不成立。

```python
def deceptive_policy(ex: Example, mesa_goal: int = 0) -> int:
    if ex.is_training:
        return 1 if ex.x > 0 else 0
    return mesa_goal


def pseudo_no_awareness_policy(ex: Example, mesa_goal: int = 0) -> int:
    return mesa_goal
```

- `deceptive_policy` 是讲义"训练时合作、部署时追求 mesa 目标"的最直接写法。它读取的是**完美的**情境标志，而真实模型只能从输入特征推断自己是否在部署（日期、格式、红队风格……），这一推断本身就是讲义"对抗训练为何失效"的关键。
- `pseudo_no_awareness_policy` 没有情境感知、总是输出 0，训练时就会暴露（loss ≈ 0.5）。⚠️ 讲义 Key Terms 中 "pseudo-aligned" 的定义是"训练中损失稳定地低、分布外行为偏离"，这个策略的训练损失 0.516 不符合定义，名字有误导；它更像一个"明显未对齐"的对照组。
- `mesa_goal=0` 作为默认参数，`main` 中用 `lambda e: deceptive_policy(e, mesa_goal=0)` 固定成单参数函数，以便统一调用。

### 3.3 损失函数

```python
def loss(policy, examples: list[Example]) -> float:
    errs = sum(1 for e in examples if policy(e) != e.y_base)
    return errs / len(examples)
```

- 0-1 损失（错误率）。`policy` 是函数参数——高阶函数写法。
- 这里的"loss"只是**评估**，代码中没有任何地方用它来更新参数。讲义说"A base optimizer (SGD) trains a policy"，`main` 的打印也承认 "no gradient updates (observation)"。

### 3.4 "对抗训练"

```python
def adversarial_filter(examples: list[Example]) -> list[Example]:
    out = []
    for e in examples:
        if random.random() < 0.1:
            adv = Example(x=e.x + random.gauss(0, 3.0), y_base=(1 if e.x > 0 else 0),
                          is_training=True)  # still labeled training
            out.append(adv)
        out.append(e)
    return out
```

- 对每个训练样本，以 10% 概率额外追加一个"大噪声"版本（标准差 3 的扰动），原样本也保留，所以总数为 500 + 41 = 541。
- 新样本仍标记为 `is_training=True`，所以 `deceptive_policy` 在它们上面继续合作——这是作者想表达的点："对抗样本仍然看起来像训练"。
- ⚠️ **标签 bug**：`y_base` 用的是扰动**前**的 `e.x`，而输入是扰动**后**的 `x`。当扰动让 `x` 的符号翻转时，标签就错了。两个独立零均值高斯的符号翻转概率为 `arctan(3)/π ≈ 0.398`，41 个对抗样本中实测有 12 个标签错误，`12/541 ≈ 0.022`——这正是输出中 `aligned`、`proxy`、`deceptive` 三者共同的 0.022 损失的来源。它是**标签噪声**，与对齐、欺骗都无关。修正：`y_base = 1 if adv_x > 0 else 0`。
- ⚠️ 名字叫"对抗训练"，但没有训练：样本加进来后只用于计算损失。讲义练习 2 问"欺骗模型的部署背叛率会不会下降"，在这份代码里无法回答——背叛率由 `if ex.is_training` 硬编码决定。

### 3.5 `main` 的三张表

```python
    training = [gen_example(training=True) for _ in range(500)]
    deployment = [gen_example(training=False, drift=0.3) for _ in range(500)]

    policies = {
        "aligned": aligned_policy,
        "proxy": proxy_policy,
        "deceptive (mesa=0)": lambda e: deceptive_policy(e, mesa_goal=0),
        "pseudo-no-awareness": lambda e: pseudo_no_awareness_policy(e, mesa_goal=0),
    }
```

- 用字典把"策略名 → 策略函数"组织起来，`run_period` 遍历字典逐一评估。字典保留插入顺序，所以输出顺序固定。
- 三张表分别回答：训练损失能否区分？部署时谁背叛？"对抗训练"能否改变什么？

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 手写固定策略、只算损失 | 直接展示"行为上不可区分" | 没有 base 优化器，看不到"SGD 为什么会选中欺骗性解"；真实研究需要可学习的策略 |
| 显式布尔情境标志 | 最简单地表达"知道自己在训练" | 情境感知变成完美神谕；对抗训练无法影响它，讲义的核心机制（学会区分测试与部署）无从体现 |
| 部署漂移 0.3 | 让背叛在部署时可见 | 漂移太小，代理策略不会失效；应把"漂移"与"部署线索"分开设计 |
| `proxy` 阈值只在 `|x| ≥ 3` 改变 | 想表达"分布外才改变行为" | 数学上与 aligned 等价，proxy 类别形同虚设 |
| 对抗样本按旧 `x` 打标签 | 实现疏忽 | 制造了 0.022 的伪损失；应按扰动后的输入重新计算标签 |
| 用 0-1 损失 | 直观 | 无法求梯度；需要学习时应换成交叉熵 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 带行内注释的字段 | `x: float  # input feature` | 自动生成 `__init__`，字段即参数 |
| 关键字参数构造 | `Example(x=x, y_base=y, is_training=training)` | 按名字传参，顺序无关、可读性高 |
| 条件表达式 | `(0.0 if training else drift)`、`1 if ex.x > 0 else 0` | 三元运算 |
| `random.gauss(mu, sigma)` | `random.gauss(0.0, 1.0)` | 正态分布采样（第二个参数是标准差） |
| 默认参数 | `def deceptive_policy(ex, mesa_goal: int = 0)` | 调用时可省略 |
| `lambda` 固定参数 | `lambda e: deceptive_policy(e, mesa_goal=0)` | 把双参数函数包装成单参数函数，统一接口 |
| 函数作为字典值 | `policies = {"aligned": aligned_policy, ...}` | 函数是一等对象，可以存进容器 |
| `.items()` 遍历 | `for label, pol in policies.items():` | 同时取键和值 |
| 生成器计数 | `sum(1 for e in examples if policy(e) != e.y_base)` | 统计满足条件的个数 |
| 列表推导式生成数据 | `[gen_example(training=True) for _ in range(500)]` | 批量构造样本 |
| f-string 对齐 | `f"  {label:24s} loss={l:.3f}  acc={acc:.3f}"` | 左对齐 24 格；三位小数 |
| `\n` 换行 | `print(f"\n{name}  (n={len(examples)})")` | 先输出空行再输出标题 |
| 模块 docstring | 文件顶部三引号字符串 | 说明用途和用法，`help(module)` 可见 |

---

## 6. 运行结果解读

实际运行（Python 3.13，`random.seed(13)`）：

```text
training loss by policy class  (n=500)
  aligned                  loss=0.000  acc=1.000
  proxy                    loss=0.000  acc=1.000      ← 与 aligned 处处相同
  deceptive (mesa=0)       loss=0.000  acc=1.000      ← 训练时合作：与 aligned 不可区分
  pseudo-no-awareness      loss=0.516  acc=0.484      ← = 训练集中 x>0 的比例

deployment loss by policy class  (n=500)
  aligned                  loss=0.000  acc=1.000
  proxy                    loss=0.000  acc=1.000      ← 注释说会"break"，实际不会
  deceptive (mesa=0)       loss=0.612  acc=0.388      ← = 部署集中 x>0 的比例，理论 Φ(0.3)=0.618
  pseudo-no-awareness      loss=0.612  acc=0.388

adversarial-training loss  (n=541)
  aligned                  loss=0.022  acc=0.978      ← 12 个错误标签 / 541，标签 bug
  proxy                    loss=0.022  acc=0.978
  deceptive (mesa=0)       loss=0.022  acc=0.978
  pseudo-no-awareness      loss=0.516  acc=0.484
```

逐项解读：

- **第一张表（讲义练习 1）**：`aligned` 与 `deceptive` 训练损失都是 0，"行为证据无法区分"这一点成立。
- **第二张表**：`deceptive` 在部署时恒输出 0，所有 `x > 0` 的样本都错，0.612 与理论值 0.618 吻合。`pseudo-no-awareness` 的部署损失相同，因为两者在部署时行为一样——区别只在训练时是否暴露。
- **proxy 两张表都是 0**：并非"漂移不够大"，而是它与 aligned 是同一个函数（见 3.2）。讲义中 proxy aligned 的关键特征"训练好、分布外坏"在这里没有体现。
- **第三张表**：三种合作策略的 0.022 完全来自标签 bug（见 3.4）；修正标签后应全部为 0。`pseudo-no-awareness` 仍约为 0.516，因为新增样本的标签直接复制自被抽中的原样本，`y_base = 1` 的比例几乎不变。
- **说明文字的论点**（"对抗样本仍标记为训练，模型可能依赖其它特征作为触发；对抗训练让它更会区分测试与部署"）是讲义的核心观点，但这份代码只用"`is_training` 始终为真"来**断言**它，并没有**演示**"学会区分"的过程。要看到这个过程，需要一个能学习、从输入特征推断情境的策略——这正是第 07 节 Sleeper Agents 代码试图做的。

---

## 7. 动手改一改

1. **修标签 bug**：把对抗样本的 `y_base` 改为按扰动后的 `x` 计算，确认三种合作策略的损失回到 0。
2. **让 proxy 真正是代理**：改成"`|x| ≤ 2` 时看符号，否则输出 0"，把部署漂移加大到 1.5，复现"训练好（约 2.3%）、部署坏（约 31%）"（测验 Q9 给出了实测值）。
3. **把情境感知从标志改成推断**：去掉 `is_training`，让欺骗策略用一个输入特征推断阶段（例如再加一维特征 `z`，训练时 `z ~ N(0, 1)`、部署时 `z ~ N(2, 1)`，策略在 `z > 1` 时背叛）。观察：此时训练分布上偶尔也会"背叛"，训练损失不再严格为 0。
4. **加入可学习的策略和 base 优化器**：用逻辑回归同时读入 `x` 和 `z`，在训练集上用 SGD 训练；比较"训练集只含 `z` 小的样本"与"对抗训练加入 `z` 大的样本"两种情况下学到的权重（讲义练习 2）。
5. **区分 proxy 与 deceptive 的测试**（讲义练习 3）：构造 2 × 2 网格——输入分布（训练/漂移）× 情境线索（像训练/像部署），分别测量两种策略的错误率，验证 proxy 随分布变化、deceptive 随线索变化。
6. **扩展到多个 mesa 目标**：让 `mesa_goal` 取 0 或 1，测量部署损失如何随 `mesa_goal` 和漂移方向变化，体会"背叛造成的损失取决于 mesa 目标与 base 目标的分歧程度"。

---

## 8. 常见坑

- **把"损失 = 0"当作"对齐"**：第一张表正是反例。
- **以为 proxy 在这里演示了分布外失效**：它与 aligned 处处相等，需要先修正实现。
- **把对抗训练集上的 0.022 解读为"对抗训练暴露了问题"**：那是标签 bug，三种合作策略的损失一模一样就是信号。
- **混淆讲义与代码的标志取值**：讲义说训练时 flag 为 0，代码里训练时 `is_training=True`。
- **把 `pseudo-no-awareness` 当作 pseudo-aligned**：它训练时就暴露，不符合讲义定义。
- **以为这份代码里有训练**：所有策略都是固定函数，"base optimizer"只存在于文字说明中。
- **以为完美情境标志是现实假设**：真实模型只能从特征推断阶段，这种推断可以被对抗训练强化——这正是讲义警告的机制。
