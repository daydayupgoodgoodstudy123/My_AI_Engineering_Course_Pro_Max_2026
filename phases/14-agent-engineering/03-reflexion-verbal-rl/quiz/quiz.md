# 测验 · Reflexion：语言反馈驱动的 Reinforcement Learning（Reflexion: Verbal Reinforcement Learning）

> **阶段 14 · Agent 工程 · 第 03 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 提示：本节中文讲义为质量很差的机器翻译（如把 HumanEval 译成"人类的测试"、vanilla 译成"香草"），请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 要解决的问题 | 基于梯度的 RL 修一个失败模式要成千上万次试验和 GPU 集群；Reflexion 不更新权重，只在试验之间保存自然语言 |
| 2 | 三个组件 + 一个数据结构 | Actor 生成轨迹（ReAct 式循环）；Evaluator 打分；Self-Reflector 写失败反思；Episodic memory 把历史反思放到下一次试验的 prompt 前面 |
| 3 | 一次试验的流程 | Actor 执行 → Evaluator 打分 → 分数低则写反思 → 存入记忆 → 下一次**从头开始**但能看到反思 |
| 4 | 三类 Evaluator | Scalar（外部二元/数值信号，如单测通过与否，信号最强）、Heuristic（预定义失败特征，如重复动作、步数超限）、Self-evaluated（LLM 自评，信号最弱，宜配合 CRITIC 式工具验证） |
| 5 | 2026 默认组合 | 有 scalar 就用 scalar，没有才用自评，heuristic 作为安全护栏 |
| 6 | 论文结果（讲义） | Shinn 等（NeurIPS 2023，arXiv:2303.11366）：ALFWorld 上超过 ReAct 等未微调基线；HotpotQA 上优于 ReAct；代码生成（HumanEval/MBPP）当时达到 SOTA，全程无梯度更新 |
| 7 | 生产中的同类模式 | Letta sleep-time compute、Claude Code 的 `CLAUDE.md` 记忆、pro-workflow 的 `/learn-rule`、LangGraph 的 reflection 节点 |
| 8 | 何时有效 | 失败信号清晰、任务类别可复现、动作预算足以改进 |
| 9 | 何时无效 | 第一次就成功；外部故障（网络断了）；反思变成"迷信"（把一次偶发故障写成规律） |
| 10 | Memory rot | 反思不断累积，有的过时或错误，buffer 越大重跑越慢；用定期压缩、TTL、sleep-time 清理 agent 缓解 |

### 核心技能（能动手做到）

- [ ] 用标准库写出 Actor / Evaluator / Self-Reflector / EpisodicMemory 四个部件，并组装成多次试验的 Reflexion 循环
- [ ] 区分"Actor 真的读了反思内容"与"Actor 只看反思条数"，并写出一个依据反思文本调整行为的 Actor
- [ ] 实现 heuristic evaluator（重复动作 → stuck），用它识别"目标不可达"并提前终止
- [ ] 为 episodic memory 实现按试验计数的 TTL、去重和容量上限，并说明为什么 TTL 按试验而非按墙钟时间
- [ ] 判断一条反思是否"可执行"：符合"我因为 Y 没做到 X，下次做 Z"，拒绝"下次更仔细"这类空话
- [ ] 针对具体任务选择 evaluator 类型（scalar / heuristic / self-eval）并说明信号强弱

---

## 二、基础自测（选择题）

**Q1.** Reflexion 系统由哪三个组件（外加一个数据结构）构成？

- A. Planner、Workers、Solver，外加证据表
- B. Actor、Evaluator、Self-Reflector，外加 episodic memory
- C. Generator、Critic、Refiner，外加历史记录
- D. Policy、Value、Reward model，外加 replay buffer

**Q2.** 与标准强化学习相比，Reflexion 用什么替代了什么？

- A. 用更大的 batch 替代更多的试验次数
- B. 用奖励模型替代人工标注
- C. 用 LoRA 微调替代全量微调
- D. 用存放在试验之间、拼进下一次 prompt 的自然语言反思，替代梯度与权重更新

**Q3.** 代码生成任务中，用 HumanEval 的单元测试"通过 / 不通过"作为反馈，属于哪类 evaluator？

- A. Scalar：来自外部 ground truth 的二元信号
- B. Heuristic：预定义的失败特征
- C. Self-evaluated：LLM 给自己的轨迹打分
- D. Reward model：训练出来的偏好模型

**Q4.** 下列哪种情况，讲义认为 Reflexion **帮不上忙**？

