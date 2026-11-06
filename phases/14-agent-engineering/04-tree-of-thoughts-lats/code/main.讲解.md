# 代码讲解 · main.py

> **所属小节**：阶段 14 · Agent 工程 · 第 04 节 Tree of Thoughts 与 LATS：审慎搜索 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数；MCTS 使用固定种子 `random.Random(7)`） ｜ **依赖**：仅标准库（`itertools`、`math`、`random`、`dataclasses`）；无需 LLM、无需网络

---

## 1. 这份代码在考察什么

这份 186 行的代码在 Game of 24（用 `[4, 6, 4, 1]` 和 `+ − × ÷` 凑出 24）上实现了两种搜索：

1. **ToT 风格的逐层 BFS（实为 beam search）**：每层把所有节点展开，按价值排序后只保留前 8 个。
2. **LATS 风格的 MCTS**：Select（UCT）→ Expand → Simulate（随机 rollout）→ Backpropagate。
3. **价值函数**：用"离 24 的距离"这个符号化分数代替 LLM 自评。

它要让你掌握"把推理形式化为搜索"所需的全部部件：状态、扩展、价值、搜索策略。同时，**这次运行两种搜索都没有找到解**——而解确实存在（`(6+1)*4-4`、`(6-1)*4+4` 都在代码的搜索空间里）。读懂它为什么失败，比读懂它怎么写更有价值：这正是讲义警告的"搜索找到了一个高分的错误答案"。

> 一句话：**搜索的上限由价值函数决定**。本代码的价值函数把搜索引向了 `6*4=24` 这个"看上去最好"的死路。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `NUMBERS` / `TARGET` / `OPS` | 模块常量 | 题目：`[4,6,4,1]` → 24，四种运算 | 任务定义 |
| `Node` | dataclass | 状态（剩余数字的元组）、路径（已做的运算）、访问次数、价值总和、子节点；`q` 属性为平均价值 | 搜索树节点 |
| `evaluate` | 函数 | 计算 `a op b`，除以 0 返回 `None` | 环境/规则 |
| `expand` | 函数 | 任选两个数做一次运算，生成所有子状态 | policy（穷举版） |
| `value` | 函数 | 终局：等于 24 得 1.0，否则 −距离/100；中间：−(最接近 24 的数的距离)/100 | value function |
| `tot_bfs` | 函数 | 逐层展开，保留前 `max_expansions_per_level` 个；遇到价值 > 0.99 立即返回 | ToT（beam BFS） |
| `uct` | 函数 | `Q + c·sqrt(ln N_parent / N_child)`，未访问返回 `inf` | UCT |
| `select` | 函数 | 沿 UCT 最大的子节点走到叶子（**未被使用**） | Select |
| `simulate` | 函数 | 从节点随机走若干步，返回终点价值 | Simulate / rollout |
| `backprop` | 函数 | 路径上每个节点 `visits += 1`、`value_sum += reward` | Backpropagate |
| `mcts` | 函数 | 迭代执行四步，最后在所有叶子里挑价值最高的 | LATS（无 LLM 版） |
| `_all_leaves` | 函数 | 递归收集没有子节点的节点 | 结果提取 |
| `main` | 函数 | 分别运行 ToT 与 MCTS，打印结果与论文数字 | 入口 |

数据流：`main` → 构造根节点 `(6, 4, 4, 1)` → `tot_bfs`（`expand` + `value` 逐层筛选）→ 打印；再构造新根节点并预先展开 → `mcts`（`uct` 选择 → `expand` → `simulate` → `backprop`，循环 80 次）→ `_all_leaves` 挑结果 → 打印。

---

## 3. 逐段精讲

### 3.1 `Node`：搜索树节点

```python
@dataclass
class Node:
    state: tuple[float, ...]
    trace: list[str]
    visits: int = 0
    value_sum: float = 0.0
    children: list["Node"] = field(default_factory=list)

    @property
    def q(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0
```

