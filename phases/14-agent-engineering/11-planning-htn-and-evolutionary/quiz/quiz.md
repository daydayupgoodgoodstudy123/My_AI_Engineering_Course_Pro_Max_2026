# 测验 · 结合 HTN 与演化搜索的 Planning（Planning with HTN and Evolutionary Search）

> **阶段 14 · Agent 工程 · 第 11 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义机翻质量很差（如把 HTN 译成"危险物品处理网"、把 AlphaEvolve 译成"阿尔法· 沃尔沃"），遇到读不通的句子请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 两类 ReAct/ReWOO 覆盖不好的问题 | ① 计划必须**可证明正确**（排程、合规流程）；② 有**可机器检查的 fitness** 的优化问题（矩阵乘法、调度启发式、编译 pass） |
| 2 | HTN 的四要素 | Task（复合 / 原子）、Method（把复合任务分解为子任务，带前置条件）、Operator（原子动作，带前置条件与效果）、State（事实集合） |
| 3 | HTN 规划的定义 | 给定目标任务与初始状态，找到一串原子 operator，使它们按顺序执行时每一步的前置条件都被满足 |
| 4 | ChatHTN 的混合循环 | 先用已有 method 分解；没有可用 method 时才问 LLM；把回答翻译成候选子任务，**用 operator schema 校验**，不合法就拒绝；然后递归 |
| 5 | ChatHTN 的正确性来源 | LLM 只能"提议分解"，不能直接改计划；正确性由符号层负责，LLM 只是扩充 method 库 |
| 6 | Online method learning | 把 LLM 产生的分解缓存并泛化，讲义："cutting LLM query frequency up to 75%" |
| 7 | AlphaEvolve 循环 | 种子程序 + 程序化 evaluator → LLM ensemble 提出变异 → evaluator 打分 → 保留最好的、继续变异 |
| 8 | AlphaEvolve 的硬约束 | fitness 必须**确定、快速、可机器检查**；"问 LLM 代码是不是更好"不是 fitness，对散文答案做演化不会收敛 |
| 9 | 选型 | 硬约束排程 / 政策自动化 → HTN；有测试或基准的代码优化 → AlphaEvolve；一般多步任务 → ReAct / ReWOO；大多数 agent 任务两者都不需要 |
| 10 | 本节代码的简化 | LLM 是脚本化的 `ScriptedLLM`；演化部分只调两个整数系数 `a、b`，变异是随机 ±2，没有 LLM，也没有真正的"程序" |

### 核心技能（能动手做到）

- [ ] 用 `Operator` / `Method` 两个 dataclass 描述一个小领域，并手动推演 `HTNPlanner.plan` 的递归过程与状态变化
- [ ] 说清楚 ChatHTN 的"LLM 只提议、符号层校验"在代码里对应哪两处检查（名字校验 + `_expand` 中的前置条件校验）
- [ ] 找出本节代码"先缓存、后验证"导致失败分解被永久缓存的 bug，并给出修复
- [ ] 为 HTN 规划器加上回溯：依次尝试所有可用 method，全部失败再走 LLM fallback
- [ ] 手算演化 demo 的 fitness（闭式 `110(3−a)² + 11(7−b)²`），解释为什么 `a` 比 `b` 先收敛
- [ ] 给定一个领域，判断该用 HTN、AlphaEvolve 还是 ReAct，并为演化搜索设计一个确定性的 evaluator

---

## 二、基础自测（选择题）

**Q1.** 在 HTN 中，"带有前置条件和效果、可以直接执行的原子动作"叫做：

- A. Operator
- B. Method
- C. Compound task
- D. State

**Q2.** 讲义列出了 AlphaEvolve 的若干公开成果。下列哪一项**不是**讲义提到的？

- A. 4×4 复数矩阵乘法用 48 次标量乘法，56 年来首次改进 Strassen
- B. 通过 Borg 调度启发式回收了 Google 0.7% 的算力
- C. 在一个前沿工作负载上让 FlashAttention 提速 32%
- D. 在 HumanEval 上超过 GPT-4

**Q3.** ChatHTN 声称"产出的每个计划都可证明 sound"，其根据是：

