# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 18 节 心智理论与涌现协调 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`）

---

## 1. 这份代码在考察什么

这份约 160 行的脚本搭了一个"无通信的分箱子"合作游戏，比较两种 agent：

1. **零阶 agent（zeroth-order）**：不建模他人，每轮在剩余箱子里均匀随机挑一个。
2. **一阶 ToM agent（first-order）**：记录"观察到的别人目标"，挑选时避开别人最近瞄准的箱子。

它对应讲义的几个概念：

- ToM 的阶数：`tom=False/True` 就是 0 阶与 1 阶的开关；
- "协调可以被度量"：用**碰撞数（duplications）**和**完成轮数**衡量协调，而不是凭感觉；
- "协调是条件依赖的，不是免费的"（Riedl 2025）：ToM agent 的优势完全来自第 0 轮注入的"偏好先验"（prime），去掉它效应就消失。

> 一句话：**用一个可计数的小游戏演示"协调效应要靠对照实验来度量"**——而读懂代码后你会发现，它最有教育意义的地方恰恰是：这里的"ToM 收益"全部来自 prime，ToM 推理本身在这个游戏里不产生任何信息。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `World` | dataclass | 箱子总数与"仍有 token 的箱子集合" | 共享环境 |
| `World.new` | classmethod | 构造所有箱子都有 token 的初始世界 | 工厂方法 |
| `Agent` | dataclass | 名字、是否 ToM、是否已领取、观察记录 | agent 状态（`observations` 即简化的 ToM 状态） |
| `Agent.choose_target` | 方法 | 零阶随机 / 一阶避开他人近期目标 | 行动选择 |
| `Agent.observe` | 方法 | 追加 `(他人名字, 箱子)` | 观察更新 |
| `run_trial` | 函数 | 一次试验：prime → 多轮"承诺—观察—计碰撞—结算" | 合作任务 |
| `bench` | 函数 | 200 个种子汇总完成数、碰撞数、轮数 | 度量 |
| `main` | 函数 | 打印两种配置的结果和（写死的）结论 | 入口 |

数据流：`main` → `bench(tom)` ×2 → 循环 200 次 `run_trial(seed=t)` → 每轮 `choose_target` → `observe` → 统计碰撞 → 结算领取 → 返回 `(完成数, 碰撞数, 轮数)` → 汇总打印。

---

## 3. 逐段精讲

### 3.1 `World`：只记"哪些箱子还有 token"

```python
@dataclass
class World:
    n_boxes: int
    boxes_with_tokens: set[int]

    @classmethod
    def new(cls, n: int) -> "World":
        return cls(n_boxes=n, boxes_with_tokens=set(range(n)))
```

- 世界状态极简：一个整数集合。领取 token 就是 `discard(box)`。
- `@classmethod` 工厂方法让调用方写 `World.new(3)` 而不用自己拼 `set(range(3))`。
- 没有位置、距离、移动——这一点很关键：**agent 的"意图"与"兑现"发生在同一轮**，见 3.5。

### 3.2 `Agent` 与两种选择策略

```python
@dataclass
class Agent:
    name: str
    tom: bool
    target: int | None = None
    collected: bool = False
    observations: list[tuple[str, int]] = field(default_factory=list)
```

- `observations` 是讲义里 `other_models` 的极简替身：只存 `(谁, 哪个箱子)` 的流水，没有按 agent 分组的信念字典，也没有 2 阶嵌套。
- `target` 字段从未被使用（定义了但没赋值），是遗留字段。
- `field(default_factory=list)`：可变默认值必须这样写，否则所有实例会共享同一个列表。

```python
    def choose_target(self, world: World, rng: random.Random) -> int:
        if self.collected:
            return -1
        available = sorted(world.boxes_with_tokens)
        if not available:
            return -1
        if not self.tom:
            return rng.choice(available)
        last_turn_targets = {box for _, box in self.observations[-(len(world.boxes_with_tokens) + 2):]}
        options = [b for b in available if b not in last_turn_targets]
        return rng.choice(options) if options else rng.choice(available)
```

