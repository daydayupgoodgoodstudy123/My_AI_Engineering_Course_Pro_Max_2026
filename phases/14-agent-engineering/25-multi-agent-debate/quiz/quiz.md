# 测验 · 多 Agent 辩论与协作（Multi-Agent Debate and Collaboration）

> **阶段 14 · Agent 工程 · 第 25 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义机翻有漏译（例如稀疏拓扑"能以更低 token 成本达到相近准确率"一句、"更多 agent 和轮数在难题上提升准确率"一句均缺失），请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 辩论协议（Society of Minds） | 讲义：Du et al.（ICML 2024）——N 个模型实例独立作答，R 轮中互读互评、更新答案，最后返回收敛答案 |
| 2 | 原论文设置与结论 | 讲义：因成本原因原实验用 N=3、R=2；在难题（MMLU、GSM8K、国际象棋走法合法性、人物传记生成）上，agent 越多、轮数越多准确率越高；跨模型组合（ChatGPT + Bard）优于单模型辩论 |
| 3 | 与 Self-Refine / CRITIC 的区别 | Self-Refine 是单模型自我批评（易群体思维）；CRITIC 用外部工具做依据（不一定有工具）；辩论是第三种：多实例、交叉批评、在分歧中收敛 |
| 4 | 稀疏拓扑 | 讲义引 arXiv:2406.11776：全连接（full mesh）不总是最优，星形/环形/hub-and-spoke 等稀疏拓扑能以更低 token 成本达到相近准确率 |
| 5 | 成本计算 | 全连接每轮每人读 N−1 个同伴：总读取次数 `N(N−1)R`（N=5、R=3 为 60）；星形中只有 spoke 读 hub 时为 `(N−1)R`（12），若 hub 也读所有 spoke 则为 `2(N−1)R`（24，本节代码的算法） |
| 6 | 何时有用 | 事实性（交叉核对减少幻觉）、规则遵循（一个模型漏掉规则，别人能抓住）、开放式推理 |
| 7 | 何时有害 | 延迟敏感（N × R 串行轮次）、成本敏感（每题 N × R 倍 token）、简单事实查询（一次查询比五方辩论便宜） |
| 8 | 三种失败模式 | 收敛塌缩（大家一起收敛到第一个错误答案，用强制分歧轮缓解）；hub 失效（星形中坏 hub 带坏所有人，轮换或多 hub）；prompt 同质化（相同 prompt 产生相同答案，用不同 prompt/模型） |
| 9 | 收敛规则 | 多数票、置信度加权、超级多数 + 兜底；skill 文件："返回第 0 号辩手的第 R 轮答案不叫收敛" |
| 10 | 2026 年的落地形态 | 讲义：Anthropic orchestrator-workers（带综合步骤的变体）、LangGraph supervisor（把辩论做成节点）、OpenAI Agents SDK（handoff 往返批评）、多 agent 评估 |

### 核心技能（能动手做到）

- [ ] 写出辩论的轮次循环，并在全连接与星形拓扑间切换
- [ ] 手算任意 N、R、拓扑下的"批评读取次数"，指出讲义与代码计数口径的差别
- [ ] 手动推演本节 `drift` 更新规则，预测辩论结果（包括不收敛、随轮数奇偶翻转的情况）
- [ ] 识别演示设计的问题：所有辩手一开始就答对了，辩论没有发挥任何作用
- [ ] 实现"带自我投票、平票保持原答案"的辩手、提前停止与"无共识"判定
- [ ] 判断一个产品场景是否适合用辩论，并说明替代方案

---

## 二、基础自测（选择题）

**Q1.** 关于 Du et al.（Society of Minds）的辩论协议，描述正确的是：

- A. 一个模型先回答，再由同一个模型反复自我批评
- B. 多个模型分工：一个检索、一个写作、一个审校
- C. N 个模型实例先独立作答，随后 R 轮中每个实例阅读他人的答案并批评、更新自己的答案，最后返回收敛的答案
- D. 多个模型各答一次，直接取多数票，没有交互轮次

**Q2.** 讲义说原论文实验采用的设置及原因是：

