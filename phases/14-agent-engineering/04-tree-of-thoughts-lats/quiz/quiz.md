# 测验 · Tree of Thoughts 与 LATS：审慎搜索（Tree of Thoughts and LATS: Deliberate Search）

> **阶段 14 · Agent 工程 · 第 04 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义为质量很差的机器翻译（如"24 的伽梅"指 Game of 24），请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | CoT 的问题 | chain-of-thought 是线性路径，第一步错了后面全错、无法回溯；讲义："Game of 24 上 GPT-4 CoT 只有 4%" |
| 2 | 推理即搜索 | 节点是"思考"（中间步骤），边是"扩展"，价值是"有多大希望"；需要能提出多个候选、评估、挑选、遇到死路时回溯 |
| 3 | Tree of Thoughts | Yao 等（NeurIPS 2023）：每个节点扩展 K 个子思考，LLM 用打分 prompt 自评，再用 BFS / DFS / beam 搜索；Game of 24 从 4%（CoT）提升到 74%（ToT，GPT-4） |
| 4 | 三种自评方式 | `sure / likely / impossible` 分类、1–10 数值打分、在候选之间投票；**自评是承重部件** |
| 5 | LATS | Zhou 等（ICML 2024）：用 MCTS 统一 ToT、ReAct、Reflexion；LLM 同时扮演 policy、value function、self-reflector，并把环境反馈混入价值 |
| 6 | LATS 结果（讲义） | GPT-4 下 HumanEval pass@1 92.7%（当时 SOTA）；GPT-3.5 下 WebShop 平均分 75.9，接近基于梯度的微调 |
| 7 | MCTS 四步 | Select（用 UCT 从根走到叶）→ Expand（生成 K 个子节点）→ Simulate（rollout 并用价值函数/环境奖励打分）→ Backpropagate（沿路径更新访问次数和价值） |
| 8 | UCT 公式 | `Q(s,a) + c·sqrt(ln N(s) / N(s,a))`：第一项利用、第二项探索；`c` 按任务调 |
| 9 | 成本现实 | 讲义：ToT 在 Game of 24 上用 CoT 的 100–1000 倍 token；只在单轨迹明显不够、正确性比延迟重要、有便宜可靠的价值函数时使用 |
| 10 | 噪声评估的陷阱 | 单一正确答案 + 有噪声的评估器时，搜索常常更糟——它会找到"高分的错误答案"；2026 年多数生产 agent 用 ReAct + 工具验证（CRITIC），搜索只用于特定场景 |

### 核心技能（能动手做到）

- [ ] 把一个问题形式化为搜索：定义状态、扩展函数、价值函数、终止条件
- [ ] 实现 ToT 风格的逐层 BFS / beam search，并能手算每层的扩展数
- [ ] 实现 MCTS 的 Select / Expand / Simulate / Backpropagate 与 UCT 选择，并解释 `c` 的作用
- [ ] 诊断"价值函数把搜索引向死路"的问题，并设计更好的价值函数（如 sure / likely / impossible 前瞻）
- [ ] 发现并修复"rollout 中找到了解却没有被记录"之类的搜索实现 bug
- [ ] 根据任务形态、预算和评估器可信度，在 ReAct / ToT / LATS / 演化搜索之间做选择

---

## 二、基础自测（选择题）

**Q1.** 按讲义转述，Game of 24 上 GPT-4 的准确率从 CoT 到 ToT 的变化是：

- A. 4% → 74%
- B. 74% → 92.7%
- C. 4% → 92.7%
- D. 33% → 74%

**Q2.** 关于 LATS，下列说法正确的是：

- A. 它是 ToT 的 DFS 版本，不需要价值函数
- B. 它用梯度训练一个价值网络来指导 MCTS
- C. 它用 MCTS 统一了 ToT、ReAct 和 Reflexion，LLM 同时充当 policy、value function 和 self-reflector，并把环境反馈混入价值估计
- D. 它只适用于数学题，不能处理有工具调用的任务

