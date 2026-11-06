# 代码讲解 · main.py

> **所属小节**：阶段 15 · 自主系统 · 第 03 节 AlphaEvolve：演化式 Coding Agents ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（Run A + Run B）或 `python main.py --no-holdout`（只跑 Run B） ｜ **依赖**：仅标准库（`argparse`、`math`、`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

一个最小的"AlphaEvolve 形状"的演化循环，任务是**符号回归**：用 `x`、常数、加法、乘法拼出一个表达式，去逼近目标函数 `2x² + 3x − 1`。

1. **程序表示**：表达式是嵌套元组构成的语法树，相当于 AlphaEvolve 数据库中的"程序"。
2. **"LLM" 提出修改**：`mutate` 用随机的小改动（换成叶子、外面套一层加/乘、扰动常数）代替 LLM 的定向编辑。
3. **Evaluator**：在训练点和测试点上计算 MSE。
4. **MAP-elites archive**：按 `(表达式深度, 常数量级)` 划分格子，每格只保留最优者，用来保持多样性。
5. **有无 held-out 信号的对比**：Run A 用训练与测试 MSE 的平均作为适应度，Run B 只用训练 MSE——对应讲义 "removing the held-out test lets the loop overfit"。

> 一句话：**演化只会朝 evaluator 指的方向走，evaluator 测什么就得到什么**。同时要看清：在默认设定下，这份代码其实**几乎演示不出过拟合**，Run A 的"测试集"也不再是真正的留出集（见 3.6、3.7）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `target` | 函数 | `2x² + 3x − 1` | 要重新发现的"真理" |
| `Expr` | 类型别名（`tuple`） | `("num", v)` / `("x",)` / `("add", a, b)` / `("mul", a, b)` | 程序表示 |
| `evaluate_expr` | 递归函数 | 给定 x 求表达式的值 | 运行程序 |
| `depth` / `max_const` | 递归函数 | 树深度；最大常数绝对值 | MAP-elites 特征 |
| `mutate` / `perturb` / `random_leaf` | 函数 | 四种变异；随机改一个常数；随机叶子 | LLM 提出的编辑 |
| `render` | 递归函数 | 把树打印成带括号的中缀表达式 | 可读输出 |
| `mse` | 函数 | 在一组点上的均方误差，溢出返回 `inf` | Evaluator |
| `Candidate` | dataclass | 表达式 + 训练分 + 测试分 + 出生代数 | 数据库中的一条记录 |
| `cell_key` | 函数 | `(min(深度, 6), min(int(最大常数/2), 4))` | MAP-elites 网格坐标 |
| `seed_candidate` | 函数 | 用随机叶子生成初始个体 | 种子程序 P₀ |
| `run_loop` | 函数 | 初始化 archive → 循环：选父代 → 变异 → 打分 → 按格子入库 | 演化主循环 |
| `main` | 函数 | 解析 `--no-holdout`，跑 Run A / Run B，打印结论 | 入口 |

数据流：`main()` → `run_loop(1500, 20, use_holdout, seed=1)` → 20 个 `seed_candidate` 入库 → 1500 代 `random.choice(archive)` → `mutate` → `mse(train)` / `mse(test)` → `cell_key` → 比较 `signal_of` 决定是否替换 → 最终按 `signal_of` 选出 `best` → `render` 打印。

---

## 3. 逐段精讲

### 3.1 程序表示：嵌套元组构成的语法树

```python
Expr = tuple  # recursive: ("num", v) | ("x",) | ("add", a, b) | ("mul", a, b)


def evaluate_expr(e: Expr, x: float) -> float:
    tag = e[0]
    if tag == "num":
        return float(e[1])
    if tag == "x":
        return x
    if tag == "add":
        return evaluate_expr(e[1], x) + evaluate_expr(e[2], x)
    if tag == "mul":
        return evaluate_expr(e[1], x) * evaluate_expr(e[2], x)
    raise ValueError(tag)
```

- 第一个元素是"标签"，其余是子节点或值。例如 `x*5 − 1` 写作 `("add", ("mul", ("x",), ("num", 5.0)), ("num", -1.0))`。
- 用元组（不可变）表示树：变异时总是构造新树，旧树可以安全地留在 archive 中被共享，不会被意外修改。
- `evaluate_expr` 是典型的**递归求值**：叶子直接返回，内部节点先求子树再合并。
- `Expr = tuple` 只是类型别名，帮助阅读；Python 不会检查元组的结构。
- 文法里没有减法和除法，负数靠负常数表示；没有除法也就没有除零问题。

### 3.2 特征函数：`depth` 与 `max_const`

```python
def depth(e: Expr) -> int:
    tag = e[0]
    if tag in ("num", "x"):
        return 1
    return 1 + max(depth(e[1]), depth(e[2]))