- A. N=3、R=2，因为成本
- B. N=10、R=10，因为准确率随规模饱和
- C. N=2、R=1，因为模型上下文长度有限
- D. N=5、R=3，因为这是最优配置

**Q3.** 全连接（full mesh）辩论，N=5、R=3，每个辩手每轮阅读所有同伴的答案。总共的"批评读取次数"是：

- A. 15
- B. 12
- C. 24
- D. 60

**Q4.** 星形拓扑（一个 hub + 若干 spoke）最典型的风险及缓解办法是：

- A. token 成本比全连接更高；改用全连接
- B. hub 出错会把错误传给所有 spoke；轮换 hub 或使用多个 hub
- C. spoke 之间信息过多导致上下文溢出；减少轮数
- D. 无法得出多数票；改为加权平均

**Q5.** 运行本节 `main.py`，三道题、两种拓扑的 `converged_round` 都是 1。根本原因是：

- A. 三个辩手的 `corrections` 让他们在第 0 轮（独立作答）时就给出了相同的正确答案，辩论根本没有分歧可以消解
- B. 辩论算法非常高效，一轮就能纠正所有错误
- C. 星形拓扑的 hub 恰好是正确的
- D. `rounds=3` 太少，看不出差别

**Q6.** 讲义 Build It 部分说输出会显示"sparse matches full mesh on 2/3 questions at lower cost"。实际运行结果是：

- A. 两种拓扑都只答对 2/3
- B. 全连接 3/3、星形 2/3
- C. 两种拓扑都答对 3/3，星形读取次数 12、全连接 18
- D. 两种拓扑都答错了国际象棋题

**Q7.** 按讲义和 skill 文件，下列哪个场景**最不应该**使用多 agent 辩论？

- A. 需要严格遵守复杂规则的判定任务，允许几秒延迟
- B. 离线批量核查一批事实性陈述，追求准确率
- C. 困难的数学推理题，用于生成评测数据
- D. 实时语音助手回答"葡萄牙的首都是哪里"，延迟预算小于 1 秒

**Q8.** 所有辩手使用同一个模型、同一个 prompt，最可能出现的问题与对策是：

- A. token 成本下降；无需处理
- B. prompt 同质化，大家给出相同答案、形成群体思维；使用不同的 prompt 和/或不同的模型
- C. hub 失效；增加轮数
- D. 收敛太慢；改用全连接

---

## 三、动手 / 代码题

**Q9.** 本节辩手的更新规则：

```python
def _make_debater(name, bias, corrections):
    def drift(question, peer_answers):
        current = corrections.get(question, bias)
        if peer_answers:
            common = Counter(peer_answers).most_common(1)[0][0]
            if common != current and common != bias:
                return common
        return current
    return Debater(name=name, drift=drift)
```

用三个辩手（顺序很重要）做全连接辩论，题目 `capital_of_portugal`：

```python
Q = "capital_of_portugal"
ds = [_make_debater("gamma", "Porto", {}),
      _make_debater("alpha", "Lisbon", {}),
      _make_debater("beta", "Madrid", {Q: "Lisbon"})]
run_debate(ds, Q, rounds=3, topology="full_mesh")
```

1. 写出第 0～3 轮每个辩手的答案和 `run_debate` 的返回值。
2. 把 `rounds` 改成 2、4，结果分别是什么？为什么结果会随轮数奇偶翻转？
3. 指出 `drift` 规则中导致这种现象的三个设计问题。

**Q10.**（成本口径）
1. 讲义说"Star N=5, R=3 ... spokes read only the hub = 12 critique ops"。用本节 `run_debate(..., topology="sparse_star")` 跑 N=5、R=3，`ops` 是多少？为什么不同？
2. 写出两种拓扑在本节代码口径下的 ops 公式，并指出 skill 文件中"Full mesh ... Debate ops scale O(N*R)"的问题。
3. 调用 `run_debate(..., topology="ring")` 会发生什么？

**Q11.** 改写辩手，使其：①记住自己上一轮的答案；②把自己的答案也算进投票；③只有当某个答案的票数**严格多于**自己当前答案时才改变主意（平票保持原答案）。用 Q9 的辩手配置验证结果，并说明这对应讲义哪条失败模式的缓解。