**Q3.** UCT 公式 `Q(s,a) + c·sqrt(ln N(s) / N(s,a))` 中，把 `c` 调大会怎样？

- A. 更偏向价值高的子节点（利用）
- B. 不影响选择，只影响回传的奖励大小
- C. 让访问次数多的子节点更容易被选中
- D. 更偏向访问次数少的子节点（探索），搜索更分散

**Q4.** MCTS 每次迭代四个阶段的正确顺序是：

- A. Expand → Select → Backpropagate → Simulate
- B. Select → Expand → Simulate → Backpropagate
- C. Simulate → Select → Expand → Backpropagate
- D. Select → Simulate → Expand → Backpropagate

**Q5.** 运行本节代码，ToT BFS 输出 `best trace: ['6*4=24', '4-1=3', '24+3=27']`，`final state: (27,)  value: -0.030`。这说明：

- A. ToT 找到了解，`-0.030` 是归一化后的置信度
- B. ToT **没有**找到解：最终结果是 27，与 24 差 3（价值 `-3/100`）；`tot_bfs` 在失败时也会返回最后一层"最好"的节点
- C. `[4, 6, 4, 1]` 无法凑出 24，所以只能返回最接近的值
- D. 只要把 `max_depth` 从 3 改为 4 就能找到解

**Q6.** ToT 失败的根本原因是什么？（提示：`(6+1)*4-4 = 24` 和 `(6-1)*4+4 = 24` 都在代码的搜索空间里）

- A. 搜索深度不够
- B. 扩展函数漏掉了加法
- C. 浮点误差导致 24 没被识别
- D. 中间状态的价值函数取"状态中离 24 最近的数"，`6*4=24` 得到的 `(24, 4, 1)` 拿到满分 0，但剩下的 4 和 1 必须继续参与运算，这是一条死路——价值函数把 beam 全部引向"高分的错误方向"

**Q7.** LATS MCTS 输出 `final state: (24, 4)  value: 0.000`，讲义说它"converging on the best rollout"。正确的解读是：

- A. 这是一个**未完成**的中间节点（还剩一个 4 没用），`best_leaf` 从树的所有叶子里按启发式价值挑选，未完成节点也会入选；真正的成功价值应为 1.0
- B. MCTS 找到了正确答案，因为状态里有 24
- C. `value 0.000` 表示 MCTS 的置信度为 0，需要更多迭代
- D. 4 可以被忽略，Game of 24 允许不使用全部数字

**Q8.** 按讲义的建议，下列哪个任务**最适合**引入树搜索？

- A. 回答"法国的首都是哪里"
- B. 一个只有单一正确答案、但评估器噪声很大的分类任务
- C. 代码生成：有单元测试可作为便宜、可靠的价值函数，且正确性比延迟更重要
- D. 对延迟极其敏感的实时语音对话

---

## 三、动手 / 代码题

**Q9.** 手算 ToT BFS 的扩展数 `expansions: 152`（`max_expansions_per_level=8`，`max_depth=3`，初始状态 `(6, 4, 4, 1)`）。

1. 写出每一层的子节点数并求和。
2. 实测第一层排名前 8 的节点里有两个完全相同的 `(24, 4, 1)`，第二层的 8 个节点**全部**来自 `6*4=24` 这一支，其中 `(24, 4)` 出现了 4 次。这暴露了什么问题？
3. 实测把 beam 宽度设为 4、8、16、24、32 都失败，48 才成功（扩展 460 次）。而完整枚举这棵树共 1129 个叶子。由此你对"加宽 beam 能弥补差的价值函数"有什么结论？

**Q10.** 讲义说 ToT 论文的一种自评是 `sure / likely / impossible` 分类。写一个价值函数 `value_lookahead(node)`：终局等于 24 得 1.0、否则 −1.0；中间状态若"剩下的数还能凑出 24"得 0.5，否则 −1.0（可以用带缓存的递归判断）。用它替换原价值函数后，beam 宽度为 1 时能否找到解、扩展多少次？这个实验有什么"作弊"之处，真实 ToT 中这一步由谁完成？

