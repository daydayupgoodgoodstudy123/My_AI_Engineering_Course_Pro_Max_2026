# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 21 节 Agent 经济体系、Token 激励与声誉 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`math`、`random`、`dataclasses`、`itertools`、`typing`）

---

## 1. 这份代码在考察什么

讲义把 agent 经济拆成三类问题：**信用分配**、**机制设计**、**声誉**。代码各用一个最小演示落地：

1. **Shapley 信用分配**：3 个 agent（coder、researcher、reviewer）合作，给出一张 8 个联盟的价值表，用精确枚举与 200 次采样计算各自的 Shapley 值。
2. **第二价格拍卖**：5 个 agent 竞标一个任务槽，最高者赢、支付第二高价。
3. **声誉加权路由**：4 个真实质量不同的 agent，100 个任务（前 50 个随机预热），用 EMA 声誉按比例路由，与随机路由比较平均质量。

> 一句话：**把"谁该拿多少、怎么定价、该信任谁"三个问题各变成十几行可运行的数学**。Shapley 部分完全正确；拍卖部分只打印了"truthful"而没有演示；声誉部分缺 slashing，且参数设置让路由收益远低于讲义的预期。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `shapley_exact` | 函数 | 枚举所有排列，累加边际贡献再除以 N! | Shapley value（精确） |
| `shapley_sampled` | 函数 | 随机打乱 K 次，平均边际贡献 | Monte Carlo Shapley |
| `Bid` | dataclass | 出价者 + 出价 | 拍卖输入 |
| `second_price` | 函数 | 排序取最高者为赢家，支付第二高价 | Vickrey 拍卖 |
| `Reputation` | 类 | EMA 更新、下限 floor、读取权重 | 声誉资本 |
| `weighted_choice` | 函数 | 按权重比例的轮盘赌抽样 | 声誉加权路由 |
| `demo_shapley` | 函数 | 3 人价值表 → 精确与采样 Shapley | Demo 1 |
| `demo_auction` | 函数 | 5 个出价 → 赢家与支付 | Demo 2 |
| `demo_reputation_routing` | 函数 | 随机 vs 声誉路由，各 100 个任务 | Demo 3 |
| `main` | 函数 | 依次运行三个 demo，打印结论 | 入口 |

数据流：`main` → `demo_shapley`（`base` 字典 → `value_fn` → `shapley_exact` / `shapley_sampled`）→ `demo_auction`（`bids` → `second_price`）→ `demo_reputation_routing`（随机路由循环；`Reputation` + `weighted_choice` 循环）→ 打印。

---

## 3. 逐段精讲

### 3.1 精确 Shapley：枚举排列

```python
def shapley_exact(value_fn: Callable[[frozenset], float], agents: list[str]) -> dict[str, float]:
    n = len(agents)
    contribs = {a: 0.0 for a in agents}
    for order in permutations(agents):
        visited: set[str] = set()
        prev_value = value_fn(frozenset(visited))
        for a in order:
            visited.add(a)
            new_value = value_fn(frozenset(visited))
            contribs[a] += new_value - prev_value
            prev_value = new_value
    factorial = math.factorial(n)
    return {a: v / factorial for a, v in contribs.items()}
```

- 直接实现讲义公式 `shapley(i) = (1/N!) Σ_O [v(S_i^O ∪ {i}) − v(S_i^O)]`：对每个加入顺序，按顺序把 agent 一个个加入联盟，记录每人加入时价值的增量。
- `frozenset`：价值函数的键必须可哈希，而普通 `set` 不可哈希，所以每次都把 `visited` 冻结成 `frozenset` 再查表。`frozenset(["coder", "researcher"])` 与 `frozenset(["researcher", "coder"])` 相等，顺序无关——这正是"联盟"的语义。
- **效率公理自动成立**：每个排列里边际贡献依次相加正好等于 `v(N) − v(∅)`，所以平均后总和也等于 `v(N)`（输出 `sum = 1.0000`）。
- 复杂度：N! 个排列 × N 次 value 调用。实测（一个 10 人价值函数）：N = 8 用时 0.26 s，N = 9 用时 3.06 s，N = 10 用时 37.6 s。
- ⚠️ 模块 docstring 说"exact for N<=6 and sampled otherwise"，但代码中没有任何根据 N 自动切换的逻辑；两个函数需要调用方自己选。

### 3.2 采样 Shapley