**Q12.**（收敛判定与演示设计）
1. `run_debate` 只在第 1 轮之后才检查是否收敛。如果第 0 轮大家就一致了，会白白花掉多少读取次数？写一个支持"第 0 轮即一致则直接返回""提前停止""未达到过半数则返回 `NO_CONSENSUS`""未知拓扑报错"的 `run_debate_early`。
2. 本节演示让三道题都在第 0 轮就一致。请重新设计演示数据，使"辩论能纠错""辩论会收敛到错误答案（收敛塌缩/hub 失效）"两种情况都能被看到。

---

## 四、面试高频题

**Q13.**（基础必考）什么是多 agent 辩论？它与 Self-Refine、CRITIC、简单的多数投票（self-consistency）有什么区别？

**Q14.**（原理深挖）为什么辩论能提升事实性和推理？它在什么情况下反而会让答案变差？

**Q15.**（工程实践）你要上线一个辩论式的"合同条款风险审查"功能。请给出 N、R、拓扑、收敛规则和成本控制的设计。

**Q16.**（场景设计）全连接与稀疏拓扑如何选择？如果用星形拓扑，怎么防止 hub 带偏所有人？

**Q17.**（追问型）你做的辩论系统在评测集上准确率几乎没比单模型高，但成本是 9 倍。你会怎么排查和改进？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义："N model instances independently propose answers to the same question. Over R rounds, each model reads the others' proposals and critiques them. Models update their answers based on the critiques. After R rounds, return the convergent answer." A 是 Self-Refine；B 是角色分工（orchestrator-workers / crew）；D 是没有交互的多数投票（self-consistency 式），缺少"互读互评、更新"这一核心。

### Q2 — 答案：A

讲义："Original experiments used N=3, R=2 due to cost." 并补充：在难题上 agent 越多、轮数越多准确率越高。B、C、D 都不是讲义说法；D 的 N=5、R=3 是讲义用来演示成本计算的例子（也是练习 5 要移植到的规模）。

### Q3 — 答案：D

每轮每个辩手读 `N − 1 = 4` 个同伴，`5 × 4 × 3 = 60`（讲义："5 × 3 = 15 proposals, each reading 4 peers = 60 critique ops"）。用本节代码实测 N=5、R=3 的全连接 `ops` 也是 60。A（15）是提案数；B（12）是讲义给星形的数（只计 spoke 读 hub）；C（24）是本节代码的星形计数（hub 也读 spoke）。

### Q4 — 答案：B

讲义："Hub failure. In a star topology, a bad hub corrupts everyone. Rotate or use multiple hubs." A 说反了，星形更便宜；C、D 不是讲义提到的风险。Q9 中把答错的 gamma 放在第一个（即 hub）时，星形拓扑同样得出错误答案。

### Q5 — 答案：A

三道题里，alpha 的 bias 就是 "Lisbon"，另外两题有 corrections；beta、gamma 三道题都有 corrections。于是第 0 轮 `drift(question, [])` 时三人答案已完全相同且正确。`run_debate` 只在第 1 轮后检查一致性，所以记为 1。三轮辩论（全连接 18 次读取、星形 12 次）都是**白花的成本**——这个演示没有展示任何"纠错"过程。B 是对输出的误读；C 与此无关（大家本来就一致）；D 错，轮数再多结果也一样。

### Q6 — 答案：C

实际输出六行全部 `CORRECT`，全连接 `ops=18`、星形 `ops=12`。讲义"2/3"的说法与代码不符——而且如 Q5 所述，两种拓扑之所以都对，是因为根本没有分歧。A、B、D 都与实际输出不符。

### Q7 — 答案：D

skill 文件拒绝规则："If the product is latency-sensitive (<1s budget), refuse debate"；"If the question class is simple factual lookup (capital, date, definition), refuse debate. Lookup + CRITIC is cheaper." D 同时命中两条。讲义"When debate hurts"也列出了延迟敏感与简单事实查询。A（规则遵循）、B（事实核查、离线）、C（困难推理）都是讲义"When debate helps"的场景。

### Q8 — 答案：B