- A. 代码单测失败，错误信息清楚
- B. 同类客服工单每天都会重复出现
- C. 这次失败是因为网络临时中断
- D. 动作预算足够让 Actor 换一种做法

**Q5.** 运行本节代码：baseline 4 次都给出 `[1, 2, 3]` 并失败；开启记忆后第 3 次用 `[6, 7, 7]` 成功。关于 `Actor.act` 如何使用记忆，正确的是：

- A. 它解析最近一条反思中的"差多少"，按差值调整三个数
- B. 它把所有反思拼成 prompt 交给一个小模型
- C. 它会读取反思中的 "larger / smaller" 关键词决定方向
- D. 它只看 `len(memory.items)`（反思条数），按条数返回写死的答案，从不读取反思内容

**Q6.** 关于 memory rot，下列说法正确的是：

- A. 指模型权重随时间退化，需要重新训练
- B. 指 episodic buffer 中积累了过时或错误的反思，使后续试验变慢甚至被误导；可用定期压缩、TTL、sleep-time 清理来缓解
- C. 指反思太短，信息量不足
- D. 只要把 buffer 设成无限大就能避免

**Q7.** 本节 `EpisodicMemory` 默认 `max_len=6`。依次 `add` 第 1～8 次试验的反思后，`items` 里保留的是：

- A. 第 3～8 次试验的反思
- B. 第 1～6 次试验的反思
- C. 全部 8 条
- D. 只有第 8 次的反思

**Q8.** 本节的 `binary_evaluator` 返回 `(total == target, total - target)`。下面哪种说法最准确？

- A. 它是严格的二元 evaluator，Self-Reflector 只能知道"失败了"
- B. 它是 self-evaluated evaluator，因为由 Actor 自己计算
- C. 名字叫 binary，但它还返回了带符号的距离 `delta`，Self-Reflector 正是靠它写出"差 14、请选更大的数"——实际传给反思器的是 scalar 距离信号
- D. 它是 heuristic evaluator，因为检查的是固定规则

---

## 三、动手 / 代码题

**Q9.** 把 `TARGET` 改为 25（三个 1～9 的整数最大和为 27，目标可达），开启记忆跑 6 次，实测输出为：

```text
[1, 2, 3] delta=-19 -> [5, 6, 7] delta=-7 -> [6, 7, 7] delta=-5 -> [6, 7, 7] delta=-5 -> [6, 7, 7] delta=-5 -> [6, 7, 7] delta=-5
```

1. 每次的反思都写着 "is 5 short; pick larger values"，为什么 Actor 仍然原地踏步？
2. 写一个 `AdaptiveActor`：读取最近一条反思中的"差多少/超多少"，在保持每个数在 1～9 范围内的前提下调整上一轮的答案。它在 TARGET = 20 时需要几次试验？

**Q10.** 完成讲义练习 3：实现 heuristic evaluator——若最近两次尝试完全相同就判为 stuck。

1. 把它与 Q9 的 `AdaptiveActor` 组合，TARGET 分别为 20、5、27、28 时会发生什么？
2. stuck 信号与 Self-Reflector 应如何配合？TARGET = 28 时，"pick larger values" 这条反思还有意义吗？

**Q11.** 完成讲义练习 2：给 episodic memory 加上 TTL（按试验计数）。

```python
class TTLMemory(EpisodicMemory):
    ttl: int = 10
    def prune(self, now: int) -> None:
        self.items = [r for r in self.items if now - r.trial < self.ttl]
```

设 `ttl = 3`、`max_len` 足够大，每次试验开始前先 `prune(t)` 再 `add(Reflection(t, ...))`，t = 1..6。最后 `items` 里留下哪几次试验的反思？TTL 和原代码的 `max_len` 在淘汰逻辑上有什么本质区别？配套 skill 为什么要求 TTL 按试验计数而不是按墙钟时间？

**Q12.** 下面是某个 coding agent 的 episodic buffer（同一任务类别"修复失败的单测"）。按讲义与配套 skill 的标准，逐条判断应保留、改写还是拒绝，并说明理由。

```text
1. 下次要更仔细一点。
2. 我没有先运行失败的测试就改了代码，导致改错文件；下次先运行 pytest -x 定位失败用例。
3. 第 12 次试验时 PyPI 超时，安装依赖失败。
4. 调试时把 OPENAI_API_KEY=sk-... 打到了日志里，下次注意。
5. 我没有先运行失败的测试就改了代码；下次先运行失败的测试。
6. 周二下午的运行总是更容易失败，周二应该少改动。
```