- 返回 `-1` 表示"不行动"（已完成或无箱可选）。
- `sorted(...)`：集合无序，排序后再 `rng.choice` 才能保证同一种子结果可复现。
- **零阶**：`rng.choice(available)`，完全不看历史。
- **一阶**：取最近若干条观察，避开其中出现的箱子；如果全被避开就退回随机。
- ⚠️ 窗口长度是 `len(剩余箱子) + 2`，与"上一轮有几个 agent 行动"无关。变量名叫 `last_turn_targets`，但实际上可能包含更早轮次的观察，也可能装不下一整轮（agent 多、箱子少时）。这是一个随手写的启发式，不是严格的"上一轮"。

### 3.3 prime：给 ToM agent 的"偏好广播"

```python
    if tom:
        for i, a in enumerate(agents):
            for j, other in enumerate(agents):
                if i != j:
                    a.observe(other.name, j % n_boxes)
```

- 每个 ToM agent 预先"看到"其它 agent-j 偏好箱子 `j % n_boxes`。3×3 时 agent-0 的观察是 `[("agent-1",1), ("agent-2",2)]`。
- 结合 3.2：agent-0 的 `last_turn_targets={1,2}`，`options=[0]`——**确定性地去 0 号箱**。agent-1、agent-2 同理。于是第一轮就无碰撞全部完成。
- docstring 坦白这是"simulating a cheap communication channel"。⚠️ 与讲义"Agents cannot communicate; they infer intent from each other's actions"矛盾：这里的协调来自**预先的信息注入（等价于角色分配）**，而不是从动作推断意图。

### 3.4 每一轮：承诺 → 观察 → 计碰撞

```python
        commitments: dict[str, int] = {}
        for a in agents:
            if a.collected:
                continue
            choice = a.choose_target(world, rng)
            if choice < 0:
                continue
            commitments[a.name] = choice

        for observer in agents:
            for other, box in commitments.items():
                if other == observer.name:
                    continue
                observer.observe(other, box)

        choices = list(commitments.values())
        for box in set(choices):
            n = choices.count(box)
            if n >= 2:
                duplications += n - 1
```

- 所有未完成 agent **同时**做决定（因为观察是在全部承诺之后才写入的）。
- 每个 agent 都会记录别人的承诺——零阶 agent 也记，只是不用。
- 碰撞计数：一个箱子被 n 个 agent 同时选中，记 n−1 次（多出来的人白跑一趟）。

### 3.5 结算：字典插入顺序决定谁赢

```python
        taken: set[int] = set()
        for name, box in commitments.items():
            if box in taken:
                continue
            if box in world.boxes_with_tokens:
                world.boxes_with_tokens.discard(box)
                for a in agents:
                    if a.name == name:
                        a.collected = True
                taken.add(box)
```

- Python 3.7+ 的 dict 保持插入顺序，所以碰撞时**编号小的 agent 永远获胜**（agent-0 > agent-1 > agent-2）。这是一个确定性偏置，不影响碰撞数统计，但若要研究"角色分化"会引入假信号。
- **关键结构性质**：被承诺的每个箱子在本轮**至少有一人领到**。由此得到两个推论：
  1. n_agents = n_boxes 时，每轮至少消耗一个箱子，3×3 最多 3 轮（2000 个种子实测最大轮数 = 3），10 轮预算永远用不完，所以"完成率"恒为 100%；
  2. 本轮被瞄准过的箱子到下一轮全都不在 `available` 里了。于是**没有 prime 时，ToM 的"避开别人目标"永远过滤不掉任何候选**，ToM agent 与零阶 agent 的行为（连同随机数消耗）逐位相同。实测去掉 prime 后两者都是 `dups=0.965, turns=1.855`。
- 用 `for a in agents: if a.name == name` 线性查找 agent，O(n)；用 `dict[name → Agent]` 更直接。

### 3.6 `bench` 与 `main`

```python
        c, d, turns = run_trial(n_agents=3, n_boxes=3, tom=tom, seed=t)
        ...
        if c == 3:
            full_trials += 1
```