讲义："Prompt homogenization. All agents use the same prompt; they produce the same answers. Use diverse prompts and/or models." skill 文件更把"相同 prompt 且相同模型"列为硬性拒绝（"Guaranteed groupthink"）。讲义还提到跨模型组合（ChatGPT + Bard）优于单模型辩论。A 忽视了问题；C、D 答非所问。

### Q9 — 参考答案

1. 逐轮推演（已运行验证；peers 的顺序按辩手列表顺序）：

| 轮次 | gamma | alpha | beta |
|------|-------|-------|------|
| 0 | Porto | Lisbon | Lisbon |
| 1 | Lisbon | **Porto** | **Porto** |
| 2 | Porto | Lisbon | Lisbon |
| 3 | Lisbon | Porto | Porto |

   - 第 1 轮 gamma：同伴 `[Lisbon, Lisbon]`，多数 Lisbon ≠ 当前 Porto 且 ≠ bias Porto → 改为 Lisbon。
   - 第 1 轮 alpha：同伴 `[Porto(gamma), Lisbon(beta)]`，`Counter.most_common` 平票时返回**先出现**的 Porto；Porto ≠ 当前 Lisbon 且 ≠ bias Lisbon → 改为 Porto！
   - 第 1 轮 beta：同伴 `[Porto, Lisbon]` → 同样平票取 Porto，≠ 当前 Lisbon、≠ bias Madrid → 改为 Porto。
   - 第 2 轮每人看到的同伴答案又反过来，于是又翻回去……
   - 返回值 `('Porto', -1, 18)`：最后一轮多数是 Porto（**错误**），从未收敛，读取 18 次。星形拓扑结果相同：`('Porto', -1, 12)`。
2. `rounds=2` → `('Lisbon', -1, 12)`（正确）；`rounds=4` → `('Lisbon', -1, 24)`；`rounds=1、3、5` → Porto。答案在两个状态之间来回振荡，最终结果只取决于**在哪一轮停下**。最初两个辩手是对的，辩论反而让系统在奇数轮时得出错误答案。
3. 三个设计问题：
   - **无记忆**：`current = corrections.get(question, bias)` 每轮都从固定观点重新算起，不考虑自己上一轮的答案，也不把自己算进投票——每个人都只是"复制同伴的多数"；
   - **平票处理随意**：`Counter.most_common` 平票时按插入顺序取第一个，结果由辩手的排列顺序决定，而不是由证据决定；
   - **"反偏见"规则导致盲从**：只要同伴多数不等于自己的 bias 就跟随，没有任何"被说服"的门槛（如证据、置信度、严格多数）。
   这正是讲义"Convergence collapse"的一种形态：辩论没有收敛到正确答案，反而被顺序和平票规则带偏。

### Q10 — 参考答案

1. 实测 N=5、R=3 的星形 `ops = 24`。本节代码的 `sparse_star_round` 中 hub 每轮读取全部 `N − 1` 个 spoke（`ops += len(spoke_names)`），每个 spoke 再读 hub 一次，每轮 `2(N − 1) = 8`，×3 = 24。讲义的 12 只计算了"spoke 读 hub"（`(N − 1) × R = 4 × 3`），没有计 hub 读 spoke。两种口径都可以，但必须说清楚；按本节代码口径，星形相对全连接的节省是 `24 / 60 = 40%`，而不是讲义暗示的 `12 / 60 = 20%`。
2. 本节代码口径：

| 拓扑 | 每轮读取次数 | 总读取次数 | 复杂度 |
|------|-------------|-----------|-------|
| 全连接 | `N(N − 1)` | `N(N − 1)R` | O(N²R) |
| 星形 | `2(N − 1)` | `2(N − 1)R` | O(NR) |

   验证：N=3、R=3 时全连接 18、星形 12（与 `main.py` 输出一致）；N=5 时 60 与 24。skill 文件写"Full mesh with N >= 6 without checking cost. Debate ops scale O(N*R)"——全连接的读取次数其实是 **O(N²R)**，只有提案数是 O(NR)。而且每次"读取"的 token 成本还会随答案变长而增加，真实 token 成本增长更快。
