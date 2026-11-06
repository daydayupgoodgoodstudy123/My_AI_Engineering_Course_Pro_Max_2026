# 测验 · AlphaEvolve：演化式 Coding Agents（AlphaEvolve — Evolutionary Coding Agents）

> **阶段 15 · 自主系统 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | AlphaEvolve 是什么 | 讲义：Novikov et al., DeepMind, 2025。前沿 coding 模型（Gemini）+ 演化循环 + 机器可检验的 evaluator |
| 2 | 循环七步 | 种子程序 → 程序数据库（每个变体有分数）→ 采样父代 → LLM 提出修改 → 编译/运行/评估 → 按分数与特征向量入库 → 重复 |
| 3 | 代表性成果 | 讲义：4×4 复矩阵乘法 48 次标量乘法（Strassen 1969 年的界是 49，56 年来首次改进）；Borg 调度启发式回收约 0.7% 集群算力；FlashAttention kernel 提速 32.5% |
| 4 | 为什么 LLM + 搜索胜过单独任一方 | LLM 产出可编译、语义合理的局部修改，把搜索集中在合理邻域；evaluator 抓住 LLM 的 confabulation（虚构的正确性/复杂度/性能声明） |
| 5 | Evaluator 是架构本身 | 成功领域的 evaluator 都"快、确定、难以作弊"：矩阵乘法逐位比对、Borg 历史负载回放模拟器、kernel 正确性 + 真实硬件计时 |
| 6 | Reward hacking 是同一句话的另一面 | 演化优化的是 evaluator 测的东西；evaluator 有漏洞，循环就会找到漏洞（空提交拿"最快"、背测试、删注释刷"代码质量"） |
| 7 | MAP-elites | 按特征向量划分网格，每格只保留该描述符下的最优变体，用多样性对抗早熟收敛 |
| 8 | Island model | 多个独立子种群并行演化、定期迁移，防止过早收敛 |
| 9 | Held-out evaluator | 讲义：用 LLM 从未见过、在评估时临时生成的输入，防止记忆；即便如此部署前仍需严格审查 |
| 10 | 同一配方的家族 | AlphaEvolve、FunSearch（cap set）、AI Scientist v2、Darwin Godel Machine：都是"生成器 + 评估器 + 循环"，差别在 evaluator 评什么、多严格 |

### 核心技能（能动手做到）

- [ ] 画出 AlphaEvolve 的循环，并说出每一步在 `main.py` 中对应哪个函数
- [ ] 手算 `cell_key`、`depth`、`max_const` 和任意表达式在训练点/测试点上的 MSE
- [ ] 识别 `main.py` 中"held-out 测试集被用进了选择信号"的方法论问题，并给出三集划分或"评估时生成新输入"的修正
- [ ] 改造训练集，真正复现"训练误差为 0、测试误差巨大"的过拟合
- [ ] 为一个新领域写出 evaluator 规格：正确性条件、性能指标、held-out 输入生成规则、反 reward hacking 检查
- [ ] 用 `outputs/skill-evaluator-rigor-audit.md` 判断一个领域是否适合 AlphaEvolve 式闭环

---

## 二、基础自测（选择题）

**Q1.** 讲义解释"为什么 LLM + 演化搜索胜过任一方单独使用"。下列哪一项最准确？

- A. LLM 能保证生成的代码一定正确，演化只是为了加速
- B. 演化算法的随机变异比 LLM 更擅长写出可编译代码
- C. LLM 产出可编译、语义合理的定向修改，把搜索集中在合理邻域；evaluator 则负责抓住 LLM 虚构的正确性和性能声明
- D. 两者结合后不再需要 evaluator

**Q2.** 关于 MAP-elites，正确的描述是：

- A. 按特征向量（描述符）划分网格，每个格子只保留具有该描述符的最优变体，从而保持多样性
- B. 只保留全局得分最高的一个程序，其余全部丢弃
- C. 把种群分成多个岛屿，定期迁移个体
- D. 一种对 LLM 进行 fine-tune 的方法