```python
def shapley_sampled(value_fn, agents, samples: int, rng: random.Random):
    contribs = {a: 0.0 for a in agents}
    for _ in range(samples):
        order = list(agents)
        rng.shuffle(order)
        ...
    return {a: v / samples for a, v in contribs.items()}
```

- 与精确版完全相同，只是把"所有排列"换成"K 个均匀随机排列"，是无偏估计。
- `order = list(agents)` 先复制再 `shuffle`，避免打乱调用方传入的列表。
- 采样版**不保证**每个人的估计值精确，但仍满足效率公理（每个排列的增量和恒为 `v(N)`）。实测：三人例子中误差约按 `1/√K` 下降（K = 10 → 0.020，K = 1000 → 0.002）；10 人时 K = 100 的平均最大误差为 0.033，对 Shapley 值只有 0.06 的 agent 而言相对误差很大。
- 实际系统中可以缓存联盟价值（只有 2^N 个不同联盟），避免重复调用昂贵的 value_fn。

### 3.3 第二价格拍卖

```python
@dataclass
class Bid:
    bidder: str
    value: float


def second_price(bids: list[Bid]) -> tuple[str, float] | None:
    if len(bids) < 2:
        return None
    sorted_bids = sorted(bids, key=lambda b: b.value, reverse=True)
    winner = sorted_bids[0].bidder
    payment = sorted_bids[1].value
    return winner, payment
```

- 规则就是讲义的 Vickrey 拍卖：最高价赢，付第二高价。
- `sorted(..., reverse=True)` 是稳定排序：平局时先出现在列表里的人赢，这是隐含的平局规则。
- 少于 2 个出价返回 `None`——生产中通常用保留价（reserve price）处理单一出价。
- ⚠️ 讲义预期输出"auction result showing truthful-bid equilibrium"，但代码只打印了一句"(winner pays second-highest bid; this is truthful)"，没有任何演示。可以枚举偏离来验证（测验 Q10）：agent-a 多报到 0.96 会赢但要付 0.95，收益 −0.13；agent-c 少报到 0.83 支付不变，少报到 0.80 就输掉 0.13 的收益。
- ⚠️ "Monotone aggregation"是 Google Research 那篇工作对 LLM token 聚合的条件，这个单物品拍卖 demo 并没有涉及任何聚合函数。

### 3.4 `Reputation`：EMA + 下限

```python
class Reputation:
    def __init__(self, alpha: float = 0.95, floor: float = 0.1) -> None:
        self.alpha = alpha
        self.floor = floor
        self.scores: dict[str, float] = {}

    def init(self, agents: list[str]) -> None:
        for a in agents:
            self.scores[a] = 1.0

    def update(self, agent: str, quality: float) -> None:
        current = self.scores.get(agent, 1.0)
        self.scores[agent] = max(self.floor, self.alpha * current + (1 - self.alpha) * quality)
```

- `update` 就是讲义公式 `rep(t+1) = α·rep(t) + (1 − α)·quality(t)`，再用 `max(floor, ...)` 保证不低于 0.1（讲义 Ship It "floor reputation"）。
- ⚠️ **初始声誉 1.0 过高**：真实质量最高也只有 0.9，新 agent 一注册就是"全场最高声誉"。配合 `α = 0.95`，一个 agent 被选中 11 次后初始值仍占 `0.95^11 ≈ 0.57` 的权重。这还是一个 **Sybil 漏洞**：被惩罚的运营方换个新身份就能拿回最高声誉，与讲义"expensive to forge"相矛盾。
- ⚠️ **没有 slashing**：讲义和 Takeaways 都提到"decay + slashing"，代码里没有任何扣分方法。
- ⚠️ **衰减只发生在"被选中时"**：没被选中的 agent 声誉永远不变。技能文件把"没有衰减的声誉"列为硬拒绝；严格说这里只有"按使用的 EMA"，没有按时间的衰减。
- 没有上限（ceiling）。

### 3.5 `weighted_choice`：按声誉比例抽样

```python
def weighted_choice(agents, weights, rng):
    total = sum(weights)
    r = rng.random() * total
    upto = 0.0
    for a, w in zip(agents, weights):
        upto += w
        if r <= upto:
            return a
    return agents[-1]
```

- 与上一节 ACO 路由的轮盘赌完全相同；标准库也有现成的 `rng.choices(agents, weights=weights)[0]`。
- 按比例抽样意味着"差的 agent 也有可观的概率被选中"：即使声誉完全等于真实质量，alpha（0.9）也只有约 37% 的概率被选中。

### 3.6 Demo 3：同一种子让预热阶段完全相同