---

## 四、面试高频题

**Q13.**（基础必考）什么是 Reflexion？它和传统 RL 微调、以及简单的"失败就重试"有什么区别？

**Q14.**（原理深挖）为什么"把反思写进 prompt"就能起到类似强化学习的效果？它的局限在哪里？为什么 self-evaluated 反馈是最弱的信号？

**Q15.**（工程实践）在生产系统里设计一个 episodic memory（反思缓冲区），你会考虑哪些维度？

**Q16.**（场景设计）为一个"自动修复 CI 失败测试"的 coding agent 设计 Reflexion 方案：evaluator 用什么、反思怎么写、记忆怎么存、何时停止。

**Q17.**（追问型）如何判断一条反思真的"有用"，而不是"迷信"？如果反思让 agent 变差了，你怎么发现和处理？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："Actor: generates a trajectory (ReAct-style loop)；Evaluator: scores the trajectory；Self-Reflector: writes a natural-language reflection on the failure"，外加 "Episodic memory: list of prior reflections, prepended to the next trial's prompt"。A 是 ReWOO（第 02 节）；C 接近 Self-Refine（第 05 节）；D 是 actor-critic 类 RL 的术语，涉及梯度训练。

### Q2 — 答案：D

讲义："No weight updates. No gradient. Just natural language stored between trials." A、C 仍是基于梯度的训练手段；B 描述的是 RLHF 中奖励模型的作用，与 Reflexion 无关。

### Q3 — 答案：A

讲义的 Scalar 类型："an external binary signal. ALFWorld succeeds or fails. HumanEval tests pass or fail. Simplest, highest-signal." 注意讲义里"scalar"包含了二元信号——关键是**来自外部 ground truth**。B 是"同一动作重复两次"之类的规则；C 是模型自评；D 不在讲义的三类之中。

### Q4 — 答案：C

讲义："The failure is external (network down, tool broken) — reflection on 'the network was down' does not help future runs." A、B、D 恰好是讲义列出的"有效条件"：清晰的失败信号、可复现的任务类别、足够的动作预算。

### Q5 — 答案：D

```python
    def act(self, memory: EpisodicMemory) -> list[int]:
        n = len(memory.items)
        if n == 0:
            return [1, 2, 3]
        if n == 1:
            return [5, 6, 7]
        if n == 2:
            return [6, 7, 7]
        return [6, 7, 7]
```

只用到条数 `n`，反思文本从未被读取。实测把反思内容换成相反的 "pick SMALLER values"，Actor 在有 1 条反思时照样返回 `[5, 6, 7]`。baseline 之所以永远停在 `[1, 2, 3]`，是因为每次都传入一个**新的空** `EpisodicMemory()`。这个 demo 演示了"有记忆 vs 无记忆"的流程差异，但没有演示"反思内容如何改变行为"——这正是 Q9 要补的。

### Q6 — 答案：B

讲义："Reflections accumulate; some are obsolete or wrong; re-runs get slower as the episodic buffer grows. Mitigation: periodic compaction, TTL on reflections, or a separate sleep-time cleanup agent (Letta)." D 恰恰会加重 memory rot；A 说的是权重，Reflexion 根本不改权重；C 不是这个术语的含义。

### Q7 — 答案：A

```python
    def add(self, r: Reflection) -> None:
        self.items.append(r)
        if len(self.items) > self.max_len:
            self.items.pop(0)
```

每次追加后若超过 6 条就弹出最旧的一条（FIFO）。加入第 7 条时弹出第 1 条，加入第 8 条时弹出第 2 条，剩下第 3～8 条。实测 `max_len=3` 时加入 1～5 条，剩下 `trial 3、4、5`。注意这只是**容量上限**，讲义"动手实现"一节说它是"a bounded list with TTL semantics"，但代码里并没有 TTL。

### Q8 — 答案：C

`SelfReflector.reflect(attempt, delta)` 依赖 `delta` 的正负和大小写出 "sum 6 is 14 short; pick larger values"。如果真的只有 `True/False`，反思器只能写"失败了"，无法给出方向和幅度。这也意味着讲义练习 1（"把 binary 换成返回距离的 scalar evaluator，会不会收敛更快"）在本代码里**已经部分成立**：反思器早就拿到了距离。B 错：evaluator 是独立于 Actor 的、基于 ground truth 的检查；D 错：heuristic 指"重复动作""步数过多"这类失败特征。

