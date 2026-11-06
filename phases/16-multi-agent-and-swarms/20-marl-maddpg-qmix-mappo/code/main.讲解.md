# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 20 节 多智能体强化学习（MARL）：MADDPG、QMIX、MAPPO ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

讲义明确说本节"不训练真实网络"，而是用**脚本策略**演示三个 MARL 模式：

1. **CTDE**（MADDPG）：训练时有全局视角的 critic，执行时只跑本地 actor；
2. **值分解**（QMIX）：联合 Q 是各 agent Q 的单调函数，因此可以各自 argmax；
3. **集中式 value**（MAPPO）：PPO + 看全局的 value function。

代码在一个 4×4 网格上放 2 个 agent、2 个 pellet，比较"各自追最近的 pellet"（independent）与"按全局最优分工"（三个 CTDE 风格函数）的平均完成步数。

> 一句话：**用"会不会两个人抢同一个 pellet"直观展示协调的价值**。但必须看清：这里的三个"算法"其实是**同一个集中式分配函数**，每一步执行都读取了双方位置——它展示的是"集中式协调的上限"，而不是 CTDE、值分解或集中式 value 本身。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `GRID` | 常量 | 网格边长 4 | 环境规模 |
| `Env` | dataclass | 两个 agent 位置、两个 pellet、剩余 pellet 集合 | 合作环境 |
| `Env.new` | staticmethod | 随机生成 4 个不同位置 | 初始状态分布 |
| `Env.done` | property | 剩余 pellet 为空即结束 | 终止条件 |
| `Env.collect_if_on_pellet` | 方法 | agent 站在 pellet 上即收集 | 奖励事件 |
| `manhattan` / `step_toward` | 函数 | 曼哈顿距离；朝目标走一步（先走差距大的轴） | 动作模型 |
| `move_or_wait` | 函数 | 可选择原地等待——**从未被调用** | 遗留代码 |
| `run_independent` | 函数 | 每个 agent 追离自己最近的 pellet | 独立学习（IQL）基线 |
| `_assigned_targets` | 函数 | 全局最小化两人距离和的分配 | "集中式 critic"的替身 |
| `run_maddpg_style` | 函数 | 每步调用集中式分配后各自走一步 | 讲义中的 CTDE |
| `run_qmix_style` | 函数 | 与上面逻辑相同 | 讲义中的值分解 |
| `run_mappo_style` | 函数 | 直接 `return run_maddpg_style(...)` | 讲义中的集中式 value |
| `bench` | 函数 | 500 个种子求平均步数 | 评测 |
| `main` | 函数 | 打印四行结果与（写死的）结论 | 入口 |

数据流：`main` → `bench(label, runner)` ×4 → 对种子 0–499：`Env.new(Random(i))` → `runner(env)` 循环"选目标 → 两人各走一步 → 收集"直到 done → 返回步数 → 平均。

---

## 3. 逐段精讲

### 3.1 环境：两个 pellet，两人都收集完才结束

```python
@dataclass
class Env:
    """Cooperative task: TWO pellets, each agent must collect one; step cost
    applies whether the agent moves or not; collisions (two agents same cell)
    cost an extra step."""
    agent0: tuple[int, int]
    agent1: tuple[int, int]
    pellet0: tuple[int, int]
    pellet1: tuple[int, int]
    pellets_remaining: set[tuple[int, int]] = field(default_factory=set)
```

- 环境与讲义不同：讲义写的是"one reward pellet... Reward = 1 if any agent reaches pellet"。单 pellet 时两个人都冲过去本来就是最优的，根本不需要协调；代码改成 2 个 pellet 后，"分工"才有意义。
- ⚠️ docstring 里的"碰撞多付一步"没有实现；"each agent must collect one"也不准确——实际只要两个 pellet 都被收走即可，同一个 agent 收两个也算完成。
- 奖励被简化为"完成所需步数"（越少越好），没有显式的 reward 数值。

```python
    @staticmethod
    def new(rng: random.Random) -> "Env":
        positions: set[tuple[int, int]] = set()
        while len(positions) < 4:
            positions.add((rng.randint(0, GRID - 1), rng.randint(0, GRID - 1)))
        a0, a1, p0, p1 = list(positions)
        return Env(agent0=a0, agent1=a1, pellet0=p0, pellet1=p1,
                   pellets_remaining={p0, p1})
```