**Q3.** 讲义给出的 AlphaEvolve 对 reward hacking 的修复措施是：

- A. 改用 LLM-as-judge 给代码打分
- B. 把 evaluator 的源码放进 prompt，让 LLM 知道评分规则
- C. 只用固定的一组公开测试用例，保证可复现
- D. 使用 LLM 从未见过、在评估时生成输入的 held-out evaluator；即便如此，任何部署前仍需严格审查

**Q4.** 在 `main.py` 中，表达式 `((x * 5) + -1)`（即 `("add", ("mul", ("x",), ("num", 5.0)), ("num", -1.0))`）的 `cell_key` 是：

```python
def cell_key(e: Expr) -> tuple[int, int]:
    d = min(depth(e), 6)
    c = min(int(max_const(e) / 2), 4)
    return (d, c)
```

- A. `(2, 5)`
- B. `(3, 2)`
- C. `(3, 5)`
- D. `(2, 2)`

**Q5.** 运行 `python main.py --no-holdout` 时会发生什么？

- A. Run A 与 Run B 都会运行，但都不使用测试集
- B. 程序报错，因为 Run A 需要测试集
- C. 只跳过 Run A；Run B（train-only）无论是否加该参数都会运行，输出与默认运行时的 Run B 完全相同
- D. 只运行 Run A

**Q6.** 在 Run A（`use_holdout=True`）中：

```python
    def signal_of(c: Candidate) -> float:
        return 0.5 * (c.train_score + c.test_score) if use_holdout else c.train_score
```

关于 Run A 输出的 "test MSE"，下列说法最准确的是：

- A. 测试点参与了选择信号，因此 Run A 的 test MSE 不再是对泛化能力的无偏估计；要评估泛化，还需要第三组从未参与选择的数据
- B. 测试点只用于最终报告，没有影响搜索
- C. 测试点被 LLM（`mutate`）看到并记忆了
- D. Run A 的 test MSE 一定高于 train MSE

**Q7.** 关于 `mse` 中的异常处理：

```python
        try:
            y = evaluate_expr(e, x)
        except (OverflowError, ValueError):
            return float("inf")
```

下列说法正确的是：

- A. 任何数值溢出都会被捕获并返回 `inf`
- B. 浮点乘法溢出会抛出 `OverflowError`
- C. `ValueError` 永远不会被触发
- D. Python 浮点乘法溢出时不会抛异常而是得到 `inf`，`inf + (-inf)` 还会得到 `nan`；所以这个 `except` 基本捕获不到溢出，MSE 可能是 `inf` 或 `nan`

**Q8.** 我们用 seed 0–49 分别跑了 Run A 与 Run B（1500 代、种群 20）：Run A 有 23 次、Run B 有 22 次精确找回目标函数（train 与 test MSE 均为 0）；**所有** 100 次运行中都没有出现"train MSE 为 0 而 test MSE 很大"的情况。由此最合理的结论是：

- A. 默认 seed 下 Run B 的 train-to-test gap（+2.10）证明了 train-only evaluator 会导致严重过拟合
- B. 在默认设定下，目标函数本身就在搜索空间内且能让训练误差为 0，train-only 搜索并没有"背训练点"的动机；单个 seed 上的差距主要来自搜索路径的随机性和外推误差，而不是 reward hacking
- C. Run A 和 Run B 完全等价，测试集毫无作用
- D. 演化搜索无法找到精确解

---

## 三、动手 / 代码题

**Q9.**（手算 MSE）默认运行中 Run B 的最优表达式是 `(((((x * x) * 2.5) + x) + -2) + x)`，即 `2.5x² + 2x − 2`；目标是 `2x² + 3x − 1`。

1. 写出误差函数 `d(x) = f(x) − target(x)`。
2. 手算它在 `train_xs = [-2, -1, 0, 1, 2, 3]` 上的 MSE，验证输出 `2.2917`。
3. 在 `test_xs = [-2.5, -1.5, ..., 3.5]` 上哪个点贡献的误差最大？这说明 "train-to-test gap" 在这里主要反映了什么？

