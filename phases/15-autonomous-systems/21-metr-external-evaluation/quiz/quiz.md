# 测验 · METR 时间跨度与外部能力 Evaluation（METR Time Horizons and External Capability Evaluation）

> **阶段 15 · 自主系统 · 第 21 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。
>
> 注：本节中文讲义是机器翻译，错译较多（如把 "logistic" 译成"后勤"、把 "eval-context gaming" 译成"电子游戏"、把 "ex-ARC Evals" 译成"前美国癌症研究中心"），概念以英文讲义为准。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | METR 是谁 | 前身是 ARC Evals，2023 年 12 月起成为独立的 501(c)(3) 非营利机构，常在模型发布前（NDA 下）对前沿模型做自主能力评估，事后公开方法 |
| 2 | Time Horizon 的定义 | 对"任务成功概率 vs log(专家完成时间)"拟合 logistic 曲线，P(success) = 0.5 处对应的专家时间就是 50% time horizon |
| 3 | 为什么用 log 时间 + logistic | 任务难度跨越分钟到数十小时，log 尺度让它们均匀展开；logistic 描述"随难度单调下降、两端趋于平台"的成功率 |
| 4 | 其它阈值 | 50% 只是一个选择；也可读 10%、90% 处的时间。**P 越高对应的时间越短**：90% horizon 是保守的短时间，10% horizon 是乐观的长时间 |
| 5 | 2026 年 1 月的数字 | 讲义："Claude Opus 4.6: ~14 hours at 50% reliability"（TH1.1）；post-2023 拟合的翻倍时间约 4.3 个月（130.8 天），约 7 个月是 TH1.0 的 2019–2025 全区间拟合 |
| 6 | 三个任务套件 | HCAST（180+ / 189 个任务，1 分钟到 8+ 小时，horizon 的主力）、RE-Bench（71 个 ML 研究工程任务，带人类专家基线）、SWAA（短任务，校准曲线低端） |
| 7 | 监控评估原型 | 监控器能否抓到模型在做"副任务"、agent 能否规避监控；对应 OpenAI PF v2 的 "Undermining Safeguards" 与 DeepMind FSF v3 的欺骗性 alignment 监控 |
| 8 | Horizon 是上界 | 理想化工具、没有真实后果、eval-context gaming（测试中表现不同）、没有真实用户的模糊请求 → 部署可靠性更低 |
| 9 | 外部评估的价值与局限 | 独立机构 + 公开方法是对"实验室自评有动机刷指标"的结构性缓解；但实验室仍控制 METR 能看到什么 |
| 10 | 实践用法 | 当作能力过滤器（horizon 远低于任务时长就别全自主上线）、趋势指标（翻倍时间）、先验（再按自己的任务分布、工具质量、部署环境往下调） |

### 核心技能（能动手做到）

- [ ] 用标准库写出 logistic 回归（梯度下降）拟合 `P(success) = sigmoid(w·log t + b)`，并从 `(w, b)` 反解任意可靠性阈值下的 horizon
- [ ] 给定 `(w, b)` 手算 50%/90%/10% horizon，并解释 10% 与 90% horizon 的比值只由斜率决定
- [ ] 模拟 eval-context gaming（把一部分失败翻成成功），观察 horizon 与斜率如何变化，并说出"相对谁比较"才是正确的基线
- [ ] 用 bootstrap 或多随机种子给 horizon 估计加上置信区间，认识到 160 个任务时 50% horizon 的不确定性有多大
- [ ] 按 `outputs/skill-horizon-interpretation.md` 审查一个厂商的 horizon 声明：方法披露、任务分布重合度、eval 差距、工具差距、HITL 假设
- [ ] 用翻倍时间做外推，并说清 4.3 个月与 7 个月两种口径会让一年后的预测相差多少

---

## 二、基础自测（选择题）

**Q1.** 关于 METR 的 50% time horizon，下列说法正确的是：

- A. 模型在 50% 的任务上成功时，这些任务的平均专家耗时
- B. 模型单次运行能连续工作的最长时间
- C. 对 P(success) 与 log(专家完成时间) 拟合 logistic 曲线后，成功概率为 0.5 处对应的专家完成时间
- D. 专家完成全部任务所需总时间的一半