- 用集合去重，保证 4 个位置互不相同（不会一开始就站在 pellet 上）。
- ⚠️ `list(positions)` 的顺序由**集合的哈希顺序**决定，而不是抽取顺序。于是"哪个位置当 agent0"并不均匀：5000 个种子里 agent0 出现在 (3,1) 930 次，出现在 (2,1) 只有 1 次。对于本实验的对比影响不大（所有策略用同一批初始状态），但生成的场景分布是有偏的。正确做法是 `rng.sample(all_cells, 4)`。

### 3.2 动作模型：先走差距大的那条轴

```python
def step_toward(pos, target):
    dx = (target[0] - pos[0])
    dy = (target[1] - pos[1])
    if abs(dx) >= abs(dy):
        nx = pos[0] + (1 if dx > 0 else -1 if dx < 0 else 0)
        ny = pos[1]
    else:
        nx = pos[0]
        ny = pos[1] + (1 if dy > 0 else -1 if dy < 0 else 0)
    nx = max(0, min(GRID - 1, nx))
    ny = max(0, min(GRID - 1, ny))
    return (nx, ny)
```

- 每步只能沿一条轴走一格，所以到达目标恰好需要曼哈顿距离那么多步。
- `1 if dx > 0 else -1 if dx < 0 else 0` 是链式条件表达式，相当于 `sign(dx)`。
- 末尾的边界截断在这里不会触发（目标总在网格内），属于防御性代码。
- `collect_if_on_pellet` 对**任何** pellet 生效：agent 路过另一个 pellet 时也会顺手收走——这让真实最优比"分配后各走各的"还略好（见 3.5）。

### 3.3 independent 基线：各自追最近

```python
        p0_target = min(env.pellets_remaining, key=lambda p: manhattan(env.agent0, p))
        p1_target = min(env.pellets_remaining, key=lambda p: manhattan(env.agent1, p))
```

- 每个 agent 只看自己与 pellet 的距离，不考虑对方——对应"把其它 agent 当环境"的独立学习。
- 当两人离同一个 pellet 最近时会一起冲过去，一个人收走后，另一个再转向剩下的 pellet，浪费步数。500 个 episode 中有 132 个比最优慢。
- 每步都重新选目标，所以是"贪心 + 动态重规划"，并非完全无脑。

### 3.4 `_assigned_targets`：集中式分配（"critic"的替身）

```python
def _assigned_targets(env: Env):
    pellets = list(env.pellets_remaining)
    if len(pellets) == 1:
        return pellets[0], pellets[0]
    p, q = pellets[0], pellets[1]
    cost_pq = manhattan(env.agent0, p) + manhattan(env.agent1, q)
    cost_qp = manhattan(env.agent0, q) + manhattan(env.agent1, p)
    return (p, q) if cost_pq <= cost_qp else (q, p)
```

- 枚举两种分工，选**距离和**更小的。两个 agent 时只有 2 种分配，暴力枚举即可；N 个 agent 时是指派问题（匈牙利算法）。
- ⚠️ **目标错配**：任务指标是"两个都收完的步数"= 两人用时的**最大值**（makespan），而这里最小化的是**和**。打平时由集合顺序决定，可能选到 makespan 更大的方案。种子 58：两种分配距离和都是 6，但完成时间一个是 3、一个是 4，代码选了 4。500 个 episode 中有 13 个因此比最优慢。按 `(makespan, 距离和)` 排序后，平均步数从 2.726 降到 2.704（测验 Q10）。
- ⚠️ **违反 CTDE 的执行约束**：这个函数读取了双方的实时位置，而且在执行时**每一步**都被调用。真正的 CTDE 只在训练时使用这类全局信息，执行时每个 agent 只能看 `o_i`。

### 3.5 三个"CTDE"函数其实是同一个策略

```python
def run_maddpg_style(env, max_steps=50):
    while not env.done and steps < max_steps:
        t0, t1 = _assigned_targets(env)
        env.agent0 = step_toward(env.agent0, t0)
        env.agent1 = step_toward(env.agent1, t1)
        env.collect_if_on_pellet()
        steps += 1

def run_qmix_style(env, max_steps=50):
    while ...:
        if len(env.pellets_remaining) >= 2:
            t0, t1 = _assigned_targets(env)
        else:
            only = next(iter(env.pellets_remaining))
            t0, t1 = only, only
        ...

def run_mappo_style(env, max_steps=50):
    return run_maddpg_style(env, max_steps)
```