- A. 它对 LLM 做了 HTN 轨迹的微调，LLM 不会再出错
- B. 它让多个 LLM 投票，多数同意才执行
- C. LLM 的建议只作为**候选分解**进入，必须通过 operator schema 校验；正确性由符号层负责
- D. 它把 LLM 生成的计划直接执行，失败后再重试

**Q4.** 运行本节 `htn_demo()`，case C 再次请求 `ship_feature_with_migration` 时发生了什么？

- A. 没有可用 method，命中 `cached_methods`，直接展开缓存的分解，不调用 LLM
- B. 抛出异常，因为该任务没有 method
- C. 先查到 `methods` 里新注册的 method，按 method 展开
- D. 再次调用 LLM，`llm.calls` 增加 1

**Q5.** 演化 demo 的 evaluator 为 `Σ_{x=-5..5} (3x+7 − (ax+b))²`。个体 `a=3, b=4` 的 fitness 是：

- A. 9
- B. 99
- C. 33
- D. 110

**Q6.** 在 `HTNPlanner.plan` 中，LLM 返回分解后，代码在**同一处**立刻做的校验是：

```python
            if not all(s in self.operators or s in self.methods for s in suggested):
                return None
```

关于这行代码，说法正确的是：

- A. 它已经检查了每个子任务的前置条件是否满足
- B. 它只检查子任务**名字**是否是已知的 operator 或已有 method 的任务；前置条件是在随后的 `_expand` 中逐步模拟检查的
- C. 它会把未知的子任务名自动注册为新的 operator
- D. 只要有一个子任务名合法就会通过

**Q7.** 按讲义"When to use which"表格，下列匹配**错误**的是：

- A. 带硬约束的排程 → HTN + ChatHTN（可证明的正确性）
- B. 有测试的代码改进 → AlphaEvolve（测试就是 evaluator）
- C. 政策约束下的自动化 → HTN（前置条件编码政策）
- D. 写一篇营销博客 → AlphaEvolve（让 LLM 评委打分作为 fitness）

**Q8.** 演化 demo 每一代保留前 3 名作为 survivors，每个 survivor 变异出 3 个 children。那么每一代调用 `evaluator` 多少次？整个程序（含初始种群、12 代）一共调用多少次？

- A. 每代 6 次，共 78 次
- B. 每代 12 次，共 150 次
- C. 每代 9 次，共 114 次
- D. 每代 18 次，共 222 次

---

## 三、动手 / 代码题

**Q9.**（读代码找 bug）下面是 `plan()` 中 LLM fallback 的分支：

```python
        if not applicable and task in self.cached_methods:
            subtasks = self.cached_methods[task]
            return self._expand(list(subtasks), state, depth)
        if not applicable:
            suggested = self.llm.decompose(task, state)
            if suggested is None:
                return None
            if not all(s in self.operators or s in self.methods for s in suggested):
                return None
            self.cached_methods[task] = suggested
            return self._expand(list(suggested), state, depth)
```

1. 用一个新建的 planner，在**空状态** `set()` 下请求 `ship_feature_with_migration`，返回什么？`cached_methods` 里会留下什么？
2. 如果脚本化 LLM 对任务 `bad` 返回 `("open_pr",)`，在状态 `{"logged_in"}` 下第一次请求得到 `None`。之后再请求 `bad`，LLM 还有机会给出别的分解吗？为什么这违背了讲义说的"reject invalid decompositions"？
3. 给出修复。

**Q10.**（补全函数）讲义练习 1 要求加入回溯。当前代码只用 `applicable[0]`：

```python
        method = applicable[0]
        return self._expand(list(method.subtasks), state, depth)
```

请改写 `plan()` 中处理复合任务的部分，使它：① 依次尝试所有前置条件满足的 method，任一成功即返回；② 全部失败（或没有可用 method）时，再尝试缓存分解与 LLM fallback；③ 只有展开成功的 LLM 分解才进入缓存。

**Q11.**（改造代码）讲义练习 2 说："when the LLM decomposes task `T` in **state pattern `P`**, store the result"。本节代码的缓存是 `cached_methods: dict[str, tuple[str, ...]]`，键只有任务名。