3. `run_debate` 中 `if topology == "full_mesh": ... else: sparse_star_round(...)`——任何不是 `"full_mesh"` 的字符串（包括 `"ring"`、拼写错误）都会**静默地**按星形运行（实测 N=5 时 `ops=24`），不会报错。应显式校验拓扑名（见 Q12 的实现）。

### Q11 — 参考答案

```python
def make_stateful_debater(name, bias, corrections):
    state = {}                                          # 每个问题记住自己的当前答案
    def drift(question, peer_answers):
        current = state.get(question, corrections.get(question, bias))
        if peer_answers:
            votes = Counter(peer_answers + [current])   # 自己也投一票
            top, n = votes.most_common(1)[0]
            if n > votes[current]:                      # 严格多于自己才改；平票保持
                current = top
        state[question] = current
        return current
    return Debater(name=name, drift=drift)
```

用 Q9 的配置（gamma=Porto 排第一，alpha=Lisbon，beta 修正为 Lisbon）实测：全连接 `('Lisbon', 1, 18)`、星形 `('Lisbon', 1, 12)`——第 1 轮 gamma 看到两票 Lisbon 被说服，alpha、beta 平票时坚持 Lisbon，一轮收敛到正确答案。对"三人各执一词（Lisbon/Madrid/Porto）"的配置，结果是三人都坚持己见、永不收敛，最终多数票只能靠平票规则——这说明**没有新证据时，辩论无法凭空产生正确答案**。

对应讲义的失败模式：
- "Convergence collapse"：要求严格多数才改主意、平票保持原答案，避免被排列顺序或少数意见带偏；
- 更进一步应引入讲义练习 2 的**置信度加权**，以及让批评附带理由/证据（真实 LLM 辩论中，辩手看到的是同伴的推理过程，而不仅是一个答案标签）。
注意：`state` 是闭包里的字典，同一个辩手对象在多次 `run_debate` 之间会保留状态，每次实验应重新创建辩手。

### Q12 — 参考答案

1. 第 0 轮已一致时，原代码仍跑满 R 轮：N=3、R=3 时全连接白花 18 次读取、星形 12 次；三道题共 90 次读取都是浪费。参考实现（已运行验证）：

```python
def run_debate_early(debaters, question, rounds, topology):
    if topology not in ("full_mesh", "sparse_star"):
        raise ValueError(f"unknown topology {topology!r}")
    prior = {d.name: d.drift(question, []) for d in debaters}
    if len(set(prior.values())) == 1:                    # 第 0 轮已一致
        return next(iter(prior.values())), 0, 0
    total_ops = 0
    hub, spokes = debaters[0], debaters[1:]
    for r in range(rounds):
        if topology == "full_mesh":
            prior, ops = full_mesh_round(debaters, question, prior)
        else:
            prior, ops = sparse_star_round(hub, spokes, question, prior)
        total_ops += ops
        if len(set(prior.values())) == 1:                # 提前停止
            return next(iter(prior.values())), r + 1, total_ops
    top, n = Counter(prior.values()).most_common(1)[0]
    return (top if n > len(debaters) / 2 else "NO_CONSENSUS"), -1, total_ops
```

   实测：原演示三道题都返回 `(答案, 0, 0)`；"两对一错"的配置（alpha=Lisbon、beta 修正为 Lisbon、gamma=Porto）全连接 `('Lisbon', 1, 6)`、星形 `('Lisbon', 1, 4)`；`topology="ring"` 抛出 `ValueError: unknown topology 'ring'`。
   需要说明的是：讲义的失败模式提醒"第 0 轮就一致"也可能是**同质化导致的一致错误**。生产中第 0 轮一致可以提前返回以省成本，但前提是辩手足够多样（不同 prompt/模型）；skill 文件甚至规定：若评测集上第 1 轮后从未出现分歧，就拒绝使用该协议。

2. 重新设计演示（每种情况都已用代码验证）：