### Q9 — 参考答案

1. Actor 只按反思**条数**返回答案：条数 ≥ 2 时永远返回 `[6, 7, 7]`（和为 20）。TARGET = 25 时它与目标差 5，反思写得再准确也没人读，于是原地踏步。这说明本节 demo 的"成功"是脚本作者事先为 TARGET = 20 写好的，不是反思驱动的。
2. 参考实现（已运行验证）：

```python
import re

class AdaptiveActor:
    """读取最近一条反思中的差值，在 [1, 9] 范围内调整上一轮答案。"""
    def __init__(self):
        self.last = [1, 2, 3]

    def act(self, memory):
        if not memory.items:
            return list(self.last)
        text = memory.items[-1].text
        m_short = re.search(r"is (\d+) short", text)
        m_over = re.search(r"overshoots by (\d+)", text)
        gap = int(m_short.group(1)) if m_short else -int(m_over.group(1)) if m_over else 0
        nxt = list(self.last)
        for i in range(3):
            if gap > 0:                       # 需要变大：每个数最多加到 9
                step = min(9 - nxt[i], gap); nxt[i] += step; gap -= step
            elif gap < 0:                     # 需要变小：每个数最少减到 1
                step = min(nxt[i] - 1, -gap); nxt[i] -= step; gap += step
        self.last = nxt
        return nxt
```

实测：TARGET = 20 时第 1 次 `[1, 2, 3]` 差 14，第 2 次调整为 `[9, 8, 3]`，和为 20，**2 次**成功（原脚本需要 3 次）；TARGET = 5 时第 2 次 `[1, 1, 3]` 成功；TARGET = 27 时第 2 次 `[9, 9, 9]` 成功。要点：真实 LLM Actor 中，"读反思"由把 `memory.as_prompt()` 拼进 prompt 实现，模型是否真的利用它，需要用 Q17 的方法验证。

### Q10 — 参考答案

```python
def stuck(history, k=2):
    return len(history) >= k and all(h == history[-1] for h in history[-k:])
```

1. 实测：TARGET 为 20、5、27 时都在第 2 次成功，heuristic 不触发；TARGET = 28 时（超过最大和 27，**不可达**）：第 1 次 `[1, 2, 3]` 差 22 → 第 2 次 `[9, 9, 9]` 差 1 → 第 3 次仍是 `[9, 9, 9]`，判为 `STUCK: same attempt repeated; target may be infeasible`，提前终止，不再浪费预算。
2. 配合方式：heuristic 是"关于过程的信号"，scalar 是"关于结果的信号"。stuck 被触发时，Self-Reflector 不应再重复"pick larger values"（Actor 已经无法再增大，这条反思毫无新信息，继续存入只会制造 memory rot），而应写出更高层的反思，例如"所有数已到上限 9 仍不足，目标可能不可达，需要检查约束或上报"，并停止循环。讲义也提醒：反思需要有"改进空间"才有用。

### Q11 — 参考答案

逐步模拟（已运行验证）：

| t | prune 后 | add 后 |
|---|---------|--------|
| 1 | [] | [1] |
| 2 | [1] | [1, 2] |
| 3 | [1, 2] | [1, 2, 3] |
| 4 | 4−1 = 3 不小于 3，删去 1 → [2, 3] | [2, 3, 4] |
| 5 | 删去 2 → [3, 4] | [3, 4, 5] |
| 6 | 删去 3 → [4, 5] | [4, 5, 6] |

最终留下第 **4、5、6** 次试验的反思。

- **本质区别**：`max_len` 是**按容量**淘汰——只有在新反思挤进来时才淘汰最旧的，buffer 不满时 100 次试验前的反思也会一直留着；TTL 是**按年龄**淘汰——不管 buffer 多空，过期就删，直接针对"过时反思"这种 memory rot。两者通常同时使用。
- **为什么按试验计数**：配套 skill 写明"TTL should be trial-scoped, not time-scoped, for offline-replayable runs"。按墙钟时间过期，离线重放同一批试验时会因为运行快慢不同而得到不同的记忆状态，结果不可复现；按试验计数则与运行速度无关。
- 实现细节：示例中 `TTLMemory` 没有加 `@dataclass`，`ttl` 只是类属性，用 `m.ttl = 3` 覆盖；生产中更清晰的做法是给每条反思存 `ttl_remaining` 字段（skill 要求的输出格式之一）。

### Q12 — 参考答案

