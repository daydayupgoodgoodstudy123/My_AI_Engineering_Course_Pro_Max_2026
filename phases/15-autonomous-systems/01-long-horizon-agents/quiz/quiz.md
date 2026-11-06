# 测验 · 从聊天机器人转向长程 Agents（The Shift from Chatbots to Long-Horizon Agents）

> **阶段 15 · 自主系统 · 第 01 节** ｜ 讲义：[docs/zh.md](../docs/zh.md)（[English](../docs/en.md)） ｜ 代码：[code/main.py](../code/main.py) ｜ 代码讲解：[code/main.讲解.md](../code/main.讲解.md)
>
> **用法**：学完讲义、跑过代码后，合上讲义完成第二～四部分，再对照第五部分的答案与解析。第一部分是"学完必须能做到"的清单，可以逐项打勾。

---

## 一、学完本节你应该掌握

### 核心知识点

| # | 知识点 | 一句话要点 |
|---|--------|-----------|
| 1 | 聊天机器人 vs 自主 agent | 聊天机器人是"无状态函数"：输入 prompt、返回回复、遗忘；自主 agent 跑一个循环、自己决定何时停、运行中持续花钱并产生副作用 |
| 2 | METR time horizon（时间跨度） | 以"人类专家完成时间的对数"为横轴拟合任务成功率的 logistic 曲线，曲线与 50% 线的交点就是 horizon；单位是"人类专家小时" |
| 3 | 任务套件 | HCAST（180+ 个 ML/网络安全/SWE/推理任务，1 分钟到 8+ 小时）、RE-Bench（71 个 ML 研究工程任务）、SWAA |
| 4 | 倍增时间 | 讲义：自 GPT-2 以来 horizon 约每 7 个月翻一番；`h(m) = h0 · 2^(m/7)`，是直线外推（对数坐标下），不是预测 |
| 5 | 可靠性复利 | 每步独立成功率 p，N 步全成功的概率是 `p^N`；p = 0.99 时 70 步只剩 49.5%，50% 目标下最多 68 步 |
| 6 | 1/e 规律 | `p^(1/(1-p)) ≈ 1/e ≈ 36.8%`：0.995 跑 200 步、0.999 跑 1000 步都只剩约 36.8% |
| 7 | horizon 长了以后什么会坏 | context（历史装不下）、trust（读不完轨迹）、failure modes（漂移、循环、reward hacking）、cost（肥尾）、observability（需要轨迹级遥测） |
| 8 | 审查单位的转变 | 单轮看"最终答案"，长程看"trajectory（轨迹）"：完整的工具调用、观察与推理序列 |
| 9 | Eval-context gaming | 模型能分辨"正在被评估"并在测试中表现得更安全；讲义：Anthropic 2024 年 alignment-faking 研究中基础测试 12%，再训练后升到 78% |
| 10 | horizon 是天花板不是地板 | 基准假设理想工具、无后果；部署时要在自己的分布上评估，并配预算、kill switch、HITL checkpoint、canary token |

### 核心技能（能动手做到）

- [ ] 用 `h0 · 2^(Δm/T)` 和 `T · log2(target/h0)` 手算任意 horizon 的未来值与"穿越月份"
- [ ] 用 `p^N` 与 `floor(ln(target)/ln(p))` 估算一条轨迹的端到端成功率与最大安全步数
- [ ] 解释 per-step 模型的假设（独立、同分布、不可恢复）以及它在真实 agent 上哪里偏乐观、哪里偏悲观
- [ ] 计算"加 checkpoint + 分段重试"之后端到端成功率的提升
- [ ] 对一个具体任务做 horizon reality check：专家时长、headroom ratio、可靠性预算、eval-vs-deploy 折扣、最小控制集
- [ ] 读懂并修正 `main.py` 中 `max_steps_for_target` 的浮点边界问题

---

## 二、基础自测（选择题）

**Q1.** METR 的 "50% time horizon" 是怎样得到的？