| 场景 | 配置（`capital_of_portugal`） | 结果 | 说明 |
|------|------------------------------|------|------|
| 辩论纠错 | alpha=Lisbon、beta 修正为 Lisbon、gamma=Porto | 1 轮收敛到 Lisbon | 多数正确时少数被纠正 |
| 振荡 / 收敛失败 | alpha=Lisbon、beta=Madrid、gamma=Porto | 不收敛，R=3 时多数恰好为 Lisbon | 三方各执一词，原规则来回摇摆 |
| hub 失效 / 被带偏 | gamma=Porto 排第一（星形中即 hub），alpha、beta 正确 | R 为奇数时得 Porto | 排列顺序（hub 位置）决定结果 |

   同时应把题目扩展为讲义说的"一道事实、一道规则、一道推理"，并为每种场景记录"第 0 轮正确率 → 辩论后正确率"的变化以及读取次数，才能真正回答"辩论值不值"（讲义练习 4）。

### Q13 — 参考回答要点

- **定义**：多个模型实例对同一问题独立作答，然后进行若干轮互相阅读、批评、修正，最后按收敛规则给出答案（讲义的 Society of Minds 协议）。
- **对比**：

| 方法 | 参与者 | 批评来源 | 主要风险 |
|------|-------|---------|---------|
| Self-Refine | 单模型 | 自己 | 自我确认、群体思维 |
| CRITIC | 单模型 + 工具 | 外部工具（检索、执行） | 依赖工具可用 |
| Self-consistency / 多数投票 | 多次采样 | 无交互，只计票 | 系统性错误会被多数放大 |
| 辩论 | 多实例（最好多模型） | 彼此 | 成本 N × R、收敛塌缩、同质化 |

- 加分点：辩论可以和 CRITIC 结合（辩手可调用工具找证据），也可以和 evaluator-optimizer 组合用于产生评测信号（讲义 2026 instantiations）。

### Q14 — 参考回答要点

- **为什么有效**：
  - 独立作答提供了多个"样本"，不同实例的错误不完全相关，交叉检查能发现幻觉（讲义：factuality）；
  - 规则类任务中，一个模型漏掉的规则可能被另一个指出（讲义举例：国际象棋走法合法性）；
  - 阅读他人的推理能暴露自己推理中的漏洞，多种思路收窄到正确答案。
- **何时变差**：
  - 辩手同质化：错误高度相关，大家一起错，辩论只是让错误更"自信"；
  - 收敛塌缩：从众压力让正确的少数放弃正确答案（Q9 就是一个例子）；
  - 星形中 hub 出错，错误被广播；
  - 没有证据的争论：缺乏外部依据时，"更会说"的一方胜出而不是"更对"的一方；
  - 简单问题上纯粹浪费成本与延迟。
- 加分点：说出缓解手段——强制第 1 轮分歧、多模型、置信度加权、要求引用证据、轮换 hub。

### Q15 — 参考回答要点

- **适用性判断**：合同风险审查是"规则遵循 + 事实核对"型任务，可以接受数秒到数十秒延迟，错误代价高——适合辩论。
- **N 与多样性**：N=3 起步（与原论文一致），使用不同模型或至少不同角色 prompt（如"偏保守的法务""偏业务的律师""条款对照检查员"），避免同质化。
- **R 与提前停止**：R=2；第 0 轮若高度一致且置信度高可提前结束；未收敛时最多再加一轮。
- **拓扑**：N 小时用全连接（3 人全连接每轮仅 6 次读取）；N ≥ 5 时考虑星形或环形，并轮换 hub。
- **收敛规则**：每个风险点由辩手给出 `(结论, 置信度, 引用的条款原文)`；按置信度加权多数，未达超级多数的条目标记为"需人工复核"而不是强行给答案。
- **成本控制**：只对初筛出的可疑条款辩论（先用单模型扫描全文）；限制每轮输出长度；记录每题读取次数与 token（skill 文件第 5 条）；在评测集上量化"辩论增益 / 成本"。
- **可观测性**：每个辩手每轮一个 span，记录答案变化轨迹，便于分析收敛塌缩（第 23、24 节）。

### Q16 — 参考回答要点