**Q10.**（让过拟合真正出现）讲义说"removing the held-out test lets the loop overfit spectacularly"，但默认设定下几乎看不到（见 Q8）。请修改 `run_loop`，让训练集只有 `[0.0, 1.0]` 两个点，比较 train-only 与 holdout 两种信号在 20 个 seed 上的结果，并解释为什么这次出现了过拟合。

**Q11.**（修正评估方法）基于 Q6 指出的问题，按讲义 "inputs generated at evaluation time" 的思路改写评估：每次评估子代时临时生成一批新的随机输入作为 held-out 信号，最终再用一组从未参与选择的"报告集"给出泛化误差。写出关键代码，并说明这样做的代价。

**Q12.**（讲义练习 5：写 evaluator 规格）你要用 AlphaEvolve 式循环优化一个"给 64 位整数数组排序"的函数。请写出 evaluator 规格，包括：(a) 正确性条件，(b) 性能指标，(c) held-out 输入生成规则，(d) 至少两条反 reward hacking 检查。

---

## 四、面试高频题

**Q13.**（基础必考）请介绍 AlphaEvolve 的架构。为什么说"evaluator 才是架构"，而生成器是可替换的？

**Q14.**（原理深挖）演化搜索中为什么需要 MAP-elites 或 island model？如果只保留当前最优解（贪心爬山）会出现什么问题？特征向量（描述符）应该怎么选？

**Q15.**（工程实践）你想在公司里用 AlphaEvolve 式循环自动优化一个线上服务的 SQL 查询或 GPU kernel。请设计 evaluator、搜索预算和上线流程。

**Q16.**（场景设计）产品经理提议："用 LLM 当评委给营销文案打分，再用演化循环自动优化文案。" 你怎么评估这个方案？

**Q17.**（追问型）FunSearch、AlphaEvolve、AI Scientist v2、Darwin Godel Machine 都是"生成器 + 评估器 + 循环"。它们的 evaluator 有什么不同？哪一个最容易出现 reward hacking？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："The LLM can produce compilable, semantically plausible modifications ... The evaluator, in turn, catches the LLM's confabulations." 讲义举例：LLM 会自信地声称某函数"渐近 O(n log n)"而实际是 O(n²)，真实计时一测便知。

- A 错：LLM 的上限恰恰是 confabulation，不能保证正确。
- B 说反了：对 2000 行 Python 文件做随机变异"几乎总会产生语法错误"。
- D 错：讲义强调去掉 evaluator，循环就只会优化"好看的代码"。

### Q2 — 答案：A

讲义 Key Terms："Grid keyed by feature vectors; each cell holds the best variant with that descriptor"。B 是贪心精英保留；C 是 island model；D 无关。`main.py` 中的 `archive: dict[tuple[int, int], Candidate]` 就是一个最简 MAP-elites：键是 `(深度, 常数量级)`，值是该格最优候选。

### Q3 — 答案：D

讲义："The fix in AlphaEvolve: ship a held-out evaluator the LLM has never seen, with inputs generated at evaluation time. Even then, DeepMind recommends strong review on any proposed deployment."

- A 错：skill 文件把"LLM judge 没有机器可检验的 ground truth"列为 hard reject。
- B 错：让 LLM 看到评分细节只会让它更容易针对性地钻空子。
- C 错：固定公开测试正是讲义例子"memorizing tests and overfitting"的温床。

### Q4 — 答案：B

- `depth`：叶子为 1，`mul(x, 5)` 为 2，外层 `add` 为 3，`min(3, 6) = 3`。
- `max_const`：常数有 5 和 −1，取绝对值最大为 5；`int(5 / 2) = int(2.5) = 2`，`min(2, 4) = 2`。