1. 这种缓存键会造成什么问题？举一个具体例子。
2. 把缓存改造成"任务 + 状态模式"的形式，说出你如何定义"状态模式"，以及命中缓存后为什么仍然需要 `_expand` 的前置条件检查。

**Q12.**（手算 + 改造）演化 demo 的实际运行轨迹（每代最优个体）如下：

```text
gen 1: (2, 3) 286    gen 2: (3, 3) 176    gen 3: (3, 4) 99
gen 4: (3, 5) 44     gen 5: (3, 6) 11     gen 6: (3, 7) 0
```

1. 证明 fitness 的闭式为 `110·(3−a)² + 11·(7−b)²`（提示：`Σx = 0`，`Σx² = 110`，共 11 个点）。
2. 解释为什么 `a` 在第 2 代就到了 3，而 `b` 一步一步爬到第 6 代才到 7。
3. 第 6 代就找到了 fitness = 0 的解，但程序仍跑满 12 代。加上早停后，总 evaluator 调用次数能从多少降到多少？
4. 讲义说 demo 是"evolutionary search over arithmetic programs: grow expressions"。代码真的在演化"程序/表达式"吗？如果要更接近 AlphaEvolve，你会怎样改？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 HTN（Hierarchical Task Network）？它和让 LLM 直接写一份自由文本计划相比，多提供了什么保证？代价是什么？

**Q14.**（原理深挖）ChatHTN 如何在引入 LLM 的同时保持计划的 soundness？以本节代码为例，指出它在哪些地方**没有完全兑现**这个承诺。

**Q15.**（原理深挖）AlphaEvolve 为什么要求 evaluator 必须"确定、快速、可机器检查"？如果用 LLM-as-judge 当 fitness 会发生什么？

**Q16.**（场景设计）你要用 AlphaEvolve 风格的演化搜索来优化公司数据仓库里一条慢 SQL 查询。请设计 evaluator、变异算子、选择策略和防作弊措施。

**Q17.**（追问型）既然 HTN 能保证正确、AlphaEvolve 能找到更优解，为什么讲义说"Reach for ReAct or ReWOO first"？你如何判断一个任务需要升级到这两种规划器？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："Operators — primitive actions with preconditions and effects"。B 的 Method 是"把复合任务分解成子任务的方式"，自身不执行；C 的复合任务需要被分解，不能直接执行；D 的 State 是"一组事实"。代码中对应 `Operator(name, preconditions, effects_add, effects_remove)`。

### Q2 — 答案：D

A、B、C 都是讲义"Published wins"的原文内容（48 次标量乘法；0.7% 的 Google 算力；FlashAttention 提速 32%）。D 是 `quiz.json` 里的干扰项，讲义没有提到任何 HumanEval 成绩。补充：Strassen 算法递归用于 4×4 时需要 7 × 7 = 49 次乘法，48 次即少了一次。

### Q3 — 答案：C

讲义："every plan produced is provably sound because LLM suggestions only enter as candidate decompositions, never as direct plan edits. The symbolic layer owns correctness; the LLM expands the method library." A 是 `quiz.json` 的干扰项，ChatHTN 不靠微调；B 投票不能提供"可证明"的保证；D 正是 ChatHTN 要避免的"直接执行 LLM 计划"。

### Q4 — 答案：A

case B 时 LLM 的分解已经写入 `self.cached_methods`。case C 中 `self.methods` 里仍然没有 `ship_feature_with_migration`（缓存不会注册为 method，所以 C 错），`applicable` 为空，于是命中第一个分支 `if not applicable and task in self.cached_methods`，直接 `_expand`。实际输出 `new LLM calls this round: 0  (expect 0)`。这就是讲义"online method learning"的最简版本。D 是没有缓存时（case B）的行为；B 错，没有 method 时会走缓存或 LLM fallback，而不是抛异常。

### Q5 — 答案：B

