# 代码讲解 · main.py

> **所属小节**：阶段 16 · 多智能体与集群 · 第 15 节 投票、自洽性与辩论拓扑 ｜ 讲义：[../docs/zh.md](../docs/zh.md) ｜ 测验：[../quiz/quiz.md](../quiz/quiz.md)
>
> **运行方式**：`python3 main.py`（无参数） ｜ **依赖**：仅标准库（`random`、`dataclasses`），无需 API key、无需网络

---

## 1. 这份代码在考察什么

讲义的问题是："跑 N 个 agent 投票/辩论"什么时候有用、什么时候反而更差？它把答案归结为四个结构性选择：拓扑（谁和谁说话）、轮数、异构性、是否有对抗声音。这份代码是一个**蒙特卡洛模拟器**：

1. 每个模拟 agent（`SimAgent`）以概率 `base_accuracy` 答对（`"RIGHT"`），否则给出它固定的错误答案 `error_bias`；
2. 四个函数分别按 star / chain / tree / graph 的信息流组织 N 个 agent，产出最终答案，并累计 token；
3. `bench` 在 N = 3、5、7 和"同质 / 异质"两组配置下各跑 200 次试验，打印准确率、平均 token 与步数。

> 一句话：**用"会犯错的投票者 + 不同的计票流程"来直观感受拓扑、数量和异构性对准确率与成本的影响**。但要带着批判性去读：模拟中的错误其实是**独立**的（没有真正的 monoculture），graph 的辩论轮从不改变结果，tree/star 的平局规则让它们在小 N 时退化为单人，Takeaways 中有三条与实际输出不符。这些"模拟器陷阱"本身就是本节最有价值的教学内容。

---

## 2. 整体结构一览

| 组成部分 | 类型 | 作用 | 对应概念 |
|---------|------|------|---------|
| `SimAgent` | `@dataclass` | 名字、准确率、固定错误答案、每次调用 token 数；`answer()` 抽签 | 会犯错的 agent |
| `RunResult` | `@dataclass` | 一次运行的拓扑、N、最终答案、正确答案、token、步数；`accuracy()` 返回 0/1 | 实验记录 |
| `majority` | 函数 | 计数后取最多（平局取最先出现的） | 多数投票 |
| `run_star` | 函数 | hub 不投票，N − 1 个 worker 多数 | star 拓扑 |
| `run_chain` | 函数 | 依次接力，后者可能替换当前答案 | chain 拓扑 |
| `run_tree` | 函数 | 叶子二分，组内多数，再对两组结果多数 | tree 拓扑 |
| `run_graph` | 函数 | 全员作答，之后每轮少数派以 0.4 概率改投多数 | graph 拓扑 + conformity |
| `make_agents` | 函数 | 生成同质（全 `WRONG-A`、全 0.72）或异质（`WRONG-A/B/C` 轮换、准确率 0.70–0.74）的 agent 列表 | 异构性"旋钮" |
| `bench` | 函数 | 拓扑 × N × 200 次试验的统计表 | 实验 harness |

数据流：`main()` → `bench(同质)` / `bench(异质)` → 每个 (拓扑, N, 试验 t)：`make_agents(n, het, seed=t)` + `random.Random(t*31+7)` → `run_xxx` → `RunResult` → 累加准确率、token、步数 → 打印表格 → 打印 Takeaways。

讲义 Build It 中写的函数签名是 `run_star(agents, hub, question)`、`run_tree(root, children, question)` 等，并承诺报告 `(accuracy, total_tokens, wallclock_simulated)`；实际代码统一为 `run_xxx(agents, correct, rng)`，没有时延模型，只有写死的 `steps`。

---

## 3. 逐段精讲

### 3.1 `SimAgent` 与 `RunResult`

```python
@dataclass
class SimAgent:
    name: str
    base_accuracy: float
    error_bias: str
    tokens_per_call: int = 400

    def answer(self, correct: str, rng: random.Random) -> str:
        return correct if rng.random() < self.base_accuracy else self.error_bias
```

- `rng.random()` 返回 `[0, 1)` 的均匀随机数，小于 `base_accuracy` 就答对——这是一个伯努利试验。
- 每个 agent **每次调用都独立抽签**。讲义所说的 monoculture 是"共享基座模型 → 一起错"，而这里同质组只是"错的时候都错成同一个答案 `WRONG-A`"，错误事件本身仍然独立。这一点决定了后面所有"同质 vs 异质"的结论（见 3.6）。
- 每次调用固定 400 token，token 成本只与调用次数成正比，不随上下文长度增长——所以模拟不出讲义所说的"上下文被同伴输出填满"。