**Q11.** 阅读 `mcts` 与 `simulate`：

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

```python
        reward = simulate(cur, depth=max(0, 3 - len(cur.trace)), rng=rng)
        backprop(path, reward)
    best_leaf = max(_all_leaves(root), key=value, default=root)
    return best_leaf, expansions
```

实测在 200 次迭代中，有 3 次 rollout 的终局正好是 24（`simulate` 返回 1.0），但最终输出仍是 `(24, 4)`。

1. 找到解的 rollout 去哪了？
2. 写出修复：记录成功的 rollout，并在找到时提前返回；`best_leaf` 只在终局节点中挑选。

**Q12.** 讲义练习 1 要求比较 UCT `c = 0.1` 与 `c = 2.0`。

1. 现有代码中 `mcts` 能直接传入 `c` 吗？要改哪一行？
2. 实测（seed = 7）结果如下，请解读：

| c | 迭代 | 扩展数 | 最佳结果 | 根节点子节点访问次数前三 |
|---|------|-------|---------|----------------------|
| 0.1 | 200 | 314 | `(24, 4)`，未解 | 26, 11, 11 |
| 0.1 | 500 | 330 | `(6-1)*4+4`，解出 | 286, 26, 20 |
| 1.4 | 500 | 1019 | `(6+1)*4-4`，解出 | 29, 24, 23 |
| 2.0 | 500 | 1032 | `(6+1)*4-4`，解出 | 26, 23, 22 |

---

## 四、面试高频题

**Q13.**（基础必考）Tree of Thoughts 和 Chain-of-Thought 有什么区别？一个 ToT 系统由哪几个部分组成？

**Q14.**（原理深挖）讲一讲 MCTS 和 UCT。LATS 在标准 MCTS 上加了什么？为什么说价值函数是整个搜索的"承重部件"？

**Q15.**（工程实践）树搜索的 token 成本是 CoT 的 100–1000 倍。在生产系统里你会如何决定"要不要搜索"，以及如何控制搜索的预算？

**Q16.**（场景设计）为一个代码生成 agent 设计 LATS 式搜索：policy、价值函数、反思、终止条件分别是什么？有哪些"高分错误答案"的风险？

**Q17.**（追问型）BFS、beam search、DFS、MCTS 在 token 预算很紧时各有什么优劣？状态重复（transposition）该怎么处理？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："All three beat CoT substantially on Game of 24 (4% -> 74% with GPT-4)." B、C 把 LATS 在 HumanEval 上的 92.7% pass@1 混了进来——那是不同的基准和方法；D 的 33% 没有出处。

### Q2 — 答案：C

讲义："LATS unifies ToT, ReAct, and Reflexion under MCTS. The LLM plays three roles: Policy… Value function… Self-reflector… Environment feedback (observations) mixes into the value function." A 错：LATS 是 MCTS 而非 DFS，且需要价值函数；B 错：价值来自 prompt 的 LLM 自评和环境奖励，不训练价值网络；D 错：LATS 在 WebShop、HumanEval 等有环境交互的任务上都有结果。

### Q3 — 答案：D

第二项 `c·sqrt(ln N(s) / N(s,a))` 在子节点访问次数 `N(s,a)` 小时更大，`c` 越大，这一项的权重越高，越倾向于去访问"还不太了解"的子节点。A 是 `c` 变小时的效果；C 说反了；B 错，`c` 只参与选择。Q12 的实测：`c = 0.1` 时根节点某个子节点被访问 286 次（高度集中），`c = 2.0` 时前三名访问次数为 26、23、22（分散）。

### Q4 — 答案：B

讲义："Select — walk from root to a leaf using UCT；Expand — generate K children via the policy；Simulate — rollout from a child…；Backpropagate — update visit counts and value estimates up the path." 本节 `mcts` 的循环体也正是这个顺序：`while cur.children` 选择 → `cur.children = expand(cur)` → `simulate` → `backprop`。

### Q5 — 答案：B

