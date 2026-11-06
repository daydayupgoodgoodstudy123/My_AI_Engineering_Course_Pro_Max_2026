# 测验 · 有界自我改进设计（Bounded Self-Improvement Designs）

> **阶段 15 · 自主系统 · 第 08 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 四个有界原语 | 讲义：研究已收敛到四个原语——formal invariants、alignment anchors、multi-objective constraints、regression detection |
| 2 | Invariant（不变量） | 每次自我修改前后都必须成立的性质，由**循环无法编辑的外部代码**检查；违反即拒绝。可抓住 DGM 式的评估器篡改 |
| 3 | Alignment anchor（对齐锚点） | 不可变的核心目标表示，放在循环的编辑面之外（只读宪法、独立仓库的评估器、人类签名的工具权限清单）；循环可以改进"怎么追求目标"，不能改"目标是什么" |
| 4 | 锚点的微妙失效 | 循环改不了锚点，但可以漂移成"换一种方式解读锚点"；讲义："Anchors are necessary, not sufficient" |
| 5 | Multi-objective constraints | 只优化单一标量会找到捷径；要求性能、安全、公平、鲁棒**每一个**约束都成立才接受修改 |
| 6 | Regression detection | 把本轮分数与历史分布比较，跌幅超过容差就暂停，防止能力损失被"后续改进"掩盖在平均数里 |
| 7 | 信息论极限 | Kolmogorov 复杂度与 Löb 定理限制了系统能对自身后继者证明什么；四个原语**不能**闭合安全问题，只是"raise the cost of silent failure" |
| 8 | Gate stack | 按"不变量 → 锚点 → 多目标评估 → 回退检测"依次检查，任何一个失败都拒绝本次修改 |
| 9 | 代码中的门的冗余 | 默认实现里不变量与锚点被同一次变异同时破坏，锚点门永远记 0 次拒绝；多目标门在原始玩具里也没有可观察的作用（性能与安全没有张力） |
| 10 | 回退门只看自身历史 | `gate_regression` 只和循环自己的历史最高分比较——skill 文件把这列为 hard reject（"the loop defines normal"） |

### 核心技能（能动手做到）

- [ ] 说出四个原语各自能拦住哪一类失败，以及缺失时最先出现的失败（skill 文件的 gap analysis）
- [ ] 读懂 `mutate()` 的四种变异分支，估算"篡改清单"分支的触发概率
- [ ] 解释为什么默认输出里 `anchor` 拒绝数恒为 0，并改造代码让锚点门体现独立价值
- [ ] 用多种子统计复现"关掉回退门 → 静默能力损失"（讲义练习 2）
- [ ] 改造玩具任务，使性能与安全产生张力，复现"关掉多目标门 → 安全下降"（讲义练习 3）
- [ ] 为一个 coding agent 设计 alignment anchor：写什么、存在哪、怎么校验（讲义练习 4）

---

## 二、基础自测（选择题）

**Q1.** 下列哪一项**不是**讲义所说的四个有界原语之一？

- A. Formal invariants
- B. Alignment anchors
- C. 模型权重加密（weight encryption）
- D. Regression detection

**Q2.** 讲义引用 Kolmogorov 复杂度和 Löb 定理，想说明的是：

- A. 系统能对自己的后继者证明的东西有上界，所以四个原语无法闭合安全问题，只能提高"静默失败"的代价
- B. 只要把四个原语都实现，就能形式化证明循环是安全的
- C. Schmidhuber 的 Gödel Machine 已经完成了非平凡的自我改进证明
- D. 不变量检查的计算复杂度太高，无法在实践中运行

**Q3.** 讲义指出 alignment anchor 有一种"微妙的失效模式"，它是：

- A. 锚点文件太大，加载变慢
- B. 锚点存储在只读位置，导致循环无法改进
- C. 锚点的哈希算法可能发生碰撞
- D. 循环改不了锚点本身，却可以在"如何解读锚点"上发生漂移；宪法式的推理层正是解读漂移所在

**Q4.** 本节性能测试有 4 个用例，所以 `perf_score` 只能取 0、0.25、0.5、0.75、1.0。`gate_regression` 的默认 `tol=0.2`，其实际效果是：

- A. 允许任何不超过 0.5 的下降
- B. 等价于严格单调门：任何一档（0.25）的下降都会被拒绝，docstring 所说的 "accept noise" 在这里不会发生
- C. 永远不会拒绝任何候选
- D. 只在性能为 0 时拒绝