- `state` 是"剩下的数字"，用**元组**（不可变）并始终降序排列，这样 `(4, 6)` 和 `(6, 4)` 是同一状态。
- `trace` 记录已做的运算，如 `['6*4=24', '24*1=24']`，相当于 ToT 中的"思考链"。
- `visits` / `value_sum` / `q` 是 MCTS 的统计量；ToT 不使用它们。
- `@property` 让 `node.q` 像属性一样访问，内部按需计算平均价值；未访问时返回 0 避免除零。
- `list["Node"]`：类型注解里引用正在定义的类，用字符串（前向引用）；文件开头有 `from __future__ import annotations` 时其实不加引号也可以。

### 3.2 `evaluate` 与 `expand`：搜索空间

```python
def expand(node: Node) -> list[Node]:
    children: list[Node] = []
    state = node.state
    if len(state) < 2:
        return children
    for i, j in itertools.combinations(range(len(state)), 2):
        for op in OPS:
            a, b = state[i], state[j]
            v = evaluate(a, op, b)
            if v is None:
                continue
            remaining = [s for k, s in enumerate(state) if k not in (i, j)]
            new_state = tuple(sorted(remaining + [v], reverse=True))
            step = f"{a}{op}{b}={v}"
            children.append(Node(state=new_state, trace=node.trace + [step]))
    return children
```

- `itertools.combinations(range(n), 2)` 生成所有下标对 `(i, j)`，`i < j`。4 个数有 6 对，每对 4 种运算，所以根节点有 24 个子节点。
- `remaining + [v]` 后重新降序排序，得到新状态；`node.trace + [step]` 生成**新列表**，不会修改父节点的 trace。
- 这里的 `expand` 是**穷举式 policy**：真实 ToT/LATS 中由 LLM 提出 K 个（通常 3–5 个）有希望的候选，而不是列出全部。
- ⚠️ 因为状态降序、`i < j`，`a` 总是大于等于 `b`：只算"大 − 小""大 ÷ 小"，不会出现 `1/4`、`4−6`。搜索空间比完整的 Game of 24 小（完整枚举有 10 种表达式写法，代码空间里只剩 `(6+1)*4-4` 与 `(6-1)*4+4` 两类）。
- ⚠️ 没有去重：输入有两个 4，`6*4` 会产生两个完全相同的 `(24, 4, 1)` 子节点；`24*1` 与 `24/1` 也会到达同一状态。
- ⚠️ 除法结果是浮点数，trace 中会出现 `24/1=24.0`、`6/1=6.0` 这样整数与浮点混杂的写法。

### 3.3 `value`：价值函数（本代码的症结）

```python
def value(node: Node) -> float:
    if len(node.state) == 1:
        result = node.state[0]
        return 1.0 if abs(result - TARGET) < 1e-6 else -abs(result - TARGET) / 100.0
    best_distance = min(abs(v - TARGET) for v in node.state)
    return -best_distance / 100.0
```

- 终局（只剩一个数）：恰好 24 得 1.0，否则按距离给一个很小的负分。用 `abs(...) < 1e-6` 比较浮点数，避免 `8/3*9` 之类的舍入误差。
- 中间状态：取"状态中**最接近 24 的那个数**"的距离。
- ⚠️ 这个启发式与任务目标不一致：Game of 24 要求**所有**数字都参与运算，状态中出现 24 并不意味着离解更近。`(24, 4, 1)` 拿到中间状态的最高分 0.0，可剩下的 4 和 1 无论怎么接都回不到 24（4、1 能组合出的 5、3、4 与 24 运算都得不到 24）。实测第一层排序中两个 `(24, 4, 1)` 排第 1、2 名，而通往正解的 `6+1=7` 排第 7 名、`6-1=5` 排第 20 名。
- ⚠️ 讲义"动手实现"说价值函数"composes a symbolic score plus a self-eval score"，代码中只有符号分数，没有任何自评部分。
- 对比讲义的 ToT 自评：`sure / likely / impossible` 判断的是"剩下的数还能不能凑出 24"——正好是这里缺失的信息（测验 Q10 实现了一个前瞻版价值函数，beam 宽度 1 即可解出）。