`value` 对终局状态的定义：等于 24 得 1.0，否则得 `-|result − 24| / 100`，27 对应 `-0.03`。`tot_bfs` 只有在某个子节点价值 > 0.99（即真的等于 24）时才提前返回；三层走完没找到，就返回最后一层 frontier 中价值最高的节点，而 `main` 打印时没有区分成功与失败。C 错：暴力枚举表明有 10 种写法（如 `(6+1)*4-4`、`(6-1)*4+4`），其中两种在代码的搜索空间里；D 错：4 个数只需 3 次运算，深度 3 已经足够，问题在价值函数。

### Q6 — 答案：D

```python
def value(node: Node) -> float:
    if len(node.state) == 1:
        ...
    best_distance = min(abs(v - TARGET) for v in node.state)
    return -best_distance / 100.0
```

中间状态只看"有没有某个数接近 24"，而不看"剩下的数还能不能凑成 24"。实测第一层排序：两个 `(24, 4, 1)` 价值 0.0 排第 1、2 名，`6+1=7`（通往正解）价值 −0.17 排第 7 名，`6-1=5` 排第 20 名。第二层的 8 个名额全被 `(24, …)` 系列占满（包括 4 个重复的 `(24, 4)`），正解分支被挤出 beam。这正是讲义所说的"搜索会找到一个高分的错误答案"。A 错：深度 3 足够；B 错：加法在 `OPS` 里；C 错：整数运算没有误差问题。

### Q7 — 答案：A

`(24, 4)` 只做了两次运算，还剩两个数，不是终局。`_all_leaves(root)` 收集的是**树中当前没有子节点的节点**，包括还没被扩展的中间节点；`max(..., key=value)` 用启发式价值挑选，`(24, 4)` 的"最近距离"为 0，于是被选中。成功的终局价值应为 1.0。所以讲义"LATS converging on the best rollout"在这次运行里并不成立（另见 Q11：rollout 中其实找到过解）。D 错：Game of 24 要求四个数都用上。

### Q8 — 答案：C

讲义列出的使用条件：单轨迹明显不够（Game of 24、复杂代码）、正确性比延迟重要、有便宜可靠的价值函数（代码的单元测试、数学的明确目标）。A 是简单问答，单轨迹就够；B 正是讲义警告的"单一正确答案 + 噪声评估器，搜索反而更糟"；D 对延迟敏感，承受不起成百上千倍的 token 成本。

### Q9 — 参考答案

1. 每层的子节点数（已用脚本逐层核对）：
   - 第 1 层：4 个数取 2 个，`C(4,2) = 6` 对 × 4 种运算 = **24**（没有除以 0 的情况）；
   - 第 2 层：保留前 8 个节点，每个剩 3 个数，`C(3,2) = 3` 对 × 4 = 12，共 `8 × 12 =` **96**；
   - 第 3 层：保留前 8 个，每个剩 2 个数，1 对 × 4 = 4，共 `8 × 4 =` **32**；
   - 合计 `24 + 96 + 32 = 152`。
   注意：`expand` 中 `a, b = state[i], state[j]` 且状态降序排列，所以只会计算"大 − 小""大 ÷ 小"，不会出现 `1/4`、`4−6` 这类运算，搜索空间比完整的 Game of 24 小。
2. 问题是**缺少去重（transposition）**：输入里有两个 4，`6*4`（第一个 4）和 `6*4`（第二个 4）产生完全相同的状态，各占一个 beam 名额；不同的运算路径也会到达同一状态（`24*1=24` 与 `24/1=24.0`）。beam 宽度 8 实际只覆盖了很少的不同状态。修复：按 `state` 去重，或用字典记录已见过的状态。
3. 结论：价值函数有系统性偏差时，加宽 beam 只是"更晚地被骗"——宽度要到 48 才把正解分支保留下来，此时扩展 460 次，已接近穷举（1129 个叶子）的 40%，搜索的意义所剩无几。改进价值函数（Q10）比堆宽度有效得多。

### Q10 — 参考答案

