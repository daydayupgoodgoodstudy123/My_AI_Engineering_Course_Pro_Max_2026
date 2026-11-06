# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 07 节 心智社会与多 Agent 辩论 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`dataclasses`；`math`、`random` 被导入但实际未使用），无需 LLM、无需网络

---

## 1. 这份代码在考察什么

讲义介绍的是 Du et al. 2023 的多 agent 辩论（multi-agent debate）：N 个 agent 先各自作答，之后每一轮都读取其他 agent 上一轮的答案并更新自己的答案，R 轮后多数表决。代码把这个过程搬到一个**数值问题**上（真值 `TRUE_ANSWER = 42.0`）：

1. **初始答案**：A=38.0、B=42.5、C=51.0，各带一个"置信度"（0.6、0.8、0.4）。
2. **一轮辩论**：每个 agent 把自己和其他人的答案按置信度加权平均，作为新答案；置信度每轮乘 1.05（上限 1.0）。
3. **度量**：`agreement_score`（离均值 0.1 以内的 agent 比例）和 `error_vs_truth`（均值与真值的距离）。
4. **对照组**：第 0 轮三个答案的均值，代表"self-consistency 基线"。

> 一句话：**用"加权平均"这个最简单的更新规则，让"各自作答 → 互相参考 → 逐轮收敛"的动力学变得肉眼可见。**

但读这份代码时要特别注意：**它的实际输出与它打印的结论相反**——辩论让误差从 1.83 **增大**到 2.50，而结尾的 Takeaways 却写着"1 round of exchange cuts the error most"。原因是一个更新顺序的 bug 加上"按置信度加权"本身不保证靠近真值。这正好可以用来理解讲义里"共识不等于正确"的警告（详见 3.3 与第 6 节）。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `TRUE_ANSWER` | 常量 | 真值 42.0，只用于评估 | 评测用的 ground truth |
| `DebateAgent` | dataclass | 名字、当前答案、置信度、历史；`initial` 记录初始答案，`revise` 加权平均更新 | 辩论中的一个 agent |
| `agreement_score` | 函数 | 离均值 ≤ `tol` 的 agent 比例 | 共识度（consensus） |
| `error_vs_truth` | 函数 | 所有 agent 均值与真值的绝对误差 | 正确性 |
| `run_debate` | 函数 | 打印第 0 轮，然后进行 R 轮更新并逐轮打印 | 辩论循环 |
| `fresh_team` | 函数 | 构造 A、B、C 三个 agent | 团队初始化 |
| `single_shot_majority` | 函数 | 第 0 轮答案的**均值**（名为 majority） | self-consistency 基线 |
| `main` | 函数 | 打印基线，跑 3 轮与 5 轮两场辩论，打印结论 | 演示入口 |

数据流：`main` → `fresh_team()` → `single_shot_majority` 得到基线 → `run_debate(team, rounds)`：`initial()` → 打印第 0 行 → 每轮对每个 agent 调 `revise(others)` → 打印该轮答案、共识度、误差。

---

## 3. 逐段精讲

### 3.1 `DebateAgent.revise`：按置信度加权平均

```python
@dataclass
class DebateAgent:
    name: str
    answer: float
    confidence: float
    history: list[float] = field(default_factory=list)

    def revise(self, others: list["DebateAgent"]) -> None:
        weights = [self.confidence] + [o.confidence for o in others]
        values = [self.answer] + [o.answer for o in others]
        total_w = sum(weights)
        new_answer = sum(w * v for w, v in zip(weights, values)) / total_w
        self.answer = new_answer
        self.confidence = min(self.confidence * 1.05, 1.0)
        self.history.append(self.answer)
```

- 新答案 = Σ(置信度 × 答案) / Σ置信度。这是对"读了别人的推理后更新观点"的极度简化：越自信的人话语权越大。
- 置信度每轮 ×1.05、封顶 1.0。所有 agent 同比例增长，所以在 B 封顶之前，权重**比例**不变；5 轮后实测置信度为 A 0.7658、B 1.0、C 0.5105。
- 这个规则隐含了讲义"sycophancy cascade"（谄媚级联）的雏形：话语权取决于"自信"而非"正确"。本例中最接近真值的 B（42.5）恰好最自信，但最离谱的 C（51.0）仍有 0.4 的权重，把共识拉高。
- `"DebateAgent"` 写成字符串是前向引用；文件已有 `from __future__ import annotations`，其实不加引号也可以。

### 3.2 两个度量：共识度与误差