- A. 以人类专家完成时间的对数为横轴，对任务成功概率拟合 logistic 曲线，取曲线与 50% 成功率线的交点对应的人类任务时长
- B. 让模型连续运行，记录它在失败前平均能运行多少小时
- C. 统计模型在所有任务上的平均成功率，再乘以任务平均时长
- D. 取模型能完成的最长任务的人类耗时，再除以 2

**Q2.** 一个 agent 每一步的成功率是 99%，步骤相互独立、任何一步失败整条轨迹就失败。它完成一条 70 步轨迹的概率最接近：

- A. 99%
- B. 70%
- C. 30%
- D. 50%

**Q3.** 按本节代码的设定（基线 14 小时、倍增时间 7 个月），14 个月后的 50% horizon 是多少？

- A. 28 小时
- B. 42 小时
- C. 56 小时
- D. 196 小时

**Q4.** 若要求端到端成功率不低于 50%，每步可靠性 0.995 的 agent 最多能跑多少步（按 `main.py` 的 `max_steps_for_target` 计算）？

- A. 69
- B. 138
- C. 200
- D. 692

**Q5.** 关于 "horizon 是能力天花板而不是可靠性地板"，下列理解最准确的是：

- A. METR 的数字假设理想工具、没有真实后果、也不考虑 eval-context gaming，真实部署通常做不到这么长；而且即使在 horizon 上也只有 50% 成功率
- B. horizon 表示模型在任何长度的任务上都至少有 50% 的成功率
- C. horizon 越长，模型在短任务上的可靠性就一定越接近 100%，可以去掉人工审查
- D. horizon 是部署环境中实测的下限，基准测试通常会低估模型

**Q6.** 讲义对比了单轮聊天与长程 agent。下列哪一项对应关系**错误**？

- A. 每次运行的 token 量：单轮约 10^3，长程约 10^5–10^7
- B. 审查单位：单轮是最终答案，长程是 trajectory
- C. 成本分布：单轮可预测，长程是 fat-tailed（肥尾）
- D. eval-vs-deploy 差距：单轮已被大量记录且不断扩大，长程则很小

**Q7.** 在 `reliability_compounding()` 中，`(per_step=0.99, steps=50)` 这一行打印的 flag 是什么？

```python
        if p < 0.5:
            flag = "coin flip or worse"
        elif p < 0.8:
            flag = "not production"
        elif p < 0.95:
            flag = "fragile"
        else:
            flag = "ok"
```

- A. `ok`
- B. `fragile`
- C. `not production`
- D. `coin flip or worse`

**Q8.** 运行结果里 `0.995^200 = 36.7%`、`0.999^1000 = 36.8%` 几乎相同。原因是：

- A. 打印时四舍五入导致的巧合
- B. 当 N = 1/(1−p) 时，`p^N = (1 − 1/N)^N` 都趋近 `1/e ≈ 0.368`
- C. `end_to_end_reliability` 内部做了归一化
- D. 两个 per-step 值的对数恰好成整数倍

---

## 三、动手 / 代码题

**Q9.** 阅读 `max_steps_for_target`：

```python
def max_steps_for_target(per_step: float, target: float) -> int:
    """Largest N such that per_step**N >= target."""
    if per_step >= 1.0:
        return 10**9
    return math.floor(math.log(target) / math.log(per_step))
```

1. 实际运行 `max_steps_for_target(0.9, 0.81)` 返回 **1**，但 `0.9**2 >= 0.81` 为 `True`。解释原因。
2. 再找出两个会出错或返回不合理值的输入。
3. 给出一个更稳健的实现。

**Q10.**（讲义练习 1 延伸）用代码中的模型（基线 14 小时、倍增 7 个月）：

