# 代码讲解 · main.py

> **所属小节**：阶段 09 · 强化学习 · 第 02 节 动态规划——策略迭代和值迭代 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python main.py`（无命令行参数） ｜ **依赖**：仅 Python 标准库（连 `import` 都没有）

---

## 1. 这份代码在考察什么

上一节我们只会"评估一个给定策略"，这一节要**求出最优策略**。代码用同一个带滑动的 4×4 GridWorld，分别跑两种经典 DP 算法并交叉验证：

1. **显式的环境模型**：`transitions(s, a)` 返回所有可能结果 `(s', r, p)`，这是 DP 与 model-free 方法的根本区别——DP 能"查表"，不用采样。
2. **Q 值是一切的积木**：`q_value(s, a, V, γ) = Σ p·(r + γV(s'))`，策略评估、策略改进、值迭代全部由它拼出来。
3. **策略迭代（PI）**：评估到收敛 → 贪心改进 → 直到策略不变。
4. **值迭代（VI）**：每次扫描直接取 `max_a`，最后提取贪心策略。
5. **交叉验证**：两种算法得到的 `V*` 的 sup-norm 差 ≈ 0、策略完全一致——这就是"DP 是正确性基准"的含义。

> 一句话：**有模型时，最优策略可以"算"出来，而不是"学"出来**；后面所有采样方法都在逼近这里的答案。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GRID`、`TERMINAL`、`ACTIONS`、`DELTAS`、`SLIP` | 常量 | 网格、终点、动作顺序、位移、滑动概率 | S、A、随机性 |
| `states()` | 函数 | 枚举 16 个状态 | 状态集 |
| `apply_move(state, direction)` | 函数 | 按方向移动并夹在边界内 | 确定性位移 |
| `perpendiculars(action)` | 函数 | 返回两个垂直方向 | 滑动方向 |
| `transitions(state, action)` | 函数 | 返回 `[(s', r, p), ...]` | 环境模型 P、R |
| `q_value(state, action, V, gamma)` | 函数 | 一步 Bellman 备份 | `Q(s,a) = Σ p(r + γV(s'))` |
| `policy_evaluation(policy, ...)` | 函数 | 原地迭代 Bellman 期望方程 | 策略评估 |
| `greedy_from_V(V, gamma)` | 函数 | 每个状态取 Q 最大的动作 | 策略改进 |
| `policy_iteration(...)` | 函数 | 评估 + 改进循环 | 策略迭代 |
| `value_iteration(...)` | 函数 | 迭代 Bellman 最优方程 | 值迭代 |
| `print_V` / `print_policy` | 函数 | 打印价值表和箭头策略 | — |
| `main()` | 函数 | 跑 VI、PI 并比较 | 交叉验证 |

调用关系：`value_iteration` 和 `policy_evaluation` 都调用 `q_value`，`q_value` 调用 `transitions`，`transitions` 调用 `apply_move` + `perpendiculars`；`policy_iteration` 调用 `policy_evaluation` 和 `greedy_from_V`。

---

## 3. 逐段精讲

### 3.1 环境模型：`apply_move`、`perpendiculars`、`transitions`

```python
ACTIONS = ("up", "down", "left", "right")
DELTAS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
SLIP = 0.1

def perpendiculars(action):
    if action in ("up", "down"):
        return ("left", "right")
    return ("up", "down")


def transitions(state, action):
    if state == TERMINAL:
        return [(state, 0.0, 1.0)]
    outcomes = []
    p_intended = 1.0 - SLIP
    outcomes.append((apply_move(state, action), -1.0, p_intended))
    for perp in perpendiculars(action):
        outcomes.append((apply_move(state, perp), -1.0, SLIP / 2.0))
    return outcomes
```

- 与第 01 节不同，这里把"动作顺序"`ACTIONS`（元组）和"位移表"`DELTAS`（字典）分开。**`ACTIONS` 的顺序有意义**：后面 `max(ACTIONS, key=...)` 遇到平局时返回第一个，元组保证顺序固定。
- `transitions` 返回**一个分布**而不是一个样本：90% 按预期方向，10% 平均分给两个垂直方向。三个概率和为 1。
- 撞墙的滑动会留在原地（`apply_move` 内部 clamp），所以可能出现"两个结果是同一个格子"的情况，求期望时直接分别累加，结果仍然正确。
- 终止态返回 `[(自身, 0.0, 1.0)]`，构成**吸收态**；同时 `policy_evaluation` 和 `value_iteration` 都显式跳过终止态，双重保险。
- 讲义原话："`transitions(s, a)` returns a list of `(s', r, p)`. This is the entire model." 这就是 DP 所需的全部信息。

### 3.2 `q_value`：一步 Bellman 备份

```python
def q_value(state, action, V, gamma):
    return sum(p * (r + gamma * V[s_next]) for s_next, r, p in transitions(state, action))
```

- 公式 `Q(s,a) = Σ_{s'} P(s'|s,a) [r + γ V(s')]`，一行生成器表达式写完。
- 把它抽成函数是这份代码最重要的设计：**评估**用 `Σ_a π(a|s) q_value(...)`，**改进**用 `argmax_a q_value(...)`，**值迭代**用 `max_a q_value(...)`——三者只差"对动作怎么聚合"。
- 解包顺序 `s_next, r, p` 必须与 `transitions` 返回的 `(s', r, p)` 一致；顺序写错不会报错，但结果全错。

### 3.3 `policy_evaluation`：原地更新

```python
def policy_evaluation(policy, gamma=0.99, tol=1e-6, max_iter=5000):
    V = {s: 0.0 for s in states()}
    for _ in range(max_iter):
        delta = 0.0
        for state in states():
            if state == TERMINAL:
                continue
            dist = policy(state)
            v = sum(pi_a * q_value(state, action, V, gamma) for action, pi_a in dist.items())
            delta = max(delta, abs(v - V[state]))
            V[state] = v
        if delta < tol:
            return V
    return V
```

- `V[state] = v` 是**原地更新**（Gauss-Seidel）：同一轮里后面的状态会读到前面状态刚更新的值。第 01 节用的是同步更新（`new_values`），讲义的 Pitfalls 指出原地更新通常更快，生产代码也用原地。
- `policy` 是函数接口 `state → {action: prob}`，所以确定性策略需要包装成 `lambda s: {policy[s]: 1.0}`（见 `policy_iteration`）。
- `delta` 是本轮最大变化量（sup-norm），与讲义"用 `max |V_new − V|`，不要用平均值"一致。
- ⚠️ 每次调用都从 `V = 0` 开始，没有热启动。对"永远到不了终点"的策略（比如初始的全部向上），要从 0 慢慢收敛到 -100，需要上千次扫描（见第 6 节）。
- ⚠️ 达到 `max_iter` 时静默返回，没有提示"未收敛"。

### 3.4 `greedy_from_V`：策略改进

```python
def greedy_from_V(V, gamma=0.99):
    policy = {}
    for state in states():
        if state == TERMINAL:
            policy[state] = "up"
            continue
        best = max(ACTIONS, key=lambda a: q_value(state, a, V, gamma))
        policy[state] = best
    return policy
```

- `max(iterable, key=函数)` 返回让 `key` 最大的**元素本身**（动作名），即 `argmax`。
- **稳定 tie-break**：Python 的 `max` 在多个元素并列最大时返回**第一个**。`(0,0)` 处 down 与 right 的 Q 值因对称而完全相等，结果总是 down（`ACTIONS` 中 down 排在 right 前）。这避免了讲义 Pitfalls 里"平局导致策略振荡、PI 无法停止"的问题。
- 终止态随便填一个 `"up"`：它不影响价值，但必须**固定**，否则 `new_policy == policy` 的比较可能因为终止态的值不同而失败。
- `lambda a: q_value(state, a, V, gamma)` 捕获了循环变量 `state`；这里 lambda 在 `max` 内立即被调用完毕，所以不会踩"闭包延迟绑定"的坑。

### 3.5 `policy_iteration`：评估 ↔ 改进

```python
def policy_iteration(gamma=0.99, tol=1e-6):
    policy = {s: "up" for s in states()}
    sweeps = 0
    for it in range(100):
        V = policy_evaluation(lambda s: {policy[s]: 1.0}, gamma=gamma, tol=tol)
        sweeps += 1
        new_policy = greedy_from_V(V, gamma)
        if new_policy == policy:
            return V, policy, it + 1
        policy = new_policy
    return V, policy, 100
```

- 初始策略"全部向上"是**任意**选择（讲义："arbitrary start"）。由于"向上"的滑动方向是左右，第 0–2 行永远到不了终点，第一轮评估得到 `V(0,0) = -100`。
- `new_policy == policy`：两个字典逐键比较。策略不再变化即为最优——这是**策略改进定理**保证的。
- 返回第三个值是外层迭代次数 `it + 1`。
- ⚠️ `sweeps` 变量被累加但**从未使用**，且它统计的是外层迭代次数（与 `it + 1` 重复），并非内层扫描次数——属于残留的死代码。若要完成讲义练习 2 的"比较扫描次数"，需要让 `policy_evaluation` 返回扫描次数并累加。
- ⚠️ 这里的 lambda 每轮都捕获**当前的** `policy` 变量；因为 `policy_evaluation` 在本轮内就用完了这个 lambda，之后 `policy = new_policy` 才重新绑定，所以没有问题。

### 3.6 `value_iteration`：一个循环搞定

```python
def value_iteration(gamma=0.99, tol=1e-6, max_iter=5000):
    V = {s: 0.0 for s in states()}
    for it in range(max_iter):
        delta = 0.0
        for state in states():
            if state == TERMINAL:
                continue
            v = max(q_value(state, action, V, gamma) for action in ACTIONS)
            delta = max(delta, abs(v - V[state]))
            V[state] = v
        if delta < tol:
            return V, greedy_from_V(V, gamma), it + 1
    return V, greedy_from_V(V, gamma), max_iter
```

- 与 `policy_evaluation` 只差一处：`Σ_a π(a|s) · q` 换成 `max_a q`——从 Bellman **期望**方程变成 Bellman **最优**方程。
- 只在收敛后调用一次 `greedy_from_V` 提取策略。
- 同样是原地更新；返回值 `it + 1` 是**扫描次数**（注意与 PI 返回的"外层迭代次数"含义不同，打印时分别写了 "sweeps" 和 "outer iters"）。

### 3.7 打印与交叉验证

```python
def print_policy(policy, title):
    arrows = {"up": "^", "down": "v", "left": "<", "right": ">"}
    # ...
        row = " ".join(arrows[policy[(r, c)]] if (r, c) != TERMINAL else "." for c in range(GRID))

# main() 末尾
    V_match = max(abs(V_vi[s] - V_pi[s]) for s in states())
    print(f"sup-norm |V_vi - V_pi| = {V_match:.2e}  (should be ~0)")
    print(f"policies identical?     {pi_vi == pi_pi}")
```

- 生成器表达式里嵌了条件表达式 `A if 条件 else B`，终点打印成 `.`。
- 用 sup-norm 比较两个价值函数，这是验证 DP 实现的标准做法；`:.2e` 用科学计数法打印很小的数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| `transitions` 返回完整分布 | DP 需要对 `s'` 精确求期望 | 真实环境通常拿不到模型，只能采样（MC/TD） |
| 抽出 `q_value` 公共函数 | 评估、改进、VI 共用同一个备份，减少出错 | 每次调用都重新生成 `transitions` 列表；大规模时会预先缓存成稀疏矩阵 |
| 原地更新 | 收敛更快（讲义 Pitfalls） | 结果依赖扫描顺序；同步版更易并行 |
| `ACTIONS` 用元组 + `max` 取第一个 | 稳定 tie-break，PI 能正常终止 | 无 |
| 每次策略评估从 0 开始 | 实现简单、每次调用相互独立 | 对不恰当的初始策略要上千次扫描；生产中会热启动或用修正策略迭代 |
| 用字典存 V 和策略 | 键就是状态元组，可读性好 | 大状态空间用 NumPy 数组 + 矩阵运算向量化 |
| PI 外层上限 100、VI 上限 5000 | 防止死循环 | 达到上限时应告警 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| 元组 vs 字典常量 | `ACTIONS = ("up", ...)`、`DELTAS = {...}` | 元组有固定顺序、不可修改，适合作为"动作的标准顺序" |
| `in` 判断成员 | `if action in ("up", "down")` | 检查元素是否在元组中 |
| 元组解包 | `dr, dc = DELTAS[direction]`、`for s_next, r, p in transitions(...)` | 一次拆出多个值 |
| 列表推导式（双层） | `[(r, c) for r in range(GRID) for c in range(GRID)]` | 枚举所有格子 |
| 字典推导式 | `{s: 0.0 for s in states()}`、`{s: "up" for s in states()}` | 初始化价值表、初始策略 |
| 生成器表达式 + `sum` | `sum(p * (r + gamma * V[s_next]) for ...)` | 求期望，不建中间列表 |
| 生成器表达式 + `max` | `max(q_value(state, action, V, gamma) for action in ACTIONS)` | 求最大 Q 值（返回数值） |
| `max(..., key=...)` | `max(ACTIONS, key=lambda a: q_value(...))` | 返回使 key 最大的**元素**，即 argmax；并列时返回第一个 |
| `lambda` 匿名函数 | `lambda s: {policy[s]: 1.0}` | 把字典策略包装成"状态→分布"的函数接口 |
| 条件表达式 | `arrows[...] if (r, c) != TERMINAL else "."` | 一行 if-else |
| `str.join` | `" ".join(f"{V[(r, c)]:7.2f}" for c in range(GRID))` | 用空格把字符串序列拼起来 |
| 字典相等比较 | `new_policy == policy` | 键和值都相同才为 True |
| `for ... in range(n)` + 提前 `return` | PI、VI 主循环 | 收敛就提前返回，否则跑满上限 |
| f-string 格式符 | `:7.2f`、`:.2e` | 定宽小数、科学计数法 |

---

## 6. 运行结果解读

实际运行（`python3 main.py`，约 0.2 秒）的输出：

```text
=== 4x4 stochastic GridWorld (slip=0.1), value iteration ===
  V* (converged in 15 sweeps)
     -6.43   -5.43   -4.43   -3.46
     -5.43   -4.42   -3.35   -2.32
     -4.43   -3.35   -2.27   -1.17
     -3.46   -2.32   -1.17    0.00

  optimal policy
   v > v v
   v v v v
   > > v v
   > > > .

=== Same MDP, policy iteration ===
  V* (converged in 5 outer iters)
     （与上面相同的价值表）

  optimal policy
     （与上面相同的箭头图）

sup-norm |V_vi - V_pi| = 6.26e-09  (should be ~0)
policies identical?     True
```

逐项解读：

- **`V*(0,0) = -6.43`**：确定性环境下 γ=0.99 的最优值是 `-(1 + 0.99 + … + 0.99⁵) ≈ -5.85`；滑动让期望步数增加，所以更低。讲义说"`V*(0,0) ≈ -6`"是粗略说法。
- **VI 15 次扫描**：最优策略下信息只需从终点向外传 6 步左右；原地更新又让传播加速。
- **PI 5 轮外层迭代**：但这 5 轮的内层评估分别用了约 1329、1313、1056、15、15 次扫描（另行实测），总共约 3700 次——前三轮的策略里仍有"到不了终点"的状态，价值要从 0 慢慢收敛到接近 -100。"外层少"不等于"总计算少"。
- **策略箭头**：都指向右下角。值得注意两处：
  - `(0,0)` 的 down 和 right Q 值完全相等，`max` 选了排在前面的 down（稳定 tie-break）；
  - `(0,1)` 选 right 而不是 down：贴着上墙向右走时，往上滑只是撞墙原地不动，而选 down 时往左滑会退回 `(0,0)`。随机环境中最优策略会考虑"失手时去哪"。
- **sup-norm 6.26e-09**：两种算法都在 `tol=1e-6` 处停止，剩下的差异是数值误差量级，验证了"同一个不动点"。

---

## 7. 动手改一改

1. 讲义练习 1：分别用 `gamma=0.9` 和 `0.99`、`SLIP=0.0` 跑值迭代，记录扫描次数和 `V*(0,0)`（参考：确定性时两者都约 7 次扫描）。
2. 让 `policy_evaluation` 额外返回扫描次数，修好 `policy_iteration` 里的 `sweeps`，统计 PI 的内层总扫描数，与 VI 比较。
3. 给 `policy_evaluation` 增加参数 `V0`，在 `policy_iteration` 中用上一轮的 V 热启动，看总扫描数下降多少。
4. 讲义练习 3：实现修正策略迭代（每轮评估只做 k 次扫描），比较 `k ∈ {1, 2, 5, 10, 50}`；验证 k=1 时与值迭代的扫描数一致。
5. 把 `value_iteration` 改成同步版本（新旧两张表），比较两者收敛所需的扫描次数。
6. 把 `SLIP` 调到 0.3、0.5，观察最优策略在边缘处如何变得更"保守"（更偏好贴墙走）。

---

## 8. 常见坑

- **元组顺序写错**：`transitions` 返回 `(s', r, p)`，若解包写成 `for p, r, s_next in ...` 不会报错，但会把概率当成状态去查字典（`KeyError`）或得出错误结果。
- **忘记终止态守卫**：对终止态做 `max_a` 备份，会给它赋上 -1 之类的错误价值，并通过 Bellman 方程污染所有状态。
- **平局随机打破**：如果用 `random.choice` 在并列最优动作中选，PI 的"策略稳定"检查可能永远不满足。
- **把 PI 的外层迭代次数当作计算量**：内层评估才是大头，尤其是初始策略不恰当时。
- **γ=1 + 不恰当初始策略**：本节"全部向上"策略在 γ=1 下评估会发散（价值趋向 -∞），只能跑满 `max_iter`；γ<1 才能保证收敛。
- **用平均变化量判收敛**：远离终点的少数状态还没收敛时就停了。