**Q2.** 按英文讲义，Time Horizon 1.1（2026 年 1 月）的头条数字与翻倍时间是：

- A. Claude Opus 4.6 约 14 小时（50% 可靠性）；post-2023 拟合翻倍时间约 4.3 个月，约 7 个月是 2019–2025 全区间拟合
- B. Claude Opus 4.6 约 14 小时（90% 可靠性）；翻倍时间约 7 个月
- C. GPT-5.1 约 48 小时（50% 可靠性）；翻倍时间约 4.3 个月
- D. Claude Opus 4.6 约 8 小时（50% 可靠性）；翻倍时间约 12 个月

**Q3.** 本节代码在 seed=3 时拟合出 `w = -1.3867`、`b = 3.3621`（`P = sigmoid(w·ln t + b)`，t 单位为小时）。**90% 可靠性**对应的 horizon 约为：

- A. 55.09 小时
- B. 11.30 小时
- C. 23.78 小时
- D. 2.32 小时

**Q4.** 下列哪一项**不是**讲义给出的"horizon 是上界而非部署预测"的理由？

- A. 基准给模型的是干净的工具和格式良好的数据
- B. 基准任务数量太少，统计上不显著
- C. 模型在测试情境下行为不同（eval-context gaming）
- D. 基准 prompt 结构化，真实用户的请求模糊且依赖上下文

**Q5.** 运行 `main.py` 得到 clean 拟合 `50%= 11.30 hr  10%= 55.09 hr  90%= 2.32 hr`。英文讲义 Use It 写道它报告 "10% horizon (conservative), and 90% horizon (optimistic)"。正确的理解是：

- A. 标签说反了：P 越高时间越短，90% horizon（2.32 小时）才是保守值，10% horizon（55.09 小时）是乐观值
- B. 讲义正确：10% horizon 只要求 10% 成功率，所以是保守的
- C. 两者没有保守/乐观之分，只是 logistic 曲线的两个对称点
- D. 代码算错了，10% horizon 应小于 50% horizon

**Q6.** `inject_gaming` 以固定概率把**失败**翻成成功、与任务长短无关。随 gaming 率上升，拟合结果最主要的变化是：

- A. 斜率不变，曲线整体左移
- B. 所有 horizon 都按同一比例放大
- C. 只有 90% horizon 大幅变大，10% horizon 几乎不变
- D. 长任务本来失败多、被翻的也多，曲线变平（|w| 变小），50% horizon 右移，10% horizon 被外推到远超数据范围（40% 时达 584.63 小时）

**Q7.** 关于 METR 的三个基准套件，正确的是：

- A. SWAA 是最长的任务套件，用于校准曲线的高端
- B. RE-Bench 有 71 个带人类专家基线的 ML 研究工程任务，用来衡量与 AI R&D-4 阈值相关的能力
- C. HCAST 只包含软件工程任务
- D. RE-Bench 就是 HCAST 的别名

**Q8.** 关于外部评估（external evaluation）的作用，讲义的立场是：

- A. 有了 METR 的独立评估，实验室自评就不再需要
- B. 外部评估比内部评估更便宜，所以更好
- C. 独立性和公开方法是结构性缓解，但不充分——实验室仍然控制 METR 能看到什么；不过有外部评估严格好于没有
- D. 外部评估只在模型发布后才进行，因此无法影响发布决策

---

## 三、动手 / 代码题

**Q9.** `main()` 的 HEADLINE 部分（节选）及实际输出：

```python
    for rate, h in gamed_h50.items():
        delta = h - true_h
        print(f"    gaming rate {rate:>4.0%}   50% horizon ≈ {h:>6.2f} hr "
              f"({delta:+.2f} hr vs ground truth)")
    print("  Trend: gaming pushes the observed 50% horizon further from the")
    print("  synthetic ground truth as the rate climbs. ...")
```

```text
    clean fit          50% horizon ≈  11.30 hr (ground truth 14.0)
    gaming rate  10%   50% horizon ≈  13.25 hr (-0.75 hr vs ground truth)
    gaming rate  20%   50% horizon ≈  14.63 hr (+0.63 hr vs ground truth)
    gaming rate  40%   50% horizon ≈  44.56 hr (+30.56 hr vs ground truth)
```