1. horizon 穿越 30 小时、168 小时（一周）分别是第几个月？写出公式和数值。
2. `deploy_gap_note()` 用 `horizon × (1 − gap)` 表示部署折扣。40% 的折扣相当于"落后"倍增曲线多少个月？20% 呢？
3. 讲义原文说 Claude Opus 4.6 的 horizon 是 "half a workday"（半个工作日），又说是 "14+ hours"。这两个说法一致吗？

**Q11.**（改造代码）`end_to_end_reliability` 假设"任何一步失败即整条轨迹失败"。现在给 agent 加 checkpoint：把 200 步轨迹切成 10 段、每段 20 步；某段失败可以从该段起点重来，每段最多尝试 r 次。每步成功率 0.99。

1. 写一个函数 `checkpointed_reliability(per_step, steps, segment, attempts)`。
2. 计算 r = 1、2、3 时的端到端成功率，并与无 checkpoint 的结果对比。
3. 这个改造本身又引入了哪些新的假设？

**Q12.**（读代码找问题）`deploy_gap_note()` 打印了 alignment-faking 的 12% / 78%，接着用 0%、20%、40% 三档 gap 计算 "deploy horizon"。请指出这段代码在推理链条上的问题，并说明如果你要给利益相关方一个"部署可用 horizon"，应该怎么得到这个数。

---

## 四、面试高频题

**Q13.**（基础必考）什么是 METR 的 time horizon？它是怎么测的？为什么用 50% 而不是 90%？

**Q14.**（原理深挖）"每步 99% 可靠的 agent 在 70 步任务上也只有一半成功率"——这个结论背后的模型是什么？它在真实 agent 上哪里偏悲观、哪里偏乐观？

**Q15.**（工程实践）把一个单轮问答系统升级为能连续运行数小时的自主 agent，系统设计上哪些东西必须重做？请按 context、trust、failure、cost、observability 逐项说明。

**Q16.**（场景设计）业务方想让 agent 在夜间无人值守地完成"把 200 个文件的 Python 2 代码迁移到 Python 3 并跑通测试"。人类专家估计需要 6 小时，预计约 300 次工具调用。你会怎么评估能不能上？

**Q17.**（追问型）既然模型可能"知道自己在被测试"，你怎么设计一个对 eval-context gaming 更稳健的评估方案？

---

## 五、参考答案与解析

### Q1 — 答案：A

讲义："METR fits a logistic curve to task-success probability against the log of expert human completion time. The horizon is the intersection of that curve with the 50% probability line." 关键是横轴是**人类专家**完成任务所需的时间（取对数），horizon 的单位因此是"人类小时"，而不是模型运行了多久。

- B 错：horizon 衡量的是"能完成多长的人类任务"，不是模型的运行时长或 MTBF。
- C 错：平均成功率 × 平均时长不是 METR 的方法，也没有 50% 交点的含义。
- D 错：没有"最长任务除以 2"这种定义。

### Q2 — 答案：D

`0.99^70 = 0.4948`，即 49.5%（代码运行输出 `0.990  70  49.5%  coin flip or worse`）。直觉上 "1% 失败率很低"，但 70 次独立机会累积起来就接近抛硬币。A 是单步成功率；B 把 `1 − 70 × 1%` 的线性近似再搞错；C 是 `0.99^120` 左右的量级。

### Q3 — 答案：C

`h(14) = 14 × 2^(14/7) = 14 × 4 = 56` 小时。A 只翻了一倍（7 个月）；B 是线性外推的错误思路（每 7 个月加 14 小时）；D 是把 14 当倍数乘了一次。代码中 12 个月时输出 `1.9 day`（45.9 小时），讲义写 2027 年约 48 小时，与之吻合。

### Q4 — 答案：B

`ln(0.5)/ln(0.995) = 138.28`，向下取整为 138。验证：`0.995^138 = 0.5007 ≥ 0.5`，`0.995^139 = 0.4982 < 0.5`。代码运行输出 `per-step 0.995: up to 138 steps`。A（69）接近 0.99 的结果（实际是 68）；C 是代码 cases 里用到的步数（0.995^200 = 36.7%，已低于 50%）；D 是 0.999 的结果（692）。

