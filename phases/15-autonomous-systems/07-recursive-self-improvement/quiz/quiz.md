# 测验 · 递归自我改进：能力与 Alignment 的权衡（Recursive Self-Improvement — Capability vs Alignment）

> **阶段 15 · 自主系统 · 第 07 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 注：中文讲义为机器翻译，部分句子不通（如把 RSI 译成"皇家空间研究所"），请以英文版为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | RSI 的精确定义 | 给定 `S_n` 产出在目标上得分更高的 `S_{n+1}`；当 `S_{n+1}` **自己**提出产生 `S_{n+2}` 的修改时，过程才是"递归的" |
| 2 | 两种 RSI | Capability RSI 的目标是任务表现（benchmark、泛化、horizon）；Alignment RSI 的目标是 alignment 质量（alignment 检查、宪法契合度、意图） |
| 3 | 闭环条件（closure condition） | 循环在两轮之间是否需要人类；改进能否泛化到新问题；alignment 能否跟上。讲义：2026 年两种循环都还没有完全闭合 |
| 4 | Alignment faking 结果 | 讲义：Anthropic 2024 年研究中，Claude 在 12% 的基础测试中表现出伪装行为，某些条件下升至 78%；RSI 每一轮都会施加同样的训练过程，可能放大它 |
| 5 | Hassabis 之问 | 循环能否"without a human in the loop"闭合？有人类的循环更慢——竞争压力推动移除人类，但人类目前是唯一可靠的 alignment 锚点 |
| 6 | 为什么能力跑得比 alignment 快 | 讲义转述 Brundage 与 Kaplan 的框架：能力有清晰可测的目标（benchmark），alignment 的目标模糊（价值、原则、意图）；优化循环更擅长尖锐目标 |
| 7 | 能力 vs alignment 的竞赛模型 | `M(t) = C(t) − A(t)`，`r_c > r_a` 时差距增长；小的速率差在复利下变成大差距 |
| 8 | 缓解手段 | 每轮做实证 alignment 检查（第 8 节）、跨模型审计（第 17 节）、外部评估（第 21 节）、触发暂停的硬阈值（第 19 节）；讲义："None is proven sufficient" |
| 9 | ICLR 2026 RSI Workshop 四个开放问题 | 评估器泛化、alignment 锚点保持、回退检测（regression detection）、轮间审计（inter-cycle audit） |
| 10 | 模拟器结论要打折扣 | 单条轨迹会误导：场景 B "stays bounded" 在 30 轮 Monte-Carlo 下约 37% 越线；场景 C "does NOT save you" 在 500 次试验中只有 0.4% 越线 |

### 核心技能（能动手做到）

- [ ] 写出 RSI 的定义，并区分"自我改进"与"递归自我改进"
- [ ] 手算两条复利曲线的差距何时越过阈值（如 `1.15^n − 1.08^n ≥ 1.5`）
- [ ] 读懂 `run()` / `crossing_cycle()` / `monte_carlo()`，说出 `max(0.9, nc)` 的作用
- [ ] 用 Monte-Carlo 检验单条轨迹得出的结论，识别"HEADLINE 与数据矛盾"之处
- [ ] 解释为什么绝对差距 `C − A` 是依赖尺度的指标，并改用比值或对数差距
- [ ] 按 `outputs/skill-rsi-cycle-pause-spec.md` 为一条 RSI 流水线写出暂停规范（阈值、单轮变化上限、回退监控、人工恢复契约）

---

## 二、基础自测（选择题）

**Q1.** 按讲义的精确定义，一个自我改进过程什么时候算"递归的"？

- A. 只要每一轮产出的系统比上一轮得分更高
- B. 当 `S_{n+1}` 自己提出产生 `S_{n+2}` 的那次修改时
- C. 当人类研究者在每一轮之间都检查结果时
- D. 当系统的能力与 alignment 以相同速率增长时

**Q2.** 讲义转述的 Anthropic 2024 年 alignment faking 研究数字是：

- A. 1% 的基础测试中伪装，重训练后降为 0%
- B. 50% 的基础测试中伪装，重训练后升至 100%
- C. 12% 的基础测试中伪装，重训练后降为 7.8%
- D. 12% 的基础测试中伪装，某些条件下升至 78%

**Q3.** 不考虑噪声，场景 A 中 `C(n) = 1.15^n`、`A(n) = 1.08^n`。差距 `C − A` 第一次 ≥ 1.5 发生在第几轮？