`(3x+7) − (3x+4) = 3`，11 个点每个误差平方 9，合计 99。闭式 `110(3−a)² + 11(7−b)² = 0 + 11×9 = 99`（已用 Python 验证）。实际运行中第 3 代最优个体正是 `a=3 b=4 fitness=99.00`。A 只算了一个点；C 是把误差 3 当成线性累加的结果；D 是 `a` 偏 1、`b` 正确时的值 `110×1`。

### Q6 — 答案：B

这行只做**名字层面**的校验：每个子任务名必须是已知 operator，或是 `self.methods` 里有键的复合任务。前置条件的检查发生在 `_expand` 中：逐个子任务递归规划，并对返回的每个步骤执行 `op.applicable(current_state)` 再 `op.apply`。A 错，名字合法不代表前置条件满足（见 Q9 的 `("open_pr",)`）；C 错，代码不会注册任何东西到 `operators`；D 错，`all(...)` 要求每一个都合法。注意一个副作用：只能通过 LLM 分解的复合任务（不在 `self.methods` 里）不能作为另一个 LLM 分解的子任务。

### Q7 — 答案：D

A、B、C 都来自讲义表格。D 违反了讲义的两条警告："Evolutionary search over prose answers does not converge"以及"'Ask the LLM if the code is better' is not a fitness function"。`outputs/skill-hybrid-planner.md` 也把"开放式任务（write a blog post）"列为两种模式的 hard reject，应使用 ReAct。

### Q8 — 答案：C

每代：3 个 survivors × 3 个 children = 9 次 `evaluator` 调用（survivors 的 fitness 已缓存在元组里，不重新算）。总数：初始 6 个个体 6 次 + 12 代 × 9 = 114 次（已在探针脚本里计数验证）。A 把种群大小 6 当成每代调用数；B、D 都是误把每个 survivor 的 children 数算成 4 或 6。

### Q9 — 参考答案

1. 实际运行结果：返回 `None`；`llm.calls == ['ship_feature_with_migration']`；而 `cached_methods == {'ship_feature_with_migration': ('open_editor', 'write_tests', 'run_tests', 'open_pr')}`。原因：名字校验通过后，代码**先写缓存再展开**；`_expand` 在第一步 `open_editor`（需要 `logged_in`）就失败了，但缓存已经写入。
2. 没有机会了。第二次请求时 `applicable` 为空且 `task in self.cached_methods`，直接走缓存分支、再次失败，**永远不会再问 LLM**。讲义的循环是"validate against the operator schema; reject invalid decompositions"——被拒绝的分解不应该进入 method 库；而这里失败的分解被"学习"成了永久规则，等于缓存投毒（cache poisoning）。实际验证：`bad` 被缓存为 `('open_pr',)` 后，只有当状态里恰好已有 `tests_passing` 时才能成功。
3. 修复：只在展开成功后缓存；缓存展开失败时允许回落到 LLM。

```python
        if not applicable:
            if task in self.cached_methods:
                cached_plan = self._expand(list(self.cached_methods[task]), state, depth)
                if cached_plan is not None:
                    return cached_plan
            suggested = self.llm.decompose(task, state)
            if suggested is None:
                return None
            if not all(s in self.operators or s in self.methods for s in suggested):
                return None
            sub_plan = self._expand(list(suggested), state, depth)
            if sub_plan is not None:
                self.cached_methods[task] = suggested   # 只缓存验证通过的分解
            return sub_plan
```

更稳妥的做法是把缓存键加上状态模式（见 Q11），并给缓存条目记录成功 / 失败次数。

### Q10 — 参考答案

```python
    def plan(self, task, state, depth=0, max_depth=12):
        if depth > max_depth:
            return None
        if task in self.operators:
            return [task] if self.operators[task].applicable(state) else None

        # ① 依次尝试所有可用 method（回溯）
        for method in self.methods.get(task, []):
            if not method.applicable(state):
                continue
            sub_plan = self._expand(list(method.subtasks), state, depth)
            if sub_plan is not None:
                return sub_plan

        # ② 缓存分解
        if task in self.cached_methods:
            sub_plan = self._expand(list(self.cached_methods[task]), state, depth)
            if sub_plan is not None:
                return sub_plan

        # ③ LLM fallback，验证成功才缓存
        suggested = self.llm.decompose(task, state)
        if suggested is None:
            return None
        if not all(s in self.operators or s in self.methods for s in suggested):
            return None
        sub_plan = self._expand(list(suggested), state, depth)
        if sub_plan is not None:
            self.cached_methods[task] = suggested
        return sub_plan
```