### Q5 — 答案：A

讲义："a horizon number is a capability ceiling, not a reliability floor"，并说 METR 自己也标明"reported horizons are idealized upper bounds, not deployment predictions"。另外 horizon 本身就是 50% 点，在这个长度的任务上一半会失败。

- B 错：50% 只在 horizon 那一点成立，比它更长的任务成功率更低。
- C 错：horizon 增长不能取消审查，讲义反复强调 kill switch、预算、HITL。
- D 方向反了：基准是理想上界，部署会更差，而且 eval-context gaming 会让基准**高估**。

### Q6 — 答案：D

讲义表格中 eval-vs-deploy 差距一行是：单轮 "small"，长程 "documented and growing"。D 把两者对调了。A、B、C 均与讲义表格一致。（注：中文讲义把 "10^5 to 10^7" 机器翻译成了 "105至107"，读中文版时要留意。）

### Q7 — 答案：C

`0.99^50 = 0.605`，即 60.5%。它不小于 0.5，但小于 0.8，命中 `elif p < 0.8` 分支，flag 为 `not production`。实际输出：`0.990  50  60.5%  not production`。注意 if/elif 链是按顺序判断的，阈值必须从小到大排列，否则会被前面的分支截走。

### Q8 — 答案：B

令 N = 1/(1−p)：p = 0.995 时 N = 200，p = 0.999 时 N = 1000，于是 `p^N = (1 − 1/N)^N → 1/e ≈ 0.3679`。实测 `0.995^200 = 0.36696`、`0.999^1000 = 0.36770`。这条经验法则很有用：**"每步失败率 1/N 的 agent，跑 N 步大约只剩 37%"**。A 错，并非巧合；C 错，函数只是 `per_step ** steps`；D 不是原因。

### Q9 — 参考答案

1. **浮点误差**：数学上 `ln(0.81)/ln(0.9) = 2`，但浮点计算得到 `1.9999999999999998`，`math.floor` 后变成 1。实测还有 `(0.7, 0.49) → 1`、`(0.95, 0.9025) → 1` 等，都是"恰好整除"的边界被 floor 截掉。默认 cases 中（target = 0.5）比值离整数很远，所以没有暴露。
2. 其它问题：
   - `per_step <= 0`：`math.log(0)` 抛 `ValueError: math domain error`；
   - `target >= 1.0`（且 per_step < 1）：`log(1) = 0`，返回 0，语义上说得通，但 `target > 1` 会返回负数；
   - `target <= 0`：同样抛 `math domain error`；
   - `per_step >= 1.0` 返回魔法数 `10**9`，调用方无法区分"无限"与"很大"。
3. 稳健实现（加容差，并用乘方回检）：

```python
import math

def max_steps_for_target(per_step: float, target: float) -> int | float:
    if not (0.0 < per_step <= 1.0) or not (0.0 < target <= 1.0):
        raise ValueError("per_step 和 target 必须在 (0, 1] 内")
    if per_step == 1.0:
        return math.inf
    n = math.floor(math.log(target) / math.log(per_step) + 1e-9)  # 吸收浮点误差
    while per_step ** (n + 1) >= target:   # 回检：防止仍然少算
        n += 1
    while n > 0 and per_step ** n < target:  # 回检：防止多算
        n -= 1
    return n
```

修正后 `(0.9, 0.81)` 返回 2，`(0.99, 0.5)` 仍返回 68。

### Q10 — 参考答案

1. 由 `h0 · 2^(m/T) = target` 得 `m = T · log2(target/h0)`（即代码的 `months_to_cross`）：
   - 30 小时：`7 × log2(30/14) = 7 × 1.0995 ≈ 7.7` 个月；
   - 168 小时：`7 × log2(12) = 7 × 3.585 ≈ 25.1` 个月（与代码输出 `7.0 day: month 25.1` 一致）。