```python
def agreement_score(agents, tol: float = 0.1) -> float:
    mean = sum(a.answer for a in agents) / len(agents)
    agree = sum(1 for a in agents if abs(a.answer - mean) <= tol)
    return agree / len(agents)

def error_vs_truth(agents) -> float:
    mean = sum(a.answer for a in agents) / len(agents)
    return abs(mean - TRUE_ANSWER)
```

- 讲义 Key Terms："Consensus — Not epistemic truth — just fraction-on-majority-answer. Can be confidently wrong." 代码把这两件事分开度量，正好可以看到"共识度到 1.0 时误差反而最大"。
- 对数值答案，"多数"用"离均值 0.1 以内"来近似；`tol` 很严格，前两轮共识度都是 0。实测把 `tol` 放宽到 0.5，第 2 轮就是 1.0——共识度的数值很依赖阈值的选择。
- `error_vs_truth` 看的是**均值**的误差，不是表决结果的误差；Du et al. 的最终答案是多数表决。

### 3.3 `run_debate`：一个"看起来同步、实际顺序"的更新 bug

```python
for r in range(1, rounds + 1):
    updates = []
    for a in agents:
        others = [o for o in agents if o is not a]
        updates.append((a, others))
    for a, others in updates:
        a.revise(others)
```

- 意图：先为每个 agent 收集"其他人"，再统一更新——这是同步更新（Jacobi 式）的写法，对应讲义算法第 2 步 "each agent is shown the other agents' round r-1 answers"。
- ⚠️ 实际：`others` 存的是 agent **对象的引用**，不是答案的快照。第二个循环里，A 先 `revise` 改了自己的 `answer`；轮到 B 时，B 看到的是 A **本轮已经更新过**的答案；C 又看到 A、B 的新答案。这是顺序更新（Gauss–Seidel 式），违背了"读上一轮答案"的设定。
- 手算第 1 轮验证：
  - A：`(0.6×38 + 0.8×42.5 + 0.4×51) / 1.8 = 77.2 / 1.8 = 42.889`；A 的置信度变 0.63。
  - B：`(0.8×42.5 + 0.63×42.889 + 0.4×51) / 1.83 = 44.49`——用的是 A 的**新**答案 42.889 和新置信度 0.63。
  - 输出中第 1 轮 A=42.89、B=44.49，与手算一致。
- **后果一：结果依赖 agent 的排列顺序**。实测 5 轮后的共识均值：顺序 A,B,C → 44.499；C,B,A → 40.949；B,A,C → 43.533。同一组人、同样的初始答案，换个发言顺序结论就差 3.5。
- **后果二：误差变大**。正确的同步更新下，三个 agent 用的是同一组权重和同一组上一轮答案，第 1 轮就全部等于 `77.2 / 1.8 = 42.889`（误差 0.889，优于基线 1.83），之后保持不变（实测）。顺序更新则让后更新的 agent 偏向已经被 C 拉高的值，最终收敛到 44.50（误差 2.50）。
- 修复方法：每轮开始先拍快照（`copy.deepcopy` 或只复制 `(answer, confidence)`），所有 agent 都基于快照更新。
- 其它小问题：`for a in agents: pass` 是无用的死代码；标签里已经写了 "(3 rounds)"，`print(f"... ({rounds} rounds)")` 又加了一次，输出成 "(3 rounds) (3 rounds)"。

### 3.4 `fresh_team` 与基线

```python
def fresh_team(seed: int) -> list[DebateAgent]:
    random.seed(seed)
    return [
        DebateAgent(name="A", answer=38.0, confidence=0.6),
        DebateAgent(name="B", answer=42.5, confidence=0.8),
        DebateAgent(name="C", answer=51.0, confidence=0.4),
    ]

def single_shot_majority(agents) -> float:
    return sum(a.answer for a in agents) / len(agents)
```

- ⚠️ `random.seed(seed)` 设置了种子，但整个文件从未调用任何随机函数，`seed=1` 和 `seed=2` 构造出的团队完全相同。所以"5 轮"那场辩论的前 3 行与"3 轮"那场一模一样。
- ⚠️ `single_shot_majority` 名为"多数表决"，实际是**均值**。对数值问题，更接近"多数"含义、也更抗离群值的是**中位数**：`median(38, 42.5, 51) = 42.5`，误差 0.5，远好于均值的 1.83，也好于辩论后的 2.50。
- `TRUE_ANSWER` 只用于评估，agent 本身不知道真值——这一点是对的：真实辩论中也没有人知道答案。