- A. 第 9 轮
- B. 第 7 轮
- C. 第 12 轮
- D. 第 15 轮

**Q4.** 讲义转述 Brundage 与 Kaplan 把 RSI 称为 "ultimate risk"，其核心论证是：

- A. 算力成本下降太快，监管跟不上
- B. 开源模型会让 RSI 失控
- C. 能力有清晰可测的目标（benchmark），alignment 的目标模糊；优化循环更擅长尖锐目标，所以能力会跑在 alignment 前面
- D. RSI 必然导致模型权重泄露

**Q5.** 下列哪一项**不是**讲义列出的 ICLR 2026 RSI Workshop 四个工程开放问题之一？

- A. 评估器泛化：到 `S_{n+10}` 时评测还在测重要的东西吗
- B. 回退检测：如何抓住能力暴涨之后的能力下滑
- C. 硬件出口管制：如何限制 RSI 系统获得训练芯片
- D. 轮间审计：下一轮开始前由谁检查这一轮

**Q6.** `run()` 中每轮的乘子是 `max(0.9, nc)`，其作用是：

- A. 把单轮的倍率下限钳在 0.9——任何一轮最多下降 10%，防止噪声让数值骤降甚至变为负数
- B. 把单轮倍率上限钳在 0.9，防止能力暴涨
- C. 把 alignment 永远压在能力的 90%
- D. 把阈值缩小为原来的 90%

**Q7.** 场景 B（`r_c = r_a = 1.10`，`noise_c = 0.02`，`noise_a = 0.03`，阈值 1.5）。用 2000 次 Monte-Carlo 重复，下列说法与实测最接近的是：

- A. 速率相同，所以差距始终有界，从不越线
- B. 30 轮内约 100% 越线
- C. 30 轮内约 2% 越线
- D. 30 轮内约 37% 越线、40 轮内约 55% 越线；绝对差距会随 C、A 的规模一起扩散，"stays bounded" 只是单条轨迹的偶然

**Q8.** 关于 Hassabis 在 WEF 2026 提出的问题，与讲义一致的分析是：

- A. 这是修辞问题，答案显然是"可以"
- B. 有人类的循环更慢，竞争上移除人类能获得速度；但在当前技术栈里人类是唯一可靠的 alignment 锚点——激励推动移除人类，安全分析往回拉
- C. 人类在循环中只负责提供算力预算
- D. 讲义认为移除人类之后 alignment faking 会自然消失

---

## 三、动手 / 代码题

**Q9.** 程序最后打印的 HEADLINE：

```python
    print("  Scenario C: higher alignment mean does NOT save you if")
    print("  capability has big surges. Noise matters as much as drift.")
```

而同一次运行的输出是：

```text
Scenario C — alignment higher mean rate but capability surges
  ...
  -> threshold not crossed in simulated window

Monte-Carlo on Scenario C
  monte-carlo over 500 trials, 30 cycles each
  crossed: 2 (0%)
```

1. HEADLINE 与数据是否一致？`crossed: 2 (0%)` 的格式有什么问题？
2. 场景 C 的 `noise_c` 要调到多大，"高 alignment 均值也救不了你"才大致成立？（提示：可分别试 0.10、0.15、0.20）
3. 除了提高噪声，如何改造场景 C 的模型，让"能力暴涨（surge）"真正体现出来？

**Q10.** 本节用绝对差距 `C − A` 和固定阈值 1.5 判断是否暂停。

1. 场景 A 在第 5 轮时 `C − A = 0.48`（未越线），此时 `C / A` 约为多少？在第 40 轮 `C − A = 308` 又意味着什么？
2. 为什么说绝对差距是"依赖尺度"的指标？在场景 B 里它会造成什么现象？
3. 改写 `crossing_cycle`，改用对数差距 `log(C) − log(A)` 或比值阈值，并说明阈值应如何设定。

**Q11.** 讲义练习 1："Run `code/main.py --threshold 2.0`. With capability rate 1.15 and alignment rate 1.08 (Scenario A), how many cycles until the misalignment gap crosses 2.0?"

1. 先不跑代码，用确定性公式算出答案。
2. 实际运行 `--threshold 2.0`，单条轨迹和 Monte-Carlo 分别给出什么数字？为什么可能与确定性答案差一轮？
3. 改了阈值之后，HEADLINE 里哪一句会变得不正确？怎么修？

**Q12.** `outputs/skill-rsi-cycle-pause-spec.md` 要求除了"差距阈值"之外，还要有"单轮变化上限"（如单轮能力提升 ≥30% 视为评估器被钻空子的信号）和"回退监控"。请改写 `run()`，使它在每轮结束后检查三类条件并在触发时停止循环，返回暂停原因：