```python
    rng = random.Random(0)
    random_quality = 0.0
    for _ in range(100):
        a = rng.choice(agents)
        q = max(0.0, min(1.0, true_quality[a] + rng.uniform(-0.1, 0.1)))
        random_quality += q

    rng = random.Random(0)
    rep = Reputation()
    rep.init(agents)
    rep_quality = 0.0
    for i in range(100):
        if i < 50:
            a = rng.choice(agents)  # warmup: learn everyone
        else:
            a = weighted_choice(agents, rep.weights(agents), rng)
        q = max(0.0, min(1.0, true_quality[a] + rng.uniform(-0.1, 0.1)))
        rep.update(a, q)
        rep_quality += q
```

- 两段都从 `Random(0)` 开始，且预热阶段的随机数消耗顺序相同（`choice` 后接 `uniform`），因此**前 50 个任务的选择与质量逐个相同**（已验证）。这是一种"共同随机数"的对照设计：差异只来自后 50 个任务。
- ⚠️ 但提升是按 100 个任务平均计算的，前 50 个相同的任务把差距稀释了一半。只看后 50 个任务：本种子随机 0.622、声誉 0.667（约 +7%）；200 个种子平均也是约 +7%。
- 讲义预期"10–20% quality gain after warmup"，原代码默认参数达不到。改参数的效果（200 个种子、后 50 个任务）：α = 0.8 → +13.7%；初始声誉 0.5 → +9.9%；改为贪心选最高声誉 → +46.9%（但完全不探索）。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 价值函数用手写字典 | 让 Shapley 的计算一目了然 | 真实 v(S) 需要一次评测（重跑测试、LLM 评审），要缓存联盟价值、控制成本 |
| 同时提供精确与采样 Shapley | 对比精度与成本 | docstring 声称的自动切换并未实现；技能文件规定 N > 6 用采样 |
| 单物品第二价格拍卖 | 最简单的 truthful 机制 | 没有保留价、没有串通防护；也没有演示 truthfulness |
| EMA 声誉 + floor | 一行公式即可 | 初始值 1.0 过高（Sybil 漏洞）、无 slashing、无时间衰减、无上限 |
| 按声誉比例路由 | 自带探索 | 收益有限；生产常用 softmax/ε-greedy/Thompson sampling |
| 共同随机数做对照 | 降低比较方差 | 汇报口径应只看预热后的任务 |
| 所有数字硬编码 | 可复现、易读 | 没有多种子统计与置信区间 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `typing.Callable` | `Callable[[frozenset], float]` | 注解"接收一个 frozenset、返回 float 的函数" |
| `itertools.permutations` | `for order in permutations(agents)` | 生成全部 N! 个排列（惰性生成器） |
| `frozenset` | `frozenset(visited)`、`frozenset(["coder"])` | 不可变集合，可以作为字典键；元素顺序无关 |
| 字典推导式 | `{a: 0.0 for a in agents}`、`{a: v / factorial for a, v in contribs.items()}` | 一行构造/变换字典 |
| `lambda` | `value_fn = lambda s: base[s]`、`key=lambda b: b.value` | 匿名函数；前者把字典包装成函数 |
| `math.factorial` | `math.factorial(n)` | 阶乘 |
| `random.shuffle` | `rng.shuffle(order)` | 原地打乱列表 |
| `@dataclass` | `class Bid` | 自动生成构造函数等 |
| 联合类型返回 | `tuple[str, float] \| None` | 可能返回元组，也可能返回 `None` |
| `sorted` + `reverse` | `sorted(bids, key=..., reverse=True)` | 降序稳定排序 |
| `if result:` 判空 | `result = second_price(bids); if result:` | `None` 为假，非空元组为真 |
| `dict.get` 默认值 | `self.scores.get(agent, 1.0)` | 键不存在时返回默认值 |
| `zip` | `for a, w in zip(agents, weights)` | 并行遍历两个列表 |
| 列表推导式 | `[self.scores.get(a, 1.0) for a in agents]` | 按顺序取权重 |
| clamp | `max(0.0, min(1.0, x))` | 把质量夹在 [0, 1] |
| f-string 格式符 | `{v:.4f}`、`{a:11s}`、`{x:+.1f}%` | 四位小数；左对齐宽 11；带正负号 |
| `"=" * 72` | 分隔线 | 字符串重复 |

---

## 6. 运行结果解读

实际运行（Python 3，耗时约 0.04 秒）：