### 3.4 `tot_bfs`：逐层 beam 搜索

```python
def tot_bfs(root: Node, max_expansions_per_level: int = 8,
            max_depth: int = 3) -> tuple[Node | None, int]:
    frontier = [root]
    expansions = 0
    for _ in range(max_depth):
        scored: list[tuple[float, Node]] = []
        for node in frontier:
            for child in expand(node):
                expansions += 1
                scored.append((value(child), child))
                if value(child) > 0.99:
                    return child, expansions
        scored.sort(key=lambda p: p[0], reverse=True)
        frontier = [n for _, n in scored[:max_expansions_per_level]]
    best = max(frontier, key=value) if frontier else None
    return best, expansions
```

- 每一层：展开 frontier 中所有节点 → 打分 → 排序 → 只留前 8 个。名为 BFS，实际是**宽度为 8 的 beam search**（真正的 BFS 会保留整层）。
- `max_depth=3`：4 个数需要 3 次运算，深度刚好够。
- 一旦某个子节点价值 > 0.99（只有终局等于 24 才可能）就提前返回。
- 扩展数：24 + 8×12 + 8×4 = **152**（与输出一致，逐层核对见测验 Q9）。
- ⚠️ `value(child)` 每个子节点算了两次（一次存入 `scored`，一次判断阈值）。
- ⚠️ 搜索失败时也返回"最后一层最好的节点"，调用者无法区分成功与失败，`main` 也没有判断。
- `scored.sort(key=lambda p: p[0], reverse=True)` 只按分数排序；Python 的排序是稳定的，分数相同的节点保持生成顺序。

### 3.5 MCTS 部件：`uct`、`select`、`simulate`、`backprop`

```python
def uct(parent: Node, child: Node, c: float = 1.4) -> float:
    if child.visits == 0:
        return float("inf")
    return child.q + c * math.sqrt(math.log(parent.visits) / child.visits)
```

- 与讲义公式 `Q(s,a) + c·sqrt(ln N(s) / N(s,a))` 一致。未访问的子节点返回 `inf`，保证每个子节点至少被试一次。
- `c=1.4` 约等于 √2，是 UCB1 的经典取值。

```python
def simulate(node: Node, depth: int, rng: random.Random) -> float:
    current = node
    for _ in range(depth):
        options = expand(current)
        if not options:
            break
        current = rng.choice(options)
    return value(current)
```

- 随机 rollout：每步从所有子节点中均匀随机选一个，走到终局后用 `value` 打分。真实 LATS 中 rollout 由 LLM policy 生成，终点可用环境奖励（如测试结果）打分。
- 用传入的 `rng`（`random.Random(7)`）而非全局 `random`，结果可复现。
- ⚠️ 只返回分数，**rollout 走到的终局节点被丢弃**。实测 200 次迭代中有 3 次 rollout 恰好走到 24，但这些解没有任何地方记录。

```python
def backprop(path: list[Node], reward: float) -> None:
    for n in path:
        n.visits += 1
        n.value_sum += reward
```

- 路径上所有节点都累加同一个奖励（单人博弈，不需要正负交替）。

`select` 函数实现了"沿 UCT 走到叶子"，但 `mcts` 没有调用它，而是把同样的逻辑内联了一遍（因为还需要记录 `path`）。它是死代码。

### 3.6 `mcts`：主循环

```python
def mcts(root: Node, iterations: int, rng: random.Random) -> tuple[Node, int]:
    expansions = 0
    for _ in range(iterations):
        path = [root]
        cur = root
        while cur.children:
            cur = max(cur.children, key=lambda ch: uct(cur, ch))
            path.append(cur)
        if cur.visits > 0 and len(cur.state) > 1:
            cur.children = expand(cur)
            expansions += len(cur.children)
            if cur.children:
                cur = cur.children[0]
                path.append(cur)
        reward = simulate(cur, depth=max(0, 3 - len(cur.trace)), rng=rng)
        backprop(path, reward)
    best_leaf = max(_all_leaves(root), key=value, default=root)
    return best_leaf, expansions
```