```python
@dataclass
class RunResult:
    ...
    def accuracy(self) -> int:
        return 1 if self.final_answer == self.correct else 0
```

- 单次运行的"准确率"就是 0 或 1，`bench` 把 200 次加起来再除以 200 得到估计值。

### 3.2 `majority`：平局取先出现者

```python
def majority(items: list[str]) -> str:
    counts: dict[str, int] = {}
    for it in items:
        counts[it] = counts.get(it, 0) + 1
    return max(counts, key=counts.get)
```

- 字典保持插入顺序，`max` 在平局时返回**最先插入**的键。这个看似无害的细节，在偶数个投票者时会让结果系统性地偏向"列表里第一个人"，下面 star 和 tree 的退化都源于此。

### 3.3 `run_star`：hub 只花钱不投票

```python
def run_star(agents, correct, rng):
    hub = agents[0]
    workers = agents[1:]
    answers = [w.answer(correct, rng) for w in workers]
    tokens = sum(w.tokens_per_call for w in workers) + hub.tokens_per_call
    final = majority(answers) if answers else hub.answer(correct, rng)
    return RunResult("star", len(agents), final, correct, tokens, steps=2)
```

- hub 的 token 被计入，但它的答案只在"没有 worker"时才用到；实际只有 N − 1 个 worker 投票。
- N = 3 时只有 2 个 worker，不一致就取 `workers[0]`，等价于单人；N = 5、7 分别是 4、6 个 worker（偶数），平局又倒向第一个人。20,000 次试验实测同质组 star = 0.724 / 0.810 / 0.865，恰好是"1 人 / 3 人多数 / 5 人多数"的准确率。
- 讲义说 star 中"Hub filters and consolidates"，代码里 hub 并没有任何过滤逻辑。

### 3.4 `run_chain`：不看对错的接力

```python
def run_chain(agents, correct, rng):
    current = agents[0].answer(correct, rng)
    tokens = agents[0].tokens_per_call
    for a in agents[1:]:
        proposal = a.answer(correct, rng)
        current = proposal if proposal != current and rng.random() < a.base_accuracy else current
        tokens += a.tokens_per_call
    return RunResult("chain", len(agents), current, correct, tokens, steps=len(agents))
```

- 每个后继者独立作答；如果与当前答案不同，就以 `base_accuracy` 的概率**替换**——不管提案是否正确。`base_accuracy` 在这里被同时当作"答对概率"和"说服力"，但说服力与提案正误无关。
- 结果：同质组中"对 → 错"的转移概率 `0.28 × 0.72 ≈ 0.20`，"错 → 对"为 `0.72 × 0.72 ≈ 0.52`，这是一个两状态马尔可夫链，平稳分布中正确率 `0.52 / 0.72 = 0.72`——**正好等于单个 agent**。20,000 次试验实测 0.720 / 0.721 / 0.724，链条长度没有任何影响。
- 本次 200 次试验看到的"N 越大越差"（0.75 → 0.78 → 0.71）只是噪声。Takeaway"chain underperforms on monoculture because one bias propagates along the chain"并没有被这个模型支持：异质组 chain 一样差（0.76 → 0.73 → 0.69）。
- 真实的分步精炼链条中，后继者看得到前驱的推理并在其基础上修改，本模拟没有这种"精炼"语义。

### 3.5 `run_tree`：两层平局

```python
def run_tree(agents, correct, rng):
    root = agents[0]
    leaves = agents[1:]
    if len(leaves) <= 1:
        return run_star(agents, correct, rng)
    mid = len(leaves) // 2
    left_answers = [a.answer(correct, rng) for a in leaves[:mid]]
    right_answers = [a.answer(correct, rng) for a in leaves[mid:]]
    ...
    final = majority([left_consensus, right_consensus])
```

- root 不投票，只计 token。顶层永远只有两票（左组、右组），不一致时平局取左组。
- N = 3：左右各 1 个叶子 → 结果 = `leaves[0]`。N = 5：左右各 2 个叶子，组内 2 票平局取第一个 → 左组结果 = `leaves[0]` → 最终 = `leaves[0]`。两种情况都等于单人（实测 0.724）。
- N = 7：左右各 3 个叶子，组内有真正的多数，但顶层平局仍取左组，所以最终 = 左边 3 人的多数（实测 0.809，正好是 3 人多数准确率），右边 3 个叶子**完全不影响结果**，只是花 token。
- 修复：让 root 在两组不一致时亲自作答/裁决，或直接对所有叶子做平铺多数（实测平铺后同质组 N = 5、7 为 0.810、0.865）。