def max_const(e: Expr) -> float:
    tag = e[0]
    if tag == "num":
        return abs(e[1])
    if tag == "x":
        return 0.0
    return max(max_const(e[1]), max_const(e[2]))
```

- 叶子深度为 1，内部节点为"1 + 较深子树的深度"。
- `max_const` 取所有常数的绝对值最大者；没有常数的表达式为 0。
- 这两个量构成 MAP-elites 的**行为描述符**：一个衡量"结构复杂度"，一个衡量"常数规模"。

### 3.3 变异：用随机编辑代替 LLM

```python
def mutate(e: Expr) -> Expr:
    choice = random.random()
    if choice < 0.25:
        return random_leaf()
    if choice < 0.5:
        return ("add", e, random_leaf())
    if choice < 0.75:
        return ("mul", e, random_leaf())
    return perturb(e)


def perturb(e: Expr) -> Expr:
    tag = e[0]
    if tag == "num":
        return ("num", e[1] + random.choice([-1.0, -0.5, 0.5, 1.0]))
    if tag == "x":
        return e
    return (tag, perturb(e[1]), e[2]) if random.random() < 0.5 else (tag, e[1], perturb(e[2]))
```

| 概率 | 动作 | 效果 |
|------|------|------|
| 25% | 整棵树换成一个随机叶子 | "推倒重来"，深度回到 1 |
| 25% | `e + leaf` | 在**最外层**加一项 |
| 25% | `e * leaf` | 把**整个表达式**乘以一项 |
| 25% | `perturb` | 沿随机路径走到一个叶子，若是常数就 ±0.5 或 ±1 |

- 只能在最外层加项或乘项，意味着要构造 `2x² + 3x − 1` 必须按特定顺序"层层包裹"，例如 `((((x*x)*2) + x) + x) + x) + −1`（Run A 找到的正是这种形状）。
- `perturb` 走到 `("x",)` 叶子时原样返回，所以有一部分 perturb 是"空操作"。
- 常数初始为 `{−2, −1, 0, 1, 2, 3}`，扰动步长为 0.5 的倍数，因此所有常数都是 0.5 的倍数；目标系数 2、3、−1 都可达。
- ⚠️ 与讲义的差别：讲义强调 LLM 能"把搜索集中在合理邻域、产出可编译的修改"；这里的随机变异没有任何"理解"，只是因为文法简单才保证每个子代都"可编译"。讲义提到的"把父代 + 若干高分变体 + evaluator 签名放进 prompt"也没有对应实现。

### 3.4 Evaluator：`mse`

```python
def mse(e: Expr, xs: list[float]) -> float:
    total = 0.0
    for x in xs:
        try:
            y = evaluate_expr(e, x)
        except (OverflowError, ValueError):
            return float("inf")
        total += (y - target(x)) ** 2
    return total / max(1, len(xs))
```

- 标准均方误差；`max(1, len(xs))` 防止空列表除零。
- 任何异常都视为"最差"（`inf`），对应讲义"编译、运行、评估"中运行失败的情形。
- ⚠️ Python 的浮点乘法溢出**不会**抛 `OverflowError`，而是得到 `inf`；`inf + (−inf)` 得到 `nan`。所以这个 `except` 基本捕获不到溢出，MSE 可能直接是 `inf` 或 `nan`（实测 `("mul", 1e200, 1e200)` 的 MSE 为 `inf`）。`nan` 与任何数比较都为 `False`，不会替换已有个体，但可能占据空格子。在本任务的常数范围内很少出现。
- `(y − target(x)) ** 2` 中的 `**` 对浮点数溢出会抛 `OverflowError`，这是 `except` 唯一可能捕获的情形。

### 3.5 MAP-elites：`cell_key` 与 archive

```python
def cell_key(e: Expr) -> tuple[int, int]:
    d = min(depth(e), 6)
    c = min(int(max_const(e) / 2), 4)
    return (d, c)