- **Select**：`while cur.children` 沿 UCT 最大的子节点下降。注意 lambda 中引用的 `cur` 是循环变量，`max` 在本行内立即求值，所以拿到的是当前父节点，没有闭包延迟绑定的问题。
- **Expand**：叶子第一次被访问时只做 rollout，**第二次**访问（`visits > 0`）才展开——这是常见的"延迟展开"，避免为只访问一次的节点浪费扩展。
- ⚠️ 展开后固定取 `cur.children[0]` 进入 rollout，而不是随机或按先验选择；加上子节点生成顺序固定，早期总是偏向第一个运算对。
- **Simulate**：剩余深度 = `3 − 已做运算数`。
- **Backpropagate**：沿 `path` 更新。
- ⚠️ `uct` 的 `c` 无法从 `mcts` 传入（讲义练习 1 需要先改这一行）。
- ⚠️ `best_leaf` 在树的**所有叶子**中按启发式价值挑选，包括还没展开的中间节点。本次输出 `(24, 4)` 只做了两次运算，就是这样被选中的。
- ⚠️ 奖励尺度：成功 1.0、失败在 −0.01～−1 之间，大部分失败的奖励都非常接近 0，与 `c·sqrt(...)` 的探索项（量级约 1）相比，Q 值差异很小，搜索更接近"按访问次数均匀探索"。
- 讲义所说的 LATS 还包括 LLM 自评与 Reflexion 反思，这里都没有；这是一份**纯 MCTS** 的玩具实现。

### 3.7 `main`

```python
    rng = random.Random(7)
    root_lats = Node(state=tuple(sorted(NUMBERS, reverse=True)), trace=[])
    root_lats.children = expand(root_lats)
    for ch in root_lats.children:
        ch.visits = 0
```