- **选择依据**：
  - 全连接：信息最充分，但读取次数 O(N²R)，N 大时上下文与成本都爆炸；适合 N ≤ 3–4；
  - 稀疏拓扑：讲义引用的研究表明能以更低 token 成本达到相近准确率；N 较大或成本敏感时优先；
  - 环形：每人只读邻居，信息传播慢，需要更多轮；
  - 星形：hub 汇总、spoke 只读 hub，最省，但单点风险最大。
- **防止 hub 带偏**（讲义："Rotate or use multiple hubs"）：
  - 每轮轮换 hub；
  - 使用多个 hub，spoke 读取多个 hub 的意见；
  - hub 选用最强或最多样的模型，并要求 hub 汇总时列出各 spoke 的分歧而不是只给结论；
  - 最终答案按全体投票而不是 hub 的答案决定；
  - 监控指标：spoke 在读到 hub 之后改变答案的比例，过高说明 hub 主导过强。

### Q17 — 参考回答要点

- **先量化**：在评测集上分别记录"第 0 轮各辩手正确率""第 0 轮多数票正确率""辩论后正确率"。如果第 0 轮多数票已经和辩论后差不多，说明增益来自"多次采样投票"，交互轮次没有贡献，可以直接退化为并行投票（成本 N 倍而非 N × R 倍）。
- **查同质化**：统计第 0 轮的分歧率。若几乎没有分歧（像本节演示那样），辩论不可能有增益——换不同模型或不同 prompt（skill 文件：第 1 轮后从无分歧则拒绝该协议）。
- **查收敛方向**：统计"从对改错"与"从错改对"的次数。若前者多，说明存在从众/收敛塌缩，需要严格多数、置信度门槛、要求证据（Q11）。
- **查任务类型**：对简单事实题，改用"检索 + CRITIC"；只对困难题启用辩论（路由）。
- **降成本**：提前停止（第 0 轮一致即返回，Q12）、稀疏拓扑、缩短每轮输出、减少 R。
- **结论**：辩论不是默认选项，要在自己的评测集上证明"每多花一倍成本带来多少准确率"再上线（讲义练习 4："Plot cost vs accuracy"）。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../05-self-refine-and-critic/docs/zh.md)：单模型自我批评与工具依据批评，辩论的两个"对照组"。
- [阶段 14 · 12 Anthropic 的工作流模式：优先采用简单方案](../../12-anthropic-workflow-patterns/docs/zh.md)：orchestrator-workers、并行投票等更简单的替代方案。
- [阶段 14 · 13 有状态图 Orchestration：Durable Execution 与 Checkpoints](../../13-langgraph-stateful-graphs/docs/zh.md)：用 LangGraph 实现多轮辩论并做 checkpoint。
- [阶段 14 · 16 OpenAI Agents SDK：Handoffs、Guardrails 与追踪](../../16-openai-agents-sdk/docs/zh.md)：用 handoff 实现往返批评。

### 本节被哪些后续内容用到
- [阶段 14 · 28 Orchestration 模式：监督者、Swarm 与层级结构](../../28-orchestration-patterns/docs/zh.md)：把辩论嵌入更大的编排系统。
- [阶段 16 · 07 心智社会与多 Agent 辩论](../../../16-multi-agent-and-swarms/07-society-of-mind-debate/docs/zh.md)：从多智能体系统角度深入辩论。
- [阶段 16 · 15 投票、自洽性与辩论拓扑](../../../16-multi-agent-and-swarms/15-voting-debate-topology/docs/zh.md)：投票与拓扑的系统化比较。
- [阶段 16 · 23 失效模式：MAST、群体思维、同质化与级联错误](../../../16-multi-agent-and-swarms/23-failure-modes-mast-groupthink/docs/zh.md)：收敛塌缩与同质化的深入分析。
- [阶段 16 · 14 面向 Agents 的共识与拜占庭容错](../../../16-multi-agent-and-swarms/14-consensus-and-bft/docs/zh.md)：当部分辩手不可靠时如何达成共识。

### 延伸关键词
`multi-agent debate` · `Society of Minds` · `self-consistency` · `full mesh` · `sparse topology` · `star / hub-and-spoke` · `ring topology` · `convergence collapse` · `groupthink` · `prompt homogenization` · `confidence-weighted voting` · `early stopping`