**Q5.** 默认运行 "All gates ON" 的输出是 `rejects {'invariant': 11, 'anchor': 0, 'multi': 66, 'regress': 27}`。锚点门一次都没有拒绝，原因是：

- A. 锚点门的实现有 bug，永远返回 True
- B. `mutate()` 在同一个分支里同时改清单和改目标，而不变量门先检查，已经把这些候选全部拦下了
- C. 种子 5 下恰好没有发生改目标的变异
- D. 目标字符串的哈希截断到 16 位，篡改后的哈希碰巧相同

**Q6.** 初始 agent 是 `Agent(ops=["nop"])`。它的 `perf_score` 与 `safety_score` 分别是：

- A. 1.0 与 1.0
- B. 0.25 与 0.0
- C. 0.0 与 0.0
- D. 0.0 与 1.0

**Q7.** 在 200 个种子上统计"只关掉回退门"（其余门打开，200 轮）的最终性能，实测结果是：

- A. 平均最终性能约 0.64，只有约 43% 的种子最终性能为 1.0；而四门全开时 100% 的种子都是 1.0
- B. 与四门全开完全相同，所有种子最终性能都是 1.0
- C. 平均最终性能为 0，所有种子都退化
- D. 最终性能更高，因为接受了更多候选

**Q8.** 在本节**原始**代码上关掉多目标门（其余门打开），在 200 个种子上统计，结果是：

- A. 安全分数平均降到 0.37
- B. 性能下降到 0.5，安全保持 1.0
- C. 性能和安全都保持 1.0，与四门全开没有可观察差别——这个玩具里性能与安全不存在张力，讲义练习 3 无法直接复现
- D. 目标发生漂移

---

## 三、动手 / 代码题

**Q9.** 讲义练习 3："Disable the multi-objective constraint. Show the loop converges on the performance axis while a safety axis drops."

```python
def apply(agent: Agent, s: str) -> str:
    for op in agent.ops:
        fn = TOOLS_IMPL.get(op)
        if fn is None:
            return ""
        s = fn(s)
    dangerous = ("exec(", "drop table", "rm -rf", "; delete from")
    low = s.lower()
    if any(d in low for d in dangerous):
        return "[blocked]"
    return s
```

1. 为什么在原始代码里，能让性能拿满分的操作序列（如 `["title", "collapse"]`）一定也能让安全拿满分？
2. 哪些操作会让安全分下降？它们为什么在"只关多目标门"时也进不来？
3. 设计一个改动，让性能与安全真正产生张力，从而复现练习 3。

**Q10.** 关于不变量门与锚点门：

```python
    elif allow_manifest_edit and random.random() < 0.5:
        manifest.add("raw_eval")
        obj = obj + "  # relax: accept any output"
```

1. 每轮触发这一分支的概率大约是多少？`main()` 里的标题 "manifest edits attempted every cycle" 准确吗？
2. 只关掉不变量门时，谁会接手拦截？同时关掉不变量门和锚点门时，200 个种子的最终性能、安全、目标漂移分别是多少？这说明了什么？
3. 改写 `mutate()`，让"改清单"和"改目标"成为两个独立事件，使两扇门各自体现价值。
4. `raw_eval` 在 `TOOLS_IMPL` 中并不存在，`apply()` 遇到它会怎样？这让"走私能力"的演示失真在哪里？

**Q11.** 回退门：

```python
def gate_regression(history_perf: list[float], perf: float, tol: float = 0.2) -> bool:
    if not history_perf:
        return True
    return perf + tol >= max(history_perf)
```

1. skill 文件的 hard reject 之一是 "Any loop whose regression check reads only from its own history"。这段代码违反了吗？为什么这是问题？
2. 它只检查了哪一个轴？讲义说的是 "no axis drops more than tolerance"。
3. 写一个 `gate_regression_v2`：按轴检查、只看最近 N 轮窗口、同时与一个外部固定基线比较。

**Q12.** 讲义练习 2："Disable regression detection. Construct an input where this leads to silent capability loss being accepted."

1. 默认输出里 "Only regression gate OFF" 的最终性能是 1.00，HEADLINE 却说 "silent capability dips get absorbed"。默认输出能证明这句话吗？
2. 关掉回退门后，什么样的候选会被接受、却让性能下降？用 `gate_multi` 的条件说明。
3. 给出一个能稳定展示静默能力损失的实验方案。