所以是 `(3, 2)`（已运行验证）。A 把深度算成 2、又没做 `/2` 分桶；C 漏了分桶；D 深度算错。常数桶宽为 2：|c| ∈ [0,2) → 0，[2,4) → 1，[4,6) → 2，……，≥ 8 都归入 4。

### Q5 — 答案：C

```python
    if not args.no_holdout:
        print("\nRun A: ...")
        ...
    print("\nRun B: no held-out test ...")
```

Run B 不在任何条件分支里，总会运行；`--no-holdout` 只是跳过 Run A。由于每次 `run_loop` 都用 `seed=DEFAULT_SEED` 重新设种子，两种方式下 Run B 的输出完全相同（已实际运行验证）。讲义练习 1 写"Disable the held-out evaluator (flag `--no-holdout`) and re-run"，容易让人以为这个参数改变了 Run B 的行为，其实对比在默认运行中就已经完成了。

### Q6 — 答案：A

`signal_of` 把 `test_score` 计入适应度，于是测试点影响了"谁能进入 archive"和"最后选谁"，它已经成了训练信号的一部分。在机器学习意义上，Run A 的 test MSE 是"被优化过的误差"，不能当作泛化估计。B 错：测试点参与了每次入库比较；C 错：`mutate` 完全不看任何数据，"LLM 没见过"这一点在代码里确实成立——这正是讲义所说的 held-out 的含义（生成器看不到），但它与"统计意义上的留出集"是两回事；D 错，Run A 最终两者都是 0。

### Q7 — 答案：D

Python 的 `float` 乘法溢出得到 `inf`，不抛 `OverflowError`（只有 `**`、`math.exp` 等少数运算会抛）。实测：`mse(("mul", ("num", 1e200), ("num", 1e200)), [1.0])` 返回 `inf`；`1e400 − 1e400` 形式的表达式返回 `nan`。`nan` 与任何数比较都为 `False`，所以 `signal_of(child) < signal_of(incumbent)` 永不成立——`nan` 候选不会替换已有个体，但若某格为空仍可能被放进去。A、B 错；C 不完全对：`evaluate_expr` 遇到未知 tag 时会 `raise ValueError(tag)`，只是正常流程下不会出现。

### Q8 — 答案：B

- 目标 `2x² + 3x − 1` 可以被这个文法精确表示，并在训练集上达到 0 误差；所有训练误差为 0 的运行，测试误差也为 0（6 个点唯一确定一个二次多项式，而 `mutate` 很难构造出 5 次插值多项式）。
- 默认 seed 下的 gap 来自一个"没拟合好"的解在外推区间（x = −2.5、3.5）误差放大（见 Q9），这是欠拟合 + 外推，不是 reward hacking。
- A 错：单个 seed 不能支持结论，且不是过拟合；C 错：50 个 seed 的平均 test MSE，Run A 为 2.17、Run B 为 4.91，测试点参与选择确实让 Run A 更重视外推区间；D 错，近一半运行找到了精确解。

### Q9 — 参考答案

1. `d(x) = (2.5x² + 2x − 2) − (2x² + 3x − 1) = 0.5x² − x − 1`。
2. 训练点：

| x | d(x) | d² |
|---|------|----|
| −2 | 3 | 9 |
| −1 | 0.5 | 0.25 |
| 0 | −1 | 1 |
| 1 | −1.5 | 2.25 |
| 2 | −1 | 1 |
| 3 | 0.5 | 0.25 |

   和为 13.75，MSE = 13.75 / 6 = **2.2917**。

3. 测试点上 `d(−2.5) = 3.125 + 2.5 − 1 = 4.625`，平方 21.39，占测试误差总和 30.73 的约 70%；其余点的平方误差都在 0.14–2.64 之间，MSE = 30.73 / 7 = **4.3906**。测试集比训练集向左多延伸了 0.5（−2.5 < −2），二次误差函数在区间边缘快速增大。所以这里的 gap 主要反映**外推误差**，而不是"记住了训练点"。

### Q10 — 参考答案

`train_xs` 写死在 `run_loop` 内部，改成参数：