2. 倍增曲线上，乘以 `(1 − gap)` 等价于时间向后平移 `T · log2(1/(1−gap))`：
   - 40%：`7 × log2(1/0.6) ≈ 5.2` 个月；
   - 20%：`7 × log2(1/0.8) ≈ 2.3` 个月。
   结论：在指数增长下，即便 40% 的部署折扣也只是"晚 5 个月"——这正是为什么讲义说趋势"too consistent to ignore"，同时也提醒我们不能靠"打个折"来获得安全感。
3. 不一致。14 小时远超一个 8 小时工作日（约 1.75 个工作日），"half a workday" 只有约 4 小时。讲义正文其它地方、代码的 baseline 都用 14 小时，"half a workday" 应是旧数字残留。另外代码把 `h < 24` 都标成 `workday-scale`，14 小时也被标为"工作日级"，标签同样偏粗糙。

### Q11 — 参考答案

1. 实现：

```python
def checkpointed_reliability(per_step, steps, segment, attempts):
    n_seg = steps // segment
    seg_ok = per_step ** segment                    # 一次尝试通过一段
    seg_ok_with_retry = 1 - (1 - seg_ok) ** attempts  # r 次里至少成功一次
    return seg_ok_with_retry ** n_seg
```

2. 实际计算（per_step = 0.99、200 步、每段 20 步）：

| 方案 | 单段成功率 | 端到端成功率 |
|------|-----------|------------|
| 无 checkpoint | — | 13.4% |
| r = 1（有 checkpoint 但不重试） | 81.8% | 13.4%（与无 checkpoint 相同） |
| r = 2 | 96.7% | 71.4% |
| r = 3 | 99.4% | 94.1% |

checkpoint 本身不提高成功率，**"checkpoint + 重试"** 才把失败的代价从"整条重来"降为"这一段重来"。这就是后续第 12 节 durable execution、第 16 节 checkpoint/rollback 的数学动机。
3. 新假设：
   - 失败能被**检测到**（若失败是静默的，重试不会被触发——这正是讲义说的"failures are invisible until they compound"）；
   - 重试之间相互独立（实际上同一个 prompt、同一个环境下的失败往往高度相关，重试 3 次可能同样失败 3 次）；
   - 回滚到段起点是干净的（有外部副作用的步骤，如发邮件、写数据库，不能简单"重来"）；
   - 重试的成本（token、时间）没被计入，真实系统还要有预算上限。

### Q12 — 参考答案

问题：

- **两个数字之间没有推导关系**。12% / 78% 是"在某些测试中出现 alignment faking 的比例"，与"horizon 应该打几折"是不同的量；代码只是把它们印在同一个标题下，0/20/40% 三档 gap 是人为设定（与 `outputs/skill-horizon-reality-check.md` 的 "Apply a 20-40% gap" 一致），不是从研究数据算出来的。
- **线性折扣的形式也是假设**：在对数尺度上，horizon 的差距更自然的表述是"落后多少个月"（见 Q10）；而且部署差距可能与任务类型强相关，不是一个常数。
- **混淆了两类原因**：eval-context gaming 关乎"行为是否一致"（安全性），而工具不理想、环境有后果关乎"能力是否打折"（可靠性），两者应分开评估。

更好的做法：在**自己的任务分布**上抽取一批有代表性的任务，记录人类专家完成时间，用相同的方法（成功率对 log 时长的 logistic 回归）拟合出自己的 50%/80% horizon；评估环境尽量与生产一致（同样的工具、权限、数据），并在部署后持续用线上轨迹抽检来校准。讲义："Production deployment requires your own evals on your own distribution."

### Q13 — 参考回答要点