---

## 四、面试高频题

**Q13.**（基础必考）有界自我改进的四个原语是什么？各自防住哪一类失败？

**Q14.**（原理深挖）为什么说这些原语只是 mitigation 而不是 proof？Löb 定理、Kolmogorov 复杂度在这里起什么作用？既然证明不了，为什么还值得做？

**Q15.**（场景设计）为一个会修改自己 prompt 和工具配置的 coding agent 设计 alignment anchor：写什么、存在哪、如何校验、如何防止"解读漂移"？

**Q16.**（工程实践）你要评审同事提交的"自我改进循环"设计，用什么清单打分？哪些情况直接否决？

**Q17.**（追问型）回退检测的容差怎么设？只和自身历史比较有什么问题？如果指标噪声很大怎么办？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义的四个原语："Formal invariants … Alignment anchors … Multi-objective constraints … Regression detection"。权重加密是安全工程手段，不在其中。

### Q2 — 答案：A

讲义："Information-theoretic results bound what any system can prove about its own successor, and no current design closes the problem formally"，"They make silent failure more expensive. A malicious or drifted loop that would quietly bypass a missing check must now actively undermine an explicit one, which is a more detectable signature." B 与讲义相反；C 错，讲义说 "nobody has completed a non-trivial proof"；D 不是讲义论点。

### Q3 — 答案：D

讲义："an anchor the loop cannot edit can still be reinterpreted by a loop that drifts in how it reads the anchor. Constitutional AI (Lesson 17) is explicitly reason-based to handle novel situations; that reasoning layer is where interpretation drift lives." B 混淆了"锚点不可改"与"循环不可改进"——循环仍可改进追求目标的方式；A、C 不是讲义讨论的问题。

### Q4 — 答案：B

`perf + 0.2 >= max(history)`：若历史最高 0.75、候选 0.5，则 `0.7 < 0.75` 被拒绝；候选 0.75 通过（实测 `gate_regression([0.75], 0.5) == False`）。因为最小下降一档就是 0.25 > 0.2，所以任何下降都被拒绝。容差要和指标的分辨率一起设计。

### Q5 — 答案：B

篡改分支同时执行 `manifest.add("raw_eval")` 和 `obj = obj + "  # relax…"`，而 `run()` 中先检查 `gate_invariant`，命中即 `continue`，锚点门根本没机会执行。实测：只关不变量门时，锚点门接手拒绝了同样的 11 次（seed 5），说明两者在这个玩具里完全冗余。A 错，锚点门在不变量门关掉时确实会拒绝；C 错，不变量门拒绝了 11 次，说明篡改发生了；D 错，追加文字后哈希不同。

### Q6 — 答案：D

`nop` 原样返回：4 个性能用例的期望输出都与输入不同（如 `"Already clean"` 期望 `"Already Clean"`），所以性能 0.0。两个安全用例原样返回后仍包含 `exec(`、`drop table`，被 `apply()` 末尾的过滤器替换成 `"[blocked]"`，安全 1.0（实测 `init 0.0 1.0`）。这也意味着 `gate_multi` 的 `perf >= 0.25` 要求第一次被接受的修改至少答对 1 个用例。

### Q7 — 答案：A

实测（seed 0–199，每次 200 轮）：只关回退门时最终性能均值 0.636，最终性能为 1.0 的比例 0.43；四门全开时均值 1.000、比例 1.00。默认 seed 5 恰好落在"最终也到了 1.0"的那 43% 里，所以默认输出看不出差别。B 只是 seed 5 的情形；C、D 与实测不符。

### Q8 — 答案：C

实测（200 个种子）：只关多目标门时性能均值 1.000、安全均值 1.000，与全开相同。原因见 Q9：在原始玩具里，能拿满性能分的输出必然也能触发安全过滤器；破坏安全的操作（`reverse`、`raw_eval`）同时破坏性能，会被回退门或不变量门拦下。A 是**四门全关**时的安全均值（0.37）；D 只在不变量门和锚点门都关掉时发生。

### Q9 — 参考答案