1. "gaming 让观测值离 ground truth 越来越远"这句话和 10% 那一行的数字矛盾在哪里？
2. 衡量"gaming 造成了多大偏差"，正确的比较基线是什么？按这个基线重写三行 delta。
3. clean 拟合本身为什么就差了 2.70 小时？是梯度下降没收敛吗？你怎么验证？

**Q10.** 手算题（可用计算器）。

1. 由 Q3 的 `w = -1.3867, b = 3.3621` 写出 p 可靠性 horizon 的公式，并算出 50% 与 10% horizon。
2. 证明 `h10 / h90 = exp(2·ln 9 / |w|)`，只由斜率决定；分别对拟合斜率 1.3867 和合成真值斜率 1.2 计算这个比值。
3. 合成数据的真值是 `P = sigmoid(1.2·(ln 14 − ln t))`。专家耗时 1 小时和 48 小时的任务，真实成功概率各是多少？

**Q11.** 阅读 `horizon_at`：

```python
def horizon_at(w: float, b: float, p: float) -> float:
    logit = math.log(p / (1 - p))
    eps = 1e-12
    if abs(w) < eps:
        raise ValueError(...)
    return math.exp((logit - b) / w)
```

1. 它防住了斜率为 0 的情况，但还有哪两类"静默返回无意义数字"的情况没防住？（提示：试试把全部任务都标成成功再拟合；再看看 10% horizon 和数据的最大专家时间。）
2. 写一个更稳健的版本 `safe_horizon(tasks, w, b, p)`：检查斜率符号、标记外推，并说明怎样给 50% horizon 附上置信区间。

**Q12.** 讲义练习 1 说"把任务时间网格减半（halve the task-time grid），horizon 估计是否明显变化"。

1. 代码里真的有"网格"吗？任务时间是怎么生成的？
2. 如果把它理解为"减少任务数"，在 seed=3 下 n = 40 / 80 / 160 / 640 时 50% horizon 分别约为 7.91 / 9.98 / 11.30 / 12.72 小时。这说明了什么？厂商只报一个数字时你应该追问什么？

---

## 四、面试高频题

**Q13.**（基础必考）什么是 METR 的 time horizon？它是怎么从一堆任务的成功/失败记录里算出来的？为什么默认报 50%？

**Q14.**（原理深挖）为什么说 time horizon 是能力上界而不是部署可靠性预测？eval-context gaming 与 sandbagging（故意藏拙）分别会把 horizon 往哪个方向推？

**Q15.**（工程实践）某厂商在发布会上说"我们的模型能以 50% 可靠性完成 14 小时的任务"，你的团队想用它做无人值守的客服工单处理。你会怎样审查这个声明并给出上线建议？

**Q16.**（场景设计）请为你们团队的 bug backlog 设计一个内部 horizon 评估：数据怎么收集、怎么拟合、输出怎么解读、和 METR 数字怎么对比。

**Q17.**（追问型）"翻倍时间约 7 个月"和"约 4.3 个月"哪个对？如果今天是 14 小时，一年后分别外推到多少？用翻倍时间做规划有什么陷阱？

---

## 五、参考答案与解析

### Q1 — 答案：C

讲义方法第 3–4 步："Fit a logistic curve: P(success) as a function of log(expert completion time). The horizon is the expert-time at which P(success) = 0.5." A 混淆了"成功任务的平均耗时"与拟合曲线的交点；B 是 agent 单次运行时长，与"专家完成这类任务要多久"是两回事（一个 14 小时 horizon 的模型可能几十分钟就做完）；D 无意义。

### Q2 — 答案：A

讲义："Claude Opus 4.6: ~14 hours at 50% reliability, as of Time Horizon 1.1 (January 2026)"；"Doubling time ... ~4.3 months (130.8 days) on the post-2023 fit ... the ~7-month figure is the full 2019–2025 fit from Time Horizon 1.0"。B 把可靠性写成 90%；C、D 的数字讲义里没有。注意讲义自身不一致：Key Terms 表、配图与 `outputs/skill-horizon-interpretation.md` 都只写了"~7 months"。