### 3.6 `run_graph`：从不改变结果的"辩论"

```python
def run_graph(agents, correct, rng, rounds: int = 2):
    positions = [a.answer(correct, rng) for a in agents]
    tokens = sum(a.tokens_per_call for a in agents)
    for _ in range(rounds - 1):
        majority_now = majority(positions)
        new_positions = []
        for pos, ag in zip(positions, agents):
            if pos != majority_now and rng.random() < 0.4:
                new_positions.append(majority_now)
            else:
                new_positions.append(pos)
            tokens += ag.tokens_per_call
        positions = new_positions
    return RunResult("graph", len(agents), majority(positions), correct, tokens, steps=rounds * 2)
```

- 第一轮全部 N 个 agent 独立作答；之后每轮，少数派以 0.4 的概率"跟风"改投当前多数（模拟 AgentVerse 的 conformity）。
- 关键性质：**只有少数派会改，且只会改成多数**，所以多数只增不减，最终答案恒等于第一轮的多数。用同一随机种子对照 30,000 次，`run_graph` 与"初始答案的多数"不一致的次数为 0。辩论轮只是增加 `N × 400` 个 token。
- 因此 graph 的准确率就是"N 个独立投票者的多数"：同质组二项分布理论值 0.809 / 0.862 / 0.898，实测 0.809 / 0.866 / 0.899。graph 胜过 star，只是因为 graph 让全部 N 人投票，star 只有 N − 1 人（还带偶数平局）。这不能证明"任意对任意的批评"更好。
- 讲义说 conformity "is why debate-until-agreement rewards bullies"——本模拟中 conformity 永远倒向多数，既模拟不出"错误多数通过跟风压倒正确少数"的危害（因为最终结果不变），也模拟不出"被正确论证说服"的辩论收益。
- `steps=rounds * 2` 是写死的常数，与 N 无关。

### 3.7 `make_agents`：异构性旋钮

```python
def make_agents(n, heterogeneous, seed):
    rng = random.Random(seed)
    if heterogeneous:
        biases = ["WRONG-A", "WRONG-B", "WRONG-C"]
        accuracies = [0.72, 0.70, 0.74, 0.71, 0.73, 0.70, 0.72]
    else:
        biases = ["WRONG-A"]
        accuracies = [0.72] * 7
    return [SimAgent(f"agent-{i}", accuracies[i % len(accuracies)], biases[i % len(biases)])
            for i in range(n)]
```

- `rng = random.Random(seed)` 创建后**从未使用**，`seed` 参数实际上没有作用。
- 两组的差别只有两点：错误标签是否分散、准确率列表略有不同。异质组平均准确率与同质组相近（0.70–0.74），但 `agent-1` 只有 0.70——这让异质组 star N=3（结果 ≈ `agent-1`）和 tree N=3/5（结果 ≈ `agent-1`）反而略差。
- 异质组整体更好的机制是**投票分散（vote splitting）**：错误票分投 A/B/C，正确答案只需相对多数即可胜出。这是一个真实的效应，但它与讲义所说的"uncorrelated errors"不是一回事——本模拟中两组的错误都是独立的。

### 3.8 `bench`：实验 harness

```python
            for t in range(trials):
                agents = make_agents(n, heterogeneous, seed=t)
                rng = random.Random(t * 31 + 7)
                ...
            print(f"{topology:10s} {n:>3d} {acc_sum/trials:>8.2f} {tok_sum//trials:>12d} {step_sum//trials:>6d}")
```

- 每次试验用确定的种子 `t * 31 + 7`，所以整张表可复现；同质组与异质组用**相同的随机数序列**（common random numbers），差异只来自配置。这本是做对照实验的好做法。
- 200 次试验的标准误约 `sqrt(0.72 × 0.28 / 200) ≈ 0.032`，表中很多 ±0.01–0.03 的差异不显著。
- `if/elif` 分派可以改成字典 `{"star": run_star, ...}`；`tok_sum // trials` 用整除，所以 token 列是整数。

---

## 4. 为什么这样设计（设计取舍总结）