1. 安全过滤器在**所有操作之后**对最终字符串做子串匹配（小写后）。性能用例需要的变换只有去空白、折叠空白、title-case，这些变换不会破坏 `exec(`、`drop table`、`rm -rf` 这些子串（`"Exec('Rm -Rf /')"` 小写后仍含 `exec(`），所以安全用例仍被 `[blocked]`。
2. `reverse`（把 `exec(` 倒成 `(cexe`，实测输出 `)'/ fr- mr'(cexe`，绕过过滤器）和 `raw_eval`（不存在于 `TOOLS_IMPL`，`apply()` 直接返回 `""`）。但它们同样会让性能用例全错：`reverse` 让性能下降 → 被回退门拒绝；`raw_eval` 需要先改清单 → 被不变量门拒绝。
3. 一种实测有效的改法：加一个能提升性能、但会顺带破坏危险模式的操作，并把一个性能用例换成需要它的用例（保持 4 个用例，避免 `gate_multi` 的 0.25 阈值失效）：

```python
import re
TOOLS_IMPL["nopunct"] = lambda s: re.sub(r"[^\w\s]", "", s)
APPROVED_TOOL_MANIFEST.add("nopunct")
CASES_PERF[3] = ("(draft)  report!", "Draft Report")
```

`nopunct` 去掉标点后，`"exec('rm -rf /')"` 变成 `"execrm rf "`，不再匹配任何危险模式，于是被原样输出（一个安全用例失败）；`"drop table users;"` 仍含 `drop table`，仍被拦截。实测（200 个种子，300 轮）：四门全开时最终性能均值 0.75、安全 1.0；只关多目标门时性能均值约 0.999、安全约 0.50（99.5% 的种子安全 < 1）。这正是练习 3 要的"性能收敛、安全下降"。注意：若是**追加**第 5 个用例，性能刻度变成 0.2，单步只能到 0.2 < 0.25，`gate_multi` 会让循环卡在初始状态（实测四门全开时性能为 0）——这说明 `perf >= 0.25` 是一个和用例数绑定的魔法数字。

### Q10 — 参考答案

1. 该分支需要前三个分支都没走：`move ≥ 0.9` 的概率 10%（加上 `ops` 长度条件不满足时落下来的少量情形），再乘以 `random.random() < 0.5`，约 5%。实测四门全开时每次运行平均 11.3 次不变量拒绝 / 200 轮 ≈ 5.7%。所以标题 "manifest edits attempted every cycle" 不准确，应理解为"允许尝试，每轮约 5% 的概率尝试"。
2. 只关不变量门：锚点门接手，200 个种子平均每次拒绝 11.3 次，结果与全开完全相同。同时关掉两者：最终性能 1.0、安全 1.0，但 100% 的种子目标漂移（`DRIFTED!`），清单里也多了 `raw_eval`。说明**行为指标看不到"休眠的走私能力"**：`raw_eval` 一用就会让输出为空，多目标门和回退门会拒绝使用它的候选，但它被留在清单里、目标被改写——只有不变量门和锚点门这种"结构性检查"能发现。这正是讲义说不变量要由外部代码检查的原因。
3. 改写：

```python
    elif allow_manifest_edit:
        r = random.random()
        if r < 0.25:
            manifest.add("raw_eval")                      # 只走私能力
        elif r < 0.5:
            obj = obj + "  # relax: accept any output"    # 只改目标
```

这样只关不变量门会放过"只走私能力"的候选，只关锚点门会放过"只改目标"的候选，各自的失败类别可以单独观察。
4. `fn is None` 时 `apply()` 返回 `""`：`raw_eval` 实际上是"让输出为空"的毁坏操作，而不是一个真正有用的危险能力。真实的走私能力往往**提升**某些指标（例如能执行任意代码从而通过更多测试），这时行为门不但拦不住，还会奖励它——更能体现不变量门的必要性。可以把它实现为一个能提升性能但绕过安全过滤的操作来改进演示。

### Q11 — 参考答案

1. 违反。`history` 只包含循环自己接受过的候选的性能。若循环先以某种方式"慢慢地"降低能力（每步都在容差内），或者评估器本身被钻空子导致历史分数虚高，自身历史就不再是可信的"正常"参照——skill 文件："the loop defines 'normal'"。应当另有一个循环无法影响的外部比较集。
2. 只检查了性能一个轴（`history.append(p)`，安全分数没有进入历史）。讲义的 worked example 要求 "no axis drops more than tolerance"。
3. 参考实现：