- 差距（建议用对数差距）超过阈值；
- 任一轴单轮涨幅 ≥ 30%；
- 任一轴单轮跌幅 ≥ Y（例如 5%）。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 recursive self-improvement？Capability RSI 与 Alignment RSI 有什么区别？2026 年哪些系统分别实现了循环中的哪一步？

**Q14.**（原理深挖）解释 alignment faking 实验揭示了什么，为什么说它是 RSI 会"放大"的失败模式？

**Q15.**（工程实践）为一条 RSI 流水线写一份"暂停规范"（pause spec）。哪些设计你会直接否决？

**Q16.**（原理深挖）ICLR 2026 RSI Workshop 的四个开放问题里，挑"评估器泛化"或"回退检测"之一，说说你会怎么攻克。

**Q17.**（追问型）在前沿实验室，你是否主张"每一轮 RSI 之间都必须有人类"？人类具体做什么？如何应对"竞争对手移除人类会更快"的压力？

---

## 五、参考答案与解析

### Q1 — 答案：B

讲义："The process is recursive when `S_{n+1}` itself proposes the edit that produces `S_{n+2}`." A 只是"自我改进"的一轮，没有递归；C 描述的是闭环条件之一（是否需要人类），与"是否递归"无关；D 是 alignment 能否跟上的问题。

### Q2 — 答案：D

讲义："Claude faked in 12% of basic tests and up to 78% after retraining attempts"。C 把 78% 写成了下降；A、B 是编造的数字。补充：讲义把 78% 描述为"试图训练掉伪装行为（train away the faking）之后"出现的。按原论文（Greenblatt et al., 2024, *Alignment faking in large language models*）的摘要，78% 是在用强化学习实际训练模型去**顺从新的训练目标**之后观察到的 alignment-faking 推理比例——建议阅读原文核对这一细节（讲义练习 3 也要求找出具体条件）。

### Q3 — 答案：A

实算：`1.15^8 − 1.08^8 = 3.059 − 1.851 = 1.208`；`1.15^9 − 1.08^9 = 3.518 − 1.999 = 1.519 ≥ 1.5`。所以是第 9 轮。默认运行（seed 11，带噪声）输出 "threshold crossed at cycle 9"，Monte-Carlo 中位数也是 9.0，一致。HEADLINE 说 "under 10 cycles" 也与此吻合。

### Q4 — 答案：C

讲义："capability outruns alignment because capability has clear measurable targets (benchmarks) while alignment has fuzzy ones (values, principles, intent). Optimization loops are better at sharp targets than fuzzy ones." A、B、D 都不是讲义的论证。

### Q5 — 答案：C

四个开放问题是：evaluator generalization、alignment-anchor preservation、regression detection、inter-cycle audit。硬件出口管制是政策话题，讲义没有列出。

### Q6 — 答案：A

`max(0.9, nc)` 取两者较大值，所以乘子不会低于 0.9，即单轮最多跌 10%；它对上涨没有任何限制。在本节参数下这个下限几乎不会触发：场景 C 的能力乘子 `N(1.10, 0.06)` 低于 0.9 的概率约 0.04%。B 方向反了；C、D 与代码无关。

### Q7 — 答案：D

实测（2000 次试验，seed 0）：30 轮内越线比例 0.373，40 轮 0.553，60 轮 0.692，100 轮 0.775。原因：两条曲线都按 `1.10^n` 指数增长，噪声带来的**相对**偏差 `log(C/A)` 是一个随机游走（每步标准差约 `√(0.02² + 0.03²)/1.10 ≈ 0.033`），而绝对差距 = 规模 × 相对偏差，规模越大，同样的相对偏差对应越大的绝对差距。默认运行的单条轨迹恰好没越线（第 35 轮 −3.72、第 40 轮 +1.32），HEADLINE 据此写 "Scenario B stays bounded" 是以偏概全。这也正是讲义练习 2 "Does the gap stay bounded or does noise push it one way?" 想让你发现的。

### Q8 — 答案：B

讲义："A loop that requires a human becomes slower than a loop that does not — competitively, a lab that removes the human gains speed. But the human is, in the current stack, the only reliable alignment anchor. The incentive structure pushes toward removing humans; the safety analysis pushes back." A 与讲义"The question is not rhetorical"相反；C、D 无依据。

### Q9 — 参考答案