- 种子就是试验编号 `t`，两种配置用同一批种子，可复现。
- ⚠️ `c == 3` 写死；改成别的 agent/箱子数时应写 `c == min(n_agents, n_boxes)`。
- `main` 里的 Takeaways 全是**硬编码字符串**（"0.96 duplications"等），不随运行结果变化。还写了"long-horizon degradation ... with max_turns=30"——但本任务最多 3 轮就结束，把 `max_turns` 调到 30 不会有任何变化。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用碰撞数、轮数作为协调指标 | 可计数、可对照，呼应"先度量再宣称" | 只是 complementarity 的最简形式；没有实现 anticipation、correction 和 Riedl 的 synergy 统计 |
| 观察流水代替 `other_models` 字典 | 代码短 | 无法区分"身份混淆"和"内容幻觉"；生产中应按 agent 分组并附来源/时间戳 |
| 第 0 轮 prime | 让 ToM agent 有可用信息 | 等价于预先分配角色，与"不能通信"设定矛盾；应改成"意图在兑现前可观察"的任务（如多轮移动） |
| 承诺与领取在同一轮 | 实现简单 | 导致从动作推断意图毫无信息量（去掉 prime 后 ToM = 零阶） |
| 碰撞按 dict 插入顺序裁决 | 确定、可复现 | agent-0 永远赢；研究角色分化时应随机裁决 |
| 结论文字硬编码 | 演示方便 | 改参数后与实际输出不符；应从统计结果生成 |
| 200 个固定种子 | 可复现 | 没有做显著性检验；讲义 Ship It 要求 p < 0.05 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `from __future__ import annotations` | 文件开头 | 注解延迟求值，允许在较老版本中写 `set[int]`、`int \| None` |
| `@dataclass` | `class World`、`class Agent` | 自动生成 `__init__`、`__repr__`、`__eq__` |
| `field(default_factory=list)` | `observations: list[...] = field(default_factory=list)` | 可变默认值的正确写法，每个实例一个新列表 |
| `@classmethod` 工厂 | `def new(cls, n) -> "World"` | 第一个参数是类本身；返回类型用字符串前向引用 |
| 类型注解 | `int \| None`、`list[tuple[str, int]]`、`dict[str, int]` | 只做文档/静态检查，运行时不强制 |
| 独立随机数生成器 | `rng = random.Random(seed)` | 每次试验独立、可复现，不污染全局 `random` |
| 集合推导式 | `{box for _, box in self.observations[...]}` | 生成去重集合；`_` 表示忽略元组第一个元素 |
| 列表推导式 + 条件 | `[b for b in available if b not in last_turn_targets]` | 过滤 |
| 负数切片 | `self.observations[-(k + 2):]` | 取最后 k+2 个元素，列表不够长时返回全部 |
| 条件表达式 | `rng.choice(options) if options else rng.choice(available)` | 空列表为假 |
| `enumerate` 嵌套 | `for i, a in enumerate(agents): for j, other in enumerate(agents)` | 同时取下标与元素 |
| dict 保序迭代 | `for name, box in commitments.items()` | Python 3.7+ 保证插入顺序，决定了碰撞胜者 |
| `list.count` | `choices.count(box)` | 统计元素出现次数 |
| 生成器表达式 + `all`/`sum` | `all(a.collected for a in agents)`、`sum(1 for a in agents if a.collected)` | 不建中间列表 |
| 元组返回与解包 | `return completions, duplications, turns` / `c, d, turns = run_trial(...)` | 多返回值 |
| f-string 格式符 | `{label:16s}`、`{tot_dup/trials:.2f}` | 左对齐宽 16 的字符串；两位小数 |
| `if __name__ == "__main__":` | 文件末尾 | 被 import 时不自动运行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3，耗时约 0.05 秒）：

```text
========================================================================
TOKEN-COLLECTION — 3 agents, 3 boxes, 10-turn budget, 200 trials each
agents cannot communicate; they observe each other's movements
========================================================================
  zeroth-order     full-completion=200/200   duplications/trial=0.96  avg_turns=1.85
  first-order ToM  full-completion=200/200   duplications/trial=0.00  avg_turns=1.00

Takeaways:
  zeroth-order agents collide on a shared box ~1x per trial (0.96 duplications).
  first-order ToM agents, given a cheap preference prime, eliminate collisions
  and finish in 1 turn instead of ~2.
  ...
```