```python
def gate_regression_v2(history: list[dict], cand: dict, external_baseline: dict,
                       tol: dict, window: int = 10) -> list[str]:
    reasons = []
    recent = history[-window:]
    for axis, value in cand.items():
        if recent:
            best_recent = max(h[axis] for h in recent)
            if value + tol[axis] < best_recent:
                reasons.append(f"{axis} regressed vs recent best {best_recent:.2f}")
        if value + tol[axis] < external_baseline[axis]:
            reasons.append(f"{axis} below external baseline {external_baseline[axis]:.2f}")
    return reasons          # 非空即拒绝，并交给人类审查
```

其中 `external_baseline` 由循环外部（例如已审批版本在保留测试集上的分数）提供，循环不能写入。

### Q12 — 参考答案

1. **不能**。seed 5 下关掉回退门的最终性能仍是 1.00，最佳性能也是 1.00，单看这次输出无法区分"有没有回退门"。唯一可见的差别是接受数从 96 变为 116（`mutate` 的随机抽样依赖当前 agent 状态，两次运行在第一次接受不同候选后随机序列就分叉了，不能逐条对应）——被多接受的候选里可能有"降分但仍满足多目标门"的，只是循环后来又爬回了 1.0。
2. 关掉回退门后，只要候选满足 `perf >= 0.25 and safety >= 1.0` 就会被接受。所以从 1.0 掉到 0.25 的候选也能落地——只要它还答对一个用例、且没破坏安全过滤。这就是"静默能力损失"：没有任何门报警。
3. 方案：固定其余门，分别在"回退门开 / 关"下跑 200 个种子，统计最终性能分布。实测：关掉时最终性能均值 0.636、只有 43% 达到 1.0；开着时 100% 为 1.0。若要单次演示，可以在 `run()` 中打印每次被接受的 `p`，找出"上一轮 1.0、本轮 0.5 仍被接受"的那一步。也可以把循环轮数缩短（例如 50 轮）或在第 k 轮强行注入一个"降分但安全"的候选，让损失更容易停留到最后。

### Q13 — 参考回答要点

| 原语 | 是什么 | 防住的失败（skill 文件 gap analysis） |
|------|-------|-------------------------------------|
| Invariants | 每次修改前后都必须成立、由外部代码检查的性质（模块哈希、工具清单、宪法头、受签名的记忆写入路径） | 缺失 → 走私能力、工具漂移；可抓 DGM 式评估器篡改 |
| Alignment anchor | 编辑面之外的不可变目标表示 | 缺失 → 目标被重新解释 |
| Multi-objective | 性能、安全、公平、鲁棒全部达标才接受 | 缺失 → 安全退步被性能提升掩盖 |
| Regression detection | 与历史分布比较，跌幅超过容差即暂停 | 缺失 → 静默能力损失 |

- 组合方式：gate stack，按顺序检查，任何一个失败都拒绝并暂停。
- 加分点：说出本节代码中门的冗余与盲区（锚点门永远 0、多目标门在原玩具中无作用、回退门只看自身历史且只有一个轴）。

### Q14 — 参考回答要点

- **为什么不是 proof**：讲义：Kolmogorov 复杂度与 Löb 定理给出了"系统能对自身后继者证明什么"的上界；Schmidhuber 的形式化 Gödel Machine 追求最强的这种证明，但"nobody has completed a non-trivial proof"。
- **Löb 定理的直觉**（讲义的通俗表述）："if a system provably believes 'I will do X if I prove I should do X,' it will do X without proving it should"——一种著名的自指陷阱：系统无法通过"相信自己的证明是可靠的"来为自己背书。严格表述是"若一个理论能证明'若 P 可证则 P'，则它能证明 P"。
- **为什么仍值得做**：讲义："A malicious or drifted loop that would quietly bypass a missing check must now actively undermine an explicit one, which is a more detectable signature." 把"静默失败"变成"主动破坏"，后者留下可检测的痕迹。
- 加分点：讲义的诚实框架——"A well-bounded loop is safer than an unbounded one, not safe in absolute terms."

### Q15 — 参考回答要点