```python
import functools

@functools.lru_cache(maxsize=None)
def solvable(state):
    if len(state) == 1:
        return abs(state[0] - 24) < 1e-6
    return any(solvable(ch.state) for ch in expand(Node(state=state, trace=[])))

def value_lookahead(node):
    if len(node.state) == 1:
        return 1.0 if abs(node.state[0] - 24) < 1e-6 else -1.0
    return 0.5 if solvable(node.state) else -1.0      # "likely/sure" vs "impossible"
```

实测：用它替换原价值函数后，beam 宽度为 **1** 时就能找到 `['6+1=7', '7*4=28', '28-4=24']`，扩展 **38** 次；宽度 2 时 50 次，宽度 8 时 122 次（都成功）。

"作弊"之处：`solvable` 内部做的是穷举搜索，它的计算量没有被计入 `expansions`——我们等于把"搜索"藏进了价值函数。真实 ToT 中，这一步由 **LLM 自评**完成：给模型看剩下的数，让它判断"sure / likely / impossible"（例如"10 和 14 → sure，因为 10+14=24"；"1、1、1 → impossible，因为太小"）。LLM 的判断便宜但有噪声；这个实验说明的是**价值函数的质量直接决定了需要多宽的搜索**——讲义称自评为"load-bearing piece"正是此意。

### Q11 — 参考答案

1. `simulate` 只返回一个数值 `value(current)`，rollout 走到的终局节点 `current` 被**丢弃**；它不在树上（rollout 节点不会挂到树里），所以 `_all_leaves(root)` 永远看不到它。三次 1.0 的奖励只是被回传、提高了路径上节点的 Q 值，而"答案本身"丢失了。实测 200 次迭代中 rollout 命中 3 次、树中终局解为 0 个，输出 `(24, 4)`；迭代到 500 次时，树自己扩展到了终局解，才输出正确答案。
2. 修复（已运行验证）：

```python
def simulate_track(node, depth, rng):
    cur = node
    for _ in range(depth):
        opts = expand(cur)
        if not opts:
            break
        cur = rng.choice(opts)
    return value(cur), cur                       # 同时返回 rollout 终点

def mcts_fixed(root, iterations, rng, c=1.4):
    expansions = 0
    for it in range(iterations):
        path, cur = [root], root
        while cur.children:
            cur = max(cur.children, key=lambda ch: uct(cur, ch, c))
            path.append(cur)
        if cur.visits > 0 and len(cur.state) > 1:
            cur.children = expand(cur)
            expansions += len(cur.children)
            if cur.children:
                cur = rng.choice(cur.children)   # 原代码固定取 children[0]
                path.append(cur)
        reward, leaf = simulate_track(cur, max(0, 3 - len(cur.trace)), rng)
        if reward > 0.99:                        # 有可验证的终局：找到即返回
            return (it + 1, leaf), expansions
        backprop(path, reward)
    return None, expansions
```

实测：seed 7 在第 428 次迭代找到 `(6-1)*4+4`；seed 1、2、3 分别在第 108、85、9 次迭代找到解。另外，若不提前返回，最终挑选时也应只在 `len(state) == 1` 的终局节点（以及记录下的成功 rollout）中选，而不是在所有叶子里按启发式挑。

要点：在有**可验证**终局（单元测试通过、等于 24）的任务里，"找到即停"能节省大量预算；LATS 论文中的代码任务也是一旦通过测试就停止。

### Q12 — 参考答案

1. 不能。`mcts` 内部写的是 `uct(cur, ch)`，用的是 `uct` 的默认参数 `c=1.4`；`main` 也没有入口。要给 `mcts` 加参数 `c`，并把这一行改成 `max(cur.children, key=lambda ch: uct(cur, ch, c))`。（上面的实验是通过修改 `uct.__defaults__` 完成的。）
2. 解读：
   - `c = 0.1` 几乎纯利用：根节点访问高度集中（500 次中 286 次给了同一个子节点），扩展数很少（330），这次碰巧集中在通往正解的分支上，所以用很少的扩展就解出；但 200 次时还停在 `(24, 4)` 的陷阱里——利用型搜索**成败取决于早期价值估计是否正确**，换个种子或价值函数稍有偏差就可能一直钻在死路里。
   - `c = 1.4 / 2.0` 更分散，扩展数约 1000+，但对价值函数的偏差更鲁棒。
   - 结论：`c` 要按任务调（讲义："Tune c per task"）。价值信号可靠时小 `c` 省钱；价值信号有偏或有噪声时需要更大的 `c`。另外本代码的奖励尺度不一致（成功 1.0、失败只在 −0.01～−1 之间），也会影响 `c` 的合适取值。