逐项解读：

- **两者都是 200/200 完成**：与讲义"Expected output"（零阶约 60%、ToM 约 95%）不符。原因见 3.5：在 3×3 设定下每轮至少消耗一个箱子，最多 3 轮必然完成。
- **零阶 0.96 碰撞 / 1.85 轮**：理论期望可精确计算为 17/18 ≈ 0.944 与 11/6 ≈ 1.833（测验 Q10）；2000 次试验实测 0.926 / 1.826。讲义说的"~35% duplication rate"没有对应的计量口径。
- **ToM 0.00 / 1.00**：prime 使每个 agent 确定性地去自己编号的箱子。讲义练习 1 说"减少约 7 倍"，实际是从 0.96 降到 0，且这个差距完全来自 prime。
- **补充实验**（临时脚本，未修改原文件）：

| 实验 | 零阶 dups / 轮数 | ToM dups / 轮数 |
|------|----------------|----------------|
| 原设定 3×3 | 0.96 / 1.85 | 0.00 / 1.00 |
| 去掉 prime | 0.965 / 1.855 | **0.965 / 1.855（逐位相同）** |
| 5×5 | 1.97 / 2.29 | 0.00 / 1.00 |
| 3 agent × 5 box | 0.555 / 1.53 | 0.635 / 1.57（ToM 更差） |
| ToM + 每轮必翻一条信念（hallucination） | — | 0.89 / 1.79 |

这张表就是本节最好的教材：**效应在对照组下消失、在不同规模下符号会翻转、对单点信念错误极其敏感**——正对应讲义"coordination emergence is prompt-conditional"的论点。

---

## 7. 动手改一改

1. **对照组**：给 `run_trial` 加一个参数 `prime: bool`，跑出"ToM + prime / ToM 无 prime / 零阶"三行，验证中间一行与零阶完全相同。
2. **修正统计口径**：把 `bench` 的 `c == 3` 改为 `c == min(n_agents, n_boxes)`；把 Takeaways 改成根据实际统计值生成；再加一列"碰撞率 = 有碰撞的试验数 / 试验数"，看看讲义"35%"可能指什么。
3. **hallucination 注入**（讲义练习 3）：每次 `choose_target` 前以概率 p 翻转一条观察，画出 p 与碰撞数的曲线（参考测验 Q12）。再写一个"身份混淆"版本（交换两条记录的 agent 名），对比两种错误的破坏力。
4. **让意图可观察**：给每个箱子一个距离（例如 2 轮路程），agent 每轮移动一步并公开当前位置；ToM agent 根据他人移动方向推断目标并改道。去掉 prime，比较 ToM 与零阶——这时测到的差距才是"从动作推断意图"的价值。
5. **2 阶 ToM**（讲义练习 2）：把 `observations` 改成 `other_models: dict[str, dict]`，并为每个他人再存一份"他认为别人会去哪"；在练习 4 的移动版任务中比较 1 阶与 2 阶。
6. **显著性检验**：对零阶与 ToM 的每次试验碰撞数做置换检验（permutation test，用标准库 `random.shuffle` 即可），报告 p 值，对应讲义 Ship It 清单。

---

## 8. 常见坑

- **把 prime 当成 ToM 能力**：先跑对照组再下结论。本代码去掉 prime 后效应为零。
- **任务结构让指标失去意义**：n_agents = n_boxes 且每轮必有人领到，完成率恒为 100%，"完成率"这个指标在这里没有区分度。
- **变量名误导**：`last_turn_targets` 并不严格是"上一轮"，窗口长度是 `剩余箱子数 + 2`。
- **agent 多于箱子时死循环到预算上限**：5×3 时 `all(collected)` 永远为假，跑满 10 轮空转，平均轮数恒为 10。
- **碰撞裁决的隐性偏置**：dict 插入顺序让 agent-0 永远赢，若用于研究"角色分化"会制造假的 identity-linked differentiation。
- **硬编码结论**：改参数后打印的 Takeaways 仍是旧数字，容易误读。
- **可变默认值**：若把 `observations` 写成 `= []` 而不是 `field(default_factory=list)`，dataclass 会直接报错（防止所有实例共享同一列表）。