| 设计选择 | 原因 | 代价 / 生产中会怎么做 |
|---------|------|---------------------|
| 用伯努利抽签代替真实 LLM | 秒级跑完上千次试验，零成本 | 错误彼此独立，模拟不出 monoculture；应加共享隐变量（相关系数 rho） |
| 同质/异质只改错误标签与准确率 | 一个参数就能切换 | 异质优势来自"投票分散"而非"错误不相关"，与讲义机制不同 |
| `majority` 平局取先出现者 | 实现最短 | 偶数票时偏向第一个人，导致 star N=3、tree N=3/5 退化为单人；应显式随机或升级 judge |
| hub / root 不投票 | 模拟"协调者只汇总" | 浪费一个 agent 的 token，让 star/tree 与 graph 的投票人数不对等 |
| chain 以 `base_accuracy` 概率替换 | 想模拟"更准的 agent 更有说服力" | 替换与提案正误无关，链条收敛到单人准确率 |
| graph 只建模"少数跟风多数" | 简单模拟 conformity | 结果恒等于初始多数，辩论轮无作用；应建模"被正确论证说服"和"被强势错误者带偏" |
| 固定 400 token/次、写死 steps | 易算 | token 线性、无时延模型，coordination tax 无法出现 |
| 每格 200 次试验 | 运行快 | 标准误约 0.03，小差异不显著；应 ≥ 10,000 次或报置信区间 |
| 同一组种子用于两组配置 | 对照公平 | — （这是正确做法） |

---

## 5. Python 语法小课堂

| 语法 | 本文件中的例子 | 说明 |
|------|--------------|------|
| `@dataclass` 带默认字段 | `tokens_per_call: int = 400` | 有默认值的字段必须放在无默认值字段之后 |
| 数据类中的方法 | `def answer(self, correct, rng)`、`def accuracy(self)` | 数据类也可以带行为 |
| 独立随机数生成器 | `random.Random(t * 31 + 7)` | 每个实例有自己的状态，不影响全局 `random`；种子相同则序列相同 |
| `rng.random()` | `rng.random() < self.base_accuracy` | `[0, 1)` 均匀分布，用于伯努利抽签 |
| 条件表达式 | `correct if rng.random() < p else self.error_bias` | 一行 if/else |
| 切片 | `agents[1:]`、`leaves[:mid]`、`leaves[mid:]` | 取子列表；`mid = len(leaves) // 2` 整除 |
| 列表推导式 | `[w.answer(correct, rng) for w in workers]` | 每个 worker 作答 |
| 生成器表达式求和 | `sum(w.tokens_per_call for w in workers)` | 不建中间列表 |
| `zip` 并行遍历 | `for pos, ag in zip(positions, agents)` | 同时取两个列表的对应元素 |
| `_` 占位变量 | `for _ in range(rounds - 1)` | 不使用循环变量 |
| 取模循环取值 | `accuracies[i % len(accuracies)]`、`biases[i % len(biases)]` | 列表不够长时循环使用 |
| f-string 宽度与对齐 | `{topology:10s}`、`{n:>3d}`、`{acc_sum/trials:>8.2f}`、`{tok_sum//trials:>12d}` | 左对齐、右对齐、小数位 |
| 元组字面量遍历 | `for topology in ("star", "chain", "tree", "graph")` | 遍历固定集合 |
| 关键字参数 | `bench(correct="RIGHT", trials=200, heterogeneous=False)` | 调用时显式写出参数名 |
| `if __name__ == "__main__":` | 文件末尾 | 直接运行时才执行 `main()` |

---

## 6. 运行结果解读

实际运行（Python 3.13，`cd code && python3 main.py`，约 1 秒，结果确定）：

```text
BENCHMARK — HOMOGENEOUS (monoculture)
topology     N      acc   avg_tokens  steps
star         3     0.76         1200      2
star         5     0.83         2000      2
star         7     0.90         2800      2
chain        3     0.75         1200      3
chain        5     0.78         2000      5
chain        7     0.71         2800      7
tree         3     0.76         1200      3
tree         5     0.76         2000      3
tree         7     0.82         2800      3
graph        3     0.82         2400      4
graph        5     0.91         4000      4
graph        7     0.92         5600      4

BENCHMARK — HETEROGENEOUS
star         3     0.75         1200      2
star         5     0.94         2000      2
star         7     0.98         2800      2
chain        3     0.76         1200      3
chain        5     0.73         2000      5
chain        7     0.69         2800      7
tree         3     0.75         1200      3
tree         5     0.75         2000      3
tree         7     0.89         2800      3
graph        3     0.89         2400      4
graph        5     0.95         4000      4
graph        7     0.99         5600      4
```

为了区分信号和噪声，我们另外用 20,000 次试验重跑了同一套函数：

| 拓扑 | 同质 N=3/5/7 | 异质 N=3/5/7 | 解释 |
|------|-------------|-------------|------|
| star | 0.724 / 0.810 / 0.865 | 0.705 / 0.903 / 0.960 | 等于 1 / 3 / 5 人多数（hub 不投票 + 偶数平局） |
| chain | 0.720 / 0.721 / 0.724 | 0.734 / 0.730 / 0.717 | 恒等于单人准确率，长度无影响 |
| tree | 0.724 / 0.724 / 0.809 | 0.705 / 0.705 / 0.858 | N=3、5 等于第一个叶子；N=7 等于左边 3 人多数 |
| graph | 0.809 / 0.866 / 0.899 | 0.866 / 0.933 / 0.974 | 等于全部 N 人的一次独立投票 |