```text
SHAPLEY ATTRIBUTION — 3 agents collaborate on a task
  exact Shapley values:
    coder       0.5083
    researcher  0.3333
    reviewer    0.1583
    sum = 1.0000 (should equal grand coalition value 1.0000)
  sampled Shapley values (N=200):
    coder       0.5117
    researcher  0.3317
    reviewer    0.1565

SECOND-PRICE AUCTION — 5 bidders compete for a task slot
  winner: agent-c  payment: 0.82

REPUTATION-WEIGHTED ROUTING — 100 tasks, 4 agents, 50 warmup
  random routing avg quality:   0.627
  rep-weighted routing:         0.650
  improvement: +3.6%
  final reputation scores:
    alpha    rep=0.918  true=0.90
    beta     rep=0.645  true=0.50
    gamma    rep=0.810  true=0.75
    delta    rep=0.565  true=0.30
```

逐项解读：

- **Shapley**：可以手算验证。coder = `(1/3)·0.5 + (1/6)·(0.85 − 0.3) + (1/6)·(0.70 − 0.1) + (1/3)·(1 − 0.55) = 0.5083`。三人之和为 1，满足效率公理。reviewer 拿到 0.158，多于"按单人能力成比例"的 0.111，因为它和别人组合时有协同。
- **采样**：200 次采样的误差在 0.004 以内，三人场景下已经足够。
- **拍卖**：c 以 0.95 赢、付 0.82（a 的出价）。truthful 的性质需要你自己枚举偏离来验证。
- **声誉路由 +3.6%**：远低于讲义的"10–20%"。原因：(1) 初始 1.0、α = 0.95 让声誉长期偏高（最终 delta 仍有 0.565，真实只有 0.3；beta 0.645 vs 0.5）；(2) 按比例抽样，最终权重下 delta 仍有约 19% 的概率被选中；(3) 前 50 个任务两边完全相同，提升被稀释一半。最终声誉的**排序**是对的（alpha > gamma > beta > delta），但**数值**普遍偏高——讲义说声誉"便宜可读"，前提是它已经收敛。

---

## 7. 动手改一改

1. **公理实验**（讲义练习 1）：把 reviewer 的所有增量改为 0，确认它的 Shapley 值为 0（null 公理）；把 coder 与 researcher 改成完全对称，确认两人份额相等（对称公理）。
2. **采样精度**（讲义练习 2、5）：对 N = 4 和 N = 10 的价值函数，画出 K ∈ {10, 100, 1000, 10000} 的误差曲线；为 `shapley_sampled` 加上联盟价值缓存，统计实际 value_fn 调用次数。
3. **演示 truthfulness**：写一个函数，对每个出价者枚举"报价 ∈ [0, 1] 网格"，在其他人不变的情况下计算收益，验证如实报价总是收益最高之一；再改成第一价格拍卖，看看最优报价变成什么。
4. **补全声誉系统**：加入 `slash`、时间衰减 `tick`、上限 `ceiling`，把新身份初始值改为 0.3（参考测验 Q12 的实现），再跑一个"坏 agent 被 slash 后换新身份"的 Sybil 场景，比较修改前后它能拿到的流量。
5. **更好的路由**：把 `weighted_choice` 换成 softmax（温度 τ）和 ε-greedy，在 200 个种子上只统计后 50 个任务，比较与随机路由的差距；再在第 75 个任务把 alpha 的质量降到 0.4，观察哪种策略最快发现。
6. **联盟竞标**（讲义练习 3）：允许 agent 组队，以"联盟价值"出价参与第二价格拍卖，用 Shapley 在队内分配收益。

---

## 8. 常见坑

- **用普通 `set` 当字典键**：会报 `TypeError: unhashable type: 'set'`，必须用 `frozenset`。
- **精确 Shapley 用在大 N 上**：N = 10 已需约 37 秒（本地实测），value_fn 若是一次 LLM 评测则完全不可行。
- **只汇报"总体提升"**：包含预热阶段的平均会稀释差距；应单独报告预热后的指标，并给出多种子统计。
- **初始声誉设成最高值**：新身份立即拥有最高信任，等于邀请 Sybil 攻击，也让 slashing 失去意义。
- **只在使用时衰减**：长期未被选中的 agent 声誉被"冻结"，既可能是过时的高分，也可能是永远翻不了身的低分。
- **把"truthful"当成无条件成立**：串通、保留价缺失、多物品、非单调聚合都会破坏它。
- **相信价值函数**：Shapley 只是把 v 公平地分下去；v 若可被操纵，分配也会被操纵——先验证再奖励。