已实际验证：给 `ship` 配两个 method（`m1` 需要 `tests_passing` 才能走通，`m2` 是一步 `hotfix`），在 `{"logged_in"}` 下原代码返回 `None`，改写后返回 `['hotfix']`；LLM 分解在空状态下失败时不再写入缓存。

要点：
- 原代码只要有可用 method，就**只**试 `applicable[0]`，它失败了也不会试第二个 method，更不会问 LLM。
- 因为 `_expand` 从 `set(state)` 复制状态、失败时直接返回 `None`、不修改调用方的 `state`，所以"回溯"不需要显式撤销——这是用不可变状态（每步 `apply` 返回新集合）的好处。
- 这是"规划期回溯"。讲义练习 1 说的是"当 operator 的后置条件在**运行时**失败时回滚"，那需要真实执行 + 补偿动作，是更难的"执行期回溯"。
- 注意：原代码中 LLM fallback 的条件是"没有**前置条件满足**的 method"（`not applicable`），而不是"所有 method 都失败"；改写后语义变宽了，需要在面试中能讲清楚这个差别。

### Q11 — 参考答案

1. 问题：同一个任务在不同状态下应该有不同的分解。例如 `deploy` 在 `{"has_migration"}` 状态下应分解为"备份 → 迁移 → 发布"，在无迁移状态下只需"发布"。键只有任务名时，第一次学到的分解会被用到所有状态上；失败时（结合 Q9 的 bug）还会把错误分解永久锁住。实际验证：被缓存的 `bad → ("open_pr",)` 在 `{"logged_in"}` 下失败、在 `{"tests_passing"}` 下成功，缓存本身无法区分这两种情况。
2. 一种做法是用"分解中各 operator 实际依赖的前置事实"作为状态模式：

```python
def relevant_facts(subtasks, operators):
    facts = set()
    for s in subtasks:
        if s in operators:
            facts |= set(operators[s].preconditions)
    return frozenset(facts)

# 存：key = (task, frozenset(state & relevant_facts(suggested, ops)))
# 查：遍历同 task 的条目，若 条目的模式 ⊆ 当前 state，则命中
```

即使命中，也必须走 `_expand` 做逐步前置条件检查：缓存只是"候选 method"，不是"已证明正确的计划"。前置条件检查是 ChatHTN soundness 的来源，缓存只省 LLM 调用、不能省校验。讲义提到的 online method learning（OpenReview `gwYEDY9j2x`）用回归（regression）把具体分解泛化成带前置条件的 method，思路与此一致，讲义称最多减少 75% 的 LLM 查询。

### Q12 — 参考答案

1. 误差 `e(x) = (3−a)x + (7−b)`。`Σe² = (3−a)²Σx² + 2(3−a)(7−b)Σx + 11(7−b)²`。在 x = −5..5 上 `Σx = 0`，`Σx² = 2×(1+4+9+16+25) = 110`，因此 `fitness = 110(3−a)² + 11(7−b)²`。用 Python 在一个网格上逐点比对，两者完全一致。验证：`(2,3)` → `110 + 176 = 286`，与种子种群输出一致。
2. `a` 方向的"坡度"是 `b` 方向的 10 倍：`a` 偏 1 罚 110，`b` 偏 1 只罚 11。选择压力几乎全部压在 `a` 上，`a=3` 的个体一出现就占据前列；之后 `a` 固定，`b` 每代只要被 ±1 或 ±2 的变异向 7 推进一步就会被选中。实际轨迹中第 2 代 `b` 没动、第 3～6 代 `b` 每代只前进 1（随机性所致，变异最多能一次走 2）。
3. 第 6 代首次出现 fitness = 0。若在 fitness = 0 时停止：`6 + 6 × 9 = 60` 次，比 114 次减少约 47%。生产中常用"连续 k 代无改进"或"达到阈值"早停，因为 evaluator 往往是最昂贵的部分（AlphaEvolve 中可能是跑一整套基准）。
4. 不是。代码只是在固定的 `a·x + b` 模板里调两个整数，相当于一个随机爬山 + 精英保留；fitness 也是平方误差而不是讲义说的 `|f(x) − target|`。更接近 AlphaEvolve 的改法：个体表示成表达式树或代码字符串；变异由（多个）LLM 生成 diff 或改写；evaluator 在固定测试集上执行程序并返回确定的分数（对抛异常、超时的个体给最差分）；维护多样性（去重、按结构分岛）；记录谱系便于分析。