### Q13 — 参考回答要点

- **CoT**：一条线性推理路径，一步错步步错，不能回溯。
- **ToT**：把推理组织成树，每个节点是一个连贯的中间步骤，可以并行提出多个候选、评估、剪枝、回溯。
- **四个组成部分**：
  1. 思考分解：一个"思考"多大（Game of 24 中是一次运算）；
  2. 思考生成器：每个节点生成 K 个候选（采样或一次提出多个）；
  3. 状态评估器：LLM 自评——sure / likely / impossible、1–10 分、或投票；
  4. 搜索算法：BFS / beam（保留每层前 b 个）、DFS（配合剪枝和回溯）。
- **效果与代价**：Game of 24 上 4% → 74%（GPT-4），但 token 是 CoT 的 100–1000 倍。
- 加分点：说明 ToT 的提升主要来自评估器能否识别死路；评估器有偏时，搜索会稳定地找到错误答案（本节代码就是例子）。

### Q14 — 参考回答要点

- **MCTS 四步**：Select（UCT 从根走到叶）→ Expand（policy 生成子节点）→ Simulate（rollout 并打分）→ Backpropagate（更新路径上节点的访问次数和价值总和）。
- **UCT**：`Q + c·sqrt(ln N / n)`，平衡利用和探索；未访问的子节点视为无穷大，保证每个子节点至少被访问一次（本节代码 `uct` 返回 `inf`）。
- **LATS 的增强**：
  - policy = ReAct 式的 LLM 动作提议；
  - value = LLM 自评 + 环境反馈（真实的工具结果、测试结果），而不只是模型的意见；
  - reflection = 失败轨迹生成 Reflexion 式反思，用于下一轮 rollout 的 prompt。
- **价值函数为何承重**：选择、剪枝、回传都依赖它；价值有偏时，UCT 的利用项会把预算持续送进错误分支（本节代码中 `(24, 4, 1)` 的陷阱）；价值好时，极窄的搜索也能成功（Q10 中 beam = 1 即可）。
- 加分点：在可验证的任务中，环境奖励（测试通过）比模型自评可靠得多，这也是 LATS 在代码任务上效果最好的原因。

### Q15 — 参考回答要点

- **何时搜索**（讲义条件）：单轨迹明显不够；正确性比延迟重要；有便宜、可靠的价值函数。反之（简单问答、噪声评估器、实时交互）就不要搜索。
- **门控**：讲义："if task_complexity > threshold: use_search()"。先用 ReAct + 工具验证（第 05 节 CRITIC）跑一次，验证失败再升级到搜索——大多数请求走便宜路径。
- **预算控制**：
  - 硬上限：最大节点数 / rollout 数 / token / 墙钟时间；
  - 可验证终局时找到即停（Q11）；
  - 去重相同状态；beam 宽度和 `c` 按任务调；
  - 价值评估批量化、缓存；用小模型做 policy 或 value 的初步筛选。
- **度量**：记录每个任务的"成功率 vs token"曲线，确认搜索带来的增益值得它的成本。
- 常见误区：在没有可靠价值函数的任务上加大搜索，只会更自信地输出错误答案。

### Q16 — 参考回答要点