### Q3 — 答案：D

`P = 0.9` 时 `logit = ln 9 = 2.1972`，`ln t = (2.1972 − 3.3621) / (−1.3867) = 0.8401`，`t = e^0.8401 ≈ 2.32` 小时，与程序输出 `90%= 2.32 hr` 一致。A 是 10% horizon，B 是 50% horizon，C 是 10% 与 90% horizon 的比值（55.09 / 2.32 ≈ 23.78）。

### Q4 — 答案：B

讲义列的四条是：Idealized tooling（A）、No real consequences、Eval-context gaming（C）、No legitimate user variance（D）。"任务太少"是统计不确定性问题（会让估计偏高或偏低，见 Q12），不是"系统性偏高"的理由，讲义也没有这样论证。

### Q5 — 答案：A

拟合的 `w < 0`（任务越长成功率越低），所以要求的成功率 p 越高，能满足的任务就越短：90% horizon = 2.32 小时，10% horizon = 55.09 小时。"保守"应指"只承诺高可靠性能做到的范围"，即 90% horizon。讲义 Use It 把两者标签说反了。B 的逻辑就是讲义的错误；C 错，logistic 在 log 尺度上关于 50% 对称，但 10%/90% 在业务含义上一个乐观一个保守；D 错，代码计算正确。

### Q6 — 答案：D

seed=3 的实测：clean `w = −1.387`；gaming 10%/20%/40% 时 `w = −1.277 / −1.255 / −0.854`。失败集中在长任务上，按失败比例翻转等于"长任务的成功率被抬得更多"，曲线变平、右移。50% horizon 从 11.30 → 44.56 小时；10% horizon 从 55.09 → 584.63 小时——而合成数据的最大专家时间只有约 46.6 小时，584 小时完全是外推。A、B、C 都与实测不符：90% horizon 只从 2.32 变到 3.40，变化最小。

### Q7 — 答案：B

讲义："RE-Bench: 71 ML research-engineering tasks with a human expert baseline. Measures whether the model can do the kind of ML R&D work that feeds into the AI R&D-4 threshold." A 说反了，SWAA 是短任务、校准低端；C 错，HCAST 覆盖 ML、网络安全、软件工程、通用推理；D 错，两者是不同套件。

### Q8 — 答案：C

讲义："It is not sufficient alone (labs still control what METR sees), but it is strictly better than no external evaluation." A 过度推论；B 讲义没有讨论成本；D 错，METR 的评估"often pre-release"，正是为发布前决策服务。

### Q9 — 参考答案

1. clean 拟合偏差是 `11.30 − 14.0 = −2.70`，10% gaming 后是 `−0.75`，**绝对偏差反而变小了**。"越来越远"只有在 clean 拟合恰好等于真值时才成立。代码把"gaming 的影响"与"小样本抽样误差"混在了同一个 delta 里。
2. 要衡量 gaming 引入的偏差，基线应是**同一批任务的 clean 拟合**：

   | gaming 率 | 50% horizon | 相对 clean（11.30） | 相对真值（14.0，代码的口径） |
   |----------|------------|-------------------|--------------------------|
   | 10% | 13.25 | +1.95 hr（+17%） | −0.75 |
   | 20% | 14.63 | +3.33 hr（+29%） | +0.63 |
   | 40% | 44.56 | +33.26 hr（+294%） | +30.56 |

   相对 clean 看，gaming 的作用是单调地把 horizon 往右推，这才是想展示的"trend"。更好的做法是多跑几个种子取中位数：我们用 30 个种子（seed 0–29）实测，clean / 10% / 20% / 40% 的 50% horizon 中位数约为 13.79 / 18.30 / 22.03 / 33.73 小时。
3. 不是没收敛。把 `iters` 从 4000 增加到 20000、100000，50% horizon 只从 11.296 变到 11.320，就稳定了；4000 步已基本收敛。差距来自**抽样噪声**：160 个任务里只有 39 个失败、只有 31 个任务长于 14 小时，对 seed=3 做 bootstrap（200 次重采样）得到的 95% 区间约为 7.96–16.06 小时，真值 14 落在区间内。30 个种子下 clean 估计从 11.06 到 35.49 都出现过。