### Q13 — 参考回答要点

- **定义**：HTN 由复合 / 原子任务、method（带前置条件的分解规则）、operator（带前置条件与效果的原子动作）和 state（事实集合）组成；规划就是把目标任务递归分解成一串 operator，并保证每一步的前置条件在当时的状态下成立。
- **多出的保证**：soundness by construction——只要 operator 的前置条件 / 效果建模正确，产出的计划在模型内必然可执行；政策可以写进前置条件（讲义："Preconditions encode policy"），不会出现 LLM "幻觉出一步"。
- **代价**：要人工建模 operator 和 method（知识工程成本高）；领域外的任务没有 method 就无解（ChatHTN 正是用 LLM 补这个缺口）；保证只在模型内成立，现实世界与模型不符时（例如执行时失败）仍需运行时监控与回滚。
- 加分点：说明 HTN 比 LLM 早很多年，至今仍是"可证明正确的计划"的参考方法；能举出 `pyhop`、`SHOP3` 等实现。

### Q14 — 参考回答要点

- **机制**：先试 method 库；无可用 method 时把"任务 + 状态"发给 LLM；把回答解析成候选子任务；对照 operator schema 校验，不合法就拒绝；递归。LLM 只能**扩充 method 库**，不能直接修改计划；最终计划中的每一步都由符号层检查前置条件。
- **本节代码兑现的部分**：`_expand` 对每个原子步骤做 `op.applicable` + `op.apply` 的顺序模拟，所以**返回的非 None 计划**确实在模型内可执行。
- **没完全兑现的地方**：
  1. 先缓存后验证：失败的分解被缓存，并且之后永远不再问 LLM（Q9）；
  2. 缓存键只有任务名，不含状态模式（Q11）；
  3. 没有回溯：只用第一个可用 method（Q10）；
  4. 名字校验过严也过松：合法名字不代表合理，只能由 LLM 分解的复合任务又不能嵌套出现；
  5. 脚本 LLM 对 `ship_feature_with_migration` 返回的分解里**根本没有迁移步骤**——计划在模型内 sound，但没有完成任务的真实意图。这说明 soundness ≠ 正确完成目标，还需要目标条件检查（例如要求结束状态包含 `migration_applied`）。
- 加分点：指出讲义"trace 显示 mid-plan LLM fallback"与代码不符——代码里 fallback 发生在顶层任务上。

### Q15 — 参考回答要点

- 演化搜索的唯一"方向感"来自选择：每一代保留 fitness 最好的个体。如果 fitness 有噪声，选择就会保留"运气好"的个体，噪声在多代中累积，搜索不收敛。
- **确定**：同一程序打两次分应相同，否则无法比较；**快速**：要评估成千上万个候选，evaluator 是主要成本；**可机器检查**：不需要人工、可自动化。
- LLM-as-judge 的问题：随机性（同一输入多次打分不同）；可被"讨好"（变异会学会写出让评委满意的注释或格式，而不是真正更好的代码）；与真实目标偏离（评委喜欢的不一定更快更对）；成本高。`outputs/skill-hybrid-planner.md` 明确把"evaluator 调用 LLM judge"列为 hard reject。
- 讲义中的成功案例都有硬指标：乘法次数、回收的算力比例、实测速度。
- 常见误区：以为"找一个强模型打分"就够了；或者 evaluator 只看部分测试导致过拟合测试集（reward hacking），需要留出集。

### Q16 — 参考回答要点