```

- 深度 1–6（≥ 6 归为 6），常数桶 0–4（桶宽 2，|c| ≥ 8 归为 4），最多 6 × 5 = 30 个格子。
- 例：`((x * 5) + -1)` 深度 3、最大常数 5 → `int(2.5) = 2` → `(3, 2)`。
- ⚠️ 深度上限 6 很低：Run A 找到的答案深度为 7，被截断成 `(6, 1)`；由于 `mutate` 每次外层加/乘都让深度 +1，几乎所有"有用"的表达式都挤在 `d = 6` 这一列，多样性主要靠常数桶维持。
- archive 是 `dict[tuple[int, int], Candidate]`：键是格子坐标，值是该格当前最优候选。

### 3.6 主循环 `run_loop`

```python
    def signal_of(c: Candidate) -> float:
        return 0.5 * (c.train_score + c.test_score) if use_holdout else c.train_score

    archive: dict[tuple[int, int], Candidate] = {}
    for _ in range(pop):
        c = seed_candidate(test_xs, train_xs, 0)
        ...
    for g in range(1, generations + 1):
        parent = random.choice(list(archive.values()))
        child_expr = mutate(parent.expr)
        tr = mse(child_expr, train_xs)
        te = mse(child_expr, test_xs)
        child = Candidate(child_expr, tr, te, g)
        key = cell_key(child_expr)
        incumbent = archive.get(key)
        if incumbent is None or signal_of(child) < signal_of(incumbent):
            archive[key] = child

        best = min(archive.values(), key=lambda c: c.train_score)
        best_trace.append(best.train_score)
        test_trace.append(best.test_score)

    best = min(archive.values(), key=signal_of)
```

- **`signal_of` 是一个闭包**：定义在 `run_loop` 内部，读取外层的 `use_holdout`。Run A 的适应度是"训练 MSE 与测试 MSE 的平均"，Run B 只用训练 MSE。
- 初始化：20 个随机叶子（只有 `x` 和 6 个常数共 7 种可能），按格子入库——叶子深度都是 1，常数桶只可能是 0（`x`、0、±1）或 1（±2、3），所以 archive 一开始最多只有 `(1, 0)`、`(1, 1)` 两个格子。
- 每代**均匀随机**选一个格子的精英当父代（不偏向高分），产生一个子代，只在它自己的格子里与在位者竞争——这就是 MAP-elites 的核心："不必是全局最好，只要是本格最好就能存活"。
- `best_trace` 按**训练分**记录 archive 中的最优，与最终按 `signal_of` 选择的口径不同（Run A 中两者可能是不同个体）。
- 最终选择用 `signal_of`：代码注释特意说明，若 Run B 在最终选择时偷看测试集，就会"silently leak the holdout back into Run B and mask the overfitting"。这个注意点是对的。
- ⚠️ **但 Run A 本身已经把测试集用进了适应度**：测试点决定了谁能进 archive、谁最终胜出，于是 Run A 打印的 "test MSE" 是被优化过的误差，不再是泛化能力的无偏估计。它对应讲义"LLM 从未见过"意义上的 held-out（`mutate` 确实不看数据），但不是统计意义上的留出集。要评估泛化，需要第三组从未参与选择的数据，或按讲义的建议"在评估时生成输入"（测验 Q11）。
- `seed: int | None = None`：传入种子时在函数内重设全局随机状态，所以 Run A、Run B 都从同一个种子开始，彼此独立可复现。

### 3.7 `main` 与命令行

```python
    parser.add_argument("--no-holdout", action="store_true", help="...")
    args = parser.parse_args()
    ...
    if not args.no_holdout:
        print("\nRun A: held-out test included in evaluator signal")
        best, train_trace, _ = run_loop(generations=1500, pop=20, use_holdout=True, seed=DEFAULT_SEED)
        ...
        print("  progress  : gen 100 train={:.3f} gen 500 train={:.3f} gen 1500 train={:.3f}".format(
            train_trace[99], train_trace[499], train_trace[-1]))

    print("\nRun B: no held-out test (train-only evaluator -> reward hacking risk)")
    best, _train_trace, _test_trace = run_loop(generations=1500, pop=20, use_holdout=False, seed=DEFAULT_SEED)