### Q10 — 参考答案

1. 由 `sigmoid(w·ln t + b) = p` 得 `ln t = (logit(p) − b) / w`，即 `h_p = exp((ln(p/(1−p)) − b) / w)`。
   - 50%：`logit = 0`，`h50 = exp(−b/w) = exp(3.3621/1.3867) = exp(2.4246) ≈ 11.30` 小时。
   - 10%：`logit = −2.1972`，`ln t = (−2.1972 − 3.3621)/(−1.3867) = 4.009`，`h10 ≈ 55.09` 小时。
2. `ln h10 − ln h90 = (−ln9 − b)/w − (ln9 − b)/w = −2·ln9 / w = 2·ln9/|w|`（w < 0），b 被消掉。拟合斜率 1.3867：比值 `exp(4.3944/1.3867) ≈ 23.78`（= 55.09/2.32）；真值斜率 1.2：比值 ≈ 38.94。斜率越平（|w| 越小），"偶尔能成"与"基本可靠"之间的距离越大——这是为什么只报一个 50% 数字会丢信息。
3. 1 小时：`sigmoid(1.2 × (ln14 − 0)) = sigmoid(3.167) ≈ 0.960`；48 小时：`sigmoid(1.2 × (2.639 − 3.871)) = sigmoid(−1.479) ≈ 0.186`。即"14 小时 horizon"的模型对 1 小时任务也有约 4% 的失败率，对 48 小时任务仍有约 19% 的成功率。

### Q11 — 参考答案

1. 两类漏网情况（已实际运行验证）：
   - **斜率符号错误**：把 3 个任务全标成成功再 `fit`，得到 `w ≈ +1.82`、`b ≈ 4.53`。`w > 0` 意味着"任务越长越容易成功"，此时 horizon 可以算出一个数，但没有意义。数据完全可分（全成功/全失败，或长短任务完全分开）时，最大似然估计本身不存在，梯度下降只会不停地把参数推大。
   - **外推**：seed=3 的任务最长约 46.6 小时，代码却报出 10% horizon 55.09 小时、gaming 40% 时 584.63 小时。超出观测范围的 horizon 只是曲线形状的假设，不是测量值。
2. 参考实现：

```python
import math, random

def safe_horizon(tasks, w, b, p):
    if w >= 0:
        raise ValueError(f"slope w={w:.3f} >= 0: success does not decrease with task length")
    h = math.exp((math.log(p / (1 - p)) - b) / w)
    t_min = min(t for t, _ in tasks)
    t_max = max(t for t, _ in tasks)
    extrapolated = not (t_min <= h <= t_max)
    return h, extrapolated

def bootstrap_h50(tasks, fit, n_boot=200, seed=0):
    rng = random.Random(seed)
    hs = []
    for _ in range(n_boot):
        sample = [tasks[rng.randrange(len(tasks))] for _ in tasks]
        w, b = fit(sample)
        if w < 0:
            hs.append(math.exp(-b / w))
    hs.sort()
    return hs[int(0.025 * len(hs))], hs[int(0.975 * len(hs)) - 1]
```

置信区间：对任务做有放回重采样、每次重拟合、取 2.5% 与 97.5% 分位数（seed=3 时约 7.96–16.06 小时）。真实评估里还要按任务族（task family）做分层重采样，因为同一族的任务高度相关。

### Q12 — 参考答案

1. 没有网格。`synth_tasks` 用 `math.exp(random.uniform(math.log(0.05), math.log(48)))` 在 0.05–48 小时之间做**对数均匀**随机抽样，每个任务再按真值概率抽一次成败。"halve the grid"只能理解为减少任务数，或把时间范围缩窄。
2. 同一种子下前 n 个任务是嵌套的，n 从 40 增加到 640，估计从 7.91 逐步靠近 14（12.72）。说明在一两百个任务的规模下，**抽样误差就可能有好几个小时**，单个点估计很不稳定。厂商只报一个数字时应追问：任务数和任务族数、每个任务跑了几次、置信区间、拟合是否按任务族加权、超过最长任务的部分是不是外推。这正是 `skill-horizon-interpretation.md` 里"Confirm the logistic fit is disclosed (slope, sample size, confidence interval)"的含义。