```python
def run_loop(generations, pop, use_holdout, seed=None,
             train_xs=(-2.0, -1.0, 0.0, 1.0, 2.0, 3.0),
             test_xs=(-2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5)):
    ...

best, _, _ = run_loop(1500, 20, use_holdout=False, seed=s, train_xs=[0.0, 1.0])
```

实测 20 个 seed（另外用一组从未参与选择的 28 个"新鲜点"评估泛化）：

| 信号 | 训练 MSE 中位数 | 测试 MSE 中位数 | 新鲜点 MSE 中位数 | 训练误差为 0 的次数 |
|------|---------------|---------------|-----------------|------------------|
| train-only | 0.0 | 104.25 | 113.1 | 14 / 20 |
| holdout（train + test 平均） | 0.0 | 0.0 | 0.0 | 13 / 20 |

train-only 下找到的解例如 `x² + 4x − 1`（测试 MSE 26.1）、`((1·x)·4·x + 1)·x − 1 = 4x³ + x − 1`（测试 MSE 3826.7）：在 x = 0、1 两点与目标完全一致（−1 和 4），其它地方错得离谱。

原因：两个点只能约束 2 个自由度，**无数个表达式都能让训练误差为 0**，train-only 的适应度无法区分它们——这才是讲义所说的 "the loop would optimize for the surface feature"。训练集越小、假设空间越大，过拟合越严重；默认 6 个点 + 二次目标的设定恰好让目标成为唯一的零误差解，掩盖了这一现象。

### Q11 — 参考答案

```python
def fresh_inputs(k=16, lo=-4.0, hi=4.0):
    return [random.uniform(lo, hi) for _ in range(k)]

REPORT_XS = [x / 8 for x in range(-32, 33)]   # 只在最后报告时使用

def evaluate_child(expr, train_xs):
    tr = mse(expr, train_xs)
    te = mse(expr, fresh_inputs())      # 每次评估都生成新的 held-out 输入
    return tr, te

# 搜索结束后：
best = min(archive.values(), key=signal_of)
print("report MSE:", mse(best.expr, REPORT_XS))   # 无偏的泛化估计
```

要点：

- **评估时生成输入**：生成器（以及任何可能的记忆机制）无法针对固定测试点优化，这是讲义给出的修复。
- **报告集独立**：选择信号用过的数据都不能再用于报告泛化——标准的 train / validation / test 三集划分。
- **代价**：
  - 评估结果带随机性，同一表达式两次得分不同；archive 比较时要么固定每代的输入批次，要么对已有个体重新评估，否则"幸运"的个体会长期霸占格子（skill 文件第 4 条：评分的 run-to-run 波动不能超过种群方差）；
  - 评估成本增加（更多输入点）；
  - 输入分布本身仍是人为设定，分布外的问题依然可能存在。

### Q12 — 参考答案

示例规格：

- **(a) 正确性**：输出是输入的一个排列（多重集相等），且单调不减；对每个测试输入与 `sorted()` 的结果逐元素比对；不得修改输入以外的全局状态；不得抛异常。
- **(b) 性能**：在固定硬件上，对 n ∈ {10, 10³, 10⁵, 10⁶} 各若干组输入测量 wall-clock 中位数（多次重复、预热、隔离 CPU）；报告各规模的时间而不是一个标量，避免只在某个规模上取巧。
- **(c) held-out 输入生成规则**：每次评估时用新的随机种子生成：均匀随机、已排序、逆序、大量重复值、全部相同、包含 `INT64_MIN/MAX`、长度 0 和 1、近乎有序（少量交换）等多种分布；种子不进入 prompt。
- **(d) 反 reward hacking 检查**：
  1. 检测是否直接调用 `sorted()`/`list.sort()`/外部库（若规则禁止）——静态检查 + 运行时 hook；
  2. 禁止缓存：同一输入的第二次调用不能明显快于第一次，且不同输入不得共享可变全局状态；
  3. 输出必须是新数组或按约定原地排序，防止"返回输入本身"在已排序用例上通过；
  4. 拒绝提交空函数或超时：超时视为失败而不是"很快"（对应讲义"rewarding time to complete rewarded submitting empty solutions"）；
  5. 内存上限检查，防止用超大查找表换时间。