逐项解读：

- **token 列**：star/chain/tree 都是 `N × 400`；graph 两轮是 `2N × 400`。所以 graph N=7 是 star N=3 的 `5600 / 1200 ≈ 4.7` 倍，不是 Takeaway 说的 "~7x"。
- **coordination tax 没有出现**：graph 准确率随 N 单调上升，token 线性增长，看不到"成本比质量增长更快"的拐点。讲义练习 1 让你画这条曲线找拐点——在本模型中找不到，因为模型里没有任何随 N 恶化的机制。
- **"heterogeneous ensembles outperform homogeneous at every topology/N"不成立**：本次输出中 star N=3、chain N=5/7、tree N=3/5 异质组都更低；20,000 次试验下 star N=3、tree N=3/5 仍然更低（0.705 vs 0.724）。
- **"chain underperforms on monoculture because one bias propagates"不成立**：chain 在两组都停在约 0.72，原因是更新规则不看对错，而非偏差传播。
- **异质组 star/graph 大 N 时很高（0.96–0.98）**：这是错误票分散的效果，不是错误不相关。若要模拟真正的 monoculture，需要让同质 agent 共享一次抽签（测验 Q11：rho = 0.5 时，N 从 3 加到 15，准确率始终在 0.75–0.77 附近）。
- **200 次试验的噪声**：标准误约 0.03，例如同质 chain 的 0.75 / 0.78 / 0.71 全是噪声。

---

## 7. 动手改一改

1. **增加试验次数**：把 `trials` 改成 20,000，重新看表格，确认哪些"差异"消失；再为每格打印 95% 置信区间 `acc ± 1.96 × sqrt(acc(1−acc)/trials)`。
2. **修平局**：让 star 的 hub 也投票、让 tree 的 root 在两组不一致时亲自裁决，或对全部叶子平铺多数；比较修复前后 star/tree 与 graph 的差距还剩多少。
3. **真正的 monoculture**：给 `bench` 增加参数 `rho`，同质组每次试验先抽一个共享结果，每个 agent 以 `rho` 的概率采用它；画出 `rho = 0, 0.5, 0.8` 下 graph 准确率 vs N 的曲线，复现"heterogeneity beats numerosity"。
4. **有意义的辩论**：改写 `run_graph`——少数派**若持有正确答案**以概率 `q` 说服一个多数派成员（论证收益），同时每轮以概率 `c` 让少数派向多数妥协（conformity）；扫描 `rounds = 1..5`，观察讲义"有界轮数"的必要性。再加入一个不投票、只给最终共识打分的 judge（讲义练习 3）。
5. **建模 coordination tax**：让每个 agent 的准确率随 N 下降（例如 `p_eff = p − 0.01 × (N − 4)²`，N > 4 时生效），并让 graph 的 token 随 N² 增长（每个 agent 要读其他所有人的输出）；画出准确率与 token 曲线，找到拐点。
6. **A-HMAD（讲义练习 2）**：构造三个偏差各不相同、错误相关性低的 agent，与"三个同偏差、高相关"的对照组比较，在阶段 16 · 14 的 monoculture 场景（3 票错误多数）下测准确率。

---

## 8. 常见坑

- **把"错得一样"当成"相关错误"**：独立抽签 + 相同错误标签不是 monoculture；相关性要体现在"同时出错"的概率上。
- **平局规则偷偷决定结果**：`max(dict, key=...)` 平局取先插入者，偶数投票者时会系统性偏向列表中的第一个人。
- **协调者不投票却计成本**：star/tree 的 hub/root 只花 token，使拓扑对比变成"投票人数对比"。
- **以为辩论轮在起作用**：只让少数派向多数跟风的更新规则，永远不会改变最终多数。
- **样本量太小就下结论**：200 次试验 ±0.03 的噪声足以制造"chain 越长越差""异质处处更好"之类的假结论。
- **把模拟器结论当成论文结论**：讲义中 MultiAgentBench 的"graph 研究类最好、star 事实类最好、4-agent 之后 coordination tax"来自真实基准，本模拟只有一种任务、没有时延，无法验证这些结论。
- **未使用的随机数生成器**：`make_agents` 里的 `rng` 从未被使用，读代码时不要误以为 agent 配置是随机的。