```

- `action="store_true"`：出现该参数时值为 `True`，否则 `False`。argparse 把 `--no-holdout` 转为属性 `args.no_holdout`。
- `--no-holdout` **只是跳过 Run A**，Run B 总会运行且结果与默认运行完全相同。讲义练习 1 "Disable the held-out evaluator (flag `--no-holdout`) and re-run" 的对比，其实默认运行就已经同时给出了。
- `train_trace[99]` 是第 100 代（下标从 0 开始）；`str.format` 与 f-string 混用，风格不统一但等价。
- HEADLINE 的文字是硬编码的，"Run B converges to low train MSE" 与默认输出（Run B 训练 MSE 2.29）并不一致。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 符号回归 + 元组语法树 | 任何子代都"可编译"，evaluator 秒级 | 与真实代码相差甚远；AlphaEvolve 让 LLM 输出 diff，编译失败很常见 |
| 随机变异代替 LLM | 无需 API，可复现 | 体现不出 LLM "定向、合理邻域"的优势 |
| 只在最外层加/乘项 | 实现最简单 | 搜索路径受限，许多等价表达式只能以特定顺序构造 |
| MAP-elites 键 `(深度≤6, 常数桶≤4)` | 保持结构与常数的多样性 | 深度上限过低，有用解都挤在一列；真实系统描述符应反映"不同做法" |
| 均匀随机选父代 | 鼓励探索 | 收敛慢；AlphaEvolve 会结合分数与多样性采样 |
| Run A 把测试集放进适应度 | 演示"有额外约束"的搜索 | 测试集不再是留出集，test MSE 不能代表泛化；应三集划分或评估时生成新输入 |
| 6 个训练点 + 二次目标 | 目标唯一可达零训练误差 | 几乎不会出现"训练 0、测试大"的过拟合；把训练集缩到 2 个点才能看到（测验 Q10） |
| 单一种子、单次运行 | 输出简洁 | 50 个种子下 Run A/B 精确命中次数为 23 vs 22，单次对比主要反映随机路径 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 类型别名 | `Expr = tuple` | 给类型起名字，便于阅读，不做检查 |
| 嵌套元组表示树 | `("add", ("x",), ("num", 2.0))` | 单元素元组必须写逗号：`("x",)` |
| 递归函数 | `evaluate_expr`、`depth`、`max_const`、`render`、`perturb` | 函数调用自身处理子树 |
| `in` 判断 | `if tag in ("num", "x")` | 成员检测 |
| `raise ValueError(tag)` | `evaluate_expr` 末尾 | 未知标签时抛异常 |
| 条件表达式 | `(tag, perturb(e[1]), e[2]) if random.random() < 0.5 else (tag, e[1], perturb(e[2]))` | 一行内二选一 |
| `random.choice` | `random.choice([-1.0, -0.5, 0.5, 1.0])`、`random.choice(list(archive.values()))` | 从序列中随机取一个；`dict.values()` 需先转 list |
| f-string `:g` | `f"{e[1]:g}"` | 通用格式：`2.0` 显示为 `2`，`2.5` 显示为 `2.5` |
| `try / except` 多异常 | `except (OverflowError, ValueError):` | 元组形式一次捕获多种异常 |
| `float("inf")` | `return float("inf")` | 正无穷，比任何有限数都大 |
| `@dataclass` | `class Candidate` | 自动生成构造函数与 `__repr__` |
| 内置泛型注解 | `tuple[int, int]`、`list[float]`、`dict[tuple[int, int], Candidate]` | 3.9+ 语法 |
| `int \| None` | `seed: int \| None = None` | 3.10+ 联合类型（配合 `from __future__ import annotations`） |
| 闭包 | `def signal_of(c)` 定义在 `run_loop` 内，读取 `use_holdout` | 内层函数"记住"外层变量 |
| `min(..., key=...)` | `min(archive.values(), key=signal_of)`、`key=lambda c: c.train_score` | 按自定义指标取最小 |
| 多返回值 | `return best, best_trace, test_trace` | 返回元组，调用处解包 |
| 下划线变量名 | `_train_trace, _test_trace` | 约定表示"不使用" |
| `argparse` | `add_argument("--no-holdout", action="store_true")` | 布尔开关参数 |
| `str.format` | `"gen 100 train={:.3f}".format(...)` | 与 f-string 等价的旧式格式化 |
| 负下标 | `train_trace[-1]` | 取最后一个元素 |

---

## 6. 运行结果解读

实际运行（`cd code && python3 main.py`，约 0.1 秒）：

```text
target: 2x^2 + 3x - 1

Run A: held-out test included in evaluator signal
  best expr : ((((((x * x) * 2) + x) + x) + x) + -1)    ← 精确等于 2x² + 3x − 1
  train MSE : 0.0000
  test  MSE : 0.0000
  generation: 1229
  progress  : gen 100 train=13.833 gen 500 train=3.167 gen 1500 train=0.000