### 3.5 `main` 与写死的结论

```python
print("\nTakeaways:")
print("  - 1 round of exchange cuts the error most.")
print("  - Rounds 2-3 compound.")
print("  - Beyond round 3 the gain per round shrinks (Du et al. plateau).")
print("  - Cost scales N * R LLM calls with growing context.")
```

- 前三条是写死的文字，与实际输出矛盾：第 1 轮误差从 1.83 升到 2.24，第 2、3 轮继续升到 2.43、2.48。真正"随轮数递减"的是**答案之间的分歧**（收敛），不是误差。
- 讲义 Build It 也说"A single round of exchange moves agents closer to the correct answer"——在这份代码里不成立。最后一条（N×R 次调用）是对讲义 Compute blowup 的正确转述。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用数值任务 + 加权平均模拟辩论 | 收敛过程可以用数字逐轮展示 | 真实辩论是文本推理，agent 会"被说服"或"坚持"，不是机械平均；平均只会收敛到初始答案的凸组合内，无法产生新答案 |
| 按置信度加权 | 模拟"自信者影响力更大" | 自信不等于正确，正是 sycophancy cascade 的来源；生产中应加入对抗角色或独立验证 |
| 置信度每轮 ×1.05 | 模拟"讨论后更确信" | 所有人一起变自信，没有信息依据；会加速锁定错误共识 |
| 引用式 `others`（顺序更新） | 代码简短 | 违背"读上一轮答案"，结果依赖发言顺序；应先快照再同步更新 |
| 用均值做基线和误差 | 简单 | 均值对离群值敏感；数值任务应比较中位数，离散答案用多数表决 |
| 严格的 `tol=0.1` | 让"完全一致"的门槛清楚 | 共识度对阈值敏感，0.1 与 0.5 的结论不同 |
| 写死 Takeaways | 传达讲义观点 | 与实测矛盾，容易让学习者"相信打印的文字而不是数据" |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` + 默认工厂 | `history: list[float] = field(default_factory=list)` | 每个 agent 有独立的历史列表 |
| 前向引用（字符串注解） | `others: list["DebateAgent"]` | 在类定义体内引用自身类型 |
| `zip` | `zip(weights, values)` | 把两个列表按位置配对 |
| 生成器表达式求和 | `sum(w * v for w, v in zip(...))`、`sum(1 for a in agents if ...)` | 加权和 / 计数 |
| 列表拼接 | `[self.confidence] + [o.confidence for o in others]` | 自己放第一个，再接上其他人 |
| `min` 做上限 | `min(self.confidence * 1.05, 1.0)` | 截断到 1.0 |
| 身份比较 `is` | `[o for o in agents if o is not a]` | 按对象身份排除自己（不是按值） |
| 对象引用语义 | `updates.append((a, others))` | 列表里存的是引用，之后对象被修改，引用看到的也是新值——本文件 bug 的根源 |
| 元组解包循环 | `for a, others in updates:` | 每个元素拆成两个变量 |
| f-string 格式 | `f'{a.answer:6.2f}'`、`f"{a.name:>6s}"`、`{agreement_score(agents):4.2f}` | 宽度 6、2 位小数；右对齐字符串 |
| f-string 内嵌 join | `f"{' '.join(f'{a.answer:6.2f}' for a in agents)}"` | f-string 里嵌套生成器与另一个 f-string（注意内外引号不同） |
| `random.seed` | `random.seed(seed)` | 固定随机数序列；本文件没有用到随机数，所以无效果 |
| 未使用的导入 | `import math` | 可删除；lint 工具会报 F401 |
| `if __name__ == "__main__":` | 文件末尾 | 作为脚本运行时才执行 |

---

## 6. 运行结果解读

实际运行（Python 3.13）：

```text
True answer: 42.0

Control (round-0 mean, self-consistency baseline): 43.83
Error vs truth: 1.83

=== Debate 3 agents, 3 rounds (3 rounds) ===
  round         A      B      C    agree    err-vs-truth
    0      38.00  42.50  51.00    0.00      1.83
    1      42.89  44.49  45.34    0.00      2.24      ← 误差变大
    2      44.15  44.56  44.59    0.00      2.43
    3      44.43  44.52  44.50    1.00      2.48      ← 达成"共识"，误差最大

=== Debate 3 agents, 5 rounds (diminishing returns) (5 rounds) ===
    （0–3 轮与上面完全相同：seed 没有作用）
    4      44.49  44.51  44.50    1.00      2.50
    5      44.50  44.50  44.50    1.00      2.50