- 根节点预先展开 24 个子节点。随后把每个子节点 `visits` 置 0 的循环是多余的——新建节点的 `visits` 默认就是 0。
- 注意根节点自己的 `visits` 也从 0 开始，第一次迭代时所有子节点 UCT 都是 `inf`，`max` 取第一个。
- 最后打印的论文数字（4% → 74%、92.7%、100–1000 倍）是写死的参考信息。讲义说"Token counts printed for both"，实际打印的是扩展次数，不是 token。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用 Game of 24 做任务 | 与 ToT 论文同一基准，终局可精确验证 | 搜索空间小，穷举也只有 1129 个叶子，看不出搜索相对穷举的优势 |
| 穷举式 `expand` | 无需 LLM | 真实 policy 只提出 3–5 个候选（skill 建议 K=3–5），质量依赖模型 |
| 符号价值"最近数字的距离" | 简单、确定 | 与"必须用完所有数"的目标不一致，把搜索引向死路；ToT 用 sure/likely/impossible 前瞻 |
| beam 宽度 8 | 控制成本 | 价值有偏时正解分支被挤出；实测宽度 48 才成功 |
| 状态降序 + 只算大对小 | 减少重复 | 漏掉 `b − a`、`b ÷ a`；且仍未去重相同状态 |
| 延迟展开 + 随机 rollout | 标准 MCTS 写法 | rollout 找到的解被丢弃；展开后固定取第一个子节点 |
| 在所有叶子里挑结果 | 实现简单 | 未完成的中间节点会被当成"最佳答案"；应只在终局或已记录的成功 rollout 中挑 |
| 固定 `random.Random(7)` | 可复现 | 单个种子的结论不可靠，比较参数时应跑多个种子 |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + `field(default_factory=list)` | `class Node` | 每个节点有独立的 `children` 列表 |
| `@property` | `def q(self)` | 方法当属性用：`node.q` |
| 前向引用注解 | `children: list["Node"]` | 在类定义内部引用自身类型 |
| 变长元组注解 | `tuple[float, ...]` | 任意长度、元素为 float 的元组 |
| `X \| None` 返回值 | `-> float \| None` | 可能返回 `None`（如除以 0） |
| `itertools.combinations` | `itertools.combinations(range(len(state)), 2)` | 生成所有不重复的下标对 |
| `enumerate` + `not in` 元组 | `[s for k, s in enumerate(state) if k not in (i, j)]` | 去掉第 i、j 个元素 |
| `sorted(..., reverse=True)` + `tuple(...)` | `tuple(sorted(remaining + [v], reverse=True))` | 降序排序后转成不可变元组 |
| 列表拼接生成新列表 | `node.trace + [step]` | 不修改原列表 |
| `continue` | `if v is None: continue` | 跳过本次循环 |
| 生成器表达式 + `min` | `min(abs(v - TARGET) for v in node.state)` | 不建中间列表直接求最小值 |
| `list.sort(key=..., reverse=True)` | `scored.sort(key=lambda p: p[0], reverse=True)` | 原地按分数降序排序（稳定排序） |
| 切片 | `scored[:max_expansions_per_level]` | 取前 k 个 |
| `max(..., key=..., default=...)` | `max(_all_leaves(root), key=value, default=root)` | 按 key 取最大；序列为空时返回 default |
| `float("inf")` | `uct` 中 | 正无穷，保证未访问子节点优先 |
| `math.sqrt` / `math.log` | `math.sqrt(math.log(parent.visits) / child.visits)` | 平方根与自然对数 |
| 独立随机数生成器 | `rng = random.Random(7)`、`rng.choice(options)` | 不影响全局随机状态，可复现 |
| 递归 | `_all_leaves` 调用自身 | 遍历整棵树 |
| `list.extend` | `out.extend(_all_leaves(ch))` | 把另一个列表的元素逐个追加 |
| 下划线前缀 | `_all_leaves` | 约定为模块内部使用的函数 |
| f-string 格式符 | `{value(best_tot):.3f}` | 保留三位小数 |

---

## 6. 运行结果解读

实际运行（Python 3.13.16，`cd code && python3 main.py`，耗时不到 0.1 秒）：

```text
======================================================================
TREE OF THOUGHTS + LATS — Phase 14, Lesson 04
======================================================================
numbers: [4, 6, 4, 1]  target: 24

ToT BFS
------------------------------------------------------------
  best trace: ['6*4=24', '4-1=3', '24+3=27']
  final state: (27,)  value: -0.030
  expansions: 152

LATS MCTS
------------------------------------------------------------
  best trace: ['6*4=24', '24*1=24']
  final state: (24, 4)  value: 0.000
  node expansions: 286

Paper headlines (for reference):
  ToT Game-of-24:  GPT-4 CoT 4%  -> ToT 74%
  LATS HumanEval:  pass@1 92.7% with GPT-4 (SOTA at paper time)
  Cost: ToT uses 100-1000x the tokens of CoT. Use with intent.
```

逐项解读：

- **ToT：失败**。最终 27，离 24 差 3，价值 −0.03。第一层两个 `(24, 4, 1)` 拿到最高分 0.0；第二层的 8 个名额**全部**来自 `6*4=24` 这一支（其中 `(24, 4)` 重复 4 次）；第三层只能得到 27、21、28、20 这类结果。正解所在的 `6+1=7` 分支在第二层被淘汰。
- **MCTS：也失败**。`(24, 4)` 是只做了两步的中间节点，`value 0.000` 只是"有个数等于 24"的启发式分，真正的成功应为 1.0。讲义说"LATS converging on the best rollout"，本次运行并不成立。
- **扩展数 152 vs 286**：两者都远小于穷举的叶子数 1129，但都没找到解——"省下的预算"建立在错误的价值函数上。
- **解是存在的**：暴力枚举得到 10 种写法，代码空间中有 `['6+1=7', '7*4=28', '28-4=24']` 和 `['6-1=5', '5*4=20', '20+4=24']`。