- **policy**：LLM 根据题目、当前代码和反思生成 K 个候选补丁或实现。
- **价值函数**：首选环境奖励——编译是否通过、可见单测通过率；辅以 LLM 自评（代码可读性、是否覆盖边界）；失败测试的错误信息作为 observation 回填。
- **反思**：rollout 失败时生成 Reflexion 式反思（"没有处理空列表"），放进后续 rollout 的 prompt。
- **终止**：所有可见测试通过即停止并返回；或达到 rollout / token 预算，返回通过率最高的候选并如实标注。
- **"高分错误答案"风险**：
  - 过拟合可见测试（硬编码测试期望值、针对样例写特判）——用隐藏测试或基于性质的测试验证；
  - 模型自评偏高；
  - 测试本身不完整，覆盖不到的 bug 拿到满分。
- 加分点：讲义提到的 AlphaEvolve（第 15 阶段第 03 节）是这一思路的极端版本——机器可检查的适应度 + 演化搜索。

### Q17 — 参考回答要点

- **BFS（全展开）**：最稳但最贵，层数一多就爆炸。
- **Beam search**：每层只保留前 b 个，预算可控；依赖价值函数，价值有偏时会整体偏到错误分支（本节 ToT 即为例）；适合预算紧、价值函数尚可的任务——这也是讲义练习 3 的问题。
- **DFS + 剪枝**：内存小，能很快走到终局拿到可验证信号；遇到死路靠评估器判断 impossible 再回溯，适合有强剪枝信号的任务。
- **MCTS**：用访问统计在探索和利用之间自适应分配预算，对价值噪声更鲁棒，但每次迭代都要 rollout，开销大，且需要调 `c`。
- **状态重复**：同一状态经不同路径到达（本节 `(24, 4)` 出现 4 次）。用"状态 → 节点"的字典去重（transposition table），合并访问统计；对 LLM 生成的文本状态，可以做规范化（排序、去空格）或语义去重。
- 加分点：预算很紧时，"先用便宜的启发式过滤，再对少量候选做昂贵评估"通常比单纯换搜索算法更有效。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：LATS 的 policy 就是 ReAct 式的动作提议。
- [阶段 14 · 03 Reflexion：语言反馈驱动的 Reinforcement Learning](../../03-reflexion-verbal-rl/docs/zh.md)：LATS 中 self-reflector 的来源。
- [阶段 11 · 02 Few-Shot, Chain-of-Thought, Tree-of-Thought](../../../11-llm-engineering/02-few-shot-cot/docs/zh.md)：CoT 与 ToT 的提示层面介绍。
- [阶段 09 · 03 Monte Carlo 方法——从完整回合中学习](../../../09-reinforcement-learning/03-monte-carlo-methods/docs/zh.md)：蒙特卡洛估计与 rollout 的基础。
- [阶段 09 · 12 游戏强化学习——AlphaZero、MuZero 和 LLM 推理时代](../../../09-reinforcement-learning/12-rl-for-games/docs/zh.md)：MCTS + UCT 在 AlphaZero 中的经典用法。

### 本节被哪些后续内容用到
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../05-self-refine-and-critic/docs/zh.md)：讲义说多数生产 agent 用 ReAct + 工具验证而非搜索；evaluator-optimizer 模式用于决定何时升级到搜索。
- [阶段 14 · 11 结合 HTN 与演化搜索的 Planning](../../11-planning-htn-and-evolutionary/docs/zh.md)：分层规划与演化搜索。
- [阶段 14 · 25 多 Agent 辩论与协作](../../25-multi-agent-debate/docs/zh.md)：另一种"多候选 + 评估"的思路。
- [阶段 15 · 03 AlphaEvolve：演化式 Coding Agents](../../../15-autonomous-systems/03-alphaevolve-evolutionary-coding/docs/zh.md)：讲义提到的"以机器可检查适应度做演化搜索"的极端例子。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../../15-autonomous-systems/13-cost-governors/docs/zh.md)：为昂贵的搜索设置预算。

### 延伸关键词
`Tree of Thoughts` · `LATS` · `MCTS` · `UCT` · `exploration vs exploitation` · `value function` · `self-evaluation (sure/likely/impossible)` · `beam search` · `rollout` · `backpropagation (MCTS)` · `transposition table` · `Game of 24` · `pass@1`