```

逐项解读：

- **基线 43.83**：`(38 + 42.5 + 51) / 3`，误差 1.83。
- **第 1 轮**：A 从 38 跳到 42.89（向众人靠拢），C 从 51 降到 45.34；但由于顺序更新，B 反而从 42.5 被拉到 44.49——**最接近真值的 agent 被拉偏了**。
- **共识度**：第 3 轮三个答案都在均值 ±0.1 内，`agree = 1.00`；此时误差 2.48，比不辩论还差。这就是讲义练习 3 的答案："共识度 1.0 并不等于正确"。
- **收敛速度**：分歧（最大值 − 最小值）从 13.0 → 2.45 → 0.44 → 0.09 → 0.02 → 0.00，确实是"边际递减"；递减的是分歧，不是误差。
- **对照实验（均为实测）**：

| 设定 | 最终均值 | 误差 |
|------|---------|------|
| 第 0 轮均值（代码基线） | 43.83 | 1.83 |
| 第 0 轮中位数 | 42.50 | 0.50 |
| 代码原样（顺序更新，A→B→C），5 轮 | 44.50 | 2.50 |
| 顺序更新，C→B→A，5 轮 | 40.95 | 1.05 |
| 顺序更新，B→A→C，5 轮 | 43.53 | 1.53 |
| 同步更新（先快照），1 轮后即稳定 | 42.89 | 0.89 |
| "只有轮数"（单 agent 反复 revise，无他人） | 不变（A 38 / B 42.5 / C 51） | 4.0 / 0.5 / 9.0 |

  结论：①同步更新确实比基线好，且一轮就收敛——这与讲义"第一轮交流收益最大"的说法一致；②顺序更新让结论依赖发言顺序；③单 agent"反思"在这个模型里完全不动——对应讲义 "Round count alone ... barely helps"（这里是"完全没用"，因为没有新信息）。

---

## 7. 动手改一改

1. **修复同步更新**：在每轮开始用 `snapshot = [(a.answer, a.confidence) for a in agents]` 拍快照，`revise` 改为接收快照数据。验证第 1 轮后三个答案都等于 42.889，且结果不再依赖 agent 的顺序。
2. **讲义练习 1**：把轮数改为 5、10，打印每轮的"分歧（max − min）"和误差，找出分歧低于 0.01 的轮次。
3. **讲义练习 2：对抗 agent**：加入 D，每轮总是报出"当前均值 + 5"，置信度固定 0.5。观察它是阻止了错误共识，还是把共识整体拉偏？再试"报出离当前均值最远的初始答案"。
4. **讲义练习 3：共识度 vs 正确性**：同时打印 `agreement_score`（`tol` 取 0.1、0.5、1.0）与误差，画出（打印）两条曲线，说明为什么"共识度 1.0"不等于正确。
5. **讲义练习 4：消融实验**：分别实现"只有 agent（第 0 轮直接聚合）"、"只有轮数（单 agent 反复 revise）"、"两者都有"，用中位数和均值两种聚合方式对比误差。思考：在加权平均模型里，"两者都有"为什么无法超过初始答案的凸包？真实 LLM 辩论的收益从哪里来？
6. **让置信度有依据**：把置信度改为"与其他人的平均距离越小越高"，或引入一个随机的"可验证证据"（例如某个 agent 能以 70% 概率得到真值的提示），观察辩论能否把这条证据传播给其他人。

---

## 8. 常见坑

- **相信打印的结论而不看数据**：Takeaways 是写死的，与输出矛盾；评估辩论效果要看误差列，不是看收敛。
- **把"引用列表"当成"快照"**：`others` 存的是对象引用，后续修改会被看到；需要同步语义时必须复制数据。
- **共识 ≠ 正确**：`agree = 1.00` 时误差最大，正是讲义说的 "Can be confidently wrong"。
- **以为设置了种子就有随机性**：`random.seed` 不产生随机数；两场辩论初始条件完全相同。
- **数值任务用均值当"多数"**：均值被离群值 C=51 拉偏；中位数更稳健。
- **权重 = 自信**：最自信的不一定最正确；全体置信度同步上涨只会加速锁定当前共识。
- **轮数口径**：Du et al. 的 R 轮包含初始作答（第 1 轮是独立作答，2..R 轮是辩论）；本代码的 "3 rounds" 是初始作答之外再更新 3 次，共 4 次"发言"。估算成本时要统一口径。