额外实验（临时脚本调用本文件中的函数）：

| 实验 | 结果 |
|------|------|
| ToT beam 宽度 4 / 8 / 16 / 24 / 32 | 全部失败（27），扩展 88 / 152 / 278 / 406 / 438 次 |
| ToT beam 宽度 48 | 成功：`(6+1)*4-4`，扩展 460 次 |
| ToT + 前瞻价值函数（sure/impossible） | beam 宽度 1 即成功，扩展 38 次 |
| MCTS 200 次迭代 | rollout 命中 24 共 3 次，但树中终局解 0 个，输出仍是 `(24, 4)` |
| MCTS 500 次迭代 | 成功：`(6+1)*4-4`，扩展 1019 次 |
| MCTS 500 次，`c = 0.1` | 成功：`(6-1)*4+4`，扩展仅 330 次，根节点某子节点被访问 286 次 |
| 修复版 MCTS（记录成功 rollout、找到即停） | seed 7 / 1 / 2 / 3 分别在第 428 / 108 / 85 / 9 次迭代找到解 |

---

## 7. 动手改一改

1. **（热身）如实报告失败**：让 `tot_bfs` 和 `mcts` 返回 `(node, expansions, solved: bool)`，`main` 中失败时打印 "no solution found"。
2. **状态去重**：在 `tot_bfs` 中用 `set` 记录本层已见过的 `state`，重复的子节点不进入 `scored`；比较去重前后 beam 宽度 8 时 frontier 中不同状态的数量。
3. **（测验 Q10）前瞻价值函数**：实现 `sure / likely / impossible` 风格的价值函数（剩余数字能否凑出 24），观察 beam 宽度 1、2、8 的表现；再给它加随机噪声（讲义练习 2），找出它能容忍的最大噪声。
4. **（测验 Q11）修复 MCTS**：`simulate` 同时返回 rollout 终点；找到终局解立即返回；`best_leaf` 只在终局节点中选择；展开后随机选择子节点而不是 `children[0]`。用 10 个随机种子统计平均需要多少次迭代。
5. **（讲义练习 1）调 UCT 的 c**：给 `mcts` 增加 `c` 参数，对 `c ∈ {0.1, 0.5, 1.4, 2.0}`、多个种子统计成功率和扩展数；打印根节点子节点的访问次数分布，观察探索是否集中。
6. **（进阶，讲义练习 3）完整 Game of 24 + beam 对比**：让 `expand` 同时计算 `a op b` 和 `b op a`；从 4nums.com 风格的题库中挑 20 题，比较 BFS（全展开）、beam（k=3、5）、MCTS 在相同扩展预算下的解题率。

---

## 8. 常见坑

- **把启发式分数当成功**：`value 0.000` 不是成功，成功是 1.0；打印结果前一定要检查终局条件。
- **价值函数与目标不一致**："有个数等于 24"不等于"离解更近"，这种偏差会让任何宽度不够的搜索稳定地失败。
- **以为加宽 beam 能弥补价值函数**：本例要宽到 48、接近穷举的 40% 才成功，搜索就失去了意义。
- **丢弃 rollout 结果**：在有可验证终局的任务中，rollout 一旦命中就应记录并（通常）停止。
- **在所有叶子里挑"最佳"**：未展开的中间节点也是"叶子"；结果应只从终局节点中挑。
- **不去重**：重复数字、交换律、等价运算会产生大量相同状态，浪费 beam 名额和预算。
- **单种子下结论**：MCTS 依赖随机数，比较参数时要跑多个种子。
- **把 MCTS 说成 LATS**：本代码没有 LLM 自评、环境反馈和反思，只是 LATS 骨架中的 MCTS 部分。