- **evaluator**：在固定快照（或采样后的生产数据副本）上运行候选 SQL：① 正确性门槛——结果集与原查询完全一致（排序后哈希比对），不一致直接最差分；② 性能——多次运行取中位数延迟，或用 `EXPLAIN` 的代价估计做快速预筛；③ 资源约束——扫描字节、内存上限、超时直接淘汰。为了确定性，固定数据、固定缓存状态（先预热或每次冷启动）、取多次中位数。
- **变异**：LLM 提出改写（改 JOIN 顺序、加 CTE、改谓词下推、改用窗口函数、建议索引）；也可加入规则化变异作补充；用 ensemble（快模型广撒网 + 强模型深改写），对应讲义"Gemini 2.0 Flash/Pro ensemble"。
- **选择**：保留 top-k + 少量多样性个体；连续 N 代无改进早停；记录谱系。
- **防作弊**：多组参数 / 多个数据切片做评估，防止只对某个快照过拟合；禁止改动结果语义的"捷径"（如加 `LIMIT`）——正确性门槛就是为此；对涉及 DDL 的建议单独审批。
- 加分点：说明这正是讲义练习 4 的要求；指出最贵的是 evaluator，因此要分级评估（先代价估计、再真实执行）。

### Q17 — 参考回答要点

- 讲义："Most agent tasks don't need either. Reach for ReAct or ReWOO first." 两者都需要额外的结构：HTN 要求 operator/method 模型，AlphaEvolve 要求确定性 evaluator；没有这些结构时，强行使用只会增加工程成本，甚至给出"虚假的保证"。
- **升级到 HTN 的信号**：计划出错代价高且不可逆（合规、财务、调度）；规则可以写成前置条件 / 效果；需要向审计方证明"每一步都合规"。
- **升级到演化搜索的信号**：目标是"最优"而非"可行"；有快速、确定的打分器（测试、基准、模拟器）；愿意为大量候选评估付算力。
- **都不满足**：开放式任务、需要与人或环境交互的任务，用 ReAct / ReWOO，配合 Self-Refine 或评审即可。
- 加分点：可以组合——HTN 负责分解与政策，子任务中有可打分的部分再交给演化搜索（讲义练习 5），并能说出它在哪里过度设计。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：ReAct 式循环是本节反复强调的"默认首选"。
- [阶段 14 · 02 ReWOO 与 Plan-and-Execute：解耦 Planning](../../02-rewoo-plan-and-execute/docs/zh.md)：本节的先修课，HTN 是"先规划后执行"的符号化、可证明版本。
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../05-self-refine-and-critic/docs/zh.md)：没有可机器检查 fitness 时的替代方案（skill 文件中的 refusal 规则指向它）。
- [阶段 14 · 10 技能库与终身学习（Voyager）](../../10-skill-libraries-voyager/docs/zh.md)：把 LLM 产出的分解缓存为可复用技能，与 online method learning 思路相同。

### 本节被哪些后续内容用到
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：evaluator-optimizer 模式与"先用最简单方案"的原则。
- [阶段 14 · 25 多 Agent 辩论与协作](../../25-multi-agent-debate/docs/zh.md)：skill 文件建议在需要辩论式验证时阅读。
- [阶段 15 · 03 AlphaEvolve：演化式 Coding Agents](../../../15-autonomous-systems/03-alphaevolve-evolutionary-coding/docs/zh.md)：AlphaEvolve 的完整展开。
- [阶段 16 · 19 面向 LLMs 的 Swarm 优化（PSO、ACO）](../../../16-multi-agent-and-swarms/19-swarm-optimization-pso-aco/docs/zh.md)：另一类基于种群的搜索。
- [阶段 19 · 24 计划—执行控制流程](../../../19-capstone-projects/24-plan-execute-control-flow/docs/zh.md)：综合项目中的规划与执行控制。

### 延伸关键词
`HTN` · `SHOP3 / pyhop` · `STRIPS 前置条件与效果` · `ChatHTN` · `online method learning` · `AlphaEvolve` · `OpenEvolve` · `fitness function` · `elitism 精英保留` · `population diversity` · `reward hacking` · `early stopping`