- 加分点：把 evaluator 输出分解为多个信号（正确性、各规模性能、内存），而不是一个标量——skill 文件："Scalar scores amplify reward hacking."

### Q13 — 参考回答要点

- **架构**：程序数据库（带分数与特征向量，MAP-elites / islands 组织）→ 采样父代 → 构造 prompt（父代 + 若干高分变体 + evaluator 签名 + 任务描述）→ LLM（讲义：Gemini Flash 负责大量候选、Gemini Pro 负责难点）产出 diff → 编译运行 → evaluator 打分 → 入库 → 循环，运行数小时到数周。
- **evaluator 才是架构**：
  - 搜索只会朝 evaluator 的梯度走，evaluator 决定了"什么叫更好"；
  - AlphaEvolve 的每个成功都来自"快、确定、难作弊"的 evaluator（矩阵乘法逐位比对、Borg 历史负载回放、kernel 计时）；
  - 换一个更强或更弱的 LLM 只影响搜索效率，换一个有漏洞的 evaluator 则会让结果从"发现"变成"reward hacking"。
- 讲义原话："The architecture works because the evaluator is machine-checkable. It does not work where the evaluator isn't."
- 加分点：说出讲义的数字（48 次乘法 vs Strassen 49、Borg 约 0.7%、FlashAttention 32.5%），并指出这些都是"有客观度量"的领域。

### Q14 — 参考回答要点

- **问题**：贪心只保留最优解会**早熟收敛**到局部最优；很多改进需要先经过"暂时变差"的中间状态（例如换一种算法结构），贪心会把这些踏脚石丢掉。
- **MAP-elites**：按行为/结构特征划分网格，每格保留最优，强制保留多种"风格"的解；新子代只需在自己的格子里胜出即可存活。
- **Island model**：多个子种群独立演化，各自走不同路径，定期迁移交换优秀个体，兼顾探索与利用。
- **描述符的选择**：应反映"解的不同做法"，与目标分数相关性不太高；例如代码长度、循环嵌套深度、使用的数据结构、内存占用、编译器优化 pass 的类别（讲义练习 2）。`main.py` 用 `(表达式深度, 常数量级)`。
- 常见误区：描述符取得太细会导致格子太多、每格样本太少；太粗则多样性不足。`main.py` 中深度被截断在 6，所有深层表达式挤在同一列。

### Q15 — 参考回答要点

- **Evaluator**：
  - 正确性：在影子库/历史快照上对比新旧查询的结果集（或 kernel 输出逐元素在容差内比对），覆盖边界数据；
  - 性能：在与生产一致的硬件和数据规模上测延迟分布（p50/p99）、资源占用；多次重复去噪；
  - held-out：用评估时抽样的真实查询参数/输入形状，不放进 prompt；
  - 反作弊：禁止改变语义的提示（如跳过排序、减少返回列）、禁止依赖缓存命中、检查执行计划。
- **搜索预算**：限定代数、token、GPU 小时；设置提前停止条件；记录每次评估成本。
- **上线流程**：搜索产物只是"候选"；需要代码审查、安全审查、灰度发布（canary）、可回滚；skill 文件："If the proposed deployment surface is irreversible ... Require staged rollout and human sign-off."
- 加分点：说明 evaluator 必须确定性足够，评分噪声不能大于候选间差异，否则选出的是"运气好"的变体。

### Q16 — 参考回答要点

- **结论**：不适合闭环自动优化。skill 文件的 hard reject："Any loop where the evaluator is an LLM judge without machine-checkable ground truth. LLM judges can be gamed."
- **风险**：
  - 演化会优化"让评委高分"的表面特征：特定措辞、长度、情绪词、甚至对评委的 prompt injection；
  - 评委分数与真实转化率可能弱相关，越优化偏离越大（Goodhart）；
  - 营销文案涉及合规、品牌风险，属于"不可逆对外发布"。