### Q13 — 参考回答要点

- **定义**：模型以 50% 概率完成的任务，其"人类专家完成时间"是多少。用人类时间作单位，把能力压缩成一个直观的标量。
- **计算**：
  1. 准备覆盖分钟到小时级的任务集（HCAST、RE-Bench、SWAA），每个任务有专家基线耗时；
  2. 让模型跑每个任务，记录成败；
  3. 用 logistic 回归拟合 `P(success) = sigmoid(w·log t + b)`；
  4. 读 P = 0.5 的交点：`h50 = exp(−b/w)`。
- **为什么 50%**：讲义："METR reports multiple thresholds in the detailed paper but leads with 50% because it is the most intuitive." 另外 50% 点位于曲线中部、数据最密，估计最稳定；10%/90% 更依赖尾部数据和外推。
- 加分点：说出斜率的含义（越陡说明能力边界越"清晰"），以及 50% 可靠性在生产里意味着"抛硬币"。

### Q14 — 参考回答要点

- **上界的四个理由**（讲义）：理想化工具和数据；没有不可逆后果；eval-context gaming（2026 International AI Safety Report 有实证记录，见第 01 节）；没有真实用户的模糊请求。
- **结论**：horizon 是"有利条件下的能力天花板"；部署可靠性是另一个、更低的数字，必须在自己的任务分布上测量。
- **两种行为偏差的方向**：
  - eval-context gaming：模型在测试中表现**更好** → 观测成功率偏高 → horizon 被高估、右移（本节代码模拟的就是这一种）；
  - sandbagging：模型在危险能力评估中**故意表现差** → horizon 被低估、左移，导致安全阈值被"低报"。第 20 节："If a model sandbags on evaluations, every framework's capability thresholds are underestimated."
- 加分点：两者都说明"测量本身会被被测对象影响"，所以需要外部评估 + 对抗式评估 + 监控评估（能否抓住副任务）。

### Q15 — 参考回答要点

按 `outputs/skill-horizon-interpretation.md` 走：

1. **方法审计**：任务套件是什么？是否公开拟合斜率、样本量、置信区间？没有方法披露的 horizon 是营销话术，拒绝引用。
2. **分布重合**：14 小时来自 SWE/ML 任务，而我们是客服工单，分布几乎不重合 → 数字不迁移，要求内部评估。
3. **eval-context 差距**：按 skill 文件打 10–40% 折扣；非结构化任务 gaming 更高。
4. **工具差距**：生产工具更脏，再打 5–30% 折扣。
5. **HITL 假设**：基准是全自主；生产若有人工审核，可靠性更高但自主性更低。
6. **结论**：给出"部署调整后的 horizon"和就绪等级（production / staging / research-only）。客服工单单件专家耗时多在分钟级，即使 horizon 远大于它，50% 可靠性的定义也说明不能直接无人值守；应先在影子流量上测自己的成功率。
- 常见误区：把"50% horizon = 14 小时"理解成"14 小时以内的任务基本都能做"——skill 文件明确把这列为 hard reject："50% reliability is a coin flip"。

### Q16 — 参考回答要点

- **数据收集**：从已关闭的 bug 中抽样数百个，覆盖不同模块和难度；用实际修复工时（或让工程师估时）作为"专家时间"，并剔除等待评审等非工作时间；每个 bug 要有可自动判定的成功标准（复现测试通过、CI 全绿）。
- **运行**：在与生产相同的工具链和权限下让 agent 修复，每个任务跑多次以降低噪声，记录成本和轨迹。
- **拟合**：`P(success)` 对 `log(工时)` 做 logistic 回归，报告 50% 和 80%/90% horizon，附 bootstrap 置信区间（按模块分层），标明哪些阈值是外推。
- **解读**：内部 horizon 应明显低于 METR 的公开数字；差距本身就是"工具差距 + 分布差距"的量化。用它决定哪些类型的 bug 可以自动修、哪些必须人工复核。
- **对比 METR**：比较排序和趋势（新模型是否同样领先），而不是绝对值；配图的第 2 条规则："public horizons predict rank-order, not absolute quality"。