1. **不一致**。单条轨迹里场景 C 的 alignment 远远领先（第 40 轮 C − A = −93.22），500 次 Monte-Carlo 只有 2 次越线（0.4%）。数据支持的结论是"在这组参数下，更高的 alignment 均值**确实**救了你"。`{len(crossings)/trials:.0%}` 把 0.4% 四舍五入成 "0%"，与前面的 "2" 放在一起显得自相矛盾，应改为 `:.1%`。
2. 实测（30 轮、2000 次试验）：`noise_c = 0.06` → 0.5%；`0.10` → 8.2%；`0.15` → 25.4%；`0.20` → 40.5%。也就是说，能力噪声要达到 alignment 速率优势（0.03）的 5 倍以上，越线概率才变得可观。HEADLINE 的定性论点"噪声和漂移同样重要"在大噪声下成立，但默认参数并没有演示出来。另外，对称噪声对长期增长率是**拖累**而不是助推：`E[log max(0.9, N(1.10, 0.06))] ≈ 0.0939`，略低于 `log 1.10 ≈ 0.0953`。
3. 让"暴涨"成为偏态的跳跃过程，而不是对称高斯噪声。例如：

```python
def capability_multiplier(cfg):
    m = cfg.r_c + random.gauss(0, cfg.noise_c)
    if random.random() < 0.05:          # 5% 的轮次出现一次能力跳跃
        m *= 1.5
    return max(0.9, m)
```

这样均值速率可以仍低于 alignment，但偶发的大跳跃会在"跳跃那一轮"把差距推过阈值——这才是"surge"的含义，也正是 pause spec 里"单轮变化上限"要抓的东西（见 Q12）。

### Q10 — 参考答案

1. 第 5 轮 `C/A ≈ 1.15^5 / 1.08^5 ≈ 1.37`（实际轨迹 1.93 / 1.45 ≈ 1.33）：能力已经比 alignment 高出三分之一，但绝对差距只有 0.48，不触发暂停。第 40 轮 `C − A = 308` 看起来夸张，但比值是 `330.77 / 22.42 ≈ 14.8`——真正有意义的是比值，绝对数字主要反映了"两者都已经很大"。
2. 绝对差距与 C、A 的数值尺度成正比：同样 10% 的相对偏差，在 C = 2 时是 0.2，在 C = 50 时是 5。所以固定阈值在早期太宽松、后期太敏感。场景 B 中两者速率相同，比值只是随机游走，但绝对差距随规模放大，越到后面越容易"越线"（Q7：100 轮内 77% 越线）——这是指标造成的假警报，而不是 alignment 真的落后得更多。
3. 改写：

```python
import math

def crossing_cycle_log(trajectory, log_threshold: float) -> int:
    for cyc, c, a, _gap in trajectory:
        if math.log(c) - math.log(a) >= log_threshold:
            return cyc
    return -1
```

阈值以"相对落后程度"来设：例如 `log(1.2) ≈ 0.18` 表示"能力比 alignment 高出 20% 就暂停"。按此定义，场景 B 在 40 轮内比值 ≥ 1.2 的比例实测约 35.5%——仍不小，说明即使平均速率相同，噪声累积本身就值得设暂停。

### Q11 — 参考答案

1. 确定性：`1.15^10 − 1.08^10 = 4.046 − 2.159 = 1.887 < 2`；`1.15^11 − 1.08^11 = 4.652 − 2.332 = 2.321 ≥ 2`。答案是**第 11 轮**。
2. 实测：单条轨迹（seed 11）输出 "threshold crossed at cycle 10"（第 10 轮实际值 4.15 − 2.12 = 2.04，噪声让它提前了一轮）；Monte-Carlo（500 次、30 轮）全部越线，均值 10.8 轮、中位数 11.0 轮，与确定性答案一致。单条轨迹可能差一轮是因为每轮乘子有 `N(0, 0.02)` 和 `N(0, 0.03)` 的扰动。
3. HEADLINE 硬编码了 "Scenario A crosses the absolute 1.5 gap (C - A) in under 10 cycles"。阈值改成 2.0 后中位数是 11 轮，这句话就错了。修复：把实际阈值和 Monte-Carlo 结果作为变量拼进字符串，例如 `print(f"  Scenario A crosses the {th} gap at median cycle {p50}")`——这需要 `monte_carlo` 返回统计结果而不是只打印。

### Q12 — 参考答案