Run B: no held-out test (train-only evaluator -> reward hacking risk)
  best expr : (((((x * x) * 2.5) + x) + -2) + x)        ← 2.5x² + 2x − 2
  train MSE : 2.2917
  test  MSE : 4.3906
  generation: 1359
  train-to-test gap: +2.0990  (large gap = overfit/reward hacking proxy)
```

`python3 main.py --no-holdout` 只输出 Run B，数字与上面完全相同。

逐项解读：

- **Run A** 在第 1229 代精确找回目标函数：`x*x*2 + x + x + x − 1`。注意 `3x` 是靠三次"外层加 x"拼出来的——这正是 `mutate` 只能在最外层加项的结果。训练曲线 13.83 → 3.17 → 0，体现了演化的阶梯式进步。
- **Run B** 停在 `2.5x² + 2x − 2`：误差函数 `d(x) = 0.5x² − x − 1`，训练 MSE = 13.75 / 6 = 2.2917；测试 MSE = 30.73 / 7 = 4.3906，其中 x = −2.5 一个点就贡献了约 70%（`d = 4.625`）。
- **这个 gap 不是"过拟合"**：Run B 连训练集都没拟合好（2.29 而不是 0）。差距来自欠拟合的解在外推区间（测试集向两端多伸出 0.5）误差放大。讲义说的 "overfit spectacularly" 在默认设定下没有出现。
- **多种子验证**（seed 0–49）：Run A 23 次、Run B 22 次精确找到目标；所有训练误差为 0 的运行，测试误差也为 0；平均测试 MSE Run A 2.17、Run B 4.91。所以默认种子下 A、B 的差别主要是**搜索路径的随机性**，加上 Run A 的适应度包含了外推区间的点。
- **让过拟合真正出现**：把训练集缩到 `[0.0, 1.0]`，train-only 信号下 20 个种子中 14 个训练误差为 0、测试 MSE 中位数 104，找到的解如 `4x³ + x − 1`（在 0、1 两点与目标一致，测试 MSE 3826.7）；holdout 信号下测试 MSE 中位数为 0（测验 Q10）。

---

## 7. 动手改一改

1. **（练习 1）**用 seed 0–19 分别跑 Run A 和 Run B，统计精确命中次数、训练/测试 MSE 的中位数，确认单个种子的结论是否稳健。
2. **复现过拟合**：把 `train_xs`、`test_xs` 改为 `run_loop` 的参数，令训练集只有 `[0.0, 1.0]`，比较两种信号（参考测验 Q10）。
3. **真正的留出集**：在评估时为每个子代生成新的随机输入作为 held-out 信号，搜索结束后用一组从未参与选择的"报告集"给出泛化误差（参考测验 Q11）；注意评分噪声对 archive 比较的影响。
4. **修正溢出处理**：在 `mse` 中用 `math.isfinite(y)` 检查结果，非有限值直接返回 `inf`，并验证 `nan` 不再进入 archive。
5. **（练习 2）**更换描述符：例如 `(使用 x 的次数, 最高次幂)`，或把深度上限提高到 10，比较找到目标的代数与成功率。
6. **进阶**：把 `mutate` 换成"更聪明"的编辑器——比如以一定概率在**子树内部**插入节点、或直接把常数替换为最小二乘拟合值——体会讲义所说"LLM 把搜索集中在合理邻域"带来的效率提升；再加入一个"简洁性惩罚"（节点数）观察解的形状变化。

---

## 8. 常见坑

- **把测试集放进适应度后还把它当泛化估计**：参与选择的数据就不再是留出集。
- **单种子下结论**：A/B 的差距可能只是随机路径不同；至少跑十几个种子。
- **以为 train-only 一定过拟合**：只有当"训练误差为 0 的解不唯一"时才会过拟合；目标在假设空间内且约束充分时，train-only 也能找到正确解。
- **混淆欠拟合 + 外推误差与过拟合**：Run B 的 gap 属于前者。
- **依赖 `OverflowError` 捕获浮点溢出**：浮点乘法溢出得到 `inf`，不会抛异常。
- **描述符上限太低**：`min(depth, 6)` 让大多数有用解挤在同一列，多样性名存实亡。
- **命令行参数的实际作用**：`--no-holdout` 只是跳过 Run A，不改变 Run B。