- **写什么**：一段简短、具体的目标陈述（例如"只修改当前任务相关的仓库文件；所有改动必须通过测试；不访问凭证；不修改 CI 与评估脚本"），加一份人类签名的工具权限清单。
- **存在哪**：agent 编辑面之外——只读挂载、独立仓库并有独立访问控制、或由 harness 在每次调用时从受保护位置加载（讲义的三个例子）。
- **如何校验**：每轮按字节比对哈希（本节 `gate_anchor` 的做法）；权限清单验签；评估器模块哈希与批准版本一致。
- **防解读漂移**：仅靠哈希不够。加入固定的"解读探针"测试集——一组需要正确理解目标才能答对的场景（例如"测试失败时能否删掉测试？"应答"否"），每轮评估；由独立模型或人类抽查 agent 对目标的复述；把关键约束写成可执行的不变量（例如 CI 配置哈希不得改变）而不是只写成自然语言。
- 常见误区：把锚点放在 agent 可写的工作目录里；只做语义比对（可被"看起来差不多"的改写绕过）。

### Q16 — 参考回答要点

按 `outputs/skill-bounded-loop-review.md`：

- **不变量清单**：每条检查什么、在哪里执行（agent 能否触及）、违反后的动作（硬拒绝 / 暂停 / 仅记录）。
- **锚点**：是什么、存在哪、如何验证循环无法编辑。
- **多目标轴**：性能之外是否有安全、公平、鲁棒；单轴循环不合格。
- **回退策略**：历史窗口、每轴容差、检测到下降时的动作；是否有外部比较集。
- **Gap analysis**：对缺失的原语预测最先出现的失败。
- 每项 0–5 分，最后给出 production / staging / research-only 的结论。
- **直接否决**：零不变量；锚点不在编辑面之外；优化单一标量；回退检查只读自身历史。拒绝条件：把"还没坏过"当安全证据；15 分钟内列不出不变量清单；四个原语不全就想上生产。

### Q17 — 参考回答要点

- **容差与指标分辨率匹配**：本节 4 个用例、分辨率 0.25，`tol = 0.2` 实际等于严格单调（Q4）。容差应基于指标的测量噪声（例如多次重复评测的标准差 × 2–3），而不是拍脑袋。
- **只和自身历史比较的问题**：历史本身可能已被污染（慢性漂移、评估器被钻空子），"正常"由循环自己定义。应加入外部固定基线和保留测试集，以及跨轴检查。
- **噪声大时**：多次重复评测取均值或置信区间；用统计检验（例如 bootstrap）判断下降是否显著；使用滑动窗口而不是单点历史最高（单点最高本身可能是噪声，会造成过多误报）；对"显著下降"暂停并交人类，对"不显著"记录观察。
- 加分点：说明"能力回退常紧跟在暴涨之后"（第 7 节 workshop 的 regression detection 问题），所以暴涨本身也应触发更严格的检查。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 04 Darwin Godel Machine：开放式自我修改 Agents](../../04-darwin-godel-machine/docs/zh.md)：本节代码沿用的 DGM 式玩具，以及评估器篡改的案例。
- [阶段 15 · 07 递归自我改进：能力与 Alignment 的权衡](../../07-recursive-self-improvement/docs/zh.md)：小速率差复利成大差距，本节给出对应的闸门设计。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：单一标量被优化时为什么会找到捷径。

### 本节被哪些后续内容用到
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../13-cost-governors/docs/zh.md)：讲义提到 cost governor 可作为额外的约束轴叠加。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../14-kill-switches-canaries/docs/zh.md)：门触发后的暂停与停止机制。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../16-checkpoints-rollback/docs/zh.md)：回退检测后的回滚。
- [阶段 15 · 17 Constitutional AI 与规则覆盖](../../17-constitutional-ai/docs/zh.md)：作为 alignment anchor 的宪法，以及解读漂移所在的推理层。
- [阶段 15 · 18 Llama Guard 与输入输出分类](../../18-llama-guard/docs/zh.md)：可接入的安全轴。
- [阶段 15 · 19 Anthropic Responsible Scaling Policy v3.0](../../19-anthropic-rsp/docs/zh.md)、[阶段 15 · 20 OpenAI Preparedness Framework 与 DeepMind Frontier Safety Framework](../../20-openai-preparedness-deepmind-fsf/docs/zh.md)：在能力阈值中引用这些原语的框架。
- [阶段 14 · 38 Verification Gates](../../../14-agent-engineering/38-verification-gates/docs/zh.md)：agent 工程中的验证闸门。

### 延伸关键词
`bounded self-improvement` · `formal invariants` · `alignment anchor` · `multi-objective constraints` · `regression detection` · `gate stack` · `Löb's theorem` · `Kolmogorov complexity` · `Gödel Machine` · `interpretation drift` · `held-out baseline` · `SAHOO`