| # | 处理 | 理由 |
|---|------|------|
| 1 | **拒绝/重写** | skill 明确："Writing reflections as 'be more careful next time.' That is not actionable"；应强制反思器重写成具体指令 |
| 2 | **保留** | 符合"我因为 Y 没做到 X，下次做 Z"的格式：失败原因（没先跑测试）+ 具体动作（`pytest -x`） |
| 3 | **拒绝** | 外部故障（网络/PyPI 超时），讲义："reflection on 'the network was down' does not help future runs"；除非可稳定复现 |
| 4 | **拒绝** | 含密钥，skill："Storing reflections that reference secrets… Reject with a specific 'contains secret'-class error before committing to the buffer"；同时应触发密钥轮换 |
| 5 | **去重** | 与第 2 条近似重复，skill 要求近似重复只保留最近的一条，或合并成信息更全的第 2 条 |
| 6 | **拒绝** | 典型的"迷信"：把偶发相关性写成规律，没有因果机制，会误导后续试验 |

延伸：这些判断本身可以做成写入 buffer 之前的过滤器（密钥正则、外部错误码识别、去重、"必须包含下次动作"的格式校验），而不是事后清理。

### Q13 — 参考回答要点

- **定义**：Shinn 等（NeurIPS 2023）提出的"语言强化学习"：Actor 尝试 → Evaluator 打分 → 失败时 Self-Reflector 写自然语言反思 → 存入 episodic memory → 下一次试验把反思放进 prompt。
- **与 RL 微调的区别**：不改权重、不算梯度、不需要训练基础设施；"学习"存在于 prompt 上下文里，可读、可删、可审计；代价是只在上下文窗口内生效，不会泛化到权重里。
- **与"失败就重试"的区别**：简单重试的每次尝试相互独立，同样的错误会再犯；Reflexion 的下一次尝试带有"上次为什么失败、这次怎么做"的信息。
- **结果**：讲义称其在 ALFWorld、HotpotQA 上超过 ReAct，在 HumanEval/MBPP 代码生成上当时达到 SOTA，全程没有梯度更新。
- 加分点：说出 2026 年的生产对应物——Claude Code 的 `CLAUDE.md`、Letta 的 sleep-time compute、LangGraph 的 reflection 节点。

### Q14 — 参考回答要点

- **为什么有效**：LLM 具备 in-context learning 能力，prompt 中的经验会改变后续生成的条件分布；自然语言反思把"稀疏的成败信号"转成"密集、具体的改进指令"（讲义："natural language is a rich-enough medium to carry 'what I learned from failure'"），相当于语义层面的 credit assignment。
- **局限**：
  - 依赖清晰的失败信号；没有 evaluator 就没有反思的依据（skill："reflection requires a signal, not a gut feeling"）；
  - 只对可复现的任务类别有用；
  - 受上下文窗口限制，buffer 会膨胀、过时（memory rot）；
  - 模型能力是上限：反思指出了方向，模型未必能执行；
  - 可能固化错误（迷信）。
- **为什么 self-eval 最弱**：模型用同一套知识评判自己，没有外部 grounding，容易给自己的错误答案"盖章"；讲义建议与基于工具的验证（第 05 节 CRITIC）配合使用。
- 加分点：讲义的 2026 默认组合——"有 scalar 用 scalar，没有用 self-eval，heuristic 做护栏"。

### Q15 — 参考回答要点

- **作用域**：task-class（默认）/ user / agent 三级；只在反思涉及用户偏好时升级到 user，**永不**自动升级到 agent 级（skill 的 scope policy）。
- **写入质量门**：格式校验（必须有失败原因和下次动作）、密钥/PII 过滤、外部故障过滤、去重与近似去重。
- **生命周期**：按试验计数的 TTL（建议 10）、容量上限、定期压缩（聚类近似反思、摘要合并），压缩放在 sleep-time，不阻塞主 agent。
- **注入方式**：单独一个 "What I learned from prior trials" 区块，最多 6 条，溢出部分汇总成一条（skill 的 prompt integration）。
- **可观测与可控**：每条反思记录来源试验 id、创建时间、命中次数；支持人工查看和删除；提供"即将过期"报告。
- 加分点：把 buffer 作为文件存储（如 `CLAUDE.md`、JSON），便于版本管理和代码评审。

### Q16 — 参考回答要点