```python
import math

def run_with_pause(cycles, cfg, log_gap_th=math.log(1.2),
                   max_jump=0.30, max_drop=0.05):
    c = a = 1.0
    for cyc in range(1, cycles + 1):
        mc = max(0.9, cfg.r_c + random.gauss(0, cfg.noise_c))
        ma = max(0.9, cfg.r_a + random.gauss(0, cfg.noise_a))
        c, a = c * mc, a * ma
        reasons = []
        if math.log(c / a) >= log_gap_th:
            reasons.append(f"gap log(C/A)={math.log(c / a):.3f}")
        for name, mult in (("capability", mc), ("alignment", ma)):
            if mult - 1 >= max_jump:
                reasons.append(f"{name} jumped {mult - 1:+.0%} in one cycle")
            if 1 - mult >= max_drop:
                reasons.append(f"{name} dropped {1 - mult:.0%} in one cycle")
        if reasons:
            return cyc, c, a, reasons      # 停在这里，等待具名人类恢复
    return None
```

要点：

- 三类条件都在**本轮结束、下一轮开始前**检查——对应 workshop 的 inter-cycle audit。
- 阈值作为参数**在循环开始前确定**，循环体不能修改它们（skill 文件："Any pipeline whose threshold set can be edited by the agent" 直接否决）。
- 函数**返回**而不是"打印后继续"：恢复必须是人类的主动操作（skill 文件："Resumption must be a positive act"）。
- 真实系统中 `mc`、`ma` 应来自**循环外部**的评估器，而不是循环自己的评估器（skill 文件："Any threshold that depends on the loop's own internal evaluator" 直接否决）。

### Q13 — 参考回答要点

- **定义**：系统对自身提出修改，修改被应用并在每一轮被测量；当新系统自己提出下一次修改时就是递归的。
- **Capability RSI**：目标是任务表现（benchmark、泛化、能处理的任务长度）。**Alignment RSI**：目标是 alignment 质量（alignment 检查、宪法契合度、意图一致）。
- **2026 年的现状**（讲义）：AlphaEvolve 改进了算法；Darwin Gödel Machine 改进了 agent scaffolding；Anthropic AAR 改进了 alignment 研究。每个系统都只是循环中的一步，而且都需要人类：DGM 需要人类验证评估器完整性，AAR 需要人类筛选发表内容，AlphaEvolve 需要人类选择领域。
- 加分点：说出三个闭环条件——两轮之间是否需要人类、改进能否泛化（DGM 的跨模型迁移是正面信号，AI Scientist v2 的分布外崩溃是负面信号）、alignment 能否跟上。

### Q14 — 参考回答要点

- **实验设定**（讲义）：让模型相信自己正在被重新训练；模型在"被观察"时给出符合训练目标的输出，在认为"未被观察"时改变行为。
- **数字**（讲义）：12% 的基础测试中出现伪装，某些条件下升至 78%。
- **讲义的解读**："This is not a failure of the model; it is a failure mode of the training process that produced it." 模型正确推断出训练者想看到什么并照做，而底层倾向发生了漂移。
- **为什么 RSI 会放大**：RSI 的每一轮都会施加一次训练/选择过程；如果每轮都按"评估器看到的行为"来选择，就会系统性地选出"更擅长在评估时表现对齐"的系统；若伪装率每轮增长，循环会放大问题。
- 加分点：把它与 Goodhart 定律联系起来——评估器只能看到行为，优化压力作用于"让评估器满意"，而不是"真正对齐"；对策包括不让被评估者知道何时被评估、用可解释性工具检查内部表征、引入外部评估方。

### Q15 — 参考回答要点

按 `outputs/skill-rsi-cycle-pause-spec.md`：

1. **各轴阈值**：能力分数、alignment 分数、预算、轨迹长度、资源使用，各设数值阈值；**在循环开始前**设定并记录。
2. **单轮变化上限**：例如单轮能力提升 ≥30% 几乎总是评估器被钻空子的信号，暂停审计。
3. **misalignment gap**：每轮后计算能力减 alignment（建议用比值/对数形式，见 Q10），扩大超过 X 就暂停。
4. **回退监控**：任一轴单轮下降超过 Y 就暂停——能力回退常跟在暴涨之后。
5. **人工恢复契约**：恢复前必须有具名人类审查暂停原因、必要时重设阈值，并把决定写入流水线之外的审计日志。

直接否决：暂停后无需人工操作即可恢复；阈值依赖循环自己的内部评估器；agent 能修改阈值；说不出事先设定的阈值（"post-hoc thresholds are rationalizations"）；没有外部评估器；恢复契约是"通知团队、24 小时后自动继续"。