- QMIX-style 在剩 1 个 pellet 时的分支与 `_assigned_targets` 的 1-pellet 分支完全等价；MAPPO-style 直接调用 MADDPG-style。所以三行输出逐位相同（2.73），这是**构造使然**，不能作为"三种算法部署时收敛到相似策略"的证据。
- QMIX 的 docstring 说"each agent picks the pellet with higher local Q (lower manhattan)"——这描述的是**各自贪心**（其实就是 independent），而代码做的是**联合分配**。真正的值分解应该是：每个 agent 有自己的 `Q_i(o_i, a_i)`，训练时通过单调混合拟合团队回报，执行时各自 argmax（见测验 Q12 的手算）。
- `next(iter(set))`：从集合中取出一个元素的惯用写法。
- 真实最优（对联合状态做 BFS）平均为 **2.698** 步；集中式分配 2.726 已经非常接近，说明这个任务里"知道对方在哪 + 合理分工"几乎就是全部。

### 3.6 `bench` 与 `main`

```python
def bench(label: str, runner) -> None:
    total = 0
    trials = 500
    for i in range(trials):
        rng = random.Random(i)
        env = Env.new(rng)
        total += runner(env)
    print(f"  {label:20s} avg_steps_to_goal = {total / trials:.2f}")
```

- 每种策略用相同的 500 个种子生成相同的初始状态，对比公平。
- `runner` 是函数作为参数传入（高阶函数）。
- 所有策略都是确定性的（初始化之后不再用随机数），所以结果完全可复现。
- `{label:20s}` 宽 20，但 "QMIX-style (mono decomp)" 等标签超过 20 个字符，所以输出没有对齐。
- ⚠️ Takeaways 写"CTDE-family variants coordinate so only the closer agent moves per step"，但代码中两人每一步都在移动；`move_or_wait` 是为"让一方等待"准备的，却从未调用。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 脚本策略、不训练 | 讲义定位为"先建立模式直觉"，训练留给阶段 09 | 无法体现 critic、混合网络、value function 的任何机制；要真正理解需用 PyMARL/MARLlib/RLlib |
| 2 个 pellet 而非讲义的 1 个 | 1 个 pellet 时不存在分工问题 | 讲义与代码不一致，预期输出也对不上 |
| 用集中式分配代表三种算法 | 代码最短 | 三行结果相同是构造使然；执行时读全局状态，违反 CTDE |
| 最小化距离和 | 指派问题的标准形式 | 与 makespan 指标错配；应按真实评价指标设计目标/奖励 |
| 集合去重生成位置 | 保证位置不重复 | 角色分配受哈希顺序影响而有偏；用 `rng.sample` |
| 每步重新分配 | 能纠正早期的次优分工 | 在真实去中心化系统里需要通信或约定 |
| 500 个固定种子 | 可复现、公平 | 没有报告方差或置信区间 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 默认工厂 | `pellets_remaining: set[...] = field(default_factory=set)` | 可变默认值必须用 `default_factory` |
| `@staticmethod` | `def new(rng) -> "Env"` | 不需要 `self`/`cls` 的工厂函数；返回类型用字符串前向引用 |
| `@property` | `def done(self) -> bool` | 像属性一样访问：`env.done`，不加括号 |
| 元组作为坐标 | `tuple[int, int]`、`(nx, ny)` | 不可变、可哈希，能放进集合 |
| 集合操作 | `positions.add(...)`、`pellets_remaining.discard(pos)` | `discard` 在元素不存在时不报错（`remove` 会报错） |
| 列表解包 | `a0, a1, p0, p1 = list(positions)` | 元素个数必须正好为 4 |
| 链式条件表达式 | `1 if dx > 0 else -1 if dx < 0 else 0` | 实现符号函数 |
| `min` + `key=lambda` | `min(env.pellets_remaining, key=lambda p: manhattan(env.agent0, p))` | 按自定义距离取最近元素 |
| 条件表达式返回元组 | `return (p, q) if cost_pq <= cost_qp else (q, p)` | 二选一 |
| `next(iter(...))` | `only = next(iter(env.pellets_remaining))` | 从集合中取任意一个元素 |
| `while` + 复合条件 | `while not env.done and steps < max_steps` | 两个条件都满足才继续，`max_steps` 防止死循环 |
| 函数作为参数 | `bench("...", run_independent)` | 高阶函数，统一评测接口 |
| f-string 格式符 | `{label:20s}`、`{total / trials:.2f}` | 左对齐宽 20；两位小数 |
| `from __future__ import annotations` | 文件开头 | 注解延迟求值 |
| `if __name__ == "__main__":` | 文件末尾 | 作为脚本运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3，耗时约 0.08 秒）：