- **替代方案**：LLM 生成候选 + 人工筛选；用真实 A/B 测试的点击/转化作为 evaluator（但成本高、延迟长、有统计噪声）；评委只作为初筛，最终由人审批；多个独立评委 + 规则检查（合规词表）。
- 加分点：对应 skill 文件 refusal rule："If the domain is unverified (creative writing ...), refuse and recommend a hybrid pipeline with human review instead of a closed loop."

### Q17 — 参考回答要点

| 系统 | 生成器 | Evaluator | 评什么 |
|------|-------|-----------|-------|
| FunSearch（2023） | PaLM / Codey | 正确性 | 组合数学（cap set 下界） |
| AlphaEvolve | Gemini | 正确性 + benchmark | 算法、kernel、调度器 |
| AI Scientist v2 | GPT / Claude | LLM 评审 + 实验 | ML 研究论文 |
| Darwin Godel Machine | agent 脚手架 | SWE-bench / Polyglot | agent 代码（讲义：SWE-bench 20% → 50%） |

- **最容易 reward hacking 的**：AI Scientist v2——评估依赖 LLM 评审，没有机器可检验的 ground truth；论文"看起来像好论文"与"结论真实可靠"之间差距很大（第 5 节详谈）。DGM 次之：benchmark 本身可被过拟合，且被修改的是 agent 自己，评分管线若与 agent 同处一个仓库就可能被改（第 4 节讲义：DGM 曾移除工具插入的幻觉检测标记来抬高分数）。
- **最不容易的**：FunSearch / AlphaEvolve 的数学类任务——结果可以被精确验证。
- 加分点：讲义总结 "All four are variations on the same recipe ... The differences are what the evaluator grades and how rigorous it is."

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 01 从聊天机器人转向长程 Agents](../../01-long-horizon-agents/docs/zh.md)：AlphaEvolve 一次运行数小时到数周，是典型的长程自主系统。
- [阶段 15 · 02 STaR、V-STaR、Quiet-STaR：自学推理](../../02-star-family-reasoning/docs/zh.md)：讲义称 AlphaEvolve 是"代码版 STaR"——用程序 evaluator 代替标签。
- [阶段 14 · 11 结合 HTN 与演化搜索的 Planning](../../../14-agent-engineering/11-planning-htn-and-evolutionary/docs/zh.md)：agent 中的演化搜索。
- [阶段 16 · 19 面向 LLMs 的 Swarm 优化（PSO、ACO）](../../../16-multi-agent-and-swarms/19-swarm-optimization-pso-aco/docs/zh.md)：另一类基于种群的搜索。

### 本节被哪些后续内容用到
- [阶段 15 · 04 Darwin Godel Machine：开放式自我修改 Agents](../../04-darwin-godel-machine/docs/zh.md)：把被演化的对象从"程序"换成"agent 自身"，同样使用 archive。
- [阶段 15 · 05 AI Scientist v2：达到研讨会论文水平的自主研究](../../05-ai-scientist-v2/docs/zh.md)：evaluator 换成 LLM 评审时会发生什么。
- [阶段 15 · 08 有界自我改进设计](../../08-bounded-self-improvement/docs/zh.md)：如何给自我改进循环设边界。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：本节"reward hacking is the other face"的系统讲解。
- [阶段 19 · 72 代码执行评估指标](../../../19-capstone-projects/72-code-exec-metric/docs/zh.md)：如何构建基于执行的代码 evaluator。

### 延伸关键词
`AlphaEvolve` · `FunSearch` · `MAP-elites` · `island model` · `quality-diversity` · `program database` · `machine-checkable evaluator` · `held-out inputs` · `reward hacking` · `Goodhart's law` · `Strassen` · `symbolic regression` · `genetic programming`