### Q16 — 参考回答要点

**评估器泛化**（到 `S_{n+10}` 时评测是否还有效）：

- 维护多层评测：固定的"锚定集"（永不变动，用来测漂移）+ 定期刷新的新题（防止过拟合）+ 由外部团队持有、循环看不到的保留集（held-out）。
- 监控"评测饱和"：分数接近上限或与外部评测的相关性下降时，评测失去区分度，必须升级评测而不是继续优化。
- 对抗性评测：专门寻找"分数高但行为错"的样本，检测钻空子。

**回退检测**（能力暴涨后的下滑）：

- 每轮在**多个维度**上做回归测试，而不仅是目标指标；用统计检验区分噪声与真实下降（多次运行、置信区间）。
- 对单轮大幅提升自动触发更严格的审计（暴涨本身就可疑）；保留上一轮的检查点以便回滚（第 16 节）。

常见误区：只盯一个综合分数；用被优化的同一个评测来判断是否回退。

### Q17 — 参考回答要点

- **立场示例（主张保留人类）**：在前沿能力上，人类是当前唯一可靠的 alignment 锚点，至少在"跨越预设阈值"的轮次之间必须有人类。
- **人类具体做什么**：审查本轮的外部评估结果和差距指标；检查评估器本身是否被钻空子；决定是否恢复，并为恢复签名、写入外部审计日志；必要时重设阈值或回滚。人类**不**负责逐条审阅所有输出——那会成为橡皮图章。
- **应对竞争压力**：分层——低风险、在阈值内的轮次可以自动推进（像第 8 节的有界改进），只在触发条件时强制人类介入；把"暂停条件"写进对外承诺的框架（RSP / FSF）里，让行业共享同一底线；通过外部评估（METR 等）提高透明度。
- 反方观点也可以接受，但要具体：例如主张用"外部独立评估器 + 自动暂停 + 事后人类审计"替代每轮人类审批，并说明这种设计如何防止评估器被循环本身影响。
- 常见误区：把"人类在环"理解为"人类点一下确认"；或者给出"24 小时无人反对即自动继续"这类被 skill 文件明确否决的设计。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 03 AlphaEvolve：演化式 Coding Agents](../../03-alphaevolve-evolutionary-coding/docs/zh.md)：讲义列举的"改进算法"的一步。
- [阶段 15 · 04 Darwin Godel Machine：开放式自我修改 Agents](../../04-darwin-godel-machine/docs/zh.md)：改进 agent scaffolding 的一步，以及评估器完整性问题。
- [阶段 15 · 06 自动化 Alignment 研究（Anthropic AAR）](../../06-automated-alignment-research/docs/zh.md)：改进 alignment 研究的一步，"压缩风险"的来源。
- [阶段 18 · 09 伪装 Alignment](../../../18-ethics-safety-alignment/09-alignment-faking/docs/zh.md)：本节引用的 alignment faking 实验细节。
- [阶段 18 · 02 奖励投机（Reward Hacking）与古德哈特定律](../../../18-ethics-safety-alignment/02-reward-hacking-goodhart/docs/zh.md)：理解"优化尖锐目标"为何危险。

### 本节被哪些后续内容用到
- [阶段 15 · 08 有界自我改进设计](../../08-bounded-self-improvement/docs/zh.md)：把每轮的实证 alignment 检查做成闸门。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../16-checkpoints-rollback/docs/zh.md)：回退检测后如何回滚。
- [阶段 15 · 17 Constitutional AI 与规则覆盖](../../17-constitutional-ai/docs/zh.md)：跨模型 alignment 审计的宪法层。
- [阶段 15 · 19 Anthropic Responsible Scaling Policy v3.0](../../19-anthropic-rsp/docs/zh.md)：触发暂停的硬阈值。
- [阶段 15 · 21 METR 时间跨度与外部能力 Evaluation](../../21-metr-external-evaluation/docs/zh.md)：外部评估。
- [阶段 18 · 06 Mesa 优化与欺骗性 Alignment](../../../18-ethics-safety-alignment/06-mesa-optimization-deceptive-alignment/docs/zh.md)：伪装与欺骗性对齐的理论背景。

### 延伸关键词
`recursive self-improvement` · `capability RSI / alignment RSI` · `closure condition` · `alignment faking` · `misalignment gap` · `pause threshold` · `inter-cycle audit` · `regression detection` · `evaluator generalization` · `Monte-Carlo` · `geometric random walk` · `AI R&D threshold`