```text
========================================================================
MARL PATTERNS on a 4x4 grid with 2 agents and 2 pellets (cooperative)
========================================================================
  independent (no coord) avg_steps_to_goal = 3.21
  MADDPG-style (CTDE)  avg_steps_to_goal = 2.73
  QMIX-style (mono decomp) avg_steps_to_goal = 2.73
  MAPPO-style (centralized V) avg_steps_to_goal = 2.73
```

逐项解读：

- **independent 3.21 vs 分工 2.73**：差 0.49 步（约 15%），来自"两人抢同一个 pellet"。讲义预期"independent ~6 步、CTDE ~3.5 步、最优 3 步"，与代码完全对不上——讲义描述的是单 pellet 环境与另一套实现。
- **三行 2.73 完全相同**：见 3.5，是同一个函数。
- **与真实最优比较**（临时脚本用 BFS 搜索联合状态空间，不修改原文件）：

| 策略 | 4×4 | 6×6 | 比最优慢的 episode 数（4×4，共 500） |
|------|-----|-----|-------------------------------|
| independent | 3.212 | 4.654 | 132 |
| 本地约定（agent0 取坐标较小的 pellet） | 3.154 | 4.548 | — |
| 集中式分配（原代码，三个 CTDE 函数） | 2.726 | 4.014 | 13 |
| 集中式分配（makespan 优先修正版） | 2.704 | 3.96 | — |
| BFS 真实最优 | 2.698 | 3.944 | 0 |

- **讲义练习 1（6×6）**：independent 与 MAPPO-style 的差距绝对值从 0.486 增大到 0.640 步，相对值从 15.1% 略降到 13.8%。
- **"本地约定"这一行最有启发**：只用本地信息、靠事先约定分工，只比 independent 好一点；集中式分配好得多，但它在执行时用了全局信息。CTDE 要解决的正是"如何在训练时借助全局信息，学出一个执行时只看本地也能接近集中式效果的策略"。

---

## 7. 动手改一改

1. **修正目标函数**：把 `_assigned_targets` 改为按 `(makespan, 距离和)` 排序，验证 4×4 平均步数从 2.726 降到约 2.704（测验 Q10）。
2. **真正的去中心化执行**：写一个 `run_decentralized(env)`，每个 agent 的决策函数只接收 `(自己的位置, pellet 列表)`；尝试不同约定（按坐标排序、按到"网格中心"的距离等），看能否逼近 2.73。
3. **修复初始化偏差**：用 `rng.sample([(x, y) for x in range(GRID) for y in range(GRID)], 4)` 生成位置，比较结果是否变化。
4. **竞争版本**（讲义练习 2）：只有一个 pellet、先到者得奖励。分析在这个设定下"分工"还有意义吗？每个 agent 的最优策略是什么？
5. **把 QMIX 做成真的**：为每个 agent 建一张表格 `Q_i[(自己位置, 剩余 pellet), 动作]`，用 VDN（`Q_tot = Q_1 + Q_2`）在这个环境上做表格 Q-learning，执行时各自 argmax，比较学到的策略与集中式分配的差距。
6. **规模扩展**：改成 3 个 agent、3 个 pellet，把 `_assigned_targets` 换成枚举全排列（`itertools.permutations`），观察 independent 与分工的差距如何变化。

---

## 8. 常见坑

- **把"集中式调度"当成 CTDE**：执行时每步都读全局状态，就是集中式执行。检查每个 agent 的决策函数到底接收了什么输入。
- **多个"算法"共用一个实现**：结果相同不是算法等价的证据；对比实验前先确认各分支代码真的不同。
- **目标函数与评价指标错配**：最小化距离和 ≠ 最小化完成时间。MARL 对奖励设计极其敏感，这是讲义 Ship It 的重点之一。
- **用集合顺序决定角色/平局**：`list(set)` 的顺序由哈希决定，不是随机，也不是插入顺序；需要随机就显式用 `rng`。
- **单 pellet 任务谈协调**：如果任一 agent 到达即成功，两人都冲过去就是最优，不存在协调问题。设计实验前先确认任务里确实有"分工收益"。
- **忽略非平稳性**：本代码没有学习，所以看不到非平稳问题；一旦两个 agent 同时学习，每个人的"环境"都在变，独立 Q-learning 可能不收敛。