- **Evaluator**：首选 scalar——CI 的测试结果（失败用例数、具体断言）；heuristic 护栏——同一补丁重复提交、修改了测试文件本身、改动行数超限；self-eval 只用于解释失败原因，不用于判定通过。
- **Actor**：ReAct 式循环，工具包括读文件、运行指定测试、编辑、提交补丁；每次试验从干净的工作区开始。
- **Self-Reflector**：输入为本次补丁 diff、测试输出、轨迹摘要；输出一条"因为 Y 没做到 X，下次做 Z"，例如"我只修了症状没修根因，下次先在调用方加断言定位输入来源"。
- **记忆**：按"仓库 + 测试套件"作为 task-class 存储；TTL 10 次试验；外部故障（CI runner 挂掉、依赖下载超时）不入库。
- **停止条件**：测试全部通过；达到最大试验次数（如 3–5 次）；heuristic 判为 stuck；成本预算用尽。未通过时把补丁和反思交给人工，而不是"声称修好了"。
- 加分点：把有效的反思升级为仓库级规则（`CLAUDE.md` / `/learn-rule`），并要求人工审核后才能升级。

### Q17 — 参考回答要点

- **判断"有用"**：
  - 做对照实验：同一批任务分别在"带这条反思"和"不带"两种情况下运行，比较成功率、步数、token；
  - 跟踪命中率：反思被注入后，相关失败模式是否减少；
  - 要求因果性：反思必须指向可解释的机制（"没先跑测试"），而不是相关性（"周二容易失败"）。
- **发现变差的信号**：成功率下降、步数上升、agent 频繁执行反思要求的动作却无效、多条反思相互矛盾。
- **处理**：撤销或降权有问题的反思；缩短 TTL；把 buffer 改为"需人工审核才能生效"；对冲突反思做合并（sleep-time compaction）。
- **与相近模式的关系**：Self-Refine（第 05 节）在**同一次**生成内迭代改写；Reflexion 跨**多次试验**积累经验；`CLAUDE.md` 等跨**会话**持久化——三者是同一思想在不同时间尺度上的应用。
- 常见误区：把所有失败都写成反思，不区分外部故障和自身错误；只增不删。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../01-the-agent-loop/docs/zh.md)：Reflexion 的 Actor 就是一个 ReAct 循环。
- [阶段 14 · 02 ReWOO 与 Plan-and-Execute：解耦 Planning](../../02-rewoo-plan-and-execute/docs/zh.md)：讲义列出的先修课；replanner 与反思都是"把失败信息带回决策"。
- [阶段 11 · 05 Context Engineering: 窗口、 预算、 记忆和检索](../../../11-llm-engineering/05-context-engineering/docs/zh.md)：反思缓冲区是上下文预算的一部分。
- [阶段 11 · 10 Evaluation 与 LLM 应用测试](../../../11-llm-engineering/10-evaluation/docs/zh.md)：evaluator 的设计与 LLM-as-judge 的局限。

### 本节被哪些后续内容用到
- [阶段 14 · 04 Tree of Thoughts 与 LATS：审慎搜索](../../04-tree-of-thoughts-lats/docs/zh.md)：LATS 在树搜索中加入了 Reflexion 式反思。
- [阶段 14 · 05 Self-Refine 与 CRITIC：迭代改进输出](../../05-self-refine-and-critic/docs/zh.md)：单次生成内的反馈改写，以及工具 grounding 的验证。
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../07-memory-virtual-context-memgpt/docs/zh.md)、[阶段 14 · 08 记忆块与休眠时计算](../../08-memory-blocks-sleep-time-compute/docs/zh.md)：讲义提到的 sleep-time 反思与记忆块。
- [阶段 14 · 34 代码仓库记忆与持久状态](../../34-repo-memory-and-state/docs/zh.md)：`CLAUDE.md` 式的跨会话经验存储。
- [阶段 14 · 46 把每一次对 Agent 的纠正转化为系统改进](../../46-turn-feedback-into-system/docs/zh.md)：`/learn-rule` 式的规则沉淀。
- [阶段 15 · 02 STaR、V-STaR、Quiet-STaR：自学推理](../../../15-autonomous-systems/02-star-family-reasoning/docs/zh.md)：对照"用梯度把经验学进权重"的路线。

### 延伸关键词
`Reflexion` · `verbal reinforcement` · `Actor / Evaluator / Self-Reflector` · `episodic memory` · `scalar / heuristic / self-eval feedback` · `memory rot` · `TTL` · `compaction` · `sleep-time compute` · `CLAUDE.md` · `in-context learning` · `credit assignment`