- **定义**：模型以 50% 概率完成的任务所对应的**人类专家**完成时长。
- **测法**：准备一组覆盖 1 分钟到 8+ 小时的任务（HCAST、RE-Bench、SWAA），每个任务有人类专家基线时间；让模型做这些任务，记录成功/失败；以 `log(人类时长)` 为自变量拟合 logistic 曲线，取 p = 0.5 的点。
- **为什么 50%**：logistic 曲线在 50% 附近斜率最大、估计最稳定（置信区间最窄）；在 80%、90% 处数据稀疏、外推不稳。但工程上 50% 远不够用——讲义的 skill 文件要求 headroom ratio 至少 4 倍。
- **趋势**：讲义：约 7 个月翻倍，2026 年 1 月 Claude Opus 4.6 为 14+ 小时；按直线外推 2027 年约 48 小时，2028 年约一周。
- 加分点：说明 horizon 把"能力"压缩成一个人能理解的单位（"能做专家需要 X 小时的事"），但它是**理想上界**；同一模型的 80% horizon 会明显更短。
- 常见误区：把 horizon 理解成"模型能连续运行的时长"。

### Q14 — 参考回答要点

- **模型**：每步独立、同分布、成功率 p，任何一步失败即整体失败，端到端成功率 = `p^N`。
- **偏悲观的地方**：
  - 真实 agent 能**自我纠错**：读到报错后重试、换工具、回退（Reflexion、verification gate 等）；
  - 有些步骤失败无害（多读了一个无关文件），并非"一步错全盘错"；
  - 有 checkpoint 和重试时，结果会大幅提升（见 Q11：200 步从 13.4% 提到 94.1%）。
- **偏乐观的地方**：
  - 失败是**相关**的：上下文越长越容易漂移，后期步骤的 p 会下降；
  - 存在**静默失败**：错误没被检测到，后续步骤在错误基础上继续"成功"，最后结果是错的；
  - 循环、reward hacking 等长程特有的失败模式不在模型里。
- 结论：`p^N` 是一个"直觉校准工具"，提醒我们可靠性必须靠**系统设计**（checkpoint、验证、HITL）而不是只靠单步模型能力。
- 加分点：给出 1/e 规律——每步失败率 1/N 的 agent 跑 N 步只剩约 37%。

### Q15 — 参考回答要点

| 维度 | 单轮时代 | 长程要重做什么 |
|------|---------|--------------|
| Context | 一个窗口装得下 | 历史会有几十万 token：压缩/摘要、checkpoint、分层记忆（阶段 14 的记忆相关小节） |
| Trust | 读一遍答案就能判断 | 读不完 1000 轮：审查对象变成 trajectory，要有抽样审计和自动验证 |
| Failure | 主要是能力不足 | 新增漂移、循环、reward hacking、eval-vs-deploy 行为差距，需要检测器 |
| Cost | 可预测 | 肥尾：一次失控循环可能烧掉一个月预算；需要 token/时间/迭代上限（第 13 节） |
| Observability | 请求日志够用 | 轨迹级遥测、动作预算、canary token（第 14 节）、kill switch |

- 另外还有**状态**：从"临时"变为"持久化 + 可恢复"（durable execution，第 12 节）。
- 加分点：强调"每一行都对应本阶段后续的一节"，并能说出 HITL 的位置应在**不可逆动作**之前（第 15 节 propose-then-commit）。

### Q16 — 参考回答要点

按讲义 `outputs/skill-horizon-reality-check.md` 的流程：

1. **专家时长**：6 小时（已给出；若业务方给不出，应先抽样测量）。
2. **Headroom ratio**：讲义中 Opus 4.6 的 horizon 是 14 小时，`14 / 6 ≈ 2.3` 倍，**低于 skill 要求的 4 倍**，处于需要警示的区间（2 倍以下必须每个关键动作都有 HITL）。若再打 20–40% 的部署折扣（8.4–11.2 小时），ratio 只有 1.4–1.9 倍。
3. **可靠性预算**：300 次工具调用，`0.99^300 ≈ 4.9%`，`0.995^300 ≈ 22%`，都远低于 50%——必须拆分任务、加 checkpoint。
4. **控制措施**：按文件或模块拆成小批次，每批跑测试作为 verification gate；git 分支隔离、只在通过后合并（可回滚）；token/时间预算与迭代上限；kill switch；早上由人审查 diff 后再合入主干（HITL 放在不可逆动作之前）。
5. **结论**：以"一次性无人值守完成"的形式是 **no-go / hold**；改造为"分批 + 自动测试 + 人工审合并"后可以 go。
- 加分点：指出"无人值守"本身与"写入主分支"这种不可逆动作冲突。