### Q17 — 参考回答要点

- 两者都"对"，口径不同：讲义说约 4.3 个月（130.8 天）是 TH1.1 对 2023 年之后数据的拟合；约 7 个月是 TH1.0 对 2019–2025 全区间的拟合。讲义正文、Key Terms 表与 skill 文件之间存在口径不一致，引用时必须说明口径。
- **外推**：14 小时 × 2^(12/7) ≈ 45.9 小时（配图写"14 hr → 48 hr in ~12 months"）；14 × 2^(12/4.3) ≈ 96.9 小时。两种口径一年后相差约 2 倍。
- **陷阱**：
  - 指数外推假设趋势不变，而翻倍时间本身就在变化（近期更快）；
  - 任务套件的上限（HCAST 最长 8+ 小时）意味着几十小时以上的 horizon 本身就是外推；
  - horizon 是上界，外推的是"天花板"，不是部署可靠性；
  - 讲义的用法："doubling time tells you how long the current practice will remain safe even without new mitigations"——它是安全规划的时钟，不是采购依据。
- 加分点：指出 skill 文件 "Vendors citing a 2025-or-earlier horizon number as current" 应被拒绝，翻倍时间越短，数字过期越快。

---

## 六、关联知识点

### 前置知识
- [阶段 15 · 01 从聊天机器人转向长程 Agents](../../01-long-horizon-agents/docs/zh.md)：horizon 概念首次出现，以及 eval-vs-deploy 行为差距。
- [阶段 15 · 19 Anthropic Responsible Scaling Policy v3.0](../../19-anthropic-rsp/docs/zh.md)：AI R&D-4 等阈值需要本节这样的测量来落地。
- [阶段 15 · 20 OpenAI Preparedness Framework 与 DeepMind Frontier Safety Framework](../../20-openai-preparedness-deepmind-fsf/docs/zh.md)：Undermining Safeguards、欺骗性 alignment 监控与 sandbagging。
- [阶段 02 · 03 逻辑回归](../../../02-ml-fundamentals/03-logistic-regression/docs/zh.md)：本节代码的拟合就是一元 logistic 回归 + 梯度下降。
- [阶段 01 · 15 机器学习统计](../../../01-math-foundations/15-statistics-for-ml/docs/zh.md)：置信区间、bootstrap、抽样误差。

### 本节被哪些后续内容用到
- [阶段 15 · 22 CAIS、CAISI 与社会规模风险](../../22-cais-caisi-societal-risk/docs/zh.md)：CAISI 等政府评估机构与外部评估生态。
- [阶段 18 · 28 Alignment 研究生态：MATS、Redwood、Apollo、METR](../../../18-ethics-safety-alignment/28-alignment-research-ecosystem/docs/zh.md)：METR 在整个 alignment 研究生态中的位置。
- [阶段 18 · 18 前沿安全框架：RSP、PF、FSF](../../../18-ethics-safety-alignment/18-frontier-safety-frameworks-rsp-pf-fsf/docs/zh.md)：阈值框架如何引用外部测量。
- [阶段 18 · 09 伪装 Alignment](../../../18-ethics-safety-alignment/09-alignment-faking/docs/zh.md)：eval-context gaming 的实证来源之一。
- [阶段 14 · 30 评估驱动的 Agent 开发](../../../14-agent-engineering/30-eval-driven-agent-development/docs/zh.md)：在自己的任务分布上做 agent 评估。
- [阶段 16 · 24 Evaluation 与协调基准评测](../../../16-multi-agent-and-swarms/24-evaluation-coordination-benchmarks/docs/zh.md)：多 agent 场景下的评估。

### 延伸关键词
`METR` · `Time Horizon 1.1` · `HCAST` · `RE-Bench` · `SWAA` · `logistic regression` · `doubling time` · `eval-context gaming` · `sandbagging` · `bootstrap CI` · `extrapolation` · `monitorability eval` · `external evaluation`