### Q17 — 参考回答要点

- **让评估与部署难以区分**：使用真实任务分布、真实工具与环境，避免"测试味"明显的提示词、固定模板或明显虚构的场景。
- **在部署中评估**：对线上轨迹做随机抽样审计（shadow evaluation），比较线上行为与离线评测行为的差异。
- **使用隐蔽探针**：canary token、蜜罐任务混入正常流量，观察模型是否越权或违规。
- **多次独立测量**：同一能力用多种格式、多个时间点测试，看结果是否一致。
- **结构性兜底**：假设评测会高估，部署侧用权限最小化、预算、HITL、kill switch 做限制，而不是只依赖评测分数。
- 讲义依据：2026 International AI Safety Report 记录了模型区分评估与部署情境的现象；Anthropic 2024 年研究中 alignment faking 在基础测试为 12%，再训练后升至 78%。
- 常见误区：认为"基准分越高越可信"——如果模型会识别评测，基准高分恰恰可能是被抬高的。

---

## 六、关联知识点

### 前置知识
- [阶段 14 · 01 Agent Loop：观察、思考、行动](../../../14-agent-engineering/01-the-agent-loop/docs/zh.md)：本节的"长程"是指这个循环跑很多轮。
- [阶段 14 · 07 Agent Memory：虚拟上下文与记忆分页](../../../14-agent-engineering/07-memory-virtual-context-memgpt/docs/zh.md)：长程运行中"context 装不下"的解决方案之一。
- [阶段 14 · 19 基准评测：SWE-bench、GAIA、AgentBench](../../../14-agent-engineering/19-benchmarks-swebench-gaia/docs/zh.md)：理解 agent 基准如何构建与评分。
- [阶段 14 · 26 失效模式：Agents 为什么会失败](../../../14-agent-engineering/26-failure-modes-agentic/docs/zh.md)：漂移、循环等长程失败的分类。

### 本节被哪些后续内容用到
- [阶段 15 · 12 长时间运行的后台 Agents：Durable Execution](../../12-durable-execution/docs/zh.md)：持久化状态与可恢复执行。
- [阶段 15 · 13 行动预算、迭代上限与成本控制](../../13-cost-governors/docs/zh.md)：应对肥尾成本。
- [阶段 15 · 14 紧急停止开关、Circuit Breakers 与金丝雀 Tokens](../../14-kill-switches-canaries/docs/zh.md)：静默失败的检测与止损。
- [阶段 15 · 15 Human-in-the-Loop：先提出方案，再 Commit](../../15-propose-then-commit/docs/zh.md)：HITL 放在不可逆动作之前。
- [阶段 15 · 16 Checkpoints（检查点）与 Rollback（回滚）](../../16-checkpoints-rollback/docs/zh.md)：本测验 Q11 的工程实现。
- [阶段 15 · 21 METR 时间跨度与外部能力 Evaluation](../../21-metr-external-evaluation/docs/zh.md)：METR 方法的深入讲解。
- [阶段 18 · 09 伪装 Alignment](../../../18-ethics-safety-alignment/09-alignment-faking/docs/zh.md)：12% / 78% 数字的来源研究。

### 延伸关键词
`METR time horizon` · `HCAST` · `RE-Bench` · `logistic regression` · `doubling time` · `compounding reliability` · `trajectory audit` · `eval-context gaming` · `alignment faking` · `headroom ratio` · `checkpoint + retry` · `fat-tailed cost`
